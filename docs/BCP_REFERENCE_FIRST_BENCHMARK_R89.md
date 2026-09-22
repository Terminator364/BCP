# BCP R89 — Reference-first benchmark: ne pas réinventer la roue

Status: CANONICAL CANDIDATE / RESEARCH-FIRST GATE
Date: 2026-09-22
Scope: API/BCP + B-EDGE Android + PC worker + Telegram cockpit + continuity/orchestration
Product bytes changed by R89: **NO**

## 1. Why R89 exists

BCP has accumulated substantial internal architecture, safeguards, tests and specification. That is useful, but it creates a failure mode: an internally coherent design can still reinvent mature interaction patterns, transport ladders, updater flows, pairing flows, state machines or operator dashboards that already exist and have been field-tested elsewhere.

R89 changes the default engineering order:

```
A+B+C CURRENT SPEC
-> REFERENCE CORPUS
-> CURRENT-vs-REFERENCE GAP MAP
-> REUSE / ADAPT / BUILD_ONLY_IF_GAP
-> LICENSE + PROVENANCE GATE
-> USER-JOURNEY DESIGN
-> REPRESENTATIVE SIMULATION
-> IMPLEMENTATION
-> FIELD GATE
```

A source may be named in design docs, code comments and attribution records. **Non-commercial use does not waive software licences.** No external source code is copied merely because the project is personal/non-commercial; code reuse requires a separate compatibility/provenance decision.

## 2. Current B-EDGE truth before benchmark

Current machine-qualified baseline:
- B-EDGE: `2.2.0-full-node-evergreen`
- package: `com.blessing.bcpedge.evergreen`
- current APK SHA-256: `a95460edc340fdba6e045ef1ad3c8ddbc062c3a61f56fbb479360f2b00102e3a`
- signature schemes: v2/v3
- field state: install pending / not field verified

The current Android UI is implemented programmatically in:
`android-b-edge/src/main/java/com/blessing/bcpedge/MainActivity.java`.

It currently places in one vertically scrolling primary surface:
- overall state;
- server-node internals;
- transports;
- capability registry;
- permission state;
- durable memory/provenance counts;
- cache/storage;
- TLS/security details;
- reconnect/checkpoint/resume buttons;
- a `PARAMÈTRES / DIAGNOSTIC` action that opens another mixed menu containing status, repair, update, memory, registry and tests.

The representative emulator test in
`.github/workflows/android-human-action-simulation.yml`
explicitly scrolls repeatedly to locate technical cards below the first viewport.

### R89 finding

This proves technical richness, **not user-task quality**. It is a field/engineering dashboard grown incrementally. It must no longer be treated as the target human UX.

BCP already contains a progressive-disclosure requirement for its Telegram cockpit: normal view first, technical evidence behind an explicit control. R89 applies the same principle consistently to B-EDGE.

## 3. External reference corpus

The references below are precedents, not dependencies. The default adoption mode is **PATTERN_ONLY / ADAPT** until a separate licence review authorizes source reuse.

| Area | Mature precedent | What it already proves | R89 decision for BCP |
|---|---|---|---|
| Android settings | Android Developers — Settings | Settings are for infrequently accessed preferences; frequent actions stay contextual | **ADAPT**: remove repair/update/test actions from “Settings” |
| Android permissions | Android Developers — Runtime permissions | Ask in context; allow cancellation; degrade gracefully | **ADAPT** permission stepper and contextual prompts |
| Server discovery onboarding | Home Assistant Companion | Discover local server first; list candidates; manual address only fallback; complete setup then dashboard | **ADAPT strongly** for PC discovery/pairing |
| Dedicated Android node | Home Assistant Android Home App / kiosk | Dedicated Android device can boot directly into a control surface | **ADAPT** for dedicated-old-phone mode |
| Device pairing | KDE Connect | Show discovered device names, request pair, accept on peer; IP fallback only when discovery fails | **ADAPT strongly** |
| Stable device identity | Syncthing | Device identity tied to public key/certificate; identity used for auth/addressing | **KEEP/ALIGN** BCP TLS identity; simplify human presentation |
| LAN discovery + HTTPS | LocalSend protocol | Multicast discovery, callback registration, HTTPS fingerprints, bounded legacy scan fallback | **ADAPT** transport/discovery ladder; avoid bespoke scans as primary |
| Direct-first + relay fallback | Tailscale / RustDesk | Prefer direct path; use relay when direct connection is impossible | **ADAPT** explicit path ladder and operator state |
| Android direct-source updater | Obtainium | Source adapters, release discovery, background work, installer abstraction, signing/verification UX | **ADAPT architecture/UX only** pending licence review; do not copy GPL code into BCP by default |
| Android persistent work | Android WorkManager | Constraint-aware, persistent, retryable work across restart/reboot | **KEEP/ALIGN** existing WorkManager path; stop inventing parallel scheduler semantics |
| Durable workflow semantics | Temporal | Durable workflows resume after process/network/infrastructure failure | **ADAPT semantics**, not runtime dependency |
| Observable task states | Prefect | Explicit task states, retries, caching, timeouts and state history | **ADAPT** mission/job state vocabulary |
| Agent/checkpoint memory | LangGraph | Checkpoints, pending writes, thread-scoped durable state | **ADAPT semantics** to BCP mission-step/checkpoint layer |
| Reliable mutation retries | Stripe / AWS Builders Library | Stable idempotency keys make uncertain retries safe | **KEEP/ALIGN** BCP idempotency + receipts |
| Cross-system delivery | AWS transactional outbox | State mutation + outgoing event persisted atomically; relay later; consumer idempotent | **ADAPT strongly** for B-EDGE outbox/Telegram/PC delivery |
| Reusable integrations | Node-RED | Flows are importable/exportable JSON; packaged nodes ship examples | **ADAPT** “recipe/flow library” before writing one-off integrations |
| Agent execution boundary | OpenHands Runtime / Agent Canvas | UI/orchestrator separated from action executor/runtime; actions return observations | **ADAPT** for future agents/tools; no UI code as executor |
| Operator status UX | Uptime Kuma | Compact status-first dashboard; detail and configuration separated | **ADAPT** visual information hierarchy |

### Primary reference URLs

- https://developer.android.com/design/ui/mobile/guides/patterns/settings
- https://developer.android.com/training/permissions/requesting
- https://developer.android.com/develop/background-work/background-tasks/persistent
- https://companion.home-assistant.io/docs/getting_started/
- https://companion.home-assistant.io/docs/gallery/android
- https://companion.home-assistant.io/docs/integrations/android-home-app-launcher/
- https://userbase.kde.org/KDEConnect/en
- https://docs.syncthing.net/dev/device-ids.html
- https://github.com/localsend/protocol
- https://tailscale.com/docs/reference/device-connectivity
- https://rustdesk.com/docs/en/self-host/
- https://github.com/ImranR98/Obtainium
- https://docs.temporal.io/
- https://docs.prefect.io/
- https://reference.langchain.com/python/langgraph/checkpoints
- https://docs.stripe.com/api/idempotent_requests
- https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/
- https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html
- https://nodered.org/docs/user-guide/editor/workspace/import-export
- https://github.com/OpenHands/docs/blob/main/openhands/usage/architecture/runtime.mdx
- https://github.com/louislam/uptime-kuma

YouTube/tutorials are permitted as **human-flow observation evidence** (tap count, labels, onboarding order, discoverability), never as the sole authority for security or architecture.

## 4. Current-vs-reference gap map

### 4.1 Home screen

**Current:** one long engineering scroll containing almost every subsystem.

**Reference pattern:** status-first overview, next action visible immediately, progressive disclosure.

**Decision — ADAPT:**
The default compact-phone home screen becomes:
1. overall state: `READY / NEEDS_ACTION / WORKING / OFFLINE / DEGRADED`;
2. current objective;
3. exactly one primary CTA when human action is required;
4. compact Phone / PC / Network status;
5. last successful checkpoint/sync time;
6. optional “Details” entry.

No raw capability list, claim counts, TLS fingerprint, cache quota or transport internals above the fold.

### 4.2 Navigation

Target compact Android information architecture:

- **Accueil** — status, current objective, next action.
- **Missions** — active/pending/completed mission steps and resumptions.
- **Appareils** — phone node, PC(s), pairing, connectivity, updates.
- **Activité** — human-readable event history / receipts.
- **Paramètres** — secondary/preferences surface, reached from top-level secondary action rather than used as a repair menu.

On a compact phone, 3–5 primary destinations fit the standard Android navigation model. Advanced diagnostics remains a secondary surface.

### 4.3 Pairing/discovery

**Current:** automatic connect plus confirmation dialog with shortened identity/TLS fingerprints; manual/diagnostic behaviors remain implementation-centric.

**Target borrowed flow (Home Assistant + KDE Connect + Syncthing):**
1. `Recherche du PC BCP…`
2. discovered PC cards by human-readable device name;
3. select PC;
4. verify a short human code / matching identity cue;
5. confirm;
6. `Connecté`.

Advanced details may show full certificate/device fingerprints.

Fallback order:
`NSD/mDNS -> bounded LocalSend-style multicast/registration-compatible discovery pattern where appropriate -> explicit QR/manual address -> diagnostic subnet scan only`.

Manual IP entry is a recovery path, not the nominal path.

### 4.4 Permissions / dedicated-server setup

**Current:** first-launch dialog may immediately ask for a bundle of server permissions and battery exemption.

**Target borrowed flow (Android + Home Assistant):**
- show value/state first;
- request each capability in context;
- explain why immediately before the OS prompt;
- allow “Later” where safe;
- display a short setup progress stepper;
- degrade explicitly if optional capability is denied;
- never imply that a denied optional permission means the entire node is broken.

Suggested steps:
`Node active -> Nearby devices -> Notifications -> Battery reliability -> Done`.

### 4.5 Settings

**Current:** “Paramètres / diagnostic” contains frequent operational actions:
repair PC, update PC, update Edge, quick test, status, memory, source registry.

**Target:**
Settings contains preferences only, e.g.:
- dedicated-server mode;
- data-saver policy;
- notification preferences;
- update channel/policy where user-configurable;
- privacy/telemetry preference;
- advanced diagnostics toggle.

Operational actions move to their object:
- update/repair PC -> **Appareils > PC**;
- update B-EDGE -> **Appareils > Ce téléphone**;
- resume/checkpoint -> **Mission** context;
- quick test -> **Diagnostics avancés**.

### 4.6 Updates

Do not invent a new update UX.

Borrow the **Obtainium-style source-adapter mental model** and Android update-state presentation:
`CHECKING -> AVAILABLE -> DOWNLOADING -> VERIFIED -> READY_TO_INSTALL -> INSTALLED / FAILED`.

BCP-specific invariants remain stricter:
- allowlisted source;
- exact expected package ID;
- pinned signing identity;
- SHA-256/readback;
- monotonic version;
- rollback evidence;
- no uninstall for normal upgrade;
- no user prompt until the package is actually verified and ready.

Obtainium is GPL-3.0 according to its repository. Therefore its architecture/UI is currently a **reference**, not a code-copy source, unless a later licence decision explicitly permits it.

### 4.7 Transport

Stop adding transport mechanisms because they are imaginable.

Reference ladder:
`LOCAL_DIRECT_ENCRYPTED -> LOCAL_ALTERNATE_DISCOVERY -> RELAY_IF_NEEDED -> DURABLE_STORE_AND_FORWARD`.

Use measured failure evidence to justify a new transport. Tailscale/RustDesk show the mature direct-first/relay-fallback pattern; LocalSend/Syncthing show mature identity/discovery patterns.

### 4.8 Durable mission execution

Keep BCP’s existing Room/WorkManager/idempotency foundations, but align vocabulary and tests to mature workflow engines:

`PENDING -> READY -> RUNNING -> WAITING_EXTERNAL / WAITING_HUMAN -> COMMITTING -> COMMITTED`
with explicit:
- retry policy;
- timeout;
- idempotency key;
- expected revision;
- result/effect receipt;
- persisted pending writes;
- recovery from last committed checkpoint.

Temporal/Prefect/LangGraph are semantic references. BCP should not import heavyweight workflow engines onto the 4 GB / zero-dollar target unless a measured gap makes that rational.

### 4.9 “Banking/payment-grade tunnel” reliability

For every effectful operation, BCP uses the same conceptual discipline seen in payment and cloud APIs:

`REQUEST_ID -> VALIDATE -> INTENT_PERSISTED -> EFFECT_ATTEMPT -> PROVIDER/DEVICE_ACK -> READBACK -> COMMIT_RECEIPT -> RECONCILE_IF_UNKNOWN`.

Rules:
- unknown outcome is not failure and not success;
- same idempotency key for retry of the same intent;
- changed intent gets a new key;
- transactional outbox when durable state and outbound notification must stay coherent;
- consumer deduplication because at-least-once delivery can duplicate messages;
- reconciliation query before repeating an uncertain mutation.

This is where BCP should copy **discipline**, not vendor implementation.

## 5. R89 target B-EDGE user journey

### Cold first launch

`Welcome -> This phone can become your BCP Edge node -> Find PC -> Select/verify -> Required setup steps -> READY`.

The user should not see database version, Room schema, claims, queue internals, TLS hashes or provider internals unless opening Advanced diagnostics.

### Normal return

The first screen answers five questions without scrolling:
1. Is BCP OK?
2. What is it doing?
3. Does it need me?
4. What happened last?
5. What is next?

### Human gate

If a human action is truly required, exactly one visually dominant CTA appears. No competing repair/update/test/checkpoint buttons.

## 6. Representative-simulation changes required before next field install

The existing emulator test currently proves that technical text exists after scrolling. R89 changes the UX proof target.

Future Android human-action simulation must verify tasks, not strings:

1. **Primary next action visible without scroll** on the representative 320×640 compact viewport.
2. From unpaired state, a discovered PC can be selected and pairing reaches a clear confirmation flow.
3. Manual IP/QR is not the default when discovery succeeds.
4. Permission setup exposes one contextual rationale at a time.
5. READY state is understandable without technical diagnostics.
6. Settings does **not** contain operational repair/update/checkpoint actions.
7. Update action is located under the relevant device and shows a persisted update state.
8. Advanced diagnostics can expose full technical evidence without cluttering Home.
9. Cold relaunch restores the same human-facing mission state.
10. Accessibility/tap targets and back navigation remain valid.

## 7. Mandatory adoption tunnel

No future BCP feature is implementation-ready until it has an entry in the reference registry with:

- requirement IDs from A+B+C;
- user-feedback IDs;
- current implementation evidence;
- at least 2 relevant external references when a mature pattern plausibly exists;
- `REUSE / ADAPT / BUILD_ONLY_IF_GAP`;
- source-code reuse licence status;
- explicit differentiator if `BUILD_ONLY_IF_GAP`;
- target user journey;
- representative test;
- rollback/compatibility impact.

### BUILD_ONLY_IF_GAP burden of proof

A custom design is allowed only when one of these is documented:
- no mature reference fits the constraint;
- licensing prevents reuse and adaptation cannot satisfy the requirement;
- BCP’s offline/RDC/4-GB/zero-dollar constraint materially changes the problem;
- security/trust model requires a different mechanism;
- reference implementation is heavier or less reliable than a bounded custom component;
- measured field evidence proves the reference pattern insufficient.

“Because we already started implementing it” is not a justification.

## 8. Immediate decisions

- **Freeze new ad-hoc B-EDGE screens and functions.**
- Preserve B-EDGE 2.2 as a machine-qualified technical baseline.
- **Defer the user install instruction** until the reference-first reconciliation has produced one coherent next candidate; avoid another install-observe-redesign loop.
- Do not discard proven transport/security/durable-state work merely because UX changes.
- R90 should implement the highest-value benchmark deltas as one coordinated slice, starting with Home / Devices / pairing / permission / update-information architecture and task-based emulator acceptance.
- Every future implementation PR must cite the relevant reference-registry IDs.

## 9. Definition of success

R89 succeeds when BCP stops measuring progress as “we implemented another screen/service” and starts measuring:

- percentage of requirements satisfied by established patterns;
- user steps removed;
- custom mechanisms avoided;
- field actions avoided;
- recovery ambiguity reduced;
- proven code reused legally where appropriate;
- bespoke code restricted to actual BCP differentiators.

The desired product is not the most original architecture. It is the **smallest, clearest, most reliable composition of already-proven ideas that satisfies A+B+C under the user’s real constraints**.
