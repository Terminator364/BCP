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
        updates = new UpdateManager(this, s -> { if (detail != null) detail.setText(s); });

        ScrollView scroll = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        int pad = dp(20);
        root.setPadding(pad,pad,pad,pad);
        scroll.addView(root);

        TextView title = new TextView(this);
        title.setText("BCP Edge · B-EDGE");
        title.setTextSize(25);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        root.addView(title);

        TextView subtitle = new TextView(this);
        subtitle.setText("Découverte, appairage, télémétrie et reprise automatiques");
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
        autoConnect();
        updates.check();
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
                    detail.setText("PC appairé automatiquement · projet buildhub");
                    String pc = r.optString("pc_name", "BCP PC");
                    String ver = r.optString("version", "");
                    output.setText("État: OK\nPC: " + pc + (ver.isEmpty() ? "" : "\nServeur: " + ver) +
                            "\nProjet: buildhub\nIdentifiants: masqués");
                    setBusy(false);
                });
            } catch (Exception ex) {
                runOnUiThread(() -> {
                    String m = ex.getMessage() == null ? ex.getClass().getSimpleName() : ex.getMessage();
                    status.setText(classify(m));
                    detail.setText("Diagnostic automatique: " + m);
                    output.setText("La télémétrie locale a conservé l'étape d'échec.");
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
                "Vérifier la mise à jour BCP Edge"
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
