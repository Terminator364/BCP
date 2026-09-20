# ChatGPT-PC Local Flow Ledger Bridge — R27

Status: IMPLEMENTED CANDIDATE / FIELD UNVERIFIED
Date: 2026-09-20

## Goal

R27 connects the real local ChatGPT-PC conversation evidence source to the BCP Conversation Delivery Ledger without modifying ChatGPT-PC's active writer branch.

Source:
`%LOCALAPPDATA%\Tunnel_PC_G4\state\flow_ledger.sqlite3`

BCP opens this SQLite source in **read-only mode** and imports only exact observable conversation-message events:
- `conversation_message_exact`
- `assistant_visible_message_exact`
with role `user` or `assistant`.

## Safety and truth

- ChatGPT-PC remains authoritative for its own flow ledger.
- BCP never writes to the source DB.
- `text_sha256` is rechecked before import.
- ChatGPT-PC `event_id` becomes the idempotent BCP message key.
- Assistant turns are imported as `CHATGPT_UI_DELIVERY_UNKNOWN`: local evidence that the response exists is not proof that the mobile/web ChatGPT UI rendered it.
- Canonical message bodies remain local.

## Resource behavior

- bounded import batch: 24 events;
- bridge executes inside the existing 10-second conversation worker;
- read-only SQLite connection with short timeout;
- cursor persists the last source sequence;
- failure to read the source is fail-open for BCP and reported as `SOURCE_READ_DEFERRED`;
- a bad hash produces `SOURCE_ROW_HOLD` and does not skip past the bad row.

## Conversation mapping

A stable short BCP conversation ID is derived from ChatGPT-PC session/mission identity. Source exact event sequence is retained in `source_ref`; BCP maintains its own per-conversation producer ordinal for R26 watermark/ack semantics.

## Telegram

The Conversations screen exposes bridge health:
- CAUGHT_UP;
- CATCHING_UP + backlog;
- SOURCE_READ_DEFERRED;
- SOURCE_ROW_HOLD;
- NOT_OBSERVED.

## Acceptance

PASS requires:
1. read-only source access;
2. user + assistant exact turns imported;
3. source text hash verified;
4. assistant UI delivery remains unknown unless separate positive evidence exists;
5. second poll creates no duplicate;
6. bad source row holds rather than skipping;
7. ChatGPT-PC open PR #8 remains untouched;
8. exact-head BCP CI green;
9. resident BCP 0.7.5 + Telegram V16 readback before FIELD_VERIFIED.
