# BCP — RDC Network & Data-Saver Policy

Status: ACTIVE REQUIREMENT
Adopted: 2026-09-19
Scope: API/BCP and reusable cross-project transport behavior

## Context

The field environment is Kinshasa with constrained and paid mobile data, intermittent connectivity and a low-resource Windows PC.

Field evidence on 2026-09-19 showed:
- Telegram Bot API works through the user's mobile-data path;
- home Wi-Fi DNS resolves api.telegram.org;
- home Wi-Fi TCP/443 to Telegram times out on the PC;
- the Telegram cockpit itself is otherwise functional and field-proven.

## Core invariants

1. HOME_WIFI_PRIMARY
   - The PC stays on home Wi-Fi by default.
   - Full-PC mobile hotspot is never the normal architecture.

2. MOBILE_DATA_IS_SCARCE
   - Mobile data is a metered fallback, not an assumed always-on resource.
   - Only the smallest required control-plane traffic may use cellular fallback.
   - Large downloads, CI artifacts, APK/ZIP payloads and routine sync must not silently consume cellular data.

3. SELECTIVE_TRANSPORT_FAILOVER
   - Telegram/API control traffic may fail over independently from bulk project traffic.
   - B-EDGE is the dedicated old phone and a first-class local BCP server node; no SIM/cellular capability is assumed. It may use any available Wi-Fi/hotspot uplink while continuing local-LAN service when Internet is absent.
   - The user's current phone may use Wi-Fi or mobile data, but is a human client only and MUST NOT be required as an infrastructure relay.
   - Preferred target: PC and B-EDGE exchange compact control state over authenticated local transport. Direct Telegram is tried first; when it fails, the PC may use the B-EDGE TLS relay, then the B-EDGE durable store-and-forward queue. Nexus/webhook remains an optional remote lane, not the sole authority.
   - Alternative zero-cost relays may be evaluated only after field validation and must not introduce paid spend or false geography.

4. OFFLINE_FIRST_QUEUEING
   - Commands/events are persisted before dispatch.
   - Temporary network loss becomes NETWORK_OFFLINE_QUEUEING, not data loss.
   - Retry uses bounded exponential backoff + jitter.
   - Duplicate delivery is rejected through idempotency/fencing.

5. DATA_MINIMIZATION
   - Compact JSON/events by default.
   - Cache deterministic status and receipts locally.
   - Do not resend unchanged state.
   - Prefer hashes/deltas over full payloads.
   - Healthy heartbeats are on-demand or low-frequency; no chat spam.

6. NO_USER_AS_NETWORK_RELAY
   - The user must not be required to move tokens, logs, IPs, prompts or receipts between devices except as a one-time physical bootstrap when unavoidable.
   - Screenshots remain fallback evidence only.

## Telegram transport target

Preferred adaptive path:

Telegram cloud
   ^                       (when phone uplink exists)
   | direct HTTPS / B-EDGE outbound
B-EDGE full node (Room queue + local API + relay)
   ^
   | authenticated LAN/hotspot; future Wi-Fi Direct/Bluetooth/USB adapters
   v
BCP PC heavy worker

BCP Nexus is an optional remote ingress/witness lane. The old dedicated phone is infrastructure; the user's current personal phone is never a required infrastructure relay. The old phone does not require a SIM.

## Acceptance gates

The transport is FIELD_VERIFIED only when:
- PC remains on home Wi-Fi;
- Telegram /status, /ci and /holds succeed through the selected fallback path;
- no full-PC hotspot is required;
- BCP survives temporary home-Internet/Nexus loss and later resumes without duplicate actions;
- measured Telegram control traffic remains compact;
- spend remains $0.00;
- no VPN, geo-spoofing or unofficial bypass is used.


## Home-WiFi B-EDGE + Nexus refinement

The dedicated old Android phone is the preferred local coordinator/witness, not a cellular relay.

The steady-state routing target is:
`PC-WORKER <-> authenticated home-LAN <-> B-EDGE`
with remote cockpit ingress/egress through a field-qualified zero-cost `BCP_NEXUS` HTTPS relay when direct Telegram egress is degraded.

If no remote route exists, compact events remain in durable local outboxes and resume idempotently after reconnect.

Full-PC mobile hotspot and the user's current phone as a relay are diagnostic/emergency fallbacks only, not product dependencies.

Detailed topology, progress and update architecture:
`docs/HOME_WIFI_EDGE_NEXUS_AND_AUTOMATIC_UPDATE_ARCHITECTURE.md`.


## R65 dedicated-phone data path

The PC must not consume mobile data merely because it can. When B-EDGE is locally reachable, compact BCP control traffic should stay PC<->phone and let the phone own queueing/retry. Bulk downloads/build artifacts remain deferred on metered paths unless the user explicitly requests them.

When the old phone has no Internet but remains locally reachable, it still serves the local API and persists messages/jobs. Remote transport state is `NETWORK_WAIT`.

When the PC and old phone lack a common LAN/router, the next qualified local transport target is Wi-Fi Direct. Bluetooth/BLE is reserved for tiny bootstrap/control traffic and USB for explicit recovery/bootstrap. These are not advertised as FIELD_VERIFIED until device tests pass.
