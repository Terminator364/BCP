# Dual-Conversation Continuity Architecture

Status: DESIGN REQUIREMENT / API CORE
Date: 2026-09-19

## Goal

Allow two ChatGPT conversations to participate in one project without creating two competing writers.

Roles:
- **ACTIVE**: current conversation holding the writer lease.
- **STANDBY**: hot spare that may read canonical state but may not mutate while ACTIVE's lease is valid.

BCP, not either conversation, is the canonical execution-state authority.

## Canonical records

BCP must maintain at minimum:

```json
{
  "project_id": "api",
  "revision": 42,
  "mission": "...",
  "last_committed_action": "A42",
  "next_atomic_action": "A43",
  "writer": {
    "conversation_id": "opaque-local-session-id",
    "lease_id": "lease-...",
    "fencing_token": 107,
    "expires_at": "..."
  },
  "running_jobs": [],
  "receipts": [],
  "platform_state": "NORMAL|PLATFORM_VERIFICATION_HOLD|RATE_LIMIT_429|TOOL_TRANSIENT",
  "updated_at": "..."
}
```

Conversation identifiers are operational opaque IDs only; they are not trusted as authorization by themselves.

## Writer lease

Every mutation requires:
- project revision precondition;
- valid unexpired lease;
- monotonic fencing token;
- idempotency key;
- receipt/readback.

If ACTIVE disappears:
1. no immediate competing write;
2. wait until lease expiry or explicit clean release;
3. STANDBY reads canonical state;
4. STANDBY obtains a new lease with a higher fencing token;
5. STANDBY executes only `next_atomic_action`.

If old ACTIVE later returns, its older fencing token is rejected. It becomes observer until it reacquires a fresh lease.

## Conversation interruption handling

When an additional-verification hold appears:
- classify it as `PLATFORM_VERIFICATION_HOLD`;
- do not mark the project failed;
- do not cancel already-dispatched bounded jobs merely because the conversation is paused;
- persist the last known conversation stage when possible;
- allow STANDBY to take over only after lease rules permit it.

The architecture does not try to circumvent the platform check. It only prevents that check from becoming a single point of failure for project continuity.

## Running jobs

Jobs already dispatched to ChatGPT-PC / B-EDGE / BuildHub may continue independently if their execution contract is already complete and bounded.

The canonical job record must expose:
- job_id;
- operation name;
- parameters hash;
- state: QUEUED/RUNNING/PASS/FAIL/HOLD;
- progress if available;
- started_at / updated_at;
- artifact/receipt hashes;
- owning fencing token.

A conversation resuming later asks BCP for job state rather than reissuing the job blindly.

## Handoff commands

- `APIAX07`: cold recovery when the conversation has lost state.
- `CONTINUE ATOMIC`: same-conversation lightweight continuation after an interrupted turn.
- Future recommended command: `TAKEOVER SAFE`: STANDBY requests writer takeover after lease expiry and resumes exactly one atomic action.
- Future recommended command: `OBSERVE`: read-only project/job status with no lease acquisition.

These are convenience phrases; the underlying correctness comes from BCP leases, revisions, fencing and idempotency.

## Safety and scope

Dual-conversation operation must not be used to evade platform safeguards. If both conversations independently enter a platform verification hold, BCP simply preserves state and waits.

## Field test

A mandatory field scenario before this feature is called complete:

1. ACTIVE acquires lease and starts bounded job J.
2. ACTIVE turn is intentionally stopped or otherwise interrupted.
3. J continues or remains durably queued without duplicate dispatch.
4. STANDBY reads checkpoint.
5. After lease expiry, STANDBY obtains a higher fencing token.
6. STANDBY resumes the next uncommitted action.
7. Original ACTIVE returns and attempts stale mutation.
8. BCP rejects stale fencing token.
9. Both conversations converge on the same revision.
