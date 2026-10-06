# BCP Execution Fabric — Project Convergence Matrix
Status: PRECONCEPTION / INVENTORY-CANDIDATE
Date: 2026-10-05

| Project/system | Current role | Location observed | Target relationship | Background work candidates |
|---|---|---|---|---|
| BCP | control/continuity plane | Terminator364/BCP | **CORE / AUTHORITY** | mission scheduling, memory, receipts, routing, resource admission |
| ChatGPT-PC / 2003 / G6 | ChatGPT↔PC control corridor | Terminator364/ChatGPT-PC | **BRIDGE + CHATGPT ADAPTER**; no second mission kernel | context projection, mission submit/readback, update bridge |
| PC Command | Windows PowerShell cockpit/control | Terminator364/PC-COMMAND-STATE + runtime elsewhere | **WINDOWS CAPABILITY PACK + optional viewer** | diagnostics, services, logs, process inspection, safe maintenance |
| BuildHub | generic builds/recovery | Terminator364/BuildHub | **SPECIALIZED EXECUTOR** | build/test/package/hash/readback/sign/publish |
| ChatGPT Delivery | Telegram/Drive delivery | ChatGPT-PC + PROJECT-DRAFTS history | **DELIVERY PROVIDER**; not mission authority | staging, checksum, Drive publish, Telegram send/retry/readback |
| PhoneMouse | Android Bluetooth HID product | Terminator364/PhoneMouse | **SEPARATE PRODUCT / CLIENT** | builds, regression tests, packaging, release verification |
| P2PCR95 | Phone→PC Remote | Terminator364/P2PCR95 | **SEPARATE PRODUCT / CLIENT** | EXE/APK build, protocol tests, health checks, evidence |
| BROWSER4G | low-resource browser | repo placeholder + PROJECT-DRAFTS authority | **SEPARATE PRODUCT / CLIENT** | build, browser benchmark, resource tests |
| KINLINK | connectivity project | Terminator364/KINLINK | **CLIENT / ADAPTER** | bounded queries, network tests, evidence |
| PROJECT-DRAFTS | incubation repository | Terminator364/PROJECT-DRAFTS | **ENGINEERING INCUBATOR ONLY** | source organization; no live mission authority |
| AX150K | anticipation/error prevention | project history | **EXPERIENCE + REGRESSION PRODUCER** | error clustering, proposed regression tests, failure mining |
| HYDRA/TWINNODE | PC↔phone offload/resource design | historical specs | **ABSORB INTO NODE SCHEDULER** | offload decisions, phone capabilities, survival modes |
| Tunnel PC G3 | split-plane PC agent design | historical specs | **ABSORB SECURITY/PRIVILEGE PATTERNS** | privilege broker, update/readback, Drive transport |
| TLIB | library intelligence | project history | **PROJECT CLIENT** | parsing, dedupe, indexing, shards, L1/L2 checks |
| Excellentia | study/corpus engine | ChatGPT-PC subproject + history | **PROJECT CLIENT** | corpus checks, uniqueness, simulations, metrics |
| Med Rebuild | current software project | context-only in this audit | **PROJECT CLIENT; LOCATION TO REGISTER** | install tests, startup/healthcheck, logs, builds |
| Xenon | current project | context-only in this audit | **PROJECT CLIENT; LOCATION TO REGISTER** | sync diagnostics, tests, git checks, logs |
| Stade 8 | current project | context-only in this audit | **PROJECT CLIENT; LOCATION TO REGISTER** | checks, build, logs, maintenance |
| Minecraft Lab | Android/game experiment | historical context | **PROJECT CLIENT** | gated builds, package/hash checks, device validation |
| CRO | Delivery-derived project | historical context | **CLIENT / reuse Delivery provider** | delivery workflows without new transport stack |
| B-EDGE | dedicated edge coordinator | Terminator364/BCP/android-b-edge | **BCP NODE** | durable queue, Chronicle, capability registry, optional inference |
| BCP Nexus | remote ingress/egress/witness | Terminator364/BCP/nexus | **REPLACEABLE REMOTE ADAPTER** | webhook ingress, status, wake hints, witness |

## Shared capabilities — never reimplement per project

1. Durable mission queue / DAG.
2. Universal Chronicle.
3. Project Registry.
4. Capability Registry.
5. Resource Governor.
6. Model Broker.
7. Error/experience ledger.
8. Receipt/readback.
9. Rollback/update framework.
10. Telegram cockpit.
11. Drive artifact/recovery transport.
12. ChatGPT bridge.
13. Windows privileged broker.
14. Windows process containment.
15. Background scheduler.
16. Offline/reboot recovery.
17. Hash/integrity primitives.
18. BuildHub dispatch.
19. Delivery dispatch.
20. Local-inference adapters.

## Target project-adapter contract

Each project registers metadata and commands instead of creating infrastructure:

```json
{
  "project_id": "med-rebuild",
  "aliases": ["Med Rebuild", "Main Reboot"],
  "origins": {"local_roots": [], "repos": [], "drive_refs": []},
  "commands": {"build": null, "test": null, "lint": null, "install_test": null, "healthcheck": null},
  "permissions": {"read": true, "project_write": "POLICY", "system_modify": "GATED"},
  "resource_profile": "CONSTRAINED_PC",
  "artifact_policy": "PROJECT_DEFINED"
}
```

Unknown fields remain UNKNOWN until observed. BCP must not invent paths, repositories or commands.

## Background work portfolio

**Interactive / high priority:** installer repair, current build failure, active sync failure, requested file transformation, current health diagnosis.

**Normal project:** smoke tests, git/worktree verification, dependency checks, updater validation, release-manifest/readback.

**Background improvement:** TLIB indexing/deduplication, Excellentia corpus audits/simulations, AX150K regression mining, library metadata extraction, stale-artifact cleanup, hash verification, documentation consistency, cache preparation.

A background job moves to WAITING_RESOURCE rather than competing with the user's foreground session.

## Immediate inventory gaps

These should be discovered by the PC capability probe instead of asking the user to manually reconstruct them:
- exact local roots for Med Rebuild, Xenon and Stade 8;
- exact runtimes/build/test commands;
- currently installed/running project components;
- Drive Desktop mount and disk headroom;
- PowerShell/Git/Node/Python versions;
- installed BCP/ChatGPT-PC/PC Command runtime state;
- actual idle RAM/commit/pagefile/process baseline;
- reusable Telegram/Delivery configuration;
- local model files already present.