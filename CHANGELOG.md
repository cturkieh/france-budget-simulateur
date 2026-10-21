# Changelog — moteur france-budget-simulateur

Versions publiées : tags git (`vX.Y.Z`). Ce fichier commence à la v0.6.8 ;
l'historique antérieur est décrit dans les messages de tags et dans
`docs/METHODOLOGIE.md` (encadrés « Corrigé en v0.6.x »).

## v0.6.10 — contre-audit externe V2 : six réserves fermées (non publiée)

**Ce qui change pour le lecteur** : des centièmes de point, sur cinq programmes.
Mesure à deux sous-processus (v0.6.9 contre v0.6.10), dix scénarios publiés et
statu quo :

- Dette 2035 : RN 152,71 → 152,76 (+0,05) ; LFI 151,75 → 151,72 (−0,03) ;
  Renaissance 151,63 → 151,66 (+0,03 : +0,02 par l'éviction, +0,01 par la
  désindexation) ; PS 144,73 → 144,71 (−0,02) ; Institut Montaigne
  (compétitivité) 127,59 → 127,60 (+0,01) ; Écologistes inchangé à l'affichage
  (−0,0004 en pleine précision).
- Dette 2030 : RN 129,68 → 129,70 ; LFI 126,90 → 126,89 ; Renaissance
  130,11 → 130,12 ; PS 125,93 → 125,92 ; IM compétitivité 120,50 → 120,51.
  Déficit 2030 : Renaissance −6,53 → −6,54, PS −5,68 → −5,67. Croissance,
  chômage, Gini et pouvoir d'achat 2030 : inchangés à l'affichage.
- Croissance potentielle publiée : une cellule à ±0,20 pt pour sept programmes,
  l'année où naît le bonus d'offre structurelle (2030 : Renaissance
  1,24 → 1,04, IM rabot 0,86 → 1,06). La colonne publie désormais le potentiel
  consommé par l'année, pas celui de l'année suivante.
- Budget 2026 voté et statu quo : identiques au bit. Horizons et LR :
  trajectoires identiques au bit, seul l'arrondi publié du potentiel 2026 passe
  de 1,14 à 1,15 (valeur 1,145 inchangée).
- Écarts maximaux, toutes années et tous scénarios, à l'affichage : Dette/PIB
  0,05 pt (RN 2035) ; Déficit/PIB, Croissance, Chômage et écart de production
  0,01 pt ; Gini, pouvoir d'achat, inflation et compétitivité 0 (pouvoir
  d'achat : 0,008 point d'indice en pleine précision) ; colonnes de potentiel
  0,20 pt.

Chaque mouvement est attribué à un lot : un banc rejoue v0.6.9, chacun des six
lots seul et leur fusion, sur toutes les colonnes des deux tableaux de sortie.
Aucune colonne ne bouge sans lot responsable. V2-04, V2-05 et V2-06 ne changent
aucune sortie. Les effets de V2-01 et V2-03 s'additionnent ; le terme
d'interaction est du second ordre (au plus 2,1 × 10⁻⁴ Md€, sur le PIB nominal
de Renaissance ; 1,4 × 10⁻⁴ Md€ sur sa dette nominale).

### V2-01 — l'éviction lisait une « part » qui n'en était pas une

- **Constat** : la part d'investissement lue par l'éviction divisait des flux
  bruts (Σ |Δdép| des leviers d'investissement) par des flux nets agrégés
  (|Δdép net| + |Δrec net|). Sur le contre-exemple de l'auditeur, +20 Md€
  d'investissement financés par −10 Md€ de dotations donnaient 2,0 ; IM
  compétitivité atteignait 2,605. L'intensité devenait alors négative et
  l'« éviction » soutenait l'expansion.
- **Correction** : part = Σ_invest max(Δdép, 0) / Σ_flux max(−f, 0), soit la
  part d'investissement productif de l'expansion brute, levier par levier, dans
  la convention des impulsions keynésiennes (`flux_par_levier`, partagé avec
  elles). Elle est dans [0 ; 1] par construction, sans bornage. L'éviction est
  ≤ 0 par contrat (`RuntimeError` sinon) et continue en l'effort : en v0.6.9,
  la croissance sautait de 0,002 pt quand l'effort net s'annulait.
- Coefficients nommés (`EVICTION_INTENSITE_INVESTISSEMENT`,
  `EVICTION_SURCROIT_NON_PRODUCTIF`, `EVICTION_SEUIL_DETTE`, constants.py) et
  déclarés sans source publiée. METHODOLOGIE et EXPLICATION_MODELE_ECONOMIQUE
  corrigées ; la seconde citait une « littérature standard » inexistante.
  `part_depenses`, sans lecteur depuis v0.6.7, est retirée ; la part devient une
  entrée obligatoire de `calculate_growth`.
- **Tests** : `tests/test_eviction_composition_v0610.py` (37 tests : part dans
  [0 ; 1] sur paires aux bornes, 200 tirages et scénarios publiés, signe,
  continuité, site d'appel, garde « aucun scénario publié sous 100 % de
  dette »). 22 mutants non équivalents sur 22 tués.
- **Écart** : seule source des mouvements de dette, déficit, croissance et
  chômage de RN, LFI et PS, et de la majeure partie de ceux de Renaissance et
  d'IM compétitivité.

### V2-02 — les colonnes de potentiel publiaient l'année suivante

- **Constat** : `Croissance_Potentielle_Totale %`, `Croissance_Potentielle %`
  et `Bonus_Potentiel_Supply %` relisaient l'état après la clôture d'année,
  donc le potentiel préparé pour t+1 (recherche publique à 20 Md€, 2030 :
  1,248 % publié pour 1,048 % consommé).
- **Correction** : photographie `potentiel_de_l_annee()` prise avant
  `update_potential_growth` ; la récurrence de l'écart de production et les
  colonnes publiées lisent cette photographie. L'identité de l'écart de
  production se reconstruit depuis les seules sorties. Arrondi Python uniforme
  sur toutes les années de ces colonnes (numpy dès 2027 auparavant).
- **Tests** : `tests/test_potentiel_publie_v0610.py` (88 tests).
- **Écart** : colonnes de potentiel seules (sept programmes, une cellule à
  ±0,20 pt ; arrondi 2026 de Horizons, LR, IM compétitivité). Dette, déficit,
  croissance, chômage, Gini, pouvoir d'achat et écart de production : identiques
  au bit.

### V2-03 — désindexation : ratio exact

- **Constat** : chaque revalorisation sous-indexée multipliait la masse par
  1 − δπ. La masse de l'année étant déjà pleinement revalorisée, le dénominateur
  manquait : une masse revalorisée de 100 à 102 puis gelée économisait 2,04 au
  lieu de 2.
- **Correction** : facteur (1 + (1 − δ)π)/(1 + π), pour les pensions et les
  prestations, en sous- comme en sur-indexation. Part indexée 0,86 inchangée ;
  l'ancrage OFCE passe de 3,70 à 3,66 Md€, dans sa tolérance.
- **Tests** : `tests/test_desindexation_exacte_v0610.py` (32 tests, dont le test
  rouge du contre-audit et des propriétés).
- **Écart** : seuls Renaissance (+0,01 pt de dette en 2030 et 2035) et IM
  compétitivité (+0,01 pt en 2032-2034) bougent ; les autres programmes et le
  statu quo sont identiques au bit.

### V2-04 — un nom de paramètre inconnu passait en silence

- **Constat** : `{"tva_rate": {"tauxx": 0.25}}` était ignoré, le levier
  appliquait son défaut et le résultat restait déclaré valide. Même silence
  pour une clé admise mais masquée par un mode exclusif
  (`{"taxe_superprofits": {"intensite": 0.5, "taux": 0.05}}`).
- **Correction** : porte des noms, puis porte des modes exclusifs. En strict,
  rejet 422 (`ParametreInconnu`, `ParametreIgnore`) ; en tolérant, le nom est
  ignoré, signalé dans `report.warnings` et `report.valid` passe à `false`.
  Contrat dérivé du code : module généré `engine/_noms_parametres.py`
  (`NOMS_PARAMETRES_ADMIS`, `MODES_EXCLUSIFS`), garde `--noms --check`. Le
  scanner de discontinuités ne balaye plus un paramètre masqué.
- **Tests** : `tests/test_noms_parametres_v0610.py` (90),
  `tests/test_modes_exclusifs_v0610.py` (31), `tests/test_noms_parametres_sync.py`
  (16, rouge et vert de la garde).
- **Écart** : aucune sortie. Un client qui envoyait des clés jamais lues reçoit
  désormais `valid: false`, avec un résultat inchangé.

### V2-05 — reproductibilité de la suite hors de macOS/Linux

- **Constat** : sous Windows sans `PYTHONUTF8`, des snapshots étaient relus en
  cp1252 et le golden master standalone échouait, moteur intact.
  `test_api_safety` lisait `app.routes` : avec fastapi 0.142.2, permis par
  `requirements.txt`, il annonçait à tort l'absence de `/scenarios` et
  `/simulate` et laissait passer un endpoint interdit.
- **Correction** : tout fichier texte ouvert en UTF-8 explicite ; tout Python
  enfant lancé par `tests/sous_processus.py`, qui fixe la sortie en UTF-8 des
  deux côtés du tube. `test_api_safety` teste le contrat publié
  (`/openapi.json` et appels réels).
- **Tests** : `tests/test_encodage_portable.py` (42 : gardes statiques sur tout
  le dépôt, rejeux sous une locale cp1252 simulée), `tests/test_api_safety.py`
  (35).
- **Écart** : aucune sortie.

### V2-06 — METHODOLOGIE décrivait deux états du recalibrage

- **Constat** : un paragraphe gardait les sommes analytiques de la v0.6.6 comme
  effet courant et tenait le recalage INVEST pour ouvert ; le garde-fou
  d'autofinancement était énoncé comme une loi sur tout investissement.
- **Correction** : la somme analytique `k × Σ profil` (2,38, inchangée depuis
  v0.6.6) est distinguée de l'effet effectif mesuré (1,41 % à 4 ans) ; le
  garde-fou est énoncé à sa portée réelle (le choc de calibrage ne
  s'autofinance pas dans le banc de référence) ; solde budgétaire (13 % du coût
  récupéré, et non 11 %), mesure en volume (0,47), dette nominale et ratio
  dette/PIB distingués.
- **Tests** : `tests/test_methodologie_recalibrage_v0610.py` (13) et
  `tests/test_multiplicateurs_centraux_v067.py` : chaque chiffre publié est
  recalculé et lié à la doc. Ils restent verts après fusion : les chiffres
  publiés du banc d'investissement tiennent avec l'éviction corrigée.
- **Écart** : aucune sortie.

### Intégration

- Un conflit textuel (`engine/growth.py` : classe `PotentielAnnee` de V2-02 et
  fonctions d'éviction de V2-01, ajoutées au même endroit) : les deux sont
  conservées.
- Deux conflits sémantiques, sans conflit textuel, rattrapés par la suite :
  la garde des noms admis (V2-04) lançait son Python enfant hors du lanceur
  commun (V2-05) ; les tirages aléatoires de l'éviction (V2-01) envoyaient une
  clé masquée, rejetée en strict par V2-04. Correction dans les tests seuls.
- Suite complète : 2867 passed, 48 skipped, en tolérant comme en strict.
  Scanner de discontinuités, dette 2035 puis pouvoir d'achat 2035 :
  450 balayages × 41 points chacun, 0 saut > 0,001 pt.

### Snapshots régénérés (une fois, après fusion)

- `tests/snapshots/golden_master_v1.json` : 58 cellules sur 880. Dette/PIB %
  (RN 7, LFI 7, Renaissance 8, PS 6, IM compétitivité 9), Déficit/PIB % (RN 4,
  LFI 3, Renaissance 5, PS 4, IM compétitivité 1), Chômage % (LFI 1),
  Croissance % (LFI, PS, IM compétitivité : 1 chacun) ; |Δ| ≤ 0,05 pt. Cause :
  44 cellules V2-01 seul, 10 V2-01 et V2-03, 4 somme des deux qui franchit un
  demi-centième.
- `tests/snapshots/standalone_master_v1.json` : 3 cellules de Dette/PIB % à
  −0,01 ; transition_ecologique 2035 (V2-01), prestations_indexation 2034 et
  2035 (V2-03).
- Non régénérés : `scenario_deltas_baseline.json` (ancre de tolérance capturée
  en v0.6.7, jamais régénérée depuis, verte) ; `measure_registry.json`
  (inchangé). Les colonnes de potentiel (V2-02) ne figurent dans aucun
  snapshot.

### Décisions laissées au mainteneur

- Éviction (V2-01) : valider la convention « part de l'expansion »
  (METHODOLOGIE écrit « convention retenue » et ne revendique pas d'arbitrage) ;
  sourcer ou recalibrer 0,002, 0,006 et le seuil de 100 %, aujourd'hui sans
  source publiée ; lisser la marche « dette > 100 % » (aucun scénario publié ne
  la franchit, minimum 114,7 %, garde CI) ; `collectivites.investissement`
  reste compté non productif (périmètre v0.6.0).
- Désindexation (V2-03) : re-dériver `RETRAITES_PART_MASSE_INDEXEE` de 0,86 à
  0,87 dans une release de paramètres ; l'ancrage OFCE est à 0,006 Md€ de sa
  tolérance ; le niveau de la masse de référence suit l'indice mixte du moteur,
  pas le seul taux légal de revalorisation.
- Arrondis (V2-02) : les autres colonnes publiées en numpy.float64 gardent
  l'arrondi numpy (±0,01 possible sur un demi-centième) ; ajouter ou non les
  colonnes de potentiel au golden master.
- API (V2-04) : un seul défaut signalé par levier en strict ; domaine de
  `chomage_alloc.montant` conservé tant que le mode hérité est public.
- Reproductibilité (V2-05) : publier les dix scénarios comme fixtures
  versionnées du dépôt public (générateur, sha256, garde `--check`) ; épingler
  l'environnement (job CI windows-latest sans `PYTHONUTF8`, `constraints.txt`
  partagé CI/Render, job hebdomadaire « dépendances récentes ») ; la cascade
  d'encodages de `budget_simulator/config.py` (utf-8, latin-1, cp1252) a une
  branche morte.
- Ancre `scenario_deltas_baseline.json` : la recapturer ou non (RN, dette
  2035 : 1,14 pt d'écart consommé sur 1,5 de tolérance).
- Documentation périmée hors lots : § 2 d'EXPLICATION_MODELE_ECONOMIQUE
  (« effet confiance Alesina », supprimé en v0.6.0), équation de l'écart de
  production v0.6.6 et fourchette de potentiel dans le même fichier, compteurs
  de tests de README et CONTRIBUTING, mention nominative d'un arbitrage dans
  constants.py (bloc baisse d'impôts), test daté
  `test_v069_tables_livrees_vides__a_retirer_en_v0610` (tables toujours vides
  en v0.6.10).

## v0.6.9 — conjoncture observée : le mécanisme, sans valeur (non publiée)

**Ce qui change pour le lecteur** : rien. Toutes les sorties sont identiques au bit
(golden masters inchangés, sans régénération ; empreinte pleine précision des dix
scénarios publiés et du statu quo identique à la v0.6.8 : sorties non arrondies,
trace du pouvoir d'achat, état final).

**Ce que la case permet** : représenter un choc DÉJÀ CONSTATÉ par la statistique
publique, que le moteur ne savait pas dire — sa croissance part toujours du
potentiel et y revient. Deux tables par année calendaire, identiques pour tous les
scénarios, vides dans cette version (`budget_simulator/constants.py` § CONJONCTURE
OBSERVÉE ; liste unique des noms : `ConjonctureObservee`) :

- `CHOCS_DEMANDE_OBSERVES` : points de croissance ajoutés à l'année par
  l'orchestrateur, après `calculate_growth` et avant tous ses lecteurs (PIB, Okun,
  recettes, écart de production, hystérèse du potentiel). Choc de demande : la
  Phillips le lit l'année suivante, le rappel vers le potentiel le referme ensuite ;
  ni impulsion budgétaire, ni choc d'offre ; hors du filet [−3,5 % ; +2,5 %] de la
  croissance modélisée (une donnée constatée n'est pas écrêtée).
- `COIN_PRIX_CONSOMMATION` : prix de la consommation − prix du PIB, cumulé en niveau
  (`engine/rdb.py`, nouvel argument `facteur_prix_conjoncture`, neutre par défaut ;
  champ de trace du même nom). Seul le prix de l'indice de pouvoir d'achat le voit :
  la colonne « Pouvoir d'Achat » et la colonne détaillée `Prix_Consommation`, que
  l'API sert dans `details` ; déflateur, recettes, dépenses indexées, dette, Gini et
  compétitivité, non.
- **Garde** (zéro échec silencieux) : année hors des années simulées (2026-2035),
  clé non entière, valeur non numérique, non finie ou au-delà de ±0,03 →
  `ValueError` à l'import. ±0,03 est le domaine du MÉCANISME : le choc n'est jamais
  écrêté, mais au-delà les filets du modèle qui le reçoit mordent en silence (mesuré :
  136 cas sur 220 à ±0,10 ; à ±0,03, 7 cas, tous sur le rebond de croissance de
  l'année suivante, aucun sur une borne de sortie) ; un choc de l'ampleur de 2020
  n'est donc pas encodable tel quel. À chaque simulation, les tables sont relues dans
  le module, revalidées et figées ; une table devenue invalide après l'import lève
  `RuntimeError` (défaut du serveur : l'API répond 500 et journalise une ERROR, pas
  un 422 « paramètres invalides »).
- **Preuves** (`tests/test_conjoncture_observee_v069.py`, écrits rouges avant le
  code) : 141 tests sur douze cas (dix scénarios publiés, statu quo, programme
  mixte) quand le `scenarios.json` du dépôt parent est présent ; la CI du dépôt
  public seul en exécute 61, sur deux cas (statu quo, programme mixte). Tables
  injectées en test, jamais dans `constants.py` ; tests des tables livrées écrits
  pour valoir vides ou remplies (un seul test daté, à retirer en v0.6.10). Choc =
  exactement le choc à son année chez tous les lecteurs de la croissance, dans le
  niveau du PIB, sans écrêtage, rien avant, rien de direct après ; écart de
  production, Okun et Phillips de l'année suivante rejoués à la main ; aucune
  impulsion budgétaire créée ; aucun filet supplémentaire sous les tables livrées ;
  coin = seule la colonne « Pouvoir d'Achat » bouge, de 1 / Π(1 + coin) ; tables
  figées pendant une simulation ; contrat HTTP 500 + ERROR ; `calculate_growth` et
  `calculate_unemployment` inchangées ; un seul point d'application
  (l'orchestrateur). Dix mutations ciblées du mécanisme sont toutes détectées.

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
