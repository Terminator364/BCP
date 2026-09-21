package com.blessing.bcpedge;

import android.Manifest;
import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.PowerManager;
import android.provider.Settings;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * Runtime capability broker for the dedicated-phone server mode.
 *
 * We deliberately request only permissions that back a concrete capability:
 * notifications for the persistent server indicator; nearby Wi-Fi for Wi-Fi
 * Direct service discovery; Bluetooth permissions for low-data node discovery.
 */
public final class EdgePermissionManager {
    public static final int REQUEST_CORE_SERVER_PERMISSIONS = 2201;
    private static final String PREFS = "bcp_edge_server_mode";
    private static final String KEY_ENABLED = "enabled";

    private EdgePermissionManager() {}

    public static void setServerModeEnabled(Context context, boolean enabled) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().putBoolean(KEY_ENABLED, enabled).commit();
    }

    public static boolean isServerModeEnabled(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getBoolean(KEY_ENABLED, true);
    }

    public static String[] missingRuntimePermissions(Context context) {
        List<String> out = new ArrayList<>();
        if (Build.VERSION.SDK_INT >= 33) {
            addIfMissing(context, out, Manifest.permission.POST_NOTIFICATIONS);
            addIfMissing(context, out, Manifest.permission.NEARBY_WIFI_DEVICES);
        } else {
            addIfMissing(context, out, Manifest.permission.ACCESS_FINE_LOCATION);
        }
        if (Build.VERSION.SDK_INT >= 31) {
            addIfMissing(context, out, Manifest.permission.BLUETOOTH_SCAN);
            addIfMissing(context, out, Manifest.permission.BLUETOOTH_CONNECT);
            addIfMissing(context, out, Manifest.permission.BLUETOOTH_ADVERTISE);
        }
        return out.toArray(new String[0]);
    }

    private static void addIfMissing(Context context, List<String> out, String permission) {
        if (context.checkSelfPermission(permission) != PackageManager.PERMISSION_GRANTED) {
            out.add(permission);
        }
    }

    public static boolean hasCoreRuntimePermissions(Context context) {
        return missingRuntimePermissions(context).length == 0;
    }

    public static void requestCoreRuntimePermissions(Activity activity) {
        String[] missing = missingRuntimePermissions(activity);
        if (missing.length == 0) return;
        activity.requestPermissions(missing, REQUEST_CORE_SERVER_PERMISSIONS);
    }

    public static boolean batteryUnrestricted(Context context) {
        PowerManager pm = context.getSystemService(PowerManager.class);
        return pm != null && pm.isIgnoringBatteryOptimizations(context.getPackageName());
    }

    public static boolean requestBatteryUnrestricted(Activity activity) {
        if (batteryUnrestricted(activity)) return true;
        try {
            Intent intent = new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS);
            intent.setData(Uri.parse("package:" + activity.getPackageName()));
            activity.startActivity(intent);
            return true;
        } catch (Exception ignored) {
            try {
                activity.startActivity(new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS));
                return true;
            } catch (Exception ignoredAgain) {
                return false;
            }
        }
    }

    public static JSONObject status(Context context) {
        JSONObject out = new JSONObject();
        try {
            String[] missing = missingRuntimePermissions(context);
            JSONArray a = new JSONArray();
            for (String p : missing) a.put(p);
            out.put("server_mode_enabled", isServerModeEnabled(context));
            out.put("runtime_permissions_ready", missing.length == 0);
            out.put("missing_runtime_permissions", a);
            out.put("battery_unrestricted", batteryUnrestricted(context));
            out.put("boot_receiver_declared", true);
            out.put("foreground_server_capable", true);
            out.put("nearby_wifi_capable", Build.VERSION.SDK_INT >= 21);
            out.put("bluetooth_discovery_capable", Build.VERSION.SDK_INT >= 21);
        } catch (Exception ignored) {}
        return out;
    }
}
