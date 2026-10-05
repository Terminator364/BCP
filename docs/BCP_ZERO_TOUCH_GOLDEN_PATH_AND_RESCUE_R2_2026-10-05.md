# BCP Zero-Touch Golden Path & Rescue Contract R2
Date: 2026-10-05
Status: PRECONCEPTION

## 1. Mandatory Golden Path

For any request that implies machine work:

USER/CHATGPT INTENT
-> BCP intent compilation
-> current project/context projection
-> existing capability lookup
-> durable mission / desired-state update
-> execution
-> verifier/readback
-> receipt
-> concise user outcome.

If an appropriate qualified capability already exists, ChatGPT MUST dispatch it rather than produce manual technical instructions.

If no capability exists, route to Capability Factory.

## 2. Manual artifact prohibition

Normal mode MUST NOT ask the user to:
- download a generated CMD/PS1 repair file;
- paste a command into PowerShell/CMD;
- move a generated file into a local project directory;
- copy terminal logs back to ChatGPT;
- repeatedly relaunch a process after recoverable failure.

These outputs are allowed only under:
`PHYSICAL_RECOVERY_ONLY`
or when the user explicitly asks for the raw script/source.

## 3. Broken execution channel

A broken Desktop Commander does not justify immediate manual fallback.

Fallback order:
1. BCP native local executor;
2. existing G6/ChatGPT-PC control bus;
3. B-EDGE/LAN path;
4. Drive/Nexus store-forward to local executor;
5. approved startup/rescue controller;
6. physical rescue only if no qualified machine path remains.

## 4. BCP Rescue Plane

The platform needs a minimal recovery path independent of normal feature modules.

Properties:
- local;
- low RAM;
- no model;
- LKG-aware;
- validates active core;
- repairs/reverts core from local signed/hashed rescue assets;
- restores one primary startup registration;
- verifies SQLite/authority state;
- does not depend on Drive/GitHub/Telegram/ChatGPT for local LKG recovery.

Reuse G6 Rescue bundle / A-B boot / Package Head / Recovery Plane contracts rather than inventing parallel machinery.

## 5. Self-healing platform layers

Layer A — project desired state
Layer B — capability health
Layer C — BCP core health
Layer D — rescue/LKG health

A higher layer can repair the layer immediately above it; cycles are forbidden.

Example:
- Med Rebuild controller repairs its launcher;
- CapabilityController repairs the launcher capability/provider;
- Core Recovery Plane repairs CapabilityController/runtime;
- Rescue Plane repairs/reverts the core.

## 6. Talk-only enforcement

The ChatGPT-side planner should classify machine-effect requests.

If `machine_effect=true`:
- it may explain what it is doing;
- but explanation does not replace dispatch when an authorized BCP path exists.

If all automated paths are unavailable:
- return exact blocker;
- attempt recovery;
- expose one minimum human action only after recovery paths are exhausted.

## 7. Friction regression

A generated repair script manually launched by the user is automatically classified:
`FRICTION_EVENT: MANUAL_EXECUTION_ARTIFACT`.

After the platform has a capability for the same causal operation, recurrence is a release-blocking regression for zero-touch certification.

## 8. Reference: current Med Rebuild / Commander class

Old flow:
ChatGPT -> generated installer/recovery file -> user downloads/runs -> console -> screenshot -> next repair.

Target:
ChatGPT -> BCP mission -> Commander capability and MedRebuild branches -> automated repair/test/readback -> result.

If Commander itself is the broken capability, BCP uses the native/rescue execution plane; Commander cannot be required to repair Commander.


## 9. Optional-provider rule

The Golden Path must never prefer a metered compatibility provider when a qualified native/local capability can perform the same effect.

Desktop Commander:
- classification: optional metered accelerator / compatibility provider;
- never canonical runtime authority;
- never required for bootstrap, local recovery, mission durability or core Windows effects;
- quota exhaustion is a provider-health event, not a platform failure.

Manual fallback remains forbidden merely because a provider quota is exhausted. The system must exhaust qualified machine alternatives first.
