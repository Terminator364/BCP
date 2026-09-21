package com.blessing.bcpedge;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;

import androidx.annotation.Nullable;
import androidx.core.app.ServiceCompat;

import com.blessing.bcpedge.storage.EdgeDatabase;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.Semaphore;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/**
 * Dedicated-phone BCP node.
 *
 * One bounded local socket exposes:
 * - authenticated HTTPS CONNECT relay restricted to api.telegram.org:443;
 * - a tiny authenticated local BCP Edge API for status, sync and durable job admission.
 *
 * Security boundary:
 * - LAN API/private relay clients authenticate with the already-paired BCP bearer credential;
 * - public endpoints expose capability/health only;
 * - Telegram TLS remains end-to-end between the PC worker and api.telegram.org;
 * - no arbitrary proxy target and no arbitrary shell execution is exposed.
 */
public final class EdgeRelayService extends Service {
    private static final String CHANNEL_ID = "bcp_edge_relay";
    private static final int NOTIFICATION_ID = 6401;
    private static final String PREFS = "bcp_edge_relay_state";

    private final ExecutorService io = Executors.newCachedThreadPool();
    private final ScheduledExecutorService registration = Executors.newSingleThreadScheduledExecutor();
    private final Semaphore connectionSlots = new Semaphore(EdgeRelayPolicy.MAX_CONNECTIONS);
    private volatile boolean stopping = false;
    private volatile ServerSocket serverSocket;
    private EdgePresenceAdvertiser presence;
    private volatile JSONObject presenceState = new JSONObject();

    @Override public void onCreate() {
        super.onCreate();
        createChannel();
        Notification n = buildNotification("Serveur Edge/API local actif");
        if (Build.VERSION.SDK_INT >= 34) {
            int types = ServiceInfo.FOREGROUND_SERVICE_TYPE_REMOTE_MESSAGING
                    | ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE;
            ServiceCompat.startForeground(this, NOTIFICATION_ID, n, types);
        } else {
            startForeground(NOTIFICATION_ID, n);
        }

        presence = new EdgePresenceAdvertiser(this);
        try {
            presenceState = presence.start(
                    EdgeRelayPolicy.RELAY_PORT,
                    new BcpClient(this).getEdgeVersion());
        } catch (Throwable ignored) {}

        io.submit(this::serveLoop);
        registration.scheduleWithFixedDelay(() -> {
            try {
                BcpClient client = new BcpClient(EdgeRelayService.this);
                client.registerEdgeRelay();
                client.recordEvent("EDGE_SERVER_HEARTBEAT", nodeSummary().toString());
            } catch (Throwable ignored) {}
        }, 1, 120, TimeUnit.SECONDS);
        mark("STARTING", "");
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null) {
            String reason = intent.getStringExtra("boot_reason");
            if (reason != null && !reason.isEmpty()) {
                try { new BcpClient(this).recordEvent("EDGE_SERVER_START_REASON", reason); }
                catch (Throwable ignored) {}
            }
        }
        return START_STICKY;
    }

    @Override public void onDestroy() {
        stopping = true;
        try { if (serverSocket != null) serverSocket.close(); } catch (Exception ignored) {}
        try { if (presence != null) presence.stop(); } catch (Exception ignored) {}
        registration.shutdownNow();
        io.shutdownNow();
        mark("STOPPED", "");
        super.onDestroy();
    }

    @Nullable @Override public IBinder onBind(Intent intent) { return null; }

    private void serveLoop() {
        try (ServerSocket server = new ServerSocket()) {
            server.setReuseAddress(true);
            server.bind(new InetSocketAddress("0.0.0.0", EdgeRelayPolicy.RELAY_PORT), 8);
            serverSocket = server;
            mark("LISTENING", "port=" + EdgeRelayPolicy.RELAY_PORT);
            while (!stopping) {
                Socket client = server.accept();
                if (!connectionSlots.tryAcquire()) {
                    try {
                        writeAscii(client.getOutputStream(),
                                "HTTP/1.1 503 Busy\r\nConnection: close\r\n\r\n");
                    } catch (Exception ignored) {}
                    try { client.close(); } catch (Exception ignored) {}
                    continue;
                }
                io.submit(() -> {
                    try { handle(client); }
                    finally {
                        connectionSlots.release();
                        try { client.close(); } catch (Exception ignored) {}
                    }
                });
            }
        } catch (Exception e) {
            if (!stopping) mark("FAILED", e.getClass().getSimpleName());
        }
    }

    private void handle(Socket client) {
        try {
            client.setSoTimeout(EdgeRelayPolicy.TUNNEL_IDLE_TIMEOUT_MS);
            InputStream cin = client.getInputStream();
            OutputStream cout = client.getOutputStream();

            String requestLine = readLine(cin, 2048);
            if (requestLine == null) return;
            String[] parts = requestLine.trim().split("\\s+");
            if (parts.length != 3) {
                writeAscii(cout, "HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n");
                return;
            }
            Map<String,String> headers = readHeaders(cin, requestLine.length());
            String method = parts[0].toUpperCase(Locale.ROOT);
            if ("CONNECT".equals(method)) {
                handleConnect(client, cin, cout, parts[1], headers);
                return;
            }
            handleApi(cin, cout, method, cleanPath(parts[1]), headers);
        } catch (Exception e) {
            mark("REQUEST_ERROR", e.getClass().getSimpleName());
        }
    }

    private void handleConnect(Socket client, InputStream cin, OutputStream cout,
                               String target, Map<String,String> headers) {
        Socket upstream = null;
        try {
            int colon = target.lastIndexOf(':');
            if (colon <= 0) {
                writeAscii(cout, "HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n");
                return;
            }
            String host = target.substring(0, colon);
            int port;
            try { port = Integer.parseInt(target.substring(colon + 1)); }
            catch (Exception e) { port = -1; }

            String expected = new CredentialStore(this).getToken();
            if (!EdgeRelayPolicy.isValidProxyAuthorization(
                    headers.get("proxy-authorization"), expected)) {
                mark("AUTH_REJECT", client.getInetAddress().getHostAddress());
                writeAscii(cout,
                        "HTTP/1.1 407 Proxy Authentication Required\r\nConnection: close\r\n\r\n");
                return;
            }
            if (!EdgeRelayPolicy.isAllowedConnectTarget(host, port)) {
                mark("TARGET_REJECT", host + ":" + port);
                writeAscii(cout, "HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n");
                return;
            }

            upstream = new Socket();
            upstream.connect(new InetSocketAddress(host, port), EdgeRelayPolicy.CONNECT_TIMEOUT_MS);
            upstream.setSoTimeout(EdgeRelayPolicy.TUNNEL_IDLE_TIMEOUT_MS);
            writeAscii(cout,
                    "HTTP/1.1 200 Connection Established\r\nProxy-Agent: BCP-EDGE\r\n\r\n");
            mark("TUNNEL_OPEN", host);

            final Socket upstreamFinal = upstream;
            Future<?> a = io.submit(() -> pumpQuiet(cin, upstreamFinal));
            Future<?> b = io.submit(() -> pumpQuiet(upstreamFinal, client));
            try { a.get(90, TimeUnit.SECONDS); } catch (Exception ignored) {}
            try { b.get(90, TimeUnit.SECONDS); } catch (Exception ignored) {}
            mark("TUNNEL_CLOSED", host);
        } catch (Exception e) {
            mark("TUNNEL_ERROR", e.getClass().getSimpleName());
        } finally {
            try { if (upstream != null) upstream.close(); } catch (Exception ignored) {}
        }
    }

    private void handleApi(InputStream in, OutputStream out, String method, String path,
                           Map<String,String> headers) throws Exception {
        if (!EdgeRelayPolicy.isAllowedApiPath(method, path)) {
            writeJson(out, 404, json("ok", false, "error", "not_found"));
            return;
        }

        if (!EdgeRelayPolicy.isPublicApiPath(method, path)) {
            String expected = new CredentialStore(this).getToken();
            if (!EdgeRelayPolicy.isValidBearerAuthorization(headers.get("authorization"), expected)) {
                writeJson(out, 401, json("ok", false, "error", "unauthorized"));
                return;
            }
        }

        if ("GET".equals(method) && "/health".equals(path)) {
            JSONObject health = nodeSummary();
            health.put("ok", true);
            writeJson(out, 200, health);
            return;
        }
        if ("GET".equals(method) && "/v1/node/capabilities".equals(path)) {
            JSONObject caps = new JSONObject();
            caps.put("ok", true);
            caps.put("role", "DEDICATED_EDGE_API_SERVER");
            caps.put("local_api", true);
            caps.put("durable_queue", true);
            caps.put("universal_event_ledger", true);
            caps.put("universal_event_ledger_mode", "APPEND_ONLY_LOCAL_CHRONICLE");
            caps.put("mission_step_envelope_v1", true);
            caps.put("provider_degraded_resume", true);
            caps.put("mission_authority", "DURABLE_BCP_STATE_NOT_CHAT_UI");
            caps.put("local_allowlisted_executor", true);
            caps.put("local_executor_kinds", new org.json.JSONArray()
                    .put("LOCAL_CONTEXT_SNAPSHOT")
                    .put("LOCAL_HEALTH_SNAPSHOT")
                    .put("LOCAL_QUEUE_SUMMARY")
                    .put("LOCAL_MEMORY_COMPACT"));
            caps.put("content_addressed_private_cache", true);
            caps.put("store_and_forward", true);
            caps.put("telegram_https_connect_relay", true);
            caps.put("nsd_presence", true);
            caps.put("wifi_direct_presence", true);
            caps.put("ble_presence", true);
            caps.put("arbitrary_proxy", false);
            caps.put("arbitrary_shell", false);
            caps.put("version", new BcpClient(this).getEdgeVersion());
            writeJson(out, 200, caps);
            return;
        }
        if ("GET".equals(method) && "/v1/node/status".equals(path)) {
            writeJson(out, 200, nodeStatus());
            return;
        }
        if ("GET".equals(method) && "/v1/node/context".equals(path)) {
            writeJson(out, 200, new BcpClient(this).localContextPack());
            return;
        }
        if ("GET".equals(method) && "/v1/node/events".equals(path)) {
            writeJson(out, 200, new BcpClient(this).localEventTail(100));
            return;
        }
        if ("GET".equals(method) && "/v1/node/mission-steps".equals(path)) {
            writeJson(out, 200, new BcpClient(this).localMissionSteps(50, true));
            return;
        }
        if ("POST".equals(method) && "/v1/node/events".equals(path)) {
            JSONObject body = readJsonBody(in, headers);
            String eventType = body.optString("event_type", "");
            JSONObject payload = body.optJSONObject("payload");
            if (payload == null) payload = new JSONObject();
            String truth = body.optString("truth_status", "OBSERVED");
            String idem = body.optString("idempotency_key", "");
            JSONObject receipt = new BcpClient(this).appendLocalEvent(
                    eventType, payload, truth, idem);
            writeJson(out, receipt.optBoolean("ok", false) ? 202 : 200, receipt);
            return;
        }
        if ("POST".equals(method) && "/v1/node/mission-steps".equals(path)) {
            JSONObject body = readJsonBody(in, headers);
            JSONObject receipt = new BcpClient(this).upsertMissionStep(body);
            writeJson(out, receipt.optBoolean("ok", false) ? 202 : 400, receipt);
            return;
        }
        if ("POST".equals(method) && "/v1/node/mission-steps/state".equals(path)) {
            JSONObject body = readJsonBody(in, headers);
            JSONObject receipt = new BcpClient(this).updateMissionStepState(body);
            writeJson(out, receipt.optBoolean("ok", false) ? 200 : 404, receipt);
            return;
        }
        if ("POST".equals(method) && "/v1/node/sync".equals(path)) {
            JSONObject result = new BcpClient(this).syncOrchestrationState();
            result.put("ok", true);
            result.put("node", nodeSummary());
            writeJson(out, 200, result);
            return;
        }
        if ("POST".equals(method) && "/v1/node/jobs".equals(path)) {
            JSONObject body = readJsonBody(in, headers);
            String kind = body.optString("kind", "").trim();
            if (kind.isEmpty() || kind.length() > 80) {
                writeJson(out, 400, json("ok", false, "error", "invalid_kind"));
                return;
            }
            JSONObject payload = body.optJSONObject("payload");
            if (payload == null) payload = new JSONObject();
            boolean requiresPc = body.optBoolean("requires_pc", true);
            JSONObject queued = new BcpClient(this).queueJob(kind, payload, requiresPc);
            queued.put("ok", queued.optBoolean("queued", false)
                    || "QUEUED".equals(queued.optString("result", ""))
                    || "ALREADY_QUEUED".equals(queued.optString("result", "")));
            writeJson(out, 202, queued);
        }
    }

    private JSONObject nodeStatus() {
        JSONObject out = nodeSummary();
        try {
            BcpClient client = new BcpClient(this);
            out.put("ok", true);
            out.put("project", client.getProject());
            out.put("paired", !client.getToken().isEmpty());
            out.put("sentinel", client.sentinelStatus());
            out.put("permissions", EdgePermissionManager.status(this));
            out.put("content_store", client.contentStoreStatus());
            out.put("network", EdgeNetworkState.snapshot(this));
            out.put("resources", EdgeResourceGovernor.snapshot(this));
            out.put("pending_jobs",
                    EdgeDatabase.get(this).edgeDao().countPendingJobs());
            out.put("local_executor", "ALLOWLISTED_ACTIVE");
            out.put("presence", presenceState);
            SharedPreferences p = getSharedPreferences(PREFS, MODE_PRIVATE);
            out.put("listener_state", p.getString("state", ""));
            out.put("listener_detail", p.getString("detail", ""));
            out.put("listener_updated_at", p.getLong("updated_at", 0L));
        } catch (Exception ignored) {}
        return out;
    }

    private JSONObject nodeSummary() {
        JSONObject out = new JSONObject();
        try {
            out.put("node", "B-EDGE");
            out.put("role", "DEDICATED_EDGE_API_SERVER");
            out.put("version", new BcpClient(this).getEdgeVersion());
            out.put("port", EdgeRelayPolicy.RELAY_PORT);
            out.put("server_mode_enabled", EdgePermissionManager.isServerModeEnabled(this));
            out.put("timestamp_ms", System.currentTimeMillis());
        } catch (Exception ignored) {}
        return out;
    }

    private static Map<String,String> readHeaders(InputStream in, int initialBytes) throws Exception {
        Map<String,String> headers = new HashMap<>();
        int headerBytes = initialBytes;
        while (true) {
            String line = readLine(in, 4096);
            if (line == null) break;
            headerBytes += line.length();
            if (headerBytes > EdgeRelayPolicy.HEADER_MAX_BYTES) {
                throw new IllegalArgumentException("headers_too_large");
            }
            if (line.isEmpty()) break;
            int colon = line.indexOf(':');
            if (colon > 0) {
                headers.put(
                        line.substring(0, colon).trim().toLowerCase(Locale.ROOT),
                        line.substring(colon + 1).trim());
            }
        }
        return headers;
    }

    private static JSONObject readJsonBody(InputStream in, Map<String,String> headers) throws Exception {
        int len = 0;
        try { len = Integer.parseInt(headers.getOrDefault("content-length", "0")); }
        catch (Exception ignored) {}
        if (len < 0 || len > EdgeRelayPolicy.API_BODY_MAX_BYTES) {
            throw new IllegalArgumentException("body_too_large");
        }
        if (len == 0) return new JSONObject();
        byte[] body = readExactly(in, len);
        return new JSONObject(new String(body, StandardCharsets.UTF_8));
    }

    private static byte[] readExactly(InputStream in, int length) throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream(length);
        byte[] buf = new byte[Math.min(4096, Math.max(1, length))];
        int remaining = length;
        while (remaining > 0) {
            int n = in.read(buf, 0, Math.min(buf.length, remaining));
            if (n < 0) throw new IllegalArgumentException("unexpected_eof");
            out.write(buf, 0, n);
            remaining -= n;
        }
        return out.toByteArray();
    }

    private static String cleanPath(String raw) {
        if (raw == null || raw.isEmpty()) return "/";
        int q = raw.indexOf('?');
        return q >= 0 ? raw.substring(0, q) : raw;
    }

    private static JSONObject json(Object... pairs) {
        JSONObject out = new JSONObject();
        try {
            for (int i = 0; i + 1 < pairs.length; i += 2) {
                out.put(String.valueOf(pairs[i]), pairs[i + 1]);
            }
        } catch (Exception ignored) {}
        return out;
    }

    private static void writeJson(OutputStream out, int code, JSONObject obj) throws Exception {
        byte[] body = obj.toString().getBytes(StandardCharsets.UTF_8);
        String reason = code == 200 ? "OK"
                : code == 202 ? "Accepted"
                : code == 400 ? "Bad Request"
                : code == 401 ? "Unauthorized"
                : code == 404 ? "Not Found"
                : "Error";
        String head = "HTTP/1.1 " + code + " " + reason + "\r\n"
                + "Content-Type: application/json; charset=utf-8\r\n"
                + "Content-Length: " + body.length + "\r\n"
                + "Connection: close\r\n"
                + "Cache-Control: no-store\r\n\r\n";
        out.write(head.getBytes(StandardCharsets.US_ASCII));
        out.write(body);
        out.flush();
    }

    private static void pumpQuiet(InputStream in, Socket outSocket) {
        try {
            OutputStream out = outSocket.getOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) >= 0) {
                out.write(buf, 0, n);
                out.flush();
            }
            try { outSocket.shutdownOutput(); } catch (Exception ignored) {}
        } catch (Exception ignored) {}
    }

    private static void pumpQuiet(Socket inSocket, Socket outSocket) {
        try {
            InputStream in = inSocket.getInputStream();
            OutputStream out = outSocket.getOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) >= 0) {
                out.write(buf, 0, n);
                out.flush();
            }
            try { outSocket.shutdownOutput(); } catch (Exception ignored) {}
        } catch (Exception ignored) {}
    }

    private static String readLine(InputStream in, int max) throws Exception {
        byte[] buf = new byte[max];
        int used = 0;
        while (used < max) {
            int b = in.read();
            if (b < 0) return used == 0 ? null
                    : new String(buf, 0, used, StandardCharsets.US_ASCII).trim();
            if (b == '\n') break;
            if (b != '\r') buf[used++] = (byte)b;
        }
        if (used >= max) throw new IllegalArgumentException("line_too_long");
        return new String(buf, 0, used, StandardCharsets.US_ASCII);
    }

    private static void writeAscii(OutputStream out, String value) throws Exception {
        out.write(value.getBytes(StandardCharsets.US_ASCII));
        out.flush();
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT < 26) return;
        NotificationChannel ch = new NotificationChannel(
                CHANNEL_ID, "BCP Edge server", NotificationManager.IMPORTANCE_LOW);
        ch.setDescription("Serveur local BCP, reprise, file durable et relais de communication.");
        NotificationManager nm = getSystemService(NotificationManager.class);
        if (nm != null) nm.createNotificationChannel(ch);
    }

    private Notification buildNotification(String text) {
        Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);
        return b.setContentTitle("BCP Edge · serveur dédié")
                .setContentText(text)
                .setSmallIcon(android.R.drawable.stat_sys_upload_done)
                .setOngoing(true)
                .build();
    }

    private void mark(String state, String detail) {
        SharedPreferences.Editor e = getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                .putString("state", state)
                .putString("detail", detail == null ? "" : detail)
                .putLong("updated_at", System.currentTimeMillis());
        if ("LISTENING".equals(state)) e.putInt("port", EdgeRelayPolicy.RELAY_PORT);
        e.apply();
    }
}
