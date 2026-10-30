# BCP Universal Remote — urgent rescue checkpoint, 2026-10-30

Resume code: `BCP|UNIVERSAL|SYNC|MASTER`.
Repo `Terminator364/BCP`, branch `feat/universal-remote-transport-20261030`.

## Verified in this turn
- User complained about too many buttons, ephemeral/closing windows, opaque `IllegalState`, too many phone taps and poor ergonomics. Do NOT ask the user to repeat these.
- **One desktop launcher installed on MBMPC**: `Desktop\BCP - OUVRIR.lnk`, and autostart `Startup\BCP - Centre de contrôle.lnk`. Previous FIVE BCP desktop shortcuts were archived reversibly in `Desktop\_Projets et outils\BCP - anciens raccourcis`, without deleting personal files. Installer output `BCP_SINGLE_LAUNCHER_INSTALLED`, `BCP_OLD_SHORTCUTS_ARCHIVED=5`, exit code 0; backup `%LOCALAPPDATA%\BCP-Universal-Remote\backups\ONE_BUTTON_20261030_234048`.
- `bcp_control_center.pyw` new Windows GUI built and Python syntax validated by successful installer. A Windows `pythonw.exe` PID 11328 for this file was observed. Full visual proof on interactive desktop NOT confirmed. Source subsequently improved to minimize instead of disappear on X, reuse singleton device registry to prevent expensive ACL/SQLite initialization every five seconds, and prefer fast G2 starter. A source-file refresh to the installed root is currently pending due Remote Desktop Commander overload; verify before claiming installed.
- `g4_device_identity.py` updated to make same-device pending enrollment idempotent (same code, unchanged expiration), support already-enrolled same device, reject mismatched credential, expose local-only challenge comparison to Windows UI. **34/34 actual MBMPC tests PASS** (also owner inventory 17, files 16, RPC13, E2E TLS30). New backend deployment `g4_individual_safe_deploy.ps1 -Apply` hung during restart and its process was terminated; unlike previous deployments, success was NOT confirmed.
- Android improved: readable server HTTP reason instead of opaque `IllegalState`; automatic pending enrollment & polling, owner code on Home, simplified Files UI and old 30min/20ops controls collapsed, existing update channel preserved. Candidate v1.5.0 `versionCode=19`, GitHub Actions Android full APK build `41140142876` SUCCESS.
- The candidate was signed locally on MBMPC using the original R3.3 keystore: `G2_RELEASE_SIGNED=PASS`, size 78583 bytes, SHA256 `d66725f11ebdd86b96b86d6f57834d86c82fe8bcb131d5c8bfd2377d555263bf`; report `%LOCALAPPDATA%\BCP-Universal-Remote\G2-v150-build\G2_SIGNED_RELEASE_REPORT.json`. Signed stable publication script `publish_v150_safe.py` staged locally but **NOT RUN**, because G2 is DOWN. Stable manifest remains **v1.4 code18**.
- A real TCP connect probe to `127.0.0.1:8898` output **`G2_8898_LISTENER=False`** after the hung restart. Earlier root service was working. This is the active high-priority incident. Do not claim the connection works until re-probed.
- Existing `g2_autostart.ps1` was read: it calls slow `Get-NetTCPConnection`, `Get-NetIPAddress`, `tailscale ip`, likely contributing to stalls on this 4GB PC. A new Python `g2_autostart_fast.py` with bounded socket checks and valid private binding selection was authored in GitHub. An earlier copy was written to root and attempted to run, but process did not return a confirmed success or journal.
- Windows recovery directly through Remote Desktop Commander is heavily delayed: two newest write_file calls updating installed `bcp_control_center.pyw` and `g2_autostart_fast.py` are **executing/pending**, call IDs:
  `d2800fca-b4d8-423d-9c33-1e66cc76c446`
  `42737fc0-62ca-46c3-b760-6d64ae47a59a`.
  Do not reissue duplicate writes until their result status is known. `list_processes` failed timed out. Several PowerShell / fast launch sessions hung. Attempted targeted force_terminate of old autostart session `18160`, result not confirmed.
- New `scripts/install_g2_fast_autostart.ps1` staged in repo, backs up old PowerShell autostart and replaces it with a simple invocation of fast Python. NOT installed on PC; avoid claiming otherwise.
- New `windows/g2_autostart_fast.py` updated to allow only loopback/RFC1918/Tailscale 100.64/10 (not 0.0.0.0) and to skip ipconfig when previous Wi-Fi address remains valid. The root copy may be older until pending write finishes; verify.
- Fast startup Windows CI workflow `.github/workflows/bcp-g2-fast-recovery.yml` created; results not yet verified.

## Immediate priority next
1. Recover remote agent throughput; check the two pending write_file results via `mcp__Remote_Desktop_Commander__get_tool_result` (do not retry same call).
2. Confirm the installed `g2_autostart_fast.py` source is latest, compile it, and launch once with bounded checks. Recheck local port 8898 and signed G2 status + Tailscale.
3. Backup/install fast PowerShell wrapper if service can be accessed, preventing recurrence; update GUI root with current optimized source.
4. Re-run 16/16 G4 production negative gate and 12/12 owner-file negative gate. Confirm idempotent enrollment on LIVE G2 after root module deployment (unit tests alone insufficient).
5. Only AFTER backend health PASS, run `publish_v150_safe.py` with verified signed APK code19 and backup stable18; verify private Tailscale served sha256, then real Samsung installed version telemetry 19. Do not silently bypass Android package-installer OS approval.
6. Validate actual desktop UI window (not just pythonw process), one icon remains, no repeated prompts.
7. Follow user's autonomy intent: if lane blocked, switch to independent safe work, but NEVER leave broken G2 unreported.

## Security and honesty
- No auto owner approval, public port, UAC bypass. One affirmative local owner consent is necessary; no manual code typing should be required once the code appears on both devices.
- Remote Desktop Commander quota already 85–86% used; minimize waste.
- Work completed via GitHub is not necessarily installed on PC.
