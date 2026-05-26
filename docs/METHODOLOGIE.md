# METHODOLOGIE - Simulateur Budget France 2025-2035

**Version** : 3.2
**Date** : Mai 2026
**Auteur** : Budget Lab France

---

## Table des Matieres

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
11. [Multiplicateurs et Mecanismes Macro](#multiplicateurs-et-mecanismes-macro)
12. [Sources et References](#sources-et-references)

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
- **Croissance potentielle supply-side** : Nouveau mecanisme dynamique. Les depenses d'investissement productif (recherche, transition ecologique, education) augmentent la croissance potentielle avec delais et rendements decroissants (cap +0,20 pt)
- **Bug fix abs()** : Les coupes budgetaires etaient incorrectement traitees comme des investissements (signe non pris en compte)
- **Bug fix decay loop** : La boucle de decroissance etait piegeee a l'interieur du gate d'effort — les impulsions passees disparaissaient quand l'effort courant etait nul

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

---

## Retraites

### Parametres Cles

| Parametre | Valeur Reference 2025 | Impact |
|-----------|----------------------|--------|
| Age legal | 62,75 ans (62 ans 9 mois) | +/-8 Md EUR par annee |
| Duree cotisation | 42,5 ans (170 trimestres) | +/-2 Md EUR par semestre |
| Indexation | 100% inflation | +/-1,5 Md EUR par 10% de variation |

### Hypotheses Economiques

**Age de depart :**
- Economies/Surcouts = (Ecart age) x 8 Md EUR/an
- Effet sur emploi seniors : elasticite +0,3 par annee supplementaire
- Trajectoire progressive sur 10-15 ans

**Indexation des pensions :**
- Base : 17 millions de retraites x pension moyenne
- Indexation 100% = maintien pouvoir d'achat
- Gel partiel (80%) = economies ~3 Md EUR/an

**Duree de cotisation :**
- Trimestres requis = duree x 4
- Decote pour carrieres incompletes
- Impact differencie selon categories socioprofessionnelles

### Impacts Macroeconomiques

- **Inegalites** : Hausse age 62,75->64 ans = -0,002 Gini (legerement progressif)
- **Pouvoir d'achat** : Gel total indexation retraites = -0,007 PA agrégé/an récurrent (OFCE Brief 124, 15/02/2024)
- **Competitivite** : Impact neutre (pas de lien direct entreprises)

---

## Sante

### Vue d'Ensemble - 3 Leviers (30 Md EUR potentiel)

La fonction sante utilise une approche structuree en 3 leviers UX distincts :

| Levier | Potentiel | Composantes |
|--------|-----------|-------------|
| **Hopital** | 13 Md EUR | Convergence tarifs + GHT + Achats groupes + Ambulatoire |
| **Ambulatoire** | 10 Md EUR | Gatekeeping + CPTS/telemedecine + Pertinence soins |
| **Prevention/Org** | 7 Md EUR | Generiques + Controles IJ + Regulation urgences + ROI prevention |
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

**Prevention ROI (1,7 Md EUR)**
- ROI 25%/an apres 2 ans
- Depistages, vaccins, maladies chroniques

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
- Pouvoir d'achat : 0 (pas de changement reste a charge)
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
| Effectifs | Ajustement ponctuel | 60 k EUR/agent/an |
| Point d'indice | Hausse salaires | 2 Md EUR/point |
| Fusion agences | Economies structurelles | Variable |

### Montee en Puissance

- 2027 : 30% efficacite
- 2028 : 60% efficacite
- 2029 : 85% efficacite
- 2030+ : 100% efficacite (plein effet)

**Base de calcul** : 157k departs/an x 40k EUR = 6,3 Md EUR/an economisables max

### SMIC et Fonction Publique (Correction v3.0)

**Double-comptage corrige** : Quand le SMIC augmente, l'impact sur la fonction publique est calcule en delta :
```
delta_fp = max(0, hausse_smic - hausse_point_indice)
```
Cela evite de compter deux fois la meme hausse si le point d'indice est deja revalorise au-dessus du SMIC.

### Impacts Macroeconomiques

- **Gini effectifs** : -10k effectifs = +0,001 Gini
- **Gini indice** : +1% point indice = -0,0005 Gini
- **Pouvoir d'achat** : +1% point indice = +0,0005 PA

---

## Chomage et Protection Sociale

### Allocations Chomage

**Parametres (post-reforme avril 2025) :**
- Taux de remplacement : 45% a 80% (base 60%)
- Duree allocations : 12 a 36 mois (base 18 mois — reforme avril 2025 : 24 → 18 mois pour les <55 ans)
- Base budgetaire : 40 Md EUR (post-reforme ; etait 45 Md EUR avant la reforme)

**Formule economique :**
- Montant = 40 × (taux / 0,60) × (duree / 18)
- Source code : `_apply_chomage_alloc` (`budget_simulator/handlers/depenses.py`), constantes `MONTANT_REF=40`, `DUREE_REF=18`
- Elasticite duree chomage : +0,1 par 5 points de taux

**Impacts :**
- Gini : Allongement durée 18 → 24 mois ≈ +5 Md EUR = -0,004 (REDUCTION inegalites — protection chomeurs)
- PA : Hausse = +0,002 (impact direct, sens inverse pour une baisse)

> **Note historique** : Avant la reforme avril 2025, la base etait `MONTANT_REF=45 Md EUR` × `DUREE_REF=24 mois`. La reforme a aligne la duree de reference (18 mois <55 ans, 22,5 mois 55-56 ans, 27 mois ≥57 ans) ; le simulateur prend la duree des <55 ans comme reference (majoritaire) pour la conversion taux ↔ montant.

### Allocation Sociale Unique (ASU)

**Principe** : Fusion RSA + Prime d'activite + APL

**Objectifs :**
1. Simplification administrative (7,5 Md EUR economies)
2. Incitation au travail (gain net +500 EUR au SMIC)
3. Lutte contre non-recours (34% -> 10%)
4. Protection ciblee (majorations vulnerables)

**Economies nettes :**
- Investissement 2026 : -1,4 Md EUR
- Economies recurrentes 2027+ : +11,5 Md EUR/an
- Protection vulnerables : -2,0 Md EUR/an

**Plafond** : range slider 50%-70% du SMIC net (defaut moteur **65%** ≈ 910 EUR personne seule, max range 70% ≈ 1 000 EUR — position NFP). Constante : `'asu_plafonnement': 0.65` dans `budget_simulator/config.py`.

**Mecanismes de protection :**
- Parent isole + 2 enfants : Minimum 1 250 EUR
- Handicape (AAH) : Minimum 1 200 EUR
- Complement de transition sur 3 ans

**Impacts :**
- Pouvoir d'achat : +0,3% (incitation travail)
- Gini : -0,005 (reduction pauvrete)
- Chomage : -0,1 point (incitation emploi)

---

## Fiscalite

### Impot sur les Societes (IS)

**Parametres :**
- Taux actuel : 25%
- Range : 15% a 35%
- Assiette : ~25% PIB avec elasticite

**Elasticite comportementale :**
- Taux > 25% : elasticite -0,5 (optimisation fiscale)
- Taux <= 25% : elasticite -0,3

**Impacts :**
- Gini : IS 25%->30% = -0,003 (redistribution)
- Competitivite : IS 25%->30% = -0,005 (delocalisation)

### TVA

**Parametres :**
- Taux actuel : 20%
- Range : 5,5% a 25%
- Assiette : 53% PIB (consommation)

**Effets :**
- Elasticite base : -0,2 si taux > 20%
- Penalite evasion si taux > 22%

**Impacts :**
- Gini : TVA +2% = +0,005 (REGRESSIF, ONE-TIME)
- PA : TVA +1pt = -0,002 PA (ONE-TIME, ajustement de niveau ; INSEE 2018 "Hausse TVA et inégalités")

### Impot sur le Revenu (IR)

**Parametres :**
- Tranche superieure : 45% actuel (range 40%-60%)
- Foyers concernes : 400k (revenus > 160k EUR)
- Revenu moyen tranche : 220k EUR

**Impacts :**
- Gini : Taux 45%->50% = -0,008 (PROGRESSIF, redistribution forte)
- PA : Hausse taux sup = -0,001

### CSG/CRDS

**Base large** : tous revenus (travail, capital, remplacement)
- Taux actuel : 9,7%
- Range : 8% a 12%

**Option progressive** : Bareme par tranches au lieu de taux flat
- Recettes neutres ou positives selon calibrage

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
- Gini : +1 point = +0,003 (moins redistributif)

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

**Redistribution possible** : Cheque energie pour menages modestes

### Investissements Verts

**Multiplicateur keynesien** : 1,2 (recalibre v3.0, etait 1,5)
- Effet levier important
- Impact sur emplois verts : 15 000/Md EUR

**Retour fiscal differencie (v3.0)** :
- Annees 1-2 : 0% (construction)
- Annees 3-4 : 5% (emplois induits, TVA)
- Annees 5+ : 8%
- Source : OECD 2021, Cour des comptes 2023

**Mesures d'investissement productif (pour multiplicateur)** : education, transition_eco, recherche (PAS defense)

**Impacts :**
- Gini : +5 Md EUR renovation = -0,001 (redistributif)
- PA : +5 Md EUR = +0,001 (economies energie)
- Competitivite : +10 Md EUR = +0,002 (competitivite verte LT)

### Aides Renovation Energetique

- MaPrimeRenov', eco-PTZ
- Effet levier : 1 EUR public = 3 EUR prive
- Reduction facture energetique menages

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

**Montee en puissance** (intensite 100%) :
- 2026 : 20% -> 14 Md EUR esperes -> 9,5 Md EUR nets
- 2027 : 35% -> 24,5 Md EUR -> 16,7 Md EUR nets
- 2028 : 50% -> 35 Md EUR -> 23,8 Md EUR nets
- 2029 : 70% -> 49 Md EUR -> 33,3 Md EUR nets
- 2030+ : 100% -> 70 Md EUR -> 47,6 Md EUR nets

**Impacts macro** : Gini=0, PA=0, Competitivite=0 (recuperation argent du)

### Fraude Sociale

**Potentiel** : 13 Md EUR (RSA, APL, arrets maladie abusifs)
- Source : HCFPS sept. 2024, Cour des comptes RAFSS mai 2025

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
  automatises integres a l'ASU et le potentiel de fraude sociale
  HCFPS. **Distinct** du « 30% des 6,3 Md€ erreurs CAF » de la
  composante `ECO_FRAUDE_STRUCT` de l'ASU (cf section ASU) : ce sont
  deux usages differents du chiffre 30%.
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

**Debat politique :**
- NFP : 1 600 EUR net (+14,4% vs 1 398 EUR actuel)
- RN : Position symbolique
- Centre : Maintien indexation automatique

**Parametres economiques :**
- Salaries concernes : 3,2 millions (DARES 2024)
- Masse salariale FP : 15% agents cat. C = ~50 Md EUR
- Cotisations sociales : +20% de la hausse brute

**Multiplicateur specifique (v3.0)** : 0,15
- Quasi-zero : la hausse du cout du travail (destruction emplois non qualifies, Kramarz & Philippon 2001) compense le boost de consommation
- Bien en dessous des transferts standards (0,50)

**Correction double-comptage (v3.0)** :
```
delta_fp = max(0, hausse_smic - hausse_point_indice)
```

**Impacts (annee 1 seulement - effet NIVEAU) :**
- PA : +100 EUR SMIC = +0,5% PA
- Competitivite : +100 EUR = -0,3%
- Gini : +100 EUR = -0,002 (progressif)

### ISF Climatique

**Debat politique :**
- NFP : ISF retabli, seuil 1,3M EUR, bareme progressif, bonus ecologique
- RN : Opposition totale
- Centre : Maintien IFI immobilier (2 Md EUR)

**Potentiel** : 0-18 Md EUR selon bareme

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
- Gini : -0,020 pour 12 Md EUR (reduction forte inegalites)
- PA : -0,001 (quasi-neutre, touche 1% population)
- Competitivite : -0,002 (risque exil entrepreneurs)

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
- Gini : -0,01 pour 15 Md EUR (redistribution capital->Etat)
- PA : Neutre (taxe entreprises)
- Competitivite : -0,005 pour 15 Md EUR tous secteurs

### TVA Energie Differenciee

**Debat politique :**
- NFP/RN : TVA 5,5% -> -17 Md EUR recettes, +1,5% PA
- Centre : Maintien 20% + bouclier tarifaire

**Modele economique :**
- Consommation energie : 120 Md EUR/an
- Recettes actuelles 20% : 24 Md EUR
- Si TVA 5,5% : 6,6 Md EUR -> perte 17,4 Md EUR

**Impacts (effet NIVEAU annee 1) :**
- PA : Baisse 20%->5,5% = +1,45%
- Gini : Baisse TVA = -0,0073 (progressif car 15% budget classes pop. vs 7% aisees)
- Competitivite : 0 (entreprises ont TVA deductible)

---

## Multiplicateurs et Mecanismes Macro

### Architecture des Multiplicateurs (v3.0)

**Weighted Blend per-measure** : Chaque mesure budgetaire a son propre multiplicateur, calcule en fonction de sa composition (recettes/depenses/investissement). Le multiplicateur global de l'annee est la moyenne ponderee des multiplicateurs individuels, ponderee par le poids budgetaire de chaque mesure.

### Table des Multiplicateurs de Base

| Type | Valeur | Source | Ancien (v2.0) |
|------|--------|--------|---------------|
| Consolidation fiscale (anticipee) | **-0,50** | Blanchard & Leigh 2013 | -0,92 |
| Consolidation depenses (anticipee) | **-0,40** | Alesina 2010 (graduel) | -0,60 |
| Expansion investissement | **1,20** | IMF 0,9-1,5, OFCE 1,0-1,3 | 1,0 |
| Expansion transferts | **0,50** | IMF 0,3-0,6 | 0,80 |
| Expansion baisses impots | **0,35** | IMF 0,1-0,5 | 0,40 |
| SMIC (special) | **0,15** | Kramarz & Philippon 2001 | n/a |
| Fraude fiscale (enforcement) | **-0,40** | Application loi existante | n/a |

### DECAY_PROFILE (Profil Temporel Differencie v3.1)

Depuis la v3.1, le simulateur utilise **3 profils de decroissance** differencies selon le type de mesure budgetaire, au lieu d'un profil unique. Le profil applique a chaque annee est un melange pondere (weighted blend) selon la composition des mesures actives.

**Profil TAXES** — pour les mesures fiscales (TVA, IS, IR, CSG, etc.) :
```
TAXES = (0.90, 0.50, 0.30, 0.15, 0.10, 0.05)  — somme = 2.00
```
Impact rapide et fort la premiere annee, decroissance classique.

**Profil TRANSFERS** — pour les transferts sociaux (retraites, SMIC, allocations) :
```
TRANSFERS = (0.90, 0.50, 0.20, 0.10, 0.05, 0.02)  — somme = 1.77
```
Effet total plus faible car les transferts sont partiellement epargnes.

**Profil INVEST** — pour les investissements productifs (education, transition ecologique, recherche) :
```
INVEST = (0.45, 0.65, 0.45, 0.25, 0.12, 0.06)  — somme = 1.98
```
Pic decale a l'annee 2 (au lieu de l'annee 1), refletant les delais de mise en oeuvre des investissements publics avant que les effets d'entrainement ne se materialisent.

**Sources** : IMF 2014, Blanchard & Leigh 2013, Ramey 2019 (profils temporels differencies par type de depense).

Cap par mesure : 2% PIB (contraintes d'offre).

> **Note — ce qui N'EST PAS en production.** Un mecanisme de *re-impulsion annuelle* (dit « Type B » : chaque tranche annuelle d'investissement aurait genere une nouvelle impulsion de demande, en plus de l'impulsion declenchee au changement de curseur) a ete prototype puis **reverte (commit `11d979e` — « revert annual re-impulse, keep differentiated decay profiles only »)**. Il n'est **pas actif** dans le moteur courant. Seuls les 3 profils de decroissance differencies ci-dessus sont en production ; l'impulsion fiscale reste declenchee une fois par changement de mesure (`_fiscal_impulses`, selection du profil via `_get_decay_profile(measure_id)` dans `budget_simulator/simulator.py`).

### Inflation et Courbe de Phillips

Le moteur modelise l'inflation par une **courbe de Phillips augmentee**, forme `output_gap` uniquement (evite le double-comptage avec la loi d'Okun qui correle deja chomage et croissance).

**Decomposition annuelle :**
```
Inflation = Terme structurel + Inertie + 0,35 × Output gap + Ajustements (effort budgetaire, TVA) + Rappel BCE
```

| Composante | Valeur | Source |
|-----------|--------|--------|
| **Terme structurel** | 1,5% | Inflation tendancielle France moyen terme. Mediane sourcee entre la sous-jacente INSEE 2025 (1,2%) et le coeur Banque de France projete / cible BCE (1,6 - 2,0%). Decision PO 2026-05-18, Option C (recoupement INSEE / Banque de France / BCE). Constante nommee `INFLATION_STRUCTURELLE` dans `budget_simulator/constants.py`. |
| **Inertie** | 50% × inflation precedente | Terme AR(1) — anticipations + indexation. Seed annee 0 = `INFLATION_BASE = 1,0%` (distinct du terme structurel, c'est juste l'initialisation de la chaine recursive). |
| **Output gap** | 0,35 × ecart au potentiel | Phillips augmentee, coefficient unique. Recalibrage v3.0 evitant le double-comptage avec Okun. |
| **Ajustement effort budgetaire** | Consolidation -0,12 × effort / Expansion +0,08 × \|effort\| | Effet desinflationniste d'une consolidation, inflationniste d'une expansion. Seuil de declenchement \|effort\| > 0,1% PIB. |
| **Rappel BCE haut** | Si inflation > 2,3 % → blend 50/50 vers 2,0% (50 % ancien, 50 % cible) | Politique monetaire restrictive |
| **Rappel BCE bas** | Si inflation < 0,8 % → blend 70/30 vers 2,0% (70 % ancien, 30 % cible — convergence plus lente) | Politique monetaire accommodante |

**Distinction importante — ne pas confondre** :
- Le **terme structurel** (1,5%) est l'**intercept** de la courbe de Phillips : vers quoi pousse l'inflation quand output gap = 0 et hors rappel BCE.
- La **cible BCE** (2,0%) est le **point de convergence forcee** atteint via le rappel monetaire au-dela des seuils 2,3% / 0,8%.
- Les deux apparaissent dans le moteur — ce ne sont pas la meme valeur ni le meme mecanisme.

**Sources** : Blanchard & Leigh 2013 (sensibilites Phillips post-2008), INSEE Note de conjoncture juin 2025 (sous-jacente), Banque de France projections macroeconomiques 2025-2027, BCE Strategy Review 2021 (cible 2%).

### Mecanismes de Second Ordre

| Mecanisme | Formule | Source |
|-----------|---------|--------|
| Cicatrice austerite | -0,10 x severite si effort >3% PIB, cap -0,3%/an | DeLong & Summers 2012 |
| Confiance Alesina | +0,20% max Y1-2, +0,15% max Y3-4 (caps divises) | Alesina 2010, conteste IMF 2012 |
| Crowding-out | 0,002 (invest) a 0,008 (transferts) | Eviction standard |
| Boost potentiel supply-side (v3.1) | Par canal, delais et depreciation differencies, cap +0,20 pt | Khan & Luintel 2006, Bom & Ligthart 2014, FMI 2015/2020 |
| Retour fiscal transition | 0% Y1-2, 5% Y3-4, 8% Y5+ | OECD 2021 |

### Croissance Potentielle Supply-Side (v3.1)

**Nouveau mecanisme** : Les depenses d'investissement productif augmentent la croissance potentielle de maniere dynamique, avec des parametres differencies par canal.

| Canal | Bonus/Md EUR | Delai | Depreciation/an | Source |
|-------|-------------|-------|-----------------|--------|
| **Recherche publique** | +0,0025 pt | 5 ans | 15% | Khan & Luintel 2006 |
| **Transition ecologique (investissement)** | +0,002 pt | 3 ans | 5% | FMI 2015, Bom & Ligthart 2014 |
| **Transition ecologique (renovation)** | +0,001 pt | 2 ans | 3% | FMI 2020 |
| **Education** | +0,001 pt | 15 ans (symbolique) | 5% | Litterature capital humain |

**Rendements decroissants** : Le bonus est calcule via `ln(1 + depense_au_dessus_du_defaut)`, ce qui attenue les gains marginaux a mesure que l'investissement augmente.

**Cap total** : +0,20 pt maximum. La croissance potentielle peut passer de 1,0% a 1,2% maximum.

**Depreciation progressive** : Si les depenses sont reduites, le bonus acquis se deprecie graduellement (il ne disparait pas instantanement). Chaque canal a son propre taux de depreciation.

**Correction bug abs() (v3.1)** : Dans les versions precedentes, les coupes budgetaires (depenses negatives) etaient incorrectement prises en valeur absolue, ce qui les traitait comme des investissements. Ce bug est corrige : seules les depenses positives au-dessus du niveau par defaut generent un bonus.

**Correction bug decay loop (v3.1)** : La boucle de decroissance des impulsions passees etait piegeee a l'interieur du gate d'effort courant. En consequence, quand l'effort budgetaire courant etait nul, les impulsions des annees precedentes disparaissaient au lieu de continuer a se dissiper normalement. Ce bug est corrige : les impulsions passees continuent leur decroissance independamment de l'effort courant.

### Mecanismes Supprimes (v3.0)

- ~~Bonus elasticite investissement (+10% sur toutes les recettes)~~ -- Sans base empirique
- ~~Bonus synergie (consolidation+investissement -> +0,4% croissance)~~ -- Sans base empirique
- ~~Bonus qualite (education+transition -> +0,2%/an)~~ -- Sans base empirique

---

## Notes Methodologiques Generales

### Effets NIVEAU vs FLUX

**Distinction cruciale pour le pouvoir d'achat (PA) :**

**Effets NIVEAU (ONE-TIME)** — Appliques UNIQUEMENT annee de mise en oeuvre via `_is_first_year_change()`.
Sur l'indice PA base 100, un effet de niveau modifie la consommation/revenu disponible UNE FOIS,
puis l'indice evolue selon la trajectoire macro (growth - inflation). Cumul multiplicatif sur
plusieurs annees produirait une erosion artificielle (OFCE Plane & Sampognaro 2024 :
choc TVA permanent = -0,5% PA en pic puis convergence asymptotique, pas erosion lineaire).

Liste exhaustive PA one-time :
- SMIC : Hausse salaire (annee 1 uniquement)
- ISF / superprofits / exonerations salaires : Changement structure
- TVA energie + TVA generale : Ajustement niveau de prix relatif
- Impot sur le revenu (taux superieur, decote) : Changement bareme
- Impots de production : Repercussion prix one-time
- Elargissement IR (nouveaux contribuables) : Changement bareme
- Fiscalite patrimoine : Changement structure fiscale
- Transition ecologique COMPOSANTE taxe carbone : Niveau de prix
- CSG (taux et progressivite) : Niveau revenu disponible
- Cotisations salariales/patronales : Niveau salaire net
- Chomage allocations : Niveau allocation versee
- Fonction publique (point indice + creations postes) : Niveau salaire FP

**Effets FLUX (RECURRENT)** — Appliques CHAQUE ANNEE legitimement :
- Prestations_indexation : Erosion annuelle si sous-indexation (chaque annee, l'ecart
  taux_indexation vs inflation creuse une nouvelle perte pour les beneficiaires)
- ASU : Allocataires plafonnes (50-70% SMIC) perdent une fraction d'allocation chaque annee tant que le plafonnement est actif (phasing pluriannuel)
- Transition ecologique COMPOSANTE renovation : Primes versees chaque annee a de nouveaux beneficiaires
- Retraites (indexation) : Erosion annuelle similaire prestations
- Fraude fiscale/sociale : Recettes recuperees annuellement
- Cotisations recurrentes : Impact budgetaire chaque annee
- Depenses courantes : Budget annuel
- Sante (efforts ONDAM) : Effort annuel reconductible

**Asymetrie volontaire** : `_apply_fonction_publique` n'applique pas d'effet PA negatif sur
les SUPPRESSIONS de postes — en France elles se font par non-remplacement de departs en
retraite (attrition naturelle), pas par licenciements creant du chomage direct. Seules les
CREATIONS de postes ajoutent du PA (calibration INSEE : 10k postes = 0,4 Md€ salaires nets
≈ +0,025% PA via /40000 × 0,001).

**Convention semantique critique** :
- `taux_indexation` (prestations_indexation) et `indexation` (retraites) sont des coefficients
  ∈ [0, 1.2] :
  - `1.0` = 100% inflation compensee (indexation pleine)
  - `0` = gel total
  - `0.5` = demi-indexation
  - `1.2` = sur-indexation (+20% au-dessus de l'inflation, rattrapage)
- NE PAS confondre avec un taux d'inflation cible (0,02, 0,025) — passer ces valeurs comme coefficient produirait un quasi-gel (~98%) au lieu d'une indexation pleine.

**Note technique sur les patterns de gating** :
Le code utilise 3 patterns equivalents pour gater un effet PA one-time :
1. `if self._is_first_year_change('<measure>_pa', {...}): pa = ... else: pa = 0.0` (preferentiel pour les nouveaux handlers, ex. `tva_rate_pa`, `impot_revenu_pa`).
2. `is_first_year = self._is_first_year_change('<measure>', {...})` puis branchement (ex. `cotisations_salariales` l.3338).
3. `if years_elapsed == 0` (ex. `_apply_csg`, `_apply_chomage_alloc`).

Les 12 mesures listees ci-dessus utilisent l'un des 3 patterns. Le test de garde-fou
`tests/test_political_scenarios_2027.py::test_pa_2029_garde_fou_gating_one_time` verifie
le comportement integre (8 scenarios, tolerance ±1.5 pt sur PA 2029).

### Phasing (Montee en Puissance)

**Exemples :**
- Fraude fiscale (5 ans) : 20% | 35% | 50% | 70% | 100%
- ISF climatique (2 ans) : 50% | 100%
- Doublons sociaux (5 ans) : 15% | 30% | 50% | 75% | 100%

### Plafonds Realistes

Le modele applique des plafonds pour eviter resultats irrealistes :
- Fraude fiscale : Max 70 Md EUR
- Fraude sociale : Max 13 Md EUR
- ISF climatique : Max 18 Md EUR
- Taxe superprofits : Max 20 Md EUR

### Indicateurs Macroeconomiques

**Coefficient de Gini :**
- Baseline 2025 : ~0,290
- Negatif = Mesure progressive (reduit inegalites)
- Positif = Mesure regressive (augmente inegalites)

**Pouvoir d'Achat :**
- Baseline 2025 : 100 (indice)
- Positif = Hausse pouvoir achat
- Negatif = Baisse pouvoir achat

**Competitivite :**
- Baseline 2025 : 100 (indice)
- Positif = Amelioration competitivite entreprises
- Negatif = Degradation competitivite

### Calibration Baseline Validee (v3.0)

| Indicateur | Valeur | Horizon |
|------------|--------|---------|
| Dette | ~132% PIB | 2035 (sans reformes) |
| Deficit | ~-6,0% PIB | 2035 (sans reformes) |
| Croissance potentielle | 1,0% | Baseline (extensible a 1,2%) |
| Chomage NAIRU | ~7,5% | Structurel |
| Inflation tendancielle | voir section « Inflation et Courbe de Phillips » | Terme structurel Phillips (`INFLATION_STRUCTURELLE`) |
| Inflation cible BCE | ~2,0% | Point de convergence forcee (rappel monetaire) |

---

## Sources et References

### Institutions Officielles Francaises

- **DGFiP** (Direction Generale des Finances Publiques)
- **INSEE** (Institut National de la Statistique)
- **DREES** (Direction de la Recherche, des Etudes, de l'Evaluation et des Statistiques)
- **DARES** (Direction de l'Animation de la Recherche)
- **COR** (Conseil d'Orientation des Retraites)
- **CNAM** (Caisse Nationale d'Assurance Maladie)
- **Unedic** (Union nationale interprofessionnelle pour l'emploi)
- **HCFPS** (Haut Conseil du Financement de la Protection Sociale) — rapports fraude sociale / minima sociaux (sept. & oct. 2024)
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

- **OCDE** - Taxing Wages, Health at a Glance, "Getting Infrastructure Right" (2021)
- **FMI** - Selected Issues France, Fiscal Monitor 2014
- **EU Tax Observatory** (Gabriel Zucman)
- **OMS** (Organisation Mondiale de la Sante)

### Recherche Academique (v3.0)

- **Blanchard & Leigh 2013** : Multiplicateurs fiscaux en periode de consolidation
- **Alesina & Ardagna 2010** : Effets confiance de l'austerite (conteste IMF 2012)
- **DeLong & Summers 2012** : Cicatrices d'austerite (hysteresis)
- **Fatas & Summers 2018** : Couts permanents de la consolidation
- **Bom & Ligthart 2014** : Elasticite output du capital public (stock model)
- **Kramarz & Philippon 2001** : Effets du salaire minimum sur l'emploi
- **Herndon, Ash & Pollin 2014** : Critique Reinhart-Rogoff (seuil 90%)
- **Auerbach & Gorodnichenko 2012** : Multiplicateurs en recession vs expansion
- **Romer & Romer 2010** : Multiplicateurs fiscaux (tax)
- **Guajardo, Leigh & Pescatori 2014** : Critique effet confiance Alesina
- **Khan & Luintel 2006** : Productivite de la recherche publique et croissance potentielle
- **Ramey 2019** : Profils temporels differencies des multiplicateurs par type de depense
- **FMI 2015** : Investissement public et croissance dans les economies avancees (Fiscal Monitor)
- **FMI 2020** : Politiques publiques pour la reprise post-COVID (retours investissement vert)

### Programmes Politiques

- **PLF 2026** - Projet de Loi de Finances
- **PLFSS 2025** - Financement Securite Sociale
- **Plan antifraude 2023-2027** (Gouvernement) - source des tooltips fraude sociale / digitalisation controles
- **NFP 2027** - Nouveau Front Populaire
- **RN 2027** - Rassemblement National

---

## Limites et Precautions

1. **Incertitude parametrique** : Les elasticites sont des estimations moyennes
2. **Delais de transmission** : Certains effets mettent 5-10 ans a se materialiser
3. **Interactions** : Les mesures peuvent se renforcer ou s'annuler
4. **Contexte macroeconomique** : Hypotheses de croissance mondiale, taux directeurs BCE
5. **Perimetre comptable** : Differences possibles avec chiffres officiels
6. **Stochasticite** : Le modele inclut un bruit aleatoire (ecart-type 0,3% sur la croissance)

---

## Choix de design assumes (vs modeles academiques)

Cette section documente les choix methodologiques deliberes qui pourraient etre vus comme des limitations par rapport aux modeles academiques (MESANGE, e-mod, OFCE iAGS, IPP TAXIPP). Ces choix sont assumes pour preserver la lisibilite et l'accessibilite citoyenne du simulateur.

### L1. Pas d'intervalles de confiance (estimations ponctuelles)

Le simulateur produit des trajectoires deterministes (avec un bruit illustratif sigma=0,3% sur la croissance), pas de bandes Monte-Carlo. **Justification** : pour un public citoyen, des fan charts a la Banque d'Angleterre introduisent plus de confusion que d'information. Pour des intervalles rigoureux, complement avec MESANGE (DG Tresor) ou e-mod (OFCE) recommande. Cette limitation est partagee par OFCE iAGS et le simulateur Tresor en sortie grand public.

### L2. Profil INVEST avec pic Y2 (et non Y3-Y4)

Le profil temporel des multiplicateurs d'investissement public est `(0.45, 0.65, 0.45, 0.25, 0.12, 0.06)` avec pic Y2. **Justification** : Bom-Ligthart 2014 (meta-analyse 578 estimations) trouve plutot un pic Y3-Y4 pour les capital stock models (TGV, nucleaire, infrastructures lourdes), mais Ramey 2019 montre Y1-Y2 pour les flow models (projets pre-prets). La France 2030 et la LPM 2024-2030 sont majoritairement des projets pre-prets qui decaissent vite, ce qui justifie le choix Y2. Choix dans la fourchette basse defendable.

### L3. Loi d'Okun avec beta = -0.35 (mediane fourchette OFCE)

Le coefficient d'Okun France est fixe a -0.35. **Justification** : la fourchette OFCE/INSEE est large [-0.30, -0.55] selon la periode et la specification. Choisir le median -0.35 evite (a) le pessimisme de -0.55 (qui ferait exploser le chomage en recession), (b) l'optimisme de -0.30 (qui sous-estimerait la sensibilite emploi). Choix de prudence pedagogique.

### L4. Elasticite fiscale en recession a 1.12 (asymetrique post-2008)

L'elasticite des recettes fiscales au PIB est `1.12` en recession (`growth < -1%`), au-dessus du consensus OCDE Wolswijk 2008 (0.95-1.05). **Justification** : Belinga-Benedek-Mooij-Norregaard (FMI 2014) et Cotis-Eyssartier 2010 montrent une asymetrie post-2008 : l'IS et les plus-values mobilieres s'effondrent plus que proportionnellement en recession (-30 a -50% en 2008-2009 pour la France). Le 1.12 est donc empiriquement justifie pour la France post-crise, meme s'il sort de la moyenne OCDE pre-crise.

### L5. Plafond effort 2% PIB par mesure

Aucune mesure ne peut depasser 2% PIB d'effort budgetaire (apres clip individuel) avant le plafond cumulatif 10% PIB (FMI 2010). **Justification** : Guajardo-Leigh-Pescatori 2014 (action-based dataset OCDE) chiffre la mediane des consolidations historiques a 1.0% PIB et le Q3 a ~1.7% PIB. Au-dela de 2%, les multiplicateurs ne sont plus calibres (Auerbach-Gorodnichenko 2012 : non-linearites fortes hors echantillon). Le plafond 2% couvre 75% des episodes historiques + sert de garde-fou pedagogique.

### L6. Modele a agent representatif (pas de microsimulation par decile)

Les coefficients Gini, pouvoir d'achat et competitivite sont calcules au niveau macro avec des coefficients calibres sur parts de budget INSEE (Budget des Familles 2017/2022), pas via une microsimulation par decile. **Justification** : architecture standard de tous les modeles macro reduits (RA-DSGE, MESANGE, e-mod). Pour la distribution par decile, complement OpenFisca-France (INRIA) et TAXIPP (IPP) recommandes. Cette limitation est partagee par tous les outils macro grand public.

### L7. Pas de backtesting historique (chocs 2008/COVID/energie 2022)

Le simulateur n'inclut pas de validation par fit historique sur les chocs 2008, COVID 2020, ou energie 2022. **Justification** : c'est un simulateur structurel calibre **ex-ante** (chocs de politique publique), pas un modele de prevision conjoncturelle. La calibration est documentee sur litterature academique (Blanchard-Leigh 2013, Auerbach-Gorodnichenko 2012, Bom-Ligthart 2014, Bozio-Wasmer 2024, COR 2024). MESANGE et e-mod ne sont pas non plus sortis avec un backtest comme prerequis.

### L8. Effets emploi des mesures fiscales : capture via le multiplicateur, pas via signal direct

Pour les mesures qui modifient les recettes fiscales (suppression de niches, hausse d'impots), **l'effet emploi est captee par le multiplicateur fiscal du moteur** (cascade : Δrecettes → Δcroissance → Δchomage via Okun β=-0.35), **pas par un signal direct exporte dans `impacts['chomage']`**.

**Lecon de calibration (mai 2026)** : un coefficient direct `0.008 × montant_supprime` avait ete introduit pour les niches sociales TGE en se basant sur Bozio-Wasmer 2024 (138k emplois pour suppression 60 Md€). Test runtime a revele un **double-comptage** : le multiplicateur fiscal atteint deja la cible Bozio-Wasmer (-140 630 emplois mesures sans signal direct), et le signal direct amplifiait l'effet ×9 a ×95.

**Regle generale** : exporter `impacts['chomage']` direct uniquement pour les mesures qui modifient le **cout du travail** (cotisations patronales, SMIC) ou la **structure du marche du travail** (assurance chomage, ASU). Pour les mesures fiscales pures (niches, IS, IR), laisser le multiplicateur faire le travail.

---

## Historique des Versions

- **Version 1.0** (31/10/2025) : Creation initiale
- **Version 2.0** (16/11/2025) : Nettoyage code, version pedagogique
- **Version 3.0** (27/03/2026) : Recalibrage complet multiplicateurs (weighted blend per-measure, DECAY_PROFILE), correction debt_drag (-0,005), correction chomage_gap_weight (0,0), ajout cicatrice austerite/crowding-out/boost potentiel/retour fiscal transition, suppression bonus sans base empirique, correction taux croissance depenses, validation baseline par agent economiste
- **Version 3.1** (29/03/2026) : DECAY_PROFILE differencie (3 profils TAXES/TRANSFERS/INVEST), croissance potentielle supply-side dynamique par canal (recherche, transition eco, education) avec delais et depreciation, correction bug abs() (coupes traitees comme investissements), correction bug decay loop (impulsions passees disparaissaient si effort courant nul)
- **Version 3.2** (18/05/2026) : Terme structurel de la courbe de Phillips releve de 1,2 % a 1,5 % (Option C, mediane sourcee INSEE sous-jacente 2025 / coeur Banque de France projete / cible BCE). Constante nommee `INFLATION_STRUCTURELLE` introduite dans `constants.py` (source unique, remplace le litteral magique `0.012`). Ajout d'une section dediee « Inflation et Courbe de Phillips » documentant l'ensemble des composantes du moteur d'inflation (terme structurel, inertie, output gap, ajustements, rappel BCE). Aucune autre modification de calibration. Golden master regenere et audite : delta cible coherent (effet denominateur PIB nominal favorable, aucun scenario ne diverge).

---

*Document participatif - Vos retours et corrections sont les bienvenus*
*Contact : contact@francebudget.fr*
