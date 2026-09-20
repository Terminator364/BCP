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
    require(server, "AUTO_UPDATE_INTERVAL_SECONDS", "WAITING_FOR_PC")
    require(edge_policy, "PC_MEMORY_PRESSURE", "WAITING_FOR_PC")
    require(
        edge_policy,
        "PC_UNAVAILABLE_RECOVERY",
        "sentinelStaleMs",
        "sentinelAlertCooldownMs",
    )
    require(edge_db, "EdgeSentinelEntity.class", "Migration(1, 2)", "addMigrations(MIGRATION_1_2)")
    require(edge_worker, "sentinel_state", "resume_pending", "return Result.success(out);")
    require(edge_scheduler, "15, TimeUnit.MINUTES, 5, TimeUnit.MINUTES")

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
        "MANAGED_WRANGLER_NO_SCRIPTS_INSTALL_FAILED",
        "--ignore-scripts",
        "@esbuild\\win32-x64\\esbuild.exe",
        "node_modules\\wrangler\\bin\\wrangler.js",
        "node_modules\\npm\\bin\\npm-cli.js",
        "MANAGED_NODE_SHA256_MISMATCH",
        "NPM_CONFIG_PREFER_OFFLINE",
        "NPM_CONFIG_FETCH_RETRIES",
    )
    assert re.search(r'\$NodeVersion\s*=\s*"24\.21\.0"', bootstrap)
    assert re.search(r'\$WranglerVersion\s*=\s*"4\.135\.0"', bootstrap)
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
