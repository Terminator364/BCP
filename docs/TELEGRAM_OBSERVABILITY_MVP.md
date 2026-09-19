# BCP — Telegram Observability MVP and ChatGPT Visibility Contract

Status: MVP-0 IMPLEMENTED ON WORK BRANCH — CI/FIELD QUALIFICATION PENDING
Adopted: 2026-09-19

## Objective

Give the user one lightweight Telegram view of real project activity so GitHub email is no longer the primary progress signal.

The cockpit aggregates only externally observable truth.

## Event sources

1. BCP runtime and Mission Event Journal.
2. GitHub commits / PR / Actions receipts.
3. BuildHub job receipts.
4. B-EDGE / PC telemetry.
5. Model Broker request lifecycle.
6. ChatGPT-related work only when it creates an external observable event through BCP, GitHub, Drive, a connector, or another qualified integration.

## ChatGPT visibility contract

BCP MUST distinguish:

### OBSERVED_CHAT_ACTION
Examples:
- a BCP job was dispatched to a ChatGPT-capable connector;
- a GitHub commit or PR was created by that conversation;
- a receipt/checkpoint was persisted;
- a supported API/connector returned a response.

### CHAT_WAITING
A request was dispatched but no external completion receipt is available yet.

### CHAT_PLATFORM_HOLD_REPORTED
The user/client reports a ChatGPT verification/hold state, or a qualified client surface exposes it.

### UNKNOWN_INTERNAL_CHAT_STATE
The standard ChatGPT UI is thinking/blocked but BCP has no supported telemetry channel.

BCP MUST NOT claim to see hidden chain-of-thought, private internal micro-actions, or OpenAI's internal verification progress.

## Telegram compact status

Example:

MISSION 48273195
Project: API/BCP
Canonical state: SAFE
Git writer: work/bcp/<mission>
Last observed:
  10:21:07 COMMIT abc123
Current:
  CHAT_WAITING — no completion receipt yet
GitHub CI:
  Windows 3/4 gates PASS
  Release manifest FAIL
BCP runtime:
  heartbeat age 18s
Spend: $0.00

## Commands

Initial read-only MVP:
- /status
- /project <id>
- /job <code>
- /last
- /ci
- /holds

Second stage:
- /run or numeric action 1
- /pause
- /resume
- /cancel_safe
- /approve <code>

## Notification policy

Push notifications only for:
- COMMITTED / CHECKPOINTED milestones;
- CI failure that blocks progression;
- recovery/takeover;
- provider capacity hold;
- human approval required;
- mission DONE.

Healthy heartbeats are visible on demand but do not spam Telegram.

## Data and security

- Bot token is stored only in local/secret storage, never committed.
- One allowlisted Telegram user/chat identity for the initial deployment.
- No secrets, full prompts, tokens, API keys or sensitive payloads in Telegram messages.
- Job codes are locators, not credentials.
- Mutating Telegram actions require BCP authorization/idempotency/fencing.

## Implementation order

MVP-0: read-only status from already-existing BCP/GitHub/Drive evidence.
MVP-1: Mission Event Journal aggregation.
MVP-2: mission creation and action 1 = EXECUTE_DEEP.
MVP-3: provider-neutral AI work through Model Broker.
MVP-4: supported ChatGPT connector lifecycle events where the product surface actually allows them.

The MVP can be useful before any external AI provider is installed.


## MVP-0 implementation refinement — 2026-09-19

This section REFINEs the existing requirement set. It does not supersede the Mission Event Journal, Model Broker, BuildHub, Drive, Git writer fence, user-friction, or later Telegram control-plane requirements.

### Runtime placement

The first read-only Telegram adapter is hosted by B-EDGE so the ~4 GB Windows PC does not gain another always-resident control-plane daemon.

The implementation uses:
- an explicit user-enabled foreground observability service for low-latency Telegram long polling;
- a visible persistent notification while that service is active;
- WorkManager as a recovery/fallback poller;
- a service-liveness fence so WorkManager does not race the active long poller;
- bounded exponential retry after network/API failure.

Correctness does not depend on Android keeping the service process immortal. Durable bot configuration, update offset and allowlist state are reconstructable after process loss.

### MVP-0 security and authority

MVP-0 is strictly read-only:
- supported commands remain /status, /project, /job, /last, /ci, /holds and /help;
- /run, /pause, /resume, /cancel_safe and /approve remain out of scope until the later mutating control plane is fenced by BCP authorization/idempotency/revision rules;
- the Telegram bot token is stored using Android Keystore-backed AES-GCM local storage and is never committed or rendered back to the user;
- the first Telegram private-chat identity is only a PENDING candidate;
- BCP Edge requires a physical in-app confirmation before that chat/user pair becomes the sole allowlisted identity;
- unapproved identities receive no project status.

### Evidence truth contract

The MVP may read:
- BCP runtime/project state through the already-paired local BCP API;
- B-EDGE durable project registry and sanitized local event types;
- public GitHub main/Actions state for public BCP/BuildHub repositories.

It must preserve the existing ChatGPT visibility contract. When there is no qualified external receipt for ChatGPT internal activity, the rendered state is UNKNOWN_INTERNAL_CHAT_STATE rather than guessed progress.

### Recovery behavior

The active long poller records a lightweight local liveness timestamp. WorkManager fallback exits without polling while that timestamp is fresh, preventing competing Telegram getUpdates consumers. If the foreground service is killed or the process is lost, the fallback may resume after the liveness fence expires.

### Qualification gates

Before integration into canonical main:
1. Android unit tests pass, including read-only command parsing and ChatGPT visibility-state regression tests.
2. Android lint passes.
3. debug and unsigned release APK compilation passes.
4. static guards prove no token-shaped literal is committed in Android source.
5. static guards prove MVP-0 contains no /run mutating command.
6. manifest/foreground-service declarations compile against targetSdk 35.
7. branch head is bound to the exact successful CI run.
8. main is re-read immediately before integration; moved main requires reconciliation/requalification.

### First unavoidable human gate

After code/CI qualification and integration, live Telegram field acceptance requires a real bot credential created/owned by the user. BCP must not fabricate, scrape or commit this secret.

The intended one-time physical flow is:
1. user obtains a Telegram bot token from BotFather;
2. token is entered locally in BCP Edge and verified with getMe;
3. user sends /start to the bot;
4. BCP Edge detects the candidate Telegram identity;
5. user physically confirms that identity in BCP Edge;
6. /status and the remaining read-only commands are field-tested.

This credential/identity step is the first real human gate for MVP-0.
