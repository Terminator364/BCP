# BCP PC Microkernel Convergence — R3 Phase 2

Date: 2026-10-05  
Status: IMPLEMENTATION_CANDIDATE / STACKED_ON_PHASE_1 / NOT FIELD CERTIFIED

## Decision

**Canonical resident-process target: evolve `windows/bcp_server_v2.py`.**

Do not create a third BCP server.

## Why V2

Repository benchmark:

| Candidate | Approx size | Durable core | Provider-specific background machinery | Decision |
|---|---:|---|---|---|
| `windows/bcp_server.py` | ~255 KB | substantial | Telegram, Nexus, updater, watchdogs, bridges, retries embedded | COMPATIBILITY / DECOMPOSE |
| `windows/bcp_server_v2.py` before Phase 2 | ~17 KB | SQLite WAL + idempotent event/head chain | minimal | **ADAPT AS MICROKERNEL** |
| ChatGPT-PC G6 runtime | separate product/control corridor | mature | owns ChatGPT-PC concerns | KEEP AS BRIDGE/PROVIDER |
| ChatGPT-PC vNext | design/prototype components | strongest fenced store + worker isolation | not field-promoted as a full runtime | REUSE COMPONENTS ONLY |
| Evergreen PowerShell supervisor | legacy startup/recovery | process supervision | parallel resident machinery | RETIRE AFTER MIGRATION |

## Microkernel boundary

The resident BCP core may own:
- local durable authority state;
- fencing/revisions/idempotency;
- transactional replication outbox;
- mission ingress normalization;
- project/capability/receipt registries;
- resource admission;
- typed worker dispatch;
- local health/readback;
- provider adapter lifecycle.

The resident core must **not** embed:
- Telegram polling business logic;
- Nexus deployment logic;
- project-specific updater loops;
- BuildHub implementation;
- Delivery implementation;
- local LLM;
- arbitrary shell execution.

Those remain typed capabilities/providers.

## Phase 2 tranche A implemented

Reused from ChatGPT-PC vNext source commit:
`6bf6e32b36008957dda014542742657af6b9e017`

Components:
- `windows/execution_fabric/local_path_policy.py`
- `windows/execution_fabric/critical_store.py`

Preserved invariants:
- local-only hot SQLite state;
- WAL + synchronous FULL;
- monotonic per-stream writer fencing;
- revision compare-and-swap;
- canonical content hash and predecessor hash;
- state + outbox atomic commit;
- idempotent exact replay;
- claimed outbox delivery leases;
- retry backoff;
- durable history and quick integrity check.

## BCP Server V2 integration

`bcp_server_v2.py` remains backward compatible with:
- `/health`;
- V1 pairing;
- V1 telemetry;
- V1 project event/head/resume endpoints.

Added Phase 2 authority **read-only diagnostic** endpoints:
- `GET /v2/authority/state?stream=...`
- `GET /v2/authority/history?stream=...`
- `GET /v2/outbox/due`

Writer fencing and `commit_transition` remain internal Python primitives. The counter-audit explicitly removed raw HTTP `/v2/authority/fence` and `/v2/authority/transition` because generic remote state mutation would bypass typed Project/Desired/Recipe validation and future capability grants.

## Database convergence

Phase 2 intentionally uses the **same local `bcp.sqlite3`**:
- legacy `events` / `heads` tables remain compatibility projections;
- fenced authority/history/outbox tables coexist in the same local SQLite authority DB.

This avoids two hot databases and enables gradual migration.

## Startup convergence policy

Not yet field-promoted.

Target rule:
1. one primary resident-process trigger;
2. one bounded stale-health fallback;
3. no simultaneous ChatGPT-PC manager + Task Scheduler + PowerShell supervisor loops after migration.

The exact field trigger is selected only after the read-only Phase 2 startup inventory.

## Security boundary

Phase 2 does not add arbitrary command execution **or generic remote authority mutation**.

CriticalStore writes are internal primitives. Network mutation must arrive through typed domain/capability handlers that apply project scope, permission, resource and evidence contracts before committing authority state.

## Acceptance for tranche A

PASS requires:
1. critical-store tests pass;
2. BCP Server V2 selftest passes;
3. same-revision/different-payload fails closed;
4. stale fence fails closed;
5. exact replay is idempotent;
6. state and outbox commit atomically;
7. hot DB rejects provider/network-sync paths;
8. V2 core has no Telegram/Nexus/update polling dependency;
9. no field certification is claimed.

## Next Phase 2 tranche

**Worker containment + resource admission**:
- reuse ChatGPT-PC `WorkerSupervisor` / Windows Job Object logic;
- expose only typed worker profiles;
- integrate GREEN/AMBER/RED admission;
- failure-inject timeout/process-tree termination;
- keep Desktop Commander outside the normal loop.


## Phase 2 tranche B implemented

Reused from ChatGPT-PC vNext source commit:
`6bf6e32b36008957dda014542742657af6b9e017`

Components:
- `windows/execution_fabric/worker_supervisor.py`;
- `windows/execution_fabric/worker_bootstrap.py`;
- `windows/execution_fabric/resource_admission.py`.

Preserved/adapted invariants:
- real project process is not spawned before the bootstrap is attached to the Windows Job Object;
- Job Object applies per-process and whole-job memory caps plus kill-on-job-close;
- worker stdout/stderr and inline input are bounded;
- worker timeout terminates the bounded process tree;
- GREEN/AMBER/RED/CRITICAL thresholds follow the established G6 constrained-PC policy;
- R4 local AI is explicitly denied during Phase 2;
- background work is stricter than foreground work;
- no free-form command/argv endpoint exists in the BCP microkernel.

Read-only runtime endpoint:
- `GET /v2/resources` returns the current resource snapshot.

The WorkerSupervisor is an internal execution primitive. A future typed capability dispatcher may call it only after:
1. capability-manifest lookup;
2. project-scope validation;
3. permission admission;
4. resource admission;
5. evidence-contract binding.

It must never be exposed as a generic shell/command API.

## Phase 2 tranche B acceptance

PASS requires:
1. G6-derived 4 GiB thresholds classify GREEN/AMBER/RED/CRITICAL correctly;
2. AMBER blocks R2/R3;
3. RED admits only R0;
4. CRITICAL admits only essential R0 work;
5. R4_LOCAL_AI remains denied;
6. Windows worker policies require a Job Object;
7. non-Windows simulation proves the bounded bootstrap path;
8. timeout failure injection produces `WorkerTimeout`;
9. no `/v2/execute`, remote `argv`, or remote `command` surface exists;
10. no field certification is claimed.

## Remaining Phase 2 work

Before field promotion:
- targeted CI for tranches A+B;
- read-only startup inventory on the PC;
- select one primary startup trigger and one bounded fallback;
- Windows-native Job Object field proof;
- resource snapshot/readback on the actual 4 GiB PC;
- compatibility proof that legacy `bcp_server.py` can be decomposed without losing Telegram/Nexus/Delivery provider behavior.

No Phase 2 field PASS is allowed from repository or Linux CI alone.


## Startup consolidation candidate decision

Repository evidence shows three historical startup generations:
1. legacy `BCP Resident Agent` Task Scheduler + `bcp_supervisor.ps1`;
2. ChatGPT-PC managed-app registration plus direct process start;
3. BCP self-registration in `HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run`.

Phase 2 candidate decision:
- **PRIMARY:** the microkernel's own idempotent per-user `HKCU Run` entry named `BlessingControlPlane`;
- **BRIDGE/PROVIDER:** ChatGPT-PC may inspect/restart BCP through typed capabilities, but BCP startup must not require ChatGPT-PC to be healthy;
- **RETIRE AFTER MIGRATION:** `BCP Resident Agent` scheduled task and `bcp_supervisor.ps1`;
- **FALLBACK:** `UNRESOLVED_FIELD` until the read-only PC startup inventory proves what is installed and which one bounded stale-health mechanism is safe.

This choice preserves the goal of one lightweight resident BCP process and avoids replacing one dependency loop with another.


## Counter-audit hardening after first CI

The first targeted Phase 2 run proved:
- compile PASS;
- CriticalStore durability/failure tests PASS;
- integrated server selftest PASS;
- resource admission / WorkerSupervisor simulation PASS.

The only initial failure was a static-test escaping bug for the Windows Run-key string, not a runtime failure.

Before accepting that green path, a second security counter-audit found the raw CriticalStore POST endpoints too broad. They were removed before promotion.

CI routing was also hardened with workflow concurrency/cancel-in-progress so superseded Phase 2 runs do not consume targeted runner budget unnecessarily.
