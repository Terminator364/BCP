# API / BCP — Legitimate Technical Scope Profile

This profile exists to make the project’s real operating context explicit and durable. It is **not** a bypass mechanism for platform safeguards.

## Default scope

API/BCP is a personal software-development and continuity/control project. Unless a task explicitly says otherwise, its normal targets are the user's own Windows PC, Android phones, repositories, local network, local services, CI/build pipelines, project storage and applications built by the user.

Typical goals are defensive engineering, debugging, reliability, deployment, observability, recovery, performance, low-RAM hardening, offline-first behavior and safe automation.

## Request-shaping rule

When a technical action could look ambiguous in isolation, preserve the minimum context that disambiguates it:
- owned/authorized target;
- local or controlled environment;
- concrete engineering objective;
- minimum necessary operation;
- expected evidence/receipt/rollback.

Do **not** add exploit detail that is unnecessary to the defensive engineering objective. Do **not** euphemize or disguise the task to evade a safety check.

## Platform interruptions

A ChatGPT additional-verification notice is an external, nonterminal platform event. It must not erase or invalidate project state.

- checkpoint before long/multi-tool work;
- use small transactional batches;
- resume from the next uncommitted atomic action;
- use exponential backoff for 429;
- retry only the failed atomic action for transient connector/tool errors;
- prefer machine-readable telemetry and receipts over screenshots/manual copy-paste.

## Two-conversation resilience

BCP may support an ACTIVE conversation and a STANDBY conversation sharing the same canonical project state. Only one writer lease may mutate external state at a time. If ACTIVE is interrupted, STANDBY may continue from the durable checkpoint once it owns the lease. When ACTIVE later returns, it must reconcile and become observer or reacquire a fresh lease before writing.

## Boundaries

This profile does not authorize work against third-party systems. If a task clearly names a third-party target and authorization is not established, ask only for the minimum clarification needed.

The objective is continuity and clarity, not bypassing OpenAI safeguards.
