# BCP Universal Remote — G4 real Windows approval field gate (30 Oct 2026)

## Baseline
- MBMPC online; G2 TLS 8898 preserved for current Samsung v1.1.1, no Android APK rebuilt in this step.
- Earlier G4 simulated tests 17/17 + 13/13 + TLS integration 10/10 passed. Those were **not** real human approval.
- G4 command/file mutations are NOT exposed through the active remote G2 API. G4 staging actions require Windows-local approval and a sealed 5-minute ticket.

## Work performed
- Improved local-only `g4_approval_center.py` to execute an exactly specified approved ticket directly via `G4Bridge.commit` after the signed-in user clicks "Approuver et exécuter" and confirms the Windows dialog. Tickets denied without local approval stay unexecuted. No UAC bypass or change of OS privilege.
- On MBMPC created test setup `g4_prepare_real_approval.py`: prepares one harmless `write_text` ticket for `G4-Staging-Workspace/G4_FIELD_APPROVAL_PROOF_20261030.txt`; verifies `commit` is denied before local approval and file remains absent.
- Created reusable `g4_field_approval_launcher.py`, which creates a fresh ticket if expired and launches the Windows-local approval window. If proof already exists, it reports completion instead of overwriting it.
- Created verified desktop shortcut `BCP G4 - Autoriser une action.lnk` targeting `pythonw.exe` and the one-click launcher. This runs in the signed-in Windows account.
- Validated Python syntax, reran G4 core 17/17 PASS. Ticket entered `PENDING` with no file mutation; local GUI pythonw process started in Windows session 1.
- **Do not claim real human approval or execution until `pending/<ticket>.json` shows DONE and proof file exists.** At audit point status was PENDING, no proof file.

## Next field step (requires human confirmation)
1. On MBMPC desktop, double-click `BCP G4 - Autoriser une action` if approval window is not visible.
2. Read the exact target and text displayed, press `Approuver et exécuter`, confirm.
3. Inspect `state/g4_field_approval_ticket.json` ticket and proof file; verify `DONE`, expected exact content, and audit row.
4. Only then continue G4 network-access mutation architecture with per-action consent, deny by default and comprehensive QA; user explicitly requires no routine manual JSON imports.

## Unchanged boundaries
No general remote shell exposed via Tailscale. No silent admin elevation. G2 actual paired Samsung and adaptive updater remain operational; no per-update APK delivery for backend changes.
