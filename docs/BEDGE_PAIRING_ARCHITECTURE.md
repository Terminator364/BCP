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

Current P0 compatibility: B-EDGE is not yet the canonical writer; the existing PC-side BCP writer remains authoritative until the explicit V2 authority migration is qualified.

Target V2: B-EDGE becomes the default orchestration coordinator with fencing, while the PC becomes a heavy worker. This target MUST NOT be activated by documentation alone.

B-EDGE is not intended to be a permanent public Internet server.

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


## Dedicated-node orchestration role

B-EDGE is the always-on lightweight coordinator of BCP when the old Android phone is dedicated to the architecture.

It MUST be able to retain and operate:
- active job graph and dependency state;
- project HEAD/checkpoint pointers;
- recent project context and user-policy cache;
- ERROR_LEDGER / known-recipe index;
- provider/quota/health state;
- PC online/offline/resource-pressure state;
- local outbox and delayed-work queue;
- lightweight deterministic scheduler.

B-EDGE SHOULD do the maximum safe pre-agent work locally. It MUST NOT call an LLM merely to decide which already-known task follows another already-known task.

### Operating modes

- `EDGE_ONLY`: PC offline; B-EDGE keeps memory, scheduler, queues, control interface and permitted remote-API access alive.
- `PC_AVAILABLE`: PC healthy; B-EDGE dispatches compute-heavy work to PC.
- `PC_MEMORY_PRESSURE`: PC resource pressure high; heavy work is deferred/queued and light orchestration remains on B-EDGE.
- `PC_UNAVAILABLE_RECOVERY`: preserve committed state and checkpoints, detect PC recovery, reconcile state, and resume from the next uncommitted action.

Mode transitions MUST be evidence-driven from heartbeats/resource telemetry, not inferred from stale state.

### Memory tiers

B-EDGE SHOULD use HOT/WARM/COLD project-memory tiers:
- HOT = active projects cached aggressively in RAM;
- WARM = recent projects with partial in-memory cache;
- COLD = durable SQLite/storage only until requested.

On Android memory pressure, eviction order is HOT cache -> WARM cache -> persistent storage while durable canonical state remains intact.

### Context-pack service

Before an agent or ChatGPT task starts, B-EDGE/BCP SHOULD construct a compact context pack from structured memory:
- stable user/project preferences relevant to the task;
- current project revision/checkpoint;
- validated architectural decisions;
- known errors/recipes;
- current node/provider constraints;
- current objective and next valid actions.

Only relevant context is injected. The entire historical corpus MUST NOT be sent by default.

### Thermal and battery discipline

Dedicated-phone mode permits larger RAM residency, but B-EDGE remains event-driven. Persistent busy loops, aggressive polling, large local LLMs and sustained heavy compute are prohibited by default.

The node should exploit RAM for cache/index/state while keeping CPU/network wakeups bounded and reducing activity automatically on thermal or battery pressure.


## Lifecycle/recovery rule

"Always-on" means recoverable under Android lifecycle rules, not guaranteed process residency.

- scheduler state and queues must be durable;
- process death must be reconstructable;
- WorkManager is the baseline for persistent deferrable work;
- periodic work is inexact and not a sub-minute heartbeat clock;
- permanent foreground data-sync services and exact-alarm loops are not the default architecture.

## Discovery hardening

Primary production discovery SHOULD migrate to Android Network Service Discovery (mDNS/DNS-SD) with a bounded discovery window.

The current raw IPv4 /24 scan is a bootstrap/POC fallback only. It must not run periodically in the background.

Fallback order:
1. NSD/mDNS;
2. QR bootstrap;
3. Bluetooth/companion/system-mediated association where justified;
4. bounded subnet diagnostic scan.

Before targeting Android 17/API 37, B-EDGE MUST implement/test the required local-network permission or supported privacy-preserving system-mediated picker path.

## Authenticated transport

Discovery identity and transport identity must converge.

Production pairing target:
1. PC possesses a persistent cryptographic device identity.
2. Discovery advertises only enough information to locate the service.
3. User confirmation/QR binds the phone to the expected PC identity.
4. Pairing bootstrap nonce is single-use and expires.
5. Normal traffic uses authenticated encrypted transport.
6. Unexpected PC certificate/key identity change enters HOLD and requires explicit re-trust.

The current cleartext HTTP POC MUST NOT transport long-lived bearer/provider secrets in the final production path.

## V2 partition/fencing behavior

After V2 authority migration:
- B-EDGE owns the current coordinator epoch;
- each PC work envelope carries that epoch plus project revision/idempotency identity;
- PC rejects stale epochs;
- PC may finish an already-accepted immutable job during temporary loss of B-EDGE;
- PC preserves the result receipt but does not independently advance global PROJECT_HEAD;
- an automatic coordinator takeover requires a third witness/lease authority or explicit user promotion.

This prevents two disconnected nodes from both becoming canonical writers.
