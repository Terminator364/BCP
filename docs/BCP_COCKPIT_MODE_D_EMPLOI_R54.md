# BCP Cockpit — Mode d’emploi utilisateur R54

Version: R54 Human Presentation / Kinshasa Time / PDF Quality  
Public visé: utilisateur non technique  
Principe: comprendre d’abord, approfondir ensuite.

## 1. Lire le cockpit en 10 secondes

Le cockpit doit permettre de répondre immédiatement à six questions:
1. Où en sommes-nous ?
2. Qu’est-ce qui est déjà confirmé ?
3. Qu’est-ce qui se passe maintenant ?
4. Qu’est-ce qui vient ensuite ?
5. Est-ce que je dois faire quelque chose ?
6. Les informations sont-elles fraîches ou anciennes ?

Si la réponse à ces six questions exige de comprendre GitHub, un SHA, un nom de variable ou un code interne, l’interface n’est pas encore suffisamment humaine.

## 2. Heure affichée

Toutes les heures normales visibles par l’utilisateur sont affichées en **heure de Kinshasa (UTC+1)**.

Exemple:
- preuve machine interne: `2026-09-20T21:51:24+00:00`;
- affichage humain: **20/09/2026 à 22:51:24 (Kinshasa)**.

Les reçus, bases de données, leases et preuves techniques peuvent rester en UTC pour la cohérence machine. Cette règle ne change jamais la preuve originale; elle change seulement sa présentation.

## 3. Les cinq états visibles

### 🔴 CRITIQUE
Un risque immédiat ou une perte de disponibilité demande une vérification prioritaire.

### 🟣 VOTRE ACTION EST NÉCESSAIRE
Une action humaine précise est obligatoire avant la suite. Le cockpit doit dire une seule action principale, ce qu’il ne faut pas répéter et comment le résultat sera vérifié.

### 🟠 À SURVEILLER
Une anomalie existe mais le système peut encore continuer ou se réparer automatiquement.

### 🟢 EN COURS
Des preuves récentes montrent que le travail avance.

### 🔵 STABLE
Aucun signal prioritaire n’est détecté.

## 4. Boutons principaux

- **🟢 Où en sommes-nous ?** — état, objectif, dernière preuve, maintenant, ensuite, action utilisateur.
- **🕘 Nouveautés** — uniquement ce qui a changé depuis votre dernière visite.
- **💬 Messages récents** — réponses réellement enregistrées par BCP et état de livraison.
- **❓ Pourquoi cet état ?** — raisons observables du statut.
- **📍 Étape actuelle** — travail actuel ou dernière étape prouvée.
- **🎯 Objectif & plan** — objectif courant et plan durable.
- **⚙️ Travail récent** — actions et preuves récentes en langage humain.
- **🔭 Risques à venir** — risques prédictifs, clairement séparés des faits.
- **▶️ Reprendre maintenant** — demande de reprise idempotente depuis le dernier checkpoint.
- **✅ Vu / compris** — confirme uniquement que le signal a été lu.
- **🔕 Pause 2h / 🔔 Alertes normales** — règle les interruptions ordinaires.
- **❔ Aide / mode d’emploi** — rappel court.
- **📚 Rapports & technique** — second niveau, volontairement séparé de l’écran principal.

## 5. Les quatre rapports PDF

### 1/4 — Situation humaine
À lire en premier. Doit montrer:
- état;
- objectif;
- ce qui est confirmé;
- maintenant;
- ensuite;
- action pour vous;
- système en bref;
- progression estimée clairement marquée comme estimation.

Aucun `mission_id`, nom de variable ou dump JSON ne doit être nécessaire.

### 2/4 — Appareils, réseau et transports
Doit expliquer en langage humain:
- PC;
- RAM et alimentation;
- ancien téléphone B-EDGE;
- Telegram;
- Drive;
- Nexus;
- fraîcheur des preuves;
- ce que les états signifient.

Les clés telles que `nexus_bootstrap_error_class` ou `event_age_seconds` sont réservées au diagnostic technique.

### 3/4 — Objectif, étapes et progression
Doit montrer:
- objectif;
- progression prouvée vs estimée;
- dernière action confirmée;
- travail actuel;
- prochaine étape;
- éventuelle action utilisateur;
- points à surveiller.

### 4/4 — Dossier technique et audit
Peut contenir:
- versions;
- IDs;
- hashes;
- checkpoint;
- états CI;
- preuves de diagnostic.

Même ici, un gros JSON brut n’est pas un bon rapport. Les preuves doivent être structurées et lisibles.

## 6. Qualité PDF obligatoire

Un PDF BCP qualifié doit:
- avoir un seul titre, jamais un doublon;
- garder les accents français corrects;
- avoir des titres/sections visuellement distincts;
- avoir des marges suffisantes;
- ne couper ni chevaucher le texte;
- paginer automatiquement;
- afficher `Page X/Y`;
- indiquer que l’heure présentée est l’heure de Kinshasa;
- rester léger pour le PC 4 Go et la connexion faible;
- être rendu en image pendant la qualification afin de détecter les défauts visuels.

## 7. ChatGPT mobile désynchronisé

Le fait qu’une réponse existe dans BCP ou dans un mail ne prouve pas que l’application ChatGPT mobile l’a déjà affichée.

Ordre de continuité:
1. **mail détaillé complet**;
2. pointeur ChatGPT;
3. Telegram comme témoin ou cockpit.

Si l’application ChatGPT est en retard, le mail devient le premier chemin de lecture. Le système ne doit pas vous demander de deviner si une réponse existe.

## 8. Ce que le cockpit ne doit pas exiger

En fonctionnement normal, vous ne devez pas devoir:
- comprendre un SHA ou un workflow;
- lire un JSON;
- convertir vous-même UTC en heure locale;
- recopier une IP, un token ou un ID;
- envoyer des captures pour une télémétrie déjà disponible;
- relancer plusieurs fois la même réparation;
- réinstaller une application pour une simple mise à jour;
- interpréter un mot interne comme `NOT_OBSERVED` pour savoir quoi faire.

## 9. Progression et preuve

Une valeur marquée `~` ou `≈` est une estimation.  
Une action n’est dite terminée que si une preuve durable la confirme.

Une donnée ancienne doit être signalée comme ancienne. L’absence de preuve fraîche n’est pas automatiquement une panne.

## 10. Priorité produit

Le cockpit R54 doit rester:
- compréhensible en moins de 30 secondes;
- lisible par un utilisateur non technique;
- cohérent entre Telegram direct et Nexus;
- robuste sous réseau intermittent;
- économe en données;
- non spammeur;
- honnête sur faits, estimations et incertitudes;
- compatible avec la contrainte PC 4 Go / RAM >90% / chauffe;
- fidèle à l’heure de Kinshasa pour toute présentation humaine.


## R55 — Où lire désormais les comptes rendus complets

Le **mail détaillé complet** est désormais l'unique surface humaine détaillée de fin de tranche.
Après confirmation d'envoi du mail, l'application ChatGPT n'affiche plus le compte rendu complet : elle affiche seulement un **pointeur ChatGPT** avec la date/heure de Kinshasa et l'identifiant du checkpoint.
Telegram reste un témoin secondaire, un canal d'alerte et de navigation de reprise.
