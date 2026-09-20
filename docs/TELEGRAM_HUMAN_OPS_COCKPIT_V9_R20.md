# Telegram Human Ops Cockpit V9 — R20

Status: IMPLEMENTED CANDIDATE / FIELD UNVERIFIED
Date: 2026-09-20

## Purpose

V9 turns Telegram from a technical status dump into a human operations cockpit for periods where the user is away from the PC, connectivity is intermittent, and several subsystems may be progressing independently.

The primary question is no longer "what internal state string is present?" but:
1. Do I need to act?
2. Is work advancing?
3. What changed since I last looked?
4. Why does BCP say this?
5. What is likely to become the next problem?
6. Which statements are proof and which are forecast?

## Design principles

### Orientation before detail

The live card starts with one human attention state:
- 🔴 CRITIQUE
- 🟣 ACTION REQUISE
- 🟠 À SURVEILLER
- 🟢 EN COURS
- 🔵 STABLE

Only after that headline does it show objective, approximate progress, current micro-action, last proof and subsystem detail.

### Forecast must carry confidence

The existing ≈ micro-action progress remains explicitly approximate. V9 also displays confidence:
- ÉLEVÉE: durable plan plus multiple independent proofs;
- MOYENNE: partial decomposition/evidence;
- FAIBLE: sparse structured evidence.

A forecast is never promoted to proof.

### "Since I last looked"

The cockpit persists the latest human interaction time. The **Depuis ma visite** view summarizes new durable mission events since that point, groups older overflow, and finishes with the current attention state and next step.

This is designed for returning after minutes or hours away without reading the whole chat.

### Explainability

The **Pourquoi ?** view exposes the observable reasons behind the headline:
- human gate;
- stale progress;
- PC heartbeat age;
- Nexus state;
- direct Telegram degradation;
- power/memory pressure;
- holds.

It does not expose hidden model reasoning or chain-of-thought.

### Predictive risk radar

The **Radar** is explicitly predictive rather than evidentiary. It surfaces near-term operational risks derived from observable signals, for example:
- Nexus not yet field-live while direct Telegram is degraded;
- PC RAM above safe margin;
- battery risk;
- B-EDGE sentinel unavailable/stale;
- failing/in-progress CI;
- stale mission evidence.

Risk levels are ÉLEVÉ / MOYEN / FAIBLE and must never be confused with an active incident.

## Notification policy

### Transition-based, not heartbeat-based

A persistent condition does not generate a new alert at every heartbeat. V9 stores the last attention fingerprint and notifies only when the meaningful state/root reason changes.

### Recovery notification

If a prior CRITIQUE / ACTION REQUISE / À SURVEILLER state clears, V9 sends one **SITUATION RÉTABLIE** notification.

### Quiet mode

The user can enable a bounded **Mode discret**. Routine notifications are suppressed while evaluation continues. Critical alerts and genuine human-action gates bypass quiet mode.

Quiet mode therefore behaves like notification muting, not monitoring disablement.

### Grouping and deduplication

Mission events remain grouped into bounded batches. Idempotency/cursor semantics remain authoritative. A notification transition is keyed so repeating the same root state does not spam the user.

## Telegram controls

Primary orientation:
- 🟢 Situation
- 🕘 Depuis ma visite
- ❓ Pourquoi ?
- 🔭 Radar
- 📍 Étape actuelle
- ⚙️ Activité fine
- 🎯 Objectif
- ▶️ Continuer

Notification controls:
- 🔕 Discret 2h
- 🔔 Normal

Depth:
- 🧰 Technique
- 📄 Suivi
- 🖥️ Appareils
- 🧭 Mission
- 📚 Audit

The four PDF reports remain available and are not replaced by the compact cockpit.

## Optional Cockpit+ Mini App

A future optional Telegram Mini App may provide:
- richer timeline;
- expandable evidence cards;
- multi-mission navigation;
- charts for health/progress history;
- alert history and acknowledgement;
- offline local presentation cache.

It is an enhancement, never a critical dependency. The plain bot card and commands remain the mandatory low-data fallback.

Mini App requirements:
- mobile-first;
- minimal JavaScript and assets;
- adapt effects/animations to Telegram device performance class;
- validate Telegram init data server-side;
- no paid dependency by default;
- no secret embedded in client assets;
- no loss of functionality when the Mini App is unavailable;
- use secure/local storage only for noncanonical UI preferences or appropriately protected client state.

## Offline-first requirements

Notification preferences, last-seen timestamp, alert fingerprints and mission evidence remain durable locally.

Losing Internet:
- does not clear state;
- does not reset progress;
- does not convert missing delivery into fake success;
- resumes synchronization when connectivity returns.

The existing WorkManager/B-EDGE and BCP/Nexus retry architecture remains the source of execution continuity; Telegram is the human surface, not canonical state.

## Field acceptance for V9

PASS requires:
1. exact-head CI green;
2. resident Telegram companion auto-updates to V9;
3. live card shows one of the five human attention states;
4. Since/Why/Radar callbacks round-trip;
5. quiet mode suppresses routine notices but not a simulated critical/human gate;
6. repeated unchanged alert does not spam;
7. recovery transition sends exactly one recovery notice;
8. direct Telegram and Nexus modes both pass the same behavioral self-tests;
9. no duplicate poller regression;
10. no secret appears in card, report, log or persisted UX state.

Until these pass, V9 remains FIELD_UNVERIFIED.
