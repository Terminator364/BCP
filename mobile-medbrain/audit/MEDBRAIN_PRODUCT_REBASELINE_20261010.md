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
