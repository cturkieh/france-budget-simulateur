# Changelog — moteur france-budget-simulateur

Versions publiées : tags git (`vX.Y.Z`). Ce fichier commence à la v0.6.8 ;
l'historique antérieur est décrit dans les messages de tags et dans
`docs/METHODOLOGIE.md` (encadrés « Corrigé en v0.6.x »).

## [v0.8.1] — non publiée (proposée) — release de paramètres « P » : droit en vigueur daté, instantanés régénérés, textes publics, objectifs en part du PIB

**Ce qui change** : des données et des textes, aucune équation ni constante de calcul du moteur, un
champ de `GET /health` (point 4), trois bornes de curseur (point 5) et une forme de calendrier qui étend
le contrat `/simulate` (point 6). (1) Le droit en
vigueur (`budget_simulator/data/droit_en_vigueur.json`) porte sa première valeur datée : la surtaxe
d'IS des grandes entreprises (`is_exceptionnel_tge.montant`), 7,3 Md€ en 2026 dans le fichier (réajustée à
6,8 Md€ en 2026 par l'atterrissage, inchangé), **0 dès 2027** : contribution due au titre des deux
premiers exercices clos à compter du 31 décembre 2025 (loi n° 2026-103, art. 12 ; BOFiP
ACTU-2026-00097) ; le projet de loi de finances pour 2027 (n° 3210), qui la prorogeait, a été
considéré comme rejeté par l'Assemblée nationale le 4 novembre 2026 (T.A. n° 362). Une loi de
finances pour 2027 votée remplacera ce segment. (2) Les taux votés des leviers à taux de la release E
sont inscrits au droit (contrat § 0.9) : `fiscalite_capital` 0,128 et 0,186, `multinationales.taux_tsn`
0,03, `operations_financieres.taux_ttf` 0,004 et `rachats_actions` 0 (la taxe de 8 % en vigueur) ; leurs
paramètres de comportement restent hors du droit. Aucune autre valeur. (3) Les scénarios publiés,
lus dans le `scenarios.json` du dépôt parent, sont ré-encodés sur leurs sources (release P du site :
10 scénarios, un retiré, un ajouté, une source par paramètre dans `scenariosSources.json`).
(4) **Version publiée** : `GET /health` publie `moteur_version` (« v0.8.1 »), lu dans
`budget_simulator.__version__`, source unique du numéro ; la première entrée de ce CHANGELOG doit porter
le même (`tests/test_version_publiee.py`). Un déploiement qui attend une version précise la lit ici ;
depuis le point 6, un site qui envoie la forme de calendrier « valeurs » exige v0.8.1 (v0.8.0 la refuse
en 422). Avant v0.8.1, le champ est absent.
(5) **Bornes hautes sourcées** (décision du mainteneur du 12/11/2026 : les objectifs de dépense qu'un
programme publié écrit en part du PIB ou du RNB sont comptés pour tous ; même règle que
`DMTG_VARIATION_MAX_MD`) : `recherche_publique.budget` 20 → 37 (`RECHERCHE_BUDGET_MAX_MD`),
`transferts_etranger.montant` 10 → 10,5 (`TRANSFERTS_ETRANGER_MAX_MD`), `depenses_publiques.credits_etat`
20 → 28 (`CREDITS_ETAT_MAX_MD`) : le plus haut objectif publié au PIB de 2032 de la référence, arrondi au
pas du curseur supérieur (recherche du secteur public à 1,5 % du PIB, niveau 0,75 % en 2024, MESR-SIES ;
aide publique au développement à 0,7 % du RNB, niveau 0,42 % en 2025, document de politique
transversale annexé au PLF 2027 ; dépense publique culturelle à 1 % du PIB, services culturels des
administrations 0,646 % en 2024, Eurostat COFOG 08.2, en plus de 14,6 Md€ de crédits annoncés). Les
bornes de la première version (20, 10 et 20) n'étaient pas sourcées. Aucun calcul ne change (chaque Md€
du curseur reste un Md€ de dépense, vérifié jusqu'à la borne) ; les bornes basses sont inchangées.
METHODOLOGIE, § « Bornes hautes relevées (v0.8.1) ».
(6) **Calendrier « valeurs »** (`profils`, montants en Md€ seulement) : `{"forme": "valeurs",
"valeurs": {"2028": …, "2029": …}}`, le montant de chaque année du début à une année ≤ 2032, sans lacune,
chacun dans le domaine du paramètre ; la valeur du programme ensuite. Motif : un objectif en part du PIB
se compte, après l'année visée, par un montant qui suit la richesse nationale ; aucune autre forme ne
l'écrit. Mêmes mesures de l'année que les autres calendriers (`_mesures_profilees`) : aucune équation ne
change, égalité au bit avec une rampe aux mêmes valeurs (`tests/test_release_p_calendrier_valeurs.py`).
Refusée aux taux et niveaux, aux coefficients d'indexation et à la recette d'une seule année ; défaut :
422 en strict, entrée ignorée et correction tracée en tolérant. API : `ProfilRequete.valeurs`
(nombres finis stricts, six entrées au plus).

**Ce que cela déplace, prouvé** (instantanés régénérés une seule fois, `BUDGETLAB_REGEN=1 make
snapshot-baseline` et `capture_scenario_deltas.py`, après audit) :
- **attribution au bit** : l'arbre v0.8.1 rejoué sur les scénarios d'avant P redonne le golden master
  historique et le delta de référence de v0.8.0 à l'identique ; en mode cadre, les scénarios d'avant P
  sur le droit SANS valeur datée redonnent le golden master du cadre 2028 et le standalone de v0.8.0 à
  l'identique. Tout écart vient donc des données de P (scénarios) et de la seule valeur datée (droit) ;
- **mode cadre, scénarios de P** : cinq des dix scénarios, en 2032, égalent cellule par cellule
  (déficit, dette, croissance moyenne 2028-2032, chômage, pouvoir d'achat, Gini) le banc de la release P
  (colonne C) ; les cinq autres ont été ré-encodés après les relectures du même jour. Relecture (sept
  paramètres de deux programmes : six d'un programme, `education.salaires` 0 → 4,4 et `education.budget` 65 → 62 en rampe,
  `cotisations_salariales.baisse_points` 1,4108 → 1,2965, `impots_production.montant` 80,6742 → 82,
  `immigration.ame` 0,4381 → 0,4597, `cotisations_patronales.taux` 0,2525 → 0,2526 ; un d'un autre,
  `prestations_menages.solidarite` 6,06 → 8,89). Leur écart au banc C, attribué paramètre par
  paramètre (chaque changement seul sur l'ancien encodage ; reste d'interaction de l'ordre de
  l'arrondi des sorties) : déficit 2032 +0,09 et −0,06 point, dette 2032 −0,21 et +0,10 point ;
  contre-relecture (sept paramètres de quatre programmes : `cotisations_patronales.taux` 0,2526 → 0,2538,
  `education.budget` 62 → 62,8, `fraude_fiscale.effort` 0,385 → 0,4068 et `fraude_sociale.effort`
  0,318 → 0,3369 pour un programme ; `impot_societes.taux` 0,264 → 0,2639 ; `recherche_publique.budget`
  19,15 → 19,65 ; `collectivites.dotation` 116,6 → 109,1, chacun pour un programme). Écarts 2032 attribués
  de même : déficit +0,04, 0,00, −0,01 et +0,17 point, dette −0,12, 0,00, +0,01 et −0,38 point (le
  premier chiffre cumule les quatre paramètres du même programme, reste d'interaction ≤ 0,02) ; seul
  instantané hors golden masters déplacé : le delta de référence d'un des trois scénarios qu'il suit
  (0,01 à 0,02 point), et celui d'un deuxième sur une cellule (0,01) ; standalone identique au bit ;
  dernière passe (objectifs de dépense écrits en part du PIB ou du RNB comptés pour tous, points 5 et 6 :
  sept paramètres de quatre programmes en calendrier « valeurs », `recherche_publique.budget` pour trois
  programmes, `transferts_etranger.montant` pour trois, `depenses_publiques.credits_etat` pour un ; et,
  pour un programme, deux montants sans calendrier écrit passés en rampe, `collectivites.dotation` et
  `education.salaires`). Écarts 2032 attribués de même, par programme : déficit −0,97, −0,50, −0,37 et
  +0,02 point, dette +1,74, +1,28, +1,05 et −0,03 point. Le premier cumule trois objectifs (recherche
  −0,38 et +0,30, dépense culturelle −0,27 et +0,42, aide au développement −0,37 et +1,04) ; le deuxième
  deux objectifs et deux rampes (aide au développement −0,36 et +0,99, recherche −0,08 et +0,01, rampes
  −0,01 et +0,14, −0,07 et +0,13) ; reste d'interaction ≤ 0,05 point. Delta de référence : deux des trois
  scénarios suivis bougent (jusqu'à +7,61 points de dette 2035 en mode historique pour l'un, ≤ 0,04 pour
  l'autre) ; standalone identique au bit ; enfin, pour ce même programme, `education.salaires` s'applique
  dès 2028 (règle commune : un taux ou un salaire sans calendrier écrit s'applique dès 2028 ; calendrier
  « rampe » retiré) : déficit 2032 +0,06 point, dette 2032 −0,14 point en mode cadre ; golden master
  historique, delta de référence, standalone et pouvoir d'achat 2029 identiques au bit (un calendrier ne
  s'applique qu'en mode cadre) ;
  l'ancien encodage rejoué sur cet arbre redonne les instantanés précédents au bit ; la référence passe de −7,17 à −7,34 % de déficit 2032 et de 138,04 à 138,52 %
  de dette ; en 2027, statu quo à −5,86 % de déficit (−5,63 avant) ;
- **valeur datée seule** (scénarios d'avant P, mode cadre) : de −0,01 à −0,03 point de déficit 2032 et
  de +0,05 à +0,15 point de dette 2032 par scénario (2027 seule : un scénario qui écrit la surtaxe
  l'impose dès 2028) ; standalone : seul le mini-scénario simulé en mode cadre (recette exceptionnelle)
  bouge ;
- **garde-fou du pouvoir d'achat 2029** : valeurs re-figées après audit dans
  `tests/snapshots/pa_2029_figes.json` (données figées, jamais régénérées par un script ; elles
  quittent le code du test), y compris les encodages mis à jour par la relecture (−0,1 et +0,2 point),
  par la contre-relecture (−0,1 et −0,2 point) puis par la dernière passe (+1,3, +0,3, −0,1 et +0,1
  point).

**Conséquences à connaître** :
- **Mode historique** (sans `annee_debut`) : la référence porte le droit de 2028 dès 2026 (surtaxe à
  0), et une recette d'une seule année y reste refusée (422 en strict, levier retiré en tolérant). Les
  tests et le golden master historique évaluent chaque scénario publié tel que ce mode l'accepte
  (`run_scenarios_full.pour_le_mode`). Le site sert le mode cadre.
- **Rapport** : sur un levier à taux inscrit au droit, un bloc neutre COMPLET (taux et paramètres de
  comportement à leur défaut, ce qu'envoie le simulateur du site) laisse toutes les sorties identiques
  au bit mais fait figurer le levier dans `cadre.leviers_modifies` et `cadre.mesures_effectives` (règle
  v0.7.2 « présent = imposé ») et déclenche la composition à trois mondes. Constaté, documenté
  (METHODOLOGIE, test `test_bloc_neutre_d_un_levier_inscrit_au_droit`), non corrigé dans une release de
  paramètres.

**Tests adaptés** (aucune tolérance élargie) : harnais `droit_sans_valeurs_datees` pour les tests d'un
mécanisme qui suppose un droit constant (atterrissage, mesures de l'année, élasticité des recettes,
rampe, éviction de référence nulle) ; tests W1-7 réécrits sur le droit livré daté ; attentes « surtaxe
6,8 » remplacées par le droit de 2028 lu dans le moteur ; G1 (neutralité au bit) sur les seules bases
qui n'encodent pas le levier (`bases_g1`), rapport comparé hors la seule différence ci-dessus
(`rapport_g1`) ; garde des écarts sourcés (v0.6.6) branchée sur le registre des sources du dépôt
parent ; ancrage empirique du Gini et cas de régression de l'éviction (V2-01) sur des programmes figés
(`tests/snapshots/programmes_figes_gini_v040.json`, `programme_fige_eviction_v0610.json`), sans
identifiant de programme dans le code ; G1 du déplafonnement : un programme publié peut dépasser
5 points, dans le domaine. Outil `scripts/scan_discontinuites.py` : balayer une clé dominante d'un
mode exclusif retire les paramètres qu'elle masque (la référence inscrit désormais ces taux).

**Textes publics mis à jour** (relus dans leurs sources ; un montant qu'aucune source téléchargée ne
porte n'est plus écrit comme voté : la surtaxe d'IS est décrite par le montant que le moteur compte en
2026, 6,8 Md€, et la révision du HCFP) : infobulles du rabot uniforme et docstrings
de `handlers/montaigne.py`, alignées sur la seule note (une citation et une base de 1 726 Md€ qui n'y
figurent pas sont retirées ; la cible de défense est celle de la note, 2,7 % du PIB, pensions
comprises) ; `docs/SCENARIOS_POLITIQUES.md` : ligne de la surtaxe et paragraphe du réajustement, nombre
de scénarios, bloc du scénario retiré, bloc du scénario ajouté, phrases d'encodage mises à jour avec P,
orientation du scénario de think tank citée dans la note, lignes « Source » régénérées par
`generate_scenario_sources.py` (dépôt parent) et tableau par `generate_scenario_params.py` ;
`docs/METHODOLOGIE.md` : règle d'encodage 5 remplacée (aucun chiffrage de tiers n'encode un
programme ; une mesure sans chiffre ni paramètre est affichée, non modélisée), référence commune,
valeurs datées de v0.8.1, chiffres re-mesurés (référence, sentier de déflateur, mission IGF, 2027),
onzième colonne du tableau du sens agrégé (écart de dette 2032 à la référence ; le précalcul du site
doit la reproduire, garde `tests/test_revue_adverse_v061.py` dans le dépôt parent) ;
`docs/EXPLICATION_MODELE_ECONOMIQUE.md` : chiffres de la référence.

## [v0.8.0] — non publiée (proposée) — release « E » : onze curseurs, déplafonnement des cotisations salariales, garde-fous, effet d'offre « échelle »

**Ce qui change** : une équation (l'effet d'offre structurel, point 5) ; onze curseurs nouveaux et
le plafond de 5 points des cotisations salariales retiré (points 2 à 4) ; des garde-fous d'entrée,
un calendrier des montants et des valeurs datées du droit en vigueur (point 1). Le plafond de 10 %
du PIB passe en mode « avertissement » par défaut (point 1.5, décision du mainteneur). Aucun scénario
publié n'utilise encore les nouveaux curseurs.

**Ce que cela déplace, prouvé au bit** (10 scénarios publiés × 2 modes × 2 portes, et les 33
mini-scénarios de v0.7.2 × 2 portes, sérialisation exacte des sorties) : canal d'offre neutralisé et
champs ajoutés au rapport retirés, la release est identique au bit à v0.7.2 dans les 106 cas. Avec
le canal d'offre, les seuls cas qui bougent sont les 32 où ce canal agit : sept programmes publiés
(dette 2032 en mode cadre : de 0 à +1,48 point ; dette 2035 en mode historique : de −0,25 à +4,13
points) et les mini-scénarios d'investissement et de recherche. Les trois autres scénarios publiés,
dont le scénario de référence « Budget 2026 (voté) », et le statu quo sont identiques au bit.

**Corrections de la revue adverse, avant publication** (deux relecteurs : cohérence comptable,
neutralité ; sur la branche d'intégration, un commit par point avec son test rouge et sa mutation) :
revenus du capital (assiette sociale scindée, point 4.2), flux vers l'étranger hors du terme
d'inflation et de la cicatrice (2.3), calendrier et valeurs datées (1.4), durée de rampe bornée à
2032 (1.3), avis Z-ter complété (4), TVA à taux réduits dans les prix (3), investissement des
collectivités dans l'effet d'offre (5), plafond de 10 % en avertissement (1.5, décision du
mainteneur), calendriers de quatre taux et niveaux (1.3), domaines élargis (6), textes neutres et
limites dites (6). Écarts au bit à la release avant revue, tous attribués : trois programmes publiés
(investissement des collectivités), un programme (plafond), deux mini-scénarios (revenus du capital,
TVA à taux réduits), et le champ `cadre.plafond_total.mode` de chaque réponse. **Au total, par
rapport à v0.7.2**, arbitrages du mainteneur et contre-vérification compris (§ 7) : dette 2032 en mode
cadre +1,48, +1,14, +1,04, +0,91, +0,89, +0,88 et +0,02 point pour sept programmes publiés, les trois
autres et le statu quo inchangés au centième ; dette 2035 en mode historique de −0,25 à +4,04 points. Le
§ 8 (investissement des collectivités, soumis au mainteneur) s'y ajoute, avec son propre tableau.

### 1. Garde-fous et calendriers

1. **Leviers inconnus refusés.** Un levier de premier niveau que le moteur ne connaît pas était
   sauté en silence quand le moteur servait de bibliothèque (l'API le refusait déjà en 422). Mode
   strict : `LevierInconnu` (422) ; mode tolérant : levier retiré, `report.valid = false` et une
   entrée `{"regle": "LEVIER_INCONNU", "leviers_ignores": […], "message": …}` dans
   `report.corrections` (liste toujours présente).
2. **Exclusions mutuelles X1 et X2** (`constants.EXCLUSIONS_MUTUELLES`) : deux curseurs qui feraient
   varier le même euro ne se cumulent pas. X1 : `droits_succession` est ignoré quand
   `fiscalite_patrimoine.intensite` ≠ 0. X2 : `transferts_etranger` est ignoré quand le rabot
   uniforme coupe la contribution à l'Union européenne (`exclure_ue = 0`). Strict :
   `LeviersIncompatibles` (422) ; tolérant : levier jamais appliqué, entrée dans `report.corrections`.
3. **Calendrier d'un montant** (champ de requête `profils`) : `plein` (défaut), `rampe` (montée
   linéaire jusqu'en 2032, valeur exacte la dernière année) ou `annee` (une seule année du mandat).
   36 paramètres éligibles : 32 montants en Md€ et, ouverts après revue adverse (calendrier écrit par
   les programmes), quatre taux ou niveaux en « plein » ou « rampe » seulement (cotisations
   salariales, cotisations patronales, salaires des enseignants, budget chômage en montant) ; les
   autres taux et les durées basculent sans calendrier. Mode cadre
   seulement. Les montées en charge internes d'un levier partent de la première année où il s'écarte
   du droit en vigueur. Bloc `cadre.profils` toujours émis. La requête `rampe` de v0.7.0 en est un
   alias : sorties identiques au bit. Une durée explicite `annees` dans `profils` est bornée pour que
   la rampe finisse au plus tard en 2032 (corrigé après revue adverse : 6 ans dès 2028 finissaient en
   2033).
4. **Valeurs datées du droit en vigueur** (`valeurs_datees` de `droit_en_vigueur.json`) : le droit
   de l'année prend la valeur du segment qui la contient ; une mesure votée pour un an ne se
   reconduit pas, y compris comme référence d'un calendrier (la référence de chaque année est le
   droit de cette année ; corrigé après revue adverse). La release est livrée sans aucune valeur
   datée (mécanisme seul).
5. **Plafond de 10 % du PIB : mesuré, avertissement par défaut.** La somme des écarts de
   dépenses et de recettes au défaut du moteur est mesurée chaque année dans les deux modes ;
   `cadre.plafond_total` publie `mode`, les années au-delà du seuil, l'impact maximal et son année.
   Interrupteur `constants.PLAFOND_TOTAL_MODE` : `avertissement` (**défaut**, décision du mainteneur
   du 12/11/2026 : aucune réduction, un avis) ou `reduction` (comportement v0.7.2, toujours
   disponible). Sur le seul programme publié qui dépasse le seuil : écarts au mode réduction de 0,08
   point de déficit et 0,25 point de dette au plus en mode cadre, 0,15 et 0,48 en mode historique ;
   aucune valeur non finie, filet de chômage jamais touché ; le filet de croissance [−3,5 % ; +2,5 %]
   mord sur une croissance plus forte (2,87 % calculés au lieu de 2,79 en mode cadre, 3,01 au lieu de
   2,84 en mode historique ; condition connue du mainteneur au moment de sa décision). Chiffres
   mesurés avec le § 8.
6. **Signature de contrat** : une réponse du moteur porte `cadre.profils` (objet) et
   `cadre.plafond_total.mode`. Registre généré : bloc `noms_parametres_admis` (noms admis de tous
   les leviers, formules comprises).

### 2. Dépenses publiques, prestations aux ménages, flux vers l'étranger

**Trois curseurs de dépense en Md€ par an** (montant identique chaque année, en euros courants, non
revalorisé ; neutre 0).

1. **`depenses_publiques`** — crédits des ministères et des opérateurs (`credits_etat`, [−60 ; +20]),
   moyens de soins de l'Assurance maladie (`ondam`, [−10 ; +10]), dotations en capital aux ménages
   (`transferts_capital`, [−10 ; +10]). Formule : somme des trois montants. Multiplicateur d'une
   dépense générique, comme le curseur de défense ; aucun effet direct sur le pouvoir d'achat, le
   Gini ni la compétitivité.
2. **`prestations_menages`** — prestations de solidarité (`solidarite`, [−35 ; +30]) et pensions en
   montant (`pensions`, [−20 ; +10]). Le montant entre dans les dépenses et, au même montant, dans
   le revenu des ménages. Multiplicateur des transferts. Gini une fois, à l'entrée en vigueur :
   −0,0008 par Md€ de solidarité versé en plus, ≈ −0,00024 par Md€ de pensions.
3. **`transferts_etranger`** — contribution au budget de l'Union européenne et aide publique au
   développement (`montant`, [−32,009 ; +10] ; borne basse = somme sourcée des deux crédits de la loi
   de finances 2026). **Multiplicateur intérieur nul** : le montant change le solde et la dette, pas
   la demande intérieure. Le terme d'inflation lié à l'effort et la cicatrice d'austérité lisent
   l'effort intérieur, net de ce flux ; les taux d'intérêt et l'éviction gardent l'effort total
   (corrigé après revue adverse : une coupe de 32 Md€ baissait l'inflation de 0,12 point l'année
   suivante). Aucun scénario publié ni mini-scénario n'utilise le curseur : sorties identiques au
   bit.

### 3. Recettes en Md€ sans comportement, déplafonnement des cotisations salariales

- **`droits_succession.variation`** — [−21,2 ; +20] (borne basse : recette 2025) ; Gini et
  compétitivité de la règle du levier « Fiscalité du patrimoine » par Md€.
- **`fiscalite_indirecte.tva_ciblee`, `.accises_energie`** — [−15 ; +15] chacun ; coin de prix pour
  les ménages ; Gini des règles de la TVA et de la TVA sur l'énergie. Une hausse de TVA à taux réduits
  passe dans les prix l'année qui suit l'entrée en vigueur de son levier, par la règle du taux normal
  (même effet sur l'inflation à recette égale ; corrigé après revue adverse) ; les accises non.
- **`impot_revenu_cible.montant`** — [−15 ; +5] ; prélèvement direct ; Gini de la règle de la décote.
- **`recette_exceptionnelle.montant`** — [0 ; 60], une seule année (calendrier « annee », à l'année
  de début par défaut) ; refusée en mode historique.
- **`cotisations_salariales.baisse_points`** — le plafond de 5 points est retiré ; la borne devient
  la suppression totale de la masse sourcée : 138,2 Md€ (Insee, comptes de la Nation, D613CE, CSG et
  CRDS exclues) ÷ 6 Md€ par point = 23,03 points. Libellé corrigé (l'ancien « taux actuel de 22 % »
  comptait la CSG et la CRDS). Les scénarios publiés écrivent au plus 5 points : inchangés au bit.

### 4. Impôts à taux avec comportement

Le moteur calcule le rendement d'un taux sur une assiette sourcée, puis retire la seule réaction
des contribuables visés (paramètre visible et réglable) ; les effets sur l'activité restent ceux du
moteur, comptés une fois.

1. **`impot_plancher_patrimoine`** — impôt minimum sur les patrimoines de plus de 100 M€ (taux
   [0 ; 3 %]) ; recette = (1 − évitement) × 20 Md€ × taux / 2 % (Sénat, rapport n° 689, 2025), moins
   ce que l'ISF prélève déjà, sur une assiette qui suit le PIB depuis 2025. **Évitement par défaut :
   35 %**, milieu de la fourchette publiée de 15 % (Saez et Zucman, 2019, contrôle fort) à 55 %
   environ (Jakobsen et al., Danemark), confiance faible ; à 2 %, ≈ 13 Md€ au PIB 2025. Aucun chiffre
   non publié n'est utilisé.
2. **`fiscalite_capital`** — part IR du prélèvement forfaitaire et prélèvements sociaux du capital,
   avec la réaction des détenteurs (`elasticite`, 0,9, IPP 2019), ou un rendement en Md€. Assiette
   sociale scindée : la part soumise au prélèvement forfaitaire (56,25 Md€) réagit au taux total, le
   reste (134,75 Md€) aux seuls prélèvements sociaux. Au défaut, la recette de la part IR culmine
   vers 54 % de taux total, dans la fourchette publiée de 43 à 57 % (Lefebvre, Lehmann et Sicsic,
   2025). Corrigé après revue adverse : la première version appliquait la même réaction aux deux
   assiettes, et relever la part IR faisait perdre de la recette et monter le Gini.
3. **`multinationales`** — bénéfices récupérés (Md€ au taux d'IS de 25 %) et taxe sur les services
   numériques avec érosion de son assiette, ou un rendement en Md€.
4. **`operations_financieres`** — taxe sur les transactions financières avec baisse des volumes
   (Colliard et Hoffmann, 2017), ou un rendement en Md€ ; rachats d'actions ; crypto-actifs.

Un taux suit son assiette (part du PIB de son année source) ; un montant en Md€ est constant en euros
courants. Un avis signale un impôt plancher combiné à la hausse d'un impôt qu'il déduit (revenus du
capital, CSG, tranche supérieure de l'IR, fiscalité du patrimoine, IR ciblé ; les deux derniers
ajoutés après revue adverse).

### 5. Effet d'offre structurel : échelle

**Constat** : le bonus de croissance potentielle d'un canal valait `coeff × log2(1 + |Δ|)`, somme
écrêtée à ±0,20 pt : le plafond était atteint dès 1 Md€ d'écart (investissement de transition),
0,74 Md€ (recherche) ou 3 Md€ (rénovation). Sept programmes publiés sur dix recevaient exactement le
même bonus de +0,20 pt par an, quel que soit leur montant (un huitième, qui coupe la recherche, le
plancher −0,20). Les sources de la v3.1 justifiaient des délais et des dépréciations, jamais la forme
logarithmique ni les coefficients par Md€.

**Canal ajouté après revue adverse** : l'investissement des collectivités (`collectivites.investissement`),
capital public comme l'investissement de l'État (même pente, délai de 3 ans, dépréciation de 5 %). Il était
exclu sur une prémisse fausse (« utilisé par aucun programme publié » : trois l'encodent). Effet : dette 2032
en mode cadre −0,07 à −0,16 point, dette 2035 en mode historique −0,23 à −0,70 point sur ces trois programmes.

**Forme retenue** : contribution linéaire dans le flux annuel par canal, `pente × Δ`, signée ; somme
saturée en douceur : `bonus = 0,20 pt × tanh(Σ / 0,20 pt)`. Pentes = élasticité au stock de capital
÷ stock : capital public +0,005 pt par Md€/an (Bom et Ligthart 2014 ; INSEE, comptes de patrimoine
2025 ; FMI 2015), R&D publique +0,032 pt (Fieldhouse et Mertens 2024), rénovation 0 (DG Trésor,
Trésor-Éco n° 394, 2026), éducation +0,0025 pt (convention, délai de 15 ans). Délais, dépréciations
et plafond inchangés. Mêmes paramètres pour tous les programmes.

**Ce que cela déplace** : chaque programme reçoit l'offre de son montant ; le sens est le même pour
tous (prime d'offre moindre). Mode cadre, dette 2032 des sept programmes concernés : +1,48, +1,30,
+1,04, +0,98, +0,22 point, deux inchangés jusqu'en 2032 (canal R&D, délai de 5 ans). Mode historique,
dette 2035 : +4,04, +4,13, +3,19, +2,88, +1,02, +0,25, −0,25 point. Gini et compétitivité inchangés.

### 6. Intégration

- Évitement par défaut de l'impôt plancher : 0,35 (constante unique dérivée de la fourchette
  sourcée) ; l'ancien calage sur une note non publiée est retiré.
- **Limites dites dans METHODOLOGIE, non corrigées** (revue adverse, décisions du mainteneur en attente) :
  effet d'offre calculé sur le flux et non sur le stock (un investissement d'une seule année n'a aucun effet
  d'offre, la recherche n'agit qu'après 5 ans) ; plafond de l'effet d'offre conventionnel ; Gini des
  cotisations salariales prolongé au-delà de la plage de sa source ; assiette de `tva_rate` incluant les biens
  aux taux réduits.
- **Domaines élargis** (valeurs à encoder de la release de paramètres suivante ; règle « domaine =
  union des bornes d'interface et des valeurs à encoder ») : `fonction_publique.effectifs` jusqu'à
  +140 000 postes (60 000 avant ; une création ne puise pas dans le vivier, aucun plafond interne) ;
  `chomage_alloc.montant` à partir de 24,85 Md€ (27,45 avant), la borne basse du taux de
  remplacement en étant dérivée (≈ 40,7 %, 45 % avant) pour que les deux écritures exclusives
  couvrent la même plage. Aucune valeur déjà admise ne change de résultat.
- **Registre public aligné sur ces domaines** (`policy_measures.json`) : `chomage_alloc.montant` à
  partir de 24,85 Md€ (27,5 avant, pas de 0,05) et `fonction_publique.effectifs` jusqu'à +140 000
  (50 000 avant). Seul effet : le mini-scénario `fonction_publique` (valeur à mi-distance du défaut et
  du maximum) passe de +25 000 à +70 000 postes ; son instantané est régénéré, et l'ancienne entrée
  simulée sur le moteur de la release reproduit l'ancien instantané au bit (l'écart vient de l'entrée
  seule). Aucun scénario publié ne change.
- Registre des mesures régénéré avec les curseurs du simulateur de la release (niveau « curseurs »).
- Une recette exceptionnelle, refusée en mode historique, est simulée en mode cadre par les outils
  qui essaient chaque levier (mini-scénarios, balayage de discontinuités, tests d'éviction) :
  `engine/cadre.LEVIERS_REFUSES_EN_MODE_HISTORIQUE`.
- Instantanés régénérés une seule fois, après audit cellule par cellule : golden masters (sept
  scénarios, effet d'offre), mini-scénarios (neuf ajoutés ; investissement, recherche et
  cotisations salariales, dont la valeur médiane du domaine passe de 2,5 à 11,5 points), ancre des
  écarts au statu quo.
- **Rétrocompatibilité** : champs de réponse ajoutés (`report.corrections`, `cadre.profils`,
  `cadre.plafond_total.mode`, `impact_max_pct_pib`, `annee_impact_max`, `cadre.filet_croissance`) ;
  un levier inconnu est désormais refusé aussi hors de l'API ; sorties des sept programmes à canal
  d'offre actif déplacées (point 5).

### 7. Arbitrages du mainteneur du 12/11/2026 et contre-vérification adverse des corrections

Un commit par point sur la branche d'intégration, chacun avec son test rouge et sa mutation.

1. **Cotisations salariales : coût du point.** Un point vaut 1 % de la masse salariale brute 2025
   (Insee, comptes de la Nation, tableau 2.101, ligne D11 : 1 157,166 Md€), soit 11,57 Md€, calculé
   (`SALAIRES_BRUTS_2025_MD / 100`) ; jusque-là 6 Md€, sans source. Le maximum du curseur devient
   le taux moyen réel des cotisations salariales, 11,94 points (D613CE / 1 % de D11), au lieu de
   23,03. Infobulle : « 1 point = 1 % de la masse salariale brute 2025 (11,6 Md€) ». Les deux
   programmes publiés écrits en points (2,5 points) voient leur montant presque doubler : dette 2032
   +0,91 et +0,89 point (mode cadre) ; ils seront reconvertis depuis leurs Md€ à la release de
   paramètres.
2. **Cotisations salariales : effet sur le Gini.** +0,0001 de Gini par Md€ rendu
   (`GINI_COTIS_SAL_PAR_MD`), estimation de France Budget (quintiles de niveau de vie Insee 2025,
   incertitude d'un facteur 2, valable pour une baisse uniforme de quelques points), au lieu de
   +0,0027 par point attribué à une source introuvable (retirée). Gini des deux programmes : −0,001.
3. **Gel d'une année des pensions et des prestations.** Calendrier « une seule année » ouvert sur
   `retraites.indexation` et `prestations_indexation.taux_indexation` (pas la rampe) ; chaque
   revalorisation garde le coefficient de son année : l'écart de niveau d'un gel reste, revalorisé
   avec la masse, sans rattrapage (avant : un retour à 1 effaçait l'économie). Au statu quo, un gel
   total des deux en 2028 rend 6,1 Md€ en 2028, puis 6,3 / 6,5 / 6,7 / 6,9 Md€ de 2029 à 2032.
   **Gini proportionnel à l'écart de niveau accumulé** (relecture adverse finale, I-1) : l'effet est
   émis en entier l'année du gel (convention de ces leviers, comme un gel permanent) ; au retour à la
   référence du calendrier — le droit en vigueur de l'année, quelle que soit sa valeur — après k
   revalorisations au coefficient gelé, le levier garde min(k, N)/N de l'effet émis au-delà de la
   référence (N = 7 pour les pensions, `RETRAITES_EROSION_PLATEAU_ANS` ; 10 pour les prestations,
   `PRESTATIONS_REVALORISATIONS_MAX`, nommée) et rend le reste. Jusque-là, il gardait tout, et ne
   reconnaissait le retour qu'à l'égalité au littéral 1,0 (droit en vigueur à 0,9999 : presque tout
   rendu). Gel total des deux en 2028, Gini publié en 2032 : +0,0027 au lieu de +0,0165 (+0,0065
   l'année du gel, +0,0021 en 2035, vers +0,0019) ; continu en fonction du droit (1,0 et 0,9999 :
   +0,0027 ; 0,9 : +0,0025). À euros égaux en 2032, il émet 3,6 fois le Gini du même montant en
   `prestations_menages` (35 fois avant), moitié moins que la sous-indexation permanente (7,2 fois,
   écart des règles par Md€, antérieur). Coefficient constant : convention inchangée, aucune sortie
   publiée ne bouge.
4. **Droits de succession** : borne haute +25 Md€ par an (+20 non sourcée), aucune décote ;
   infobulle avec un avertissement sourcé (taux effectif ≈ 10 % au sommet contre 45 % affichés ;
   part évitée non chiffrable pour une forte hausse).
5. **Prévention en santé** : quatre références fausses corrigées et un rapport dit introuvable rétabli
   (code, tests, infobulle, METHODOLOGIE) ; infobulle : le curseur borne la dépense de prévention à
   11,2 Md€, un effort supplémentaire se saisit en dépense de soins (curseur « Moyens de soins de
   l'Assurance maladie »), sans retour modélisé (relecture adverse finale, m-b) ; retour de 50 % =
   hypothèse haute. Base 7,5 et borne 11,2 inchangées.
6. **TVA à taux réduits** (contre-vérification I1, m1) : passage dans les prix sur l'incrément annuel
   positif de la recette, chaque marche plafonnée, retrait symétrique ; seules les hausses
   s'additionnent avec le taux normal avant le plafond commun ; `tva_rate` inchangé au bit.
7. **Mineurs** : référence d'un calendrier du budget chômage en montant convertie du taux du droit
   (m2) ; retour anticipé des cotisations salariales conditionné au traqueur (m4) ; alias `rampe`
   v0.7.0 borné à 2032 (m5) ; filet de croissance [−3,5 % ; +2,5 %] signalé par un avis, année et
   valeur avant écrêtage (m6 : un programme publié, une année par mode), et publié aussi en bloc
   structuré `cadre.filet_croissance` (bornes, années, croissance calculée et retenue ; toujours émis,
   sorties inchangées au bit) ; limites dites (m3, m7, m9).
   Relecture adverse finale (m-c) : une durée de rampe trop longue est ramenée à la borne et tracée en
   tolérant pour un profil « rampe » comme pour l'alias (avant : profil ignoré, programme en plein dès
   le début) ; en strict, le refus dit le domaine, sans « ramenée à ».
8. **Entrée invalide servie en 500** (relecture adverse finale ; antérieur à la passe) : un entier
   géant sur `fonction_publique_reforme.fusion_agences` ou `digitalisation`, en mode cadre, faisait
   lever le lecteur latéral du vivier des effectifs (conversion en flottant) ; l'API répondait 500 en
   strict au lieu de 422. Ce lecteur traite désormais une valeur non finie ou hors des flottants comme
   la clé absente, ce que fait déjà la porte des valeurs : 422 en strict, 200 et rapport invalide en
   tolérant. Les 82 paramètres du registre à ±10⁴⁰⁰ et 10³⁰, en strict, dans les deux modes : aucun 5xx.

Empreinte au bit (206 cas, deux modes du plafond) : 24 cas diffèrent de la tête précédente, tous
attribués (points 1-2 : deux programmes et le mini-scénario des cotisations ; m6 : rapport seul d'un
programme ; § 8 : trois programmes). Instantanés régénérés une fois, après audit cellule par cellule.

### 8. Investissement des collectivités : classe de l'investissement productif (contre-vérification I2 ; soumis au mainteneur)

Le canal d'offre de l'investissement des collectivités était déjà celui de l'État ; leur classe de
multiplicateur et d'éviction ne l'était pas : à montant égal, 10 Md€ par an d'investissement local faisaient
monter la dette 2032 (+0,20 point en mode cadre) quand ceux de l'État la faisaient baisser (−0,40). Désormais, la
seule part `investissement` du levier `collectivites` est publiée dans son impact (`depenses_investissement`) et
forme un flux distinct `(collectivites, investissement)` (`INVESTISSEMENT_PRODUCTIF_PARTIEL`), multiplié, lu par
l'éviction et réparti dans le temps comme l'investissement productif de l'État ; la dotation garde la classe de la
dépense générique. 10 Md€ : −0,37 point de dette 2032 (mode cadre) contre −0,40 pour l'État ; −0,63 contre −0,71
en 2035 (mode historique). Effet isolé sur les scénarios publiés (empreinte au bit : seuls trois programmes
bougent, les sept autres et le statu quo sont identiques au bit) :

| Programme | Dette 2032, mode cadre | Déficit 2032, mode cadre | Dette 2035, mode historique |
|---|---|---|---|
| A (15 Md€ d'investissement local) | −0,31 | +0,11 | −0,63 |
| B (8 Md€) | −0,48 | +0,12 | −0,98 |
| C (8 Md€) | −0,47 | +0,12 | −0,91 |

Le premier programme gagne moins que les deux autres malgré un montant plus élevé : le filet de croissance
mord sur sa trajectoire (§ 7). Variante écartée : la classe sans le profil de persistance de l'investissement
(−0,53 point pour 10 Md€ en 2032, au-delà de l'État). Ce point est réversible par un seul commit.

## [v0.7.2] — 2026-11-08 — paramètres : borne des effectifs, écrêtage visible, dette de départ

**Ce qui change** : paramètres, bornes, un champ de réponse additif et de la documentation.
Aucune équation n'est touchée. Un commit par point.

1. **Borne basse du curseur `fonction_publique.effectifs` : −400 000 → −500 000**
   (`PARAM_DOMAINS`, décision du mainteneur du 08/11/2026). Elle couvre le −480 000 d'un
   programme annoncé, avec une marge. Elle reste sous la capacité du vivier de départs d'un
   mandat 2028-2032 en mode cadre : 67 % × 157 000 × 5 = 525 950. Un banc du 08/11/2026 a
   montré un effet proportionnel, sans écrêtage, à −480 000 et −500 000, pour un début en 2028
   sans réforme de l'État. Un début plus tardif, ou le curseur combiné à la réforme de l'État,
   peut être raboté par le vivier : ce rabot est signalé (point 7). Preuve :
   `tests/test_parametres_v072.py`, test-propriété « borne < capacité du vivier », calculée
   depuis les constantes, et témoin comportemental : aucun rabot à la borne, rabot détecté à
   110 % du vivier. Sorties bit-identiques : la borne ne change aucune valeur déjà admise.
2. **Écrêtage visible : `report.leviers_ecretes`**. En mode tolérant, chaque paramètre
   ramené à une borne de `PARAM_DOMAINS` ou `INTENSITE_DOMAINS` y figure une fois par
   simulation, sous la forme `{levier, demande, applique, borne, motif}`, `motif` valant
   `"domaine"` (le motif `"vivier"` est ajouté au point 7). La liste est vide quand rien
   n'est écrêté. Le mode strict refuse toujours en 422. Hors champ : une `annee_debut` ou une
   durée de rampe (`rampe.annees`) hors domaine, signalées dans `report.warnings` seulement. Avant, l'écrêtage ne se lisait que
   dans une phrase de `report.warnings` et dans un journal serveur. Preuve : tests unitaires,
   simulateur en mode historique et cadre, API tolérante et stricte ; réponse bit-identique
   hors ce champ sur cinq cas comparés avant et après, golden masters verts. Une demande non
   finie est rendue en texte, pour que la réponse JSON reste valide. Doc : docstring de
   `/simulate`, METHODOLOGIE § « Paramètres d'entrée : noms et valeurs ».
3. **Dette publique de départ, fin 2025 : 115,6 → 115,7 % du PIB** (`DETTE_RATIO_2025`).
   Source : Insee Première n° 2106, « Le compte des administrations publiques en 2025 »,
   mai 2026, figure 5 : 3 460,5 Md€, 115,7 % du PIB. Elle révise les 115,6 % des
   Informations rapides n° 78 du 27/03/2026. Au PIB 2025 du moteur, 2 991 Md€, 1,157 redonne
   3 460,6 Md€ ; 1,156 en donnait 3 457,6. Le tendanciel dérivé du potentiel passe de 1,228 à
   1,2285 %, le potentiel total du statu quo reste 1,1 %. Golden masters régénérés par
   `make snapshot-baseline`, chiffres publiés re-mesurés dans METHODOLOGIE et
   EXPLICATION_MODELE_ECONOMIQUE.

   | Statu quo (aucune mesure) | 2026 | 2027 | 2032 |
   |---|---|---|---|
   | Mode historique, dette % PIB | 117,97 → 118,07 | 120,43 → 120,53 | 136,56 → 136,68 |
   | Mode historique, déficit % PIB | −5,30 inchangé | −5,51 → −5,52 | −7,31 → −7,32 |
   | Mode cadre 2028, dette % PIB | 119,4 inchangé | 121,87 → 121,86 | 138,06 → 138,04 |
   | Mode cadre 2028, déficit % PIB | −5,5 inchangé | −5,63 inchangé | −7,17 inchangé |

   En mode cadre, la dette 2026 est l'atterrissage observé : l'ajustement stock-flux 2026
   passe de 14,1 à 11,1 Md€, car il absorbait la dette manquante. Seul le tendanciel dérivé
   bouge ensuite, d'où un effet de signe opposé et minime. Écart maximal sur les golden
   masters : dette +0,15 pt (mode historique, 2035), +0,1 pt (mode cadre), déficit 0,02 pt,
   croissance 0,01 pt ; chômage et Gini inchangés. Scénario de référence `plf_2026`, mode
   historique : dette 2030 128,64 → 128,75 %, 2035 149,77 → 149,91 %. **Rétrocompatibilité** :
   le mode historique n'est plus la sortie de v0.6.11 au bit près, à cause de ce seul
   paramètre. Les valeurs d'audit épinglées (V2-02, V2-03) sont re-déclarées. La garde de
   continuité de `test_portes_activation_v067.py` mesure désormais la dette sans arrondi :
   un écart réel de 7e-5 pt y valait 0,01 pt à une frontière d'arrondi.
4. **Ligne Source LR** de `docs/SCENARIOS_POLITIQUES.md` : la formule « source faisant foi »
   est retirée, seul parti à la porter. Le sens est inchangé, les deux documents restent cités
   avec leurs dates. Cette ligne est GÉNÉRÉE depuis `scenariosSources.json` du dépôt parent
   (`scripts/generate_scenario_sources.py`, garde `--check`) : la même correction y est requise
   avant le bump, faute de quoi le générateur rétablit la formule.

5. **Scénarios réencodés sur le droit effectif** (dépôt parent, décision du mainteneur du
   08/11/2026). Un paramètre non sourcé d'un programme vaut désormais le droit en vigueur
   réajusté, et non plus le budget voté brut : franchises 100 → 120, défense 57 → 58, surtaxe
   d'IS 7,3 → 6,8 Md€, selon les scénarios. `plf_2026` est réencodé de même, sous le libellé
   « Budget 2026 voté, réajusté sur l'exécution 2026 » : il est le statu quo, avec ou sans pont. Gardes mises à
   jour : `test_cadre_v070_mesures_annee` vérifie que `plf_2026` égale le droit voté du moteur
   plus les réajustements de l'atterrissage, et diffère du voté brut ; mutation prouvée.
   `test_reencodage_v066` prend la même référence. La table générée de
   `docs/SCENARIOS_POLITIQUES.md` suit. Golden master historique régénéré avec les deux effets,
   dette 115,7 % et réencodage : sept scénarios changent, au plus +0,24 pt de dette 2035 (RN).
   Golden master cadre 2028 et standalone bit-identiques. Scénario de référence, mode
   historique : déficit 2026 −5,22 %, dette 2030 128,81 %, dette 2035 150,11 %.

### Contrat : retrait du pont « égal au voté = non touché »

6. **Présent = imposé, absent = hérité** (`heriter_du_droit`, `budget_simulator/engine/cadre.py`,
   décision du mainteneur du 08/11/2026). Mode cadre seulement : le mode historique ne lit pas
   le droit en vigueur. Jusqu'en v0.7.1, un levier ou un paramètre égal au budget VOTÉ était
   traité comme non touché et remplacé par le droit en vigueur réajusté : des franchises
   demandées à 100 étaient appliquées à 120, sans signal. Désormais, un paramètre présent est
   appliqué tel quel ; un levier absent, ou un paramètre absent d'un bloc présent, reçoit le
   droit en vigueur réajusté, comme avant. `cadre.mesures_effectives` et
   `cadre.leviers_modifies` gardent leur sens : poser le voté brut y apparaît comme une
   modification. Ce qui change pour un appelant : une requête qui recopiait le budget voté
   n'est plus le statu quo ; `{}` ou le scénario « Budget 2026 voté, réajusté sur l'exécution 2026 » le sont, au
   bit. Preuve, en TDD : `test_present_impose_absent_herite`, rouge avant le retrait
   (120 appliqué pour 100 demandé), vert après. Neuf tests du cadre réécrits sur le droit
   réajusté, lu dans le moteur (`DROIT_REAJUSTE`, `tests/cadre_harness.py`).
   `test_g_programme_vide_en_cadre_est_le_droit_en_vigueur` vérifie au bit, en mode cadre,
   `{}` ≡ droit réajusté explicite ≡ `plf_2026`. Avec les scénarios réencodés du point 5, aucun
   golden master ne bouge. Avec l'ancien `plf_2026` voté brut, le golden master cadre aurait
   changé.

### Revue passe 1 (08/11/2026)

7. **Rabot du vivier visible** (`handlers/efficience.py`, `engine/orchestrator.py`). Le plafond
   du vivier de départs (67 % des départs cumulés, réforme de l'État comprise) rabotait la cible
   du curseur `fonction_publique.effectifs` sans signal, hors du journal de débogage. Cas
   mesurés à −500 000 : début en 2029, 420 760 postes retirés en 2032 puis la cible en 2033 ;
   le rattrapage glisse d'un an par année de début, et n'a pas lieu dans l'horizon pour un début
   en 2032 ; curseur + réforme 50/50 en 2028, 311 645 postes en 2035. Désormais, une entrée
   par simulation dans `report.leviers_ecretes` : `{levier: "fonction_publique.effectifs",
   demande, applique, borne: [−capacité, null], motif: "vivier", annee}`, valeurs de la
   DERNIÈRE année rabotée, et un avis dans `report.warnings` qui donne la période. Le résultat
   reste valide (limite du modèle, pas une entrée invalide), y compris en mode strict. Seul le
   monde du programme est consigné en mode cadre. Trajectoires inchangées au bit. Preuve :
   garde comportemental paramétré sur les débuts 2028 à 2032 (oracle arithmétique depuis les
   constantes) et sur curseur + réforme (oracle : journal du handler), « réalisé < cible ⇔
   entrée présente » ; 12 tests rouges sans le correctif. Le commentaire de `constants.py`
   (« rattrapée d'un coup en 2033 ») et METHODOLOGIE sont corrigés : le « sans rabot » ne vaut
   que pour un début en 2028 sans réforme.
8. **Contrat : clé inconnue refusée** (`SimulationRequest`, `extra='forbid'`). Une clé hors
   `mesures`, `periods`, `annee_debut`, `rampe` donne 422, dans les deux modes. Avant,
   `annee_debu: 2030` était ignoré : 200 en mode historique, sans avertissement. Appelants du
   dépôt parent vérifiés (`api.js`, `verify_render_live.py`, tests privés) : aucun n'envoie
   d'autre clé ; les scripts de précalcul appellent le moteur en Python, sans l'API.
9. **Avis « présent = imposé »** (`engine/cadre.py`, mode cadre). Un paramètre posé qui vaut
   exactement le budget voté mais diffère du réajusté annule le réajustement de l'atterrissage :
   un avis le dit (« defense.budget : 57 imposé (budget voté), annule le réajustement 2026
   (58) »). `report.valid` inchangé ; réponse bit-identique hors ce texte (test avec l'avis
   neutralisé).
10. **Paramètre `null` = absent, en strict comme en tolérant** (`heriter_du_droit`). En strict,
   `{"defense": {"budget": null}}` gardait le `null` jusqu'à la porte annuelle, qui le retirait
   après l'héritage : le handler appliquait son défaut (57 au lieu de 58), sans signal, et
   `defense` figurait parmi les leviers modifiés. Désormais strict ≡ tolérant ≡ statu quo au
   bit (trajectoire, détail, leviers modifiés), sur `defense.budget` et
   `sante.franchise_participation_taux`.
11. **Doc** : docstring de `/simulate` et METHODOLOGIE § cadre. `leviers_ecretes` ne couvre pas
   `annee_debut` ni `rampe.annees` ; un levier à modes exclusifs (`chomage_alloc`,
   `taxe_superprofits`, `exonerations_salaires`) n'hérite de rien dans un bloc partiel, le
   handler y lit ses défauts.

**Preuves** (après la revue passe 1) : `make test` et `BUDGETLAB_STRICT=1`, 2906 passed,
186 skipped, sans `scenarios.json` ; avec les scénarios réencodés du dépôt parent, 3257 passed,
49 skipped, dans les deux modes (mêmes tests sautés qu'avant la passe). Golden masters
inchangés ; pyright sans erreur nouvelle sur les fichiers touchés.

## [v0.7.1] — 2026-11-07 — doc/test : le tableau agrégé suit l'horizon de notation 2027-2032 de l'app

**Ce qui change** : documentation et test seulement, aucune équation ni aucun paramètre ; sorties
du moteur identiques au bit à la v0.7.0. Le tableau « Neutralite : ce que la version v0.6.1 du
moteur deplace, EN AGREGE » de `docs/METHODOLOGIE.md` gagne une dixième colonne, l'écart de dette
**2032** au scénario de référence en mode cadre (programmes appliqués de 2028 à 2032), avec sa
mise à jour datée ; les neuf colonnes historiques (dette 2035) sont inchangées. Le test
`test_le_sens_agrege_de_la_version_est_publie_et_a_jour` lit désormais l'année de notation de
l'app (`ANNEE_NOTATION_APP = 2032`) dans le précalcul au lieu de sa dernière année : il rougissait
contre le précalcul cadre de l'app, et restait skippé dans la CI publique (précalcul absent).
Titres v0.6.8 à v0.7.0 : mention « non publiée » retirée, ces versions sont taguées.

## [v0.7.0] — 2026-11-07 — cadre temporel 2027-2032

**Ce qui change** : la SÉMANTIQUE TEMPORELLE du moteur. Jusqu'en v0.6.11, un programme
s'appliquait dès 2026, un an avant l'élection et deux ans avant le premier budget du nouvel
élu. La v0.7.0 applique chaque programme à partir de son `annee_debut` (2028 pour les
programmes et le simulateur, arbitrage du mainteneur du 07/11/2026) et le DROIT EN VIGUEUR
avant : le budget 2026 voté, reconduit à droit constant en 2027. L'année 2026 est
l'atterrissage observé ou prévu, injecté identiquement pour tous les scénarios. **Aucune
équation macro n'est touchée** (croissance, Phillips, Okun, recettes, dépenses, dette) et le
plafond de 10 % du PIB est inchangé. Détail : `docs/METHODOLOGIE.md` § « Cadre temporel
2027-2032 ».

**Rétrocompatibilité** : sans `annee_debut` (ou avec 2026), le moteur est en MODE HISTORIQUE,
la sortie de v0.6.11 au bit près — 44 cas comparés en pleine précision (10 scénarios publiés,
33 mini-scénarios du registre, un programme mixte ; toutes colonnes de résultats et de détails,
impacts par levier, rapport), golden masters `golden_master_v1.json` et
`standalone_master_v1.json` inchangés. Le mode historique ne lit ni le droit en vigueur ni
l'atterrissage.

### Cinq lots, un commit chacun, mesurés séparément

| Lot | Contenu | Effet sur la dette 2032 des dix scénarios (`annee_debut = 2028`) |
|---|---|---|
| A — mesures de l'année | point unique `mesures_de_l_annee` lu par `apply_measures` ET les lecteurs latéraux ; droit en vigueur (`data/droit_en_vigueur.json`) avant le début ; un levier absent du programme garde la valeur du droit | de −1,3 (LR) à +3,6 (Écologistes) contre v0.6.11 ; budget voté inchangé |
| B — effets ponctuels en incrément | `effet(p) − effet(p au dernier déclenchement)` : la part héritée n'est plus recomptée à la bascule, une rampe ne compte plus trois fois l'effet | compétitivité seule, +0,01 à +0,07 point |
| C — horloges | `H = H(droit, 2026) + [H(programme, début) − H(droit, début)]`, trois mondes d'évaluation des handlers ; 22 sites passés sur l'horloge du levier ; rampes de mandat (effectifs FP, réforme FP) de max(début, 2027) à 2032 ; choc d'âge, ASU, revalorisations, passage de la TVA dans les prix sur l'horloge du levier | de −1,74 (LFI) à +1,65 (IM compétitivité), dont l'horloge de l'âge de départ −1,9 à +1,0 |
| D — rampe | rampe paramétrique sur demande (aucune par défaut) ; postes d'enseignants sur la rampe de mandat des effectifs FP (mode cadre) | ±0,1 par défaut (enseignants) |
| E — atterrissage 2026 | `data/atterrissage_observe.json` : réajustements du droit en vigueur (défense 58, franchises 120 %, surtaxe IS 6,8), puis cibles ; déflateur injecté, écart de solde persistant, ajustement stock-flux, choc de croissance, coin IPC ; colonne IPC | +2,1 à +2,3 pour tous |

Statu quo 2027 à droit constant (budget 2026 exécuté, reconduit) : déficit −5,63 % du PIB,
dette 121,87 %, croissance 1,33 % (rebond du modèle, jamais forcé), chômage 8,17 %. Atterrissage
2026 publié (`cadre.atterrissage`, valeurs arrêtées par le mainteneur le 07/11/2026) : croissance
du modèle 1,24 % → 0,4 % brut (choc −0,84 point) ; déflateur 1,34 % → 1,5 % injecté (+0,16
point, dénominateur des ratios officiels) ; IPC 2,3 % par un coin de +0,79 point rapporté au
déflateur injecté ; chômage 7,82 % → 8,3 % (moyenne annuelle) ; solde −5,78 % → −5,5 %
(réajustements −1,2 Md€, puis résidu +8,5 Md€ de recettes, persistant) ; dette 118,94 % →
119,4 % (ajustement stock-flux +14,1 Md€). Garde des valeurs publiées :
`tests/test_cadre_v070_atterrissage.py`.

### Contrat API `/simulate`

- Requête : `annee_debut` (entier strict, facultatif ; absent ou 2026 = mode historique ;
  2027-2032 = mode cadre) ; `rampe` (facultative, mode cadre) =
  `{"annees": 1-6, "leviers": ["levier.parametre", …]}`, leviers éligibles
  `engine/cadre.py::RAMPE_LEVIERS_ELIGIBLES`. `periods` reste limité à 10.
- 422 : `annee_debut` non entier (texte, booléen, flottant) ou `rampe` mal formée (deux modes) ;
  en strict, `annee_debut` hors [2026 ; 2032], `annee_debut` ≤ dernière année d'atterrissage
  injectée (2026 est le mode historique, jamais en conflit), `annees` hors [1 ; 6], levier de
  rampe inconnu ou non éligible, rampe en mode historique. En tolérant : correction tracée,
  `report.valid = false`.
- Réponse : bloc `cadre` (mode, `annee_debut`, années de droit en vigueur, identifiant et
  source du droit en vigueur, leviers modifiés, rampe effective, atterrissage avec cibles
  sourcées, réajustements et leurs sources, décomposition, années où le plafond de 10 % mord) ;
  colonne `Inflation IPC %` (prix de la consommation des ménages ; `Inflation %` reste le
  déflateur, injecté en 2026 en mode cadre).
- Taille bornée de `rampe.leviers` (revue de sécurité) : au plus 15 noms de 64 caractères au
  plus (422) ; côté moteur, rejet au-delà, dédoublonnage, un seul avertissement agrégé.

### Décisions appliquées (arbitrages du mainteneur du 07/11/2026)

Programmes de 2028 à 2032 ; 2027 à droit constant ; atterrissage 2026 en deux temps (leviers
réels réajustés et reconduits, puis résidu forcé et persistant) ; déflateur du PIB injecté, IPC
par le coin de prix, jamais dans le déflateur ; chômage 2026 en moyenne annuelle sourcée ;
fraude fiscale inchangée à 0,14 ; aucune rampe par défaut ;
effets ponctuels en incrément ; horloges recalées dès cette passe ; plafond de 10 % inchangé ;
simulateur dès 2028 ; croissance 2027 jamais forcée.

### Gardes nouvelles

- Droit en vigueur et atterrissage : données serveur validées sans aucune correction ; un
  défaut est une erreur 500 tracée, jamais un 422 ni une correction silencieuse.
- Composition des lecteurs latéraux hors handlers (âge de départ, effet d'offre, TVA) non
  implémentée : un droit en vigueur qui s'en écarte fait échouer le chargement.
- Écart modèle → cible au-delà de ±0,03 (domaine des tables v0.6.9) : erreur, jamais un
  écrêtage. Une année injectée ne peut pas figurer aussi dans les tables v0.6.9.
- Le budget voté de l'application doit rester égal au droit en vigueur VOTÉ
  (`tests/test_cadre_v070_mesures_annee.py`) ; les réajustements vivent dans le fichier
  d'atterrissage, chacun avec sa source, et s'appliquent au droit en vigueur à partir de 2026 en
  mode cadre : l'application n'a rien à changer pour eux.
- Golden master du cadre : `tests/snapshots/golden_master_cadre_2028.json`
  (`tests/test_cadre_v070_golden.py`).

**Revue passe 1** (`tests/test_cadre_v070_revue_passe1.py`) : suite verte sans le `scenarios.json` de l'application (référence « droit en vigueur », jamais `plf_2026`) ; un bloc partiel est complété paramètre par paramètre par le droit en vigueur (hors leviers à modes exclusifs ; aucun scénario publié n'en contient) ; aucun réajustement sans source ; six grandeurs écrites chaque année (`null` permis) ; montant sans objet publié `null`, jamais 0 ; grandeurs fermées, journal complet exigé, solde publié sous `deficit` ; plafond nommé `PLAFOND_IMPACT_TOTAL_PIB` (valeur inchangée) et `plafond_total` dans le rapport du cadre ; état du mode cadre gelé (`EtatCadre`) ; garde des états propres à chaque monde ; échec de l'évaluation isolée des réajustements traité comme le chemin principal ; toute erreur de lecture d'un fichier serveur = défaut du serveur ; rampe sans effet = avis informatif et `rampe.leviers_ignores` ; caches rendus en copie profonde ; `cadre.mesures_effectives` exposé (droit en vigueur réajusté, programme par-dessus).

### Limites connues

- Superposition linéaire des horloges : un programme qui retire une mesure héritée à profil non
  monotone (fraude fiscale) garde un petit résidu en fin de période (−0,3 Md€ en 2035).
- L'émulation du 07/11 annonçait +0,2 à +0,9 point de dette 2032 pour les horloges ; elle ne
  recalait ni les canaux seniors ni les horloges écrites en dur. Les chiffres de la passe sont
  ceux des bancs.
- L'effet des réajustements sur le solde est mesuré levier par levier, sans les plafonds de 5 %
  et 10 % du PIB.

## v0.6.11 — re-encodage LR et Horizons sur leurs sources primaires (paramètres seuls, publiée le 07/11/2026)

**Ce qui change** : les paramètres de deux scénarios publiés, `lr_2027` et
`horizons_2027`, et deux bornes de domaine élargies aux valeurs servies. **Aucune
équation du moteur n'est touchée** ; les huit autres scénarios (budget 2026 voté,
RN, LFI, Renaissance, PS, Écologistes, Institut Montaigne rabot et compétitivité)
sont identiques au bit (golden master et précalcul vérifiés scénario par scénario).
Arbitrage du mainteneur du 02/11/2026 : « on met à jour tout de suite » (LFI et PS
ne bougent pas, leurs sources sont attendues les 6-7/11 et 7-8/11). Règle appliquée :
celle de METHODOLOGIE § « Règle d'encodage des programmes politiques » — gardé si
chiffré par le programme, sinon droit en vigueur ; un levier retiré se pose à la
valeur de `plf_2026`, jamais omis ; aucune neutralité affirmée n'est créditée.

### `lr_2027` — livret « Rétablir l'ordre dans les comptes publics » (15 fiches, 12/10/2026)

Le volet « Comptes publics », « à venir » au 07/10/2026, est publié : 197 Md€
d'économies en 2032 (146 affectés au déficit, 51 rendus ; État 96, sphère sociale
91, collectivités 10). Chaque ligne du livret est ventilée sur le levier qui lui
correspond quand il existe, à son montant :

| Fiche du livret | Montant 2032 | Levier | Avant → après | Conversion |
|---|---|---|---|---|
| 3 — 400 000 départs non remplacés | 25 Md€ | `fonction_publique.effectifs` | −300 000 → **−400 000** | cible du livret (vivier 631 140 : pas de plafonnement ; rampe 2027-2032) |
| 8 — assurance chômage, durée 18 → 15 mois | 14 Md€ | `chomage_alloc.duree` | 18 → **15** | paramètre du livret (le moteur calcule 2,25 Md€ : 3 mois × 0,75) |
| 9 — AME réduite aux soins essentiels | 0,7 Md€ | `immigration.ame` | 1,2 → **0,5** | 1,2 − 0,7 |
| 14 — impôts de production supprimés | 15 Md€ | `impots_production.montant` | 83 → **82** | 97 − 15 (était 97 − 14 détaillés) |
| 5 — fraude (gel des avoirs, IA, aides) | 5 Md€ | `fraude_fiscale.effort` | 0,14 → **0,45** | régime net du levier (× 30 × 0,53) : même convention que le 0,14 de la LF 2026 ; +4,93 Md€ nets au plus grand centième ≤ 5 |
| 10 — fraude sociale | 4 Md€ | `fraude_sociale.effort` | 0,1 → **1,0** | 4 Md€ > capacité du levier avec l'ASU active (≈ 3,3 Md€ nets) → plafond, comme la fraude fiscale du RN |
| 12 — fonctionnement des collectivités | 10 Md€ | `collectivites.dotation` | 116,6 → **106,6** | 116,6 − 10 (même levier que l'effort des collectivités du RN) |
| 4 — énergies intermittentes subventionnées | 4 Md€ | `subventions_tge.montant` | 33 → **29** | 33 − 4 (l'énergie est dans l'assiette du levier) |
| 4 — niches, politique de la ville, zonages | 4,9 Md€ | `niches_fiscales_tge.montant` | 57 → **52** | 57 − 5 (arrondi au pas du curseur, écart 0,1 à la ligne) ; arbitrage du mainteneur : même levier que Renaissance 56, Horizons 32, PS 40, Écologistes 25, LFI 20 |

Inchangés et confirmés par le livret : cotisations patronales 0,2525 (15 gagés +
10 « autofinancés », neutralité non créditée), cotisations salariales −2,5 points
(15 Md€), ASU 1 / 0,70 (compte social unique, 10 Md€ dans le livret — le moteur
chiffre cette variante en coût, ≈ 4,6 Md€ sur le solde 2030, écart signalé à la
fiche), âge du taux plein 65 ans (12 Md€ de « mesures d'âge » dans le livret, 9 sur le
site ; le moteur calcule 5,4 Md€/an dès 2032). **Non encodées, faute de levier**
(≈ 107 Md€ des 197) : opérateurs 5, agences 7,5, base zéro 11,5, doublons 4, carence
3 (fiche 3) ; immobilier 5, formation 6, immigration État 3, APD 3,5, culture 2,6,
MaPrimeRénov' 2 (le levier ne descend pas sous le droit en vigueur), contrats aidés 1
(fiche 4) ; réserves 7,5, Agirc-Arrco 7,2,
cotisation de capitalisation 6 (un prélèvement, compté en économie par le livret),
RAFP 4,3, régimes spéciaux 3, fraude 2 (fiche 6) ; arrêts maladie 4 (fiche 7) ; gain
d'IS 4 (effet retour, règle 3) et RIA 2 (fiche 8) ; immigration hors AME 9,3 (fiche 9) ;
gestion de la Sécurité sociale 4 (fiche 11) ; familles/transmission 3 (objet mixte
IR + DMTG, aucun levier propre), relais
MaPrimeRénov' 3, CEE 4 (fiche 14). Les 14 Md€ « autofinancés » ne sont pas crédités.

### `horizons_2027` — page « Pour une France plus prospère » réécrite (02/11/2026), réponses sur l'école (23/10/2026)

| Annonce | Levier | Avant → après | Motif |
|---|---|---|---|
| « un tiers des départs en retraite non remplacés, plus de 250 000 postes sur le quinquennat » | `fonction_publique.effectifs` | −3 119 → **−250 000** | nombre de postes du candidat ; rampe 2027-2032, même règle que RN et LR |
| réforme des agences (intensité 10/20 posée en hypothèse le 30/08/2026) | `fonction_publique_reforme` | 10/20 → **0/0** (droit voté) | le candidat chiffre lui-même le non-remplacement ; la réforme puise dans le même vivier de départs (double comptage) — même traitement que le RN (agences comptées dans les effectifs, réforme à 0/0) |
| +20 % de rémunération moyenne des enseignants « financés par la baisse démographique » | `education.salaires` | 0 → **20** | coût brut (10 Md€/an dans le moteur : 20 % de 50 Md€) ; le financement démographique n'est pas crédité (règle 3, aucun nombre de postes annoncé) |

Non encodés : 3 jours de carence (pas de levier d'indemnités journalières), zéro
cotisation patronale au-delà de la 37ᵉ heure (non chiffré), IR nul trois ans pour les
jeunes parents (3 Md€/an : le seul levier d'IR disponible est la décote, dont la
population et le canal distributif ne sont pas ceux de la mesure), allocation
familiale unique « à coût constant », PER abondé de 500 €. **Fonds d'adaptation
climatique de 2 Md€/an : non encodé, à l'arbitrage du mainteneur.** Le levier existe
(`transition_ecologique.investissement`) mais, mesuré, +2 Md€/an déplace la dette 2035
de −5,3 pt et le déficit 2030 de +0,23 pt : l'effet d'offre `coeff × log2(1 + Δ)`
(growth.py, `SUPPLY_EFFECTS`) atteint son plafond de +0,20 pt de croissance potentielle
dès 1 Md€ (0,028 pt à 0,1 Md€, 0,20 à 1, 2 et 5 Md€). Continu depuis la v0.6.7 (plus de
porte à 0,1 Md€), il reste hors de proportion aux petits montants ; encoder le fonds
aurait fait de ce seul paramètre le premier mouvement du scénario. Tracé pour une
passe moteur dédiée, pas corrigé ici (release paramètres seuls).

### Domaines élargis (constants.py, `_PARAM_DOMAINS_MOTEUR`)

`fonction_publique.effectifs` [−300 000 ; 60 000] → [−400 000 ; 60 000] et
`education.salaires` [−5 ; 15] → [−5 ; 20] : même règle qu'en v0.6.7 (domaine élargi à
la valeur extrême servie, pas au-delà ; sans cela le mode strict refuse LR et Horizons
en 422 et le mode tolérant les clampe en silence). Aucune autre sortie ne change.

### Ce que cela déplace (2030 ; dette 2035 entre parenthèses ; banc levier par levier, interactions ≤ 0,04 pt)

- **LR** : déficit −6,79 → −6,05 % ; dette 130,15 → 128,43 % (156,14 → 150,17) ;
  chômage 7,26 → 7,43 ; croissance moyenne 2026-2030 1,42 → 1,29 ; pouvoir d'achat
  105,2 → 104,5 ; compétitivité 100,73 → 100,64 ; Gini 0,291 → 0,292. Solde 2030 :
  +28 Md€, dont collectivités +8,3, fraude fiscale +5,0, niches +4,2, effectifs +3,5,
  subventions +3,3, fraude sociale +2,4, chômage +2,2, AME +0,6, impôts de production
  −0,9. Dette 2035 : collectivités −1,9, fraude fiscale −0,9, niches −0,9, subventions
  −0,8, fraude sociale −0,6, effectifs −0,5, chômage −0,5, AME −0,1, impôts de
  production +0,2 (niches 57 → 52 ajoutées en complément, arbitrage du mainteneur :
  seules, déficit 2030 +0,11 pt, dette 2035 −0,87 pt, compétitivité −0,08).
- **Horizons** : déficit −5,44 → −5,39 % ; dette 126,84 → 126,61 % (144,95 → 144,92) ;
  chômage 7,47 → 7,39 ; croissance moyenne 1,17 → 1,23 ; pouvoir d'achat 102,4 → 102,9 ;
  compétitivité 100,38 → 100,39 en 2030, Gini inchangé. Dette 2035 : effectifs −1,06, réforme des agences
  retirée +0,52, enseignants +0,49. Solde 2030 : effectifs +8,2, réforme −3,9,
  enseignants −3,4 Md€.
- Indice de pouvoir d'achat 2029 (garde `test_political_scenarios_2027`) : LR
  104,7 → 104,0, Horizons 101,9 → 102,5, dans la tolérance ±1,5 ; valeurs figées
  inchangées.
- Tableau agrégé de METHODOLOGIE : neuvième colonne « Écart au 02/11/2026 » — LR +6,4
  → +0,4, Horizons −4,8 inchangé au dixième (−4,82 → −4,85), les sept autres
  identiques.

### Snapshots et tests

- Golden master `tests/snapshots/golden_master_v1.json` régénéré : seuls `lr_2027` et
  `horizons_2027` diffèrent ; `standalone_master_v1.json` inchangé.
- `tests/snapshots/scenario_deltas_baseline.json` **recapturé sur le moteur v0.6.10**
  (décision du mainteneur du 21/10/2026 : « recapturer au prochain tag » ; l'ancre
  datait de la v0.6.7 et le RN consommait 1,14 pt de sa tolérance de 1,5). Les trois
  scénarios de l'ancre (statu quo voté, LFI, RN) n'ont pas changé de paramètres : les
  nouveaux deltas sont ceux de la v0.6.10 servie en production.
- `tests/test_reencodage_v066.py` : écarts sourcés LR (14) et Horizons (9) mis à jour ;
  la propriété (a) « retiré = posé au droit voté, jamais omis » est paramétrée par
  scénario et couvre la réforme des agences d'Horizons ; (a3) vérifie que les deux
  valeurs hors curseur sont dans le domaine moteur. 44 tests.
- `tests/test_political_scenarios_2027.py` : note de recalage (valeurs attendues
  inchangées).

### Arbitrages du mainteneur du 02/11/2026

Tous les choix d'encodage ci-dessous ont été arbitrés par le mainteneur le 02/11/2026 ;
les chiffrages servis en dépendent et sont validés.

1. Arbitrage du mainteneur du 02/11/2026 : conversion de la fraude fiscale par le régime
   net (convention LF 2026) plutôt que par la cible brute (0,14 + 5/30 ≈ 0,31) — l'écart
   entre les deux est de 2,3 Md€ nets en 2030.
2. Arbitrage du mainteneur du 02/11/2026 : fraude sociale au plafond 1,0 (règle RN)
   plutôt qu'au premier centième qui sature (0,45) — écarts ≤ 0,02 pt de déficit sur
   2026-2035 entre les deux conventions.
3. Arbitrage du mainteneur du 02/11/2026 : énergies intermittentes (4 Md€) portées par
   `subventions_tge` ; niches/politique de la ville/zonages (4,9 Md€) portées par
   `niches_fiscales_tge` 57 → 52 (symétrie avec les cinq autres programmes encodés sur
   ce levier) ; familles/transmission (3 Md€) laissée non encodée (objet mixte IR +
   DMTG, aucun levier propre, dit sur la fiche) — les fiches du livret non encodées sont
   nommées dans la fiche LR du simulateur.
4. Arbitrage du mainteneur du 02/11/2026 : Horizons, retrait de la réforme des agences
   (10/20 → 0/0) au motif du double comptage avec les 250 000 postes (précédent RN).
5. Arbitrage du mainteneur du 02/11/2026 : Horizons, fonds d'adaptation 2 Md€/an non
   encodé (effet d'offre hors de proportion, ci-dessus).
6. Arbitrage du mainteneur du 02/11/2026 : recapture de l'ancre des deltas.
7. Arbitrage du mainteneur du 02/11/2026 : numéro de version v0.6.11 (les numéros se
   suivent ; la release « valeurs INSEE + part indexée 0,87 » annoncée sous ce numéro en
   v0.6.10 glisse à v0.6.12, le retrait de l'éviction à v0.6.13).

## v0.6.10 — contre-audit externe V2 : six réserves fermées (tag v0.6.10)

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

## v0.6.9 — conjoncture observée : le mécanisme, sans valeur (tag v0.6.9)

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

## v0.6.8 — indice de pouvoir d'achat « RDB-moteur » (tag v0.6.8)

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
