# BCP Project Registry + Typed Adapter — R3 Phase 3

Date: 2026-10-05  
Status: IMPLEMENTATION_CANDIDATE / STACKED_ON_PHASE_2 / NOT FIELD CERTIFIED

## 1. Objective

Phase 3 turns BCP's provider-neutral project contract into a durable registry without creating a second mission/state database.

First client used for proof: **MED_REBUILD**.

MED_REBUILD remains a project client. BCP remains mission/routing/policy/evidence authority.

## 2. Registry architecture

Canonical storage:
- same local `bcp.sqlite3`;
- same Phase 2 `CriticalStore`;
- stream namespace: `project/<project_id>`.

No separate hot project DB is introduced.

Each write inherits:
- monotonic writer fencing;
- compare-and-swap revision;
- content hash/predecessor hash;
- atomic replication outbox;
- durable history.

Project listing is a bounded projection of `authority_state` by the `project/` prefix.

## 3. Runtime module

`windows/execution_fabric/project_registry.py`

Capabilities:
- validate project record;
- `put` with revision/fencing;
- exact unchanged record -> no revision churn;
- `get`;
- bounded `list`;
- resolve exact ID;
- resolve aliases;
- fail closed on ambiguous aliases.

## 4. Anti-invention law

BCP must never create a project binding because it is plausible.

Validation rules include:
- `BOUND local_root` requires a path;
- `UNRESOLVED local_root` must not assert a path;
- `BOUND repo` requires a repository;
- `UNRESOLVED repo` must not assert a repository;
- `BOUND/PARTIAL Drive` requires an object id;
- conversation is always `NON_AUTHORITATIVE`.

Discovery and authority are separate:
- a PC probe may observe a candidate path;
- policy/adapter logic may validate it;
- only then can a later project record revision move from `UNRESOLVED` to `BOUND`.

## 5. Read-only API

Phase 3 adds:
- `GET /v2/projects`
- `GET /v2/projects/resolve?identifier=...`

No generic project-registry write endpoint is introduced.

Writes remain internal until the permission/capability-grant plane is connected.

## 6. Typed Project Adapter contract

New schema:
`schemas/bcp_project_adapter_v1.schema.json`

An adapter binds **operations to capability IDs**.

It does not carry:
- shell commands;
- argv;
- PowerShell snippets;
- CMD strings;
- executable paths supplied by a remote user.

Execution mechanics belong to the capability manifest/provider implementation.

Adapter states:
- `BOUND`;
- `WAITING_BINDING`;
- `TEMP_UNAVAILABLE`;
- `UNSUPPORTED`.

## 7. MED_REBUILD binding truth

Observed engineering binding:
- repository: `Terminator364/ChatGPT-PC`;
- branch: `feat/med-rebuild-study-engine-v1-5`;
- path: `med-rebuild-study-hub/v1.5-prototype`;
- runtime authority: PC.

Still unresolved:
- exact local PC project root;
- canonical local runtime process binding;
- local updater/LKG authority as a BCP capability;
- artifact authority outside the repository.

Therefore:
- repository `RELEASE_VERIFY` may be `BOUND`;
- PC `INSPECT`, `TEST`, `HEALTHCHECK`, `UPDATE_ACTIVATE`, `ROLLBACK` remain `WAITING_BINDING`.

This is intentional. The registry is not allowed to turn prior assumptions into local authority.

## 8. Tests

Phase 3 tests cover:
- register/get/list/alias resolution;
- unchanged put does not churn revision;
- update increments revision;
- stale expected revision fails closed;
- alias ambiguity fails closed;
- registry writes use the same transactional outbox;
- unresolved root cannot carry an invented path;
- bound repository requires a real repository value;
- conversation cannot become authority;
- adapter has no command/argv/shell field;
- PC operations remain waiting until field binding;
- adapter evidence/permission/resource vocabularies stay within canonical capability manifest enums.

## 9. Field gates still required

Before MED_REBUILD PC operations can become BOUND:
1. read-only PC inventory finds the actual local root;
2. runtime/process/port identity is read back;
3. updater and rollback/LKG authority are observed;
4. resource class is confirmed on the real PC;
5. capability manifests are bound to typed executors;
6. permission and evidence contracts pass;
7. field receipt is produced.

Repository CI is not field proof.

## 10. Next work after Phase 3 repository gate

Phase 4:
**Desired State + Recipe/Incident engine**

Reuse:
- existing BCP desired-state schema;
- G6 side-effect journal;
- BCP Error Ledger / validated recipes;
- CriticalStore revision/fencing/outbox.

Do not create a parallel incident or scheduler database.
