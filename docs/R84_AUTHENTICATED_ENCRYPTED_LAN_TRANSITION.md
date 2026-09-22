# R84 — Authenticated + encrypted LAN transition

## Scope

R84 deliberately implements one provable security frontier rather than relabeling the whole LAN as secure.

### B-EDGE ingress

- TCP 8877: HTTPS API only.
- Persistent RSA private key: AndroidKeyStore alias `bcp-edge-tls-v1`.
- TLS protocol floor: TLS 1.2, with TLS 1.3 preferred when available.
- Peer trust model: paired SHA-256 certificate pin.
- Private API bearer is transmitted only after the PC verifies the TLS peer pin.

### Telegram CONNECT relay

- TCP 8876: CONNECT only.
- Target allowlist remains exactly `api.telegram.org:443`.
- Telegram payload remains provider end-to-end TLS.
- 2.2 proxy authentication: HMAC-SHA256 over CONNECT target, timestamp and random nonce.
- Timestamp skew is bounded to 120 seconds and nonces are replay-checked in-memory.
- The paired long-lived bearer is not sent in the clear CONNECT header for 2.2.

### Compatibility

BCP PC continues accepting legacy 2.1.2 relay registration as an explicitly insecure compatibility state. A 2.2 secure registration is accepted only with HTTPS, port 8877, a 64-hex certificate SHA-256 fingerprint and HMAC relay authentication.

## Truth boundary

This slice does **not** yet encrypt B-EDGE -> PC control traffic on port 8765. Therefore:

- `PC -> B-EDGE private API`: encrypted + pinned.
- `PC -> Telegram through B-EDGE`: Telegram payload encrypted end-to-end; relay credential protected with HMAC.
- `B-EDGE -> PC control API`: authenticated but payload still clear HTTP.
- Overall status: `PARTIAL`.
- Release blocker remains: `AUTHENTICATED_ENCRYPTED_LAN_BIDIRECTIONAL`.

No B-EDGE 2.2 field installation is authorized by this document.
