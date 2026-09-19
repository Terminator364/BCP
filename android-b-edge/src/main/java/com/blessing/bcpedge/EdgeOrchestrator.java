package com.blessing.bcpedge;

import android.content.Context;
import android.content.SharedPreferences;

import com.blessing.bcpedge.storage.EdgeContextEntity;
import com.blessing.bcpedge.storage.EdgeDao;
import com.blessing.bcpedge.storage.EdgeDatabase;
import com.blessing.bcpedge.storage.EdgeDependencyEntity;
import com.blessing.bcpedge.storage.EdgeJobEntity;
import com.blessing.bcpedge.storage.EdgeMemoryEntity;
import com.blessing.bcpedge.storage.EdgeProjectEntity;
import com.blessing.bcpedge.storage.EdgeReceiptEntity;

import org.json.JSONArray;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

public final class EdgeOrchestrator {
    private static final String PREFS = "bcp_edge_orchestrator_settings";
    private static final String[] MEMORY_SCOPES = {
            "USER_MEMORY","PROJECT_MEMORY","TECHNICAL_KNOWLEDGE",
            "OPERATING_STATE","HISTORY","POLICY"
    };

    private final Context context;
    private final SharedPreferences prefs;
    private final EdgeDao dao;

    public EdgeOrchestrator(Context context) {
        this.context=context.getApplicationContext();
        this.prefs=this.context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        this.dao=EdgeDatabase.get(this.context).edgeDao();
        registerProject(getActiveProject(), "ACTIVE", 0L, 0L);
    }

    public synchronized void setMode(String mode) {
        prefs.edit().putString("mode",mode).putLong("mode_at",System.currentTimeMillis()).commit();
    }

    public synchronized String getMode() {
        return prefs.getString("mode","EDGE_ONLY");
    }

    public synchronized String getActiveProject() {
        String p=prefs.getString("active_project","buildhub");
        return p==null || p.trim().isEmpty() ? "buildhub" : p.trim();
    }

    public synchronized void setActiveProject(String projectId) {
        String p=projectId==null?"":projectId.trim();
        if(p.isEmpty() || p.length()>128) throw new IllegalArgumentException("INVALID_PROJECT_ID");
        registerProject(p,"ACTIVE",0L,0L);
        prefs.edit().putString("active_project",p).commit();
    }

    public synchronized JSONArray projects() {
        JSONArray out=new JSONArray();
        for(EdgeProjectEntity p:dao.projects()){
            JSONObject o=new JSONObject();
            try{
                o.put("project_id",p.projectId);
                o.put("status",p.status);
                o.put("head_revision",p.headRevision);
                o.put("coordinator_epoch",p.coordinatorEpoch);
                o.put("updated_at",p.updatedAt);
            }catch(Exception ignored){}
            out.put(o);
        }
        return out;
    }

    public synchronized void registerProject(String projectId,String status,long headRevision,long epoch){
        dao.putProject(new EdgeProjectEntity(projectId,status,headRevision,epoch,System.currentTimeMillis()));
    }

    public synchronized boolean shouldRunPeriodicSync(long minIntervalMs) {
        long now=System.currentTimeMillis();
        long last=prefs.getLong("orchestration_sync_attempt_at",0L);
        if(!EdgePolicy.shouldRunSync(now,last,minIntervalMs)) return false;
        prefs.edit().putLong("orchestration_sync_attempt_at",now).commit();
        return true;
    }

    public synchronized void cacheContext(JSONObject contextPack) {
        try{
            String project=contextPack.optString("project_id",getActiveProject());
            JSONObject head=contextPack.optJSONObject("head");
            String revision=head==null?"0":String.valueOf(head.optLong("revision",0L));
            String raw=contextPack.toString();
            dao.putContext(new EdgeContextEntity(project,raw,revision,sha256(raw),System.currentTimeMillis()));
        }catch(Exception ignored){}
    }

    public synchronized JSONObject cachedContext() {
        try{
            EdgeContextEntity e=dao.contextForProject(getActiveProject());
            if(e==null) return new JSONObject();
            JSONObject out=new JSONObject(e.payloadJson);
            out.put("source","B_EDGE_ROOM_CACHE");
            out.put("offline",true);
            out.put("mode",getMode());
            out.put("cached_at",e.updatedAt);
            out.put("source_revision",e.sourceRevision);
            out.put("source_hash",e.sourceHash);
            return out;
        }catch(Exception e){ return new JSONObject(); }
    }

    public synchronized void putMemory(String layer,String key,Object value) {
        putMemory(layer,key,value,"LOCAL_DETERMINISTIC","B-EDGE",false,null);
    }

    public synchronized void putMemory(String layer,String key,Object value,String evidenceClass,
                                       String source,boolean pinned,Long expiresAt) {
        String scope=layer==null?"":layer.trim().toUpperCase();
        if(scope.isEmpty()) throw new IllegalArgumentException("INVALID_MEMORY_SCOPE");
        String k=key==null?"":key.trim();
        if(k.isEmpty() || k.length()>180) throw new IllegalArgumentException("INVALID_MEMORY_KEY");
        long now=System.currentTimeMillis();
        dao.putMemory(new EdgeMemoryEntity(
                getActiveProject(),scope,k,String.valueOf(value instanceof String?value:JSONObject.wrap(value)),
                evidenceClass==null?"UNCLASSIFIED":evidenceClass,
                source==null?"B-EDGE":source,pinned,now,now,expiresAt));
    }

    public synchronized JSONObject memorySnapshot() {
        JSONObject all=new JSONObject();
        long now=System.currentTimeMillis();
        try{
            for(String scope:MEMORY_SCOPES){
                JSONArray arr=new JSONArray();
                for(EdgeMemoryEntity m:dao.memoryForScope(getActiveProject(),scope,now,24)){
                    JSONObject e=new JSONObject();
                    e.put("key",m.memoryKey);
                    e.put("value_json",m.valueJson);
                    e.put("evidence_class",m.evidenceClass);
                    e.put("source",m.source);
                    e.put("pinned",m.pinned);
                    e.put("updated_at",m.updatedAt);
                    arr.put(e);
                }
                all.put(scope,arr);
            }
        }catch(Exception ignored){}
        return all;
    }

    public synchronized JSONObject queueJob(String kind,JSONObject payload,boolean requiresPc) {
        return queueJob(kind,payload,requiresPc,50,null);
    }

    public synchronized JSONObject queueJob(String kind,JSONObject payload,boolean requiresPc,
                                            int priority,JSONArray dependencies) {
        String project=getActiveProject();
        String id=UUID.randomUUID().toString();
        String idem="edge-job-"+id;
        String resource=EdgeResourceGovernor.classify(requiresPc,false);
        JSONObject resources=EdgeResourceGovernor.snapshot(context);
        String state=EdgePolicy.nextState(requiresPc,getMode());
        if(EdgeResourceGovernor.shouldDefer(resource,resources) && !requiresPc) state="HOLD";
        if(dependencies!=null && dependencies.length()>0) state="BLOCKED";
        long now=System.currentTimeMillis();
        EdgeJobEntity job=new EdgeJobEntity(
                id,project,kind==null?"generic":kind,
                payload==null?"{}":payload.toString(),state,requiresPc,
                Math.max(0,Math.min(priority,100)),resource,idem,now,now);
        List<EdgeDependencyEntity> deps=new ArrayList<>();
        if(dependencies!=null){
            for(int i=0;i<dependencies.length();i++){
                String d=dependencies.optString(i,"").trim();
                if(!d.isEmpty()) deps.add(new EdgeDependencyEntity(id,d));
            }
        }
        boolean admitted=dao.admitJob(job,deps,EdgePolicy.boundedQueueLimit());
        if(!admitted) throw new IllegalStateException("EDGE_QUEUE_BACKPRESSURE");
        return jobJson(job,resources);
    }

    public synchronized JSONArray pendingJobs() {
        JSONArray out=new JSONArray();
        for(EdgeJobEntity j:dao.pendingJobs(getActiveProject(),EdgePolicy.boundedQueueLimit())){
            out.put(jobJson(j,null));
        }
        return out;
    }

    public synchronized void acknowledgeJob(String localId,JSONObject remoteReceipt) {
        long now=System.currentTimeMillis();
        dao.setJobState(localId,"ACKED",now);
        String receiptRaw=remoteReceipt==null?"{}":remoteReceipt.toString();
        long revision=remoteReceipt==null?0L:remoteReceipt.optLong("revision",0L);
        dao.insertReceipt(new EdgeReceiptEntity(
                "receipt-"+localId,localId,getActiveProject(),"edge-job-"+localId,
                remoteReceipt==null?"ACKED":remoteReceipt.optString("result","ACKED"),
                sha256(receiptRaw),revision,now));
    }

    public synchronized void markJobState(String localId,String state) {
        dao.setJobState(localId,state,System.currentTimeMillis());
    }

    public synchronized int unresolvedDependencies(String localId) {
        return dao.unresolvedDependencies(localId);
    }

    public synchronized void housekeeping() {
        long now=System.currentTimeMillis();
        dao.deleteExpiredMemory(now);
        dao.deleteStaleContext(now-(24L*60L*60L*1000L));
    }

    private JSONObject jobJson(EdgeJobEntity job,JSONObject resources) {
        JSONObject o=new JSONObject();
        try{
            o.put("local_id",job.localId);
            o.put("project_id",job.projectId);
            o.put("kind",job.kind);
            o.put("payload",new JSONObject(job.payloadJson));
            o.put("requires_pc",job.requiresPc);
            o.put("state",job.state);
            o.put("priority",job.priority);
            o.put("resource_class",job.resourceClass);
            o.put("idempotency_key",job.idempotencyKey);
            o.put("created_at",job.createdAt);
            if(resources!=null) o.put("resources",resources);
        }catch(Exception ignored){}
        return o;
    }

    private static String sha256(String s) {
        try{
            MessageDigest md=MessageDigest.getInstance("SHA-256");
            byte[] b=md.digest(s.getBytes(StandardCharsets.UTF_8));
            StringBuilder out=new StringBuilder();
            for(byte x:b) out.append(String.format("%02x",x));
            return out.toString();
        }catch(Exception e){ return ""; }
    }
}
