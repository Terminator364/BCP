# BCP Execution Fabric — Acceptance & Use-Case Matrix R1

Status: SEALED_PRECONCEPTION_R1 SUPPORTING MATRIX
Date: 2026-10-05

## A. Reference use cases

### UC-01 — Med Rebuild / Commander recovery without blocking the project

**User intent**
"Continue Med Rebuild. Make the local Commander path work, but keep fixing what you can meanwhile."

**Expected plan**
- branch A: Commander capability recovery;
- branch B: repo/project inspection;
- branch C: installer/launcher audit;
- branch D: targeted tests;
- branch E: update/rollback health.

**Expected behavior**
- Commander auth/pairing failure pauses only branch A;
- B/C/D/E continue if resources permit;
- no reinstall loop;
- no package `@latest` in interactive recovery;
- one compact user action only if irreducible auth is required;
- final result contains branch-level receipts.

**Failure if**
- entire mission blocks because Desktop Commander is offline;
- user must copy logs manually;
- success is claimed from process existence alone.

### UC-02 — "Stop heavy things" while preserving mission state

**User intent**
"Stop anything heavy; keep the important state."

**Expected behavior**
- Resource Governor enters PRESSURE/SURVIVAL policy;
- heavy child trees receive graceful cancellation deadline then Job Object termination if needed;
- committed steps remain committed;
- partial uncommitted effects reconcile;
- mission status becomes PAUSED_SAFE/WAITING_RESOURCE;
- no unrelated user process is killed.

### UC-03 — TLIB background indexing

**User intent**
"Continue scanning/indexing the library when the PC has room."

**Expected behavior**
- bounded batches;
- local disk checkpoints;
- one heavy worker;
- pause on foreground load/RAM pressure;
- resume after reboot;
- no entire corpus in RAM;
- progress derived from actual committed items.

### UC-04 — Excellentia corpus simulation

**User intent**
"Run 100 x 100-question simulations in the background and report failures."

**Expected behavior**
- deterministic test job;
- seeded/reproducible batches where appropriate;
- checkpointed results;
- no LLM per question;
- failures enter error/regression ledger;
- can resume after interruption.

### UC-05 — PhoneMouse/P2PCR95 build

**User intent**
"Build the next candidate."

**Expected behavior**
- BCP validates adapter/current revision;
- BuildHub owns build;
- one heavy PC worker;
- project-specific source remains private;
- CI may accelerate but is not required for an already installed local BuildHub;
- artifact hash/signature/readback required.

### UC-06 — ChatGPT Delivery

**User intent**
"Send the finished PDF on Telegram and keep Drive clean."

**Expected behavior**
- artifact staged once;
- hash;
- choose transport;
- Drive persistent placement only if policy requires;
- Telegram send receipt/provider ID;
- cleanup/retention rule;
- failed delivery does not invalidate the generated artifact.

### UC-07 — Medical/library preprocessing

**User intent**
"Index these cardiology PDFs and prepare what I need for a study synthesis."

**Expected behavior**
- local inventory/hash/text extraction/index;
- no clinical interpretation delegated to tiny model by default;
- ChatGPT performs high-value synthesis;
- sources/artifacts remain traceable;
- background extraction yields to foreground use.

### UC-08 — Internet disappears

**Expected behavior**
- local mission state continues;
- local deterministic steps continue;
- cloud-required steps WAITING_NETWORK;
- Drive/Telegram outboxes persist;
- no duplicate effects on reconnect.

### UC-09 — PC reboots

**Expected behavior**
- runtime reconstructs mission state;
- reads receipts/idempotency ledger;
- reconciles ambiguous in-flight actions;
- resumes next uncommitted safe step;
- avoids simultaneous restart of all heavy workers.

### UC-10 — B-EDGE absent

**Expected behavior**
- PC can operate in explicitly authorized standalone/coordinator compatibility mode;
- no mission is silently lost;
- later B-EDGE return reconciles through epoch/fencing;
- no automatic split brain.

### UC-11 — ChatGPT conversation ends

**Expected behavior**
- mission continues if it has executable branches;
- NEEDS_CHATGPT branch is held;
- Telegram/local cockpit may show exact state;
- new chat can resolve mission by ID/context connector.

### UC-12 — Local AI unavailable or crashes

**Expected behavior**
- capability expires/goes TEMP_UNAVAILABLE;
- deterministic/ChatGPT path continues;
- no canonical mutation from partial model output;
- no restart loop.

## B. Cross-cutting gates

| Gate | Oracle | Evidence |
|---|---|---|
| G1 Durable mission | restart process/PC mid-job; state resumes | mission event log + next step |
| G2 Idempotency | replay same envelope | one committed effect |
| G3 Resource safety | inject RAM pressure | background pauses, user foreground remains usable |
| G4 Heavy concurrency | queue 3 heavy jobs | at most 1 active |
| G5 Capability loss | disable Commander/GitHub/Drive independently | only dependent branches hold |
| G6 Network loss | disconnect Internet | local work continues; outbox persists |
| G7 Update rollback | activate broken candidate | LKG restored with receipt |
| G8 Privilege boundary | malicious/free-form admin request | denied unless typed allowed capability |
| G9 Prompt injection | hostile README/log/PDF | data cannot change policy/permissions |
| G10 Evidence | command exits 0 but healthcheck fails | mission not DONE |
| G11 Startup | reboot/logon | one primary startup path, no restart storm |
| G12 Backlog | multiple projects | truthful RUNNING/WAITING/DONE views |
| G13 Transport dedupe | same mission via two transports | one mission/effect |
| G14 SQLite/WAL | long run + checkpoint | bounded WAL, consistent DB |
| G15 Model crash | kill inference process | mission survives |
| G16 Offline auth | auth unavailable | AUTH_REQUIRED/HOLD, no false repair |
| G17 Dirty Git | uncommitted user work | no destructive overwrite |
| G18 Artifact delivery | Telegram fails after generation | artifact remains valid/retryable |
| G19 Drive stale | stop Drive sync | no hot-state loss |
| G20 Read-only audit | no write permission | full diagnostic still available |

## C. Resource qualification

The Phase-0 probe records:
- total and available physical RAM;
- commit charge/limit;
- pagefile size/location;
- hard-fault rate sample;
- top process working sets;
- HDD/SSD type where detectable;
- disk free and queue;
- CPU topology/load;
- installed runtime versions;
- startup hooks/services/tasks;
- BCP resident footprint;
- Commander resident footprint;
- Drive state;
- network state.

No fixed local-AI profile is promoted from specification alone.

## D. Desktop Commander migration tests

1. Detect current exact installed version and package source.
2. Inventory all current autostart hooks.
3. Prove whether more than one hook fires on logon.
4. Preserve existing device/session identity.
5. Replace `@latest` with a qualified exact version where legacy artifacts still use latest.
6. Separate package update from process start.
7. Test network unavailable.
8. Test auth required.
9. Test corrupted local config.
10. Test server-side presence error.
11. Test process crash.
12. Test repeated click on launcher.
13. Test PC reboot at 90% memory pressure.
14. Verify Med Rebuild-native work continues when Commander stays offline.

## E. User-effort gate

A normal task fails UX acceptance if it requires any of the following when the machine could have observed/performed it itself:
- asking the user to copy terminal output;
- asking for repeated screenshots to prove machine state;
- asking the user to manually move generated files between project folders;
- asking the user to repeat a command after a recoverable reboot/network failure;
- asking repeated UAC approval for a previously scoped safe capability;
- making the user choose a transport that policy can choose automatically;
- forcing reinstall for an ordinary transient failure.

## F. Final field certification threshold

Do not call the Execution Fabric FIELD_READY until:
- all P0 gates G1–G13 pass on MBMPC or the actual target node;
- resident footprint is measured;
- reboot and network-loss recovery are proven;
- at least one real Med Rebuild mission is completed end-to-end;
- at least one long background job pauses/resumes under pressure;
- at least one build task passes through BuildHub;
- at least one Delivery task produces provider/readback evidence;
- no local model is required for any of the above.
