# BCP / B-EDGE Deep Audit Ledger — 2026-09-19

Status: ACTIVE AUDIT
Branch: `work/bcp/audit-hardening-20260919`
Base integration line: BCP 0.6.0 / B-EDGE 2.0.0-rc1
Rule: green compilation is not sufficient evidence of correct orchestration semantics.

## Executive state

The V2 candidate has materially improved durability (Room, WorkManager, memory evidence, multi-project registry, queue state), but it is not yet an autonomous executor.

Current high-level classification:
- durable edge memory: PARTIAL / CI-qualified, device-failure qualification pending;
- queue durability: HARDENED, terminal executor pending;
- PC autonomous execution: NOT IMPLEMENTED / contract defined;
- offline B-EDGE reconciliation: HARDENED in audit branch, device test pending;
- memory integrity: HARDENED against evidence downgrade, category model pending;
- production LAN transport: NOT READY; current cleartext path remains POC compatibility;
- V2 authority migration: NOT READY;
- zero-dollar AI broker runtime: SPECIFIED, provider field qualification/runtime adapter pending.

## Findings

### A-001 — REMOTE_QUEUED tracking black hole
Severity: CRITICAL
Status: FIXED_IN_AUDIT_BRANCH

Finding:
B-EDGE counted `REMOTE_QUEUED` jobs globally but `pendingJobs(project)` did not select them. After a queue acknowledgement, the job could disappear from reconciliation while still being non-terminal.

Fix:
- include `REMOTE_QUEUED` in durable pending query;
- retain until terminal evidence exists.

Required proof:
- process/reboot round-trip;
- local REMOTE_QUEUED remains visible.

### A-002 — provisional receipt could block terminal receipt
Severity: CRITICAL
Status: FIXED_IN_AUDIT_BRANCH

Finding:
`edge_receipts.actionId` is primary key while receipt insert used IGNORE. A later terminal receipt with the same action could be discarded after an earlier QUEUED/ACCEPTED receipt. Dependency evaluation could then remain blocked forever.

Fix:
- receipt upsert uses REPLACE for the same logical action;
- terminal result can supersede queue acknowledgement.

Required proof:
- QUEUED -> SUCCESS same action ID;
- dependent job unlocks only after terminal success.

### A-003 — blind redispatch of already-queued remote jobs
Severity: MEDIUM/HIGH
Status: FIXED_IN_AUDIT_BRANCH

Finding:
Every reconciliation could POST the same REMOTE_QUEUED job again.

Fix:
- fetch remote job snapshot by idempotency key;
- observe durable remote presence;
- suppress repost while remote row exists;
- permit idempotent resubmit only when remote row is missing.

### A-004 — duplicate WorkManager reconciliation implementations
Severity: HIGH
Status: FIXED_IN_AUDIT_BRANCH

Finding:
Two distinct `EdgeReconcileWorker` classes existed:
- one CONNECTED-only / 15-minute path;
- one NOT_REQUIRED / 30-minute path.

This creates ambiguous recovery policy and can suppress local-only reconciliation when offline.

Fix:
- remove legacy duplicate worker;
- route reconcile requests through one scheduler.

### A-005 — offline treated as retry failure
Severity: MEDIUM
Status: FIXED_IN_AUDIT_BRANCH

Finding:
Offline EDGE_ONLY could trigger repeated WorkManager retries even though local maintenance had succeeded.

Fix:
- local reconciliation runs before remote access;
- offline is a valid successful local-maintenance outcome;
- exceptional worker failure remains bounded retry.

### A-006 — periodic WorkManager schedule churn
Severity: MEDIUM
Status: FIXED_IN_AUDIT_BRANCH

Finding:
Periodic schedule used UPDATE while orchestrator construction may occur repeatedly.

Fix:
- use unique periodic work with KEEP so object reconstruction does not continually reset scheduling policy.

### A-007 — server memory evidence downgrade
Severity: CRITICAL
Status: FIXED_IN_AUDIT_BRANCH

Finding:
Windows memory admission prevented lower-evidence replacement only when the old item was pinned. Unpinned MACHINE_READBACK could be overwritten by lower evidence.

Fix:
- reject any evidence-rank downgrade for an existing key;
- server and Android policy now align conservatively.

Self-test:
- MACHINE_READBACK -> MODEL_DERIVED must reject.

### A-008 — pinned memory could silently become unpinned
Severity: HIGH
Status: FIXED_IN_AUDIT_BRANCH

Finding:
Server upsert wrote the incoming pinned flag directly. An equal-authority update could clear a previously pinned item.

Fix:
- pinning is monotone for same canonical key unless a future explicit revocation/supersession protocol is used.

Self-test:
- pinned MACHINE_READBACK updated by same evidence with pinned=false remains pinned.

### A-009 — candidate manifest pointed to mutable/wrong main bytes
Severity: HIGH
Status: FIXED_IN_AUDIT_BRANCH

Finding:
Candidate `release/server.json` used the `main/windows/bcp_server.py` URL while its hash described candidate-branch bytes. Before merge, a field update could see a URL/hash mismatch.

Fix:
- candidate manifest pins exact immutable commit URL + SHA-256 + source_commit.

Rule:
- candidate update metadata must identify exact bytes, not assume main already contains them.

### A-010 — durable queue is not yet a PC executor
Severity: CRITICAL
Status: OPEN / EXPLICITLY EXPOSED

Finding:
BCP 0.6 persists jobs and dependencies but no qualified PC worker was found that:
- transactionally claims jobs;
- creates/renews leases;
- executes an allowlisted adapter;
- writes terminal receipts;
- reconciles crash-after-effect.

Mitigation:
`/v1/orchestrator/status` in the audit server explicitly reports:
- `durable_queue_ready=true`;
- `pc_executor_ready=false`;
- `queue_ack_is_completion=false`.

Target contract:
`docs/PC_JOB_EXECUTOR_CONTRACT.md`.

Promotion gate:
one bounded NOOP/diagnostic job must complete through claim -> lease -> execution -> terminal receipt before any autonomous-execution claim.

### A-011 — Android job envelope is incomplete
Severity: HIGH
Status: OPEN

Finding:
Server job schema accepts action_id, expected_revision, input_hash, coordinator_epoch, evidence_contract and dependencies, but current B-EDGE POST sends only kind/payload/requires_pc/resource_class plus idempotency header.

Risk:
V2 fencing/evidence policy exists on paper but is not carried end-to-end by Android.

Required fix:
extend durable EdgeJobEntity/protocol envelope and add migration + round-trip tests.

### A-012 — Room schema lifecycle is not production-qualified
Severity: HIGH
Status: OPEN

Finding:
Current edge Room DB is version 1 with `exportSchema=false`; no released migration campaign exists yet.

Required fix before durable long-term V2 state:
- export schemas;
- add explicit migration tests;
- prove upgrade without loss;
- no destructive fallback for canonical state.

### A-013 — memory category not represented in runtime schema
Severity: HIGH
Status: OPEN

Finding:
Policy correctly distinguishes NORMATIVE / DESCRIPTIVE / DERIVED / UNTRUSTED_CONTENT, but current Android/server rows primarily encode layer + evidence class.

Why it matters:
authority is category-dependent. A user preference and a machine-observed fact should not share one global scalar precedence model.

Required fix:
add category/authority domain to the next schema migration and test category-specific conflict rules.

### A-014 — receipt provenance is incomplete on B-EDGE
Severity: HIGH
Status: OPEN

Finding:
EdgeReceiptEntity currently stores `outputHash`, but audit implementation may use a hash of the receipt JSON when no explicit output hash exists, and raw receipt/evidence pointer is not durably preserved in the receipt row.

Required fix:
separate:
- receipt_hash;
- effect/output_hash;
- evidence pointer/payload;
- terminal/nonterminal classification.

Requires schema migration, so do not hot-patch without migration tests.

### A-015 — legacy checkpoint/cached resume still uses SharedPreferences
Severity: MEDIUM/HIGH
Status: OPEN

Finding:
New jobs/memory use Room, but legacy pending checkpoint body/idempotency and cached resume remain duplicated in SharedPreferences.

Required fix:
migrate to transactional durable outbox/memory after compatibility import.

### A-016 — POC cleartext LAN bearer path
Severity: CRITICAL_BEFORE_PRODUCTION
Status: OPEN / KNOWN

Finding:
B-EDGE still uses HttpURLConnection HTTP on LAN. Discovery identity is not yet the final authenticated encrypted transport.

Required fix:
persistent PC cryptographic identity + paired trust + TLS/pinning/equivalent authenticated encrypted channel.

No production ACTIVE promotion while long-lived bearer/provider secrets can traverse unrestricted cleartext.

### A-017 — subnet scan remains fallback
Severity: MEDIUM
Status: ACCEPTABLE_POC_FALLBACK / NOT_FINAL

NSD is now primary. /24 scan remains bounded fallback with reduced concurrency. It must stay diagnostic/fallback only and must not become periodic background behavior.

### A-018 — Android future local-network permission
Severity: FUTURE_COMPATIBILITY
Status: OPEN

Before targetSdk/API 37 promotion, qualify Android 17 local-network permission/system-mediated path. Do not misdiagnose denied permission as PC offline.

### A-019 — canonical requirements contain historical/current-target drift
Severity: MEDIUM
Status: OPEN

The canonical document still contains an older "Current target: BCP 0.4.7" block while the integration line is 0.6/2.0-RC.

Required fix:
preserve historical P0 evidence, but separate:
- FIELD_BASELINE;
- CURRENT_INTEGRATION_CANDIDATE;
- NEXT_PROMOTION_TARGET.

Do not rewrite history as if the older field proof never existed.

### A-020 — direct-main concurrency risk
Severity: HIGH
Status: POLICY_FIXED

Repository now has `.project-memory/GIT_WRITER_LEASE_POLICY.json` forbidding autonomous direct-main writes.

This audit branch follows that policy. Merge only after reread/reconcile and exact-head CI.

## Next audit frontier

Priority order:
1. qualify current audit branch CI;
2. implement/verify a minimal proof-carrying PC executor state machine;
3. carry full fencing/evidence envelope from B-EDGE to PC;
4. Room schema v2 with migration tests for memory category + receipt provenance;
5. migrate checkpoint/outbox away from SharedPreferences;
6. encrypted LAN transport;
7. device lifecycle/failure-injection campaign;
8. only then V2 coordinator-authority promotion;
9. free model broker runtime/provider field qualification;
10. Telegram autonomous mission cockpit.
