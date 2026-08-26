# Scénarios politiques

**Date** : 2026-07-07
**Statut** : document canonique unique (remplace les anciens `PARAMETRES_SCENARIOS_POLITIQUES.md` et `SCENARIOS_POLITIQUES_SYNTHESE.md`)

> **Source unique.** Les paramètres injectés présentés plus bas sont générés automatiquement depuis le moteur (`frontend-react/src/data/scenarios.json`) — ils reflètent exactement ce que simule l'outil. La prose ci-dessous est volontairement **qualitative** : elle décrit l'orientation des scénarios sans réénoncer aucune valeur chiffrée d'un paramètre injecté, afin qu'aucune divergence ne puisse réapparaître entre le texte et le moteur.

---

## Avertissement

Cet outil est un simulateur citoyen indépendant, sans affiliation gouvernementale ni partisane. Les scénarios sont une interprétation des programmes et documents officiels disponibles, destinée à comparer des orientations budgétaires. Ils peuvent évoluer à mesure que les programmes sont précisés. Pour signaler une imprécision, contactez : contact@francebudget.fr.

---

## Les 9 scénarios

Le simulateur propose **9 scénarios** : **7 programmes politiques** (gouvernement et principales formations) et **2 scénarios de think tank** produits par l'Institut Montaigne. Chaque scénario fixe l'ensemble des paramètres d'entrée du moteur ; le détail chiffré exact figure dans la section générée « Paramètres injectés ».

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

- **Source** : Programme G. Attal (Renaissance) — finances publiques, 2 juil. 2026
- **Orientation** : redressement des comptes par la dépense plutôt que par l'impôt : objectif affiché de retour à l'équilibre en une décennie, effort porté d'abord sur le modèle social (gel temporaire des prestations, reprise de la réforme de l'assurance chômage) et sur la réduction des effectifs publics, sans hausse d'impôt et avec poursuite de la baisse de la fiscalité de production. Éducation, défense et transition écologique affichées comme priorités préservées. Le paramétrage encode les mesures chiffrables du programme de campagne — non la cible d'équilibre, qui est un résultat calculé par le moteur.

### Programme Horizons Philippe 2027
<!-- scenario:horizons_2027 -->

- **Source** : Deal fiscal Horizons (E. Philippe, 6 nov 2025) + meeting de lancement (5 juil. 2026)
- **Orientation** : compétitivité à solde neutre : « deal fiscal » avec les entreprises (forte baisse de la fiscalité de production intégralement compensée par la réduction des aides et niches aux entreprises, présentée comme à somme nulle pour l'État), prolongement de la réforme des retraites par un allongement de l'activité et une contribution accrue des retraités. Programme en cours de dévoilement (campagne lancée le 5 juillet 2026) : seules les mesures publiquement chiffrées sont paramétrées, le reste restant au statu quo budgétaire voté.

### Programme LR Retailleau 2027
<!-- scenario:lr_2027 -->

- **Source** : Programme éco Retailleau, 3 volets (janv.–févr. 2026, Les Échos — pas de document officiel consolidé)
- **Orientation** : programme d'économies d'ampleur sans hausse d'impôts, structuré en trois volets (travail, production, finances publiques) : réforme structurelle de l'État (réduction marquée des effectifs, fusion d'agences), refonte des aides sociales autour d'un compte social unique plafonné, report de l'âge de départ à la retraite complété d'un pilier par capitalisation, et choc de compétitivité sur le coût du travail et la fiscalité de production. Aucun document programmatique consolidé publié à ce stade : paramétrage établi sur la presse de référence, à confirmer à mesure des chiffrages 2027.

### Programme PS 2027
<!-- scenario:ps_2027 -->

- **Source** : Le Projet socialiste, volet éco « Vivre libres » (adopté le 25 juin 2026)
- **Orientation** : social-démocratie d'équilibre, en position médiane entre la gauche de rupture et la majorité sortante. Abrogation partielle de la réforme des retraites, revalorisation du salaire minimum, investissement dans l'éducation et la transition, financés par une progressivité fiscale accrue et une fiscalité du patrimoine des plus hauts patrimoines (référence à la taxe Zucman). Recherche d'un équilibre entre justice sociale et soutenabilité budgétaire.

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
| Mesure | Paramètre | Budget 2026 (voté) | Programme RN Le Pen 2027 | Programme LFI Mélenchon 2027 | Programme Renaissance Attal 2027 | Programme Horizons Philippe 2027 | Programme LR Retailleau 2027 | Programme PS 2027 | Institut Montaigne — Rabot -8% | Institut Montaigne — Compétitivité |
|--------|-----------|--------------------|--------------------------|------------------------------|----------------------------------|----------------------------------|------------------------------|-------------------|--------------------------------|------------------------------------|
| abattement_retraites | reforme_active | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| asu | asu_activation | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| asu | asu_plafonnement | 0.65 | 0.65 | 0.65 | 0.65 | 0.65 | 0.7 | 0.65 | 0.65 | 0.7 |
| chomage_alloc | degressivite | false | false | false | false | false | false | false | false | false |
| chomage_alloc | duree | 18 | 24 | 30 | 15 | 18 | 18 | 27 | 24 | 18 |
| chomage_alloc | taux_remplacement | 0.6 | 0.57 | 0.7 | 0.6 | 0.6 | 0.57 | 0.65 | 0.6 | 0.55 |
| collectivites | dotation | 116.6 | 115 | 140 | 120 | 120 | 110 | 130 | 110 | 95 |
| collectivites | investissement | 0 | 0 | 15 | 0 | 0 | 0 | 8 | 0 | 0 |
| cotisations_patronales | taux | 0.27 | 0.27 | 0.3 | 0.27 | 0.27 | 0.25 | 0.28 | 0.27 | 0.26 |
| cotisations_salariales | baisse_points | 0 | 2 | 0 | 1.5 | 0 | 0 | 0 | 0 | 0 |
| csg | progressive | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| csg | taux | 0.098039 | 0.097 | 0.105 | 0.097 | 0.097 | 0.097 | 0.1 | 0.097 | 0.097 |
| defense | budget | 57 | 50 | 45 | 65 | 57 | 65 | 50 | 50 | 50 |
| education | budget | 65 | 65 | 85 | 65 | 65 | 65 | 75 | 65 | 80 |
| education | enseignants | 0 | 0 | 60000 | 0 | 0 | -20000 | 30000 | 0 | 10000 |
| education | salaires | 0 | 0 | 15 | 5 | 0 | 1.5 | 8 | 0 | 8 |
| elargissement_ir | taux_contribuables_cible | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 |
| exonerations_salaires | intensite | 0 | 0 | 1 | 0 | 0 | 0 | 0.5 | 0 | 0 |
| fiscalite_patrimoine | intensite | 0 | 0.15 | 0.3 | 0 | 0 | 0 | 0.25 | 0 | 0 |
| fonction_publique | effectifs | -3119 | -50000 | 60000 | -100000 | -3119 | -200000 | 20000 | 0 | -120000 |
| fonction_publique | point_indice | 0 | 0 | 10 | 0 | 0 | 0 | 3 | 0 | 0 |
| fonction_publique_reforme | digitalisation | 0 | 30 | 10 | 50 | 20 | 50 | 15 | 0 | 50 |
| fonction_publique_reforme | fusion_agences | 0 | 50 | 0 | 50 | 10 | 60 | 10 | 0 | 60 |
| fraude_fiscale | effort | 0.14 | 1 | 1 | 0.5 | 0.5 | 0.8 | 0.9 | 0 | 0.8 |
| fraude_sociale | effort | 0.1 | 1 | 0.5 | 0.3 | 0.3 | 1 | 0.6 | 0 | 0.8 |
| immigration | ame | 1.2 | 0.4 | 1.5 | 1.2 | 1.2 | 0.3 | 1.4 | 1.1 | 0.8 |
| immigration | integration | 0.8 | 0.3 | 1.2 | 0.8 | 0.8 | 0.4 | 1 | 0.7 | 0.6 |
| impot_revenu | decote | 1 | 1.1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| impot_revenu | taux_superieur | 0.45 | 0.45 | 0.6 | 0.45 | 0.45 | 0.45 | 0.5 | 0.45 | 0.45 |
| impot_societes | niches | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| impot_societes | taux | 0.25 | 0.25 | 0.3 | 0.25 | 0.25 | 0.25 | 0.27 | 0.25 | 0.25 |
| impots_production | montant | 97 | 87 | 97 | 87 | 47 | 82 | 97 | 97 | 90 |
| is_exceptionnel_tge | montant | 7.3 | 0 | 15 | 0 | 7.3 | 8 | 12 | 8 | 8 |
| isf_climatique | intensite | 0 | 0.3 | 1 | 0 | 0 | 0 | 0.6 | 0 | 0 |
| niches_fiscales_tge | montant | 57 | 58 | 20 | 56 | 31 | 50 | 40 | 58 | 40 |
| niches_sociales_tge | montant | 68 | 70 | 50 | 68 | 68 | 80 | 55 | 70 | 55 |
| optimisation_dette | intensite | 0 | 0.6 | 0 | 0.3 | 0.3 | 0.6 | 0.2 | 0 | 0.5 |
| prestations_indexation | taux_indexation | 1 | 1 | 1 | 0.8 | 1 | 1 | 1 | 1 | 1 |
| rabot_uniforme | exclure_defense | — | — | — | — | — | — | — | 1 | 1 |
| rabot_uniforme | exclure_dette | — | — | — | — | — | — | — | 1 | 1 |
| rabot_uniforme | exclure_ue | — | — | — | — | — | — | — | 1 | 1 |
| rabot_uniforme | taux_reduction | — | — | — | — | — | — | — | 0.08 | 0 |
| recherche_publique | budget | 10 | 8 | 15 | 8 | 8 | 3 | 12 | 0 | 15 |
| retraites | age_depart | — | 61.5 | 60 | — | 65 | 65 | 62 | 64 | 65 |
| retraites | duree_cotisation | 42.5 | 41 | 40 | 42.5 | 43 | 43 | 43 | 43 | 44 |
| retraites | indexation | 1 | 1 | 1 | 0.9 | 1 | 1 | 1 | 1 | 0.8 |
| sante | effort_ambu | 20 | 5 | 0 | 20 | 20 | 15 | 0 | 0 | 25 |
| sante | effort_hopital | 15 | 5 | 0 | 15 | 15 | 20 | 0 | 0 | 30 |
| sante | effort_prev_org | 10 | 5 | 0 | 20 | 10 | 10 | 0 | 0 | 15 |
| sante | franchise_participation_taux | 100 | 100 | 0 | 100 | 100 | 120 | 50 | 100 | 110 |
| sante | prevention_budget | 7.5 | 7.5 | 10.5 | 7.5 | 7.5 | 7.5 | 9.5 | 7.5 | 8.5 |
| smic | montant_brut | 1800 | 1800 | 2050 | 1800 | 1800 | 1800 | 2150 | 1800 | 1800 |
| subventions_tge | montant | 33 | 35 | 20 | 33 | 8 | 45 | 25 | 32 | 25 |
| taxe_superprofits | intensite | 0 | 0.5 | 1 | 0 | 0 | 0 | 0.5 | 0 | 0 |
| transition_ecologique | investissement | 0 | 5 | 50 | 0 | 0 | 8 | 25 | 0 | 20 |
| transition_ecologique | renovation | 0 | 3 | 30 | 20 | 0 | 8 | 20 | 0 | 15 |
| transition_ecologique | taxe_carbone | 44.6 | 44.6 | 120 | 44.6 | 44.6 | 100 | 100 | 100 | 110 |
| tva_energie | taux | 0.2 | 0.055 | 0.055 | 0.2 | 0.2 | 0.2 | 0.1 | 0.2 | 0.2 |
| tva_rate | taux | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 |
<!-- SCENARIO_PARAMS:END -->

---

## Note méthodologique

Le simulateur repose sur une chaîne déterministe **53 curseurs (sliders) → 36 mesures → 33 handlers** : les réglages de l'interface sont convertis en mesures normalisées, elles-mêmes appliquées par des handlers de calcul qui produisent la trajectoire budgétaire 2025-2035. Le registre exhaustif de cette chaîne (dimension sliders incluse) est documenté dans [`docs/MEASURE_REGISTRY.md`](MEASURE_REGISTRY.md).

Le moteur applique des multiplicateurs budgétaires différenciés par mesure (investissement, transferts, prélèvements, coupes de dépenses) et un profil temporel de décroissance lui-même différencié, ainsi que des mécanismes de second tour (cicatrice d'austérité au-delà d'un effort élevé, effets de confiance plafonnés, éviction, retour fiscal de la transition, effets d'offre dynamiques de l'investissement productif). Le détail des calibrations et des sources académiques sous-jacentes relève de la documentation technique du moteur ; ce document ne porte que sur les scénarios et leurs paramètres d'entrée.

---

*Outil citoyen indépendant — document évolutif. Contact : contact@francebudget.fr*
