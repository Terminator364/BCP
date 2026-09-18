BCP FINAL BOOTSTRAP 0.3
=======================

This replaces all earlier BCP PC bootstrap/repair/evergreen files.

Architecture:
- Reuses the existing ChatGPT-PC runtime at %LOCALAPPDATA%\Tunnel_PC_G4.
- Installs BCP as a ChatGPT-PC managed app under %LOCALAPPDATA%\ChatGPT_ManagedApps\bcp.
- Does NOT install system Python.
- Does NOT create a Windows Scheduled Task.
- Does NOT require manual IP/token/project entry.
- Creates only a Private/Domain LocalSubnet firewall rule for TCP 8765.
- Registers the app in ChatGPT-PC and writes machine-readable receipts.

Usage:
1. Extract this ZIP completely.
2. Double-click INSTALL_BCP_FINAL.cmd.
3. Accept the Windows UAC prompt once.
4. Wait for BCP INSTALLATION = PASS.
5. Reopen the already-installed BCP Edge app on the old phone.

Do not use any older BCP PC installer after this package.
