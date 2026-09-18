package com.blessing.bcpedge;

import android.content.Context;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;

public final class TelemetryStore {
    private final File file;

    public TelemetryStore(Context context) {
        file = new File(context.getFilesDir(), "telemetry_queue.jsonl");
    }

    public synchronized void add(String type, String detail) {
        try {
            JSONObject o = new JSONObject();
            o.put("ts", System.currentTimeMillis());
            o.put("type", type);
            o.put("edge_version", "0.2.2");
            if (detail != null) o.put("detail", detail.length() > 240 ? detail.substring(0,240) : detail);
            try (FileOutputStream fos = new FileOutputStream(file, true)) {
                fos.write((o.toString() + "\n").getBytes("UTF-8"));
            }
        } catch (Exception ignored) {}
    }

    public synchronized JSONArray readAll() throws Exception {
        JSONArray a = new JSONArray();
        if (!file.exists()) return a;
        try (BufferedReader br = new BufferedReader(new InputStreamReader(new FileInputStream(file), "UTF-8"))) {
            String line;
            while ((line = br.readLine()) != null) {
                line = line.trim();
                if (!line.isEmpty()) a.put(new JSONObject(line));
            }
        }
        return a;
    }

    public synchronized void clear() {
        if (file.exists()) file.delete();
    }
}
