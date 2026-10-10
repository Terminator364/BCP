# Blessing MedBrain — Android 0.2.0 candidate

Medical learning assistant, user-controlled, on-device and zero-PC operation.

## Architecture
- Native Android app with five nonempty functional workspaces.
- SQLite v2 migrates alpha v1 without dropping books, adds FTS4 search, provenance, review ledger, and recent events.
- PDF text extraction and Latin OCR fallback for image-only pages (ML Kit bundled offline); image imports recognize text but do NOT imply comprehension of all diagrams.
- Persistent WorkManager batches and automatic resumption after process death; optional local-folder discovery through Android SAF.
- Optional Qwen3-1.7B GGUF local inference in **separate :inference process** (llama.cpp Android wrapper). The main app never needs to load model weights.
- Atomic model vault import with SHA-256, storage reserve, old-model rollback, no GGUF distributed with APK.
- Grounded FTS4 retrieval with title/page provenance, study materials, response correction, manual review records, diagnostics and user-directed text export.
- No network permission or credentials. An individual file can be chosen from Google Drive's document provider; a whole remote Drive account is NOT synchronized through this API.

## Honesty gates
- CI success demonstrates compilation, lint, and simulated JVM/Robolectric tests only.
- Physical Galaxy S21 FE RAM/thermal/reboot and source-provider behavior are not certified without real device evidence.
- OCR of text is not interpretation of charts/anatomical images.
- RAG is not continuous training of neural weights. Knowledge growth is queryable corpus + verified retrieval; LoRA fine-tuning remains research.
- No clinical diagnosis, patient decision support or medical practice use.
- No auto-delete and no broad media access.
- BCP orchestration authority remains canonical. No shadow broker and no replacement of B-EDGE.

## Proof
Workflow: .github/workflows/medbrain-android.yml
Unit tests: SQLite/FTS, academic provenance, five UI pages.
Release candidate APK is published only on PASS, with SHA256 receipt. No merge or stable-label before phone qualification.

## Desired future expansion
- OAuth read-only Drive folder sync for the second Google account with user consent and incremental changes API.
- True medical multimodal image model and diagram caption validation, semantic embeddings, relationship graph and robust exam benchmarking.
- Signed release update channel and mobile field test suite, integrated with BCP contracts.
