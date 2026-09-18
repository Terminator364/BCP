# BCP — Blessing Control Plane — POC V0.1

First runtime/field harness derived from the sealed BCP V0.7 preconception.

## Goal

Prove the first continuity primitive end-to-end:

1. run a lightweight PC node;
2. install the B-Edge APK on the old Android phone;
3. commit a project checkpoint over the trusted LAN;
4. interrupt/restart;
5. recover the same committed revision and next action without replay.

## Components

- `pc-node/` — Python 3.10+ standard-library server, SQLite/WAL.
- `android-b-edge/` — Android Java app, package `com.blessing.bcpedge`.
- `.github/workflows/android-build.yml` — public CI build + SHA-256.
- `project_state.json` — explicit recovery pointer.

## PC quick start

```bat
cd pc-node
py -3 bcp_server.py --bind 0.0.0.0 --port 8765
```

The first start creates `pc-node/state/bcp_token.txt` and prints the bearer token once.

Health:
```
http://127.0.0.1:8765/health
```

For the old phone use the PC LAN IPv4 address, e.g. `http://192.168.1.25:8765`.

Do not expose this POC port directly to the public Internet.

## Runtime truth

A checkpoint is COMMITTED only when the event and project HEAD are persisted in the same SQLite transaction and a revision + event hash are returned.

Status: `POC_IMPLEMENTED / LOCAL_TESTABLE / ANDROID_CI_PREPARED / FIELD_UNVERIFIED`
