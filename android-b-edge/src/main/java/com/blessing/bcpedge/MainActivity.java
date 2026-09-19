package com.blessing.bcpedge;

import android.app.Activity;
import android.app.AlertDialog;
import android.os.Bundle;
import android.graphics.Typeface;
import android.view.View;
import android.widget.*;
import org.json.JSONObject;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

public class MainActivity extends Activity {
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private final ScheduledExecutorService heartbeat = Executors.newSingleThreadScheduledExecutor();
    private BcpClient client;
    private TextView status, detail, output;
    private Button connect, checkpoint, resume, settings;
    private UpdateManager updates;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        client = new BcpClient(this);
        updates = new UpdateManager(this, client, s -> { if (detail != null) detail.setText(s); });

        ScrollView scroll = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        int pad = dp(20);
        root.setPadding(pad,pad,pad,pad);
        scroll.addView(root);

        TextView title = new TextView(this);
        title.setText("BCP Edge Evergreen · B-EDGE");
        title.setTextSize(25);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        root.addView(title);

        TextView subtitle = new TextView(this);
        subtitle.setText("Mémoire durable · orchestration · reprise · télémétrie · mises à jour vérifiées");
        subtitle.setPadding(0,dp(6),0,dp(16));
        root.addView(subtitle);

        status = new TextView(this);
        status.setText("DÉMARRAGE");
        status.setTextSize(22);
        status.setTypeface(Typeface.DEFAULT_BOLD);
        root.addView(status);

        detail = new TextView(this);
        detail.setText("Initialisation...");
        detail.setPadding(0,dp(6),0,dp(18));
        root.addView(detail);

        connect = button(root, "CONNECTER AUTOMATIQUEMENT");
        settings = button(root, "PARAMÈTRES / MISES À JOUR");
        checkpoint = button(root, "ENREGISTRER CHECKPOINT");
        resume = button(root, "REPRENDRE LE PROJET");

        output = new TextView(this);
        output.setTypeface(Typeface.MONOSPACE);
        output.setTextIsSelectable(true);
        output.setPadding(0,dp(18),0,dp(24));
        root.addView(output);

        connect.setOnClickListener(v -> autoConnect());
        settings.setOnClickListener(v -> showSettings());
        checkpoint.setOnClickListener(v -> runAction("CHECKPOINT", () ->
                client.checkpoint("B-EDGE paired and telemetry active",
                        "Restart PC/phone and verify automatic resume")));
        resume.setOnClickListener(v -> runAction("RESUME", () -> client.resume()));

        setContentView(scroll);
        updates.reconcileAfterLaunch();
        autoConnect();
        heartbeat.scheduleAtFixedRate(() -> {
            try { client.heartbeat("FOREGROUND"); } catch (Exception ignored) {}
        }, 60, 60, TimeUnit.SECONDS);
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
                    detail.setText("PC appairé automatiquement · projet " + client.getProject());
                    String pc = r.optString("pc_name", "BCP PC");
                    String ver = r.optString("version", "");
                    output.setText("État: OK\nB-EDGE: " + client.getEdgeVersion() +
                            "\nPC: " + pc + (ver.isEmpty() ? "" : "\nServeur: " + ver) +
                            "\nProjet: " + client.getProject() + "\nIdentifiants: masqués");
                    setBusy(false);
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
                    detail.setText("Diagnostic automatique: " + m);
                    output.setText("La télémétrie locale a conservé l'étape d'échec.");
                    setBusy(false);
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
                    .setMessage(pc + (version.isEmpty() ? "" : " · BCP " + version) +
                            "\nEmpreinte: " + hint +
                            "\n\nCette confirmation n'est demandée qu'au premier appairage.")
                    .setPositiveButton("CONFIRMER", (d, w) -> confirmPendingPairing())
                    .setNegativeButton("ANNULER", null)
                    .show();
        } catch (Exception ex) {
            status.setText("APPAIRAGE ÉCHOUÉ");
            detail.setText("Candidat d'appairage indisponible");
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
                    detail.setText("PC confirmé et appairé · projet buildhub");
                    output.setText("État: OK\nB-EDGE: " + client.getEdgeVersion() +
                            "\nPC: " + r.optString("pc_name", "BCP PC") +
                            "\nServeur: " + r.optString("version", "") +
                            "\nProjet: buildhub\nIdentifiants: masqués");
                    setBusy(false);
                    updates.check();
                });
            } catch (Exception ex) {
                runOnUiThread(() -> {
                    status.setText("APPAIRAGE ÉCHOUÉ");
                    detail.setText("Diagnostic automatique: " +
                            (ex.getMessage() == null ? ex.getClass().getSimpleName() : ex.getMessage()));
                    setBusy(false);
                });
            }
        });
    }

    private void showSettings() {
        final String[] choices = new String[] {
                "État des versions",
                "État ChatGPT-PC",
                "Réparer ChatGPT-PC maintenant",
                "Mettre à jour le serveur PC maintenant",
                "Vérifier / mettre à jour BCP Edge",
                "État orchestrateur / mémoire",
                "Test rapide B-EDGE"
        };
        new AlertDialog.Builder(this)
                .setTitle("Paramètres BCP")
                .setItems(choices, (dialog, which) -> {
                    if (which == 0) {
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
                    } else if (which == 1) {
                        runAction("CHATGPT-PC", () -> client.chatgptPcStatus());
                    } else if (which == 2) {
                        new AlertDialog.Builder(this)
                                .setTitle("Réparer ChatGPT-PC")
                                .setMessage("Lancer le Recovery Plane borné avec la cible déjà vérifiée ?")
                                .setPositiveButton("RÉPARER", (d, w) ->
                                        runAction("RÉCUPÉRATION CHATGPT-PC", () -> client.recoverChatgptPc()))
                                .setNegativeButton("ANNULER", null)
                                .show();
                    } else if (which == 3) {
                        runAction("MISE À JOUR SERVEUR", () -> client.applyServerUpdate());
                    } else if (which == 4) {
                        updates.check(true);
                    } else if (which == 5) {
                        runAction("ORCHESTRATEUR", () -> {
                            JSONObject out = client.orchestratorStatus();
                            JSONObject ctx = client.contextPack();
                            out.put("context_pack_cached", ctx.length() > 0);
                            return out;
                        });
                    } else if (which == 6) {
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
        if (message.contains("PC_NOT_FOUND")) return "PC NON TROUVÉ";
        if (message.contains("NO_LAN_IPV4")) return "RÉSEAU LOCAL ABSENT";
        if (message.contains("PAIRING")) return "APPAIRAGE ÉCHOUÉ";
        if (message.contains("HTTP_401")) return "AUTHENTIFICATION ÉCHOUÉE";
        return "CONNEXION ÉCHOUÉE";
    }

    private void setBusy(boolean busy) {
        connect.setEnabled(!busy);
        settings.setEnabled(!busy);
        checkpoint.setEnabled(!busy);
        resume.setEnabled(!busy);
    }

    private Button button(LinearLayout root, String text) {
        Button b = new Button(this);
        b.setText(text);
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
