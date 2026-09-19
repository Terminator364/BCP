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

function cockpitKeyboard() {
  return {
    inline_keyboard: [
      [
        { text: "🔄 Actualiser", callback_data: "bcp:status" },
        { text: "📍 Où ?", callback_data: "bcp:where" },
      ],
      [
        { text: "🗂 Missions", callback_data: "bcp:missions" },
        { text: "🧾 Détails", callback_data: "bcp:details" },
      ],
      [
        { text: "📄 PDF suivi", callback_data: "bcp:pdf:summary" },
        { text: "📚 PDF technique", callback_data: "bcp:pdf:technical" },
      ],
    ],
  };
}

function callbackToCommand(data) {
  const map = {
    "bcp:status": "/status",
    "bcp:where": "/where",
    "bcp:missions": "/missions",
    "bcp:details": "/details",
  };
  return map[String(data || "")] || "";
}

function pdfAscii(value) {
  return String(value ?? "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[—–]/g, "-")
    .replace(/→/g, "->")
    .replace(/←/g, "<-")
    .replace(/[^\x20-\x7E\n]/g, "?");
}

function pdfEscape(value) {
  return String(value).replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)");
}

function concatBytes(parts) {
  const size = parts.reduce((n, p) => n + p.length, 0);
  const out = new Uint8Array(size);
  let offset = 0;
  for (const p of parts) { out.set(p, offset); offset += p.length; }
  return out;
}

function reportPdfBytes(title, body) {
  const encoder = new TextEncoder();
  const rawLines = pdfAscii(title + "\n\n" + body).split("\n");
  const lines = [];
  for (let raw of rawLines) {
    if (!raw) { lines.push(""); continue; }
    while (raw.length > 92) {
      let cut = raw.lastIndexOf(" ", 92);
      if (cut < 24) cut = 92;
      lines.push(raw.slice(0, cut).trimEnd());
      raw = raw.slice(cut).trimStart();
    }
    lines.push(raw);
  }
  const perPage = 46;
  const pages = [];
  for (let i = 0; i < Math.max(1, lines.length); i += perPage) pages.push(lines.slice(i, i + perPage));
  if (!pages.length) pages.push([]);

  const objects = [];
  objects.push(encoder.encode("<< /Type /Catalog /Pages 2 0 R >>"));
  objects.push(new Uint8Array());
  objects.push(encoder.encode("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"));
  const pageRefs = [];
  let nextObj = 4;
  for (const pageLines of pages) {
    const pageObj = nextObj++;
    const streamObj = nextObj++;
    pageRefs.push(pageObj);
    const content = ["BT", "/F1 10 Tf", "48 790 Td", "12 TL"];
    pageLines.forEach((line, idx) => {
      if (idx) content.push("T*");
      content.push("(" + pdfEscape(line) + ") Tj");
    });
    content.push("ET");
    const stream = encoder.encode(content.join("\n"));
    objects.push(encoder.encode(
      "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 3 0 R >> >> /Contents " +
      streamObj + " 0 R >>"
    ));
    objects.push(concatBytes([
      encoder.encode("<< /Length " + stream.length + " >>\nstream\n"),
      stream,
      encoder.encode("\nendstream"),
    ]));
  }
  objects[1] = encoder.encode("<< /Type /Pages /Kids [" + pageRefs.map((x) => x + " 0 R").join(" ") +
    "] /Count " + pageRefs.length + " >>");

  const parts = [encoder.encode("%PDF-1.4\n%BCP\n")];
  const offsets = [0];
  let length = parts[0].length;
  objects.forEach((obj, idx) => {
    offsets.push(length);
    const wrapped = concatBytes([
      encoder.encode(String(idx + 1) + " 0 obj\n"),
      obj,
      encoder.encode("\nendobj\n"),
    ]);
    parts.push(wrapped);
    length += wrapped.length;
  });
  const xref = length;
  let trailer = "xref\n0 " + (objects.length + 1) + "\n0000000000 65535 f \n";
  for (const off of offsets.slice(1)) trailer += String(off).padStart(10, "0") + " 00000 n \n";
  trailer += "trailer\n<< /Size " + (objects.length + 1) + " /Root 1 0 R >>\nstartxref\n" + xref + "\n%%EOF\n";
  parts.push(encoder.encode(trailer));
  return concatBytes(parts);
}

async function telegramSendDocument(env, filename, bytes, caption) {
  const token = requireEnv(env, "TELEGRAM_BOT_TOKEN");
  const form = new FormData();
  form.set("chat_id", requireEnv(env, "ALLOWED_CHAT_ID"));
  form.set("caption", cleanText(caption, 900));
  form.set("document", new Blob([bytes], { type: "application/pdf" }), filename);
  const response = await fetch("https://api.telegram.org/bot" + token + "/sendDocument", {
    method: "POST",
    body: form,
  });
  let body = {};
  try { body = await response.json(); } catch (_) {}
  if (!response.ok || !body.ok) throw new Error("telegram_sendDocument_failed_" + response.status);
  return body.result;
}

async function sendCachedReportPdf(env, reportKey) {
  const row = await env.DB.prepare(
    "SELECT body_text, updated_at FROM reports WHERE report_key=?1"
  ).bind(reportKey).first();
  if (!row || !String(row.body_text || "")) {
    await telegramCall(env, "sendMessage", {
      chat_id: requireEnv(env, "ALLOWED_CHAT_ID"),
      text: "Rapport pas encore disponible. Le cockpit attend une nouvelle preuve BCP.",
      reply_markup: cockpitKeyboard(),
      disable_web_page_preview: true,
    });
    return false;
  }
  const technical = reportKey === "technical";
  const title = technical ? "BCP - Rapport technique" : "BCP - Rapport de suivi";
  const filename = technical ? "BCP_DETAILS_TECHNIQUES.pdf" : "BCP_SUIVI.pdf";
  const bytes = reportPdfBytes(title, String(row.body_text));
  await telegramSendDocument(env, filename, bytes, title + " · " + String(row.updated_at || ""));
  return true;
}

async function acceptTelegramWebhook(request, env) {
  const expected = requireEnv(env, "TELEGRAM_WEBHOOK_SECRET");
  const got = request.headers.get("x-telegram-bot-api-secret-token") || "";
  if (!safeEqual(got, expected)) return jsonResponse({ ok: false }, 401);

  let update;
  try { update = await request.json(); }
  catch (_) { return jsonResponse({ ok: false, error: "invalid_json" }, 400); }

  const updateId = Number(update?.update_id);
  if (!Number.isSafeInteger(updateId)) return jsonResponse({ ok: true, ignored: "no_update_id" });

  const callback = update?.callback_query || null;
  const message = callback?.message || update?.message || {};
  const chat = message?.chat || {};
  const chatId = String(chat?.id ?? "");
  const allowedChatId = requireEnv(env, "ALLOWED_CHAT_ID");
  if (chatId !== allowedChatId || String(chat?.type || "") !== "private") {
    if (callback?.id) {
      try { await telegramCall(env, "answerCallbackQuery", { callback_query_id: String(callback.id), text: "Non autorisé" }); }
      catch (_) {}
    }
    return jsonResponse({ ok: true, ignored: "unauthorized_chat" });
  }

  if (callback) {
    const data = cleanText(callback?.data || "", 64);
    try {
      await telegramCall(env, "answerCallbackQuery", {
        callback_query_id: String(callback?.id || ""),
        text: data.startsWith("bcp:pdf:") ? "Préparation du PDF…" : "BCP actualise…",
      });
    } catch (_) {}

    if (data === "bcp:pdf:summary") {
      await sendCachedReportPdf(env, "summary");
      return jsonResponse({ ok: true, callback: data });
    }
    if (data === "bcp:pdf:technical") {
      await sendCachedReportPdf(env, "technical");
      return jsonResponse({ ok: true, callback: data });
    }
    const command = callbackToCommand(data);
    if (!command) return jsonResponse({ ok: true, ignored: "unknown_callback" });
    await env.DB.prepare(
      "INSERT OR IGNORE INTO commands(telegram_update_id, chat_id, text, state, created_at) VALUES(?1, ?2, ?3, 'QUEUED', ?4)"
    ).bind(updateId, chatId, command, nowIso()).run();
    return jsonResponse({ ok: true, callback: data, queued: command });
  }

  const text = cleanText(message?.text || "", 1024);
  if (!text.startsWith("/")) return jsonResponse({ ok: true, ignored: "non_command" });
  const commandName = text.split(/\s+/, 1)[0].split("@", 1)[0].toLowerCase();
  if (commandName === "/report") {
    await sendCachedReportPdf(env, "summary");
    return jsonResponse({ ok: true, report: "summary" });
  }
  if (commandName === "/reporttech") {
    await sendCachedReportPdf(env, "technical");
    return jsonResponse({ ok: true, report: "technical" });
  }

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
      reply_markup: cockpitKeyboard(),
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


async function liveCard(request, env) {
  if (!deviceAuthorized(request, env)) return jsonResponse({ ok: false }, 401);
  let body;
  try { body = await request.json(); }
  catch (_) { return jsonResponse({ ok: false, error: "invalid_json" }, 400); }

  const text = cleanText(body?.text || "");
  const cardKey = cleanText(body?.card_key || "mission-status", 96);
  if (!text || !cardKey) return jsonResponse({ ok: false, error: "invalid_live_card" }, 400);

  const bodyHash = await sha256Hex(cardKey + "\n" + text);
  const prior = await env.DB.prepare(
    "SELECT telegram_message_id, body_hash FROM live_cards WHERE card_key=?1"
  ).bind(cardKey).first();

  if (prior && String(prior.body_hash || "") === bodyHash) {
    return jsonResponse({
      ok: true,
      duplicate: true,
      edited: false,
      telegram_message_id: String(prior.telegram_message_id || ""),
    });
  }

  let messageId = prior ? String(prior.telegram_message_id || "") : "";
  let edited = false;

  if (messageId) {
    try {
      const result = await telegramCall(env, "editMessageText", {
        chat_id: requireEnv(env, "ALLOWED_CHAT_ID"),
        message_id: Number(messageId),
        text,
        reply_markup: cockpitKeyboard(),
        disable_web_page_preview: true,
      });
      messageId = String(result?.message_id ?? messageId);
      edited = true;
    } catch (_) {
      messageId = "";
    }
  }

  if (!messageId) {
    const result = await telegramCall(env, "sendMessage", {
      chat_id: requireEnv(env, "ALLOWED_CHAT_ID"),
      text,
      reply_markup: cockpitKeyboard(),
      disable_web_page_preview: true,
    });
    messageId = String(result?.message_id ?? "");
  }

  await env.DB.prepare(
    "INSERT INTO live_cards(card_key, telegram_message_id, body_hash, updated_at) VALUES(?1, ?2, ?3, ?4) " +
    "ON CONFLICT(card_key) DO UPDATE SET telegram_message_id=excluded.telegram_message_id, body_hash=excluded.body_hash, updated_at=excluded.updated_at"
  ).bind(cardKey, messageId, bodyHash, nowIso()).run();

  return jsonResponse({
    ok: true,
    edited,
    telegram_message_id: messageId,
  });
}

async function storeReports(request, env) {
  if (!deviceAuthorized(request, env)) return jsonResponse({ ok: false }, 401);
  let body;
  try { body = await request.json(); }
  catch (_) { return jsonResponse({ ok: false, error: "invalid_json" }, 400); }

  const summary = cleanText(body?.summary || "", 18000);
  const technical = cleanText(body?.technical || "", 26000);
  if (!summary || !technical) return jsonResponse({ ok: false, error: "invalid_report" }, 400);

  const now = nowIso();
  const rows = [
    ["summary", summary, await sha256Hex(summary), now],
    ["technical", technical, await sha256Hex(technical), now],
  ];
  await env.DB.batch(rows.map((r) =>
    env.DB.prepare(
      "INSERT INTO reports(report_key, body_text, body_hash, updated_at) VALUES(?1, ?2, ?3, ?4) " +
      "ON CONFLICT(report_key) DO UPDATE SET body_text=excluded.body_text, body_hash=excluded.body_hash, updated_at=excluded.updated_at"
    ).bind(...r)
  ));
  return jsonResponse({ ok: true, updated_at: now });
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
    version: "0.1.5",
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
      if (request.method === "POST" && url.pathname === "/v1/device/live-card") return liveCard(request, env);
      if (request.method === "POST" && url.pathname === "/v1/device/report") return storeReports(request, env);
      return jsonResponse({ ok: false, error: "not_found" }, 404);
    } catch (error) {
      return jsonResponse({ ok: false, error: "internal_error" }, 500);
    }
  },
};
