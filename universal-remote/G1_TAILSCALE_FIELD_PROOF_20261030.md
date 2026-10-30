# BCP Universal Remote — Gate G1, preuve terrain

Date : 2026-10-30.

## État vérifié sur MBMPC
- Tailscale Windows 1.104.4 installé ; service Windows opérationnel.
- Authentification de MBMPC sur le même tailnet que le Samsung, confirmée par le résultat de la commande `tailscale status --json`.
- PC : `100.109.148.51` ; Samsung : `100.119.168.75`.
- Statut de l'agent Tailscale : `Running`.
- Samsung `MBM S21 Fe` : pair identifié et `Online = true`.
- Test réel : `tailscale ping 100.119.168.75` a renvoyé `pong`, via une adresse LAN privée ; latence observée 211 ms.

**Conclusion : G1 PASS (association Tailscale + échange réseau).**

## Ce que G1 ne prouve PAS
- Le service BCP Android ne parle pas encore sur Tailscale/LAN.
- Le canal ChatGPT -> Android -> Windows n'est pas encore en service.
- La connexion par USB/Bluetooth n'est pas validée.
- Le ping via LAN n'est pas un test de débits applicatifs ni de résistance à des coupures.

## Prochaines étapes
G2 : identifier le transport local le plus économique, canal applicatif authentifié/chiffré, retour de requête et résultat, sans partage de 4G. Réutiliser les sources R3.3 et V4-LAB, sans effacer les clés ni les signatures existantes.
G3 : voies USB/ADB et Bluetooth de secours.
G4/G5 : capacités Windows complètes et canal natif ChatGPT prouvés de bout en bout.
