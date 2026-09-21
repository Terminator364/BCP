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

public final class TelegramCredentialStore {
    private static final String ALIAS = "bcp-edge-telegram-v1";
    private static final String PREFS = "bcp_edge_telegram_credentials";
    private static final String BLOB = "telegram_blob";
    private final SharedPreferences prefs;

    public TelegramCredentialStore(Context context) {
        prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public synchronized void put(String token, long chatId) throws Exception {
        if (token == null || !token.matches("^\\d{6,12}:[A-Za-z0-9_-]{20,}$")) {
            throw new IllegalArgumentException("TELEGRAM_TOKEN_FORMAT_INVALID");
        }
        if (chatId == 0L) throw new IllegalArgumentException("TELEGRAM_CHAT_ID_INVALID");
        JSONObject payload = new JSONObject();
        payload.put("token", token);
        payload.put("chat_id", chatId);

        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key());
        byte[] iv = cipher.getIV();
        byte[] ct = cipher.doFinal(payload.toString().getBytes(StandardCharsets.UTF_8));
        byte[] blob = new byte[1 + iv.length + ct.length];
        blob[0] = (byte) iv.length;
        System.arraycopy(iv, 0, blob, 1, iv.length);
        System.arraycopy(ct, 0, blob, 1 + iv.length, ct.length);
        prefs.edit().putString(BLOB, Base64.encodeToString(blob, Base64.NO_WRAP)).commit();
    }

    public synchronized String getToken() {
        JSONObject p = read();
        return p.optString("token", "");
    }

    public synchronized long getChatId() {
        JSONObject p = read();
        return p.optLong("chat_id", 0L);
    }

    public synchronized boolean configured() {
        return !getToken().isEmpty() && getChatId() != 0L;
    }

    public synchronized void clear() {
        prefs.edit().remove(BLOB).commit();
    }

    private JSONObject read() {
        try {
            String encoded = prefs.getString(BLOB, "");
            if (encoded == null || encoded.isEmpty()) return new JSONObject();
            byte[] blob = Base64.decode(encoded, Base64.NO_WRAP);
            if (blob.length < 14) return new JSONObject();
            int ivLen = blob[0] & 0xff;
            if (ivLen < 12 || ivLen > 16 || blob.length <= 1 + ivLen) return new JSONObject();
            byte[] iv = new byte[ivLen];
            byte[] ct = new byte[blob.length - 1 - ivLen];
            System.arraycopy(blob, 1, iv, 0, ivLen);
            System.arraycopy(blob, 1 + ivLen, ct, 0, ct.length);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(128, iv));
            return new JSONObject(new String(cipher.doFinal(ct), StandardCharsets.UTF_8));
        } catch (Exception ignored) {
            return new JSONObject();
        }
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
