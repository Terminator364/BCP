package com.blessing.rescuebridge;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.InterfaceAddress;
import java.net.NetworkInterface;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Enumeration;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.Callable;
import java.util.concurrent.CompletionService;
import java.util.concurrent.ExecutorCompletionService;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

/** One-tap discovery bound to Android USB tether interface; never scans Wi-Fi/mobile data.
 * A positive discovery only proves a public health endpoint, not device pairing.
 */
public final class UsbAutoDiscovery {
    private UsbAutoDiscovery() {}
    public static final class Found {
        public final String ip,source,method;
        public final int port;
        Found(String ip,int port,String source,String method){this.ip=ip;this.port=port;this.source=source;this.method=method;}
    }
    private static final class UsbLink {
        final Inet4Address local,broadcast;
        final String name;
        UsbLink(Inet4Address a,Inet4Address b,String n){local=a;broadcast=b;name=n;}
    }
    public static Inet4Address usbAddress() throws Exception {
        List<UsbLink> links=usbLinks();
        if(links.isEmpty())throw new IllegalStateException("USB_TETHER_NOT_FOUND");
        return links.get(0).local;
    }
    public static Found discover() throws Exception {
        List<UsbLink> links=usbLinks();
        if(links.isEmpty())throw new IllegalStateException("USB_TETHER_NOT_FOUND");
        for(UsbLink link:links){
            Found result=udpDiscover(link);
            if(result!=null)return result;
        }
        // Bounded /24 TCP fallback for tether USB only, capped to 4 seconds.
        for(UsbLink link:links){
            Found result=scanUsbSubnet(link);
            if(result!=null)return result;
        }
        throw new IllegalStateException("USB_PC_NOT_FOUND");
    }
    private static List<UsbLink> usbLinks()throws Exception{
        List<UsbLink> links=new ArrayList<>();
        Enumeration<NetworkInterface> all=NetworkInterface.getNetworkInterfaces();
        if(all==null)return links;
        for(NetworkInterface iface:Collections.list(all)){
            if(!iface.isUp()||iface.isLoopback())continue;
            String name=iface.getName().toLowerCase(Locale.ROOT);
            // Android often calls the tether interface rndis0 or usb0. Never use wlan/rmnet.
            if(!(name.contains("rndis")||name.contains("usb")||name.contains("ncm")||name.contains("tether")))continue;
            for(InterfaceAddress ia:iface.getInterfaceAddresses()){
                if(!(ia.getAddress()instanceof Inet4Address))continue;
                Inet4Address local=(Inet4Address)ia.getAddress();
                if(!UsbDiscoveryProtocol.isPrivateIpv4(local.getHostAddress()))continue;
                // Some Android firmwares omit broadcast metadata for USB tethering.
                // Keep the interface for reverse TCP; UDP discovery is optional.
                InetAddress broadcast=ia.getBroadcast();
                Inet4Address usbBroadcast=broadcast instanceof Inet4Address
                    ? (Inet4Address)broadcast : null;
                links.add(new UsbLink(local,usbBroadcast,name));
                if(links.size()>=2)return links;
            }
        }
        return links;
    }
    private static String nonce(){
        byte[] n=new byte[16];new SecureRandom().nextBytes(n);
        StringBuilder b=new StringBuilder(32);
        for(byte x:n)b.append(String.format(Locale.ROOT,"%02x",x&255));
        return b.toString();
    }
    private static Found udpDiscover(UsbLink link){
        if(link.broadcast==null)return null;
        String nonce=nonce();
        byte[] request=UsbDiscoveryProtocol.request(nonce).getBytes(StandardCharsets.US_ASCII);
        try(DatagramSocket sock=new DatagramSocket(new InetSocketAddress(link.local,0))){
            sock.setBroadcast(true);
            sock.setSoTimeout(350);
            DatagramPacket outgoing=new DatagramPacket(request,request.length,link.broadcast,UsbDiscoveryProtocol.PORT);
            for(int attempt=0;attempt<3;attempt++){
                sock.send(outgoing);
                for(int replies=0;replies<3;replies++){
                    byte[] data=new byte[140];DatagramPacket incoming=new DatagramPacket(data,data.length);
                    try{sock.receive(incoming);}catch(java.net.SocketTimeoutException e){break;}
                    String ip=incoming.getAddress().getHostAddress();
                    if(!UsbDiscoveryProtocol.sameSubnet24(link.local.getHostAddress(),ip))continue;
                    int port=UsbDiscoveryProtocol.parseResponse(new String(data,0,incoming.getLength(),StandardCharsets.US_ASCII),nonce);
                    if(port==UsbDiscoveryProtocol.AGENT_PORT && verifiesHealth(link.local,ip,port))return new Found(ip,port,link.name,"Annonce USB");
                }
            }
        }catch(Exception ignored){/* UDP restricted by device; fallback follows */}
        return null;
    }
    private static boolean verifiesHealth(Inet4Address local,String ip,int port){
        try(Socket s=new Socket()){
            s.bind(new InetSocketAddress(local,0));
            s.connect(new InetSocketAddress(ip,port),400);
            s.setSoTimeout(700);
            OutputStream out=s.getOutputStream();
            out.write("GET /health HTTP/1.0\r\nHost: usb-rescue\r\n\r\n".getBytes(StandardCharsets.US_ASCII));out.flush();
            InputStream in=s.getInputStream();ByteArrayOutputStream b=new ByteArrayOutputStream();
            byte[] buf=new byte[512];int n;
            while(b.size()<2400&&(n=in.read(buf))>0)b.write(buf,0,Math.min(n,2400-b.size()));
            String response=new String(b.toByteArray(),StandardCharsets.UTF_8);
            return response.startsWith("HTTP/1.") && response.contains(" 200 ")
                && response.contains("\"service\":\"BCP-USB-RESCUE\"") && response.contains("\"protocol\":1");
        }catch(Exception ignored){return false;}
    }
    private static Found scanUsbSubnet(UsbLink link){
        String local=link.local.getHostAddress();
        String[] parts=local.split("\\.");
        String prefix=parts[0]+"."+parts[1]+"."+parts[2]+".";
        ExecutorService pool=Executors.newFixedThreadPool(12);
        CompletionService<Found> completion=new ExecutorCompletionService<>(pool);
        int submitted=0;
        try{
            for(int i=1;i<=254;i++){
                final String candidate=prefix+i;
                if(candidate.equals(local))continue;
                completion.submit(()->verifiesHealth(link.local,candidate,UsbDiscoveryProtocol.AGENT_PORT)
                    ?new Found(candidate,UsbDiscoveryProtocol.AGENT_PORT,link.name,"Recherche locale USB"):null);
                submitted++;
            }
            long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(5);
            for(int i=0;i<submitted;i++){
                long remaining=deadline-System.nanoTime();if(remaining<=0)break;
                Future<Found> f=completion.poll(remaining,TimeUnit.NANOSECONDS);if(f==null)break;
                try {Found r=f.get();if(r!=null)return r;}catch(Exception ignored){}
            }
        }catch(Exception ignored){}
        finally{pool.shutdownNow();}
        return null;
    }
}
