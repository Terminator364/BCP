# BCP / API — Cahier des charges canonique A+B+C — R76

Status: CANONICAL_CANDIDATE
Rule: the product specification is A + B + C. A subset is never “the product”.

## A — Original intent and sealed preconception

A is reconstructed from the sealed BCP V0.7 lineage, BCP_API_Personnelle_Dossier_Complet_2026-09-18.pdf and APIAX07_HANDOFF.md.
BCP is a personal digital control/continuity plane, not merely an HTTP API. It gives projects stable identity, canonical HEAD, operational memory, bounded permissions, structured jobs, immutable events/receipts/evidence, offline continuity and deterministic recovery across ChatGPT, PC, phone Edge, BuildHub, Drive, GitHub, Gmail and future adapters.

A requires as one system: local-first interruption tolerance; Project/HEAD/Event/Job/Artifact/Evidence/Capability/Device/Checkpoint contracts; append-only history, idempotency and fencing; allowlisted schema-bound execution; CORE separated from ADAPTERS; thin-cloud coordination; universal OUTBOX/INBOX; proof-carrying receipts; approval lanes; global recovery pointer; explicit resource budgets; retention/export; a comprehensible multi-project cockpit; and minimal human handoff.

## B — Engineering expansion beyond the original idea

B must go materially further than A while remaining feasible, zero-dollar-first and field-verifiable.

### B1. Phone-primary Edge appliance
The dedicated old Android phone is promoted from client/relay to PRIMARY LOW-POWER EDGE/API APPLIANCE. It owns a durable CORE subset: project-state replica, inbox/outbox, receipts, communication journal, memory/index, capability snapshot, low-risk scheduler, health/presence, content cache and authenticated local API. The Windows PC becomes a specialist worker for Windows-only, build/sign, heavy or compatibility tasks — not the always-on communications center.

### B2. Optional dedicated-device management
Because this phone is fully dedicated, BCP SHALL support an optional fully-managed / Device-Owner appliance profile behind a separate qualified provisioning gate. Lock-task/kiosk and selected device policy can then be enabled. Root is not a baseline requirement; normal app mode remains supported.

### B3. Multi-transport local fabric
Cheapest viable path order: same-LAN NSD; hotspot LAN; Wi-Fi Direct service discovery when no shared AP exists; BLE for presence/control/tiny payloads; optional Nearby Connections adapter where Google Play Services is acceptable; USB/ADB/tether only as a separately field-qualified recovery transport. The old phone needs no SIM and may use household Wi-Fi or another phone’s hotspot.

### B4. Storage and memory
The current fixed 8 GiB ceiling underuses a fully dedicated 64 GB device. Target policy: adaptive use up to about half of total storage, capped at 32 GiB, while preserving at least 8 GiB or 20% device reserve (whichever is larger), with early degradation on pressure. Critical operational state remains in SQLite/Room; bulk/cache/history uses content-addressed app-private storage. Portable recovery bundles handle uninstall-sensitive state.

Critical SQLite state SHALL have explicit power-loss durability classes, bounded WAL checkpoint policy and abrupt-power-loss tests. Chronic memory SHALL use bounded indexing/FTS rather than injecting raw history into every reasoning call.

### B5. Phone-side execution
EDGE_ONLY must do useful work, not only snapshots. Allowlisted deterministic operations SHALL include state/context snapshots, communication audit/queue maintenance, content verification/hash/index work, recovery bundle preparation, reconciliation and other bounded low-risk primitives. Arbitrary shell/code execution remains forbidden.

### B6. Communication broker
The phone durably keeps provider-bound intents and replays them idempotently when uplink returns. Telegram can use a direct phone relay. Gmail remains provider/API scoped, but delivery intent and receipt state can still be stored locally. Local enqueue is never confused with provider delivery.

### B7. Local API security
The bearer-protected cleartext HTTP LAN API is transitional. Target: authenticated encryption with Android-Keystore key material, paired trust/pinning and replay-resistant requests. No arbitrary proxy target and no shell endpoint.

### B8. Server-grade phone UI
The phone UI is an appliance cockpit, not a demo client. It SHALL expose Node/Server readiness; Projects/HEADs; Jobs/Queue/Local execution; Communications/receipts; Memory/Context/Storage; Network/transports; Permissions/Dedicated mode; Diagnostics/Recovery/Updates. Visual acceptance on emulator and target screenshots is a release gate.

## C — Accumulated field requirements

C carries all durable feedback: no micro-beta install chain; representative PC/Android simulation before user clicks; Gmail START -> work -> Gmail END provider proof -> app pointer; 25-minute cadence with target 23 minutes useful work + 2 minutes close reserve; PRIMARY_ASSISTANT owns normal close with no scheduled-automation dependency; Gmail label BCP; Telegram alternate routing; aggressively reduce PC centrality and mobile-data use; fully use the old phone RAM/storage/always-on strengths; professional UI; BCPGO BCP fresh-chat takeover without re-teaching; zero-dollar/weak-PC/unstable-power-network as normal conditions; field truth outranks CI/UI optimism.

## Release rule

No Android, Windows or control-plane candidate may be called “the BCP product” unless its release manifest references this A+B+C revision and traceability matrix. A feature may be CI-proven while the product remains incomplete. Field promotion requires FIELD evidence, not compilation alone.

## Current measured maturity

Machine-readable authority: .project-memory/ABC_REQUIREMENTS_TRACEABILITY.json.
R76 baseline weighted A+B+C engineering maturity: 45.9%. A=46.3%, B=41.8%, C=52%. This deliberately discounts PARTIAL and CI-only work and is a planning metric, not a quality boast.

## Mandatory convergence
1. Make phone 2.2 a coherent full-node candidate, not a micro-release.
2. Close local transport encryption/pairing.
3. Expand EDGE_ONLY useful execution.
4. Replace the 8 GiB cache ceiling with dedicated-device adaptive storage.
5. Complete phone memory/index/recovery-replica behavior.
6. Qualify Telegram phone relay and provider receipts in field.
7. Replace the phone UI with the server-grade cockpit and visually audit it.
8. Run crash/power/network partition tests and fresh-conversation takeover.
9. Recompute A+B+C score from evidence after each integrated milestone.
