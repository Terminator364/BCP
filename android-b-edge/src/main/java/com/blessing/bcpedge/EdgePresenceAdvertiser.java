package com.blessing.bcpedge;

import android.Manifest;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothManager;
import android.bluetooth.le.AdvertiseCallback;
import android.bluetooth.le.AdvertiseData;
import android.bluetooth.le.AdvertiseSettings;
import android.bluetooth.le.BluetoothLeAdvertiser;
import android.content.Context;
import android.content.pm.PackageManager;
import android.net.nsd.NsdManager;
import android.net.nsd.NsdServiceInfo;
import android.net.wifi.p2p.WifiP2pManager;
import android.net.wifi.p2p.nsd.WifiP2pDnsSdServiceInfo;
import android.os.Build;
import android.os.Looper;
import android.os.ParcelUuid;

import org.json.JSONObject;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * Multi-transport presence plane.
 *
 * Data still flows over authenticated sockets. BLE and Wi-Fi Direct are used
 * as low-data discovery/beacon paths so the dedicated phone can remain visible
 * when the normal home-LAN topology changes.
 */
public final class EdgePresenceAdvertiser {
    public static final String NSD_TYPE = "_bcpedge._tcp.";
    public static final String BLE_SERVICE_UUID = "7bd4cfc0-4bb6-4c5d-9d32-28f2c99e8876";

    private final Context context;
    private NsdManager nsd;
    private NsdManager.RegistrationListener nsdListener;
    private BluetoothLeAdvertiser bleAdvertiser;
    private AdvertiseCallback bleCallback;
    private WifiP2pManager p2p;
    private WifiP2pManager.Channel p2pChannel;
    private WifiP2pDnsSdServiceInfo p2pService;

    public EdgePresenceAdvertiser(Context context) {
        this.context = context.getApplicationContext();
    }

    public JSONObject start(int port, String version) {
        JSONObject out = new JSONObject();
        try { out.put("nsd", startNsd(port, version)); } catch (Exception ignored) {}
        try { out.put("ble", startBle(version)); } catch (Exception ignored) {}
        try { out.put("wifi_direct", startWifiDirect(port, version)); } catch (Exception ignored) {}
        return out;
    }

    public void stop() {
        try {
            if (nsd != null && nsdListener != null) nsd.unregisterService(nsdListener);
        } catch (Exception ignored) {}
        try {
            if (bleAdvertiser != null && bleCallback != null) bleAdvertiser.stopAdvertising(bleCallback);
        } catch (Exception ignored) {}
        try {
            if (p2p != null && p2pChannel != null && p2pService != null) {
                p2p.removeLocalService(p2pChannel, p2pService, null);
            }
        } catch (Exception ignored) {}
    }

    private String startNsd(int port, String version) {
        nsd = context.getSystemService(NsdManager.class);
        if (nsd == null) return "UNAVAILABLE";
        NsdServiceInfo info = new NsdServiceInfo();
        info.setServiceName("BCP-EDGE");
        info.setServiceType(NSD_TYPE);
        info.setPort(port);
        if (Build.VERSION.SDK_INT >= 21) {
            try {
                info.setAttribute("v", version);
                info.setAttribute("role", "server");
                info.setAttribute("api", "v1");
            } catch (Exception ignored) {}
        }
        nsdListener = new NsdManager.RegistrationListener() {
            @Override public void onRegistrationFailed(NsdServiceInfo serviceInfo, int errorCode) {}
            @Override public void onUnregistrationFailed(NsdServiceInfo serviceInfo, int errorCode) {}
            @Override public void onServiceRegistered(NsdServiceInfo serviceInfo) {}
            @Override public void onServiceUnregistered(NsdServiceInfo serviceInfo) {}
        };
        nsd.registerService(info, NsdManager.PROTOCOL_DNS_SD, nsdListener);
        return "ADVERTISING";
    }

    private String startBle(String version) {
        if (Build.VERSION.SDK_INT >= 31
                && context.checkSelfPermission(Manifest.permission.BLUETOOTH_ADVERTISE)
                != PackageManager.PERMISSION_GRANTED) {
            return "PERMISSION_REQUIRED";
        }
        BluetoothManager manager = context.getSystemService(BluetoothManager.class);
        BluetoothAdapter adapter = manager == null ? null : manager.getAdapter();
        if (adapter == null || !adapter.isEnabled() || !adapter.isMultipleAdvertisementSupported()) {
            return "UNAVAILABLE";
        }
        bleAdvertiser = adapter.getBluetoothLeAdvertiser();
        if (bleAdvertiser == null) return "UNAVAILABLE";

        AdvertiseSettings settings = new AdvertiseSettings.Builder()
                .setAdvertiseMode(AdvertiseSettings.ADVERTISE_MODE_LOW_POWER)
                .setTxPowerLevel(AdvertiseSettings.ADVERTISE_TX_POWER_LOW)
                .setConnectable(false)
                .setTimeout(0)
                .build();
        AdvertiseData data = new AdvertiseData.Builder()
                .setIncludeDeviceName(false)
                .addServiceUuid(new ParcelUuid(UUID.fromString(BLE_SERVICE_UUID)))
                .build();
        bleCallback = new AdvertiseCallback() {};
        bleAdvertiser.startAdvertising(settings, data, bleCallback);
        return "ADVERTISING";
    }

    private String startWifiDirect(int port, String version) {
        if (Build.VERSION.SDK_INT >= 33
                && context.checkSelfPermission(Manifest.permission.NEARBY_WIFI_DEVICES)
                != PackageManager.PERMISSION_GRANTED) {
            return "PERMISSION_REQUIRED";
        }
        if (Build.VERSION.SDK_INT < 33
                && context.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)
                != PackageManager.PERMISSION_GRANTED) {
            return "PERMISSION_REQUIRED";
        }
        p2p = context.getSystemService(WifiP2pManager.class);
        if (p2p == null) return "UNAVAILABLE";
        p2pChannel = p2p.initialize(context, Looper.getMainLooper(), null);
        if (p2pChannel == null) return "UNAVAILABLE";

        Map<String,String> record = new HashMap<>();
        record.put("role", "bcp-edge-server");
        record.put("port", String.valueOf(port));
        record.put("version", version);
        record.put("api", "v1");
        p2pService = WifiP2pDnsSdServiceInfo.newInstance(
                "BCP-EDGE", "_bcpedge._tcp", record);
        p2p.addLocalService(p2pChannel, p2pService, new WifiP2pManager.ActionListener() {
            @Override public void onSuccess() {}
            @Override public void onFailure(int reason) {}
        });
        return "ADVERTISING";
    }
}
