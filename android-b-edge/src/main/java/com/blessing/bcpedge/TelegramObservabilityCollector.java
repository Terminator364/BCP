package com.blessing.bcpedge;

import android.content.Context;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.Locale;

public final class TelegramObservabilityCollector {
    private static final String BCP_REPO = "Terminator364/BCP";
    private static final String BUILDHUB_REPO = "Terminator364/BuildHub";
    private final BcpClient bcp;

    public TelegramObservabilityCollector(Context context) {
        this.bcp = new BcpClient(context.getApplicationContext());
    }

    public String render(String raw) {
        TelegramObservabilityPolicy.Command cmd = TelegramObservabilityPolicy.parse(raw);
        try {
            switch (cmd.kind) {
                case START:
                    return "BCP Telegram Observability · LECTURE SEULE\n" +
                            "Identité approuvée. Utilise /status, /project, /last, /ci, /holds ou /job.\n\n" +
                            status();
                case STATUS: return status();
                case PROJECT: return project(cmd.argument);
                case JOB: return job(cmd.argument);
                case LAST: return last();
                case CI: return ci();
                case HOLDS: return holds();
                case HELP: return help();
                default: return "Commande non reconnue.\n\n" + help();
            }
        } catch (Exception ex) {
            return "BCP OBSERVABILITY\nÉtat: SOURCE_TEMPORAIREMENT_INDISPONIBLE\n" +
                    "Classe: " + ex.getClass().getSimpleName() +
                    "\nAucune progression n'est inventée.";
        }
    }

    private String status() {
        StringBuilder s = new StringBuilder();
        s.append("BCP OBSERVABILITY · READ ONLY\n");
        s.append("Project: ").append(bcp.getProject()).append("\n");
        boolean serverSeen = false;
        try {
            JSONObject h = bcp.health();
            serverSeen = h.optBoolean("ok", false);
            s.append("BCP runtime: ").append(serverSeen ? "HEALTHY" : "UNHEALTHY");
            String version = h.optString("version", "");
            if (!version.isEmpty()) s.append(" · v").append(version);
            s.append("\n");
        } catch (Exception ex) {
            s.append("BCP runtime: UNREACHABLE\n");
        }

        try {
            JSONObject resume = bcp.resume();
            JSONObject head = resume.optJSONObject("head");
            if (head != null) {
                s.append("Project revision: ").append(head.optLong("revision", 0)).append("\n");
                JSONObject payload = head.optJSONObject("payload");
                if (payload != null) {
                    String state = payload.optString("status", "");
                    if (!state.isEmpty()) s.append("Project state: ").append(safeState(state)).append("\n");
                }
            }
            if (resume.optBoolean("offline", false)) s.append("Project source: LOCAL_CACHE\n");
        } catch (Exception ex) {
            s.append("Project state: UNAVAILABLE\n");
        }

        try {
            JSONObject o = bcp.orchestratorStatus();
            s.append("Orchestrator: ").append(safeState(o.optString("operating_mode",
                    o.optString("mode", "OBSERVED")))).append("\n");
            if (o.has("queued_jobs")) s.append("Queued jobs: ").append(o.optInt("queued_jobs", 0)).append("\n");
        } catch (Exception ex) {
            s.append("Orchestrator: ").append(serverSeen ? "UNAVAILABLE" : "EDGE_ONLY_OR_UNKNOWN").append("\n");
        }

        JSONObject gh = PublicGitHubEvidence.snapshot(BCP_REPO);
        if (gh.optBoolean("ok", false)) {
            s.append("GitHub main: ").append(shortSha(gh.optString("sha", ""))).append("\n");
            s.append("CI latest: ").append(safeState(gh.optString("ci", "UNKNOWN"))).append("\n");
        } else {
            s.append("GitHub: UNAVAILABLE\n");
        }
        s.append("ChatGPT: ").append(TelegramObservabilityPolicy.chatVisibilityState(
                false, false, false, false)).append("\n");
        s.append("Spend policy: 0.00 USD\n");
        s.append("Truth mode: EXTERNAL_EVIDENCE_ONLY");
        return s.toString();
    }

    private String project(String argument) {
        String id = argument == null ? "" : argument.trim();
        if (id.isEmpty() || id.equalsIgnoreCase(bcp.getProject())) {
            try {
                JSONObject r = bcp.resume();
                JSONObject head = r.optJSONObject("head");
                StringBuilder s = new StringBuilder("PROJECT ").append(bcp.getProject()).append("\n");
                if (head == null) return s.append("Head: UNAVAILABLE").toString();
                s.append("Revision: ").append(head.optLong("revision", 0)).append("\n");
                JSONObject payload = head.optJSONObject("payload");
                if (payload != null) {
                    appendIfPresent(s, "State", payload.optString("status", ""));
                    appendIfPresent(s, "Last committed", payload.optString("last_completed_action", ""));
                    appendIfPresent(s, "Next", payload.optString("next_action", ""));
                }
                if (r.optBoolean("offline", false)) s.append("Source: LOCAL_CACHE\n");
                return s.toString().trim();
            } catch (Exception ex) {
                return "PROJECT " + bcp.getProject() + "\nState: UNAVAILABLE";
            }
        }

        JSONArray registry = bcp.projectRegistry();
        for (int i = 0; i < registry.length(); i++) {
            JSONObject p = registry.optJSONObject(i);
            if (p != null && id.equalsIgnoreCase(p.optString("project_id", ""))) {
                return "PROJECT " + p.optString("project_id", id) +
                        "\nState: " + safeState(p.optString("status", "UNKNOWN")) +
                        "\nRevision: " + p.optLong("head_revision", 0) +
                        "\nSource: B_EDGE_DURABLE_REGISTRY";
            }
        }
        return "PROJECT " + id + "\nState: NOT_FOUND_IN_LOCAL_DURABLE_REGISTRY\n" +
                "Aucun changement de projet n'a été effectué.";
    }

    private String job(String code) {
        String c = code == null ? "" : code.trim();
        if (c.isEmpty()) return "Usage: /job <code>";
        return "JOB " + c + "\nState: MISSION_JOURNAL_RESOLVER_NOT_ACTIVE_IN_MVP0\n" +
                "Le code n'est pas interprété comme une preuve d'exécution.";
    }

    private String last() {
        JSONArray events = bcp.recentTelemetry(8);
        if (events.length() == 0) {
            return "LAST OBSERVED\nAucun événement local récent non purgé.";
        }
        StringBuilder s = new StringBuilder("LAST OBSERVED · LOCAL B-EDGE\n");
        for (int i = 0; i < events.length(); i++) {
            JSONObject e = events.optJSONObject(i);
            if (e == null) continue;
            s.append("• ").append(e.optLong("ts", 0L)).append(" ")
                    .append(safeState(e.optString("type", "EVENT"))).append("\n");
        }
        s.append("Détails sensibles omis.");
        return s.toString().trim();
    }

    private String ci() {
        JSONObject bcpCi = PublicGitHubEvidence.snapshot(BCP_REPO);
        JSONObject build = PublicGitHubEvidence.snapshot(BUILDHUB_REPO);
        StringBuilder s = new StringBuilder("CI OBSERVABILITY\n");
        appendRepoCi(s, "BCP", bcpCi);
        appendRepoCi(s, "BuildHub", build);
        return s.toString().trim();
    }

    private String holds() {
        StringBuilder s = new StringBuilder("HOLDS OBSERVED\n");
        int count = 0;
        try {
            JSONObject r = bcp.resume();
            JSONObject head = r.optJSONObject("head");
            JSONObject payload = head == null ? null : head.optJSONObject("payload");
            String state = payload == null ? "" : payload.optString("status", "");
            String upper = state.toUpperCase(Locale.ROOT);
            if (upper.contains("HOLD") || upper.contains("BLOCK")) {
                s.append("• PROJECT: ").append(safeState(state)).append("\n");
                count++;
            }
        } catch (Exception ignored) {}

        JSONObject gh = PublicGitHubEvidence.snapshot(BCP_REPO);
        String conclusion = gh.optString("ci", "");
        if ("FAILURE".equals(conclusion) || "CANCELLED".equals(conclusion) ||
                "TIMED_OUT".equals(conclusion)) {
            s.append("• CI: ").append(conclusion).append("\n");
            count++;
        }
        if (count == 0) {
            s.append("Aucun HOLD durable détecté dans les sources actuellement lisibles.\n");
            s.append("Cela ne prouve pas l'absence d'un état interne ChatGPT non observable.");
        }
        return s.toString().trim();
    }

    private String help() {
        return "COMMANDES READ ONLY\n" +
                "/status — état compact\n" +
                "/project <id> — état durable du projet\n" +
                "/job <code> — résolution quand le Mission Journal sera actif\n" +
                "/last — derniers événements observables\n" +
                "/ci — GitHub CI BCP + BuildHub\n" +
                "/holds — blocages durables observés\n" +
                "/help — cette aide";
    }

    private static void appendRepoCi(StringBuilder s, String label, JSONObject snap) {
        s.append(label).append(": ");
        if (!snap.optBoolean("ok", false)) {
            s.append("UNAVAILABLE\n");
            return;
        }
        s.append(shortSha(snap.optString("sha", "")))
                .append(" · ")
                .append(safeState(snap.optString("ci", "UNKNOWN")))
                .append("\n");
    }

    private static void appendIfPresent(StringBuilder s, String label, String value) {
        if (value != null && !value.trim().isEmpty()) {
            String v = value.trim();
            if (v.length() > 220) v = v.substring(0, 220) + "…";
            s.append(label).append(": ").append(v).append("\n");
        }
    }

    private static String safeState(String value) {
        if (value == null || value.isEmpty()) return "UNKNOWN";
        return value.replaceAll("[^A-Za-z0-9_./:+ -]", "?").trim();
    }

    private static String shortSha(String sha) {
        if (sha == null || sha.isEmpty()) return "UNKNOWN";
        return sha.substring(0, Math.min(8, sha.length()));
    }
}
