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

Cold recovery command: `APIAX07`.
Same-conversation post-interruption continuation: `CONTINUE ATOMIC`.
Future dual-conversation takeover command: `TAKEOVER SAFE`.

## Conversation-loss acceptance test

This invariant is not FIELD_VERIFIED until a fresh conversation can recover the exact project state and next action using durable project artifacts only, with no screenshot or manual reconstruction by the user.
