"""Le moteur est DÉTERMINISTE sans graine (v0.6.7, recalage du corridor).

Jusqu'en v0.6.6, la croissance recevait un tirage N(0 ; 0,3 %) et l'inflation
un tirage N(0 ; 0,05 %), graine 42 refixée à chaque ``simulate()`` : les mêmes
nombres pour tous les scénarios, donc aucune information. Avec l'output gap en
NIVEAU (v0.6.7, B3), le bruit de croissance devenait un choc de demande
persistant (+0,6 % de PIB en 2029) qui sortait à lui seul le scénario de
référence du corridor de la mission (dette 2029 −2,26 pt ; sans lui −0,39).
Une incertitude se publie en variante, pas en tirage caché dans la trajectoire
centrale.

Trois propriétés, pour que le hasard ne revienne pas par la bande :
1. le moteur n'accède JAMAIS au générateur aléatoire de numpy (tout accès lève),
   sur les 44 cas du golden master (statu quo, scénarios publiés, leviers seuls) ;
2. le résultat ne dépend pas de l'état global de ce générateur ;
3. ``simulate()`` ne touche plus à l'état du générateur de l'APPELANT (l'ancien
   ``np.random.seed(42)`` le réinitialisait à chaque simulation).
"""
import sys
from pathlib import Path

import numpy as np
import pytest

from budget_simulator.simulator import BudgetSimulatorV45

sys.path.insert(0, str(Path(__file__).parent / 'snapshots'))
from coverage_scenarios import build_standalone_scenarios  # noqa: E402
from run_scenarios_full import SCENARIOS  # noqa: E402


class _HasardInterdit:
    """Remplace ``numpy.random`` : tout accès, même en lecture, est une faute."""

    def __getattr__(self, nom):
        raise AssertionError(
            f"le moteur a accédé à numpy.random.{nom} : un tirage caché est "
            "revenu dans la trajectoire centrale")


def _cas():
    cas = {'statu_quo': {}}
    cas.update(SCENARIOS)  # vide sur un fork moteur seul : le statu quo reste
    cas.update({f'SA:{k}': v for k, v in build_standalone_scenarios().items()})
    return cas


@pytest.mark.parametrize('nom', sorted(_cas()))
def test_aucun_acces_au_generateur_aleatoire(nom, monkeypatch):
    mesures = _cas()[nom]
    monkeypatch.setattr(np, 'random', _HasardInterdit())
    df, _, _ = BudgetSimulatorV45(periods=10, mesures=mesures).simulate()
    assert len(df) == 11


def test_le_resultat_ne_depend_pas_de_l_etat_du_generateur():
    np.random.seed(0)
    a, a2, _ = BudgetSimulatorV45(periods=10).simulate()
    np.random.seed(12345)
    np.random.normal(size=1000)
    b, b2, _ = BudgetSimulatorV45(periods=10).simulate()
    assert a.equals(b) and a2.equals(b2)


def test_simulate_ne_reinitialise_pas_le_generateur_de_l_appelant():
    np.random.seed(7)
    attendu = np.random.random()
    np.random.seed(7)
    BudgetSimulatorV45(periods=10).simulate()
    assert np.random.random() == attendu
