# Changelog — moteur france-budget-simulateur

Versions publiées : tags git (`vX.Y.Z`). Ce fichier commence à la v0.6.8 ;
l'historique antérieur est décrit dans les messages de tags et dans
`docs/METHODOLOGIE.md` (encadrés « Corrigé en v0.6.x »).

## v0.6.8 — indice de pouvoir d'achat « RDB-moteur » (non publiée)

**Ce qui change pour le lecteur** : l'indice de pouvoir d'achat suit désormais la
définition de l'INSEE — revenu disponible brut (RDB) des ménages, déflaté par le prix
de leur consommation, par unité de consommation (UC), base 100 en 2025. Seule la
colonne « Pouvoir d'Achat » change ; toutes les autres sorties sont bit-identiques
(44 scénarios vérifiés : 10 publiés, statu quo, 33 leviers isolés).

- **Formule** (`budget_simulator/engine/rdb.py`) : RDB = part privée au PIB nominal +
  rémunérations publiques nettes (volume tendanciel du statu quo × déflateur, identiques
  en réel pour tous les scénarios) + euros des mesures de l'année par canal ; prix = déflateur × coin de fiscalité indirecte ;
  indice de NIVEAU (l'année t ne lit que les grandeurs de t).
- **Contrat des handlers** : chacun des 33 handlers émet ses montants par canal ménages
  (clé `menages` : prélèvements directs, indirects, prestations, rémunérations
  publiques, salaires privés). Un handler qui déplace des euros sans canaux échoue
  bruyamment.
- **Arbitrages du mainteneur** : impôts sur les entreprises et dépense publique sans
  effet direct (par la croissance) ; hausse de rémunération des agents en place comptée
  une fois, à sa part nette (0,535) ; TVA et accises répercutées à 100 % à la hausse,
  50 % à la baisse, pour leur seule part payée par les ménages ; seules les prestations
  EN ESPÈCES entrent au RDB (santé et APA, transferts en nature, à zéro) ; indice par UC.
- **Disparaissent** : les vingt coefficients forfaitaires `pouvoir_achat` (un seul
  nommé, aucun sourcé, transmission de 2 % à 175 % des euros), leur réémission annuelle
  (un niveau composé en croissance), l'atténuation × 0,5 à partir de 2027, le double
  compte dépense publique + croissance. Constantes retirées : `RETRAITES_PA_GEL_TOTAL`,
  `COEFF_PA_NICHES_SOCIALES_TGE`.
- **Sources** (constantes nommées, `constants.py` § INDICE DE POUVOIR D'ACHAT) : INSEE
  (RDB 2024-2025, taux d'épargne, unités de consommation, Note de conjoncture de juin
  2026), FIPECO (masse salariale publique 2025 ; taxes foncières 2024, part ménages 26,1 /
  42,9 Md€), service-public.fr F468, DG Trésor via le Sénat (part de la TVA nette pesant sur
  la consommation des ménages, 56,0 %, pour la TVA énergie), Conseil général de l'économie
  (part ménages de la composante carbone, 5,3 / 8,2 Md€), Sénat avis PLF 2025 (AAH 15,9 Md€),
  Benzarti, Carloni, Harju & Kosonen (JPE 2020), Carbonnier (JPubE
  2007), Benzarti & Carloni (AEJ:EP 2019). Deux valeurs non sourcées en ligne, signalées :
  part des primes dans le brut public (~25 %), part nette du brut privé (0,78).
- **Effet** (2030, v0.6.7 → v0.6.8) : statu quo 106,0 → 103,6 ; étendue des dix
  scénarios 20,2 → 12,2 pt (2035 : 22,1 → 8,8). Tableau complet et lecture :
  `docs/METHODOLOGIE.md` § Indice de pouvoir d'achat.
- **Limite déclarée** : statu quo 2026 à +0,8 % par UC contre −0,7 % prévu par l'INSEE
  (juin 2026) — écart porté par la croissance et l'inflation 2026 du moteur, antérieures
  au choc énergétique de 2026, pas par le passage au RDB (recalage macro : release
  dédiée).
- **Outils** : `scripts/scan_discontinuites.py --colonne "Pouvoir d'Achat"` scanne
  l'indice (0 saut > 0,001 pt sur 460 balayages).

### Revue passe 1 (correctifs, même version)

Seule la colonne « Pouvoir d'Achat » bouge, de cinq scénarios publiés (golden masters :
toutes les autres colonnes identiques au bit, 44 cas) ; balayage PA : 0 saut > 0,001 pt.

- **M1, rabot uniforme** : la santé (250 Md€) et l'APA sont des transferts EN NATURE,
  hors RDB — le rabot les comptait comme un revenu retiré, alors que le levier santé ne
  compte que les franchises. Désormais un euro de santé vaut zéro de RDB dans les deux
  leviers (test transversal) ; dans « dépendance » (APA + AAH), seule l'AAH (15,9 Md€) reste
  un revenu. IM rabot 2030 : 94,8 → 95,9 (2035 : 99,4 → 100,6).
- **M2, fiscalité indirecte** : la part ménages dépend de la BASE du levier et c'est le
  handler qui l'applique. TVA taux normal : 1,0 (sa base est déjà la consommation des
  ménages ; la part TVA totale 0,560 la réduisait deux fois) ; TVA énergie : 0,560 (base =
  toute l'énergie, approximation déclarée) ; taxe carbone : 5,3 / 8,2 = 0,646 (CGE). Effet
  sur les scénarios publiés ≤ 0,02 pt (aucun ne touche la TVA à taux normal).
- **L3, taxe foncière** : seule la part ménages (26,1 / 42,9 Md€, FIPECO 2024) est un
  prélèvement direct ; la part entreprises passe par la croissance (arbitrage 1). LFI, PS,
  Écologistes 2030 : +0,15 à +0,21 pt.
- **L2, mesures « formule »** : côté recettes ou mixte, hors contrat des canaux ménages,
  elles émettent un avis explicite (aucune n'existe au registre : les quatre sont côté
  dépenses, verrouillé par test).
- **L4, tests** : les tests qui recalculaient le code avec ses propres constantes sont
  remplacés par des propriétés indépendantes (valeurs posées à la main depuis la source,
  identité recettes ↔ prix, niveau constant sans composition, part nette redérivée des taux
  légaux).
- **Doc** : effet du passage par UC corrigé (−2,1 pt en 2030, −4,3 en 2035, mesuré ; −2,4 /
  −4,9 publiés à tort) ; « Indice de pouvoir d'achat » devient une section de
  `docs/METHODOLOGIE.md` (ancre des renvois « § Indice de pouvoir d'achat »).
