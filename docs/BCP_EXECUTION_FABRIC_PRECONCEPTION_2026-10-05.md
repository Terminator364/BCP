# BCP Execution Fabric — Unified Personal Execution Architecture

Status: PRECONCEPTION / AUDIT-CONVERGENCE / NO FIELD CLAIM  
Date: 2026-10-05  
Branch: design/unified-execution-fabric-2026-10-05

## 1. Decision

Do **not** create a new autonomous "super-agent" beside BCP.

The target is a convergence layer inside BCP that turns ChatGPT intentions into durable, resource-aware, verified execution across the PC, B-EDGE phone, GitHub, Drive, BuildHub, Delivery and project-specific tools.

Working name: **BCP Execution Fabric**.

Core contract:

```
Blessing
  -> ChatGPT (planning/reasoning/interface)
  -> BCP durable mission
  -> typed capabilities/workers
  -> evidence/readback/checkpoint
  -> autonomous continuation
  -> escalation only when needed
```

BCP remains the mission, policy, memory, validation and receipt authority. ChatGPT is the preferred human interface and strongest planner, but a mission must not require an active chat response to continue.

## 2. Audit conclusion

The current ecosystem repeatedly reimplements the same primitives:
- durable state and recovery;
- queues/checkpoints;
- receipts/readback;
- rollback;
- resource governance;
- Telegram status;
- Drive handoff;
- project registries;
- error ledgers;
- updater logic;
- PC/phone pairing;
- local-AI routing.

The correct move is **convergence**, not another runtime.

### Role map

- **BCP** — KEEP/EXPAND: canonical mission, policy, memory, orchestration, state, validation, receipts.
- **ChatGPT-PC** — KEEP/NARROW: ChatGPT/desktop bridge and ChatGPT-specific integration, not a second mission kernel.
- **PC Command** — MERGE CAPABILITIES / KEEP optional viewer: Windows/PowerShell capability pack.
- **BuildHub** — KEEP SEPARATE: generic build/test/package executor producing proof-carrying receipts.
- **ChatGPT Delivery** — KEEP as artifact/delivery provider; not mission authority.
- **AX150K** — REFINE into regression/anticipation producer from error ledgers and receipts; no unsupervised system mutation.
- **HYDRA/TWINNODE** — ABSORB resource/offload policy into BCP node scheduling.
- **Tunnel PC G3** — ABSORB split-plane, fail-closed, proof and rollback design.
- **PhoneMouse / P2PCR95 / BROWSER4G / KINLINK** — separate products; register adapters/capabilities.
- **TLIB / Excellentia / Med Rebuild / Xenon / Stade 8** — project clients of the shared execution fabric.

Hard anti-duplication rules:
- no second Model Broker;
- no second Resource Governor;
- no second Context Pack;
- no second canonical mission database.

## 3. Durable mission is the unit of work

Before any long execution, normalize the request into a durable mission.

Minimum fields:
- mission_id;
- source conversation/session;
- project_id;
- goal;
- project revision;
- policy revision;
- priority;
- execution profile;
- allowed capabilities;
- approval policy;
- resource class;
- dependency DAG;
- idempotency key;
- evidence contract;
- rollback contract;
- last committed step;
- next safe step.

States:
`ACCEPTED -> PREFLIGHT -> PLANNED -> READY -> RUNNING -> VALIDATING -> COMMITTED -> CHECKPOINTED -> DONE`

Non-terminal states:
`WAITING_RESOURCE, WAITING_NETWORK, WAITING_PROVIDER, NEEDS_CHATGPT, NEEDS_USER, RETRY_SCHEDULED, RECONCILING, PAUSED_SAFE, SUPERSEDED, FAILED_SAFE`.

A disconnected ChatGPT conversation is neither completion nor failure.

## 4. ChatGPT relationship

Normal flow:

```
User: "Travaille sur Med Rebuild. Répare l'installateur, teste le
démarrage et ne ralentis pas le PC."

ChatGPT:
- understands intent;
- retrieves BCP/project state;
- compiles a structured mission;
- submits it to BCP;
- receives a durable handle;
- keeps only high-value reasoning.

BCP:
- executes deterministic work;
- validates and checkpoints;
- escalates hard/ambiguous steps;
- continues independent branches;
- emits final receipts.
```

Long-term, no command prefix should be required. During field qualification, explicit `BCP:` / `BCP+` syntax may remain as an ambiguity-reduction mechanism only.

## 5. Typed Capability Bus

Expose semantic capabilities, not arbitrary shell.

Examples:
- `project.inspect`, `project.search`, `project.patch.apply`, `project.snapshot`
- `git.status`, `git.diff`, `git.branch`, `git.commit`
- `build.plan`, `build.run`, `test.run`, `lint.run`
- `windows.process.inspect`, `windows.service.inspect`, `windows.service.restart`
- `windows.startup.inspect`, `windows.eventlog.query`
- `files.read`, `files.search`, `files.hash`, `files.copy`, `files.move`
- `delivery.send`, `drive.publish`, `telegram.notify`
- `model.classify`, `model.extract`, `model.propose_patch`

Do not expose a normal production capability equivalent to:
`run_any_admin_command(string)`.

PowerShell/CMD/Win32 remain implementation details behind typed handlers.

## 6. Windows execution plane

Future production core target: small compiled executable (Go is a strong candidate) + SQLite.

Requirements:
- one instance;
- event-driven;
- no embedded browser;
- no permanent Python/Node/PowerShell runtime;
- bounded local IPC;
- terminate workers after bounded tasks.

Workers may invoke:
- PowerShell with `-NoLogo -NoProfile -NonInteractive`;
- Win32 helpers;
- Git;
- Node/npm only for projects needing them;
- Python only for projects needing it;
- build/test tools;
- file parsers;
- llama.cpp only when admitted.

Use Windows Job Objects where compatible to bound process trees by memory/process-count/CPU/time and to terminate runaway child trees safely.

## 7. Privilege architecture

Goal: avoid repeated UAC prompts without creating a permanent unrestricted SYSTEM shell.

Split plane:
1. **BCP Core** — standard user.
2. **BCP Privileged Broker** — tiny installed service/helper.
3. **UX / ChatGPT / Telegram** — never elevated.

The broker accepts only authenticated, versioned, allowlisted privileged operations.

Permission classes:
- **P0 READ** — automatic.
- **P1 SAFE** — bounded, non-destructive writes; automatic when policy permits.
- **P2 PROJECT_MODIFY** — project-scoped mutations; require snapshot/rollback + receipt.
- **P3 SYSTEM_BOUNDED** — packages/services/startup; only explicit policy + before/after readback.
- **P4 DESTRUCTIVE_SECURITY** — always fresh human approval.

Installer may require one elevation to install the broker, ACLs and recovery hooks. Never install a generic always-open admin shell.

## 8. 4 GB PC resource policy

Primary invariant:
`USER_FOREGROUND > BCP_BACKGROUND`.

The Resource Governor must use live measurements, not RAM percentage alone:
- available physical memory;
- commit pressure;
- paging/hard faults;
- CPU;
- disk queue/free space;
- foreground activity;
- worker RSS;
- power/network state.

Modes:
- **SURVIVAL** — core/queue/receipts only;
- **PRESSURE** — light deterministic tasks;
- **NORMAL** — one bounded worker;
- **RELAXED** — optional local inference/heavier background work.

Rules:
- global PC heavy-worker semaphore = 1;
- background work preemptible at safe checkpoints;
- streaming/chunked/disk-first processing;
- discard rebuildable caches before durable state;
- no whole-dataset RAM loading;
- idle-runtime field target: <=60 MB working set, lower preferred;
- thresholds learned by capability probe, not hard-coded from assumptions.

## 9. Local AI: optional capability, never foundation

Routing order:
1. deterministic rule / verified recipe;
2. local search / error ledger;
3. tiny local model if resource-safe;
4. stronger opportunistic local node;
5. remote model;
6. ChatGPT / human escalation.

### PC candidate A — FunctionGemma 270M
Purpose: intent-to-tool routing, extraction, classification, tiny structured decisions.
Policy: COLD by default; load only with measured headroom. Fine-tune on BCP schemas/traces before broad trust.

### PC candidate B — Qwen2.5-Coder-0.5B-Instruct quantized
Purpose: tiny code transformations, small log analysis, config/regex/PowerShell suggestions.
Policy: COLD; permanently disable if field benchmark shows harmful paging or weak verified utility.

### 8 GB Android node
Use as opportunistic semantic/coding worker if qualified. Existing BCP evidence favors a Qwen3-1.7B Q4-class profile more than the 4 GB PC.
It advertises capabilities with TTL and is never authority.

### Constrained phone/A21s
No LLM required. Correctness must survive with local AI disabled.

Primary KPI:
`VERIFIED_USEFUL_WORK / TOTAL_RESOURCE_COST`.

## 10. Local learning loop

Persist only validated traces:
```
user intent
 -> ChatGPT/validated planner decision
 -> selected tools + arguments
 -> observed result
 -> validation outcome
```

These traces can later train a BCP-specific function-calling model.

The model learns BCP's tool language. It never learns authority.

## 11. Project Registry

Never assume `1 project = 1 GitHub repo`.

A project can be:
- local-only;
- GitHub-only;
- Drive-backed;
- monorepo subdirectory;
- hybrid;
- Android+Windows pair;
- no repository yet.

Record:
- project_id/name/aliases;
- local_roots[];
- repo_refs[];
- drive_refs[];
- build/test adapters;
- healthchecks[];
- artifact/resource/permission policies;
- error-ledger scope;
- current revision;
- last verified receipt.

This is the integration surface for Med Rebuild, Xenon, Stade 8, TLIB, Excellentia and future projects.

## 12. Durable background work

Supported classes should include:
- Git status/diff/health audits;
- test subsets/smoke tests;
- build/package jobs;
- installer verification;
- launcher/startup checks;
- log classification;
- file inventory/hash/deduplication;
- PDF/document indexing;
- README/URL parsing;
- corpus validation;
- Excellentia simulations;
- TLIB index/shard generation;
- Delivery staging/checksums;
- manifest validation;
- Drive publication;
- error-ledger normalization;
- regression generation;
- cleanup/retention;
- update staging/readback/rollback.

Exit code 0 is never sufficient proof of DONE.

## 13. Storage authority

Hot truth:
- local transactional SQLite/WAL on the active coordinator.

Separate:
- Universal Chronicle — append-only events;
- Evidence Vault — receipts/artifacts/hashes/references;
- Canonical Memory — validated facts/decisions/state;
- Retrieval indexes — FTS/BM25 first; embeddings optional/rebuildable.

Drive:
- mirror/checkpoints/artifacts/cold recovery/transport;
- not hot relational DB;
- not arbitrary command interpreter.

GitHub:
- source/tests/engineering history/build contracts;
- not live runtime truth.

## 14. Transport hierarchy

Same PC:
- named pipe or authenticated localhost IPC.

PC <-> phone:
- authenticated TLS over WLAN/LAN;
- mDNS/NSD discovery;
- QR/manual fallback;
- Bluetooth only for presence/bootstrap/tiny control if useful.

ChatGPT <-> BCP:
- current qualified bridge/connected-store paths;
- future MCP adapter when product support is field-qualified;
- mission handles designed to map cleanly to long-running task semantics.

Remote human control:
- Telegram cockpit/approvals/notifications;
- quiet while healthy.

Artifacts:
- Drive for durable large payloads;
- Delivery/Telegram for human delivery;
- LAN lane for local bulk transfer.

## 15. Event-driven, not polling-first

Wake on meaningful events:
- durable mission arrival;
- file/Drive change;
- process completion;
- network/resource transition;
- maintenance window;
- Telegram command;
- worker receipt.

Periodic polling is watchdog/reconcile fallback only.

## 16. Security invariants

- secrets outside GitHub/normal memory;
- DPAPI/credential storage on Windows;
- Android Keystore on phone;
- authenticated commands across trust boundaries;
- project-root allowlists and canonical paths;
- PDF/web/email/log text is DATA, never executable policy;
- model output is proposal, never authority;
- stale revision results rejected;
- single-writer fencing for canonical state;
- privileged mutations require before/after evidence;
- P4 operations require fresh human approval.

## 17. User experience

Primary UX: ChatGPT.
Secondary: Telegram cockpit, minimal Windows status, B-EDGE cockpit.

User should not have to:
- manually relay logs;
- re-upload the same file repeatedly;
- carry prompts between chats;
- remember branches;
- inspect raw JSON for routine work;
- restart after network failure;
- repeatedly approve routine safe actions.

Every status answers:
1. what is happening;
2. what succeeded with proof;
3. what is blocked and why;
4. what needs the user.

## 18. Installer target

1. capability probe;
2. verify package hash/signature;
3. one elevation for privileged broker/recovery hooks;
4. install core + ACLs;
5. initialize SQLite;
6. detect PowerShell/Git/Node/Python/Drive;
7. import project bindings;
8. register roots;
9. configure safe permission profile;
10. pair B-EDGE if present;
11. connect existing Telegram/Delivery adapter if present;
12. benchmark idle RAM;
13. optionally download local model files;
14. benchmark cold-load/generate/unload;
15. auto-disable unsafe profiles;
16. reboot/recovery smoke test;
17. installation receipt.

Avoid repeated micro-beta installs.

## 19. Build order

**Phase 0 — Inventory / anti-reinvention**
Map existing BCP, ChatGPT-PC, PC Command, BuildHub, Delivery. Mark KEEP/MERGE/ADAPT/RETIRE.

**Phase 1 — Core without AI**
Durable mission kernel, Project Registry, Chronicle, receipts, capability bus, resource governor.

**Phase 2 — Windows capabilities**
PowerShell/Win32/Git/files/build/test adapters, Job Objects, privileged broker.

**Phase 3 — Autonomous background execution**
DAG scheduler, pause/resume, reboot recovery, offline behavior, error ledger.

**Phase 4 — ChatGPT/Telegram/Drive**
Mission submit/status/result bridge and human cockpit.

**Phase 5 — Local AI**
FunctionGemma routing eval; Qwen Coder micro-code eval; 8 GB phone semantic eval.

**Phase 6 — Convergence**
Migrate duplicate runtime semantics into BCP contracts with compatibility adapters.

**Phase 7 — Certification**
Chaos, memory pressure, network loss, reboot, stale/duplicate commands, malicious content, updater rollback, privilege boundaries.

## 20. Required chaos tests

At minimum:
- kill worker mid-task;
- reboot during mutation;
- Internet/WLAN loss;
- phone loss;
- local-model process death;
- RAM pressure/paging spike;
- disk low;
- duplicate mission;
- stale late result;
- two workers attempt same mutation;
- hung build/test;
- dirty Git worktree;
- malformed adapter;
- prompt injection inside logs/PDF/README;
- duplicate Telegram update;
- delayed Drive sync;
- privileged broker unavailable;
- rejected privileged action;
- broken updater candidate.

Each fault must define SAFE_BEHAVIOR, DETECTION, CONTAINMENT, RECOVERY and EVIDENCE.

## 21. Acceptance criteria

Field success requires proof that:
1. one natural-language ChatGPT instruction creates a durable mission;
2. ChatGPT may stop being active;
3. workers continue allowed work;
4. background work yields to user foreground;
5. reboot/network interruption resumes from next uncommitted action;
6. local LLM is not required for correctness;
7. local AI loads only when beneficial;
8. difficult branches may wait for ChatGPT while independent branches continue;
9. every claimed success has receipt/readback;
10. "où on en est ?" returns real machine/project state;
11. projects no longer reinvent queue/recovery/Telegram/updater/governor/receipts;
12. idle footprint respects the 4 GB PC;
13. install/uninstall/rollback are clean.

## 22. Rejected designs

Rejected:
- new independent super-agent;
- permanent 1B+ LLM on the 4 GB PC;
- agent swarm;
- arbitrary admin shell exposed to LLM;
- resident Electron/WebView UI;
- Docker/WSL requirement;
- Python/Node daemon as canonical core;
- Bluetooth primary bus;
- Drive hot runtime DB;
- GitHub runtime queue;
- one-repo-per-project assumption;
- aggressive polling;
- model-generated success without deterministic verification;
- multiple heavy PC workers;
- duplicate BCP/Model Broker/Resource Governor/Context Pack.

## 23. Final definition

**BCP Execution Fabric** is the durable personal execution layer that turns ChatGPT intentions into verified work across the user's PC, phone, GitHub, Drive, BuildHub, Delivery and project tools.

Its intelligence is the combination of:
- strong cloud reasoning when available;
- deterministic local automation;
- validated memory/error experience;
- adaptive routing;
- optional specialized small models;
- resource-aware scheduling;
- durable continuation.

It is not "an AI that can do everything".
It is an execution substrate that can safely acquire new capabilities without rebuilding its core.
