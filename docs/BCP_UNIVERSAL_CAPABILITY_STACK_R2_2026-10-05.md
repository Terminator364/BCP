# BCP Universal Capability Stack R2
Date: 2026-10-05
Status: PRECONCEPTION

## Universal execution ladder

For every requested effect, choose the highest-reliability/lowest-cost qualified provider.

1. INTERNAL BCP
   - state, queue, Chronicle, recipes, project registry, artifacts.

2. DIRECT API / CONNECTOR
   - GitHub, Drive, Telegram/Delivery, provider APIs.
   - Preferred for external services.

3. NATIVE OS / STRUCTURED CLI
   - Win32/WMI/CIM;
   - PowerShell cmdlets;
   - Git;
   - package managers;
   - project-specific CLIs.

4. DECLARATIVE DESIRED STATE
   - WinGet Configuration / DSC where appropriate.
   - Preferred for reproducible package/tool/settings state.

5. BUILD / SOFTWARE FACTORY
   - ChatGPT planning/code generation;
   - isolated worktree;
   - BuildHub build/test/package;
   - provenance/hash;
   - canary/install/register/update.

6. BROWSER SEMANTIC AUTOMATION
   - browser/provider connector first;
   - Playwright-style role/label/text locators and auto-waiting when local browser automation is needed;
   - no coordinate scripting as first choice.

7. WINDOWS GUI SEMANTIC AUTOMATION
   - Microsoft UI Automation tree/control patterns;
   - locate window/control by semantic properties;
   - read state before action;
   - verify state after action.

8. INPUT/VISION FALLBACK
   - keyboard/SendInput/coordinates/screenshots only when semantic automation is unavailable;
   - higher uncertainty;
   - stricter readback and timeout;
   - never use visual success alone when a machine-readable oracle exists.

9. HUMAN GATE
   - only irreducible physical/auth/security/ambiguity action.

## Software Factory

User intent:
"Crée-moi un petit logiciel qui fait X sur mon PC."

Normal path:
INTENT
-> requirements/context projection
-> create/modify source in isolated Git worktree
-> static checks
-> tests
-> BuildHub
-> package
-> hash/provenance
-> canary
-> register project/application
-> install through capability grant
-> create Desired State if the software is meant to stay healthy
-> update channel
-> receipt.

The user should receive the working software/outcome, not source code that they must manually place/build unless they explicitly ask for source.

## Research Factory

Research work is split:
- acquisition: connectors/APIs/browser;
- normalization: deterministic local transforms;
- indexing: disk-first;
- analysis/synthesis: ChatGPT or qualified reasoning provider;
- artifact publication: Delivery/Drive.

When ChatGPT is not active:
- deterministic acquisition/normalization/backlog work may continue;
- already-defined queries/data fetches may continue;
- novel semantic research questions requiring new reasoning move to NEEDS_REASONING rather than hallucinating.

## Windows GUI provider

Microsoft UI Automation is the preferred native GUI adapter because it exposes most desktop UI elements programmatically and supports automation clients/tests.

Capability examples:
- gui.window.find
- gui.control.query
- gui.control.invoke
- gui.control.set_value
- gui.selection.select
- gui.window.wait_state
- gui.dialog.read

Every UI action uses:
OBSERVE -> ACT -> READBACK.

GUI automation is scoped to explicitly authorized applications/windows.

## Browser provider

For local web automation:
- semantic locators by role/label/text/test ID;
- auto-wait/actionability;
- bounded navigation domains;
- secrets through credential provider, never prompt text;
- downloads registered as artifacts;
- auth/CAPTCHA moves to HUMAN_ACTION rather than bypass.

## Capability quality score

Candidate providers are ranked by:
1. determinism;
2. observability/readback;
3. resource cost;
4. failure isolation;
5. latency;
6. offline ability;
7. privilege requirement;
8. maintenance burden.

A lower layer is used only if higher layers cannot satisfy the effect.

## "Do anything" interpretation

The Fabric is not permitted to execute literally arbitrary unbounded actions.

It is designed so any authorized legitimate request can:
- map to an existing capability;
- trigger acquisition of a new bounded capability;
- or surface one precise irreducible blocker.

This is the operational meaning of universal.
