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
    }

    public void start() {
        stopping = false;
        io.submit(this::serveLoop);
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

            String secret = pass.optString("secret", "");
            int minutes = normalizeMinutes(pass.optInt("minutes", 30));
            if (secret.length() < 24) return json("ok", false, "error", "pass_secret_invalid");

            long now = System.currentTimeMillis();
            long offerCreatedAt = pass.optLong("offer_created_at_ms", now);
            long offerExpiresAt = pass.optLong("offer_expires_at_ms", now + Math.max(30, minutes) * 60_000L);
            prefs.edit()
                    .putString("build", build)
                    .putLong("snapshot_at", now)
                    .putString("snapshot_sha256", sha256(plain))
                    .putInt("questions", pack.optJSONArray("questions") == null ? 0 : pack.optJSONArray("questions").length())
                    .putString("pass_hash", sha256(secret.getBytes(StandardCharsets.UTF_8)))
                    .putInt("pass_minutes", minutes)
                    .putLong("pass_offer_created_at", offerCreatedAt)
                    .putLong("pass_offer_expires_at", offerExpiresAt)
                    .putLong("pass_activated_at", 0L)
                    .putLong("pass_expires_at", 0L)
                    .putString("sessions_json", "[]")
                    .apply();

            out.put("ok", true);
            out.put("build", build);
            out.put("questions", prefs.getInt("questions", 0));
            out.put("http_port", HTTP_PORT);
            out.put("snapshot_sha256", prefs.getString("snapshot_sha256", ""));
            out.put("pass_minutes", minutes);
            out.put("pass_activated", false);
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

            if ("GET".equals(method) && "/health".equals(path)) {
                writeJson(out, 200, status()); return;
            }
            if ("GET".equals(method) && "/pair".equals(path)) {
                if (!passOfferAlive()) { writeText(out, 410, "text/html; charset=utf-8", expiredPage()); return; }
                writeText(out, 200, "text/html; charset=utf-8", pairPage()); return;
            }
            if ("POST".equals(method) && "/api/claim".equals(path)) {
                JSONObject body = readJsonBody(in, headers, MAX_BROWSER_BODY);
                writeClaim(out, body.optString("token", "")); return;
            }

            boolean auth = browserAuthorized(headers.get("cookie"));
            if (!auth) {
                if ("GET".equals(method) && "/".equals(path) && passOfferAlive()) {
                    writeRedirect(out, "/pair"); return;
                }
                writeJson(out, 401, json("ok", false, "error", "pass_required")); return;
            }

            if ("GET".equals(method) && ("/".equals(path) || "/study".equals(path))) {
                writeText(out, 200, "text/html; charset=utf-8", studyPage()); return;
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

    private void writeClaim(OutputStream out, String token) throws Exception {
        long now = System.currentTimeMillis();
        if (!passOfferAlive()) { writeJson(out, 410, json("ok", false, "error", "pass_expired")); return; }
        String supplied = sha256(token.getBytes(StandardCharsets.UTF_8));
        String expected = prefs.getString("pass_hash", "");
        if (expected.isEmpty() || !MessageDigest.isEqual(
                supplied.getBytes(StandardCharsets.US_ASCII),
                expected.getBytes(StandardCharsets.US_ASCII))) {
            writeJson(out, 403, json("ok", false, "error", "pass_invalid")); return;
        }
        int minutes = normalizeMinutes(prefs.getInt("pass_minutes", 30));
        long activated = prefs.getLong("pass_activated_at", 0L);
        long expires = prefs.getLong("pass_expires_at", 0L);
        if (activated <= 0L || expires <= now) {
            activated = now;
            expires = now + minutes * 60_000L;
            prefs.edit().putLong("pass_activated_at", activated).putLong("pass_expires_at", expires).apply();
        }
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
        writeJson(out, 200, json("ok", true, "expires_at", expires, "remaining_seconds", Math.max(0L, (expires - now) / 1000L)), extra);
    }

    private boolean passOfferAlive() {
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
        return "<!doctype html><html lang=fr><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
                + "<meta name=referrer content=no-referrer><title>Excellentia · Connexion Edge</title><style>"
                + "body{font-family:system-ui;background:#091522;color:#eef6ff;margin:0;min-height:100vh;display:grid;place-items:center;padding:20px}.b{max-width:430px;background:#10263f;border:1px solid #284d73;border-radius:22px;padding:24px}button,input{width:100%;box-sizing:border-box;padding:14px;border-radius:12px;border:1px solid #365778;background:#0b1b2d;color:#fff}button{margin-top:10px;background:#1684f8;border:0;font-weight:800}.m{color:#a8bdd2}.ok{color:#63e6a3}.bad{color:#ff8390}</style></head><body><div class=b>"
                + "<h2>📚 Excellentia · Continuité Edge</h2><p class=m>Ce pass fonctionne sur le même Wi‑Fi même si le PC est ensuite éteint.</p>"
                + "<form id=f><input id=c placeholder='Code/jeton'><button>Se connecter</button></form><p id=s class=m>Connexion au nœud B‑EDGE…</p>"
                + "<script>(function(){const f=document.getElementById('f'),c=document.getElementById('c'),s=document.getElementById('s');async function go(t){s.textContent='Vérification…';let last=null;for(let a=1;a<=3;a++){try{const r=await fetch('/api/claim',{method:'POST',cache:'no-store',headers:{'content-type':'application/json'},body:JSON.stringify({token:t})}),j=await r.json();if(!r.ok){const e=new Error(j.error||'REFUSED');e.http=true;throw e}history.replaceState(null,'','/pair');s.className='ok';s.textContent='Connecté. Ouverture…';setTimeout(()=>location.replace('/'),250);return}catch(e){last=e;if(e.http)break;if(a<3){s.className='m';s.textContent='Connexion instable · nouvelle tentative…';await new Promise(r=>setTimeout(r,450*a))}}}s.className='bad';s.textContent='Connexion refusée : '+(last&&last.message?last.message:'REFUSED')}const h=location.hash||'';if(h.startsWith('#t=')){const t=decodeURIComponent(h.slice(3));location.hash='';go(t)}f.onsubmit=e=>{e.preventDefault();if(c.value.trim())go(c.value.trim())}})();</script></div></body></html>";
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
<meta name="theme-color" content="#0d1117">
<title>Excellentia · Edge</title>
<style>
*{box-sizing:border-box}
body{font-family:system-ui;background:#0b1119;color:#edf4ff;margin:0}
.top{position:sticky;top:0;background:#101a27;border-bottom:1px solid #25364d;padding:14px 16px;z-index:2}
.wrap{max-width:900px;margin:auto;padding:16px}
.card{background:#111d2b;border:1px solid #263a53;border-radius:16px;padding:16px;margin:12px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px}
button,select{padding:11px;border-radius:10px;border:1px solid #34506f;background:#14263a;color:#fff}
.primary{background:#147be0;font-weight:800}
.ans{display:block;width:100%;text-align:left;margin:8px 0}
.good{border-color:#35c88a;background:#103125}
.bad{border-color:#ef6672;background:#35151a}
.muted{color:#9fb2c7;font-size:13px}
.pill{font-size:12px;padding:5px 8px;border:1px solid #35506d;border-radius:999px}
.row{display:flex;gap:8px;align-items:center;justify-content:space-between;flex-wrap:wrap}
h1,h2,h3{margin:.2em 0 .5em}
</style>
</head>
<body>
<div class="top"><div class="row"><b>Excellentia Study Hub · EDGE</b><span class="pill" id="net">nœud local</span></div></div>
<main class="wrap">
  <div class="card">
    <h2>Continuité locale</h2>
    <p class="muted">Le contenu vient du dernier snapshot validé du PC. Tes réponses sont conservées sur l’ancien téléphone puis réconciliées au retour du PC.</p>
    <div class="grid">
      <select id="mod"></select>
      <button class="primary" id="start">Lancer 10 questions</button>
      <button id="resume">Reprendre</button>
    </div>
  </div>
  <div id="host"></div>
</main>
<script>
(async()=>{
  const H=document.getElementById('host');
  const M=document.getElementById('mod');
  let pack=null,run=null;
  const esc=v=>String(v??'')
    .replaceAll('&','&amp;')
    .replaceAll('<','&lt;')
    .replaceAll('>','&gt;');

  function outbox(){
    try{return JSON.parse(localStorage.getItem('exc_edge_outbox')||'[]')}
    catch{return []}
  }
  function saveOutbox(items){
    localStorage.setItem('exc_edge_outbox',JSON.stringify(items.slice(-500)));
  }
  async function flushOutbox(){
    const pending=outbox();
    if(!pending.length)return true;
    const keep=[];
    for(const item of pending){
      try{
        const r=await fetch('/api/progress',{
          method:'POST',cache:'no-store',
          headers:{'content-type':'application/json'},
          body:JSON.stringify(item)
        });
        if(!r.ok)throw new Error('HTTP_'+r.status);
      }catch{keep.push(item)}
    }
    saveOutbox(keep);
    return keep.length===0;
  }
  function queueProgress(item){
    const pending=outbox();
    if(!pending.some(x=>x.id===item.id))pending.push(item);
    saveOutbox(pending);
    void flushOutbox();
  }

  async function load(){
    const r=await fetch('/api/offline-pack',{cache:'no-store'});
    if(!r.ok)throw new Error('snapshot indisponible');
    pack=await r.json();
    const mods=pack.modules||[];
    M.innerHTML='<option value="0">Grand Mix</option>'+
      mods.filter(x=>Number(x.id)<=7)
        .map(x=>'<option value="'+Number(x.id)+'">'+esc(x.short||x.title)+'</option>')
        .join('');
    const saved=localStorage.getItem('exc_edge_run');
    if(saved){try{run=JSON.parse(saved)}catch{}}
    await flushOutbox();
    render();
  }

  function save(){
    if(run)localStorage.setItem('exc_edge_run',JSON.stringify(run));
  }

  function pick(){
    const m=Number(M.value||0);
    const all=(pack.questions||[]).filter(q=>!m||Number(q.module)===m);
    const a=[...all];
    for(let i=a.length-1;i>0;i--){
      const j=Math.floor(Math.random()*(i+1));
      [a[i],a[j]]=[a[j],a[i]];
    }
    run={id:'edge-run-'+Date.now()+'-'+Math.random().toString(36).slice(2,8),ids:a.slice(0,10).map(q=>q.id),i:0,score:0,answers:{},started:Date.now()};
    save();render();
  }

  function current(){
    if(!run)return null;
    return (pack.questions||[]).find(x=>x.id===run.ids[run.i])||null;
  }

  async function answer(i){
    const x=current();
    if(!x||run.answers[x.id]!=null)return;
    const ok=Number(i)===Number(x.answer);
    run.answers[x.id]=i;
    if(ok)run.score++;
    save();
    queueProgress({
      id:run.id+'-'+(run.i+1)+'-'+x.id,
      run_id:run.id,run_total:run.ids.length,run_position:run.i+1,
      question_id:x.id,knowledge_id:x.knowledge_id,module:x.module,
      selected:i,correct:ok,mode:'EDGE_OFFLINE'
    });
    render();
  }

  function next(){
    void flushOutbox();
    if(run.i<run.ids.length-1){run.i++;save();render();return}
    H.innerHTML='<div class="card"><h2>Terminé · '+run.score+'/'+run.ids.length+
      '</h2><p class="muted">Résultat conservé sur B‑EDGE.</p>'+
      '<button class="primary" id="reset">Nouvelle série</button></div>';
    document.getElementById('reset').onclick=()=>{
      localStorage.removeItem('exc_edge_run');
      run=null;
      render();
    };
  }

  function render(){
    if(!run){
      H.innerHTML='<div class="card"><h3>Prêt</h3><p class="muted">Choisis un module puis lance une série. Le PC n’est pas requis pour cette continuité.</p></div>';
      return;
    }
    const x=current();
    if(!x){H.innerHTML='<div class="card">Session locale invalide.</div>';return}
    const selected=run.answers[x.id];
    H.innerHTML='<div class="card"><div class="row"><span class="pill">Question '+(run.i+1)+' / '+run.ids.length+
      '</span><b>'+run.score+' pts</b></div><h2>'+esc(x.prompt)+'</h2>'+
      (x.choices||[]).map((c,i)=>'<button class="ans '+(selected!=null?(i===Number(x.answer)?'good':i===Number(selected)?'bad':''):'')+
        '" data-a="'+i+'">'+esc(c)+'</button>').join('')+
      (selected!=null?'<p class="muted">'+esc(x.explanation||'')+'</p><button class="primary" id="next">Suivant</button>':'')+
      '</div>';
    document.querySelectorAll('[data-a]').forEach(b=>b.onclick=()=>answer(Number(b.dataset.a)));
    const n=document.getElementById('next');
    if(n)n.onclick=next;
  }

  document.getElementById('start').onclick=pick;
  document.getElementById('resume').onclick=render;
  await load();
})().catch(e=>{
  document.getElementById('host').innerHTML='<div class="card"><h3>Snapshot indisponible</h3><p>'+String(e.message||e)+'</p></div>';
});
</script>
</body>
</html>
""";
    }

    static int normalizeMinutes(int n) {
        int[] allowed = new int[]{30,60,90,120,180,240,360,480};
        for (int x : allowed) if (n == x) return x;
        return 30;
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

    private static void writeBytes(OutputStream out, int status, String type, byte[] body) throws Exception {
        writeBytes(out, status, type, body, new HashMap<>());
    }

    private static void writeBytes(OutputStream out, int status, String type, byte[] body, Map<String,String> extra) throws Exception {
        String reason = status == 200 ? "OK" : status == 202 ? "Accepted" : status == 302 ? "Found" : status == 400 ? "Bad Request" : status == 401 ? "Unauthorized" : status == 403 ? "Forbidden" : status == 404 ? "Not Found" : status == 410 ? "Gone" : status == 503 ? "Unavailable" : "OK";
        StringBuilder h = new StringBuilder("HTTP/1.1 ").append(status).append(' ').append(reason).append("\r\n")
                .append("Content-Type: ").append(type).append("\r\n")
                .append("Content-Length: ").append(body.length).append("\r\n")
                .append("Cache-Control: no-store\r\n")
                .append("X-Content-Type-Options: nosniff\r\n")
                .append("Referrer-Policy: no-referrer\r\n")
                .append("Connection: close\r\n");
        for (Map.Entry<String,String> e : extra.entrySet()) h.append(e.getKey()).append(": ").append(e.getValue()).append("\r\n");
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
