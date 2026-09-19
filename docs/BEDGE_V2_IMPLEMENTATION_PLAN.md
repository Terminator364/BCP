# B-EDGE V2 — Incremental Implementation Plan

Status: IMPLEMENTATION ROADMAP
Adopted: 2026-09-19
Constraint: do not destabilize the current field-proven P0 release train

## Principle

B-EDGE V2 is built by strangler-style migration: add verified subsystems beside the existing Evergreen P0 path, migrate one authority/data responsibility at a time, then remove legacy behavior only after readback proves replacement equivalence.

No big-bang rewrite.

## Phase 0 — Freeze invariants and baseline

Deliver:
- canonical requirements R4;
- runtime hardening architecture;
- failure-injection matrix;
- machine-readable B-EDGE V2 policy;
- exact inventory of current prototype limitations.

Gate:
- current P0 Windows/B-EDGE behavior remains working;
- no release artifact is promoted solely because docs changed.

## Phase 1 — Durable local state foundation

Dependencies targeted for the current Java/Groovy Android app after implementation qualification:
- Room stable line compatible with Java annotation processing;
- WorkManager stable line;
- optional DataStore only for small settings when migration value justifies it.

Initial recommendation at 2026-09-19:
- Room 2.8.5 for Java-friendly annotationProcessor path;
- WorkManager 2.11.2;
- DataStore 1.2.1 only if/when small preferences are migrated.

Deliver:
- `BcpDatabase`;
- versioned schema;
- projects/jobs/dependencies/receipts/outbox/node/provider/error/memory tables;
- migration tests;
- import adapter from current SharedPreferences/cache state;
- no behavior switch yet.

Gate:
- existing pairing/session survives upgrade;
- schema create/migration tests PASS;
- process-kill DB atomicity tests PASS.

## Phase 2 — Multi-project registry

Remove the architectural hard-code of `PROJECT = buildhub`.

Deliver:
- durable project registry;
- active/default project concept only as UI convenience;
- per-project heads/checkpoints;
- project isolation tests;
- backward compatibility mapping existing `buildhub` state into registry.

Gate:
- existing BuildHub path still works;
- at least three synthetic projects can queue/resume independently.

## Phase 3 — Durable job/outbox engine

Move pending checkpoint and queued action semantics from single SharedPreferences slots to Room.

Deliver:
- durable mission/job/action records;
- idempotency ledger;
- job dependency DAG;
- READY/BLOCKED/HOLD/DONE transitions;
- prioritized outbox;
- critical-event retention classes.

Gate:
- duplicate enqueue/receipt tests PASS;
- process kill at each transition PASS;
- offline replay PASS.

## Phase 4 — WorkManager recovery runtime

Deliver:
- unique reconciliation work;
- network-constrained outbox flush;
- device-reboot reconciliation;
- provider-reset/retry scheduling;
- no permanent foreground-service requirement.

Gate:
- kill app -> restart/recover;
- reboot -> recover;
- duplicate WorkManager execution -> zero duplicate committed effect.

## Phase 5 — Resource governor

Deliver:
- EDGE_R0/R1/R2/PC_R3/REMOTE_AI classification;
- battery/charging/power-save/network gates;
- memory-pressure cache eviction;
- thermal throttling;
- PC RAM/availability dispatch gate.

Gate:
- pressure tests show bounded RAM/CPU/wakeups;
- background work backs off before thermal/low-battery damage;
- critical lightweight control remains responsive.

## Phase 6 — Structured project memory + retrieval

Deliver:
- memory scopes and evidence classes;
- Room FTS index;
- pinned policy/decision handling;
- candidate-memory admission;
- supersede/conflict/freshness logic;
- Context Pack generator with deterministic hash.

Gate:
- task-specific retrieval precision test set;
- no cross-project leakage;
- model-proposed facts cannot silently overwrite USER_DECLARED/MACHINE_VERIFIED facts;
- Context Pack p95 remains bounded.

## Phase 7 — Deterministic scheduler + agent contract

Deliver:
- priority + fairness/aging;
- immutable job envelope;
- agent/tool permission profile;
- bounded iteration/retry/no-new-evidence breaker;
- structured result validator;
- artifact/receipt handoff.

Gate:
- simulated multiple-agent chantier runs without agent-to-agent free-form loops;
- model outage leaves deterministic work running;
- one background project cannot starve interactive work.

## Phase 8 — PC fenced-worker protocol

Deliver:
- coordinator epoch/fencing token;
- expected revision/input hash in work envelope;
- stale-fence rejection;
- local PC receipt cache during partition;
- idempotent reconciliation.

Gate:
- network partition test produces one canonical head;
- stale delayed command rejected;
- B-EDGE loss after dispatch does not lose PC result.

## Phase 9 — Discovery and authenticated LAN transport

Deliver:
- NSD/mDNS primary discovery;
- QR fallback;
- bounded diagnostic scan only;
- persistent PC cryptographic identity;
- TLS authenticated channel and pinning/trust continuity;
- credential rotation.

Gate:
- packet capture contains no bearer/provider secret in plaintext;
- DHCP change reconnects;
- malicious/incorrect discovery responder cannot silently hijack pairing;
- Android 17 local-network permission/picker test plan passes before targetSdk 37.

## Phase 10 — Replication and recovery

Deliver:
- PC near-line state replica;
- consistent logical/DB snapshot;
- snapshot hash/readback;
- encrypted cold backup;
- recovery key wrapped separately for Android and Windows;
- phone-loss replacement procedure;
- coordinator epoch rotation.

Gate:
- destructive simulated phone loss restores latest verified state;
- corrupt newest snapshot rejected;
- old phone is fenced after replacement coordinator promotion.

## Phase 11 — Free model broker execution

Deliver:
- real provider field qualification;
- quota vector;
- expected-call-cost model;
- safe burn rate;
- 50/25/25 bootstrap reserve;
- conservation mode;
- provider adapters one at a time.

Gate:
- ZERO_USD invariant;
- provider 429/exhaustion fails closed;
- full day simulation preserves emergency reserve;
- no multi-model fan-out by default.

## Phase 12 — Telegram cockpit

Deliver:
- Telegram update-id dedup;
- command -> durable mission conversion;
- compact status/approval/result messages;
- no heartbeat spam.

Optional after separate field gates:
- Cloudflare zero-cost webhook ingress;
- FCM wake hints.

Gate:
- duplicate update creates one mission;
- offline node yields honest QUEUED state;
- cloud/push outage does not disable BCP.

## Phase 13 — V2 authority promotion

Only after all prior gates:
- migrate default canonical orchestration writer from PC P0 to B-EDGE V2;
- PC switches to fenced-worker mode;
- preserve rollback procedure;
- publish authority-migration receipt.

Gate:
- reboot/process kill/partition/device loss/poor connectivity/resource pressure campaign PASS;
- no split-brain;
- no lost committed revision;
- no secret exposure;
- SPEND_USD = 0.00.

## Implementation rule for every phase

Each phase must ship:
1. schema/protocol version;
2. migration/rollback;
3. static/unit/integration tests;
4. failure-injection test where relevant;
5. telemetry/readback;
6. no manual screenshot requirement for machine-observable results;
7. proof of compatibility with the previous qualified phase.
