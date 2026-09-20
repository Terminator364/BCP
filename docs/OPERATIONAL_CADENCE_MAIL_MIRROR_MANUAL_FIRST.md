# BCP OPERATIONAL CADENCE / MIRROR POLICY

Status: CANONICAL
Revision: 2026-09-20-R50

## 1. Work-slice cadence
- Default execution slice: 5 to 6 minutes.
- Each slice must end with a durable checkpoint before continuing.
- A slice should produce concrete evidence: test result, correction, merge, package, artifact, readback, or a clearly identified human gate.
- Do not extend a slice silently because a long job is still running. Checkpoint and continue in the next slice.

## 2. Response/mail mirror
- At the end of each slice, the ChatGPT response and checkpoint email body MUST be textually identical.
- The email subject may be shorter for navigation, but the body must not be summarized, rewritten, or shortened.
- This mirror exists so a slow/reloading ChatGPT UI cannot destroy continuity.

## 3. Manual-first / one-shot field rule
- On the field PC, prefer one manual transfer/install when network retry loops are slower or less reliable.
- Do not use blind retry loops.
- One attempt -> readback -> diagnose exact cause -> correct upstream -> requalify -> one new attempt.
- Every package must be tested in GitHub or equivalent harness before field installation.
- Field-relevant conditions include Windows 11, 4 GB RAM, >90% memory pressure, thermal pressure, intermittent network, DriveFS quirks, reboot, and low-resource operation.

## 4. CURRENT artifact hygiene
- The installation folder is API_BCP/00_INSTALL_CURRENT.
- It MUST contain only currently actionable artifacts.
- Replace stable CURRENT filenames in place whenever possible.
- Temporary upload files must be deleted after replacement.
- Historical artifacts belong in GitHub/releases/archive, not in 00_INSTALL_CURRENT.

## 5. Human gates
- If a true human gate is reached, stop mutation and request one precise action.
- Do not stack several user actions unless technically inseparable.
- After the user action, resume with a new 5–6 minute slice and readback before the next mutation.

## 6. Propagation
- This policy is the reference pattern for the user's other software projects.
- When those projects are next touched, port this policy into their durable project continuity/spec files instead of relying only on chat memory.
