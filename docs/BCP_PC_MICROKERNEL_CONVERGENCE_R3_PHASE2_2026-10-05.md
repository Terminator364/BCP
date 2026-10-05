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

Added Phase 2 authority endpoints:
- `GET /v2/authority/state?stream=...`
- `GET /v2/authority/history?stream=...`
- `GET /v2/outbox/due`
- `POST /v2/authority/fence`
- `POST /v2/authority/transition`

These are candidate interfaces only. They do not certify field installation.

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

Phase 2 does not add arbitrary command execution.

The V2 authority endpoints mutate only the local durable state machine.
Typed capability execution and Windows Job Object containment are the next Phase 2 tranche.

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
