# BCP Universal Remote — G4 audit repris et retesté (2026-10-30)

## Environnement réel
PC MBMPC Windows. G2 servi sur IP Wi-Fi, Tailscale et loopback, port 8898. Agent G4 déjà créé sur PC dans `%LOCALAPPDATA%\BCP-Universal-Remote\g4_agent.py`; interface d'approbation `g4_approval_center.py`.

## 40 tests exécutés dans ce tour
- `g4_core_security_test.py`: **17/17 PASS**, permissions, listing, faux sceau, ticket expiré/modifié, écriture de test, audit.
- `g4_additional_security_test.py`: **13/13 PASS**, chemin absolu, refus clés privées, refus sans approbation, simulation d'approbation locale, sauvegarde, commande Windows `whoami.exe` en laboratoire, ticket expiré et altéré refusés.
- `g4_single_agent_staging_test.py`: **10/10 PASS**, TLS et HMAC, inventaire Windows/processus/fichiers, refus modifications et mauvaise signature, préservation de G2, absence de publication G4 mutation sur WAN.
- Résultat final processus: `G4_REAUDIT_TESTS=PASS`, code de sortie 0.
- Les permissions d'utilisateur étaient **simulées par le banc**, pas approuvées via interaction réelle sur le bureau. La commande `whoami.exe` était un test non destructif.

## Fonctionnalités déjà présentes
G4 HTTPS 8910 local seulement pour mises à jour: `write_text`, `mkdir`, `run` avec tickets 5 min scellés HMAC et approbation par une interface Tkinter locale; commandes sous le compte Windows courant, sans contournement UAC. Sauvegarde lors des remplacements de fichiers. Routes G4 lecture intégrées dans G2 pour capacités, système, processus, list et read fichiers, audit, avec HMAC.

## Risques et arbitrages
- Ne pas exposer de commande arbitraire sur le réseau à ce stade. La préparation et l'approbation doivent être reliées à une UX explicite et à un protocole strict.
- Les liens symboliques, redirections de chemins, le contenu de sous-processus et les changements concurrentiels entre approbation et exécution méritent des tests de sécurité supplémentaires.
- Le compte Windows et UAC restent l'autorité. Aucun droit administrateur n'est accordé par le câble ou Tailscale.
- Ne pas confondre G4 staging Windows et ChatGPT natif. Une intégration externe compatible et connectée est encore nécessaire.
- G2 Android v1.1.1 demeure la base stable; ne pas déclencher de nouvelle APK pour les travaux backend seulement.

## Prochaine validation
Démontrer une approbation humaine réelle sur MBMPC d'une action inoffensive; ensuite connecter des méthodes Android explicitement autorisées à des endpoints G4 durcis, puis effectuer une preuve via vrai téléphone. Les mutations G4 ne doivent pas devenir accessibles par défaut à toute session distante.
