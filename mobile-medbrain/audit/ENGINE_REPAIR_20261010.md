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
