# BCP — Telegram Mission Cockpit and Observable Progress Journal

Status: CANONICAL DESIGN REQUIREMENT
Adopted: 2026-09-19

## Goal

BCP must let the user submit a mission from a lightweight Telegram bot, start it with a compact confirmation, follow durable progress, and recover the exact state even when a chat conversation is delayed or interrupted.

Telegram is a cockpit and ingress surface. BCP remains the canonical state authority.

## Target user flow

User -> Telegram bot -> BCP Mission Intake -> durable mission -> planner -> deterministic work / Model Broker / PC / B-EDGE / BuildHub / GitHub -> receipts/checkpoints -> Telegram status

The user should be able to:
- submit a normal-language mission;
- receive a compact interpretation;
- choose:
  - 1 = EXECUTE_DEEP;
  - 2 = PLAN_ONLY;
  - 3 = STATUS;
  - 4 = PAUSE;
  - 5 = CANCEL_SAFE;
- receive concise status and only necessary approval requests.

Routine healthy telemetry should stay quiet.

## Mission envelope

Before any long-running execution, BCP stores a durable MISSION_ENVELOPE containing:
- mission_id;
- project_id;
- user_request_digest;
- canonical specification revision;
- context revision;
- execution profile: FAST / NORMAL / DEEP / AUDIT;
- allowed capabilities;
- provider policy;
- zero-paid-spend invariant;
- approval gates;
- idempotency key;
- current step;
- last committed step;
- next valid step;
- evidence references.

The large prompt/context package is stored by BCP. The user must not manually carry it between services.

## Short synchronization code

After a mission is created, Telegram may return a short human-friendly job code such as:

48273195

Preferred explicit cross-client syntax:

BCPGO 48273195

The short code is a reference to the durable mission, not the mission content itself and not a replacement for normal account/device authorization.

A standard chat client can resolve the code only if a qualified BCP connector/bridge is available on that client. If not, Telegram/BCP remains the execution path and the code still identifies the mission for status/recovery.

## Long work must be decomposed

A deep mission must not depend on a single long opaque response.

BCP decomposes it into bounded micro-sprints:
1. resolve current context;
2. resolve known facts/errors/cache locally;
3. formulate the next subproblem;
4. call a model only when needed;
5. validate the returned result;
6. commit an allowed mutation;
7. write a checkpoint;
8. continue.

The total mission may run for a long time, but each durable progress boundary is small.

## Append-only mission event log

Every observable micro-action is recorded in MISSION_EVENT_LOG.

Required states:
- ACCEPTED;
- NORMALIZED;
- PLANNED;
- QUEUED;
- STARTED;
- DISPATCHED;
- WAITING_PROVIDER;
- RESULT_RECEIVED;
- VALIDATING;
- COMMITTED;
- CHECKPOINTED;
- RETRY_SCHEDULED;
- BLOCKED;
- HOLD;
- DONE;
- CANCELLED.

Each event should include:
- monotonic sequence number;
- job_id and step_id;
- timestamp;
- component/worker;
- concise action summary;
- provider/tool if used;
- input/output digest where useful;
- evidence/receipt reference;
- error class;
- next safe action.

While a provider call is still outstanding, an adaptive lightweight heartbeat records that the job is still waiting, the elapsed duration, the last durable checkpoint, and the next retry deadline when applicable.

## Reasoning records

BCP does not depend on private token-by-token reasoning from any model.

It persists instead:
- task decomposition;
- concise decision/rationale summaries;
- hypotheses being tested;
- evidence used;
- selected/rejected option summaries;
- tool/provider actions;
- receipts and checkpoints.

When more detail is needed, the worker produces an explicit structured decision record as normal output before the next mutation.

## Chat interruption behavior

If a ChatGPT conversation is delayed or interrupted, BCP does not invent progress.

For jobs already running through BCP or another external worker:
- they may continue normally;
- Telegram shows the current durable state.

For a task whose only active worker is the delayed chat:
- state becomes WAITING_EXTERNAL_CHAT_RESULT or PROVIDER_PENDING_UNKNOWN;
- Telegram shows the exact last confirmed checkpoint;
- another provider may continue only if the job is provider-neutral and replay-safe.

## Model/API use

Telegram itself should remain lightweight.

Normal route:
Telegram -> local rules/cache/error ledger -> Model Broker only if needed.

Status checks, hashes, retries, queue operations, build/test launches, known-error recipes and checkpointing are deterministic/local by default.

Complex reasoning uses one selected field-qualified free provider by default. Multi-model fan-out is exceptional and bounded.

## Progress UX

Example:

MISSION 48273195
Project: API/BCP
State: WAITING_PROVIDER
Spec rev: 184
Last committed: step 07 — CI patch persisted
Current: step 08 — model review outstanding
Last event: 10:42:18
Elapsed current step: 01:14
Next safe action: validate -> checkpoint
Spend: $0.00

Use stage/step state rather than fake percentages.

## Recovery

Supported recovery intents:
- BCPGO
- BCPGO <project>
- BCPGO <job_code>
- project aliases such as APIAX07 RESYNC

Recovery returns:
- exact specification revision;
- mission state;
- last committed action;
- current outstanding action;
- next safe action;
- evidence references.

Committed work is not replayed.

## Failure states

Required durable states:
- FREE_MODEL_CAPACITY_HOLD;
- PROVIDER_PENDING_UNKNOWN;
- PROVIDER_TIMEOUT;
- PLATFORM_VERIFICATION_HOLD;
- NETWORK_OFFLINE_QUEUEING;
- SPEC_CONFLICT_HOLD;
- HUMAN_APPROVAL_REQUIRED.

Every hold must be resumable.

## Acceptance

This feature is not FIELD_VERIFIED until:
1. a Telegram request becomes a durable MISSION_ENVELOPE;
2. action 1 starts a bounded DEEP job;
3. a job code resolves to the correct durable mission through a supported client;
4. every mutation creates event + receipt + checkpoint;
5. timeout leaves an exact resumable state;
6. chat interruption does not erase the mission;
7. a fresh client displays the exact last committed step;
8. replay/duplicate execution is rejected;
9. low-bandwidth status remains usable;
10. paid spend remains exactly zero;
11. a specification update preserves prior active requirements unless explicitly superseded.

## Implementation order

Do not interrupt the current BCP 0.4.7 field-acceptance campaign.

After that campaign:
1. activate cumulative specification merge policy in Context Fabric;
2. implement Mission Event Journal;
3. implement Telegram mission intake/status/approval surface;
4. connect the Model Broker to field-qualified free providers;
5. enable short-code handoff on clients that have a qualified BCP connector;
6. run interruption, timeout, replay and low-network acceptance.
