# BCP — Telegram Bot Setup and Kinshasa Field Gate

Status: IMPLEMENTATION GUIDE — Telegram Observability MVP
Budget invariant: 0 USD
Mode: READ_ONLY
Target: Kinshasa, Democratic Republic of the Congo

## What is already automated

The repository contains two deployment files:

- bcp_telegram_observability.py — standard-library, low-RAM read-only cockpit.
- CONFIGURE_BCP_TELEGRAM.ps1 — local secret/bootstrap configurator.

The configurator performs the following automatically after the human BotFather step:

1. validates the token against the official Telegram Bot API using getMe;
2. refuses to silently replace an existing webhook;
3. stores the token only under the local BCP state directory;
4. restricts the local token file ACL to the current Windows user;
5. waits for one private Telegram message and detects the chat ID automatically;
6. asks the user to approve that detected private identity locally;
7. writes only the non-secret allowlist/configuration state;
8. runs the bot self-test;
9. installs a per-user startup entry;
10. starts the lightweight worker and sends a confirmation message;
11. writes a sanitized local setup receipt without the token.

No Telegram token, full prompt, model/API key, bearer token, or private chat payload belongs in GitHub, Drive, the project specification, Telegram status output, or ChatGPT.

## Irreducible human step A — create the bot

Use the official Telegram account @BotFather.

1. Open Telegram and open @BotFather.
2. Send /newbot.
3. Choose a display name, for example BCP Cockpit.
4. Choose a unique username ending in bot, for example BlessingBCPCockpitBot.
5. BotFather returns a bot token.

Treat that token like a password. Do not paste it into ChatGPT, GitHub, Drive, an issue, a PR, source code, or a screenshot.

If the token is ever exposed, use BotFather to revoke/rotate it before continuing.

## Irreducible human step B — local secret bootstrap on Windows

Extract the qualified BCP Telegram package on the target PC.

Run:

    powershell -NoProfile -ExecutionPolicy Bypass -File .\CONFIGURE_BCP_TELEGRAM.ps1

The script asks for the BotFather token using a local secure prompt. The token is used only by the local setup/runtime.

After getMe succeeds, the script prints the bot username. On the Android phone:

1. open that bot;
2. press Start;
3. send /status.

The PC detects the private chat automatically. Verify the displayed Telegram identity on the PC and type YES locally to authorize it.

No chat ID copy/paste is required.

## Field gate

Documentation and current Bot API behavior are not sufficient to claim Kinshasa field availability.

The field gate is PASS only when the real user account and normal Kinshasa network, without VPN/proxy/false country, complete all of:

- official Bot API getMe succeeds;
- getUpdates receives the user's private /status;
- the local BCP bot sends a reply through sendMessage;
- /status returns an evidence-based snapshot;
- /ci returns GitHub CI truth or an explicit NOT_OBSERVED;
- /holds returns durable holds or explicitly reports none observed;
- token remains local and absent from Git/Drive/log output;
- paid spend remains exactly 0.00 USD.

Before that live smoke test the correct state is:

DOC_OK / ZERO_USD_OK / KINSHASA_FIELD_SMOKE_PENDING

After success:

KINSHASA_SMOKE_PASS / READ_ONLY_FIELD_ACTIVE

## Runtime behavior

The worker uses Telegram long polling with a server-held request timeout of about 50 seconds. This is intentionally not an aggressive short polling loop.

Network failures use bounded backoff. GitHub public state is cached briefly and stale cache may be shown if the network drops. The canonical BCP state remains local/durable; Telegram is only a cockpit.

The initial command surface is deliberately read-only:

- /status
- /project <id>
- /job <code>
- /last
- /ci
- /holds

Unknown/mutating commands are refused in MVP-0.

## ChatGPT visibility contract

Telegram may show only externally observable ChatGPT-related truth:

- OBSERVED_CHAT_ACTION
- CHAT_WAITING
- CHAT_PLATFORM_HOLD_REPORTED
- UNKNOWN_INTERNAL_CHAT_STATE

The bot never claims access to private chain-of-thought, hidden model work, or OpenAI verification internals.

When no supported telemetry exists, UNKNOWN_INTERNAL_CHAT_STATE is the correct result.

## Disable without deleting the secret

To disable automatic startup while preserving local configuration for recovery:

    powershell -NoProfile -ExecutionPolicy Bypass -File .\CONFIGURE_BCP_TELEGRAM.ps1 -Disable

The user may then rotate/revoke the BotFather token separately if desired.

## Next implementation stages

MVP-0 is read-only observability.

Future stages remain separately gated:

- MVP-1: durable Mission Event Journal integration;
- MVP-2: French mission intake -> MISSION_ENVELOPE -> explicit action selection;
- MVP-3: short mission locator such as 48273195 and BCPGO 48273195;
- MVP-4: Model Broker using only field-qualified zero-cost providers.

No later stage may weaken the writer fence, idempotency, secret handling, zero-dollar invariant, or evidence rules established by MVP-0.
