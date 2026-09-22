# R89 — BCP Anti-Reinvention Benchmark

Status: RESEARCHED / DESIGN-DELTA-ONLY / NO PRODUCT BYTES CHANGED  
Canonical base: `f40879b234ea619eff82445eedb5802796d1f9d8`  
Date: 2026-09-22

## 1. Why R89 exists

BCP has accumulated strong backend capabilities faster than its human-facing product shell.

The current Android candidate already has Room, Chronicle/events, mission-step durability, queue/store-and-forward, capability registry, memory claims, local TLS API, discovery, pairing, resource governor, update logic and recovery hooks. The problem is not that these concepts are missing.

The problem is that the UI exposes them mostly as:
- one vertically scrolling screen;
- a small set of summary cards;
- ten diagnostics/actions inside one `AlertDialog`;
- raw JSON dumped into one monospaced text block.

That is a product-UX bottleneck, not a missing-architecture problem.

The R89 rule is therefore:

> **Do not invent a new UI pattern when a mature project has already solved the same human problem. Reuse the proven interaction model, adapt it to BCP's constraints, and preserve the existing backend.**

## 2. Canonical BCP requirements that matter here

The A+B+C specification already requires a real server cockpit on the dedicated phone, including:
- state;
- queues;
- memory;
- transports;
- permissions;
- health;
- diagnostics;
- version/update state;
- recovery;
- onboarding tied to actual Android capabilities;
- bad-network/offline behavior as normal operating conditions;
- minimal repeated user work.

Therefore R89 does **not** add a new requirement. It operationalizes an existing C-layer requirement using proven external patterns.

## 3. Current BCP Android UI — exact reality

Current implementation: `MainActivity.java`.

### Main screen

The app builds one programmatic Java `ScrollView` with:
1. global status/detail;
2. node/server card;
3. autonomy/transports card;
4. capability card;
5. permissions/server-mode card;
6. action card;
7. raw JSON/text output.

### Diagnostics/settings

`PARAMÈTRES / DIAGNOSTIC` opens one list dialog with:
- node state;
- permissions/autonomy;
- versions;
- ChatGPT-PC state;
- repair ChatGPT-PC;
- update PC server;
- update BCP Edge;
- orchestrator/memory;
- capability registry/sources;
- quick B-EDGE test.

This mixes:
- configuration;
- repair;
- update;
- diagnostic;
- observability;
- destructive/sensitive actions

inside one modal list.

### Existing emulator proof is narrower than real UX proof

The current Android Human-Action Simulation proves:
- app launches;
- the main scroll changes;
- key text becomes visible after scrolling;
- local TLS API is live;
- capability flags are correct;
- cold relaunch works.

It does **not** prove:
- the Settings/Diagnostic flow is usable;
- a user can understand what is wrong without raw JSON;
- mission/history/queue drill-down;
- repair issue prioritization;
- device/pairing detail ergonomics;
- search/filter;
- first-time onboarding comprehension;
- recovery from permission denial;
- execution/receipt history UX.

So “human-action simulation PASS” must not be interpreted as “BCP UI finished.”

## 4. High-signal references

This benchmark intentionally uses a small set of mature, high-signal references rather than thousands of low-signal screenshots.

### 4.1 Home Assistant Companion — primary UX reference

Sources:
- https://github.com/home-assistant/android
- https://companion.home-assistant.io/docs/getting_started/
- https://companion.home-assistant.io/docs/gallery/android/
- https://www.home-assistant.io/integrations/repairs/
- https://www.home-assistant.io/integrations/system_health/
- https://companion.home-assistant.io/docs/integrations/android-home-app-launcher/

Patterns already solved:
- automatic local discovery first;
- manual fallback second;
- onboarding as discrete stages;
- per-feature settings;
- permissions requested in context;
- dedicated System Health;
- Repairs inbox for actionable problems;
- dedicated logs/troubleshooting;
- optional dedicated-device / launcher mode.

**BCP adoption:** high.

BCP should not copy Home Assistant wholesale or become WebView-first. The useful part is the **information architecture** and **progressive disclosure**.

### 4.2 Syncthing / Syncthing-Fork — state and device UX reference

Sources:
- https://github.com/syncthing/syncthing
- https://docs.syncthing.net/intro/gui
- https://github.com/mbrukman/syncthing-fork-android

Patterns already solved:
- top-level separation of Devices / Folders / Status;
- explicit named runtime states;
- progress visible beside the object it belongs to;
- UI explains why syncing is or is not happening;
- nearby discovery;
- recent changes;
- battery-aware background behavior.

**BCP adoption:** high for state vocabulary, object lists, reason/status presentation.

### 4.3 Tailscale — trust and device onboarding reference

Sources:
- https://tailscale.com/docs/features/access-control/device-management
- https://tailscale.com/docs/features/access-control/device-management/device-approval
- https://tailscale.com/docs/install/android

Patterns already solved:
- Machines/device list;
- explicit trust state such as “Needs approval”;
- one approval action followed by immediate connectivity;
- QR/code fallback;
- no manual-IP workflow as the normal path.

**BCP adoption:** high for pairing/trust UX.

### 4.4 KDE Connect — phone/PC relationship reference

Source:
- https://github.com/KDE/kdeconnect-android

Patterns already solved:
- separate connected and available devices;
- pair once;
- expose capabilities per paired device;
- local Wi-Fi + TLS;
- familiar “device first, features second” mental model.

**BCP adoption:** high for Devices screen.

License note: KDE Connect is GPL. Use the pattern unless a deliberate compatible code-use decision is made.

### 4.5 LocalSend — local discovery and secure peer UX reference

Sources:
- https://github.com/localsend/localsend
- https://github.com/localsend/protocol/blob/main/README.md

Patterns already solved:
- nearby-device-first UI;
- multiple discovery methods because LANs are unreliable;
- HTTPS;
- certificate fingerprint as stable peer identity;
- human alias plus technical identity;
- prepare/accept/reject flow;
- no external server required.

**BCP adoption:** very high for LAN/device-discovery presentation.

### 4.6 Temporal Web UI — mission/receipt/history reference

Sources:
- https://github.com/temporalio/ui
- https://docs.temporal.io/web-ui

Patterns already solved:
- list executions;
- status filtering;
- timeline history;
- compact grouped history;
- workers;
- pending activities;
- relationships;
- human summary + full JSON detail;
- retry/cancel/reset actions when safe.

**BCP adoption:** very high for Mission/Chronicle UI.

BCP already owns the data required for much of this. The missing piece is presentation.

### 4.7 n8n — executions reference

Sources:
- https://github.com/n8n-io/n8n
- https://docs.n8n.io/build/understand-workflows/understand-executions/view-all-executions/
- https://docs.n8n.io/build/understand-workflows/understand-executions/view-executions-for-a-single-workflow/

Patterns already solved:
- Executions tab;
- Failed / Running / Success / Waiting filters;
- retry failed execution from history;
- execution history kept conceptually separate from workflow-definition history.

**BCP adoption:** high.

### 4.8 Node-RED — diagnostics reference

Sources:
- https://github.com/node-red/node-red
- https://nodered.org/docs/user-guide/editor/sidebar/
- https://nodered.org/docs/user-guide/editor/workspace/nodes
- https://nodered.org/docs/user-guide/handling-errors

Patterns already solved:
- status displayed close to the component;
- error marker with reason;
- dedicated Debug view;
- dedicated Context view;
- error navigates back to affected object.

**BCP adoption:** high for diagnostics; **do not** copy the canvas editor.

### 4.9 Cockpit — server appliance cockpit reference

Sources:
- https://github.com/cockpit-project/cockpit
- https://cockpit-project.org/

Patterns already solved:
- Overview;
- Networking;
- Storage;
- Logs;
- Services;
- software updates;
- multi-machine switching;
- direct reflection of real system state.

**BCP adoption:** high for the dedicated-phone server cockpit hierarchy.

### 4.10 Portainer — multi-environment admin reference

Sources:
- https://github.com/portainer/portainer
- https://docs.portainer.io/admin/environments

Pattern:
- an Environments list is the single entrance to multiple managed nodes;
- auto-onboarding;
- one detail page per environment.

**BCP adoption:** secondary/future for PC/B-EDGE/Nexus multi-node administration.

### 4.11 Android official platform guidance

Sources:
- https://developer.android.com/design/ui/mobile/guides/layout-and-content/layout-and-nav-patterns
- https://developer.android.com/training/permissions/requesting
- https://developer.android.com/training/permissions/usage-notes

Platform constraints:
- 3–5 primary destinations are a familiar mobile navigation pattern;
- primary actions should remain prominent; secondary actions go into overflow/detail;
- request permissions in context;
- explain what feature is affected;
- gracefully degrade after denial;
- do not ask for every permission on startup;
- adapt layout to screen size.

This is not optional style guidance when it intersects permission behavior.

### 4.12 Banking/payment transaction tunnels — state + next action + asynchronous truth

Primary industry references:
- https://docs.adyen.com/account/payments-lifecycle
- https://docs.adyen.com/online-payments/build-your-integration/payment-result-codes

Adyen's payment UI/API model separates:
- intermediate states such as Received / Pending / PresentToShopper;
- final outcomes such as Authorised / Cancelled / Refused / Error;
- an explicit action to take for each non-final state;
- asynchronous confirmation for outcomes that are not final at the first response.

BCP should adopt the **interaction contract**, not payment-domain semantics:

`RECEIVED -> WAITING | ACTION_REQUIRED | PROCESSING -> RESULT_COMMITTED | FAILED_SAFE`

Rules:
- never show SUCCESS merely because an operation was accepted;
- always show the current state and the next action;
- if the final provider outcome is unknown, show `RECONCILING`, not success or generic failure;
- durable receipt/readback is the analogue of the final payment confirmation;
- raw provider/transport details belong behind Technical details.

This directly strengthens BCP communications, updates, pairing, missions and recovery without adding a new backend subsystem.

## 5. Visual/video references

Useful visual references:
- Home Assistant Android gallery: https://companion.home-assistant.io/docs/gallery/android/
- LocalSend Android ↔ Windows walkthrough: https://www.youtube.com/watch?v=Gm3_CM6NAsU
- KDE Connect Android ↔ Windows pairing/capabilities walkthrough: https://www.youtube.com/watch?v=y57I0lKPBHk

These are reference flows, not sources of canonical truth.

## 6. Source/license rule

BCP may freely **learn a pattern** from a public product.

Copying implementation code is a separate decision.

Examples:
- Home Assistant Android: Apache-2.0;
- Node-RED: Apache-2.0;
- Temporal UI: MIT;
- Syncthing: MPL-2.0;
- KDE Connect: GPL-2.0/GPL-3.0;
- Cockpit: mixed LGPL/GPL.

Therefore:
- architecture/UX pattern reuse: allowed as design inspiration;
- direct source copy: only after file-level license compatibility review;
- GPL/MPL material: default to pattern-only unless an explicit license decision is made;
- future BCP source comments/docs should name major inspirations where useful.

## 7. The most important comparison: BCP vs proven patterns

| Human problem | BCP now | Proven pattern | R89 decision |
|---|---|---|---|
| “Is BCP healthy?” | long summary cards | Cockpit Overview + HA System Health | ADOPT |
| “What needs my action?” | mixed into status text/dialog | HA Repairs | ADOPT |
| “What happened?” | backend Chronicle exists, no proper UI | Temporal timeline / n8n Executions | ADOPT |
| “What is running/waiting/failed?” | backend mission states, not human list | Temporal/n8n/Syncthing statuses | ADOPT |
| “Which devices exist?” | auto-connect + pairing dialog | Tailscale/KDE/LocalSend device list | ADOPT |
| “Why is this device unavailable?” | diagnostic text/raw JSON | Syncthing reason/status | ADOPT |
| “How do I pair?” | automatic flow + one confirmation dialog | Tailscale/KDE/HA discovery flow | ADAPT |
| “What permissions are missing?” | aggregated server-mode flow | Android/HA per-feature contextual prompt | ADAPT |
| “How do I repair?” | diagnostic menu actions | HA Repairs | ADOPT |
| “How do I inspect internals?” | JSON dumped into main output | Node-RED Debug/Context + Temporal JSON detail | ADOPT |
| “How do I see transports?” | one text block | Cockpit Networking + LocalSend/Tailscale peer detail | ADAPT |
| “How do I see memory/queue?” | counts only | Temporal pending/history + Node-RED Context | ADAPT |
| “How do I know update state?” | buried in diagnostic menu | Cockpit/HA Updates | ADOPT |
| “How do I use dedicated phone?” | server mode button | HA dedicated launcher/kiosk pattern | KEEP_OPTIONAL |

## 8. Minimal BCP UI target — no new backend architecture

Android official guidance recommends 3–5 primary destinations. BCP needs exactly four.

### 1. Home

Purpose: answer in <5 seconds:
- Is the node healthy?
- Is PC reachable?
- Is BCP operating offline safely?
- Is there something I must do?

Content:
- single global state: `READY / DEGRADED / ACTION_REQUIRED / RECOVERING / OFFLINE_LOCAL_OK`;
- one-sentence reason;
- node identity/version;
- PC state;
- network/transports;
- queue/mission counts;
- one “Action required” card if applicable;
- recent 3 meaningful events.

No raw JSON.

### 2. Activity

Backed by **existing** Chronicle + mission-step tables.

Views:
- Running;
- Waiting;
- Failed/Needs action;
- Completed.

Detail:
- timeline;
- checkpoint/receipt;
- provider state;
- next safe action;
- retry/reconcile only when policy allows;
- Technical details collapsible.

This borrows Temporal/n8n interaction models without importing their engines.

### 3. Devices

Backed by **existing** discovery/pairing/transports.

Sections:
- This B-EDGE;
- Paired PC;
- Available nearby;
- Nexus/remote endpoint when applicable.

Each device shows:
- name;
- trusted/pending/offline state;
- last seen;
- transport;
- TLS/pin state;
- capabilities;
- one clear next action.

This borrows Tailscale/KDE/LocalSend.

### 4. System

Grouped subsections:
- Health & Repairs;
- Permissions & 24/7;
- Storage & memory;
- Queue/Chronicle;
- Capabilities;
- Network & transports;
- Updates & version;
- Diagnostics & logs;
- Advanced.

This borrows Home Assistant + Cockpit.

The existing ten-item settings dialog disappears as the primary information architecture. Advanced destructive/debug actions may remain behind confirmation.

## 9. Repairs model

BCP already has enough machine truth to generate Repairs without a new database.

Examples:
- battery optimization active;
- nearby-device permission missing;
- TLS/pin mismatch;
- PC unreachable;
- stale capability;
- queue stuck;
- provider delivery OUTCOME_UNKNOWN;
- update mismatch;
- low storage;
- Chronicle/readback failure;
- relay unavailable.

Each Repair card must contain:
1. **what is wrong**;
2. **what is affected**;
3. **whether BCP remains safe**;
4. **the one recommended action**;
5. technical details behind disclosure.

This is a direct adaptation of Home Assistant Repairs, not a new subsystem.

## 10. Status vocabulary

Human UI should not dump all internal states directly.

### Global UI states

- `READY`
- `OFFLINE_LOCAL_OK`
- `DEGRADED`
- `ACTION_REQUIRED`
- `RECOVERING`
- `FAILED_SAFE`

### Object states

Mission/device/capability can retain their richer machine states underneath.

This follows Syncthing/Temporal: many machine states, few understandable top-level human states.

## 11. Permission UX

Current BCP server-mode setup is directionally correct but too aggregated.

Adopt Android/Home Assistant behavior:
- request Nearby Devices when local discovery is first enabled/needed;
- explain exactly which discovery path is lost if denied;
- request notification permission when foreground server operation requires it;
- battery unrestricted remains a separate “reliability improvement” step, not disguised as a normal runtime permission;
- denial must leave the app usable in degraded mode;
- System > Permissions shows status and impact.

No repeated nag loop.

## 12. What BCP should NOT copy

Do not:
- turn BCP into a Home Assistant clone;
- import a giant web frontend;
- add Node-RED canvas editing;
- add Portainer container concepts;
- copy Temporal backend architecture;
- add Tailscale's cloud identity model;
- import Syncthing's sync engine;
- add UI frameworks merely because references use them.

The goal is to copy **solved human interaction patterns**, not foreign product architecture.

## 13. Implementation rule for the next Android candidate

Because the user explicitly wants to avoid repeated installations, the current 2.2 package should **not** be presented as the final human gate merely because its backend is machine-qualified.

R89 recommends a temporary product hold:

`MACHINE_QUALIFIED_2_2 / HUMAN_INSTALL_DEFERRED_PENDING_COHERENT_UI_CONVERGENCE`

This is not a safety rollback. It is a productization decision.

Before the next human install, one coherent candidate should add:
1. four-destination information architecture;
2. Home health/action-required summary;
3. Activity timeline over existing Chronicle/mission state;
4. Devices page over existing discovery/pairing data;
5. System/Repairs/permissions/update sections;
6. human-readable result rendering with raw JSON only as Technical details;
7. emulator navigation tests for all four destinations;
8. repair/actionability tests;
9. onboarding/pairing UX test;
10. current transport/security/runtime regression suite unchanged.

No new database schema is required for this UI convergence unless implementation proves a specific missing query.

## 14. Human-action simulation must become a real UX test

The current workflow proves scrollability and text presence.

The next workflow should additionally prove:
- navigation to all four destinations;
- Home has one visible global state;
- Activity can show at least one seeded event/mission and open detail;
- Devices can show local node + paired/unpaired fixture states;
- System can open Health/Repairs and Permissions;
- a seeded repair shows reason + affected feature + action;
- technical JSON is hidden by default and expandable;
- no horizontal clipping at 320×640;
- back navigation returns to the expected parent;
- state persists across cold relaunch.

Screenshots should be captured for each primary destination, not just top/bottom of one long page.

## 15. Anti-reinvention source comments

Where an implementation consciously follows an external pattern, use a short comment only when it helps maintainers, for example:

```text
// UX pattern: Home Assistant Repairs — actionable issue + effect + repair.
// BCP implementation is independent and backed by local BCP machine truth.
```

or:

```text
// Interaction pattern: Temporal execution history — summary first, timeline detail,
// raw event JSON behind explicit technical disclosure.
```

Do not litter every file with attribution when a design document already records the source.

## 16. Recommended sequence

### R89 — now
Research + benchmark + product hold decision only.

### R90 — one cohesive UI convergence tranche
Implement the four-screen shell and map **existing** backend data into it.

### R91 — emulator/user-flow qualification
Seed deterministic fixtures, navigate every primary flow, capture screenshots, fix regressions.

### Then — one human install
Publish/sign/Drive-readback the UI-converged 2.2 candidate and ask for **one** in-place install.

This is faster overall than installing backend-complete/UI-incomplete 2.2 now and asking the user to install again immediately after UI fixes.

## 17. Final R89 conclusion

The user’s “do not reinvent the wheel” criticism is supported by the code and test evidence.

BCP has already solved much of A and B internally. The remaining visible gap is disproportionately C: product information architecture, human state presentation, repair UX and execution/device drill-down.

The correct move is **not another architecture cycle**.

The correct move is:
- reuse Home Assistant for onboarding/repairs/system-health patterns;
- Syncthing for state/reason/progress;
- Tailscale/KDE/LocalSend for device trust/discovery;
- Temporal/n8n for mission/execution history;
- Node-RED for debug/context presentation;
- Cockpit for server cockpit hierarchy;
- Android official guidance for navigation and permissions;
- keep BCP’s own durable backend and security model.

That is “paint and modernize the wheel,” not reinvent it.

