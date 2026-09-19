# BCP — Telegram Human Cockpit V5: micro-actions concrètes, progression vérifiable et rapports explicatifs

Status: ACTIVE PRODUCT REQUIREMENT DELTA / IMPLEMENTATION CANDIDATE
Adopted: 2026-09-20
Evolution rule: SPEC_REFRESH_CURRENT_THEN_MERGE_REFINE_PRESERVE
Builds on: `docs/TELEGRAM_HUMAN_COCKPIT_V4_INTERACTIVE_EXPORTS.md`

## But

V5 corrige le principal défaut d'ergonomie observé sur le terrain : un cockpit peut être techniquement exact tout en restant trop abstrait pour l'utilisateur.

Le cockpit doit donc répondre immédiatement à quatre questions humaines :

1. **Qu'est-ce qui est en train d'être fait, concrètement ?**
2. **Quelle micro-action vient d'être terminée ?**
3. **Quelle micro-action vient ensuite ?**
4. **Sur combien d'étapes vérifiables sommes-nous, lorsque ce total existe réellement ?**

Le cockpit ne remplace pas la chaîne de pensée de ChatGPT et ne prétend pas l'observer. Il projette uniquement des événements durables et des étapes explicitement persistées par BCP.

## Définition normative d'une micro-action

Une micro-action est une unité de travail courte, concrète, observable et vérifiable.

Exemples valides :
- ouvrir et lire un fichier précis ;
- comparer deux versions d'un fichier ;
- modifier un fichier précis ;
- vérifier un commit précis ;
- lancer un test ou un workflow déterminé ;
- lire le résultat d'un workflow ;
- vérifier un hash ou un reçu ;
- publier un checkpoint ;
- vérifier une télémétrie Drive/B-EDGE/Nexus ;
- produire ou vérifier un PDF ;
- fusionner une PR après qualification.

Exemples trop vagues pour l'interface humaine :
- « traiter le projet » ;
- « avancer » ;
- « réflexion » ;
- « activité » ;
- « vérifier le système » sans objet précis ;
- un nom de composant seul sans verbe/action.

Les identifiants techniques restent permis dans `/details`, mais la vue normale doit privilégier le libellé humain du plan persisté.

## Source de vérité de la progression

La barre de progression ne peut être calculée que depuis un **plan fini persistant** présent dans l'état BCP.

Le plan doit contenir une liste ordonnée d'étapes avec au minimum :
- `id` ;
- `label` humain ;
- `state` ;
- `verified`.

La progression affichée est :

`nombre d'étapes vérifiées / nombre total d'étapes du plan`.

Aucun pourcentage n'est produit à partir :
- du temps écoulé ;
- du nombre de messages ChatGPT ;
- d'une estimation subjective ;
- d'un spinner ;
- d'une durée de « réflexion » ;
- du nombre de commits seulement.

Si aucun plan fini n'est disponible, le cockpit affiche la phase/état sans pourcentage.

## Carte Telegram normale

Structure cible :

```
🤖 BCP Cockpit — API/BCP
🟢 Une preuve récente confirme que ça avance.

🎯 Micro-action actuelle: Vérifier le workflow Windows Bootstrap
📊 Progression: ██████░░░░ 60% — 6/10 micro-actions vérifiées
✅ Dernière micro-action terminée: Vérifier le commit 7dca68f
➡️ Prochaine micro-action: Lire le journal du job Windows
👤 Action pour vous: AUCUNE

🕒 Dernière preuve: <timestamp> · âge <durée>

✅ PC/BCP
✅ Ancien téléphone
✅ Drive
🌐 Relais Nexus: <état simple>
🧪 Tests: <état simple>
```

La vue normale doit être compréhensible par une personne qui ne connaît ni Git, ni les PR, ni les SHA.

## Boutons

Le clavier V5 doit rester compact et stable :

- **🔄 Actualiser**
- **📍 Étape**
- **📋 Micro-actions**
- **🗂 Missions**
- **🧾 Détails**
- **📄 PDF suivi**
- **📚 PDF technique**

`📋 Micro-actions` ouvre le journal numéroté des dernières micro-actions durables.

## Journal numéroté

Le journal humain doit afficher les entrées sous forme :

```
1. ✅ Lire le cahier des charges courant
2. ✅ Vérifier le commit de la PR
3. • Lancer le test Windows Bootstrap
4. 🔴 Corriger l'échec du test de hash
```

Chaque entrée doit venir d'un événement durable ou d'une étape de mission persistée.

Le journal ne doit pas imiter les messages intermédiaires internes du modèle.

## Automatique sans ChatGPT Scheduled Automation

L'expérience doit être automatique, mais **pas** via les automatismes planifiés ChatGPT/Work.

Le comportement automatique autorisé est résident et événementiel dans BCP/B-EDGE/Nexus :
- écrire les événements de mission au moment où les micro-actions se produisent ;
- actualiser la carte Telegram lors d'un changement utile ;
- ne pas spammer les heartbeats inchangés ;
- persister avant envoi ;
- reprendre après coupure réseau ;
- conserver un curseur durable ;
- ne jamais rejouer aveuglément une mutation au statut inconnu.

## Réseau Kinshasa / faible consommation

Contexte terrain contraignant :
- PC sur Wi-Fi maison ;
- ancien téléphone B-EDGE sur le même Wi-Fi maison ;
- téléphone courant parfois Wi-Fi, parfois données mobiles ;
- direct PC -> Telegram peut être lent ou timeout sur le Wi-Fi maison ;
- les données mobiles doivent être économisées.

V5 conserve donc :
- journal local-first ;
- relais Nexus lorsqu'il est qualifié ;
- cache de rapports ;
- payloads texte compacts ;
- aucune image obligatoire ;
- aucun téléchargement lourd répétitif ;
- zéro téléchargement si version inchangée ;
- aucun besoin de mettre le PC entier sur hotspot comme mode normal.

## PDF de suivi humain

Le PDF utilisateur doit contenir :
- résumé de la mission ;
- micro-action actuelle ;
- dernière micro-action terminée ;
- prochaine micro-action ;
- barre/ratio si plan fini ;
- plan numéroté complet ;
- journal récent des micro-actions ;
- état simple PC/B-EDGE/Drive/Nexus/tests ;
- dernier horodatage de preuve ;
- action humaine requise ou AUCUNE ;
- explication courte de la signification des états.

Il doit être explicatif, pas seulement recopier `/status`.

## PDF technique

Le PDF technique doit ajouter :
- mission_id ;
- worker/component ;
- statut durable ;
- timestamps ;
- receipt/evidence ;
- hold_reason ;
- plan complet ;
- journal des événements ;
- état CI ;
- état des transports ;
- contrat de vérité/limites d'observation.

Il ne doit jamais contenir de token ou secret.

## Nexus

Nexus reste un relais, pas une source de vérité.

Quand il est qualifié :
- les callbacks Telegram sont accusés réception rapidement ;
- les commandes lecture seule sont relayées vers BCP ;
- les réponses sont dédupliquées ;
- un résumé/PDF cache peut être servi même si le PC ne joint pas Telegram directement ;
- l'état canonique demeure BCP local + preuves durables.

Si Nexus n'est pas déployé/autorisé, le cockpit doit l'afficher clairement comme non actif et conserver le mode dégradé local/direct sans boucle infinie.

## Mise à jour automatique

V5 doit être livré par le plan de mise à jour existant :
- manifeste CURRENT ;
- hash SHA-256 ;
- téléchargement seulement si version différente ;
- staging ;
- self-test ;
- bascule atomique ;
- rollback ;
- conservation du token/chat autorisé ;
- reprise réseau ;
- aucune saisie répétée du token ;
- aucune manipulation manuelle de ZIP dans le fonctionnement normal.

## Tests d'acceptation V5

1. le statut utilise la mission SQLite persistée lorsqu'elle existe ;
2. le libellé courant vient du `label` du plan si disponible ;
3. la barre apparaît pour un plan fini ;
4. la barre n'apparaît pas sans dénominateur réel ;
5. le nombre d'étapes vérifiées correspond exactement au plan ;
6. la dernière micro-action utilise `last_committed_step` ;
7. la prochaine utilise `next_step` ;
8. le bouton Micro-actions est présent ;
9. le journal est numéroté ;
10. le journal lit `mission_events` SQLite avant le fallback JSONL ;
11. PDF suivi inclut plan + journal ;
12. PDF technique inclut métadonnées mission + plan + journal ;
13. aucun secret n'est exporté ;
14. self-test Python passe ;
15. tests Windows et Linux passent ;
16. transport Nexus/direct conserve la même sémantique de boutons ;
17. pertes Telegram/Nexus n'arrêtent pas l'exécution locale ;
18. aucune ChatGPT scheduled automation n'est créée ;
19. aucune réinstallation manuelle n'est exigée si l'auto-update converge ;
20. FIELD_VERIFIED n'est attribué qu'après round-trip terrain Kinshasa.
