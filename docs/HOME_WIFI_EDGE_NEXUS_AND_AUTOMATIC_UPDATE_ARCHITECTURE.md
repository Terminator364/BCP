# BCP — Home-WiFi Edge, Telegram Nexus and Automatic Update Architecture

Status: CANONICAL REFINEMENT — NEXUS MVP IMPLEMENTED / FIELD UNVERIFIED
Date: 2026-09-19
Scope: API/BCP, B-EDGE, Telegram cockpit, release/update plane

## Field topology correction

The physical network model is:

- **PC-WORKER**: Windows PC, normally on the home Wi-Fi.
- **B-EDGE**: dedicated old Android phone, also normally on the same home Wi-Fi. It is **not** assumed to have cellular data.
- **CURRENT PHONE**: the user's daily phone. It may use home Wi-Fi or mobile data, but it is a human client only and MUST NOT be required as an always-on relay.
- **Internet/cloud services**: Telegram, GitHub, Drive and an optional zero-cost BCP Nexus relay.

This supersedes any architecture that assumes B-EDGE can routinely switch to mobile data.

## Objective

Keep the PC and B-EDGE on the home LAN, minimize paid mobile-data use, preserve control/observability during intermittent connectivity, and remove routine manual downloading/copying of BCP updates.

The user must not be the transport, telemetry, update or secret-copy bus.

## Preferred transport stack

### Path A — local LAN first

PC-WORKER <-> B-EDGE uses the authenticated local LAN channel for:
- mission/event replication;
- status and heartbeat;
- update metadata exchange;
- compact receipts;
- queued commands;
- local recovery coordination.

This path consumes no mobile data.

### Path B — direct Internet services when healthy

PC-WORKER and B-EDGE may use normal HTTPS to GitHub/Drive/BCP Nexus when reachable.

Direct PC -> Telegram Bot API is opportunistic only. It MUST NOT be a single point of failure because field evidence showed Telegram TCP/443 can time out on the home-WiFi path.

### Path C — BCP Nexus relay for Telegram

When direct Telegram egress is unreliable, use a small HTTPS relay reachable by the home-WiFi path:

Telegram -> HTTPS webhook -> BCP Nexus -> durable compact command/event queue
PC/B-EDGE -> HTTPS fetch/ack to BCP Nexus
BCP Nexus -> Telegram sendMessage

The Nexus:
- is transport/control-plane only, never canonical project memory;
- stores only minimal queue/event state and no large project payloads;
- uses authenticated device requests and idempotency keys;
- accepts webhook updates only with Telegram webhook secret validation;
- does not expose bot token to PC/phone clients unless the chosen implementation requires it;
- must operate under ZERO_USD policy;
- must degrade to local queueing if unavailable.

A Cloudflare-Workers-class implementation is a candidate because a free request tier exists, but free-tier availability/limits are field-validated before promotion and are never assumed unlimited.

### Path D — offline store-and-forward

If the home Internet path cannot reach Telegram or Nexus:
- PC and B-EDGE continue local deterministic work;
- outbound notifications/commands remain in durable outbox;
- status remains available locally;
- no committed action is replayed;
- reconnect flushes only unacknowledged idempotent messages.

The current phone is never required to tether the PC for routine operation.

## Telegram architecture

Preferred steady state:
- Telegram uses webhook delivery to BCP Nexus rather than competing long-polling workers.
- Only one Telegram update-consumer mode is active at a time.
- getUpdates remains a diagnostic/fallback mode after webhook removal.
- 409 conflict from concurrent getUpdates consumers is treated as configuration/ownership conflict, not retried indefinitely.

The bot remains a cockpit, not canonical state.

## Human-first progress surface

The default Telegram status is compact and nontechnical.

Example:

BCP — Mission 48273195
[██████░░░░] 6/10 verified steps
✅ Context loaded
✅ Local plan stored
✅ PC worker ready
✅ B-EDGE paired
✅ GitHub update published
✅ Checkpoint written
🔄 CI qualification
⏳ Field validation
Next action: wait for CI result
Network: home Wi-Fi / delayed
Spend: $0.00

Rules:
- percentage is allowed only when derived from a finite declared step set;
- hidden ChatGPT reasoning is never represented as progress;
- every completed step needs durable evidence/receipt;
- if no new evidence exists, report NO_NEW_EXTERNAL_EVIDENCE;
- routine healthy heartbeats do not spam the user.

## Automatic release/update plane

### Release train

Every coordinated BCP release produces a signed/hashed release manifest containing at minimum:
- product/version;
- compatibility range;
- source commit;
- artifact URL or Drive file ID;
- SHA-256;
- signing identity/signature where supported;
- minimum required B-EDGE/PC protocol version;
- rollback version;
- release channel: TEST / CURRENT / ROLLBACK;
- qualification receipt references.

Only a fully qualified release may advance CURRENT.

### PC automatic update

PC-WORKER:
1. checks the small CURRENT manifest on startup/reconnect and at a low-frequency bounded interval;
2. performs no download when version/hash is unchanged;
3. downloads only over an allowed non-metered path by default;
4. verifies source allowlist, hash and signature/pinned identity;
5. stages update separately from live runtime;
6. takes a rollback snapshot;
7. atomically switches version;
8. restarts the managed BCP runtime;
9. runs health/readback;
10. commits success only after machine-readable receipt;
11. rolls back automatically on failed acceptance.

No repeated user PowerShell setup is normal operation after field qualification.

### B-EDGE automatic update

B-EDGE:
1. checks CURRENT metadata with WorkManager/reconnect-triggered work, not a permanent tight loop;
2. downloads a new APK only when on allowed Wi-Fi and only when version changes;
3. stores it in app-owned cache;
4. verifies package/signature/hash and compatibility before presenting it;
5. preserves the current working APK/metadata for rollback;
6. invokes Android Package Installer only when required.

On ordinary non-rooted Android, final APK installation confirmation may still require one human approval. The architecture MUST NOT claim silent install unless a separately qualified device-owner/managed-device path proves it.

After verified install:
- temporary APK payload is deleted;
- B-EDGE reconnects;
- version/compatibility receipt is emitted;
- rollback remains available.

### Drive/GitHub publication

- GitHub is source/build/CI authority for public BCP code.
- Drive CURRENT is the user-facing distribution mirror and recovery location.
- Publishing a new qualified release replaces CURRENT in place, preserves only the bounded rollback history, and cleans failed/superseded temporary payloads.
- This publication is event-driven by release qualification, not by a ChatGPT scheduled automation.
- No hourly/daily ChatGPT automation is required.

## Data-saver rules

- LAN traffic is preferred between PC and B-EDGE.
- No large artifact is transferred through Telegram.
- No full project context is sent to the Nexus.
- Use hashes/deltas/compact receipts.
- Do not poll Telegram or cloud status aggressively.
- Current phone mobile data is not infrastructure capacity and is never budgeted as such.
- Large downloads are deferred when only metered/unstable connectivity is available.

## Failure classification

Required states:
- HOME_LAN_OK
- HOME_INTERNET_DEGRADED
- TELEGRAM_DIRECT_DEGRADED
- NEXUS_REACHABLE
- NEXUS_UNREACHABLE
- NETWORK_OFFLINE_QUEUEING
- UPDATE_AVAILABLE
- UPDATE_STAGED
- UPDATE_APPLYING
- UPDATE_VERIFIED
- UPDATE_ROLLBACK
- HUMAN_ANDROID_INSTALL_APPROVAL_REQUIRED
- NO_NEW_EXTERNAL_EVIDENCE

No network failure may erase canonical state.

## Implementation order

1. Preserve the already field-working Telegram cockpit and 0.4.7 acceptance line.
2. Correct topology assumptions: B-EDGE has home Wi-Fi only; current phone is not a relay.
3. Add a transport abstraction: DIRECT_TELEGRAM, NEXUS_WEBHOOK, LOCAL_OUTBOX.
4. Implement the webhook/Nexus candidate behind a feature flag and validate it from the actual home Wi-Fi.
5. Move Telegram steady state to webhook/Nexus only after field PASS.
6. Add unified CURRENT release manifest.
7. Add PC staged self-update + automatic rollback.
8. Add B-EDGE Wi-Fi-only update downloader + one-tap Android install approval.
9. Add finite-step mission progress journal and human-first status.
10. After these P0/P1A gates pass, resume the broader API/BCP Model Broker and multi-project orchestration roadmap.

## Acceptance gates

Transport is accepted only when:
- PC and B-EDGE remain on home Wi-Fi;
- current phone may independently be on Wi-Fi or mobile data;
- /status reaches the user without requiring PC hotspot/tethering;
- Telegram direct failure does not stop local BCP work;
- Nexus outage queues and later replays without duplicate effects;
- no secret is copied through chat/Drive/GitHub;
- no large mobile-data transfer is required;
- spend remains $0.00.

Update plane is accepted only when:
- a new qualified release appears as CURRENT without manual file sorting;
- unchanged versions cause zero artifact download;
- wrong hash/signature is rejected;
- interrupted download resumes or restarts safely;
- failed PC update rolls back automatically;
- B-EDGE receives the correct APK automatically over Wi-Fi and requires at most the unavoidable Android installation approval;
- receipts prove the installed version;
- old temporary artifacts are cleaned while bounded rollback remains available.


## Implementation checkpoint — Nexus MVP

Implemented candidate components:
- Cloudflare-Workers-class Nexus worker with D1 durable command/reply/outbound tables;
- Telegram webhook secret verification and private-chat allowlist;
- authenticated device pull/reply/push endpoints;
- idempotency reservations for reply/push effects;
- PC observability worker transport abstraction: DIRECT_TELEGRAM remains default, NEXUS is opt-in;
- local Nexus configurator that stores device secret only in BCP local state;
- dedicated CI qualification workflow.

This checkpoint is not FIELD_VERIFIED. Live promotion requires external cloud authorization, provider secret provisioning, webhook ownership migration and a real home-WiFi round-trip.
