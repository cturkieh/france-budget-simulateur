"""Multiplicateurs « centraux » mesurés dans le MOTEUR COMPLET (v0.6.7, arbitrage du
mainteneur du 07/10/2026).

Chaque famille est calée sur la valeur centrale de la littérature (constants.py,
MULT_CIBLE_NIVEAU_4ANS : FMI WEO oct. 2014 ch. 3, Gechert 2015, Ramey 2019), en
EFFET DE NIVEAU sur le PIB réel 4 ans après le début d'une impulsion permanente de
1 % du PIB — mesuré avec tout le moteur (rappel vers le potentiel, Phillips, Okun,
dette), pas en k × Σ profil analytique. Garde-fou : le choc d'investissement de
calibrage (1 % du PIB permanent, levier éducation, statu quo) ne s'autofinance pas
dans ce banc, ni en multiplicateur cumulé × taux de prélèvements, ni en solde
public mesuré. Portée : CE choc, pas tout investissement, toute intensité ou tout
état macroéconomique (contre-audit externe V2-06, METHODOLOGIE § Multiplicateurs).
"""
import pytest

from budget_simulator.constants import MULT_CIBLE_NIVEAU_4ANS, TAUX_PRELEVEMENTS_AUTOFINANCEMENT
from budget_simulator.simulator import BudgetSimulatorV45

# famille → (levier synthétique, flux, signe) : dépense + = expansion, recette + = hausse
FAMILLES = {
    'investissement': ('education', 'depenses', +1),
    'transferts': ('retraites', 'depenses', +1),
    'hausse_impots': ('tva_rate', 'recettes', +1),
    'baisse_impots': ('tva_rate', 'recettes', -1),
    'coupe_depenses': ('collectivites', 'depenses', -1),
}


def _simuler(famille=None, periods=12):
    levier, flux, signe = FAMILLES[famille] if famille else (None, None, 0)

    class _Impulsion(BudgetSimulatorV45):
        def apply_measures(self, year, spending, revenues, gdp, inflation, unemployment):
            sp, rv, imp = super().apply_measures(year, spending, revenues, gdp, inflation, unemployment)
            if levier:
                x = 0.01 * gdp * signe
                imp = dict(imp)
                imp[levier] = {'depenses': x if flux == 'depenses' else 0.0,
                               'recettes': x if flux == 'recettes' else 0.0}
                if flux == 'depenses':
                    sp += x
                else:
                    rv += x
            return sp, rv, imp

    return _Impulsion(periods=periods, mesures={}).simulate()


@pytest.fixture(scope='module')
def mesures(request):
    import budget_simulator.engine.orchestrator as orch
    mp = pytest.MonkeyPatch()
    mp.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
    try:
        base = _simuler()
        return base, {f: _simuler(f) for f in FAMILLES}
    finally:
        mp.undo()


def _niveaux(base, cas):
    yb, yr = base[1]['PIB_Réel_Base2025'], cas[1]['PIB_Réel_Base2025']
    # impulsion au budget 2026, effet dès 2027 (lag d'un an) : horizon H = index − 1
    return [abs(yr[i] - yb[i]) / yb[i] * 100 for i in range(len(yr))]


@pytest.mark.parametrize('famille', list(FAMILLES))
def test_niveau_a_4_ans_sur_la_valeur_centrale(mesures, famille):
    base, cas = mesures
    niveau_4 = _niveaux(base, cas[famille])[5]
    cible = MULT_CIBLE_NIVEAU_4ANS[famille]
    tolerance = 0.10 if famille == 'investissement' else 0.05   # investissement : non retouché (1,41 vs 1,5)
    assert niveau_4 == pytest.approx(cible, rel=tolerance), (
        f'{famille} : niveau à 4 ans {niveau_4:.3f} vs cible centrale {cible}')


def test_choc_investissement_de_calibrage_ne_s_autofinance_pas_dans_le_banc(mesures):
    """Portée : le choc de calibrage de ce fichier (1 % du PIB permanent sur le
    levier éducation, statu quo, 2026-2036), pas tout investissement.

    Trois notions distinctes (contre-audit externe V2-06) :
    - autofinancement BUDGÉTAIRE, deux mesures distinctes : (a) part du coût
      brut récupérée par le SOLDE public (intérêts compris), solde NET des
      recettes induites (+458 Md EUR, qui dépassent seules le coût de 395) et
      des dépenses induites hors impulsion (+405 : indexation, intérêts) —
      mesurée 0,13 (v0.6.10) ; (b) en volume, sans prix ni intérêts :
      multiplicateur cumulé (Ramey, ΣΔY/ΣΔG sur 10 ans) × taux de
      prélèvements = 0,47 < 1 ;
    - dette NOMINALE : plus haute que le statu quo en fin d'horizon ;
    - ratio dette/PIB : non vérifié année par année (un PIB plus haut peut le
      faire passer sous le statu quo sans rembourser le coût, −0,05 pt en
      2030-2031) ; seule sa valeur de fin d'horizon est bornée."""
    base, cas = mesures
    n = _niveaux(base, cas['investissement'])
    cumule_10 = sum(n[2:12]) / 10
    assert cumule_10 * TAUX_PRELEVEMENTS_AUTOFINANCEMENT < 1
    df0, df = base[0], cas['investissement'][0]
    cout = sum(0.01 * df['PIB'][i] for i in range(1, 12))
    degradation = sum(df0['Déficit'][i] - df['Déficit'][i] for i in range(1, 12))
    assert 1 - degradation / cout < 1
    assert degradation > 0.5 * cout   # l'essentiel du coût reste à la charge des finances publiques
    assert df['Dette'][11] > df0['Dette'][11]                   # dette nominale 2036
    assert df['Dette/PIB %'][11] > df0['Dette/PIB %'][11]       # ratio 2036


def test_le_statu_quo_ne_depend_pas_des_multiplicateurs():
    """Sans aucune impulsion, la table des multiplicateurs n'est jamais lue : le
    recalibrage laisse le statu quo identique au bit."""
    from budget_simulator.simulator import FiscalMultipliers
    a = BudgetSimulatorV45(periods=10, mesures={}).simulate()[0]
    sim = BudgetSimulatorV45(periods=10, mesures={})

    class _Interdit(FiscalMultipliers):
        def get_multiplier(self, *args, **kwargs):
            raise AssertionError('multiplicateur lu au statu quo')

    sim.multipliers = _Interdit()
    b = sim.simulate()[0]
    assert a.equals(b)
