# BCP Execution Fabric — Autonomic Zero-Touch Architecture R2
Status: PRECONCEPTION R2 / SUPERSEDES R1 WHERE STRICTER
Date: 2026-10-05

## 0. User contract

The target normal experience is:

> User speaks to ChatGPT once. ChatGPT expresses intent. BCP persists both finite missions and persistent desired states. BCP observes reality, executes, verifies, repairs drift, updates itself and acquires new bounded capabilities when necessary. The user is interrupted only for irreducible human gates.

This does NOT promise zero failures. It promises:
- known failures become self-healing recipes;
- novel failures are contained, evidenced and converted into reusable regression/repair knowledge;
- the same avoidable manual intervention should not recur;
- routine technical work does not require the user to copy logs, run commands, move files or repeatedly approve already-scoped safe actions.

## 1. Two execution primitives, not one

R1 introduced durable finite missions.

R2 adds persistent **Desired State Resources**.

### Mission
Finite objective:
- build Med Rebuild;
- send a PDF;
- audit TLIB;
- generate an APK.

Mission ends.

### Desired State
Persistent invariant:
- Desktop Commander capability is healthy when needed;
- Med Rebuild launcher opens correctly;
- BCP core is on the latest qualified release;
- Delivery is healthy;
- project dependencies are installed at qualified versions;
- Drive mirror is eventually consistent;
- only one heavy worker is active;
- background jobs yield to foreground pressure.

Desired state has no one-time "finish". A controller continuously or eventfully reconciles CURRENT -> DESIRED.

## 2. Autonomic control model

BCP adopts a MAPE-K-inspired loop, implemented event-first and resource-aware:

MONITOR
- sensors: files, processes, services, Git state, health endpoints, logs, package state, resource state, provider state.

ANALYZE
- compare actual state to desired state;
- match Error/Recipe Ledger;
- classify drift/failure;
- determine whether a capability is missing.

PLAN
- deterministic reconciler first;
- known recipe second;
- ChatGPT/high-level planner for unknown/complex changes;
- optional model only after qualification.

EXECUTE
- typed capability calls;
- bounded workers;
- staged updates;
- capability acquisition pipeline.

KNOWLEDGE
- Project Registry;
- Capability Registry;
- Desired State Registry;
- Error/Recipe Ledger;
- Chronicle;
- receipts/provenance;
- update/channel state.

## 3. Kubernetes/DSC lesson: desired vs actual state

BCP does NOT copy Kubernetes or run Kubernetes.

It borrows the reconciliation principle:
- desired state is explicit;
- actual state is observed;
- reconcilers are idempotent;
- stale observations do not justify blind replay;
- repeated reconcile calls must be harmless;
- controllers own explicit fields/capabilities.

Microsoft DSC/WinGet Configuration may be used as a provider for Windows package/settings desired state, but BCP remains the mission/policy/evidence authority.

## 4. Intent Plane

Primary interface remains ChatGPT.

A user sentence may compile into:
1. an answer only;
2. a finite Mission Envelope;
3. a persistent Desired State Resource;
4. both.

Example:
"Installe ce qu'il faut et fais en sorte que Med Rebuild marche toujours sans que je m'en occupe."

Compilation:
- mission: repair current Med Rebuild;
- desired state: MedRebuildRuntime/healthy;
- desired state: MedRebuildUpdater/qualified-current;
- capability grant requests if bounded system changes are necessary.

No permanent magic prefix is required.

## 5. Desired State Resource

Each resource follows a spec/status model.

Example:
```
kind: DesktopCommanderRemote
spec:
  availability: READY_WHEN_NEEDED
  package: PINNED_QUALIFIED
  preserve_identity: true
  startup: EVENT_DRIVEN
  repair: IN_PLACE
status:
  observed_generation: 17
  health: AUTH_REQUIRED
  last_evidence: ...
  last_reconcile: ...
```

The controller:
- observes;
- calculates drift;
- performs the smallest safe correction;
- verifies;
- records status;
- backs off if external authorization/network is required.

## 6. Zero-Touch Friction Budget

Routine work target:
- 0 terminal copy/paste by the user;
- 0 screenshot-as-telemetry when the machine can inspect itself;
- 0 manual file relay between ChatGPT/project/Drive/Telegram;
- 0 repeated UAC prompts for already granted bounded capabilities;
- 0 manual update checks;
- 0 reinstall-as-first-response;
- 0 repeated repair for the same causal incident after a validated recipe exists.

Any avoidable manual step is recorded as a **FRICTION_EVENT**.

Rule:
- first avoidable friction -> candidate platform defect;
- repeated avoidable friction -> P0 automation/regression obligation.

## 7. Capability Factory

A universal system cannot pre-code every future operation.

When BCP receives an intent for which no safe capability exists:

CAPABILITY_GAP
-> research/reuse search
-> select existing OS/tool/library/provider when possible
-> license/provenance/security review
-> generate typed Capability Manifest + adapter
-> build/test in bounded sandbox
-> static policy checks
-> canary
-> evidence
-> register capability
-> execute original mission
-> add regression + recipe
-> optionally promote to shared capability.

The core never self-modifies ad hoc during a user job.

New capability code is treated as a versioned artifact.

## 8. Capability acquisition order

REUSE first:
1. existing BCP capability;
2. existing Windows/PowerShell/DSC/WinGet capability;
3. existing BuildHub/Delivery/GitHub/Drive provider;
4. trusted open-source/library;
5. small generated adapter around known tools;
6. new implementation only if a real gap remains.

This extends the existing BCP REUSE/ADAPT/BUILD_ONLY_IF_GAP doctrine.

## 9. Capability package

A capability package contains:
- capability manifest;
- exact source/provenance;
- executor bytes/scripts;
- hashes;
- permission class;
- resource class;
- input/output schema;
- health/readback contract;
- rollback;
- tests;
- compatibility;
- update channel;
- signing/provenance metadata.

No capability becomes AVAILABLE merely because its installer exited successfully.

## 10. Self-update fabric

Everything shared uses one update control plane:
- BCP core;
- B-EDGE;
- capability adapters;
- project adapters;
- BuildHub;
- Delivery provider;
- optional model runtime/model files;
- UI shells.

Update states:
DISCOVERED -> STAGED -> VERIFIED -> CANARY -> ACTIVATING -> HEALTHCHECK -> COMMITTED
or
FAILED -> ROLLBACK -> LKG.

Rules:
- no critical `@latest` execution path;
- current version is a signed/hashed qualified target;
- update checks may be automatic;
- activation is resource-aware;
- no update while a conflicting critical mission step is in unsafe phase;
- rollback stays bounded;
- old artifacts are garbage-collected only after LKG retention policy.

## 11. Update security model

BCP should adopt TUF-like security properties even if the first implementation is simpler:
- trusted root/key metadata;
- target hashes;
- freshness/expiry;
- anti-rollback version monotonicity;
- snapshot consistency;
- separation of qualification from activation.

BuildHub artifacts should carry provenance describing source revision, build process and inputs, aligned with SLSA/in-toto concepts.

Goal:
"automatic update" must not mean "download newest bytes and run them."

## 12. Windows Desired State provider

Use WinGet Configuration / Microsoft DSC selectively for:
- required package versions;
- dev/runtime dependencies;
- selected machine settings;
- reproducible onboarding;
- `test` before `apply`.

BCP wraps this with:
- project policy;
- trust review;
- resource admission;
- receipts;
- rollback when possible.

DSC is a provider, not BCP's canonical brain.

## 13. Privilege grants: install once, do not approve forever

Initial installer may request elevation to establish narrow infrastructure.

BCP stores **Capability Grants**, not generic admin permission.

Example:
- allow `windows.service.restart` for BCP-owned service;
- allow `windows.task.ensure` within BCP task namespace;
- allow package install/repair for approved package IDs/channels;
- deny arbitrary registry/system/security mutation.

The privileged helper:
- runs with least privilege possible;
- uses service SID/restricted identity where practical;
- local-only authenticated IPC with explicit ACLs;
- accepts typed messages only;
- has no arbitrary network listener;
- cannot execute model text directly.

P4 destructive/security-sensitive operations still require fresh approval.

## 14. Resource-aware autonomic loop

The autonomic system itself must not become the biggest load.

Event-first:
- filesystem change;
- process exit;
- service state;
- network transition;
- new mission;
- release manifest change;
- scheduled maintenance;
- idle/AC window.

No hot 5-second global polling loop by default.

A tiny sentinel/controller may stay resident only if measured field cost is acceptable.
Everything else wakes on demand.

## 15. Self-healing hierarchy

When something is unhealthy:

L0 OBSERVE
- read state, no mutation.

L1 RECONCILE
- idempotent expected-state correction.

L2 VALIDATED RECIPE
- apply known repair.

L3 RESTART COMPONENT
- bounded restart with cooldown.

L4 ROLLBACK
- return to last-known-good.

L5 REPROVISION CAPABILITY
- reinstall/repair exact qualified package only if local state is actually corrupt/missing.

L6 CAPABILITY FACTORY
- if the failure reveals a missing/obsolete capability.

L7 CHATGPT/HUMAN
- novel architecture, irreversible decision, external authorization.

"Reinstall" is deliberately late, not step 1.

## 16. Failure learning contract

Every significant incident produces:
- causal signature;
- observed symptoms;
- environment;
- root-cause confidence;
- successful repair;
- failed attempts;
- regression test;
- reusable recipe;
- capability/update implication.

A recipe is promoted only after evidence.

The system may suggest new recipes automatically; it may not silently promote unsafe mutation logic.

## 17. Med Rebuild reference transformation

Current class of problem:
user receives a file/script, launches it, watches console, sends screenshot, gets another script, retries.

Target:
1. ChatGPT creates/updates desired state for MedRebuildRuntime.
2. BCP observes launcher/updater/runtime/Commander capabilities.
3. Missing "stop commands" capability triggers Capability Factory.
4. Factory creates typed bounded adapter.
5. BuildHub/static tests qualify it.
6. BCP installs/registers it.
7. Reconciler uses it.
8. Launcher/install health verified.
9. Error signature + repair become regression/recipe.
10. user receives only result/exceptional gate.

The user never manually moves or launches a generated repair file in normal operation.

## 18. Broad "do anything" capability domains

The Fabric is designed to gain adapters for:
- filesystem/document processing;
- Git/source control;
- builds/tests/package/signing;
- Windows processes/services/tasks/events/packages/settings;
- browser automation where authorized;
- local web services;
- Android/ADB/build workflows;
- Drive/GitHub/Telegram/Delivery;
- indexing/search/library processing;
- project simulations/benchmarks;
- update/recovery;
- network/LAN diagnostics;
- report/artifact generation;
- optional local/remote inference.

Universal means **extensible under policy**, not unrestricted arbitrary execution.

## 19. Talk-only UX

Default interaction:
User -> ChatGPT natural language.

ChatGPT can say internally:
- answer only;
- create mission;
- assert desired state;
- inspect status;
- grant request;
- cancel/pause.

BCP handles transport and tool choice.

User-facing interruptions are reserved for:
- physical action;
- external 2FA/CAPTCHA/device authorization;
- provider terms/payment/account decision;
- P4 destructive/security action;
- genuine ambiguity with irreversible consequences.

Everything else is automation debt if it requires user mechanics.

## 20. Background "free compute" policy

When user is active:
- only tiny/light jobs unless explicitly requested.

When idle + resources safe:
- indexing;
- simulations;
- regression runs;
- update staging;
- hash/integrity audits;
- dependency cache preparation;
- document preprocessing;
- error-ledger mining;
- artifact cleanup;
- BuildHub qualification.

Background work is always checkpointable/preemptible.

## 21. What must never be autonomously "fixed"

Default no-touch:
- deleting unrelated personal files;
- security controls/firewall/AV weakening;
- credential extraction;
- financial/payment/account actions;
- destructive disk/partition operations;
- arbitrary registry mass edits;
- publishing private repositories;
- irreversible cloud deletion;
- bypassing provider authentication.

BCP may diagnose and propose these; execution follows explicit higher-risk policy.

## 22. Bootstrap paradox

Before Execution Fabric exists, some manual bootstrap is unavoidable.

Goal:
**one final platform bootstrap**, not recurring project bootstrap.

Initial install should:
- inventory;
- install/register core;
- establish restricted privileged helper;
- configure event-driven startup;
- create SQLite state;
- import current BCP/PC Command/ChatGPT-PC/Delivery knowledge;
- register existing project roots;
- establish update trust;
- create rollback;
- verify reboot/recovery.

After that, new projects should onboard through Project/Capability manifests rather than new bespoke installers.

## 23. Acceptance upgrade from R1

R2 is not successful until field tests prove:
- desired-state drift is detected and repaired;
- known failure self-heals without user mechanics;
- unknown capability gap can be turned into a tested capability;
- update is staged/verified/activated/rolled back automatically;
- same causal incident does not generate the same manual workflow twice;
- talk-only Med Rebuild repair completes end-to-end except irreducible human gate;
- no local AI required for any of the above;
- PC remains responsive under normal 85–95% RAM reality.

## 24. Final R2 definition

BCP Execution Fabric R2 is a **personal autonomic control plane**:
- ChatGPT is the natural-language planner;
- Desired State controllers keep systems healthy;
- durable Missions perform finite work;
- Capability Factory expands what the system can do;
- Resource Governor decides when/where work runs;
- Update Fabric keeps components current safely;
- Chronicle/receipts prove reality;
- Error/Recipe Ledger ensures failures become reusable knowledge.

The intended steady-state UX is:
**Speak -> observe verified result.**


## 25. Operational Digital Twin

BCP maintains a lightweight structured projection of the real operating world.

Entities:
- nodes/devices;
- projects;
- repositories;
- local roots;
- installed components;
- services/processes;
- packages/runtimes;
- capabilities;
- desired-state resources;
- missions/jobs;
- artifacts;
- transports/providers;
- resource conditions;
- incidents/recipes;
- versions/update channels.

Relationships:
- project USES capability;
- capability PROVIDED_BY node/provider;
- mission TARGETS project;
- task DEPENDS_ON capability/task;
- artifact PRODUCED_BY build/revision;
- desired state MANAGES resource;
- incident RESOLVED_BY recipe;
- component UPDATED_BY channel.

Implementation:
- SQLite relational tables + indexed views;
- Chronicle remains immutable history;
- Digital Twin is a reconstructible projection, not separate authority;
- no Neo4j or heavy graph server on the 4 GB PC.

ChatGPT consumes a task-scoped Context Projection from this twin instead of re-reading the whole system.

## 26. Context Compiler for ChatGPT

Before ChatGPT plans an action, BCP should be able to emit:

```
PROJECT
current revision
local root
health
pending missions
recent incidents
relevant capabilities
resource state
last verified receipts
update state
known blockers
```

The compiler selects only relevant data.

Goal:
- reduce repeated context reconstruction;
- reduce user explanations;
- reduce token/latency waste;
- ground planning in machine reality;
- avoid stale conversational assumptions.

## 27. Work Portfolio Controller

BCP manages all projects as one portfolio.

Priority order by default:
1. integrity/recovery;
2. explicit interactive user request;
3. blocking prerequisite;
4. normal project work;
5. maintenance;
6. background improvement.

Global constraints:
- one heavy PC job;
- per-project mutation locks;
- foreground always wins;
- resource and network admission;
- deadlines/urgency;
- starvation prevention for low-priority work.

When the user says:
"avance mes projets pendant que je fais autre chose"

BCP can choose from READY background tasks without requiring a new ChatGPT turn for every micro-step.

It may NOT invent new project goals. It executes only durable backlog items/desired-state reconciliation already authorized by user/project policy.

## 28. Autonomy modes

A user-facing autonomy profile controls interruption frequency.

### SILENT_SAFE
Automatic:
- P0/P1;
- diagnostics;
- known self-heals;
- checks;
- safe updates staged;
- background work.

### PROJECT_AUTONOMOUS
Adds:
- P2 project mutations with snapshot/rollback/evidence;
- commits on work branches;
- builds/tests;
- project-local updates.

### SYSTEM_BOUNDED
Adds explicitly pre-granted P3 capabilities:
- BCP-owned services/tasks;
- approved packages/runtimes;
- approved firewall rules for BCP-owned endpoints where separately granted.

P4 remains approval-gated in every mode.

The install process can let the user pre-authorize capability classes once, represented as revocable Capability Grants.

## 29. Interaction classes

Every event is classified:

- INVISIBLE: healthy reconciliation/background work.
- DIGEST: non-urgent completion/status; batch into one summary.
- NOTIFY: meaningful failure/recovery/update.
- APPROVE: explicit bounded action needs consent.
- HUMAN_ACTION: authentication/CAPTCHA/physical/provider gate.

The system must not notify on every heartbeat or retry.

## 30. Manual-friction learning

BCP records every moment where the user had to:
- open terminal;
- run a script;
- copy a log;
- screenshot state;
- move a file;
- retry a command;
- click a repair executable;
- re-enter already-known configuration.

Each becomes `FRICTION_EVENT`.

The audit engine periodically asks:
"Could the machine have observed/performed this itself?"

If yes:
- create automation debt;
- attach to capability/update/project backlog;
- prioritize repeated/high-cost friction.

This turns the user's real annoyance into platform requirements automatically.

## 31. Universal system criterion

The system is not judged by the number of built-in tools.

It is judged by:
- breadth of trusted capability providers;
- speed of safe capability acquisition;
- amount of user mechanics eliminated;
- ability to preserve state across failure;
- verified useful work per RAM/CPU/network cost;
- percentage of repeated incidents converted to self-healing recipes;
- percentage of project setup/update/recovery handled declaratively.

"Tout faire" therefore means:
**Any legitimate authorized task is either already executable, can be acquired as a capability, or is escalated with a precise irreducible reason — without making the user the integration layer.**


## 32. Logical controller set

Controllers are logical modules, NOT separate resident daemons.

- MissionController — finite durable work/DAG.
- DesiredStateController — current vs desired reconciliation.
- ResourceController — PC/phone resource admission and preemption.
- CapabilityController — capability availability/health/TTL.
- CapabilityFactoryController — capability gap pipeline.
- ReleaseController — project/component update promotion/rollback.
- TransportController — Drive/Telegram/Nexus/direct path health and outbox.
- ArtifactController — generated files, hashes, retention, delivery.
- ContextController — Digital Twin projections/context packs.
- FrictionController — converts avoidable user mechanics into automation debt.
- IncidentController — Error Ledger, recipes, regressions.
- PortfolioController — priorities/WIP/background work.

All share the same event bus/Chronicle/SQLite state and resource governor.

## 33. Privileged provider decision

Before implementing a custom privileged Windows service, Phase 0/2 must benchmark and prototype **PowerShell Just Enough Administration (JEA)** as a native least-privilege provider.

JEA can expose only selected cmdlets/functions/external commands and can use temporary virtual accounts for privileged actions.

Decision tree:
- if JEA can meet local-only, bounded-action, latency/resource and reliability requirements, reuse it for suitable P3 operations;
- if not, implement a tiny restricted BCP privileged helper with service SID + explicit ACL;
- both remain behind the same typed Capability contract.

No mission depends on a specific privilege implementation.

## 34. Candidate adapter sandboxing

Capability Factory candidate code should run in the smallest practical isolation boundary.

Order:
1. static/schema validation;
2. temporary worktree/root;
3. normal-user process with Job Object;
4. network-denied process when network is unnecessary;
5. Windows restricted/AppContainer sandbox API when supported and compatible;
6. privileged canary only after previous gates pass.

The 4 GB PC must not require a heavyweight VM/container simply to test every adapter.
