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
from pathlib import Path

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


METHODO = Path(__file__).resolve().parent.parent / 'docs' / 'METHODOLOGIE.md'


def _fr(x, decimales=0, signe=False):
    """Format de la doc : virgule décimale, signe moins typographique (U+2212)."""
    s = f'{x:+.{decimales}f}' if signe else f'{x:.{decimales}f}'
    return s.replace('-', '\u2212').replace('.', ',')


def _banc_autofinancement(base, cas):
    """Les grandeurs que METHODOLOGIE publie sur le banc d'autofinancement
    (choc de calibrage, 2026-2036 = index 1 à 11)."""
    (df0, ann0, _), (df, ann, _) = base, cas
    periode = range(1, 12)
    n = _niveaux(base, cas)
    cout = sum(0.01 * df['PIB'][i] for i in periode)   # = impulsion injectée (0,01 × PIB de l'année)
    d_rec = sum(ann['Recettes_Totales'][i] - ann0['Recettes_Totales'][i] for i in periode)
    d_dep = sum(ann['Dépenses_Totales'][i] - ann0['Dépenses_Totales'][i] for i in periode)
    d_int = sum(ann['Intérêts_Dette'][i] - ann0['Intérêts_Dette'][i] for i in periode)
    degradation = sum(df0['Déficit'][i] - df['Déficit'][i] for i in periode)
    return {
        'cout': cout, 'd_recettes': d_rec, 'd_depenses_hors_impulsion': d_dep - cout,
        'd_interets': d_int, 'degradation': degradation, 'part_rendue': 1 - degradation / cout,
        'volume': sum(n[2:12]) / 10 * TAUX_PRELEVEMENTS_AUTOFINANCEMENT,
        'niveau_4': n[5], 'niveau_10': n[11], 'nominal_2030': (df['PIB'][5] / df0['PIB'][5] - 1) * 100,
        'dette': {i: df['Dette'][i] - df0['Dette'][i] for i in periode},
        'ratio': {i: df['Dette/PIB %'][i] - df0['Dette/PIB %'][i] for i in periode},
    }


def test_chiffres_publies_du_banc_lies_a_la_mesure(mesures):
    """Reprise après réfutation (V2-06) : chaque chiffre que METHODOLOGIE publie
    sur le banc d'autofinancement est RECALCULÉ ici et doit figurer tel quel dans
    la doc. Une dérive du moteur casse la doc au lieu de la laisser se périmer —
    c'est ainsi qu'un « 11 % » mesuré avant la fin des lots v0.6.7 a survécu.
    L'identité comptable (dégradation = Δdépenses + Δintérêts − Δrecettes)
    garantit que la décomposition publiée explique bien le solde."""
    base, cas = mesures
    m = _banc_autofinancement(base, cas['investissement'])
    d_dep_total = m['d_depenses_hors_impulsion'] + m['d_interets']
    assert m['degradation'] == pytest.approx(m['cout'] + d_dep_total - m['d_recettes'], abs=0.5)
    attendus = {
        'part rendue': f"ne récupère que {_fr(100 * m['part_rendue'])} % du coût brut ({_fr(m['cout'])} Md EUR",
        'recettes induites': f"recettes induites (+{_fr(m['d_recettes'])} Md EUR",
        'dépenses induites': (f"(+{_fr(d_dep_total)} Md EUR : dépenses indexées sur les prix "
                              f"+{_fr(m['d_depenses_hors_impulsion'])}, intérêts +{_fr(m['d_interets'])})"),
        'volume': f"× {_fr(TAUX_PRELEVEMENTS_AUTOFINANCEMENT, 2)} = {_fr(m['volume'], 2)} < 1",
        'dette nominale': f"+{_fr(m['dette'][5])} Md EUR en 2030, +{_fr(m['dette'][11])} Md EUR en 2036",
        'PIB nominal 2030': f"{_fr(m['nominal_2030'], 2, True)} % en 2030 pour {_fr(m['niveau_4'], 2, True)} % en volume",
        'ratio 2030-2031': (f"en 2030 ({_fr(m['ratio'][5], 2, True)} pt) "
                            f"et 2031 ({_fr(m['ratio'][6], 2, True)} pt)"),
        'ratio 2035': f"({_fr(m['ratio'][10], 1, True)} pt en 2035)",
        'niveau 4 ans': f"effet de niveau de {_fr(m['niveau_4'], 2)} % du PIB à 4 ans",
        'niveau 10 ans': f"et de {_fr(m['niveau_10'], 2)} % à 10 ans",
    }
    texte = ' '.join(METHODO.read_text(encoding='utf-8').split())
    manquants = [f'{nom} : « {chaine} »' for nom, chaine in attendus.items() if chaine not in texte]
    assert not manquants, ('METHODOLOGIE ne publie plus la mesure du banc (moteur ou doc à '
                           'réaligner) :\n' + '\n'.join(manquants))


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
