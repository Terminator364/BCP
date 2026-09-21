package com.blessing.bcpedge;

import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Truthful adaptive route planner for the dedicated B-EDGE appliance.
 *
 * This class does not claim remote delivery. It only reports locally observable
 * network facts and the preferred next transport according to BCP policy.
 */
public final class EdgeRouteManager {
    private static final String RELAY_PREFS = "bcp_edge_relay_state";

    private EdgeRouteManager() {}

    public static JSONObject snapshot(Context context) {
        JSONObject out = new JSONObject();
        try {
            JSONObject net = EdgeNetworkState.snapshot(context);
            SharedPreferences bcp = context.getSharedPreferences("bcp", Context.MODE_PRIVATE);
            SharedPreferences relay = context.getSharedPreferences(RELAY_PREFS, Context.MODE_PRIVATE);

            String server = bcp.getString("server", "");
            boolean paired = !new CredentialStore(context).getToken().isEmpty();
            String listener = relay.getString("state", "UNKNOWN");
            boolean localApiListening = "LISTENING".equals(listener)
                    || "TUNNEL_OPEN".equals(listener)
                    || "TUNNEL_CLOSED".equals(listener);
            boolean validated = net.optBoolean("validated", false);
            boolean metered = net.optBoolean("metered", false);
            String transport = net.optString("transport", "NONE");
            boolean localNetwork = "WIFI".equals(transport)
                    || "ETHERNET".equals(transport)
                    || "VPN".equals(transport);

            String preferred;
            String reason;
            if (paired && localNetwork && !server.isEmpty()) {
                preferred = "PC_LOCAL_LAN";
                reason = "paired_pc_and_local_network_available";
            } else if (localApiListening && localNetwork) {
                preferred = "PHONE_LOCAL_API";
                reason = "phone_local_api_available_on_local_network";
            } else if (validated && !metered) {
                preferred = "PHONE_OUTBOUND_INTERNET";
                reason = "validated_unmetered_uplink";
            } else if (validated) {
                preferred = "PHONE_OUTBOUND_DATA_SAVER";
                reason = "validated_metered_uplink";
            } else {
                preferred = "STORE_AND_FORWARD";
                reason = "no_validated_uplink";
            }

            JSONArray fallback = new JSONArray();
            fallback.put("NSD_LAN");
            fallback.put("WIFI_DIRECT_WHEN_AUTHORIZED");
            fallback.put("BLE_PRESENCE_CONTROL");
            fallback.put("USB_MAINTENANCE_FUTURE_FIELD_GATED");

            out.put("preferred_route", preferred);
            out.put("reason", reason);
            out.put("network", net);
            out.put("paired", paired);
            out.put("pc_endpoint_configured", !server.isEmpty());
            out.put("local_api_listening", localApiListening);
            out.put("internet_validated", validated);
            out.put("metered", metered);
            out.put("data_saver", metered);
            out.put("fallback_order", fallback);
            out.put("no_uplink_behavior", "DURABLE_STORE_AND_FORWARD");
            out.put("remote_delivery_claimed", false);
            out.put("timestamp_ms", System.currentTimeMillis());
        } catch (Exception ignored) {}
        return out;
    }
}
