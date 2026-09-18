# BCP B-EDGE Pairing Architecture — Canonical

Status: CANONICAL / supersedes manual-IP POC UX

## Role of the old Android phone

The old Android phone is not merely a remote UI. Installing BCP Edge turns it into the **B-EDGE node** of Blessing Control Plane.

B-EDGE responsibilities:
- local durable outbox / store-and-forward;
- cached recovery pointer and project HEAD snapshot;
- local technical telemetry queue;
- pairing identity and credential vault;
- LAN/hotspot continuity when Internet is unavailable;
- delayed synchronization with the PC/control plane after reconnection;
- recovery assistance after ChatGPT/session/network interruptions.

It is not the canonical writer and is not intended to be a permanent public Internet server.

## Pairing model

### Primary path — automatic LAN discovery + one confirmation
1. PC agent advertises a BCP service on the trusted LAN using mDNS/DNS-SD (or bounded UDP fallback if required by the target Android/Windows stack).
2. BCP Edge discovers candidate PCs automatically.
3. The user sees the PC name/fingerprint and confirms once.
4. Credentials are provisioned automatically.
5. PC endpoint, identity and project state are persisted.
6. Future launches reconnect automatically, even if the PC DHCP address changes.

### QR bootstrap — preferred explicit pairing fallback
The PC can display a QR code containing only bootstrap material:
- protocol version;
- ephemeral pairing nonce;
- PC public identity/fingerprint;
- discovery hint/endpoint.

The QR must not embed a long-lived bearer token.

After scan:
- phone and PC complete pairing;
- a scoped credential is issued;
- the bootstrap nonce expires immediately.

### Bluetooth bootstrap — optional transport fallback
Bluetooth may be used for discovery/bootstrap when LAN discovery is unavailable or the local network isolates clients.

Bluetooth is not required to carry the normal BCP data plane. After bootstrap, BCP can use the best available local transport (trusted LAN/hotspot/direct path) while preserving the same paired identity.

## UX rule

Normal mode must not expose fields for IP address, port, bearer token or project ID.

Those fields belong only under:
`Diagnostics > Manual fallback`

## Telemetry

The phone must locally record the staged connection state:
- RADIO_READY
- LAN_READY
- PC_DISCOVERED
- PAIRING_STARTED
- PAIRING_CONFIRMED
- CREDENTIAL_ISSUED
- TCP_REACHABLE
- HTTP_HEALTH_PASS
- AUTH_PASS
- PROJECT_HEAD_PASS
- CHECKPOINT_COMMIT_PASS

If a stage fails, BCP Edge must identify the failing stage without requiring screenshots or manual reasoning.

## Acceptance gate

`BEDGE_ZERO_TOUCH_PAIRING=PASS` only when:
- fresh install requires no IP/token/project typing;
- pairing needs at most one explicit confirmation;
- reconnect works after phone/PC restart;
- reconnect works after DHCP/IP change;
- diagnostics identify the failing stage automatically;
- manual fallback remains available but is not the normal path.
