# CD9 + B-EDGE opportunistic edge architecture

Status: R90 candidate, zero-dollar, phone/PC non-authoritative.

## Invariant

ChatGPT Delivery must remain correct when the old phone, PC, Wi-Fi or power is unavailable. Google Drive/cloud state remains the durable authority. B-EDGE is an opportunistic accelerator/cache/relay and store-and-forward node.

## Why this shape

The old Android phone is more available than the PC but is still a weak, failure-prone device on a slow/intermittent network. Therefore CD9 never waits indefinitely for it and never requires it to reconstruct canonical state.

## Candidate behavior

- exposes authenticated `GET /v1/node/cd9/status`;
- reports network, battery, private cache headroom and store-and-forward readiness;
- target logical object is 2,000,000,000 bytes, while ChatGPT-side physical segments stay at 500,000,000 bytes;
- does **not** claim that the current B-EDGE process is a Telegram Local Bot API server;
- keeps the existing strict HTTPS CONNECT relay as a small-file/fallback transport aid;
- Drive remains canonical for complete large objects;
- bulk mobile-data use stays disabled by default.

## Update policy

The R90 candidate adds a tiny background metadata probe:
- public signed release metadata only;
- successful probe interval: 6 hours;
- failed probe retry: 30 minutes;
- no APK background download;
- one Android notification per newer version;
- existing UpdateManager still verifies package, SHA-256 and Evergreen signing identity before Android presents its unavoidable install confirmation.

This reduces routine manual checking without pretending a normal third-party APK can silently self-install.

## Human gate

Only after exact-head Android build/lint/unit/task-simulation gates, pinned signing, Drive CURRENT readback and rollback proof may the user receive one in-place update request. No succession of micro-installs.
