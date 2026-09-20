# API / BCP — Cahier des charges canonique courant

Status: CANONICAL PRODUCT REQUIREMENT
Revision: 2026-09-20-R15
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

Current synchronized target: **BCP 0.6.2 + B-EDGE 2.0.0-rc1 Evergreen**, requirements revision R8.

The preserved BCP 0.6.0 / B-EDGE 2.0.0-rc1 line is field-evidenced: Drive telemetry proves a live Windows BCP 0.6.0 runtime and Drive CURRENT contains the privately signed B-EDGE 2.0.0-rc1 APK. That field-proven line MUST be reconciled with the newer Git writer fence, Nexus/Telegram transport, Progress Presence and `P0_MISSION_AUTONOMY_AND_OBSERVABLE_EXECUTION`; it MUST NOT be replaced by a lower 0.5.x line.

BCP 0.6.1 is the anti-downgrade patch train that combines those lines. The version increment is mandatory because a live 0.6.0 runtime will not consume a different same-version payload through the monotonic managed updater.

Promotion gate:
- exact-head coordinated CI PASS for Windows, Android, compatibility, CURRENT, Telegram and Nexus;
- server source/version/hash and installer/acceptance target agree on 0.6.1;
- the signed B-EDGE CURRENT APK hash/signing identity are pinned and read back;
- merge occurs only through the Git single-writer fence;
- the existing managed updater advances the live PC from 0.6.0 to 0.6.1 without downgrade/reinstall;
- fresh `BCP_RUNTIME_LATEST.json` proves 0.6.1 by timestamp/version/hash;
- B-EDGE exact-version/readback and mission-journal interruption/recovery evidence follow.

No blind reinstall is allowed merely because telemetry is missing. Existing field-proven 0.6/Edge2 artifacts are preserved until their reconciled successors are proven.

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

The earlier 0.4.7 sequencing gate is superseded by the reconciled 0.6.1/R8 line. Telegram/BCP mission control and observable durable execution are now active P0 requirements and must be qualified together with field continuity rather than postponed behind an obsolete release number.

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


### Telegram observability MVP

Before full Telegram mission execution is enabled, deploy a read-only observability MVP that aggregates BCP runtime, GitHub/CI, BuildHub, B-EDGE/PC telemetry, Model Broker lifecycle and other durable receipts.

ChatGPT visibility is evidence-based:
- externally committed/checkpointed ChatGPT work may be shown as observed;
- a dispatched request with no completion receipt is shown as `CHAT_WAITING`;
- a reported verification state may be shown as `CHAT_PLATFORM_HOLD_REPORTED`;
- if the standard ChatGPT UI exposes no supported telemetry, show `UNKNOWN_INTERNAL_CHAT_STATE`.

Never claim access to hidden chain-of-thought or OpenAI internal verification progress.

Canonical design: `docs/TELEGRAM_OBSERVABILITY_MVP.md`.

## P0/P1 — Telegram read-only observability control plane

This is an additive refinement under SPEC_REFRESH_CURRENT_THEN_MERGE_REFINE_PRESERVE. It does not retire the Windows/B-EDGE field, durability, synchronized-release, Context Fabric, writer-fence, secret-handling or zero-spend requirements above.

Current priority is to field a read-only Telegram cockpit before complex AI-agent control.

MVP-0 MUST:
- expose /status, /project <id>, /job <code>, /last, /ci and /holds;
- aggregate only machine-readable or externally observable truth from BCP runtime, B-EDGE/PC telemetry, GitHub commits/branches/PR/Actions, BuildHub receipts, Drive receipts/checkpoints, Mission Event Journal and Model Broker state when those sources are actually accessible;
- represent missing sources as NOT_OBSERVED/UNKNOWN rather than inventing progress;
- use ChatGPT states OBSERVED_CHAT_ACTION, CHAT_WAITING, CHAT_PLATFORM_HOLD_REPORTED and UNKNOWN_INTERNAL_CHAT_STATE only from supported external evidence;
- never claim access to hidden chain-of-thought, internal OpenAI verification progress or other inaccessible ChatGPT internals;
- preserve DEFAULT_PAID_SPEND=0 USD and never auto-enable billing;
- keep the Telegram bot token in local secret storage only; it MUST NOT be committed, synced to Drive, printed in status, or requested through ChatGPT;
- allowlist one explicitly approved private Telegram chat for initial deployment;
- remain read-only: mutating Telegram commands are refused until a later separately qualified stage;
- use lightweight long polling/event-driven observation with bounded retry/backoff, small payloads and bounded cache; no aggressive polling or heavy always-on framework;
- preserve the repository Git single-writer fence for every future Telegram-triggered mutation.

Field promotion requires a normal-network Kinshasa smoke test without VPN, false country data or unofficial relay: official Bot API getMe succeeds, the user's private message is observed, sendMessage succeeds, and /status returns a truthful evidence-based response. Documentation alone is not FIELD proof.

MVP-1 through MVP-4 remain future gated increments: durable Mission Event Journal integration; mission normalization/explicit action selection; short mission locator and BCPGO <code>; then Model Broker routing only through RDC field-qualified zero-cost providers.


## P0 — RDC network/data-saver resilience

This is additive under SPEC_REFRESH_CURRENT_THEN_MERGE_REFINE_PRESERVE.

Field evidence shows the Telegram cockpit is functional over mobile data while the PC's home-Wi-Fi path resolves api.telegram.org but times out on TCP/443. Therefore the product MUST NOT require the whole PC to remain on mobile hotspot.

Requirements:
- home Wi-Fi is the PC default transport;
- mobile data is scarce/metered fallback only;
- Telegram/control-plane traffic may fail over selectively without moving bulk project traffic to cellular;
- preferred steady-state is a lightweight Telegram transport on B-EDGE with authenticated local B-EDGE<->PC communication;
- offline queueing, bounded retry/backoff, idempotency and reconnect recovery are mandatory;
- large downloads/artifacts MUST NOT silently use cellular fallback;
- compact deltas/receipts and cache-first behavior are required;
- no VPN, false geography, quota circumvention or paid fallback;
- the user is not the network/secret/log relay.

Canonical detailed policy:
`docs/RDC_NETWORK_AND_DATA_SAVER_POLICY.md`.
 

## P0/P1A — Progress Presence during opaque ChatGPT/UI delays

The immediate user-facing objective of the Telegram cockpit is certainty of progress when ChatGPT UI is delayed, interrupted, disconnected or under additional verification.

BCP MUST provide proactive, durable progress presence from external evidence:
- per-mission event journal;
- current component/step and elapsed time;
- last confirmed checkpoint/proof;
- next safe action;
- transition notifications;
- sparse adaptive waiting heartbeats;
- explicit `NO_NEW_EXTERNAL_EVIDENCE` / `WAITING_EXTERNAL_CHAT_RESULT` instead of invented thinking progress;
- Telegram `/watch`, `/tail`, `/where` surfaces.

This does not claim access to hidden model chain-of-thought or internal platform verification state.

Detailed contract:
`docs/TELEGRAM_MISSION_COCKPIT_AND_PROGRESS_JOURNAL.md`.


### Human-first cockpit UX

The user-facing Telegram surface MUST default to a simple dashboard, not engineering telemetry.
- `/status` = simple state, checkmarks, next action and a progress bar/percentage only over explicitly finite verifiable items;
- `/details` = technical evidence for agents/debugging;
- raw SHAs, branches, hashes and diagnostic jargon stay in the technical view unless they are needed for a real human decision;
- hidden reasoning progress is never converted into a fake percentage.


## P0/P1A — Push-first progress relay and no-manual-update target

This refinement preserves all prior field-acceptance, Git writer fence, zero-spend, security and data-saver requirements.

User-facing progress MUST be push-first:
- BCP-managed micro-actions emit durable mission events;
- Telegram pushes state transitions automatically instead of requiring repeated `/status` polling;
- `/where [job]` and `/tail [job]` expose current and recent durable proof;
- fast event bursts may be compacted, but committed/checkpointed boundaries remain recoverable;
- a missing event is never replaced with invented hidden reasoning.

The dedicated old Android phone (B-EDGE) is the preferred low-data Telegram relay:
- PC heavy work remains on home Wi-Fi;
- PC<->B-EDGE remains local/authenticated;
- when qualified and necessary, only Telegram control-plane sockets may use selective cellular egress on B-EDGE;
- large artifacts and bulk sync must never silently move to cellular.

Manual replacement of Telegram worker files is a bootstrap-only condition. The steady-state product MUST use a qualified, hash-verified, atomic, rollback-capable worker update path that preserves the locally stored bot secret and authorized chat state.

A future ChatGPT-visible-state observer may record only states exposed by the user's own client/UI. It MUST NOT infer or expose hidden chain-of-thought or internal platform-verification progress.

Canonical detailed architecture:
`docs/TELEGRAM_PROGRESS_RELAY_AND_UPDATE_ARCHITECTURE.md`.


## P0/P1A — Correct field topology and transport independence

The canonical field topology is:
- PC-WORKER: home Wi-Fi primary.
- B-EDGE dedicated old Android phone: same home Wi-Fi primary; no cellular fallback is assumed.
- Current daily phone: may use Wi-Fi or mobile data, but MUST NOT be required as an always-on BCP relay.

Telegram delivery MUST NOT depend on direct PC access to api.telegram.org. The system SHALL support a transport abstraction with:
- LOCAL_LAN_OUTBOX;
- DIRECT_TELEGRAM when healthy;
- NEXUS_WEBHOOK/HTTPS relay after zero-cost field qualification;
- offline store-and-forward.

If direct Telegram egress fails, local BCP work continues and only the remote cockpit is degraded.

The current phone's mobile data is a user-access path, not infrastructure capacity.

## P0/P1A — Automatic qualified update plane

Routine BCP/PC/B-EDGE upgrades MUST converge toward zero-manual distribution:
- CI builds and qualifies coordinated artifacts;
- a compact CURRENT manifest carries version, compatibility, source revision, hashes/signature identity, artifact location and rollback metadata;
- unchanged manifests cause no artifact download;
- PC stages, verifies, applies, health-checks and automatically rolls back on failure;
- B-EDGE checks updates through WorkManager/reconnect-triggered work on allowed Wi-Fi, downloads only changed APKs to app-owned cache, verifies them, and requests only the unavoidable Android package-install approval;
- successful install/update emits machine-readable receipts and removes temporary payloads;
- Drive CURRENT is replaced in place only after qualification and bounded rollback history is preserved;
- no ChatGPT scheduled automation is part of the update plane.

Canonical design:
`docs/HOME_WIFI_EDGE_NEXUS_AND_AUTOMATIC_UPDATE_ARCHITECTURE.md`.


### P0 — Nexus bootstrap runtime fallback

The Nexus bootstrap MUST remain zero-touch until a genuinely irreducible human authorization gate is reached.

- If a discovered system `npx`/Wrangler launcher fails its bounded version probe, BCP MUST automatically attempt the pinned managed portable runtime before entering a human hold.
- The managed fallback SHOULD invoke portable `node.exe` with npm's `npx-cli.js` directly so bootstrap correctness does not depend on a Windows `.cmd` wrapper.
- System and managed probes MUST remain bounded, retry/backoff aware, low-data, secret-safe and externally diagnosable through sanitized receipts.
- A runtime-probe failure MUST NOT require the user to install Node/Wrangler manually, re-enter the Telegram token/chat identity, run PowerShell, or shuttle ZIPs.
- `DEFAULT_PAID_SPEND = 0 USD` remains mandatory.
- Successful CI proves only the candidate implementation. FIELD promotion still requires fresh resident runtime readback and a real Nexus/Telegram round-trip.
- Cloudflare account/browser authorization, when first genuinely required by a functioning Wrangler runtime, remains an explicit one-time human gate and MUST NOT be bypassed.


Canonical Nexus field gate:
`docs/BCP_NEXUS_FIELD_GATE.md`.

The Nexus implementation is not ACTIVE/FIELD_VERIFIED merely because CI passes. Promotion requires a real home-WiFi health and Telegram round-trip with direct PC->Telegram allowed to remain degraded.


## P0 — Mission autonomy and observable execution

Requirement ID: `P0_MISSION_AUTONOMY_AND_OBSERVABLE_EXECUTION`.

A mission MUST be persisted before significant work. Long work is decomposed into bounded durable micro-sprints with explicit context resolution, dependency plan, local deterministic work, optional qualified worker dispatch, structured result, deterministic validation, authorized idempotent mutation, receipt/readback, checkpoint and next uncommitted action.

Chat is not canonical state. Worker processes and model sessions are replaceable. A committed effect is never replayed. External interruption, network loss or worker replacement is nonterminal when a durable checkpoint exists.

Every mission exposes an append-only observable event log and the fields `current_step`, `last_committed_step`, `next_step`, `last_progress_at`, `worker/component`, `receipt/evidence`, `status` and `failure/hold reason`. Progress percentages may describe only finite externally verifiable plan steps; private model reasoning is never represented as progress.

The scheduler is local-first. Hashing, state lookup, dependency resolution, known-error lookup, queue replay, tests and checkpointing do not consume model quota merely because a model is available. Provider use is allowed only through the Model Broker policy and `DEFAULT_PAID_SPEND = 0 USD` remains a hard invariant.

Telegram is a human-first cockpit: `/status` is compact, `/details` technical, `/where` reports the durable execution pointer, and `/tail` reports recent observable events. Spontaneous notifications are reserved for meaningful checkpoints, blocks, human decisions or completion.

The field topology remains unchanged: PC-WORKER and dedicated B-EDGE normally use home Wi-Fi; the current phone is a human terminal only. Direct PC-to-Telegram delivery is not a mandatory path.


## P0 — Cockpit humain de progression vérifiable

- La vue Telegram normale est non technique ; les détails Git/PR/SHA sont relégués à `/details`.
- Chaque mission bornée expose des micro-étapes observables ; un pourcentage n’est affiché que lorsque le dénominateur réel est connu.
- Le cockpit expose la dernière preuve durable, son âge, l’étape actuelle et la prochaine étape.
- Le silence n’est jamais assimilé automatiquement à un blocage ChatGPT.
- Les changements d’état utiles sont poussés automatiquement sans spammer les états inchangés.
- Les contraintes RDC restent P0 : faible débit, intermittence, données mobiles coûteuses, reprise locale, B-EDGE et Nexus.
- Aucun automate ChatGPT/Work planifié n’est requis pour cette surveillance.

## P0 — Human-visible mission presence and Telegram cockpit V3

BCP MUST provide a non-technical, durable mission-presence surface that remains useful when the ChatGPT UI is delayed, interrupted or ambiguous.

Active requirements:
- one editable live Telegram mission card per active mission rather than repeated duplicate status messages;
- medium-length plain-language status with current step, last completed step, next expected step, explicit user action, last proof-of-life timestamp/age and delivery lag;
- truthful progress bar and percentage only when a finite persisted plan denominator exists; otherwise show step position without invented percentage;
- normal view hides raw PR/SHA/workflow/fence identifiers and exposes them via `/details`;
- repeated zero spend is omitted from the normal view and surfaced only when financially relevant or requested;
- one bot multiplexes multiple projects/missions/conversation sources by default;
- resident progress presence comes from BCP Mission Event Journal, heartbeats and receipts, not hidden ChatGPT reasoning;
- local presence/update timers MUST NOT use ChatGPT scheduled automations or consume Work quota;
- optional progress-card images are low-data, cached and not heartbeat-driven;
- PC, B-EDGE, Nexus/remote ingress and durable evidence freshness are independently observable;
- user action is always explicit as AUCUNE / REQUISE / OPTIONNELLE;
- updates are event-driven, qualified, hash-pinned and as automatic as the OS permits.

Canonical detailed requirement:
- `docs/TELEGRAM_HUMAN_COCKPIT_V3_AND_MULTI_MISSION_REQUIREMENTS.md`

Implementation candidate on 2026-09-19:
- Telegram companion `2026.09.19-human-cockpit-v3` implements `/missions`, fresh B-EDGE presence, explicit human-action/timing fields, low-noise transition alerts, and one editable direct-Telegram live card;
- Nexus `0.1.4` adds persistent D1 live-card state plus `/v1/device/live-card`, using Telegram `editMessageText` with send fallback;
- this is CI-qualified candidate work until merged and then proven by field readback; it is not yet claimed FIELD_VERIFIED.


## P0 — Telegram Human Cockpit V4: interactive controls and portable reports

This is an additive refinement under SPEC_REFRESH_CURRENT_THEN_MERGE_REFINE_PRESERVE. It preserves all V3 truthfulness, low-data, single-bot, Nexus, update, security and non-ChatGPT-automation requirements.

The normal Telegram mission surface MUST now support progressive disclosure through a stable read-only inline control set:
- **Actualiser** -> current evidence-based status;
- **Où ?** -> exact durable execution pointer;
- **Missions** -> recent/active mission view;
- **Détails** -> technical evidence;
- **PDF suivi** -> compact human-readable status export;
- **PDF technique** -> deeper diagnostics/evidence export.

Requirements:
- button callbacks are accepted only from the allowlisted private chat and acknowledged immediately;
- routine state updates edit one live card rather than produce duplicate message spam;
- percentages remain forbidden unless the persisted finite denominator is real;
- the normal view uses medium-length plain French and stable visual hierarchy;
- raw Git/PR/SHA/workflow/fence identifiers remain in the technical view unless required for a real decision;
- exported reports are generated from the same durable evidence as the card, are timestamped snapshots, contain no secret, and never become canonical state;
- report generation uses a lightweight dependency-free path and is explicit/milestone-driven rather than heartbeat-driven;
- Nexus MAY cache the latest sanitized human and technical report text so a PDF request can be served while direct PC->Telegram egress is degraded;
- report/PDF failure never blocks local mission execution;
- optional image-card UX remains separately gated and must be low-data/cached if implemented;
- typed commands remain available as fallbacks: `/report` and `/reporttech`;
- no ChatGPT scheduled automation is introduced.

Canonical detailed requirement:
- `docs/TELEGRAM_HUMAN_COCKPIT_V4_INTERACTIVE_EXPORTS.md`

Implementation candidate on 2026-09-19:
- direct Telegram adds inline callbacks, immediate callback acknowledgement, live-card controls and dependency-free PDF delivery;
- Nexus adds callback routing, report cache and PDF delivery at the webhook edge;
- CI must prove syntax, self-tests, D1 schema and secret/read-only guards on the exact candidate commit;
- FIELD_VERIFIED remains false until real Kinshasa Telegram/Nexus button and PDF round-trips succeed.


## P0 — Human-first Telegram cockpit V5

The Telegram cockpit MUST expose concrete externally verifiable micro-actions rather than vague activity names.

A micro-action is a bounded human-readable action such as reading a named file, checking a commit, starting a defined test, reading a test result, modifying a specific file, verifying a receipt/hash, or committing a durable checkpoint.

When BCP has a persisted finite mission plan:
- the normal view MUST show current, last completed, and next micro-action using the plan's human labels;
- the progress bar and percentage MUST equal verified steps / total persisted steps;
- no time-based or model-internal percentage may be invented;
- the user MUST be able to open a numbered Micro-actions journal backed by durable mission events;
- raw PR/SHA/run identifiers stay behind the technical details view.

The human PDF MUST include the plan and recent micro-actions, not merely copy the status card. The technical PDF MUST additionally expose mission metadata, worker/component, evidence/receipt references, hold reason, plan and event journal while redacting secrets.

Automatic cockpit presence/update remains resident/event-driven BCP/B-EDGE/Nexus behavior. It MUST NOT use ChatGPT scheduled monitoring automations.

Canonical detailed delta:
`docs/TELEGRAM_HUMAN_COCKPIT_V5_MICRO_ACTIONS_AND_PROGRESS.md`.

## P0 — Field-ecosystem preflight before promotion (R13)

This is additive under `SPEC_REFRESH_CURRENT_THEN_MERGE_REFINE_PRESERVE`. It converts recurring field incidents into mandatory pre-promotion regression obligations.

Before a BCP/Telegram/B-EDGE/Nexus release may be promoted, CI MUST run a deterministic field-ecosystem preflight shaped around the actual deployment constraints:
- Windows 11 PC with approximately 4 GB RAM and frequent high memory pressure;
- serialized/low-memory Android build settings and explicit `PC_MEMORY_PRESSURE` / `WAITING_FOR_PC` behavior;
- Kinshasa home-Wi-Fi where DNS may resolve while direct Telegram TCP/443 egress times out;
- selective Nexus HTTPS control-plane fallback without moving bulk traffic to mobile data;
- intermittent/weak connectivity with bounded retry/backoff, watchdogs, idempotency and offline queueing;
- Telegram single-receiver discipline so a prior HTTP 409 `getUpdates` conflict cannot be normalized as healthy multi-poller operation;
- Nexus runtime regression where system `npx`/Wrangler may exit 1 with empty stdout/stderr;
- automatic pinned portable Node + direct `node.exe -> npx-cli.js` fallback before any human runtime-install gate;
- zero-dollar, secret-safe, data-saver and unchanged-version-zero-download invariants;
- exact release version/hash coordination between CURRENT, Windows BCP, B-EDGE and Nexus.

The preflight MUST be network-independent for deterministic regression checks. Real Internet/Cloudflare/Telegram round-trips remain FIELD gates and MUST NOT be fabricated by CI.

A green generic syntax/self-test alone is insufficient when a known field failure mechanism is not exercised. Every newly classified field failure MUST either become an executable regression test or an explicit machine-checkable contract guard before the next promotion.

Canonical implementation:
- `tools/validate_field_ecosystem.py`
- `.github/workflows/field-ecosystem-preflight.yml`

Promotion evidence is bound to the exact tested commit SHA and remains subject to the Git writer lease/integration fence.

## P0 — Telegram cockpit field liveness and remote-operability (R14)

This requirement is additive and preserves all prior Telegram/BCP/Nexus requirements.

The Telegram cockpit MUST NOT rely on the user to detect a dead or disconnected poller by repeatedly tapping buttons. The resident stack MUST externalize machine-readable Telegram worker health and make that health observable through the existing BCP external heartbeat/Drive path.

Required invariants:
- every active Telegram transport worker publishes a small secret-free health record containing mode, process id, state, latest successful poll time, bounded failure count and the most recent callback receipt/handling timestamps;
- button callbacks such as **Actualiser** produce a machine-readable callback receipt before/after dispatch so a silent user-visible failure can be distinguished from an unreceived update;
- BCP mirrors Telegram worker health into `BCP_RUNTIME_LATEST.json`; the user is not the telemetry bus;
- a resident watchdog may restart the companion only when health is genuinely stale, with a restart cooldown to prevent loops;
- ordinary network timeout/backoff is NOT treated as a dead process, because the worker continues updating health while degraded;
- single-receiver discipline remains mandatory; duplicate pollers must be suppressed and HTTP 409 conflicts must never be normalized as healthy;
- direct PC -> Telegram remains opportunistic on the Kinshasa home-Wi-Fi path; Nexus remains the durable remote transport when direct TCP/443 is unavailable;
- remote work must continue while the user is away from home whenever BCP/Nexus/Drive evidence and bounded jobs are sufficient; only a genuine human authorization gate may require user presence.

Canonical implementation line:
- BCP server 0.6.8 or later;
- Telegram cockpit V6 or later;
- external heartbeat fields `telegram_companion_*`;
- resident stale-health watchdog with bounded restart cooldown.

## P0 — Human-readable progress, fine micro-actions and complete reports (R15)

This requirement is additive. The Telegram surface is a human operational dashboard, not a dump of internal state names.

### Human-first live card
- The visible title is an interactive monitoring concept such as **Automate de suivi BCP**, not a bare internal component label.
- Raw strings such as `NOT_OBSERVED`, workflow implementation names and internal hold codes belong in technical reports, not the primary human card.
- If no human action is required, the card omits the user-action row instead of displaying a redundant `AUCUNE`.
- PC, B-EDGE, Drive, Nexus and CI states are translated into clear human sentences.

### Fine-grained micro-action model
A micro-action is atomic and observable. Examples include reading/opening a file or PDF, checking a workflow, reading logs, changing one file, calculating a hash, launching one test, checking one test result, committing one mutation, performing one readback, or validating one receipt.

The system MUST support a dynamic micro-action forecast. When the exact count is not known, it MAY estimate a total and progress, but MUST mark it explicitly with **≈**. The forecast is planning telemetry, not proof; it may be recalculated as work expands or contracts. Confirmed completed actions remain evidence-backed and distinct from forecast work.

### Two separate progress concepts
- **Mission progress estimate**: ≈done/total fine micro-actions for the current user objective.
- **Ecosystem health**: independent percentage derived from observable PC/BCP, B-EDGE, Drive, CI and Nexus availability/qualification signals.

These values MUST NOT be conflated.

### PC power and memory telemetry
- The resident Windows heartbeat SHOULD expose dependency-free RAM load, available memory, AC/battery source, battery percentage when available, and a battery-critical flag.
- The human card translates these signals into states such as **PC allumé · secteur · RAM 88%** or **batterie critique**, while raw values stay available in technical reports.
- This telemetry must remain lightweight enough for the 4 GB Windows target.

### Automatic refresh and intermittent connectivity
- While a transport is available, the live card refreshes automatically on a bounded adaptive interval; the manual refresh button is a convenience, not the primary update mechanism.
- Offline periods retain local durable state and do not erase progress. Reconnection resumes synchronization automatically.
- Automatic refresh must remain data-aware and avoid unnecessary large transfers.

### PDF suite
Telegram MUST expose at least four complementary generated PDFs:
1. human situation / executive follow-up;
2. devices, network and transports;
3. objective, stages and fine micro-actions;
4. technical dossier / audit.

Each report is generated from current durable evidence and is designed to be substantially more complete than the compact live card.
