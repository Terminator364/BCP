# BCP R67 — Dedicated Android Phone as Primary Edge Server

Status: candidate implementation + field-gated transport expansion.

## Architectural correction

The dedicated old Android phone is no longer treated as a secondary UI or a narrow Telegram relay. It is a first-class BCP node with a different job from the Windows PC.

**Phone:** continuity, local API, durable queue, cache, store-and-forward, low-data egress gateway, local sentinel, network adaptation.

**PC:** Windows-only operations, PowerShell, heavy/burst compute, desktop integration and actions that actually require Windows.

This deliberately removes the assumption that the PC must be the communication centre.

## Concrete R67 implementation

The existing B-EDGE foreground relay on TCP 8876 now also exposes a bounded authenticated local API:

- `GET /health` — minimal unauthenticated discovery/liveness;
- `GET /v1/edge/status` — authenticated role/mode/queue/connectivity state;
- `GET /v1/edge/capabilities` — authenticated transport/hardware capability snapshot;
- `GET /v1/edge/jobs?project_id=...` — durable queued jobs;
- `POST /v1/edge/jobs` — enqueue an Edge/PC-bound job with durable Room state;
- `POST /v1/edge/reconcile` — request bounded WorkManager reconciliation;
- `GET /v1/edge/sentinel` — PC-availability continuity state.

The same foreground service retains the strict allowlisted HTTPS CONNECT relay to `api.telegram.org:443`. It is not a general-purpose Internet proxy.

The service returns `START_STICKY`, is restarted after normal boot/package replacement where Android permits it, and WorkManager remains the durable fallback.

## Why this saves mobile data

The target topology is not “put the PC on the phone hotspot and let Windows consume Internet freely”.

The preferred low-data topology becomes:

`PC --local path--> old phone BCP server --allowlisted tiny uplink--> Internet control surfaces`

The PC can therefore remain without general Internet access while still reaching BCP control traffic through the phone. This is especially valuable when the old phone gets an uplink from another hotspot/Wi-Fi and the PC uses a separate local transport to the old phone.

## Transport ladder

1. Private LAN / shared hotspot — implemented baseline.
2. USB/ADB port-forward — test target for a wired control path even without common LAN.
3. Wi-Fi Direct — high-value next transport because Android can maintain a P2P link while retaining another uplink on supported hardware/platform combinations.
4. Bluetooth/BLE — emergency low-bandwidth heartbeat/command lane, not bulk transport.
5. OEM USB tether/accessory paths — optional capability-gated path.

R67 CI uses an Android emulator plus real `adb forward` to prove that a PC-side process can reach the phone server through a USB-style local port-forward without relying on the emulator LAN address.

## Android dedicated-device mode

Root is not the baseline requirement.

For a phone permanently dedicated to BCP, an optional **Device Owner / DPC** mode is architecturally valid and can provide stronger kiosk/policy/background guarantees. Android's official dedicated-device model treats Device Owner as full device management, but provisioning can require an unprovisioned/factory-reset device. Therefore this remains an explicit later gate, not a silent migration.

## Research basis used in R67

Official Android documentation confirms:
- WorkManager is the recommended persistent work primitive and survives restarts/reboots;
- `remoteMessaging` foreground service is specifically intended for cross-device message continuity and local message relay;
- Wi-Fi Direct provides direct peer connectivity without an access point and can coexist with another uplink in the Android API model;
- Companion Device APIs can support persistent presence for Bluetooth/BLE companion scenarios;
- USB host/accessory modes and ADB/network debugging provide wired connectivity options;
- Device Owner is the official strong-control model for fully dedicated Android devices.

Field behavior still depends on the actual old phone/OEM, so transport promotion remains evidence-gated.

## Next implementation gates

- Android emulator: APK install -> foreground node -> ADB/USB-forward -> `/health` PASS -> unauthorized protected endpoint returns 401 -> UI smoke/cold relaunch.
- Windows: register `PHONE_PRIMARY_EDGE_SERVER`, mirror capabilities and connectivity, probe the authenticated local status endpoint, expose node reachability in BCP runtime telemetry.
- Real phone: capability readback for Wi-Fi Direct/BLE/USB/device-owner state before enabling each transport.
- No repeated manual user experiment before the representative automated path passes.
