package com.blessing.bcpedge;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONObject;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

import androidx.annotation.NonNull;
import androidx.core.content.ContextCompat;

public class MainActivity extends Activity {
    private static final String UI_PREFS = "bcp_edge_ui";
    private static final String ONBOARDING_KEY = "server_onboarding_220_shown";

    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private final ScheduledExecutorService heartbeat = Executors.newSingleThreadScheduledExecutor();
    private BcpClient client;
    private UpdateManager updates;

    private TextView status;
    private TextView detail;
    private TextView nodeInfo;
    private TextView autonomyInfo;
    private TextView permissionsInfo;
    private TextView output;
    private Button connect;
    private Button checkpoint;
    private Button resume;
    private Button settings;
    private Button serverMode;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        client = new BcpClient(this);
        updates = new UpdateManager(this, client, s ->
                runOnUiThread(() -> { if (detail != null) detail.setText(s); }));

        EdgePermissionManager.setServerModeEnabled(this, true);
        setContentView(buildUi());

        updates.reconcileAfterLaunch();
        startEdgeServer();
        autoConnect();
        refreshLocalPanels();

        heartbeat.scheduleAtFixedRate(() -> {
            try { client.heartbeat("FOREGROUND"); } catch (Exception ignored) {}
            runOnUiThread(this::refreshLocalPanels);
        }, 60, 60, TimeUnit.SECONDS);

        getWindow().getDecorView().postDelayed(this::maybeOfferDedicatedServerSetup, 900);
    }

    private View buildUi() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        int pad = dp(16);
        root.setPadding(pad, pad, pad, dp(28));
        root.setBackgroundColor(Color.rgb(246, 247, 249));
        scroll.addView(root);

        TextView title = text("BCP Edge Server", 22, true);
        root.addView(title);

        TextView subtitle = text(
                "Ancien téléphone dédié · serveur local · mémoire durable · relais · reprise autonome",
                13, false);
        subtitle.setTextColor(Color.rgb(80, 86, 94));
        subtitle.setPadding(0, dp(4), 0, dp(12));
        root.addView(subtitle);

        LinearLayout stateCard = card(root);
        status = text("DÉMARRAGE", 20, true);
        stateCard.addView(status);
        detail = text("Initialisation du nœud Edge…", 13, false);
        detail.setPadding(0, dp(4), 0, 0);
        stateCard.addView(detail);

        LinearLayout nodeCard = card(root);
        nodeCard.addView(label("NŒUD SERVEUR"));
        nodeInfo = text("Lecture de l’état local…", 14, false);
        nodeInfo.setPadding(0, dp(5), 0, 0);
        nodeCard.addView(nodeInfo);

        LinearLayout autonomyCard = card(root);
        autonomyCard.addView(label("AUTONOMIE / TRANSPORTS"));
        autonomyInfo = text("File durable · LAN/API · découverte locale", 14, false);
        autonomyInfo.setPadding(0, dp(5), 0, 0);
        autonomyCard.addView(autonomyInfo);

        LinearLayout permissionCard = card(root);
        permissionCard.addView(label("AUTORISATIONS SERVEUR"));
        permissionsInfo = text("Vérification…", 14, false);
        permissionsInfo.setPadding(0, dp(5), 0, dp(8));
        permissionCard.addView(permissionsInfo);
        serverMode = button(permissionCard, "ACTIVER / RENFORCER LE MODE SERVEUR 24/7");
        serverMode.setOnClickListener(v -> beginDedicatedServerSetup());

        LinearLayout actions = card(root);
        actions.addView(label("ACTIONS"));
        connect = button(actions, "RECONNECTER AU PC");
        checkpoint = button(actions, "ENREGISTRER CHECKPOINT");
        resume = button(actions, "REPRENDRE LE PROJET");
        settings = button(actions, "PARAMÈTRES / DIAGNOSTIC");

        output = text("", 12, false);
        output.setTypeface(Typeface.MONOSPACE);
        output.setTextIsSelectable(true);
        output.setPadding(dp(2), dp(10), dp(2), dp(8));
        actions.addView(output);

        connect.setOnClickListener(v -> autoConnect());
        checkpoint.setOnClickListener(v -> runAction("CHECKPOINT", () ->
                client.checkpoint("B-EDGE server node active",
                        "Verify durable phone-first communication and resume")));
        resume.setOnClickListener(v -> runAction("RESUME", () -> client.resume()));
        settings.setOnClickListener(v -> showSettings());

        TextView footer = text(
                "Les identifiants restent masqués. Les fonctions sensibles exigent l’appairage BCP.",
                11, false);
        footer.setTextColor(Color.rgb(90, 96, 104));
        footer.setPadding(dp(3), dp(6), dp(3), 0);
        root.addView(footer);

        return scroll;
    }

    private void startEdgeServer() {
        try {
            Intent relay = new Intent(this, EdgeRelayService.class);
            ContextCompat.startForegroundService(this, relay);
            client.recordEvent("EDGE_SERVER_START_REQUESTED", "foreground_activity");
        } catch (Exception ex) {
            client.recordEvent("EDGE_SERVER_START_DEFERRED",
                    ex.getMessage() == null ? ex.getClass().getSimpleName() : ex.getMessage());
        }
    }

    private void refreshLocalPanels() {
        try {
            SharedPreferences relay = getSharedPreferences("bcp_edge_relay_state", MODE_PRIVATE);
            String listener = relay.getString("state", "STARTING");
            int port = relay.getInt("port", EdgeRelayPolicy.RELAY_PORT);
            String mode = EdgePermissionManager.isServerModeEnabled(this) ? "ACTIF" : "PAUSE";
            nodeInfo.setText(
                    "Mode serveur: " + mode
                            + "\nAPI locale: port " + port
                            + "\nÉcoute: " + listener
                            + "\nVersion: " + client.getEdgeVersion());

            JSONObject ps = EdgePermissionManager.status(this);
            boolean runtime = ps.optBoolean("runtime_permissions_ready", false);
            boolean battery = ps.optBoolean("battery_unrestricted", false);
            permissionsInfo.setText(
                    "Appareils à proximité: " + (runtime ? "PRÊT" : "À AUTORISER")
                            + "\nBatterie 24/7: " + (battery ? "SANS RESTRICTION" : "À RENFORCER")
                            + "\nDémarrage après reboot: ACTIVÉ");

            JSONObject storage = client.contentStoreStatus();
            JSONObject net = EdgeNetworkState.snapshot(this);
            JSONObject route = client.routeStatus();
            JSONObject comms = client.communicationStatus();
            JSONObject resources = EdgeResourceGovernor.snapshot(this);
            double quotaGiB = storage.optDouble("quota_gib", 0d);
            long usedMiB = storage.optLong("used_bytes", 0L) / (1024L * 1024L);
            autonomyInfo.setText(
                    "File durable Room: active"
                            + "\nCache privé téléphone: " + usedMiB + " MiB / " + quotaGiB + " GiB"
                            + "\nRéseau: " + net.optString("transport", "AUCUN")
                            + " · " + net.optString("routing_hint", "STORE_AND_FORWARD")
                            + "\nRoute BCP: " + route.optString("preferred_route", "STORE_AND_FORWARD")
                            + "\nJournal communication: " + comms.optInt("entries_current_segment", 0) + " événements"
                            + "\nLAN/API + NSD: actif"
                            + "\nWi‑Fi Direct / BLE découverte: " + (runtime ? "prêt" : "autorisation requise")
                            + "\nStore-and-forward: actif"
                            + "\nCahier produit: A+B+C");
        } catch (Exception ignored) {}
    }

    private void maybeOfferDedicatedServerSetup() {
        SharedPreferences p = getSharedPreferences(UI_PREFS, MODE_PRIVATE);
        if (p.getBoolean(ONBOARDING_KEY, false)) return;
        p.edit().putBoolean(ONBOARDING_KEY, true).apply();
        if (EdgePermissionManager.hasCoreRuntimePermissions(this)) return;

        new AlertDialog.Builder(this)
                .setTitle("Activer le vrai mode serveur")
                .setMessage(
                        "Ce téléphone est dédié à BCP. Pour qu’il reste un nœud Edge fiable, "
                                + "Android doit autoriser les notifications du service, la découverte "
                                + "des appareils à proximité (Wi‑Fi/Bluetooth) et, idéalement, "
                                + "l’exécution sans restriction de batterie.\n\n"
                                + "Ces autorisations servent uniquement au serveur local, à la découverte "
                                + "et à la continuité BCP.")
                .setPositiveButton("ACTIVER", (d, w) -> beginDedicatedServerSetup())
                .setNegativeButton("PLUS TARD", null)
                .show();
    }

    private void beginDedicatedServerSetup() {
        EdgePermissionManager.setServerModeEnabled(this, true);
        if (!EdgePermissionManager.hasCoreRuntimePermissions(this)) {
            EdgePermissionManager.requestCoreRuntimePermissions(this);
            return;
        }
        requestBatteryStep();
    }

    private void requestBatteryStep() {
        refreshLocalPanels();
        if (EdgePermissionManager.batteryUnrestricted(this)) {
            status.setText("SERVEUR DÉDIÉ ACTIF");
            detail.setText("Autorisations principales et continuité 24/7 prêtes.");
            startEdgeServer();
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("Autonomie 24/7")
                .setMessage(
                        "Autoriser BCP Edge à fonctionner sans optimisation batterie réduit le risque "
                                + "qu’Android coupe le serveur lorsque l’écran est éteint.")
                .setPositiveButton("OUVRIR LE RÉGLAGE", (d, w) -> {
                    EdgePermissionManager.requestBatteryUnrestricted(this);
                })
                .setNegativeButton("GARDER LE MODE STANDARD", null)
                .show();
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions,
                                           @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == EdgePermissionManager.REQUEST_CORE_SERVER_PERMISSIONS) {
            refreshLocalPanels();
            requestBatteryStep();
        }
    }

    @Override protected void onResume() {
        super.onResume();
        if (client != null) refreshLocalPanels();
    }

    private void autoConnect() {
        setBusy(true);
        output.setText("");
        io.submit(() -> {
            try {
                JSONObject r = client.connectAutomatically((stage, d) ->
                        runOnUiThread(() -> {
                            status.setText(stage);
                            detail.setText(d);
                        }));
                runOnUiThread(() -> {
                    status.setText("CONNECTÉ");
                    detail.setText("Téléphone serveur appairé · projet " + client.getProject());
                    String pc = r.optString("pc_name", "BCP PC");
                    String ver = r.optString("version", "");
                    output.setText(
                            "État: OK"
                                    + "\nB-EDGE: " + client.getEdgeVersion()
                                    + "\nPC: " + pc
                                    + (ver.isEmpty() ? "" : "\nServeur PC: " + ver)
                                    + "\nProjet: " + client.getProject()
                                    + "\nIdentifiants: masqués");
                    setBusy(false);
                    refreshLocalPanels();
                    updates.check();
                });
            } catch (Exception ex) {
                String m = ex.getMessage() == null ? ex.getClass().getSimpleName() : ex.getMessage();
                if ("PAIR_CONFIRM_REQUIRED".equals(m)) {
                    runOnUiThread(() -> {
                        setBusy(false);
                        showPairingConfirmation();
                    });
                    return;
                }
                runOnUiThread(() -> {
                    status.setText(classify(m));
                    detail.setText("Le nœud local reste actif. Diagnostic PC: " + m);
                    output.setText("Le téléphone conserve la file, la mémoire et la télémétrie locales.");
                    setBusy(false);
                    refreshLocalPanels();
                });
            }
        });
    }

    private void showPairingConfirmation() {
        try {
            JSONObject p = client.pendingPairingInfo();
            String pc = p.optString("pc_name", "BCP PC");
            String version = p.optString("version", "");
            String fp = p.optString("identity_fingerprint", "");
            String hint = fp.isEmpty() ? "empreinte disponible après mise à niveau"
                    : fp.substring(0, Math.min(12, fp.length()));
            new AlertDialog.Builder(this)
                    .setTitle("Confirmer ce PC")
                    .setMessage(pc + (version.isEmpty() ? "" : " · BCP " + version)
                            + "\nEmpreinte: " + hint
                            + "\n\nCette confirmation n’est demandée qu’au premier appairage.")
                    .setPositiveButton("CONFIRMER", (d, w) -> confirmPendingPairing())
                    .setNegativeButton("ANNULER", null)
                    .show();
        } catch (Exception ex) {
            status.setText("APPAIRAGE ÉCHOUÉ");
            detail.setText("Candidat d’appairage indisponible");
        }
    }

    private void confirmPendingPairing() {
        setBusy(true);
        io.submit(() -> {
            try {
                JSONObject r = client.confirmPendingPairing((stage, d) ->
                        runOnUiThread(() -> {
                            status.setText(stage);
                            detail.setText(d);
                        }));
                runOnUiThread(() -> {
                    status.setText("CONNECTÉ");
                    detail.setText("PC confirmé · téléphone serveur prêt");
                    output.setText(
                            "État: OK"
                                    + "\nB-EDGE: " + client.getEdgeVersion()
                                    + "\nPC: " + r.optString("pc_name", "BCP PC")
                                    + "\nServeur PC: " + r.optString("version", "")
                                    + "\nProjet: " + client.getProject()
                                    + "\nIdentifiants: masqués");
                    setBusy(false);
                    refreshLocalPanels();
                    updates.check();
                });
            } catch (Exception ex) {
                runOnUiThread(() -> {
                    status.setText("APPAIRAGE ÉCHOUÉ");
                    detail.setText("Diagnostic automatique: "
                            + (ex.getMessage() == null ? ex.getClass().getSimpleName() : ex.getMessage()));
                    setBusy(false);
                });
            }
        });
    }

    private void showSettings() {
        final String[] choices = new String[] {
                "État du nœud serveur",
                "Autorisations / autonomie 24/7",
                "État des versions",
                "État ChatGPT-PC",
                "Réparer ChatGPT-PC maintenant",
                "Mettre à jour le serveur PC maintenant",
                "Vérifier / mettre à jour BCP Edge",
                "État orchestrateur / mémoire",
                "TEST RAPIDE B-EDGE"
        };
        new AlertDialog.Builder(this)
                .setTitle("BCP Edge · diagnostic")
                .setItems(choices, (dialog, which) -> {
                    if (which == 0) {
                        runAction("NŒUD SERVEUR", () -> {
                            JSONObject out = EdgePermissionManager.status(this);
                            out.put("edge_version", client.getEdgeVersion());
                            out.put("project", client.getProject());
                            out.put("sentinel", client.sentinelStatus());
                            return out;
                        });
                    } else if (which == 1) {
                        beginDedicatedServerSetup();
                    } else if (which == 2) {
                        runAction("VERSIONS", () -> {
                            JSONObject s = client.serverUpdateStatus();
                            JSONObject out = new JSONObject();
                            out.put("edge_version", client.getEdgeVersion());
                            out.put("server_current", s.optString("current_version", ""));
                            out.put("server_target", s.optString("target_version", ""));
                            out.put("server_update_available", s.optBoolean("available", false));
                            out.put("server_auto_update", s.optBoolean("auto_update", true));
                            return out;
                        });
                    } else if (which == 3) {
                        runAction("CHATGPT-PC", () -> client.chatgptPcStatus());
                    } else if (which == 4) {
                        new AlertDialog.Builder(this)
                                .setTitle("Réparer ChatGPT-PC")
                                .setMessage("Lancer le Recovery Plane borné avec la cible déjà vérifiée ?")
                                .setPositiveButton("RÉPARER", (d, w) ->
                                        runAction("RÉCUPÉRATION CHATGPT-PC", () -> client.recoverChatgptPc()))
                                .setNegativeButton("ANNULER", null)
                                .show();
                    } else if (which == 5) {
                        runAction("MISE À JOUR SERVEUR", () -> client.applyServerUpdate());
                    } else if (which == 6) {
                        updates.check(true);
                    } else if (which == 7) {
                        runAction("ORCHESTRATEUR", () -> {
                            JSONObject out = client.orchestratorStatus();
                            JSONObject ctx = client.contextPack();
                            out.put("context_pack_cached", ctx.length() > 0);
                            return out;
                        });
                    } else if (which == 8) {
                        runAction("TEST RAPIDE B-EDGE", () -> client.runQuickAcceptance());
                    }
                })
                .setNegativeButton("FERMER", null)
                .show();
    }

    private interface Action { JSONObject run() throws Exception; }

    private void runAction(String name, Action action) {
        setBusy(true);
        io.submit(() -> {
            try {
                JSONObject r = action.run();
                runOnUiThread(() -> {
                    status.setText(name + " OK");
                    output.setText(r.toString());
                    setBusy(false);
                    refreshLocalPanels();
                });
            } catch (Exception ex) {
                runOnUiThread(() -> {
                    status.setText(name + " ÉCHEC");
                    output.setText(ex.getMessage());
                    setBusy(false);
                });
            }
        });
    }

    private String classify(String message) {
        if (message.contains("PC_NOT_FOUND")) return "PC NON TROUVÉ · EDGE ACTIF";
        if (message.contains("NO_LAN_IPV4")) return "LAN ABSENT · EDGE LOCAL";
        if (message.contains("PAIRING")) return "APPAIRAGE ÉCHOUÉ";
        if (message.contains("HTTP_401")) return "AUTHENTIFICATION ÉCHOUÉE";
        return "PC INDISPONIBLE · EDGE ACTIF";
    }

    private void setBusy(boolean busy) {
        connect.setEnabled(!busy);
        settings.setEnabled(!busy);
        checkpoint.setEnabled(!busy);
        resume.setEnabled(!busy);
        serverMode.setEnabled(!busy);
    }

    private LinearLayout card(LinearLayout root) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(14), dp(12), dp(14), dp(12));

        GradientDrawable bg = new GradientDrawable();
        bg.setColor(Color.WHITE);
        bg.setCornerRadius(dp(14));
        bg.setStroke(dp(1), Color.rgb(224, 227, 232));
        card.setBackground(bg);

        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, 0, 0, dp(10));
        root.addView(card, lp);
        return card;
    }

    private TextView label(String value) {
        TextView v = text(value, 12, true);
        v.setTextColor(Color.rgb(67, 74, 84));
        return v;
    }

    private TextView text(String value, int sp, boolean bold) {
        TextView v = new TextView(this);
        v.setText(value);
        v.setTextSize(sp);
        v.setTextColor(Color.rgb(24, 28, 33));
        if (bold) v.setTypeface(Typeface.DEFAULT_BOLD);
        return v;
    }

    private Button button(LinearLayout root, String text) {
        Button b = new Button(this);
        b.setText(text);
        b.setAllCaps(false);
        root.addView(b, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT));
        return b;
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    @Override protected void onDestroy() {
        super.onDestroy();
        io.shutdownNow();
        heartbeat.shutdownNow();
        updates.close();
    }
}
