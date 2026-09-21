# API / BCP — Cahier des charges canonique courant

Status: CANONICAL PRODUCT REQUIREMENT
Revision: 2026-09-21-R67
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

## P0 — Offline mission sentinel, stall detection and bounded resume (R16)

The product MUST remain operationally understandable when the user is away from the PC, the PC loses Internet, Telegram is unreachable from the home Wi-Fi, or the interactive ChatGPT conversation stops producing external evidence.

### Truth boundary
BCP MUST NOT claim that a standard ChatGPT UI conversation can literally click its own Continue button or execute indefinitely in the background. Instead:
- durable state/checkpoints remain authoritative outside chat;
- BCP detects absence of new **external proof**, not hidden model state;
- BCP creates a durable resume intent that qualified local/edge/model-broker workers can consume when available;
- Telegram reports what was detected/requested, without inventing hidden ChatGPT activity.

### Stall detector
For each nonterminal mission, BCP tracks the last **non-watchdog evidence anchor**. A watchdog-generated retry event MUST NOT reset that anchor or masquerade as real task progress.

Default policy:
- stale threshold: approximately 10 minutes without a new non-watchdog proof;
- bounded automatic resume requests: maximum 3 per unchanged evidence anchor;
- increasing cooldowns: approximately 5 min, 15 min, then 60 min;
- a new genuine proof resets the retry epoch;
- terminal missions are ignored;
- explicit human authorization/approval/login/platform gates suppress blind auto-resume.

### Durable resume intent
A resume request MUST be:
- atomic and persisted locally before acknowledgement;
- assigned a deterministic idempotency key derived from mission + evidence anchor + next step;
- mirrored to the existing control/Drive plane when available;
- replay-safe across reboot/network loss;
- zero-paid-spend by default;
- consumed only by a qualified worker/orchestrator; persistence of the request is not itself proof of task completion.

### Telegram
The cockpit MUST expose a real **▶️ Continuer** control. It creates the same durable resume intent as the automatic watchdog and MUST deduplicate an already-pending request.

The cockpit SHOULD proactively notify, with deduplication:
- stalled progress detected;
- automatic resume requested;
- retry budget exhausted/escalated;
- genuine human gate reached.

### Two-sentinel target
The PC BCP process is the local sentinel while the PC is running. The dedicated old-phone B-EDGE node is the target secondary sentinel for periods where the PC is off/unreachable:
- B-EDGE preserves mission/outbox/checkpoint metadata;
- it can receive remote control through the qualified Nexus/Telegram path;
- it does not invent PC progress;
- it queues heavy PC work as WAITING_FOR_PC;
- when the PC returns, state is reconciled by idempotency/revision/fencing before execution.

No duplicate Telegram poller is introduced.

## P0 — B-EDGE independent secondary sentinel (R17)

The dedicated old Android phone MUST become the independent continuity sentinel for periods where the PC is absent.

Implementation requirements:
- durable per-project sentinel state lives in Room/SQLite, never process-only RAM;
- WorkManager performs a low-duty periodic reconcile (15-minute Android minimum baseline with flex), so process death/reboot does not erase monitoring;
- PC offline is a valid state, not a worker failure/retry storm;
- one transient failure remains distinct from confirmed `PC_UNAVAILABLE_RECOVERY`;
- confirmed PC absence requires at least two failures plus a stale last-success interval;
- the phone creates a stable durable `resume_request_id` / resume-pending state while PC work is unavailable;
- PC-only jobs remain `WAITING_FOR_PC`; B-EDGE MUST NOT fabricate completion;
- alert emission is deduplicated and bounded (minimum one-hour repeat cooldown for an unchanged PC-loss epoch);
- when the PC returns, reachability state reconciles to `PC_AVAILABLE` and stale resume-pending state is cleared only by an observed successful PC contact;
- Room schema upgrades MUST use an explicit migration; destructive migration is forbidden for canonical/offline state.

Remote notification while the PC is completely offline requires an independent qualified egress path from B-EDGE. The target path is Nexus/device-authenticated outbound HTTPS. Until that path is provisioned and field-qualified, B-EDGE MUST persist the alert/outbox locally and MUST NOT claim that Telegram was notified.

A source build or unsigned APK is not a deployable field release. The existing installed APK remains authoritative until a same-identity signed candidate is produced, hash/signature verified, and then installed through the normal Android human gate if the OS requires confirmation.

## P0 — Portable Node lifecycle parity and field-shaped CI (R18)

This requirement is additive and preserves R17.

A managed portable runtime MUST be self-contained not only for the top-level executable but also for package-manager child/lifecycle processes.

The Nexus bootstrap MUST:
- place the pinned portable Node directory first in the bootstrap process `PATH` before any npm installation;
- prove from a child shell that `node --version` resolves to the exact pinned portable version before running npm lifecycle scripts;
- fail with a machine-readable runtime-preparation class if that binding cannot be proven;
- keep npm cache persistent and bounded retries/data-saver semantics;
- invoke the pinned Wrangler JS entry point directly through the same pinned `node.exe`;
- never require the user to install Node/Wrangler manually to compensate for this class of failure.

CI MUST explicitly remove the hosted runner's globally installed Node from the relevant PATH and prove that Wrangler plus lifecycle dependencies such as esbuild can install and execute using only the pinned portable runtime. A green test that accidentally relies on the CI image's global Node is invalid evidence.

Field incident bound to this requirement:
- Nexus 0.1.9 reached the resident PC but npm failed in the `esbuild` lifecycle path while the exact same install passed on GitHub;
- the correction is Nexus 0.2.0 with explicit portable-child-runtime binding.

## P0 — Telegram Human Ops Cockpit V9 / R20

This requirement is additive and preserves R18.

The Telegram human surface MUST prioritize **orientation before detail**. The top of the live card MUST expose one human attention state:
- CRITIQUE;
- ACTION REQUISE;
- À SURVEILLER;
- EN COURS;
- STABLE.

The headline is derived only from observable evidence and declared human gates. Raw internal state strings remain behind technical views.

### Return-after-absence UX
The cockpit MUST provide:
- **Depuis ma visite**: durable changes since the previous human interaction;
- **Pourquoi ?**: observable reasons behind the current attention state;
- **Radar**: explicitly predictive near-term operational risks, never represented as proof.

### Forecast confidence
Every approximate micro-action forecast SHOULD carry a confidence label. Confidence is based on plan/evidence structure and MUST NOT convert approximate work into confirmed progress.

### Notification lifecycle
Notifications MUST be transition-driven rather than heartbeat-driven:
- repeated unchanged conditions are deduplicated;
- related mission events are grouped;
- CRITIQUE / ACTION / À SURVEILLER may notify on meaningful transition;
- when such a state clears, one recovery notification is emitted;
- monitoring/evaluation continues even when notifications are muted.

### Quiet mode
A bounded local quiet mode MUST suppress routine notifications while allowing genuine critical/human-action gates through. Quiet mode MUST NOT disable watchdog evaluation, durable state, or recovery logic.

### Optional Cockpit+ Mini App
A richer Telegram Mini App MAY be added after the Nexus field gate, but it is never a critical dependency. The plain bot/card interface remains the mandatory low-data fallback.

A Mini App MUST:
- be mobile-first and low-resource;
- adapt optional animation/effects to device performance capability;
- validate Telegram initialization data server-side;
- contain no embedded operational secret;
- treat client storage as UI/cache state, not canonical project state;
- remain zero-paid-spend by default;
- degrade cleanly to the standard bot surface.

Canonical detailed requirement:
- `docs/TELEGRAM_HUMAN_OPS_COCKPIT_V9_R20.md`

## P0 — Telegram Rich Cockpit V10 / R21

This requirement is additive and preserves R20.

BCP SHOULD use Telegram Bot API Rich Messages when available to improve the human operations surface, but Rich Messages MUST NOT become a critical dependency.

### Preferred rich presentation
The primary live card MAY use structured Rich Message content with:
- human attention heading;
- compact table for objective, ≈progress, forecast confidence, proof age and human gate;
- current/next action;
- collapsible explanation and subsystem details;
- styled callback buttons.

### Styled control semantics
Semantic button style MUST preserve meaning:
- `success` for healthy/safe action;
- `primary` for normal navigation/inspection;
- `danger` only for a real critical/human-action state;
- `link` for informational navigation when appropriate.

Exact client colors MUST NOT be assumed; style is semantic.

### Actionability-aware notifications
- CRITIQUE and genuine ACTION REQUISE states may generate normal notifications.
- Automatic recovery/resume notices SHOULD be delivered silently when supported.
- À SURVEILLER remains visible in the cockpit/Radar and SHOULD NOT behave like a paging alert while safe automation remains available.
- Notification muting never disables evaluation or durable recovery.

### Mandatory V9 fallback
For every rich send/edit:
1. try the rich API;
2. on sanitized failure, fall back immediately to the V9 plain-text card and InlineKeyboard;
3. do not require user intervention;
4. do not lose the live-card cursor/fingerprint.

DIRECT_TELEGRAM and NEXUS MUST expose the same functional controls. Nexus carries both plain text and optional rich HTML and performs the same rich-first/fallback decision at the edge.

### Four-report transport parity
Nexus MUST support the same four report snapshots as direct mode:
- summary;
- devices/network;
- mission/micro-actions;
- technical audit.

Older summary+technical publishers remain accepted during rolling transition.

### Resource/cost/security constraints
- normal rich payload target <= 30000 characters;
- no media in the default card;
- edit one live card rather than spam;
- no heavy local browser/runtime;
- `allow_paid_broadcast` MUST NOT be enabled;
- rich content is escaped/redacted and MUST contain no secret;
- callback data remains allowlisted/bounded;
- DEFAULT_PAID_SPEND=0 USD.

### Truth boundary
Rich formatting changes presentation only. Approximate progress, prediction confidence, risk radar and durable proof MUST remain semantically distinct. Rich drafts, if later introduced, are transient UX and never evidence of work.

Canonical detailed requirement:
- `docs/TELEGRAM_RICH_COCKPIT_V10_R21.md`

## P0 — Telegram Attention Lifecycle V11 / R22

This requirement is additive and preserves R21 Rich Cockpit behavior.

### Acknowledge without hiding reality
The human cockpit MUST expose a **J’ai vu** acknowledgement for the current attention signal. Acknowledgement:
- records only that the user has seen the current signal/root reason;
- suppresses repeat interruption for that exact unchanged signal;
- MUST NOT mark the underlying incident resolved;
- MUST NOT suppress a new root cause, worsened severity, or a new human-action gate;
- is cleared after stable observable recovery, so a later recurrence of the same root cause can notify as a new incident;
- remains local/durable and secret-free.

### Anti-flapping
Recovery notifications MUST be damped so transient oscillations do not produce repeated “incident/recovery” chatter.
Default recovery stability gate:
- at least 2 consecutive observations, OR
- at least 60 seconds continuously in the recovered state.

CRITICAL and genuine ACTION REQUISE transitions remain immediate.

### Notification budget
Routine noncritical notifications MUST be rate-bounded independently of monitoring:
- default rolling window: 30 minutes;
- default routine interruption budget: 3;
- CRITICAL and genuine human-action gates bypass this budget;
- WATCH remains dashboard/Radar-first and does not page while safe automation exists;
- budget exhaustion suppresses notification delivery only, never evaluation, watchdogs, state persistence, or recovery;
- budget is consumed only after positive notification delivery;
- a transport failure MUST NOT mark an alert as delivered, and critical/action-required alerts remain retryable after reconnect.

### Operational semantics
The cockpit MUST distinguish:
- detected;
- acknowledged by the human;
- being handled automatically;
- recovered/resolved by observable evidence.

Acknowledgement is never evidence of recovery.

### External basis
This design intentionally follows established incident-management practice: alerts should be actionable, deduplicated/grouped, and resistant to flapping/noise. The implementation remains zero-dollar and does not depend on paid alerting services.

## P0 — Conversation Delivery Ledger & Telegram Inbox V12 / R23

This requirement is additive and preserves R22.

BCP MUST distinguish **work completion** from **user-visible message delivery**. A durable mission/checkpoint or generated response is not proof that the ChatGPT mobile/web UI displayed the answer.

### Durable conversation ledger
BCP maintains a bounded local SQLite ledger for BCP-aware conversations. Each mirrored message records:
- bounded stable conversation id and human alias;
- source kind (CHATGPT_UI, CHATGPT_PC, OPENAI_API, BCP_AGENT);
- monotonic sequence and idempotent message key;
- role and redacted/bounded text;
- generated/mirrored timestamps;
- content hash and evidence class;
- linked mission when available;
- explicit delivery state.

Allowed delivery semantics include:
- GENERATED;
- MIRRORED_BCP;
- TELEGRAM_SENT;
- USER_SEEN;
- CHATGPT_UI_DELIVERY_UNKNOWN;
- DELIVERY_GAP_DETECTED.

The UI MUST render uncertainty honestly. `CHATGPT_UI_DELIVERY_UNKNOWN` MUST NOT be translated to delivered or failed.

### Telegram conversation inbox
The main cockpit exposes **💬 Conversations**. It shows the most recent BCP-aware conversations X/Y/Z, latest activity, delivery state, and bounded previews of recent messages.

A detailed conversation view MUST remain bounded/low-data and use compact identifiers compatible with Telegram callback limits. DIRECT_TELEGRAM and NEXUS expose equivalent access.

### ChatGPT UI truth boundary
BCP MUST NOT imply continuous access to arbitrary private ChatGPT UI history. Standard ChatGPT UI messages enter this ledger only through supported explicit receipts/bridges. OpenAI API / BCP-agent conversations may mirror through their supported APIs/clients.

### Privacy
- full conversation bodies remain local to BCP by default;
- normal GitHub release metadata and external runtime telemetry MUST NOT contain user conversation bodies;
- credential/token patterns are redacted before ledger persistence;
- message text and retention are bounded;
- the ledger is operational redundancy, not an account-history export.

### Delivery-gap target
When durable work evidence exists but expected downstream message-delivery evidence does not appear within a bounded interval, BCP SHOULD raise a deduplicated delivery-gap signal. This signal is observational and MUST NOT infer hidden ChatGPT model/UI state.

### Bounded interactive cadence
During active human development sessions, checkpoint/report cadence SHOULD target approximately 25 minutes of useful work, reserving roughly the final minute for durable checkpoint/email delivery so long tool/reasoning sequences do not leave the user unable to distinguish work, network/UI loss, or interruption. This is not a ChatGPT scheduled/background automation.

Canonical detailed requirement:
- `docs/CONVERSATION_DELIVERY_LEDGER_AND_TELEGRAM_INBOX_R23.md`

## P0 — Delivery Gap Detector / R24

This requirement is additive and preserves R23.

BCP MUST derive a **delivery gap** when an assistant message has a durable BCP receipt but no positive downstream reading evidence after a bounded interval. Default threshold: 5 minutes.

The detector:
- operates only on durable BCP receipts;
- MUST NOT infer hidden ChatGPT model state, platform state, or whether the ChatGPT app actually rendered the answer;
- MUST clear the derived gap once positive `USER_SEEN` evidence exists;
- MUST remain idempotent and restart-safe because the gap is derived from durable message state;
- MUST expose an authenticated `/v1/conversations/gaps` read surface;
- MUST surface active gaps in Telegram as a WATCH-level attention signal, subject to the existing acknowledgement, anti-flap and notification-budget rules;
- MUST keep message bodies local by default and avoid copying full conversation bodies into GitHub or ordinary external telemetry.

A delivery gap is therefore evidence of **missing positive delivery/reading proof**, not proof of a ChatGPT failure.

The Telegram Conversations view MUST show a human-readable “Réponse sauvegardée mais lecture non confirmée” indicator with age when the threshold is crossed. R53 supersedes the older “Réponse potentiellement manquée” display wording because missing seen evidence is not proof that generation or delivery failed.

Field acceptance additionally requires:
- no gap before threshold;
- gap after threshold when an assistant receipt remains unseen;
- automatic disappearance after explicit seen evidence;
- no duplicate notification for an unchanged gap episode;
- no false “delivered” claim when the UI delivery remains unknown.

## P0 — Conversation Receipt Bridge & Sequence Repair / R25

This requirement is additive and preserves R24.

BCP MUST provide a low-footprint local receipt bridge so supported local producers can feed the Conversation Delivery Ledger automatically without making the user or the ChatGPT UI the telemetry bus.

The bridge MUST:
- consume a bounded append-only local JSONL inbox incrementally;
- persist a cursor and survive process restart;
- preserve message-key idempotency;
- tolerate malformed lines without poisoning later valid receipts;
- treat producer sequence separately from BCP ingestion sequence;
- dynamically detect missing producer sequence ranges;
- automatically clear a sequence gap when late receipts arrive;
- expose synchronization gaps without claiming hidden ChatGPT failure;
- keep canonical conversation bodies local by default.

Telegram MUST surface sequence incompleteness as a human-readable WATCH signal in the Conversations view.

Canonical detail:
- `docs/CONVERSATION_RECEIPT_BRIDGE_AND_SEQUENCE_REPAIR_R25.md`

## P0 — Producer Watermark Sync & Receipt Acknowledgement / R26

This requirement is additive and preserves R25.

BCP MUST distinguish “all receipts currently seen” from “all receipts the producer reports having emitted”.

Supported producers MAY publish a durable high-water mark per conversation/session. BCP MUST compare this watermark with locally persisted producer-sequence receipts and derive COMPLETE / INCOMPLETE synchronization truth.

BCP MUST:
- persist producer watermarks and heartbeat timestamps;
- distinguish producer sequence from BCP ingestion sequence;
- detect both internal and tail gaps relative to the announced watermark;
- automatically clear gaps when late receipts arrive;
- write a local durable acknowledgement summarizing contiguous receipt progress;
- expose authenticated producer-sync readback;
- keep canonical conversation bodies local by default;
- never translate producer synchronization evidence into a claim that the ChatGPT UI displayed a message.

Telegram MUST show producer-sync completeness in the Conversations view.

Canonical detail:
- `docs/PRODUCER_WATERMARK_SYNC_AND_RECEIPT_ACK_R26.md`

### Interactive work cadence default

For active technical project work where this project context is available, use bounded work tranches targeting **25 minutes**, with a practical **24–25 minute** window before the durable checkpoint unless a real gate requires earlier return.

The cadence policy MUST NOT be treated as a background-execution promise: after ChatGPT responds, another invocation is required for the next ChatGPT tranche. Resident BCP components may continue independently where explicitly implemented.

Canonical policy:
- `.project-memory/INTERACTIVE_WORK_CADENCE_POLICY.json`

## P0 — ChatGPT-PC Local Flow Ledger Bridge / R27

This requirement is additive and preserves R26.

BCP MUST consume supported exact ChatGPT-PC conversation evidence directly from the local ChatGPT-PC flow ledger using read-only SQLite access, without mutating ChatGPT-PC runtime authority or requiring the user to relay screenshots/messages manually.

The bridge MUST:
- read only exact conversation-message event kinds with user/assistant roles;
- verify declared source text SHA-256 before import;
- use source event identity for idempotence;
- persist a local source cursor and import in bounded batches;
- fail open if ChatGPT-PC is unavailable;
- fail closed on a corrupt source row rather than skip past it;
- preserve the distinction between response existence and ChatGPT UI display;
- keep canonical message bodies local by default;
- expose bridge health/backlog in Telegram Conversations.

Canonical detail:
- `docs/CHATGPT_PC_LOCAL_FLOW_LEDGER_BRIDGE_R27.md`

## P0 — Evidence-Based End-to-End Cadence Telemetry / R28

This requirement is additive and preserves R27.

Interactive technical work MUST target approximately 25 minutes of useful work per normal tranche, with a practical 24–25 minute window unless a genuine human gate, safety/tool failure, or completed atomic action justifies earlier return.

BCP MUST NOT equate ChatGPT's displayed “thinking” duration with end-to-end user-visible latency.

Where durable timestamps exist, BCP MUST decompose latency into distinct evidence classes:
- user/request event -> assistant/product event;
- assistant/product event -> BCP mirror;
- BCP mirror -> explicit user seen acknowledgement;
- request -> explicit user seen acknowledgement.

Missing evidence MUST remain missing. An unsynchronized manual stopwatch is useful context but MUST NOT be used as an authoritative calibration sample.

Telegram conversation detail SHOULD expose the measured decomposition with an explicit “not measured” state when seen evidence is absent.

Canonical cadence policy:
- `.project-memory/INTERACTIVE_WORK_CADENCE_POLICY.json`

## P0 — Cloudflare OAuth Device-Flow Resilience / R29

This requirement is additive and preserves R28.

The one-time Nexus Cloudflare human authorization gate MUST prefer Wrangler OAuth Device Authorization when available, because it does not depend on the localhost callback path used by classic browser OAuth.

The bootstrap MUST:
- prefer `wrangler login --device`;
- keep classic `wrangler login` only as an automatic fallback;
- never ask the user to paste a Cloudflare API token into chat;
- preserve the existing no-secret logging contract;
- re-check `wrangler whoami --json` after authorization before any D1/Worker mutation;
- preserve idempotent deployment and single Telegram receiver ownership;
- remain zero-dollar and never select a paid plan automatically.

Wrangler 4.135.0 is pinned by this project and is newer than the provider's documented 4.119.0 minimum for device authorization.

If authorization expires or the user does not complete it in time, BCP records `HUMAN_AUTH_REQUIRED` and retries through the normal resident recovery path rather than inventing deployment success.

## P0 — Adaptive Nexus Human-Gate Manifest Watch / R31

This requirement is additive and preserves R30.

The normal resident update cadence remains data-saving and low-frequency. However, when Nexus is already blocked on a genuine `HUMAN_AUTH_REQUIRED` Cloudflare gate, BCP MUST use a lightweight manifest-only fast path so a newly qualified auth-resilience bundle is not delayed by the normal 30-minute update cycle.

The watcher MUST:
- poll only the small Nexus release manifest while the local Nexus state is `HUMAN_AUTH_REQUIRED`;
- use a 2-minute normal interval while that gate is active;
- perform no artifact download or relaunch when the bundle version is unchanged;
- launch the normal hash-pinned Nexus delivery path only when a different qualified bundle version is observed;
- back off on network failures up to 15 minutes;
- return to the normal long cadence outside the human-gate state;
- preserve zero-dollar, secret hygiene, idempotence, and single-receiver semantics.

This is an optimization of update detection, not a bypass of Cloudflare authorization.


## P0 — Independent Outbound Update Lanes / R34

This requirement is additive and preserves R31.

Fresh field telemetry from the resident Windows node showed that one outbound transport failure could leave the server update check in `CHECK_FAILED` while Telegram/Nexus convergence remained pending. Resident update orchestration MUST therefore isolate transport lanes so a failure in one remote endpoint does not suppress reconciliation attempts for the others.

BCP MUST:
- treat SERVER, TELEGRAM_COMPANION and NEXUS as independent update/reconciliation lanes;
- preserve hash verification, allowlists, rollback and zero-dollar policy in every lane;
- classify bounded outbound failures into machine-readable transport classes, including timeout, DNS resolution, TLS/certificate failure and connection refusal where observable;
- persist a bounded sanitized error detail and next retry delay without secrets;
- use bounded retry/backoff under weak connectivity rather than tight loops;
- preserve the normal low-data cadence when healthy;
- keep companion reconciliation eligible even when the server manifest check fails;
- never infer that a provider human-auth gate is resolved merely because transport recovers;
- never replay a completed install merely because convergence telemetry is delayed.

The target BCP release for this requirement is 0.7.8. Windows installer, acceptance runner, server manifest and CURRENT metadata MUST remain version-aligned to prevent recurrence of the R32 drift class.


## P0 — Recovery Launcher Bridge / DriveFS Separation / R38

This requirement is additive and preserves R34.

### Field evidence
A real Windows 11 / B-EDGE recovery sequence on 2026-09-20 exposed a compound failure:
- B-EDGE left the home LAN and later rejoined the same Wi-Fi;
- after PC reboot/unlock, Windows Firewall blocked the Python-hosted BCP listener until Private-network consent was granted;
- B-EDGE then reconnected to the same paired PC without re-pairing;
- the ChatGPT-PC Startup fallback failed with Windows Script Host error `800A0408` at line 1 / character 1 because the generated VBS was UTF-8 with BOM;
- the cloud recovery target was updated while the PC-local Control Folder remained stale, causing `recovery_target_not_active`;
- prior recovery logs also proved that temporary-file + `os.replace` assumptions against `G:\\Mon Drive` can fail with `OSError: [Errno 22] Invalid argument`;
- Cloudflare classic browser OAuth produced a localhost callback failure while a separate device-authorization page existed. These are distinct auth paths and neither is proof that the other succeeded.

### Mandatory architecture
BCP/ChatGPT-PC MUST distinguish:
- local NTFS state, suitable for atomic critical state transitions;
- provider-synchronised DriveFS state, suitable for replicated exchange but not assumed to provide identical rename/fsync semantics;
- cloud provider state;
- human browser authorization state.

Critical local recovery truth MUST NOT depend on a successful atomic replace directly on DriveFS.

BCP MUST provide a least-privilege local recovery-launcher bridge when:
- the ChatGPT-PC runtime exists locally;
- the Drive-backed recovery target is missing/stale/inactive, or its package has not yet synchronised;
- the known local Recovery Startup launcher can be reconstructed from the existing local runtime.

The bridge MUST:
- reconstruct only the known `ChatGPTPC_RecoveryPlane.vbs` launcher;
- write it as UTF-16 and perform local readback;
- launch the existing local recovery runner consolelessly;
- require no UAC elevation, no generic process kill, no credential copy, and no network-policy broadening;
- record a machine-readable local receipt;
- return `BRIDGE_STARTED` semantics rather than claiming the target ChatGPT-PC release installed;
- preserve the later hash-pinned recovery-target/package verification before any actual release promotion.

### Provider-synchronised file semantics
When DriveFS cannot support the local atomic-write primitive:
- preserve canonical local evidence first;
- mirror/synchronise provider state best-effort;
- surface `CLOUD_MIRROR_HOLD` or equivalent rather than failing the local recovery transaction;
- never use provider-synchronised folders as the sole authoritative location for watchdog/lease/critical recovery state.

### Cloudflare auth truth
Device authorization is preferred. Classic localhost callback failure is diagnostic evidence only.
After any human consent, Wrangler `whoami --json` or an equivalent provider-authenticated readback is mandatory before deployment is declared authorized.

Target server release for this requirement: BCP 0.7.9.


## P0 — Zero-touch re-entry, local authority and human-gate singularity / R40

This requirement is additive and preserves R38/R39.

### Operating environment is nominal, not exceptional
The supported field baseline includes Windows 11 with 4 GB RAM, sustained memory pressure above 90%, rapid thermal rise, unstable AC/network, Android B-EDGE leaving and later rejoining the home Wi-Fi, and periods where Google Drive for desktop is stopped, stale or disconnected. Correctness must survive these states without restart storms, duplicate heavy work, repeated user taps or ambiguous success claims.

### Local-first critical state
Critical recovery, watchdog, lease, active-release pointer and command-consumer state MUST have a canonical local NTFS copy under the app-owned local state root. A provider-synchronised filesystem such as DriveFS is a replication/exchange transport only.
- No critical transaction may require atomic rename/fsync semantics on a virtual Drive mount.
- Drive mirror failure is a separately observable CLOUD_MIRROR_HOLD and must not roll back a locally successful recovery.
- Fresh LAN/B-EDGE machine readback outranks a stale Drive heartbeat for current field truth.
- Cloud mirrors remain useful for remote readback, audit and recovery payload distribution, but staleness must be explicit.

### Cloudflare human gate singularity
For supported Wrangler versions, OAuth device authorization is the sole automatic Cloudflare login path.
- No automatic fallback to classic localhost:8976 OAuth is permitted after device flow starts or expires.
- Device-code non-completion/expiry remains HUMAN_AUTH_REQUIRED.
- A later explicit qualified attempt generates a fresh code.
- Authorization is not considered complete until a post-login authenticated `whoami --json` readback succeeds.
- No API token, Telegram token or device secret is copied through chat.

### B-EDGE re-entry scheduling
The Android periodic sentinel remains at the platform-valid 15-minute minimum. Faster recovery MUST use bounded unique one-shot work triggered by foreground/network-return signals rather than sub-15-minute polling.
The next signed B-EDGE release MUST:
- converge all production reconciliation calls onto one worker implementation;
- eliminate the duplicate legacy/new EdgeReconcileWorker policy split;
- require a connected-network constraint for one-shot reconciliation;
- use explicit bounded exponential backoff;
- coalesce duplicate immediate requests under one unique-work key;
- trigger a one-shot reconciliation on Wi-Fi availability while the app process is alive;
- preserve the 15-minute periodic safety net if the process is absent.

### Android release identity
A changed B-EDGE source MUST NOT be published under an already-distributed versionCode/versionName or old APK hash. Source candidate, signed artifact, version metadata, certificate continuity and Drive CURRENT readback must agree before publication. The user must not be asked to uninstall or re-pair for an ordinary in-place update.

### Resource-pressure invariant
Recovery/update/orchestration paths on the 4 GB PC must serialize heavy work, bound queues/logs, prefer local disk streaming over RAM aggregation, back off under repeated failure, and yield non-critical work under high memory/thermal pressure. Heartbeat liveness alone is not proof of forward progress.


## P0 — DriveFS Mirror Fail-Open / R43

This requirement is additive and preserves R40-R42.

Provider-synchronised telemetry/control folders are projections, not the transactional authority for local recovery/update actions.

BCP MUST:
- keep local transaction state authoritative;
- treat DriveFS/provider mirror publication as best-effort;
- record a bounded local `CLOUD_MIRROR_HOLD` receipt when a mirror write fails;
- never convert a successfully completed local recovery/update action into HTTP 500 solely because the provider-synchronised mirror failed;
- preserve secret hygiene and bounded error detail;
- retry/reconcile through existing periodic telemetry paths;
- avoid recursive failure while recording the local mirror hold.

Target server release: BCP 0.7.10.


## P0 — Target-bundled recovery runner / R47

This requirement is additive and preserves R43-R46.

### Field-derived failure mechanism
A recovery target can contain the fix required to install itself while the currently installed recovery runner still contains the older defect. Hash-verifying the target ZIP is not sufficient if BCP then launches the stale installed runner to perform the transition.

### Mandatory bootstrap rule
After BCP verifies the target recovery package SHA-256:
- BCP MUST extract the recovery runner from that exact verified target archive;
- the member path MUST be exact and unique;
- the member size MUST be bounded;
- the source MUST decode deterministically and compile successfully;
- target-specific safety contracts MAY be enforced before launch;
- the staged local copy MUST be byte-readback verified and SHA-256 receipted;
- the launched runner provenance MUST be HASH_VERIFIED_TARGET_PACKAGE;
- the older installed recovery runner MUST NOT be trusted as the bootstrap authority for a newer target package.

For Recovery sequence 6034 and later, the runner contract MUST preserve DriveFS recovery-result fail-open semantics: provider publication failure cannot abort a locally successful updater before active-pointer convergence.

No UAC elevation, credential transfer, generic process kill, OAuth bypass, or network-policy broadening is introduced by this bootstrap rule.

Target server release: BCP 0.7.11.


## R51 — Explicit fresh Nexus device-flow retry

When Nexus is in `HUMAN_AUTH_REQUIRED` because a Cloudflare device authorization expired or was not completed, BCP MUST NOT treat an ordinary apply call as a fresh retry.

A fresh retry MUST be an explicit human-confirmed action and MUST:
- archive and remove the stale Nexus auth receipt before relaunch;
- record a new explicit retry nonce;
- relaunch the device-only Wrangler path so a new device code is generated;
- never reuse an expired device code;
- never fall back automatically to classic `wrangler login` / `localhost:8976`;
- preserve zero-USD and existing local Telegram authorization;
- refuse deployment success until provider-authenticated `whoami` or equivalent readback succeeds.

The explicit retry endpoint is `/v1/system/nexus/retry-auth` and requires `{"confirm": true}`.
Ordinary `/v1/system/nexus/apply` remains non-escalating when the current state is already `HUMAN_AUTH_REQUIRED`.


## R53 — Human-first Cockpit simplification and user guide

This requirement is additive and preserves prior cockpit, evidence, Nexus, Telegram and mission semantics.

### Human comprehension is a P0 acceptance criterion
The normal Telegram/API cockpit MUST be understandable without Git, CI, SHA, transport or internal BCP vocabulary.

The primary surface MUST answer in this order:
1. where are we now;
2. what changed;
3. what is the current step;
4. what happens next;
5. does the user need to act;
6. why is the system showing this state.

### Required primary labels
Direct Telegram and Nexus MUST expose semantically identical controls:
- 🟢 Où en sommes-nous ?
- 🕘 Nouveautés
- 💬 Messages récents
- ❓ Pourquoi cet état ?
- 📍 Étape actuelle
- 🎯 Objectif & plan
- ⚙️ Travail récent
- 🔭 Risques à venir
- ▶️ Reprendre maintenant
- ✅ Vu / compris
- 🔕 Pause 2h
- 🔔 Alertes normales
- ❔ Aide / mode d’emploi

Deep technical evidence remains behind:
- 🧰 Détails techniques;
- the four PDF exports.

### Delivery-gap wording
A mirrored assistant response with no seen evidence MUST NOT be phrased as if ChatGPT necessarily failed.
The human-facing explanation must say that BCP has a durable copy but has not received a reading confirmation, and must provide a clear choice:
- ✅ Vu / compris if already read;
- 💬 Messages récents or email mirror if not visible in ChatGPT.

### User guide
The canonical guide is:
- docs/BCP_COCKPIT_MODE_D_EMPLOI_R53.md

### Interactive tranche and Gmail START/END acknowledgement gate
The active API/BCP work cadence now targets 25 minutes, with a practical 24–25 minute window unless a real gate requires earlier return.
When email is available, the complete checkpoint body MUST be sent by email first. After positive Gmail send receipt, the ChatGPT application MUST show only the short pointer containing mail confirmation, Kinshasa date/time, and checkpoint identifier; it MUST NOT duplicate the detailed checkpoint body.

Checkpoint delivery order is normative:
1. EMAIL_START_NOTICE;
2. SUBSTANTIVE_WORK;
3. EMAIL_END_FULL_CHECKPOINT_RETRY_UNTIL_ACK;
4. CHATGPT_POINTER_ONLY_AFTER_EMAIL_END_ACK;
5. TELEGRAM_WITNESS_OPTIONAL.

A failed START email blocks substantive work. A failed END email MUST be retried until the mail provider returns a successful send acknowledgement. No ChatGPT end message, hold message, success message, or pointer may be emitted before that END acknowledgement; after the acknowledgement, ChatGPT is pointer-only.

### Progressive disclosure
The normal mobile cockpit MUST NOT expose reports and deep technical diagnostics at the same visual level as orientation and human-action controls.
The primary keyboard contains only orientation, current-step, resume, acknowledgement, notification and help controls plus one entry point **📚 Rapports & technique**.
The advanced keyboard contains the four PDF exports, technical details and a clear return control.
Direct Telegram and Nexus MUST keep this hierarchy semantically identical.


## P0 — Human Presentation, Kinshasa Time & PDF Quality / R54

This requirement is additive and preserves all prior requirements.

### Human-time boundary

BCP MUST distinguish machine time from human presentation time.

- Canonical receipts, hashes, leases, database events and interoperability timestamps remain UTC/offset-aware for deterministic machine processing.
- Every normal user-facing timestamp in Telegram, Nexus human surfaces, email checkpoints and generated human reports MUST be rendered in **Africa/Kinshasa (UTC+1)**.
- A human-facing timestamp MUST say that it is Kinshasa time when ambiguity is possible.
- Raw UTC ISO timestamps may appear only in explicitly technical/debug evidence, and even there the normal reading path SHOULD provide the Kinshasa equivalent.
- Time conversion MUST NOT mutate the underlying canonical evidence.

### Ten-second comprehension contract

A normal user surface MUST answer, without requiring GitHub/BCP jargon:
1. Where are we?
2. What is already confirmed?
3. What is happening now?
4. What happens next?
5. Does the user need to do anything?
6. Is the information fresh or stale?

The first screen/page SHOULD be understandable by a non-technical reader without knowing SHA, PR, workflow IDs, internal enum names, transport class names or database field names.

Internal labels such as `nexus_bootstrap_error_class`, `mission_id`, `last_committed_step`, `event_age_seconds`, raw enum values and raw JSON MUST NOT be the primary presentation in human reports.

### PDF quality contract

The four PDF reports remain complementary, but their roles are now explicit:

1. **Situation humaine** — decision/orientation first; concise state, objective, confirmed work, current step, next step, human action.
2. **Appareils, réseau et transports** — human-readable device and connectivity status; raw telemetry field names are hidden.
3. **Objectif, étapes et progression** — objective, proven progress, current work, next work, user action and points to watch; technical mission IDs are hidden.
4. **Dossier technique et audit** — versions, checkpoints, IDs and engineering evidence are allowed, but raw multi-kilobyte JSON dumps are replaced by structured summaries.

All PDF outputs MUST:
- use a single non-duplicated document title;
- use clear visual hierarchy between title, sections, body and bullets;
- preserve French accents and punctuation correctly;
- have bounded margins and no clipped/overlapping text;
- paginate automatically and display page number;
- state that displayed human time is Kinshasa time;
- avoid orphan section headings where practical;
- remain lightweight enough for the 4 GB Windows target and weak network;
- preserve a dependency-free fallback path;
- be visually rendered and inspected in qualification, not merely checked for a valid `%PDF` header.

### Human/technical separation

User-facing views MAY link to a technical view, but MUST NOT force the user to read diagnostic internals to understand normal operation.

The technical report MUST retain enough exact evidence for engineering audit while the human reports translate that evidence into plain language.

### Regression obligations

Qualification MUST include at least:
- UTC -> Kinshasa conversion fixture;
- no raw UTC offset in reports 1–3;
- no raw mission ID / Nexus error-class field in reports 1–3;
- WinAnsi-compatible French glyph rendering in the dependency-free PDF fallback;
- bold/section font presence and page footer/page count;
- rendered-page visual smoke inspection for representative long content;
- protection against duplicate report titles.

Target presentation revision: **R54**.


## P0 — Email-only detailed human checkpoint / R55

This requirement is additive and supersedes only the human checkpoint delivery surface from R53/R54; all underlying execution, telemetry, evidence, rollback, security and product requirements remain active.

### Human-facing delivery rule
For every normal active technical work tranche targeting 25 minutes (practical 24–25 minute window):
1. execute useful project work first;
2. persist the durable checkpoint and evidence;
3. send the complete human-readable checkpoint by email;
4. only after positive Gmail send receipt, the ChatGPT application response MUST be pointer-only.

The ChatGPT pointer MUST contain only:
- confirmation that the mail was sent;
- Kinshasa-local date/time;
- checkpoint identifier.

After a successful email send, the ChatGPT response MUST NOT duplicate the detailed checkpoint body, action list, technical report, or progress explanation.

### Email is the detailed authority
Email becomes the sole primary detailed human checkpoint surface for this project. The email MUST contain:
- checkpoint ID;
- Kinshasa-local date/time;
- what was actually executed;
- verified evidence and uncertainty;
- current project state;
- exactly one current human gate when needed;
- the next project action;
- explicit supersession of older user instructions when applicable.

Telegram remains a secondary witness/alert/recovery-navigation channel and does not replace the detailed email checkpoint.

### Failure semantics
If Gmail delivery fails:
- never claim that the mail was sent;
- ChatGPT may state only an EMAIL_DELIVERY_HOLD plus the minimum recovery instruction needed to restore delivery;
- do not silently fall back to a full in-app checkpoint unless the user explicitly asks for that exception.

### Cadence
The canonical interactive tranche target is now approximately 25 minutes for BCP, with a practical 24–25 minute window. Earlier 5–6, 5–7, and 8–10 minute human-facing checkpoint cadence rules are superseded by R58 for this project.

Canonical machine policy:
- `.project-memory/DELIVERY_REDUNDANCY_POLICY.json`


## P0 — Pre-human action simulation gate

Before instructing the user to click, install, authorize, run, reboot, retry, or replace a CURRENT artifact, BCP MUST exercise the exact user-facing path in representative automation whenever technically feasible.

Mandatory principles:
- use Windows GitHub-hosted runners for Windows/PowerShell/runtime paths;
- use Android unit/lint/build tests and an emulator/instrumented path when Android UI/platform behavior materially affects correctness;
- test the exact CURRENT package/version/hash and the version-propagation/update path, not only source code in isolation;
- include runtime execution, negative controls, HOLD/rollback behavior, and readback expectations;
- if a path fails in CI/simulation, continue fixing automatically and do not ask the user to repeat the same action;
- distinguish simulated/provider-boundary evidence from real field verification;
- external consent/authentication such as Cloudflare device authorization remains a real human/provider boundary, but all code before that boundary must be exercised first;
- do not claim FIELD_VERIFIED from simulation alone.

Canonical policy:
`.project-memory/PRE_HUMAN_ACTION_SIMULATION_POLICY.json`.

Representative simulation is a release gate, not a substitute for field truth. A Windows runner can qualify Windows/PowerShell/local-runtime behavior; Android CI and an emulator/instrumented runner can qualify Android behavior where relevant; real account consent, provider availability, physical radio/network conditions and device-specific field effects remain separately evidenced gates.

For the current Nexus authorization path, qualification includes both the server-side explicit-retry runtime path and the exact Windows PowerShell one-shot helper against a local HTTP simulation, including a positive LAUNCHED response and an expected HTTP 500/HOLD negative control.


## P0 — Interactive work cadence

Normal interactive technical work uses a ~25-minute useful-work tranche: target 25 minutes, with approximately the final minute reserved for durable checkpoint/email delivery. Earlier return is allowed only for a real human gate, safety hold, tool failure, or a completed atomic action that should be checkpointed immediately. The full checkpoint is sent by email first; ChatGPT then shows only the short Gmail/date-time/checkpoint pointer after confirmed mail delivery.

The durable `project_state.json` must expose the currently active cadence and simulation-gate policy so a fresh `BCPGO BCP` recovery cannot regress to a superseded 5–7 or 8–10 minute rule or ask the user to repeat an unqualified action path.


## P0 — Gmail START/END tranche handshake — R60

For every user-invoked active technical tranche where Gmail is available:

- a **START** email MUST be sent before substantive project work begins; only minimal routing/context lookup needed to identify the active project is allowed before this message;
- the START email MUST include project, Kinshasa-local day/date/time, tranche target, and work scope;
- the normal tranche target remains approximately 25 minutes;
- at the end, a **full END checkpoint** MUST be sent by Gmail before any user-visible ChatGPT completion response;
- after successful END mail delivery, ChatGPT MUST be pointer-only: “Va sur Gmail” + Kinshasa-local day/date/time + checkpoint identifier;
- detailed work results MUST NOT be duplicated into the ChatGPT app after the mail succeeds;
- START-mail failure blocks substantive work; END-mail failure MUST trigger automatic resend attempts and forbids any ChatGPT end output until a provider send acknowledgement is obtained.

Canonical machine policies:
- `.project-memory/DELIVERY_REDUNDANCY_POLICY.json`
- `.project-memory/INTERACTIVE_WORK_CADENCE_POLICY.json`
- `.project-memory/UNIVERSAL_CONTINUATION_CODE_REGISTRY.json`


## P0 — Autonomous communication liveness across restart and network change / R62

Field evidence showed two distinct communication failure modes that MUST be handled without using the user as a telemetry bus:

1. the resident Telegram worker can be alive and polling successfully while the human sees no new message for hours because no event crossed the prior push threshold;
2. a transient DNS/network failure during Nexus manifest staging can overwrite the visible Nexus delivery state with `STAGE_FAILED`, causing the explicit one-shot helper to misleadingly report `NO_HUMAN_AUTH_RETRY_NEEDED` even when a durable Cloudflare human-auth receipt previously existed.

The communication plane MUST therefore:

- emit a compact Telegram **BCP connected** notice after a genuine PC/worker restart once the direct Bot API path is actually proven healthy, with anti-spam suppression for quick worker restarts;
- emit a compact **Telegram reconnected** notice after recovery from bounded direct transport failures, including Wi-Fi ↔ hotspot/mobile changes;
- emit at most one silent lightweight **BCP still online** proof every 90 minutes while the PC and direct Telegram path remain healthy, so prolonged silence is not confused with a dead bot;
- preserve bounded data use: no high-frequency healthy heartbeat spam and no large payload on these liveness notices;
- persist transport-notice receipts locally and never mark a notice delivered if the Telegram send failed;
- keep mission/event delivery and user commands independent from the liveness notice channel;
- preserve a prior stable Nexus state and human-auth receipt when a later manifest check fails because of DNS/timeout/TLS/connection refusal;
- when a one-shot Nexus retry is invoked during a network-stage failure, retry staging once immediately and, if the network is still unavailable, return a truthful automatic recovery state instead of a misleading success/no-retry result;
- never reuse stale Cloudflare device codes and never enable automatic localhost:8976 fallback;
- keep Gmail START -> work -> Gmail END provider acknowledgement -> ChatGPT pointer-only as the primary tranche communication order;
- arm an automatic tranche-end watchdog at START so the user never has to send “eh oh” merely to obtain the END checkpoint.

Target coordinated release:
- BCP server **0.7.14**;
- Telegram companion **2026.09.21-comms-autonomy-v20**.

## P0 — R64 dedicated B-EDGE adaptive communications plane

The dedicated old Android phone is infrastructure. It MUST be used as a real B-EDGE continuity/relay node and MUST NOT regress to a passive telemetry client.

Field topology is uplink-agnostic and MUST NOT assume a SIM in B-EDGE:
- B-EDGE may obtain Internet through home Wi-Fi or another Wi-Fi uplink such as the user's temporary hotspot;
- PC<->B-EDGE uses the best qualified local path and MUST continue local store-and-forward even when neither node has Internet;
- loss of the user's temporary hotspot MUST NOT erase project state, queue entries, receipts, checkpoints or communication intents;
- without any Internet uplink, remote Telegram delivery is truthfully `NETWORK_WAIT`; it is queued, never fabricated;
- a future Bluetooth/Companion/Wi-Fi-Direct local path may preserve PC<->B-EDGE reachability when no common LAN exists, but it is not FIELD_VERIFIED until exercised on the real devices.

### Selective low-data relay

When direct PC->Telegram transport is degraded and B-EDGE has a validated Internet uplink, B-EDGE SHALL be eligible to relay only the tiny Telegram control plane before any broader traffic is considered.

R64 baseline relay contract:
- PC discovers/registers the paired B-EDGE relay over the authenticated local BCP channel;
- relay registration is short-lived and bound to the observed private-LAN source address;
- B-EDGE accepts authenticated HTTP CONNECT only for `api.telegram.org:443`;
- TLS remains end-to-end PC<->Telegram; B-EDGE does not receive the Telegram bot token or message payload in plaintext;
- proxy authentication uses the existing paired BCP credential, never the Telegram token;
- the relay has bounded concurrent connections, connect timeout and idle timeout;
- GitHub, Drive, APK/ZIP/PDF and other bulk traffic are forbidden from this control-only relay unless a later separately qualified policy explicitly allows them;
- direct Telegram is attempted normally; B-EDGE relay is a transport failover on direct network errors;
- relay liveness/expiry is externalized in BCP runtime telemetry;
- when B-EDGE has no usable uplink, messages remain durable and retry on network return.

### Data-saver invariant

A metered/mobile path MUST change policy, not merely network address:
- heavy downloads/build sync/update artifacts are deferred unless explicitly required;
- compact control messages, receipts and state deltas have priority;
- unchanged-version downloads remain zero;
- PC and B-EDGE caches are preferred over remote re-fetch;
- the user's current phone is not required to remain present for correctness.

### Promotion gate

No R64 user-facing install/update may be requested until:
1. Android unit/lint/build and emulator human-action simulation pass on the exact candidate head;
2. relay allowlist/authentication/expiry negative controls pass;
3. Windows Telegram fallback contract passes without exposing the bot token to B-EDGE;
4. server registration accepts only authenticated private-LAN B-EDGE state;
5. CURRENT/server/Android/Telegram versions and hashes are coordinated;
6. field installation/readback proves the signed B-EDGE runtime before the relay is represented as FIELD_ACTIVE.


## P0 — Dedicated phone as primary Edge/API server — R67

The dedicated old Android phone is a first-class BCP infrastructure node. It MUST NOT be reduced to a passive client, a UI-only endpoint, or a narrow Telegram proxy.

Target division of responsibility:
- **phone**: authenticated local API, durable Room/SQLite WAL state, durable job/outbox queue, store-and-forward control messages, local sentinel, compact context/checkpoint cache, WorkManager recovery, adaptive network capability detection, and low-data egress gateway;
- **PC**: Windows/PowerShell specialist, desktop integration and burst/heavy compute when those capabilities are actually required.

The phone path MUST remain useful while the PC has no general Internet access. Preferred topology is `PC -> local phone path -> allowlisted phone uplink` for control traffic. The phone does not require its own SIM; any validated Wi-Fi/hotspot uplink is acceptable.

Transport ladder:
1. private LAN/shared hotspot;
2. USB/ADB-style local port-forward where available;
3. Wi-Fi Direct after real-device qualification;
4. Bluetooth/BLE for tiny emergency control/heartbeat traffic after qualification;
5. OEM/USB accessory/tether paths only when capability-probed and field-qualified.

BCP MUST NOT silently convert the phone into an unrestricted Internet proxy. Bulk/general-purpose PC traffic is excluded by default; the current remote relay remains allowlisted to the Telegram control-plane target.

A dedicated-device Android Device Owner/DPC mode MAY be used as a later explicit provisioning mode for stronger kiosk/policy/background guarantees. Root is not a baseline requirement and MUST NOT be assumed. Any provisioning step that can reset/wipe the device requires explicit user approval.

Concrete R67 source contract:
- phone local API role: `PHONE_PRIMARY_EDGE_SERVER`;
- bounded local API shares TCP 8876 with the strict CONNECT relay;
- protected endpoints use the existing paired BCP bearer identity;
- WorkManager/Room remain the durable recovery authority;
- normal boot/package replacement re-arms server/reconciliation where Android permits;
- PC registration and telemetry MUST expose phone role, API reachability, capabilities, connectivity, queue depth and Edge version;
- representative Android CI MUST prove APK install, foreground server startup, USB/ADB local port-forward health, auth boundary, UI and cold relaunch before user field action.

Canonical policy: `.project-memory/PHONE_PRIMARY_EDGE_SERVER_POLICY.json`.
