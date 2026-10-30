package com.blessing.rescuebridge;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.security.cert.X509Certificate;
import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLSocketFactory;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;

/** G2 TLS+HMAC adapter. Never falls back to cleartext HTTP. No Android dependency. */
public final class G2TransportClient {
    private static final SecureRandom RANDOM = new SecureRandom();
    private final String host, sharedKey, pinnedSha256;
    private final int port;
    private final boolean pinRequired;

    public G2TransportClient(String host, int port, String key, String fingerprint) {
        if(host==null || !host.matches("[A-Za-z0-9.-]{4,253}"))
            throw new IllegalArgumentException("Invalid host");
        if((port!=443 && port<1024) || port>65535)throw new IllegalArgumentException("Invalid port");
        if(key==null || !key.matches("[0-9a-fA-F]{64}"))
            throw new IllegalArgumentException("Missing paired key");
        this.host=host; this.port=port; this.sharedKey=key;
        this.pinRequired=fingerprint!=null && !fingerprint.isEmpty();
        if(pinRequired && !fingerprint.matches("[0-9a-fA-F]{64}"))
            throw new IllegalArgumentException("Invalid certificate fingerprint");
        this.pinnedSha256=pinRequired?fingerprint.toLowerCase(java.util.Locale.ROOT):"";
        if(!pinRequired && !host.endsWith(".ts.net"))
            throw new IllegalArgumentException("Unpinned local TLS forbidden");
    }

    private static String hex(byte[] data){
        StringBuilder b=new StringBuilder(data.length*2);
        for(byte x:data) b.append(String.format(java.util.Locale.ROOT,"%02x",x & 255));
        return b.toString();
    }
    private SSLSocketFactory pinnedSockets() throws Exception {
        final String expected=pinnedSha256;
        X509TrustManager pinned=new X509TrustManager() {
            @Override public X509Certificate[] getAcceptedIssuers(){return new X509Certificate[0];}
            @Override public void checkClientTrusted(X509Certificate[] c,String a) throws java.security.cert.CertificateException{
                throw new java.security.cert.CertificateException("Client certificates unsupported");
            }
            @Override public void checkServerTrusted(X509Certificate[] chain,String auth) throws java.security.cert.CertificateException{
                if(chain==null || chain.length==0)throw new java.security.cert.CertificateException("No server cert");
                try {
                    String got=hex(MessageDigest.getInstance("SHA-256").digest(chain[0].getEncoded()));
                    if(!MessageDigest.isEqual(expected.getBytes(StandardCharsets.US_ASCII),got.getBytes(StandardCharsets.US_ASCII)))
                        throw new java.security.cert.CertificateException("Pinned identity mismatch");
                }catch(java.security.GeneralSecurityException e){
                    throw new java.security.cert.CertificateException(e);
                }
            }
        };
        SSLContext c=SSLContext.getInstance("TLS");c.init(null,new TrustManager[]{pinned},RANDOM);
        return c.getSocketFactory();
    }
    private static byte[] decodeHex(String hex) {
        byte[] raw=new byte[hex.length()/2];
        for(int i=0;i<raw.length;i++)
            raw[i]=(byte)Integer.parseInt(hex.substring(i*2,i*2+2),16);
        return raw;
    }
    public String perform(String endpoint,String json) throws Exception {
        return performInternal(endpoint,json,null,null);
    }
    public String performDevice(String endpoint,String json,String deviceId,String deviceSecret) throws Exception {
        if(deviceId==null||!deviceId.matches("[0-9a-f]{32}")||
           deviceSecret==null||!deviceSecret.matches("[0-9a-f]{64}"))
            throw new SecurityException("INDIVIDUAL_DEVICE_CREDENTIAL_INVALID");
        return performInternal(endpoint,json,deviceId,deviceSecret);
    }
    private String performInternal(String endpoint,String json,String deviceId,String deviceSecret) throws Exception {
        if(!endpoint.matches("(/v1/(status|diagnostics|audit|phone-state)|/v1/g4/(capabilities|system|processes|files/list|files/read|audit|changes/prepare|changes/status|session/use|session/status|session/revoke|device/enroll/request|owner/status|universal/inventory))"))throw new IllegalArgumentException("Endpoint G2 interdit");
        byte[] body=json.getBytes(StandardCharsets.UTF_8);
        if(body.length>131072)throw new IllegalArgumentException("Request too large");
        byte[] random=new byte[16];RANDOM.nextBytes(random);String nonce=hex(random);
        String ts=Long.toString(System.currentTimeMillis()/1000);
        HttpsURLConnection c=(HttpsURLConnection)new URL("https://"+host+":"+port+endpoint).openConnection();
        if(pinRequired){
            c.setSSLSocketFactory(pinnedSockets());
            // A matching pinned certificate is the device identity, even if LAN IP changed.
            c.setHostnameVerifier((hostname,session)->hostname.equals(host));
        }
        c.setConnectTimeout(7000);
        c.setReadTimeout(endpoint.startsWith("/v1/g4/")?30000:7000);
        c.setRequestMethod("POST");c.setDoOutput(true);
        c.setRequestProperty("Content-Type","application/json; charset=utf-8");
        c.setRequestProperty("X-Bridge-Time",ts);
        c.setRequestProperty("X-Bridge-Nonce",nonce);
        c.setRequestProperty("X-Bridge-Signature",
            BridgeProtocol.signRequest(sharedKey,"POST",endpoint,ts,nonce,body));
        if(deviceId!=null){
            String individualNonce=hex(new java.security.SecureRandom().generateSeed(16));
            String material="BCP_DEVICE_V1\n"+deviceId+"\nPOST\n"+endpoint+"\n"+ts+"\n"+
                individualNonce+"\n"+BridgeProtocol.sha256(body);
            javax.crypto.Mac mac=javax.crypto.Mac.getInstance("HmacSHA256");
            mac.init(new javax.crypto.spec.SecretKeySpec(decodeHex(deviceSecret),"HmacSHA256"));
            String individualSignature=hex(mac.doFinal(material.getBytes(StandardCharsets.US_ASCII)));
            c.setRequestProperty("X-BCP-Device",deviceId);
            c.setRequestProperty("X-BCP-Device-Time",ts);
            c.setRequestProperty("X-BCP-Device-Nonce",individualNonce);
            c.setRequestProperty("X-BCP-Device-Signature",individualSignature);
        }
        try{
            try(OutputStream o=c.getOutputStream()){o.write(body);}
            int code=c.getResponseCode();
            try(InputStream in=code<400?c.getInputStream():c.getErrorStream()){
                if(in==null)throw new IllegalStateException("Empty response");
                ByteArrayOutputStream out=new ByteArrayOutputStream();
                byte[] buf=new byte[4096];int n;
                while((n=in.read(buf))!=-1){
                    if(out.size()+n>200000)throw new IllegalArgumentException("Oversize response");
                    out.write(buf,0,n);
                }
                byte[] reply=out.toByteArray();
                if(!BridgeProtocol.constantTimeHexEquals(
                    BridgeProtocol.signResponse(sharedKey,nonce,code,reply),
                    c.getHeaderField("X-Bridge-Signature")))
                    throw new SecurityException("HMAC response mismatch");
                if(code!=200)throw new IllegalStateException("Server declined: "+code);
                return new String(reply,StandardCharsets.UTF_8);
            }
        }finally{c.disconnect();}
    }
}
