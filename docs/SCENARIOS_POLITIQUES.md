# Scénarios politiques

**Date** : 2026-07-07
**Statut** : document canonique unique (remplace les anciens `PARAMETRES_SCENARIOS_POLITIQUES.md` et `SCENARIOS_POLITIQUES_SYNTHESE.md`)

> **Source unique.** Les paramètres injectés présentés plus bas sont générés automatiquement depuis le moteur (`frontend-react/src/data/scenarios.json`) — ils reflètent exactement ce que simule l'outil. La prose ci-dessous est volontairement **qualitative** : elle décrit l'orientation des scénarios sans réénoncer aucune valeur chiffrée d'un paramètre injecté, afin qu'aucune divergence ne puisse réapparaître entre le texte et le moteur.

---

## Avertissement

Cet outil est un simulateur citoyen indépendant, sans affiliation gouvernementale ni partisane. Les scénarios sont une interprétation des programmes et documents officiels disponibles, destinée à comparer des orientations budgétaires. Ils peuvent évoluer à mesure que les programmes sont précisés. Pour signaler une imprécision, contactez : contact@francebudget.fr.

---

## Les 10 scénarios

Le simulateur propose **10 scénarios** : le **budget 2026 voté** (scénario de référence), **8 programmes de candidats** et **1 scénario de think tank** produit par l'Institut Montaigne. Chaque scénario fixe l'ensemble des paramètres d'entrée du moteur ; le détail chiffré exact figure dans la section générée « Paramètres injectés ».

### Budget 2026 voté, réajusté sur l'exécution 2026
<!-- scenario:plf_2026 -->

- **Source** : LF 2026 (loi 2026-103 du 19 fév 2026)
- **Orientation** : consolidation budgétaire modérée, dans la continuité, avec préservation des acquis sociaux après amendements parlementaires. Trajectoire de réduction graduelle du déficit sans rupture fiscale ni sociale ; effort de maîtrise réparti sur les enveloppes ministérielles, hausse marquée de l'effort de défense, et fiscalité des grandes entreprises mobilisée à titre exceptionnel. C'est le scénario de référence « politique votée ».

#### Périmètre couvert : ce que ce scénario n'encode pas, et pourquoi

Ce scénario est **le point de départ du simulateur et le comparateur implicite de tous les
programmes de parti**. À ce titre, ce qu'il omet compte autant que ce qu'il pose : une mesure
votée mais non représentée déplace mécaniquement l'écart affiché de chaque programme. Le
périmètre est donc déclaré ici, dans les deux sens.

**Ne sont paramétrées que les mesures représentables par un levier existant du simulateur**, sans
lui faire dire autre chose que ce qu'il calcule. La décomposition mesure par mesure de référence
est le **Tableau 4 de l'OFCE, *Policy brief* n° 154 du 26 février 2026** (« Budget 2026 : un
déficit de compromis », Madec, Plane *et al.*) — la seule décomposition chiffrée de la loi
**votée** (et non du projet de loi) que la collecte de sources ait trouvée.

Mesures votées **non encodées**, avec leur montant 2026 tel que publié par l'OFCE et le motif :

| Mesure votée (LF / LFSS 2026) | Md€ 2026 | Sens sur le solde | Pourquoi elle n'est pas encodée |
|---|---:|---|---|
| Hausse du taux de cotisation **CNRACL** | 1,7 | recette | Le levier de cotisations du moteur porte sur la **masse salariale privée** et emporte un canal emploi et compétitivité calibré sur les entreprises. La CNRACL est le régime des agents des collectivités : l'encoder injecterait un choc d'emploi privé que la loi n'a pas voté. |
| Sortie du **bouclier tarifaire TICFE** | 1,0 | recette | La TICFE est une **accise**, le levier disponible est un **taux de TVA** sur l'énergie, déjà à son niveau plein. |
| **Taxe exceptionnelle sur les complémentaires santé** (2,05 %) | 1,0 | recette | Votée **pour la seule année 2026**. Tous les leviers du simulateur décrivent des flux permanents : l'encoder créerait une recette perpétuelle que la loi n'a pas votée. |
| Prorogation de la **CDHR** (contribution différentielle sur les hauts revenus) | 0,7 | recette | Même motif : une **prorogation d'un an** encodée dans un levier permanent reproduirait, en sens inverse, le biais que cette version corrige. |
| Renforcement du **malus écologique automobile** | 0,6 | recette | Aucun levier de fiscalité des véhicules n'existe dans le simulateur. |
| **PSR-UE** (contribution au budget de l'Union) | 5,7 | dépense | Aucun levier de prélèvement sur recettes au profit de l'UE. **C'est la plus grosse ligne non représentée, et elle joue CONTRE le scénario de référence.** |
| Hausse de la **prime d'activité** | 0,7 | dépense | Le levier de prestations du simulateur porte sur l'**indexation**, pas sur le barème d'une prestation isolée. |
| **Aide publique au développement** | 0,8 | dépense | Aucun levier d'APD. |

Sont en revanche **encodées** : la hausse de CSG sur les revenus financiers et la *flat tax*, et
l'effort demandé aux collectivités locales (dont Dilico). Deux réserves d'interprétation, à dire
plutôt qu'à taire : le levier CSG porte un **taux global**, la valeur posée est donc celle qui
produit le rendement voté sur l'assiette du levier, et l'effet sur le pouvoir d'achat s'y répartit
sur **tous** les ménages là où la loi ne vise que les revenus du capital — l'indicateur de pouvoir
d'achat du scénario de référence est donc, sur ce point, **pessimiste** ; le levier
« collectivités » est libellé en **dotations**, alors que l'effort voté transite en partie par
d'autres canaux.

Enfin, **la charge d'intérêts** (+5,8 Md€ en 2026) n'est pas un paramètre : elle est produite par
le bloc dette du moteur, à partir du stock et du taux apparent.

#### Ce que les paramètres encodés supposent

Les mesures ci-dessus sont celles que le scénario **n'encode pas**. Celles qu'il encode portent,
elles aussi, des choix de **périmètre** ou d'**hypothèse** — justifiés, mais qui ne se lisent pas
dans le chiffre. Les taire reviendrait à présenter comme des données ce qui est, en partie, une
convention. Aucune des cinq lignes ci-dessous ne change une valeur : elles la qualifient.

| Paramètre | Ce qu'il suppose, et qui ne se voit pas dans le chiffre |
|---|---|
| `fonction_publique.effectifs = -3 119` | C'est le **« total général » du tableau des schémas d'emplois** annexé au budget 2026 : périmètre ministères + opérateurs **+ caisses de sécurité sociale**, hors effet de la réforme de la formation des enseignants. **Sur le seul périmètre État, la loi crée +6 724 ETP** (ministères +8 381, opérateurs −1 728). Le chiffre retenu est donc celui de l'affichage gouvernemental, et non celui de l'État employeur. Effet sur le solde : **+0,19 Md€/an** — l'enjeu est **éditorial, pas numérique**, et il est dit ici pour cette raison. |
| `sante` (15 / 20 / 10) | Calé sur l'**année 1** (+1,28 Md€, prudent face aux 4,1 Md€ d'économies Sécurité sociale votées). Mais le moteur en fait un effort **structurel permanent de 4,98 Md€/an** à partir de 2030 (dont 0,33 Md€ des franchises réajustées à 120 % depuis le 08/11/2026). **La persistance est une hypothèse**, et une hypothèse discutable : une LFSS est **annuelle**, et son paquet d'économies est passé de **10,4** à **4,1** Md€ au cours du débat parlementaire. C'est le deuxième contributeur de l'effort résiduel du scénario de référence. |
| `niches_sociales_tge = 68` | Proxy de la réforme des **allègements généraux de cotisations** (Sénat, rapport général n° 139 t. II : **3,9** Md€ bruts / **3,1** Md€ nets en 2026). **L'assiette réelle est celle des rémunérations inférieures à 3 SMIC, tous employeurs** — et non les grandes entreprises que le nom du levier désigne. Les 2 Md€ encodés restent en deçà du chiffrage : conservateur, mais sur une assiette qui n'est pas celle du libellé. |
| `defense = 58` (57 votés) | 57,15 Md€ hors CAS Pensions est un montant **nominal**, et **nominal ≠ structurel** : l'OFCE (*Policy brief* n° 154) chiffre la dépense structurelle supplémentaire à **5,3** Md€ et non 6,7. Par ailleurs le +7 **constant** sur tout l'horizon **sous-représente les marches de la LPM** (+3,2 Md€/an) au-delà de 2027 : les deux écarts jouent en sens opposé et ne sont pas compensés l'un par l'autre. |
| `is_exceptionnel_tge = 0` (7,3 votés pour 2026) | 7,3 Md€ est le rendement **2026** de la contribution exceptionnelle sur les bénéfices des grandes entreprises (6,8 Md€ réajustés sur l'exécution 2026). Votée pour les deux premiers exercices clos à compter du 31 décembre 2025 (loi 2026-103, art. 12), elle n'est pas reconduite : 0 à partir de 2027, tant qu'aucune loi de finances pour 2027 n'est votée. Le projet de loi de finances pour 2027, qui la prorogeait, a été considéré comme rejeté par l'Assemblée nationale le 4 novembre 2026 (T.A. n° 362). Dans le moteur, c'est une valeur datée du droit en vigueur ; le scénario porte la valeur de 2028, premier budget du mandat. |

**Réajustement sur l'exécution 2026 (08/11/2026, v0.7.2).** Le scénario porte le budget voté
RÉAJUSTÉ, égal au point de départ du mode cadre : défense 58 Md€ (57 votés), franchises médicales
120 % (100 % votés) ; la surtaxe d'impôt sur les sociétés, réajustée à 6,8 Md€ en 2026 (7,3 votés),
s'arrête dès 2027 (valeur datée du droit en vigueur, moteur v0.8.1). Sources et montants :
`budget_simulator/data/atterrissage_observe.json` (bloc `reajustements_droit_en_vigueur`) ; garde :
`tests/test_cadre_v070_mesures_annee.py`. Les lignes ci-dessus décrivent les montants votés.

**Garde permanente.** Une loi de finances est annuelle. Le scénario peut porter l'effort chiffré
pour son année et faire l'hypothèse, déclarée, que les mesures structurelles persistent ; il ne
peut pas **accélérer**. Un test-propriété du moteur
(`tests/test_scenario_plf2026_v061.py::test_gouvernance_effort_2030_ne_derive_pas_au_dela_de_lannee_votee`)
borne à 0,5 point de PIB la dérive de l'effort encodé entre l'année votée et 2030 — sans quoi le
scénario de référence voterait, silencieusement, un ajustement que le législateur n'a pas voté.

### Programme RN Le Pen 2027
<!-- scenario:rn_2027 -->

- **Source** : Conférence de presse du 6 octobre 2026 (M. Le Pen, trajectoire financière 2027-2032 ; J. Bardella, contre-budget 2027), vidéos publiées sur rassemblementnational.fr, transcrites et relues le 12/11/2026
- **Orientation** : trajectoire financière 2027-2032 et contre-budget 2027 présentés le 6 octobre 2026 : objectif affiché d'économies nettes en 2032, annoncées sur l'immigration, les retraites et la Sécurité sociale sans ventilation par mesure ; baisse d'impôts de production, retour du prélèvement forfaitaire unique à son taux d'avant 2026, contribution à l'Union européenne réduite, effort de recherche publique accru et enveloppe pour les outre-mer. Le paramétrage encode les mesures chiffrées par nature qui ont un levier dans le simulateur ; les enveloppes d'économies sans ventilation sont affichées dans la fiche du programme, non comptées, et les cibles de déficit et de dette annoncées sont des résultats, pas des paramètres.

### Programme LFI Mélenchon 2027
<!-- scenario:lfi_2027 -->

- **Source** : L'Avenir en commun, édition 2027, et document « Comment nous allons remettre de l’ordre dans les comptes publics » du 14/10/2026 (melenchon2027.fr), lus le 11/11/2026
- **Orientation** : rupture économique et relance massive. Forte hausse des dépenses publiques (éducation, services publics, transition écologique planifiée), retour sur la réforme des retraites, revalorisation du salaire minimum et des rémunérations publiques, financée par une progressivité fiscale fortement accrue et le rétablissement d'une fiscalité du patrimoine.

### Programme Renaissance Attal 2027
<!-- scenario:renaissance_2027 -->

- **Source** : Programme de G. Attal (Renaissance) : fiches-mesures d'attalpresident.fr et lettre aux Français du 15/10/2026, lus le 11/11/2026
- **Orientation** : redressement des comptes par la dépense plutôt que par l'impôt (objectif affiché de retour à l'équilibre en une décennie, effort d'abord sur le modèle social et les effectifs publics, sans hausse d'impôt), désormais combiné à des engagements de dépense et de baisse de prélèvements : plan d'investissement « France 2040 » pour l'IA (part publique ~10 Md€/an), baisse des cotisations sur le travail pour « rapprocher le salaire net du salaire brut », financée par les économies d'assurance chômage et revalorisation enseignante. Le candidat adosse ces promesses aux mêmes économies non ventilées ; le paramétrage encode les mesures chiffrables des deux volets — non la cible d'équilibre, qui est un résultat calculé par le moteur.

### Programme Horizons Philippe 2027
<!-- scenario:horizons_2027 -->

- **Source** : Priorités d'É. Philippe (Horizons) sur edouardphilippe.fr et annonces de « l’Heure de vérité » du 08/10/2026, lues le 11/11/2026
- **Orientation** : compétitivité et maîtrise affichée des comptes : « pacte fiscal » avec les entreprises (forte baisse de la fiscalité de production intégralement compensée par la réduction des aides et niches, à somme nulle pour l'État), durcissement de l'assurance chômage (12 mois d'indemnisation maximum pour les moins de 50 ans, encodé au paramètre annoncé — le modèle applique la durée à tous les allocataires, donc chiffre en borne haute), fin de la surtaxe provisoire sur les grandes entreprises, et, depuis la réforme des retraites présentée le 29 septembre 2026, un relèvement de l'âge légal et de la durée de cotisation au-delà de la réforme de 2023 (encodés aux paramètres annoncés ; les départs anticipés et le pilier de capitalisation ne sont pas modélisés). Depuis la réécriture de la page de priorités (consultée le 2 novembre 2026), le non-remplacement d'un départ en retraite sur trois dans la fonction publique est encodé au nombre de postes annoncé par le candidat (montée en charge linéaire 2027-2032, même règle que les autres programmes), et la réforme des agences, dont l'intensité était jusque-là une hypothèse de modélisation, revient au droit en vigueur (même vivier de départs : la garder serait compter deux fois). La revalorisation des enseignants annoncée le 23 octobre 2026 est encodée à son coût brut : le financement « par la baisse démographique » affirmé par le candidat n'est pas crédité (règle d'encodage, point 3). La cible de déficit à 2 % du PIB en fin de quinquennat est un résultat annoncé, non une mesure : seules les mesures publiquement chiffrées sont paramétrées, l'écart entre la cible et la trajectoire calculée mesurant la part non ventilée du programme.

### Programme LR Retailleau 2027
<!-- scenario:lr_2027 -->

- **Source** : Livret « Rétablir l'ordre dans les comptes publics » (15 fiches, octobre 2026) et projet de B. Retailleau sur avecretailleau.fr, lus le 11/11/2026
- **Orientation** : programme d'économies d'ampleur sans hausse d'impôts, publié mesure par mesure sur le site de campagne avec une ligne de financement par mesure, puis ventilé ligne à ligne par le livret « Rétablir l'ordre dans les comptes publics » (octobre 2026) : réforme structurelle de l'État (non-remplacement massif des départs en retraite, encodé au nombre de postes du livret, montée en charge linéaire 2027-2032), refonte des aides sociales autour d'un compte social unique plafonné, durcissement de l'assurance chômage (durée maximale encodée au paramètre du livret), aide médicale d'État réduite aux soins essentiels, lutte contre la fraude fiscale et sociale, effort de fonctionnement des collectivités et fin de certaines subventions (encodés aux montants du livret là où un levier du simulateur correspond), report de l'âge du taux plein complété d'un pilier par capitalisation, et baisse des prélèvements sur le travail et la production, partagée entre entreprises (cotisations patronales, impôts de production) et salariés (cotisations salariales). Le paramétrage encode le coût de ces baisses tel que chiffré par le candidat ; les lignes du livret sans levier dans le simulateur (réserves des retraites, alignement des régimes, cotisation de capitalisation comptée en économie, arrêts maladie, jours de carence, revue des interventions de l'État, gestion de la Sécurité sociale, etc.) ne sont pas encodées et sont listées dans la fiche du programme.

### Programme PS 2027
<!-- scenario:ps_2027 -->

- **Source** : Livret « Révolution écologique » (glucks2027.fr, 09/11/2026), Projet socialiste (projet-socialiste.fr) et communiqué du Parti socialiste sur les salaires, lus le 11/11/2026
- **Orientation** : social-démocratie d'équilibre, en position médiane entre la gauche de rupture et la majorité sortante. Abrogation partielle de la réforme des retraites, revalorisation du salaire minimum, investissement dans l'éducation et la transition, financés par une progressivité fiscale accrue et une fiscalité du patrimoine des plus hauts patrimoines (référence à la taxe Zucman). Recherche d'un équilibre entre justice sociale et soutenabilité budgétaire.

### Programme Les Écologistes Tondelier 2027
<!-- scenario:ecologistes_2027 -->

- **Source** : « Pour une prospérité écologique », programme des Écologistes daté de juillet 2026 (lesecologistes.fr), lu le 11/11/2026
- **Orientation** : prospérité écologique par la refonte fiscale et l'investissement social : forte revalorisation du travail (salaire minimum à 2 000 € brut, rémunérations publiques), retour de l'âge minimum de départ à 62 ans, « garantie d'autonomie » remplaçant le RSA dès 18 ans, rénovation énergétique massive et adaptation climatique (7 Md€/an), financées par une refonte de la fiscalité du capital et des hauts revenus (ISF climatique, imposition minimale des très hauts patrimoines, tranche supérieure d'IR, CSG progressive relevée, imposition renforcée des grandes entreprises). Programme adopté en juillet 2026 ; la candidature reste suspendue aux discussions d'union à gauche — le paramétrage encode le programme adopté, indépendamment de l'issue.

### Programme Nouvelle Énergie Lisnard 2027
<!-- scenario:nouvelle_energie_2027 -->

- **Source** : Programme D. Lisnard (Nouvelle Énergie) — pages « Notre programme » et « Questions » de unenouvelleenergie.fr, entretien du 27/10/2026 publié le 28/10/2026 et « Livre noir de la bureaucratie » (avril 2026), consultés le 11/11/2026
- **Orientation** : réduction de la dépense publique présentée comme préalable à la baisse des prélèvements, avec une répartition annoncée entre salaire net des actifs, impôts de production (en commençant par la suppression de la C3S) et désendettement ; suppressions de postes publics et redéploiement d'agents vers le terrain ; condition de résidence pour les allocations non contributives ; remplacement de l'aide médicale d'État par une aide d'urgence ; revalorisation des rémunérations des enseignants, conditionnée à une réorganisation. Le paramétrage encode les mesures chiffrées qui ont un levier dans le simulateur ; l'enveloppe globale d'économies, non ventilée, est affichée dans la fiche du programme, non comptée.

### Institut Montaigne — Rabot -8%
<!-- scenario:im_rabot_2029 -->

- **Source** : Institut Montaigne — Budget Base Zéro (Nov 2025)
- **Orientation** : scénario illustratif de think tank appliquant une réduction uniforme des dépenses publiques, hors postes que la note juge incompressibles (charge de la dette, défense, contribution européenne). Selon ses auteurs, cette approche, « en plus de cristalliser les résistances, traduirait une logique d’austérité sans cap plutôt qu’une stratégie cohérente de redressement ».

---

## Paramètres injectés (généré — ne pas éditer à la main)

> Tableau produit automatiquement par `scripts/generate_scenario_params.py` depuis `frontend-react/src/data/scenarios.json`. Toute modification manuelle entre les marqueurs sera écrasée. Ce tableau fait foi : en cas de doute, c'est lui qui décrit ce que simule l'outil.

<!-- SCENARIO_PARAMS:START -->
| Mesure | Paramètre | Budget 2026 voté, réajusté sur l'exécution 2026 | Programme RN Le Pen 2027 | Programme LFI Mélenchon 2027 | Programme Renaissance Attal 2027 | Programme Horizons Philippe 2027 | Programme LR Retailleau 2027 | Programme PS 2027 | Programme Les Écologistes Tondelier 2027 | Institut Montaigne — Rabot -8% | Programme Nouvelle Énergie Lisnard 2027 |
|--------|-----------|-------------------------------------------------|--------------------------|------------------------------|----------------------------------|----------------------------------|------------------------------|-------------------|------------------------------------------|--------------------------------|-----------------------------------------|
| abattement_retraites | reforme_active | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| asu | asu_activation | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| asu | asu_plafonnement | 0.65 | 0.65 | 0.65 | 0.65 | 0.65 | 0.65 | 0.65 | 0.65 | 0.65 | 0.65 |
| chomage_alloc | degressivite | false | false | false | false | false | false | false | false | false | false |
| chomage_alloc | duree | 18 | 18 | 18 | 18 | 12 | 15 | 18 | 18 | 18 | 18 |
| chomage_alloc | montant | — | — | 39.6 | 31.6 | — | 24.85 | — | — | — | — |
| chomage_alloc | taux_remplacement | 0.6 | 0.6 | — | — | 0.6 | — | 0.6 | 0.6 | 0.6 | 0.6 |
| collectivites | dotation | 116.6 | 116.6 | 116.6 | 109.6 | 116.6 | 104.6277 | 116.6 | 116.6 | 116.6 | 116.6 |
| collectivites | investissement | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| cotisations_patronales | taux | 0.27 | 0.27 | 0.27 | 0.27 | 0.27 | 0.2526 | 0.27 | 0.28 | 0.27 | 0.27 |
| cotisations_salariales | baisse_points | 0 | 0 | 0 | 0.4321 | 0 | 1.2965 | 0 | 0 | 0 | 10.3702 |
| csg | progressive | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| csg | taux | 0.098039 | 0.098039 | 0.098039 | 0.098039 | 0.098039 | 0.098039 | 0.098039 | 0.108039 | 0.098039 | 0.098039 |
| defense | budget | 58 | 58 | 58 | 58 | 58 | 58.1 | 58 | 58 | 58 | 58 |
| depenses_publiques | credits_etat | — | 3.24 | 14.6 | 10 | — | -58.4145 | 2.6 | 3 | — | — |
| depenses_publiques | ondam | — | — | 2.4 | — | — | -5.9861 | 9.6 | — | — | 0.75 |
| depenses_publiques | transferts_capital | — | — | — | 0.66 | — | — | — | — | — | — |
| droits_succession | variation | — | — | 20 | — | — | — | 25 | — | — | — |
| education | budget | 65 | 65 | 72.1 | 65 | 65 | 62 | 65 | 65 | 65 | 65 |
| education | enseignants | 0 | 0 | 10000 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| education | salaires | 0 | 0 | 0 | 6.5 | 20 | 4.4 | 16 | 5 | 0 | 20 |
| elargissement_ir | taux_contribuables_cible | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 |
| exonerations_salaires | intensite | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| fiscalite_capital | prelevements_sociaux_capital | 0.186 | 0.172 | — | 0.186 | 0.186 | 0.186 | 0.186 | 0.206 | 0.186 | 0.186 |
| fiscalite_capital | rendement_md | — | — | 9 | — | — | — | — | — | — | — |
| fiscalite_capital | taux_ir_forfaitaire | 0.128 | 0.128 | — | 0.128 | 0.128 | 0.128 | 0.128 | 0.128 | 0.128 | 0.128 |
| fiscalite_patrimoine | intensite | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| fonction_publique | effectifs | -3119 | -3119 | 140000 | -97000 | -250000 | -400000 | 10000 | 21700 | -3119 | -400000 |
| fonction_publique | point_indice | 0 | 0 | 10 | 0 | 0 | 0 | 0 | 10 | 0 | 0 |
| fonction_publique_reforme | digitalisation | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| fonction_publique_reforme | fusion_agences | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| fraude_fiscale | effort | 0.14 | 0.14 | 0.24 | 0.14 | 0.14 | 0.385 | 0.14 | 0.14 | 0.14 | 0.14 |
| fraude_sociale | effort | 0.1 | 0.1 | 0.1 | 0.1 | 0.1 | 0.318 | 0.1 | 0.1 | 0.1 | 0.1 |
| immigration | ame | 1.2 | 1.2 | 1.2 | 1.2 | 1.2 | 0.4597 | 1.2 | 1.2 | 1.2 | 0.45 |
| immigration | integration | 0.8 | 0.8 | 0.8 | 0.8 | 0.8 | 0.8 | 0.8 | 0.8 | 0.8 | 0.8 |
| impot_plancher_patrimoine | taux | — | — | 0.02 | — | — | — | 0.02 | 0.02 | — | — |
| impot_revenu | decote | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| impot_revenu | taux_superieur | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 | 0.6 | 0.45 | 0.45 |
| impot_revenu_cible | montant | — | — | — | — | -3 | — | — | — | — | — |
| impot_societes | niches | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| impot_societes | taux | 0.25 | 0.25 | 0.264 | 0.25 | 0.25 | 0.25 | 0.25 | 0.25 | 0.25 | 0.25 |
| impots_production | montant | 97 | 80 | 100 | 92.89 | 47 | 82 | 97 | 97 | 97 | 57 |
| is_exceptionnel_tge | montant | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| isf_climatique | intensite | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| multinationales | benefices_recuperes | — | — | 5 | — | — | — | — | — | — | — |
| multinationales | rendement_tsn_md | — | — | 3.9 | — | — | — | — | — | — | — |
| multinationales | taux_tsn | 0.03 | 0.03 | — | 0.03 | 0.03 | 0.03 | 0.03 | 0.05 | 0.03 | 0.03 |
| niches_fiscales_tge | montant | 57 | 57 | 46.97 | 57 | 25.33 | 51.6669 | 57 | 57 | 57 | 57 |
| niches_sociales_tge | montant | 68 | 68 | 56.03 | 68 | 68 | 68 | 57 | 68 | 68 | 68 |
| operations_financieres | crypto_actifs | — | — | 1 | — | — | — | — | — | — | — |
| operations_financieres | rachats_actions | 0 | 0 | 2.5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| operations_financieres | rendement_ttf_md | — | — | 5 | — | — | — | — | — | — | — |
| operations_financieres | taux_ttf | 0.004 | 0.004 | — | 0.004 | 0.004 | 0.004 | 0.004 | 0.007 | 0.004 | 0.004 |
| optimisation_dette | intensite | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| prestations_indexation | taux_indexation | 1 | 1 | 1 | 0 | 1 | 1 | 1 | 1 | 1 | 1 |
| prestations_menages | pensions | — | — | — | — | — | -13.2783 | — | — | — | — |
| prestations_menages | solidarite | — | — | 22.8 | — | — | -16.5289 | 20 | 8.89 | — | -8 |
| rabot_uniforme | exclure_defense | — | — | — | — | — | — | — | — | 1 | — |
| rabot_uniforme | exclure_dette | — | — | — | — | — | — | — | — | 1 | — |
| rabot_uniforme | exclure_ue | — | — | — | — | — | — | — | — | 1 | — |
| rabot_uniforme | taux_reduction | — | — | — | — | — | — | — | — | 0.08 | — |
| recette_exceptionnelle | montant | — | — | 5 | — | — | — | 50 | — | — | — |
| recherche_publique | budget | 10 | 19.15 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 |
| retraites | age_depart | — | — | 60 | — | 65 | 65 | 62 | 62 | — | — |
| retraites | duree_cotisation | 42.5 | 42.5 | 40 | 42.5 | 45 | 42.5 | 43 | 42.5 | 42.5 | 42.5 |
| retraites | indexation | 1 | 1 | 1 | 0 | 1 | 1 | 1 | 1 | 1 | 1 |
| sante | effort_ambu | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 |
| sante | effort_hopital | 15 | 15 | 15 | 15 | 15 | 15 | 15 | 15 | 15 | 15 |
| sante | effort_prev_org | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 | 10 |
| sante | franchise_participation_taux | 120 | 120 | 0 | 120 | 120 | 120 | 120 | 0 | 120 | 120 |
| sante | prevention_budget | 7.5 | 7.5 | 7.5 | 7.5 | 7.5 | 7.5 | 11.2 | 7.5 | 7.5 | 7.5 |
| smic | montant_brut | 1800 | 1800 | 2180 | 1800 | 1800 | 1800 | 2180 | 2000 | 1800 | 1800 |
| subventions_tge | montant | 33 | 33 | 33 | 33 | 14.67 | 28.6464 | 33 | 33 | 33 | 33 |
| taxe_superprofits | intensite | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| transferts_etranger | montant | — | -9 | — | — | — | -3.8094 | 0.5 | — | — | — |
| transition_ecologique | investissement | 0 | 0 | 6.36 | 0 | 1.02 | 0 | 20 | 7 | 0 | 0 |
| transition_ecologique | renovation | 0 | 0 | 7.05 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| transition_ecologique | taxe_carbone | 44.6 | 44.6 | 44.6 | 44.6 | 44.6 | 44.6 | 44.6 | 44.6 | 44.6 | 44.6 |
| tva_energie | taux | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 |
| tva_rate | taux | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 |

- Calendrier, Programme RN Le Pen 2027, `depenses_publiques.credits_etat` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme RN Le Pen 2027, `recherche_publique.budget` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme LFI Mélenchon 2027, `recette_exceptionnelle.montant` : une seule année, 2028 (annee)
- Calendrier, Programme Renaissance Attal 2027, `impots_production.montant` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme Renaissance Attal 2027, `prestations_indexation.taux_indexation` : une seule année, 2028 (annee)
- Calendrier, Programme Renaissance Attal 2027, `retraites.indexation` : une seule année, 2028 (annee)
- Calendrier, Programme Horizons Philippe 2027, `education.salaires` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme Horizons Philippe 2027, `impots_production.montant` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme Horizons Philippe 2027, `niches_fiscales_tge.montant` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme Horizons Philippe 2027, `subventions_tge.montant` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme LR Retailleau 2027, `chomage_alloc.montant` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme LR Retailleau 2027, `collectivites.dotation` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme LR Retailleau 2027, `depenses_publiques.credits_etat` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme LR Retailleau 2027, `depenses_publiques.ondam` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme LR Retailleau 2027, `education.budget` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme LR Retailleau 2027, `niches_fiscales_tge.montant` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme LR Retailleau 2027, `prestations_menages.pensions` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme LR Retailleau 2027, `prestations_menages.solidarite` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme LR Retailleau 2027, `subventions_tge.montant` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme LR Retailleau 2027, `transferts_etranger.montant` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme PS 2027, `depenses_publiques.ondam` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme PS 2027, `recette_exceptionnelle.montant` : une seule année, 2028 (annee)
- Calendrier, Programme PS 2027, `sante.prevention_budget` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme PS 2027, `transferts_etranger.montant` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme Les Écologistes Tondelier 2027, `cotisations_patronales.taux` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme Les Écologistes Tondelier 2027, `depenses_publiques.credits_etat` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme Les Écologistes Tondelier 2027, `education.salaires` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme Les Écologistes Tondelier 2027, `prestations_menages.solidarite` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme Les Écologistes Tondelier 2027, `transition_ecologique.investissement` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme Nouvelle Énergie Lisnard 2027, `cotisations_salariales.baisse_points` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme Nouvelle Énergie Lisnard 2027, `education.salaires` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme Nouvelle Énergie Lisnard 2027, `impots_production.montant` : montée progressive jusqu'à la fin du mandat (rampe)
- Calendrier, Programme Nouvelle Énergie Lisnard 2027, `prestations_menages.solidarite` : montée progressive jusqu'à la fin du mandat (rampe)
<!-- SCENARIO_PARAMS:END -->

---

## Note méthodologique

Le simulateur repose sur une chaîne déterministe **53 curseurs (sliders) → 36 mesures → 33 handlers** : les réglages de l'interface sont convertis en mesures normalisées, elles-mêmes appliquées par des handlers de calcul qui produisent la trajectoire budgétaire 2025-2035. Le registre exhaustif de cette chaîne (dimension sliders incluse) est documenté dans [`docs/MEASURE_REGISTRY.md`](MEASURE_REGISTRY.md).

Le moteur applique des multiplicateurs budgétaires différenciés par mesure (investissement, transferts, prélèvements, coupes de dépenses) et un profil temporel de décroissance lui-même différencié, ainsi que des mécanismes de second tour (cicatrice d'austérité au-delà d'un effort élevé, effets de confiance plafonnés, éviction, retour fiscal de la transition, effets d'offre dynamiques de l'investissement productif). Le détail des calibrations et des sources académiques sous-jacentes relève de la documentation technique du moteur ; ce document ne porte que sur les scénarios et leurs paramètres d'entrée.

---

*Outil citoyen indépendant — document évolutif. Contact : contact@francebudget.fr*
