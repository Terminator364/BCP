# BCP Autonomic Execution Fabric — Zero-Touch Acceptance Matrix R2
Date: 2026-10-05
Status: PRECONCEPTION / FIELD GATES

## ZT-0 — User contract

Normal path:
NATURAL_LANGUAGE_INTENT -> VERIFIED_RESULT.

A task is NOT zero-touch if the user is asked to perform a technical step that a qualified machine capability could have performed.

Irreducible human gates are separately classified and are not automation defects:
- physical action;
- provider/device authorization;
- CAPTCHA/2FA;
- payment/account/legal decision;
- P4 destructive/security-sensitive operation;
- irreversible ambiguity.

## ZT-1 — Med Rebuild unknown local capability

Inject:
A Med Rebuild repair requires a local stop/restart/inspection operation that is not yet in Capability Registry.

Expected:
1. Mission records CAPABILITY_GAP.
2. Existing/reusable capability search occurs.
3. If absent, candidate adapter is produced on a work branch/temp root.
4. Candidate passes static/schema/security/resource tests.
5. Candidate runs canary.
6. Capability registers as T1 only after evidence.
7. Original mission resumes automatically.
8. User does not run a generated CMD/PS1 manually.
9. Incident and capability acquisition enter Chronicle/Error Ledger.
10. Repeating same intent uses registered capability.

Failure:
- assistant gives user a repair script as normal path;
- user must paste terminal output;
- untested generated capability receives admin authority.

## ZT-2 — Known incident recurrence

Inject same causal failure twice.

Expected:
- first incident may require investigation;
- root cause + repair + regression becomes validated recipe;
- second incident matches signature and self-heals;
- no repeated user mechanics.

Metric:
REPEATED_MANUAL_FRICTION_FOR_VALIDATED_INCIDENT = 0.

## ZT-3 — Desired-state drift

Desired:
MedRebuild launcher PASS and updater HEALTHY.

Inject:
launcher file missing / wrong qualified version.

Expected:
- controller observes drift;
- stages exact qualified repair;
- applies bounded correction;
- performs health/readback;
- marks IN_SYNC;
- notification only if user-impacting or repair failed.

## ZT-4 — Automatic update

Inject:
new qualified BCP/project/capability release.

Expected:
DISCOVER -> STAGE -> VERIFY -> CANARY -> ACTIVATE -> HEALTHCHECK -> COMMIT.

Inject health failure:
-> automatic ROLLBACK to LKG.

Reject:
blind @latest execution.

## ZT-5 — Supply-chain tamper

Inject wrong artifact hash/provenance.

Expected:
- no activation;
- candidate quarantined;
- current/LKG continues;
- incident recorded.

## ZT-6 — RAM 85–95%

Start with high memory pressure.

Expected:
- no local model load;
- heavy work WAITING_RESOURCE;
- lightweight state/reconcile remains alive where feasible;
- user foreground unaffected;
- no RAM-cleaner killing unrelated processes;
- work resumes after hysteresis threshold is satisfied.

## ZT-7 — ChatGPT conversation ends

Expected:
- durable finite tasks continue;
- desired-state controllers continue;
- novel branch requiring reasoning becomes NEEDS_REASONING/NEEDS_CHATGPT;
- independent branches continue;
- new chat receives mission/twin context without user reconstruction.

## ZT-8 — Desktop Commander unavailable

Expected:
- desktop_commander capability enters TEMP_UNAVAILABLE/AUTH_REQUIRED;
- local native BCP capabilities continue;
- Med Rebuild does not globally block;
- no reinstall loop.

## ZT-9 — Internet absent

Expected:
- local desired-state reconciliation continues;
- local jobs continue;
- provider-dependent steps WAITING_NETWORK;
- outbox persists;
- reconnect dedupes effects.

## ZT-10 — PC reboot

Expected:
- no manual rerun;
- runtime wakes through one primary startup mechanism;
- SQLite/Chronicle reconcile;
- ambiguous prior effect is read back before replay;
- heavy backlog resumes serially.

## ZT-11 — Project source update

Expected:
- separate worktree/branch;
- no overwrite of dirty user work;
- build/tests;
- artifact provenance;
- canary;
- serialized merge/promotion;
- rollback available.

## ZT-12 — Dependency update

Expected:
- desired version/channel policy;
- candidate tested before live activation;
- patch/minor auto-promotion only if project policy permits;
- major/breaking migration waits for sufficient proof or high-level decision.

## ZT-13 — Admin operation

Routine pre-granted P3:
- no repeated UAC;
- typed scoped operation;
- explicit IPC ACL;
- before/after evidence.

P4:
- fresh human approval always.

## ZT-14 — Capability Factory security

Candidate adapter attempts:
- undeclared network;
- path outside scope;
- undeclared child process;
- privilege escalation;
- schema-invalid output.

Expected:
- contain/reject/quarantine;
- no registration.

## ZT-15 — Telegram/Drive failure

Expected:
- canonical mission stays local/coordinator;
- delivery/store-forward retries;
- artifact/mission success not falsified;
- user receives eventual receipt when transport returns.

## ZT-16 — Voice-first interaction

From ChatGPT voice/text:
"Arrange Med Rebuild and keep it healthy."

Expected:
- no special command syntax required;
- intent compiles to mission + desired state when appropriate;
- user receives concise outcome/irreducible gate only.

## ZT-17 — Friction Controller

Inject user manual intervention event.

Expected:
- classify as IRREDUCIBLE or AVOIDABLE;
- avoidable -> automation debt item;
- repeated avoidable -> P0 regression/capability backlog.

## ZT-18 — Portfolio background work

User says:
"avance ce que tu peux pendant que je fais autre chose."

Expected:
- only already-authorized backlog/desires;
- no invented project goals;
- one heavy PC worker;
- low-priority starvation prevention;
- foreground preemption;
- consolidated digest instead of notification spam.

## ZT-19 — Digital Twin freshness

Expected:
ChatGPT context projection includes source timestamps/revisions.
Stale facts are marked stale/unknown, never silently treated as current.

## ZT-20 — No-model survival

Disable all local/remote optional inference.

Expected:
- core boots;
- desired-state known recipes operate;
- builds/tests/files/Git/update/recovery work;
- complex unknown reasoning waits but does not corrupt/block unrelated work.

## Final zero-touch field gate

Do NOT claim ZERO_TOUCH_FIELD_READY until:
- ZT-1 through ZT-20 have explicit tests;
- Med Rebuild completes at least one genuine previously-manual recovery end-to-end;
- same incident repeats and auto-heals;
- one automatic update rolls forward;
- one intentionally bad update rolls back;
- one missing capability is acquired and reused;
- PC is proven usable under its normal high-RAM-pressure baseline;
- user performs no technical mechanics except a classified irreducible human gate.
