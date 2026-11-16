# Changelog — moteur france-budget-simulateur

**BLOQUANT AVANT PUBLICATION : retirer l'échec attendu de la garde du pouvoir d'achat 2029 et mettre à jour les valeurs figées après relecture.**

Versions publiées : tags git (`vX.Y.Z`). Ce fichier commence à la v0.6.8 ;
l'historique antérieur est décrit dans les messages de tags et dans
`docs/METHODOLOGIE.md` (encadrés « Corrigé en v0.6.x »).

## [non publiée — proposée] — paramètres du lot 3 : valeurs officielles

**Statut** : proposée, non publiée, sans numéro de version. Release de PARAMÈTRES, distincte du bloc « défauts du
lot 3 » ci-dessous, qu'elle suppose appliqué : aucune équation ne change ici.

- **Impôts sur le patrimoine aux comptes nationaux 2025.** Bases du curseur « Fiscalité du patrimoine » et IFI que
  remplace l'ISF : Insee, comptes nationaux annuels base 2020 publiés le 29/05/2026, tableau 3.217 « Principaux
  impôts par catégorie », 2025 (rouvert) — IFI 2,714 Md€ (autres impôts courants, D59), droits de succession 16,070
  (impôts en capital, D91), taxe foncière 44,179 (impôts divers sur la production, D292 ; dont ménages 27,015),
  62,963 Md€ au total, contre 2 + 15 + 36 = 53 (« DGFiP 2024 », référence non retrouvée). Périmètre inchangé : le
  curseur fait varier les successions, pas les donations (4,982 Md€). Même cadre comptable que la référence du
  moteur (comptes des administrations publiques). Deux valeurs de cadres différents ramenées au même tableau :
  `DMTG_2025_MD` (successions et donations, 21,052 Md€ : borne basse de `droits_succession`, au lieu de 21,2 de
  l'annexe Voies et moyens 2027) et `DMTG_SUCCESSIONS_2025_MD` (successions seules, base du curseur, au lieu de 15
  d'une note antérieure à 2021) ; part ménages de la taxe foncière du même tableau et de la même année que sa base
  (27,015 / 44,179, au lieu de 26,1 / 42,9 de 2024 appliqué à 36). Infobulles du registre public mises à jour (IFI
  2,7 Md€, bloc 63,0 Md€, repère des droits de succession) ; le chiffre de Gini de l'infobulle du patrimoine est
  retiré (la passe sur les inégalités les porte). Coefficients de Gini et de compétitivité par Md€ inchangés.
  Golden master isolé : bougent exactement les cas qui portent l'ISF ou le patrimoine (scénario qui pose l'ISF,
  deux modes ; deux mini-scénarios) ; 60 sur 64 identiques au bit. Effet (mode cadre, 2032, pleine précision, pile
  assemblée), scénario qui pose l'ISF : dette +0,04 point, déficit −0,02 point de PIB (IFI remplacé de 2 à 2,714
  Md€). Chiffre publié de l'ISF en 2030 (mode cadre) : +9,11 → +8,31 Md€, garde de test. Re-déclaré : le Gini du
  curseur du patrimoine (méthode du lot 4, seul l'IFI compte) se lit sur l'IFI de 2025 (constante) ; chiffre publié
  de l'effet prix des rémunérations publiques recalculé par sa garde (dette 2032 −1,405 au lieu de −1,404 point).
- **Les donations entrent dans le curseur « Fiscalité du patrimoine »** (changement de périmètre, arbitrage du
  mainteneur). Le curseur faisait varier l'IFI, les droits de succession et la taxe foncière ; il fait varier aussi
  les droits de donation (4,982 Md€ en 2025, même tableau Insee, D91), comme le levier `droits_succession`, qui
  porte sur les deux : base « successions et donations » = `DMTG_2025_MD` (21,052 Md€). Ce n'est pas une valeur
  sourcée mais un choix de périmètre. Bloc 62,963 → 67,945 Md€ en 2025 (±30 % = ±20,4 Md€ au lieu de ±18,9). Aucun
  scénario publié ne pose ce curseur ; golden master isolé : seul le mini-scénario du curseur bouge, 63 sur 64
  identiques au bit. Enjeu pour un visiteur (loi votée, mode cadre, +30 %) : 21,8 Md€ de recette en 2028 au lieu de
  20,2 ; dette 2032 −0,11 point, déficit +0,05 point de PIB.
- **Rabot uniforme : défense au périmètre de la note source.** Part du PIB de la défense exclue du rabot
  (`MONTAIGNE_DEFENSE_PART_PIB`, mécanisme du bloc « défauts du lot 3 ») : 0 (seule la catégorie « équipements »,
  25 Md€ en 2025) → 0,027, 2,7 % du PIB, pensions comprises (Institut Montaigne, « Budget base zéro », novembre 2025,
  p. 81 et note 113, rouverte). Avec le PIB du moteur, 86 Md€ en 2029 (91 selon la note, dont le PIB est plus élevé).
  Convention déclarée : la part de 2,7 % est gardée chaque année du rabot, 2028 compris (la note la fixe pour 2029).
  Infobulle de l'exclusion mise à jour. Golden master isolé : bougent exactement le scénario de référence de la note
  (deux modes) et le mini-scénario du rabot ; 61 sur 64 identiques au bit. Effet (mode cadre, pleine précision, pile
  assemblée) : coupe 2029 du scénario de la note 143,97 → 139,47 Md€ ; 2032 : dette +0,04 point, déficit −0,06 point
  de PIB ; indice d'inégalités −0,0002 (la part coupée entre dans le montant de la méthode du lot 4). Re-déclarés :
  coupe de dotation du rabot (règle du lot 5c) et effet attendu sur l'indice d'inégalités (lot 4) à la part coupée ;
  chiffres publiés de l'encadré du lot 5c recalculés par sa garde.

## [non publiée — proposée] — défauts du lot 3 : gardes d'entrée, double compte, commentaires

**Statut** : proposée, non publiée, sans numéro de version. Commits de CORRECTION (gardes, formules), distincts
du bloc « paramètres du lot 3 » ; ils supposent appliqués les blocs des lots 1 et 5 ci-dessous.

- **Gardes d'entrée : booléens et nombres.** Deux entrées passaient la porte des valeurs sans trace
  (`report.valid: true`) : `fonction_publique.effectifs: true` (un booléen vaut 1 en Python : un poste créé)
  et `chomage_alloc.degressivite: 5` (le paramètre est déclaré booléen, le handler le lit par sa vérité : 5,
  0,5 ou −1 activaient la dégressivité). Désormais : sur une quantité bornée (`PARAM_DOMAINS`, intensités), un
  booléen fait échouer le levier comme une valeur non numérique (effet nul, `report.valid: false` ; 422 en
  strict) ; sur un interrupteur 0/1 (registre public : `toggle`, ou domaine 0 à 1 au pas de 1), il reste lu
  comme 0/1 ; un paramètre déclaré booléen n'admet que `true`, `false`, 0 et 1 — une autre valeur numérique est
  retirée (défaut du levier) avec une correction, refusée en strict. Listes dérivées du registre public
  (`PARAM_INTERRUPTEURS`, `PARAM_BOOLEENS`). Les lecteurs latéraux (âge de départ des canaux seniors, point
  d'indice lu par le SMIC, ISF lu par l'impôt plancher, IS lu par les bénéfices récupérés, effet d'offre,
  exclusions mutuelles) voient un booléen refusé au neutre, comme une chaîne ; avant, l'effet d'offre levait et
  s'éteignait pour TOUS les leviers. Test rouge puis vert : `tests/test_gardes_booleens.py` (nouveau ; propriété
  sur chaque paramètre borné du registre ; un booléen donne la trajectoire d'une chaîne, lecteurs latéraux
  compris ; les deux cas de bout en bout). Re-déclarés : `csg.taux = True` est refusé comme booléen et non plus
  comme hors domaine (`tests/test_param_domains_guard.py`) ; l'âge de départ booléen n'est plus ramené à 60 ans
  par les canaux macro (`tests/test_cloture_revue_lot3.py`). Sorties identiques au bit, en pleine précision, sur
  les 64 cas du golden master (dix scénarios publiés des deux modes, mini-scénarios, statu quo). Limite
  déclarée : un levier refusé compte pour zéro en entier, y compris la valeur de droit en vigueur qu'il porte en
  mode cadre (exemple : `fonction_publique.effectifs: true` sur la loi de finances votée perd les suppressions de
  postes du droit en vigueur, alors qu'une clé absente les garde). C'est le traitement antérieur d'une chaîne de
  caractères, que les gardes étendent aux booléens.
- **Sources de l'ISF dans le code** (aucun calcul ne change). Les commentaires de
  `handlers/fiscalite_menages.py` attribuaient le taux d'évasion de 15 % et le plafond de 18 Md€ à l'« EU Tax
  Observatory 2024 », dont le rapport ne contient aucun des deux. Ils disent désormais ce que la documentation
  publique dit déjà : 15 % est une convention de Saez et Zucman (2019, *Brookings Papers on Economic Activity*,
  tableau 2 p. 461, scénario « contrôle fort » d'un impôt américain à assiette complète), pas une mesure
  française ; 18 Md€ est un plafond sans source, qui ne mord jamais (recette nette maximale ≈ 10,07 Md€). Garde :
  `tests/test_isf_sources_commentaires.py` (nouveau ; rouge avant). Sorties identiques au bit.
- **IFI compté une seule fois** quand l'ISF et le curseur « Fiscalité du patrimoine » sont combinés. L'ISF
  d'intensité i remplace la part i de l'IFI (courbe continue v0.6.7) ; le bloc du patrimoine faisait pourtant
  varier l'IFI entier : pour ISF 1 et patrimoine +30 %, 0,6 Md€ par an d'un impôt supprimé, dans la recette, le
  canal des ménages, le Gini et la compétitivité, avec `report.valid: true` (aucune règle d'exclusion ne couvrait
  la paire). Le bloc ne fait plus varier que l'IFI encore en vigueur, (1 − i) × IFI, i lu comme l'impôt plancher
  (règle Z) ; la part en vigueur entre dans les paramètres suivis des effets ponctuels. Test rouge puis vert :
  `tests/test_ifi_double_compte.py` (nouveau ; levier inchangé sans ISF, IFI au prorata de ce qui en reste,
  mêmes euros dans les quatre canaux, cas de l'audit de bout en bout). Golden master isolé : aucun cas ne
  combine les deux leviers, 64 sur 64 identiques au bit.
- **Cotisations salariales : mode « montant en Md€ »** (extension du contrat, aucune équation ne change pour le mode
  en points). `cotisations_salariales.montant_md` : Md€ par an rendus aux salariés, constants en euros courants, de 0
  à 138,217 Md€ (masse 2025, Insee) ; mode exclusif (avec lui, `baisse_points` n'est pas lu : refus en strict,
  correction sinon) ; éligible aux calendriers des montants (rampe depuis 0, valeurs annuelles) ; même coefficient de
  Gini par Md€. Pour les programmes qui écrivent des milliards : leur conversion en points n'était fidèle que tant que
  le point restait figé en euros 2025. Test rouge puis vert : `tests/test_cotisations_montant_md.py` (nouveau). Module
  généré des noms (`_noms_parametres.py`) et registre public régénérés. Golden master isolé : 64 cas sur 64
  identiques au bit (aucun encodage publié n'utilise encore le mode). Re-déclarés : modes exclusifs dérivés (un
  couple de plus), 82 paramètres bornés au lieu de 81, profils éligibles (un montant de plus).
- **Rabot uniforme : assiette en euros de l'année.** La coupe s'appliquait aux dépenses en volume (euros 2025) :
  un taux de 8 % ne valait qu'environ 7,4 % des dépenses de l'année en 2032. Désormais masses nominales de l'année
  (`masse_categorie_nominale`), la méthode de la note source (Institut Montaigne, « Budget base zéro », novembre 2025,
  annexe 4, p. 141 : « tendanciel en volume ajusté par le déflateur du PIB ») ; AAH à la même assiette. Équation
  seule : le périmètre des exclusions ne change pas ici. Test rouge puis vert : `tests/test_rabot_assiette_note.py`
  (nouveau). Golden master isolé : bougent exactement les cas où le rabot est non nul — le scénario de référence de
  la note (deux modes) et le mini-scénario du levier ; 61 sur 64 identiques au bit. Effet (mode cadre, pile
  assemblée) : coupe 2029 du scénario de la note 136,46 → 143,97 Md€ ; dette 2032 +0,01 point, déficit +0,13 point
  de PIB. Re-déclarés : les tests du canal ménages du rabot lisent les masses nominales ; la coupe de dotation du
  rabot (règle du lot 5c) est recalculée sur la masse nominale, et ses chiffres publiés mis à jour.
- **Rabot uniforme : exclusion de la défense au-delà des équipements** (équation, valeur neutre ; relecture adverse :
  mécanisme séparé de sa valeur). La défense exclue vaut une part du PIB de l'année (`MONTAIGNE_DEFENSE_PART_PIB`),
  dont la catégorie « équipements » (exclue en entier) ; le reste est retiré au prorata des autres catégories, faute
  de catégorie « défense » hors équipement (convention déclarée : composition sociale de la coupe inchangée) ; AAH à
  la même part coupée. Indice d'inégalités (méthode unique du lot 4, coefficient × montant d'année pleine de
  l'année source) : le montant des prestations en espèces coupées porte la même part coupée, lue sur les masses et
  le PIB de 2025 (composition des deux règles). Valeur neutre 0 : seule la catégorie « équipements » est exclue,
  comme avant ; la valeur de la note est posée par la release de paramètres. Test rouge puis vert :
  `tests/test_rabot_assiette_note.py` (mécanisme sous une part posée par le test ; part nulle = exclusion d'avant ;
  indice d'inégalités sur la part coupée, 2 rouges avant). Golden master isolé : 64 cas sur 64 identiques au bit.
- **Rabot uniforme : la contribution à l'Union européenne est exclue là où elle est comptée** (correction,
  relevée par la relecture adverse du lot). Les catégories du moteur somment la dépense primaire des administrations
  (Insee, tableau 3.201) ; « autres » en est le résidu, et cette dépense compte la contribution à l'UE (opération D76).
  Avec `exclure_ue = 1` (le cas de la note), elle restait pourtant rabotée dans « autres » (environ 2 Md€ de coupe en
  trop par an à 8 %) ; avec `exclure_ue = 0`, 44 Md€ × taux étaient ajoutés par-dessus, la même dépense coupée deux
  fois. Désormais `CONTRIBUTION_UE_2025_MD = 22,983` (Eurostat, comptes nationaux annuels des secteurs,
  administrations publiques, D76 versé en 2025, provisoire), sur le chemin de sa catégorie, est retirée de l'assiette
  de « autres » quand elle est exclue, et rabotée une fois sinon. Infobulle de l'exclusion : 23 Md€ en 2025 au lieu de
  « ~44 Md€ ». Test rouge puis vert : `tests/test_rabot_assiette_note.py` (montant, exclusion exacte, pas de double
  coupe, chiffre publié de la coupe 2029 lié à la mesure). Golden master isolé : mêmes 3 cas ; 61 sur 64 identiques
  au bit. Effet (mode cadre, pleine précision, pile assemblée) : coupe 2029 du scénario de la note 139,47 → 137,49
  Md€ ; dette 2032 +0,01 point, déficit −0,02 point de PIB. **Limite déclarée** : la coupe tombe sous la fourchette de
  la note (138 à 140 Md€ ; 8 % × 1 741 = 139,3), de 0,5 à 2,5 Md€ en 2029, parce que l'assiette 2029 du moteur
  (1 719 Md€) suit ses propres projections de dépense et de PIB ; le périmètre n'est pas réglé pour retrouver la
  cible. Indice d'inégalités : la part coupée de la méthode du lot 4 se lit sur les assiettes de 2025, contribution
  à l'UE retirée si elle est exclue (test rouge puis vert).
- **Impôts sur le patrimoine : l'assiette suit le PIB nominal** (règle commune « un taux suit son assiette »).
  Le curseur « Fiscalité du patrimoine » est un pourcentage des recettes de l'IFI, des droits de succession et de
  donation et de la taxe foncière : il s'appliquait pourtant à un bloc figé en euros de l'année source (part dans
  le PIB en baisse d'environ 10 % sur le mandat). L'IFI que remplace l'ISF croissait de 2 % par an depuis 2026,
  une convention propre à ce levier, sans source ouverte. Désormais bloc × intensité × PIB_t / PIB_2025 et IFI
  remplacé × PIB_t / PIB_2025 (`_indice_pib_source`, année source `ANNEE_SOURCE_PATRIMOINE`) ; effets ponctuels
  (Gini, compétitivité) hors indice, comme les revenus du capital et l'impôt plancher. Aucune valeur de base ne
  change (bloc patrimoine, bloc « paramètres » distinct) ; les trois bases sont extraites en constantes nommées
  (`PATRIMOINE_IFI_MD`, `PATRIMOINE_SUCCESSIONS_MD`, `PATRIMOINE_TAXE_FONCIERE_MD`), l'IFI étant le même pour
  les deux leviers. Test rouge puis vert : `tests/test_patrimoine_assiette_pib.py` (nouveau). Golden master
  isolé : bougent exactement les cas qui portent l'un des deux leviers — le scénario qui pose l'ISF (deux modes)
  et les deux mini-scénarios des leviers ; 60 cas sur 64 identiques au bit. Instantanés régénérés une fois
  (mêmes cas). Re-déclarés : l'IFI des tests de l'ISF continu et de l'horloge de l'ISF suit le PIB ; l'assiette
  du test de pouvoir d'achat du patrimoine porte l'indice de l'année ; l'indépendance de l'ISF et de l'impôt
  plancher (Z4') se compare au rejeu et à la première année (le plancher change le PIB, donc l'IFI déduit) ; la
  recette d'année pleine du test du Gini de l'ISF (méthode du lot 4) se lit au PIB de 2025, où l'IFI déduit vaut
  celui de 2025, sans la correction de +2 % par an. Chiffre publié recalculé par sa garde (effet prix des
  rémunérations publiques, METHODOLOGIE) : le point d'indice seul abaisse la dette 2032 de 1,429 et 1,376 point.
- **ISF : la recette suit le PIB nominal, comme l'IFI qu'elle remplace** (règle commune « un taux suit son
  assiette », relevé par la relecture adverse du lot). Le commit précédent faisait suivre le PIB à l'IFI déduit,
  mais pas à la recette de l'ISF, fixe en euros (350 000 foyers × 4,512 M€ × 0,75 %) : la règle ne s'appliquait
  qu'à un côté de la différence ISF − IFI, qui perdait de son poids dans le PIB chaque année. L'impôt plancher,
  autre impôt à taux sur le patrimoine, suivait déjà le PIB. Désormais recette nette de l'année source × PIB_t /
  PIB(`ANNEE_SOURCE_ISF`), année source = 2025, celle de l'IFI remplacé : convention de symétrie, déclarée (les
  chiffrages publiés qui calent la recette, de 2024, ne fixent pas d'année de base). Plafond de 18 Md€ appliqué en
  euros de 2025 (ne mord jamais) ; Gini et compétitivité hors indice, comme les autres impôts à taux. Test rouge
  puis vert : `tests/test_isf_recette_suit_pib.py` (nouveau ; écart ISF − IFI proportionnel au PIB, recette
  inchangée au PIB de 2025, effets ponctuels hors indice). Golden master isolé : bougent exactement les cas qui
  portent l'ISF — le scénario qui le pose (deux modes) et le mini-scénario du levier ; 61 sur 64 identiques au bit.
  Effet (mode cadre, 2032, pleine précision, sur la pile assemblée) : dette −0,05 point, déficit +0,04 point de PIB
  pour le scénario qui pose l'ISF.
  Instantanés régénérés une fois (mêmes cas). Re-déclarés : la forme fermée de l'ISF complet (tests de l'ISF
  continu et de l'horloge) porte l'indice du PIB ; chiffre publié de l'ISF en 2030 (mode cadre) +7,81 → +9,11 Md€,
  garde de test.
- **TVA ciblée : coefficients par Md€ découplés du point du taux normal** (relevé par la relecture adverse du lot,
  aucune sortie ne change). `GINI_TVA_PAR_MD` et `COMPET_TVA_PAR_MD` (effets par Md€ de
  `fiscalite_indirecte.tva_ciblee`) étaient dérivés en appelant la fonction du curseur du taux NORMAL : corriger le
  rendement d'un point de ce taux aurait presque doublé, en silence, l'effet par Md€ d'un autre levier. Leur
  recette de référence est désormais figée à sa valeur de v0.8.1 (`TVA_RECETTE_REFERENCE_TVA_CIBLEE_MD`, 28,42 Md€
  pour +2 points au PIB 2025, même calcul, au bit) ; leur révision relève d'une passe dédiée. Test rouge puis vert :
  `tests/test_tva_ciblee_coefficients.py` (nouveau ; indépendance vérifiée sur l'arbre syntaxique, valeurs au bit).
  Golden master isolé : 64 cas sur 64 identiques au bit.
- **Point de TVA du taux normal : rendement net du seul taux de 20 %** (équation ; V1 et V2 l'étiquetaient à tort
  « paramètres »). L'assiette d'un point était toute la consommation des ménages, taux réduits compris, × 0,9
  (0,53 × PIB × 0,9 = 14,24 Md€ au PIB 2025, plus que le point brut de tous les taux, 13,7) : un point de TVA était
  surestimé de 90 %. Désormais le point net du seul taux de 20 %, 7,5 Md€ au PIB 2025 (DG Trésor, Trésor-Éco n° 371,
  septembre 2025, p. 4, tableau 2, rouvert), en part du PIB de l'année, sans le facteur 0,9 (le point est calé sur
  les recettes encaissées, note 5). Élasticités, majoration en chômage élevé et coude au-delà de 22 % inchangés
  (conventions du moteur). Les coefficients par Md€ de `tva_ciblee` ne changent pas (recette de référence figée au
  point précédent). Part du canal des ménages laissée à 1,0 (borne haute, limite déclarée : la part des ménages du
  seul taux normal n'est pas publiée). Aucun scénario publié ne bouge ; golden master isolé : seul le mini-scénario
  de `tva_rate` bouge, 63 sur 64 identiques au bit. Visiteur (budget voté, mode cadre, 2032, pile assemblée) : +1
  point = déficit −0,22 point de PIB et dette −0,68 (−0,43 et −1,32 avant). Test rouge puis vert : `tests/test_tva_point_net.py`
  (nouveau ; un point statique = 7,5 Md€ au PIB 2025, assiette en part du PIB, rapport constant à l'ancienne
  formule hors facteur 0,9).

## [non publiée — proposée] — équations du lot 4 : méthode unique du Gini (montants en euros, émission une fois, hausse 2026 sur le capital, facteur 1,0, ni convergence ni amortissement)

**Statut** : proposée, non publiée, sans numéro de version. Commit d'ÉQUATIONS, distinct du commit de paramètres
du même lot ci-dessous, qu'il suppose appliqué. Seule la colonne Gini bouge : toutes les autres colonnes des dix
scénarios publiés (deux modes) et des 42 mini-scénarios du golden master sont identiques au bit en pleine
précision.

**Les défauts.** Sept règles n'avaient pas la forme K × montant ou comptaient un instrument à deux coefficients,
et l'assemblage retardait et freinait l'effet sans source :
- tranche supérieure de l'IR : −0,008 par 5 points, jusqu'à −0,0075 par Md€ effectivement prélevé, quinze fois la
  borne arithmétique d'un prélèvement ;
- ISF : −0,020 pour 12 Md€ de recette BRUTE (avant remplacement de l'IFI), le phasage compté deux fois ; l'impôt
  plancher en recopiait l'émission effective (le quart de la règle), à corriger avec lui ;
- indexation des prestations : +0,008 par 10 points de sous-indexation, sans lien avec les euros — un gel d'un an
  (≈ 1,4 Md€) émettait autant qu'un retrait de 10 Md€, six fois la borne arithmétique d'une prestation ;
- indexation des pensions : effet « par point » à l'ouverture de l'écart, flux résiduel de 10 % par an, part
  min(k, N)/N gardée au retour au calendrier — un gel d'un an pesait, par Md€, la moitié d'un gel permanent ;
- rabot uniforme : 0,10 × taux × part sociale × phasage, sans source, RÉÉMIS chaque année dans un agrégateur
  cumulatif (l'indice dérivait tant que le rabot durait) ;
- hausse de 2026 de la CSG sur les revenus du capital (droit en vigueur, portée par le taux global du levier
  CSG) : comptée au coefficient de la CSG pour tous les programmes, alors que son retrait par le levier de la
  fiscalité du capital l'est au coefficient du capital ;
- facteur d'atténuation `GINI_IMPACT_SCALE` = 0,22, sur la seule justification « IPP/OFCE 2022 », passage non
  retrouvé, et contredit par la source des coefficients (avec 0,22, l'effet des prestations ciblées serait
  environ cinq fois plus petit que la contribution publiée par l'INSEE) ;
- convergence de l'indice vers sa cible à 35 % par an (`GINI_CONVERGENCE_RATE`) et amortissement des seules
  baisses à l'approche de 0,25 : aucune source, et l'amortissement ne freinait que les programmes qui réduisent
  les inégalités.

**Les corrections.**
- Tranche supérieure de l'IR : coefficient de l'IFI × Md€ de recette du taux (la recette, extraite en fonction
  pure, est identique au bit).
- ISF et impôt plancher, ensemble : coefficient de l'IFI × recette nette d'année pleine (IFI remplacé déduit pour
  l'ISF), émis au changement du paramètre et rendu au retour à 0 ; la compétitivité est inchangée (hors périmètre).
- Indexation des prestations et des pensions : K × écart EN EUROS (écart de niveau × masse de 2025 de la catégorie,
  l'unité de Y), en incrément ; un gel d'une année garde exactement l'écart qu'il laisse, sans règle séparée au
  retour au calendrier ni flux résiduel (le helper `_retour_au_calendrier`, sans autre appelant, est retiré ;
  `_reference_du_calendrier` reste : la référence datée du SMIC la lit).
- Rabot : chaque catégorie de prestations en espèces à son coefficient (minima sociaux et AAH, chômage, pensions ;
  santé, APA et autres à 0), sur le montant d'année pleine que fixe le taux, émis une fois au changement du taux.
- Hausse de 2026 sur le capital : la part du taux de CSG comprise entre 9,7 % et le taux du droit en vigueur
  (`CSG_TAUX_DROIT_EN_VIGUEUR_2026`, égal à la valeur de `data/droit_en_vigueur.json`, verrouillé par test) prend
  le coefficient du capital ; le reste d'une variation du taux garde celui de la CSG.
- Facteur d'atténuation 1,0 : les coefficients sont physiques et bornés un par un. Aucune règle ne garde
  l'ancien facteur (le SMIC a une valeur sourcée ; l'âge de départ et la CSG progressive sont à zéro faute de
  source) : pas de constante historique.
- Assemblage (arbitrage du mainteneur) : la convergence de 35 % par an et l'amortissement près du plancher sont
  retirés. L'indice publié de l'année vaut la base plus la somme des effets émis jusqu'à elle : l'effet d'une
  mesure arrive l'année où elle s'applique, les calendriers des programmes continuent de jouer. Les bornes de
  sécurité [0,25 ; 0,40] restent le seul garde-fou. La garde de CI de vitesse annuelle (|ΔGini| ≤ 0,01) devient
  une limite déclarée dans la Documentation : un programme qui concentre de fortes mesures sur sa première année
  bouge l'indice plus vite que l'INSEE ne l'a observé (au plus 0,014 en un an), sans effet sur le niveau
  atteint.
- Infobulles du registre public (`policy_measures.json`) : les mentions de Gini que le lot rend fausses
  (CSG progressive, élargissement de l'IR, patrimoine, SMIC, taxe sur les superprofits, TVA énergie, rabot,
  cotisations salariales) et trois qui l'étaient déjà (niches fiscales, niches sociales, exonérations des
  hausses de salaire, à Gini nul dans le moteur) sont réécrites en français courant, sans chiffre qu'un test
  ne lie ; la citation « OFCE 2024 » de la CSG progressive est retirée.

- Tests : `tests/test_gini_equations_lot4.py` (nouveau ; rouge sur le commit de paramètres, vert) — une propriété
  par équation ; garde de borne au niveau des handlers (effet par Md€ sous la borne pour chaque levier en Md€) ;
  facteur 1,0 ancré sur la contribution publiée par l'INSEE ; SMIC émis une fois ; un coefficient pour la hausse
  de 2026 sur le capital ; indice publié = base + cumul des effets, au bit, dans les deux modes, bornes de
  sécurité gardées, plus de constante de convergence (rouge sur l'assemblage d'avant) ; propriétés vues sans
  `scenarios.json` (signe et valeur de l'abattement, même émission
  dans les deux modes pour le rabot, l'ISF et la CSG, retour au défaut de l'impôt sur le revenu).
  `tests/test_gini_borne_registre_lot4.py` (nouveau, proposé par la relecture adverse) : chaque levier du
  registre, chaque paramètre sur son domaine, effet émis par Md€ sous la borne arithmétique, sans dépendre
  d'aucun nom de constante ni d'aucune liste de leviers (rouge sur l'état d'avant le lot et sous mutation).
  Ancrage (e) de l'assemblage rendu effectif : la borne V porte sur la cible non plafonnée (que le plancher dur
  ne masque plus ; rouge vers un facteur 6 sur toutes les émissions), et un test lit la contribution publiée des
  prestations à travers l'assemblage (rouge hors d'un facteur 0,8 à 1,6). Re-déclarés, avec leur motif dans le test : les propriétés I-1 de la relecture adverse
  finale de la release E (sous la forme des écarts en euros), la bascule de l'indexation des pensions, le gel
  d'une année des arbitrages de la release E, la carte des émetteurs récurrents (le rabot en sort ; reste le canal
  d'âge), le canal indexation de la revue adverse v0.6.1, le coefficient de la CSG au commit de paramètres.
- Tests-propriétés de l'assemblage gardés verts : clip jamais atteint (saturation impossible), classement 2030
  préservé, statu quo inerte, réentrance, ancrage des programmes figés ; la propriété de vitesse annuelle est
  retirée avec la convergence (limite déclarée).
- Golden master isolé : les trois instantanés régénérés ne diffèrent que par la colonne Gini.

## [non publiée — proposée] — paramètres du lot 4 : méthode unique du Gini (coefficients au classement final, plages publiées, périmètre, base)

**Statut** : proposée, non publiée, sans numéro de version. Commit de PARAMÈTRES ; les équations du même lot
(tranche supérieure de l'IR, ISF et impôt plancher, indexation des prestations et des pensions en euros, rabot
émis une fois, hausse 2026 des prélèvements sur le capital, facteur d'atténuation) suivent dans un commit séparé.
Seule la colonne Gini bouge.

**Le défaut.** Les règles d'effet sur l'indice de Gini venaient de familles différentes (par point de taux, par
Md€, forfaits), écrites à des époques différentes. Certaines dépassaient l'effet maximal qu'un euro puisse avoir
sur l'indice (fiscalité du patrimoine : −0,001 par Md€, deux fois la borne d'un prélèvement ; élargissement de
l'IR : +0,0011 par Md€). D'autres portaient sur des montants hors du revenu disponible que l'indice de l'INSEE
mesure (droits de succession, taxe foncière, franchises de santé, aides à la rénovation, TVA, accises, taxe
carbone, impôt sur les superprofits). La CSG portait le mauvais signe (« légèrement régressive », source non
retrouvée ; l'INSEE la classe parmi les prélèvements faiblement progressifs). Plusieurs règles n'avaient aucune
source (SMIC « INSEE 2024 », âge de départ, CSG progressive « OFCE 2023 », décote, élargissement de l'IR). La
base de l'indice (0,29, « INSEE 2024 ») ne correspondait à aucune année récente.

**La correction.** Une seule règle, K × montant, avec K = (C − G) / Y (prestation) ou −(C − G) / Y (prélèvement),
C au CLASSEMENT FINAL des niveaux de vie, celui de l'indice publié (dérivée de Lerman et Yitzhaki) : INSEE,
*Revenus et patrimoine des ménages* 2024, fiches 1.3 et 1.4 (composition du niveau de vie par dixième), C et G sur
les mêmes dixièmes ; Y = 1 380 Md€, la masse des niveaux de vie (et non le revenu disponible brut des comptes
nationaux : étiquette corrigée) ; `constants.py`, § CANAUX GINI. La figure 2 de la fiche « Redistribution
monétaire » (*France, portrait social* 2025, classement initial) reste en recoupement publié : ses K dépassent
ceux du classement final de 19 à 45 %.
- sourcés : prestations ciblées −0,000521 par Md€ versé (jusqu'ici −0,0008) ; CSG −0,0000863 par Md€ prélevé
  (jusqu'ici +0,002 par point, signe inversé) ; cotisations salariales +0,0000541 par Md€ rendu (proxy : salaires ;
  jusqu'ici +0,0001). **Cette valeur remplace l'arbitrage du mainteneur du 12/11/2026** (plage +0,00006 à
  +0,0001, tirée du classement initial) : arbitrage du mainteneur, la méthode commune au classement final
  s'applique aussi aux cotisations ; impôt sur le revenu −0,000297 ; allocations chômage +0,000238 par Md€ coupé, en euros (l'ancre DREES
  n° 1368, en personnes, recalculée à −0,138, reste l'ancre du canal durée) ; IFI −0,000444 (figure 2, conservée) ;
  décote +0,000122 par Md€ de recette (Conseil des prélèvements obligatoires, rapport particulier n° 2, tableau
  n° 34 ; classement par revenu déclaré : limite déclarée) ; allocation sociale unique au coefficient des
  prestations ciblées (arbitrage du mainteneur), au lieu de la borne théorique C = −1, majorant délibéré
  jusqu'ici (limite de sens non établi : la concentration propre de son transfert net n'est pas publiée) ;
- plages publiées (bornes recalculées en test depuis les tableaux publiés) : pensions −0,0000685 par Md€, centre
  de −0,0000474 (toutes pensions, fiche 1.4) à −0,0000895 (gel des pensions de base, IPP 2025, tableau 2.2) ;
  abattement des retraités −0,0000902, centre de −0,0000855 à −0,0000949 (IPP, suppression ; le levier décrit le
  forfait de 2 000 € : limite déclarée) ; revenus du capital −0,000398, borne basse sourcée (IPP, suppression du
  prélèvement forfaitaire unique) d'une plage qui va jusqu'à −0,000506 (borne arithmétique) ; SMIC −0,02375 par
  unité de hausse, centre de −0,0231 à −0,0244 (groupe d'experts sur le SMIC 2017, gains par dixième, graphiques
  n° 41 et 45 ; jusqu'ici −0,03, « INSEE 2024 », sans passage), extrapolation linéaire au-delà de +1 % déclarée
  comme convention ;
- zéro faute de source, limite déclarée avec son sens : impôt sur le revenu ciblé et élargissement de l'IR (le
  levier ne dit pas quel instrument il porte ; jusqu'ici une convention « classes moyennes », +0,000255) ; CSG
  progressive (jusqu'ici −0,015) ; âge de départ (jusqu'ici +0,001 par 1,25 année d'écart ; mécanisme gardé) ;
- périmètre (0) : droits de succession, taxe foncière, TVA, accises, taxe carbone, franchises de santé, aides à
  la rénovation, taxe sur les superprofits — hors du revenu disponible de l'INSEE (définition c1458 ; concept
  strict, prix exclus, arbitrage du mainteneur) ; rémunérations publiques : dans le périmètre, zéro faute de
  source (arbitrage du mainteneur ; le sens même de l'effet n'est pas assuré, la dispersion des salaires publics
  étant plus faible que celle de l'ensemble des salariés) ;
- `GINI_BASE` 0,302 : INSEE, série « Niveau de vie et indicateurs d'inégalités », parue le 09/07/2026, valeur
  2024. Commun à tous les programmes.
- Borne arithmétique verrouillée : |K| ≤ (1 − G) / Y pour un prélèvement, (1 + G) / Y pour une prestation, garde
  d'import sur les coefficients nommés et garde de CI sur toute constante dont le nom suit un style du dépôt (la
  garde qui ne dépend d'aucun nom, sur tout le registre, vient avec le commit d'équations).

Citations retirées : « OFCE Policy Brief n° 124 » pour le Gini des pensions (le document ne contient aucun indice de
Gini ; le commentaire de la règle se trompait en outre d'un facteur 10), « OFCE 2023 » (chômage, CSG progressive),
« OFCE 2024 » (TVA, CSG, franchises), « INSEE 2024 » (SMIC), aucune n'ayant de passage retrouvé.

- Tests : `tests/test_gini_methode_unique_lot4.py` (nouveau ; rouge sur l'état d'avant, vert après) : classement
  et borne de chaque constante, recette exécutée depuis les chiffres publiés (classement final et recoupement de
  la figure 2), bornes de chaque plage recalculées, zéros faute de source, périmètre (zéro pour chaque montant
  hors revenu disponible, à l'année d'entrée en vigueur), signe de la CSG, base. Tests re-déclarés, avec leur
  motif dans le test : socle et chantiers W2 à W4 de la release E (constantes remplacées ; l'IR ciblé, à zéro,
  éprouvé par un coefficient sonde), arbitrage des cotisations (remplacé, voir ci-dessus), ASU (coefficient des
  prestations ciblées), canaux de la transition
  (I28, I29), recette de l'ancre ARE, horloge du canal d'âge (éprouvée par un coefficient sonde), CSG
  progressive, ancrage (e) de l'assemblage.
- Golden master isolé : les trois instantanés régénérés ne diffèrent que par la colonne Gini (comparateur
  colonne par colonne ; toutes les autres colonnes identiques).
## [non publiée — proposée] — équation : la croissance n'est plus écrêtée, le filet ne fait plus qu'un avis

**Statut** : proposée, non publiée, sans numéro de version. Commit d'ÉQUATION, sur le lot SMIC.

**La règle** (arbitrage du mainteneur du 16/11/2026). L'écrêtage de la croissance réelle annuelle dans
[−3,5 % ; +2,5 %] (`np.clip` en fin de `calculate_growth`), qui ne venait d'aucune source, est supprimé. Les bornes
(`CROISSANCE_FILET_MIN`, `CROISSANCE_FILET_MAX`, noms conservés) restent celles du domaine de validité des
multiplicateurs linéaires : une croissance qui en sort est publiée telle qu'elle est calculée, et l'avis
`_filet_croissance` la signale (« croissance non écrêtée ; résultats à lire avec prudence »). Le contrat lu par le
site ne change pas : même préfixe (« filet de croissance [−3,50 % ; 2,50 %] atteint : »), même format par année
(« x % calculés, y % retenus », désormais égaux), même bloc `cadre.filet_croissance` (croissance retenue =
croissance calculée). Le libellé du site, qui dit la croissance « ramenée à la limite », est à retoucher côté site.

**Ce qui bouge** (pleine précision). Mode cadre (publié) : rien, au bit, pour les dix scénarios et la référence
sans programme (garde de CI : aucun n'en sort, aucune année). **Mode historique de l'API** : les deux programmes
publiés dont la croissance 2026 sortait du domaine — croissance 2026 de 2,76 % et 4,39 % au lieu de 2,50 % ; dette
2032 plus basse de 1,02 et 7,99 points ; pouvoir d'achat 2029 plus haut de 0,13 et 0,89 point (publié : +0,2 et
+0,9) ; les huit autres scénarios identiques au bit. Mini-scénario des cotisations salariales (mode historique) : il
sortait aussi du domaine, il bouge.

- Test rouge puis vert : `tests/test_croissance_sans_ecretage.py` (nouveau) — croissance hors du domaine publiée
  telle quelle, avis au même format, aucun avis dans le domaine, garde du mode publié (programmes dérivés des
  scénarios publiés, aucun nom).
- Tests mis à jour (ils verrouillaient l'écrêtage) : `test_release_e_filet_structure.py` (valeur retenue = valeur
  calculée), `test_release_e_arbitrages.py` (avis m6), `test_symetrie_depense_courante.py` (un gros choc reste en
  miroir ; la limite déclarée dit « en sortent »).
- Documentation : METHODOLOGIE (encadré de l'avis du filet : la phrase « lever le filet suppose une crise de
  financement » est remplacée par la règle ; limite du calendrier de l'impulsion ; plafond de taille), docstrings de
  `api.py`, `cadre.py`, `growth.py`, `orchestrator.py`, commentaire de `constants.py`.

## [non publiée — proposée] — texte : l'option du lot 6 (santé et réforme de l'État au rythme de la dépense courante) est retenue

**Statut** : commit de TEXTE ; moteur inchangé. L'option était décrite comme « non tranchée » ; elle est retenue
(arbitrage du mainteneur du 16/11/2026). Mis à jour : le statut du bloc de l'option ci-dessous, l'encadré « Rythme de
la dépense courante » de METHODOLOGIE et la docstring de son test. Le message du commit de l'option n'est pas
réécrit.

## [non publiée — proposée] — texte du lot SMIC : ancrage sur le Trésor et ses trois limites, chiffrées

**Statut** : proposé, non publié. Commit de TEXTE (documentation et garde de chiffres liés) ; moteur, instantanés et
sorties inchangés.

**L'ancrage** (arbitrage du mainteneur du 16/11/2026). Le coût d'une hausse du SMIC suit l'échelle du Trésor (groupe
d'experts 2017, modèle statique), pas celle de l'OFCE (modèle dynamique, environ deux fois plus coûteux par point).
Trois limites sont déclarées dans METHODOLOGIE (§ SMIC), chacune avec son sens et son chiffre, sans nouvel élément
sur les écrans (mode cadre 2028, programmes publiés qui relèvent le SMIC) :
1. coût au bas de la fourchette publiée (Trésor −0,0105 point de PIB par point de hausse, OFCE −0,020 à −0,024) :
   si l'écart était entièrement réel, dette 2032 plus haute de 0,24 à 0,67 point (OFCE 2012) et de 0,34 à 0,96 point
   (OFCE 2024) — favorable aux programmes qui relèvent le SMIC ; l'ordre de grandeur annoncé avant le lot (« jusqu'à
   0,5 point ») était une estimation, la mesure sur la pile donne jusqu'à 0,96 ;
2. effet direct sur le chômage au-dessus de l'effet net de l'OFCE (0,025 contre 0,007 point par point) : ramené à
   0,007, chômage 2032 plus bas de 0,06 à 0,16 point, dette 2032 plus basse de 0,04 à 0,13 point — sens contraire ;
3. revenu des salariés du privé (4,7 à 14,0 Md€ en 2032) et coût du travail absents du PIB ; l'OFCE, tous canaux
   compris, en tire une perte nette de 9 600 à 27 200 emplois pour ces programmes ; effet sur le PIB publié par
   aucune source.

- Garde : `tests/test_smic_limites.py` (nouveau) recalcule ces chiffres (programmes dérivés des scénarios publiés,
  aucun nom) et vérifie leur sens ; elle se saute sans les scénarios publiés.

## [non publiée — proposée] — paramètres du lot SMIC : dernier SMIC du Journal officiel et part nette officielle

**Statut** : proposée, non publiée, sans numéro de version. Commit de PARAMÈTRES, sur les deux équations du lot SMIC
ci-dessous. **Suppose le réencodage des fiches côté site** (`scenarios.json` : SMIC des programmes qui n'y touchent
pas porté à 1 867,02 €, valeur du droit en vigueur ; montants écrits en net reconvertis avec le rapport officiel) :
sans lui, un programme encodé à 1 800 € recevrait une baisse du SMIC.

**Les valeurs** (arbitrage du mainteneur du 16/11/2026). Référence : le dernier SMIC brut mensuel paru au Journal
officiel, 1 867,02 € (12,31 € de l'heure sur 35 heures ; arrêté du 22 mai 2026, JORF n° 0121, en vigueur au 1er juin
2026), au lieu de 1 800 € sans source (`SMIC_BRUT_MENSUEL_REFERENCE_EUR`, `constants.py`) ; c'est aussi la valeur
du droit en vigueur (`data/droit_en_vigueur.json`), le défaut du moteur (`config.py`) et celui du registre des
paramètres (`policy_measures.json`, info-bulle réécrite). Part nette officielle : 1 477,93 € nets
(service-public.fr, fiche F2300) / 1 867,02 € ≈ 0,7916 (`PART_NETTE_DU_BRUT_SMIC`) ; conversion d'un montant écrit en
net : `smic_brut_du_net` (`handlers/additionnels.py`), 1 700 € nets = 2 147,55 € bruts (2 180 € avec l'ancien
rapport de 0,78). Limites déclarées (METHODOLOGIE, § SMIC) : la règle légale ajoute à l'inflation la moitié du gain
de pouvoir d'achat du salaire horaire de base des ouvriers et employés, non comptée (référence un peu basse) ;
référence à mettre à jour à la parution du décret de décembre 2026.

**Ce qui bouge** (pleine précision, avec les fiches réencodées). Hausses retenues en mode cadre 2028 (référence portée à 2028 :
1 920,21 €) : 11,84 % pour les deux programmes à 1 700 € nets (au lieu de 21,1 % avant le lot), 4,16 % pour le
programme à 2 000 € bruts (au lieu de 11,1 %). Mode cadre : dette 2032 de −0,13 à −0,06 point, déficit 2032 de +0,01 à +0,07 point, croissance moyenne
2028-2032 de −0,008 à +0,001 point, chômage 2032 de −0,11 à −0,08 point, pouvoir d'achat 2032 de −0,34 à −0,15
point ; mode historique : dette 2032 de −0,46 à −0,11 point. Les sept autres scénarios et la référence sans
programme, encodés à la valeur du droit, sont identiques au bit (neutralité vérifiée par les instantanés).

- Test rouge puis vert : `tests/test_smic_parametres.py` (nouveau) — référence du Journal officiel, part nette et
  conversion, défaut, droit et registre égaux à la référence, neutralité du droit et du défaut dans les deux modes.
- Tests du lot SMIC ramenés à la constante de référence (`test_smic_flux_tresor.py`, `test_fp_rampe_v067.py`).
- Bloc généré des scénarios (`docs/SCENARIOS_POLITIQUES.md`) régénéré depuis les fiches réencodées ; instantanés
  régénérés (seuls les trois programmes qui relèvent le SMIC et le mini-scénario du levier bougent).
- Chiffres liés de l'encadré du lot 5d et de la note d'EXPLICATION recalculés par leur garde (la part « agents
  publics » du SMIC seule y vaut désormais 0,029 à 0,185 point de dette 2032).

## [non publiée — proposée] — équation du lot SMIC : la hausse se lit contre une référence datée, portée à l'année d'application

**Statut** : proposée, non publiée, sans numéro de version. Commit d'ÉQUATION, sur le bloc suivant (cinq postes du
Trésor). La valeur de la référence ne change pas encore (1 800 €, défaut historique du moteur) : le dernier SMIC paru
au Journal officiel vient au commit de paramètres qui suit.

**La règle** (arbitrage du mainteneur du 16/11/2026). Un montant de programme se lit tel qu'il est écrit : un SMIC
brut mensuel de son année d'application, l'origine du levier. Il est comparé à la référence
(`SMIC_BRUT_MENSUEL_REFERENCE_EUR`, année `SMIC_ANNEE_DE_REFERENCE` = 2026, `constants.py`) portée à cette année avec
l'indice de prix des dépenses du moteur, la revalorisation légale faisant déjà partie du statu quo. La hausse est
fixée l'année d'origine, puis conservée en pourcentage. L'indice de chaque année est celui que le moteur a calculé
cette année-là (`_indice_prix_par_annee`, posé avec la mémoire de l'inflation ; une année passée absente lève une
erreur, jamais un 1,0 silencieux). La valeur du droit en vigueur de l'année se lit dans les euros de l'année de
référence (`_smic_de_reference`, `handlers/additionnels.py`) : elle est neutre à toute origine. Sans cette règle, le
monde « droit au début » de la composition, à l'horloge du programme, verrait une baisse du SMIC, que la
composition ajouterait à la hausse du programme. Limite déclarée (METHODOLOGIE, § SMIC) : en mode cadre, un montant
compris entre la valeur du droit et la référence portée à l'année d'application est une baisse.

**Ce qui bouge** (pleine précision). Mode historique : rien, au bit (l'année d'application y est l'année de
référence ; instantané historique, mini-scénarios et écarts au statu quo identiques). Mode cadre 2028 : les trois
programmes publiés qui relèvent le SMIC, hausse plus faible (indice 2028 / 2026 du moteur), dette 2032 de −0,07 à
−0,05 point, déficit 2032 de +0,02 à +0,04 point, croissance moyenne 2028-2032 de −0,005 à −0,001 point, chômage
2032 de −0,06 à −0,04 point, pouvoir d'achat 2032 de −0,20 à −0,14 point, Gini 2032 +0,0002 ; les sept autres
scénarios et la référence sans programme identiques au bit.

- Test rouge puis vert : `tests/test_smic_reference_datee.py` (nouveau) — indice mémorisé chaque année, hausse du
  mode cadre contre la référence portée à l'année d'application et conservée ensuite, neutralité de la valeur du
  droit dans tous les mondes (y compris « droit au début »), mode historique inchangé, défaut neutre ; deux mutants
  rougissent (sans la neutralité du droit, sans les prix).
- Chiffres liés de l'encadré du lot 5d et de la note d'EXPLICATION recalculés par leur garde ; la garde écrit
  désormais « x » au lieu de « x à x » quand les deux bornes s'arrondissent pareil.
- Registre des paramètres régénéré (`docs/MEASURE_REGISTRY.md`, `tests/snapshots/measure_registry.json`) : le
  défaut du levier est désormais la constante de référence.

## [non publiée — proposée] — équation du lot SMIC : les cinq postes du Trésor, chacun selon sa nature

**Statut** : proposée, non publiée, sans numéro de version. Commit d'ÉQUATION, sur les lots 2, 6 et 5 assemblés.
La hausse se lit encore contre 1 800 € (la référence datée vient au commit suivant) ; aucun autre levier ne change.

**La règle** (arbitrage du mainteneur du 16/11/2026). Le levier `smic` reprend les effets d'une hausse de 1 % du
SMIC sur le solde public publiés par le groupe d'experts sur le SMIC (rapport 2017, tableau 9, PDF p. 82, modèle
Saphir de la DG Trésor), en M€ de 2017 par point : cotisations des employeurs nettes des allègements −400,
cotisations et contributions des salariés +240, paie publique −260, prestations sociales +110, impôt sur le revenu
+70 ; total −240 (`SMIC_TRESOR_SOLDE_PAR_POINT_M_EUR_2017`, `constants.py`). Mise à l'échelle : × salaires bruts
2025 / 2017 (1 157,166 / 880,657 Md€, Insee, tableau 2.101, `SALAIRES_BRUTS_2017_MD`) × PIB nominal de l'année /
PIB 2025, × la hausse en points. Chaque poste garde sa nature : la paie publique passe au canal des rémunérations
publiques (traitement des transferts du lot 5b, effet prix du lot 5d ; seul l'écart au point d'indice compte, comme
avant) ; la baisse des prestations est un transfert ; cotisations des salariés, impôt sur le revenu et allègements
forment un flux de recettes au coefficient et au profil des impôts (`RECETTES_AU_PROFIL_DES_IMPOTS`,
`simulator.py`) — un seul flux, exact tant que la hausse et la baisse d'impôts ont le même coefficient (garde de
test). `smic` sort de `MESURES_MULTIPLICATEUR_NET` ; le coefficient propre de 0,15 écrit dans `get_multiplier`,
sans source, est supprimé. La fraude fiscale garde le sien, au bit (garde de test). Effet direct sur le chômage
conservé (+0,025 point par point de hausse, une fois). Pouvoir d'achat : le revenu disponible du tableau 8 du même
rapport (PDF p. 81), +690 M€ par point (revenu brut +1 110, cotisations des salariés −240, impôt sur le revenu −70,
prestations −110) ; la part des agents publics passe par la règle du moteur (0,535 € par € de coût), le reste est
le salaire net du privé ; les cotisations des salariés ne sont comptées qu'une fois.

**Ce qui disparaît.** Une paie publique de 50 Md€ de masse (15 à 45 % au-dessus du Trésor) ; 12 Md€ de prestations
qui montaient avec le SMIC (le Trésor les fait baisser) ; des cotisations à 45 % sur 2,7 millions de salariés ; la
part nette de 0,78 (`PART_NETTE_DU_BRUT_SALAIRES_PRIVES`, sans source, retirée : plus aucun lecteur).

**Ce qui bouge** (pleine précision, à la hausse encore lue contre 1 800 €). Mode cadre 2028 : les trois programmes
publiés qui relèvent le SMIC, dette 2032 de −0,71 à +0,18 point, déficit 2032 de −0,04 à +0,13 point, croissance
moyenne 2028-2032 de +0,001 à +0,023 point, chômage 2032 de −0,002 à −0,027 point, pouvoir d'achat 2032 de +0,15 à
+0,33 point, Gini inchangé ; mode historique : dette 2032 de −0,99 à +0,27 point. Les sept autres scénarios et la
référence sans programme sont identiques au bit ; instantanés : seuls ces trois programmes et le mini-scénario du
SMIC bougent.

- Test rouge puis vert : `tests/test_smic_flux_tresor.py` (nouveau) — postes et total des tableaux 9 et 8, flux mis
  à l'échelle chaque année, paie publique nette du point d'indice, revenu des ménages du tableau 8 sans double
  compte, effet sur le chômage, plus de coefficient propre pour le SMIC, fraude fiscale au bit, coefficient et
  profil de chaque flux dans le moteur complet, prémisse du flux unique de recettes.
- Tests mis à jour (ils verrouillaient l'ancienne exception) : `test_impulsions_v067.py` (liste des leviers à
  coefficient propre), `test_remunerations_publiques_transferts.py` (plus d'émetteur à coefficient propre ; le
  verrou de l'exception par le comportement est retiré, la règle générale s'applique au SMIC),
  `test_prestations_hors_transferts.py` (le SMIC émet ce canal comme levier de transfert),
  `test_symetrie_transferts_v067.py` (le SMIC entre dans la symétrie des transferts),
  `test_fp_rampe_v067.py` (paie publique en euros de l'année, au PIB nominal).
- Documentation : METHODOLOGIE § SMIC réécrite (sans la liste des positions politiques, périmée), tableau des
  multiplicateurs, encadrés des lots 5b, 5d et 5e, table du pouvoir d'achat, profils ; EXPLICATION mise à jour ;
  chiffres liés des encadrés des lots 5c et 5d recalculés par leurs gardes.

## [non publiée — proposée] — équations du lot 5c : dotation aux collectivités, la moitié d'une variation en investissement local

**Statut** : proposée, non publiée, sans numéro de version. Commit d'ÉQUATION, distinct des blocs des lots 5e, 5d
et 5b ci-dessous, qu'il suppose appliqués. Aucun coefficient ne change.

**La règle** (arbitrage du mainteneur du 16/11/2026). Une variation de la dotation aux collectivités
(`collectivites.dotation`) est prise pour moitié (`PART_DOTATION_INVESTIE` = 0,5, `constants.py`) comme une variation
d'investissement local, pour l'autre moitié comme de la dépense courante, dans les deux sens. La moitié investie
prend le traitement du curseur d'investissement local : flux d'investissement, coefficient et profil de
l'investissement productif (1,41 point de PIB à 4 ans par point de PIB, contre 0,79) et effet d'offre du capital
public local (canal `collectivites_invest`). L'effet direct sur le déficit reste d'un euro pour un euro. La même règle
vaut pour la coupe de la ligne « Dotations » par le rabot uniforme (`COUPES_DE_DOTATION`) : même ligne de 120 Md€
que le curseur ; la part investie de la coupe est publiée dans l'impact du rabot (impulsion) et, en mode cadre,
nourrit le même canal d'offre depuis une référence nulle. Un levier en échec (valeur non numérique) n'a ni impulsion
ni effet d'offre, curseur d'investissement compris (avant : son effet d'offre comptait encore).

**Deux références, déclarées.** L'impulsion se compte depuis le défaut du moteur (120 Md€), comme toute dépense ;
l'effet d'offre, en mode cadre, depuis la dotation du droit en vigueur de l'année (116,6 Md€), lue dans le cadre de
la simulation (`CadreTemporel.droit_en_vigueur_de`), pour que le statu quo ne consomme aucune offre (contrat W6-10,
inchangé et vert dans les deux modes). Écart : 1,7 Md€ par an ; la référence sans programme porte l'impulsion
(+0,15 point de dette 2032) sans l'effet d'offre (+0,09 de plus s'il était compté depuis le défaut). Le mode
historique n'applique pas le droit en vigueur et n'en lit pas le fichier : la part investie n'y a pas d'effet d'offre,
son impulsion y est comptée. Une première version comptait l'offre depuis le droit dans les deux modes : le statu
quo nu du mode historique recevait un bonus (dette 2032 −0,09 point), et ce mode lisait le fichier du droit ;
écartée. Cause : le défaut du moteur diffère du droit en vigueur ; un alignement relèverait d'une release de
paramètres.

**Sources et limites.** Caisse des Dépôts, *Éclairages* n° 8 (septembre 2015) : élasticité de l'investissement local
aux dotations de 0,14 à 0,40 la première année, « symétrie à court terme », 0,40 pour les communes après trois baisses
successives ; rapportée aux montants de 2013 (DGCL), 0,20 à 0,26 € par euro la première année, 0,41 à 0,59 € pour
une baisse durable. Cour des comptes, *Les finances publiques locales* (septembre 2018, p. 69-86) : part forfaitaire
de la DGF réduite de 11,2 Md€ en 2013-2017, investissement local de 2017 inférieur de 10,8 % à celui de 2013 (environ 0,6 € par euro, sans
contrefactuel, cycle électoral non neutralisé). La moitié est le centre de la fourchette d'une baisse durable. Limites
déclarées (METHODOLOGIE, encadré du lot 5c et limite 12) : une seule étude économétrique, non évaluée par des pairs ;
une seule part quel que soit l'horizon, dès la première année, alors que l'étude ne tient pour causales que ses
estimations de court terme (0,20 à 0,26 €) — effet de première année surestimé si l'on suit ce seul court terme ; une
part montant avec la durée de la baisse demanderait des conventions que l'étude ne donne pas (non proposée) ; aucune
réaction des collectivités sur le solde (impôt local, emprunt, fiscalité transférée) ; symétrie au-delà du court terme
par convention ; double compte possible demande + offre, commun aux leviers d'investissement (0,045 à 0,106 point de
dette 2032 pour les quatre scénarios qui baissent la dotation, celui du rabot uniforme compris).

- Test rouge puis vert : `tests/test_dotation_investissement_local.py` (nouveau), ce qu'il garde :
  - **impulsion** identique à celle du curseur d'investissement à part × (dotation − défaut), dépense compensée,
    effet d'offre retiré, deux modes, deux sens : au bit en mode historique, à 1e-12 près en mode cadre ;
  - **effet d'offre, mode cadre** : identique à celui du curseur à part × (dotation − dotation du droit) ;
  - **mode historique** : aucun effet d'offre de la part investie, aucun appel au chargeur du droit (espion, avec
    son témoin en mode cadre) ;
  - non-vacuité (la dotation n'est plus de la seule dépense courante ; le droit diffère du défaut), miroir hausse
    et baisse sur le PIB de 1 à 4 ans, chiffres publiés de l'encadré et de la note d'EXPLICATION liés à la mesure ;
  - **coupe de dotation du rabot** : même ligne de dépense que le curseur (périmètre), part investie publiée chaque
    année = part × coupe, effet d'offre en mode cadre seulement et égal, en montant, à celui du curseur
    d'investissement pour part × coupe (pas seulement de même signe) ; **levier en échec** sans impulsion ni offre ;
  - **curseur d'investissement, dotation et coupe du rabot bougés ensemble** : sur le canal d'offre, leurs parts
    s'ajoutent, aucune ne remplace les autres (aucun scénario publié ne bouge le curseur : sans ce test, une part
    qui remplaçait l'écart du curseur laissait toute la suite verte) ;
  - paragraphe « Ce qui bouge » et décomposition de l'encadré recalculés en pleine précision et liés à la mesure
    (avec les scénarios publiés ; non liés : le coefficient seul et les rangs), double compte de la limite compris.
  Rouge avant, sur l'état du lot 5e : 21 échecs sur 30 (les tests de structure et d'invariance passaient déjà).
  Mutations, toutes rouges : « offre depuis le défaut » (le test d'offre, W6-10 et W6-9 du mode cadre), « offre
  aussi en mode historique » (le test du mode historique, W6-10 et W6-9 historiques), « pas d'offre en mode cadre »,
  « impulsion depuis le droit », « rabot sans part investie », « rabot sans offre », « levier en échec avec offre »,
  « valeur non numérique lue comme le défaut », « part de la dotation qui remplace l'écart du curseur », « part du
  rabot qui remplace les deux autres » (ces deux-là, d'un caractère, n'étaient vues par aucun test avant les deux
  tests de combinaison) et « offre du rabot doublée » (vue sans les scénarios publiés par le test du montant et
  celui de la combinaison ; avant, par un golden master seulement).
- Tests existants adaptés, aucune tolérance élargie : W6-9 (la projection « paramètres d'offre au neutre » ramène la
  dotation au droit en mode cadre, sa référence d'offre) ; part d'investissement publiée (curseur plus part de la
  dotation ; avant le début, en mode cadre, la part de la dotation du droit) ; W6-9, la projection retire aussi le
  rabot en mode cadre (son neutre d'offre est l'absence de coupe) ; source unique du lot 5e (le flux de dépense du
  rabot net aussi de sa part investie) ; `depenses_investissement` dans
  `TRACEABILITY_KEYS` (une sous-part de `depenses`, lue par `flux_par_levier`, comme `recettes_tva`) ; chiffres
  liés de la documentation ; la garde des chiffres du lot 5d retire la part investie (ce lot, postérieur), pour que
  ses chiffres restent ceux de son état (sans elle, ils bougent au millième : −1,704 deviendrait −1,707).
- Golden master isolé (pleine précision) : l'état d'avant, instrumenté, liste les cas où la dotation lue diffère du
  défaut, ou que le rabot coupe, une année au moins ; seuls ceux-là bougent (23 : les dix scénarios dans les deux
  modes, la référence du mode cadre, deux mini-scénarios) ; les 41 autres cas, dont le statu quo historique, sont
  identiques au bit.
  Instantanés régénérés une fois (golden masters historique, cadre et mini-scénarios, delta de référence). Pouvoir
  d'achat 2029 figé non modifié.
- Effet (mode cadre 2028, dix scénarios publiés, par rapport au lot 5e, en pleine précision) : dette 2032 de +0,146
  à +0,149 point pour les six qui gardent la dotation du droit (référence +0,148), de +0,256 à +0,413 pour les trois
  qui la baissent de 7 à 12 Md€, +0,481 pour celui qui utilise le rabot (dont +0,323 pour sa coupe de dotation) ;
  déficit 2032 de −0,024 à −0,116 ; croissance moyenne 2028-2032 de −0,006 à −0,037 ; Gini inchangé (moins de
  0,0001). Décomposition (trois programmes, en écart à la référence) : coefficient seul +0,126 à +0,246 ; avec le
  profil de l'investissement +0,063 à +0,191 ; avec l'effet d'offre (ce commit) +0,109 à +0,266. Variantes de la part
  (baisse durable de 10 Md€) : +0,15 à 20 %, +0,38 à 50 %, +0,46 à 60 %. Rangs, en pleine précision pour tous les
  indicateurs : le budget 2026 voté et un programme échangent les 4ᵉ et 5ᵉ rangs de dette et de déficit 2032 et les
  7ᵉ et 8ᵉ de chômage 2032 ; deux programmes échangent les 7ᵉ et 8ᵉ rangs de déficit 2032 ; aux sorties du moteur, à
  deux décimales (une pour le pouvoir d'achat), ce dernier échange devient un ex æquo au 7ᵉ rang et un ex æquo
  apparaît au 5ᵉ rang de pouvoir d'achat 2032 ; aux valeurs affichées par le site, à une décimale, l'échange des 4ᵉ
  et 5ᵉ rangs de déficit et celui des 7ᵉ et 8ᵉ rangs de chômage disparaissent, l'ex æquo du 7ᵉ rang de déficit se
  départage, trois rangs de croissance bougent (5ᵉ → 7ᵉ, 8ᵉ → 7ᵉ ex æquo, ex æquo du 5ᵉ rang ramené de trois
  scénarios à deux), l'échange de dette et l'ex æquo de pouvoir d'achat demeurent.
- Pile d'intégration (reporté après les lots 2, 6, 5b, 5d et 5e, mesuré contre le lot 5e reporté) : dette 2032
  de +0,131 à +0,136 point pour les six qui gardent la dotation du droit (référence +0,136), de +0,182 à +0,311
  pour les trois qui la baissent, +0,342 pour le rabot (dont +0,207 pour sa coupe) ; déficit −0,020 à −0,094 ;
  croissance moyenne −0,004 à −0,029 ; décomposition +0,002 à +0,100 (profil de l'investissement) et +0,046 à
  +0,175 (avec l'offre) ; variantes de la part : +0,10 / +0,25 / +0,30 (20 / 50 / 60 %) ; double compte 0,044 à
  0,110 ; chiffres liés de l'encadré et de la note recalculés ; rangs relus sur la pile (deux lectures). Point (c) :
  le miroir hausse/baisse de dotation tient sa tolérance de 1 % sur la pile (au plus 0,9 %, de 1 à 4 ans, dans les
  deux modes) ; l'écart de 1,04 à 1,24 % vu à l'essai d'assemblage portait sur la première version du lot, dont
  l'offre se comptait depuis le défaut ; aucune re-déclaration. Point (d) : la garde du calage sur le tableau du FMI
  reste verte avec la part investie des dotations.
- Arbitrage du mainteneur du 16/11/2026, texte seulement : indemnités journalières dans le curseur Ondam, calcul
  inchangé, limite déclarée (METHODOLOGIE, limite 11 ; EXPLICATION) — des prestations en espèces, 6,75 % de l'Ondam
  constaté 2025 (17,9 sur 265,4 Md€, Commission des comptes de la sécurité sociale, mai 2026) ; au traitement des
  transferts, au plus 0,003 point de dette 2032. Seul classement encore à arbitrer : la dynamique de la dépense de
  santé selon le levier qui la porte.
- Docs : METHODOLOGIE (nouvel encadré, table de base, périmètre du canal investissement, classements, limites 11
  et 12, chiffres liés), EXPLICATION (table, notes en français courant), commentaires de `constants.py`,
  `simulator.py`, `engine/growth.py`, `engine/orchestrator.py` et `handlers/montaigne.py`.

## [non publiée — proposée] — équations du lot 5e : prestations en espèces émises hors des leviers de transfert au traitement des transferts

**Statut** : proposée, non publiée, sans numéro de version. Commit d'ÉQUATION, distinct du bloc du lot 5b
ci-dessous, qu'il suppose appliqué. Aucun coefficient ne change.

**La règle** (même mécanique que le lot 5b). Le montant qu'un levier émet au canal ménages `prestations` et qui
n'est pas déjà traité comme un transfert (levier hors `TRANSFER_MEASURES`, hors coefficient propre) forme un flux
distinct `(levier, 'prestations')`, au coefficient et au profil des transferts, dans les deux sens ; le reste du
levier garde sa famille. Un seul cas : le rabot uniforme, dont les coupes de pensions, d'allocations chômage et de
minima sociaux (environ un tiers de la coupe : 46,8 Md€ sur 141,2 en 2032, mode cadre) étaient prises en dépense
courante. Source : prestations sociales en espèces (SEC 2010, D.62), déjà traitées en transferts quand un levier de
transfert les porte.

**Exceptions**, verrouillées par la liste et par le comportement : le SMIC (coefficient propre) ; la santé
(`PRESTATIONS_NON_RECLASSEES`), dont le canal porte les franchises et participations, une prestation en nature
(D.632), en attente d'un arbitrage. Limite déclarée (METHODOLOGIE, limite 10) : la coupe de masse salariale du rabot
reste assimilée à des effectifs ; la note source ne dit pas s'il s'agit d'un gel ; prise comme un gel, elle
relèverait la dette 2032 de 1,07 point (le traitement des transferts l'abaisserait de 0,51 point, l'effet prix
du lot 5d, qui retire le coût du gel du PIB publié, la relèverait de 1,59 point) ; sur la pile d'intégration,
1,08, 0,58 et 1,65.

- `flux_par_levier` (`engine/growth.py`) reçoit les leviers de transfert et les exclusions, en arguments nommés
  OBLIGATOIRES (un appelant qui les oublierait désactiverait la règle en silence ; appelants modifiés :
  `_stocker_impulsions` et les tests `test_eviction_composition_v0610`, `test_release_e_investissement_local`) ;
  `_stocker_impulsions` prend le flux `prestations` au traitement des transferts, comme le flux `remunerations`.
- Test rouge puis vert : `tests/test_prestations_hors_transferts.py` (nouveau), ce qu'il garde :
  - **inventaire** dérivé du registre des paramètres : hors des leviers de transfert et des coefficients
    propres, exactement le rabot (reclassé) et la santé (exclue) ; un émetteur nouveau rougit, à classer ;
  - **source unique** : chaque année, le flux de prestations vaut exactement le canal, deux modes ;
  - **même effet qu'un transfert** du même montant, à 1e-9 près, en montée en charge sur trois ans, deux sens,
    cinq états, pour le rabot et un émetteur synthétique ; non-vacuité ;
  - **exceptions par le comportement** : retirer le canal du SMIC ou de la santé ne change aucune colonne
    macroéconomique ; le retirer du rabot change la trajectoire ;
  - **signature** : `flux_par_levier` refuse un appel sans les deux ensembles.
  Rouge avant : 25 échecs sur 32. Mutations « santé reclassée », « règle désactivée », « leviers de transfert oubliés », « règle limitée à la
  première impulsion », « prestations comptées en plus de la dépense », « SMIC reclassé » : toutes rouges.
- Tests adaptés, aucune tolérance élargie : les espions de `flux_par_levier` du lot 5b transmettent les arguments
  nommés ; la mutation de W2-13 (levier de prestations retiré des transferts) coupe aussi la seconde voie,
  `PRESTATIONS_NON_RECLASSEES` ; le test du pouvoir d'achat qui pose un canal `prestations` sans euro budgétaire
  le pose sur un levier de transfert (sur un autre levier, ce canal est désormais une part de la dépense, lue par
  la croissance).
- Golden master isolé (pleine précision) : l'état d'avant, instrumenté, liste les cas où un levier hors transfert,
  hors coefficient propre et hors santé émet au canal ; seuls ceux-là bougent (3 : le programme qui utilise le rabot
  dans les deux modes, le mini-scénario du rabot) ; les 61 autres sont identiques au bit. Instantanés régénérés une
  fois (golden masters historique, cadre et mini-scénarios ; delta de référence inchangé). Pouvoir d'achat 2029 figé
  non modifié.
- Effet (mode cadre 2028, par rapport au lot 5b) : le programme qui utilise le rabot, dette 2032 −0,58 point,
  déficit 2032 plus faible de 0,14, croissance moyenne 2028-2032 +0,042, chômage 2032 −0,06 ; les neuf autres
  scénarios et la référence identiques au bit. Rangs : aucun ne change en pleine précision (ni aux sorties du
  moteur, deux décimales) ; aux valeurs affichées par le site (une décimale), le programme qui utilise le rabot
  rejoint, ex æquo, le 1ᵉʳ rang de déficit 2032.
- Pile d'intégration (reporté après les lots 2, 6, 5b et 5d, mesuré contre le lot 5d reporté) : le programme qui
  utilise le rabot, dette 2032 −0,65, déficit +0,15, croissance moyenne +0,038, chômage −0,07 ; en dette 2032 il
  passe du 2ᵉ au 1ᵉʳ rang. Point (a) : `niveaux_du_budget` (lot 6) prend les deux ensembles désormais obligatoires
  de `flux_par_levier` et les transmet ; ses deux appelants (budget évalué hors de son effet propre, budget
  précédent) passent les mêmes ensembles que `_stocker_impulsions` (source unique), comme le banc du lot 6.
- Docs : METHODOLOGIE (encadré, table de base, classements, limite 10), EXPLICATION (table et note en français
  courant), commentaires de `simulator.py` et `engine/growth.py`.

## [non publiée — proposée] — équations du lot 5d : effet prix des rémunérations publiques sur le PIB en valeur publié

**Statut** : proposée, non publiée, sans numéro de version. Commit d'ÉQUATION, distinct du bloc du lot 5b
ci-dessous, qu'il suppose appliqué. Aucun coefficient ne change. Remplace la limite (3) de l'encadré du lot 5b.

**La règle.** Le coût employeur de l'année des rémunérations publiques à effectifs constants — le canal ménages
`remunerations_publiques` de tous les leviers, part « agents publics » de la hausse du SMIC comprise,
`cout_employeur_des_remunerations` (`engine/growth.py`), source unique — s'ajoute au PIB en valeur PUBLIÉ, en niveau,
dans les deux sens. L'effet prix est une identité comptable : l'exception du SMIC du lot 5b ne vaut que pour la
demande. L'assiette de la part publique du SMIC est en cours d'instruction (reprise avec le traitement du SMIC). Le déflateur publié en est relevé d'autant (PIB publié = PIB réel × déflateur publié),
« Inflation % » (déflateur du PIB) publie sa variation, et les ratios publiés (dette, déficit, recettes, dépenses
rapportés au PIB) sont rapportés au PIB publié (`au_pib_publie`). Rien n'entre dans le moteur : PIB nominal,
déflateur et inflation internes, indice des prix à la consommation, recettes, indexations, Phillips, impulsions,
prime de taux, traînée, atterrissage, Gini, pouvoir d'achat sont ceux de l'état sans effet prix.

**Sources.** SEC 2010 § 10.28 (production non marchande évaluée à la somme de ses coûts), § 10.30 et § 10.44 (une
hausse de rémunération à effectifs constants est un prix) ; Mésange 2017 p. 92 (le prix de la valeur ajoutée non
marchande suit le salaire moyen par tête non marchand) ; Insee Première n° 1950, mai 2023 (le déflateur de la
consommation des administrations « tiré par la revalorisation du point d'indice des fonctionnaires »).

**Limites déclarées** (METHODOLOGIE, encadré du lot 5d) : pas de rétroaction sur la prime de taux ni la traînée de
dette (rapportées au PIB publié, elles abaisseraient le ratio de dette de 2032 d'environ 0,2 point par point de PIB
de coût, au plus 0,25 mesuré) ; effectifs non concernés (leur valeur ajoutée directe en volume reste au multiplicateur de la
dépense courante, nul la première année avant le calendrier du lot 6, contre 1,2 à 2,0 dans les modèles publiés) — à coût égal, la première
année, une hausse de salaire relève le PIB publié de 1 % et abaisse le ratio de dette de 0,2 point par point de PIB,
une embauche ne relève pas le PIB et accroît le ratio de 1,05 point (sur la pile, depuis le calendrier du lot 6 : −1,40
point pour le salaire, PIB publié +1,67 %, contre −0,21 pour l'embauche, PIB +0,69 %) ; effort budgétaire rapporté
au PIB interne (écart au plus 0,033 point de PIB), écart de production inchangé (volume) ; ratio des recettes publié
en baisse, sans retour des cotisations modélisé.

- Test rouge puis vert : `tests/test_effet_prix_remunerations.py` (nouveau), à la précision machine : identité
  publiée PIB = PIB réel × déflateur, avec et sans rémunération ; inflation publiée = variation du déflateur
  publié ; chaque année, PIB publié − PIB interne = coût employeur de l'année, effectifs exclus ; ratios publiés ×
  PIB publié = ratios internes × PIB interne ; toute autre colonne identique au bit (indice des prix à la
  consommation, PIB réel, croissance, chômage, soldes et stocks en euros, taux, effort, écart de production,
  potentiel, pouvoir d'achat, Gini, compétitivité) ; sans rémunération, tout identique au bit ; le SMIC seul relève
  le PIB publié du montant de son canal, rien d'autre ; hausse et baisse en miroir à 1 % près (mesuré : 0,015 % à
  0,34 %, le coût suivant la masse salariale indexée) ; chiffres du paragraphe « Ce qui bouge » de l'encadré et de
  la note d'EXPLICATION recalculés en pleine précision et liés à la mesure (avec les scénarios publiés, groupes lus
  dans les impacts, sans nom de scénario ; non liés : les rangs).
  Rouge avant : 13 échecs sur 45 (le cœur de la règle ; les gardes d'invariance, vraies avant le lot, passaient déjà). Mutations « prix entré dans le PIB interne », « prix dans l'indice des prix à la
  consommation », « prix compté une seule année », « prix aussi pour les effectifs », « déflateur publié non
  relevé », « SMIC exclu de l'effet prix » : toutes rouges.
- Tests adaptés, aucune tolérance élargie : l'équivalence du lot 5b (« même effet qu'un transfert »), la garde de
  comportement de l'exception du SMIC du lot 5b (qui porte sur la demande) et les tests de la conjoncture observée
  (PIB nominal INTERNE) retirent l'effet prix des deux côtés (il est verrouillé par le test neuf).
  Le rejeu de la formule du pouvoir d'achat depuis les sorties publiées retire l'effet prix du déflateur publié
  (D = Déflateur × (PIB − coût) / PIB) : la formule lit le déflateur interne, ce que METHODOLOGIE précise désormais.
  Même défaut, latent, dans trois bancs qui relisaient le PIB publié comme le PIB interne (verts faute de
  rémunération dans leur programme) : l'effort du test W2-15 et les niveaux d'impulsion du test des impulsions
  lisent désormais le PIB interne reconstruit (PIB publié − coût de l'année), le banc des multiplicateurs lit
  l'impulsion telle qu'injectée ; un cas avec rémunération prouve la bonne lecture (0,01 × PIB interne, 1 % sous
  0,01 × PIB publié). Commentaire du validateur annuel corrigé : il borne des ratios au PIB interne et n'alimente que
  le journal de débogage ; le rapport publié lit les ratios publiés.
- Golden master isolé (pleine précision) : bougent les 15 cas où un levier émet une rémunération (sept programmes,
  deux modes, et le mini-scénario du SMIC), et seulement les colonnes PIB, déflateur, inflation du déflateur et
  ratios au PIB ; les 49 autres cas sont identiques au bit. Instantanés régénérés une fois (golden masters
  historique, cadre et mini-scénarios, delta de référence). Pouvoir d'achat 2029 figé non modifié.
- Effet (mode cadre 2028, par rapport au lot 5b, pleine précision) : seuls les rapports au PIB bougent — la dette,
  le déficit, les recettes et les dépenses en euros ne changent pas, c'est le PIB en valeur publié, au dénominateur,
  qui est relevé. Dette rapportée au PIB en 2032 : −1,704 et −1,558 point pour les deux programmes qui relèvent le
  point d'indice (PIB publié 2032 plus haut de 1,18 et 1,11 %), −0,766 pour un programme qui revalorise les
  enseignants et relève le SMIC, de −0,084 à −0,397 pour les quatre autres ; décomposition, chaque levier compté
  seul : point d'indice −1,461 et −1,437, enseignants −0,084 à −0,397, part publique du SMIC −0,024 à −0,455
  (retirée de l'ensemble : −0,024 à −0,453, les leviers interagissant par le PIB publié) ; déficit 2032 rapporté au
  PIB plus faible de 0,003 à 0,120 ; inflation du déflateur publiée +0,013 à +0,240 point par an en moyenne sur
  2028-2032 (jusqu'à +1,27 une année) ; indice des prix à la consommation, croissance, chômage, Gini et pouvoir
  d'achat identiques au bit. Rangs en pleine précision (comme aux sorties du moteur, deux décimales) : dette 2032,
  9ᵉ/10ᵉ ; aux valeurs affichées par le site (une décimale), s'y ajoutent en dette un ex æquo au 4ᵉ rang qui se
  départage et en déficit un ex æquo nouveau au 7ᵉ rang.
- Pile d'intégration (reporté après les lots 2, 6 et 5b, mesuré contre le lot 5b reporté) : dette rapportée au PIB
  en 2032 −1,611 et −1,549 point (point d'indice ; PIB publié 2032 +1,16 et +1,11 %), −0,748, −0,088 à −0,385 ;
  déficit 2032 rapporté au PIB plus faible de 0,003 à 0,104 ; décomposition, chaque levier seul : 1,428 et 1,381,
  0,088 à 0,385, SMIC 0,024 à 0,445 (0,443 retirée de l'ensemble) ; chiffres liés de l'encadré et de la note
  recalculés. Rangs de dette 2032 : trois changent entre le 4ᵉ et le 6ᵉ (pleine précision). L'effet prix entre dans
  la boucle refondue du lot 6 sur la seule passe définitive : l'évaluation hors effet propre n'en laisse aucune
  trace (test d'empreinte du lot 6, qui compare tous les attributs d'instance, nouvel état compris). Limite (2)
  relue avec le lot 6 : l'embauche a désormais un effet la première année.
- Docs : METHODOLOGIE (encadré, limite (3) du lot 5b), EXPLICATION (la dette rapportée au PIB baisse, la dette en
  euros ne change pas), docstrings de `engine/growth.py` et commentaires de `engine/orchestrator.py`.

## [non publiée — proposée] — équations du lot 5b : rémunérations publiques à effectifs constants au traitement des transferts

**Statut** : proposée, non publiée, sans numéro de version. Commit d'ÉQUATION, distinct du bloc du lot 5
ci-dessous, qu'il suppose appliqué. Aucun coefficient ne change.

**La règle** (arbitrage du mainteneur du 16/11/2026). Une hausse (ou une baisse) de rémunération des agents publics
à effectifs constants est un revenu versé aux agents : pour la croissance, elle prend le traitement des transferts,
coefficient `MULT_TRANSFERTS` et profil `DECAY_PROFILE_TRANSFERS`, dans les deux sens. Elle vaut pour le point
d'indice (`fonction_publique`, jusqu'ici de la dépense courante, 0,79 point de PIB à 4 ans par point de PIB) et
pour la revalorisation des enseignants en place (`education.salaires`, jusqu'ici au coefficient et au profil de
l'investissement productif, 1,41) : désormais 0,65. Les effectifs (embauches, suppressions, postes d'enseignants)
et le reste de chaque levier gardent leur famille et leur profil.

**Sources et limites.** Comptabilité nationale : une hausse de rémunération à effectifs et structure constants est un
effet prix, pas volume (SEC 2010 § 10.44 et § 11.35-11.37 ; Eurostat, manuel des prix et volumes, 2016, § 3.11.2).
Mésange (document de travail Insee G2017/04, p. 106) fait jouer les « salaires publics en prix » comme les
prestations en espèces. Le niveau est encadré par deux modèles publiés : e-mod.fr (OFCE, policy brief n° 17, avril
2017, p. 15 : multiplicateur « proche de 0,9 au bout de trois ans pour les prestations sociales, les transferts
sociaux en nature et les salaires publics », assiette du « point de PIB » non précisée) et QUEST (Roeger & in 't
Veld 2010, texte et tableau 2 : effet sur le PIB privé de 0,3 pour les salaires publics, contre 0,20 à 0,53 pour
les transferts généraux, soit 0,55 à 0,74 transfert par euro de coût ; choc temporaire d'un an, Union
européenne). Le coefficient des transferts du moteur (0,65 à 4 ans) se situe entre les deux et s'applique au coût
employeur entier : « le même effet qu'un transfert du même montant » porte sur le coût employeur brut, dont le
revenu net des agents n'est qu'une part (`PART_NETTE_REMUNERATIONS_APU`). Limites déclarées : les sources décrivent
un effet différé (Mésange : « Les mécanismes de transmission à l'activité sont donc plus lents » ; e-mod.fr : 0,25
la première année), le profil des transferts du moteur est concentré sur les premières années (profil repris par
analogie, sans source : effet trop rapide la première année) ; le retour immédiat des cotisations et de la CSG aux
administrations n'est pas modélisé à part (il ne passe que par l'élasticité des recettes au PIB, la même année
depuis le calendrier du lot 6 sur la pile d'intégration, avec un an de retard avant) ; l'effet
prix sur le PIB en valeur n'est pas représenté ; les études empiriques sur les salaires publics divergent (Bermperoglou, Pappa & Vella 2017 ; Forni, Monteforte & Sessa 2009 ;
FMI, document de travail 19/125) et n'ont été lues qu'en résumé. Pour les effectifs, Gechert (catégorie « emploi
public ») et l'OFCE (Creel, Heyer & Plane 2011) ne contredisent pas la dépense courante.

**La correction.** `flux_par_levier` (`engine/growth.py`) sort de la dépense du levier le montant qu'il émet déjà
au canal ménages `remunerations_publiques` (coût de l'année, le même que lit le pouvoir d'achat) : flux distinct
`remunerations`, que `_stocker_impulsions` prend au coefficient et au profil des transferts ; le reste de la
dépense garde son flux. Sans ce canal, rien ne change. Un levier à coefficient propre garde tout dans son solde.

- **En attente d'un arbitrage du mainteneur** : la hausse du SMIC émet aussi une part « agents publics » à ce canal.
  Le SMIC a un coefficient propre appliqué à son solde (`MESURES_MULTIPLICATEUR_NET`) : cette part y reste.
  Mesuré, la sortir du solde au traitement des transferts baisserait la dette 2032 (mode cadre) de 0,05 à 0,81
  point pour les trois programmes publiés qui relèvent le SMIC.
- Test rouge puis vert : `tests/test_remunerations_publiques_transferts.py` (nouveau), ce qu'il garde :
  - **émetteurs** dérivés du registre des paramètres (`PARAM_DOMAINS` et `INTENSITE_DOMAINS`, chaque paramètre
    porté seul à chaque borne), pas d'une liste : point d'indice, revalorisation des enseignants, et la part
    « agents publics » du SMIC, seule exception à coefficient propre, verrouillée par la liste et par le
    comportement (retirer cette part du canal ne change aucune colonne macroéconomique) ;
  - **source unique** : chaque année, le flux de rémunération vaut exactement le canal, le reste de la dépense
    garde sa famille et son profil, aucun flux de rémunération sans canal ; deux programmes (hausses, baisses),
    deux modes ;
  - **même effet qu'un transfert** : ±1 point de PIB de rémunération donne toute la trajectoire
    macroéconomique (PIB, dette, déficit, chômage, inflation, taux) d'un transfert du même montant, à 1e-9 près,
    pour chaque émetteur dérivé et un émetteur synthétique, dans les deux sens et cinq états (banc historique,
    mode cadre 2028, dette à 160 % du PIB, écarts de production à −3 % et à +1,5 %), en montée en charge sur
    trois ans (une règle limitée à la première impulsion de chaque levier y rougit) ;
  - **miroir** par les vrais curseurs (point d'indice ±2 %, revalorisation ±5 %), 1 à 6 ans, deux modes ;
  - **plafond de 10 % du PIB** en mode « reduction » : canal et dépense réduits du même facteur, source unique
    tenue.
  Le test « source unique » est un détecteur de changement de la formule de `flux_par_levier`, pas une propriété ;
  un canal pris hors de la dépense ou doublé est vu par le miroir et par les tests du pouvoir d'achat.
  Rouge avant : 37 échecs sur 45 (l'inventaire, les miroirs, symétriques depuis le lot 5, et l'exception du SMIC,
  vraie avant le lot, passaient déjà). Banc des
  multiplicateurs : famille « rémunération publique », tolérance des transferts (0,795 avant, rouge ; 0,650 après).
- Golden master isolé : l'état d'avant, instrumenté, liste les cas où un levier hors coefficient propre émet ce
  canal ; seuls ceux-là bougent (les sept programmes concernés, dans les deux modes), les 50 autres cas sont
  identiques au bit en pleine précision, dont les 42 mini-scénarios et les deux statu quo. Instantanés régénérés
  une fois (golden masters historique et cadre, delta de référence) ; mini-scénarios inchangés. Pouvoir d'achat
  2029 figé non modifié (écart au plus 0,3, tolérance 1,5).
- Effet (mode cadre 2028, dix scénarios publiés, par rapport au lot 5) : dette 2032 de +0,16 à +0,59 point pour
  les sept programmes concernés, déficit 2032 de −0,04 à −0,14, croissance moyenne 2028-2032 de −0,011 à −0,037
  point ; Gini inchangé, compétitivité au plus 0,0003 point d'indice. Décomposition : coefficient seul (profil
  d'origine) 0,29 et 0,28 point pour le point d'indice, 0,09 à 0,56 pour les enseignants ; coefficient et profil
  (ce commit) 0,53 et 0,52, et 0,07 à 0,57. Rangs : cinq rangs de croissance moyenne changent, deux programmes
  échangent les 5ᵉ et 6ᵉ rangs de chômage 2032 ; dette, déficit et Gini inchangés.
- Pile d'intégration (reporté après les lots 2 et 6, mesuré contre l'option du lot 6 reportée) : dette 2032 de +0,09
  à +0,59 point pour les sept programmes concernés, déficit 2032 de −0,03 à −0,13, croissance moyenne de −0,010 à
  −0,034 ; rangs (sorties du moteur) : dette 2032, deux changent, croissance moyenne, deux. Adapté : l'espion du test
  du traitement des transferts prend la signature du lot 6 (`niveaux` du budget) ; la rémunération publique prend
  le coefficient recalé des transferts (0,785 au lieu de 0,688) dans les tableaux des familles ; chiffres
  « moteur actuel » du lot 2 recalculés (variantes de la recherche).
- Arbitrage du mainteneur du 16/11/2026, texte seulement : subventions aux entreprises et transferts en capital aux
  ménages, classement inchangé (dépense courante), limite déclarée (METHODOLOGIE, limite 9) — aucune source
  consultée ne chiffre une subvention durable (Mésange, note 77 : sans effet dans le modèle ; QUEST ne chiffre que
  des aides temporaires à l'investissement) ; le coefficient de la dépense courante est vraisemblablement trop fort.
  Mesuré : au coefficient des transferts, la dette 2032 (mode cadre) baisserait de 0,02 à 0,10 point selon le
  programme (au plus 0,08 en écart à la référence) ; transferts en capital : +0,005 point, un programme.
- Hors du changement, mesuré : la revalorisation des enseignants ne nourrit pas l'effet d'offre (il ne lit que le
  budget de l'éducation) ; elle nourrit la compétitivité (« attractivité du métier »), de 0,002 à 0,007 point
  d'indice en 2032 selon le programme ; inchangé ici.
- Docs : METHODOLOGIE (nouvel encadré, table de base, tableau des familles, périmètre du canal investissement,
  Fonction publique, « Classement à arbitrer » du lot 5 : point d'indice traité), EXPLICATION (table et note en
  français courant), docstrings des handlers et commentaires de `simulator.py` et `_types.py`.
## [non publiée — proposée] — option du lot 6 (équation) : santé et réforme de l'État au rythme de la dépense courante

**Statut** : OPTION retenue (arbitrage du mainteneur du 16/11/2026), non publiée, sans numéro de version. Commit
d'ÉQUATION séparé, au-dessus de la release du profil de l'investissement (bloc suivant). Le titre du commit dit
encore « non tranchée » : il est antérieur à l'arbitrage.

**Le défaut.** `INVESTMENT_FLOW_MEASURES` donnait à la santé et à la réforme de l'État le rythme de l'investissement
(`DECAY_PROFILE_INVEST`), alors qu'elles prennent depuis la v0.6.0 le coefficient de la dépense courante, le code les
décrivant comme « de la consommation/optimisation publique ». Classement de la première version publique, motivé
par un seul commentaire ; aucune source dans l'historique du dépôt. Depuis le calage du profil de l'investissement
sur le FMI, leur chemin pour un point de PIB permanent était 0,28 / 0,47 / 0,63 / 0,77 / 0,77, loin de celui d'une
dépense courante (0,69 / 0,93 / 0,98 / 0,90 / 0,79) et de la dépense générique de Mésange (0,78 / 1,06 / 1,03).

**La correction.** Les deux leviers sortent de `INVESTMENT_FLOW_MEASURES`, qui garde le périmètre du canal de
l'investissement (éducation, recherche, transition écologique) : ils prennent le rythme de la dépense courante
(`DECAY_PROFILE_TAXES`). Aucun coefficient ne change.

- Test rouge puis vert : `test_sante_et_reforme_de_l_etat_au_rythme_de_la_depense_courante` (chemin de chacun des
  deux leviers = celui d'un levier synthétique de dépense courante de même coefficient, au bit près, six années
  d'effet, hausse et baisse, mode historique et mode cadre) : rouge 8 sur 8 avant, vert après ; rouge 4 sur 8 si
  l'un des deux leviers revient dans `INVESTMENT_FLOW_MEASURES`.
- Re-déclaré : la limite « santé et réforme de l'État » de la release du profil devient, dans cette option, une
  règle ; sa garde chiffrée est retirée du test des limites du chemin (le chemin est gardé par le test ci-dessus).
- **Contrat affaibli, à accepter avec l'option** : « le curseur de prévention ne réduit jamais la dette » (I20). La
  santé agissant dès sa première année, le ratio de dette passe sous le statu quo les deux premières années, par le
  dénominateur : au maximum du curseur (11,2 Md€), −0,019 puis −0,007 point en mode historique, −0,024 puis −0,014
  en mode cadre, égaux à ceux d'une dépense courante de même montant ; la dette en euros est au-dessus dès la
  première année (+2,4 puis +4,4 Md€). Propriété re-déclarée, vérifiée dans les deux modes : dette en euros jamais
  sous le statu quo ; ratio jamais dessous à partir de la troisième année ; les deux premières, écart au plus égal à
  celui d'une dépense courante de même montant.
- Chiffres liés re-mesurés (référence, sentier de déflateur, marge de Phillips, atterrissage, investissement vert
  tiré seul, investissement local, chemin de l'investissement en mode cadre : 1,40 et 1,56 ; cumul sur cinq ans en
  mode cadre : +0,8 % et −11,8 % avec canal d'offre, −6,9 % et −18,6 % sans).
- Instantanés régénérés une fois : les dix scénarios publiés des deux modes (tous portent la santé) ; trois
  mini-scénarios sur 42 (santé, réforme de l'État, recette exceptionnelle). Pouvoir d'achat 2029 figé non modifié
  (écart au plus 0,4 point, tolérance 1,5).
- Effet (mode cadre 2028, dix scénarios publiés, dette 2032, par rapport à la release du profil) : de −0,03 à +0,14
  point ; aucun rang de dette ni de déficit ne change.
- Pile d'intégration (reporté après le lot 2 et le lot 6 entier, mesuré contre le profil du FMI reporté) : de −0,02
  à +0,14 point de dette 2032, référence +0,10 ; aucun rang de dette ni de déficit ne change (deux décimales).
- Docs : METHODOLOGIE (encadré « Rythme de la dépense courante », limites du profil, encadré du lot 5 sur la
  santé), EXPLICATION.

## [non publiée — proposée] — paramètres du lot 6 (suite) : profil de l'investissement calé sur le tableau du FMI

**Statut** : proposée, non publiée, sans numéro de version. Release de PARAMÈTRES (arbitrage du mainteneur : le profil
suit le tableau du FMI, source citée), qui suppose appliqués les deux blocs du lot 6 ci-dessous. Aucune équation ne change ;
seules des valeurs changent : les cinq premiers termes de `DECAY_PROFILE_INVEST`, et une cible nommée
(`CHEMIN_CIBLE_INVESTISSEMENT`).

**Ce qui change.** Le TOTAL, demande et canal d'offre, d'un levier de capital public reproduit année par année le
tableau 3.4, colonne (1), du FMI (WEO oct. 2014, ch. 3, p. 95) : 0,457 / 0,755 / 1,035 / 1,389 / 1,539 (écarts-types
0,147 à 0,441 ; 17 économies avancées, 1985-2013 ; choc = erreur de prévision de l'investissement public, en part du
PIB). Profil (0,45 ; 0,65 ; 0,45 ; 0,25 ; 0,12 ; 0,06) → (0,3718 ; 0,3152 ; 0,3487 ; 0,3495 ; 0,2201 ; 0,06) ;
coefficient inchangé (1,31). Protocole : mode historique, choc permanent de 1 % du PIB par an dès 2026, levier de la
transition écologique, canal d'offre alimenté par son paramètre d'investissement (1 % du PIB nominal 2026). Le
dernier terme ne change pas : la source n'estime rien au-delà de quatre ans après le choc.

- Test rouge puis vert : `test_chemin_de_l_investissement_sur_le_tableau_du_fmi` (chemin H0-H4 à 0,0005 point, la
  précision du tableau ; rouge avec le profil d'avant : 0,553 / 1,247 / 1,562 / 1,696 / 1,669). Mutations rouges : un
  terme du profil décalé de 0,001, coefficient à 1,30 ou 1,32, canal d'offre neutralisé (cible lue sur la demande
  seule).
- Limites déclarées, liées à la mesure (`test_limites_du_chemin_liees_a_la_mesure`) : en mode cadre, 1,40 et 1,55
  les deux dernières années ; selon la taille du choc (offre plafonnée), 1,57 à quatre ans pour 0,5 % du PIB, 1,50
  pour 1,5 % ; les leviers qui portent ce profil sans canal d'offre actif sur l'horizon (éducation, recherche,
  rénovation) n'ont que la demande, 1,26 et 1,28 les deux dernières années ; santé et réforme de l'État, au
  coefficient de la dépense courante, de 0,28 à 0,77. Comparaison à Mésange déclarée : plus haut la première année
  (1,31), plus bas ensuite (0,93 à cinq ans), pur choc de demande.
- Re-déclarés, motif daté dans chaque test : le banc des multiplicateurs ne compare plus la demande seule de
  l'investissement à 1,5 (la cible porte sur le chemin total) ; chiffres du banc d'autofinancement (demande seule :
  6 % du coût récupéré, ratio au-dessus du statu quo dès 2030) et du tableau des familles ; forme du profil (le « pic
  à l'année 2 » n'est plus une règle) ; banc de l'auditeur gardé sur le profil de l'audit, comme ses coefficients ;
  premier terme du profil lu dans le moteur (test du plancher monétaire) ; valeurs datées V2-02 ; investissement
  local et de l'État, 10 Md€ par an : écart absolu inchangé dans les deux modes, signe et rapport en mode cadre
  seulement (en mode historique 2035, +0,07 et −0,03, de part et d'autre de zéro) ; investissement vert tiré seul :
  le ratio de dette 2035 baisse jusqu'à 10 Md€/an, puis le coût l'emporte entre 10 et 20 Md€/an ; chiffres liés de
  la référence, du sentier de déflateur, de la marge de Phillips et de l'atterrissage. Disparaît la limite « calage
  sur un seul point » de la release précédente. Aucune tolérance élargie ; la nouvelle (0,0005 point) est plus
  serrée.
- Instantanés régénérés une fois : les dix scénarios publiés des deux modes (dette, déficit, chômage, croissance,
  inflation, pouvoir d'achat ; compétitivité en mode cadre) ; six mini-scénarios sur 42 (éducation, recherche,
  transition écologique, santé, réforme de l'État, recette exceptionnelle). Pouvoir d'achat 2029 figé non modifié :
  écart au plus 0,4 point, tolérance 1,5.
- Effet (mode cadre 2028, dix scénarios publiés, dette 2032, par rapport à la release précédente) : de −0,16 à
  +1,76 point ; les programmes riches en investissement montent, ceux qui le coupent ou n'y touchent pas bougent à
  peine ; référence −0,14.
- Pile d'intégration (reporté après le lot 2 et le lot 6, mesuré contre les paramètres du lot 6 reportés) : de −0,16
  à +1,73 point de dette 2032, référence −0,14. La garde du calage (tableau 3.4 année par année) reste verte avec le
  lot 2. Textes réécrits sur la pile : la recherche, en forme stock depuis le lot 2, a un canal d'offre actif dès
  l'année qui suit la dépense et son total dépasse le tableau (3,19 et 3,62 les deux dernières années, chiffre lié à
  la mesure) ; le curseur d'investissement vert tiré seul ne fait plus baisser le ratio de dette 2035, même pour les
  petits montants (le coût l'emporte dès le début du curseur) ; chiffres « moteur actuel » du lot 2 recalculés
  (recherche +5 Md€ par an : −1,38 point et −11,7 Md€ ; effet total par euro 1,22 / 1,52 / 4,15 €).
- Docs : METHODOLOGIE (« Calendrier de l'impulsion » : profil calé, protocole, ce que la source ne dit pas,
  comparaison à Mésange, limites ; profil INVEST ; L2 ; somme analytique ; banc d'autofinancement ; tableau des
  familles ; profils par famille), EXPLICATION (profil en français courant, table des coefficients).

## [non publiée — proposée] — paramètres du lot 6 : coefficients d'impact recalés après la correction du calendrier

**Statut** : proposée, non publiée, sans numéro de version. Release de PARAMÈTRES, distincte du commit d'équation
du lot 6 (bloc suivant), qu'elle suppose appliqué. Aucune équation ne change.

**Pourquoi.** Le budget agissant désormais dès son année, le niveau « quatre ans après » de chaque famille est celui
de sa cinquième année d'effet, et non plus de sa quatrième : à coefficients inchangés, il baissait de 9 à 13 % au banc
des multiplicateurs (investissement 1,41 → 1,29 ; transferts 0,650 → 0,563 ; impôts 0,646 → 0,584 ; dépense
courante 0,794 → 0,720). Les cibles (`MULT_CIBLE_NIVEAU_4ANS`) ne changent pas.

**Le recalage.** Méthode de la sécante sur le banc de `tests/test_multiplicateurs_centraux_v067.py`, chaque
coefficient ramené au niveau à 4 ans d'avant le lot : `MULT_INVESTISSEMENT` 1,2 → **1,31** (1,41 ; la cible 1,5 reste
à −6 %, dans sa tolérance de 10 %, comme avant), `MULT_COUPE_DEPENSES` 0,74 → **0,811** (0,79, hausse et coupe),
`MULT_TRANSFERTS` 0,688 → **0,785** (0,650), `MULT_HAUSSE_IMPOTS` et `MULT_BAISSE_IMPOTS` 0,615 → **0,674** (0,65 ;
la baisse reste au coefficient de la hausse). Facteurs ×1,09 à ×1,14. Le lot change le calendrier, pas les niveaux :
recaler l'investissement sur 1,5 plutôt que sur 1,41 serait une décision distincte. Les coefficients propres (SMIC
0,15, fraude fiscale −0,40), présents depuis la première version publique, ne sont calés sur aucun niveau mesuré
dans le moteur : non recalés, limite déclarée (recalés comme leur famille de profil, ils déplaceraient la dette 2032
des programmes publiés de 0,03 point au plus).

**Calage de l'investissement** : tranché par le mainteneur dans la release suivante (profil calé sur le tableau du
FMI) ; la limite « calage sur un seul point » qu'énonçait ce bloc n'a plus cours.

- Test rouge puis vert : banc des multiplicateurs, niveau à 4 ans sur la cible pour les six familles (en échec
  attendu strict au commit d'équation, vert ici ; écart au niveau d'avant le lot ≤ 0,2 %).
- Re-déclarés : coefficients écrits en dur remplacés par leur constante (symétrie de l'investissement) ; banc de
  l'auditeur avec la table de l'audit, investissement compris ; représentations du verrou documentaire ; miroir du
  curseur de défense : 1,0087 à la 4ᵉ année d'effet (tolérance 1 %), 1,0108 à l'année calendaire d'avant le lot
  (tolérance 1,5 %, montant fixe en Md€) ; gros choc de 2 points : écart au miroir de 10 % (13 % en mode cadre),
  exactement la part écrêtée par le filet de croissance ; valeurs datées V2-02 et
  V2-03 ; forme de l'effet d'offre de l'investissement vert (le ratio baisse sur tout le curseur) ; réponse des prix
  comparée à ThreeME et Mésange.
- Instantanés régénérés une fois : restent identiques les mini-scénarios du SMIC, de la fraude fiscale et de
  l'abattement des retraites (aucune impulsion à un coefficient recalé) ; les dix scénarios publiés bougent.
  Pouvoir d'achat 2029 figé non modifié (écarts au figé ≤ 0,3 point, tolérance 1,5).
- Effet (mode cadre 2028, dix scénarios publiés, dette 2032), recalage seul : de −1,31 à +1,70 point ; équation et
  recalage ensemble, par rapport à l'état d'avant le lot : de −4,26 point (la plus forte relance) à +4,58 (le plus
  fort effort de consolidation) ; référence −0,03. Étendue de la dette 2032 entre les dix scénarios : 13,4 → 4,7
  points. Déficit 2032 : −0,84 à +0,64 ; croissance moyenne 2028-2032 : −0,26 à +0,11 point ; Gini inchangé.
- Pile d'intégration (reporté après le lot 2 et l'équation du lot 6, mesuré contre eux) : recalage seul de −1,28 à
  +1,70 point de dette 2032 ; équation et recalage ensemble, contre le lot 2 : de −4,17 à +4,58 ; référence −0,03 ;
  étendue de la dette 2032 12,99 → 5,43 points ; déficit 2032 −0,84 à +0,64 ; croissance moyenne −0,258 à +0,108.
  Chiffres « moteur actuel » du lot 2 recalculés sur la pile (recherche +5 Md€ par an : dette 2032 −1,61 point et
  −17,2 Md€ ; effet total par euro à quatre ans 1,31 / 1,61 / 4,24 €, la propriété « au-dessus de la cible de 1,5 »
  tient de nouveau, attente stricte levée) ; courbe de l'investissement vert : baisse sur tout le curseur.
- Docs : METHODOLOGIE (recalage, profils par famille dans « Calendrier de
  l'impulsion », ordres de grandeur des limites restantes, table des multiplicateurs, somme analytique de
  l'investissement à k = 1,31, tableau des familles, chiffres liés à la mesure), EXPLICATION (table des
  coefficients).

## [non publiée — proposée] — équation du lot 6 : le budget agit dès son année (calendrier de l'impulsion)

**Statut** : proposée, non publiée, sans numéro de version. Commit d'ÉQUATION, qui suppose appliqués les blocs des
lots 1 et 5 ci-dessous ; les coefficients sont recalés dans un commit de paramètres distinct (bloc suivant).

**Le défaut.** La croissance de l'année t était calculée avant les mesures de t et ne lisait que l'impulsion du
budget de t−1 : une mesure n'agissait sur le PIB, les recettes et le chômage induits qu'à partir de l'année qui suit
son premier budget. Effet nul l'année du premier budget, pour toutes les familles et dans les deux modes. Le code y
voyait un « lag standard » qui évitait un calcul en boucle ; aucune source n'était citée. Les coefficients étant
calés sur un niveau « quatre ans après », le niveau visé était atteint à cet horizon, mais toute la trajectoire
arrivait un an trop tard : dans la fenêtre publiée, une année d'effet sur cinq manquait.

**Ce que disent les sources (rouvertes).** Toutes donnent un effet l'année du choc : FMI, WEO d'octobre 2014, ch. 3,
tableau 3.4 (investissement public, +0,46 % de PIB l'année du choc, +1,54 % quatre ans après) ; Mésange 2017
(document de travail Insee G2017/04 : +1,31 la première année pour l'investissement, p. 102 ; +0,78 pour une dépense
générique, p. 105 ; chocs effectifs au premier trimestre, p. 100) ; OFCE 2011 (tableau 5 : +0,8 à +1,2 selon
l'instrument) et OFCE 2017 (policy brief n° 17, tableau 5 : −0,6 la première année pour une baisse de la dépense).
Aucune des sources consultées ne porte de demi-année. Détail, conventions de chaque source et ce qu'elle ne dit pas :
METHODOLOGIE, « Calendrier de l'impulsion ».

**La correction.** Effet plein l'année du premier budget. Chaque année, le bloc « demande » tourne d'abord sans
l'impulsion de son propre budget, sur une copie profonde de l'état, pour évaluer les efforts de ce budget
(`_niveaux_hors_effet_propre`) ; il tourne ensuite pour de bon avec cette impulsion, âge 0 de son profil
(`_demande_de_l_annee`). C'est la valorisation d'avant (le budget à l'état macro de son année, avant son propre
effet), appliquée l'année même : seul le calendrier change. Calcul exact, sans tolérance ni itération, déterministe.
Écartés : le point fixe (impulsion évaluée à l'état final ; temps de calcul ×5 au mieux, ×22 dans le prototype ;
au plus 0,07 point de dette 2032 d'écart, mode cadre) et le réordonnancement simple (mesures publiées évaluées à un
PIB qui n'est pas celui de l'année ; au plus 0,02 point). Coût : ×2,0 (15 → 31 ms par simulation, mode cadre,
médiane des dix programmes publiés). Un avis posé sous la déduplication du journal, que l'évaluation partage,
était perdu (formule côté recettes) : il est posé hors d'elle, au même texte. Inchangés et déclarés en limites :
effets directs des mesures sur le chômage et passage de la TVA dans les prix, toujours un an après ; effet d'offre ;
ancrage de l'assiette de la taxe sur les transactions financières en mode historique ; filet de croissance, que
deux des dix programmes publiés atteignent dès leur première année en mode historique (aucun en mode cadre).

- Test rouge puis vert : `tests/test_calendrier_impulsion.py` (nouveau) — pour chaque famille (dépense courante en
  hausse et en baisse, transferts, investissement, impôts en hausse et en baisse, SMIC, fraude fiscale) et dans les
  deux modes : impulsion stockée l'année du budget, effort ex ante de ±1 point exactement, écart de croissance de
  l'année égal à −k × impulsion × profil(0) ; année d'avant inchangée ; montant fixe rapporté au PIB hors effet
  propre (et non au PIB final) ; aucune trace de l'évaluation dans l'état (42 mini-scénarios, deux modes) ni dans
  les sorties et le rapport (avis, corrections, écrêtages, levier en échec, plafonds) ; niveaux toujours passés par
  `simulate()` ; prix de l'année identiques dans les deux évaluations. Rouge sur l'état d'avant : 37 sur 37.
- Gardes ajoutées à la revue adverse du lot : un choc de conjoncture observé n'entre pas dans l'impulsion de son
  année (les impulsions stockées sont exactement les variations des niveaux évalués hors effet propre, l'année du
  choc comprise ; rouge si le choc contamine l'impulsion) ; somme des impulsions égale au niveau publié, exactement,
  quand la rétroaction keynésienne est neutralisée (deux modes) ; gros choc de 2 points gardé : l'écart au miroir
  est exactement la part écrêtée par le filet de croissance, et le miroir revient filet levé ; limite du filet liée
  aux instantanés.
- Banc des multiplicateurs : niveau à 4 ans de 9 à 13 % sous les cibles à coefficients inchangés ; marqué en échec
  attendu strict jusqu'au commit de paramètres.
- Re-déclarés un par un, motif daté dans chaque test : bancs d'effet direct de l'année d'entrée (solde égal aux
  euros du levier, pouvoir d'achat égal au statu quo, indépendance de deux leviers, coût d'une réforme, passage de
  la TVA réduite dans les prix) dans un laboratoire sans rétroaction keynésienne (`tests/effets_directs.py`,
  multiplicateurs nuls), le moteur complet gardant le signe et l'ordre de grandeur ; espions de la chaîne organique,
  des lecteurs latéraux et des handlers (appels de l'évaluation hors effet propre exclus ou acceptés par égalité) ;
  ordre des appels ; somme des impulsions (exacte au niveau évalué hors effet propre, à 1 % du niveau publié) ;
  choc de demande observé (valorisation du budget de l'année au PIB qui contient le choc, filet de croissance,
  hystérèse du chômage) ; flux vers l'étranger (valorisation des autres leviers) ; miroir de la dépense courante
  (horizons 0 à 5 ; 1,5 point sous le filet, 2 points à la part écrêtée près) ; miroir du curseur de la défense
  (4e année d'effet à 1 %, année calendaire d'avant le lot à 1,5 %, le curseur étant un montant fixe en Md€) ; recette
  exceptionnelle (frein l'année même) ; ancrage de l'assiette (D3) ; cas public d'hystérèse du potentiel ; valeurs
  datées (V2-02, V2-03) ; forme de l'effet d'offre de l'investissement vert (plus de passage à un coût dans le
  domaine) ; réponse des prix comparée à ThreeME et Mésange.
- Instantanés régénérés une fois : 41 mini-scénarios sur 42 bougent (tous ceux dont un levier porte une impulsion),
  les dix scénarios publiés des deux modes. Statu quo en mode historique identique au bit ; en mode cadre, le droit
  en vigueur 2026-2027 agit un an plus tôt : 2026 inchangé (atterrissage), croissance 2027 +0,08 point, dette 2032
  −0,03 point. Pouvoir d'achat 2029 figé non modifié (revue humaine).
- Effet (mode cadre 2028, dix scénarios publiés, dette 2032, coefficients inchangés) : de −2,95 point (la plus
  forte relance) à +3,32 (le plus fort effort de consolidation) ; référence −0,03. Le retard avantageait les
  programmes qui consolident.
- Pile d'intégration (reporté après le lot 2, mesuré contre le lot 2) : de −2,89 à +3,32 point de dette 2032 ;
  référence −0,03. Chiffres « moteur actuel » du lot 2 recalculés sur la pile (recherche +5 Md€ par an : dette 2032
  −1,52 point et −15,3 Md€ au lieu de −1,35 et −10,3 ; table des variantes ; courbe de l'investissement vert) ; la
  propriété « effet total par euro au-dessus de la cible » attend le recalage du commit de paramètres suivant.
- Docs : METHODOLOGIE (« Calendrier de l'impulsion » : sources, règle, correction, pistes écartées, limites,
  profils ; boucle annuelle ; chiffres liés à la mesure), EXPLICATION (séquence annuelle en français courant),
  infobulle du registre (`policy_measures.json`) de la recette exceptionnelle (« freine la croissance la même
  année »).
## [non publiée — proposée] — équations du lot 2 : effet d'offre de la recherche publique

**Statut** : proposée, non publiée, sans numéro de version. Commits d'ÉQUATION, un par équation, qui supposent
appliqués le lot 1 et le lot 5 ci-dessous ; aucun paramètre ne change. Arbitrage du mainteneur des 15 et
16/11/2026. Règle suivie : aucune convention inventée ; une forme ou une constante vient d'une source rouverte,
sinon le point reste en l'état et il est déclaré.

**(1) Recherche publique en forme stock, effet l'année qui suit la dépense.** Le bonus de croissance potentielle
du canal suivait la dépense de l'année, et seulement après cinq années consécutives d'écart au défaut : une
dépense d'une seule année n'avait aucun effet, un programme commencé en 2028 n'agissait pas avant 2033, et un
surcroît de dépense qui dure n'était jamais usé. Le moteur suit désormais le stock de recherche ajouté par le
programme (inventaire permanent : chaque année, 15 % de dépréciation et l'écart de dépense de l'année), et le
bonus de l'année suivante vaut 0,032 point par Md€ ajouté au stock. Source : l'étude de la Réserve fédérale de
Dallas dont le moteur tire déjà l'élasticité (Fieldhouse & Mertens, WP 2305, rév. 11/2024), qui relie la
productivité au stock sans délai propre (éq. (6)) et vérifie ce calendrier dans son annexe E.1 ; réserves : une
hypothèse vérifiée, pas un délai mesuré, sur données américaines, sans source française. Les « 8 à 15 ans »
cités jusqu'ici séparent un vote de crédits de l'effet, pas une dépense de l'effet. Dépréciation de 15 % : OCDE
2001 et Khan & Luintel 2006 (0,16 au BEA selon Fieldhouse & Mertens), inchangée. Les autres canaux (capital
public de l'État et des collectivités, rénovation, éducation) restent dans le flux : la dépréciation et le délai
d'une forme stock n'ont pas de source rouverte pour eux. Test : `tests/test_offre_recherche_stock.py`
(inventaire permanent exact, effet dès l'année qui suit le début du programme dans les deux modes, gain
temporaire d'une dépense d'une seule année, coupe et hausse en miroir sur le stock, budget par défaut sans effet,
stock remis à zéro entre deux simulations du même objet).
Golden master isolé : seuls bougent les trois scénarios publiés qui augmentent la recherche, dans chaque mode, et
le mini-scénario de la recherche. Mesuré (mode cadre 2028, dix scénarios publiés, par rapport au lot 5) : dette
2032 de −1,81 à −1,13 point, déficit 2032 de +0,28 à +0,45, croissance moyenne 2028-2032 de +0,08 à +0,13 point ;
les sept autres scénarios sont identiques au bit ; cinq rangs de dette 2032 et deux rangs de déficit changent,
aucun rang de croissance. Limite de cet état, retirée au point (2) : la saturation commune vers ±0,20 pt
s'applique encore au pas annuel du stock. Tests re-déclarés avec motif daté : la table des canaux (délai de la
recherche 5 → 0), les attendus de forme, de profil et de solde (`test_effet_offre_echelle_v0612.py`), les
valeurs V2-02 du potentiel publié ; les deux tests « une année sans effet » et « retour au défaut » de la
recherche, propres à la forme flux, sont remplacés par le contrat du stock. Instantanés régénérés ; pouvoir
d'achat 2029 figé non modifié (dans sa tolérance).

**(2) Recherche publique : forme logarithmique, hors du plafond.** Le gain de la recherche n'est plus plafonné à
0,20 point par an : ce plafond, convention de la v3.1, n'avait aucune source et pesait surtout sur le plus gros
programme de recherche. À la place, la forme à élasticité constante que la même étude donne pour calibrer un
modèle : 0,06 × la variation du logarithme du stock (187 Md€ au départ, plus le stock ajouté). Rendements
décroissants doux, sans borne commune ; une coupe pèse plus qu'une hausse du même montant, d'autant plus que
le montant est grand (à long terme, 4 % de plus pour 1 Md€ par an, 45 % pour la plus forte coupe) ; une dépense
d'une seule année laisse un niveau acquis positif (la limite du point (1) disparaît). Le plafond ne porte plus
que sur la somme des canaux en flux (capital public de l'État et des collectivités, rénovation, éducation) : les
en retirer sans forme stock rendrait leur effet de niveau illimité ; point ouvert, lié à leur forme stock, qui
attend une source pour sa dépréciation et son délai. La constante `OFFRE_PENTE_RD_PUBLIQUE` est retirée (le canal
lit l'élasticité et le stock). Test : `tests/test_offre_recherche_stock.py` (forme exacte, aucun plafond pour la
recherche, niveau acquis ε × ln(1 + A/K), rendements décroissants doux, coupe plus lourde qu'une hausse du même
montant — jusqu'à 45 % à long terme pour la plus forte coupe du levier, 22 % après cinq ans —, stock de départ
jamais épuisé sur le domaine du levier). Golden master isolé : seuls bougent les mêmes cas qu'au point (1).
Mesuré (mode cadre 2028, par rapport au point (1)) : dette 2032 de −1,59 à −0,31 point, déficit 2032 de +0,09 à
+0,43, croissance moyenne 2028-2032 de +0,026 à +0,134 pour les trois programmes qui augmentent la recherche ;
les sept autres scénarios identiques au bit ; deux rangs de dette 2032, deux de déficit et deux de croissance
changent. Deux variantes de sensibilité, publiées dans METHODOLOGIE seulement et liées à la mesure par
`tests/test_offre_recherche_variantes.py` : effet deux ans après la dépense (OCDE 2001), 30 % d'une hausse
absorbés par les salaires des chercheurs (Goolsbee 1998 : bas de sa fourchette de 30 à 50 %, le cas calculé pour
l'ensemble de la recherche). Déclaré, chiffres liés à la mesure par `tests/test_offre_chiffres_publies_lot2.py` :
une hausse de la recherche se rembourse dans le moteur avant la fin du mandat, en part du PIB et en euros (5 Md€
de plus par an sur le droit en vigueur, mode cadre : dette 2032 plus basse de 1,35 point et de 10,3 Md€, solde
2032 meilleur de 8,3 Md€), conséquence de l'étude source, dont le rendement estimé (1,71 € de PIB par an et par
euro de stock, intervalle 1,07 à 2,22) dépasse celui du moteur (0,96 à 1,14), avec ses réserves (étude
américaine, calendrier posé puis jugé raisonnable, plus gros programme publié hors du domaine estimé) ; le
périmètre du stock (élasticité du stock civil appliquée à un stock qui comprend la recherche de défense des
administrations : effet par euro un peu sous-estimé) ; pour les leviers d'investissement, un effet total par euro
au-dessus de la cible publiée, la demande étant calée sur un effet total qui contient déjà l'offre — raison du
plafond conservé pour les canaux en flux. Points ouverts pour une release de paramètres : stock de départ figé en
euros de 2025, formule de l'OCDE, durée de vie retenue par l'Insee. Tests re-déclarés avec motif daté : la forme attendue
et la symétrie exacte de la recherche, sa sortie du plafond (borne du gros programme, seuils et ordres de
grandeur de la recherche), la constante retirée (`test_effet_offre_echelle_v0612.py`), les valeurs V2-02.
Instantanés régénérés ; pouvoir d'achat 2029 figé non modifié (dans sa tolérance).

**(3) Transition écologique : retour fiscal propre retiré.** Le levier ajoutait à ses recettes 0 %, puis 5 %,
puis 8 % de sa dépense d'investissement et de rénovation. Double compte : les recettes du moteur suivent déjà le
PIB nominal (élasticité 1,0), qui porte les impôts de l'activité induite ; ni l'investissement des collectivités
ni la recherche ne recevaient ce surplus. Les deux références citées (OCDE, « Getting Infrastructure Right » ;
« Cour des comptes 2023 ») ne contiennent pas ce chiffre ou sont introuvables. Retiré sans remplacement : 10 Md€
par an investis par l'État ou par les collectivités donnent désormais la même dette, au bit. Test :
`tests/test_transition_sans_retour_fiscal.py` (recettes propres limitées à la taxe carbone ; garde « pas
d'autofinancement » sur le levier réel, que les gardes de calibrage ne couvraient pas : dette et déficit plus
lourds en euros chaque année de 2028 à 2035, investissement et rénovation, et part des recettes dans le PIB
jamais relevée, rouge avec l'ancien barème comme avec un retour qui rembourserait la dépense ; même effet que
l'investissement local ; propriété générique sur les cinq leviers d'investissement — transition, rénovation,
collectivités, recherche, éducation — : aucune recette propre dans les impacts utilisés par le moteur, rouge si un
retour fiscal est remis hors du handler). Golden master isolé : bougent les quatre scénarios publiés qui
investissent dans la transition (deux modes), le mini-scénario du levier et un delta de référence. Mesuré (mode
cadre 2028, par rapport au point (2)) : dette 2032 de +0,01 à +0,04 point, déficit 2032 au plus −0,03 ; aucun
rang ne change ; six scénarios identiques au bit. Tests re-déclarés avec motif daté : l'horloge d'un calendrier
« une seule année » (`test_release_e_w1.py`, plus de recette propre qui distingue la cinquième année), la
docstring de l'investissement local, les chiffres liés de l'encadré du curseur vert (le coût l'emporte désormais
entre 10 et 20 Md€/an) et de l'investissement local (désormais égal à celui de l'État). Instantanés régénérés ;
pouvoir d'achat 2029 figé non modifié (dans sa tolérance).

**Cumul du lot** (mode cadre 2028, dix scénarios publiés, par rapport au lot 5) : les trois programmes qui
augmentent la recherche, dette 2032 de −3,37 à −1,67 point, déficit 2032 de +0,41 à +0,86, croissance moyenne
2028-2032 de +0,134 à +0,266 point ; deux autres programmes, +0,01 et +0,02 point de dette 2032 (retour fiscal
retiré) ; les cinq autres scénarios identiques au bit. Rangs : six rangs de dette 2032, trois de déficit et deux de
croissance changent. Points laissés ouverts, déclarés dans METHODOLOGIE : la forme stock des canaux de capital
public (dépréciation et délai sans source arrêtée) et leur plafond, qui relèvent d'un calage conjoint de la demande
et de l'offre ; le stock de départ de la recherche (euros de 2025, formule de l'OCDE, durée de vie retenue par
l'Insee), qui relève d'une release de paramètres.

Pile d'intégration : les chiffres de ce bloc sont ceux du lot contre son parent (lot 5), inchangé dans la pile ; les
chiffres « moteur actuel » de METHODOLOGIE qui en viennent sont recalculés au report du lot 6 (bloc du lot 6).

## [non publiée — proposée] — équations du lot 5 : dépense courante symétrique en signe

**Statut** : proposée, non publiée, sans numéro de version. Commit d'ÉQUATION, distinct des deux blocs du lot 1
ci-dessous, qu'il suppose appliqués. Aucun coefficient ne change.

**Le défaut.** Convention du mainteneur (v0.6.7) : pas d'asymétrie de signe retenue — même instrument, même
coefficient, en hausse comme en baisse. C'est une convention, pas un résultat de la méta-analyse citée pour les
valeurs (Gechert 2015, qui classe par instrument et ne teste pas le signe). Elle valait pour
les transferts, les impôts et l'investissement, pas pour la dépense courante (ni investissement productif, ni
levier de transfert : défense, dotations des collectivités, postes et point d'indice, réforme de l'État, crédits
des ministères, moyens de soins, santé, subventions aux grandes entreprises, aide médicale de l'État et
intégration). Sa baisse prenait `MULT_COUPE_DEPENSES` ; sa hausse, `MULT_TRANSFERTS`, parce que la branche
« expansion » de `FiscalMultipliers.get_multiplier` versait toute dépense hors investissement dans la case des
transferts. Pour un point de PIB permanent : 0,74 point de PIB à 4 ans en hausse, 0,79 en baisse. L'asymétrie
était déclarée au lot 1 (encadré « Portée à déclarer »).

**La correction.** La branche « expansion » reprend la partition de la branche « consolidation » : la part
« transferts » est celle que la composition déclare, le reste de la dépense hors investissement est de la
dépense courante, au coefficient de sa coupe (`base_multipliers['expansion']['spending_based']` =
`MULT_COUPE_DEPENSES`, k = 0,74). La voie inverse, abaisser la coupe au niveau des transferts, a été écartée par le
mainteneur. Transferts, impôts, investissement, coefficients propres (SMIC, fraude fiscale) et profils de
décroissance ne changent pas ; la fourchette ×0,75 / ×1,25 des fiches multiplie la même constante dans les deux
sens. Limite déclarée : une étude par signe (Barnichon, Debortoli & Matthes, Review of Economic Studies 89(1),
2022) trouve, sur données américaines, un multiplicateur d'une baisse de dépense au-dessus de 1 et celui d'une
hausse nettement en dessous de 1 ; le moteur ne représente pas cette asymétrie, et l'ancien écart (0,79 contre
0,74) ne la représentait pas non plus : il venait d'un trou de classement, pour la seule dépense courante. Une
asymétrie de signe sourcée, pour toutes les familles, relève d'une instruction séparée.

- Test rouge puis vert : `tests/test_symetrie_depense_courante.py` (nouveau). Ce qu'il garde, vérifiable dans le
  fichier :
  - **leviers** : tous ceux dont une hausse est de la dépense courante, dérivés du registre des paramètres
    (`PARAM_DOMAINS` et `INTENSITE_DOMAINS`, chaque paramètre porté seul à chaque borne) et non d'une liste :
    défense, dotations des collectivités, crédits des ministères et moyens de soins, postes et point d'indice,
    réforme de l'État, aide médicale de l'État et intégration, santé, subventions aux grandes entreprises, plus un
    levier synthétique absent de toute liste ; un test vérifie que chaque levier de dépense du registre est rangé
    dans une famille gardée par un test (investissement, transferts, coefficient propre, hors demande intérieure,
    dépense courante) ;
  - **miroir** : hausse et baisse permanentes d'un point de PIB, effet sur le PIB réel à 1 % près, à 1, 2, 3, 4, 5
    et 6 ans, dans cinq états (banc historique, mode cadre 2028, dette à 160 % du PIB, écarts de production à −3 %
    et à +1,5 %), sans neutraliser aucune non-linéarité : écart de 5 à 10 % avant, au plus 0,7 % après ; au-delà de
    6 ans le niveau revient vers zéro et le rapport n'est plus une mesure. La première année, miroir à 0,1 % près
    pour une dette à 180 % ou à 85 % du PIB et pour un choc de 2 points de PIB. Même miroir par le curseur de
    défense (±10 Md€ ; 1,089 et 1,031 avant, 1,007 après) ;
  - **aucun autre chemin** : sans hausse de dépense courante, donner une autre valeur au nouveau coefficient laisse
    toutes les sorties identiques au bit (transferts, impôts, investissement, coupes, dans les deux sens) ; pendant
    des simulations complètes, il entre dans un appel si et seulement si l'appel est une hausse de dépense
    courante ; à la table, hausse = coupe pour chaque levier de dépense courante, dans quatre régimes.
  Banc des multiplicateurs : famille « hausse de dépense courante », cible et tolérance de la coupe (0,735 avant,
  rouge ; 0,795 après). Le miroir porte sur le PIB, pas sur la dette (limite déclarée dans METHODOLOGIE).
- Golden master isolé : l'état d'avant, instrumenté, liste les cas où une hausse de dépense courante est active ;
  seuls ceux-là bougent, les autres sont identiques au bit en pleine précision. En mode cadre, le droit en vigueur
  de 2026-2027 relève la défense : toute simulation en mode cadre est concernée, la référence sans programme
  comprise. Bougent : les dix scénarios publiés des deux modes et 4 mini-scénarios sur 42 (3 à la précision des
  instantanés : le quatrième bouge de 0,0002 point de dette) ; restent identiques au bit : 38 mini-scénarios et
  le statu quo du mode historique. Colonnes : dette, déficit, croissance, chômage, inflation, pouvoir d'achat ;
  Gini (au plus 1e-7, aucun instantané) et compétitivité (au plus 0,0003 point d'indice, un instantané par
  arrondi) par des effets émis qui suivent l'économie. Delta de référence (`scenario_deltas_baseline.json`)
  régénéré, comme au lot 1 (statu quo du mode historique identique au bit ; les écarts des trois scénarios
  bougent, jusqu'à −1,02 point de dette 2035).
- Effet (mode cadre 2028, dix scénarios publiés, par rapport au lot 1) : dette 2032 de −0,61 à −0,09 point,
  déficit 2032 de +0,01 à +0,12, croissance moyenne 2028-2032 au plus +0,023 point, chômage 2032 au plus −0,04,
  inflation 2032 au plus +0,03. Rangs : deux programmes échangent les 2ᵉ et 3ᵉ rangs de croissance moyenne, deux
  autres les 5ᵉ et 6ᵉ rangs de chômage 2032 ; dette, déficit et Gini inchangés.
- Tests re-déclarés : W2-11 (crédits des ministères ≡ défense) — l'écart documenté pour une baisse en mode cadre
  venait de cette asymétrie ; l'équivalence vaut désormais dans les deux sens et les deux modes. Chiffres liés à
  la mesure mis à jour : tableau des familles (nouvelle ligne), cadre temporel (2027), scénario de référence et
  corridor de la mission, investissement local, effet d'offre « échelle » (encadré et docstring), banc de prix de
  l'encadré d'inflation, « Marge à déclarer » du déflateur (corridor de dette 1,27 pt, resté à 1,21 ; désormais lié
  à la mesure par `tests/test_phillips_v061.py`). Docstrings de trois tests qui décrivaient l'ancienne règle.
  Pouvoir d'achat 2029 figé (revue humaine) non modifié : sa tolérance absorbe l'écart (au plus 0,3 point).
- Docs : METHODOLOGIE (encadré du lot 1 marqué traité, nouvel encadré, tableau des familles, table de base —
  dont deux valeurs restées à leur état d'avant le lot 1, 0,71 et 0,63, remises à 0,688 et 0,615 —,
  `depenses_publiques`, limite 8 : symétrie vérifiée sur le PIB, pas sur la dette, qui n'est plus en miroir quand
  la prime de taux est plafonnée, préexistant, toutes familles), EXPLICATION (table et note en français courant).
  La symétrie de signe n'est plus attribuée à la méta-analyse citée, y compris dans les lignes antérieures sur les
  transferts et l'investissement. Classements à arbitrer, non modifiés (soumis au mainteneur ; un changement
  ferait l'objet d'un commit d'équation distinct) : le point d'indice de la fonction publique, que le revenu des
  ménages traite comme un revenu versé aux agents et la croissance comme de la dépense courante — pris seul au
  coefficient des transferts, il relèverait de 0,28 et 0,29 point la dette 2032 (mode cadre) des deux programmes
  publiés qui le relèvent ; l'Ondam, l'aide médicale de l'État, les transferts en capital aux ménages, les
  subventions aux entreprises, la dotation des collectivités ; et la dynamique de la santé, qui diffère selon le
  levier qui la porte (profil de l'investissement pour `sante`, des impôts pour les moyens de soins).

## [non publiée — proposée] — paramètres du lot 1 : coefficient des transferts recalé

**Statut** : proposée, non publiée, sans numéro de version. Release de PARAMÈTRES, distincte du bloc
« équations » ci-dessous, qu'elle suppose appliqué : aucune équation ne change ici.

**Coefficient des transferts recalé.** `MULT_TRANSFERTS` 0,71 → 0,688. Le 0,71 était calé sur une relance
100 % transferts sous éviction ; l'éviction retirée, il donnait 0,672 à 4 ans au lieu de la cible de 0,65
(Gechert 2015). Bissection sur le banc de `tests/test_multiplicateurs_centraux_v067.py`, moteur sans les
trois mécanismes retirés : 0,6882 ; hausse et coupe de transferts à 0,650 ; tolérance de la famille
resserrée de 5 % à 1 % (rouge à 0,71). Un calage fait avant le retrait du terme d'effort de l'inflation
(éviction seule neutralisée) donnait 0,684 ; sur l'état final, 0,684 ne donne que 0,646. Aucun autre
paramètre ne bouge, la pente de Phillips notamment. Effet (mode cadre 2028, dix scénarios publiés, par
rapport au bloc « équations ») : dette 2032 de −0,06 à +0,39 point ; deux programmes s'échangent les 2ᵉ et
3ᵉ rangs de croissance moyenne (écart 0,002 point). Portée déclarée : en expansion, ce coefficient vaut
pour toute dépense hors investissement, alors qu'une coupe de dépense courante prend
`MULT_COUPE_DEPENSES` (0,80 à 4 ans) : asymétrie de signe antérieure au lot, signalée, non traitée.
Valeurs V2-03 re-déclarées ; chiffres liés à la mesure (tableau des familles, investissement local,
encadré d'effet d'offre, banc de prix de l'encadré d'inflation) mis à jour ; pouvoir d'achat 2029 figé
non modifié.

**Cumul des deux blocs** (équations puis paramètres ; mode cadre 2028, dix scénarios publiés, par rapport
à v0.8.1) : dette 2032 de −2,70 à +1,33 point, déficit 2032 de −0,18 à +0,36, croissance moyenne 2028-2032
de −0,009 à +0,075 point, dette 2035 de −5,73 à +2,66 ; Gini et compétitivité inchangés. Rangs : trois
rangs de dette 2032 changent entre trois scénarios qui se tiennent en 0,26 point ; deux rangs de
croissance s'échangent ; déficit et Gini inchangés. Preuve d'équivalence : les trois mécanismes
neutralisés en mémoire dans la v0.8.1, avec ce coefficient, donnent des sorties identiques au bit au
code de ce commit. Les trois mécanismes retirés étaient asymétriques : deux pénalisaient les programmes
qui consolident (inflation, cicatrice), un ceux qui relancent (éviction) ; le premier domine.

## [non publiée — proposée] — équations du lot 1 : mécanismes macro sans source retirés

**Statut** : proposée, non publiée, sans numéro de version (la version du code reste v0.8.1 tant que
l'arbitrage du mainteneur n'a pas fixé la publication). Ce bloc regroupe les commits d'ÉQUATION du lot ;
les paramètres recalés en conséquence forment un bloc distinct (release de paramètres). Règle suivie :
un mécanisme reste s'il est conforme à la littérature et non redondant. Chaque retrait est un commit
distinct, avec son test de propriété (rouge sur l'état d'avant, vert après), ses instantanés régénérés
une fois et un contrôle « golden master isolé » : seuls bougent les scénarios où le mécanisme jouait.
Preuve d'équivalence, pour chaque retrait : le mécanisme neutralisé en mémoire sur la v0.8.1 donne des
sorties identiques au bit à celles du code du commit (dix scénarios publiés, deux modes).

**(1) Inflation : terme d'effort budgétaire retiré.** `calculate_inflation` ajoutait −0,12 × effort
(consolidation) ou +0,08 × |effort| (expansion), chaque année tant que l'effort durait. Dette déclarée
depuis v0.6.1 (I18) : non sourcé, asymétrique, en double compte avec l'écart de production et, appliqué
à un niveau d'effort, il faisait dériver le niveau des prix sans fin (choc permanent d'un point de PIB :
écart d'inflation de +0,12 à −0,19 point à 20 ans). Aucun des modèles institutionnels lus (Mésange,
ThreeME, quinze modèles du SEBC) n'a de terme direct de l'effort global sur les prix. Les études
empiriques lues mesurent un effet total ; l'une (BCE, document de travail 2996, 2024) trouve une réponse
des prix aux relances amplifiée quand la dette est haute : le moteur ne la modélise pas, limite déclarée
(inflation des relances probablement sous-estimée), que l'ancien terme, indépendant de la dette, ne
représentait pas non plus. Retiré sans remplacement : le budget ne touche plus les prix que par l'écart
de production et le passage de la TVA ; l'état transmis à `calculate_inflation` ne porte plus d'effort.
Limite déclarée : à 5 ans, le moteur répond en prix moins que les deux modèles français publiés (un peu
plus de la moitié de ThreeME, un tiers environ de Mésange, pour un point de PIB de dépense) ; l'effet
des budgets sur les prix est donc probablement sous-estimé, dans les deux sens. La pente de la courbe de
Phillips, qui porte désormais seule cette réponse, est à instruire séparément (release de paramètres).
Test : `tests/test_inflation_sans_terme_d_effort.py` (chiffres du banc de prix de METHODOLOGIE liés à la
mesure). Mesuré (mode cadre 2028, dix scénarios publiés) :
dette 2032 de −1,89 à +1,24 point, déficit 2032 au plus ±0,16 point, croissance moyenne 2028-2032 au plus
+0,011 point, Gini et compétitivité inchangés ; trois rangs de dette 2032 changent entre trois scénarios
qui se tiennent en 0,26 point. Sensibilité des curseurs : dans le scénario publié en forte consolidation,
1 Md€ de défense de plus augmente la dette 2035 de 0,072 point au lieu de 0,031 (mode cadre, pleine
précision) ; le terme désinflait les consolidations et y compensait une partie de toute dépense
supplémentaire. Instantanés :
les dix scénarios des deux modes et 41 des 42 mini-scénarios bougent (tous ceux où l'effort n'était pas
nul), aucune colonne Gini ni compétitivité. Tests re-déclarés (motif daté dans chacun) : valeurs V2-03
(gels totaux) et V2-02 (potentiel 2030) ; effet d'offre « échelle » (décroissance lue sur l'effet signé
par Md€, chiffres de sa docstring et de l'encadré de METHODOLOGIE liés à la mesure, sur le droit en
vigueur livré avec le moteur : la garde tourne aussi en CI publique) ; investissement
local (écart absolu ; le rapport de deux effets proches de zéro sort de son intervalle à cet état ;
chiffres publiés liés à la mesure) ; W2-15 (f) ; trois tests unitaires d'inflation ; tableau des
familles de multiplicateurs lié à la mesure ; garde de discontinuités étendue à tous les scénarios
publiés, avec une contre-épreuve sur un scénario synthétique (elle ne dépend plus d'aucun programme
publié et tourne aussi en CI publique) ; delta de référence régénéré. Le pouvoir d'achat 2029 figé
(`pa_2029_figes.json`, revue humaine) n'est pas modifié : sa tolérance absorbe l'écart.

**(2) Croissance : cicatrice d'austérité retirée.** `calculate_growth` ôtait 0,10 × (effort intérieur
− 3 % du PIB), plafonné à 0,3 point par an, aux seules consolidations. Le seuil avait été choisi pour
que l'utilisateur trouve toujours une solution viable. Les deux sources citées (DeLong & Summers 2012,
Fatás & Summers 2016-2018) décrivent un effet de niveau sur le potentiel, proportionnel à l'impulsion,
propre aux économies déprimées à la borne zéro des taux : ni seuil, ni plafond, ni sens unique. Elle
doublait les multiplicateurs, calés sur l'effet de niveau à 4 ans mesuré. Retirée sans remplacement ;
l'effort intérieur, qui n'avait plus d'autre lecteur, est retiré avec elle (le principe qu'il portait
reste tenu par les impulsions : un flux vers un agent non résident n'en stocke aucune). L'hystérèse du
potentiel (`update_potential_growth`) n'est pas touchée. Test : `tests/test_cicatrice_retiree.py`
(croissance invariante au niveau de consolidation ; linéaire dans l'impulsion ; multiplicateur effectif
constant à 2 % près de 1 % à 8 % du PIB, deux non-linéarités légitimes neutralisées et déclarées dans le
test, et de 1 % à 6,5 % du PIB sans aucune neutralisation ; rouge sur l'état d'avant : +5 à +6 % dès
3,5 %, et une cicatrice réintroduite par un autre chemin avec un seuil de 3,5 %, 4 % ou 5 %, ou réservée
aux économies déprimées avec un seuil de 2 % à 5 %, le fait rougir aussi ; limite déclarée du harnais :
le choc est injecté après `apply_measures`). Effet isolé sur v0.8.1 (mode cadre 2028) : un
scénario publié bouge en 2032 (dette −0,92 point, déficit +0,23, croissance moyenne +0,067), un second en
2035 seulement (−0,17) ; les huit autres sont identiques au bit ; aucun rang ne change. Preuve
d'équivalence : l'effort intérieur borné à 3 % en mémoire dans la v0.8.1 donne des sorties identiques au
bit à la v0.8.1 privée de ce seul bloc, et au code de ce commit (après le commit précédent).
Sensibilité des curseurs : dans le scénario publié en forte consolidation, 1 Md€ de défense de plus
augmente la dette 2035 de 0,124 point au lieu de 0,072 (mode cadre, pleine précision ; 0,031 en v0.8.1) :
une dépense de plus n'y est plus compensée en grande partie par la cicatrice ; elle coûte désormais à
peine moins que dans les neuf autres programmes publiés (de 0,129 à 0,179 point, même mesure).
Instantanés : deux scénarios dans chaque mode, un mini-scénario.
Tests re-déclarés : deux tests de croissance du simulateur ; les deux tests W2-15 (f) (le flux vers
l'étranger ne change la croissance de t+1 que par la traînée de dette, même sur une consolidation sévère).
Docs : la phrase de `SCENARIOS_POLITIQUES.md` qui citait des « effets de confiance plafonnés »
(inexistants depuis v0.6.0) et la cicatrice est corrigée.

**(3) Croissance : éviction (« crowding-out ») retirée** (arbitrage du mainteneur du 21/10/2026,
« option C », appliqué après deux reports). `calculate_growth` ôtait intensité × effort net de t−1 aux
seules relances au-delà de 100 % du PIB de dette (intensité 0,002 à 0,008 selon la part
d'investissement productif de la relance ; coefficients déclarés sans source). La littérature lue
trouve un multiplicateur plus faible quand la dette est haute, avec des modèles linéaires dans le signe
du choc ; aucune étude lue ne réserve l'effet aux relances. Retirés : `effet_eviction`,
`intensite_eviction`, `part_investissement_expansion`, les trois constantes `EVICTION_*`, et la
plomberie devenue sans lecteur (effort net et part d'investissement transmis à la croissance, états
`_budget_effort_prev` et `_part_investissement_prev`) ; l'effort de l'année reste calculé pour la prime
de taux et la colonne publiée. **Ce que fait le ×0,95 « dette élevée » restant (inchangé)** : dans tout
le domaine publié (dix scénarios, deux modes, banc de calibrage), la dette lue dépasse son seuil de
110 % ; le facteur s'applique donc à tous les appels et il est absorbé par la calibration des
coefficients. Après ce retrait, aucune réduction des multiplicateurs liée au niveau de dette n'est
modélisée dans le domaine publié ; la dette agit par la traînée sur le potentiel et par la prime de
taux. Le facteur reste une marche à 110 %, inerte dans ce domaine : dette de modèle déclarée, gardée par
un test qui rougit le jour où un scénario publié lit une dette sous le seuil. **Paramètre admis dans ce
commit d'équation** : `MULT_BAISSE_IMPOTS` 0,63 → 0,615 (= hausse). Le 0,63 compensait l'éviction d'une
relance 100 % baisse d'impôts ; sans elle, la baisse valait 3,6 % de plus que la hausse et le test de
symétrie à ±3 % rougissait ; appliqué avant le retrait, il le faisait rougir dans l'autre sens (0,964) :
aucun ordre de commits ne l'évite. **Les deux effets, séparés** (mode cadre 2028, dix scénarios
publiés, dette 2032, par rapport au point (2)) : le retrait de l'éviction seul, de −0,15 à −0,00 point ;
le coefficient seul, de +0,02 à +0,22 ; la somme, de −0,10 à +0,14 (déficit 2032 au plus ±0,03,
croissance moyenne au plus ±0,007 point ; aucun rang ne change). Pour sept scénarios sur dix, le
coefficient pèse plus que le retrait, et en sens inverse. En mode historique (dette 2035), le retrait
seul va jusqu'à −1,06 point, le coefficient seul jusqu'à +0,33. Preuve d'équivalence : l'éviction
neutralisée en mémoire dans la v0.8.1 (intensités nulles, coefficient 0,615) donne des sorties
identiques au bit à la v0.8.1 privée de ce seul retrait, et au code de ce commit. Asymétrie coupe/hausse
de transferts : 0,1 % (3,8 % avant). Test : `tests/test_eviction_retiree.py` (croissance invariante à
l'effort net ; coupe et hausse de transferts de même ampleur à 1 % près, dette au-delà de 100 % ; aucun
symbole de l'éviction dans le moteur ; dette lue au-dessus du seuil du ×0,95 au banc, garde publique, et
dans le domaine publié, garde privée par nature, sautée sans les scénarios publiés). Instantanés : tous les scénarios publiés (chacun a une relance ou une baisse d'impôts),
16 mini-scénarios sur 42. Tests re-déclarés : `test_eviction_composition_v0610.py` (acte : la part et
l'éviction n'existent plus ; restent les flux du contre-exemple, la convention de flux des impulsions et
l'absence de marche au changement de signe de l'effort ; programme figé
`programme_fige_eviction_v0610.json` retiré avec ses deux tests), banc d'additivité à dette 116 %
(strictement additif), symétrie des transferts (un seul test, à 1 %), W2-15 (d) (une hausse du flux
vers l'étranger n'agit plus que par la traînée de dette), investissement local (le rapport local/État
revient dans son intervalle : les deux assertions sont gardées), valeurs V2-02.

## [v0.8.1] — 2026-11-12 — release de paramètres « P » : droit en vigueur daté, instantanés régénérés, textes publics, objectifs en part du PIB

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

**Corrections de la revue du moteur, avant publication** (un test rouge par point ; aucune équation ne
change ; golden masters, deltas de référence et standalone identiques au bit, sans régénération) :
- **Nombre non fini dans `/simulate` : 422, plus jamais 500.** Un `NaN`, un `Infinity` ou un littéral
  hors des flottants (`1e400`) dans un montant de calendrier `valeurs`, `profils.*.annee`,
  `profils.*.annees`, `annee_debut`, `periods` ou `rampe.annees` rendait un 500 : la réponse 422
  standard de FastAPI recopie l'entrée fautive (`input`), et un flottant non fini n'est pas sérialisable
  en JSON standard. La classe de route du `router` (`_RouteEntreesNonFinies`, `api.py`) relance l'erreur
  avec ses nombres non finis écrits en texte (`"NaN"`, `"Infinity"`, `"-Infinity"`) ; toute autre réponse
  422 est inchangée au bit. Dans la classe de route, et non dans un gestionnaire de l'application : le
  correctif suit le routeur dans toute application qui l'inclut. Chaque refus de schéma est tracé
  (WARNING : emplacement et type, jamais la valeur reçue). `tests/test_api_nombres_non_finis_v081.py`.
- **Calendrier `valeurs` sans effet qui s'écarte de la référence : plus d'échec silencieux.** Quand le
  programme laisse le paramètre à sa référence (valeur égale ou absente de `mesures`), des montants
  datés différents de la référence étaient ignorés avec un simple avis, `report.valid` restant `true`.
  Désormais : 422 en strict (message qui nomme le paramètre et les années) ; en tolérant, l'entrée est
  ignorée et tracée comme correction (`report.valid = false`), comme toute entrée invalide. Un
  calendrier dont tous les montants égalent la référence reste accepté avec l'avis « calendrier sans
  effet ». Aucun scénario publié n'est concerné (chaque calendrier `valeurs` publié accompagne une
  valeur de programme différente de la référence).
- **Année d'un montant daté en chiffres ASCII seulement** (`[0-9]{4}`) : `\d{4}` admettait tout
  chiffre Unicode (« ٢٠٢٨ », que Python lit 2028).
- **Documenté, inchangé** : une année répétée dans l'objet JSON garde la dernière valeur (comportement
  standard du JSON, avant toute validation) ; aucune règle de monotonie ; un début ramené après
  l'atterrissage en tolérant ne décale jamais les montants (l'entrée est ignorée et tracée). Tests
  ajoutés pour les trois cas. Non traité (conception, noté) : en tolérant, un seul montant fautif fait
  ignorer tout le calendrier.

## [v0.8.0] — 2026-11-12 — release « E » : onze curseurs, déplafonnement des cotisations salariales, garde-fous, effet d'offre « échelle »

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
