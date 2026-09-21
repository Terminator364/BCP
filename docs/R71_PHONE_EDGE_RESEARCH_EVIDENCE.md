# R71 — Dedicated Android Edge/API node research evidence

Status: engineering evidence for the B-EDGE full-node line  
Date: 2026-09-21

This note records the external Android architecture evidence used by R70/R71. It does not replace field tests on the dedicated phone.

## Offline-first local authority

Android's official offline-first guidance says a repository that uses network resources should have a local data source, and upper layers should read from that local source. It also describes persistent queues and WorkManager as appropriate tools for draining queued reads/writes when connectivity returns.

Source:
https://developer.android.com/topic/architecture/data-layer/offline-first

BCP implication:
- Room/WAL remains the durable phone-side source for queue, memory, receipts and local operating state.
- Network/PC reconciliation updates local state; UI must not depend on a live PC response to remain useful.
- WorkManager is the bounded reconciliation mechanism, not the sole runtime server.

## Wi-Fi Direct service discovery

Android documents Wi-Fi Direct DNS-SD as a way to advertise and discover services between nearby devices even when no local network or hotspot is available.

Sources:
https://developer.android.com/develop/connectivity/wifi/nsd-wifi-direct
https://developer.android.com/develop/connectivity/wifi/wifi-direct

BCP implication:
- LAN NSD remains preferred on a shared Wi-Fi/hotspot.
- Wi-Fi Direct DNS-SD is a real local fallback when supported/authorized.
- The implementation must request the appropriate Wi-Fi/nearby/location permissions for the Android version instead of silently assuming them.

## Foreground connected-device / remote-messaging service

Android requires foreground-service types on modern target SDKs. The connectedDevice type is explicitly intended for interactions with external devices over Bluetooth, USB or network connections and has permission/runtime prerequisites.

Sources:
https://developer.android.com/develop/background-work/services/fgs/service-types
https://developer.android.com/about/versions/14/behavior-changes-14
https://developer.android.com/develop/background-work/services/fgs/troubleshooting

BCP implication:
- the persistent phone node keeps a user-visible foreground notification;
- `connectedDevice|remoteMessaging` is retained only while it matches actual work;
- runtime permission state is surfaced in the server dashboard before starting capability-dependent paths;
- permission failure must degrade capability, not crash the whole node.

## Wi-Fi Aware as optional hardware-dependent fallback

Android Wi-Fi Aware can publish/discover nearby services without another connectivity type, but it consumes resources and must be closed when not needed.

Source:
https://developer.android.com/develop/connectivity/wifi/wifi-aware

BCP implication:
- Wi-Fi Aware is an optional later transport for devices that support it, not a mandatory dependency.
- It must be power-gated and capability-detected.

## Dedicated-device / Device Owner mode

Android's device-management APIs provide dedicated-device/device-owner management, but this is a materially more invasive provisioning mode than normal runtime permissions.

Source:
https://developer.android.com/work/device-admin

BCP implication:
- normal B-EDGE full-node must work without Device Owner;
- an optional **Advanced Dedicated Mode** can be evaluated separately for this user-owned dedicated phone if its provisioning cost is justified;
- no destructive/factory-reset provisioning is introduced as a hidden requirement.

## R71 architectural conclusion

The dedicated phone is not a UI accessory. It is the persistent low-power node:
- local API server;
- Room/WAL durable state and queue;
- local context builder;
- bounded private cache;
- foreground service with boot/package-replacement restore;
- LAN NSD + capability-gated Wi-Fi Direct/BLE;
- Telegram CONNECT relay with end-to-end Telegram TLS;
- store-and-forward when no uplink exists;
- PC treated as Windows/heavy-compute executor rather than communications singleton.

Field promotion still requires exact-head emulator/CI qualification plus a single coherent in-place phone installation, not repeated micro-beta installs.
