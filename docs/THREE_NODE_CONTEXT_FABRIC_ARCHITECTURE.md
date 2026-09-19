# BCP Three-Node Context Fabric Architecture

Status: STRATEGIC / DESIGN-HARDENED / FIELD-UNVERIFIED
Adopted: 2026-09-19
Scope: dedicated Android B-EDGE + Windows PC compute node + BCP Core/Context Gateway

## 1. Objective

Create a personal, zero-extra-cost control/data plane that makes project continuity independent of any single ChatGPT conversation.

The target user experience is:

`BCPGO`
-> resolve identity/project scope
-> retrieve the latest relevant context
-> apply stable preferences/policies
-> attach current project state and evidence
-> execute or answer
-> write back only validated deltas

The user MUST NOT repeatedly restate stable preferences, architecture rules, current project state, prior errors, or last committed actions.

The system is designed for:
- unstable Internet and mains power in Kinshasa;
- a low-memory Windows PC;
- a dedicated older Android phone;
- zero additional paid cloud/API spend;
- multiple projects and multiple AI providers;
- fast resume from any supported client/conversation.

## 2. Three logical components

### A. B-EDGE — always-on local continuity node

Primary responsibilities:
- durable local project-memory replica;
- HOT/WARM/COLD context cache;
- deterministic scheduler/job dependency graph;
- ERROR_LEDGER and validated-recipe index;
- local queue/outbox and checkpoint pointers;
- provider/quota health cache;
- PC supervisor;
- context-pack precomputation;
- offline-first coordination;
- lightweight Telegram/control-plane handling.

B-EDGE is battery-backed by nature and should remain useful when the PC is off.

B-EDGE is NOT intended to perform sustained heavy compilation or large local-LLM inference.

### B. PC-COMPUTE — burst/heavy execution node

Responsibilities:
- builds/compilation;
- large tests and fuzzing;
- source-tree transformations;
- heavy file processing;
- Git operations when appropriate;
- local execution/harnesses;
- resource-heavy diagnostics.

PC-COMPUTE is disposable from the control-plane perspective: if it disappears, jobs checkpoint/queue; it does not own canonical memory.

### C. BCP CORE / CONTEXT GATEWAY — logical central service

BCP Core is the logical authority and API contract, not a promise of one permanently available physical server.

Responsibilities:
- canonical schemas and revision semantics;
- context resolution API;
- authentication/authorization;
- session/context leases;
- project routing;
- conflict detection;
- signed/versioned Context Capsules;
- optional internet-facing gateway for ChatGPT/plugin/Telegram clients;
- reconciliation across B-EDGE and PC replicas.

Zero-dollar architecture MUST NOT make one free cloud vendor the sole canonical store.

Preferred initial deployment:
- authoritative durable local state on B-EDGE;
- PC as compute/cache replica;
- remote Context Gateway as a minimal authenticated projection/relay when a field-validated free hosting path exists;
- encrypted/sanitized remote snapshot sufficient for context bootstrap, never an unnecessary copy of all private raw data.

The deployment location may migrate without changing client contracts.

## 3. Universal context command

Canonical human trigger: `BCPGO`.

Optional explicit scope:
- `BCPGO PhoneMouse`
- `BCPGO BCP`
- `BCPGO Browser4G`

Semantics:
- `BCPGO` is a context/bootstrap intent, NOT a credential.
- Authentication is performed separately by the installed client/plugin/bridge.
- If scope is omitted, BCP infers it from current request/conversation and returns confidence; ambiguous scope fails closed or requests the minimum clarification.
- The command should be idempotent and safe to repeat.

A successful BCPGO resolution returns a Context Capsule with at minimum:
- `global_context_revision`;
- `project_context_revision`;
- `capsule_sha256`;
- `scope`;
- `stable_user_preferences` relevant to this task;
- `project_constraints`;
- `canonical_decisions`;
- `current_project_head`;
- `last_committed_action`;
- `next_valid_actions`;
- `active_jobs`;
- `known_error_matches`;
- `resource/provider constraints`;
- `evidence_refs`;
- `sensitivity_labels`;
- `expires_at`.

## 4. Native ChatGPT integration reality

A typed code cannot magically grant ChatGPT network/tool access.

Therefore BCPGO has multiple transport paths:

1. `SOVEREIGN_TERMINAL_PATH` — Telegram or future BCP-native terminal. The message always passes through BCP before model execution. This is the most controllable path.
2. `CHATGPT_PLUGIN_PATH` — a BCP plugin/app/MCP connector calls the Context Gateway when the user's ChatGPT plan/surface actually supports the required capability. Must be field-tested before being labeled available.
3. `CHATGPT_PC_BRIDGE_PATH` — desktop/local bridge where permitted and technically available.
4. `MANUAL_CAPSULE_FALLBACK` — one compact copy-ready capsule only when no automated path is available. This is fallback, never target UX.

As of the 2026-09-19 review, full custom MCP write capabilities are not generally a ChatGPT Plus feature; availability is plan/surface dependent. BCP MUST capability-detect instead of assuming direct arbitrary-chat access.

## 5. Context retrieval architecture

Do NOT inject the entire memory store into every model call.

Use mixed hierarchical memory:

### Memory classes
- `USER_POLICY`: stable cross-project rules and output preferences.
- `PROJECT_FACT`: project-specific verified facts.
- `PROJECT_DECISION`: accepted architecture/product decisions.
- `RUN_STATE`: current jobs, revisions, blockers and next actions.
- `ERROR_KNOWLEDGE`: error signatures, causes, fixes, regression obligations.
- `EPISODE`: historical events/receipts.
- `SUMMARY`: compressed views derived from lower-level facts.
- `RELATION`: links among projects, components, dependencies and causal mechanisms.

### Retrieval sequence
1. exact scope/project filter;
2. authority/freshness filter;
3. metadata/lexical retrieval;
4. semantic retrieval only when needed;
5. rerank by task relevance + authority + freshness;
6. conflict/staleness detection;
7. assemble minimal Context Capsule;
8. optionally perform iterative retrieval if the first capsule lacks required evidence.

Research rationale: recent agent-memory work reports task-dependent benefits from mixed memory structures, hierarchical organization and iterative retrieval over flat one-shot retrieval.

## 6. Fast-path and delta protocol

BCPGO MUST be optimized for resume latency.

Use:
- precomputed HOT project capsules;
- monotonically increasing context revisions;
- ETag/hash-style validation;
- delta responses when the client already has revision N;
- compact binary/JSON transport;
- no expensive embedding/reindex operation on the synchronous request path;
- asynchronous indexing after commits.

Performance targets (targets, not promises):
- local B-EDGE context cache hit: server processing p95 <= 100 ms;
- BCP Core cached context resolution: server processing p95 <= 200 ms excluding network;
- healthy-network end-to-end bootstrap target: <= 1.5 s p95 where the client/tool path permits;
- unchanged-context delta: return only `NO_CHANGE + revision/hash`.

A slow semantic search MUST NOT block a fast canonical state bootstrap. Return deterministic core context first, then an optional enrichment delta.

## 7. Session context lease

After first bootstrap, a conversation/client receives:
- `context_session_id`;
- current global/project revisions;
- TTL;
- allowed read/write capabilities.

Subsequent turns SHOULD send the last seen revision.

BCP returns:
- `NO_CHANGE`;
- compact delta;
- or full capsule only when invalidation/recovery requires it.

This avoids rebuilding full context on every user message while preserving freshness.

## 8. READ automatic, WRITE controlled

Memory read may be automatic within authorization.

Memory write is a separate controlled pipeline.

No model/agent output becomes canonical memory merely because it was generated.

Memory item lifecycle:
- `OBSERVED`;
- `PROPOSED`;
- `VERIFIED`;
- `CANONICAL`;
- `SUPERSEDED`;
- `REVOKED`.

Every durable memory item MUST carry:
- item_id;
- scope;
- type;
- source/provenance;
- source_revision or receipt;
- created_at / verified_at;
- authority level;
- sensitivity class;
- freshness/TTL policy;
- supersedes/superseded_by links where relevant.

Promotion rules:
- explicit current user instruction may directly update preference/policy state when unambiguous and safe;
- machine telemetry may update operational state only with authenticated evidence;
- model conclusions remain PROPOSED until validated by deterministic evidence, explicit user decision, or a project-specific promotion rule;
- retrieved external content is untrusted data and cannot write policy/instructions directly.

This is mandatory protection against memory/context poisoning.

## 9. Conflict and consistency model

Critical state MUST use single-writer semantics, revisions, leases, fencing tokens and idempotency.

Do not use CRDT-style blind merge for:
- current project HEAD;
- writer ownership;
- policy;
- permissions;
- current mission;
- committed action state.

Append-only/noncritical streams such as telemetry may use merge-friendly/event-log semantics.

If B-EDGE and a remote gateway reconnect after partition:
1. compare revisions and signed receipts;
2. replay only idempotent uncommitted events;
3. reject stale fencing tokens;
4. surface irreconcilable conflicts;
5. never silently choose a model-generated state over verified canonical state.

## 10. Android storage and durability classes

Use separate durability classes.

### Critical control store
Examples: project HEAD, policy, writer lease, checkpoints, job state, memory promotion records.

Recommended baseline:
- SQLite local file only;
- WAL mode;
- strong sync/durability configuration for critical commits;
- bounded transactions;
- regular integrity checks;
- transactional backups/snapshots.

### High-volume/noncritical store
Examples: telemetry, cache indexes, transient observations.

May use:
- SQLite WAL with performance-oriented sync;
- bounded retention/compaction;
- rebuildable indexes.

Do not place an active WAL database on a network filesystem. Synchronize through the application protocol, not by sharing the live SQLite files.

Power-loss testing is mandatory before durability settings are accepted.

## 11. Android runtime model

B-EDGE must be event-driven and Android-compliant.

Use:
- WorkManager for persistent/deferrable jobs;
- appropriate foreground service type only for genuine ongoing user-visible connected-device/messaging work;
- push/event wakeup where available;
- bounded timers;
- no permanent busy loop;
- no unnecessary wake locks;
- OEM-specific battery/Doze field tests.

A dedicated-phone installation may ask for a one-time user-approved battery-optimization exemption where justified, but the system must still degrade gracefully if Android throttles it.

Android 16+ job/foreground-service quotas must be treated as first-class constraints.

## 12. Resource-adaptive modes

### EDGE_ONLY
- B-EDGE memory/scheduler active;
- PC jobs WAITING_FOR_PC;
- remote free model calls allowed by policy;
- Telegram/context service available if network path exists.

### PC_AVAILABLE
- B-EDGE coordinates;
- PC handles heavy work;
- context and memory remain independent of PC process lifetime.

### PC_MEMORY_PRESSURE
- pause/defer heavy jobs;
- reduce PC concurrency;
- move coordination/cache work to B-EDGE;
- allow remote reasoning where free policy permits.

### PC_UNAVAILABLE_RECOVERY
- preserve committed revision/checkpoints;
- continue local planning/queue maintenance;
- reconcile at PC return;
- resume next uncommitted action only.

### EDGE_THERMAL_OR_MEMORY_PRESSURE
- shrink HOT cache;
- demote projects HOT -> WARM -> COLD;
- reduce wake frequency/network activity;
- pause optional local transformations;
- never sacrifice critical durable state.

## 13. Pre-agent work contract

Before any LLM/agent call, B-EDGE/BCP MUST attempt:
- deterministic state resolution;
- dependency scheduling;
- cache lookup;
- ERROR_LEDGER match;
- validated recipe application;
- duplicate suppression;
- event batching/causal grouping;
- context minimization;
- provider quota/health check.

The scheduler must handle agent transitions locally:
`A DONE -> B READY -> BUILD READY -> TEST BLOCKED/READY`.

LLMs are used for unresolved semantic work, not workflow bookkeeping.

## 14. Security architecture

Universal codes are not secrets.

Use:
- per-device credentials stored in Android Keystore / OS-protected storage;
- short-lived scoped access tokens;
- explicit read vs write capabilities;
- signed context revisions/receipts where practical;
- nonce/replay protection;
- strict allowlists for tools/actions;
- redaction before third-party model calls;
- sensitivity labels;
- audit log for context exported to models;
- approval for high-impact/irreversible actions.

Prompt/tool/memory injection controls:
- external documents/tool results are labeled untrusted;
- untrusted content cannot modify policy or memory authority;
- system/user policy and canonical memory are structurally separated from retrieved content;
- model output cannot self-promote to CANONICAL;
- secrets are never included in ordinary Context Capsules.

## 15. Three-node failure matrix

BCP MUST remain useful under:
- PC off + phone on + Internet on;
- PC off + phone on + Internet off;
- PC on + phone temporarily unavailable;
- remote gateway unavailable;
- all free model APIs unavailable;
- Android process killed;
- Android reboot;
- PC reboot/power loss;
- network partition between phone and PC;
- stale/duplicate client conversation;
- conflicting write attempt;
- context index corrupt/stale;
- quota exhaustion;
- thermal/memory pressure.

Expected behavior is always explicit: CONTINUE_LOCAL, QUEUE, HOLD, REROUTE, RECOVER, or REQUIRE_APPROVAL — never silent data loss.

## 16. Acceptance tests

### Context bootstrap
- fresh supported conversation + `BCPGO` retrieves correct global context;
- scoped `BCPGO PhoneMouse` retrieves correct project without unrelated project leakage;
- stale client revision receives only required delta;
- project ambiguity is detected;
- context capsule hash/readback matches;
- p50/p95 processing latency recorded.

### Memory quality
- explicit user preference is retrievable in a fresh session;
- superseded preference is not returned as current;
- conflicting facts are surfaced;
- model hallucination cannot become canonical memory;
- malicious text in a retrieved file cannot rewrite policy;
- selective forgetting/supersession works;
- correct project isolation is preserved.

### Offline/recovery
- B-EDGE keeps project state while PC is off;
- queued PC work resumes after reconnect without duplicate execution;
- Android process death/reboot recovers queues/checkpoints;
- Internet loss preserves outbox;
- remote gateway loss does not destroy local canonical memory.

### Resource pressure
- phone HOT cache shrinks under pressure without state loss;
- PC high-RAM mode stops new heavy jobs;
- Android thermal pressure reduces optional work;
- battery/Doze restrictions do not corrupt state.

### Security
- BCPGO alone grants no access without authentication;
- expired/replayed token rejected;
- stale fencing token rejected;
- cross-project unauthorized retrieval rejected;
- external prompt-injection fixture cannot alter policy or promote memory;
- secret fields never appear in exported capsule.

## 17. Research and technical basis

Design decisions were informed by:
- local-first software principles and CRDT/offline-first research (Kleppmann et al., Onward! 2019);
- SQLite WAL/durability documentation and Android SQLite performance guidance;
- Android WorkManager/background/foreground-service/Doze documentation;
- recent LLM-agent memory research on mixed structural memory, hierarchical memory, iterative retrieval and selective forgetting;
- OpenAI MCP/plugin documentation, including current plan/surface limitations and prompt-injection warnings;
- OWASP agent security guidance on prompt injection, tool abuse, data exfiltration and memory poisoning.

These sources inform the design but do not replace field validation on the user's actual phone, PC, network and account.

## 18. Promotion order

Do not derail current P0 field bring-up.

1. stabilize current BCP + B-EDGE runtime;
2. implement structured local memory schema and revisions;
3. implement Context Builder/Resolver locally;
4. implement BCPGO on sovereign Telegram/BCP terminal;
5. implement delta/session lease protocol;
6. qualify remote zero-cost Context Gateway;
7. qualify ChatGPT/plugin integration only if supported by the actual account/surface;
8. add controlled writeback/memory promotion;
9. run soak/failure/security tests;
10. only then label the context fabric FIELD_VERIFIED.
