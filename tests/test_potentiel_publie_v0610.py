"""Colonnes de croissance potentielle = potentiel CONSOMMÉ par l'année (v0.6.10,
contre-audit externe du 07/10/2026, réserve V2-02).

Constat : dans la boucle annuelle, l'output gap est mis à jour avec le potentiel
de l'année, PUIS ``update_potential_growth`` clôt l'année (hystérèse du
tendanciel, bonus d'offre structurel préparés pour t+1), PUIS la ligne de sortie
relisait l'état. La colonne ``Croissance_Potentielle_Totale %`` publiait donc le
potentiel de l'année SUIVANTE : l'identité de l'output gap n'était pas
reconstructible depuis les sorties (81 scénarios sur 280 au contre-audit).

Cas du contre-audit, ``{"recherche_publique": {"budget": 20}}``, 2030, valeurs
non arrondies : croissance 1,093783 % ; potentiel consommé 1,048206 % ; colonne
publiée 1,248206 % ; output gap 0,200243 %. Le bonus recherche naît à la
5ᵉ année active (fin 2030) : il ne compte qu'à partir de 2031.

Instrumentation (sans modifier le moteur) : ``round`` neutralisé dans
l'orchestrateur, comme au contre-audit, et sous-classe qui photographie
``croissance_potentielle_totale()`` à l'ENTRÉE de ``update_potential_growth``,
c'est-à-dire la valeur que croissance, Okun et output gap viennent de lire.
"""
from unittest.mock import patch

import pytest

from budget_simulator.engine import orchestrator as orchestrator_module
from budget_simulator.simulator import BudgetSimulatorV45

CAS_AUDIT = {'recherche_publique': {'budget': 20}}
ANNEE_AUDIT = 2030


class _SimulateurInstrumente(BudgetSimulatorV45):
    """Photographie le potentiel consommé, juste avant la clôture de l'année."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.potentiel_consomme = {}

    def update_potential_growth(self, growth, year):
        self.potentiel_consomme[self.annee_base + year] = {
            'total': self.croissance_potentielle_totale(),
            'tendanciel': self.base_params['croissance_potentielle'],
            'offre_structurelle': self._potential_growth_bonus,
            'offre_travail': self._labour_supply_bonus,
        }
        super().update_potential_growth(growth, year)


def _simuler_brut(mesures):
    """Simulation 10 ans, colonnes NON arrondies, plus le potentiel consommé."""
    sim = _SimulateurInstrumente(periods=10, mesures=mesures)
    with patch.object(orchestrator_module, 'round', lambda x, n=None: float(x), create=True):
        df, detail, _ = sim.simulate()
    return df.set_index('Année'), detail.set_index('Année'), sim.potentiel_consomme


def test_v2_02_colonne_potentiel_total_2030_est_le_potentiel_consomme():
    """Rouge sur v0.6.9 : colonne 1,248206 % contre 1,048206 % consommé."""
    df, detail, consomme = _simuler_brut(CAS_AUDIT)

    # Les chiffres du contre-audit se reproduisent (6 décimales publiées).
    assert df.loc[ANNEE_AUDIT, 'Croissance %'] == pytest.approx(1.093783, abs=5e-7)
    assert detail.loc[ANNEE_AUDIT, 'Output_Gap %'] == pytest.approx(0.200243, abs=5e-7)
    assert consomme[ANNEE_AUDIT]['total'] * 100 == pytest.approx(1.048206, abs=5e-7)

    # La colonne publiée est le potentiel consommé, pas celui préparé pour 2031.
    assert detail.loc[ANNEE_AUDIT, 'Croissance_Potentielle_Totale %'] == pytest.approx(
        consomme[ANNEE_AUDIT]['total'] * 100, abs=1e-12)
