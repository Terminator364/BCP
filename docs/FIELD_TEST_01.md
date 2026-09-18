# FIELD TEST 01 — restart/resume continuity

## Required evidence

1. Run `windows/BCP_PC_BOOTSTRAP.cmd` on the target Windows PC.
2. Install the CI-built BCP Edge APK on the old Android phone.
3. Keep both devices on the same trusted LAN.
4. Enter the server URL + bearer token shown by the PC bootstrap.
5. Project: `buildhub-test`.
6. `Tester /health` must return HTTP 200.
7. Commit:
   - last completed: `checkpoint before interruption`
   - next action: `resume after restart`
8. Record returned revision and event hash.
9. Stop the PC node.
10. Restart the bootstrap/server.
11. Tap `Reprendre le projet`.

PASS only if the same committed revision / event hash and next action are recovered.

Current status before this field test: `CI_PASS / FIELD_UNVERIFIED`.
