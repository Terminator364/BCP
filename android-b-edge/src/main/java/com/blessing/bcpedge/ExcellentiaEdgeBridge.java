package com.blessing.bcpedge;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Base64;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Inet4Address;
import java.net.NetworkInterface;
import java.net.URLEncoder;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.zip.GZIPInputStream;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

/**
 * Excellentia continuity node hosted by the dedicated B-EDGE phone.
 *
 * The PC may disappear after synchronisation. The phone retains:
 * - the latest validated Excellentia offline pack;
 * - a bounded QR/pass definition;
 * - browser sessions for the selected duration;
 * - a durable local progress/event queue for later reconciliation.
 *
 * The HTTP study surface intentionally carries no BCP bearer/token.
 * PC -> B-EDGE snapshot admission remains on the authenticated TLS API.
 */
public final class ExcellentiaEdgeBridge {
    public static final int HTTP_PORT = 8878;
    private static final String PREFS = "excellentia_edge_bridge";
    private static final String COOKIE = "exc_edge";
    private static final String PACK_FILE = "excellentia-offline-pack.json";
    private static final String PROGRESS_FILE = "excellentia-progress.jsonl";
    private static final int MAX_BROWSER_BODY = 128 * 1024;

    private final Context context;
    private final SharedPreferences prefs;
    private final ExecutorService io = Executors.newCachedThreadPool();
    private final SecureRandom random = new SecureRandom();
    private volatile boolean stopping = false;
    private volatile ServerSocket serverSocket;

    public ExcellentiaEdgeBridge(Context context) {
        this.context = context.getApplicationContext();
        this.prefs = this.context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        ensurePermanentPass();
    }

    public void start() {
        ensurePermanentPass();
        stopping = false;
        io.submit(this::serveLoop);
    }

    private static String permanentPassSecret(Context context) {
        try {
            String token = new CredentialStore(context.getApplicationContext()).getToken();
            if (token == null || token.isEmpty()) return "";
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(token.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            byte[] out = mac.doFinal("excellentia-edge-permanent-v1".getBytes(StandardCharsets.UTF_8));
            return Base64.encodeToString(out, Base64.NO_WRAP | Base64.URL_SAFE | Base64.NO_PADDING);
        } catch (Exception ignored) {
            return "";
        }
    }

    private boolean ensurePermanentPass() {
        String secret = permanentPassSecret(context);
        if (secret.length() < 24) return false;
        long created = prefs.getLong("permanent_pass_created_at", 0L);
        if (created <= 0L) created = System.currentTimeMillis();
        prefs.edit()
                .putBoolean("permanent_pass", true)
                .putLong("permanent_pass_created_at", created)
                .putString("pass_hash", sha256(secret.getBytes(StandardCharsets.UTF_8)))
                .putInt("pass_minutes", 480)
                .putLong("pass_offer_created_at", created)
                .putLong("pass_offer_expires_at", Long.MAX_VALUE / 4L)
                .apply();
        return true;
    }

    public static String permanentPairUrl(Context context, int minutes) {
        try {
            String secret = permanentPassSecret(context);
            String ip = localIpv4();
            if (secret.length() < 24 || ip.isEmpty()) return "";
            int m = normalizeMinutes(minutes);
            return "http://" + ip + ":" + HTTP_PORT + "/pair#t="
                    + URLEncoder.encode(secret, "UTF-8") + "&m=" + m;
        } catch (Exception ignored) {
            return "";
        }
    }

    private static String localIpv4() {
        try {
            java.util.Enumeration<NetworkInterface> ifaces = NetworkInterface.getNetworkInterfaces();
            while (ifaces != null && ifaces.hasMoreElements()) {
                NetworkInterface ni = ifaces.nextElement();
                if (!ni.isUp() || ni.isLoopback()) continue;
                java.util.Enumeration<java.net.InetAddress> addrs = ni.getInetAddresses();
                while (addrs.hasMoreElements()) {
                    java.net.InetAddress a = addrs.nextElement();
                    if (!(a instanceof Inet4Address) || a.isLoopbackAddress()) continue;
                    String ip = a.getHostAddress();
                    if (ip.startsWith("10.") || ip.startsWith("192.168.") || ip.matches("^172\\.(1[6-9]|2[0-9]|3[01])\\..*")) return ip;
                }
            }
        } catch (Exception ignored) {}
        return "";
    }

    public void stop() {
        stopping = true;
        try { if (serverSocket != null) serverSocket.close(); } catch (Exception ignored) {}
        io.shutdownNow();
    }

    public JSONObject installSnapshot(JSONObject body) {
        JSONObject out = new JSONObject();
        try {
            String build = body.optString("build", "").trim();
            String encoded = body.optString("pack_gzip_base64", "");
            String expectedGzipSha = body.optString("pack_gzip_sha256", "").toLowerCase(Locale.ROOT);
            JSONObject pass = body.optJSONObject("pass");
            if (build.isEmpty() || encoded.isEmpty() || pass == null) {
                return json("ok", false, "error", "invalid_snapshot");
            }
            byte[] gz = Base64.decode(encoded, Base64.DEFAULT);
            if (gz.length == 0 || gz.length > EdgeRelayPolicy.EXCELLENTIA_SNAPSHOT_MAX_BYTES) {
                return json("ok", false, "error", "snapshot_size_invalid");
            }
            String actualGzipSha = sha256(gz);
            if (!expectedGzipSha.isEmpty() && !MessageDigest.isEqual(
                    expectedGzipSha.getBytes(StandardCharsets.US_ASCII),
                    actualGzipSha.getBytes(StandardCharsets.US_ASCII))) {
                return json("ok", false, "error", "snapshot_sha_mismatch");
            }
            byte[] plain = gunzip(gz, EdgeRelayPolicy.EXCELLENTIA_SNAPSHOT_MAX_BYTES * 5);
            JSONObject pack = new JSONObject(new String(plain, StandardCharsets.UTF_8));
            if (!pack.has("questions") || !pack.has("modules")) {
                return json("ok", false, "error", "snapshot_schema_invalid");
            }
            atomicWrite(new File(context.getFilesDir(), PACK_FILE), plain);

            boolean permanentPass = ensurePermanentPass();
            String secret = pass.optString("secret", "");
            int minutes = normalizeMinutes(pass.optInt("minutes", 30));
            if (!permanentPass && secret.length() < 24) return json("ok", false, "error", "pass_secret_invalid");

            long now = System.currentTimeMillis();
            SharedPreferences.Editor editor = prefs.edit()
                    .putString("build", build)
                    .putLong("snapshot_at", now)
                    .putString("snapshot_sha256", sha256(plain))
                    .putInt("questions", pack.optJSONArray("questions") == null ? 0 : pack.optJSONArray("questions").length());
            if (!permanentPass) {
                long offerCreatedAt = pass.optLong("offer_created_at_ms", now);
                long offerExpiresAt = pass.optLong("offer_expires_at_ms", now + Math.max(30, minutes) * 60_000L);
                long previousOfferCreatedAt = prefs.getLong("pass_offer_created_at", 0L);
                long previousActivatedAt = prefs.getLong("pass_activated_at", 0L);
                long previousExpiresAt = prefs.getLong("pass_expires_at", 0L);
                boolean samePass = previousOfferCreatedAt > 0L && previousOfferCreatedAt == offerCreatedAt;
                editor.putString("pass_hash", sha256(secret.getBytes(StandardCharsets.UTF_8)))
                        .putInt("pass_minutes", minutes)
                        .putLong("pass_offer_created_at", offerCreatedAt)
                        .putLong("pass_offer_expires_at", Math.max(offerExpiresAt, prefs.getLong("pass_offer_expires_at", 0L)));
                if (samePass) {
                    editor.putLong("pass_activated_at", previousActivatedAt)
                            .putLong("pass_expires_at", previousExpiresAt);
                } else {
                    editor.putLong("pass_activated_at", 0L)
                            .putLong("pass_expires_at", 0L)
                            .putString("sessions_json", "[]");
                }
            }
            editor.apply();
            if (permanentPass) ensurePermanentPass();

            out.put("ok", true);
            out.put("build", build);
            out.put("questions", prefs.getInt("questions", 0));
            out.put("http_port", HTTP_PORT);
            out.put("snapshot_sha256", prefs.getString("snapshot_sha256", ""));
            out.put("pass_minutes", prefs.getInt("pass_minutes", minutes));
            out.put("pass_activated", false);
            out.put("permanent_pass", prefs.getBoolean("permanent_pass", false));
            return out;
        } catch (Exception e) {
            return json("ok", false, "error", "snapshot_install_failed", "detail", e.getClass().getSimpleName());
        }
    }

    public JSONObject status() {
        long now = System.currentTimeMillis();
        long activated = prefs.getLong("pass_activated_at", 0L);
        long expires = prefs.getLong("pass_expires_at", 0L);
        File pack = new File(context.getFilesDir(), PACK_FILE);
        JSONObject out = json(
                "ok", true,
                "mode", "EXCELLENTIA_EDGE_CONTINUITY",
                "http_port", HTTP_PORT,
                "snapshot_present", pack.exists() && pack.length() > 0,
                "build", prefs.getString("build", ""),
                "snapshot_at", prefs.getLong("snapshot_at", 0L),
                "snapshot_sha256", prefs.getString("snapshot_sha256", ""),
                "questions", prefs.getInt("questions", 0),
                "pass_minutes", prefs.getInt("pass_minutes", 0),
                "pass_offer_created_at", prefs.getLong("pass_offer_created_at", 0L),
                "pass_offer_expires_at", prefs.getLong("pass_offer_expires_at", 0L),
                "pass_activated", activated > 0L,
                "pass_expires_at", expires,
                "pass_remaining_seconds", expires > now ? Math.max(0L, (expires - now) / 1000L) : 0L,
                "permanent_pass", prefs.getBoolean("permanent_pass", false),
                "pair_url_ready", !permanentPairUrl(context, 480).isEmpty(),
                "progress_events", countProgressLines()
        );
        return out;
    }

    public JSONObject revoke() {
        prefs.edit()
                .remove("pass_hash")
                .remove("pass_minutes")
                .remove("pass_offer_expires_at")
                .remove("pass_activated_at")
                .remove("pass_expires_at")
                .putString("sessions_json", "[]")
                .apply();
        return json("ok", true, "revoked", true, "snapshot_retained", new File(context.getFilesDir(), PACK_FILE).exists());
    }

    public JSONObject acknowledgeProgress(JSONObject body) {
        JSONArray ids = body == null ? null : body.optJSONArray("ids");
        if (ids == null || ids.length() == 0) return json("ok", true, "removed", 0);
        java.util.HashSet<String> acked = new java.util.HashSet<>();
        for (int i = 0; i < ids.length(); i++) {
            String id = ids.optString(i, "").trim();
            if (!id.isEmpty()) acked.add(id);
        }
        File src = new File(context.getFilesDir(), PROGRESS_FILE);
        if (!src.exists() || acked.isEmpty()) return json("ok", true, "removed", 0);
        File tmp = new File(context.getFilesDir(), PROGRESS_FILE + ".tmp");
        int removed = 0;
        try (BufferedReader r = new BufferedReader(new InputStreamReader(new FileInputStream(src), StandardCharsets.UTF_8));
             FileOutputStream out = new FileOutputStream(tmp, false)) {
            String line;
            while ((line = r.readLine()) != null) {
                if (line.trim().isEmpty()) continue;
                boolean drop = false;
                try { drop = acked.contains(new JSONObject(line).optString("id", "")); }
                catch (Exception ignored) {}
                if (drop) { removed++; continue; }
                out.write((line + "\n").getBytes(StandardCharsets.UTF_8));
            }
            out.getFD().sync();
        } catch (Exception e) {
            try { tmp.delete(); } catch (Exception ignored) {}
            return json("ok", false, "error", "progress_ack_failed");
        }
        try {
            if (src.exists() && !src.delete()) throw new IllegalStateException("progress_replace_delete_failed");
            if (!tmp.renameTo(src)) throw new IllegalStateException("progress_replace_rename_failed");
        } catch (Exception e) {
            return json("ok", false, "error", "progress_ack_replace_failed");
        }
        return json("ok", true, "removed", removed, "remaining", countProgressLines());
    }

    public JSONObject revoke(String reason) {
        long now = System.currentTimeMillis();
        prefs.edit()
                .remove("pass_hash")
                .putLong("pass_offer_expires_at", now - 1L)
                .putLong("pass_expires_at", now - 1L)
                .putString("sessions_json", "[]")
                .apply();
        return json("ok", true, "revoked", true, "reason", reason == null ? "" : reason, "at", now);
    }

    public JSONObject progressTail(int max) {
        JSONArray items = new JSONArray();
        File f = new File(context.getFilesDir(), PROGRESS_FILE);
        if (!f.exists()) return json("ok", true, "count", 0, "items", items);
        try (BufferedReader r = new BufferedReader(new InputStreamReader(new FileInputStream(f), StandardCharsets.UTF_8))) {
            java.util.ArrayDeque<String> q = new java.util.ArrayDeque<>();
            String line;
            int lim = Math.max(1, Math.min(1000, max));
            while ((line = r.readLine()) != null) {
                if (line.trim().isEmpty()) continue;
                q.addLast(line);
                while (q.size() > lim) q.removeFirst();
            }
            for (String x : q) {
                try { items.put(new JSONObject(x)); } catch (Exception ignored) {}
            }
        } catch (Exception ignored) {}
        return json("ok", true, "count", items.length(), "items", items);
    }

    private void serveLoop() {
        try (ServerSocket server = new ServerSocket()) {
            server.setReuseAddress(true);
            server.bind(new InetSocketAddress("0.0.0.0", HTTP_PORT), 12);
            serverSocket = server;
            while (!stopping) {
                Socket client = server.accept();
                io.submit(() -> handleClient(client));
            }
        } catch (Exception ignored) {
        }
    }

    private void handleClient(Socket client) {
        try (Socket c = client) {
            c.setSoTimeout(30_000);
            InputStream in = c.getInputStream();
            OutputStream out = c.getOutputStream();
            String line = readLine(in, 4096);
            if (line == null) return;
            String[] p = line.trim().split("\\s+");
            if (p.length != 3) { writeText(out, 400, "text/plain; charset=utf-8", "Bad request"); return; }
            String method = p[0].toUpperCase(Locale.ROOT);
            String path = cleanPath(p[1]);
            Map<String,String> headers = readHeaders(in);

            if ("OPTIONS".equals(method) && "/health".equals(path)) {
                Map<String,String> cors = new HashMap<>();
                cors.put("Access-Control-Allow-Origin", "*");
                cors.put("Access-Control-Allow-Methods", "GET, OPTIONS");
                cors.put("Access-Control-Allow-Private-Network", "true");
                writeJson(out, 200, json("ok", true), cors); return;
            }
            if ("GET".equals(method) && "/health".equals(path)) {
                Map<String,String> cors = new HashMap<>();
                cors.put("Access-Control-Allow-Origin", "*");
                cors.put("Access-Control-Allow-Private-Network", "true");
                writeJson(out, 200, status(), cors); return;
            }
            if ("GET".equals(method) && "/pair".equals(path)) {
                Map<String,String> cache = new HashMap<>();
                cache.put("Cache-Control", "private, max-age=28800, stale-if-error=86400");
                if (!passOfferAlive()) { writeText(out, 410, "text/html; charset=utf-8", expiredPage(), cache); return; }
                writeText(out, 200, "text/html; charset=utf-8", pairPage(), cache); return;
            }
            if ("POST".equals(method) && "/api/claim".equals(path)) {
                JSONObject body = readJsonBody(in, headers, MAX_BROWSER_BODY);
                writeClaim(out, body.optString("token", ""), body.optLong("expires_at_ms", 0L), body.optInt("minutes", 0)); return;
            }

            boolean auth = browserAuthorized(headers.get("cookie"));
            if (!auth) {
                if ("GET".equals(method) && "/".equals(path) && passOfferAlive()) {
                    writeRedirect(out, "/pair"); return;
                }
                writeJson(out, 401, json("ok", false, "error", "pass_required")); return;
            }

            if ("GET".equals(method) && ("/".equals(path) || "/study".equals(path))) {
                Map<String,String> cache = new HashMap<>();
                cache.put("Cache-Control", "private, max-age=28800, stale-if-error=86400");
                writeText(out, 200, "text/html; charset=utf-8", studyPage(), cache); return;
            }
            if ("GET".equals(method) && "/api/status".equals(path)) {
                writeJson(out, 200, status()); return;
            }
            if ("GET".equals(method) && "/api/offline-pack".equals(path)) {
                File f = new File(context.getFilesDir(), PACK_FILE);
                if (!f.exists()) { writeJson(out, 503, json("ok", false, "error", "snapshot_missing")); return; }
                writeBytes(out, 200, "application/json; charset=utf-8", readAll(f, EdgeRelayPolicy.EXCELLENTIA_SNAPSHOT_MAX_BYTES * 5));
                return;
            }
            if ("POST".equals(method) && "/api/progress".equals(path)) {
                JSONObject body = readJsonBody(in, headers, MAX_BROWSER_BODY);
                JSONObject receipt = appendProgress(body);
                writeJson(out, 202, receipt); return;
            }
            if ("GET".equals(method) && "/api/progress".equals(path)) {
                writeJson(out, 200, progressTail(100)); return;
            }
            writeJson(out, 404, json("ok", false, "error", "not_found"));
        } catch (Exception ignored) {
        }
    }

    private void writeClaim(OutputStream out, String token, long requestedExpiresAt, int requestedMinutes) throws Exception {
        long now = System.currentTimeMillis();
        ensurePermanentPass();
        if (!passOfferAlive()) { writeJson(out, 410, json("ok", false, "error", "pass_expired")); return; }
        String supplied = sha256(token.getBytes(StandardCharsets.UTF_8));
        String expected = prefs.getString("pass_hash", "");
        if (expected.isEmpty() || !MessageDigest.isEqual(
                supplied.getBytes(StandardCharsets.US_ASCII),
                expected.getBytes(StandardCharsets.US_ASCII))) {
            writeJson(out, 403, json("ok", false, "error", "pass_invalid")); return;
        }
        boolean permanent = prefs.getBoolean("permanent_pass", false);
        int minutes = normalizeMinutes(requestedMinutes > 0 ? requestedMinutes : prefs.getInt("pass_minutes", 480));
        long maxSessionExpiry = now + minutes * 60_000L;
        long authoritativeExpiry = requestedExpiresAt > now ? Math.min(requestedExpiresAt, maxSessionExpiry) : 0L;
        long expires = authoritativeExpiry > 0L ? authoritativeExpiry : maxSessionExpiry;
        if (!permanent) {
            long activated = prefs.getLong("pass_activated_at", 0L);
            long globalExpires = prefs.getLong("pass_expires_at", 0L);
            if (activated > 0L && globalExpires <= now) {
                writeJson(out, 410, json("ok", false, "error", "pass_expired")); return;
            }
            if (activated <= 0L) {
                prefs.edit().putLong("pass_activated_at", now).putLong("pass_expires_at", expires).apply();
            } else {
                expires = Math.min(expires, globalExpires);
            }
        } else {
            prefs.edit().putLong("pass_activated_at", now).putLong("pass_expires_at", expires).apply();
        }
        if (expires <= now) { writeJson(out, 410, json("ok", false, "error", "pass_expired")); return; }
        String raw = randomToken();
        JSONArray sessions = sessions();
        JSONObject session = new JSONObject();
        session.put("hash", sha256(raw.getBytes(StandardCharsets.UTF_8)));
        session.put("created_at", now);
        session.put("expires_at", expires);
        sessions.put(session);
        saveSessions(cleanSessions(sessions, now));
        Map<String,String> extra = new HashMap<>();
        extra.put("Set-Cookie", COOKIE + "=" + raw + "; HttpOnly; SameSite=Lax; Path=/; Max-Age=" + Math.max(1L, (expires - now) / 1000L));
        writeJson(out, 200, json("ok", true,
                "offer_created_at", prefs.getLong("pass_offer_created_at", 0L),
                "expires_at", expires,
                "remaining_seconds", Math.max(0L, (expires - now) / 1000L)), extra);
    }

    private boolean passOfferAlive() {
        ensurePermanentPass();
        if (prefs.getBoolean("permanent_pass", false) && !prefs.getString("pass_hash", "").isEmpty()) return true;
        long now = System.currentTimeMillis();
        long activated = prefs.getLong("pass_activated_at", 0L);
        long expires = prefs.getLong("pass_expires_at", 0L);
        if (activated > 0L) return expires > now;
        return prefs.getLong("pass_offer_expires_at", 0L) > now;
    }

    private boolean browserAuthorized(String cookieHeader) {
        String raw = cookieValue(cookieHeader, COOKIE);
        if (raw.isEmpty()) return false;
        long now = System.currentTimeMillis();
        String h = sha256(raw.getBytes(StandardCharsets.UTF_8));
        JSONArray sessions = cleanSessions(sessions(), now);
        saveSessions(sessions);
        for (int i = 0; i < sessions.length(); i++) {
            JSONObject x = sessions.optJSONObject(i);
            if (x == null || x.optLong("expires_at", 0L) <= now) continue;
            String expected = x.optString("hash", "");
            if (!expected.isEmpty() && MessageDigest.isEqual(
                    h.getBytes(StandardCharsets.US_ASCII),
                    expected.getBytes(StandardCharsets.US_ASCII))) return true;
        }
        return false;
    }

    private JSONArray sessions() {
        try { return new JSONArray(prefs.getString("sessions_json", "[]")); }
        catch (Exception e) { return new JSONArray(); }
    }

    private JSONArray cleanSessions(JSONArray src, long now) {
        JSONArray out = new JSONArray();
        for (int i = 0; i < src.length(); i++) {
            JSONObject x = src.optJSONObject(i);
            if (x != null && x.optLong("expires_at", 0L) > now) out.put(x);
        }
        return out;
    }

    private void saveSessions(JSONArray a) {
        prefs.edit().putString("sessions_json", a.toString()).apply();
    }

    private JSONObject appendProgress(JSONObject body) {
        try {
            JSONObject row = new JSONObject();
            row.put("id", body.optString("id", "edge-" + System.currentTimeMillis() + "-" + random.nextInt(1_000_000)));
            row.put("at", System.currentTimeMillis());
            row.put("build", prefs.getString("build", ""));
            row.put("run_id", body.optString("run_id", ""));
            row.put("run_total", body.optInt("run_total", 0));
            row.put("run_position", body.optInt("run_position", 0));
            row.put("question_id", body.optString("question_id", ""));
            row.put("knowledge_id", body.optString("knowledge_id", ""));
            row.put("selected", body.has("selected") ? body.optInt("selected", -1) : -1);
            row.put("correct", body.optBoolean("correct", false));
            row.put("module", body.optInt("module", 0));
            row.put("mode", body.optString("mode", "EDGE_OFFLINE"));
            row.put("origin_session_id", body.optString("origin_session_id", ""));
            row.put("elapsed_ms", Math.max(0, Math.min(40_000, body.optInt("elapsed_ms", 0))));
            row.put("timed_out", body.optBoolean("timed_out", false));
            synchronized (this) {
                try (FileOutputStream fos = new FileOutputStream(new File(context.getFilesDir(), PROGRESS_FILE), true)) {
                    fos.write((row.toString() + "\n").getBytes(StandardCharsets.UTF_8));
                    fos.getFD().sync();
                }
            }
            return json("ok", true, "queued", true, "id", row.optString("id"));
        } catch (Exception e) {
            return json("ok", false, "error", "progress_write_failed");
        }
    }

    private long countProgressLines() {
        long n = 0L;
        File f = new File(context.getFilesDir(), PROGRESS_FILE);
        if (!f.exists()) return 0L;
        try (BufferedReader r = new BufferedReader(new InputStreamReader(new FileInputStream(f), StandardCharsets.UTF_8))) {
            while (r.readLine() != null) n++;
        } catch (Exception ignored) {}
        return n;
    }

    private String pairPage() {
        return """
<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Excellentia · Connexion Edge</title>
<style>
body{font-family:system-ui;background:#091522;color:#eef6ff;margin:0;min-height:100vh;display:grid;place-items:center;padding:20px}
.b{max-width:430px;background:#10263f;border:1px solid #284d73;border-radius:22px;padding:24px}
button,input{width:100%;box-sizing:border-box;padding:14px;border-radius:12px;border:1px solid #365778;background:#0b1b2d;color:#fff}
button{margin-top:10px;background:#1684f8;border:0;font-weight:800}
.m{color:#a8bdd2}.ok{color:#63e6a3}.bad{color:#ff8390}
</style>
</head>
<body>
<div class="b">
<h2>📚 Excellentia · Continuité Edge</h2>
<p class="m">Un seul pass, avec reprise locale même après microcoupure Wi‑Fi.</p>
<form id="f"><input id="c" placeholder="Code/jeton"><button>Se connecter</button></form>
<p id="s" class="m">Connexion au nœud B‑EDGE…</p>
</div>
<script>
(function(){
  const f=document.getElementById('f'),c=document.getElementById('c'),s=document.getElementById('s');
  const decodeState=v=>{
    try{
      let b=v.replaceAll('-','+').replaceAll('_','/');
      while(b.length%4)b+='=';
      return JSON.parse(decodeURIComponent(escape(atob(b))))
    }catch{return null}
  };
  const privatePrefix=()=>{
    const h=location.hostname||'';
    const p=h.split('.');
    if(p.length!==4)return null;
    const n=p.map(Number);
    if(n.some(x=>!Number.isInteger(x)||x<0||x>255))return null;
    const priv=n[0]===10||n[0]===192&&n[1]===168||n[0]===172&&n[1]>=16&&n[1]<=31;
    return priv?p.slice(0,3).join('.')+'.':null;
  };
  async function probe(ip,expected){
    const ctl=new AbortController();const t=setTimeout(()=>ctl.abort(),450);
    try{
      const r=await fetch('http://'+ip+':8878/health',{cache:'no-store',mode:'cors',signal:ctl.signal});
      if(!r.ok)return null;
      const j=await r.json();
      if(j?.mode!=='EXCELLENTIA_EDGE_CONTINUITY')return null;
      if(expected&&Number(j.pass_offer_created_at||0)!==Number(expected))return null;
      return ip;
    }catch{return null}finally{clearTimeout(t)}
  }
  async function recover(token,state){
    const exp=Number(localStorage.getItem('exc_edge_pass_expires_at')||0);
    if(exp&&Date.now()>=exp){localStorage.removeItem('exc_edge_rebind_token');return false}
    const prefix=privatePrefix();if(!prefix||!token)return false;
    s.className='m';s.textContent='Recherche du nœud Excellentia sur le Wi‑Fi…';
    const expected=localStorage.getItem('exc_edge_offer_created_at')||'';
    let next=1,found=null;
    async function worker(){
      while(!found&&next<255){
        const i=next++,ip=prefix+i;if(ip===location.hostname)continue;
        const hit=await probe(ip,expected);if(hit){found=hit;break}
      }
    }
    await Promise.all(Array.from({length:20},()=>worker()));
    if(!found)return false;
    const payload=state?('&state='+encodeURIComponent(state)):'';
    location.replace('http://'+found+':8878/pair#t='+encodeURIComponent(token)+payload);
    return true;
  }
  async function go(t,state){
    if(!t)return;
    localStorage.setItem('exc_edge_rebind_token',t);
    s.textContent='Vérification…';let last=null;
    for(let a=1;a<=3;a++){
      try{
        const authoritativeExpiry=Number(localStorage.getItem('exc_edge_authoritative_expires_at')||0);
        const r=await fetch('/api/claim',{method:'POST',cache:'no-store',headers:{'content-type':'application/json'},body:JSON.stringify({token:t,expires_at_ms:authoritativeExpiry,minutes})});
        const j=await r.json();
        if(!r.ok){const e=new Error(j.error||'REFUSED');e.http=true;throw e}
        if(j.offer_created_at)localStorage.setItem('exc_edge_offer_created_at',String(j.offer_created_at));if(j.expires_at)localStorage.setItem('exc_edge_pass_expires_at',String(j.expires_at));localStorage.setItem('exc_edge_last_ip',location.hostname);
        history.replaceState(null,'','/pair');
        s.className='ok';s.textContent='Connecté. Ouverture…';
        setTimeout(()=>location.replace('/'),250);return;
      }catch(e){
        last=e;if(e.http)break;
        if(a<3){s.className='m';s.textContent='Connexion instable · nouvelle tentative…';await new Promise(r=>setTimeout(r,450*a))}
      }
    }
    if(await recover(t,state))return;
    s.className='bad';s.textContent='Connexion refusée : '+(last&&last.message?last.message:'REFUSED');
  }
  const q=new URLSearchParams((location.hash||'').replace(/^#/,''));
  const minutes=Math.max(30,Math.min(480,Number(q.get('m')||480)));
  const state=q.get('state')||'';
  const restored=state?decodeState(state):null;
  if(restored){
    if(typeof restored.run==='string'&&restored.run)localStorage.setItem('exc_edge_run',restored.run);
    if(typeof restored.outbox==='string'&&restored.outbox)localStorage.setItem('exc_edge_outbox',restored.outbox);
    if(Number(restored.pass_expires_at_ms)>0)localStorage.setItem('exc_edge_authoritative_expires_at',String(Number(restored.pass_expires_at_ms)));
  }
  const token=q.get('t')||localStorage.getItem('exc_edge_rebind_token')||'';
  if(token){location.hash='';go(token,state)}
  f.onsubmit=e=>{e.preventDefault();const t=c.value.trim();if(t)go(t,'')};
})();
</script>
</body>
</html>
""";
    }

    private String expiredPage() {
        return "<!doctype html><html lang=fr><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><body style='font-family:system-ui;background:#091522;color:#eef6ff;padding:28px'><h2>Pass expiré</h2><p>Crée un nouveau pass Excellentia depuis le PC administrateur.</p></body></html>";
    }

    private String studyPage() {
        return """
<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#0b1119">
<title>Excellentia Study Hub · Edge</title>
<style>
*{box-sizing:border-box}html,body{margin:0;min-height:100%;font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#09111b;color:#edf4ff}
body{padding-bottom:72px}.top{position:sticky;top:0;z-index:20;background:rgba(11,17,25,.96);backdrop-filter:blur(12px);border-bottom:1px solid #22364d;padding:12px 14px}
.topline{display:flex;align-items:center;justify-content:space-between;gap:10px;max-width:980px;margin:auto}.brand{font-weight:850;letter-spacing:-.2px}.sub{font-size:12px;color:#9fb2c7}
.pills{display:flex;gap:7px;align-items:center;flex-wrap:wrap}.pill{font-size:12px;padding:5px 9px;border:1px solid #35506d;border-radius:999px;background:#102030}
.wrap{max-width:980px;margin:auto;padding:16px}.hero{background:linear-gradient(135deg,#11283c,#102036);border:1px solid #294865;border-radius:20px;padding:18px;margin-bottom:14px}
.hero h1{font-size:24px;margin:0 0 8px}.hero p{margin:0;color:#abc0d6;line-height:1.55}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:11px}.card{background:#101c29;border:1px solid #263b53;border-radius:16px;padding:15px}
.action{cursor:pointer;text-align:left;min-height:116px}.action b{display:block;font-size:17px;margin:8px 0 5px}.icon{font-size:23px}.muted{color:#9fb2c7;font-size:13px;line-height:1.5}
h2,h3{margin:.15em 0 .6em}button,select{font:inherit;color:#fff;background:#14263a;border:1px solid #34506f;border-radius:11px;padding:11px 13px}
button{cursor:pointer}.primary{background:#1284ee;border-color:#1284ee;font-weight:800}.ghost{background:#0d1926}.full{width:100%}.row{display:flex;align-items:center;gap:9px;justify-content:space-between;flex-wrap:wrap}
.toolbar{display:flex;gap:9px;flex-wrap:wrap;margin:10px 0 14px}.toolbar>*{flex:1 1 150px}
.nav{position:fixed;z-index:30;bottom:0;left:0;right:0;background:#0d1723;border-top:1px solid #263b53;display:flex;justify-content:center;overflow-x:auto}
.nav button{border:0;border-radius:0;background:transparent;color:#8fa6bd;min-width:86px;padding:11px 9px 10px;font-size:12px}.nav button.active{color:#fff;background:#132337}
.view{display:none}.view.active{display:block}.lesson{margin:10px 0}.lesson summary{cursor:pointer;font-weight:800}.lesson ul{padding-left:19px}.lesson li{margin:7px 0;line-height:1.45}
.kcard{padding:15px;border-radius:14px;border:1px solid #2c4560;background:#0e1a27;margin:10px 0}.kanswer{display:none;margin-top:9px;color:#7fe0ad}.kcard.revealed .kanswer{display:block}
.ans{display:block;width:100%;text-align:left;margin:9px 0;padding:13px}.good{border-color:#35c88a;background:#103125}.bad{border-color:#ef6672;background:#35151a}
.timer-hot{border-color:#ef6672!important;color:#ff98a0!important}.quizbox{max-width:760px;margin:auto}.question{font-size:clamp(20px,5vw,30px);line-height:1.25;margin:18px 0}
.empty{text-align:center;padding:28px 10px}.stat{font-size:28px;font-weight:850}.mini{font-size:11px;color:#8399b0}.danger{color:#ff8791}
@media(min-width:760px){body{padding-bottom:0}.nav{position:sticky;top:58px;bottom:auto;border-top:0;border-bottom:1px solid #263b53}.nav button{min-width:120px}.wrap{padding-top:20px}}
</style>
</head>
<body>
<header class="top">
  <div class="topline">
    <div><div class="brand">Excellentia Study Hub · EDGE</div><div class="sub">Mode élève · essai libre · continuité locale</div></div>
    <div class="pills"><span class="pill" id="timer">Essai libre</span><span class="pill" id="net">nœud local</span></div>
  </div>
</header>
<nav class="nav" id="nav">
  <button data-view="home" class="active">Accueil</button>
  <button data-view="learn">Apprendre</button>
  <button data-view="train">S'entraîner</button>
  <button data-view="review">Réviser</button>
  <button data-view="exam">Examens</button>
  <button data-view="progress">Progression</button>
</nav>
<main class="wrap">
  <section id="v-home" class="view active"></section>
  <section id="v-learn" class="view"></section>
  <section id="v-train" class="view"></section>
  <section id="v-review" class="view"></section>
  <section id="v-exam" class="view"></section>
  <section id="v-progress" class="view"></section>
  <section id="v-quiz" class="view"></section>
</main>
<script>
(async()=>{
  const QUESTION_LIMIT_MS=40000;
  let pack=null,run=null,timingBusy=false,currentView='home',reviewCards=[];
  const esc=v=>String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
  const q=s=>document.querySelector(s),qa=s=>[...document.querySelectorAll(s)];
  let recovering=false;

  function routePrefix(){
    const raw=localStorage.getItem('exc_edge_last_ip')||location.hostname||'',p=raw.split('.');
    if(p.length!==4)return null;const n=p.map(Number);
    if(n.some(x=>!Number.isInteger(x)||x<0||x>255))return null;
    const priv=n[0]===10||n[0]===192&&n[1]===168||n[0]===172&&n[1]>=16&&n[1]<=31;
    return priv?p.slice(0,3).join('.')+'.':null
  }
  function encodeRouteState(){
    try{
      const x={run:localStorage.getItem('exc_edge_run')||'',outbox:localStorage.getItem('exc_edge_outbox')||'[]',pass_expires_at_ms:Number(localStorage.getItem('exc_edge_pass_expires_at')||0)};
      return btoa(unescape(encodeURIComponent(JSON.stringify(x)))).replaceAll('+','-').replaceAll('/','_').replace(/=+$/,'')
    }catch{return ''}
  }
  async function probeRoute(ip,expected){
    const ctl=new AbortController(),t=setTimeout(()=>ctl.abort(),450);
    try{
      const r=await fetch('http://'+ip+':8878/health',{cache:'no-store',mode:'cors',signal:ctl.signal});if(!r.ok)return null;
      const j=await r.json();if(j?.mode!=='EXCELLENTIA_EDGE_CONTINUITY')return null;
      if(expected&&Number(j.pass_offer_created_at||0)!==Number(expected))return null;return ip
    }catch{return null}finally{clearTimeout(t)}
  }
  async function recoverRoute(){
    if(recovering)return true;
    const exp=Number(localStorage.getItem('exc_edge_pass_expires_at')||0);if(exp&&Date.now()>=exp){localStorage.removeItem('exc_edge_rebind_token');return false}
    const token=localStorage.getItem('exc_edge_rebind_token')||'',prefix=routePrefix();if(!token||!prefix)return false;
    recovering=true;q('#net').textContent='recherche du nœud…';
    const expected=localStorage.getItem('exc_edge_offer_created_at')||'';let next=1,found=null;
    async function worker(){while(!found&&next<255){const ip=prefix+(next++);if(ip===location.hostname)continue;const hit=await probeRoute(ip,expected);if(hit){found=hit;break}}}
    await Promise.all(Array.from({length:20},()=>worker()));
    if(!found){recovering=false;q('#net').textContent='hors ligne · local';return false}
    const state=encodeRouteState();location.replace('http://'+found+':8878/pair#t='+encodeURIComponent(token)+(state?'&state='+encodeURIComponent(state):''));return true
  }

  function outbox(){try{return JSON.parse(localStorage.getItem('exc_edge_outbox')||'[]')}catch{return []}}
  function saveOutbox(items){localStorage.setItem('exc_edge_outbox',JSON.stringify(items.slice(-500)))}
  async function flushOutbox(){
    const pending=outbox();if(!pending.length)return true;const keep=[];
    for(const item of pending){try{const r=await fetch('/api/progress',{method:'POST',cache:'no-store',headers:{'content-type':'application/json'},body:JSON.stringify(item)});if(!r.ok)throw new Error()}catch{keep.push(item)}}
    saveOutbox(keep);return keep.length===0
  }
  function queueProgress(item){const p=outbox();if(!p.some(x=>x.id===item.id))p.push(item);saveOutbox(p);void flushOutbox()}

  function modules(){
    const mods=Array.isArray(pack?.modules)?pack.modules:[];
    return mods.filter(x=>Number(x.id)<=8)
  }
  function moduleOptions(all=true){
    return (all?'<option value="0">Grand Mix</option>':'')+modules().map(x=>'<option value="'+Number(x.id)+'">'+esc(x.short||x.title||('Module '+x.id))+'</option>').join('')
  }
  function questions(module=0){return (pack?.questions||[]).filter(x=>!module||Number(x.module)===Number(module))}
  function lessonCount(){return Object.values(pack?.lessons||{}).reduce((n,a)=>n+(Array.isArray(a)?a.length:0),0)}

  function setView(v){
    currentView=v;
    qa('.view').forEach(x=>x.classList.remove('active'));q('#v-'+v)?.classList.add('active');
    qa('#nav [data-view]').forEach(x=>x.classList.toggle('active',x.dataset.view===v));
    if(v!=='quiz'&&(!run||current()?.id==null))q('#timer').textContent='Essai libre';
    renderView(v);window.scrollTo({top:0,behavior:'instant'})
  }
  function renderView(v){
    if(v==='home')renderHome();else if(v==='learn')renderLearn();else if(v==='train')renderTrain();
    else if(v==='review')renderReview();else if(v==='exam')renderExam();else if(v==='progress')renderProgress();else if(v==='quiz')renderQuiz()
  }

  function renderHome(){
    const active=run&&current();
    q('#v-home').innerHTML=
      '<div class="hero"><h1>Bienvenue dans ton espace Excellentia</h1><p>Le QR ouvre maintenant la plateforme en <b>essai libre</b>. Choisis ce que tu veux faire ; aucun test ne démarre automatiquement.</p></div>'+
      '<div class="grid">'+
      card('📘','Apprendre',lessonCount()+' fiches disponibles','learn')+
      card('🎯',"S'entraîner",'Séries chronométrées · 40 s/question','train')+
      card('🔁','Réviser','Rappel actif et micro-fiches','review')+
      card('🧪','Examens','Simulation avec correction masquée','exam')+
      card('📈','Progression','État local, reprise et synchronisation','progress')+
      '</div>'+
      (active?'<div class="card"><div class="row"><div><b>Session en cours</b><div class="muted">Question '+(Number(run.i)+1)+' / '+run.ids.length+'</div></div><button class="primary" id="resumeRun">Reprendre</button></div></div>':'');
    q('#resumeRun')?.addEventListener('click',()=>setView('quiz'))
  }
  function card(icon,title,desc,view){return '<button class="card action" data-go="'+view+'"><span class="icon">'+icon+'</span><b>'+esc(title)+'</b><span class="muted">'+esc(desc)+'</span></button>'}

  function renderLearn(){
    q('#v-learn').innerHTML='<div class="hero"><h1>Apprendre</h1><p>Choisis un module puis ouvre une fiche. Le contenu vient du dernier snapshot validé du PC.</p></div>'+
      '<div class="toolbar"><select id="learnMod">'+moduleOptions(false)+'</select></div><div id="lessonHost"></div>';
    const sel=q('#learnMod');sel.onchange=renderLessonList;renderLessonList()
  }
  function renderLessonList(){
    const m=Number(q('#learnMod')?.value||modules()[0]?.id||1),list=pack?.lessons?.[String(m)]||[];
    q('#lessonHost').innerHTML=list.length?list.map((l,i)=>'<details class="card lesson"><summary>'+esc(l.title||('Fiche '+(i+1)))+' <span class="mini">· '+Number(l.minutes||0)+' min</span></summary>'+
      '<p class="muted">'+esc(l.summary||'')+'</p>'+
      ((l.objectives||[]).length?'<h3>Objectifs</h3><ul>'+(l.objectives||[]).map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>':'')+
      ((l.points||[]).length?'<h3>Points clés</h3><ul>'+(l.points||[]).map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>':'')+
      ((l.recall_prompts||[]).length?'<h3>Rappel actif</h3><ul>'+(l.recall_prompts||[]).map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>':'')+
      '</details>').join(''):'<div class="card empty">Aucune fiche dans ce module.</div>'
  }

  function renderTrain(){
    q('#v-train').innerHTML='<div class="hero"><h1>S\'entraîner</h1><p>Tu choisis quand commencer. Une fois la série lancée : 40 secondes maximum par question.</p></div>'+
      '<div class="card"><div class="toolbar"><select id="trainMod">'+moduleOptions(true)+'</select><select id="trainCount"><option>10</option><option>20</option><option>30</option></select><button class="primary" id="trainStart">Lancer la série</button></div></div>';
    q('#trainStart').onclick=()=>startRun(Number(q('#trainMod').value||0),Number(q('#trainCount').value||10),'module')
  }

  function renderExam(){
    q('#v-exam').innerHTML='<div class="hero"><h1>Examens</h1><p>40 secondes par question. Les réponses sont enregistrées, mais la correction reste masquée jusqu\'à la fin.</p></div>'+
      '<div class="card"><div class="toolbar"><select id="examMod">'+moduleOptions(true)+'</select><select id="examCount"><option value="10">Mini blanc · 10</option><option value="20">Blanc · 20</option><option value="30">Blanc · 30</option></select><button class="primary" id="examStart">Commencer</button></div></div>';
    q('#examStart').onclick=()=>startRun(Number(q('#examMod').value||0),Number(q('#examCount').value||10),'mock')
  }

  function renderReview(){
    if(!reviewCards.length){
      const all=[...questions(0)];for(let i=all.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[all[i],all[j]]=[all[j],all[i]]}reviewCards=all.slice(0,12)
    }
    q('#v-review').innerHTML='<div class="hero"><h1>Réviser</h1><p>Essaie de répondre mentalement, puis touche la carte pour révéler la réponse.</p></div>'+
      reviewCards.map((x,i)=>'<div class="kcard" data-card="'+i+'"><b>'+esc(x.prompt)+'</b><div class="kanswer"><b>'+esc((x.choices||[])[Number(x.answer)]||'')+'</b><div class="muted">'+esc(x.explanation||'')+'</div></div></div>').join('')+
      '<button class="full ghost" id="newReview">Nouvelles cartes</button>';
    qa('[data-card]').forEach(x=>x.onclick=()=>x.classList.toggle('revealed'));
    q('#newReview').onclick=()=>{reviewCards=[];renderReview()}
  }

  function renderProgress(){
    const answered=run?Object.keys(run.answers||{}).length:0;
    q('#v-progress').innerHTML='<div class="hero"><h1>Progression locale</h1><p>Cette vue couvre ce qui est disponible sur B-EDGE pendant que le PC est absent.</p></div>'+
      '<div class="grid">'+
      '<div class="card"><div class="stat">'+Number(pack?.questions?.length||0)+'</div><div class="muted">questions disponibles</div></div>'+
      '<div class="card"><div class="stat">'+lessonCount()+'</div><div class="muted">fiches disponibles</div></div>'+
      '<div class="card"><div class="stat">'+outbox().length+'</div><div class="muted">réponses en attente de synchro</div></div>'+
      '<div class="card"><div class="stat">'+answered+'</div><div class="muted">réponses dans la session locale</div></div>'+
      '</div><div class="card"><b>Snapshot</b><div class="muted">'+esc(pack?.build||'inconnu')+' · synchronisation automatique au retour du PC</div></div>'
  }

  function save(){if(run)localStorage.setItem('exc_edge_run',JSON.stringify(run))}
  function current(){if(!run)return null;return questions(0).find(x=>x.id===run.ids[run.i])||null}
  function startRun(module,count,mode){
    const all=[...questions(module)];for(let i=all.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[all[i],all[j]]=[all[j],all[i]]}
    const now=Date.now();run={id:'edge-run-'+now+'-'+Math.random().toString(36).slice(2,8),origin_session_id:'',ids:all.slice(0,Math.max(1,Math.min(count,all.length))).map(x=>x.id),i:0,score:0,answers:{},mode,module,started:now,question_started_at:now,deadlineAt:now+QUESTION_LIMIT_MS,question_limit_ms:QUESTION_LIMIT_MS};
    save();setView('quiz')
  }
  function ensureQuestionClock(){
    if(!run)return;const x=current();if(!x||run.answers[x.id]!=null)return;
    const now=Date.now();if(!Number(run.question_started_at||0))run.question_started_at=now;
    if(!Number(run.deadlineAt||0))run.deadlineAt=now+QUESTION_LIMIT_MS;save()
  }
  function questionMsLeft(){if(!run)return QUESTION_LIMIT_MS;const x=current();if(!x||run.answers[x.id]!=null)return 0;ensureQuestionClock();return Math.max(0,Number(run.deadlineAt||0)-Date.now())}
  function paintTimer(){
    const el=q('#timer');if(!el)return;
    if(currentView!=='quiz'||!run||!current()){el.textContent='Essai libre';el.classList.remove('timer-hot');return}
    const x=current(),answered=run.answers[x.id]!=null,sec=Math.max(0,Math.ceil(questionMsLeft()/1000));
    el.textContent=answered?'Répondu':'00:'+String(sec).padStart(2,'0');el.classList.toggle('timer-hot',!answered&&sec<=10)
  }
  async function answer(i,timedOut=false){
    const x=current();if(!x||run.answers[x.id]!=null||timingBusy)return;timingBusy=true;
    try{
      const selected=timedOut?-1:Number(i),ok=!timedOut&&selected===Number(x.answer),started=Number(run.question_started_at||Date.now()),elapsed=timedOut?QUESTION_LIMIT_MS:Math.max(0,Math.min(QUESTION_LIMIT_MS,Date.now()-started));
      run.answers[x.id]=selected;if(ok)run.score++;run.deadlineAt=0;save();
      queueProgress({id:run.id+'-'+(run.i+1)+'-'+x.id,run_id:run.id,run_total:run.ids.length,run_position:run.i+1,origin_session_id:String(run.origin_session_id||''),question_id:x.id,knowledge_id:x.knowledge_id,module:x.module,selected,correct:ok,mode:String(run.mode||'EDGE_OFFLINE'),elapsed_ms:elapsed,timed_out:timedOut});
      if(timedOut){nextQuestion();return}renderQuiz()
    }finally{timingBusy=false}
  }
  function nextQuestion(){
    void flushOutbox();
    if(run.i<run.ids.length-1){run.i++;const now=Date.now();run.question_started_at=now;run.deadlineAt=now+QUESTION_LIMIT_MS;save();renderQuiz();return}
    finishRun()
  }
  function finishRun(){
    const mock=String(run.mode||'').toLowerCase()==='mock';
    q('#v-quiz').innerHTML='<div class="quizbox card empty"><h2>Terminé'+(mock?'':' · '+run.score+'/'+run.ids.length)+'</h2><p class="muted">'+(mock?'Les réponses sont enregistrées. La correction complète sera consolidée au retour du PC.':'Résultat conservé sur B-EDGE et synchronisé automatiquement.')+'</p><button class="primary" id="backHome">Retour à l\'accueil</button></div>';
    q('#timer').textContent='Terminé';q('#backHome').onclick=()=>{localStorage.removeItem('exc_edge_run');run=null;setView('home')}
  }
  function renderQuiz(){
    const x=current();if(!run||!x){setView('home');return}currentView='quiz';
    qa('.view').forEach(v=>v.classList.remove('active'));q('#v-quiz').classList.add('active');qa('#nav button').forEach(b=>b.classList.remove('active'));
    ensureQuestionClock();paintTimer();
    const selected=run.answers[x.id],answered=selected!=null,mock=String(run.mode||'').toLowerCase()==='mock';
    q('#v-quiz').innerHTML='<div class="quizbox"><div class="card"><div class="row"><span class="pill">Question '+(run.i+1)+' / '+run.ids.length+'</span><b>'+(mock?'Examen':run.score+' pts')+'</b></div><div class="question">'+esc(x.prompt)+'</div>'+
      (x.choices||[]).map((c,i)=>'<button class="ans '+(answered&&!mock?(i===Number(x.answer)?'good':i===Number(selected)?'bad':''):'')+'" '+(answered?'disabled ':'')+'data-a="'+i+'">'+esc(c)+'</button>').join('')+
      (answered?(mock?'<p class="muted">Réponse enregistrée. Correction masquée jusqu\'à la fin.</p>':'<p class="muted">'+esc(x.explanation||'')+'</p>')+'<button class="primary full" id="next">'+(run.i<run.ids.length-1?'Question suivante':'Terminer')+'</button>':'')+
      '</div><button class="ghost full" id="leaveQuiz">← Retour à la plateforme</button></div>';
    if(!answered)qa('[data-a]').forEach(b=>b.onclick=()=>answer(Number(b.dataset.a),false));
    q('#next')?.addEventListener('click',nextQuestion);q('#leaveQuiz').onclick=()=>setView('home')
  }

  qa('#nav [data-view]').forEach(b=>b.onclick=()=>setView(b.dataset.view));
  document.addEventListener('click',e=>{const b=e.target.closest('[data-go]');if(b)setView(b.dataset.go)});
  setInterval(()=>{if(currentView!=='quiz'||!run||timingBusy)return;const x=current();if(!x||run.answers[x.id]!=null){paintTimer();return}paintTimer();if(questionMsLeft()<=0)void answer(-1,true)},250);
  setInterval(async()=>{if(recovering)return;try{const r=await fetch('/api/status',{cache:'no-store',signal:AbortSignal.timeout(1800)});if(!r.ok)throw new Error();q('#net').textContent='nœud local · connecté';void flushOutbox()}catch{void recoverRoute()}},12000);

  try{
    const r=await fetch('/api/offline-pack',{cache:'no-store'});if(!r.ok)throw new Error('snapshot indisponible');pack=await r.json();
  }catch(e){if(await recoverRoute())return;throw e}
  localStorage.setItem('exc_edge_last_ip',location.hostname);
  const saved=localStorage.getItem('exc_edge_run');if(saved){try{run=JSON.parse(saved)}catch{}}
  await flushOutbox();q('#net').textContent='nœud local · connecté';setView('home')
})().catch(e=>{
  document.querySelector('.wrap').innerHTML='<div class="card"><h2>Continuité locale indisponible</h2><p class="muted">'+String(e&&e.message||e)+'</p></div>'
});
</script>
</body>
</html>
""";
    }

    private static String cookieValue(String header, String name) {
        if (header == null) return "";
        for (String p : header.split(";")) {
            int i = p.indexOf('=');
            if (i > 0 && name.equals(p.substring(0, i).trim())) return p.substring(i + 1).trim();
        }
        return "";
    }

    private String randomToken() {
        byte[] b = new byte[32];
        random.nextBytes(b);
        return Base64.encodeToString(b, Base64.NO_WRAP | Base64.URL_SAFE | Base64.NO_PADDING);
    }

    private static byte[] gunzip(byte[] gz, int maxBytes) throws Exception {
        try (GZIPInputStream in = new GZIPInputStream(new ByteArrayInputStream(gz));
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) >= 0) {
                if (out.size() + n > maxBytes) throw new IllegalArgumentException("snapshot_uncompressed_too_large");
                out.write(buf, 0, n);
            }
            return out.toByteArray();
        }
    }

    private static void atomicWrite(File target, byte[] data) throws Exception {
        File tmp = new File(target.getParentFile(), target.getName() + ".tmp");
        try (FileOutputStream out = new FileOutputStream(tmp)) {
            out.write(data);
            out.getFD().sync();
        }
        if (target.exists() && !target.delete()) throw new IllegalStateException("replace_delete_failed");
        if (!tmp.renameTo(target)) throw new IllegalStateException("replace_rename_failed");
    }

    private static byte[] readAll(File file, int max) throws Exception {
        if (file.length() > max) throw new IllegalArgumentException("file_too_large");
        try (FileInputStream in = new FileInputStream(file); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buf = new byte[8192]; int n;
            while ((n = in.read(buf)) >= 0) { if (out.size() + n > max) throw new IllegalArgumentException("file_too_large"); out.write(buf, 0, n); }
            return out.toByteArray();
        }
    }

    private static Map<String,String> readHeaders(InputStream in) throws Exception {
        Map<String,String> h = new HashMap<>();
        int total = 0;
        while (true) {
            String line = readLine(in, 8192);
            if (line == null || line.isEmpty()) break;
            total += line.length();
            if (total > 16_384) throw new IllegalArgumentException("headers_too_large");
            int i = line.indexOf(':');
            if (i > 0) h.put(line.substring(0, i).trim().toLowerCase(Locale.ROOT), line.substring(i + 1).trim());
        }
        return h;
    }

    private static JSONObject readJsonBody(InputStream in, Map<String,String> headers, int max) throws Exception {
        int len;
        try { len = Integer.parseInt(headers.getOrDefault("content-length", "0")); } catch (Exception e) { len = 0; }
        if (len <= 0 || len > max) throw new IllegalArgumentException("body_size_invalid");
        byte[] b = new byte[len];
        int off = 0;
        while (off < len) { int n = in.read(b, off, len - off); if (n < 0) throw new IllegalArgumentException("unexpected_eof"); off += n; }
        return new JSONObject(new String(b, StandardCharsets.UTF_8));
    }

    private static String cleanPath(String raw) {
        String p = raw == null ? "/" : raw;
        int q = p.indexOf('?'); if (q >= 0) p = p.substring(0, q);
        return p.startsWith("/") ? p : "/" + p;
    }

    private static String readLine(InputStream in, int max) throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        int prev = -1;
        while (out.size() < max) {
            int c = in.read();
            if (c < 0) break;
            if (prev == '\r' && c == '\n') {
                byte[] b = out.toByteArray();
                int n = Math.max(0, b.length - 1);
                return new String(b, 0, n, StandardCharsets.UTF_8);
            }
            out.write(c); prev = c;
        }
        if (out.size() == 0) return null;
        return new String(out.toByteArray(), StandardCharsets.UTF_8).trim();
    }

    private static void writeRedirect(OutputStream out, String location) throws Exception {
        byte[] body = new byte[0];
        String h = "HTTP/1.1 302 Found\r\nLocation: " + location + "\r\nCache-Control: no-store\r\nConnection: close\r\nContent-Length: 0\r\n\r\n";
        out.write(h.getBytes(StandardCharsets.US_ASCII));
        out.write(body); out.flush();
    }

    private static void writeJson(OutputStream out, int status, JSONObject body) throws Exception {
        writeJson(out, status, body, new HashMap<>());
    }

    private static void writeJson(OutputStream out, int status, JSONObject body, Map<String,String> extra) throws Exception {
        writeBytes(out, status, "application/json; charset=utf-8", body.toString().getBytes(StandardCharsets.UTF_8), extra);
    }

    private static void writeText(OutputStream out, int status, String type, String body) throws Exception {
        writeBytes(out, status, type, body.getBytes(StandardCharsets.UTF_8));
    }

    private static void writeText(OutputStream out, int status, String type, String body, Map<String,String> extra) throws Exception {
        writeBytes(out, status, type, body.getBytes(StandardCharsets.UTF_8), extra);
    }

    private static void writeBytes(OutputStream out, int status, String type, byte[] body) throws Exception {
        writeBytes(out, status, type, body, new HashMap<>());
    }

    private static void writeBytes(OutputStream out, int status, String type, byte[] body, Map<String,String> extra) throws Exception {
        String reason = status == 200 ? "OK" : status == 202 ? "Accepted" : status == 302 ? "Found" : status == 400 ? "Bad Request" : status == 401 ? "Unauthorized" : status == 403 ? "Forbidden" : status == 404 ? "Not Found" : status == 410 ? "Gone" : status == 503 ? "Unavailable" : "OK";
        String cacheControl = extra.containsKey("Cache-Control") ? extra.get("Cache-Control") : "no-store";
        StringBuilder h = new StringBuilder("HTTP/1.1 ").append(status).append(' ').append(reason).append("\r\n")
                .append("Content-Type: ").append(type).append("\r\n")
                .append("Content-Length: ").append(body.length).append("\r\n")
                .append("Cache-Control: ").append(cacheControl).append("\r\n")
                .append("X-Content-Type-Options: nosniff\r\n")
                .append("Referrer-Policy: no-referrer\r\n")
                .append("Connection: close\r\n");
        for (Map.Entry<String,String> e : extra.entrySet()) {
            if ("Cache-Control".equalsIgnoreCase(e.getKey())) continue;
            h.append(e.getKey()).append(": ").append(e.getValue()).append("\r\n");
        }
        h.append("\r\n");
        out.write(h.toString().getBytes(StandardCharsets.US_ASCII));
        out.write(body);
        out.flush();
    }

    private static String sha256(byte[] b) {
        try {
            byte[] d = MessageDigest.getInstance("SHA-256").digest(b);
            StringBuilder s = new StringBuilder(64);
            for (byte x : d) s.append(String.format(Locale.ROOT, "%02x", x & 0xff));
            return s.toString();
        } catch (Exception e) { return ""; }
    }

    private static JSONObject json(Object... kv) {
        JSONObject o = new JSONObject();
        try { for (int i = 0; i + 1 < kv.length; i += 2) o.put(String.valueOf(kv[i]), kv[i + 1]); }
        catch (Exception ignored) {}
        return o;
    }
}
