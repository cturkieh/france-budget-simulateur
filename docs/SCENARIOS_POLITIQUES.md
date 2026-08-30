# Scénarios politiques

**Date** : 2026-07-07
**Statut** : document canonique unique (remplace les anciens `PARAMETRES_SCENARIOS_POLITIQUES.md` et `SCENARIOS_POLITIQUES_SYNTHESE.md`)

> **Source unique.** Les paramètres injectés présentés plus bas sont générés automatiquement depuis le moteur (`frontend-react/src/data/scenarios.json`) — ils reflètent exactement ce que simule l'outil. La prose ci-dessous est volontairement **qualitative** : elle décrit l'orientation des scénarios sans réénoncer aucune valeur chiffrée d'un paramètre injecté, afin qu'aucune divergence ne puisse réapparaître entre le texte et le moteur.

---

## Avertissement

Cet outil est un simulateur citoyen indépendant, sans affiliation gouvernementale ni partisane. Les scénarios sont une interprétation des programmes et documents officiels disponibles, destinée à comparer des orientations budgétaires. Ils peuvent évoluer à mesure que les programmes sont précisés. Pour signaler une imprécision, contactez : contact@francebudget.fr.

---

## Les 10 scénarios

Le simulateur propose **10 scénarios** : **8 programmes politiques** (gouvernement et principales formations) et **2 scénarios de think tank** produits par l'Institut Montaigne. Chaque scénario fixe l'ensemble des paramètres d'entrée du moteur ; le détail chiffré exact figure dans la section générée « Paramètres injectés ».

### Budget 2026 (voté)
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
| `sante` (15 / 20 / 10) | Calé sur l'**année 1** (+1,28 Md€, prudent face aux 4,1 Md€ d'économies Sécurité sociale votées). Mais le moteur en fait un effort **structurel permanent de 4,65 Md€/an** à partir de 2030. **La persistance est une hypothèse**, et une hypothèse discutable : une LFSS est **annuelle**, et son paquet d'économies est passé de **10,4** à **4,1** Md€ au cours du débat parlementaire. C'est le deuxième contributeur de l'effort résiduel du scénario de référence. |
| `niches_sociales_tge = 68` | Proxy de la réforme des **allègements généraux de cotisations** (Sénat, rapport général n° 139 t. II : **3,9** Md€ bruts / **3,1** Md€ nets en 2026). **L'assiette réelle est celle des rémunérations inférieures à 3 SMIC, tous employeurs** — et non les grandes entreprises que le nom du levier désigne. Les 2 Md€ encodés restent en deçà du chiffrage : conservateur, mais sur une assiette qui n'est pas celle du libellé. |
| `defense = 57` | 57,15 Md€ hors CAS Pensions est un montant **nominal**, et **nominal ≠ structurel** : l'OFCE (*Policy brief* n° 154) chiffre la dépense structurelle supplémentaire à **5,3** Md€ et non 6,7. Par ailleurs le +7 **constant** sur tout l'horizon **sous-représente les marches de la LPM** (+3,2 Md€/an) au-delà de 2027 : les deux écarts jouent en sens opposé et ne sont pas compensés l'un par l'autre. |
| `is_exceptionnel_tge = 7,3` | 7,3 Md€ est le rendement **2026** de la contribution exceptionnelle sur les bénéfices des grandes entreprises. Le porter sur tout l'horizon suppose sa **reconduction annuelle** — hypothèse que Fipeco juge probable et que le ministre de l'Économie a confirmée pour 2027, mais qui reste une hypothèse, non un texte voté au-delà de 2026. |

**Garde permanente.** Une loi de finances est annuelle. Le scénario peut porter l'effort chiffré
pour son année et faire l'hypothèse, déclarée, que les mesures structurelles persistent ; il ne
peut pas **accélérer**. Un test-propriété du moteur
(`tests/test_scenario_plf2026_v061.py::test_gouvernance_effort_2030_ne_derive_pas_au_dela_de_lannee_votee`)
borne à 0,5 point de PIB la dérive de l'effort encodé entre l'année votée et 2030 — sans quoi le
scénario de référence voterait, silencieusement, un ajustement que le législateur n'a pas voté.

### Programme RN Le Pen 2027
<!-- scenario:rn_2027 -->

- **Source** : Programme éco RN (détaillé par J. Bardella, avril 2026 — candidate : M. Le Pen)
- **Orientation** : priorité au pouvoir d'achat et à la compétitivité par allègement de la fiscalité de production et rapprochement du brut et du net, assouplissement de l'âge de départ pour les carrières longues, et resserrement des dépenses liées à l'immigration. Logique de baisse ciblée de prélèvements financée par des économies de fonctionnement et des contributions exceptionnelles sur certains secteurs.

### Programme LFI Mélenchon 2027
<!-- scenario:lfi_2027 -->

- **Source** : L'Avenir en commun, édition 2025 (831 mesures)
- **Orientation** : rupture économique et relance massive. Forte hausse des dépenses publiques (éducation, services publics, transition écologique planifiée), retour sur la réforme des retraites, revalorisation du salaire minimum et des rémunérations publiques, financée par une progressivité fiscale fortement accrue et le rétablissement d'une fiscalité du patrimoine. Note technique : la tranche supérieure d'impôt sur le revenu annoncée par le programme dépasse le plafond du curseur du simulateur ; elle est donc simulée à la valeur maximale que l'outil permet (voir le tableau généré).

### Programme Renaissance Attal 2027
<!-- scenario:renaissance_2027 -->

- **Source** : Programme G. Attal (Renaissance) — attalpresident.fr/programme, consulté le 30 août 2026 (entretiens Les Échos 17/06, Le Parisien 02/07, Le Télégramme 22/07, Le Monde 25/08)
- **Orientation** : redressement des comptes par la dépense plutôt que par l'impôt (objectif affiché de retour à l'équilibre en une décennie, effort d'abord sur le modèle social et les effectifs publics, sans hausse d'impôt), désormais combiné à des engagements de dépense et de baisse de prélèvements : plan d'investissement « France 2040 » pour l'IA (part publique ~10 Md€/an), « droit au brut » par baisse des cotisations salariales (non chiffré par le candidat, encodé sur bornes de tiers) et revalorisation enseignante. Le candidat adosse ces promesses aux mêmes économies non ventilées ; le paramétrage encode les mesures chiffrables des deux volets — non la cible d'équilibre, qui est un résultat calculé par le moteur.

### Programme Horizons Philippe 2027
<!-- scenario:horizons_2027 -->

- **Source** : Priorités É. Philippe — « Pour une France plus prospère » (site officiel) + AFP/débat Medef du 27 août 2026
- **Orientation** : compétitivité et maîtrise affichée des comptes : « pacte fiscal » avec les entreprises (forte baisse de la fiscalité de production intégralement compensée par la réduction des aides et niches, à somme nulle pour l'État), durcissement de l'assurance chômage (12 mois d'indemnisation maximum pour les moins de 50 ans, encodé au paramètre annoncé — le modèle applique la durée à tous les allocataires, donc chiffre en borne haute), fin de la surtaxe provisoire sur les grandes entreprises, et « travailler un peu plus longtemps » sans âge légal chiffré (calendrier légal maintenu, durée de cotisation en hypothèse). La cible de déficit à 2 % du PIB en fin de quinquennat est un résultat annoncé, non une mesure : seules les mesures publiquement chiffrées sont paramétrées, l'écart entre la cible et la trajectoire calculée mesurant la part non ventilée du programme.

### Programme LR Retailleau 2027
<!-- scenario:lr_2027 -->

- **Source** : Programme éco Retailleau, 3 volets (janv.–févr. 2026, Les Échos — pas de document officiel consolidé)
- **Orientation** : programme d'économies d'ampleur sans hausse d'impôts, structuré en trois volets (travail, production, finances publiques) : réforme structurelle de l'État (réduction marquée des effectifs, fusion d'agences), refonte des aides sociales autour d'un compte social unique plafonné, report de l'âge de départ à la retraite complété d'un pilier par capitalisation, et choc de compétitivité sur le coût du travail et la fiscalité de production. Aucun document programmatique consolidé publié à ce stade : paramétrage établi sur la presse de référence, à confirmer à mesure des chiffrages 2027.

### Programme PS 2027
<!-- scenario:ps_2027 -->

- **Source** : Le Projet socialiste, volet éco « Vivre libres » (adopté le 25 juin 2026)
- **Orientation** : social-démocratie d'équilibre, en position médiane entre la gauche de rupture et la majorité sortante. Abrogation partielle de la réforme des retraites, revalorisation du salaire minimum, investissement dans l'éducation et la transition, financés par une progressivité fiscale accrue et une fiscalité du patrimoine des plus hauts patrimoines (référence à la taxe Zucman). Recherche d'un équilibre entre justice sociale et soutenabilité budgétaire.

### Programme Les Écologistes Tondelier 2027
<!-- scenario:ecologistes_2027 -->

- **Source** : « Pour une prospérité écologique » — nouveau programme des Écologistes (557 mesures, adopté le 13 juil. 2026)
- **Orientation** : prospérité écologique par la refonte fiscale et l'investissement social : forte revalorisation du travail (salaire minimum à 2 000 € brut, rémunérations publiques), retour de l'âge minimum de départ à 62 ans, « garantie d'autonomie » remplaçant le RSA dès 18 ans, rénovation énergétique massive et adaptation climatique (7 Md€/an), financées par une refonte de la fiscalité du capital et des hauts revenus (ISF climatique, imposition minimale des très hauts patrimoines, tranche supérieure d'IR, CSG progressive relevée, imposition renforcée des grandes entreprises). Programme adopté en juillet 2026 ; la candidature reste suspendue aux discussions d'union à gauche — le paramétrage encode le programme adopté, indépendamment de l'issue.

### Institut Montaigne — Rabot -8%
<!-- scenario:im_rabot_2029 -->

- **Source** : Institut Montaigne — Budget Base Zéro (Nov 2025)
- **Orientation** : scénario illustratif de think tank appliquant une réduction uniforme des dépenses publiques, hors postes sanctuarisés (dette, défense, contribution européenne). Il est présenté par ses auteurs comme cumulant les résistances sans réallocation stratégique : un cas d'école d'austérité non différenciée, à fort impact social attendu.

### Institut Montaigne — Compétitivité
<!-- scenario:im_competitivite_2029 -->

- **Source** : Institut Montaigne — Budget Base Zéro (Nov 2025)
- **Orientation** : scénario de think tank combinant des économies importantes (retraites, efficience de la santé, fonction publique) à un réinvestissement stratégique vers l'éducation, la recherche et la transition. Logique de réallocation au service de la croissance potentielle, présentée par ses auteurs comme l'option recommandée.

---

## Paramètres injectés (généré — ne pas éditer à la main)

> Tableau produit automatiquement par `scripts/generate_scenario_params.py` depuis `frontend-react/src/data/scenarios.json`. Toute modification manuelle entre les marqueurs sera écrasée. Ce tableau fait foi : en cas de doute, c'est lui qui décrit ce que simule l'outil.

<!-- SCENARIO_PARAMS:START -->
| Mesure | Paramètre | Budget 2026 (voté) | Programme RN Le Pen 2027 | Programme LFI Mélenchon 2027 | Programme Renaissance Attal 2027 | Programme Horizons Philippe 2027 | Programme LR Retailleau 2027 | Programme PS 2027 | Programme Les Écologistes Tondelier 2027 | Institut Montaigne — Rabot -8% | Institut Montaigne — Compétitivité |
|--------|-----------|--------------------|--------------------------|------------------------------|----------------------------------|----------------------------------|------------------------------|-------------------|------------------------------------------|--------------------------------|------------------------------------|
| abattement_retraites | reforme_active | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| asu | asu_activation | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 1 |
| asu | asu_plafonnement | 0.65 | 0.65 | 0.65 | 0.65 | 0.65 | 0.7 | 0.65 | 0.5 | 0.65 | 0.7 |
| chomage_alloc | degressivite | false | false | false | false | false | false | false | false | false | false |
| chomage_alloc | duree | 18 | 24 | 30 | 16.5 | 16 | 18 | 27 | 24 | 24 | 18 |
| chomage_alloc | taux_remplacement | 0.6 | 0.57 | 0.7 | 0.6 | 0.6 | 0.57 | 0.65 | 0.6 | 0.6 | 0.55 |
| collectivites | dotation | 116.6 | 115 | 140 | 116.6 | 116.6 | 110 | 130 | 130 | 110 | 95 |
| collectivites | investissement | 0 | 0 | 15 | 0 | 0 | 0 | 8 | 8 | 0 | 0 |
| cotisations_patronales | taux | 0.27 | 0.27 | 0.3 | 0.27 | 0.27 | 0.242 | 0.28 | 0.28 | 0.27 | 0.26 |
| cotisations_salariales | baisse_points | 0 | 2 | 0 | 2.5 | 0 | 0 | 0 | 0 | 0 | 0 |
| csg | progressive | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 1 | 0 | 0 |
| csg | taux | 0.098039 | 0.098039 | 0.105 | 0.098039 | 0.098039 | 0.098039 | 0.1 | 0.108039 | 0.098039 | 0.098039 |
| defense | budget | 57 | 50 | 45 | 65 | 57 | 65 | 50 | 57 | 50 | 50 |
| education | budget | 65 | 65 | 85 | 65 | 65 | 65 | 75 | 75 | 65 | 80 |
| education | enseignants | 0 | 0 | 60000 | 0 | 0 | -20000 | 30000 | 30000 | 0 | 10000 |
| education | salaires | 0 | 0 | 15 | 6.5 | 0 | 1.5 | 8 | 15 | 0 | 8 |
| elargissement_ir | taux_contribuables_cible | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 |
| exonerations_salaires | intensite | 0 | 0 | 1 | 0 | 0 | 0 | 0.5 | 0 | 0 | 0 |
| fiscalite_patrimoine | intensite | 0 | 0.15 | 0.3 | 0 | 0 | 0 | 0.25 | 0.3 | 0 | 0 |
| fonction_publique | effectifs | -3119 | -50000 | 60000 | -100000 | -3119 | -250000 | 20000 | 20000 | 0 | -120000 |
| fonction_publique | point_indice | 0 | 0 | 10 | 0 | 0 | 0 | 3 | 10 | 0 | 0 |
| fonction_publique_reforme | digitalisation | 0 | 30 | 10 | 50 | 20 | 50 | 15 | 0 | 0 | 50 |
| fonction_publique_reforme | fusion_agences | 0 | 50 | 0 | 50 | 10 | 60 | 10 | 0 | 0 | 60 |
| fraude_fiscale | effort | 0.14 | 1 | 1 | 0.14 | 0.14 | 0.8 | 0.9 | 1 | 0 | 0.8 |
| fraude_sociale | effort | 0.1 | 1 | 0.5 | 0.1 | 0.1 | 1 | 0.6 | 0 | 0 | 0.8 |
| immigration | ame | 1.2 | 0.4 | 1.5 | 1.2 | 1.2 | 0.3 | 1.4 | 1.5 | 1.1 | 0.8 |
| immigration | integration | 0.8 | 0.3 | 1.2 | 0.8 | 0.8 | 0.4 | 1 | 1.2 | 0.7 | 0.6 |
| impot_revenu | decote | 1 | 1.1 | 1 | 1 | 1 | 1 | 1 | 1.1 | 1 | 1 |
| impot_revenu | taux_superieur | 0.45 | 0.45 | 0.6 | 0.45 | 0.45 | 0.45 | 0.5 | 0.6 | 0.45 | 0.45 |
| impot_societes | niches | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| impot_societes | taux | 0.25 | 0.25 | 0.3 | 0.25 | 0.25 | 0.25 | 0.27 | 0.25 | 0.25 | 0.25 |
| impots_production | montant | 97 | 87 | 97 | 87 | 47 | 82 | 97 | 97 | 97 | 90 |
| is_exceptionnel_tge | montant | 7.3 | 0 | 15 | 0 | 0 | 8 | 12 | 15 | 8 | 8 |
| isf_climatique | intensite | 0 | 0.3 | 1 | 0 | 0 | 0 | 0.6 | 1 | 0 | 0 |
| niches_fiscales_tge | montant | 57 | 58 | 20 | 56 | 32 | 50 | 40 | 25 | 58 | 40 |
| niches_sociales_tge | montant | 68 | 70 | 50 | 68 | 68 | 80 | 55 | 50 | 70 | 55 |
| optimisation_dette | intensite | 0 | 0.6 | 0 | 0 | 0 | 0.6 | 0.2 | 0.3 | 0 | 0.5 |
| prestations_indexation | taux_indexation | 1 | 1 | 1 | 0.8 | 1 | 1 | 1 | 1 | 1 | 1 |
| rabot_uniforme | exclure_defense | — | — | — | — | — | — | — | — | 1 | 1 |
| rabot_uniforme | exclure_dette | — | — | — | — | — | — | — | — | 1 | 1 |
| rabot_uniforme | exclure_ue | — | — | — | — | — | — | — | — | 1 | 1 |
| rabot_uniforme | taux_reduction | — | — | — | — | — | — | — | — | 0.08 | 0 |
| recherche_publique | budget | 10 | 8 | 15 | 20 | 10 | 3 | 12 | 14 | 0 | 15 |
| retraites | age_depart | — | 61.5 | 60 | — | — | 65 | 62 | 62 | 64 | 65 |
| retraites | duree_cotisation | 42.5 | 41 | 40 | 42.5 | 43 | 43 | 43 | 42.5 | 43 | 44 |
| retraites | indexation | 1 | 1 | 1 | 0.9 | 1 | 1 | 1 | 1 | 1 | 0.8 |
| sante | effort_ambu | 20 | 5 | 0 | 20 | 20 | 15 | 0 | 0 | 0 | 25 |
| sante | effort_hopital | 15 | 5 | 0 | 15 | 15 | 20 | 0 | 0 | 0 | 30 |
| sante | effort_prev_org | 10 | 5 | 0 | 20 | 10 | 10 | 0 | 0 | 0 | 15 |
| sante | franchise_participation_taux | 100 | 100 | 0 | 100 | 100 | 120 | 50 | 100 | 100 | 110 |
| sante | prevention_budget | 7.5 | 7.5 | 10.5 | 7.5 | 7.5 | 7.5 | 9.5 | 9.5 | 7.5 | 8.5 |
| smic | montant_brut | 1800 | 1800 | 2050 | 1800 | 1800 | 1800 | 2150 | 2000 | 1800 | 1800 |
| subventions_tge | montant | 33 | 35 | 20 | 33 | 8 | 45 | 25 | 20 | 32 | 25 |
| taxe_superprofits | intensite | 0 | 0.5 | 1 | 0 | 0 | 0 | 0.5 | 0.5 | 0 | 0 |
| transition_ecologique | investissement | 0 | 5 | 50 | 0 | 0 | 8 | 25 | 7 | 0 | 20 |
| transition_ecologique | renovation | 0 | 3 | 30 | 0 | 0 | 8 | 20 | 25 | 0 | 15 |
| transition_ecologique | taxe_carbone | 44.6 | 44.6 | 120 | 44.6 | 44.6 | 100 | 100 | 44.6 | 100 | 110 |
| tva_energie | taux | 0.2 | 0.055 | 0.055 | 0.2 | 0.2 | 0.2 | 0.1 | 0.2 | 0.2 | 0.2 |
| tva_rate | taux | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 |
<!-- SCENARIO_PARAMS:END -->

---

## Note méthodologique

Le simulateur repose sur une chaîne déterministe **53 curseurs (sliders) → 36 mesures → 33 handlers** : les réglages de l'interface sont convertis en mesures normalisées, elles-mêmes appliquées par des handlers de calcul qui produisent la trajectoire budgétaire 2025-2035. Le registre exhaustif de cette chaîne (dimension sliders incluse) est documenté dans [`docs/MEASURE_REGISTRY.md`](MEASURE_REGISTRY.md).

Le moteur applique des multiplicateurs budgétaires différenciés par mesure (investissement, transferts, prélèvements, coupes de dépenses) et un profil temporel de décroissance lui-même différencié, ainsi que des mécanismes de second tour (cicatrice d'austérité au-delà d'un effort élevé, effets de confiance plafonnés, éviction, retour fiscal de la transition, effets d'offre dynamiques de l'investissement productif). Le détail des calibrations et des sources académiques sous-jacentes relève de la documentation technique du moteur ; ce document ne porte que sur les scénarios et leurs paramètres d'entrée.

---

*Outil citoyen indépendant — document évolutif. Contact : contact@francebudget.fr*
