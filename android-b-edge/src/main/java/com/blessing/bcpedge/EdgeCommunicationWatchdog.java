package com.blessing.bcpedge;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONObject;

/**
 * Phone-owned communication liveness. This runs inside the foreground node service,
 * so compact Telegram state changes do not depend on the Windows Telegram worker.
 */
public final class EdgeCommunicationWatchdog {
    private static final String PREFS = "bcp_edge_comm_watchdog";
    private static final long STARTUP_NOTICE_MIN_MS = 6L * 60L * 60L * 1000L;
    private static final long ALIVE_NOTICE_MS = 90L * 60L * 1000L;

    private final Context context;
    private final SharedPreferences prefs;

    public EdgeCommunicationWatchdog(Context context) {
        this.context = context.getApplicationContext();
        this.prefs = this.context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public synchronized JSONObject tick(BcpClient client, boolean pcReachable) {
        JSONObject out = new JSONObject();
        try {
            JSONObject network = EdgeConnectivity.snapshot(context);
            EdgeTelegramSender telegram = new EdgeTelegramSender(context);
            long now = System.currentTimeMillis();

            String pcState = pcReachable ? "REACHABLE" : "UNREACHABLE";
            String previousPc = prefs.getString("pc_state", "UNKNOWN");
            String networkState = network.optBoolean("validated_internet", false)
                    ? "ONLINE_" + network.optString("transport", "OTHER")
                    : network.optBoolean("connected", false) ? "LOCAL_ONLY" : "OFFLINE";
            String previousNetwork = prefs.getString("network_state", "UNKNOWN");

            boolean telegramReady = telegram.configured()
                    && network.optBoolean("validated_internet", false);
            String noticeKind = "";
            String message = "";

            long lastStartup = prefs.getLong("last_startup_notice_at", 0L);
            long lastAlive = prefs.getLong("last_alive_notice_at", 0L);

            if (telegramReady && (lastStartup == 0L || now - lastStartup >= STARTUP_NOTICE_MIN_MS)) {
                noticeKind = "PHONE_NODE_ONLINE";
                message = "🟢 B-EDGE actif · téléphone serveur opérationnel · PC "
                        + (pcReachable ? "joignable" : "hors ligne")
                        + " · réseau " + network.optString("transport", "inconnu");
            } else if (telegramReady && !"UNKNOWN".equals(previousPc) && !previousPc.equals(pcState)) {
                noticeKind = pcReachable ? "PC_RECONNECTED" : "PC_UNREACHABLE";
                message = pcReachable
                        ? "🟢 BCP : PC retrouvé par le téléphone serveur. File locale en reprise."
                        : "🟠 BCP : PC non joignable. Le téléphone serveur reste actif et conserve la file.";
            } else if (telegramReady && !"UNKNOWN".equals(previousNetwork)
                    && !previousNetwork.equals(networkState)
                    && network.optBoolean("validated_internet", false)) {
                noticeKind = "PHONE_UPLINK_RECOVERED";
                message = "🟢 B-EDGE : accès Internet revenu sur le téléphone serveur · "
                        + network.optString("transport", "réseau") + ".";
            } else if (telegramReady && (lastAlive == 0L || now - lastAlive >= ALIVE_NOTICE_MS)) {
                noticeKind = "PHONE_NODE_ALIVE";
                message = "🟢 B-EDGE vivant · PC " + (pcReachable ? "joignable" : "hors ligne")
                        + " · file locale conservée · "
                        + network.optString("transport", "réseau");
            }

            long messageId = 0L;
            if (!message.isEmpty()) {
                JSONObject receipt = telegram.sendText(message);
                messageId = receipt.optLong("message_id", 0L);
                SharedPreferences.Editor e = prefs.edit()
                        .putString("last_notice_kind", noticeKind)
                        .putLong("last_notice_message_id", messageId)
                        .putLong("last_notice_at", now);
                if ("PHONE_NODE_ONLINE".equals(noticeKind)) e.putLong("last_startup_notice_at", now);
                if ("PHONE_NODE_ALIVE".equals(noticeKind)) e.putLong("last_alive_notice_at", now);
                e.apply();
                client.recordEvent("EDGE_COMM_NOTICE_SENT", noticeKind + ":" + messageId);
            }

            prefs.edit()
                    .putString("pc_state", pcState)
                    .putString("network_state", networkState)
                    .putLong("last_tick_at", now)
                    .apply();

            out.put("ok", true);
            out.put("pc_state", pcState);
            out.put("network_state", networkState);
            out.put("telegram_ready", telegramReady);
            out.put("notice_kind", noticeKind);
            out.put("message_id", messageId);
        } catch (Exception ex) {
            try {
                out.put("ok", false);
                out.put("error_class", ex.getClass().getSimpleName());
            } catch (Exception ignored) {}
            client.recordEvent("EDGE_COMM_WATCHDOG_DEFERRED", ex.getClass().getSimpleName());
        }
        return out;
    }

    public JSONObject status() {
        JSONObject out = new JSONObject();
        try {
            out.put("last_tick_at", prefs.getLong("last_tick_at", 0L));
            out.put("pc_state", prefs.getString("pc_state", "UNKNOWN"));
            out.put("network_state", prefs.getString("network_state", "UNKNOWN"));
            out.put("last_notice_kind", prefs.getString("last_notice_kind", ""));
            out.put("last_notice_at", prefs.getLong("last_notice_at", 0L));
            out.put("last_notice_message_id", prefs.getLong("last_notice_message_id", 0L));
        } catch (Exception ignored) {}
        return out;
    }
}
