#!/usr/bin/env python3
"""Deterministic preflight for Blessing's real BCP field ecosystem.

This is intentionally network-free. It validates release invariants and the
presence of the recovery paths that field incidents have already proven necessary.
"""
from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def load(path: str):
    return json.loads(read(path))


def require(text: str, *needles: str) -> None:
    missing = [x for x in needles if x not in text]
    assert not missing, f"missing contract markers: {missing}"


def main() -> int:
    current = load("release/current.json")
    server_release = load("release/server.json")
    nexus_release = load("release/nexus_bootstrap.json")
    server = read("windows/bcp_server.py")
    telegram = read("windows/bcp_telegram_observability.py")
    bootstrap = read("windows/BOOTSTRAP_BCP_NEXUS.ps1")
    edge_policy = read("android-b-edge/src/main/java/com/blessing/bcpedge/EdgePolicy.java")
    edge_db = read("android-b-edge/src/main/java/com/blessing/bcpedge/storage/EdgeDatabase.java")
    edge_worker = read("android-b-edge/src/main/java/com/blessing/bcpedge/work/EdgeReconcileWorker.java")
    edge_scheduler = read("android-b-edge/src/main/java/com/blessing/bcpedge/work/EdgeWorkScheduler.java")
    edge_legacy_worker = read("android-b-edge/src/main/java/com/blessing/bcpedge/EdgeReconcileWorker.java")
    edge_app = read("android-b-edge/src/main/java/com/blessing/bcpedge/BcpEdgeApplication.java")
    edge_manifest = read("android-b-edge/src/main/AndroidManifest.xml")
    android_candidate = load("release/android_candidate.json")
    rdc = read("docs/RDC_NETWORK_AND_DATA_SAVER_POLICY.md")

    # Zero-cost + data-saver invariants.
    assert current["zero_usd"] is True
    policy = current["update_policy"]
    assert policy["scheduled_chatgpt_automation"] is False
    assert policy["metered_large_download_default"] is False
    assert policy["unchanged_version_zero_download"] is True
    assert nexus_release["zero_usd"] is True

    # Real Windows/4 GB ecosystem: serialized/low-footprint orchestration and
    # explicit pressure handling must remain represented.
    require(
        server,
        "AUTO_UPDATE_INTERVAL_SECONDS",
        "UPDATE_NETWORK_BACKOFF_SECONDS",
        "_transport_error_detail",
        '"transport_lane": "SERVER"',
        '"transport_lane": "TELEGRAM_COMPANION"',
        '"transport_lane": "NEXUS"',
        "NEXUS_HUMAN_GATE_MANIFEST_WATCH_SECONDS",
        "NEXUS_HUMAN_GATE_MANIFEST_WATCH_MAX_BACKOFF_SECONDS",
        "start_nexus_human_gate_manifest_watcher",
        "HUMAN_GATE_FAST_PATH",
        "WAITING_FOR_PC",
        "_write_utf16_recovery_vbs",
        "ChatGPTPC_RecoveryPlane.vbs",
        "RECOVERY_LAUNCHER_REPAIRED_AND_STARTED",
        "LOCAL_TARGET_NOT_ACTIVE_BRIDGE_STARTED",
        "PACKAGE_SYNC_PENDING_BRIDGE_STARTED",
        "recovery_vbs_utf16_bom_missing",
        "CLOUD_MIRROR_HOLD",
        "_record_telemetry_mirror_hold",
        "SELFTEST_DRIVEFS_FAIL_OPEN",
    )
    require(edge_policy, "PC_MEMORY_PRESSURE", "WAITING_FOR_PC")
    require(
        edge_policy,
        "PC_UNAVAILABLE_RECOVERY",
        "sentinelStaleMs",
        "sentinelAlertCooldownMs",
    )
    require(edge_db, "EdgeSentinelEntity.class", "Migration(1, 2)", "addMigrations(MIGRATION_1_2)")
    require(edge_worker, "sentinel_state", "resume_pending", "return Result.success(out);", "EDGE_RECONCILE_START")
    require(
        edge_scheduler,
        "15, TimeUnit.MINUTES, 5, TimeUnit.MINUTES",
        "NetworkType.CONNECTED",
        "BackoffPolicy.EXPONENTIAL",
        "ExistingWorkPolicy.KEEP",
        "LEGACY_V1_PERIODIC",
        "LEGACY_V1_NOW",
        "LEGACY_V2_PERIODIC",
        "LEGACY_V2_NOW",
    )
    require(edge_legacy_worker, "Compatibility shim", "work.EdgeReconcileWorker.execute")
    assert "enqueueUniqueWork" not in edge_legacy_worker
    assert "enqueueUniquePeriodicWork" not in edge_legacy_worker
    require(
        edge_app,
        "registerDefaultNetworkCallback",
        "TRANSPORT_WIFI",
        "NET_CAPABILITY_VALIDATED",
        "WIFI_VALIDATED_RETURN",
        "MIN_REENTRY_TRIGGER_MS",
    )
    require(edge_manifest, 'android:name=".BcpEdgeApplication"')
    assert android_candidate["version_code"] > 210
    assert android_candidate["publication_allowed"] is False
    assert android_candidate["distribution_status"] == "UNSIGNED_CI_CANDIDATE_NOT_PUBLISHED"

    # Kinshasa/home-Wi-Fi reality: direct Telegram may fail while DNS still works.
    # Nexus must therefore remain an independent HTTPS control-plane route.
    require(
        rdc,
        "home Wi-Fi TCP/443 to Telegram times out on the PC",
        "SELECTIVE_TRANSPORT_FAILOVER",
        "BCP Nexus HTTPS webhook/relay",
        "OFFLINE_FIRST_QUEUEING",
        "bounded exponential backoff",
        "MOBILE_DATA_IS_SCARCE",
    )
    require(telegram, "DIRECT_TELEGRAM", 'mode == "NEXUS"', "backoff = [2, 5, 15, 30, 60]")
    assert telegram.count('"getUpdates"') == 1, "multiple Telegram poller code paths detected"

    # Nexus regression: a silent EXIT 1 from system npx/wrangler must never send
    # the user to a manual Node/Wrangler installation path.
    require(
        bootstrap,
        "WRANGLER_PROBE_EXIT",
        "no stdout/stderr captured",
        "system Wrangler probe failed; switching automatically to managed portable Node/Wrangler",
        "Ensure-ManagedWranglerLauncher",
        "NODE_DIRECT_WRANGLER_CLI",
        "MANAGED_WRANGLER_INSTALL_FAILED",
        "node_modules\\wrangler\\bin\\wrangler.js",
        "node_modules\\npm\\bin\\npm-cli.js",
        "MANAGED_NODE_SHA256_MISMATCH",
        "NPM_CONFIG_PREFER_OFFLINE",
        "NPM_CONFIG_FETCH_RETRIES",
        "MANAGED_NODE_PATH_BINDING_FAILED",
        "MANAGED_NODE_CHILD_PROCESS_PROBE_FAILED",
        '@("login","--device")',
        "BCP_NEXUS_AUTH_DEVICE_FLOW",
        "CLOUDFLARE_DEVICE_AUTH_REQUIRED_OR_EXPIRED",
        "BCP_NEXUS_AUTH_DEVICE_FLOW=HUMAN_AUTH_REQUIRED_OR_EXPIRED",
        "$env:PATH = $nodeHome + ';'",
        '--foreground-scripts',
    )
    assert re.search(r'\$NodeVersion\s*=\s*"24\.21\.0"', bootstrap)
    assert re.search(r'\$WranglerVersion\s*=\s*"4\.135\.0"', bootstrap)
    assert '@("login") -AllowFailure' not in bootstrap
    assert "DEFERRED_FALLBACK_BROWSER" not in bootstrap
    assert re.search(r'\$NodeArchiveSha256\s*=\s*"[0-9a-f]{64}"', bootstrap)

    # Retry/watchdog bounds: no infinite spin in weak connectivity.
    require(
        server,
        "NEXUS_BOOTSTRAP_RETRY_BASE_SECONDS = 5 * 60",
        "NEXUS_BOOTSTRAP_RETRY_MAX_SECONDS = 30 * 60",
        "NEXUS_BOOTSTRAP_MAX_AUTO_ATTEMPTS = 4",
        "NEXUS_BOOTSTRAP_PROCESS_TIMEOUT_SECONDS = 45 * 60",
        "_terminate_nexus_process_tree",
    )

    # Mission stall watchdog: absence of proof must not be confused with progress,
    # retries are bounded, and Telegram exposes a real durable Continue request.
    require(
        server,
        "MISSION_STALE_SECONDS = 10 * 60",
        "MISSION_WATCHDOG_MAX_AUTO_REQUESTS = 3",
        "MISSION_WATCHDOG_COOLDOWNS = (5 * 60, 15 * 60, 60 * 60)",
        "_mission_watchdog_anchor",
        "NOT (event_type='RETRY_SCHEDULED' AND summary LIKE 'Watchdog:%')",
        "request_mission_resume",
        "consume_mission_resume_request",
        "MISSION_RESUME_REQUESTS.jsonl",
        "HUMAN_GATE",
        "NO_CLAIM_OF_CHATGPT_UI_SELF_CONTINUATION" if "NO_CLAIM_OF_CHATGPT_UI_SELF_CONTINUATION" in server else "MISSION_RESUME_REQUEST_PATH",
    )
    require(
        telegram,
        "bcp:continue",
        "/continue",
        "watchdog_notice",
        "Reprise automatique demandée",
        "WATCHDOG_NOTIFY_STATE_PATH",
    )

    # Telegram Rich Cockpit V10 remains an enhancement, never a new failure point.
    # Both direct and Nexus paths must retain V9 fallback and all four reports.
    nexus_worker = read("nexus/cloudflare-worker/src/worker.mjs")
    require(
        telegram,
        "sendRichMessage",
        "rich_message",
        "RICH_MESSAGE_SEND_FALLBACK",
        "RICH_MESSAGE_EDIT_FALLBACK",
        "V9 plain text is mandatory fallback",
        "bcp:since",
        "bcp:why",
        "bcp:risks",
        "bcp:quiet:120",
        "report_devices",
        "report_mission",
        "bcp:conversations",
        "conversation_threads",
        "CHATGPT_UI_DELIVERY_UNKNOWN",
    )
    require(
        nexus_worker,
        "sendRichMessage",
        "rich_message",
        "RICH_V10",
        "V9_PLAIN_FALLBACK",
        "bcp:since",
        "bcp:why",
        "bcp:risks",
        "bcp:quiet:120",
        "bcp:conversations",
        "bcp:pdf:devices",
        "bcp:pdf:mission",
        'version: "0.2.6"',
    )
    # R53 human cockpit: primary labels must be self-explanatory and identical across direct/Nexus.
    require(
        telegram,
        "🟢 Où en sommes-nous ?",
        "🕘 Nouveautés",
        "💬 Messages récents",
        "❓ Pourquoi cet état ?",
        "📍 Étape actuelle",
        "🎯 Objectif & plan",
        "⚙️ Travail récent",
        "🔭 Risques à venir",
        "▶️ Reprendre maintenant",
        "✅ Vu / compris",
        "❔ Aide / mode d’emploi",
        "🧰 Détails techniques",
        "📚 Rapports & technique",
        "def advanced_keyboard",
        "bcp:advanced",
        "réponse(s) ChatGPT sont sauvegardées dans BCP",
        "mail miroir",
    )
    require(
        nexus_worker,
        "🟢 Où en sommes-nous ?",
        "🕘 Nouveautés",
        "💬 Messages récents",
        "❓ Pourquoi cet état ?",
        "▶️ Reprendre maintenant",
        "❔ Aide / mode d’emploi",
        "📚 Rapports & technique",
        "function advancedCockpitKeyboard",
        "bcp:advanced",
        '"bcp:help": "/help"',
    )
    assert "🟢 Situation" not in telegram
    assert "🟢 Situation" not in nexus_worker

    # Progressive disclosure regression: PDF/technical controls belong to the secondary menu.
    telegram_primary = telegram.split("def keyboard() -> dict:", 1)[1].split("def advanced_keyboard() -> dict:", 1)[0]
    nexus_primary = nexus_worker.split("function cockpitKeyboard()", 1)[1].split("function advancedCockpitKeyboard()", 1)[0]
    for deep_label in ("📄 Résumé PDF", "🖥️ État appareils", "🧭 Plan mission", "📚 Audit PDF", "🧰 Détails techniques"):
        assert deep_label not in telegram_primary, ("telegram_primary_leaks_deep_control", deep_label)
        assert deep_label not in nexus_primary, ("nexus_primary_leaks_deep_control", deep_label)
    assert "📚 Rapports & technique" in telegram_primary
    assert "📚 Rapports & technique" in nexus_primary

    # R54 human presentation / PDF parity.
    require(
        telegram,
        "KINSHASA_TZ",
        "human_timestamp",
        "/Encoding /WinAnsiEncoding",
        "/BaseFont /Helvetica-Bold",
        "Page {page_no}/{total_pages}",
        "Heure affichée : Kinshasa",
        "Créé le : ",
        "ACTION POUR VOUS",
    )
    require(
        nexus_worker,
        "pdfWinAnsiEscape",
        "function advancedCockpitKeyboard",
        "/Encoding /WinAnsiEncoding",
        "/BaseFont /Helvetica-Bold",
        "Page ",
        "Heure affichée : Kinshasa",
        "%BCP-HUMAN-PDF",
        "humanTimestampKinshasa",
        'version: "0.2.6"',
    )
    for human_fn_start, human_fn_end in (
        ("def report_summary", "def report_devices"),
        ("def report_devices", "def report_mission"),
        ("def report_mission", "def report_technical"),
    ):
        block = telegram.split(human_fn_start, 1)[1].split(human_fn_end, 1)[0]
        assert "utc_now()" not in block
        assert "nexus_bootstrap_error_class" not in block
        assert "mission_id:" not in block

    assert "allow_paid_broadcast" not in telegram
    assert "allow_paid_broadcast" not in nexus_worker
    assert set(nexus_release["report_exports"]["cached_reports"]) == {
        "summary", "devices", "mission", "technical"
    }

    # Conversation-delivery truth: local ledger exists and UI keeps unknown UI delivery explicit.
    require(
        server,
        "conversation_threads",
        "conversation_messages",
        "CHATGPT_UI_DELIVERY_UNKNOWN",
        "/v1/conversations",
        "_conversation_safe_text",
        "conversation_delivery_gaps",
        '["v1", "conversations", "gaps"]',
        "DERIVED_FROM_BCP_RECEIPTS_NOT_CHATGPT_INTERNAL_STATE",
        "CONVERSATION_RECEIPTS.jsonl",
        "process_conversation_receipt_inbox",
        "conversation_sequence_gaps",
        '["v1", "conversations", "sequence-gaps"]',
        "conversation_producers",
        "conversation_register_producer",
        "conversation_receipt_ack.json",
        '["v1", "conversations", "producers"]',
        '"producer-heartbeat"',
        "sync_chatgpt_pc_flow_ledger",
        "flow_ledger.sqlite3",
        "mode=ro",
        "CHATGPT_PC_FLOW_LEDGER",
        "conversation_latency_summary",
        "MEASURED_FROM_DURABLE_RECEIPT_TIMESTAMPS_ONLY",
    )
    require(
        telegram,
        "CONVERSATIONS SYNCHRONISÉES",
        "affichage ChatGPT non confirmé",
        "/conversation <ID>",
        "Réponse sauvegardée mais lecture non confirmée",
        "mail miroir d’abord",
        "delivery_gap_count",
        "Synchronisation incomplète",
        "sequence_gap_count",
        "conversation_producer_sync",
        "Synchronisation complète jusqu’au message",
        "announced_sequence",
        "chatgpt_pc_flow_bridge",
        "Connexion ChatGPT-PC",
        "conversation_latency_summary",
        "Décomposition temporelle",
        "human_timestamp",
        "KINSHASA_TZ",
        "/Encoding /WinAnsiEncoding",
        "/BaseFont /Helvetica-Bold",
        "ACTION POUR VOUS",
        "Heure affichée : Kinshasa",
    )

    # R53 delivery/cadence policy must remain explicit and machine-checkable.
    cadence_policy = load(".project-memory/INTERACTIVE_WORK_CADENCE_POLICY.json")
    delivery_policy = load(".project-memory/DELIVERY_REDUNDANCY_POLICY.json")
    assert cadence_policy["acceptable_window_minutes"] == [8, 10]
    assert cadence_policy["response_timing"]["user_visible_target_minutes"] == [8, 10]
    assert delivery_policy["cadence"]["work_slice_minutes"] == "8-10"
    assert delivery_policy["channels"]["email"]["body_must_equal_chat_checkpoint_exactly"] is True
    assert delivery_policy["channels"]["email"]["send_before_chat_checkpoint"] is True
    assert delivery_policy["checkpoint_delivery_order"] == [
        "EMAIL_EXACT_MIRROR", "CHATGPT_FINAL", "TELEGRAM_WITNESS_OPTIONAL"
    ]
    assert delivery_policy["ui_policy"]["progressive_disclosure_required"] is True
    guide = read("docs/BCP_COCKPIT_MODE_D_EMPLOI_R54.md")
    require(guide, "mail miroir exact", "d’abord le mail miroir exact", "📚 Rapports & technique", "heure de Kinshasa", "Page X/Y", "UTC+1")
    assert delivery_policy["packaging"]["nested_zip_for_user_action_forbidden"] is True

    # Release coordination remains explicit.
    assert current["components"]["windows_bcp"]["version"] == server_release["version"]
    assert current["components"]["nexus"]["version"] == nexus_release["version"]
    assert current["components"]["nexus"]["auto_update_eligible"] is True

    # Secret hygiene: never hard-code BotFather-style secrets.
    joined = "\n".join((server, telegram, bootstrap))
    assert not re.search(r"\b\d{6,12}:[A-Za-z0-9_-]{20,}\b", joined)

    print("BCP_FIELD_ECOSYSTEM_PREFLIGHT=PASS")
    print("profile=KINSHASA_HOME_WIFI_LOW_RAM_UNSTABLE_NETWORK_ZERO_USD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
