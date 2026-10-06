# BCP Cross-Project Adapters — R3 Phase 8

Date: 2026-10-06  
Status: IMPLEMENTATION_CANDIDATE / REPOSITORY-GATED / NOT FIELD CERTIFIED

## 1. Objective

Phase 8 turns the Phase 3 project-adapter contract into a durable, provider-neutral
cross-project registry and enrolls the first seven project families named by the Phase 7
Capability Factory exit plan:

- TLIB;
- Excellentia;
- ChatGPT Delivery;
- BuildHub;
- PC COMMAND;
- PhoneMouse;
- P2PCR95.

MED-REBUILD remains the earlier vertical evidence client and is not the center of Phase 8.

## 2. Reuse, not reinvention

Phase 8 reuses:
- Phase 2 `CriticalStore`;
- Phase 3 `ProjectRegistry` and `bcp.project_adapter/1`;
- Phase 7 `CapabilityRegistry/CapabilityFactory`;
- the existing repository/project release evidence for each enrolled project.

No new scheduler, updater, mission kernel, Resource Governor or shell executor is created.

## 3. Durable Project Adapter Registry

Module:
`windows/execution_fabric/project_adapter_registry.py`

Namespace:
`project-adapter/<project_id>/<sha256(adapter_id + version)>`

Properties:
- immutable adapter id/version records;
- same CriticalStore fencing, revision/hash/outbox semantics as the rest of BCP;
- one typed binding per operation within an adapter;
- fail-closed ambiguity when multiple BOUND adapters claim the same project operation;
- no execution behavior.

## 4. Binding law

A `BOUND` GitHub binding is accepted only when the corresponding ProjectRecord contains
that exact repository as a BOUND repo origin.

A `BOUND` PC-native binding is accepted only when the ProjectRecord contains an observed
BOUND local root.

Therefore:
- repository evidence cannot promote a PC/runtime operation;
- an audit document cannot become a source-code binding;
- conversation/memory cannot become engineering authority;
- missing project entrypoints remain `WAITING_BINDING`.

## 5. Initial catalog

Runtime catalog:
`windows/execution_fabric/catalogs/phase8_cross_project.json`

### TLIB

Historical audit evidence records a deployed TLIB build/runtime, but no canonical TLIB
source root is observed on current `ChatGPT-PC/main`.

Result:
- engineering authority: UNRESOLVED;
- repo origin: UNRESOLVED;
- all adapter operations: WAITING_BINDING.

This is intentional anti-invention behavior.

### Excellentia

Observed:
- repo: `Terminator364/ChatGPT-PC`;
- path: `excellentia-study-cockpit`;
- stable manifest: `excellentia-study-cockpit/release/current.json`;
- manifest app version: 2.3.0;
- manifest source commit: `73f6bc1f841643b5dda94f1c6fd81d56b65780bc`.

Result:
- INSPECT: BOUND / repository;
- RELEASE_VERIFY: BOUND / exact manifest;
- test/runtime/update/rollback: WAITING_BINDING until their typed capability and/or field
  roots are admitted.

### ChatGPT Delivery

Observed:
- repo: `Terminator364/ChatGPT-PC`;
- path: `chatgpt-delivery`;
- project state explicitly defines a multi-provider canonical truth order involving stable
  manifest, update feedback, Delivery health and ACTIVE_VERSION.

Result:
- repository INSPECT: BOUND;
- release verification is intentionally WAITING_BINDING to provider `DELIVERY`;
- repo-only evidence is not allowed to impersonate Drive/live Delivery truth.

### BuildHub

Observed repo/head:
`Terminator364/BuildHub@18ac5c048acfa6f190713239cd1611952d9ca24c`.

Result:
- repository INSPECT: BOUND;
- live BuildHub execution/release operations remain WAITING_BINDING until a typed provider
  binding is admitted.

### PC COMMAND

Observed:
`Terminator364/PC-COMMAND-STATE@f10913f1fecc678a1c6ccc31758eb753cdb20924`.

This repository is a private runtime state bus, not asserted as engineering source.

Result:
- engineering authority stays UNRESOLVED;
- state repository is COMPATIBILITY authority;
- repository INSPECT can be BOUND;
- execution/update operations remain field-gated.

### PhoneMouse / P2PCR95

Observed repositories:
- `Terminator364/PhoneMouse@397ad5e1aac7d1b5ef53a6dec52655e907a80d44`;
- `Terminator364/P2PCR95@64c4539288404602fb8aedc9fdf8fa314a9a482d`.

Repository INSPECT is BOUND. Local/control operations remain WAITING_BINDING.

## 6. Capability Factory relationship

A Project Adapter is not a capability implementation.

It says:
`project operation -> typed capability_id + provider + policy/evidence envelope`.

When the capability does not exist or is not sufficiently trusted, Phase 7 Capability
Factory remains responsible for reuse search, qualification, canary and registration.

Phase 8 never auto-creates executable command strings.

## 7. Read-only microkernel views

Added:
- `GET /v2/project-adapters?project=<id>`;
- `GET /v2/project-adapters/resolve?project=<id>&operation=<op>`.

`include_waiting=true` may inspect an unresolved mapping, but cannot convert its state to
BOUND.

No Phase 8 POST endpoint exists.

## 8. Acceptance

Repository PASS requires:
1. catalog schema parses;
2. all 7 ProjectRecords validate;
3. all 7 ProjectAdapters validate;
4. catalog seeds into one shared CriticalStore;
5. exact Excellentia release binding resolves;
6. TLIB BOUND resolution fails closed;
7. native-PC BOUND operations fail without a real local root;
8. repo mismatch is rejected;
9. immutable adapter collision is rejected;
10. ambiguous BOUND resolution fails closed;
11. no P4/R4 auto bindings;
12. no command/argv/shell mechanics;
13. Phase 7 and Project Registry regressions remain green;
14. no field certification claim.

## 9. Next atomic work unit

After Phase 8 repository PASS:
- persist the updated BCP construction ledger;
- prepare **one batched field-binding campaign** for unresolved local roots/runtime
  operations across projects;
- use PC/last-mile evidence only where a repository proof cannot resolve a binding;
- do not invent a new numeric BCP phase until the canonical construction plan is updated.

The existing B-EDGE V2 "Phase 9" is a separate plan and is not renamed or reused here.
