package com.blessing.bcpedge;

import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONArray;
import org.json.JSONObject;

import java.util.UUID;

public final class EdgeOrchestrator {
    private static final String PREFS = "bcp_edge_orchestrator";
    private final SharedPreferences prefs;

    public EdgeOrchestrator(Context context) {
        prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public synchronized void setMode(String mode) {
        prefs.edit()
                .putString("mode", mode)
                .putLong("mode_at", System.currentTimeMillis())
                .apply();
    }

    public synchronized String getMode() {
        return prefs.getString("mode", "EDGE_ONLY");
    }

    public synchronized void cacheContext(JSONObject context) {
        try {
            prefs.edit()
                    .putString("context_pack", context.toString())
                    .putLong("context_at", System.currentTimeMillis())
                    .apply();
        } catch (Exception ignored) {}
    }

    public synchronized JSONObject cachedContext() {
        try {
            String raw = prefs.getString("context_pack", "");
            JSONObject out = raw.isEmpty() ? new JSONObject() : new JSONObject(raw);
            out.put("source", "B_EDGE_CACHE");
            out.put("offline", true);
            out.put("mode", getMode());
            out.put("cached_at", prefs.getLong("context_at", 0));
            return out;
        } catch (Exception e) {
            return new JSONObject();
        }
    }

    public synchronized void putMemory(String layer, String key, Object value) {
        try {
            JSONObject all = new JSONObject(prefs.getString("memory", "{}"));
            JSONObject bucket = all.optJSONObject(layer);
            if (bucket == null) bucket = new JSONObject();
            JSONObject entry = new JSONObject();
            entry.put("value", value);
            entry.put("updated_at", System.currentTimeMillis());
            bucket.put(key, entry);
            all.put(layer, bucket);
            compactMemory(all);
            prefs.edit().putString("memory", all.toString()).apply();
        } catch (Exception ignored) {}
    }

    public synchronized JSONObject memorySnapshot() {
        try { return new JSONObject(prefs.getString("memory", "{}")); }
        catch (Exception e) { return new JSONObject(); }
    }

    public synchronized JSONObject queueJob(String kind, JSONObject payload, boolean requiresPc) {
        try {
            JSONArray q = new JSONArray(prefs.getString("job_queue", "[]"));
            JSONObject job = new JSONObject();
            job.put("local_id", UUID.randomUUID().toString());
            job.put("kind", kind);
            job.put("payload", payload);
            job.put("requires_pc", requiresPc);
            job.put("state", EdgePolicy.nextState(requiresPc, getMode()));
            job.put("created_at", System.currentTimeMillis());
            q.put(job);
            while (q.length() > EdgePolicy.boundedQueueLimit()) {
                JSONArray n = new JSONArray();
                for (int i = 1; i < q.length(); i++) n.put(q.get(i));
                q = n;
            }
            prefs.edit().putString("job_queue", q.toString()).apply();
            return job;
        } catch (Exception e) {
            return new JSONObject();
        }
    }

    public synchronized JSONArray pendingJobs() {
        try { return new JSONArray(prefs.getString("job_queue", "[]")); }
        catch (Exception e) { return new JSONArray(); }
    }

    public synchronized void replaceJobs(JSONArray q) {
        prefs.edit().putString("job_queue", q.toString()).apply();
    }

    private void compactMemory(JSONObject all) throws Exception {
        int count = 0;
        JSONArray keys = all.names();
        if (keys == null) return;
        for (int i = 0; i < keys.length(); i++) {
            JSONObject b = all.optJSONObject(keys.getString(i));
            if (b != null && b.names() != null) count += b.names().length();
        }
        if (count <= EdgePolicy.boundedMemoryEntries()) return;
        // Conservative pressure response: retain project/policy/operating state;
        // trim history first. Durable PC copy remains authoritative after sync.
        JSONObject history = all.optJSONObject("HISTORY");
        if (history != null) {
            JSONArray hk = history.names();
            if (hk != null) {
                int remove = Math.min(hk.length(), count - EdgePolicy.boundedMemoryEntries());
                for (int i = 0; i < remove; i++) history.remove(hk.getString(i));
            }
        }
    }
}
