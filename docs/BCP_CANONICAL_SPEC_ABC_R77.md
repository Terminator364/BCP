# BCP — Spécification canonique intégrale A+B+C — R77

Status: CANONICAL_CANDIDATE
Revision: 2026-09-21-R77
Continuation code: `BCPGO BCP`

## 0. Règle d'autorité

Le cahier des charges BCP n'est plus interprété comme une liste de fonctions ajoutées au fil des versions.

Il est défini par la composition obligatoire **A + B + C**:

- **A — Origine / préconception**: intention initiale, package scellé V0.7, dossier de compréhension, fonctions promises, architecture et invariants historiques qui restent actifs.
- **B — Approfondissement**: recherche technique/scientifique/pratique, contre-audit, meilleures pratiques et possibilités réalistes permettant d'aller plus loin que l'idée initiale sans gonfler artificiellement le produit.
- **C — Feedback cumulé**: retours terrain, corrections, exigences de travail, contraintes RDC, préférences d'interface, règles de communication, décisions de version et observations sur la sous-utilisation du téléphone.

Une fonctionnalité de produit n'est pas considérée comme "alignée cahier des charges" parce qu'elle satisfait une seule couche. Elle doit être tracée vers les exigences A+B+C concernées.

## 1. Sources A

Autorités connues:
- `.project-memory/APIAX07_CONTINUITY.json`
- package scellé `BCP_PRECONCEPTION_V0_7_AX15GO_SEALED.zip`, SHA-256 `50166472fd60329bc21d958f1bc97f3f410922dfd0c7f32071be35703051ebec`
- dossier `BCP_API_Personnelle_Dossier_Complet_2026-09-18.pdf`, SHA-256 `9e01e1dd5dd40d176d51c85b6d985506f6379702e94ab9201167031afce35ab3`
- `README.md`, `API_PROJECT_CONTINUITY.md`, cahier canonique courant.

A impose notamment:
1. continuité indépendante de la conversation;
2. état canonique durable et récupérable;
3. PC faible RAM + téléphone Android dédié + 0 USD;
4. offline-first, reprise après coupure courant/réseau;
5. contrôle local, receipts, idempotence, preuve avant succès;
6. automatisation maximale et friction utilisateur minimale;
7. téléphone et PC comme nœuds complémentaires;
8. mémoire projet, orchestration et journalisation;
9. intégration Drive/GitHub/Gmail/Telegram/BuildHub et futurs adaptateurs;
10. architecture extensible aux agents/API/fournisseurs futurs.

## 2. Sources B — recherche et approfondissement

### 2.1 Universal Chronicle & Memory Fabric

Le registre UCMF001 affine la mémoire vers:
- Chronicle append-only exacte;
- Evidence Vault;
- Canonical Memory;
- Derived Memory;
- indexes reconstruisibles;
- Context Capsules minimales;
- truth status, provenance, supersession et source capability registry;
- aucun full-history replay dans chaque prompt.

Le téléphone ne doit pas "résumer toute la Bible" à chaque action. Le hot path doit être borné:
`INPUT -> SESSION LOOKUP -> REVISION CHECK -> HOT CAPSULE -> DURABLE PREFLIGHT -> DISPATCH`.

### 2.2 Android — conclusions retenues

Recherche officielle Android:
- WorkManager: travail durable/rejouable sous contraintes; pas chemin sub-seconde permanent.
  https://developer.android.com/reference/androidx/work/WorkManager
- Room/SQLite: stockage local transactionnel robuste.
  https://developer.android.com/jetpack/androidx/releases/room
- Foreground service: seulement pour travail perceptible/continu; types explicites requis sur Android moderne.
  https://developer.android.com/develop/background-work/services/fgs
  https://developer.android.com/develop/background-work/services/fgs/service-types
- NSD/mDNS: publicité/découverte de services sur LAN.
  https://developer.android.com/reference/android/net/nsd/NsdManager
- Wi-Fi Direct service discovery: chemin peer-to-peer quand aucun LAN/hotspot utilisable.
  https://developer.android.com/develop/connectivity/wifi/nsd-wifi-direct
- Bluetooth/BLE: permissions SCAN/ADVERTISE/CONNECT et CDM lorsque pertinent.
  https://developer.android.com/develop/connectivity/bluetooth/bt-permissions
- ConnectivityManager.NetworkCallback: adaptation aux changements réels de réseau.
  https://developer.android.com/reference/android/net/ConnectivityManager.NetworkCallback
- Dedicated device / DPC: option avancée pour un téléphone volontairement entièrement dédié; ce mode exige provisioning dédié et peut nécessiter reset/QR enrollment.
  https://developer.android.com/work/dpc/dedicated-devices/

### 2.3 Décision d'architecture Android

Le téléphone dédié n'est plus "client Android + relay".

Il devient une **appliance BCP Edge/API de premier rang**:

```
BLESSING / CLIENTS
       |
       v
+------------------------+
| B-EDGE PHONE APPLIANCE |
|------------------------|
| Local API server       |
| Chronicle/outbox       |
| Project memory         |
| Context builder        |
| Scheduler/DAG          |
| Local task engine      |
| Error/recipe ledger    |
| Resource governor      |
| Network route manager  |
| Telegram relay         |
| NSD/WiFiDirect/BLE     |
| Update/rollback agent  |
+-----------+------------+
            |
   +--------+--------+
   |                 |
   v                 v
PC/Windows Worker   Nexus/remote APIs
heavy/tool work     optional outbound paths
```

### 2.4 Modes du téléphone

**STANDARD_DEDICATED**
- application normale, permissions justifiées;
- foreground service visible;
- battery-unrestricted optionnelle;
- WorkManager pour reconcile/maintenance;
- Room/SQLite durable;
- NSD + Wi-Fi Direct + BLE de présence/contrôle;
- aucune exigence root.

**FULLY_MANAGED_OPTIONAL**
- uniquement si le bénéfice est mesuré et l'utilisateur accepte le provisioning;
- Device Owner/DPC possible sur appareil dédié;
- permet une gestion plus stricte du cycle de vie et du mode kiosque/dédié;
- n'est jamais présenté comme root;
- factory reset/provisioning peut être requis: donc gate humain explicite et réversible seulement via plan de migration.

**ROOT/LAB**
- hors baseline;
- jamais requis pour atteindre le produit principal;
- ne peut être étudié que séparément après inventaire modèle/bootloader/Knox/risques et décision explicite.

## 3. Sources C — feedback accumulé

C rend obligatoires les invariants suivants:

1. arrêter la sous-utilisation du téléphone 4 Go / 64 Go;
2. PC = nœud Windows/calcul lourd, pas centre obligatoire de toute communication;
3. ancien téléphone sans SIM doit rester utile via Wi-Fi/LAN/hotspot/P2P/BLE;
4. réduire les données mobiles consommées par le PC;
5. aucune succession de micro-bêtas installables;
6. une version utilisateur doit être un incrément cohérent couvrant plusieurs exigences;
7. Windows/Android doivent être simulés avant tout clic utilisateur techniquement simulable;
8. interface visuelle serveur mature, pas simple écran "connecté";
9. onboarding permissions fonctionnel et explicatif;
10. Gmail START/END comme surface humaine primaire détaillée;
11. ChatGPT = pointeur après END provider-ack;
12. tranche = 25 minutes, cible 23 min travail + 2 min closeout;
13. normal closeout sans dépendance à automation/watchdog;
14. label Gmail `BCP`;
15. Telegram secondaire mais résilient;
16. `BCPGO BCP` recharge tout sans demander de réexpliquer;
17. aucune fausse déclaration de succès;
18. Drive/GitHub/receipts/readback servent de preuve durable.

## 4. Architecture cible consolidée

### 4.1 Autorité

Court terme:
- GitHub main + writer fence = source canonique code/spec;
- BCP Windows demeure writer canonique existant;
- B-EDGE monte en capacité sans split-brain.

Migration cible:
- B-EDGE devient coordinator logique primaire;
- PC devient worker fenced;
- authority epoch/fencing et receipts empêchent deux heads concurrents;
- migration explicite, réversible et testée.

### 4.2 Data plane local

Le téléphone maintient localement:
- Room/SQLite;
- project registry;
- event ledger;
- outbox;
- receipts/idempotency;
- context capsule cache;
- provider/quota cache;
- error/recipe ledger;
- route/network state;
- node health;
- bounded content cache.

### 4.3 Transport plane

Ordre adaptatif:
1. LAN authentifié/chiffré lorsque disponible;
2. Wi-Fi Direct quand LAN absent/isolé;
3. BLE pour découverte, présence et contrôle léger;
4. USB/RNDIS/ADB uniquement comme fallback de maintenance explicitement qualifié;
5. Nexus/Internet sortant lorsque nécessaire;
6. aucune exposition Internet entrante directe du téléphone.

Le produit doit distinguer:
- disponibilité locale;
- disponibilité Internet;
- réseau mesuré/non mesuré;
- captive portal;
- état route Telegram;
- état PC;
- coût data estimé.

### 4.4 Communication plane

Gmail:
- START provider-ack avant travail;
- END provider-ack + SENT readback avant réponse ChatGPT;
- delivery_key idempotent;
- label BCP.

Telegram:
- witness/cockpit secondaire;
- direct PC si sain;
- relay téléphone/Nexus si qualifié;
- queue durable si aucun uplink;
- succès seulement sur provider receipt.

ChatGPT:
- raisonnement/interactivité;
- jamais source de vérité unique;
- pointeur seulement après END.

## 5. Interface B-EDGE cible

L'UI doit devenir un véritable **cockpit de serveur**.

Écran Accueil:
- rôle actuel: EDGE_ONLY / PC_AVAILABLE / MEMORY_PRESSURE / RECOVERY;
- santé téléphone;
- PC/Telegram/Nexus;
- prochain travail;
- action humaine éventuelle.

Écran Serveur:
- API locale;
- port/identité;
- sessions;
- clients appairés;
- authentification;
- état TLS;
- uptime/restarts.

Écran Réseau:
- Wi-Fi actuel;
- Internet validé;
- metered/data saver;
- NSD;
- Wi-Fi Direct;
- BLE;
- route active;
- bytes TX/RX par route.

Écran Files & Jobs:
- pending/running/hold/retry/completed;
- DAG;
- idempotency;
- receipts.

Écran Mémoire:
- HOT/WARM/COLD;
- cache utilisé;
- DB;
- Chronicle;
- context capsules;
- compaction/index.

Écran Permissions:
- chaque permission avec raison;
- accordée/refusée;
- lien système si réglage spécial;
- battery optimization;
- optional dedicated-device mode.

Écran Diagnostics:
- erreurs;
- transport outage;
- last successful Telegram/Gmail relay;
- recovery timeline;
- export sanitized report.

## 6. Anti-micro-bêta release gate

Aucun nouvel APK utilisateur ne doit être publié uniquement parce qu'un sous-problème est corrigé.

Un incrément installable doit:
1. avoir un coverage manifest A+B+C;
2. fermer un lot cohérent de P0;
3. exécuter simulation Android install/launch/navigation/permissions;
4. exécuter tests Windows/protocole;
5. prouver update in-place;
6. prouver rollback;
7. avoir SHA/signature/readback Drive;
8. expliciter les gaps non bloquants.

## 7. Scoring de couverture

Source machine: `.project-memory/ABC_REQUIREMENTS_INDEX.json`.

Échelle:
- 0 = missing
- 1 = designed/researched
- 2 = implemented partial/candidate
- 3 = qualified CI/process
- 4 = field verified

R77 baseline:
- exigences cataloguées: **45**
- maturité pondérée: **57.8%**
- implémenté/candidat ou mieux: **86.7%**
- qualifié CI/process ou mieux: **42.2%**
- strictement field-verified au niveau de l'exigence complète: **2.2%**

Interprétation:
- le problème principal n'est pas l'absence totale de code;
- le problème est l'écart entre nombreuses briques candidates et un produit intégralement qualifié/field-proven;
- donc priorité = intégration verticale cohérente + qualification, pas micro-bêta supplémentaire.

## 8. Prochain vertical slice obligatoire

Le prochain produit téléphone cohérent doit fermer ensemble:
1. authenticated encrypted LAN transport;
2. phone-local API + auth;
3. durable Room state;
4. local scheduler/task engine;
5. context builder minimal;
6. resource governor;
7. route manager LAN/WiFiDirect/BLE;
8. Telegram store-forward relay;
9. mature server dashboard;
10. permission onboarding;
11. boot/process-kill recovery;
12. Android emulator/UI/permission test;
13. PC protocol compatibility;
14. Drive signed CURRENT publication;
15. field telemetry readback.

Avant ce slice, aucune installation utilisateur supplémentaire n'est nécessaire.

## 9. Règle de continuité

Toute conversation qui reçoit `BCPGO BCP` charge d'abord:
- `.project-memory/ABC_REQUIREMENTS_INDEX.json`;
- ce document;
- `docs/BCP_ABC_COVERAGE_MATRIX_R77.md`;
- les politiques communication/cadence;
- `project_state.json`;
- `API_PROJECT_CONTINUITY.md`;
- writer fence;
- manifests release.

Elle reprend le **next uncommitted action** contre A+B+C, sans demander à l'utilisateur de reconstituer l'ancien chat.
