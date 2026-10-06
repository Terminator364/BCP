# BCP Execution Fabric — Sealed Preconception R1

Status: **SEALED_PRECONCEPTION_R1 / DESIGN ONLY / NOT FIELD-CERTIFIED**  
Date: 2026-10-05  
Supersedes: the incomplete assumptions in `BCP_EXECUTION_FABRIC_PRECONCEPTION_2026-10-05.md` where this document is stricter.

## 0. What is being built

BCP Execution Fabric is not a local chatbot and not a replacement for ChatGPT.

It is a **durable personal execution substrate** that lets ChatGPT turn natural-language intent into verified work across the user's projects and devices, then continue allowed work without requiring an active ChatGPT turn.

The key product promise is:

> The user expresses intent once. ChatGPT plans. BCP persists the mission. The least expensive qualified capability performs each step. Work survives interruption. Success is claimed only with readback evidence.

The runtime must be valuable with:
- no local AI;
- no Desktop Commander;
- no GitHub availability;
- no Drive availability;
- no Telegram availability;
- no B-EDGE availability;
- no Internet for purely local work.

Loss of a capability reduces available work; it does not erase mission state.

## 1. Final architecture

```
                         USER
                          |
                   ChatGPT text/voice
                          |
                          v
                 +----------------+
                 |    ChatGPT     |
                 | plan / reason  |
                 | audit / design |
                 +--------+-------+
                          |
                    MISSION PLAN
                          |
                          v
+================================================================+
|                         BCP                                    |
|                                                                |
|  Mission Kernel        Universal Chronicle     Policy Engine    |
|  Project Registry      Capability Registry    Resource Gov.     |
|  Error/Recipe Ledger   Artifact Registry      Model Broker      |
|  Scheduler/DAG         Evidence/Receipts      Update/Recovery   |
+==============================+=================================+
                               |
                    typed capability dispatch
                               |
          +--------------------+---------------------+
          |                    |                     |
          v                    v                     v
  +---------------+    +---------------+     +---------------+
  |  PC WORKER    |    |   B-EDGE      |     | REMOTE/CLOUD  |
  | Windows/files |    | continuity    |     | GitHub/Drive  |
  | Git/tests     |    | LAN/queue     |     | Nexus/Delivery|
  | BuildHub      |    | optional AI   |     | provider APIs |
  +-------+-------+    +---------------+     +---------------+
          |
          +-- Med Rebuild
          +-- Xenon
          +-- Stade 8
          +-- TLIB
          +-- Excellentia
          +-- PhoneMouse
          +-- P2PCR95
          +-- ChatGPT-PC
          +-- other registered projects
```

## 2. Authority model

BCP is an authority **role**, not necessarily one permanent process on one device.

Canonical domains:
- mission state;
- policy;
- canonical project state pointers;
- validated memory;
- receipts/evidence;
- idempotency/fencing.

Target coordinator:
- B-EDGE when V2 coordinator authority is actually field-qualified.

Compatibility:
- PC may remain current authority during migration or operate as a standalone coordinator mode when explicitly promoted.

Never:
- automatic dual-writer guessing;
- PC and B-EDGE independently advancing the same canonical head during partition.

Every authority transition uses coordinator epoch/fencing and is reversible/auditable.

## 3. The mission is not the conversation

A ChatGPT turn can disappear, hit a platform limit, lose Internet, or be closed.

A BCP mission persists:
- goal;
- project;
- current revision;
- plan/DAG;
- permissions;
- resource budget;
- evidence contract;
- last committed step;
- next safe step;
- pending dependencies;
- escalation reason.

ChatGPT may be reattached later by mission ID.

## 4. Capability-loss semantics

Capabilities include:
- Desktop Commander;
- GitHub;
- Drive;
- Telegram;
- BuildHub;
- B-EDGE;
- Nexus;
- local inference;
- browser automation;
- project runtimes.

Each capability has:
- AVAILABLE;
- DEGRADED;
- TEMP_UNAVAILABLE;
- AUTH_REQUIRED;
- RESOURCE_HOLD;
- UNSUPPORTED;
- STALE.

A mission branch requiring an unavailable capability moves to `WAITING_CAPABILITY`.
Independent branches continue.

**Critical invariant:** Desktop Commander failure must never block project-local work that BCP can perform through native file/Git/shell/build capabilities.

## 5. PC reality is the design center

Target field machine:
- Windows 11;
- approximately 4 GB RAM;
- dual-core low-end CPU class;
- mechanical HDD/pagefile pressure may be significant;
- ordinary use may already consume 85–95% RAM;
- Internet/power may be intermittent.

Therefore:
- no architecture requiring large resident heaps;
- no agent swarm;
- one heavy PC job globally;
- foreground user activity always wins;
- disk-first/chunked processing;
- no aggressive process killing or "RAM cleaner" behavior;
- no restart storm;
- background work may pause for hours rather than degrade the user session.

### Resident budget

Field gate:
- preferred incremental idle BCP footprint <= 60 MB;
- maximum target before architectural escalation <= 96 MB;
- near-zero idle CPU and no busy polling;
- resident adapters must be consolidated rather than one daemon per project.

The existing Python runtime is benchmarked before any rewrite.
A Go/native supervisor is a **measured optimization**, not a V1 assumption.

## 6. Resource Governor R2

Do not gate only on "RAM percent".

Admission inputs:
- AvailablePhysicalMemory;
- commit charge / commit limit;
- hard faults/paging;
- disk queue and free space;
- CPU;
- foreground/user activity;
- active worker RSS;
- power/AC/battery;
- network class;
- workload resource class.

Modes:

### SURVIVAL
- Chronicle/queue/receipts only;
- no local model;
- no heavy worker;
- accept/queue missions;
- keep user foreground responsive.

### PRESSURE
- light deterministic reads/checks;
- no heavy build;
- no local AI unless a separately qualified tiny profile proves safe.

### NORMAL
- one bounded worker;
- ordinary tests, file work, Git operations;
- background work only if it remains unobtrusive.

### RELAXED
- heavier background work;
- optional inference;
- bulk indexing/checkpoints.

Mode transitions must have hysteresis/cooldown to avoid oscillation.

## 7. PC local AI — final baseline

### V1 baseline: **NO LOCAL MODEL INSTALLED OR REQUIRED**

Reason:
FunctionGemma 270M is small by LLM standards but Google's own on-device benchmark reports roughly 549–551 MB peak RSS for its tested int8 profile. On a PC commonly operating at 85–95% of ~4 GB, that is too large to make a default dependency.

Therefore the initial "intelligence" comes from:
1. ChatGPT planning when connected;
2. deterministic scheduler;
3. Project Registry;
4. Error/Recipe Ledger;
5. validated rules/recipes;
6. exact tool contracts.

### Optional qualification lane A
`FunctionGemma 270M`
- role: natural language -> BCP tool call;
- requires BCP-specific fine-tuning/evaluation;
- COLD only;
- never authority;
- only promoted after RAM/latency/accuracy field evidence.

### Optional qualification lane B
`Qwen2.5-Coder-0.5B-Instruct` quantized
- role: tiny code/log/config proposals;
- COLD only;
- never allowed to commit unvalidated mutations.

### Preferred stronger local semantic lane
8 GB Android phone:
- opportunistic semantic/coding inference;
- advertised via capability TTL;
- absence is normal.

No project may require a local model to boot, recover, update or execute deterministic work.

## 8. Intelligence without a local model

BCP uses a **Recipe Engine** before any model.

Example error recipe:
```
signature:
  component = desktop_commander_remote
  stderr contains = "JSON"
  process = exits_early

validated recipe:
  preserve device identity
  quarantine corrupt config
  restart exact pinned runtime
  verify process + remote evidence
```

Recipes are generated from real incident history and promoted only after validation.

This turns prior failures into reusable intelligence with almost zero RAM.

## 9. Desktop Commander case study

The current Desktop Commander recovery artifacts demonstrate why the Fabric is needed:
- portable Node/runtime recovery;
- package resolution through npx;
- process discovery;
- regex log classification;
- multiple startup paths;
- watchdog;
- auth/pairing handling;
- repair state;
- manual interpretation after failure.

The existing design is useful evidence but too complex to remain a standalone orchestration pattern.

### Final target

Desktop Commander becomes capability:
`desktop_commander.remote.ensure_available`.

BCP sequence:
1. read current capability state;
2. determine whether the Remote process is actually healthy;
3. reuse exact installed/pinned package/runtime;
4. preserve existing identity/session;
5. start only if needed;
6. use bounded backoff;
7. detect AUTH_REQUIRED distinctly;
8. emit receipt;
9. never reinstall just because remote presence is temporarily unavailable;
10. continue unrelated Med Rebuild work even if Commander remains unavailable.

### Startup correction

Do not use redundant:
- HKCU Run +
- Startup folder +
- logon task +
- frequent watchdog

as the normal architecture.

Select one primary startup/recovery mechanism with one fallback:
- event/logon triggered Task Scheduler, or
- trigger-start service where a true service is justified.

Use a watchdog only for stale-health recovery with cooldown, not as an unconditional restart loop.

### Package correction

Avoid `@latest` in production execution.
Use exact qualified version/hash and update through the shared updater.

Package priming/download is a separate staged update job, never hidden inside the interactive "start Commander" path.

## 10. Med Rebuild scenario

User says in ChatGPT:

> "Continue Med Rebuild. I need the local Commander path working, but meanwhile inspect the installer and fix what can be fixed."

ChatGPT creates one mission with independent branches:

```
MISSION MR-x
 |
 +-- A: desktop_commander.ensure_available
 |
 +-- B: project.git.inspect
 |
 +-- C: installer.static_audit
 |
 +-- D: launcher.healthcheck
 |
 +-- E: targeted tests
```

If A reaches `AUTH_REQUIRED`:
- A pauses;
- B/C/D/E continue;
- user receives one compact approval/action request.

If RAM enters SURVIVAL:
- heavy test pauses;
- static audit and state persistence can continue if safe.

If Internet disappears:
- local B/C/D/E continue;
- remote receipts queue.

If PC reboots:
- BCP reconstructs the mission;
- committed steps are not replayed;
- incomplete effects reconcile before retry.

This is the reference use-case for the entire Fabric.

## 11. Background execution portfolio

### Development
- repo/worktree health;
- build/test/lint;
- launcher/install/update verification;
- artifact hash/signature checks;
- dependency/cache checks;
- log normalization;
- regression generation.

### TLIB
- document inventory;
- hashing/dedupe;
- parse/metadata;
- L1/L2 indexing;
- sharding;
- integrity audits;
- background scanning in bounded batches.

### Excellentia
- corpus uniqueness;
- knowledge_id coverage;
- session simulations;
- offline/sync tests;
- scoring/analytics;
- regression runs.

### ChatGPT Delivery
- staging;
- checksum;
- transport selection;
- Drive publish;
- Telegram delivery;
- retries/readback;
- retention cleanup.

### Medical/library/document work
- local file inventory;
- metadata extraction;
- OCR only when explicitly necessary and supported;
- PDF/text indexing;
- bibliography preparation;
- batch conversions;
- artifact staging for ChatGPT reasoning/delivery.

### PC/system
- diagnostic reads;
- services/ports/processes;
- disk/log health;
- update staging;
- no autonomous destructive cleanup.

## 12. Project Registry R2

A project adapter is declarative and small.

It defines:
- identities/aliases;
- local roots;
- repositories;
- Drive references;
- build/test/health commands;
- safe write scope;
- privileged capability needs;
- resource profile;
- artifact policy;
- updater policy;
- known validated recipes.

The adapter must not contain its own generic scheduler, queue, Telegram stack, resource governor or mission database.

## 13. Windows worker containment

Every non-trivial process tree is launched through a containment wrapper where compatible.

Windows Job Objects are preferred for:
- whole-tree tracking;
- job/process memory limits;
- priority;
- execution accounting;
- bounded termination.

A child process must not silently escape resource governance unless the adapter explicitly declares and tests that requirement.

For Java/Gradle/Node tasks, combine application-native limits with Job Object containment.

## 14. Privilege model R2

The user may accept administrator prompts during initial installation, but installation-time convenience must not produce a permanent unrestricted admin shell.

### Standard plane
BCP core and ordinary workers run as the normal user.

### Privileged plane
Use least-privilege capability-specific execution:
- LocalService where sufficient;
- narrowly configured elevated helper/capsule only for operations that truly require it;
- explicit ACLs on local IPC;
- no network listener on the privileged helper;
- no free-form command string;
- no model access directly to privileged IPC.

Named-pipe ACLs must be explicit; default ACL assumptions are not acceptable.

### Permission classes
- P0 READ;
- P1 SAFE_WRITE;
- P2 PROJECT_MUTATION;
- P3 BOUNDED_SYSTEM_CHANGE;
- P4 DESTRUCTIVE_OR_SECURITY_SENSITIVE.

P4 always needs fresh human approval.

## 15. Transport model R2

Mission state is transport-independent.

Priority is capability-driven, not hard-coded forever.

### Same PC
- named pipe / authenticated localhost IPC.

### PC <-> B-EDGE
- authenticated TLS over WLAN/LAN;
- mDNS/NSD discovery;
- QR/manual fallback;
- Bluetooth only for discovery/bootstrap/tiny control if qualified.

### ChatGPT -> BCP
Possible adapters:
1. direct BCP connector/plugin/MCP when actually supported and field-qualified;
2. BCP Nexus HTTPS ingress when Nexus is live;
3. connected Drive mission mailbox/store-and-forward;
4. Desktop Commander as bootstrap/break-glass execution path.

A typed code such as BCPGO is a context trigger, not a transport by itself.

### Telegram
- human cockpit;
- approvals;
- notifications;
- optional mission ingress;
- not canonical state.

### Drive
- artifact store;
- cold recovery;
- mission store-and-forward fallback;
- never hot DB;
- WAL/SQLite stays on local storage.

## 16. Event-driven Windows lifecycle

Avoid permanent polling where the OS already offers triggers.

Use:
- logon trigger;
- idle/maintenance trigger;
- system event trigger;
- network/resource change event where practical;
- bounded reconciliation timer as fallback.

Trigger-start service is preferred over always-on auto-start for work that only needs to wake on events.

The mission kernel may remain resident only if its measured footprint justifies it. Otherwise a lightweight sentinel can wake the worker.

## 17. SQLite/WAL policy

SQLite/WAL is appropriate for local transactional mission state because readers/writers can coexist efficiently and I/O is mostly sequential.

Rules:
- DB lives on local disk only, never inside a network filesystem/Drive synchronization path;
- one canonical writer per coordinator epoch;
- WAL checkpoints are bounded and preferably scheduled during low activity;
- monitor WAL growth;
- long readers must not starve checkpoints;
- produce logical backups/snapshots rather than raw-copying a live DB/WAL pair.

## 18. Update system

All shared components use one staged updater pattern:
1. discover qualified manifest;
2. download to staging;
3. verify version/hash/signature;
4. static/self-test;
5. resource/admission check;
6. activate atomically or side-by-side;
7. health/readback;
8. commit current pointer;
9. rollback to LKG on failure.

No project should embed a separate ad-hoc updater unless its platform requires a distinct adapter.

Interactive launch paths never perform uncontrolled package upgrades.

## 19. Evidence model

A step is DONE only if its evidence contract passes.

Possible evidence:
- exact exit code;
- output hash;
- file readback;
- process health;
- HTTP health;
- service state;
- Git revision;
- test result;
- artifact signature;
- provider message ID;
- destination readback.

Statuses distinguish:
- command accepted;
- process started;
- result observed;
- result validated;
- state committed.

"Started" is never "done".

## 20. Backlog and cognitive load

BCP maintains a global project backlog:

- INBOX;
- PLANNED;
- READY;
- RUNNING;
- WAITING_RESOURCE;
- WAITING_CAPABILITY;
- WAITING_CHATGPT;
- WAITING_USER;
- RECONCILING;
- DONE;
- FAILED_SAFE;
- SUPERSEDED.

ChatGPT can ask BCP for:
- what is running;
- what changed since last check;
- what needs the user;
- what can run in background;
- what is blocked;
- what is safe to defer.

This is a core feature, not an optional dashboard.

## 21. UX contract

Primary interface: ChatGPT.

The user should be able to say naturally:
- "continue Med Rebuild";
- "fix the launcher";
- "classify these files";
- "run the light checks in the background";
- "where are all my projects?";
- "stop anything heavy";
- "send the finished artifact on Telegram".

BCP converts the request into durable execution.

The user must not normally:
- copy terminal logs;
- carry files between chats;
- remember exact branches;
- rerun commands after reboot;
- repeatedly approve safe routine actions;
- inspect raw JSON;
- manually choose the same transport repeatedly.

Technical detail remains available on demand.

## 22. Explicit anti-patterns

Forbidden as defaults:
- model-first architecture;
- one agent daemon per project;
- permanent browser automation;
- duplicated watchdogs;
- broad SYSTEM shell;
- unbounded PowerShell execution from model text;
- implicit success;
- polling every few seconds;
- auto-kill of unrelated user processes;
- reinstall-as-repair;
- `@latest` in critical runtime paths;
- Drive/GitHub as live mission authority;
- no-receipt completion;
- background work that competes with foreground use;
- hidden provider/network dependency.

## 23. Implementation sequence — final

### Phase 0: Field Capability Probe
No model download.
Read-only inventory:
- RAM/commit/pagefile/hard-fault baseline;
- CPU/disk;
- current BCP/ChatGPT-PC/PC Command/Commander processes;
- PowerShell/Git/Node/Python;
- Drive state;
- project roots;
- startup tasks/services;
- ports;
- existing model files;
- current Desktop Commander identity/runtime and duplicate startup hooks.

### Phase 1: Consolidate the existing Mission Kernel + Project Registry
Do not rebuild BCP mission primitives already present in Windows/B-EDGE.

Observed existing building blocks include Windows SQLite jobs/dependencies/mission_events/memory/resource status/resume requests and B-EDGE Room projects/jobs/dependencies/receipts/events/mission-steps/capability registry.

Phase 1 work is therefore:
- define one provider-neutral mission/receipt/capability contract;
- expose existing queues and Chronicle through that contract;
- generalize the project registry beyond legacy/default projects;
- normalize Windows receipts/evidence with B-EDGE receipts;
- add project adapters;
- prove exact recovery after restart.

### Phase 2: Native Windows Capability Pack
- files/Git/process/service/eventlog;
- Job Object worker wrapper;
- bounded command adapters;
- Desktop Commander adapter;
- updater adapter.

### Phase 3: Resource-Aware Background Work
- single heavy semaphore;
- preemption/checkpoints;
- idle/AC scheduling;
- background TLIB/Excellentia/build tasks.

### Phase 4: Ingress/Cockpit Convergence
- ChatGPT bridge;
- Drive store-forward;
- Telegram cockpit;
- B-EDGE sync;
- Nexus when field-live.

### Phase 5: Privileged Capsules
Only after P0-P2 ordinary execution is proven.

### Phase 6: Local AI Qualification
Only after the non-AI runtime proves value and idle resource compliance.

### Phase 7: Cross-project migration
Retire duplicate queues/watchdogs/updaters gradually behind compatibility adapters.

## 24. Seal gates

Preconception is considered conceptually closed only if all design questions have an explicit answer.

### Architecture
PASS — one mission authority model; typed capabilities; project adapters.

### 4 GB survival
PASS BY DESIGN — no local AI required; one heavy worker; foreground priority; resource modes.

### ChatGPT discontinuity
PASS BY DESIGN — durable mission independent of chat turn.

### PC reboot/network failure
PASS BY DESIGN — checkpoint/reconcile/resume semantics.

### Desktop Commander failure
PASS BY DESIGN — capability loss, not platform failure.

### Project heterogeneity
PASS BY DESIGN — registry supports local/GitHub/Drive/hybrid.

### Security
PASS BY DESIGN — least privilege, typed actions, explicit IPC ACL, no arbitrary admin shell.

### Evidence
PASS BY DESIGN — receipt/readback required.

### Local AI
PASS BY DESIGN — optional, cold, benchmark-gated.

### Transport
PASS BY DESIGN — multiple adapters, no single channel is canonical.

### Updates
PASS BY DESIGN — shared staged update/rollback contract.

### Remaining uncertainty
FIELD ONLY:
- actual PC idle footprint;
- exact installed project roots;
- actual existing startup duplication;
- exact BCP Windows runtime resource profile;
- actual Commander runtime health;
- model benchmark if ever attempted;
- Nexus provider authorization/field availability;
- full B-EDGE coordinator promotion status.

These are not reasons to reopen conceptual architecture. They are Phase 0/field qualification data.

## 25. Final sealed decision

Build **the deterministic durable execution fabric first**.

Do not install a local model merely to make the system feel "AI".

The AI value comes first from ChatGPT planning, BCP memory/recipes, exact project state and safe tool execution. Local inference is promoted later only if measured evidence shows that it creates more verified useful work than the RAM/latency/reliability cost it adds.

This architecture is considered SEALED_PRECONCEPTION_R1 until field evidence contradicts an assumption.


## 26. Repository tri-audit correction

A final repository pass confirmed that this is **not a greenfield mission engine**.

Already present:
- Windows SQLite jobs and dependencies;
- Windows mission_events and memory records;
- Windows mission resume requests and resource status;
- B-EDGE durable project registry;
- B-EDGE jobs/dependencies;
- B-EDGE receipts and idempotency;
- B-EDGE capability registry;
- Chronicle/events and mission-step state.

Therefore the implementation center shifts again:

```
NOT:
new orchestrator -> migrate everything

BUT:
existing BCP primitives
 -> unify contracts
 -> add missing Windows capability/evidence layer
 -> register projects
 -> migrate duplicate project-local infrastructure
```

This materially reduces implementation risk and RAM cost.

The detailed existing-vs-gap inventory is canonical companion:
`docs/BCP_EXECUTION_FABRIC_EXISTING_VS_GAP_MAP_R1_2026-10-05.md`.

Machine contracts added by this preconception:
- `schemas/bcp_capability_manifest_v1.schema.json`;
- `schemas/bcp_mission_envelope_v2.schema.json`.

Reference case:
- `docs/examples/execution-fabric/med-rebuild-commander-mission.example.json`;
- `docs/examples/execution-fabric/desktop-commander.ensure_available.capability.example.json`.
