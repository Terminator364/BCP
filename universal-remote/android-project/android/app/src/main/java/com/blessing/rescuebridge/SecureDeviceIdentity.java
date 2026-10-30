package com.blessing.rescuebridge;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.security.SecureRandom;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import org.json.JSONObject;

/** A separate owner-capable device credential. G2's historical shared key is never sufficient. */
public final class SecureDeviceIdentity {
    private static final String ALIAS="bcp_g4_per_device_aes_v1";
    private static final String PREF="bcp_g4_device_identity_v1";
    private static final SecureRandom RNG=new SecureRandom();
    private SecureDeviceIdentity(){}

    public static final class Credential {
        public final String deviceId,secret;
        private Credential(String deviceId,String secret){this.deviceId=deviceId;this.secret=secret;}
    }
    private static String hex(byte[] raw){
        StringBuilder s=new StringBuilder(raw.length*2);
        for(byte b:raw)s.append(String.format(java.util.Locale.ROOT,"%02x",b&255));
        return s.toString();
    }
    private static SecretKey key() throws Exception {
        KeyStore ks=KeyStore.getInstance("AndroidKeyStore");ks.load(null);
        KeyStore.Entry e=ks.getEntry(ALIAS,null);
        if(e instanceof KeyStore.SecretKeyEntry)return ((KeyStore.SecretKeyEntry)e).getSecretKey();
        KeyGenerator gen=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
        gen.init(new KeyGenParameterSpec.Builder(ALIAS,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256).build());
        return gen.generateKey();
    }
    private static void validate(Credential c){
        if(c==null||!c.deviceId.matches("[a-f0-9]{32}")||!c.secret.matches("[a-f0-9]{64}"))
            throw new SecurityException("Invalid individual device credential");
    }
    public static synchronized Credential getOrCreate(Context ctx) throws Exception {
        SharedPreferences p=ctx.getSharedPreferences(PREF,Context.MODE_PRIVATE);
        String iv=p.getString("iv",null),encrypted=p.getString("encrypted",null);
        if(iv!=null||encrypted!=null){
            if(iv==null||encrypted==null)throw new SecurityException("Partial device credential state");
            Cipher dec=Cipher.getInstance("AES/GCM/NoPadding");
            dec.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Base64.decode(iv,Base64.NO_WRAP)));
            JSONObject j=new JSONObject(new String(dec.doFinal(Base64.decode(encrypted,Base64.NO_WRAP)),StandardCharsets.UTF_8));
            Credential c=new Credential(j.getString("id"),j.getString("secret"));
            validate(c);return c;
        }
        byte[] id=new byte[16],sec=new byte[32];RNG.nextBytes(id);RNG.nextBytes(sec);
        Credential c=new Credential(hex(id),hex(sec));
        JSONObject j=new JSONObject().put("id",c.deviceId).put("secret",c.secret);
        Cipher enc=Cipher.getInstance("AES/GCM/NoPadding");
        enc.init(Cipher.ENCRYPT_MODE,key());
        byte[] sealed=enc.doFinal(j.toString().getBytes(StandardCharsets.UTF_8));
        if(!p.edit().putString("iv",Base64.encodeToString(enc.getIV(),Base64.NO_WRAP))
                .putString("encrypted",Base64.encodeToString(sealed,Base64.NO_WRAP)).commit())
            throw new IllegalStateException("Device credential persistence failed");
        return c;
    }
}
