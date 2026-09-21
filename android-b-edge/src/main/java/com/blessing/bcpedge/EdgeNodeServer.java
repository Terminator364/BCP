package com.blessing.bcpedge;

import android.content.Context;

import com.blessing.bcpedge.work.EdgeWorkScheduler;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.URLDecoder;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Semaphore;

public final class EdgeNodeServer {
    private final Context context;
    private final ExecutorService io = Executors.newCachedThreadPool();
    private final Semaphore slots = new Semaphore(EdgeNodePolicy.MAX_CONNECTIONS);
    private volatile boolean stopping;
    private volatile ServerSocket serverSocket;

    public EdgeNodeServer(Context context) {
        this.context = context.getApplicationContext();
    }

    public void start() {
        io.submit(this::serveLoop);
    }

    public void stop() {
        stopping = true;
        try { if (serverSocket != null) serverSocket.close(); } catch (Exception ignored) {}
        io.shutdownNow();
    }

    private void serveLoop() {
        try (ServerSocket server = new ServerSocket()) {
            server.setReuseAddress(true);
            server.bind(new InetSocketAddress("0.0.0.0", EdgeNodePolicy.NODE_PORT), 8);
            serverSocket = server;
            new BcpClient(context).recordEvent("EDGE_NODE_LISTENING", "port=" + EdgeNodePolicy.NODE_PORT);
            while (!stopping) {
                Socket client = server.accept();
                if (!slots.tryAcquire()) {
                    try { writeJson(client.getOutputStream(), 503, error("busy")); } catch (Exception ignored) {}
                    try { client.close(); } catch (Exception ignored) {}
                    continue;
                }
                io.submit(() -> {
                    try { handle(client); }
                    finally {
                        slots.release();
                        try { client.close(); } catch (Exception ignored) {}
                    }
                });
            }
        } catch (Exception ex) {
            if (!stopping) new BcpClient(context).recordEvent("EDGE_NODE_FAILED", ex.getClass().getSimpleName());
        }
    }

    private void handle(Socket client) {
        try {
            client.setSoTimeout(EdgeNodePolicy.SOCKET_TIMEOUT_MS);
            InetAddress addr = client.getInetAddress();
            if (addr == null || !(addr.isSiteLocalAddress() || addr.isLoopbackAddress() || addr.isLinkLocalAddress())) {
                writeJson(client.getOutputStream(), 403, error("private_lan_required"));
                return;
            }

            InputStream in = client.getInputStream();
            OutputStream out = client.getOutputStream();
            String request = readLine(in, 2048);
            if (request == null) return;
            String[] p = request.trim().split("\\s+");
            if (p.length != 3) {
                writeJson(out, 400, error("bad_request_line"));
                return;
            }
            String method = p[0].toUpperCase(Locale.ROOT);
            URI target = URI.create(p[1]);
            String path = target.getPath();
            Map<String,String> query = parseQuery(target.getRawQuery());

            Map<String,String> headers = new HashMap<>();
            int headerBytes = request.length();
            while (true) {
                String line = readLine(in, 4096);
                if (line == null) return;
                headerBytes += line.length();
                if (headerBytes > EdgeNodePolicy.MAX_HEADER_BYTES) {
                    writeJson(out, 431, error("headers_too_large"));
                    return;
                }
                if (line.isEmpty()) break;
                int colon = line.indexOf(':');
                if (colon > 0) {
                    headers.put(line.substring(0, colon).trim().toLowerCase(Locale.ROOT),
                            line.substring(colon + 1).trim());
                }
            }

            String token = new CredentialStore(context).getToken();
            if (!EdgeNodePolicy.isValidAuthorization(headers.get("authorization"), token)) {
                writeJson(out, 401, error("unauthorized"));
                return;
            }

            int contentLength = 0;
            try { contentLength = Integer.parseInt(headers.getOrDefault("content-length", "0")); }
            catch (Exception ignored) {}
            if (contentLength < 0 || contentLength > EdgeNodePolicy.MAX_BODY_BYTES) {
                writeJson(out, 413, error("body_too_large"));
                return;
            }
            String rawBody = contentLength == 0 ? "" : readBody(in, contentLength);

            BcpClient clientApi = new BcpClient(context);
            EdgeOrchestrator orchestrator = new EdgeOrchestrator(context);

            if ("GET".equals(method) && "/v1/node/status".equals(path)) {
                JSONObject status = new JSONObject();
                status.put("ok", true);
                status.put("role", "B_EDGE_FULL_NODE");
                status.put("edge_version", clientApi.getEdgeVersion());
                status.put("project", clientApi.getProject());
                status.put("mode", orchestrator.getMode());
                status.put("pending_jobs", orchestrator.pendingCount());
                status.put("network", EdgeConnectivity.snapshot(context));
                status.put("sentinel", clientApi.sentinelStatus());
                status.put("telegram_outbound_configured", new TelegramCredentialStore(context).configured());
                status.put("node_port", EdgeNodePolicy.NODE_PORT);
                writeJson(out, 200, status);
                return;
            }

            if ("GET".equals(method) && "/v1/node/projects".equals(path)) {
                writeJson(out, 200, new JSONObject()
                        .put("ok", true)
                        .put("projects", orchestrator.projectRegistry()));
                return;
            }

            if ("GET".equals(method) && "/v1/node/context".equals(path)) {
                String project = query.getOrDefault("project_id", clientApi.getProject());
                if (!EdgeNodePolicy.isSafeProjectId(project)) {
                    writeJson(out, 400, error("invalid_project_id"));
                    return;
                }
                writeJson(out, 200, new JSONObject()
                        .put("ok", true)
                        .put("project_id", project)
                        .put("context", orchestrator.cachedContext(project)));
                return;
            }

            if ("GET".equals(method) && "/v1/node/memory".equals(path)) {
                String project = query.getOrDefault("project_id", clientApi.getProject());
                if (!EdgeNodePolicy.isSafeProjectId(project)) {
                    writeJson(out, 400, error("invalid_project_id"));
                    return;
                }
                writeJson(out, 200, new JSONObject()
                        .put("ok", true)
                        .put("project_id", project)
                        .put("memory", orchestrator.memorySnapshot(project)));
                return;
            }

            if ("GET".equals(method) && "/v1/node/jobs".equals(path)) {
                String project = query.getOrDefault("project_id", clientApi.getProject());
                if (!EdgeNodePolicy.isSafeProjectId(project)) {
                    writeJson(out, 400, error("invalid_project_id"));
                    return;
                }
                writeJson(out, 200, new JSONObject()
                        .put("ok", true)
                        .put("project_id", project)
                        .put("jobs", orchestrator.pendingJobs(project)));
                return;
            }

            if ("POST".equals(method) && "/v1/node/resume-intent".equals(path)) {
                JSONObject body = rawBody.isEmpty() ? new JSONObject() : new JSONObject(rawBody);
                String project = body.optString("project_id", clientApi.getProject());
                if (!EdgeNodePolicy.isSafeProjectId(project)) {
                    writeJson(out, 400, error("invalid_project_id"));
                    return;
                }
                String idem = headers.getOrDefault("idempotency-key", body.optString("idempotency_key", ""));
                if (!EdgeNodePolicy.isSafeIdempotencyKey(idem)) {
                    writeJson(out, 400, error("invalid_idempotency_key"));
                    return;
                }
                JSONObject payload = new JSONObject()
                        .put("source", "PHONE_NODE")
                        .put("reason", body.optString("reason", "USER_OR_WATCHDOG_RESUME"));
                JSONObject queued = orchestrator.queueJobWithIdempotency(
                        project, "MISSION_RESUME", payload, true, 95, "PC_REQUIRED",
                        new JSONArray(), idem);
                EdgeWorkScheduler.requestImmediate(context, "PHONE_RESUME_INTENT");
                writeJson(out, 202, queued);
                return;
            }

            if ("POST".equals(method) && "/v1/node/enqueue".equals(path)) {
                JSONObject body = rawBody.isEmpty() ? new JSONObject() : new JSONObject(rawBody);
                String project = body.optString("project_id", clientApi.getProject());
                String kind = body.optString("kind", "");
                if (!EdgeNodePolicy.isSafeJobKind(kind)) {
                    writeJson(out, 400, error("invalid_job_kind"));
                    return;
                }
                JSONObject payload = body.optJSONObject("payload");
                if (payload == null) payload = new JSONObject();
                boolean requiresPc = body.optBoolean("requires_pc", false);
                int priority = EdgeNodePolicy.boundedPriority(body.optInt("priority", 70));
                String resourceClass = body.optString("resource_class",
                        EdgePolicy.resourceClass(requiresPc, false, false));
                String idem = headers.getOrDefault("idempotency-key", body.optString("idempotency_key", ""));
                if (!EdgeNodePolicy.isSafeIdempotencyKey(idem)) {
                    writeJson(out, 400, error("invalid_idempotency_key"));
                    return;
                }
                JSONObject queued = orchestrator.queueJobWithIdempotency(
                        project, kind, payload, requiresPc, priority, resourceClass,
                        new JSONArray(), idem);
                EdgeWorkScheduler.requestImmediate(context, "EDGE_NODE_ENQUEUE");
                writeJson(out, 202, queued);
                return;
            }

            if ("POST".equals(method) && "/v1/node/reconcile".equals(path)) {
                EdgeWorkScheduler.requestImmediate(context, "EDGE_NODE_REMOTE_RECONCILE");
                writeJson(out, 202, new JSONObject().put("ok", true).put("state", "QUEUED"));
                return;
            }

            writeJson(out, 404, error("not_found"));
        } catch (Exception ex) {
            try { writeJson(client.getOutputStream(), 500, error("internal_error")); } catch (Exception ignored) {}
        }
    }

    private static Map<String,String> parseQuery(String raw) throws Exception {
        Map<String,String> out = new HashMap<>();
        if (raw == null || raw.isEmpty()) return out;
        for (String part : raw.split("&")) {
            if (part.isEmpty()) continue;
            int eq = part.indexOf('=');
            String k = eq < 0 ? part : part.substring(0, eq);
            String v = eq < 0 ? "" : part.substring(eq + 1);
            out.put(URLDecoder.decode(k, "UTF-8"), URLDecoder.decode(v, "UTF-8"));
        }
        return out;
    }

    private static JSONObject error(String value) {
        JSONObject o = new JSONObject();
        try { o.put("ok", false).put("error", value); } catch (Exception ignored) {}
        return o;
    }

    private static String readLine(InputStream in, int max) throws Exception {
        byte[] buf = new byte[max];
        int used = 0;
        while (used < max) {
            int b = in.read();
            if (b < 0) return used == 0 ? null : new String(buf, 0, used, StandardCharsets.US_ASCII).trim();
            if (b == '\n') break;
            if (b != '\r') buf[used++] = (byte) b;
        }
        if (used >= max) throw new IllegalArgumentException("line_too_long");
        return new String(buf, 0, used, StandardCharsets.US_ASCII);
    }

    private static String readBody(InputStream in, int length) throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream(length);
        byte[] buf = new byte[Math.min(4096, Math.max(1, length))];
        int remaining = length;
        while (remaining > 0) {
            int n = in.read(buf, 0, Math.min(buf.length, remaining));
            if (n < 0) throw new IllegalArgumentException("body_truncated");
            out.write(buf, 0, n);
            remaining -= n;
        }
        return out.toString("UTF-8");
    }

    private static void writeJson(OutputStream out, int code, JSONObject body) throws Exception {
        byte[] payload = body.toString().getBytes(StandardCharsets.UTF_8);
        String reason = code == 200 ? "OK" : code == 202 ? "Accepted" : "Error";
        String head = "HTTP/1.1 " + code + " " + reason + "\r\n"
                + "Content-Type: application/json; charset=utf-8\r\n"
                + "Content-Length: " + payload.length + "\r\n"
                + "Connection: close\r\n\r\n";
        out.write(head.getBytes(StandardCharsets.US_ASCII));
        out.write(payload);
        out.flush();
    }
}
