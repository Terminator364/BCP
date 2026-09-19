package com.blessing.bcpedge;

import android.content.Context;

import org.json.JSONArray;
import org.json.JSONObject;

public final class TelegramObservabilityPoller {
    private final TelegramConfigStore config;
    private final TelegramObservabilityCollector collector;
    private final BcpClient bcp;

    public TelegramObservabilityPoller(Context context) {
        Context app = context.getApplicationContext();
        this.config = new TelegramConfigStore(app);
        this.collector = new TelegramObservabilityCollector(app);
        this.bcp = new BcpClient(app);
    }

    public int pollOnce(int timeoutSeconds) throws Exception {
        if (!config.isEnabled() || !config.hasBotToken()) return 0;
        TelegramBotClient bot = new TelegramBotClient(config.getBotToken());
        long offset = config.getLastUpdateId() + 1L;
        JSONArray updates = bot.getUpdates(offset, timeoutSeconds);
        int handled = 0;

        for (int i = 0; i < updates.length(); i++) {
            JSONObject update = updates.optJSONObject(i);
            if (update == null) continue;
            long updateId = update.optLong("update_id", 0L);
            if (updateId <= config.getLastUpdateId()) continue;
            JSONObject message = update.optJSONObject("message");
            if (message == null) {
                config.setLastUpdateId(updateId);
                continue;
            }
            JSONObject chat = message.optJSONObject("chat");
            JSONObject from = message.optJSONObject("from");
            String text = message.optString("text", "");
            if (chat == null || from == null || text.isEmpty()) {
                config.setLastUpdateId(updateId);
                continue;
            }

            long chatId = chat.optLong("id", 0L);
            long userId = from.optLong("id", 0L);
            String chatType = chat.optString("type", "");
            if (!config.isAuthorized(chatId, userId)) {
                if ("private".equals(chatType)) {
                    boolean offered = config.offerPendingIdentity(
                            chatId, userId, senderLabel(from));
                    if (offered) {
                        bot.sendText(chatId,
                                "BCP Telegram: identité détectée. Confirme-la physiquement dans BCP Edge avant tout accès aux statuts.");
                        bcp.recordEvent("TELEGRAM_IDENTITY_PENDING", "private_chat");
                    }
                }
                config.setLastUpdateId(updateId);
                handled++;
                continue;
            }

            TelegramObservabilityPolicy.Command command =
                    TelegramObservabilityPolicy.parse(text);
            if (!TelegramObservabilityPolicy.isReadOnly(command.kind)) {
                bot.sendText(chatId,
                        "BCP Telegram MVP-0 est strictement en lecture seule. Utilise /help.");
            } else {
                bot.sendText(chatId, collector.render(text));
                bcp.recordEvent("TELEGRAM_READ_COMMAND", command.kind.name());
            }
            config.setLastUpdateId(updateId);
            handled++;
        }
        return handled;
    }

    private static String senderLabel(JSONObject from) {
        String username = from.optString("username", "");
        if (!username.isEmpty()) return "@" + username;
        String first = from.optString("first_name", "");
        String last = from.optString("last_name", "");
        String label = (first + " " + last).trim();
        return label.isEmpty() ? "Telegram user" : label;
    }
}
