# BCP Offline Mission Sentinel and Resume Architecture

Status: R16 IMPLEMENTATION CANDIDATE / FIELD UNVERIFIED
Date: 2026-09-20

## Goal

Keep API/BCP understandable and recoverable when:
- the user is away from the house;
- the Windows PC loses Internet or powers off;
- direct PC -> Telegram TCP/443 is unavailable;
- the interactive ChatGPT conversation stops producing durable external evidence;
- power/network returns later.

The system detects absence of observable progress, preserves the last durable checkpoint, produces a bounded resume intent, notifies the user through the best available control path, and resumes only through qualified workers.

## Truth model

BCP does **not** claim access to hidden ChatGPT model state and does **not** claim a normal ChatGPT conversation can autonomously press its own Continue button.

It observes durable evidence only:
- mission_events;
- mission last_progress_at;
- GitHub workflow/commit/receipt evidence;
- PC/B-EDGE/Nexus heartbeats;
- local jobs/outbox;
- explicit platform/human holds.

No new proof means **stalled observable progress**, not proof that a model is internally stuck.

## PC sentinel

BCP 0.7.0 runs a lightweight mission watchdog from the existing heartbeat loop.

For each nonterminal mission:
1. locate the latest non-watchdog evidence anchor;
2. compute age of that proof;
3. ignore terminal work;
4. suppress blind retries for explicit human gates;
5. after ~10 minutes without new proof, generate a durable resume request;
6. deduplicate by mission + evidence anchor + next step;
7. allow at most 3 automatic requests for the same unchanged proof anchor;
8. use increasing cooldowns of about 5, 15 and 60 minutes;
9. reset the retry epoch only when genuine non-watchdog evidence advances.

Watchdog-generated RETRY_SCHEDULED events are excluded from the evidence anchor so the watchdog cannot create fake progress by observing itself.

## Durable resume request

Files:
- state/mission_resume_request.json — latest durable intent;
- state/MISSION_RESUME_REQUESTS.jsonl — append-only local audit;
- state/mission_watchdog.json — current watchdog classification.

The request includes:
- deterministic request_id;
- mission_id and project_id;
- next step;
- worker class when known;
- source (automatic watchdog or Telegram user action);
- evidence anchor;
- timestamp;
- zero-paid-spend invariant.

BCP acknowledges/mirrors this request to the existing control/Drive plane when available.

Persistence or acknowledgement of a request is **not** completion evidence. A qualified worker or Model Broker must later produce its own result/receipt.

## Telegram V8

The cockpit adds:
- ▶️ Continuer — creates the same durable idempotent resume intent;
- automatic notification when a stalled mission caused an auto-resume request;
- automatic notification when the bounded retry budget is exhausted;
- automatic notification for a real human gate.

Notifications are deduplicated by state + mission + evidence anchor + attempt.

The manual Continue button is therefore a real control-plane mutation, not cosmetic text.

## Offline behavior

### PC alive, Internet degraded
- BCP local mission/watchdog state remains available;
- retries are local and bounded;
- Drive updates when Drive connectivity returns;
- direct Telegram can fail without destroying mission state;
- Nexus is preferred when its field gate is complete.

### PC offline
The PC sentinel cannot execute while the machine is off. Therefore the target architecture uses the old Android B-EDGE phone as the independent secondary sentinel.

B-EDGE must preserve enough compact replicated state to know:
- last committed project revision;
- active mission identifier;
- last proof timestamp;
- pending resume/outbox entries;
- PC heartbeat age;
- whether work is WAITING_FOR_PC vs remote-capable.

It must never fabricate PC work while the PC is absent.

### Both PC and phone disconnected
Both retain local durable queues. When either reconnects, it publishes receipts. Reconciliation is idempotent and fenced before effects are replayed.

## Secondary B-EDGE sentinel target

The dedicated old phone becomes the remote continuity anchor:
- WorkManager/Room-backed periodic reconciliation, not a permanent busy loop;
- tiny control-plane traffic only;
- Nexus/Telegram control if available;
- cellular use restricted to tiny control messages when policy permits;
- bulk builds/APKs/Drive transfers remain off metered mobile data;
- notification if PC has been unreachable beyond policy threshold;
- WAITING_FOR_PC queue for PC-only work;
- remote/free-provider semantic work only through Model Broker policy and zero-dollar gates.

This target is separate from the already implemented PC watchdog and remains FIELD_UNVERIFIED until Android code/tests/receipts prove it.

## Failure classes

- ACTIVE: recent non-watchdog proof.
- STALLED: evidence age crossed threshold.
- RESUME_REQUESTED: durable bounded resume intent created.
- NETWORK_WAIT: transport is unavailable; preserve queue.
- HUMAN_GATE: user authorization/login/approval required; no blind retries.
- ESCALATED: three automatic requests for the unchanged evidence anchor produced no new proof.
- DONE/CANCELLED: watchdog disabled for mission.

## Anti-loop / anti-spam

- stable deterministic request IDs;
- max three automatic resume requests per unchanged anchor;
- increasing cooldown;
- notification fingerprinting;
- one Telegram poller;
- new actual evidence resets the retry epoch;
- restart/reboot does not erase requests;
- no repeated paid/model calls solely because the watchdog ticks.

## Field acceptance gates

1. BCP 0.7.0 resident readback.
2. Telegram V8 resident readback.
3. Mission self-test confirms self-generated watchdog events do not advance evidence anchor.
4. A synthetic stale mission creates exactly one resume request in first cooldown.
5. Second tick within cooldown creates no duplicate.
6. Telegram receives one deduplicated stalled/resume notice.
7. ▶️ Continuer queues a request and duplicate taps deduplicate.
8. Offline -> reconnect preserves and mirrors the same request ID.
9. Explicit human gate suppresses auto-resume.
10. Reboot preserves watchdog/request state.
11. B-EDGE secondary sentinel implemented and field-qualified separately.

## Cost/resource contract

DEFAULT_PAID_SPEND = 0 USD.
No heavy local LLM.
No tight polling loop.
No duplicate Telegram receiver.
No assumption of continuous mains power or Internet.
