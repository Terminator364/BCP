package com.blessing.bcpedge;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Build;
import org.json.JSONArray;
import org.json.JSONObject;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;

public final class BcpClient {
    public interface Progress { void onStage(String stage, String detail); }

    private static final String PREFS = "bcp";
    private static final String PROJECT = "buildhub";
    private static final String EDGE_VERSION = "0.2.2";
    private final Context context;
    private final SharedPreferences prefs;
    private final TelemetryStore telemetry;

    public BcpClient(Context context) {
        this.context = context.getApplicationContext();
        this.prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        this.telemetry = new TelemetryStore(context);
    }

    public String getServer() { return prefs.getString("server", ""); }
    public String getToken() { return prefs.getString("token", ""); }
    public String getProject() { return PROJECT; }

    public JSONObject connectAutomatically(Progress progress) throws Exception {
        progress.onStage("START", "BCP Edge démarre");
        telemetry.add("START", null);

        String savedServer = getServer();
        String savedToken = getToken();
        if (!savedServer.isEmpty()) {
            progress.onStage("RECONNECT", "Vérification du PC déjà appairé");
            telemetry.add("RECONNECT_TRY", savedServer);
            try {
                JSONObject h = requestJson("GET", savedServer + "/health", null, null, null, 1200, 1500);
                if (h.optBoolean("ok")) {
                    progress.onStage("CONNECTED", "PC retrouvé automatiquement");
                    telemetry.add("RECONNECT_PASS", savedServer);
                    heartbeat("RECONNECT_PASS");
                    return h;
                }
            } catch (Exception ignored) {
                telemetry.add("RECONNECT_FAIL", savedServer);
            }
        }

        progress.onStage("DISCOVERY", "Recherche automatique du PC sur le Wi-Fi");
        telemetry.add("DISCOVERY_START", null);
        String server = discoverLan(progress);
        if (server == null) {
            telemetry.add("PC_NOT_FOUND", null);
            throw new IOException("PC_NOT_FOUND");
        }

        progress.onStage("PC_FOUND", server);
        telemetry.add("PC_DISCOVERED", server);

        JSONObject pairBody = new JSONObject();
        pairBody.put("device_name", Build.MANUFACTURER + " " + Build.MODEL);
        pairBody.put("edge_version", EDGE_VERSION);
        pairBody.put("project", PROJECT);

        progress.onStage("PAIRING", "Appairage sécurisé local");
        telemetry.add("PAIRING_STARTED", server);
        JSONObject pair = requestJson("POST", server + "/pair", pairBody.toString(),
                null, null, 2000, 3000);

        String token = pair.optString("token", "");
        if (token.isEmpty()) {
            telemetry.add("PAIRING_FAIL", pair.toString());
            throw new IOException("PAIRING_FAILED");
        }

        prefs.edit().putString("server", server).putString("token", token).apply();
        telemetry.add("PAIRING_PASS", server);
        progress.onStage("CONNECTED", "Appairé à " + pair.optString("pc_name", "BCP PC"));
        heartbeat("PAIRING_PASS");
        return publicPairStatus(pair);
    }

    private String discoverLan(Progress progress) throws Exception {
        String ip = localIpv4();
        if (ip == null) throw new IOException("NO_LAN_IPV4");
        String[] p = ip.split("\\.");
        if (p.length != 4) throw new IOException("UNSUPPORTED_SUBNET");
        String prefix = p[0] + "." + p[1] + "." + p[2] + ".";

        ExecutorService pool = Executors.newFixedThreadPool(32);
        CompletionService<String> cs = new ExecutorCompletionService<>(pool);
        List<Future<String>> futures = new ArrayList<>();
        for (int i = 1; i <= 254; i++) {
            final String host = prefix + i;
            if (host.equals(ip)) continue;
            futures.add(cs.submit(() -> {
                String base = "http://" + host + ":8765";
                try {
                    JSONObject h = requestJson("GET", base + "/health", null,
                            null, null, 280, 450);
                    if (h.optBoolean("ok") && h.optString("service", "").startsWith("BCP")) {
                        return base;
                    }
                } catch (Exception ignored) {}
                return null;
            }));
        }

        String found = null;
        try {
            int total = futures.size();
            long deadline = System.currentTimeMillis() + 6500;
            for (int i = 0; i < total && System.currentTimeMillis() < deadline; i++) {
                Future<String> f = cs.poll(450, TimeUnit.MILLISECONDS);
                if (f == null) continue;
                String s = f.get();
                if (s != null) { found = s; break; }
            }
        } finally {
            for (Future<String> f : futures) f.cancel(true);
            pool.shutdownNow();
        }
        if (found != null) progress.onStage("DISCOVERY_PASS", found);
        return found;
    }

    private static String localIpv4() throws SocketException {
        Enumeration<NetworkInterface> ifaces = NetworkInterface.getNetworkInterfaces();
        while (ifaces.hasMoreElements()) {
            NetworkInterface ni = ifaces.nextElement();
            if (!ni.isUp() || ni.isLoopback()) continue;
            Enumeration<InetAddress> addrs = ni.getInetAddresses();
            while (addrs.hasMoreElements()) {
                InetAddress a = addrs.nextElement();
                if (a instanceof Inet4Address && a.isSiteLocalAddress()) return a.getHostAddress();
            }
        }
        return null;
    }

    public JSONObject checkpoint(String completed, String next) throws Exception {
        ensureConnected();
        JSONObject payload = new JSONObject();
        payload.put("status", "ACTIVE");
        payload.put("last_completed_action", completed);
        payload.put("next_action", next);
        JSONObject body = new JSONObject();
        body.put("type", "checkpoint");
        body.put("payload", payload);
        telemetry.add("CHECKPOINT_START", null);
        JSONObject r = requestJson("POST",
                getServer() + "/v1/projects/" + enc(PROJECT) + "/events",
                body.toString(), getToken(), "edge-" + UUID.randomUUID(), 2500, 5000);
        telemetry.add("CHECKPOINT_PASS", r.optString("event_hash", ""));
        flushTelemetry();
        return r;
    }

    public JSONObject resume() throws Exception {
        ensureConnected();
        telemetry.add("RESUME_START", null);
        JSONObject r = requestJson("GET",
                getServer() + "/v1/projects/" + enc(PROJECT) + "/resume",
                null, getToken(), null, 2500, 5000);
        telemetry.add("RESUME_PASS", "revision=" + r.optJSONObject("head"));
        flushTelemetry();
        return r;
    }

    public JSONObject health() throws Exception {
        ensureConnected();
        return requestJson("GET", getServer() + "/health", null, null, null, 1500, 2500);
    }

    public void heartbeat(String reason) {
        telemetry.add("PHONE_HEARTBEAT", reason == null ? "FOREGROUND" : reason);
        flushTelemetry();
    }

    private JSONObject publicPairStatus(JSONObject pair) throws Exception {
        JSONObject safe = new JSONObject();
        safe.put("paired", pair.optBoolean("paired", true));
        safe.put("pc_name", pair.optString("pc_name", "BCP PC"));
        safe.put("version", pair.optString("version", ""));
        safe.put("project", PROJECT);
        safe.put("credential", "stored_securely_not_displayed");
        return safe;
    }

    private void ensureConnected() throws IOException {
        if (getServer().isEmpty() || getToken().isEmpty()) throw new IOException("NOT_PAIRED");
    }

    public void flushTelemetry() {
        if (getServer().isEmpty() || getToken().isEmpty()) return;
        try {
            JSONArray events = telemetry.readAll();
            if (events.length() == 0) return;
            JSONObject body = new JSONObject();
            body.put("events", events);
            requestJson("POST", getServer() + "/v1/telemetry", body.toString(),
                    getToken(), "telemetry-" + UUID.randomUUID(), 1500, 3000);
            telemetry.clear();
        } catch (Exception ignored) {}
    }

    private static JSONObject requestJson(String method, String url, String body,
                                          String token, String idem,
                                          int connectMs, int readMs) throws Exception {
        HttpURLConnection c = (HttpURLConnection)new URL(url).openConnection();
        c.setRequestMethod(method);
        c.setConnectTimeout(connectMs);
        c.setReadTimeout(readMs);
        c.setRequestProperty("Accept", "application/json");
        if (token != null && !token.isEmpty()) c.setRequestProperty("Authorization", "Bearer " + token);
        if (idem != null) c.setRequestProperty("Idempotency-Key", idem);
        if (body != null) {
            c.setDoOutput(true);
            c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            try (OutputStream os = c.getOutputStream()) {
                os.write(body.getBytes(StandardCharsets.UTF_8));
            }
        }
        int code = c.getResponseCode();
        InputStream in = code >= 400 ? c.getErrorStream() : c.getInputStream();
        String raw = readAll(in);
        if (code >= 400) throw new IOException("HTTP_" + code + ": " + raw);
        return raw.isEmpty() ? new JSONObject() : new JSONObject(raw);
    }

    private static String readAll(InputStream in) throws IOException {
        if (in == null) return "";
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buf = new byte[4096];
        int n;
        while ((n = in.read(buf)) >= 0) out.write(buf, 0, n);
        return out.toString("UTF-8");
    }

    private static String enc(String s) {
        try { return URLEncoder.encode(s, "UTF-8"); }
        catch (Exception e) { return s; }
    }
}
