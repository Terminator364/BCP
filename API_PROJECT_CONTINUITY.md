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
