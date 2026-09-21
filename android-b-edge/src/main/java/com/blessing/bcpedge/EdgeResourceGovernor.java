package com.blessing.bcpedge;

import android.app.ActivityManager;
import android.content.Context;
import android.net.ConnectivityManager;
import android.net.NetworkCapabilities;
import android.os.BatteryManager;
import android.os.Build;
import android.os.PowerManager;
import android.os.StatFs;
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
            boolean networkPresent=false;
            boolean internetCapable=false;
            boolean internetValidated=false;
            if(cm!=null){
                NetworkCapabilities nc=cm.getNetworkCapabilities(cm.getActiveNetwork());
                networkPresent=nc!=null;
                internetCapable=nc!=null && nc.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET);
                internetValidated=internetCapable
                        && nc.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED);
            }
            out.put("battery_pct",battery);
            out.put("charging",charging);
            out.put("power_save",powerSave);
            out.put("thermal_status",thermal);
            out.put("low_memory",lowMemory);
            long totalMem=Math.max(1L,mi.totalMem);
            long availMem=Math.max(0L,mi.availMem);
            int memoryLoad=(int)Math.max(0L,Math.min(100L,100L-((availMem*100L)/totalMem)));
            StatFs fs=new StatFs(context.getFilesDir().getAbsolutePath());
            long storageTotal=Math.max(1L,fs.getTotalBytes());
            long storageFree=Math.max(0L,fs.getAvailableBytes());
            long storageReserve=Math.max(512L*1024L*1024L,storageTotal/20L);
            boolean storagePressure=storageFree<storageReserve;
            out.put("avail_mem_bytes",availMem);
            out.put("total_mem_bytes",totalMem);
            out.put("memory_load_percent",memoryLoad);
            out.put("storage_free_bytes",storageFree);
            out.put("storage_total_bytes",storageTotal);
            out.put("storage_reserve_bytes",storageReserve);
            out.put("storage_pressure",storagePressure);
            out.put("network_metered",metered);
            out.put("network_present",networkPresent);
            out.put("network_connected",networkPresent);
            out.put("internet_capable",internetCapable);
            out.put("internet_validated",internetValidated);
        }catch(Exception ignored){}
        return out;
    }

    public static boolean shouldDefer(String resourceClass, JSONObject s){
        return shouldDeferSignals(
                resourceClass,
                s.optBoolean("low_memory",false),
                s.optInt("memory_load_percent",0),
                s.optBoolean("storage_pressure",false),
                s.optBoolean("power_save",false),
                s.optInt("battery_pct",-1),
                s.optBoolean("charging",false),
                s.optInt("thermal_status",-1),
                s.optBoolean("internet_validated",false));
    }

    // Pure deterministic admission function so the safety policy is testable
    // without an Android runtime/JSONObject implementation.
    public static boolean shouldDeferSignals(
            String resourceClass,
            boolean lowMemory,
            int memoryLoadPercent,
            boolean storagePressure,
            boolean powerSave,
            int batteryPercent,
            boolean charging,
            int thermalStatus,
            boolean internetValidated) {
        if ("EDGE_R0".equals(resourceClass)) return false;
        boolean low = lowMemory || memoryLoadPercent >= 92;
        boolean hot = thermalStatus >= 0
                && thermalStatus >= PowerManager.THERMAL_STATUS_SEVERE;
        if ("PC_R3".equals(resourceClass)) return false;
        if ("EDGE_R2".equals(resourceClass))
            return low || storagePressure || powerSave || hot
                    || (batteryPercent >= 0 && batteryPercent < 25 && !charging);
        if ("REMOTE_AI".equals(resourceClass))
            return storagePressure || !internetValidated || powerSave || hot
                    || (batteryPercent >= 0 && batteryPercent < 15 && !charging);
        return low || storagePressure || hot;
    }
}
