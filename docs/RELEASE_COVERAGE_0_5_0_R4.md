# BCP 0.5.0 + B-EDGE 1.1.0 — R4 Coordinated Qualification

Canonical requirements: 2026-09-19-R4

This validation branch is rebased on the latest synchronized PC + Android implementation.

## Promotion matrix

| Capability | State before field promotion |
|---|---|
| PC 0.5.0 durable memory/context/jobs | IMPLEMENTED + SELFTEST_REQUIRED |
| B-EDGE Room/SQLite transactional fabric | IMPLEMENTED + CI_BUILD_REQUIRED |
| B-EDGE WorkManager reconciliation | IMPLEMENTED + CI_BUILD_REQUIRED |
| Multi-project registry/routing | IMPLEMENTED + CI_BUILD_REQUIRED |
| Durable job queue + backpressure | IMPLEMENTED + UNIT/CI_REQUIRED |
| Job dependency relation | IMPLEMENTED + CI_REQUIRED |
| Receipt/idempotency persistence | IMPLEMENTED + CI_REQUIRED |
| Context Pack offline cache | IMPLEMENTED + CI_REQUIRED |
| EDGE_ONLY / PC_AVAILABLE / PC_MEMORY_PRESSURE | IMPLEMENTED + UNIT/CI_REQUIRED |
| PC reboot / identity / checkpoint recovery | PRIOR FIELD EVIDENCE + 0.5 REGRESSION REQUIRED |
| Keystore credential protection | PRIOR IMPLEMENTED + REGRESSION REQUIRED |
| Update/rollback | IMPLEMENTED + CI REQUIRED |
| Exact PC↔Android version/hash contract | CI REQUIRED |
| V2 coordinator authority migration | DEFERRED UNTIL FENCING FIELD QUALIFIED |
| Authenticated encrypted LAN/TLS | NOT YET FINAL; POC LOCAL TRANSPORT REMAINS |
| NSD/mDNS primary discovery | NOT YET FINAL; bounded scan remains compatibility path |

## Non-negotiable field package gate

No synchronized user package may be promoted to Drive CURRENT until server tests, Android unit tests/lint/build, compatibility/hash checks, signing verification, and one batched real-device acceptance campaign pass.

The field campaign must cover install/update, pairing continuity, multi-project state, offline queue, queue replay, memory pressure, PC reboot, phone process recovery, telemetry, and exact version/hash readback.
