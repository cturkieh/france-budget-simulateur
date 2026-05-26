"""Bloc moteur — Chômage (loi d'Okun + ajustements structurels).

Méthode couverte :
- ``calculate_unemployment`` : taux de chômage de l'année à partir de
  la croissance (loi d'Okun macro), des impacts directs des mesures
  (canal micro : incitations emploi / activation / redistribution),
  d'une convergence NAIRU et d'ajustements structurels (hystérèse en
  récession, détente en surchauffe), clampé sur [4 %, 12 %].

Sources du canal micro : Lehmann et al. (2013), France Stratégie
(2019), Bargain (2017).

Profil de couplage : aucun état ÉCONOMIQUE d'instance écrit, aucun
contrat producteur/consommateur d'état économique (à la différence de
``InflationMixin``). Lecture seule de ``self.economic_coeffs['okun']``
et ``self.base_params`` (``croissance_potentielle``, ``chomage_nairu``).
Seul effet de bord : append conditionnel dans le sink de logs PARTAGÉ
``self.debug_logs`` via ``_log_debug`` — la méthode n'est donc pas pure
au sens strict, et ``self.debug_logs`` doit être initialisé par
``BudgetSimulatorV45`` avant appel.

L'agrégation des impacts chômage
(``isinstance(impact, dict) and 'chomage' in impact``) est tolérante
au type ET à la clé. La re-analyse adverse (2026-05-16) a RÉFUTÉ ce
vecteur comme risque actuel : ``apply_measures`` garantit toujours un
dict (un non-dict crashe bruyamment à l'affectation
``measure_impacts['depenses']`` AVANT d'atteindre ce collecteur, avec
``logger.error`` + ``HANDLER_FAILED_KEY``), et aucun des 33 handlers
n'émet la clé ``'chomage'`` mal orthographiée (grep exhaustif). Le
``isinstance`` est donc un garde défensif inerte aujourd'hui. Risque
résiduel purement PRÉVENTIF/FUTUR : un futur renommage/typo dans un
handler, non rattrapé par un test de contrat. Sévérité LOW — réponse
proportionnée = un test de contrat unique sur les 33 handlers (clés
numériques ⊂ ensemble canonique), PAS un durcissement de ce collecteur
(cf ``docs/REFACTOR_SPLIT_PLAN.md``, lot reclassé LOW préventif).
"""
from typing import Dict

import numpy as np

from .._logging import _log_debug


class UnemploymentMixin:
    """Bloc moteur — Chômage (loi d'Okun + ajustements structurels)."""

    def calculate_unemployment(self, growth: float, unemployment_prev: float, year: int, impacts: Dict = None) -> float:
        """Loi d'Okun avec ajustements structurels + impacts directs mesures"""

        # ===== LOI D'OKUN (effet croissance - MACRO) =====
        delta_unemployment = self.economic_coeffs['okun'] * (
            growth - self.base_params['croissance_potentielle']
        )

        unemployment = unemployment_prev + delta_unemployment

        # ===== IMPACTS DIRECTS DES MESURES (MICRO) =====
        # Intègre effets structurels: incitations emploi, activation, redistribution
        # Sources: Lehmann et al. (2013), France Stratégie (2019), Bargain (2017)
        if impacts:
            chomage_direct = 0
            for measure_id, impact in impacts.items():
                if isinstance(impact, dict) and 'chomage' in impact:
                    chomage_direct += impact['chomage']

            unemployment += chomage_direct

            if abs(chomage_direct) > 0.0001:
                _log_debug(self.debug_logs,
                    f"Y{year}: Impact direct chômage = {chomage_direct*100:+.3f} points"
                )

        # ===== CONVERGENCE NAIRU =====
        nairu = self.base_params['chomage_nairu']
        unemployment = 0.94 * unemployment + 0.06 * nairu

        # ===== AJUSTEMENTS STRUCTURELS =====
        if growth < -0.015:
            unemployment += 0.002
            _log_debug(self.debug_logs, f"Y{year}: Hystérèse chômage")
        elif growth > 0.020 and unemployment > nairu:
            unemployment -= 0.001

        unemployment = np.clip(unemployment, 0.04, 0.12)

        return unemployment
