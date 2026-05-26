"""Bloc moteur — Recettes publiques (élasticité + plafond de Laffer).

Méthode couverte :
- ``calculate_revenues`` : recettes organiques de l'année à partir de
  la base de l'année précédente, de la croissance nominale et d'une
  élasticité fiscale dépendant du régime de croissance, avec érosion
  fiscale et plafond de Laffer (zones 55 / 60 / 65 % du PIB).

État partagé ``self.recettes_precedentes`` — invariant non évident à
NE PAS « corriger » sans relire ``simulate()`` :
- Lu en entrée (base de croissance organique) puis réécrit en fin de
  méthode avec les recettes calculées. ``calculate_revenues`` est le
  SEUL producteur de cet état dans la boucle en régime établi :
  l'écriture finale porte réellement la persistance N→N+1 (contrairement
  à ``InflationMixin``, où c'est l'orchestrateur qui re-persiste).
- ``recettes_precedentes`` reste **volontairement la base ORGANIQUE,
  AVANT mesures**. ``simulate()`` n'y réinjecte délibérément PAS le
  delta des mesures : le faire recréerait un double-comptage par
  compounding (une mesure TVA à +7 Md€ dériverait à ~+77 Md€ sur 10 ans
  au lieu de rester ~+8 Md€). Cf la NOTE « Revenue compounding
  DÉSACTIVÉ » dans ``simulate()``. Un futur mainteneur qui « rebranche »
  le delta sur cet état réintroduit ce bug — d'où la nature load-bearing
  de l'invariant.
- Init / reset relèvent de l'hôte ``BudgetSimulatorV45``
  (``__init__`` / ``_reset_state`` / bloc bootstrap ``year_idx == 0``
  de ``simulate()`` = année 2025, amorçage ``recettes_base`` HORS de
  cette méthode), hors périmètre du split (non touché). Année 2026
  (``year_idx == 1``) passe en revanche bien par cette méthode, mais
  y suit une branche de TRANSITION dédiée (``if year == 1`` :
  élasticité plancher 1.06, érosion nulle) — ce n'est pas le chemin
  nominal.

Lecture seule : ``self.base_params['erosion_recettes']``.
Sink de logs : ``self.debug_logs`` via ``_log_debug``.
Tous attributs d'instance de ``BudgetSimulatorV45``.
"""
from .._logging import _log_debug


class RevenuesMixin:
    """Bloc moteur — Recettes publiques (élasticité + plafond de Laffer)."""

    def calculate_revenues(self, gdp: float, growth: float, inflation: float, year: int) -> float:
        """Calcul des recettes avec élasticité CORRIGÉE"""

        # Croissance nominale
        nominal_growth = growth + inflation

        # Élasticité de base selon croissance
        if growth > 0.02:
            elasticity_base = 1.08
        elif growth < -0.01:
            elasticity_base = 1.12
        elif growth < 0:
            elasticity_base = 1.06
        else:
            elasticity_base = 1.00

        # Ajustement transition 2026 - Élasticité renforcée
        if year == 1:
            # 2026: Élasticité minimale pour lisser la transition (dynamisme fiscal post-COVID)
            elasticity = max(elasticity_base, 1.06)
        else:
            elasticity = elasticity_base

        revenues = self.recettes_precedentes * (1 + nominal_growth * elasticity)

        # Érosion fiscale (niches, optimisation)
        # Transition 2026: Pas d'érosion (rattrapage fiscal post-COVID)
        if year == 1:
            erosion = 0.0
        else:
            erosion = self.base_params['erosion_recettes']
        revenues *= (1 - erosion)

        # Plafond de Laffer
        revenue_ratio = revenues / gdp

        if revenue_ratio > 0.65:
            revenues = gdp * 0.65
            _log_debug(self.debug_logs, f"Y{year}: PLAFOND Laffer 65% PIB")
        elif revenue_ratio > 0.60:
            excess = revenue_ratio - 0.60
            revenues *= (1 - 0.15 * excess)
            _log_debug(self.debug_logs, f"Y{year}: Zone Laffer critique")
        elif revenue_ratio > 0.55:
            excess = revenue_ratio - 0.55
            revenues *= (1 - 0.05 * excess)
            _log_debug(self.debug_logs, f"Y{year}: Rendements décroissants")

        # Mise à jour pour l'année suivante
        self.recettes_precedentes = revenues

        return revenues
