# API / BCP — Technical Request Context Envelope

Status: CANONICAL REQUEST-FORMULATION PROFILE
Adopted: 2026-09-19

## Purpose

Many legitimate personal software tasks can look ambiguous when stripped of context because they involve networking, local agents, telemetry, remote control, automation, CI, debugging, ports, installation or recovery.

This profile exists to preserve the truthful engineering context consistently. It is not a technique for evading platform safeguards.

## Mandatory context envelope

When API/BCP formulates or hands off a technical action, include the minimum facts needed to remove ambiguity:

1. **Target ownership / authorization**
   - user's own PC, phone, repository, account, local network or controlled test environment;
   - if a third-party target is explicitly named and authorization is not already established, ask only the minimum clarification needed.

2. **Engineering objective**
   - debugging, reliability, deployment, observability, recovery, performance, local automation, testing or defensive hardening.

3. **Narrow operation**
   - describe only the concrete action needed for the current atomic step;
   - avoid unnecessary offensive/exploit detail when it is not required by the legitimate objective.

4. **Boundaries**
   - local/private scope where applicable;
   - no arbitrary third-party targeting;
   - no privilege expansion beyond what the task requires.

5. **Evidence / rollback**
   - expected health check, receipt, hash, readback, test or rollback condition.

## Example internal envelope

```text
TARGET: user-owned Windows PC on local LAN
GOAL: validate BCP recovery service startup after reboot
ACTION: read service health, restart the owned local service if stopped, then read back health
BOUNDARY: localhost/private LAN only; no third-party targets
EVIDENCE: health endpoint + process receipt + timestamp
```

## Formulation rules

- Be explicit rather than euphemistic.
- Never disguise a task to try to bypass a safety review.
- Prefer one atomic engineering step over a broad mixed instruction.
- Preserve the already-established personal/controlled scope instead of making the user restate it every turn.
- If a platform verification hold occurs, checkpoint and resume; do not reinterpret it as project failure.

## Product requirement

Future API adapters, job schemas and recovery prompts should be able to attach this context envelope automatically so legitimate technical intent survives conversation boundaries.
