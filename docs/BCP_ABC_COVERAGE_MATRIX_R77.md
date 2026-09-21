# BCP — Matrice de couverture A+B+C — R77

Cette matrice n'est pas une note marketing. Elle dérive de `.project-memory/ABC_REQUIREMENTS_INDEX.json`.

## Résumé

| Mesure | Valeur |
|---|---:|
| Exigences A+B+C cataloguées | 45 |
| Maturité pondérée (0..4) | 57.8% |
| Implémenté/candidat ou mieux | 86.7% |
| Qualifié CI/process ou mieux | 42.2% |
| Field-verified au niveau de l'exigence complète | 2.2% |

Le produit possède donc beaucoup de briques, mais reste loin d'un produit intégralement prouvé. Cela explique pourquoi des micro-bêtas peuvent donner une impression de faible progression malgré beaucoup de code.

## Gaps P0 à fermer avant prochain install téléphone

1. transport LAN authentifié/chiffré;
2. route EDGE_ONLY réellement indépendante du PC;
3. Context Builder minimal prouvé sur mémoire locale;
4. resource governor stressé sur profil 4 Go / stockage réel;
5. Telegram direct/phone/Nexus avec preuve provider et store-forward;
6. UI serveur complète + navigation/permissions simulées;
7. recovery reboot/process kill;
8. full-node Android exact-head CI;
9. package signé/pinné + Drive CURRENT readback;
10. field telemetry après installation.

## Règle

Toute nouvelle PR produit doit référencer les IDs Axx/Bxx/Cxx affectés.
Toute release doit publier une matrice:
`REQUIREMENT_ID -> IMPLEMENTED -> TESTED_CI -> TESTED_DEVICE -> FIELD_VERIFIED`.

Aucun pourcentage ne peut être augmenté par une simple rédaction de documentation.
