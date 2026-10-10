# MedBrain 0.4.6 — terrain: conversation et mémoire (2026-10-10)

Diagnostic réel: Galaxy S21 FE Android 16, 491 livres, 3171 / 17016 pages analysées, 3117 indexées, Qwen GGUF 1223 MiB SHA d2387ca2..., batterie 7%, 1925 MiB RAM disponible. Deux INFERENCE_TIMEOUT à 95 s, prompts 4788 et 4736 caractères. Capture « donc ? » entraîne faux passages anticoagulants; « continue au point 4 » entraîne faux passages tissus mous/acidose.

Cause confirmée dans MainActivity: FTS exécuté avant détection des relances, contexte 8 messages + 4 sources 850 caractères, 144 tokens, timeout 95 sec. Il s'agit d'un RAG partiel sur 18,3% des pages dénombrées; aucun entraînement des poids du réseau neuronal. Les anciens OOM de 256 MiB ne sont pas attribués automatiquement à l'APK 0.4.6.

Correction: routeur dialogue qui exclut relances du FTS, reprend dernière réponse utile sans anciens timeouts, prompts courts <=1350 char, sources <=2x330 char, cooldown 5 min après timeout, génération suspendue si batterie <=14%, réponse de repli explicite et jamais présentée comme synthèse neuronale. Tests de régression sur les formulations utilisateur exactes.

Limite: cette correction source ne certifie ni latence réelle sur Galaxy, ni qualité clinique, ni streaming. Conservation intégrale SQLite schema 4, GGUF et signature; pas de publication APK à ce stade.