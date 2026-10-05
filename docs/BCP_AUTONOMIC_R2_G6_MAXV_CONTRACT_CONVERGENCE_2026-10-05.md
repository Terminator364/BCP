# BCP Autonomic R2 — Contract Convergence with G6 / MAXV
Date: 2026-10-05
Status: PRECONCEPTION / ANTI-REINVENTION

## Decision

R2 introduces new product semantics (Desired State, Friction Controller, Capability Factory workflow, Portfolio/Digital Twin), but MUST NOT create a parallel execution/security contract stack where G6 already defines stronger contracts.

## Canonical mapping

| R2 concept | Canonical underlying contract | R2 role |
|---|---|---|
| Mission Envelope V2 | G6 MISSION IR v1 + BCP durable mission/jobs | intake/transport envelope compiled to immutable execution IR |
| Capability Manifest V1 | G6 SKILL MANIFEST v1.1 | lightweight registry/catalog projection; executable workers use Skill Manifest |
| Capability Grant V1 | G6 authority.db v1 / Authority Ladder | UX/policy projection; authority storage stays canonical G6/BCP authority |
| Desired State Resource V1 | **new R2 concept** | persistent desired-vs-actual resource, executes via existing mission/skill/effect contracts |
| Reconcile effect | G6 SIDE-EFFECT JOURNAL v1 | PREPARED -> OBSERVED -> VERIFIED -> COMMITTED |
| Operational Digital Twin | G6 COMPONENT GRAPH + CAPABILITY FINGERPRINT + BCP project registry | reconstructible current-state projection |
| Release Controller | G6 PACKAGE HEAD v2 + package lifecycle + MIGRATION RUN + transition receipts + A/B BOOT RECORD | autonomic orchestrator over existing release contracts |
| Capability Factory | G6 self-extension admission + SKILL MANIFEST + dependency lock + isolation/effect declaration + assurance tests | workflow that creates/promotes new skills |
| Privileged operation | G6 Privileged Broker catalog / IPC SECURITY PROFILE / authority ladder | implementation provider may be JEA or custom broker |
| GUI capability | G6 UI target descriptor + Interaction Bridge + UI transaction contract | provider uses Windows UI Automation where possible |
| Error/recipe handling | G6 ERROR TAXONOMY + BCP ERROR_LEDGER | classification + validated repair recipes |
| Resource placement | G6 Resource Governor + BCP node capabilities | extends to choose PC/B-EDGE/BuildHub/CI/ChatGPT placement |
| Update security | G6 dependency/package/provenance/security floor + R2 TUF/SLSA-inspired policy | no blind latest |
| Recovery | G6 RESTORE CAPSULE + transition receipts + side-effect journal | exact reconcile/resume |
| Local worker | MAXV Local Worker lineage / current BCP Windows worker | reuse/migrate, do not add another daemon |

## New R2 concepts that genuinely add value

### Desired State Controller
G6 is strong on mission/release/effects, but persistent "keep X healthy/current" reconciliation is promoted to a first-class resource in R2.

### Friction Controller
Manual user mechanics become structured automation-debt evidence.

### Work Portfolio Controller
Cross-project backlog/resource priority is explicit.

### Capability Factory workflow
G6 already defines secure self-extension admission contracts; R2 turns those contracts into an end-to-end product behavior from user intent -> missing skill -> qualified skill -> resumed mission.

### Compute Placement Controller
Selects execution node/provider by capability, resource, privacy, network and proof needs.

### Talk-only Intent Plane
ChatGPT natural language is the main product UX; trigger aliases remain continuity tools rather than required syntax.

## MAXV Local Worker absorption

Historical MAXV Local Worker proves reusable patterns:
- supervisor + worker separation;
- STOP flag / controlled recovery;
- startup supervisor;
- approved-script runner;
- arbitrary shell disabled;
- transactional upgrade and rollback;
- exact hash/readback;
- capability probe;
- one-thread / bounded-memory toolchain;
- local heartbeat authority with Drive best-effort mirror.

Do not ship a third independent local worker.

Migration target:
- inventory actual surviving MAXV/ChatGPT-PC/BCP local worker bytes;
- extract reusable adapters/tests;
- map approved scripts to typed capabilities;
- map supervisor recovery to the shared lifecycle controller;
- retire duplicate heartbeat/queue paths after field equivalence is proven.

## MAXV W5 execution-kernel absorption

Historical W5 contributes:
- write-ahead OPEN before material mutation;
- VERIFY/READBACK before COMMIT;
- exact idempotency;
- interrupt/reconcile rather than blind replay;
- fast memoryless resume;
- delta restore instead of full reread;
- module trigger registry;
- cost/information-efficient scheduling;
- error/failure -> generalized sibling regression;
- stop only on explicit/real boundary.

These principles become BCP-wide rather than MAXV-specific.

## No parallel authority rule

If R2 and G6 express the same security/effect fact, G6/BCP canonical contract wins unless a later explicit migration supersedes it.

New R2 JSON schemas remain DESIGN/bridge schemas until:
- mapping tests exist;
- no semantic weakening is proven;
- canonical storage owner is decided;
- migrations are defined.

## Implementation implication

Phase 0 now inventories:
- existing BCP Windows runtime;
- B-EDGE Room state;
- ChatGPT-PC/G6 components;
- MAXV Local Worker remnants;
- PC Command;
- BuildHub;
- Delivery.

Phase 1 is **contract convergence and adapters**, not another engine.
