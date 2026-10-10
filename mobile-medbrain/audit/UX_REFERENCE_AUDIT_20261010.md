# MedBrain UX Reference Audit — 2026-10-10
Source projects inspected:
- Excellentia V2.2: excellentia-study-cockpit/v2/public/index.html, style.css, app.js (ChatGPT-PC). Five-position mobile dock, More sheet, contextual tabs, quick search, sync indicators, theme and density.
- Med Rebuild V1.5: med-rebuild-study-hub/v1.5-prototype/public/app.js, views.js, style.css (ChatGPT-PC). Sections Learning, Clinical Practice, Review, Exam, Progress, Settings; nested teaching models, revision debt and evidence of mastery.
- Familiar conversation design: message-first chat, compact header, pinned keyboard-aware composer, durable history, cited evidence behind expandable source details, clear generation states.

Target architecture: Navigation -> conversation/task router -> dialogue or document retrieval -> evidence check -> local model -> response + citations + chat history. Parallel authorized file scanning and medical pedagogy. Keep all existing data on package upgrade.
Audit gates: 1000 scenario routing cases (not 1000 true neural dialogues), Android system bars/keyboard, landscape, unrelated obstetric hits when asked about adult heart, resumable work, backup/signature continuity, no fake Google Drive OAuth, source provenance. Current installed 0.3.3 is retained until an in-place signed update is verified.
UI implementation: compact header; 5 icon dock items (Home, Chat, Library, Learn, More); More opens Diagnostics and Settings; input fixed above dock; minimize raw page dumps; distinguish pages read, indexed, understood, demonstrated mastery.