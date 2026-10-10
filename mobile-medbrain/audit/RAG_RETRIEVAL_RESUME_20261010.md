# MedBrain — reprise strictement depuis le pack 2026-10-10

Autorité: MEDBRAIN_PACK_REPRISE_EXACTE_2026-10-10.zip / HEAD 5b9db03e77c9af569ff5addaa975b1fb3d3bf5a3
Portée: uniquement le client mobile-medbrain/ dans PR #187.

## Anomalie P0 constatée
Le RAG utilisait une recherche FTS4 avec disjonction des termes et `LIMIT 180`. Sur une bibliothèque à centaines de pages, des occurrences hors sujet pouvaient précéder la page pertinente puis la masquer.

## Correction soumise à vérification CI
- Recherche en trois étapes : 3 termes conjoints, 2 termes conjoints, puis OR de secours.
- Limite de candidats bornée (360 par étape), déduplication par (document,page), score clinique existant conservé et ordre déterministe.
- Test de régression avec 240 pages d'obstétrique suivies d'une page d'anatomie cardiaque adulte.
- Aucun changement de schéma SQLite, d'identité Android, de certificat ou de versionCode.

## Contre-audit / limites
- Ne garantit pas le rappel parfait au-delà des 360 premiers candidats d'une étape ni une pertinence médicale neuronale.
- `AND` FTS4 et tri doivent être validés par Robolectric/CI. Le téléphone S21 FE, ses 91 livres historiques, GGUF et les migrations in-place requièrent encore preuve terrain.
- Les 1 000 variantes du test de routage antérieur ne sont pas 1 000 scénarios médicaux distincts.
- Pas d'APK publiée par ce commit; garder 0.4.5 et toute base existante.
