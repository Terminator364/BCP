# BCP 0.5 / B-EDGE 1.1 — Counter-Audit Against V2 Target

Status: COUNTER-AUDIT / ACTIONABLE
Date: 2026-09-19
Compared against:
- docs/BEDGE_RUNTIME_V2_HARDENING.md
- docs/BEDGE_V2_TEST_MATRIX.md
- docs/CANONICAL_PRODUCT_REQUIREMENTS.md R4

## Overall assessment

BCP 0.5 / B-EDGE 1.1 is a useful transitional implementation that proves:
- memory layers can be externalized from chat;
- deterministic operating modes can exist;
- jobs can be queued with idempotency identity;
- a Context Pack can be exposed;
- B-EDGE can preserve an offline queue and context cache;
- PC memory pressure can influence scheduling.

It is NOT yet the durable B-EDGE V2 runtime.

Promotion state:
`DESIGN_DIRECTION_PASS / TRANSITIONAL_IMPLEMENTATION / V2_RUNTIME_UNVERIFIED`

## Findings

### F01 — Android orchestration state is still SharedPreferences
Severity: HIGH
Observed:
- EdgeOrchestrator stores mode, Context Pack, full memory JSON and job queue JSON in SharedPreferences.

Risks:
- poor fit for growing structured multi-project state;
- no relational constraints/DAG transactions;
- large JSON rewrites;
- weak crash-atomic semantics for multi-record transitions;
- difficult migrations/search/indexing.

Required:
- migrate canonical local state to Room/SQLite;
- keep SharedPreferences/DataStore only for small non-canonical settings.

### F02 — Project remains hard-coded to buildhub
Severity: HIGH
Observed:
- BcpClient PROJECT constant remains `buildhub`.

Risk:
- architecture cannot yet be the memory/orchestrator for all projects.

Required:
- durable project registry;
- project-scoped queues/memory/context;
- explicit active/default project only as UI convenience.

### F03 — Queue overflow discards oldest entry blindly
Severity: CRITICAL FOR V2
Observed:
- EdgeOrchestrator trims the first item when queue length exceeds the fixed bound.

Risk:
- a critical/interactive or unreconciled job can be silently lost.

Required:
- no silent drop of canonical/pending actions;
- priority-aware admission;
- backpressure/HOLD when durable capacity is exhausted;
- discard only explicitly disposable telemetry/cache classes.

### F04 — Memory compaction is not age/evidence aware
Severity: HIGH
Observed:
- compaction removes HISTORY keys based on JSONObject name iteration, not oldest timestamp/evidence class.

Risk:
- important audit history may be removed while newer noise survives.

Required:
- database retention policy with timestamps, type and evidence class;
- canonical receipts/fencing/security history never evicted by ordinary cache pressure.

### F05 — Async apply() is used for job/memory persistence
Severity: HIGH
Observed:
- SharedPreferences.Editor.apply() is used on orchestration state.

Risk:
- there is a persistence window between logical acceptance and disk durability, especially under abrupt process death/power loss.

Required:
- transactional Room commit for canonical queue/state;
- report DONE/QUEUED only after durable transaction.

### F06 — Context Pack cache is a monolithic JSON blob
Severity: MEDIUM/HIGH
Observed:
- entire server Context Pack is cached in SharedPreferences.

Risks:
- size growth;
- repeated serialization;
- stale context without explicit source-revision invalidation;
- no scoped retrieval.

Required:
- Context Pack generated from durable structured memory;
- revision vector/hash;
- bounded size;
- FTS/task relevance;
- cache entry disposable/rebuildable.

### F07 — heartbeat() performs orchestration synchronization
Severity: HIGH FOR 24H ENDURANCE
Observed:
- BcpClient.heartbeat() calls syncOrchestrationState();
- sync performs status GET + Context Pack GET + queued-job flush.

Risk:
- a future frequent heartbeat becomes a network/CPU/battery amplification loop;
- repeated Context Pack downloads even without state change;
- unnecessary PC wake/network pressure.

Required:
- decouple liveness heartbeat from orchestration reconciliation;
- event-driven/debounced sync;
- WorkManager for deferred reconciliation;
- revision/ETag-like change test before fetching full context.

### F08 — Successful immediate job submission is replayed unnecessarily
Severity: MEDIUM
Observed:
- queueJob persists locally, POSTs the same job, then calls flushQueuedJobs while the just-accepted local entry is still in the queue.

Effect:
- stable idempotency prevents duplicate canonical effect, which is good;
- but an avoidable second network request occurs.

Required:
- acknowledge/remove the locally queued record after remote receipt before bulk flush;
- preserve it only if receipt is uncertain.

### F09 — Android queue has no dependency DAG
Severity: HIGH
Observed:
- local queue is a flat JSON array.

Required:
- job_dependencies table;
- READY/BLOCKED transitions;
- bounded dependency traversal;
- no model required for deterministic transitions.

### F10 — Android resource governor is still minimal
Severity: MEDIUM/HIGH
Observed:
- EdgePolicy has simple PC reachability/memory-pressure state and fixed queue/memory limits.

Missing:
- Android thermal status;
- battery/charging/power-save state;
- network metering;
- memory pressure callbacks;
- EDGE_R0/R1/R2 classes;
- hysteresis/debounce.

Required:
- implement resource governor before allowing long unattended chantier execution.

### F11 — PC memory-pressure threshold has no hysteresis
Severity: MEDIUM
Observed:
- PC_MEMORY_PRESSURE switches at 85% used memory.

Risk:
- oscillation near threshold;
- percentage alone is misleading on a ~4 GB machine;
- available absolute bytes also matter.

Required:
- enter/exit hysteresis;
- absolute available-RAM floor;
- CPU/load and current heavy-job state;
- cooldown before redispatch.

### F12 — Server memory write accepts direct upsert
Severity: HIGH
Observed:
- memory_put(project, layer, key, value, source) directly replaces a key.

Missing:
- evidence class;
- source/provenance ID;
- pinned/user-declared protection;
- conflict/supersedes semantics;
- freshness/TTL;
- candidate admission.

Required:
- memory candidates -> admission validator -> canonical commit.

### F13 — Context Pack is recent-data based, not task-relevance based
Severity: HIGH FOR TOKEN ECONOMY
Observed:
- build_context_pack returns up to 12 recent memory entries from every layer plus recent events.

Risk:
- irrelevant tokens;
- important older pinned rule can be missed;
- cross-project/global policy selection is primitive.

Required:
- pinned invariants first;
- task/project exact retrieval;
- FTS relevance;
- token/byte budget;
- source revision/hash.

### F14 — PC job records are not yet full execution contracts
Severity: HIGH
Observed:
- jobs table has project, kind, payload, state, requires_pc, idempotency key and timestamps.

Missing:
- action identity;
- dependency edges;
- priority;
- resource class;
- expected revision/input hash;
- coordinator epoch/fence;
- evidence contract;
- attempt/lease data.

Required:
- immutable execution envelope before PC becomes a V2 fenced worker.

### F15 — Current transport remains POC cleartext LAN
Severity: HIGH BEFORE V2 AUTHORITY
Observed:
- BcpClient uses http:// endpoints and manifest allows cleartext.

Mitigation:
- current local P0 pairing/credential flow exists and is field-oriented.

Required before V2 authority:
- persistent PC cryptographic identity;
- authenticated TLS;
- pin/trust continuity;
- credential rotation;
- packet-level test proving no bearer/provider secret in cleartext.

### F16 — Subnet scan remains normal fallback implementation
Severity: MEDIUM
Observed:
- /24 discovery can fan out across up to 254 addresses with a 32-thread executor.

Risk:
- avoidable CPU/network/battery activity;
- fragile on non-/24 networks;
- Android future local-network permission changes.

Required:
- NSD/mDNS primary;
- QR/system-mediated fallback;
- subnet scan diagnostic-only, bounded.

### F17 — No Android process-death recovery worker yet
Severity: CRITICAL FOR V2
Observed:
- no Room/WorkManager foundation in current B-EDGE runtime.

Required:
- unique WorkManager reconciliation;
- phone reboot/process kill tests;
- canonical state reconstructable without process residency.

### F18 — Authority migration is not implemented yet
Severity: EXPECTED / BLOCKER FOR V2 PROMOTION
Observed:
- current PC SQLite remains canonical writer.

This is correct for P0 compatibility.

Required:
- only after fencing/replication/recovery tests, explicitly migrate authority to B-EDGE V2;
- no premature dual writer.

## Positive findings

- Android credential token uses Android Keystore AES-GCM.
- PC event commits already use revision/idempotency protections.
- SQLite WAL + synchronous FULL is a strong base on PC.
- local job POST idempotency remains stable across immediate replay.
- telemetry/outbox operations are bounded rather than infinite.
- PC Sanity and Windows sandbox E2E tests pass during the 0.5 transition.
- coordinated server/edge release metadata is being introduced.

## Immediate priority order

1. Restore all CI contracts for 0.5 / 1.1.
2. Do not promote 1.1 SharedPreferences orchestration as V2 durability.
3. Room schema + migrations.
4. WorkManager reconciliation.
5. remove hard-coded buildhub.
6. queue backpressure/priority; no silent drop.
7. memory admission/evidence model.
8. task-specific Context Pack.
9. resource governor/hysteresis.
10. NSD + authenticated TLS.
11. fencing/replication.
12. Telegram/free-model automation.
13. explicit V2 authority promotion.

## Counter-audit conclusion

The parallel 0.5/1.1 work is valuable because it moves the product from pure architecture toward executable orchestration.

The main danger would be mistaking the transitional prototype for the final edge runtime.

The correct strategy is to preserve its field-compatible behavior while replacing its fragile state mechanisms phase by phase under the V2 test matrix.
