"""Désindexation : ratio EXACT de revalorisation (v0.6.10, contre-audit externe V2-03).

Constat (contre-audit du 07/10/2026 sur v0.6.7, reproduit à l'identique sur v0.6.9) :
``_ecart_revalorisations`` composait ``Π (1 − δ × π)`` et appliquait l'écart à la
masse nominale de l'année, qui est la masse APRÈS revalorisation complète
(``masse_categorie_nominale`` porte l'indice de prix cumulé des dépenses). Le
rapport exact entre une masse revalorisée de ``(1 − δ) × π`` et la même masse
revalorisée de ``π`` est ``(1 + (1 − δ)π) / (1 + π) = 1 − δπ / (1 + π)`` : la
formule v0.6.7 omettait le dénominateur ``1 + π``, une approximation au premier
ordre qui surestimait toute économie (et tout surcoût) de désindexation.

Exemple du contre-audit : une masse de 100 revalorisée de 2 % devient 102 ; un gel
total économise exactement 2, la formule v0.6.7 en rendait 2,04. Après dix
revalorisations à 2 % : écart exact 17,965170 %, formule v0.6.7 18,292719 %.
Dette 2035 des gels totaux, seul le facteur remplacé : pensions 148,02 → 148,06 %,
prestations 150,20 → 150,21 %.
"""
import pytest

from budget_simulator.constants import POLICY_START_YEAR
from budget_simulator.simulator import BudgetSimulatorV45

_PI = 0.02
_N_MAX = 10   # plafond de revalorisations des prestations ; ici seul compte qu'il ne morde pas


def _ecart_hors_simulation(delta: float, n_revalorisations: int, pi: float = _PI) -> float:
    """Écart du helper du moteur après ``n_revalorisations`` à inflation constante ``pi``.

    Hors simulation, ``_inflation_par_annee`` est vide : chaque revalorisation après
    la première porte l'inflation de l'appel, et la première ``taux_2026`` — ici la
    même ``pi``, pour une inflation rigoureusement constante.
    """
    sim = BudgetSimulatorV45(mesures={})
    return sim._ecart_revalorisations(delta, POLICY_START_YEAR + n_revalorisations - 1,
                                      pi, _N_MAX, pi)


# ---------------------------------------------------------------------------
# RED — chiffres exacts du contre-audit (V2-03)
# ---------------------------------------------------------------------------

def test_v2_03_gel_total_masse_100_revalorisee_a_102_economise_exactement_2():
    """RED v0.6.9 : 102 × 2 % = 2,04. Une masse de 100 revalorisée de 2 % vaut 102 ;
    gelée, elle reste à 100 : l'économie est exactement 2."""
    masse_revalorisee = 100.0 * (1 + _PI)
    economie = masse_revalorisee * _ecart_hors_simulation(1.0, 1)
    assert economie == pytest.approx(2.0, abs=1e-12)


def test_v2_03_dix_revalorisations_a_2_pourcent_ecart_exact():
    """RED v0.6.9 : 18,292719 % (1 − 0,98¹⁰). Exact : 1 − 1,02⁻¹⁰ = 17,965170 %."""
    assert _ecart_hors_simulation(1.0, 10) * 100 == pytest.approx(17.965170, abs=5e-7)


@pytest.mark.parametrize('mesures, dette_2035', [
    pytest.param({'retraites': {'indexation': 0.0}}, 148.06, id='gel_pensions'),
    pytest.param({'prestations_indexation': {'taux_indexation': 0.0}}, 150.21,
                 id='gel_prestations'),
])
def test_v2_03_dette_2035_des_gels_totaux(mesures, dette_2035):
    """RED v0.6.9 : 148,02 (pensions) et 150,20 (prestations). Contre-calcul du
    contre-audit, seul le facteur remplacé par le ratio exact, toutes les autres
    règles conservées (part indexée comprise) : 148,06 et 150,21, au centième.
    Chiffres de la trajectoire v0.6.9 : un lot d'équation ultérieur qui déplace la
    dette du statu quo re-déclare ces deux valeurs en acte."""
    df, _, _ = BudgetSimulatorV45(periods=10, mesures=mesures).simulate()
    dette = df.loc[df['Année'] == 2035, 'Dette/PIB %'].iloc[0]
    assert dette == pytest.approx(dette_2035, abs=0.005)
