# B-EDGE Full Phone Server Node & Adaptive Transport — R65

Status: IMPLEMENTATION CANDIDATE / FIELD UNVERIFIED
Revision: 2026-09-21-R65

## Decision

The dedicated old Android phone is not a passive client and not merely a Telegram tunnel. It is a first-class BCP Edge server node.

The PC remains the heavy Windows worker. B-EDGE owns lightweight durable continuity work that benefits from a low-power always-available Android node.

## R65 node responsibilities

B-EDGE owns:
- a private-LAN authenticated local API on TCP/8877;
- the existing narrow Telegram TLS CONNECT relay on TCP/8876;
- Room/SQLite project state, memory, queue, dependencies and receipts;
- idempotent store-and-forward communication jobs;
- local network/uplink state;
- PC reachability sentinel and recovery intent;
- local Telegram outbound capability after explicit on-device secret provisioning;
- boot/package-replacement recovery through the same foreground node service;
- WorkManager reconciliation and bounded retry;
- compact phone-side telemetry and a lightweight human cockpit.

The phone does **not** assume a SIM. An uplink can be home Wi-Fi, another phone hotspot, or another validated network. When no Internet uplink exists, remote delivery is impossible and must remain a truthful durable `NETWORK_WAIT`, while the local server/queue remains available.

## Adaptive route order

For compact control-plane traffic:

1. PC <-> B-EDGE authenticated LAN API where both devices share a LAN/hotspot.
2. Direct PC Telegram HTTPS when healthy.
3. PC -> B-EDGE HTTPS CONNECT tunnel when the PC Telegram egress fails but the phone uplink works.
4. PC -> B-EDGE durable local queue for compact Telegram text when direct+tunnel delivery fail.
5. B-EDGE later drains the queue when its own validated uplink is available and its local Telegram credential is configured.
6. Nexus/cloud remains an optional remote witness/ingress route, never the only continuity authority.

Bulk APK/ZIP/build traffic is explicitly excluded from the phone communication relay unless a later qualified policy opts in. Metered paths default to control-plane-only.

## Security boundary

- BCP paired bearer authenticates local PC<->phone API calls.
- Local node endpoints accept only private/link-local/loopback clients.
- Job kind, body size, priority, idempotency key and concurrency are bounded.
- The Telegram bot secret is **not** auto-copied across cleartext LAN.
- Optional phone-side Telegram outbound is provisioned explicitly on the phone and encrypted with Android Keystore AES-GCM.
- The existing HTTPS CONNECT relay never sees the Telegram token or plaintext Telegram TLS traffic.
- Canonical state is still fenced; B-EDGE does not silently seize Git/main authority.

## Lifecycle

R65 uses a visible foreground service because Android explicitly classifies remote messaging and connected-device interactions as foreground-service use cases. The service hosts both the relay and local node API. WorkManager remains the durable reconciliation safety net.

The node must recover after device boot or package replacement, subject to real-device Android/OEM background policy. A CI/emulator PASS does not replace a real boot/battery-optimization field test.

## Additional transports — researched, not falsely promoted

### Wi-Fi Direct / P2P
Android Wi-Fi Direct can discover/connect nearby peers without an access point or Internet and then use ordinary sockets. It is the preferred next transport candidate when both devices are physically near but no shared LAN/hotspot is available. It requires the Android nearby-Wi-Fi permission model and real-device testing.

### Local-only hotspot
Android LocalOnlyHotspot creates a local network without Internet. It is a useful fallback candidate when a shared router is unavailable. R65 does not yet promote it to CURRENT because reconnection credentials, Windows joining behavior and OEM reliability need field validation.

### Bluetooth / BLE
Bluetooth is appropriate as a low-bandwidth bootstrap/control fallback, not for bulk sync. A later transport adapter can carry discovery, small commands, wake/recovery hints and possibly local endpoint negotiation.

### USB
USB is a useful recovery/bootstrap path when radio networking is unavailable. It remains a future explicit transport adapter rather than a hidden dependency.

## Dedicated-device mode

Android's fully managed/device-owner APIs can give much deeper control on a truly dedicated phone, but normal provisioning commonly requires a managed-device enrollment flow and may require a factory reset/unprovisioned state. R65 does not force that disruptive transition.

A later **DEDICATED_DEVICE_OWNER** phase may be offered only after:
- current phone data is backed up or confirmed disposable;
- user explicitly accepts the provisioning/reset implications;
- the DPC path is simulated and rollback/recovery is documented.

Until then, R65 gets substantial value from normal app privileges, foreground service, WorkManager, Room and explicit nearby/network permissions.

## UI direction

The phone surface is a node cockpit, not a developer console. Primary view should answer:
- Is the node alive?
- Is the PC reachable?
- What network/uplink exists?
- Can Telegram leave now?
- How many durable messages/jobs are waiting?
- What is the current mode?
- Is user action actually required?

Technical IDs/hashes belong behind progressive disclosure.

## Acceptance gates

R65 is not FIELD_VERIFIED until:
- Android unit/build/lint PASS;
- emulator install/launch/UI/relaunch PASS;
- boot receiver/service declaration is validated;
- private-LAN node API authentication/negative controls PASS;
- duplicate enqueue proves one durable effect;
- no-Internet enqueue survives and later drains without duplication;
- PC direct -> relay -> store-forward route simulation PASS;
- real old-phone reboot recovery PASS;
- real LAN/hotspot switch recovery PASS;
- metered data behavior is measured;
- Telegram phone-side outbound is explicitly provisioned and proves send/readback if that lane is enabled;
- no user is required as a routine telemetry or message shuttle.

## Design references

Primary authority is Android's current platform documentation:
- Foreground service types: https://developer.android.com/develop/background-work/services/fgs/service-types
- Wi-Fi Direct: https://developer.android.com/develop/connectivity/wifi/wifi-direct
- Wi-Fi Direct service discovery: https://developer.android.com/develop/connectivity/wifi/nsd-wifi-direct
- Nearby Wi-Fi permissions: https://developer.android.com/develop/connectivity/wifi/wifi-permissions
- Local-only hotspot: https://developer.android.com/develop/connectivity/wifi/localonlyhotspot
- Companion device pairing: https://developer.android.com/develop/connectivity/bluetooth/companion-device-pairing
- Dedicated devices: https://developer.android.com/work/dpc/dedicated-devices/

Practical video/tutorial review is used only for UX/workflow intuition; platform/security claims are grounded in official Android contracts.


## R66 — Phone-primary control plane

R66 moves the design farther than "phone as relay". The dedicated Android device now owns a useful control-plane subset even while Windows is unavailable:

- authenticated local project registry/context/memory/jobs API;
- durable idempotent resume-intent intake;
- phone-owned PC reachability sentinel;
- phone-owned Telegram outbound liveness and recovery notices;
- local durable queue drain independent of the Windows Telegram worker;
- foreground service + boot/package-replacement restart;
- low-data network-state adaptation without assuming a SIM.

### Inbound Telegram ownership boundary

The same Telegram bot token MUST NOT be long-polled concurrently by both PC and phone. R66 therefore keeps inbound `getUpdates` ownership on the existing fenced worker and gives the phone independent outbound/liveness ownership. A later PHONE_PRIMARY inbound mode must introduce a durable poller lease with a single active owner and explicit failover/readback.

### Storage utilization direction

The phone's app-private storage is a continuity asset, not spare capacity. The R66/R67 direction is:
- Room/SQLite project memory, jobs, receipts and checkpoints now;
- bounded content-addressed recovery cache next;
- signed/hash-pinned BCP artifacts/manifests may be retained once per hash and served locally to avoid repeated downloads;
- metered uplinks never prefetch bulk content by default;
- cache eviction is based on free-space floor, age and canonical pin status.

### Network transport research applied

Official Android platform contracts support the following qualified direction:
- Wi-Fi Direct service discovery for direct sockets without a router;
- Wi-Fi Aware where hardware supports it, for direct peer discovery/data paths;
- LocalOnlyHotspot for routerless local communication without Internet;
- CompanionDeviceManager for one-time nearby-device association and background/FGS-related companion privileges;
- foreground `connectedDevice` / `remoteMessaging` service types for the active node duties;
- Device Owner / fully-managed mode as an optional deeper-control phase only after explicit provisioning-impact approval.

Practical old-phone server demonstrations also confirm the general viability of using Android as an always-on lightweight home/edge server, but BCP platform/security decisions remain grounded in Android's official APIs rather than tutorial-specific shortcuts such as arbitrary public tunnels.
