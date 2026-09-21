package com.blessing.bcpedge;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;

import org.json.JSONObject;

/** Lightweight network truth for adaptive routing/data-saver decisions. */
public final class EdgeNetworkState {
    private EdgeNetworkState() {}

    public static JSONObject snapshot(Context context) {
        JSONObject out = new JSONObject();
        try {
            ConnectivityManager cm = context.getSystemService(ConnectivityManager.class);
            if (cm == null) return out.put("state", "UNAVAILABLE");
            Network network = cm.getActiveNetwork();
            NetworkCapabilities caps = network == null ? null : cm.getNetworkCapabilities(network);
            if (caps == null) {
                out.put("state", "OFFLINE");
                out.put("internet", false);
                out.put("validated", false);
                return out;
            }
            boolean wifi = caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI);
            boolean cellular = caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR);
            boolean ethernet = caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET);
            boolean vpn = caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN);
            boolean internet = caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET);
            boolean validated = caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED);
            boolean metered = cm.isActiveNetworkMetered();
            String transport = wifi ? "WIFI" : cellular ? "CELLULAR" : ethernet ? "ETHERNET" : vpn ? "VPN" : "OTHER";
            out.put("state", validated ? "ONLINE" : internet ? "UNVALIDATED" : "LOCAL_ONLY");
            out.put("transport", transport);
            out.put("internet", internet);
            out.put("validated", validated);
            out.put("metered", metered);
            out.put("local_api_available_without_internet", true);
            out.put("large_transfer_allowed_by_default", validated && !metered);
            out.put("routing_hint", validated
                    ? (metered ? "DATA_SAVER" : "NORMAL")
                    : "STORE_AND_FORWARD");
        } catch (Exception ignored) {}
        return out;
    }
}
