"""Symétrie par instrument des TRANSFERTS (v0.6.7, lot 3b — réfuteur macro).

Gechert (2015, Oxford Economic Papers 67(3)) classe les multiplicateurs par
INSTRUMENT, pas par signe : couper 1 € de pensions coûte ce que l'ajout en
rapporte. Jusqu'ici, une consolidation d'un levier de ``TRANSFER_MEASURES``
prenait le coefficient de la COUPE GÉNÉRIQUE (MULT_COUPE_DEPENSES, atténué ÷1,10
« confiance » AFG 2019) quand sa hausse prenait MULT_TRANSFERTS : couper 1 % du PIB
de pensions coûtait 0,707 point de PIB à 4 ans, la hausse en rapportait 0,653
(+8,2 %). Désormais même coefficient dans les deux sens (l'atténuation
« confiance » de la coupe générique est elle-même retirée depuis, v0.6.7).

Asymétrie RÉSIDUELLE, mesurée et déclarée (hors périmètre) : en moteur complet le
rapport vaut 1,044 — c'est l'ÉVICTION (engine/growth.py, « crowding-out »), qui
pénalise les seules expansions financées par la dette au-delà de 100 % du PIB sans
« crowding-in » symétrique pour les consolidations. Éviction neutralisée : 1,009.
"""
import pytest

from budget_simulator.simulator import BudgetSimulatorV45, FiscalMultipliers

COMPO_TRANSFERT = {'depenses': 1.0, 'recettes': 0.0, 'investissement': 0.0, 'transferts': 1.0}
ETAT_NEUTRE = {'output_gap': 0.0, 'unemployment_gap': 0.0, 'debt_ratio': 1.15, 'interest_rate': 0.023}


@pytest.mark.parametrize('levier', sorted(BudgetSimulatorV45.TRANSFER_MEASURES - {'smic'}))
def test_coefficient_identique_dans_les_deux_sens(levier):
    """À l'an 3 (année quelconque : plus aucun coefficient ne dépend de l'année)."""
    fm = FiscalMultipliers()
    hausse = fm.get_multiplier('expansion', COMPO_TRANSFERT, ETAT_NEUTRE, 3, levier)
    coupe = FiscalMultipliers().get_multiplier('consolidation', COMPO_TRANSFERT, ETAT_NEUTRE, 3, levier)
    assert coupe == pytest.approx(-hausse, abs=1e-12)


def _niveau_h4(signe):
    """Niveau du PIB réel (%) 4 ans après le début d'une impulsion PERMANENTE de
    ±1 % du PIB sur les pensions (forme du test RED du réfuteur)."""
    def run(x0):
        class S(BudgetSimulatorV45):
            def apply_measures(self, year, sp, rv, gdp, inf, u):
                sp, rv, imp = super().apply_measures(year, sp, rv, gdp, inf, u)
                if year - self.annee_base >= 1 and x0:
                    x = x0 * gdp
                    imp = dict(imp)
                    imp['retraites'] = {'depenses': x, 'recettes': 0.0}
                    sp += x
                return sp, rv, imp
        return S(periods=10, mesures={}).simulate()[1]['PIB_Réel_Base2025']
    y0, y1 = run(0.0), run(0.01 * signe)
    return (y1[5] / y0[5] - 1) * 100


def test_la_coupe_coute_ce_que_la_hausse_rapporte_eviction_isolee(monkeypatch):
    origine = BudgetSimulatorV45.calculate_growth

    def sans_eviction(self, year, etat):
        # L'éviction ne lit qu'un effort NÉGATIF (expansion) : le borner à 0 la
        # neutralise sans toucher au reste de calculate_growth.
        return origine(self, year, {**etat, 'effort_budgetaire': max(etat['effort_budgetaire'], 0.0)})

    monkeypatch.setattr(BudgetSimulatorV45, 'calculate_growth', sans_eviction)
    hausse, coupe = _niveau_h4(+1), _niveau_h4(-1)
    assert abs(abs(coupe) / abs(hausse) - 1) < 0.03, (hausse, coupe)


def test_asymetrie_residuelle_est_l_eviction_declaree():
    """Moteur complet : l'écart restant est celui de l'éviction (mesuré 1,044) —
    borné pour qu'une NOUVELLE asymétrie de signe ne s'y cache pas."""
    hausse, coupe = _niveau_h4(+1), _niveau_h4(-1)
    assert 1.0 < abs(coupe) / abs(hausse) < 1.06, (hausse, coupe)
