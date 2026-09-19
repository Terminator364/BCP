package com.blessing.bcpedge;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

public final class TelegramBotClient {
    private final String token;

    public TelegramBotClient(String token) {
        String t = token == null ? "" : token.trim();
        if (t.length() < 20 || !t.contains(":")) throw new IllegalArgumentException("INVALID_BOT_TOKEN");
        this.token = t;
    }

    public JSONObject getMe() throws Exception {
        return call("GET", "getMe", null, 5000, 7000);
    }

    public JSONArray getUpdates(long offset, int timeoutSeconds) throws Exception {
        int bounded = Math.max(0, Math.min(40, timeoutSeconds));
        String query = "?offset=" + Math.max(0L, offset) +
                "&timeout=" + bounded +
                "&allowed_updates=" + URLEncoder.encode("[\"message\"]", "UTF-8");
        JSONObject response = call("GET", "getUpdates" + query, null,
                6000, (bounded + 8) * 1000);
        JSONArray result = response.optJSONArray("result");
        return result == null ? new JSONArray() : result;
    }

    public void sendText(long chatId, String text) throws Exception {
        JSONObject body = new JSONObject();
        body.put("chat_id", chatId);
        body.put("text", TelegramObservabilityPolicy.clipForTelegram(text));
        body.put("disable_web_page_preview", true);
        call("POST", "sendMessage", body, 5000, 8000);
    }

    private JSONObject call(String method, String endpoint, JSONObject body,
                            int connectMs, int readMs) throws Exception {
        URL url = new URL("https://api.telegram.org/bot" + token + "/" + endpoint);
        HttpURLConnection c = (HttpURLConnection) url.openConnection();
        c.setRequestMethod(method);
        c.setConnectTimeout(connectMs);
        c.setReadTimeout(readMs);
        c.setRequestProperty("Accept", "application/json");
        c.setRequestProperty("User-Agent", "BCP-Edge-Telegram-Observability/1");
        if (body != null) {
            c.setDoOutput(true);
            c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            try (OutputStream os = c.getOutputStream()) {
                os.write(body.toString().getBytes(StandardCharsets.UTF_8));
            }
        }
        int code = c.getResponseCode();
        InputStream in = code >= 400 ? c.getErrorStream() : c.getInputStream();
        String raw = readAll(in);
        if (code >= 400) throw new IOException("TELEGRAM_HTTP_" + code);
        JSONObject out = raw.isEmpty() ? new JSONObject() : new JSONObject(raw);
        if (!out.optBoolean("ok", false)) throw new IOException("TELEGRAM_API_REJECTED");
        return out;
    }

    private static String readAll(InputStream in) throws IOException {
        if (in == null) return "";
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buf = new byte[4096];
        int n;
        while ((n = in.read(buf)) >= 0) out.write(buf, 0, n);
        return out.toString("UTF-8");
    }
}
