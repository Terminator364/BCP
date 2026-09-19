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


## RDC zero-cost provider plan — evidence ladder

This section is deliberately stricter than ordinary vendor-comparison notes.

### Core rule

A provider is NOT considered usable merely because:
- its website is reachable;
- a consumer subscription exists somewhere;
- a blog says it has a free tier;
- the provider is available in some African countries;
- an account can be created.

For this project, "usable in Kinshasa" means the exact developer API path succeeds from the user's real RDC account/network without VPN, false country information, shared/borrowed keys, billing activation, or quota-circumvention.

Provider lifecycle:
- `DOCUMENTED_CANDIDATE`: official docs support a free developer/API path and no reviewed rule excludes RDC.
- `ACCOUNT_PASS`: real account signup/login succeeds.
- `KEY_PASS`: API credential can be created with no card/billing requirement.
- `KINSHASA_SMOKE_PASS`: one minimal API request succeeds from the user's real Kinshasa network.
- `QUOTA_PASS`: free quota/limits are machine-readable or can be safely learned from responses/dashboard.
- `BCP_ADAPTER_PASS`: BCP adapter handles success, auth failure, 429, timeout and quota exhaustion.
- `ACTIVE_FREE_PROVIDER`: all prior gates pass.

Until `KINSHASA_SMOKE_PASS`, never describe a provider as field-verified in RDC.

### Important Google distinction

Google consumer products and Google developer APIs have separate availability rules.

- Google currently lists the Democratic Republic of the Congo as an available region for Google AI Studio and the Gemini API.
- This does NOT imply that every Google AI / Gemini consumer paid subscription (for example Google AI Pro) is available in RDC.
- Therefore the user's prior inability to subscribe to a consumer Gemini plan must not be used as proof that the Gemini developer API is unavailable, nor may documentation alone be used as proof that it works for this account.

Gemini remains a candidate only until an actual Kinshasa API-key + smoke call succeeds.

### Ordered zero-cost plans

#### PLAN A — Mistral API Free mode

Why first:
- official developer docs state Free mode is enabled by default;
- API keys can be created in Free mode;
- no credit card is required;
- usage/rate limits apply;
- OpenAI-style chat completion semantics are straightforward for a broker adapter.

Current status: `DOCUMENTED_CANDIDATE`.
Field requirement: real Kinshasa signup -> API key -> one minimal completion -> record headers/limits.

Failure outcome: do not troubleshoot with VPN or alternate-country registration; mark `REGION_OR_ACCOUNT_BLOCKED` and move to Plan B.

#### PLAN B — GroqCloud Free tier

Why second:
- official billing docs distinguish a Free tier from Developer paid tier;
- payment method is required to upgrade, not to remain Free;
- official free-tier rate limits are documented and exposed via response headers;
- current Groq terms contain a contracting path for customers domiciled in Europe, Middle East or Africa;
- OpenAI-compatible API surface and very fast inference are suitable for low-RAM/offline-first orchestration.

Current status: `DOCUMENTED_CANDIDATE`.
Field requirement: real Kinshasa signup -> API key -> minimal inference -> capture rate-limit headers.

Hard rule: never create multiple accounts/organizations to multiply quota; Groq explicitly prohibits usage orchestration intended to bypass published limits.

#### PLAN C — OpenRouter Free

Why third:
- official current Free plan exposes API access;
- 25+ free models;
- no payment option is required on the Free plan;
- current Free-plan ceiling is 50 requests/day;
- one API key can expose multiple upstream free models, making it a useful fallback broker behind BCP.

Current status: `DOCUMENTED_CANDIDATE`.
Field requirement: real Kinshasa signup -> free API key -> call `openrouter/free` or one current `:free` model.

Caveat:
- individual upstream models may have their own geographic restrictions;
- OpenRouter terms explicitly prohibit using VPN/proxies to reach restricted models.
- Therefore BCP must treat provider-level and model-level region eligibility separately.

#### PLAN D — Cloudflare Workers AI Free

Why fourth:
- Cloudflare documents a Workers Free account path with no credit card in its onboarding material;
- Workers AI currently includes 10,000 Neurons/day free;
- multiple useful LLMs remain available on Workers Free;
- Cloudflare already has network presence/traffic infrastructure in Kinshasa, which is favorable for latency/resilience but is NOT itself proof of Workers AI account eligibility.

Current status: `DOCUMENTED_CANDIDATE`.
Field requirement: real Kinshasa Cloudflare signup -> Workers AI API token -> minimal REST inference -> daily quota readback.

This is especially useful as an independent infrastructure/provider failure domain.

#### PLAN E — Gemini API Free tier

Why retained but not relied on:
- Google officially lists Democratic Republic of the Congo for Google AI Studio/Gemini API;
- developer-API availability is separate from consumer Google AI Pro subscription availability.

Current status: `DOCUMENTED_REGION_OK / FIELD_UNVERIFIED`.
Field requirement: real existing/new Google account -> AI Studio/API key path -> minimal Gemini API call from Kinshasa without VPN or false geography.

If the account UI blocks the user, simply mark it unavailable and continue with A-D.

#### PLAN F — Hugging Face Inference Providers

Why last-resort:
- one Hugging Face account can route to multiple inference providers;
- free users currently receive only a small monthly inference credit allowance ($0.10 at the time of this review);
- useful for compatibility tests and emergency small jobs, not a primary autonomous-work budget.

Current status: `FALLBACK_CANDIDATE`.

### Broker policy

BCP provider priority is not permanently hard-coded. Initial bootstrap order is:

`MISTRAL_FREE -> GROQ_FREE -> OPENROUTER_FREE -> CLOUDFLARE_WORKERS_AI_FREE -> GEMINI_FREE_IF_FIELD_PASS -> HUGGINGFACE_FALLBACK`

After field tests, BCP must rank only ACTIVE providers by:
1. actual free capacity remaining;
2. job capability fit;
3. observed reliability from Kinshasa;
4. latency;
5. context requirements;
6. privacy/data policy;
7. recent 429 / capacity failures.

A provider that requires a card, billing activation, false geography, VPN, borrowed credentials, paid credits, or quota farming is automatically excluded from the ZERO_USD pool.

### Zero-cost exhaustion behavior

If every ACTIVE_FREE_PROVIDER is exhausted or unavailable:
- persist the job;
- return `FREE_MODEL_CAPACITY_HOLD`;
- wait for documented quota reset or provider recovery;
- continue deterministic/local work that does not require an LLM;
- never auto-enable billing.

### First field-validation sprint

The first real provider test must be deliberately tiny and performed one provider at a time:
1. open provider signup from normal Kinshasa connection;
2. create account using real country/account data;
3. create API key without entering a payment method;
4. send one harmless minimal prompt;
5. store only provider name, model, timestamp, HTTP status, latency, quota headers/remaining capacity and a fingerprint of the key — never the key itself;
6. mark PASS/FAIL with exact failure class;
7. immediately move to the next plan if region/account/payment blocks occur.

The user must not manually shuttle API responses between providers in normal operation. These manual field checks are bootstrap-only; BCP should own the adapters afterward.


## 24-hour endurance and quota-allocation policy

### Objective

BCP MUST optimize for continuous useful work over a full day, not maximum instantaneous LLM throughput. A continuous chantier means continuous progress, not continuous prompting.

Default design target:
- deterministic/local execution performs the overwhelming majority of operations;
- LLM calls are sparse, event-driven and justified by unresolved semantic work;
- free-provider capacity is treated as a finite strategic resource;
- normal work must preserve capacity for user-facing incidents later in the day;
- the system must remain useful even when every free LLM provider is exhausted.

### Escalation ladder

Every event/job MUST begin at the lowest adequate layer and escalate only when lower layers cannot resolve it:

1. `L0_EVENT_ENGINE` — heartbeat, queueing, sync, checksums, lifecycle, telemetry, timers, retries, outbox.
2. `L1_RULE_ENGINE` — deterministic policy and known-condition handling.
3. `L2_KNOWLEDGE_CACHE` — ERROR_LEDGER, validated recipes, prior receipts, deduplicated known incidents.
4. `L3_LOW_COST_MODEL` — classification, compact summarization, simple routing where an LLM is genuinely needed.
5. `L4_REASONING_MODEL` — diagnosis, code generation, architecture reasoning, novel incident analysis.
6. `L5_HUMAN_CHATGPT` — high-impact ambiguity, cross-system architectural decisions, low-confidence conflicts, or work explicitly escalated to the user's ChatGPT Plus session.

A task MUST NOT be promoted to a higher layer merely because model capacity is available.

### Local-first rule

The following MUST NOT consume LLM quota by default:
- heartbeats and liveness checks;
- network up/down detection;
- battery/RAM/CPU/disk observation;
- file transfer and synchronization;
- hashing/signature/readback;
- build invocation;
- test execution;
- deterministic retry/backoff;
- known-error recovery with validated recipe;
- queue/outbox replay;
- checkpoint creation;
- routine templated notifications;
- cache lookup and deduplication.

### Batching and deduplication

BCP MUST NOT map one event to one LLM call.

Before any model call, the broker MUST:
1. aggregate related events over a bounded window;
2. deduplicate equivalent observations;
3. group events by causal incident when possible;
4. resolve known incidents from rules/cache/ERROR_LEDGER;
5. remove information already represented in canonical state;
6. send one compact evidence package only for the unresolved remainder.

Offline replay MUST be compacted before any LLM use. Thousands of queued events may produce zero, one or a few model calls after local reconciliation.

### Provider-budget model

Provider limits MUST be discovered from real account/API telemetry whenever possible. BCP MUST NOT hard-code marketing quotas as operational truth.

For each ACTIVE_FREE_PROVIDER, track at minimum:
- provider/model;
- quota dimensions exposed by the provider (requests, tokens, compute units/Neurons, monthly credits, etc.);
- observed remaining capacity;
- reset policy/window if known;
- p50/p95 latency;
- recent success/error/429 rate;
- task-type success history;
- last successful Kinshasa smoke test;
- estimated consumption of the pending call.

Initial conservative allocation policy after field validation:
- at most ~50% of measured free capacity for planned/background work;
- ~25% reserved for fallbacks and user-impacting incidents;
- ~25% strategic reserve protected from ordinary jobs.

These percentages are bootstrap policy, not provider facts. BCP may adapt them after sufficient telemetry, but MUST preserve a non-zero emergency reserve unless explicitly overridden.

### Soft limits, hard limits and conservation mode

Each provider MUST have:
- `SOFT_LIMIT` — normal work begins to reroute/defer;
- `RESERVE_FLOOR` — background jobs may not cross it;
- `HARD_LIMIT` — BCP refuses further calls before accidental paid usage or uncontrolled exhaustion.

When a provider approaches its soft limit, the broker SHOULD raise its internal routing cost and prefer cache, deterministic execution or another ACTIVE_FREE_PROVIDER.

When global free capacity becomes constrained, BCP enters `AI_CONSERVATION_MODE` and continues useful non-LLM work such as tests, fuzzing, benchmarks, dependency checks, static analysis, log processing, backups, deterministic AX150K exploration, and known-error remediation.

If no compliant free model path remains, enter `FREE_MODEL_CAPACITY_HOLD` for LLM-dependent work while continuing all safe deterministic work.

### Global multi-project budget

Parallel projects MUST share one global AI budget. A background chantier may never monopolize all free-provider capacity.

The scheduler MUST support dynamic project weights, for example:
- normal continuous-improvement project: background priority;
- user-facing broken PhoneMouse/P2PCR95 path: user-impacting priority;
- urgent recovery/security-integrity incident: critical priority.

Weights are dynamically rebalanced. Paused or background projects checkpoint cleanly when a higher-priority incident needs reserved capacity.

### Single-provider default and cross-check policy

The normal path is one provider per reasoning step.

BCP MUST NOT fan the same prompt to all providers by default.

A second or third model may be used only for explicit reasons such as:
- materially low confidence;
- contradictory diagnoses;
- high-impact architectural decision;
- failed first-provider attempt;
- designated audit/critic step where independent review is justified.

Cross-checks are bounded and audited; model agreement is never treated as proof without deterministic verification.

### Model-role policy

Logical agents are provider-neutral. Multiple agents may share one provider, and one agent may switch providers through the broker.

Initial role preference MAY favor:
- low-latency/free models for classification and log triage;
- stronger code/reasoning models for patch design and novel diagnosis;
- OpenRouter-like aggregators primarily as reserve/multi-model fallback;
- independent infrastructure providers as failure-domain diversity.

These are hypotheses only. After field telemetry, routing MUST be driven by measured capability, reliability, latency and remaining free capacity rather than brand preference.

### Call admission circuit breaker

Every LLM request MUST pass a call-admission gate equivalent to:

`provider_call_allowed(job, provider, model)`

The gate MUST reject, defer or reroute when any of the following applies:
- deterministic result already exists;
- equivalent request/result is cached;
- same incident was recently resolved;
- provider is unhealthy or rate-limited;
- projected call would violate reserve policy;
- job priority is insufficient for remaining capacity;
- provider is not ACTIVE_FREE_PROVIDER;
- projected monetary cost is non-zero under ZERO_USD policy;
- duplicate/retry loop is detected;
- request exceeds configured context/token budget.

This gate MUST prevent a buggy agent loop from draining all providers.

### Continuous chantier execution model

A command such as "continue improving the architecture" MUST create a durable long-running mission composed of bounded cycles:

observe -> identify next weakness -> resolve locally if possible -> call broker only if needed -> mutate -> deterministic test -> audit -> checkpoint -> next cycle.

The mission MUST stop/pause on:
- no meaningful improvement frontier;
- provider reserve floor reached;
- PC resource pressure;
- network/power degradation that makes further work unsafe;
- human approval requirement;
- high-risk/irreversible change;
- repeated failure/no-new-evidence condition.

BCP MUST never interpret "continuous" as an unbounded tight LLM loop.

### ChatGPT escalation path

ChatGPT Plus remains a high-level human-interactive reasoning surface, not a free OpenAI API backend.

Normal operation MUST NOT require the user to manually shuttle prompts between providers. If a hard problem needs ChatGPT-level review and no automated authorized bridge is available, BCP MAY generate one compact, copy-ready escalation packet as a fallback only.

The preferred long-term path is an authorized ChatGPT-PC/BCP bridge that packages canonical context and reconciles the returned result without making the user the integration layer.

### Human-facing AI capacity abstraction

Telegram/UI SHOULD expose one compact `AI_CAPACITY` view instead of forcing the user to understand every provider's quota units.

Minimum view:
- current-day capacity state;
- strategic/emergency reserve state;
- monthly/long-window capacity state where applicable;
- provider health states;
- number of model calls avoided by cache/rules;
- current spend, which MUST remain `0.00 USD` under ZERO_USD policy.

Provider-specific details remain available in diagnostics.

### Notification ergonomics

Silence means normal operation.

Telegram/cockpit SHOULD notify primarily for:
- mission completion or meaningful checkpoint;
- user-impacting incident;
- approval/decision required;
- free-capacity hold or recovery;
- requested status/report.

Routine heartbeat success MUST NOT spam the user.

### Telemetry and optimization KPIs

Track at minimum:
- deterministic operations count;
- LLM calls by provider/model/project/task type;
- calls avoided by cache/rules/deduplication;
- tokens/requests/compute units consumed when observable;
- budget and reserve remaining;
- provider 429/timeouts/errors;
- task success/failure after model advice;
- time-to-recovery;
- percentage of incidents resolved without LLM;
- ZERO_USD spend invariant.

A core optimization KPI is:

`AI_CALLS_AVOIDED_WITHOUT_RELIABILITY_LOSS`

The system should become less dependent on repeated model calls as its validated recipes, ERROR_LEDGER and deterministic automation improve.
