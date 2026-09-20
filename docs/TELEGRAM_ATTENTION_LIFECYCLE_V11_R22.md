# Telegram Attention Lifecycle V11 — R22

Status: IMPLEMENTED CANDIDATE / FIELD UNVERIFIED
Date: 2026-09-20

## Goal

V11 reduces interruption noise without reducing observability. It builds on Rich Cockpit V10 and keeps the V9 plain-text fallback.

The human question becomes:
1. Is this new?
2. Have I already seen it?
3. Does it truly need me?
4. Is it stable enough to call recovered?
5. Is the system monitoring even when it does not notify me?

## 1. Acknowledgement

The cockpit exposes **✅ J’ai vu**.

Acknowledgement means only:
- the user has seen the current attention signal/root cause;
- the exact unchanged signal should not interrupt again.

It does **not** mean:
- the incident is fixed;
- the mission is complete;
- automatic recovery stops;
- a new/worsened signal is hidden.

The acknowledgement belongs to the current incident episode. After stable observable recovery it is cleared, so a later recurrence of the same root cause is treated as a new incident and may notify again.

The acknowledgement key is derived from attention severity plus the observable root reason.

## 2. Anti-flapping

CRITICAL and genuine ACTION REQUISE transitions are immediate.

A recovery notification is sent only after the recovered state is observed twice or remains stable for at least 60 seconds. This prevents rapid degraded/recovered oscillations from producing chat noise.

WATCH remains visible in the live card and Radar and is not treated as a page-like alert while safe automation is available.

## 3. Routine notification budget

Default policy:
- rolling window: 30 minutes;
- routine interruption budget: 3;
- CRITICAL and genuine human-action alerts bypass the routine budget.

Budget exhaustion suppresses delivery only. It never suppresses:
- state evaluation;
- mission watchdogs;
- durable checkpoints;
- automatic recovery;
- Drive/Nexus telemetry;
- the live Telegram card.

A routine notification consumes budget only after a positive delivery receipt. A network failure does not spend the budget and does not mark the alert as delivered. Critical/action-required alerts that fail in transport remain retryable after reconnect.

## 4. Human incident semantics

The interface distinguishes:
- **détecté** — evidence says a condition exists;
- **vu** — the human acknowledged seeing that condition;
- **géré automatiquement** — automation remains responsible;
- **rétabli** — observable evidence proves the condition cleared.

Acknowledgement is never treated as recovery proof.

## 5. Transport parity

DIRECT_TELEGRAM and NEXUS expose the same acknowledgement callback:
- `/ack`
- `bcp:ack`

The rich V10 surface may render the acknowledgement as a styled callback. V9 fallback keeps a normal inline button.

## 6. Reliability principles incorporated

The design follows established operational alerting principles:
- alert only on actionable conditions;
- deduplicate/group repeated events;
- avoid flapping;
- keep critical bypass for genuinely urgent human action;
- preserve monitoring when notifications are muted or budget-limited.

No paid incident-management dependency is introduced.

## 7. Field acceptance

PASS requires:
1. exact-head CI green;
2. V11 resident on the PC;
3. `J’ai vu` callback round-trip observed;
4. same unchanged signal does not re-interrupt after acknowledgement;
5. changed/worsened root cause still notifies;
6. simulated fast recovery oscillation does not emit duplicate recovery notices;
7. stable recovery emits one silent recovery notice;
8. routine notification budget caps noncritical interruption while monitoring continues;
9. CRITICAL/human-action transition bypasses the routine budget;
10. DIRECT_TELEGRAM and NEXUS behavior remains equivalent.

Until these pass, V11 remains FIELD_UNVERIFIED.
