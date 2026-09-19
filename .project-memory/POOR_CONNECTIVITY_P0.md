# API / BCP — Poor-Connectivity and UI-Unresponsiveness Requirement

Status: P0 PRODUCT REQUIREMENT
Adopted: 2026-09-19

## Observed user pain

The user regularly experiences unstable connectivity and ChatGPT/browser responsiveness problems during long technical sessions, including request timeouts and browser prompts such as wait/quit page when entering or using a project conversation.

These are external conditions the product must tolerate rather than assume away.

## P0 requirements

API/BCP MUST be designed so that:
- project state is local-first and durable outside the browser tab;
- a slow/frozen ChatGPT page does not imply project failure;
- requests/jobs are queued durably before dispatch where feasible;
- retries use bounded exponential backoff and idempotency keys;
- already-dispatched bounded jobs can continue independently of the browser conversation;
- long operations expose machine-readable progress and receipts;
- reconnect resumes from the last committed checkpoint, not from the beginning;
- transient network loss cannot duplicate writes;
- uploads/downloads should be resumable or chunked when the transport supports it;
- telemetry and recovery metadata remain lightweight enough for low-bandwidth links;
- the control path should degrade gracefully to a lightweight client or alternate front-end when the main ChatGPT web UI is unavailable;
- the user should not have to keep a heavy browser tab alive for project continuity.

## Architecture implication

ChatGPT is a reasoning/interface layer, not the sole runtime. Canonical project state and durable execution should live in BCP/ChatGPT-PC/B-EDGE/BuildHub as appropriate.

## Non-goal

BCP cannot make the ChatGPT website itself immune to network outages, browser hangs, or platform timeouts. Its job is to make those failures nonterminal for the user's projects.

## Field acceptance

Before declaring this requirement complete, test:
1. disconnect network during a queued/running job;
2. close or freeze the ChatGPT browser tab;
3. reconnect from a fresh conversation/client;
4. verify no duplicate mutation;
5. verify the same canonical revision and job state;
6. resume from the next uncommitted action without manual reconstruction.
