# BCP Release / Update Controller — R3 Phase 5

Date: 2026-10-05  
Status: IMPLEMENTATION_CANDIDATE / STACKED_ON_PHASE_4 / NOT FIELD CERTIFIED

## Decision

Phase 5 is a **release transaction orchestrator**, not a universal updater.

BCP owns:
- release policy;
- project/release identity;
- monotonic sequence and anti-downgrade;
- provenance references;
- migration classification;
- LKG proof requirements;
- typed operation ordering;
- Action Receipt validation;
- exact post-activation / post-rollback readback;
- durable recovery state.

Project/provider capabilities own:
- build;
- package;
- download/transfer;
- staging;
- activation;
- health probe;
- rollback.

No project installer is reimplemented in BCP.

## Shared authority

Release transactions use the existing Phase 2 CriticalStore:

`release/<project>/<release_id>`

They inherit:
- fencing;
- revision CAS;
- hash chain;
- transactional outbox;
- durable history;
- idempotent replay.

No release-specific hot database is introduced.

## Contract

`schemas/bcp_release_transaction_v1.schema.json`

A transaction contains:
- candidate immutable release ref;
- observed/current release ref;
- proven LKG ref;
- migration policy;
- release policy;
- typed Project Adapter operation bindings;
- normalized Action Receipt IDs;
- candidate readback;
- rollback readback;
- failure/hold reason.

A generic monotonic `sequence` is used for anti-replay / anti-downgrade. BCP does not attempt to compare arbitrary product version strings.

## Project Adapter execution path

Phase 5 requires these typed operations:

1. `RELEASE_VERIFY`
2. `UPDATE_STAGE`
3. `UPDATE_ACTIVATE`
4. `HEALTHCHECK`
5. `ROLLBACK` when rollback policy requires it

Bindings come from `bcp.project_adapter/1`.

Missing operations are represented as `UNSUPPORTED` with null capability/provider fields. BCP does not invent a capability ID.

## Normal state path

`DISCOVERED`
→ `VERIFY_READY`
→ `STAGE_READY`
→ `ACTIVATE_READY`
→ `HEALTH_PENDING`
→ exact readback
→ `COMMIT_READY`
→ `COMMITTED`

The controller does not call an executable directly. It consumes typed Action Receipts from the capability plane.

## Proof law

For every operation, its Action Receipt must:
- match project;
- match provider;
- match capability ID;
- contain the binding's evidence contract.

For FIELD target:
- UPDATE_ACTIVATE receipt must be FIELD proof;
- HEALTHCHECK receipt must be FIELD proof;
- ROLLBACK receipt must be FIELD proof;
- `field_certified=true` is mandatory for those receipts.

A successful activation receipt is not a committed release.

Commit requires exact post-activation readback:
- version;
- sequence;
- artifact SHA-256;
- health PASS.

## LKG law

If rollback is required:
- an LKG must exist;
- it must be proven;
- a FIELD transaction requires FIELD-proven LKG.

Normal activation is held at `WAITING_LKG` otherwise.

Rollback is two-stage proof:
1. typed ROLLBACK Action Receipt;
2. exact LKG version/sequence/hash + health readback.

Only then is the transaction `ROLLED_BACK`.

## Anti-downgrade and stale recovery

Normal release candidate:

`candidate.sequence > current.sequence`

If candidate sequence is older/equal, the transaction becomes:

`SUPERSEDED_NO_ROLLBACK`

with:
`RELEASE_LINE_RECONCILIATION_REQUIRED`.

Crash recovery carries the G6 invariant forward:

If a stale/incomplete transaction exists but a newer or equal release is already durably COMMITTED, recovery **must not restore the old LKG over the newer release**.

It becomes:
`SUPERSEDED_NO_ROLLBACK`.

## Migration safety

Migration classes:
- NONE
- BACKWARD_COMPATIBLE
- REVERSIBLE
- IRREVERSIBLE

IRREVERSIBLE without explicit approval:
`WAITING_APPROVAL`.

Project semantics and destructive/security-sensitive changes are not silently promoted.

P4 Project Adapter bindings are representable in the transaction, but the automatic policy ceiling remains P3. P4 therefore becomes a hold, not an invalid manifest and not an automatic action.

## Resource policy

All required operations are checked against:
- transaction resource ceiling;
- current GREEN / AMBER / RED / CRITICAL admission.

A release transaction may therefore remain `WAITING_RESOURCE` even when a capability is correctly bound.

## MED-REBUILD vertical

Example:
`docs/examples/execution-fabric/med-rebuild.release-transaction-hold.example.json`

This is deliberately a **safe HOLD**, not a product release.

Current generic proof:
- RELEASE_VERIFY is bound to GitHub;
- UPDATE_STAGE is not declared by the Phase 3 adapter;
- PC UPDATE_ACTIVATE / HEALTHCHECK / ROLLBACK remain WAITING_BINDING;
- local PC project root is still unresolved from Phase 3.

Result:
`WAITING_CAPABILITY`.

BCP therefore proves it can refuse to fake “zero touch” when the field capability plane is incomplete.

## Read-only API

Added:
- `GET /v2/releases?project=...`

Not added:
- POST update;
- POST activate;
- POST rollback;
- POST release commit.

Mutation remains internal to the permission/capability plane.

## Reused prior work

Phase 5 preserves and generalizes:
- `bcp_current_release/1`;
- BCP CURRENT hash/rollback policy;
- Project Release Controller R2 design;
- B-EDGE anti-downgrade law;
- project-specific updaters;
- G6 managed-app transaction laws:
  - monotonic sequence;
  - backup before mutation;
  - payload readback;
  - rollback on failure;
  - interrupted transaction recovery;
  - SUPERSEDED_NO_ROLLBACK.

It reuses the **laws**, not the project updater implementation.

## Repository acceptance

PASS requires:
1. controller/schema compile and parse;
2. happy release cannot COMMIT before exact readback;
3. anti-downgrade holds;
4. missing/unproven LKG holds;
5. irreversible migration holds for approval;
6. P4 binding holds;
7. resource pressure holds;
8. MED_REBUILD remains WAITING_CAPABILITY;
9. receipt project/provider/capability/evidence binding is enforced;
10. FIELD activation/health/rollback receipts require FIELD certification;
11. activation failure enters rollback path;
12. rollback requires exact LKG readback;
13. mismatched candidate readback requires rollback/fail-safe;
14. stale interrupted transaction cannot overwrite newer commit;
15. no generic downloader/installer/shell exists in ReleaseController;
16. HTTP release surface is read-only;
17. Phase 4/3/microkernel regressions remain green.

## Field gates

Repository PASS is not field PASS.

Before any actual project activation:
- exact project binding;
- qualified candidate;
- capability observations;
- resource admission;
- proven LKG;
- target-specific receipts;
- exact field readback.

Desktop Commander remains LAST_MILE_METERED and is not part of normal release operation.

## Next roadmap phase

After Phase 5 repository PASS:

**Phase 6 — Transport / Cockpit**

The transport layer must carry mission/progress/receipt projections without becoming mission authority or a hidden runtime clock.
