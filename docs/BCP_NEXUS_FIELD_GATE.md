# BCP Nexus — Deployment and Field Gate

Status: IMPLEMENTATION CANDIDATE
Date: 2026-09-19

## Purpose

BCP Nexus removes direct PC-to-Telegram reachability from the critical path.

Target field path:

Telegram -> HTTPS webhook -> BCP Nexus
PC/B-EDGE -> HTTPS BCP Nexus
PC <-> B-EDGE -> authenticated home LAN

The PC and dedicated B-EDGE old phone both remain on the home Wi-Fi. The user's current phone is only the human Telegram client and is never a required relay.

## Implemented MVP

Repository components:
- `nexus/cloudflare-worker/src/worker.mjs`
- `nexus/cloudflare-worker/migrations/0001_init.sql`
- `nexus/cloudflare-worker/wrangler.toml.example`
- `windows/bcp_telegram_observability.py` transport mode `NEXUS`
- `windows/CONFIGURE_BCP_NEXUS.ps1`
- `windows/BOOTSTRAP_BCP_NEXUS.ps1` — one-time deployment/bootstrap helper that reuses the already-local Telegram token/chat authorization, generates Nexus secrets locally, provisions them directly to the provider, migrates receiver ownership to webhook mode, configures the local worker and writes a machine-readable receipt.

Nexus routes:
- `GET /health`
- `POST /telegram/webhook`
- `GET /v1/device/commands`
- `POST /v1/device/reply`
- `POST /v1/device/push`

Security:
- Telegram webhook header secret is mandatory.
- Telegram private chat ID is allowlisted.
- Device HTTPS requests require bearer token + device ID.
- Bot token, webhook secret and device token are deployment secrets and are never committed.
- Command/reply/push effects are idempotency-keyed.
- Large artifacts are forbidden from this relay by contract.

## Receiver ownership

Telegram long polling and webhooks are mutually exclusive receiver modes.

Migration sequence:
1. deploy and health-check Nexus;
2. create D1 schema;
3. configure secrets;
4. set Telegram webhook with secret token;
5. stop direct `getUpdates` worker ownership;
6. configure local BCP worker to `NEXUS`;
7. verify /status round trip;
8. verify duplicate command/reply rejection;
9. verify Nexus outage -> local retry/outbox behavior;
10. only then promote Nexus as steady state.

Rollback:
1. set local transport back to `DIRECT_TELEGRAM`;
2. delete Telegram webhook;
3. start exactly one direct long-poll worker.

Never run webhook receiver and direct `getUpdates` ownership simultaneously.

## Zero-cost gate

The first implementation target is Cloudflare Workers + D1 because it can fit the expected tiny control-plane traffic on a free plan. Free-tier limits are external provider constraints and MUST be re-read and field-checked before deployment. BCP never silently upgrades to a paid plan.

## True human gate

Code/CI can prepare the relay without user action. Live deployment needs authorization to an external cloud account and creation of provider secrets.

Do not ask the user to paste the Telegram bot token into ChatGPT.

Preferred bootstrap:
- authenticate the deployment tool to the chosen provider on the user's PC;
- the deployment helper reads the already-local Telegram token/chat configuration;
- generate webhook/device secrets locally;
- upload secrets directly to the provider over TLS;
- write the same device secret into BCP local state;
- never expose the values in logs, GitHub, Drive or chat.

## One-time zero-touch bootstrap contract

The preferred live-deployment path is now a single bounded bootstrap action, not a sequence of manual token/file transfers.

`windows/BOOTSTRAP_BCP_NEXUS.ps1` MUST:
- reuse the already-authorized local Telegram token and private chat identity; never ask the user to paste them into ChatGPT, GitHub or Drive;
- use the provider's authenticated CLI session as the only unavoidable cloud-account gate;
- create or reuse the D1 database;
- generate webhook/device secrets locally with a cryptographic RNG;
- send provider secrets directly over TLS and never print them;
- deploy and health-check the Nexus worker;
- stop the direct long-poll receiver before setting the webhook;
- configure the local BCP worker in NEXUS mode and restart it;
- emit one Telegram bootstrap confirmation through Nexus;
- persist a local receipt with URL/version/state but no secrets;
- roll receiver ownership back toward DIRECT_TELEGRAM if migration fails after webhook activation.

A missing Cloudflare/Wrangler login is a true human gate. It is not a reason to ask for the Telegram token again.

The helper is idempotent at the resource/configuration level: rerunning it may refresh generated secrets and deployment state, but it MUST NOT create competing Telegram receivers or duplicate canonical BCP state.

## Field acceptance

PASS requires:
- Nexus /health reachable from PC while PC stays on home Wi-Fi;
- Telegram webhook reports no delivery error;
- /status reaches Nexus, then BCP, then returns to Telegram;
- direct PC->Telegram can remain unavailable without breaking the cockpit;
- duplicate webhook update produces one command;
- duplicate BCP reply produces one Telegram send;
- temporary Nexus outage does not corrupt command cursor/canonical BCP state;
- no mobile hotspot/tether is required;
- spend remains $0.00;
- no secrets appear in repository, Drive artifacts or logs.

Until these pass, status is IMPLEMENTED_CI_QUALIFIED / FIELD_UNVERIFIED.
