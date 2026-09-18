# BCP — Zero-Touch Setup Requirement

Status: REQUIRED / NEXT UPDATE

Observed during FIELD TEST 01 (2026-09-18): manual entry of PC IP, bearer token and project name on the old Android phone creates unnecessary friction and error risk.

## Product requirement

Normal operation must not require the user to manually type or copy:
- PC IPv4 address;
- TCP port;
- bearer token;
- project identifier;
- recurring connection settings after first pairing.

## Target UX

### First pairing
1. PC node starts.
2. BCP Edge discovers the PC automatically on the trusted LAN.
3. User confirms the discovered PC once.
4. Pairing provisions credentials automatically.
5. Pairing state is persisted on both sides.

Preferred pairing channels, in order:
- LAN discovery + short confirmation code;
- QR code shown on PC and scanned by phone;
- manual IP/token only as a diagnostic fallback.

### Subsequent launches
- BCP Edge reconnects automatically to the last paired PC.
- If the PC IP changes, discovery repairs the endpoint automatically.
- Token rotation is transparent to the user.
- Project selection is recovered from BCP state; no repeated typing.
- Health check and reconnect retry run automatically.

## Update requirements
- Preserve paired state across app updates and phone/PC restarts.
- Provide one-tap re-pair/reset.
- Never expose long-lived secrets in screenshots/logs/UI by default.
- Keep LAN scope restricted to trusted/private networks.
- Manual fields remain available only under an Advanced/Diagnostics section.

## Acceptance criteria
FIELD_SETUP_ZERO_TOUCH is PASS only when a fresh install can reach a paired, working state with at most one explicit user confirmation and no manual IP/token entry.
