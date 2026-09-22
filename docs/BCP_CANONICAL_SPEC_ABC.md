# BCP — Cahier des charges intégral A+B+C

Status: CANONICAL CANDIDATE R81 · SOURCE-RECONCILED UCMF V9  
Revision: 2026-09-22-R81

## 1. Autorité

Le produit BCP n'est pas défini par le dernier écran Android, le dernier incident Telegram ou la dernière PR. Son dénominateur est **A + B + C**.

- **A — Préconception/origine** : intention source, package de préconception scellé, fonctions promises, architecture initiale, UCMF/Bible interne, Context Fabric, contraintes RDC/0 USD et continuité.
- **B — Approfondissement** : recherche technique et scientifique, contre-audit, meilleures pratiques, possibilités réalistes et amélioration au-delà de l'idée initiale.
- **C — Terrain** : tous les retours, corrections, préférences de travail, échecs, screenshots, versions, contraintes opérationnelles et exigences cumulées.

Aucune couche ne remplace les autres. Les trois sont cumulatives selon `SPEC_REFRESH_CURRENT_THEN_MERGE_REFINE_PRESERVE`.

Les pointeurs machine-readable sont :
- `.project-memory/BCP_ABC_SOURCE_REGISTRY.json`
- `.project-memory/BCP_ABC_COVERAGE.json`

## 2. A — produit promis à préserver

BCP est un **plan personnel de contrôle, mémoire, continuité et exécution** indépendant d'une conversation ChatGPT particulière.

Le système cible doit permettre :
1. une chronique durable de toute action **observable** et sémantiquement significative ;
2. une preuve exacte séparée des résumés dérivés ;
3. une mémoire canonique avec provenance, autorité, admission, supersession et révocation ;
4. des capsules de contexte petites et rapides plutôt qu'un replay de tout l'historique ;
5. une reprise par `BCPGO BCP` sans reconstruction manuelle ;
6. un système trois nœuds : B-EDGE, PC-WORKER, BCP NEXUS ;
7. des opérations idempotentes avec revision preconditions, fencing, receipts et readback ;
8. un mode offline-first, résilient aux coupures RDC ;
9. ZERO_USD par défaut ;
10. l'utilisateur hors de la boucle de télémétrie normale.

### Téléphone dédié

Le vieux téléphone Android est un **nœud B-EDGE de premier rang**, pas un simple écran ni un proxy Telegram.

Il doit progressivement héberger :
- registre projets et sessions ;
- Universal Event Ledger / Chronicle local ;
- Evidence pointers ;
- mémoire structurée HOT/WARM/COLD ;
- queue/outbox persistante ;
- scheduler/DAG local ;
- moteur de politiques ;
- ERROR_LEDGER/recettes validées ;
- Context Builder ;
- cache provider/quota/node ;
- API locale authentifiée ;
- découverte et transports locaux ;
- store-and-forward ;
- cockpit serveur et diagnostic ;
- reprise après reboot/process death/package replacement ;
- orchestration EDGE_ONLY lorsque le PC est absent ;
- dispatch vers PC uniquement pour les classes lourdes.

Le PC reste un **worker Windows lourd et réplique vérifiée**, pas le centre obligatoire de toute communication.

## 3. B — approfondissement obligatoire

### UCMF001 V9 — Postulats de recherche 2–9 intégrés dans B

Les Postulats **2–9** sont classés dans **B** : ils approfondissent l'idée source A au lieu de la réécrire. Le registre Drive UCMF001 courant a été relu directement et contient bien la lignée jusqu'au **Postulat 9 — CHATGPT-DEGRADED OPERATING ENVIRONMENT**.

Ils imposent notamment :
- **P2** : Universal Chronicle exacte + mémoire canonique dérivée, provenance, SQLite WAL, outbox transactionnelle et récupération sélective ;
- **P3** : téléphone SM-A217F dédié comme appliance local-first de continuité et futur coordinateur logique après preuve de fencing/réplication ;
- **P4** : fast path P0 sans scan global ni attente réseau, HotSnapshot immuable, writer-arbiter P0–P3, transaction durable de tour et reverse-RPC sortant ;
- **P5** : chaos/counter-research proof-carrying, negative controls et protection contre les faux compteurs ;
- **P6** : FMECA/SFTA/STPA, black-start, absence humaine et états POWER/LAN/INTERNET/AUTHORITY séparés ;
- **P7** : gray failures, fault injection temporelle, health vector, Direct-Boot mini-kernel, freshness envelope, horloges monotones et tests des protections elles-mêmes ;
- **P8** : séparation FAST CONTROL PLANE / BULK DATA PLANE, média/original scellé, reprise par chunks et dérivés asynchrones ;
- **P9** : **CHATGPT IS AN EXECUTOR, NOT THE MISSION AUTHORITY** ; une conversation peut mourir sans tuer la mission. Toute étape distante doit être précédée d'une enveloppe durable et les états provider sont explicites, y compris OUTCOME_UNKNOWN/RECONCILING.

La richesse de la mémoire ne doit pas introduire une latence structurelle. Une recherche globale, embedding, Drive sync, provider distant ou bulk media ne bloque pas le chemin interactif normal lorsque l'état local suffisant existe.

Les améliorations réalistes retenues incluent :

### Local-first et durabilité
- Room/SQLite WAL comme cœur local transactionnel ;
- WorkManager pour travail différé/reprise, jamais comme boucle sub-seconde ;
- index et résumés reconstructibles ; preuves et état canonique non reconstructibles uniquement depuis un résumé ;
- transactional outbox et livraison at-least-once avec effets idempotents ;
- fast path sans embedding, compaction, Drive sync ou scan global.

### Appliance Android à niveaux

**Tier 1 — Server App Mode** : app normale, permissions justifiées, foreground service visible, Room, WorkManager, LAN/NSD, store-forward.

**Tier 2 — Dedicated Appliance Power Mode** : batterie sans restriction, démarrage/reprise renforcé, nearby-device permissions, installation qualifiée, contrôles supplémentaires strictement nécessaires.

**Tier 3 — Fully Managed / Device Owner (optionnel)** : uniquement après analyse de bénéfice et gate humain explicite. Ce tier peut réduire certaines limitations Android pour un appareil réellement dédié, mais son provisioning potentiellement disruptif interdit toute activation silencieuse.

### Réseau
- NSD/mDNS primaire sur LAN ;
- Wi-Fi Direct service discovery comme chemin local sans LAN/hotspot lorsque le matériel/permission le permet ;
- BLE pour présence/contrôle minimal, pas pour gros payloads ;
- USB comme futur chemin terrain qualifié ;
- serveur Internet entrant public non requis ;
- transport LAN de production **authentifié et chiffré** ; le cleartext actuel reste POC et ne satisfait pas la cible finale ;
- data saver et routage vers le téléphone pour éviter que le PC consomme inutilement l'uplink mobile.

### Android lifecycle
Toujours-on signifie **toujours récupérable**, pas processus immortel. La correction dépend de Room/outbox/checkpoints, jamais d'un thread vivant pour toujours.

## 4. C — exigences terrain cumulées

Les retours utilisateur deviennent des exigences P0 :

- arrêter les micro-bêtas ;
- ne pas demander des installations répétées ;
- simuler Windows/Android avant tout clic humain ;
- exploiter réellement les 4 Go RAM / stockage du téléphone dédié sans le saturer ;
- ne pas supposer de SIM dans l'ancien téléphone ;
- faire du téléphone un serveur/Edge autonome même PC absent ;
- fournir une vraie UI serveur : état, files, mémoire, transports, permissions, santé, diagnostics, version, reprise ;
- permettre un onboarding Android d'autorisations réellement liées aux fonctions ;
- considérer réseau mauvais, Wi-Fi cassé, hotspot temporaire et coupures de courant comme conditions normales ;
- Gmail START -> travail -> Gmail END -> pointeur ChatGPT ;
- communication **ADAPTIVE_TASK_WINDOW** : Gmail START avec scope + fenêtre de fin estimée ; aucun minimum/max fixe artificiel ; Gmail END obligatoire avec résultat/preuves/next action ;
- la fermeture normale appartient à l'assistant actif, sans dépendre d'un automate ;
- Telegram, Gmail, Drive et relay ne sont “envoyés” qu'avec preuve du provider/readback ;
- `BCPGO BCP` doit reprendre ces règles dans une nouvelle conversation.

## 5. Mesure honnête de l'avancement

Le macro-audit R79, après lecture directe du handoff APIAX07, du dossier de compréhension et du registre Drive UCMF001 **V1–V9**, donne un dénominateur plus large et donc un score volontairement plus conservateur :
- **couverture fonctionnelle pondérée : 53,9 %** ;
- **maturité de preuve : 42,2 %**.

Ces valeurs restent un **score macro de maturité de preuve**, pas un pourcentage marketing du produit final. Le ZIP scellé V0.7 reste garanti par son pointeur SHA/manifest et n'a pas été prétendu relu octet par octet. Les sources A lisibles ont cependant été substantiellement reconstruites et recoupées.

### Mission survival / provider-degraded P0

Avant tout appel modèle/provider susceptible d'être interrompu, BCP doit pouvoir persister un **BCP_MISSION_STEP_ENVELOPE_V1** contenant au minimum : mission/step/revision/projet, opération demandée, hashes input/contexte, policy revision, expected state revision, dernier checkpoint, dépendances, classe d'effet, idempotency/fencing si applicable, next safe action, continuation frontier et temps monotone + mural.

États provider autorisés : `NOT_DISPATCHED`, `DISPATCH_ATTEMPTED`, `PROVIDER_ACKED`, `STREAM_OBSERVED`, `RESULT_OBSERVED`, `RESULT_COMMITTED`, `PLATFORM_HOLD`, `INTERRUPTED`, `OUTCOME_UNKNOWN`, `RECONCILING`, `SUPERSEDED`.

Le téléphone dédié est le lieu naturel de cette enveloppe locale durable afin que la reprise ne dépende ni du scrollback ChatGPT ni d'un PC vivant.

## 6. Écart critique actuel

Le candidat Android 2.2.0 possède déjà un vrai serveur local, Room, WAL, queue, scheduler, local executor, API, présence NSD/Wi-Fi Direct/BLE, resource governor et boot restore. Mais il reste insuffisant contre A+B+C parce que :

1. la **Universal Chronicle** est maintenant implémentée dans Room v3 et exposée par l'API locale, mais reste à qualifier sur l'appareil 2.2 réel ;
2. le transport LAN local reste cleartext POC et doit devenir authentifié + chiffré avant cible finale ;
3. l'app terrain installée reste 2.1.2 alors que 2.2 full-node est encore candidate ;
4. Telegram terrain reste dégradé ;
5. l'admission/supersession mémoire et le registre de capacités/source ne sont pas complets ;
6. l'UI serveur ne couvre pas encore tout le cockpit A+B+C ;
7. Device Owner reste un tier optionnel à bénéfice/risque mesuré, jamais un prérequis caché.

## 7. Règle de release

Une release utilisateur significative doit avancer un **vertical slice cohérent A+B+C**. Elle ne peut pas être présentée comme un jalon produit si elle ne corrige qu'un bouton, une acceptation ou un symptôme isolé.

Chaque candidate doit publier :
- source revision A+B+C ;
- matrice de couverture ;
- statuts IMPLEMENTED / CI / DEVICE / FIELD ;
- gaps explicites ;
- compatibilité Windows/Android ;
- update/rollback ;
- readback terrain.

Le prochain incrément téléphone doit au minimum intégrer la Chronicle locale et renforcer son cockpit avant d'être envisagé comme nouvelle installation.


## 8. Vertical slice R81 — gouvernance locale téléphone

R81 ferme une partie structurante de deux gaps A+B+C sans créer une nouvelle micro-bêta :

- **registre local de capacités** Room v5 : chaque capacité observée porte nœud, provider, type, état, transport, détails, classe de preuve, observed_at, expiry et updated_at ;
- **journal append-only des claims mémoire** : chaque tentative d'admission porte source, autorité, evidence_class, idempotency_key, état ADMITTED/REJECTED et lien de supersession ;
- la mémoire canonique dérivée n'est modifiée qu'après passage de la politique de précédence ; un claim plus faible ne peut pas écraser silencieusement une mémoire mieux prouvée/pinnée ;
- le Context Builder local inclut désormais capacités observées + ledger des claims, sans dépendre du PC ;
- API privée authentifiée : `GET/POST /v1/node/capability-registry` et `GET/POST /v1/node/memory-claims` ;
- cockpit serveur : affiche le nombre de capacités et de claims/provenances réellement présents ;
- migration Room **v4→v5** explicite ; aucune destructive migration autorisée.

Cette tranche augmente la couverture fonctionnelle macro provisoire à **56,1 %** tout en gardant la maturité de preuve à **42,2 %** tant que l'exact-head CI et la migration sur appareil 2.2 ne sont pas prouvés. Elle ne constitue donc pas une autorisation d'installation.


## 9. R89 — Reference-first / anti-réinvention

R89 rend obligatoire la règle suivante avant toute nouvelle UI, fonction, couche de transport, service, protocole ou module majeur :

`A+B+C -> références matures -> gap map -> REUSE/ADAPT/BUILD_ONLY_IF_GAP -> licence/provenance -> parcours utilisateur -> simulation représentative -> implémentation`.

Sources de référence autorisées et priorisées :
1. documentation officielle de plateforme/standard ;
2. implémentations open source matures ;
3. produits/documentations industrielles matures ;
4. littérature de fiabilité distribuée ;
5. vidéos/tutoriels uniquement pour observer les parcours humains, jamais comme seule autorité d'architecture/sécurité.

Politique machine-readable : `.project-memory/REFERENCE_FIRST_POLICY.json`.
Registre des précédents : `.project-memory/EXTERNAL_REFERENCE_REGISTRY.json`.
Benchmark R89 : `docs/BCP_REFERENCE_FIRST_BENCHMARK_R89.md`.

### Charge de preuve BUILD_ONLY_IF_GAP

Une implémentation custom doit documenter pourquoi les précédents matures ne satisfont pas BCP : contrainte RDC/offline/4 Go/0 $, modèle de confiance, licence incompatible, footprint excessif, ou échec terrain mesuré. Le fait qu'un composant custom existe déjà n'est pas une justification.

### UX B-EDGE cible

La candidate 2.2 actuelle devient **baseline technique**, pas UX cible. La prochaine candidate cohérente doit appliquer :
- Accueil status-first avec état, objectif, dernier succès et **une seule prochaine action principale visible sans scroll** ;
- navigation compacte `Accueil / Missions / Appareils / Activité`, Paramètres secondaire ;
- Paramètres réservé aux préférences peu fréquentes ; réparation/mise à jour/test restent contextuels à Appareils/Missions/Diagnostics ;
- pairing inspiré des parcours Home Assistant/KDE Connect : découverte par nom -> sélection -> vérification humaine -> confirmé ; IP/QR seulement fallback ;
- permissions demandées au moment où la capacité correspondante est activée ;
- diagnostics techniques, TLS hashes, claims, registres et preuves derrière divulgation progressive ;
- updater présenté comme état persistant `CHECKING -> AVAILABLE -> DOWNLOADING -> VERIFIED -> READY_TO_INSTALL -> INSTALLED/FAILED`.

La simulation Android doit désormais prouver **des tâches utilisateur**, pas seulement la présence de chaînes après cinq scrolls.

### Vérité courante R89

- B-EDGE 2.2.0-full-node-evergreen : **machine-qualified / Drive CURRENT-ready / field-unverified**.
- Transport candidate 2.2 : **TLS pinné bidirectionnel qualifié CI** ; les anciennes mentions de production LAN cleartext dans les sections historiques ne décrivent plus la candidate courante.
- Le prochain clic utilisateur `ANDROID_IN_PLACE_INSTALL` est **temporairement différé par R89** : la baseline 2.2 est conservée, mais BCP doit d'abord intégrer les deltas reference-first à plus forte valeur dans une candidate cohérente afin d'éviter un nouveau cycle installer -> constater -> refaire.
- Aucun byte produit/release n'est modifié par R89.
