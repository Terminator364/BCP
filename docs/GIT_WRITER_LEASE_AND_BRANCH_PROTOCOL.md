# BCP — Git Writer Lease and Cross-Conversation Integration Protocol

Status: CANONICAL P0 SAFETY REQUIREMENT
Adopted: 2026-09-19

This policy applies to every active ChatGPT conversation, Work session, CI bot and future agent that can mutate the BCP repository.

## Hard rule

Many conversations may reason in parallel. Only fenced integration may advance canonical state.

Autonomous conversations MUST NOT make product mutations directly on `main`.

Normal path:
`READ_MAIN_HEAD -> UNIQUE_WORK_BRANCH -> SERIAL_MUTATIONS -> CI -> PR -> MAIN_HEAD_RECHECK -> RECONCILE_IF_MOVED -> ONE_SERIALIZED_MERGE -> READBACK`.

Each writer records:
- writer/session or mission identity;
- exact `base_main_sha`;
- intended file scope;
- expected CI gates.

If `main` moved, the candidate enters `REBASE_OR_RECONCILE_REQUIRED`. It is not merged blindly and does not inherit an older green CI result.

A CI result proves only the exact commit SHA it tested.

Useful divergent work is preserved on `recovery/*` branches and reconciled through draft PRs. Normal automation never force-pushes `main`.

## Conversation behavior

At the start of every mutation-capable turn:
1. load `.project-memory/GIT_WRITER_LEASE_POLICY.json`;
2. read current `main` SHA;
3. identify the conversation/session/mission writer;
4. use that writer's unique work branch;
5. perform serial mutations on that branch;
6. checkpoint branch head;
7. integrate only through the serialized merge fence.

A conversation that has stale state may continue analysis, but may not mutate canonical state until it reconciles.

## Relation to cahier des charges continuity

Specification updates follow `MERGE_REFINE_PRESERVE`. Git serialization prevents three conversations from independently rewriting the same canonical specification at the same time.

## Acceptance

The policy is FIELD/PROCESS verified only after two simulated or real concurrent writers:
- create separate branches;
- preserve both work lines;
- merge one;
- detect moved main on the second;
- reconcile and requalify;
- leave no useful work unreachable;
- never force-update main.
