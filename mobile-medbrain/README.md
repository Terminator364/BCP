# MedBrain Personnel 0.4 — chantier de refonte cognitive et UX

**Source de vérité** : la PR #187 du dépôt Terminator364/BCP, branche unique existante. Aucun écrasement de B-EDGE.

### Changements intégrés (pas encore certifiés sur le téléphone)
- Conversation persistante, bulles, salutations naturelles, 3 modes (Auto / Général / Mes sources), sources consultables sur demande et historique local SQLite v4.
- Recherche médicale plus stricte ; exclusion des occurrences non pertinentes comme « cœur fœtal » pour une question sur la taille du cœur adulte. Absence de références inventées ; aucun résultat pertinent n'est un résultat légitime.
- Paramètres interactifs : modèle, import local GGUF, téléchargement Qwen3 1.7B Q4_K_M uniquement après acceptation et sur Wi-Fi non facturé, apparence, texte, contexte et CPU, effacement confirmé de l'historique.
- Téléchargement GGUF repris par Range si possible, SHA-256 public épinglé, modèle précédent sauvegardé, WorkManager soumis à Wi-Fi non facturé et réserve de stockage. URL fixe de source Hugging Face ; 1,28 Go, non inclus dans l'APK.
- BCP reste coordinateur ; ingestion et indexation continuent indépendamment de la conversation, sous limites Android.
- La connexion Drive récursive OAuth au second compte reste à implémenter ; sélection de dossiers via Android ne signifie pas synchronisation complète d'un autre compte Drive.
- Aucun diagnostic clinique autonome. Apprentissage actuel = mémoire documentaire, non modification des poids neuronaux.

### Gates
Build/test/lint/release exact HEAD, migrations v1/v2/v3→v4, recherche, UI 6 onglets, modèle/network opt-in, signature release avec la clé MedBrain Personnel déjà établie, **sans effacer la v0.3.3**, puis tests terrain sur S21 FE.

# MedBrain Personnel — Installation côte à côte v0.3.1

Cette version utilise l'identifiant Android `com.blessing.medbrain.personal` et le titre `MedBrain Personnel` afin de **ne pas remplacer ni désinstaller** la MedBrain 0.2 installée (`com.blessing.medbrain`).

Après validation CI, le binaire est signé avec une clé de publication personnelle stable conservée hors du dépôt public. La sortie brute de GitHub (`app-debug.apk`) n'est PAS celle à installer. Seul le binaire resigné et authentifié sera distribué via ChatGPT Delivery.

L'application neuve possède sa propre base SQLite, donc **les données 0.2 restent dans la 0.2**. Aucune fonction de transfert n'a été certifiée à ce stade ; garder l'ancienne application installée. Première connexion au second compte Drive via Android est une autorisation utilisateur requise. L'accès OAuth intégral / récurrent au compte Drive n'est pas encore implémenté.

Surveillez en priorité la navigation haute adaptée aux barres Android 16, l'import GGUF par Worker, l'exploration des dossiers sans plafond total et le rapport Diagnostic. Aucune fonction médicale autonome n'est certifiée.
