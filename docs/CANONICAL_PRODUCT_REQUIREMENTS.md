# API / BCP — Cahier des charges canonique courant

Status: CANONICAL PRODUCT REQUIREMENT
Revision: 2026-09-19-R5
Supersedes: fragmented requirements only as an index; underlying detailed requirement files remain authoritative.

## Mission

API/BCP is the personal digital control and continuity plane for the user's own devices, accounts, repositories, local network, builds and controlled test environments.

The immediate objective is not more architecture. It is to make the Windows + BCP + B-EDGE chain operate in the field with automatic recovery and machine-readable evidence.

## P0 — Windows/field bring-up

The Windows side MUST:
- run as a lightweight managed application on the existing ChatGPT-PC substrate; no heavy local LLM and no unnecessary parallel daemon;
- install/update idempotently with hash verification, readback and rollback;
- survive restart/logon/power/network interruption without losing canonical state; the minimal per-user lifecycle launcher may restart the same managed BCP process, but must not create a second control plane;
- self-update only from allowlisted, hash-pinned release metadata;
- expose health, version, PID, update state, recovery state and bounded diagnostics in machine-readable form;
- publish a sanitized heartbeat independently of the interactive ChatGPT-PC channel;
- never require routine manual IP/token/project entry;
- never require repeated reinstall cycles for normal upgrades or recovery;
- clean its own known temporary/download artifacts automatically after a verified successful install/update, while preserving failure evidence and never deleting unrelated user files;
- remain bounded under high memory pressure on the ~4 GB Windows target;
- fail closed / HOLD on ambiguous state rather than claim ACTIVE.

Current external heartbeat contract:
- canonical filename: `BCP_RUNTIME_LATEST.json`;
- rolling event log: `BCP_RUNTIME_EVENTS.jsonl`;
- preferred synced location: `API_BCP/02_TELEMETRY/BCP/`;
- compatibility fallback while field migration is incomplete: `CHATGPT_PC_AGENT/03_TELEMETRY/BCP/`;
- heartbeat cadence target: <= 60 s while runtime is alive;
- no bearer tokens, secrets or raw arbitrary payloads in the external heartbeat.

## P0 — User friction

The user MUST NOT be the telemetry or integration bus.

Normal operation must not require:
- screenshots for routine diagnostics;
- copying logs between phone/PC/chat;
- retyping IPs/tokens/project IDs;
- downloading successive installer revisions manually;
- repeating project context after a conversation interruption;
- manually relaying prompts/results between model providers.

User interaction should be limited to unavoidable physical approval, security consent, or irreversible-action approval.

## P0 — Durable continuity

Canonical project state lives outside chat.

Every mutation requires:
- revision precondition;
- idempotency key;
- bounded operation contract;
- receipt/readback;
- durable checkpoint;
- single-writer/fencing semantics where multiple conversations can participate.

Conversation/platform/network interruption is nonterminal. Resume from the next uncommitted action; never replay a committed mutation.

## P0 — B-EDGE / phone

B-EDGE MUST:
- discover the PC automatically on trusted LAN/hotspot where feasible;
- pair without normal manual IP/token entry;
- send lightweight telemetry;
- receive compact status/recovery state;
- continue/recover across intermittent connectivity;
- use app-owned cache for future in-app update payloads and delete those payloads after verified installation; do not request broad storage access merely to clean arbitrary Downloads;
- support a later fallback path (QR/Bluetooth or equivalent) only if measured LAN discovery failure justifies it.

## P0 — Dedicated B-EDGE orchestration and project-memory role

The old Android phone is a dedicated always-on B-EDGE node, not merely a telemetry relay.

B-EDGE MUST provide a lightweight local control plane containing:
- durable project-memory cache and project-state index;
- local scheduler and dependency graph for jobs/agents;
- policy/rule engine;
- ERROR_LEDGER / validated-recipe lookup;
- provider/quota state cache;
- PC supervisor and resource-state cache;
- local queue/outbox and checkpoint pointers;
- compact context-pack builder for ChatGPT/agents;
- HOT/WARM/COLD project-memory tiers.

Before any agent/model call, B-EDGE/BCP SHOULD perform the maximum safe deterministic work locally:
1. load canonical project state;
2. resolve current project/head/checkpoint;
3. inspect dependencies and blockers;
4. check cache / ERROR_LEDGER / known recipes;
5. deduplicate already-solved work;
6. build the minimal context pack;
7. decide whether an LLM call is necessary;
8. dispatch only the unresolved semantic task.

Normal orchestration decisions such as `dependencies_done -> queue(next_task)` MUST be local deterministic logic and MUST NOT consume LLM quota.

B-EDGE MUST support at least these operating modes:
- `EDGE_ONLY`: PC offline; memory, scheduler, queues, Telegram/control, light rules and remote free-API calls remain available.
- `PC_AVAILABLE`: PC healthy; B-EDGE coordinates and dispatches heavy work to PC.
- `PC_MEMORY_PRESSURE`: PC under high RAM/CPU pressure; heavy jobs queue/pause while B-EDGE continues memory/orchestration and may route reasoning to remote APIs.
- `PC_UNAVAILABLE_RECOVERY`: PC lost/rebooting; B-EDGE preserves last committed revision, checkpoints and pending jobs, then reconciles and resumes when PC returns.

Project-memory temperature policy:
- `HOT`: active projects; recent state/index/context cache may stay resident in RAM.
- `WARM`: recently used projects; partial cache resident.
- `COLD`: inactive projects; persist on storage/SQLite and load on demand.

Memory pressure MUST degrade HOT -> WARM -> COLD without losing durable state.

B-EDGE may use a larger RAM cache in dedicated-phone mode, but heavy sustained CPU, local large-model inference, compilation, video processing, or other thermal-heavy workloads are out of scope by default. The preferred use of phone RAM is hot state/index/cache, not continuous heavy compute.

BCP memory MUST be structured into at least:
- USER_MEMORY / stable user preferences and cross-project defaults;
- PROJECT_MEMORY / project-specific state, decisions, constraints and next actions;
- TECHNICAL_KNOWLEDGE / ERROR_LEDGER, validated recipes and reusable lessons;
- OPERATING_STATE / live node/job/provider state;
- HISTORY / receipts/events;
- POLICY / permissions, budgets and invariants.

Before ChatGPT/agent execution, the Context Builder MUST assemble only the relevant subset of these layers. Chat history is never the sole source of truth.

When the PC is offline, B-EDGE SHOULD precompute and prepare as much as possible: resolve project state, build work plans, prepare compact context, consult free remote models when policy allows, and queue heavy jobs as `WAITING_FOR_PC`. When the PC returns, it should receive already-prepared bounded work rather than redoing orchestration.


## P0/P1 — B-EDGE V2 hardening invariants

The dedicated-phone architecture MUST distinguish current field-proven P0 behavior from the target B-EDGE V2 authority migration.

### Android process/lifecycle invariant

"Always-on B-EDGE" means always recoverable, not process immortality.

- correctness MUST NOT depend on the Android app process remaining resident;
- in-memory state is rebuildable cache only;
- durable project/job/memory state migrates to a transactional Room/SQLite fabric;
- WorkManager is the baseline persistent/deferred execution primitive;
- a permanent foreground data-sync service or exact-alarm loop is not the baseline scheduler;
- after process/device restart, B-EDGE reconstructs runnable state from durable storage and reconciles receipts/idempotency.

### Durable memory invariant

Complex multi-project state MUST NOT remain implemented as one hard-coded project plus SharedPreferences slots.

Target storage MUST support:
- project registry;
- scoped memory;
- multi-job DAG/dependencies;
- multiple pending actions/checkpoints;
- receipts/idempotency ledger;
- outbox;
- provider/node state;
- ERROR_LEDGER;
- Context Pack cache and provenance.

Secrets remain in Android Keystore-protected storage and MUST NOT be copied into ordinary memory/telemetry/Drive/GitHub.

### Agent invariant

Agents are ephemeral logical workers. They do not form a permanent peer-to-peer chat network.

`JOB -> CONTEXT_PACK -> WORKER -> STRUCTURED_RESULT -> VALIDATOR -> TOOL/EFFECT -> RECEIPT -> DURABLE_STATE`

BCP owns sequencing, permissions, retries, budgets and stop conditions.

A model output cannot directly become canonical memory or a committed project mutation without validation/evidence.

### Delivery/idempotency invariant

BCP MUST NOT claim impossible network-level exactly-once execution.

The target is replayable/at-least-once delivery with:
- stable idempotency keys;
- revision preconditions;
- coordinator epoch/fencing;
- effect/readback receipts;
- unique committed-effect deduplication.

### Split-brain invariant

During the V2 authority phase, B-EDGE becomes the default orchestration coordinator and the PC becomes a fenced heavy worker.

During a partition:
- PC may complete already-issued immutable jobs and preserve receipts;
- PC MUST NOT independently advance the global project head without a valid coordinator fence;
- delayed stale-epoch commands are rejected;
- automatic writer takeover requires an independent third witness/lease service or explicit user promotion.

Until this migration is field-qualified, the existing PC-side canonical writer remains authoritative. Authority migration MUST be explicit, versioned, reversible and tested.

### Resource governor invariant

Every job is classified before execution:
- `EDGE_R0`: tiny deterministic;
- `EDGE_R1`: light DB/network/context;
- `EDGE_R2`: heavier index/compaction/bulk work under favorable battery/thermal/RAM conditions;
- `PC_R3`: heavy build/test/file/CPU work;
- `REMOTE_AI`: semantic reasoning subject to quota/privacy gates.

Android memory pressure evicts HOT/WARM caches before any durable state. Thermal/power-save/battery/network state can defer noncritical work.

### Discovery/transport invariant

The current raw /24 scan + cleartext HTTP path is POC-compatible behavior, not final production architecture.

Target:
- NSD/mDNS-DNS-SD primary discovery with bounded lifetime;
- QR explicit bootstrap fallback;
- subnet scan only as bounded diagnostic fallback;
- Android 17 local-network permission/system-mediated picker migration before targetSdk 37;
- persistent PC identity and authenticated encrypted LAN transport;
- no bearer/API credential over unrestricted cleartext HTTP in production mode.

### Telegram/remote-ingress invariant

Telegram is a cockpit adapter, never canonical state.

A future zero-cost webhook/push ingress may improve wake latency, but remains optional and must pass the same real Kinshasa/account field gate. Durable BCP queue state, not push delivery, is authoritative.

Canonical hardening documents:
- `docs/BEDGE_RUNTIME_V2_HARDENING.md`
- `docs/BEDGE_V2_TEST_MATRIX.md`
- `.project-memory/BEDGE_RUNTIME_V2_POLICY.json`

## P0 — Synchronized product release train

Normal user-facing releases MUST be coordinated product increments, not isolated micro-patches.

Except for an explicitly labeled emergency hotfix, a release candidate MUST advance and qualify the coordinated set:
- Windows/PC BCP runtime and lifecycle;
- Android B-EDGE application;
- PC↔B-EDGE protocol compatibility;
- durable memory/checkpoint/orchestration state;
- telemetry and machine-readable acceptance evidence;
- offline/reconnect/reboot recovery;
- resource-pressure behavior on the 4 GB PC and dedicated Android node;
- update/rollback and Drive CURRENT distribution.

A user-facing TEST/CURRENT artifact MUST NOT be presented as a meaningful product milestone if it only changes an acceptance harness or one narrow symptom while leaving the synchronized product capabilities unchanged.

Each release candidate MUST publish a coverage manifest mapping implemented/tested capabilities to the current canonical requirements revision. The manifest MUST distinguish IMPLEMENTED, TESTED_STATIC, TESTED_CI, TESTED_DEVICE, FIELD_VERIFIED, DEFERRED and NOT_IMPLEMENTED.

Before publication to Drive CURRENT, PC and Android artifacts MUST be built from compatible pinned revisions and their compatibility contract MUST be tested together. Device tests that can be automated or simulated MUST run before user field testing. User interaction is reserved for irreducible physical gates such as Android package installation, OS confirmation, first trust confirmation, or real-device reboot/sign-in.

The release pipeline SHOULD batch multiple related P0 improvements into a coherent increment so that every user-visible release materially reduces the distance to the final specification.

## P0 — Environment constraints

Design assumptions:
- unstable mains power and Internet are normal;
- low bandwidth and temporary offline periods are normal;
- Windows memory pressure can be very high;
- battery use on phone and PC matters;
- DEFAULT_PAID_SPEND = 0 USD.

Therefore use:
- lightweight JSON state/receipts;
- durable local queues/outbox;
- bounded retries/backoff;
- bounded concurrency;
- cache/reuse;
- no heavyweight always-on services unless measured evidence requires them.

## P0 — Proof rules

`MODEL != PORTABLE != CLOUD != NATIVE != FIELD`.

No component is FIELD_VERIFIED or ACTIVE until fresh native/field evidence exists.

A valid Windows field promotion requires at minimum:
1. exact runtime version readback;
2. fresh heartbeat within the expected cadence;
3. successful health/diagnostics readback;
4. update/rollback state coherent;
5. no missing/hash-error payload evidence;
6. restart/recovery proof;
7. no duplicate canonical mutation.

## P0 — Current release objective

Current target: BCP 0.4.7.

BCP 0.4.7 keeps the 0.4.6 field-proof guarantees and adds an authenticated local B-EDGE update relay backed by the canonical Drive installer folder. The server recomputes the APK SHA-256 before exposing release metadata or bytes.

Promotion gate:
- CI qualification PASS;
- Windows installer/selftest PASS;
- existing managed-update path consumes 0.4.7;
- `BCP_RUNTIME_LATEST.json` appears in synced Drive;
- its timestamp/version/hash prove a live 0.4.7 runtime;
- B-EDGE telemetry/readback follows.

No blind reinstall is allowed merely because telemetry is missing.

## P1 — Provider/model broker and autonomous loops

After P0 continuity is field-proven:
- add a provider-neutral Model Broker;
- support legitimate free/zero-cost/BYOK providers as replaceable adapters;
- make quota/capacity/cost explicit and field-measured from Kinshasa before ACTIVE promotion;
- never silently spend money; `DEFAULT_PAID_SPEND = 0 USD` is a hard invariant;
- use bounded autonomous loops with deterministic verification;
- integrate GitHub/BuildHub/B-EDGE jobs through receipts;
- add Telegram or equivalent low-bandwidth cockpit for status, approvals and alerts;
- optimize for 24-hour endurance rather than maximum instantaneous LLM throughput;
- preserve strategic provider capacity for incidents and user-facing work later in the day;
- continue useful deterministic/local work even when all free LLM capacity is exhausted.

### P1 — Mandatory 24-hour AI endurance policy

A "continuous chantier" means continuous useful progress, not continuous prompting.

All work escalates through this ladder:
`EVENT_ENGINE -> RULE_ENGINE -> KNOWLEDGE_CACHE/ERROR_LEDGER -> LOW_COST_MODEL -> REASONING_MODEL -> HUMAN/CHATGPT`.

A higher layer is used only when lower layers cannot safely resolve the task.

The following are local/deterministic by default and MUST NOT consume LLM quota merely because a model is available: heartbeat, telemetry, synchronization, hashes, build invocation, test execution, retries/backoff, queue/outbox replay, known-error repair, checkpointing, resource observation and routine notifications.

Before any model call, BCP MUST batch, deduplicate, causal-group and resolve known events locally. One event MUST NOT imply one LLM call. Offline event backlogs are compacted before model escalation.

For every ACTIVE_FREE_PROVIDER, BCP MUST maintain observed capacity, reset window, recent 429/errors, latency, success history and task fit. Marketing quotas are not operational truth; real account/API telemetry is.

Initial conservative allocation after field validation:
- <= ~50% of measured free capacity for planned/background work;
- ~25% for fallbacks and user-impacting incidents;
- ~25% protected strategic reserve.

These are bootstrap scheduling ratios, not vendor facts, and may adapt after telemetry while preserving a non-zero reserve.

Every provider has a `SOFT_LIMIT`, `RESERVE_FLOOR` and `HARD_LIMIT`. Crossing the soft limit increases routing cost; background work cannot cross the reserve floor; the hard limit prevents accidental exhaustion or paid use.

When free capacity becomes constrained, BCP enters `AI_CONSERVATION_MODE`: it continues tests, fuzzing, static analysis, dependency checks, benchmarks, log processing, backups, deterministic AX150K exploration and known-error remediation while sharply reducing model calls. If no compliant free model remains, only LLM-dependent work enters `FREE_MODEL_CAPACITY_HOLD`.

Parallel projects share one global AI budget. Background work may never monopolize all provider capacity. User-impacting or integrity/recovery incidents may preempt a background chantier after checkpoint.

The normal reasoning path uses one provider. Multi-model fan-out is forbidden by default; cross-checking is allowed only for bounded reasons such as low confidence, contradictory diagnoses, high-impact architecture, failed first attempt or an explicit audit step.

Every model call MUST pass a call-admission circuit breaker that rejects/defer/reroutes duplicate, cached, unnecessary, unhealthy, over-budget, non-free, reserve-violating or retry-loop calls.

Logical agents are provider-neutral. Providers are interchangeable execution engines selected by measured capability, reliability, latency and remaining free capacity, not hard-coded brand identity.

Telegram/UI SHOULD expose a compact `AI_CAPACITY` abstraction (daily state, emergency reserve, long-window capacity, provider health, calls avoided, spend) while provider-specific quota units remain diagnostic detail. Silence means normal operation; routine healthy heartbeats must not spam the user.

Required optimization KPIs include deterministic-operations count, LLM calls by provider/project/task, calls avoided by cache/rules/deduplication, quota consumption, 429/error rate, non-LLM incident resolution rate, time-to-recovery, reserve state and the invariant `SPEND_USD = 0.00`.

Canonical detailed policy: `docs/FREE_API_MODEL_BROKER_AUTONOMY_REQUIREMENTS.md`.
Machine-readable provider plan: `.project-memory/AI_PROVIDER_PLAN_RDC.json`.

These extensions must not displace the P0 field bring-up.

## P1 — Universal Context Fabric / three-node BCP

BCP MUST present one logical personal control/data plane across:
- **B-EDGE** — dedicated Android memory/coordinator node;
- **PC-WORKER** — heavy execution + verified replica;
- **BCP NEXUS** — remotely reachable thin bootstrap/context/witness/ingress facade.

The user-facing universal bootstrap command is:
`BCPGO`

`BCPGO` is a semantic trigger, not an authentication credential.

A fresh authorized ChatGPT conversation SHOULD use `BCPGO` to:
1. read a tiny current bootstrap manifest;
2. load GLOBAL_CORE;
3. infer or accept an explicit project scope;
4. load only that PROJECT_CORE;
5. load a bounded TASK_DELTA;
6. continue from current durable state without asking the user to restate already-persisted preferences/architecture.

Normal bootstrap MUST be precomputed and MUST NOT broad-scan the full memory corpus or repositories.

Per-turn context refresh SHOULD use revision-aware results:
- `UNCHANGED`;
- `DELTA`;
- `FULL_REFRESH`;
- `CONFLICT`;
- `DEGRADED`;
- `HOLD`.

This permits BCP consultation before each answer/action without repeatedly injecting the full memory corpus.

Memory MUST distinguish:
- normative instructions/preferences/policies;
- descriptive machine/source facts;
- derived summaries;
- untrusted external content.

External/web/retrieved/model-generated content MUST NOT directly promote itself into USER_MEMORY, POLICY or pinned project decisions.

Target connected-store baseline for current ChatGPT workflow:
- `API_BCP/00_CONTEXT/BCP_BOOTSTRAP_CURRENT.json`
- `API_BCP/00_CONTEXT/GLOBAL_CONTEXT_CURRENT.json`
- `API_BCP/00_CONTEXT/projects/<project_id>/PROJECT_CONTEXT_CURRENT.json`

A future remote MCP/plugin/app adapter is optional and must be field/product qualified. Current architecture MUST NOT assume that the user's present ChatGPT Plus plan provides writable custom MCP access.

Canonical detailed architecture:
`docs/BCP_CONTEXT_FABRIC_THREE_NODE_ARCHITECTURE.md`.



## P1 — Three-node context fabric and universal recall

BCP MUST evolve into a three-node personal context fabric:

1. **B-EDGE** — dedicated always-on local continuity/memory/orchestration node.
2. **PC-COMPUTE** — burst/heavy execution node for builds, tests and resource-intensive work.
3. **BCP CORE / CONTEXT GATEWAY** — logical central API/context authority with no single physical free-cloud dependency.

The canonical universal context command is `BCPGO`. It is a bootstrap intent, not an authentication secret.

Target behavior:
`BCPGO -> scope resolution -> fast Context Capsule -> current preferences/policies/project state -> execution -> controlled writeback`.

A fresh supported conversation should not require the user to restate stable preferences, project architecture, current HEAD, known errors or the last committed action.

### Context performance

BCP MUST use precomputed HOT project capsules, revision hashes and delta retrieval. Expensive embedding/reindex work must stay off the synchronous bootstrap path.

Targets:
- B-EDGE cached resolver processing p95 <= 100 ms;
- cached BCP Context Gateway processing p95 <= 200 ms excluding network;
- healthy-network supported-client bootstrap target p95 <= 1.5 s;
- unchanged contexts return `NO_CHANGE` plus revision/hash rather than full reload.

These are engineering targets and require field measurement before any guarantee.

### Structured memory

Memory is mixed/hierarchical rather than one monolithic summary.

Required classes:
`USER_POLICY`, `PROJECT_FACT`, `PROJECT_DECISION`, `RUN_STATE`, `ERROR_KNOWLEDGE`, `EPISODE`, `SUMMARY`, `RELATION`.

Retrieval must first filter by scope, authority and freshness; use semantic retrieval only where helpful; rerank and detect conflicts/staleness before producing the capsule.

### Automatic READ, controlled WRITE

Authorized context READ may be automatic.

Memory WRITE is gated. Model output does not become canonical merely because a model produced it.

Lifecycle:
`OBSERVED -> PROPOSED -> VERIFIED -> CANONICAL -> SUPERSEDED/REVOKED`.

Every durable memory item carries provenance, scope, timestamps, authority, sensitivity, freshness policy and supersession links.

External/retrieved content is untrusted and cannot directly modify policy or promote itself into canonical memory.

### Consistency

Critical state uses single-writer revisions, leases, fencing and idempotency. Blind CRDT/merge semantics are forbidden for writer ownership, project HEAD, policy, permissions, mission and committed-action state.

Append-only/noncritical telemetry may use merge-friendly event-log semantics.

### Supported access paths

BCPGO must have capability-gated transports:
- sovereign Telegram/BCP terminal: preferred guaranteed path once built;
- ChatGPT plugin/app/MCP path only after the actual account/surface passes field qualification;
- ChatGPT-PC bridge where supported;
- one compact manual capsule as last-resort fallback.

A typed phrase alone cannot grant a client network access. BCP must not claim native ChatGPT connectivity unless the connector/tool path is actually installed and field-tested.

Canonical detailed design: `docs/THREE_NODE_CONTEXT_FABRIC_ARCHITECTURE.md`.
Machine-readable policy: `.project-memory/CONTEXT_FABRIC_POLICY.json`.

## Acceptance sequence

The project is not considered operationally complete until this sequence passes:
1. Windows BCP runtime proves current version via external heartbeat.
2. B-EDGE discovers/pairs and produces telemetry.
3. Checkpoint commit succeeds.
4. Windows/runtime or network is interrupted.
5. Same committed revision is recovered without replay.
6. Fresh conversation recovers exact state without user reconstruction.
7. Stale writer mutation is rejected.
8. Resource-pressure and poor-connectivity tests remain bounded.


## Acceptance execution policy

Final acceptance MUST be batched rather than performed as a sequence of manual user tests.

The canonical field campaign is `BCP_FINAL_ACCEPTANCE_CURRENT` and must:
- update BCP to the current qualified target if needed;
- create one checkpoint with an explicit revision precondition;
- replay the same idempotency key and prove no duplicate revision is created;
- submit a stale-revision mutation and prove it is rejected;
- verify loopback and LAN health;
- snapshot pairing/token/committed revision;
- schedule one automatic Windows reboot and resume through RunOnce;
- prove the same pairing/token and committed revision/hash survive reboot without replay;
- prove the managed BCP listener/lifecycle returns;
- run bounded resource-pressure and poor-connectivity probes;
- publish one machine-readable `BCP_FINAL_ACCEPTANCE_LATEST.json` receipt;
- clean only its own known downloaded/extracted acceptance artifacts after success.

The user must not be required to return between individual gates. One launch may cover the device/runtime acceptance campaign. A brand-new ChatGPT conversation is a platform boundary and may be spot-checked separately because the local PC harness cannot instantiate a new ChatGPT conversation itself.


### Downloads hygiene

Known legacy BCP artifacts in the Windows Downloads folder are deleted by exact allowlisted names at the beginning of the final acceptance campaign. The currently-running acceptance package is preserved until the campaign succeeds, then its own downloaded/extracted files are removed. Unrelated user files are never matched by the cleanup rule.


### Publication gate

A Drive `CURRENT` artifact MUST NOT be replaced by an unqualified build. Publication requires all applicable public GitHub CI gates to pass first: syntax/parse, self-test, internal object-contract checks, version/manifest cross-checks, server self-test and package creation. Failed/cancelled builds remain diagnostic evidence only and are never promoted to `API_BCP/00_A_INSTALLER`.


## P0 — B-EDGE Evergreen distribution

The canonical Android line is B-EDGE Evergreen.

Requirements:
- stable package identity and stable Android signing certificate;
- private signing key MUST remain outside public GitHub;
- public GitHub receives only non-secret certificate fingerprint/release metadata and must qualify source/unsigned APK before signing;
- signed APK promotion to `API_BCP/00_A_INSTALLER/BCP_EDGE_CURRENT.apk` happens only after all Android CI gates pass;
- B-EDGE downloads future updates through the authenticated local BCP relay, not from an unauthenticated arbitrary URL;
- update manifest package ID, version, APK SHA-256 and signing-certificate SHA-256 are verified before installation;
- APK payload lives in app-owned cache and is cleaned after a verified successful update;
- normal micro-patch flow is one tap in B-EDGE plus the Android installation confirmation required by the OS;
- update failures never destroy pairing or canonical project state;
- the first transition from the legacy debug-signed 0.2.5 line may use a one-time side-by-side Evergreen package because the old ephemeral signing key cannot be recovered safely;
- subsequent Evergreen versions MUST update in place without uninstall/reinstall cycles.


## P0 — Cumulative specification continuity

For every project, the phrase **“mise à jour du cahier des charges”** means **MERGE + REFINE + PRESERVE**.

The new user input is a delta against the current active requirement set, never a replacement specification.

Required behavior:
- load prior active requirements first;
- classify the new delta as ADD, REFINE, SUPERSEDE_EXPLICIT, DEPRECATE_EXPLICIT or CONFLICT_HOLD;
- preserve every prior active requirement not explicitly superseded;
- preserve history/provenance for superseded requirements;
- never delete an old principle merely because it was omitted from a newer message;
- keep acceptance tests, error-ledger obligations and regressions attached to all still-active requirements;
- if a contradiction is ambiguous, hold the conflicting requirement and ask only the minimum clarification needed;
- materialize a current canonical view from the active requirement graph after every accepted update.

Canonical machine-readable policy:
`.project-memory/SPEC_EVOLUTION_POLICY.json`.

## P1A — Telegram mission cockpit and observable long-running work

After the currently active BCP 0.4.7 field-acceptance campaign, accelerate the Telegram/BCP cockpit from a notification-only concept into a mission-control surface.

Target:
`Telegram -> BCP Mission Intake -> durable MISSION_ENVELOPE -> deterministic engine / Model Broker / workers -> append-only MISSION_EVENT_LOG -> receipts/checkpoints -> Telegram status`.

The user must be able to submit a normal-language request, confirm a deep execution with a compact action such as `1`, receive a short job reference, and see the exact durable progress without depending on a ChatGPT conversation remaining responsive.

Long work must be decomposed into bounded micro-sprints and checkpointed after every committed mutation. Persist observable decisions/actions/receipts, not hidden model chain-of-thought.

A short code such as `48273195` is a mission locator, not the mission content and not an authorization credential. Preferred explicit handoff syntax is `BCPGO <job_code>`. Resolution is available only on clients with a qualified BCP integration.

When a chat/provider is delayed, BCP must expose the exact last confirmed checkpoint and a durable waiting state such as `WAITING_EXTERNAL_CHAT_RESULT` or `PROVIDER_PENDING_UNKNOWN`; it must never fabricate hidden progress.

Canonical detailed design:
`docs/TELEGRAM_MISSION_COCKPIT_AND_PROGRESS_JOURNAL.md`.


## P0 — Repository single-writer / Git integration fence

This policy applies to all active ChatGPT project conversations, Work sessions, CI bots and future agents.

Many workers may reason in parallel, but canonical repository state advances through one fenced integration path.

Normal autonomous path:
`READ_MAIN_HEAD -> UNIQUE_WORK_BRANCH -> SERIAL_MUTATIONS -> CI -> PR -> MAIN_HEAD_RECHECK -> RECONCILE_IF_MOVED -> SERIALIZED_MERGE -> READBACK`.

Requirements:
- no autonomous direct product mutation to `main`;
- each writer records exact `base_main_sha`;
- one work branch per conversation/session/mission;
- concurrent file writes on the same branch are forbidden;
- CI proof belongs only to the exact commit SHA tested;
- moved `main` requires reconciliation and requalification before merge;
- useful divergent work is preserved on `recovery/*` branches;
- normal automation never force-pushes `main`;
- Drive/release CURRENT publication must reference the exact qualified merged source SHA.

Canonical protocol:
- `docs/GIT_WRITER_LEASE_AND_BRANCH_PROTOCOL.md`
- `.project-memory/GIT_WRITER_LEASE_POLICY.json`
