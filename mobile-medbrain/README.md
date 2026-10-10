# MedBrain Personnel — Installation côte à côte v0.3.1

Cette version utilise l'identifiant Android `com.blessing.medbrain.personal` et le titre `MedBrain Personnel` afin de **ne pas remplacer ni désinstaller** la MedBrain 0.2 installée (`com.blessing.medbrain`).

Après validation CI, le binaire est signé avec une clé de publication personnelle stable conservée hors du dépôt public. La sortie brute de GitHub (`app-debug.apk`) n'est PAS celle à installer. Seul le binaire resigné et authentifié sera distribué via ChatGPT Delivery.

L'application neuve possède sa propre base SQLite, donc **les données 0.2 restent dans la 0.2**. Aucune fonction de transfert n'a été certifiée à ce stade ; garder l'ancienne application installée. Première connexion au second compte Drive via Android est une autorisation utilisateur requise. L'accès OAuth intégral / récurrent au compte Drive n'est pas encore implémenté.

Surveillez en priorité la navigation haute adaptée aux barres Android 16, l'import GGUF par Worker, l'exploration des dossiers sans plafond total et le rapport Diagnostic. Aucune fonction médicale autonome n'est certifiée.
