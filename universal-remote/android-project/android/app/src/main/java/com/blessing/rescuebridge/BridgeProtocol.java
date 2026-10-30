package com.blessing.rescuebridge;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.util.Locale;

/** Pure-Java HMAC protocol. No Android dependency: JVM client/Windows interoperability testable. */
public final class BridgeProtocol {
    private BridgeProtocol() {}

    public static String sha256(byte[] body) throws Exception {
        byte[] h=MessageDigest.getInstance("SHA-256").digest(body);
        return hex(h);
    }
    private static String hex(byte[] bytes) {
        StringBuilder b=new StringBuilder(bytes.length*2);
        for (byte v:bytes) b.append(String.format(Locale.ROOT,"%02x",v&255));
        return b.toString();
    }
    public static String hmac(String key, String message) throws Exception {
        if (key==null || key.length()<32) throw new IllegalArgumentException("Pairing secret must contain >=32 characters");
        Mac mac=Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(key.getBytes(StandardCharsets.UTF_8),"HmacSHA256"));
        return hex(mac.doFinal(message.getBytes(StandardCharsets.UTF_8)));
    }
    public static String signRequest(String key,String method,String path,String timestamp,String nonce,byte[] body) throws Exception {
        return hmac(key,method+"\n"+path+"\n"+timestamp+"\n"+nonce+"\n"+sha256(body));
    }
    public static String signResponse(String key,String nonce,int status,byte[] body) throws Exception {
        return hmac(key,nonce+"\n"+status+"\n"+sha256(body));
    }
    public static boolean constantTimeHexEquals(String a,String b) {
        if (a==null||b==null) return false;
        return MessageDigest.isEqual(a.getBytes(StandardCharsets.US_ASCII),b.getBytes(StandardCharsets.US_ASCII));
    }
    public static String escapeJson(String raw) {
        if (raw==null) return "null";
        StringBuilder b=new StringBuilder("\"");
        for(char c:raw.toCharArray()) {
            switch(c) {
                case '"': b.append("\\\""); break;
                case '\\': b.append("\\\\"); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                case '\t': b.append("\\t"); break;
                default: if(c<0x20) b.append(String.format(Locale.ROOT,"\\u%04x",(int)c)); else b.append(c);
            }
        }
        return b.append('"').toString();
    }
}
