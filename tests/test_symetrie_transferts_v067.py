"""Symétrie par instrument des TRANSFERTS (v0.6.7, lot 3b — réfuteur macro).

Gechert (2015, Oxford Economic Papers 67(3)) classe les multiplicateurs par
INSTRUMENT, pas par signe : couper 1 € de pensions coûte ce que l'ajout en
rapporte. Jusqu'ici, une consolidation d'un levier de ``TRANSFER_MEASURES``
prenait le coefficient de la COUPE GÉNÉRIQUE (MULT_COUPE_DEPENSES, atténué ÷1,10
« confiance » AFG 2019) quand sa hausse prenait MULT_TRANSFERTS : couper 1 % du PIB
de pensions coûtait 0,707 point de PIB à 4 ans, la hausse en rapportait 0,653
(+8,2 %). Désormais même coefficient dans les deux sens (l'atténuation
« confiance » de la coupe générique est elle-même retirée depuis, v0.6.7).

Asymétrie RÉSIDUELLE, mesurée et déclarée jusqu'à v0.8.1 : en moteur complet le
rapport valait 1,044 — c'était l'ÉVICTION (« crowding-out »), qui pénalisait les
seules expansions financées par la dette au-delà de 100 % du PIB sans
« crowding-in » symétrique pour les consolidations. Éviction neutralisée : 1,009.

Lot 1 (15/11/2026) : l'éviction est RETIRÉE (tests/test_eviction_retiree.py). Les
deux tests qui isolaient puis bornaient cette asymétrie (« éviction isolée » à ±3 %,
« asymétrie résiduelle = l'éviction déclarée » dans ]1 ; 1,06[) sont re-déclarés en
un seul, plus strict : moteur complet, rapport à 1 % près.
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


def test_la_coupe_coute_ce_que_la_hausse_rapporte():
    """Moteur complet, dette au-delà de 100 % du PIB : couper 1 % du PIB de pensions
    coûte ce que l'ajouter rapporte, à 1 % près (v0.8.1 : 1,044, l'éviction)."""
    hausse, coupe = _niveau_h4(+1), _niveau_h4(-1)
    assert hausse > 0 > coupe
    assert abs(abs(coupe) / abs(hausse) - 1) < 0.01, (hausse, coupe)
