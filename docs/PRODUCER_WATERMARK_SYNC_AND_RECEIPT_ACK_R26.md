# Producer Watermark Sync & Receipt Acknowledgement — R26

Status: IMPLEMENTED CANDIDATE / FIELD UNVERIFIED
Date: 2026-09-20

## Goal

R26 strengthens R25 by distinguishing “all receipts currently seen” from “all receipts the producer says exist”.

A producer heartbeat publishes a high-water mark:
- conversation id;
- producer session id;
- sequence floor;
- announced sequence;
- source kind/reference;
- heartbeat time.

BCP compares that announced watermark to locally durable receipts.

## Why this matters

Without a producer watermark, receipts 41, 42 could look complete even if the producer had already emitted 43, 44, 45 and the network/app lost them.

With R26:
- producer announces 45;
- BCP has through 42;
- Telegram reports 43–45 missing;
- late receipts repair the gap automatically;
- once all 43–45 arrive, the producer state becomes COMPLETE.

This is synchronization evidence, not hidden ChatGPT-state inference.

## Durable producer state

SQLite table: `conversation_producers`.

Per conversation + producer session:
- source kind/reference;
- sequence floor;
- announced sequence;
- last heartbeat;
- last receipt;
- update time.

BCP derives:
- highest received sequence;
- highest contiguous received sequence;
- missing ranges/count;
- COMPLETE / INCOMPLETE.

## Producer inputs

Supported local receipt:
- `bcp.conversation_producer_heartbeat/1`

Authenticated HTTP:
- POST `/v1/conversations/{id}/producer-heartbeat`

Readback:
- GET `/v1/conversations/producers?conversation_id=...`

The existing R25 JSONL bridge may carry both message receipts and producer heartbeats.

## Durable acknowledgement

BCP writes:
`conversation_receipt_ack.json`

This local acknowledgement summarizes producer watermarks and contiguous receipt progress so same-machine producers can cheaply know what BCP has durably consumed.

No cloud transcript is required.

## Telegram UX

For producer-aware conversations:
- COMPLETE => “🔄 Sync producteur complète jusqu’à #N”
- INCOMPLETE => “🧩 Synchronisation incomplète” with missing ranges
- detailed view shows received vs announced watermark per producer session.

Incomplete producer sync is WATCH-level attention, subject to existing anti-flap/ack/budget rules.

## Truth boundary

Producer watermark proves only what a supported producer reports having emitted.

It does not prove:
- the ChatGPT UI displayed the message;
- the user saw it;
- the model internally completed any un-receipted turn.

## Acceptance

PASS requires:
1. producer announces N with receipts only through N-2 => tail gap appears;
2. late N-1/N receipts remove tail gap;
3. restart preserves producer watermark;
4. local ack file reflects contiguous receipt progress;
5. duplicate receipts remain idempotent;
6. Telegram renders complete/incomplete sync honestly;
7. exact-head Windows/Linux/field-shaped CI green;
8. resident BCP 0.7.4 + Telegram V15 field readback before FIELD_VERIFIED.
