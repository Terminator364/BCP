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
 * First-class BCP phone node.
 *
 * One bounded foreground service exposes:
 * - authenticated local Edge API for health/status/jobs/reconciliation;
 * - durable Room/WorkManager orchestration through EdgeNodeApi;
 * - allowlisted HTTPS CONNECT relay for the tiny Telegram control plane.
 *
 * The phone is infrastructure, not a passive client. Bulk Internet access is
 * intentionally not exposed: the PC can reach the phone node locally while
 * Windows remains off the general Internet path.
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
    private EdgeNodeApi edgeApi;

    @Override public void onCreate() {
        super.onCreate();
        edgeApi = new EdgeNodeApi(this);
        createChannel();
        Notification n = buildNotification("Serveur Edge local + relais sécurisé actifs");
        if (Build.VERSION.SDK_INT >= 34) {
            ServiceCompat.startForeground(
                    this,
                    NOTIFICATION_ID,
                    n,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_REMOTE_MESSAGING);
        } else {
            startForeground(NOTIFICATION_ID, n);
        }
        io.submit(this::serveLoop);
        registration.scheduleWithFixedDelay(() -> {
            try {
                new BcpClient(EdgeRelayService.this).registerEdgeRelay();
            } catch (Throwable ignored) {}
        }, 1, 120, TimeUnit.SECONDS);
        mark("STARTING", "");
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        return START_STICKY;
    }

    @Override public void onDestroy() {
        stopping = true;
        try { if (serverSocket != null) serverSocket.close(); } catch (Exception ignored) {}
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
            mark("LISTENING", "port=" + EdgeRelayPolicy.RELAY_PORT + ",role=PHONE_PRIMARY_EDGE_SERVER");
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
        Socket upstream = null;
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

            Map<String,String> headers = new HashMap<>();
            int headerBytes = requestLine.length();
            while (true) {
                String line = readLine(cin, 4096);
                if (line == null) return;
                headerBytes += line.length();
                if (headerBytes > 16_384) {
                    writeAscii(cout,
                            "HTTP/1.1 431 Request Header Fields Too Large\r\nConnection: close\r\n\r\n");
                    return;
                }
                if (line.isEmpty()) break;
                int colon = line.indexOf(':');
                if (colon > 0) {
                    headers.put(
                            line.substring(0, colon).trim().toLowerCase(Locale.ROOT),
                            line.substring(colon + 1).trim());
                }
            }

            String method = parts[0].toUpperCase(Locale.ROOT);
            String target = parts[1];

            if (!"CONNECT".equals(method)) {
                if (!"GET".equals(method) && !"POST".equals(method)) {
                    writeAscii(cout,
                            "HTTP/1.1 405 Method Not Allowed\r\nConnection: close\r\n\r\n");
                    return;
                }
                int contentLength = parseContentLength(headers.get("content-length"));
                if (contentLength < 0 || contentLength > EdgeNodeApi.MAX_BODY_BYTES) {
                    writeAscii(cout,
                            "HTTP/1.1 413 Payload Too Large\r\nConnection: close\r\n\r\n");
                    return;
                }
                String body = contentLength == 0 ? "" :
                        new String(readExactly(cin, contentLength), StandardCharsets.UTF_8);
                EdgeNodeApi.Response response = edgeApi.handle(method, target, headers, body);
                writeJsonResponse(cout, response.status, response.body);
                mark("EDGE_API", method + " " + target + " -> " + response.status);
                return;
            }

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
            mark("CONNECTION_ERROR", e.getClass().getSimpleName());
        } finally {
            try { if (upstream != null) upstream.close(); } catch (Exception ignored) {}
        }
    }

    private static int parseContentLength(String raw) {
        if (raw == null || raw.trim().isEmpty()) return 0;
        try { return Integer.parseInt(raw.trim()); }
        catch (Exception e) { return -1; }
    }

    private static byte[] readExactly(InputStream in, int length) throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream(length);
        byte[] buf = new byte[Math.min(8192, Math.max(1, length))];
        int remaining = length;
        while (remaining > 0) {
            int n = in.read(buf, 0, Math.min(buf.length, remaining));
            if (n < 0) throw new java.io.EOFException("request_body_truncated");
            out.write(buf, 0, n);
            remaining -= n;
        }
        return out.toByteArray();
    }

    private static void writeJsonResponse(OutputStream out, int status, String body) throws Exception {
        String reason = status == 200 ? "OK" :
                status == 202 ? "Accepted" :
                status == 400 ? "Bad Request" :
                status == 401 ? "Unauthorized" :
                status == 404 ? "Not Found" :
                status == 413 ? "Payload Too Large" : "Error";
        byte[] payload = (body == null ? "{}" : body).getBytes(StandardCharsets.UTF_8);
        String head = "HTTP/1.1 " + status + " " + reason + "\r\n" +
                "Content-Type: application/json; charset=utf-8\r\n" +
                "Content-Length: " + payload.length + "\r\n" +
                "Cache-Control: no-store\r\n" +
                "Connection: close\r\n\r\n";
        out.write(head.getBytes(StandardCharsets.US_ASCII));
        out.write(payload);
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
            if (b < 0) return used == 0 ? null :
                    new String(buf, 0, used, StandardCharsets.US_ASCII).trim();
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
                CHANNEL_ID, "BCP Phone Server", NotificationManager.IMPORTANCE_LOW);
        ch.setDescription("Serveur Edge local BCP, continuité et relais de contrôle léger.");
        NotificationManager nm = getSystemService(NotificationManager.class);
        if (nm != null) nm.createNotificationChannel(ch);
    }

    private Notification buildNotification(String text) {
        Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);
        return b.setContentTitle("BCP Phone Server")
                .setContentText(text)
                .setSmallIcon(android.R.drawable.stat_sys_upload_done)
                .setOngoing(true)
                .build();
    }

    private void mark(String state, String detail) {
        SharedPreferences.Editor e = getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                .putString("state", state)
                .putString("detail", detail == null ? "" : detail)
                .putLong("updated_at", System.currentTimeMillis())
                .putString("role", "PHONE_PRIMARY_EDGE_SERVER");
        if ("LISTENING".equals(state)) e.putInt("port", EdgeRelayPolicy.RELAY_PORT);
        e.apply();
    }
}
