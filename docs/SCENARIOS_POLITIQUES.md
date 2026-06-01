# Scénarios politiques

**Date** : 2026-05-31
**Statut** : document canonique unique (remplace les anciens `PARAMETRES_SCENARIOS_POLITIQUES.md` et `SCENARIOS_POLITIQUES_SYNTHESE.md`)

> **Source unique.** Les paramètres injectés présentés plus bas sont générés automatiquement depuis le moteur (`frontend-react/src/data/scenarios.json`) — ils reflètent exactement ce que simule l'outil. La prose ci-dessous est volontairement **qualitative** : elle décrit l'orientation des scénarios sans réénoncer aucune valeur chiffrée d'un paramètre injecté, afin qu'aucune divergence ne puisse réapparaître entre le texte et le moteur.

---

## Avertissement

Cet outil est un simulateur citoyen indépendant, sans affiliation gouvernementale ni partisane. Les scénarios sont une interprétation des programmes et documents officiels disponibles, destinée à comparer des orientations budgétaires. Ils peuvent évoluer à mesure que les programmes sont précisés. Pour signaler une imprécision, contactez : contact@francebudget.fr.

---

## Les 8 scénarios

Le simulateur propose **8 scénarios** : **6 programmes politiques** (gouvernement et principales formations) et **2 scénarios de think tank** produits par l'Institut Montaigne. Chaque scénario fixe l'ensemble des paramètres d'entrée du moteur ; le détail chiffré exact figure dans la section générée « Paramètres injectés ».

### Budget 2026 (voté)
<!-- scenario:plf_2026 -->

- **Source** : LF 2026 (loi 2026-103, JO 19 fév 2026)
- **Orientation** : consolidation budgétaire modérée, dans la continuité, avec préservation des acquis sociaux après amendements parlementaires. Trajectoire de réduction graduelle du déficit sans rupture fiscale ni sociale ; effort de maîtrise réparti sur les enveloppes ministérielles, hausse marquée de l'effort de défense, et fiscalité des grandes entreprises mobilisée à titre exceptionnel. C'est le scénario de référence « politique votée ».

### Programme RN Bardella 2027
<!-- scenario:rn_2027 -->

- **Source** : Programme éco RN (Bardella, avril 2026)
- **Orientation** : priorité au pouvoir d'achat et à la compétitivité par allègement de la fiscalité de production et rapprochement du brut et du net, assouplissement de l'âge de départ pour les carrières longues, et resserrement des dépenses liées à l'immigration. Logique de baisse ciblée de prélèvements financée par des économies de fonctionnement et des contributions exceptionnelles sur certains secteurs.

### Programme LFI Mélenchon 2027
<!-- scenario:lfi_2027 -->

- **Source** : L'Avenir en commun, édition 2025 (831 mesures)
- **Orientation** : rupture économique et relance massive. Forte hausse des dépenses publiques (éducation, services publics, transition écologique planifiée), retour sur la réforme des retraites, revalorisation du salaire minimum et des rémunérations publiques, financée par une progressivité fiscale fortement accrue et le rétablissement d'une fiscalité du patrimoine. Note technique : la tranche supérieure d'impôt sur le revenu annoncée par le programme dépasse le plafond du curseur du simulateur ; elle est donc simulée à la valeur maximale que l'outil permet (voir le tableau généré).

### Programme Renaissance
<!-- scenario:renaissance_2027 -->

- **Source** : Plan budgétaire structurel moyen terme (PSMT) 2025-2029
- **Orientation** : continuité de la trajectoire gouvernementale, cap sur le plein emploi et le retour du déficit sous le seuil européen. Hypothèse de continuité sur les retraites (la réforme de 2023 est suspendue jusqu'à 2028 ; position de campagne 2027 non arrêtée), modernisation et rationalisation de l'État, allègement ciblé pour les classes moyennes et baisse du coin socio-fiscal, plan d'investissement écologique d'ampleur intermédiaire.

### Programme LR 2027 (Retailleau)
<!-- scenario:lr_2027 -->

- **Source** : Programme Retailleau (grandes lignes 07/01/2026, Europe 1 / Public Sénat)
- **Orientation** : programme d'économies d'ampleur sans hausse d'impôts, articulé autour d'une réforme structurelle de l'État (réduction des effectifs et fusion d'agences), d'une refonte des aides sociales et d'un durcissement des dépenses d'immigration, avec maintien d'un effort de défense élevé. Programme présidentiel porté par le candidat B. Retailleau (grandes lignes publiées début 2026), non entièrement chiffré à ce stade ; le paramétrage retient l'esprit du programme (économies sans hausse d'impôts), à confirmer à mesure des chiffrages 2027.

### Programme PS 2027
<!-- scenario:ps_2027 -->

- **Source** : Projet « Vivre libre » 144p (22 avril 2026, dir. Chloé Ridel)
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
| Mesure | Paramètre | Budget 2026 (voté) | Programme RN Bardella 2027 | Programme LFI Mélenchon 2027 | Programme Renaissance | Programme LR | Programme PS 2027 | Institut Montaigne — Rabot -8% | Institut Montaigne — Compétitivité |
|--------|-----------|--------------------|----------------------------|------------------------------|-----------------------|--------------|-------------------|--------------------------------|------------------------------------|
| abattement_retraites | reforme_active | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| asu | asu_activation | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 1 |
| asu | asu_plafonnement | 0.65 | 0.65 | 0.65 | 0.65 | 0.7 | 0.65 | 0.65 | 0.7 |
| chomage_alloc | degressivite | false | false | false | false | false | false | false | false |
| chomage_alloc | duree | 18 | 24 | 30 | 21 | 18 | 27 | 24 | 18 |
| chomage_alloc | taux_remplacement | 0.6 | 0.57 | 0.7 | 0.57 | 0.57 | 0.65 | 0.6 | 0.55 |
| collectivites | dotation | 120 | 115 | 140 | 122 | 110 | 130 | 110 | 95 |
| collectivites | investissement | 0 | 0 | 15 | 3 | 0 | 8 | 0 | 0 |
| cotisations_patronales | taux | 0.27 | 0.27 | 0.3 | 0.25 | 0.25 | 0.28 | 0.27 | 0.26 |
| cotisations_salariales | baisse_points | 0 | 2 | 0 | 1.5 | 0 | 0 | 0 | 0 |
| csg | progressive | 0 | 0 | 1 | 0 | 0 | 1 | 0 | 0 |
| csg | taux | 0.097 | 0.097 | 0.105 | 0.097 | 0.097 | 0.1 | 0.097 | 0.097 |
| defense | budget | 57 | 50 | 45 | 55 | 65 | 50 | 50 | 50 |
| education | budget | 65 | 65 | 85 | 72 | 65 | 75 | 65 | 80 |
| education | enseignants | 0 | 0 | 60000 | -10000 | -20000 | 30000 | 0 | 10000 |
| education | salaires | 0 | 0 | 15 | 3 | 1.5 | 8 | 0 | 8 |
| elargissement_ir | taux_contribuables_cible | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 |
| exonerations_salaires | intensite | 0 | 0 | 1 | 0.5 | 0 | 0.5 | 0 | 0 |
| fiscalite_patrimoine | intensite | 0 | 0.15 | 0.3 | 0 | 0 | 0.25 | 0 | 0 |
| fonction_publique | effectifs | -3119 | -50000 | 60000 | -20000 | -60000 | 20000 | 0 | -120000 |
| fonction_publique | point_indice | 0 | 0 | 10 | 1 | 0 | 3 | 0 | 0 |
| fonction_publique_reforme | digitalisation | 20 | 30 | 10 | 35 | 50 | 15 | 0 | 50 |
| fonction_publique_reforme | fusion_agences | 10 | 50 | 0 | 30 | 60 | 10 | 0 | 60 |
| fraude_fiscale | effort | 0.5 | 1 | 1 | 0.8 | 0.8 | 0.9 | 0 | 0.8 |
| fraude_sociale | effort | 0.3 | 1 | 0.5 | 0.5 | 1 | 0.6 | 0 | 0.8 |
| immigration | ame | 1.2 | 0.4 | 1.5 | 1.2 | 0.3 | 1.4 | 1.1 | 0.8 |
| immigration | integration | 0.8 | 0.3 | 1.2 | 0.9 | 0.4 | 1 | 0.7 | 0.6 |
| impot_revenu | decote | 1 | 1.1 | 1 | 1.1 | 1 | 1 | 1 | 1 |
| impot_revenu | taux_superieur | 0.45 | 0.45 | 0.6 | 0.45 | 0.45 | 0.5 | 0.45 | 0.45 |
| impot_societes | niches | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| impot_societes | taux | 0.25 | 0.25 | 0.3 | 0.25 | 0.25 | 0.27 | 0.25 | 0.25 |
| impots_production | montant | 97 | 87 | 97 | 100 | 95 | 97 | 97 | 90 |
| is_exceptionnel_tge | montant | 7.3 | 0 | 15 | 8 | 8 | 12 | 8 | 8 |
| isf_climatique | intensite | 0 | 0.3 | 1 | 0 | 0 | 0.6 | 0 | 0 |
| niches_fiscales_tge | montant | 56 | 58 | 20 | 30 | 50 | 40 | 58 | 40 |
| niches_sociales_tge | montant | 68 | 70 | 50 | 65 | 80 | 55 | 70 | 55 |
| optimisation_dette | intensite | 0.3 | 0.6 | 0 | 0.5 | 0.6 | 0.2 | 0 | 0.5 |
| prestations_indexation | taux_indexation | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| rabot_uniforme | exclure_defense | — | — | — | — | — | — | 1 | 1 |
| rabot_uniforme | exclure_dette | — | — | — | — | — | — | 1 | 1 |
| rabot_uniforme | exclure_ue | — | — | — | — | — | — | 1 | 1 |
| rabot_uniforme | taux_reduction | — | — | — | — | — | — | 0.08 | 0 |
| recherche_publique | budget | 8 | 8 | 15 | 5 | 3 | 12 | 0 | 15 |
| retraites | age_depart | 62.75 | 61.5 | 60 | 64 | 64 | 62 | 64 | 65 |
| retraites | duree_cotisation | 42.5 | 41 | 40 | 43 | 43 | 43 | 43 | 44 |
| retraites | indexation | 1 | 1 | 1 | 0.8 | 1 | 1 | 1 | 0.8 |
| sante | effort_ambu | 20 | 5 | 0 | 15 | 15 | 0 | 0 | 25 |
| sante | effort_hopital | 15 | 5 | 0 | 20 | 20 | 0 | 0 | 30 |
| sante | effort_prev_org | 10 | 5 | 0 | 10 | 10 | 0 | 0 | 15 |
| sante | franchise_participation_taux | 100 | 100 | 0 | 100 | 120 | 50 | 100 | 110 |
| sante | prevention_budget | 5 | 5 | 8 | 6 | 5 | 7 | 5 | 6 |
| smic | montant_brut | 1800 | 1800 | 2050 | 1850 | 1800 | 2150 | 1800 | 1800 |
| subventions_tge | montant | 33 | 35 | 20 | 30 | 45 | 25 | 32 | 25 |
| taxe_superprofits | intensite | 0 | 0.5 | 1 | 0 | 0 | 0.5 | 0 | 0 |
| transition_ecologique | investissement | 0 | 5 | 50 | 20 | 8 | 25 | 0 | 20 |
| transition_ecologique | renovation | 0 | 3 | 30 | 15 | 8 | 20 | 0 | 15 |
| transition_ecologique | taxe_carbone | 44.6 | 44.6 | 120 | 110 | 100 | 100 | 100 | 110 |
| tva_energie | taux | 0.2 | 0.055 | 0.055 | 0.2 | 0.2 | 0.1 | 0.2 | 0.2 |
| tva_rate | taux | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 |
<!-- SCENARIO_PARAMS:END -->

---

## Note méthodologique

Le simulateur repose sur une chaîne déterministe **53 curseurs (sliders) → 36 mesures → 33 handlers** : les réglages de l'interface sont convertis en mesures normalisées, elles-mêmes appliquées par des handlers de calcul qui produisent la trajectoire budgétaire 2025-2035. Le registre exhaustif de cette chaîne (dimension sliders incluse) est documenté dans [`docs/MEASURE_REGISTRY.md`](MEASURE_REGISTRY.md).

Le moteur applique des multiplicateurs budgétaires différenciés par mesure (investissement, transferts, prélèvements, coupes de dépenses) et un profil temporel de décroissance lui-même différencié, ainsi que des mécanismes de second tour (cicatrice d'austérité au-delà d'un effort élevé, effets de confiance plafonnés, éviction, retour fiscal de la transition, effets d'offre dynamiques de l'investissement productif). Le détail des calibrations et des sources académiques sous-jacentes relève de la documentation technique du moteur ; ce document ne porte que sur les scénarios et leurs paramètres d'entrée.

---

*Outil citoyen indépendant — document évolutif. Contact : contact@francebudget.fr*
