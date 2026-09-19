const JSON_HEADERS = { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" };

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });
}

function nowIso() {
  return new Date().toISOString();
}

function cleanText(value, max = 3900) {
  return String(value ?? "").replace(/[\r\0]/g, " ").trim().slice(0, max);
}

function safeEqual(a, b) {
  const x = new TextEncoder().encode(String(a ?? ""));
  const y = new TextEncoder().encode(String(b ?? ""));
  if (x.length !== y.length) return false;
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
}

async function sha256Hex(text) {
  const data = new TextEncoder().encode(String(text));
  const digest = await crypto.subtle.digest("SHA-256", data);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function requireEnv(env, key) {
  const value = String(env[key] ?? "").trim();
  if (!value) throw new Error("missing_env_" + key);
  return value;
}

function bearer(request) {
  const raw = request.headers.get("authorization") || "";
  return raw.startsWith("Bearer ") ? raw.slice(7) : "";
}

function deviceAuthorized(request, env) {
  const token = bearer(request);
  const id = request.headers.get("x-bcp-device-id") || "";
  return safeEqual(token, requireEnv(env, "BCP_DEVICE_TOKEN"))
    && safeEqual(id, requireEnv(env, "BCP_DEVICE_ID"));
}

async function telegramCall(env, method, payload) {
  const token = requireEnv(env, "TELEGRAM_BOT_TOKEN");
  const response = await fetch("https://api.telegram.org/bot" + token + "/" + method, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  let body = {};
  try { body = await response.json(); } catch (_) {}
  if (!response.ok || !body.ok) {
    throw new Error("telegram_" + method + "_failed_" + response.status);
  }
  return body.result;
}

async function acceptTelegramWebhook(request, env) {
  const expected = requireEnv(env, "TELEGRAM_WEBHOOK_SECRET");
  const got = request.headers.get("x-telegram-bot-api-secret-token") || "";
  if (!safeEqual(got, expected)) return jsonResponse({ ok: false }, 401);

  let update;
  try { update = await request.json(); }
  catch (_) { return jsonResponse({ ok: false, error: "invalid_json" }, 400); }

  const updateId = Number(update?.update_id);
  const message = update?.message || {};
  const chat = message?.chat || {};
  const chatId = String(chat?.id ?? "");
  const allowedChatId = requireEnv(env, "ALLOWED_CHAT_ID");
  const text = cleanText(message?.text || "", 1024);

  if (!Number.isSafeInteger(updateId)) return jsonResponse({ ok: true, ignored: "no_update_id" });
  if (chatId !== allowedChatId || String(chat?.type || "") !== "private") {
    return jsonResponse({ ok: true, ignored: "unauthorized_chat" });
  }
  if (!text.startsWith("/")) return jsonResponse({ ok: true, ignored: "non_command" });

  await env.DB.prepare(
    "INSERT OR IGNORE INTO commands(telegram_update_id, chat_id, text, state, created_at) VALUES(?1, ?2, ?3, 'QUEUED', ?4)"
  ).bind(updateId, chatId, text, nowIso()).run();

  return jsonResponse({ ok: true });
}

async function pullCommands(request, env) {
  if (!deviceAuthorized(request, env)) return jsonResponse({ ok: false }, 401);
  const url = new URL(request.url);
  const after = Math.max(0, Number.parseInt(url.searchParams.get("after") || "0", 10) || 0);
  const limit = Math.max(1, Math.min(20, Number.parseInt(url.searchParams.get("limit") || "8", 10) || 8));

  const rows = await env.DB.prepare(
    "SELECT id, text, created_at FROM commands WHERE id > ?1 AND state IN ('QUEUED','DELIVERED') ORDER BY id ASC LIMIT ?2"
  ).bind(after, limit).all();

  const commands = (rows.results || []).map((r) => ({
    id: Number(r.id),
    text: String(r.text || ""),
    created_at: r.created_at,
  }));
  const nextCursor = commands.length ? commands[commands.length - 1].id : after;

  if (commands.length) {
    await env.DB.prepare(
      "UPDATE commands SET state='DELIVERED', delivered_at=?1 WHERE id > ?2 AND id <= ?3 AND state='QUEUED'"
    ).bind(nowIso(), after, nextCursor).run();
  }
  return jsonResponse({ schema: "bcp.nexus.commands/1", commands, next_cursor: nextCursor });
}

async function replyToCommand(request, env) {
  if (!deviceAuthorized(request, env)) return jsonResponse({ ok: false }, 401);
  let body;
  try { body = await request.json(); }
  catch (_) { return jsonResponse({ ok: false, error: "invalid_json" }, 400); }

  const commandId = Number(body?.command_id);
  const text = cleanText(body?.text || "");
  const idem = cleanText(body?.idempotency_key || "", 128);
  if (!Number.isSafeInteger(commandId) || commandId <= 0 || !text || !idem) {
    return jsonResponse({ ok: false, error: "invalid_reply" }, 400);
  }

  const cmd = await env.DB.prepare("SELECT id, chat_id, state FROM commands WHERE id=?1")
    .bind(commandId).first();
  if (!cmd) return jsonResponse({ ok: false, error: "command_not_found" }, 404);

  const bodyHash = await sha256Hex(commandId + "\n" + text);
  const reserve = await env.DB.prepare(
    "INSERT OR IGNORE INTO replies(command_id, idempotency_key, body_hash, status, updated_at) VALUES(?1, ?2, ?3, 'RESERVED', ?4)"
  ).bind(commandId, idem, bodyHash, nowIso()).run();

  if (!reserve.meta?.changes) {
    const existing = await env.DB.prepare(
      "SELECT status, body_hash, telegram_message_id FROM replies WHERE command_id=?1"
    ).bind(commandId).first();
    if (!existing || String(existing.body_hash) !== bodyHash) {
      return jsonResponse({ ok: false, error: "idempotency_conflict" }, 409);
    }
    return jsonResponse({
      ok: true, duplicate: true, status: existing.status,
      telegram_message_id: existing.telegram_message_id || null,
    });
  }

  try {
    const result = await telegramCall(env, "sendMessage", {
      chat_id: String(cmd.chat_id),
      text,
      disable_web_page_preview: true,
    });
    const messageId = String(result?.message_id ?? "");
    await env.DB.batch([
      env.DB.prepare(
        "UPDATE replies SET status='SENT', telegram_message_id=?1, updated_at=?2 WHERE command_id=?3"
      ).bind(messageId, nowIso(), commandId),
      env.DB.prepare(
        "UPDATE commands SET state='REPLIED', replied_at=?1 WHERE id=?2"
      ).bind(nowIso(), commandId),
    ]);
    return jsonResponse({ ok: true, telegram_message_id: messageId });
  } catch (error) {
    await env.DB.prepare(
      "UPDATE replies SET status='SEND_FAILED', updated_at=?1 WHERE command_id=?2"
    ).bind(nowIso(), commandId).run();
    return jsonResponse({ ok: false, error: "telegram_send_failed" }, 502);
  }
}

async function pushEvent(request, env) {
  if (!deviceAuthorized(request, env)) return jsonResponse({ ok: false }, 401);
  let body;
  try { body = await request.json(); }
  catch (_) { return jsonResponse({ ok: false, error: "invalid_json" }, 400); }

  const text = cleanText(body?.text || "");
  const idem = cleanText(body?.idempotency_key || "", 128);
  const kind = cleanText(body?.kind || "EVENT", 40);
  if (!text || !idem) return jsonResponse({ ok: false, error: "invalid_event" }, 400);

  const bodyHash = await sha256Hex(kind + "\n" + text);
  const reserve = await env.DB.prepare(
    "INSERT OR IGNORE INTO outbound(idempotency_key, kind, body_hash, status, updated_at) VALUES(?1, ?2, ?3, 'RESERVED', ?4)"
  ).bind(idem, kind, bodyHash, nowIso()).run();

  if (!reserve.meta?.changes) {
    const existing = await env.DB.prepare(
      "SELECT status, body_hash, telegram_message_id FROM outbound WHERE idempotency_key=?1"
    ).bind(idem).first();
    if (!existing || String(existing.body_hash) !== bodyHash) {
      return jsonResponse({ ok: false, error: "idempotency_conflict" }, 409);
    }
    return jsonResponse({
      ok: true, duplicate: true, status: existing.status,
      telegram_message_id: existing.telegram_message_id || null,
    });
  }

  try {
    const result = await telegramCall(env, "sendMessage", {
      chat_id: requireEnv(env, "ALLOWED_CHAT_ID"),
      text,
      disable_web_page_preview: true,
    });
    const messageId = String(result?.message_id ?? "");
    await env.DB.prepare(
      "UPDATE outbound SET status='SENT', telegram_message_id=?1, updated_at=?2 WHERE idempotency_key=?3"
    ).bind(messageId, nowIso(), idem).run();
    return jsonResponse({ ok: true, telegram_message_id: messageId });
  } catch (error) {
    await env.DB.prepare(
      "UPDATE outbound SET status='SEND_FAILED', updated_at=?1 WHERE idempotency_key=?2"
    ).bind(nowIso(), idem).run();
    return jsonResponse({ ok: false, error: "telegram_send_failed" }, 502);
  }
}

async function health(env) {
  let db = "UNKNOWN";
  try {
    const row = await env.DB.prepare("SELECT 1 AS ok").first();
    db = row?.ok === 1 ? "OK" : "DEGRADED";
  } catch (_) {
    db = "DEGRADED";
  }
  return jsonResponse({
    schema: "bcp.nexus.health/1",
    service: "BCP_NEXUS",
    version: "0.1.0",
    status: db === "OK" ? "HEALTHY" : "DEGRADED",
    database: db,
    spend_policy: "ZERO_USD",
    time: nowIso(),
  }, db === "OK" ? 200 : 503);
}

export default {
  async fetch(request, env) {
    try {
      const url = new URL(request.url);
      if (request.method === "GET" && url.pathname === "/health") return health(env);
      if (request.method === "POST" && url.pathname === "/telegram/webhook") return acceptTelegramWebhook(request, env);
      if (request.method === "GET" && url.pathname === "/v1/device/commands") return pullCommands(request, env);
      if (request.method === "POST" && url.pathname === "/v1/device/reply") return replyToCommand(request, env);
      if (request.method === "POST" && url.pathname === "/v1/device/push") return pushEvent(request, env);
      return jsonResponse({ ok: false, error: "not_found" }, 404);
    } catch (error) {
      return jsonResponse({ ok: false, error: "internal_error" }, 500);
    }
  },
};
