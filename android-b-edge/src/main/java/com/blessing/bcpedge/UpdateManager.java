package com.blessing.bcpedge;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;

import androidx.core.content.FileProvider;

import org.json.JSONObject;

import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class UpdateManager {
    public interface Listener { void onUpdateStatus(String status); }

    static final String EVERGREEN_PACKAGE = "com.blessing.bcpedge.evergreen";
    static final String EVERGREEN_CERT_SHA256 =
            "0baad4749918f1b2430bbbf3f5ddbdb1de4908b017910d67aef2cb987ddeb617";
    private static final long MAX_APK_BYTES = 50L * 1024L * 1024L;
    private static final String PREFS = "bcp_edge_updates";

    private final Activity activity;
    private final BcpClient client;
    private final SharedPreferences prefs;
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private final Listener listener;
    private volatile boolean checking = false;

    public UpdateManager(Activity activity, BcpClient client, Listener listener) {
        this.activity = activity;
        this.client = client;
        this.listener = listener;
        this.prefs = activity.getSharedPreferences(PREFS, Activity.MODE_PRIVATE);
    }

    public void reconcileAfterLaunch() {
        io.submit(() -> {
            try {
                verifyInstalledIdentity();
                int current = currentVersionCode();
                int pending = prefs.getInt("pending_version_code", 0);
                if (pending > 0 && current >= pending) {
                    cleanupUpdateCache();
                    String name = prefs.getString("pending_version_name", "");
                    prefs.edit().clear().apply();
                    client.recordEvent("EDGE_UPDATE_COMMITTED",
                            "version_code=" + current + (name.isEmpty() ? "" : ",version=" + name));
                    client.flushTelemetry();
                    status("B-EDGE EVERGREEN " + currentVersionName() + " ACTIF");
                }
            } catch (Exception ex) {
                client.recordEvent("EDGE_UPDATE_RECONCILE_FAIL", safe(ex));
            }
        });
    }

    public void check() { check(false); }

    public void check(boolean userInitiated) {
        if (checking) {
            if (userInitiated) status("VÉRIFICATION DÉJÀ EN COURS");
            return;
        }
        checking = true;
        io.submit(() -> {
            try {
                verifyInstalledIdentity();
                JSONObject m = getJsonAuthenticated(client.getServer() + "/v1/edge/update");
                validateManifest(m);

                int latest = m.getInt("version_code");
                int current = currentVersionCode();
                if (!UpdatePolicy.shouldInstall(current, latest)) {
                    cleanupUpdateCache();
                    if (userInitiated) status("B-EDGE EST À JOUR · " + currentVersionName());
                    client.recordEvent("EDGE_UPDATE_NOT_NEEDED", "version_code=" + current);
                    return;
                }

                status("MISE À JOUR B-EDGE " + m.optString("version_name", "") + " DISPONIBLE");
                client.recordEvent("EDGE_UPDATE_AVAILABLE",
                        current + "->" + latest);

                if (Build.VERSION.SDK_INT >= 26 &&
                        !activity.getPackageManager().canRequestPackageInstalls()) {
                    status("AUTORISE B-EDGE À INSTALLER SES MISES À JOUR UNE FOIS");
                    Intent settings = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                            Uri.parse("package:" + activity.getPackageName()));
                    activity.startActivity(settings);
                    return;
                }

                File dir = new File(activity.getCacheDir(), "updates");
                if (!dir.exists() && !dir.mkdirs()) throw new IOException("UPDATE_CACHE_CREATE_FAILED");
                cleanupUpdateCache();
                File part = new File(dir, "bcp-edge-update.apk.part");
                File apk = new File(dir, "bcp-edge-update.apk");

                client.recordEvent("EDGE_UPDATE_DOWNLOAD_START", "version_code=" + latest);
                downloadAuthenticated(client.getServer() + "/v1/edge/update/apk", part);

                String actual = sha256(part);
                String expected = m.getString("apk_sha256").toLowerCase(Locale.ROOT);
                if (!actual.equals(expected)) {
                    part.delete();
                    throw new SecurityException("APK_SHA256_MISMATCH");
                }

                verifyArchiveIdentity(part, m);
                if (!part.renameTo(apk)) {
                    copyFile(part, apk);
                    part.delete();
                }

                prefs.edit()
                        .putInt("pending_version_code", latest)
                        .putString("pending_version_name", m.optString("version_name", ""))
                        .putString("pending_apk_sha256", expected)
                        .apply();

                client.recordEvent("EDGE_UPDATE_VERIFIED",
                        "version_code=" + latest + ",sha256=" + expected.substring(0, 12));
                client.flushTelemetry();

                status("MISE À JOUR VÉRIFIÉE — CONFIRME L'INSTALLATION");
                Uri uri = FileProvider.getUriForFile(activity,
                        activity.getPackageName() + ".files", apk);
                Intent install = new Intent(Intent.ACTION_VIEW);
                install.setDataAndType(uri, "application/vnd.android.package-archive");
                install.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
                activity.startActivity(install);
            } catch (Exception ex) {
                client.recordEvent("EDGE_UPDATE_FAIL", safe(ex));
                client.flushTelemetry();
                if (userInitiated) status("ÉCHEC MISE À JOUR: " + safe(ex));
            } finally {
                checking = false;
            }
        });
    }

    private JSONObject getJsonAuthenticated(String u) throws Exception {
        ensureConnected();
        HttpURLConnection c = (HttpURLConnection)new URL(u).openConnection();
        c.setConnectTimeout(3000);
        c.setReadTimeout(7000);
        c.setUseCaches(false);
        c.setRequestProperty("Accept", "application/json");
        c.setRequestProperty("Authorization", "Bearer " + client.getToken());
        int code = c.getResponseCode();
        InputStream in = code >= 400 ? c.getErrorStream() : c.getInputStream();
        String raw = readAll(in);
        if (code >= 400) throw new IOException("HTTP_" + code + ": " + raw);
        return new JSONObject(raw);
    }

    private void downloadAuthenticated(String u, File out) throws Exception {
        ensureConnected();
        HttpURLConnection c = (HttpURLConnection)new URL(u).openConnection();
        c.setConnectTimeout(5000);
        c.setReadTimeout(30000);
        c.setUseCaches(false);
        c.setRequestProperty("Authorization", "Bearer " + client.getToken());
        int code = c.getResponseCode();
        if (code >= 400) {
            String raw = readAll(c.getErrorStream());
            throw new IOException("HTTP_" + code + ": " + raw);
        }
        long announced = c.getContentLengthLong();
        if (announced > MAX_APK_BYTES) throw new IOException("APK_TOO_LARGE");
        long total = 0;
        try (InputStream in = c.getInputStream();
             OutputStream os = new FileOutputStream(out)) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) >= 0) {
                total += n;
                if (total > MAX_APK_BYTES) throw new IOException("APK_TOO_LARGE");
                os.write(buf, 0, n);
            }
        }
        if (total <= 0) throw new IOException("APK_EMPTY");
    }

    private void validateManifest(JSONObject m) throws Exception {
        if (!m.optBoolean("ok", false)) throw new IOException("EDGE_MANIFEST_NOT_OK");
        String packageId = m.optString("package_id", "");
        String cert = m.optString("signing_cert_sha256", "").toLowerCase(Locale.ROOT);
        String sha = m.optString("apk_sha256", "").toLowerCase(Locale.ROOT);
        int versionCode = m.optInt("version_code", 0);
        if (!UpdatePolicy.trustedManifest(packageId, EVERGREEN_PACKAGE,
                cert, EVERGREEN_CERT_SHA256, sha, versionCode)) {
            throw new SecurityException("EDGE_MANIFEST_TRUST_POLICY_FAILED");
        }
    }

    private void verifyInstalledIdentity() throws Exception {
        if (!EVERGREEN_PACKAGE.equals(activity.getPackageName()))
            throw new SecurityException("EVERGREEN_PACKAGE_ID_MISMATCH");
        String actual = installedCertSha256();
        if (!EVERGREEN_CERT_SHA256.equals(actual))
            throw new SecurityException("EVERGREEN_SIGNATURE_MISMATCH");
    }

    private void verifyArchiveIdentity(File apk, JSONObject manifest) throws Exception {
        PackageManager pm = activity.getPackageManager();
        int flags = Build.VERSION.SDK_INT >= 28
                ? PackageManager.GET_SIGNING_CERTIFICATES : PackageManager.GET_SIGNATURES;
        PackageInfo info = pm.getPackageArchiveInfo(apk.getAbsolutePath(), flags);
        if (info == null) throw new SecurityException("APK_PACKAGE_INFO_MISSING");
        if (!EVERGREEN_PACKAGE.equals(info.packageName))
            throw new SecurityException("APK_PACKAGE_ID_MISMATCH");
        long archiveCode = Build.VERSION.SDK_INT >= 28 ? info.getLongVersionCode() : info.versionCode;
        if (archiveCode != manifest.getLong("version_code"))
            throw new SecurityException("APK_VERSION_CODE_MISMATCH");
        String cert = certSha256(info);
        if (!EVERGREEN_CERT_SHA256.equals(cert))
            throw new SecurityException("APK_SIGNING_CERT_MISMATCH");
    }

    private String installedCertSha256() throws Exception {
        PackageManager pm = activity.getPackageManager();
        int flags = Build.VERSION.SDK_INT >= 28
                ? PackageManager.GET_SIGNING_CERTIFICATES : PackageManager.GET_SIGNATURES;
        PackageInfo info = pm.getPackageInfo(activity.getPackageName(), flags);
        return certSha256(info);
    }

    private static String certSha256(PackageInfo info) throws Exception {
        Signature[] signatures;
        if (Build.VERSION.SDK_INT >= 28) {
            if (info.signingInfo == null) throw new SecurityException("SIGNING_INFO_MISSING");
            signatures = info.signingInfo.hasMultipleSigners()
                    ? info.signingInfo.getApkContentsSigners()
                    : info.signingInfo.getSigningCertificateHistory();
        } else {
            signatures = info.signatures;
        }
        if (signatures == null || signatures.length == 0)
            throw new SecurityException("SIGNATURE_MISSING");
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        md.update(signatures[0].toByteArray());
        return hex(md.digest());
    }

    private int currentVersionCode() throws Exception {
        PackageInfo p = activity.getPackageManager().getPackageInfo(activity.getPackageName(), 0);
        long code = Build.VERSION.SDK_INT >= 28 ? p.getLongVersionCode() : p.versionCode;
        return (int)Math.min(Integer.MAX_VALUE, code);
    }

    private String currentVersionName() throws Exception {
        PackageInfo p = activity.getPackageManager().getPackageInfo(activity.getPackageName(), 0);
        return p.versionName == null ? "" : p.versionName;
    }

    private void cleanupUpdateCache() {
        File dir = new File(activity.getCacheDir(), "updates");
        File[] files = dir.listFiles();
        if (files == null) return;
        for (File f : files) {
            String n = f.getName();
            if (n.equals("bcp-edge-update.apk") || n.equals("bcp-edge-update.apk.part")) {
                try { f.delete(); } catch (Exception ignored) {}
            }
        }
    }

    private void ensureConnected() throws IOException {
        if (client.getServer().isEmpty() || client.getToken().isEmpty())
            throw new IOException("NOT_PAIRED");
    }

    private static void copyFile(File src, File dst) throws IOException {
        try (InputStream in = new FileInputStream(src);
             OutputStream out = new FileOutputStream(dst)) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) >= 0) out.write(buf, 0, n);
        }
    }

    private static String sha256(File file) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        try (InputStream in = new FileInputStream(file)) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) >= 0) md.update(buf, 0, n);
        }
        return hex(md.digest());
    }

    private static String hex(byte[] bytes) {
        StringBuilder sb = new StringBuilder();
        for (byte b : bytes) sb.append(String.format(Locale.ROOT, "%02x", b & 0xff));
        return sb.toString();
    }

    private static String readAll(InputStream in) throws IOException {
        if (in == null) return "";
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] b = new byte[4096];
        int n;
        while ((n = in.read(b)) >= 0) out.write(b, 0, n);
        return out.toString("UTF-8");
    }

    private static String safe(Exception ex) {
        String m = ex.getMessage();
        if (m == null || m.isEmpty()) m = ex.getClass().getSimpleName();
        if (m.length() > 180) m = m.substring(0, 180);
        return m;
    }

    private void status(String s) {
        activity.runOnUiThread(() -> listener.onUpdateStatus(s));
    }

    public void close() { io.shutdownNow(); }
}
