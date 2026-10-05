# BCP Autonomic Execution Fabric — Final Pre-Construction Audit A+B+C R3
Date: 2026-10-05
Status: FINAL_PRECONSTRUCTION_AUDIT_R3 / DESIGN SEALED SUBJECT TO FIELD EVIDENCE

## Executive verdict

The program to build is not a new "local AI", not Desktop Commander replacement alone, and not another parallel BCP.

It is a **zero-touch autonomic execution system** that makes ChatGPT the primary conversational intent/planning interface while durable local/edge components execute, reconcile, self-heal, update, acquire bounded new capabilities and preserve work across hours/days/weeks.

Normal target UX:
**Speak -> verified result.**

The system is allowed to fail. It is not allowed to repeatedly make the user perform avoidable technical mechanics for the same class of failure.

---

# A — REALITY, INHERITANCE, ANTI-REINVENTION

## A1. Target constraints

Field design center:
- Windows 11 PC, ~4 GB RAM;
- normal memory pressure often already ~85–95%;
- intermittent Internet/power;
- low/zero budget preference;
- long-running project work;
- user wants ChatGPT as primary interface;
- Desktop Commander has quota and cannot be required;
- user operates multiple projects concurrently.

Consequences:
- one lightweight resident PC control process target;
- one heavy PC worker globally;
- event-driven, not aggressive polling;
- local durable state;
- disk-first/chunked background work;
- no local LLM required;
- no metered external provider required for correctness.

## A2. Existing assets that MUST be reused

### BCP
Already contains substantial durable mission/job/event/memory/recovery/resource/Telegram/B-EDGE infrastructure.

Role:
canonical cross-project mission/policy/memory/validation/evidence authority.

### ChatGPT-PC / G6
Already contains:
- AgentCore/autopilot/update/capabilities;
- G6 Mission IR, Skill Manifest, authority, side-effect journal, Package Head/A-B/recovery contracts;
- local-first RFC-0001 microkernel design;
- project/runtime capability infrastructure.

Role:
PC-node engineering plane and lazy skill/capability provider.

### ChatGPT-PC RFC-0001
Adopt as PC-node vNext baseline:
- resident microkernel;
- lazy workers;
- transactional local outbox;
- local SQLite;
- Job Object containment;
- Drive off critical path;
- Project Capsules;
- no cloud boot dependency.

### MAXV Local Worker / W5
Reuse principles:
- supervisor/worker;
- approved runner;
- STOP/recovery;
- transactional update/rollback;
- OPEN -> EXECUTE -> OBSERVE/VERIFY -> COMMIT;
- idempotency;
- fast/memoryless resume;
- local heartbeat authority; Drive best-effort mirror.

### PC Command
Role:
Windows capability pack + optional viewer.
Do not retain a competing mission kernel.

### BuildHub
Role:
generic build/test/package executor.
External CI is accelerator, not boot dependency.

### ChatGPT Delivery
Role:
artifact transport / Drive / Telegram provider.
Not mission authority.

### AX150K
Role:
incident/regression/anticipation producer.
No direct unvalidated system mutation.

## A3. Latest-source rule

At construction start, NEVER assume the 2026-10-05 snapshot heads are still current.

Required Source Preflight:
1. fetch current BCP main and PR/design branch;
2. fetch current ChatGPT-PC main;
3. fetch current BuildHub main;
4. fetch PC-COMMAND-STATE;
5. inspect relevant open PRs/branches and current release pointers;
6. compare current reality to this R3 contract;
7. preserve newer compatible improvements;
8. reject regression to older design merely to match this document.

Current snapshot examples are evidence, not future authority.

## A4. Anti-reinvention hard rules

Do NOT build:
- a second Model Broker;
- a second Resource Governor;
- a second canonical mission DB;
- another project-specific queue;
- another generic updater;
- another resident heavy AgentCore beside BCP/G6;
- a new MAXV-like worker from scratch;
- a new Telegram/Drive control plane per project;
- a permanent local 1B+ LLM;
- Docker/Kubernetes/WSL as required substrate.

Implementation is primarily **convergence + missing capabilities + proof**, not greenfield orchestration.

---

# B — TARGET PRODUCT / AUTONOMIC ARCHITECTURE

## B1. Two first-class primitives

### Durable Mission
Finite work:
- build;
- repair;
- analyze;
- send;
- generate;
- test.

### Desired State Resource
Persistent invariant:
- component remains healthy;
- project stays on latest qualified release;
- update channel remains valid;
- launcher remains functional;
- only one heavy worker;
- delivery provider remains healthy.

## B2. Mandatory controllers — logical modules, not separate daemons

- MissionController
- DesiredStateController
- ResourceController
- CapabilityController
- CapabilityFactoryController
- ReleaseController
- TransportController
- ArtifactController
- ContextController
- FrictionController
- IncidentController
- PortfolioController
- ComputePlacementController

They share:
- event bus;
- SQLite/local state;
- Chronicle;
- Resource Governor;
- receipts/evidence.

## B3. Mandatory Golden Path

For machine-effect requests:

ChatGPT intent
-> BCP context projection
-> existing capability lookup
-> durable mission / desired state
-> execute
-> observe
-> verify
-> commit
-> receipt
-> concise user result.

If capability is absent:
-> Capability Factory.

Normal mode MUST NOT fall back directly to:
- "download this CMD";
- "paste this PowerShell";
- "send me a screenshot";
- "copy this log";
unless all qualified machine recovery/execution paths are genuinely unavailable.

## B4. Capability Factory

A universal system cannot pre-code every future tool.

Pipeline:
GAP_DETECTED
-> DEFINE CONTRACT
-> REUSE SEARCH
-> SOURCE/LICENSE/TRUST REVIEW
-> BUILD/ADAPT
-> STATIC VALIDATION
-> SANDBOX
-> RESOURCE TEST
-> SECURITY TEST
-> ROLLBACK TEST
-> CANARY
-> REGISTER
-> RESUME ORIGINAL MISSION
-> INCIDENT/RECIPE/REGRESSION LEARNING.

New capability code is a versioned artifact, never ad-hoc self-modification.

## B5. Universal execution ladder

Prefer:
1. internal BCP;
2. direct provider API/connector;
3. Win32/WMI/CIM/PowerShell/Git/CLI;
4. WinGet/DSC desired state;
5. BuildHub/software factory;
6. semantic browser automation;
7. Windows UI Automation;
8. input/vision fallback;
9. irreducible human gate.

## B6. Quota independence

Desktop Commander classification:
**EXTERNAL_METERED_OPTIONAL**.

It is:
- optional accelerator;
- compatibility/break-glass provider;
- NOT required for boot;
- NOT required for recovery;
- NOT required for mission durability;
- NOT canonical authority.

Quota exhaustion:
- no retry storm;
- no auto purchase;
- migrate eligible tasks to local/native equivalents;
- block only provider-exclusive dependent branches.

The core must pass certification with Desktop Commander completely absent.

## B7. Long-horizon execution

Missions may last:
- minutes;
- 6 hours;
- overnight;
- days;
- one week+.

Every long mission becomes a DAG of bounded work units.

Protocol:
OPEN -> EXECUTE -> OBSERVE -> VERIFY -> COMMIT.

Resume classes:
- RESUME_NATIVE;
- REPLAY_IDEMPOTENT;
- OBSERVE_BEFORE_RETRY;
- NONRESUMABLE_ATOMIC;
- EXTERNAL_JOB_HANDLE;
- NEEDS_REASONING.

No multi-hour opaque NONRESUMABLE_ATOMIC step.

## B8. Conversation independence

ChatGPT is primary planning/reasoning interface, not the runtime clock.

After a turn ends:
- already-planned deterministic authorized work continues;
- desired-state reconciliation continues;
- builds/tests/indexing/transfer/verifications may continue;
- novel reasoning pauses at NEEDS_REASONING;
- independent branches continue.

New conversation receives exact current context projection.

## B9. Operational Digital Twin

SQLite + Chronicle + reconstructible projections track:
- devices;
- projects;
- roots/repos;
- versions;
- processes/services;
- capabilities;
- missions;
- desired states;
- artifacts;
- updates;
- incidents;
- resources;
- provider/quota status.

No heavy graph DB.

## B10. Self-healing ladder

L0 observe
L1 reconcile expected state
L2 validated recipe
L3 bounded restart
L4 rollback LKG
L5 reprovision exact qualified component
L6 Capability Factory
L7 ChatGPT/human.

Reinstall is late, not first response.

## B11. Update fabric

DISCOVER
-> STAGE
-> VERIFY hash/provenance
-> TEST
-> CANARY
-> ACTIVATE
-> HEALTHCHECK
-> COMMIT

Failure:
-> ROLLBACK -> LKG.

No blind @latest critical path.

Use TUF-like anti-rollback/freshness/integrity properties and SLSA/in-toto-style provenance where practical.

## B12. Resource law

User foreground > BCP background.

Modes:
SURVIVAL / PRESSURE / NORMAL / RELAXED.

Admission considers:
- available memory;
- commit/pagefile;
- hard faults;
- CPU;
- disk;
- foreground activity;
- worker RSS;
- power;
- network.

One heavy PC worker.

No local model by default.

## B13. PC-node implementation baseline

Adopt ChatGPT-PC RFC-0001 local-first microkernel as vNext design baseline.

Do not run two full resident control planes.

Construction must benchmark current BCP Windows runtime vs G6/vNext components and converge to **one lightweight resident PC control process**.

RFC-0001 design targets are aspirational until field-proven:
- <=45 MiB GREEN;
- <=36 MiB AMBER;
- <=28 MiB RED/CRITICAL.

## B14. Privilege

Standard core = normal user.

Pre-authorize scoped Capability Grants:
- P0 read;
- P1 safe write;
- P2 project mutation;
- selected P3 bounded system operations.

P4 destructive/security operations always fresh approval.

Evaluate JEA first for suitable Windows privileged capabilities before custom privileged service.
If custom helper is required:
- least privilege;
- typed actions only;
- explicit IPC ACL;
- no generic admin shell;
- no direct model text execution.

## B15. Local AI

Not installed in initial build.

Optional later:
- FunctionGemma 270M: specialized function/tool routing;
- Qwen2.5-Coder-0.5B quantized: tiny code/log tasks;
- stronger 8 GB phone node.

Promotion requires measured verified useful work > resource/reliability cost.

---

# C — CONSTRUCTION PROTOCOL / VERIFICATION / DELIVERY

## C1. Program ownership

BCP repo:
- program authority/contracts;
- B-EDGE/coordinator;
- durable mission/desired-state convergence;
- policy/evidence schemas.

ChatGPT-PC repo:
- PC local-first microkernel;
- G6 skills/providers;
- PC runtime adapters.

BuildHub:
- build/test/package provider.

PC-COMMAND-STATE/runtime:
- Windows capability source/viewer to adapt/migrate.

Delivery:
- artifact transport provider.

Do not move code merely for aesthetics.

## C2. Construction branches

Never develop directly on main.

At construction start:
- refresh all current heads;
- create dedicated implementation branches from current compatible heads;
- retain PR #168/design docs as specification input;
- reconcile if current main advanced;
- use serialized merge/lease for mutation.

## C3. Phase 0A — Repository preflight (starts immediately even if PC is offline)

Read-only/engineering:
- inventory current code implementing R3 concepts;
- map KEEP / ADAPT / MERGE / RETIRE;
- map existing tests;
- identify duplicate daemons/startup/update/queue code;
- map RFC-0001 implemented vs design-only;
- define first vertical slice;
- create exact field probe.

No runtime installation.

## C4. Phase 0B — PC capability probe

When PC reachable:
read-only:
- current processes and startup hooks;
- BCP/G6/MAXV/PC Command/Desktop Commander state;
- actual RAM/commit/pagefile/hard faults;
- disk/CPU;
- PowerShell/Git/Node/Python;
- Drive;
- project roots;
- services/tasks/ports;
- current local models;
- current installed versions.

Produce signed/hashed probe receipt.

## C5. First vertical slice — MUST be useful before broad platform build

Reference goal:
**Med Rebuild zero-touch local repair path without Desktop Commander dependency.**

Prove:
1. ChatGPT intent -> durable mission;
2. local PC microkernel receives mission;
3. project registry resolves Med Rebuild;
4. native capability inspects project/runtime;
5. repair/test branch executes;
6. Job Object contains worker;
7. evidence/readback;
8. receipt;
9. interrupted run resumes;
10. Desktop Commander absent does not block.

Do NOT start by building every future controller.

## C6. Construction sequence

### Phase 1 — Contract convergence
- map R2 bridge schemas to G6 canonical contracts;
- no semantic weakening;
- normalize receipts/capabilities/project records.

### Phase 2 — PC microkernel convergence
- one resident process target;
- local DB/outbox;
- worker supervisor;
- Job Objects;
- resource admission;
- startup/recovery.

### Phase 3 — Project Registry + Med Rebuild adapter
- local roots/repo bindings;
- health checks;
- project locks;
- native Windows/Git/files/test capabilities.

### Phase 4 — Desired State + Recipe/Incident engine
- persistent resource reconciliation;
- known repair recipes;
- friction events.

### Phase 5 — Release/update controller
- staged qualified updates;
- LKG rollback;
- provenance;
- migration safety.

### Phase 6 — Transport/cockpit
- ChatGPT bridge;
- Drive store-forward;
- Telegram cockpit;
- Nexus/B-EDGE where field-live.

### Phase 7 — Capability Factory
- safe reuse/build/register pipeline;
- sandbox/canary;
- security/resource gates.

### Phase 8 — Cross-project adapters
- TLIB;
- Excellentia;
- Delivery;
- BuildHub;
- PC Command;
- PhoneMouse/P2PCR95;
- others.

### Phase 9 — Long-horizon/chaos certification
- quota exhaustion;
- reboot;
- PC off;
- network loss;
- provider switch;
- 6-hour build;
- 7-day mission;
- new ChatGPT conversation.

### Phase 10 — Optional local AI qualification
Only after non-AI zero-touch core passes field gates.

## C7. Mandatory verification cycle per tranche

Every tranche:
1. implement;
2. static audit;
3. unit/integration tests;
4. counter-audit against ABC contract;
5. chaos/failure injection appropriate to tranche;
6. resource check;
7. security/authority check;
8. exact readback;
9. receipt;
10. update Chronicle/build ledger;
11. only then continue.

No "looks good".

## C8. Mandatory anti-false-PASS rules

Never claim:
- installed from file existence alone;
- running from process spawn alone;
- healthy from HTTP 200 alone if deeper oracle exists;
- completed from exit code alone;
- progress from elapsed time;
- field-certified from CI/simulation alone.

Evidence must bind exact:
- revision;
- task/mission;
- environment;
- target;
- artifact hash where relevant;
- verifier.

## C9. Long-session autonomy

The construction project itself must use the same design principles:
- persistent build ledger;
- exact next step;
- checkpoints;
- no need for user "continue" for ordinary work inside a turn/tool session;
- on tool/provider limit, preserve state and continue with available alternatives;
- no promise of hidden asynchronous ChatGPT reasoning after turn end.

## C10. Construction safety authority

Pre-authorized for construction:
- read all connected project sources;
- create development branches;
- create/update project-scoped files on development branches;
- run CI/tests/builds where quotas/resources allow;
- create docs/schemas/tests;
- create draft PRs;
- use BuildHub;
- generate field probes.

Not pre-authorized:
- destructive personal-file deletion;
- arbitrary security weakening;
- P4 operations;
- irreversible production data migration;
- blind main merge without gates;
- spending/purchasing quota.

## C11. "Stop and ask" is narrow

Do not ask the user for technical facts the machine/repositories can discover.

Human gate only for:
- irreversible ambiguity;
- external authentication/2FA/CAPTCHA;
- account/payment/legal decision;
- P4 destructive/security action;
- physical action.

Otherwise make best effort and continue.

## C12. Definition of Construction Ready

The new project may begin implementation when:
- Source Preflight complete;
- design branch/PR #168 read;
- RFC-0001 read;
- G6 contracts read;
- current repos mapped;
- no new competing core planned;
- Phase 0A ledger created.

PC access is NOT required to start Phase 0A.

## C13. Definition of First Real Success

Not "architecture written".

Success requires one real end-to-end Med Rebuild flow where:
- user gives natural-language intent;
- no manual CMD/PowerShell relay;
- native local path executes;
- interruption/reboot is recoverable;
- Desktop Commander absent/quota exhausted;
- result is independently verified.

## C14. Final ABC invariant

A = reuse real system/history and constraints.
B = build the zero-touch autonomic target.
C = prove every effect and survive real failures.

If any implementation violates A, B or C, it is not BCP Autonomic Execution Fabric.
