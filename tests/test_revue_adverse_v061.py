"""Clôture de la revue adverse v0.6.1 — la sémantique de l'item I3 propagée partout.

L'item I3 a changé la SIGNIFICATION de la valeur 62,75 : la référence d'âge
n'est plus un scalaire figé mais le calendrier légal (62,75 ans en 2026-2027,
puis +3 mois par génération jusqu'à 64,0 ans en 2032). Poser 62,75 sur tout
l'horizon ne décrit donc plus « je ne touche à rien » mais « je suspends la
réforme DÉFINITIVEMENT » — une mesure, facturée jusqu'à 6,78 Md€/an de pensions
à partir de 2032.

Le lot 3 a retiré cet encodage du seul scénario de référence `plf_2026`. La
revue adverse a montré que l'artefact survivait sur DEUX autres surfaces
publiées — le défaut du moteur (donc `/scenarios → status_quo`, donc le point
de départ du simulateur) et le programme de parti `renaissance_2027` — et que
le canal budgétaire gardait une horloge de montée en charge différente de celle
des canaux macro.

Ce fichier porte les gardes permanentes de cette clôture. Chaque test nomme la
surface qu'il protège : ce sont toutes des surfaces PUBLIÉES.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from budget_simulator._seniors import retraites_ecart_age_ans
from budget_simulator.config import load_default_values
from budget_simulator.constants import POLICY_START_YEAR
from budget_simulator.simulator import BudgetSimulatorV45

# Fenêtre de vérification : l'horizon publié (10 ans) plus une décennie, pour
# couvrir le plateau du calendrier légal (2032) et au-delà.
_MILLESIMES = tuple(range(POLICY_START_YEAR, POLICY_START_YEAR + 20))

# ---------------------------------------------------------------------------
# 1. Le défaut du moteur — « statu quo » de `/scenarios` et du simulateur
# ---------------------------------------------------------------------------


@pytest.mark.parametrize('year', _MILLESIMES)
def test_le_defaut_du_moteur_est_neutre_sur_tous_les_millesimes(year):
    """Le défaut livré doit avoir un écart RIGOUREUSEMENT nul chaque année.

    C'est la définition opératoire du statu quo depuis I3, et elle ne peut pas
    être satisfaite par un scalaire : la référence bouge de 62,75 à 64,0 entre
    2026 et 2032. Un défaut figé à 62,75 devient une mesure dès 2028 — mesurée
    à +3,65 pt de dette 2035 sur le tendanciel.
    """
    assert retraites_ecart_age_ans(load_default_values()['retraites'], year) == 0.0


def test_le_defaut_du_moteur_ne_change_pas_la_trajectoire():
    """Même invariant, vu du seul endroit qui compte : la trajectoire publiée.

    Simuler le bloc `retraites` par défaut doit rendre exactement la même dette
    que simuler ce bloc privé de tout âge — sinon le « statu quo » de l'API
    chiffre une réforme des retraites que personne n'a demandée.
    """
    defauts = load_default_values()['retraites']
    sans_age = {k: v for k, v in defauts.items() if k != 'age_depart'}
    avec = BudgetSimulatorV45(periods=10, mesures={'retraites': defauts}).simulate()[0]
    sans = BudgetSimulatorV45(periods=10, mesures={'retraites': sans_age}).simulate()[0]
    assert avec['Dette/PIB %'].iloc[-1] == pytest.approx(sans['Dette/PIB %'].iloc[-1], abs=1e-9)
