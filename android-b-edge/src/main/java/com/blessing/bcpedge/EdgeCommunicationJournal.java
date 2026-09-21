package com.blessing.bcpedge;

import android.content.Context;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;

/**
 * Small app-private append-only communication journal.
 *
 * It records transport decisions/receipts without storing bearer tokens or
 * arbitrary payloads. Remote delivery is represented only when a provider
 * receipt is explicitly supplied by the caller.
 */
public final class EdgeCommunicationJournal {
    private static final long ROTATE_BYTES = 2L * 1024L * 1024L;
    private static final int MAX_DETAIL = 240;
    private final File file;
    private final File previous;

    public EdgeCommunicationJournal(Context context) {
        File dir = new File(context.getFilesDir(), "bcp-edge-communication");
        if (!dir.isDirectory()) dir.mkdirs();
        file = new File(dir, "communication.jsonl");
        previous = new File(dir, "communication.prev.jsonl");
    }

    public synchronized void append(String event, String route, String detail,
                                    String providerReceipt) {
        try {
            rotateIfNeeded();
            JSONObject row = new JSONObject();
            row.put("at_ms", System.currentTimeMillis());
            row.put("event", safe(event, 64));
            row.put("route", safe(route, 64));
            row.put("detail", safe(detail, MAX_DETAIL));
            boolean ack = providerReceipt != null && !providerReceipt.trim().isEmpty();
            row.put("provider_ack", ack);
            if (ack) row.put("provider_receipt_ref", safe(providerReceipt, 96));
            byte[] bytes = (row.toString() + "\n").getBytes(StandardCharsets.UTF_8);
            try (FileOutputStream out = new FileOutputStream(file, true)) {
                out.write(bytes);
                out.getFD().sync();
            }
        } catch (Exception ignored) {}
    }

    public synchronized JSONObject summary() {
        JSONObject out = new JSONObject();
        try {
            int lines = 0;
            String last = "";
            if (file.isFile()) {
                try (BufferedReader r = new BufferedReader(new InputStreamReader(
                        new FileInputStream(file), StandardCharsets.UTF_8))) {
                    String line;
                    while ((line = r.readLine()) != null) {
                        if (!line.trim().isEmpty()) {
                            lines++;
                            last = line;
                        }
                    }
                }
            }
            out.put("state", "ACTIVE");
            out.put("path_class", "APP_PRIVATE");
            out.put("entries_current_segment", lines);
            out.put("bytes_current_segment", file.isFile() ? file.length() : 0L);
            out.put("rotated_segment_present", previous.isFile());
            out.put("last_event", last.isEmpty() ? new JSONObject() : new JSONObject(last));
            out.put("remote_delivery_truth_rule",
                    "PROVIDER_ACK_REQUIRED; LOCAL_QUEUE_ACCEPTANCE_IS_NOT_REMOTE_DELIVERY");
        } catch (Exception ignored) {}
        return out;
    }

    private void rotateIfNeeded() {
        if (!file.isFile() || file.length() < ROTATE_BYTES) return;
        if (previous.exists()) previous.delete();
        file.renameTo(previous);
    }

    private static String safe(String raw, int max) {
        if (raw == null) return "";
        String s = raw.replaceAll("[\\r\\n\\t]", " ").trim();
        if (s.length() > max) s = s.substring(0, max);
        // Defend against accidental credential logging.
        s = s.replaceAll("(?i)Bearer\\s+[A-Za-z0-9._~+\\-/=]+", "Bearer [REDACTED]");
        s = s.replaceAll("\\b\\d{6,12}:[A-Za-z0-9_-]{20,}\\b", "[REDACTED_TOKEN]");
        return s;
    }
}
