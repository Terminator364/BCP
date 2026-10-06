# BCP Desired State + Incident/Recipe Engine — R3 Phase 4

Date: 2026-10-05  
Status: IMPLEMENTATION_CANDIDATE / STACKED / NOT FIELD CERTIFIED

## 1. Objective

Phase 4 adds persistent desired-state reconciliation and evidence-gated failure learning without creating a second mission database, scheduler, Resource Governor, or shell-based repair engine.

Everything durable is stored through the existing Phase 2 `CriticalStore`. There is one canonical Phase 4 implementation: `desired_state_registry.py`, `incident_recipe.py`, `action_receipt_registry.py`. No parallel desired-state or incident engine is retained.

## 2. Durable namespaces

- Desired resources: `desired/<project_id>/<resource_id>`
- Incidents: `incident/<project_id>/<resource_id>/<causal_signature>`
- Repair recipes: `recipe/<recipe_id>`
- Action receipts: `receipt/<sha256(receipt_id)>`

All inherit local-only SQLite, WAL + FULL sync, writer fencing, revision CAS, hash chain, atomic outbox and history.

## 3. Desired State Registry

Module: `windows/execution_fabric/desired_state_registry.py`

Rules:
- first generation is exactly 1 and begins unobserved (`observed_generation=0`, `phase=UNKNOWN`);
- a desired-state writer cannot self-certify observation of the generation it is creating;
- spec changes require generation +1;
- generation gaps are rejected;
- same generation may not change desired spec;
- exact same spec is idempotent and does not churn revision;
- observed status may change without changing desired generation;
- status may not claim observation of a future generation;
- stale status writers fail closed.

This prevents a reconciler from changing the desired target merely to report success.

## 4. Deterministic drift and incident identity

BCP computes desired-vs-observed drift itself using a bounded desired-subset comparator. A provider cannot supply a trusted `matches_desired=true` flag.

Extra observed fields are tolerated. Missing desired fields, type mismatches and value mismatches create deterministic drift paths. Those paths/reasons seed the causal incident signature.

Only a later conforming observation may resolve a drift incident. A successful action receipt alone never marks the system recovered.

## 5. Incident identity

A causal incident signature is SHA-256 over canonical project id, resource id and structured symptoms.

Environment fingerprint is retained separately. Repeated observations of the same causal incident update the same durable incident stream.

When the Desired State generation changes, the same causal signature starts a new repair episode: attempts, backoff, prior repair receipts and last error are reset. An old failure budget cannot block a new desired objective.

## 6. Repair recipe lifecycle

New schema: `bcp.repair_recipe/1`

States: CANDIDATE, VALIDATED, SUSPENDED, RETIRED.

A new recipe must enter as CANDIDATE.

VALIDATED requires:
- references to **real immutable `bcp.action_receipt/1` records** in the shared CriticalStore;
- each non-optional recipe capability must be covered by at least one durable SUCCEEDED/PASS receipt;
- at least one regression reference;
- when `field_evidence_required=true`, field-certified receipts (`proof_scope=FIELD`) must cover the same required capabilities.

A string that merely looks like a receipt ID is not evidence and cannot promote a recipe.

A recipe cannot contain command, argv, shell, script/executable injection, or PowerShell/CMD command strings. It contains typed `capability_id` steps with permission/resource/evidence contracts.

## 7. Reconciliation planning

Module: `windows/execution_fabric/incident_recipe.py`

Planner order:
1. observation matches desired -> IN_SYNC;
2. insufficient symptoms -> NEEDS_REASONING;
3. persist/update incident;
4. OBSERVE_ONLY -> OBSERVE_ONLY_DRIFT;
5. max attempts -> FAILED_SAFE;
6. active backoff -> WAITING_BACKOFF;
7. match exactly one VALIDATED recipe;
8. no validated recipe -> NEEDS_REASONING;
9. multiple validated recipes -> FAILED_SAFE;
10. permission/resource policy ceiling check;
11. current Resource Governor admission check;
12. emit `EXECUTE_TYPED_PLAN` containing capability IDs only.

The planner never executes its own plan.

## 8. Historical Error Ledger reuse

Module: `windows/execution_fabric/legacy_error_ledger.py`

The existing `.project-memory/ERROR_LEDGER.jsonl` remains historical causal knowledge. FIXED rows with regression/prevention evidence may become recipe-authoring candidates, but the projection is non-executable, CANDIDATE_ONLY, never silently VALIDATED, and never field-certified.

## 9. Friction ledger and read-only microkernel views

Operational friction is stored under `friction/<project>/<signature>`, deduplicated by stable fingerprint, and is never executable authority.

Phase 4 adds authenticated read-only views:
- `GET /v2/desired`
- `GET /v2/recipes`
- `GET /v2/incidents`
- `GET /v2/friction`

There are deliberately no dedicated remote POST endpoints for desired resources, incidents, recipes or reconcile plans in this phase.

## 10. Security boundary

The raw CriticalStore is an internal authority primitive.

The generic Phase 2 development endpoints `/v2/authority/fence` and `/v2/authority/transition` are **absent from the current network surface**. They remain internal CriticalStore primitives only.

Typed domain/capability APIs are the only acceptable future mutation path. Phase 4 does not expose POST endpoints for Desired State, recipes, incidents or reconciliation plans.

## 11. Failure-injection coverage

Tests cover stale/gapped desired generations, self-certification attempts, schema drift, BCP-computed drift, provider false-PASS rejection, spec mutation without generation bump, stale status writer, future observed generation, candidate recipe non-execution, command smuggling rejection, invented/unrelated receipts, immutable receipt collision, mandatory field proof for P3, capability unavailability, validated-recipe overwrite prevention, desired-generation incident reset, action-PASS-without-recovery, friction deduplication, observe-only drift, permission/resource policy blocks, RAM pressure deferral, retry backoff, max-attempt fail-safe, ambiguous recipes, and historical Error Ledger non-promotion.

## 12. Phase 4 acceptance

Repository PASS requires:
1. schemas parse;
2. Desired State tests pass;
3. Incident/Recipe failure-injection tests pass;
4. Error Ledger projection tests pass;
5. static boundary guard passes;
6. upstream regressions remain green;
7. no field certification claim.

## 13. Next phase

**Phase 5 — Release/update controller**

Reuse existing BCP release contracts, G6 package/update receipts, BCP rollback experience, and Desired State/Recipe invariants. Do not build another project-specific updater.
