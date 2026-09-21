package com.blessing.bcpedge;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;

import org.json.JSONObject;

public final class EdgeConnectivity {
    private EdgeConnectivity() {}

    public static JSONObject snapshot(Context context) {
        JSONObject out = new JSONObject();
        try {
            ConnectivityManager cm = context.getSystemService(ConnectivityManager.class);
            Network n = cm == null ? null : cm.getActiveNetwork();
            NetworkCapabilities c = (cm == null || n == null) ? null : cm.getNetworkCapabilities(n);

            boolean connected = c != null;
            boolean internet = connected && c.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET);
            boolean validated = connected && c.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED);
            boolean wifi = connected && c.hasTransport(NetworkCapabilities.TRANSPORT_WIFI);
            boolean cellular = connected && c.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR);
            boolean ethernet = connected && c.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET);
            boolean vpn = connected && c.hasTransport(NetworkCapabilities.TRANSPORT_VPN);
            boolean metered = cm != null && cm.isActiveNetworkMetered();

            String transport = wifi ? "WIFI"
                    : ethernet ? "ETHERNET"
                    : cellular ? "CELLULAR"
                    : vpn ? "VPN"
                    : connected ? "OTHER"
                    : "NONE";
            String uplink = validated ? "INTERNET_READY"
                    : connected ? "LOCAL_ONLY_OR_UNVALIDATED"
                    : "OFFLINE";

            out.put("connected", connected);
            out.put("internet_capability", internet);
            out.put("validated_internet", validated);
            out.put("metered", metered);
            out.put("transport", transport);
            out.put("uplink_state", uplink);
            out.put("local_server_ready_without_internet", true);
        } catch (Exception ignored) {}
        return out;
    }
}
