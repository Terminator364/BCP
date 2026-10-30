package com.blessing.rescuebridge;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.io.BufferedWriter;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.Inet4Address;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Locale;
import org.json.JSONObject;

/** Android is a temporary USB-only listener; Windows initiates the connection OUTBOUND.
 * This avoids Windows Defender's default inbound firewall blocking the companion.
 * The first HELLO is only a physical-link probe; signed RPC is mandatory for access.
 */
public final class UsbReverseLink {
    private UsbReverseLink() {}
    public static final int PORT=8768;
    public static final class Result {
        public final String ip;
        public final JSONObject response;
        public final boolean paired;
        public Result(String ip,JSONObject r,boolean p){this.ip=ip;this.response=r;this.paired=p;}
    }
    public static Result await(Inet4Address phoneUsbAddress,String key,String endpoint,int listenMillis)throws Exception{
        if(!endpoint.matches("/(status|diagnostics)"))throw new IllegalArgumentException("Action interdite");
        try(ServerSocket server=new ServerSocket()){
            server.setReuseAddress(true);
            server.bind(new InetSocketAddress(phoneUsbAddress,PORT),1);
            server.setSoTimeout(listenMillis);
            try(Socket pc=server.accept()){
                pc.setSoTimeout(5500);
                String pcAddress=pc.getInetAddress().getHostAddress();
                if(!UsbDiscoveryProtocol.sameSubnet24(phoneUsbAddress.getHostAddress(),pcAddress))throw new SecurityException("PC hors liaison USB");
                BufferedReader reader=new BufferedReader(new InputStreamReader(pc.getInputStream(),StandardCharsets.UTF_8));
                String hello=reader.readLine();
                if(!"BCP_USB_RESCUE_PC_HELLO/1".equals(hello))throw new SecurityException("Service inconnu");
                if(key==null || !key.matches("[0-9a-fA-F]{64}"))return new Result(pcAddress,null,false);
                String nonce=nonce();String ts=String.valueOf(System.currentTimeMillis()/1000);
                byte[] body="{}".getBytes(StandardCharsets.UTF_8);
                String uri="/v1"+endpoint;
                JSONObject request=new JSONObject();
                request.put("endpoint",uri);request.put("nonce",nonce);request.put("timestamp",ts);
                request.put("body","{}");
                request.put("signature",BridgeProtocol.signRequest(key,"POST",uri,ts,nonce,body));
                BufferedWriter out=new BufferedWriter(new OutputStreamWriter(pc.getOutputStream(),StandardCharsets.UTF_8));
                out.write(request.toString());out.write("\n");out.flush();
                // A max-sized reply MUST NOT be accepted; status/diagnostics are bounded.
                String line=readBoundedLine(reader,8192);
                JSONObject wrapped=new JSONObject(line);
                int status=wrapped.getInt("status");
                String json=wrapped.getString("body"),signature=wrapped.getString("signature");
                byte[] raw=json.getBytes(StandardCharsets.UTF_8);
                String expected=BridgeProtocol.signResponse(key,nonce,status,raw);
                if(!BridgeProtocol.constantTimeHexEquals(expected,signature))throw new SecurityException("Signature de réponse invalide");
                return new Result(pcAddress,new JSONObject(json),true);
            }
        }
    }
    private static String nonce(){
        byte[] bytes=new byte[16];new SecureRandom().nextBytes(bytes);
        StringBuilder out=new StringBuilder(32);
        for(byte b:bytes)out.append(String.format(Locale.ROOT,"%02x",b&255));
        return out.toString();
    }
    private static String readBoundedLine(BufferedReader reader,int max)throws Exception{
        StringBuilder out=new StringBuilder();int c;
        while((c=reader.read())!=-1 && c!='\n'){
            if(out.length()>=max)throw new IllegalStateException("Réponse trop longue");
            out.append((char)c);
        }
        if(c==-1)throw new IllegalStateException("Réponse absente");
        return out.toString();
    }
}
