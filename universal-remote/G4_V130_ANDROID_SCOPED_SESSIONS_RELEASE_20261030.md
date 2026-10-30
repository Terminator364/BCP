# BCP Universal Remote — G4 session groupée + Android v1.3.0 (30 octobre 2026)

## État canonique de livraison
- Branche : `feat/universal-remote-transport-20261030`.
- Source serveur G4 : commit `ee9271a`. Source Android v1.3.0 : commit `5eccade`.
- Android CI : run `41113429385`, `build-apk` **success**. Une exécution séparée du workflow historique `windows-bootstrap-validation.yml` a signalé `failure` avec 0 job : sujet distinct à examiner, ne pas le présenter comme un succès.
- APK : package `com.blessing.rescuebridge`, **versionCode 17**, versionName `1.3.0-g4-scoped-session`.
- Fichier signé sur MBMPC : `%LOCALAPPDATA%\BCP-Universal-Remote\G2-v130-build\BCP-Universal-v1.3.0-SIGNED.apk` ; **66 295 octets**.
- SHA-256 vérifié : `f9784884dbca80c85a11968af8e6b0febb98e7b6a95fe98fc080221cd1c4fde1`.
- Signature : certificat identique à R3.3/v1.1.1, selon vérification locale du signataire.
- Canal stable unique : `/updates/stable.json` → version 17, et `/updates/stable.apk` → fichier correspondant, SHA et longueur vérifiés après téléchargement HTTPS/TLS1.3 privé.
- Ancienne stable v1.1.1 (version 15) sauvegardée dans `backups/G4_V130_STABLE_PREVIOUS`, manifest et APK validés. Version 16 non publiée.
- Aucune APK installée automatiquement sur le vrai Samsung n'a été observée lors de cette livraison : dernier rapport Android réel `version_code=15` à 20h10 heure Kinshasa. Le client doit ouvrir BCP ou bénéficier d'un JobScheduler Android pour détecter la stable v1.3.

## Fonctionnement de la permission groupée
- Actions G4 en lecture seule : déjà accessibles depuis une session Android appairée, sans confirmation répétée.
- Créations réversibles limitées : une demande pour un dossier exact sous le profil Windows, et **approbation réelle Windows obligatoire**.
- Après approbation : au maximum 30 min, 20 opérations, 65 536 octets de texte cumulés et 8 192 octets par nouveau fichier.
- Types automatiques autorisés : création de dossier, nouveau fichier `.txt/.md/.csv`. Refus de suppression, exécution de commandes, installation, modification de fichiers existants et accès à la racine du profil/disque.
- Toute demande passe par TLS+HMAC, horodatage et nonce anti-rejeu; quota scellé et verrou exclusif, action journalisée. Révocation possible.
- Interface Android v1.3 : demande de session, attente et contrôle automatiques de l'approbation Windows, état/quota, création de dossier/nouveau fichier, révocation. Pas de mission JSON.
- Bureau MBMPC : `BCP - Autorisations G4.lnk` ouvre le centre Windows pour approbation explicite et révocation. Le raccourci ne signe aucune approbation de lui-même.

## Résultats des bancs
- Autorisations bornées unitaires : **27 PASS**, **1 non exécuté** (création réelle de symlink/jonction Windows refusée par le système).
- Intégration G4 locale : **15 PASS**.
- G2 HTTPS/HMAC G4 en staging isolé : **17 PASS**.
- Régression de sécurité historique G4 : **17 + 13 = 30 PASS**.
- Nouvelle API G4 sur production, incluant Tailscale TLS1.3 et refus d'opérations sans grant : **23 PASS**, aucune mutation.
- Client Android Java contre serveur réel : lecture signée OK, cinq endpoints G4 protégés rejetés en l'absence d'autorisation, endpoint de commit arbitraire absent.
- Android CI Gradle + AAPT release : PASS; archive APK, classes.dex, manifeste, empreinte CI : PASS.
- Après publication v1.3 : manifeste/versionCode17, APK SHA, TLS, G4 sécurité et statut G2 HMAC : PASS.
- `private-state/g4/grants` : **0 grant actif** au dernier contrôle. Le banc d'approbation groupée réel depuis le Samsung est encore à faire.

## Contrôles de sécurité et limites non closes
- Ne jamais dire que l'installation v1.3, la création d'un fichier depuis Samsung ou l'approbation humaine d'un grant de session sont déjà validées : seuls les bancs et le canal de publication sont vérifiés.
- Le test de création d'un lien symbolique NTFS et le scénario d'une jonction changée localement simultanément à une écriture ne sont pas entièrement démontrés. Les ACL Windows et l'interdiction de parcours reparse restent obligatoires.
- L'approbation Windows demeure nécessaire **une fois par portée de session**; elle n'est pas remplacée par un droit admin implicite.
- Les opérations Windows sensibles et l'élévation UAC restent soumises aux autorisations spécifiques et à Windows.
- Une connexion ChatGPT vers l'agent BCP sans passer par le connecteur Desktop Commander (G5 natif) n'est **pas encore opérationnelle**. Ne pas exposer les routes privées sur Internet public.

## Prochaine preuve terrain sans réinstaller manuellement
1. Le Samsung appairé ouvre BCP (v1.1.1) et laisse le mécanisme de mise à jour récupérer v1.3.0 ; Android peut demander la confirmation système de sécurité.
2. Vérifier `state/g2-phone-status.json` pour le vrai `version_code=17`.
3. Dans l'onglet Fichiers Android v1.3, choisir le dossier G4 et demander une permission de 30 min.
4. L'utilisateur approuve **une fois** sur MBMPC via `BCP - Autorisations G4`; le téléphone surveille l'état du ticket.
5. Depuis le Samsung, créer deux fichiers/dossiers nouveaux dans la portée sans nouvelle confirmation Windows ; vérifier le journal, la limite et la révocation. Ensuite poursuivre G5.
