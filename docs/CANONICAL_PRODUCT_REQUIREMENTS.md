# API / BCP — Cahier des charges canonique courant

Status: CANONICAL PRODUCT REQUIREMENT
Revision: 2026-09-19-R1
Supersedes: fragmented requirements only as an index; underlying detailed requirement files remain authoritative.

## Mission

API/BCP is the personal digital control and continuity plane for the user's own devices, accounts, repositories, local network, builds and controlled test environments.

The immediate objective is not more architecture. It is to make the Windows + BCP + B-EDGE chain operate in the field with automatic recovery and machine-readable evidence.

## P0 — Windows/field bring-up

The Windows side MUST:
- run as a lightweight managed application on the existing ChatGPT-PC substrate; no heavy local LLM and no unnecessary parallel daemon;
- install/update idempotently with hash verification, readback and rollback;
- survive restart/logon/power/network interruption without losing canonical state; the minimal per-user lifecycle launcher may restart the same managed BCP process, but must not create a second control plane;
- self-update only from allowlisted, hash-pinned release metadata;
- expose health, version, PID, update state, recovery state and bounded diagnostics in machine-readable form;
- publish a sanitized heartbeat independently of the interactive ChatGPT-PC channel;
- never require routine manual IP/token/project entry;
- never require repeated reinstall cycles for normal upgrades or recovery;
- clean its own known temporary/download artifacts automatically after a verified successful install/update, while preserving failure evidence and never deleting unrelated user files;
- remain bounded under high memory pressure on the ~4 GB Windows target;
- fail closed / HOLD on ambiguous state rather than claim ACTIVE.

Current external heartbeat contract:
- canonical filename: `BCP_RUNTIME_LATEST.json`;
- rolling event log: `BCP_RUNTIME_EVENTS.jsonl`;
- preferred synced location: `API_BCP/02_TELEMETRY/BCP/`;
- compatibility fallback while field migration is incomplete: `CHATGPT_PC_AGENT/03_TELEMETRY/BCP/`;
- heartbeat cadence target: <= 60 s while runtime is alive;
- no bearer tokens, secrets or raw arbitrary payloads in the external heartbeat.

## P0 — User friction

The user MUST NOT be the telemetry or integration bus.

Normal operation must not require:
- screenshots for routine diagnostics;
- copying logs between phone/PC/chat;
- retyping IPs/tokens/project IDs;
- downloading successive installer revisions manually;
- repeating project context after a conversation interruption;
- manually relaying prompts/results between model providers.

User interaction should be limited to unavoidable physical approval, security consent, or irreversible-action approval.

## P0 — Durable continuity

Canonical project state lives outside chat.

Every mutation requires:
- revision precondition;
- idempotency key;
- bounded operation contract;
- receipt/readback;
- durable checkpoint;
- single-writer/fencing semantics where multiple conversations can participate.

Conversation/platform/network interruption is nonterminal. Resume from the next uncommitted action; never replay a committed mutation.

## P0 — B-EDGE / phone

B-EDGE MUST:
- discover the PC automatically on trusted LAN/hotspot where feasible;
- pair without normal manual IP/token entry;
- send lightweight telemetry;
- receive compact status/recovery state;
- continue/recover across intermittent connectivity;
- use app-owned cache for future in-app update payloads and delete those payloads after verified installation; do not request broad storage access merely to clean arbitrary Downloads;
- support a later fallback path (QR/Bluetooth or equivalent) only if measured LAN discovery failure justifies it.

## P0 — Environment constraints

Design assumptions:
- unstable mains power and Internet are normal;
- low bandwidth and temporary offline periods are normal;
- Windows memory pressure can be very high;
- battery use on phone and PC matters;
- DEFAULT_PAID_SPEND = 0 USD.

Therefore use:
- lightweight JSON state/receipts;
- durable local queues/outbox;
- bounded retries/backoff;
- bounded concurrency;
- cache/reuse;
- no heavyweight always-on services unless measured evidence requires them.

## P0 — Proof rules

`MODEL != PORTABLE != CLOUD != NATIVE != FIELD`.

No component is FIELD_VERIFIED or ACTIVE until fresh native/field evidence exists.

A valid Windows field promotion requires at minimum:
1. exact runtime version readback;
2. fresh heartbeat within the expected cadence;
3. successful health/diagnostics readback;
4. update/rollback state coherent;
5. no missing/hash-error payload evidence;
6. restart/recovery proof;
7. no duplicate canonical mutation.

## P0 — Current release objective

Current target: BCP 0.4.6.

BCP 0.4.6 keeps the 0.4.5 revision-precondition/stale-writer guarantees and adds native managed-runtime proof in authenticated diagnostics: server PID, exact server path, SHA-256 and lifecycle registration. Process CommandLine visibility is not an acceptance oracle.

Promotion gate:
- CI qualification PASS;
- Windows installer/selftest PASS;
- existing managed-update path consumes 0.4.6;
- `BCP_RUNTIME_LATEST.json` appears in synced Drive;
- its timestamp/version/hash prove a live 0.4.6 runtime;
- B-EDGE telemetry/readback follows.

No blind reinstall is allowed merely because telemetry is missing.

## P1 — Provider/model broker and autonomous loops

After P0 continuity is field-proven:
- add a provider-neutral Model Broker;
- support legitimate free/zero-cost/BYOK providers as replaceable adapters;
- make quota/capacity/cost explicit;
- never silently spend money;
- use bounded autonomous loops with deterministic verification;
- integrate GitHub/BuildHub/B-EDGE jobs through receipts;
- add Telegram or equivalent low-bandwidth cockpit for status, approvals and alerts.

These extensions must not displace the P0 field bring-up.

## Acceptance sequence

The project is not considered operationally complete until this sequence passes:
1. Windows BCP runtime proves current version via external heartbeat.
2. B-EDGE discovers/pairs and produces telemetry.
3. Checkpoint commit succeeds.
4. Windows/runtime or network is interrupted.
5. Same committed revision is recovered without replay.
6. Fresh conversation recovers exact state without user reconstruction.
7. Stale writer mutation is rejected.
8. Resource-pressure and poor-connectivity tests remain bounded.


## Acceptance execution policy

Final acceptance MUST be batched rather than performed as a sequence of manual user tests.

The canonical field campaign is `BCP_FINAL_ACCEPTANCE_CURRENT` and must:
- update BCP to the current qualified target if needed;
- create one checkpoint with an explicit revision precondition;
- replay the same idempotency key and prove no duplicate revision is created;
- submit a stale-revision mutation and prove it is rejected;
- verify loopback and LAN health;
- snapshot pairing/token/committed revision;
- schedule one automatic Windows reboot and resume through RunOnce;
- prove the same pairing/token and committed revision/hash survive reboot without replay;
- prove the managed BCP listener/lifecycle returns;
- run bounded resource-pressure and poor-connectivity probes;
- publish one machine-readable `BCP_FINAL_ACCEPTANCE_LATEST.json` receipt;
- clean only its own known downloaded/extracted acceptance artifacts after success.

The user must not be required to return between individual gates. One launch may cover the device/runtime acceptance campaign. A brand-new ChatGPT conversation is a platform boundary and may be spot-checked separately because the local PC harness cannot instantiate a new ChatGPT conversation itself.


### Downloads hygiene

Known legacy BCP artifacts in the Windows Downloads folder are deleted by exact allowlisted names at the beginning of the final acceptance campaign. The currently-running acceptance package is preserved until the campaign succeeds, then its own downloaded/extracted files are removed. Unrelated user files are never matched by the cleanup rule.


### Publication gate

A Drive `CURRENT` artifact MUST NOT be replaced by an unqualified build. Publication requires all applicable public GitHub CI gates to pass first: syntax/parse, self-test, internal object-contract checks, version/manifest cross-checks, server self-test and package creation. Failed/cancelled builds remain diagnostic evidence only and are never promoted to `API_BCP/00_A_INSTALLER`.
