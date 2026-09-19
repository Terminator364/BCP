# API / BCP — Session Survival Invariants

Status: CANONICAL / MUST LOAD ON EVERY RECOVERY
Adopted: 2026-09-19

## Core invariant

No ChatGPT conversation, including the current API conversation, may be the sole authority for project state, intent, scope, next action, evidence, or recovery.

Assume any conversation can:
- hit context/message limits;
- be interrupted;
- enter an additional-verification hold;
- be stopped by the user;
- lose tool continuity;
- become unavailable later.

Therefore API/BCP MUST keep durable external state sufficient for a fresh conversation to continue without reconstructing the project from chat history.

## Durable state required

At minimum preserve outside chat:
- project mission;
- legitimate technical scope;
- current architecture/invariants;
- last committed atomic action;
- next uncommitted atomic action;
- current field gate/blocker;
- running/queued job IDs and state;
- receipts, hashes, readbacks and evidence;
- writer lease/fencing state;
- platform interruption classification;
- recovery instructions;
- user-friction requirements that motivated the architecture.

## Recovery behavior

A fresh conversation must load durable state first. It must not ask the user to re-explain already-persisted context unless evidence is missing or contradictory.

Universal cold bootstrap: `BCPGO`.
API/BCP scoped recovery alias: `APIAX07`.
Same-conversation post-interruption continuation: `CONTINUE ATOMIC`.
Future dual-conversation takeover command: `TAKEOVER SAFE`.

## Conversation-loss acceptance test

This invariant is not FIELD_VERIFIED until a fresh conversation can recover the exact project state and next action using durable project artifacts only, with no screenshot or manual reconstruction by the user.


## Context Fabric survival rule

A fresh conversation should not reconstruct state by reading all project history.

Preferred recovery path:
`BCPGO -> bootstrap manifest -> GLOBAL_CORE -> PROJECT_CORE -> TASK_DELTA`.

Subsequent turns use revision-aware `UNCHANGED/DELTA` refresh rather than full memory replay.

The bootstrap code is not an authentication token. An authorized connected BCP/Drive/app path must exist.

Canonical design: `docs/BCP_CONTEXT_FABRIC_THREE_NODE_ARCHITECTURE.md`.
