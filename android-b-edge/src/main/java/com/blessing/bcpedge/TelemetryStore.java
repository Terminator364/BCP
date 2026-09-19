package com.blessing.bcpedge;

import android.content.Context;
import org.json.JSONArray;
import org.json.JSONObject;

import java.io.*;
import java.util.ArrayList;
import java.util.List;

public final class TelemetryStore {
    private static final long MAX_BYTES = 256L * 1024L;
    private static final int MAX_EVENTS = 600;
    private final File file;

    public TelemetryStore(Context context) {
        file = new File(context.getFilesDir(), "telemetry_queue.jsonl");
    }

    public synchronized void add(String type, String detail) {
        try {
            JSONObject o = new JSONObject();
            o.put("ts", System.currentTimeMillis());
            o.put("type", type);
            o.put("edge_version", "1.0.0");
            if (detail != null) o.put("detail",
                    detail.length() > 240 ? detail.substring(0,240) : detail);
            try (FileOutputStream fos = new FileOutputStream(file, true)) {
                fos.write((o.toString() + "\n").getBytes("UTF-8"));
            }
            compactIfNeeded();
        } catch (Exception ignored) {}
    }

    public synchronized JSONArray readBatch(int max) throws Exception {
        JSONArray a = new JSONArray();
        if (!file.exists() || max <= 0) return a;
        try (BufferedReader br = new BufferedReader(
                new InputStreamReader(new FileInputStream(file), "UTF-8"))) {
            String line;
            while (a.length() < max && (line = br.readLine()) != null) {
                line = line.trim();
                if (!line.isEmpty()) a.put(new JSONObject(line));
            }
        }
        return a;
    }

    public synchronized void acknowledge(int count) throws Exception {
        if (!file.exists() || count <= 0) return;
        List<String> keep = new ArrayList<>();
        try (BufferedReader br = new BufferedReader(
                new InputStreamReader(new FileInputStream(file), "UTF-8"))) {
            String line;
            int skipped = 0;
            while ((line = br.readLine()) != null) {
                if (skipped < count) {
                    skipped++;
                } else if (!line.trim().isEmpty()) {
                    keep.add(line);
                }
            }
        }
        rewrite(keep);
    }

    public synchronized int count() {
        if (!file.exists()) return 0;
        int n = 0;
        try (BufferedReader br = new BufferedReader(
                new InputStreamReader(new FileInputStream(file)))) {
            while (br.readLine() != null) n++;
        } catch (Exception ignored) {}
        return n;
    }

    private void compactIfNeeded() throws Exception {
        if (!file.exists()) return;
        int count = count();
        if (file.length() <= MAX_BYTES && count <= MAX_EVENTS) return;

        List<String> all = new ArrayList<>();
        try (BufferedReader br = new BufferedReader(
                new InputStreamReader(new FileInputStream(file), "UTF-8"))) {
            String line;
            while ((line = br.readLine()) != null) {
                if (!line.trim().isEmpty()) all.add(line);
            }
        }
        int start = Math.max(0, all.size() - MAX_EVENTS);
        List<String> keep = new ArrayList<>(all.subList(start, all.size()));
        while (serializedSize(keep) > MAX_BYTES && keep.size() > 1) {
            keep.remove(0);
        }
        rewrite(keep);
    }

    private static long serializedSize(List<String> lines) throws Exception {
        long total = 0;
        for (String s : lines) total += s.getBytes("UTF-8").length + 1;
        return total;
    }

    private void rewrite(List<String> lines) throws Exception {
        File tmp = new File(file.getParentFile(), file.getName() + ".tmp");
        try (FileOutputStream fos = new FileOutputStream(tmp, false)) {
            for (String s : lines) fos.write((s + "\n").getBytes("UTF-8"));
        }
        if (file.exists() && !file.delete()) throw new IOException("TELEMETRY_REPLACE_DELETE_FAILED");
        if (!tmp.renameTo(file)) {
            try (InputStream in = new FileInputStream(tmp);
                 OutputStream out = new FileOutputStream(file)) {
                byte[] b = new byte[8192];
                int n;
                while ((n = in.read(b)) >= 0) out.write(b,0,n);
            }
            tmp.delete();
        }
    }
}
