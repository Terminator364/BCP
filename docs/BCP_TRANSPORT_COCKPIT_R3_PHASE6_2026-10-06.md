# BCP Transport / Human Cockpit — R3 Phase 6

Date: 2026-10-06  
Status: IMPLEMENTATION_CANDIDATE / NOT FIELD CERTIFIED

## 1. Objective

Phase 6 exposes mission/progress/proof projections to human surfaces without making a
transport, UI, phone, Telegram bot, Drive mailbox, Nexus relay, or model conversation
the execution authority.

The control law remains:

`DURABLE BCP STATE -> COCKPIT PROJECTION -> ROUTE PLAN -> TYPED PROVIDER -> ACTION RECEIPT -> ACK`.

No provider callback, chat message, UI animation, or hidden model state can advance the
canonical mission state.

## 2. Reuse, not rebuild

Phase 6 reuses existing BCP transport/provider work:

- Telegram observability/cockpit;
- Nexus transport;
- Drive/store-forward paths;
- B-EDGE relay;
- local native UI;
- capability observations;
- Phase 4 Action Receipts;
- Phase 2 CriticalStore/outbox.

The new fabric is provider-neutral. It does **not** call Telegram, Drive, Nexus, sockets,
or HTTP providers directly.

## 3. Human Cockpit Projection

Contract:

`schemas/bcp_cockpit_projection_v1.schema.json`

A projection contains only evidence-derived information:

- canonical state;
- human state;
- current / last / next step;
- human action required;
- latest durable proof;
- connectivity observations;
- technical references;
- finite progress only when a finite persisted plan exists.

### Progress law

No persisted finite plan -> `finite_progress = null`.

When a finite plan exists:

`percent = floor(completed_verified_steps * 100 / total_steps)`.

The percentage is machine-derived. It is never estimated from elapsed time or model
reasoning.

### Proof law

`last_proof` is chosen only from durable mission events. A UI/model event such as
“thinking”, “working”, or “almost done” is not proof and cannot become the last proof.

Hidden reasoning fields are rejected rather than exported.

## 4. Transport Delivery

Contract:

`schemas/bcp_transport_delivery_v1.schema.json`

Durable namespace:

`transport/<project>/<delivery_id>`

A delivery persists:

- exact cockpit projection hash;
- requested human surface;
- preferred transports;
- target proof scope;
- route selection;
- idempotency key;
- delivery status;
- normalized Action Receipt reference.

The same delivery id cannot silently change content.

## 5. Routing policy

Routes are selected from `bcp.capability_observation/1`, never from hard-coded provider
availability.

Typical order for Telegram surface:

1. direct Telegram capability;
2. Nexus/B-EDGE typed live relay when qualified;
3. Drive/store-forward when allowed;
4. explicit WAITING_AUTH / WAITING_NETWORK / NO_ROUTE.

Low-data policy and stale observations are honored.

A FIELD delivery requires FIELD_READBACK-quality capability observation. Repository or
simulation evidence cannot be silently upgraded to FIELD.

## 6. Acknowledgement law

A route plan contains a typed `capability_id` and provider id. It contains no shell,
command, argv, executable path, provider token, or provider-specific API request.

Delivery becomes ACKNOWLEDGED only after a real immutable `bcp.action_receipt/1`:

- exists in ActionReceiptRegistry;
- matches project;
- matches selected provider;
- matches capability id;
- satisfies the route evidence contract;
- is SUCCEEDED/PASS;
- is FIELD-certified when target scope is FIELD.

A provider returning “OK” outside the receipt chain is not delivery proof.

## 7. Store-forward

Store-forward is a routing mode, not execution authority.

A store-forward provider may durably accept a projection while the destination is
offline. The delivery remains represented honestly until destination/provider evidence
satisfies its contract.

## 8. Read-only microkernel API

Phase 6 adds authenticated read-only views:

- `GET /v2/cockpit?project=<project_id>`
- `GET /v2/deliveries?project=<project_id>`

No POST cockpit, dispatch, Telegram-send, Drive-send, Nexus-send, shell, or command
endpoint is added.

Actual dispatch remains a typed capability operation under the permission/capability
plane.

## 9. No hidden runtime clock

Phase 6 creates no polling loop, scheduler, resident transport worker, retry thread, or
background timer.

A scheduler/controller may later request a new projection or dispatch work unit.
The transport module itself does not become the runtime clock.

## 10. Repository acceptance

PASS requires:

1. schemas parse;
2. projection validation tests pass;
3. no percentage without finite persisted plan;
4. non-durable UI/model events cannot become proof;
5. hidden-reasoning fields are rejected;
6. direct/fallback/store-forward routing tests pass;
7. FIELD routing rejects weaker capability evidence;
8. delivery idempotency and collision tests pass;
9. invented/wrong provider/wrong capability receipts are rejected;
10. evidence-contract mismatch is rejected;
11. FIELD delivery requires FIELD-certified receipt;
12. no shell/provider API/network loop exists in the fabric;
13. microkernel Phase 6 surface is GET-only;
14. Phase 5/4/3 regressions remain green;
15. no field certification claim.

## 11. Field gates

Repository PASS is not field PASS.

Field certification later requires a batched campaign proving actual provider bindings
and delivery receipts for the selected real transports (for example Telegram/Nexus/B-EDGE)
without turning Desktop Commander into a runtime dependency.

Desktop Commander remains LAST_MILE_METERED.
