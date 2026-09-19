# BCP — Telegram Human Cockpit V3, Multi-Mission Presence and Low-Latency UX

Status: ACTIVE PRODUCT REQUIREMENT DELTA
Adopted: 2026-09-19

## Purpose

The Telegram cockpit is the user's human control and visibility surface when ChatGPT UI state is ambiguous, delayed, interrupted, under platform verification, or temporarily disconnected.

It does not expose hidden chain-of-thought. It exposes externally observable mission progress, machine receipts, node health, current bounded action, and explicit human gates.

The user is not an IT operator and MUST NOT need to decode commit numbers, raw branch names, workflow IDs, hashes, or transport jargon in the normal view.

## Human-first default card

The normal /status view MUST be a readable mission card, not a raw telemetry dump.

It MUST show:
1. Project or mission name in plain language.
2. Overall state: WORKING / WAITING / BLOCKED / NEEDS YOU / DONE / DEGRADED.
3. Verifiable progress: [██████░░░░] 6/10 — 60% only when the finite plan denominator is known.
4. Current step in plain language.
5. Last completed step.
6. Next expected step.
7. Human action: AUCUNE / REQUISE / OPTIONNELLE, with one concise instruction when required.
8. Last proof of life: source timestamp, age, and source node.
9. Connectivity summary: PC, B-EDGE, Nexus/remote ingress, GitHub/Drive as compact OK/DEGRADED/OFFLINE states.
10. Message timing: observed_at, sent_at, and delivery lag when materially delayed.

Normal status MUST NOT repeatedly show spend/cost while spend is zero. Cost remains available in /details and surfaces automatically only for a non-zero charge, budget threshold, or COST_HOLD.

Technical identifiers such as PR numbers, commit SHA, branch, workflow/run IDs, fencing tokens and raw exception codes belong in /details, not the default card.

## Progress truth rules

A percentage is allowed only for a finite, explicit, externally tracked plan.

- completed_steps / planned_steps MUST be machine derivable.
- If the plan changes, the card MUST say Plan révisé and recompute the denominator.
- Hidden reasoning, model thought depth, platform verification progress, or unknown future work MUST NOT be converted into a percentage.
- When a denominator is not trustworthy, show the current step and say that total work remains open instead of inventing a percent.
- Weighted phases are allowed only when weights are predefined in the mission plan and persisted durably.

## Micro-action journal

Every mission SHOULD persist a compact event stream:

MISSION_STARTED -> STEP_STARTED -> EVIDENCE_OBSERVED -> STEP_COMMITTED -> NEXT_STEP_SELECTED -> ... -> MISSION_DONE

Each event MUST carry:
- mission_id;
- project_id;
- step_id and optional parent macro_step_id;
- human label;
- state;
- observed_at timestamp;
- source node/provider;
- evidence locator or receipt when available;
- idempotency key;
- revision/fence metadata where a mutation is involved;
- human_action_required and concise instruction;
- optional plan position n/N.

The cockpit may summarize events, but the durable journal remains machine-readable.

## One live card, not message spam

For an active mission, Telegram SHOULD maintain one primary live status message and update it with editMessageText or the equivalent instead of sending repeated near-duplicate status messages.

New push messages are reserved for meaningful transitions:
- human action required;
- BLOCKED/HOLD;
- recovery/takeover;
- milestone committed;
- mission DONE;
- material network/provider degradation.

Duplicate events MUST be collapsed by mission/event idempotency keys.

## Useful message size

Default messages SHOULD be medium-length and explanatory enough for a non-technical user.

Do not compress the normal view into cryptic one-line codes.
Do not dump raw engineering logs.
Use concise paragraphs and a stable visual hierarchy.
Technical depth remains available through /details.

## Images and visual cards

Telegram image delivery is supported as an optional UX layer, not the primary progress transport.

- Text remains the default because mobile data is constrained.
- A lightweight progress-card image MAY be generated for explicit /card, major milestones, or when it materially improves comprehension.
- Do not regenerate/send images for every heartbeat.
- Image size SHOULD be aggressively bounded and cached.
- The same underlying truth must remain available in text for low-data mode.

## Latency and timestamp contract

Every user-visible status response MUST distinguish event observation time from render/send time, and expose delivery lag when known.

The system MUST NOT make a delayed message look current.

Recommended resident cadence, adjustable by the resource governor:
- active local node heartbeat: target 15–30 s;
- idle heartbeat: target 45–60 s;
- power/data-saver mode: target 90–120 s;
- mission state transition: publish immediately, with 2–5 s coalescing to merge bursts;
- Telegram/Nexus retry: bounded exponential backoff with jitter, no tight retry loop;
- no-evidence watchdog: after a persisted threshold, report WAITING_EXTERNAL_EVIDENCE or POSSIBLE_STALL without claiming hidden ChatGPT reasoning state.

These are resident BCP timers, not ChatGPT scheduled automations and must not consume ChatGPT Work quotas.

## Independence from the active ChatGPT turn

The cockpit MUST remain useful when the ChatGPT conversation is silent or interrupted.

No Telegram progress push may depend on this assistant being actively generating a response.

Progress sources are the durable Mission Event Journal and externally observable nodes/receipts. A ChatGPT conversation contributes only when it emits a supported external event/checkpoint.

If no supported event exists, the cockpit says so plainly, for example:
ChatGPT: état interne non observable — dernière preuve externe il y a 74 s.

## Multi-conversation and multi-project model

One Telegram bot is the preferred default. Do NOT create one bot per ChatGPT conversation.

The bot MUST multiplex:
- multiple projects;
- multiple missions;
- multiple ChatGPT conversations/sessions as logical mission sources;
- PC/B-EDGE/BuildHub/model-broker jobs.

Required views:
- /status — current or most relevant mission card;
- /missions — active missions and their plain-language state;
- /project <name> — latest project status;
- /last — last durable milestone;
- /details — technical evidence;
- /help — plain-language commands.

Conversation/session identifiers are correlation metadata, not canonical state.

Multiple physical Telegram bots are allowed only for an explicit security/ownership boundary or a proven platform limitation. They are not the default scaling mechanism.

## Node and connectivity presence

The cockpit MUST separately represent:
- PC-WORKER/BCP runtime alive/stale/offline;
- B-EDGE old phone alive/stale/offline;
- Nexus/remote ingress reachability;
- GitHub/Drive evidence freshness;
- current user phone as UI endpoint only, not required infrastructure.

The old phone remains on home Wi-Fi as B-EDGE. It does not need Telegram installed.

The current phone may move between home Wi-Fi and mobile data without becoming a relay dependency.

## Home-WiFi transport strategy

Observed field fact: direct PC -> Telegram API can fail on home Wi-Fi even when DNS succeeds.

Target path:
PC local event -> durable outbox -> B-EDGE/LAN and/or Nexus HTTPS ingress -> Telegram Bot API -> current phone.

BCP MUST field-test which of PC->Nexus and B-EDGE->Nexus works on the real home network and prefer the cheapest reliable path.

If remote delivery is unavailable:
- persist locally first;
- keep local mission execution independent;
- retry later with bounded backoff;
- never lose or duplicate committed events.

## Automatic update UX

Qualified update metadata is event-driven and machine-readable.

- Windows BCP updates SHOULD be fully automatic in user space when safe, hash-pinned, reversible and read back.
- B-EDGE SHOULD discover/download the qualified APK automatically into app-owned cache.
- If Android requires OS/user installation confirmation, Telegram/BCP should present exactly one clear human gate rather than repeated manual file handling.
- Drive CURRENT artifacts are replaced/curated by the product workflow; the user should not manually sort versions.
- No ChatGPT scheduled automation is required for update delivery.

## Human action contract

Every mission card MUST contain one of:
- Action pour vous: AUCUNE
- Action pour vous: REQUISE — <one concrete instruction>
- Action pour vous: OPTIONNELLE — <one concrete instruction>

If no action is needed, the user should not have to send /status repeatedly to keep work moving.

## Acceptance tests

V3 is not FIELD_VERIFIED until all applicable tests pass:
1. one live mission card is edited rather than duplicated under repeated events;
2. finite plan renders truthful n/N and percentage;
3. dynamic plan revision is visible and recomputed;
4. event timestamps expose delivery lag;
5. user action gate is explicit;
6. technical IDs are hidden from normal view and visible in /details;
7. zero spend is suppressed from normal view;
8. PC heartbeat loss is detected without claiming hidden ChatGPT state;
9. B-EDGE heartbeat loss is independently detected;
10. home-WiFi PC->Telegram failure does not stop local mission journaling;
11. Nexus/B-EDGE relay path is field-tested on the real Kinshasa network;
12. duplicate events do not produce duplicate Telegram messages;
13. multi-mission view can distinguish at least two simultaneous project missions;
14. no ChatGPT scheduled automation is used for resident presence/update checks;
15. a user can understand current work, last success, next step, and whether they must act without reading engineering logs.
