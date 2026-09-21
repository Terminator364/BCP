# BCP — Adaptive Communication Fabric R63

Status: IMPLEMENTATION CANDIDATE  
Date: 2026-09-21

## Goal

BCP must remain observable when home Wi-Fi, mobile data, ChatGPT, Telegram, Drive or a single device path is degraded. The user is never the transport bus.

## Adaptive topology

```
PC-WORKER --authenticated LAN/hotspot LAN--> B-EDGE old Android
     |                                      |
     | local durable outbox                 | selective tiny egress
     |                                      +--> Telegram (Wi-Fi when healthy)
     |                                      +--> Telegram (cellular only if available/allowed)
     |                                      +--> Nexus (Wi-Fi/cellular, compact only)
     +--> direct Telegram (opportunistic)
     +--> Nexus (qualified path)
```

B-EDGE cellular capability is **discovered, not assumed**. The old phone may operate on home Wi-Fi only, may be the hotspot owner, or may have validated cellular while the PC reaches it locally. The current daily phone remains a human client and is never required infrastructure.

## Why the old phone matters

The old phone is promoted from passive companion to a real edge relay/witness. PC control events are persisted first, transferred over local LAN without mobile-data cost, then relayed remotely by the cheapest healthy B-EDGE path. If all remote paths fail, events stay queued and later resume without duplicates.

For Android reliability, steady state prefers **phone-initiated pull/long-poll from the PC** plus the existing WorkManager reconciliation safety net. This avoids making correctness depend on an always-listening Android server that the OS can kill. A foreground remote-messaging service may later provide low-latency mission-active long-poll after dedicated field qualification.

## Route selection

1. Local LAN to B-EDGE.
2. B-EDGE Wi-Fi remote egress if validated.
3. B-EDGE cellular only for compact control traffic when available and policy permits.
4. Qualified Nexus path.
5. Direct PC Telegram only as opportunistic fallback, never single point of failure.
6. Durable local outbox if none are reachable.

Large downloads/build artifacts/Drive bulk sync never silently move to mobile data.

## Delivery semantics

Every notification receives an idempotency key. The producer persists before dispatch. A route may mark only ACCEPTED/DELIVERED after positive acknowledgement. Timeouts retain the row. Reconnect drains pending rows in bounded batches. Duplicate delivery is suppressed at both relay and remote side.

## Chat/Gmail tranche contract

For user-invoked project work: Gmail START -> substantive work (~25 min target) -> Gmail END retry until provider ACK -> ChatGPT pointer only. A timeout or client glitch must not require an “eh oh” message from the user.

## Acceptance

R63 is not FIELD_VERIFIED until:
- old phone route capabilities are machine-read back;
- PC->B-EDGE local event transfer survives Wi-Fi/hotspot changes;
- a compact event reaches Telegram through B-EDGE while direct PC Telegram is intentionally blocked;
- cellular bytes remain bounded to the control-plane budget;
- reconnect causes zero duplicate user messages;
- PC reboot and Android process death recover automatically;
- direct-PC failure does not erase queued communication;
- spend remains $0.
