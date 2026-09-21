# R81 — B-EDGE full-node research evidence and implementation decisions

Status: RESEARCH-BACKED CANDIDATE · 2026-09-22

## Scope

This note extends **B** in the canonical **A+B+C** specification. It does not replace A (original product intent) or C (field feedback). It records current Android platform evidence used to decide which capabilities belong on the dedicated phone and which mechanisms are appropriate.

## 1. Offline-first: phone local state must be authoritative for phone-resident work

Android's official offline-first architecture guidance says a networked repository should have a local data source and that the local source should be the canonical source consumed by higher layers. It also identifies persistent queues and WorkManager as appropriate mechanisms for deferred synchronization and network recovery.

Source:
- https://developer.android.com/topic/architecture/data-layer/offline-first

BCP consequence:
- Room/SQLite WAL remains the phone's durable core;
- Chronicle, mission-step state, capability registry, queues and receipts must remain useful with the PC or Internet unavailable;
- WorkManager is recovery/deferred-sync infrastructure, not the sub-second control hot path.

## 2. Direct local discovery without home LAN is a real platform capability

Android's Wi-Fi Direct service-discovery documentation states that services can be discovered and advertised directly between nearby devices without an existing local network or hotspot.

Source:
- https://developer.android.com/develop/connectivity/wifi/nsd-wifi-direct

BCP consequence:
- NSD remains the ordinary same-LAN path;
- Wi-Fi Direct service discovery is a legitimate fallback when the house LAN/hotspot is unavailable;
- Android 13+ requires NEARBY_WIFI_DEVICES for the relevant Wi-Fi APIs;
- discovery and permission state belong in the phone capability registry instead of being architectural assumptions.

## 3. Long-running server work must respect Android foreground-service rules

Android documents that Android 12+ restricts foreground-service starts from the background, with defined exemptions including BOOT_COMPLETED / MY_PACKAGE_REPLACED, while Android 14+ enforces service-type prerequisites and permissions. The connectedDevice service type is appropriate for network/Bluetooth/USB interactions when its prerequisites are satisfied.

Sources:
- https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start
- https://developer.android.com/develop/background-work/services/fgs/service-types
- https://developer.android.com/develop/background-work/services/fgs/troubleshooting
- https://developer.android.com/about/versions/14/behavior-changes-14

BCP consequence:
- B-EDGE must request only the runtime permissions actually needed by enabled capabilities;
- foreground service startup must be tested on target API levels and after reboot/package replace;
- permission state is a capability/evidence input, not a one-time onboarding fiction;
- failures must degrade to durable queue/store-forward rather than silently killing the node.

## 4. Optional appliance tier is technically distinct from ordinary app permissions

Android Enterprise documents device-owner / fully managed device capabilities. Device-owner authority is materially different from ordinary application permissions and can support a stronger dedicated-appliance tier, but provisioning and policy control have explicit platform constraints.

Sources:
- https://developer.android.com/work/device-admin
- https://developer.android.com/reference/android/app/admin/DevicePolicyManager

BCP consequence:
- do **not** pretend ordinary runtime permissions equal device-owner authority;
- keep an optional, explicitly provisioned appliance tier in the roadmap for the phone that is genuinely dedicated to BCP;
- normal 2.2 must remain useful without device-owner mode;
- any future device-owner promotion needs a separate human-consent/provisioning gate and field proof.

## 5. R81 implementation response

R81 closes part of the A+B+C gap `SOURCE_CAPABILITY_ADAPTERS` by adding a phone-resident durable capability registry:

- Room `edge_capabilities` table (schema v5);
- deterministic per-project/provider/capability identities;
- availability states: AVAILABLE / DEGRADED / UNAVAILABLE / WAITING_AUTH / UNKNOWN;
- evidence classes: MACHINE_READBACK / LOCAL_PROBE / PROVIDER_ACK / USER_CONFIRMED / CONFIGURED / UNKNOWN;
- bounded TTL and stale-entry purge;
- metadata SHA-256 and Chronicle event only when material state/evidence changes;
- authenticated `GET/POST /v1/node/capability-registry`;
- built-in observations for local API, local executor, store-and-forward, PC worker, Telegram relay/network and resource governor;
- inclusion in local context packs and server-first UI.

This turns the phone from a passive list of hard-coded promises into a node that can answer: **what can I do now, through which source/provider, with what evidence, and for how long is that observation valid?**

## Non-claims

R81 does not claim:
- encrypted LAN transport is complete;
- Wi-Fi Direct has passed field pairing on the user's exact phone;
- device-owner provisioning is active;
- Telegram relay is field-proven;
- B-EDGE 2.2 is ready for user installation.

Those remain separate gates.
