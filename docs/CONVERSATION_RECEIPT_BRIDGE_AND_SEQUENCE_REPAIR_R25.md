# Conversation Receipt Bridge & Sequence Repair — R25

Status: IMPLEMENTED CANDIDATE / FIELD UNVERIFIED
Date: 2026-09-20

## Goal

R25 turns the R23/R24 ledger into an automatically feedable local subsystem without making ChatGPT UI history or the phone the source of truth.

A BCP-aware producer (ChatGPT-PC, BCP agent, OpenAI API client, or future local bridge) may append compact receipts to a local append-only JSONL inbox. The resident BCP server ingests them automatically.

## Receipt contract

Schema: `bcp.conversation_receipt/2`.

Required semantic fields:
- conversation_id;
- message_key;
- role;
- text.

Supported evidence fields:
- alias;
- source_kind;
- source_ref;
- generated_at;
- delivery_state;
- evidence_class;
- linked_mission_id;
- producer_session_id;
- producer_sequence.

No receipt can prove that the ChatGPT mobile/web UI rendered the message unless a separate positive receipt establishes that fact.

## Local-first ingestion

Canonical inbox:
`%LOCALAPPDATA%\ChatGPT_ManagedApps\bcp\state\CONVERSATION_RECEIPTS.jsonl`.

BCP:
- polls locally at a low frequency;
- reads incrementally from a durable byte offset;
- consumes a bounded number of lines per pass;
- accepts duplicate message keys idempotently;
- advances past malformed/oversized receipts instead of permanently blocking the queue;
- does not upload the canonical transcript to GitHub/Nexus/Drive.

If the producer log is truncated/rotated, an invalid cursor safely resets to the beginning; message idempotency prevents replay duplication.

## Producer sequence repair

For each conversation + producer session, positive `producer_sequence` values form a monotonic producer stream.

BCP derives sequence gaps dynamically from durable receipts:
- 41,42,44 => gap 43;
- if 43 arrives later, the gap automatically disappears;
- receipt arrival order does not define conversational order;
- local BCP `sequence` remains a durable ingestion sequence and is separate from producer sequence.

Sequence gaps are evidence of incomplete receipt synchronization only. They are not evidence that ChatGPT failed to generate a response.

## Telegram UX

The Conversations inbox shows:
- potentially missed-response delivery gaps from R24;
- **Synchronisation incomplète** when producer sequence numbers are missing;
- missing range and producer session in the detailed conversation view.

An unresolved sequence gap raises WATCH attention and is subject to the existing acknowledgement, anti-flap and notification-budget policy.

## Security / privacy

- local-only canonical bodies by default;
- bounded text + existing secret-pattern redaction;
- no BotFather/OpenAI/GitHub tokens in receipt logs;
- local producers SHOULD use the authenticated HTTP API where possible; the file inbox is a same-machine interoperability bridge;
- the inbox is not an authorization boundary for arbitrary network peers.

## Acceptance

PASS requires:
1. receipt 1 + receipt 3 produces a sequence-gap indication;
2. late receipt 2 removes the gap;
3. duplicate message key creates no duplicate conversation row;
4. process restart resumes from cursor;
5. cursor beyond a truncated file safely resets;
6. malformed line does not poison following valid receipts;
7. Telegram shows incomplete synchronization honestly;
8. no hidden ChatGPT-state claim;
9. exact-head CI green on Windows/Linux/field-shaped profile;
10. resident BCP 0.7.3 + Telegram V14 readback before field-verified status.
