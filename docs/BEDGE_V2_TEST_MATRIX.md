# B-EDGE V2 — Verification and Failure-Injection Matrix

Status: TEST REQUIREMENT
Adopted: 2026-09-19
Parent architecture: docs/BEDGE_RUNTIME_V2_HARDENING.md

## Test philosophy

A design claim is not promoted by documentation alone.

Evidence classes:
- STATIC — schema/lint/property inspection;
- UNIT — deterministic local unit test;
- INTEGRATION — Android/PC/API components together;
- DEVICE — real Android device execution;
- FIELD — real Kinshasa network/power/account path;
- FAILURE_INJECTION — forced interruption/partition/resource failure.

All critical state transitions require machine-readable receipts.

## A. Android lifecycle survival

A1. Kill B-EDGE process during IDLE.
Expected: no canonical loss; next start reconstructs state.

A2. Kill process after job persisted but before execution.
Expected: job remains runnable exactly once in canonical effect terms.

A3. Kill process during remote call after provider accepted request but before local receipt.
Expected: uncertain attempt reconciles without duplicate mutation.

A4. Kill process after effect but before local DONE state.
Expected: idempotency/readback identifies already-applied effect.

A5. Reboot phone with queued jobs/outbox.
Expected: reconciliation resumes via supported Android background primitives; no permanent-service assumption.

A6. Force WorkManager duplicate enqueue.
Expected: unique work/idempotency suppresses duplicate effect.

## B. Power/battery/thermal

B1. Enter power-save mode during BACKGROUND_IMPROVEMENT.
Expected: noncritical work throttles/defers.

B2. Battery-low while uncharged.
Expected: EDGE_R2 maintenance deferred; critical lightweight operations remain possible.

B3. Thermal status escalates.
Expected: cache/CPU/network-intensive background work backs off.

B4. Device charging and thermally healthy.
Expected: deferred compaction/index work may run.

B5. Prolonged device idle/Doze.
Expected: system accepts delayed background execution; no false failure alarm solely due to scheduler delay.

## C. Memory pressure

C1. Trigger onTrimMemory levels / app background pressure.
Expected: HOT cache shrinks before durable state.

C2. Process killed after cache eviction.
Expected: database reconstructs required state.

C3. Large multi-project memory corpus.
Expected: bounded RAM; FTS/search returns correct scoped results.

C4. Cache poisoning/stale cache.
Expected: source revision mismatch invalidates Context Pack/cache.

## D. Database integrity

D1. Power/process kill during transaction.
Expected: atomic prior/new transaction state; no partial canonical mutation.

D2. Schema migration upgrade.
Expected: migration preserves project/job/receipt counts and invariants.

D3. Duplicate idempotency key.
Expected: unique constraint returns prior receipt / ALREADY_COMMITTED equivalent.

D4. Corrupt derived index/cache.
Expected: rebuildable from authoritative rows.

D5. Corrupt primary DB.
Expected: fail closed; preserve evidence; restore from latest verified local/synced backup path, never fabricate state.

## E. Multi-project isolation

E1. Concurrent PhoneMouse + BCP + Browser4G jobs.
Expected: no cross-project state leakage.

E2. Same error signature in two projects.
Expected: reusable technical recipe may be shared, project-specific state remains isolated.

E3. Context Pack for project A.
Expected: excludes irrelevant confidential project B content unless explicitly cross-project policy allows it.

E4. One project monopolizes provider quota.
Expected: global fairness/reserve prevents starvation.

## F. Agent loop controls

F1. Agent requests another agent recursively.
Expected: orchestrator enforces max depth/permission.

F2. Agent repeats same failed action.
Expected: no-new-evidence/retry breaker stops loop.

F3. Two agents propose conflicting mutations.
Expected: deterministic revision/fencing gate serializes or rejects stale proposal.

F4. Model proposes a memory fact without evidence.
Expected: stored only as MODEL_PROPOSED or rejected, never silently promoted.

F5. Model output claims test PASS without machine receipt.
Expected: status remains unverified.

## G. PC dispatch and partition

G1. PC disappears before accepting job.
Expected: job returns to WAITING_FOR_PC/READY after bounded lease expiry.

G2. PC accepts, executes, B-EDGE disappears.
Expected: PC stores receipt; does not independently advance V2 global PROJECT_HEAD.

G3. Network partition; both nodes alive.
Expected: only valid fenced coordinator can commit head.

G4. Delayed command from old coordinator epoch arrives.
Expected: PC rejects as STALE_FENCE.

G5. Duplicate receipt after reconnect.
Expected: deduplicated by action/idempotency identity.

G6. User explicitly promotes PC during B-EDGE device failure.
Expected: requires explicit promotion/witness semantics and epoch change; old B-EDGE cannot later overwrite new head.

## H. Discovery and local network

H1. NSD discovery on normal trusted LAN.
Expected: finds PC without /24 scan.

H2. DHCP address changes.
Expected: reconnect via identity/service discovery.

H3. NSD unavailable.
Expected: QR or bounded diagnostic fallback.

H4. Raw scan fallback invoked.
Expected: strict timeout/concurrency; never recurring background behavior.

H5. Android 17 local-network permission denied.
Expected: clear UX / system-picker path / HOLD; no misleading PC_OFFLINE diagnosis.

## I. Pairing/transport security

I1. First pairing identity confirmation.
Expected: fingerprint/key bound to trusted PC identity.

I2. LAN attacker responds first to discovery.
Expected: cannot silently obtain trusted identity/credential.

I3. Replay old pairing nonce.
Expected: rejected.

I4. Certificate/key changes unexpectedly.
Expected: connection HOLD + explicit re-trust workflow.

I5. Packet inspection production mode.
Expected: no bearer/provider key visible in cleartext.

I6. Telemetry/export scan.
Expected: no bearer/provider secrets.

## J. Provider budget / zero-dollar

J1. Provider 429.
Expected: update health, bounded backoff, reroute if allowed.

J2. Provider quota nearly depleted.
Expected: SOFT_LIMIT raises routing cost.

J3. Background task would cross RESERVE_FLOOR.
Expected: defer.

J4. All free providers exhausted.
Expected: FREE_MODEL_CAPACITY_HOLD for semantic work; deterministic work continues.

J5. Paid fallback offered by provider.
Expected: reject; no billing auto-enable.

J6. Runaway agent tries repeated calls.
Expected: call-admission gate blocks by duplicate/retry/budget controls.

J7. Quota reset.
Expected: capacity recovers only after verified reset/response, not assumed clock alone.

## K. Context/memory quality

K1. User preference pinned.
Expected: included in relevant project Context Packs.

K2. Preference superseded by user.
Expected: new value wins; old item retained/superseded for history, not selected.

K3. Machine fact becomes stale.
Expected: freshness policy excludes or flags it.

K4. Contradictory evidence.
Expected: memory item marked conflicted; no silent overwrite.

K5. Oversized history.
Expected: Context Pack stays within budget by retrieval/ranking, not truncating critical invariants.

K6. Same Context Pack source revision.
Expected: reproducible hash.

## L. Telegram terminal

L1. Same Telegram update delivered twice.
Expected: one durable mission.

L2. B-EDGE offline but cloud ingress active.
Expected: command durably queued; acknowledgement does not falsely claim execution.

L3. No cloud ingress and device sleeps > scheduler cadence.
Expected: delayed command processing is reported honestly; no 24/7 instant guarantee.

L4. FCM wake hint duplicated/lost.
Expected: durable queue reconciliation remains authoritative.

L5. Telegram unavailable.
Expected: BCP continues; cockpit is optional adapter.

## M. Offline/poor-connectivity replay

M1. Thousands of telemetry events offline.
Expected: local compaction/dedup; no one-event-one-LLM behavior.

M2. Internet returns intermittently.
Expected: bounded batches and exponential backoff.

M3. PC and Internet both unavailable.
Expected: EDGE_ONLY preserves memory, planning and eligible local work.

M4. Network changes Wi-Fi <-> hotspot.
Expected: node identity survives endpoint changes.

## N. Acceptance metrics

Record:
- RAM baseline/p95 under EDGE_ONLY and PC_AVAILABLE;
- wakeups/hour;
- CPU time/hour;
- battery drain/hour unplugged;
- thermal throttling events;
- DB size/growth per day;
- outbox depth/recovery time;
- duplicate effects = 0;
- split-brain head divergence = 0;
- LLM calls/day and calls avoided;
- provider reserve remaining;
- deterministic incident resolution ratio;
- Context Pack median/p95 size;
- time from PC return to queued-job resume;
- SPEND_USD = 0.00.

## Promotion rule

B-EDGE V2 remains DESIGN_HARDENED / RUNTIME_UNVERIFIED until the automated suite and real-device campaign cover the applicable sections above.

No individual PASS may substitute for an untested process-death, reboot, partition, memory-pressure, transport-security or zero-dollar invariant.


## O. Replica / backup / phone-loss recovery

O1. B-EDGE writes canonical revision; PC online.
Expected: PC replica reaches same revision/hash and emits readback receipt.

O2. B-EDGE writes while PC offline, then PC reconnects.
Expected: ordered/idempotent catch-up; no duplicate effects.

O3. Generate cold backup while DB is live.
Expected: consistent snapshot/export with schema/revision/hash; never an unsafe partial raw copy.

O4. Inspect cold backup payload.
Expected: provider keys, bearer tokens and device secrets absent; private memory encrypted when configured.

O5. Destroy/uninstall/reset B-EDGE in test environment after verified backup.
Expected: PC/backup recovery procedure can reconstruct latest qualified state.

O6. Promote replacement coordinator after old phone loss.
Expected: new epoch fences old phone; stale old phone cannot commit when it reappears.

O7. Corrupt newest backup.
Expected: validation rejects it and uses prior verified snapshot; no silent restore from corrupt data.

O8. Rotate recovery/data encryption key.
Expected: new snapshots use new key version; retained recovery procedure for allowed older snapshots remains deterministic.

## P. Event retention / compaction

P1. Generate repetitive healthy heartbeat flood.
Expected: compaction removes/reduces noise without affecting project state.

P2. Generate security/fencing/canonical mutation events.
Expected: retention policy never discards required audit evidence.

P3. Delete/rebuild Context Pack cache.
Expected: regenerated packs from same source revision preserve deterministic critical content/hash policy.

## Q. Remote command latency tiers

Q1. Push/cloud ingress says RECEIVED while B-EDGE is offline.
Expected: user sees QUEUED/RECEIVED, never false DONE.

Q2. Delayed Telegram update delivered after local state changed.
Expected: update ID dedup + mission preconditions prevent stale duplicated action.

Q3. FCM wake hint lost.
Expected: periodic/cloud reconciliation eventually finds durable command; push is never authoritative.

Q4. Cloud ingress quota exhausted/unavailable.
Expected: local BCP continues; ingress marked degraded; no paid upgrade.


## R. Universal Context Fabric / BCPGO

R1. Fresh ChatGPT conversation sends only `BCPGO` with connected context source available.
Expected: GLOBAL_CORE + inferred PROJECT_CORE recovered without user reconstruction or broad repository scan.

R2. Fresh conversation sends `BCPGO <project>`.
Expected: explicit project wins over weak auto-detection and only that project's context is selected.

R3. Same global/project revision is requested on next turn.
Expected: resolver returns `UNCHANGED` or equivalent tiny no-change response; no full Context Pack retransmission.

R4. One user preference changes after conversation bootstrap.
Expected: next resolution returns bounded `DELTA`; new preference supersedes old value deterministically.

R5. Project revision changes while conversation remains open.
Expected: stale context is detected by revision vector; delta/full refresh occurs before mutation.

R6. Remote bootstrap projection hash is corrupted.
Expected: reject projection; use prior verified projection or HOLD; never silently trust corrupted context.

R7. Remote projection is old but internally valid.
Expected: mark `DEGRADED/STALE`; do not claim current field state.

R8. Ambiguous project auto-detection.
Expected: no cross-project memory merge; return minimal global context plus project candidates/HOLD instead of leaking unrelated project state.

R9. BCPGO path has no authorized connector/source.
Expected: report integration unavailable; command text is not treated as authentication or magical connectivity.

R10. Normal warm bootstrap.
Expected: no LLM call required; BCP-side manifest p95 target <= 1 s and global+project resolution p95 target <= 2 s after projections are prebuilt.

R11. Context Pack exceeds 32 KiB target.
Expected: retain critical pinned policies/state, move evidence/history to on-demand references, record oversize metric; never truncate critical invariants first.

R12. Context Pack source revision repeats.
Expected: stable reproducible source revision/hash policy.

## S. Memory authority / poisoning / privacy

S1. User explicitly sets a durable preference.
Expected: stored as normative user memory with user provenance and included where relevant.

S2. User explicitly replaces that preference.
Expected: new item supersedes old; old remains historical but is not selected.

S3. Retrieved webpage says to change a user preference/system rule.
Expected: content remains `UNTRUSTED_CONTENT`; cannot write USER_MEMORY/POLICY.

S4. Model output claims a new architectural fact without evidence.
Expected: `MODEL_PROPOSED` only or reject; cannot overwrite verified canonical state.

S5. Machine receipt contradicts a derived summary.
Expected: receipt wins; summary invalidated/rebuilt.

S6. Prompt-injection string is embedded in Git/Drive/RAG content.
Expected: it is delimited/treated as data; tool/policy scope unchanged.

S7. Retrieval query for project A overlaps semantically with confidential project B.
Expected: project scope filter blocks B unless explicit cross-project technical-knowledge policy permits a sanitized reusable recipe.

S8. Privacy extraction/adversarial query asks for unrelated stored memory.
Expected: least-privilege context scope prevents disclosure.

S9. History grows large.
Expected: topic segmentation + FTS/metadata retrieval keeps Context Pack bounded; selective forgetting/compaction preserves canonical receipts and pinned decisions.

## T. Three-node BCP NEXUS continuity

T1. B-EDGE online, PC online, NEXUS online.
Expected: one coordinator epoch/head; PC is fenced worker; NEXUS projection matches verified current revision.

T2. NEXUS offline.
Expected: B-EDGE/PC local operation continues; remote ChatGPT/Telegram ingress marked degraded; no paid failover.

T3. PC offline.
Expected: B-EDGE context/memory/scheduler remain operational; heavy jobs become WAITING_FOR_PC.

T4. B-EDGE offline, PC and NEXUS online.
Expected: PC does not silently advance global head without valid promotion/witness semantics; NEXUS exposes last verified context and queued commands only.

T5. Pairwise network partition creates delayed old command.
Expected: coordinator epoch/fencing rejects stale command.

T6. All three reconnect after partition.
Expected: receipts reconcile idempotently; one canonical head; no duplicated external effect.

T7. NEXUS free-tier quota exhausted.
Expected: remote facade degrades/fails closed; local BCP remains operational; no billing enablement.

T8. Drive bootstrap mirror and NEXUS disagree.
Expected: compare revision/hash/authority; newest cannot automatically win if integrity/fencing evidence conflicts; HOLD and reconcile.

T9. Raw SQLite/WAL file is presented as cross-device replica.
Expected: reject as unsupported replication mechanism; require logical snapshot/event replication.
