# BCP R54 — Audit profond de présentation humaine et PDF

Status: IMPLEMENTED CANDIDATE / CI + FIELD VERIFICATION PENDING  
Date: 2026-09-20  
Scope: Telegram direct, Nexus, quatre PDF, horodatages visibles, release metadata, tests.

## 1. Motif

Le contrôle précédent vérifiait surtout la validité fonctionnelle et la présence des éléments. Il ne suffisait pas pour garantir qu’un utilisateur non technique comprend immédiatement ce qu’il voit.

L’audit R54 traite la présentation comme une exigence P0.

## 2. Défauts découverts

### H54-01 — UTC brut visible dans les rapports
**Sévérité:** P0 UX / vérité contextuelle.  
Les quatre rapports utilisaient directement `utc_now()` dans la ligne “Généré”. D’autres surfaces affichaient `seen_at`, `last_activity_at` et les événements sous forme ISO UTC.

**Correction:** formatter humain central Kinshasa; UTC conservé uniquement pour la preuve machine.

### H54-02 — Rapport Appareils exposant les noms de champs internes
**Sévérité:** P0 UX.  
Le rapport affichait directement des clés telles que `nexus_bootstrap_error_class`, `telegram_companion_last_callback_handled_at`, `event_age_seconds`.

**Correction:** présentation humaine PC/B-EDGE/Telegram/Drive/Nexus; champs internes réservés au rapport technique.

### H54-03 — Rapport Mission exposant des identifiants et étapes internes
**Sévérité:** P0 UX.  
`mission_id`, `current_step`, `last_committed_step` et autres champs internes formaient le cœur du rapport.

**Correction:** structure objectif → confirmé → maintenant → ensuite → action utilisateur.

### H54-04 — Rapport technique avec dump JSON GitHub brut
**Sévérité:** P1 lisibilité.  
Un snapshot JSON de plusieurs milliers de caractères était injecté dans le PDF.

**Correction:** synthèse CI/workflows structurée; preuves techniques conservées sans dump brut.

### H54-05 — Double titre PDF
**Sévérité:** P1 présentation.  
Le renderer ajoutait un titre, tandis que le corps commençait de nouveau par “BCP — RAPPORT X/4”.

**Correction:** détection anti-double-titre + corps des rapports sans titre dupliqué.

### H54-06 — PDF plat, 10 pt uniforme, coupures fixes
**Sévérité:** P1 présentation.  
Helvetica 10, 92 caractères, 46 lignes/page, aucune hiérarchie, aucun numéro de page.

**Correction:** Helvetica/Helvetica-Bold, styles titre/section/corps/bullet, marges, pagination verticale, Page X/Y et footer Kinshasa.

### H54-07 — Accents français cassés
**Sévérité:** P0 qualité documentaire.  
Le rendu visuel a montré des glyphes erronés pour `réseau`, `Créé`, `mémoire`, etc., malgré un PDF structurellement valide.

**Cause:** octets CP1252 sans déclaration d’encodage de police.

**Correction:** `/Encoding /WinAnsiEncoding` sur Helvetica et Helvetica-Bold + test de glyphes `Café déjà prêt à Kinshasa.`.

### H54-08 — Deux moteurs PDF divergents
**Sévérité:** P0 cohérence multi-transport.  
Telegram/PC et Nexus possédaient deux générateurs distincts. Nexus conservait le renderer plat et supprimait les accents.

**Correction:** parité de structure PDF R54 sur les deux chemins, mêmes principes de pagination/hierarchie/WinAnsi.

### H54-09 — Légende PDF Nexus avec `updated_at` UTC brut
**Sévérité:** P0 cohérence horaire.  
La légende Telegram envoyée depuis Nexus concaténait directement la valeur de stockage.

**Correction:** formatter `humanTimestampKinshasa` dans le Worker.

### H54-10 — Version Nexus incohérente
**Sévérité:** P0 observabilité.  
Le bundle était publié comme Nexus 0.2.5 alors que `/health` répondait encore `version: 0.2.3`.

**Correction:** Nexus 0.2.6 et garde CI exacte.

## 3. Audit visuel représentatif

Un rapport “Appareils” représentatif a été généré avant/après avec les mêmes faits:
- avant: 2 pages, double titre, mur de clés techniques, UTC brut, accents cassés;
- après: 1 page, titre unique, sections visibles, français correct, heure Kinshasa, informations interprétées.

Cette comparaison est une preuve de conception locale. La qualification terrain sur le PDF réellement généré par le PC reste requise avant FIELD_VERIFIED.

## 4. Invariants R54

- preuve machine: UTC;
- présentation humaine: Africa/Kinshasa;
- rapports 1–3: aucun champ interne comme contenu principal;
- rapport 4: technique mais structuré;
- PDF: titre unique, accents corrects, hiérarchie, pagination, Page X/Y;
- Nexus et Telegram: parité fonctionnelle;
- aucune promotion FIELD_VERIFIED sans rendu PDF réel.

## 5. Tests ajoutés

- fixture UTC 21:51:24 → Kinshasa 22:51:24;
- absence de `+00:00` dans rapports humains 1–3;
- absence de `nexus_bootstrap_error_class` et `mission_id:` dans rapports humains;
- présence Helvetica-Bold + WinAnsiEncoding;
- présence Page 1/N;
- test glyphes français;
- protection anti-double-titre;
- vérification de séparation menu principal / menu technique;
- version Nexus 0.2.6 obligatoire;
- hash release exact pour Telegram V18 et Nexus 0.2.6.

## 6. Gate restant

Après CI verte et merge:
1. convergence PC vers Telegram V18;
2. génération réelle des quatre PDF;
3. lecture/rendu des PDF terrain;
4. vérification timestamps Kinshasa;
5. vérification Nexus si transport distant actif;
6. seulement alors: FIELD_VERIFIED pour R54.
