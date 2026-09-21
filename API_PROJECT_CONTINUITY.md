# R72 Dual-Closeout Communication Handoff — 2026-09-21

Canonical continuation code: `BCPGO BCP`.

## R72 merged checkpoint

- Exact-head R72 qualification: **PASS across all 12 critical workflows** on `be2d79671ac3ea18becc9e9812ae258f3ba4bdc8`.
- PR #140 merged to `main` at `7a82599ac3cfbeca1e153b02f035291d1b8f660e` after main-head recheck.
- Main readback confirms delivery policy R72, cadence policy R72, communication-survival schema v2, ACTIVE_TRANCHE ledger, BCPGO dual-closeout recovery and canonical requirements R72.
- The live R72 tranche remains open until the timer-driven Gmail END obtains provider acknowledgement. No user relaunch is part of that proof.
- After END proof, persist the closed tranche receipt, then continue B-EDGE 2.2.0 full-node and the Telegram-companion local/Drive fallback lane.

## Why R72 exists

R71 proved that a watchdog scheduled at minute 29 is too close to the 30-minute user-visible deadline. In the observed R71 tranche, the user relaunch arrived seconds before the scheduled watchdog execution, so the END mail appeared to depend on the user's "eh oh" message even though the watchdog was about to run. This is unacceptable for the communication contract.

R72 changes the closeout trigger from "near-deadline single watchdog" to **timer-driven dual pre-deadline closeout**:

1. Gmail START + provider ACK before substantive work.
2. Durable pre-close snapshot by T+26.
3. Normal closeout guard at T+27.
4. Hard close guard at T+28.
5. Absolute END deadline T+30.
6. Both guards search Gmail for the checkpoint id before sending, preventing duplicate END mail.
7. Gmail END must have provider ACK + readback + BCP label.
8. ChatGPT is pointer-only after END ACK.
9. A user message is never the closeout trigger.

Durable active-tranche ledger:
`.project-memory/ACTIVE_TRANCHE.json`.

Fresh-conversation recovery MUST load this active-tranche ledger before deciding whether work is still open, closing, or already END-acknowledged.

## Current product direction

The product direction from R71 remains unchanged: B-EDGE 2.2.0 full-node is the next coherent phone product gate, not another micro-beta. The dedicated phone remains the persistent low-power BCP server/edge node; the PC is the Windows/heavy worker.

---

# R71 Communication-Survival Handoff — 2026-09-21

Canonical continuation code: `BCPGO BCP`.

## R71 merged checkpoint

- PR #138 merged to `main` at `ed67963c97130078b1442c8b369fbe6fb41f19a2`.
- All 12 critical qualification workflows passed on exact pre-merge head `d00deaff968bb10df7d87c0a959d03ed4d3faf43`.
- Main readback confirms BCP Windows target **0.7.16**, Telegram companion **2026.09.21-comms-survival-v22**, requirements revision R71, communication survival policy, 30-minute tranche policy and global qualification trigger.
- Field convergence is now the gate: verify MBMPC 0.7.16 + Telegram V22 runtime telemetry and actual transport route.
- Installed phone remains B-EDGE 2.1.2 until the coherent 2.2.0 full-node APK is signed, published to Drive CURRENT and exact-hash read back. Do not ask for another phone install before that gate closes.


A fresh conversation MUST load `.project-memory/COMMUNICATION_SURVIVAL_POLICY.json` before resuming work. The user MUST NOT be asked to reconstruct communication rules, the 30-minute cadence, phone-primary architecture, or current field state.

## R71 communication survival / cross-conversation recovery

The durable communication fabric is:
1. Gmail START/END for detailed human checkpoints, with provider ACK required;
2. Telegram as secondary witness/alert, direct first then B-EDGE relay when qualified;
3. dedicated Android phone as persistent low-power queue/API/store-and-forward node;
4. Drive as durable replicated telemetry/recovery evidence;
5. ChatGPT as interactive reasoning/pointer surface, never canonical state.

If ChatGPT UI stalls or the conversation is replaced, `BCPGO BCP` resumes from durable state. The user does not need to send an “eh oh” message to obtain a checkpoint. The dual closeout guards are armed at START: normal closeout before the deadline and a hard backup guard after it; Gmail END is retried until provider acknowledgement before any ChatGPT end output.

Detailed technical recovery runbook:
`docs/BCP_COMMUNICATION_SURVIVAL_AND_CROSS_CHAT_RECOVERY_R72.md`.

Private human recovery copy: `API_BCP/03_DOCUMENTATION/BCP — PLAN DE SECOURS COMMUNICATION & REPRISE R71` in the user's Drive. Do not put its Drive ID or private link into the public repository.

## R71 current communication targets

- BCP Windows candidate: **0.7.16** — exports the proven Telegram route (`DIRECT_TELEGRAM`, `B_EDGE_RELAY`, or no working route) into machine-readable runtime telemetry.
- Telegram companion candidate: **2026.09.21-comms-survival-v22** — persists route receipts without exposing the Telegram token to the phone.
- Android full-node candidate: **2.2.0-full-node-evergreen** — exact-head CI/signing/publication still gate the next user installation.
- Installed phone field release remains 2.1.2 until that coherent full-node gate is closed.

Canonical continuation code: `BCPGO BCP`.

A fresh conversation MUST load durable state first, send the **BCP-labeled Gmail START**, preserve the ~30-minute tranche contract, and never ask the user to restate the dedicated-phone architecture.

## Field truth recovered from the installed phone

The user has installed B-EDGE 2.1.2 in place. The visible phone UI reports CONNECTÉ / MBMPC / server 0.7.15, and machine telemetry independently confirms:
- BCP 0.7.15 resident on MBMPC;
- paired=true;
- B-EDGE relay active at the phone LAN address on port 8876;
- B-EDGE field version 2.1.2-rc1-edge-relay;
- Telegram direct transport is currently in outage, so the phone relay path is materially relevant.

This proves the installed 2.1.2 app is real and active, but it also proves the user's criticism: 2.1.2 is still an Edge-relay release, not the completed dedicated-phone server appliance.

## Active R69 product direction

The old Android phone is the **primary persistent low-power BCP appliance node**. It MUST be used beyond a passive client/relay role:
- foreground local API server;
- durable Room/WAL project memory, receipts and job queue;
- store-and-forward and idempotent reconciliation;
- boot/package-replacement restoration;
- local LAN NSD presence;
- Wi-Fi Direct DNS-SD presence when supported/authorized;
- low-power BLE presence beacon when supported/authorized;
- bounded authenticated node API for status/sync/job admission;
- strict Telegram HTTPS CONNECT relay retained;
- PC is a Windows/heavy-compute worker, not the sole communication center;
- no SIM in the old phone is assumed.

Current R69 candidate branch:
`work/bcp/r69-phone-server-fullnode-20260921-1554`

Candidate identity:
- versionCode: **220**;
- versionName: **2.2.0-full-node-evergreen**;
- applicationId remains `com.blessing.bcpedge.evergreen`;
- in-place update only; never uninstall merely to upgrade.

The candidate introduces meaningful Android permission/onboarding for dedicated-server use, a compact server-oriented UI, local API health/capabilities/private endpoints, boot restore, NSD/Wi-Fi-Direct/BLE presence, and representative Android-emulator API-server testing.

Do not expose 2.2.0 to the user until exact-head CI/build/emulator qualification passes and a signed APK with the pinned Evergreen certificate is published/read back into `API_BCP/00_INSTALL_CURRENT/BCP_EDGE_CURRENT.apk`.

## Communication/continuity contract

1. Every BCP tranche: Gmail START with label **BCP** before substantive work.
2. Target ~30 minutes; watchdog is fail-safe, not a substitute for normal closeout.
3. Gmail END contains the complete checkpoint and must have provider send acknowledgement.
4. ChatGPT emits no end message before END acknowledgement.
5. After END acknowledgement, ChatGPT is pointer-only.
6. Telegram is secondary witness/control; durable state remains repo/BCP/phone/Drive as applicable.
7. Before user install/click/retry, exact representative simulation must pass.
8. All repo mutation obeys the single-writer Git fence.

---

# R68 Fresh Conversation Handoff — 2026-09-21

Canonical continuation code: `BCPGO BCP`.

On a fresh conversation, this code MUST recover durable state first and preserve the current communication contract without asking the user to restate it.

## Communication contract

1. Apply Gmail label **BCP** to BCP START/END mail.
2. Send Gmail START before substantive work.
3. Work target: approximately 30 minutes.
4. Send the full Gmail END checkpoint and require provider send acknowledgement.
5. Before END acknowledgement, ChatGPT emits no end message.
6. After END acknowledgement, ChatGPT is pointer-only: Gmail + Kinshasa day/date/time + checkpoint id.
7. Use the tranche END watchdog as fail-safe; normal END disables it after successful send.
8. Telegram is a secondary witness/remote-control channel, never the sole durable checkpoint.

## Dedicated old phone role

The old Android phone is a **primary BCP Edge/server node**, not a passive client. It is dedicated infrastructure and should absorb persistent/low-power communication work whenever feasible:
- local API/relay and authenticated PC<->phone control path;
- durable Room-backed state, local resume cache and pending checkpoint queue;
- WorkManager reconciliation and foreground remote-messaging service;
- Telegram-only HTTPS CONNECT relay with end-to-end TLS and strict `api.telegram.org:443` allowlist;
- network-wait/store-and-forward semantics when no uplink exists;
- no SIM is assumed in the old phone;
- PC remains a Windows/compute node when Windows-specific work is needed, not the single communication center.

## Current installable phone release

Stable Drive CURRENT is now replaced in place with:
- package: `com.blessing.bcpedge.evergreen`;
- versionCode: **212**;
- versionName: **2.1.2-rc1-edge-relay-evergreen**;
- stable file: `API_BCP/00_INSTALL_CURRENT/BCP_EDGE_CURRENT.apk`;
- SHA-256: `3eb1260dee31c3ff2b9668d22fd90460bdc331426f9f5361d46eb78b0a59e2cc`;
- signing certificate SHA-256: `0baad4749918f1b2430bbbf3f5ddbdb1de4908b017910d67aef2cb987ddeb617`;
- APK Signature Scheme v2/v3: PASS;
- Drive byte/hash readback: PASS;
- previous 2.1.0 copy preserved for rollback.

The install action, when exposed, is **in-place only**: do not uninstall and do not re-pair unless a field failure proves it necessary.

## Current merged state and field gate

R68 exact-head CI passed on `4196c0ac93cc6442d460a4b79bb2c8afa7fbc060`.
PR #136 merged to `main` at `546c5d4042660e80a60fa10eff0d760301e48bdc`.
Main readback confirms B-EDGE 2.1.2, exact APK SHA, pinned certificate metadata, server 0.7.15 coordination, R68 mail-label policy and phone-primary Edge continuity.

The next legitimate human field gate is now exactly one **in-place** install:
- open `API_BCP/00_INSTALL_CURRENT/BCP_EDGE_CURRENT.apk`;
- install/update over the existing BCP Edge app;
- **do not uninstall** first;
- do not re-pair unless subsequent machine evidence proves pairing was lost.

After install, verify in order: version 2.1.2 readback, existing pairing continuity, foreground relay service/notification, relay registration at BCP 0.7.15, and one Telegram round-trip. Any failure should be diagnosed from telemetry and fixed automatically before asking the user to repeat actions.

---

# R64 Fresh Conversation Handoff — 2026-09-21

Canonical continuation code: `BCPGO BCP`.

R64 closes a real implementation gap: the dedicated old phone is infrastructure, not a passive client.

Current candidate:
- PR #133 on branch `work/bcp/r64-phone-edge-adaptive-comms-20260921-1312`;
- BCP 0.7.15: fresh private-LAN B-EDGE relay registration + relay liveness in runtime telemetry;
- B-EDGE 2.1.2 candidate: dedicated remote-messaging foreground relay, Room/WorkManager continuity retained;
- Telegram V21: direct Bot API first, then B-EDGE HTTPS CONNECT failover only on network transport failure;
- relay target is strictly `api.telegram.org:443`; no GitHub/Drive/APK/bulk relay;
- Telegram TLS remains end-to-end; B-EDGE does not need the Telegram bot token;
- no SIM is assumed in the old phone. It uses any available Wi-Fi uplink; without uplink, remote delivery waits durably and local state survives.

Normal recovery:
1. Gmail START before substantive work.
2. Target ~30 minutes.
3. Finish/read exact-head PR #133 CI; auto-fix simulation failures without user retry.
4. Merge only through the single-writer fence.
5. Field-promote server/phone/Telegram only after exact version/hash/signing/readback gates.
6. Gmail END must be provider-acknowledged before any ChatGPT end output.
7. ChatGPT remains pointer-only after successful END.

Do not ask the user to reinstall or repeat clicks while R64 is still CI/field-unverified.

---

# R62 Post-Merge Communication Handoff — 2026-09-21

Canonical main integration:
- R62 merge SHA: `3a20c14fea1644c48e5bfaf3970d6010159e93bc`;
- exact qualified PR head: `03d9b2b76356ef093f1680ee86f16286ff8dafca`;
- exact-head required CI: PASS;
- target resident server: BCP 0.7.14;
- target Telegram companion: 2026.09.21-comms-autonomy-v20.

Current field truth after merge:
- resident MBMPC is still observed on BCP 0.7.13;
- server update check is CHECK_FAILED;
- direct Telegram transport is flapping and latest readback is DEGRADED_RETRY / WinError10060;
- Nexus remains STAGE_FAILED / DNS_RESOLUTION_FAILED;
- therefore source integration is complete but resident convergence is not yet field-proven.

Do not ask the user to reinstall BCP, re-enter the Telegram token, repeatedly click the Nexus helper, or switch networks again merely for diagnosis.

Next recovery path:
1. finish/read post-merge CI;
2. observe automatic convergence to 0.7.14 + Telegram V20;
3. if raw GitHub/DNS prevents convergence, implement a Drive-local update/failover lane so communication recovery does not depend on a single Internet hostname;
4. only after the R62 runtime is field-proven may a remaining Cloudflare consent gate be exposed;
5. provider-authenticated readback remains mandatory before Nexus success.

# R62 Communication Autonomy Handoff — 2026-09-21

Current field truth:
- MBMPC is alive on BCP 0.7.13.
- After the user switched from failing home Wi-Fi to mobile hotspot, direct Telegram is ACTIVE, last poll is fresh, and consecutive failures are 0.
- The bot was therefore alive; the human-facing failure was prolonged silence because healthy polling alone did not emit a liveness notice.
- Nexus currently reports STAGE_FAILED / DNS_RESOLUTION_FAILED. The user-facing one-shot showed NO_HUMAN_AUTH_RETRY_NEEDED even though this was a network-stage condition, so no additional manual retry is justified on the old runtime.

R62 candidate:
- BCP 0.7.14 preserves a prior Nexus human-auth gate across transient staging-network failures and can recover it from the durable receipt.
- A network-stage one-shot now retries staging once and otherwise reports NETWORK_RECOVERY_PENDING with automatic recovery instead of misleading success/no-retry.
- Telegram V20 sends a compact online notice after a genuine restart, a reconnect notice after network recovery, and at most one silent alive proof every 90 minutes.
- No Telegram token re-entry, BCP reinstall, or repeated user clicking is part of the recovery path.

Next:
1. exact-head CI;
2. writer-fenced merge;
3. automatic resident convergence to BCP 0.7.14 + Telegram V20;
4. Drive/Telegram readback;
5. only then expose any remaining irreducible Cloudflare human authorization gate.

# R60 Fresh Conversation Handoff — 2026-09-21

Canonical continuation code for a new conversation:

`BCPGO BCP`

On a fresh conversation, this code means:
- load `project_state.json`, this handoff, the canonical requirements, delivery policy, 30-minute cadence policy, pre-human action simulation policy, writer-fence policy and CURRENT manifests;
- do not reconstruct the project from chat history;
- resume from the next uncommitted action only;
- immediately send a short Gmail **START** notice before substantive project work; at tranche end send the full Gmail **END** checkpoint; only after the END receipt is confirmed may ChatGPT answer, and then it is pointer-only;
- normal useful-work tranche target is approximately 30 minutes (practical 29–30 minute window unless a real gate ends it earlier);
- never instruct the user to click/install/retry a technically simulatable path before representative CI/runtime simulation has passed;
- preserve the single-writer fence and exact-head CI/merge discipline.

### R61 merged communications checkpoint

R61 is merged on `main` at `66cbeeb2cd1315369fddbdc1d611fd7e38e5803e`. Exact-head CI passed before merge and the observed post-merge gates are all green: CURRENT #796, PC Sanity #320, Nexus One-Shot #141, Nexus Transport #513, Telegram Observability #550 and Field Ecosystem #727.

The direct Telegram worker is alive but the transport remains unusable from MBMPC due repeated WinError 10060 timeouts. BCP 0.7.13 is field-proven and the Nexus one-shot path is qualified. The next irreducible human gate is therefore exactly one fresh Cloudflare device authorization using `API_BCP/00_INSTALL_CURRENT/BCP_NEXUS_AUTH_CURRENT.zip`. Never reuse an expired code, reinstall BCP, re-enter the Telegram token, or fall back to localhost:8976. Completion requires provider-authenticated readback and proof that Telegram receiver ownership moved to Nexus/webhook.

### R61 communication recovery state

Fresh field telemetry after the PC was powered on proves BCP 0.7.13 is alive and UP_TO_DATE, while the Telegram companion process is alive but the direct Bot API path is timing out with WinError 10060 and repeated failures. Treat this as a transport outage, not as a dead process and not as evidence that Telegram messages are being delivered.

R60 post-merge qualification is fully green. The next real recovery boundary for remote Telegram is the already-qualified Nexus path. R61 companion V19 adds explicit `DIRECT_TRANSPORT_OUTAGE` state plus durable outage/recovery receipts. After R61 exact-head qualification and merge, exactly one fresh Nexus/Cloudflare device authorization is the next legitimate human gate; after authorization require provider-authenticated readback before Telegram webhook/Nexus ownership is declared restored.

### 30-minute END watchdog — R61

At each Gmail START, arm a one-shot assistant watchdog for +30 minutes. The watchdog must check whether this tranche's END Gmail already has a provider send acknowledgement. If yes, it does nothing. If no, it sends an accurate END checkpoint from the latest durable state and only then may a ChatGPT pointer appear. A normal successful END disables the watchdog. This removes dependence on the user sending “eh oh” or another relaunch just to close a tranche.

### START/END Gmail handshake — R60
For every user-invoked continuation/relaunch/message that starts project work:
1. perform only the minimum routing/context lookup needed to know the project;
2. send Gmail START with Kinshasa day/date/time, project and tranche scope;
3. perform the substantive work;
4. persist evidence/checkpoint;
5. send Gmail END with the complete checkpoint and retry automatically until the provider returns a successful send acknowledgement;
6. only after that END acknowledgement, in ChatGPT show: “Va sur Gmail” + Kinshasa day/date/time + checkpoint id.

If the START mail fails, do not begin the substantive tranche. If the END mail fails, emit no ChatGPT end message at all; retry the END mail until acknowledged.

### Fast field-readback lookup

To avoid slow broad Drive search on every continuation, recover the resident BCP runtime through deterministic folder traversal:
1. locate the exact folder named `API_BCP`;
2. list its exact child `02_TELEMETRY`;
3. list child `BCP`;
4. list/fetch `BCP_RUNTIME_LATEST.json`;
5. use its machine fields (`server_version`, `server_sha256`, `updated_at`, `update_state`, `nexus_bootstrap_state`) as field evidence.

Do not start with a broad full-Drive content search for runtime telemetry. Keep Drive IDs out of the public repository; resolve IDs from the connected private Drive at runtime.

Current durable integration truth:
- R58 server fix is already merged on `main` at `0db531771d631ebade0847494baf3ca82c713674`; R60 continuity/simulation hardening remains on PR #127 until exact-head CI is green;
- BCP target is **0.7.13**;
- 0.7.13 fixes the Nexus explicit-retry HTTP 500 caused by the missing `uuid` import;
- the Nexus server-side retry path passed runtime simulation;
- the exact Windows PowerShell one-shot helper passed both a simulated `202 / LAUNCHED` path and an expected `500 / HOLD` negative control;
- exact-head R58 qualification passed before merge; R60 exact-head qualification is the current integration gate;
- fresh Google Drive machine readback from `API_BCP/02_TELEMETRY/BCP/BCP_RUNTIME_LATEST.json` now proves **BCP 0.7.13** on MBMPC with exact server SHA-256 `cb4b05e5771b35a69bba3de804af3b5e6abed07ffb698015ad257467f61ba4fe`, `update_state=UP_TO_DATE`, `paired=true`;
- Nexus remains `HUMAN_AUTH_REQUIRED` with bundle `0.2.6` and error class `CLOUDFLARE_DEVICE_AUTH_REQUIRED_OR_EXPIRED`;
- therefore the BCP-version convergence gate is cleared, but **do not ask the user to retry Nexus until PR #127 passes exact-head CI and is merged/read back**.

Current action:
1. finish exact-head R60 qualification on PR #127;
2. reread `main` and merge only through the single-writer fence if all required checks are green;
3. verify the merge/readback and post-merge workflows;
4. then expose exactly one fresh Nexus Cloudflare device-authorization action;
5. after consent, require provider-authenticated `whoami`/equivalent readback before Nexus is complete.

No reinstall, reboot, stale Cloudflare code, or repeated Nexus ZIP attempt is justified before the R60 integration gate is cleared.

---

# API — Official Project Continuity Handoff

Canonical continuation code: `APIAX07`
Legacy alias: `BCP CONTINUE` (compatibility only).

## Official identity
- Project name: API
- Architectural lineage / internal system name: BCP — Blessing Control Plane
- Frozen authority: BCP V0.7 AX15GO SEALED
- Batch: AX15GO-BCP-20260918-V07
- Status: PRECONCEPTION_FINAL_CLOSED_SEALED_V0_7
- Broad preconception is closed; implementation/native/cloud/field evidence remains required.

## Mission
API is not merely an HTTP API or an API for calling ChatGPT. It is the personal digital control/continuity plane: canonical project identity/state, operational memory, bounded permissions, signed/idempotent jobs, receipts/evidence, offline continuity and deterministic recovery across ChatGPT, ChatGPT-PC, B-Edge, BuildHub, Drive, GitHub, Gmail and future adapters.

## Why now
The target is the recurring fragmentation/manual-handoff problem: conversation limits and context dilution; CURRENT/FINAL/RECOVER proliferation; screenshots used as telemetry; manual download/move/run/copy/hash loops; CI/quota dependency; unstable power/connectivity; a ~4 GB Windows PC under high memory pressure; and completion claims without artifact/hash/test/readback.

## Recovery on APIAX07
1. Recover latest API continuity state.
2. Verify the immutable V0.7 authority SHA-256 and MANIFEST.sha256.
3. Read package_state, V0.7 AX15GO audit, design closure, invariants, AX150K adapter and portable harness evidence.
4. Recover latest field/runtime state from Library/GitHub/ChatGPT-PC without asking the user to restate known context.
5. Keep the sealed architecture unless measured evidence reveals a security defect, implementation impossibility or acceptance failure.


## Universal BCP bootstrap command

Canonical cross-project bootstrap command: `BCPGO`.

Purpose:
- usable as the common semantic entry point across fresh ChatGPT conversations and project scopes;
- recover GLOBAL_CORE first, then the inferred/explicit PROJECT_CORE and current TASK_DELTA;
- avoid broad recovery scans when a precomputed context projection exists;
- use revision-aware UNCHANGED/DELTA refreshes on subsequent turns;
- never treat the command text itself as authentication.

Compatibility:
- `APIAX07` remains the API/BCP scoped recovery alias and retains its deliver-first semantics where applicable;
- `CONTINUE ATOMIC` remains the next-action resume phrase when state is already known;
- project-specific recovery commands remain valid aliases;
- `BCPGO <project>` may explicitly select a project when auto-detection is ambiguous.

Integration reality:
- a typed code cannot create connectivity by itself;
- BCPGO requires an authorized connected read path such as the BCP Drive context projection, or a future qualified BCP app/plugin/MCP adapter;
- until such a direct adapter is field-proven on the user's current plan, Google Drive-connected bootstrap is the preferred universal read path;
- no public exposure of private B-EDGE memory is required.

Canonical architecture: `docs/BCP_CONTEXT_FABRIC_THREE_NODE_ARCHITECTURE.md`.

## Mandatory DELIVER-FIRST first mission
When the user types only `APIAX07` in a fresh conversation, do not start with a recap or a question. Recover latest state and **provide the newest qualified downloadable artifact needed to unblock the current field step first**.

At creation time (2026-09-18), BCP Edge is already installed on the old phone and the PC-side integration is the blocker. The current artifact is:
- `BCP_FINAL_BOOTSTRAP_0_3.zip`
- SHA-256 `dbb8ae256bafb2ce1f72d5cab02a6dab1726e3234a3bc4e5a27ac377fb5aabd3`

If a newer qualified artifact exists, deliver it instead and explain the supersession. Never silently regress to an older installer.

Then obtain machine-readable ChatGPT-PC/B-Edge readback and progress the reality gates. Do not use the user as a telemetry bus; minimize screenshots and manual IP/token/project copy-paste.

## Design invariants carried forward
- local-first, interruption-tolerant;
- ChatGPT reasons; devices execute bounded named operations;
- reuse ChatGPT-PC as Windows control/execution substrate; no parallel resident control plane unless evidence reopens design;
- thin cloud; CORE/ADAPTER separation;
- canonical revision/fencing/security/incarnation semantics; ambiguity => HOLD/CONFLICT;
- allowlist/schema/capability/expiry/idempotence/evidence for jobs; no arbitrary shell from untrusted content;
- offline safety can only reduce privileges;
- preserve P0 durability/reserve;
- DEFAULT_PAID_SPEND=0 USD;
- MODEL != PORTABLE != CLOUD != NATIVE != FIELD;
- every real failure becomes a regression obligation.

## Reality-gap bookkeeping
The AX150K adapter enumerates 9 PENDING reality probes, while package_state.json says empirical_gates_open=8. Reconcile this bookkeeping mismatch during implementation; do not drop a probe.


## Platform verification / interruption context (observed 2026-09-19)

Observed user-facing behavior:
- During long technical/tool-heavy turns, ChatGPT may display a system message such as **“Nos systèmes effectuent quelques vérifications supplémentaires avant de répondre”**.
- The user observed that pressing the ChatGPT **Stop** button ended both the active reasoning/tool turn and that verification hold in the UI. Treat this as an observed recovery action, **not as a guaranteed platform contract**.
- Separate this event from `429 / Too Many Requests` and from ordinary connector/tool failures; they are not the same class of incident.
- These platform holds must be treated as **external, nonterminal events**. They do not invalidate the API/BCP architecture, field state, commits, receipts, or prior verified work.

Required API behavior:
1. Before long/multi-tool work, persist `mission`, `last_committed_action`, `next_atomic_action`, relevant hashes/receipts, and the current field gate.
2. Prefer small transactional batches over long mixed GitHub/Drive/build/browser bursts.
3. On a platform verification hold:
   - do not restart the project;
   - do not re-run already committed mutations;
   - do not spam retries;
   - preserve the exact recovery pointer;
   - if the user stops the turn, resume from the last durable checkpoint on the next turn.
4. On `429 / Too Many Requests`:
   - use bounded exponential backoff with jitter;
   - serialize heavy tool calls;
   - resume idempotently.
5. On connector/tool transient failure:
   - re-check the affected channel;
   - retry only the failed atomic action when safe;
   - require readback/receipt before marking success.
6. Never try to evade or rewrite requests merely to bypass platform safety checks. Preserve the legitimate local/personal development context already established.
7. The user must not be the telemetry bus. Prefer machine-readable ChatGPT-PC / B-Edge / GitHub / Drive evidence over screenshots/manual copy-paste.

Cross-project policy source:
- `.project-memory/PLATFORM_CUT_RESILIENCE.md`

Recovery rule:
- A platform verification hold is classified as `PLATFORM_VERIFICATION_HOLD`.
- It is **nonterminal**.
- After the hold ends—or after the user stops that turn—`APIAX07` must recover the last durable state and continue from the **next uncommitted atomic action**, not from the beginning.


## APIAX07 low-friction recovery profile

Because repeated full recovery turns have triggered long platform verification holds, `APIAX07` must now use a staged recovery pattern focused on continuity and reduced tool burst, not on bypassing safety systems.

### Stage A — immediate recovery response
On `APIAX07`:
- recover only the latest durable project pointer and already-known canonical state;
- do **not** start broad web/GitHub/Drive/tool sweeps in the first response unless strictly required to answer the next atomic action;
- return a compact recovery record: current mission, last committed action, next atomic action, blocking gate, and whether any field evidence is missing;
- preserve all legitimate local/personal-device context already established;
- do not re-explain the whole architecture.

### Stage B — execution
After the recovery record:
- execute one atomic operation at a time;
- checkpoint after each successful mutation;
- serialize GitHub/Drive/build/tool work rather than launching a mixed burst;
- if a platform verification hold appears, treat it as nonterminal and stop cleanly at the last durable checkpoint;
- after user Stop or platform release, resume from the next uncommitted atomic action.

### User-facing behavior
The user should not need to repeatedly type recovery commands. One `APIAX07` after an interruption is sufficient. If the platform interrupts again, the project must resume from the durable checkpoint without resetting or asking the user to reconstruct prior state.


## Ultra-light resume after a verification hold

Observed sequence (2026-09-19): APIAX07 successfully began recovery and reached the step “identified control-plane state and next action”, then the ChatGPT platform showed an additional-verification hold before the turn completed.

Interpretation:
- recovery itself had started correctly;
- do not assume APIAX07 is the cause of the hold;
- treat the hold as a mid-turn platform interruption after partial recovery.

After such a hold, DO NOT rerun the full APIAX07 recovery loop again in the same conversation.

Use the continuation phrase:
`CONTINUE ATOMIC`

Semantics of `CONTINUE ATOMIC`:
- continue from the state already identified in the interrupted turn;
- do not redo broad recovery;
- do not re-scan GitHub/Drive/web unless the next atomic action strictly needs one source;
- perform only the next uncommitted atomic action;
- checkpoint immediately after completion;
- stop cleanly if another platform hold occurs.

If the conversation has lost the previously identified state entirely, then fall back to `APIAX07` once.


## Durable legitimate technical scope profile

On every API recovery, load and preserve:
- `.project-memory/API_SCOPE_PROFILE.json`
- `docs/LEGITIMATE_TECHNICAL_SCOPE_PROFILE.md`
- `.project-memory/PLATFORM_CUT_RESILIENCE.md`

This scope profile is canonical context for API/BCP. It records that the normal environment is the user's own devices, repositories, local network, CI/build systems and controlled tests, with defensive engineering/debugging/reliability/automation intent.

When a technical task could be ambiguous in isolation, retain only the minimum disambiguating context: owned/authorized target, local/controlled environment, concrete engineering objective, minimum necessary operation, and success/rollback evidence.

Do not weaken, disguise or bypass platform safeguards. If an additional-verification hold occurs, classify it as nonterminal, checkpoint and resume. If a request clearly targets a third party without established authorization, ask the minimum clarification needed.

## Product motivation and dual-conversation continuity

On every API recovery, also load and preserve:
- `.project-memory/USER_FRICTION_CHARTER.md`
- `.project-memory/WHY_API_EXISTS.json`
- `docs/DUAL_CONVERSATION_CONTINUITY.md`

These are canonical product requirements, not optional notes.

API/BCP exists partly because a ChatGPT conversation must not be a single point of failure for project execution. The system must be designed so platform verification holds, interrupted turns, rate limits and conversation loss do not erase state or force the user to reconstruct context manually.

Dual-conversation design is therefore part of API CORE:
- one ACTIVE writer conversation;
- one STANDBY read-capable conversation;
- canonical state in BCP, never in either chat alone;
- writer lease + monotonic fencing token + revision precondition + idempotency key for every mutation;
- STANDBY may take over only after lease expiry/clean release;
- stale ACTIVE writes are rejected;
- already-dispatched bounded jobs may continue independently and are observed through BCP receipts/job state.

User-experience acceptance target: interruption -> durable checkpoint -> safe takeover -> next uncommitted atomic action -> receipt, with no screenshot/manual state reconstruction.

## P0 session-survival and request-context requirements

These files are mandatory recovery inputs and must be loaded before expanding work:
- `.project-memory/SESSION_SURVIVAL_INVARIANTS.md`
- `.project-memory/PLATFORM_FRICTION_P0.md`
- `.project-memory/USER_FRICTION_CHARTER.md`
- `.project-memory/WHY_API_EXISTS.json`
- `.project-memory/API_SCOPE_PROFILE.json`
- `.project-memory/PLATFORM_CUT_RESILIENCE.md`
- `docs/TECHNICAL_REQUEST_CONTEXT_ENVELOPE.md`
- `docs/DUAL_CONVERSATION_CONTINUITY.md`

Priority rule: until interruption-resilience and dual-conversation continuity are FIELD_VERIFIED, do not treat them as optional polish. They are P0 product requirements and take priority over nonessential expansion.

Request formulation rule: when a legitimate technical task could appear ambiguous in isolation, API/BCP must automatically preserve the truthful minimum context envelope: owned/authorized target, local/controlled environment, engineering objective, narrow atomic action, boundaries, and expected evidence/rollback. This is for clarity and continuity, never for bypassing platform safeguards.

Session-loss rule: assume this conversation may disappear at any time. No current-chat detail required for project recovery may remain only in chat memory.

## Temporary manual relay while dual-conversation automation is unfinished

Until automated ACTIVE/STANDBY writer leases are FIELD_VERIFIED, use `docs/MANUAL_CONVERSATION_RELAY.md`.

Operational rule:
- if a verification hold interrupts a useful turn, the user may stop that turn, open a fresh API conversation and send `CONTINUE ATOMIC`;
- the fresh conversation must recover durable state and execute only the next uncommitted atomic action;
- never keep two writer conversations mutating the project concurrently;
- committed/PASS actions with receipts must not be replayed;
- if state is ambiguous, HOLD and verify before writing.

This relay may be repeated across fresh conversations. It is a continuity mechanism, not a mechanism for bypassing platform safeguards.

## Resynchronization command

Canonical resynchronization phrase:
`APIAX07 RESYNC`

Use this when the user remains inside the same API project but cannot access the most recent conversation/response because a device, browser, network, or page failed.

Semantics:
- do not treat this as a new project start;
- recover the latest durable API/BCP state and the most recent completed/committed result available from project sources;
- identify what the user had last requested and what output/result was produced or left pending;
- present the missing latest result first, then the exact current state and next action;
- do not replay already COMMITTED mutations;
- do not require the user to copy/paste the inaccessible prior response;
- avoid ChatGPT-PC during the currently active ChatGPT-PC isolation diagnostic mode unless the user explicitly ends that mode;
- if no durable copy of the inaccessible response exists, say so explicitly and reconstruct only from durable evidence, without inventing missing content.

`CONTINUE ATOMIC` remains the execution-resume command after state is already known. `APIAX07 RESYNC` is specifically for state/result resynchronization across conversations/devices.
## Active diagnostic mode — ChatGPT-PC channel isolated

Current temporary diagnostic state: ACTIVE.

Until explicitly ended with `END ISOLATION CHATGPT-PC`:
- continue API/BCP work without using ChatGPT-PC as the interactive execution/control/recovery/installation/LAN bridge;
- telemetry remains mandatory, but prefer already externalized BCP/GitHub/Drive/receipt evidence or BCP-native lightweight observability;
- do not ask the user to relay logs, commands, IPs, tokens, or screenshots when durable machine-readable evidence is available;
- `APIAX07 RESYNC` and `CONTINUE ATOMIC` must preserve this isolation mode automatically;
- do not regress or replay already COMMITTED work.

This is an A/B diagnostic isolation, not a conclusion that ChatGPT-PC causes platform checks.

## Strategic free-API / Model Broker / lightweight-cockpit extension

On every API recovery, also load:
- `docs/FREE_API_MODEL_BROKER_AUTONOMY_REQUIREMENTS.md`

This preserves the prior project discussion about:
- a provider-neutral Model Broker;
- legitimate free/zero-cost/BYOK model APIs such as Gemini/Flash-class and Groq-backed providers as replaceable examples;
- explicit quota/capacity/cost handling with DEFAULT_PAID_SPEND=0;
- bounded autonomous agent loops with deterministic verification and receipts;
- GitHub + BuildHub + B-EDGE execution/result loops;
- Telegram or an equivalent lightweight phone cockpit;
- no manual prompt/result/log shuttle by the user;
- using alternate legitimate adapters to reduce the operational impact of ChatGPT/browser/provider interruptions without bypassing safeguards.

Priority: preserve this direction now, but do not displace P0 field bring-up and continuity verification.

## Cumulative cahier-des-charges updates

On every recovery, load:
- `.project-memory/SPEC_EVOLUTION_POLICY.json`
- `docs/TELEGRAM_MISSION_COCKPIT_AND_PROGRESS_JOURNAL.md`

Canonical interpretation of “mise à jour du cahier des charges”:
- merge/refine/preserve the active specification;
- never restart the specification from the newest message;
- preserve prior requirements unless the user explicitly supersedes/deprecates them;
- preserve requirement history, evidence and regression obligations;
- ambiguous contradiction => `SPEC_CONFLICT_HOLD`, not silent replacement.

For long-running work, the target execution model is:
`Telegram/BCP mission intake -> durable mission envelope -> bounded micro-sprints -> append-only event journal -> receipts/checkpoints -> compact status`.

A short Telegram job code is a mission locator. `BCPGO <job_code>` may resolve it only through an actually qualified BCP integration; a typed number alone is not assumed to create network connectivity.

Progress reporting stores observable step/decision summaries and evidence. It does not depend on hidden model chain-of-thought.


## Cross-conversation repository writer fence

Mandatory on every recovery and mutation-capable turn:
- load `.project-memory/GIT_WRITER_LEASE_POLICY.json`;
- load `docs/GIT_WRITER_LEASE_AND_BRANCH_PROTOCOL.md`;
- treat every active ChatGPT conversation as a potentially concurrent writer;
- do not mutate canonical `main` autonomously;
- create/use one unique work branch per conversation/session/mission;
- re-read `main` before integration;
- if `main` moved, enter `REBASE_OR_RECONCILE_REQUIRED`;
- serialize merges and verify the final integrated SHA;
- preserve divergent useful work through recovery branches/draft PRs.

Conversation memory is not a Git lock. Parallel reasoning is allowed; parallel direct writes to canonical state are not.


## P0 mission autonomy recovery binding — 2026-09-19

Canonical requirement ID: `P0_MISSION_AUTONOMY_AND_OBSERVABLE_EXECUTION`.

BCPGO recovery MUST first read the durable mission/checkpoint state and continue from the next uncommitted action. A conversation boundary, network interruption, worker loss, or platform hold is not mission completion.

Before significant work, persist the mission envelope. Each bounded step produces observable event/evidence state. Model or agent workers are replaceable and cannot directly promote unvalidated output to canonical project state.

The current implementation line is BCP 0.5.1 candidate on a writer-fenced work branch. FIELD_VERIFIED remains false until exact-head CI, serialized integration, managed update/readback, interruption recovery, and human-first cockpit evidence pass.


## Telegram Human Cockpit V4 recovery binding — 2026-09-19

On every BCP recovery, load:
- `docs/TELEGRAM_HUMAN_COCKPIT_V4_INTERACTIVE_EXPORTS.md`;
- `.project-memory/TELEGRAM_COCKPIT_V4_STATE.json`;
- `release/telegram_observability.json`;
- `release/nexus_bootstrap.json`;
- `release/current.json`.

The cockpit target is one human-first editable Telegram card with read-only inline controls for refresh, exact position, missions, details, human PDF and technical PDF. It must remain truthful under ChatGPT verification/UI ambiguity, low bandwidth and direct PC->Telegram degradation. Nexus may serve cached sanitized reports, but BCP durable state remains authoritative.

No ChatGPT scheduled automation is part of this presence/update path. Do not require token re-entry, repeated manual ZIP replacement or user-mediated log transfer for normal updates.

The 2026-09-19 V4 implementation lives on its fenced candidate branch until exact-head CI, main-head reconciliation and serialized merge succeed. FIELD_VERIFIED remains false until a real Kinshasa button/PDF round-trip and resident update readback succeed.


## Universal continuation registry — 2026-09-20

Mandatory recovery inputs:
- `.project-memory/UNIVERSAL_CONTINUATION_CODE_REGISTRY.json`;
- `.project-memory/INTERACTIVE_WORK_CADENCE_POLICY.json`;
- `.project-memory/DELIVERY_REDUNDANCY_POLICY.json`;
- `.project-memory/PRE_HUMAN_ACTION_SIMULATION_POLICY.json`.

Resolution order:
`BCPGO / scoped alias -> durable project pointer -> writer-fence state -> exact checkpoint -> delivery policy -> cadence policy -> next uncommitted atomic action`.

Aliases do not fork project history. If an alias and `BCPGO <project>` resolve to different durable authorities, enter conflict hold rather than guessing.

Current/future projects inherit the 29–30 minute useful-work checkpoint cadence, targeting 30 minutes, by default when this context is available. Past chat transcripts are not rewritten; recovery must use durable project state rather than asking the user to reconstruct them.


### Email-first recovery invariant

On every `BCPGO` recovery, before any detailed ChatGPT checkpoint is shown:
- load `.project-memory/DELIVERY_REDUNDANCY_POLICY.json`;
- perform the useful-work tranche using the active 29–30 minute cadence, targeting 30 minutes, unless a real gate ends it earlier;
- send the complete human checkpoint by Gmail first when Gmail is available;
- after successful email delivery, the ChatGPT app response MUST be pointer-only and contain only: `MAIL_SENT`, Kinshasa date/time, and checkpoint ID;
- do not duplicate the detailed checkpoint body in ChatGPT after the email has succeeded;
- if email delivery fails, state the delivery hold truthfully and include only the minimum recovery instruction in ChatGPT.


### No-micro-beta field rule — R70

For the dedicated B-EDGE phone, do not ask the user to install another tiny delta merely because one component changed. The next field APK is admitted only as a coherent vertical slice that includes the full-node runtime, 24/7 lifecycle, local authenticated API, durable queue/memory, transport presence, permission onboarding, user-facing server dashboard, in-place update continuity and representative Android emulator checks. If any of those gates fail, fix and requalify in CI before another user install.

The old phone is a first-class BCP node. The Windows PC remains an important Windows/heavy-compute executor, but it must not be the sole communications center or the only place where durable orchestration state survives.

### Pre-human action simulation invariant

Before asking the user to click, install, authorize, reboot, retry, or replace a CURRENT artifact, load `.project-memory/PRE_HUMAN_ACTION_SIMULATION_POLICY.json` and exercise the exact path in representative CI/simulation when technically feasible. Windows actions should run on a Windows runner; Android behavior should use unit/lint/build and emulator/instrumented tests when the platform behavior matters. Simulation may qualify everything up to a real provider/user-consent boundary, but cannot be promoted to FIELD_VERIFIED without real field evidence. If simulation fails, keep fixing automatically and do not ask the user to repeat the same action.
