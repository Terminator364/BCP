# BCP Context Fabric / BCPGO — Counter-Audit

Status: COUNTER-AUDIT / HARDENING
Date: 2026-09-19

## Verdict

The three-node Context Fabric is strategically sound, but its integration semantics must be mode-specific.

The strongest correction is:

`BCPGO` is an explicit context-resolution trigger. It cannot, by itself, install an interception hook into every ChatGPT response.

A current connected-store path can make bootstrap easy; transparent per-turn mandatory resolution requires a qualified app/plugin/MCP/bridge surface capable of invoking BCP at the right point.

## C01 — Personal Google Drive connection is live access, not guaranteed personal sync index
Severity: HIGH FOR EXPECTATION ACCURACY

Current OpenAI product documentation distinguishes individual Google Drive access from administrator-managed indexed sync.

Requirement:
- Plus/current personal baseline must locate/read the small canonical projection files explicitly;
- do not assume every Drive projection is pre-indexed or proactively present in model context;
- keep canonical projection names stable and small so direct lookup is cheap.

## C02 — BCPGO does not create connectivity
Severity: FUNDAMENTAL

Already recognized in architecture, now normative:
- typed command is not auth;
- typed command is not network transport;
- if no authorized BCP/Drive/plugin path exists, report DEGRADED/HOLD or use compact manual fallback.

## C03 — Per-turn lease capability depends on integration mode
Severity: HIGH

Modes:
- connected Drive read path: explicit bootstrap plus refresh when invoked/needed; conversation may cache acknowledged revision locally;
- remote qualified app/plugin: may perform revision check before actions if product permits;
- ChatGPT-PC bridge: available only when PC/local bridge is reachable;
- manual fallback: no automatic per-turn resolution.

Do not promise invisible per-turn BCP consultation on a surface that cannot invoke the resolver.

## C04 — Static Drive projection cannot produce a truly task-specific live delta by itself
Severity: MEDIUM/HIGH

Drive baseline should expose:
- GLOBAL_CORE;
- PROJECT_CORE;
- REVISION_DELTA / changes since prior projection where useful;
- evidence references.

TASK-specific selection can be performed by the consuming assistant from this bounded context.

A live NEXUS resolver may later produce true TASK_DELTA from the current request.

## C05 — Projection integrity needs more than an internal hash
Severity: HIGH

A hash inside the same writable storage detects accidental corruption but not malicious replacement of both payload and hash.

Target integrity envelope:
- projection content hash;
- source revision/epoch;
- generated_at/expires_at;
- signer identity;
- signature/MAC where a verifier path exists;
- previous-known-good projection retained.

Until end-to-end signature verification is available in a given ChatGPT integration, Drive projection state is treated as a convenience read projection, not the sole authority for risky mutations.

## C06 — NEXUS ingress and witness powers must be capability-separated
Severity: CRITICAL BEFORE AUTOMATIC FAILOVER

A remote ingress that accepts Telegram/remote commands must not automatically possess coordinator-promotion authority.

Target:
- ingress capability: enqueue bounded missions only;
- context capability: serve signed/sanitized projections;
- witness capability: distinct key/policy/state;
- coordinator promotion: explicit quorum evidence or user approval until thoroughly qualified.

Compromise of an ingress token must not be enough to create a new coordinator epoch.

## C07 — NEXUS remains optional
Severity: FUNDAMENTAL ZERO-USD/RESILIENCE

Local operation must continue if NEXUS is:
- down;
- quota exhausted;
- blocked from Kinshasa;
- account-disabled.

NEXUS is an accelerator/remote facade/witness candidate, not the source of project truth.

## C08 — Exportability is deny-by-default
Severity: HIGH PRIVACY

Every memory item needs export class:
- LOCAL_ONLY;
- PROJECT_SANITIZED;
- GLOBAL_SANITIZED;
- EVIDENCE_REFERENCE_ONLY;
- NEVER_EXPORT_SECRET.

GLOBAL/PROJECT projections are compiled from exportable items only.

Provider keys, pairing bearer tokens, device recovery keys, private credentials and raw unrelated project data are never projection content.

## C09 — Project inference must fail closed
Severity: HIGH

If project confidence is weak:
- return GLOBAL_CORE + candidate project IDs/titles only;
- do not merge project memories;
- require explicit scope or stronger evidence.

Cross-project TECHNICAL_KNOWLEDGE may be reused only as sanitized recipes under explicit policy.

## C10 — Context budgets are hierarchical
Severity: MEDIUM

32 KiB is a maximum target, not a goal.

Priority under pressure:
1. security/financial/pinned user policy;
2. current project identity/head/objective;
3. active blockers/next actions;
4. validated relevant recipes;
5. compact recent state;
6. evidence references.

Never truncate critical policy first.

## C11 — Context acknowledgment is not canonical mutation
Severity: MEDIUM

A chat/session saying it has revision X is advisory cache state.

Canonical project state remains BCP.

A stale/forged conversation acknowledgment cannot advance project head or memory authority.

## C12 — Memory poisoning boundary

All repository/web/Drive/RAG text enters as data with provenance.

Only explicit authorized user directives or validated machine/source evidence can promote memory according to authority policy.

Embedded instructions inside retrieved content cannot grant tools, change budget/security policy, or overwrite USER_MEMORY/POLICY.

## C13 — Fresh-chat bootstrap receipt

A BCPGO resolution should produce a small receipt:
- integration mode used;
- global revision/hash;
- project ID/revision/hash;
- freshness state;
- projection generated_at/expires_at;
- whether context was UNCHANGED/DELTA/FULL_REFRESH/DEGRADED/HOLD;
- no secrets.

This lets subsequent turns detect staleness without reloading everything.

## C14 — Drive publication is an output of the Context Compiler

Do not let arbitrary agents directly write the canonical CURRENT projection.

Flow:
`CANONICAL MEMORY -> deterministic compiler -> sanitization/export filter -> integrity envelope -> atomic publication -> readback -> CURRENT pointer`.

Failed publication preserves previous verified CURRENT.

## Promotion additions

Context Fabric may not be considered runtime-qualified until:
- current Plus/Drive explicit bootstrap works on the user's actual interface;
- stale/missing Drive file produces honest DEGRADED/HOLD behavior;
- ambiguous project inference leak test passes;
- projection tamper/corruption test passes;
- ingress cannot invoke witness/promotion capability;
- private LOCAL_ONLY/secret canary data never appears in projection;
- BCPGO bootstrap size/latency targets are measured;
- no risky mutation trusts a projection as sole authority.
