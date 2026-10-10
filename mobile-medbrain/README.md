# Blessing MedBrain — Android, alpha 0.1

## Ce qui est réellement implémenté
- Application Android arm64-v8a autonome (sans connexion au PC).
- Import Android Storage Access Framework de PDF textuels et fichiers texte, y compris un document choisi dans un compte Drive visible dans le sélecteur Android.
- Extraction page par page via PdfBox-Android (pages contenant du texte sélectionnable uniquement).
- Journal de progression SQLite, ingestion en lots de 8 pages avec reprise WorkManager et absence de doublons (clé document+page).
- Recherche lexicale locale avec extraits **vraiment présents** dans les documents, titres et numéros de page.
- Import volontaire de poids GGUF dans le stockage privé de l'application.
- Réponse en français via inférence locale llama.cpp AAR + extraits de la bibliothèque, sans réseau requis pour les fichiers locaux.

## Ce qui n'est PAS fait
- Pas de parcours récursif automatique du second compte Drive (autorisation OAuth / sélection des dossiers à implémenter).
- Pas de compréhension des figures, ni d'OCR des pages scannées.
- Pas d'entraînement neuronal ou fine-tuning; « apprendre » signifie ici extraire/indexer pour retrieval-augmented generation.
- Pas de garantie de validité clinique; ne pas utiliser comme dispositif de décision.
- Pas de synchronisation TLIB / BCP active : seulement architecture séparée, avant intégration contractuelle.
- Pas d'auto-exécution continue chaque minute; WorkManager peut différer les travaux.
- Pas de suppression de photos ou action PC.
- Bibliothèque et modèles non inclus dans l'APK (données privées / taille).

## Compilation reproductible
```bash
cd mobile-medbrain
gradle :app:assembleDebug --no-daemon
```
Le pipeline GitHub fournit un artefact APK debug si et seulement si la compilation aboutit. Ne pas déclarer d'APK livré sans preuve du workflow et de l'artefact.

## Premier gate humain
1. Installer l'APK debug quand il est compilé et vérifié.
2. Dans l'app, choisir un PDF depuis le sélecteur Android (Drive ou stockage).
3. Choisir le fichier GGUF Qwen3-1.7B existant si disponible sur l'appareil.
Les identifiants Google et tokens ne doivent jamais être placés dans GitHub.

## Limitations opérationnelles
Le premier traitement PDF est textuel; les passages qui sont des images doivent être marqués non traités, pas proclamés assimilés.
Sur des documents volumineux, PdfBox peut consommer beaucoup de mémoire lors de l'ouverture, malgré le traitement par lots. La qualification sur Galaxy S21 FE est obligatoire.
Utiliser branche isolée, aucun remplacement de B-EDGE; publication et intégration BCP bloquées jusqu'aux preuves terrain.
