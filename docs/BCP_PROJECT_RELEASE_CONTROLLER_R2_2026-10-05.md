# BCP Project Release Controller R2
Date: 2026-10-05
Status: PRECONCEPTION

## Goal

Make "update automatically" true across BCP-managed projects without equating automation with blindly installing latest bytes.

## Two update classes

### Infrastructure/package update
Examples:
- BCP core;
- Desktop Commander adapter/runtime;
- Node/Python/JDK/Gradle dependencies;
- Delivery/BuildHub components;
- optional inference runtime.

Uses qualified version channels and desired state.

### Product/source release
Examples:
- Med Rebuild;
- PhoneMouse;
- P2PCR95;
- TLIB;
- Excellentia.

Source change must travel through a release pipeline before device activation.

## Release pipeline

SOURCE_CHANGE
-> PLAN/DIFF CLASSIFY
-> BUILD
-> STATIC TEST
-> UNIT/INTEGRATION
-> RESOURCE PROFILE
-> ARTIFACT HASH
-> PROVENANCE
-> STAGE
-> CANARY
-> FIELD HEALTH
-> COMMIT CURRENT
or
-> ROLLBACK LKG.

## Automatic dependency maintenance

A project adapter may opt into:
- monitor approved dependency channels;
- create update candidate branch;
- build/test;
- classify breaking change risk;
- promote patch/minor versions automatically only within project policy;
- hold major/security-sensitive migrations for ChatGPT/human review when compatibility proof is insufficient.

No direct update on the live worktree.

## Desired-state examples

- MedRebuild.version = latest_qualified
- MedRebuild.launcher.health = PASS
- MedRebuild.updater.state = HEALTHY
- PhoneMouse.artifact = latest_signed_qualified
- BCP.server = release/current.json exact qualified hash
- Delivery.health = OK
- BuildHub.release = latest_qualified

The controller observes actual state and converges safely.

## Project worktree rule

Autonomous code mutation:
- dedicated work branch/worktree;
- never overwrite dirty user work;
- writer lease/fence;
- exact-head tests;
- serialized merge;
- post-merge readback;
- staged device promotion.

## Human interruption rule

No interruption for:
- patch generation;
- tests;
- candidate build;
- staging;
- rollback to LKG.

Interrupt only when:
- product semantics change materially and no existing roadmap/policy authorizes it;
- major irreversible data migration;
- provider/license/account decision;
- security-sensitive action requiring fresh approval.
