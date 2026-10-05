# BCP Execution Fabric — Existing-vs-Gap Map R1

Status: SEALED_PRECONCEPTION_R1 SUPPORTING AUDIT
Date: 2026-10-05

## Already implemented or materially present in BCP

### Windows BCP runtime
Observed in `windows/bcp_server.py` and related contracts:
- SQLite-backed `jobs`;
- `job_dependencies`;
- `mission_events`;
- `memory_records`;
- orchestrator status endpoint;
- `READY/BLOCKED/WAITING_FOR_PC` job semantics;
- mission resume request persistence;
- PC resource snapshot including memory load and available memory;
- ChatGPT/flow receipt bridge components;
- Telegram observability integration;
- update/recovery infrastructure.

### B-EDGE
Observed in Room/Android sources:
- `edge_projects` project registry;
- durable edge jobs;
- dependencies;
- receipts with idempotency;
- events/Chronicle;
- mission steps;
- memory;
- memory claims/provenance;
- capability registry with TTL;
- node/resource governance;
- local executor and store-and-forward contracts.

### Shared BCP design already canonical
- durable missions;
- idempotency/fencing;
- receipts/readback;
- Error Ledger / validated recipes;
- Context Pack;
- Model Broker strategy;
- Resource Governor;
- B-EDGE/PC/Nexus three-node model;
- Telegram cockpit;
- offline/recovery semantics.

## Gaps to implement or prove

### G1 — General Windows Project Registry
No equivalent durable Windows `projects` table was confirmed during this audit.
Need:
- project roots;
- repo/Drive bindings;
- aliases;
- adapters;
- permission/resource/update profiles.

Do not create a competing registry if B-EDGE remains coordinator; define one provider-neutral schema and project it to Windows.

### G2 — Windows receipt/evidence normalization
B-EDGE has explicit receipt entities.
Windows job schema has evidence contract fields, but a general durable action-receipt store was not confirmed.

Need one provider-neutral receipt contract shared across PC/B-EDGE/BuildHub/Delivery.

### G3 — Typed Capability Bus
Current code has endpoints and operations, but a unified capability namespace for all projects is not yet proven.

Need:
`provider + capability_id + input_schema + effect_class + permission_class + resource_class + evidence_contract`.

### G4 — Desktop Commander adapter
Current Commander recovery exists outside BCP as launcher/install artifacts.

Need migration to a BCP capability:
`desktop_commander.remote.ensure_available`.

### G5 — Process containment
No field-proven common Windows Job Object wrapper was confirmed.

Need:
- launch process suspended where appropriate;
- assign to job;
- set limits;
- resume;
- whole-tree accounting/termination;
- adapter exceptions explicitly tested.

### G6 — Privileged capability plane
No final least-privilege typed privileged broker/capsule architecture was confirmed as implemented.

Need:
- explicit local IPC ACL;
- no free-form shell;
- P0-P4 action classes;
- LocalService when sufficient;
- narrowly elevated operations only where required.

### G7 — Startup consolidation
Desktop Commander artifacts currently demonstrate overlapping startup/recovery mechanisms.
Need migration to:
- one primary trigger;
- one bounded fallback;
- stale-health watchdog only.

### G8 — Direct ChatGPT mission ingress
A BCP code/phrase is not itself transport.
Current viable adapters are conditional:
- Desktop Commander when online;
- Drive connected-store/store-forward;
- Telegram/BCP;
- Nexus when field-live;
- future direct MCP/plugin connector when qualified.

Need a transport-independent mission ingress adapter API.

### G9 — Nexus field status
Repository state still records Nexus provider authorization/field gating.
Do not treat Nexus as guaranteed normal path until readback proves it live.

### G10 — Local AI
Still optional/design/qualification-only.
Do not download models in Phase 0.

### G11 — Cross-project migration
TLIB, Excellentia, BuildHub, Delivery, PC Command and current software projects still contain project-local recovery/update/queue behavior.

Need compatibility adapters and gradual retirement, never flag-day rewrite.

## Anti-rewrite conclusion

The Execution Fabric implementation is primarily:
1. schema/contract convergence;
2. project adapter integration;
3. Windows capability hardening;
4. transport unification;
5. evidence normalization;
6. removal of duplicate background machinery.

It is **not** a greenfield orchestration platform.
