# BCP Construction Execution Routing Policy R3.1
Date: 2026-10-05
Status: CANONICAL_CONSTRUCTION_POLICY

## 0. Goal

Construction must be automatic, quota-aware and simulation-first.

The system must minimize:
- Desktop Commander quota consumption;
- PC field interventions;
- repeated manual user actions;
- expensive remote jobs;
- unnecessary rebuilds.

The system must maximize:
- repository-side validation;
- reproducible simulation;
- reusable build/test evidence;
- exact-head verification;
- local/native execution only when field reality is actually required.

## 1. Core law

**SIMULATE / VERIFY OFF-MACHINE FIRST; TOUCH THE PC LAST.**

Desktop Commander is never the default construction tool.

For each change, the construction controller chooses the cheapest qualified path that can answer the current question.

## 2. Provider classes

### G0 — Repository reasoning / static verification
Examples:
- GitHub source inspection;
- diff analysis;
- schema validation;
- lint/static parsing;
- unit tests that can run in a lightweight repository environment;
- branch/worktree construction;
- review/counter-audit.

Cost class:
LOW / preferred.

No Desktop Commander.

### G1 — Reproducible CI / simulation
Examples:
- GitHub Actions Windows/Linux jobs;
- BuildHub;
- project-specific test workflows;
- installer static QA;
- package generation;
- simulated Windows behavior;
- deterministic integration tests.

Cost class:
QUOTA_AWARE.

GitHub Actions itself may have quota, therefore:
- query/observe budget when possible;
- avoid duplicate workflows;
- use targeted tests before full matrices;
- cache/reuse immutable artifacts/results;
- do not rerun exact-head PASS without a changed input/evidence-expiry reason.

### G2 — Local-native PC validation
Examples:
- actual process/service/startup behavior;
- actual RAM/pagefile/CPU/disk behavior;
- local paths/ACLs;
- real installer/startup;
- actual Windows Job Object behavior;
- actual project data/device integration.

Provider:
BCP local-first microkernel / G6 skill / PowerShell / Win32 / WMI / CIM / CLI.

Desktop Commander still not required.

### G3 — Desktop Commander metered field assist
Use only when:
- an existing qualified local capability cannot yet perform the effect;
- remote interactive inspection materially shortens a specific field gate;
- a capability is unique to Desktop Commander for the current stage;
- quota state is AVAILABLE and expected value justifies the budget.

Desktop Commander must never be used for:
- ordinary repository reading;
- routine Git operations available through GitHub;
- repeated build/test loops reproducible in CI/BuildHub;
- polling/heartbeat;
- long background jobs;
- bulk file scans;
- routine logs already machine-readable through BCP native capabilities.

### G4 — Human irreducible gate
Only:
- physical action;
- 2FA/CAPTCHA/device authorization;
- P4 destructive/security action;
- irreversible ambiguity;
- provider/account/payment decision.

## 3. Automatic construction routing

For each atomic work unit:

1. CLASSIFY question:
   - CODE_LOGIC
   - BUILD
   - SIMULATION
   - WINDOWS_BEHAVIOR
   - DEVICE_SPECIFIC
   - RESOURCE_PROFILE
   - AUTH_PROVIDER
   - DELIVERY
   - RELEASE

2. IDENTIFY candidate providers.

3. SCORE candidates on:
   - correctness;
   - reproducibility;
   - quota/budget;
   - cost;
   - field specificity;
   - latency;
   - resource load on MBMPC;
   - observability/readback;
   - resumability.

4. SELECT highest-value lowest-cost provider.

5. RUN smallest sufficient test first.

6. ESCALATE only if evidence is insufficient.

7. CACHE result by:
   - source revision;
   - environment fingerprint;
   - test contract version;
   - artifact hash.

## 4. Desktop Commander quota policy

Desktop Commander budget state:
- AVAILABLE
- LOW
- EXHAUSTED
- RATE_LIMITED
- UNKNOWN

Policy:

AVAILABLE:
- may use for specific field-only tasks after simulation-first gates.

LOW:
- no exploratory use;
- no repeated reads;
- only high-value blocker-clearing field checks;
- collect all needed observations in one bounded session.

EXHAUSTED:
- do not retry;
- switch to native BCP/local providers;
- queue provider-exclusive task;
- continue independent construction.

UNKNOWN:
- treat conservatively as LOW until evidence says otherwise.

Every Desktop Commander session should have a **mission bundle**:
- exact questions to answer;
- exact files/processes/state to inspect;
- exact write actions if any;
- expected evidence;
- stop condition.

Avoid opening multiple sessions for facts that could be collected in one bounded field pass.

## 5. GitHub/CI quota policy

GitHub is preferred for source-level construction, but GitHub Actions is also quota-bearing.

Therefore separate:

### GitHub API / repository operations
Use heavily for:
- code search;
- reads;
- branches;
- diffs;
- commits;
- PRs;
- source audits.

### GitHub Actions
Use selectively for:
- reproducible builds;
- Windows/Linux test matrices;
- exact-head packaging;
- installer simulation.

Before a full workflow:
- run static/local repository checks;
- target the changed module;
- skip unaffected matrices where policy permits;
- reuse exact-head successful artifacts if immutable and still valid.

If Actions quota is unavailable:
fallback:
1. BuildHub;
2. local lightweight test provider;
3. another already-qualified free provider;
4. WAITING_PROVIDER for genuinely provider-specific job.

Do not fall back directly to Desktop Commander just because CI quota is unavailable.

## 6. BuildHub role

BuildHub is preferred for generic reproducible build/test/package operations when it can perform them without stressing MBMPC.

Construction controller should:
- submit exact revision;
- receive durable job handle;
- collect logs/artifacts;
- verify hashes;
- persist receipt;
- reattach after conversation/network interruption.

BuildHub is a provider, not mission authority.

## 7. Test pyramid for constrained construction

Every code change should attempt the following in order:

L0 — schema/static/unit checks
L1 — targeted integration simulation
L2 — broader CI/build
L3 — platform simulation
L4 — field-local native validation
L5 — Desktop Commander bounded assist if still uniquely useful

Most defects should die at L0-L3.

The goal is that G3/Desktop Commander sees only changes that already passed all non-field gates.

## 8. Med Rebuild example

Change:
repair launcher/startup logic.

Automatic route:

A. GitHub:
- inspect current code;
- create implementation branch;
- patch;
- static tests;
- inspect med-rebuild-ci workflow.

B. CI/BuildHub:
- Windows test;
- installer/launcher simulation;
- failure injection;
- package candidate.

C. Counter-audit:
- inspect diff/results;
- fix regressions;
- rerun only changed gates.

D. Local BCP native:
- stage candidate;
- actual startup/readback;
- actual resource test;
- rollback test.

E. Desktop Commander:
- ONLY if one remaining field question cannot be observed through BCP native capabilities.

The expected normal result is **zero Desktop Commander calls** for most iterations.

## 9. Long construction sessions

For 6-hour/day/week construction:

The controller runs a repeated automatic loop:

DISCOVER CURRENT HEAD
-> PLAN ATOMIC SLICE
-> PATCH BRANCH
-> STATIC/UNIT
-> SIMULATE/CI/BUILDHUB
-> COUNTER-AUDIT
-> FAILURE INJECTION
-> RECEIPT
-> CHECKPOINT
-> NEXT SLICE.

Field validation is batched:
- collect multiple already-qualified changes;
- run one bounded PC field campaign;
- avoid repeated Desktop Commander/local-device wakeups.

## 10. Field campaign batching

Instead of:

change 1 -> Desktop Commander
change 2 -> Desktop Commander
change 3 -> Desktop Commander

Prefer:

change 1 -> simulate
change 2 -> simulate
change 3 -> simulate
all green
-> ONE FIELD CAMPAIGN
   - inspect
   - install/stage
   - verify all relevant gates
   - capture receipts.

This conserves:
- Desktop Commander quota;
- user's time;
- PC RAM/CPU;
- network;
- context switching.

## 11. Automatic stop/escalation

Do not ask user "continue?" after ordinary successful tranche.

Continue automatically until:
- irreducible human gate;
- unsafe ambiguity;
- all eligible providers exhausted;
- no reproducible next step;
- P4 action;
- field access is truly required and no native/remote qualified path exists.

Persist exact next step when stopping.

## 12. Construction KPIs

Track:
- Desktop Commander calls per verified field release;
- Desktop Commander minutes/operations per mission if observable;
- percentage defects caught before PC field stage;
- CI jobs per commit;
- duplicate CI reruns avoided;
- BuildHub reuse rate;
- field campaigns per release;
- manual user interventions;
- mean verified progress per provider-cost unit.

Target:
**Desktop Commander usage trends toward exceptional, not routine.**

## 13. Hard acceptance rule

The automatic construction system FAILS if:
- it consumes Desktop Commander quota for routine source/build/test work available elsewhere;
- it repeatedly performs field checks that could have been simulated;
- it blocks because Desktop Commander quota ended while another qualified provider exists;
- it asks the user to manually execute test/recovery steps solely to save implementation effort.

The system PASSES when:
- repository/CI/BuildHub do most iteration;
- PC native path does final reality checks;
- Desktop Commander is a rare, bounded, high-value specialist tool.
