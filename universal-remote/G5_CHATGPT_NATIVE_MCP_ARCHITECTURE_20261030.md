# BCP Universal Remote — G5 Native ChatGPT MCP integration, evidence-based design

Date: 2026-10-30. Continuity: `BCP|UNIVERSAL|SYNC|MASTER`.
This is a **design and implementation gate**, not a claim that a ChatGPT-native BCP plugin is installed.

## Verified external constraints

1. OpenAI supports connecting remote MCP servers and private/on-premises servers through **Secure MCP Tunnel** without exposing the local server publicly: https://developers.openai.com/api/docs/guides/tools-connectors-mcp
2. In the current ChatGPT Plugins experience, a custom MCP plugin may use an HTTPS endpoint or a **Tunnel** connection, subject to the account/workspace permission: https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt
3. Full read/write MCP plugin access has plan/workspace restrictions. As of this checkpoint the Help Center specifies Business and Enterprise/Edu for full MCP; do not assume that an individual Plus account can install a full write connector. Check the actual UI/permissions before promising it.
4. API-driven MCP via Responses supports `tunnel_id`, but API billing is separate from an ordinary ChatGPT subscription. The user's budget is zero preferred, $5–10 tolerated only if expressly authorized. **Do not create API charges automatically.**
5. Existing Remote Desktop Commander is already connected and can execute approved Windows actions in this conversation. It is the working contingency until G5-native access is actually connected.

## Architecture: PC never exposed through a public Funnel

`ChatGPT plugin → Secure MCP Tunnel (if account supports it) → BCP MCP broker bound to 127.0.0.1 → individual ChatGPT client trust + scope + idempotency ledger → G4 owner capability engine under Windows ACL/UAC`

Do not reuse the existing phone's G2 shared pairing key as a ChatGPT owner identity. Create a **separate cryptographic client registration**, locally approved on Windows, revocable without affecting the Samsung. The tunnel is a transport, not authorization.

### Tool contract (future)

| Tool | Capability | Side effect | Consent |
|---|---|---|---|
| bcp_status | status | none | approved connection |
| bcp_drives | system.volumes | none | owner read grant |
| bcp_files_list | files.list | none | owner read grant |
| bcp_files_read_chunk | files.read_chunk | none | owner read grant |
| bcp_upload_begin/append/commit/status/abort | G4 owner files | write | device-local owner write grant, overwrite requires expected old SHA |
| bcp_jobs_enqueue/status/cancel/output | durable jobs | execute | explicit owner commands grant and local sensitive-action policy |
| bcp_processes | processes.list | none | owner process grant |
| bcp_desktop_windows | desktop.windows | none | owner desktop grant |

No automatic admin privilege elevation, UAC bypass, access to BCP signing keys, or unlogged destructive operations.

### Required implementation gates

- G5.0: verify user's real ChatGPT account has custom MCP write-capable connection; if not, use the connected Remote Desktop Commander and preserve readiness for a later plan change.
- G5.1: build a minimal read-only BCP MCP server bound exclusively to `127.0.0.1`; integration tests verify initialization, tool enumeration, authorization failure, and bounded memory.
- G5.2: separate Windows-local approval for the ChatGPT MCP client, **never** automatic trust from a tunnel ID.
- G5.3: integrate G5 idempotency ledger (already 21/21 local test PASS) before any write-capable tool: permanent unique request IDs, duplicate detection, interrupted jobs marked for reconciliation; do not replay blindly.
- G5.4: integrate owner-scoped streamed files, then durable jobs, then desktop/service operations; test each with a synthetic locally approved owner in a TEMP folder.
- G5.5: connect through Secure MCP Tunnel with proper OAuth 2.1 where needed; check account eligibility and actual plugin installation. Never publish BCP as an open public HTTP endpoint.
- G5.6: real ChatGPT tool-call positive test for benign read and temp-file write, after user authorization. Distinguish LAB, INSTALLED CONNECTOR, and PRODUCTION E2E.

## Active boundary

As of this document: G4.1 individual phone owner API in production, owner file route with default deny; signed Android v1.4 available but real installation and owner enrollment still not independently confirmed. G5 native connector is **NOT IMPLEMENTED**; standard connected Remote Desktop Commander provides working access today.
