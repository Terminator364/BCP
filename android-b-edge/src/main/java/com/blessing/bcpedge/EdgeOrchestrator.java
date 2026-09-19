package com.blessing.bcpedge;

import android.content.Context;
import android.content.SharedPreferences;

import com.blessing.bcpedge.storage.EdgeDao;
import com.blessing.bcpedge.storage.EdgeDatabase;
import com.blessing.bcpedge.storage.EdgeJobEntity;
import com.blessing.bcpedge.storage.EdgeMemoryEntity;
import com.blessing.bcpedge.storage.EdgeProjectEntity;
import com.blessing.bcpedge.storage.EdgeReceiptEntity;
import com.blessing.bcpedge.work.EdgeWorkScheduler;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.List;
import java.util.UUID;

public final class EdgeOrchestrator {
    private static final String PREFS = "bcp_edge_orchestrator_settings";
    private final SharedPreferences settings;
    private final EdgeDao dao;

    public EdgeOrchestrator(Context context) {
        Context app = context.getApplicationContext();
        settings = app.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        dao = EdgeDatabase.get(app).edgeDao();
        EdgeWorkScheduler.schedulePeriodic(app);
    }

    public synchronized void setMode(String mode) {
        // Mode is reconstructable operating state, not canonical project memory.
        settings.edit().putString("mode", mode).putLong("mode_at", System.currentTimeMillis()).commit();
    }

    public synchronized String getMode() {
        return settings.getString("mode", "EDGE_ONLY");
    }

    public synchronized boolean shouldRunPeriodicSync(long minIntervalMs) {
        long now = System.currentTimeMillis();
        long last = settings.getLong("orchestration_sync_attempt_at", 0L);
        if (last > 0L && now >= last && (now - last) < Math.max(30_000L, minIntervalMs)) return false;
        return settings.edit().putLong("orchestration_sync_attempt_at", now).commit();
    }

    public void ensureProject(String projectId, long headRevision, long epoch) {
        long now = System.currentTimeMillis();
        dao.putProject(new EdgeProjectEntity(projectId, "ACTIVE", headRevision, epoch, now));
    }

    public JSONArray projectRegistry() {
        JSONArray out = new JSONArray();
        for (EdgeProjectEntity p : dao.projects()) {
            JSONObject o = new JSONObject();
            try {
                o.put("project_id", p.projectId);
                o.put("status", p.status);
                o.put("head_revision", p.headRevision);
                o.put("coordinator_epoch", p.coordinatorEpoch);
                o.put("updated_at", p.updatedAt);
                out.put(o);
            } catch (Exception ignored) {}
        }
        return out;
    }

    public void cacheContext(String projectId, JSONObject context) {
        long now = System.currentTimeMillis();
        long revision = 0;
        JSONObject head = context.optJSONObject("head");
        if (head != null) revision = head.optLong("revision", 0);
        ensureProject(projectId, revision, 0);
        dao.putMemory(new EdgeMemoryEntity(
                projectId, "OPERATING_STATE", "context_pack",
                context.toString(), "CACHE", "PC_CONTEXT_PACK",
                false, now, now, null
        ));
    }

    public JSONObject cachedContext(String projectId) {
        try {
            List<EdgeMemoryEntity> rows = dao.memoryForScope(projectId, "OPERATING_STATE", System.currentTimeMillis(), 32);
            for (EdgeMemoryEntity row : rows) {
                if (!"context_pack".equals(row.memoryKey)) continue;
                JSONObject out = new JSONObject(row.valueJson);
                out.put("source", "B_EDGE_ROOM_CACHE");
                out.put("offline", true);
                out.put("mode", getMode());
                out.put("cached_at", row.updatedAt);
                return out;
            }
        } catch (Exception ignored) {}
        return new JSONObject();
    }

    public void putMemory(String projectId, String layer, String key, Object value,
                          String evidenceClass, boolean pinned, Long expiresAt) {
        long now = System.currentTimeMillis();
        dao.putMemory(new EdgeMemoryEntity(
                projectId, layer, key, JSONObject.valueToString(value),
                evidenceClass == null ? "UNVERIFIED" : evidenceClass,
                "B_EDGE", pinned, now, now, expiresAt
        ));
    }

    public JSONObject memorySnapshot(String projectId) {
        JSONObject out = new JSONObject();
        String[] scopes = new String[]{"USER_MEMORY","PROJECT_MEMORY","TECHNICAL_KNOWLEDGE","OPERATING_STATE","HISTORY","POLICY"};
        long now = System.currentTimeMillis();
        try {
            for (String scope : scopes) {
                JSONArray rows = new JSONArray();
                for (EdgeMemoryEntity m : dao.memoryForScope(projectId, scope, now, 24)) {
                    JSONObject r = new JSONObject();
                    r.put("key", m.memoryKey);
                    r.put("value", new JSONObject("{\"v\":" + m.valueJson + "}").opt("v"));
                    r.put("evidence_class", m.evidenceClass);
                    r.put("pinned", m.pinned);
                    r.put("updated_at", m.updatedAt);
                    rows.put(r);
                }
                out.put(scope, rows);
            }
        } catch (Exception ignored) {}
        return out;
    }

    public JSONObject queueJob(String projectId, String kind, JSONObject payload,
                               boolean requiresPc, int priority, String resourceClass,
                               JSONArray dependencies) {
        JSONObject out = new JSONObject();
        try {
            if (dao.countPendingJobs() >= EdgePolicy.boundedQueueLimit()) {
                out.put("result", "HOLD_BACKPRESSURE");
                out.put("state", "HOLD");
                out.put("reason", "DURABLE_QUEUE_CAPACITY_REACHED");
                out.put("queued", false);
                return out;
            }
            String id = UUID.randomUUID().toString();
            String idem = "edge-job-" + id;
            long now = System.currentTimeMillis();
            String state = dependencies != null && dependencies.length() > 0
                    ? "BLOCKED" : EdgePolicy.nextState(requiresPc, getMode());
            EdgeJobEntity job = new EdgeJobEntity(
                    id, projectId, kind, payload.toString(), state, requiresPc,
                    priority, resourceClass == null ? (requiresPc ? "PC_R3" : "EDGE_R1") : resourceClass,
                    idem, now, now
            );
            long inserted = dao.insertJob(job);
            if (inserted == -1L) {
                out.put("result", "ALREADY_QUEUED");
                out.put("local_id", id);
                return out;
            }
            if (dependencies != null) {
                for (int i = 0; i < dependencies.length(); i++) {
                    String dep = dependencies.optString(i, "");
                    if (!dep.isEmpty()) dao.insertDependency(
                            new com.blessing.bcpedge.storage.EdgeDependencyEntity(id, dep));
                }
            }
            out.put("result", "QUEUED");
            out.put("local_id", id);
            out.put("idempotency_key", idem);
            out.put("project_id", projectId);
            out.put("kind", kind);
            out.put("payload", payload);
            out.put("requires_pc", requiresPc);
            out.put("priority", priority);
            out.put("resource_class", job.resourceClass);
            out.put("state", state);
            out.put("created_at", now);
            out.put("queued", true);
            return out;
        } catch (Exception e) {
            try {
                out.put("result", "HOLD_PERSISTENCE_ERROR");
                out.put("state", "HOLD");
                out.put("queued", false);
                out.put("error", e.getClass().getSimpleName());
            } catch (Exception ignored) {}
            return out;
        }
    }

    public JSONArray pendingJobs(String projectId) {
        JSONArray out = new JSONArray();
        for (EdgeJobEntity j : dao.pendingJobs(projectId, 128)) {
            JSONObject o = new JSONObject();
            try {
                if ("BLOCKED".equals(j.state) && dao.unresolvedDependencies(j.localId) == 0) {
                    String next = EdgePolicy.nextState(j.requiresPc, getMode());
                    dao.setJobState(j.localId, next, System.currentTimeMillis());
                    j.state = next;
                }
                o.put("local_id", j.localId);
                o.put("project_id", j.projectId);
                o.put("kind", j.kind);
                o.put("payload", new JSONObject(j.payloadJson));
                o.put("state", j.state);
                o.put("requires_pc", j.requiresPc);
                o.put("priority", j.priority);
                o.put("resource_class", j.resourceClass);
                o.put("idempotency_key", j.idempotencyKey);
                o.put("created_at", j.createdAt);
                out.put(o);
            } catch (Exception ignored) {}
        }
        return out;
    }

    public void acknowledgeRemoteJob(String projectId, JSONObject job, JSONObject receipt) {
        try {
            String localId = job.optString("local_id", "");
            String idem = job.optString("idempotency_key", "");
            String result = receipt.optString("result", "ACCEPTED");
            long revision = receipt.optLong("revision", 0);
            String actionId = receipt.optString("event_hash", "");
            if (actionId.isEmpty()) actionId = UUID.randomUUID().toString();
            dao.insertReceipt(new EdgeReceiptEntity(
                    actionId, localId, projectId, idem, result,
                    receipt.toString(), revision, System.currentTimeMillis()
            ));
            if (!localId.isEmpty()) {
                dao.setJobState(localId, "COMMITTED", System.currentTimeMillis());
                dao.deleteJob(localId);
            }
        } catch (Exception ignored) {}
    }

    public int pendingCount() {
        return dao.countPendingJobs();
    }

    public int compactExpiredMemory() {
        return dao.deleteExpiredMemory(System.currentTimeMillis());
    }
}
