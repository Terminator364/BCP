package com.blessing.bcpedge;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageInfo;
import android.os.Build;

import androidx.core.app.NotificationCompat;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/**
 * Tiny background release probe.
 *
 * It never downloads an APK in the background and therefore avoids wasting
 * scarce data. It checks only the small public signed-release metadata at a
 * bounded cadence. Actual APK download remains hash/signature verified through
 * UpdateManager and Android still owns final install confirmation.
 */
public final class EdgeBackgroundUpdateProbe {
    private static final String PREFS = "bcp_edge_background_update_probe";
    private static final String MANIFEST =
            "https://raw.githubusercontent.com/Terminator364/BCP/main/release/android.json";
    private static final long SUCCESS_INTERVAL_MS = 6L * 60L * 60L * 1000L;
    private static final long FAILURE_INTERVAL_MS = 30L * 60L * 1000L;
    private static final int MAX_MANIFEST_BYTES = 64 * 1024;
    private static final String CHANNEL = "bcp_edge_updates";
    private static final int NOTIFICATION_ID = 6421;

    private EdgeBackgroundUpdateProbe() {}

    public static JSONObject maybeProbe(Context context, BcpClient client) {
        JSONObject out = new JSONObject();
        SharedPreferences p = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        long now = System.currentTimeMillis();
        long last = p.getLong("last_attempt_ms", 0L);
        boolean lastOk = p.getBoolean("last_attempt_ok", false);
        long interval = lastOk ? SUCCESS_INTERVAL_MS : FAILURE_INTERVAL_MS;
        try {
            if (last > 0 && now - last < interval) {
                out.put("ok", true);
                out.put("skipped", true);
                out.put("next_after_ms", last + interval);
                out.put("update_available", p.getBoolean("update_available", false));
                out.put("latest_version_code", p.getInt("latest_version_code", 0));
                return out;
            }

            p.edit().putLong("last_attempt_ms", now).apply();
            JSONObject m = fetchJson();
            String pkg = m.optString("package_id", "");
            String cert = m.optString("signing_cert_sha256", "");
            String sha = m.optString("apk_sha256", "");
            int latest = m.optInt("version_code", 0);
            String name = m.optString("version_name", "");
            if (!UpdatePolicy.trustedManifest(
                    pkg, UpdateManager.EVERGREEN_PACKAGE,
                    cert, UpdateManager.EVERGREEN_CERT_SHA256,
                    sha, latest)) {
                throw new SecurityException("BACKGROUND_UPDATE_MANIFEST_UNTRUSTED");
            }

            PackageInfo pi = context.getPackageManager()
                    .getPackageInfo(context.getPackageName(), 0);
            long currentLong = Build.VERSION.SDK_INT >= 28
                    ? pi.getLongVersionCode() : pi.versionCode;
            int current = (int)Math.min(Integer.MAX_VALUE, currentLong);
            boolean available = UpdatePolicy.shouldInstall(current, latest);

            p.edit()
                    .putBoolean("last_attempt_ok", true)
                    .putLong("last_success_ms", now)
                    .putInt("latest_version_code", latest)
                    .putString("latest_version_name", name)
                    .putBoolean("update_available", available)
                    .apply();

            out.put("ok", true);
            out.put("skipped", false);
            out.put("current_version_code", current);
            out.put("latest_version_code", latest);
            out.put("latest_version_name", name);
            out.put("update_available", available);
            out.put("probe_source", "PUBLIC_SIGNED_METADATA_GITHUB");
            out.put("apk_background_download", false);

            if (available && p.getInt("last_notified_version_code", 0) != latest) {
                notifyAvailable(context, name);
                p.edit().putInt("last_notified_version_code", latest).apply();
                try {
                    client.recordEvent("EDGE_UPDATE_BACKGROUND_AVAILABLE",
                            current + "->" + latest + "," + name);
                } catch (Exception ignored) {}
            }
        } catch (Exception e) {
            p.edit().putBoolean("last_attempt_ok", false).apply();
            try {
                out.put("ok", false);
                out.put("error", e.getClass().getSimpleName());
                out.put("retry_after_ms", now + FAILURE_INTERVAL_MS);
            } catch (Exception ignored) {}
        }
        return out;
    }

    public static JSONObject cachedStatus(Context context) {
        SharedPreferences p = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        JSONObject out = new JSONObject();
        try {
            out.put("last_attempt_ms", p.getLong("last_attempt_ms", 0L));
            out.put("last_attempt_ok", p.getBoolean("last_attempt_ok", false));
            out.put("last_success_ms", p.getLong("last_success_ms", 0L));
            out.put("latest_version_code", p.getInt("latest_version_code", 0));
            out.put("latest_version_name", p.getString("latest_version_name", ""));
            out.put("update_available", p.getBoolean("update_available", false));
            out.put("policy", "6H_SUCCESS_30M_FAILURE_METADATA_ONLY");
            out.put("automatic_install", false);
            out.put("android_confirmation_required", true);
        } catch (Exception ignored) {}
        return out;
    }

    private static JSONObject fetchJson() throws Exception {
        HttpURLConnection c = (HttpURLConnection)new URL(MANIFEST).openConnection();
        c.setConnectTimeout(4000);
        c.setReadTimeout(7000);
        c.setInstanceFollowRedirects(true);
        c.setRequestProperty("Accept", "application/json");
        try {
            int code = c.getResponseCode();
            if (code < 200 || code >= 300) throw new java.io.IOException("HTTP_" + code);
            try (InputStream in = c.getInputStream()) {
                ByteArrayOutputStream out = new ByteArrayOutputStream();
                byte[] b = new byte[4096];
                int total = 0, n;
                while ((n = in.read(b)) >= 0) {
                    total += n;
                    if (total > MAX_MANIFEST_BYTES) throw new java.io.IOException("MANIFEST_TOO_LARGE");
                    out.write(b, 0, n);
                }
                return new JSONObject(out.toString("UTF-8"));
            }
        } finally {
            c.disconnect();
        }
    }

    private static void notifyAvailable(Context context, String version) {
        NotificationManager nm = context.getSystemService(NotificationManager.class);
        if (nm == null) return;
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel ch = new NotificationChannel(
                    CHANNEL, "BCP Edge mises à jour",
                    NotificationManager.IMPORTANCE_DEFAULT);
            ch.setDescription("Une notification seulement lorsqu’une nouvelle version vérifiée existe.");
            nm.createNotificationChannel(ch);
        }
        Intent open = new Intent(context, MainActivity.class);
        open.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pi = PendingIntent.getActivity(
                context, 6421, open,
                PendingIntent.FLAG_UPDATE_CURRENT
                        | (Build.VERSION.SDK_INT >= 23 ? PendingIntent.FLAG_IMMUTABLE : 0));
        nm.notify(NOTIFICATION_ID,
                new NotificationCompat.Builder(context, CHANNEL)
                        .setSmallIcon(android.R.drawable.stat_sys_download_done)
                        .setContentTitle("BCP Edge · mise à jour disponible")
                        .setContentText((version == null || version.isEmpty() ? "Nouvelle version" : version)
                                + " · ouvre BCP Edge pour la vérifier et l’installer.")
                        .setContentIntent(pi)
                        .setAutoCancel(true)
                        .setOnlyAlertOnce(true)
                        .build());
    }
}
