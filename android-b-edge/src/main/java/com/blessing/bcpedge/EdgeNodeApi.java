package com.blessing.bcpedge;

import android.content.Context;
import android.net.Uri;

import com.blessing.bcpedge.work.EdgeWorkScheduler;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.Map;

public final class EdgeNodeApi {
    public static final int MAX_BODY_BYTES = 64 * 1024;

    private final Context context;
    private final EdgeOrchestrator orchestrator;

    public EdgeNodeApi(Context context) {
        this.context = context.getApplicationContext();
        this.orchestrator = new EdgeOrchestrator(this.context);
    }

    public Response handle(String method, String rawTarget, Map<String,String> headers, String body) {
        try {
            Uri uri = Uri.parse("http://bcp.edge" + (rawTarget == null ? "/" : rawTarget));
            String path = uri.getPath() == null ? "/" : uri.getPath();

            if ("GET".equals(method) && "/health".equals(path)) {
                JSONObject o = new JSONObject();
                o.put("ok", true);
                o.put("service", "BCP-EDGE-NODE");
                o.put("role", "PHONE_PRIMARY_EDGE_SERVER");
                o.put("api_version", 1);
                o.put("relay_port", EdgeRelayPolicy.RELAY_PORT);
                return json(200, o);
            }

            if (!authorized(headers)) {
                return json(401, new JSONObject().put("ok", false).put("error", "UNAUTHORIZED"));
            }

            if ("GET".equals(method) && "/v1/edge/status".equals(path)) {
                JSONObject o = new JSONObject();
                o.put("ok", true);
                o.put("role", "PHONE_PRIMARY_EDGE_SERVER");
                o.put("mode", orchestrator.getMode());
                o.put("pending_jobs", orchestrator.pendingCount());
                o.put("connectivity", EdgeConnectivity.snapshot(context));
                o.put("relay_port", EdgeRelayPolicy.RELAY_PORT);
                o.put("queue_limit", EdgePolicy.boundedQueueLimit());
                o.put("storage", "ROOM_SQLITE_WAL");
                o.put("scheduler", "WORKMANAGER_PLUS_EVENT_CALLBACKS");
                return json(200, o);
            }

            if ("GET".equals(method) && "/v1/edge/capabilities".equals(path)) {
                JSONObject o = EdgeConnectivity.snapshot(context);
                o.put("ok", true);
                o.put("lan_api", true);
                o.put("telegram_connect_relay", true);
                o.put("durable_queue", true);
                o.put("store_and_forward", true);
                o.put("pc_optional_for_edge_jobs", true);
                o.put("transport_policy", new JSONArray()
                        .put("PRIVATE_LAN")
                        .put("WIFI_DIRECT_FIELD_GATED")
                        .put("BLUETOOTH_CONTROL_FIELD_GATED")
                        .put("USB_CONTROL_FIELD_GATED"));
                return json(200, o);
            }

            if ("GET".equals(method) && "/v1/edge/jobs".equals(path)) {
                String project = uri.getQueryParameter("project_id");
                if (project == null || project.trim().isEmpty()) project = "buildhub";
                JSONObject o = new JSONObject();
                o.put("ok", true);
                o.put("project_id", project);
                o.put("jobs", orchestrator.pendingJobs(project));
                return json(200, o);
            }

            if ("POST".equals(method) && "/v1/edge/jobs".equals(path)) {
                JSONObject in = body == null || body.trim().isEmpty()
                        ? new JSONObject() : new JSONObject(body);
                String project = in.optString("project_id", "buildhub");
                String kind = in.optString("kind", "").trim();
                if (kind.isEmpty()) {
                    return json(400, new JSONObject().put("ok", false).put("error", "KIND_REQUIRED"));
                }
                JSONObject payload = in.optJSONObject("payload");
                if (payload == null) payload = new JSONObject();
                boolean requiresPc = in.optBoolean("requires_pc", false);
                int priority = Math.max(0, Math.min(100, in.optInt("priority", 50)));
                String resource = in.optString("resource_class", requiresPc ? "PC_R3" : "EDGE_R1");
                JSONArray deps = in.optJSONArray("dependencies");
                JSONObject queued = orchestrator.queueJob(
                        project, kind, payload, requiresPc, priority, resource, deps);
                queued.put("ok", queued.optBoolean("queued", false) ||
                        "ALREADY_QUEUED".equals(queued.optString("result", "")));
                return json(queued.optBoolean("queued", false) ? 202 : 200, queued);
            }

            if ("POST".equals(method) && "/v1/edge/reconcile".equals(path)) {
                EdgeWorkScheduler.requestImmediate(context, "LOCAL_EDGE_API");
                return json(202, new JSONObject()
                        .put("ok", true)
                        .put("result", "RECONCILE_QUEUED"));
            }

            if ("GET".equals(method) && "/v1/edge/sentinel".equals(path)) {
                String project = uri.getQueryParameter("project_id");
                if (project == null || project.trim().isEmpty()) project = "buildhub";
                JSONObject o = orchestrator.sentinelStatus(project);
                o.put("ok", true);
                return json(200, o);
            }

            return json(404, new JSONObject().put("ok", false).put("error", "NOT_FOUND"));
        } catch (Exception e) {
            try {
                return json(500, new JSONObject()
                        .put("ok", false)
                        .put("error", "EDGE_API_ERROR")
                        .put("class", e.getClass().getSimpleName()));
            } catch (Exception ignored) {
                return new Response(500, "{\"ok\":false,\"error\":\"EDGE_API_ERROR\"}");
            }
        }
    }

    private boolean authorized(Map<String,String> headers) {
        String auth = headers == null ? null : headers.get("authorization");
        String expected = new CredentialStore(context).getToken();
        return EdgeRelayPolicy.isValidBearerAuthorization(auth, expected);
    }

    private static Response json(int status, JSONObject body) {
        return new Response(status, body.toString());
    }

    public static final class Response {
        public final int status;
        public final String body;

        Response(int status, String body) {
            this.status = status;
            this.body = body == null ? "{}" : body;
        }
    }
}
