const JSON_HEADERS = { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" };

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });
}

function nowIso() {
  // Canonical machine time remains UTC.
  return new Date().toISOString();
}

function humanTimestampKinshasa(value = null, seconds = true) {
  const d = value ? new Date(String(value)) : new Date();
  if (Number.isNaN(d.getTime())) return cleanText(value || "heure non observée", 80);
  const k = new Date(d.getTime() + 60 * 60 * 1000);
  const pad = (n) => String(n).padStart(2, "0");
  const base = pad(k.getUTCDate()) + "/" + pad(k.getUTCMonth() + 1) + "/" + k.getUTCFullYear()
    + " à " + pad(k.getUTCHours()) + ":" + pad(k.getUTCMinutes());
  return base + (seconds ? ":" + pad(k.getUTCSeconds()) : "") + " (Kinshasa)";
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
        { text: "🟢 Où en sommes-nous ?", callback_data: "bcp:status" },
        { text: "🕘 Nouveautés", callback_data: "bcp:since" },
      ],
      [
        { text: "💬 Messages récents", callback_data: "bcp:conversations" },
        { text: "❓ Pourquoi cet état ?", callback_data: "bcp:why" },
      ],
      [
        { text: "📍 Étape actuelle", callback_data: "bcp:where" },
        { text: "🎯 Objectif & plan", callback_data: "bcp:missions" },
      ],
      [
        { text: "⚙️ Travail récent", callback_data: "bcp:tail" },
        { text: "🔭 Risques à venir", callback_data: "bcp:risks" },
      ],
      [{ text: "▶️ Reprendre maintenant", callback_data: "bcp:continue" }],
      [
        { text: "✅ Vu / compris", callback_data: "bcp:ack" },
        { text: "🔕 Pause 2h", callback_data: "bcp:quiet:120" },
        { text: "🔔 Alertes normales", callback_data: "bcp:quiet:off" },
      ],
      [
        { text: "❔ Aide / mode d’emploi", callback_data: "bcp:help" },
        { text: "📚 Rapports & technique", callback_data: "bcp:advanced" },
      ],
    ],
  };
}

function advancedCockpitKeyboard() {
  return {
    inline_keyboard: [
      [
        { text: "📄 Résumé PDF", callback_data: "bcp:pdf:summary" },
        { text: "🖥️ État appareils", callback_data: "bcp:pdf:devices" },
      ],
      [
        { text: "🧭 Plan mission", callback_data: "bcp:pdf:mission" },
        { text: "📚 Audit PDF", callback_data: "bcp:pdf:technical" },
      ],
      [{ text: "🧰 Détails techniques", callback_data: "bcp:details" }],
      [{ text: "↩️ Retour au cockpit", callback_data: "bcp:status" }],
    ],
  };
}

function callbackToCommand(data) {
  const map = {
    "bcp:continue": "/continue",
    "bcp:status": "/status",
    "bcp:since": "/since",
    "bcp:why": "/why",
    "bcp:risks": "/risks",
    "bcp:ack": "/ack",
    "bcp:conversations": "/conversations",
    "bcp:where": "/where",
    "bcp:tail": "/tail",
    "bcp:missions": "/objective",
    "bcp:quiet:120": "/quiet 120",
    "bcp:quiet:off": "/quiet off",
    "bcp:details": "/details",
    "bcp:help": "/help",
  };
  return map[String(data || "")] || "";
}

function pdfNormalize(value) {
  const replacements = new Map([
    ["—", "-"], ["–", "-"], ["→", "->"], ["←", "<-"], ["•", "*"], ["≈", "~"],
    ["✅", "[OK]"], ["⚠️", "[!]"], ["⚠", "[!]"], ["🟢", "[OK]"], ["🟡", "[~]"], ["🟠", "[~]"],
    ["🔴", "[X]"], ["⚪", "[ ]"], ["🤖", "BCP"], ["🎯", "OBJECTIF"], ["📊", "PROGRESSION"],
    ["➡️", "ENSUITE"], ["➡", "ENSUITE"], ["👤", "VOUS"], ["🕒", "HEURE"], ["⏱️", "AGE"],
    ["📨", "ENVOI"], ["🌐", "RESEAU"], ["🧪", "TESTS"], ["🔧", "DETAILS"], ["ℹ️", "INFO"],
    ["💾", "CHECKPOINT"], ["🏁", "TERMINE"], ["📌", "MISSION"], ["🧭", "PLAN"],
    ["▶️", "DEMARRER"], ["📤", "ENVOYE"], ["📥", "RECU"], ["🔎", "VERIFIER"],
    ["🔁", "REESSAI"], ["🛑", "BLOQUE"], ["⏹️", "ARRET"], ["🛰️", "BCP"],
    ["💬", "MESSAGES"], ["❓", "POURQUOI"], ["📍", "ETAPE"], ["⚙️", "TRAVAIL"],
    ["🔭", "RISQUES"], ["🔕", "PAUSE"], ["🔔", "ALERTES"], ["📄", "RAPPORT"],
    ["🖥️", "APPAREILS"], ["📚", "AUDIT"], ["🧰", "TECHNIQUE"], ["🕘", "NOUVEAUTES"],
    ["📈", "PROGRESSION"], ["🎚️", "CONFIANCE"], ["🔵", "[i]"], ["🟣", "[ACTION]"],
  ]);
  let text = String(value ?? "").replace(/\r/g, "");
  for (const [src, dst] of replacements.entries()) text = text.split(src).join(dst);
  return text;
}

function winAnsiByte(ch) {
  const cp = ch.codePointAt(0);
  if (cp >= 0x20 && cp <= 0x7e) return cp;
  if (cp >= 0xa0 && cp <= 0xff) return cp;
  const extra = new Map([
    ["€",0x80],["‚",0x82],["ƒ",0x83],["„",0x84],["…",0x85],["†",0x86],["‡",0x87],
    ["ˆ",0x88],["‰",0x89],["Š",0x8a],["‹",0x8b],["Œ",0x8c],["Ž",0x8e],
    ["‘",0x91],["’",0x92],["“",0x93],["”",0x94],["•",0x95],["–",0x96],["—",0x97],
    ["˜",0x98],["™",0x99],["š",0x9a],["›",0x9b],["œ",0x9c],["ž",0x9e],["Ÿ",0x9f],
  ]);
  return extra.get(ch) ?? 0x3f;
}

function pdfWinAnsiEscape(value) {
  const src = pdfNormalize(value);
  let out = "";
  for (const ch of src) {
    const b = winAnsiByte(ch);
    if (b === 0x28 || b === 0x29 || b === 0x5c) out += "\\" + String.fromCharCode(b);
    else if (b < 0x20 || b >= 0x7f) out += "\\" + b.toString(8).padStart(3, "0");
    else out += String.fromCharCode(b);
  }
  return out;
}

function pdfWrap(value, width) {
  let text = pdfNormalize(value).trim();
  if (!text) return [""];
  const out = [];
  while (text.length > width) {
    let cut = text.lastIndexOf(" ", width);
    if (cut < Math.max(18, Math.floor(width / 3))) cut = width;
    out.push(text.slice(0, cut).trimEnd());
    text = text.slice(cut).trimStart();
  }
  out.push(text);
  return out;
}

function pdfStyle(raw) {
  const line = String(raw ?? "").trim();
  if (!line) return ["blank", ""];
  if (line.startsWith("- ") || line.startsWith("* ")) return ["bullet", line.slice(2).trim()];
  if (
    line.length <= 76 &&
    /[A-Za-zÀ-ÿ]/.test(line) &&
    line === line.toUpperCase() &&
    !/^(HTTP|SHA|ID:)/.test(line)
  ) return ["section", line];
  if (/^(À RETENIR|ACTION POUR VOUS|CE QUI BLOQUE|CE QUI VA)/.test(line)) return ["section", line];
  return ["body", line];
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
  const docTitle = pdfNormalize(cleanText(title, 140));
  let rawLines = String(body ?? "").replace(/\r/g, "").split("\n");

  // Keep one document title only; cached report bodies may repeat their own title.
  if (rawLines.length && /^BCP.*RAPPORT/i.test(rawLines[0].trim())) {
    rawLines = rawLines.slice(1);
    if (rawLines.length && !rawLines[0].trim()) rawLines = rawLines.slice(1);
  }

  const specs = {
    title:   { font:"F2", size:16, leading:21, width:56, indent:0 },
    section: { font:"F2", size:11.5, leading:17, width:70, indent:0 },
    body:    { font:"F1", size:9.5, leading:13, width:82, indent:0 },
    bullet:  { font:"F1", size:9.5, leading:13, width:78, indent:12 },
    blank:   { font:"F1", size:9.5, leading:8, width:82, indent:0 },
  };

  const entries = [["title", docTitle], ["blank", ""]];
  for (const raw of rawLines) {
    const [style, value] = pdfStyle(raw);
    if (style === "blank") { entries.push([style, ""]); continue; }
    const wrapped = pdfWrap(value, specs[style].width);
    wrapped.forEach((line, pos) => {
      entries.push([style, style === "bullet" ? ((pos === 0 ? "* " : "  ") + line) : line]);
    });
  }

  const left = 48, top = 792, bottom = 58;
  const pages = [];
  let page = [];
  let y = top;
  for (const [style, line] of entries) {
    const leading = specs[style].leading;
    const required = leading + (style === "section" ? 13 : 0);
    if (y - required < bottom) {
      pages.push(page);
      page = [];
      y = top - 18;
    }
    page.push([style, line, y]);
    y -= leading;
  }
  if (page.length || !pages.length) pages.push(page);

  const objects = [];
  objects.push(encoder.encode("<< /Type /Catalog /Pages 2 0 R >>"));
  objects.push(new Uint8Array());
  objects.push(encoder.encode("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"));
  objects.push(encoder.encode("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"));

  const pageRefs = [];
  let nextObj = 5;
  const totalPages = pages.length;
  for (let pageNo = 1; pageNo <= totalPages; pageNo++) {
    const pageObj = nextObj++;
    const streamObj = nextObj++;
    pageRefs.push(pageObj);
    const content = ["BT"];
    if (pageNo > 1) {
      content.push("/F2 8 Tf", "1 0 0 1 48 814 Tm", "(" + pdfWinAnsiEscape(docTitle) + ") Tj");
    }
    for (const [style, line, lineY] of pages[pageNo - 1]) {
      const spec = specs[style];
      content.push(
        "/" + spec.font + " " + spec.size + " Tf",
        "1 0 0 1 " + (left + spec.indent) + " " + lineY + " Tm",
        "(" + pdfWinAnsiEscape(line) + ") Tj"
      );
    }
    const footer = "Page " + pageNo + "/" + totalPages + " - Heure affichée : Kinshasa (UTC+1)";
    content.push("/F1 7.5 Tf", "1 0 0 1 48 28 Tm", "(" + pdfWinAnsiEscape(footer) + ") Tj", "ET");
    const stream = encoder.encode(content.join("\n"));
    objects.push(encoder.encode(
      "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents " +
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

  const parts = [encoder.encode("%PDF-1.4\n%BCP-HUMAN-PDF\n")];
  const offsets = [0];
  let length = parts[0].length;
  objects.forEach((obj, idx) => {
    offsets.push(length);
    const wrapped = concatBytes([
      encoder.encode(String(idx + 1) + " 0 obj\n"), obj, encoder.encode("\nendobj\n"),
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
  const meta = {
    summary: ["BCP - Situation humaine complète", "BCP_1_SITUATION.pdf"],
    devices: ["BCP - Appareils, réseau et transports", "BCP_2_APPAREILS_RESEAU.pdf"],
    mission: ["BCP - Objectif, étapes et progression", "BCP_3_MISSION_PROGRESS.pdf"],
    technical: ["BCP - Dossier technique et audit", "BCP_4_AUDIT_TECHNIQUE.pdf"],
  }[reportKey] || ["BCP - Rapport", "BCP_RAPPORT.pdf"];
  const title = meta[0];
  const filename = meta[1];
  const bytes = reportPdfBytes(title, String(row.body_text));
  await telegramSendDocument(env, filename, bytes, title + " · " + humanTimestampKinshasa(row.updated_at, true));
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

    if (data === "bcp:advanced") {
      await telegramCall(env, "sendMessage", {
        chat_id: allowedChatId,
        text: "📚 Rapports & technique\nCes outils sont secondaires : utilisez-les pour approfondir une situation déjà comprise.",
        reply_markup: advancedCockpitKeyboard(),
        disable_web_page_preview: true,
      });
      return jsonResponse({ ok: true, callback: data, advanced_menu: true });
    }
    if (data === "bcp:pdf:summary") {
      await sendCachedReportPdf(env, "summary");
      return jsonResponse({ ok: true, callback: data });
    }
    if (data === "bcp:pdf:devices") {
      await sendCachedReportPdf(env, "devices");
      return jsonResponse({ ok: true, callback: data });
    }
    if (data === "bcp:pdf:mission") {
      await sendCachedReportPdf(env, "mission");
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
  const silent = Boolean(body?.silent);
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
      disable_notification: silent,
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
  const richHtml = cleanText(body?.rich_html || "", 30000);
  const cardKey = cleanText(body?.card_key || "mission-status", 96);
  if (!text || !cardKey) return jsonResponse({ ok: false, error: "invalid_live_card" }, 400);

  const bodyHash = await sha256Hex(cardKey + "\n" + text + "\n" + richHtml);
  const prior = await env.DB.prepare(
    "SELECT telegram_message_id, body_hash FROM live_cards WHERE card_key=?1"
  ).bind(cardKey).first();

  if (prior && String(prior.body_hash || "") === bodyHash) {
    return jsonResponse({
      ok: true, duplicate: true, edited: false,
      telegram_message_id: String(prior.telegram_message_id || ""),
    });
  }

  let messageId = prior ? String(prior.telegram_message_id || "") : "";
  let edited = false;
  let renderMode = "V9_PLAIN_FALLBACK";

  if (messageId && richHtml) {
    try {
      const result = await telegramCall(env, "editMessageText", {
        chat_id: requireEnv(env, "ALLOWED_CHAT_ID"),
        message_id: Number(messageId),
        rich_message: { html: richHtml, skip_entity_detection: true },
      });
      messageId = String(result?.message_id ?? messageId);
      edited = true;
      renderMode = "RICH_V10";
    } catch (_) {}
  }

  if (messageId && !edited) {
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
      renderMode = "V9_PLAIN_FALLBACK";
    } catch (_) {
      messageId = "";
    }
  }

  if (!messageId && richHtml) {
    try {
      const result = await telegramCall(env, "sendRichMessage", {
        chat_id: requireEnv(env, "ALLOWED_CHAT_ID"),
        rich_message: { html: richHtml, skip_entity_detection: true },
      });
      messageId = String(result?.message_id ?? "");
      renderMode = "RICH_V10";
    } catch (_) {}
  }

  if (!messageId) {
    const result = await telegramCall(env, "sendMessage", {
      chat_id: requireEnv(env, "ALLOWED_CHAT_ID"),
      text,
      reply_markup: cockpitKeyboard(),
      disable_web_page_preview: true,
    });
    messageId = String(result?.message_id ?? "");
    renderMode = "V9_PLAIN_FALLBACK";
  }

  await env.DB.prepare(
    "INSERT INTO live_cards(card_key, telegram_message_id, body_hash, updated_at) VALUES(?1, ?2, ?3, ?4) " +
    "ON CONFLICT(card_key) DO UPDATE SET telegram_message_id=excluded.telegram_message_id, body_hash=excluded.body_hash, updated_at=excluded.updated_at"
  ).bind(cardKey, messageId, bodyHash, nowIso()).run();

  return jsonResponse({ ok: true, edited, render_mode: renderMode, telegram_message_id: messageId });
}

async function storeReports(request, env) {
  if (!deviceAuthorized(request, env)) return jsonResponse({ ok: false }, 401);
  let body;
  try { body = await request.json(); }
  catch (_) { return jsonResponse({ ok: false, error: "invalid_json" }, 400); }

  const values = {
    summary: cleanText(body?.summary || "", 18000),
    devices: cleanText(body?.devices || "", 22000),
    mission: cleanText(body?.mission || "", 24000),
    technical: cleanText(body?.technical || "", 26000),
  };
  if (!values.summary || !values.technical) {
    return jsonResponse({ ok: false, error: "invalid_report" }, 400);
  }

  const now = nowIso();
  const rows = [];
  for (const [key, value] of Object.entries(values)) {
    if (value) rows.push([key, value, await sha256Hex(value), now]);
  }
  await env.DB.batch(rows.map((r) =>
    env.DB.prepare(
      "INSERT INTO reports(report_key, body_text, body_hash, updated_at) VALUES(?1, ?2, ?3, ?4) " +
      "ON CONFLICT(report_key) DO UPDATE SET body_text=excluded.body_text, body_hash=excluded.body_hash, updated_at=excluded.updated_at"
    ).bind(...r)
  ));
  return jsonResponse({ ok: true, updated_at: now, report_count: rows.length });
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
    version: "0.2.6",
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
