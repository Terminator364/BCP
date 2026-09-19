# API/BCP — Free API, Model Broker and Autonomous Loop Requirements

Status: STRATEGIC REQUIREMENT — subordinate to P0 continuity/field bring-up
Adopted: 2026-09-19

## Why this exists

API/BCP must not depend on one chat session, one AI provider, one browser tab, or one cloud path.
The system should be able to use legitimate free/zero-cost external APIs and local/device capabilities as replaceable adapters while preserving one canonical project state, bounded execution, receipts, and deterministic recovery.

This requirement is especially relevant when the primary ChatGPT conversation is delayed, rate-limited, under additional verification, unavailable, or simply not the best execution path for a narrow task.

It is NOT a mechanism to bypass platform safeguards. External providers and APIs must be used according to their own terms, quotas, permissions and safety requirements.

## Architectural pattern

User mission
  -> BCP canonical state / job planner
  -> Model Broker + Tool/Provider Broker
      -> ChatGPT when appropriate
      -> Gemini / other legitimate zero-cost or BYOK model provider
      -> GitHub / BuildHub
      -> B-EDGE
      -> Drive / Gmail
      -> future specialist APIs
  -> deterministic verifier / receipts
  -> next bounded action
  -> checkpoint

No provider is the canonical project memory. BCP is.

## Model Broker

Create a provider-neutral Model Broker.

Selection inputs:
- capability needed;
- expected quality;
- latency;
- current quota/capacity;
- privacy/data-classification constraints;
- cost;
- network availability;
- tool support;
- context-window needs;
- reliability history.

Required behaviors:
- providers are replaceable adapters;
- detect quota/capacity exhaustion explicitly;
- never silently switch into paid spend;
- default paid spend remains 0 USD;
- if no compliant zero-cost path is available, enter `MODEL_CAPACITY_HOLD` or `COST_HOLD`;
- downgrade/alternate-provider choices must be explicit and auditable;
- provider failure must not corrupt canonical state;
- every AI-produced mutation remains subject to deterministic validation/readback.

Provider examples discussed in prior project work include Gemini/Flash-class models and Groq-backed models. These are examples, not permanent dependencies; actual availability/free tiers must be revalidated at implementation time.

## Agent / autonomous-loop model

An agent is not just a model. It is:

model/provider
+ durable state/memory
+ bounded tool loop
+ explicit rules/permissions
+ objective
+ stop conditions
+ evidence/readback

Multiple logical roles may share one underlying model/provider:
- orchestrator;
- coding worker;
- test/review worker;
- build coordinator;
- research worker;
- summarizer/classifier.

Autonomy rules:
- work in bounded micro-sprints;
- one mutation boundary at a time;
- checkpoint after each committed mutation;
- use idempotency keys;
- deterministic verification precedes optional LLM critique;
- LLM agreement/consensus is not evidence;
- destructive/irreversible actions require the configured human approval gate;
- stop on ambiguity, missing permission, contradictory state, or failed evidence.

## GitHub + BuildHub + B-EDGE loop

Target high-level loop:

BCP job
  -> GitHub / BuildHub / B-EDGE as relevant
  -> result + receipt
  -> optional Model Broker reasoning/critique
  -> next bounded action
  -> checkpoint

This permits a project to continue making progress through durable jobs even when one conversational interface is temporarily unavailable.

GitHub remains a multiplier, not a single point of dependency.
BuildHub remains the build factory.
B-EDGE remains the phone-side edge/relay node.
BCP remains the canonical coordination and recovery authority.

## Telegram / lightweight cockpit

A lightweight messaging cockpit is a desired adapter for:
- status;
- build completion/failure notifications;
- compact diagnostics;
- approval requests;
- job pause/resume;
- latest checkpoint;
- read-only project summaries.

Telegram was discussed as one candidate because bot APIs can provide a low-bandwidth, phone-friendly interface. It is an adapter, not canonical state, and must never receive secrets that do not need to leave the trusted execution environment.

The cockpit should be optional and replaceable by another messaging/UI adapter.

## Free/zero-cost API strategy

Candidate categories:
- AI/model APIs with legitimate free tiers or BYOK;
- Telegram Bot API / equivalent messaging adapters;
- GitHub / GitHub Actions within allowed free/public-resource constraints;
- Google Drive / Gmail APIs under the user's account;
- domain-specific free APIs where they materially improve a project.

Rules:
- no architecture may assume an unlimited free tier;
- quota/rate limits are first-class telemetry;
- cache and reuse deterministic results;
- prefer local execution when it is cheaper, faster, or more resilient;
- use circuit breakers and bounded retry/backoff;
- queue work durably when an external provider is unavailable;
- expose provider/quota/cost state to BCP;
- never make the user manually shuttle prompts/results between services in the normal path.

## Relation to current verification/interruption problem

This architecture can reduce the operational impact of:
- ChatGPT additional-verification holds;
- browser freezes/timeouts;
- rate limits;
- temporary provider outages;
- unstable connectivity.

It does so by externalizing state and using alternate legitimate execution/analysis adapters for bounded tasks, not by evading any platform control.

A ChatGPT hold must therefore be treated as:
checkpoint -> keep durable jobs safe -> continue through another allowed adapter where policy and job semantics permit -> reconcile receipts -> resume canonical workflow.

## Low-connectivity / low-RAM constraints

Design for:
- unstable power and Internet;
- low bandwidth;
- low-memory Windows PC;
- old Android phone;
- intermittent browser availability.

Therefore:
- small payloads;
- resumable/chunked transfers where supported;
- lightweight JSON receipts;
- cache-first behavior;
- local queues/outbox;
- no heavy always-on local LLM requirement;
- bounded concurrency;
- graceful degradation.

## Product requirement: user is not the integration layer

The normal user path must NOT be:
copy prompt -> paste in provider A -> copy result -> paste in ChatGPT -> take screenshot -> send log -> retype token/IP.

The normal path must be:
mission -> BCP orchestrates adapters -> machine-readable receipts -> user sees concise result/approval only when needed.

## Promotion order

Do not let this strategic expansion derail the current P0 field bring-up.

Order:
1. prove BCP 0.4.1 runtime/heartbeat and durable telemetry;
2. prove conversation/session interruption survival;
3. prove B-EDGE connectivity/recovery;
4. then add Model Broker/provider adapters incrementally;
5. then add Telegram/lightweight cockpit;
6. then broaden autonomous multi-agent loops.

Each adapter must pass failure-injection, quota, offline, idempotency, and recovery tests before becoming a trusted production path.


## Geographic and field-availability gate

BCP must never treat a provider as usable merely because a marketing page or documentation says a free tier exists.

A provider is ACTIVE only after all of the following are true:
1. `DOC_REGION_OK` — current official documentation does not exclude the user's country/region.
2. `ACCOUNT_ACCESS_OK` — the user's real account can create/authenticate the required credential without false country information.
3. `NETWORK_PATH_OK` — the user's actual Kinshasa/RDC network can reach the API without VPN/proxy/location spoofing.
4. `FREE_TIER_OK` — a real zero-cost allowance exists for the intended API path.
5. `LIVE_CALL_PASS` — a minimal real API request succeeds from the intended runtime.
6. `QUOTA_READBACK_OK` — quota/rate-limit state can be observed or inferred safely.
7. `TERMS_OK` — usage does not require quota evasion, multi-account farming, fake geography, or other prohibited workarounds.

Until all gates pass, provider status is `CANDIDATE_UNVERIFIED`, even if its docs claim regional support.

### Current candidate matrix (2026-09-19)

- Google Gemini API / AI Studio:
  - Official Google availability documentation currently lists the Democratic Republic of the Congo as supported.
  - User-reported field access is currently problematic/unavailable.
  - Therefore status: `DOC_REGION_OK / FIELD_ACCESS_UNVERIFIED_OR_BLOCKED`.
  - Do not make Gemini a required dependency until a real Kinshasa API-key creation + minimal API call passes without VPN or false-country settings.

- GroqCloud:
  - Official docs expose a Free tier and account-level/project rate limits.
  - Groq's current service agreement explicitly defines an EMEA/Africa contracting path; no DRC-specific exclusion was found in the reviewed docs.
  - Status: `HIGH_PRIORITY_CANDIDATE / FIELD_TEST_REQUIRED`.

- OpenRouter:
  - Current official pricing advertises API access on a Free plan, 25+ free models and 50 requests/day.
  - No DRC-specific exclusion was found in the reviewed public pricing/docs.
  - Status: `HIGH_PRIORITY_CANDIDATE / FIELD_TEST_REQUIRED`.

- Mistral API / Studio:
  - Official docs state Free mode is enabled by default with no credit card required, subject to usage/rate limits.
  - No DRC-specific exclusion was found in the reviewed public docs.
  - Status: `HIGH_PRIORITY_CANDIDATE / FIELD_TEST_REQUIRED`.

- Cloudflare Workers AI:
  - Official docs provide a free allocation of 10,000 Neurons/day on the Workers Free plan.
  - No DRC-specific exclusion was found in the reviewed Workers AI docs.
  - Status: `CANDIDATE / FIELD_TEST_REQUIRED`.

- Hugging Face Inference Providers:
  - Free accounts currently receive a small monthly inference credit allowance; routed requests do not require separate provider accounts.
  - Capacity is small, so this is a fallback/experimental adapter, not the primary zero-cost reasoning engine.
  - Status: `FALLBACK_CANDIDATE / FIELD_TEST_REQUIRED`.

### No-circumvention rule

BCP must never recommend or automate:
- VPN/location spoofing to unlock a provider;
- false country/account information;
- multi-account or multi-organization quota farming;
- key sharing from third parties;
- scraping/leaking credentials;
- using unofficial piracy-oriented relay services.

If a provider fails geographic/account eligibility, BCP marks it unavailable and routes to another compliant provider.
