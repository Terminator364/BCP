package com.blessing.bcpedge;

import android.content.Context;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public final class EdgeTelegramSender {
    private final Context context;
    private final TelegramCredentialStore credentials;

    public EdgeTelegramSender(Context context) {
        this.context = context.getApplicationContext();
        this.credentials = new TelegramCredentialStore(this.context);
    }

    public boolean configured() {
        return credentials.configured();
    }

    public JSONObject bootstrapFromPairedPc(BcpClient client) {
        JSONObject out = new JSONObject();
        try {
            JSONObject r = client.telegramEdgeBootstrap();
            String token = r.optString("token", "");
            long chatId = r.optLong("allowed_chat_id", 0L);
            credentials.put(token, chatId);
            out.put("ok", true);
            out.put("configured", true);
            out.put("chat_id_present", true);
            out.put("credential_storage", "ANDROID_KEYSTORE_AES_GCM");
            return out;
        } catch (Exception ex) {
            try {
                out.put("ok", false);
                out.put("configured", credentials.configured());
                out.put("error_class", ex.getClass().getSimpleName());
            } catch (Exception ignored) {}
            return out;
        }
    }

    public JSONObject sendText(String text) throws Exception {
        String token = credentials.getToken();
        long chatId = credentials.getChatId();
        if (token.isEmpty() || chatId == 0L) throw new IllegalStateException("EDGE_TELEGRAM_NOT_CONFIGURED");

        JSONObject payload = new JSONObject();
        payload.put("chat_id", chatId);
        payload.put("text", text == null ? "" : text.substring(0, Math.min(3900, text.length())));
        payload.put("disable_web_page_preview", true);

        URL url = new URL("https://api.telegram.org/bot" + token + "/sendMessage");
        HttpURLConnection c = (HttpURLConnection) url.openConnection();
        c.setRequestMethod("POST");
        c.setConnectTimeout(7000);
        c.setReadTimeout(15000);
        c.setDoOutput(true);
        c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        c.setRequestProperty("Accept", "application/json");
        byte[] body = payload.toString().getBytes(StandardCharsets.UTF_8);
        try (OutputStream os = c.getOutputStream()) {
            os.write(body);
        }
        int code = c.getResponseCode();
        InputStream in = code >= 400 ? c.getErrorStream() : c.getInputStream();
        String raw = readAll(in);
        if (code != 200) throw new IllegalStateException("EDGE_TELEGRAM_HTTP_" + code);
        JSONObject obj = raw.isEmpty() ? new JSONObject() : new JSONObject(raw);
        if (!obj.optBoolean("ok", false)) throw new IllegalStateException("EDGE_TELEGRAM_API_REJECTED");
        JSONObject result = obj.optJSONObject("result");
        JSONObject out = new JSONObject();
        out.put("ok", true);
        out.put("message_id", result == null ? 0 : result.optLong("message_id", 0L));
        return out;
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
