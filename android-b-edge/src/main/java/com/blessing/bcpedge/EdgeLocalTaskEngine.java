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
                || "LOCAL_CAPABILITY_SNAPSHOT".equals(k)
                || "LOCAL_MEMORY_COMPACT".equals(k);
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
            if ("LOCAL_CAPABILITY_SNAPSHOT".equals(k)) {
                BcpClient client = new BcpClient(context);
                JSONObject refreshed = client.refreshBuiltinCapabilities();
                out.put("capabilities", refreshed.optJSONObject("registry"));
                out.put("refreshed", refreshed.optInt("refreshed", 0));
                out.put("offline_capable", true);
                return out;
            }
            if ("LOCAL_MEMORY_COMPACT".equals(k)) {
                int removed = orchestrator.compactExpiredMemory();
                out.put("expired_entries_removed", removed);
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
