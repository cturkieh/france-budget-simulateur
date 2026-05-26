"""Section 1 — Efficience et organisation (DERNIÈRE section splittée, Phase 1.7).

Mesures couvertes (5 handlers) :
- ``fraude_fiscale`` : lutte contre la fraude fiscale. Cible convertie en
  Md€ (intensité 0-1 → 0-30 Md€, ou legacy direct), montée en puissance
  5 ans (20 % → 100 % en 2030, rendements décroissants ensuite, plancher
  70 %). Recettes réelles = espérées × 68 % (recouvrement DGFiP 2024),
  dépenses = 15 % des espérées. Effet ``recettes`` ET ``depenses``.
- ``fraude_sociale`` : lutte contre la fraude sociale (RSA/APL). ROI 8,75x
  (croisement fichiers CAF/Pôle Emploi, baseline structurelle), phasing
  4 ans, recouvrement 70 %, plafond NIVEAU 13 Md€ puis cap IGAS 8 Md€,
  **puis** anti-double-comptage ASU (-30 %·phasing à plein régime) —
  contrepartie de l'exclusion des gains fraude IA côté ``_apply_asu``
  (cf section Couplages).
- ``fonction_publique_reforme`` : réforme structurelle FP (fusion agences
  + digitalisation). Coûts initiaux 2026-2029 (0,15 Md€/point/an) puis
  gains via non-remplacement (157 k départs/an × 40 k€, taux non-remplacé
  fonction de l'intensité, montée 0,3 → 1,0). Pénalité dégradation
  service si ``fusion`` > 7 et ``digitalisation`` < 3.
- ``fonction_publique`` : effectifs (±) et point d'indice. Base 5,5 M
  agents, masse salariale 330 Md€, coût moyen 60 k€/agent. Impact
  ``pouvoir_achat`` one-time, asymétrie volontaire (suppressions =
  attrition naturelle, pas d'effet PA sur les actifs). ``int(...)`` sur
  ``variation_effectifs`` au logging : le frontend JSON peut envoyer un
  float (25000.0) là où ``{:+d}`` exige un int — garde-fou Phase 0.8 à
  préserver tel quel.
- ``optimisation_dette`` : optimisation de la gestion de dette. Économie
  ~2,5 Md€ × intensité, effet temporaire 2026-2030 uniquement.

Convention d'application :
- Profil « EFFICIENCE » : récupérer de l'argent dû / optimiser l'interne
  ne crée pas de valeur économique → ``gini`` / ``pouvoir_achat`` /
  ``competitivite`` neutralisés à 0 pour fraude_fiscale, fraude_sociale,
  fonction_publique_reforme, optimisation_dette. Seul ``fonction_publique``
  porte un effet ``pouvoir_achat`` (point d'indice / créations de postes),
  gated one-time par ``self._is_first_year_change('fonction_publique', …)``
  (méthode de l'hôte). Voir docs/METHODOLOGIE.md § "Lutte contre la
  Fraude" et § "Fonction Publique".
- Garde précoce ``if <cible> == 0: return 0, 0, {}`` dans les 5 handlers
  (mesure inactive = neutre) — PRÉSERVÉ tel quel du monolithe.

Sources principales :
- DGFiP 2024, Cour des comptes 2025 — fraude fiscale.
- HCFPS 2024, CNAF 2023, Cour des comptes 2025 — fraude sociale.
- METHODOLOGIE.md § Fonction Publique — réforme FP.
- DGAFP 2024, INSEE 2024 — effectifs / point d'indice FP.
- Cour des comptes 2025, IGF 2024 — optimisation dette.

Couplages avec ``BudgetSimulatorV45`` (instance hôte du mixin) :
- LIT la méthode ``self._is_first_year_change`` et le sink de logs
  ``self.debug_logs`` (via ``_log_debug``, sans incidence sur les sorties
  de simulation), fournis par la base class (simulator.py).
- ``_apply_fraude_sociale`` applique l'anti-double-comptage ASU en
  dérivant le phasing ASU de ``self.mesures`` + l'année via la SOURCE
  UNIQUE ``handlers._phasing.asu_phasing`` (entrée du run, lecture
  seule). **Plus aucun couplage par attribut d'instance** : l'ancien
  contrat producteur/consommateur fragile (lecture de
  ``self.asu_active``/``self.asu_phasing`` posés par ``_apply_asu``,
  sensible à l'ordre d'exécution — items type-design F1/F3) est
  DISSOUS. Le consommateur est auto-suffisant : indépendant de l'ordre
  des handlers et du fait que ``_apply_asu`` ait tourné ou non
  (ASU absente de ``self.mesures`` ou ``asu_activation == 0`` →
  ``asu_phasing`` renvoie 0.0 → réduction nulle = comportement correct ;
  prédicat ``== 0`` et non ``== 1`` à dessein, cf ``asu_phasing``).
- N'ÉCRIT aucun attribut d'instance : les 5 handlers sont purement
  fonctionnels (entrée params → sortie impacts). Aucun état propre au
  mixin. Aucun handler n'appelle un handler d'un autre mixin (invariant
  ADR Phase 1.2).

Sous-sections : ``fraude_fiscale`` / ``fraude_sociale`` (lutte fraude),
puis ``fonction_publique_reforme`` / ``fonction_publique`` /
``optimisation_dette`` (Sous-section 1.2 : Efficience Dépenses).
"""
from typing import TYPE_CHECKING, Dict, Tuple

from ..constants import POLICY_START_YEAR
from .._logging import _log_debug
from ._phasing import _year_phasing, asu_phasing
from ._types import ImpactsDict


# Idiome mixin-self typing : NE PAS factoriser dans _types.py (casse la
# liaison self mypy + risque MRO). Réplication volontaire 7×. Cf Lot D.
if TYPE_CHECKING:
    from ._types import _SimulatorState

    _MixinBase = _SimulatorState
else:
    _MixinBase = object


class EfficienceMixin(_MixinBase):
    """Handlers Section 1 — Efficience et organisation."""

    def _apply_fraude_fiscale(self, measure: Dict, params: Dict, year: int, gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Lutte fraude fiscale avec montée progressive (5 ans). Potentiel 80-100 Md€, ROI 13x (IA intégrée baseline).
        Sources: DGFiP 2024, Cour comptes 2025. Voir METHODOLOGIE.md § Lutte contre la Fraude."""
        # Conversion intensité (0-1) vers Md€ (0-30)
        # Frontend v4.5+ envoie intensité 0-1, mais legacy peut envoyer Md€ directement
        effort_raw = params.get('effort', 0)
        if effort_raw <= 1.0:
            # Mode intensité (0-1) → conversion en Md€
            recettes_cible = effort_raw * 30  # 0-30 Md€ (Cour des comptes: DGFiP récupère ~15 Md€/an, max réaliste ~30 Md€)
        else:
            # Mode legacy (déjà en Md€)
            recettes_cible = effort_raw

        if recettes_cible == 0:
            return 0, 0, {}

        # Année de référence
        years_elapsed = year - POLICY_START_YEAR

        # ===== MONTÉE EN PUISSANCE (5 ANS) =====
        if years_elapsed < 0:
            # Avant 2026 : pas d'effet
            progress = 0.0
        elif years_elapsed == 0:
            # 2026 (Année 1) : 20%
            progress = 0.20
        elif years_elapsed == 1:
            # 2027 (Année 2) : 35%
            progress = 0.35
        elif years_elapsed == 2:
            # 2028 (Année 3) : 50%
            progress = 0.50
        elif years_elapsed == 3:
            # 2029 (Année 4) : 70% (objectif gouvernement 40 Md€ détectés)
            progress = 0.70
        elif years_elapsed == 4:
            # 2030 (Année 5) : 100% (palier maximal atteint)
            progress = 1.0
        else:
            # 2031+ : rendements décroissants (les cas faciles sont traités en premier)
            years_past_peak = years_elapsed - 4
            progress = max(0.70, 1.0 - years_past_peak * 0.05)  # -5%/an après pic, plancher 70%

        # ===== RECETTES ESPÉRÉES =====
        recettes_esperees = recettes_cible * progress

        # ===== RECETTES RÉELLES (68% d'efficacité) =====
        # Taux recouvrement empirique DGFiP 2024 : 11.4 / 16.7 = 68.3%
        efficacite_reelle = 0.68
        delta_revenue = recettes_esperees * efficacite_reelle

        # ===== DÉPENSES (15% des recettes espérées) =====
        # Coût contrôles IT + RH : ~10k agents DGFiP + infrastructure IA
        taux_depenses = 0.15
        delta_spending = recettes_esperees * taux_depenses

        # ===== IMPACTS =====
        # EFFICIENCE : Récupération argent dû, pas de création valeur → impacts macro = 0
        impacts = {
            'depenses': delta_spending,
            'recettes': delta_revenue,
            'gini': 0,  # Pas d'impact redistributif (récupération fraude)
            'pouvoir_achat': 0,  # Pas d'impact direct sur ménages
            'competitivite': 0  # Pas d'impact sur compétitivité entreprises
        }

        # ===== LOGS DEBUG =====
        net_benefit = delta_revenue - delta_spending
        roi_observed = delta_revenue / delta_spending if delta_spending > 0 else 0

        _log_debug(self.debug_logs,
            f"Y{year}: Fraude fiscale - Cible {recettes_cible:.0f}Md€, "
            f"Progression {progress*100:.0f}%, "
            f"Espérées {recettes_esperees:.1f}Md€, "
            f"Réelles {delta_revenue:.1f}Md€ (68%), "
            f"Dépenses {delta_spending:.1f}Md€ (15%), "
            f"Net +{net_benefit:.1f}Md€ (ROI {roi_observed:.1f}x IA intégrée)"
        )

        return delta_spending, delta_revenue, impacts

    def _apply_fraude_sociale(self, measure: Dict, params: Dict, year: int,
                              gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Lutte fraude sociale (RSA, APL). Potentiel 13 Md€, ROI 8.75x (numérisation intégrée), phasing 4 ans.
        Sources: HCFPS 2024, Cour comptes 2025. Voir METHODOLOGIE.md § Lutte contre la Fraude."""
        # Conversion intensité (0-1) vers Md€ (0-3)
        # Frontend v4.5+ envoie intensité 0-1, mais legacy peut envoyer Md€ directement
        effort_raw = params.get('effort', 0)
        if effort_raw <= 1.0:
            # Mode intensité (0-1) → conversion en Md€
            budget_controles = effort_raw * 3  # 0-3 Md€
        else:
            # Mode legacy (déjà en Md€)
            budget_controles = effort_raw

        if budget_controles == 0:
            return 0, 0, {}

        # Phasing 4 ans
        years_elapsed = year - POLICY_START_YEAR
        phasing = _year_phasing(years_elapsed, (0.25, 0.50, 0.75, 1.0))

        # ===== ROI : 8.75x (numérisation/data mining intégrée par défaut) =====
        # ANCIEN MODÈLE : 7x base + 25% bonus optionnel si checkbox cochée
        # NOUVEAU MODÈLE : 8.75x baseline (croisement fichiers CAF/Pôle Emploi opérationnel)
        # Justification : CNAF 2023, HCFPS 2024, Plan antifraude 2023-2027
        # Ce n'est plus une "option" mais la réalité structurelle CAF/CPAM 2025+
        roi_base = 8.75
        efficacite_recuperation = 0.70

        # Économies
        economies_identifiees = budget_controles * roi_base * phasing
        economies_reelles = economies_identifiees * efficacite_recuperation

        # Plafond théorique 13 Md€ (fraude détectée max), puis cap IGAS :
        # la fraude sociale réellement recouvrable est estimée 6-8 Md€/an
        # (IGAS). C'est un plafond de NIVEAU (montant max recouvrable),
        # DISTINCT du mécanisme anti-double-comptage ASU ci-dessous (ne pas
        # reconfondre les deux — c'est cette confusion qui rendait jadis
        # la réduction ASU inerte : 8 < plafond ASU ∈ [9,1 ; 13]).
        economies_reelles = min(economies_reelles, 13.0)  # plafond théorique (shadowé tant que 8 < 13)
        economies_reelles = min(economies_reelles, 8.0)    # cap IGAS = borne effective

        # Anti-double-comptage ASU : si l'ASU est active, ses contrôles IA
        # intégrés captent déjà une part de la fraude sociale → ce levier
        # n'en récupère que le RÉSIDUEL (jusqu'à -30 % à plein régime,
        # 0.30·phasing). Contrepartie OBLIGATOIRE de l'exclusion symétrique
        # des gains fraude IA (+3-6 Md€) côté `_apply_asu` (cf docstring
        # depenses.py) : sans elle, ces montants ne sont comptés NI là NI
        # ici. Appliqué APRÈS le cap IGAS (sinon shadowé). Dérivé de
        # `self.mesures` + l'année via la source unique `asu_phasing` →
        # AUCUNE dépendance à l'ordre d'exécution des handlers.
        asu_ph = asu_phasing(self.mesures, year)
        economies_reelles *= (1 - 0.30 * asu_ph)

        delta_spending = -economies_reelles + budget_controles

        impacts = {
            'depenses': delta_spending,
            'gini': 0.0,
            'pouvoir_achat': 0.0,
            'competitivite': 0.0
        }

        roi_observe = economies_reelles / budget_controles if budget_controles > 0 else 0
        asu_info = (f", anti-double-comptage ASU -{0.30 * asu_ph * 100:.0f}%"
                    if asu_ph > 0 else "")
        _log_debug(self.debug_logs,
            f"Y{year}: Fraude sociale - Budget {budget_controles:.1f}Md€, "
            f"Économies {economies_reelles:.1f}Md€, ROI {roi_observe:.1f}x (numérisation intégrée){asu_info}"
        )

        return delta_spending, 0, impacts

    # -----------------------------------------------------------------------
    # Sous-section 1.2 : Efficience Dépenses
    # -----------------------------------------------------------------------


    def _apply_fonction_publique_reforme(self, measure: Dict, params: Dict, year: int,
                                         gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Réforme structurelle FP (fusion agences, digitalisation). Phasing 2026-2030. Base 157k départs/an × 40k€.
        Voir METHODOLOGIE.md § Fonction Publique."""
        # Les sliders sont maintenant en % (0-100), on les convertit en 0-10
        fusion = params.get('fusion_agences', 0) / 10
        digitalisation = params.get('digitalisation', 0) / 10
        year_idx = year - 2025

        # Intensité totale (0-20)
        intensite_totale = fusion + digitalisation

        delta_spending = 0

        # PHASE 1: COÛTS INITIAUX (2026-2029)
        if 1 <= year_idx <= 4:
            # Coûts: audits, formation, systèmes IT
            # Formule: 0.15 Md€ par point d'intensité/an
            cout_annuel = intensite_totale * 0.15
            delta_spending += cout_annuel
            _log_debug(self.debug_logs, f"Y{year}: Réforme FP - Coûts investissement: +{cout_annuel:.1f} Md€")

        # PHASE 2: GAINS VIA NON-REMPLACEMENTS (2027+)
        if year_idx >= 2:
            # Départs naturels annuels
            departs_annuels = 157000
            salaire_moyen = 40000

            # Taux de non-remplacement selon intensité
            # 0 = 100% remplacement (0% économie)
            # 10 = 50% remplacement (50% économie)
            # 20 = 33% remplacement (67% économie)
            if intensite_totale == 0:
                taux_non_remplacement = 0
            elif intensite_totale <= 10:
                taux_non_remplacement = intensite_totale * 0.05  # 0-50%
            else:
                taux_non_remplacement = 0.50 + (intensite_totale - 10) * 0.017  # 50-67%

            # Montée en puissance progressive
            if year_idx == 2:  # 2027
                efficacite = 0.3  # Démarrage lent
            elif year_idx == 3:  # 2028
                efficacite = 0.6
            elif year_idx == 4:  # 2029
                efficacite = 0.85
            else:  # 2030+
                efficacite = 1.0  # Plein effet

            # Calcul économies annuelles
            postes_non_remplaces = departs_annuels * taux_non_remplacement * efficacite
            economie_annuelle = postes_non_remplaces * salaire_moyen / 1e9

            # Cumul des économies sur les années
            annees_ecoulees = min(year_idx - 1, 8)  # Cap à 8 ans d'effet cumulé
            # Chaque cohorte annuelle de non-remplacement s'accumule linéairement
            # En année N : N cohortes actives, chacune générant economie_annuelle
            # Plafonné à 8 ans (turnover stabilisé)
            economie_cumulee = economie_annuelle * min(annees_ecoulees + 1, 8)

            delta_spending -= economie_cumulee

            _log_debug(self.debug_logs,
                f"Y{year}: Réforme FP - Non-remplacement {taux_non_remplacement*100:.0f}% "
                f"(efficacité {efficacite*100:.0f}%), économies: -{economie_cumulee:.1f} Md€"
            )

        # Impact qualité service si intensité excessive sans digitalisation
        if fusion > 7 and digitalisation < 3 and year_idx >= 3:
            penalite = 0.3  # Dégradation service public
            delta_spending += penalite
            _log_debug(self.debug_logs, f"Y{year}: Pénalité dégradation service: +{penalite:.1f} Md€")

        # EFFICIENCE : Optimisation administrative, pas d'impact économique réel → impacts macro = 0
        impacts = {
            'depenses': delta_spending,
            'gini': 0,  # Pas d'impact redistributif (optimisation interne)
            'pouvoir_achat': 0,  # Pas d'impact direct sur ménages
            'competitivite': 0  # Gains productivité admin ≠ compétitivité entreprises
        }
        return delta_spending, 0, impacts

    def _apply_fonction_publique(self, measure: Dict, params: Dict, year: int,
                                  gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Effectifs et point d'indice FP. Impacts directs sur masse salariale.
        Base: 5.5M agents, masse salariale 330 Md€, salaire moyen 60k€/an (charges incluses).
        Sources: DGAFP 2024, INSEE 2024."""

        variation_effectifs = params.get('effectifs', 0)  # -100k à +50k
        hausse_point_indice = params.get('point_indice', 0)  # -2% à +5%

        if variation_effectifs == 0 and hausse_point_indice == 0:
            return 0, 0, {}

        # Constantes FP
        masse_salariale_base = 330  # Md€
        cout_moyen_agent = 60000  # €/an (salaire + charges)

        delta_spending = 0

        # 1. VARIATION EFFECTIFS
        # Coût/économie = variation × coût moyen agent
        if variation_effectifs != 0:
            impact_effectifs = variation_effectifs * cout_moyen_agent / 1e9  # en Md€
            delta_spending += impact_effectifs
            # Cast int explicite : JSON frontend peut envoyer 25000.0 (float), `{:+d}` exige int.
            _log_debug(self.debug_logs,
                f"Y{year}: FP Effectifs - {int(variation_effectifs):+d} agents = {impact_effectifs:+.1f} Md€")

        # 2. POINT D'INDICE
        # Hausse de X% = X% × masse salariale
        if hausse_point_indice != 0:
            impact_point_indice = (hausse_point_indice / 100) * masse_salariale_base
            delta_spending += impact_point_indice
            _log_debug(self.debug_logs,
                f"Y{year}: FP Point indice - {hausse_point_indice:+.1f}% = {impact_point_indice:+.1f} Md€")

        # IMPACTS MACRO
        # Pouvoir d'achat : ONE-TIME (effet demande initial)
        # Hausse point indice → +PA pour fonctionnaires (15% pop active)
        # +1% point indice = +0.003 PA (effet modéré car 15% de la pop)
        # Créations postes = emplois stables = +PA (+10k postes = +0.001 PA)
        params_fp = {
            'effectifs': variation_effectifs,
            'point_indice': hausse_point_indice
        }

        if self._is_first_year_change('fonction_publique', params_fp):
            pouvoir_achat = hausse_point_indice * 0.003
            # Asymétrie volontaire : suppressions de postes = non-remplacement de départs en retraite
            # (attrition naturelle, pas de licenciements), donc pas d'effet PA direct sur les actifs.
            # Création : 10k postes × 60k€ × 70% net = 0.4 Md€ → +0.025% PA (calibration INSEE).
            if variation_effectifs > 0:
                pouvoir_achat += variation_effectifs / 40000 * 0.001
        else:
            pouvoir_achat = 0.0

        # Compétitivité : PAS D'IMPACT DIRECT
        # Lien masse salariale FP → compétitivité entreprises trop indirect
        # (Hausse FP → Déficit → Dette → Prélèvements futurs = effet 5-10 ans, négligeable)
        # Compétitivité concerne secteur privé, pas secteur public
        competitivite = 0.0

        # Gini : peu d'impact (salaires FP déjà compressés)
        gini = 0

        impacts = {
            'depenses': delta_spending,
            'gini': gini,
            'pouvoir_achat': pouvoir_achat,
            'competitivite': competitivite
        }

        _log_debug(self.debug_logs,
            f"Y{year}: FP Total = {delta_spending:+.1f} Md€ (PA: {pouvoir_achat:+.4f}, Compét: {competitivite:+.4f})")

        return delta_spending, 0, impacts


    def _apply_optimisation_dette(self, measure: Dict, params: Dict, year: int,
                                  gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Optimisation dette. Potentiel 1-2.5 Md€. Temporaire 2026-2030. Impacts macro=0.
        Sources: Cour comptes 2025, IGF 2024. Voir METHODOLOGIE.md § Notes Methodologiques Generales (pas de section dédiée — levier technique mineur)."""
        intensite = params.get('intensite', 0)

        if intensite == 0:
            return 0, 0, {}

        year_idx = year - 2025

        # Effet temporaire 2026-2030
        if year_idx <= 0 or year_idx > 5:
            delta_spending = 0
        else:
            economie_max = 2.5
            delta_spending = -economie_max * intensite

        impacts = {
            'depenses': delta_spending,
            'gini': 0.0,
            'pouvoir_achat': 0.0,
            'competitivite': 0.0
        }

        _log_debug(self.debug_logs,
            f"Y{year}: Optimisation dette - Intensité {intensite*100:.0f}%, "
            f"Économies {-delta_spending:.1f}Md€"
        )

        return delta_spending, 0, impacts
