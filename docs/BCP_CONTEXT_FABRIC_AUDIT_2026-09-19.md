# BCP Context Fabric — Research / Audit / Counter-Audit 2026-09-19

Status: DESIGN REVIEW RECORD
Scope: universal memory/context, three-node topology, Android edge runtime, ChatGPT integration, security and zero-dollar remote gateway

## Executive conclusion

The architecture is viable if "centralized" means one logical authority and one universal API/context contract, not one fragile physical machine.

Recommended topology:
- B-EDGE = dedicated always-recoverable edge memory/coordinator;
- PC-WORKER = heavy fenced worker + near-line replica;
- BCP NEXUS = thin remote bootstrap/context/witness/ingress facade;
- one canonical revision/epoch/fencing model spans all three.

The user-facing north star is one command: `BCPGO`.

The strongest performance decision is to precompute small context projections and use revision-aware UNCHANGED/DELTA responses instead of rebuilding or retransmitting all memory on every turn.

## Research findings adopted

### Hierarchical memory instead of monolithic context

MemGPT introduced OS-inspired hierarchical/virtual context management for long-running conversations/documents. This supports BCP's HOT/WARM/COLD memory and small working Context Packs.

Generative Agents showed that useful agent memory requires selective retrieval and higher-level reflection rather than raw accumulation.

Recent personalized conversational-memory work (2025) found that memory granularity matters and that segment-level construction plus compression/denoising can improve retrieval versus naïve turn/session storage.

A 2026 survey of autonomous-agent memory frames memory as a write-manage-read loop and identifies contradiction handling, latency budgets, privacy governance and selective forgetting as core engineering issues.

MemoryAgentBench (2025) emphasizes four competencies: accurate retrieval, test-time learning, long-range understanding and selective forgetting. BCP therefore treats "forgetting/compaction" as a feature, not data loss.

### Durable execution

Temporal/durable-workflow architecture separates deterministic workflow state from at-least-once side-effect activities and reconstructs state from durable event history.

BCP adopts the pattern, not the heavyweight Temporal deployment:
- deterministic scheduler;
- immutable job/action envelopes;
- idempotency;
- receipts;
- replay/reconciliation;
- no duplicate canonical effect.

### Local-first

Local-first software research supports offline ownership and local availability.

Counter-audit: CRDT/multi-master is rejected for canonical PROJECT_HEAD, permissions and irreversible jobs. BCP chooses a single-writer fenced head and permits merge-friendly approaches only for non-authoritative data where safe.

### SQLite

SQLite WAL is suitable for fast local transactional state and concurrent local readers/writer, but WAL is explicitly same-host; it is not a network-replication mechanism.

Therefore B-EDGE/PC replication uses logical events/verified snapshots, never shared/raw WAL.

### Android background execution

Android documentation makes a permanent background-process assumption unsafe:
- background work is restricted;
- WorkManager is the default choice for most persistent deferrable work;
- foreground services are user-visible and constrained;
- Android 15 imposes aggregate timeouts on dataSync/mediaProcessing foreground-service types;
- Android 16 applies job execution quotas even in scenarios that were more permissive before.

Therefore "always-on B-EDGE" means always recoverable, not an immortal process.

### MCP / context protocol direction

MCP 2026-07-28 uses explicit per-request metadata and is stateless at the protocol core; durable application state is referenced by explicit identifiers.

That aligns with BCP's Context Pack IDs, revisions and context leases.

Counter-audit: current ChatGPT product support cannot be assumed to provide full writable custom MCP to the user's current Plus plan. BCP must work through connected-store/read paths today and add a direct MCP/plugin adapter only when the actual plan/product surface supports it.

### Persistent-memory security

OWASP and recent agent-memory research show persistent memory and RAG are durable prompt-injection/memory-poisoning attack surfaces.

BCP therefore separates:
- normative memory;
- descriptive facts;
- derived summaries;
- untrusted content.

External content/model output cannot directly write POLICY or USER_MEMORY.

## Current repository implementation audit

Target design already exists in:
- `docs/BEDGE_RUNTIME_V2_HARDENING.md`;
- `.project-memory/BEDGE_RUNTIME_V2_POLICY.json`;
- `docs/BEDGE_V2_TEST_MATRIX.md`.

Current Android implementation remains earlier than the target:
- `EdgeOrchestrator.java` stores mode/context/memory/job queue in SharedPreferences;
- `EdgePolicy.java` provides only simple mode/queue/cache rules;
- Android Gradle currently has no Room/WorkManager dependency;
- telemetry is a bounded JSONL file;
- therefore the dedicated multi-project memory/scheduler fabric is NOT yet runtime-implemented.

This is a controlled migration gap, not a reason to abandon the architecture.

## Major design improvements accepted in this audit

1. Introduce one logical `BCP NEXUS` facade instead of calling any one physical device "the server".
2. Adopt `BCPGO` as universal cross-project bootstrap trigger.
3. Keep `APIAX07` and project codes as scoped aliases.
4. Add a tiny Bootstrap Manifest.
5. Split context into GLOBAL_CORE, PROJECT_CORE, TASK_DELTA, EVIDENCE_ON_DEMAND.
6. Add revision-aware per-turn `UNCHANGED/DELTA/FULL_REFRESH`.
7. Precompute context projections on state mutation.
8. Make Context Packs hashable and schema-validated.
9. Add normative/descriptive/derived/untrusted memory categories.
10. Add explicit `LLM_EXPORTABLE` memory label.
11. Use structured key/value memory for stable preferences and topic segments for conversational learning.
12. Keep original receipts/evidence authoritative; summaries are caches.
13. Reject raw cross-device SQLite/WAL replication.
14. Keep single-writer/fencing for canonical head.
15. Use NEXUS as potential third witness only after field qualification.
16. Prefer current connected Drive projection for ChatGPT bootstrap.
17. Treat direct MCP/plugin write integration as future/conditional.
18. Add anti-memory-poisoning and privacy-extraction tests.
19. Add measurable bootstrap/context performance SLOs.
20. Make full-history prompt injection a non-default anti-pattern.

## Fast-path design

Fresh chat:

`BCPGO`
-> read BCP_BOOTSTRAP_CURRENT
-> resolve GLOBAL_CORE
-> infer/select project
-> resolve PROJECT_CORE
-> attach current TASK_DELTA
-> answer/act

Later turn:

`resolve_context(last_revision, project, request_hash)`
-> UNCHANGED / DELTA / FULL_REFRESH / CONFLICT / DEGRADED / HOLD

This means BCP may be consulted on every turn while network/token cost remains tiny on the common UNCHANGED path.

## Zero-dollar remote NEXUS candidate

Cloudflare is a technically attractive future NEXUS candidate after Kinshasa/account field validation:
- Workers Free supports SQLite-backed Durable Objects;
- current documented free Durable Objects quota includes 100,000 requests/day and 13,000 GB-s/day;
- D1 current Free plan documents 5 million rows read/day, 100,000 rows written/day and 5 GB storage;
- free-tier queries now fail closed at quota rather than silently becoming paid.

These capacities are far above a single-user bootstrap/control workload if queries are indexed and compact, but they are not treated as available until field qualification passes.

Google Drive remains valuable as:
- connected private read projection for current ChatGPT;
- change feed/push-notification capable storage;
- cold backup/recovery store.

## Universal-command reality

`BCPGO` is not magic.

For a brand-new conversation to use it:
- ChatGPT must know the trigger semantics via durable/native pointer/instructions/plugin;
- and an authorized source/tool must expose the BCP projection.

Recommended two-level bootstrap:
1. ChatGPT/native instruction remembers only: "BCPGO => consult BCP bootstrap source".
2. All actual preferences/project state live externally in BCP.

This minimizes dependency on ChatGPT-native memory while preserving convenience.

## State-machine counter-audit

A synthetic model was exercised over 10,000 randomized sequences of 200 operations including:
- B-EDGE commits;
- PC commits;
- coordinator promotion;
- stale old-coordinator commits.

With the specified epoch/fencing acceptance rule:
- accepted revisions remained unique and monotonic;
- no stale commit was accepted in the model;
- 857,152 stale/unauthorized attempts were rejected.

This is only a design-model sanity check. It is NOT FIELD/RUNTIME evidence. The real implementation still requires the failure-injection matrix.

## Risks still open

### R1 — ChatGPT direct universal integration
Current Plus capabilities do not guarantee a private writable custom MCP app path. Drive-connected bootstrap is the near-term baseline.

### R2 — B-EDGE database migration
SharedPreferences must be replaced for canonical multi-project/job/memory state without breaking the current Evergreen field line.

### R3 — Remote NEXUS field availability
Cloudflare/other free infrastructure must pass real RDC account/network/no-card tests.

### R4 — Memory relevance
Retrieval quality must be benchmarked on the user's real multi-project corpus. FTS-first is intentionally simple; semantic indexing is optional after evidence.

### R5 — Privacy
Cross-project retrieval and model-export filters require adversarial tests.

### R6 — Android wake latency
WorkManager is durable but not instant. Low-latency remote commands need a qualified push/cloud queue path or honest delayed semantics.

### R7 — Authority migration
Current PC-side field-proven authority cannot be silently replaced by B-EDGE V2. Promotion requires a versioned reversible migration and partition tests.

## Rejected designs

- full conversation dump on every request;
- always-resident Android daemon as correctness requirement;
- permanent dataSync foreground service;
- LLM-driven scheduler;
- every-agent-direct-chat-to-every-agent;
- unrestricted multi-model voting;
- raw SQLite DB/WAL sync between devices;
- CRDT multi-master global project head;
- cloud-only memory authority;
- public GitHub for private user-memory projection;
- universal code treated as secret/authentication;
- provider/model outputs writing memory without admission;
- free-tier provider used before Kinshasa field proof;
- paid fallback when free quota is exhausted.

## Next implementation priority after current P0 field line

1. Room/SQLite schema + migration tests.
2. WorkManager reconciliation.
3. multi-project registry + job DAG.
4. structured memory admission/provenance.
5. FTS Context Compiler.
6. Context Pack schemas and unit/property tests.
7. precomputed Drive GLOBAL/PROJECT projections.
8. BCPGO fresh-conversation acceptance.
9. per-turn delta protocol.
10. PC replica/work-envelope integration.
11. remote NEXUS field test.
12. direct ChatGPT app/plugin integration when supported.
