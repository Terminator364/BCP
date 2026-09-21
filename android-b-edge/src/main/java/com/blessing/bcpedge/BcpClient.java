package com.blessing.bcpedge;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Build;
import com.blessing.bcpedge.work.EdgeWorkScheduler;

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
    private static final String DEFAULT_PROJECT = "buildhub";
    private static final String EDGE_VERSION = "2.2.0-rc1-full-node";
    private final Context context;
    private final SharedPreferences prefs;
    private final TelemetryStore telemetry;
    private final CredentialStore credentials;
    private final EdgeOrchestrator orchestrator;

    public BcpClient(Context context) {
        this.context = context.getApplicationContext();
        this.prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        this.telemetry = new TelemetryStore(context);
        this.credentials = new CredentialStore(context);
        this.orchestrator = new EdgeOrchestrator(context);
    }

    public String getServer() { return prefs.getString("server", ""); }
    public String getToken() { return credentials.getToken(); }
    public String getProject() { return prefs.getString("active_project", DEFAULT_PROJECT); }
    public void setProject(String projectId) {
        String p = projectId == null ? "" : projectId.trim();
        if (p.isEmpty() || p.length() > 128) throw new IllegalArgumentException("invalid_project_id");
        prefs.edit().putString("active_project", p).commit();
        orchestrator.ensureProject(p, 0, 0);
    }
    public JSONArray projectRegistry() { return orchestrator.projectRegistry(); }
    public String getEdgeVersion() { return EDGE_VERSION; }
    public JSONObject sentinelStatus() { return orchestrator.sentinelStatus(getProject()); }

    public JSONObject observePcSentinel(boolean reachable) {
        JSONObject s = orchestrator.observePcReachability(getProject(), reachable);
        if (s.optBoolean("transitioned", false)) {
            telemetry.add("EDGE_SENTINEL_TRANSITION",
                    s.optString("previous_state", "") + "->" + s.optString("state", ""));
        }
        if (s.optBoolean("alert_due", false)) {
            telemetry.add("EDGE_SENTINEL_PC_UNAVAILABLE",
                    "resume=" + s.optString("resume_request_id", ""));
        }
        return s;
    }

    public void recordEvent(String type, String detail) {
        telemetry.add(type, detail);
    }

    public JSONObject registerEdgeRelay() {
        JSONObject out = new JSONObject();
        try {
            if (getServer().isEmpty() || getToken().isEmpty()) {
                out.put("ok", false);
                out.put("state", "NOT_PAIRED");
                return out;
            }
            JSONObject body = new JSONObject();
            body.put("port", EdgeRelayPolicy.RELAY_PORT);
            body.put("capability", "HTTPS_CONNECT_TELEGRAM");
            body.put("ttl_seconds", EdgeRelayPolicy.REGISTRATION_TTL_SECONDS);
            body.put("edge_version", EDGE_VERSION);
            body.put("node_role", "DEDICATED_EDGE_API_SERVER");
            body.put("api_port", EdgeRelayPolicy.RELAY_PORT);
            body.put("api_version", "v1");
            body.put("store_and_forward", true);
            body.put("durable_queue", true);
            JSONObject r = requestJson(
                    "POST", getServer() + "/v1/edge/relay/register",
                    body.toString(), getToken(), "edge-relay-register",
                    1500, 3000);
            telemetry.add("EDGE_RELAY_REGISTERED",
                    r.optString("relay_host", "") + ":" + r.optInt("relay_port", 0));
            return r;
        } catch (Exception ex) {
            try {
                out.put("ok", false);
                out.put("state", "REGISTRATION_DEFERRED");
                out.put("error_class", ex.getClass().getSimpleName());
            } catch (Exception ignored) {}
            telemetry.add("EDGE_RELAY_REGISTRATION_DEFERRED", ex.getClass().getSimpleName());
            return out;
        }
    }

    public JSONObject serverUpdateStatus() throws Exception {
        ensureConnected();
        return requestJson("GET", getServer() + "/v1/system/update", null,
                getToken(), null, 2500, 7000);
    }

    public JSONObject applyServerUpdate() throws Exception {
        ensureConnected();
        telemetry.add("SERVER_UPDATE_REQUESTED", null);
        JSONObject r = requestJson("POST", getServer() + "/v1/system/update/apply", "{}",
                getToken(), "server-update-" + UUID.randomUUID(), 3000, 45000);
        telemetry.add("SERVER_UPDATE_ACCEPTED", r.optString("target_version", ""));
        return r;
    }

    public JSONObject chatgptPcStatus() throws Exception {
        ensureConnected();
        return requestJson("GET", getServer() + "/v1/system/chatgpt-pc", null,
                getToken(), null, 2500, 7000);
    }

    public JSONObject recoverChatgptPc() throws Exception {
        ensureConnected();
        telemetry.add("CHATGPT_PC_RECOVERY_REQUESTED", null);
        JSONObject body = new JSONObject();
        body.put("confirm", true);
        JSONObject r = requestJson("POST", getServer() + "/v1/system/chatgpt-pc/recover",
                body.toString(), getToken(), "chatgpt-pc-recover-" + UUID.randomUUID(), 3000, 12000);
        telemetry.add("CHATGPT_PC_RECOVERY_ACCEPTED", r.optString("target_version", ""));
        return r;
    }


    private JSONObject autoPromoteServerIfNeeded(Progress progress) {
        try {
            JSONObject st = serverUpdateStatus();
            String current = st.optString("current_version", "");
            String target = st.optString("target_version", current);
            boolean available = st.optBoolean("available", false);
            if (!available) {
                telemetry.add("SERVER_UPDATE_NOT_NEEDED", current);
                return health();
            }

            progress.onStage("SERVER_UPDATE", "Mise à niveau automatique du serveur PC vers " + target);
            telemetry.add("SERVER_UPDATE_AUTO_START", current + "->" + target);
            JSONObject applied = applyServerUpdate();
            if (!applied.optBoolean("restart_required", false)) {
                telemetry.add("SERVER_UPDATE_AUTO_NO_RESTART", target);
                return health();
            }

            long deadline = System.currentTimeMillis() + 30000;
            Exception last = null;
            while (System.currentTimeMillis() < deadline) {
                try {
                    Thread.sleep(900);
                    JSONObject h = health();
                    String got = h.optString("version", "");
                    if (h.optBoolean("ok") && (target.isEmpty() || target.equals(got))) {
                        telemetry.add("SERVER_UPDATE_AUTO_PASS", got);
                        progress.onStage("SERVER_UPDATED", "Serveur PC " + got + " actif");
                        flushTelemetry();
                        return h;
                    }
                } catch (Exception ex) {
                    last = ex;
                }
            }
            telemetry.add("SERVER_UPDATE_AUTO_PENDING", target);
            progress.onStage("SERVER_UPDATE_PENDING", "Mise à jour appliquée; redémarrage encore en cours");
            return health();
        } catch (Exception ex) {
            // Connection remains usable even if update metadata is temporarily unavailable.
            telemetry.add("SERVER_UPDATE_AUTO_DEFERRED",
                    ex.getMessage() == null ? ex.getClass().getSimpleName() : ex.getMessage());
            return null;
        }
    }

    public JSONObject connectAutomatically(Progress progress) throws Exception {
        progress.onStage("START", "BCP Edge démarre");
        telemetry.add("START", null);

        String savedServer = getServer();
        if (!savedServer.isEmpty()) {
            progress.onStage("RECONNECT", "Vérification du PC déjà appairé");
            telemetry.add("RECONNECT_TRY", savedServer);
            try {
                JSONObject h = requestJson("GET", savedServer + "/health", null, null, null, 1200, 1500);
                if (h.optBoolean("ok")) {
                    String fp = h.optString("identity_fingerprint", "");
                    if (!fp.isEmpty()) prefs.edit().putString("confirmed_pc_fingerprint", fp).apply();
                    progress.onStage("CONNECTED", "PC retrouvé automatiquement");
                    telemetry.add("RECONNECT_PASS", savedServer);
                    heartbeat("RECONNECT_PASS");
                    flushPendingCheckpoint();
                    syncOrchestrationState();
                    JSONObject promoted = autoPromoteServerIfNeeded(progress);
                    return promoted != null ? promoted : h;
                }
            } catch (Exception ignored) {
                telemetry.add("RECONNECT_FAIL", savedServer);
            }
        }

        progress.onStage("DISCOVERY", "Recherche automatique du PC sur le Wi-Fi");
        telemetry.add("DISCOVERY_START", null);
        JSONObject candidate = discoverLan(progress);
        if (candidate == null) {
            telemetry.add("PC_NOT_FOUND", null);
            throw new IOException("PC_NOT_FOUND");
        }

        String server = candidate.getString("server");
        String pcName = candidate.optString("pc_name", "BCP PC");
        String fingerprint = candidate.optString("identity_fingerprint", "");
        String version = candidate.optString("version", "");

        progress.onStage("PC_FOUND", pcName);
        telemetry.add("PC_DISCOVERED", pcName + "@" + server);

        String confirmed = prefs.getString("confirmed_pc_fingerprint", "");
        if (getToken().isEmpty() && (confirmed.isEmpty() ||
                (!fingerprint.isEmpty() && !fingerprint.equals(confirmed)))) {
            prefs.edit()
                    .putString("pending_pair_server", server)
                    .putString("pending_pair_pc_name", pcName)
                    .putString("pending_pair_fingerprint", fingerprint)
                    .putString("pending_pair_version", version)
                    .apply();
            telemetry.add("PAIRING_CONFIRM_REQUIRED",
                    pcName + (fingerprint.isEmpty() ? "" : "#" + fingerprint));
            throw new IOException("PAIR_CONFIRM_REQUIRED");
        }

        return pairServer(server, fingerprint, progress);
    }

    public JSONObject pendingPairingInfo() throws Exception {
        JSONObject o = new JSONObject();
        o.put("server", prefs.getString("pending_pair_server", ""));
        o.put("pc_name", prefs.getString("pending_pair_pc_name", "BCP PC"));
        o.put("identity_fingerprint", prefs.getString("pending_pair_fingerprint", ""));
        o.put("version", prefs.getString("pending_pair_version", ""));
        return o;
    }

    public JSONObject confirmPendingPairing(Progress progress) throws Exception {
        String server = prefs.getString("pending_pair_server", "");
        String fingerprint = prefs.getString("pending_pair_fingerprint", "");
        if (server.isEmpty()) throw new IOException("PAIRING_CANDIDATE_MISSING");
        if (!fingerprint.isEmpty()) {
            prefs.edit().putString("confirmed_pc_fingerprint", fingerprint).apply();
        } else {
            // Legacy bootstrap: bind confirmation to the discovered endpoint until
            // the server upgrades and exposes its stable identity fingerprint.
            prefs.edit().putString("confirmed_pc_fingerprint", "legacy:" + server).apply();
        }
        return pairServer(server, fingerprint, progress);
    }

    private JSONObject pairServer(String server, String fingerprint, Progress progress) throws Exception {
        JSONObject pairBody = new JSONObject();
        pairBody.put("device_name", Build.MANUFACTURER + " " + Build.MODEL);
        pairBody.put("edge_version", EDGE_VERSION);
        pairBody.put("project", getProject());
        if (fingerprint != null && !fingerprint.isEmpty()) {
            pairBody.put("identity_fingerprint", fingerprint);
        }

        progress.onStage("PAIRING", "Appairage sécurisé local");
        telemetry.add("PAIRING_STARTED", server);
        JSONObject pair = requestJson("POST", server + "/pair", pairBody.toString(),
                null, null, 2000, 3000);

        String token = pair.optString("token", "");
        if (token.isEmpty()) {
            telemetry.add("PAIRING_FAIL", pair.optString("error", "PAIRING_FAILED"));
            throw new IOException("PAIRING_FAILED");
        }

        credentials.putToken(token);
        String returnedFingerprint = pair.optString("identity_fingerprint", "");
        SharedPreferences.Editor ed = prefs.edit()
                .putString("server", server)
                .remove("pending_pair_server")
                .remove("pending_pair_pc_name")
                .remove("pending_pair_fingerprint")
                .remove("pending_pair_version");
        if (!returnedFingerprint.isEmpty()) {
            ed.putString("confirmed_pc_fingerprint", returnedFingerprint);
        }
        ed.apply();

        telemetry.add("PAIRING_PASS", server);
        progress.onStage("CONNECTED", "Appairé à " + pair.optString("pc_name", "BCP PC"));
        heartbeat("PAIRING_PASS");
        registerEdgeRelay();
        JSONObject promoted = autoPromoteServerIfNeeded(progress);
        if (promoted != null) {
            String fp = promoted.optString("identity_fingerprint", "");
            if (!fp.isEmpty()) prefs.edit().putString("confirmed_pc_fingerprint", fp).apply();
            JSONObject safe = new JSONObject();
            safe.put("paired", true);
            safe.put("pc_name", promoted.optString("pc_name", pair.optString("pc_name", "BCP PC")));
            safe.put("version", promoted.optString("version", pair.optString("version", "")));
            safe.put("project", getProject());
            safe.put("credential", "stored_securely_not_displayed");
            return safe;
        }
        return publicPairStatus(pair);
    }

    private JSONObject discoverLan(Progress progress) throws Exception {
        progress.onStage("DISCOVERY_NSD", "Recherche mDNS/NSD du PC");
        String nsd=NsdDiscovery.discover(context,2400L);
        if(!nsd.isEmpty()){
            JSONObject found=probeServer(nsd,700,1000);
            if(found!=null){
                telemetry.add("DISCOVERY_NSD_PASS",nsd);
                progress.onStage("DISCOVERY_PASS",found.optString("pc_name",found.optString("server","")));
                return found;
            }
            telemetry.add("DISCOVERY_NSD_STALE",nsd);
        }

        String ip=localIpv4();
        if(ip==null) throw new IOException("NO_LAN_IPV4");
        String[] p=ip.split("\\.");
        if(p.length!=4) throw new IOException("UNSUPPORTED_SUBNET");
        String prefix=p[0]+"."+p[1]+"."+p[2]+".";
        telemetry.add("DISCOVERY_SUBNET_FALLBACK",prefix+"0/24");

        ExecutorService pool=Executors.newFixedThreadPool(12);
        CompletionService<String> cs=new ExecutorCompletionService<>(pool);
        List<Future<String>> futures=new ArrayList<>();
        for(int n=1;n<=254;n++){
            final String host=prefix+n;
            if(host.equals(ip)) continue;
            futures.add(cs.submit(()->{
                JSONObject found=probeServer("http://"+host+":8765",180,320);
                return found==null?null:found.toString();
            }));
        }
        JSONObject found=null;
        try{
            int total=futures.size();
            long deadline=System.currentTimeMillis()+3800;
            for(int n=0;n<total && System.currentTimeMillis()<deadline;n++){
                Future<String> future=cs.poll(220,TimeUnit.MILLISECONDS);
                if(future==null) continue;
                String raw=future.get();
                if(raw!=null){found=new JSONObject(raw);break;}
            }
        }finally{
            for(Future<String> future:futures) future.cancel(true);
            pool.shutdownNow();
        }
        if(found!=null) progress.onStage("DISCOVERY_PASS",found.optString("pc_name",found.optString("server","")));
        return found;
    }

    private JSONObject probeServer(String base,int connectMs,int readMs){
        try{
            JSONObject h=requestJson("GET",base+"/health",null,null,null,connectMs,readMs);
            if(!h.optBoolean("ok") || !h.optString("service","").startsWith("BCP")) return null;
            JSONObject found=new JSONObject();
            found.put("server",base);
            found.put("pc_name",h.optString("pc_name","BCP PC"));
            found.put("version",h.optString("version",""));
            found.put("identity_fingerprint",h.optString("identity_fingerprint",""));
            return found;
        }catch(Exception ignored){return null;}
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

        JSONObject current = requestJson("GET",
                getServer() + "/v1/projects/" + enc(getProject()) + "/resume",
                null, getToken(), null, 2500, 5000);
        cacheResume(current);
        JSONObject head = current.optJSONObject("head");
        int expectedRevision = head == null ? 0 : head.optInt("revision", 0);

        JSONObject payload = new JSONObject();
        payload.put("status", "ACTIVE");
        payload.put("last_completed_action", completed);
        payload.put("next_action", next);
        payload.put("edge_version", EDGE_VERSION);

        JSONObject body = new JSONObject();
        body.put("type", "checkpoint");
        body.put("payload", payload);
        body.put("expected_revision", expectedRevision);

        String fingerprint = completed + "\n" + next + "\n" + expectedRevision;
        String savedFingerprint = prefs.getString("pending_checkpoint_fingerprint", "");
        String idem = prefs.getString("pending_checkpoint_idem", "");
        if (idem.isEmpty() || !fingerprint.equals(savedFingerprint)) {
            idem = "edge-" + UUID.randomUUID();
        }

        prefs.edit()
                .putString("pending_checkpoint_idem", idem)
                .putString("pending_checkpoint_fingerprint", fingerprint)
                .putString("pending_checkpoint_body", body.toString())
                .apply();

        telemetry.add("CHECKPOINT_START", "expected_revision=" + expectedRevision);
        try {
            JSONObject r = postPendingCheckpoint(body, idem);
            onCheckpointReceipt(r);
            return r;
        } catch (Exception ex) {
            telemetry.add("CHECKPOINT_QUEUED",
                    ex.getMessage() == null ? ex.getClass().getSimpleName() : ex.getMessage());
            flushTelemetry();
            throw ex;
        }
    }

    private JSONObject postPendingCheckpoint(JSONObject body, String idem) throws Exception {
        return requestJson("POST",
                getServer() + "/v1/projects/" + enc(getProject()) + "/events",
                body.toString(), getToken(), idem, 2500, 5000);
    }

    private void onCheckpointReceipt(JSONObject r) throws Exception {
        String result = r.optString("result", "");
        if ("COMMITTED".equals(result) || "ALREADY_COMMITTED".equals(result)) {
            prefs.edit()
                    .remove("pending_checkpoint_idem")
                    .remove("pending_checkpoint_fingerprint")
                    .remove("pending_checkpoint_body")
                    .apply();
            JSONObject resumed = requestJson("GET",
                    getServer() + "/v1/projects/" + enc(getProject()) + "/resume",
                    null, getToken(), null, 2500, 5000);
            cacheResume(resumed);
        }
        telemetry.add("CHECKPOINT_PASS",
                "revision=" + r.optInt("revision", -1) + ",result=" + result);
        flushTelemetry();
    }

    public void flushPendingCheckpoint() {
        String bodyRaw = prefs.getString("pending_checkpoint_body", "");
        String idem = prefs.getString("pending_checkpoint_idem", "");
        if (bodyRaw.isEmpty() || idem.isEmpty() || getToken().isEmpty()) return;
        try {
            telemetry.add("CHECKPOINT_RETRY_START", null);
            JSONObject r = postPendingCheckpoint(new JSONObject(bodyRaw), idem);
            onCheckpointReceipt(r);
            telemetry.add("CHECKPOINT_RETRY_PASS", r.optString("result", ""));
        } catch (Exception ex) {
            String msg = ex.getMessage() == null ? ex.getClass().getSimpleName() : ex.getMessage();
            telemetry.add(msg.contains("HTTP_409") ?
                    "CHECKPOINT_RETRY_CONFLICT" : "CHECKPOINT_RETRY_DEFERRED", msg);
        }
    }

    public JSONObject resume() throws Exception {
        telemetry.add("RESUME_START", null);
        try {
            ensureConnected();
            JSONObject r = requestJson("GET",
                    getServer() + "/v1/projects/" + enc(getProject()) + "/resume",
                    null, getToken(), null, 2500, 5000);
            cacheResume(r);
            telemetry.add("RESUME_PASS", "revision=" + r.optJSONObject("head"));
            flushTelemetry();
            return r;
        } catch (Exception ex) {
            String cached = prefs.getString("cached_resume_json", "");
            if (!cached.isEmpty()) {
                JSONObject r = new JSONObject(cached);
                r.put("source", "LOCAL_CACHE");
                r.put("offline", true);
                telemetry.add("RESUME_CACHE_FALLBACK", ex.getClass().getSimpleName());
                return r;
            }
            throw ex;
        }
    }

    private void cacheResume(JSONObject r) {
        try {
            orchestrator.putMemory(getProject(), "PROJECT_MEMORY", "resume_snapshot", r,
                    "MACHINE_READBACK", true, null);
            prefs.edit()
                    .putString("cached_resume_json", r.toString())
                    .putLong("cached_resume_at", System.currentTimeMillis())
                    .commit();
        } catch (Exception ignored) {}
    }

    public JSONObject orchestratorStatus() throws Exception {
        ensureConnected();
        JSONObject r = requestJson("GET", getServer() + "/v1/orchestrator/status",
                null, getToken(), null, 1800, 3500);
        boolean pressure = "PC_MEMORY_PRESSURE".equals(r.optString("operating_mode", ""));
        orchestrator.setMode(EdgePolicy.mode(true, pressure));
        return r;
    }

    public JSONObject contextPack() throws Exception {
        try {
            ensureConnected();
            JSONObject r = requestJson("GET",
                    getServer() + "/v1/projects/" + enc(getProject()) + "/context",
                    null, getToken(), null, 2200, 5000);
            orchestrator.cacheContext(getProject(), r);
            return r;
        } catch (Exception ex) {
            orchestrator.setMode("EDGE_ONLY");
            JSONObject cached = orchestrator.cachedContext(getProject());
            if (cached.length() > 0) return cached;
            throw ex;
        }
    }

    public JSONObject queueJob(String kind, JSONObject payload, boolean requiresPc) throws Exception {
        String resourceClass=EdgePolicy.resourceClass(requiresPc,false,false);
        JSONObject local = orchestrator.queueJob(
                getProject(), kind, payload, requiresPc, 50,
                resourceClass, new JSONArray());
        if (!local.optBoolean("queued", false)) return local;
        JSONObject resources=EdgeResourceGovernor.snapshot(context);
        if(EdgeResourceGovernor.shouldDefer(resourceClass,resources)){
            local.put("deferred_by_resource_governor",true);
            local.put("resources",resources);
            EdgeWorkScheduler.requestImmediate(context);
            return local;
        }
        try {
            ensureConnected();
            JSONObject body = new JSONObject();
            body.put("kind", kind);
            body.put("payload", payload);
            body.put("requires_pc", requiresPc);
            body.put("resource_class", local.optString("resource_class", ""));
            String idem = local.optString("idempotency_key", "");
            JSONObject r = requestJson("POST",
                    getServer() + "/v1/projects/" + enc(getProject()) + "/jobs",
                    body.toString(), getToken(), idem, 2200, 5000);
            orchestrator.acknowledgeRemoteJob(getProject(), local, r);
            flushQueuedJobs();
            return r;
        } catch (Exception ex) {
            orchestrator.setMode("EDGE_ONLY");
            local.put("offline", true);
            local.put("queued_locally", true);
            EdgeWorkScheduler.requestImmediate(context, "QUEUE_OFFLINE");
            return local;
        }
    }

    public void flushQueuedJobs() {
        if (getServer().isEmpty() || getToken().isEmpty()) return;
        try {
            JSONArray q = orchestrator.pendingJobs(getProject());
            for (int i = 0; i < q.length() && i < 24; i++) {
                JSONObject job = q.optJSONObject(i);
                if (job == null || "BLOCKED".equals(job.optString("state", ""))) continue;
                try {
                    JSONObject body = new JSONObject();
                    body.put("kind", job.optString("kind", "generic"));
                    body.put("payload", job.optJSONObject("payload") == null ? new JSONObject() : job.optJSONObject("payload"));
                    body.put("requires_pc", job.optBoolean("requires_pc", true));
                    body.put("resource_class", job.optString("resource_class", ""));
                    JSONObject receipt = requestJson("POST",
                            getServer() + "/v1/projects/" + enc(getProject()) + "/jobs",
                            body.toString(), getToken(),
                            job.optString("idempotency_key", ""),
                            1800, 4000);
                    orchestrator.acknowledgeRemoteJob(getProject(), job, receipt);
                } catch (Exception ex) {
                    // At-least-once: keep durable row until a positive receipt exists.
                }
            }
        } catch (Exception ignored) {}
    }

    public JSONObject syncOrchestrationState() {
        JSONObject out = new JSONObject();
        try {
            JSONObject st = orchestratorStatus();
            JSONObject sentinel = observePcSentinel(true);
            out.put("mode", orchestrator.getMode());
            out.put("sentinel", sentinel);
            JSONObject ctx = contextPack();
            out.put("context_cached", ctx.length() > 0);
            flushQueuedJobs();
            out.put("edge_relay", registerEdgeRelay());
            out.put("queued_jobs_remaining", orchestrator.pendingCount());
            orchestrator.putMemory(getProject(), "OPERATING_STATE", "last_sync", out, "MACHINE_READBACK", false, null);
            telemetry.add("ORCHESTRATOR_SYNC_PASS", orchestrator.getMode());
        } catch (Exception ex) {
            JSONObject sentinel = observePcSentinel(false);
            try {
                out.put("mode", orchestrator.getMode());
                out.put("offline", true);
                out.put("sentinel", sentinel);
                out.put("queued_jobs_remaining", orchestrator.pendingCount());
            } catch (Exception ignored) {}
            telemetry.add("ORCHESTRATOR_SYNC_DEGRADED", ex.getClass().getSimpleName());
        }
        return out;
    }

    public JSONObject health() throws Exception {
        ensureConnected();
        return requestJson("GET", getServer() + "/health", null, null, null, 1500, 2500);
    }

    public JSONObject runQuickAcceptance() throws Exception {
        ensureConnected();
        telemetry.add("EDGE_ACCEPTANCE_START", null);
        JSONObject out = new JSONObject();
        out.put("edge_version", EDGE_VERSION);

        JSONObject h = health();
        out.put("health_ok", h.optBoolean("ok", false));
        out.put("server_version", h.optString("version", ""));
        if (!h.optBoolean("ok", false)) throw new IOException("SERVER_UNHEALTHY");

        JSONObject r = requestJson("GET",
                getServer() + "/v1/projects/" + enc(getProject()) + "/resume",
                null, getToken(), null, 2500, 5000);
        JSONObject head = r.optJSONObject("head");
        out.put("project_head_reachable", true);
        out.put("project_revision", head == null ? 0 : head.optInt("revision", 0));

        JSONObject up = serverUpdateStatus();
        out.put("server_update_available", up.optBoolean("available", false));
        out.put("server_target", up.optString("target_version", ""));

        try {
            JSONObject cp = chatgptPcStatus();
            out.put("chatgpt_pc_reachable", cp.optBoolean("ok", true));
            out.put("chatgpt_pc_version", cp.optString("active_version",
                    cp.optString("version", "")));
        } catch (Exception ex) {
            out.put("chatgpt_pc_reachable", false);
            out.put("chatgpt_pc_error", ex.getClass().getSimpleName());
        }

        JSONObject orch = syncOrchestrationState();
        out.put("orchestration_mode", orch.optString("mode", ""));
        out.put("sentinel", sentinelStatus());
        out.put("context_cached", orch.optBoolean("context_cached", false));
        out.put("queued_jobs_remaining", orch.optInt("queued_jobs_remaining", 0));
        out.put("paired", !getToken().isEmpty());
        out.put("ok", true);
        telemetry.add("EDGE_ACCEPTANCE_PASS",
                "revision=" + out.optInt("project_revision", 0));
        flushTelemetry();
        return out;
    }

    public void heartbeat(String reason) {
        telemetry.add("PHONE_HEARTBEAT", reason == null ? "FOREGROUND" : reason);
        if (orchestrator.shouldRunPeriodicSync(EdgePolicy.defaultReconcileIntervalMs())) {
            EdgeWorkScheduler.requestImmediate(context);
        }
        flushTelemetry();
    }

    private JSONObject publicPairStatus(JSONObject pair) throws Exception {
        JSONObject safe = new JSONObject();
        safe.put("paired", pair.optBoolean("paired", true));
        safe.put("pc_name", pair.optString("pc_name", "BCP PC"));
        safe.put("version", pair.optString("version", ""));
        safe.put("project", getProject());
        safe.put("credential", "stored_securely_not_displayed");
        return safe;
    }

    private void ensureConnected() throws IOException {
        if (getServer().isEmpty() || getToken().isEmpty()) throw new IOException("NOT_PAIRED");
    }

    public void flushTelemetry() {
        if (getServer().isEmpty() || getToken().isEmpty()) return;
        try {
            // Bound one flush to at most 3 x 100 events to protect battery/network.
            for (int batch = 0; batch < 3; batch++) {
                JSONArray events = telemetry.readBatch(100);
                if (events.length() == 0) return;
                JSONObject body = new JSONObject();
                body.put("events", events);
                JSONObject receipt = requestJson("POST",
                        getServer() + "/v1/telemetry", body.toString(),
                        getToken(), "telemetry-" + UUID.randomUUID(), 1500, 3000);
                int accepted = receipt.optInt("accepted", 0);
                if (accepted <= 0) return;
                telemetry.acknowledge(accepted);
                if (accepted < events.length()) return;
            }
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
