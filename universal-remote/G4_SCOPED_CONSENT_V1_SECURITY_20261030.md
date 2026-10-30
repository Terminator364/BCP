# BCP Universal Remote — G4 permissions de session bornées (30 octobre 2026)

## Intention et contrainte utilisateur
L'utilisateur ne doit pas approuver chaque lecture ni chaque création bénigne. La preuve d'approbation humaine Windows pour un fichier test est déjà validée. Une nouvelle permission de session sera demandée **une fois** pour une portée déterminée, puis pourra autoriser une série de créations limitées.

## Moteur ajouté (aucun téléchargement APK requis)
Fichiers Windows dans `%LOCALAPPDATA%\BCP-Universal-Remote` :
- `g4_scoped_sessions.py` : permissions temporaires HMAC, portée et quotas, validation des chemins, journal, révocation.
- `g4_agent.py` : action de préparation `grant_session` signée uniquement par la **confirmation Windows locale** existante, puis `session_use`, `session_status`, `session_revoke`.
- `g2_tls_bridge.py` : accès aux nouvelles routes depuis le canal G2 existant, authentifié par HMAC + horodatage + nonce anti-rejeu.
- `g4_approval_center.py` : précise le dossier, durée, quota, catégories; présente les autorisations actives et permet leur révocation.

## Limites strictes d'une autorisation groupée
- Durée au plus **30 minutes**, nombre au plus **20 opérations**, octets cumulés au plus **65 536**, fichier texte au plus **8 192 octets**.
- Dossier existant **précis** situé sous le profil utilisateur Windows avec au moins deux niveaux de profondeur; pas de profil complet, pas de racine du disque; interdictions de répertoires privés et secrets existantes.
- Création de nouveaux dossiers (`mkdir`) ou nouveaux fichiers `.txt/.md/.csv` uniquement. Écriture atomique par `open('xb')` pour refuser les remplacements existants.
- **Aucune exécution de commande, suppression, écrasement, installation, élévation administrateur ou changement système** par permission groupée. Ces opérations restent sous autorisations exactes spécifiques et droits Windows/UAC.
- Chaque demande comporte un identifiant unique, une permission HMAC persistante, un quota consommé de façon exclusive par verrou interprocessus; révocation possible et expiration automatique.
- Un verrou laissé par crash met en échec les demandes suivantes (fail-closed) plutôt que d'autoriser une opération involontaire.

## Tests réalisés — LABORATOIRE isolé
- `g4_scoped_session_unit_test.py`: **27 contrôles réussis**, **1 non exécuté** (création d'un lien symbolique impossible sans droit Windows).
- `g4_scoped_integration_test.py`: **15 contrôles réussis** (l'approbation a été synthétique, limitée aux fichiers temporaires du laboratoire; aucune nouvelle approbation humaine réelle ni permission réelle persistante).
- `g4_scoped_hmac_staging_test.py`: **17 contrôles réussis** avec HTTPS + HMAC + anti-rejeu, approbation synthétique isolée, vérification des quotas et révocations, maintien de G2.
- `g4_core_security_test.py`: **17/17** et `g4_additional_security_test.py`: **13/13**, mécanisme existant préservé.
- Total sans doublon apparent : 89 réussites sur les suites nommées, avec 1 contrôle de lien symbolique non exécuté. Ces bancs ne prouvent **pas** encore l'approbation humaine d'une permission de session ni son usage depuis l'application Samsung.

## Décisions de livraison
- Ne pas toucher à la version Android v1.1.1 validée sur l'appareil. Les fonctions G4 supplémentaires peuvent être développées côté Windows, sans APK à chaque changement.
- Avant production, vérifier qu'aucune mutation distante ne passe sans approbation puis valider par le canal Tailscale HTTPS; conserver une sauvegarde des sources précédentes pour restauration.
- La migration vers une interface Android G4 demande un futur essai de mise à jour de l'APK distinct, non urgent et par le mécanisme automatique existant.
- La liaison ChatGPT native (G5) n'est pas automatiquement fournie par ces fichiers; l'outil connecté Desktop Commander est actuellement la voie réelle d'intervention sur MBMPC.

## Limites résiduelles
Le contrôle d'un changement local malveillant et simultané des jonctions NTFS entre validation du chemin et écriture n'est pas entièrement prouvé. Les droits Windows restent essentiels. Le premier essai réel d'une **autorisation groupée approuvée humainement** reste à faire; il ne doit pas être simulé ni auto-approuvé en production.
