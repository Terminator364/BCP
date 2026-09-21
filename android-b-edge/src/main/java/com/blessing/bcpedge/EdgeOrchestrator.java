package com.blessing.bcpedge;

import android.content.Context;
import android.content.SharedPreferences;

import com.blessing.bcpedge.storage.EdgeDao;
import com.blessing.bcpedge.storage.EdgeDatabase;
import com.blessing.bcpedge.storage.EdgeJobEntity;
import com.blessing.bcpedge.storage.EdgeMemoryEntity;
import com.blessing.bcpedge.storage.EdgeCapabilityEntity;
import com.blessing.bcpedge.storage.EdgeMemoryClaimEntity;
import com.blessing.bcpedge.storage.EdgeProjectEntity;
import com.blessing.bcpedge.storage.EdgeReceiptEntity;
import com.blessing.bcpedge.storage.EdgeSentinelEntity;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.List;
import java.util.UUID;
import java.security.MessageDigest;
import java.nio.charset.StandardCharsets;

public final class EdgeOrchestrator {
    private static final String PREFS = "bcp_edge_orchestrator_settings";
    private final SharedPreferences settings;
    private final EdgeDao dao;

    public EdgeOrchestrator(Context context) {
        Context app = context.getApplicationContext();
        settings = app.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        dao = EdgeDatabase.get(app).edgeDao();
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
        int updated = dao.updateProjectHeadPreservingEpoch(projectId, "ACTIVE", headRevision, now);
        if (updated == 0) {
            dao.insertProject(new EdgeProjectEntity(projectId, "ACTIVE", headRevision, epoch, now));
        }
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
        JSONObject receipt = admitMemoryClaim(
                projectId, layer, key, value, evidenceClass,
                "B_EDGE_INTERNAL", "LOCAL_NODE_POLICY", "",
                "", pinned, expiresAt);
        String result = receipt.optString("result", "");
        if (!receipt.optBoolean("ok", false)
                || "REJECTED".equals(result) || "HOLD".equals(result)) {
            throw new IllegalArgumentException(
                    receipt.optString("error", "memory_admission_rejected_precedence"));
        }
    }

    public JSONObject admitMemoryClaim(String projectId, String scope, String key, Object value,
                                       String evidenceClass, String source, String authority,
                                       String supersedesClaimId, String idempotencyKey,
                                       boolean pinned, Long expiresAt) {
        JSONObject out = new JSONObject();
        long now = System.currentTimeMillis();
        try {
            String p = projectId == null ? "" : projectId.trim();
            String s = scope == null ? "" : scope.trim().toUpperCase();
            String k = key == null ? "" : key.trim();
            String evidence = evidenceClass == null ? "UNVERIFIED" : evidenceClass.trim().toUpperCase();
            String src = source == null ? "UNKNOWN" : source.trim();
            String auth = authority == null ? "UNSPECIFIED" : authority.trim().toUpperCase();
            String idem = idempotencyKey == null ? "" : idempotencyKey.trim();
            String supersedes = supersedesClaimId == null ? "" : supersedesClaimId.trim();
            if (p.isEmpty() || s.isEmpty() || k.isEmpty()) throw new IllegalArgumentException("invalid_memory_claim_identity");
            if (k.length() > 160 || s.length() > 64 || src.length() > 160 || auth.length() > 96) {
                throw new IllegalArgumentException("memory_claim_field_too_long");
            }
            if (idem.isEmpty()) idem = "memory-claim:" + sha256(p + "\n" + s + "\n" + k + "\n" + jsonValueString(value) + "\n" + evidence + "\n" + src);
            if (idem.length() > 192) throw new IllegalArgumentException("idempotency_key_too_long");

            EdgeMemoryClaimEntity prior = dao.memoryClaimByIdempotency(p, idem);
            if (prior != null) return memoryClaimReceipt(prior, "ALREADY_RECORDED");

            EdgeMemoryEntity old = dao.memoryItem(p, s, k);
            if (old != null && old.expiresAt != null && old.expiresAt <= now) old = null;
            boolean admitted = EdgePolicy.canReplaceMemory(
                    s, old == null ? null : old.evidenceClass,
                    old != null && old.pinned, evidence);
            String claimId = "mcl-" + UUID.randomUUID();
            String state = admitted ? "ADMITTED" : "REJECTED";
            String reason = admitted ? "PRECEDENCE_ACCEPTED" : "PRECEDENCE_REJECTED";
            EdgeMemoryClaimEntity claim = new EdgeMemoryClaimEntity(
                    claimId, p, s, k, jsonValueString(value), evidence,
                    src.isEmpty() ? "UNKNOWN" : src,
                    auth.isEmpty() ? "UNSPECIFIED" : auth,
                    supersedes, state, reason, idem, pinned, now, now);
            long inserted = dao.insertMemoryClaim(claim);
            if (inserted == -1L) {
                EdgeMemoryClaimEntity existing = dao.memoryClaimByIdempotency(p, idem);
                return memoryClaimReceipt(existing == null ? claim : existing, "ALREADY_RECORDED");
            }

            if (admitted) {
                if (!supersedes.isEmpty()) {
                    dao.setMemoryClaimState(supersedes, "SUPERSEDED", "SUPERSEDED_BY:" + claimId, now);
                }
                boolean effectivePinned = pinned || (old != null && old.pinned);
                long createdAt = old == null ? now : old.createdAt;
                dao.putMemory(new EdgeMemoryEntity(
                        p, s, k, jsonValueString(value), evidence,
                        src.isEmpty() ? "B_EDGE" : src,
                        effectivePinned, createdAt, now, expiresAt));
            }
            out = memoryClaimReceipt(claim, admitted ? "ADMITTED" : "REJECTED");
            out.put("canonical_memory_updated", admitted);
        } catch (Exception e) {
            try {
                out.put("ok", false);
                out.put("result", "HOLD");
                out.put("error", e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage());
            } catch (Exception ignored) {}
        }
        return out;
    }

    public JSONArray memoryClaimLedger(String projectId, int requestedLimit) {
        JSONArray out = new JSONArray();
        int limit = Math.max(1, Math.min(200, requestedLimit));
        for (EdgeMemoryClaimEntity row : dao.memoryClaims(projectId, limit)) {
            out.put(memoryClaimJson(row));
        }
        return out;
    }

    public void putCapability(String projectId, String capabilityId, String nodeId,
                              String provider, String capabilityKind, String state,
                              String transport, JSONObject details, String evidenceClass,
                              long observedAt, Long expiresAt) {
        String cid = capabilityId == null ? "" : capabilityId.trim().toUpperCase();
        if (cid.isEmpty() || cid.length() > 128) throw new IllegalArgumentException("invalid_capability_id");
        long now = System.currentTimeMillis();
        dao.putCapability(new EdgeCapabilityEntity(
                projectId,
                cid,
                nodeId == null || nodeId.trim().isEmpty() ? "B-EDGE" : nodeId.trim(),
                provider == null ? "LOCAL" : provider.trim().toUpperCase(),
                capabilityKind == null ? "GENERIC" : capabilityKind.trim().toUpperCase(),
                state == null ? "UNKNOWN" : state.trim().toUpperCase(),
                transport == null ? "LOCAL" : transport.trim().toUpperCase(),
                details == null ? "{}" : details.toString(),
                evidenceClass == null ? "MACHINE_READBACK" : evidenceClass.trim().toUpperCase(),
                observedAt <= 0L ? now : observedAt,
                expiresAt,
                now
        ));
    }

    public JSONArray capabilityRegistry(String projectId, int requestedLimit) {
        JSONArray out = new JSONArray();
        int limit = Math.max(1, Math.min(200, requestedLimit));
        long now = System.currentTimeMillis();
        for (EdgeCapabilityEntity row : dao.capabilities(projectId, now, limit)) {
            JSONObject item = new JSONObject();
            try {
                item.put("capability_id", row.capabilityId);
                item.put("node_id", row.nodeId);
                item.put("provider", row.provider);
                item.put("kind", row.capabilityKind);
                item.put("state", row.state);
                item.put("transport", row.transport);
                item.put("details", new JSONObject(row.detailsJson));
                item.put("evidence_class", row.evidenceClass);
                item.put("observed_at", row.observedAt);
                item.put("expires_at", row.expiresAt == null ? JSONObject.NULL : row.expiresAt);
                item.put("updated_at", row.updatedAt);
            } catch (Exception ignored) {}
            out.put(item);
        }
        return out;
    }

    private static JSONObject memoryClaimJson(EdgeMemoryClaimEntity row) {
        JSONObject out = new JSONObject();
        try {
            out.put("claim_id", row.claimId);
            out.put("project_id", row.projectId);
            out.put("scope", row.scope);
            out.put("memory_key", row.memoryKey);
            out.put("value", new JSONObject("{\"v\":" + row.valueJson + "}").opt("v"));
            out.put("evidence_class", row.evidenceClass);
            out.put("source", row.source);
            out.put("authority", row.authority);
            out.put("supersedes_claim_id", row.supersedesClaimId);
            out.put("state", row.state);
            out.put("reason", row.reason);
            out.put("idempotency_key", row.idempotencyKey);
            out.put("pinned", row.pinned);
            out.put("admitted_at", row.admittedAt);
            out.put("updated_at", row.updatedAt);
        } catch (Exception ignored) {}
        return out;
    }

    private static JSONObject memoryClaimReceipt(EdgeMemoryClaimEntity row, String result) {
        JSONObject out = memoryClaimJson(row);
        try {
            out.put("ok", row != null);
            out.put("result", result);
            out.put("authority", "B_EDGE_MEMORY_ADMISSION_LEDGER");
        } catch (Exception ignored) {}
        return out;
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
            String result = receipt.optString("result", "ACCEPTED").trim().toUpperCase();
            long revision = receipt.optLong("revision", 0);
            String rawReceipt = receipt.toString();
            String outputHash = sha256(rawReceipt);
            String actionId = receipt.optString("action_id", receipt.optString("event_hash", ""));
            if (actionId.isEmpty()) actionId = "receipt-" + sha256(idem + "\n" + rawReceipt);
            dao.insertReceipt(new EdgeReceiptEntity(
                    actionId, localId, projectId, idem, result,
                    outputHash, revision, System.currentTimeMillis()
            ));
            if (localId.isEmpty()) return;
            if (EdgePolicy.isCompletionResult(result)) {
                dao.setJobState(localId, "COMMITTED", System.currentTimeMillis());
                dao.deleteJob(localId);
            } else if (EdgePolicy.isRemoteQueueAccepted(result)) {
                // Dispatch acknowledgement is not completion proof.
                dao.setJobState(localId, "REMOTE_QUEUED", System.currentTimeMillis());
            } else {
                dao.setJobState(localId, "HOLD", System.currentTimeMillis());
            }
        } catch (Exception ignored) {}
    }

    public JSONObject acknowledgeLocalJob(JSONObject job, JSONObject output) {
        JSONObject receipt = new JSONObject();
        try {
            String localId = job.optString("local_id", "");
            String projectId = job.optString("project_id", "");
            String idem = job.optString("idempotency_key", "");
            String raw = output == null ? "{}" : output.toString();
            String outputHash = sha256(raw);
            String actionId = "local-receipt-" + sha256(idem + "\n" + raw);
            long now = System.currentTimeMillis();

            long inserted = dao.insertReceipt(new EdgeReceiptEntity(
                    actionId, localId, projectId, idem, "COMMITTED",
                    outputHash, 0L, now
            ));
            if (!localId.isEmpty()) {
                dao.setJobState(localId, "COMMITTED", now);
                dao.deleteJob(localId);
            }
            receipt.put("result", inserted == -1L ? "ALREADY_COMMITTED" : "COMMITTED");
            receipt.put("action_id", actionId);
            receipt.put("output_hash", outputHash);
            receipt.put("executor", "B_EDGE_LOCAL_TASK_ENGINE");
            receipt.put("output", output == null ? new JSONObject() : output);
        } catch (Exception e) {
            try {
                receipt.put("result", "HOLD");
                receipt.put("error", e.getClass().getSimpleName());
            } catch (Exception ignored) {}
        }
        return receipt;
    }

    public int pendingCount() {
        return dao.countPendingJobs();
    }

    public synchronized JSONObject observePcReachability(String projectId, boolean reachable) {
        long now = System.currentTimeMillis();
        EdgeSentinelEntity old = dao.sentinel(projectId);
        long lastSuccess = old == null ? 0L : old.lastPcSuccessAt;
        int failures = old == null ? 0 : old.consecutiveFailures;
        String oldState = old == null ? "UNKNOWN" : old.state;
        String lastAlertKey = old == null ? "" : old.lastAlertKey;
        long lastAlertAt = old == null ? 0L : old.lastAlertAt;
        boolean resumePending = old != null && old.resumePending;
        String resumeRequestId = old == null ? "" : old.resumeRequestId;

        if (reachable) {
            lastSuccess = now;
            failures = 0;
            resumePending = false;
            resumeRequestId = "";
        } else {
            failures = Math.min(1000, failures + 1);
        }

        String state = EdgePolicy.sentinelState(now, lastSuccess, failures);
        boolean alertDue = EdgePolicy.sentinelAlertDue(state, now, lastAlertAt);
        if ("PC_UNAVAILABLE_RECOVERY".equals(state) && !resumePending) {
            resumePending = true;
            resumeRequestId = "edge-resume-" + sha256(projectId + "\n" + lastSuccess);
        }
        if (alertDue) {
            lastAlertKey = sha256(projectId + "\n" + state + "\n" + lastSuccess);
            lastAlertAt = now;
        }
        dao.putSentinel(new EdgeSentinelEntity(
                projectId, state, lastSuccess, now, failures,
                lastAlertKey, lastAlertAt, resumePending, resumeRequestId
        ));
        if ("PC_AVAILABLE".equals(state)) setMode("PC_AVAILABLE");
        else if ("PC_UNAVAILABLE_RECOVERY".equals(state)) setMode("PC_UNAVAILABLE_RECOVERY");
        else setMode("EDGE_ONLY");

        JSONObject out = new JSONObject();
        try {
            out.put("project_id", projectId);
            out.put("state", state);
            out.put("previous_state", oldState);
            out.put("last_pc_success_at", lastSuccess);
            out.put("last_check_at", now);
            out.put("consecutive_failures", failures);
            out.put("resume_pending", resumePending);
            out.put("resume_request_id", resumeRequestId);
            out.put("alert_due", alertDue);
            out.put("transitioned", !state.equals(oldState));
        } catch (Exception ignored) {}
        return out;
    }

    public JSONObject sentinelStatus(String projectId) {
        EdgeSentinelEntity s = dao.sentinel(projectId);
        JSONObject out = new JSONObject();
        try {
            if (s == null) {
                out.put("state", "NOT_OBSERVED");
                out.put("project_id", projectId);
                return out;
            }
            out.put("project_id", s.projectId);
            out.put("state", s.state);
            out.put("last_pc_success_at", s.lastPcSuccessAt);
            out.put("last_check_at", s.lastCheckAt);
            out.put("consecutive_failures", s.consecutiveFailures);
            out.put("last_alert_key", s.lastAlertKey);
            out.put("last_alert_at", s.lastAlertAt);
            out.put("resume_pending", s.resumePending);
            out.put("resume_request_id", s.resumeRequestId);
        } catch (Exception ignored) {}
        return out;
    }

    public int compactExpiredMemory() {
        return dao.deleteExpiredMemory(System.currentTimeMillis());
    }

    private static String sha256(String value) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] digest = md.digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder out = new StringBuilder(digest.length * 2);
            for (byte b : digest) out.append(String.format("%02x", b & 0xff));
            return out.toString();
        } catch (Exception e) {
            throw new IllegalStateException("sha256_unavailable", e);
        }
    }

    private static String jsonValueString(Object value) {
        if (value == null || value == JSONObject.NULL) return "null";
        if (value instanceof JSONObject || value instanceof JSONArray) return value.toString();
        if (value instanceof Number || value instanceof Boolean) return String.valueOf(value);
        return JSONObject.quote(String.valueOf(value));
    }
}
