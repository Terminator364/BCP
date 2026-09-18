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
