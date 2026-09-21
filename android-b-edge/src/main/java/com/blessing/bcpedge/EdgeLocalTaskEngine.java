package com.blessing.bcpedge;

import android.content.Context;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Small allowlisted executor for deterministic jobs that belong on the dedicated phone.
 *
 * This is intentionally NOT a shell or general code runner. It executes only bounded
 * BCP maintenance/snapshot jobs so EDGE_ONLY can make useful progress while the PC is
 * offline, expensive, rebooting or under memory pressure.
 */
public final class EdgeLocalTaskEngine {
    private EdgeLocalTaskEngine() {}

    public static boolean supports(String kind) {
        String k = normalize(kind);
        return "LOCAL_CONTEXT_SNAPSHOT".equals(k)
                || "LOCAL_HEALTH_SNAPSHOT".equals(k)
                || "LOCAL_QUEUE_SUMMARY".equals(k)
                || "LOCAL_MEMORY_COMPACT".equals(k)
                || "LOCAL_CONTENT_STORE_STATUS".equals(k)
                || "LOCAL_RECOVERY_CHECKPOINT".equals(k);
    }

    public static JSONObject execute(Context context, EdgeOrchestrator orchestrator,
                                     String projectId, String kind, JSONObject payload) {
        String k = normalize(kind);
        JSONObject out = new JSONObject();
        try {
            out.put("result", "COMMITTED");
            out.put("executor", "B_EDGE_LOCAL_TASK_ENGINE");
            out.put("kind", k);
            out.put("project_id", projectId);
            out.put("timestamp_ms", System.currentTimeMillis());

            if ("LOCAL_CONTEXT_SNAPSHOT".equals(k)) {
                out.put("mode", orchestrator.getMode());
                out.put("sentinel", orchestrator.sentinelStatus(projectId));
                out.put("pending_jobs", orchestrator.pendingJobs(projectId));
                out.put("memory", orchestrator.memorySnapshot(projectId));
                out.put("network", EdgeNetworkState.snapshot(context));
                out.put("resources", EdgeResourceGovernor.snapshot(context));
                return out;
            }
            if ("LOCAL_HEALTH_SNAPSHOT".equals(k)) {
                out.put("mode", orchestrator.getMode());
                out.put("sentinel", orchestrator.sentinelStatus(projectId));
                out.put("network", EdgeNetworkState.snapshot(context));
                out.put("resources", EdgeResourceGovernor.snapshot(context));
                out.put("pending_count", orchestrator.pendingCount());
                return out;
            }
            if ("LOCAL_QUEUE_SUMMARY".equals(k)) {
                JSONArray jobs = orchestrator.pendingJobs(projectId);
                out.put("pending_count", jobs.length());
                out.put("jobs", jobs);
                return out;
            }
            if ("LOCAL_MEMORY_COMPACT".equals(k)) {
                int removed = orchestrator.compactExpiredMemory();
                out.put("expired_entries_removed", removed);
                return out;
            }
            if ("LOCAL_CONTENT_STORE_STATUS".equals(k)) {
                out.put("content_store", new EdgeContentStore(context).status());
                return out;
            }
            if ("LOCAL_RECOVERY_CHECKPOINT".equals(k)) {
                JSONObject snapshot = new JSONObject();
                snapshot.put("project_id", projectId);
                snapshot.put("mode", orchestrator.getMode());
                snapshot.put("sentinel", orchestrator.sentinelStatus(projectId));
                snapshot.put("pending_jobs", orchestrator.pendingJobs(projectId));
                snapshot.put("memory", orchestrator.memorySnapshot(projectId));
                snapshot.put("network", EdgeNetworkState.snapshot(context));
                snapshot.put("resources", EdgeResourceGovernor.snapshot(context));
                snapshot.put("created_at_ms", System.currentTimeMillis());
                JSONObject stored = new EdgeContentStore(context).putJson(
                        "recovery", projectId + "-latest", snapshot);
                out.put("snapshot", snapshot);
                out.put("stored", stored);
                if (!stored.optBoolean("stored", false)) {
                    out.put("result", "HOLD");
                    out.put("error", "RECOVERY_CHECKPOINT_PERSIST_FAILED");
                }
                return out;
            }

            out.put("result", "HOLD");
            out.put("error", "UNSUPPORTED_LOCAL_TASK");
        } catch (Exception e) {
            try {
                out.put("result", "HOLD");
                out.put("error", e.getClass().getSimpleName());
            } catch (Exception ignored) {}
        }
        return out;
    }

    private static String normalize(String kind) {
        return kind == null ? "" : kind.trim().toUpperCase();
    }
}
