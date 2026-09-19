# API / BCP — Manual Conversation Relay Protocol

Status: TEMPORARY OPERATING PROCEDURE until automated ACTIVE/STANDBY leases are FIELD_VERIFIED
Adopted: 2026-09-19

## Goal

Keep API/BCP work moving when a ChatGPT conversation is interrupted by an additional-verification hold or other nonterminal platform interruption.

## User procedure

1. Work normally in one conversation.
2. If an additional-verification hold appears and the turn is not completing in a useful time, stop that turn.
3. Open a fresh API project conversation.
4. Send exactly: `CONTINUE ATOMIC`.
5. The new conversation must recover the durable checkpoint and execute only the next uncommitted atomic action.
6. If that conversation is also interrupted, repeat the relay in another fresh conversation.

## Critical single-writer rule

Do not keep two conversations actively mutating the project at the same time.

Before the automated writer-lease/fencing implementation is FIELD_VERIFIED:
- stop the blocked turn before starting the next writer conversation;
- the new conversation must read durable state first;
- it must not replay an action already marked COMMITTED/PASS with a receipt;
- if state is ambiguous, it must enter HOLD and verify readback before mutating anything.

## `CONTINUE ATOMIC` semantics

`CONTINUE ATOMIC` means:
- no broad recap;
- no full architecture restart;
- no broad GitHub/Drive/web rescan unless the next action strictly needs it;
- read the last durable checkpoint;
- identify `last_committed_action` and `next_atomic_action`;
- execute at most one atomic mutation or one bounded verification step;
- persist receipt/checkpoint immediately;
- return a compact status.

## Request-context rule

Every resumed technical action should carry the existing truthful scope profile:
- user-owned/authorized target;
- local or controlled environment where applicable;
- concrete engineering objective;
- narrow operation;
- expected evidence/rollback.

This context is for clarity and continuity, not to bypass platform safeguards. There is no guarantee that it will prevent an additional-verification hold.

## Exit condition

Retire this manual relay procedure only after automated dual-conversation ACTIVE/STANDBY lease takeover has passed field testing.
