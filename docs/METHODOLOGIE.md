# METHODOLOGIE - Simulateur Budget France 2025-2035

**Version** : 4.0
**Date** : Juin 2026
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

**Changements majeurs v4.0 (refonte « assemblage temporel ») :**
- **Depenses** : recurrence unique chainee des l'annee 1 — `Dep(t) = Dep(t-1) x (1 + g_vol) x (1 + pi_idx)`. Plus de regime special 2026 (« bridging year ») ni de taux d'amorcage exogene. Indexation mixte : 54% de la depense suit l'inflation PASSEE (pensions, prestations), 46% le deflateur contemporain
- **Recettes** : elasticite unitaire au PIB nominal contemporain (`ELASTICITE_PO_PIB = 1,0`, HCFP note 2023-01). Supprimes : elasticite differenciee par regime de croissance (1,00/1,06/1,08/1,12), erosion forfaitaire 0,2%/an, rustines de transition 2026
- **Boucle annuelle reordonnee** : macro de l'annee (avec impulsion budgetaire de t-1) -> PIB (deflateur contemporain) -> chomage -> flux aux prix de l'annee -> mesures (impulsion stockee pour t+1)
- **Phillips ANCREE** : formule `(1-rho) x (pi* + kappa x gap) + rho x pi(t-1)` — `INFLATION_STRUCTURELLE` (1,6%) est le point de convergence REEL et `PHILLIPS_PENTE_MT` (0,20) est DIRECTEMENT la pente de moyen terme ; rappel BCE a 2,0% en garde-fou de surchauffe, plancher a 0,8% desormais inerte en statu quo
- **Baseline honnete** : l'« assainissement implicite gratuit » (~24 Md EUR/an) de l'ancien assemblage a disparu. **Chiffres recales le 26/08/2026** — ceux publies ici jusque-la (deficit 2026 -5,05 %, dette 2030 ~129,5 %, dette 2035 ~150 %) dataient d'AVANT les lots 8 et 9, qui les ont deplaces de 10 a 12 points. Et ils melangeaient deux objets : le **statu quo NU** (le moteur sans aucune mesure, objet de calibration, servi nulle part) et le **scenario de reference** `plf_2026` (« Budget 2026 (vote) », ce que le site sert comme point de depart). Les deux, mesures sur l'etat livre :

| | statu quo NU | scenario de reference `plf_2026` |
|---|---|---|
| Deficit 2026 | -5,30 % | **-5,17 %** (loi votee : -5,0 %) |
| Dette 2030 | 129,12 % | **128,65 %** (mission IGF : 130,5) |
| Dette 2035 | 151,17 % | **149,77 %** |
| Deficit 2035 | -9,05 % | **-8,69 %** |

  Chiffres re-mesures le 30/08/2026 (passe v0.6.3 : fin du double comptage de la duree
  d'indemnisation, monotonie fraude sociale, cout perenne du non-recours ASU, graine 2025
  aux comptes definitifs INSEE et inertie d'inflation ramenee au milieu de sa fourchette).
  Re-mesures le 07/10/2026 (v0.6.7 : moteur sans tirage aleatoire, cf. « Stochasticite », et
  tendanciel du potentiel re-ancre a 1,228 %, cf. « Calibration Baseline Validee »).

  Toute grandeur mesuree publiee dans ce document nomme desormais son objet, et une garde de la suite moteur (`tests/test_chiffres_publies_v061.py`) la recalcule a chaque execution : un chiffre qui cesse de reproduire fait rougir la CI au lieu de rester en ligne.

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
| Indexation | 100% inflation | v0.6.7 : écart de niveau composé des revalorisations évitées (chacune à l'inflation de son année) sur 0,86 de la masse nominale des pensions, SYMETRIQUE au premier ordre, plateau 7 ans |

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
  nominale des pensions de l'année × [1 − Π_s (1 − δ × max(π_s, 0))]`, δ = 1 − indexation, une
  revalorisation par an dès 2026, chacune à l'inflation de SON année, sept au plus (plateau 7 ans) —
  le stock de pensions erode se renouvelle (nouvelles pensions liquidees sur les salaires,
  extinction des cohortes anciennes) ; l'écart constitué subsiste ensuite, sans se rembourser.
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

- **Inegalites** : +1,25 annee d'age au-dessus de la reference legale de l'annee = +0,001 Gini (legerement REGRESSIF — mortalite differentielle : esperance de vie ouvriers -6 ans vs cadres, taux d'emploi 55-64 ans 52 % vs 71 %, COR 2024). Correction v0.6.0 : la doc affichait -0,002 « legerement progressif », signe INVERSE du code (audit 08/2026, constat 6). v0.6.1 : l'ecart se mesure a la reference de l'annee, comme le canal budgetaire, pour que le statu quo reste neutre ; le coefficient est inchange — l'effet distributif du canal emploi n'est pas etabli (heterogeneite forte documentee) et ne sera pas ajuste hors d'une passe dediee. L'effet plein est servi l'annee ou la mesure OUVRE son ecart au calendrier legal (et non l'annee ou elle apparait), puis 10 % de residu annuel : cf. § « Effets NIVEAU vs FLUX », 4e pattern.
- **Pouvoir d'achat** : Gel total indexation retraites = -0,007 PA agrégé/an récurrent (OFCE Brief 124, 15/02/2024)
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
| DREES, *Les depenses de sante en 2023*, Panoramas ed. 2024, fiche 21 tableau 1 | prevention institutionnelle **7 516 M EUR en 2023** ; ed. 2025 : +0,9 % en 2024 | **7,5 Md EUR** |
| OCDE, *Health at a Glance 2025*, note pays France (nov. 2025) | « France spends **2,3 %** of total health spending on prevention […] less than the OECD average of **3,4 %** » | 2,3 % x 333 Md EUR (DCSi) = **7,66 Md EUR** |

**La borne haute : 11,2 Md EUR, et elle est DERIVEE, pas choisie.** C'est la
convergence vers la moyenne OCDE : 7,5 + (3,4 % − 2,3 %) x 333 = 11,2 Md EUR.
L'amplitude du curseur (0 a +3,7 Md EUR/an) devient ainsi sourcee, alors que
l'amplitude de la v0.5.1 (0 a +3,0) l'etait par accident.

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
   **15 Md EUR/an**. Le curseur pilote l'agregat SHA (7,5), **pas les 15**.
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
| Vos et al., *ACE-Prevention Final Report*, 2010 | 21 mesures **dominantes** sur 150 : 4,6 Md AU$ → 11 Md AU$, ratio **2,4** | **borne haute absolue** (selection optimale, vie entiere) |
| OCDE, *The Heavy Burden of Obesity*, 2019, ch. 6 | meilleure intervention : 13 Md USD PPA cumules 2020-2050 sur 36 pays ≈ **0,012 Md EUR/pays/an** | trois ordres de grandeur sous la v0.5.1 |

Le « six-fold economic return » du resume executif du meme rapport OCDE 2019
et le « 7 US$ pour 1 » de l'OMS (*Saving lives, spending less*, 2021, champ :
76 pays a revenu faible ou intermediaire) sont des retours **PIB/emploi**, pas
budgetaires : ils n'ont pas leur place dans un solde public francais.

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
(60 k EUR, euros 2025 non indexés). Ordres de grandeur calculés : intensité 10 →
215 875 postes en 2030 (13,0 Md EUR/an), 529 875 au plateau (31,8 Md EUR/an) ; intensité
20 → 289 272 postes en 2030 (17,4 Md EUR/an), 710 032 au plateau (42,6 Md EUR/an). Les
« potentiels » cités plus haut pour les deux axes sont des ordres de grandeur de la
littérature, pas les montants du moteur. Jusqu'à v0.6.6, le stock valait
`départs × taux × efficacité(année courante) × nombre d'années` : il réévaluait les
cohortes passées, comptait une cohorte 2026 inexistante et pouvait croître de plus que
les départs d'une année (intensité 20 : 525 950 postes en 2030 ; audit externe Codex,
10/2026). Le curseur « effectifs » puise dans le **même vivier** : réforme + curseur ne
suppriment jamais plus de postes que les départs cumulés depuis 2026 (v0.6.0). Propriétés
verrouillées par `tests/test_audit_codex_v067.py` et `tests/test_fp_v060.py`.

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
- Gini canal taux : GINI_ALLOC_PAR_MD_EUR = 0,0008 par Md EUR coupe (OFCE 2023)
- Gini canal duree : × GINI_DUREE_SURPOIDS = 1,6 — par euro, une coupe de
  duree frappe plus bas (cohorte fin de droits : a +3 mois, 71 % ne touchent
  ni RSA ni ASS — Dares Focus n° 53 × DREES E&R n° 1368 ; cf. M35)
- Degressivite : son facteur (±15 % d'allocations) s'applique aux DEUX canaux
  ET au Gini (v0.6.4, fin du free lunch — meme famille que le fix PA v0.6.3)
- PA : 0,002 par 5 Md EUR sur le canal € total (taux ET duree, v0.6.3)

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
| Pouvoir d'achat | effort / revenu disponible brut | nul a cout constant |
| Gini | borne theorique proportionnelle a l'effort | nul a cout constant |

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

**Pourquoi le Gini est une borne, pas une estimation.** Aucune source ne publie
l'effet de l'ASU sur l'indice de Gini : les scenarios officiels donnent un
**taux de pauvrete**. Le moteur ne fabrique pas la conversion. Il retient une
borne theorique entierement explicite — un transfert net integralement recu par
le tout premier centile, cas limite ou l'amelioration est arithmetiquement
maximale. Toute concentration reelle etant moins extreme, l'effet reel est plus
**petit** : le moteur **majore** deliberement le benefice redistributif des
programmes genereux plutot que de le minorer. Et il le **conditionne a
l'effort** : dans la variante a cout constant, la reforme compte **4,0 millions
de perdants pour 3,9 millions de gagnants** — c'est un pur transfert entre
menages, dont l'effet agrege est nul par construction.

**Effets de NIVEAU, pas de flux.** Le Gini et le pouvoir d'achat de l'ASU sont
emis sous forme d'**increment de montee en charge** : leur somme sur les quatre
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

**Limite connue et non corrigee ici** : les coefficients Gini herites des autres
leviers sociaux sont d'un ordre de grandeur superieur **par euro transfere**.
Les homogeneiser suppose de re-deriver le facteur d'echelle global
`GINI_IMPACT_SCALE`, chantier explicitement differe (v0.7).

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

**Impact Gini (recalibre v0.6.1, item I28)** : **+0,0010 de Gini pour
+50 EUR/tCO2** (fourchette 0,0009-0,0011), soit exactement la MOITIE du
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

**Retour fiscal differencie (v3.0)** :
- Annees 1-2 : 0% (construction)
- Annees 3-4 : 5% (emplois induits, TVA)
- Annees 5+ : 8%
- Source : OECD 2021, Cour des comptes 2023

**Mesures d'investissement productif (pour multiplicateur)** : education, transition_eco, recherche (PAS defense)

**Impacts :**
- Gini : +5 Md EUR renovation = **-0,0017** (redistributif ; recalibre v0.6.1,
  cf. § Aides Renovation Energetique)
- PA : +5 Md EUR = +0,001 (economies energie)
- Competitivite : +10 Md EUR = +0,002 (competitivite verte LT)
- L'investissement vert lui-meme n'a **aucun** canal Gini : aucune source ne
  donne l'incidence distributive d'un euro d'investissement (a la difference
  des aides a la renovation, qui sont un transfert monetaire aux menages). Le
  chiffre n'est pas fabrique.

### Aides Renovation Energetique

- MaPrimeRenov', eco-PTZ
- Effet levier : 1 EUR public = 3 EUR prive
- Reduction facture energetique menages

**Impact Gini (recalibre v0.6.1, item I29)** : **-0,00034 de Gini par Md EUR**,
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

Contrairement a l'education, l'aide a la renovation est un transfert
**monetaire** aux menages : elle entre legitimement dans le revenu disponible,
le canal est pleinement dans le perimetre de l'indicateur affiche.

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

**Curseur d'intensité — courbe continue (v0.6.7, audit externe Codex 10/2026, arbitrage de
Cyril)** : `recette totale = IFI + intensité × (ISF complet − IFI)`, donc écart au statu quo =
`intensité × (ISF complet − IFI)`, où « ISF complet » est le point NFP ci-dessous (seuil 1,3 M EUR,
taux 1 %, bonus vert 30 % : +7,90 Md EUR en 2030, IFI de 2,16 Md EUR déduit). Gini, pouvoir
d'achat et compétitivité sont interpolés de la même façon. Monotone, nul à 0, identique au bit à 1
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

**Impulsions par levier et par flux (v0.6.7, audit externe Codex 10/2026)** : l'effet keynésien de l'année est la somme, sur les leviers, les flux et les âges, de

```
effet(t) = Σ_levier Σ_flux Σ_âge  −k(flux, sens) × Δe(t − âge) × profil_levier(âge)
Δe(t)    = e(t) − e(t−1),  e = flux du levier / PIB nominal de son année   (e > 0 = consolidation)
```

Chaque flux d'un levier est multiplié séparément : ses recettes au canal fiscal, ses dépenses au canal investissement (éducation, recherche, transition écologique) ou transferts/générique. Le sens (consolidation ou expansion) est celui du NIVEAU du flux par rapport au statu quo, pas celui de sa variation : retirer une hausse d'impôts porte le multiplicateur d'une hausse, donc la somme des effets d'IMPULSION d'une mesure retirée revient exactement à zéro et ce cumul ne dépend que du niveau atteint (un flux qui change de signe dans l'année est scindé en zéro). **Ce n'est pas le niveau du PIB** (texte corrigé en v0.6.7, lot 3b ; l'équation est inchangée) : le rappel vers le potentiel « rembourse » pendant la mesure l'écart qu'elle ouvre, et au retrait le PIB passe SOUS la référence avant d'y revenir lentement — une relance temporaire de +1 % du PIB de transferts pendant 4 ans porte le PIB à +0,8 % au pic, puis à −0,46 % en 2033-2034 et encore −0,35 % en 2039, dont environ 0,2 pt de traînée de la dette accumulée (−0,15 % sans elle). Une mesure temporaire n'est donc pas neutre en niveau une fois retirée : elle se paie en partie après coup. Exceptions : le SMIC et la fraude fiscale ont un coefficient calibré sur leur effet NET, appliqué à leur solde (`FiscalMultipliers.MESURES_MULTIPLICATEUR_NET`). L'impulsion de l'année est lue dans les impacts de t−1 (lag d'un an, cf. boucle annuelle).

**Ce que cela corrige (v0.6.6, deux erreurs de calcul)** : (1) une impulsion n'était stockée qu'au changement du hash des mesures — constant pendant une simulation —, donc UNE impulsion par scénario, égale au NIVEAU de la première année non nulle : la montée en charge n'était jamais multipliée (fraude fiscale : 0,10 % du PIB multiplié, 0,47 % atteint en 2030), et les résidus s'arrêtaient net dès que l'effort courant repassait sous 0,1 % du PIB ; (2) un seul multiplicateur par scénario, moyenne des multiplicateurs SIGNÉS pondérée par l'effort BRUT puis appliquée à l'effort NET : un programme équilibré n'avait aucun effet keynésien, et une consolidation nette pouvait être comptée comme une relance (banc de l'auditeur, 40 Md EUR d'investissement + 20/40/50 Md EUR d'impôts : +0,253 / 0 / +0,060 pt au lieu de +0,420 / +0,120 / −0,030). Contrat verrouillé par `tests/test_impulsions_v067.py` (somme signée, additivité d'une montée en charge, résidus après retrait, franchissement de zéro, chaque variation multipliée une fois en simulation complète).

**Multiplicateur cumulé = k × Σ profil** : avec ces profils, l'effet de NIVEAU d'une impulsion permanente vaut 2,38 fois l'impulsion pour l'investissement (1,2 × 1,98), 1,0 pour une hausse d'impôts (0,5 × 2,0), 0,89 pour les transferts (0,5 × 1,77), 1,09 à 1,20 pour une coupe générique, 0,70 pour une baisse d'impôts. La v0.6.6 n'exposait presque jamais ces grandeurs (une seule impulsion par scénario, plafonnée) ; depuis la v0.6.7 elles portent tout le canal keynésien. **Limite déclarée** : 2,38 est au-dessus du FMI (WEO oct. 2014, ch. 3 : +1,5 % de PIB quatre ans après 1 point de PIB d'investissement public, en conditions favorables) ; le recalage du profil INVEST est un arbitrage de calibration ouvert, distinct de cette correction d'équation.

### Table des Multiplicateurs de Base

| Type | Valeur | Source | Ancien |
|------|--------|--------|--------|
| Consolidation fiscale (anticipee) | **-0,615** | v0.6.7 : calé « central » (tableau ci-dessous) | -0,50 (v0.6.6), -0,92 (v2.0) |
| Consolidation depenses generique | **-0,81** (v0.6.7, calé « central » ; -0,60 en v0.6.6) | Ramey 2019 (« 0,6 to 1 », bas de fourchette) ; Gechert & Rannenberg 0,4-0,7 | -0,40 (v3.0-v5.1, sous le consensus) |
| Coupe d'investissement public | **-1,20** | SYMETRIQUE de la hausse (Gechert 2015 et Mesange : linearite en signe ; FMI WEO oct. 2010 ch. 3 : coupes d'investissement au haut de l'echelle de cout) | canal ABSENT v5.1 (coupe traitee a -0,40 : audit 08/2026, constat 2) |
| Expansion investissement | **1,20** | IMF 0,9-1,5, OFCE 1,0-1,3 | 1,0 (v2.0) |
| Expansion transferts | **0,71** | v0.6.7 : calé « central » | 0,50 (v0.6.6), 0,80 (v2.0) |
| Expansion baisses impots | **0,455** | v0.6.7 : calé « central » (asymétrie hausse/baisse 0,7 conservée) | 0,35 (v0.6.6), 0,40 (v2.0) |
| SMIC (special) | **0,15** | Kramarz & Philippon 2001 | n/a |
| Fraude fiscale (enforcement) | **-0,40** | Application loi existante | n/a |

**Recalibrage « central » des familles (v0.6.7, GO de Cyril du 07/10/2026)** — règle : chaque
famille est calée sur la valeur CENTRALE de la littérature, en effet de NIVEAU sur le PIB réel 4 ans
après le début d'une impulsion PERMANENTE de 1 % du PIB (définition du FMI), MESURÉ DANS LE MOTEUR
COMPLET (rappel vers le potentiel λ = 0,2, Phillips, Okun, dette) et non en `k × Σ profil`. Une
famille déjà centrale ne bouge pas. Constantes `MULT_*` et `MULT_CIBLE_NIVEAU_4ANS` (constants.py),
test-propriété `tests/test_multiplicateurs_centraux_v067.py`.

| Famille (profil) | Cible centrale, niveau à 4 ans | Source vérifiée | Moteur avant (k v0.6.6) | Moteur après | 10 ans (niveau / cumulé Ramey) |
|---|---|---|---|---|---|
| Investissement public (INVEST) | 1,5 | FMI WEO oct. 2014 ch. 3 : « +0,4 % la même année, +1,5 % quatre ans après » ; Gechert 2015 : dépenses ≈ 1, investissement ≈ +0,5 | 1,41 (k = 1,2) | **inchangé** (−6 %) | 0,40 / 0,92 |
| Coupe de dépenses générique (TAXES) | 0,8 | Ramey 2019 JEP : « 0.6 to 1 for spending multipliers » (milieu) ; Gechert ≈ 1 | 0,58 (k = 0,60) | 0,79 (k = 0,81) | 0,15 / 0,56 |
| Transferts (TRANSFERS) | 0,65 | Gechert 2015 : « 0.3 to 0.4 units » sous les dépenses (≈ 1) | 0,44 (k = 0,50) | 0,65 (k = 0,71) | 0,01 / 0,43 |
| Hausse d'impôts (TAXES) | 0,65 | Gechert 2015 (même écart) ; Ramey 2019 « −2 to −3 » (États-Unis, chocs narratifs : non retenu comme central pour la France) | 0,52 (k = 0,50) | 0,65 (k = 0,615) | 0,05 / 0,44 |
| Baisse d'impôts (TAXES) | 0,455 | asymétrie hausse/baisse du moteur conservée (0,35/0,50) — borne haute de lecture pour l'investissement : Banque mondiale, GEP juin 2024 ch. 3, niveau ≈ 1,1 à 5 ans (≤ 1,6), économies émergentes et en développement | 0,33 (k = 0,35) | 0,45 (k = 0,455) | 0,09 / 0,28 |

Le rappel vers le potentiel rend les effets de demande transitoires : à 10 ans le niveau est revenu
près de zéro (l'effet durable du capital public passe par le canal d'offre `SUPPLY_EFFECTS`). **Aucun
investissement ne s'autofinance** : multiplicateur cumulé 10 ans × 0,51 = 0,47 < 1, et 11 % seulement
du coût brut d'une impulsion permanente d'investissement revient au solde public sur 2026-2036
(intérêts compris) — jusqu'en v0.6.6, `k × Σ profil` = 1,2 × 1,98 = 2,38 en effet permanent impliquait
l'autofinancement (2,38 × 0,51 > 1), masqué par l'impulsion unique. Le recalibrage RELÈVE trois familles
sur quatre : la v0.6.6 était sous la valeur centrale pour les impôts, les transferts et les coupes.

**Perimetre du canal investissement (v0.6.0)** : education, recherche publique,
transition ecologique UNIQUEMENT (`INVESTMENT_CORE_MEASURES`). La sante courante
et la reforme de l'Etat sont de la consommation/optimisation publique : canaux
transferts/generique (la revue adverse du 24/08 a montre que le perimetre large
donnait un multiplicateur d'investissement aux coupes... de sante).
L'attenuation « confiance » (division par 1,10, Alesina-Favero-Giavazzi 2019 :
plans depense « mild recessionary ») ne s'applique qu'a la part NON-investissement
d'une consolidation — l'echantillon AFG ne contient quasiment aucun plan a
dominante investissement.

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

### DECAY_PROFILE (Profil Temporel Differencie v3.1)

Depuis la v3.1, le simulateur utilise **3 profils de decroissance** differencies selon le type de mesure budgetaire, au lieu d'un profil unique. Depuis la v0.6.7, chaque impulsion porte le profil de SON levier (`_get_decay_profile`) — plus de mélange pondéré à l'échelle du programme.

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

**Plus de plafond de taille (v0.6.7)** : le plafond « effort ≤ 2 % du PIB » est retiré (cf. L5). Le seul filet reste le clip de croissance [−3,5 % ; +2,5 %].

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
Inflation = (1 - 0,5) × (1,6% + 0,20 × Output gap) + 0,5 × Inflation precedente + Ajustements (effort budgetaire, TVA) + Garde-fous BCE
```
soit, pour un output gap constant, un point fixe `pi = 1,6% + 0,20 x gap`.

| Composante | Valeur | Source |
|-----------|--------|--------|
| **Point fixe (terme tendanciel)** | (1 - inertie) × 1,6% | **Deflateur du PIB** tendanciel France (voir « Ce que mesure la variable inflation » ci-dessous). Chaine d'ancrage sourcee maillon par maillon : 2,0% IPCH zone euro (BCE, Survey of Professional Forecasters T3 2026 — anticipations de long terme inchangees malgre un IPCH 2026 a 2,7-3,0%) -> ~1,75% IPC France (Gouvernement, Rapport d'avancement annuel 2026 du PSMT 2025-2029, **note 6**, qui ecrit l'ecart explicitement) -> ~1,6% deflateur (INSEE, blog « Inflation : les deflateurs en comptabilite nationale », sept. 2022 ; decomposition RAA 2026 p. 12). Constante `INFLATION_STRUCTURELLE`. **Correction v4.0** : dans un AR(1) `i(t) = c + rho × i(t-1)`, le point fixe est `c/(1-rho)`, pas `c` — l'intercept a ete mis sous `(1-rho)`. |
| **Inertie** | 50% × inflation precedente | Terme AR(1) — anticipations + indexation. Depuis la v4.1 c'est un parametre de **vitesse** seulement : il ne deplace plus le niveau du regime etabli. Ancrage sourcee : BdF Billet de blog n° 335 (dec. 2023) — dans les pays sans clause d'indexation, dont la France depuis 1983, la transmission de l'inflation realisee aux anticipations tombe sous 1/3 de sa valeur de court terme aux horizons longs. Seed annee 0 = `INFLATION_BASE = 1,0%` (distinct du point fixe : c'est l'initialisation de la chaine recursive). |
| **Output gap** | **pente de moyen terme 0,20** × ecart au potentiel, DANS l'ancrage | `PHILLIPS_PENTE_MT`. **Correction v4.1** : le terme de gap etait reste HORS de l'ancrage (coefficient 0,35), ce qui faisait de rho un multiplicateur cache — la grandeur homologue de la litterature valait 0,35/0,50 = 0,70, ecrite nulle part. Depuis, le parametre du code EST la pente de moyen terme. **A declarer : choix de calibration ENCADRE, pas une estimation France** (il n'en existe aucune sur l'output gap). Bornes : BdF, *Rue de la Banque* n° 56 (fev. 2018), pente 4c2/(1-c1) ~ 0,40 (zone euro) ; BCE, ECB WP n° 3133 (oct. 2025), ~0,065 converti sur l'output gap. Motif du 0,20 : le gap est negatif sur tout l'horizon des scenarios francais, donc sur le segment plat au sens de Benigno-Eggertsson. |
| **Ajustement effort budgetaire** | Consolidation -0,12 × effort / Expansion +0,08 × \|effort\| | Effet desinflationniste d'une consolidation, inflationniste d'une expansion. Seuil de declenchement \|effort\| > 0,1% PIB. **Dette connue declaree** : ces deux termes sont non sourcees, asymetriques et en double-comptage partiel avec le canal output gap — item d'une instruction dediee, pas corriges en v4.1. |
| **Garde-fou BCE haut** | Si inflation > 2,0% (cible BCE, `BCE_CIBLE_INFLATION`) → blend 50/50 vers la cible | Garde-fou de SURCHAUFFE (v4.0) : contient l'inflation au-dessus de la cible. Ne se declenche pas en statu quo. |
| **Garde-fou BCE bas** | Si inflation < 0,8 % (`BCE_PLANCHER_ACCOMMODANT`) → blend 70/30 vers la TENDANCIELLE 1,6% | Politique monetaire accommodante, tiree vers le point fixe du regime. **v4.1** : ce plancher se declenchait DES L'ANNEE 1 du statu quo (0,725% pre-garde -> 0,95% publiee), c'est-a-dire que la calibration etait portee par un clip. Les deux garde-fous sont desormais INERTES en statu quo, verifie par test. |

**Output gap initial** : le niveau **gap initial de -0,7%** est pose sur l'annee de base (`OUTPUT_GAP_INITIAL`). Sources : Gouvernement, RAA 2026, **Tableau n° 2 p. 20** (avis HCFP n° 2026-3 du 17/04/2026) : -0,7 en 2027 et 2028, -0,5 en 2029 ; variante documentee FMI, *Article IV* PR n° 26/255 du 22/07/2026, Table 1 : -0,4. La v4.0 partait de -1,5%, soit 2 a 4 fois plus bas que les deux estimations officielles, **sans aucune source dans le code**.

**Output gap en NIVEAU, rappel vers le potentiel (v0.6.7, B3 — arbitrage de Cyril, audit externe Codex 10/2026, bloc A constat 3)** — deux équations :

```
(1) définition : (1 + gap_t) = (1 + gap_{t−1}) × (1 + g_t) / (1 + g*_t)        [écart du PIB réel à son potentiel, BCE/OCDE/FMI/CE]
(2) croissance : g_t = g*_t − λ × gap_{t−1} + effets de demande (multiplicateurs, éviction, cicatrice),  λ = OUTPUT_GAP_RAPPEL = 0,2
```

Sens économique : le **potentiel** g* est la vitesse de croisière ; un écart de niveau est **rappelé** de 20 % par an (persistance 0,8), à la manière de l'équation d'output gap autorégressive des modèles semi-structurels de projection du FMI (forme de l'équation (1) de Berg, Karam & Laxton (2006), « Practical Model-Based Monetary Policy Analysis—A How-To Guide », IMF Working Paper 06/81 : `ygap_t = β_ld·ygap_{t+1} + β_lag·ygap_{t−1} − β_RRgap·(RR − RR*)_{t−1} + … + ε_t` ; ici `λ = 1 − β_lag`, sans terme prospectif ni canal de taux réel. Les auteurs (WP/06/80, vue d'ensemble) citent une fourchette β_lag de 0,5 à 0,9 ; la persistance retenue, 0,8 (λ = 0,2), est un CHOIX dans cette fourchette — aucune source précise ne publie 0,8 pour la France ni pour une équation annuelle d'économie avancée (recherche du 07/10/2026) —, arbitré puis confirmé le 07/10/2026 ; ce n'est pas une estimation France). Le rappel vit dans l'équation de CROISSANCE, pas dans la statistique de gap : c'est le PIB qui revient vers son potentiel, et (1) reste l'identité exacte de l'écart simulé. Conséquences assumées : les effets de NIVEAU des multiplicateurs deviennent transitoires (un choc de demande permanent n'est pas un gain de potentiel ; l'offre passe par les canaux dédiés : capital public `SUPPLY_EFFECTS`, offre de travail seniors), et un effet structurel d'emploi (coût du travail, Bozio-Wasmer) n'est rendu que transitoirement — limite déclarée.

**Ce que cela remplace** : jusqu'en v0.6.6, `gap(t) = 0,8 × gap(t−1) + 0,2 × (croissance − potentiel)`, moyenne mobile de l'écart de CROISSANCE qui effaçait chaque année 20 % d'un écart de niveau réel. La justification écrite ici (« avec l'identité comptable le gap ne se refermerait jamais en statu quo, croissance = potentielle ») avait une prémisse fausse : au statu quo, la croissance restait SOUS le potentiel, de la traînée de dette (−2,0 pts cumulés en 2035) et du bruit tiré (−0,56). L'identité pure seule (variante écartée) le montre : statu quo gap 2034 −2,68 %, dette 2035 164,17 %, régime « récession » permanent dès 2033, sortie du corridor de la mission. Le rappel referme l'écart ; le reclassement de la traînée de dette (ci-dessous) retire la cause de la dérive.

**Traînée de dette = effet d'OFFRE (v0.6.7, B3)** : `debt_drag × (dette/PIB − 0,9)` au-delà de 90 % (coefficient −0,005, compromis Reinhart-Rogoff −0,008 / Herndon-Ash-Pollin −0,003) abaisse désormais la croissance POTENTIELLE de l'année (quatrième terme de `croissance_potentielle_totale()`), que lisent la croissance, la loi d'Okun et l'output gap. La littérature la place sur la croissance de long terme : Kumar & Woo (2010), « Public Debt and Growth », IMF Working Paper 10/174, « the impact of high public debt on long-run economic growth » : +10 pts de dette initiale ↔ −0,2 pt de croissance annuelle du PIB réel par tête, « somewhat smaller in advanced economies », l'effet passant par « a slowdown in labor productivity growth mainly due to reduced investment and slower growth of capital stock » — un canal d'offre. Le coefficient du moteur (−0,05 pt par +10 pts au-delà de 90 %) est quatre fois plus prudent. Jusqu'en v0.6.6 elle frappait la seule croissance effective : Okun la lisait comme un choc de demande (+0,2-0,3 pt de chômage en fin d'horizon) et elle creusait l'écart de production. Verrouillé par `tests/test_output_gap_niveau_v067.py` (identité, rappel exact, au statu quo `g − g*` = rappel, la traînée n'ouvre ni gap ni chômage).

**Pass-through TVA (v4.0)** : one-shot, applique l'annee qui SUIT l'entree en vigueur de la mesure — la macro de l'annee t est calculee AVANT les mesures de t, l'impact TVA transmis vient donc de t-1. Pas de re-pass-through les annees suivantes : la persistance passe par l'inertie (rho = 0,5). **v0.6.7** : plus de seuil d'activation a 0,3 % du PIB de recettes de TVA — le pass-through (30 %, plafonne a 0,2 pt) vaut deja 0 en 0, le seuil le faisait naitre d'un coup a +0,09 pt (curseur TVA a 20,63 % : -0,30 pt de dette 2035, statu quo compris).

**Ce que mesure la variable `inflation` — une variable pour trois roles (v4.1)** : le moteur n'a qu'une variable la ou l'economie en distingue trois — (i) le **deflateur du PIB**, denominateur du ratio de dette ; (ii) l'**IPC**, pour le pouvoir d'achat ; (iii) l'**indice d'indexation** des prestations. L'arbitrage retenu est de la caler sur le **deflateur**, parce que l'INSEE tranche explicitement (blog sept. 2022 : « les ressources publiques etant plus ou moins fonction du PIB en valeur plutot que de la seule consommation, c'est plutot le deflateur du PIB qui importe pour apprecier le taux d'emprunt reel des administrations publiques »), et parce que la dette est la sortie principale du site. L'indexation **legale** des pensions suit, elle, l'IPC hors tabac. **Biais residuel declare : -0,15 pt/an** sur les roles (ii) et (iii) — ecart deflateur/prix a la consommation mesure a -0,1/-0,2 pt en regime normal, jusqu'a -0,6/-0,8 pt en annee de choc energetique. **Ce biais n'est PAS conservateur — il FLATTE les chiffres publies** (correction du 26/08/2026 ; cette page ecrivait l'inverse). Il minore la depense indexee, donc il AMELIORE le deficit et la dette — la sortie principale du site — et il minore la perte de pouvoir d'achat affichee, donc il embellit cet indicateur aussi. Les deux effets vont dans le meme sens, et c'est le sens favorable ; « conservateur » designerait l'erreur qui joue contre soi. **Magnitude, mesuree par contre-epreuve** (depense primaire indexee sur l'IPC — l'indice que l'indexation legale suit — tout le reste identique) : deficit 2030 -6,40 -> -6,86, deficit 2035 -10,70 -> -11,95 ; dette 2030 129,65 -> 130,93, **dette 2035 159,35 -> 164,85, soit 5,5 points de PIB** (contre-epreuve mesuree le 26/08/2026 sur l'etat v0.6.1 ; l'ordre de grandeur — le seul message ici — est inchange par la passe v0.6.3, dont les valeurs étaient 129,35 / 158,85 / -10,68 ; v0.6.7, impulsions levier par levier : 129,91 / 160,69 / -10,99). Ce n'est pas un residu de second ordre. Il n'est pas corrige ici : tous les handlers consomment `inflation`, scinder en trois variables est un changement d'architecture instruit separement — ce qui est corrige, c'est ce qu'on en dit.

**Distinction importante — ne pas confondre** :
- Le **point fixe** (1,6%, `INFLATION_STRUCTURELLE`) est l'inflation vers laquelle le regime converge quand output gap = 0.
- La **cible BCE** (2,0%, `BCE_CIBLE_INFLATION`) est le **seuil du garde-fou de surchauffe** : au-dessus, la banque centrale freine (blend 50/50). Ce n'est PLUS un point de convergence forcee (mecanique pre-v4.0).
- L'output gap negatif tire le deflateur effectif vers **~1,3-1,6%**, sous le point fixe. Corridor officiel vise : 1,3 / 1,6 / 1,6 / 1,5 / 1,5% (RAA 2026 Tableau n° 2 pour 2026-2029, mission IGF 07/2026 pour 2030) ; **realise du moteur sur le scenario de reference `plf_2026`** : 1,34 / 1,42 / 1,45 / 1,46 / 1,46%, ecart annuel <= 0,18 pt, **moyenne 2026-2030 = 1,426%** (fourchette du dossier : 1,40-1,60). Le statu quo NU, lui, rend 1,34 / 1,44 / 1,49 / 1,51 / 1,53%. (Re-mesure 07/10/2026, v0.6.7 : le bruit tire graine 42 soutenait le deflateur, 1,498% de moyenne avec lui.) Ces deux series ne sont pas interchangeables : la page en publiait une troisieme, celle du scenario de reference d'AVANT le lot 9, jusqu'au 26/08/2026. (Recale 30/08/2026, v0.6.3 : graine 2025 aux comptes definitifs INSEE — deflateur 2025 realise 1,1 % — et inertie `rho` 0,50 -> 0,33, milieu de la fourchette declaree, encadre par la direction Banque de France, Billet n° 335.)
- **Marge a declarer** : la moyenne du scenario servi est a 0,026 pt du plancher de la fourchette (0,098 avec le bruit tire, 0,014 avant le recalage v0.6.3), et la sensibilite du sentier au parametre d'inertie `rho` vaut 0,056 pt entre 0,25 et 0,50 depuis l'output gap en niveau (v0.6.7 ; 0,046 au 30/08/2026, 0,062 avant) — AU-DESSUS du < 0,05 demande par le brief, la fenetre 2026-2030 etant desormais transitoire. La conformite tient pour `rho` dans [0,20 ; 0,45] ; a 0,50, borne haute de la fourchette, la moyenne tombe a 1,384 %, sous le plancher : echec attendu DECLARE (`tests/test_phillips_v061.py`), marge que le tirage aleatoire tenait. En sens inverse, le corridor de DETTE est a 1,85 pt (2030) pour une tolerance portee de 1,6 a 2,0 (v0.6.7) : le PIB nominal etant desormais honnete, l'ecart revele le residu (b) que le PIB trop bas compensait — declare ici plutot que tu (chiffres complets : « Calibration Baseline Validee »).

**Sources** : BCE Survey of Professional Forecasters T3 2026 ; Gouvernement, RAA 2026 du PSMT 2025-2029 (Tableau n° 2, note 6), avis HCFP n° 2026-3 ; INSEE, blog « Inflation : les deflateurs en comptabilite nationale » (sept. 2022) ; Banque de France, *Rue de la Banque* n° 56 (fev. 2018) et Billet de blog n° 335 (dec. 2023) ; BCE, ECB Working Paper n° 3133 (oct. 2025) ; FMI, *France: 2026 Article IV Consultation*, PR n° 26/255 ; BCE Strategy Review 2021 (cible symetrique 2%).

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

**Rendements decroissants** : Le bonus est calcule via `log2(1 + |ecart au defaut|)` (la page ecrivait `ln` jusqu'au 07/10/2026 ; le code a toujours calcule `log2`), ce qui attenue les gains marginaux a mesure que l'investissement augmente. **v0.6.7** : plus de seuil d'activation a 100 M EUR d'ecart — le bonus, nul en 0, naissait d'un coup a `coeff x log2(1,1)` (transition ecologique a 0,1 Md EUR : -0,80 pt de dette 2035 sur « Budget 2026 (vote) »).

**Cap total** : +0,20 pt maximum (et plancher symetrique -0,20 pt, v0.6.0). Le potentiel total peut depasser d'au plus 0,20 pt son niveau sans effet d'offre (tendanciel 1,228 % depuis la v0.6.7, net de la traînee de dette).

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

**Distinction cruciale pour le pouvoir d'achat (PA) :**

**Effets NIVEAU (ONE-TIME)** — Appliques UNIQUEMENT annee de mise en oeuvre via `_is_first_year_change()`.
Sur l'indice PA base 100, un effet de niveau modifie la consommation/revenu disponible UNE FOIS,
puis l'indice evolue selon la trajectoire macro (croissance réelle, v0.6.7 — cf. § Indicateurs Macroeconomiques). Cumul multiplicatif sur
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
  (v0.6.7) : `écart = masse nominale minima_sociaux de l'année × [1 − Π (1 − δ × max(π_s, 0))]`,
  δ = 1 − taux_indexation, produit sur les revalorisations écoulées (2026 → année, dix au plus),
  chacune à l'inflation de SON année. Jusqu'à v0.6.6, `(1 − δ × π_t)^k` réécrivait tout
  l'écart passé à l'inflation du jour (gel total : −1,8 Md EUR en 2027 à 2 %, 0 en 2028
  si l'inflation tombait à 0 ; audit externe Codex, 10/2026). À inflation constante, les
  deux formules coïncident. Les deux limites signalées au lot 2 sont levées au lot 3C, par
  alignement sur la convention des pensions : l'assiette n'est plus 90 Md EUR figés en euros 2025
  mais la masse nominale de la catégorie `minima_sociaux` (90 Md EUR en 2025), et la première
  revalorisation est celle de 2026 (un gel voté pour 2026 rapporte en 2026)
- Retraites (indexation) : même forme que les prestations depuis v0.6.7 — `0,86 × masse
  nominale des pensions × [1 − Π (1 − δ × max(π_s, 0))]`, sept revalorisations au plus
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
> la plus lourde des trois, jamais auditee). Leur traitement releve du
> chantier v0.7 : la valeur de `GINI_IMPACT_SCALE` n'est pas re-derivable tant
> que les coefficients ne sont pas tous sources.

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
- ISF climatique : Max 18 Md EUR
- Taxe superprofits : Max 20 Md EUR

### Indicateurs Macroeconomiques

**Coefficient de Gini :**
- Baseline 2025 : ~0,290
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

**Assemblage Gini (v0.4.0 — realisme empirique).** Les sensibilites par mesure
(sections par levier ci-dessus) ne sont plus sommees telles quelles : leur somme
brute sur-reagissait d'un facteur ~4 par rapport aux microsimulations de
reference (IPP/OFCE 2022 : un programme redistributif de 5-10 % du PIB deplace
le Gini de −0,02 a −0,03 sur un quinquennat) et arrivait en quasi-totalite des
la premiere annee, jusqu'a saturer le plancher 0,25. Trois etages, appliques au
point unique d'agregation (`engine/orchestrator.py`, constantes `constants.py`) :

1. **Rescale** (`GINI_IMPACT_SCALE = 0,22`) : la somme des impacts alimente une
   *cible* cumulee — un seul facteur global, les ecarts relatifs entre
   programmes sont preserves.
2. **Inertie** (`GINI_CONVERGENCE_RATE = 0,35`) : le Gini courant converge vers
   la cible a ~35 %/an (lag du 1er ordre). Justification : la serie INSEE
   sur 25 ans ne montre jamais |ΔGini| > ~0,01/an, meme lors des reformes
   fiscales majeures (ISF→PFU 2018 : ~±0,005).
3. **Plancher asymptotique** (`GINI_SOFT_FLOOR = 0,25`) : les pas a la baisse
   sont amortis proportionnellement a la distance au plancher (rendements
   decroissants de la redistribution a l'approche des niveaux les plus
   egalitaires de l'UE — seuls la Slovaquie, la Tchequie, la Slovenie et la
   Belgique sont sous 25, Eurostat 2024). Le clip dur [0,25 ; 0,40] subsiste
   en filet anti-flottant mais ne peut plus etre atteint.

Resultat sur les programmes 2027 : LFI 2030 ≈ 0,269, PS ≈ 0,276, RN ≈ 0,285
(au lieu d'une co-saturation LFI/PS a 0,250) — ordres de grandeur coherents
avec les evaluations IPP/OFCE, vitesse compatible avec l'historique INSEE,
classement inchange. Proprietes verrouillees par tests dedies.

**Indice de pouvoir d'achat (synthétique, non comparable au RDB INSEE) :**
- Baseline 2025 : 100 (indice)
- Positif = Hausse pouvoir achat
- Negatif = Baisse pouvoir achat
- **Formule exacte (v0.6.7)** — c'est tout ce que l'indice contient :

  ```
  PA(2025) = 100
  PA(t)    = PA(t−1) × (1 + borne(g(t) + micro(t)))
  micro(t) = Σ_mesures impacts['pouvoir_achat'](t) × (1 en 2026, 0,5 ensuite)
  borne    = ± PA_VARIATION_ANNUELLE_MAX (filet, ne mord sur aucun scénario publié)
  ```

  `g(t)` est la croissance RÉELLE du PIB agrégé — pas par tête, pas le revenu disponible ;
  `micro(t)` est la somme des effets forfaitaires des mesures, atténués de moitié après
  l'an 1 (adaptation comportementale). **Ce n'est pas le RDB réel par unité de
  consommation de l'INSEE** (historique +0,3 à +0,8 %/an hors crises) : au statu quo,
  l'indice croît comme le PIB réel (108,7 en 2035). Il se lit en ÉCART entre programmes,
  pas en niveau. Refonte en RDB réel par UC : v0.6.8.
- **Corrigé en v0.6.7 (audit externe Codex, 10/2026)** : la v0.6.6 calculait
  `g − π + 0,54 × π` — l'inflation retranchée d'une croissance déjà réelle (le nominal
  porte le déflateur), puis rendue à 54 % par une « protection d'indexation »
  (`INDEXATION_BASELINE_RATIO`, supprimée) qui n'existait que pour compenser cette
  soustraction ; le commentaire du code parlait de « PIB/tête » sans division par la
  population. Effet : +2,0 à +3,4 pt d'indice en 2029 pour les dix scénarios publiés,
  presque uniforme (un peu plus pour les programmes à inflation plus haute, pénalisés
  deux fois auparavant).

**Competitivite :**
- Baseline 2025 : 100 (indice)
- Positif = Amelioration competitivite entreprises
- Negatif = Degradation competitivite

### Calibration Baseline Validee (v0.6.0)

Reference de calibration : mission Jaravel/Ragot/Tavernier/Valla (IGF, juillet
2026, commandee par les ministres Lescure et Amiel) — tendanciel a politique
inchangee, Tableaux 3/4/5/6. Corridor verrouille en CI
(`tests/test_calibration_mission_v060.py`) sur le scenario « Budget 2026
vote » : deficit -5,0 -> -6,76 %, dette 118,4 -> 130,5 %, charge de la dette
78 -> 124 Md EUR, taux apparent 2,2 -> 3,1 % (2026-2030).

**Valeurs réelles du scénario de référence face à la mission** (v0.6.7, lot 3b — tendanciel dérivé 1,228 %, TOL_DETTE portée de 1,6 à 2,0 pt ; HCFP : dette 2030 ≈ 129,5 %) :

| Année | Dette moteur | Dette mission | Écart | Déficit moteur | Déficit mission | Niveau PIB nominal vs mission |
|---|---|---|---|---|---|---|
| 2026 | 117,84 | 118,4 | −0,56 | −5,17 | −5,00 | 0,37 % |
| 2027 | 120,22 | 121,4 | −1,18 | −5,35 | −5,88 | 0,24 % |
| 2028 | 122,78 | 124,2 | −1,42 | −5,58 | −6,21 | 0,01 % |
| 2029 | 125,57 | 127,3 | −1,73 | −5,85 | −6,57 | −0,05 % |
| 2030 | 128,65 | 130,5 | −1,85 | −6,20 | −6,76 | −0,12 % |

Lecture : le PIB nominal est désormais honnête (niveau 2030 à −0,12 % de la mission, tolérance ±0,6) ; l'écart de dette (−1,85 pt en 2030) révèle un solde primaire du statu quo légèrement trop favorable — le résidu (b) décrit dans `tests/test_calibration_mission_v060.py`, que le PIB nominal trop bas compensait jusqu'ici. Chantier ouvert v0.6.8 (bloc dépenses). Statu quo NU (aucune mesure) : dette 2030 129,12 %, 2035 151,17 %.

| Indicateur | Valeur | Horizon |
|------------|--------|---------|
| Croissance reelle depenses primaires | +0,8 a +1,4%/an CHAQUE annee | Tendanciel officiel (mission IGF : Ondam +3,5 % courants, retraites 354->401 Md EUR) |
| Elasticite recettes / PIB nominal | 1,00 | Ratio recettes/PIB stable par construction (~52,2%) |
| Deficit | **-5,17 %** PIB | 2026, scenario de reference `plf_2026` (mission : -5,00 par hypothese ; statu quo NU : -5,30) |
| Dette | **128,65 %** PIB | 2030, scenario de reference (mission : 130,5 ; ecart -1,85 pt depuis le re-ancrage DERIVE du potentiel v0.6.7, qui rend le PIB nominal honnete et revele le residu (b) — +0,05 sans bruit avant re-ancrage, -1,98 avec le bruit ; la v4.0 affichait +2,4 pt) |
| Dette | **129,12 %** PIB | 2030, statu quo NU (aucune mesure) — l'objet de calibration, servi nulle part |
| Dette | **151,17 %** PIB | 2035, statu quo NU (taux honnetes v0.6.0 : marginal 3,47 % @ 117,6 % AFT, boule de neige reelle r > g des 2029 ; scenario de reference : 149,77) |
| Deficit | **-9,05 %** PIB | 2035, statu quo NU (charge d'interets ~7 % du PIB ; scenario de reference : -8,69) |
| Croissance potentielle | tendanciel 1,228 % ; potentiel TOTAL du statu quo 1,1% a la dette 2025 | Derive (v0.6.7) : potentiel officiel 1,1 % (mission IGF 07/2026, 1,2/1,2/1,0/1,0) + traînée de la dette heritee 0,128 pt (-0,005 x (115,6 - 90) %) — la traînee supplementaire due a la dette qui monte ensuite reste un effet du modele |
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

Règle écrite le 07/10/2026. Elle est appliquée à ce jour à RN, Horizons et LR
(re-encodage du 07/10/2026), ainsi qu'à Renaissance et Horizons (re-encodage du
30/08/2026). PS, LFI et Écologistes seront passés au crible à leur prochain
re-sourcing (17/10, 6-7/11 et 10-13/12/2026).

Référence commune : le **droit en vigueur (budget 2026 voté)**, c'est-à-dire les
paramètres du scénario « Budget 2026 (voté) » (`plf_2026`). Ci-dessous, « droit en
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
5. **Exception : mesure annoncée mais non chiffrée.** Quand le candidat annonce
   une mesure sans la chiffrer, elle est encodée sur des bornes de tiers
   documentées dans sa fiche. Exemple : le « droit au brut » de Renaissance.
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
`tests/test_reencodage_v066.py`.

---

## Limites et Precautions

1. **Incertitude parametrique** : Les elasticites sont des estimations moyennes
2. **Delais de transmission** : Certains effets mettent 5-10 ans a se materialiser
3. **Interactions** : Les mesures peuvent se renforcer ou s'annuler
4. **Contexte macroeconomique** : Hypotheses de croissance mondiale, taux directeurs BCE
5. **Perimetre comptable** : Differences possibles avec chiffres officiels
6. **Stochasticite** : Aucune. Le moteur est deterministe depuis la v0.6.7 : les tirages N(0 ; 0,3 %) sur la croissance et N(0 ; 0,05 %) sur l'inflation (graine 42, les memes nombres pour tous les scenarios) ont ete retires. Avec l'output gap en niveau, le premier devenait un choc de demande persistant (+0,6 % de PIB en 2029) qui sortait a lui seul le scenario de reference du corridor de la mission (dette 2029 -2,26 pt ; sans lui -0,39). Une incertitude se publie en variante, pas en tirage cache dans la trajectoire centrale. Verrouille par `tests/test_deterministe_v067.py` (aucun acces au generateur aleatoire, sur les 44 cas).

---

## Neutralite : ce que la version v0.6.1 du moteur deplace, EN AGREGE

Chaque correction de cette version porte, dans son commit, le sens dans lequel
elle joue. **Ce paragraphe dit ce que la SOMME produit** — parce qu'une suite de
corrections individuellement justifiees peut avoir un sens agrege qu'aucune
d'elles n'annonce, et parce que le scenario de reference « Budget 2026 (vote) »
est le comparateur implicite de tous les programmes de parti.

Ecart de dette 2035 de chaque programme AU scenario de reference, en points de
PIB (un ecart plus grand = programme plus couteux que la politique votee) :

| Scenario | Ecart moteur v0.6.0 | Ecart moteur v0.6.1 | Ecart au 30/08/2026 (re-encodage scenarios) | Ecart moteur v0.6.3 | Ecart moteur v0.6.4 | Ecart au 07/10/2026 (re-encodage scenarios) |
|---|---|---|---|---|---|---|
| `rn_2027` | +3,4 | +10,9 | +10,6 | +7,0 | +7,1 | +6,7 |
| `lfi_2027` | +13,2 | +25,0 | +25,0 | +17,8 | +17,7 | +17,7 |
| `renaissance_2027` | -7,1 | -4,9 | -1,5 | -0,9 | -0,9 | -0,9 |
| `horizons_2027` | -10,8 | -7,0 | -1,3 | -0,8 | -0,8 | -8,8 |
| `lr_2027` | -13,3 | -6,3 | -4,0 | -3,3 | -3,3 | +8,0 |
| `ps_2027` | +0,1 | +8,4 | +8,4 | +3,8 | +3,7 | +3,7 |
| `ecologistes_2027` | — | — | -2,2 | -5,8 | -5,8 | -5,8 |
| `im_rabot_2029` | -33,6 | -26,7 | -27,0 | -26,8 | -26,8 | -26,8 |
| `im_competitivite_2029` | -36,4 | -24,2 | -24,7 | -25,1 | -25,0 | -25,0 |

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

### L2. Profil INVEST avec pic Y2 (et non Y3-Y4)

Le profil temporel des multiplicateurs d'investissement public est `(0.45, 0.65, 0.45, 0.25, 0.12, 0.06)` avec pic Y2. **Justification** : Bom-Ligthart 2014 (meta-analyse 578 estimations) trouve plutot un pic Y3-Y4 pour les capital stock models (TGV, nucleaire, infrastructures lourdes), mais Ramey 2019 montre Y1-Y2 pour les flow models (projets pre-prets). La France 2030 et la LPM 2024-2030 sont majoritairement des projets pre-prets qui decaissent vite, ce qui justifie le choix Y2. Choix dans la fourchette basse defendable.

### L3. Loi d'Okun avec beta = -0.35 (mediane fourchette OFCE)

Le coefficient d'Okun France est fixe a -0.35. **Justification** : la fourchette OFCE/INSEE est large [-0.30, -0.55] selon la periode et la specification. Choisir le median -0.35 evite (a) le pessimisme de -0.55 (qui ferait exploser le chomage en recession), (b) l'optimisme de -0.30 (qui sous-estimerait la sensibilite emploi). Choix de prudence pedagogique.

### L4. Elasticite fiscale unitaire uniforme (pas de regime conjoncturel)

L'elasticite des prelevements obligatoires au PIB nominal est `ELASTICITE_PO_PIB = 1.0`, uniforme sur tout le cycle (refonte v4.0). **Justification** : HCFP note 2023-01 (series 2002-2022) — elasticite observee 1,01-1,07, non significativement differente de 1 ; convention CBO/OBR/DG Tresor a politique inchangee. L'ancienne elasticite differenciee par regime de croissance (1,00/1,06/1,08/1,12) et l'erosion fiscale forfaitaire (0,2%/an, qui rendait l'elasticite de facto ~0,93) ont ete supprimees : l'asymetrie conjoncturelle joue taxe par taxe (IS, plus-values), pas en global, et aucune institution ne modelise une erosion globale des recettes. Une erosion reelle se modelise PAR TAXE, comme mesure explicite. Consequence : en statu quo, le ratio recettes/PIB est stable par construction (~52,2%) — c'est la definition d'un scenario a politique inchangee.

### L5. Plus de plafond de taille sur l'impulsion keynésienne (v0.6.7)

Jusqu'en v0.6.6, le niveau d'effort multiplié était plafonné à 2 % du PIB (appliqué en fait au programme entier, pas « par mesure » comme l'écrivait cette page). **Retiré en v0.6.7.** Raisons : (1) la littérature citée ne porte pas de saturation — Guajardo, Leigh et Pescatori (2014) estiment des effets LINÉAIRES dans la taille de l'ajustement (la médiane de 1 % du PIB décrit l'échantillon, pas une borne de l'effet), Auerbach et Gorodnichenko (2012) documentent une non-linéarité d'ÉTAT (récession/expansion, déjà portée par l'ajustement ×1,15/×0,85, à transition continue depuis le lot 3b), pas de taille, et Blanchard et Leigh (2013) trouvent des effets PLUS forts pour les grandes consolidations, jamais plus faibles ; (2) un plafond tronque le coût — ou le gain — des seuls programmes les plus brutaux, ce qui avantage par construction ceux qui concentrent leur effort ; (3) la stabilité ne dépend pas de lui : l'effet est une convolution finie (6 ans) des impulsions annuelles, bornée par k_max × 1,15 × 1,3 × Σ |impulsions des 6 dernières années|, sous le clip de croissance [−3,5 % ; +2,5 %]. Seul scénario publié touché : `im_rabot_2029`, dont la coupe atteint 5,2 % du PIB (3,1 % la première année), désormais multipliée en entier. Le plafond cumulatif de 10 % du PIB sur les MESURES (budget, FMI 2010) est inchangé.

### L6. Modele a agent representatif (pas de microsimulation par decile)

Les coefficients Gini, pouvoir d'achat et competitivite sont calcules au niveau macro avec des coefficients calibres sur parts de budget INSEE (Budget des Familles 2017/2022), pas via une microsimulation par decile. **Justification** : architecture standard de tous les modeles macro reduits (RA-DSGE, MESANGE, e-mod). Pour la distribution par decile, complement OpenFisca-France (INRIA) et TAXIPP (IPP) recommandes. Cette limitation est partagee par tous les outils macro grand public.

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
par aucune institution**. L'IGAS 2024 (Bras & Monasse) dit pourquoi :
« en l'absence d'une evaluation structuree en France de l'efficacite et de
l'efficience des actions de PPS ». Ce 0,50 est donc **un choix de
modelisation**, borne par la litterature internationale (Cohen 2008 : 19 % des
interventions preventives sont cost-saving ; ACE-Prevention 2010 : ratio 2,4
pour les 21 mesures **dominantes** sur 150, vie entiere, selection optimale ;
OCDE 2019 ch. 6 : 0,012 Md EUR/pays/an pour la meilleure intervention), **et
il ne sera jamais presente comme source**. Ce que les sources etablissent, et
que le moteur respecte, c'est seulement que le taux est **inferieur a 1** et
qu'il est **differe**.

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

**M3. Deux termes d'effort budgetaire conserves — dette connue, declaree.** Le
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
malgre l'ajout du canal emploi. La justification : l'heterogeneite est forte et
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

**M23. ASU : un Gini majorant plutot qu'une conversion inventee.** Le choix :
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

**M29. Le facteur d'echelle global n'est pas re-derive.** Le choix :
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
