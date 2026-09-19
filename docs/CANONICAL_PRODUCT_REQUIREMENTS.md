# API / BCP — Cahier des charges canonique courant

Status: CANONICAL PRODUCT REQUIREMENT
Revision: 2026-09-19-R2
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

Current target: BCP 0.4.7.

BCP 0.4.7 keeps the 0.4.6 field-proof guarantees and adds an authenticated local B-EDGE update relay backed by the canonical Drive installer folder. The server recomputes the APK SHA-256 before exposing release metadata or bytes.

Promotion gate:
- CI qualification PASS;
- Windows installer/selftest PASS;
- existing managed-update path consumes 0.4.7;
- `BCP_RUNTIME_LATEST.json` appears in synced Drive;
- its timestamp/version/hash prove a live 0.4.7 runtime;
- B-EDGE telemetry/readback follows.

No blind reinstall is allowed merely because telemetry is missing.

## P1 — Provider/model broker and autonomous loops

After P0 continuity is field-proven:
- add a provider-neutral Model Broker;
- support legitimate free/zero-cost/BYOK providers as replaceable adapters;
- make quota/capacity/cost explicit and field-measured from Kinshasa before ACTIVE promotion;
- never silently spend money; `DEFAULT_PAID_SPEND = 0 USD` is a hard invariant;
- use bounded autonomous loops with deterministic verification;
- integrate GitHub/BuildHub/B-EDGE jobs through receipts;
- add Telegram or equivalent low-bandwidth cockpit for status, approvals and alerts;
- optimize for 24-hour endurance rather than maximum instantaneous LLM throughput;
- preserve strategic provider capacity for incidents and user-facing work later in the day;
- continue useful deterministic/local work even when all free LLM capacity is exhausted.

### P1 — Mandatory 24-hour AI endurance policy

A "continuous chantier" means continuous useful progress, not continuous prompting.

All work escalates through this ladder:
`EVENT_ENGINE -> RULE_ENGINE -> KNOWLEDGE_CACHE/ERROR_LEDGER -> LOW_COST_MODEL -> REASONING_MODEL -> HUMAN/CHATGPT`.

A higher layer is used only when lower layers cannot safely resolve the task.

The following are local/deterministic by default and MUST NOT consume LLM quota merely because a model is available: heartbeat, telemetry, synchronization, hashes, build invocation, test execution, retries/backoff, queue/outbox replay, known-error repair, checkpointing, resource observation and routine notifications.

Before any model call, BCP MUST batch, deduplicate, causal-group and resolve known events locally. One event MUST NOT imply one LLM call. Offline event backlogs are compacted before model escalation.

For every ACTIVE_FREE_PROVIDER, BCP MUST maintain observed capacity, reset window, recent 429/errors, latency, success history and task fit. Marketing quotas are not operational truth; real account/API telemetry is.

Initial conservative allocation after field validation:
- <= ~50% of measured free capacity for planned/background work;
- ~25% for fallbacks and user-impacting incidents;
- ~25% protected strategic reserve.

These are bootstrap scheduling ratios, not vendor facts, and may adapt after telemetry while preserving a non-zero reserve.

Every provider has a `SOFT_LIMIT`, `RESERVE_FLOOR` and `HARD_LIMIT`. Crossing the soft limit increases routing cost; background work cannot cross the reserve floor; the hard limit prevents accidental exhaustion or paid use.

When free capacity becomes constrained, BCP enters `AI_CONSERVATION_MODE`: it continues tests, fuzzing, static analysis, dependency checks, benchmarks, log processing, backups, deterministic AX150K exploration and known-error remediation while sharply reducing model calls. If no compliant free model remains, only LLM-dependent work enters `FREE_MODEL_CAPACITY_HOLD`.

Parallel projects share one global AI budget. Background work may never monopolize all provider capacity. User-impacting or integrity/recovery incidents may preempt a background chantier after checkpoint.

The normal reasoning path uses one provider. Multi-model fan-out is forbidden by default; cross-checking is allowed only for bounded reasons such as low confidence, contradictory diagnoses, high-impact architecture, failed first attempt or an explicit audit step.

Every model call MUST pass a call-admission circuit breaker that rejects/defer/reroutes duplicate, cached, unnecessary, unhealthy, over-budget, non-free, reserve-violating or retry-loop calls.

Logical agents are provider-neutral. Providers are interchangeable execution engines selected by measured capability, reliability, latency and remaining free capacity, not hard-coded brand identity.

Telegram/UI SHOULD expose a compact `AI_CAPACITY` abstraction (daily state, emergency reserve, long-window capacity, provider health, calls avoided, spend) while provider-specific quota units remain diagnostic detail. Silence means normal operation; routine healthy heartbeats must not spam the user.

Required optimization KPIs include deterministic-operations count, LLM calls by provider/project/task, calls avoided by cache/rules/deduplication, quota consumption, 429/error rate, non-LLM incident resolution rate, time-to-recovery, reserve state and the invariant `SPEND_USD = 0.00`.

Canonical detailed policy: `docs/FREE_API_MODEL_BROKER_AUTONOMY_REQUIREMENTS.md`.
Machine-readable provider plan: `.project-memory/AI_PROVIDER_PLAN_RDC.json`.

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


## P0 — B-EDGE Evergreen distribution

The canonical Android line is B-EDGE Evergreen.

Requirements:
- stable package identity and stable Android signing certificate;
- private signing key MUST remain outside public GitHub;
- public GitHub receives only non-secret certificate fingerprint/release metadata and must qualify source/unsigned APK before signing;
- signed APK promotion to `API_BCP/00_A_INSTALLER/BCP_EDGE_CURRENT.apk` happens only after all Android CI gates pass;
- B-EDGE downloads future updates through the authenticated local BCP relay, not from an unauthenticated arbitrary URL;
- update manifest package ID, version, APK SHA-256 and signing-certificate SHA-256 are verified before installation;
- APK payload lives in app-owned cache and is cleaned after a verified successful update;
- normal micro-patch flow is one tap in B-EDGE plus the Android installation confirmation required by the OS;
- update failures never destroy pairing or canonical project state;
- the first transition from the legacy debug-signed 0.2.5 line may use a one-time side-by-side Evergreen package because the old ephemeral signing key cannot be recovered safely;
- subsequent Evergreen versions MUST update in place without uninstall/reinstall cycles.
