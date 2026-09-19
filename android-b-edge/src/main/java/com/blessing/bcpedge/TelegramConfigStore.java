package com.blessing.bcpedge;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.security.KeyStore;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

public final class TelegramConfigStore {
    private static final String ALIAS = "bcp-edge-telegram-observability-v1";
    private static final String PREFS = "bcp_telegram_observability";
    private static final String TOKEN_BLOB = "bot_token_blob";
    private final SharedPreferences prefs;

    public TelegramConfigStore(Context context) {
        prefs = context.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public synchronized void putBotToken(String token) throws Exception {
        String value = token == null ? "" : token.trim();
        if (value.length() < 20 || !value.contains(":")) {
            throw new IllegalArgumentException("INVALID_BOT_TOKEN");
        }
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key());
        byte[] iv = cipher.getIV();
        byte[] ct = cipher.doFinal(value.getBytes(StandardCharsets.UTF_8));
        byte[] blob = new byte[1 + iv.length + ct.length];
        blob[0] = (byte) iv.length;
        System.arraycopy(iv, 0, blob, 1, iv.length);
        System.arraycopy(ct, 0, blob, 1 + iv.length, ct.length);
        prefs.edit().putString(TOKEN_BLOB, Base64.encodeToString(blob, Base64.NO_WRAP)).commit();
    }

    public synchronized String getBotToken() {
        try {
            String encoded = prefs.getString(TOKEN_BLOB, "");
            if (encoded == null || encoded.isEmpty()) return "";
            byte[] blob = Base64.decode(encoded, Base64.NO_WRAP);
            if (blob.length < 14) return "";
            int ivLen = blob[0] & 0xff;
            if (ivLen < 12 || ivLen > 16 || blob.length <= 1 + ivLen) return "";
            byte[] iv = new byte[ivLen];
            byte[] ct = new byte[blob.length - 1 - ivLen];
            System.arraycopy(blob, 1, iv, 0, ivLen);
            System.arraycopy(blob, 1 + ivLen, ct, 0, ct.length);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(128, iv));
            return new String(cipher.doFinal(ct), StandardCharsets.UTF_8);
        } catch (Exception ignored) {
            return "";
        }
    }

    public synchronized boolean hasBotToken() {
        return !getBotToken().isEmpty();
    }

    public synchronized void setBotIdentity(String username) {
        prefs.edit().putString("bot_username", username == null ? "" : username).commit();
    }

    public synchronized String getBotUsername() {
        return prefs.getString("bot_username", "");
    }

    public synchronized void setEnabled(boolean enabled) {
        prefs.edit().putBoolean("enabled", enabled).commit();
    }

    public synchronized boolean isEnabled() {
        return prefs.getBoolean("enabled", false);
    }

    public synchronized boolean offerPendingIdentity(long chatId, long userId, String label) {
        if (chatId == 0L || userId == 0L || isAuthorized(chatId, userId)) return false;
        long existingChat = prefs.getLong("pending_chat_id", 0L);
        long existingUser = prefs.getLong("pending_user_id", 0L);
        if (existingChat != 0L || existingUser != 0L) {
            return false;
        }
        return prefs.edit()
                .putLong("pending_chat_id", chatId)
                .putLong("pending_user_id", userId)
                .putString("pending_label", label == null ? "" : label)
                .putLong("pending_at", System.currentTimeMillis())
                .commit();
    }

    public synchronized boolean authorizePending() {
        long chat = prefs.getLong("pending_chat_id", 0L);
        long user = prefs.getLong("pending_user_id", 0L);
        if (chat == 0L || user == 0L) return false;
        return prefs.edit()
                .putLong("allowed_chat_id", chat)
                .putLong("allowed_user_id", user)
                .remove("pending_chat_id")
                .remove("pending_user_id")
                .remove("pending_label")
                .remove("pending_at")
                .commit();
    }

    public synchronized void clearPending() {
        prefs.edit()
                .remove("pending_chat_id")
                .remove("pending_user_id")
                .remove("pending_label")
                .remove("pending_at")
                .commit();
    }

    public synchronized boolean isAuthorized(long chatId, long userId) {
        long allowedChat = prefs.getLong("allowed_chat_id", 0L);
        long allowedUser = prefs.getLong("allowed_user_id", 0L);
        return allowedChat != 0L && allowedUser != 0L &&
                allowedChat == chatId && allowedUser == userId;
    }

    public synchronized boolean hasAuthorizedIdentity() {
        return prefs.getLong("allowed_chat_id", 0L) != 0L &&
                prefs.getLong("allowed_user_id", 0L) != 0L;
    }

    public synchronized void markServicePoll() {
        prefs.edit().putLong("service_poll_at", System.currentTimeMillis()).apply();
    }

    public synchronized boolean servicePollFresh(long maxAgeMs) {
        long at = prefs.getLong("service_poll_at", 0L);
        long now = System.currentTimeMillis();
        return at > 0L && now >= at && (now - at) <= Math.max(5_000L, maxAgeMs);
    }

    public synchronized long getLastUpdateId() {
        return prefs.getLong("last_update_id", 0L);
    }

    public synchronized void setLastUpdateId(long updateId) {
        if (updateId <= getLastUpdateId()) return;
        prefs.edit().putLong("last_update_id", updateId).commit();
    }

    public synchronized JSONObject status() {
        JSONObject out = new JSONObject();
        try {
            out.put("enabled", isEnabled());
            out.put("token_configured", hasBotToken());
            out.put("bot_username", getBotUsername());
            out.put("identity_authorized", hasAuthorizedIdentity());
            out.put("pending_identity", hasPendingIdentity());
            out.put("pending_label", pendingLabel());
            out.put("mode", "READ_ONLY_MVP0");
        } catch (Exception ignored) {}
        return out;
    }

    public synchronized String pendingLabel() {
        return prefs.getString("pending_label", "");
    }

    public synchronized boolean hasPendingIdentity() {
        return prefs.getLong("pending_chat_id", 0L) != 0L &&
                prefs.getLong("pending_user_id", 0L) != 0L;
    }

    public synchronized void clearAll() {
        prefs.edit().clear().commit();
    }

    private SecretKey key() throws Exception {
        KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
        ks.load(null);
        if (ks.containsAlias(ALIAS)) {
            return ((KeyStore.SecretKeyEntry) ks.getEntry(ALIAS, null)).getSecretKey();
        }
        KeyGenerator kg = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        kg.init(new KeyGenParameterSpec.Builder(ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build());
        return kg.generateKey();
    }
}
