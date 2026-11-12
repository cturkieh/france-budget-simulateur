# MEASURE_REGISTRY — Contrat de paramètres (GÉNÉRÉ)

> **NE PAS ÉDITER À LA MAIN.** Généré par `scripts/generate_measure_registry.py` depuis les lectures du dict `params` dans le corps des méthodes `measure_handlers`. Toute édition manuelle sera écrasée et fait échouer la CI (`tests/test_measure_registry_sync.py`).

Vérité = corps des méthodes `measure_handlers` + `constants.INTENSITE_DOMAINS`. Le bloc `parametres` de `policy_measures.json` n'est PAS le contrat.

## `abattement_retraites` — Réforme abattement fiscal retraités
- type : `fonction` · catégorie : `fiscalite`
- paramètres lus par le handler :
  - `reforme_active` (défaut : `0`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `abattement_retraites_reforme` → param `reforme_active` [0–1, pas 1]

## `asu` — Allocation Sociale Unique (ASU)
- type : `fonction` · catégorie : `social`
- flags : `VERIFIED_ALIVE_config_asu_defaults`
- paramètres lus par le handler :
  - `asu_activation` (défaut : `0`)
  - `asu_plafonnement` (défaut : `ASU_PLAFONNEMENT_DEFAUT` (non littéral))
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `asu_activation` → param `asu_activation` [0–1, pas 1]
  - `asu_plafonnement` → param `asu_plafonnement` [0.5–0.7, pas 0.05]

## `chomage_alloc` — Assurance chômage
- type : `fonction` · catégorie : `social`
- paramètres lus par le handler :
  - `degressivite` (défaut : `False`)
  - `duree` (défaut : `DUREE_REF` (non littéral))
  - `montant` (défaut : `MONTANT_REF` (non littéral))
  - `taux_remplacement` (défaut : `TAUX_REF` (non littéral))
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `chomage_duree` → param `duree` [12–36, pas 3]
  - `chomage_montant` → param `montant` [24.85–48.8, pas 0.05]
  - `chomage_taux_remplacement` → param `taux_remplacement` [0.45–0.8, pas 0.05]

## `cotisations_patronales` — Cotisations patronales
- type : `fonction` · catégorie : `competitivite`
- paramètres lus par le handler :
  - `taux` (défaut : `0.27`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `cotisations_patronales_taux` → param `taux` [0.15–0.35, pas 0.01]

## `cotisations_salariales` — Cotisations salariales
- type : `fonction` · catégorie : `fiscalite`
- paramètres lus par le handler :
  - `baisse_points` (défaut : `0.0`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `cotisations_salariales_baisse` → param `baisse_points` [0–11.94, pas 0.01]

## `csg` — CSG/CRDS
- type : `fonction` · catégorie : `fiscalite`
- paramètres lus par le handler :
  - `progressive` (défaut : `0`)
  - `taux` (défaut : `0.097`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `csg_progressive` → param `progressive` [0–1, pas 1]
  - `csg_taux` → param `taux` [0.08–0.12, pas 0.001]

## `droits_succession` — Droits de succession et de donation
- type : `fonction` · catégorie : `fiscalite`
- paramètres lus par le handler :
  - `variation` (défaut : `NEUTRES_RELEASE_E['droits_succession']['variation']` (non littéral))
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `droits_succession_variation` → param `variation` [-21.2–25, pas 0.5]

## `education` — Éducation nationale
- type : `fonction` · catégorie : `depenses`
- paramètres lus par le handler :
  - `budget` (défaut : `65`)
  - `enseignants` (défaut : `0`)
  - `salaires` (défaut : `0`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `education_budget` → param `budget` [60–90, pas 2]
  - `education_enseignants` → param `enseignants` [-20000–60000, pas 5000]
  - `education_salaires` → param `salaires` [0–15, pas 1]

## `elargissement_ir` — Élargissement de la base IR
- type : `fonction` · catégorie : `fiscalite`
- paramètres lus par le handler :
  - `taux_contribuables_cible` (défaut : `0.45`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `elargissement_ir_cible` → param `taux_contribuables_cible` [0.45–0.7, pas 0.01]

## `exonerations_salaires` — Exonérations hausses salaires
- type : `fonction` · catégorie : `social`
- flags : `INTENSITE_DRIVEN`
- paramètres lus par le handler :
  - `intensite` (domaine : `[0.0, 1.0]`, défaut : `None`)
  - `seuil_hausse` (défaut : `0.01`)
  - `taux_exoneration` (défaut : `0.0`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `exo_salaires_intensite` → param `intensite` [0–1, pas 0.1]

## `fiscalite_capital` — Revenus du capital
- type : `fonction` · catégorie : `fiscalite`
- paramètres lus par le handler :
  - `elasticite` (défaut : `NEUTRES_RELEASE_E['fiscalite_capital']['elasticite']` (non littéral))
  - `prelevements_sociaux_capital` (défaut : `NEUTRES_RELEASE_E['fiscalite_capital']['prelevements_sociaux_capital']` (non littéral))
  - `rendement_md` (**requis** (KeyError si absent))
  - `taux_ir_forfaitaire` (défaut : `NEUTRES_RELEASE_E['fiscalite_capital']['taux_ir_forfaitaire']` (non littéral))
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `capital_elasticite` → param `elasticite` [0–2, pas 0.05]
  - `capital_prelevements_sociaux` → param `prelevements_sociaux_capital` [0–0.3, pas 0.001]
  - `capital_rendement_md` → param `rendement_md` [-15–15, pas 0.5]
  - `capital_taux_ir` → param `taux_ir_forfaitaire` [0–0.45, pas 0.001]

## `fiscalite_indirecte` — Fiscalité indirecte ciblée
- type : `fonction` · catégorie : `fiscalite`
- paramètres lus par le handler :
  - `accises_energie` (défaut : `NEUTRES_RELEASE_E['fiscalite_indirecte']['accises_energie']` (non littéral))
  - `tva_ciblee` (défaut : `NEUTRES_RELEASE_E['fiscalite_indirecte']['tva_ciblee']` (non littéral))
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `accises_energie` → param `accises_energie` [-15–15, pas 0.5]
  - `tva_ciblee` → param `tva_ciblee` [-15–15, pas 0.5]

## `fiscalite_patrimoine` — Fiscalité du patrimoine
- type : `fonction` · catégorie : `fiscalite`
- flags : `INTENSITE_DRIVEN`
- paramètres lus par le handler :
  - `intensite` (domaine : `[-0.3, 0.3]`, défaut : `None`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `fiscalite_patrimoine_intensite` → param `intensite` [-0.3–0.3, pas 0.05]

## `fonction_publique` — Fonction publique
- type : `fonction` · catégorie : `depenses`
- paramètres lus par le handler :
  - `effectifs` (défaut : `0`)
  - `point_indice` (défaut : `0`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `fp_effectifs` → param `effectifs` [-100000–140000, pas 10000]
  - `fp_point_indice` → param `point_indice` [-2–5, pas 0.5]

## `fonction_publique_reforme` — Réforme fonction publique
- type : `fonction` · catégorie : `depenses`
- paramètres lus par le handler :
  - `digitalisation` (défaut : `0`)
  - `fusion_agences` (défaut : `0`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `fp_digitalisation` → param `digitalisation` [0–100, pas 5]
  - `fp_fusion_agences` → param `fusion_agences` [0–100, pas 5]

## `fraude_fiscale` — Lutte contre la fraude fiscale
- type : `fonction` · catégorie : `fiscalite`
- flags : `KNOWN_SEMANTIC_EFFORT_BIMODAL`
- paramètres lus par le handler :
  - `effort` (défaut : `0`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `fraude_effort` → param `effort` [0–1, pas 0.1]

## `fraude_sociale` — Lutte contre la fraude sociale
- type : `fonction` · catégorie : `social`
- flags : `KNOWN_SEMANTIC_EFFORT_BIMODAL`
- paramètres lus par le handler :
  - `effort` (défaut : `0`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `fraude_sociale_effort` → param `effort` [0–1, pas 0.1]

## `impot_plancher_patrimoine` — Impôt plancher sur les très hauts patrimoines
- type : `fonction` · catégorie : `fiscalite`
- paramètres lus par le handler :
  - `evitement` (défaut : `NEUTRES_RELEASE_E['impot_plancher_patrimoine']['evitement']` (non littéral))
  - `taux` (défaut : `NEUTRES_RELEASE_E['impot_plancher_patrimoine']['taux']` (non littéral))
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `impot_plancher_evitement` → param `evitement` [0–0.95, pas 0.025]
  - `impot_plancher_taux` → param `taux` [0–0.03, pas 0.001]

## `impot_revenu` — Impôt sur le revenu
- type : `fonction` · catégorie : `fiscalite`
- paramètres lus par le handler :
  - `decote` (défaut : `1.0`)
  - `taux_superieur` (défaut : `0.45`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `ir_decote` → param `decote` [0.5–1.5, pas 0.1]
  - `ir_taux_superieur` → param `taux_superieur` [0.4–0.6, pas 0.01]

## `impot_revenu_cible` — Impôt sur le revenu : mesure ciblée
- type : `fonction` · catégorie : `fiscalite`
- paramètres lus par le handler :
  - `montant` (défaut : `NEUTRES_RELEASE_E['impot_revenu_cible']['montant']` (non littéral))
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `impot_revenu_cible_montant` → param `montant` [-15–5, pas 0.5]

## `impot_societes` — Impôt sur les sociétés
- type : `fonction` · catégorie : `fiscalite`
- paramètres lus par le handler :
  - `niches` (défaut : `0`)
  - `taux` (défaut : `0.25`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `is_taux` → param `taux` [0.15–0.35, pas 0.01]

## `impots_production` — Impôts sur la production
- type : `fonction` · catégorie : `competitivite`
- paramètres lus par le handler :
  - `montant` (défaut : `97`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `impots_production` → param `montant` [37–125, pas 5]

## `is_exceptionnel_tge` — IS exceptionnel TGE
- type : `fonction` · catégorie : `competitivite`
- paramètres lus par le handler :
  - `montant` (défaut : `8`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `is_exceptionnel_tge` → param `montant` [0–15, pas 1]

## `isf_climatique` — ISF Climatique
- type : `fonction` · catégorie : `fiscalite`
- flags : `INTENSITE_DRIVEN`
- paramètres lus par le handler :
  - `intensite` (domaine : `[0.0, 1.0]`, défaut : `None`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `isf_intensite` → param `intensite` [0–1, pas 0.01]

## `multinationales` — Multinationales : bénéfices transférés et taxe numérique
- type : `fonction` · catégorie : `fiscalite`
- paramètres lus par le handler :
  - `benefices_recuperes` (défaut : `NEUTRES_RELEASE_E['multinationales']['benefices_recuperes']` (non littéral))
  - `erosion_tsn` (défaut : `NEUTRES_RELEASE_E['multinationales']['erosion_tsn']` (non littéral))
  - `rendement_tsn_md` (**requis** (KeyError si absent))
  - `taux_tsn` (défaut : `NEUTRES_RELEASE_E['multinationales']['taux_tsn']` (non littéral))
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `multinationales_benefices` → param `benefices_recuperes` [0–12.6, pas 0.1]
  - `tsn_erosion` → param `erosion_tsn` [0–10, pas 0.1]
  - `tsn_rendement_md` → param `rendement_tsn_md` [-1–10, pas 0.1]
  - `tsn_taux` → param `taux_tsn` [0–0.1, pas 0.005]

## `niches_fiscales_tge` — Niches fiscales grandes entreprises
- type : `fonction` · catégorie : `competitivite`
- paramètres lus par le handler :
  - `montant` (défaut : `58`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `niches_fiscales_tge` → param `montant` [5–70, pas 5]

## `niches_sociales_tge` — Niches sociales grandes entreprises
- type : `fonction` · catégorie : `competitivite`
- paramètres lus par le handler :
  - `montant` (défaut : `70`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `niches_sociales_tge` → param `montant` [10–80, pas 5]

## `operations_financieres` — Opérations financières
- type : `fonction` · catégorie : `fiscalite`
- paramètres lus par le handler :
  - `crypto_actifs` (défaut : `NEUTRES_RELEASE_E['operations_financieres']['crypto_actifs']` (non littéral))
  - `elasticite_volume` (défaut : `NEUTRES_RELEASE_E['operations_financieres']['elasticite_volume']` (non littéral))
  - `rachats_actions` (défaut : `NEUTRES_RELEASE_E['operations_financieres']['rachats_actions']` (non littéral))
  - `rendement_ttf_md` (**requis** (KeyError si absent))
  - `taux_ttf` (défaut : `NEUTRES_RELEASE_E['operations_financieres']['taux_ttf']` (non littéral))
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `crypto_actifs` → param `crypto_actifs` [0–5, pas 0.1]
  - `rachats_actions` → param `rachats_actions` [-0.2–15, pas 0.1]
  - `ttf_elasticite_volume` → param `elasticite_volume` [0–0.25, pas 0.01]
  - `ttf_rendement_md` → param `rendement_ttf_md` [-3–10, pas 0.1]
  - `ttf_taux` → param `taux_ttf` [0–0.01, pas 0.0005]

## `optimisation_dette` — Optimisation dette
- type : `fonction` · catégorie : `depenses`
- flags : `INTENSITE_DRIVEN`
- paramètres lus par le handler :
  - `intensite` (domaine : `[0.0, 1.0]`, défaut : `None`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `optimisation_dette` → param `intensite` [0–1, pas 0.1]

## `prestations_indexation` — Indexation prestations sociales
- type : `fonction` · catégorie : `social`
- paramètres lus par le handler :
  - `taux_indexation` (défaut : `1.0`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `prestations_indexation` → param `taux_indexation` [0–120, pas 5]

## `prestations_menages` — Prestations versées aux ménages, en montant
- type : `fonction` · catégorie : `social`
- paramètres lus par le handler :
  - `pensions` (défaut : `NEUTRES_RELEASE_E['prestations_menages']['pensions']` (non littéral))
  - `solidarite` (défaut : `NEUTRES_RELEASE_E['prestations_menages']['solidarite']` (non littéral))
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `prestations_pensions` → param `pensions` [-20–10, pas 0.5]
  - `prestations_solidarite` → param `solidarite` [-35–30, pas 0.5]

## `rabot_uniforme` — Rabot budgétaire uniforme
- type : `fonction` · catégorie : `depenses`
- paramètres lus par le handler :
  - `exclure_defense` (défaut : `1`)
  - `exclure_dette` (défaut : `1`)
  - `exclure_ue` (défaut : `1`)
  - `taux_reduction` (défaut : `0`)
- sliders UI : _(aucun — mesure pilotée par scénario/API uniquement)_

## `recette_exceptionnelle` — Recette exceptionnelle
- type : `fonction` · catégorie : `fiscalite`
- paramètres lus par le handler :
  - `montant` (défaut : `NEUTRES_RELEASE_E['recette_exceptionnelle']['montant']` (non littéral))
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `recette_exceptionnelle_montant` → param `montant` [0–60, pas 1]

## `recherche_publique` — Recherche publique
- type : `formule` · catégorie : `economie`
- paramètres lus par le handler :
  - `budget` (défaut : `10`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `recherche_budget` → param `budget` [0–37, pas 1]

## `retraites` — Réforme des retraites
- type : `fonction` · catégorie : `social`
- paramètres lus par le handler :
  - `age_depart` (défaut : `ref_age` (non littéral))
  - `duree_cotisation` (défaut : `RETRAITES_REF_DUREE_ANS` (non littéral))
  - `indexation` (défaut : `1.0`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `retraites_age` → param `age_depart` [60–67, pas 0.25]
  - `retraites_duree` → param `duree_cotisation` [40–45, pas 0.5]
  - `retraites_indexation` → param `indexation` [0–1.2, pas 0.05]

## `sante` — Système de santé
- type : `fonction` · catégorie : `social`
- paramètres lus par le handler :
  - `effort_ambu` (défaut : `0`)
  - `effort_hopital` (défaut : `0`)
  - `effort_prev_org` (défaut : `0`)
  - `franchise_participation_taux` (défaut : `100`)
  - `prevention_budget` (défaut : `PREVENTION_BASE_MD_EUR` (non littéral))
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `effort_ambu` → param `effort_ambu` [0–100, pas 5]
  - `effort_hopital` → param `effort_hopital` [0–100, pas 5]
  - `effort_prev_org` → param `effort_prev_org` [0–100, pas 5]
  - `franchise_participation_taux` → param `franchise_participation_taux` [0–200, pas 10]
  - `prevention_budget` → param `prevention_budget` [7.5–11.2, pas 0.1]

## `smic` — SMIC
- type : `fonction` · catégorie : `social`
- paramètres lus par le handler :
  - `montant_brut` (défaut : `1800`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `smic_montant_brut` → param `montant_brut` [1400–2200, pas 50]

## `subventions_tge` — Subventions grandes entreprises
- type : `fonction` · catégorie : `competitivite`
- paramètres lus par le handler :
  - `montant` (défaut : `35`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `subventions_tge` → param `montant` [5–50, pas 5]

## `taxe_superprofits` — Taxe sur les superprofits
- type : `fonction` · catégorie : `fiscalite`
- flags : `INTENSITE_DRIVEN`
- paramètres lus par le handler :
  - `intensite` (domaine : `[0.0, 1.0]`, défaut : `None`)
  - `seuil_hausse` (défaut : `1.2`)
  - `taux` (défaut : `0.25`)
  - `tous_secteurs` (défaut : `True`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `superprofits_intensite` → param `intensite` [0–1, pas 0.1]

## `transition_ecologique` — Transition écologique
- type : `fonction` · catégorie : `economie`
- paramètres lus par le handler :
  - `investissement` (défaut : `0`)
  - `renovation` (défaut : `0`)
  - `taxe_carbone` (défaut : `CARBONE_PRIX_REFERENCE_EUR_T` (non littéral))
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `transition_investissement` → param `investissement` [0–40, pas 2]
  - `transition_renovation` → param `renovation` [0–40, pas 2]
  - `transition_taxe_carbone` → param `taxe_carbone` [0–200, pas 5]

## `tva_energie` — TVA Énergie
- type : `fonction` · catégorie : `fiscalite`
- paramètres lus par le handler :
  - `taux` (défaut : `0.2`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `tva_energie_taux` → param `taux` [0.055–0.2, pas 0.005]

## `tva_rate` — Taux de TVA
- type : `fonction` · catégorie : `fiscalite`
- paramètres lus par le handler :
  - `taux` (défaut : `0.2`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat` (apiFormat.js) / `LEVER_META` (leverMeta.js)) :
  - `tva_taux` → param `taux` [0.15–0.25, pas 0.005]

## Sliders hors handlers Python

Ces sliders ne passent pas par un handler Python de `measure_handlers`. **Cela ne signifie pas qu'ils sont sans effet** — voir les deux catégories ci-dessous.

### Mesures formule (ASTEVAL) — effet réel sur le solde

Pilotées par une formule déclarative dans `policy_measures.json` (évaluée via ASTEVAL, cf. `orchestrator.py`). Elles **modifient bien dépenses/recettes et le solde** ; simplement modélisées par formule plutôt que par un handler Python.

- `collectivites_dotation` → `collectivites`.`dotation`
- `collectivites_investissement` → `collectivites`.`investissement`
- `defense_budget` → `defense`.`budget`
- `depenses_credits_etat` → `depenses_publiques`.`credits_etat`
- `depenses_ondam` → `depenses_publiques`.`ondam`
- `depenses_transferts_capital` → `depenses_publiques`.`transferts_capital`
- `immigration_ame` → `immigration`.`ame`
- `immigration_integration` → `immigration`.`integration`
- `transferts_etranger_montant` → `transferts_etranger`.`montant`
