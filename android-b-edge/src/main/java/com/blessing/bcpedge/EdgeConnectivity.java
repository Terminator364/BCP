package com.blessing.bcpedge;

import android.app.admin.DevicePolicyManager;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothManager;
import android.content.Context;
import android.content.pm.PackageManager;
import android.hardware.usb.UsbManager;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;

import org.json.JSONArray;
import org.json.JSONObject;

public final class EdgeConnectivity {
    private EdgeConnectivity() {}

    public static JSONObject snapshot(Context context) {
        JSONObject out = new JSONObject();
        try {
            Context app = context.getApplicationContext();
            ConnectivityManager cm = app.getSystemService(ConnectivityManager.class);
            Network active = cm == null ? null : cm.getActiveNetwork();
            NetworkCapabilities caps = active == null || cm == null ? null : cm.getNetworkCapabilities(active);
            JSONArray transports = new JSONArray();
            if (caps != null) {
                if (caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) transports.put("WIFI");
                if (caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) transports.put("CELLULAR");
                if (caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)) transports.put("ETHERNET");
                if (caps.hasTransport(NetworkCapabilities.TRANSPORT_BLUETOOTH)) transports.put("BLUETOOTH");
                if (caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN)) transports.put("VPN");
            }
            out.put("transports", transports);
            out.put("internet", caps != null && caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET));
            out.put("validated", caps != null && caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED));
            out.put("metered", cm != null && cm.isActiveNetworkMetered());

            PackageManager pm = app.getPackageManager();
            out.put("wifi_direct_supported", pm.hasSystemFeature(PackageManager.FEATURE_WIFI_DIRECT));
            out.put("bluetooth_le_supported", pm.hasSystemFeature(PackageManager.FEATURE_BLUETOOTH_LE));
            out.put("usb_host_supported", pm.hasSystemFeature(PackageManager.FEATURE_USB_HOST));
            out.put("companion_device_setup_supported",
                    pm.hasSystemFeature(PackageManager.FEATURE_COMPANION_DEVICE_SETUP));

            BluetoothManager bm = app.getSystemService(BluetoothManager.class);
            BluetoothAdapter ba = bm == null ? null : bm.getAdapter();
            out.put("bluetooth_enabled", ba != null && ba.isEnabled());

            UsbManager um = app.getSystemService(UsbManager.class);
            out.put("usb_device_count", um == null ? 0 : um.getDeviceList().size());

            DevicePolicyManager dpm = app.getSystemService(DevicePolicyManager.class);
            out.put("device_owner", dpm != null && dpm.isDeviceOwnerApp(app.getPackageName()));
            out.put("dedicated_mode_ready",
                    dpm != null && dpm.isDeviceOwnerApp(app.getPackageName()));
        } catch (Exception e) {
            try { out.put("error", e.getClass().getSimpleName()); } catch (Exception ignored) {}
        }
        return out;
    }
}
