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


## U. AX15GO cross-project causal regression

Canonical mechanism source:
`.project-memory/AX15GO_CROSS_PROJECT_CAUSAL_LEDGER.json`.

These tests are causal obligations, not a scenario-counting certification. Candidate-source fixes remain candidate until their own project gates pass.

U1. A bounded operation contains one worker/wait that never completes.
Expected: every blocking primitive derives a timeout from the remaining monotonic deadline; the operation exits within declared deadline plus bounded scheduler tolerance.

U2. A permanent invariant is repaired, then a later reconstruction/version transform reintroduces the old value.
Expected: final-transform/final-artifact validation repairs or rejects the regression. Intermediate-source PASS cannot certify the published artifact.

U3. Critical publication reaches copy/replace/hash readback and power loss occurs before the platform-qualified durability boundary.
Expected: no `COMMITTED/DURABLE_LOCAL` claim before the required flush boundary. Linux and Windows durability semantics are qualified separately; noncritical telemetry is not burdened with blanket fsync.

U4. A sealed runtime has a known defect but only a future/vNext engineering primitive is improved.
Expected: deployed runtime status remains unchanged. Documentation/adapter/test changes cannot be reported as a deployed fix.

U5. A dedicated repository exists while its fence still says PLACEHOLDER/NOT_CANONICAL and another repository owns current source.
Expected: bootstrap/recovery resolves the declared canonical source and refuses to infer authority from repository existence.

U6. Discovery has a six-second outer deadline but is given hundreds or thousands of candidate endpoints.
Expected: both elapsed time and queued/in-flight work remain bounded; cancellation does not leave a large task/socket tail.

U7. The temporary CI cache containing the pinned Android signing identity expires after a long quiet period.
Expected: release fails closed with a recovery-required state; no replacement/new signing key is generated. In-place update continuity remains pending until a separately verified recovery copy is proven.

U8. The new artifact is durable; COMMITTED receipt crosses its atomic replace boundary; a later receipt durability/readback step errors.
Expected: the artifact is not blindly rolled back. System either completes bounded durability reconciliation or reports `COMMIT_OUTCOME_UNKNOWN`.

U9. Process/reboot interruption leaves source, published artifact and receipt in differing survival combinations.
Expected: side-effect-free reconciliation classifies exact identity before replay as `COMMITTED`, `NOT_COMMITTED`, `ARTIFACT_PRESENT_RECEIPT_MISSING`, `RECEIPT_PRESENT_ARTIFACT_MISMATCH`, `RECEIPT_UNREADABLE` or `CONFLICT`.

U10. A new dedicated repository is created before product-source migration.
Expected: mandatory repository-level agent/security/CI-budget bootstrap policy is already inherited; placeholder verifier rejects undeclared product files until explicit authority migration.

Promotion note:
- a PASS in U proves only the tested causal invariant;
- candidate PR evidence remains candidate until its source repository qualifies/merges it;
- none of U upgrades B-EDGE/BCP runtime or field certification by itself.


## V. AX15GO R4 gray-failure health vector

Canonical contract:
`.project-memory/AX15GO_GRAY_HEALTH_R4.json`.

These are anti-false-green obligations. They do not promote the current runtime merely because the document exists.

V1. `/health` returns process/HTTP liveness while an authenticated project command fails.
Expected: liveness dimension may be PASS; `AUTHENTICATED_COMMAND_PATH_USABLE` fails and aggregate state is not END_TO_END_HEALTHY.

V2. Home LAN remains usable while Internet/Nexus is unavailable.
Expected: local BCP core stays usable; remote ingress is DEGRADED/OFFLINE independently. No false global DEAD state.

V3. Heartbeat/process is fresh while SQLite canonical authority cannot acquire a writer transaction.
Expected: `SQLITE_AUTHORITY_WRITABLE=FAIL`; mutation admission is HOLD/DEGRADED and no green aggregate is emitted.

V4. Telegram cockpit replies successfully while coordinator epoch/fence is stale.
Expected: cockpit health cannot authorize a canonical mutation; stale fence is rejected.

V5. Process and network are alive while project revision/context evidence is stale.
Expected: `PROJECT_REVISION_FRESH=STALE`; resolver refreshes or HOLDs before mutation.

V6. Nexus `/health` is green while B-EDGE is offline.
Expected: remote ingress may queue/receive only according to its durable contract; no claim of local execution or DONE.

V7. B-EDGE is paired and LAN-reachable but the authenticated command plane stalls.
Expected: pairing/liveness remain distinct from command usability; no END_TO_END_HEALTHY.

V8. Wi-Fi association and DNS resolution succeed while one HTTPS dependency is blackholed.
Expected: only that route/circuit is degraded; retries are bounded and local work remains nonblocking.

V9. All fast liveness signals are green but server generation/identity differs from the pinned release.
Expected: identity dimension fails closed; health aggregate is CONFLICT/HOLD, not healthy.

V10. Health probes themselves are invoked repeatedly during a degraded network period.
Expected: probes remain bounded, side-effect-free where feasible, do not become a polling storm, and do not enter the per-turn fast path.

Promotion note:
- current BCP 0.6.4 payload is intentionally unchanged by R4;
- runtime closure requires a coordinated next release with exact hash/version/Android compatibility gates;
- this avoids a same-version payload mutation while still making the gray-health defect and regression obligations canonical.


## W. Field regression — offsite return + reboot + Windows firewall recovery

W1. B-EDGE leaves the trusted home LAN, accumulates failed reconnect attempts, then later rejoins the same Wi-Fi while the paired PC has rebooted.
Expected: the app does not require re-pairing, manual IP, token entry, or repeated taps. Saved pairing identity remains authoritative; discovery/reconnect resumes automatically with bounded retries.

W2. After PC reboot/unlock, Windows presents an inbound firewall consent for the Python-hosted BCP listener.
Expected: BCP requires only Private/Domain + LocalSubnet access on TCP 8765. Public-network access is not required and must not be the default recovery path.

W3. B-EDGE is on the same LAN and reports PC_NOT_FOUND while the PC-side Python listener is blocked by Windows Firewall.
Expected: diagnostics distinguish generic PC_NOT_FOUND from WINDOWS_FIREWALL_BLOCK_SUSPECTED when corroborating evidence exists. The user must not be asked to infer the network cause from repeated failed taps.

W4. The user taps CONNECTER AUTOMATIQUEMENT repeatedly while the PC is unavailable.
Expected: taps coalesce into one bounded discovery/reconnect transaction; no thread/socket storm, battery drain, duplicate pairing, or unbounded /24 scans.

W5. Firewall access becomes available after an initial PC_NOT_FOUND.
Expected: one subsequent automatic or explicit reconnect reaches the already-paired PC, flushes queued phone telemetry, and continues the same project revision without reinstallation.

W6. PC network category is Public after reconnect to the home Wi-Fi.
Expected: BCP does not silently broaden exposure. Recovery either restores the trusted Private profile or reports a precise NETWORK_PROFILE_NOT_TRUSTED / FIREWALL gate.

W7. The PC reboots under >90% RAM pressure and high thermal load.
Expected: BCP/ChatGPT-PC recovery remains foreground-friendly, low-concurrency, bounded-memory, and avoids simultaneous heavy restart/update/discovery work.

Field origin:
- 2026-09-20 real user test after leaving home with the B-EDGE phone, returning to the home Wi-Fi, rebooting/unlocking the PC, observing B-EDGE PC_NOT_FOUND and a Windows Security prompt for Python inbound network access.
- This is now a permanent regression vector, not a one-off support incident.


W8. Recovery target is ACTIVE in cloud Drive but the PC-local DriveFS copy is missing/stale/inactive after reboot.
Expected: B-EDGE recovery does not report a generic HTTP_500. BCP starts the bounded local recovery-launcher bridge, explicitly reports bridge-vs-release-install truth, and waits for the normal hash-pinned target/package path to converge.

W9. ChatGPTPC_RecoveryPlane.vbs is valid VBScript text encoded as UTF-8 with BOM and Windows Script Host returns 800A0408 at line 1 character 1.
Expected: bridge reconstructs only the known launcher as UTF-16, readbacks exact content/hash, starts the existing recovery runner, and records no privilege/network expansion.

W10. A recovery receipt is mirrored to a provider-synchronised DriveFS path whose temporary-file/os.replace semantics reject the local atomic-write primitive.
Expected: local canonical recovery evidence is preserved; cloud mirror becomes HOLD/deferred; local recovery must not roll back solely because the provider mirror rejected atomic replace.

W11. Cloudflare classic browser OAuth callback reaches localhost after the callback listener has exited while a separate device-authorization page is/was present.
Expected: localhost failure and device-flow state remain distinct. No auth success is claimed until provider-authenticated whoami/readback succeeds.


## X. R40 zero-touch re-entry / provider-mirror / auth regressions

X1. Drive for desktop is stopped or its streamed virtual drive is unavailable while local BCP remains healthy.
Expected: local recovery/watchdog truth continues; Drive becomes CLOUD_MIRROR_HOLD, never the sole reason to fail a local transaction.

X2. Drive heartbeat is stale but a paired B-EDGE obtains a newer authenticated /health readback from the same PC.
Expected: the fresh LAN machine readback is current field truth; the stale Drive sample remains historical evidence and is never allowed to downgrade the newer observation.

X3. Wrangler device authorization is started and the human does not approve within the bounded code window.
Expected: HUMAN_AUTH_REQUIRED / CLOUDFLARE_DEVICE_AUTH_REQUIRED_OR_EXPIRED. No automatic classic `wrangler login`, no localhost:8976 callback, no token-copy instruction.

X4. A later explicit Nexus retry follows X3.
Expected: generate a fresh device code and require authenticated whoami readback before deployment; never reuse the stale device code.

X5. B-EDGE leaves home Wi-Fi and later regains Wi-Fi while its process is alive.
Expected: one unique one-shot reconciliation is requested on network availability and duplicate triggers coalesce; no scan/retry storm.

X6. B-EDGE process is absent during Wi-Fi return.
Expected: WorkManager periodic recovery remains bounded at the 15-minute minimum interval; no illegal faster periodic schedule is introduced.

X7. Source code changes after a signed APK version was distributed.
Expected: CI forbids silently reusing the distributed version/artifact metadata; next publication requires a new versionCode/versionName and verified same-certificate signed artifact.

X8. PC RAM stays above 90% during recovery.
Expected: one heavy recovery/update lane at a time, bounded telemetry/queues, no duplicate extraction/build/restart storm, and foreground user work retains priority.


W12. Recovery target contains a fixed runner while the installed recovery runner is older/defective.
Expected: after package SHA verification, BCP stages the exact target-bundled payload/tools/recovery_update_runner.py, validates exact member count/size/UTF-8/syntax, readbacks and hashes the staged runner, and launches that runner. The stale installed runner is not bootstrap authority.

W13. Target package runner is missing, duplicated, oversized, invalid UTF-8, syntax-invalid, or violates the sequence-specific DriveFS fail-open contract.
Expected: recovery HOLD/reject before launch; no fallback to an older installed runner and no false target-install claim.

W14. Target-bundled runner is staged successfully.
Expected: machine-readable receipt records target version/sequence, target package SHA-256, staged runner SHA-256, local path, and provenance HASH_VERIFIED_TARGET_PACKAGE with no privilege expansion.
