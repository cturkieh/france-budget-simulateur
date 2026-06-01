# MODELE ECONOMIQUE DU SIMULATEUR

**Version** : 3.1
**Date** : Mars 2026
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

**Nouveaute v3.0** : Le modele utilise desormais un systeme de multiplicateurs keynesiens **par mesure** (weighted blend), un profil temporel de decroissance (DECAY_PROFILE) calibre sur la litterature empirique, et plusieurs mecanismes de second ordre (cicatrice d'austerite, crowding-out differencie, boost investissement sur la croissance potentielle).

**Nouveaute v3.1** : Le DECAY_PROFILE est desormais **differencie** en 3 profils (TAXES, TRANSFERS, INVEST) melanges selon la composition des mesures. La croissance potentielle beneficie d'un nouveau mecanisme **supply-side** dynamique par canal (recherche, transition ecologique, education) avec delais, depreciation et rendements decroissants.

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
- Austerite severe (>3% PIB) -> Cicatrice structurelle (DeLong & Summers 2012)

**Influences DE la croissance :**
- Croissance -> PIB reel en hausse
- Croissance -> Chomage en baisse (loi d'Okun)
- Croissance -> Pouvoir d'achat en hausse

---

### 2. Inflation

**Formule generale :**
```
Inflation = Base + Inertie + Output Gap + Ajustements
```

**Decomposition :**
- **Base** : 1,5% (inflation tendancielle France moyen terme : mediane entre la sous-jacente INSEE 2025 a 1,2% et le coeur Banque de France projete / cible BCE 1,6-2,0%)
<!-- Terme intercept de la courbe de Phillips (constante nommee INFLATION_STRUCTURELLE = 0.015, budget_simulator/constants.py). La constante constants.py INFLATION_BASE = 0.010 (1,0%) est distincte : c'est la graine d'inertie inflation_precedente en annee 0, PAS l'intercept Phillips. Note METHODOLOGIE.md, section « Calibration Baseline Validee (v3.0) » (« Inflation cible ~2,0% BCE ») = point de CONVERGENCE forcee (rappel BCE), pas le terme de base — coherent avec inflation.py:87,90 (0.02). -->
<!-- Decision PO 2026-05-18 (sourcee) : 1,2% -> 1,5%. Option C, recoupement INSEE / Banque de France / BCE. -->


- **Inertie** : 50% de l'inflation precedente (anticipations, indexation)
- **Output gap** : 0,35 x (Production - Potentiel)
  - Output gap > 0 (surchauffe) -> Inflation en hausse
  - Output gap < 0 (sous-utilisation) -> Inflation en baisse
- **Rappel BCE** : Si inflation > 2,3%, convergence forcee vers 2,0% (blend 50/50)

**Point de convergence :**
```
Inflation long terme ~ 2,0% (cible BCE)
```

**Influences SUR l'inflation :**
- Output gap en hausse -> Inflation en hausse
- Chomage en baisse -> Inflation en hausse
- TVA en hausse -> Inflation en hausse (effet one-shot)
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

**Formule generale :**
```
Recettes (t) = Recettes (t-1) x (1 + Croissance + Inflation) + dMesures
```

**Elasticite des recettes au PIB** : ~1,0
- PIB nominal +1% -> Recettes +1%

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

---

### 2. Depenses Publiques

**Formule generale :**
```
Depenses_cat(t) = Depenses_cat(t-1) x (1 + taux_croissance_reel_cat) x (1 + Inflation)
```

**Taux de croissance reels par categorie :**

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

**Calibration baseline 2035 (sans reformes) :**
- Deficit : ~-6,0% du PIB
- Dette : ~132% du PIB

---

## Dynamique de la Dette

### 1. Dette Nominale

**Accumulation simple :**
```
Dette (t) = Dette (t-1) + Deficit (t)
```

**Exemple :**
- Dette 2025 : ~3 460 Md EUR (115,6% du PIB de 2 991 Md EUR)
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

**Exemple chiffre :**
- Deficit/PIB : 5%
- Croissance + Inflation : 3%
- Dette/PIB initial : 115%
- **d(Dette/PIB) = 5% - 3% x 1,15 = 5% - 3,45% = +1,55%**
- Ratio monte a **116,55%**

---

### 3. Condition de Stabilisation

**Pour stabiliser la dette/PIB :**
```
Deficit/PIB < (Croissance + Inflation) x Dette/PIB
```

**Application numerique :**
Avec dette 115%, croissance 1%, inflation 2% :
```
Deficit max = 3,0% x 115% = 3,45% du PIB
```

**Conclusion** : A 115% de dette, il faut un deficit inferieur a 3,5% du PIB pour stabiliser le ratio.

---

## Pouvoir d'Achat

### 1. Composante Macro

**Formule :**
```
PA macro = Croissance - Inflation
```

**Mecanisme :**
- Croissance : Production par tete en hausse
- Inflation : Prix en hausse
- Gap = Pouvoir d'achat reel

**Exemple :**
- Croissance : 1,0%
- Inflation : 2,0%
- **PA macro = -1,0%/an**

---

### 2. Composante Micro (Mesures)

**Agregation des impacts :**
```
PA micro = Somme(Impacts mesures)
```

**Sources de gains :**
- CSG progressive : +0,4%
- ASU : +1,2%
- TVA energie reduite : +1,45%
- Baisse cotisations salariales : +1,5%

**Formule totale :**
```
PA final = PA initial x Produit(1 + Croissance - Inflation + PA micro)
```

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

**NOUVEAU modele (v3.0)** : Moyenne ponderee des multiplicateurs per-measure. Chaque mesure appelle `get_multiplier` avec son propre `measure_id` et sa propre composition, puis les multiplicateurs sont ponderes par le poids budgetaire de chaque mesure.

### Valeurs du Modele

| Type de mesure | Multiplicateur | Source |
|----------------|----------------|--------|
| **Consolidation** | | |
| Hausse impots (anticipee) | **-0,50** | Blanchard & Leigh 2013 (0,3-0,5) |
| Coupes depenses (anticipee) | **-0,40** | Alesina & Ardagna 2010 (0,3-0,5 graduel) |
| **Expansion** | | |
| Investissement public | **1,20** | IMF 0,9-1,5, OFCE 1,0-1,3 |
| Transferts sociaux | **0,50** | IMF 0,3-0,6 |
| Baisses impots | **0,35** | IMF 0,1-0,5 |
| **Cas speciaux** | | |
| SMIC | **0,15** | Kramarz & Philippon 2001 (quasi-zero) |
| Fraude fiscale | **-0,40** | Enforcement, pas nouvelle taxe |

### Profil Temporel (DECAY_PROFILE Differencie v3.1)

Les effets des multiplicateurs se dissipent dans le temps selon **3 profils differencies** (v3.1), melanges selon la composition des mesures actives :

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
| Dette elevee | x0,95 | Ratio > 110% (Ricardo-Barro) |
| Confiance | /1,10 | Consolidation spending-led, annee > 1 |
| ZLB | x1,30 | Taux < 2% et output gap < -2% |

### Mecanismes Supprimes (v3.0)

Les mecanismes suivants ont ete retires car sans base empirique suffisante :

- ~~Bonus elasticite investissement (+10% sur toutes les recettes)~~ -- SUPPRIME
- ~~Bonus synergie (consolidation+investissement -> +0,4% croissance)~~ -- SUPPRIME
- ~~Bonus qualite (education+transition -> +0,2%/an)~~ -- SUPPRIME

---

## Mecanismes de Second Ordre

### 1. Cicatrice d'Austerite (Austerity Scarring)

**Source** : DeLong & Summers 2012, Fatas & Summers 2018

**Mecanisme** : L'austerite tres severe (effort >3% PIB) cause des dommages structurels permanents.

```
Si effort_budgetaire > 3% PIB :
  severite = effort - 0.03
  cicatrice = -0.10 x severite
  cap = -0.30% par an maximum
```

**Interpretation** : Les reformes graduelles (retraites, sante, fusion) ne declenchent PAS de cicatrice car elles ameliorent l'offre a long terme. Seule l'austerite brutale est penalisee.

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

### 3. Crowding-Out Differencie

**Source** : Litterature standard sur l'eviction

**Mecanisme** : L'investissement productif genere des retours (faible crowding), tandis que les transferts ne creent pas de capacite productive (fort crowding).

```
crowding_intensity = 0.002 + (1 - part_investissement) x 0.006
```

| Type de depense | Intensite crowding |
|-----------------|--------------------|
| Investissement pur | 0,002 |
| Mix equilibre | 0,005 |
| Transferts purs | 0,008 |

**Condition** : Uniquement active pour les expansions (effort < 0) avec dette > 100%.

---

### 4. Croissance Potentielle Supply-Side (v3.1)

**Sources** : Khan & Luintel 2006, Bom & Ligthart 2014, FMI 2015 (Fiscal Monitor), FMI 2020, Ramey 2019

**Mecanisme** : Les depenses d'investissement productif augmentent la croissance potentielle de maniere dynamique, avec des parametres differencies par canal. Chaque canal a son propre bonus marginal, delai d'activation et taux de depreciation.

| Canal | Bonus/Md EUR au-dessus du defaut | Delai | Depreciation/an | Source |
|-------|----------------------------------|-------|-----------------|--------|
| **Recherche publique** | +0,0025 pt | 5 ans | 15% | Khan & Luintel 2006 |
| **Transition ecologique (investissement)** | +0,002 pt | 3 ans | 5% | FMI 2015, Bom & Ligthart 2014 |
| **Transition ecologique (renovation)** | +0,001 pt | 2 ans | 3% | FMI 2020 |
| **Education** | +0,001 pt | 15 ans (symbolique) | 5% | Litterature capital humain |

**Rendements decroissants** : Le bonus est calcule via `ln(1 + x)` ou `x` est le montant additionnel en Md EUR au-dessus du niveau par defaut. Cela attenue les gains marginaux a mesure que l'investissement augmente (les premiers milliards sont plus productifs que les suivants).

**Cap total** : +0,20 pt maximum. La croissance potentielle peut passer de 1,0% a 1,2% maximum.

**Depreciation progressive** : Si les depenses sont reduites par rapport au niveau par defaut, le bonus acquis ne disparait pas instantanement. Il se deprecie graduellement au taux propre a chaque canal. La recherche publique (15%/an) se deprecie plus vite que la renovation (3%/an), refletant la peremption plus rapide du capital connaissance vs le capital physique.

**Bugs corriges (v3.1)** :
- **Bug abs()** : Les coupes budgetaires (valeurs negatives) etaient prises en valeur absolue et traitees comme des investissements. Corrige : seules les depenses positives au-dessus du defaut generent un bonus.
- **Bug decay loop** : La boucle de decroissance des impulsions passees etait imbriquee dans le gate d'effort courant. Quand l'effort courant etait nul, les impulsions des annees precedentes disparaissaient au lieu de continuer leur decroissance naturelle. Corrige : les impulsions passees decroissent independamment.

---

### 5. Retour Fiscal de la Transition Ecologique

**Source** : OECD 2021 "Getting Infrastructure Right", Cour des comptes 2023

**Mecanisme** : L'investissement dans la transition ecologique genere des retours fiscaux (emplois induits -> IR + cotisations, activite -> TVA).

| Periode | Taux de retour fiscal |
|---------|----------------------|
| Annees 1-2 | 0% (phase construction) |
| Annees 3-4 | 5% |
| Annees 5+ | 8% |

---

## Contraintes Macro-economiques

### 1. Regles Europeennes (Pacte de Stabilite)

**Objectifs officiels :**
- Deficit public < 3% du PIB
- Dette publique < 60% du PIB (ou reduction significative)

**Situation France 2025 :**
- Deficit : ~5% PIB -> **NON CONFORME**
- Dette : ~115,6% PIB -> **NON CONFORME**

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

**Hypotheses modele :**
- Taux implicite dette : ~1,9% (taux moyen pondere du stock)
- Croissance nominale : ~3,0% (1% reel + 2,0% inflation)
- **r - g ~ -1,1%** -> Favorable mais fragile

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

**Calibration v3.0** : Modelise explicitement via le crowding-out differencie (section precedente).

---

## Exemples Numeriques

### Scenario 1 : Statut Quo 2025-2035

**Parametres initiaux (2025) :**
- PIB nominal : 2 991 Md EUR
- Dette : 3 461 Md EUR (115,6% PIB)
- Deficit : ~-150 Md EUR (-5%)
- Chomage : 7,6%
- Pouvoir d'achat : 100

**Trajectoire baseline calibree (sans reformes) :**

| Variable | 2025 | 2030 | 2035 |
|----------|------|------|------|
| Croissance | 0,9% | ~0,9% | ~0,8% |
| Inflation | ~1,0% | ~2,0% | ~2,0% |
| Chomage | 7,6% | ~7,5% | ~7,5% |
| Dette/PIB | 115,6% | ~124% | ~132% |
| Deficit/PIB | -5,0% | ~-5,5% | ~-6,0% |

**Analyse :**
- La dette monte a ~132% d'ici 2035 sans reformes
- Le deficit se creuse sous l'effet des depenses (vieillissement, defense, sante)
- La croissance s'erode lentement via le debt drag

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
- Debt drag reduit (dette stabilisee)
- Croissance maintenue a ~1,0%
- **PA 2035 : ~92** (vs ~88 sans reforme)

---

### Scenario 3 : Programme NFP

**Mesures principales :**
- ISF climatique : +12 Md EUR
- Taxe superprofits : +15 Md EUR
- SMIC +14% : effets via multiplicateur quasi-nul (0,15)
- TVA energie 5,5% : -17 Md EUR
- Retraite 60 ans : -15 Md EUR

**Impacts macro :**
- Pouvoir d'achat : +3-4% (SMIC, TVA energie)
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
- Pouvoir d'achat : -2% (gel prestations)
- Gini : +0,02 (hausse inegalites)
- Competitivite : +0,5% (baisse charges)
- Risque cicatrice d'austerite si effort cumule > 3% PIB

**Trade-off** : Rigueur budgetaire vs acceptabilite sociale

---

## Conclusion

### Le Trilemme Fondamental

Avec une dette a 115,6% du PIB, la France fait face a un trilemme impossible :

1. **Maintenir le pouvoir d'achat** (croissance > inflation)
2. **Stabiliser la dette** (deficit < 3,5% PIB)
3. **Eviter les reformes structurelles**

**IL FAUT CHOISIR :**
- Accepter un PA qui baisse (-8 a -12 pts sur 10 ans)
- OU reformer (fiscal, structurel)
- OU laisser filer la dette (insoutenable a ~132% en 2035)

### Points Cles du Modele v3.1

1. **Debt drag** : -0,005 pt par % au-dessus de 90% (compromis Reinhart-Rogoff / Herndon)
2. **Multiplicateurs per-measure** : Weighted blend par mesure, pas de multiplicateur global
3. **DECAY_PROFILE differencie** : 3 profils — TAXES (somme 2,00), TRANSFERS (somme 1,77), INVEST (somme 1,98, pic decale Y2). Melange pondere par composition des mesures
4. **Cicatrice austerite** : -0,10 x severite pour effort >3% PIB, cap -0,3%/an
5. **Crowding-out differencie** : 0,002 (investissement) a 0,008 (transferts)
6. **Supply-side dynamique** : Croissance potentielle augmentee par canal (recherche +0,0025pt/Md EUR, transition +0,002pt, renovation +0,001pt, education +0,001pt), delais et depreciation differencies, rendements decroissants ln(1+x), cap +0,20pt
7. **Retour fiscal transition** : 0%/5%/8% (phase-in OECD 2021)
8. **Contraintes europeennes** : Deficit < 3%, dette < 60%

### Validation

Le simulateur a ete calibre avec l'assistance d'un agent economiste expert. Les trajectoires baseline sont coherentes :
- Dette 2035 baseline : ~132% PIB
- Deficit 2035 baseline : ~-6,0% PIB
- Croissance potentielle : 1,0% (extensible a 1,2% avec investissement soutenu)
- Chomage NAIRU : ~7,5%
- Inflation cible : ~2,0% (BCE)

---

*Document participatif - Vos retours et corrections sont les bienvenus*
*Contact : contact@francebudget.fr*
