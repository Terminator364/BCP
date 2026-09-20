package com.blessing.bcpedge;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.nio.charset.StandardCharsets;
import java.security.KeyStore;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

public final class CredentialStore {
    private static final String ALIAS = "bcp-edge-evergreen-v1";
    private static final String PREFS = "bcp_credentials";
    private static final String TOKEN_BLOB = "token_blob";
    private static final String NEXUS_TOKEN_BLOB = "nexus_token_blob";
    private final SharedPreferences prefs;

    public CredentialStore(Context context) {
        prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public synchronized void putToken(String token) throws Exception {
        putSecret(TOKEN_BLOB, token);
    }

    public synchronized String getToken() {
        return getSecret(TOKEN_BLOB);
    }

    public synchronized void putNexusToken(String token) throws Exception {
        putSecret(NEXUS_TOKEN_BLOB, token);
    }

    public synchronized String getNexusToken() {
        return getSecret(NEXUS_TOKEN_BLOB);
    }

    public synchronized void clear() {
        prefs.edit().remove(TOKEN_BLOB).remove(NEXUS_TOKEN_BLOB).commit();
    }

    private void putSecret(String slot, String token) throws Exception {
        if (token == null || token.isEmpty()) throw new IllegalArgumentException("EMPTY_TOKEN");
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key());
        byte[] iv = cipher.getIV();
        byte[] ct = cipher.doFinal(token.getBytes(StandardCharsets.UTF_8));
        byte[] blob = new byte[1 + iv.length + ct.length];
        blob[0] = (byte)iv.length;
        System.arraycopy(iv,0,blob,1,iv.length);
        System.arraycopy(ct,0,blob,1+iv.length,ct.length);
        prefs.edit().putString(slot, Base64.encodeToString(blob, Base64.NO_WRAP)).commit();
    }

    private String getSecret(String slot) {
        try {
            String encoded = prefs.getString(slot, "");
            if (encoded == null || encoded.isEmpty()) return "";
            byte[] blob = Base64.decode(encoded, Base64.NO_WRAP);
            if (blob.length < 14) return "";
            int ivLen = blob[0] & 0xff;
            if (ivLen < 12 || ivLen > 16 || blob.length <= 1 + ivLen) return "";
            byte[] iv = new byte[ivLen];
            byte[] ct = new byte[blob.length - 1 - ivLen];
            System.arraycopy(blob,1,iv,0,ivLen);
            System.arraycopy(blob,1+ivLen,ct,0,ct.length);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(128, iv));
            return new String(cipher.doFinal(ct), StandardCharsets.UTF_8);
        } catch (Exception ignored) {
            return "";
        }
    }

    private SecretKey key() throws Exception {
        KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
        ks.load(null);
        if (ks.containsAlias(ALIAS)) {
            return ((KeyStore.SecretKeyEntry)ks.getEntry(ALIAS, null)).getSecretKey();
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
