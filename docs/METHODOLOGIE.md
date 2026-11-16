# METHODOLOGIE - Simulateur Budget France 2025-2035

**Version** : 4.0
**Date** : Juin 2026
**Auteur** : Budget Lab France

---

## Table des Matieres

0. [Cadre temporel 2027-2032 (v0.7.0)](#cadre-temporel-2027-2032-v070)
1. [Hypotheses Demographiques](#hypotheses-demographiques)
2. [Retraites](#retraites)
3. [Sante](#sante)
4. [Fonction Publique](#fonction-publique)
5. [Chomage et Protection Sociale](#chomage-et-protection-sociale)
6. [Fiscalite](#fiscalite)
7. [Competitivite des Entreprises](#competitivite-des-entreprises)
8. [Transition Ecologique](#transition-ecologique)
9. [Lutte contre la Fraude](#lutte-contre-la-fraude)
10. [Mesures Presidentielles 2027](#mesures-presidentielles-2027)
11. [Curseurs de la release E (v0.8.0)](#curseurs-de-la-release-e-v080)
12. [Multiplicateurs et Mecanismes Macro](#multiplicateurs-et-mecanismes-macro)
13. [Sources et References](#sources-et-references)

---

## Introduction

Ce document detaille les **hypotheses economiques** et les **mecanismes de calcul** utilises dans le simulateur budgetaire. L'objectif est d'assurer une transparence totale sur nos choix methodologiques.

**Principes directeurs :**
- Alignement avec les projections officielles (COR, DREES, INSEE)
- Calibration sur donnees empiriques (OFCE, IPP, France Strategie, IMF, Blanchard & Leigh)
- Effets retour macroeconomiques modelises via multiplicateurs per-measure
- Phasing realiste des reformes (delais de mise en oeuvre)

**Changements majeurs v3.0 :**
- Multiplicateurs keynesiens recalibres et appliques par mesure (weighted blend)
- Profil temporel DECAY_PROFILE calibre sur la litterature
- Suppression des bonus sans base empirique (investissement, synergie, qualite)
- Ajout cicatrice d'austerite, crowding-out differencie, boost investissement potentiel
- debt_drag corrige de -0,008 a -0,005
- chomage_gap_weight corrige de +0,40 a 0,0 (bug inversion)
- Taux de croissance depenses corrige (defense 3,0%, transition_eco 2,5%)

**Changements majeurs v3.1 :**
- **DECAY_PROFILE differencie** : 3 profils (TAXES, TRANSFERS, INVEST) au lieu d'un seul. Le profil est melange (weighted blend) selon la composition des mesures actives
- **Croissance potentielle supply-side** : Nouveau mecanisme dynamique. Les depenses d'investissement productif (recherche, transition ecologique, education) augmentent la croissance potentielle avec delais et rendements decroissants (cap +0,20 pt). **v0.8.0** : effet proportionnel au montant (élasticité au stock de capital public ou de R&D publique, sourcée), plafond atteint à l'échelle de plusieurs dizaines de Md€/an et non plus dès le premier milliard (cf. § Croissance Potentielle Supply-Side)
- **Bug fix abs()** : Les coupes budgetaires etaient incorrectement traitees comme des investissements (signe non pris en compte)
- **Bug fix decay loop** : La boucle de decroissance etait piegeee a l'interieur du gate d'effort — les impulsions passees disparaissaient quand l'effort courant etait nul

**Changements majeurs v4.0 (refonte « assemblage temporel ») :**
- **Depenses** : recurrence unique chainee des l'annee 1 — `Dep(t) = Dep(t-1) x (1 + g_vol) x (1 + pi_idx)`. Plus de regime special 2026 (« bridging year ») ni de taux d'amorcage exogene. Indexation mixte : 54% de la depense suit l'inflation PASSEE (pensions, prestations), 46% le deflateur contemporain
- **Recettes** : elasticite unitaire au PIB nominal contemporain (`ELASTICITE_PO_PIB = 1,0`, HCFP note 2023-01). Supprimes : elasticite differenciee par regime de croissance (1,00/1,06/1,08/1,12), erosion forfaitaire 0,2%/an, rustines de transition 2026
- **Boucle annuelle reordonnee** : macro de l'annee (avec impulsion budgetaire de t-1) -> PIB (deflateur contemporain) -> chomage -> flux aux prix de l'annee -> mesures (impulsion stockee pour t+1). **Lot 6 (non publie)** : le budget de l'annee agit des cette annee ; il est d'abord evalue hors de son effet propre, puis l'annee est calculee avec son impulsion (§ « Calendrier de l'impulsion »)
- **Phillips ANCREE** : formule `(1-rho) x (pi* + kappa x gap) + rho x pi(t-1)` — `INFLATION_STRUCTURELLE` (1,6%) est le point de convergence REEL et `PHILLIPS_PENTE_MT` (0,20) est DIRECTEMENT la pente de moyen terme ; rappel BCE a 2,0% en garde-fou de surchauffe, plancher a 0,8% desormais inerte en statu quo
- **Baseline honnete** : l'« assainissement implicite gratuit » (~24 Md EUR/an) de l'ancien assemblage a disparu. **Chiffres recales le 26/08/2026** — ceux publies ici jusque-la (deficit 2026 -5,05 %, dette 2030 ~129,5 %, dette 2035 ~150 %) dataient d'AVANT les lots 8 et 9, qui les ont deplaces de 10 a 12 points. Et ils melangeaient deux objets : le **statu quo NU** (le moteur sans aucune mesure, objet de calibration, servi nulle part) et le **scenario de reference** `plf_2026` (« Budget 2026 vote, reajuste sur l'execution 2026 » depuis le 08/11/2026, ce que le site sert comme point de depart). Les deux, mesures sur l'etat livre :

| | statu quo NU | scenario de reference `plf_2026` |
|---|---|---|
| Deficit 2026 | -5,30 % | **-5,39 %** (loi votee : -5,0 % ; surtaxe IS 2026 non comptee, voir ci-dessous) |
| Dette 2030 | 129,23 % | **129,41 %** (mission IGF : 130,5) |
| Dette 2035 | 151,32 % | **151,49 %** |
| Deficit 2035 | -9,06 % | **-9,04 %** |

  Chiffres re-mesures le 30/08/2026 (passe v0.6.3 : fin du double comptage de la duree
  d'indemnisation, monotonie fraude sociale, cout perenne du non-recours ASU, graine 2025
  aux comptes definitifs INSEE et inertie d'inflation ramenee au milieu de sa fourchette).
  Re-mesures le 07/10/2026 (v0.6.7 : moteur sans tirage aleatoire, cf. « Stochasticite », et
  tendanciel du potentiel re-ancre a 1,228 %, cf. « Calibration Baseline Validee »).
  Re-mesures le 08/11/2026 (v0.7.2 : dette de depart fin 2025 recalee de 115,6 a 115,7 %,
  Insee Premiere n° 2106, mai 2026 ; tendanciel derive 1,2285 %), et scenario de reference
  reencode sur le droit reajuste (« Budget 2026 vote, reajuste sur l'execution 2026 » : defense 58, franchises 120 %,
  surtaxe IS 6,8).
  Re-mesures le 12/11/2026 (release de parametres P, moteur v0.8.1) : le scenario de reference porte
  desormais le droit du premier budget du mandat (2028), ou la surtaxe d'IS votee pour 2026 vaut 0
  (valeur datee du droit en vigueur, cf. « Cadre temporel »). En mode historique, ou un programme
  s'applique des 2026, ces chiffres ne comptent donc pas les 6,8 Md€ de surtaxe 2026 (environ 0,22 pt
  de PIB). Le site, en mode cadre, part de l'atterrissage 2026 injecte (deficit -5,5 %).

  Toute grandeur mesuree publiee dans ce document nomme desormais son objet, et une garde de la suite moteur (`tests/test_chiffres_publies_v061.py`) la recalcule a chaque execution : un chiffre qui cesse de reproduire fait rougir la CI au lieu de rester en ligne.

---

## Cadre temporel 2027-2032 (v0.7.0)

**Pourquoi.** Jusqu'en v0.6.11, un programme s'appliquait dès 2026, un an avant l'élection
et deux ans avant le premier budget du nouvel élu. Depuis v0.7.0, chaque requête peut
porter une **année de début** (`annee_debut`) : les programmes et le simulateur commencent
en **2028**, le premier budget du mandat 2027-2032 (arbitrage du mainteneur du 07/11/2026).
Aucune équation macro n'est modifiée ; seul le calendrier d'application change.

### Deux modes

| | Mode historique | Mode cadre |
|---|---|---|
| Déclenché par | `annee_debut` absent ou égal à 2026 | `annee_debut` de 2027 à 2032 |
| 2026 | le programme | l'atterrissage observé ou prévu, identique pour tous |
| Avant l'année de début | — | le **droit en vigueur** : budget 2026 voté, reconduit à droit constant en 2027 |
| À partir de l'année de début | le programme | le programme, levier par levier, par-dessus le droit en vigueur |
| Sortie | celle de v0.6.11, au bit près | — |

Le droit en vigueur est un **fichier de données** (`budget_simulator/data/droit_en_vigueur.json`),
égal au scénario « Budget 2026 (voté) ». Il se remplace sans code le jour où une loi de finances
pour 2027 est promulguée. Un levier que le programme ne mentionne pas, ou laisse à `null`, garde
la valeur du droit en vigueur : « le programme ne dit rien » veut dire « rien ne change ». De même,
un paramètre absent d'un levier que le programme modifie garde la valeur du droit en vigueur, sauf
pour les leviers à modes exclusifs (assurance chômage, taxe sur les superprofits, exonérations sur
les salaires), dont le handler lit alors ses défauts. Les mesures appliquées à partir de l'année de
début sont publiées dans le bloc `cadre.mesures_effectives` de la réponse.

### Les mesures de l'année : un point unique

En tête de chaque année, le moteur pose les **mesures de l'année** : le droit en vigueur avant
l'année de début, le programme ensuite. Les handlers les lisent, mais aussi les lecteurs
latéraux : offre de travail et chômage des seniors, effet d'offre des dépenses productives,
montée en charge de l'ASU, point d'indice, réforme de l'État. Un interrupteur posé dans la
seule application des mesures aurait laissé ces canaux appliquer le programme dès 2026.

### Les horloges : la part héritée garde la sienne, l'incrément démarre la sienne

Beaucoup de leviers ont une montée en charge : rabot uniforme à 50 % puis 100 %, fraude sur
cinq ans, santé, ASU sur quatre ans, retraites par cohortes. Compter ces phasages depuis 2026
ferait entrer un programme de 2028 au milieu de sa montée. Pour chaque levier, à partir de
l'année de début :

    H(année) = H(droit, horloge 2026) + [H(programme, horloge début) − H(droit, horloge début)]

Le moteur évalue les handlers dans **trois mondes** (le droit sur l'horloge de 2026, avec l'état
du moteur ; le programme et le droit sur l'horloge du début, avec des états propres) et combine
leurs sorties clé par clé. Conséquences :

- un levier **égal au droit en vigueur**, qui ne lit aucun levier modifié, garde ses impacts au
  bit près : son incrément est nul exactement ;
- un levier qui lit un autre levier (la fraude sociale lit l'ASU, le SMIC le point d'indice, les
  effectifs la réforme de l'État) reçoit l'incrément de sa lecture, sur l'horloge du levier lu ;
- les **rampes de mandat** (effectifs de la fonction publique, cohortes de la réforme de l'État,
  postes d'enseignants) courent de max(année de début, 2027) à 2032 : un cinquième par an de
  2028 à 2032 ;
- le **choc d'âge** des retraites est daté au plus tôt de l'année de début : ses montées en
  charge (pensions, offre de travail, chômage seniors) partent avec le programme ;
- restent **calendaires** : le calendrier légal de l'âge (62,75 ans gelés jusqu'en 2027, puis
  +3 mois par an jusqu'à 64 ans en 2032) et la revalorisation légale de 2026 ; la recette
  d'un ISF climatique et l'IFI qu'il remplacerait suivent le PIB nominal de l'année (leur assiette),
  quelle que soit l'année d'entrée du programme ;
- le passage d'une hausse de TVA dans les prix a lieu l'année qui suit son entrée en vigueur,
  sur l'horloge de la TVA ; le coefficient et le plafond sont inchangés.

**Limite** : c'est une superposition linéaire. Un programme qui retire une mesure héritée dont le
profil n'est pas monotone garde un petit résidu en fin de période (fraude fiscale ramenée à 0 :
−0,3 Md€ en 2035). Les lecteurs latéraux hors handlers (âge de départ, effet d'offre, TVA) ne
sont pas composés : c'est exact tant que le droit en vigueur reste au défaut du moteur sur ces
canaux, ce que le chargement du fichier vérifie.

### Les effets ponctuels en incrément

Les effets « une fois » au changement d'un paramètre (compétitivité, emploi, Gini) étaient
recalculés sur le niveau complet à chaque changement. La part du droit en vigueur comptée en
2026 était recomptée en 2028, et une rampe sur cinq ans comptait trois fois l'effet. Depuis
v0.7.0, un changement émet l'**incrément** : effet du niveau atteint moins effet du niveau au
dernier déclenchement. Le cumul ne dépend plus que du niveau atteint.

### La rampe

Une requête peut demander une rampe : `{"annees": n, "leviers": ["levier.parametre", …]}`, de 1 à
6 ans, sur les budgets et dotations en milliards d'euros et sur les cinq leviers fiscaux des
grandes entreprises. Le paramètre passe linéairement de la valeur du droit en vigueur à celle du
programme : p(t) = p_droit + (p_programme − p_droit) × min(max(t − début + 1, 0), n) / n. La
rampe porte sur le paramètre, pas sur un montant, parce que l'effet d'offre lit la valeur du
paramètre. **Aucune rampe n'est appliquée par défaut** : un programme qui publie une trajectoire
la déclare levier par levier.

### L'atterrissage 2026, en deux temps

Le fichier `budget_simulator/data/atterrissage_observe.json` porte, par année jouée, des
réajustements du droit en vigueur puis des cibles sourcées. Il est appliqué en mode cadre, à
l'identique pour tous les scénarios, et se révise sans code (valeurs arrêtées par le mainteneur
le 07/11/2026).

1. **Réajustements du droit en vigueur** : un levier réel qui a dérapé est corrigé dans le droit en
   vigueur et le suit ensuite : le budget réellement exécuté devient le droit constant de 2027.
   Règle d'assemblage (v0.7.2, décision du mainteneur du 08/11/2026) : **présent = imposé,
   absent = hérité**. Un paramètre présent dans le programme est appliqué tel quel, même égal au
   budget voté : des franchises demandées à 100 sont appliquées à 100, pas au 120 réajusté. Un
   levier absent, ou un paramètre absent d'un bloc présent, reçoit le droit en vigueur réajusté ;
   un paramètre à `null` compte comme absent, en mode strict comme en tolérant (v0.7.2, revue :
   le strict appliquait auparavant le défaut du handler). Exception, les leviers à modes
   exclusifs (`chomage_alloc`, `taxe_superprofits`, `exonerations_salaires`) : un bloc partiel n'y
   hérite de rien, le handler lit ses défauts pour les paramètres absents, comme en mode
   historique, car ajouter une clé du droit pourrait masquer le mode choisi. Quand un paramètre
   posé vaut le budget voté mais diffère du réajusté, un avis le signale dans `report.warnings`
   (« defense.budget : 57 imposé (budget voté), annule le réajustement 2026 (58) ») ; le
   résultat reste valide. Jusqu'en v0.7.1, un « pont » traitait une valeur égale au voté comme
   non touchée et lui substituait le réajusté, sans le signaler. Le fichier du droit en vigueur reste le budget
   VOTÉ ; le scénario « Budget 2026 voté, réajusté sur l'exécution 2026 » de l'application est ce droit réajusté,
   donc le statu quo du mode cadre au bit, comme une requête vide.

| Levier | Voté → réajusté | Motif (source dans le fichier) |
|---|---|---|
| `defense.budget` | 57 → 58 Md€ | crédits de la loi de programmation militaire exécutés à 58 Md€ |
| `sante.franchise_participation_taux` | 100 → 120 % | hausse des plafonds des franchises décidée en 2026, environ 0,3 Md€ |
| `is_exceptionnel_tge.montant` | 7,3 → 6,8 Md€ | rendement de la surtaxe révisé de −0,5 Md€ en comptabilité nationale |

2. **Cibles** : le moteur mesure l'écart entre son résultat, après les réajustements, et l'observé,
   puis le force.

| Grandeur 2026 | Valeur | Mécanisme |
|---|---|---|
| Croissance | 0,4 % (brut annuel) | choc de demande = cible − croissance du modèle, au point d'application des chocs observés |
| Déflateur du PIB | 1,5 % | imposé : c'est le dénominateur des ratios officiels de déficit et de dette |
| IPC | 2,3 % | coin du prix de la consommation, rapporté au déflateur injecté : il touche l'indice de pouvoir d'achat et la colonne IPC, jamais le déflateur |
| Chômage | 8,3 % (moyenne annuelle) | niveau imposé après la loi d'Okun |
| Déficit | 5,5 % du PIB | écart résiduel ajouté au niveau organique des recettes, donc **persistant** (rebasage) |
| Dette | 119,4 % du PIB | ajustement stock-flux de l'année |

Sources et dates de chaque valeur : dans le fichier. Décomposition publiée par le moteur pour
2026 (bloc `cadre.atterrissage` de la réponse) :

| Grandeur 2026 | Modèle | Observé | Écart forcé |
|---|---|---|---|
| Croissance | 1,22 % | 0,4 % | choc de −0,82 point |
| Déflateur du PIB | 1,34 % | 1,5 % | +0,16 point |
| IPC | déflateur injecté 1,5 % | 2,3 % | coin de +0,79 point |
| Chômage | 7,82 % | 8,3 % | +0,48 point |
| Solde | −5,78 % du PIB | −5,5 % | réajustements −1,2 Md€, puis résidu +8,6 Md€ de recettes |
| Dette | 119,04 % du PIB | 119,4 % | ajustement stock-flux de +11,1 Md€ |

Le solde « modèle » est celui du moteur avec les réajustements et le déflateur injecté. Même
après eux, le moteur reste plus pessimiste que la dernière prévision officielle : le résidu est
porté en recettes et persiste. Sans ce rebasage, l'écart disparaîtrait en 2027 et le déficit y
rebondirait sans aucune mesure. Avec lui, le budget 2026 exécuté, reconduit à droit constant hors
mesures votées pour une durée limitée (la surtaxe d'IS votée pour 2026 s'arrête en 2027, v0.8.1),
donne en 2027 un **déficit de
−5,80 %** du PIB et une **dette de 121,92 %**. La croissance 2027, 1,42 %, est le rebond du
modèle : elle n'est jamais forcée. Une année injectée ne peut pas être l'année de début d'un
programme : l'atterrissage écrase des niveaux (422 en mode strict).

### Le plafond de 10 % du PIB

Il porte sur la somme des écarts de dépenses et de recettes au **défaut du moteur**, pas au droit
voté (`PLAFOND_IMPACT_TOTAL_PIB`). Depuis la v0.8.0, cette somme est **mesurée chaque année dans
les deux modes** et publiée dans le bloc `cadre.plafond_total` : `mode`, années au-delà du seuil,
impact maximal mesuré (avant toute réduction) et son année. Ce qui se passe au-delà dépend de
`constants.PLAFOND_TOTAL_MODE` :

- `avertissement` (**défaut**, décision du mainteneur du 12/11/2026) : aucune réduction, un avis
  (« Mesures au-delà de 10 % du PIB en … : hors du domaine de validité du modèle (effets supposés
  proportionnels), résultats à lire avec prudence ») ; le résultat est la somme des mesures ;
- `reduction` (comportement de la v0.7.2, toujours disponible et testé) : tous les impacts de l'année
  sont réduits au prorata, avec l'avis « plafonné » dans `report.warnings`. Le résultat d'un
  programme concerné n'est alors pas la somme de ses mesures.

Banc d'intégration sur le moteur de la release (corrections des revues adverses et classe de
l'investissement des collectivités comprises) : un seul programme publié dépasse le seuil (impact
maximal 10,93 % du PIB en 2030 en mode cadre, 11,27 % en 2028 en mode historique). Sans réduction,
ses écarts restent faibles (déficit 0,08 point et dette 0,25 point au plus en mode cadre, 0,15 et
0,48 en mode historique), aucune valeur n'est non finie et le filet de chômage n'est jamais touché ;
le filet de croissance [−3,5 % ; +2,5 %], qui mord déjà une année avec la réduction, mord sur une
croissance plus forte (2,79 → 2,87 % en mode cadre, 2,84 → 3,01 % en mode historique). Le mainteneur
a tranché en connaissance de cette condition : l'avertissement est le défaut.

**Filet de croissance : avis (v0.8.0, contre-vérification m6 ; historique : l'écrêtage décrit ici est retiré
depuis, paragraphe suivant).** Le filet [−3,5 % ; +2,5 %] de la
croissance réelle annuelle (`CROISSANCE_FILET_MIN`, `CROISSANCE_FILET_MAX`, valeurs inchangées : borne
de validité des multiplicateurs linéaires) ne laissait qu'un journal de débogage. Quand il mord, un avis
le dit désormais dans `report.warnings`, avec chaque année et la croissance calculée avant écrêtage
(« filet de croissance [−3,50 % ; 2,50 %] atteint : 2030 (2,87 % calculés, 2,50 % retenus) — … ») ;
comme tout avis, il n'invalide pas le rapport. La même information est publiée sans phrase à analyser
dans le bloc `cadre.filet_croissance` (bornes en %, années, et pour chaque année la croissance calculée
et la croissance retenue), toujours présent, vide quand le filet ne mord pas.

**Écrêtage retiré (arbitrage du mainteneur du 16/11/2026, non publié).** L'écrêtage de la croissance dans
[−3,5 % ; +2,5 %] ne venait d'aucune source. Il est supprimé : une croissance hors de ce domaine est publiée
telle qu'elle est calculée. Les bornes restent celles du domaine de validité des multiplicateurs linéaires,
et l'avis comme le bloc `cadre.filet_croissance` le signalent toujours, au même format (croissance retenue
= croissance calculée ; « croissance non écrêtée ; résultats à lire avec prudence »). En mode cadre (le mode
publié), aucun programme publié ni la référence sans programme n'en sort, aucune année : aucun chiffre
publié ne change (garde : `tests/test_croissance_sans_ecretage.py`). Le mode historique de l'API change
pour les deux programmes publiés qui en sortaient en 2026 (chiffres mesurés : CHANGELOG, bloc du retrait).

### Calendrier d'un montant (`profils`, v0.8.0)

Champ de requête `profils`, à côté de `mesures`, en mode cadre seulement :

```json
"profils": {
  "depenses_publiques.credits_etat": {"forme": "rampe"},
  "defense.budget": {"forme": "annee", "annee": 2030}
}
```

- `plein` (défaut) : la valeur du programme chaque année dès le début ;
- `rampe` : montée linéaire de la référence à la valeur du programme sur `n = 2032 − début + 1`
  budgets ; la dernière année, la valeur exacte du programme. Une durée explicite `annees` est
  admise si la rampe finit au plus tard en 2032 (`annees` ≤ 2032 − début + 1) ; l'alias `rampe` de
  v0.7.0 suit la même borne (jusqu'en v0.7.2, 1 à 6 ans quel que soit le début, si bien qu'une rampe
  pouvait finir en 2035, contre-vérification m5). Au-delà, pour l'un comme pour l'autre : 422 en
  strict (« annees = 6 hors de [1 ; 5] (la rampe finit au plus tard en 2032) »), durée ramenée à la
  borne, correction tracée et `report.valid = false` en tolérant (relecture adverse finale, m-c :
  jusque-là, un profil trop long était ignoré, le programme s'appliquant en plein dès le début) ;
- `annee` : la valeur du programme l'année choisie seulement (dans [début ; 2032]), la référence
  avant et après ;
- `valeurs` (v0.8.1, montants en Md€ seulement) : `{"forme": "valeurs", "valeurs": {"2028": 12.8,
  "2029": 15.7, …}}`, le montant de CHAQUE année du début à une année ≤ 2032, sans lacune ni doublon,
  chacun dans le domaine du paramètre (une valeur datée ne contourne jamais la borne d'un curseur) ;
  après la dernière année écrite, la valeur du programme. Motif : un objectif écrit en part du PIB ou
  du RNB se compte, après l'année visée, par un montant qui suit la richesse nationale (décision du
  mainteneur du 12/11/2026) ; aucune autre forme ne l'écrit. Les mesures de chaque année passent par le
  chemin des autres calendriers : **aucune équation ne change**, ce que prouve l'égalité au bit avec
  une rampe aux mêmes valeurs (`tests/test_release_p_calendrier_valeurs.py`). Interdite aux quatre taux
  et niveaux, aux deux coefficients d'indexation et à la recette d'une seule année (`FORMES_ADMISES`).
  Défaut (année manquante ou en trop, montant non fini ou hors domaine, plus d'entrées que d'années
  du mandat) : 422 en strict, entrée ignorée et correction tracée en tolérant (le programme
  s'applique alors chaque année). Un premier montant égal à la référence retarde l'origine d'horloge
  du levier, comme « une seule année ». Précisions (revue du moteur, v0.8.1) : une année s'écrit en
  quatre chiffres ASCII 0-9 (« ٢٠٢٨ » est illisible) ; aucune règle de monotonie, les montants
  s'appliquent tels qu'écrits ; un objet JSON qui répète une année garde la DERNIÈRE valeur
  (comportement standard du JSON, avant toute validation : le moteur ne voit qu'une année) ; si le
  programme laisse le paramètre à sa référence (valeur égale ou absente de `mesures`), un montant
  qui s'en écarte serait sans effet : 422 en strict, entrée ignorée et correction tracée en tolérant
  (tous les montants à la référence : simple avis « calendrier sans effet ») ; un début ramené après
  l'atterrissage en tolérant ne décale jamais les montants : écrits dès le début demandé, ils ne
  commencent plus au début retenu, l'entrée est ignorée et tracée. Un nombre non fini dans le corps de
  `/simulate` (`NaN`, `Infinity`, `1e400`), quel que soit le champ : 422, jamais 500.

Référence : la valeur du droit en vigueur de l'année (celle du début, sauf valeur datée qui change
ensuite) ; pour un levier absent du droit, son neutre ;
pour un rendement en Md€ de mode exclusif (`rendement_*`), 0. Paramètres éligibles (38) : les
montants en Md€, deux coefficients d'indexation (ci-dessous) et quatre taux ou niveaux qu'un programme écrit avec une montée progressive —
baisse des cotisations salariales (points), taux des cotisations patronales, revalorisation des
salaires des enseignants (%), budget chômage en montant (`engine/cadre.py`, `PROFILS_ELIGIBLES`,
`PROFILS_TAUX_ET_NIVEAUX`) ; pour ces quatre, « plein » et « rampe » seulement (une réforme de
niveau qui s'annule l'année suivante n'est pas un calendrier de programme), rampe = interpolation
linéaire entre le droit en vigueur et la cible, cible exacte en 2032, effets ponctuels émis en
incréments (ouvert après revue adverse). Les autres taux et les durées basculent sans calendrier. La recette exceptionnelle n'admet que la forme « une seule année », à l'année de début
par défaut, et elle est refusée en mode historique. Forme mal écrite : 422 dans les deux modes ; clé
non éligible, année hors du mandat, mode historique : 422 en strict, entrée ignorée et
`report.valid = false` en tolérant ; au plus 38 entrées. Un calendrier posé sur un montant égal à sa
référence est sans effet : un avis le dit.

**Gel d'une année des pensions et des prestations** (décision du mainteneur du 12/11/2026). Les deux
coefficients d'indexation, `retraites.indexation` et `prestations_indexation.taux_indexation`
(`PROFILS_INDEXATIONS`), admettent « plein » et « une seule année » (pas la rampe : le coefficient
s'applique à la revalorisation de chaque année, et un programme écrit un gel ou une sous-indexation,
pas une montée progressive du coefficient). Le moteur garde le coefficient de CHAQUE revalorisation
écoulée : un gel en 2028 suivi d'une revalorisation normale laisse l'écart de niveau de 2028, appliqué
ensuite à la masse revalorisée de chaque année ; aucun rattrapage. L'économie de l'année t ≥ 2028 vaut
donc part indexée × masse nominale de t × π₂₀₂₇ / (1 + π₂₀₂₇) (pensions : part indexée 0,86 ;
prestations : toute la masse), la même que celle d'un gel permanent en 2028. Au statu quo, un gel
total des deux en 2028 rend 6,1 Md€ en 2028, puis 6,3, 6,5, 6,7 et 6,9 Md€ de 2029 à 2032 (inflation
2027 du moteur : 1,37 %), contre 32,3 Md€ en 2032 pour un gel permanent. Avant cette correction, le
moteur recalculait tout l'écart au coefficient de l'année : un retour à 1 effaçait l'économie
(rattrapage implicite complet), d'où l'absence de calendrier sur ces deux clés.

**Effet d'un gel sur les inégalités : l'écart en euros (lot 4, méthode unique du Gini).** Depuis le
lot 4, ces deux leviers émettent K × l'écart en euros de l'année, en incrément : K est le coefficient
par Md€ du levier (prestations ciblées de l'INSEE pour les prestations, coefficient des pensions, centre
d'une plage publiée, pour les retraites ; § Indicateurs Macroeconomiques) et l'écart en euros est l'écart de niveau appliqué à la
masse de 2025 de la catégorie (euros de 2025, l'unité de Y). Un gel d'une année garde exactement
l'écart en euros qu'il laisse, sans rattrapage ; un gel permanent le voit croître jusqu'au plateau des
cohortes ; aucune règle séparée au retour au calendrier, aucun flux résiduel conventionnel. La règle
de la relecture ci-dessous est conservée pour l'historique.

*Historique (relecture adverse finale de la release E, I-1, jusqu'au lot 4) : proportionnel à l'écart
de niveau accumulé.* Ces deux leviers émettaient tout leur effet sur le Gini à l'ouverture d'un
écart (convention pensée pour une sous-indexation durable : c'est l'effet de l'écart au plateau, après
N revalorisations — 7 pour les pensions, `RETRAITES_EROSION_PLATEAU_ANS`, 10 pour les prestations,
`PRESTATIONS_REVALORISATIONS_MAX`) ; l'année du gel est donc celle d'un gel permanent. Au RETOUR à la
référence du calendrier — le droit en vigueur de l'année, quelle que soit sa valeur — après k
revalorisations au coefficient gelé, le levier garde **min(k, N)/N** de l'effet émis au-delà de la
référence (à l'ouverture et, pour les pensions, par le flux des nouvelles cohortes pendant le palier) et
rend le reste : un gel d'une année en garde 1/7 (pensions) et 1/10 (prestations) ; un palier qui n'a
porté sur aucune revalorisation comptée ne garde rien. À coefficient constant, rien ne change : sorties
des scénarios publiés identiques au bit. Ordre de grandeur, gel total des deux coefficients en 2028 au
statu quo (mode cadre) : Gini publié +0,0065 en 2028, comme un gel permanent, puis il redescend au
rythme de convergence du Gini (35 % de l'écart à la cible par an) : +0,0027 en 2032, +0,0021 en 2035,
vers +0,0019. Jusqu'ici, il gardait tout : +0,0165 en 2032 et +0,018 en 2035, presque autant qu'un gel
permanent (+0,0168 en 2032) pour une économie cinq fois moindre. Et le retour ne se reconnaissait qu'à
l'égalité au littéral 1,0 : avec un droit en vigueur à 0,9999 (fichier remplaçable sans code), le même
gel rendait presque tout (+0,0013 en 2032 au lieu de +0,0165) ; l'effet est désormais continu,
proportionnel à l'écart gelé (droit à 1,0 ou 0,9999 : +0,0027 en 2032 ; à 0,9 : +0,0025). **Limites
dites** : à euros égaux en 2032, le gel d'une année des deux coefficients émet encore 3,6 fois le Gini
du même montant écrit en `prestations_menages` (35 fois avant ; 0,5 fois pour les pensions seules,
7,1 fois pour les prestations seules), moitié moins que la sous-indexation permanente (7,2 fois) :
l'écart vient des règles par Md€ des deux leviers, antérieures à cette passe (≈ 14 pour les
prestations, au backlog) ; un changement de coefficient qui ne revient pas à la référence de l'année
(par exemple une valeur datée du droit en vigueur) suit la règle d'incrément.

**Effets ponctuels sous une rampe** (limite dite, contre-vérification m3) : ils sont émis en incréments,
et leur cumul vaut l'effet du palier quand l'effet ne lit que le paramètre. Quand il lit aussi une
grandeur de l'année (la masse salariale nominale : compétitivité des cotisations patronales et des
salaires des enseignants), le cumul dépend du chemin : pour une rampe 2028-2032, + 6,6 % pour les
cotisations patronales et − 8 % pour les salaires des enseignants par rapport au calendrier « chaque
année » ; l'indice de compétitivité gagne ainsi ≈ 0,15 point pour une baisse de cotisations patronales en
rampe. L'exprimer en part du PIB relève d'une passe dédiée.

**Rampe et valeur datée** (contre-vérification m7) : la référence d'une rampe est le droit de CHAQUE
année ; si le droit change pendant la rampe, le chemin n'est pas monotone. Exemple (banc du relecteur) :
rampe de 6,8 à 10 dès 2028, droit ramené à 0 en 2030 : 7,44 → 8,08 → 6,0 → 8,0 → 10. C'est la règle
voulue (« le droit de l'année, puis la cible ») ; un programme qui veut un chemin monotone l'écrit en
« chaque année ».

**Horloge.** Les montées en charge internes d'un levier partent de son origine : la première année
où il s'écarte du droit en vigueur (l'année de début pour « chaque année » et la rampe : sorties
inchangées). Un effet ponctuel émis l'année choisie est rendu l'année suivante. Bloc `cadre.profils`
toujours émis (`{}` sans calendrier) : par paramètre, `forme`, `annee`, `origine` et `valeurs`. La
requête `rampe: {annees, leviers}` (v0.7.0) est un alias d'un profil « rampe » de durée `annees` :
une seule implémentation, sorties identiques au bit.

### Valeurs datées du droit en vigueur (v0.8.0)

Champ facultatif `valeurs_datees` de `budget_simulator/data/droit_en_vigueur.json` : le droit de
l'année `a` prend, pour chaque paramètre daté, la valeur du segment qui contient `a`. Un réajustement
d'atterrissage de l'année `y` ne vaut que dans le segment de `y` : une mesure votée pour un an ne se
reconduit pas, même réajustée. Après l'année de début, un changement de segment s'applique aux
leviers que le programme ne fixe pas, et à la référence d'un calendrier cette année-là : « une seule
année » rend le droit de l'année les autres années, « rampe » interpole entre le droit de l'année et
la cible (corrigé après revue adverse : la référence restait le droit du début, et un calendrier
« une seule année » reconduisait ensuite une mesure votée pour une durée limitée). Segments
contigus depuis 2026, dernier segment ouvert, source non vide : sinon le fichier est refusé. La
v0.8.0 est livrée sans aucune valeur datée.

**v0.8.1 (release de paramètres P)** : une seule valeur datée, la surtaxe d'IS des grandes entreprises
(`is_exceptionnel_tge.montant`) : 7,3 Md€ en 2026 dans le fichier (l'atterrissage la réajuste à
6,8 Md€ en 2026 seulement), 0 dès 2027. Sources du fichier : loi n° 2026-103 de finances pour 2026,
art. 12 (contribution due au titre des deux premiers exercices clos à compter du 31 décembre 2025) et
BOFiP ACTU-2026-00097 ; projet de loi de finances pour 2027 (n° 3210), qui la prorogeait, considéré
comme rejeté par l'Assemblée nationale le 4 novembre 2026 (T.A. n° 362). Une loi de finances pour 2027
votée remplacera ce segment. Les taux votés des leviers à taux de la release E sont inscrits au droit
(`fiscalite_capital` 12,8 % et 18,6 %, `multinationales.taux_tsn` 3 %, `operations_financieres.taux_ttf`
0,4 %, `rachats_actions` 0 = la taxe de 8 % en vigueur), sans effet sur les trajectoires ; leurs
paramètres de comportement (élasticité, érosion) restent au défaut du moteur, hors du droit. Un bloc qui
les écrit aussi, à leur défaut, laisse les sorties identiques au bit mais fait figurer le levier dans
`cadre.leviers_modifies` (règle « présent = imposé »).

### Garde-fous d'entrée (v0.8.0)

- **Levier inconnu** : strict, `LevierInconnu` (422) ; tolérant, levier retiré, `report.valid =
  false` et une entrée `LEVIER_INCONNU` dans `report.corrections`. Le registre de référence est celui
  du moteur.
- **Exclusions mutuelles** (`constants.EXCLUSIONS_MUTUELLES`), quand deux curseurs feraient varier
  le même euro :

  | Règle | Conditions | Levier ignoré | Motif |
  |---|---|---|---|
  | X1 | `droits_succession.variation` ≠ 0 et `fiscalite_patrimoine.intensite` ≠ 0 | `droits_succession` | le curseur du patrimoine fait déjà varier les droits de succession |
  | X2 | `transferts_etranger.montant` ≠ 0, `rabot_uniforme.taux_reduction` > 0 et `exclure_ue` = 0 | `transferts_etranger` | le rabot qui n'exclut pas la contribution à l'UE la coupe déjà |

  Strict : `LeviersIncompatibles` (422) ; tolérant : le levier désigné n'est jamais appliqué, la
  trajectoire est celle de l'autre seul, `report.valid = false` et une entrée de la règle dans
  `report.corrections`. Un droit en vigueur qui remplirait lui-même une condition est refusé au
  chargement.

---

## Hypotheses Demographiques

### Evolution des Depenses Publiques

Le simulateur distingue trois logiques d'evolution :

1. **Depenses endogenes** : Varient avec le taux de chomage (allocations)
2. **Depenses exogenes fixes** : Taux de croissance constant (famille, logement)
3. **Depenses demographiques** : Sensibles au vieillissement (retraites, sante, dependance)

### Calibrage sur Projections Officielles

| Organisme | Domaine | Projection 2025-2035 |
|-----------|---------|----------------------|
| **COR** | Retraites | Quasi-stabilisation a 14,0-14,1% du PIB |
| **DREES** | Sante | +0,1 a +0,3 points de PIB |
| **INSEE/DREES** | Protection sociale | Tendance +0,15 pts/an |

**Sources** : COR juin 2025, DREES Comptes sante 2024, INSEE 2024

### Taux de Croissance Reels des Depenses (v3.0)

| Categorie | Taux reel | Source |
|-----------|-----------|--------|
| Retraites | +1,2%/an | COR 2025 : 13,9->14,0% PIB |
| Sante | +1,8%/an | ONDAM tendanciel |
| Chomage | -0,3%/an | Reforme assurance chomage |
| Dependance | +2,5%/an | Baby-boomers 85+, plan autonomie |
| Minima sociaux | +0,5%/an | Indexation legale |
| Masse salariale | +0,3%/an | Revalorisations point d'indice, GVT |
| Education fonctionnement | +0,3%/an | Renovation, numerique |
| Defense equipement | +3,0%/an | LPM 2024-2030 lissee |
| Collectivites | +0,5%/an | Cour des comptes : +0,8% volume 2025 |
| Investissements | +1,0%/an | France 2030 |
| Aides entreprises | 0,0%/an | CIR/CICE stables |
| Transition eco | +2,5%/an | MaPrimeRenov post-montee en charge |

**Important v3.0** : Defense est a +3,0%/an reel (pas 5,5%), transition_eco a +2,5%/an (pas 4,0%). Ces corrections evitent une surestimation des depenses baseline.

**Rabot uniforme (v3.0)** : Utilise desormais la base de depenses dynamique de l'annee en cours, et non plus la base figee 2025. Cela evite la sous-estimation de l'impact des coupes dans le temps.

**Rabot uniforme, assiette en euros de l'année (lot 3, proposé après v0.8.1).** La coupe s'applique aux dépenses de
l'année en euros courants (masse nominale de chaque catégorie), la méthode de la note de l'Institut Montaigne
(annexe 4, p. 141 : « tendanciel en volume ajusté par le déflateur du PIB »). Jusqu'au lot 3, l'assiette était en
volume (euros 2025) : un rabot de 8 % ne valait qu'environ 7,4 % des dépenses de l'année en 2032. L'AAH, part en
espèces de la catégorie « dépendance », suit la même assiette.

**Rabot uniforme, exclusion de la défense au-delà des équipements (lot 3, équation).** La défense exclue de la coupe
vaut une part du PIB de l'année (`MONTAIGNE_DEFENSE_PART_PIB`), dont la catégorie « équipements », exclue en entier.
Le moteur n'a pas de catégorie « défense » hors équipement : le reste (personnel, pensions, fonctionnement) est
retiré au prorata des autres catégories, ce qui laisse inchangée la composition sociale de la coupe (convention
déclarée). L'indice d'inégalités du rabot (coefficient par milliard de prestations en espèces coupées, montant
d'année pleine de 2025) porte la même part coupée, calculée sur les dépenses et le PIB de 2025. À la valeur neutre 0,
seule la catégorie « équipements » est exclue, comme avant.
Enjeu du prorata, mesuré sur la pile assemblée (scénario de la note, mode cadre) : retirer ce reste des seules
pensions changerait le pouvoir d'achat 2032 de +0,13 point d'indice et la dette 2032 de +0,05 point ; de la seule
masse salariale, de −0,07 et −0,02 point (la coupe totale est la même).

**Rabot uniforme, défense au périmètre de la note (lot 3, valeur sourcée).** La part de la défense exclue est celle
de la note : 2,7 % du PIB, pensions comprises (p. 81 : « dépenses de défense portées à 2,7 % du PIB d'ici 2029, soit
91 Md€ » ; note 113 : « En intégrant les pensions »), au lieu de la seule catégorie « équipements » (25 Md€ en 2025).
Avec le PIB du moteur, 2,7 % du PIB font 86 Md€ en 2029 (la note suppose un PIB plus élevé). Convention déclarée,
aucune source ne tranchant : la note fixe ce niveau pour 2029 ; le moteur le garde chaque année du rabot, 2028
compris, comme il garde le taux de 8 % au-delà de 2029. Enjeu mesuré : ne l'appliquer qu'à partir de 2029
baisserait la dette 2032 du scénario de la note de 0,03 point.

**Rabot uniforme, contribution à l'Union européenne (lot 3, correction).** Les catégories du moteur somment la dépense
primaire des administrations publiques (Insee, tableau 3.201) ; « autres » en est le résidu, et cette dépense compte
la contribution de la France au budget de l'Union européenne (opération D76, « ressources propres de l'UE fondées sur
la TVA et le RNB »). Montant 2025 : 22,983 Md€ (Eurostat, comptes nationaux annuels des secteurs, administrations
publiques, provisoire) ; il suit le chemin de sa catégorie, le moteur ne projetant pas la hausse que la note prévoit
(44 Md€ en 2029). Avec l'exclusion (`exclure_ue = 1`, celle de la note), la contribution est retirée de l'assiette de
« autres » ; sans elle, elle est rabotée une fois, dans « autres ». Jusqu'au lot 3, elle restait rabotée même exclue
(environ 2 Md€ de coupe en trop par an à 8 %), et sans exclusion 44 Md€ × taux étaient ajoutés par-dessus : la même
dépense coupée deux fois.

**Coupe du scénario de la note et écart à la note (limite déclarée).** Au taux de 8 %, premier budget en 2028, la
coupe vaut 137,5 Md€ en 2029. La note chiffre 138 Md€ (graphique, p. 84) à 140 Md€ (texte, p. 83), soit 8 % de
1 741 Md€ (139,3) : le moteur coupe un peu moins, de 0,5 à 2,5 Md€ en 2029. Son assiette 2029 vaut 1 719 Md€ au lieu de
1 741 : ses propres projections de dépense et de PIB (3 178 Md€ en 2029 ; les 91 Md€ de défense de la note, pour 2,7 %
du PIB, supposent un PIB de 3 370 Md€). Le périmètre n'est pas réglé pour retrouver la cible : l'écart est déclaré, pas
corrigé. Enjeu : une coupe de 2 Md€ de plus par an, l'ordre de grandeur de l'écart, baisserait la dette 2032 du
scénario d'environ 0,01 point (mode cadre).

### Assemblage des Depenses (v4.0 — recurrence unique chainee)

Depuis la refonte « assemblage temporel » (juin 2026), les taux par categorie ci-dessus ne portent plus le NIVEAU des depenses : ils servent de **cle de repartition** dans la croissance en volume agregee. La recurrence appliquee des l'annee 1 est :

```
Depenses(t) = Depenses(t-1) x (1 + g_vol) x (1 + pi_idx)
```

- `g_vol` : croissance en VOLUME — moyenne des taux reels par categorie (+ ajustements demographiques, sectoriels et cycliques), ponderee par les parts courantes de chaque categorie
- `pi_idx` : indexation mixte des prix — **54%** de la depense suit l'inflation **PASSEE** (pensions et prestations revalorisees sur l'inflation N-1, realite institutionnelle francaise, FIPECO ; constante `INDEXATION_DEPENSES_INFLATION_PASSEE`), **46%** suit le deflateur **contemporain**

Le chainage sur le niveau de l'annee precedente supprime PAR CONSTRUCTION l'ancien regime special 2026 (« bridging year » a formule fermee + taux d'amorcage exogene, dont le niveau etait jete au passage a l'annee 2). C'est la pratique institutionnelle standard (CBO/OBR/DG Tresor) : l'annee 1 se distingue par ses donnees, jamais par sa mecanique. Resultat statu quo : croissance reelle des depenses primaires entre **+0,8% et +1,4% CHAQUE annee** (tendanciel officiel +1,0-1,2%/an), verifie par `tests/test_baseline_properties.py`.

---

## Retraites

### Parametres Cles

| Parametre | Reference | Impact |
|-----------|-----------|--------|
| Age legal | le DROIT EN VIGUEUR de l'annee simulee : 62,75 ans (62 ans 9 mois) en 2026-2027, puis +3 mois par an jusqu'a 64,0 ans en 2032 | bareme PLAT et SYMETRIQUE : +/-6,0 Md EUR par annee d'age d'ecart a la reference, sur tout le domaine 60-67 ans ; phasing cohortes 5 ans |
| Duree cotisation | 42,5 ans (170 trimestres) | +/-2 Md EUR par semestre (+/-4 Md EUR par annee, phasing 5 ans) |
| Indexation | 100% inflation | v0.6.7 : écart de niveau composé des revalorisations évitées (chacune à l'inflation de l'année précédente, N−1) sur 0,86 de la masse nominale des pensions, SYMETRIQUE au premier ordre, plateau 7 ans |

### Hypotheses Economiques

**Age de depart — la reference (refonte v0.6.1) :**

L'age de reference n'est plus une valeur figee : c'est **le calendrier legal**,
annee par annee. La LFSS 2026 gele l'age d'ouverture des droits (AOD) a
62 ans 9 mois a compter du 1er septembre 2026 et **jusqu'au 1er janvier 2028
seulement** ; la montee en charge de la reforme 2023 (+3 mois par generation)
**reprend ensuite** jusqu'a 64 ans.

| Annee simulee | 2026 | 2027 | 2028 | 2029 | 2030 | 2031 | 2032 et apres |
|---|---|---|---|---|---|---|---|
| Age legal de reference | 62,75 | 62,75 | 63,00 | 63,25 | 63,50 | 63,75 | **64,0 ans en 2032** |

Pourquoi c'est structurant : la baseline du simulateur est calee sur le
tendanciel de la mission IGF de juillet 2026, dont les hypotheses retraites
integrent explicitement la suspension jusqu'en 2028 — **la reprise vers 64 ans
est donc DEJA dans la baseline**. Avec une reference figee a 62,75 ans, un
programme qui dit « je maintiens 64 ans » etait credite d'une economie que la
loi produit deja (double comptage), et un programme a 60 ans etait chiffre sur
2,75 annees alors que l'ecart au droit en vigueur a horizon 2032 est de
4,0 annees. La correction joue **dans les deux sens**.

Consequence de lecture : un curseur laisse a 62,75 ans sur tout l'horizon ne
decrit pas « je ne touche a rien », mais « je suspends la reforme
definitivement » — ce qui a un cout (jusqu'a 7,5 Md EUR/an de pensions brutes
a partir de 2032, 6,8 Md EUR net de la fuite sociale).

**Corollaire : le statu quo n'est pas un nombre.** Puisque la reference bouge
de 62,75 a 64,0 ans entre 2026 et 2032, AUCUN age fixe ne decrit « je ne touche
a rien » sur tout l'horizon. Le statu quo est donc encode par l'**absence** de
curseur d'age : ni les valeurs par defaut du moteur (`/scenarios` →
`status_quo`), ni le point de depart du simulateur, ni le scenario de reference
« Budget 2026 (vote) » ne posent d'`age_depart`, et l'ecart au droit en vigueur
y est rigoureusement nul chaque annee. Toute valeur posee — 62,75 comprise —
est une MESURE, et elle est chiffree comme telle. Dans l'interface, la position
neutre du curseur s'affiche « calendrier legal » ; on y revient par le bouton
« Reinitialiser ».

**Age de depart — le bareme (refonte v0.6.1) :**
- **6,0 Md EUR par annee d'age** d'ecart a la reference legale de l'annee, en
  moindres depenses de pension. Bareme **PLAT** sur tout le domaine 60-67 ans
  et **strictement SYMETRIQUE** : une annee de report rapporte exactement ce
  qu'une annee d'abaissement coute. Montee en charge cohortes 5 ans.
- Deux sources primaires independantes convergent **au dixieme** sur cette
  valeur, pour une annee d'age :
  - **DG Tresor**, *Effets d'une mesure d'age sur le solde des APU*, document
    n 12 de la **seance pleniere du COR du 27 janvier 2022**, diapositive 5 :
    -0,4 pt de PIB pour un report de 2 ans, soit 0,20 pt/an x 2 991 Md EUR
    = 5,98 Md EUR ;
  - **Cour des comptes**, *Situation financiere et perspectives du systeme de
    retraites*, fevrier 2025, **tableau n 6, p. 72** (variante symetrique
    generations 1964-1968, exercice 2035, Md EUR constants 2024) : **6,0 Md EUR**
    de moindres depenses (4,3 de base + 1,7 de complementaires).

  Base de conversion validee par le COR lui-meme (*Dossier en bref* de la
  seance du **26 mars 2026** : « 0,2 point de PIB ex ante (6 milliards
  d'euros) »).
- Ce que la v0.6.0 affichait (14,2 Md EUR/an sous 64 ans) etait **faux d'un
  facteur ~2,4** : voir le piege de lecture ci-dessous. La « falaise » de -58 %
  a 64 ans venait entierement de ce premier segment errone, pas d'un phenomene
  source.
- **Bande de sensibilite publiee** : une baisse d'une annee d'age coute entre
  **4,2 et 6,0 Md EUR** selon qu'on retient ou non l'asymetrie hausse/baisse.

**Choix assumes (aucune source ne les etablit — declares, jamais masques) :**
1. **Au-dela de 65 ans**, aucune source consultee ne chiffre le passage 65->66
   ni 66->67, alors que le curseur monte a 67 ans : prolonger le palier est une
   **convention**, pas une estimation. Le rendement decroissant est reel mais
   doux (0,285 -> 0,25 -> 0,20-0,25 pt sur le solde du systeme), jamais en
   falaise. Hors de la plage 63-65 ans, le chiffrage est une extrapolation.
2. **Symetrie stricte**. Un facteur d'asymetrie a la baisse (0,70) est publie,
   mais il est mesure sur le seul palier 64->63 et decoule d'une hypothese
   explicite sur les carrieres longues : **rien ne le valide de 62 vers 60**.
   Surtout, aucune des deux options n'est neutre — un coefficient plus faible a
   la baisse **allege** le cout affiche des programmes d'abaissement de l'age,
   un coefficient plus eleve les **alourdit**. La symetrie est le seul choix
   qui ne demande pas de prendre parti, et c'est deja la philosophie du
   handler.

**Perimetre du levier — ce que le handler ne contient PAS (et ou ca vit) :**
- Le canal **cotisations** (Cour, T6 : +2,4 Md EUR par annee d'age ; DG Tresor :
  +1,5) n'a **aucun slot** dans le handler retraites : il nait du canal
  PIB/emploi ci-dessous, ce qui rend le double comptage structurellement
  impossible. Ce n'est pas une omission, c'est la garde elle-meme.
- Le **canal emploi seniors** (offre de travail -> PIB -> recettes, bosse de
  chomage transitoire, fuite sociale residuelle) est modelise depuis la
  v0.6.1 — voir la section dediee ci-dessous. Il etait absent des versions
  precedentes, **dans les deux sens**.

### Canal emploi seniors (v0.6.1)

Une mesure d'age ne fait pas que decaler des pensions : elle **augmente
l'offre de travail**, donc le PIB, donc les recettes publiques ; elle produit
au passage une **bosse de chomage transitoire** et une **fuite** vers d'autres
prestations. Ces trois effets forment une **identite comptable** et sont
livres ensemble (COR, seance pleniere du 26 mars 2026, Document n 3,
encadre 2). Ils jouent en sens **opposes** : le premier en faveur des
programmes de report d'age, les deux autres contre.

**1. Offre de travail -> PIB : +0,80% de niveau de PIB par annee d'age**

C'est le milieu du consensus publie par le COR (Dossier en bref du
26/03/2026 : « 0,7 a 0,9 point de PIB », « 210 000 a 240 000 emplois » pour un
an d'age). Les trois modeles a long terme : I-MIP 0,93 / OFCE 0,78 /
DG Tresor 0,7 a 20 ans.

**C'est un effet de NIVEAU, pas de TAUX** — la distinction est structurante.
Le moteur ne consomme que l'**increment annuel** de ce niveau : +0,12 point de
croissance au maximum, une seule annee (2030), et jamais plus de +0,15.
Montee en charge (fraction du niveau de long terme, par annee) :

| Annee | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Fraction du LT | 0,025 | 0,139 | 0,236 | 0,357 | 0,507 | 0,541 | 0,578 | 0,617 | 0,658 | 0,702 |
| Niveau de PIB (pt) | 0,02 | 0,11 | 0,19 | 0,29 | 0,41 | 0,43 | 0,46 | 0,49 | 0,53 | 0,56 |

Le canal passe par la **croissance potentielle**, jamais par la demande : un
choc d'offre n'ouvre donc ni ecart d'Okun ni output gap (cf. § Croissance
Potentielle Supply-Side).

**2. Bosse de chomage transitoire : +0,18% au pic par annee d'age**

Une partie des seniors maintenus en activite bascule au chomage plutot qu'en
emploi. Cette valeur est une **DERIVATION PROPRE A CE SIMULATEUR — elle n'est
publiee par aucune institution**, et il faut le dire clairement, parce que
c'est le point ou les modeles officiels divergent le plus : a un an, la
DG Tresor trouve **0,00**, l'I-MIP **-0,40** et l'OFCE **+0,55** (COR
26/03/2026, Document n 2, tableau 4). La divergence est irreductible a court
terme ; nous ne tranchons pas a leur place, nous nous positionnons entre eux
et nous publions comment.

Les trois routes de la derivation, toutes appuyees sur la part « chomage » du
devenir des seniors decales — **stable a 26-27 % sur deux methodologies et
deux sources de donnees independantes** :

| Route | Base | Resultat |
|---|---|---|
| (a) Troisieme derivation — **base intermediaire non reproductible** (cf. ci-dessous) | non publiable en l'etat | **+0,13** |
| (b) Cles Dubois-Koubi hommes (63 % emploi / 26 % chomage / 11 % inactivite) | 305 000 decalants | **+0,19** |
| (c) Cles Rabate-Rochut (44 / 27 / 29) | 305 000 decalants | **+0,21** |
| | **Moyenne retenue** | **+0,18** |

**Ce que nous ne pouvons pas etayer, et nous le disons plutot que de le
combler** (revue adverse du 25/08) : les routes (b) et (c) se recalculent
integralement a partir des elements ci-dessous — cle de repartition publiee ×
variation de population active, rapportee a la population active totale. La
route (a) ne s'y ramene pas : la localisation de source et la base de calcul
qui figuraient ici n'ont pas ete etablies par la collecte, et la base publiee ne
reconstituait pas le resultat publie. Elles sont **retirees** — la regle du
projet est de retirer, jamais de re-sourcer par approximation.

Consequence a connaitre, dans les deux sens : la moyenne retenue (**+0,18**)
est tiree vers le BAS par cette route (0,13 contre 0,19 et 0,21). Une bosse de
chomage plus faible **allege** le cout affiche des programmes de report d'age
et **allege** le gain affiche des programmes d'abaissement. La valeur n'a pas
ete recalculee ici : la modifier serait un recalibrage, qui exige sa propre
passe de sourcing, pas une correction de redaction.

Sources primaires : Dubois Y. & Koubi M., Insee, document de travail
G2016/08 (2016) et Insee Analyses n 30 (05/01/2017) ; Rabate S. & Rochut J.,
*Journal of Pension Economics and Finance* 19(3), 2020, p. 293-308. Base
demographique : population active 31 802 milliers, chomage 7,3 % (COR
26/03/2026, Document n 4, note 7).

Position dans le debat : entre DG Tresor 0,0 et OFCE +0,55, tres loin de
Mesange +0,7 / e-mod.fr +0,5 — que la Cour des comptes desavoue explicitement.
Les deux chiffres sont ceux de sa **note 121** (fevrier 2025, p. 67 : « le
chomage augmente a horizon de 10 ans de 0,7 point dans Mesange et de 0,5 point
dans e-mod.fr ») ; le desaveu, lui, est au **corps de cette meme page 67** :
« les recherches micro-econometriques menees sur la reforme de 2010 ont montre
que l'evolution du chomage observee ne correspondait pas a celle predite par
les modeles ».

La bosse se **resorbe** (profil OFCE, seule serie publiee allant jusqu'a
l'extinction) : pic **+0,10 point** en annees 4-5 par annee d'age, +0,064 a
dix ans, +0,029 a vingt ans, **zero a long terme**. Le mecanisme de la
resorption est source (COR, Document n 6, partie 3) : l'offre de travail
accrue ralentit les salaires et le revenu global de l'economie augmente — les
deux relevent la demande de travail.

**3. Fuite sociale residuelle : 9,6% des economies brutes**

Cour des comptes, fevrier 2025, p. 67-68, citant **DREES, note BRET n 21-43,
janvier 2022** et **DARES, note SD-EMT-DSIDE, janvier 2022** — les deux notes
primaires **n'ont pas pu etre consultees directement**, elles sont donc citees
**via la Cour** (p. 67, note 125) et jamais comme source de premiere main :
la hausse des prestations represente **20 %** des economies brutes, dont
**52 % d'assurance chomage, 36 % d'indemnites journalieres et 12 % de minima
sociaux**.

Le simulateur n'en inscrit que **9,6 %** (= 48 % x 20 %, soit les indemnites
journalieres et les minima sociaux) : la part assurance-chomage est **deja
produite** par le moteur, dont la categorie de depense « chomage » suit le
taux de chomage — que la bosse ci-dessus fait precisement bouger. Inscrire
les 20 % complets serait un double comptage. Verification croisee : au pic,
+0,10 point de chomage sur une base de 40 Md EUR donne 0,53 Md EUR, contre
0,62 Md EUR par la cle DREES/DARES — ecart de 14 %.

Le debat « 20 % ou 25 % » est clos : **les deux, selon le denominateur**
(20 % = hors invalidite/AAH, avec chomage, rapporte au solde du systeme —
Cour des comptes ; 25 % = avec invalidite/AAH, hors chomage, rapporte aux
depenses de retraites — DREES).

**Bouclage : ce que l'ensemble reconstitue**

Pour une annee d'age a horizon dix ans, moindres depenses + recettes nees du
PIB donnent **17,5 Md EUR**, contre **17,7 Md EUR** dans la decomposition de
la Cour des comptes (fevrier 2025, tableau n 6, p. 72 : depenses de retraites
+6,0 / cotisations retraites +2,4 / autres recettes publiques +9,3 / ensemble
des APU +17,7). Le simulateur ne cale rien sur ce total : il le retrouve.

**Choix assumes de ce canal (declares, jamais masques) :**
1. Les horizons 3, 4 et 6 a 9 ans ne sont publies par personne : ce sont des
   **interpolations log-lineaires** entre les points publies (1, 2, 5, 10, 20
   ans et long terme).
2. La montee en charge par cohortes (5 ans) **multiplie** le profil
   d'absorption macroeconomique. Les deux profils decrivent des phenomenes
   distincts et le raisonnement tient, mais **le produit n'est mesure par
   personne**. Sa sensibilite est testee : le bouclage a dix ans est de
   17,5 Md EUR avec la multiplication et 18,2 sans — le choix ne change pas
   la conclusion.
3. **Les QUATRE canaux demarrent a l'annee ou l'ecart s'ouvre**, pas a l'annee
   ou la simulation commence — les deux profils macro comme la montee en charge
   par cohortes du canal budgetaire, qui est le MEME facteur (les profils
   macro l'incluent multiplicativement). Ils decrivent la reaction de
   l'economie a un choc d'age : leur horloge part quand le choc part. La
   distinction n'est pas
   theorique — la reference legale monte de 62,75 ans (2026-2027) a 64,0 ans
   (2032), donc un programme qui pose l'age a 62,75 a un ecart **rigoureusement
   nul** les deux premieres annees et ne s'ecarte du droit en vigueur qu'a
   partir de 2028. Indexer sur l'annee de depart de la simulation lui
   appliquait la bosse de chomage **en pleine phase de resorption** et un
   niveau de PIB deja presque forme.
4. **Un ecart qui s'ouvre progressivement est date une seule fois.** Le
   simulateur ne convolue pas une suite de chocs annuels : il date le choc a
   sa premiere annee non nulle et applique une seule montee en charge. Une
   convolution exigerait de decomposer un profil publie en reponses
   impulsionnelles, ce que le COR ne publie pas.
   **Consequence chiffree, a dire plutot qu'a decouvrir** : sur un programme a
   age FIXE, l'ecart au droit en vigueur continue de s'elargir jusqu'en 2032
   pendant que la montee en charge court deja. Les deux rampes se multiplient,
   donc l'increment annuel de niveau de PIB par annee d'age depasse celui d'un
   ecart maintenu constant : **0,177 point au maximum contre 0,120**, sur tout
   le domaine du curseur (60 a 67 ans). Le maximum est atteint pour l'age dont
   l'ecart s'ouvre le plus tard — la valeur gelee, 62,75 ans. C'est une
   propriete de la convention, pas une estimation ; elle est bornee et testee
   (test-propriete P7, forme rampe).

**Ce qui n'est deliberement PAS modelise** (et pourquoi — c'est de la sobriete,
pas un oubli) :

| Tentation | Pourquoi non |
|---|---|
| Effet d'eviction sur l'emploi des jeunes | Consensus macro sur l'**absence** d'effet : Kalwij, Kapteyn & De Vos 2010 (22 pays OCDE, 1960-2008), Gruber, Milligan & Wise 2009, Ben Salem, Blanchet, Bozio & Roger 2010, Munnell & Wu 2012, Carta, D'Amuri & von Wachter 2025. L'effet existe au niveau de la **firme** et ne remonte pas au macro |
| Effet sur la productivite | « La litterature empirique ne met pas en evidence d'effet negatif systematique » (COR 26/03/2026, Document n 6, p. 8) |
| Baisse de l'epargne par anticipation | Non identifiable en France ; la DG Tresor emet elle-meme un doute (COR, Document n 3, annexe p. 8-9) |
| Elasticite OFCE 0,30 (emploi / population active) | Decrit un choc « soudain » et indifferencie ; l'ex post francais donne 0,60-0,70, la population touchee etant deja en emploi |
| Effet du canal sur les **inegalites** | **NON ETABLI** : l'heterogeneite est forte et documentee (capital humain eleve prolonge son activite, carrieres discontinues basculent en chomage ou invalidite), mais aucune source ne la chiffre. Le coefficient Gini du levier d'age reste **inchange** par ce canal |
| **Canal emploi du levier « duree de cotisation »** | **ASYMETRIE ASSUMEE, ET C'EST LA PLUS IMPORTANTE A CONNAITRE.** Le canal n'est cable que sur l'age d'ouverture des droits. Une duree d'assurance deplace pourtant le meme age effectif de depart — 40 annuites au lieu de 42,5, c'est partir plus tot — mais le levier ne produit que sa ligne de depense : ni offre de travail vers le PIB, ni bosse de chomage, ni fuite sociale. Mesure : un mouvement de 2,5 ans obtenu par la duree vaut +2,3 points de dette 2035, le meme mouvement obtenu par l'age en vaut +10,4, soit un rapport de 1 a 4,5. **Ce n'est pas neutre en pratique** : le plus gros mouvement a la baisse de la duree est celui de LFI (non taxe par le canal), les mouvements a la hausse sont ceux du PS, des Republicains, d'Horizons et de l'Institut Montaigne (non credites). Le calibrage du levier de duree n'a pas ete audite par la passe de sourcing v0.6.1 ; tant qu'il ne l'est pas, l'asymetrie est **dite** plutot que corrigee a l'aveugle — corriger un levier non source pour « faire symetrique » deplacerait des programmes sur une valeur inventee |

**Piege de lecture a connaitre : les deux « 17,7 Md EUR » n'ont aucun rapport**

C'est l'erreur qui a produit le bareme de la v0.6.0. Deux grandeurs portent le
meme nombre et mesurent des objets differents :

| | Senat, rapport n l23-498 (2023-2024) | Cour des comptes 02/2025, tableau n 6 |
|---|---|---|
| Ce que 17,7 Md EUR mesure | produit **BRUT** de l'age **+ acceleration Touraine** | effet **toutes APU** d'**UNE** annee d'age |
| Perimetre | systeme de retraites | ensemble des finances publiques |
| Annee | 2030 | 2035 |
| Millesime | **euros courants** | **euros constants 2024** |
| Montee en charge | **partielle** | **complete** |

Table de passage fermee et verifiee cote Senat :
17,7 + 2,0 (autres recettes) - 6,8 (accompagnement) = 12,9 ~ 13,0 Md EUR —
confirme verbatim par le Senat (« reduire de 13 milliards d'euros son deficit
previsionnel en 2030 ») — puis divise par un deflateur ~1,10 = 11,8 Md EUR, la
valeur Rexecode du tableau n 5 de la Cour. Ce deflateur n'est **pas publie** :
il est reconstitue, et presente comme tel.

Deux precautions qui restent valables pour tout futur recalibrage :
- **tension interne au rapport de la Cour** : son tableau 4 donne +0,4 pt de PIB
  pour le systeme, son tableau 5 donne 9,7 Md EUR constants 2024 (soit 0,33 pt,
  qui s'arrondit a 0,3). Les deux ne sont **pas reconciliables a la precision
  publiee** : on ne fabrique pas de passerelle, on privilegie les tableaux en
  Md EUR ;
- le chiffre du Senat melant age et duree d'assurance sans ventilation publiee,
  il n'est **plus utilise comme cible de calibration** du levier d'age.

Enfin, l'attribution « Cour des comptes, 14 Md EUR bruts pour 60->62 » qui
figurait dans le code a ete **retiree** : elle est introuvable dans le rapport
cite. L'ordre de grandeur voisin qui circule (0,43 pt de PIB a horizon 2030
pour un AOD ramene de 62 a 60 ans) provient d'une decomposition **DREES**
relayee par l'**Institut Montaigne** (fiches presidentielle 2022 et
legislatives 2024) ; la note DREES d'origine n'ayant pas ete retrouvee en
ligne, elle est citee **par son relais**, jamais comme source de premiere main.

**Indexation des pensions :**
- Base : 17 millions de retraites x pension moyenne
- Indexation 100% = maintien pouvoir d'achat (statu quo legal, impact budgetaire nul)
- Erosion CUMULATIVE (v0.6.7, audit externe Codex 10/2026) : `économie(t) = 0,86 de la masse
  nominale des pensions de l'année × [1 − Π_s (1 + (1 − δ) × π⁺_{s−1}) / (1 + π⁺_{s−1})]`,
  π⁺ = max(π, 0), δ = 1 − indexation, une revalorisation par an dès 2026, sept au plus (plateau
  7 ans) — le stock de pensions erode se renouvelle (nouvelles pensions liquidees sur les salaires,
  extinction des cohortes anciennes) ; l'écart constitué subsiste ensuite, sans se rembourser.
  Chaque facteur est le rapport exact de deux masses : la masse revalorisée de (1 − δ)π à la masse
  revalorisée de π. La masse nominale de l'année est celle du statu quo, DÉJÀ pleinement
  revalorisée (elle porte l'indice de prix cumulé des dépenses du moteur, `pi_idx` ci-dessus).

  > **Corrigé en v0.6.10 (contre-audit externe, V2-03).** Jusqu'en v0.6.9, chaque facteur valait
  > `1 − δ × π⁺`, une approximation au premier ordre : appliquée à une masse déjà revalorisée, elle
  > omettait le dénominateur `1 + π`. Exemple : une masse de 100 revalorisée de 2 % vaut 102 ; gelée,
  > elle reste à 100, l'économie est exactement 2 — l'ancienne formule donnait 2,04 ; après dix
  > revalorisations à 2 %, écart 17,97 % au lieu de 18,29 %. Le facteur exact est
  > `1 − δ × π⁺ / (1 + π⁺)` ; même formule pour la sur-indexation (δ < 0, surcoût), miroir exact
  > de la sous-indexation pour une revalorisation ; une déflation n'ouvre toujours aucun écart.
  > Mêmes règles pour les prestations (§ Effets FLUX). Effet : seuls les deux programmes publiés
  > qui désindexent bougent, d'un centième de point de dette — Renaissance (pensions 90 %,
  > prestations 80 %) +0,01 pt en 2030 et 2035 ; IM-compétitivité (pensions 80 %, prestations
  > neutralisées par l'ASU) +0,01 pt en 2032-2034, inchangé à l'arrondi en 2030 et 2035 ; les huit
  > autres programmes et le statu quo sont identiques au bit près. Gel total : dette 2035
  > 148,02 → 148,06 % (pensions), 150,20 → 150,21 % (prestations). La part indexée 0,86 n'est
  > pas modifiée dans cette version : l'ancrage OFCE ci-dessous (gel 2026 de 1,1 % = 3,7 Md EUR)
  > passe de 3,70 à 3,66 Md EUR, dans sa tolérance de 0,05 Md EUR ; sa re-dérivation sous le ratio
  > exact (0,87) relève d'une release de paramètres, arbitrage du mainteneur.
- Calendrier N−1 (réfutation des handlers, 07/10/2026) : chaque revalorisation porte l'inflation de
  l'ANNÉE PRÉCÉDENTE, comme la loi (pensions au 1er janvier, prestations au 1er avril, sur l'inflation
  passée) et comme la baseline du moteur (part indexée de `pi_idx`, ci-dessus). Les revalorisations
  à partir de 2027 portent l'inflation que le moteur calcule pour l'année d'avant. Celle du 1er janvier
  2026 a déjà eu lieu : c'est un fait, `REVALORISATION_PENSIONS_2026` = **0,9 %** (coefficient 1,009,
  art. L161-25 CSS, gel du PLFSS rejeté — service-public.fr, « Pensions de retraite de base : quelle
  revalorisation au 1er janvier 2026 ? » ; circulaire Cnav 2025/29). Un gel total 2026 évite donc
  0,9 % / 1,009 de la masse indexée revalorisée : **3,0 Md EUR**. La part indexée 0,86 ne change pas : elle reste déduite du
  point OFCE avec l'hypothèse de l'OFCE (1,1 % → 3,7 Md EUR, soit 336 Md EUR), seul le taux évité
  diffère. Le moteur revalorisait à l'inflation de l'année COURANTE (1,33 % en 2026) : le même gel
  valait 4,48 Md EUR. Les prestations, revalorisées au 1er avril, gardent pour 2026 l'inflation 2025
  réalisée (`INFLATION_BASE`, 1,1 %) : leur taux effectif n'a pas été vérifié. Effet de la correction
  sur la dette 2035 : Renaissance +0,07 pt (inflation N−1) puis +0,02 (taux 2026 effectif),
  IM-compétitivité +0,04 puis +0,02.
- Part indexée 0,86 : la masse que porte une désindexation décidée par la loi (régimes de base
  et pensions publiques ; l'Agirc-Arrco est revalorisé par les partenaires sociaux), calée sur
  l'OFCE — P. Madec, « Impôts et prestations : quels effets attendre d'une « année blanche » ? »,
  blog de l'OFCE, 30/06/2025 : gel au 1er janvier 2026 d'une revalorisation de 1,1 % = **3,7 Md EUR**,
  soit 336 Md EUR de masse indexée, pour 390,7 Md EUR de masse nominale 2026 dans le moteur. Le même
  billet chiffre l'« année blanche » COMPLÈTE à ~6 Md EUR (pensions 3,7 + prestations hors chômage
  0,8 + allocations chômage 0,4 + gel du barème de l'IR 1,2) : le « 5,7-6 Md EUR » parfois cité pour
  les seules pensions est ce total.
- Jusqu'en v0.6.6 : `1,5 Md EUR × (1 − indexation) × années` (plateau 7 ans), sans inflation et sans
  source — sur 380 Md EUR de pensions, une inflation implicite de 0,39 %, quatre fois moins qu'une
  revalorisation réelle. Effet de la correction : renaissance_2027 (indexation 0,9) et
  im_competitivite_2029 (0,8) gagnent 0,46 pt de dette 2035 chacun ; aucun autre scénario publié
  ne désindexe les pensions.
- SYMETRIQUE au premier ordre : la sur-indexation (>100%) est un surcout miroir, exact la première
  année, puis écarté de O((δπ)²) par la composition des revalorisations — verrouille par
  tests/test_retraites_indexation_symetrie.py et tests/test_desindexation_v067.py
- Caveat : le plateau 7 ans s'applique au canal BUDGETAIRE ; l'effet pouvoir
  d'achat de la desindexation reste recurrent (applique chaque annee, sans
  plafond de duree — cf § Effets FLUX)

**Duree de cotisation :**
- Trimestres requis = duree x 4
- Decote pour carrieres incompletes
- Impact differencie selon categories socioprofessionnelles

### Impacts Macroeconomiques

- **Inegalites** (lot 4) : canal d'indexation = coefficient des pensions (−0,0000685 par Md EUR versé, centre de la plage publiée) × écart en euros, en incrément (§ Effet d'un gel sur les inégalités) ; canal d'âge : coefficient à ZÉRO faute de source (aucune des sources consultées ne chiffre l'effet d'un âge de départ sur le Gini du niveau de vie ; sens de la limite : un recul de l'âge accroît probablement les inégalités, effet omis — § Méthode unique du Gini). Règle d'avant le lot 4 : +1,25 annee d'age au-dessus de la reference legale de l'annee = +0,001 Gini (legerement REGRESSIF — mortalite differentielle : esperance de vie ouvriers -6 ans vs cadres, taux d'emploi 55-64 ans 52 % vs 71 %, COR 2024). Correction v0.6.0 : la doc affichait -0,002 « legerement progressif », signe INVERSE du code (audit 08/2026, constat 6). v0.6.1 : l'ecart se mesure a la reference de l'annee, comme le canal budgetaire, pour que le statu quo reste neutre ; le coefficient est inchange — l'effet distributif du canal emploi n'est pas etabli (heterogeneite forte documentee) et ne sera pas ajuste hors d'une passe dediee. L'effet plein est servi l'annee ou la mesure OUVRE son ecart au calendrier legal (et non l'annee ou elle apparait), puis 10 % de residu annuel : cf. § « Effets NIVEAU vs FLUX », 4e pattern.
- **Pouvoir d'achat** (v0.6.8) : les pensions non versées (âge, durée, indexation) sortent du RDB des ménages au montant du budget, canal `prestations` (l'ancien −0,007/an pour un gel total se composait d'une année sur l'autre)
- **Competitivite** : Impact neutre (pas de lien direct entreprises)
- **Croissance et chomage** : depuis la v0.6.1, le levier d'age agit aussi par
  le canal emploi seniors (section ci-dessus) — croissance potentielle a la
  hausse, bosse de chomage transitoire, recettes supplementaires nees du PIB.
  Ces effets sont **strictement symetriques** : un abaissement de l'age retire
  a l'economie exactement ce qu'un report lui apporte

---

## Sante

### Vue d'Ensemble - 3 Leviers (30 Md EUR potentiel)

La fonction sante utilise une approche structuree en 3 leviers UX distincts :

| Levier | Potentiel | Composantes |
|--------|-----------|-------------|
| **Hopital** | 13 Md EUR | Convergence tarifs + GHT + Achats groupes + Ambulatoire |
| **Ambulatoire** | 10 Md EUR | Gatekeeping + CPTS/telemedecine + Pertinence soins |
| **Prevention/Org** | 7 Md EUR | Generiques + Controles IJ + Regulation urgences + ciblage prevention |
| **TOTAL** | **30 Md EUR** | +50% vs Cour des Comptes (20 Md EUR) |

### Levier 1 : Hopital (13 Md EUR)

**Convergence tarifs public/prive (5 Md EUR)**
- Source : IGAS 2023
- Ecarts tarifaires secteur prive lucratif +20-40% sur certains actes
- Alignement progressif sur tarifs publics

**Fermetures/GHT mutualisation (4 Md EUR)**
- Source : Cour des Comptes 2025
- Services dupliques, plateaux techniques sous-utilises
- Restructurations necessaires

**Achats groupes (3 Md EUR)**
- Source : IGAS 2023
- Dispositifs medicaux : 2,5 Md EUR
- Medicaments liste en sus : 0,75 Md EUR
- Centralisation achats nationale/europeenne

**Virage ambulatoire (1 Md EUR)**
- Objectif 80% chirurgie ambulatoire (vs 64% actuel)
- Economies nettes conservatrices

### Levier 2 : Ambulatoire (10 Md EUR)

**Gatekeeping renforce (4 Md EUR)**
- Source : OCDE 2024
- France 3,1% PIB ambulatoire vs UE 2,3%
- Renforcement parcours de soins

**CPTS et telemedecine (3 Md EUR)**
- Source : HCAAM 2024
- 730 CPTS en 2024, objectif 1000+ en 2027
- Coordination territoriale

**Pertinence des soins (3 Md EUR)**
- Source : Cour des Comptes avril 2025
- Reduction variations territoriales : 2,8 Md EUR

### Levier 3 : Prevention & Organisation (7 Md EUR)

**Generiques et biosimilaires (2,5 Md EUR)**
- Taux generiques France : 86,5%
- Biosimilaires : 35% -> 80% = ~1 Md EUR

**Controles IJ (1 Md EUR)**
- Mesure PLFSS 2025
- Renforcement controles arrets maladie abusifs

**Regulation urgences (1,8 Md EUR)**
- Cout urgences : 5,6 Md EUR (2023)
- Reorientation vers medecine de ville

**Prevention — meilleur ciblage (1,7 Md EUR)**
- Depistages, vaccins, maladies chroniques : gain d'EFFICIENCE a depense
  constante, pas rendement d'une depense additionnelle
- Ordre de grandeur ancre sur la Cour des comptes (note Ondam du 14/04/2025) :
  prevention des maladies chroniques 400 M EUR + prevention de la perte
  d'autonomie jusqu'a 1,2 Md EUR, soit ~1,6 Md EUR a horizon 2029, obtenus par
  un MEILLEUR CIBLAGE et non par une depense supplementaire
- Le rendement « 25 % par an apres 2 ans » affiche jusqu'a la v0.6.0 est
  RETIRE : il ne renvoyait a aucune publication (cf. section
  « Investissement prevention » ci-dessous)

### Investissement prevention (refonte v0.6.1)

Curseur `sante.prevention_budget`. A ne pas confondre avec le levier
`effort_prev_org` ci-dessus : celui-la optimise la prevention EXISTANTE,
celui-ci finance un volume ADDITIONNEL. Le moteur ne consomme que l'ecart a la
base ; la base ne fait que positionner le curseur.

**L'assiette (v0.6.1) : 7,5 Md EUR, et non 5,0**

Deux sources independantes, meme nomenclature internationale (System of Health
Accounts, SHA), convergent a 1 % pres :

| Source | Ce qu'elle publie | Conversion |
|---|---|---|
| DREES, *Les depenses de sante en 2023*, Panoramas ed. 2024, fiche 21 tableau 1 | prevention institutionnelle **7 516 M EUR en 2023** ; l'ed. 2025 a revise la serie : 8 657 M EUR en 2023, **8 731 M EUR en 2024** (PLFSS 2026, annexe 5 « Prévention », p. 47, source DREES) | **7,5 Md EUR** (ancien millesime ; passage a ≈ 8,7 : decision ouverte, release de parametres) |
| OCDE, *Health at a Glance 2025*, note pays France (nov. 2025) | « France spends **2,3 %** of total health spending on prevention […] less than the OECD average of **3,4 %** » | 2,3 % x 333 Md EUR (DCSi) = **7,66 Md EUR** |

**La borne haute : 11,2 Md EUR, et elle est DERIVEE, pas choisie.** C'est la
convergence vers la moyenne OCDE : 7,5 + (3,4 % − 2,3 %) x 333 = 11,2 Md EUR.
L'amplitude du curseur (0 a +3,7 Md EUR/an) devient ainsi sourcee, alors que
l'amplitude de la v0.5.1 (0 a +3,0) l'etait par accident. C'est la borne du **retour modelise**, pas
de la depense : au-dela, aucune evaluation ne documente de gain a cette echelle (rendements
decroissants, mesures autofinancees qui coutent peu : taxes et reglementation), si bien qu'une
depense de prevention supplementaire s'encode comme une depense de soins, sans retour.

**Deux pieges de lecture, tous deux corriges ici :**

1. **La bosse 2020-2022 n'est pas une base.** La serie DREES fait 5 665 (2019)
   → 9 272 (2020) → **16 515 (2021)** → 12 175 (2022) → 7 516 (2023) M EUR :
   c'est du Covid (tests, vaccins, masques). L'OCDE note elle-meme le retour
   « to historical levels of 3 % in 2023 ». Retenir un point de la bosse
   ferait croire a un effondrement de la prevention francaise.
2. **Perimetre SHA, pas perimetre large.** La « prevention institutionnelle »
   SHA EXCLUT la prevention en consultation ordinaire, les depistages hors
   depistage organise, une grande partie de la vaccination et la prise en
   charge des facteurs de risque — toutes comptees en CSBM. En perimetre
   large, la Cour des comptes chiffre l'effort francais a environ
   **15 Md EUR/an** (*La politique de prévention en santé*, communication au
   comite d'evaluation et de controle de l'Assemblee nationale, 1er decembre
   2021, p. 44, donnees 2016 ; ce rapport ne publie aucun taux de rendement).
   Le curseur pilote l'agregat SHA (7,5), **pas les 15**.
   Melanger les deux perimetres est l'erreur la plus frequente sur ce sujet.

Les mentions « France 2 % / OCDE 2,8 % » qui figuraient dans le code et les
infobulles jusqu'a la v0.6.0 relevaient d'un millesime OCDE 2020 : elles sont
retirees.

**Le taux de compensation (I20) : le dernier « repas gratuit » du moteur**

Jusqu'a la v0.6.0, le moteur appliquait `min(annees x 25 % ; 200 %)` a partir
de la 2e annee. A 100 %, l'euro depense est integralement gage ; **a 200 %, la
mesure RAPPORTE autant qu'elle coute, chaque annee et pour toujours** —
+10 Md EUR/an de prevention reduisaient la dette 2035 d'environ 42 Md EUR.
La litterature dit l'inverse :

| Source | Ce qu'elle etablit | Portee |
|---|---|---|
| Cohen, Neumann & Weinstein, *NEJM* 358(7):661-663, 2008 (DOI 10.1056/NEJMp0708558) | **19 %** des interventions preventives sont cost-saving, contre 18 % des traitements curatifs (599 etudes) | depenses de sante — l'esperance du retour est tres inferieure a 1 |
| van Baal et al., *PLoS Medicine* 5(2):e29, 2008 | « lifetime health expenditure was highest among healthy-living people » | vie entiere — contre-effet des annees de vie gagnees |
| Vos et al., *ACE-Prevention Final Report*, 2010 | 23 interventions préventives **dominantes** sur 123 (paquet de 20) : 4,6 Md AU$ → 11 Md AU$, ratio **2,4** | **borne haute absolue** (selection optimale, vie entiere) |
| OCDE, *The Heavy Burden of Obesity*, 2019, ch. 6 | meilleure intervention : 13 Md USD PPA cumules 2020-2050 sur 36 pays ≈ **0,012 Md EUR/pays/an** | trois ordres de grandeur sous la v0.5.1 |

Le « six-fold economic return » du resume executif du meme rapport OCDE 2019
et le « 7 US$ pour 1 » de l'OMS (*Saving lives, spending less*, 2021, champ :
76 pays a revenu faible ou intermediaire) sont des retours **PIB/emploi**, pas
budgetaires : ils n'ont pas leur place dans un solde public francais.

Le delai s'appuie sur Fourcade N. & Cash R., « Comment évaluer l'efficacité économique de la
prévention ? », *Regards* n° 61 (EN3S), mai 2023, p. 41 : « les bénéfices économiques de la
prévention sont souvent postérieurs aux dépenses engagées ».

Regle retenue en v0.6.1 : **4 annees pleines sans aucun retour, puis +10
points par an, plafonnes a 50 %**, applique **symetriquement** (une coupe de
prevention rend moins que son montant, exactement comme un investissement
coute moins que le sien). Trajectoire pour +3 Md EUR/an :

| Annee | 2027 | 2029 | 2031 | 2033 | 2035 |
|---|---|---|---|---|---|
| Moteur v0.5.1 | +2,25 | 0,00 | −1,50 | −3,00 | **−3,00** |
| Moteur v0.6.1 | +3,00 | +3,00 | +2,40 | +1,80 | **+1,50** |

Lecture : la prevention **coute toujours** de l'argent public, mais coute
**de moins en moins**. C'est le maximum que la litterature autorise.

**Limite connue, dite ici plutot que decouverte par un contradicteur** (LEVÉE en
v0.6.7 : l'impulsion est désormais la variation de chaque levier, sans aucun seuil —
le paragraphe décrit l'état v0.6.1-v0.6.6) : le
moteur ne cree une impulsion budgetaire que si l'effort depasse 0,1 % du PIB
(`engine/growth.py`) — une regle A SEUIL. Un budget de prevention qui fait
franchir ce seuil declenche d'un coup le multiplicateur, donc un peu de PIB,
donc un ratio de dette legerement plus bas. Consequence mesuree : pousser le
curseur au plafond fait MONTER la dette 2035 dans 7 des 9 scenarios publies de l'epoque (v0.6.1)
(jusqu'a +2,57 pt) et la fait baisser de 0,02 et 0,23 pt dans les deux autres.
Ces deux baisses sont un **artefact de seuil du bloc macro**, pas un rendement
de la prevention ; elles sont bornees par un test-propriete. Meme famille que
la non-linearite du plancher monetaire accommodant documentee en v0.6.1
(lot I6). Traitement du seuil : item v0.6.2.

**Sens de la correction** : elle joue dans un seul sens, **contre les
programmes qui investissent dans la prevention**. Ecrit ici parce que c'est la
regle du projet — un simulateur citoyen ne se protege pas en evitant les
corrections sensibles, il se protege en disant dans quel sens joue chacune.

**Ancrage francais des ordres de grandeur** — Cour des comptes, note sur
l'Ondam du 14/04/2025 : 1 an d'esperance de vie sans incapacite ≈ 1,5 Md EUR
economises ; prevention des maladies chroniques 400 M EUR ; prevention de la
perte d'autonomie jusqu'a 1,2 Md EUR, soit environ 1,6 Md EUR a horizon 2029 —
et par un meilleur ciblage, pas par une depense additionnelle.

### Phasing Differencie (2026-2030)

| Annee | Admin | Structurel | Total Max |
|-------|-------|------------|-----------|
| 2026 | 50% | 20% | -7,2 Md EUR |
| 2027 | 80% | 40% | -15,8 Md EUR |
| 2028 | 100% | 60% | -21,4 Md EUR |
| 2029 | 100% | 80% | -25,7 Md EUR |
| 2030+ | 100% | 100% | -30,0 Md EUR |

**Justification** : Mesures administratives (generiques, controles) deployables rapidement, mesures structurelles (fermetures, convergence) necessitent plusieurs annees.

### Impacts Macroeconomiques

**NEUTRALITE TOTALE** : Mesures d'efficience pure
- Gini : 0 (pas de changement redistributif)
- Pouvoir d'achat : 0 (pas de changement reste a charge ; canaux ménages nuls)
- Competitivite : 0 (optimisation interne)

---

## Fonction Publique

### Reforme Structurelle - 2 Axes

**Digitalisation et polyvalence**
- Potentiel max : 10 Md EUR/an a maturite
- Courbe en S : gains progressifs
- Investissement initial necessaire

**Fusion agences/doublons**
- Potentiel : 5-15 Md EUR selon perimetre
- Delai moyen : 3-5 ans
- Resistances organisationnelles

### Parametres d'Ajustement

| Parametre | Impact | Cout/Economie |
|-----------|--------|---------------|
| Effectifs | Cible atteinte en 2032 (rampe 2027-2032) | 60 k EUR/agent/an en euros 2025, indexé |
| Point d'indice | Hausse salaires | 3,3 Md EUR par point de % (330 Md EUR en euros 2025), indexé |
| Fusion agences | Economies structurelles | Variable |

### Montee en Puissance

Efficacité de la cohorte de départs de l'année (non-remplacement réellement réalisé) :

- 2027 : 30% efficacite
- 2028 : 60% efficacite
- 2029 : 85% efficacite
- 2030+ : 100% efficacite (plein effet)

**Base de calcul (v0.6.7)** : le stock de postes non remplacés est la **somme de cohortes
annuelles** de départs, `157 000 × taux × efficacité(année de la cohorte)`, à partir de
2027 (2026 = préparation, coûts seuls), huit cohortes au plus (2027-2034). Le taux de
non-remplacement vaut 5 % par point d'intensité jusqu'à 10 (50 %), puis 1,7 point de plus
par point (67 % à l'intensité 20), borné à [0 ; 1] : une cohorte ne dépasse jamais les
départs de son année. Chaque poste vaut le coût complet chargé `COUT_MOYEN_AGENT_FP_EUR`
(60 k EUR en euros 2025), exprimé en euros de l'année par l'indice de prix des dépenses
du moteur depuis v0.6.7 — celui qui fait croître la masse salariale du statu quo (~70 k
EUR en 2035). Figé jusqu'en v0.6.6, il sous-estimait les économies d'une réduction comme le
coût d'une création, d'environ 15 % en fin d'horizon. Le curseur « effectifs » applique le
même coût, la même année : un poste vaut autant pour les deux leviers. Toutes les masses de
la fonction publique suivent ce même indice : la masse salariale du point d'indice (330 Md
EUR), la part FP d'une hausse du SMIC (50 Md EUR), les coûts de la réforme (0,15 Md EUR par
point d'intensité, 2026-2029) et sa pénalité de dégradation du service (0,3 Md EUR), tous
calés en euros 2025. Indexer les économies d'une réduction d'effectifs sans indexer le coût
d'une hausse de rémunération aurait laissé une asymétrie (effet sur la dette 2035 : LFI
+0,73 pt, PS +0,47, Écologistes +0,35). Ordres de grandeur
calculés (au coût 2025) : intensité 10 →
215 875 postes en 2030 (13,0 Md EUR/an), 529 875 au plateau (31,8 Md EUR/an) ; intensité
20 → 289 272 postes en 2030 (17,4 Md EUR/an), 710 032 au plateau (42,6 Md EUR/an). Les
« potentiels » cités plus haut pour les deux axes sont des ordres de grandeur de la
littérature, pas les montants du moteur. Jusqu'à v0.6.6, le stock valait
`départs × taux × efficacité(année courante) × nombre d'années` : il réévaluait les
cohortes passées, comptait une cohorte 2026 inexistante et pouvait croître de plus que
les départs d'une année (intensité 20 : 525 950 postes en 2030 ; audit externe Codex,
10/2026). Le curseur « effectifs » puise dans le **même vivier** (ci-dessous). Propriétés
verrouillées par `tests/test_audit_codex_v067.py` et `tests/test_fp_v060.py`.

### Curseur « effectifs » : rampe 2027-2032 et vivier partagé (v0.6.7)

**Règle** (arbitrage du 07/10/2026, la même pour tous les programmes et dans les deux
sens). La valeur du curseur est une cible de **stock** de postes, atteinte par une rampe
linéaire : rien en 2026 (budget voté, le mandat n'a pas commencé), un sixième de la cible
par an de 2027 à 2032, la cible pleine en 2032 et au-delà. 2032 est l'année que donnent
les sources du RN (« trajectoire 2027-2032 ») et de LR (« sur le quinquennat ») ; aucune
source de programme n'annonce une cible plus rapide. Exemple : −201 000 postes donnent
−33 500 en 2027 et −201 000 en 2032. Une création de postes suit la même rampe
(+60 000 donnent +10 000 en 2027) ; elle n'a pas d'effet direct sur le pouvoir d'achat
(v0.6.8 : par la croissance seulement).

**Plafond partagé avec la réforme de l'État.** Une réduction opère par non-remplacement
des départs (157 000 par an), le vivier de la réforme. Réforme + curseur ne suppriment
jamais plus de **67 %** des départs cumulés depuis 2027 (`FP_TAUX_NON_REMPLACEMENT_MAX`),
le taux maximal de la réforme elle-même (intensité 20) : le curseur ne peut pas faire ce
que la réforme ne peut pas. C'est une valeur de construction du moteur, pas une
estimation sourcée (repère : la RGPP 2007-2012 visait un départ sur deux). Sur les
programmes publiés, la rampe seule demande au plus 50 000 postes par an (LR, 32 % des
départs) ; le plafond ne mord que si une réforme de l'État intense s'y ajoute.

**Domaine du curseur (v0.7.2 ; borne haute en v0.8.0).** Le moteur accepte une cible de −500 000 à
+140 000 postes (borne haute +60 000 jusqu'à la release E, élargie pour une valeur à encoder ; une
création ne puise pas dans le vivier, aucun rabot)
(`PARAM_DOMAINS`, `budget_simulator/constants.py`) ; la borne basse était −400 000 depuis
v0.6.11. Décision du mainteneur du 08/11/2026 : couvrir le −480 000 d'un programme annoncé,
avec une marge. En mode cadre, un mandat 2028-2032 compte cinq cohortes de départs : le
vivier peut retirer au plus 67 % × 157 000 × 5 = 525 950 postes, et la borne reste dessous.
Un banc du 08/11/2026 l'a vérifié : à −480 000 et −500 000, l'effet sur le déficit et la
dette vaut 1,20 et 1,25 fois celui de −400 000, et le stock retiré égale la cible chaque
année. Ce « sans rabot » vaut pour un début en 2028 sans réforme de l'État ; un
test-propriété (`tests/test_parametres_v072.py`) interdit une borne qui le briserait. Ailleurs,
le vivier peut raboter la cible. Un programme qui commence en 2029 ou après dispose de moins
de cohortes pour la même cible en 2032 : à −500 000, il retire 420 760 postes en 2032 pour
un début en 2029, puis rattrape la cible en 2033. Le rattrapage glisse d'un an par année de
début, et n'a pas lieu dans l'horizon 2035 pour un début en 2032. La réforme de l'État puise
dans le même vivier : combinée au curseur, elle peut le saturer, comme avant (réforme 50/50 et
−500 000 en 2028 : 311 645 postes retirés en 2035). **Tout rabot du vivier est signalé** dans
`report.leviers_ecretes`, avec le motif `vivier`, le réalisé et l'année de la dernière année
rabotée, et par un avis dans `report.warnings` ; le résultat reste valide, car c'est une
limite du modèle et non une entrée invalide. Une valeur hors domaine est ramenée à la borne et
signalée de même, motif `domaine` (section « Paramètres d'entrée : noms et valeurs »).

**Ce que la règle corrige.** Jusqu'en v0.6.6, la cible était posée dès 2026 dans la seule
limite de 100 % des départs cumulés depuis 2026 : RN et LR supprimaient 157 000 postes dès
2026 (aucun départ remplacé dans toute la fonction publique) et atteignaient leur cible
dès 2027 ; les créations de postes étaient instantanées. Effet de la correction sur la
dette 2035 (réfutation des handlers, 07/10/2026) : LR +1,72 pt, RN +1,24, Renaissance
+0,67, IM-compétitivité +0,66 ; LFI −0,37, PS −0,24, Écologistes −0,13 (coût des
créations étalé).

**Conséquence assumée sur le scénario de référence.** `plf_2026` encode −3 119 postes
pour 2026, et Horizons pose ce levier à la même valeur (droit en vigueur). La règle
commune les fait monter de 2027 à 2032 au lieu de les appliquer en 2026 : 0,19 Md EUR
d'économie de moins en 2026, rien au-delà de 2032 (déficit 2026 de référence −5,16 % au
lieu de −5,15 %). Propriétés verrouillées par `tests/test_fp_rampe_v067.py`.

### SMIC et Fonction Publique (Correction v3.0)

**Double-comptage corrige** : Quand le SMIC augmente, l'impact sur la fonction publique est calcule en delta :
```
delta_fp = max(0, hausse_smic - hausse_point_indice)
```
Cela evite de compter deux fois la meme hausse si le point d'indice est deja revalorise au-dessus du SMIC.

### Impacts Macroeconomiques

- **Gini** : aucun effet (le handler pose 0 : salaires de la fonction publique déjà
  compressés). Les règles « −10k effectifs = +0,001 » et « +1 % de point d'indice = −0,0005 »
  publiées ici jusqu'au 07/10/2026 n'étaient pas celles du moteur.
- **Pouvoir d'achat** (v0.6.8, arbitrage du mainteneur) : le point d'indice est un revenu
  des agents en place, canal `rémunérations publiques`, compté à sa part nette (0,535 € par €
  de coût) chaque année ; les créations et suppressions de postes n'ont pas d'effet direct
  (elles passent par la croissance)
- **Croissance** (lot 5b, arbitrage du mainteneur du 16/11/2026) : le point d'indice, ce même
  montant, prend le traitement des transferts (coefficient et profil), dans les deux sens ; les
  créations et suppressions de postes restent de la dépense courante. Depuis le lot SMIC, la paie
  publique d'une hausse du SMIC (poste du Trésor, § SMIC) prend le même traitement
  2027-2032 ; suppressions : aucun effet (attrition naturelle, pas de licenciement).

---

## Chomage et Protection Sociale

### Allocations Chomage

**Parametres (post-reforme avril 2025) :**
- Taux de remplacement : ≈ 40,7 % a 80 % (base 60 %) ; en montant, 24,85 a 48,8 Md EUR. Release E
  (revue adverse) : la borne basse du montant est portee de 27,45 a 24,85 Md EUR (valeur a encoder
  d'un programme) et celle du taux en est DERIVEE (24,85 / 36,6 × 60 %), pour que les deux ecritures
  exclusives couvrent la meme plage (ancienne borne du taux : 45 %)
- Duree allocations : 12 a 36 mois (base 18 mois — reforme avril 2025 : 24 → 18 mois pour les <55 ans)
- Base du canal taux : 36,6 Md EUR (v0.6.4 — la somme des lignes du rapport
  financier Unedic 2025 proportionnelles a l'allocation : ARE 32,124 +
  ARE Formation 1,718 + ASR/ASP 1,745 + autres 0,020 + ARCE 0,956 ; exclus
  avec leur raison d'assiette : points de retraite 2,43 — assiette = SJR —,
  contribution France Travail 4,98 — 11 % des recettes N−2 —, aides
  forfaitaires, activite partielle ; derivation complete dans constants.py)

**Formule economique (deux canaux SEPARES depuis v0.6.3) :**
- Canal TAUX : delta = 36,6 × (taux/0,60 − 1) — proportionnel, tous allocataires
- Canal DUREE : delta = (duree − 18) × 0,75 × (taux/0,60) — cout MARGINAL
  (M32), seule la minorite qui epuise ses droits est concernee
- Source code : `_apply_chomage_alloc` (`budget_simulator/handlers/depenses.py`),
  constantes `CHOMAGE_MONTANT_REF_MD=36.6`, `CHOMAGE_DUREE_REF_MOIS=18`,
  `COUT_CHOMAGE_MARGINAL_MOIS_MD=0.75`

**Impacts distributifs (v0.6.4, sur les euros des canaux ci-dessus) :**
- Gini canal taux : GINI_ALLOC_PAR_MD_EUR = 0,000238 par Md EUR coupe, soit (G − C) / Y au
  classement final, C des euros d'allocations chômage (INSEE, *Revenus et patrimoine des
  ménages* 2024, fiche 1.4) — lot 4, méthode unique (§ Indicateurs Macroeconomiques) ; l'ancre
  DREES (C_ARE = −0,138, E&R n° 1368, en personnes) donnait 0,000319 et reste l'ancre de validité
  du canal durée ; jusqu'ici 0,0008, attribué à « OFCE 2023 » sans passage retrouvé
- Gini canal duree : × GINI_DUREE_SURPOIDS = 1,6 — par euro, une coupe de
  duree frappe plus bas (cohorte fin de droits : a +3 mois, 71 % ne touchent
  ni RSA ni ASS — Dares Focus n° 53 × DREES E&R n° 1368 ; cf. M35)
- Degressivite : son facteur (±15 % d'allocations) s'applique aux DEUX canaux
  ET au Gini (v0.6.4, fin du free lunch — meme famille que le fix PA v0.6.3)
- PA : canal € total (taux ET duree, v0.6.3) ; v0.6.8 : les allocations elles-mêmes, canal `prestations`

> **Note historique** : avant la reforme d'avril 2025 la base etait 45 Md EUR
> × 24 mois ; de v0.6.3 a v0.6.4 le canal taux portait 40 Md EUR — un agregat
> (~charges techniques hors France Travail) qui incluait des lignes qu'un
> changement de taux ne met pas a l'echelle. Le simulateur prend la duree des
> <55 ans (18 mois) comme reference pour la conversion taux ↔ montant.

### Allocation Sociale Unique (ASU)

> **Refonte v0.6.1 (items I22 a I26).** Jusqu'a la v0.5.1 le moteur faisait de
> l'ASU une machine a economies (-11,5 Md EUR/an a plein regime), avec un bonus
> emploi et une amelioration du Gini servie a cout nul. La **seule evaluation
> administrative publiee** de la reforme chiffre au contraire un effet
> budgetaire perenne compris **entre 0 et +2,0 Md EUR par an de COUT**. Quatre
> des sources citees par le code ont ete **retirees, pas reecrites** : deux
> etaient introuvables, une nommait un organisme inexistant, une etait une note
> de plaidoyer refutee au fond par la Cour des comptes.

**Perimetre** : **39 Md EUR** — RSA + prime d'activite + APL, via un « revenu
social de reference ». Les **prestations familiales n'en font pas partie** : la
mission parlementaire conclut a « une harmonisation des bases de ressources et
une evolution des baremes » plutot qu'a « une creation d'allocation unique », et
F. Lenglart ecrit « unifier […] et non pas les fusionner ». Le moteur les
fusionnait, et les chiffrait a **52 Md EUR** la ou les prestations familiales
valent **32,3 Md EUR** : il se trompait a la fois de champ et de montant.
Le perimetre de 39 Md EUR est un **libelle** : il n'entre dans aucun calcul du
moteur, et la somme des trois lignes citees vaut 37,4 Md EUR — un ecart de
1,6 Md EUR que le dossier de sourcing ne reconcilie pas, signale ici plutot que
comble.

**Plafond** : curseur 50 %-70 % du SMIC net (defaut moteur **65 %**). Il ne
pilote plus une economie de baremes, mais l'**effort budgetaire perenne** de la
reforme, entre les deux seules variantes chiffrees par la DREES et l'Igas :
« a cout constant » (0) et « +2 Md EUR perennes ». Interpolation lineaire entre
ces deux bornes : **convention declaree**, aucune source ne publie la
correspondance entre un niveau de plafond et un montant.

**Ce que la reforme coute et rapporte, dans le moteur :**

| Composante | Valeur | Statut |
|---|---|---|
| Effort perenne (curseur) | 0 a **+2,0 Md EUR par an** | scenarios DREES/Igas juin 2024 |
| Economie de gestion | **-0,3 Md EUR par an** | DERIVATION (voir ci-dessous) |
| Cout de transition | +1,1 Md EUR par an sur 4 ans | fourchette officielle 2 a 13,4 Md EUR cumules, **plancher retenu**, + 2,4 Md EUR de hausse du recours |
| Effet emploi | **0** | aucun effet observable (Cour des comptes / IPP) |
| Competitivite | **0** | aucune source |
| Pouvoir d'achat | effort + recours, en euros de l'année (canal `prestations`, v0.6.8) | nul a cout constant |
| Gini | coefficient des prestations ciblées de l'INSEE × transfert net (lot 4) | nul a cout constant |

**Pourquoi l'economie de gestion ne peut pas depasser un ordre de grandeur.**
La gestion de **toute** la branche famille vaut environ **3 Md EUR** par an
(Cour des comptes, communication au Senat de janvier 2026, chapitre « Le cout de
la gestion par la CNAF ») : la prime d'activite y pese 360 M EUR en cout complet,
le RSA environ 280 M EUR. Un coefficient de 6 Md EUR par an en representait donc
le **double** — supprimer integralement la CNAF n'economiserait que 3 Md EUR. Sur
le perimetre reel de l'ASU la masse mobilisable est de 0,8 a 1,0 Md EUR/an ; le
moteur retient **0,3 Md EUR par an**. Ce chiffre est une **derivation assumee**,
jamais une estimation officielle : la mission parlementaire declare
explicitement que ses moyens « n'ont pas permis d'en estimer precisement le
montant ». Le sens de court terme est d'ailleurs **inverse** — la convention
d'objectifs et de gestion 2023-2027 augmente les moyens de gestion de 34 %,
notamment pour absorber le pic d'activite lie a la « solidarite a la source » :
la reforme coute de la gestion avant d'en economiser.

**Pourquoi il n'y a plus d'effet emploi.** Le chapitre 3 du rapport de la Cour
des comptes sur la prime d'activite a pour titre « Des effets significatifs sur
les revenus des menages modestes **mais pas d'effets observables sur l'emploi** ».
L'etude sous-jacente, conduite par l'Institut des politiques publiques a la
demande de la Cour (octobre 2023), ne trouve aucun effet « dans les differentes
sous-populations analysees », et pres de 80 % des allocataires interroges
declarent ne pas tenir compte de la prime d'activite dans leur comportement
d'emploi. Un dispositif de 10,6 Md EUR et 4,81 millions de beneficiaires ne
produit aucun effet emploi mesurable : il est exclu qu'une refonte de baremes en
produise un.

**Pourquoi reduire le non-recours COUTE.** Le cout de transition publie
(2 a 13,4 Md EUR cumules sur quatre ans) est explicitement donne « hors hausse du
taux de recours (2,4 milliards d'euros d'apres la DGALN) » pour le seul volet
logement. Le moteur traitait la baisse du non-recours comme un gain
redistributif gratuit ; elle est desormais **facturee**.

**Le Gini de l'ASU (lot 4, arbitrage du mainteneur).** Aucune source ne publie
l'effet de l'ASU sur l'indice de Gini : les scenarios officiels donnent un
**taux de pauvrete**. Le moteur ne fabrique pas la conversion. Depuis le lot 4,
il applique au transfert net le coefficient des prestations ciblées de l'INSEE
au classement final (prestations familiales, aides au logement, minima sociaux,
prime d'activité : la famille que l'ASU fusionne, § Indicateurs
Macroeconomiques, méthode unique). Jusqu'au lot 4, il retenait une borne
theorique — un transfert net integralement recu par le tout premier centile —,
qui majorait l'effet. Limite declaree, de sens non etabli : la concentration
propre du transfert net de l'ASU n'est publiee nulle part. Et l'effet reste
**conditionne a l'effort** : dans la variante a cout constant, la reforme compte **4,0 millions
de perdants pour 3,9 millions de gagnants** — c'est un pur transfert entre
menages, dont l'effet agrege est nul par construction.

**Effets de NIVEAU, pas de flux.** Le Gini de l'ASU est
emis sous forme d'**increment de montee en charge** (le pouvoir d'achat, depuis la
v0.6.8, lit le niveau du transfert de l'année, en euros) : leur somme sur les quatre
annees vaut exactement le niveau atteint, et ils valent zero une fois le regime
permanent installe. Une reforme de baremes deplace le niveau des transferts une
fois ; elle ne reduit pas les inegalites un peu plus chaque annee pour toujours,
ce que la v0.5.1 faisait en emettant le meme delta chaque annee dans un
agregateur cumulatif.

**Sources primaires** (URL completes dans `budget_simulator/constants.py`,
section « CALIBRATION ALLOCATION SOCIALE UNIQUE ») :
- Assemblee nationale, commission des affaires sociales, mission « flash » sur
  l'opportunite et les modalites de la creation d'une allocation sociale unique,
  rapporteures N. Colin-Oesterle et S. Runel, **juillet 2025** (chiffrages DREES
  et Igas, modele Ines, juin 2024) ;
- Cour des comptes, *La prime d'activite*, communication au Senat (art. 58-2°
  LOLF), **janvier 2026**, annexe au rapport d'information Senat n° 728
  (2025-2026), p. 101-102 ;
- Cour des comptes, *Certification des comptes du regime general de securite
  sociale — exercice 2024*, **mai 2025** ;
- Institut des politiques publiques, *La reforme de 2019 de la prime
  d'activite*, **octobre 2023**, publiee par France Strategie.

**Lot 4 — limite levée** : les coefficients Gini des leviers sociaux, jusqu'ici
d'un ordre de grandeur supérieur **par euro transféré**, sont tirés de la même
identité que l'ancienne borne de l'ASU (méthode unique, § Indicateurs
Macroeconomiques) ; l'ASU prend celui des prestations ciblées.

---

## Fiscalite

### Impot sur les Societes (IS)

**Parametres :**
- Taux actuel : 25%
- Range : 15% a 35%
- Assiette imposable : 9,1 % du PIB (benefice fiscal net, DGFiP 2024 : 0,091 × 2 750 × 25 % ≈ 62 Md EUR), reduite de 20 % en recession

**Elasticite comportementale de l'assiette :**
- Taux > 25% : elasticite -1,0 (optimisation fiscale)
- Taux <= 25% : elasticite -0,6

**Formule (v0.6.7)** : `assiette(t) = 0,091 × PIB × (1 + e × (t − 0,25))` et
`Δrecettes = t × assiette(t) − 0,25 × assiette(0,25)`, soit l'effet statique
(Δtaux × assiette actuelle) plus l'effet de comportement (nouveau taux × variation
d'assiette). La v0.6.6 calculait `(t − 0,25) × assiette(t)` : elle omettait la recette
perdue a 25 % sur l'assiette qui part et exagerait l'effet dans les deux sens (35 % a
PIB 3 000 : 24,6 au lieu de 17,7 Md EUR ; audit externe Codex, 10/2026). Ancrage :
DG Tresor 2017, passer de 33 % a 25 % coute 10 a 12 Md EUR/an en regime stationnaire ;
la formule donne 11,2 au PIB 2017 (l'ancienne 15,4). Verrouille par
`tests/test_audit_codex_v067.py` (decomposition, effet reel inferieur a l'effet
statique dans les deux sens, monotonie, ancre DG Tresor).

**Impacts :**
- Gini : aucun (canal retire en v0.6.1, non source et asymetrique)
- Competitivite : ONE-TIME, `−Δrecettes × 0,015` l'annee du changement de taux (delocalisation / attractivite)

### TVA

**Parametres :**
- Taux actuel : 20%
- Range : 5,5% a 25%
- Assiette : 53% PIB (consommation)

**Effets :**
- Elasticite base : -0,2 si taux > 20%
- Penalite evasion si taux > 22%

**Impacts :**
- Gini : 0 (lot 4, périmètre INSEE : le niveau de vie est mesuré avant les prix ; jusqu'ici +0,005 pour +2 points, « OFCE 2024 » sans passage retrouvé)
- PA (v0.6.8 : canal ménages en euros, § Indice de pouvoir d'achat) : par les prix, τ+ = 1,0 (hausse), τ− = 0,5 (baisse) ; la base du levier étant la consommation des ménages, toute la recette pèse sur elle (part 1,0)

### Impot sur le Revenu (IR)

**Parametres :**
- Tranche superieure : 45% actuel (range 40%-60%)
- Foyers concernes : 400k (revenus > 160k EUR)
- Revenu moyen tranche : 220k EUR

**Impacts :**
- Gini (lot 4, méthode unique) : −0,000444 par Md EUR de recette de la tranche supérieure (coefficient
  de l'IFI de l'INSEE ; la concentration de la tranche supérieure est au moins celle de l'IFI) ; décote :
  +0,000122 par Md EUR (Conseil des prélèvements obligatoires, rapport particulier n° 2, tableau n° 34 :
  gain de la décote par dixième, concentration 0,134). Jusqu'ici −0,008 pour 45%->50% (« OFCE 2023 »,
  passage non retrouvé), jusqu'à −0,0075 par Md EUR, quinze fois la borne arithmétique
- PA (v0.6.8 : canal ménages en euros, § Indice de pouvoir d'achat) : prélèvement direct, −1 € de RDB par €

### CSG/CRDS

**Base large** : tous revenus (travail, capital, remplacement)
- Taux actuel : 9,7%
- Range : 8% a 12%

**Option progressive** : Bareme par tranches au lieu de taux flat
- Recettes neutres ou positives selon calibrage

**Gini (lot 4, méthode unique)** : −0,0000863 par Md EUR de recette (constante
`GINI_CSG_PAR_MD`, classement final, INSEE, *Revenus et patrimoine des ménages* 2024) — une
HAUSSE de CSG réduit l'indice. L'INSEE classe les contributions sociales parmi les
prélèvements « faiblement progressifs » (*France, portrait social* 2025, fiche « Redistribution
monétaire », figure 2). Option progressive : 0 faute de source (jusqu'ici −0,015, « OFCE 2023 »,
sans passage retrouvé).
Jusqu'ici +0,002 par point (« CSG légèrement régressive », OFCE 2024, passage
non retrouvé) : le signe était inversé.

---

## Competitivite des Entreprises

### Indice de Competitivite (Base 100 en 2025)

**Composantes et ponderations :**

1. **Cout du travail (30%)**
   - Cotisations patronales
   - Charges sociales
   - Calibration : -1% PIB cotisations = +0,30 pts competitivite

2. **Fiscalite (25%)**
   - IS, impots production
   - Calibration : -10 Md EUR impots production = +1,0 pt competitivite

3. **Innovation (20%)**
   - CIR, budget recherche
   - Calibration : +1 Md EUR R&D = +0,05 pt competitivite

4. **Transition ecologique (15%)**
   - Investissements verts
   - Taxe carbone
   - Calibration : +1 Md EUR transition = +0,06 pt competitivite

5. **Efficience administrative (10%)**
   - Simplification
   - Digitalisation

### Impots de Production

**Situation France (post-suppression progressive CVAE) :**
- Actuel : 97 Md EUR (~3,5% PIB) — INSEE 2024, CAE 2025
- Reste tres au-dessus de la mediane UE
- Allemagne : ~40 Md EUR (point de comparaison handicap competitivite)
- Source code : `_apply_impots_production` (`budget_simulator/handlers/competitivite.py`), `montant_base = 97`

> **Note historique** : Le total culminait a ~112 Md EUR (~4,5% PIB) avant les reformes de la loi de finances 2023-2024 (suppression progressive de la CVAE). Le defaut moteur reflete l'apres-reforme (97 Md EUR).

**Impacts :**
- PIB : -10 Md EUR = +0,12% PIB
- Emploi : capte via canal chomage (coef -0,00007 pt/Md EUR, ~+0,06%/Md EUR) — canal unique, pas de double comptage
- Competitivite : -10 Md EUR = +0,018 pt

### Cotisations Patronales

**Taux France** : 27% (range 15%-35%)

**Impacts :**
- Emploi : -1 point = +0,08% emploi (27M emplois prives)
- Competitivite : -1 point = +0,015 pt
- Gini : 0 (cotisations patronales : aucun effet direct sur le revenu disponible des ménages, le handler n'émet rien ; la ligne « +1 point = +0,003 » de cette section était périmée, corrigée au lot 4)

---

## Transition Ecologique

### Taxe Carbone

**Parametres :**
- Prix actuel : 44,6 EUR/tCO2
- Range : 0 a 200 EUR/tCO2
- Elasticite emissions : -0,3 par 10 EUR supplementaire

**Impacts par palier :**
- Prix < 100 EUR/t : impact neutre
- 100-200 EUR/t : -0,1 pt competitivite par 10 EUR
- > 200 EUR/t : -0,2 pt par 10 EUR (penalite forte)

**Impact Gini (lot 4, périmètre INSEE)** : **0 de Gini pour +50 EUR/tCO2**.
Le site publie le Gini du niveau de vie de l'INSEE, mesuré avant les prix : une
taxe sur la consommation n'y entre pas (arbitrage du mainteneur : concept INSEE
strict). La dérivation ci-dessous reste documentée comme VARIANTE d'un autre
concept, le niveau de vie net des taxes (celui de l'IPP).

**Variante, concept net des taxes (v0.6.1, item I28)** : +0,0010 de Gini pour
+50 EUR/tCO2 (fourchette 0,0009-0,0011), soit exactement la MOITIE du
coefficient de la v0.6.0. Sources : Douenne T. (2020), « The Vertical and
Horizontal Distributive Effects of Energy Taxes: A Case Study of a French
Policy », *The Energy Journal* 41(3), p. 231-253 ; Institut des politiques
publiques, « The redistributive effects of carbon taxation in France »,
*Note IPP* n° 34, juillet 2018. Ces deux evaluations portent sur le passage
de 22 a 44,6 EUR/tCO2 (4,1 Md EUR/an de recettes, hors electricite) : taux
d'effort D1 = 0,55 % du revenu disponible contre D10 = 0,20-0,21 %. Le
coefficient de la v0.6.0 (+0,002) s'appuyait sur une note attribuee a l'OFCE
que la collecte de sourcing n'a pas pu retrouver ; la citation a ete retiree,
pas reecrite.

> **CONDITION DE VALIDITE — le signe peut s'inverser.** Ce coefficient suppose
> l'ABSENCE DE RECYCLAGE des recettes, ce qui est bien le cas dans le moteur :
> la taxe carbone y abonde le budget general. Douenne montre qu'avec une
> **compensation forfaitaire**, les deciles D1 a D5 deviennent GAGNANTS et que
> le signe de l'effet s'inverse. Dire « la taxe carbone est regressive » sans
> cette condition serait une demi-verite. Rapporte aux DEPENSES totales plutot
> qu'au revenu, l'effort est d'ailleurs quasi plat (0,37 % contre 0,32 %). Le
> cheque energie (354 M EUR, 8,6 % des recettes) ne corrige pas la
> regressivite mesuree sur le revenu.

**Redistribution possible** : Cheque energie pour menages modestes

### Investissements Verts

**Multiplicateur keynesien** : 1,2 (recalibre v3.0, etait 1,5)
- Effet levier important
- Impact sur emplois verts : 15 000/Md EUR

**Retour fiscal propre — RETIRÉ (lot 2, 16/11/2026, non publié ; arbitrage du mainteneur du 15/11/2026).**
Jusqu'ici, le levier ajoutait à ses recettes 0 % de sa dépense d'investissement et de rénovation les deux
premières années, 5 % les deux suivantes, puis 8 %, au titre des impôts et cotisations de l'activité induite.
Les deux références citées ne portent pas ce chiffre : OCDE, *Getting Infrastructure Right* (2017, un cadre de
gouvernance ; aucun taux de retour fiscal, aucune édition 2021 trouvée) et « Cour des comptes 2023, retour TVA
8-10 % » (introuvable). Surtout, c'était un double compte : les recettes du moteur suivent déjà le PIB nominal,
avec une élasticité de 1,0 (§ Recettes), et ce canal porte précisément les impôts de l'activité induite ; ni
l'investissement des collectivités ni la recherche ne recevaient ce surplus. Désormais un euro d'investissement
public reçoit le même retour, celui de l'élasticité, quel que soit le levier : 10 Md€ par an par l'État ou par
les collectivités donnent la même dette, au bit. Le levier n'est pas autofinancé : tiré seul sur le droit en
vigueur, l'investissement comme la rénovation alourdissent la dette et le déficit en euros chaque année de 2028 à
2035 ; une amélioration en part du PIB vient du dénominateur, pas d'un remboursement. **Ce qui bouge** (mode
cadre 2028, dix scénarios publiés) : les quatre programmes qui investissent dans la transition, dette 2032 de
+0,01 à +0,04 point, déficit 2032 au plus −0,03 point ; aucun rang ne change ; les six autres scénarios sont
identiques au bit. Garde : `tests/test_transition_sans_retour_fiscal.py` (recettes propres limitées à la taxe
carbone ; pas d'autofinancement en euros, et part des recettes dans le PIB jamais relevée par le levier, ce que
l'ancien barème faisait ; même effet que l'investissement local ; et, pour les cinq leviers d'investissement —
transition, rénovation, collectivités, recherche, éducation —, aucune recette propre dans les impacts que le
moteur utilise, de sorte qu'un retour fiscal remis ailleurs que dans le handler fait aussi rougir la garde).

**Mesures d'investissement productif (pour multiplicateur)** : education, transition_eco, recherche (PAS defense ; hors revalorisation des enseignants en place, au traitement des transferts depuis le lot 5b) ; avec l'investissement local, la moitie d'une variation de dotation aux collectivites depuis le lot 5c

**Impacts :**
- Gini : **0** (lot 4, périmètre INSEE : une aide à des travaux est un transfert en
  capital, hors du revenu disponible ; variante hors champ −0,0017 pour +5 Md EUR,
  cf. § Aides Renovation Energetique)
- PA (v0.6.8 : canal ménages en euros, § Indice de pouvoir d'achat) : rénovation = aide à l'investissement (hors RDB), par la croissance ; taxe carbone par les prix, pour sa part payée par les ménages (64,6 %)
- Competitivite : +10 Md EUR = +0,002 (competitivite verte LT)
- L'investissement vert lui-meme n'a **aucun** canal Gini : aucune source ne
  donne l'incidence distributive d'un euro d'investissement. Le chiffre n'est
  pas fabrique.

### Aides Renovation Energetique

- MaPrimeRenov', eco-PTZ
- Effet levier : 1 EUR public = 3 EUR prive
- Reduction facture energetique menages

**Impact Gini (lot 4, périmètre INSEE)** : **0 de Gini pour +5 Md EUR**. Le
revenu disponible de l'INSEE ne comprend, côté transferts, que les indemnités
de chômage, les pensions et « les autres prestations sociales perçues »
(définition c1458) : une aide à des travaux est un transfert en capital (le
canal pouvoir d'achat du moteur la classe déjà hors RDB, v0.6.8), pas une
prestation sociale. La dérivation ci-dessous reste documentée comme variante
d'un indicateur élargi aux transferts en capital, qui n'est pas celui du site.

**Variante hors champ (v0.6.1, item I29)** : -0,00034 de Gini par Md EUR,
soit -0,0017 pour +5 Md EUR — meme signe que la v0.6.0, mais 1,7 fois plus
fort. Sources : ONRE/SDES, « Les renovations energetiques aidees du secteur
residentiel entre 2016 et 2020 », resultats provisoires, fevrier 2023,
graphiques 11 a 14 (MaPrimeRenov' concentre 60 % des economies d'energie sur
les deciles D1-D4 ; l'ancien CITE etait au contraire ANTI-redistributif) ;
Observatoire national de la precarite energetique, « Tableau de bord de la
precarite energetique », edition 2024, donnees Anah 2023 (« 505 126 dossiers
MaPrimeRenov' engages en 2023, 67 % concernent les menages modestes et tres
modestes »). Le coefficient de la v0.6.0 s'appuyait sur une publication
attribuee a l'agence de la transition ecologique que la collecte de sourcing
n'a pas pu retrouver ; la citation a ete retiree, pas reecrite.

> **HYPOTHESE DECLAREE** : aucune publication ne ventile les MONTANTS verses
> par decile — l'ONRE publie des economies d'energie, l'ONPE des nombres de
> dossiers. Le coefficient suppose donc que les euros suivent le profil des
> ECONOMIES D'ENERGIE. C'est une hypothese CONSERVATRICE : les taux de prise
> en charge plus eleves des menages « Bleu » et « Jaune » rendraient le profil
> en euros plus pro-pauvres, donc le coefficient plus fort. Confiance :
> DEFENDABLE, jamais SOLIDE.

Jusqu'au lot 4, ce paragraphe affirmait que l'aide à la rénovation « entre
légitimement dans le revenu disponible » : c'était inexact au sens de l'INSEE
(voir ci-dessus).

---

## Lutte contre la Fraude

### Fraude Fiscale

**Potentiel total** : 80-100 Md EUR/an (Solidaires FP 2018, AN)
- Detecte 2024 : 20 Md EUR (DGFiP)
- Objectif 2029 : 40 Md EUR (Gouvernement)
- ROI observe : 10-19x selon methode
- Taux recouvrement : 68%

**Multiplicateur specifique (v3.0)** : -0,40
- La fraude fiscale n'est ni une hausse fiscale ni une baisse de depenses
- C'est une meilleure application de la loi existante (enforcement)
- Multiplicateur modere (-0,40) entre -0,70 et -0,50

**IA/Numerisation integree par defaut** :
- 56% controles fiscaux declenches par IA (DGFiP 2024)
- Outils : CFVR, Foncier Innovant, GALAXIE
- Plan Pilat 2024 : unification chaine controle

**Montee en puissance** (intensite 100 %, cible maximale 30 Md EUR esperes —
Cour des comptes : la DGFiP recupere ~15 Md EUR/an, maximum realiste ~30 ;
recouvrement effectif 68 % — DGFiP 2024 : 11,4/16,7 — et couts de controle
15 % des recettes esperees). Correction v0.6.0 : l'ancienne echelle 70 Md EUR
esperes / 47,6 nets etait a un facteur ~3 du code (audit 08/2026, constat 6) :
- 2026 : 20% -> 6 Md EUR esperes -> 4,1 recouvres -> ~3,2 nets
- 2027 : 35% -> 10,5 Md EUR -> 7,1 recouvres -> ~5,6 nets
- 2028 : 50% -> 15 Md EUR -> 10,2 recouvres -> ~8,0 nets
- 2029 : 70% -> 21 Md EUR -> 14,3 recouvres -> ~11,1 nets
- 2030+ : 100% -> 30 Md EUR -> 20,4 recouvres -> ~15,9 nets (puis -5 %/an, plancher 70 %)

**Impacts macro** : Gini=0, PA=0, Competitivite=0 (recuperation argent du)

### Fraude Sociale

**Potentiel** : 13 Md EUR (RSA, APL, arrets maladie abusifs)

> **Valeur NON AUDITEE — dette declaree (balayage v0.6.1).** L'attribution
> qui figurait ici a un « haut conseil » de la protection sociale millesime
> sept. 2024 est **retiree** : l'acronyme employe ne designait aucun
> organisme. Ce n'est pas une faute de frappe a reparer — les deux
> institutions reelles au nom voisin (**HCFiPS** et HCFEA) ont ete verifiees,
> aucune ne publie ces chiffres. L'attribution n'est donc **pas remplacee**
> par une source de substitution.
>
> Ce que dit la source primaire reellement disponible — Cour des comptes,
> *Certification des comptes du regime general de securite sociale et du
> CPSTI, exercice 2024*, mai 2025 : le risque financier residuel sur les
> prestations CAF vaut **11,7 % a 9 mois (9,4 Md EUR)** et **8,0 % a 24 mois
> (6,3 Md EUR, jamais detecte)** ; la fraude estimee vaut **4,25 Md EUR, soit
> 5,1 % des prestations legales** (2023).
>
> Deux tensions avec la calibration du moteur, dites plutot que tues :
> le « potentiel 13 Md EUR » **depasse le risque residuel total** mesure par
> la Cour ; et **30 a 36 %** de ce risque sont des **rappels**, c'est-a-dire
> de l'argent **du aux allocataires**, dont la detection **augmente** la
> depense — le gisement brut d'indus plafonne donc vers **4,0-4,4 Md EUR**.
> Le levier `fraude_sociale` n'etait pas au perimetre du dossier de sourcing
> v0.6.1 : le ROI 8,75, le taux de recuperation 0,70 et le plafond 13 Md EUR
> sont laisses **inchanges** et instruits dans une passe dediee.

**Numerisation integree** :
- Croisement fichiers CAF/Pole Emploi/CPAM operationnel
- Datamining RSA/APL deploye toutes CAF
- ROI baseline : 8,75x (numerisation integree)

**Plafond realiste** : 13 Md EUR (plafond de NIVEAU, fraude detectee max)
**Cap IGAS** : 8 Md EUR (fraude sociale reellement recouvrable/an, IGAS 2023) — borne effective
**Impacts macro** : Neutralite totale

**Anti-double-comptage ASU (option A, mai 2026)** :
Quand l'ASU est active, ses controles IA integres captent deja une part
de la fraude sociale. Le levier « lutte fraude sociale » n'en recupere
donc que le **residuel** : `economies *= (1 - 0,30 · phasing_ASU)`,
applique APRES le cap IGAS (jusqu'a -30% a plein regime ASU, soit un
plafond effectif d'environ **5,6 Md EUR/an** quand l'ASU est pleinement
deployee — hypothese conservatrice assumee).
- Le coefficient **0,30** est l'overlap estime entre les controles
  automatises integres a l'ASU et le potentiel de fraude sociale.
  MAJ v0.6.1 : la composante symetrique cote ASU (`ECO_FRAUDE_STRUCT`,
  « 30% des 6,3 Md EUR d'erreurs CAF ») est **SUPPRIMEE**. La Cour des
  comptes (certification 2024) etablit que ce montant est une somme
  algebrique dont **30 a 36 % sont des rappels dus aux allocataires** :
  les detecter AUGMENTE la depense. Le residuel de fraude qualifiee est
  desormais porte par le seul curseur « Fraude sociale ». La reduction
  de -30 % ci-dessus est CONSERVEE : elle ne dependait pas de cette
  composante, seulement du fait que l'ASU integre des controles.
- **Contrepartie obligatoire** de l'exclusion symetrique des gains
  fraude IA (+3-6 Md€) cote ASU : sans cette reduction, ces montants
  ne seraient comptes ni cote ASU ni cote fraude_sociale (double-
  comptage inverse, biais optimiste ~+0,1 a +0,5 pt Dette/PIB sur les
  scenarios combinant ASU + fraude). Source unique du calendrier ASU :
  `handlers/_phasing.py::asu_phasing` (independant de l'ordre des
  handlers).

---

## Mesures Presidentielles 2027

### SMIC

**La règle (lot SMIC, arbitrage du mainteneur du 16/11/2026, non publiée).** Le curseur est le SMIC brut
mensuel. Pour les finances publiques, le moteur reprend les cinq postes qu'a publiés le groupe d'experts sur le
SMIC pour une hausse de 1 % (rapport 2017, tableau 9, PDF p. 82 ; modèle Saphir de la DG Trésor ; sans effet sur
l'emploi, par hypothèse de la source) et traite chacun selon sa nature :

| Poste (effet sur le solde public) | M€ de 2017 par point de hausse | Traitement dans le moteur |
|---|---|---|
| Cotisations des employeurs, nettes des allègements de charges | −400 | recette en moins (baisse de charges) : coefficient et profil des impôts |
| Cotisations et contributions des salariés | +240 | recette (impôt) : coefficient et profil des impôts |
| Paie publique | −260 | dépense au canal des rémunérations publiques : traitement des transferts (lot 5b) et effet prix sur le PIB en valeur publié (lot 5d) |
| Prestations sociales | +110 | baisse de dépense : un transfert, coefficient et profil des transferts |
| Impôt sur le revenu | +70 | recette (impôt) : coefficient et profil des impôts |
| **Total** | **−240** | |

- **La hausse** : un montant de programme se lit tel qu'il est écrit, comme un SMIC brut mensuel de son année
  d'application (l'origine du levier : 2028 pour les programmes publiés). Il est comparé à la référence portée à
  cette année avec l'indice de prix des dépenses du moteur, puisque la revalorisation légale fait déjà partie du
  statu quo : hausse = montant / (référence × indice de l'année d'application / indice de l'année de référence)
  − 1. Elle est fixée cette année-là, puis conservée en pourcentage : le SMIC du programme suit ensuite la
  revalorisation légale. La valeur du droit en vigueur est la seule valeur neutre lue telle quelle : elle se lit
  dans les euros de l'année de référence, quelle que soit l'année de début. Tout montant différent, même d'un
  centime, se lit comme un SMIC de l'année d'application. En mode historique, l'année d'application est l'année
  de référence : la lecture est continue (1 900 € : hausse de 1,77 %). **Limite** : en mode cadre, tout montant
  compris entre la valeur du droit et la référence portée à l'année d'application est une baisse, et la lecture
  saute à la valeur du droit. En 2028 (référence portée à 1 920,21 €) : 1 867,02 € donnent une hausse nulle,
  1 867,03 € une baisse de 2,77 %, 1 900 € une baisse de 1,05 % ; la hausse ne devient positive qu'au-delà de
  1 920,21 € (1 950 € : +1,55 %). Les programmes publiés sont encodés sur des points exacts de la règle (valeur du
  droit, ou montant de leur source).
- **La référence** : le dernier SMIC brut mensuel paru au Journal officiel, 1 867,02 € (12,31 € de l'heure sur la
  base de 35 heures ; arrêté du 22 mai 2026, en vigueur au 1er juin 2026), année de référence 2026, soit environ
  1 920 € en 2028 avec les prix du moteur. C'est aussi la valeur du droit en vigueur et le défaut du curseur.
  **Limites** : la règle légale de revalorisation ajoute à l'inflation la moitié du gain de pouvoir d'achat du
  salaire horaire de base des ouvriers et employés, que le moteur ne compte pas : la référence est un peu basse,
  donc la hausse d'un programme un peu haute ; la référence est à mettre à jour à la parution du décret de
  décembre 2026.
- **Un montant écrit en net** se convertit en brut avec le rapport officiel net / brut du SMIC : 1 477,93 / 1 867,02
  ≈ 0,7916 (`PART_NETTE_DU_BRUT_SMIC`, `smic_brut_du_net`) ; 1 700 € nets valent ainsi 2 147,55 € bruts.
- **Mise à l'échelle** : chaque poste × salaires bruts 2025 / salaires bruts 2017 (1 157,166 / 880,657 Md€,
  Insee, comptes nationaux base 2020, tableau 2.101) × PIB nominal de l'année / PIB 2025, × la hausse en points.
- **Paie publique** : seul l'écart entre la hausse du SMIC et celle du point d'indice compte (anti double
  compte : un point d'indice relevé couvre déjà une partie de la hausse pour les agents) ; aucune économie pour
  une baisse du SMIC. **Limite** (sens : favorable à une baisse du SMIC ; aucun programme publié n'est concerné) :
  pour une baisse, la paie publique n'est pas réduite et les quatre autres postes restent linéaires. Une baisse
  coûte donc au budget, 20 M€ de 2017 par point (prestations −110, impôt sur le revenu −70, cotisations des
  salariés −240, cotisations des employeurs nettes des allègements +400), et soutient l'activité : en 2028, à
  ±2,60 % autour de la référence portée à l'année, PIB réel 2032 +0,018 % pour la hausse et +0,002 % pour la
  baisse. Au minimum du curseur (1 400 €, baisse de 27,09 %), le solde direct du levier se dégrade de 4,0 Md€ sur
  2028-2032, mais la dette 2032 baisse de 0,40 point, par l'effet direct sur le chômage (chômage 2032 plus bas
  de 0,53 point) et les allocations économisées. Chiffres recalculés par `tests/test_smic_limites.py`.
- **Recettes** : prélèvements des salariés, impôt sur le revenu et allègements forment un seul flux, au
  coefficient des impôts ; c'est exact parce que la hausse et la baisse d'impôts ont le même coefficient
  (0,674), ce que vérifie un test.
- **Pouvoir d'achat** : le revenu disponible du tableau 8 du même rapport (PDF p. 81), +690 M€ par point :
  revenu brut +1 110, cotisations et contributions des salariés −240, impôt sur le revenu −70, prestations
  −110 (prime d'activité −50, aides au logement −40, prestations familiales −10, minima sociaux −10). La part
  des agents publics passe par la règle du moteur (0,535 € de revenu par € de coût) ; le reste est le salaire
  net du privé. Les cotisations des salariés ne sont comptées qu'une fois, dans le salaire net.
- **Emploi** : effet direct conservé, +0,025 point de chômage par point de hausse, une fois, l'année où la
  hausse s'applique (il passe par la dépense d'allocations ; le chômage ne revient pas sur la croissance).
- **Compétitivité** : inchangée (−0,025 par point de hausse, une fois).
- **Gini** (lot 4) : −0,02375 × hausse relative (`GINI_SMIC_PAR_HAUSSE`), une fois, l'année où la hausse
  s'applique. La hausse est celle du levier : SMIC du programme rapporté au SMIC de référence de l'année
  d'application (référence datée ci-dessus), 0,10 = +10 %. Centre de la plage −0,0231 à −0,0244 tirée des gains
  par dixième de revenu disponible du même rapport du groupe d'experts (graphiques n° 41 et 45 : la hausse de 1 %
  du tableau 8 répartie par dixième ; le « −0,1 % » du tableau n° 12 en est l'arrondi). Chiffrage statique pour
  +1 % ; extrapolation linéaire aux hausses encodées = convention déclarée, qui surestime probablement la baisse
  de l'indice pour les fortes hausses. Jusqu'ici −0,03 × hausse (« INSEE 2024 », sans passage retrouvé).
- **Limites de l'ancrage sur le Trésor** (arbitrage du mainteneur ; mode cadre 2028, pleine précision, programmes
  publiés qui relèvent le SMIC ; chiffres recalculés par `tests/test_smic_limites.py`) :
  1. *Coût au bas de la fourchette publiée* — sens : favorable aux programmes qui relèvent le SMIC. Le Trésor
     chiffre −0,0105 point de PIB par point de hausse (modèle statique, sans effet sur l'emploi) ; l'OFCE, −0,020
     (2012) à −0,024 (2024 : −0,3 point de PIB pour 12,4 %) point (modèle e-mod, dynamique, emploi compris, à un
     an). Si l'écart entre les deux sources était entièrement réel, ajouté chaque année en coût budgétaire pur,
     sans effet sur la demande, la dette 2032 serait plus haute de 0,24 à 0,67 point (écart de l'OFCE 2012) et de
     0,34 à 0,97 point (OFCE 2024).
     Aucune des deux sources n'est « la bonne » : l'une exclut l'emploi par hypothèse, l'autre est un seul modèle.
  2. *Effet direct sur le chômage au-dessus de l'effet net de l'OFCE* — sens contraire : défavorable aux
     programmes qui relèvent le SMIC. Le moteur ajoute 0,025 point de chômage par point de hausse ; l'effet net
     de l'OFCE, allègements compris, est de 0,007. Ramené à 0,007, le chômage 2032 serait plus bas de 0,06 à 0,16
     point et la dette 2032 plus basse de 0,04 à 0,13 point (moins d'allocations).
  3. *Revenu des salariés du privé et coût du travail absents du PIB* — sens : plutôt favorable aux programmes qui
     relèvent le SMIC, contraire à celui de la limite 2. Le salaire net en plus des salariés du privé (de 4,7 à
     14,0 Md€ en 2032) ne soutient pas la demande dans le moteur, et la hausse du coût du travail n'y freine pas
     l'activité. L'OFCE, tous canaux compris, en tire une perte nette d'environ 2 300 emplois par point de hausse à
     un an, soit de 9 600 à 27 200 emplois pour ces programmes ; aucune source ne publie l'effet sur le PIB.
- **Ce qui disparaît** : le coefficient propre de 0,15 appliqué au solde du levier, qui ne venait d'aucune
  source ; une paie publique de 50 Md€ de masse (15 à 45 % au-dessus du Trésor) ; 12 Md€ de prestations qui
  montaient avec le SMIC (selon le Trésor, elles baissent) ; des cotisations à 45 % sur 2,7 millions de
  salariés ; la part nette de 0,78, sans source.

Tests : `tests/test_smic_flux_tresor.py`, `tests/test_smic_reference_datee.py`, `tests/test_smic_parametres.py`,
`tests/test_smic_limites.py`.

### ISF Climatique

**Debat politique :**
- NFP : ISF retabli, seuil 1,3M EUR, bareme progressif, bonus ecologique
- RN : Opposition totale
- Centre : Maintien IFI immobilier (2 Md EUR)

**Potentiel** : 0-18 Md EUR selon bareme

**Curseur d'intensité — courbe continue (v0.6.7, audit externe Codex 10/2026, arbitrage du
mainteneur du 07/10/2026)** : `recette totale = IFI + intensité × (ISF complet − IFI)`, donc écart au statu quo =
`intensité × (ISF complet − IFI)`, où « ISF complet » est le point NFP ci-dessous (seuil 1,3 M EUR,
taux 1 %, bonus vert 30 % : ≈ 10,07 Md EUR de recette nette en 2025, IFI déduit ; +8,31 Md EUR en 2030 en
mode cadre). L'IFI déduit vaut 2,714 Md EUR en 2025 (Insee, comptes nationaux ; 2 Md EUR jusqu'au lot 3).
La recette de l'ISF et l'IFI déduit suivent tous deux le PIB nominal depuis 2025 (règle
« un taux suit son assiette », comme l'impôt plancher). Jusqu'au lot 3, l'IFI croissait de 2 % par an
depuis 2026, une convention propre à ce levier (2,16 Md EUR en 2030), et la recette de l'ISF restait
fixe en euros : la règle ne s'appliquait qu'à un côté de la différence. L'année source de la recette
(2025, celle de l'IFI remplacé, `ANNEE_SOURCE_ISF`) est une convention de symétrie, déclarée : les
chiffrages publiés qui calent la recette, de 2024, ne fixent pas d'année de base. Le plafond de 18 Md EUR
s'applique en euros de 2025 et ne mord jamais. Gini et compétitivité sont comptés hors indice (euros de
2025), comme pour les autres impôts à taux. Gini, pouvoir d'achat et compétitivité sont interpolés de la
même façon. Monotone, nul à 0, identique au bit à 1
(`tests/test_isf_continu_v067.py`, grille de 1 000 points). Jusqu'en v0.6.6, l'intensité pilotait
seuil, taux et bonus avec des paliers de foyers et d'assiette en escalier : dès 10⁻⁶ l'IFI était
supprimé alors que le nouvel impôt ne rapportait presque rien (−2,17 Md EUR en 2030), puis deux
falaises (+1,26 Md EUR à 0,571 ; +2,82 Md EUR entre 0,999 et 1). Scénarios publiés : LFI et
Écologistes (intensité 1) inchangés au bit ; `ps_2027` (0,6) passe de +2,0 à +4,7 Md EUR/an
environ (dette 2035 −0,45 pt) ; les autres ne recourent pas au levier.

**Distribution patrimoniale (IPP 2024) :**
- 1,3M EUR : 350k foyers (top 1,5%, seuil NFP)
- 2,0M EUR : 130k foyers (top 0,5%)

**Bareme progressif NFP :**
- 0,5% (1,3-2,5M EUR)
- 0,7% (2,5-5M EUR)
- 1,0% (>5M EUR)

**Bonus ecologique** : 20% patrimoine eligible (ENR, forets)
- Reduction assiette = assiette x 0,20 x bonus

**Phasing** : 2 ans (cadastre fiscal)
- 2026 : 50%
- 2027+ : 100%

**Impacts :**
- Gini (lot 4, méthode unique) : −0,000444 par Md EUR de recette nette d'année pleine, IFI remplacé
  déduit (coefficient de l'IFI de l'INSEE), émis au changement de l'intensité, comme l'impôt plancher
  (corrigés ensemble). Jusqu'ici −0,020 pour 12 Md EUR de recette BRUTE, le phasage compté deux fois
- PA (v0.6.8 : canal ménages en euros, § Indice de pouvoir d'achat) : prélèvement direct, −1 € de RDB par €
- Competitivite : -0,002 (risque exil entrepreneurs)

**Combiné avec « Fiscalité du patrimoine » (IFI compté une seule fois, proposé après v0.8.1).** L'ISF
d'intensité i remplace la part i de l'IFI. Le curseur du patrimoine, qui fait varier IFI, successions et
taxe foncière, ne fait donc varier que l'IFI encore en vigueur, (1 − i) × IFI : à l'intensité 1, il ne
touche plus l'IFI. Avant, il faisait varier l'IFI entier, déjà supprimé : pour ISF 1 et patrimoine
+30 %, 0,6 Md EUR par an d'un impôt qui n'existait plus, dans la recette, le pouvoir d'achat et le Gini.
L'intensité lue est celle de l'année (même lecture que l'impôt plancher). Aucun scénario publié ne
combine les deux leviers. Verrouillé par `tests/test_ifi_double_compte.py`.

### Taxe Superprofits

**Debat politique :**
- NFP : 25% sur superprofits (>120% moyenne 2017-2021) -> +15 Md EUR
- RN : 33% energeticiens uniquement
- Centre : Opposition (exil fiscal)

**Assiette superprofits (2022-2024) :**
- Tous secteurs : 60 Md EUR
  - Energie : 40 Md EUR (TotalEnergies, Engie)
  - Banques : 10 Md EUR
  - Luxe : 5 Md EUR
  - Tech : 5 Md EUR

**TEMPORAIRE** : 3 ans (disparait apres 2028)

**Plafond realiste** : 20 Md EUR

**Impacts :**
- Gini : 0 (lot 4, périmètre : impôt payé par des sociétés, hors du revenu disponible des ménages, comme l'IS ; jusqu'ici −0,01 pour 15 Md EUR, sans source)
- PA : aucun effet direct (taxe entreprises, par la croissance)
- Competitivite : -0,005 pour 15 Md EUR tous secteurs
- Taux nul (intensité 0) : mesure inactive, neutre sur tous les canaux. Jusqu'à v0.6.6,
  la branche « énergie seule » émettait -0,002 de compétitivité à intensité 0, sans
  taxe levée : poser le levier à 0 ou l'omettre ne donnait pas la même trajectoire
  (corrigé v0.6.7, `tests/test_audit_codex_v067.py`).
- Bloc vide `{"taxe_superprofits": {}}` : sans clé `intensite`, le levier passe en mode
  legacy, dont les défauts sont ceux du programme NFP (25 %, seuil 120 %, tous
  secteurs) — il applique donc la taxe pleine (+15 Md EUR/an 2026-2028). Pour le
  désactiver : `{"intensite": 0}` ou clé omise.

### TVA Energie Differenciee

**Debat politique :**
- NFP/RN : TVA 5,5% -> -17 Md EUR recettes
- Centre : Maintien 20% + bouclier tarifaire

**Modele economique :**
- Consommation energie : 120 Md EUR/an
- Recettes actuelles 20% : 24 Md EUR
- Si TVA 5,5% : 6,6 Md EUR -> perte 17,4 Md EUR

**Impacts (effet NIVEAU annee 1) :**
- PA (v0.6.8 : canal ménages en euros, § Indice de pouvoir d'achat) : baisse répercutée à τ− = 0,5 sur la part de la TVA nette qui pèse sur la consommation des ménages (56,0 %, la base de 120 Md€ comprenant l'énergie des entreprises)
- Gini : 0 (lot 4, périmètre INSEE : niveau de vie mesuré avant les prix ; jusqu'ici −0,0073, sans source)
- Competitivite : 0 (entreprises ont TVA deductible)

---

## Curseurs de la release E (v0.8.0)

Onze curseurs, chacun avec ses bornes sourcées, ses canaux (budget, ménages, Gini, compétitivité)
et ses règles d'indépendance avec les curseurs voisins, testées par mutation
(`tests/test_release_e_w2.py`, `tests/test_release_e_w3.py`, `tests/test_release_e_w4.py`). Les
coefficients par Md€ sont des expressions des constantes du moteur, signées (effet d'un Md€ en plus),
jamais des nombres recopiés (`constants.py`, bloc « RELEASE E — SOCLE »). À leur valeur neutre, les
curseurs laissent toutes les sorties identiques au bit.

### Dépenses publiques, prestations aux ménages, flux vers l'étranger

#### Une règle commune : un montant reste constant en euros courants

Un curseur en Md€ porte le montant qu'un programme écrit, identique chaque année d'application,
sans revalorisation. C'est la convention des curseurs en Md€ existants (défense, niches,
impôts de production, subventions). Une dépense et une recette de même montant ont donc la
même trajectoire de solde. Conséquence dite : leur poids dans le PIB baisse avec la croissance
nominale (d'environ 10 % de 2028 à 2032 au rythme du moteur). Seul un **taux** suit son
assiette.

#### `prestations_menages`

- **Calcul** : dépense = `solidarite + pensions`, chaque année d'application.
- **Pouvoir d'achat** : le même montant est un revenu versé (ou retiré) aux ménages, canal
  « prestations » de l'indice de revenu disponible.
- **Croissance** : multiplicateur des transferts sociaux, en consolidation comme en expansion,
  et profil de décroissance des transferts (le levier est rangé avec les prestations existantes).
- **Inégalités** : effet ponctuel, émis l'année d'entrée en vigueur (puis, sous un calendrier
  progressif, par incréments dont la somme vaut l'effet du palier ; un montant posé une seule
  année est rendu l'année suivante) :
  `Gini = GINI_SOLIDARITE_PAR_MD × solidarite + GINI_PENSIONS_PAR_MD × pensions`.
  - `GINI_SOLIDARITE_PAR_MD = −0,000521` (lot 4, sourcé) : coefficient des prestations
    ciblées de l'INSEE au classement final (prestations familiales, aides au logement, minima
    sociaux et prime d'activité ; *Revenus et patrimoine des ménages* 2024), au signe d'une
    hausse. Jusqu'ici −0,0008, la règle chômage « OFCE 2023 ».
  - `GINI_PENSIONS_PAR_MD = −0,0000685` (lot 4, centre de la **plage publiée** −0,0000474 à
    −0,0000895 : § Indicateurs Macroeconomiques, méthode unique). Jusqu'ici ≈ −0,00024 :
    effet **cumulé** d'un gel total de l'indexation des
    pensions sur le mandat de cinq ans tel que le moteur l'émet (0,005 la première année, puis
    10 % de ce flux chaque année), rapporté à l'économie atteinte en fin de mandat
    (380 Md€ × (1 − 1,016⁻⁵)). Plus faible par Md€ que la solidarité, parce que la population
    concernée est moins pauvre : même ordre que les règles du moteur.
  - Les deux constantes sont signées (effet d'un Md€ versé en plus) ; le calcul n'ajoute aucun
    signe.
- **Ce que le curseur ne fait pas** : il ne modifie ni la masse des minima sociaux ni celle des
  retraites, et ne lit aucun autre curseur. Il s'ajoute donc aux règles d'indexation des
  prestations et des pensions, au SMIC, à l'assurance chômage (règles et budget des
  allocations) et à l'allocation sociale unique : celle-ci neutralise la seule règle
  d'indexation des prestations, pas un montant décidé. Âge de départ, durée de cotisation et
  indexation des pensions restent au curseur des retraites ; les indemnités journalières
  maladie relèvent du curseur des moyens de soins.

#### `depenses_publiques`

- **Calcul** : dépense = `credits_etat + ondam + transferts_capital`, chaque année
  d'application.
- **Croissance** : multiplicateur d'une dépense générique (celui de la coupe de dépense
  courante, en hausse comme en baisse depuis le lot 5 ; jusque-là, celui des transferts en
  hausse) et profil de décroissance des impôts, comme le curseur de défense : `credits_etat = x`
  donne les mêmes résultats que la défense relevée de x, vérifié par test dans les deux modes et
  dans les deux sens. En mode cadre, une coupe de crédits est lue comme une consolidation alors
  qu'une défense ramenée sous son niveau du droit en vigueur, mais au-dessus du défaut du
  moteur, reste une expansion moindre : jusqu'au lot 5, les deux sens n'avaient pas le même
  coefficient et les résultats différaient ; ils sont désormais identiques.
- **Pas d'effet direct** sur le pouvoir d'achat, le Gini ni la compétitivité (règle des
  dépenses publiques du moteur). `transferts_capital` est une somme versée une fois en capital,
  hors revenu courant ; limite dite : il prend le multiplicateur d'une dépense générique.
- **Priorité aux curseurs dédiés** : postes (fonction publique, hôpital compris), agences,
  collectivités, défense, éducation, recherche, subventions aux entreprises, aide médicale de
  l'État, rénovation des logements, contribution européenne et aide au développement,
  prestations versées aux ménages ont leur propre curseur. Les crédits s'y ajoutent sans les
  modifier (vérifié par test, à état identique, pour chacun) ; l'Ondam s'ajoute aux efforts
  d'efficience et à la prévention du curseur Santé sans les modifier.

#### `transferts_etranger`

- **Calcul** : dépense = `montant`, chaque année d'application.
- **Multiplicateur intérieur nul** : aucune impulsion de demande n'est enregistrée pour ce
  flux. Critère : la contrepartie directe est un agent non résident (budget de l'Union,
  bénéficiaires de l'aide extérieure). Un impôt payé par une entreprise établie en France garde
  le multiplicateur fiscal, quelle que soit l'origine de ses bénéfices : le moteur ne modélise
  l'incidence finale d'aucun impôt sur les sociétés.
- **Ce qui reste** : le montant compte dans le solde, la dette et l'effort budgétaire total. Une
  coupe réduit la dette et donc la traînée de dette sur la croissance (seul canal mesuré l'année
  suivante, vérifié par test, pour une coupe comme pour une hausse depuis le retrait de l'éviction
  au lot 1) ; l'effort total nourrit la prime de taux : effet de financement et non de demande.
- **Hors des deux autres effets de demande** : le terme d'inflation lié à l'effort budgétaire et
  la cicatrice d'austérité (effort au-delà de 3 % du PIB) lisaient l'effort INTÉRIEUR, net de ce
  flux (inflation de l'année suivante inchangée, vérifié par test). Depuis le lot 1 (15/11/2026),
  les deux sont retirés, l'effort intérieur avec eux : le flux ne change la croissance de l'année
  suivante que par la traînée de dette, y compris sur une consolidation sévère (vérifié par test). **Corrigé avant
  publication** (revue adverse de la release) : la première version les laissait lire l'effort
  total ; une coupe de 32 Md€ baissait l'inflation de 0,12 point l'année suivante, et sur un
  programme déjà au-delà de 3 % d'effort, la coupe déclenchait la cicatrice.
- **Aucun effet direct** sur le pouvoir d'achat, le Gini ni la compétitivité.
- **Faisabilité** : la contribution européenne est fixée par les décisions de l'Union (cadre
  financier pluriannuel) ; le simulateur chiffre l'effet budgétaire d'une variation sans juger
  de sa faisabilité.
- **Exclusion** : avec le rabot uniforme appliqué sans exclure la contribution européenne, le
  curseur est ignoré (le rabot coupe déjà cette contribution ; règle X2, § « Garde-fous d'entrée (v0.8.0) »). Avec le rabot hors contribution européenne, les deux s'additionnent.

#### Bornes hautes relevées (v0.8.1) : objectifs écrits en part du PIB ou du RNB

Décision du mainteneur du 12/11/2026 : un objectif de dépense qu'un programme publié écrit en part du
PIB ou du revenu national brut est compté, pour tous, par une seule convention (écart entre l'objectif
et le dernier niveau officiel, multiplié par le PIB de l'année visée dans la référence du moteur). Trois
bornes, que la première version ne sourçait pas, sont relevées jusqu'au plus haut de ces objectifs, au
PIB de 2032 de la référence (3 565,1 Md€ ; mesures vides, début 2028), arrondi au pas du curseur
supérieur ; la garde `tests/test_release_p_bornes_objectifs.py` recalcule l'objectif sur la référence et
vérifie qu'il est sous la borne, à moins d'un pas :

| Paramètre | Avant → après | Plus haut objectif publié | Dernier niveau officiel |
|---|---|---|---|
| `recherche_publique.budget` | 20 → 37 | 1,5 % du PIB pour la recherche du secteur public en 2032 : base 10 + 0,75 point × 3 565,1 = 36,74 | 0,75 % du PIB en 2024 : « L’effort de recherche des administrations représente 0,75 % du PIB en 2024 » (MESR-SIES, note flash n° 2026-16) |
| `transferts_etranger.montant` | 10 → 10,5 | aide publique au développement à 0,7 % du RNB : 0,28 point × 3 565,1 × 1,0172 = 10,15 | « 0,42 % du revenu national brut (RNB) » en 2025 (document de politique transversale « Politique française en faveur du développement », annexe au projet de loi de finances pour 2027) ; RNB/PIB 2025 = 3 042 365 / 2 991 055,9 (Eurostat) |
| `depenses_publiques.credits_etat` | 20 → 28 | dépense publique culturelle à 1 % du PIB, en plus de 14,6 Md€ de crédits annoncés (plus haut montant écrit) : 14,6 + 0,354 point × 3 565,1 = 27,22 | services culturels de toutes les administrations, 18 963,0 M€ en 2024, soit 0,646 % du PIB (Eurostat, COFOG 08.2) |

Aucune borne ne change un calcul : chaque Md€ du curseur reste un Md€ de dépense (vérifié par test
jusqu'à la borne). Un euro d'aide publique au développement, agrégat de l'OCDE (dons, prêts comptés en
équivalent-don, frais d'accueil des réfugiés), est compté comme un euro de dépense publique.

#### Repères mesurés (dépenses, budget 2026 reconduit, mode cadre 2027-2032)

Écart au budget 2026 reconduit, un curseur à la fois (moteur v0.8.0, banc d'intégration) :

| Curseur | Solde 2028 | Solde 2032 | Dette 2032 | Croissance 2029 | Gini 2032 | Pouvoir d'achat 2032 |
|---|---|---|---|---|---|---|
| `credits_etat` −10 | +0,33 pt | +0,20 pt | −0,37 pt | −0,20 pt | 0 | −0,2 |
| `solidarite` −10 | +0,33 pt | +0,22 pt | −0,48 pt | −0,19 pt | +0,005 | −0,6 |
| `pensions` −12 | +0,39 pt | +0,27 pt | −0,59 pt | −0,23 pt | +0,001 | −0,7 |
| `transferts_etranger` −5 | +0,17 pt | +0,22 pt | −0,91 pt | 0,00 pt | 0 | 0 |

Points de PIB pour le solde et la dette (un solde « +0,33 » = déficit réduit de 0,33 point),
points de croissance, unités du Gini et de l'indice de pouvoir d'achat (base 100 en 2025) ;
valeurs arrondies des sorties publiées du moteur. Colonne Gini remesurée au lot 4 (méthode unique :
+0,0055 et +0,0013 ; jusqu'ici +0,0016 et +0,0006).

### Recettes en Md€ sans comportement, déplafonnement des cotisations salariales

#### Recettes en Md€ sans comportement : règle commune

Chaque levier rend, l'année où il s'applique, `Δrecettes = montant` (aucune dépense). Le montant ne dépend ni de
l'année, ni du PIB, ni des prix : 10 Md€ en 2028 restent 10 Md€ en 2032, ce qui fait baisser leur poids dans le PIB
d'environ 10 % sur le mandat (même convention que les autres curseurs en Md€). Les quatre leviers prennent la classe
« recettes » du multiplicateur budgétaire, comme tout prélèvement du moteur : à montant égal, successions, TVA à taux
réduits, accises et impôt sur le revenu ciblé donnent la même trajectoire de croissance, d'inflation (déflateur), de
chômage, de déficit et de dette (vérifié en test à 1e-12 près, en hausse et en baisse, dans les deux modes) ; seuls
diffèrent les indicateurs qui leur sont propres (Gini, compétitivité, pouvoir d'achat, inflation des prix à la
consommation), et une hausse de TVA à taux réduits, qui passe dans les prix l'année suivante comme la TVA normale
(voir les limites ci-dessous).

Effets ponctuels : effet = coefficient signé × montant, émis l'année d'entrée ; une montée progressive émet les
incréments (leur somme vaut l'effet du palier) ; un retour au neutre rend l'effet (somme nulle).

| Levier | Canal ménages | Gini par Md€ | Compétitivité par Md€ | Source de la règle |
|---|---|---|---|---|
| Successions et donations | aucun (transfert en capital) | 0 (lot 4 : hors revenu disponible ; jusqu'ici −0,001) | −0,0002 | Gini : périmètre INSEE ; compétitivité : levier « Fiscalité du patrimoine » (−0,002 pour 10 Md€) |
| TVA à taux réduits | prix, 100 % | 0 (lot 4 : niveau de vie avant les prix ; jusqu'ici +0,000176) | −0,0000176 | levier « TVA » (−0,0005 pour +2 points, rapportés à la recette de +2 points au PIB 2025) |
| Accises sur l'énergie | prix, 56 % (part de la consommation des ménages dans la TVA) | 0 (lot 4 : niveau de vie avant les prix ; jusqu'ici +0,000417) | 0 | — |
| Impôt sur le revenu ciblé | prélèvement direct, 100 % | 0 | 0 | lot 4 : zéro faute de source, le levier ne dit pas quel instrument il porte (§ Méthode unique du Gini ; jusqu'ici la règle de la décote, +0,0004) |
| Recette exceptionnelle | aucun | 0 | 0 | — |

Signes : une hausse de recette sur le patrimoine réduit la compétitivité. Lot 4 : successions et taxes sur la
consommation n'ont plus d'effet Gini (périmètre INSEE) ; l'impôt sur le revenu ciblé non plus, faute de source sur
l'instrument (le signe dépend de l'instrument : § Méthode unique du Gini).

#### Recettes en Md€ : limites dites

- **Successions** : la borne basse (−21,052 Md€) est la recette de 2025 des droits de succession et de donation
  (Insee, comptes nationaux, tableau 3.217 ; même valeur que la part « successions et donations » du curseur
  « Fiscalité du patrimoine », arbitrage du mainteneur). Les droits de la référence suivent le PIB : une
  baisse encodée à la borne laisse leur croissance depuis 2025 (≈ 1,6 Md€ en 2028, ≈ 4 Md€ en 2032, calcul du
  contrat). Le levier ne se combine pas avec « Fiscalité du patrimoine », qui fait déjà varier les successions (règle d'exclusion X1, § « Garde-fous d'entrée (v0.8.0) »).
  La borne haute (+25 Md€ par an, `DMTG_VARIATION_MAX_MD`) est une décision du mainteneur du 12/11/2026 : le plus
  haut supplément annoncé par un programme publié, compté tel quel ; la borne +20 de la première version n'était pas
  sourcée. **Aucune décote d'évitement** : au sommet, l'impôt payé est déjà loin du barème — le 0,1 % qui hérite le
  plus « ne paie qu’à peine 10 % de droits de succession sur l’ensemble de ce patrimoine hérité, bien loin du taux
  marginal de 45 % affiché par le barème » (Conseil d'analyse économique, note n° 69, 2021, p. 4-5) ; transmission
  par décès d'une entreprise de 100 M€ à deux enfants : « un taux effectif d’imposition de 10,7 % » avec le pacte
  Dutreil, 44,4 % sans (Cour des comptes, *Les droits de succession*, 2024, p. 28) — et, pour une forte hausse, aucune
  étude ne permet de chiffrer la part évitée, qui dépend de la fermeture des dispositifs dérogatoires (pacte Dutreil,
  assurance-vie, démembrement). L'infobulle du curseur le dit ; un réglage d'évitement sourcé reste à faire.
- **Accises** : la part payée par les ménages est provisoire (part de la TVA, à sourcer pour les accises) ; les
  entreprises paient une partie des accises, mais la compétitivité est nulle, comme pour la TVA sur l'énergie.
- **TVA à taux réduits** : elle passe par le coin de prix de l'indice des prix à la consommation ET, comme le
  levier « TVA », par le passage dans les prix l'année qui suit chaque hausse (30 % de la hausse en points de
  PIB, plafonné à 0,2 point) : à recette égale, même effet sur l'inflation que le taux normal (vérifié par test à
  1e-12 point près). Comme c'est un montant qui admet les calendriers « une seule année » et « rampe », le passage
  porte sur l'**incrément annuel positif** de sa recette : chaque marche d'une rampe passe, plafonnée à 0,2 point ;
  quand une hausse antérieure est retirée (fin d'une hausse d'une seule année), le passage déjà fait est rendu au
  prorata du retrait (passage négatif symétrique), si bien que le niveau des prix revient vers la référence ; une
  baisse sous zéro ne passe pas (règle du taux normal). **Règle d'addition** avec le taux normal : seules les
  hausses de l'année s'additionnent avant le plafond commun ; une baisse de l'un n'annule pas la hausse de l'autre.
  Le levier « TVA » (taux normal), qui ne change qu'une fois, garde sa règle au bit. Les accises n'y passent pas,
  comme le levier « TVA sur l'énergie ». **Corrigé avant publication**, deux fois : (1) revue adverse de la release
  — la première version ne donnait ce canal qu'au taux normal ; à recette égale (15,3 Md€), l'inflation de l'année
  suivante montait de 0,09 point avec le taux normal et baissait de 0,05 avec les taux réduits (0,35 point de dette
  2032 d'écart) ; (2) contre-vérification — la correction faisait un seul passage, sur le niveau de l'année
  d'origine et à la hausse seulement : une hausse d'une seule année laissait le niveau des prix relevé pour toujours
  (dette 2032 −0,58 point contre −0,24 pour une recette exceptionnelle du même montant), une rampe ne passait que sa
  première marche, et une baisse des taux réduits annulait la hausse du taux normal la même année.
- **Recette exceptionnelle** : comme tout prélèvement, elle freine la croissance l'année de la recette (l'année
  suivante jusqu'au lot 6, calendrier de l'impulsion), puis l'effet s'inverse. Elle s'applique une seule année (calendrier « annee », obligatoire ; refusée en mode historique).
- **Cotisations salariales, mode montant** (proposé après v0.8.1) : un programme qui écrit sa baisse en milliards
  d'euros (et non en points) s'encode avec `cotisations_salariales.montant_md`, Md€ par an rendus aux salariés,
  constants en euros courants (règle commune des montants), de 0 à 138,217 Md€ (la masse des cotisations salariales de
  2025) ; il admet la rampe et les valeurs annuelles, comme les autres montants (référence de la rampe : 0). Mode
  exclusif : avec `montant_md`, `baisse_points` n'est pas lu (refus en mode strict, correction signalée sinon). Même
  effet sur les inégalités par Md€ rendu (`GINI_COTIS_SAL_PAR_MD`). Avant, les programmes écrits en Md€ étaient
  convertis en points au coût du point de 2025, ce qui n'était fidèle que tant que le point restait figé.
- **Cotisations salariales** : un point vaut 1 % de la masse salariale brute 2025, tous salariés, public compris
  (Insee, tableau 2.101, D11 = 1 157,166 Md€), soit ≈ 11,57 Md€, calculé à partir de cette donnée ; le maximum du
  curseur, la suppression des 138,2 Md€ de cotisations salariales (D613CE, même tableau, même année), vaut donc
  ≈ 11,94 points : le taux moyen réel. « Baisser de X points » signifie « baisser le taux moyen de X points ».
  C'est un majorant du rendement d'une baisse d'un point du taux légal (une partie des salaires bruts est hors
  assiette) ; la valeur de la Commission des comptes de la Sécurité sociale pour les seuls salariés, cotisation
  déplafonnée (9,74 Md€ en 2026, octobre 2026, encadré 2), en est la borne basse sourcée. **Corrigé avant
  publication** (décision du mainteneur du 12/11/2026) : la première version comptait 6 Md€ par point, sans source
  (vraisemblablement un point sur l'assiette du seul secteur privé vers 2018-2019), et la borne valait 23,03 points,
  près de deux fois le taux réel. Un programme écrit en points voit son montant presque doubler (× 1,93) ; ceux
  qu'on a encodés en points à partir d'un montant en Md€ seront reconvertis depuis ce montant à la release de
  paramètres (leur solde ne bougera alors pas). L'effet sur les inégalités est un coefficient PAR Md€ rendu aux salariés : +0,0000541 de Gini par
  Md€ (constante `GINI_COTIS_SAL_PAR_MD` ; lot 4 : les salaires de l'Insee au classement final, sous la plage
  ci-dessous, que tirait le classement initial ; jusqu'ici +0,0001), émis une fois à l'entrée en vigueur, en incréments sous un calendrier
  progressif. C'est une **estimation de France Budget** : aucune étude publiée ne chiffre une baisse uniforme de
  cotisations salariales (les études de redistribution laissent de côté les cotisations contributives). Méthode :
  effet statique de premier ordre d'un gain réparti comme une cotisation proportionnelle au salaire,
  ΔGini ≈ s × (C − G) / (1 + s), par quintiles de niveau de vie (Insee, *France, portrait social* 2025 : cotisations
  famille comme substitut et niveau de vie par quintile ; masse : CCSS octobre 2026) ; plage +0,00006 à +0,0001 par
  Md€, haut de la plage retenu ; incertitude d'un facteur 2 environ. Domaine : une baisse uniforme de quelques
  points, effet statique seul ; une baisse ciblée (heures supplémentaires, Insee 2020) a l'effet inverse. Au
  maximum, la suppression totale émet ≈ +0,0075 (lot 4). Par Md€ rendu aux ménages, la baisse de cotisations émet
  donc +0,0000541 de Gini, contre −0,000521 pour les prestations de solidarité (un Md€ versé en plus ; lot 4). **Corrigé avant publication** (décision du mainteneur du 12/11/2026) : la première
  version émettait +0,0027 par point de 6 Md€ (≈ +0,00045 par Md€, +0,062 au maximum), attribué à une source
  introuvable, quatre à sept fois au-dessus de cette estimation, et la note « Inégalités » saturait au-delà
  d'environ 15 points.
- **TVA, assiette du taux normal** (corrigée au lot 3, équation) : un point du curseur `tva_rate` vaut le
  rendement net du seul taux de 20 %, 7,5 Md€ au PIB 2025 (DG Trésor, Trésor-Éco n° 371, septembre 2025, p. 4,
  tableau 2 ; net = après la TVA payée par les administrations sur leurs propres achats, que le moteur, qui compte le
  solde de toutes les administrations, ne fait pas varier ; point calé sur les recettes encaissées, note 5), en part
  du PIB de l'année. Jusqu'au lot 3 : 0,53 × PIB × 0,9 = 14,24 Md€ par point, toute la consommation des ménages,
  taux réduits compris, plus que le point brut de tous les taux (13,7) : l'effet d'un point était surestimé de 90 %.
  Les élasticités de l'assiette (−0,2 en hausse, −0,1 en baisse), la majoration en chômage élevé et le coude au-delà
  de 22 % sont inchangés (conventions du moteur, sans source écrite ; le chiffrage du Trésor est statique). Une
  hausse de tous les taux s'encode désormais avec `tva_rate` (taux normal) et `tva_ciblee` pour les taux réduits
  (0,4 + 2,0 + 1,6 = 4,0 Md€ net par point, même tableau). Aucun scénario publié ne bouge (taux normal à 20 % partout,
  `tva_ciblee` nul). Pour un visiteur (budget voté, mode cadre, 2032) : +1 point améliore le déficit de 0,22 point
  de PIB et baisse la dette de 0,68 point (0,43 et 1,32 avant). Les coefficients par Md€ de `tva_ciblee` ne changent
  pas : leur recette de référence est figée (point suivant).
- **TVA ciblée, coefficients par Md€** (lot 3) : l'effet sur la compétitivité (et sur le Gini, nul depuis le lot 4)
  d'un Md€ de `fiscalite_indirecte.tva_ciblee` est la règle de `tva_rate` pour +2 points rapportée à une recette de référence
  figée, celle que rendait la fonction du taux normal à +2 points en v0.8.1 (28,42 Md€ au PIB 2025, même calcul,
  valeurs identiques au bit). Ces coefficients ne lisent plus la fonction du taux normal : corriger le rendement
  d'un point du taux normal ne change pas l'effet par Md€ d'un autre levier. Leur révision relève d'une passe
  dédiée (`tests/test_tva_ciblee_coefficients.py`).

### Impôts à taux avec comportement

#### Impôts à taux : règles communes

- **Un taux suit son assiette.** L'assiette est sourcée à une année (2025 ; 2026 pour la taxe
  sur les transactions financières, première année pleine au taux de 0,4 %) et suit le PIB
  nominal depuis cette année : la recette ne dépend pas de l'année où le programme commence.
  Un montant en Md€ reste constant en euros courants (règle commune de la release). La règle
  vaut aussi, depuis le lot 3, pour le curseur « Fiscalité du patrimoine » (un pourcentage des
  recettes de l'IFI, des droits de succession et de donation et de la taxe foncière), pour l'IFI
  que remplace l'ISF et pour la recette de l'ISF elle-même (même année source que l'IFI qu'il
  remplace) ; avant, le bloc restait figé en euros de l'année source (sa part dans le PIB
  baissait d'environ 10 % sur le mandat), et la recette de l'ISF aussi. Leurs effets ponctuels sur le Gini et la compétitivité
  sont comptés hors indice, comme ceux des autres impôts à taux. Bases 2025 (Insee, comptes nationaux
  annuels publiés le 29/05/2026, tableau 3.217 « Principaux impôts par catégorie ») : IFI 2,714 Md€ (autres
  impôts courants, D59), droits de succession et de donation 21,052 (impôts en capital, D91 ; changement de périmètre, arbitrage du mainteneur :
  jusqu'ici le curseur ne comptait que les successions, 16,070), taxe foncière 44,179 (impôts divers sur la
  production, D292 ; dont 27,015 payés par les ménages), 67,945 Md€ au total ; jusqu'au lot 3, 2 + 15 + 36 =
  53 Md€ (« DGFiP 2024 », référence non retrouvée).
- **Un montant annoncé est un rendement net.** Quand une source donne un montant sans taux,
  le curseur en Md€ (`rendement_*`) remplace le calcul : ni taux, ni réaction, ni assiette
  ne s'y appliquent, et les paramètres de taux fournis en même temps sont ignorés (refus en
  mode strict, correction signalée sinon). Une mesure que la source écrit en taux s'encode en
  taux, jamais en montant (règle d'encodage). L'impôt plancher n'a pas de curseur en Md€ :
  toutes ses sources l'écrivent en taux.
- **La réaction des contribuables ne contient que leur réaction.** Chaque paramètre de
  comportement (évitement, élasticité, érosion) réduit la recette de l'impôt concerné, et
  rien d'autre : il ne lit ni la croissance, ni l'emploi, ni l'inflation, ni un autre curseur
  (hors des deux lectures déclarées : l'ISF pour l'impôt plancher, le taux d'IS pour les
  bénéfices récupérés). Les effets sur l'activité, l'emploi et les autres recettes sont ceux
  que le moteur calcule déjà à partir de la recette (multiplicateur fiscal, compétitivité) :
  les compter aussi dans le paramètre serait un double compte. Vérifié par test : un
  évitement e au taux τ donne exactement les mêmes résultats, sur toutes les grandeurs, qu'un
  impôt sans réaction au taux τ × (1 − e).
- **Effets ponctuels.** Gini et compétitivité bougent une fois, l'année d'entrée en vigueur,
  par la constante du moteur multipliée par la recette d'année pleine, hors assiette et
  montée en charge ; sous un calendrier progressif, par incréments dont la somme vaut l'effet
  du palier ; un curseur ramené à son neutre rend son effet.
- **Aucun effet direct sur le chômage** : comme tout prélèvement, la recette passe par le
  multiplicateur fiscal (classe « recettes »).

#### `impot_plancher_patrimoine`

- **Calcul** : recette = (1 − évitement) × R_REF × (taux / 2 %) × imputation de l'ISF ×
  indice d'assiette (PIB de l'année / PIB 2025) × phasage (0,5 l'année de mise en place,
  1 ensuite, comme la collecte de l'ISF). `R_REF = 20 Md€` : rendement sans comportement d'un
  taux de 2 % au-delà de 100 M€, « 20 milliards d'euros, avec une marge d'erreur de 5 »
  (Sénat, rapport n° 689, 2025) ; l'assiette statique implicite est donc 1 000 Md€ en 2025
  [CALCUL].
- **Impôts déjà payés** : la proposition de loi déduit l'IR, l'IFI, la CSG, la CRDS et la
  contribution exceptionnelle sur les hauts revenus, et le rendement de référence porte sur ce
  texte ; seul l'ISF, absent du droit, est imputé par le moteur :
  `imputation = max(0 ; 1 − intensité de l'ISF × 1 % / taux)`. Un ISF complet (taux de 1 %)
  et un plancher à 1 % ne rapportent rien de plus que l'ISF. L'IS des sociétés détenues n'est
  pas imputé (le texte ne l'impute pas).
- **Évitement** (`evitement`) : part de la recette mécanique perdue par l'exil,
  l'optimisation, la sous-évaluation et la moindre accumulation des seuls contribuables
  visés. Points d'appui publiés pour la seule réaction des contribuables visés : 15 % (Saez
  et Zucman, 2019, contrôle fort, États-Unis), 20 % (Zucman, 2024, scénario bas), 54 % (marge
  intensive, Danemark, Jakobsen et al.), soit une fourchette de 15 % à 55 % environ, confiance
  faible (assiette très concentrée, biens professionnels inclus, aucune estimation pour un
  impôt plancher différentiel). Valeur par défaut : **35 %**, milieu de cette fourchette
  (constante unique du moteur `EVITEMENT_PLANCHER_DEFAUT`, dérivée des deux bornes, lue au
  registre comme neutre) ; à 2 % et au PIB 2025, le rendement vaut ≈ 13 Md€ au lieu de 20 Md€
  sans réaction [CALCUL]. Aucun chiffre non publié n'est utilisé.
- **Canaux** : prélèvement direct des ménages (comme l'ISF). Gini (lot 4, corrigé avec l'ISF) :
  coefficient de l'IFI de l'INSEE, −0,000444 par Md€ de recette d'année pleine (jusqu'ici la règle
  effective de l'ISF, le quart de sa règle affichée). Compétitivité : règle **effective** de l'ISF par
  Md€ de recette d'année pleine (le phasage entre deux fois dans la compétitivité de l'ISF ; hors du
  périmètre du lot 4). Comme pour l'ISF, la perte de compétitivité suit la recette
  perçue : elle est plus faible quand l'évitement est fort (indicateur seul, sans effet sur
  le budget).
- **Avis** : si un impôt que le plancher déduit est relevé en même temps (revenus du capital
  au-dessus du droit voté ; CSG, tranche supérieure de l'IR, fiscalité du patrimoine (IFI) ou
  impôt sur le revenu ciblé au-dessus du droit en vigueur),
  le résultat porte l'avis « Impôts déductibles de l'impôt plancher relevés en même temps : la
  recette du plancher est surestimée, au plus de la part de ces hausses payée par les foyers
  concernés (non chiffrable faute de répartition publiée). » Aucun calcul : la répartition par
  foyer n'est pas publiée.

#### `fiscalite_capital`

- **Calcul** (mode taux) : l'assiette sociale est **scindée**. La part soumise au prélèvement
  forfaitaire (A_IR : dividendes, intérêts, plus-values) voit le taux total ; le reste
  (A_PS − A_IR : revenus fonciers, produits de placement hors prélèvement forfaitaire) ne voit
  que les prélèvements sociaux, puisque la part IR du prélèvement forfaitaire ne le frappe pas :
  ΔR = {[τ × f(τ) − 31,4 %] × A_IR + [τ_PS × f_PS − 18,6 %] × (A_PS − A_IR)} × indice
  d'assiette (source 2025), avec τ = τ_IR + τ_PS,
  `f(τ) = max(0,5 ; 1 + élasticité × ((1 − τ) − (1 − 31,4 %)) / (1 − 31,4 %))` et
  `f_PS = max(0,5 ; 1 + élasticité × (18,6 % − τ_PS) / (1 − 31,4 %))` (forme et plancher de
  l'impôt sur le revenu du moteur). Recette aux nouveaux taux sur l'assiette qui réagit, moins
  la recette aux taux d'aujourd'hui : zéro exactement au droit voté. Une variation des seuls
  prélèvements sociaux donne exactement la même recette que la formule à facteur commun de la
  première version de cette fiche (vérifié au bit par test).
  **Corrigé avant publication** (revue adverse de la release) : la première version appliquait
  le facteur f(τ) aux DEUX assiettes ; relever la seule part IR érodait alors toute l'assiette
  sociale (191 Md€, 3,4 fois plus large) : + 7,2 points de part IR faisaient perdre 0,37 Md€ et
  montaient le Gini, et la supprimer ne coûtait que 1,2 Md€ au lieu de 5,4.
- **Assiettes** : part IR, `A_IR = 7,2 / 12,8 % = 56,25 Md€` [CALCUL] (rendement 2022 du
  prélèvement forfaitaire, Sénat, rapport n° 689), prise comme valeur 2025 sans revalorisation
  [INTERPRÉTATION prudente] ; prélèvements sociaux, `A_PS ≈ 191 Md€` [CALCUL] (revenus du
  patrimoine ≈ 81 et produits de placement ≈ 110 Md€, Commission des comptes de la Sécurité
  sociale, octobre 2026 ; Voies et moyens 2027) : un point de prélèvements sociaux rapporte
  ≈ 1,9 Md€ avant comportement [CALCUL].
- **Élasticité** (défaut 0,9) : en 2018, le taux marginal supérieur sur les dividendes passe
  de 60,1 % à 53,3 % et les dividendes versés augmentent de 15,3 % du fait de la réforme
  (Institut des politiques publiques, note n° 46, 2019) : ln(1,153) / ln(0,467 / 0,399) ≈ 0,9
  [CALCUL]. Mesure micro (dividendes déclarés et versés, revenus des autres catégories
  inchangés) : réaction des contribuables visés, sans effet macro. Ce n'est pas un majorant :
  après la hausse de 2013, les dividendes déclarés par les ménages concernés avaient baissé de
  40 % (même note). La même élasticité s'applique à chaque assiette, chacune sur le taux qui
  la frappe [INTERPRÉTATION] ; l'assiette sociale du prélèvement forfaitaire est prise égale à
  A_IR (valeur 2022) [INTERPRÉTATION].
- **Point de retournement (documenté et testé)** : au défaut, la recette de la part IR culmine
  quand le taux total atteint τ* = 31,4 % / 2 + (1 − 31,4 %) / (2 × 0,9) ≈ 53,8 % [CALCUL],
  soit une part IR d'environ 35,2 % (+ 3,7 Md€ au PIB 2025). C'est dans la fourchette publiée du
  taux de Laffer des revenus du capital en France : ≈ 57 % sans la réaction croisée des revenus
  du travail, ≈ 43 % avec (Lefebvre, Lehmann et Sicsic, « Estimating the Laffer tax rate on
  capital income: cross-base responses matter! », *Scandinavian Journal of Economics* 127(2),
  2025, p. 460-489, DOI 10.1111/sjoe.12578 ; réformes françaises de 2008 à 2017). Le moteur ne
  modélise pas la réaction croisée des revenus du travail. Au PIB 2025 [CALCUL] : part IR à 20 %,
  + 2,0 Md€ (+ 4,05 sans réaction) ; à 30 %, + 3,5 ; à 45 % (borne), + 3,0 ; suppression (0 %),
  − 5,4. La part sociale croît sur tout son domaine (+ 1,8 Md€ à 20 %).
- **Au-delà du sommet, le plancher** (limite dite, préexistante ; contre-vérification m9) : le
  facteur f ne descend pas sous 0,5 ; quand le plancher mord (forte élasticité, ou prélèvements
  sociaux déjà hauts), l'assiette ne baisse plus et la recette REMONTE avec le taux au lieu de
  continuer à décroître. À une élasticité de 2, passer la part IR de 30 % à 45 % fait aller la
  recette de − 4,0 à + 0,2 Md€ ; à l'élasticité par défaut (0,9), cela n'arrive que si les
  prélèvements sociaux sont portés à 25 % ou plus. Le plancher est celui de l'impôt sur le revenu
  du moteur (une assiette ne disparaît jamais plus qu'à moitié) ; au-delà du point de retournement,
  la recette n'est donc qu'un ordre de grandeur.
- **Mode montant** (`rendement_md`) : rendement annoncé, constant, même Gini et même
  compétitivité par Md€.
- **Canaux** : prélèvement direct des ménages. Gini : coefficient « revenus du capital » du
  lot 4, borne basse sourcée d'une plage publiée (−0,000398 par Md€, IPP, suppression du
  prélèvement forfaitaire unique ; jusqu'à −0,000506, borne arithmétique) ; jusqu'ici la
  règle du levier « Fiscalité du patrimoine » (−0,001). Compétitivité : règle du levier
  « Fiscalité du patrimoine » par Md€ (−0,0002), plutôt que celle de la tranche
  supérieure de l'IR, l'assiette des revenus du capital étant bien plus large que la tranche
  à 45 %. Assiettes disjointes de la tranche supérieure de l'IR ; la part sociale s'ajoute à
  une variation générale de la CSG (deux écarts distincts, vérifié par test dans les deux
  sens).

#### `multinationales`

- **Bénéfices récupérés** : ΔR₁ = b × τ_IS / 25 %, constant en euros courants, τ_IS = taux
  d'IS du programme (curseur IS, après ses bornes ; 25 % s'il n'est pas modifié). Borne haute
  provisoire 12,6 Md€ = 21 % de l'impôt sur les sociétés perdu par transfert de bénéfices
  (Tørsløv, Wier et Zucman, 2023, ligne France) × 60 Md€ d'IS net [CALCUL ; À SOURCER : IS
  net exécuté 2025]. Assiette disjointe de l'IS et de la surtaxe (vérifié par test) : seule la
  lecture du taux d'IS relie les deux curseurs.
- **Taxe sur les services numériques** : ΔR₂ = [τ × max(0 ; 1 − érosion × (τ − 3 %)) − 3 %] ×
  A_TSN × indice d'assiette (source 2025), `A_TSN = 0,902 / 3 % ≈ 30,1 Md€` [CALCUL] (902 M€
  perçus en 2025, Voies et moyens 2027). Érosion : défaut provisoire 1,0, convention
  d'élasticité de l'assiette de l'IS du moteur, faute d'estimation publiée (À SOURCER) ;
  réaction de l'assiette taxée seule (localisation de la facturation). La recette croît en
  taux jusqu'à τ* = (1 + érosion × 3 %) / (2 × érosion) [CALCUL] : au défaut, 51,5 %, hors du
  domaine (+ 0,85 Md€ à 6 % au PIB 2025).
- **Canaux** : aucun effet direct sur les ménages (convention des impôts d'entreprise), Gini
  nul ; compétitivité : règle de l'IS par Md€ pour les bénéfices, des impôts de production pour
  la TSN (assise sur le chiffre d'affaires). Multiplicateur fiscal (impôt payé par une
  entreprise établie en France).

#### `operations_financieres`

- **Taxe sur les transactions financières** : ΔR₁ = τ × V(τ) − 0,4 % × V_REF, × indice
  d'assiette (source 2026), V(τ) = V_REF × max(0 ; 1 − élasticité × (τ − 0,4 %) / 0,1 point),
  `V_REF = 2,888 / 0,4 % ≈ 722 Md€` [CALCUL] (2 888 M€ en 2026, Voies et moyens 2027). Défaut
  de l'élasticité : 5 % de volume par 0,1 point [CALCUL] (− 10 % pour 0,2 point en 2012,
  Colliard et Hoffmann, *Journal of Finance*, 2017 ; titres taxés contre non taxés : aucune
  composante macro). La recette croît jusqu'à τ* = (0,1 point + élasticité × 0,4 %) / (2 ×
  élasticité) [CALCUL] : au défaut, 1,2 %, hors du domaine (+ 0,54 Md€ à 0,5 % ; + 2,17 Md€ à
  1 %, au volume 2026). Le volume n'est jamais négatif.
- **Rachats d'actions** : recette en ÉCART à la taxe de 8 % en vigueur depuis la loi de
  finances 2025 (≈ 0,2 Md€ par an, déjà dans la référence) ; borne basse − 0,2 = suppression.
  **Crypto-actifs** : recette nouvelle (aucune taxe en vigueur ; assiette À SOURCER).
- **Canaux** : aucun effet direct sur les ménages, Gini nul ; compétitivité : règle de l'IS
  exceptionnel par Md€.

#### Hypothèses de comportement des impôts à taux

| Impôt | Paramètre | Défaut | Source | Ce qu'il contient | Réglable |
|---|---|---|---|---|---|
| Impôt plancher | `evitement` | 35 % (milieu de la fourchette) | fourchette publiée 15 % à 55 % (Saez et Zucman 2019 ; Zucman 2024 ; Jakobsen et al.) | exil, optimisation, sous-évaluation, moindre accumulation des contribuables visés | oui |
| Revenus du capital | `elasticite` | 0,9 | IPP, note n° 46 (2019), réforme de 2018 ; sommet de recette qui en résulte (taux total ≈ 54 %) dans la fourchette de Lefebvre, Lehmann et Sicsic (2025), 43 à 57 % | dividendes déclarés et versés (assiette du prélèvement forfaitaire au taux total, reste de l'assiette sociale aux seuls prélèvements sociaux) | oui |
| Taxe sur les services numériques | `erosion_tsn` | 1,0 (provisoire) | aucune estimation publiée ; convention de l'IS du moteur | localisation de la facturation | oui |
| Taxe sur les transactions financières | `elasticite_volume` | 5 % par 0,1 point | Colliard et Hoffmann (2017) | volumes échangés | oui |
| ISF | évasion | 15 % | convention de Saez et Zucman (2019), impôt américain à assiette complète ; pas une mesure française | patrimoine caché | non (passe dédiée) |
| Tranche supérieure de l'IR | élasticité du revenu imposable | 0,25 | Lehmann et Sicsic (IPP, 2020), 0,20 à 0,30 (source citée dans le code, non revérifiée par la release) | revenu déclaré | non (passe dédiée) |
| Impôt sur les sociétés (taux) | élasticité de l'assiette | − 1,0 en hausse, − 0,6 en baisse | convention du moteur, sans mesure française ; repère cité dans le code : DG Trésor 2017 (33 → 25 % = − 10 à − 12 Md€ par an) | localisation des bénéfices | non (passe dédiée) |
| TVA (taux normal) | élasticité de la consommation taxée | − 0,1 en baisse, − 0,2 en hausse (× 1,2 si chômage > 10 %) | convention du moteur, sans source écrite | consommation | non (passe dédiée) |

Les hypothèses des impôts existants deviennent visibles dans cette release ; elles deviendront
réglables toutes ensemble dans une passe dédiée (rendre réglable un seul impôt donnerait une
prise sur les seules mesures d'un camp).

---

## Multiplicateurs et Mecanismes Macro

### Architecture des Multiplicateurs (v3.0)

**Impulsions par levier et par flux (v0.6.7, audit externe Codex 10/2026)** : l'effet keynésien de l'année est la somme, sur les leviers, les flux et les âges, de

```
effet(t) = Σ_levier Σ_flux Σ_âge  −k(flux, sens) × Δe(t − âge) × profil_levier(âge)
Δe(t)    = e(t) − e(t−1),  e = flux du levier / PIB nominal de son année   (e > 0 = consolidation)
```

Chaque flux d'un levier est multiplié séparément : ses recettes au canal fiscal, ses dépenses au canal investissement (éducation, recherche, transition écologique) ou transferts/générique, et, depuis le lot 5b, la part de sa dépense émise au canal ménages des rémunérations publiques (point d'indice, revalorisation des enseignants en place) au traitement des transferts, et, depuis le lot 5c, la moitié d'une variation de dotation aux collectivités au flux de l'investissement local. Le sens (consolidation ou expansion) est celui du NIVEAU du flux par rapport au statu quo, pas celui de sa variation : retirer une hausse d'impôts porte le multiplicateur d'une hausse, donc la somme des effets d'IMPULSION d'une mesure retirée revient exactement à zéro et ce cumul ne dépend que du niveau atteint (un flux qui change de signe dans l'année est scindé en zéro). **Ce n'est pas le niveau du PIB** (texte corrigé en v0.6.7, lot 3b ; l'équation est inchangée) : le rappel vers le potentiel « rembourse » pendant la mesure l'écart qu'elle ouvre, et au retrait le PIB passe SOUS la référence avant d'y revenir lentement — une relance temporaire de +1 % du PIB de transferts pendant 4 ans porte le PIB à +0,8 % au pic, puis à −0,46 % en 2033-2034 et encore −0,35 % en 2039, dont environ 0,2 pt de traînée de la dette accumulée (−0,15 % sans elle). Une mesure temporaire n'est donc pas neutre en niveau une fois retirée : elle se paie en partie après coup. Exceptions : le SMIC et la fraude fiscale ont un coefficient calibré sur leur effet NET, appliqué à leur solde (`FiscalMultipliers.MESURES_MULTIPLICATEUR_NET`). L'impulsion du budget de l'année agit dès cette année : `e(t)` est l'effort du budget de t, évalué hors de son effet propre (lot 6 ; jusque-là, l'impulsion était lue dans les impacts de t−1, avec un an de retard : § « Calendrier de l'impulsion »).

**Ce que cela corrige (v0.6.6, deux erreurs de calcul)** : (1) une impulsion n'était stockée qu'au changement du hash des mesures — constant pendant une simulation —, donc UNE impulsion par scénario, égale au NIVEAU de la première année non nulle : la montée en charge n'était jamais multipliée (fraude fiscale : 0,10 % du PIB multiplié, 0,47 % atteint en 2030), et les résidus s'arrêtaient net dès que l'effort courant repassait sous 0,1 % du PIB ; (2) un seul multiplicateur par scénario, moyenne des multiplicateurs SIGNÉS pondérée par l'effort BRUT puis appliquée à l'effort NET : un programme équilibré n'avait aucun effet keynésien, et une consolidation nette pouvait être comptée comme une relance (banc de l'auditeur, 40 Md EUR d'investissement + 20/40/50 Md EUR d'impôts : +0,253 / 0 / +0,060 pt au lieu de +0,420 / +0,120 / −0,030). Contrat verrouillé par `tests/test_impulsions_v067.py` (somme signée, additivité d'une montée en charge, résidus après retrait, franchissement de zéro, chaque variation multipliée une fois en simulation complète).

**Somme analytique `k × Σ profil` (définition ; valeurs de la v0.6.6)** : le coefficient d'impact multiplié par la somme de son profil donne l'effet de niveau qu'aurait une impulsion permanente si aucune autre équation ne réagissait. Avec les coefficients de la v0.6.6, cette somme analytique valait 2,38 pour l'investissement (1,2 × 1,98 ; inchangée jusqu'au lot 6, puis 2,59 avec k = 1,31 et le même profil, et 2,18 avec le profil calé sur le FMI, somme 1,6653), 1,0 pour une hausse d'impôts (0,5 × 2,0), 0,89 pour les transferts (0,5 × 1,77), 1,09 à 1,20 pour une coupe générique, 0,70 pour une baisse d'impôts ; la v0.6.6 ne les exposait presque jamais (une seule impulsion par scénario, plafonnée), et depuis la v0.6.7 les impulsions portent tout le canal keynésien. **Ce n'est pas l'effet effectif** : dans le moteur complet, le rappel vers le potentiel (λ = 0,2), Phillips, Okun et la dette réagissent ; l'investissement, à k = 1,31 depuis le lot 6 (1,2 jusque-là) et avec le profil calé sur le FMI, produit pour la demande seule un effet de niveau de 1,28 % du PIB à 4 ans et de 0,29 % à 10 ans ; avec le canal d'offre d'un levier de capital public, le total suit le tableau du FMI (1,539 à 4 ans ; § « Calendrier de l'impulsion »). Historique de la demande seule : 1,41 et 0,40 au lot 6 avant le calage du profil ; 1,29 et 0,33 au même lot à k = 1,2 ; 1,41 et 0,37 au lot 1 ; 1,41 et 0,40 jusqu'à v0.8.1. Et non 2,18. Les valeurs courantes, calées sur cet effet mesuré, sont celles du tableau « Recalibrage central des familles » ci-dessous (constantes `MULT_*` et `MULT_CIBLE_NIVEAU_4ANS`, `budget_simulator/constants.py`).

### Table des Multiplicateurs de Base

| Type | Valeur | Source | Ancien |
|------|--------|--------|--------|
| Consolidation fiscale (anticipee) | **-0,674** | v0.6.7 : calé « central » (tableau ci-dessous) | -0,50 (v0.6.6), -0,92 (v2.0) ; lot 6 : -0,615 (calendrier de l'impulsion, recalage) |
| Consolidation depenses generique | **-0,811** (v0.6.7, calé « central », sans atténuation « confiance » ; -0,81 ÷ 1,10 avant, -0,60 en v0.6.6) | Ramey 2019 (« 0,6 to 1 », milieu) ; Gechert & Rannenberg 0,4-0,7 | -0,40 (v3.0-v5.1, sous le consensus) ; lot 6 : -0,74 (calendrier de l'impulsion, recalage) |
| Coupe d'investissement public | **-1,31** | SYMETRIQUE de la hausse (convention du mainteneur : pas d'asymetrie de signe retenue ; Mesange : multiplicateurs identiques a la hausse et a la baisse ; FMI WEO oct. 2010 ch. 3 : coupes d'investissement au haut de l'echelle de cout) | canal ABSENT v5.1 (coupe traitee a -0,40 : audit 08/2026, constat 2) ; lot 6 : -1,20 (calendrier de l'impulsion, recalage) |
| Expansion investissement | **1,31** | IMF 0,9-1,5, OFCE 1,0-1,3 | 1,0 (v2.0) ; lot 6 : 1,20 (calendrier de l'impulsion, recalage) |
| Dotation aux collectivites, part investie (la moitie d'une variation, hausse ou baisse) | **1,31** | lot 5c, arbitrage du mainteneur : traitement du curseur d'investissement local (coefficient, profil, effet d'offre en mode cadre) ; Caisse des Depots 2015, Cour des comptes 2018 ; limites : encadre du lot 5c | 0,74 (depense courante) |
| Expansion depense courante | **0,811** | lot 5 : même coefficient que la coupe de dépense courante (convention du mainteneur : pas d'asymétrie de signe retenue, même instrument, même coefficient ; limite : encadré du lot 5) | 0,688 (coefficient des transferts, jusqu'au lot 5) ; lot 6 : 0,74 (calendrier de l'impulsion, recalage) |
| Expansion transferts | **0,785** | v0.6.7 : calé « central » ; recalé au lot 1 (release de paramètres) | 0,71 (v0.6.7), 0,50 (v0.6.6), 0,80 (v2.0) ; lot 6 : 0,688 (calendrier de l'impulsion, recalage) |
| Remuneration publique a effectifs constants (hausse ou baisse) | **0,785** | lot 5b, arbitrage du mainteneur : traitement des transferts (coefficient et profil) ; niveau encadre par e-mod.fr (OFCE 2017) et QUEST (2010), profil par analogie, limites : encadre du lot 5b | 0,811 (point d'indice, depense courante) ; 1,31 (revalorisation des enseignants, investissement) ; lot 6 : 0,688 avant le recalage |
| Prestations en especes emises hors des leviers de transfert (coupes de prestations du rabot uniforme) | **0,785** | lot 5e : traitement des transferts (coefficient et profil), prestations en especes (SEC 2010, D.62) ; exception : franchises de sante (en nature) ; le SMIC est un levier de transfert | 0,74 (depense courante) |
| Expansion baisses impots | **0,674** | v0.6.7 : même valeur centrale EFFECTIVE que la hausse (0,65 à 4 ans) — aucune asymétrie de signe établie ; = hausse depuis le lot 1 | 0,63 (v0.6.7), 0,455 (v0.6.7 avant symétrie), 0,35 (v0.6.6), 0,40 (v2.0) ; lot 6 : 0,615 (calendrier de l'impulsion, recalage) |
| SMIC : paie publique et baisse des prestations | **0,785** | lot SMIC, arbitrage du mainteneur : traitement des transferts (coefficient et profil) ; postes du Trésor, § SMIC | 0,15 sur le solde du levier, sans source (jusqu'au lot SMIC) |
| SMIC : cotisations des salariés, impôt sur le revenu, allègements des employeurs | **0,674** | lot SMIC : coefficient et profil des impôts (le même en hausse et en baisse) | 0,15 sur le solde du levier |
| Fraude fiscale (enforcement) | **-0,40** | Application loi existante | n/a |

**Recalibrage « central » des familles (v0.6.7, arbitrage du mainteneur du 07/10/2026)** — règle : chaque
famille est calée sur la valeur CENTRALE de la littérature, en effet de NIVEAU sur le PIB réel 4 ans
après le début d'une impulsion PERMANENTE de 1 % du PIB (définition du FMI), MESURÉ DANS LE MOTEUR
COMPLET (rappel vers le potentiel λ = 0,2, Phillips, Okun, dette) et non en `k × Σ profil`. Une
famille déjà centrale ne bouge pas. Constantes `MULT_*` et `MULT_CIBLE_NIVEAU_4ANS` (constants.py),
test-propriété `tests/test_multiplicateurs_centraux_v067.py`.

| Famille (profil) | Cible centrale, niveau à 4 ans | Source vérifiée | Moteur avant (k v0.6.6) | Moteur après (v0.6.7) | 10 ans, v0.6.7 (niveau / cumulé Ramey) | Moteur actuel : 4 ans (k) ; 10 ans (niveau / cumulé) |
|---|---|---|---|---|---|---|
| Investissement public (INVEST) | 1,5 ; depuis le lot 6, tout le chemin du tableau 3.4 (0,457 à 1,539), demande et offre d'un levier de capital public | FMI WEO oct. 2014 ch. 3 : « +0,4 % la même année, +1,5 % quatre ans après » ; Gechert 2015 : dépenses ≈ 1, investissement ≈ +0,5 — borne haute de lecture : Banque mondiale, GEP juin 2024 ch. 3, niveau ≈ 1,1 à 5 ans (≤ 1,6), économies émergentes et en développement | 1,41 (k = 1,2) | **inchangé** (−6 %) | 0,40 / 0,92 | 1,28 (k = 1,31) ; 0,29 / 0,82 |
| Coupe de dépenses générique (TAXES) | 0,8 | Ramey 2019 JEP : « 0.6 to 1 for spending multipliers » (milieu) ; Gechert ≈ 1 | 0,58 (k = 0,60 ÷ 1,10) | 0,80 (k = 0,74, sans facteur « confiance » ; 0,79 à k = 0,81 ÷ 1,10) | 0,15 / 0,56 | 0,79 (k = 0,811) ; 0,11 / 0,58 |
| Hausse de dépense courante (TAXES) | 0,8 | la même que la coupe : même instrument (lot 5) | non mesurée (coefficient des transferts) | non mesurée (coefficient des transferts ; 0,74 au lot 1, k = 0,688) | — | 0,79 (k = 0,811) ; 0,11 / 0,58 |
| Transferts (TRANSFERS) | 0,65 | Gechert 2015 : « 0.3 to 0.4 units » sous les dépenses (≈ 1) | 0,44 (k = 0,50) | 0,65 (k = 0,71) | 0,01 / 0,43 | 0,65 (k = 0,785) ; 0,04 / 0,48 |
| Rémunération publique à effectifs constants (TRANSFERS) | 0,65 | la même que les transferts (lot 5b) : entre QUEST 2010 (effet sur le PIB privé de 0,3, choc d'un an) et e-mod.fr 2017 (« proche de 0,9 au bout de trois ans ») | non mesurée | non mesurée (au lot 5 : 0,79 pour le point d'indice, 1,41 pour la revalorisation des enseignants) | — | 0,65 (k = 0,785) ; 0,04 / 0,48 |
| Hausse d'impôts (TAXES) | 0,65 | Gechert 2015 (même écart) ; Ramey 2019 « −2 to −3 » (États-Unis, chocs narratifs : non retenu comme central pour la France) | 0,52 (k = 0,50) | 0,65 (k = 0,615) | 0,05 / 0,44 | 0,65 (k = 0,674) ; 0,01 / 0,45 |
| Baisse d'impôts (TAXES) | 0,65 | la même que la hausse : aucune asymétrie de signe établie (paragraphe ci-dessous) ; jusqu'au 07/10/2026, « asymétrie hausse/baisse du moteur conservée (0,35/0,50) », sans source | 0,33 (k = 0,35) | 0,65 (k = 0,63 ; 0,45 à k = 0,455 avant symétrie) | 0,02 / 0,43 | 0,65 (k = 0,674) ; 0,03 / 0,46 |

> **Coefficient des transferts recalé (lot 1, release de paramètres, 15/11/2026, non publiée).** `MULT_TRANSFERTS`
> 0,71 → **0,688**. Le 0,71 avait été calé (v0.6.7) sur une relance 100 % transferts SOUS éviction ; l'éviction
> retirée (équation 3 du lot), il donnait 0,672 à 4 ans au lieu de la cible de 0,65 (Gechert 2015), +3,4 %.
> Bissection sur le banc de `tests/test_multiplicateurs_centraux_v067.py`, moteur sans les trois mécanismes
> retirés : k = 0,6882 → 0,688 ; hausse de transferts 0,650, coupe 0,650 à 4 ans ; tolérance du banc resserrée
> à 1 %. Un calage fait avant le retrait du terme d'effort de l'inflation (éviction seule neutralisée) donnait
> 0,684 ; sur l'état sans les trois mécanismes, 0,684 ne donne que 0,646. Aucun autre paramètre ne bouge (la pente de Phillips
> n'est pas touchée). Ce qui bouge (mode cadre 2028, dix scénarios publiés, par rapport à l'équation 3) : dette
> 2032 de −0,06 à +0,39 point, d'autant plus que les hausses de transferts ou de dépense courante du programme
> sont fortes (chacune vaut désormais 0,65 à 4 ans, au lieu de 0,67) ; deux programmes s'échangent les 2ᵉ et 3ᵉ
> rangs de croissance moyenne 2028-2032 (1,334 contre 1,336 %) ; dette, déficit et Gini : aucun rang ne change. **Portée déclarée, traitée au lot 5**
> (encadré suivant) : en expansion, `get_multiplier` (`simulator.py`) donnait ce coefficient à TOUTE dépense hors
> investissement (part « transferts » = dépense − investissement), dépense courante comprise, alors qu'une COUPE
> de dépense courante prend `MULT_COUPE_DEPENSES` : une asymétrie de signe pour la dépense courante (0,74 en hausse,
> 0,79 en baisse à 4 ans au banc), antérieure au lot 1.

> **Dépense courante symétrique en signe (lot 5, équation, 15/11/2026, non publiée).** Convention du mainteneur
> (v0.6.7, « pas prouvé = valeur centrale ») : pas d'asymétrie de signe retenue — même instrument, même
> coefficient, en hausse comme en baisse. La méta-analyse citée pour les valeurs (Gechert 2015) classe les
> multiplicateurs par instrument ; elle ne teste pas le signe : l'égalité des deux sens est une convention, pas un
> résultat de cette source. Elle valait pour les transferts, les impôts et
> l'investissement, pas pour la dépense courante, c'est-à-dire toute dépense qui n'est ni de l'investissement
> productif ni un transfert : défense, dotations des collectivités, postes et point d'indice, réforme de l'État,
> crédits des ministères, moyens de soins, santé, subventions aux grandes entreprises, aide médicale de l'État et
> intégration. Sa baisse prenait `MULT_COUPE_DEPENSES` ; sa hausse, `MULT_TRANSFERTS`, parce que la branche
> « expansion » de `get_multiplier` versait toute dépense hors investissement dans la case des transferts. Pour un
> point de PIB permanent (banc ci-dessus) : 0,74 point de PIB à 4 ans en hausse, 0,79 en baisse. Désormais la
> hausse prend le coefficient de la baisse, `MULT_COUPE_DEPENSES` (k = 0,74, valeur inchangée) : 0,79 dans les deux
> sens. L'autre voie, abaisser la coupe au niveau des transferts, a été écartée par le mainteneur. **Limite
> déclarée** : une étude par signe (Barnichon, Debortoli & Matthes, *Review of Economic Studies* 89(1), 2022,
> « Understanding the Size of the Government Spending Multiplier: It's in the Sign ») trouve, sur données
> américaines, un multiplicateur d'une baisse de dépense au-dessus de 1 et celui d'une hausse nettement en
> dessous de 1 : une asymétrie que le moteur ne représente pas. L'ancien écart (0,79 contre 0,74) ne la
> représentait pas non plus : il venait d'un trou de classement, pour la seule dépense courante. La question
> d'une asymétrie de signe sourcée, pour toutes les familles, relève d'une instruction séparée. Aucun
> coefficient ne change, et un programme sans hausse de dépense courante est identique au bit. Le coefficient des
> transferts, calé sur un banc de transferts, ne bouge pas (hausse et coupe à 0,650). La fourchette ×0,75 / ×1,25
> des fiches multiplie la même constante dans les deux sens. Test : `tests/test_symetrie_depense_courante.py`
> (leviers : chaque levier dont une hausse est de la dépense courante, dérivé du registre des paramètres et non
> d'une liste — défense, dotations des collectivités, crédits des ministères et moyens de soins, postes et point
> d'indice, réforme de l'État, aide médicale de l'État et intégration, santé, subventions —, plus un levier
> synthétique ; chaque levier de dépense du registre rangé dans une famille gardée par un test ; hausse et baisse
> permanentes d'un point de PIB en miroir sur le PIB réel à 1 % près, à 1, 2, 3, 4, 5 et 6 ans, dans cinq états :
> banc historique, mode cadre 2028, dette à 160 % du PIB, écarts de production à −3 % et à +1,5 % ; aucune
> non-linéarité neutralisée ; rouge avant : rapport de 1,05 à 1,10, vert après : écart au plus 0,7 % ; la première
> année, même miroir à 0,1 % près pour une dette à 180 % ou à 85 % du PIB et pour un choc de 2 points de PIB ; même
> miroir par le curseur de défense ; coefficient lu par les seules hausses de dépense courante), et famille
> « hausse de dépense courante » du banc des multiplicateurs, à la cible et à la tolérance de la coupe. Le miroir
> porte sur le PIB, pas sur la dette (limite 8 de « Limites et Precautions »). **Ce qui bouge** : en
> mode cadre, le droit en vigueur de 2026-2027 relève la défense au-dessus du défaut du moteur (budget 2026
> voté) ; toute simulation en mode cadre porte donc une hausse de dépense courante, la référence sans programme
> comprise, et les dix programmes publiés en portent une dans les deux modes (la défense à 58 Md€ au moins). Mode
> cadre 2028, dix scénarios publiés, par rapport au lot 1 : dette 2032 de −0,61 à −0,09 point (−0,09 environ
> pour les quatre dont la seule hausse de dépense courante est la défense, autant que la référence sans
> programme), déficit 2032 de +0,01 à +0,12 point, croissance moyenne 2028-2032 au plus +0,023 point, chômage
> 2032 au plus −0,04 point, inflation 2032 au plus +0,03 point ; Gini inchangé à la précision publiée (au plus
> 1e-7, par un levier de coupe dont l'effet sur les inégalités dépend de dépenses qui suivent l'économie), compétitivité
> au plus 0,0003 point d'indice (par deux leviers fiscaux dont l'effet émis suit le PIB). Rangs : deux programmes échangent les 2ᵉ et 3ᵉ rangs de croissance moyenne
> (1,356 contre 1,336 %), deux autres les 5ᵉ et 6ᵉ rangs de chômage 2032 (7,71 contre 7,72 %) ; dette, déficit et
> Gini : aucun rang ne change. **Classements à arbitrer** (soumis au mainteneur ; un changement ferait
> l'objet d'un commit d'équation distinct, avec son test), état au lot 5c :
> - **le point d'indice de la fonction publique** : **traité au lot 5b** (encadré suivant), avec la
>   revalorisation des enseignants en place. Le moteur se contredisait : le revenu des ménages (`engine/rdb.py`)
>   traitait une hausse du point d'indice comme un revenu versé aux agents, à l'égal d'une prestation, et la
>   croissance la rangeait en dépense courante, avec les embauches. L'enjeu mesuré ici (mode cadre 2028, pleine
>   précision), le point d'indice seul au coefficient des transferts, profil inchangé : 0,28 et 0,29 point de
>   dette 2032 pour les deux programmes publiés qui le relèvent (0,52 et 0,53 avec aussi le profil des
>   transferts, la règle retenue au lot 5b) ;
> - **arbitré, classement inchangé, limite déclarée** (arbitrage du mainteneur du 16/11/2026) : les subventions
>   aux entreprises et les transferts en capital aux ménages restent au coefficient de la dépense courante
>   (limite 9 de « Limites et Precautions ») ;
> - **les coupes de prestations en espèces du rabot uniforme** (pensions, allocations chômage, minima sociaux) :
>   **traitées au lot 5e** (encadré du lot 5e) ;
> - **la dotation des collectivités** (un transfert entre administrations) : **traitée au lot 5c** (encadré du lot
>   5c) : la moitié d'une variation est de l'investissement local, coupe du rabot uniforme comprise ;
> - **arbitré, calcul inchangé, limite déclarée** (arbitrage du mainteneur du 16/11/2026) : les indemnités
>   journalières comprises dans le curseur Ondam, des prestations en espèces, restent au coefficient de la dépense
>   courante (limite 11 de « Limites et Precautions »). Les soins de l'Ondam et de l'aide médicale de l'État,
>   prestations en nature, restent de la dépense courante, comme les franchises de l'assurance maladie (canal
>   `prestations` de la santé, exclu du lot 5e) ;
> - **la même dépense de santé avait une dynamique différente selon le levier qui la porte** (préexistant, résolu
>   par l'option du lot 6) : `sante` suivait le profil de persistance de l'investissement
>   (`INVESTMENT_FLOW_MEASURES`), les moyens de soins de `depenses_publiques` celui de la dépense courante. Pour un
>   point de PIB permanent (banc historique), 0,28 contre 0,69 point de PIB la première année, 0,77 contre 0,79 à
>   4 ans avec le profil de l'investissement calé sur le FMI (0,31 contre 0,62 et 0,85 contre 0,79 au lot 5) ;
>   depuis l'option, le même chemin, au bit près.
>
> Le lot 5 rend chaque classe symétrique ; il ne change aucun de ces classements.

> **Rémunérations publiques à effectifs constants au traitement des transferts (lot 5b, équation, 16/11/2026,
> non publiée).** Arbitrage du mainteneur du 16/11/2026 : une hausse (ou une baisse) de rémunération des agents
> publics à effectifs constants est un revenu versé aux agents ; pour la croissance, elle prend le traitement des
> transferts — coefficient `MULT_TRANSFERTS` et profil `DECAY_PROFILE_TRANSFERS` —, dans les deux sens. Elle vaut
> pour le point d'indice (`fonction_publique`, jusqu'ici de la dépense courante : 0,79 point de PIB à 4 ans par
> point de PIB) et pour la revalorisation des enseignants en place (`education.salaires`, jusqu'ici au coefficient
> et au profil de l'investissement productif : 1,41) ; désormais 0,65, comme un transfert. Les effectifs
> (embauches, suppressions, postes d'enseignants) et le reste de chaque levier gardent leur famille et leur
> profil ; aucun coefficient ne change. **Source unique** : le montant reclassé est celui que le levier émet déjà
> au canal ménages `remunerations_publiques` (coût de l'année), le même que lit l'indice de pouvoir d'achat ; il
> forme un flux distinct dans `flux_par_levier` (`engine/growth.py`). **Sources** : en comptabilité nationale, une
> hausse de rémunération à effectifs et structure constants est un effet prix, pas volume (SEC 2010 § 10.44 et
> § 11.35-11.37 ; Eurostat, *Handbook on prices and volume measures in national accounts*, 2016, § 3.11.2) ; le
> modèle Mésange (Bardaji et al., « Le modèle macroéconométrique Mésange : réestimation et nouveautés », document
> de travail Insee G2017/04, p. 106) écrit que la dépense publique « joue de manière indirecte et donc différée
> par d'autres composantes (salaires publics en prix, par exemple si on augmente le point d'indice ; prestations
> sociales en espèces) ». **Niveau, encadré par deux modèles publiés** : le modèle e-mod.fr de l'OFCE (Ducoudré,
> Plane & Sampognaro, *Dépenses publiques : quels enjeux pour le prochain quinquennat ?*, policy brief n° 17,
> avril 2017, p. 15) écrit que « Le multiplicateur est proche de 0,9 au bout de trois ans pour les prestations
> sociales, les transferts sociaux en nature et les salaires publics », sans préciser l'assiette du « point de
> PIB » de rémunérations (coût employeur ou salaire brut) ; le modèle QUEST de la Commission européenne (Roeger &
> in 't Veld, *European Economy Economic Papers* 426, 2010, texte p. 17 imprimée, p. 20 du PDF, et tableau 2) donne
> à une hausse des salaires publics « an additional private sector GDP multiplier of 0.3 », contre 0,20 à 0,53
> pour les transferts généraux du même tableau, soit, d'après ce tableau, 0,55 à 0,74 fois l'effet d'un transfert par
> euro de coût, pour un choc temporaire d'un an sur l'Union européenne. Le coefficient des transferts du moteur
> (0,65 point de PIB à 4 ans) se situe entre les deux, et il s'applique au coût employeur entier : « le même
> effet qu'un transfert du même montant » porte sur le coût employeur brut, dont le revenu net des agents n'est
> qu'une part (`PART_NETTE_REMUNERATIONS_APU`). **Limites déclarées** : (1) les sources décrivent un effet
> différé (Mésange, même page : « Les mécanismes de transmission à l'activité sont donc plus lents » ; e-mod.fr :
> 0,25 la première année) alors que le profil des transferts du moteur est concentré sur les premières années :
> ce profil est repris par analogie, sans source, et l'effet est trop rapide la première année ; (2) le retour
> immédiat des cotisations (employeur et salariales) et de la CSG aux administrations publiques n'est pas
> modélisé à part : il ne passe que par l'élasticité des recettes au PIB (la même année depuis le calendrier du
> lot 6, avec un an de retard avant), et le coût pour le déficit en reste surestimé la première année ; (3) l'effet prix d'une hausse de rémunération sur le PIB en valeur (SEC 2010
> § 10.28 : la production non marchande vaut la somme de ses coûts) est traité au lot 5d, sur le seul PIB publié
> (encadré suivant) ; (4) les études empiriques sur les salaires publics divergent (Bermperoglou,
> Pappa & Vella, *Journal of Economic Dynamics and Control*, 2017 ; Forni, Monteforte & Sessa, *Journal of Public
> Economics*, 2009 ; FMI, document de travail 19/125) et n'ont été lues qu'en résumé. Pour les effectifs, la méta-analyse de
> Gechert (catégorie « emploi public ») et l'OFCE (Creel, Heyer & Plane, *Revue de l'OFCE* n° 116, 2011) ne
> contredisent pas le classement en dépense courante. **Tranché depuis (lot SMIC, § SMIC)** : la hausse du SMIC
> émet aussi une part « agents publics » à ce canal ; elle restait, au lot 5b, dans le solde du SMIC, à son
> coefficient propre. Le SMIC n'a plus de coefficient propre : sa paie publique, poste du Trésor, suit la règle. Test : `tests/test_remunerations_publiques_transferts.py` (émetteurs dérivés du registre des
> paramètres, pas d'une liste ; source unique, chaque année, dans les deux sens et les deux modes ; même
> trajectoire macroéconomique qu'un transfert du même montant, à 1e-9 près, pour chaque émetteur et un émetteur
> synthétique, dans les deux sens et dans cinq états, en montée en charge sur trois ans ; vrais curseurs en miroir
> à 1 % près de 1 à 6 ans ; aucun levier à coefficient propre n'émet ce canal (le SMIC en est sorti) ; source
> unique tenue sous le plafond de 10 % du PIB en mode « reduction ») et famille « rémunération publique » du banc des
> multiplicateurs, à la tolérance des transferts. **Ce qui bouge** (mode cadre 2028, dix scénarios publiés, par
> rapport au lot 5) : les sept programmes qui relèvent le point d'indice ou la revalorisation des enseignants ;
> la référence sans programme et les trois autres sont identiques au bit. Dette 2032 de +0,16 à +0,59 point,
> déficit 2032 de −0,04 à −0,14 point, croissance moyenne 2028-2032 de −0,011 à −0,037 point ; sur la pile
> d'intégration (lots 2 et 6 appliqués, mesuré contre le commit qui le précède) : dette 2032 de +0,09 à +0,59
> point, déficit 2032 de −0,03 à −0,13, croissance moyenne de −0,010 à −0,034 ; Gini inchangé,
> compétitivité au plus 0,0003 point d'indice (un levier fiscal dont l'effet émis suit le PIB). **Décomposition**
> (même mesure) : le coefficient seul, avec le profil d'origine, coûterait 0,29 et 0,28 point de dette 2032 aux
> deux programmes qui relèvent le point d'indice, et de 0,09 à 0,56 point aux six qui revalorisent les
> enseignants ; avec aussi le profil des transferts (ce commit), 0,53 et 0,52 point pour le point d'indice — le
> profil des transferts s'éteint plus vite que celui des impôts —, et de 0,07 à 0,57 point pour les enseignants
> — le profil de l'investissement culmine la deuxième année : selon le calendrier du programme, passer au profil
> des transferts relève ou abaisse l'effet (décomposition mesurée contre le lot 5). Rangs, contre le lot 5 : cinq
> rangs de croissance moyenne changent, deux programmes échangent les 5ᵉ et 6ᵉ rangs de chômage 2032 ; dette,
> déficit et Gini : aucun rang ne change. Rangs sur la pile (sorties du moteur) : en dette 2032, un scénario passe
> du 6ᵉ au 4ᵉ rang et un programme du 4ᵉ au 5ᵉ ; en croissance moyenne, deux rangs changent ; à une décimale, la
> dette et le déficit changent chacun d'un ou deux rangs, la croissance et le chômage d'un.

> **Effet prix des rémunérations publiques sur le PIB en valeur publié (lot 5d, équation, 16/11/2026, non
> publiée).** Pour toute hausse ou baisse de rémunération des agents publics à effectifs constants (canal ménages
> `remunerations_publiques` de tous les leviers : point d'indice, revalorisation des enseignants en place, part «
> agents publics » de la hausse du SMIC), le coût employeur de l'année s'ajoute au PIB en valeur publié, en niveau,
> dans les deux sens : une hausse le relève, un gel relatif ou une baisse l'abaisse. Le montant est ce canal
> (`cout_employeur_des_remunerations`, `engine/growth.py`, source unique : le même que lisent l'impulsion du lot 5b
> et le pouvoir d'achat). L'effet prix est une identité comptable, indépendante du coefficient par lequel la
> croissance prend le levier. Depuis le lot SMIC, la part « agents publics » de la hausse du SMIC est la paie
> publique du Trésor (§ SMIC). Le déflateur publié en est relevé d'autant (PIB publié = PIB réel × déflateur publié), la
> colonne « Inflation % » (déflateur du PIB) publie sa variation, et les ratios publiés (dette, déficit, recettes et
> dépenses rapportés au PIB) sont rapportés au PIB publié (`au_pib_publie`). **Sources** : la production non
> marchande est évaluée « as the sum of the costs incurred », rémunération des salariés comprise (SEC 2010 § 10.28)
> ; son volume se mesure aux rémunérations « at base period prices » (§ 10.30) et le prix de chaque type de travail
> est « the compensation paid per hour » (§ 10.44) : une hausse de rémunération à effectifs constants relève le PIB
> en valeur et son déflateur, pas son volume. Mésange (document de travail Insee G2017/04, p. 92) : « le prix de la
> valeur ajoutée non marchande, et par suite les prix de demande en produits non marchands, suivent le salaire moyen
> par tête non marchand ». Insee Première n° 1950 (mai 2023) : « Le déflateur de la consommation des APU augmente
> moins (+1,2 %), même s'il est tiré par la revalorisation du point d'indice des fonctionnaires ». **Rien n'entre
> dans le moteur** : le PIB nominal, le déflateur et l'inflation internes, donc les recettes (élasticité au PIB
> nominal), les indexations, la courbe de Phillips et son inertie, la taille des impulsions, la prime de taux et la
> traînée de dette, l'écart de déficit, le passage de la TVA dans les prix, les bases des leviers et les plafonds,
> l'atterrissage, le Gini et le pouvoir d'achat, restent ceux de l'état sans effet prix ; l'indice des prix à la
> consommation (colonne « Inflation IPC % »), qui ne contient pas les salaires publics, aussi. **Limites déclarées**
> : (1) mesure sans rétroaction : la prime de taux et la traînée de dette lisent le ratio de dette au PIB interne ;
> rapportées au PIB publié, elles abaisseraient le ratio de dette de 2032 d'environ 0,2 point par point de PIB de
> coût (mesuré : au plus 0,25 point, mode cadre 2028) ; (2) les effectifs ne sont pas concernés : la valeur ajoutée
> directe d'une embauche, en volume, reste portée par le multiplicateur de la dépense courante, qui agit dès l'année
> du budget depuis le lot 6 (0,69 % de PIB la première année pour un point de PIB de masse salariale), alors que les
> modèles publiés donnent 1,2 à 2,0 point de PIB par point de PIB de masse salariale la première année (OFCE, *Revue
> de l'OFCE* n° 116, 2011 : 1,2 ; OFCE, policy brief n° 17, 2017 : 2,0) ; à coût égal, une hausse de salaire et une
> embauche ne sont donc pas traitées de façon comparable la première année : au sens du SEC, chacune ajoute son coût
> au PIB en valeur, en prix pour l'une, en volume pour l'autre ; dans le moteur, pour un point de PIB de coût dès
> 2028 (mode cadre), la hausse de salaire relève le PIB publié de 1,67 % et abaisse le ratio de dette de 1,40 point
> la première année, l'embauche relève le PIB de 0,69 % et l'abaisse de 0,21 point (avant le calendrier du lot 6 :
> +1 % et −0,20 point contre 0 et +1,05) ; (3) l'effort budgétaire (colonne « Effort_Budgétaire % ») reste rapporté
> au PIB interne, comme la taille des impulsions qu'il mesure (écart au PIB publié : au plus 0,033 point de PIB) ;
> l'écart de production, en volume, n'est pas touché ; (4) le ratio des recettes publié baisse sans que les recettes
> bougent : le retour immédiat des cotisations n'est pas modélisé à part (limite (2) du lot 5b). Test :
> `tests/test_effet_prix_remunerations.py` (identité publiée PIB = PIB réel × déflateur, avec et sans rémunération ;
> inflation publiée = variation du déflateur publié ; chaque année, le PIB publié porte exactement le coût employeur
> de l'année, effectifs exclus, SMIC compris ; ratios publiés × PIB publié = ratios internes × PIB interne ; toute
> autre colonne identique au bit, indice des prix à la consommation compris ; sans rémunération, tout identique au
> bit ; le SMIC seul relève le PIB publié du montant de son canal, rien d'autre ; hausse et baisse en miroir ;
> chiffres du paragraphe « Ce qui bouge » liés à la mesure, en pleine précision, sauf les rangs ; mutations « prix
> entré dans le PIB interne », « prix dans l'indice des prix à la consommation », « prix compté une seule année », «
> prix aussi pour les effectifs », « déflateur publié non relevé » et « SMIC exclu de l'effet prix » : toutes
> rouges). **Ce qui bouge** (mode cadre 2028, dix scénarios publiés, par rapport au lot 5b ; écarts en pleine
> précision, sans les arrondis de sortie du moteur) : les sept programmes qui relèvent le point d'indice, la
> revalorisation des enseignants ou le SMIC ; la référence sans programme et les trois autres sont identiques au
> bit. **Seuls les rapports au PIB bougent** : la dette et le déficit en euros ne changent pas, ni les recettes ni
> les dépenses ; c'est le PIB en valeur publié, au dénominateur, qui est relevé. Dette rapportée au PIB en 2032 :
> −1,525 et −1,405 point pour les deux qui relèvent le point d'indice (PIB publié 2032 plus haut de 1,09 et 1,02 %),
> −0,487 point pour un programme qui revalorise les enseignants et relève le SMIC, de −0,088 à −0,385 point pour les
> quatre autres ; déficit 2032 rapporté au PIB plus faible de 0,003 à 0,090 point ; recettes et dépenses rapportées
> au PIB plus faibles dans la même proportion ; inflation du déflateur publiée plus haute de 0,013 à 0,222 point par
> an en moyenne sur 2028-2032 (jusqu'à 1,10 point l'année d'une forte hausse) ; indice des prix à la consommation,
> croissance, chômage, Gini et pouvoir d'achat identiques au bit. **Décomposition** (chaque levier compté seul) : le
> point d'indice seul abaisse la dette rapportée au PIB de 2032 de 1,429 et 1,376 point ; la revalorisation des
> enseignants seule de 0,088 à 0,385 point ; la part « agents publics » du SMIC seule de 0,029 à 0,185 point.
> Méthode : chaque levier est mesuré seul, le coût des autres retiré ; mesurée en retirant la seule part du SMIC de
> l'ensemble, elle vaut 0,029 à 0,185 point, l'écart venant de ce que les leviers interagissent par le PIB publié.
> **Rangs.** En pleine précision (comme aux sorties du moteur, à deux décimales) : en dette 2032 rapportée au PIB,
> deux programmes échangent les 9ᵉ et 10ᵉ rangs ; déficit, croissance, chômage, pouvoir d'achat, compétitivité et
> Gini : aucun rang ne change. Aux valeurs affichées par le site (une décimale), s'y ajoutent : en dette, deux
> scénarios ex æquo au 4ᵉ rang se départagent (4ᵉ et 5ᵉ) ; en déficit, deux programmes deviennent ex æquo au 7ᵉ
> rang. Sur la pile d'intégration (lots 2 et 6 appliqués, contre le lot 5b reporté), en pleine précision : en dette
> 2032 rapportée au PIB, trois rangs changent entre le 4ᵉ et le 6ᵉ (le scénario du budget 2026 voté passe du 4ᵉ au
> 6ᵉ) ; aux sorties du moteur (deux décimales), un ex æquo au 5ᵉ rang se départage ; aux valeurs affichées par le
> site (une décimale), un ex æquo à trois au 4ᵉ rang se départage ; déficit, croissance, chômage, pouvoir d'achat,
> compétitivité et Gini : aucun rang ne change.

> **Prestations en espèces émises hors des leviers de transfert : traitement des transferts (lot 5e, équation,
> 16/11/2026, non publiée).** Même règle que le lot 5b : le montant qu'un levier émet au canal ménages `prestations`
> et qui n'est pas déjà traité comme un transfert (levier hors `TRANSFER_MEASURES`, hors coefficient propre) forme
> un flux distinct, `(levier, 'prestations')` dans `flux_par_levier` (`engine/growth.py`), au coefficient et au
> profil des transferts (`MULT_TRANSFERTS`, `DECAY_PROFILE_TRANSFERS`), dans les deux sens ; le reste du levier
> garde sa famille. Un seul cas : le rabot uniforme, dont les coupes de pensions, d'allocations chômage et de minima
> sociaux, allocation aux adultes handicapés comprise (`_CATEGORIES_ESPECES`, `handlers/montaigne.py`), étaient
> prises en dépense courante avec le reste du rabot ; elles en font environ un tiers (46,8 Md€ sur 141,2 en 2032,
> mode cadre, programme publié qui l'utilise). **Source** : ce sont des prestations sociales en espèces (SEC 2010,
> D.62), que le moteur traite déjà comme des transferts quand un levier de transfert les porte (`retraites`,
> `chomage_alloc`, `prestations_menages`) ; le montant est celui que lit déjà l'indice de pouvoir d'achat.
> **Exceptions déclarées**, verrouillées par la liste et par le comportement (retirer leur canal ne change aucune
> colonne macroéconomique) : le SMIC, levier de transfert, dont toute la dépense est déjà au traitement des
> transferts (jusqu'au lot SMIC, à coefficient propre, il gardait ce canal dans son solde) ; la santé
> (`PRESTATIONS_NON_RECLASSEES`, `simulator.py`) aussi : son canal `prestations` porte les franchises et
> participations, un reste à charge sur des remboursements de soins, c'est-à-dire une prestation en nature (SEC
> 2010, D.632), pas en espèces ; laissée en l'état, en attente d'un arbitrage. **Limites** : celles du lot 5b pour
> le coefficient et le profil des transferts (profil concentré sur les premières années) ; la coupe de masse
> salariale du rabot n'est pas touchée (limite 10 de « Limites et Precautions »). Test :
> `tests/test_prestations_hors_transferts.py` (émetteurs dérivés du registre des paramètres : hors des leviers de
> transfert et des coefficients propres, exactement le rabot et la santé ; source unique chaque année, deux modes ;
> même trajectoire macroéconomique qu'un transfert du même montant, à 1e-9 près, en montée en charge sur trois ans,
> dans les deux sens et cinq états, pour le rabot et un émetteur synthétique ; non-vacuité ; exceptions du SMIC et
> de la santé par le comportement ; mutations « santé reclassée », « règle désactivée », « règle limitée à la
> première impulsion », « prestations comptées en plus de la dépense » et « SMIC reclassé » : toutes rouges). **Ce
> qui bouge** (mode cadre 2028, dix scénarios publiés, par rapport au lot 5b) : le seul programme qui utilise le
> rabot, dette 2032 −0,58 point, déficit 2032 plus faible de 0,14 point, croissance moyenne 2028-2032 +0,042 point,
> chômage 2032 −0,06 point ; les neuf autres scénarios et la référence sans programme sont identiques au bit. Rangs :
> aucun ne change en pleine précision (ni aux sorties du moteur, à deux décimales) ; aux valeurs affichées par le site
> (une décimale), le programme qui utilise le rabot rejoint, ex æquo, le 1ᵉʳ rang de déficit 2032. Sur la pile
> d'intégration (lots 2, 6, 5b et 5d appliqués, contre le lot 5d reporté) : dette 2032 −0,65 point, déficit 2032
> plus faible de 0,15, croissance moyenne +0,038, chômage 2032 −0,07 ; en dette 2032, ce programme passe du 2ᵉ au
> 1ᵉʳ rang (pleine précision comme aux sorties du moteur), et, à une décimale, il rejoint aussi, ex æquo, le 9ᵉ rang
> de chômage.

> **Dotation aux collectivités : la moitié d'une variation comptée comme de l'investissement local (lot 5c,
> équation, 16/11/2026, non publiée).** Arbitrage du mainteneur du 16/11/2026 : une variation de la dotation aux
> collectivités (`collectivites.dotation`) est prise pour moitié (`PART_DOTATION_INVESTIE` = 0,5, `constants.py`)
> comme une variation d'investissement local, pour l'autre moitié comme de la dépense courante, dans les deux sens.
> La moitié investie prend le traitement du curseur d'investissement local (`collectivites.investissement`) : flux
> d'investissement, coefficient et profil de l'investissement productif (sur la pile d'intégration, avec le
> calendrier et le profil du lot 6 : 1,28 point de PIB à 4 ans par point de PIB pour la demande seule, 1,54 avec
> l'effet d'offre d'un équipement public, contre 0,79 pour la dépense courante ; 1,41 contre 0,79 sur le lot 5e
> seul) et effet d'offre du capital public local (canal `collectivites_invest`). L'effet direct sur le déficit reste
> d'un euro pour un euro. Avant : toute la dotation était de la dépense courante. La même règle vaut pour la coupe
> de cette ligne de dépense par le rabot uniforme (`COUPES_DE_DOTATION`, `simulator.py`) : sa catégorie «
> collectivites » est la même ligne de 120 Md€ « Dotations » que déplace le curseur ; la part investie de la coupe
> est publiée dans l'impact du rabot (impulsion d'investissement) et, en mode cadre, nourrit le même canal d'offre,
> depuis une référence nulle (le statu quo ne porte pas cette coupe). **Source unique** : la part
> (`part_investie_d_une_variation_de_dotation`) ; `part_investie_des_autres_parametres` (`simulator.py`) donne le
> montant du curseur à l'impulsion (ajouté à la clé d'impact `depenses_investissement` du curseur) et au canal
> d'offre ; `references_d_offre_des_parts_investies` donne la référence de l'offre. **Sources** : Caisse des Dépôts,
> *Éclairages* n° 8, « Impact des dotations de l'État sur l'investissement des collectivités : une approche
> économétrique (2001-2013) », septembre 2015 — élasticité des dépenses d'investissement hors remboursement de la
> dette aux dotations totales de 0,14 (communes) à 0,40 (départements) la première année, « On constate une symétrie
> à court terme », 0,40 pour les communes « après 3 années successives de baisse » ; rapportée aux montants de 2013
> (DGCL, *Les collectivités locales en chiffres 2015*), un euro de dotation en moins retire 0,20 à 0,26 €
> d'investissement local la première année et 0,41 à 0,59 € pour une baisse durable (0,47 à 0,61 €, déduit et non
> publié tel quel : la simulation des baisses de 2014-2017 que publie l'étude, −10 % à −13 % d'investissement à
> l'horizon 2017, rapportée à 12,5 Md€ de baisse). Cour des comptes, *Les finances publiques locales*, septembre
> 2018, p. 69-86 : la part forfaitaire de la dotation globale de fonctionnement a été réduite de 11,2 Md€ entre 2013
> et 2017, et l'investissement local de 2017 restait inférieur de 10,8 % à celui de 2013, soit environ 0,6 € par
> euro de dotation (lecture sans contrefactuel : la Cour ne neutralise pas le cycle électoral) ; « l'investissement,
> surtout l'effort d'équipement local, a servi immédiatement de variable d'ajustement ». La moitié est le centre de
> la fourchette d'une baisse durable, pas un chiffre publié. **Variantes** (fourchette des sources, de 20 % la
> première année à 60 % pour une baisse durable ; mode cadre 2028, dette 2032 en écart à la référence) : une baisse
> durable de 10 Md€ de la dotation sous le droit en vigueur coûte, par rapport à la seule dépense courante, +0,25
> point à la part retenue (50 %), +0,10 point à 20 % et +0,30 point à 60 %. **Deux références, déclarées** :
> l'impulsion de la part investie se compte depuis le défaut du moteur, comme toute dépense ; son effet d'offre, en
> mode cadre, depuis la dotation du droit en vigueur de l'année, lue dans le cadre de la simulation, pour que le
> statu quo, qui applique ce droit, ne consomme aucune offre (contrat W6-10 de
> `tests/test_effet_offre_echelle_v0612.py`, inchangé). Tant que le droit (116,6 Md€) reste sous le défaut (120
> Md€), les deux montants diffèrent de 1,7 Md€ par an : la référence sans programme porte l'impulsion d'une baisse
> d'investissement local de 1,7 Md€ par an (+0,14 point de dette 2032), sans son effet d'offre, qui lui ajouterait
> 0,09 point de dette 2032. **Différence entre les deux modes** : le mode historique n'applique pas le droit en
> vigueur (il ne lit pas même son fichier) ; faute de cette référence, la part investie n'y a pas d'effet d'offre,
> et son impulsion y est comptée. Le site calcule tous ses chiffres en mode cadre. La double référence et la
> condition de mode viennent de l'écart entre le défaut du moteur et le droit en vigueur ; aligner le défaut sur le
> droit relèverait d'une release de paramètres. **Limites déclarées** : (1) une seule étude économétrique française,
> non évaluée par des pairs, dont 94 % des observations sont des communes, appliquée ici aux montants agrégés avec
> le ratio investissement/dotations de 2013 ; la définition exacte de ses « dotations totales » n'est pas vérifiée ;
> l'étude prévient que son long terme « suggère plus l'idée d'une influence mutuelle des variables que d'une
> véritable causalité » ; (2) une seule part, quel que soit l'horizon, dès la première année, alors que l'étude ne
> tient pour causales que ses estimations de court terme (0,20 à 0,26 € la première année) : si l'on suit ce seul
> court terme, l'effet de la première année est surestimé ; une part qui monterait avec la durée de la baisse
> demanderait une valeur pour les années intermédiaires et une règle de cumul des baisses que l'étude ne donne pas,
> elle n'est donc pas proposée en variante (les variantes à 20 % et 60 % en donnent les bornes) ; (3) aucune
> réaction des collectivités sur le solde public, ni impôt local, ni emprunt, ni fiscalité transférée par l'État en
> compensation : un programme qui baisse la dotation est lu comme une baisse nette ; en 2014-2017, la part passée
> par les taux des impôts locaux est d'au plus 0,19 à 0,24 € par euro de dotation (majorant déduit du bilan de la
> Cour), et les administrations locales n'ont pas creusé leur déficit en agrégé : leur solde passe de −4,8 Md€ en
> 2014 à +0,8 Md€ en 2017 (Insee Première n° 1698, mai 2018, figure 3), leur dette croissant moins vite qu'avant
> (+14,6 Md€ de 2013 à 2017, 2,2 % par an contre 3,5 % de 2010 à 2013 ; Cour des comptes, même rapport) ; (4) la
> même part en hausse et en baisse : l'étude constate une symétrie à court terme ; au-delà, c'est la convention de
> symétrie du moteur (encadré du lot 5) ; (5) comme pour tout investissement public du moteur, l'effet d'offre de la
> moitié investie s'ajoute à un coefficient de demande calé sur l'effet total à quatre ans : un double compte
> possible, commun à ces leviers, qui pèse ici de 0,044 à 0,115 point de dette 2032 pour les quatre scénarios qui
> baissent la dotation, celui du rabot uniforme compris. **Levier en échec** : une valeur non numérique fait échouer
> le levier, qui n'a alors ni impulsion ni effet d'offre, curseur d'investissement compris (avant ce lot, ce curseur
> gardait son effet d'offre). Test : `tests/test_dotation_investissement_local.py` (part lue par le registre ;
> impulsion identique à celle du curseur d'investissement à part × (dotation − défaut), effet d'offre retiré, dans
> les deux modes et les deux sens : au bit en mode historique, à 1e-12 près en mode cadre ; en mode cadre, effet
> d'offre identique à celui du curseur à part × (dotation − dotation du droit) ; en mode historique, aucun effet
> d'offre et aucune lecture du droit en vigueur ; non-vacuité ; hausse et baisse en miroir sur le PIB de 1 à 4 ans ;
> coupe de dotation du rabot : même ligne de dépense, part investie publiée chaque année, effet d'offre en mode
> cadre seulement ; levier en échec sans impulsion ni offre ; offre de la coupe du rabot égale, en montant, à celle
> du curseur d'investissement pour part × coupe ; curseur d'investissement, dotation et coupe du rabot bougés
> ensemble : leurs parts s'ajoutent sur le canal d'offre, aucune ne remplace les autres ; chiffres de cet encadré
> liés à la mesure, ceux du paragraphe suivant en pleine précision, sauf le coefficient seul et les rangs ;
> mutations « offre depuis le défaut », « offre aussi en mode historique », « pas d'offre en mode cadre », «
> impulsion depuis le droit », « part de la dotation qui remplace l'écart du curseur », « part du rabot qui remplace
> les deux autres » et « offre du rabot doublée » : toutes rouges). **Ce qui bouge** (mode cadre 2028, dix scénarios
> publiés, par rapport au lot 5e ; écarts calculés en pleine précision, sans les arrondis de sortie du moteur) :
> tous, et la référence sans programme, puisque le droit en vigueur porte une dotation sous le défaut ; dette 2032
> de +0,134 à +0,136 point pour les six qui gardent la dotation du droit (référence : +0,136), de +0,182 à +0,311
> point pour les trois programmes qui la baissent de 7 à 12 Md€, +0,346 point pour celui qui utilise le rabot
> uniforme (dont +0,211 pour sa coupe de dotation) ; déficit 2032 de −0,020 à −0,096 point ; croissance moyenne
> 2028-2032 de −0,004 à −0,030 point ; Gini inchangé (écart inférieur à 0,0001). **Décomposition** (même mesure, les
> trois programmes qui baissent la dotation, en écart à la référence) : le coefficient seul, profil d'origine
> (mesuré sur le lot 5e seul, avant les lots 2 et 6), +0,126 à +0,246 point ; avec le profil de l'investissement,
> +0,001 à +0,100 point (ce profil culmine la deuxième année puis s'éteint) ; avec aussi l'effet d'offre (ce
> commit), +0,046 à +0,175 point. **Rangs**, comparés en pleine précision pour tous les indicateurs : le scénario du
> budget 2026 voté et un programme échangent les 4ᵉ et 5ᵉ rangs de dette et de déficit 2032 et les 7ᵉ et 8ᵉ rangs de
> chômage 2032 ; deux programmes échangent les 7ᵉ et 8ᵉ rangs de déficit 2032 ; croissance, pouvoir d'achat,
> compétitivité et Gini : aucun rang ne change. Aux sorties du moteur, à deux décimales (une pour le pouvoir
> d'achat), l'échange des 7ᵉ et 8ᵉ rangs de déficit devient un ex æquo au 7ᵉ rang, et un ex æquo apparaît au 5ᵉ rang
> de pouvoir d'achat 2032. Aux valeurs affichées par le site, à une décimale : en dette, l'échange des 4ᵉ et 5ᵉ
> rangs demeure ; en déficit, l'échange des 4ᵉ et 5ᵉ rangs disparaît, et l'ex æquo qui existait au 7ᵉ rang se
> départage (7ᵉ et 8ᵉ) ; en chômage, l'échange des 7ᵉ et 8ᵉ rangs disparaît ; en croissance, trois rangs bougent :
> un programme passe du 5ᵉ au 7ᵉ rang, un autre du 8ᵉ au 7ᵉ, ex æquo, et l'ex æquo du 5ᵉ rang passe de trois
> scénarios à deux ; en pouvoir d'achat, l'ex æquo nouveau au 5ᵉ rang demeure. Ces rangs sont ceux du lot 5c sur le
> lot 5e seul. Sur la pile d'intégration (lots 2, 6, 5b, 5d et 5e appliqués, contre le lot 5e reporté), en pleine
> précision : en dette 2032, le scénario du budget 2026 voté et un programme échangent les 5ᵉ et 6ᵉ rangs, deux
> autres programmes les 7ᵉ et 8ᵉ ; en déficit 2032, le même échange des 5ᵉ et 6ᵉ rangs ; en chômage 2032, ces
> deux-là échangent les 7ᵉ et 8ᵉ ; croissance, pouvoir d'achat, compétitivité et Gini : aucun rang ne change. Aux
> sorties du moteur (deux décimales), s'y ajoutent un ex æquo nouveau au 6ᵉ rang de croissance et un ex æquo au 6ᵉ
> rang de chômage ; à une décimale, comme le site, l'ex æquo du 5ᵉ rang de déficit se départage, la croissance
> compte un ex æquo à trois au 6ᵉ rang et l'ex æquo du 9ᵉ rang de chômage se départage.

**Transferts symétriques en signe (v0.6.7, lot 3b — réfuteur macro).** Gechert (2015) classe par INSTRUMENT, pas par signe : une COUPE de transfert (`TRANSFER_MEASURES` hors SMIC, multiplié sur son solde net) prend désormais le même coefficient que la hausse (k = 0,71). Jusqu'ici elle prenait celui de la coupe générique, atténué ÷1,10 « confiance » : couper 1 % du PIB de pensions coûtait 0,707 point de PIB à 4 ans quand la hausse en rapportait 0,653 (+8,2 %). Déplace la dette 2035 des seuls programmes qui coupent des transferts (IM Compétitivité −0,12, Horizons −0,11, Renaissance −0,05, LR −0,04, IM Rabot −0,02 pt). **Asymétrie résiduelle déclarée jusqu'à v0.8.1** : en moteur complet, la coupe coûtait encore 4,4 % de plus que la hausse ne rapportait ; c'était l'éviction (« crowding-out »), qui réduisait l'effet des seules expansions financées par la dette au-delà de 100 % du PIB sans « crowding-in » symétrique pour les consolidations (éviction neutralisée : 0,9 %). Éviction retirée au lot 1 (15/11/2026) : 0,1 %, verrouillé à 1 % par `tests/test_symetrie_transferts_v067.py`.
(Correction du lot 5 : la symétrie de signe n'est pas un résultat de Gechert 2015, qui classe par instrument et ne teste pas le signe ; c'est une convention du mainteneur, pour toutes les familles. Limite déclarée : encadré « Dépense courante symétrique en signe ».)

**Baisse d'impôts symétrique de la hausse (v0.6.7 — arbitrage du mainteneur du 07/10/2026 : « pas prouvé = valeur centrale »).** Jusqu'ici une baisse d'impôts valait 0,7 fois une hausse (k 0,455 contre 0,615 ; « asymétrie hausse/baisse du moteur conservée (0,35/0,50) », un héritage sans source) : rendre 1 point de PIB d'impôts rapportait 0,45 point de PIB à 4 ans quand le prélever en coûtait 0,65 — 0,2 point de PIB d'écart défavorable, mécanique, par point de PIB pour tout programme qui baisse un impôt. Vérification en ligne du 07/10/2026 : les études de référence estiment UN coefficient pour les deux signes (Romer & Romer 2010, *AER* 100(3), 763-801, chocs narratifs : « tax increases are highly contractionary », modèle linéaire ; Mertens & Ravn 2013, *AER* 103(4), 1212-47, impôts sur le revenu et sur les sociétés, « short run output effects of tax shocks are large » ; méta-analyse Gechert 2015, *Oxford Economic Papers* 67(3), qui classe par instrument) ; les seules estimations d'une asymétrie de signe se contredisent : aux États-Unis c'est la BAISSE qui l'emporte (Hussain & Malik 2016, *Journal of Economic Dynamics and Control* 69, 268-300 : « the output response to a tax increase is statistically insignificant, but output shows a significantly positive and permanent increase following a tax decrease » ; Jones, Olson & Wohar 2015, *Journal of Macroeconomics* 43, 38-48 : « in the U.S. positive tax shocks—tax increases—do not affect output while negative tax shocks—tax cuts—have large, positive effects »), au Royaume-Uni la HAUSSE (même article : « In the U.K., tax increases substantially reduce output while tax cuts have no significant effect »). Aucune asymétrie n'est établie dans un sens : la baisse prend la valeur centrale de la hausse, 0,65 d'effet de niveau à 4 ans. Le coefficient d'impact était un peu plus haut (k = 0,63 contre 0,615) parce que l'éviction du moteur (« crowding-out ») ne frappait que les expansions au-delà de 100 % du PIB de dette : à k égal, la baisse n'aurait valu que 0,631 (−3 %) ; éviction neutralisée, k égaux donnaient un rapport 1,001. Éviction retirée au lot 1 (15/11/2026) : k = 0,615 dans les deux sens. Déplace les seuls scénarios qui baissent un impôt (dette 2035 : LR −2,84 pt, Horizons −2,72, RN −1,70, Renaissance −1,58, IM Compétitivité −1,05, LFI −0,88, PS −0,77, Budget 2026 voté −0,03) et 5 cas isolés du golden master ; les 31 autres cas, dont le statu quo, Écologistes et IM Rabot, sont identiques au bit. Verrouillé par `tests/test_symetrie_impots_v067.py` (trois leviers fiscaux, rapport baisse/hausse à 4 ans à ±3 %).

Le rappel vers le potentiel rend les effets de demande transitoires : à 10 ans le niveau est revenu
près de zéro (l'effet durable du capital public passe par le canal d'offre `SUPPLY_EFFECTS`). **Le choc
d'investissement retenu pour le calibrage ne s'autofinance pas dans le banc de référence** : impulsion
synthétique PERMANENTE de 1 % du PIB sur le levier éducation, à partir du statu quo, 2026-2036
(`tests/test_multiplicateurs_centraux_v067.py`). Trois notions à ne pas confondre, mesurées sur ce banc :
(1) autofinancement budgétaire — le solde public ne récupère que 6 % du coût brut (392 Md EUR sur
2026-2036) : les recettes induites (+330 Md EUR) sont en grande partie absorbées par les dépenses
induites hors impulsion (+306 Md EUR : dépenses indexées sur les prix +154, intérêts +152) ; mesure
distincte, en volume, sans prix ni intérêts : multiplicateur cumulé 10 ans × 0,51 = 0,42 < 1 ; (2) dette
nominale — +96 Md EUR en 2030, +369 Md EUR en 2036 ; (3) ratio dette/PIB — le PIB nominal plus haut
(volume et prix : +1,87 % en 2030 pour +1,28 % en volume) gonfle le dénominateur sans compenser le coût : le ratio
dépasse le statu quo en 2030 (+0,38 pt) et 2031 (+0,82 pt), puis de plus en plus (+4,6 pt en 2035). Ce banc
mesure la DEMANDE seule (levier éducation, sans canal d'offre sur l'horizon) avec le profil calé sur le FMI ; un
levier de capital public y ajoute son canal d'offre. Avant ce calage (lot 6, k = 1,31, profil « pic Y2 ») :
26 % du coût récupéré, dette nominale +61 Md EUR en 2030, ratio sous le statu quo en 2030 (−1,13 pt) et 2031
(−0,88 pt). Jusqu'au lot 6 (calendrier de l'impulsion : l'effet sur l'activité n'arrivait qu'en 2027 ;
coefficient 1,2), 8 % du coût récupéré, dette nominale +104 Md EUR en 2030, ratio au-dessus du statu quo dès 2030
(+0,57 pt).
Jusqu'à v0.8.1, le terme d'effort de l'inflation (retiré au lot 1) ajoutait 0,08 point d'inflation par
point de PIB de relance, chaque année : la hausse des prix portait alors près des deux tiers des recettes
induites (+458 Md EUR, 13 % du coût récupéré) et le ratio passait légèrement SOUS le statu quo en 2030
(−0,06 pt) et 2031 (−0,01 pt). C'est un garde-fou sur un choc, pas une démonstration pour
tous les investissements, intensités, combinaisons et états macroéconomiques ; il est complété par le
balayage du curseur éducation (`tests/test_symetrie_v060.py` : dette 2035 croissante de 45 à 85, en euros
et en ratio). Jusqu'en v0.6.6, la somme analytique `k × Σ profil` = 1,2 × 1,98 = 2,38 en effet permanent
impliquait l'autofinancement (2,38 × 0,51 > 1), masqué par l'impulsion unique. Le recalibrage RELÈVE trois
familles sur quatre : la v0.6.6 était sous la valeur centrale pour les impôts, les transferts et les coupes.

> **Corrigé en v0.6.10 (contre-audit externe, V2-06)** : cette section décrivait deux états du
> recalibrage — un paragraphe gardait les sommes analytiques de la v0.6.6 comme effet courant et tenait
> le recalage du profil INVEST pour une question encore pendante, alors que le tableau décrit le
> recalibrage v0.6.7 réalisé — et énonçait comme une loi sur tout investissement un garde-fou qui ne
> vérifie qu'un choc. La part rendue au solde (13 %) remplace un 11 % mesuré avant la fin des lots de la
> v0.6.7. Aucune sortie du moteur ne change ; verrouillé par `tests/test_methodologie_recalibrage_v0610.py`.

**Incertitude et poids du canal keynésien (v0.6.7, arbitrage du mainteneur du 07/10/2026).** Le
classement entre programmes dépend d'abord de ce canal. Mesure du 07/10/2026 (moteur v0.6.7, les cinq
multiplicateurs `MULT_*` à zéro, toutes les autres équations inchangées), dette 2035 en % du PIB :

| Scénario | Avec canal (central) | Sans canal | Effet du canal (pts) |
|---|---:|---:|---:|
| Statu quo | 151,2 | 151,2 | 0,0 |
| Budget 2026 voté | 149,8 | 148,4 | +1,4 |
| RN | 152,7 | 159,6 | −6,9 |
| LFI | 151,8 | 176,3 | −24,5 |
| Renaissance | 151,6 | 156,1 | −4,5 |
| Horizons | 145,0 | 140,4 | +4,6 |
| LR | 156,1 | 161,8 | −5,7 |
| PS | 144,7 | 157,8 | −13,1 |
| Les Écologistes | 137,1 | 145,4 | −8,3 |
| IM Rabot | 134,4 | 106,1 | +28,3 |
| IM Compétitivité | 127,6 | 127,7 | −0,1 |

Selon les programmes, le canal déplace la dette 2035 de −24,5 à +28,3 points, les deux extrêmes des dix
scénarios publiés (négatif : le canal allège la dette, cas des programmes de relance ; positif : il
l'alourdit, cas des consolidations). La valeur centrale retenue est celle de la table ci-dessus (FMI WEO
oct. 2014, Ramey 2019, Gechert 2015), mais la littérature ne tranche pas pour la France. Le site publie
donc, sur chaque fiche programme, une fourchette : la même trajectoire avec les cinq multiplicateurs
(`MULT_INVESTISSEMENT`, `MULT_COUPE_DEPENSES`, `MULT_TRANSFERTS`, `MULT_HAUSSE_IMPOTS`,
`MULT_BAISSE_IMPOTS`) ×0,75 et ×1,25 — coefficient propre de la fraude fiscale et
ajustements conjoncturels inchangés. Les deux extrêmes des dix scénarios, dette 2035 : la fourchette la
plus large est celle d'IM Rabot (125,4 à 144,5 %), la plus étroite celle d'IM Compétitivité (127,6 % dans
les deux cas) ; chaque fiche publie la sienne. Le statu quo, sans impulsion, ne bouge pas (151,2 %).

**Perimetre du canal investissement (v0.6.0)** : education, recherche publique,
transition ecologique UNIQUEMENT (`INVESTMENT_CORE_MEASURES`). La sante courante
et la reforme de l'Etat sont de la consommation/optimisation publique : canaux
transferts/generique (la revue adverse du 24/08 a montre que le perimetre large
donnait un multiplicateur d'investissement aux coupes... de sante). Depuis le lot 5b,
la revalorisation des enseignants en place en sort : une hausse de remuneration a
effectifs constants, au traitement des transferts (encadre du lot 5b). Depuis le lot 5c,
la moitie d'une variation de dotation aux collectivites y entre, par le flux de
l'investissement local (encadre du lot 5c).

**Atténuation « confiance » retirée (v0.6.7 — règle posée par le mainteneur le 07/10/2026 : un mécanisme reste si et seulement s'il est conforme à la littérature).** Jusqu'ici toute coupe de dépense générique était divisée par 1,10 dès la 2ᵉ année (« effet confiance », Alesina-Favero-Giavazzi : plans par la dépense « mild recessionary »). Deux constats, chacun suffisant :

1. **Il était redondant par construction.** Le facteur frappait 100 % des coupes génériques (sonde sur les 44 cas du golden master : aucune coupe générique hors de son champ), et la calibration v0.6.7 cale l'EFFECTIF de la coupe sur 0,8 (Ramey 2019) : il était donc absorbé dans k. Preuve : sans le facteur, avec k = 0,81 / 1,10, les 44 cas sont identiques au bit. Il ne modélisait rien ; il affichait un mécanisme.
2. **L'effet qu'il affichait est contredit par la table qui le porte, et n'est pas établi pour la France.** Alesina, Favero & Giavazzi (2015, *Journal of International Economics* 96, S19-S42 ; livre *Austerity*, 2019) : « Fiscal adjustments based upon spending cuts are much less costly, in terms of output losses, than tax-based ones », différence « not to be explained by accompanying policies, including monetary policy » mais par la confiance et l'investissement privé. Le FMI (WEO oct. 2010, ch. 3, « Will It Hurt? ») trouve le même classement mais l'attribue d'abord à la politique monétaire : « Consolidation is more painful when it relies primarily on tax hikes; this occurs largely because central banks typically provide less monetary stimulus during such episodes » — canal qui n'existe pas pour un pays de la zone euro, dont la politique monétaire est commune. Et la méta-analyse retenue par le moteur pour classer les instruments (Gechert 2015, 104 études) donne l'ordre INVERSE : dépenses ≈ 1, impôts 0,3 à 0,4 de moins. La table par famille suit Gechert — coupe 0,8 contre hausse d'impôts 0,65 —, si bien que, même ÷ 1,10, une consolidation par la dépense coûtait PLUS de PIB qu'une consolidation par l'impôt : le facteur n'implémentait pas l'effet d'AFG, il en portait le nom. Les multiplicateurs fiscaux narratifs américains (Ramey 2019 : « −2 to −3 ») iraient dans le sens d'AFG, mais ils ne sont pas retenus comme centraux pour la France (choix déclaré dans la table ci-dessus). Guajardo, Leigh & Pescatori (2014, *JEEA* 12(4)) réfutent l'austérité EXPANSIONNISTE (« fiscal consolidation has contractionary effects on private demand and GDP »), pas la composition : ils ne tranchent pas cette question.

Décision : le facteur est retiré, k de la coupe générique passe de 0,81 (÷ 1,10) à 0,74 pour garder l'effectif sourcé (0,7963 → 0,8004 à 4 ans). Un effet de composition à la AFG n'est PAS introduit à la place : il faudrait poser une cible de coupe sous celle de l'impôt, contre la méta-analyse et avec un canal monétaire absent en zone euro. Effet mesuré : les seuls cas qui coupent une dépense générique bougent, de l'arrondi de k (dette 2035 : IM Rabot +0,16 pt, IM Compétitivité +0,06, Horizons +0,04, RN, Renaissance et LR +0,03, LFI et PS +0,02, Écologistes et Budget 2026 voté +0,01) ; les 29 autres cas, dont le statu quo, sont identiques au bit. Verrouillé par `tests/test_symetrie_v060.py` (coefficient identique à toute année, plus de clé `confidence`).

**Limite documentee (residu de « pompe a PIB »)** : dans un moteur dynamique a
etats (taux, chomage, dette), une sequence hausse-puis-coupe de meme montant ne
laisse pas un PIB strictement identique — residu mesure +0,2 a +0,6 % du PIB
2035 selon le curseur (v5.1 : jusqu'a +2 %). Le residu est borne par
test-propriete en CI ; le reduire encore releve d'un chantier de linearisation
dedie, pas d'un coefficient.

### Régimes conjoncturels à transition continue (v0.6.7, lot 3b)

**Ce qui change.** Jusqu'en v0.6.6, chaque dépendance du moteur à la conjoncture était une MARCHE : multiplicateurs ×1,15 si output gap < −2 % ou écart de chômage > 2 pts, ×0,85 si gap > 2 % et écart < −1 pt, ×1,3 (ZLB) si taux < 2 % et gap < −2 % ; dépenses en volume ×0,90 si gap < −2 %, ×1,02 si gap > 2 % ; inflation ×0,80 si gap < −2,5 % et écart > 1 pt, ×1,08 si gap > 2 % et écart < −1 pt ; chômage +0,2 pt si croissance < −1,5 %, −0,1 pt si croissance > 2 % ; potentiel ×0,997 / ×1,002 au-delà de ∓2 % de croissance ; plancher monétaire accommodant (sous 0,8 % d'inflation, π → 0,7 π + 0,3 π*), qui faisait REMONTER l'inflation de 0,80 à 1,04 % au franchissement. Une marche transforme une variation infinitésimale d'un paramètre en saut : la prévention de `im_rabot_2029` poussée de 10⁻⁹ Md€ au-delà de 7,6 Md€ coûtait −1,67 pt de dette 2035, et un balayage systématique (chaque paramètre de `PARAM_DOMAINS` × 10 scénarios publiés, bissection à 10⁻⁹ : `scripts/scan_discontinuites.py`) trouvait ce type de saut en 26 points (20 couples scénario × paramètre), de +1,92 pt (curseur `rabot_uniforme` de « Budget 2026 (voté) ») à −0,20 pt ; deux de plus (plancher monétaire, −0,66 et −0,69 pt sur le même curseur de « Budget 2026 (voté) » et d'Horizons) sont apparus une fois la marche récession lissée, qui les masquait.

**Forme retenue.** Chaque régime passe par un poids w ∈ [0 ; 1] et la réponse est la moyenne des réponses des deux régimes pondérée par w (`x × (1 + (F − 1) × w)`, F = facteur du plein régime ; `engine/_regimes.py`). C'est la structure des modèles à transition lisse d'Auerbach & Gorodnichenko (2012), « Measuring the Output Responses to Fiscal Policy », *American Economic Journal: Economic Policy* 4(2), 1-27 (DOI 10.1257/pol.4.2.1) : « using regime-switching models, we find large differences in the size of spending multipliers in recessions and expansions » — leur STVAR pondère les deux régimes par un poids F(z) continu de l'état. A&G emploient une logistique ; le moteur retient une **rampe linéaire à support compact** : poids nul hors de la zone (régime normal inchangé AU BIT : statu quo et « Budget 2026 (voté) » identiques), plein au-delà (plein régime inchangé au bit), 0,5 au seuil historique. Conditions composées : « ou » → max des poids, « et » → min. **Demi-largeurs, choix déclarés** (`REGIME_DEMI_LARGEUR_*`) : ±1 pt sur l'output gap et l'écart de chômage (zone −3 % → −1 % autour du seuil −2 %), ±0,5 pt sur la croissance (avec ±1 pt, la zone du seuil +2 % commencerait à +1 % et engloberait la croissance normale du statu quo, 0,9-1,2 %), ±0,3 pt sur l'inflation pour le plancher monétaire (la plus petite valeur ronde qui garde la règle CROISSANTE avec marge — ±0,2 pt la laisserait décroissante par endroits — et dont la zone 0,5-1,1 % reste sous l'inflation la plus basse du statu quo, 1,34 %). La condition « chômage au-dessus du NAIRU » du rebond n'est pas un régime mais un plancher : le rebond s'arrête désormais au NAIRU (l'ancienne marche retirait 0,1 pt entier, quitte à passer sous le NAIRU). Depuis le ré-ancrage du potentiel (même lot), les hystérèses du chômage et du potentiel lisent la croissance CYCLIQUE — l'écart au potentiel total, comme la loi d'Okun (correction I6) —, seuils historiques ré-exprimés en écart au potentiel officiel 1,1 % (chômage −2,6 / +0,9 pt, potentiel −3,1 / +0,9 pt) : lues sur le niveau de croissance, elles comptaient la croissance d'OFFRE comme un boom, et un choc d'offre faisait baisser le chômage (propriété P1, `tests/test_okun_potentiel_v061.py`). Les bornes de l'hystérèse du tendanciel deviennent RELATIVES (−0,4 / +0,1 pt autour du tendanciel de départ, la marge de la v0.6.6) : absolues à [0,7 ; 1,2 %] avec un tendanciel à 1,228 %, elles auraient interdit l'hystérèse positive et gardé la négative.

**Ce que cela déplace** (dette 2035, avant → après) : `im_rabot_2029` 141,67 → 141,14 (son gap 2027 de −2,31 % n'est plus au plein régime récession mais à poids 0,66 : moins d'amplification de sa consolidation, −0,72 pt ; moins de compression de dépense, +0,23 ; inflation et plancher monétaire +0,08 ; chômage −0,12) ; `lfi_2027` 158,83 → 158,35 (gap de +2,5 à +3,6 % : régimes expansion et tensions entrés plus tôt et plus progressivement — multiplicateurs −0,26, inflation −0,14, dépenses −0,07) ; `ps_2027` 152,00 → 151,80 (gap 2029 à +2,01 %, pile sur l'ancienne marche « tensions ») ; `horizons_2027` 154,51 → 154,42. Les six autres scénarios et le statu quo sont identiques au bit. La règle est la même pour tous ; les scénarios qui bougent sont ceux dont l'économie simulée s'approche des seuils, aux deux bords.

**Inerte et conservé** : la condition ZLB lit `taux_interet_base` (2,00 %, constant), jamais sous 2 % — sa condition de gap suit la même transition, sans effet. **Reste discontinu, hors périmètre, déclaré** : le plafond de Laffer à 60 et 65 % de recettes/PIB (inatteignable, ~52 % servi). Verrouillé par `tests/test_continuite_regimes_v067.py` : continuité de chaque régime à ±10⁻⁹ de son seuil, plancher monétaire continu et croissant, plateaux identiques au bit, valeur médiane au seuil, et les 28 points de saut réels du balayage (écart < 0,001 pt de dette 2035 pour ±10⁻⁷ de la plage du paramètre).

**Portes d'activation (même lot).** Une porte est un seuil sous lequel un effet PROPORTIONNEL à la taille d'un levier est mis à zéro : l'effet vaut déjà 0 en 0, la porte ne fait que créer une marche à son seuil. Quatre sont retirées : effet d'offre (100 M€ d'écart au défaut), pass-through TVA (0,3 % du PIB), effet de l'effort budgétaire sur l'inflation (0,1 % du PIB), et le filtre des impacts de l'orchestrateur (|Δ| ≤ 0,1 Md€ et effets micro ≤ 10⁻⁴) — qui comptait le BUDGET d'un petit levier sans son multiplicateur, ni son effet direct sur le chômage, ni son impact TVA : c'est lui qui faisait « apparaître » la prévention de `im_rabot_2029` à 7,6 Md€. Ce filtre ne décide plus que de ce que l'API PUBLIE (`measure_impacts`, identique sur les 44 cas du golden master) ; le moteur lit tous les leviers évalués. Effet sur les scénarios publiés : au plus 0,02 pt de dette 2035 (Écologistes −0,02, Renaissance +0,01) ; la variante ASU « à coût constant » coûte +0,46 pt au lieu de +0,59 (son effort de 0,08 % du PIB a désormais son effet prix). Après les deux corrections, le balayage complet ne trouve plus aucun saut au-dessus de 0,001 pt (460 balayages × 41 points), hors interrupteurs 0/1. Verrouillé par `tests/test_portes_activation_v067.py`. Limite de l'outil, déclarée : le balayage repère un saut par contraste avec ses voisins ; la porte TVA, noyée dans la pente de la TVA, a été trouvée par lecture du code, pas par lui.

### Calendrier de l'impulsion (lot 6, équation, 16/11/2026, non publiée)

**Le défaut.** Jusqu'au lot 6, la croissance de l'année t était calculée AVANT les mesures de t et ne lisait que
l'impulsion du budget de t−1 (`_last_impacts`) : une mesure n'agissait sur le PIB, et donc sur les recettes et le
chômage qu'elle entraîne, qu'à partir de l'année qui suit son premier budget. Effet nul l'année du premier budget,
pour toutes les familles (dépense courante, transferts, investissement, impôts, coefficients propres) et dans les
deux modes. Le code présentait ce retard comme un « lag standard » qui « casse la circularité mesures → macro →
flux → mesures sans recherche de point fixe » ; aucune source n'était citée. Les coefficients étant calés sur un
niveau « quatre ans après » (`MULT_CIBLE_NIVEAU_4ANS`), le niveau visé était atteint à cet horizon, mais toute la
trajectoire arrivait un an trop tard : dans la fenêtre publiée (programme qui commence en 2028, lecture en 2032),
une année d'effet sur cinq manquait, et le budget de la dernière année n'agissait pas dans la fenêtre.

**Ce que disent les sources (rouvertes le 16/11/2026).** Toutes donnent un effet l'année du choc ; aucune ne donne 0.

| Source | Choc | Année du choc | Années suivantes | Ce que la source ne dit pas, ou fixe |
|---|---|---|---|---|
| FMI, *World Economic Outlook*, oct. 2014, ch. 3, tableau 3.4 (p. 95), colonne (1) ; texte p. 82 | investissement public, +1 point de PIB, non anticipé (erreur de la prévision OCDE d'automne de la même année) ; 17 économies avancées, 1985-2013, projections locales annuelles | +0,46 (« about 0.4 percent in the same year ») | +0,76 ; +1,04 ; +1,39 ; +1,54 (k = 1 à 4) | k = 0 = année du choc ; la trajectoire de l'investissement après le choc n'est pas publiée (persistance inconnue) ; politique monétaire historique ; l'équation (3.4) imprimée écrit y(t+k) − y(t), qui annulerait k = 0 : les figures, qui partent de 0 en k = −1, indiquent une normalisation sur l'année d'avant (lecture déduite) |
| même chapitre, simulations du modèle GIMF (p. 87) | investissement public permanent, +1 % du PIB | « about 2 percent in the same year » | | taux directeurs près de zéro pendant deux ans |
| Mésange 2017 (Insee et DG Trésor, document de travail G2017/04), p. 102 | investissement public, +1 point de PIB en volume, permanent, non financé | +1,31 | 2 ans +1,38 ; 3 ans +1,22 ; 5 ans +0,93 ; 10 ans +0,57 | choc « effectif au 1er trimestre » (p. 100) ; taux d'intérêt réels et changes nominaux constants |
| Mésange 2017, p. 105 | dépense publique générique, 1 point de PIB | +0,78 | +1,06 ; +1,03 ; 5 ans +0,86 ; 10 ans +0,53 | idem ; solde primaire −0,53 point la première année |
| Mésange 2017, p. 112, 115 et 117 | hausse de TVA ; baisse de CSG ; baisse d'impôt sur le revenu, « 1 % du PIB ex ante » (p. 100) | −0,32 ; +0,41 ; +0,41 | 5 ans −0,81 ; +0,81 ; +0,81 | idem |
| OFCE, *Revue de l'OFCE* n° 116, janvier 2011, « Petit précis de politique budgétaire par tous les temps », tableau 5, p. 83 | baisse durable de prélèvements ou hausse de dépenses, 1 point de PIB, milieu de cycle | +0,8 (TVA) à +1,2 (investissement, emploi public) | 5 ans +0,6 à +1,3 ; 10 ans +0,2 à +0,7 | politique monétaire « exogène et neutre » ; trimestre d'entrée non précisé |
| OFCE, policy brief n° 17, 2017, tableau 5 (p. 14) et p. 15 | baisse permanente de 1 point de PIB de la dépense, « dès la première année » | −0,6 ; investissement +1,1 | −0,9 ; −0,9 ; −0,7 ; −0,6 | politique monétaire non précisée |
| méta-analyse citée pour les cibles (*Oxford Economic Papers* 67(3), 2015 ; version IMK WP 117, 2013) | 104 études | ne publie pas de profil annuel | multiplicateurs plus élevés aux horizons longs | les multiplicateurs d'impact y sont des multiplicateurs cumulés d'horizon un trimestre |

**Règle retenue : effet plein l'année du premier budget.** L'impulsion du budget de t entre dans la croissance de
t avec le premier terme de son profil (âge 0), comme celles des budgets suivants. Mésange fait démarrer ses chocs au
premier trimestre de la première année, et le moteur chiffre chaque mesure en année pleine (montants annuels d'un
budget qui s'applique au 1er janvier). Aucune des sources consultées ne porte de convention « demi-année » ; une
mesure qui entrerait en vigueur en cours d'année n'est pas représentable, le moteur n'ayant pas de calendrier
infra-annuel (limite).

**La correction.** Chaque année, le bloc « demande » (croissance, prix, PIB, chômage, flux organiques, mesures)
tourne d'abord avec l'impulsion de son propre budget nulle, sur une copie profonde de l'état du simulateur ; il rend
l'effort de chaque flux de chaque levier, en part du PIB nominal de cet état ; la copie est jetée
(`_niveaux_hors_effet_propre`). Le bloc tourne ensuite pour de bon avec l'impulsion de ce budget, variation de ces
efforts par rapport au budget précédent, âge 0 de son profil (`_demande_de_l_annee`) ; les mesures publiées sont
évaluées à l'état final de l'année. C'est la valorisation qu'avait l'impulsion avant le lot — le budget de t−1
évalué à l'état de t−1, avant son propre effet — appliquée l'année même : seul le calendrier change. L'impulsion
est ainsi « ex ante » au sens des variantes publiées (Mésange 2017 : chocs fiscaux « à hauteur de 1 % du PIB ex
ante », p. 100) : la variation du rendement d'une mesure due à son propre effet sur l'activité joue sur le solde,
pas sur l'impulsion, comme les stabilisateurs automatiques du moteur. Le calcul est exact (ni tolérance ni
itération), déterministe et sans point de départ arbitraire. Les avis du rapport sont posés hors de la
déduplication du journal, que l'évaluation partage (un avis posé sous elle était perdu : celui d'une formule côté
recettes). Garde : `tests/test_calendrier_impulsion.py` (effet plein de la première année pour chaque famille et
dans les deux modes, impulsion ex ante, aucune trace de l'évaluation dans l'état ni dans le rapport).

**Pistes écartées.** (a) **Point fixe** sur la boucle annuelle (efforts évalués à l'état final, impulsion « ex
post ») : 1 à 8 itérations par année à 10⁻¹³ près, un temps de calcul multiplié par 5 au mieux (22 dans le
prototype mesuré) ; il change la définition de l'impulsion en plus du calendrier, et rend la consolidation plus
coûteuse et la relance moins porteuse à la fois (efforts rapportés à un PIB que leur propre effet a déplacé) ; écart
à la correction retenue, mode cadre, coefficients recalés : au plus 0,09 point de dette 2032 et 0,006 point de
croissance moyenne 2028-2032. (b) **Réordonnancement simple** (mesures évaluées une seule fois, hors effet propre, et publiées telles
quelles) : aucun surcoût, mais les montants publiés de l'année seraient évalués à un PIB qui n'est pas celui de
l'année, l'écart entre numérateur et dénominateur que la refonte « assemblage temporel » a corrigé ; écart mesuré :
au plus 0,02 point de dette 2032. (c) **Demi-année** : aucune source.

**Coût de calcul.** Le bloc « demande » tourne deux fois par année : une simulation passe de 15 à 31 ms en mode
cadre (médiane des dix programmes publiés, machine de développement), soit ×2,0.

**Ce qui n'a pas changé de calendrier (limites déclarées).**
- **Effets directs des mesures sur le chômage** (`impacts['chomage']` : coût du travail, SMIC, allocations,
  allègements) : toujours lus avec un an de retard. Ce retard ne se justifiait que par la cohérence avec l'ancienne
  impulsion ; c'est désormais une convention qu'aucune des sources consultées ne porte (Mésange 2017, baisse des
  cotisations employeurs de 1 % du PIB : chômage −0,35 point dès la première année, p. 107 ; cotisations salariés :
  −0,10, p. 110) ; sens : l'effet emploi de ces leviers arrive un an tard, dans les deux sens. Ordre de grandeur,
  mesuré à la revue du lot (effets directs lus la même année, à partir des impacts évalués hors effet propre ;
  coefficients recalés) : de −0,06 à +0,09 point de dette 2032 selon le programme publié, et 0,05 point de chômage
  2032 au plus.
- **Passage d'une hausse de TVA dans les prix** : l'année qui suit son entrée en vigueur, conséquence de l'ordre de
  calcul (les prix de l'année sont calculés avant ses mesures), sans source ; sens : la hausse des prix, et l'érosion
  du pouvoir d'achat qu'elle entraîne, arrivent un an tard pour tout programme qui relève la TVA. Au 16/11/2026,
  aucun des dix programmes publiés ne modifie la TVA : la limite ne joue que dans le simulateur.
- **Effet d'offre** (`update_potential_growth`) : il clôt l'année, son bonus agit l'année suivante, après les délais
  propres à chaque canal ; à instruire avec ces délais.
- **Domaine de la croissance dès la première année** : l'effet de la première année arrivant l'année du budget, la
  croissance peut dépasser +2,5 % (`CROISSANCE_FILET_MAX`, borne de validité des multiplicateurs linéaires) cette
  année-là. En mode historique (non publié), deux des dix programmes publiés en sortent dès leur première année
  (2026), contre un seul, la deuxième année, avant ce lot ; en mode cadre (publié), aucun. Depuis le retrait de
  l'écrêtage (arbitrage du mainteneur du 16/11/2026), un avis le signale et la hausse et la baisse d'un même gros
  choc restent en miroir (`tests/test_symetrie_depense_courante.py`) ; jusque-là, le filet les en écartait de la
  part écrêtée exactement.
- **Taxe sur les transactions financières, mode historique** : son assiette, sourcée en 2026, suit le PIB nominal
  depuis cette année ; en mode historique, 2026 est aussi la première année du programme, dont l'effet entre
  désormais dans ce PIB d'ancrage (seul ce levier, seul ce mode ; le mode cadre commence après 2026).
- **Forme de la première année par famille**, comparée aux sources (tableau ci-dessous) : l'investissement suit le
  FMI (0,46 ; paragraphe « Profil de l'investissement » ci-dessous) et reste sous les modèles français (Mésange
  1,31, OFCE 1,1 à 1,2) ; la dépense courante est proche de Mésange (0,69 contre 0,78) ; les impôts sont au-dessus
  de Mésange (0,57 contre 0,32 à 0,41) et sous l'OFCE 2011 (0,8 à 1,1). Hors investissement, le profil de chaque
  famille (`DECAY_PROFILE_*`) n'est pas recalé : la forme, et non le seul niveau à 4 ans, reste à instruire.
- **Retour au solde la première année** : pour un point de PIB de dépense, le moteur rend désormais 0,24 à 0,36 €
  par euro la première année (recettes induites), contre rien avant ; Mésange en rend environ la moitié (solde
  primaire −0,53 pour la dépense générique, −0,49 pour l'investissement), l'OFCE 2017 environ 0,3.
- **Coefficients propres** (SMIC 0,15, fraude fiscale −0,40) : présents depuis la première version publique, ils ne
  sont calés sur aucun niveau mesuré à un horizon dans le moteur complet ; ils ne sont pas recalés (leur niveau à
  4 ans baisse comme celui des autres familles avant recalage : SMIC 0,10 → 0,08, fraude −0,38 → −0,34). Recalés
  comme leur famille de profil (transferts × 0,785 / 0,688, impôts × 0,674 / 0,615), ils déplaceraient la dette 2032
  des programmes publiés de 0,03 point au plus (mesuré à la revue du lot). À trancher. Celui du SMIC est retiré
  depuis (lot SMIC, § SMIC) ; reste celui de la fraude fiscale.

**Recalage des coefficients (lot 6, release de paramètres, 16/11/2026, non publiée).** À coefficients inchangés, la
correction du calendrier faisait baisser le niveau à 4 ans du banc de 9 à 13 % : la trajectoire n'est plus décalée
d'un an, et le niveau « quatre ans après » est désormais celui de la cinquième année d'effet. Les cibles
(`MULT_CIBLE_NIVEAU_4ANS`) ne changent pas ; chaque coefficient est recalé, par la méthode de la sécante sur le banc
de `tests/test_multiplicateurs_centraux_v067.py`, pour que sa famille retrouve son niveau à 4 ans d'avant le lot :
investissement 1,2 → **1,31** (1,4098 visé, 1,41 atteint ; la cible 1,5 reste à −6 %, dans la tolérance de 10 %,
comme avant), dépense courante 0,74 → **0,811** (coupe 0,794), transferts 0,688 → **0,785** (0,650), impôts 0,615 →
**0,674** (hausse 0,646 ; la baisse reste au coefficient de la hausse). Le lot change le calendrier, pas les niveaux :
le recalage sur les niveaux d'avant isole l'effet du calendrier ; recaler l'investissement sur sa cible de 1,5
plutôt que sur 1,41 serait une décision distincte. SMIC et fraude fiscale ne sont pas recalés (ci-dessus).

**Profil de l'investissement calé sur le FMI (lot 6, release de paramètres, arbitrage du mainteneur).** Le moteur
reproduit, année par année, le tableau 3.4, colonne (1), du FMI (*World Economic Outlook*, octobre 2014, chapitre 3,
p. 95) : pour un point de PIB d'investissement public, +0,457 % de PIB l'année du choc, puis +0,755, +1,035, +1,389
et +1,539 quatre ans après (écarts-types de 0,147 à 0,441 ; 17 économies avancées, 1985-2013 ; le choc est l'erreur
de la prévision d'investissement public de l'OCDE d'automne pour la même année, en part du PIB). La cible porte sur
l'effet TOTAL, demande et capacité de production, qu'estime le FMI : le chemin de la demande seule et celui du canal
d'offre du capital public (`SUPPLY_EFFECTS`), ensemble, l'atteignent pour un levier de capital public.
- **Protocole de calage** : mode historique, choc permanent de 1 % du PIB par an dès 2026, levier de référence à
  canal d'offre actif : la transition écologique (impulsion de demande sur le levier, canal d'offre alimenté par son
  paramètre « investissement », constant, égal à 1 % du PIB nominal 2026). Le coefficient reste 1,31 ; les cinq
  premiers termes du profil `DECAY_PROFILE_INVEST` sont recalés, (0,45 ; 0,65 ; 0,45 ; 0,25 ; 0,12) →
  (0,3718 ; 0,3152 ; 0,3487 ; 0,3495 ; 0,2201). Cinq termes pour cinq valeurs : l'ajustement est exact PAR
  CONSTRUCTION, quel que soit le protocole ; la garde (`tests/test_multiplicateurs_centraux_v067.py`) est une garde
  de non-régression, pas une validation. Sa précision (0,0005 point) vaut pour ce protocole seulement : le mode
  publié, la taille du choc et l'entrée du canal d'offre déplacent la cinquième année de 0,015 à 0,036 point
  (limites ci-dessous), quand l'écart-type de la source y est de 0,441.
- **Ce que la source ne dit pas** : la persistance du choc (la trajectoire de l'investissement après le choc n'est pas
  publiée ; le « permanent » du protocole est une lecture du moteur) ; le partage entre demande et capacité de
  production (le chapitre décrit les deux canaux sans décomposer son estimation : le partage est celui du moteur) ;
  la recherche. Aucune estimation au-delà de quatre ans après le choc : le moteur conserve sa décroissance
  antérieure (dernier terme du profil inchangé, puis rappel vers le potentiel). Les simulations du modèle du FMI
  présentées dans le même chapitre ne sont publiées qu'en graphiques ; elles ne servent pas au calage.
- **Comparaison à Mésange** (2017, p. 102, variante d'investissement public, « pur choc de demande », taux réels
  constants) : Mésange est plus haut la première année (1,31 contre 0,46) et plus bas ensuite (5 ans : 0,93 contre
  1,54). Le moteur suit l'estimation empirique du FMI, pas le modèle français.
- **Limites déclarées.** (1) Mode : le même choc en mode cadre (choc posé en 2028), 1,40 et 1,56 les deux dernières
  années du chemin (au lieu de 1,389 et 1,539 ; les trois premières à 0,006 près). (2) Taille : le canal d'offre est
  plafonné et rend moins par euro quand le montant grandit : 1,57 à quatre ans pour un choc de 0,5 % du PIB, 1,50
  pour un choc de 1,5 %. (3) Leviers : le profil est commun à toutes les dépenses d'investissement ; seul un levier
  dont le canal d'offre agit dans les quatre ans reproduit le tableau (transition écologique, part investissement
  des collectivités). L'éducation (délai de son canal d'offre : 15 ans) et la rénovation (canal nul) n'ont, sur
  cet horizon, que la demande seule : 1,26 et 1,28 les deux dernières années, contre 1,39 et 1,54. La recherche,
  en forme stock depuis le lot 2, a un canal d'offre actif dès l'année qui suit la dépense, hors du plafond : son
  total dépasse le tableau : 3,19 et 3,62 les deux dernières années, pour une demande seule de 1,26 et 1,28 (le
  double compte de la demande et de l'offre déclaré au lot 2). Conséquence du calage, pas règle choisie : à instruire. Enjeu, mesuré à la
  revue du lot (un profil propre donnant à leur demande seule le total du FMI) : la dette 2032 baisserait de 0,2 à
  0,3 point pour les deux programmes publiés qui relèvent le plus ces dépenses, de 0,07 point au plus pour les
  autres, sans changer aucun rang de dette. Ce qui trancherait : la classification comptable de chaque levier
  (investissement, consommation publique, transferts en capital), qui dit si le tableau du FMI s'applique à lui,
  puis des estimations d'effet par fonction (éducation, recherche). (4) Entrée du canal d'offre : l'impulsion de
  demande vaut 1 % du PIB de chaque année, le canal d'offre est alimenté par un montant constant, 1 % du PIB
  nominal 2026 ; alimenté par 1 % du PIB nominal de 2030, la cinquième année vaut 1,56 au lieu de 1,539 (+0,019).
  (5) Couplage : le profil de la demande est calé PAR DIFFÉRENCE avec le canal d'offre du capital public. Toute
  révision des paramètres de ce canal (pente, délai, dépréciation) impose de recaler le profil, et change donc la
  demande des leviers qui n'ont pas ce canal ; la garde rougit (vérifié pour une pente × 1,05 et un délai de 2 ans
  au lieu de 3). La santé et la réforme de l'État ne portent pas ce profil : dépenses courantes, elles prennent le
  coefficient et le rythme de la dépense courante (option du lot 6, équation, encadré « Rythme de la dépense
  courante » ci-dessous).
- **Cumul des cinq premières années** (choc posé en 2028, mode cadre, somme des niveaux H0 à H4 ; Mésange « 4 ans »
  pris au milieu de « 3 ans » et « 5 ans ») : un levier à canal d'offre actif est à +0,8 % du FMI et à −11,8 % de
  Mésange ; un levier sans canal d'offre, à −6,9 % et −18,6 % (sans l'option du rythme de la dépense courante, qui
  change le droit en vigueur de la santé dans l'état de départ : +0,6 %, −12,0 %, −7,1 % et −18,7 %). Mésange simule un choc permanent, le FMI une
  innovation d'une année dont la persistance n'est pas publiée : une partie de l'écart de rythme peut venir de la
  nature du choc.

**Rythme de la dépense courante (option du lot 6, équation, retenue par arbitrage du mainteneur du 16/11/2026).** La santé et la
réforme de l'État prennent le coefficient de la dépense courante depuis la v0.6.0 : « consommation/optimisation
publique », hors du canal de l'investissement productif. Elles en prennent désormais aussi le rythme
(`DECAY_PROFILE_TAXES`, celui de toute dépense courante) : elles sortent de `INVESTMENT_FLOW_MEASURES`, qui garde le
même périmètre que le canal de l'investissement (éducation, recherche, transition écologique). Le classement
d'origine date de la première version publique, avec pour seul motif un commentaire (« flux de dépenses
productives chaque année ») ; aucune source dans l'historique du dépôt. Effet, pour un point de PIB permanent
(banc historique) : 0,69 point de PIB la première année au lieu de 0,28, 0,79 à 4 ans au lieu de 0,77 ; leur
chemin est, au bit près, celui d'un levier de dépense courante de même coefficient, dans les deux sens et les deux
modes (`tests/test_symetrie_depense_courante.py`). Conséquence, déclarée : le curseur de prévention fait passer le
ratio de dette sous le statu quo les deux premières années, comme toute dépense courante de même montant (au
maximum du curseur, −0,019 puis −0,007 point en mode historique, −0,024 puis −0,014 en mode cadre), par le
dénominateur ; la dette en euros reste au-dessus du statu quo chaque année, et le ratio dès la troisième année
(`tests/test_prevention_v061.py`, deux modes).

**Profils par famille** (choc permanent d'un point de PIB posé au premier budget, mode cadre 2028 ; PIB en volume,
écart en % au cas sans choc ; H0 = année du premier budget, H4 = « quatre ans après » ; coefficients recalés ;
profil de l'investissement calé sur le FMI, dont le levier de capital public ajoute son canal d'offre à cette
demande).

| Famille | H0 | H1 | H2 | H4 | H9 | Avant le lot 6 (H0 ; H4) | Sources, année du choc ; 5ᵉ année |
|---|---|---|---|---|---|---|---|
| Dépense courante | 0,69 | 0,94 | 0,98 | 0,80 | 0,20 | 0,00 ; 0,80 | Mésange 0,78 ; 0,86 |
| Transferts | 0,67 | 0,91 | 0,88 | 0,66 | 0,12 | 0,00 ; 0,65 | OFCE 2011 (prestations) 1,0 ; 0,9 |
| Investissement, demande seule | 0,46 | 0,76 | 1,04 | 1,29 | 0,41 | 0,00 ; 1,42 | FMI (total) 0,46 ; 1,54 — Mésange 1,31 ; 0,93 |
| Hausse d'impôts | −0,57 | −0,78 | −0,81 | −0,66 | −0,12 | 0,00 ; −0,65 | Mésange (TVA) −0,32 ; −0,81 |

### DECAY_PROFILE (Profil Temporel Differencie v3.1)

Depuis la v3.1, le simulateur utilise **3 profils de decroissance** differencies selon le type de mesure budgetaire, au lieu d'un profil unique. Depuis la v0.6.7, chaque impulsion porte le profil de SON levier (`_get_decay_profile`) — plus de mélange pondéré à l'échelle du programme.

**Profil TAXES** — pour les mesures fiscales (TVA, IS, IR, CSG, etc.) :
```
TAXES = (0.90, 0.50, 0.30, 0.15, 0.10, 0.05)  — somme = 2.00
```
Impact rapide et fort la premiere annee, decroissance classique.

**Profil TRANSFERS** — pour les transferts sociaux (retraites, allocations, dépense d'une hausse du SMIC ; les recettes du SMIC prennent le profil TAXES, `RECETTES_AU_PROFIL_DES_IMPOTS`) :
```
TRANSFERS = (0.90, 0.50, 0.20, 0.10, 0.05, 0.02)  — somme = 1.77
```
Effet total plus faible car les transferts sont partiellement epargnes.

**Profil INVEST** — pour les investissements productifs (education, transition ecologique, recherche) :
```
INVEST = (0.3718, 0.3152, 0.3487, 0.3495, 0.2201, 0.06)  — somme = 1.6653
```
Lot 6 (release de paramètres, arbitrage du mainteneur) : les cinq premiers termes sont calés pour que le total (demande et canal d'offre) d'un levier de capital public reproduise le tableau 3.4, colonne (1), du FMI (WEO oct. 2014, ch. 3, p. 95), année par année ; dernier terme inchangé (aucune estimation au-delà de quatre ans). Jusque-là : (0.45, 0.65, 0.45, 0.25, 0.12, 0.06), somme 1,98, « pic décalé à l'année 2 » (convention de la v3.1, sans calage à une source).

**Sources** : profil INVEST, FMI, WEO oct. 2014, ch. 3, tableau 3.4 (lot 6). Profils TAXES et TRANSFERS : convention de la v3.1, citée jusque-là avec IMF 2014, Blanchard & Leigh 2013 et Ramey 2019 sans calage à une valeur de ces sources (non rouvertes au lot 6).

**Plus de plafond de taille (v0.6.7)** : le plafond « effort ≤ 2 % du PIB » est retiré (cf. L5). Le clip de croissance [−3,5 % ; +2,5 %] qui restait est retiré à son tour (arbitrage du mainteneur du 16/11/2026) : il ne fait plus qu'un avis.

> **Note — ce qui N'EST PAS en production.** Un mecanisme de *re-impulsion annuelle* (dit « Type B » : chaque tranche annuelle d'investissement aurait genere une nouvelle impulsion de demande, en plus de l'impulsion declenchee au changement de curseur) a ete prototype puis **reverte (commit `11d979e` — « revert annual re-impulse, keep differentiated decay profiles only »)**. Il n'est **pas actif** : il re-multipliait le NIVEAU de la dépense chaque année, donc la comptait plusieurs fois. La v0.6.7 fait l'inverse : seule la VARIATION annuelle de l'effort est une impulsion, si bien que la somme des impulsions d'un levier égale exactement son niveau — chaque euro est multiplié une fois (`tests/test_impulsions_v067.py`).

### Taux d'Interet (v0.6.0 : ancre + spread, audit externe 08/2026)

**Architecture** : `taux_marginal(dette, effort) = ancre_zone_euro + spread_France`.
Toute la litterature estime l'effet de la dette sur le SPREAD, jamais sur le
taux total ; l'ancre zone euro (2,65 % = Bund 10 ans 3,24 % - 59 pb de coin de
maturite, calage 08/2026) est une constante exogene datee — le moteur ne
prevoit pas la politique monetaire (choix de design assume).

**Table d'ancrage du taux marginal** (point observe : 3,47 % au ratio de dette
117,6 % — taux moyen pondere des emissions MLT, AFT aout 2026) :

| Dette/PIB | Taux marginal | Statut |
|-----------|---------------|--------|
| 100 % | 2,94 % | interpole, source |
| 115 % | 3,39 % | interpole, source |
| **117,6 %** | **3,47 %** | **ancre observee (AFT)** |
| 130 % | 4,09 % | interpole, source |
| 150 % | 5,19 % | borne haute du domaine estime |
| 170 % | 6,79 % | EXTRAPOLATION assumee (aucune estimation > ~180 %) |

Pentes du spread : 2 pb/pt (< 90 %), 3 pb/pt (90-120 % — solide : Laubach 2009,
Pamies et al. 2021, Baldacci-Kumar 2010), 5,5 pb/pt (120-150 %), 8 pb/pt
(> 150 %, extrapolation calee sur episodes — Portugal 2011, spread 459 pb).
Plafond absolu de stress : 8 % (borne, pas une prevision). Supprimes v0.6.0,
avec source : remise BCE inconditionnelle a > 150 % de dette (le TPI exige de
ne PAS etre en procedure de deficit excessif — la France y est, BCE
21/07/2022 ; la courbe v5.1 etait de fait NON monotone : franchir 150 %
BAISSAIT le taux), terme calendaire, falaise +100 pb (vecu 2024-2026 : +21 pb).

**Prime d'effort budgetaire** : 20 pb par point de PIB d'effort (FMI WEO
oct. 2010 ch. 3 ; Furceri et al. 2025 ; Laubach 2009 ; vecu France 2024-2026 :
15-21 pb), amplifiee par la dette au-dela de 90 % (ACL), continue, symetrique
jusqu'aux plafonds — plafond de bonus -45 pb (mission IGF 07/2026, encadre 4),
cap de malus +60 pb (~2x le pic France 2024-2026). Limitation assumee :
`effort_budgetaire` est un NIVEAU d'effort vs baseline, pas un flux annuel —
le cumul partiel avec le deplacement le long de la courbe de dette est borne
par ces plafonds (cf. choix de design).

**Charge d'interets** : le stock herite (amorce 2,0 % en 2026, perimetre toutes
APU — coherent avec le taux apparent 2,2 % de la mission IGF) se reprice au
taux marginal selon un profil LINEAIRE approxime : demi-vie de repricing =
maturite/2 = 4 ans (maturite moyenne 8 ans, AFT). Le taux apparent remonte
ainsi de 2,2 % vers ~3,1 % en 2030, comme dans le tendanciel officiel.

**Fait non reproduit (documente)** : la Grece (dette ~143 %) emprunte en 2026
MOINS cher que la France — les marches pricent la trajectoire ANTICIPEE, pas
le ratio courant. Une courbe assise sur le ratio courant ne peut pas
reproduire ce fait ; le plafond de bonus -45 pb (source mission) prime.

### Inflation et Courbe de Phillips

Le moteur modelise l'inflation par une **courbe de Phillips ANCREE**, forme `output_gap` uniquement (evite le double-comptage avec la loi d'Okun qui correle deja chomage et croissance).

**Decomposition annuelle (v4.1, aout 2026) :**
```
Inflation = (1 - 0,5) × (1,6% + 0,20 × Output gap) + 0,5 × Inflation precedente + Passage de la TVA dans les prix + Garde-fous BCE
```
soit, pour un output gap constant, un point fixe `pi = 1,6% + 0,20 x gap`.

| Composante | Valeur | Source |
|-----------|--------|--------|
| **Point fixe (terme tendanciel)** | (1 - inertie) × 1,6% | **Deflateur du PIB** tendanciel France (voir « Ce que mesure la variable inflation » ci-dessous). Chaine d'ancrage sourcee maillon par maillon : 2,0% IPCH zone euro (BCE, Survey of Professional Forecasters T3 2026 — anticipations de long terme inchangees malgre un IPCH 2026 a 2,7-3,0%) -> ~1,75% IPC France (Gouvernement, Rapport d'avancement annuel 2026 du PSMT 2025-2029, **note 6**, qui ecrit l'ecart explicitement) -> ~1,6% deflateur (INSEE, blog « Inflation : les deflateurs en comptabilite nationale », sept. 2022 ; decomposition RAA 2026 p. 12). Constante `INFLATION_STRUCTURELLE`. **Correction v4.0** : dans un AR(1) `i(t) = c + rho × i(t-1)`, le point fixe est `c/(1-rho)`, pas `c` — l'intercept a ete mis sous `(1-rho)`. |
| **Inertie** | 50% × inflation precedente | Terme AR(1) — anticipations + indexation. Depuis la v4.1 c'est un parametre de **vitesse** seulement : il ne deplace plus le niveau du regime etabli. Ancrage sourcee : BdF Billet de blog n° 335 (dec. 2023) — dans les pays sans clause d'indexation, dont la France depuis 1983, la transmission de l'inflation realisee aux anticipations tombe sous 1/3 de sa valeur de court terme aux horizons longs. Seed annee 0 = `INFLATION_BASE = 1,0%` (distinct du point fixe : c'est l'initialisation de la chaine recursive). |
| **Output gap** | **pente de moyen terme 0,20** × ecart au potentiel, DANS l'ancrage | `PHILLIPS_PENTE_MT`. **Correction v4.1** : le terme de gap etait reste HORS de l'ancrage (coefficient 0,35), ce qui faisait de rho un multiplicateur cache — la grandeur homologue de la litterature valait 0,35/0,50 = 0,70, ecrite nulle part. Depuis, le parametre du code EST la pente de moyen terme. **A declarer : choix de calibration ENCADRE, pas une estimation France** (il n'en existe aucune sur l'output gap). Bornes : BdF, *Rue de la Banque* n° 56 (fev. 2018), pente 4c2/(1-c1) ~ 0,40 (zone euro) ; BCE, ECB WP n° 3133 (oct. 2025), ~0,065 converti sur l'output gap. Motif du 0,20 : le gap est negatif sur tout l'horizon des scenarios francais, donc sur le segment plat au sens de Benigno-Eggertsson. |
| **Ajustement effort budgetaire** | **RETIRE (lot 1, 15/11/2026)** — etait : consolidation -0,12 × effort / expansion +0,08 × \|effort\| | Dette declaree depuis la v4.1 (non source, asymetrique, double compte avec l'output gap), instruite et retiree sans remplacement. Aucun des modeles institutionnels lus (Mesange, ThreeME, modeles du SEBC : Kilponen et al. 2019) n'a de terme direct de l'effort global sur les prix : l'effet y passe par la demande, ce que fait deja la pente sur l'output gap. Les etudes empiriques lues mesurent un effet total ; celle de Checherita-Westphal & Pesso (BCE WP 2996, 2024) trouve une reponse des prix aux relances amplifiee quand la dette est haute : **limite declaree**, le moteur ne la modelise pas (sens probable : inflation des relances sous-estimee a la dette francaise), et l'ancien terme, independant de la dette, ne la representait pas. Applique a un NIVEAU d'effort, le terme faisait deriver le niveau des prix sans fin (choc permanent d'un point de PIB : ecart d'inflation de +0,12 a -0,19 point a 20 ans, l'output gap referme). Le budget ne touche plus les prix que par l'output gap et par le passage de la TVA. Effet et garde : § « Terme d'effort de l'inflation retire (lot 1) » ci-dessous, `tests/test_inflation_sans_terme_d_effort.py`. |
| **Garde-fou BCE haut** | Si inflation > 2,0% (cible BCE, `BCE_CIBLE_INFLATION`) → blend 50/50 vers la cible | Garde-fou de SURCHAUFFE (v4.0) : contient l'inflation au-dessus de la cible. Ne se declenche pas en statu quo. |
| **Garde-fou BCE bas** | Si inflation < 0,8 % (`BCE_PLANCHER_ACCOMMODANT`) → blend 70/30 vers la TENDANCIELLE 1,6% | Politique monetaire accommodante, tiree vers le point fixe du regime. **v4.1** : ce plancher se declenchait DES L'ANNEE 1 du statu quo (0,725% pre-garde -> 0,95% publiee), c'est-a-dire que la calibration etait portee par un clip. Les deux garde-fous sont desormais INERTES en statu quo, verifie par test. |

> **Terme d'effort de l'inflation retiré (lot 1, 15/11/2026, non publié).** Jusqu'à v0.8.1, `calculate_inflation`
> ajoutait −0,12 × effort (consolidation) ou +0,08 × |effort| (expansion), l'effort étant l'écart du solde de
> t−1 au statu quo en part du PIB. Revue des sources de novembre 2026 : aucun des modèles institutionnels lus
> (Mésange 2017 ; Largier et al., OFCE WP 2026-9, Mésange et ThreeME ; Kilponen et al. 2019, quinze modèles du
> SEBC) n'a de terme direct de l'effort global sur les prix ; les effets directs documentés sont propres à des
> instruments (TVA, déjà modélisée ; prix administrés de l'énergie). Les études empiriques lues mesurent un effet
> total, sans séparer effet direct et effet de demande : Auerbach & Gorodnichenko 2017 (niveau des prix, réponse
> non significative) ; Checherita-Westphal & Pesso (BCE WP 2996, 2024), dont le résumé conclut que « high debt
> levels tend to amplify the inflation response to fiscal expansions ». **Limite déclarée** : le moteur ne modélise
> pas cette amplification ; sens probable, une inflation des relances sous-estimée à la dette française. L'ancien
> terme ne la représentait pas : il ne dépendait pas de la dette et il était plus fort pour les consolidations.
> Banc (choc permanent d'un point de PIB de dépense courante, hausse puis baisse, statu quo, mode historique ; écart
> du niveau des prix, le déflateur, au statu quo) : en v0.8.1, avec le terme, +1,05 / −1,33 % à 5 ans et
> +3,53 / −4,69 % à 20 ans, écart d'inflation résiduel de +0,12 à −0,19 point à 20 ans ; sans lui (mesure du moteur
> actuel) : +0,76 / −0,76 % à 5 ans, +1,49 / −1,48 % à 20 ans, écart d'inflation ≤ 0,02 point à 20 ans
> (lot 5 : la hausse de dépense courante prend le coefficient de sa baisse ; +0,51 et +1,26 avant, la hausse au
> coefficient des transferts ; lot 6 : l'effet sur l'activité commence l'année du choc, l'écart de production
> s'ouvre un an plus tôt et les prix ont une année de plus pour réagir à 5 ans, puis le coefficient est recalé —
> +0,55 / −0,54 avant le lot).
> **Limite déclarée** : à 5 ans, le moteur répond en prix moins que les deux modèles français publiés pour un choc
> comparable, environ 85 % de ThreeME (0,89 %) et la moitié environ de Mésange (1,3 à 1,5 %) ; sens :
> l'effet des budgets sur les prix est probablement sous-estimé, pour une relance comme pour une consolidation. Les
> études empiriques lues trouvent une réponse plus faible et non significative, et les modèles du SEBC la disent
> « rather contained ». Avec le terme, la hausse se rapprochait des modèles français, mais par un effet sans source,
> plus fort pour les consolidations et qui dérivait sans fin. La pente de la courbe de Phillips sur l'écart de
> production (0,20), qui porte désormais seule cette réponse, est à instruire séparément, dans une release de
> paramètres. Ce qui bouge (mode cadre 2028, dette 2032) : le
> terme baissait le PIB nominal des programmes qui consolident et montait celui des programmes qui relancent ;
> sans lui, dette 2032 des dix scénarios publiés de −1,89 point (le plus fort effort de consolidation) à +1,24
> (la plus forte relance) ; déficit 2032 au plus ±0,16 point ; croissance moyenne 2028-2032 au plus +0,011 point ;
> Gini et compétitivité inchangés. Trois rangs de dette 2032 changent, entre trois scénarios qui se tiennent en
> 0,26 point (dont le scénario de référence, 6ᵉ → 5ᵉ) ; déficit, croissance et Gini : aucun rang ne change.
> Garde : `tests/test_inflation_sans_terme_d_effort.py` (invariance à l'effort, extinction de l'écart
> d'inflation après un choc permanent, réponse des prix symétrique pour les transferts ; chiffres « mesure du
> moteur actuel » du banc et comparaison aux deux modèles français recalculés et cherchés dans ce texte).

**Output gap initial** : le niveau **gap initial de -0,7%** est pose sur l'annee de base (`OUTPUT_GAP_INITIAL`). Sources : Gouvernement, RAA 2026, **Tableau n° 2 p. 20** (avis HCFP n° 2026-3 du 17/04/2026) : -0,7 en 2027 et 2028, -0,5 en 2029 ; variante documentee FMI, *Article IV* PR n° 26/255 du 22/07/2026, Table 1 : -0,4. La v4.0 partait de -1,5%, soit 2 a 4 fois plus bas que les deux estimations officielles, **sans aucune source dans le code**.

**Output gap en NIVEAU, rappel vers le potentiel (v0.6.7, B3 — arbitrage du mainteneur (07/10/2026), audit externe Codex 10/2026, bloc A constat 3)** — deux équations :

```
(1) définition : (1 + gap_t) = (1 + gap_{t−1}) × (1 + g_t) / (1 + g*_t)        [écart du PIB réel à son potentiel, BCE/OCDE/FMI/CE]
(2) croissance : g_t = g*_t − λ × gap_{t−1} + effets de demande (multiplicateurs) + c_t,  λ = OUTPUT_GAP_RAPPEL = 0,2
    sans écrêtage depuis le 16/11/2026 : si g_t − c_t sort de [−3,5 % ; +2,5 %], un avis le signale (§ Écrêtage retiré)
    c_t = CHOCS_DEMANDE_OBSERVES[t] (v0.6.9) : choc de demande observé, 0 si l'année est absente de la table, hors du contrôle du domaine
```

**Colonnes publiées du potentiel** (détail annuel servi par l'API) : toutes exposent le potentiel **consommé par l'année t** — celui que lisent la croissance (2), la loi d'Okun et la récurrence (1) —, jamais celui préparé pour t+1 par la clôture d'année (hystérèse du tendanciel, bonus d'offre structurelle). `Croissance_Potentielle_Totale %` = g*_t = `Croissance_Potentielle %` (tendanciel) + `Bonus_Potentiel_Supply %` (offre structurelle) + `Bonus_Offre_Travail %` (offre de travail) + traînée de dette (sans colonne propre, déductible par différence à l'arrondi près). L'identité (1) se reconstruit donc depuis les seules colonnes `Output_Gap %`, `Croissance %` et `Croissance_Potentielle_Totale %` : exactement sur les valeurs non arrondies, dans la marge de l'arrondi à 2 décimales sur les valeurs servies (`tests/test_potentiel_publie_v0610.py`).

> **Corrigé en v0.6.10 (contre-audit externe, V2-02)** : jusqu'en v0.6.9, la ligne de sortie relisait l'état APRÈS la clôture d'année ; `Croissance_Potentielle_Totale %`, `Croissance_Potentielle %` et `Bonus_Potentiel_Supply %` publiaient le potentiel de l'année suivante (recherche publique à 20 Md€, 2030 : 1,248 % publié pour 1,048 % consommé ; 7 des 10 programmes publiés touchés, une cellule à ±0,20 pt chacun, l'année où naît le bonus d'offre structurelle). Le moteur photographie désormais le potentiel de l'année avant la clôture et publie cette photographie, en flottant Python toutes les années : une même colonne suivait deux conventions d'arrondi selon l'année (numpy dès 2027). Effet visible de cette uniformisation : en 2026, `Croissance_Potentielle_Totale %` passe de 1,14 à 1,15 pour Horizons, LR et Institut Montaigne (compétitivité) — même valeur 1,145, désormais arrondie au plus proche. Correction d'affichage seule : dette, déficit, croissance, chômage, Gini, pouvoir d'achat et output gap sont identiques au bit.

Sens économique : le **potentiel** g* est la vitesse de croisière ; un écart de niveau est **rappelé** de 20 % par an (persistance 0,8), à la manière de l'équation d'output gap autorégressive des modèles semi-structurels de projection du FMI (forme de l'équation (1) de Berg, Karam & Laxton (2006), « Practical Model-Based Monetary Policy Analysis—A How-To Guide », IMF Working Paper 06/81 : `ygap_t = β_ld·ygap_{t+1} + β_lag·ygap_{t−1} − β_RRgap·(RR − RR*)_{t−1} + … + ε_t` ; ici `λ = 1 − β_lag`, sans terme prospectif ni canal de taux réel. Les auteurs (WP/06/80, vue d'ensemble) citent une fourchette β_lag de 0,5 à 0,9 ; la persistance retenue, 0,8 (λ = 0,2), est un CHOIX dans cette fourchette — aucune source précise ne publie 0,8 pour la France ni pour une équation annuelle d'économie avancée (recherche du 07/10/2026) —, arbitré puis confirmé le 07/10/2026 ; ce n'est pas une estimation France). Le rappel vit dans l'équation de CROISSANCE, pas dans la statistique de gap : c'est le PIB qui revient vers son potentiel, et (1) reste l'identité exacte de l'écart simulé. Conséquences assumées : les effets de NIVEAU des multiplicateurs deviennent transitoires (un choc de demande permanent n'est pas un gain de potentiel ; l'offre passe par les canaux dédiés : capital public `SUPPLY_EFFECTS`, offre de travail seniors), et un effet structurel d'emploi (coût du travail, Bozio-Wasmer) n'est rendu que transitoirement — limite déclarée.

**Ce que cela remplace** : jusqu'en v0.6.6, `gap(t) = 0,8 × gap(t−1) + 0,2 × (croissance − potentiel)`, moyenne mobile de l'écart de CROISSANCE qui effaçait chaque année 20 % d'un écart de niveau réel. La justification écrite ici (« avec l'identité comptable le gap ne se refermerait jamais en statu quo, croissance = potentielle ») avait une prémisse fausse : au statu quo, la croissance restait SOUS le potentiel, de la traînée de dette (−2,0 pts cumulés en 2035) et du bruit tiré (−0,56). L'identité pure seule (variante écartée) le montre : statu quo gap 2034 −2,68 %, dette 2035 164,17 %, régime « récession » permanent dès 2033, sortie du corridor de la mission. Le rappel referme l'écart ; le reclassement de la traînée de dette (ci-dessous) retire la cause de la dérive.

**Traînée de dette = effet d'OFFRE (v0.6.7, B3)** : `debt_drag × (dette/PIB − 0,9)` au-delà de 90 % (coefficient −0,005, compromis Reinhart-Rogoff −0,008 / Herndon-Ash-Pollin −0,003) abaisse désormais la croissance POTENTIELLE de l'année (quatrième terme de `croissance_potentielle_totale()`), que lisent la croissance, la loi d'Okun et l'output gap. La littérature la place sur la croissance de long terme : Kumar & Woo (2010), « Public Debt and Growth », IMF Working Paper 10/174, « the impact of high public debt on long-run economic growth » : +10 pts de dette initiale ↔ −0,2 pt de croissance annuelle du PIB réel par tête, « somewhat smaller in advanced economies », l'effet passant par « a slowdown in labor productivity growth mainly due to reduced investment and slower growth of capital stock » — un canal d'offre. Le coefficient du moteur (−0,05 pt par +10 pts au-delà de 90 %) est quatre fois plus prudent. Jusqu'en v0.6.6 elle frappait la seule croissance effective : Okun la lisait comme un choc de demande (+0,2-0,3 pt de chômage en fin d'horizon) et elle creusait l'écart de production. Verrouillé par `tests/test_output_gap_niveau_v067.py` (identité, rappel exact, au statu quo `g − g*` = rappel, la traînée n'ouvre ni gap ni chômage).

**Conjoncture observée (v0.6.9 — case VIDE)** : deux tables par année calendaire, identiques pour tous les scénarios (`constants.py`). `CHOCS_DEMANDE_OBSERVES` ajoute à la croissance (2) de l'année un choc de demande DÉJÀ CONSTATÉ par la statistique publique, après son calcul et avant tous ses lecteurs (PIB, Okun, recettes, écart de production (1), hystérèse du potentiel) : comme tout choc de demande, il ouvre un écart que la Phillips lit l'année suivante et que le rappel referme ensuite ; il n'est ni une impulsion budgétaire (aucun multiplicateur) ni un choc d'offre, et n'est pas écrêté par le filet de la croissance modélisée (c'est une donnée). `COIN_PRIX_CONSOMMATION`, cumulé en niveau, sépare le prix de la consommation des ménages du déflateur du PIB (termes de l'échange : prix importés) et n'entre que dans le prix de l'indice de pouvoir d'achat (§ Indice de pouvoir d'achat) ; déflateur, recettes, dépenses indexées et dette n'y voient rien. En v0.6.9 les deux tables sont vides : sorties identiques au bit. Leur remplissage, sourcé année par année, est une release distincte. Une année hors des années simulées, une clé non entière, une valeur non finie ou au-delà de ±0,03 lèvent une erreur à l'import et à chaque simulation : au-delà de 3 points, le choc n'est pas écrêté mais les filets du modèle qui le reçoit (croissance, chômage, inflation) mordent en silence — un choc de l'ampleur de 2020 n'est donc pas encodable tel quel ; même en deçà, un test vérifie qu'une valeur livrée ne fait mordre aucun filet de plus qu'à tables vides. Verrouillé par `tests/test_conjoncture_observee_v069.py`.

**Pass-through TVA (v4.0)** : one-shot, applique l'annee qui SUIT l'entree en vigueur de la mesure — la macro de l'annee t est calculee AVANT les mesures de t, l'impact TVA transmis vient donc de t-1. Pas de re-pass-through les annees suivantes : la persistance passe par l'inertie (rho = 0,5). **v0.6.7** : plus de seuil d'activation a 0,3 % du PIB de recettes de TVA — le pass-through (30 %, plafonne a 0,2 pt) vaut deja 0 en 0, le seuil le faisait naitre d'un coup a +0,09 pt (curseur TVA a 20,63 % : -0,30 pt de dette 2035, statu quo compris).

**Ce que mesure la variable `inflation` — une variable pour trois roles (v4.1)** : le moteur n'a qu'une variable la ou l'economie en distingue trois — (i) le **deflateur du PIB**, denominateur du ratio de dette ; (ii) l'**IPC**, pour le pouvoir d'achat ; (iii) l'**indice d'indexation** des prestations. L'arbitrage retenu est de la caler sur le **deflateur**, parce que l'INSEE tranche explicitement (blog sept. 2022 : « les ressources publiques etant plus ou moins fonction du PIB en valeur plutot que de la seule consommation, c'est plutot le deflateur du PIB qui importe pour apprecier le taux d'emprunt reel des administrations publiques »), et parce que la dette est la sortie principale du site. L'indexation **legale** des pensions suit, elle, l'IPC hors tabac. **Biais residuel declare : -0,15 pt/an** sur les roles (ii) et (iii) — ecart deflateur/prix a la consommation mesure a -0,1/-0,2 pt en regime normal, jusqu'a -0,6/-0,8 pt en annee de choc energetique. **Ce biais n'est PAS conservateur — il FLATTE les chiffres publies** (correction du 26/08/2026 ; cette page ecrivait l'inverse). Il minore la depense indexee, donc il AMELIORE le deficit et la dette — la sortie principale du site — et il minore la perte de pouvoir d'achat affichee, donc il embellit cet indicateur aussi. Les deux effets vont dans le meme sens, et c'est le sens favorable ; « conservateur » designerait l'erreur qui joue contre soi. **Magnitude, mesuree par contre-epreuve** (depense primaire indexee sur l'IPC — l'indice que l'indexation legale suit — tout le reste identique) : deficit 2030 -6,40 -> -6,86, deficit 2035 -10,70 -> -11,95 ; dette 2030 129,65 -> 130,93, **dette 2035 159,35 -> 164,85, soit 5,5 points de PIB** (contre-epreuve mesuree le 26/08/2026 sur l'etat v0.6.1 ; l'ordre de grandeur — le seul message ici — est inchange par la passe v0.6.3, dont les valeurs étaient 129,35 / 158,85 / -10,68 ; v0.6.7, impulsions levier par levier : 129,91 / 160,69 / -10,99). Ce n'est pas un residu de second ordre. Il n'est pas corrige ici : tous les handlers consomment `inflation`, scinder en trois variables est un changement d'architecture instruit separement — ce qui est corrige, c'est ce qu'on en dit.

**Distinction importante — ne pas confondre** :
- Le **point fixe** (1,6%, `INFLATION_STRUCTURELLE`) est l'inflation vers laquelle le regime converge quand output gap = 0.
- La **cible BCE** (2,0%, `BCE_CIBLE_INFLATION`) est le **seuil du garde-fou de surchauffe** : au-dessus, la banque centrale freine (blend 50/50). Ce n'est PLUS un point de convergence forcee (mecanique pre-v4.0).
- L'output gap negatif tire le deflateur effectif vers **~1,3-1,6%**, sous le point fixe. Corridor officiel vise : 1,3 / 1,6 / 1,6 / 1,5 / 1,5% (RAA 2026 Tableau n° 2 pour 2026-2029, mission IGF 07/2026 pour 2030) ; **realise du moteur sur le scenario de reference** : 1,34 / 1,45 / 1,50 / 1,52 / 1,53%, ecart annuel <= 0,15 pt, **moyenne 2026-2030 = 1,468%** (fourchette du dossier : 1,40-1,60). Le statu quo NU, lui, rend 1,34 / 1,44 / 1,49 / 1,51 / 1,53%. (Re-mesure 07/10/2026, v0.6.7 : le bruit tire graine 42 soutenait le deflateur, 1,498% de moyenne avec lui.) Ces deux series ne sont pas interchangeables : la page en publiait une troisieme, celle du scenario de reference d'AVANT le lot 9, jusqu'au 26/08/2026. (Recale 30/08/2026, v0.6.3 : graine 2025 aux comptes definitifs INSEE — deflateur 2025 realise 1,1 % — et inertie `rho` 0,50 -> 0,33, milieu de la fourchette declaree, encadre par la direction Banque de France, Billet n° 335.)
- **Marge a declarer** : (re-mesure le 16/11/2026, lot 6, calendrier de l'impulsion, coefficients recales, profil de l'investissement cale sur le FMI, puis option du rythme de la depense courante, puis lot 5c, dotation pour moitie en investissement local : moyenne du scenario servi 1,468 %, a 0,068 pt du plancher ; sensibilite a `rho` entre 0,25 et 0,50 : 0,054 pt ; a `rho` = 0,50, 1,428 %, au-dessus du plancher ; corridor de dette a 1,09 pt en 2030 ; chiffres lies a la mesure par `tests/test_phillips_v061.py`. Lot 6, avant l'option : 1,474 %, 0,074 pt, 0,058 pt, 1,430 %, 1,32 pt. Lot 6, avant le calage du profil : 1,470 %, 0,070 pt, 0,056 pt, 1,430 %, 1,20 pt. Lot 6, equation seule : 1,468 %, 0,068 pt, 0,054 pt, 1,430 %, 1,18 pt. Lot 5, hausse de depense courante au coefficient de sa coupe : 1,470 %, 0,070 pt, 0,058 pt, 1,428 %, 1,27 pt. Lot 1, terme d'effort de l'inflation et eviction retires, coefficient des transferts recale : 1,470 %, 0,070 pt, 0,054 pt (0,056 avant le retrait de l'eviction), 1,428 %, 1,21 pt. Re-mesure du 12/11/2026, release P, moteur v0.8.1 : 1,474 %, 0,074 pt, 0,052 pt, 1,436 %, 1,28 pt. La suite du paragraphe date de la v0.6.7.) La moyenne du scenario servi est a 0,028 pt du plancher de la fourchette (0,098 avec le bruit tire, 0,014 avant le recalage v0.6.3), et la sensibilite du sentier au parametre d'inertie `rho` vaut 0,056 pt entre 0,25 et 0,50 depuis l'output gap en niveau (v0.6.7 ; 0,046 au 30/08/2026, 0,062 avant) — AU-DESSUS du < 0,05 demande par le brief, la fenetre 2026-2030 etant desormais transitoire. La conformite tient pour `rho` dans [0,20 ; 0,45] ; a 0,50, borne haute de la fourchette de travail, la moyenne tombe a 1,384 %, sous le plancher (marge que le tirage aleatoire tenait) : la plage TESTEE est restreinte a [0,20 ; 0,45] (arbitrage du 07/10/2026, `tests/test_phillips_v061.py`), `rho` servi (0,33) restant au milieu ; une valeur servie au-dela de 0,45 sortirait du corridor. En sens inverse, le corridor de DETTE est a 1,86 pt (2030) pour une tolerance portee de 1,6 a 2,0 (v0.6.7) : le PIB nominal etant desormais honnete, l'ecart revele le residu (b) que le PIB trop bas compensait — declare ici plutot que tu (chiffres complets : « Calibration Baseline Validee »).

**Sources** : BCE Survey of Professional Forecasters T3 2026 ; Gouvernement, RAA 2026 du PSMT 2025-2029 (Tableau n° 2, note 6), avis HCFP n° 2026-3 ; INSEE, blog « Inflation : les deflateurs en comptabilite nationale » (sept. 2022) ; Banque de France, *Rue de la Banque* n° 56 (fev. 2018) et Billet de blog n° 335 (dec. 2023) ; BCE, ECB Working Paper n° 3133 (oct. 2025) ; FMI, *France: 2026 Article IV Consultation*, PR n° 26/255 ; BCE Strategy Review 2021 (cible symetrique 2%).

### Mecanismes de Second Ordre

> **Cicatrice d'austérité retirée (lot 1, 15/11/2026, non publié).** Le seuil de 3 % du PIB avait été choisi
> « pour éviter le piège où l'utilisateur ne peut trouver aucune solution viable », pas d'après une source ; la
> pénalité s'ajoutait chaque année tant que l'effort durait, au lieu d'un recul ponctuel du niveau du PIB, et
> n'avait aucun pendant pour une relance. Sources rouvertes : DeLong & Summers, « Fiscal Policy in a Depressed
> Economy », BPEA printemps 2012 (effet de niveau sur le potentiel proportionnel à l'impulsion, « ΔY^f = ηµΔG », η
> entre 0 et 0,2, en économie déprimée à la borne zéro des taux) ; Fatás & Summers, NBER WP 22374 (2016), JIE 112
> (2018) (régression linéaire sur la baisse du PIB due à la politique budgétaire, consolidations de 2010-2011,
> « much smaller effects » hors crise) ; ni seuil, ni plafond, ni sens unique dans aucune des deux ; Gechert, Horn & Paetz (Oxford
> Bulletin 2019) et Girardi, Paternesi Meloni & Stirati (Cambridge Journal of Economics 2020) : effets de long
> terme pour les deux signes, l'« hystérèse inversée » des relances. Redondance : les multiplicateurs sont calés sur
> l'effet de niveau à 4 ans mesuré, persistance comprise ; la cicatrice le relevait pour un seul programme, au-delà
> de la cible de 0,8 qui vaut pour tous, et contredisait le rappel vers le potentiel (λ = 0,2). Retirée sans
> remplacement : une hystérèse symétrique sur l'écart de production serait un autre modèle (aucune valeur publiée
> pour la France hors crise), à instruire à part, avec l'hystérèse du potentiel existante (`update_potential_growth`,
> bornes −0,4 / +0,1 point et rebond après l'an 3 : asymétrique elle aussi, non touchée ici). Ce qui bouge (mode
> cadre 2028) : un seul des dix scénarios publiés en 2032, celui dont l'effort intérieur dépassait 3 % du PIB
> (effet isolé sur v0.8.1 : dette 2032 −0,92 point, déficit 2032 +0,23, croissance moyenne 2028-2032 +0,067 ;
> −0,87, +0,22 et +0,066 après le retrait du terme d'effort de l'inflation) ; un second en 2035 seulement (dette
> −0,17, puis −0,15) ; les huit autres sont identiques au bit ; aucun rang ne change. L'effort intérieur (net des flux vers
> un agent non résident), qui n'avait plus d'autre lecteur, est retiré avec elle. Garde :
> `tests/test_cicatrice_retiree.py` (croissance invariante au niveau de consolidation, multiplicateur effectif constant
> de 1 % à 8 % du PIB, et de 1 % à 6,5 % dans le moteur complet sans aucune neutralisation).

| Mecanisme | Formule | Source |
|-----------|---------|--------|
| Cicatrice austerite | **RETIRÉE (lot 1, 15/11/2026)** — était : −0,10 × (effort − 3 % du PIB) aux seules consolidations, plafond −0,3 pt/an | Citée jusqu'à v0.8.1 comme « DeLong & Summers 2012 » : à tort. DeLong & Summers (BPEA 2012) et Fatás & Summers (NBER WP 22374, 2016) décrivent un effet de niveau sur le potentiel, proportionnel à l'impulsion, propre aux économies déprimées à la borne zéro ; ni seuil, ni plafond, ni sens unique. Encadré ci-dessus |
| ~~Confiance Alesina~~ | **SUPPRIME** : bonus de croissance retire en v0.6.0 ; attenuation ÷1,10 des coupes retiree en v0.6.7 (§ Multiplicateurs) | Alesina 2010, conteste IMF 2012 |
| Crowding-out (éviction) | **RETIRÉE (lot 1, 15/11/2026 ; arbitrage du mainteneur du 21/10/2026, « option C »)** — était : intensité × effort si effort < 0 et dette > 100 % ; intensité 0,002 (relance 100 % investissement productif) à 0,008 (0 %) | Aucune source publiée. Reste le ×0,95 des multiplicateurs au-delà de 110 % : inerte dans le domaine publié, où la dette lue dépasse toujours ce seuil ; aucune réduction des multiplicateurs liée au niveau de dette n'y est modélisée — encadré ci-dessous |
| Boost potentiel supply-side (v3.1, échelle en v0.8.0, lot 2) | Recherche publique : stock, forme logarithmique, effet l'année qui suit la dépense, hors plafond (lot 2). Autres canaux : linéaires dans le flux (élasticité / stock), délais et dépréciation différenciés, leur somme saturée vers ±0,20 pt | Bom & Ligthart 2014 ; INSEE comptes de patrimoine 2025 ; FMI 2015 ; Fieldhouse & Mertens 2024 (élasticité et calendrier de la recherche) ; OCDE 2001 et Khan & Luintel 2006 (dépréciation de la recherche) ; DG Trésor ThreeME 2026 |
| Retour fiscal transition | **RETIRÉ (lot 2, 16/11/2026)** — était : 0 % Y1-2, 5 % Y3-4, 8 % Y5+ | Double compte avec l'élasticité des recettes au PIB ; références citées (« OECD 2021 », « Cour des comptes 2023 ») sans ce chiffre ou introuvables ; § Investissements verts |

**Éviction (« crowding-out ») — RETIRÉE (lot 1 des corrections d'équations, 15/11/2026, non publié).** Arbitrage du
mainteneur du 21/10/2026 (« option C » : on ne garde, pour la dette, que le ×0,95 symétrique au-delà de 110 % de dette),
appliqué au lot 1 après deux reports. Jusqu'à v0.8.1, `engine/growth.py` (`effet_eviction`) ôtait à la croissance de
l'année t :

```
éviction_t   = intensité_{t−1} × effort_{t−1}   si effort_{t−1} < 0 et dette_{t−1} > 100 % ; 0 sinon
intensité    = 0,002 + (1 − part_{t−1}) × 0,006                    (0,002 à part = 1 ; 0,008 à part = 0)
part_{t−1}   = part d'investissement productif de l'expansion brute du budget de t−1, ∈ [0 ; 1]
```

Coefficients `EVICTION_SEUIL_DETTE`, `EVICTION_INTENSITE_INVESTISSEMENT`, `EVICTION_SURCROIT_NON_PRODUCTIF` : aucune
source publiée (calibration v3.0 du 27/03/2026). **Pourquoi elle est retirée.** La littérature lue (Huidrom, Kose, Lim &
Ohnsorge, JME 2020 ; Ilzetzki, Mendoza & Végh, JME 2013, qui scindent l'échantillon à 60 % de dette ; Nickel & Tudyka,
JMCB 2014 ; contestée par Auerbach & Gorodnichenko 2017, qui trouvent l'écart non significatif) trouve un
multiplicateur plus faible quand la dette est haute. Ses modèles sont linéaires dans le signe du choc : l'effet y vaut
pour une consolidation comme pour une relance par construction (Auerbach & Gorodnichenko préviennent que les coupes ne
sont pas forcément symétriques des hausses). Aucune étude lue ne réserve l'effet aux relances, aucune ne différencie
investissement et transferts de 1 à 4 (l'investissement public est lui aussi affaibli, Adarov et al. 2024). Deux
effets de bord mesurés sur la v0.6.10 : la coupe de transferts coûtait 4 % de plus que la hausse ne rapportait ; et le
calage des coefficients sur une relance 100 % transferts faisait dépendre la valeur d'un même euro de transferts du
reste du programme.

**Ce que fait le ×0,95 restant (mesuré).** Dans tout le domaine publié (dix scénarios, mode historique et mode cadre,
et le banc de calibrage des multiplicateurs), la dette lue dépasse le seuil de 110 % à chaque appel (au moins 115,5 %).
Le facteur s'applique donc à tous les appels et il est absorbé par la calibration des coefficients d'impact, calés à
4 ans facteur compris : il ne différencie aucun scénario publié. Après le retrait de l'éviction, **aucune réduction des
multiplicateurs liée au niveau de dette n'est modélisée dans le domaine publié** ; la dette agit par la traînée sur le
potentiel (au-delà de 90 %) et par la prime de taux d'effort (`engine/debt.py`). Le facteur reste une marche à 110 %,
inerte dans ce domaine : dette de modèle déclarée (un programme qui ramènerait la dette sous 110 % verrait ses
multiplicateurs monter d'un coup de 5,3 %). Gardes : `tests/test_eviction_retiree.py`, dont deux tests rougissent le
jour où le banc ou un scénario publié lit une dette sous ce seuil.

**Ce qui change avec le retrait.** La croissance ne lit plus ni l'effort net ni la part d'investissement de l'expansion
(plomberie retirée). Le coefficient d'impact des baisses d'impôts, 0,63, qui compensait l'éviction d'une relance 100 %
baisse d'impôts, revient à celui de la hausse, 0,615 : sinon la baisse vaudrait 3,6 % de plus que la hausse (test de
symétrie à ±3 %, `tests/test_symetrie_impots_v067.py`) ; c'est un paramètre, admis dans ce commit d'équation parce
qu'aucun ordre de commits n'évite un test de symétrie rouge (appliqué avant le retrait, il donnerait un rapport de 0,964). **Les deux effets,
séparés** (mode cadre 2028, dix scénarios publiés, dette 2032, par rapport à l'équation précédente) : le retrait de
l'éviction seul, de −0,15 à −0,00 point ; le coefficient des baisses d'impôts seul, de +0,02 à +0,22 point ; la somme,
de −0,10 à +0,14 point (déficit 2032 au plus ±0,03, croissance moyenne 2028-2032 au plus ±0,007 point ; aucun rang ne
change). Pour sept scénarios sur dix, le coefficient pèse plus que le retrait, et en sens inverse : c'est pourquoi un
programme de consolidation qui baisse aussi des impôts voit sa dette 2032 monter (jusqu'à +0,14). En mode historique
(dette 2035), le retrait seul va jusqu'à −1,06 point et le coefficient seul jusqu'à +0,33. Preuve d'équivalence :
l'éviction neutralisée en mémoire dans la v0.8.1 (intensités nulles, coefficient 0,615) donne des sorties identiques
au bit à la v0.8.1 privée de ce seul retrait, et au code de ce commit (après les deux précédents). L'asymétrie
coupe/hausse de transferts tombe de 4,1 % (v0.8.1 ; 3,8 % après les deux premiers retraits) à 0,1 %
(`tests/test_symetrie_transferts_v067.py`, désormais à 1 %). Garde : `tests/test_eviction_retiree.py` (croissance
invariante à l'effort net, coupe et hausse de transferts de même ampleur, aucun symbole de l'éviction dans le moteur,
dette lue au-dessus du seuil du facteur). Les multiplicateurs effectifs à 4 ans, mesurés après le retrait :
investissement 1,41, transferts 0,67, hausse d'impôts 0,65, baisse 0,65, coupe de dépenses 0,79 ; le recalage du
coefficient des transferts sur leur cible de 0,65 est une décision de paramètres, séparée (encadré « Coefficient
des transferts recalé » du § Multiplicateurs).

> **Corrigé en v0.6.10 (contre-audit externe, V2-01), sans objet depuis le lot 1** : jusqu'en v0.6.9, la part divisait des flux BRUTS par levier (Σ |Δdép| des leviers d'investissement) par des flux NETS agrégés (|Δdép net| + |Δrec net|) — ce n'était pas une part. +20 Md€ d'investissement financés pour moitié par −10 Md€ de dotations donnaient 2,0 : l'intensité devenait négative et l'« éviction » soutenait l'expansion (+0,0013 pt de croissance en 2027) ; IM Compétitivité atteignait 2,605. La part est désormais définie sur une seule convention, dans [0 ; 1] par construction, sans bornage (que l'auditeur écartait comme justification). Convention retenue entre deux candidates : flux bruts au numérateur et au dénominateur (écartée : une coupe d'investissement y comptait comme investissement, et les consolidations diluaient la part) et part de l'expansion (retenue). Elle supprime aussi une marche : quand l'effort net s'annulait, l'ancienne part divergeait et la croissance sautait (+0,002 pt en 2027 pour 10 Md€ d'investissement financés par −10 Md€ de dotations) ; elle est désormais continue. Les écarts suivent la composition réelle des relances : la part baisse pour RN (0,37 à 0,81 sur l'horizon, gonflée par un dénominateur net qui se réduisait ; désormais 0,19 à 0,23) et Renaissance (0,21-0,49 → 0,21-0,22), elle monte pour LFI, le PS et les Écologistes (0,20-0,36 → 0,40-0,50). Dette 2035, mesurée sur v0.6.9 : RN +0,05, LFI −0,03, Renaissance +0,02, PS −0,02, IM Compétitivité +0,01 pt, Écologistes < 0,001 ; Budget 2026 voté, Horizons, LR, IM Rabot et statu quo identiques au bit ; contre-exemple de l'auditeur 145,13 → 145,18 %.

### Croissance Potentielle Supply-Side (v3.1, échelle en v0.8.0)

**Mecanisme** : les depenses d'investissement productif augmentent la croissance potentielle de maniere dynamique, avec des parametres differencies par canal.

| Canal | Pente : bonus par Md€/an d'écart au défaut | Délai | Dépréciation/an | Source de la pente |
|---|---|---|---|---|
| **Recherche publique** | forme logarithmique du stock : 0,06 × variation du logarithme du stock (187 Md€ au départ), soit ≈ +0,032 pt par Md€ ajouté pour les petits montants ; hors du plafond (lot 2) | aucun : forme stock, effet l'année qui suit la dépense (lot 2) | 15 % (stock) | Fieldhouse & Mertens 2024 (élasticité de la R&D civile 0,06) ; stock = 28 Md€/an de R&D des APU / 15 % (INSEE 2025, inventaire permanent) |
| **Transition écologique (investissement)** | +0,005 pt (= 0,106 × 0,87 / 1 855 Md€) | 3 ans | 5 % | Bom & Ligthart 2014 (0,106) ; FMI 2015 (efficience 87 %) ; INSEE, comptes de patrimoine 2025 (actifs non financiers des APU hors terrains) |
| **Transition écologique (rénovation)** | **0** (aucun effet d'offre) | 2 ans | 3 % | DG Trésor, Trésor-Éco n° 394 (07/2026), ThreeME : +50 % de subvention → PIB +2,2 pt à 1 an, −0,36 à 10 ans, −0,04 à long terme (effet de demande seul) |
| **Éducation** | +0,0025 pt (moitié du capital public, convention v3.1) | 15 ans (hors horizon) | 5 % | littérature capital humain (délai) ; pente sans source propre, inerte sur l'horizon |
| **Investissement des collectivités** | +0,005 pt (même pente que l'investissement de l'État) | 3 ans | 5 % | capital public : mêmes sources que la transition écologique (investissement) ; canal distinct, sommé avant la saturation |

**Corrigé avant publication** (revue adverse de la release) : l'investissement des collectivités
(`collectivites.investissement`) était exclu de l'effet d'offre, sur la prémisse qu'aucun programme publié ne
l'utilisait ; trois programmes l'encodent (8 à 15 Md€). À montant égal, il reçoit désormais exactement l'offre de
l'investissement de l'État (vérifié par test). Effet mesuré sur les trois programmes concernés : dette 2032 en
mode cadre −0,07 à −0,16 point, dette 2035 en mode historique −0,23 à −0,70 point ; les sept autres programmes
publiés sont identiques au bit.

**Classe de multiplicateur et d'éviction (v0.8.0, contre-vérification I2).** Le canal d'offre ne suffisait pas : à
montant égal, 10 Md€ par an d'investissement local faisaient MONTER la dette 2032 (+0,20 point en mode cadre, +0,64
en 2035 en mode historique) quand 10 Md€ d'investissement de l'État la faisaient baisser (−0,40 et −0,71), parce
que le levier `collectivites` (une formule, dotation + investissement) prenait en entier la classe de la dépense
générique. Désormais, sa seule part `investissement` est publiée dans son impact (`depenses_investissement`) et
forme un flux distinct, `(collectivites, investissement)` (`INVESTISSEMENT_PRODUCTIF_PARTIEL`), multiplié (et lu par
l'éviction jusqu'à son retrait au lot 1) et réparti dans le temps comme l'investissement productif de l'État (classe `investissement`, profil de
persistance de l'investissement) ; la dotation garde la classe de la dépense générique (pour moitié depuis le lot 5c,
encadré du lot 5c). 10 Md€ par an, mesuré en
v0.8.0 : −0,37 point de dette 2032 (mode cadre) contre −0,40 pour l'État, −0,63 contre −0,71 en 2035 (mode
historique) ; le reste d'écart était la recette propre du levier de l'État, retirée au lot 2 : les deux leviers
donnent désormais le même effet, au bit. Mesure du moteur actuel, 10 Md€ par an :
−0,14 point de dette 2032 (mode cadre) contre −0,14 pour l'État, 0,07 contre 0,07 en 2035 (mode historique)
(lot 1 : le terme d'effort de l'inflation, retiré, faisait baisser le ratio de toute relance par le dénominateur ;
lot 5 : la hausse de défense du droit en vigueur, présente dans toute simulation en mode cadre, prend le coefficient
de la coupe de dépense courante ; lot 2 : retour fiscal propre de l'État retiré ; lot 6 : l'investissement agit dès
l'année de son budget, son effet sur le PIB arrive un an plus tôt dans la fenêtre, et son coefficient est recalé,
puis son profil est calé sur le tableau du FMI : la demande de l'investissement est plus faible dès la première
année — −0,59 / −0,59 et −0,59 / −0,59 avant ce calage, sur la pile ; lot 5c : la dotation du droit en
vigueur, sous le défaut, a sa part investie dans toute simulation en mode cadre ;
chiffre lié à la mesure par `tests/test_release_e_investissement_local.py`). Trois programmes publiés bougent (dette 2032 en mode cadre
−0,31 à −0,48 point, dette 2035 en mode historique −0,63 à −0,98) ; les sept autres sont identiques au bit.

**Forme (v0.8.0, échelle)** : la contribution de chaque canal est **linéaire dans le flux annuel** —
`pente × (valeur − défaut)`, signée —, puis la somme est saturée en douceur vers le plafond :
`bonus = 0,20 pt × tanh(Σ / 0,20 pt)`. C'est la forme qu'implique une fonction de production à élasticité
constante au STOCK de capital public (Bom & Ligthart 2014, *Journal of Economic Surveys* 28(5), méta-analyse de
578 estimations : 0,106 en moyenne, 0,083 à court terme, 0,122 à long terme) : un flux Δ soutenu accroît le stock
K de Δ par an, donc la croissance potentielle de ε × Δ / K par an (K supposé constant sur l'horizon, écart ≤ 3 %
du PIB). Stock productif : 2 945 Md€ d'actifs non financiers des APU fin 2025, dont 37 % de terrains (INSEE,
comptes de patrimoine 2025, lus via FIPECO 2026) → 1 855 Md€ hors terrains ; efficience 87 % (FMI 2015, « Making
Public Investment More Efficient » : écart d'efficience de 13 % dans les économies avancées). Ordre de grandeur :
1 % du PIB d'investissement public par an (≈ 30 Md€) ≈ +0,15 pt de potentiel par an, sous le +1,5 % de niveau de
PIB à 4 ans (demande et offre) de FMI WEO oct. 2014 ch. 3 / Abiad, Furceri & Topalova 2016 (*J. of
Macroeconomics* 50). R&D publique : Fieldhouse & Mertens (Dallas Fed WP 2305, rév. 11/2024 ; *AER* 2026),
élasticité de production du capital de R&D public ≈ 0,11 au total, 0,06 pour la R&D non militaire (retenu : le
levier est la recherche civile) ; stock de R&D des APU dérivé par inventaire permanent (28 Md€/an, INSEE 2025,
15 %/an) ≈ 187 Md€ — aucune statistique publiée du stock trouvée, dérivation déclarée. Constantes :
`constants.py`, bloc « RELEASE E — W6 ».

**Rendements décroissants** : pour la recherche, par sa forme logarithmique (lot 2, encadré ci-dessous). Pour les
canaux en flux, ils portent sur leur somme, par la saturation vers le plafond — linéaire à l'origine (1 Md€ vaut
un dixième de 10 Md€ tant que la saturation ne mord pas), mi-plafond à ≈ 22 Md€/an de capital public, 90 % du
plafond à 59 Md€/an. La littérature ne trouve de contrainte
d'absorption qu'à des échelles très supérieures (Gurara, Kpodar, Presbitero & Tessema, FMI WP 20/48 : coûts
unitaires croissants quand l'investissement public approche 10 % du PIB, 7 % si l'efficience est faible ;
Presbitero 2016, *J. of Development Economics* 120 : effet « relativement petit ») ; le plafond reste une
convention de prudence, justifiée par l'incertitude sur ε (0,05 chez Ramey 2020, NBER WP 27625 ; 0,12 à long
terme chez Bom & Ligthart ; 0,06-0,20 pour la R&D) ; elle l'était aussi par un « délai de 8-15 ans de la R&D »
qui sépare en fait un vote de crédits de l'effet, pas une dépense de l'effet (encadré « Recherche publique en
forme stock » ci-dessous). Conséquence mesurée :
comme le coût de la dépense croît linéairement et son effet d'offre sature, la dette n'est pas monotone dans le
montant au-delà du mi-plafond (programme publié sans autre levier d'offre, investissement 0 → 50 Md€, dette 2035 :
minimum vers 40-45 Md€ ; aucune borne du moteur n'intervient).

**Limites dites, non corrigées** (revue adverse de la release E ; forme et délais : décision du mainteneur en
attente, passe dédiée) :
- **Flux, pas stock, pour le capital public, la rénovation et l'éducation.** Le bonus de ces canaux dépend de
  l'écart du flux COURANT au défaut, compté après un délai d'années consécutives d'écart ; l'élasticité invoquée
  porte pourtant sur le stock. Conséquences : un investissement d'une seule année (calendrier « annee ») n'a
  aucun effet d'offre, quelle que soit sa taille (l'élasticité au stock donnerait ≈ +0,25 % de niveau de PIB
  pour 50 Md€) ; et le flux supplémentaire n'est pas déprécié tant qu'il dure. La recherche publique est passée
  en forme stock au lot 2 (encadré ci-dessous) ; pour les autres canaux, la dépréciation et le délai d'une
  forme stock n'ont pas de source rouverte à ce jour.
- **Plafond ±0,20 pt : une convention**, pas une source (justifiée par l'incertitude sur l'élasticité et par les
  délais) ; il pèse surtout sur les plus gros montants d'investissement. Depuis le lot 2, il ne porte plus que
  sur les canaux en flux : la recherche en est sortie, avec sa forme logarithmique. Les en retirer aussi, sans
  leur donner de forme stock, rendrait leur effet de niveau illimité (une contribution linéaire qui ne s'use
  pas) : point ouvert, lié à leur forme stock. Les délais des autres canaux (3, 2 et 15 ans) ne sont pas
  ré-audités ; la recherche, en forme stock depuis le lot 2, n'a plus de délai propre.
- **Demande et offre, pour les leviers d'investissement : un effet total par euro au-dessus de la cible
  publiée.** Le coefficient de la famille investissement est calé sur un effet TOTAL mesuré par le FMI (WEO
  d'octobre 2014, ch. 3 : +1,5 % de PIB quatre ans après une hausse d'un point de PIB d'investissement public),
  qui contient déjà le surcroît de capacité de production ; le canal d'offre du moteur s'y ajoute. Mesure du
  moteur actuel, PIB réel par euro dépensé chaque année, quatre ans après le début (15 Md€ par an dès 2026, mode
  historique) : 1,22 € pour une dépense de la famille investissement sans effet d'offre (le levier du banc de calage), 1,52 € pour l'investissement de l'État ou des collectivités, 4,15 € pour la recherche (1,65 € pour l'État tant que son levier gardait un retour fiscal propre, retiré au lot 2). Le sens est donc
  connu : pour ces leviers, le moteur compte une partie de l'effet d'offre deux fois, d'une ampleur inconnue pour
  la recherche, dont la dépense prend le coefficient de la famille investissement. C'est aussi pourquoi le
  plafond des canaux en flux est conservé : le retirer, ou donner au capital public une forme stock, ajouterait
  de l'offre à un effet déjà total. La correction passe par un calage conjoint de la demande et de l'offre, qui
  n'est pas fait ici. Garde : `tests/test_offre_chiffres_publies_lot2.py`.

**Plafond des canaux en flux** : ±0,20 pt (convention v3.1, plancher symétrique depuis la v0.6.0), atteint
asymptotiquement par leur somme. La recherche s'y ajoute, hors plafond, depuis le lot 2 : le potentiel total
n'a plus de borne fixe.

**Délai et mandat** : en mode cadre (programme dès 2028, chiffres publiés en 2032), le canal R&D agit dès 2029
(forme stock, lot 2 ; jusque-là, délai de 5 ans : pas avant 2033) et le capital public (délai 3 ans) en 2031 et
2032 seulement.

> **Recherche publique en forme stock (lot 2, 16/11/2026, non publié ; arbitrage du mainteneur du 15/11/2026).**
> Jusqu'ici, le bonus de la recherche suivait la dépense de l'année, et seulement après cinq années consécutives
> d'écart au défaut. Une dépense d'une seule année n'avait donc aucun effet, quelle que soit sa taille ; un
> programme commencé en 2028 n'agissait pas avant 2033, après le mandat ; et un surcroît de dépense qui dure
> n'était jamais usé. Le moteur suit désormais le **stock** de recherche ajouté par le programme : chaque année,
> ce stock perd 15 % de sa valeur et reçoit l'écart de dépense de l'année (`A_t = 0,85 × A_{t−1} + Δ_t`, en Md€,
> nul avant le programme) ; le bonus de croissance potentielle de l'année suivante vaut 0,032 point par Md€
> ajouté au stock (pour les petits montants depuis la forme logarithmique : encadré suivant). **Source** : l'étude de la Réserve fédérale de Dallas dont le moteur tire déjà l'élasticité
> (Fieldhouse & Mertens, Dallas Fed WP 2305, rév. 11/2024) relie la productivité au stock de recherche
> publique, sans délai propre (éq. (6) : Δtfp_t = ϕ Δk_t, k_t logarithme du stock) ; les auteurs posent ce
> calendrier, puis le vérifient sur leurs réponses estimées (annexe E.1 : « the timing assumptions implied by
> the structural equation appear reasonable »). **Réserves** : c'est une hypothèse posée puis vérifiée, pas un
> délai mesuré ; les données sont américaines ; aucune source française n'a été trouvée. Les « 8 à 15 ans » de
> la même étude séparent un vote de crédits de l'effet significatif : ils comprennent le temps que mettent les
> crédits à devenir dépense, que le levier du moteur, une dépense, a déjà franchi ; Khan & Luintel (2006), cités
> jusqu'ici pour les délais, utilisent des stocks retardés d'un à deux ans. Dépréciation de 15 % par an : OCDE
> (Guellec & van Pottelsberghe, DSTI/DOC(2001)3, stocks de R&D publique) et Khan & Luintel 2006 ; 0,16 en
> moyenne au BEA, selon Fieldhouse & Mertens. **Conséquences** : l'effet commence l'année qui suit la dépense ;
> une dépense d'une seule année donne un gain qui s'use ensuite au rythme de la dépréciation ; une coupe ôte du
> stock ce qu'une hausse y ajoute. Dans l'état de ce premier commit, la saturation commune vers ±0,20 pt
> s'appliquait encore au pas annuel du stock : un gros pas était écrêté, les petits pas négatifs qui suivent ne
> l'étaient pas, si bien qu'une dépense d'une seule année pouvait laisser un niveau légèrement négatif ; le
> commit suivant (forme logarithmique, hors plafond) a retiré cet effet. **Ce qui bouge** (mode cadre 2028, dix scénarios publiés,
> par rapport au lot 5) : les trois programmes qui augmentent la recherche, dette 2032 de −1,81 à −1,13 point,
> déficit 2032 de +0,28 à +0,45, croissance moyenne 2028-2032 de +0,08 à +0,13 point ; les sept autres sont
> identiques au bit ; cinq rangs de dette 2032 et deux rangs de déficit changent, aucun rang de croissance.
> Garde : `tests/test_offre_recherche_stock.py`.

> **Forme logarithmique de la recherche et sortie du plafond (lot 2, 16/11/2026, non publié ; arbitrage du
> mainteneur du 16/11/2026).** Le gain de la recherche n'est plus plafonné à 0,20 point par an : ce plafond, une
> convention de la v3.1, n'avait aucune source (aucune étude lue n'en fixe : Fieldhouse & Mertens, FMI Fiscal
> Monitor 2024, QUEST III, CBO) et il pesait surtout sur le plus gros programme de recherche. À la place, la forme
> à élasticité constante que la même étude de la Réserve fédérale de Dallas donne pour calibrer un modèle (p. PDF
> 31, d'où vient déjà le 0,06) : le gain de l'année suivante vaut 0,06 × [ln(187 + A_t) − ln(187 + A_{t−1})],
> où 187 Md€ est le stock de départ et A le stock ajouté par le programme. Les rendements décroissent doucement :
> doubler une hausse soutenue ajoute moins que le double, sans jamais buter sur une borne commune ; une coupe pèse
> plus qu'une hausse du même montant, d'autant plus que le montant est grand (à long terme, effet d'une coupe
> soutenue supérieur à celui d'une hausse de même montant de 4 % pour 1 Md€ par an, 20 % pour 5 Md€, 45 % pour
> 10 Md€, la plus forte coupe du levier ; après cinq ans, 22 % pour cette coupe) ; une dépense d'une seule année laisse un
> niveau acquis positif, qui s'use au rythme du stock. Le plafond ne porte plus que sur les canaux en flux
> (capital public de l'État et des collectivités, rénovation, éducation) : les en retirer sans forme stock rendrait
> leur effet de niveau illimité, et leur forme stock attend une source pour sa dépréciation et son délai (point
> ouvert). **Ce qui bouge** (mode cadre 2028, dix scénarios publiés, par rapport au commit précédent) : les trois
> programmes qui augmentent la recherche, dette 2032 de −1,59 à −0,31 point, déficit 2032 de +0,09 à +0,43,
> croissance moyenne 2028-2032 de +0,026 à +0,134 point ; les sept autres sont identiques au bit ; deux rangs de
> dette 2032, deux de déficit et deux de croissance changent. **Variantes, en sensibilité seulement** (aucune
> n'entre dans la version principale) : (i) effet deux ans après la dépense, hypothèse de l'OCDE (Guellec & van
> Pottelsberghe 2001 : retard de deux ans posé a priori pour la recherche publique) ; (ii) « hausse rapide » :
> 30 % d'une hausse partent en salaires des chercheurs et n'entrent pas au stock. Goolsbee (1998, États-Unis)
> estime que les études usuelles surestiment l'effet de la recherche publique de « 30 to 50% » : sur la hausse de
> 1980-1984, l'effort réel de recherche n'augmente que de 7,6 % au lieu de 11 %, « 30% smaller », pour l'ensemble
> de la recherche, et jusqu'à « 40-50% » de moins si toute la hausse allait aux métiers les plus demandés
> (physiciens, ingénieurs de l'aéronautique). La variante retient 30 %, le bas de cette fourchette, parce que c'est
> le cas calculé pour la recherche dans son ensemble, que finance le levier ; elle reste
> en sensibilité seulement, car l'élasticité de 0,06 est estimée sur un échantillon où cet effet a déjà joué en
> moyenne : l'appliquer dans la version principale le compterait deux fois. Écart à la version principale, mode
> cadre 2028, en points : dette 2032 / déficit 2032 / croissance moyenne 2028-2032. Garde :
> `tests/test_offre_recherche_variantes.py`.

| Écart de recherche du programme en 2032 | (i) Effet deux ans après la dépense | (ii) 30 % d'une hausse en salaires |
|---|---|---|
| +26,7 Md€ | +1,32 / −0,31 / −0,091 | +0,91 / −0,24 / −0,073 |
| +10,7 Md€ | +0,70 / −0,16 / −0,049 | +0,49 / −0,13 / −0,040 |
| +8,9 Md€ | +0,62 / −0,13 / −0,038 | +0,49 / −0,12 / −0,038 |
| aucun (sept scénarios) | 0 | 0 |
| droit en vigueur, +5 Md€ par an (version principale : −1,39 / +0,28 / +0,138) | +0,41 / −0,07 / −0,019 | +0,41 / −0,10 / −0,029 |

> **Ce que cela implique : une hausse de la recherche publique se rembourse dans le moteur avant la fin du
> mandat, en part du PIB et en euros.** Mesure du moteur actuel, 5 Md€ de plus par an sur le droit en vigueur,
> mode cadre (programme dès 2028) : dette 2032 plus basse de 1,39 point de PIB et de 11,7 Md€, solde 2032 meilleur
> de 8,0 Md€ ; la dette en euros passe sous celle de la référence dès 2031. C'est la conséquence de l'étude
> source, pas un excès du moteur : Fieldhouse & Mertens estiment qu'un euro de stock de recherche publique civile
> rapporte 1,71 € de PIB par an (tableau 2 ; intervalle 1,07 à 2,22), plus que le rendement implicite du moteur :
> 0,96 € en 2025, 1,14 € en 2032 (élasticité 0,06 × PIB ÷ stock de 187 Md€) ; seul le bas de leur intervalle
> recoupe le moteur. Ces auteurs concluent d'ailleurs à un sous-investissement public dans la recherche civile.
> **Réserves** : l'étude est américaine ; le calendrier (la productivité suit le stock sans attendre) y est posé,
> puis jugé raisonnable au vu des résultats, pas mesuré ; et le plus gros programme publié sort du domaine estimé
> (stock ajouté de l'ordre d'un tiers du stock de départ en cinq ans, quand les réponses de l'étude sont mises à
> l'échelle d'une hausse de 1 % du stock). **Périmètre** : l'élasticité de 0,06 est celle du stock CIVIL (la
> conversion ×0,5 de l'étude, p. PDF 31, repose sur la part civile américaine, environ la moitié). Le stock de
> départ vient de l'investissement en recherche des administrations des comptes nationaux (28 Md€ en 2025, Insee
> via FIPECO), estimé par l'Insee à partir de l'enquête du ministère de la Recherche auprès des administrations,
> qui couvre la recherche de défense qu'elles exécutent (6 % de cette dépense en 2008, dernière part relevée) :
> appliquer au stock total l'élasticité du stock civil sous-estime un peu l'effet d'un euro de recherche civile.
> Aucune valeur ne change ici. **Points ouverts, pour une release de paramètres** : le stock de départ est figé en
> euros de 2025 alors que le stock ajouté s'accumule en euros courants ; l'OCDE (Guellec & van Pottelsberghe 2001)
> calcule le stock de départ par dépense ÷ (croissance + dépréciation), soit un stock plus petit ; l'Insee retient,
> dans les comptes nationaux, une durée de vie conventionnelle de 10 ans pour les actifs de recherche. Garde :
> `tests/test_offre_chiffres_publies_lot2.py`.

> **Corrigé en v0.8.0 (revue adverse de la v0.6.11, échelle)** : jusque-là le bonus d'un canal valait
> `coeff × log2(1 + |écart|)` (la page écrivait `ln` jusqu'au 07/10/2026 ; le code a toujours calculé `log2`),
> somme écrêtée à ±0,20 pt. Le plafond était atteint dès 1 Md€ d'écart (transition écologique : 0,0020 × log2(2)
> = 0,0020), si bien que 1 Md€ et 50 Md€ recevaient la même prime d'offre : sur un programme publié sans autre
> levier d'offre, l'investissement 0 → 1 Md€ déplaçait la dette 2035 de −5,3 pt (2 Md€ : rien de plus), et six
> programmes publiés sur dix recevaient le même bonus de +0,20 pt (un septième, qui coupe la recherche, le plancher
> −0,20) — un défaut d'échelle favorable aux petits montants, préexistant (`log2` depuis la v3.1 ; la porte à
> 0,1 Md€ retirée en v0.6.7 ne faisait que le lisser). Mesuré sur le moteur v0.8.0 : la part de la dette 2035 due
> au seul effet d'offre (mode historique) se resserre pour les sept programmes concernés, de −7,0 à −3,3 pt avant
> à −5,2 à −2,5 pt après pour les six qui investissent, de +3,2 à +2,9 pt pour celui qui coupe ; dette 2032 en
> mode cadre : de 0 à +1,48 pt ; le scénario de référence, les deux autres programmes et le statu quo sont
> identiques au bit. Le sens est le même pour tous : chaque programme reçoit l'offre de son montant. **Le curseur
> d'investissement tiré seul ne fait plus baisser le ratio de dette 2035, même pour les petits montants** (droit en
> vigueur, c'est-à-dire le budget 2026 voté tel que le moteur le tient, mode historique : 149,54 → 149,62 à
> 10 Md€/an ; mesure du moteur actuel ; +0,01 point dès le premier Md€) : le coût l'emporte dès le début du
> curseur, de plus en plus par Md€ : 0 → 50 Md€/an, 149,54 → 151,81 (canal d'offre coupé : 156,49) ; le canal
> d'offre réduit donc nettement la hausse du ratio sans l'annuler, et l'élasticité centrale (FMI WP 15/95 : « the
> public-debt-to-GDP ratio may actually decline ») ne suffit plus à faire baisser le ratio. Avec le seul lot 6
> entier (sans le lot 2), le ratio baissait jusqu'à 10 Md€/an (149,43 → 149,41) puis le coût l'emportait entre 10
> et 20 Md€/an (151,21 à 50 Md€/an ; 155,87 sans le canal d'offre) ; sur la pile, avant le calage du profil de
> l'investissement sur le tableau du FMI (plus de demande les premières années), le ratio baissait sur tout le
> curseur (149,39 → 148,26 à 50 Md€/an ; 152,86 sans le canal d'offre). Jusqu'au lot 6
> (calendrier de l'impulsion : l'investissement
> agissait sur l'activité un an après son budget ; coefficient 1,2 au lieu de 1,31), le coût l'emportait entre
> 20 et 30 Md€/an (149,14 → 149,97 à 50 Md€/an ; 154,62 sans le canal d'offre), et dès 10 à 20 Md€/an une fois
> retiré le retour fiscal propre du levier (lot 2 : 149,14 → 150,47 ; 155,12).
> Jusqu'à v0.8.1, le terme d'effort de
> l'inflation (retiré au lot 1) faisait baisser le ratio de toute relance par le dénominateur (149,91 → 148,25 à
> 50 Md€/an ; 152,87 sans le canal d'offre ; mesuré en v0.8.1). Dit, non verrouillé en signe, verrouillé en
> échelle et en forme (rendement par Md€ décroissant) par `tests/test_effet_offre_echelle_v0612.py`, qui
> recalcule aussi les chiffres de ce paragraphe (le droit en vigueur est livré avec le moteur).

**Correction « un seul potentiel » (v0.6.1)** : jusqu'a la v0.6.0, trois blocs du moteur lisaient la
croissance potentielle et deux d'entre eux ignoraient le bonus supply-side. La croissance de l'annee
partait bien de « tendanciel + bonus », mais la **loi d'Okun** et la **mise a jour de l'output gap**
mesuraient leur ecart contre le **tendanciel seul**. Consequence : tout choc d'**offre** etait lu comme
un exces de **demande**. L'ecart ouvert chaque annee valait `okun x bonus`, et la convergence NAIRU
(`u = 0,94 x u + 0,06 x nairu`) l'accumulait vers un etat stationnaire `0,94/0,06 = 15,67` fois plus
grand — soit jusqu'a **1,10 pt de chomage permanent** pour un bonus au plafond, plus un **output gap
permanent de 0,20 pt** reinjecte dans la courbe de Phillips et dans le choix du multiplicateur.
Les trois lectures passent desormais par une source unique
(`GrowthMixin.croissance_potentielle_totale()`).

Ce que la correction change, et ce qu'elle ne change pas :

- **inchange** : un investissement productif (recherche, education, transition) augmente toujours la
  croissance potentielle, donc le PIB. Le canal d'offre est intact ;
- **retire** : le gain (ou la perte) de **chomage** qui accompagnait ce bonus sans justification. Un
  choc d'offre deplace le PIB potentiel : par construction il n'ouvre ni ecart d'Okun ni output gap.

**Sens de la correction** — elle est **symetrique par construction**, mais elle ne tombe pas de la meme
facon selon les programmes, et cela doit etre dit : les programmes qui **augmentent** les depenses
d'offre perdaient a tort un peu de chomage (ils en regagnent ~+0,4 pt a l'horizon 2035), ceux qui les
**coupent** en gagnaient a tort (ils en perdent ~-0,3 pt). Le sens du biais suivait le **signe** de la
variation de depense d'offre, pas la couleur politique : la correction retire l'artefact dans les deux
sens, avec la meme formule.

**Limite connue (non corrigee en v0.6.1)** : le plancher monetaire accommodant (inflation < 0,8% tiree
vers la tendancielle) est une regle **a seuil**. L'inflation n'est donc pas strictement monotone en
l'output gap : deux scenarios peuvent voir leur inflation bouger dans le sens oppose a leur output gap
selon le nombre de fois ou ce seuil est franchi. C'est un comportement pre-existant du bloc inflation,
documente ici parce que la correction ci-dessus le rend visible.

**Depreciation progressive** : Si les depenses sont reduites, le bonus acquis se deprecie graduellement (il ne disparait pas instantanement). Chaque canal a son propre taux de depreciation.

**Correction bug abs() (v3.1)** : Dans les versions precedentes, les coupes budgetaires (depenses negatives) etaient incorrectement prises en valeur absolue, ce qui les traitait comme des investissements. Ce bug est corrige : seules les depenses positives au-dessus du niveau par defaut generent un bonus.

**Correction bug decay loop (v3.1, achevée en v0.6.7)** : La boucle de decroissance des impulsions passees etait piegeee a l'interieur du gate d'effort courant. En consequence, quand l'effort budgetaire courant etait nul, les impulsions des annees precedentes disparaissaient au lieu de continuer a se dissiper normalement. La v3.1 annonçait ce bug corrigé ; il ne l'était pas : la somme des résidus est restée sous la condition `abs(effort) > 0,001` jusqu'en v0.6.6 (taxe superprofits : −0,07 pt prévu en 2030, 0 servi — audit Codex 10/2026). Depuis la v0.6.7 les résidus sont sommés sans aucune condition sur l'effort courant.

### Mecanismes Supprimes (v3.0)

- ~~Bonus elasticite investissement (+10% sur toutes les recettes)~~ -- Sans base empirique
- ~~Bonus synergie (consolidation+investissement -> +0,4% croissance)~~ -- Sans base empirique
- ~~Bonus qualite (education+transition -> +0,2%/an)~~ -- Sans base empirique

---

## Notes Methodologiques Generales

### Effets NIVEAU vs FLUX

**Pouvoir d'achat : plus de gating (v0.6.8).** L'indice de pouvoir d'achat est un indice de
NIVEAU (RDB des ménages / prix / UC, § Indice de pouvoir d'achat) : chaque année, chaque levier
émet le montant de l'année par canal ménages, et l'indice ne lit que l'année courante. Un
changement permanent compte donc pour son niveau, chaque année, sans composition ni
atténuation — la question « one-time ou récurrent » ne se pose plus pour lui. Jusqu'en v0.6.7,
douze leviers émettaient un coefficient la première année seulement, sept chaque année (un
niveau devenait une croissance), le tout atténué de moitié à partir de 2027.

**Effets NIVEAU (ONE-TIME) — Gini et compétitivité** : appliqués UNIQUEMENT l'année de mise en
oeuvre via `_is_first_year_change()` (ou `years_elapsed == 0`) ; l'indice cumule le niveau.

> **MAJ v0.6.1 — l'ASU change de famille.** Ses effets Gini et pouvoir d'achat
> etaient classes FLUX et emis a l'identique chaque annee dans des agregateurs
> cumulatif (`gini_cible_cumul += …`) et multiplicatif (`purchasing_power *= …`),
> ce qui en faisait une redistribution composee a l'infini. Ils sont desormais des
> effets de NIVEAU emis par **increment de montee en charge** : somme egale au
> niveau atteint, zero en regime permanent. Son effet `depenses` reste un flux
> (l'effort budgetaire perenne est bien une charge annuelle recurrente).

> **MAJ v0.6.7 — la même règle vaut pour l'effet chômage direct.** Le moteur ajoute
> `impacts['chomage']` au taux de chômage AVANT la convergence vers le NAIRU
> (`u = 0,94·u + 0,06·nairu`, `engine/unemployment.py`). Un terme réémis chaque année
> y converge donc vers 0,94/0,06 ≈ 15,7 fois sa valeur. Tous les émetteurs de la clé
> sont gatés une seule fois, sauf deux, corrigés en v0.6.7 (audit externe Codex,
> 10/2026) : `cotisations_salariales` (−0,05 pt par point de baisse, émis l'année
> d'entrée : à 1 pt, l'effet direct atteignait −0,33 pt en 2034) et `rabot_uniforme`
> (+0,004 × taux, émis par incrément de montée en charge comme l'ASU). Émis une fois,
> l'effet décroît ensuite au rythme de la convergence. Propriété verrouillée en CI
> sur tous les mini-scénarios et scénarios publiés : aucune émission chômage directe
> une fois la montée en charge finie (`tests/test_audit_codex_v067.py`). Un effet de
> niveau PERMANENT se modélise comme la bosse seniors (terme ajouté après la
> convergence, retiré de l'état reporté), pas par réémission.
>
> **MAJ v0.6.7, lot 3 — ces deux effets directs sont RETIRÉS.** Une fois les impulsions
> budgétaires multipliées levier par levier, l'un et l'autre faisaient double emploi :
> celui des cotisations salariales chiffrait le canal consommation (« +0,5 % PA → +0,3 %
> conso → +0,05 % emploi, multiplicateur 0,6 ») que le multiplicateur keynésien applique
> déjà à la baisse de recettes du levier ; celui du rabot (« moins de fonctionnaires, moins
> de commandes publiques », étiqueté Okun) refaisait le chemin coupe → activité → Okun du
> multiplicateur sur la dépense — c'est d'ailleurs le seul chemin du levier
> `fonction_publique`. Règle : un effet chômage direct de DEMANDE n'est légitime que pour
> une mesure sans flux budgétaire, invisible du multiplicateur (CSG progressive à recette
> nulle). Effet : renaissance_2027 et lr_2027 +0,08 pt de chômage 2034, +0,18/+0,19 pt de
> dette 2035 ; im_rabot_2029 −0,02 pt de chômage.

**Effets FLUX (RECURRENT)** — Appliques CHAQUE ANNEE legitimement :
- Prestations_indexation : Erosion annuelle si sous-indexation (chaque annee, l'ecart
  taux_indexation vs inflation creuse une nouvelle perte pour les beneficiaires) ;
  SYMETRIQUE : la sur-indexation (>100%) est un surcout budgetaire miroir. Formule
  (v0.6.7, ratio exact v0.6.10 — § Retraites) : `écart = masse nominale minima_sociaux de
  l'année × [1 − Π (1 + (1 − δ) × π⁺_s) / (1 + π⁺_s)]`, π⁺ = max(π, 0),
  δ = 1 − taux_indexation, produit sur les revalorisations écoulées (2026 → année, dix au plus),
  chacune à l'inflation de l'année précédente (calendrier N−1, même règle que les pensions,
  § Retraites). Jusqu'à v0.6.6, `(1 − δ × π_t)^k` réécrivait tout
  l'écart passé à l'inflation du jour (gel total : −1,8 Md EUR en 2027 à 2 %, 0 en 2028
  si l'inflation tombait à 0 ; audit externe Codex, 10/2026). À inflation constante, les
  deux formules coïncident. Les deux limites signalées au lot 2 sont levées au lot 3C, par
  alignement sur la convention des pensions : l'assiette n'est plus 90 Md EUR figés en euros 2025
  mais la masse nominale de la catégorie `minima_sociaux` (90 Md EUR en 2025), et la première
  revalorisation est celle de 2026 (un gel voté pour 2026 rapporte en 2026)
- Retraites (indexation) : même forme que les prestations depuis v0.6.7 — `0,86 × masse
  nominale des pensions × [1 − Π (1 + (1 − δ) × π⁺_s) / (1 + π⁺_s)]`, sept revalorisations au plus
  (§ Retraites ; la constante 1,5 Md EUR, insensible à l'inflation, a disparu)
- Transition ecologique COMPOSANTE renovation : Primes versees chaque annee a de nouveaux beneficiaires
- Fraude fiscale/sociale : Recettes recuperees annuellement
- Cotisations recurrentes : Impact budgetaire chaque annee
- Depenses courantes : Budget annuel
- Sante (efforts ONDAM) : Effort annuel reconductible

> **MAJ v0.6.1 lot 6 — l'education quitte les emetteurs de flux.** La meme
> distinction vaut pour le Gini, dont l'agregateur `gini_cible_cumul` ACCUMULE
> l'emission annuelle : un effet de NIVEAU emis chaque annee y est compose a
> l'infini. Apres le retrait du fallback (item I27), il reste **trois**
> handlers dont l'emission Gini annuelle ne converge pas vers zero a politique
> constante, tous documentes et verrouilles par un test dedie :
> `impot_societes` (via la regle survivante, dette connue ci-dessus),
> `retraites` (residu delibere de 10 %/an, cf. « flux annuel des nouvelles
> cohortes de retraites impactees ») et `rabot_uniforme` (emission croissante,
> la plus lourde des trois, jamais auditee). **Lot 4** : il n'en reste qu'un,
> le canal d'âge des retraites (résidu de 10 %/an, convention déclarée) — la
> règle de l'IS a été retirée au lot 7, le rabot émet désormais une fois au
> changement du taux, et l'indexation des pensions suit son écart en euros.

**Effectifs de la fonction publique (v0.6.8)** : ni les créations ni les suppressions de postes
n'ont d'effet direct sur le pouvoir d'achat (arbitrage du mainteneur) — elles passent par la
croissance, qui contient la production publique de ces agents. L'ancienne asymétrie (créations
+0,025 % par 10 000 postes, suppressions 0) a disparu avec elle.

**Convention semantique critique** :
- `taux_indexation` (prestations_indexation) et `indexation` (retraites) sont des coefficients
  ∈ [0, 1.2] :
  - `1.0` = 100% inflation compensee (indexation pleine)
  - `0` = gel total
  - `0.5` = demi-indexation
  - `1.2` = sur-indexation (+20% au-dessus de l'inflation, rattrapage)
- NE PAS confondre avec un taux d'inflation cible (0,02, 0,025) — passer ces valeurs comme coefficient produirait un quasi-gel (~98%) au lieu d'une indexation pleine.

**Note technique sur les patterns de gating** (Gini et compétitivité ; le pouvoir d'achat
n'est plus gaté depuis la v0.6.8) :
1. `if self._is_first_year_change('<measure>_<canal>', {...}): x = ... else: x = 0.0`.
2. `is_first_year = self._is_first_year_change('<measure>', {...})` puis branchement (ex. `cotisations_salariales`).
3. `if years_elapsed == 0` (ex. `_apply_csg`, `_apply_chomage_alloc`).

Le test de garde-fou `tests/test_political_scenarios_2027.py::test_pa_2029_garde_fou_gating_one_time`
verifie l'indice de pouvoir d'achat integre (10 scenarios, tolerance ±1,5 pt sur 2029).

**4e pattern, une seule mesure — l'horloge du CHOC (v0.6.1, lot 7)**. Les trois
patterns ci-dessus partent tous de l'annee ou la MESURE apparait, ce qui suppose
une reference FIXE. Le canal d'age des retraites n'en a pas : sa reference est le
calendrier legal, qui monte de 62,75 ans (2026-2027) a 64,0 ans (2032). Un
programme qui figerait l'age a 62,75 a donc un ecart RIGOUREUSEMENT NUL en
2026-2027 : servir l'effet plein en 2026 revenait a le servir sur zero, puis a ne
laisser que le residu de flux (10 %) pour tout l'horizon — la mortalite
differentielle d'un gel de la reforme etait chiffree au dixieme de sa valeur.
L'effet Gini d'age se declenche donc a la **premiere annee d'ecart non nul**
(`_seniors.retraites_annee_debut_ecart_age_handler`), la MEME horloge que les
quatre autres canaux d'une mesure d'age (moindres pensions, fuite sociale, offre
de travail, bosse de chomage). Le canal INDEXATION du meme handler garde l'horloge
du run : sa reference (la pleine indexation) ne bouge pas. Les deux horloges
coincident pour tout age different de 62,75, donc pour tous les scenarios publies.

### Phasing (Montee en Puissance)

**Exemples :**
- Fraude fiscale (5 ans) : 20% | 35% | 50% | 70% | 100%
- ISF climatique (2 ans) : 50% | 100%
- Doublons sociaux (5 ans) : 15% | 30% | 50% | 75% | 100%

### Plafonds Realistes

Le modele applique des plafonds pour eviter resultats irrealistes :
- Fraude fiscale : Max 30 Md EUR esperes (~20,4 recouvres, ~15,9 nets)
- Fraude sociale : Max 13 Md EUR
- ISF climatique : Max 18 Md EUR (euros de 2025, avant l'indice d'assiette ; ne mord jamais)
- Taxe superprofits : Max 20 Md EUR

### Paramètres d'entrée : noms et valeurs

Un levier ne lit que les paramètres de son contrat (`budget_simulator/engine/_noms_parametres.py` et `docs/MEASURE_REGISTRY.md`, générés depuis le code des handlers et des formules). Trois leviers ont des modes exclusifs : avec `intensite`, les clés héritées de `taxe_superprofits` et d'`exonerations_salaires` ne sont pas lues ; avec `taux_remplacement`, `chomage_alloc.montant` non plus. Une valeur hors domaine est ramenée à la borne (rejetée en mode strict), une valeur non finie est retirée, et chaque correction invalide le résultat (`report.valid: false`).

**Booléens et nombres (gardes d'entrée, proposées après v0.8.1).** Un booléen n'est pas un nombre : sur une quantité bornée (`fonction_publique.effectifs`, une intensité, un taux, un montant), `true` ou `false` fait échouer le levier comme une valeur non numérique (effet compté nul, `report.valid: false` ; 422 en mode strict). Avant, `true` valait 1 en silence : un poste créé, ou l'ISF complet pour `isf_climatique.intensite`. Un booléen reste lu comme 0/1 sur un interrupteur, c'est-à-dire un paramètre que le registre public déclare `toggle` ou de domaine 0 à 1 au pas de 1 (`csg.progressive`, `asu.asu_activation`, exclusions du rabot), comme avant. Inversement, un paramètre déclaré booléen (`chomage_alloc.degressivite`) n'admet que `true`, `false`, 0 et 1 : une autre valeur (5, 0,5) activait la dégressivité en silence ; elle est désormais retirée (le levier applique son défaut, pas de dégressivité) avec une correction (`report.valid: false`), et refusée en mode strict. Les canaux qui lisent ces valeurs hors de la porte suivent la même règle et voient le levier refusé au neutre : offre et chômage des seniors (âge de départ), point d'indice lu par le SMIC, intensité de l'ISF lue par l'impôt plancher, taux d'IS lu par les bénéfices récupérés, effet d'offre (un levier refusé n'éteint plus celui des autres), conditions des exclusions mutuelles. Les deux listes sont dérivées du registre public (`PARAM_INTERRUPTEURS`, `PARAM_BOOLEENS`, `constants.py`), jamais écrites à la main ; verrouillé par `tests/test_gardes_booleens.py`. Aucune entrée valide ne change de résultat. Limite déclarée : un levier refusé compte pour zéro en entier, y compris la valeur de droit en vigueur qu'il porte en mode cadre (`fonction_publique.effectifs: true` sur la loi de finances votée perd les suppressions de postes du droit en vigueur, alors qu'une clé absente les garde) ; c'est le traitement antérieur d'une chaîne de caractères, étendu aux booléens.

**Écrêtage visible (v0.7.2).** Une valeur ramenée à sa borne figure aussi, sous forme
structurée, dans `report.leviers_ecretes` : une entrée par paramètre écrêté, avec le levier
(`fonction_publique.effectifs`), la valeur demandée, la valeur appliquée, le domaine
`[bas, haut]` et le motif `domaine`. La liste est vide quand rien n'est écrêté. Elle couvre
les domaines des paramètres nommés et de l'intensité, dans les deux modes temporels. Avant,
l'écrêtage ne se lisait que dans une phrase de `report.warnings` et dans un journal serveur.
Les trajectoires sont inchangées : le champ ne fait que décrire une correction déjà
appliquée. Le rabot du curseur effectifs par le vivier de départs, à l'intérieur du handler,
y figure aussi, une fois par simulation, avec le motif `vivier` : la valeur appliquée est le
stock retiré la dernière année rabotée (champ `annee`), la borne `[−capacité, null]` est la
capacité du vivier cette année-là. Il n'invalide pas le résultat (`report.valid` inchangé,
avis dans `report.warnings`). Hors du champ : une `annee_debut` ou une durée de rampe
(`rampe.annees`) hors domaine, signalées dans `report.warnings` seulement.

**Requête (v0.7.2).** Une clé inconnue au niveau de la requête `/simulate` (hors `mesures`,
`periods`, `annee_debut`, `rampe`) est refusée (422). Avant, `annee_debu: 2030` était ignoré
en silence et la simulation tournait en mode historique.

> **Corrigé en v0.6.10 (contre-audit externe, V2-04)** : un NOM de paramètre que le levier ne lit pas (faute de frappe : `{"tva_rate": {"tauxx": 0.25}}`) était ignoré en silence — le levier appliquait son défaut et le résultat restait déclaré valide. Il est désormais rejeté en mode strict (422, avec les noms admis) ; en mode tolérant, il est ignoré, signalé dans `report.warnings` et invalide le résultat, le levier restant appliqué avec ses autres paramètres. Même traitement pour une clé admise mais masquée par un mode exclusif (`{"taxe_superprofits": {"intensite": 0.5, "taux": 0.05}}` : `taux` n'était pas appliqué, sans signal). Les noms admis et les modes exclusifs sont dérivés du code (`budget_simulator/engine/_noms_parametres.py`, généré), jamais d'une liste tenue à la main. Les 10 scénarios publiés n'utilisent aucun nom inconnu : leurs trajectoires sont identiques au bit.

### Indicateurs Macroeconomiques

**Coefficient de Gini :**
- Base : 0,302 — dernière valeur publiée par l'INSEE, pour 2024 (« Niveau de vie et
  indicateurs d'inégalités », série parue le 09/07/2026). Jusqu'au lot 4 : 0,29, étiqueté
  « INSEE 2024 » à tort.
- Negatif = Mesure progressive (reduit inegalites)
- Positif = Mesure regressive (augmente inegalites)

**Perimetre de l'indicateur — ce qui explique les zeros (v0.6.1, items I27 et
I30).** L'indice publie est le Gini du **niveau de vie** : revenu disponible
par unite de consommation, definition INSEE. N'y entre donc que ce qui passe
par le revenu disponible des menages. Deux consequences, ecrites ici parce
qu'elles se lisent sinon comme des oublis :

- **Les depenses d'education n'ont aucun effet Gini direct**, parce que ce sont
  des transferts EN NATURE. Zero **par construction de l'indicateur**, pas par
  omission. Sur l'indicateur ELARGI (revenus elargis a l'ensemble de
  l'economie, Insee Analyses n° 118, avril 2026), l'effet existe mais reste du
  **second ordre** : deplacer le Gini elargi de 0,01 demanderait environ
  72 Md EUR, soit +70 % du budget de l'education nationale. Aucune elasticite
  « +1 Md EUR d'education → ΔGini » n'existe dans la litterature, pour une
  raison methodologique : les evaluations distributives francaises travaillent
  en microsimulation sur BAREMES (OpenFisca, TAXIPP, Ines), et une depense
  d'education n'a pas de bareme. Le chiffre n'est donc pas fabrique.
- **La recherche publique reste a zero**, et c'est un trou de la LITTERATURE,
  pas de la collecte : aucune etude n'estime l'incidence distributive de la R&D
  publique sur les menages, qui s'evalue par ses RENDEMENTS. L'INSEE classe la
  diffusion de la recherche parmi les depenses de consommation COLLECTIVE (non
  individualisables), reparties par hypothese, avec trois variantes publiees
  et l'avertissement que ces hypotheses « sont determinantes ».

**Le choix de la BASE inverse les signes — a lire avant de comparer nos chiffres
a une autre etude (v0.6.1, item I32).** Un meme prelevement indirect est
**regressif** rapporte au revenu disponible et **progressif** rapporte au revenu
elargi. Ce n'est pas un desaccord entre auteurs : c'est le meme fait mesure sur
deux denominateurs, dont les Gini eux-memes different fortement (**0,297** pour
le niveau de vie, **0,188** pour le niveau de vie elargi — Insee Analyses n 118,
avril 2026). Exemple : les prelevements sur les produits et la production (TVA,
TICPE) portent un coefficient de concentration de **+0,230**, ce qui leur donne
un signe POSITIF (regressif) sur la base disponible et NEGATIF (progressif) sur
la base elargie. Le sens s'inverse sans qu'aucun chiffre ne change.

Le simulateur n'a qu'UNE base — le Gini du niveau de vie — et tous ses
coefficients sont calibres sur celle-la. Deux consequences :

- un coefficient importe d'une publication qui utilise l'autre base doit etre
  **re-derive**, jamais recopie ;
- un lecteur qui compare nos signes a une etude construite sur le revenu elargi
  trouvera des desaccords qui **ne sont pas des erreurs**.

C'est aussi la reponse a l'accusation de calibration orientee : une calibration
orientee se reconnaitrait a une base **variable selon la mesure**, choisie a
chaque fois pour obtenir le signe voulu. Ici elle est unique, declaree, et la
meme pour tous les programmes.

**L'education joue dans les DEUX SENS, et le moteur ne peut pas les distinguer
(v0.6.1).** Le parametre d'education est un budget GLOBAL, alors que l'incidence
distributive de la depense educative change de signe selon la filiere et selon
la facon de classer les menages :

- l'enseignement **superieur n'est pas redistributif** — coefficient de
  concentration **-0,032**, et **+0,211** pour les etudiants decohabitants ;
  l'INSEE (*France, portrait social*, ed. 2021) mesure que les 10 % les plus
  aises percoivent **12 %** des depenses du superieur, contre 7 % de celles du
  primaire-secondaire ;
- en **cycle de vie**, les depenses au-dela de l'age de l'enseignement
  obligatoire « aggravent legerement les inegalites » entre menages classes par
  ORIGINE SOCIALE — et le resultat **s'inverse** si on les classe par revenu
  FUTUR (Allegre, Melonio & Timbeau, OFCE, 2012) ;
- la valorisation INSEE se fait **au cout de production** : une depense
  inefficace y apparait exactement aussi redistributive qu'une depense efficace.

Un curseur unique en euros ne peut trancher aucun de ces cas. C'est une **limite
explicite de l'outil**, pas un arbitrage en faveur d'un bord — et elle vaut dans
les deux sens : ni les programmes qui augmentent le budget de l'education, ni
ceux qui le reduisent, ne recoivent de bonus ou de malus distributif a ce titre.

**Ce qui a ete supprime en v0.6.1 (item I27).** Un « fallback generique »
heritait de la v4.5 : six regles par mesure appliquees aux handlers qui
n'emettaient pas eux-memes d'impact Gini (retraites 0,10 / chomage 0,15 /
sante 0,08 / TVA 0,05 / transition et education 0,04). **Aucune n'avait de
source**, et cinq etaient inatteignables (leurs handlers emettent tous leur
Gini). La sixieme, l'education, etait active et **asymetrique** : une HAUSSE
de depense reduisait le Gini, une COUPE n'emettait rien — un avantage
silencieux aux programmes de coupe. Elle etait de surcroit reemise chaque
annee dans un agregateur cumulatif, faisant deriver l'indice avec l'horizon.

**Dette connue, declaree.** Une seule regle survit, celle de l'impot sur les
societes (0,03 par point de recettes rapporte au PIB). Elle est **non sourcee**
et **asymetrique** (une baisse d'IS n'emet rien), et elle est ACTIVE, y compris
dans des scenarios publies. Elle n'est pas corrigee en v0.6.1 parce qu'elle
deplace des chiffres publies et qu'aucune source ne dit par quoi la
remplacer : la retirer ou la symetriser sans source remplacerait un biais par
un autre. Elle est nommee en constante, verrouillee par un test de
caracterisation, et renvoyee au chantier v0.7 avec la re-derivation de
`GINI_IMPACT_SCALE`.

**Méthode unique du Gini (lot 4).** Une seule règle pour tout levier dont l'effet passe par
le revenu disponible des ménages : l'effet brut d'un levier vaut **K × montant** (Md€), avec
K = (C − G) / Y pour une prestation (un Md€ versé en plus) et K = −(C − G) / Y pour un
prélèvement (un Md€ prélevé en plus). C est le coefficient de concentration de l'instrument
**au classement final** des niveaux de vie (celui de l'indice publié), G le Gini du niveau de
vie et Y la masse des niveaux de vie du champ (1 380 Md€ : niveau de vie moyen de 2024,
30 900 € par unité de consommation, × environ 44,5 millions d'unités, ordre de grandeur déduit,
±3 % ; ce n'est pas le revenu disponible brut des comptes nationaux, 1 870 Md€). C'est la dérivée
du Gini publié par rapport à une composante du revenu (Lerman et Yitzhaki, 1985). Constantes :
`constants.py`, § CANAUX GINI.

*Borne arithmétique.* C est compris entre −1 et 1. Un prélèvement ne peut donc pas réduire
l'indice de plus de (1 − G) / Y = 0,00051 par Md€ (tout payé par la personne la plus aisée),
une prestation pas de plus de (1 + G) / Y = 0,00094 par Md€ (tout versé à la plus modeste).
Trois gardes la verrouillent : une garde d'import sur les coefficients nommés ; une garde de CI
sur toute constante dont le nom suit un style du dépôt (« …GINI…PAR_MD », « …GINI…PAR_10MD »
ramenée à un Md€) ; et une garde de CI qui ne dépend d'aucun nom : chaque levier du registre,
chaque paramètre porté à son minimum, à son maximum et à deux points intermédiaires, doit émettre
par Md€ moins que la borne (`tests/test_gini_borne_registre_lot4.py`). Avant le lot, onze leviers
dépassaient la borne (indexation des prestations, tranche supérieure de l'IR, patrimoine…).

*Données.* INSEE, *Revenus et patrimoine des ménages*, édition 2024 : fiche 1.4, figure 1
(composition du niveau de vie selon le dixième de niveau de vie, 2021) et fiche 1.3, figure 1
(niveau de vie moyen de chaque dixième, de 8 820 à 64 840 €). Montant de chaque composante par
dixième = part × niveau de vie moyen ; C et G sont calculés sur les mêmes dixièmes. Recoupement
publié, au classement initial : INSEE, *France, portrait social* 2025, fiche « Redistribution
monétaire », figure 2 (part A et progressivité B de chaque transfert, « la différence en valeur
absolue entre son pseudo-Gini et le Gini du niveau de vie initial ») : K = (V − P) / Y
(prestation), −(P + V) / Y (prélèvement), V = Σ |A × B| / 1000 = 0,0923. Cette pente d'un
pseudo-Gini dépasse celle du Gini publié de 19 % (prestations) à 45 % (CSG) ; l'IFI, que la
fiche 1.4 ne sépare pas, la garde (le classement change peu tout en haut).
Ordres de grandeur, avant assemblage : -0,0052 pour +10 Md EUR verses en prestations ciblées ;
-0,0009 pour +10 Md EUR de CSG ; -0,0044 pour +10 Md EUR d'IFI.

| Instrument (levier) | K par Md€ (+1 Md€) | Statut | Fondement |
|---|---|---|---|
| Prestations ciblées : prestations familiales, aides au logement, minima, prime d'activité (`prestations_menages` solidarité) | −0,000521 | sourcé | INSEE RPM 2024, fiche 1.4, classement final (figure 2 de la FPS 2025 : −0,000622) |
| CSG et CRDS (`csg`, taux) | −0,0000863 | sourcé | même fiche, « Contributions sociales : CSG et CRDS » (figure 2 : −0,000125) ; la part du taux qui porte la hausse de 2026 sur les revenus du capital (jusqu'au taux du droit en vigueur) prend le coefficient du capital |
| Cotisations salariales (`cotisations_salariales`, par Md€ rendu) | +0,0000541 | sourcé (proxy : salaires) | même fiche, « Salaires » ; plafonds non comptés, effet probablement surestimé ; sous la plage +0,00006 à +0,0001 de la décision du 12/11/2026, que tirait le classement initial |
| Impôt sur le revenu (référence) | −0,000297 | sourcé | même fiche, « Impôt sur le revenu et le patrimoine » (figure 2 : −0,000400) |
| IFI (`fiscalite_patrimoine`, part IFI), ISF (`isf_climatique`, recette nette d'année pleine), impôt plancher, tranche supérieure de l'IR (`impot_revenu`, par Md€ de recette) | −0,000444 | sourcé (classement initial) | FPS 2025, figure 2, IFI, B = 5,2, « le prélèvement le plus progressif » ; la tranche supérieure est au moins aussi concentrée (valeur prudente, sous la borne −0,00051) |
| Indexation des prestations (`prestations_indexation`) | −0,000521 × écart en euros | sourcé | coefficient des prestations ciblées × écart de niveau appliqué à la masse de 2025 de la catégorie, en incrément |
| Indexation des pensions (`retraites`, canal indexation) | −0,0000685 × écart en euros | **plage publiée** | coefficient des pensions × écart de niveau appliqué à la masse indexée de 2025, en incrément |
| Rabot uniforme (`rabot_uniforme`) | par catégorie | sourcé et plage publiée | minima et AAH −0,000521, chômage +0,000238 par Md€ coupé, pensions −0,0000685 ; santé, APA, autres : 0 ; émis une fois |
| Allocations chômage (`chomage_alloc`, canal taux, par Md€ coupé) | +0,000238 | sourcé | même fiche, « Allocations chômage », en euros (l'ancre DREES E&R n° 1368, en personnes, donnait +0,000319) ; canal durée × 1,6 |
| Pensions (`prestations_menages` pensions) | −0,0000685 | **plage publiée** −0,0000474 à −0,0000895, centre | toutes pensions au classement final (fiche 1.4) ; gel des pensions de base (IPP, rapport 2025-2026, tableau 2.2, trois groupes, non recalé : ce regroupement majore l'écart des pensions de 8 %) |
| Revenus du capital (`fiscalite_capital`) | −0,000398 | **plage publiée** −0,000398 à −0,000506, borne basse | IPP, tableau 2.2, suppression du prélèvement forfaitaire unique (trois groupes) ; borne arithmétique ; plus lâche : revenus du patrimoine de la fiche 1.4, −0,000273 |
| Décote de l'IR (`impot_revenu`, décote, par Md€ de recette) | +0,000122 | sourcé, limite déclarée | Conseil des prélèvements obligatoires, rapport particulier n° 2 (2024), tableau n° 34, C = 0,134 ; classement par revenu déclaré, pas par niveau de vie |
| Abattement de 10 % des retraités (`abattement_retraites`) | −0,0000902 | **plage publiée** −0,0000855 à −0,0000949, centre ; limite déclarée | IPP, tableau 2.2, suppression (trois groupes ; corrigé du regroupement mesuré sur la CSG, × 1,11). La source chiffre la suppression, le levier décrit le forfait de 2 000 € (plus progressif par Md€ net) |
| SMIC (`smic`, par unité de hausse relative) | −0,02375 × hausse | **plage publiée** −0,0231 à −0,0244, centre ; extrapolation **convention déclarée** | groupe d'experts sur le SMIC, rapport du 1er décembre 2017, graphiques n° 41 et 45 (gains par dixième d'une hausse de 1 %) ; le tableau n° 12 (« −0,1 % ») en est l'arrondi |
| Impôt sur le revenu ciblé (`impot_revenu_cible`), élargissement de l'IR (`elargissement_ir`) | 0 | **zéro faute de source** | le levier ne dit pas quel instrument il porte ; la seule source qui ventile une baisse d'IR (baisse du taux de la première tranche de 2020, INSEE, FPS 2022, figure 4) donne +0,000109 à +0,000120 par Md€ de baisse (l'indice monte) et ne vaut que pour cet instrument |
| CSG progressive (`csg`, progressive) ; âge de départ (`retraites`, canal d'âge) | 0 | **zéro faute de source** | aucune des sources consultées ne chiffre l'effet ; sens de la limite ci-dessous |
| Droits de succession, taxe foncière, TVA, accises, taxe carbone, franchises et remboursements de santé, aides à la rénovation, taxe sur les superprofits | 0 | périmètre | hors du revenu disponible de l'INSEE (définition c1458) |
| Rémunérations publiques (point d'indice, salaires enseignants) | 0 | **zéro faute de source**, dans le périmètre (arbitrage du mainteneur) | revenus d'activité nets, donc dans le revenu disponible ; aucune des sources consultées ne répartit les agents publics par dixième de niveau de vie ; le sens même de l'effet n'est pas assuré |

*Périmètre.* Le revenu disponible de l'INSEE « comprend les revenus d'activité nets des
cotisations sociales, les indemnités de chômage, les retraites et pensions, les revenus du
patrimoine (fonciers et financiers) et les autres prestations sociales perçues, nets des impôts
directs. Ces derniers incluent l'impôt sur le revenu, la taxe d'habitation, la contribution
sociale généralisée – CSG –, contribution à la réduction de la dette sociale – CRDS – et les
prélèvements sociaux sur les revenus du patrimoine » (définition c1458). N'y entrent ni un
transfert en capital (succession, aide à des travaux), ni un transfert en nature (soins), ni
un prix (TVA, accises, taxe carbone), ni un impôt d'entreprise. Concept retenu : INSEE strict,
prix exclus (arbitrage du mainteneur) ; la variante « niveau de vie net de TVA » de l'IPP
donnerait environ +0,00009 par Md€ de TVA payée par les ménages (aucun programme publié
concerné).

*Zéros faute de source : sens de chaque limite.* Impôt sur le revenu ciblé : une mesure qui vise
les dixièmes du milieu (concentration sous G) réduirait l'indice, une baisse du bas du barème
l'augmenterait ; le signe dépend de l'instrument, que le levier ne dit pas. CSG progressive à
recette constante : réduirait l'indice ; effet omis (aucun programme publié). Âge de départ : un
recul de l'âge accroît probablement les inégalités (espérance de vie et emploi des seniors plus
faibles chez les ouvriers) ; effet omis, à l'avantage des programmes qui reculent l'âge, au
détriment de ceux qui l'avancent. Rémunérations publiques : une hausse proportionnelle aux
salaires de l'ensemble des salariés augmenterait légèrement l'indice, mais les salaires publics sont moins
dispersés que ceux de l'ensemble des salariés : le sens même de l'effet n'est pas assuré, il est compté à
zéro (arbitrage du mainteneur).

*Limites déclarées, au même sens pour tous les programmes.* (1) Regroupement par dixièmes : les
écarts internes à chaque dixième sont ignorés (sur la figure 1 de la fiche « Redistribution
monétaire », le regroupement minore les K de 3 à 7 %) ; avec le Gini publié de 2021 (0,294) au
lieu de celui des mêmes dixièmes (0,286), les K varient de 1 à 12 %. (2) Premier ordre : effet
linéaire en montant ; un retrait de T Md€ vaut exactement T × (C − G) / (Y ± T), soit 8 %
d'écart à 120 Md€. (3) Un montant constant en euros courants garde son effet alors que son
poids dans un revenu qui croît baisse : surestimation d'environ 3 % par an d'écart à 2025 ; les
montants des programmes sont lus dans l'unité de leur encodage. (4) SMIC : chiffrage statique
pour +1 %, à emploi inchangé ; extrapolé linéairement aux hausses encodées (jusqu'à +21 %), il
surestime probablement la baisse de l'indice (diffusion au-dessus du SMIC, dégressivité de la
prime d'activité, effets d'emploi signalés par le même rapport).

**Rabot uniforme (lot 4).** Chaque catégorie de prestations en espèces coupée à son coefficient par Md€
(minima sociaux et AAH : prestations ciblées ; allocations chômage : règle montant ; pensions :
coefficient des pensions, plage publiée) ; santé, APA et autres catégories : 0 (hors du revenu disponible) ; montant d'année pleine
que fixe le taux (base 2025), émis une fois au changement du taux. Jusqu'ici 0,10 × taux × part sociale
× phasage, sans source, réémis chaque année dans un agrégateur cumulatif.

**Hausse de 2026 sur les revenus du capital (lot 4, équations).** Le budget voté encode la hausse de la CSG sur
les revenus du capital par le taux global du levier CSG (le taux qui produit le rendement voté sur l'assiette du
levier). Cette part du taux, entre 9,7 % et le taux du droit en vigueur, prend le coefficient du capital : c'est
le même instrument qu'un programme retire par le levier « fiscalité du capital », au même coefficient. Le reste
d'une variation du taux de CSG garde celui de la CSG.

**Règles qui ne sont pas en Md€ (lot 4).** SMIC : chiffrage statique sourcé pour +1 % (plage publiée), sans
l'ancien facteur 0,22 ; extrapolation linéaire déclarée comme convention. Âge de départ et CSG progressive : zéro
faute de source (§ Méthode unique du Gini, sens de chaque limite) ; le mécanisme du canal d'âge (écart à la
référence de l'année, 10 % de résidu des cohortes) est gardé, éprouvé en test par un coefficient sonde. Aucune
règle ne garde l'ancien facteur d'atténuation.

**Assemblage du Gini (lot 4 ; arbitrage du mainteneur).** L'indice publié de l'année vaut la base (0,302)
plus la somme des effets émis par les mesures jusqu'à cette année, chacun émis une fois, l'année où la mesure
s'applique (les calendriers des programmes jouent par leurs profils). Deux bornes de sécurité, [0,25 ; 0,40]
(`GINI_SOFT_FLOOR`, `GINI_HARD_CEILING`), restent le seul garde-fou : une valeur qui en sortirait serait publiée à
la borne, avec un avertissement ; aucun programme publié ne les approche (minimum 0,276 en 2032).

*Facteur d'atténuation `GINI_IMPACT_SCALE` = 1,0* : les coefficients sont physiques et bornés un par un, il n'y a
plus rien à atténuer ; la justification de 0,22 (« IPP/OFCE 2022 ») n'a pas de passage retrouvé, et la source même
des coefficients le contredit : la masse des prestations ciblées (5,8 % du niveau de vie) pesée par leur
coefficient retrouve 76 % de la contribution que publie l'INSEE (0,0551 ; écart entre effet marginal et effet
moyen), contre 17 % avec 0,22 (verrouillé par test).

*Retirés au lot 4, faute de source* (arbitrage du mainteneur) : la convergence de 35 % par an vers la cible
(`GINI_CONVERGENCE_RATE`, v0.4.0) et l'amortissement des baisses à l'approche de 0,25, qui ne freinait que les
programmes qui réduisent les inégalités. Pour les programmes publiés, en 2032 : l'indice des trois programmes les
plus redistributifs baisse de 0,0035 à 0,0053 de plus ; ceux qui montent en charge atteignent plus tôt leur niveau ;
aucun rang ne change.

*Limite déclarée : la vitesse.* L'effet d'une mesure arrive en entier l'année où elle s'applique. La série de
l'INSEE bouge rarement de plus de 0,01 d'une année sur l'autre (au plus 0,014, entre 2012 et 2013) ; un
programme qui concentre de fortes mesures redistributives sur sa première année affiche un saut plus grand (jusqu'à
environ 0,025 en 2028 parmi les programmes publiés, mesuré le 16/11/2026). Sens : la trajectoire est plus rapide
que ce que l'histoire a observé ; le niveau atteint, lui, ne dépend pas de ce choix. L'ancienne garde de CI
(|ΔGini| ≤ 0,01 par an) est retirée avec la convergence.

*Ancrage, verrouillé par test* : la cible d'un programme figé réduit l'indice d'au plus la réduction due à
l'ensemble des transferts du champ de l'INSEE (0,092 ; le test rougit si toutes les émissions sont multipliées par
environ 6), et un Md€ de prestations ciblées, lu à travers l'assemblage et pesé sur leur masse, retrouve entre 60
et 120 % de leur contribution publiée (0,0551 ; mesuré 76 % ; le test rougit pour un facteur global hors de 0,8 à
1,6).

*Historique.* De la v0.4.0 au lot 4, trois étages (facteur 0,22, convergence de 35 % par an, amortissement près
de 0,25) corrigeaient une somme brute de règles héritées qui sur-réagissait d'un facteur ~4 et saturait le plancher
dès la première année. La méthode unique (coefficients physiques et bornés) a rendu ces trois étages sans objet.

**Competitivite :**
- Baseline 2025 : 100 (indice)
- Positif = Amelioration competitivite entreprises
- Negatif = Degradation competitivite

### Indice de pouvoir d'achat (RDB-moteur, v0.6.8)

- Baseline 2025 : 100 (indice). Positif = hausse du pouvoir d'achat par unité de consommation.
- **Définition (celle de l'INSEE)** : revenu disponible brut (RDB) des ménages, déflaté par le
  prix de leur consommation, rapporté au nombre d'unités de consommation (UC). Indice de
  NIVEAU : l'année t ne lit que les grandeurs de l'année t (`engine/rdb.py`, fonctions pures).
- **Formule exacte** :

  ```
  RDB(t) = (RDB₂₀₂₅ − R_pub) × PIB_nominal(t) / PIB_nominal(2025)      revenus privés et de base
         + R_pub × (1 + v)^(t − 2025) × D(t)                           rémunérations publiques nettes
         + Σ_mesures [ prestations − prélèvements directs
                       + n × rémunérations publiques + salaires privés nets ]   (Md€ de l'année)
  P(t)   = D(t) × (1 + Σ_mesures τ± × p_m × prélèvements indirects_m / C(t)) × K(t),   C(t) = (1 − s) × RDB_base(t)
  K(t)   = Π_{2026 ≤ y ≤ t} (1 + COIN_PRIX_CONSOMMATION[y])   (v0.6.9 ; facteur 1 pour une année absente de la table)
  PA(t)  = 100 × [RDB(t) / RDB₂₀₂₅] / P(t) / (1 + γ)^(t − 2025)
  borne  = variation annuelle ± PA_VARIATION_ANNUELLE_MAX (filet, ne mord sur aucun scénario publié)
  ```

  `PIB_nominal(t)` et `D(t)` sont le PIB et le déflateur INTERNES du moteur (lot 5d) : l'effet prix des
  rémunérations publiques ne relève que le PIB et le déflateur publiés ; il ne touche ni le revenu ni les prix
  à la consommation des ménages. Depuis les sorties publiées, D(t) = Déflateur × (PIB − coût) / PIB, où coût est
  la somme des canaux `remunerations_publiques` de l'année.

  | Symbole | Valeur | Source (vérifiée en ligne le 07/10/2026, pages HTML et résumés) |
  |---|---|---|
  | RDB₂₀₂₅ | 1 870 Md€ | INSEE : 1 861,1 Md€ en 2024 (*France portrait social*, 18/11/2025) × 1,005 (évolution 2025 en valeur, *La consommation des ménages en 2025* ; Insee Première n° 2105) |
  | s | 17,9 % | INSEE, taux d'épargne 2025 (*La consommation des ménages en 2025*) |
  | γ (UC) | 0,4 %/an | INSEE : effet « par UC » −0,5 pt (2024), −0,3 pt (2025), Insee Première n° 2105 ; 0,4 implicite dans la prévision 2026 (Note de conjoncture de juin 2026 : −0,3 % / −0,7 % par UC) |
  | n | 0,535 | FIPECO 2025 : 247,6 Md€ bruts / 370,0 Md€ cotisations employeurs incluses × 0,80 du brut au net (taux de service-public.fr F468 ; part de primes ~25 % **non sourcée**) ; avant impôt sur le revenu |
  | R_pub | n × 370,0 ≈ 198 Md€ | idem |
  | p_m (TVA taux normal) | 1,0 (borne haute, limite déclarée) | depuis le lot 3, l'assiette du levier est le point net du seul taux de 20 % (Trésor-Éco n° 371, tableau 2 : 7,5 Md€ en 2025), payé par les ménages et par les entreprises qui ne récupèrent pas la TVA ; la part des ménages n'est publiée que tous taux confondus (65,1 % des recettes nettes en 2022, administrations comprises) : la recette entière reste comptée sur les ménages, ce qui majore l'effet sur le pouvoir d'achat (+1 point : −0,65 point d'indice en 2032 à 1,0, contre −0,53 à 0,758 et −0,48 à 0,652, budget voté, mode cadre) |
  | p_m (TVA énergie) | 56,0 % | base = toute l'énergie, entreprises comprises. DG Trésor, *Analyse de la composition des recettes de TVA* (2022), citée par le Sénat (rapport n° 942, 2024-2025) : 65,1 % des recettes de TVA nette proviennent des ménages, « dont 86 % de leur consommation et 14 % de leurs investissements » ; 0,651 × 0,86. Moyenne tous biens appliquée à l'énergie faute de répartition propre sourcée (approximation) |
  | p_m (taxe carbone) | 64,6 % | recette totale de la composante carbone. Conseil général de l'économie, *Les outils de régulation économique du carbone*, § 5.6 : 5,3 Md€ payables par les ménages sur 8,2 Md€ (2019) |
  | τ+ / τ− | 1,0 / 0,5 | Benzarti, Carloni, Harju & Kosonen, JPE 128(12), 2020 : « prices respond twice as much to VAT increases as to VAT decreases » ; Carbonnier, JPubE 91(5-6), 2007 : baisses répercutées à 57 % et 77 % ; Benzarti & Carloni, AEJ:EP 11(1), 2019 : baisse de la restauration, consommateurs les moins bénéficiaires |
  | D(t) | déflateur du PIB du moteur | — |
  | K(t) | 1 (table vide en v0.6.9) | écart cumulé prix de la consommation − prix du PIB constaté (termes de l'échange) ; paragraphe « Conjoncture observée » de la section Inflation et Courbe de Phillips |
  | v | 0,6 %/an | volume tendanciel de la masse salariale du statu quo du moteur (`spending_growth_rates`, « GVT + point d'indice ») |

- **Canaux par levier** (chaque handler émet la clé `menages`, `handlers/_types.canaux_menages`,
  en Md€ de l'année, écart au statu quo ; contrat verrouillé pour les 33 handlers) :

  | Canal | Leviers | Effet sur l'indice |
  |---|---|---|
  | prélèvements directs | IR, décote, élargissement IR, CSG, cotisations salariales, impôt sur le revenu d'une hausse du SMIC (Trésor), abattement retraités, ISF climatique, IFI et part ménages de la taxe foncière (`fiscalite_patrimoine` : 27,0 Md€ sur 44,2, Insee 2025 ; la part des entreprises passe par la croissance ; hors droits de succession : transfert en capital, hors RDB) | −1 € de RDB par € |
  | prélèvements indirects | TVA générale, TVA énergie, taxe carbone | par les prix : τ± × p_m (part ménages propre à la base du levier) |
  | prestations | retraites (âge, durée, indexation), allocations chômage, ASU (effort + recours, hors coût de bascule), indexation des minima, franchises santé, part « prestations en espèces » du rabot uniforme (pensions, chômage, minima, AAH ; santé et APA, transferts en nature, à 0 comme dans le levier santé), baisse des prestations quand le SMIC monte (Trésor, tableau 8) | +1 € de RDB par € |
  | rémunérations publiques | point d'indice, revalorisation des enseignants, paie publique d'une hausse du SMIC (Trésor, tableau 9) | n = 0,535 € par € de coût |
  | salaires privés | SMIC : salaires nets du tableau 8 du Trésor (revenu brut − cotisations des salariés), moins la part nette des agents publics | +1 € de RDB par € |
  | **aucun** (par la croissance) | impôts de production, IS, cotisations patronales, niches et subventions des entreprises, superprofits, exonérations de cotisations patronales, embauches et suppressions de postes publics, investissement, rénovation (aide à l'investissement, hors RDB), recherche, efficience, fraude, gestion de la dette ; mesures « formule » côté dépenses (côté recettes : avis explicite dans la réponse, aucune n'existe au registre) | 0 direct |

- **Arbitrages du mainteneur (v0.6.8)** : (1) un impôt sur les entreprises n'a aucun effet
  direct sur le pouvoir d'achat, il passe par la croissance et l'emploi ; (2) la dépense
  publique n'a aucun effet direct — exception : une hausse de rémunération des agents en place
  est un revenu, comptée UNE fois, à sa part nette ; la masse salariale publique de base suit
  son volume tendanciel au prix du déflateur, identique en réel pour tous les scénarios (ni la
  croissance, ni l'écart de production, ni l'indexation passée n'y touchent) : la croissance
  n'agit que sur la part privée ; (3) répercussion asymétrique de la fiscalité indirecte, sourcée ; (4) les baisses
  d'indice qui résultent de la suppression de coefficients non sourcés sont acceptées et
  publiées (tableau ci-dessous) ; (5) indice par UC, ancré sur l'INSEE.
- **Hypothèses affichées** : salaires privés, revenus des indépendants et du patrimoine,
  prestations et prélèvements DE BASE évoluent à parts constantes du PIB nominal (le moteur ne
  les modélise pas séparément) ; l'emploi agit à travers le PIB (un facteur « emploi » en sus
  compterait deux fois les effets de la loi d'Okun) — les effets directs d'une mesure sur le
  chômage (SMIC, progressivité de la CSG) ne sont donc pas retranchés des salaires ; la part
  nette des rémunérations publiques est avant impôt sur le revenu ; une mesure à recette nulle
  (CSG progressive) ne change pas le RDB agrégé : son effet est sur le Gini.
- **Ancrage INSEE** : statu quo 2026-2035, +0,64 %/an par UC en moyenne — INSEE +0,4 %/an en
  2011-2019, +0,5 %/an depuis 2010 (test : [0 ; 1] %/an). Année 2026 : +0,8 % servi (budget
  voté : +0,7 %) contre −0,7 % par UC prévu par l'INSEE (Note de conjoncture du 17/06/2026,
  vue d'ensemble) — la Note du 10/09/2026 confirme : pouvoir d'achat −0,4 % (≈ −0,8 % par
  UC), PIB +0,4 %, inflation 2,4 % en août. L'indice suit le PIB réel par UC (vérifié à
  0,15 pt) : l'écart (≈ 1,5 pt) vient de la croissance 2026 du moteur (1,24 % contre 0,4 %,
  ≈ 0,8 pt) et de son prix — déflateur du PIB 1,34 % contre des prix de consommation
  tirés par l'énergie importée (≈ 2 %, ≈ 0,6 pt) —, pas du passage au RDB. Tolérance du
  test : 1,6 pt. Correctifs possibles (non appliqués) : recaler la macro 2026 (toutes les
  colonnes, release dédiée) ; ou un coin « prix importés » 2026 dans le seul prix de la
  consommation, à sourcer (déflateurs INSEE 2026 non trouvés en page HTML).
- **Ce qui a disparu (v0.6.7 → v0.6.8)** : `PA(t) = PA(t−1) × (1 + g(t) + micro(t))`, où
  `micro(t)` sommait vingt coefficients forfaitaires (un seul nommé, aucun sourcé),
  transmettant de 2 % à 175 % de leurs euros, sept d'entre eux réémis chaque année (un niveau
  devenu croissance), atténués de moitié à partir de 2027 selon l'année calendaire, et
  ajoutés à la croissance que les mêmes dépenses produisaient déjà (double compte).
  Diagnostic : `docs/plans/v068-pouvoir-achat.md` du dépôt parent.
- **Avant / après (dix scénarios publiés, statu quo, même moteur par ailleurs : toutes les
  autres colonnes sont bit-identiques)** :

  | Scénario | 2030 v0.6.7 | 2030 v0.6.8 | 2035 v0.6.7 | 2035 v0.6.8 |
  |---|---|---|---|---|
  | Statu quo | 106,0 | 103,6 | 111,5 | 106,6 |
  | Budget 2026 voté (plf_2026) | 105,7 | 103,3 | 111,3 | 106,5 |
  | RN | 110,3 | 105,0 | 116,0 | 107,8 |
  | LFI | 117,4 | 108,1 | 123,2 | 109,4 |
  | Renaissance | 107,2 | 104,8 | 110,3 | 107,1 |
  | Horizons | 110,9 | 102,4 | 116,9 | 105,8 |
  | LR | 110,3 | 105,2 | 115,1 | 107,5 |
  | PS | 113,5 | 106,5 | 119,7 | 108,8 |
  | Écologistes | 112,2 | 105,0 | 119,1 | 108,2 |
  | Institut Montaigne, rabot | 97,2 | 95,9 | 101,1 | 100,6 |
  | Institut Montaigne, compétitivité | 109,4 | 104,2 | 115,5 | 107,3 |
  | **Étendue (10 scénarios)** | **20,2** | **12,2** | **22,1** | **8,8** |

  Lecture : environ −2,1 pt pour tous en 2030 (−4,3 en 2035) viennent du passage « par UC »
  (0,4 %/an, identique pour tous ; mesuré sur le statu quo : indice × (1,004ⁿ − 1)) ; le
  reste est l'effet de la définition. Écarts au statu quo en 2030 (valeurs du tableau),
  v0.6.7 → v0.6.8 : budget voté −0,3 → −0,3 ; RN +4,3 → +1,4 ; LFI +11,4 → +4,5 ;
  Renaissance +1,2 → +1,2 ; Horizons +4,9 → −1,2 ; LR +4,3 → +1,6 ; PS +7,5 → +2,9 ;
  Écologistes +6,2 → +1,4 ; rabot −8,8 → −7,7 ; compétitivité +3,4 → +0,6. Huit écarts se
  resserrent, deux sont inchangés à 0,1 pt près. Ceux qui se resserrent le plus sont les
  programmes dont l'indice reposait sur des coefficients sans source — impôts de production
  (175 % de transmission pour un impôt d'entreprise), point d'indice et dépenses comptés en
  sus de la croissance, rénovation réémise chaque année. En 2035 le rabot passe de −10,4 à
  −6,0 : ses coupes de prestations sont comptées en euros de l'année au lieu d'un
  coefficient composé chaque année, et seules les prestations en espèces entrent au RDB
  (la santé et l'APA, transferts en nature, n'y entrent pas, comme dans le levier santé).

### Calibration Baseline Validee (v0.6.0)

Reference de calibration : mission Jaravel/Ragot/Tavernier/Valla (IGF, juillet
2026, commandee par les ministres Lescure et Amiel) — tendanciel a politique
inchangee, Tableaux 3/4/5/6. Corridor verrouille en CI
(`tests/test_calibration_mission_v060.py`) sur le scenario « Budget 2026
vote » : deficit -5,0 -> -6,76 %, dette 118,4 -> 130,5 %, charge de la dette
78 -> 124 Md EUR, taux apparent 2,2 -> 3,1 % (2026-2030).

**Valeurs réelles du scénario de référence face à la mission** (v0.6.7, lot 3b — TOL_DETTE portée de 1,6 à 2,0 pt ; HCFP : dette 2030 ≈ 129,5 % ; re-mesurées en v0.7.2 : dette de départ 115,7 %, tendanciel dérivé 1,2285 %, scénario « Budget 2026 voté, réajusté sur l'exécution 2026 » réencodé le 08/11/2026, défense 58, franchises 120 %, surtaxe IS 6,8) :

| Année | Dette moteur | Dette mission | Écart | Déficit moteur | Déficit mission | Niveau PIB nominal vs mission |
|---|---|---|---|---|---|---|
| 2026 | 118,04 | 118,4 | −0,36 | −5,39 | −5,00 | 0,47 % |
| 2027 | 120,53 | 121,4 | −0,87 | −5,54 | −5,88 | 0,40 % |
| 2028 | 123,23 | 124,2 | −0,97 | −5,77 | −6,21 | 0,21 % |
| 2029 | 126,18 | 127,3 | −1,12 | −6,07 | −6,57 | 0,19 % |
| 2030 | 129,41 | 130,5 | −1,09 | −6,43 | −6,76 | 0,18 % |

Re-mesurées le 12/11/2026 (release de paramètres P, moteur v0.8.1) : la référence ne compte plus la surtaxe d'IS votée pour 2026 seulement (0 dès 2027, valeur datée ; en mode historique, 0 dès 2026). Re-mesurées le 15/11/2026 (lot 1 : terme d'effort de l'inflation et éviction retirés, coefficient des transferts recalé ; 2027-2030 seulement, 2026 identique), puis au lot 5 (la hausse de défense du scénario prend le coefficient de la coupe de dépense courante ; 2027-2030 seulement). Re-mesurées le 16/11/2026 (lot 6, calendrier de l'impulsion : le budget de chaque année agit dès cette année ; 2026-2030), puis après le recalage des coefficients d'impact du même lot (release de paramètres), puis au lot 5c (la dotation du scénario, sous le défaut du moteur, a pour moitié le traitement de l'investissement local ; 2027-2030 seulement). Lecture : le PIB nominal est désormais honnête (niveau 2030 à +0,18 % de la mission, tolérance ±0,6) ; l'écart de dette (−1,09 pt en 2030) révèle un solde primaire du statu quo légèrement trop favorable — le résidu (b) décrit dans `tests/test_calibration_mission_v060.py`, que le PIB nominal trop bas compensait jusqu'ici. Chantier ouvert v0.6.8 (bloc dépenses). Statu quo NU (aucune mesure) : dette 2030 129,12 %, 2035 151,17 %.

| Indicateur | Valeur | Horizon |
|------------|--------|---------|
| Croissance reelle depenses primaires | +0,8 a +1,4%/an CHAQUE annee | Tendanciel officiel (mission IGF : Ondam +3,5 % courants, retraites 354->401 Md EUR) |
| Elasticite recettes / PIB nominal | 1,00 | Ratio recettes/PIB stable par construction (~52,2%) |
| Deficit | **-5,39 %** PIB | 2026, scenario de reference (mission : -5,00 par hypothese ; statu quo NU : -5,30 ; v0.8.1 : surtaxe IS 2026 non comptee en mode historique) |
| Dette | **129,41 %** PIB | 2030, scenario de reference (mission : 130,5 ; ecart -1,09 pt (lot 5c : dotation pour moitie en investissement local ; -1,14 au lot 6, option du rythme de la dépense courante ; -1,32 au lot 6, profil de l'investissement ; -1,20 au lot 6, paramètres recalés ; -1,18 au lot 6, calendrier de l'impulsion, équation ; -1,27 au lot 5 : hausse de depense courante au coefficient de sa coupe ; -1,21 au lot 1 : terme d'effort de l'inflation et eviction retires, coefficient des transferts recale ; -1,28 en v0.8.1 : surtaxe IS arretee ; -1,69 en v0.7.2 : dette de depart 115,7 % et reencodage du 08/11/2026 ; -1,86 avant) depuis le re-ancrage DERIVE du potentiel v0.6.7, qui rend le PIB nominal honnete et revele le residu (b) — +0,05 sans bruit avant re-ancrage, -1,98 avec le bruit ; la v4.0 affichait +2,4 pt) |
| Dette | **129,23 %** PIB | 2030, statu quo NU (aucune mesure) — l'objet de calibration, servi nulle part |
| Dette | **151,32 %** PIB | 2035, statu quo NU (taux honnetes v0.6.0 : marginal 3,47 % @ 117,6 % AFT, boule de neige reelle r > g des 2029 ; scenario de reference : 151,49) |
| Deficit | **-9,06 %** PIB | 2035, statu quo NU (charge d'interets ~7 % du PIB ; scenario de reference : -9,04) |
| Croissance potentielle | tendanciel 1,2285 % ; potentiel TOTAL du statu quo 1,1% a la dette 2025 | Derive (v0.6.7) : potentiel officiel 1,1 % (mission IGF 07/2026, 1,2/1,2/1,0/1,0) + traînée de la dette heritee 0,1285 pt (-0,005 x (115,7 - 90) %, dette fin 2025 de l'Insee Premiere n° 2106, mai 2026 ; 0,128 pt sur 115,6 avant v0.7.2) — la traînee supplementaire due a la dette qui monte ensuite reste un effet du modele |
| Chomage NAIRU | ~7,5% | Structurel |
| Inflation tendancielle | 1,6% = point fixe Phillips (`INFLATION_STRUCTURELLE`), deflateur du PIB | Effective statu quo ~1,2-1,5% (output gap negatif) |
| Cible BCE | 2,0% (`BCE_CIBLE_INFLATION`) | Garde-fou de surchauffe, inactif en statu quo |

**Note v0.6.0** : les niveaux 2035 ont fortement monte vs v0.5.1 (dette ~150 ->
~168 %) : l'audit externe d'aout 2026 a montre que le taux marginal 1,9 %
(ancre ZIRP morte, ecart 148 pb au marche) etouffait l'effet boule de neige —
cf. § Taux d'Interet. Le message est celui de la mission IGF : « a politique
inchangee », la trajectoire est insoutenable.

**Note v4.0** : l'ancien assemblage affichait dette 2035 ~132% et deficit 2035 ~-6,0%. L'ecart ne venait pas d'hypotheses economiques differentes mais d'un « assainissement implicite gratuit » (~24 Md EUR/an) cree par la mecanique d'assemblage elle-meme (lag du deflateur sur les flux, couture de la « bridging year », erosion et elasticite differenciee des recettes). La baseline v4.0 est la trajectoire honnete « a politique inchangee » ; ces proprietes sont verifiees en continu par `tests/test_baseline_properties.py`.

---

## Sources et References

### Release E (v0.8.0)

- **Bom & Ligthart 2014** (*Journal of Economic Surveys* 28(5)) : élasticité du PIB au capital public
  (0,106, méta-analyse de 578 estimations) — pente du canal capital public (÷ stock INSEE hors terrains ×
  efficience FMI 2015).
- **Fieldhouse & Mertens 2024** (Dallas Fed WP 2305 ; *AER* 2026) : élasticité de production du capital de
  R&D public (0,06 R&D civile) — pente du canal recherche.
- **DG Trésor, Trésor-Éco n° 394 (2026)** : ThreeME, subvention à la rénovation des logements sans effet de
  niveau durable — canal rénovation à 0.
- **Gurara, Kpodar, Presbitero & Tessema 2020** (FMI WP 20/48) et **Presbitero 2016** (*JDE* 120) :
  contraintes d'absorption de l'investissement public (échelle du plafond).
- **Saez & Zucman 2019** (*Brookings Papers on Economic Activity*, tableau 2 p. 461) et **Jakobsen et al.**
  (Danemark, p. 36) : bornes de la fourchette d'évitement de l'impôt plancher (15 % à 55 % environ).
- **Sénat, rapport n° 689 (2025)** : rendement sans comportement d'un impôt plancher de 2 % (20 Md€).
- **IPP, note n° 46 (2019)** : élasticité des dividendes (0,9) ; **Colliard & Hoffmann 2017** (*Journal of
  Finance*) : volumes de la taxe sur les transactions financières.
- **Insee, comptes nationaux annuels, tableau 3.217 (2025, publiés le 29/05/2026)** : recettes de l'IFI, des
  droits de mutation à titre gratuit et de la taxe foncière (dont part des ménages) — bases du curseur « Fiscalité
  du patrimoine », IFI remplacé par l'ISF, borne basse des droits de succession.
- **Insee, comptes de la Nation, tableau 2.101 (2025)** : masse des cotisations sociales à la charge des salariés
  (D613CE, 138,217 Md€) et salaires et traitements bruts (D11, 1 157,166 Md€) — coût d'un point de cotisation
  salariale (1 % de D11) et maximum du curseur (D613CE / 1 % de D11 ≈ 11,94 points, le taux moyen réel).


### Institutions Officielles Francaises

- **DGFiP** (Direction Generale des Finances Publiques)
- **INSEE** (Institut National de la Statistique)
- **DREES** (Direction de la Recherche, des Etudes, de l'Evaluation et des Statistiques)
- **DARES** (Direction de l'Animation de la Recherche)
- **COR** (Conseil d'Orientation des Retraites)
- **CNAM** (Caisse Nationale d'Assurance Maladie)
- **Unedic** (Union nationale interprofessionnelle pour l'emploi)
- **Senat** (Commission des finances) — rapports finances 2024

### Organismes d'Audit

- **Cour des Comptes** - Rapports sur depenses publiques
- **IGAS** (Inspection Generale des Affaires Sociales)
- **IGF** (Inspection Generale des Finances)

### Think Tanks et Recherche

- **OFCE** (Observatoire Francais des Conjonctures Economiques)
- **IPP** (Institut des Politiques Publiques)
- **France Strategie**
- **CAE** (Conseil d'Analyse Economique)
- **Rexecode** (Centre de Recherche)

### Organismes Internationaux

- **OCDE** - Taxing Wages, Health at a Glance ; "Getting Infrastructure Right" (2017, cité jusqu'au lot 2 pour un retour fiscal de la transition qu'il ne contient pas)
- **FMI** - Selected Issues France, Fiscal Monitor 2014
- **EU Tax Observatory** (Gabriel Zucman)
- **OMS** (Organisation Mondiale de la Sante)

### Recherche Academique (v3.0)

- **Blanchard & Leigh 2013** : Multiplicateurs fiscaux en periode de consolidation
- **Alesina & Ardagna 2010** : Effets confiance de l'austerite (conteste IMF 2012)
- **DeLong & Summers 2012** : hysteresis en economie deprimee a la borne zero (effet de niveau sur le potentiel proportionnel a l'impulsion budgetaire) ; citee jusqu'a v0.8.1 pour une « cicatrice d'austerite » a seuil, plafonnee et a sens unique, qu'elle ne contient pas (retiree au lot 1)
- **Fatas & Summers 2018** : couts permanents des consolidations de 2010-2011 (regression lineaire, en crise) ; meme remarque
- **Bom & Ligthart 2014** : Elasticite output du capital public (stock model)
- **Kramarz & Philippon 2001** : Effets du salaire minimum sur l'emploi
- **Herndon, Ash & Pollin 2014** : Critique Reinhart-Rogoff (seuil 90%)
- **Auerbach & Gorodnichenko 2012** : Multiplicateurs en recession vs expansion
- **Romer & Romer 2010** : Multiplicateurs fiscaux (tax)
- **Guajardo, Leigh & Pescatori 2014** : Critique effet confiance Alesina
- **Alesina, Favero & Giavazzi 2015** (*J. International Economics* 96) et **FMI, WEO oct. 2010 ch. 3** : composition des consolidations (attenuation « confiance » retiree en v0.6.7)
- **Hussain & Malik 2016** (*JEDC* 69) et **Jones, Olson & Wohar 2015** (*J. Macroeconomics* 43) : asymetries de signe des chocs fiscaux, de sens oppose selon le pays (baisse d'impots symetrique en v0.6.7)
- **Khan & Luintel 2006** : Productivite de la recherche publique et croissance potentielle
- **Ramey 2019** : multiplicateurs de dépense « 0.6 to 1 » (cible de la coupe de dépense courante) ; citée jusqu'au lot 6 pour les profils temporels différenciés, sans calage à une valeur (le profil INVEST suit désormais le FMI, WEO oct. 2014, tableau 3.4)
- **FMI 2015** : Investissement public et croissance dans les economies avancees (Fiscal Monitor)
- **FMI 2020** : Politiques publiques pour la reprise post-COVID (retours investissement vert)
- **Cohen, Neumann & Weinstein 2008** : « Does Preventive Care Save Money? Health Economics and the Presidential Candidates », *New England Journal of Medicine* 358(7):661-663, DOI 10.1056/NEJMp0708558 — borne le taux de compensation de la prevention (v0.6.1)
- **van Baal et al. 2008** : « Lifetime Medical Costs of Obesity : Prevention No Cure for Increasing Health Expenditure », *PLoS Medicine* 5(2):e29 — cout des annees de vie gagnees
- **Vos et al. 2010** : *ACE-Prevention Final Report*, University of Queensland / Deakin University — borne haute absolue du retour de la prevention (ratio 2,4, mesures dominantes)
- **OCDE 2019** : *The Heavy Burden of Obesity — The Economics of Prevention*, chapitre 6 (Goryakin et al.) — effet budgetaire chiffre de la meilleure intervention
- **DREES 2024/2025** : *Les depenses de sante en 2023* (Panoramas, fiche 21) et edition 2025 — prevention institutionnelle, perimetre SHA
- **OCDE 2025** : *Health at a Glance 2025*, note pays France — part de la prevention dans la depense de sante (2,3 % France / 3,4 % OCDE)
- **IGAS 2024** (Bras & Monasse) : absence d'evaluation structuree de l'efficience des actions de prevention et promotion de la sante en France

### Programmes Politiques

- **PLF 2026** - Projet de Loi de Finances
- **PLFSS 2025** - Financement Securite Sociale
- **Plan antifraude 2023-2027** (Gouvernement) - source des tooltips fraude sociale / digitalisation controles
- **NFP 2027** - Nouveau Front Populaire
- **RN 2027** - Rassemblement National

### Règle d'encodage des programmes politiques

Règle écrite le 07/10/2026, appliquée à tous les programmes publiés depuis la release
de paramètres P (moteur v0.8.1, 12/11/2026) : ils sont ré-encodés le même jour sur leurs
sources, et chaque paramètre qui s'écarte de la référence porte une source (adresse
officielle, date de lecture, citation vérifiée sur le texte téléchargé, règle appliquée),
dans le registre `scenariosSources.json` du dépôt parent.

Référence commune : le **droit en vigueur au premier budget du mandat** (budget 2026
voté, réajusté sur l'exécution 2026, sans les mesures votées pour une durée limitée),
c'est-à-dire les paramètres du scénario de référence (`plf_2026`). Ci-dessous, « droit en
vigueur » désigne toujours cette référence.

1. **Coût annoncé par le candidat.** Une mesure est encodée au paramètre publié
   par le candidat ou sa formation. À défaut de paramètre, elle est encodée au
   montant qu'il annonce. Exemple : la TVA sur l'énergie du RN est encodée à son
   taux publié de 5,5 %.
2. **Le simulateur chiffre lui-même.** L'écart entre ce chiffrage et celui du
   candidat est signalé dans la fiche du programme. Il n'est jamais comblé en
   ajustant un paramètre.
3. **Jamais d'autofinancement comportemental.** Un effet retour annoncé (« la
   mesure se finance d'elle-même », « neutre pour les finances publiques ») n'est
   pas crédité d'office. Seuls les canaux macroéconomiques du moteur, les mêmes
   pour tous les scénarios, produisent des effets retour.
4. **Aucune économie ni dépense non sourcée.** Un paramètre qu'aucune source
   vivante ne chiffre ni ne fixe est posé au droit en vigueur.
5. **Aucun chiffrage de tiers.** Une mesure s'encode quand la source du programme
   en donne la nature (qui paie ou qui reçoit, quel type de dépense ou de recette)
   et un montant ou un paramètre. Une mesure annoncée sans chiffre ni paramètre
   n'est pas encodée : la fiche l'affiche comme annoncée, non modélisée. Un
   chiffrage publié par un tiers ne sert jamais à encoder un programme ; les
   estimations publiques servent seulement à régler le moteur, de la même façon
   pour tous les scénarios. (Cette règle remplace, depuis la release de
   paramètres P, l'exception qui encodait une mesure non chiffrée sur des bornes
   de tiers.)
6. **Un levier absent de la source vivante est retiré.** Quand un document plus
   récent (contre-budget, projet chiffré) remplace la source d'un programme, une
   mesure de l'ancien document qui n'y figure plus revient au droit en vigueur.
   Elle n'est pas conservée par inertie.
7. **Les cibles ne sont pas des paramètres.** Un déficit, une dette ou une
   enveloppe d'économies annoncés sont des résultats. L'écart entre ces cibles et
   la trajectoire calculée mesure la part non modélisée ou non ventilée du
   programme.

En résumé, chaque scénario porte ce que sa source chiffre, ni plus ni moins, et
ses hypothèses de modélisation sont écrites dans sa fiche.

**Mise en œuvre : un levier retiré se pose à la valeur de `plf_2026`, il n'est
jamais omis.** Une clé absente vaut le défaut du moteur (année 2025). Ce défaut
diffère du droit en vigueur pour plusieurs leviers. Garde exécutable :
`tests/test_reencodage_v066.py` (avec, dans le dépôt parent, le registre des sources).

---

## Limites et Precautions

1. **Incertitude parametrique** : Les elasticites sont des estimations moyennes
2. **Delais de transmission** : Certains effets mettent 5-10 ans a se materialiser
3. **Interactions** : Les mesures peuvent se renforcer ou s'annuler
4. **Contexte macroeconomique** : Hypotheses de croissance mondiale, taux directeurs BCE
5. **Perimetre comptable** : Differences possibles avec chiffres officiels
6. **Stochasticite** : Aucune. Le moteur est deterministe depuis la v0.6.7 : les tirages N(0 ; 0,3 %) sur la croissance et N(0 ; 0,05 %) sur l'inflation (graine 42, les memes nombres pour tous les scenarios) ont ete retires. Avec l'output gap en niveau, le premier devenait un choc de demande persistant (+0,6 % de PIB en 2029) qui sortait a lui seul le scenario de reference du corridor de la mission (dette 2029 -2,26 pt ; sans lui -0,39). Une incertitude se publie en variante, pas en tirage cache dans la trajectoire centrale. Verrouille par `tests/test_deterministe_v067.py` (aucun acces au generateur aleatoire, sur les 44 cas).
7. **Reproductibilite de la suite de tests** : son verdict ne depend ni de la machine (locale) ni de la structure interne d'une dependance.
   > **Corrigé en v0.6.10 (contre-audit externe, V2-05)** : sous Windows sans `PYTHONUTF8=1`, des snapshots JSON etaient relus avec l'encodage de la locale (cp1252) : les colonnes accentuees (« Déficit/PIB % », « Chômage % ») devenaient illisibles et le golden master standalone echouait, moteur intact. Tout fichier texte est desormais ouvert en UTF-8 explicite, et tout interpreteur Python enfant est lance par un lanceur commun (`tests/sous_processus.py`) qui fixe sa sortie standard en UTF-8 des deux cotes du tube, verrouille par `tests/test_encodage_portable.py` (gardes statiques sur tout le depot + rejeux des lecteurs de snapshots et des tests a sous-processus sous une locale cp1252 simulee). Et `tests/test_api_safety.py` lisait la table de routage interne de FastAPI : avec fastapi 0.142.2, version permise par `requirements.txt`, il annoncait a tort l'absence de `GET /scenarios` et `POST /simulate`, et ne voyait plus un endpoint interdit ajoute au routeur ; il teste desormais le contrat publie (`/openapi.json`) et appelle chaque endpoint. Aucun chiffre du moteur ne change.

8. **Symetrie hausse/baisse verifiee sur le PIB, pas sur la dette** (preexistant, toutes familles) : les tests de symetrie comparent l'effet sur le PIB reel, et la dette d'une hausse et d'une baisse de meme ampleur n'est plus en miroir quand la prime de taux atteint son plafond de malus (0,60 point), une relance n'y coutant plus de prime quand une coupe en regagne (mesure, mode cadre 2028, ±1 point de PIB de depense courante, dette 2032 : +1,80 / -2,04 point dans un programme publie au plafond, 13,5 % d'ecart contre 2 % sur le PIB et 1 % plafond leve ; 3 % pour la reference sans programme ; 11 % pour les transferts).

9. **Subventions aux entreprises et transferts en capital aux menages** (arbitrage du mainteneur du 16/11/2026 : classement inchange, limite declaree) : aucune source consultee ne chiffre l'effet d'une subvention durable. Mesange (document de travail Insee G2017/04, note 77 p. 105) range les transferts courants, les transferts en capital et les subventions parmi les postes « sans effets directs ou indirects sur l'activite dans le modele » ; QUEST (Roeger & in 't Veld, European Economy Economic Papers 426, 2010, tableau 2) ne chiffre que des aides temporaires a l'investissement, dont l'effet vient d'un report dans le temps et ne se transpose pas a une subvention permanente. Le moteur leur donne le coefficient de la depense courante, vraisemblablement trop fort. Ordre de grandeur (mode cadre 2028, dette 2032, mesure au lot 5b) : prises au coefficient des transferts, profil inchange, les subventions baisseraient la dette de 0,02 a 0,10 point selon le programme (0,02 pour la reference sans programme, dont le droit en vigueur baisse les subventions ; au plus 0,08 en ecart a elle) ; les transferts en capital aux menages la releveraient de 0,005 point, pour un seul programme.

10. **Coupe de masse salariale du rabot uniforme** (lot 5e, non touchee) : le moteur l'assimile a des effectifs (depense courante), alors que la note source du levier ne dit pas s'il s'agit d'un gel des remunerations ou d'une baisse d'effectifs ; ses exemples d'ajustement sont des fermetures et des rencherissements de services, pas des gels de remuneration. Ordre de grandeur (mode cadre 2028, dette 2032, mesure sur la pile d'integration, lots 2 et 6 appliques) : prise comme un gel, elle releverait la dette 2032 du programme publie qui l'utilise de 1,08 point : le traitement des transferts du lot 5b l'abaisserait de 0,58 point, l'effet prix du lot 5d, qui retire le cout du gel du PIB en valeur publie, la releverait de 1,65 point (sur l'etat du lot 5e seul : 1,07, 0,51 et 1,59). Son assiette n'est pas modifiee.

11. **Indemnites journalieres dans le curseur Ondam** (arbitrage du mainteneur du 16/11/2026 : calcul inchange, limite declaree) : les indemnites journalieres maladie et accidents du travail sont des prestations en especes, donc des transferts en comptabilite nationale. Elles sont comprises dans le curseur Ondam, un montant libre sans ventilation, pris au coefficient de la depense courante. Elles font 6,75 % de l'Ondam constate en 2025 (17,9 Md€ sur 265,4 ; Commission des comptes de la securite sociale, rapport de mai 2026, tableaux 2 et 3). Prises a cette part au traitement des transferts, elles changeraient la dette 2032 d'au plus 0,003 point (mode cadre 2028, mesure au lot 5b). A reprendre si un programme encode une mesure ciblee sur les arrets de travail.

12. **Dotation aux collectivites** (lot 5c) : la part investie d'une variation (50 %) repose sur une seule etude econometrique francaise, non evaluee par des pairs, et sur un bilan descriptif ; elle ne varie pas avec l'horizon (20 % la premiere annee dans les sources, 40 a 60 % pour une baisse durable : effet de la premiere annee surestime si l'on suit le seul court terme de l'etude) ; aucune reaction des collectivites sur le solde public n'est modelisee (impot local, emprunt, fiscalite transferee) ; elle vaut aussi pour la coupe de dotation du rabot uniforme ; en mode historique, la part investie n'a pas d'effet d'offre (encadre du lot 5c).

---

## Neutralite : ce que la version v0.6.1 du moteur deplace, EN AGREGE

Chaque correction de cette version porte, dans son commit, le sens dans lequel
elle joue. **Ce paragraphe dit ce que la SOMME produit** — parce qu'une suite de
corrections individuellement justifiees peut avoir un sens agrege qu'aucune
d'elles n'annonce, et parce que le scenario de reference « Budget 2026 (vote) »
est le comparateur implicite de tous les programmes de parti.

Ecart de dette 2035 de chaque programme AU scenario de reference, en points de
PIB (un ecart plus grand = programme plus couteux que la politique votee) :

| Scenario | Ecart moteur v0.6.0 | Ecart moteur v0.6.1 | Ecart au 30/08/2026 (re-encodage scenarios) | Ecart moteur v0.6.3 | Ecart moteur v0.6.4 | Ecart au 07/10/2026 (re-encodage scenarios) | Ecart moteur v0.6.7 | Ecart moteur v0.6.10 | Ecart au 02/11/2026 (re-encodage scenarios) | Ecart moteur v0.7.0 (cadre 2027-2032, dette 2032) | Ecart au 12/11/2026 (moteur v0.8.0 et release de parametres P, dette 2032) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `rn_2027` | +3,4 | +10,9 | +10,6 | +7,0 | +7,1 | +6,7 | +2,9 | +3,0 | +3,0 | +1,4 | -0,3 |
| `lfi_2027` | +13,2 | +25,0 | +25,0 | +17,8 | +17,7 | +17,7 | +2,0 | +2,0 | +2,0 | -1,8 | +6,2 |
| `renaissance_2027` | -7,1 | -4,9 | -1,5 | -0,9 | -0,9 | -0,9 | +1,9 | +1,9 | +1,9 | +0,9 | -0,2 |
| `horizons_2027` | -10,8 | -7,0 | -1,3 | -0,8 | -0,8 | -8,8 | -4,8 | -4,8 | -4,8 | -1,7 | -2,1 |
| `lr_2027` | -13,3 | -6,3 | -4,0 | -3,3 | -3,3 | +8,0 | +6,4 | +6,4 | +0,4 | -0,0 | -3,6 |
| `ps_2027` | +0,1 | +8,4 | +8,4 | +3,8 | +3,7 | +3,7 | -5,0 | -5,1 | -5,1 | -2,3 | +1,5 |
| `ecologistes_2027` | — | — | -2,2 | -5,8 | -5,8 | -5,8 | -12,7 | -12,7 | -12,7 | -4,7 | +2,6 |
| `im_rabot_2029` | -33,6 | -26,7 | -27,0 | -26,8 | -26,8 | -26,8 | -15,4 | -15,4 | -15,4 | -3,2 | -3,7 |
| `im_competitivite_2029` | -36,4 | -24,2 | -24,7 | -25,1 | -25,0 | -25,0 | -22,2 | -22,2 | -22,2 | -7,9 | — |
| `nouvelle_energie_2027` | — | — | — | — | — | — | — | — | — | — | +5,2 |

**Mise à jour du 07/10/2026 — sixième colonne : re-encodage de trois scénarios,
aucune ligne de moteur modifiée.** Les sept autres scénarios ont des trajectoires
bit-identiques à la v0.6.4. Ce qui bouge vient des programmes eux-mêmes, encodés
sous la règle de la section « Règle d'encodage des programmes politiques » :
Horizons (-0,8 vers -8,8) intègre sa réforme des retraites du 29/09/2026 (âge légal
et durée de cotisation relevés) ; LR (-3,3 vers +8,0) passe au projet chiffré de son
site de campagne (baisse des cotisations patronales ramenée au coût annoncé par le
candidat, baisse des cotisations salariales ajoutée, effectifs portés à la cible
annoncée) et ses leviers sans source publique sont ramenés au droit en vigueur ; RN (+7,1 vers +6,7) passe au contre-budget du 06/10/2026 : les
paramètres hérités sans source (taxe sur les superprofits, baisse des cotisations
salariales, fiscalité du patrimoine, optimisation de la dette, assurance chômage,
efforts de santé et de fraude sociale, défense) reviennent au droit voté, les
mesures chiffrées du contre-budget entrent, et la part de son plan sans levier
dans le simulateur (« priorité nationale », contribution européenne, économies non
ventilées) n'est pas encodée. Chaque scénario porte ce que sa source chiffre, ni
plus ni moins.

**Mise à jour v0.6.7 (07/10/2026) — septième colonne : corrections d'équations issues
d'un audit externe, aucun paramètre de scénario modifié.** Six écarts au scénario de
référence sur neuf se resserrent, dans les deux sens : les programmes qui creusaient la dette
par rapport au budget voté la creusent moins (LFI +17,7 vers +2,0, LR +8,0 vers +6,4,
RN +6,7 vers +2,9), ceux qui la réduisaient la réduisent moins (IM Rabot -26,8 vers
-15,4, IM Compétitivité -25,0 vers -22,2, Horizons -8,8 vers -4,8) ; deux
programmes changent de côté (PS +3,7 vers -5,0, Renaissance -0,9 vers +1,9) et
l'écart des Écologistes s'accentue (-5,8 vers -12,7). Le moteur principal est le
canal keynésien : impulsions comptées levier par levier et multiplicateurs recalés sur
la valeur centrale de la littérature (§ « Multiplicateurs et Mecanismes Macro ») — une
relance y regagne en croissance une part de son coût, une consolidation y perd une
part de son rendement. Ce canal étant le plus incertain du modèle, chaque fiche
publie la fourchette ×0,75 / ×1,25 (même §, « Incertitude et poids du canal
keynésien »).

**Mise à jour v0.6.10 (21/10/2026) — huitième colonne : six réserves d'un contre-audit
externe fermées, aucun paramètre de scénario modifié.** Deux corrections d'équation
déplacent les sorties, de quelques centièmes de point : la part d'investissement lue par
l'éviction est ramenée dans [0 ; 1] (§ « Multiplicateurs et Mecanismes Macro »,
encadré V2-01) et la désindexation des pensions et prestations passe au ratio exact
(§ « Retraites », encadré V2-03). Le scénario de référence est identique au bit, donc les écarts bougent
comme les dettes 2035 elles-mêmes : RN +2,9 vers +3,0 (+0,05 pt de dette) et PS -5,0
vers -5,1 (-0,02) ; LFI (-0,03), Renaissance (+0,03) et IM Compétitivité (+0,01) restent
au même dixième ; les trajectoires de dette, déficit, croissance et chômage de Horizons,
LR et IM Rabot sont identiques au bit. Aucun classement ne change. Les quatre autres
réserves (colonnes de potentiel publiées, noms de paramètres, reproductibilité,
documentation) ne déplacent ni la dette ni le déficit : seules les colonnes de potentiel
bougent (±0,20 pt une année, sept programmes, encadré V2-02).

**Mise à jour du 02/11/2026 — neuvième colonne : re-encodage de deux scénarios sur leurs
sources primaires, aucune ligne de moteur modifiée.** Les huit autres scénarios ont des
trajectoires identiques au bit à la v0.6.10. LR (+6,4 vers +0,4) passe au livret « Rétablir
l'ordre dans les comptes publics » du 12/10/2026 : les lignes du livret qui ont un levier dans
le simulateur entrent aux montants du livret (effectifs portés à la cible du livret, durée
d'indemnisation du chômage, aide médicale d'État, fraude fiscale et sociale, fonctionnement
des collectivités, subventions aux énergies, niches fiscales des entreprises, impôts de
production), les autres restent non
encodées et sont listées dans sa fiche ; ses baisses de prélèvements sont inchangées. Horizons
(−4,8, inchangé au dixième : −4,82 vers −4,85) encode le nombre de postes publics non remplacés
annoncé par le candidat et la revalorisation des enseignants à son coût brut, et retire
l'hypothèse d'intensité de la réforme des agences qui puisait dans le même vivier de départs ;
les trois mouvements se compensent presque sur la dette 2035, pas sur le déficit 2030 (−5,44
vers −5,39 %). Les deux domaines de paramètres élargis à ces valeurs servies (effectifs
−400 000, salaires enseignants +20 %) ne changent aucune autre sortie. Chaque scénario porte ce
que sa source chiffre, ni plus ni moins (section « Règle d'encodage des programmes politiques »).

**Mise à jour du 07/11/2026 — dixième colonne : la mesure change d'objet, aucune équation ni
aucun paramètre de scénario modifié.** Depuis la v0.7.0, l'application note chaque programme sur
la **dette 2032**, fin du mandat 2027-2032, et non plus sur la dette 2035 ; chaque programme y
est appliqué de 2028 à 2032 par-dessus le droit en vigueur (budget 2026 voté, reconduit en 2027),
après un atterrissage 2026 injecté à l'identique pour tous les scénarios (section « Cadre
temporel 2027-2032 (v0.7.0) »). La dixième colonne mesure donc l'écart de dette 2032 au scénario
de référence, dans ce cadre. Les écarts y sont mécaniquement plus petits que dans les colonnes
précédentes : cinq budgets de programme (2028 à 2032) au lieu de dix années (2026 à 2035), et une
dette lue trois ans plus tôt, avant que les écarts de déficit ne se cumulent. Deux écarts changent de signe : LFI (+2,0
vers −1,8) et LR (+0,4 vers −0,04, nul au dixième). Ce resserrement
n'est PAS un changement d'équation : les équations macro (croissance, Phillips, Okun, recettes,
dépenses, dette) et le plafond de 10 % du PIB sont ceux de la v0.6.11, seul le calendrier
d'application change. Les neuf colonnes précédentes restent publiées telles quelles : elles
mesurent un autre objet (dette 2035, programme appliqué dès 2026) et ne se comparent pas
terme à terme avec la dixième.

**Mise à jour du 12/11/2026 — onzième colonne : moteur v0.8.0 (release E) et release de paramètres
P (v0.8.1).** Même objet que la dixième colonne (dette 2032, mode cadre). Elle cumule la release
d'équations E (CHANGELOG du moteur, v0.8.0 : de 0 à +1,5 point de dette 2032 selon les programmes) et
la release de paramètres P : tous les programmes ré-encodés le même jour sur leurs sources, une source
par paramètre ; une référence qui ne reconduit plus la surtaxe d'IS votée pour 2026 (déficit 2032 de
−7,17 à −7,34 %, dette 2032 de 138,04 à 138,52 %) ; un scénario de think tank retiré (« — »), un
programme ajouté. Cinq des huit scénarios déjà publiés changent de signe : les mouvements viennent de
leurs encodages, pas d'une équation commune ; le paramétrage de chacun est dans
`docs/SCENARIOS_POLITIQUES.md`. Valeurs du moteur v0.8.1 sur les scénarios de la release P, après la
relecture du 12/11/2026 qui a mis à jour sept paramètres de deux programmes, puis de la
contre-relecture qui a mis à jour sept paramètres de quatre programmes (les écarts concernés bougent
de zéro à quatre dixièmes), puis de la dernière passe du même jour : les objectifs de dépense écrits
en part du PIB ou du RNB comptés pour tous par une seule convention (§ « Bornes hautes relevées
(v0.8.1) » ; sept paramètres de quatre programmes, calendrier « valeurs ») et deux montants sans
calendrier écrit passés en rampe (un programme) ; l'écart de dette 2032 à la référence de ces quatre
programmes bouge de −0,03 à 1,74 point. Pour ce même programme, un salaire sans calendrier écrit
s'applique ensuite dès 2028, règle commune des taux et salaires (dette 2032 −0,14 point). Les scénarios dont l'encodage est inchangé sont identiques au
bit ; le précalcul servi par le site doit les reproduire (garde `tests/test_revue_adverse_v061.py`).

**Mise a jour du 31/08/2026 — sens agrege de la v0.6.4 (calage chomage,
cinquieme colonne).** Le recalage de la base du canal taux (40 -> 36,6 Md EUR,
assiette proportionnelle a l'allocation) reduit l'amplitude budgetaire de ce
canal d'environ 8,5 % : les programmes qui BAISSENT le taux de remplacement
economisent un peu moins (RN +7,0 -> +7,1), ceux qui l'AUGMENTENT coutent un
peu moins (LFI +17,8 -> +17,7 ; PS +3,8 -> +3,7). Le recalage distributif
(`gini_duree`, k = 1,6 — cf. M35) ne touche pas la dette ; ce qu'il touche,
et dans quel sens : il ameliore le Gini des programmes qui ALLONGENT la duree
d'indemnisation (LFI 0,272 -> 0,271 ; PS 0,278 -> 0,277 ; RN 0,287 -> 0,286)
et degrade celui de ceux qui la RACCOURCISSENT (Horizons 0,290 -> 0,291) —
directionnel par construction, mais desormais adosse a des donnees observees
la ou l'ancien coefficient ne citait aucune source. Effet budgetaire
symetrique (meme assiette pour tous), de l'ordre du dixieme de point :
aucune note globale ni aucun classement ne bouge.

**Mise a jour du 30/08/2026 au soir — sens agrege de la v0.6.3 (quatrieme
colonne).** Cette passe corrige deux bugs verifies et trois attributions, et
son sens agrege est le MIROIR de la v0.6.1 : elle REND aux programmes ce que
des mecanismes non sources leur retiraient. (1) La duree d'indemnisation
chomage etait comptee DEUX FOIS (~2,89 Md EUR par mois d'ecart, contre
0,75 sources Unedic) : les programmes qui l'allongent voient leur penalite
fondre — LFI -7,2 points d'ecart, PS -4,6, RN -3,6, Les Ecologistes -3,6 —
et les scenarios qui la reduisent (Renaissance a 15 mois, Horizons a
12 mois, desormais encodes au parametre annonce et non plus en « duree
equivalente ») economisent moins qu'avant : leurs ecarts favorables se
resserrent encore (-1,5 vers -0,9 ; -1,3 vers -0,8). (2) L'effort
anti-fraude au-dela du gisement IGAS ne coute plus a fonds perdus
(monotonie retablie : ~+1,5 Md EUR/an rendus a RN et LR). (3) En sens
inverse, le cout PERENNE du non-recours resorbe par l'ASU (2,4 Md EUR/an,
DGALN) retire des economies a ses deux porteurs (LR, im_competitivite).
(4) Le scenario im_rabot perd un artefact d'encodage (24 mois de duree
herites de la reference d'avant la reforme d'avril 2025 — le « je ne change
rien » d'alors etait devenu « +6 mois » quand le droit a bouge). Aucun de
ces mouvements n'est un choix de calibration : chacun est la consequence
d'une source ou d'une regle appliquee symetriquement, et les corrections
jouent dans les deux sens (la gauche recupere sur la duree, la droite sur
la fraude ; la droite paie le recours ASU, le centre perd ses durees
equivalentes).

**Mise a jour du 30/08/2026 — la troisieme colonne ne mesure PAS un changement de
moteur** (aucune ligne de calcul n'a change) : elle mesure le re-encodage des
scenarios Renaissance, Horizons et LR sur leurs programmes publies cet ete, plus
l'ajout du scenario Les Ecologistes (programme adopte le 13/07/2026). Le sens
agrege de ce re-encodage : les ecarts favorables des scenarios du bloc central et
de LR au scenario de reference se resserrent nettement (Renaissance -4,9 vers -1,5,
Horizons -7,0 vers -1,3, LR -6,3 vers -4,0) — non par un choix de calibration,
mais parce que la regle « aucun candidat ne recoit d'economies non sourcees »
est desormais appliquee uniformement : les leviers herites sans source (efforts
de fraude, optimisation de dette, coupes de recherche non annoncees, et une
baisse de CSG furtive de 0,1 point presente dans six scenarios sans qu'aucun
programme ne la porte — corrigee aussi chez RN et dans les deux scenarios de
l'Institut Montaigne) sont revenus au droit en vigueur, et les depenses annoncees
par les candidats (plan d'investissement Renaissance, baisse de cotisations
« droit au brut ») sont entrees dans les scenarios au meme titre que leurs
economies.

**Le constat, sans enrobage — sur le passage v0.6.0 → v0.6.1 : les huit
programmes alors publies se degradaient tous PAR RAPPORT au scenario de
reference — gauche comme droite, de +2,4 points pour Renaissance a +12,4 pour
la variante competitivite de l'Institut Montaigne.** (La troisieme colonne,
elle, mesure le re-encodage des scenarios du 30/08/2026, pas le moteur — voir
la mise a jour sous le tableau.) La cause est identifiable : cette version cable des canaux
macroeconomiques (emploi seniors, Okun sur le potentiel, plafond de rendement de
la prevention, cout reel de l'allocation sociale unique) que les programmes de
parti actionnent beaucoup plus que la politique votee, laquelle ne bouge presque
aucun de ces leviers.

**Precision de lecture, ajoutee avec le recalage de la courbe de Phillips
(lot 8)** : ce tableau publie des ECARTS RELATIFS, pas des niveaux. En NIVEAU, le
lot 8 ameliore la dette 2035 des NEUF scenarios sans exception (-5,6 a -10,6
points), parce qu'un deflateur realise plus proche du corridor officiel donne un
PIB nominal plus grand a tout le monde — c'est une correction de denominateur, en
aucun cas une amelioration des finances publiques. Le scenario de reference passe
ainsi de 170,1 (v0.6.0) a 158,85 points sur l'etat livre (recale 30/08/2026, v0.6.3). Sur les ecarts relatifs, le lot 8 joue
entre -0,7 et +4,3 point : il retire un peu de leur avantage aux deux scenarios
les plus austeres (im_rabot, im_competitivite), dont la desinflation etait en
partie soutenue par un garde-fou monetaire qui se declenchait jusqu'a dix annees
sur dix, et allege tres legerement la penalite du RN et de LFI. C'est le sens
attendu et annonce d'un aplatissement de pente : il retire aux programmes
d'expansion une part de leur penalite inflationniste ET aux programmes de
consolidation leur prime desinflationniste implicite.

**La moitie compensatrice est LIVREE (lot 9) : le sourcing du scenario de
reference lui-meme.** Elle etait annoncee ici comme manquante ; elle ne l'est
plus. Le scenario « Budget 2026 (vote) » encodait +25,5 Md EUR/an d'effort en
2030 dont environ 90 % venaient de trois leviers qu'aucune loi de finances n'a
chiffres (reforme des agences et operateurs, fraude fiscale et sociale,
efficience sante). Ils sont retires, et — c'est l'autre moitie, sans laquelle on
remplacerait un biais par un autre — les recettes reellement votees et absentes
sont encodees (CSG sur les revenus du capital, effort des collectivites). Effort
encode : **+2,9 Md EUR en 2026 et +25,5 en 2030 AVANT, +3,9 et +11,8 APRES**. Le
deficit 2026 reste sur la cible votee de -5,0 % (-5,28 avant, -5,25 apres) : la
correction ne se paie pas d'un decrochage par rapport a la loi, elle en rapproche.

**Le sens de cette moitie, mesure metrique par metrique — et il n'est pas
uniforme.** Le scenario de reference perd l'effort qu'il n'avait pas de titre a
porter, donc son DEFICIT se degrade chaque annee de 2027 a 2034 (jusqu'a
-0,41 point en 2030) et sa dette NOMINALE 2035 monte de 73 Md EUR. Consequence
sur les ecarts publies :

| Mesure de l'ecart au scenario de reference | Deplacement du lot 9 | En faveur de |
|---|---|---|
| Deficit 2030 | -0,41 pt pour les huit | **les programmes de parti** |
| Dette 2030 | -0,74 pt pour les huit | **les programmes de parti** |
| Deficit 2035 | -0,07 pt pour les huit | **les programmes de parti** |
| Dette 2035 (tableau ci-dessus) | **+0,57 pt pour les huit** | le scenario de reference |
| Pouvoir d'achat 2029, Gini 2030 | inchanges a la precision publiee | — |

Le deplacement est **identique pour les huit programmes** sur chaque ligne : seul
le referentiel a bouge, aucun programme n'a ete retouche, et aucun rang du
classement ne change.

**Pourquoi la derniere ligne s'inverse, et pourquoi ce n'est pas une bonne
nouvelle pour la politique votee.** Le ratio de dette 2035 du scenario de
reference passe de 159,7 a 159,2 points ALORS QUE sa dette nominale augmente :
l'effort retire cessait de peser sur l'activite, la croissance gagne environ
0,2 point par an a partir de 2031 et le PIB nominal 2035 grossit de 1,6 % contre
1,2 % pour la dette. C'est **exactement la meme classe d'effet que celle
identifiee au lot 8 — un denominateur, pas des finances publiques
assainies** — et c'est pour cela que les quatre autres mesures, elles, vont
toutes dans le sens annonce.

**Garde permanente pour que la derive ne revienne pas.** Une loi de finances est
annuelle : le scenario de reference peut porter l'effort chiffre pour son annee
et supposer, en le declarant, que les mesures structurelles persistent ; il ne
peut pas accelerer. Un test-propriete borne desormais a 0,5 point de PIB la
derive de l'effort encode entre l'annee votee et 2030 (mesure : 0,75 point avant
le lot 9, 0,26 apres). Le perimetre couvert — les mesures votees que le
simulateur ne sait pas representer, dans les deux sens, dont les 5,7 Md EUR de
prelevement sur recettes au profit de l'UE qui jouent CONTRE le scenario de
reference — est publie dans `SCENARIOS_POLITIQUES.md`.

C'est dit ici plutot que decouvert par un lecteur : un simulateur citoyen ne se
protege pas en evitant les corrections sensibles, il se protege en disant dans
quel sens joue chacune — **et ce que leur somme produit**.

---

## Choix de design assumes (vs modeles academiques)

Cette section documente les choix methodologiques deliberes qui pourraient etre vus comme des limitations par rapport aux modeles academiques (MESANGE, e-mod, OFCE iAGS, IPP TAXIPP). Ces choix sont assumes pour preserver la lisibilite et l'accessibilite citoyenne du simulateur.

### L1. Pas d'intervalles de confiance (estimations ponctuelles)

Le simulateur produit des trajectoires deterministes (sans aucun tirage depuis la v0.6.7 ; jusque-la, un bruit sigma=0,3% a graine fixe sur la croissance), pas de bandes Monte-Carlo. **Justification** : pour un public citoyen, des fan charts a la Banque d'Angleterre introduisent plus de confusion que d'information. Pour des intervalles rigoureux, complement avec MESANGE (DG Tresor) ou e-mod (OFCE) recommande. Cette limitation est partagee par OFCE iAGS et le simulateur Tresor en sortie grand public.

### L2. Profil INVEST calé sur le FMI (lot 6 ; jusque-là, pic Y2)

Depuis le lot 6 (release de paramètres, arbitrage du mainteneur), les cinq premiers termes du profil sont calés sur le tableau 3.4, colonne (1), du FMI (WEO oct. 2014, ch. 3) : `(0.3718, 0.3152, 0.3487, 0.3495, 0.2201, 0.06)` ; § « Calendrier de l'impulsion ». Historique : le profil était `(0.45, 0.65, 0.45, 0.25, 0.12, 0.06)` avec pic Y2, un choix présenté jusqu'au lot 6 comme justifié par une lecture de Bom et Ligthart (2014) et de Ramey (2019) sur le rythme des projets ; aucune de ces lectures ne fixait de valeur, et elles ne justifient pas le profil actuel, calé sur la seule estimation du FMI.

### L3. Loi d'Okun avec beta = -0.35 (mediane fourchette OFCE)

Le coefficient d'Okun France est fixe a -0.35. **Justification** : la fourchette OFCE/INSEE est large [-0.30, -0.55] selon la periode et la specification. Choisir le median -0.35 evite (a) le pessimisme de -0.55 (qui ferait exploser le chomage en recession), (b) l'optimisme de -0.30 (qui sous-estimerait la sensibilite emploi). Choix de prudence pedagogique.

### L4. Elasticite fiscale unitaire uniforme (pas de regime conjoncturel)

L'elasticite des prelevements obligatoires au PIB nominal est `ELASTICITE_PO_PIB = 1.0`, uniforme sur tout le cycle (refonte v4.0). **Justification** : HCFP note 2023-01 (series 2002-2022) — elasticite observee 1,01-1,07, non significativement differente de 1 ; convention CBO/OBR/DG Tresor a politique inchangee. L'ancienne elasticite differenciee par regime de croissance (1,00/1,06/1,08/1,12) et l'erosion fiscale forfaitaire (0,2%/an, qui rendait l'elasticite de facto ~0,93) ont ete supprimees : l'asymetrie conjoncturelle joue taxe par taxe (IS, plus-values), pas en global, et aucune institution ne modelise une erosion globale des recettes. Une erosion reelle se modelise PAR TAXE, comme mesure explicite. Consequence : en statu quo, le ratio recettes/PIB est stable par construction (~52,2%) — c'est la definition d'un scenario a politique inchangee.

### L5. Plus de plafond de taille sur l'impulsion keynésienne (v0.6.7)

Jusqu'en v0.6.6, le niveau d'effort multiplié était plafonné à 2 % du PIB (appliqué en fait au programme entier, pas « par mesure » comme l'écrivait cette page). **Retiré en v0.6.7.** Raisons : (1) la littérature citée ne porte pas de saturation — Guajardo, Leigh et Pescatori (2014) estiment des effets LINÉAIRES dans la taille de l'ajustement (la médiane de 1 % du PIB décrit l'échantillon, pas une borne de l'effet), Auerbach et Gorodnichenko (2012) documentent une non-linéarité d'ÉTAT (récession/expansion, déjà portée par l'ajustement ×1,15/×0,85, à transition continue depuis le lot 3b), pas de taille, et Blanchard et Leigh (2013) trouvent des effets PLUS forts pour les grandes consolidations, jamais plus faibles ; (2) un plafond tronque le coût — ou le gain — des seuls programmes les plus brutaux, ce qui avantage par construction ceux qui concentrent leur effort ; (3) la stabilité ne dépend pas de lui : l'effet est une convolution finie (6 ans) des impulsions annuelles, bornée par k_max × 1,15 × 1,3 × Σ |impulsions des 6 dernières années|, sous le clip de croissance [−3,5 % ; +2,5 %]. Seul scénario publié touché : `im_rabot_2029`, dont la coupe atteint 5,2 % du PIB (3,1 % la première année), désormais multipliée en entier. Le plafond cumulatif de 10 % du PIB sur les MESURES (budget, FMI 2010) est inchangé.

### L6. Modele a agent representatif (pas de microsimulation par decile)

Les coefficients Gini et competitivite sont calcules au niveau macro avec des coefficients calibres sur parts de budget INSEE (Budget des Familles 2017/2022), pas via une microsimulation par decile ; le pouvoir d'achat (v0.6.8) est un agregat comptable (RDB des menages en euros, § Indice de pouvoir d'achat), sans distribution par decile. **Justification** : architecture standard de tous les modeles macro reduits (RA-DSGE, MESANGE, e-mod). Pour la distribution par decile, complement OpenFisca-France (INRIA) et TAXIPP (IPP) recommandes. Cette limitation est partagee par tous les outils macro grand public.

### L7. Pas de backtesting historique (chocs 2008/COVID/energie 2022)

Le simulateur n'inclut pas de validation par fit historique sur les chocs 2008, COVID 2020, ou energie 2022. **Justification** : c'est un simulateur structurel calibre **ex-ante** (chocs de politique publique), pas un modele de prevision conjoncturelle. La calibration est documentee sur litterature academique (Blanchard-Leigh 2013, Auerbach-Gorodnichenko 2012, Bom-Ligthart 2014, Bozio-Wasmer 2024, COR 2024). MESANGE et e-mod ne sont pas non plus sortis avec un backtest comme prerequis.

### L8. Effets emploi des mesures fiscales : capture via le multiplicateur, pas via signal direct

Pour les mesures qui modifient les recettes fiscales (suppression de niches, hausse d'impots), **l'effet emploi est captee par le multiplicateur fiscal du moteur** (cascade : Δrecettes → Δcroissance → Δchomage via Okun β=-0.35), **pas par un signal direct exporte dans `impacts['chomage']`**.

**Lecon de calibration (mai 2026)** : un coefficient direct `0.008 × montant_supprime` avait ete introduit pour les niches sociales TGE en se basant sur Bozio-Wasmer 2024 (138k emplois pour suppression 60 Md€). Test runtime a revele un **double-comptage** : le multiplicateur fiscal atteint deja la cible Bozio-Wasmer (-140 630 emplois mesures sans signal direct), et le signal direct amplifiait l'effet ×9 a ×95.

**Regle generale** : exporter `impacts['chomage']` direct uniquement pour les mesures qui modifient le **cout du travail** (cotisations patronales, SMIC) ou la **structure du marche du travail** (assurance chomage, ASU). Pour les mesures fiscales pures (niches, IS, IR), laisser le multiplicateur faire le travail.

### L9. Plafond de compensation de la prevention : 0,50, choix de modelisation assume

Le taux de compensation d'un euro supplementaire de prevention
plafonne a **0,50** (`PREVENTION_OFFSET_CENTRAL_CAP`), atteint apres un delai
de 4 ans et une rampe de 10 points par an. **Justification, et surtout statut** : l'effet
budgetaire net d'un euro SUPPLEMENTAIRE de prevention en France **n'est publie
par aucune institution**. L'IGAS 2024 (Bras & Monasse) dit pourquoi : le champ
« est encore peu structuré en France, et mobilise de façon insuffisante des
analyses d'efficience » (synthese, p. 2 ; corrige a la release E : la citation
qui figurait ici n'est pas dans le rapport). Ce 0,50 est donc **un choix de
modelisation**, borne par la litterature internationale (Cohen 2008 : 19 % des
interventions preventives sont cost-saving ; ACE-Prevention 2010 : ratio 2,4
pour le paquet des 23 interventions préventives **dominantes** sur 123, vie entiere, selection optimale ;
OCDE 2019 ch. 6 : 0,012 Md EUR/pays/an pour la meilleure intervention), **et
il ne sera jamais presente comme source**. C'est une **hypothese haute**, assumee
(verification du 12/11/2026) : aucune source ne la chiffre, et a l'horizon 2035 elle penche du cote
genereux pour des mesures de depense (ACE-Prevention : ≈ 0,36 sur la tranche ajoutee quand on elargit le
paquet, vie entiere ; OCDE 2019 : economies de sante inferieures aux couts). Ce que les sources etablissent,
et que le moteur respecte, c'est seulement que le taux est **inferieur a 1** et qu'il est **differe**.

Deux corollaires assumes de la meme facon :
- **la forme de la rampe** (lineaire, plafonnee) est une convention : aucune
  courbe de rendement decroissant n'est publiee. Deux elements convergents
  interdisent seulement un rendement constant et non borne — Cohen 2008 (« des
  depistages frequents sont plus efficaces mais moins efficients ») et
  l'IGAS 2024 (aucune evaluation d'efficience disponible en France) ;
- **le cout des annees de vie gagnees** (pensions, autonomie) est un mecanisme
  certain (van Baal 2008 ; arithmetique des retraites) dont le quantum n'est
  pas publie : il est signale ici et **n'est affecte d'aucun coefficient**.

---

## Choix de modelisation assumes — le registre des arbitrages

La section precedente (L1 a L9) declare ce que ce simulateur ne fait **pas**
par rapport aux modeles academiques. Celle-ci declare l'inverse : ce qu'il a
fallu **trancher** pour qu'il produise un chiffre, la ou les sources publiques
divergent, se contredisent, ou ne publient rien du tout. Un modele qui refuse
d'arbitrer ne rend aucun resultat : la neutralite ne consiste donc pas a
n'avoir aucun choix, mais a les prendre **symetriquement**, a nommer
l'alternative ecartee, et a dire dans quel sens joue chacun. Le registre
ci-dessous est l'index de ces arbitrages — le detail, les sources primaires et
les tests-proprietes vivent dans les sections thematiques auxquelles chaque
entree renvoie. Regle qui les gouverne tous : **un coefficient non source est
supprime, jamais recalibre sur une valeur inventee.**

### Macro : inflation, output gap, chomage

**M1. Pente de Phillips a 0,20 — calibration encadree, pas estimation France.**
Le choix : `PHILLIPS_PENTE_MT = 0,20` sur l'output gap. L'alternative ecartee :
0,40, la pente de moyen terme mesuree par la Banque de France (*Rue de la
Banque* n° 56, fevrier 2018, formule 4c2/(1-c1)), tous regimes confondus. La
justification : dans les scenarios francais l'output gap est **negatif sur tout
l'horizon**, donc sur le segment ou les estimations controlant les anticipations
sont les plus pertinentes — la BCE (ECB WP n° 3133, octobre 2025) y mesure
environ 0,065 converti sur l'output gap. Retenir 0,40 sur-punirait la conjoncture
basse. **Il n'existe aucune estimation publiee de la pente de Phillips sur la
France seule et sur l'output gap** : 0,20 est encadre par 0,40 et 0,065, ce
n'est pas une valeur estimee. Detail : § Inflation et Courbe de Phillips.

**M2. Courbe lineaire — pas de non-linearite en L inverse.** Le choix : la
courbe reste lineaire, donc **symetrique par construction**. L'alternative
ecartee : la non-linearite en L inverse (Benigno & Eggertsson, NBER WP 31197),
qui est pourtant sourcee. La justification : elle est **asymetrique par
construction** — plate en bas (aucune desinflation pour les programmes de
consolidation), raide en haut (surcout inflationniste pour les programmes
d'expansion). L'introduire serait une decision de neutralite, pas un reglage
technique. Le verdict le plus recent la conteste par ailleurs : avec effets
fixes pays x temps, « the non-linearity effectively disappears » (BCE, WP
n° 3133).

**M3. Deux termes d'effort budgetaire conserves — dette connue, declaree (RETIRES au lot 1,
15/11/2026 : voir le tableau de la courbe de Phillips ; le texte ci-dessous date de la v4.1).** Le
choix : les termes `-0,12 x effort` (consolidation) et `+0,08 x |effort|`
(expansion) de `calculate_inflation` sont maintenus en l'etat. L'alternative
ecartee : les retirer dans la meme passe que le recalage de la courbe. La
justification : ils cumulent **trois defauts reels** — non sources, asymetriques
entre eux, et en double comptage partiel avec le canal output gap — ce qui en
fait une instruction a eux seuls, pas un effet de bord d'une recalibration. Ils
sont **dits** plutot que corriges a l'aveugle.

**M4. Une seule variable d'inflation, calee sur le deflateur.** Le choix : la
variable unique `inflation` remplit trois roles (deflateur du PIB, IPC du
pouvoir d'achat, indice d'indexation des prestations) et elle est calee sur le
**deflateur**. L'alternative ecartee : la scinder en trois — tous les handlers
la consomment, c'est un changement d'architecture instruit separement. La
justification : l'INSEE tranche explicitement en faveur du deflateur pour
apprecier les ressources publiques, et la dette est la sortie principale du
site. **Le biais residuel de -0,15 pt/an n'est pas conservateur** : mesure par
contre-epreuve, il vaut **5,5 points de dette 2035**. Detail : § Inflation et
Courbe de Phillips.

**M5. Output gap initial a -0,7 % — loi de mouvement remplacée en v0.6.7 (B3,
cf. § Inflation : gap en niveau, rappel λ = 0,2 dans la croissance, traînée de
dette en offre ; le raisonnement ci-dessous est celui de la v0.6.1, sa prémisse
« croissance = potentielle en statu quo » était fausse).** Le
choix : `OUTPUT_GAP_INITIAL = -0,7 %` (RAA 2026, tableau n° 2 p. 20 ; avis HCFP
n° 2026-3), et le gap continue d'obeir a `gap(t) = 0,8 x gap(t-1) + 0,2 x
(croissance - potentielle)`. Deux alternatives ecartees : la variante FMI
-0,4 % (Article IV 2026, Table 1), et le remplacement de la loi de mouvement par
l'identite comptable. La justification : les deux primaires encadrent -0,7 et
-0,4, et c'est la borne basse qui est retenue ; avec l'identite comptable, en
statu quo (croissance = potentielle) le gap **ne se refermerait jamais** et
l'inflation resterait durablement deprimee. C'est le niveau de depart qui etait
faux, pas la loi.

**M6. Les conversions chomage - output gap passent par le coefficient du
moteur.** Le choix : toute conversion entre un ecart de chomage et un ecart
d'activite utilise le coefficient d'Okun du moteur (-0,35, cf. L3). La
justification : la passe de sourcing v0.6.1 **n'a pas cherche** de coefficient
d'Okun estime sur la France. Les grandeurs qui en derivent sont donc
defendables au mieux, et ne sont jamais presentees comme des valeurs estimees.

### Retraites : bareme d'age et canal emploi seniors

**M7. Bareme plat au-dela de 65 ans.** Le choix : 6,0 Md EUR par annee d'age
sur **tout** le domaine 60-67 ans. L'alternative ecartee : un rendement
decroissant au-dela de 65 ans. La justification : aucune source consultee ne
chiffre le passage 65->66 ni 66->67, alors que le curseur monte a 67 ans. Le
rendement decroissant est reel mais **doux** (0,285 -> 0,25 -> 0,20-0,25 pt sur
le solde du systeme), jamais en falaise. **Hors de la plage 63-65 ans, le
chiffrage est une extrapolation.** Detail : § Retraites.

**M8. Symetrie stricte du bareme d'age.** Le choix : une annee de report
rapporte exactement ce qu'une annee d'abaissement coute. L'alternative ecartee :
le facteur d'asymetrie **0,70 a la baisse**, publie par la Cour des comptes
(fevrier 2025, tableau n° 6 : -4,2 contre +6,0). La justification : ce facteur
est mesure sur le seul palier 64->63 et decoule d'une hypothese explicite de
modelisation sur les carrieres longues (Prisme suppose 80 % de reports a la
hausse contre 40 % d'avancements a la baisse, Cour note 135 p. 74) ; rien ne le
valide de 62 vers 60. Surtout, **aucune des deux options n'est neutre** — un
coefficient plus faible a la baisse allege le cout affiche des programmes
d'abaissement, un plus eleve les alourdit. La symetrie est le seul choix qui ne
demande pas de prendre parti. Bande de sensibilite publiee : une baisse d'une
annee d'age coute de **4,2 a 6,0 Md EUR/an**.

**M9. Aucun slot cotisations dans le handler retraites.** Le choix : le handler
n'inscrit que les moindres depenses de pension ; les cotisations retraite (Cour,
tableau n° 6 : +2,4 Md EUR/an ; DG Tresor : +1,5) et les autres recettes
publiques naissent **entierement** du canal PIB/emploi. L'alternative ecartee :
activer un slot recette a +1,5 Md EUR/an, qui aurait donne au levier le
perimetre exact du solde du systeme de retraites (7,5 Md EUR par annee d'age).
La justification : les deux options ne peuvent pas coexister sans double
comptage, et l'absence de slot le rend **structurellement impossible** plutot
que corrige par un coefficient. Grandeur de controle publiee, consommee par
aucun calcul : la part des prelevements additionnels relevant des cotisations
vaut 2,4 / (2,4 + 9,3) = **20,5 %** (fourchette de controle 20-33 %).

**M10. Interpolation log-lineaire des profils macro.** Le choix : les horizons
3, 4 et 6 a 9 ans des profils d'absorption et de resorption sont interpoles
log-lineairement. La justification : le COR ne publie que les horizons 1, 2, 5,
10, 20 ans et long terme. C'est une **convention**, pas une estimation. Le
profil d'absorption reste ecrit en clair dans `constants.py`
(`ABSORPTION_OFFRE_SENIORS`), sans etre consomme par le moteur, pour que le
profil effectivement utilise demeure auditable.

**M11. Le produit des deux montees en charge.** Le choix : le profil
d'absorption macroeconomique est **multiplie** par la montee en charge par
cohortes sur 5 ans. L'alternative ecartee : n'appliquer que l'un des deux — le
calibrage COR est explicitement sans progressivite. La justification : les deux
profils decrivent des phenomenes distincts, l'absorption du choc par l'economie
d'un cote et l'arrivee des cohortes de l'autre ; le raisonnement tient, mais
**le produit n'est mesure par personne**. Sensibilite testee : le bouclage a dix
ans vaut **17,5 Md EUR avec** la multiplication et **18,2 sans**, contre 17,7
dans la decomposition de la Cour — le choix ne change pas la conclusion.

**M12. La bosse de chomage a +0,18 pt : une derivation propre a ce
simulateur.** Le choix : +0,18 pt de taux de chomage au pic par annee d'age.
L'alternative ecartee : reprendre l'un des modeles institutionnels. La
justification : c'est le point ou ils divergent le plus, et **definitivement** —
a un an, DG Tresor 0,00, I-MIP -0,40, OFCE +0,55 (COR du 26/03/2026, Document
n° 2, tableau 4). La valeur retenue est la moyenne de **trois routes
independantes** (+0,13 / +0,19 / +0,21), toutes appuyees sur la part « chomage »
du devenir des seniors decales, **stable a 26-27 % sur deux methodologies et
deux sources de donnees independantes** (Dubois & Koubi, Insee 2016 ; Rabate &
Rochut, *JPEF* 2020). Statut : **derivation de ce simulateur, jamais un chiffre
institutionnel**. Sens : elle joue **contre** les programmes de report d'age.

**M13. Fuite sociale a 9,6 %, et non aux 20 % publies.** Le choix : la fuite
vers d'autres prestations est inscrite a 9,6 % de la moindre depense brute.
L'alternative ecartee : les 20 % publies par la Cour des comptes. La
justification : la cle DREES/DARES decompose ces 20 % en 52 % d'assurance
chomage, 36 % d'indemnites journalieres et 12 % de minima sociaux, et **la part
assurance chomage est deja produite endogenement** par la categorie de depense
« chomage » du moteur — que la bosse M12 fait precisement bouger. On ne retient
donc que 48 % x 20 %. Verification croisee : 0,53 Md EUR par le canal endogene
contre 0,62 Md EUR par la cle, ecart de 14 %.

**M14. Le choc est date une seule fois.** Le choix : les quatre canaux du levier
d'age demarrent l'annee ou l'ecart au calendrier legal s'ouvre — pas l'annee ou
la simulation commence — et un ecart qui s'ouvre progressivement porte **une
seule** montee en charge. L'alternative ecartee : convoluer une suite de chocs
annuels. La justification : une convolution exigerait de decomposer un profil
publie en reponses impulsionnelles, ce que le COR ne publie pas. Consequence
chiffree, bornee et testee : l'increment annuel maximal de niveau de PIB par
annee d'age atteint **0,177 pt** au lieu de 0,120 pour un ecart maintenu
constant.

**M15. Le canal emploi n'est cable que sur l'age d'ouverture des droits.** Le
choix : le levier « duree de cotisation » ne produit que sa ligne de depense —
ni offre de travail vers le PIB, ni bosse de chomage, ni fuite sociale. La
justification : son calibrage (4,0 Md EUR/an par annee) n'a pas ete audite par
la passe de sourcing v0.6.1. **Asymetrie assumee et mesuree** : un mouvement de
2,5 ans obtenu par la duree vaut +2,3 points de dette 2035, le meme mouvement
obtenu par l'age en vaut +10,4 — un rapport de 1 a 4,5, qui n'est pas neutre en
pratique. Corriger un levier non source pour « faire symetrique » deplacerait
des programmes sur une valeur inventee : l'asymetrie est **dite** plutot que
comblee. Detail : § Canal emploi seniors.

**M16. Quatre canaux deliberement non cables.** Le choix : pas d'effet
d'eviction sur l'emploi des jeunes, pas d'effet sur la productivite, pas de
baisse d'epargne par anticipation, pas de reprise de l'elasticite OFCE 0,30
emploi/population active. La justification : les trois premiers relevent d'un
consensus d'absence d'effet macro (Kalwij, Kapteyn & De Vos 2010 sur 22 pays
OCDE ; COR 26/03/2026, Document n° 6) ou d'une non-identifiabilite reconnue par
la DG Tresor elle-meme ; le quatrieme decrit un choc soudain et indifferencie,
quand l'ex post francais donne 0,60-0,70. C'est de la sobriete, pas un oubli —
le tableau complet est en § Canal emploi seniors.

**M17. L'effet distributif du canal emploi n'est pas ajuste.** Le choix : le
coefficient Gini du levier d'age (+0,001 par 1,25 annee d'ecart) reste inchange
malgre l'ajout du canal emploi (lot 4 : ce coefficient passe à zéro faute de source,
§ Méthode unique du Gini ; le mécanisme ci-dessous est gardé). La justification : l'heterogeneite est forte et
documentee — les carrieres a capital humain eleve se prolongent, les carrieres
discontinues basculent en chomage ou en invalidite — mais **aucune source ne la
chiffre**. Convention associee, elle aussi declaree : l'effet plein est servi
l'annee ou la mesure ouvre son ecart, puis **10 % de residu annuel**
(`RETRAITES_GINI_RESIDU_FLUX`), parce qu'une reforme d'age deplace le niveau des
inegalites une fois puis ne laisse qu'un flux de nouvelles cohortes.

### Social et sante : prevention, allocation sociale unique

**M18. Prevention : le taux de compensation plafonne a 0,50.** Entree detaillee
en **L9** ci-dessus. En resume : l'effet budgetaire net d'un euro
**supplementaire** de prevention en France n'est publie par aucune institution,
et l'IGAS 2024 dit pourquoi ; 0,50 est borne par la litterature internationale
et **ne sera jamais presente comme source**. Deux corollaires assumes de la meme
facon : la **forme de la rampe** (4 annees pleines sans retour, puis +10 points
par an) est une convention faute de courbe de rendement decroissant publiee ; le
**cout des annees de vie gagnees** est un mecanisme certain au quantum non
publie, signale et affecte d'aucun coefficient.

**M19. ASU : le curseur de plafond pilote un effort budgetaire, par
interpolation lineaire.** Le choix : le curseur 50-70 % du SMIC net est mappe
lineairement sur l'effort budgetaire perenne, entre les deux **seules** variantes
chiffrees par la DREES et l'Igas (juin 2024) — « a cout constant » (0) et
« +2 Md EUR perennes ». L'alternative ecartee : conserver une economie de
baremes (-11,5 Md EUR/an a plein regime en v0.5.1). La justification : aucune
source ne publie la correspondance entre un niveau de plafond et un montant —
l'interpolation est une **convention declaree**.

**M20. ASU : economie de gestion a 0,3 Md EUR/an, une derivation.** Le choix :
0,3 Md EUR/an (fourchette 0,2-0,5). L'alternative ecartee : les 6,0 Md EUR/an de
la v0.5.1, sourcees par une note de think tank. La justification : la gestion de
**toute** la branche famille vaut environ 3 Md EUR/an (Cour des comptes,
communication au Senat, janvier 2026) — le coefficient precedent en representait
le double ; sur le perimetre reel de l'ASU la masse mobilisable est de 0,8 a
1,0 Md EUR/an. Statut : **derivation assumee**, jamais une estimation
officielle — la mission parlementaire declare que ses moyens « n'ont pas permis
d'en estimer precisement le montant ».

**M21. ASU : le plancher de la fourchette de transition, et le recours en
charge perenne.** Le choix : le cout de transition retenu est le **plancher**
de la fourchette publiee — 2 Md EUR cumules sur quatre ans — et la hausse du
taux de recours (2,4 Md EUR/an, DGALN) est une charge **perenne** montant avec
le phasing (v0.6.3). Deux alternatives ecartees : le plafond 13,4 Md EUR (ou le
milieu) pour la transition ; et, pour le recours, tant l'ancien rattachement a
la seule montee en charge (0,6 Md EUR/an sur quatre ans puis plus rien — 
qu'aucune source ne soutient : une reforme dont l'objet est de resorber le
non-recours ne cesse pas de le payer en annee 5) que le gisement de recours
integral (~7,8 Md EUR/an, DREES ER n° 1370 et n° 1379, 2026 — qu'aucun
scenario officiel ne suppose). La justification : le chiffrage de la mission
flash se declare lui-meme « hors hausse du taux de recours » ; ajouter les
2,4 Md EUR COMPLETE la source, au seul montant qu'elle attache a la reforme.
Que cela retourne un levier « economies » en cout est le constat de la source,
pas un choix du modele.

**M22. ASU : zero economie de fraude.** Le choix : aucune economie de fraude
structurelle n'est inscrite dans l'ASU. L'alternative ecartee : les 2,0 Md EUR/an
de la v0.5.1, presentes comme 30 % des « 6,3 Md EUR d'erreurs CAF ». La
justification : ce montant est la **somme algebrique** d'indus et de rappels —
30 a 36 % sont des sommes **dues** aux allocataires, dont la detection augmente
la depense (Cour des comptes, certification des comptes du regime general,
exercice 2024). Le residuel de fraude qualifiee est par ailleurs deja porte par
le curseur « Fraude sociale ».

**M23. ASU : un Gini majorant plutot qu'une conversion inventee** (choix de la v0.6.1 ; lot 4 : remplace,
sur arbitrage du mainteneur, par le coefficient des prestations ciblées de l'INSEE, § Allocation Sociale
Unique). Le choix d'origine :
l'effet Gini de l'ASU est une **borne theorique entierement explicite** — un
transfert net integralement recu par le tout premier centile. L'alternative
ecartee : convertir en points de Gini la baisse de 1,1 pt du taux de pauvrete
publiee par la DREES et l'Igas. La justification : aucune source ne publie le
Gini de l'ASU, et la conversion serait une derivation non sourcee. La borne
**majore deliberement** le benefice redistributif des programmes genereux
plutot que de le minorer, et elle est conditionnee a l'effort : a cout constant,
la reforme compte 4,0 millions de perdants pour 3,9 millions de gagnants — un
pur transfert entre menages, d'effet agrege nul par construction.

### Redistribution : perimetre et coefficients de Gini

**M24. Une seule base : le Gini du niveau de vie.** Le choix : tous les
coefficients Gini sont calibres sur le revenu disponible par unite de
consommation (definition INSEE). L'alternative ecartee : le revenu elargi a
l'ensemble de l'economie (Gini 0,188 contre 0,297 — Insee Analyses n° 118, avril
2026). La justification : un moteur ne peut avoir qu'**une** base, et **le choix
de la base inverse les signes** — un meme prelevement indirect est regressif
rapporte au revenu disponible et progressif rapporte au revenu elargi, sans
qu'aucun chiffre ne change. Consequence operationnelle : tout coefficient
importe d'une publication qui utilise l'autre base doit etre **re-derive**,
jamais recopie. Detail : § Indicateurs Macroeconomiques.

**M25. Education : zero par construction de l'indicateur.** Le choix :
`_apply_education` emet `gini = 0,0` en clair, avec son motif de perimetre.
Deux alternatives ecartees : (a) l'ancien fallback generique qui retranchait
0,04 x (depense / PIB) — sans aucune source, **asymetrique** (une coupe emettait
exactement zero) et recurrent ; (b) un coefficient de -1,4 x 10^-4 par Md EUR
derive sur la base **elargie**. La justification : les depenses d'education sont
des transferts **en nature** et n'entrent pas dans le revenu disponible — zero
par construction de l'indicateur, pas par omission. Aucune elasticite « +1 Md EUR
d'education -> Gini » n'existe dans la litterature, et c'est methodologique : les
evaluations distributives francaises travaillent en microsimulation sur
**baremes**, et une depense d'education n'a pas de bareme. Ordre de grandeur,
meme sur l'indicateur qui lui est le plus favorable : deplacer le Gini elargi de
0,01 demanderait environ **72 Md EUR**, soit +70 % du budget de l'education
nationale.

**M26. Recherche publique : zero assume et argumente.** Le choix : `gini = 0,0`.
La justification : c'est un trou de la **litterature**, pas de la collecte —
aucune etude, francaise ou internationale, n'estime l'incidence distributive de
la depense publique de R&D sur les menages, qui s'evalue par ses **rendements**.
L'INSEE classe la diffusion de la recherche parmi les depenses de consommation
**collective**, repartie par hypothese, avec trois variantes publiees et
l'avertissement que ces hypotheses « sont determinantes ». Le commentaire du
code qui affirmait une incidence a ete retire, pas reecrit.

**M27. Renovation energetique : le profil des euros est une hypothese
declaree.** Le choix : -3,4 x 10^-4 de Gini par Md EUR. L'hypothese : **aucune
publication ne ventile les montants verses par decile** — l'ONRE publie des
economies d'energie, l'ONPE des nombres de dossiers ; on suppose donc que les
euros suivent le profil des **economies d'energie**. Elle est **conservatrice** :
les taux de prise en charge plus eleves des menages « Bleu » et « Jaune »
rendraient le profil en euros plus pro-pauvres, donc le coefficient plus fort en
valeur absolue. Statut : DEFENDABLE, jamais SOLIDE.

**M28. Taxe carbone : la condition de validite du coefficient est publiee.** Le
choix : +0,0010 de Gini pour +50 EUR/tCO2 (Douenne, *The Energy Journal* 2020 ;
Note IPP n° 34, juillet 2018). La condition : le coefficient est derive de
politiques evaluees **sans recyclage** des recettes — ce qui correspond bien au
moteur, ou les recettes abondent le budget general. **Si un scenario ajoutait une
compensation forfaitaire, le signe s'inverserait** : les deciles D1 a D5
deviendraient gagnants. La condition est publiee ici parce que le moteur ne sait
pas la detecter tout seul.

**M29. Le facteur d'echelle global n'est pas re-derive.** *Lot 4 : sans objet —
le facteur vaut 1,0, les coefficients étant physiques et bornés un par un
(méthode unique, § Indicateurs Macroeconomiques).* Le choix d'alors :
`GINI_IMPACT_SCALE = 0,22` reste en l'etat. La justification : c'est un facteur
**global unique** applique a la somme agregee, qui preserve les ecarts relatifs
entre scenarios — lui attribuer un biais oriente est une erreur d'analyse. Il
pose en revanche un vrai probleme de **tracabilite** des qu'un coefficient
source entre dans l'agregat. Sa re-derivation suppose d'avoir source **tous** les
coefficients Gini et corrige la semantique flux/niveau : chantier explicitement
differe (v0.7), et non bricole entre-temps.

**M32. Assurance chomage : le mois de duree coute son prix MARGINAL, pas le
moyen.** Le choix (v0.6.3) : un mois de duree maximale d'indemnisation vaut
0,75 Md EUR/an au taux de reference (Unedic : la reduction 24 -> 18 mois
economise « de l'ordre de 4,5 Md EUR par an », fev. 2023, confirme par
l'ex-post du 18/12/2025), multiplie par `taux/0,60`. L'alternative ecartee : le
cout moyen (36,6/18 ≈ 2,0 Md EUR/mois depuis le recalage d'assiette v0.6.4),
qui traiterait chaque mois de plafond
comme paye a tous les allocataires — or ~30 % des entrants seulement
atteignent la fin de droits, et les droits ne sont consommes qu'aux deux
tiers. L'ancienne formule cumulait les deux (double comptage, ~2,89 Md EUR par
mois) : corrige, pas recalibre. Condition de validite declaree : contracyclicite
active (chomage < 9 %).

**M33. Fraude sociale : le budget de controle sature avec le gisement.** Le
choix (v0.6.3) : au-dela du point ou le gisement recouvrable (cap IGAS
6-8 Md EUR/an, net du residuel ASU) est atteint, l'excedent de budget de
controle n'est **pas engage** — le solde net est plat, jamais decroissant.
L'alternative ecartee : une courbe a rendements decroissants lisse, qui aurait
laisse le solde net REDIMINUER au-dela d'un pic (aucune source ne publie la
forme de cette courbe, et la non-monotonie penalisait les programmes a effort
maximal de ~1,5 Md EUR/an a fonds perdus). Meme famille de correction que la
non-monotonie relevee par l'audit externe d'aout 2026.

**M34. Inertie d'inflation a 0,33 — calibration encadree, pas estimation.** Le
choix (v0.6.3) : `INFLATION_INERTIE = 0,33`, milieu de la fourchette de
travail declaree (0,20-0,50). L'alternative ecartee : le 0,50 historique — un
litteral sans source, au sommet de cette fourchette. L'encadrement : aucune
institution ne publie de coefficient de pass-through des anticipations
(verifie contre BCE, blog du 31/03/2026) ; la direction vient de la Banque de
France (Billet n° 335, dec. 2023) — transmission aux anticipations « moins
d'un tiers » de sa valeur de court terme aux horizons longs dans les pays sans
indexation salariale, objet voisin mais distinct de l'inflation retardee d'une
forme reduite, et declare comme tel. Effet mesure : la sensibilite de la
calibration a ce parametre tombe de 0,062 a 0,046 pt.

**M35. Le canal distributif de la duree : surpoids k = 1,6 par euro, cale sur
les donnees de bascule fin de droits (v0.6.4 — resout le differe v0.6.3).**
Le choix : `gini_duree = GINI_DUREE_SURPOIDS × GINI_ALLOC_PAR_MD_EUR × euros
du canal duree`, avec k = 1,6. La derivation, sur donnees OBSERVEES (aucune
microsimulation distributive d'une reforme de duree n'est publiee — verifie
OFCE, IPP, DREES, CNAF, DG Tresor) : destins a +3 mois d'une fin de droits
(Dares Focus n° 53 : 31 % emploi salarie, 18 % RSA, 11 % ASS, 71 % ni-ni)
croises avec les positions distributives par population (DREES E&R n° 1368,
ERFS×DRM 2021), estimateur par coefficients de concentration — un ratio de
parts de deciles n'est PAS un ratio d'impacts Gini (verification adverse,
constat 22). Fourchette testee [1,29 ; 1,96] — l'enveloppe de l'estimateur
corrige, celle de l'estimateur ecarte (jusqu'a 2,72) ne borne rien ; le trou
des 71 % « ni RSA ni
ASS » (groupe heterogene, inobservable) porte la largeur. Les alternatives
ecartees : k = 2,0 (moyenne d'indicateurs incluant le taux de pauvrete — un
headcount n'a pas de correspondance defendable vers une elasticite de Gini,
retrograde en robustesse) ; l'ancien 0,002/6 mois (k implicite 0,556, aucune
source : par euro, la duree pesait moitie moins que le taux alors que la
coupe tombe sur une population dont 59-76 % vit dans les deux premiers
deciles APRES la perte). La nuance qui protege du double comptage avec le
canal taux : les fins de droits ne sont PAS plus pauvres AVANT la coupe (SJR
moyen 64 EUR = celui de l'ensemble des indemnisables — Dares, tableau 1) ;
tout le surpoids vient de l'apres. Limites declarees de la calibration :
(1) le trou des 71 % « ni RSA ni ASS » — groupe heterogene et inobservable —
porte toute la largeur de la fourchette ; (2) les groupes ARE/ASS/RSA de la
DREES se RECOUVRENT (un menage peut percevoir deux prestations, encadre 2) —
les traiter comme des positions disjointes est une approximation ; (3) la
DREES decrit 2021, AVANT la reforme 2023 (deux biais en sens contraires :
colonne ARE tres inseree qui GONFLE k, fins de droits post-2023 aux
affiliations plus longues qui le DEGONFLE) ; (4) la regle est lineaire alors
qu'un choc tout-ou-rien concentre est convexe — k devrait croitre avec
l'ampleur de la coupe, non modelise et assume. Meme passe : la degressivite
cesse d'etre un free lunch Gini (constat 27, meme forme que le fix PA
v0.6.3), son facteur scalant les euros a la source.

### Scenario de reference et gouvernance

**M30. Le scenario de reference ne porte que l'effort chiffre par la loi.** Le
choix : « Budget 2026 (vote) » n'encode plus les leviers qu'aucune loi de
finances n'a chiffres. L'alternative ecartee : conserver le calage sur le
deficit de l'annee 1. La justification : le scenario etait **cale sur le deficit
2026, pas construit mesure par mesure** ; tant qu'il n'etait qu'une colonne parmi
neuf, c'etait une approximation, mais depuis qu'il est le point de depart du
simulateur et le comparateur implicite de tous les programmes, c'etait un biais
systematique en faveur de la politique votee. **Contrepartie obligatoire, livree
dans le meme lot** : les recettes reellement votees et absentes sont encodees —
sans quoi on remplacerait un biais par un autre. Effort encode : +2,9 Md EUR en
2026 et +25,5 en 2030 **avant**, +3,9 et +11,8 **apres**. Garde permanente : un
test-propriete borne a **0,5 point de PIB** la derive de l'effort encode entre
l'annee votee et 2030 (mesure : 0,75 avant, 0,26 apres). Detail : § Neutralite.

**M31. Ce que le perimetre du scenario de reference ne sait pas representer est
declare, pas force.** Le choix : les mesures votees qu'aucun levier existant ne
sait porter — environ 6,5 Md EUR de recettes, dont les 5,7 Md EUR de prelevement
sur recettes au profit de l'Union europeenne, qui jouent **contre** le scenario
de reference — sont publiees telles quelles dans `SCENARIOS_POLITIQUES.md`
plutot que rangees dans un levier approchant. Y figurent aussi les hypotheses
que les parametres encodes supposent : reconduction annuelle de la contribution
exceptionnelle sur les benefices des grandes entreprises, persistance
structurelle d'un effort sante que la LFSS ne vote que pour une annee, et
perimetre du schema d'emplois (le total gouvernemental inclut les caisses de
securite sociale ; sur le seul perimetre Etat, le solde est positif).

---

## Historique des Versions

- **Version 1.0** (31/10/2025) : Creation initiale
- **Version 2.0** (16/11/2025) : Nettoyage code, version pedagogique
- **Version 3.0** (27/03/2026) : Recalibrage complet multiplicateurs (weighted blend per-measure, DECAY_PROFILE), correction debt_drag (-0,005), correction chomage_gap_weight (0,0), ajout cicatrice austerite/crowding-out/boost potentiel/retour fiscal transition, suppression bonus sans base empirique, correction taux croissance depenses, validation baseline par agent economiste
- **Version 3.1** (29/03/2026) : DECAY_PROFILE differencie (3 profils TAXES/TRANSFERS/INVEST), croissance potentielle supply-side dynamique par canal (recherche, transition eco, education) avec delais et depreciation, correction bug abs() (coupes traitees comme investissements), correction bug decay loop (impulsions passees disparaissaient si effort courant nul)
- **Version 3.2** (18/05/2026) : Terme structurel de la courbe de Phillips releve de 1,2 % a 1,5 % (Option C, mediane sourcee INSEE sous-jacente 2025 / coeur Banque de France projete / cible BCE). Constante nommee `INFLATION_STRUCTURELLE` introduite dans `constants.py` (source unique, remplace le litteral magique `0.012`). Ajout d'une section dediee « Inflation et Courbe de Phillips » documentant l'ensemble des composantes du moteur d'inflation (terme structurel, inertie, output gap, ajustements, rappel BCE). Aucune autre modification de calibration. Golden master regenere et audite : delta cible coherent (effet denominateur PIB nominal favorable, aucun scenario ne diverge).
- **Version 4.0** (10/06/2026) : Refonte « assemblage temporel ». Depenses : recurrence unique chainee des l'annee 1 (suppression du regime special 2026 et du taux d'amorcage exogene), indexation mixte 54% inflation passee / 46% contemporaine (`INDEXATION_DEPENSES_INFLATION_PASSEE`) ; les facteurs par categorie deviennent une cle de repartition. Recettes : elasticite unitaire au PIB nominal contemporain (`ELASTICITE_PO_PIB = 1,0`, HCFP note 2023-01) ; suppression de l'elasticite differenciee par regime (1,00/1,06/1,08/1,12), de l'erosion forfaitaire 0,2%/an et des rustines de transition 2026 (plancher 1,06, erosion nulle). Boucle annuelle reordonnee : macro de l'annee (impulsion budgetaire de t-1) -> PIB au deflateur contemporain -> chomage -> flux aux prix de l'annee -> mesures (impulsion stockee pour t+1) ; pass-through TVA one-shot l'annee qui suit l'entree en vigueur. Phillips corrigee en point fixe ((1-rho) x pi* + rho x pi(t-1)) : `INFLATION_STRUCTURELLE` (1,5%) devient le point de convergence reel, rappel BCE abaisse a 2,0% (`BCE_CIBLE_INFLATION`) en garde-fou de surchauffe, plancher accommodant tire vers la tendancielle. Baseline statu quo resultante (honnete) : croissance reelle des depenses +0,8/1,4%/an chaque annee, elasticite recettes 1,00, deficit 2026 -5,05%, dette 2030 ~129,5%, dette 2035 ~150%. Tests-proprietes du statu quo ajoutes (`tests/test_baseline_properties.py`).

- **Version 4.1** (26/08/2026) : Courbe de Phillips **ancree** et deflateur recale. (1) Forme : le terme d'output gap passe DANS l'ancrage — `(1-rho) x (pi* + kappa x gap) + rho x pi(t-1)`. Correction d'algebre : l'ancienne forme laissait le gap hors ancrage, donc la pente de moyen terme effective valait `0,35/(1-0,5) = 0,70`, une grandeur ecrite nulle part et sourcee nulle part, pendant que le code affichait 0,35. Meme piege que l'intercept AR(1) corrige en v4.0, deplace d'un terme. Consequence : `rho` cesse d'etre un multiplicateur cache de la pente et redevient un parametre de vitesse (residu de niveau mesure entre rho = 0,25 et rho = 0,50 : 0,130 pt en 2035 avant, 0,000 apres). (2) Pente : `PHILLIPS_PENTE_MT = 0,20`, **choix de calibration encadre et declare comme tel** — il n'existe pas d'estimation publiee de la pente de Phillips sur la France seule et sur l'output gap ; bornes BdF *Rue de la Banque* n° 56 (~0,40) et BCE WP n° 3133 (~0,065). (3) Niveau de depart : `OUTPUT_GAP_INITIAL` de -1,5% (sans source dans le code) a **-0,7%** (RAA 2026 Tableau n° 2 p. 20, avis HCFP n° 2026-3 ; variante FMI -0,4 documentee), en constante unique — la valeur etait dupliquee en deux points du simulateur. (4) Point fixe : `INFLATION_STRUCTURELLE` 1,5% -> **1,6%**, cible sur le **deflateur du PIB** et non plus sur un melange IPC/IPCH (chaine BCE SPF T3 2026 -> RAA note 6 -> INSEE deflateurs). Resultat mesure au lot : deflateur 0,89% -> 1,40% de moyenne 2026-2030, ecart annuel au corridor officiel <= 0,17 pt (contre 0,78 pt). Sur l'etat livre apres les lots 9 et 10, la moyenne du scenario de reference vaut **1,414%** et l'ecart annuel 0,18 pt — un scenario moins austere desinfle un peu moins, et la moyenne decolle du plancher de la fourchette. **Ce que cela a revele** : la v4.0 reproduisait la dette 2030 de la mission IGF par la compensation de deux erreurs de sens oppose — un PIB nominal 3,1% trop bas (qui gonflait le ratio) contre un solde primaire 0,5 pt trop favorable (qui le degonflait). La premiere est corrigee, la seconde est desormais visible et bornee par son propre test. **Sens de la correction (neutralite)** : l'inflation realisee plus haute ameliore le ratio de dette de TOUS les scenarios (denominateur) et rencherit les depenses indexees de TOUS (numerateur) — elle ne favorise aucun camp ; l'aplatissement de la pente retire aux programmes d'expansion une part de leur penalite inflationniste ET aux programmes de consolidation leur prime desinflationniste implicite. Aucun rang du classement des scenarios ne change. Non fait volontairement : les termes `effort_budgetaire` (-0,12 / +0,08, non sourcees et asymetriques) et la courbe non lineaire en L inverse (asymetrique par construction, decision de neutralite qui merite sa propre instruction).

---

*Document participatif - Vos retours et corrections sont les bienvenus*
*Contact : contact@francebudget.fr*
