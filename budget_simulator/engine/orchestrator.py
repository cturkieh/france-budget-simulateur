"""Bloc moteur — Orchestrateur (boucle de simulation + dispatch des mesures).

Méthodes couvertes :
- ``simulate`` : boucle de simulation principale (année par année).
  Réinitialise l'état, amorce 2025, puis pour chaque année : démographie,
  recettes/dépenses de base, application des mesures, croissance,
  inflation, dette, chômage, Gini, pouvoir d'achat, compétitivité,
  validation, agrégation des résultats. Orchestre les 11 méthodes macro
  des autres mixins (10 ``calculate_*`` + ``update_potential_growth`` ;
  ``update_demography`` est propre à l'orchestrateur).
- ``apply_measures`` : dispatch central des mesures (handler Python
  prioritaire, sinon formule ASTEVAL), plafonds 5 % PIB / mesure et
  10 % PIB total (FMI 2010), flag ``HANDLER_FAILED_KEY`` + mode
  ``BUDGETLAB_STRICT``.
- ``detect_active_measures`` : liste les mesures écartées de leur valeur
  par défaut (log de débogage en 2026).
- ``update_demography`` : met à jour la population (taux net +
  vieillissement post-2030).

Ce mixin est l'ASSEMBLEUR : il ne porte presque aucune logique
économique propre (déléguée aux mixins ``handlers/`` et ``engine/`` via
``self``), mais lit/écrit massivement l'état d'instance de
``BudgetSimulatorV45``. Le contrat producteur/consommateur DÉTAILLÉ de
chaque état partagé (``recettes_precedentes``, ``inflation_precedente``,
``_potential_growth_bonus``, ``_fiscal_impulses``, ``debt_structure``,
``_spending_factors``, ...) est documenté côté mixin PRODUCTEUR
(``engine/revenues.py``, ``engine/inflation.py``, ``engine/growth.py``,
``engine/debt.py``, ``engine/expenditures.py``) — non redupliqué ici
pour éviter la dérive documentaire.

Le SEUL invariant que ce mixin porte en propre (non documentable côté
producteur, car imposé par ``simulate`` seul) est le CONTRAT D'ORDRE
des appels dans la boucle annuelle :
``calculate_revenues`` / ``calculate_expenditures`` (base organique)
→ ``apply_measures`` (deltas mesures ; ``budget_effort`` en dérive)
→ ``calculate_growth`` / ``calculate_inflation`` (consomment
``budget_effort``) → ``update_potential_growth`` (clôt l'année).
Réordonner ces appels casse les contrats producteur/consommateur même
si chaque méthode reste byte-identique.

Note historique (Phase 2, 2026-05-16) : un ajustement d'élasticité
recettes post-``calculate_inflation`` a été supprimé — voir le
tombstone inline (boucle annuelle) et ``docs/REFACTOR_SPLIT_PLAN.md``.

Helpers / état hôte via MRO (NON migrés, restent sur
``BudgetSimulatorV45``) : ``_reset_state``, ``_get_default_values``,
``_apply_complex_measure`` (Section 7 legacy : dispatch handler Python,
sous garde `measure_id in measure_handlers` côté ``apply_measures``),
``validator`` (``EconomicValidator``), ``aeval``
(``asteval.Interpreter``), ``measure_registry`` / ``measure_handlers``,
constantes de classe (``INVESTMENT_FLOW_MEASURES`` ...), et tout l'état
d'instance initialisé dans ``__init__`` / ``_reset_state``.

``_BUDGET_KEYS`` (détail interne, aucun consommateur externe) est
local à ce module. ``INDEXATION_BASELINE_RATIO`` (constante calibrée
sourcée, importée par un test) est déplacée vers
``budget_simulator/constants.py`` (foyer canonique des constantes
économiques, cohérent avec ``HANDLER_FAILED_KEY`` /
``CHARGES_INTERET_MD_EUR``). Retrait symétrique de ``simulator.py``
dans le même commit (leçon Phase 1.4→1.7).

Catch large pré-existant : ``apply_measures`` enveloppe chaque mesure
d'un ``except Exception`` qui logge ``logger.error(exc_info=True)`` +
pose ``HANDLER_FAILED_KEY`` dans ``impacts`` + escalade si
``BUDGETLAB_STRICT`` (fail-fast CI). Ce catch-ci n'est PAS silencieux
(``logger.error`` + flag d'état observable + golden master Phase 0.7) —
à distinguer du catch silencieux supply-side de ``update_potential_growth``
(``engine/growth.py``, tracé Phase 2). Préservé byte-for-byte.

Sink de logs : ``self.debug_logs`` via ``_log_debug``.
Tous attributs d'instance de ``BudgetSimulatorV45``.
"""
import logging
import os
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from .._logging import _log_debug
from ..constants import CHARGES_INTERET_MD_EUR, HANDLER_FAILED_KEY, INDEXATION_BASELINE_RATIO
from ._param_domain import validate_intensite_domain

logger = logging.getLogger(__name__)

_BUDGET_KEYS = frozenset({'depenses', 'recettes'})


class OrchestratorMixin:
    """Bloc moteur — Orchestrateur (boucle de simulation + dispatch des mesures)."""

    def detect_active_measures(self) -> List[str]:
        """Détecte les mesures activement modifiées"""
        defaults = self._get_default_values()
        active_measures = []

        for measure_id, params in self.mesures.items():
            if measure_id not in defaults:
                continue
            for param_name, value in params.items():
                if param_name not in defaults[measure_id]:
                    continue
                default_val = defaults[measure_id][param_name]

                if isinstance(value, bool):
                    if value != default_val:
                        active_measures.append(f"{measure_id}.{param_name}={value}")
                elif isinstance(value, (int, float)):
                    threshold = 0.5 if isinstance(default_val, int) else 0.01
                    if abs(value - default_val) > threshold:
                        active_measures.append(f"{measure_id}.{param_name}={value:.2f}")

        return active_measures

    def update_demography(self, annee: int):
        """Met à jour la démographie"""
        taux_net = (
            self.demography['taux_natalite'] -
            self.demography['taux_mortalite'] +
            self.demography['solde_migratoire']
        )

        if annee >= 2030:
            taux_net -= self.demography['taux_vieillissement'] * 0.5

        self.demography['population'] *= (1 + taux_net)
        _log_debug(self.debug_logs, f"Y{annee-2025}: Population {self.demography['population']:.1f}M")

    def apply_measures(self, year: int, spending: float, revenues: float,
                       gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, Dict]:
        """
        Applique les mesures budgétaires pour ajuster dépenses et recettes.
        - Type "formule" : utilise ASTEVAL avec post-traitement (ex. CSG avec effet Laffer).
        - Type "fonction" : traitement spécifique via _apply_complex_measure.
        - Plafonne les impacts à 5% PIB par mesure, 10% PIB total (FMI, 2010).
        Returns: (dépenses ajustées, recettes ajustées, dictionnaire des impacts).
        """
        delta_spending_total = 0
        delta_revenue_total = 0
        impacts = {}
        # Log des mesures actives en 2026 pour débogage
        if year == 2026:
            active_measures = self.detect_active_measures()
            if active_measures:
                _log_debug(self.debug_logs, "=== MESURES ACTIVES ===")
                for measure in active_measures:
                    _log_debug(self.debug_logs, f" • {measure}")
            else:
                _log_debug(self.debug_logs, "=== STATUS QUO - Aucune mesure active ===")
        # Traite chaque mesure définie dans self.mesures
        # BUDGETLAB_STRICT (CI/calibration) : collecter toutes les mesures en
        # échec d'une même année et lever un ExceptionGroup APRÈS la boucle,
        # plutôt qu'un fail-fast sur la première (qui masquerait les suivantes).
        strict_mode = os.environ.get('BUDGETLAB_STRICT', '').strip().lower() in ('1', 'true', 'yes')
        strict_failures: list[Exception] = []
        for measure_id, parameters in self.mesures.items():
            if measure_id not in self.measure_registry:
                _log_debug(self.debug_logs, f"⚠ Mesure {measure_id} inconnue - ignorée")
                continue
            measure = self.measure_registry[measure_id]
            delta_spending, delta_revenue = 0, 0
            try:
                # Porte unique Lot C Item 1 : borne intensite par domaine
                # AVANT le dispatch. Tolérant = warning+clamp ; STRICT =
                # ValueError capté par l'except infra → ExceptionGroup
                # (synergie Item 3). No-op (objet identique) hors registre
                # ou intensite valide → golden master byte-identique.
                parameters = validate_intensite_domain(
                    measure_id, parameters, strict=strict_mode
                )
                if measure_id in self.measure_handlers:
                    # Python handler takes precedence over ASTEVAL formula
                    delta_spending, delta_revenue, measure_impacts = self._apply_complex_measure(
                        measure, parameters, year, gdp, inflation, unemployment
                    )
                elif measure.get('type') == 'formule':
                    # Fall back to ASTEVAL formula
                    context = {
                        'p': parameters,
                        'annee': year,
                        'pib': gdp,
                        'consommation': 0.53 * gdp,
                        'masse_salariale': 0.52 * gdp,
                        'profits': 0.25 * gdp,
                        'inflation': inflation,
                        'chomage': unemployment
                    }
                    self.aeval.symtable = context
                    result = self.aeval(measure['formule'])
                    if self.aeval.error:
                        error_msgs = [str(e.get_error()) for e in self.aeval.error]
                        logger.error("ASTEVAL formule %s: %s", measure_id, '; '.join(error_msgs))
                        self.aeval.error = []
                        result = 0
                    elif result is None:
                        result = 0
                    # Post-traitement pour ajustements spécifiques (ex. effet Laffer CSG)
                    if measure.get('cible') == 'depenses':
                        delta_spending = result
                        measure_impacts = {'depenses': delta_spending}
                    elif measure.get('cible') == 'recettes':
                        delta_revenue = result
                        measure_impacts = {'recettes': delta_revenue}
                    elif measure.get('cible') == 'mixte':
                        delta_spending = result * 0.6
                        delta_revenue = result * 0.4
                        measure_impacts = {'depenses': delta_spending, 'recettes': delta_revenue}
                else:
                    # No handler and no formula - skip
                    _log_debug(self.debug_logs, f"Mesure {measure_id}: ni handler Python ni formule ASTEVAL - ignoree")
                    continue
                # Plafonne impacts individuels à 5% PIB (FMI, 2010)
                max_impact = 0.05 * gdp
                # Detection clip : signal une mesure aux ordres de grandeur suspects (calibration ou bug)
                if abs(delta_spending) > max_impact or abs(delta_revenue) > max_impact:
                    logger.warning(
                        "CLIP 5%% PIB Y%d %s : delta_spending=%.1f delta_revenue=%.1f (max=%.1f)",
                        year, measure_id, delta_spending, delta_revenue, max_impact,
                    )
                delta_spending = np.clip(delta_spending, -max_impact, max_impact)
                delta_revenue = np.clip(delta_revenue, -max_impact, max_impact)
                # Propager le clip aux measure_impacts (sinon multiplicateur calculé sur valeur
                # non-clip mais budget appliqué sur valeur clip → incohérence interne)
                measure_impacts['depenses'] = delta_spending
                measure_impacts['recettes'] = delta_revenue
                delta_spending_total += delta_spending
                delta_revenue_total += delta_revenue

                # Vérifier si la mesure a un impact budgétaire OU macroéconomique significatif
                has_budget_impact = abs(delta_spending) > 0.1 or abs(delta_revenue) > 0.1
                has_macro_impact = (
                    abs(measure_impacts.get('gini', 0)) > 0.0001 or
                    abs(measure_impacts.get('pouvoir_achat', 0)) > 0.0001 or
                    abs(measure_impacts.get('competitivite', 0)) > 0.0001
                )

                # Inclure si impact budgétaire OU macro
                if has_budget_impact or has_macro_impact:
                    impacts[measure_id] = measure_impacts
                    if has_budget_impact:
                        _log_debug(self.debug_logs,
                            f"Mesure {measure_id}: "
                            f"Δdép={delta_spending:.1f} Md€, "
                            f"Δrec={delta_revenue:.1f} Md€"
                        )
            except Exception as e:
                logger.error("Mesure %s échouée: %s", measure_id, e, exc_info=True)
                _log_debug(self.debug_logs, f"⚠ Erreur mesure {measure_id}: {e}")
                # _handler_failed évite qu'une régression silencieuse passe quand la mesure
                # était à default (delta=0 attendu == 0 obtenu sur crash). Voir
                # docs/REFACTOR_SPLIT_PLAN.md Phase 0.7.
                impacts[measure_id] = {
                    'erreur': str(e),
                    'depenses': 0,
                    'recettes': 0,
                    HANDLER_FAILED_KEY: True,
                }
                # BUDGETLAB_STRICT (CI/calibration) escalade ; prod absorbe pour
                # ne pas casser le service citoyen. On annote l'exception de la
                # mesure fautive et on la collecte : l'ExceptionGroup est levé
                # après la boucle (cf. strict_failures supra).
                if strict_mode:
                    e.add_note(f"measure_id={measure_id}, year={year}")
                    strict_failures.append(e)
        # Fail-fast STRICT : lever en une fois toutes les exceptions handler
        # collectées, AVANT d'appliquer des totaux issus d'un calcul partiel.
        # apply_measures est appelée une fois PAR ANNÉE → strict_failures est
        # borné à l'année courante (pas d'accumulation inter-annuelle).
        # INVARIANT : aucun code exécutable ne doit s'intercaler entre la fin
        # de la boucle ci-dessus et ce raise — sinon une exception levée là
        # masquerait silencieusement les strict_failures collectées.
        if strict_failures:
            raise ExceptionGroup(
                f"{len(strict_failures)} handler(s) en échec en mode BUDGETLAB_STRICT",
                strict_failures,
            )
        # Plafonne l'impact total à 10% PIB (FMI, 2010)
        total_impact = abs(delta_spending_total) + abs(delta_revenue_total)
        if total_impact > 0.10 * gdp:
            scaling_factor = (0.10 * gdp) / total_impact
            # Plafond systémique (FMI 2010) : signal visible hors mode debug —
            # cohérent avec le CLIP 5 % PIB par mesure (un total >10 % PIB
            # traduit une calibration agrégée aberrante, pas un cas nominal).
            logger.warning(
                "CLIP 10%% PIB TOTAL Y%d : impact total %.1f Md€ > 10%% PIB "
                "(plafond=%.1f Md€) → scaling ×%.4f",
                year, total_impact, 0.10 * gdp, scaling_factor,
            )
            delta_spending_total *= scaling_factor
            delta_revenue_total *= scaling_factor
            for measure_id in impacts:
                for key, val in impacts[measure_id].items():
                    if key in _BUDGET_KEYS and isinstance(val, (int, float, np.integer, np.floating)):
                        impacts[measure_id][key] = val * scaling_factor
            _log_debug(self.debug_logs, f"Y{year}: Mesures plafonnées à 10% PIB")
        # Mise à jour des dépenses et recettes
        spending += delta_spending_total
        revenues += delta_revenue_total

        if year == 2026 or abs(delta_revenue_total) > 10:
            _log_debug(self.debug_logs, f"Y{year}: 📊 RECETTES FINALES:")
            _log_debug(self.debug_logs, f"  Base (avant mesures): {revenues - delta_revenue_total:.1f} Md€")
            _log_debug(self.debug_logs, f"  Delta mesures: {delta_revenue_total:.1f} Md€")
            _log_debug(self.debug_logs, f"  TOTAL: {revenues:.1f} Md€")
            _log_debug(self.debug_logs, f"  Ratio/PIB: {revenues/gdp*100:.1f}%")

        return spending, revenues, impacts

    def simulate(self) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
        """
        Simulation principale V4.5 avec OUTPUT_GAP DYNAMIQUE CORRIGÉ
        """
        # Réinitialiser TOUT l'état mutable avant chaque simulation
        # Sans cela, un second appel démarre depuis l'état final du premier
        self._reset_state()

        # Guard: PIB_BASE doit être > 0 pour éviter divisions par zéro
        if self.base_params['pib_base'] <= 0:
            raise ValueError(f"PIB_BASE invalide: {self.base_params['pib_base']}. Doit être > 0.")

        results_list = []
        results_detailed = []
        validation_log = []
        measure_impacts_by_year = []  # NOUVEAU: stockage des impacts par mesure par année

        # État initial
        gdp_nominal = self.pib_nominal
        gdp_real = self.pib_reel_base2025
        debt = self.dette_courante
        unemployment = self.base_params['chomage_base']
        inflation = self.base_params['inflation_base']
        growth = self.base_params['croissance_potentielle']
        output_gap = self.output_gap_courant  # -0.015 initial
        purchasing_power = 100.0  # Initialisation avant la boucle (base 100 en 2025)
        competitivite_index = 100.0  # Indice de compétitivité des entreprises (base 100 en 2025)

        # Boucle de simulation
        for year_idx in range(0, self.periods + 1):
            year = self.annee_base + year_idx
            _log_debug(self.debug_logs, f"\n{'='*50}")
            _log_debug(self.debug_logs, f"ANNÉE {year}")
            _log_debug(self.debug_logs, '='*50)

            if year_idx == 0:
                _log_debug(self.debug_logs, f"AVANT Y2026: recettes_precedentes = {self.recettes_precedentes:.1f}")
                # Année 2025
                revenues = self.base_params['recettes_base']  # 1545
                spending = self.base_params['depenses_base'] - CHARGES_INTERET_MD_EUR  # 1698 - 56 = 1642
                interest_rate = self.base_params['taux_interet_base']
                interests = CHARGES_INTERET_MD_EUR
                deficit = revenues - (spending + interests)  # 1545 - 1698 = -153
                impacts = {}
                budget_effort = 0
                multiplier = 1.0
                growth = self.base_params['croissance_2025']  # INSEE: 0.9%
                inflation = self.base_params['inflation_base']  # source unique : INFLATION_BASE (seed inertie)
                self.recettes_precedentes = revenues  # 1545 Md€
                self.croissance_precedente = growth      # 0.9%
                self.inflation_precedente = inflation    # 1.0%

                # NOUVEAU: Stocker impacts vides pour 2025
                measure_impacts_by_year.append({'Année': year})
            else:
                # Variables d'état
                unemployment_gap = unemployment - self.base_params['chomage_nairu']
                debt_ratio = debt / gdp_nominal

                self.update_demography(year)

                _log_debug(self.debug_logs, f"Y{year_idx}: Output gap = {output_gap:.3f}")

                # Calcul recettes/dépenses base
                revenues_base = self.calculate_revenues(
                    gdp_nominal,
                    self.croissance_precedente,
                    self.inflation_precedente,
                    year_idx
                )

                # IMPORTANT: Passer output_gap pour cyclicité
                spending_base = self.calculate_expenditures(
                    gdp_nominal,
                    self.inflation_precedente,
                    unemployment,
                    year_idx,
                    output_gap  # AJOUT pour cyclicité
                )

                _log_debug(self.debug_logs, f"Y{year_idx}: Base: rec={revenues_base:.1f}, dep={spending_base:.1f}")

                # Application des mesures
                spending_after, revenues_after, impacts = self.apply_measures(
                    year, spending_base, revenues_base, gdp_nominal,
                    self.inflation_precedente, unemployment
                )

                self._last_impacts = impacts

                # NOUVEAU: Stocker les impacts de cette année pour le frontend
                year_impacts = {'Année': year}
                for measure_id, measure_data in impacts.items():
                    if isinstance(measure_data, dict):
                        year_impacts[measure_id] = measure_data.copy()
                measure_impacts_by_year.append(year_impacts)

                # Effort budgétaire
                delta_spending = spending_after - spending_base

                # NOTE: Ajustement baseline dépenses DÉSACTIVÉ.
                # Les handlers retournent le delta TOTAL cumulé, pas marginal.
                # L'appliquer à la baseline créait un double-comptage (delta via handler
                # + baseline réduite). Nécessite un tracking per-handler des deltas
                # marginaux pour être implémenté correctement.

                delta_revenue = revenues_after - revenues_base

                # NOTE: Revenue compounding DÉSACTIVÉ (même bug que Fix 2).
                # Les handlers retournent le delta TOTAL chaque année, pas marginal.
                # Ajouter le delta total à recettes_precedentes créait un double-comptage :
                # TVA +7 Md€ compoundait à +77 Md€ en 10 ans au lieu de ~8 Md€.
                # recettes_precedentes reste la base organique (avant mesures).

                fiscal_impulse = delta_revenue - delta_spending
                budget_effort = fiscal_impulse / gdp_nominal

                total_measures = abs(delta_spending) + abs(delta_revenue)
                part_spending = abs(delta_spending) / total_measures if total_measures > 0 else 0
                part_revenue = 1 - part_spending

                # Seules les dépenses d'investissement PRODUCTIF comptent pour le multiplicateur élevé.
                # Utilise le frozenset de classe INVESTMENT_FLOW_MEASURES (centralisé)
                part_investment = sum(
                    abs(impacts.get(m, {}).get('depenses', 0))
                    for m in self.INVESTMENT_FLOW_MEASURES
                ) / total_measures if total_measures > 0 else 0

                _log_debug(self.debug_logs, f"Y{year_idx}: Effort budgétaire = {budget_effort:.3f}")
                _log_debug(self.debug_logs, f"Composition: rec={part_revenue:.2f}, dep={part_spending:.2f}, inv={part_investment:.2f}")

                # Calcul croissance
                economic_state_growth = {
                    'output_gap': output_gap,
                    'unemployment_gap': unemployment_gap,
                    'effort_budgetaire': budget_effort,
                    'part_depenses': part_spending,
                    'part_investissement': part_investment,
                    'debt_ratio': debt_ratio,
                    'interest_rate': self.base_params['taux_interet_base'],
                    'unemployment': unemployment,
                    'deficit_ratio': deficit / gdp_nominal if year_idx > 0 else -0.054
                }

                growth = self.calculate_growth(year_idx, economic_state_growth)
                _log_debug(self.debug_logs, f"Y{year_idx}: Croissance = {growth:.3f}")

                # Calcul inflation
                economic_state_inflation = {
                    'output_gap': output_gap,
                    'unemployment_gap': unemployment_gap,
                    'effort_budgetaire': budget_effort,
                    'tva_impact': impacts.get('tva_rate', {}).get('recettes', 0) / gdp_nominal if year_idx == 1 else 0
                }

                inflation = self.calculate_inflation(year_idx, economic_state_inflation)
                _log_debug(self.debug_logs, f"Y{year_idx}: Inflation = {inflation:.3f}")

                # [SUPPRIMÉ Phase 2 — 2026-05-16, option B] Un ajustement
                # d'élasticité recettes sur la VARIATION d'inflation se
                # trouvait ici (`revenues_after *= 1 + (inflation -
                # inflation_precedente) * 0.5`). NE PAS réactiver : (1) mort
                # par construction — calculate_inflation réécrit
                # self.inflation_precedente avant ce point (0/10 ans) ;
                # (2) double-comptage — calculate_revenues (engine/revenues.py)
                # modélise déjà inflation→recettes via l'élasticité au PIB
                # nominal. Réactivation = biais optimiste systématique de la
                # dette. Chiffrage + décision : docs/REFACTOR_SPLIT_PLAN.md
                # (item Phase 2 résolu).

                # Mise à jour PIB
                gdp_real *= (1 + growth)
                self.deflateur_cumule *= (1 + inflation)
                gdp_nominal = gdp_real * self.deflateur_cumule

                _log_debug(self.debug_logs, f"Y{year_idx}: PIB nominal = {gdp_nominal:.1f}")

                revenues = revenues_after
                spending = spending_after

                # Taux d'intérêt et déficit
                marginal_rate = self.calculate_interest_rate(debt_ratio, year_idx, budget_effort)
                interests, interest_rate = self.calculate_interest_payment(debt, marginal_rate)
                deficit = revenues - spending - interests

                # Chômage (avec impacts directs mesures)
                unemployment = self.calculate_unemployment(growth, unemployment, year_idx, impacts)

                # Dette
                nominal_growth = growth + inflation

                # Calcul principal - équation comptable
                debt = debt - deficit  # Déficit négatif = augmentation de dette

                # Analyse Domar complémentaire (pour logs uniquement)
                if year_idx > 0:
                    debt_ratio = debt / gdp_nominal  # RECALCULER avec la nouvelle dette
                    r_minus_g = interest_rate - nominal_growth

                    # Vérification de cohérence
                    expected_debt_change = -deficit
                    actual_debt_change = debt - self.dette_courante

                    if abs(actual_debt_change - expected_debt_change) > 1:
                        _log_debug(self.debug_logs,
                            f"Y{year_idx}: ⚠️ Incohérence dette: "
                            f"Δ={actual_debt_change:.1f} vs déficit={-deficit:.1f}"
                        )

                    # Alerte soutenabilité
                    if r_minus_g > 0.01 and revenues - spending < 0:
                        _log_debug(self.debug_logs,
                            f"Y{year_idx}: 🚨 Dynamique explosive (r-g={r_minus_g*100:.2f}%)"
                        )

                # MISE À JOUR OUTPUT GAP - CRITIQUE !
                output_gap = 0.8 * output_gap + 0.2 * (growth - self.base_params['croissance_potentielle'])
                _log_debug(self.debug_logs, f"Y{year_idx}: Nouveau output gap = {output_gap:.3f}")

                # Mise à jour croissance potentielle
                self.update_potential_growth(growth, year_idx)

                # Multiplicateur pour logs — réutiliser la valeur stockée dans _fiscal_impulses
                # (le weighted blend a déjà été calculé dans calculate_growth)
                # Chercher l'impulse la plus récente (pas juste year_idx,
                # car l'impulse n'est stockée que l'année où les mesures changent)
                if year_idx in self._fiscal_impulses:
                    multiplier = self._fiscal_impulses[year_idx][1]
                elif self._fiscal_impulses:
                    latest_year = max(self._fiscal_impulses.keys())
                    multiplier = self._fiscal_impulses[latest_year][1]
                else:
                    multiplier = 1.0

                # Stockage pour année suivante
                self.croissance_precedente = growth
                self.inflation_precedente = inflation
                self.dette_courante = debt
                self.pib_nominal = gdp_nominal
                self.pib_reel_base2025 = gdp_real
                self.output_gap_courant = output_gap  # IMPORTANT

            # Calcul Gini centralisé
            # CORRECTION V4.6 : Application CHAQUE année pour capturer phasing/temporalité
            # Évite double-comptage car impacts sont calculés en DELTA, pas en cumulatif
            gini_impact = 0
            if year_idx > 0:  # Pas d'impact pour année base (2025)
                gini_impact = self.calculate_gini_impact(impacts, gdp_nominal)
                if gini_impact != 0:
                    _log_debug(self.debug_logs, f"Y{year_idx}: Impact Gini annuel = {gini_impact:.6f}")
                self.gini_courant += gini_impact
                self.gini_courant = np.clip(self.gini_courant, 0.25, 0.40)

            # Pouvoir d'achat (macro + micro) - Mise à jour INCRÉMENTALE
            # Sources : INSEE, OFCE 2024 - PA = f(Croissance, Inflation, Mesures fiscales/sociales)
            if year_idx > 0:  # Pas de mise à jour pour l'année de base (2025)
                # Effet macro brut : Croissance - Inflation (PIB/tête réel)
                pa_macro = growth - inflation

                # Protection indexation française (cf. constante INDEXATION_BASELINE_RATIO).
                indexation_baseline = INDEXATION_BASELINE_RATIO * inflation

                # Effet macro net (après protection sociale)
                pa_macro_net = pa_macro + indexation_baseline

                # Effet micro : Impacts directs des mesures fiscales/sociales permanentes.
                # Les mesures permanentes (TVA, IR, CSG...) affectent le PA chaque année,
                # pas seulement en année 1. L'ancien gate `year_idx == 1` bloquait
                # l'effet PA des réformes après la première année, ce qui sous-estimait
                # l'impact cumulé sur le pouvoir d'achat des ménages.
                # Atténuation : effet réduit de 50% après année 1 (adaptation comportementale).
                pa_micro = 0
                if len(measure_impacts_by_year) > 0:
                    year_measures = measure_impacts_by_year[-1]
                    for measure_id, measure_data in year_measures.items():
                        if measure_id != 'Année' and isinstance(measure_data, dict) and 'pouvoir_achat' in measure_data:
                            pa_micro += measure_data['pouvoir_achat']
                            if abs(measure_data['pouvoir_achat']) > 0.001:
                                _log_debug(self.debug_logs,
                                    f"Y{year}: PA micro {measure_id} = {measure_data['pouvoir_achat']:+.4f}")
                    # Atténuer l'effet cumulé après année 1 : adaptation comportementale
                    # et transmission partielle des effets fiscaux sur les prix
                    if year_idx > 1:
                        pa_micro *= 0.5

                # PA total = Macro net (après indexation baseline) + Micro (mesures)
                purchasing_power *= (1 + pa_macro_net + pa_micro)

                if abs(pa_micro) > 0.001:
                    _log_debug(self.debug_logs,
                        f"Y{year}: PA = {purchasing_power:.1f} (macro {pa_macro:+.2%}, micro {pa_micro:+.2%})")

            # Compétitivité des entreprises - Mise à jour MULTIPLICATIVE (comme PA)
            # Sources : OCDE 2024, Banque de France, DG Trésor
            # IMPORTANT : Appliqué CHAQUE ANNÉE pour cumuler impacts RÉCURRENT (éducation, transition)
            # Les impacts ONE-TIME sont automatiquement filtrés par _is_first_year_change()
            competitivite_delta = self.calculate_competitivite(impacts, gdp_nominal, year)
            if abs(competitivite_delta) > 0.0001:
                # Conversion points d'indice → pourcentage : 0.795 pts = 0.795% = 0.00795
                competitivite_index *= (1 + competitivite_delta / 100)  # Application multiplicative

                if abs(competitivite_delta) > 0.001:
                    _log_debug(self.debug_logs,
                        f"Y{year}: Compétitivité = {competitivite_index:.2f} (delta {competitivite_delta:+.3f} pts = {competitivite_delta/100:+.2%})")

            # Validation
            year_data = {
                'Recettes/PIB %': revenues / gdp_nominal * 100,
                'Dépenses/PIB %': spending / gdp_nominal * 100,
                'Dette/PIB %': debt / gdp_nominal * 100,
                'Gini': self.gini_courant,
                'Inflation %': inflation * 100,
                'Output_Gap %': output_gap * 100,
                'Taux_Intérêt %': interest_rate * 100
            }

            violations = self.validator.validate_year(year_data)
            if violations:
                validation_log.append(f"An {year}: {', '.join(violations)}")

            # Résultats
            results_list.append({
                'Année': year,
                'PIB': round(gdp_nominal, 1),
                'Croissance %': round(growth * 100, 2),
                'Inflation %': round(inflation * 100, 2),
                'Déficit': round(deficit, 1),
                'Déficit/PIB %': round(deficit / gdp_nominal * 100, 2),
                'Dette': round(debt, 1),
                'Dette/PIB %': round(debt / gdp_nominal * 100, 2),
                'Chômage %': round(unemployment * 100, 2),
                'Gini': round(self.gini_courant, 3),
                'Pouvoir d\'Achat': round(purchasing_power, 1),
                'Competitivite': round(competitivite_index, 2),
                'Recettes/PIB %': round(revenues / gdp_nominal * 100, 1),
                'Dépenses/PIB %': round((spending + interests) / gdp_nominal * 100, 1),  # AVEC intérêts
            })

            results_detailed.append({
                'Année': year,
                'Recettes_Totales': round(revenues, 1),
                'Dépenses_Totales': round(spending, 1),
                'Intérêts_Dette': round(interests, 1),
                'Dépenses_Totales_Avec_Intérêts': round(spending + interests, 1),
                'Taux_Intérêt %': round(interest_rate * 100, 2),
                'Effort_Budgétaire %': round(budget_effort * 100, 2) if year_idx > 0 else 0,
                'Multiplicateur': round(multiplier, 2),
                'PIB_Réel_Base2025': round(gdp_real, 1),
                'Déflateur': round(self.deflateur_cumule, 3),
                'Output_Gap %': round(output_gap * 100, 2),
                'Croissance_Potentielle %': round(self.base_params['croissance_potentielle'] * 100, 2),
                'Bonus_Potentiel_Supply %': round(self._potential_growth_bonus * 100, 3),
                'Croissance_Potentielle_Totale %': round((self.base_params['croissance_potentielle'] + self._potential_growth_bonus) * 100, 2),
            })

        # Validation finale
        results_df = pd.DataFrame(results_list)
        trajectory_report = self.validator.validate_trajectory(results_df)

        if validation_log:
            _log_debug(self.debug_logs, "\n" + "="*50)
            _log_debug(self.debug_logs, "ALERTES VALIDATION")
            for alert in validation_log:
                _log_debug(self.debug_logs, f"⚠ {alert}")

        if trajectory_report['warnings']:
            _log_debug(self.debug_logs, "\n" + "="*50)
            _log_debug(self.debug_logs, "AVERTISSEMENTS")
            for warning in trajectory_report['warnings']:
                _log_debug(self.debug_logs, f"⚠ {warning}")

        if trajectory_report['critical']:
            _log_debug(self.debug_logs, "\n" + "="*50)
            _log_debug(self.debug_logs, "ALERTES CRITIQUES")
            for critical in trajectory_report['critical']:
                _log_debug(self.debug_logs, f"🚨 {critical}")

        if trajectory_report['tests']:
            _log_debug(self.debug_logs, "\n" + "="*50)
            _log_debug(self.debug_logs, "TESTS ÉCONOMIQUES")
            for test in trajectory_report['tests']:
                _log_debug(self.debug_logs, f"📊 {test}")

        # NOUVEAU: Ajouter les impacts détaillés au rapport
        trajectory_report['measure_impacts_by_year'] = measure_impacts_by_year

        return results_df, pd.DataFrame(results_detailed), trajectory_report
