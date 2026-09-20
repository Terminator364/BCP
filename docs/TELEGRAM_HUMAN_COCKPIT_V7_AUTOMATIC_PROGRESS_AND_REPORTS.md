# Telegram Human Cockpit V7 — Automatic Progress, Fine Micro-actions and Complete Reports

Status: R15 IMPLEMENTED CANDIDATE / FIELD UNVERIFIED
Date: 2026-09-20

## 1. Human objective

Telegram is the user's low-friction operational window into BCP. The primary card must answer, in human language:

1. What are we trying to achieve now?
2. Is work active, paused, waiting, blocked, or disconnected?
3. Approximately how far through the current request are we?
4. What fine-grained action is happening now?
5. What was last confirmed?
6. What happens next?
7. Are the PC, old-phone B-EDGE server, Drive, Nexus and qualification pipeline healthy?
8. Does the user need to do anything?

The card title is **Automate de suivi BCP**, not an internal component dump.

## 2. Two different percentages

### 2.1 Mission progress estimate

A fine micro-action is an atomic observable operation, for example:
- open/read a file or PDF;
- inspect one workflow;
- read one log/result;
- change one file;
- compute/check one hash;
- launch one test;
- check one test result;
- create one commit;
- perform one readback;
- validate one receipt.

The exact future count is usually unknowable. BCP therefore produces a deterministic **forecast**, explicitly marked with the approximation symbol `≈`.

Example:
`██████░░░░░░ ≈49% · ≈31/63 micro-actions`

The forecast may grow or shrink as the task is decomposed. This is not fabricated proof. Confirmed micro-actions remain evidence-backed.

### 2.2 Ecosystem health

A separate percentage summarizes currently observable availability/qualification of PC/BCP, B-EDGE, Drive, GitHub CI and Nexus. It is not mission progress.

## 3. Execution interpretation

The live card translates evidence into states:
- recent durable evidence -> active;
- CI still running -> remote work active;
- known platform hold -> interrupted but resumable;
- no evidence for a bounded interval -> apparent pause, not invented work;
- transport loss -> local state remains durable and sync resumes on reconnection.

The system never claims access to private model chain-of-thought.

## 4. Device semantics

PC status is phrased as human state: alive, telemetry delayed, or not recently reachable.

B-EDGE is a resident old-phone server. If paired but no fresh phone event is required, the normal human state is **paired / standby**, not an alarming "missing proof" message.

Nexus is presented as a staged remote-relay preparation with an explicitly approximate percentage and an explanation of the current stage.

Raw codes remain available in technical reports.

## 5. Automatic refresh

The manual Refresh button is secondary.

The card automatically refreshes through the active transport:
- active/nonterminal mission: target interval about 60 seconds;
- completed/idle mission: target interval about 300 seconds;
- state changes may trigger immediate refresh;
- direct Telegram and Nexus both use the same card fingerprint semantics;
- when offline, state is kept locally; transport retries are bounded; synchronization resumes after reconnect;
- refresh remains data-aware and avoids large downloads.

A refresh time bucket is included in the card fingerprint so an unchanged-but-alive card can still visibly update at the bounded interval.

## 6. Buttons

Primary controls:
- 🟢 Situation
- 🔵 Où en est-on ?
- ⚙️ Activité fine
- 🎯 Objectif
- 🧰 Technique

Report controls:
- 📄 1·Suivi
- 🖥️ 2·Appareils
- 🧭 3·Mission
- 📚 4·Audit

Telegram does not guarantee arbitrary button colours, so stable coloured symbols are used instead of pretending to control client theme colours.

## 7. Fine activity view

The Activity view contains:
- current forecast counter;
- recently confirmed micro-actions;
- a short predicted window of upcoming micro-actions, each marked `≈`;
- explicit warning that forecast numbering may be recalculated.

This provides the requested "4/64, 5/64, 6/64..." style experience without misrepresenting estimates as proofs.

## 8. Objective view

The Objective button displays:
- current human objective;
- estimated progress;
- current step;
- next step;
- persisted plan when available.

The historic Missions list remains available separately through the command surface and reports.

## 9. Four generated PDF reports

The cockpit generates four complementary reports from current durable evidence:

1. **Situation humaine complète** — executive current state, objective, progress, recent activity.
2. **Appareils, réseau et transports** — PC/BCP, B-EDGE, Drive, direct Telegram, Nexus, connectivity and CI.
3. **Objectif, étapes et micro-actions** — mission metadata, forecast, plan, fine journal, holds.
4. **Dossier technique et audit** — technical state, checkpoint/revision, evidence, CI snapshot, truth contract.

The compact Telegram card is intentionally concise; the PDFs carry depth.

## 10. Liveness and self-recovery inherited from V6

V7 preserves:
- secret-free worker health file;
- successful poll timestamps;
- callback receive/handle receipts;
- external BCP heartbeat mirroring;
- bounded stale-worker watchdog;
- restart cooldown;
- single receiver/poller discipline;
- HTTP 409 conflict is never normalized as healthy.

## 11. Field gates

V7 is not FIELD_VERIFIED until:
1. exact-head CI passes;
2. serialized merge completes;
3. BCP 0.6.8 and Telegram V7 are consumed by the resident PC;
4. Drive readback exposes V6/V7 worker-health fields;
5. Telegram button callback round-trip is observed;
6. automatic refresh is observed without a manual tap;
7. at least one of each four PDF reports is generated in real Telegram;
8. offline/reconnect behaviour is observed without state loss.

## 12. Cost and resource constraints

- DEFAULT_PAID_SPEND=0 USD.
- No ChatGPT scheduled automation for live presence.
- No duplicate Telegram pollers.
- No heavy local runtime added to the 4 GB Windows PC.
- Preserve low-data and intermittent-connectivity semantics.
