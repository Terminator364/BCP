# Telegram Rich Cockpit V10 — R21

Status: IMPLEMENTED CANDIDATE / FIELD UNVERIFIED
Date: 2026-09-20
Basis: Telegram Bot API 10.3 (Rich Messages and styled RichMessageButton), with V9 plain-message fallback retained.

## Goal

V10 upgrades the V9 Human Ops cockpit into a structured Telegram-native surface without introducing a web UI dependency.

The rich surface is an enhancement, not a critical transport. Every V10 operation MUST be able to fall back to the V9 plain-text + InlineKeyboard implementation when:
- the Telegram Bot API rejects a Rich Message;
- an older/self-hosted Bot API lacks the method;
- editing a prior message as rich content fails;
- Nexus is temporarily running an older worker;
- a client-side rendering difference makes the richer surface unavailable.

## Rich live card

The preferred live card uses Bot API Rich Messages with:
- a human attention heading;
- a compact table for objective, approximate progress, confidence, proof age and human gate;
- an explicit current action and next action;
- a collapsible "Pourquoi ?" block;
- a collapsible devices/network/evidence block;
- callback buttons embedded in the rich content.

No operational secret is included in rich markup.

## Styled button semantics

Telegram Bot API 10.3 exposes semantic styles. BCP uses them conservatively:
- `success`: healthy/current-state confirmation and safe continue/navigation where appropriate;
- `primary`: navigation, inspection, explanations and predictive views;
- `danger`: only when the current observable state is CRITICAL or requires genuine human action;
- `link`: informational navigation when needed.

Styles are semantic hints; Telegram clients may render theme-specific colors. BCP MUST NOT rely on an exact RGB color for meaning.

## Fallback contract

Direct Telegram:
1. try `sendRichMessage` / `editMessageText.rich_message`;
2. if the call fails, log only the sanitized failure class/detail;
3. immediately fall back to V9 `sendMessage` / text edit + InlineKeyboard;
4. do not require user action.

Nexus:
1. PC sends both a plain V9 text representation and optional `rich_html`;
2. Nexus first tries the rich Telegram call;
3. if it fails, Nexus sends/edits the plain V9 card with the normal keyboard;
4. the D1 card fingerprint includes both plain and rich representations so the fallback cannot silently present stale content.

## Transport parity

The same human controls MUST work through DIRECT_TELEGRAM and NEXUS:
- Situation;
- Depuis ma visite;
- Pourquoi ?;
- Radar;
- Étape;
- Activité fine;
- Objectif;
- Continuer;
- quiet/normal notification mode;
- Technique.

The four report buttons MUST also be available through both paths:
1. Situation humaine;
2. Appareils/réseau/transports;
3. Mission/micro-actions;
4. Audit technique.

Nexus report cache accepts the four current reports while remaining backwards compatible with older clients that only send summary + technical.

## Low-data / low-resource constraints

- Rich HTML is bounded below Telegram's 32768-byte content limit; implementation target is <= 30000 characters after sanitization.
- No media is included in the default live card.
- The normal update path edits one card instead of producing a message stream.
- Fallback uses the already-existing V9 implementation, so no extra runtime dependency is introduced.
- No local browser/WebView is added to the 4 GB PC.
- `allow_paid_broadcast` is never enabled; DEFAULT_PAID_SPEND remains 0 USD.

## Truth boundary

Rich formatting changes presentation only.
- Approximate progress remains marked ≈.
- Forecast confidence remains separate from proof.
- Radar remains predictive, not evidentiary.
- Rich Message drafts, if later used, MUST be treated as transient UX only and never as durable evidence of task execution.
- Hidden model reasoning is never displayed or inferred.

## Future-safe use of drafts

Telegram 10.3 supports `sendRichMessageDraft`, including stop controls. BCP MAY later use a short-lived draft for visibly long human-triggered rendering/generation operations.

If implemented:
- draft state is never canonical;
- it must terminate in a persistent final message;
- a missing/expired draft is not an error condition;
- no fake "thinking" or hidden model state may be represented;
- it must not increase heartbeat traffic.

## Security

- Rich markup is built from escaped/redacted observable values.
- Callback data remains short and allowlisted.
- The webhook secret, bot token and Nexus device token remain outside message content.
- Rich Message API errors are sanitized before logging.
- No external HTML/script execution is introduced.

## Field acceptance

V10 is FIELD_VERIFIED only after:
1. exact-head CI passes on Windows and Ubuntu;
2. rich HTML self-test validates tables, details, styled callback buttons and fallback markers;
3. Nexus Worker syntax/security contracts pass;
4. direct Telegram sends/edits one real Rich Message;
5. at least one forced rich-call failure proves V9 fallback;
6. Nexus sends/edits the same rich card after Cloudflare authorization;
7. all four report buttons work through Nexus;
8. callback receive/handle receipts remain observable;
9. unchanged-card deduplication remains intact;
10. no duplicate Telegram receiver is introduced.

Until these gates pass, Rich V10 remains FIELD_UNVERIFIED and V9 remains the field-safe fallback.
