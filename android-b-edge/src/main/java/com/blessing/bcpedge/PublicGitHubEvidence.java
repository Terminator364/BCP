package com.blessing.bcpedge;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Locale;

public final class PublicGitHubEvidence {
    private PublicGitHubEvidence() {}

    public static JSONObject snapshot(String repository) {
        JSONObject out = new JSONObject();
        try {
            JSONObject commit = getJson("https://api.github.com/repos/" + repository + "/commits/main");
            String sha = commit.optString("sha", "");
            JSONObject runs = getJson("https://api.github.com/repos/" + repository +
                    "/actions/runs?branch=main&per_page=1");
            JSONArray a = runs.optJSONArray("workflow_runs");
            String ci = "NO_RUN";
            if (a != null && a.length() > 0) {
                JSONObject run = a.optJSONObject(0);
                if (run != null) {
                    String status = run.optString("status", "unknown");
                    String conclusion = run.optString("conclusion", "");
                    ci = conclusion.isEmpty() ? status : conclusion;
                }
            }
            out.put("ok", !sha.isEmpty());
            out.put("sha", sha);
            out.put("ci", ci.toUpperCase(Locale.ROOT));
        } catch (Exception ex) {
            try {
                out.put("ok", false);
                out.put("error_class", ex.getClass().getSimpleName());
            } catch (Exception ignored) {}
        }
        return out;
    }

    private static JSONObject getJson(String url) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setRequestMethod("GET");
        c.setConnectTimeout(4000);
        c.setReadTimeout(6000);
        c.setRequestProperty("Accept", "application/vnd.github+json");
        c.setRequestProperty("X-GitHub-Api-Version", "2022-11-28");
        c.setRequestProperty("User-Agent", "BCP-Edge-Observability/1");
        int code = c.getResponseCode();
        if (code >= 400) throw new java.io.IOException("GITHUB_HTTP_" + code);
        try (InputStream in = c.getInputStream()) {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            byte[] buf = new byte[4096];
            int n;
            while ((n = in.read(buf)) >= 0) bytes.write(buf, 0, n);
            return new JSONObject(bytes.toString("UTF-8"));
        }
    }
}
