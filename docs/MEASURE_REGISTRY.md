# MEASURE_REGISTRY — Contrat de paramètres (GÉNÉRÉ)

> **NE PAS ÉDITER À LA MAIN.** Généré par `scripts/generate_measure_registry.py` depuis les lectures du dict `params` dans le corps des méthodes `measure_handlers`. Toute édition manuelle sera écrasée et fait échouer la CI (`tests/test_measure_registry_sync.py`).

Vérité = corps des méthodes `measure_handlers` + `constants.INTENSITE_DOMAINS`. Le bloc `parametres` de `policy_measures.json` n'est PAS le contrat.

## `abattement_retraites` — Réforme abattement fiscal retraités
- type : `fonction` · catégorie : `fiscalite`
- paramètres lus par le handler :
  - `reforme_active` (défaut : `0`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `abattement_retraites_reforme` → param `reforme_active` [0–1, pas 1]

## `asu` — Allocation Sociale Unique (ASU)
- type : `fonction` · catégorie : `social`
- flags : `VERIFIED_ALIVE_config_asu_defaults`
- paramètres lus par le handler :
  - `asu_activation` (défaut : `0`)
  - `asu_plafonnement` (défaut : `0.65`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `asu_activation` → param `asu_activation` [0–1, pas 1]
  - `asu_plafonnement` → param `asu_plafonnement` [0.5–0.7, pas 0.05]

## `chomage_alloc` — Assurance chômage
- type : `fonction` · catégorie : `social`
- paramètres lus par le handler :
  - `degressivite` (défaut : `False`)
  - `duree` (défaut : `None`)
  - `montant` (défaut : `None`)
  - `taux_remplacement` (défaut : `0.6`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `chomage_duree` → param `duree` [12–36, pas 3]
  - `chomage_taux_remplacement` → param `taux_remplacement` [0.45–0.8, pas 0.05]

## `cotisations_patronales` — Cotisations patronales
- type : `fonction` · catégorie : `competitivite`
- paramètres lus par le handler :
  - `taux` (défaut : `0.27`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `cotisations_patronales_taux` → param `taux` [0.15–0.35, pas 0.01]

## `cotisations_salariales` — Cotisations salariales
- type : `fonction` · catégorie : `fiscalite`
- paramètres lus par le handler :
  - `baisse_points` (défaut : `0.0`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `cotisations_salariales_baisse` → param `baisse_points` [0–5, pas 0.5]

## `csg` — CSG/CRDS
- type : `fonction` · catégorie : `fiscalite`
- paramètres lus par le handler :
  - `progressive` (défaut : `0`)
  - `taux` (défaut : `0.097`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `csg_progressive` → param `progressive` [0–1, pas 1]
  - `csg_taux` → param `taux` [0.08–0.12, pas 0.001]

## `education` — Éducation nationale
- type : `fonction` · catégorie : `depenses`
- paramètres lus par le handler :
  - `budget` (défaut : `65`)
  - `enseignants` (défaut : `0`)
  - `salaires` (défaut : `0`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `education_budget` → param `budget` [60–90, pas 2]
  - `education_enseignants` → param `enseignants` [-20000–60000, pas 5000]
  - `education_salaires` → param `salaires` [0–15, pas 1]

## `elargissement_ir` — Élargissement de la base IR
- type : `fonction` · catégorie : `fiscalite`
- paramètres lus par le handler :
  - `taux_contribuables_cible` (défaut : `0.45`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `elargissement_ir_cible` → param `taux_contribuables_cible` [0.45–0.7, pas 0.01]

## `exonerations_salaires` — Exonérations hausses salaires
- type : `fonction` · catégorie : `social`
- flags : `INTENSITE_DRIVEN`
- paramètres lus par le handler :
  - `intensite` (domaine : `[0.0, 1.0]`, défaut : `None`)
  - `seuil_hausse` (défaut : `0.01`)
  - `taux_exoneration` (défaut : `0.0`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `exo_salaires_intensite` → param `intensite` [0–1, pas 0.1]

## `fiscalite_patrimoine` — Fiscalité du patrimoine
- type : `fonction` · catégorie : `fiscalite`
- flags : `INTENSITE_DRIVEN`
- paramètres lus par le handler :
  - `intensite` (domaine : `[-0.3, 0.3]`, défaut : `None`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `fiscalite_patrimoine_intensite` → param `intensite` [-0.3–0.3, pas 0.05]

## `fonction_publique` — Fonction publique
- type : `fonction` · catégorie : `depenses`
- paramètres lus par le handler :
  - `effectifs` (défaut : `0`)
  - `point_indice` (défaut : `0`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `fp_effectifs` → param `effectifs` [-100000–50000, pas 10000]
  - `fp_point_indice` → param `point_indice` [-2–5, pas 0.5]

## `fonction_publique_reforme` — Réforme fonction publique
- type : `fonction` · catégorie : `depenses`
- paramètres lus par le handler :
  - `digitalisation` (défaut : `0`)
  - `fusion_agences` (défaut : `0`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `fp_digitalisation` → param `digitalisation` [0–100, pas 5]
  - `fp_fusion_agences` → param `fusion_agences` [0–100, pas 5]

## `fraude_fiscale` — Lutte contre la fraude fiscale
- type : `fonction` · catégorie : `fiscalite`
- flags : `KNOWN_SEMANTIC_EFFORT_BIMODAL`
- paramètres lus par le handler :
  - `effort` (défaut : `0`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `fraude_effort` → param `effort` [0–1, pas 0.1]

## `fraude_sociale` — Lutte contre la fraude sociale
- type : `fonction` · catégorie : `social`
- flags : `KNOWN_SEMANTIC_EFFORT_BIMODAL`
- paramètres lus par le handler :
  - `effort` (défaut : `0`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `fraude_sociale_effort` → param `effort` [0–1, pas 0.1]

## `impot_revenu` — Impôt sur le revenu
- type : `fonction` · catégorie : `fiscalite`
- paramètres lus par le handler :
  - `decote` (défaut : `1.0`)
  - `taux_superieur` (défaut : `0.45`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `ir_decote` → param `decote` [0.5–1.5, pas 0.1]
  - `ir_taux_superieur` → param `taux_superieur` [0.4–0.6, pas 0.01]

## `impot_societes` — Impôt sur les sociétés
- type : `fonction` · catégorie : `fiscalite`
- paramètres lus par le handler :
  - `niches` (défaut : `0`)
  - `taux` (défaut : `0.25`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `is_taux` → param `taux` [0.15–0.35, pas 0.01]

## `impots_production` — Impôts sur la production
- type : `fonction` · catégorie : `competitivite`
- paramètres lus par le handler :
  - `montant` (défaut : `97`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `impots_production` → param `montant` [37–125, pas 5]

## `is_exceptionnel_tge` — IS exceptionnel TGE
- type : `fonction` · catégorie : `competitivite`
- paramètres lus par le handler :
  - `montant` (défaut : `8`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `is_exceptionnel_tge` → param `montant` [0–15, pas 1]

## `isf_climatique` — ISF Climatique
- type : `fonction` · catégorie : `fiscalite`
- flags : `INTENSITE_DRIVEN`
- paramètres lus par le handler :
  - `intensite` (domaine : `[0.0, 1.0]`, défaut : `None`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `isf_intensite` → param `intensite` [0–1, pas 0.01]

## `niches_fiscales_tge` — Niches fiscales grandes entreprises
- type : `fonction` · catégorie : `competitivite`
- paramètres lus par le handler :
  - `montant` (défaut : `58`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `niches_fiscales_tge` → param `montant` [5–70, pas 5]

## `niches_sociales_tge` — Niches sociales grandes entreprises
- type : `fonction` · catégorie : `competitivite`
- paramètres lus par le handler :
  - `montant` (défaut : `70`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `niches_sociales_tge` → param `montant` [10–80, pas 5]

## `optimisation_dette` — Optimisation dette
- type : `fonction` · catégorie : `depenses`
- flags : `INTENSITE_DRIVEN`
- paramètres lus par le handler :
  - `intensite` (domaine : `[0.0, 1.0]`, défaut : `None`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `optimisation_dette` → param `intensite` [0–1, pas 0.1]

## `prestations_indexation` — Indexation prestations sociales
- type : `fonction` · catégorie : `social`
- paramètres lus par le handler :
  - `taux_indexation` (défaut : `1.0`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `prestations_indexation` → param `taux_indexation` [0–100, pas 5]

## `rabot_uniforme` — Rabot budgétaire uniforme
- type : `fonction` · catégorie : `depenses`
- paramètres lus par le handler :
  - `exclure_defense` (défaut : `1`)
  - `exclure_dette` (défaut : `1`)
  - `exclure_ue` (défaut : `1`)
  - `taux_reduction` (défaut : `0`)
- sliders UI : _(aucun — mesure pilotée par scénario/API uniquement)_

## `recherche_publique` — Recherche publique
- type : `formule` · catégorie : `economie`
- paramètres lus par le handler :
  - `budget` (défaut : `10`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `recherche_budget` → param `budget` [0–20, pas 1]

## `retraites` — Réforme des retraites
- type : `fonction` · catégorie : `social`
- paramètres lus par le handler :
  - `age_depart` (défaut : `62.75`)
  - `duree_cotisation` (défaut : `42.5`)
  - `indexation` (défaut : `1.0`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `retraites_age` → param `age_depart` [60–67, pas 0.5]
  - `retraites_duree` → param `duree_cotisation` [40–45, pas 0.5]
  - `retraites_indexation` → param `indexation` [0.5–1.2, pas 0.05]

## `sante` — Système de santé
- type : `fonction` · catégorie : `social`
- paramètres lus par le handler :
  - `effort_ambu` (défaut : `0`)
  - `effort_hopital` (défaut : `0`)
  - `effort_prev_org` (défaut : `0`)
  - `franchise_participation_taux` (défaut : `100`)
  - `prevention_budget` (défaut : `5.0`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `effort_ambu` → param `effort_ambu` [0–100, pas 5]
  - `effort_hopital` → param `effort_hopital` [0–100, pas 5]
  - `effort_prev_org` → param `effort_prev_org` [0–100, pas 5]
  - `franchise_participation_taux` → param `franchise_participation_taux` [0–200, pas 10]
  - `prevention_budget` → param `prevention_budget` [5–8, pas 0.5]

## `smic` — SMIC
- type : `fonction` · catégorie : `social`
- paramètres lus par le handler :
  - `montant_brut` (défaut : `1800`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `smic_montant_brut` → param `montant_brut` [1400–2200, pas 50]

## `subventions_tge` — Subventions grandes entreprises
- type : `fonction` · catégorie : `competitivite`
- paramètres lus par le handler :
  - `montant` (défaut : `35`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `subventions_tge` → param `montant` [5–50, pas 5]

## `taxe_superprofits` — Taxe sur les superprofits
- type : `fonction` · catégorie : `fiscalite`
- flags : `INTENSITE_DRIVEN`
- paramètres lus par le handler :
  - `intensite` (domaine : `[0.0, 1.0]`, défaut : `None`)
  - `seuil_hausse` (défaut : `1.2`)
  - `taux` (défaut : `0.25`)
  - `tous_secteurs` (défaut : `True`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `superprofits_intensite` → param `intensite` [0–1, pas 0.1]

## `transition_ecologique` — Transition écologique
- type : `fonction` · catégorie : `economie`
- paramètres lus par le handler :
  - `investissement` (défaut : `0`)
  - `renovation` (défaut : `0`)
  - `taxe_carbone` (défaut : `44.6`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `transition_investissement` → param `investissement` [0–40, pas 2]
  - `transition_renovation` → param `renovation` [0–40, pas 2]
  - `transition_taxe_carbone` → param `taxe_carbone` [0–200, pas 5]

## `tva_energie` — TVA Énergie
- type : `fonction` · catégorie : `fiscalite`
- paramètres lus par le handler :
  - `taux` (défaut : `0.2`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `tva_energie_taux` → param `taux` [0.055–0.2, pas 0.005]

## `tva_rate` — Taux de TVA
- type : `fonction` · catégorie : `fiscalite`
- paramètres lus par le handler :
  - `taux` (défaut : `0.2`)
- sliders UI (front → moteur, dérivé de `convertToAPIFormat`/`variablesConfig`) :
  - `tva_taux` → param `taux` [0.15–0.25, pas 0.005]

## Sliders hors handlers Python

Ces sliders ne passent pas par un handler Python de `measure_handlers`. **Cela ne signifie pas qu'ils sont sans effet** — voir les deux catégories ci-dessous.

### Mesures formule (ASTEVAL) — effet réel sur le solde

Pilotées par une formule déclarative dans `policy_measures.json` (évaluée via ASTEVAL, cf. `orchestrator.py`). Elles **modifient bien dépenses/recettes et le solde** ; simplement modélisées par formule plutôt que par un handler Python.

- `collectivites_dotation` → `collectivites`.`dotation`
- `collectivites_investissement` → `collectivites`.`investissement`
- `defense_budget` → `defense`.`budget`
- `immigration_ame` → `immigration`.`ame`
- `immigration_integration` → `immigration`.`integration`
