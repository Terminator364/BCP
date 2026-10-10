# MedBrain Product Rebaseline — architecture and field gate
Date: 2026-10-10
Authority: MedBrain Android existing BCP PR #187 + MedRebuild/Excellentia product sources, not a new repository.
Decision: STOP creating incremental APK releases merely because Android CI turns green.

## Source products actually consulted
- Terminator364/ChatGPT-PC `med-rebuild/core/00_MASTER_BRIEF.md`: D3->D4 clinical reasoning; bedside semeiology, differentials, investigations; cardiology pilot only.
- `med-rebuild/core/01_PEDAGOGY_PROTOCOL.md`: TEACH -> UNDERSTAND -> GUIDED RECALL -> APPLICATION -> CLINICAL CASE -> EXPLANATORY CORRECTION -> REVISION -> VERIFIED MASTERY; no mastery from reading.
- `excellentia-study-cockpit/v2/ARCHITECTURE.md`: spaces & contextual subtabs, resume sessions, evidence-based progression, offline-first, mobile bottom dock, no dead panels.
- `med-rebuild-study-hub/audit/MED_REBUILD_V1_8_EXCELLENTIA_PARITY_RELEASE.md`: Cardiologie 3 tomes, 60 source modules, 156 teaching sheets; source preservation; native app must REUSE, not rebuild these under another curriculum.
- MedBrain installed 0.4.6: 491 books, 3171/17016 pages analyzed, 3117 indexed at latest diagnostic (18.3% of total declared), GGUF 1223 MiB, 2x95-second timeouts, 7% battery, outdated & unrelated references. Those numbers describe progress, not successful machine learning.

## What the user actually ordered
A personal medical AI assistant, not a PDF search form with a narrow model: ChatGPT-like conversational UX (new chat, separate threads, history/search, stable draft, long multi-turn continuity), medicine-first grounded evidence, learn/practice/revise/growth from MedRebuild and Excellentia, local Qwen when feasible, progressive source ingestion, BCP-guided orchestration, no repeated diagnosis screenshots, no PC resource dependency.

## Product architecture
UI State / Navigation
  -> Persistent Threads + Conversation State (topic, intent, unresolved question, last section, references)
  -> Dialogue Manager (follow-up, clarification, topic switch, retrieval eligibility; not 300 canned patterns)
  -> Evidence Broker (FTS now; hybrid BM25/semantic embeddings + rerank & provenance later)
  -> Model Adapter (bounded context, prompt budgeting, warm session, native streaming needed)
  -> Response Validator (relevance, origin of claims, clinical safety, no fabricated citations)
  -> Learning Engine (MedRebuild teaching protocol, distinct student mastery ledger)
  -> Durable Reports / Diagnostics / Updater and Field Telemetry.

## Reliability Gates — necessary, not currently passed
G1 Product UX: new thread, history, switch, delete confirmation, drafts, scroll, theme, keyboard; every button real.
G2 Dialogue: at least 200 diverse, multi-turn scenarios including contextual ellipsis and indirect follow-ups. Distinguish deterministic routing tests from true GGUF evaluations.
G3 Retrieval: 100 real medical queries across 10 disciplines with relevance judgments and zero bogus citation claims. FTS count != knowledge mastered; include no-match behavior and source conflict.
G4 Learning: 20 real tutor activities using objectives, rich explanation, recall, cases, correction and spaced revision; TEACH BEFORE TEST.
G5 Native engine: Galaxy S21 FE, charged >=25%, 10+ turns, latency P50/P95, memory and battery thermals; no 70/95s dead screens. Define acceptable thresholds only after benchmarking.
G6 Release: same Android signing cert, increasing versionCode, SQLite v4->v5 survival, 491 book preservation, rollback and signed Delivery receipt; separate build-green from field-ready.
G7 Offline/concurrency: background ingest cannot starve chat; cold/warm start, kill/reboot recovery and no data loss.

## Initial vertical implementation
Reuse preexisting `chats.thread_id`: schema-v5 metadata only (titles/timestamps), migrate all legacy threads in-place. Add New conversation + History, thread-specific drafts, switch and confirmed delete; capture threadId when async response completes so a message never appears in the wrong thread. Tests for migration and isolation. No model changes, no files removed.

## Outstanding architecture choices
Streaming JNI/Vulkan-backed adapter and Qwen reasoning mode benchmark versus alternate small nonthinking models, semantic retrieval that can be used offline within device limits, structured student progress ledger, live Drive OAuth explicit scopes. No claim that all 491 PDFs became neuron weights; RAG retrieval != training.

## Backend spike 2026-10-10 — candidates researched, not installed
- Vendor AAR current `dev.ffmpegkit-maintained:llama-android:0.1.1` supports blocking completion/embeddings in free release but no streaming, Vulkan, or multiconversation KV cache: https://github.com/ffmpegkit-maintained/llama-android
- Official upstream GGUF `ggml-org/llama.cpp` Android Studio example offers Kotlin Flow streaming: https://github.com/ggml-org/llama.cpp/blob/master/docs/android.md
- `hokanosekai/llama.kt` exposes streaming and chat templating, session/KV cache, CPU and potentially GPU but build/ABI need field verification on S21 FE; no measured gains for MedBrain: https://github.com/hokanosekai/llama.kt
- Google LiteRT-LM Kotlin API streams but uses the LiteRT model ecosystem; existing user GGUF needs migration or a separate backend: https://developers.google.com/edge/litert-lm/android
- Qwen3 official documentation supports hard `enable_thinking=false` when applying the chat template, whereas `/no_think` is a softer preference that cannot guarantee suppressing internal thinking under every wrapper: https://github.com/QwenLM/Qwen3/blob/main/docs/source/getting_started/quickstart.md
Decision: separate InferenceAdapter from UI; benchmark official llama.cpp Android with same GGUF on charged S21 FE, report time to first token and total P50/P95, memory and power; retain existing signed installation until proven. No paid backend dependence.

## Vendor native audit — concrete remaining root cause
`ffmpegkit-maintained/llama-android` main `library/src/main/jni/llama_jni.cpp` lines 173-175 calls `llama_memory_clear(llama_get_memory(h->ctx), true)` for *every* `Llama.complete()` request. Warm GGUF weights do NOT preserve chat KV. Lines 192-199 terminate after `maxTokens` even if answer is unfinished. Public code: https://github.com/ffmpegkit-maintained/llama-android/blob/main/library/src/main/jni/llama_jni.cpp
The vendor `LlamaResult` already exposes tokensGenerated, promptEvalTimeMs, generateTimeMs, and tokensPerSecond, which had been discarded by MedBrain. Diagnostic metadata now collects them (no user prompts in log), and a token-cap termination displays a visible incomplete-answer notice.
These changes make failure observable, not solved. The native streaming/KV-backed replacement remains P0, field-unproven.

## Inference partial-response repair (source implementation; requires Android CI and field)
- New `AnswerContinuationPolicy`: choose 144 default or 160 tokens x up to 2 for explicit detailed questions on battery>=25%; if first reply is *proven budget cut-off*, expose the first useful part immediately and issue one bounded continuation request, with citations retained only from initial evidence.
- Model KV is not preserved by current vendor; second pass uses short original context and tail, not native token-level continuation; 2-part limit cannot guarantee an exhaustive answer.
- Explicit incomplete label remains after the second token-limit; never turn an inference failure into a false completed clinical recommendation.
- Cover limits, no duplicate cutoff notices, battery, failure and long prompts in deterministic tests. Genuine native GGUF streaming remains a separate field gate.

## Lifecycle continuity — recovery from interrupted Android process
- If the latest message in a selected thread is an unanswered user turn (not an in-progress generation), Chat shows `Reprendre la réponse interrompue`.
- Retry validates the same stored last question and does not append a duplicate user message; any generated answer stays associated with its original thread.
- Covers death/restart during native generation, manual thread changes, and urgent response branch, with deterministic unit tests; NO background service or false promise of continuing generation while Android is killed.

## Evidence diversity and observable ingestion coverage
- The homepage now appends the percentage of declared pages genuinely indexed (recomputed from SQLite); 491 discovered books are NOT 491 semantically understood books.
- FTS retrieval reserves up to two pages per actual book when other matching books are present; remaining free slots are filled by original rank. No new citations are invented and no content is thrown away.
- New Robolectric regression builds 3 indexed cardiology books, tests distinct citation diversity and explicit coverage.

## Conversational intent expansion — grammar, not canned replies
- The router additionally recognizes pronominal/anaphoric references and facet-only follow-ups (symptoms, tests, therapy, risks) across more than 120 generated, varied test phrasings.
- Explicit named medical conditions remain independent search queries, rather than being grafted onto the preceding conversation.
- Distinguish this deterministic routing evidence from genuine LLM conversation quality; no assertion of GPT-level semantic understanding.

## 0.5.0 internal candidate (NOT installable yet)
- Build versionCode increments 40 (delivered 0.4.6) -> 41. Same applicationId `com.blessing.medbrain.personal`, Kotlin/SQLite migration additive. GitHub workflow verifies v41 and outputs an explicitly non-installable, unsigned engineering artifact.
- No signing or Delivery publication until Android + BCP CI success plus clinical/multi-turn evaluation on device. Android package identity preservation alone cannot certify that local data survived an actual 0.4.6->0.5.0 upgrade.

## MedRebuild native Android curriculum (read-only / offline)
- Original source `Terminator364/ChatGPT-PC` `hotfix/med-rebuild-v193-r3-final`, `med-rebuild-study-hub/v1.5-prototype/config/cardio-fiches-v18.json` SHA blob f25dd5abc745d630fbecb20587511e09d3cad2b1.
- Full unedited 784,894-character JSON packaged in Android assets, not recreated by Qwen; 60 source modules, 156 fiches, 47/66/43 across 3 tomes. Google Docs source titles and section locators displayed, never fabricated page numbers.
- The Learn UI has a real 3-tome catalogue, module navigation, complete lesson content, learning objectives, essentials and active recall. Optional deeper session combines 2–3 original consecutive fiches with visible headings. Previous/next links and practice action are functional. No neuronal request is required for reading.
- Roboelectric tests verify IDs/content/source traceability and limits. This does not imply all fiches are educationally rich: original lengths range from 147 to 9472 characters; further editorial QA is required. Reading is NOT automatic verified mastery.

## Offline recall path without overstated scoring
- Added source-derived free-answer self-check within the original cardiology fiche reader. Course hidden during recall; answer draft persists by fiche ID; user reveals original essential points for comparison and can mark `A_REVOIR`. No fake AI grade or automatic mastery proof.
- Expanded Robolectric UI smoke test: from `Étudier` to actual cardiology fiche source text, then switch to recall without showing answer content.

## MedRebuild ↔ Practice source continuity
- Practise from a cardiology lesson now binds the exact original fiche ID and checks that its title remains the user's active topic.
- Generated questions and answer-comparison references are the original recall/essentials from the source, instantly usable offline. This is explicitly NOT automated student grading.
- Returning to the full original fiche works; switching topic clears source match, preventing stale-document attribution. Robolectric smoke covers course→practice→questions.

## OCR/GGUF contention fix
- Existing worker checked inference activity only when the job began; a four-page PDFBox + ML Kit OCR batch could continue consuming RAM and CPU after the user sent a chat message. The PDF worker now rechecks before each individual page and yields with `Result.retry()` if inference takes priority; its already committed SQLite pages and source cache remain intact.
- On cancellation, the worker no longer incorrectly marks a book ERROR; scheduling/resumption remains owned by WorkManager. Deterministic time-boundary tests added. Physical concurrent OCR/Chat benchmark still required.

## Critical medical chat safety / academic context 2026-10-11
- The former `isUrgent()` used `q.contains("hemorragie")` and `q.contains("avc")`: *any course question* about these medical topics bypassed the neuronal/RAG engine with a canned first-aid reply. This explains the user's clinical-learning screenshot.
- New routing distinguishes first-person/personal red flags and current clinical emergencies from explicit academic scenarios; both branches have regression tests. It is a conservative lexical guard, not a triage device. Real symptom presentations still receive immediate help guidance.
