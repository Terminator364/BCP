package com.blessing.bcpedge;

import android.content.Context;
import android.content.SharedPreferences;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * Outbound-only Telegram relay for compact BCP control messages.
 *
 * The PC remains canonical. B-EDGE pulls already-persisted notifications over
 * the authenticated local channel, then tries the cheapest healthy phone
 * network. Telegram credentials are kept in Android Keystore-backed storage.
 */
public final class EdgeTelegramRelay {
    private static final String PREFS = "bcp_edge_relay";
    private static final String TELEGRAM_SECRET = "telegram_bot_token";
    private static final int CONNECT_TIMEOUT_MS = 3500;
    private static final int READ_TIMEOUT_MS = 7000;

    private final Context context;
    private final CredentialStore credentials;
    private final SharedPreferences prefs;

    public EdgeTelegramRelay(Context context) {
        this.context = context.getApplicationContext();
        this.credentials = new CredentialStore(this.context);
        this.prefs = this.context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public boolean applyConfig(JSONObject cfg) {
        try {
            if (cfg == null || !cfg.optBoolean("configured", false)) return false;
            String token = cfg.optString("telegram_bot_token", "");
            long chatId = cfg.optLong("allowed_chat_id", 0L);
            if (token.isEmpty() || chatId == 0L) return false;
            credentials.putSecret(TELEGRAM_SECRET, token);
            prefs.edit()
                    .putLong("allowed_chat_id", chatId)
                    .putBoolean("cellular_control_allowed",
                            cfg.optBoolean("cellular_control_allowed", false))
                    .putInt("max_cellular_payload_bytes",
                            Math.min(AdaptiveNetworkRouter.MAX_CELLULAR_CONTROL_BYTES,
                                    Math.max(512, cfg.optInt(
                                            "max_cellular_payload_bytes",
                                            AdaptiveNetworkRouter.MAX_CELLULAR_CONTROL_BYTES))))
                    .putLong("config_updated_at", System.currentTimeMillis())
                    .commit();
            return true;
        } catch (Exception ignored) {
            return false;
        }
    }

    public JSONObject deliver(JSONObject item) {
        JSONObject out = new JSONObject();
        try {
            String deliveryId = item.optString("delivery_id", "");
            JSONObject prior = localReceipt(deliveryId);
            if (prior != null) {
                prior.put("delivered", true);
                prior.put("recovered_local_receipt", true);
                return prior;
            }

            String token = credentials.getSecret(TELEGRAM_SECRET);
            long chatId = prefs.getLong("allowed_chat_id", 0L);
            if (token.isEmpty() || chatId == 0L) {
                out.put("delivered", false);
                out.put("state", "RELAY_NOT_CONFIGURED");
                return out;
            }

            String payloadClass = item.optString("payload_class", "").trim().toUpperCase();
            JSONObject payload = item.optJSONObject("payload");
            if (payload == null) throw new IllegalArgumentException("relay_payload_missing");
            String text = payload.optString("text", "");
            if (text.isEmpty()) throw new IllegalArgumentException("relay_text_missing");
            boolean silent = payload.optBoolean("silent", false);
            byte[] payloadBytes = payload.toString().getBytes(StandardCharsets.UTF_8);
            boolean cellularAllowed = prefs.getBoolean("cellular_control_allowed", false)
                    && AdaptiveNetworkRouter.isCellularEligiblePayload(
                            payloadClass, payloadBytes.length);

            ConnectivityManager cm = (ConnectivityManager)
                    context.getSystemService(Context.CONNECTIVITY_SERVICE);
            if (cm == null) throw new IllegalStateException("connectivity_manager_missing");

            Exception last = null;
            // Free Wi-Fi path first.
            for (Network network : cm.getAllNetworks()) {
                NetworkCapabilities caps = cm.getNetworkCapabilities(network);
                if (!validated(caps) || !caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) continue;
                try {
                    long messageId = sendOnNetwork(network, token, chatId, text, silent);
                    JSONObject sent = success(AdaptiveNetworkRouter.WIFI_TELEGRAM, messageId);
                    persistLocalReceipt(deliveryId, sent);
                    return sent;
                } catch (Exception ex) {
                    last = ex;
                }
            }

            // Metered path is allowed only for tiny control classes.
            if (cellularAllowed) {
                for (Network network : cm.getAllNetworks()) {
                    NetworkCapabilities caps = cm.getNetworkCapabilities(network);
                    if (!validated(caps) || !caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) continue;
                    try {
                        long messageId = sendOnNetwork(network, token, chatId, text, silent);
                        JSONObject sent = success(AdaptiveNetworkRouter.CELLULAR_TELEGRAM, messageId);
                        persistLocalReceipt(deliveryId, sent);
                        return sent;
                    } catch (Exception ex) {
                        last = ex;
                    }
                }
            }

            out.put("delivered", false);
            out.put("state", AdaptiveNetworkRouter.LOCAL_OUTBOX);
            out.put("error_class", last == null ? "NO_ELIGIBLE_REMOTE_NETWORK"
                    : last.getClass().getSimpleName());
        } catch (Exception ex) {
            try {
                out.put("delivered", false);
                out.put("state", AdaptiveNetworkRouter.LOCAL_OUTBOX);
                out.put("error_class", ex.getClass().getSimpleName());
            } catch (Exception ignored) {}
        }
        return out;
    }

    private String receiptKey(String deliveryId) {
        return "delivery_receipt." + (deliveryId == null ? "" : deliveryId);
    }

    private JSONObject localReceipt(String deliveryId) {
        if (deliveryId == null || deliveryId.isEmpty()) return null;
        String raw = prefs.getString(receiptKey(deliveryId), "");
        if (raw == null || raw.isEmpty()) return null;
        try { return new JSONObject(raw); }
        catch (Exception ignored) { return null; }
    }

    private void persistLocalReceipt(String deliveryId, JSONObject sent) {
        if (deliveryId == null || deliveryId.isEmpty() || sent == null) return;
        prefs.edit().putString(receiptKey(deliveryId), sent.toString()).commit();
    }

    public void confirmPcAck(String deliveryId) {
        if (deliveryId == null || deliveryId.isEmpty()) return;
        prefs.edit().remove(receiptKey(deliveryId)).commit();
    }

    private static boolean validated(NetworkCapabilities caps) {
        return caps != null
                && caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                && caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED);
    }

    private static JSONObject success(String route, long messageId) throws Exception {
        JSONObject out = new JSONObject();
        out.put("delivered", true);
        out.put("route", route);
        out.put("provider_message_id", messageId > 0L ? String.valueOf(messageId) : "");
        return out;
    }

    private long sendOnNetwork(Network network, String token, long chatId,
                               String text, boolean silent) throws Exception {
        URL url = new URL("https://api.telegram.org/bot" + token + "/sendMessage");
        HttpURLConnection c = (HttpURLConnection) network.openConnection(url);
        c.setRequestMethod("POST");
        c.setConnectTimeout(CONNECT_TIMEOUT_MS);
        c.setReadTimeout(READ_TIMEOUT_MS);
        c.setDoOutput(true);
        c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        c.setRequestProperty("Accept", "application/json");

        JSONObject body = new JSONObject();
        body.put("chat_id", chatId);
        body.put("text", text.length() > 3900 ? text.substring(0, 3900) : text);
        body.put("disable_web_page_preview", true);
        body.put("disable_notification", silent);
        byte[] bytes = body.toString().getBytes(StandardCharsets.UTF_8);
        try (OutputStream os = c.getOutputStream()) {
            os.write(bytes);
        }

        int code = c.getResponseCode();
        InputStream in = code >= 400 ? c.getErrorStream() : c.getInputStream();
        String raw = readAll(in);
        if (code != 200) throw new IllegalStateException("telegram_http_" + code);
        JSONObject obj = new JSONObject(raw);
        if (!obj.optBoolean("ok", false)) throw new IllegalStateException("telegram_api_rejected");
        JSONObject result = obj.optJSONObject("result");
        return result == null ? 0L : result.optLong("message_id", 0L);
    }

    private static String readAll(InputStream in) throws Exception {
        if (in == null) return "";
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buf = new byte[4096];
        int n;
        while ((n = in.read(buf)) >= 0) out.write(buf, 0, n);
        return out.toString("UTF-8");
    }
}
