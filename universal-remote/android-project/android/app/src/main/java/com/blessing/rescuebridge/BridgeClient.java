package com.blessing.rescuebridge;

import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.InetAddress;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;

/** Android HTTP client for the bounded Windows agent over a private USB-tether subnet.
 * V0.1 uses cleartext HTTP; HMAC authenticates content but DOES NOT encrypt it.
 * Never send secrets/private documents or expose the agent to a public interface.
 */
public final class BridgeClient {
    private final String ip, key;
    private final int port;
    private final SecureRandom random=new SecureRandom();

    public BridgeClient(String ip,int port,String key) throws Exception {
        if(!isPrivateIpv4(ip)) throw new IllegalArgumentException("Adresse IPv4 privee requise (USB)");
        if(port<1024||port>65535) throw new IllegalArgumentException("Port incorrect");
        if(key==null || !key.matches("[0-9a-fA-F]{64}")) throw new IllegalArgumentException("Cle d'appairage: 64 caracteres hexadecimaux");
        this.ip=ip;this.port=port;this.key=key;
    }
    public static boolean isPrivateIpv4(String ip) {
        if(ip==null||!ip.matches("[0-9]{1,3}(\\.[0-9]{1,3}){3}")) return false;
        String[] parts=ip.split("\\.");int[] n=new int[4];
        try {for(int i=0;i<4;i++){n[i]=Integer.parseInt(parts[i]);if(n[i]>255 || (parts[i].length()>1 && parts[i].startsWith("0"))) return false;}}catch(NumberFormatException e){return false;}
        return n[0]==10 || (n[0]==172 && n[1]>=16 && n[1]<=31) || (n[0]==192 && n[1]==168);
    }
    public JSONObject perform(String endpoint,JSONObject payload) throws Exception {
        if(!endpoint.matches("/(status|diagnostics|files|read|write|audit)")) throw new IllegalArgumentException("Action interdite");
        String path="/v1"+endpoint;
        byte[] body=payload.toString().getBytes(StandardCharsets.UTF_8);
        if(body.length>128*1024) throw new IllegalArgumentException("Taille de requete excessive");
        String ts=String.valueOf(System.currentTimeMillis()/1000);
        byte[] nb=new byte[16];random.nextBytes(nb);
        StringBuilder nonceBuilder=new StringBuilder();for(byte b:nb)nonceBuilder.append(String.format(java.util.Locale.ROOT,"%02x",b&0xff));
        String nonce=nonceBuilder.toString();
        URL url=new URL("http://"+ip+":"+port+path);
        HttpURLConnection c=(HttpURLConnection)url.openConnection();
        c.setConnectTimeout(4500);c.setReadTimeout(9000);c.setRequestMethod("POST");c.setDoOutput(true);
        c.setRequestProperty("Content-Type","application/json; charset=utf-8");
        c.setRequestProperty("X-Bridge-Time",ts);
        c.setRequestProperty("X-Bridge-Nonce",nonce);
        c.setRequestProperty("X-Bridge-Signature",BridgeProtocol.signRequest(key,"POST",path,ts,nonce,body));
        try {
            try(OutputStream os=c.getOutputStream()){os.write(body);}
            int status=c.getResponseCode();
            if(status!=200 && status!=400 && status!=401) throw new IllegalStateException("HTTP "+status);
            String sig=c.getHeaderField("X-Bridge-Signature");
            try(InputStream ins=status<400?c.getInputStream():c.getErrorStream()){
                ByteArrayOutputStream output=new ByteArrayOutputStream();byte[] buf=new byte[4096];int n;
                while((n=ins.read(buf))!=-1){if(output.size()+n>200000) throw new IllegalStateException("Reponse trop grande");output.write(buf,0,n);}
                byte[] data=output.toByteArray();
                String expected=BridgeProtocol.signResponse(key,nonce,status,data);
                if(!BridgeProtocol.constantTimeHexEquals(expected,sig))throw new SecurityException("Signature reponse invalide");
                return new JSONObject(new String(data,StandardCharsets.UTF_8));
            }
        } finally {c.disconnect();}
    }
}
