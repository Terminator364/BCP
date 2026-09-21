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
                || "LOCAL_COMMUNICATION_RECORD".equals(k);
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
            if ("LOCAL_COMMUNICATION_RECORD".equals(k)) {
                String recordId = payload.optString("idempotency_key",
                        payload.optString("record_id", "")).trim();
                if (recordId.isEmpty() || recordId.length() > 160) {
                    out.put("result", "HOLD");
                    out.put("error", "COMMUNICATION_ID_REQUIRED");
                    return out;
                }
                JSONObject record = new JSONObject();
                record.put("record_id", recordId);
                record.put("channel", bounded(payload.optString("channel", "BCP"), 40));
                record.put("direction", bounded(payload.optString("direction", "LOCAL"), 24));
                record.put("kind", bounded(payload.optString("kind", "CHECKPOINT"), 48));
                record.put("state", bounded(payload.optString("state", "STAGED"), 40));
                record.put("text", bounded(payload.optString("text", ""), 8192));
                record.put("source_node", bounded(payload.optString("source_node", "B-EDGE"), 64));
                record.put("created_at_ms", payload.optLong("created_at_ms", System.currentTimeMillis()));
                record.put("stored_at_ms", System.currentTimeMillis());
                long expiresAt = System.currentTimeMillis() + 14L * 24L * 60L * 60L * 1000L;
                orchestrator.putMemory(projectId, "HISTORY", "comm:" + recordId,
                        record, "MACHINE_READBACK", false, expiresAt);
                out.put("record_id", recordId);
                out.put("communication_record", record);
                out.put("journal", "B_EDGE_DURABLE_COMMUNICATION_HISTORY");
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

    private static String bounded(String value, int max) {
        String v = value == null ? "" : value;
        return v.length() <= max ? v : v.substring(0, max);
    }

    private static String normalize(String kind) {
        return kind == null ? "" : kind.trim().toUpperCase();
    }
}
