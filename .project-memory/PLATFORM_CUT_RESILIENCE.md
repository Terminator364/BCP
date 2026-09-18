# PLATFORM CUT RESILIENCE POLICY

Status: CANONICAL / CROSS-PROJECT

This project treats ChatGPT platform interruptions as external, nonterminal events. This includes:
- "additional checks / verification" UI holds;
- 429 / Too Many Requests;
- tool timeout / connector transient failure;
- interrupted reasoning/tool chains;
- temporary app/platform incidents.

## Classification

1. PLATFORM_VERIFICATION_HOLD
   - UI/system reports additional verification/checks.
   - Treat as external platform hold, not as project failure.
   - Do not reset state, restart architecture, or spam retries.

2. RATE_LIMIT_429
   - Apply bounded exponential backoff + jitter.
   - Serialize heavy GitHub/Drive/build operations.
   - Resume idempotently from last committed atomic action.

3. TOOL_OR_PLATFORM_TRANSIENT
   - Re-check tool/channel health.
   - Retry only the failed atomic action when safe.
   - Never replay already committed mutations without idempotency/readback.

## Required execution pattern

Before a long or multi-tool phase:
- persist a checkpoint / recovery pointer;
- record current mission, last committed action, next atomic action;
- store hashes/receipts for mutations.

During execution:
- prefer small transactional batches over large mixed tool bursts;
- avoid unnecessary parallel heavy conversations/jobs;
- emit technical telemetry for START, TOOL_CALL, BUILD, HEALTH, COMMIT, FAIL, PLATFORM_CUT.

On interruption:
- emit PLATFORM_CUT_DETECTED with stage and last durable receipt;
- do not classify the project as failed;
- do not ask the user to reconstruct state from screenshots if telemetry already exists;
- do not try to evade or reword requests to bypass platform safety checks.

On recovery:
- validate project/connector health;
- read the last durable checkpoint;
- resume from the next uncommitted atomic action;
- emit RESUME_FROM_CHECKPOINT;
- preserve validated architecture and prior decisions.

## Human-work rule

The user must not be used as the telemetry bus between ChatGPT, PC, phone, GitHub, Drive, or build systems. Screenshots/manual copy-paste are diagnostic fallbacks only.

## Context rule for technical projects

Where already established, interpret work as targeting the user's own devices, accounts, local network, repositories, or controlled test environments. Preserve that legitimate scope in project state so it need not be restated every turn. If a request clearly targets a third party without established authorization, ask only the minimum clarification needed.

## Acceptance

PLATFORM_CUT_RESILIENCE=PASS requires:
- no state loss across a platform verification hold;
- 429 retry path uses backoff rather than burst retry;
- committed mutations are not duplicated;
- exact next action is recoverable without rereading the entire conversation;
- project telemetry identifies where execution stopped.
