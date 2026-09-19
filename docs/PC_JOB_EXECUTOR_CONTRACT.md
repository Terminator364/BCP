# BCP PC Job Executor — Proof-Carrying Contract

Status: TARGET CONTRACT / NOT YET FIELD-VERIFIED
Audit date: 2026-09-19
Parent: BCP 0.6 / B-EDGE 2.0 RC hardening

## Purpose

A durable queue is not an executor.

BCP MUST distinguish:
- accepted into durable queue;
- leased to a worker;
- actually running;
- terminally completed/failed;
- effect verified by machine-readable evidence.

No UI, Telegram message, agent, or Context Pack may translate QUEUED/ACCEPTED into DONE.

## State machine

Canonical PC job states:

`READY -> LEASED -> RUNNING -> SUCCEEDED | FAILED | CANCELLED`

Additional scheduler states:
- `BLOCKED` — dependency not terminal-success;
- `WAITING_FOR_PC` — PC capability/resource gate unavailable;
- `HOLD` — policy/evidence/user decision required;
- `RETRY_WAIT` — bounded retry after classified transient failure.

`REMOTE_QUEUED` is a B-EDGE mirror state meaning only that the PC/server has a durable copy of the job.

## Queue admission envelope

Every PC-bound job MUST carry:
- `job_id/local_id`;
- `action_id`;
- `idempotency_key`;
- project ID;
- job kind;
- exact payload;
- resource class;
- priority;
- expected project revision;
- input hash;
- coordinator epoch/fencing token;
- evidence contract;
- dependency job IDs;
- bounded timeout/retry policy.

Missing critical fencing/evidence fields cause HOLD once V2 authority is active.

## Claim / lease

Claim is transactional.

A worker may claim only a job that:
- is READY;
- has no unresolved dependency;
- matches the worker's declared capabilities;
- passes current resource/policy gates;
- has no active unexpired lease.

Claim writes:
- worker ID;
- lease ID;
- lease expiry;
- attempt number;
- coordinator epoch;
- state LEASED.

Execution starts only after successful claim readback.

Lease expiry makes the attempt uncertain/reclaimable, not automatically failed.

## Execution

The PC worker MUST use an allowlisted handler registry.

Forbidden default:
- arbitrary shell command from model/Telegram/job payload;
- arbitrary executable path supplied by remote text;
- eval/exec of model-produced code as an orchestration primitive.

Allowed handlers are explicit product adapters, for example:
- registered BuildHub job;
- registered project test suite;
- bounded file hash/readback;
- approved deployment/update adapter;
- diagnostic probe.

Each handler has a schema, resource budget, timeout and evidence contract.

## Terminal receipt

A queue acknowledgement is never a terminal receipt.

Terminal receipt minimum:
- job/action/idempotency IDs;
- worker + lease IDs;
- terminal result;
- started/finished timestamps;
- attempt number;
- exact input hash;
- output/effect hash(es);
- exit/result code where applicable;
- evidence/readback payload or pointer;
- coordinator epoch;
- project revision observed;
- error class for failure;
- retryability classification.

A receipt is terminal only if result is one of:
- SUCCEEDED;
- FAILED;
- CANCELLED.

Compatibility aliases such as PASS/SUCCESS/COMMITTED may be normalized at protocol boundaries, but persisted job state uses the canonical state machine.

## Dependency semantics

A dependent job becomes READY only when every required dependency has a verified terminal-success receipt.

QUEUED, ACCEPTED, LEASED, RUNNING, timeout-with-unknown-effect, or transport success MUST NOT unlock dependencies.

## Crash / partition semantics

Worker crash while leased:
- preserve job + attempt;
- lease eventually expires;
- inspect/readback for possible effect before re-execution;
- retry with same logical idempotency key when safe.

B-EDGE loss while PC executes:
- PC may finish an already-leased immutable job;
- store terminal receipt locally;
- do not independently advance global PROJECT_HEAD without valid fence;
- reconcile receipt when coordinator returns.

## Resource policy

The executor shares the low-RAM Windows machine.

Before claim/start:
- inspect RAM/CPU/power/network;
- respect resource class;
- serialize heavy jobs by default;
- use one heavy worker maximum unless field telemetry proves safe;
- checkpoint long jobs when adapter supports it;
- suspend background improvement before user-impacting recovery work.

## Observability

`/v1/orchestrator/status` MUST expose independently:
- durable_queue_ready;
- pc_executor_ready;
- active_worker_count;
- running_job_count;
- leased_job_count;
- terminal_receipt_count;
- oldest_ready_job_age;
- executor_last_heartbeat;
- executor_degraded_reason.

Until an executor exists and passes tests:
`pc_executor_ready = false`.

## Promotion tests

The executor is not ACTIVE until all pass:
1. QUEUED cannot be reported DONE.
2. A queued noop/diagnostic test is claimed, runs, and emits a terminal receipt.
3. Duplicate submission produces one logical effect.
4. Worker crash after effect/before receipt does not duplicate the effect after recovery.
5. Lease expiry + reclaim preserves attempt history.
6. Stale coordinator epoch cannot claim or terminally commit.
7. Dependency unlock requires terminal success.
8. Failed dependency keeps dependent jobs blocked/held.
9. High RAM pressure prevents heavy claim/start.
10. PC reboot resumes durable ready/leased jobs safely.
11. B-EDGE offline during running job preserves receipt for later reconciliation.
12. Unknown job kind is HOLD/REJECT, never arbitrary execution.
13. Telegram/model text cannot inject an arbitrary shell command.
14. Terminal receipt readback is visible from B-EDGE and Context Pack.
