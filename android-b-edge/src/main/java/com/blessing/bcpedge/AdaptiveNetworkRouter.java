package com.blessing.bcpedge;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;

/**
 * R63 route classifier for compact control-plane traffic.
 *
 * This class never transfers bulk payloads. It only classifies which tiny
 * communication lane is eligible; actual delivery must still persist first,
 * use idempotency keys, and require a positive acknowledgement.
 */
public final class AdaptiveNetworkRouter {
    public static final int MAX_CELLULAR_CONTROL_BYTES = 16 * 1024;

    public static final String LOCAL_OUTBOX = "LOCAL_DURABLE_OUTBOX";
    public static final String WIFI_TELEGRAM = "BEDGE_DIRECT_TELEGRAM_WIFI";
    public static final String CELLULAR_TELEGRAM = "BEDGE_DIRECT_TELEGRAM_CELLULAR";
    public static final String WIFI_NEXUS = "NEXUS_WIFI";
    public static final String CELLULAR_NEXUS = "NEXUS_CELLULAR";

    private AdaptiveNetworkRouter() {}

    public static final class Snapshot {
        public final boolean wifiValidated;
        public final boolean cellularValidated;
        public final boolean activeMetered;
        public final boolean anyValidatedInternet;

        public Snapshot(boolean wifiValidated, boolean cellularValidated,
                        boolean activeMetered, boolean anyValidatedInternet) {
            this.wifiValidated = wifiValidated;
            this.cellularValidated = cellularValidated;
            this.activeMetered = activeMetered;
            this.anyValidatedInternet = anyValidatedInternet;
        }
    }

    public static Snapshot snapshot(Context context) {
        ConnectivityManager cm = (ConnectivityManager)
                context.getSystemService(Context.CONNECTIVITY_SERVICE);
        if (cm == null) return new Snapshot(false, false, false, false);

        boolean wifi = false;
        boolean cellular = false;
        boolean validated = false;
        try {
            for (Network network : cm.getAllNetworks()) {
                NetworkCapabilities caps = cm.getNetworkCapabilities(network);
                if (caps == null) continue;
                boolean internet = caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET);
                boolean ok = internet && caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED);
                if (!ok) continue;
                validated = true;
                if (caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) wifi = true;
                if (caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) cellular = true;
            }
        } catch (Exception ignored) {}

        boolean metered = false;
        try { metered = cm.isActiveNetworkMetered(); } catch (Exception ignored) {}
        return new Snapshot(wifi, cellular, metered, validated);
    }

    public static String chooseControlRoute(
            Snapshot s,
            boolean directTelegramHealthy,
            boolean nexusHealthy,
            boolean cellularAllowed,
            int payloadBytes) {
        if (s == null || payloadBytes < 0) return LOCAL_OUTBOX;

        // Free/unmetered remote egress first.
        if (s.wifiValidated && directTelegramHealthy) return WIFI_TELEGRAM;
        if (s.wifiValidated && nexusHealthy) return WIFI_NEXUS;

        // Cellular is allowed only for tiny control traffic.
        boolean tiny = payloadBytes <= MAX_CELLULAR_CONTROL_BYTES;
        if (cellularAllowed && tiny && s.cellularValidated && directTelegramHealthy) {
            return CELLULAR_TELEGRAM;
        }
        if (cellularAllowed && tiny && s.cellularValidated && nexusHealthy) {
            return CELLULAR_NEXUS;
        }
        return LOCAL_OUTBOX;
    }

    public static boolean isCellularEligiblePayload(String payloadClass, int payloadBytes) {
        if (payloadBytes < 0 || payloadBytes > MAX_CELLULAR_CONTROL_BYTES) return false;
        String p = payloadClass == null ? "" : payloadClass.trim().toUpperCase();
        return p.equals("ALERT")
                || p.equals("CHECKPOINT_POINTER")
                || p.equals("MISSION_STATE")
                || p.equals("ACK")
                || p.equals("COMMAND_RECEIPT");
    }
}
