# BCP Autonomic R2 — PC Node Baseline
Date: 2026-10-05
Status: PRECONCEPTION / ANTI-REINVENTION

## Decision

The PC execution-node architecture SHALL NOT be redesigned from scratch.

Adopt the existing:
`Terminator364/ChatGPT-PC/chatgpt-pc/rfcs/RFC-0001-LOCAL-FIRST-MICROKERNEL.md`
as the primary vNext PC-node baseline, subject to fresh field benchmarking and contract convergence.

## What RFC-0001 already solves

- resident local microkernel vs lazy worker plane;
- low-RAM design targets (45 MiB GREEN, 36 MiB AMBER, 28 MiB RED/CRITICAL);
- one heavy worker;
- Windows Job Object containment;
- resource-aware worker admission;
- local SQLite first;
- transactional local outbox;
- Drive removed from critical command path;
- generation/manifest/pointer-last replication;
- local-first recovery ladder;
- Project Capsules;
- explicit authority/durability classes;
- offline operation;
- worker supervisor;
- content-addressed immutable artifacts;
- migration without flag-day replacement;
- no Kubernetes/container/paid-cloud requirement.

## What BCP Autonomic R2 adds above RFC-0001

1. Desired State Resources and reconcilers.
2. Capability Factory as product behavior.
3. Zero-Touch Golden Path enforcement.
4. Friction Controller.
5. Cross-project Work Portfolio Controller.
6. Operational Digital Twin/context projection for ChatGPT.
7. Automatic Release Controller across projects/capabilities.
8. Capability Grants / talk-only autonomy UX.
9. Compute Placement across PC/B-EDGE/BuildHub/CI/ChatGPT.
10. BCP three-node coordinator integration and durable mission semantics.

## Node role

Target:
- B-EDGE / BCP coordinator: durable cross-project coordination when field-qualified;
- PC Local-First Microkernel: local execution authority for effects on the PC, durable local outbox and recovery;
- G6 skill/capability plane: lazy executable modules behind the microkernel;
- BCP Desired State / Mission control: decides intended work and policy;
- Drive/Nexus/Telegram/GitHub: transports/providers, never local runtime authority.

## Runtime consolidation

Do not keep both:
- a full resident BCP Windows server;
- and a full resident G6 AgentCore

as independent control planes.

Phase 0 measures both current footprints and responsibilities.

Migration options:
A. BCP Windows ingress/API becomes a thin module of the Local-First Microkernel.
B. Microkernel hosts BCP node adapter and lazy-loads G6 modules.
C. If one current runtime is clearly lighter/more field-proven, retain it as shell and port the other's contracts/providers.

Selection is evidence-driven.

## Legacy worker absorption

MAXV Local Worker patterns and approved runners become worker/capability providers behind the microkernel.

PC Command Windows actions become capability modules/viewer.

Desktop Commander becomes an optional compatibility/break-glass capability.

No additional resident daemon is introduced for those systems.

## Zero-touch architecture stack

```
ChatGPT voice/text
       |
       v
BCP Intent / Mission / Desired State
       |
       v
BCP/B-EDGE Coordinator
       |
       v
PC Local-First Microkernel  (RFC-0001)
       |
       +-- G6 skills lazy
       +-- PC Command capabilities
       +-- BuildHub jobs
       +-- Delivery jobs
       +-- MAXV legacy providers
       +-- UI Automation / Browser providers
       +-- optional Desktop Commander
```

## Field gate

Before implementation:
- prove actual current installed runtime(s);
- benchmark idle RSS/startup/commit/paging;
- inventory duplicate startup hooks;
- identify which RFC-0001 pieces are already implemented in vNext;
- map BCP Windows features to G6 microkernel modules;
- choose one resident PC process target.

No big-bang rewrite or dual-daemon promotion.
