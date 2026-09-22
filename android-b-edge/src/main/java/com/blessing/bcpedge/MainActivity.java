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
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import com.blessing.bcpedge.storage.EdgeDatabase;

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
    private TextView capabilityInfo;
    private TextView permissionsInfo;
    private TextView output;
    private Button connect;
    private Button checkpoint;
    private Button resume;
    private Button settings;
    private Button serverMode;
    private FrameLayout screenHost;
    private View homeScreen;
    private View activityScreen;
    private View devicesScreen;
    private View systemScreen;
    private TextView homeSummary;
    private TextView homeAction;
    private TextView homeRecent;
    private TextView activitySummary;
    private TextView activityList;
    private TextView activityEvents;
    private TextView devicesSummary;
    private TextView devicesTrust;
    private TextView repairsInfo;
    private Button homeActionButton;
    private Button navHome;
    private Button navActivity;
    private Button navDevices;
    private Button navSystem;
    private Button technicalToggle;
    private String currentScreen = "HOME";
    private boolean busy = false;
    private int lastPendingJobs = 0;
    private int lastMissionCount = 0;
    private int lastEventCount = 0;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        client = new BcpClient(this);
        updates = new UpdateManager(this, client, s ->
                runOnUiThread(() -> { if (detail != null) detail.setText(s); }));

        EdgePermissionManager.setServerModeEnabled(this, true);
        setContentView(buildUi());

        updates.reconcileAfterLaunch();
        startEdgeServer();
        io.submit(() -> {
            try { client.refreshUiGovernanceCache(); } catch (Exception ignored) {}
            runOnUiThread(() -> {
                refreshLocalPanels();
                refreshHumanData();
            });
        });
        autoConnect();
        refreshLocalPanels();
        refreshHumanData();

        heartbeat.scheduleAtFixedRate(() -> {
            try {
                client.heartbeat("FOREGROUND");
                client.refreshUiGovernanceCache();
            } catch (Exception ignored) {}
            runOnUiThread(() -> {
                refreshLocalPanels();
                refreshHumanData();
            });
        }, 60, 60, TimeUnit.SECONDS);

        getWindow().getDecorView().postDelayed(this::maybeOfferDedicatedServerSetup, 900);
    }

    private View buildUi() {
        LinearLayout shell = new LinearLayout(this);
        shell.setOrientation(LinearLayout.VERTICAL);
        shell.setBackgroundColor(Color.rgb(246, 247, 249));

        screenHost = new FrameLayout(this);
        LinearLayout.LayoutParams hostLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f);
        shell.addView(screenHost, hostLp);

        homeScreen = buildHomeScreen();
        activityScreen = buildActivityScreen();
        devicesScreen = buildDevicesScreen();
        systemScreen = buildSystemScreen();

        LinearLayout nav = new LinearLayout(this);
        nav.setOrientation(LinearLayout.HORIZONTAL);
        nav.setPadding(dp(4), dp(4), dp(4), dp(4));
        nav.setBackgroundColor(Color.WHITE);
        navHome = navButton(nav, "Accueil", "HOME");
        navActivity = navButton(nav, "Activité", "ACTIVITY");
        navDevices = navButton(nav, "Appareils", "DEVICES");
        navSystem = navButton(nav, "Système", "SYSTEM");
        shell.addView(nav, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT));

        showScreen("HOME");
        return shell;
    }

    private View buildHomeScreen() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout root = screenBody(scroll, "BCP Edge Server",
                "Votre nœud BCP · état utile, actions seulement si nécessaires");

        LinearLayout stateCard = card(root);
        status = text("DÉMARRAGE", 22, true);
        stateCard.addView(status);
        detail = text("Initialisation du nœud Edge…", 13, false);
        detail.setPadding(0, dp(5), 0, 0);
        stateCard.addView(detail);

        LinearLayout summary = card(root);
        summary.addView(label("EN UN COUP D’ŒIL"));
        homeSummary = text("Lecture du téléphone, du PC et de la file…", 14, false);
        homeSummary.setPadding(0, dp(5), 0, 0);
        summary.addView(homeSummary);

        LinearLayout action = card(root);
        action.addView(label("ACTION REQUISE"));
        homeAction = text("Vérification…", 14, false);
        homeAction.setPadding(0, dp(5), 0, dp(6));
        action.addView(homeAction);
        homeActionButton = button(action, "RÉSOUDRE");

        LinearLayout recent = card(root);
        recent.addView(label("RÉCEMMENT"));
        homeRecent = text("Aucun événement récent chargé.", 13, false);
        homeRecent.setPadding(0, dp(5), 0, 0);
        recent.addView(homeRecent);

        TextView footer = text(
                "BCP continue localement si le PC ou Internet disparaît. Les identifiants restent masqués.",
                11, false);
        footer.setTextColor(Color.rgb(90, 96, 104));
        footer.setPadding(dp(3), dp(4), dp(3), dp(8));
        root.addView(footer);
        return scroll;
    }

    private View buildActivityScreen() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout root = screenBody(scroll, "Activité",
                "Missions, traitements, reprises et preuves durables");

        LinearLayout summary = card(root);
        summary.addView(label("ÉTAT DES MISSIONS"));
        activitySummary = text("Chargement…", 14, false);
        activitySummary.setPadding(0, dp(5), 0, 0);
        summary.addView(activitySummary);

        LinearLayout missions = card(root);
        missions.addView(label("MISSIONS RÉCENTES"));
        activityList = text("Aucune mission chargée.", 13, false);
        activityList.setPadding(0, dp(5), 0, 0);
        missions.addView(activityList);

        LinearLayout events = card(root);
        events.addView(label("CHRONICLE"));
        activityEvents = text("Aucun événement récent.", 13, false);
        activityEvents.setPadding(0, dp(5), 0, 0);
        events.addView(activityEvents);

        LinearLayout actions = card(root);
        actions.addView(label("REPRISE"));
        checkpoint = button(actions, "ENREGISTRER UN CHECKPOINT");
        resume = button(actions, "REPRENDRE LA MISSION");
        Button refresh = button(actions, "ACTUALISER L’ACTIVITÉ");
        checkpoint.setOnClickListener(v -> runAction("CHECKPOINT", () ->
                client.checkpoint("B-EDGE user checkpoint",
                        "Resume from durable phone state")));
        resume.setOnClickListener(v -> runAction("REPRISE", () -> client.resume()));
        refresh.setOnClickListener(v -> refreshHumanData());
        return scroll;
    }

    private View buildDevicesScreen() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout root = screenBody(scroll, "Appareils",
                "Découverte, confiance et connexion sans saisir d’adresse ni de token");

        LinearLayout devices = card(root);
        devices.addView(label("APPAREILS CONNUS"));
        devicesSummary = text("Lecture des appareils…", 14, false);
        devicesSummary.setPadding(0, dp(5), 0, 0);
        devices.addView(devicesSummary);

        LinearLayout trust = card(root);
        trust.addView(label("CONFIANCE & TRANSPORT"));
        devicesTrust = text("Vérification de la liaison sécurisée…", 13, false);
        devicesTrust.setPadding(0, dp(5), 0, 0);
        trust.addView(devicesTrust);

        LinearLayout actions = card(root);
        actions.addView(label("CONNEXION"));
        connect = button(actions, "RECHERCHER / RECONNECTER LE PC");
        Button trustDetail = button(actions, "DÉTAILS DE CONFIANCE");
        connect.setOnClickListener(v -> autoConnect());
        trustDetail.setOnClickListener(v -> showTrustDetails());
        return scroll;
    }

    private View buildSystemScreen() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout root = screenBody(scroll, "Système",
                "Santé, réparations, autonomie et diagnostics avancés");

        LinearLayout repairs = card(root);
        repairs.addView(label("REPAIRS"));
        repairsInfo = text("Analyse de santé…", 14, false);
        repairsInfo.setPadding(0, dp(5), 0, 0);
        repairs.addView(repairsInfo);

        LinearLayout permissionCard = card(root);
        permissionCard.addView(label("AUTORISATIONS & 24/7"));
        permissionsInfo = text("Vérification…", 14, false);
        permissionsInfo.setPadding(0, dp(5), 0, dp(8));
        permissionCard.addView(permissionsInfo);
        serverMode = button(permissionCard, "RENFORCER LE MODE SERVEUR 24/7");
        serverMode.setOnClickListener(v -> beginDedicatedServerSetup());

        LinearLayout nodeCard = card(root);
        nodeCard.addView(label("NŒUD SERVEUR"));
        nodeInfo = text("Lecture de l’état local…", 13, false);
        nodeInfo.setPadding(0, dp(5), 0, 0);
        nodeCard.addView(nodeInfo);

        LinearLayout autonomyCard = card(root);
        autonomyCard.addView(label("STOCKAGE, FILE & RÉSEAU"));
        autonomyInfo = text("Lecture…", 13, false);
        autonomyInfo.setPadding(0, dp(5), 0, 0);
        autonomyCard.addView(autonomyInfo);

        LinearLayout capabilityCard = card(root);
        capabilityCard.addView(label("CAPACITÉS"));
        capabilityInfo = text("Initialisation…", 13, false);
        capabilityInfo.setPadding(0, dp(5), 0, 0);
        capabilityCard.addView(capabilityInfo);

        LinearLayout advanced = card(root);
        advanced.addView(label("MISES À JOUR & DIAGNOSTIC"));
        Button edgeUpdate = button(advanced, "VÉRIFIER LA MISE À JOUR BCP EDGE");
        settings = button(advanced, "OUTILS AVANCÉS");
        technicalToggle = button(advanced, "AFFICHER LE DERNIER DÉTAIL TECHNIQUE");
        output = text("", 11, false);
        output.setTypeface(Typeface.MONOSPACE);
        output.setTextIsSelectable(true);
        output.setPadding(dp(2), dp(8), dp(2), dp(4));
        output.setVisibility(View.GONE);
        advanced.addView(output);
        edgeUpdate.setOnClickListener(v -> updates.check(true));
        settings.setOnClickListener(v -> showSettings());
        technicalToggle.setOnClickListener(v -> {
            boolean show = output.getVisibility() != View.VISIBLE;
            output.setVisibility(show ? View.VISIBLE : View.GONE);
            technicalToggle.setText(show
                    ? "MASQUER LE DÉTAIL TECHNIQUE"
                    : "AFFICHER LE DERNIER DÉTAIL TECHNIQUE");
        });
        return scroll;
    }

    private LinearLayout screenBody(ScrollView scroll, String titleValue, String subtitleValue) {
        scroll.setFillViewport(true);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        int pad = dp(14);
        root.setPadding(pad, pad, pad, dp(18));
        root.setBackgroundColor(Color.rgb(246, 247, 249));
        scroll.addView(root);

        TextView title = text(titleValue, 22, true);
        root.addView(title);
        TextView subtitle = text(subtitleValue, 12, false);
        subtitle.setTextColor(Color.rgb(80, 86, 94));
        subtitle.setPadding(0, dp(3), 0, dp(10));
        root.addView(subtitle);
        return root;
    }

    private Button navButton(LinearLayout root, String title, String screen) {
        Button b = new Button(this);
        b.setText(title);
        b.setAllCaps(false);
        b.setTextSize(10);
        b.setMinHeight(dp(48));
        b.setPadding(dp(2), 0, dp(2), 0);
        b.setOnClickListener(v -> showScreen(screen));
        root.addView(b, new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        return b;
    }

    private void showScreen(String screen) {
        currentScreen = screen;
        View target = "ACTIVITY".equals(screen) ? activityScreen
                : "DEVICES".equals(screen) ? devicesScreen
                : "SYSTEM".equals(screen) ? systemScreen : homeScreen;
        screenHost.removeAllViews();
        screenHost.addView(target, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT));
        styleNav(navHome, "HOME".equals(screen));
        styleNav(navActivity, "ACTIVITY".equals(screen));
        styleNav(navDevices, "DEVICES".equals(screen));
        styleNav(navSystem, "SYSTEM".equals(screen));
        if ("ACTIVITY".equals(screen) || "HOME".equals(screen)) refreshHumanData();
        refreshLocalPanels();
    }

    private void styleNav(Button button, boolean selected) {
        if (button == null) return;
        button.setTypeface(selected ? Typeface.DEFAULT_BOLD : Typeface.DEFAULT);
        button.setTextColor(selected ? Color.rgb(20, 73, 140) : Color.rgb(66, 72, 80));
        button.setAlpha(selected ? 1f : 0.72f);
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
            boolean serverEnabled = EdgePermissionManager.isServerModeEnabled(this);
            String mode = serverEnabled ? "ACTIF" : "PAUSE";
            JSONObject ps = EdgePermissionManager.status(this);
            boolean runtime = ps.optBoolean("runtime_permissions_ready", false);
            boolean battery = ps.optBoolean("battery_unrestricted", false);
            JSONObject storage = client.contentStoreStatus();
            JSONObject net = EdgeNetworkState.snapshot(this);
            JSONObject resources = EdgeResourceGovernor.snapshot(this);
            JSONObject capabilities = client.cachedCapabilities();
            JSONObject claims = client.cachedMemoryClaims();
            JSONObject sentinel = client.sentinelStatus();

            boolean paired = !client.getToken().isEmpty();
            boolean tlsPinned = client.getServer().startsWith("https://")
                    && client.getPcTlsCertSha256().matches("[0-9a-f]{64}");
            String transport = net.optString("transport", "AUCUN");
            boolean networkAvailable = !"AUCUN".equalsIgnoreCase(transport)
                    && !"NONE".equalsIgnoreCase(transport)
                    && !transport.isEmpty();
            int failures = sentinel.optInt("consecutive_failures", 0);

            nodeInfo.setText(
                    "Mode serveur: " + mode
                            + "\nAPI sécurisée: " + EdgeRelayPolicy.API_TLS_PORT
                            + " · relais Telegram: " + EdgeRelayPolicy.RELAY_PORT
                            + "\nService: " + listener
                            + "\nVersion: " + client.getEdgeVersion());

            permissionsInfo.setText(
                    "Appareils à proximité: " + (runtime ? "PRÊT" : "À AUTORISER")
                            + "\nBatterie 24/7: " + (battery ? "SANS RESTRICTION" : "À RENFORCER")
                            + "\nDémarrage après reboot: ACTIVÉ");

            double quotaGiB = storage.optDouble("quota_gib", 0d);
            long usedMiB = storage.optLong("used_bytes", 0L) / (1024L * 1024L);
            autonomyInfo.setText(
                    "État durable: PRÊT"
                            + "\nFile & reprise: ACTIVES"
                            + "\nMémoire admise: " + claims.optInt("count", 0) + " éléments"
                            + "\nStockage privé: " + usedMiB + " MiB / " + quotaGiB + " GiB"
                            + "\nRéseau: " + transport
                            + " · " + net.optString("routing_hint", "STORE_AND_FORWARD")
                            + "\nStore-and-forward: ACTIF");

            JSONArray capRows = capabilities.optJSONArray("capabilities");
            int capCount = capRows == null ? 0 : capRows.length();
            int ready = 0, degraded = 0, permission = 0;
            StringBuilder keyStates = new StringBuilder();
            if (capRows != null) {
                for (int i = 0; i < capRows.length(); i++) {
                    JSONObject row = capRows.optJSONObject(i);
                    if (row == null) continue;
                    String capState = row.optString("state", "UNKNOWN");
                    if ("READY".equals(capState) || "AVAILABLE".equals(capState)
                            || "TLS_PINNED".equals(capState)) ready++;
                    else if ("DEGRADED".equals(capState) || "UNAVAILABLE".equals(capState)
                            || "POC_CLEAR_HTTP".equals(capState) || "PENDING".equals(capState)) degraded++;
                    else if ("PERMISSION_REQUIRED".equals(capState) || "WAITING_AUTH".equals(capState)) permission++;
                    if (i < 6) {
                        if (keyStates.length() > 0) keyStates.append("\n");
                        keyStates.append("• ")
                                .append(humanize(row.optString("capability_id",
                                        row.optString("kind", "capacité"))))
                                .append(": ").append(humanState(capState));
                    }
                }
            }
            capabilityInfo.setText(
                    "Disponibles: " + ready + " / " + capCount
                            + "\nÀ surveiller: " + degraded
                            + " · Autorisation: " + permission
                            + (keyStates.length() == 0 ? "" : "\n" + keyStates));

            devicesSummary.setText(
                    "Ce téléphone · B-EDGE " + client.getEdgeVersion() + "\n"
                            + (serverEnabled ? "Serveur local actif" : "Serveur en pause")
                            + "\n\nPC BCP · " + (paired ? "APPAIRÉ" : "NON APPAIRÉ")
                            + "\nDécouverte: automatique sur le réseau local");

            devicesTrust.setText(
                    "PC: " + (paired ? "confiance enregistrée" : "à confirmer lors du premier appairage")
                            + "\nCanal téléphone ↔ PC: "
                            + (tlsPinned ? "TLS PINNÉ" : paired ? "SÉCURISATION EN ATTENTE" : "NON ÉTABLI")
                            + "\nIdentifiants: masqués"
                            + "\nRelais: direct d’abord, fallback contrôlé si nécessaire");

            StringBuilder repairs = new StringBuilder();
            if (!runtime) repairs.append("• Autoriser la découverte des appareils.\n");
            if (!battery) repairs.append("• Renforcer l’autonomie 24/7.\n");
            if (!paired) repairs.append("• Appairer le PC BCP.\n");
            if (paired && !tlsPinned) repairs.append("• Finaliser la liaison TLS pinnée.\n");
            if (failures > 0) repairs.append("• Vérifier la reconnexion PC (")
                    .append(failures).append(" échecs consécutifs).\n");
            if (repairs.length() == 0) repairs.append("Aucune réparation requise.");
            repairsInfo.setText(repairs.toString().trim());

            homeSummary.setText(
                    "Téléphone Edge: " + (serverEnabled ? "PRÊT" : "EN PAUSE")
                            + "\nPC: " + (paired ? (tlsPinned ? "APPAIRÉ · SÉCURISÉ" : "APPAIRÉ") : "À CONNECTER")
                            + "\nRéseau: " + (networkAvailable ? transport : "HORS-LIGNE · MODE LOCAL")
                            + "\nEn attente: " + lastPendingJobs + " tâche(s)");

            configurePrimaryAction(runtime, battery, paired, tlsPinned, networkAvailable, failures);

            if (!busy) {
                if (!runtime) {
                    status.setText("ACTION REQUISE");
                    detail.setText("Autorisez la découverte locale pour que BCP trouve les appareils.");
                } else if (!paired) {
                    status.setText("PRÊT LOCALEMENT");
                    detail.setText("Le téléphone fonctionne déjà. Le PC peut être découvert et appairé automatiquement.");
                } else if (!networkAvailable) {
                    status.setText("HORS-LIGNE · CONTINUE");
                    detail.setText("Le réseau est absent. La file et la mémoire restent sur ce téléphone.");
                } else if (failures > 0) {
                    status.setText("DÉGRADÉ · REPRISE AUTO");
                    detail.setText("Le PC est temporairement indisponible; BCP conserve l’état et retente proprement.");
                } else {
                    status.setText("PRÊT");
                    detail.setText("Téléphone Edge actif · PC sécurisé · reprise durable disponible.");
                }
            }

            if (resources.optBoolean("low_memory", false)) {
                repairsInfo.append("\n• Pression mémoire détectée : les tâches lourdes doivent attendre.");
            }
        } catch (Exception ignored) {}
    }

    private void configurePrimaryAction(boolean runtime, boolean battery, boolean paired,
                                        boolean tlsPinned, boolean networkAvailable, int failures) {
        if (!runtime) {
            homeAction.setText("BCP a besoin de l’autorisation de proximité pour découvrir les appareils.");
            homeActionButton.setText("AUTORISER LA DÉCOUVERTE");
            homeActionButton.setVisibility(View.VISIBLE);
            homeActionButton.setOnClickListener(v -> beginDedicatedServerSetup());
        } else if (!paired) {
            homeAction.setText("Le téléphone est prêt localement. Connectez le PC sans saisir d’adresse ni de token.");
            homeActionButton.setText("RECHERCHER LE PC");
            homeActionButton.setVisibility(View.VISIBLE);
            homeActionButton.setOnClickListener(v -> {
                showScreen("DEVICES");
                autoConnect();
            });
        } else if (!tlsPinned) {
            homeAction.setText("La confiance PC existe mais le canal pinné doit être finalisé automatiquement.");
            homeActionButton.setText("SÉCURISER LA CONNEXION");
            homeActionButton.setVisibility(View.VISIBLE);
            homeActionButton.setOnClickListener(v -> autoConnect());
        } else if (failures > 0 && networkAvailable) {
            homeAction.setText("La dernière liaison PC a rencontré des échecs; l’état local reste sûr.");
            homeActionButton.setText("RECONNECTER");
            homeActionButton.setVisibility(View.VISIBLE);
            homeActionButton.setOnClickListener(v -> autoConnect());
        } else if (!battery) {
            homeAction.setText("BCP fonctionne, mais Android peut limiter le service écran éteint.");
            homeActionButton.setText("RENFORCER LE MODE 24/7");
            homeActionButton.setVisibility(View.VISIBLE);
            homeActionButton.setOnClickListener(v -> beginDedicatedServerSetup());
        } else {
            homeAction.setText("Aucune action requise.");
            homeActionButton.setVisibility(View.GONE);
        }
    }

    private void refreshHumanData() {
        if (client == null || io.isShutdown()) return;
        io.submit(() -> {
            try {
                JSONObject missions = client.localMissionSteps(20, false);
                JSONObject events = client.localEventTail(12);
                int pending = EdgeDatabase.get(MainActivity.this).edgeDao().countPendingJobs();
                runOnUiThread(() -> applyHumanData(missions, events, pending));
            } catch (Exception ignored) {}
        });
    }

    private void applyHumanData(JSONObject missions, JSONObject events, int pending) {
        try {
            lastPendingJobs = Math.max(0, pending);
            JSONArray m = missions.optJSONArray("mission_steps");
            JSONArray e = events.optJSONArray("events");
            lastMissionCount = m == null ? 0 : m.length();
            lastEventCount = e == null ? 0 : e.length();

            int active = 0, done = 0, attention = 0;
            StringBuilder missionText = new StringBuilder();
            if (m != null) {
                for (int i = 0; i < m.length(); i++) {
                    JSONObject row = m.optJSONObject(i);
                    if (row == null) continue;
                    String provider = row.optString("provider_state", "NOT_DISPATCHED");
                    if ("RESULT_COMMITTED".equals(provider) || "SUPERSEDED".equals(provider)) done++;
                    else if ("OUTCOME_UNKNOWN".equals(provider) || "PLATFORM_HOLD".equals(provider)
                            || "INTERRUPTED".equals(provider)) attention++;
                    else active++;
                    if (i < 8) {
                        if (missionText.length() > 0) missionText.append("\n\n");
                        missionText.append("• ")
                                .append(humanize(row.optString("requested_operation", "Mission")))
                                .append("\n  ").append(humanMissionState(provider));
                        String next = row.optString("next_safe_action", "").trim();
                        if (!next.isEmpty()) missionText.append(" · ").append(humanize(next));
                    }
                }
            }
            activitySummary.setText(
                    "En cours: " + active
                            + " · Action/attention: " + attention
                            + " · Terminées: " + done
                            + "\nFile durable: " + lastPendingJobs + " tâche(s)");
            activityList.setText(missionText.length() == 0
                    ? "Aucune mission récente sur ce téléphone."
                    : missionText.toString());

            StringBuilder eventText = new StringBuilder();
            StringBuilder homeText = new StringBuilder();
            if (e != null) {
                for (int i = 0; i < e.length(); i++) {
                    JSONObject row = e.optJSONObject(i);
                    if (row == null) continue;
                    String event = humanize(row.optString("event_type", "Événement"));
                    String truth = row.optString("truth_status", "OBSERVED");
                    if (i < 6) {
                        if (eventText.length() > 0) eventText.append("\n");
                        eventText.append("• ").append(event)
                                .append(" · ").append(humanTruth(truth));
                    }
                    if (i < 3) {
                        if (homeText.length() > 0) homeText.append("\n");
                        homeText.append("• ").append(event);
                    }
                }
            }
            activityEvents.setText(eventText.length() == 0
                    ? "Aucun événement Chronicle récent."
                    : eventText.toString());
            homeRecent.setText(homeText.length() == 0
                    ? "Aucun événement récent."
                    : homeText.toString());
            refreshLocalPanels();
        } catch (Exception ignored) {}
    }

    private String humanMissionState(String state) {
        if ("RESULT_COMMITTED".equals(state)) return "Terminée";
        if ("RESULT_OBSERVED".equals(state)) return "Résultat reçu · validation";
        if ("STREAM_OBSERVED".equals(state)) return "Traitement en cours";
        if ("PROVIDER_ACKED".equals(state)) return "Acceptée";
        if ("DISPATCH_ATTEMPTED".equals(state)) return "Envoi en cours";
        if ("PLATFORM_HOLD".equals(state)) return "Action requise / plateforme en attente";
        if ("INTERRUPTED".equals(state)) return "Interrompue · reprise disponible";
        if ("OUTCOME_UNKNOWN".equals(state)) return "Résultat à vérifier";
        if ("RECONCILING".equals(state)) return "Réconciliation";
        if ("SUPERSEDED".equals(state)) return "Remplacée";
        return "Reçue";
    }

    private String humanTruth(String truth) {
        if ("VERIFIED".equals(truth)) return "vérifié";
        if ("REPORTED".equals(truth)) return "signalé";
        if ("INFERRED".equals(truth)) return "déduit";
        if ("MODEL_GENERATED".equals(truth)) return "proposé";
        if ("UNKNOWN".equals(truth)) return "à vérifier";
        return "observé";
    }

    private String humanState(String state) {
        if ("READY".equals(state) || "AVAILABLE".equals(state) || "TLS_PINNED".equals(state)) return "prêt";
        if ("PERMISSION_REQUIRED".equals(state) || "WAITING_AUTH".equals(state)) return "autorisation";
        if ("DEGRADED".equals(state) || "PENDING".equals(state)) return "à surveiller";
        if ("UNAVAILABLE".equals(state)) return "indisponible";
        return humanize(state);
    }

    private String humanize(String value) {
        String s = value == null ? "" : value.trim().replace('_', ' ');
        if (s.isEmpty()) return "—";
        s = s.toLowerCase(java.util.Locale.ROOT);
        return Character.toUpperCase(s.charAt(0)) + s.substring(1);
    }

    private void showTrustDetails() {
        String server = client.getServer();
        String pin = client.getPcTlsCertSha256();
        String pinHint = pin.length() >= 16 ? pin.substring(0, 16) + "…" : (pin.isEmpty() ? "non établi" : pin);
        new AlertDialog.Builder(this)
                .setTitle("Confiance PC")
                .setMessage("Canal: " + (server.startsWith("https://") ? "HTTPS / TLS pinné" : "non établi")
                        + "\nEmpreinte certificat: " + pinHint
                        + "\nAdresse technique: " + (server.isEmpty() ? "non enregistrée" : server)
                        + "\n\nLe token d’appairage n’est jamais affiché.")
                .setPositiveButton("OK", null)
                .show();
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
        if (client != null) {
            refreshLocalPanels();
            io.submit(() -> {
                try { client.refreshCapabilityRegistry(); } catch (Exception ignored) {}
                runOnUiThread(() -> {
                    refreshLocalPanels();
                    refreshHumanData();
                });
            });
        }
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
                    refreshHumanData();
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
                    refreshHumanData();
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
            String tlsFp = p.optString("tls_cert_sha256", "");
            String hint = fp.isEmpty() ? "indisponible"
                    : fp.substring(0, Math.min(12, fp.length()));
            String tlsHint = tlsFp.isEmpty() ? "indisponible"
                    : tlsFp.substring(0, Math.min(16, tlsFp.length()));
            new AlertDialog.Builder(this)
                    .setTitle("Confirmer ce PC")
                    .setMessage(pc + (version.isEmpty() ? "" : " · BCP " + version)
                            + "\nIdentité PC: " + hint
                            + "\nEmpreinte TLS: " + tlsHint
                            + "\n\nCette confirmation lie ce téléphone au certificat TLS de ce PC.")
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
                    refreshHumanData();
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
                "Registre capacités / sources",
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
                        runAction("CAPACITÉS / SOURCES", () -> client.localCapabilities());
                    } else if (which == 9) {
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
                    refreshHumanData();
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
        this.busy = busy;
        if (connect != null) connect.setEnabled(!busy);
        if (settings != null) settings.setEnabled(!busy);
        if (checkpoint != null) checkpoint.setEnabled(!busy);
        if (resume != null) resume.setEnabled(!busy);
        if (serverMode != null) serverMode.setEnabled(!busy);
        if (homeActionButton != null) homeActionButton.setEnabled(!busy);
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
