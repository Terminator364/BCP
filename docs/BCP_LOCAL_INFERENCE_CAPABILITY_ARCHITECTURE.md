# BCP — Local Inference Capability Architecture

Status: DESIGN_ONLY / RESEARCHED / P0-NON-BLOCKING  
Date: 2026-09-22  
Canonical base recovered before analysis: `f2e0e0682c693a6abbdabe01f129aa527401dcd6`  
Rule: `SPEC_REFRESH_CURRENT_THEN_MERGE_REFINE_PRESERVE`

## 1. Executive decision

BCP must not be reorganized around Qwen, llama.cpp, PocketPal, or a new AI node.

Local inference is admitted only as a replaceable `MODEL_PROVIDER / CAPABILITY_PROVIDER / EXECUTION_WORKER` behind the existing Model Broker, Capability Registry, Context Pack, Resource Governor, durable mission state, validation, and receipt system.

Target outcome:

`BCP canonical state -> deterministic scheduler/context compiler -> existing Model Broker -> optional LOCAL_INFERENCE provider -> validator -> tool/action -> receipt -> BCP commit`

The system must remain correct with zero local models, zero cloud models, no Internet, and the opportunistic 8 GB phone absent.

## 2. Canonical recovery snapshot

- CURRENT_HEAD at recovery completion: `f2e0e0682c693a6abbdabe01f129aa527401dcd6`.
- R86 was merged only after the exact PR head `ea0c6b186f2ad694e6c095bdc2c8b6107f458a9a` had green CURRENT, Managed Server, Final Acceptance, Coordinated PC, Coordinated Product, Android Build, Android Human-Action, Field Ecosystem and Nexus one-shot gates.
- CURRENT release train: `BCP-0.7.18_EDGE-2.1.2-edge-relay_NEXUS-0.2.6`.
- Candidate full-node train: `BCP-0.7.18_EDGE-2.2.0-full-node_NEXUS-0.2.6`.
- Distributed B-EDGE remains 2.1.2; candidate 2.2 remains unpublished until signing, v2/v3 signature proof, APK hash, Drive CURRENT replacement/readback, and in-place update proof.
- Immediate P0 remains product field bring-up: full-node phone promotion, encrypted/authenticated LAN field proof, direct-boot/black-start, communications/recovery, and real device evidence.
- Local inference remains P1/optional and must not delay those gates.

## 3. Existing BCP mechanisms that MUST be reused

### Authority

BCP is the mission, memory, policy, orchestration, state, validation and receipt authority.

Current authority invariants already include:
- external durable canonical state;
- single writer fencing;
- monotonic revisions/epochs;
- idempotent mutations;
- evidence/readback before promotion;
- explicit memory evidence classes and precedence;
- no provider as canonical memory.

Target V2 still keeps B-EDGE as the eventual default coordinator and PC as a fenced worker; the authority migration itself remains separately field-gated.

### Capability Registry

The existing Room `EdgeCapabilityEntity` already stores:
- project ID;
- capability ID;
- node ID;
- provider;
- capability kind;
- state;
- transport;
- JSON details;
- evidence class;
- observed time;
- expiry/TTL;
- update time.

Therefore **no new registry and no database schema migration are required for the first Local AI design**. Model/runtime fields fit in the existing `detailsJson` envelope until measured scale proves otherwise.

### Resource Governor

`EdgeResourceGovernor` already measures:
- available/total RAM and memory load;
- low-memory signal;
- storage free/reserve/pressure;
- battery and charging;
- power-save;
- Android thermal status;
- network presence/capability/validation;
- metered state.

The important defect for Local AI is semantic, not structural: current `REMOTE_AI` admission assumes validated Internet. Local inference therefore needs one additional provider/resource class inside the same governor, not a second governor.

Proposed future class: `LOCAL_AI`.

### Context Pack and memory admission

The existing BCP Context Pack is canonical. Memory already has provenance, evidence class, TTL, supersession and admission rules.

No `LOCAL_LLM_CONTEXT_PACK` is allowed.

### Model Broker

The Model Broker exists as a strategic/provider-neutral contract and has quota/cost/admission rules, but current maturity remains partial. Remote candidates are still field-unverified. Local inference should be added to this broker, not used as a reason to create another router.

## 4. Field evidence admitted without overclaim

### A21s / 4 GB

User field evidence:
- `Qwen2.5-1.5B-Instruct Q4_K_M`, approximately 1.12 GB GGUF;
- PocketPal / llama.cpp, CPU-only;
- context 1024; batch/ubatch 128; 6 threads; mmap on; mlock off; Flash Attention off;
- approximately 3.5–4.0 tok/s typical, 4.23 tok/s observed peak;
- offline inference works;
- simple arithmetic/instruction-following/reasoning failures were observed.

BCP classification:
`OPTIONAL_COLD_LOCAL_INFERENCE_CAPABILITY / DEVICE_MODEL_RUNTIME_PROVEN_OUTSIDE_BCP / BCP_COEXISTENCE_UNVERIFIED`.

This is not evidence that B-EDGE plus the model can coexist safely on 4 GB.

### Current 8 GB phone

Qwen3-4B Q4_K_M:
- model load observed;
- inference crashes in the tested PocketPal profiles;
- classification: `CURRENT_RUNTIME_PROFILE_UNSTABLE` only.

Qwen2.5-1.5B Q4_K_M:
- runs;
- quality remains limited;
- useful only for low-risk bounded tasks until eval evidence exists.

Qwen3-1.7B Q4_K_M:
- runs correctly in the observed profile;
- Think OFF approximately 6.6–7.3 tok/s on favorable runs;
- TTFT around 1–1.2 s on some runs;
- Think ON works but can consume the output budget;
- observed N Predict 256 may be exhausted by reasoning; 512 allowed the tested answer to finish.

BCP classification:
`PRIMARY_LOCAL_SEMANTIC_CAPABILITY_CANDIDATE / DEVICE_RUNTIME_PROVEN_OUTSIDE_BCP / BCP_INTEGRATION_UNVERIFIED`.

The 8 GB phone remains an opportunistic worker, never infrastructure authority.

## 5. Minimal target architecture

### Logical

`User/Mission
  -> BCP durable mission + deterministic scheduler
  -> canonical Context Pack
  -> deterministic Context Projection
  -> existing Model Broker
       -> DETERMINISTIC_ENGINE
       -> VALIDATED_KNOWLEDGE / ERROR_LEDGER
       -> LOCAL_INFERENCE
       -> REMOTE_FREE_INFERENCE
       -> CHATGPT_ESCALATION
       -> HUMAN_DECISION
  -> validator
  -> permitted tool/action
  -> receipt/readback
  -> canonical BCP commit`

### Physical

B-EDGE A21s:
- durable mission/state;
- Chronicle;
- queue/scheduler;
- memory/capability registry;
- communications;
- resource governance;
- optional cold local inference only if device qualification proves safe.

PC:
- Windows/heavy worker;
- build/test/file operations;
- telemetry/receipts;
- no always-on heavy LLM on the 4 GB PC by default.

BCP Nexus:
- replaceable remote ingress/egress/witness/cockpit functions only;
- no model or memory authority.

8 GB phone:
- opportunistic `LOCAL_INFERENCE` worker;
- capability advertised with TTL;
- disappearance is a normal availability transition.

## 6. Runtime choice

### Option A — llama.cpp in the main B-EDGE process

Advantages:
- minimum IPC;
- fastest call path;
- simple packaging.

Rejected as baseline:
- native crash/OOM can kill the critical B-EDGE process;
- model allocations compete directly with Chronicle/queue/API/scheduler;
- failure containment is too weak for the 4 GB dedicated node.

Use only for a tiny proof harness, never as the default architecture.

### Option B — llama.cpp in a separate BCP Android process

Preferred long-term integrated architecture.

Form:
`B-EDGE main process -> bound IPC service in :bcp_inference -> llama.cpp binding -> GGUF`.

Properties:
- no LAN listener;
- one local generation at a time;
- native crash/process death does not directly kill the B-EDGE main process;
- request/result carry mission/action/revision/idempotency/context hashes;
- late results are rejected after supersession;
- process can be unloaded completely;
- model file is immutable while mapped.

A normal secondary app process is the baseline. Stronger `isolatedProcess` can be evaluated later; Android isolated services lose direct app-data access, so they add file-descriptor/IPC complexity and are not free security.

### Option C — external Android runtime + BCP adapter

Preferred **first device qualification path**, because PocketPal/llama.cpp has already produced field measurements without changing BCP.

It may become a real provider only if the external runtime exposes a stable, authenticated, automatable local interface. UI automation is not a provider API and must not become a production dependency.

Verdict:
- immediate evaluation: C;
- product integration if value is proven: B;
- main-process A: not baseline.

## 7. Capability Registry extension

No schema fork. Add one capability record such as `LOCAL_TEXT_INFERENCE` with details:

- runtime / runtime_version;
- model_id / family / model_hash / quantization;
- model_size_bytes;
- availability;
- profile_id;
- max_context;
- reasoning capability;
- supported structured-output mode;
- expected/observed TTFT;
- expected/observed throughput;
- RAM baseline/peak/headroom;
- battery and charging;
- thermal state;
- network state;
- privacy capability;
- model load state;
- device class;
- known failures;
- evidence status.

State vocabulary:
`AVAILABLE, MODEL_LOADING, READY, GENERATING, UNLOADED, TEMP_UNAVAILABLE, THERMAL_HOLD, LOW_RAM_HOLD, BATTERY_HOLD, NETWORK_UNREACHABLE, ANDROID_KILLED, MODEL_MISSING, MODEL_HASH_MISMATCH, RUNTIME_ERROR, STALE_CAPABILITY`.

TTL expiry changes routing availability only; it never deletes mission state.

## 8. Model Broker extension

One new provider category:
`LOCAL_INFERENCE`.

No second router.

Selection inputs:
- requested capability;
- privacy class;
- verified task-quality history;
- current capability TTL/state;
- RAM/storage/battery/thermal;
- model load cost;
- latency/deadline;
- network state;
- remote free quota;
- monetary spend;
- resource cost;
- B-EDGE criticality;
- context fit;
- evidence class.

Objective:
`VERIFIED_USEFUL_WORK / TOTAL_RESOURCE_COST` subject to availability, safety and evidence constraints.

The broker must prefer a deterministic answer over any LLM answer when both can satisfy the task.

## 9. Resource cost model

ZERO_USD is only one dimension.

Provider cost vector:
- monetary_cost;
- ram_pressure;
- battery_cost;
- thermal_cost;
- latency;
- load_time;
- network_cost;
- storage_cost;
- token_budget;
- availability_risk;
- impact_on_bedge.

The Resource Governor remains authoritative for local admission.

### LOCAL_LLM_ADMISSION_GATE

Hard deny:
- B-EDGE critical integrity/recovery job active;
- current memory pressure or insufficient measured headroom;
- severe thermal state;
- model hash mismatch/corruption;
- storage reserve violated;
- superseded mission/context;
- runtime crash-loop hold.

Normally defer:
- battery low and not charging;
- power-save;
- better already-ready provider available within deadline;
- large model cold-load would jeopardize current foreground mission;
- device capability TTL stale.

A21s policy:
`DENY BY DEFAULT UNTIL BCP_COEXISTENCE_DEVICE_QUALIFICATION`.

8 GB phone policy:
`OPPORTUNISTIC_PREFERRED_LOCAL_WORKER WHEN READY AND RESOURCE-SAFE`.

No fixed RAM threshold is asserted before instrumentation. Device qualification must measure real peak memory and establish:
`required_headroom = observed_peak_delta + BCP_safety_reserve`.

## 10. Context Projection, not a second Context Pack

Pipeline:
`canonical Context Pack -> deterministic compiler -> provider-specific projection -> model`.

Profiles:
- `LOCAL_1024`;
- `LOCAL_1536`;
- `LOCAL_2048`.

Always preserve:
- mission/action;
- objective;
- worker role;
- applicable invariants/policy;
- permissions;
- canonical revision;
- necessary facts/evidence;
- relevant known errors;
- resource constraints;
- output schema;
- `context_pack_hash`.

Drop first:
- narration;
- redundant history;
- unrelated details;
- superseded states;
- optional explanations.

Normative authorization/policy text is never summarized by the same small model whose action depends on it.

## 11. Provider-neutral request/response

### BCP_MODEL_REQUEST

Minimum fields:
- schema_version;
- mission_id;
- action_id;
- idempotency_key;
- expected_revision;
- requested_capability;
- context_pack_hash;
- context_projection_profile;
- privacy_class;
- reasoning_mode: OFF/AUTO/ON;
- generation_token_budget;
- reasoning_token_budget;
- final_answer_token_reserve;
- deadline;
- resource_budget;
- output_schema;
- validation_requirements.

### BCP_MODEL_RESULT

Minimum fields:
- provider_id;
- node_id;
- model_id;
- model_hash;
- runtime/runtime_version;
- request_hash;
- context_pack_hash;
- source_revision;
- structured_output;
- stop_reason;
- metrics;
- reasoning_mode;
- validation_status;
- evidence_refs;
- generated_at.

Adapter protocols may be llama.cpp native, OpenAI-compatible, Gemini, Groq or future providers. No external API shape becomes the internal BCP architecture.

## 12. Think/reasoning policy

Default: `OFF`.

Broker examples:
- classify/extract/summarize/known-error candidate: OFF;
- novel diagnosis: AUTO;
- bounded architecture critic: ON only with explicit budget.

For ON/AUTO:
- reason is recorded;
- reasoning budget is bounded;
- final-answer token reserve is separate;
- deadline/resource margin must permit it;
- exhaustion before final answer returns `NEEDS_ESCALATION`, never fabricated completion.

Current llama.cpp exposes reasoning on/off/auto and a reasoning token budget, so BCP can model this as a provider capability rather than a Qwen-specific architectural rule.

## 13. Structured-output and validation policy

Preferred output is constrained JSON.

Example classification:
`{
  "classification": "KNOWN_ERROR|NOVEL|AMBIGUOUS|UNKNOWN",
  "proposal": null,
  "evidence_refs": [],
  "confidence": "LOW|MEDIUM|HIGH",
  "needs_escalation": true
}`

llama.cpp supports grammar and JSON-Schema-constrained generation. This improves syntax adherence, not truthfulness.

Invariant:
`MODEL_PROPOSES -> VALIDATOR_CHECKS -> TOOL_EXECUTES -> RECEIPT_PROVES -> BCP_COMMITS`.

Never:
`MODEL_OUTPUT -> DIRECT_CANONICAL_MUTATION`.

## 14. Memory safety

All LLM output starts as `MODEL_PROPOSED`.

It cannot self-promote to:
`MACHINE_VERIFIED, USER_DECLARED, POLICY, CANONICAL, PINNED`.

Admission validates:
- context hash and source revision;
- output schema;
- authority/evidence class;
- contradictions;
- supersession;
- sensitive-content filter;
- integrity hash;
- deterministic evidence requirements.

Prompt/log/retrieved content is untrusted data and cannot carry authority markers merely by saying so.

## 15. Model storage and distribution

### Control plane in GitHub

GitHub stores:
- manifests;
- hashes;
- licenses/upstream refs;
- profiles;
- benchmark receipts;
- routing and compatibility;
- failure ledger;
- eval definitions.

Normal Git must not contain GGUF weights: GitHub blocks regular repository files above 100 MiB.

### Model bytes

Allowed sources:
- exact upstream/model source;
- personal Drive mirror;
- optional GitHub Release asset when appropriate;
- device cache;
- LAN/local transfer;
- Quick Share/manual local transfer as bootstrap fallback.

Git LFS is not selected by reflex. GitHub Free/Pro LFS permits files up to 2 GB but introduces separate storage/transfer semantics. GitHub Releases also permit assets under 2 GiB, but a 1+ GB model should still not be repeatedly pulled over unreliable WAN when a verified local copy exists.

### Immutable model cache

Each model instance is keyed by SHA-256.

Rules:
- download to `.partial`;
- resume where the source supports it;
- verify size + SHA-256;
- atomic rename into a hash-addressed immutable path;
- never overwrite/truncate a model while mmap is active;
- do not GC a leased/loaded hash;
- reuse exact hash without redownload;
- wrong file with same filename is rejected;
- stale mirror cannot supersede a newer manifest without explicit version policy.

Large transfer policy:
prefer already-cached -> LAN/local -> exact upstream/mirror according to reachability/cost; prefer charging and non-metered network for large downloads.

## 16. Observability

Every local inference attempt records non-secret metadata:
- mission/action/node;
- provider/model/model_hash;
- runtime version/profile;
- request/context hashes;
- context/generation token counts;
- reasoning mode;
- TTFT;
- generation throughput;
- load time;
- RAM before/after/peak if measurable;
- battery/charging;
- thermal;
- network state;
- stop reason;
- result status;
- validator status.

Never log credentials, API tokens, private raw memory corpus, or unnecessary prompt payloads.

## 17. BuildHub decision

Classification: `REDUCE / KEEP AS SPECIALIZED BUILD FACTORY`.

Reason:
- GitHub Actions already provides CI orchestration;
- BCP owns canonical mission/state;
- B-EDGE owns phone-side durable edge functions;
- ChatGPT-PC owns Windows execution;
- duplicating orchestration/memory/model routing inside BuildHub would be harmful.

Keep BuildHub only where it adds a real capability:
- reusable build execution/packaging;
- offline/local build path if field need proves it;
- durable build receipts consumable by BCP.

Do not give BuildHub a Model Broker, scheduler authority or Local AI responsibility.

Retirement remains conditional on proving all useful build functions are covered elsewhere; no automatic deletion decision is made here.

## 18. ChatGPT-PC impact

No local heavy model is moved onto the 4 GB PC by default.

ChatGPT-PC remains:
- Windows executor;
- capability source;
- telemetry/receipt producer;
- BCP transport/recovery participant;
- consumer of Model Broker results.

It must not become a second memory authority, scheduler, broker or permanent LLM host.

## 19. P0 acceleration boundary

Local AI research is complete enough to **stop designing it for now**.

It must not block:
1. post-merge sanity of R86;
2. signed 2.2 candidate production;
3. v2/v3 signature/hash proof;
4. Drive CURRENT replacement/readback;
5. in-place update;
6. full-node field test;
7. reboot/black-start/recovery proof;
8. communications/relay truth.

No Local AI product code should be merged before those immediate field gates unless it directly fixes a demonstrated P0 blocker.

## 20. Promotion gates for Local AI

`DESIGN_ONLY`:
architecture/policy/eval/chaos complete.

`IMPLEMENTED`:
provider adapter + admission + projection + receipt plumbing exist.

`CI_VERIFIED`:
fake-provider, schema, routing, stale-context, failure-injection and security tests pass without full GGUF.

`RUNTIME_VERIFIED`:
runtime adapter works in a controlled Android process.

`DEVICE_VERIFIED`:
specific device/model/hash/profile passes resource + quality eval.

`BCP_INTEGRATION_VERIFIED`:
mission -> projection -> model -> validator -> receipt -> no-authority-corruption path proven.

`FIELD_VERIFIED`:
repeated useful BCP work under real battery/network/thermal/reboot conditions.

PocketPal PASS is never BCP FIELD PASS.

## 21. Research findings — SOURCE_VERIFIED

Checked 2026-09-22:

1. llama.cpp Android documentation supports Android Studio binding and Android NDK builds; it warns that context size can spike memory and kill the terminal.
   - https://github.com/ggml-org/llama.cpp/blob/master/docs/android.md
   - https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md

2. llama.cpp CLI supports grammar/JSON Schema constrained generation and reasoning on/off/auto with reasoning budgets.
   - https://github.com/ggml-org/llama.cpp/blob/master/tools/cli/README.md

3. Android may reclaim/kill processes under memory pressure; cached/background processes are explicitly kill candidates.
   - https://developer.android.com/topic/performance/memory/guide/system-wide-memory
   - https://developer.android.com/reference/kotlin/android/app/Activity

4. WorkManager periodic execution is inexact and minimum periodic interval is 15 minutes; long-running workers use foreground execution mechanisms and remain subject to platform quotas.
   - https://developer.android.com/develop/background-work/background-tasks/persistent/getting-started/define-work
   - https://developer.android.com/develop/background-work/background-tasks/persistent/how-to/long-running

5. Android 15 limits dataSync/mediaProcessing foreground-service use to six hours in a 24-hour period for targeting apps, reinforcing on-demand rather than permanent inference.
   - https://developer.android.com/develop/background-work/services/fgs/timeout

6. Qwen3-1.7B and Qwen2.5-1.5B-Instruct upstream pages report Apache-2.0; Qwen3 supports explicit thinking/non-thinking operation.
   - https://huggingface.co/Qwen/Qwen3-1.7B
   - https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct

7. Hugging Face Hub download tooling uses a cache/metadata mechanism to avoid unnecessary redownloads when files are unchanged.
   - https://huggingface.co/docs/huggingface_hub/guides/download

8. GitHub blocks regular repository files over 100 MiB; Git LFS plan limits and Release assets are separate mechanisms. Release assets must be under 2 GiB each.
   - https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github
   - https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage
   - https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases

## 21B. Forum/community signals — practical only, not authority

These signals do not override device receipts or primary documentation.

- Recent LocalLLaMA reports show small 1B-class models running fully offline on Android, with large throughput variation by device/context/runtime. This supports treating performance as a per-profile capability, not a model-wide constant.
  - https://www.reddit.com/r/LocalLLaMA/comments/1rm9f1m/running_a_local_llm_on_android_with_termux_no/
- PocketPal users/developers repeatedly report memory, backend and chat-template sensitivity. This supports the rule that one failed 4B profile is not proof that all 4B configurations are impossible, and that model/runtime/profile/template belong in the qualification identity.
  - https://www.reddit.com/r/LocalLLaMA/comments/1fppt99/
  - https://www.reddit.com/r/LocalLLaMA/comments/1rktgha/
- Community reports also note that UI wrappers may not expose a stable text-completion API. This reinforces using PocketPal as an evidence/qualification tool unless a stable automatable provider interface is actually verified.
  - https://www.reddit.com/r/LocalLLaMA/comments/1moabey/llamacpp_on_android/

## 22. Contradictions removed

- “Local = free” -> false; local has RAM/battery/thermal/load/storage/availability costs.
- “7 tok/s = good provider” -> false; useful verified task success is the KPI.
- “Qwen3-4B crashed = 4B impossible” -> false; only that tested runtime/profile is unstable.
- “A21s runs 1.5B = B-EDGE can safely host it” -> false; coexistence is unproven.
- “Separate process solves everything” -> false; it adds IPC, late-result and lifecycle failures.
- “JSON grammar means answer is true” -> false; it constrains form only.
- “mmap lowers risk enough” -> false; memory pressure and model-file lifecycle still need explicit controls.
- “GitHub can just store 1+ GB weights” -> false for normal Git and usually inefficient for RDC repeated transfer.
- “Think ON is smarter therefore default” -> false; reasoning can consume the output budget and resources without guaranteeing correctness.
- “Local AI can fix deterministic state truth” -> forbidden.

## 23. Final self-attack

### Complexity introduced

Only five new concepts are allowed:
1. `LOCAL_INFERENCE` provider type;
2. `LOCAL_AI` resource class/admission policy;
3. deterministic Context Projection;
4. provider-neutral model request/result envelope;
5. Local AI eval/device qualification.

Everything else reuses existing BCP components.

### New failures created and containment

- separate process dies -> mission remains durable; capability expires; retry/reroute;
- IPC result arrives late -> expected revision/context/action hash rejects it;
- mmap model replaced -> immutable hash path + load lease;
- capability stale -> unavailable, never guessed available;
- model hallucination -> MODEL_PROPOSED + deterministic validation;
- local model unavailable -> remote/deterministic/human routing;
- no Internet -> local/deterministic path still works;
- no local AI anywhere -> BCP correctness unchanged;
- A21s pressure -> model load denied/unloaded before B-EDGE durability is threatened;
- Qwen/llama.cpp replacement -> adapter/manifest change only; internal request contract remains stable.

## 24. Final architecture status

Architecture decision: `MINIMAL_EXTENSION_ACCEPTED_AS_DESIGN_ONLY`.

Recommended next Local AI action: **none in P0 runtime**.

When P0 field bring-up is stable, first implementation should be a fake/local-provider contract plus device eval harness; only after measured value should BCP gain the separate-process llama.cpp provider.

The target remains:

**BCP can exploit local inference when it creates measured value, lose it without state loss, replace it without rearchitecture, constrain it by resources, validate outputs before effect, and continue deterministically with no model available.**

