# API/BCP — Temporary ChatGPT-PC Isolation Mode

Status: TEMPORARY DIAGNOSTIC MODE
Adopted: 2026-09-19

## Purpose

Temporarily isolate ChatGPT-PC from API/BCP work to test whether the recurring additional-verification friction correlates with ChatGPT-PC-oriented operations such as local telemetry, runtime control, recovery scripts, LAN/service inspection, or installation orchestration.

## Activation phrase

`CONTINUE ATOMIC — MODE ISOLATION CHATGPT-PC`

## Rules while active

- Do not use ChatGPT-PC itself as the execution/control/recovery/install/LAN-control channel during this diagnostic window.
- Telemetry remains a P0 requirement. Do NOT disable observability. Prefer telemetry already externalized to BCP/GitHub/Drive/receipts or a BCP-native lightweight telemetry path that does not require ChatGPT-PC as the interactive bridge.
- Do not make the user copy/paste telemetry, commands, IPs, tokens, logs, or prompts between devices. The system must recover/read the durable evidence automatically when the connected source is available.
- Direct inspection of ChatGPT-PC-local telemetry is temporarily excluded only to isolate that channel as a variable; this is not a permanent product design.
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

## Automatic activation

The current project may enter this mode from durable state without requiring the user to copy/paste the activation phrase. The phrase exists only as a recovery alias.

While active, `CONTINUE ATOMIC` alone is sufficient: recover this mode from project memory and continue with the next bounded action.
