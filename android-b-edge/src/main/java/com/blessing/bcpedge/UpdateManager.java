package com.blessing.bcpedge;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import androidx.core.content.FileProvider;
import org.json.JSONObject;

import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class UpdateManager {
    public interface Listener { void onUpdateStatus(String status); }

    private static final String MANIFEST_URL =
            "https://raw.githubusercontent.com/Terminator364/BCP/main/release/android.json";
    private final Activity activity;
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private final Listener listener;
    private volatile boolean checking = false;

    public UpdateManager(Activity activity, Listener listener) {
        this.activity = activity;
        this.listener = listener;
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
                JSONObject m = getJson(MANIFEST_URL);
                int latest = m.optInt("version_code", 0);
                int current = activity.getPackageManager()
                        .getPackageInfo(activity.getPackageName(), 0).versionCode;
                if (latest <= current) {
                    if (userInitiated) status("BCP EDGE EST À JOUR");
                    return;
                }

                status("MISE À JOUR B-EDGE DISPONIBLE");
                if (Build.VERSION.SDK_INT >= 26 &&
                        !activity.getPackageManager().canRequestPackageInstalls()) {
                    status("AUTORISE BCP EDGE À INSTALLER SES MISES À JOUR UNE FOIS");
                    Intent s = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                            Uri.parse("package:" + activity.getPackageName()));
                    activity.startActivity(s);
                    return;
                }

                String apkUrl = m.optString("apk_url", "");
                String apkSha256 = m.optString("apk_sha256", "").toLowerCase();
                if (apkUrl.isEmpty() || apkSha256.length() != 64) {
                    status("MISE À JOUR EDGE PAS ENCORE PUBLIÉE/SIGNÉE");
                    return;
                }
                File apk = new File(activity.getExternalCacheDir(), "bcp-edge-update.apk");
                download(apkUrl, apk);
                String actual = sha256(apk);
                if (!actual.equals(apkSha256)) {
                    if (apk.exists()) apk.delete();
                    throw new SecurityException("APK_SHA256_MISMATCH");
                }
                status("MISE À JOUR TÉLÉCHARGÉE ET VÉRIFIÉE — CONFIRME L'INSTALLATION");
                Uri uri = FileProvider.getUriForFile(activity,
                        activity.getPackageName() + ".files", apk);
                Intent i = new Intent(Intent.ACTION_VIEW);
                i.setDataAndType(uri, "application/vnd.android.package-archive");
                i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
                activity.startActivity(i);
            } catch (Exception ex) {
                // Update failures never block BCP continuity, but user-triggered checks are visible.
                if (userInitiated) status("ÉCHEC MISE À JOUR: " + ex.getClass().getSimpleName());
            } finally {
                checking = false;
            }
        });
    }

    private void status(String s) {
        activity.runOnUiThread(() -> listener.onUpdateStatus(s));
    }

    private static JSONObject getJson(String u) throws Exception {
        HttpURLConnection c = (HttpURLConnection)new URL(u).openConnection();
        c.setConnectTimeout(4000);
        c.setReadTimeout(5000);
        c.setUseCaches(false);
        try (InputStream in = c.getInputStream()) {
            return new JSONObject(readAll(in));
        }
    }

    private static void download(String u, File out) throws Exception {
        HttpURLConnection c = (HttpURLConnection)new URL(u).openConnection();
        c.setConnectTimeout(7000);
        c.setReadTimeout(15000);
        try (InputStream in = c.getInputStream();
             OutputStream os = new FileOutputStream(out)) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) >= 0) os.write(buf,0,n);
        }
    }

    private static String sha256(File file) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        try (InputStream in = new FileInputStream(file)) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) >= 0) md.update(buf, 0, n);
        }
        StringBuilder sb = new StringBuilder();
        for (byte b : md.digest()) sb.append(String.format("%02x", b & 0xff));
        return sb.toString();
    }

    private static String readAll(InputStream in) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] b = new byte[4096];
        int n;
        while ((n=in.read(b))>=0) out.write(b,0,n);
        return out.toString("UTF-8");
    }

    public void close() { io.shutdownNow(); }
}
