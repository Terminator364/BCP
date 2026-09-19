# BCP Git Writer Lease and Branch Protocol

Status: CANONICAL INTEGRATION SAFETY REQUIREMENT
Adopted: 2026-09-19

## Incident that motivated this rule

During parallel BCP/B-EDGE work, multiple autonomous conversations wrote repository contents at nearly the same time from different observed `main` heads.

The result was real Git divergence:
- workflow runs existed for commits no longer reachable from the current `main`;
- useful BCP 0.6 / B-EDGE V2 work existed on competing lines;
- CI results could refer to a commit that was already superseded by another writer.

This is a repository-level split-brain problem.

## Hard rule

Autonomous agents/conversations MUST NOT write product changes directly to `main`.

Normal mutation path:

```
READ main HEAD
  -> create unique work branch at exact HEAD
  -> perform serial file mutations on that branch
  -> run CI / self-tests
  -> open PR
  -> re-read main HEAD
  -> reconcile if main moved
  -> merge one integration candidate at a time
  -> verify merged SHA + CI
```

Direct-to-main writes are reserved for explicit human emergency repair and must still be immediately audited.

## Branch identity

Each logical writer gets one unique branch:

`work/<project>/<session-or-mission-id>`

Recovery branches use:

`recovery/<purpose>-<date>`

The writer records:
- writer/session ID;
- project/mission;
- `base_main_sha`;
- creation timestamp;
- intended file scope;
- expected CI gates.

## Writer lease semantics

There are two separate leases:

### 1. Work-branch lease
The writer owns only its branch and may update it serially.

No other autonomous writer should mutate that branch unless explicitly taking over the mission.

### 2. Integration lease
Only one integration operation may advance `main` at a time.

Before merge:
1. fetch current `main` HEAD;
2. compare it with the PR base observed during qualification;
3. if `main` moved, recompute mergeability and required CI;
4. never force-update `main` to bypass divergence;
5. merge with the exact expected PR head SHA;
6. read back `main` and verify the merge commit/revision.

A stale integration candidate enters `REBASE_OR_RECONCILE_REQUIRED`, not `MERGE_ANYWAY`.

## Contents API discipline

Create/update/delete file operations are serialized inside one branch.

Writers MUST NOT fire concurrent writes against the same branch.

The blob SHA of a file is not sufficient as a global repository-head lease. A writer must also remember the branch base/head it observed.

## CI discipline

CI belongs to an immutable commit SHA.

A green run for commit A does not prove commit B.

Promotion requires:
- candidate commit SHA;
- all required gates for that exact SHA;
- release manifest hashes matching that exact SHA/content;
- no newer unqualified main commit substituted silently.

Cancelled runs are not PASS.

## Release publication fence

Drive CURRENT / release CURRENT MUST be generated only from the exact qualified integration SHA.

Publication receipt records:
- source commit SHA;
- PR/merge identity;
- artifact SHA-256;
- coordinated component versions;
- requirements revision;
- CI run IDs;
- field-verification state.

If source SHA no longer matches the intended integration head, publication stops.

## Divergence recovery

When an unreachable/superseded useful commit is detected:
1. create a `recovery/*` branch at the exact commit SHA;
2. open a draft PR against current `main`;
3. compare changed files and requirements;
4. cherry-pick/reimplement/reconcile only the useful deltas;
5. never move `main` backward or force-push merely to recover work.

## Multi-conversation rule

BCP treats every ChatGPT conversation, Work session, CI bot and future agent as a potentially concurrent writer.

Conversation memory is NOT a Git lock.

Before any repository mutation, the agent must:
- load this policy;
- discover current `main` SHA;
- use or create its mission branch;
- avoid direct main mutation.

## Repository single-writer principle

The repository follows the same principle as B-EDGE/PC canonical state:

**many workers may compute in parallel; only a fenced integration path may advance canonical state.**

Parallel reasoning is encouraged.
Parallel direct writes to canonical `main` are prohibited.

## Acceptance tests

The protocol is not considered effective until tests prove:

1. two simulated writers start from the same `main`;
2. both create separate branches;
3. both can commit without overwriting each other;
4. first PR merges;
5. second writer detects moved `main`;
6. second PR must reconcile/requalify before merge;
7. no useful commit becomes unreachable;
8. artifact publication references the exact merged SHA;
9. force update of `main` is never used by normal automation.

## Current recovery evidence

The 2026-09-19 counter-audit preserved divergent work as draft recovery PRs rather than discarding it.

This policy supersedes the earlier implicit assumption that separate file updates on `main` were safe simply because they touched different paths.
