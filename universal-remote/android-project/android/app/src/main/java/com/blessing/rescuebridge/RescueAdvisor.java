package com.blessing.rescuebridge;

import java.util.Locale;

/** Plain-Java user-facing diagnostics, testable without an Android device. */
public final class RescueAdvisor {
    private RescueAdvisor() {}

    public static String problem(String code) {
        if (code == null) return "État inconnu : réessaie le diagnostic.";
        switch (code.toUpperCase(Locale.ROOT)) {
            case "CONFIGURATION_MISSING": return "Adresse du PC absente. Ouvre Réglages, puis utilise l’adresse indiquée par DIAGNOSTIC.cmd sur Windows.";
            case "PAIRING_REQUIRED": return "Appairage manquant. Récupère la clé avec SHOW-PAIRING-KEY.cmd sur ton propre PC et enregistre-la dans Réglages.";
            case "USB_UNAVAILABLE": return "Branche un câble compatible données. Sur Android, active le partage de connexion USB ; le seul mode Transfert de fichiers ne suffit pas.";
            case "PC_ASLEEP": return "Le PC est en veille ou éteint. Réveille Windows, puis relance le diagnostic.";
            case "AGENT_UNAVAILABLE": return "La liaison réseau ne répond pas. Vérifie que le PC est allumé, que le partage USB est actif et que l’agent Windows est lancé.";
            case "USB_FIREWALL_POSSIBLE": return "Windows ne répond pas à la connexion. Vérifie USB-READINESS.cmd sur le PC ; si nécessaire, autorise FIX-USB-FIREWALL.cmd uniquement pour le réseau USB.";
            case "BAD_ADDRESS": return "Adresse du PC incorrecte. Lis l’IPv4 USB actuelle dans USB-READINESS.cmd puis corrige Réglages.";
            case "TIMEOUT": return "Délai dépassé. Vérifie le câble, le partage USB, l’adresse Windows et l’agent avant de réessayer.";
            case "AUTH_FAILED": return "Vérification de sécurité refusée. Contrôle l’appairage et la clé : aucune opération Windows n’a été acceptée.";
            case "LINK_VERIFIED": return "Agent Windows accessible et réponse signée vérifiée. Cette preuve concerne la commande testée, pas le contrôle complet du bureau.";
            default: return "Diagnostic : " + code.replaceAll("[^A-Za-z0-9_ -]", "");
        }
    }

    public static String codeForException(String name) {
        if (name == null) return "AGENT_UNAVAILABLE";
        if (name.contains("ConnectException") || name.contains("NoRoute")) return "USB_FIREWALL_POSSIBLE";
        if (name.contains("UnknownHost") || name.contains("MalformedURL")) return "BAD_ADDRESS";
        if (name.contains("Timeout") || name.contains("SocketTimeout")) return "TIMEOUT";
        if (name.contains("Security") || name.contains("Signature")) return "AUTH_FAILED";
        return "AGENT_UNAVAILABLE";
    }
}
