# BCP UNIVERSAL REMOTE — Correction d'architecture : moteur intégral, confiance durable
Date : 30 octobre 2026 — MBMPC / Samsung

## Décision canonique, à ne plus contredire
Le système BCP Universal Remote **n'est pas une application de création de notes dans un dossier limité**. Sa cible est un plan de contrôle Windows personnel, pilotable par un appareil appairé et ultérieurement directement depuis ChatGPT, avec des fonctionnalités comparables ou plus riches que Desktop Commander.

Les limites du prototype (dossier G4-Staging-Workspace, 30 minutes, 20 opérations, 8 KiB par fichier) étaient des paramètres expérimentaux de sécurité pour un petit sous-module. **Elles ne sont pas des restrictions de capacité du moteur**. Les garder uniquement comme profil « essai limité » facultatif, à supprimer comme chemin principal de la roadmap.

## Capacité visée (distincte de la sécurité et du transport)
- Tout volume Windows accessible au compte opérateur : inspection, navigation, recherche, lecture/écriture/renommage/déplacement/copie, opérations en lot, sauvegarde et récupération.
- Shell et logiciels : PowerShell, CMD, Python, scripts, installations et exécution contrôlée, sorties consultables, processus persistants et logs.
- Interface Windows : capture, fenêtres, clavier, souris, presse-papiers et automatisation graphique (à construire, sous session Windows autorisée).
- Administration : services, planificateur, configurations, logiciels et diagnostics réseau, avec droits réels Windows et UAC. Aucune élévation secrète.
- Orchestration : tâches enchaînées, dépendances, reprise après panne, contrôle d'avancement, rollback quand applicable, journal vérifiable, garde-fous et isolation des effets.
- Transports : priorité Wi-Fi local sans Internet, Tailscale privé à distance, USB et Bluetooth en secours; aucune activation automatique du partage de données mobiles.
- Réception et mises à jour Android sans réinstaller manuellement; moteur Windows pouvant évoluer sans nouvel APK à chaque fois.
- ChatGPT G5 : une véritable action connectée, pas une promesse fondée sur la seule APK.

## Architecture corrigée
1. **BCP CORE / ABILITIES** : outils Windows généraux sans restrictions arbitraires à des dossiers précis. Le compte Windows et ses ACL définissent les ressources accessibles.
2. **BCP OWNER TRUST** : identité d'appareil appairé, profil propriétaire local signé HMAC, confiance durable jusqu'à révocation; pas d'expiration imposée, pas de quota de nombre d'opérations, pas de portée dossier imposée. Profil observateur possible pour appareils secondaires.
3. **CONSENT CONTROL** : consentement explicite à l'activation du profil propriétaire dans Windows; politique de confirmation des opérations très sensibles configurable. Le choix d'un fonctionnement sans prompts répétitifs ne contourne pas UAC, l'authentification ou les permissions OS.
4. **TRANSPORT** : protocole G2 TLS et HMAC actuel conservé jusqu'à remplacement audité; per-transport buffers/quotas de taille de réponse sont techniques, **pas des limites de taille totale du fichier**.
5. **JOBS + UI + CHATGPT** : exécution asynchrone, séquençage, écran, rappels et connecteur ChatGPT. Modules encore à construire, ne pas déclarer terminés.
6. **ROLLBACK** : chaque ajout testé séparément, retour arrière possible, ne pas endommager G2 ou une installation Android qui fonctionne.

## Preuves au 30/10
- Android réel : `version_code=17` à `2026-10-30T19:40:06Z`, réseau `cellular`, app visible et à jour. **v1.3.0 installée** et télémétrie G2 vérifiée sur MBMPC.
- Nouveau module `g4_owner_trust.py` : **22/22 tests**, test `g4_owner_trust_test.py`. Durable (expiry:null), sans quota (operation_limit:null), sans restriction dossier (path_scope:null), intégrité HMAC, profils observateur/opérateur, révocation; aucun profil propriétaire réel créé.
- Nouveau module `g4_universal_inventory.py` : identification réelle de **4 volumes**, **6 fenêtres** et 100 processus dans une page. Test synthétique **245 entrées** parcourues sur deux pages et binaire de **410 000 octets** relu intégralement en **7 blocs** avec intégrité vérifiée. Les limites 128 entrées/page et 64 KiB par réponse sont exclusivement des protections RAM/réseau, pas de total.
- L'agent G4 actif reste celui du précédent déploiement, avec les anciens modules d'autorisation temporaire; les nouveaux modules ne sont **pas encore exposés dans le G2 en production**. Pas de nouvelle APK publiée.
- Une limite historique du lecteur G4 à 256 KiB et 100 items existe encore dans l'ancien agent. La nouvelle bibliothèque corrige ce modèle mais son câblage et ses tests de bout en bout restent à réaliser.
- La clé G2 actuelle peut être partagée par le mécanisme d'appairage; la segmentation par appareil et les révocations individuelles requièrent une évolution d'identité, à tester avant activation propriétaire distante.
- Aucun privilège administrateur Windows supplémentaire n'a été accordé, aucune autorisation durable réelle n'a été activée.

## Priorités suivantes non négociables
A. Brancher l'inventaire à un endpoint G4 authentifié et paginé, sans limite totale, tester grands volumes et gros fichiers.
B. Renforcer identité unique de chaque téléphone / rotation de clés et réaliser une approbation propriétaire **unique** sur Windows, révocable.
C. Ajouter toutes les mutations de fichiers, shell/journal/jobs, écran/entrée, services/installation; appliquer l'autorité du compte Windows, les permissions et l'audit.
D. Instrumenter un système de QA : tests unitaires, API, simultanéité, sécurité, vrais appareils et reprise; ne pas décréter un stade fini sur de seules simulations.
E. Relier les capacités au Samsung puis construire un vrai connecteur ChatGPT G5.
F. Maintenir en permanence le cahier mère GitHub et la stabilité du canal de mise à jour stable unique.

## Code de continuité
`BCP|UNIVERSAL|OWNER-TRUST|FULL-WINDOWS|G4-G5|20261030`
