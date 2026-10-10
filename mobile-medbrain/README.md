# MedBrain 0.3 — correction terrain S21 FE (2026-10-10)

Field issues from screenshots: navigation obscured by Android 16 bottom system bar, landscape cut-off, folder selection restrictions, arbitrary 500-file cap, white/black view on GGUF selection. All are now tracked and separately addressed.

## Changes
- Android WindowInsets safe areas (status/navigation bars and display cutout), always accessible top navigation in portrait (3+2) / landscape (5 in one row); restored tab after rotation.
- PDF/text import remains via Android SAF; **Google Drive root/whole-account sync NOT implemented**. Android may forbid selected roots; proper OAuth Google Drive integration is a separate identity and permissions gate. Never claim otherwise.
- Durable SQLite 3 folder walk queue via Android DocumentsContract, unlimited number of eligible files over successive bounded worker runs. Error events and pending-node count visible.
- GGUF picker entry/return/errors recorded; ModelVault.import reports bounded progress without loading model into the UI process; storage preflight and rollback remain.
- Local Java crash receipts persisted and available in Diagnostic export (not native crash dump and not private Google Drive provider logs).
- Tests: existing evidence/migrations/study/navigation plus folder >500, v2->v3 migration, top-accessible tabs.

## Security, identity and signing
- Never force uninstall of a version with user data. Existing 0.2 APK is signed with an ephemeral GitHub Actions debug key. A 0.3 APK built on a new runner has **different signing identity** and cannot update 0.2 in-place; a real stable release keystore must be securely provisioned first. Never store private signing key in git. Do not guarantee installation over existing app.
- User's old Alpha 0.1 had 85/86 pages; deleting the app may already have removed the old private SQLite DB. Do not claim 0.3 restores it unless an external backup is verified.
- Physical testing and full second-Google-account Drive OAuth still pending. CI tests are not field-device certification.

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
