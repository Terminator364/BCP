# BCP — Telegram Progress Relay and Automatic Update Architecture

Status: IMPLEMENTATION CANDIDATE
Date: 2026-09-19
Scope: API/BCP, Telegram cockpit, B-EDGE, PC-WORKER
Integration rule: work-branch only until the active BCP 0.4.7 field-acceptance campaign clears its merge fence.

## User problem

The ChatGPT client may remain on visible states such as “Traitement…”, an additional-verification screen, a connection error, or an interrupted response for minutes. The user must not have to poll ChatGPT, ask another conversation, send screenshots, copy tokens, or manually inspect GitHub to know whether externally observable work is advancing.

The product must therefore separate:

1. **what BCP can prove externally**;
2. **what the ChatGPT UI visibly reports** through a supported observer;
3. **what remains unknowable inside the model/platform**.

BCP never fabricates hidden reasoning progress.

## Target topology

```
ChatGPT / Model / GitHub / BuildHub / local jobs
                 |
                 v
         BCP MISSION_EVENT_LOG
                 |
          durable checkpoint
                 |
      +----------+-----------+
      |                      |
      v                      v
  PC-WORKER <--- LAN ---> B-EDGE (old Android)
                             |
                    tiny control traffic
                             |
                             v
                         Telegram
                             |
                             v
                           User
```

### PC-WORKER

The PC remains on home Wi-Fi by default and performs heavy work: repositories, builds, tests, Drive sync, durable state, receipts and local BCP execution.

The PC writes a compact event before and after every BCP-managed micro-action. Normal examples:
- `PLANNED`
- `STARTED`
- `DISPATCHED`
- `WAITING_PROVIDER`
- `RESULT_RECEIVED`
- `VALIDATING`
- `COMMITTED`
- `CHECKPOINTED`
- `BLOCKED`
- `DONE`

The user never needs to be the telemetry bridge.

### B-EDGE — old dedicated Android phone

B-EDGE is the preferred lightweight network relay/witness.

It keeps its authenticated local relationship with PC-WORKER over the home LAN. For Telegram egress it follows this order:

1. home-Wi-Fi Telegram path when functional;
2. if that specific Telegram path is unavailable and Android network binding is supported, bind **only the tiny Telegram control-plane sockets** to cellular;
3. keep bulk traffic, APK/ZIP downloads, builds and Drive synchronization off mobile data;
4. if neither transport works, queue compact events durably and resume later without duplicate delivery.

The whole PC must not be moved to mobile hotspot just to make Telegram work.

### Telegram

Telegram is the human cockpit, not canonical memory.

It is **push-first**:
- state changes are sent automatically;
- several fast micro-actions may be compacted into one low-data message;
- unchanged healthy state is silent;
- a sparse waiting heartbeat may be emitted after a long quiet interval;
- `/status`, `/where`, `/tail` and `/details` remain on-demand surfaces.

## What “progress” means

Progress is based only on finite externally verifiable work.

If a mission has 12 declared steps and 7 have durable completion receipts, the cockpit may display `7/12 = 58%`.

If the current action is an opaque ChatGPT/provider call, the percentage freezes at the last proven boundary and the state says, for example:

`WAITING_EXTERNAL_CHAT_RESULT — last proof: step 07 checkpointed`

A spinner, “Traitement…”, or elapsed time alone is not evidence that hidden reasoning is advancing.

## Visible ChatGPT observer

A future optional observer may record only **visible client states** from the user's own authorized device/browser, for example:

- `CHAT_REQUEST_SUBMITTED`
- `CHAT_UI_THINKING_VISIBLE`
- `CHAT_UI_VERIFICATION_VISIBLE`
- `CHAT_UI_RESPONSE_VISIBLE`
- `CHAT_UI_INTERRUPTED`
- `CHAT_UI_NETWORK_ERROR`

This observer must use accessibility/DOM/UI information that is actually exposed to the user. It must not attempt to recover private chain-of-thought or internal OpenAI verification state.

When no qualified observer exists on the device where ChatGPT is being used, the cockpit must say `UNKNOWN_INTERNAL_CHAT_STATE` while continuing to report GitHub/BuildHub/BCP/B-EDGE work normally.

## Proactive event delivery

The Telegram worker watches the append-only `MISSION_EVENT_LOG.jsonl`.

Rules:
- first start primes its cursor and does not replay an old backlog;
- each later durable transition is pushed automatically;
- cursor advancement is atomic;
- failed Telegram delivery does not advance the cursor, so reconnect can retry;
- if the journal window is compacted and the cursor disappears, re-prime without speculative replay;
- bursty transitions are compacted to a bounded message count;
- token/secret material is never included.

## Automatic-update target

Manual download/copy/replace of Telegram files is a temporary bootstrap condition, not the steady-state product.

### PC Telegram worker

Target flow:

`QUALIFIED CI -> release manifest -> SHA-256 verified staged package -> atomic replace -> restart -> health receipt -> rollback on failure`

Requirements:
- no administrator privilege for routine worker updates;
- token and local chat authorization survive upgrades and are never copied into release artifacts;
- update is idempotent;
- exact source/release SHA is retained in a machine-readable receipt;
- failed update restores the previous worker;
- no update is promoted from an unqualified branch;
- no paid service is introduced.

### B-EDGE

B-EDGE uses its Evergreen stable package/signing identity.

Android OS installation confirmation may still be required where Android requires it; the design must not pretend ordinary apps can silently bypass that gate. Everything before that confirmation — download, hash/signature verification, staging, state preservation and post-install recovery — should be automated.

## Platform-verification behavior

This architecture does **not** disable or bypass ChatGPT platform checks.

Its purpose is to make a platform hold non-destructive:

`request/checkpoint -> durable waiting state -> external safe jobs continue -> Telegram reports exact proof -> resume from checkpoint`

If a provider-neutral job can legally and safely continue through another qualified provider, Model Broker may do so under its existing policy. If not, it waits without replaying committed work.

## Immediate implementation sequence

1. Preserve the active BCP 0.4.7 field-acceptance campaign.
2. Qualify proactive Telegram event push and `/where`/`/tail` on a fenced work branch.
3. After the field-acceptance merge fence clears, reconcile and merge.
4. Move Telegram transport from PC-direct to B-EDGE selective relay.
5. Add managed worker self-update.
6. Add visible-client ChatGPT observer where technically supported.
7. Run Kinshasa low-bandwidth/mobile-data measurements and interruption tests.
8. Promote only after machine-readable field receipts.

## Acceptance

The feature is FIELD_VERIFIED only when:
- the user starts no manual status polling;
- a BCP-managed mission emits automatic Telegram transitions;
- a 5+ minute opaque provider/chat wait shows last proof + elapsed wait without fake progress;
- PC stays on home Wi-Fi;
- Telegram control traffic can use B-EDGE fallback without moving bulk PC traffic to mobile data;
- disconnect/reconnect does not duplicate events;
- a qualified worker update installs without token re-entry;
- spend remains exactly $0.00.
