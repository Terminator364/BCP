# BCP — Telegram Observability MVP and ChatGPT Visibility Contract

Status: IMPLEMENTATION-READY DESIGN
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
