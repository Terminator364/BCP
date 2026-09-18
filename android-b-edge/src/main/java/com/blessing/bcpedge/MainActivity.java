package com.blessing.bcpedge;

import android.app.Activity;
import android.os.Bundle;
import android.content.SharedPreferences;
import android.graphics.Typeface;
import android.widget.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private EditText server, token, project, completed, next;
    private TextView output;
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private SharedPreferences prefs;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        prefs = getSharedPreferences("bcp", MODE_PRIVATE);

        ScrollView scroll = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        int pad = dp(18);
        root.setPadding(pad, pad, pad, pad);
        scroll.addView(root);

        TextView title = new TextView(this);
        title.setText("BCP Edge · POC V0.1");
        title.setTextSize(24);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        root.addView(title);

        TextView info = new TextView(this);
        info.setText("Client de continuité pour le téléphone ancien. Test LAN contrôlé.");
        info.setPadding(0, dp(6), 0, dp(12));
        root.addView(info);

        server = field(root, "Serveur", prefs.getString("server", "http://192.168.1.2:8765"));
        token = field(root, "Token", prefs.getString("token", ""));
        project = field(root, "Projet", prefs.getString("project", "buildhub"));
        completed = field(root, "Dernière action terminée", "BCP Edge installed");
        next = field(root, "Prochaine action", "Verify restart + resume");

        Button health = button(root, "Tester /health");
        Button resume = button(root, "Reprendre le projet");
        Button checkpoint = button(root, "Enregistrer checkpoint");

        output = new TextView(this);
        output.setTextIsSelectable(true);
        output.setTypeface(Typeface.MONOSPACE);
        output.setPadding(0, dp(14), 0, dp(30));
        root.addView(output);

        health.setOnClickListener(v -> runNet(() ->
            request("GET", cleanBase() + "/health", null, null)));

        resume.setOnClickListener(v -> {
            savePrefs();
            runNet(() -> request("GET",
                cleanBase() + "/v1/projects/" + enc(project.getText().toString()) + "/resume",
                null, null));
        });

        checkpoint.setOnClickListener(v -> {
            savePrefs();
            String idem = "android-" + UUID.randomUUID();
            String body = "{\"type\":\"checkpoint\",\"payload\":{"
                + "\"status\":\"ACTIVE\","
                + "\"last_completed_action\":" + q(completed.getText().toString()) + ","
                + "\"next_action\":" + q(next.getText().toString())
                + "}}";
            runNet(() -> request("POST",
                cleanBase() + "/v1/projects/" + enc(project.getText().toString()) + "/events",
                body, idem));
        });

        setContentView(scroll);
    }

    private EditText field(LinearLayout root, String hint, String value) {
        EditText e = new EditText(this);
        e.setHint(hint);
        e.setText(value);
        e.setSingleLine(false);
        root.addView(e, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT));
        return e;
    }

    private Button button(LinearLayout root, String text) {
        Button b = new Button(this);
        b.setText(text);
        root.addView(b);
        return b;
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    private String cleanBase() {
        String s = server.getText().toString().trim();
        while (s.endsWith("/")) s = s.substring(0, s.length()-1);
        return s;
    }

    private void savePrefs() {
        prefs.edit()
            .putString("server", cleanBase())
            .putString("token", token.getText().toString().trim())
            .putString("project", project.getText().toString().trim())
            .apply();
    }

    private interface NetCall { String call() throws Exception; }

    private void runNet(NetCall c) {
        output.setText("...");
        io.submit(() -> {
            try {
                String r = c.call();
                runOnUiThread(() -> output.setText(r));
            } catch (Exception ex) {
                runOnUiThread(() -> output.setText(
                    "ERROR\n" + ex.getClass().getSimpleName() + ": " + ex.getMessage()));
            }
        });
    }

    private String request(String method, String url, String body, String idem) throws Exception {
        HttpURLConnection c = (HttpURLConnection)new URL(url).openConnection();
        c.setRequestMethod(method);
        c.setConnectTimeout(7000);
        c.setReadTimeout(10000);
        c.setRequestProperty("Accept", "application/json");

        if (!url.endsWith("/health")) {
            c.setRequestProperty("Authorization", "Bearer " + token.getText().toString().trim());
        }
        if (idem != null) c.setRequestProperty("Idempotency-Key", idem);

        if (body != null) {
            c.setDoOutput(true);
            c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            try (OutputStream os = c.getOutputStream()) {
                os.write(body.getBytes(StandardCharsets.UTF_8));
            }
        }

        int code = c.getResponseCode();
        InputStream in = code >= 400 ? c.getErrorStream() : c.getInputStream();
        return "HTTP " + code + "\n" + readAll(in);
    }

    private static String readAll(InputStream in) throws IOException {
        if (in == null) return "";
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buf = new byte[4096];
        int n;
        while ((n = in.read(buf)) >= 0) out.write(buf, 0, n);
        return out.toString("UTF-8");
    }

    private static String q(String s) {
        return "\"" + s.replace("\\","\\\\").replace("\"","\\\"")
                .replace("\n","\\n").replace("\r","\\r") + "\"";
    }

    private static String enc(String s) {
        try { return URLEncoder.encode(s.trim(), "UTF-8"); }
        catch (Exception e) { return s.trim(); }
    }

    @Override protected void onDestroy() {
        super.onDestroy();
        io.shutdownNow();
    }
}
