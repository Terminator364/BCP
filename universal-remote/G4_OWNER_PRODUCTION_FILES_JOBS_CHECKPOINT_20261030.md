# BCP Universal Remote — G4 full-Windows owner-gated core / checkpoint 2026-10-30

## Architecture canonique
BCP vise un plan de contrôle du PC personnel **plus autonome que Desktop Commander**, pas un outil limité à un dossier de test, 30 minutes ou 20 opérations. Les ACL du compte Windows, UAC, la connexion cryptographique et les autorisations propriétaires restent l'autorité. Les tailles de paquet (64 KiB) et les pages (100–128 éléments) protègent le réseau et les 4 Go RAM : **elles ne limitent pas le nombre d'opérations ou la taille totale des fichiers**.

## Déploiement effectué sur MBMPC — confirmé
- G2 historique, Tailscale HTTPS/HMAC, appairage et mise à jour Android v1.3.0 maintenus.
- Modules `g4_owner_gateway.py`, `g4_owner_trust.py`, `g4_universal_inventory.py` et routes authentifiées :
  - `POST /v1/g4/owner/status`
  - `POST /v1/g4/universal/inventory`
- Actions d'inventaire en lecture : `system.volumes`, `files.stat`, `files.list`, `files.read_chunk`, `files.digest`, `processes.list`, `desktop.windows`. Lecture sur les lecteurs accessibles au compte Windows, sauf fichiers de clés et secrets de l'agent.
- Source commit initial `4595d9b`, correction initialisation et CI commit `da5404f`.
- Déploiement initial : timeout d'initialisation → **retour arrière automatique confirmé**, G2 conservé.
- Correctif : initialisation de G4 dans un thread séparé, G2 continue à fonctionner durant les opérations ACL et publie `state/g4-startup-state.json`.
- Second déploiement : **PASS**, initialisation READY, **16/16 contrôles de production**, commande HTTPS/HMAC via Tailscale TLS 1.3 PASS, appairage préservé PASS.
- Aucune confiance propriétaire n'a été activée silencieusement, aucune mutation Windows réalisée pendant les tests de production.
- Raccourci permanent sur Bureau MBMPC : `BCP - Profil proprietaire.lnk`, interface locale d'enrôlement unique et de révocation. **Ne pas activer l'autorisation administrative à distance avant l'identité individualisée de chaque téléphone.**
- Limitation existante : l'ancienne version d'appairage distribue une clé de connexion partagée; le nouveau modèle propriétaire l'utilise temporairement pour identifier le canal, pas encore chaque appareil individuel. Migration par appareil nécessaire avant ouverture du shell complet.

## Nouveaux moteurs locaux (non exposés aux téléphones)
1. `g4_full_files.py` : transfert de fichier complet par blocs à l'emplacement de destination, reprise après redémarrage, SHA-256, remplacement avec sauvegarde, quarantaine réversible et restauration. Écritures limitées par permissions Windows et consentement du futur pont, **pas par un dossier fixe ni un nombre total de requêtes**. Chaque modification est journalisée et les remplacements utilisent la même partition pour un renommage atomique. `g4_full_files_test.py` **23/23 PASS** après contre-audit.
2. `g4_durable_jobs.py` : file durable SQLite pour tâches et dépendances, pagination, annulation et reprise des demandes non exécutées, classification `INTERRUPTED` après crash sans rejouer involontairement. La file n'a pas de plafond artificiel de nombre de tâches; le parallélisme sera gouverné par la RAM et la charge du PC. `g4_durable_jobs_queue_test.py` **14/14 PASS** sur métadonnées. **Lancement de véritables commandes, annulation d'un processus en cours et supervision après redémarrage Windows NON encore prouvés.**
3. Le nouveau moteur de fichiers et la file de tâches **ne sont pas des routes exposées dans G2** à cette étape. Toute capacité d'écriture/commande distante doit rester derrière une vraie identité cryptographique distincte pour le téléphone et un profil propriétaire local approuvé.

## Suite logique à exécuter
A. Unique credential par appareil Android (sans réappairage laborieux), rotation/révocation indépendante, signature des requêtes liées à cette identité, stockage Android Keystore.
B. Relier le moteur de fichiers au canal G4 avec consentement propriétaire durable et vérifications Windows ACL/UAC, auditer la suppression vers quarantaine et restaurations.
C. Valider de vraies tâches persistantes et commandes Windows dans un laboratoire autorisé, tester déconnexion/reprise/coupure électrique.
D. Ajouter bureau distant et entrée clavier/souris, services, installation, automatisation de séquences et journal.
E. Interface mobile unifiée sans missions JSON, mise à jour automatique conservée.
F. Vrai connecteur de contrôle natif ChatGPT G5; ne pas le confondre avec la seule APK.

## Preuves non encore acquises
- Profil propriétaire réel **non activé** sur MBMPC; les routes d'inventaire général refusent donc les requêtes non approuvées.
- Aucun test de shell complet depuis le Samsung, aucune élévation UAC, aucune autorisation « administrateur total » confirmée.
- Les exercices de fichiers sont des tests sur répertoires temporaires, pas des opérations sur documents personnels.
- Le workflow ancien `windows-bootstrap-validation.yml` signale séparément des échecs sans jobs; le workflow G4 Owner CI dédié avait un problème de création de dossier sous un runner neuf et a été corrigé dans `da5404f`, statut CI à reconfirmer.

## Continuité
`BCP|UNIVERSAL|OWNER-TRUST|FULL-WINDOWS|G4-G5|20261030`

**Ne pas réintroduire le bridage 30 min / 20 opérations / dossier unique comme architecture canonique.**
