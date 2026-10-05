# BCP Typed Worker Containment + Resource Admission — R3 Phase 2B

Date: 2026-10-05  
Status: IMPLEMENTATION_CANDIDATE / STACKED / NOT FIELD CERTIFIED

## Goal

Add bounded worker execution to the selected BCP microkernel without turning the core into an arbitrary remote shell.

## Reused components

From ChatGPT-PC vNext source commit:
`6bf6e32b36008957dda014542742657af6b9e017`

Reused:
- `WorkerSupervisor`;
- `WorkerPolicy`;
- start-gated `worker_bootstrap.py`;
- Windows Job Object containment;
- process/job memory caps;
- timeout termination;
- bounded stdout/stderr;
- inline-input cap;
- non-Windows simulation mode for repository tests.

## Start-gated containment

The parent launches only the trusted bootstrap.

On Windows:
1. bootstrap starts and blocks on stdin;
2. BCP creates/configures the Job Object;
3. bootstrap process is assigned to that Job Object;
4. only then is the typed execution plan delivered;
5. the real worker starts inside the inherited job boundary.

This closes the ordinary assign-after-spawn escape window.

## No arbitrary shell capability

Phase 2B intentionally exposes **no HTTP endpoint accepting caller-supplied argv or shell text**.

The WorkerSupervisor is an internal primitive.

Phase 3 Capability Bus must map:
`capability_id -> fixed/validated executor builder -> WorkerPolicy`.

A caller may submit capability inputs defined by schema; it may not submit arbitrary executable text.

## Resource admission

`resource_admission.py` is not a second Resource Governor.

It consumes an externally established mode:
- GREEN;
- AMBER;
- RED;
- CRITICAL.

It decides only whether a typed work unit can start.

### Conservative policy

GREEN:
- R0-R3 admitted;
- R4 local AI remains separately policy-gated.

AMBER:
- foreground/normal R0-R1 only;
- background improvement only R0;
- R2/R3 wait.

RED:
- only R0 foreground or critical recovery;
- everything else waits.

CRITICAL:
- only R0 critical integrity recovery;
- preserve machine otherwise.

## Why this matters on MBMPC

The target PC has a constrained memory envelope.

BCP therefore must prefer:
- deferral over thrashing;
- bounded output over pipe-memory growth;
- child-tree kill over orphan processes;
- explicit memory ceilings;
- background priority for non-interactive work.

## Field gate still required

Repository CI can prove:
- plan validation;
- output bounding;
- timeout semantics;
- admission decisions;
- refusal of Job-Object-required work on non-Windows.

Only Windows field evidence can prove:
- `CreateJobObjectW`;
- `SetInformationJobObject`;
- `AssignProcessToJobObject`;
- kill-on-job-close;
- whole descendant tree containment;
- actual memory ceilings.

No field certification is claimed in Phase 2B repository tests.

## Next Phase 2 tranche

Phase 2C:
- read-only startup inventory;
- select one primary resident trigger;
- select one bounded stale-health fallback;
- identify and retire overlapping legacy supervisors only after proof;
- field-test Job Object behavior in the same batched campaign.

After Phase 2 convergence passes: **Phase 3 — Project Registry + typed Capability Bus adapters**.
