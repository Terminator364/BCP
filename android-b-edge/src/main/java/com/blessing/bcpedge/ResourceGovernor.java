package com.blessing.bcpedge;

import android.app.ActivityManager;
import android.content.Context;
import android.net.ConnectivityManager;
import android.os.BatteryManager;
import android.os.Build;
import android.os.PowerManager;

import org.json.JSONObject;

public final class ResourceGovernor {
    private final Context context;

    public ResourceGovernor(Context context) {
        this.context = context.getApplicationContext();
    }

    public JSONObject snapshot() {
        JSONObject out = new JSONObject();
        try {
            ActivityManager am = (ActivityManager) context.getSystemService(Context.ACTIVITY_SERVICE);
            ActivityManager.MemoryInfo mi = new ActivityManager.MemoryInfo();
            if (am != null) am.getMemoryInfo(mi);

            BatteryManager bm = (BatteryManager) context.getSystemService(Context.BATTERY_SERVICE);
            int battery = bm == null ? -1 :
                    bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY);
            boolean charging = bm != null && Build.VERSION.SDK_INT >= 23 && bm.isCharging();

            PowerManager pm = (PowerManager) context.getSystemService(Context.POWER_SERVICE);
            boolean powerSave = pm != null && pm.isPowerSaveMode();
            int thermal = 0;
            if (pm != null && Build.VERSION.SDK_INT >= 29) thermal = pm.getCurrentThermalStatus();

            ConnectivityManager cm = (ConnectivityManager)
                    context.getSystemService(Context.CONNECTIVITY_SERVICE);
            boolean metered = cm != null && cm.isActiveNetworkMetered();

            out.put("available_bytes", mi.availMem);
            out.put("total_bytes", mi.totalMem);
            out.put("low_memory", mi.lowMemory);
            out.put("battery_pct", battery);
            out.put("charging", charging);
            out.put("power_save", powerSave);
            out.put("thermal_status", thermal);
            out.put("metered", metered);
            out.put("edge_r0_allowed", true);
            out.put("edge_r1_allowed", EdgePolicy.resourceAllowed(
                    "EDGE_R1", mi.lowMemory, powerSave, thermal, battery, charging, metered));
            out.put("edge_r2_allowed", EdgePolicy.resourceAllowed(
                    "EDGE_R2", mi.lowMemory, powerSave, thermal, battery, charging, metered));
        } catch (Exception ex) {
            try {
                out.put("degraded", true);
                out.put("edge_r0_allowed", true);
                out.put("edge_r1_allowed", false);
                out.put("edge_r2_allowed", false);
                out.put("error", ex.getClass().getSimpleName());
            } catch (Exception ignored) {}
        }
        return out;
    }

    public boolean allowed(String resourceClass) {
        JSONObject s = snapshot();
        if ("EDGE_R0".equals(resourceClass)) return true;
        if ("EDGE_R2".equals(resourceClass)) return s.optBoolean("edge_r2_allowed", false);
        return s.optBoolean("edge_r1_allowed", false);
    }
}
