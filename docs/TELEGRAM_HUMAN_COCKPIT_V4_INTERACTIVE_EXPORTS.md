# BCP — Telegram Human Cockpit V4: interactive controls, progressive disclosure and portable reports

Status: ACTIVE PRODUCT REQUIREMENT DELTA / IMPLEMENTATION CANDIDATE
Adopted: 2026-09-19
Evolution rule: SPEC_REFRESH_CURRENT_THEN_MERGE_REFINE_PRESERVE
Builds on: `docs/TELEGRAM_HUMAN_COCKPIT_V3_AND_MULTI_MISSION_REQUIREMENTS.md`

## Purpose

V4 makes the Telegram cockpit understandable and useful without requiring the user to behave like an operator.

The default surface is a medium-length live mission card with a small set of obvious buttons. Technical identifiers, raw receipts and long evidence remain available on demand. The same durable state can also be exported as a compact human PDF or a deeper technical PDF.

V4 does not expose hidden ChatGPT reasoning. It reports only durable BCP mission events, receipts, node presence, CI/build evidence, checkpoints and externally observable chat states.

## UX principles

The cockpit follows four hard principles:

1. **Visibility of system status** — the user should always be able to tell whether a mission is working, waiting, blocked, done, or lacking fresh evidence.
2. **Progressive disclosure** — normal view first; technical evidence only behind an explicit control.
3. **Determinate progress only when true** — percentage/bar only when an explicit persisted finite denominator exists. Otherwise show the current step, last completed step and next expected step.
4. **Immediate interaction acknowledgement** — button taps are acknowledged immediately before any slower refresh/export work.

These principles are product constraints, not decorative preferences.

## Default live card

The normal mission card SHOULD look structurally like:

```
🤖 BCP — <mission name>
🟢 EN COURS

📊 [██████░░░░] 6/10 — 60%      # only when denominator is real
🎯 Maintenant: <plain-language current step>
✅ Dernière étape: <last committed step>
➡️ Ensuite: <next safe step>
👤 Action pour vous: AUCUNE | REQUISE | OPTIONNELLE

🕒 Dernière preuve: <timestamp / age>
🖥 PC <state> · 📱 B-EDGE <state> · 🌐 Nexus <state>
🧪 Tests <state>
```

If no trustworthy denominator exists, the progress line becomes a phase/state description and MUST NOT invent a percentage.

The card is edited in place for routine changes. New Telegram messages are reserved for meaningful transitions: human gate, HOLD/BLOCKED, recovery, milestone, mission completion or material degradation.

## Interactive button contract

The default card exposes a stable compact keyboard:

- **🔄 Actualiser** — refresh the current evidence-based card.
- **📍 Où ?** — show the exact current durable step.
- **🗂 Missions** — show recent/active missions.
- **🧾 Détails** — show the technical evidence view.
- **📄 PDF suivi** — download a compact human-readable status report.
- **📚 PDF technique** — download a deeper diagnostics/evidence report.

Buttons remain read-only in V4. No mutating/destructive command is introduced by this UX layer.

Typed fallbacks remain available:
- `/status`
- `/where`
- `/missions`
- `/details`
- `/report`
- `/reporttech`

## Portable report contract

### Human PDF

The human PDF contains:
- generation timestamp;
- current mission state;
- current/last/next step;
- truthful progress if finite;
- explicit human action;
- node/connectivity summary;
- last proof age;
- important test/hold state.

It omits raw secrets and routine engineering noise.

### Technical PDF

The technical PDF contains:
- the technical `/details` view;
- recent durable micro-actions;
- recent mission summary;
- relevant receipts/evidence references already exposed by the safe diagnostics layer;
- generation timestamp.

The report is a snapshot, never canonical state.

### Low-data constraints

- reports are plain compact PDFs using no heavy rendering stack;
- image assets are not required for report generation;
- reports are generated only on explicit request or a meaningful milestone, never every heartbeat;
- report generation must not trigger a large artifact download on mobile data;
- unchanged cached report content should be reused when the source evidence is unchanged;
- bot token, device secret and other credentials are never embedded.

## Nexus behavior

Direct PC -> Telegram is not a required path.

When Nexus is active:
- PC/B-EDGE publishes a sanitized summary and technical report snapshot to the authenticated Nexus device endpoint;
- Nexus stores only the report text required for export plus timestamps/hashes;
- Telegram button presses are acknowledged at the webhook edge;
- simple button commands are queued to BCP through the existing durable command path;
- PDF buttons can be served from the latest cached report even if the PC is temporarily unreachable;
- all callback handling remains restricted to the allowlisted private chat.

The cached Nexus report is advisory presentation state; canonical project state stays in BCP durable state.

## Visual hierarchy and language

The normal view:
- uses plain French labels;
- keeps a stable field order;
- uses a small set of semantic icons;
- avoids PR/SHA/branch/run IDs unless the user opens **Détails**;
- avoids repeating `Spend: $0.00` in normal status;
- uses medium-length text so that useful context is visible without becoming a raw log dump;
- distinguishes “no fresh evidence” from “blocked”.

The technical view may be denser.

## Optional image card

A visual image card remains an optional later layer, not a dependency of V4.

It may be added only if:
- it materially improves comprehension over the text card;
- it is generated from the same durable truth;
- it is cached;
- size is aggressively bounded;
- it is requested explicitly or emitted at a milestone rather than every heartbeat.

Until qualified, the text live card plus PDF exports is the authoritative human interface.

## Accessibility and interaction

- button labels are explicit verbs/nouns rather than ambiguous symbols alone;
- button order remains stable;
- a button tap receives immediate acknowledgement;
- critical state changes are also represented in text, not color alone;
- timestamps/age make stale information obvious;
- the same information remains available through typed commands when inline controls are unavailable.

## Failure behavior

If Telegram/Nexus is slow or unavailable:
- local mission journaling continues;
- no committed step is replayed;
- outgoing status/report work remains bounded and retryable;
- the user is shown the last confirmed evidence, not fabricated current activity;
- PDF/report failure does not block project execution;
- the cockpit can recover from stale message IDs by sending a fresh live card.

If the report cache has no source evidence yet, the PDF control returns a short “report not yet available” state instead of fabricating content.

## Update behavior

V4 is delivered through the existing qualified update plane:
- hash-pinned release metadata;
- atomic replacement;
- self-test;
- rollback on launch failure;
- preservation of local Telegram secret and approved chat;
- no repeated token entry;
- no ChatGPT scheduled automation;
- no manual file shuffling as normal operation.

## Acceptance tests

V4 is not FIELD_VERIFIED until applicable tests pass:

1. direct Telegram card renders all six buttons;
2. each button is accepted only from the approved private chat;
3. callback acknowledgement is issued before slower processing;
4. status/where/missions/details buttons return the expected read-only view;
5. PDF suivi downloads a valid PDF;
6. PDF technique downloads a valid PDF;
7. exported PDFs contain no token/secret;
8. PDF generation succeeds without third-party Python packages;
9. one live mission card is edited in place rather than duplicated for normal updates;
10. unchanged live-card/report state is deduplicated;
11. finite n/N renders a truthful percentage; open-ended work does not;
12. stale evidence is explicitly labelled;
13. Nexus stores/reuses latest report snapshot and can serve a PDF while PC direct Telegram egress is degraded;
14. Nexus callback path is idempotent and allowlisted;
15. D1 migration preserves existing command/reply/outbound/live-card state;
16. direct Telegram and Nexus expose equivalent button semantics;
17. Telegram/Nexus loss does not stop local mission execution;
18. report export remains below configured low-data size bounds for normal mission snapshots;
19. CI validates Python syntax/self-test on Windows and Linux plus Worker syntax/D1 schema;
20. no ChatGPT scheduled automation is created or required.

## Research rationale

The design is aligned with established usability guidance: keep system status visible, use determinate indicators only when meaningful progress can be measured, otherwise communicate current/remaining work, and hide secondary technical complexity behind progressive disclosure. Telegram's Bot API supports inline callback buttons, callback acknowledgements, editable messages and document delivery, which allows this interaction model without adding a heavy UI framework.

