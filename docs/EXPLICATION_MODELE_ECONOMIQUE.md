# MODELE ECONOMIQUE DU SIMULATEUR

**Version** : 4.0
**Date** : Juin 2026
**Auteur** : Budget Lab France

---

## Table des Matieres

1. [Vue d'Ensemble](#vue-densemble)
2. [Variables Macroeconomiques](#variables-macroeconomiques)
3. [Finances Publiques](#finances-publiques)
4. [Dynamique de la Dette](#dynamique-de-la-dette)
5. [Pouvoir d'Achat](#pouvoir-dachat)
6. [Boucles de Retroaction](#boucles-de-retroaction)
7. [Multiplicateurs Keynesiens](#multiplicateurs-keynesiens)
8. [Mecanismes de Second Ordre](#mecanismes-de-second-ordre)
9. [Contraintes Macro-economiques](#contraintes-macro-economiques)
10. [Exemples Numeriques](#exemples-numeriques)

---

## Vue d'Ensemble

Le simulateur modelise les interactions entre 4 blocs principaux :

```
[1. VARIABLES MACRO]  ->  [2. FINANCES PUBLIQUES]
         |                          |
[3. POUVOIR D'ACHAT]  <-  [4. DETTE & DEFICIT]
```

Ces blocs sont interconnectes par des boucles de retroaction qui capturent les effets de second ordre des politiques economiques.

**Nouveaute v3.0** : Le modele utilise desormais un systeme de multiplicateurs keynesiens **par mesure** (weighted blend), un profil temporel de decroissance (DECAY_PROFILE) calibre sur la litterature empirique, et plusieurs mecanismes de second ordre (cicatrice d'austerite et crowding-out differencie — tous deux retires au lot 1, 15/11/2026 —, boost investissement sur la croissance potentielle).

**Nouveaute v3.1** : Le DECAY_PROFILE est desormais **differencie** en 3 profils (TAXES, TRANSFERS, INVEST) melanges selon la composition des mesures. La croissance potentielle beneficie d'un nouveau mecanisme **supply-side** dynamique par canal (recherche, transition ecologique, education) avec delais, depreciation et rendements decroissants.

**Nouveaute v4.0 (refonte « assemblage temporel », juin 2026)** : les flux budgetaires sont calcules par des recurrences chainees uniques appliquees des l'annee 1 (plus de regime special 2026), les recettes suivent le PIB nominal contemporain avec une elasticite unitaire, la courbe de Phillips converge reellement vers son point fixe, et la boucle annuelle est reordonnee. **Nouveaute v4.1 (aout 2026)** : la courbe de Phillips est ANCREE (le terme d'output gap passe dans l'ancrage, le parametre du code devient directement la pente de moyen terme 0,20) et son point fixe est recale sur le deflateur du PIB a 1,6%.

**Sequence annuelle de calcul (v4.0) :**
```
1. Macro de l'annee (croissance, inflation) — avec l'impulsion budgetaire de l'annee PRECEDENTE (lag standard)
2. PIB nominal de l'annee (deflateur contemporain)
3. Chomage (loi d'Okun sur la croissance de l'annee)
4. Flux budgetaires organiques AUX PRIX DE L'ANNEE (recettes, depenses)
5. Mesures de l'annee (impulsion budgetaire stockee pour l'annee suivante)
```

L'ancien ordre calculait les flux avec la croissance et l'inflation de l'annee precedente pendant que le PIB portait celles de l'annee courante : le numerateur des ratios budgetaires vivait un an derriere le denominateur (bug d'assemblage, corrige v4.0). Le lag de l'impulsion budgetaire (etape 1) casse la circularite mesures -> macro -> flux -> mesures sans recherche de point fixe.

---

## Variables Macroeconomiques

### 1. Croissance (Growth)

**Formule generale :**
```
Growth = Potentiel + Debt Drag + Multiplicateur fiscal + Effets second ordre
```

**Composantes :**

- **Potentiel** : 1,0% par an (capacite productive de l'economie, peut atteindre 1,2% avec investissement soutenu)
- **Debt drag** : Frein cause par l'endettement eleve
  - Formule : -0,005 x (Dette/PIB - 0,90)
  - Exemple : Si dette = 115% PIB -> Drag = -0,005 x 0,25 = -0,125%
  - Source : Compromis entre Reinhart-Rogoff (-0,008) et Herndon et al. 2014 (-0,003)

**Influences SUR la croissance :**
- Dette haute -> Croissance basse (via debt drag)
- Chomage haut -> Croissance basse (main d'oeuvre inactive)
- Rigueur budgetaire -> Croissance basse (multiplicateur fiscal)
- (Cicatrice d'austerite au-dela de 3 % du PIB : RETIREE au lot 1, 15/11/2026 — voir « Mecanismes de second ordre »)

**Influences DE la croissance :**
- Croissance -> PIB reel en hausse
- Croissance -> Chomage en baisse (loi d'Okun)
- Croissance -> Pouvoir d'achat en hausse

---

### 2. Inflation

**Formule generale (v4.1) — courbe ANCREE :**
```
Inflation = (1 - Inertie) x (Tendancielle + Pente x Output gap) + Inertie x Inflation precedente + Passage TVA
```
Le gap est DANS l'ancrage : pour un gap constant, le point fixe vaut exactement `Tendancielle + Pente x gap`.

**Decomposition :**
- **Tendancielle (point fixe)** : 1,6%, cible sur le **deflateur du PIB** France a moyen terme. Chaine sourcee : 2,0% IPCH zone euro (BCE, Survey of Professional Forecasters T3 2026) -> ~1,75% IPC France (RAA 2026, note 6, qui ecrit l'ecart) -> ~1,6% deflateur (INSEE, blog sur les deflateurs, sept. 2022). Depuis la v4.0, la forme `(1-rho) x pi* + rho x pi(t-1)` fait de cette valeur le point de convergence REEL du regime (dans un AR(1), le point fixe est `c/(1-rho)`, pas l'intercept `c`)
<!-- Point FIXE de la courbe de Phillips (constante nommee INFLATION_STRUCTURELLE = 0.016, budget_simulator/constants.py ; formule v4.1 dans engine/inflation.py, fonction point_fixe_phillips_ancree). La constante constants.py INFLATION_BASE = 0.010 (1,0%) est distincte : c'est la graine d'inertie inflation_precedente en annee 0, PAS le point fixe Phillips. BCE_CIBLE_INFLATION = 0.020 : seuil du garde-fou de surchauffe, PAS un point de convergence forcee. BCE_PLANCHER_ACCOMMODANT = 0.008 : seuil bas, nomme en v4.1. -->
<!-- v4.1 (26/08/2026) : 1,5% -> 1,6%. La variable inflation du moteur EST le deflateur du PIB (arbitrage documente) ; l'ancienne valeur melangeait IPC et IPCH. -->


- **Inertie** : 50% de l'inflation precedente (anticipations, indexation). Parametre de VITESSE seulement depuis la v4.1 : il ne deplace plus le niveau du regime etabli
- **Output gap** : **pente de moyen terme 0,20** x (Production - Potentiel), a l'interieur de l'ancrage
  - Output gap > 0 (surchauffe) -> Inflation en hausse
  - Output gap < 0 (sous-utilisation) -> Inflation en baisse
  - **A declarer** : 0,20 est un choix de calibration ENCADRE (BdF *Rue de la Banque* n° 56 ~0,40 ; BCE WP n° 3133 ~0,065), PAS une estimation France — il n'en existe aucune sur l'output gap
  - Niveau de depart : **gap initial de -0,7%** sur l'annee de base (RAA 2026 Tableau n° 2 p. 20 / avis HCFP n° 2026-3 ; variante FMI -0,4), puis `gap(t) = 0,8 x gap(t-1) + 0,2 x (croissance - potentiel)`
- **Effort budgetaire** : aucun effet direct sur l'inflation. Le terme `-0,12 x effort` (consolidation) / `+0,08 x |effort|` (expansion) est RETIRE au lot 1 (15/11/2026) : non source (aucun modele institutionnel, Mesange, ThreeME ni modeles du SEBC, n'en a), asymetrique, en double compte avec l'output gap, et il faisait deriver le niveau des prix sans fin. Le budget agit sur les prix par l'output gap et par le passage de la TVA. Limite declaree : une etude de la BCE (Checherita-Westphal & Pesso, WP 2996, 2024) trouve une reponse des prix aux relances amplifiee quand la dette est haute ; le moteur ne la modelise pas, ce qui sous-estime probablement l'inflation des relances
- **Garde-fou BCE haut** : Si inflation > 2,0% (cible BCE), freinage monetaire (blend 50/50 vers la cible) — garde-fou de SURCHAUFFE, inactif en statu quo
- **Garde-fou BCE bas** : Si inflation < 0,8%, politique accommodante tiree vers la TENDANCIELLE 1,6% (blend 70/30). Inactif en statu quo depuis la v4.1 — il se declenchait en annee 1 auparavant

**Une variable, trois roles (limite explicite)** : `inflation` sert a la fois de deflateur du PIB (denominateur de la dette), d'IPC (pouvoir d'achat) et d'indice d'indexation des prestations. Elle est calee sur le **deflateur**, parce que c'est lui qui commande le ratio de dette (INSEE tranche explicitement). Biais residuel declare de **-0,15 pt/an** sur les deux autres roles. **Ce biais FLATTE les chiffres publies, il n'est pas prudent** (correction du 26/08/2026) : minorer la depense indexee AMELIORE le deficit et la dette, et minorer la perte de pouvoir d'achat embellit cet indicateur — les deux effets jouent dans le sens favorable. Mesure par contre-epreuve, en indexant la depense sur l'IPC (l'indice que suit l'indexation legale des pensions) : **la dette 2035 passerait de 158,85 a environ 164,4 % du PIB, soit ~5,5 points de plus**, et le deficit 2035 de -10,68 a environ -11,9 % (contre-epreuve mesuree le 26/08/2026 sur l'etat v0.6.1 — l'ordre de grandeur, seul message de ce paragraphe, est inchange par la passe v0.6.3).

**Point de convergence :**
```
Inflation long terme ~ 1,6% (point fixe Phillips)
Inflation statu quo effective ~ 1,2-1,5% (output gap negatif)
```

**Influences SUR l'inflation :**
- Output gap en hausse -> Inflation en hausse
- Chomage en baisse -> Inflation en hausse
- TVA en hausse -> Inflation en hausse (effet one-shot, l'annee qui SUIT l'entree en vigueur : la macro de l'annee est calculee avant les mesures de l'annee)
- Effort budgetaire en hausse -> Inflation en baisse

**Influences DE l'inflation :**
- Inflation -> Pouvoir d'achat en baisse
- Inflation -> PIB nominal en hausse
- Inflation -> Taux d'interet en hausse (implicitement)

---

### 3. Chomage

**Loi d'Okun :**
```
dChomage = -0,35 x (Croissance - Croissance potentielle)
```

**Interpretation :**
- Si croissance > potentiel -> Chomage baisse
- Coefficient -0,35 : 1% de croissance supplementaire = -0,35 pt de chomage
- NAIRU : 7,5% (taux de chomage structurel)

**Influences SUR le chomage :**
- Croissance en hausse -> Chomage en baisse
- SMIC en hausse -> Chomage en hausse (elasticite -0,1 par 10% de hausse)
- Cotisations patronales en baisse -> Chomage en baisse (elasticite +0,08 par point)

**Influences DU chomage :**
- Chomage -> Inflation (via output gap)
- Chomage -> Depenses sociales en hausse (allocations)
- Chomage -> Recettes fiscales en baisse (assiette reduite)

**Correction v3.0** : Le parametre `chomage_gap_weight` a ete mis a 0,0 (etait +0,40). L'ancien coefficient positif signifiait "chomage eleve = plus de croissance", ce qui est economiquement faux. Le canal chomage->croissance est deja capture par l'output_gap via Okun.

---

## Finances Publiques

### 1. Recettes Fiscales

**Formule generale (v4.0) :**
```
n(t) = (1 + Croissance) x (1 + Inflation) - 1        [croissance nominale CONTEMPORAINE, composee]
Recettes (t) = Recettes (t-1) x (1 + n(t) x 1,0) + dMesures
```

**Elasticite des recettes au PIB** : exactement 1,0 (`ELASTICITE_PO_PIB`)
- PIB nominal +1% -> Recettes +1%
- Source : HCFP note 2023-01 (series 2002-2022) — elasticite observee 1,01-1,07, non significativement differente de 1 ; convention CBO/OBR/DG Tresor a politique inchangee
- Consequence : en statu quo, le ratio recettes/PIB est STABLE par construction (~52,2%) — c'est la definition d'un scenario a politique inchangee

**Supprimes par la v4.0** : elasticite differenciee par regime de croissance (1,00/1,06/1,08/1,12), erosion fiscale forfaitaire (0,2%/an, qui rendait l'elasticite de facto ~0,93), rustines de transition 2026 (plancher 1,06, erosion nulle). Une erosion reelle se modelise PAR TAXE, en mesure explicite.

**Composantes principales (2025) :**
- TVA : ~140 Md EUR (20% de 700 Md EUR consommation)
- IR : ~85 Md EUR
- IS : ~60 Md EUR
- CSG : ~150 Md EUR
- Cotisations sociales : ~400 Md EUR
- Total : ~1 562 Md EUR (recettes APU realisees 2025, INSEE)

**Influences :**
- PIB nominal en hausse -> Recettes en hausse
- Taux fiscaux en hausse -> Recettes en hausse
- Chomage en hausse -> Recettes en baisse (assiette reduite)

**Recettes écrites en montant (v0.8.0).** Quatre curseurs permettent d'écrire une recette en milliards
d'euros quand un programme la donne ainsi : droits de succession, TVA sur les produits à taux réduit,
taxes sur les carburants et l'énergie, mesure ciblée d'impôt sur le revenu, et une recette d'une seule
année. Le simulateur prend le montant tel quel, le même chaque année, et calcule ses effets sur la
croissance comme pour tout impôt. Une hausse de TVA sur les produits à taux réduit se répercute aussi
dans les prix l'année suivante, comme une hausse du taux normal du même montant ; une hausse progressive se
répercute marche par marche, et une hausse retirée fait redescendre les prix d'autant. Le curseur des cotisations salariales va jusqu'à leur suppression
totale (138 milliards d'euros en 2025), hors CSG et CRDS, qui ont leur propre curseur ; un point y vaut 1 % de la
masse salariale brute 2025 (11,6 milliards d'euros, Insee), si bien que la suppression totale vaut 11,9 points, le
taux moyen réel de ces cotisations.

**Impôts écrits en taux (v0.8.0).** Quand un programme écrit un taux d'impôt, le simulateur ne recopie
pas le montant annoncé : il calcule la recette à partir d'une assiette sourcée, puis retire la part que
les contribuables visés feraient disparaître en réagissant (départ, optimisation, baisse des dividendes
versés, des volumes échangés ou de la facturation en France). Cette réaction est un réglage visible, avec
sa source, que chacun peut modifier ; pour l'impôt plancher sur les très grands patrimoines, 35 % par
défaut, milieu de la fourchette publiée (15 % à 55 % environ). Elle ne contient que la réaction des
contribuables : l'effet de l'impôt sur l'activité et l'emploi est calculé par ailleurs, une seule fois,
par le moteur. Quand une source ne donne qu'un montant, sans taux, ce montant est utilisé tel quel.

---

### 2. Depenses Publiques

**Formule generale (v4.0 — recurrence unique chainee) :**
```
Depenses(t) = Depenses(t-1) x (1 + g_vol) x (1 + pi_idx)
```

- `g_vol` : croissance en VOLUME — moyenne des taux reels par categorie (tableau ci-dessous), ponderee par les parts courantes. Les facteurs par categorie servent de CLE DE REPARTITION ; ils ne portent plus le niveau (porte par le chainage)
- `pi_idx` : indexation mixte des prix — 54% de la depense suit l'inflation PASSEE (pensions et prestations revalorisees sur l'inflation N-1 ; constante `INDEXATION_DEPENSES_INFLATION_PASSEE`), 46% le deflateur contemporain

La recurrence s'applique des l'annee 1 : plus de regime special 2026 (« bridging year ») ni de taux d'amorcage exogene (pratique CBO/OBR/DG Tresor : l'annee 1 se distingue par ses donnees, jamais par sa mecanique).

**Taux de croissance reels par categorie (cle de repartition) :**

| Categorie | Croissance reelle | Source |
|-----------|-------------------|--------|
| Retraites | +1,2%/an | COR 2025 (vieillissement + indexation) |
| Sante | +1,8%/an | ONDAM tendanciel |
| Dependance | +2,5%/an | Baby-boomers 85+ |
| Defense equipement | +3,0%/an | LPM 2024-2030 (lissee) |
| Transition eco | +2,5%/an | MaPrimeRenov post-montee en charge |
| Investissements | +1,0%/an | France 2030, rythme stabilise |
| Chomage | -0,3%/an | Reforme assurance chomage |
| Autres | +0,2 a +0,5%/an | Categories residuelles |

**Correction v3.0** : Defense corrigee de 5,5% a 3,0%/an, transition_eco de 4,0% a 2,5%/an.

**Total depenses base 2025** : ~1 714 Md EUR (dont 64,7 Md EUR charges d'interet) — realise INSEE 2025

---

### 3. Deficit Budgetaire

**Formule simple :**
```
Deficit = Depenses - Recettes
```

**Calibration baseline — statu quo NU, mesure sur l'etat livre (07/10/2026, v0.6.7 ; dette re-mesuree le 08/11/2026, v0.7.2) :**
- Deficit 2026 : -5,30% du PIB
- Dette 2030 : 129,23% du PIB (HCFP : >125% sans ajustement)
- Deficit 2035 : -9,06% du PIB
- Dette 2035 : 151,32% du PIB

> **Deux objets a ne pas confondre.** Ci-dessus, le **statu quo NU** : le moteur
> sans aucune mesure. Ce n'est PAS ce que le site sert : le point de depart du
> simulateur est le scenario **« Budget 2026 vote, reajuste sur l'execution 2026 »**, qui encode la loi de
> finances reajustee sur l'execution 2026 et rend -5,45 % de deficit 2026, 129,22 % de
> dette 2030 et 151,40 % en 2035 (depuis la v0.8.1, la surtaxe d'IS votee pour 2026 seulement
> n'y est plus comptee, et ce mode l'applique des 2026 ; le site part de l'atterrissage 2026, -5,5 %). Jusqu'au 26/08/2026 cette page publiait -5,05 / ~129,5 / ~150 % —
> des valeurs d'avant les lots 8 et 9, perimees de 10 a 12 points. Une garde de
> la suite moteur (`tests/test_chiffres_publies_v061.py`) recalcule desormais
> ces chiffres a chaque execution.

---

## Dynamique de la Dette

### 1. Dette Nominale

**Accumulation simple :**
```
Dette (t) = Dette (t-1) + Deficit (t)
```

**Exemple :**
- Dette 2025 : ~3 460 Md EUR (115,7% du PIB de 2 991 Md EUR)
- Deficit 2026 : ~-150 Md EUR
- **Dette 2026 : ~3 610 Md EUR**

---

### 2. Ratio Dette/PIB

**Formule cruciale :**
```
d(Dette/PIB) = Deficit/PIB - (Croissance + Inflation) x Dette/PIB
```

**Decomposition :**
- **Numerateur** : Deficit augmente la dette
- **Denominateur** : Croissance + Inflation erodent le ratio

**Exemple chiffre (regime statu quo du moteur) :**
- Deficit/PIB : 5%
- Croissance + Inflation : 2,1% (~1% reel + ~1,1% inflation effective)
- Dette/PIB initial : 115%
- **d(Dette/PIB) = 5% - 2,1% x 1,15 = 5% - 2,42% = +2,6%**
- Ratio monte a **117,6%**

---

### 3. Condition de Stabilisation

**Pour stabiliser la dette/PIB :**
```
Deficit/PIB < (Croissance + Inflation) x Dette/PIB
```

**Application numerique :**
Avec dette 115%, croissance 1%, inflation 1,6% (tendancielle du moteur) :
```
Deficit max = 2,5% x 115% = 2,9% du PIB
```

**Conclusion** : A 115% de dette, il faut un deficit inferieur a ~3% du PIB pour stabiliser le ratio (et moins encore avec l'inflation statu quo effective ~1,2-1,5%).

---

## Pouvoir d'Achat

**Définition (v0.6.8, celle de l'INSEE)** : revenu disponible brut (RDB) des ménages, déflaté
par le prix de leur consommation, par unité de consommation, base 100 en 2025
(`engine/rdb.py`). Formule exacte, sources et tableau avant/après : METHODOLOGIE,
§ Indice de pouvoir d'achat.

```
RDB(t)  = part privée × PIB nominal(t)          (salaires privés, indépendants, patrimoine)
        + part publique × volume tendanciel(t) × déflateur(t)   (rémunérations publiques nettes)
        + euros des mesures de l'année           (prestations − impôts directs + ...)
Prix(t) = déflateur(t) × (1 + TVA/accises répercutées / consommation)
PA(t)   = 100 × RDB réel(t) / RDB(2025) / UC(t)
```

**Mécanisme :**
- La croissance agit sur la part privée du revenu (salaires, revenus d'activité et du
  patrimoine) : c'est par elle que passent les impôts sur les entreprises, les embauches et
  l'investissement publics.
- Les mesures qui touchent DIRECTEMENT les ménages entrent en euros : prestations en espèces
  (pensions, allocations, minima, AAH ; la santé et l'APA sont des transferts en nature, hors
  revenu disponible), impôts directs (IR, CSG, cotisations salariales, part ménages de la taxe
  foncière), rémunérations des agents en place (point d'indice, à 0,535 € net par € de coût),
  salaires au SMIC. La TVA et les accises passent par les prix, pour leur part payée par les
  ménages (hausse répercutée en entier, baisse à moitié).
- Indice de NIVEAU : chaque année ne lit que les montants de l'année ; une mesure permanente
  pèse son niveau, chaque année, sans se composer.

**Exemple (statu quo)** : +0,64 %/an par UC en moyenne 2026-2035 (INSEE : +0,4 à +0,5 %/an
sur longue période) → indice 106,6 en 2035.

**Jusqu'en v0.6.7** : indice SYNTHÉTIQUE, `PA × (1 + croissance réelle + Σ coefficients
forfaitaires)`, coefficients atténués de moitié après l'an 1 — vingt coefficients non sourcés,
ajoutés à la croissance que les mêmes dépenses produisaient déjà.

---

## Boucles de Retroaction

### Boucle 1 : Spirale Dette-Croissance (NEGATIVE)

```
Dette/PIB en hausse
  -> Debt drag en hausse
  -> Croissance en baisse
  -> PIB nominal en baisse
  -> Recettes en baisse
  -> Deficit en hausse
  -> Dette en hausse
  -> Repetition...
```

**Effet** : La dette elevee s'auto-entretient
**Calibration** : -0,005 pt de croissance par point de dette au-dessus de 90%
**Source** : Compromis Reinhart-Rogoff / Herndon et al. 2014

---

### Boucle 2 : Stabilisateur Inflation-PA

```
Inflation en hausse
  -> Pouvoir d'achat en baisse
  -> Consommation en baisse
  -> Output gap en baisse
  -> Inflation en baisse
```

**Effet** : Auto-regulation partielle de l'inflation

---

### Boucle 3 : Courbe de Phillips (via Output Gap)

```
Chomage en baisse
  -> Output gap en hausse
  -> Inflation en hausse
  -> Pouvoir d'achat en baisse
  -> Demande en baisse
  -> Production en baisse
  -> Chomage en hausse
```

**Effet** : Arbitrage fondamental chomage/inflation
**Calibration** : 0,35 x output_gap (Phillips augmentee, coefficient unique)

---

## Multiplicateurs Keynesiens

### Definition

Le multiplicateur mesure l'impact sur le PIB d'une variation des depenses ou recettes publiques.

### Architecture : Weighted Blend par Mesure (v3.0)

**ANCIEN modele (v2.0)** : Un multiplicateur global calcule a partir de la composition agregee.

**Modele v3.0 a v0.6.6** : Moyenne ponderee des multiplicateurs per-measure. Chaque mesure appelle `get_multiplier` avec son propre `measure_id` et sa propre composition, puis les multiplicateurs sont ponderes par le poids budgetaire de chaque mesure.

**Modèle v0.6.7 (audit externe Codex 10/2026)** : la moyenne ci-dessus mêlait des multiplicateurs de signes opposés, pondérés par l'effort BRUT et appliqués à l'effort NET — un programme équilibré n'avait aucun effet keynésien et une consolidation nette pouvait compter comme une relance ; et une seule impulsion était stockée par scénario (son niveau de première année). Désormais chaque flux de chaque levier (recettes, dépenses) est multiplié séparément, sur la VARIATION annuelle de son effort en % du PIB, avec le profil de son levier : `effet(t) = Σ −k × Δe(t − âge) × profil(âge)`. Le sens (consolidation/expansion) suit le niveau du flux par rapport au statu quo. Détail et tests : METHODOLOGIE § Multiplicateurs.

### Valeurs du Modele

Coefficients d'impact `k` v0.6.7, calés pour que l'effet de NIVEAU sur le PIB réel 4 ans après une impulsion permanente de 1 % du PIB, mesuré dans le moteur complet, tombe sur la valeur centrale de la littérature (entre parenthèses ; détail et sources : METHODOLOGIE § Table des Multiplicateurs de Base).

| Type de mesure | Multiplicateur | Source |
|----------------|----------------|--------|
| **Consolidation** | | |
| Hausse impots | **-0,615** (effet 0,65) | Gechert 2015 (méta-analyse, 104 études) |
| Coupes depenses generiques | **-0,74** (effet 0,8) | Ramey 2019 (« 0.6 to 1 ») |
| Coupe d'investissement public | **-1,20** | symetrique de la hausse |
| **Expansion** | | |
| Investissement public | **1,20** (effet 1,41) | FMI WEO oct. 2014 (1,5 a 4 ans) |
| Depense courante (defense, dotations, postes, credits, sante) | **0,74** (effet 0,8), meme coefficient que la coupe (lot 5) | convention : pas d'asymetrie de signe retenue (meme instrument, meme coefficient) |
| Transferts sociaux | **0,688** (effet 0,65), meme coefficient pour une coupe | Gechert 2015 |
| Baisses impots | **0,615** (effet 0,65, comme la hausse) | aucune asymetrie de signe etablie (v0.6.7) |
| **Cas speciaux** | | |
| SMIC | **0,15** | Kramarz & Philippon 2001 (quasi-zero) |
| Fraude fiscale | **-0,40** | Enforcement, pas nouvelle taxe |

**Flux hors de la demande intérieure (v0.8.0).** Les multiplicateurs mesurent l'effet d'un euro dépensé,
ou prélevé, sur la demande des agents résidents. Un versement dont la contrepartie directe est non
résidente (contribution au budget de l'Union, aide extérieure) ne passe pas par cette demande : son
multiplicateur intérieur est nul. Le moteur n'enregistre donc aucune impulsion pour le curseur
`transferts_etranger` (`MESURES_HORS_DEMANDE_INTERIEURE`). Les deux autres effets de demande qui
lisaient l'effort budgétaire (terme d'inflation, cicatrice d'austérité) sont retirés au lot 1, et l'effort
intérieur, net de ce flux, avec eux. Le flux garde ses effets de financement : solde, dette, traînée de dette sur la croissance,
prime de taux (l'éviction d'une hausse est retirée au lot 1).

**Prestations en montant (v0.8.0).** Le curseur `prestations_menages` prend le multiplicateur des
transferts sociaux dans les deux sens, comme les règles d'indexation, l'assurance chômage et les
retraites.

**Dépense courante, même effet dans les deux sens (lot 5, 15/11/2026, non publié).** Jusqu'ici, une
dépense qui n'est ni de l'investissement ni une prestation (défense, dotations des collectivités,
postes, crédits des ministères, santé) n'avait pas le même effet selon qu'on l'augmentait ou qu'on la
réduisait : un point de PIB de moins coûtait 0,79 point de PIB au bout de 4 ans, un point de PIB de
plus n'en rapportait que 0,74, parce que la hausse prenait le coefficient des prestations. Le moteur
applique désormais à la hausse le coefficient de la baisse, comme il le fait déjà pour les impôts, les
prestations et l'investissement : 0,79 dans les deux sens. C'est une convention (même instrument, même
coefficient), pas un résultat établi : une étude américaine qui sépare les deux sens trouve qu'une baisse de
dépense publique pèse plus sur l'activité qu'une hausse ne la soutient, ce que le moteur ne représente pas ;
l'ancien écart ne le représentait pas non plus, il venait d'un oubli de classement. Tous les programmes publiés sont concernés,
parce que tous relèvent la défense ; en mode cadre, leur dette 2032 baisse de 0,09 à 0,61 point (METHODOLOGIE,
encadré « Dépense courante symétrique en signe »).

### Profil Temporel (DECAY_PROFILE Differencie v3.1)

Les effets des multiplicateurs se dissipent dans le temps selon **3 profils differencies** (v3.1) ; depuis la v0.6.7, chaque impulsion porte le profil de son levier (plus de mélange à l'échelle du programme) :

**Profil TAXES** (mesures fiscales : TVA, IS, IR, CSG, etc.) :
```
TAXES = (0.90, 0.50, 0.30, 0.15, 0.10, 0.05)  — somme = 2.00
```

| Annee | Coefficient | Interpretation |
|-------|-------------|----------------|
| 0 (impact) | 0,90 | Quasi-totalite de l'effet |
| 1 | 0,50 | Moitie de l'effet initial |
| 2 | 0,30 | Decroissance rapide |
| 3 | 0,15 | Effet residuel |
| 4 | 0,10 | Tres faible |
| 5 | 0,05 | Quasi-nul |

**Profil TRANSFERS** (transferts sociaux : retraites, SMIC, allocations) :
```
TRANSFERS = (0.90, 0.50, 0.20, 0.10, 0.05, 0.02)  — somme = 1.77
```
Effet total plus faible (somme 1,77 vs 2,00) car les transferts sont partiellement epargnes par les menages.

**Profil INVEST** (investissements productifs : education, transition ecologique, recherche) :
```
INVEST = (0.45, 0.65, 0.45, 0.25, 0.12, 0.06)  — somme = 1.98
```
Pic decale a l'annee 2 (0,65 au lieu de 0,45 en annee 0). Cela reflete les delais de construction et de montee en puissance des projets d'investissement public avant que les effets d'entrainement economique ne se concretisent.

**Melange pondere** : Le profil effectif est un blend des 3 profils, pondere par la composition budgetaire des mesures actives pour l'annee en cours.

**Sources** : IMF 2014, Blanchard & Leigh 2013, Auerbach & Gorodnichenko 2012, Ramey 2019 (profils temporels differencies).

**Cap par mesure** : L'effort est plafonne a 2% du PIB par impulsion (contraintes d'offre, rendements decroissants).

### Ajustements Contextuels

| Contexte | Coefficient | Condition |
|----------|-------------|-----------|
| Recession | x1,15 | Output gap < -2% ou chomage gap > 2% |
| Expansion | x0,85 | Output gap > 2% et chomage gap < -1% |
| Dette elevee | x0,95 | Ratio > 110% — calibration prudente du moteur, pas une valeur citee (voir ci-dessous) |
| ~~Confiance~~ | ~~/1,10~~ | Retire en v0.6.7 : absorbe par la calibration sur l'effet a 4 ans et contredit par la table par famille (METHODOLOGIE § Multiplicateurs) |
| ZLB | x1,30 | Taux < 2% et output gap < -2% |

**Coefficient « dette elevee » (x0,95 au-dela de 110 %)** : le SENS est celui de la litterature
— des multiplicateurs plus faibles quand la position budgetaire est degradee (Huidrom, Kose, Lim &
Ohnsorge, « Why do fiscal multipliers depend on fiscal positions? », *Journal of Monetary Economics*
114, 2020, p. 109-125 : canaux ricardien et de taux ; Ilzetzki, Mendoza & Vegh, « How big (small?)
are fiscal multipliers? », *Journal of Monetary Economics* 60(2), 2013, p. 239-254 : multiplicateurs
negatifs dans les pays tres endettes). Le SEUIL (110 %) et l'AMPLITUDE (-5 %) sont des choix du
moteur, qu'aucune de ces deux sources ne fournit : elles decrivent un effet plus fort (multiplicateur
de long terme nul ou negatif en position faible), d'ou le qualificatif de calibration prudente. **Mesure
(lot 1, 15/11/2026)** : dans tout le domaine publie (dix scenarios, deux modes, banc de calibrage), la dette
lue depasse 110 % a chaque appel ; le facteur s'applique donc partout et il est absorbe par la calibration
des coefficients, calee a 4 ans facteur compris. Il ne differencie aucun scenario publie : aucune reduction
des multiplicateurs liee au niveau de dette n'est modelisee dans ce domaine, ou la dette agit par la trainee
sur le potentiel et par la prime de taux. Il reste une marche a 110 %, inerte dans ce domaine (dette de
modele declaree, gardee par un test qui rougit le jour ou un scenario publie lit une dette sous le seuil).

### Mecanismes Supprimes (v3.0)

Les mecanismes suivants ont ete retires car sans base empirique suffisante :

- ~~Bonus elasticite investissement (+10% sur toutes les recettes)~~ -- SUPPRIME
- ~~Bonus synergie (consolidation+investissement -> +0,4% croissance)~~ -- SUPPRIME
- ~~Bonus qualite (education+transition -> +0,2%/an)~~ -- SUPPRIME

---

## Mecanismes de Second Ordre

### 1. Cicatrice d'Austerite (Austerity Scarring) — RETIREE (lot 1, 15/11/2026)

**Ce qu'elle faisait jusqu'a v0.8.1** : au-dela d'un effort de consolidation de 3 % du PIB, la croissance perdait chaque annee 0,10 point par point de PIB d'effort supplementaire, plafonne a 0,3 point par an. Aucun pendant pour une relance.

**Pourquoi elle est retiree** : les deux sources citees (DeLong & Summers 2012, Fatas & Summers 2018) ne contiennent ni seuil, ni plafond, ni sens unique ; elles decrivent un effet de niveau sur le potentiel, proportionnel a l'impulsion budgetaire et propre aux economies deprimees a la borne zero des taux. Le seuil de 3 % avait ete choisi pour que l'utilisateur trouve toujours une solution viable. La cicatrice doublait en outre les multiplicateurs, deja cales sur l'effet mesure a 4 ans. Une hysterese symetrique fondee sur l'ecart de production serait un autre modele, a instruire a part (METHODOLOGIE, « Mecanismes de second ordre »).

---

### 2. Effet Confiance Alesina (caps reduits)

**Source** : Alesina & Ardagna 2010, conteste par IMF 2012, Guajardo et al. 2014

**Conditions** : Effort >1,5% PIB, part depenses >50%, dette >110%

| Periode | Multiplicateur confiance | Cap |
|---------|--------------------------|-----|
| Annees 1-2 | 0,10 | +0,20% max |
| Annees 3-4 | 0,08 | +0,15% max |
| Annees 5+ | 0,02 | +0,04% max |

**Note v3.0** : Caps divises par deux par rapport a la v2.0 pour refleter le scepticisme empirique.

---

### 3. Crowding-Out Differencie — RETIRE (lot 1, 15/11/2026)

**Ce qu'il faisait jusqu'a v0.8.1** : quand le budget de l'annee precedente etait une relance nette et que la dette depassait 100 % du PIB, la croissance perdait de 0,002 (relance 100 % investissement productif) a 0,008 (sans investissement productif) point par point de PIB de relance. Aucun effet pour une consolidation. Coefficients sans source publiee.

**Pourquoi il est retire** : arbitrage du mainteneur du 21/10/2026 (« option C »), applique au lot 1. Les etudes lues (Huidrom et al. 2020, Ilzetzki et al. 2013, Nickel & Tudyka 2014) trouvent un multiplicateur plus faible quand la dette est haute, avec des modeles lineaires dans le signe du choc ; aucune etude lue ne reserve l'effet aux relances. Le moteur garde la reduction symetrique de 5 % des multiplicateurs au-dela de 110 % de dette ; mais comme la dette depasse ce seuil dans tout le domaine publie, cette reduction est absorbee par la calibration et ne differencie aucun scenario : la dette agit par la prime de taux et la trainee sur le potentiel. Couper ou augmenter les transferts d'un point de PIB a desormais le meme effet, a 0,1 % pres (4 % d'ecart avant). Detail : METHODOLOGIE, « Mecanismes de second ordre ».

---

### 4. Croissance Potentielle Supply-Side (v3.1, échelle en v0.8.0)

**Sources** : Bom & Ligthart 2014 (élasticité du PIB au capital public), INSEE comptes de patrimoine 2025
(stock), FMI 2015 (efficience), Fieldhouse & Mertens 2024 (R&D publique), DG Trésor ThreeME 2026
(rénovation), Fieldhouse & Mertens 2024 (calendrier de la recherche), OCDE 2001 et Khan & Luintel 2006
(dépréciation de la recherche), FMI 2015/2020 (délais et dépréciations des autres canaux).

**Mecanisme** : Les depenses d'investissement productif augmentent la croissance potentielle de maniere
dynamique, avec des parametres differencies par canal. **v0.8.0** : la pente est dérivée d'une élasticité
du PIB au STOCK de capital divisée par ce stock — un flux Δ soutenu accroît le stock de Δ par an, donc la
croissance potentielle de ε × Δ / K par an.

| Canal | Pente : bonus par Md€/an d'écart au défaut | Délai | Dépréciation/an | Source de la pente |
|---|---|---|---|---|
| **Recherche publique** | +0,032 pt par Md€ ajouté à la réserve de connaissances pour les petits montants, un peu moins ensuite ; hors du plafond | aucun : effet l'année qui suit la dépense (lot 2) | 15 % par an de la réserve | Fieldhouse & Mertens 2024 (0,06) ; stock de R&D des APU ≈ 187 Md€ (inventaire permanent, INSEE 2025) |
| **Transition écologique (investissement)** | +0,005 pt | 3 ans | 5 % | Bom & Ligthart 2014 (0,106) ; FMI 2015 (efficience 87 %) ; INSEE 2025 (1 855 Md€ hors terrains) |
| **Transition écologique (rénovation)** | **0** | 2 ans | 3 % | DG Trésor, Trésor-Éco n° 394 (2026), ThreeME : effet de demande seul |
| **Éducation** | +0,0025 pt | 15 ans (hors horizon) | 5 % | convention v3.1 (moitié du capital public) |
| **Investissement des collectivités** | +0,005 pt | 3 ans | 5 % | capital public, mêmes sources que l'investissement de l'État |

**Rendements decroissants** : pour la recherche, chaque milliard de plus rapporte un peu moins que le précédent
(lot 2, ci-dessous). Pour les autres canaux, la somme de leurs contributions est saturée en douceur vers le
plafond,
`bonus = 0,20 pt × tanh(Σ / 0,20 pt)` — proportionnelle aux petits montants (1 Md€ vaut un dixième de
10 Md€), mi-plafond vers 22 Md€/an de capital public, 90 % du plafond vers 60 Md€/an. Jusqu'à la v0.8.0,
la forme `coeff × log2(1 + x)` atteignait le plafond dès 1 Md€ : 1 Md€ et 50 Md€ recevaient la même
prime (corrigé, cf. METHODOLOGIE). (Cette page écrivait `ln(1 + x)` ; le code calculait `log2`.)

**Plafond** : ±0,20 pt (convention, sans source), approché sans jamais être atteint par la somme des canaux autres
que la recherche. Depuis le lot 2, la recherche en est sortie : plus la réserve de connaissances est grande, moins
un milliard de plus la fait progresser en proportion, si bien que chaque milliard rapporte un peu moins que le
précédent, sans plafond fixe ; c'est la règle que l'étude de la Réserve fédérale de Dallas propose pour un modèle.
Une baisse du budget pèse plus qu'une hausse du même montant : à long terme, 45 % de plus pour la plus forte baisse
possible (10 Md€ par an), 4 % de plus pour 1 Md€. Deux variantes (effet deux ans après la dépense ; 30 % d'une
hausse absorbés par les salaires des chercheurs) sont mesurées dans METHODOLOGIE, en sensibilité seulement.

**Recherche publique (lot 2, arbitrage du mainteneur du 15/11/2026)** : le moteur compte les connaissances que
la recherche accumule. Chaque année, 15 % de ce qui a été accumulé se périme, et l'argent dépensé en plus dans
l'année s'y ajoute. Le gain de croissance de l'année suivante dépend de ce qui a été ajouté à cette réserve : 0,032
point par milliard d'euros pour les premiers milliards, un peu moins ensuite (voir « Plafond » ci-dessus). Conséquences : l'effet commence l'année qui suit la dépense (avant : seulement après
cinq ans, donc rien pendant le mandat pour un programme qui commence en 2028) ; une dépense faite une seule année
donne un gain qui s'estompe ensuite ; une baisse du budget retire ce qu'une hausse du même montant ajoute. Source :
l'étude de la Réserve fédérale de Dallas dont vient déjà le chiffre de l'effet (Fieldhouse & Mertens). Ses
auteurs supposent que la productivité suit cette réserve sans attendre, puis jugent cette hypothèse raisonnable
au vu de leurs résultats : ce n'est pas un délai mesuré, les données sont américaines, et aucune étude française
n'a été trouvée. Détail : METHODOLOGIE, encadré « Recherche publique en forme stock ».

**Une hausse de recherche se rembourse dans le moteur avant la fin du mandat.** 5 Md€ de plus par an, à partir de
2028, font baisser la dette en 2032 de 1,35 point de PIB et de 10,3 Md€, et améliorent le solde de 8,3 Md€ : la
croissance supplémentaire rapporte plus d'impôts que la dépense ne coûte. C'est ce que dit l'étude dont vient le
chiffre de l'effet, qui trouve même un rendement plus élevé que celui du moteur. Mais l'étude est américaine, son
calendrier est une hypothèse jugée raisonnable et non une mesure, et le plus gros programme publié ajoute environ
un tiers de la réserve de connaissances en cinq ans, bien au-delà des hausses que l'étude observe. Détail et
chiffres : METHODOLOGIE.

**Investissement : une part de l'effet est comptée deux fois.** L'effet sur l'activité d'un euro investi est réglé
sur une mesure du FMI qui comprend déjà le surcroît de capacité de production ; le moteur y ajoute son propre effet
de long terme. Résultat : quatre ans après le début, un euro investi chaque année par l'État ou les collectivités
donne un peu plus d'activité que la mesure du FMI (environ 1,7 € au lieu de 1,5 €). C'est la raison pour laquelle
le plafond de ces canaux est conservé ; la correction demande un réglage d'ensemble, qui reste à faire.

**Depreciation progressive** (autres canaux) : Si les depenses sont reduites par rapport au niveau par defaut, le bonus acquis ne disparait pas instantanement. Il se deprecie graduellement au taux propre a chaque canal. La recherche publique (15%/an) se deprecie plus vite que la renovation (3%/an), refletant la peremption plus rapide du capital connaissance vs le capital physique.

**Bugs corriges (v3.1)** :
- **Bug abs()** : Les coupes budgetaires (valeurs negatives) etaient prises en valeur absolue et traitees comme des investissements. Corrige : seules les depenses positives au-dessus du defaut generent un bonus.
- **Bug decay loop** : La boucle de decroissance des impulsions passees etait imbriquee dans le gate d'effort courant. Quand l'effort courant etait nul, les impulsions des annees precedentes disparaissaient au lieu de continuer leur decroissance naturelle. Corrige : les impulsions passees decroissent independamment.

---

### 5. Retour Fiscal de la Transition Ecologique — RETIRE (lot 2, 16/11/2026)

**Ce qu'il faisait** : le levier de transition ajoutait a ses recettes 0 %, puis 5 %, puis 8 % de sa depense
d'investissement et de renovation (impots et cotisations de l'activite induite).

**Pourquoi il est retire** (arbitrage du mainteneur du 15/11/2026) : les recettes du moteur suivent deja le PIB
(elasticite 1,0), qui porte justement les impots de l'activite induite : le meme euro etait compte deux fois, et
pour ce seul levier. Les deux references citees (OCDE « Getting Infrastructure Right », Cour des comptes 2023) ne
contiennent pas ce chiffre ou sont introuvables. Desormais, un euro investi par l'Etat ou par les collectivites a
le meme effet. Le levier n'est pas autofinance : tire seul, il alourdit la dette et le deficit en euros chaque
annee ; si le ratio de dette baisse un peu pour les petits montants, c'est parce que le PIB grossit, pas parce que
la depense se rembourse. Detail : METHODOLOGIE, « Investissements verts ».

---

## Contraintes Macro-economiques

### 1. Regles Europeennes (Pacte de Stabilite)

**Objectifs officiels :**
- Deficit public < 3% du PIB
- Dette publique < 60% du PIB (ou reduction significative)

**Situation France 2025 :**
- Deficit : ~5% PIB -> **NON CONFORME**
- Dette : 115,70% PIB -> **NON CONFORME**

**Sanctions possibles :**
- Procedure pour deficit excessif (PDE)
- Astreintes financieres (0,2% PIB = ~6 Md EUR)
- Surveillance renforcee Commission europeenne

---

### 2. Soutenabilite de la Dette

**Critere r-g (taux d'interet - croissance) :**
```
Si r > g : Dette insoutenable a long terme
Si r < g : Dette stabilisable meme avec deficit primaire
```

**Hypotheses modele (v4.0) :**
- Taux implicite dette : ~2,0 % a l'amorce 2026 (taux moyen pondere du stock, recale v0.6.0 sur le taux apparent 2,2 % toutes APU de la mission IGF 07/2026), remontant vers ~3,1 % en 2030 au fil du refinancement au taux marginal de marche (~3,47 %, AFT)
- Croissance nominale : ~2,0-2,1% (~1% reel + ~1,1% inflation statu quo effective)
- **r - g ~ -0,2%** en debut de periode -> marge tres faible ; devient POSITIF en fin d'horizon quand la croissance s'erode (debt drag) : dynamique boule de neige

---

### 3. Contrainte de Credibilite

**Prime de risque :**
- Dette > 100% PIB : +0,1 a +0,3 pt de taux
- Dette > 130% PIB : +0,5 a +1,0 pt de taux (seuil critique)

**Impact sur charge d'interet :**
- Dette 3 460 Md EUR x +0,1 pt = +3,5 Md EUR/an

---

### 4. Effet d'Eviction

**Mecanisme :**
```
Endettement Etat en hausse -> Taux marche en hausse -> Investissement prive en baisse
```

**Calibration** : jusqu'a v0.8.1, modelise via le crowding-out differencie, retire au lot 1 (15/11/2026). Le canal des taux passe par la prime d'effort sur le taux de la dette ; la dette agit aussi par la trainee sur le potentiel. La reduction de 5 % des multiplicateurs au-dela de 110 % du PIB est absorbee par la calibration dans le domaine publie (dette toujours au-dessus du seuil) : elle n'y differencie aucun scenario.

---

## Exemples Numeriques

### Scenario 1 : Statut Quo 2025-2035

**Parametres initiaux (2025) :**
- PIB nominal : 2 991 Md EUR
- Dette : 3 461 Md EUR (115,7% PIB)
- Deficit : ~-150 Md EUR (-5%)
- Chomage : 7,6%
- Pouvoir d'achat : 100

**Trajectoire baseline — statu quo NU, mesuree sur l'etat livre (26/08/2026) :**

| Variable | 2025 | 2030 | 2035 |
|----------|------|------|------|
| Croissance | 0,80% | 1,11% | 0,97% |
| Inflation | 1,10% | 1,53% | 1,58% |
| Chomage | 7,60% | 7,44% | 7,41% |
| Dette/PIB | 115,70% | 129,23% | 151,32% |
| Deficit/PIB | -5,08% | -6,45% | -9,06% |

Les lignes Inflation de ce tableau affichaient ~1,1% en 2030 comme en 2035
jusqu'au 26/08/2026 — c'est-a-dire precisement la variable que le recalage de
la courbe de Phillips existe pour corriger, laissee a sa valeur d'avant. Tableau
re-mesure en entier le 07/10/2026 (v0.6.7) : ses lignes croissance, inflation,
chomage et deficit 2030 etaient encore celles d'etats anterieurs. Dette et deficit
re-mesures le 08/11/2026 (v0.7.2 : dette de depart recalee a 115,7 %).

**Analyse :**
- La dette monte a 151,32% d'ici 2035 sans aucune mesure (129,23% des 2030 — HCFP : >125% sans ajustement)
- Le deficit se creuse sous l'effet des depenses (vieillissement, defense, sante) et de la boule de neige des interets
- La croissance s'erode lentement via le debt drag
- L'inflation effective reste sous le point fixe 1,6% (output gap negatif)
- Avant la v4.0, la meme baseline affichait ~132% de dette en 2035 : l'ecart venait d'un « assainissement implicite gratuit » (~24 Md EUR/an) cree par l'ancienne mecanique d'assemblage, pas d'hypotheses economiques

---

### Scenario 2 : Reforme Structurelle

**Mesures appliquees :**
- Reforme fonction publique : -10 Md EUR/an
- Efficience sante : -15 Md EUR/an
- Lutte fraude : +20 Md EUR/an
- Taxe superprofits : +10 Md EUR/an (temporaire)

**Impact budgetaire :**
- Deficit reduit de ~55 Md EUR des 2028
- Deficit/PIB passe de 5% a ~3,5%

**Impact sur trajectoire :**
- Debt drag reduit (trajectoire de dette tres en-dessous du statu quo NU, 151,32% en 2035)
- Croissance maintenue a ~1,0%
- PA legerement inferieur au statu quo a court terme (effort budgetaire), ecart resorbe ensuite

---

### Scenario 3 : Programme NFP

**Mesures principales :**
- ISF climatique : +12 Md EUR
- Taxe superprofits : +15 Md EUR
- SMIC +14% : effets via multiplicateur quasi-nul (0,15)
- TVA energie 5,5% : -17 Md EUR
- Retraite 60 ans : -44 Md EUR/an a plein regime (16 Md EUR x 2,75 annees, montee en charge 5 ans)

**Impacts macro :**
- Pouvoir d'achat : hausse (SMIC, TVA energie, transferts) — chiffres a jour : METHODOLOGIE
- Gini : -0,04 (forte reduction inegalites)
- Competitivite : -1% (ISF, charges)
- SMIC : multiplicateur 0,15 (quasi-zero, Kramarz & Philippon)

**Trade-off** : Gains sociaux immediats vs soutenabilite long terme

---

### Scenario 4 : Programme LR

**Mesures principales :**
- ASU plafonnee : +12 Md EUR (economies)
- FP -100k postes : +6 Md EUR
- Fusion agences : +8 Md EUR
- Gel prestations : +4 Md EUR

**Impacts macro :**
- Pouvoir d'achat : baisse (gel prestations) — chiffres a jour : METHODOLOGIE
- Gini : +0,02 (hausse inegalites)
- Competitivite : +0,5% (baisse charges)

**Trade-off** : Rigueur budgetaire vs acceptabilite sociale

---

## Conclusion

### Le Trilemme Fondamental

Avec une dette a 115,7% du PIB, la France fait face a un trilemme impossible :

1. **Maintenir le pouvoir d'achat** (croissance > inflation)
2. **Stabiliser la dette** (deficit < ~3% PIB au regime nominal v4.0)
3. **Eviter les reformes structurelles**

**IL FAUT CHOISIR :**
- Accepter un PA qui stagne (~+0,3 pt/an en statu quo : croissance faible, gains quasi nuls en fin d'horizon)
- OU reformer (fiscal, structurel)
- OU laisser filer la dette (insoutenable : 129,23% des 2030, 151,32% en 2035 sans aucune mesure)

### Points Cles du Modele v4.0

1. **Debt drag** : -0,005 pt par % au-dessus de 90% (compromis Reinhart-Rogoff / Herndon)
2. **Multiplicateurs per-measure** : Weighted blend par mesure, pas de multiplicateur global
3. **DECAY_PROFILE differencie** : 3 profils — TAXES (somme 2,00), TRANSFERS (somme 1,77), INVEST (somme 1,98, pic decale Y2). Melange pondere par composition des mesures
4. **Cicatrice austerite** : RETIREE au lot 1 (15/11/2026) — sans source pour son seuil de 3 % ni pour son sens unique
5. **Crowding-out differencie** : RETIRE au lot 1 (15/11/2026, option C du 21/10/2026) — sans source et a sens unique ; la dette agit par la prime de taux et la trainee sur le potentiel (la reduction de 5 % des multiplicateurs au-dela de 110 % est absorbee par la calibration dans le domaine publie)
6. **Supply-side dynamique** : Croissance potentielle augmentee par canal (v0.8.0 : recherche +0,032 pt/Md€, transition +0,005 pt, renovation 0, education +0,0025 pt — elasticites sourcees divisees par les stocks), delais et depreciation differencies, saturation douce vers le plafond ±0,20 pt ; lot 2 : recherche en forme stock logarithmique, effet l'annee qui suit la depense, hors du plafond
7. **Retour fiscal transition** : RETIRE au lot 2 (16/11/2026) — double compte avec l'elasticite des recettes au PIB, references sans ce chiffre
8. **Contraintes europeennes** : Deficit < 3%, dette < 60%
9. **Assemblage temporel (v4.0)** : recurrences chainees uniques des l'annee 1 (depenses : g_vol + indexation mixte 54/46 ; recettes : elasticite 1,0 au PIB nominal contemporain), boucle annuelle macro -> PIB -> chomage -> flux -> mesures, Phillips en point fixe avec garde-fou BCE a 2,0%
10. **Phillips ancree (v4.1)** : `(1-rho) x (pi* + 0,20 x gap) + rho x pi(t-1)`, point fixe 1,6% cale sur le deflateur du PIB, gap initial de -0,7% (RAA 2026 / HCFP)

### Validation

Le simulateur a ete calibre avec l'assistance d'un agent economiste expert. Les trajectoires baseline sont coherentes :
- Croissance reelle des depenses primaires : +0,8 a +1,4%/an CHAQUE annee (tendanciel officiel +1,0-1,2%)
- Elasticite recettes / PIB nominal : 1,00 (ratio recettes/PIB stable ~52,2%)
- Deficit 2026 : -5,30% PIB en statu quo NU ; **-5,45% pour le scenario de reference** « Budget 2026 vote, reajuste sur l'execution 2026 », qui est ce que le site sert (loi votee : -5,0%)
- Dette 2030 : 129,23% PIB en statu quo NU ; 129,23% pour le scenario de reference (HCFP : >125% sans ajustement)
- Dette 2035 : 151,32% PIB en statu quo NU ; 151,29% pour le scenario de reference. Deficit 2035 : -9,06% / -9,03%
- Croissance potentielle : 1,1% de potentiel TOTAL (sentier de la mission IGF 07/2026), soit un tendanciel de 1,2285 % net de la traînee de la dette heritee (v0.6.7) ; extensible avec investissement soutenu
- Chomage NAIRU : ~7,5%
- Inflation : point fixe 1,6% (`INFLATION_STRUCTURELLE`, deflateur du PIB), pente de moyen terme 0,20 (`PHILLIPS_PENTE_MT`), gap initial de -0,7% (`OUTPUT_GAP_INITIAL`), effective statu quo ~1,2-1,5% ; cible BCE 2,0% = garde-fou de surchauffe

Ces proprietes du statu quo sont verifiees en continu par `tests/test_baseline_properties.py` (croissance reelle des depenses chaque annee, absence de marche du ratio primaire, elasticite apparente 1,00 +/- 0,02, jump-off INSEE, non-regression des deltas mesure-vs-baseline).

---

*Document participatif - Vos retours et corrections sont les bienvenus*
*Contact : contact@francebudget.fr*
