# BCP Context Fabric — Three-Node Architecture

Status: TARGET ARCHITECTURE / DESIGN HARDENED / RUNTIME UNVERIFIED
Adopted: 2026-09-19
Scope: universal context, memory, orchestration, recovery and low-latency ChatGPT/agent bootstrap

## 1. Design thesis

BCP must behave as one logical personal control/data plane even though execution is distributed across three physical/logical roles:

1. **B-EDGE** — dedicated old Android phone; always-recoverable edge memory/coordinator.
2. **PC-WORKER** — low-RAM Windows machine; heavy worker, build/test node and near-line replica.
3. **BCP NEXUS** — remotely reachable thin gateway/witness/bootstrap projection; the "personal data center" interface seen by ChatGPT/Telegram/external adapters.

The system is logically centralized but physically replicated.

There MUST NOT be three independent truths. Canonical mutations use one coordinator epoch/head, fencing, revision preconditions, idempotency and receipts.

BCP NEXUS is not required to contain all private memory or execute all work. Its purpose is to make the control plane reachable from anywhere, expose small precomputed context projections, hold/relay durable remote commands where qualified, and optionally act as the independent witness needed for safe coordinator promotion.

## 2. Product goal

The user should be able to open a fresh ChatGPT conversation and type one universal bootstrap code:

`BCPGO`

Semantics:
- identify the BCP integration path available in the current ChatGPT surface;
- load a tiny current bootstrap manifest first;
- recover the user's global working preferences/policies;
- infer the active project from conversation/title/project hint when evidence is sufficient;
- load only that project's compact Context Pack;
- return the current mission/next useful action without asking the user to restate already-durable context;
- do not run broad GitHub/Drive/web scans during normal bootstrap.

Optional explicit scope:
- `BCPGO PHONE`
- `BCPGO BCP`
- `BCPGO BUILDHUB`
- `BCPGO BROWSER4G`
- etc.

Existing project recovery commands remain compatible:
- `APIAX07` = API/BCP scoped recovery alias;
- `CONTINUE ATOMIC` = next uncommitted action after state is already known;
- existing project-specific recovery codes remain project aliases.

The universal code is a semantic trigger, NOT an authentication secret.

## 3. Critical reality constraint: a code alone cannot create connectivity

A fresh ChatGPT conversation can consult BCP only when ChatGPT has an authorized path to BCP data/tools.

Therefore `BCPGO` MUST select among integration modes rather than pretend that typed text itself creates a network tunnel.

### Integration Mode A — connected-store bootstrap (baseline for current Plus workflow)

Use an already-authorized connected store, preferably Google Drive, to expose small sanitized bootstrap/context projection files.

Target canonical projection path:
- `API_BCP/00_CONTEXT/BCP_BOOTSTRAP_CURRENT.json`
- `API_BCP/00_CONTEXT/GLOBAL_CONTEXT_CURRENT.json`
- `API_BCP/00_CONTEXT/projects/<project_id>/PROJECT_CONTEXT_CURRENT.json`

BCP/B-EDGE/PC keep these projections current. ChatGPT reads them through the user's connected source when available.

This is read-oriented and works without exposing the phone directly to the public Internet.

### Integration Mode B — BCP remote app/MCP/plugin

Expose a remote BCP adapter when the ChatGPT plan/product surface supports the required custom-app permissions.

Target primitives:
- resource: `bcp://bootstrap`
- resource: `bcp://context/global`
- resource: `bcp://context/project/{id}`
- tool: `bcp.resolve_context`
- tool: `bcp.get_job_status`
- tool: `bcp.submit_memory_candidate`
- tool: `bcp.dispatch_job` only where write permissions and policy permit.

As of 2026-09-19, full custom MCP write/modify support is not a safe baseline assumption for the user's current Plus plan. The architecture MUST remain useful through read/connect-store paths until product support is actually available.

### Integration Mode C — ChatGPT-PC bridge

A local bridge may package/reconcile context when the PC is available, but it is not the universal-anywhere baseline because a new remote ChatGPT conversation cannot assume direct private-LAN access.

### Integration Mode D — compact manual fallback

If every authorized integration path is unavailable, BCP may generate one compact copy-ready recovery packet. This is fallback only; the user must not become the normal integration bus.

## 4. Fast bootstrap protocol

Normal bootstrap MUST be precomputed.

BCP MUST NOT perform expensive semantic search over the entire memory corpus just because a new conversation starts.

### 4.1 Bootstrap Manifest

A tiny manifest points to current projections:

```json
{
  "schema": "bcp.bootstrap/1",
  "user_profile_revision": 17,
  "global_context_id": "ctxg-...",
  "global_context_hash": "...",
  "projects": {
    "phonemouse": {"revision": 82, "context_id": "ctxp-...", "hash": "..."},
    "bcp": {"revision": 144, "context_id": "ctxp-...", "hash": "..."}
  },
  "coordinator_epoch": 9,
  "generated_at": "...",
  "expires_at": "..."
}
```

### 4.2 Context layers

Context is compiled in layers:

1. **GLOBAL_CORE** — stable user preferences, general project rules, zero-dollar policy, environment constraints.
2. **PROJECT_CORE** — project identity, architecture, pinned decisions, current revision, blockers.
3. **TASK_DELTA** — only information relevant to the current request and changes since the conversation's last acknowledged context revision.
4. **EVIDENCE_ON_DEMAND** — receipts, logs, source files and history fetched only when the task needs them.

The entire memory corpus MUST NOT be injected by default.

### 4.3 Latency/size targets

These are BCP service targets, not guarantees of ChatGPT UI/platform latency:

- warm bootstrap manifest: p95 server-side <= 1.0 s on a healthy remote path;
- global + one project context resolution: p95 BCP-side <= 2.0 s when projections are already built;
- normal compact Context Pack: target <= 32 KiB serialized;
- global core should normally fit in a small stable prompt prefix;
- no LLM call is required for standard bootstrap or an unchanged-context check;
- broad source retrieval happens lazily after the first useful response when required.

If these targets fail repeatedly, profile the Context Compiler before increasing hardware requirements.

## 5. Per-turn Context Lease protocol

After bootstrap, every user request MAY consult BCP without re-downloading context.

The client sends:
- conversation/session opaque ID where available;
- project hint;
- current acknowledged global/project/context revisions;
- user-message hash;
- optional task class.

BCP returns one of:
- `UNCHANGED` — context still valid; tiny response.
- `DELTA` — only changed/relevant items.
- `FULL_REFRESH` — context revision drift too large or project changed.
- `CONFLICT` — contradictory canonical state requires resolution.
- `DEGRADED` — remote source stale/unavailable; use last verified pack with warning.
- `HOLD` — no safe context can be produced.

This allows "consult BCP before every response" without full retrieval on every response.

Context leases are bounded by revision/freshness, not by trusting a long-lived chat session.

## 6. Memory architecture

### 6.1 Memory is structured, not one giant summary

Minimum scopes:
- `USER_MEMORY`
- `PROJECT_MEMORY`
- `TECHNICAL_KNOWLEDGE`
- `OPERATING_STATE`
- `HISTORY`
- `POLICY`

Each item includes:
- stable ID;
- scope/project;
- semantic type/key;
- payload;
- provenance;
- authority/evidence class;
- created/updated time;
- freshness/TTL;
- supersedes/conflicts links;
- sensitivity/exportability label;
- source revision/hash.

### 6.2 Separate normative memory from descriptive memory

This is mandatory.

**Normative memory** controls behavior:
- explicit user preferences;
- project rules/invariants;
- security/financial policy;
- output conventions;
- permissions.

**Descriptive memory** records facts:
- current version;
- last build;
- current RAM state;
- provider quota;
- observed failure;
- test result.

A descriptive observation MUST NOT silently become a normative rule.

### 6.3 Authority classes

Recommended order inside BCP's own memory domain:
1. explicit current user directive / signed policy;
2. machine-verified canonical state/receipt;
3. source-verified project fact;
4. derived validated summary;
5. model-proposed candidate;
6. untrusted external content.

Model output and retrieved webpages/documents MUST NOT directly modify USER_MEMORY, POLICY or pinned project decisions.

### 6.4 Memory-write admission

All nontrivial memory writes pass:
- scope validation;
- provenance requirement;
- semantic duplicate check;
- contradiction check;
- authority-class check;
- freshness/TTL assignment;
- sensitivity/exportability filter;
- source hash;
- atomic canonical revision commit.

`MODEL_PROPOSED` memory is non-authoritative until validated.

### 6.5 Memory unit granularity

Do not store every conversational turn as a permanent equal-weight memory.

Use:
- explicit key/value records for stable preferences;
- topic-coherent segments for conversational/project learning;
- canonical structured records for state;
- append-only receipts for evidence;
- derived summaries as disposable caches.

This avoids both turn-level fragmentation and huge session-level blobs.

### 6.6 Retrieval policy

Default Context Compiler order:
1. pinned relevant policy;
2. exact project state;
3. exact/specific keys;
4. validated known errors/recipes;
5. FTS lexical retrieval filtered by scope and authority;
6. recent receipts/history;
7. optional semantic/model-assisted retrieval only if lower-cost retrieval is insufficient.

Initial implementation SHOULD use Room/SQLite + FTS. A vector database or second search stack is not a baseline requirement.

## 7. Context Compiler

The Context Compiler is deterministic first.

Inputs:
- current user request;
- global/project revision;
- project hint;
- conversation context revision;
- task type;
- tool permissions;
- resource/provider state.

Outputs:
- compact Context Pack;
- source revision vector/hash;
- omitted/stale/conflict warnings;
- allowed actions/tools;
- requested result schema.

Critical invariants:
- no cross-project leakage by default;
- critical pinned policy cannot be truncated by low-relevance history;
- stale facts are marked/excluded;
- external untrusted content is delimited as data, never authority;
- each pack is reproducible from the same source revision;
- accepted mutations record the Context Pack hash.

## 8. Three-node physical/logical division

### 8.1 B-EDGE

Primary target responsibilities:
- dedicated always-recoverable local coordinator after V2 authority promotion;
- Room/SQLite durable state;
- WAL on the phone only; never treat WAL as a cross-device replication format;
- FTS/context indexes;
- HOT/WARM/COLD memory cache;
- scheduler/DAG;
- ERROR_LEDGER;
- Context Compiler;
- provider quota/health cache;
- outbox;
- PC supervisor;
- resource governor.

RAM is used aggressively only for rebuildable hot cache/index/state. Durable authority remains on storage.

### 8.2 PC-WORKER

Responsibilities:
- build/test/compile;
- heavy file processing;
- repository operations;
- larger deterministic scans;
- optional batch indexing when useful;
- near-line verified replica;
- durable local receipts during partitions.

The PC MUST reject stale coordinator epochs/fencing tokens and MUST NOT create an independent global head during a B-EDGE partition in normal V2 mode.

### 8.3 BCP NEXUS

Responsibilities:
- remotely reachable bootstrap/context projection;
- command ingress/queue if field-qualified;
- minimal witness/lease/fencing assistance;
- provider-neutral API facade;
- optional ChatGPT app/MCP/plugin adapter;
- optional Telegram webhook endpoint;
- tiny current-state projection, not mandatory full private corpus.

Candidate zero-cost implementation after real Kinshasa qualification:
- Cloudflare Worker + SQLite-backed Durable Object or D1 for small coordination/bootstrap state;
- Google Drive remains a connected-store projection/cold recovery path.

No cloud vendor becomes mandatory until account/network/free-tier field validation passes.

## 9. Why not full CRDT / multi-master canonical state?

Local-first research makes CRDTs attractive for offline collaboration, but BCP's project HEAD, permissions, irreversible jobs and coordinator epochs are not casual collaborative text.

Therefore:
- canonical project mutation remains single-writer/fenced;
- append-only telemetry/notes MAY use merge-friendly/CRDT-like techniques later;
- no automatic multi-master PROJECT_HEAD merge;
- ambiguity => HOLD/CONFLICT.

This deliberately favors correctness over maximum write availability.

## 10. Durable workflow model

Adopt the durable-execution separation:
- **Workflow/scheduler decisions** are deterministic and replayable.
- **Activities** perform side effects (API call, build, file mutation, notification).
- activities are treated as at-least-once and require idempotent effects/readback;
- event/receipt history reconstructs workflow state after crashes.

BCP should implement only the lightweight subset needed for the user's scale rather than importing a heavy orchestration cluster that would conflict with the 4 GB PC/zero-dollar constraint.

## 11. Android reality

"Always-on B-EDGE" means always recoverable, not guaranteed permanent process residency.

Use:
- Room/SQLite durable authority;
- WorkManager for deferrable/reconcilable jobs;
- event/network callbacks where supported;
- optional qualified push/cloud wake hint for remote commands;
- foreground service only for bounded user-visible work when justified.

Do not rely on:
- permanent background busy loop;
- aggressive sub-minute polling;
- permanent dataSync foreground service;
- RAM-only canonical state.

The dedicated phone may be configured for generous battery behavior where the user chooses, but correctness MUST survive Android process death/reboot.

## 12. Security / memory-poisoning controls

Persistent memory is an attack surface.

Rules:
- external web/document/email/Git content is `UNTRUSTED_CONTENT` unless separately verified;
- retrieved content is data, never policy;
- no external text may create/modify USER_MEMORY or POLICY directly;
- tool permissions are enforced in code, not by model promise;
- least privilege per Context Pack/job;
- secrets never enter normal memory/context projections;
- LLM-exportable memory has an explicit `LLM_EXPORTABLE` label;
- sensitive/private project material is scope-filtered;
- memory mutations have integrity hashes/audit trail;
- high-risk mutations require human approval;
- adversarial prompt/memory-poisoning tests are mandatory.

## 13. Replication and backup

Live state replication is logical/event/snapshot based, never raw cross-device SQLite WAL sharing.

Target copies:
- B-EDGE: live V2 state;
- PC: near-line verified replica;
- remote/Drive: bounded sanitized/encrypted recovery projections/snapshots.

Context projections are derived products and can be rebuilt from canonical memory.

## 14. Zero-dollar and outage behavior

If BCP NEXUS/cloud is unavailable:
- B-EDGE and PC continue locally;
- Telegram remote ingress may degrade/delay;
- Drive-connected bootstrap may serve as read fallback if current;
- no paid failover.

If B-EDGE is offline:
- NEXUS can expose last verified context projection and queue commands;
- PC does not silently promote itself without witness/user promotion rules.

If PC is offline:
- B-EDGE continues context/memory/scheduling/remote reasoning;
- heavy jobs become `WAITING_FOR_PC`.

If all external AI capacity is exhausted:
- context/memory/scheduler remain operational;
- deterministic work continues;
- semantic tasks enter `FREE_MODEL_CAPACITY_HOLD`.

## 15. Current implementation gap

As of adoption:
- current Android `EdgeOrchestrator` still stores context/memory/job queue in SharedPreferences;
- current Android module does not yet implement the target Room/SQLite + WorkManager memory/scheduler fabric;
- current V2 documents already define the intended migration;
- therefore this Context Fabric is DESIGN_HARDENED but not RUNTIME/FIELD VERIFIED.

Do not claim the universal bootstrap or dedicated-phone memory fabric is operational until the implementation and tests exist.

## 16. Acceptance tests

### Bootstrap/context
- fresh ChatGPT conversation + `BCPGO` recovers global policy and correct project without user reconstruction;
- warm path does not broad-scan repositories/Drive;
- same revision yields `UNCHANGED`;
- one changed preference yields bounded `DELTA`;
- wrong/ambiguous project hint does not leak another project's content;
- stale projection is labeled;
- corrupted hash is rejected;
- Context Pack remains bounded;
- context critical-policy recall is 100% on test corpus;
- irrelevant memory inclusion rate is measured and bounded.

### Memory quality
- explicit user preference supersedes older preference;
- external webpage cannot become user preference;
- model-proposed fact cannot overwrite machine-verified fact;
- stale operating fact expires;
- selective forgetting/compaction preserves canonical evidence;
- memory poisoning corpus cannot create privileged policy;
- privacy extraction tests do not expose unrelated project memory.

### Three-node continuity
- B-EDGE loss;
- PC loss;
- NEXUS loss;
- pairwise network partitions;
- delayed duplicate commands;
- coordinator epoch change;
- cold restore from verified snapshot;
- no split-brain PROJECT_HEAD.

### Android
- process kill;
- phone reboot;
- Doze;
- background restriction;
- low-memory pressure;
- thermal pressure;
- WorkManager duplicate/redelivery;
- delayed push/reconciliation.

### Performance
Measure:
- BCP bootstrap p50/p95;
- Context Pack size p50/p95;
- context cache hit ratio;
- DB query latency;
- B-EDGE RSS p50/p95;
- CPU time/hour;
- wakeups/hour;
- battery drain/hour;
- DB growth/day;
- context retrieval precision/recall on a curated project-memory suite;
- number of LLM calls avoided.

## 17. Migration sequence

Do not break current field-proven P0.

1. preserve Evergreen pairing/update/telemetry line;
2. add Room schema + migrations;
3. move project registry/jobs/checkpoints/memory from SharedPreferences to DB;
4. add WorkManager reconciliation;
5. add structured memory authority/provenance model;
6. add FTS + Context Compiler;
7. generate precomputed GLOBAL/PROJECT context projections;
8. create Drive bootstrap mirror and validate fresh-conversation read path;
9. adopt `BCPGO` universal bootstrap semantics;
10. implement per-turn revision/delta protocol;
11. implement PC verified replica/work envelopes;
12. field-test candidate BCP NEXUS remote gateway/witness under ZERO_USD;
13. add Telegram ingress/push tier;
14. add remote app/MCP/plugin adapter when plan/platform support is real;
15. qualify three-node failure matrix;
16. promote B-EDGE/NEXUS V2 authority only after evidence.

## 18. Research basis and counter-audit conclusions

The design is informed by:
- MemGPT's hierarchical/virtual-context idea: fast and slow memory tiers rather than stuffing all history into one context.
- Generative Agents: retrieval plus reflection/planning; memory usefulness depends on selective retrieval rather than raw accumulation.
- recent personalized-conversation memory research showing memory granularity and compression/denoising materially affect retrieval quality.
- recent memory-agent benchmarks emphasizing retrieval accuracy, long-range understanding, learning and selective forgetting.
- local-first software principles: local availability and user-owned durable data, while avoiding unsafe multi-master merging for authoritative state.
- durable-workflow/event-sourcing practice: deterministic workflow state separated from at-least-once side-effect activities.
- SQLite WAL/transaction semantics: strong local transactional store, but not a network-replication format.
- Android background-execution guidance: persistent correctness must not depend on an immortal process.
- MCP's stateless 2026 core: cross-request application state should use explicit IDs/revisions, which aligns with BCP Context Packs and context leases.
- prompt-injection/memory-poisoning literature and OWASP guidance: external retrieved content and model outputs are untrusted; persistent memory requires strict write admission.

The counter-audit rejects these tempting but weak designs:
- "send all memories to every model call";
- "one huge natural-language profile file";
- "phone process must run forever";
- "every event asks an LLM what to do";
- "three devices may all write PROJECT_HEAD while offline";
- "CRDT solves every synchronization problem";
- "the universal command itself authenticates the user";
- "a free cloud service can be mandatory before Kinshasa field proof";
- "ChatGPT Plus is automatically a writable custom MCP client";
- "a model may decide what becomes canonical memory".

## 19. North-star user experience

Fresh conversation:
`BCPGO`

BCP resolves:
`GLOBAL_CORE + PROJECT_CORE + TASK_DELTA`

ChatGPT should be able to act as if it already knows:
- how the user prefers projects to be run/presented;
- zero-dollar and resource constraints;
- current project architecture and decisions;
- exact current revision/checkpoint;
- what has already failed and why;
- what the next useful action is.

For later messages:
`request -> resolve_context(revision) -> UNCHANGED/DELTA -> answer/action -> validated outcome -> durable state`

The user should stop being the memory bus.


## 24. Integration-mode truth table

BCPGO behavior is constrained by the integration surface actually available.

### Connected Google Drive / connected-store mode
- explicit live file lookup is the baseline;
- do not assume a personal administrator-style synchronized index;
- bootstrap reads stable named projection files;
- acknowledged revisions may remain conversation-local;
- transparent mandatory per-turn resolver invocation is not guaranteed by this mode.

### Qualified remote app/plugin mode
- may expose direct context resolution and revision checks where the ChatGPT product/plan actually permits them;
- read/write capabilities are independently permissioned;
- current Plus architecture MUST NOT assume full custom MCP write/modify support.

### ChatGPT-PC bridge mode
- may provide local high-fidelity context when PC is reachable;
- is not universal-anywhere baseline.

### Manual fallback
- one compact recovery packet only;
- never the normal integration bus.

## 25. Projection publication and integrity

Connected-store projections are derived read models, never canonical memory.

Publication pipeline:
`CANONICAL MEMORY -> CONTEXT COMPILER -> EXPORT FILTER -> INTEGRITY ENVELOPE -> ATOMIC PUBLISH -> READBACK -> CURRENT`.

Integrity metadata SHOULD include:
- schema;
- global/project revision;
- coordinator epoch;
- content hash;
- generated_at;
- expires_at;
- source snapshot/hash;
- signer/key ID where signature verification is supported.

An internal hash detects accidental corruption but is insufficient authentication if both file and hash can be replaced. Risky mutations MUST therefore verify canonical state through an authoritative write path rather than trusting a Drive projection alone.

Previous verified CURRENT is retained until the replacement passes publication/readback.

## 26. Memory export classes

Every memory item intended for Context Fabric compilation MUST be classified:
- `LOCAL_ONLY`;
- `PROJECT_SANITIZED`;
- `GLOBAL_SANITIZED`;
- `EVIDENCE_REFERENCE_ONLY`;
- `NEVER_EXPORT_SECRET`.

Default for unknown sensitivity is non-export.

Provider credentials, BCP bearer tokens, pairing secrets, encryption/recovery keys and unrelated private project content are never placed in remote context projections.

## 27. NEXUS capability separation

BCP NEXUS capabilities are separately authorized:
- `INGRESS`: accept/deduplicate/queue bounded commands;
- `CONTEXT_READ`: serve sanitized projections;
- `WITNESS`: attest coordinator epoch/lease evidence;
- `PROMOTION`: participate in coordinator promotion only under qualified quorum policy.

Ingress credentials MUST NOT grant witness/promotion authority.

Until witness behavior is independently security- and field-qualified, coordinator failover remains explicit-user-promotion or HOLD rather than automatic.

## 28. Static projection vs live task delta

The connected-store baseline exposes precomputed GLOBAL_CORE, PROJECT_CORE and optional revision delta.

A truly request-specific TASK_DELTA requires a live resolver that sees the current task. Therefore:
- Drive-only mode may let the consuming assistant select task-relevant items from the bounded projection;
- live NEXUS/app mode may compute TASK_DELTA;
- architecture MUST NOT claim static storage alone produces live task-semantic deltas.

## 29. Fresh-chat context receipt

BCPGO resolution SHOULD expose a compact, non-secret receipt containing:
- integration mode;
- global revision/hash;
- selected project ID/revision/hash;
- coordinator epoch if exportable;
- generated_at/expires_at;
- resolution state (`UNCHANGED|DELTA|FULL_REFRESH|CONFLICT|DEGRADED|HOLD`);
- projection integrity state.

This receipt is advisory context-cache state only. It cannot advance canonical project state.


### R69 — B-EDGE as the primary persistent appliance node

B-EDGE is not just a memory replica or a network relay. On the dedicated old Android phone it is the preferred persistent low-power appliance node for BCP:
- bounded local API server;
- durable Room/WAL memory, receipts and store-and-forward queue;
- local presence/discovery by LAN NSD, optional Wi-Fi Direct and optional BLE beacon;
- Telegram selective relay while preserving end-to-end TLS;
- lifecycle restart after reboot/app replacement where Android permits it;
- lightweight coordination and continuity while PC-WORKER is absent;
- PC-WORKER receives Windows-only or heavy jobs and remains a replica/worker, not the only control plane.

The phone node must never claim work that requires the PC actually ran. It can queue, coordinate, preserve intent, expose health, relay control and later reconcile receipts.
