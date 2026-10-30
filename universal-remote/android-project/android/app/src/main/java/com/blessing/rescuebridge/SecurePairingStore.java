package com.blessing.rescuebridge;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** Pairing token encrypted by Android Keystore AES/GCM; never backup material. */
public final class SecurePairingStore {
    private static final String ALIAS="bcp_usb_rescue_pairing_v1";
    private static final String PREF="bcp_rescue_secure";
    private static SecretKey key() throws Exception {
        KeyStore store=KeyStore.getInstance("AndroidKeyStore");store.load(null);
        KeyStore.Entry e=store.getEntry(ALIAS,null);
        if(e instanceof KeyStore.SecretKeyEntry)return ((KeyStore.SecretKeyEntry)e).getSecretKey();
        KeyGenerator g=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
        g.init(new KeyGenParameterSpec.Builder(ALIAS,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256).build());return g.generateKey();
    }
    public static void save(Context ctx,String secret) throws Exception {
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,key());
        byte[] bytes=cipher.doFinal(secret.getBytes(java.nio.charset.StandardCharsets.UTF_8));
        SharedPreferences p=ctx.getSharedPreferences(PREF,Context.MODE_PRIVATE);
        if(!p.edit().putString("nonce",Base64.encodeToString(cipher.getIV(),Base64.NO_WRAP))
               .putString("cipher",Base64.encodeToString(bytes,Base64.NO_WRAP)).commit())
            throw new IllegalStateException("Impossible d'enregistrer la cle chiffree");
    }
    public static String load(Context ctx) throws Exception {
        SharedPreferences p=ctx.getSharedPreferences(PREF,Context.MODE_PRIVATE);
        String nonce=p.getString("nonce",null),ciphertext=p.getString("cipher",null);
        if(nonce==null || ciphertext==null)return "";
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Base64.decode(nonce,Base64.NO_WRAP)));
        return new String(cipher.doFinal(Base64.decode(ciphertext,Base64.NO_WRAP)),java.nio.charset.StandardCharsets.UTF_8);
    }
    public static void clear(Context ctx) throws Exception {
        // Forget both the encrypted token and the underlying Android Keystore key.
        // Without deleting the alias, old encrypted backups could remain decryptable.
        if(!ctx.getSharedPreferences(PREF,Context.MODE_PRIVATE).edit().clear().commit())
            throw new IllegalStateException("Effacement des donnees impossible");
        KeyStore store=KeyStore.getInstance("AndroidKeyStore");store.load(null);
        if(store.containsAlias(ALIAS))store.deleteEntry(ALIAS);
    }
}
