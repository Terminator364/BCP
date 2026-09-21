# BCP — Communication Survival & Cross-Conversation Recovery R71

Status: CANONICAL CANDIDATE  
Date: 2026-09-21  
Continuation code: `BCPGO BCP`

## 1. Purpose

BCP must continue to communicate and recover even when one or more of these fail at the same time: ChatGPT UI, home Wi-Fi, PC Internet, Telegram direct egress, Google Drive synchronization, PC reboot/logoff, or the active conversation itself.

The system therefore treats communication as a **multi-plane fabric**, not as one bot or one PC process.

## 2. Planes and authority

### Gmail — detailed human checkpoint
Gmail is the primary detailed human-facing checkpoint surface. Every interactive tranche sends START before substantive work and END after durable checkpointing. END is retried until the mail provider acknowledges the send. Only then may ChatGPT emit the short pointer.

### Telegram — witness / alert / navigation
Telegram is secondary. It must never be the only durable truth. Direct PC egress is preferred when healthy; if direct transport fails and a fresh B-EDGE relay registration exists, PC uses the dedicated phone as the CONNECT relay. A Telegram delivery claim requires a positive Bot API response.

### Dedicated phone — low-power local communications appliance
The old Android phone is a first-class node. It owns persistent local queue/memory/receipts, local API, boot restoration, local discovery and store-and-forward. If there is no uplink, it persists events rather than pretending delivery. When an uplink or PC returns, replay is idempotent.

### Drive — durable replicated evidence
Drive mirrors runtime evidence and current install artifacts. It is useful for cross-device recovery, but DriveFS/provider availability is not assumed. The deterministic runtime path is:
`API_BCP/02_TELEMETRY/BCP/BCP_RUNTIME_LATEST.json`.

### ChatGPT — interactive reasoning surface
ChatGPT is not canonical state. A new conversation must recover from durable project state with `BCPGO BCP`. The user must not reconstruct the project manually.

## 3. 30-minute tranche protocol

1. Resolve project context only as much as necessary.
2. Gmail START + provider ACK.
3. Arm one-shot END watchdog for minute 29.
4. Work until about minute 29.
5. Persist branch/state/checkpoint.
6. Gmail END + retry until provider ACK.
7. Disable watchdog if normal END succeeded.
8. ChatGPT emits only Gmail/date-time/checkpoint pointer.

A missing ChatGPT reply must never be required to trigger the END checkpoint.

## 4. Failure matrix

- ChatGPT UI stalls: no project state loss; watchdog sends END; next conversation uses `BCPGO BCP`.
- Gmail START fails: substantive tranche does not start.
- Gmail END fails: retry; no ChatGPT end output.
- Telegram direct timeout/DNS/TLS failure: classify and try fresh B-EDGE relay; otherwise persist outage.
- Phone has no uplink: store-and-forward; no fake delivery.
- PC disappears: phone remains local node; pending PC-required jobs become WAITING_FOR_PC.
- PC returns: reconcile queue, receipts and context by idempotency key.
- Drive unavailable: preserve local durable state; retry later with bounded backoff.
- Home Wi-Fi changes to hotspot or back: discovery/registration refresh; no fixed-IP assumption.
- Conversation changes: `BCPGO BCP` loads policies, writer fence, current state and next action.

## 5. Anti-false-success rules

A generated message is not a delivered message. A local queue receipt is not a Telegram receipt. A Drive mirror is not proof the user saw the message. A ChatGPT response object is not proof the app rendered it. Each layer stores the strongest evidence it actually has.

## 6. New-conversation recovery runbook

In a fresh supported conversation type only:

`BCPGO BCP`

BCP must then:
- load the communication/delivery/cadence policies first;
- send Gmail START before substantive work;
- load writer-fence policy and current main SHA;
- load project_state and API_PROJECT_CONTINUITY;
- recover exact active candidate/field gate;
- avoid replaying committed work;
- perform the next uncommitted action;
- end by Gmail END ACK then ChatGPT pointer.

No manual recap from the user is part of the normal recovery path.

## 7. Phone-first direction

The phone is the persistent, low-power edge appliance. The PC is retained for Windows-only operations and heavier compute, but it is no longer the sole communications center. B-EDGE full-node work must keep moving toward local authenticated API, durable queue/memory, bounded content cache, local discovery, adaptive transport and independent store-and-forward behavior.

## 8. Acceptance gates

Communication survival is considered qualified only when representative tests cover:
- Gmail START/END contract and END retry semantics;
- stale conversation -> BCPGO cold recovery;
- Telegram direct failure -> phone relay fallback;
- phone no-uplink -> durable queue -> replay;
- PC offline -> phone stays active;
- PC return -> idempotent reconciliation;
- Wi-Fi/hotspot change -> rediscovery/re-registration;
- duplicate delivery -> deduplication;
- crash/reboot during pending messages -> queue survives;
- no channel may promote weaker evidence to stronger delivery truth.
