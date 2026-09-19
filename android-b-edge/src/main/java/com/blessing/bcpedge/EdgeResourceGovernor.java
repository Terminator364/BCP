package com.blessing.bcpedge;

import android.app.ActivityManager;
import android.content.Context;
import android.net.ConnectivityManager;
import android.net.NetworkCapabilities;
import android.os.BatteryManager;
import android.os.Build;
import android.os.PowerManager;
import org.json.JSONObject;

public final class EdgeResourceGovernor {
    private EdgeResourceGovernor(){}

    public static JSONObject snapshot(Context context){
        JSONObject out=new JSONObject();
        try{
            BatteryManager bm=(BatteryManager)context.getSystemService(Context.BATTERY_SERVICE);
            PowerManager pm=(PowerManager)context.getSystemService(Context.POWER_SERVICE);
            ActivityManager am=(ActivityManager)context.getSystemService(Context.ACTIVITY_SERVICE);
            ConnectivityManager cm=(ConnectivityManager)context.getSystemService(Context.CONNECTIVITY_SERVICE);
            int battery=bm==null?-1:bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY);
            boolean charging=bm!=null && bm.isCharging();
            boolean powerSave=pm!=null && pm.isPowerSaveMode();
            int thermal=Build.VERSION.SDK_INT>=29 && pm!=null ? pm.getCurrentThermalStatus() : -1;
            ActivityManager.MemoryInfo mi=new ActivityManager.MemoryInfo();
            if(am!=null) am.getMemoryInfo(mi);
            boolean lowMemory=am!=null && mi.lowMemory;
            boolean metered=cm!=null && cm.isActiveNetworkMetered();
            boolean connected=false;
            if(cm!=null){
                NetworkCapabilities nc=cm.getNetworkCapabilities(cm.getActiveNetwork());
                connected=nc!=null && nc.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET);
            }
            out.put("battery_pct",battery);
            out.put("charging",charging);
            out.put("power_save",powerSave);
            out.put("thermal_status",thermal);
            out.put("low_memory",lowMemory);
            out.put("avail_mem_bytes",mi.availMem);
            out.put("network_metered",metered);
            out.put("network_connected",connected);
        }catch(Exception ignored){}
        return out;
    }

    public static boolean shouldDefer(String resourceClass, JSONObject s){
        if("EDGE_R0".equals(resourceClass)) return false;
        boolean low=s.optBoolean("low_memory",false);
        boolean power=s.optBoolean("power_save",false);
        int battery=s.optInt("battery_pct",-1);
        int thermal=s.optInt("thermal_status",-1);
        boolean hot=thermal>=0 && thermal>=PowerManager.THERMAL_STATUS_SEVERE;
        if("EDGE_R2".equals(resourceClass))
            return low || power || hot || (battery>=0 && battery<25 && !s.optBoolean("charging",false));
        if("REMOTE_AI".equals(resourceClass))
            return !s.optBoolean("network_connected",false) || power || (battery>=0 && battery<15 && !s.optBoolean("charging",false));
        return low || hot;
    }
}
