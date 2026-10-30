# BCP Universal Remote — Cahier de continuité (2026-10-30)

## Mission canonique
Permettre à ChatGPT d'administrer le PC Windows de l'utilisateur via un agent local et une passerelle Android. Capacités visées : terminal, processus, fichiers, logiciels, diagnostics et contrôle graphique. L'agent pourra disposer de privilèges administrateur après installation et authentification; ne jamais interpréter cela comme la suppression de l'authentification ou du consentement Windows.

## Transports
1. Wi-Fi LAN (prioritaire si téléphone et PC sur même réseau; Internet inutile pour les paquets locaux).
2. Tailscale (distance, deux appareils connectés; Tailscale ne constitue pas le canal ChatGPT lui-même).
3. USB (appairage initial et secours; ADB et USB tethering sont des mécanismes distincts).
4. Bluetooth (secours bas débit, à développer).
Sélection automatique, reprise après coupure, failover, journaux de livraison avec IDs pour empêcher les doubles commandes.
NE JAMAIS activer automatiquement le partage d'Internet mobile vers Windows.

## Patrimoine vérifié sur MBMPC
- Installation historique dans %LOCALAPPDATA%/BCP-USB-Rescue : Windows bridge_agent.py, sauvegardes, APK R3.3 signée, répertoire V4-LAB (ADB).
- Sources R3.3 dans %USERPROFILE%/BCP-USB-Rescue-R3_3-Staging/r33.
- BCP historique dans %LOCALAPPDATA%/BCP, plus dépôt GitHub BCP (préserver sans écrasement).
- Premier preflight indépendant et non destructif dans %LOCALAPPDATA%/BCP-Universal-Remote/scripts/BCP-Transport-Preflight.ps1.
- Premier test préflight : Wi-Fi Windows actif, Wi-Fi Android NON vérifié; Tailscale Windows absent avant installation; USB réseau et Bluetooth réseau non connectés; outils ADB présents; gardien V4 enregistré mais inactif; aucun canal Android/ChatGPT validé.
- Tailscale Android déjà installé et connecté (preuve via capture utilisateur). NE PAS enregistrer ici l'adresse IP, les secrets ni l'identifiant de connexion.
- Tentative winget : échec mise à jour source. L'installateur Windows officiel 1.104.4 a été téléchargé, signature Authenticode VALID / Tailscale Inc.; installation lancée via UAC, mais résultat final à confirmer.

## Architecture minimale
- Agent Windows = exécution locale et attestations; gestionnaire de transports séparé des capacités.
- Passerelle Android = découverte, appairage, continuité, chiffrement, routage, télémétrie.
- Passerelle ChatGPT = action connector/API explicite et disponible; le seul lancement de Tailscale ne donne aucun accès ChatGPT.
- Canal à haute confiance : TLS ou Noise/SSH avec identité d'appareil épinglée, authentification mutuelle, anti-rejeu, journal d'audit et secours. Ne pas exposer l'ancien serveur HTTP/HMAC sur Wi-Fi ou Tailscale.
- Gestion des privilèges administrateur dans le cadre Windows, sans ouvrir une interface non authentifiée vers le shell.
- Optimisation PC RAM 4 Go : un seul agent léger, connexions persistantes bornées, pas de polling intensif.

## Gates d'acceptation
G0 : héritage / environnement / sauvegardes retrouvés.
G1 : Tailscale Windows installé et connecté au même tailnet que Android, ping test.
G2 : Wi-Fi LAN PC<->Android prouvé par aller-retour authentifié chiffré.
G3 : USB et Bluetooth opérationnels sans tether Internet mobile.
G4 : agent exécute commandes étendues, transferts, captures et actions GUI avec authentification.
G5 : ChatGPT peut appeler réellement l'agent via une intégration disponible, réception des résultats.
G6 : failover automatique, tests de reprise, rollback, mesures RAM/batterie/data, QA sur appareils réels.

## Vérité de livraison
Ne jamais confondre script écrit, test unitaire, service en écoute, appareil visible, transport authentifié et contrôle ChatGPT opérationnel. Les confirmations nécessitent des preuves de bout en bout.
