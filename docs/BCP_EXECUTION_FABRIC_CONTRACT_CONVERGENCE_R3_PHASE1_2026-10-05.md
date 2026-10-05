# BCP Execution Fabric — Contract Convergence R3 Phase 1

Date: 2026-10-05  
Status: IMPLEMENTATION_CANDIDATE / NOT FIELD CERTIFIED

## 1. Purpose

Phase 1 converges the already-existing BCP, B-EDGE, ChatGPT-PC/G6 and vNext contracts into one provider-neutral vocabulary.

Doctrine: **REUSE -> ADAPT -> BUILD ONLY IF GAP**.

This phase does not create a second mission kernel and does not promote vNext runtime code.

## 2. Canonical BCP contracts after Phase 1

| Concern | Canonical contract |
|---|---|
| Mission authority | `schemas/bcp_mission_envelope_v2.schema.json` |
| Transport-independent ingress | `schemas/bcp_mission_ingress_v1.schema.json` |
| Project metadata/bindings | `schemas/bcp_project_record_v1.schema.json` |
| Capability definition | `schemas/bcp_capability_manifest_v1.schema.json` |
| Capability runtime observation | `schemas/bcp_capability_observation_v1.schema.json` |
| Consequential permission grant | `schemas/bcp_capability_grant_v1.schema.json` |
| Normalized action proof | `schemas/bcp_action_receipt_v1.schema.json` |
| Desired state | `schemas/bcp_desired_state_resource_v1.schema.json` |

## 3. Project convergence

### ChatGPT-PC Project Capsule -> BCP Project Record

Preserve:
- `project_id`, display name, profile, status;
- continuation codes;
- engineering/runtime/artifact authority;
- GitHub and Drive bindings;
- resource/background profile;
- adapters;
- explicit compatibility/migration rule.

BCP extends the representation with:
- local-root bindings;
- permission profile;
- update profile;
- coordinator epoch/head revision;
- explicit unresolved/candidate states.

Hard rule: an unresolved local path/repository/Drive object remains **UNRESOLVED**. No adapter may invent a binding.

### B-EDGE EdgeProjectEntity -> BCP Project Record

Projection:
- `projectId -> project_id`;
- `status -> status`;
- `headRevision -> head_revision`;
- `coordinatorEpoch -> coordinator_epoch`;
- `updatedAt -> updated_at`.

B-EDGE may retain its compact Room table. Rich metadata remains a projection of the provider-neutral record, not a competing project authority.

## 4. Capability convergence

### Static definition

`bcp.capability_manifest/1` is the stable capability definition:

`provider + capability_id + input/output schema + effect class + permission class + resource class + evidence contract + executor`.

### Dynamic observation

`bcp.capability_observation/1` carries:
- provider/node/project scope;
- observed availability;
- transport;
- evidence class;
- freshness/expiry;
- provider-specific details.

This prevents mutable probe state from becoming part of the capability definition.

### G6 capability probes

G6 `g4.capabilities/2` and Windows capability probes map to one or more capability observations.

### B-EDGE EdgeCapabilityEntity

Projection:
- `capabilityId -> capability_id`;
- `provider -> provider_id`;
- `nodeId -> node_id`;
- `projectId -> project_id`;
- `state -> state`;
- `transport -> transport`;
- `evidenceClass -> evidence_class`;
- `detailsJson -> details`;
- `observedAt/expiresAt -> observed_at/expires_at`.

## 5. Receipt convergence

`bcp.action_receipt/1` is the provider-neutral action proof.

### B-EDGE EdgeReceiptEntity

Projection:
- `actionId -> action_id` and may also seed `receipt_id`;
- `jobId -> job_id`;
- `projectId -> project_id`;
- `idempotencyKey -> idempotency_key`;
- `result -> result/status mapping`;
- `outputHash -> output_hash`;
- `committedRevision -> committed_revision`;
- `createdAt -> created_at`.

### vNext CriticalStore DurableReceipt

Projection:
- `stream_id` is retained in evidence/readback metadata;
- `revision -> committed_revision`;
- `fencing_token -> fencing_token`;
- `content_hash -> content_hash`;
- `predecessor_hash -> predecessor_hash`;
- `outbox_message_id -> outbox_message_id`;
- `idempotent_replay -> idempotent_replay`;
- `DURABLE_LOCAL -> durability=DURABLE_LOCAL`.

The normalized receipt must never weaken fencing or revision semantics.

### G6 journal / side-effect journal

G6 journal references are attached to `side_effects[].journal_ref`.

Journal entries remain chronological/audit data; the receipt is the normalized proof object. They are complementary, not replacements.

## 6. Anti-false-PASS invariant

A receipt is not a field certificate merely because:
- repository checks passed;
- CI passed;
- a provider returned HTTP 200;
- a file exists;
- a process is present.

`field_certified=true` is valid only with `proof_scope=FIELD`.

Field success must include the evidence classes required by the capability contract and the relevant readback.

## 7. Mission ingress convergence

All ingress adapters normalize to `bcp.mission_ingress/1`, which embeds the canonical `bcp.mission_envelope/2`.

Supported transport identities remain:
- CHATGPT;
- TELEGRAM;
- LOCAL_UI;
- DRIVE_MAILBOX;
- NEXUS;
- API;
- RECOVERY.

Transport is not mission authority. Duplicate transport events are rejected/deduplicated by `dedupe_key`.

## 8. Permission and resource invariants

Permission classes remain ordered:

`P0_READ < P1_SAFE_WRITE < P2_PROJECT_MUTATION < P3_BOUNDED_SYSTEM_CHANGE < P4_DESTRUCTIVE_OR_SECURITY_SENSITIVE`.

Resource classes remain:

`R0_TINY < R1_LIGHT < R2_MEDIUM < R3_HEAVY < R4_LOCAL_AI`.

No adapter may silently map a stronger permission/effect into a weaker class.

## 9. Phase 1 acceptance

Phase 1 passes only when:
1. all canonical schema JSON files parse;
2. shared permission/resource/evidence enums are compatible;
3. mission ingress transports are a superset/equal match of Mission Envelope source kinds;
4. capability observation states cover capability-manifest availability states;
5. Project Capsule and B-EDGE project fields can project without semantic loss;
6. EdgeReceipt + CriticalStore durable fields fit the normalized action receipt;
7. anti-false-PASS rule is enforced structurally;
8. a targeted repository test proves these invariants.

## 10. Explicit non-goals

Phase 1 does **not**:
- install or modify the PC;
- merge vNext into G6;
- create a new scheduler;
- create a new Resource Governor;
- create a new updater;
- require Desktop Commander;
- certify any field runtime.

Next phase after Phase 1 PASS: **Phase 2 — PC microkernel convergence**, benchmarking current BCP Windows runtime against G6/vNext and selecting one lightweight resident control process.
