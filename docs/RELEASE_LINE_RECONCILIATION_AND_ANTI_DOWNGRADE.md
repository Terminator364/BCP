# BCP release-line reconciliation and anti-downgrade gate

Status: REQUIRED before the next B-EDGE publication or automatic-update promotion.

## Why this gate exists

Two valid development lines currently coexist and must not be conflated:

- The current `main` product line exposes the qualified automatic-update contract for BCP 0.5.0 / B-EDGE 1.1.0.
- A preserved integration line contains BCP 0.6.0 / B-EDGE 2.0.0-rc1. PR #13 was merged into `work/integration/bcp06-edge2rc1-20260919`, not into `main`.

Google Drive already contains a private stable-signed `BCP_EDGE_CURRENT.apk` paired with `BCP_EDGE_CURRENT.json` declaring B-EDGE 2.0.0-rc1 (versionCode 200), source commit `8b3896a71b5b04e714de05b41c6c7bd24d574ba6`, SHA-256 `c1640260cbaafdd92bb69c98f6780b5b03d26ad4bf1553bce393dbaf33c8c389`, and the pinned Evergreen certificate fingerprint.

Therefore, publishing or replacing Drive CURRENT with any lower B-EDGE version is forbidden unless an explicit rollback is authorized and recorded.

## Private signing fact

A private Evergreen signing authority exists in the private Drive signing area and matches the public pinned certificate fingerprint.

Rules:

- Never commit private signing material, password, keystore bytes, or base64 to public GitHub.
- Public state may record only package identity, certificate fingerprint, artifact hash, version, CI evidence, and non-secret publication metadata.
- Never rotate the signing authority casually because Android update continuity depends on the signing identity.

## Required promotion sequence

1. Read current `main` and the preserved 0.6/2.0 integration line.
2. Compare and reconcile the candidate line against everything merged into `main` afterward.
3. Re-run exact-head CI for Windows, Android, coordinated compatibility, Telegram observability, release-contract validation, and any affected Nexus tests.
4. Verify the private signed APK readback: versionCode/versionName, package id, SHA-256, pinned signer fingerprint, v2/v3 signature verification.
5. Verify BCP server compatibility and field acceptance on the real PC/B-EDGE pair.
6. Only then promote the reconciled release metadata and automatic-update manifest.
7. After promotion, replace Drive CURRENT only with a versionCode >= the currently published versionCode, except for an explicit audited rollback.

## Anti-downgrade invariant

Normal update publication MUST satisfy:

`candidate.versionCode >= current_drive.versionCode`

If the candidate is lower, stop with `RELEASE_LINE_RECONCILIATION_REQUIRED`; do not overwrite Drive CURRENT.

## User-experience requirement

The user is not the release transport. Once the reconciled line is promoted, B-EDGE should obtain qualified updates over home Wi-Fi through the existing authenticated BCP update path, with only the Android OS confirmation that cannot legitimately be automated away.

This gate is about continuity and correctness; it is not a mechanism for bypassing platform or provider safeguards.
