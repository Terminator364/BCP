# BCP Desired State + Recipe / Incident Engine — R3 Phase 4

Date: 2026-10-05  
Status: IMPLEMENTATION_CANDIDATE / STACKED_ON_PHASE_3 / NOT FIELD CERTIFIED

## 1. Objective

Phase 4 implements the roadmap items:

- persistent resource reconciliation;
- known repair recipes;
- friction events.

It does so **without** adding another database, scheduler, resident daemon or shell executor.

The execution ladder remains:

`OBSERVE -> COMPARE -> INCIDENT -> RECIPE -> ADMISSION -> TYPED CAPABILITY -> RECEIPT -> RE-OBSERVE`.

A successful action receipt is not sufficient to declare recovery.

## 2. Reused authority

All Phase 4 runtime state uses the existing Phase 2/3 `CriticalStore`.

Stream namespaces:

- `desired/<project>/<resource-hash>`
- `recipe/<recipe_id>`
- `incident/<project>/<fingerprint>`

They inherit:

- local-only SQLite authority;
- WAL + synchronous FULL;
- monotonic writer fencing;
- revision compare-and-swap;
- canonical content hash / predecessor hash;
- transactional outbox;
- durable history;
- idempotent replay.

No parallel incident DB and no parallel scheduler DB are introduced.

## 3. Desired State

Existing canonical contract is reused unchanged:

`schemas/bcp_desired_state_resource_v1.schema.json`

New runtime module:

`windows/execution_fabric/desired_state.py`

Responsibilities:

- strict contract validation;
- fenced desired-state persistence;
- bounded list/get projections;
- deterministic drift comparison.

### Drift law

The desired object is treated as an invariant subset of observed state.

Extra observed fields do not create drift.

Missing or different desired fields do create deterministic drift paths.

The drift detector performs no mutation and no reasoning.

## 4. Repair Recipe

New gap contract:

`schemas/bcp_repair_recipe_v1.schema.json`

Runtime:

`windows/execution_fabric/repair_recipes.py`

A recipe contains:

- a typed incident match;
- permission/resource ceilings;
- bounded attempts/backoff;
- ordered steps;
- capability IDs;
- required evidence;
- failure policy;
- provenance.

It does **not** contain:

- shell commands;
- argv;
- executable paths chosen by the remote caller;
- PowerShell/CMD snippets.

### Validation levels

Recipes are one of:

- `DRAFT`
- `REPOSITORY_VALIDATED`
- `FIELD_VALIDATED`
- `RETIRED`

Hard invariant:

`auto_eligible=true -> status=FIELD_VALIDATED`.

Repository CI can prove recipe structure and regressions. It cannot promote a system mutation recipe to automatic field execution.

## 5. Incident engine

New contract:

`schemas/bcp_incident_v1.schema.json`

Runtime:

`windows/execution_fabric/incident_engine.py`

Incident classes:

- DRIFT
- FRICTION
- CAPABILITY
- RESOURCE
- PROVIDER
- AUTH
- UPDATE
- UNKNOWN

Incident state is deterministic and durable.

Repeated identical drift/friction produces the same fingerprint and increments occurrence count instead of creating noisy duplicate incidents.

## 6. Reconciliation decision

The engine receives an explicit observation plus:

- project/resource identity;
- capability observations;
- current resource mode;
- desired-state policy.

It then evaluates:

1. desired-vs-observed drift;
2. matching recipe;
3. recipe validation level;
4. desired permission ceiling;
5. desired resource ceiling;
6. live GREEN/AMBER/RED/CRITICAL admission;
7. capability availability;
8. attempt ceiling.

Possible outcomes include:

- IN_SYNC
- NEEDS_REASONING
- WAITING_APPROVAL
- WAITING_RESOURCE
- WAITING_CAPABILITY
- RECONCILING
- FAILED_SAFE

No background retry loop is created by Phase 4.

A future scheduler/controller may call reconciliation ticks using the same durable state.

## 7. Anti-false-PASS rule

When a recipe step returns a successful `bcp.action_receipt/1`:

- the step may become `DONE`;
- the incident remains `RECONCILING`.

Only a subsequent observation proving the desired invariants may:

- set Desired State to `IN_SYNC`;
- set the matching drift incident to `RECOVERED`.

Therefore:

`ACTION PASS != SYSTEM RECOVERED`.

## 8. Friction events

Phase 4 records avoidable user/platform friction as durable incidents.

Examples:

- repeated QR re-pairing;
- repeated manual command mechanics;
- repeated auth/bootstrap mechanics;
- user forced to repeat a known recovery sequence.

A friction fingerprint is stable across recurrence.

Known friction may match a recipe, but recipe execution still requires policy/resource/capability admission.

This is how BCP can learn from recurrent operational friction without making ChatGPT reasoning a runtime clock.

## 9. Error Ledger convergence

The existing:

`.project-memory/ERROR_LEDGER.jsonl`

remains historical technical knowledge.

Phase 4 does not reinterpret every ledger row as an executable recipe.

A ledger incident can seed a typed repair recipe only when:

- the mechanism is understood;
- regression evidence exists;
- the repair is capability-typed;
- permission/resource/evidence contracts are explicit.

Example:

`BCP-ARCH-0003` seeds:

`bcp.windows.startup.remove-legacy-supervisor`

Its current state is:

- `REPOSITORY_VALIDATED`
- `auto_eligible=false`

because startup mutation has not yet been field-certified under the new fabric.

## 10. BCP startup desired-state example

Example resource:

`docs/examples/execution-fabric/bcp-microkernel-startup.desired-state.example.json`

Desired invariants include:

- primary trigger = HKCU_RUN;
- legacy BCP scheduled task absent;
- legacy PowerShell supervisor absent;
- ChatGPT-PC not required for BCP startup.

This is an engineering desired state, not current field truth.

Field inventory must still observe the actual PC.

## 11. Read-only microkernel API

Phase 4 adds only:

- `GET /v2/desired?project=...`
- `GET /v2/recipes`
- `GET /v2/incidents?project=...`

There is no:

- `POST /v2/desired`
- `POST /v2/recipes`
- `POST /v2/incidents`
- `POST /v2/reconcile`

Mutation remains an internal policy/capability responsibility until permission/grant routing is connected.

## 12. Repository acceptance

Targeted Phase 4 gate must prove:

1. all new modules compile;
2. desired state uses the same CriticalStore/outbox;
3. deterministic subset drift;
4. recipe free-form execution fields are rejected;
5. repository-validated recipe cannot auto-run;
6. no-recipe drift becomes NEEDS_REASONING;
7. permission ceiling blocks unsafe recipe;
8. AMBER/RED resource policy blocks excess work;
9. unavailable capability blocks repair;
10. field-validated admitted recipe reaches RECONCILING;
11. attempt ceiling becomes FAILED_SAFE;
12. successful step receipt does not mark RECOVERED;
13. fresh conforming observation marks IN_SYNC/RECOVERED;
14. repeated friction reuses the same fingerprint;
15. Phase 1/2/3 regressions remain green;
16. HTTP Phase 4 surface is read-only.

## 13. Field gates still required

Phase 4 repository PASS is not field PASS.

Field promotion requires at least:

- actual BCP startup inventory;
- actual resource snapshot on MBMPC;
- actual capability observations;
- exact local/project bindings;
- field action receipts;
- post-action readback;
- evidence that the reconciled invariant is true.

Desktop Commander remains last-mile/metered and is not part of normal reconciliation.

## 14. Next roadmap phase

After Phase 4 repository gate:

**Phase 5 — Release / Update Controller**

Required reuse:

- project-specific qualified manifests;
- CriticalStore/outbox;
- Project Registry;
- Desired State;
- Incident engine;
- LKG/rollback contracts;
- provenance and migration-safety checks.

Phase 5 must not create a second updater for projects that already have a qualified updater. It coordinates typed release capabilities.
