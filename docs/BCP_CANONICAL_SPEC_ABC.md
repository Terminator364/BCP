# BCP — Cahier des charges intégral A+B+C

Status: CANONICAL CANDIDATE R78 · SOURCE-RECONCILED  
Revision: 2026-09-21-R78

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

### Fast-path P0 issu des Postulats de recherche UCMF001 2–4

Les Postulats 2–4 sont classés dans **B** : ils approfondissent l'idée source A au lieu de la réécrire. Ils imposent que la richesse de la mémoire n'introduise pas une latence structurelle. Le chemin interactif P0 doit privilégier : contexte précompilé, lecture locale ciblée, HotSnapshot immuable, writer-arbiter P0–P3, une transaction durable de tour, circuit-breakers par dépendance, puis synchronisation/compaction asynchrones. Une recherche globale, un embedding, Drive ou un provider distant ne doit pas bloquer la réponse normale quand l'état local suffisant existe. Le canal reverse-RPC doit être initié en sortie par B-EDGE; long-poll et WebSocket restent des challengers à mesurer sur le vrai téléphone.

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

Le macro-audit R78, après lecture directe du handoff APIAX07, du dossier de compréhension et des Postulats UCMF001 V1–V4, donne :
- **couverture fonctionnelle pondérée : 57,0 %** ;
- **maturité de preuve : 45,35 %**.

Ces valeurs restent un **score macro de maturité de preuve**, pas un pourcentage marketing du produit final. Le ZIP scellé V0.7 reste garanti par son pointeur SHA/manifest et n'a pas été prétendu relu octet par octet. Les sources A lisibles ont cependant été substantiellement reconstruites et recoupées.

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
