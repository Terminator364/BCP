# BCP Cockpit — Mode d’emploi utilisateur

Version: R53 Human Cockpit
Public visé: utilisateur non technique
Principe: montrer d’abord ce qui compte humainement, garder la technique derrière un bouton.

## 1. À quoi sert le cockpit

BCP Cockpit est l’interface humaine du projet API/BCP. Il ne remplace pas ChatGPT: il sert à montrer ce que le système sait durablement, ce qui avance, ce qui attend, ce qui a changé depuis votre dernière visite, et quand une action de votre part est réellement nécessaire.

Il doit rester utile même quand:
- l’application ChatGPT mobile se synchronise mal;
- le PC a une connexion faible;
- Telegram direct est dégradé;
- Drive est en retard;
- le PC a peu de RAM ou chauffe;
- une conversation ChatGPT est interrompue.

## 2. Les cinq états visibles

### 🔴 CRITIQUE
Un risque immédiat ou une perte de disponibilité demande une vérification prioritaire. Exemple: PC non joignable longtemps ou batterie critique.

### 🟣 VOTRE ACTION EST NÉCESSAIRE
Le système peut conserver son état, mais une action humaine précise est obligatoire avant la suite. Exemple: autorisation Cloudflare.

### 🟠 À SURVEILLER
Le système continue mais une anomalie existe. Il ne faut pas forcément agir tout de suite.

### 🟢 EN COURS
Des preuves récentes montrent que le travail avance.

### 🔵 STABLE
Aucun signal prioritaire n’est détecté.

## 3. Boutons principaux

### 🟢 Où en sommes-nous ?
Vue d’ensemble. À utiliser en premier.
Affiche:
- état global;
- objectif;
- progression estimée quand elle est calculable;
- action actuelle;
- dernière action confirmée;
- prochaine étape;
- santé PC/B-EDGE/Drive/Nexus/tests;
- âge de la dernière preuve.

### 🕘 Nouveautés
Montre uniquement ce qui a changé depuis votre dernière visite au cockpit.
Utilité: revenir après plusieurs minutes/heures sans relire toute l’historique.

### 💬 Messages récents
Montre les conversations/réponses que BCP a effectivement reçues ou miroirées.
Important: la présence d’une réponse ici prouve qu’elle existe dans BCP, pas forcément que l’application ChatGPT l’a affichée sur votre téléphone.

### ❓ Pourquoi cet état ?
Explique les raisons observables du statut actuel.
Exemples:
- autorisation humaine requise;
- PC sans heartbeat récent;
- message BCP non confirmé comme lu;
- mission en attente;
- Telegram direct dégradé.

### 📍 Étape actuelle
Montre la micro-action actuelle ou la dernière étape prouvée, ainsi que l’étape suivante quand elle est connue.

### 🎯 Objectif & plan
Explique l’objectif courant et, lorsqu’un plan fini existe, les étapes prévues et celles déjà vérifiées.

### ⚙️ Travail récent
Journal des micro-actions et reçus récents. Plus détaillé que la vue principale, mais encore lisible sans connaître Git.

### 🔭 Risques à venir
Vue prédictive.
Ce bouton ne dit pas qu’un incident est arrivé; il signale des fragilités probables à partir des preuves disponibles.
Exemples:
- RAM élevée;
- PC sur batterie;
- Nexus non autorisé;
- qualification GitHub encore en cours.

### ▶️ Reprendre maintenant
Demande à BCP de reprendre la mission durable.
Ce bouton n’est pas un “rejouer tout”. La demande est idempotente: BCP doit reprendre depuis la dernière preuve et ne pas refaire ce qui est déjà confirmé.

### ✅ Vu / compris
Confirme que vous avez pris connaissance du signal actuel.
À utiliser quand BCP dit qu’une réponse est sauvegardée mais n’a pas de preuve de lecture.
Cela évite que le même signal inchangé revienne comme une nouvelle alerte.

### 🔕 Pause 2h
Réduit les notifications ordinaires pendant deux heures.
Les signaux critiques et vrais gates humains restent autorisés à passer.

### 🔔 Alertes normales
Quitte le mode discret et remet le fonctionnement habituel.

### ❔ Aide / mode d’emploi
Affiche directement un résumé des boutons et commandes utiles.

## 4. Rapports PDF

### 📄 Résumé PDF
Rapport humain compact: situation, objectif, progression, prochaine action.

### 🖥️ État appareils
PC, B-EDGE, réseau, Drive, Nexus et transports.

### 🧭 Plan mission
Objectif, étapes, micro-actions et progression prouvée.

### 📚 Audit PDF
Rapport technique approfondi: preuves, états, diagnostics, CI et anomalies.

## 5. Détails techniques

### 🧰 Détails techniques
Vue destinée au diagnostic.
Peut contenir GitHub, CI, transport, hashes, versions et preuves.
La vue normale ne doit pas vous obliger à comprendre ces éléments.

## 6. Règles de lecture importantes

### Progression avec ≈
Une valeur comme “≈60 %” est une estimation de décomposition du travail. Elle n’est pas une preuve de temps restant.

### Preuve fraîche
Le cockpit affiche l’âge de la dernière preuve durable connue. Une absence de nouvelle preuve n’est pas automatiquement une panne ChatGPT.

### Message BCP ≠ affichage ChatGPT
BCP peut avoir reçu une réponse alors que l’application ChatGPT mobile ne l’affiche pas encore. C’est précisément pourquoi le mail et Telegram servent de canaux de continuité.

### Gate humain
Quand votre action est réellement nécessaire, le cockpit doit dire:
1. ce qui bloque;
2. l’unique action à faire;
3. ce qu’il ne faut pas refaire;
4. comment le système vérifiera le résultat.

## 7. Ordre recommandé au quotidien

1. Ouvrir **🟢 Où en sommes-nous ?**
2. Si vous revenez après une absence: **🕘 Nouveautés**
3. Si quelque chose est incompréhensible: **❓ Pourquoi cet état ?**
4. Si une action humaine est demandée: faire uniquement l’action indiquée.
5. En cas de doute sur ChatGPT mobile: **💬 Messages récents** puis le mail miroir.
6. Utiliser **🧰 Détails techniques** seulement pour diagnostic approfondi.

## 8. Ce que le cockpit ne doit jamais vous demander

En fonctionnement normal, vous ne devez pas avoir à:
- recopier des IP;
- recopier des tokens;
- comprendre des SHA/PR/workflow IDs;
- relancer en boucle une installation;
- deviner si une ancienne action a réussi;
- réinstaller une application pour une simple mise à jour;
- faire plusieurs téléchargements Internet quand un package manuel one-shot est disponible.

## 9. Continuité par mail

Pour les tranches de travail interactives:
- cible courante: 8–10 minutes de travail utile;
- fin de tranche: checkpoint visible;
- le corps du mail miroir doit être textuellement identique au message final ChatGPT;
- le mail sert de canal de secours quand l’application ChatGPT mobile est en retard ou se recharge mal.

## 10. Lecture de l’alerte “réponse sauvegardée mais non lue”

Cette alerte signifie:
- BCP possède une réponse assistant durable;
- BCP n’a pas reçu de preuve explicite que vous l’avez vue dans l’interface;
- cela peut être un problème de synchronisation de l’application, pas un problème de génération de la réponse.

Action:
- si vous avez déjà vu la réponse: **✅ Vu / compris**;
- sinon: **💬 Messages récents** ou consulter le mail miroir.

## 11. Priorité produit

Le cockpit doit rester:
- lisible en moins de 30 secondes;
- utilisable sans connaissance Git/GitHub;
- robuste sous réseau intermittent;
- économe en données;
- non spammeur;
- clair sur faits vs prévisions;
- clair sur action humaine vs travail automatique;
- cohérent entre Telegram direct et Nexus.
