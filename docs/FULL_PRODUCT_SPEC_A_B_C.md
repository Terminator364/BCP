# BCP — Full Product Specification A+B+C

Status: CANONICAL CANDIDATE R77 · MERGE_REFINE_PRESERVE
Date: 2026-09-21

## 1. Definition

BCP is evaluated against the whole specification, never against a convenient subset.

- **A — Original preconception**: sealed BCP V0.7 / APIAX07 lineage, original product intent, promised functions and architecture.
- **B — Research-backed expansion**: realizable extensions that go materially further than A while respecting Android/Windows constraints, zero-dollar operation and DRC network/power conditions.
- **C — Accumulated field feedback**: user corrections, working preferences, field failures and operating rules, including full use of the dedicated Android phone, communication continuity, no micro-beta loop and proof before user actions.

The canonical formula is: **PRODUCT_SPEC = A + B + C**. A release can be locally correct and still be globally incomplete.

## 2. Evidence maturity

Current conservative weighted maturity on this R77 mapping: **NaN%**.
A=NaN% · B=NaN% · C=NaN%.

This is an evidence maturity score: FIELD=100%, CI=80%, CODE=60%, DESIGN=30%, GAP=0%. It is deliberately stricter than feature-counting. A requirement moves upward only with concrete evidence.

## 3. Non-negotiable architecture

B-EDGE is the preferred persistent low-power appliance node. PC-WORKER is the Windows/heavy worker and verified replica. BCP NEXUS is a thin remote bootstrap/witness/ingress facade, never mandatory full private memory. Canonical state remains single-writer/fenced; no split-brain PROJECT_HEAD.

The dedicated Android phone must remain useful with the PC absent: local API, durable queue/memory/receipts, store-and-forward, context pack, bounded local execution, presence/discovery and communications relay. It must not require its own SIM.

## 4. R77 research constraints added to B

Android official guidance materially constrains the implementation:
- Wi-Fi Direct can provide peer/service discovery without an existing LAN, but requires modern Nearby Wi-Fi permissions and capability/location-mode handling.
- Bluetooth SCAN/ADVERTISE/CONNECT are runtime permissions on modern Android and must be explicitly onboarded.
- Foreground-service background starts are restricted on modern Android; Android 15 also limits long-running `dataSync` FGS time. Therefore correctness must not depend on an immortal background process.
- WorkManager/transactional local storage remain the recovery path for deferrable/retriable work; foreground service is reserved for active connected-device/remote-messaging duties.

## 5. Capability ledger

### A

- **A01 — Canonical project identity/state** [P0 · CODE_PRESENT] — One canonical project identity, revision/head and current mission state survive conversations/devices.
- **A02 — Operational memory** [P0 · DESIGN_ONLY] — Structured project/user/technical/operating/history/policy memory with provenance and authority classes.
- **A03 — Bounded permissions** [P0 · CODE_PRESENT] — Named operations, least privilege, R0-R4-style bounded authority; no arbitrary shell as normal API.
- **A04 — Idempotent jobs** [P0 · CODE_PRESENT] — Jobs have stable IDs/idempotency, bounded retries and duplicate suppression.
- **A05 — Receipts and evidence** [P0 · CI_PROVEN] — Side effects produce machine-readable receipts/readback before COMMITTED/SUCCESS.
- **A06 — Offline continuity** [P0 · CODE_PRESENT] — Loss of Internet must not destroy project state or queued work.
- **A07 — Deterministic recovery** [P0 · CODE_PRESENT] — Recovery resumes the next uncommitted action rather than replaying committed work.
- **A08 — ChatGPT orchestration** [P0 · FIELD_PROVEN] — ChatGPT reasons/orchestrates while durable external state remains authoritative.
- **A09 — ChatGPT-PC Windows worker** [P0 · FIELD_PROVEN] — Windows node executes bounded Windows-only/heavy work and exposes telemetry/receipts.
- **A10 — Dedicated Android B-EDGE** [P0 · FIELD_PROVEN] — Old Android phone is a permanent dedicated B-EDGE node, not merely a UI accessory.
- **A11 — BuildHub build factory** [P1 · FIELD_PROVEN] — Build/test packaging is offloaded to a build factory/CI path instead of overloading low-RAM PC.
- **A12 — Drive durable mirror** [P0 · FIELD_PROVEN] — Drive holds CURRENT/installers/telemetry/recovery/context projections with readback.
- **A13 — GitHub source + CI authority** [P0 · FIELD_PROVEN] — Repository branches/PRs/exact-head CI govern code integration.
- **A14 — Gmail checkpoint channel** [P0 · FIELD_PROVEN] — Detailed human START/END checkpoints use Gmail with provider acknowledgement.
- **A15 — Telegram cockpit** [P0 · GAP_OPEN] — Telegram provides human-visible status/cockpit and secondary communication path.
- **A16 — CORE/ADAPTER separation** [P0 · DESIGN_ONLY] — Core state/orchestration is separated from replaceable providers/adapters.
- **A17 — PROJECT_HEAD semantics** [P0 · CODE_PRESENT] — Canonical mutations advance a fenced head/revision, never silent multi-master state.
- **A18 — Error ledger** [P0 · CODE_PRESENT] — Failures become durable generalized evidence rather than ephemeral chat text.
- **A19 — Inbox/outbox** [P0 · CODE_PRESENT] — Durable inbox/outbox queues support disconnected work and later reconciliation.
- **A20 — Model/provider broker** [P1 · DESIGN_ONLY] — Multiple free/available providers are replaceable; quota failure is HOLD/retry, never forced payment.
- **A21 — Checkpointed jobs** [P0 · FIELD_PROVEN] — Long work is split into durable checkpoints with resumable next action.
- **A22 — Content-addressed vault/cache** [P1 · CODE_PRESENT] — Large/reusable artifacts and context are addressed by content hash with bounded local storage.
- **A23 — Time trust** [P1 · DESIGN_ONLY] — Receipts/events carry explicit observed/generated times and avoid assuming wall-clock truth after outages.
- **A24 — LAN anti-entropy** [P0 · DESIGN_ONLY] — Nodes reconcile state after local partitions without silently creating conflicting canonical heads.
- **A25 — Incarnation/epoch/fencing** [P0 · DESIGN_ONLY] — Restarts and coordinator changes are protected by epoch/fencing/revision preconditions.
- **A26 — Security classes** [P0 · CODE_PRESENT] — Operations are categorized by risk/permission and unsafe ambiguity fails closed.
- **A27 — Zero-dollar default** [P0 · FIELD_PROVEN] — No automatic purchase, paid API, recharge or mandatory paid cloud dependency.
- **A28 — Secret separation** [P0 · CODE_PRESENT] — Tokens/pairing secrets never live in public repo or exported context projections.
- **A29 — Low-resource PC profile** [P0 · CI_PROVEN] — PC work is bounded for ~4GB RAM, one heavy job at a time, degraded modes under pressure.
- **A30 — Three-level durability** [P0 · DESIGN_ONLY] — Hot local state, durable local DB/receipts, and external recovery mirrors cooperate without one single point of failure.

### B

- **B31 — Phone-primary Edge/API appliance** [P0 · CODE_PRESENT] — Dedicated phone is preferred persistent low-power appliance node; PC is not communications center.
- **B32 — Authenticated local phone API** [P0 · CODE_PRESENT] — Phone exposes bounded authenticated status/sync/jobs/context surfaces and public minimal health/capabilities.
- **B33 — Phone durable Room/SQLite authority** [P0 · CODE_PRESENT] — Phone keeps queue, receipts, memory/index and store-forward state in transactional local DB.
- **B34 — Phone local scheduler** [P0 · CODE_PRESENT] — Deterministic local jobs run on phone without waiting for PC where capability permits.
- **B35 — Phone context compiler** [P0 · CODE_PRESENT] — Phone can build compact project/context packs locally and serve them through authenticated API.
- **B36 — Adaptive private cache** [P1 · CODE_PRESENT] — Phone uses bounded app-private cache/content store with reserve; never consumes entire 64GB device.
- **B37 — Foreground server lifecycle** [P0 · CODE_PRESENT] — A user-visible foreground connected-device/remote-messaging service hosts the persistent local node when allowed.
- **B38 — Boot/package restore** [P0 · CODE_PRESENT] — Phone restores server capability after reboot/package replacement under Android lifecycle rules.
- **B39 — WorkManager reconciliation** [P0 · CODE_PRESENT] — Deferrable reconciliation/drain work uses WorkManager rather than assuming immortal process residency.
- **B40 — LAN NSD discovery** [P0 · CODE_PRESENT] — Phone advertises/discovers BCP services on shared LAN without manual IP entry.
- **B41 — Wi-Fi Direct fallback** [P1 · CODE_PRESENT] — Phone/PC may discover/connect directly without normal LAN/hotspot when hardware/permission supports it.
- **B42 — BLE control/presence fallback** [P1 · CODE_PRESENT] — BLE is available for low-bandwidth discovery/control hints, not bulk payload transport.
- **B43 — USB fallback path** [P2 · DESIGN_ONLY] — Architecture reserves USB/tether/local link as a manual last-resort local path when practical.
- **B44 — Metered/data-saver routing** [P0 · CODE_PRESENT] — Phone and PC classify metered/unmetered connectivity and minimize PC mobile-data use.
- **B45 — Store-and-forward communications** [P0 · CODE_PRESENT] — Messages/commands/telemetry queue durably when no uplink exists and drain idempotently later.
- **B46 — Telegram selective phone relay** [P0 · CODE_PRESENT] — Phone can relay Telegram-bound control traffic while preserving Telegram TLS and strict allowlist.
- **B47 — Telegram ownership lease** [P0 · DESIGN_ONLY] — Only one active inbound Telegram poller/webhook owner exists; failover is explicit/leased to avoid conflicts.
- **B48 — Adaptive transport scoring** [P0 · DESIGN_ONLY] — Runtime chooses LAN/hotspot/Wi-Fi Direct/BLE/USB/remote based on reachability, cost, power and payload class.
- **B49 — Resumable chunk transfer** [P1 · DESIGN_ONLY] — Large artifacts use chunking/hash/resume and do not restart from zero after weak-network interruption.
- **B50 — Resource governor** [P0 · CODE_PRESENT] — Phone/PC throttle CPU, RAM, wakeups, retries, cache and transfer rates under heat/battery/memory pressure.
- **B51 — Permission onboarding** [P0 · CODE_PRESENT] — Dedicated-phone UI requests only capabilities actually used: notifications, Nearby Wi-Fi/Bluetooth, battery mode, etc.
- **B52 — Android lifecycle compliance** [P0 · DESIGN_ONLY] — Foreground/background restrictions, Doze and modern target-SDK limits are explicitly handled instead of assuming an immortal service.
- **B53 — Device-owner advanced mode optional** [P2 · DESIGN_ONLY] — An invasive dedicated-device mode may be evaluated separately, never hidden as baseline or factory-reset requirement.
- **B54 — Chronicle + supersession memory** [P0 · DESIGN_ONLY] — Memory tracks lineage/supersession/conflicts rather than replacing one giant summary file.
- **B55 — Context pack integrity** [P0 · DESIGN_ONLY] — Context projections carry revisions/hashes/freshness/export class and are reproducible from source revision.
- **B56 — Fast BCPGO bootstrap** [P0 · CODE_PRESENT] — Fresh conversation loads compact bootstrap/project context rather than broad Drive/GitHub scans.
- **B57 — Per-turn delta protocol** [P1 · DESIGN_ONLY] — Consumers use UNCHANGED/DELTA/FULL_REFRESH/CONFLICT/DEGRADED/HOLD semantics for revision-aware context refresh.
- **B58 — Three-node partition safety** [P0 · DESIGN_ONLY] — B-EDGE, PC-WORKER and NEXUS survive pairwise partitions without split-brain PROJECT_HEAD.
- **B59 — Pre-human representative simulation** [P0 · CI_PROVEN] — User click/install/retry paths are simulated in Windows/Android CI when technically reproducible.
- **B60 — Server-first human UI** [P0 · CODE_PRESENT] — Phone UI shows node health, transports, queue, memory, permissions, autonomy and diagnostics instead of pretending to be only a PC client.

### C

- **C61 — Gmail START before work** [P0 · FIELD_PROVEN] — Every user-invoked tranche sends/acks labeled BCP START before substantive work.
- **C62 — Gmail END before app reply** [P0 · FIELD_PROVEN] — Every tranche sends complete END and verifies SENT/provider message_id before ChatGPT final pointer.
- **C63 — 25-minute cadence** [P0 · GAP_OPEN] — Canonical cadence is 25 minutes total: ~23 useful work + ~2 closeout reserve.
- **C64 — Primary close owner, no normal automation dependency** [P0 · CODE_PRESENT] — Active assistant owns normal close; scheduled guards are not the normal path.
- **C65 — Delivery-key idempotence** [P0 · CODE_PRESENT] — START/END are tracked by unique delivery key + Gmail search + provider message_id to prevent duplicates/missing closes.
- **C66 — Append-only communication ledger** [P0 · CODE_PRESENT] — Communication receipts survive chat/UI loss and allow crash-window recovery.
- **C67 — ChatGPT pointer-only after END** [P0 · FIELD_PROVEN] — Detailed checkpoint stays in Gmail; app shows only Gmail/date/time/checkpoint after ACK.
- **C68 — BCP Gmail label** [P0 · FIELD_PROVEN] — All BCP START/END mail is labeled BCP for deterministic recovery/search.
- **C69 — Fresh conversation without re-explanation** [P0 · CODE_PRESENT] — BCPGO BCP reloads communication, A+B+C spec, writer fence, state and next action without asking user to reconstruct history.
- **C70 — User not telemetry bus** [P0 · CODE_PRESENT] — System checks GitHub/Drive/telemetry/connectors itself before asking for screenshots/commands.
- **C71 — No micro-beta install loop** [P0 · CODE_PRESENT] — Do not repeatedly make user install tiny increments; publish one coherent qualified full-node candidate.
- **C72 — Full use of dedicated phone** [P0 · CODE_PRESENT] — 4GB/64GB dedicated Android carries meaningful memory, orchestration, communication and local execution workload.
- **C73 — PC is specialized worker, not sole center** [P0 · DESIGN_ONLY] — PC handles Windows/heavy compute/build/sign/compatibility while communications/state can survive without it.
- **C74 — No SIM assumption on old phone** [P0 · DESIGN_ONLY] — Phone full-node works on LAN/hotspot/local links and does not require its own SIM.
- **C75 — RDC unstable network/power** [P0 · DESIGN_ONLY] — Architecture treats brownouts, poor Wi-Fi, mobile hotspot changes and abrupt device loss as normal test cases.
- **C76 — Zero additional spend** [P0 · FIELD_PROVEN] — Existing/free resources only; quota exhaustion becomes checkpoint/HOLD/retry, not payment.
- **C77 — Concrete UI before field install** [P0 · CI_PROVEN] — Android emulator must verify actual screens/buttons/permissions/status before asking user to install.
- **C78 — Communication P0 over product polish** [P0 · CODE_PRESENT] — Continuity/Gmail/Telegram/ledger failures are repaired before cosmetic/product expansion.
- **C79 — A+B+C coverage gate** [P0 · GAP_OPEN] — Every release/change maps to the whole A+B+C ledger; partial-scope success cannot masquerade as product completion.
- **C80 — Truthful completion percentage** [P0 · GAP_OPEN] — Completion percentage is computed from evidence-backed capability states and distinguishes design/code/CI/field proof.

## 6. Release gate

No candidate may be described as the final BCP product unless:
1. all P0 requirements are at least CODE_PRESENT;
2. every user-facing install/click path has representative CI/emulator qualification where technically simulatable;
3. communication START/END delivery is provider-acknowledged and recoverable across fresh conversations;
4. B-EDGE full-node remains useful in PC-absent mode;
5. current release manifests map to this ledger revision;
6. exact-head CI and field readback are attached to the promotion receipt.

Micro-betas that merely advance one small capability are internal CI candidates only; they are not a reason to repeatedly reinstall on the phone.
