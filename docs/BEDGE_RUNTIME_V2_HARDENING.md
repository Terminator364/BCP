# B-EDGE Runtime V2 — Hardening Architecture

Status: TARGET ARCHITECTURE / NOT YET FIELD-VERIFIED
Adopted: 2026-09-19
Scope: dedicated old Android phone as BCP edge-memory/orchestration node

## 1. Design thesis

B-EDGE is a dedicated, recoverable edge coordinator. It is NOT assumed to be an immortal Android process.

The architecture optimizes for:
- durable continuity across Android process death, reboot, PC outage, Internet outage and power loss;
- maximum deterministic/local work before any LLM call;
- strict zero-dollar operation by default;
- low CPU/thermal/battery cost while exploiting otherwise-unused phone RAM for hot state/cache;
- auditable multi-agent execution with no uncontrolled agent-to-agent loops;
- safe coexistence with the low-RAM Windows PC.

Core rule:

`RAM is cache; durable state is authority.`

If Android kills the app process, all essential work must be reconstructable from durable state.

## 2. Runtime layers

### Layer A — Durable State Fabric

Target storage: Room/SQLite transactional database.

SharedPreferences/DataStore may hold only small configuration flags and non-canonical preferences. Complex project/job/memory state MUST NOT depend on SharedPreferences.

Minimum logical tables:
- `projects` — project registry, status, head revision, coordinator epoch;
- `memory_items` — scoped user/project/technical/policy memories with provenance and freshness;
- `jobs` — durable mission/job state, priority, resource class, idempotency key;
- `job_dependencies` — DAG edges and READY/BLOCKED dependencies;
- `action_receipts` — execution receipts, output hashes, readback/evidence;
- `outbox` — durable outbound events/commands;
- `provider_state` — free-provider health/quota/reset telemetry;
- `node_state` — PC/B-EDGE capability and health snapshots;
- `error_ledger` — normalized causal errors and validated recipes;
- `context_pack_cache` — generated context packs keyed by source revisions;
- `leases_fencing` — coordinator epoch/lease metadata where applicable.

Use database transactions for state transitions that must commit atomically.

Secrets/API keys/bearer credentials MUST remain outside the ordinary project-memory tables and use Android Keystore-protected storage.

### Layer B — Event Engine

Wake on meaningful triggers rather than busy-loop polling:
- app/user action;
- network change callback;
- WorkManager execution;
- FCM/push trigger if that optional path is field-qualified;
- PC discovery/reconnect event;
- queued job becoming runnable;
- provider reset/recovery;
- bounded maintenance window.

Periodic WorkManager is a fallback health/reconciliation mechanism, not a sub-minute heartbeat engine.

### Layer C — Deterministic Scheduler

The scheduler is ordinary code, not an LLM.

It owns:
- job DAG transitions;
- READY/BLOCKED/RUNNING/HOLD/DONE states;
- priority and fairness;
- resource admission;
- provider-call admission;
- checkpoint/retry timing;
- PC dispatch;
- preemption at safe checkpoint boundaries.

Normal dependency transitions such as `A DONE -> B READY` never consume model quota.

### Layer D — Context/Memory Resolver

Build minimal task-specific Context Packs from structured memory.

Retrieval order:
1. pinned policies/invariants;
2. exact project/current-state records;
3. known error signatures/validated recipes;
4. lexical/full-text local search;
5. recent relevant receipts/history;
6. optional semantic/model-assisted reasoning only if deterministic retrieval is insufficient.

Initial implementation SHOULD prefer Room + FTS for simplicity and low overhead. AppSearch is an optional later optimization if scale/latency measurements justify a second index.

### Layer E — Model/Tool Broker

Models are replaceable workers, never canonical memory.

The broker selects one provider by default and uses measured:
- remaining free capacity;
- latency/reliability;
- task fit;
- context needs;
- recent 429/failure state;
- privacy policy;
- expected quota cost.

Multi-model cross-check is exceptional and bounded.

## 3. Android lifecycle policy

### Always recoverable, not always resident

B-EDGE MUST assume Android may terminate its process.

Therefore:
- no correctness invariant may depend only on in-memory objects;
- each externally visible transition is persisted before/with execution;
- on process restart, scheduler state is rebuilt from the database;
- unfinished work is reconciled through receipts/idempotency keys;
- duplicate WorkManager delivery is harmless.

### WorkManager

Use WorkManager for persistent deferrable work:
- state reconciliation;
- outbox flush;
- telemetry compaction/upload;
- provider reset recheck;
- queued work whose constraints become valid;
- periodic maintenance.

Use unique work names derived from stable job/mission identifiers so duplicate enqueues collapse predictably.

Periodic work is inexact and has a minimum interval; it is not a real-time orchestration clock.

### Foreground services

A permanent foreground data-sync service is NOT the baseline architecture.

Foreground service use is reserved for bounded user-visible work where Android policy genuinely requires/permits it. Android 15 dataSync foreground-service duration limits make a permanent sync daemon unsuitable.

### Boot

After device reboot, schedule reconciliation rather than assuming a permanent process can restart unrestricted background services.

## 4. Resource governor

Every runnable job has a resource class:

- `EDGE_R0`: tiny deterministic state/rule operation; normally allowed.
- `EDGE_R1`: light DB/network/context work; allowed when basic resource gates pass.
- `EDGE_R2`: heavier indexing/compaction/bulk sync; prefer charging, healthy thermal state and adequate RAM.
- `PC_R3`: build/test/heavy file/CPU work; dispatch to PC only.
- `REMOTE_AI`: semantic reasoning; subject to provider quota/privacy/admission gates.

Admission inputs:
- Android thermal status;
- power-save/low-power state;
- charging/battery state;
- memory pressure callbacks and current memory snapshot;
- network availability/metering;
- PC online/resource state;
- global project priority;
- AI capacity/reserve state.

On Android memory pressure:
`HOT cache -> WARM cache -> durable COLD storage`.

The system MUST release rebuildable caches before durable state.

## 5. Multi-project memory model

Memory scopes:
- `USER_MEMORY` — stable user preferences/cross-project defaults;
- `PROJECT_MEMORY` — project-specific decisions, constraints, objectives;
- `TECHNICAL_KNOWLEDGE` — ERROR_LEDGER, reusable recipes, regression lessons;
- `OPERATING_STATE` — current jobs/nodes/providers/resources;
- `HISTORY` — receipts/events/audit trail;
- `POLICY` — permissions, budgets, security invariants.

Each durable memory item SHOULD carry:
- stable ID;
- scope/project;
- type/key;
- content or structured payload;
- provenance/source;
- evidence class;
- importance/pinned flag;
- created/updated timestamps;
- freshness/expiry semantics where applicable;
- supersedes/conflicts relation when relevant.

Suggested evidence classes:
- `USER_DECLARED`;
- `MACHINE_VERIFIED`;
- `SOURCE_VERIFIED`;
- `MODEL_PROPOSED`;
- `STALE`;
- `CONTRADICTED`.

A model MUST NOT directly promote `MODEL_PROPOSED` content to canonical fact.

## 6. Memory-write admission and anti-drift

Agents/models propose memory candidates. BCP validates before commit:
1. scope is correct;
2. provenance exists;
3. candidate is not a semantic duplicate;
4. contradiction with pinned/current facts is checked;
5. evidence class is assigned correctly;
6. freshness/TTL is set if time-sensitive;
7. sensitive material is filtered;
8. resulting canonical revision is persisted atomically.

Derived summaries are disposable caches. Original receipts/evidence remain the ground truth and can invalidate stale summaries.

## 7. Context Pack contract

Every model/ChatGPT escalation receives a bounded Context Pack containing only relevant state.

Minimum fields:
- `context_pack_id`;
- project ID and canonical revision;
- user/global policies relevant to task;
- project invariants/decisions;
- current objective;
- current state/checkpoint;
- relevant known errors/recipes;
- resource/provider constraints;
- permitted tools/actions;
- requested output contract;
- source revision vector/hash.

Every model result that causes a mutation SHOULD record the Context Pack hash for reproducibility.

No model receives the entire memory corpus by default.

## 8. Agent execution model

Agents are ephemeral logical roles, not permanent daemons.

Flow:
`JOB -> Context Pack -> one worker/model -> structured result -> validator -> tool action -> receipt -> durable state`.

Rules:
- no direct free-form agent-to-agent chat loop;
- agents exchange information through BCP artifacts/receipts;
- bounded iteration/depth;
- explicit tool permissions;
- one provider per reasoning step by default;
- mutation proposals are validated before effect;
- recursive agent spawning is bounded/disabled by default;
- a planner may create a DAG, but BCP owns the DAG thereafter.

## 9. Delivery semantics: no fake exactly-once guarantee

Network/distributed execution is treated as at-least-once/replayable.

Every mutation envelope includes:
- `job_id`;
- `action_id`;
- `idempotency_key`;
- expected project revision;
- coordinator epoch/fencing token;
- input hash;
- expected evidence contract.

Receipts include:
- execution attempt;
- result;
- output hashes;
- observed state/readback;
- committed canonical revision if applicable.

A UNIQUE constraint/idempotency ledger prevents duplicate committed effects.

## 10. Split-brain policy

Two-node B-EDGE + PC operation MUST favor consistency over automatic dual-writer availability.

Target V2 policy:
- B-EDGE is the default orchestration coordinator after the migration to V2 authority;
- PC is a fenced worker for canonical state;
- PC may finish already-issued immutable jobs while B-EDGE is unreachable;
- PC stores receipts locally during partition;
- PC MUST NOT independently advance global `PROJECT_HEAD` without a valid coordinator lease/epoch;
- on reconnection, receipts are reconciled idempotently.

Automatic coordinator takeover requires an independent third witness/lease service or explicit user promotion. It must not be simulated with two-node guesswork.

P0 compatibility: until V2 authority migration is field-qualified, the current PC-side canonical-writer behavior remains authoritative. Migration MUST be explicit, versioned and reversible.

## 11. PC dispatch contract

B-EDGE sends immutable work envelopes to the PC:
- job/action identity;
- exact input/source revision/hash;
- resource class/limits;
- execution command/tool;
- timeout;
- evidence/readback contract;
- coordinator epoch.

PC responsibilities:
- reject stale/fenced commands;
- execute only assigned scope;
- checkpoint locally where appropriate;
- return machine-readable receipts;
- avoid promoting global state itself in V2 worker mode.

## 12. Discovery and LAN transport

Primary discovery:
- Android Network Service Discovery / mDNS-DNS-SD with bounded discovery lifetime.

Fallbacks:
- QR bootstrap;
- Bluetooth/companion discovery where justified;
- raw subnet scan only as a bounded diagnostic fallback.

The current /24 parallel scan is POC behavior and MUST NOT become the normal periodic path.

Future-proofing:
- Android 17 local-network permission/picker behavior must be handled before targetSdk 37 promotion.

## 13. Transport security

The current POC HTTP LAN transport is temporary.

Final trusted path MUST NOT transmit bearer credentials over unrestricted cleartext HTTP.

Target:
- persistent PC device identity;
- user-confirmed pairing binds that identity;
- TLS/HTTPS local transport;
- certificate/SPKI/fingerprint pinning or equivalent authenticated channel;
- scoped/rotatable credentials;
- replay-resistant bootstrap nonce;
- no long-lived secret in QR code;
- no provider API keys in telemetry, project memory, GitHub or Drive.

Cleartext may remain only for explicitly isolated localhost/debug compatibility where no secret crosses an untrusted link.

## 14. Telegram/control terminal

Telegram is an adapter, not state authority.

Command handling:
- dedupe by Telegram update/event ID;
- convert command into durable BCP mission;
- immediate acknowledgement may say QUEUED/STARTED;
- result/approval notifications are concise;
- silence means normal health.

Preferred eventual remote-ingress architecture, if field-qualified:
`Telegram webhook -> zero-cost ingress queue/witness -> BCP/B-EDGE/PC`.

Optional FCM may act as a wake hint on compatible Android devices. A push message is not a commit and never replaces durable queue state.

Fallback without cloud ingress:
- Telegram long polling only in an allowed active mode;
- periodic reconciliation is allowed to be delayed;
- no permanent aggressive polling loop.

No zero-cost cloud component becomes required until real Kinshasa/account field validation passes.

## 15. AI quota pacing

Quota is a vector, not one percentage.

Track where available:
- requests/minute;
- requests/day;
- tokens/minute/day/month;
- provider compute units;
- monthly credit;
- reset timestamp/window.

For each quota dimension:
`safe_burn_rate = max(0, remaining - protected_reserve) / max(time_to_reset, epsilon)`.

Call admission compares expected task cost against all active quota dimensions.

A human-facing `AI_CAPACITY` scalar may be derived from the tightest normalized dimension, but diagnostics preserve the full vector.

Bootstrap 50/25/25 planned/fallback/reserve policy remains a conservative starting policy, not a fixed long-term allocation.

## 16. Scheduler fairness

Job priorities:
1. `CRITICAL_INTEGRITY_RECOVERY`
2. `USER_INTERACTIVE`
3. `NORMAL_PROJECT`
4. `BACKGROUND_IMPROVEMENT`

Use priority + aging/fairness so background projects cannot starve forever and one project cannot consume all AI/PC capacity.

Preemption occurs only at safe checkpoint boundaries.

## 17. Migration from current Evergreen POC

Current prototype limitations observed:
- single hard-coded project (`buildhub`);
- complex pending/cached state stored in SharedPreferences;
- no Room/SQLite project-memory fabric;
- no WorkManager scheduler;
- /24 LAN scan with high temporary thread fan-out;
- unrestricted cleartext LAN transport;
- single pending checkpoint slot;
- telemetry queue is bounded but not priority-aware;
- no thermal/memory-aware job governor;
- no multi-project DAG.

Migration order:
1. preserve existing field-proven pairing/update path;
2. add durable database schema + migration tests;
3. move project registry/cache/checkpoint queue to DB;
4. add WorkManager recovery/reconciliation worker;
5. add resource governor;
6. generalize from hard-coded `buildhub` to project registry;
7. add Context Pack + memory admission;
8. add deterministic DAG scheduler;
9. migrate discovery from subnet scan to NSD primary;
10. introduce authenticated TLS LAN transport;
11. qualify split-brain/fencing behavior;
12. add optional Telegram cloud ingress/push wake path;
13. only then promote B-EDGE V2 authority.

Do not break the current P0 release line while incomplete V2 subsystems are being built.

## 18. Success criteria

B-EDGE V2 is not ACTIVE until device tests prove:
- process kill/restart recovers all runnable state;
- phone reboot recovers queues/checkpoints;
- duplicate work does not duplicate canonical effects;
- PC loss/recovery resumes from exact next action;
- PC/B-EDGE partition cannot create two canonical heads;
- memory-pressure eviction loses no durable state;
- thermal/power constraints throttle noncritical work;
- multiple projects remain isolated;
- Context Pack retrieval is deterministic and bounded;
- stale/model-proposed memory cannot silently overwrite pinned facts;
- LAN credential never crosses cleartext in production mode;
- Android 17 local-network behavior has a tested migration path;
- AI reserve cannot be exhausted by a runaway background agent;
- Telegram duplicate updates cannot create duplicate missions;
- ZERO_USD policy fails closed.


## 19. Replication, backup and device-loss recovery

B-EDGE may become the default V2 writer/coordinator, but it MUST NOT become the only durable copy of project memory.

Target copy model:
- primary live V2 orchestration state: B-EDGE Room/SQLite;
- verified near-line replica: PC when available;
- cold encrypted/sanitized recovery snapshots: Drive or equivalent existing user storage;
- source/artifact truth remains in the appropriate GitHub/Drive project stores.

Replication rules:
- secrets are excluded from normal project-memory snapshots;
- provider keys/bearer tokens remain in device credential stores;
- logical snapshots carry schema version, coordinator epoch, project revision vector, record counts, content hash and creation timestamp;
- PC acknowledges replica application with readback/hash;
- cloud/cold backup promotion occurs only after snapshot verification;
- backups are bounded and version-retained; they do not become an unbounded event dump.

Do not raw-copy a live SQLite/WAL file as an arbitrary filesystem operation. Produce a consistent database/logical snapshot using a supported transaction/backup/export path.

### Recovery-key model

If cold backups contain private project memory, they SHOULD be encrypted before cloud storage.

A recovery design must avoid a key that exists only in the phone Keystore, otherwise phone loss makes the backup unreadable.

Preferred target:
- generate a dedicated BCP recovery/data-encryption key;
- wrap/protect a usable copy for B-EDGE using Android Keystore;
- wrap/protect a second usable copy for the paired PC using Windows user-scoped DPAPI or an equivalent OS credential facility;
- Drive receives only ciphertext + non-secret manifest;
- key rotation is versioned;
- loss of one device must not automatically expose plaintext or make verified backups unrecoverable.

The exact cryptographic envelope is an implementation gate and must be reviewed/tested before production use.

### Physical B-EDGE loss

If the phone is destroyed/offline for an extended period:
1. PC freezes global-head advancement by default unless an explicit recovery promotion is performed.
2. PC loads the latest verified replica/snapshot.
3. User or a qualified independent witness authorizes a new coordinator epoch.
4. Replacement B-EDGE is paired and seeded from the verified state.
5. Old coordinator epoch is permanently fenced.
6. Any later receipts from the old device are reconciled as historical/stale evidence, never allowed to overwrite the promoted head.

## 20. History retention and compaction

Not all historical data has equal retention value.

Keep durable:
- canonical mutations;
- action receipts/effect hashes;
- pinned user/project decisions;
- ERROR_LEDGER causal entries and validated recipes;
- authority/fencing transitions;
- security/audit-relevant events.

Compact/expire aggressively:
- repetitive healthy heartbeats;
- redundant transient network events;
- rebuildable Context Pack caches;
- temporary model outputs that produced no accepted effect;
- duplicate telemetry.

Compaction MUST preserve enough provenance to explain every current canonical state transition.

## 21. Telegram wake/ingress tiers

Remote command latency has explicit tiers:

- `T0_LOCAL_ACTIVE`: app/PC active; immediate local command execution.
- `T1_PUSH_WAKE`: optional FCM or equivalent no-cost push wake hint after field qualification.
- `T2_CLOUD_QUEUE`: optional zero-cost webhook ingress stores durable command until a node consumes it.
- `T3_PERIODIC_RECONCILIATION`: no push/cloud; WorkManager reconciliation may be delayed and is not advertised as instant.

Telegram update IDs are deduplicated into one BCP mission ID.

A webhook/push acknowledgment means only `RECEIVED/QUEUED` unless execution evidence exists. It MUST NOT claim `DONE` before canonical receipt/readback.


## 22. Context Fabric / BCP NEXUS integration

B-EDGE V2 is one physical role inside the single logical BCP Context Fabric.

Logical peers:
- B-EDGE = live edge memory/coordinator target;
- PC-WORKER = heavy fenced worker + replica;
- BCP NEXUS = remote bootstrap/context/witness/ingress facade.

B-EDGE MUST continuously maintain precomputable context projections for the universal `BCPGO` bootstrap path.

Projection classes:
- GLOBAL_CORE;
- PROJECT_CORE per active project;
- TASK_DELTA generated from revision change;
- evidence references only, not all raw evidence.

The remote projection is derived and rebuildable. It is not permission to upload all private B-EDGE memory.

Until a dedicated remote BCP adapter is field-qualified, Google Drive-connected projection is the preferred ChatGPT-accessible bootstrap mirror.

BCP NEXUS may later provide the independent witness needed for safe automatic coordinator promotion, but a free cloud candidate is not trusted until ZERO_USD + Kinshasa field gates pass.

Canonical cross-project command: `BCPGO`.
Canonical design: `docs/BCP_CONTEXT_FABRIC_THREE_NODE_ARCHITECTURE.md`.
