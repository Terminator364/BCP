# BCP Capability Factory & Self-Update — R2
Date: 2026-10-05
Status: PRECONCEPTION

## Capability Factory pipeline

1. GAP_DETECTED
2. DEFINE_CONTRACT
3. REUSE_SEARCH
4. SOURCE_TRUST_CHECK
5. LICENSE_POLICY_CHECK
6. BUILD_ADAPTER
7. STATIC_VALIDATE
8. SANDBOX_TEST
9. RESOURCE_TEST
10. ROLLBACK_TEST
11. SECURITY_TEST
12. CANARY
13. REGISTER
14. EXECUTE_ORIGINAL_INTENT
15. LEARN_RECIPE
16. PROMOTE_OR_QUARANTINE

Each stage emits a receipt.

## Sandboxing strategy

Prefer the lightest adequate isolation:
- no-effect static validation;
- temporary project worktree;
- restricted temp directory;
- normal-user process;
- Windows sandbox/restricted process APIs for untrusted/headless generated helpers where practical;
- Job Object process tree containment;
- network denied by default unless capability declares it;
- privileged effects only through typed broker.

A generated adapter cannot directly inherit permanent admin authority.

## Capability trust classes

T0 BUILTIN
- shipped with BCP; exact-qualified.

T1 VERIFIED_LOCAL
- generated/reused adapter; tested and field-proven on this machine.

T2 VERIFIED_REMOTE
- trusted external/provider adapter with provenance/readback.

T3 CANDIDATE
- canary/test only.

T4 QUARANTINED
- failed or untrusted.

Only T0-T2 may serve unattended normal missions.

## Update rings

DEVELOPMENT -> QUALIFIED -> CANARY -> CURRENT -> LKG -> RETIRED.

The user runs CURRENT.
CANARY may receive bounded real tests.
LKG is rollback target.

## Auto-update policy

Automatically:
- discover;
- download/stage;
- hash/signature/provenance verify;
- static/self-test;
- schedule safe activation;
- canary;
- health readback;
- promote or rollback;
- report exceptional failure.

Never automatically:
- trust a new signing root without policy;
- cross a major destructive migration without compatible rollback/migration proof;
- downgrade below anti-rollback floor;
- activate under unsafe resource pressure merely because update exists.

## Supply-chain evidence

Every executable/update artifact should record:
- source repository/revision;
- builder identity/class;
- build recipe;
- relevant dependencies;
- artifact SHA-256;
- tests/gates;
- signer/verification method;
- promotion timestamp;
- rollback predecessor.

This is a BCP-level lightweight provenance envelope inspired by SLSA/in-toto.
