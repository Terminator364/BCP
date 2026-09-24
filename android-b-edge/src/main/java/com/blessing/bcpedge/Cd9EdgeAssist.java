package com.blessing.bcpedge;

import android.content.Context;

import org.json.JSONObject;

/**
 * Truthful CD9 assist projection for the dedicated old phone.
 *
 * This node is opportunistic: Drive/cloud remains the durable authority and
 * ChatGPT Delivery must continue when this phone, Wi-Fi or the PC disappears.
 */
public final class Cd9EdgeAssist {
    public static final long LOGICAL_OBJECT_TARGET_BYTES = 2_000_000_000L;
    public static final long CHATGPT_SEGMENT_TARGET_BYTES = 500_000_000L;

    private Cd9EdgeAssist() {}

    public static JSONObject status(Context context) {
        JSONObject out = new JSONObject();
        try {
            JSONObject storage = new EdgeContentStore(context).status();
            JSONObject network = EdgeNetworkState.snapshot(context);
            JSONObject permissions = EdgePermissionManager.status(context);
            String transport = network.optString("transport", "AUCUN");
            boolean online = !transport.isEmpty()
                    && !"AUCUN".equalsIgnoreCase(transport)
                    && !"NONE".equalsIgnoreCase(transport);
            boolean server = EdgePermissionManager.isServerModeEnabled(context);
            boolean battery = permissions.optBoolean("battery_unrestricted", false);
            long quota = storage.optLong("quota_bytes", 0L);
            long free = storage.optLong("free_device_bytes", 0L);
            boolean cacheHeadroom = quota >= 512L * 1024L * 1024L && free >= 768L * 1024L * 1024L;

            out.put("ok", true);
            out.put("role", "OPPORTUNISTIC_EDGE_CACHE_RELAY_STORE_FORWARD");
            out.put("authority", "CLOUD_DRIVE_PRIMARY");
            out.put("required_for_correctness", false);
            out.put("phone_required", false);
            out.put("pc_required", false);
            out.put("server_mode", server);
            out.put("battery_unrestricted", battery);
            out.put("network_transport", transport);
            out.put("network_online", online);
            out.put("store_and_forward", true);
            out.put("cache_headroom", cacheHeadroom);
            out.put("cache_quota_bytes", quota);
            out.put("device_free_bytes", free);
            out.put("logical_object_target_bytes", LOGICAL_OBJECT_TARGET_BYTES);
            out.put("chatgpt_segment_target_bytes", CHATGPT_SEGMENT_TARGET_BYTES);
            out.put("native_large_bot_api", false);
            out.put("telegram_https_connect_relay", true);
            out.put("slow_network_policy", "RESUME_FROM_CHECKPOINT_NO_FULL_RESTART");
            out.put("metered_policy", "NO_BULK_BY_DEFAULT");
            out.put("route", online && server && cacheHeadroom
                    ? "EDGE_ASSIST_READY"
                    : "CLOUD_PRIMARY_EDGE_DEGRADED");
        } catch (Exception e) {
            try {
                out.put("ok", false);
                out.put("route", "CLOUD_PRIMARY_EDGE_UNAVAILABLE");
                out.put("error", e.getClass().getSimpleName());
            } catch (Exception ignored) {}
        }
        return out;
    }
}
