# BCP Autonomic Execution Fabric — Final Verification Rules R2
Date: 2026-10-05
Status: PRECONCEPTION / FINAL VERIFICATION ADDENDUM

## 0. Purpose

This addendum defines the final non-negotiable verification rules for ZERO-TOUCH R2.

The architecture is invalid if it only works while one external metered provider, one ChatGPT conversation, one GUI session or one continuous network connection remains available.

## 1. No Metered Provider as Correctness Dependency

Every capability provider is classified:

- LOCAL_UNMETERED — native PC/B-EDGE capability under user control;
- LOCAL_BOUNDED_RESOURCE — local but constrained by RAM/CPU/disk/battery;
- EXTERNAL_METERED — quota/rate/credit constrained;
- EXTERNAL_UNMETERED_OR_ACCOUNT — external service without a known per-action quota but still not runtime authority;
- UNKNOWN_BUDGET — provider budget cannot be proven.

Rules:
- ZERO-TOUCH correctness may not depend exclusively on EXTERNAL_METERED or UNKNOWN_BUDGET providers.
- Desktop Commander is explicitly EXTERNAL_METERED_OPTIONAL / compatibility accelerator.
- Exhausting Desktop Commander quota blocks only tasks that have no qualified alternative and marks them WAITING_CAPABILITY_PROVIDER; it never blocks unrelated work.
- A provider advertised as available is not equivalent to sufficient quota.
- The scheduler must know provider health + budget class + last quota evidence + cooldown/reset when observable.
- A long mission must not start a critical non-checkpointable phase on a provider whose remaining budget cannot reasonably cover that phase.
- Paid credits/upgrades are never assumed or purchased automatically.

## 2. Provider Fallback Law

For PC effects, preferred fallback order is:

1. PC Local-First Microkernel native capability;
2. qualified G6/ChatGPT-PC skill;
3. PowerShell/Win32/WMI/CIM/Git/CLI/WinGet/DSC provider;
4. project-specific local adapter;
5. B-EDGE/LAN executor if capable;
6. BuildHub / approved CI / external connector when useful;
7. Desktop Commander or equivalent metered remote executor;
8. Capability Factory;
9. exact irreducible human gate.

Desktop Commander may accelerate specialized work but may never sit above the native local execution plane in dependency order.

## 3. Quota-Aware Scheduler

The Capability Registry adds provider budget state:

- provider_id
- budget_class
- quota_state = AVAILABLE | LOW | EXHAUSTED | RATE_LIMITED | UNKNOWN
- remaining_hint
- reset_at_or_unknown
- evidence_at
- capability_equivalents[]
- migration_cost
- resumability_class.

Scheduling rule:
rank by correctness + local authority + observability + available budget + resource cost, not by convenience alone.

When a quota becomes LOW:
- stop assigning new optional work to that provider;
- finish/checkpoint the safe current atomic unit if possible;
- migrate queued work to equivalents.

When EXHAUSTED:
- no retry storm;
- mark provider unavailable until reset/evidence changes;
- continue independent branches.

## 4. Long-Horizon Mission Contract

A mission may legitimately last:
- minutes;
- 6 hours;
- overnight;
- multiple days;
- one week or more.

Duration does not change the correctness model.

Every long mission is compiled into a durable DAG of bounded work units.

Each material unit follows:
OPEN -> EXECUTE -> OBSERVE -> VERIFY -> COMMIT.

No six-hour opaque command is accepted when it can be decomposed into checkpointable stages.

## 5. Long Task Resumability Classes

Each work unit declares:

- RESUME_NATIVE — tool supports restart/resume from checkpoint;
- REPLAY_IDEMPOTENT — safe exact rerun with same idempotency key;
- OBSERVE_BEFORE_RETRY — inspect real effect before deciding;
- NONRESUMABLE_ATOMIC — bounded short atomic section; must not be hours long;
- EXTERNAL_JOB_HANDLE — remote build/test has durable job ID and can be reattached;
- NEEDS_REASONING — requires new ChatGPT/qualified planner reasoning before next branch.

A long mission is invalid if its critical path consists of an unbounded NONRESUMABLE_ATOMIC action.

## 6. Conversation Independence

ChatGPT is the primary reasoning interface but a ChatGPT turn/conversation is not the mission lifetime.

On conversation end:
- committed task graph remains durable;
- already-authorized deterministic/local work may continue;
- builds/tests/indexing/copies/downloads/verification/reconciliation may continue;
- desired-state controllers continue;
- receipts accumulate;
- novel branches requiring new reasoning move to NEEDS_REASONING rather than guessing.

A new ChatGPT conversation restores from the exact current mission/context projection. The user must not reconstruct the project manually.

Important truth:
ChatGPT itself does not keep reasoning after the turn ends. Continuation is performed by the resident BCP/PC/B-EDGE components using the durable plan and capabilities already authorized.

## 7. Six-Hour / Multi-Day Software Construction

For software construction lasting hours/days:

PHASE 1 — durable specification + acceptance tests
PHASE 2 — isolated branch/worktree
PHASE 3 — implementation work units
PHASE 4 — incremental build/lint/unit tests
PHASE 5 — integration tests
PHASE 6 — resource/security/regression gates
PHASE 7 — package/provenance/hash
PHASE 8 — canary/field test
PHASE 9 — qualified promotion
PHASE 10 — desired-state/update registration.

After every material phase:
- exact revision;
- artifact hash;
- test result;
- open blockers;
- next work unit;
- rollback point;
are durable.

A PC reboot, chat closure, quota exhaustion or network outage may delay work but must not erase verified progress.

## 8. One-Week Mission Rule

For missions spanning days:
- no assumption of continuous PC uptime;
- no assumption of continuous Internet;
- no assumption of continuous ChatGPT availability;
- no assumption that Desktop Commander, GitHub Actions, Drive or any other external provider remains continuously available;
- work queue survives reboot;
- safe missed work becomes due, not falsely completed;
- stale leases expire and reconcile;
- dependency/version changes are revalidated before resuming mutation;
- completed immutable stages are reused, not rerun for reassurance.

## 9. External Build/CI Rule

BuildHub/GitHub CI/other builders may accelerate heavy work.

But:
- source state and mission state remain durable outside the CI job;
- every external job has exact input revision and durable job handle;
- CI quota failure = WAITING_PROVIDER or local/build-provider fallback;
- a CI timeout does not invalidate already committed local work;
- no project is architected so that an account quota permanently prevents local recovery/maintenance.

## 10. PC-Off / Sleep / Restart Semantics

PC OFF:
- no claim that local work is progressing;
- queued mission remains durable;
- coordinator may continue provider-independent work elsewhere;
- PC-targeted work becomes WAITING_NODE.

PC ON:
- microkernel starts through the single primary startup path;
- reconciles interrupted units;
- reads actual effects before replay;
- resumes eligible work according to resources.

Sleep:
- work is PAUSED_BY_POWER unless a separately verified wake policy exists;
- elapsed wall time never implies progress.

## 11. Network Loss

No network:
- local work continues;
- local desired-state reconciliation continues;
- remote effects queue;
- provider jobs move WAITING_NETWORK;
- outbox stays durable.

Reconnect:
- no blind replay;
- deduplicate by effect/idempotency key;
- read back remote state;
- continue.

## 12. Resource Pressure During Long Jobs

At high RAM/commit/pagefile pressure:
- foreground user work wins;
- checkpoint/preempt heavy worker;
- do not kill unrelated user processes;
- do not start optional local AI;
- use lower-cost node/provider where safe;
- resume only after hysteresis proves recovery.

A long job is successful only if the machine remains usable under its field resource envelope.

## 13. Evidence Freshness Law

A PASS must bind:
- exact task/mission ID;
- exact source revision;
- exact artifact hash when applicable;
- exact target/node;
- verifier result;
- observed time;
- environment/capability fingerprint where material.

Old PASS evidence cannot certify changed code, changed machine state or changed dependencies without compatibility proof.

## 14. No False Progress

Progress changes only after durable work-state changes.

Forbidden:
- progress by elapsed time;
- progress by heartbeat;
- progress by "tool still running";
- claiming work active while PC is off;
- claiming a remote provider is working without current durable job evidence.

For a week-long mission, 73% means 73% of weighted durable scope, not 73% of expected calendar duration.

## 15. No Lost Work Gate

ZERO_TOUCH_FIELD_READY requires proving:
- kill worker mid-step;
- kill core mid-write;
- close ChatGPT;
- exhaust Desktop Commander quota;
- rate-limit an external provider;
- disconnect Internet;
- reboot Windows;
- sleep/wake;
- run under RAM pressure;
- resume next day;
- resume from a new conversation.

After every test:
- no committed work lost;
- no non-idempotent effect duplicated;
- no stale PASS promoted;
- next exact step reconstructible.

## 16. Provider Independence Acceptance Tests

### ZT-Q1 — Desktop Commander quota exhausted
Expected:
- Desktop Commander -> EXHAUSTED;
- no retry storm;
- local/native alternatives selected;
- unrelated branches continue;
- user is not asked to purchase quota;
- only truly provider-exclusive action may wait.

### ZT-Q2 — Desktop Commander absent from machine/account
Expected:
all core BCP functionality still boots and works.

### ZT-Q3 — GitHub Actions quota unavailable
Expected:
local BuildHub/PC or another approved build path handles eligible jobs; otherwise WAITING_PROVIDER with state preserved.

### ZT-Q4 — Drive unavailable
Expected:
local authority/outbox remains correct and later syncs.

### ZT-Q5 — ChatGPT unavailable temporarily
Expected:
precompiled deterministic mission branches continue; reasoning-required branches pause honestly.

## 17. Long-Horizon Acceptance Tests

### ZT-L1 — 6-hour construction
Inject restarts/resource pressure/provider loss.
Expected:
checkpointable progress + exact resume with no manual reconstruction.

### ZT-L2 — overnight PC shutdown
Expected:
mission PAUSED_NODE_OFF; on startup reconcile and resume.

### ZT-L3 — 7-day project build
Expected:
multiple sessions/conversations/providers; one canonical task graph; immutable completed stages reused.

### ZT-L4 — provider switch mid-build
Expected:
same exact source/input contract transferred or rebuilt on equivalent provider; outputs verified before adoption.

### ZT-L5 — stale dependency after 3 days
Expected:
revalidate dependency/security/version assumptions before mutation resumes.

## 18. Final Dependency Principle

A universal personal execution system must remain useful when every optional external accelerator is unavailable.

Minimum survival set:
- local microkernel;
- local durable state;
- native Windows/file/Git/build capabilities that are installed;
- local recovery/LKG;
- queued mission/desired-state knowledge.

Everything else is an accelerator/provider.

## 19. Final Product Test

The product fails this architecture if the user can reasonably say:

> "Desktop Commander quota ended, so now my whole system cannot work."

The required answer from the architecture is:

> "Desktop Commander quota ended. That provider is unavailable. BCP continued through the native/local capability plane, migrated eligible tasks, preserved the rest, and only the genuinely provider-exclusive branch is waiting."
