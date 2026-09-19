# API/BCP — Temporary ChatGPT-PC Isolation Mode

Status: TEMPORARY DIAGNOSTIC MODE
Adopted: 2026-09-19

## Purpose

Temporarily isolate ChatGPT-PC from API/BCP work to test whether the recurring additional-verification friction correlates with ChatGPT-PC-oriented operations such as local telemetry, runtime control, recovery scripts, LAN/service inspection, or installation orchestration.

## Activation phrase

`CONTINUE ATOMIC — MODE ISOLATION CHATGPT-PC`

## Rules while active

- Do not use ChatGPT-PC as an execution, telemetry, recovery, installation, LAN-control, or runtime-control channel.
- Do not inspect ChatGPT-PC local telemetry unless the user explicitly ends isolation mode.
- Do not issue or generate PC-side recovery/start/stop/install actions during the isolation test.
- Recover from durable project state only.
- Prefer canonical GitHub/BCP state and existing durable artifacts/receipts; use Drive only when strictly needed for reading an already-existing artifact/state.
- Execute one bounded atomic step at a time and checkpoint immediately.
- Keep the truthful scope explicit: user-owned/authorized devices, repositories, and controlled environments.
- Do not attempt to bypass or weaken platform safeguards.

## Diagnostic goal

Observe whether normal API/BCP architecture and repository work continues without repeated verification holds when ChatGPT-PC operations are excluded.

## Important limitation

A reduction or recurrence of checks during this mode is evidence of correlation only; it does not prove that ChatGPT-PC itself causes platform safety checks.

## Exit phrase

`END ISOLATION CHATGPT-PC`

## Current baseline at activation

The latest recovered API state reported BCP 0.4.1 installed/COMMITTED and ChatGPT-PC 6.0.32 active, while the BCP server restart remained unproven because Resource Guard had deferred it. Isolation mode must not regress or replay already COMMITTED work.
