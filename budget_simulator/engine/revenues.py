"""Bloc moteur — Recettes publiques (élasticité unitaire + plafond de Laffer).

Refonte « assemblage temporel » (2026-06) — remplace l'ancienne élasticité
différenciée par régime de croissance (1,00/1,06/1,08/1,12), l'érosion
fiscale forfaitaire (EROSION_RECETTES = 0,2 %/an, qui rendait l'élasticité
de facto ~0,93) et les deux rustines de transition 2026 (plancher 1,06 +
érosion nulle, « dynamisme post-COVID » jamais ré-examiné depuis oct. 2025)
par la convention institutionnelle :

    Recettes_t = Recettes_{t-1} × (1 + n_t × ELASTICITE_PO_PIB)

avec ``n_t`` = croissance NOMINALE CONTEMPORAINE du PIB ((1+g)(1+π)−1,
exactement la croissance du dénominateur) et ``ELASTICITE_PO_PIB`` = 1,0
(HCFP note 2023-01 : élasticité observée 1,01-1,07, non significativement
différente de 1 ; CBO/OBR/Trésor ne modélisent JAMAIS une érosion globale —
les érosions réelles sont par taxe, à porter en mesures si souhaité).

En statu quo, le ratio recettes/PIB est ainsi STABLE par construction
(c'est la définition d'un scénario à politique inchangée) ; il ne bouge
que sous les zones de Laffer (garde-fous hors statu quo) et les mesures.

État partagé ``self.recettes_precedentes`` — invariant non évident à
NE PAS « corriger » sans relire ``simulate()`` :
- Lu en entrée (base de croissance organique) puis réécrit en fin de
  méthode. SEUL producteur de cet état dans la boucle en régime établi.
- Reste **volontairement la base ORGANIQUE, AVANT mesures**. ``simulate()``
  n'y réinjecte délibérément PAS le delta des mesures : le faire
  recréerait un double-comptage par compounding (une mesure TVA à +7 Md€
  dériverait à ~+77 Md€ sur 10 ans au lieu de rester ~+8 Md€). Cf la NOTE
  « Revenue compounding DÉSACTIVÉ » dans ``simulate()``.
- Init / reset relèvent de l'hôte (année 0 = ``recettes_base`` INSEE).

Sink de logs : ``self.debug_logs`` via ``_log_debug``.
Tous attributs d'instance de ``BudgetSimulatorV45``.
"""
from .._logging import _log_debug
from ..constants import ELASTICITE_PO_PIB


class RevenuesMixin:
    """Bloc moteur — Recettes publiques (élasticité unitaire + plafond de Laffer)."""

    def calculate_revenues(self, gdp: float, growth: float, inflation: float, year: int) -> float:
        """Recettes organiques de l'année (croissance nominale contemporaine, élasticité 1).

        ``growth`` / ``inflation`` = valeurs CONTEMPORAINES de l'année simulée
        (l'orchestrateur les calcule désormais AVANT les flux).
        """
        # Croissance nominale exacte du PIB (composée, pas additive : cohérente
        # avec gdp_nominal = gdp_real × deflateur du dénominateur)
        nominal_growth = (1 + growth) * (1 + inflation) - 1

        revenues = self.recettes_precedentes * (1 + nominal_growth * ELASTICITE_PO_PIB)

        # Plafond de Laffer (garde-fous, inchangés — inertes en statu quo ~52 %)
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
