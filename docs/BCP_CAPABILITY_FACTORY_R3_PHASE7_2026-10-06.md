# BCP Capability Factory — R3 Phase 7

Date: 2026-10-06  
Status: IMPLEMENTATION_CANDIDATE / NOT FIELD CERTIFIED

## 1. Objective

Phase 7 implements the R3.1-ABC Capability Factory as an **evidence-gated admission and promotion pipeline**.

It does not create another resident agent, package manager, updater, shell executor, resource governor or mission authority.

BCP remains:
- mission authority;
- policy authority;
- project/capability registry authority;
- evidence/receipt authority.

Providers execute typed capabilities only after admission.

## 2. Canonical pipeline

The R3 policy pipeline is preserved:

1. GAP_DETECTED
2. DEFINE_CONTRACT
3. REUSE_SEARCH
4. SOURCE_TRUST_CHECK
5. LICENSE_POLICY_CHECK
6. BUILD_ADAPTER
7. STATIC_VALIDATE
8. SANDBOX_TEST
9. RESOURCE_TEST
10. ROLLBACK_TEST
11. SECURITY_TEST
12. CANARY
13. REGISTER
14. execute the original intent through the normal capability/grant path
15. learn a repair recipe only from verified outcomes.

The durable candidate begins at **REUSE_SEARCH** because GAP_DETECTED and DEFINE_CONTRACT are intake/design steps that must already have produced a typed capability contract before executable admission can begin.

## 3. Reused components — no reinvention

### Existing BCP contracts

Phase 7 reuses:
- `bcp.capability_manifest/1`;
- `bcp.capability_grant/1`;
- `bcp.project_adapter/1`;
- `bcp.action_receipt/1`;
- Phase 2 `CriticalStore` + Resource Admission;
- Phase 5 Release Controller for qualified artifact promotion/rollback;
- Phase 6 transport/cockpit for human projection only.

### ChatGPT-PC / G6 primitives

Reference source inspected from ChatGPT-PC main revision:
`7f3a04d4a597086e2505bfc5e31bc02497bd963e`.

Reused laws/primitives:
- `pca/untrusted.py`: external source data is non-actionable until admitted;
- `pca/capabilities.py`: target/native capability probes and freshness;
- `pca/registry.py`: local-root, managed-app, argv and resource-profile validation;
- `pca/runner.py`: registered argv only, `shell=False`, bounded timeout/output and Job memory limit;
- `pca/safezip.py`: path traversal, symlink and uncompressed-size protection;
- `pca/windows_lab.py`: native Windows/resource/Job Object/sandbox-adjacent qualification;
- `pca/requirement_enforcement.py`: pre-action invariants and anti-false-field-PASS.

Phase 7 composes these through typed providers. It does not copy their full control plane into BCP.

## 4. Contracts

Added:
- `schemas/bcp_capability_factory_candidate_v1.schema.json`;
- `schemas/bcp_capability_factory_plan_v1.schema.json`;
- `schemas/bcp_capability_registration_v1.schema.json`.

Durable namespaces:
- candidate: `capability-factory/<project>/<candidate_id>`;
- registration: `capability-registration/<sha256(capability|provider|version)>`.

All share the existing fenced CriticalStore.

## 5. Trust model

Trust classes:
- T0_BUILTIN;
- T1_VERIFIED_LOCAL;
- T2_VERIFIED_REMOTE;
- T3_CANDIDATE;
- T4_QUARANTINED.

A new Factory candidate starts only as:
- T3_CANDIDATE, or
- T4_QUARANTINED.

It cannot self-declare T0/T1/T2.

Automatic promotion may end only in T1 or T2:
- **T1_VERIFIED_LOCAL** requires a FIELD canary Action Receipt and `field_certified=true`;
- **T2_VERIFIED_REMOTE** requires provider-or-better canary proof;
- repository/simulation canary cannot produce unattended registered capability authority.

T0 is reserved for pre-existing built-ins admitted outside this candidate path.

## 6. Source and license gates

A candidate source records:
- source kind;
- locator;
- immutable revision where available;
- artifact SHA-256 where available;
- publisher.

Source-trust and license checks are typed gates with Action Receipts.

T4 source:
- QUARANTINED.

Denied license:
- QUARANTINED.

Unknown/review-required license:
- WAITING_APPROVAL.

No arbitrary external text is executable authority.

## 7. Typed gate law

The Factory itself never runs candidate code.

`plan_next()` emits a `bcp.capability_factory_plan/1` containing only:
- candidate/project IDs;
- gate ID;
- typed `capability_id`;
- permission class;
- resource class;
- target proof scope;
- structured input;
- evidence contract.

No:
- command;
- argv;
- shell;
- PowerShell command string;
- CMD command string;
- network/provider invocation.

Each gate receipt must match:
- project;
- exact gate capability;
- deterministic idempotency key `factory:<candidate>:<gate>`;
- source revision when both sides provide it;
- minimum proof scope;
- gate evidence contract.

A successful receipt from another candidate or another source revision cannot advance the candidate.

## 8. Permission/effect law

Capability manifest effect and permission class must be semantically identical:

- READ_ONLY -> P0_READ
- SAFE_WRITE -> P1_SAFE_WRITE
- PROJECT_MUTATION -> P2_PROJECT_MUTATION
- BOUNDED_SYSTEM_CHANGE -> P3_BOUNDED_SYSTEM_CHANGE
- DESTRUCTIVE_OR_SECURITY_SENSITIVE -> P4

The automatic Factory does not qualify P4.

P4 requires a separate fresh human-approved lane outside this unattended Phase 7 path.

## 9. Resource / local-AI law

Automatic Phase 7 supports:
- R0_TINY;
- R1_LIGHT;
- R2_MEDIUM;
- R3_HEAVY.

R4_LOCAL_AI is deferred to **Phase 10**.

Every executable gate is admitted by the existing Resource Admission Controller.

Resource pressure produces WAITING_RESOURCE, not a fake failure and not resource-policy bypass.

## 10. Executor safety

For proposed capability manifests:
- MODEL cannot hold consequential mutation authority;
- local executable executor kinds must carry a pinned version and SHA-256;
- requires_admin cannot be classified below P3;
- P2/P3 capability requires explicit rollback;
- free-form input fields capable of smuggling `command`, `argv`, `shell` or equivalent execution mechanics are rejected.

The Factory module itself contains no subprocess/provider/network execution path.

## 11. Canary and registration

Canary proof scope is explicit:
- REPOSITORY;
- SIMULATION;
- PROVIDER;
- FIELD.

Registration is immutable for:
`capability_id + provider_id + version`.

Conflicting content for an existing identity fails closed.

Registration records:
- final manifest;
- source provenance;
- license state;
- all required gate receipt IDs;
- source revision;
- derived trust class.

Registration means **the capability is admitted to the registry**. It does not mean an arbitrary mission may execute it.

Execution still requires:
1. project scope;
2. active Capability Grant / policy admission;
3. resource admission;
4. provider availability;
5. normal Action Receipt/evidence/readback.

## 12. HTTP boundary

Microkernel exposes authenticated read-only inspection:
- `GET /v2/capability-factory?project=...`;
- `GET /v2/capabilities`.

It deliberately does **not** expose network POST endpoints to:
- create candidates;
- record gates;
- register capabilities;
- submit manifests;
- execute providers.

Mutation remains internal to the typed mission/capability plane.

## 13. Verification

Repository gate covers:
- schema parsing and contract convergence;
- exact R3 gate sequence;
- T3/T4 candidate trust law;
- T1/T2 promoted trust law;
- P4/R4 exclusion;
- effect/permission semantic matching;
- rollback/admin/executor pinning;
- source-revision and gate-idempotency binding;
- evidence completeness;
- license/trust quarantine and approval holds;
- resource pressure;
- FIELD canary enforcement;
- immutable registration;
- no direct shell/network/provider execution;
- read-only microkernel boundary;
- Phase 6 and Phase 5 regression.

Repository/CI PASS remains distinct from Windows/provider FIELD PASS.

## 14. Next canonical phase

After Phase 7 PASS:

**Phase 8 — Cross-project adapters**
- TLIB;
- Excellentia;
- Delivery;
- BuildHub;
- PC Command;
- PhoneMouse/P2PCR95;
- additional registered projects.

The parked Memory Fabric branch remains future ContextController work and does not reorder the canonical R3 construction sequence.
