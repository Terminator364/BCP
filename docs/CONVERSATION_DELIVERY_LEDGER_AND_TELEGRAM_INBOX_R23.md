# Conversation Delivery Ledger & Telegram Inbox — R23

Status: IMPLEMENTED CANDIDATE / FIELD UNVERIFIED
Date: 2026-09-20

## Purpose

R23 addresses a recurrent field failure: ChatGPT may finish work or produce a response, while the user's phone never visibly receives that response because of mobile RAM pressure, app/UI interruption, network loss, or platform verification friction.

BCP must separate **work completion** from **message delivery**.

The Telegram cockpit exposes **💬 Conversations**, a low-data inbox for the most recent BCP-aware conversations (X/Y/Z), their last mirrored messages, and their delivery evidence.

## Truth boundary

BCP MUST NOT claim it can continuously read arbitrary private ChatGPT UI history.

For standard ChatGPT UI conversations:
- a message appears in the ledger only after a supported BCP/ChatGPT-PC/external receipt mirrors it;
- absence from the ledger does not mean the message did not exist;
- `CHATGPT_UI_DELIVERY_UNKNOWN` means BCP has durable content/evidence but no proof the ChatGPT mobile/web UI displayed it.

For OpenAI API / BCP-agent conversations, a supported client may mirror message receipts directly into the ledger.

## Delivery states

The ledger distinguishes:
- `GENERATED` — producer reports the message was generated;
- `MIRRORED_BCP` — content is durably stored in BCP;
- `TELEGRAM_SENT` — Telegram transport positively accepted a mirrored notification/message;
- `USER_SEEN` — explicit user acknowledgement exists;
- `CHATGPT_UI_DELIVERY_UNKNOWN` — no reliable ChatGPT UI display receipt exists;
- `DELIVERY_GAP_DETECTED` — BCP detects a durable work/message record without expected downstream delivery evidence.

These states are not interchangeable.

## Durable schema

Local SQLite stores:
- conversation id (short bounded identifier);
- human alias;
- source kind: CHATGPT_UI, CHATGPT_PC, OPENAI_API, or BCP_AGENT;
- source reference;
- monotonic local sequence;
- role;
- bounded/redacted message text;
- generated/mirrored timestamps;
- delivery state;
- evidence class;
- optional linked mission id;
- content hash;
- explicit seen timestamp.

Message insertion is idempotent by conversation + message key. Duplicate keys do not create duplicate Telegram history.

## Privacy and security

- Full conversation text remains local to the BCP PC by default.
- GitHub release metadata never contains user conversation bodies.
- External runtime telemetry SHOULD mirror only counts/state/hashes, not full conversation text.
- Common credential/token patterns are redacted before durable storage.
- Message bodies are bounded.
- The ledger is not a substitute for the user's ChatGPT account archive.

## Telegram UX

Primary button: **💬 Conversations**.

The inbox shows up to the most recent five BCP-aware conversations with:
- alias/source;
- last activity;
- latest delivery state;
- last two mirrored message previews;
- short conversation id.

Detailed command:
- `/conversation <ID>` shows a bounded recent turn window.

Human labels:
- 📝 generated;
- 🪞 BCP mirror;
- 📬 sent to Telegram;
- 👁 seen;
- ❔ ChatGPT display not confirmed;
- ⚠️ delivery uncertain.

A message being visible in Telegram is useful redundancy, but it does not prove that the ChatGPT app displayed the corresponding answer.

## Transport parity

DIRECT_TELEGRAM and NEXUS both expose `bcp:conversations` -> `/conversations`.

Callback data remains compact and within Telegram limits. Detailed conversation selection initially uses a short local id; later rich dynamic per-thread buttons may be added after field qualification.

## Offline behavior

The ledger is local SQLite/WAL and therefore remains available while external Internet is unavailable.

When a producer or transport reconnects:
- messages are appended using idempotency keys;
- sequence gaps remain detectable;
- a future B-EDGE replication layer may carry a sanitized bounded subset;
- canonical message bodies are not silently uploaded to public infrastructure.

## Delivery-gap detection target

A future producer integration SHOULD create a gap signal when:
1. durable mission/work proof says a user-facing response was produced;
2. a corresponding message mirror exists or was expected;
3. no downstream delivery/acknowledgement evidence appears within a bounded interval.

That signal belongs to Telegram Attention Lifecycle and is subject to deduplication/anti-flap rules. It must never fabricate hidden ChatGPT state.

## Five-minute work cadence

For interactive development sessions, the project should checkpoint approximately every bounded work tranche rather than remaining silent for long periods. This is an interaction strategy, not a scheduled background ChatGPT automation.

The durable checkpoint records:
- what changed;
- which CI/tests are still running;
- next atomic action;
- whether a human gate actually exists.

## Field acceptance

PASS requires:
1. exact-head server/Telegram/Nexus/coordinated/field CI green;
2. BCP 0.7.1 resident;
3. Telegram V12 resident;
4. a BCP-aware test conversation with user + assistant message receipts;
5. Conversations button displays the thread and previews;
6. `CHATGPT_UI_DELIVERY_UNKNOWN` renders as uncertainty, not success/failure;
7. duplicate message key produces no duplicate row;
8. secret-pattern redaction verified;
9. direct and Nexus callbacks remain equivalent;
10. restart/offline/reconnect preserves the ledger.

Until these pass, R23 remains FIELD_UNVERIFIED.
