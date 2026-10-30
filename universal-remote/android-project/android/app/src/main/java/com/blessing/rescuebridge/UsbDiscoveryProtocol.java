package com.blessing.rescuebridge;

import java.util.Locale;

/** Small pure-Java, deliberately unauthenticated discovery protocol.
 * Never grants file/mission access; only the existing HMAC challenge may do so.
 */
public final class UsbDiscoveryProtocol {
    public static final int PORT=8767;
    public static final int AGENT_PORT=8876;
    public static final String REQUEST="BCP_USB_RESCUE_DISCOVER/1";
    public static final String RESPONSE="BCP_USB_RESCUE_HERE/1";
    private UsbDiscoveryProtocol() {}

    public static String request(String nonce) {
        if (!validNonce(nonce)) throw new IllegalArgumentException("Invalid discovery nonce");
        return REQUEST+" "+nonce;
    }
    public static int parseResponse(String message,String nonce) {
        if (!validNonce(nonce) || message==null || message.length()>128) return -1;
        String[] parts=message.trim().split(" ");
        if (parts.length!=3 || !RESPONSE.equals(parts[0]) || !nonce.equals(parts[1])) return -1;
        if (!parts[2].matches("[0-9]{1,5}"))return -1;
        try { int port=Integer.parseInt(parts[2]);return port==AGENT_PORT?port:-1; }
        catch(NumberFormatException e){return -1;}
    }
    public static boolean validNonce(String nonce){return nonce!=null && nonce.matches("[0-9a-f]{32}");}
    public static boolean isPrivateIpv4(String ip){
        if(ip==null||!ip.matches("[0-9]{1,3}(\\.[0-9]{1,3}){3}"))return false;
        String[] p=ip.split("\\.");int[] n=new int[4];
        try{for(int i=0;i<4;i++){n[i]=Integer.parseInt(p[i]);if(n[i]>255)return false;}}catch(Exception e){return false;}
        return n[0]==10||(n[0]==172&&n[1]>=16&&n[1]<=31)||(n[0]==192&&n[1]==168);
    }
    public static boolean sameSubnet24(String a,String b){
        if(!isPrivateIpv4(a)||!isPrivateIpv4(b))return false;
        String[] x=a.split("\\."),y=b.split("\\.");
        return x[0].equals(y[0])&&x[1].equals(y[1])&&x[2].equals(y[2]);
    }
}
