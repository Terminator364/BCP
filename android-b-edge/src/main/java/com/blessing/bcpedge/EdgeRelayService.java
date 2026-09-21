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

import org.json.JSONObject;

import androidx.annotation.Nullable;
import androidx.core.app.ServiceCompat;

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
 * Dedicated-node, low-data HTTPS CONNECT relay.
 *
 * Security boundary:
 * - LAN clients must authenticate with the already-paired BCP bearer credential.
 * - only api.telegram.org:443 is allowed;
 * - TLS stays end-to-end between the PC Telegram worker and Telegram, so B-EDGE
 *   never receives the bot token or message payload in plaintext.
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
    private volatile EdgeNodeServer nodeServer;

    @Override public void onCreate() {
        super.onCreate();
        createChannel();
        Notification n = buildNotification("Nœud serveur B-EDGE actif · relais + file durable");
        if (Build.VERSION.SDK_INT >= 34) {
            ServiceCompat.startForeground(
                    this,
                    NOTIFICATION_ID,
                    n,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_REMOTE_MESSAGING
                            | ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE);
        } else {
            startForeground(NOTIFICATION_ID, n);
        }
        nodeServer = new EdgeNodeServer(this);
        nodeServer.start();
        io.submit(this::serveLoop);
        registration.scheduleWithFixedDelay(() -> {
            try {
                BcpClient client = new BcpClient(EdgeRelayService.this);
                JSONObject relay = client.registerEdgeRelay();
                boolean pcReachable = relay.optBoolean("ok", false);
                client.observePcSentinel(pcReachable);
                EdgeLocalExecutor.drain(EdgeRelayService.this, client);
                new EdgeCommunicationWatchdog(EdgeRelayService.this).tick(client, pcReachable);
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
        try { if (nodeServer != null) nodeServer.stop(); } catch (Exception ignored) {}
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
                        writeAscii(client.getOutputStream(), "HTTP/1.1 503 Busy\r\nConnection: close\r\n\r\n");
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
            if (parts.length != 3 || !"CONNECT".equalsIgnoreCase(parts[0])) {
                writeAscii(cout, "HTTP/1.1 405 Method Not Allowed\r\nConnection: close\r\n\r\n");
                return;
            }

            Map<String,String> headers = new HashMap<>();
            int headerBytes = requestLine.length();
            while (true) {
                String line = readLine(cin, 4096);
                if (line == null) return;
                headerBytes += line.length();
                if (headerBytes > 16_384) {
                    writeAscii(cout, "HTTP/1.1 431 Request Header Fields Too Large\r\nConnection: close\r\n\r\n");
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

            String target = parts[1];
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
            if (!EdgeRelayPolicy.isValidProxyAuthorization(headers.get("proxy-authorization"), expected)) {
                mark("AUTH_REJECT", client.getInetAddress().getHostAddress());
                writeAscii(cout, "HTTP/1.1 407 Proxy Authentication Required\r\nConnection: close\r\n\r\n");
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
            writeAscii(cout, "HTTP/1.1 200 Connection Established\r\nProxy-Agent: BCP-EDGE\r\n\r\n");
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
            if (b < 0) return used == 0 ? null : new String(buf, 0, used, StandardCharsets.US_ASCII).trim();
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
        ch.setDescription("Nœud serveur local BCP : file durable, relais Telegram et continuité PC/téléphone.");
        NotificationManager nm = getSystemService(NotificationManager.class);
        if (nm != null) nm.createNotificationChannel(ch);
    }

    private Notification buildNotification(String text) {
        Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);
        return b.setContentTitle("BCP Edge")
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
