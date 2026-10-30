# BCP Universal Remote — G4.1 Individual Device Identity / checkpoint 2026-10-30

## Universal recovery code
`BCP|UNIVERSAL|SYNC|MASTER`

Resolver: `universal-remote/BCP_UNIVERSAL_SYNC_MASTER.json` on branch
`feat/universal-remote-transport-20261030` of `Terminator364/BCP`.
Verify branch HEAD, Windows live service, Android signed stable manifest,
then continue from the last confirmed gate. This code is NOT a credential.

## Canonical requirement
Full authorized Windows control through an individual phone and later ChatGPT:
files of arbitrary aggregate size, Windows shell, persistent jobs, process,
desktop and software management. Network priority LAN > Tailscale > USB >
Bluetooth. No forced mobile tether or forbidden cellular update. Keep
Windows ACL/UAC, owner local consent, authentication, audit, reversibility.
Never reintroduce experimental 30-minute/20-operation/single-folder limits
as core architecture. No restart of G0/G1/G2.

## Confirmed baseline before G4.1
- MBMPC online via Desktop Commander; G2 TLS/HMAC active; owner-general
  inventory was deployed with 16/16 production negative/security controls.
- Real Samsung reported Android versionCode 17, release v1.3.0, on mobile
  data; signed stable channel preserved.
- Existing G4 owner-general route correctly rejects unapproved requests.
- A prior local Windows test-file approval was actually performed; this is
  NOT equivalent to granting a durable owner profile.
- Initial local file engine 23/23 checks, local task queue 14/14 metadata
  checks; neither was exposed to remote owner controls.
- G3, G5 and full G6 are unfinished.

## Source work in this tranche
- `universal-remote/windows/g4_device_identity.py`:
  per-device 256-bit random secrets (provided by phone), unique 128-bit ID,
  pending enrollment capped and expiring, one local six-digit verification,
  no authority before local confirmation, per-device HMAC with
  timestamp/nonce/body digest, SQLite replay protection, device revocation.
  The shared legacy G2 HMAC key is transport authentication ONLY.
- `universal-remote/tests/g4_device_identity_test.py`:
  29 isolation/negative/adversarial assertions PASS in a real Windows
  temporary directory on MBMPC (no personal files touched).
- Dedicated clean Windows CI `bcp-g4-device-identity.yml`:
  after fixing an overly eager rate-limit assertion and a SQLite connection
  leak, run `41124418894` SUCCESS.
- `universal-remote/windows/g4_owner_gateway.py`: fail-closed legacy
  owner route; new function for owner enrollment of a separately registered
  device; owner inventory accepts the verified device identity argument.
- `universal-remote/windows/g2_tls_bridge.py`: source-only pending
  enrollment route; owner inventory now requires the signed individual
  device headers in addition to G2 transport authentication.
- `universal-remote/windows/g4_owner_center.py`: updated Windows-local
  UI for per-device pending enrollment, code entry, owner consent and
  independent revocation. No auto-approval on launch.
- `SecureDeviceIdentity.java`: separate Android Keystore AES/GCM-sealed
  identity and generated 256-bit device secret; `G2TransportClient.java`
  can submit the individual HMAC headers.
- Android CI runs `41124621360` and `41124649348` succeeded for the
  new library/client source.

## Important NOT DONE (never infer from a successful compile)
1. The Android MainActivity UI for requesting and showing the code, then
   reading owner-general inventory, is not yet integrated. Thus no true
   Samsung G4.1 enrollment has happened.
2. The new G4.1 source is NOT deployed to the active Windows G2 service;
   do not restart or replace it before complete staging and rollback proof.
3. The phone has NOT received an APK update past signed v1.3.0. No
   individual owner device has been enrolled; no owner profile activated.
4. The owner-core CI suite was queued/running after migration of legacy
   unit tests at checkpoint time. Reconfirm latest completion. An older run
   failed due an indentation error in a migrated test, corrected in
   commit `44b4790630f90d21b3d341dde571f22ceefd8790`.
5. No generic file write, shell, desktop GUI, service or install command
   exposed to Android; no BCP-native ChatGPT connector.
6. Existing unrelated GitHub Windows bootstrap workflow reports 0-job
   failures; do not present it as a passed workflow.

## Immediate next ordered work
1. Confirm clean Windows owner-core CI and Android build; fix regressions.
2. Finish Android UI with per-device code display (without leaking secret),
   signed inventory request and Wi-Fi-first/Tailscale fallback.
3. Test G4.1 staging against a synthetic individual device and explicit
   local approval simulated ONLY in isolated tests; no synthetic grants
   on production.
4. Deploy backend with backup, timeout/rollback and G2 16/16 health gate;
   confirm all owner actions still fail without real enrollment.
5. Publish one signed stable Android upgrade using existing signing
   identity only after CI + smoke and keep old stable for rollback.
6. **Human gate:** user opens BCP on Samsung, initiates individual identity,
   then enters its six-digit code and approves once in the BCP Windows
   owner window. The assistant cannot silently supply that consent.
7. Validate a genuine Samsung signed owner inventory, then connect
   complete file transactions and durable job execution, moving through
   G4 and G5 with audited end-to-end evidence.

## Continuity invariant
Machine-readable master registry is canonical; maintain a verified-live
checkpoint and an in-development checkpoint separately. Never confuse
successful CI, compiled source, published APK, installed APK, trusted
device or end-to-end ChatGPT execution.
