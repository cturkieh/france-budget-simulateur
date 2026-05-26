"""Bloc moteur — Impacts micro agrégés (Gini + compétitivité).

Méthodes couvertes :
- ``calculate_gini_impact`` : agrège la variation d'indice de Gini.
  Priorité à l'impact ``gini`` calculé directement par chaque handler ;
  fallback générique (règles par ``measure_id``) pour les mesures sans
  impact Gini explicite.
- ``calculate_competitivite`` : COLLECTE (ne calcule pas) les impacts
  ``competitivite`` produits par chaque handler ``_apply_*``.
  Méthodologie CUT OCDE / DG Trésor (cf METHODOLOGIE.md § Compétitivité).

Profil de couplage : **purement collectrices**. Lecture seule du dict
``impacts`` (sortie des handlers) et de ``gdp`` ; aucun état d'instance
écrit, aucun contrat producteur/consommateur (≠ ``InflationMixin`` /
``RevenuesMixin`` / ``DebtMixin`` / ``ExpendituresMixin``).

Filtre tolérant : les deux méthodes sautent tout ``impact`` non-dict.
``calculate_competitivite`` n'agrège que la clé ``'competitivite'``
(aucun fallback) ; ``calculate_gini_impact`` privilégie ``'gini'`` puis
applique un fallback générique par ``measure_id``. La re-analyse adverse
(2026-05-16) a RÉFUTÉ le « masquage silencieux » comme risque actuel :
``apply_measures`` garantit toujours un dict (un non-dict crashe
bruyamment en amont avec ``logger.error`` + ``HANDLER_FAILED_KEY``), et
aucun des 33 handlers n'émet ``'gini'``/``'competitivite'`` mal
orthographiée (grep exhaustif). Les clés custom (``description``,
``rabot_details``, ``emploi``…) sont ignorées À RAISON (métadonnées, cf
``_types.py``). Garde ``isinstance`` = défensif inerte aujourd'hui ;
risque résiduel purement PRÉVENTIF/FUTUR (typo lors d'un futur
renommage). Sévérité LOW — même lot reclassé que ``UnemploymentMixin``
(réponse proportionnée = test de contrat sur les 33 handlers, PAS
durcissement des collecteurs ; cf ``docs/REFACTOR_SPLIT_PLAN.md``).

Sink de logs : ``self.debug_logs`` via ``_log_debug``
(``calculate_competitivite`` uniquement).
Tous attributs d'instance de ``BudgetSimulatorV45``.
"""
from typing import Dict

from .._logging import _log_debug


class MicroImpactsMixin:
    """Bloc moteur — Impacts micro agrégés (Gini + compétitivité)."""

    def calculate_gini_impact(self, impacts: Dict, gdp: float) -> float:
        """
        Calcul de l'impact des mesures sur les inégalités

        CORRECTION V4.5 : Utilise directement les impacts 'gini' calculés par chaque fonction
        au lieu de recalculer avec des règles génériques (qui ignoraient les nouvelles mesures)
        """
        gini_change = 0

        for measure_id, impact in impacts.items():
            if not isinstance(impact, dict):
                continue

            # NOUVEAU : Prioriser l'impact Gini calculé directement par la fonction de mesure
            if 'gini' in impact:
                gini_change += impact['gini']
                continue

            # ANCIEN : Fallback pour les mesures sans impact Gini explicite
            spending_impact = impact.get('depenses', 0)
            revenue_impact = impact.get('recettes', 0)

            if measure_id in ['retraites', 'sante', 'chomage_alloc']:
                if spending_impact < 0:
                    if measure_id == 'retraites':
                        gini_change += 0.10 * abs(spending_impact / gdp)
                    elif measure_id == 'chomage_alloc':
                        gini_change += 0.15 * abs(spending_impact / gdp)
                    else:
                        gini_change += 0.08 * abs(spending_impact / gdp)

            elif measure_id in ['education', 'transition_ecologique']:
                if spending_impact > 0:
                    gini_change -= 0.04 * (spending_impact / gdp)

            if measure_id == 'impot_societes' and revenue_impact > 0:
                gini_change -= 0.03 * (revenue_impact / gdp)
            if measure_id == 'tva_rate' and revenue_impact > 0:
                gini_change += 0.05 * (revenue_impact / gdp)

            # ===== CORRECTION V4.5 : Mesures ASTEVAL fiscales redistributives =====
            # CSG : Désormais géré directement dans _apply_csg() avec paramètres taux + progressive

        return gini_change

    def calculate_competitivite(self, impacts: Dict, gdp: float, year: int) -> float:
        """Collecte les impacts compétitivité calculés dans chaque fonction _apply_*.

        Méthodologie basée sur Coût Unitaire Travail (OCDE) et indicateurs DG Trésor.
        Chaque mesure calcule son propre impact selon sa nature économique.
        Cette fonction ne fait que COLLECTER les impacts, pas les calculer.

        Sources: OCDE 2024 (CUT), DG Trésor 2021-2024, France Stratégie CNP.
        Voir METHODOLOGIE.md § Compétitivité."""

        competitivite_delta = 0
        impacts_details = []

        for measure_id, impact in impacts.items():
            if not isinstance(impact, dict):
                continue

            # Collecter l'impact compétitivité calculé directement par la mesure
            if 'competitivite' in impact:
                comp_value = impact['competitivite']
                if abs(comp_value) > 0.0001:  # Seuil pour log
                    impacts_details.append(f"{measure_id}={comp_value:+.3f}")
                competitivite_delta += comp_value

        if impacts_details:
            _log_debug(self.debug_logs, f"Y{year}: COMPETITIVITE TOTALE = {competitivite_delta:+.3f} ({', '.join(impacts_details)})")

        return competitivite_delta
