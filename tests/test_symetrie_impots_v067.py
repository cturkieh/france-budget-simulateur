"""Symétrie en signe des IMPÔTS, mesurée dans le moteur complet (v0.6.7 — réfuteur macro).

Jusqu'ici une BAISSE d'impôts valait 0,7 fois une hausse (« asymétrie hausse/baisse du
moteur conservée (0,35/0,50) », héritage sans source) : 1 point de PIB rendu aux
contribuables rapportait 0,45 point de PIB à 4 ans quand 1 point prélevé en coûtait
0,65 — pénalité de 0,2 point de PIB par point de PIB pour tout programme qui baisse
un impôt. Aucune source ne publie cette asymétrie dans ce sens (constants.py,
MULT_CIBLE_NIVEAU_4ANS) : la baisse est calée sur la même valeur centrale que la
hausse, Gechert (2015) classant par instrument, pas par signe.

Mesure : niveau du PIB réel 4 ans après le début d'une impulsion PERMANENTE de 1 % du
PIB (définition de calibration de tests/test_multiplicateurs_centraux_v067.py), pour
un levier fiscal ordinaire — tous les leviers de recettes partagent la composition
« recettes » ; seuls le SMIC et la fraude fiscale ont un coefficient propre.
"""
import logging

import pytest

from budget_simulator.simulator import BudgetSimulatorV45, FiscalMultipliers

logging.disable(logging.WARNING)

LEVIERS_FISCAUX = ('tva_rate', 'impot_revenu', 'impots_production')


def _niveaux(levier, signe, periods=12):
    """Écart de niveau du PIB réel (%) d'une impulsion de recettes de signe × 1 % du PIB,
    dès le budget 2026 (harnais du réfuteur, canal recettes)."""
    def run(x0):
        class _Impulsion(BudgetSimulatorV45):
            def apply_measures(self, year, sp, rv, gdp, inf, u):
                sp, rv, imp = super().apply_measures(year, sp, rv, gdp, inf, u)
                x = x0 * gdp if year - self.annee_base >= 1 else 0.0
                if x:
                    imp = dict(imp)
                    imp[levier] = {'depenses': 0.0, 'recettes': x}
                    rv += x
                return sp, rv, imp
        return _Impulsion(periods=periods, mesures={}).simulate()[1]['PIB_Réel_Base2025']
    y0, y1 = run(0.0), run(0.01 * signe)
    return [(a / b - 1) * 100 for a, b in zip(y1, y0)]


@pytest.fixture(scope='module')
def round_neutralise():
    import budget_simulator.engine.orchestrator as orch
    mp = pytest.MonkeyPatch()
    mp.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
    yield
    mp.undo()


@pytest.mark.parametrize('levier', LEVIERS_FISCAUX)
def test_baisse_et_hausse_d_impots_symetriques_a_4_ans(round_neutralise, levier):
    """Rendre 1 point de PIB d'impôts rapporte, à 4 ans, ce que le prélever coûte (±3 %).
    RED avant correctif : rapport baisse/hausse 0,687 (0,448 contre 0,652)."""
    assert not ({levier} & FiscalMultipliers.MESURES_MULTIPLICATEUR_NET)
    hausse, baisse = _niveaux(levier, +1), _niveaux(levier, -1)
    assert hausse[5] < 0 < baisse[5]
    rapport = abs(baisse[5]) / abs(hausse[5])
    assert rapport == pytest.approx(1.0, abs=0.03), (
        f'{levier} : baisse {baisse[5]:+.4f} % contre hausse {hausse[5]:+.4f} % à 4 ans '
        f'(rapport {rapport:.4f})')
