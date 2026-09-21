# R76 — A+B+C research and architecture evidence

## Internal authority
- BCP V0.7 AX15GO SEALED preconception.
- BCP_API_Personnelle_Dossier_Complet_2026-09-18.pdf.
- APIAX07_HANDOFF.md.
- Current cumulative CANONICAL_PRODUCT_REQUIREMENTS.md and field evidence through R76.

## External engineering basis
- Android Wi-Fi Direct service discovery can advertise/discover services and communicate directly even without a shared local network/hotspot. Android 13+ uses NEARBY_WIFI_DEVICES runtime permission.
- Android app-specific persistent storage is appropriate for private app data; free space must be queried and use must be bounded.
- Android 15 adds BOOT_COMPLETED restrictions for several foreground-service types, so boot restoration remains API-level qualified and tested.
- DevicePolicyManager lock-task allowlisting is available to device owners / qualified managed-device roles, making an optional dedicated-appliance mode feasible.
- SQLite synchronous=FULL in WAL mode provides stronger durability semantics for critical state than NORMAL; critical vs rebuildable data must be explicit and abrupt-power-loss tested.
- Transactional-outbox + idempotent-consumer semantics remain the correct provider-delivery model because retries can duplicate sends.

## R76 consequence
The phone is the low-power continuity appliance, the PC is a capability node, and cloud is thin rendezvous/coordination. Communication, memory, queueing and recovery must continue meaningfully when the PC is absent.

## Source pointers
- https://developer.android.com/develop/connectivity/wifi/nsd-wifi-direct
- https://developer.android.com/develop/connectivity/wifi/wifi-direct
- https://developer.android.com/training/data-storage/app-specific
- https://developer.android.com/about/versions/15/behavior-changes-15
- https://developer.android.com/reference/android/app/admin/DevicePolicyManager
- https://sqlite.org/pragma.html
- AWS Prescriptive Guidance — Transactional Outbox Pattern
