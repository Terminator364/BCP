# API / BCP — User Friction Charter

Status: CANONICAL PRODUCT REQUIREMENT
Date adopted: 2026-09-19

## Why this product exists

API/BCP is being built in part because long ChatGPT technical sessions are not a reliable sole place to hold project execution state.

Observed friction to design out:
- ChatGPT turns can be interrupted by additional-verification holds;
- those holds can add substantial wall-clock delay even when the visible thinking time is shorter;
- a user may stop an interrupted turn and need to continue elsewhere;
- long tool-heavy turns can lose momentum or require repeated recovery;
- screenshots/manual copy-paste make the user act as the telemetry bus;
- repeating full project recovery wastes time and can duplicate work;
- a conversation must never be the only copy of the project's execution state.

## Product promise

The system must make conversation interruption nonterminal.

A healthy API/BCP deployment should ensure:
1. the project state survives the conversation;
2. already-dispatched device/build jobs may continue independently;
3. a second conversation can safely resume from the durable checkpoint;
4. only one writer may mutate canonical external state at a time;
5. resumption does not replay committed work;
6. the user does not have to reconstruct state manually;
7. platform checks are respected, not bypassed;
8. legitimate technical scope is stored durably so it need not be re-explained every turn.

## What Blessing does not want

The product must actively reduce:
- waiting without knowing whether a real job is still progressing;
- repeated continue / recover / resend screenshot loops;
- repeated IP/token/project copy-paste;
- repeated installer/reinstall cycles;
- duplicate builds or duplicate mutations after recovery;
- losing 5–30+ minutes of wall-clock time because one ChatGPT turn is paused;
- having to lower the ambition of legitimate personal software projects just to keep continuity.

## UX rule

The normal recovery experience should be:

`interruption -> durable checkpoint already exists -> standby conversation reads it -> lease acquired -> next uncommitted atomic action -> receipt -> continue`

not:

`interruption -> user explains everything again -> broad rescan -> repeated commands -> screenshots -> uncertain state`.

## Acceptance criteria

This charter is satisfied only when a field test demonstrates:
- an ACTIVE conversation is interrupted mid-project;
- canonical state remains intact;
- a STANDBY conversation recovers the exact next action;
- no committed operation is duplicated;
- single-writer protection prevents concurrent mutation;
- the user provides no screenshot or manual state reconstruction;
- a later return of the original conversation reconciles instead of replaying stale work.


## Universal-context UX requirement

The normal fresh-conversation experience should become:

`BCPGO -> tiny bootstrap manifest -> GLOBAL_CORE -> PROJECT_CORE -> TASK_DELTA -> useful answer/action`

not:

`new chat -> user re-explains preferences -> re-explains project architecture -> screenshots -> broad recovery scan`.

A later turn should normally receive `UNCHANGED` or a bounded `DELTA`, not the entire memory corpus again.

The user may keep many projects, but the assistant should see only the global core plus the active project's scoped context and task-relevant cross-project knowledge.

The universal code is a trigger only; authorization comes from the connected BCP/Drive/app path.
