package com.blessing.rescuebridge;

import org.json.JSONObject;
import java.io.*;
import java.net.URL;
import javax.net.ssl.HttpsURLConnection;

/** One-time trusted PC challenge. The secret is never entered manually or put in chat. */
public final class BCPPairClient {
    private static final String PAIR="https://mbmpc.taild48ba2.ts.net/pair/v1";
    private BCPPairClient(){}
    public static String redeem(String pin) throws Exception {
        if(pin==null || !pin.matches("[0-9]{8}"))throw new IllegalArgumentException("Code à 8 chiffres requis");
        HttpsURLConnection conn=(HttpsURLConnection)new URL(PAIR).openConnection();
        conn.setRequestMethod("POST");
        conn.setInstanceFollowRedirects(false);
        conn.setConnectTimeout(7000);
        conn.setReadTimeout(12000);
        conn.setUseCaches(false);
        conn.setDoOutput(true);
        conn.setRequestProperty("Content-Type","application/json; charset=utf-8");
        conn.setRequestProperty("Cache-Control","no-store");
        try {
            byte[] request=new JSONObject().put("code",pin).toString().getBytes(java.nio.charset.StandardCharsets.UTF_8);
            try(OutputStream out=conn.getOutputStream()){out.write(request);}
            if(conn.getResponseCode()!=200)throw new SecurityException("Code refusé ou expiré");
            ByteArrayOutputStream bytes=new ByteArrayOutputStream();
            try(InputStream in=conn.getInputStream()){
                byte[] buf=new byte[256];int n;
                while((n=in.read(buf))!=-1){
                    if(bytes.size()+n>1024)throw new SecurityException("Réponse d'appairage trop grande");
                    bytes.write(buf,0,n);
                }
            }
            JSONObject reply=new JSONObject(bytes.toString("UTF-8"));
            String key=reply.getString("key");
            if(!reply.optBoolean("ok") || !key.matches("[0-9a-fA-F]{64}"))
                throw new SecurityException("Appairage non authentifié");
            return key;
        }finally{conn.disconnect();}
    }
}
