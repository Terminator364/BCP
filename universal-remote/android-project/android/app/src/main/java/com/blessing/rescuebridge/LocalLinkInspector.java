package com.blessing.rescuebridge;

import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.util.Collections;
import java.util.Enumeration;
import java.util.Locale;

/** Safe read-only local network hint. Never claims this proves a physical USB cable. */
public final class LocalLinkInspector {
    private LocalLinkInspector() {}
    public static String summary() {
        try {
            StringBuilder out = new StringBuilder();
            Enumeration<NetworkInterface> interfaces = NetworkInterface.getNetworkInterfaces();
            if (interfaces == null) return "Interfaces indisponibles";
            for (NetworkInterface iface : Collections.list(interfaces)) {
                if (!iface.isUp() || iface.isLoopback()) continue;
                String n=iface.getName().toLowerCase(Locale.ROOT);
                if (!(n.contains("usb") || n.contains("rndis") || n.contains("ncm") || n.contains("tether"))) continue;
                for (InetAddress ip: Collections.list(iface.getInetAddresses())) {
                    if (!(ip instanceof Inet4Address) || ip.isLoopbackAddress()) continue;
                    if (out.length()>0) out.append(" ; ");
                    out.append(iface.getName()).append(" : ").append(ip.getHostAddress());
                }
            }
            return out.length()>0?out.toString():"Aucune interface USB identifiée automatiquement (cela ne prouve pas une panne).";
        } catch (Exception e) {
            return "Lecture du réseau non disponible : " + e.getClass().getSimpleName();
        }
    }
}
