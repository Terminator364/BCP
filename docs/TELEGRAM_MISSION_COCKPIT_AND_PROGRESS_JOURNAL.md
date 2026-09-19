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


## Progress Presence Layer — proactive certainty during opaque chat/UI delays

The user must never need to infer whether work is progressing from a spinning ChatGPT UI.

BCP therefore exposes a **Progress Presence Layer** over durable external evidence.

### Required behavior

For every BCP-managed mission:
- emit a durable event before and after each externally observable micro-action;
- maintain `last_event_at`, `last_checkpoint_at`, `current_component`, `current_step`, `next_safe_action`;
- expose whether a worker/job is RUNNING, WAITING, BLOCKED, OFFLINE, DONE or UNKNOWN;
- push Telegram updates on state transitions;
- while waiting, send sparse adaptive heartbeats only when useful, never aggressive polling;
- if no new externally observable evidence exists, explicitly report `NO_NEW_EXTERNAL_EVIDENCE` instead of pretending that reasoning is still progressing.

### Telegram UX

Add commands:
- `/watch <job>` — subscribe to state transitions for one mission;
- `/unwatch <job>` — stop push updates;
- `/tail <job>` — last durable events;
- `/where <job>` — current component, step, elapsed time, last proof and next safe action.

Example:

```
MISSION 48273195
State: WAITING_CI
Current: GitHub Actions / qualification
Last proof: PR #31 opened 13:24:21
Last event: CI_STARTED 13:24:31
Elapsed: 01:14
Next safe action: merge only if all gates PASS
Spend: $0.00
```

### ChatGPT-specific truthfulness

BCP MUST distinguish:
- `OBSERVED_CHAT_ACTION`: an externally evidenced ChatGPT-triggered action exists;
- `CHAT_WAITING`: a request was dispatched and no completion evidence exists yet;
- `CHAT_PLATFORM_HOLD_REPORTED`: a platform verification hold was explicitly reported/observed through a supported signal;
- `UNKNOWN_INTERNAL_CHAT_STATE`: the standard ChatGPT UI exposes no supported progress telemetry;
- `NO_NEW_EXTERNAL_EVIDENCE`: no GitHub/Drive/worker/receipt event has appeared since the last durable checkpoint.

BCP MUST NOT infer hidden chain-of-thought or claim that ChatGPT is still reasoning merely because the UI spinner is visible.

### Watchdog behavior

If no durable event is observed for a bounded interval:
- do not mark failure immediately;
- show elapsed time since the last proof;
- verify external jobs (GitHub/BuildHub/B-EDGE/worker heartbeat) where supported;
- if all external workers are idle and the only outstanding dependency is chat/provider output, mark `WAITING_EXTERNAL_CHAT_RESULT` or `PROVIDER_PENDING_UNKNOWN`;
- if the mission is provider-neutral and replay-safe, a qualified alternate provider may continue only under Model Broker policy;
- committed work is never replayed.

### Low-data requirement

Progress Presence is RDC/data-saver aware:
- transition-driven push by default;
- compact text payloads;
- adaptive heartbeats measured in minutes, not seconds;
- no repeated full status payload when unchanged;
- no mobile-data fallback for large artifacts.


## 2026-09-19 implementation refinement — push-first presence

The user must not need to type `/status` repeatedly.

The read-only worker implementation candidate now treats `MISSION_EVENT_LOG.jsonl` as a push source:
- cursor is durable and atomic;
- first start primes without replaying old backlog;
- later verifiable state transitions are pushed automatically;
- rapid transitions are compacted;
- delivery failure leaves the cursor unadvanced so reconnect can retry;
- `/where [job]` exposes the latest durable mission state;
- `/tail [job]` exposes recent durable micro-actions.

This still does not make ordinary ChatGPT UI internals observable. A visible-client observer is a separate capability and may report only UI states actually exposed on an authorized device.

The transport target and automatic-update contract are defined in:
`docs/TELEGRAM_PROGRESS_RELAY_AND_UPDATE_ARCHITECTURE.md`.


## Silent-execution watchdog

A user-visible spinner or a long tool/model call is not proof of progress.

For every BCP-managed long operation, the coordinator MUST commit a durable pre-dispatch event before starting the potentially slow action. That event records:
- mission/job/step identifier;
- external component or provider;
- dispatch timestamp;
- last committed checkpoint;
- replay/idempotency key where applicable;
- expected observation channel;
- next safe action if no result arrives.

If no new durable evidence is observed for 60 seconds, the cockpit MUST classify the interval as `NO_NEW_EXTERNAL_EVIDENCE` or `WAITING_EXTERNAL_ACTION`; it MUST NOT claim that the hidden model/tool is still reasoning.

After 3 minutes without new external evidence, the watchdog SHOULD:
1. re-read supported external evidence sources (GitHub job state, BCP/B-EDGE heartbeat, Drive receipt, BuildHub receipt);
2. keep already-dispatched work alive when independently running;
3. avoid replaying a mutation whose commit status is unknown;
4. surface the last durable checkpoint and exact resumable next action;
5. permit another conversation/provider to take over only when fencing, idempotency and replay-safety allow it.

A ChatGPT/browser interruption therefore becomes a presentation/worker-availability problem, not loss of project state. The user must not have to send screenshots simply to prove whether a GitHub/Drive/BCP action completed.


## P0 mission autonomy binding

The cockpit MUST project durable mission state, not model internals.

Human-first command contract:
- `/status`: compact project/mission state and only a finite verified-step progress bar when a finite plan exists;
- `/details`: technical evidence, receipts, worker/component and hold classification;
- `/where`: current_step, last_committed_step, next_step, last_progress_at, worker/component, receipt/evidence and failure/hold reason;
- `/tail`: recent append-only observable mission events.

Spontaneous messages are transition-driven and sparse: meaningful checkpoint, blocking condition, required human decision, or completion. Routine unchanged heartbeats do not generate chat spam.

No output may expose or claim to expose private chain-of-thought. If no new durable proof exists, report an evidence-based WAITING/STALLED/PROVIDER_WAIT/PLATFORM_HOLD/NETWORK_WAIT or NO_NEW_EXTERNAL_EVIDENCE state rather than inferred hidden progress.


## Cockpit human-first V2

La vue normale Telegram est destinée à l’utilisateur, pas au débogage Git. Les numéros de PR, SHA, branches, IDs de runs et détails de transport restent disponibles dans `/details`, mais ne doivent pas encombrer le suivi courant.

Le suivi normal doit afficher, quand les preuves existent :
- la micro-action observable actuelle ou la dernière micro-action durable ;
- une barre et un pourcentage uniquement si un vrai `step_index/step_total` borné existe ;
- l’âge de la dernière preuve durable ;
- un état d’activité honnête : récent, attente externe, silence à surveiller, ou absence de preuve ;
- PC/BCP, ancien téléphone B-EDGE, Drive, Nexus et qualification avec une iconographie simple ;
- la prochaine action en français simple.

Une absence de nouvelle preuve ne signifie pas automatiquement que ChatGPT est bloqué. Le cockpit doit dire qu’aucune nouvelle preuve durable n’a été observée, puis distinguer cette situation d’un vrai état BLOCKED/HOLD enregistré.

Les notifications automatiques sont transitionnelles : elles réagissent à un changement humainement utile de mission, d’étape, de liaison, de résultat de test ou de bande d’activité. Un nouveau commit ou run CI qui ne change pas la situation utile ne doit pas produire un doublon.

## Human Cockpit V3 binding — 2026-09-19

The human-facing mission cockpit now follows `docs/TELEGRAM_HUMAN_COCKPIT_V3_AND_MULTI_MISSION_REQUIREMENTS.md`.

Binding refinements:
- one editable live mission card replaces repeated near-duplicate status pushes;
- normal messages are medium-length, plain-language and explicitly show current step, last success, next step, human action, proof-of-life time/age and delivery lag;
- truthful progress bars/percentages are permitted only for persisted finite plans with a machine-derived denominator;
- raw PR/SHA/run/fence identifiers move behind `/details`;
- zero-dollar spend is not repeated in the normal view;
- one bot multiplexes multiple missions/projects/conversation sources by default rather than creating one bot per conversation;
- resident progress presence is driven by BCP events/heartbeats and MUST NOT depend on an active ChatGPT turn;
- resident timers are local BCP behavior, not ChatGPT scheduled automations;
- optional lightweight images/cards are data-saver aware and not sent on every heartbeat.


## Human Cockpit V4 binding — 2026-09-19

The human-facing cockpit is further refined by `docs/TELEGRAM_HUMAN_COCKPIT_V4_INTERACTIVE_EXPORTS.md`.

Binding:
- the live mission card exposes stable inline controls for refresh, exact position, missions and technical details;
- `/report` and `/reporttech` plus matching buttons provide compact human and technical PDF snapshots;
- callback taps are acknowledged immediately before slower refresh/export work;
- PDF/report state is presentation-only and never canonical authority;
- Nexus may cache sanitized report text so exports remain available during degraded direct PC->Telegram egress;
- all controls remain read-only in this increment;
- optional image-card UX remains separately gated;
- no ChatGPT scheduled automation is created or required.
