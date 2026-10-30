# BCP Universal Remote — G4 secured Windows agent (staging)

**Status: G4 Windows localhost staging tested, Android/ChatGPT production integration NOT yet complete.**
Date: 2026-10-30. Baseline Android v1.1.1 / G2 field validated and preserved.

## Implemented
- TLS 1.2+ on **127.0.0.1:8910 only**. No public binding, no Tailscale Serve exposure, no Funnel.
- Existing BCP HMAC-SHA256 paired secret, nonce replay protection, bounded payloads and SQLite audit.
- Read-only: Windows system inventory, process listing, browse and UTF-8 text read using
  authorized absolute Windows paths (not restricted to demo folder). Protected private
  state, credential paths and large files are explicitly denied.
- Potential mutations: write_text, mkdir, run (preexisting Windows executable
  with explicit bounded argument array). Every change requires a 5-minute, single-use
  approved ticket shown on **local Windows Approval Center**.
- The user's local approval seals ticket ID, expiry and exact operation specification
  with an HMAC over a Windows-local private 32-byte key. It cannot be granted by
  merely sending approved:true or editing ticket status. Mutations have backup
  and change-detection protections where applicable.
- Runs as normal Windows user. Does not silently elevate via UAC or bypass security.
- Windows approval app: g4_approval_center.py (Tkinter) and optional Desktop shortcut
  BCP G4 - Autoriser mes operations.cmd. No automatic approvals or invisible clicks.

## Verified on MBMPC
- Python direct security bench **17/17 PASS**: sensitive-path and relative-path rejection,
  auth-spec forgery, replay, unapproved changes, file race, audit and safe lab write.
- Additional bench **13/13 PASS**: approved command whoami.exe, mkdir, original-file
  backup, expired ticket, altered signed specification and denied dangerous paths.
- Network TLS/HMAC test **8/8 PASS**: authenticated system/process/list endpoints,
  invalid HMAC denied, private key read denied, change request without approval denied.
- Total **38/38** passing. Positive mutation approvals in these benches are
  **synthetic lab simulations**; no physical Windows GUI click/approval field-proof yet.

## Boundaries and next gates
1. Validate actual Windows user clicking Approve/Reject on a harmless operation.
2. Ensure no commands or files exposed through G2 before per-device permission policy.
3. Integrate G4 endpoint safely with existing single Windows agent to avoid
   extra permanent RAM use; stop separate staging server afterward.
4. Add Android G4 operations to signed APK updater only when Windows endpoint is ready.
5. Build genuine ChatGPT integration through an action-capable authenticated connector,
   not by assuming Android app gives ChatGPT native PC permission.

## User policy
Preserve v1.1.1 Android, successful Wi-Fi/Tailscale pairing and signed updates.
No automatic cellular-data ban. Never commit certificates, approval HMAC keys,
pairing secrets or Windows local state to GitHub.
