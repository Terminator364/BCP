# MedBrain 0.4.5 — réparation des goulets mémoire et inférence (10 octobre 2026)

Observations du téléphone (journal du 10/10) : 491 livres ; 1534 pages indexées sur 13200 dénombrées ; requêtes RESUME × 483 répétées ; OutOfMemoryError dans l'application Android limitée à 256 Mio de tas Java ; plusieurs accès Drive SAF perdus (Cello error 2) ; une génération hors délai de 120 s ; Qwen3 affichant du raisonnement anglais et 5,7 tokens/s.

## Modifications sans perte des données existantes
- Cache GGUF dans le processus :inference tant que l'écran de discussion/étude reste connecté, mutex d'accès et arrêt isolé en cas d'inférence bloquée.
- Demande explicite /no_think pour Qwen3, budget 144 tokens (chat) et jusqu'à 230 (prompts longs), filtrage prudent des sorties contenant uniquement des pensées.
- File AI bornée à 2, pour que le cours guidé ne refuse plus automatiquement quand Chat travaille.
- Découverte de dossiers : enregistrement SQLite seulement, puis petit lot de lancement à la fin du parcours.
- Import multiple : ne crée plus un worker par document sur le champ.
- Reprise : max 2 jobs par action. Maintenance périodique : max 2. Enchaînement d'un nouveau livre uniquement après que l'autre est INDEXED.
- Allocation de jobs round-robin, pauses avant OCR lorsque l'inférence est active.
- Etats NEEDS_ACCESS exclus des reprises ; nouvelle autorisation du fournisseur Android nécessaire.
- Identité com.blessing.medbrain.personal, schéma SQLite 4 et versionCode 39 conservés. Aucun APK signé fourni par ce commit.

## Contre-audit
Le modèle local ne peut pas répondre instantanément à 5,7 tokens/s. La mesure sur téléphone reste nécessaire. Les anciennes 483 tâches WorkManager déjà en attente dans la version installée peuvent subsister après mise à jour; les correctifs empêchent de créer de nouvelles vagues mais ne prouvent pas l'annulation rétrospective de l'ancienne file.
L'affichage final est borné et les pensées explicites sont masquées, mais aucun test neuronal réel de Qwen avec le wrapper Android n'est encore certifié.
Les exceptions fournisseur ne sont pas des preuves de livres supprimés.

## Suite — réparation de l'ancienne file et pédagogie offline-first
- Worker unique de migration: annule progressivement les anciens work names learn-ID (24 par tranche, checkpoint persistant), sans supprimer les documents, pages, dialogues, modèle ou tâche de téléchargement GGUF.
- Les nouvelles acquisitions sont suspendues durant cette migration et reprennent ensuite à hauteur de deux travaux.
- Étudier fournit immédiatement jusqu'à 4 références indexées et paginées, même avant la synthèse locale. La synthèse rapide reste distincte des preuves.
- Budget de sortie de fiche: 230 tokens au maximum (modèle local lent), sans le présenter comme un cours exhaustif.
- Modèle: restauration d'un ancien fichier brain.previous ou model-download.previous si et seulement si brain.gguf est absent et le backup porte l'en-tête GGUF.
- Les nouveaux tests et la qualification CI restent nécessaires; performances réelles non garanties avant essai sur Galaxy.

## Candidate de livraison 0.4.6 (non signée)
- Identité inchangée: com.blessing.medbrain.personal ; versionCode 40 (strictement >39) ; versionName 0.4.6-personal-rc.
- Ancien raisonnement sauvegardé reste présent dans SQLite mais n'est plus réinjecté dans le contexte du modèle.
- Pendant le Chat, les titres et pages sources pertinents apparaissent immédiatement avant la synthèse.
- Le moteur de bibliothèque dev.ffmpegkit-maintained:llama-android:0.1.1 open source gratuit ne fournit ni streaming natif des tokens ni GPU Vulkan. Le meilleur rendu de fluidité absolue impose une autre voie JNI/backend, non certifiée dans cette release.
- AUCUN BINAIRE NON SIGNÉ OU SIGNÉ AVEC UNE NOUVELLE CLÉ NE DOIT ÊTRE INSTALLÉ EN PLACE DE 0.4.5. Le gate signature stable et Galaxy S21 FE reste ouvert.
