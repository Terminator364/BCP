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
   - Preferred target: B-EDGE performs Telegram transport and returns compact local/LAN events to BCP.
   - If Android network binding is used, bind only Telegram transport to cellular while preserving local B-EDGE<->PC communication over LAN where supported.
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

Preferred steady-state path:

Telegram cloud <-> B-EDGE lightweight Telegram transport
                     |
                     | local authenticated LAN channel
                     v
                    BCP PC

The PC therefore remains on home Wi-Fi. Cellular usage, when required, is limited to the Telegram control-plane bytes on B-EDGE rather than the entire PC network stack.

## Acceptance gates

The transport is FIELD_VERIFIED only when:
- PC remains on home Wi-Fi;
- Telegram /status, /ci and /holds succeed through the selected fallback path;
- no full-PC hotspot is required;
- BCP survives temporary cellular loss and later resumes without duplicate actions;
- measured Telegram control traffic remains compact;
- spend remains $0.00;
- no VPN, geo-spoofing or unofficial bypass is used.


## Selective B-EDGE relay refinement

The dedicated old Android phone is the preferred Telegram relay/witness, not the PC replacement.

The steady-state routing target is:
`PC-WORKER --authenticated LAN--> B-EDGE --Telegram transport--> Telegram`.

B-EDGE keeps local PC communication on the home LAN. If the home-Wi-Fi route to the official Telegram Bot API is unavailable, a qualified Android implementation may bind only the small Telegram control-plane connection to cellular while leaving bulk traffic on Wi-Fi. If no route exists, compact events are queued and later resumed idempotently.

The PC therefore remains on home Wi-Fi. Full-PC mobile hotspot is a diagnostic fallback only, not a product dependency.

Detailed transport/progress/update architecture:
`docs/TELEGRAM_PROGRESS_RELAY_AND_UPDATE_ARCHITECTURE.md`.
