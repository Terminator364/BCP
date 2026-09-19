package com.blessing.bcpedge;

import android.content.Context;
import android.net.nsd.NsdManager;
import android.net.nsd.NsdServiceInfo;

import java.net.InetAddress;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

public final class NsdDiscovery {
    private static final String TYPE="_bcp._tcp.";
    private NsdDiscovery(){}

    public static String discover(Context context,long timeoutMs){
        NsdManager manager=(NsdManager)context.getSystemService(Context.NSD_SERVICE);
        if(manager==null) return "";
        CountDownLatch latch=new CountDownLatch(1);
        String[] result=new String[]{""};
        AtomicBoolean resolving=new AtomicBoolean(false);
        NsdManager.DiscoveryListener listener=new NsdManager.DiscoveryListener(){
            @Override public void onDiscoveryStarted(String serviceType){}
            @Override public void onStartDiscoveryFailed(String serviceType,int errorCode){latch.countDown();}
            @Override public void onStopDiscoveryFailed(String serviceType,int errorCode){}
            @Override public void onDiscoveryStopped(String serviceType){}
            @Override public void onServiceLost(NsdServiceInfo serviceInfo){}
            @Override public void onServiceFound(NsdServiceInfo serviceInfo){
                if(serviceInfo==null || !serviceInfo.getServiceType().contains("_bcp._tcp")) return;
                if(!resolving.compareAndSet(false,true)) return;
                manager.resolveService(serviceInfo,new NsdManager.ResolveListener(){
                    @Override public void onResolveFailed(NsdServiceInfo serviceInfo,int errorCode){
                        resolving.set(false);
                    }
                    @Override public void onServiceResolved(NsdServiceInfo resolved){
                        try{
                            InetAddress host=resolved.getHost();
                            int port=resolved.getPort();
                            if(host!=null && port>0){
                                result[0]="http://"+host.getHostAddress()+":"+port;
                                latch.countDown();
                            }
                        }finally{ resolving.set(false); }
                    }
                });
            }
        };
        try{
            manager.discoverServices(TYPE,NsdManager.PROTOCOL_DNS_SD,listener);
            latch.await(Math.max(400L,timeoutMs),TimeUnit.MILLISECONDS);
        }catch(Exception ignored){
        }finally{
            try{manager.stopServiceDiscovery(listener);}catch(Exception ignored){}
        }
        return result[0];
    }
}
