# BCP G4 — Politique de confirmation non répétitive et premier test humain confirmé

Date: 2026-10-30, MBMPC.

## Validation du test utilisateur
Le ticket local f658bc74073587c8f3ca205c80b21e8a a été explicitement approuvé dans la fenêtre Windows et son état est devenu **DONE**. Le fichier `G4-Staging-Workspace/G4_FIELD_APPROVAL_PROOF_20261030.txt` existe et contient exactement le texte prévu. Ce fichier n'existait pas avant confirmation. Le scellement du ticket et l'écriture sont enregistrés.

## Autres tests sans intervention répétée
La suite G4 de lecture authentifiée, relancée sur **le serveur réel port 8898**, passe 10/10 : santé TLS, capacités, inventaire, processus, répertoires autorisés, refus de modification non approuvée, refus HMAC erroné, refus de clé privée, refus d'endpoint d'écriture, santé G2. **Aucune approbation supplémentaire n'a été requise pour ces consultations.**

## Politique produit décidée avec l'utilisateur
L'approbation réelle était un test unique de sécurité G4, pas un mode de travail où l'utilisateur doit cliquer pour chaque requête.

1. **Lecture/diagnostic** : exécution automatique après authentification, sans dialogue Windows à chaque fois, tant que les limites de données et les exclusions de secrets sont respectées.
2. **Opérations réversibles de faible risque** : concevoir un consentement de session local, limité par catégorie, dossier et durée (par exemple 30 minutes) afin d'éviter les demandes répétitives. Chaque action doit rester journalisée. **Non implémenté à ce stade** : ne jamais affirmer que cette permission est disponible avant audit.
3. **Opérations sensibles** (suppression massive, commandes exécutables, installation, droits administrateur, changement système) : autorisation contextuelle explicite, éventuellement par lot de commandes exactes. Respecter UAC et la session Windows, sans élévation implicite.
4. **Aucun accès superutilisateur implicite** depuis Tailscale, le téléphone ou ChatGPT. Aucun secret de paire dans un chat ou un dépôt.
5. **Pas de nouvelle APK nécessaire** pour le travail backend Windows. Maintenir BCP Android v1.1.1 et G2 stables.

## Prochain chantier
Définir puis auditer les autorisations temporaires bornées; ne pas exposer de nouvelles routes d'écriture à distance tant que l'authentification, le consentement, la limitation de portée, les journaux et la révocation ne sont pas prouvés. L'intégration directe à ChatGPT (G5) n'est pas validée.

Résultat global : consentement Windows réel prouvé; G4 lecture sur serveur actif sans validation répétée, 10/10 PASS.
