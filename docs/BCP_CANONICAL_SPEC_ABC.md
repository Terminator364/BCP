# BCP — Cahier des charges intégral A+B+C

Status: CANONICAL CANDIDATE R81 · SOURCE-RECONCILED UCMF V9 + PHONE CAPABILITY REGISTRY  
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
- cadence **25 minutes = cible 23 min travail + 2 min fermeture** ;
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


## R81 — téléphone comme registre de capacités

Le téléphone dédié ne doit pas seulement exécuter des fonctions codées ; il doit pouvoir **décrire durablement ce qu'il sait réellement faire maintenant**.

Le registre de capacités local est donc une exigence A+B+C :

- identité déterministe de capacité par projet/type/provider/source ;
- état `AVAILABLE | DEGRADED | UNAVAILABLE | WAITING_AUTH | UNKNOWN` ;
- classe de preuve `MACHINE_READBACK | LOCAL_PROBE | PROVIDER_ACK | USER_CONFIRMED | CONFIGURED | UNKNOWN` ;
- métadonnées hashées, timestamp, TTL et expiration ;
- stockage Room local et utilisable hors connexion ;
- exposition uniquement via API locale authentifiée pour le détail ;
- intégration au Context Builder et au tableau de bord serveur ;
- événement Chronicle uniquement lors d'un changement matériel afin d'éviter le bruit.

La première implémentation candidate couvre l'API locale, l'exécuteur local borné, le store-and-forward, le worker PC, le relais Telegram/réseau et le gouverneur de ressources.

Cette exigence ne vaut pas preuve terrain. Le 2.2 reste non publiable tant que l'exact-head CI, l'émulateur Android, l'identité/signature APK et les gates terrain requis n'ont pas passé.

### Communication R81

La tranche interactive normale est **25 minutes** : cible 23 minutes de travail substantiel + environ 2 minutes de fermeture.

Le `PRIMARY_ASSISTANT` possède le chemin normal `START -> WORK -> CLOSE_INTENT -> Gmail END -> provider ACK -> CLOSED -> pointer ChatGPT`.

Un automate éventuel est **strictement un secours d'urgence** après interruption/échec du close primaire. Il ne doit jamais remplacer la fenêtre de travail utile ni être utilisé pour attendre artificiellement l'heure de fin.
