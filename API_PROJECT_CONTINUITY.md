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
