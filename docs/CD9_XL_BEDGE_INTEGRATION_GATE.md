# CD9 XL × B-EDGE integration gate

Date: 2026-09-24
Branch: work/cd9/xl-edge-tdlib-20260924

## Decision

Reuse B-EDGE as the zero-dollar, low-power, persistent phone-side foundation for ChatGPT Delivery XL. Do not make the Windows PC a 24/7 prerequisite and do not introduce a permanent Termux daemon as a second competing PhoneNode.

## Verified base before any XL source mutation

- CURRENT Android release: `2.2.0-full-node-evergreen` / versionCode 220.
- Stable Drive CURRENT: `BCP_EDGE_CURRENT.apk`.
- Drive file size read back: 2,293,572 bytes.
- SHA-256 read back: `a95460edc340fdba6e045ef1ad3c8ddbc062c3a61f56fbb479360f2b00102e3a`.
- This matches `release/current.json` and `release/android.json`.
- Machine/emulator qualification and signing/readback already exist.
- `field_verified` is still false: the real old phone is the next gate.

## Why this is the next gate

B-EDGE already contains the primitives CD9 would otherwise have to reinvent:
- foreground `START_STICKY` Android service;
- BOOT_COMPLETED/package-replaced restoration;
- durable Room/store-and-forward state;
- bounded private content cache;
- TLS local API and authenticated Telegram-only relay;
- network/battery/resource policy for a dedicated phone;
- server-mode onboarding.

Adding a second permanent daemon before proving this base on-device would violate REUSE/ADAPT and A+B+C.

## Next human field action

Perform one in-place update on the old phone:
1. install CURRENT over the existing BCP Edge app;
2. do not uninstall and do not re-pair unless telemetry proves it necessary;
3. open BCP Edge;
4. grant notifications/nearby-device permissions if requested;
5. enable/reinforce dedicated 24/7 server mode and battery-unrestricted mode;
6. capture the screen showing version/server/autonomy status.

No Telegram API_ID/API_HASH, VPS, paid service, PC installation, or giant network transfer is requested before this gate.

## After the gate

Candidate next lane:
- native Telegram large-file transport on B-EDGE;
- TDLib is the current RESEARCH/ADAPT candidate because Telegram officially supports Android/Java, asynchronous local storage and local-file sending;
- preserve one-heavy-transfer-at-a-time, bounded RAM and app-private temporary storage;
- receive large Telegram files to phone storage and feed the existing authenticated CD9 XL bridge in bounded chunks;
- qualify progressive live gates: 150 MB, 200 MB, 500 MB, 1 GB, then the practical maximum;
- treat the Local Bot API 2000 MB value only as an official architectural upper reference until the B-EDGE path is field-proven.

## Cost and quota rules

- zero USD is P0;
- use existing public BCP CI sparingly and consolidate source changes before triggering Android qualification;
- Vercel and Apps Script remain control/orchestration planes, not bulk-byte pipes;
- Drive remains durable evidence/storage;
- the PC is an optional heavy worker, never the sole persistent communications node.
