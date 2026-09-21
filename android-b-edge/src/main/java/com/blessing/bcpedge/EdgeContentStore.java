package com.blessing.bcpedge;

import android.content.Context;
import android.os.StatFs;

import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * App-private content-addressed store for the dedicated phone node.
 *
 * The phone's storage is useful as a durable cache, but BCP must never consume
 * it blindly. The quota is adaptive and leaves most device storage available.
 * Secrets are not written through this API.
 */
public final class EdgeContentStore {
    private static final long MIN_QUOTA = 512L * 1024L * 1024L;
    private static final long MAX_QUOTA = 8L * 1024L * 1024L * 1024L;
    private static final int MAX_JSON_BYTES = 8 * 1024 * 1024;

    private final File root;

    public EdgeContentStore(Context context) {
        root = new File(context.getFilesDir(), "bcp-edge-content-v1");
        if (!root.isDirectory()) root.mkdirs();
    }

    public synchronized JSONObject putJson(String namespace, String logicalKey, JSONObject value) {
        JSONObject out = new JSONObject();
        try {
            byte[] bytes = value.toString().getBytes(StandardCharsets.UTF_8);
            if (bytes.length > MAX_JSON_BYTES) {
                out.put("stored", false);
                out.put("reason", "OBJECT_TOO_LARGE");
                return out;
            }
            String ns = safe(namespace);
            String key = sha256(logicalKey == null ? "" : logicalKey);
            File dir = new File(root, ns);
            if (!dir.isDirectory() && !dir.mkdirs()) {
                out.put("stored", false);
                out.put("reason", "CACHE_DIR_UNAVAILABLE");
                return out;
            }
            File finalFile = new File(dir, key + ".json");
            File tmp = new File(dir, key + ".tmp");
            try (FileOutputStream fos = new FileOutputStream(tmp, false)) {
                fos.write(bytes);
                fos.getFD().sync();
            }
            if (finalFile.exists() && !finalFile.delete()) {
                tmp.delete();
                out.put("stored", false);
                out.put("reason", "REPLACE_DELETE_FAILED");
                return out;
            }
            if (!tmp.renameTo(finalFile)) {
                tmp.delete();
                out.put("stored", false);
                out.put("reason", "ATOMIC_RENAME_FAILED");
                return out;
            }
            trimToQuota();
            out.put("stored", true);
            out.put("sha256", sha256(bytes));
            out.put("bytes", bytes.length);
            out.put("namespace", ns);
            return out;
        } catch (Exception ex) {
            try {
                out.put("stored", false);
                out.put("reason", ex.getClass().getSimpleName());
            } catch (Exception ignored) {}
            return out;
        }
    }

    public synchronized JSONObject status() {
        JSONObject out = new JSONObject();
        try {
            long used = size(root);
            long quota = quotaBytes();
            StatFs fs = new StatFs(root.getAbsolutePath());
            out.put("path_class", "APP_PRIVATE");
            out.put("used_bytes", used);
            out.put("quota_bytes", quota);
            out.put("quota_gib", roundGiB(quota));
            out.put("free_device_bytes", fs.getAvailableBytes());
            out.put("file_count", countFiles(root));
            out.put("within_quota", used <= quota);
            out.put("policy", "ADAPTIVE_MAX_8_GIB_LEAVES_DEVICE_HEADROOM");
        } catch (Exception ignored) {}
        return out;
    }

    private long quotaBytes() {
        try {
            StatFs fs = new StatFs(root.getAbsolutePath());
            long total = fs.getTotalBytes();
            long available = fs.getAvailableBytes();
            long byTotal = Math.max(MIN_QUOTA, total / 8L);
            long byAvailable = Math.max(128L * 1024L * 1024L, available / 2L);
            return Math.min(MAX_QUOTA, Math.min(byTotal, byAvailable));
        } catch (Exception ex) {
            return MIN_QUOTA;
        }
    }

    private void trimToQuota() {
        long quota = quotaBytes();
        long used = size(root);
        if (used <= quota) return;
        File[] files = root.listFiles();
        if (files == null) return;
        java.util.ArrayList<File> leaves = new java.util.ArrayList<>();
        collectFiles(root, leaves);
        leaves.sort((a,b) -> Long.compare(a.lastModified(), b.lastModified()));
        for (File file : leaves) {
            if (used <= quota) break;
            long n = file.length();
            if (file.delete()) used = Math.max(0L, used - n);
        }
    }

    private static void collectFiles(File dir, java.util.List<File> out) {
        File[] children = dir.listFiles();
        if (children == null) return;
        for (File f : children) {
            if (f.isDirectory()) collectFiles(f, out);
            else out.add(f);
        }
    }

    private static long size(File dir) {
        if (dir == null || !dir.exists()) return 0L;
        if (dir.isFile()) return dir.length();
        long total = 0L;
        File[] children = dir.listFiles();
        if (children != null) for (File f : children) total += size(f);
        return total;
    }

    private static int countFiles(File dir) {
        if (dir == null || !dir.exists()) return 0;
        if (dir.isFile()) return 1;
        int total = 0;
        File[] children = dir.listFiles();
        if (children != null) for (File f : children) total += countFiles(f);
        return total;
    }

    private static String safe(String value) {
        String s = value == null ? "general" : value.replaceAll("[^A-Za-z0-9._-]", "_");
        return s.isEmpty() ? "general" : s.substring(0, Math.min(48, s.length()));
    }

    private static String sha256(String value) {
        return sha256(value.getBytes(StandardCharsets.UTF_8));
    }

    private static String sha256(byte[] value) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] digest = md.digest(value);
            StringBuilder out = new StringBuilder(64);
            for (byte b : digest) out.append(String.format("%02x", b & 0xff));
            return out.toString();
        } catch (Exception ex) {
            throw new IllegalStateException("sha256_unavailable", ex);
        }
    }

    private static double roundGiB(long bytes) {
        return Math.round((bytes / (1024d * 1024d * 1024d)) * 100d) / 100d;
    }
}
