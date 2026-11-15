"""Inflation : le terme d'« effort budgétaire » est retiré (lot 1 des corrections d'équations).

Jusqu'à v0.8.1, ``calculate_inflation`` ajoutait à la courbe de Phillips un effet DIRECT de
l'effort budgétaire de l'année précédente : −0,12 × effort pour une consolidation, +0,08 × |effort|
pour une expansion, chaque année tant que l'effort durait. Défauts déclarés depuis v0.6.1 (I18) et
confirmés par la revue des sources de novembre 2026 :

- aucune source : les modèles français (Mésange, ThreeME) et ceux du SEBC (Kilponen et al. 2019)
  n'ont pas de terme direct de l'effort global sur les prix ; l'effet y passe par la demande (écart
  de production, chômage, salaires). Les études empiriques lues mesurent un effet total : celle de
  Checherita-Westphal & Pesso (BCE WP 2996, 2024) trouve une réponse des prix aux relances
  amplifiée quand la dette est haute, que le moteur ne modélise pas (limite déclarée : sous-estimation
  probable de l'inflation des relances) et que l'ancien terme, indépendant de la dette, ne
  représentait pas ;
- double compte : la Phillips lit déjà l'écart de production que l'effort ouvre ;
- asymétrie et dérive : appliqué à un NIVEAU d'effort, il déplaçait l'inflation pour toujours.
  Après un choc permanent d'un point de PIB, l'écart d'inflation restait de +0,12 à −0,19 point à
  20 ans alors que l'écart de production s'était refermé, et le niveau des prix divergeait.

Contrat verrouillé ici : l'inflation ne dépend du budget que par l'écart de production (Phillips
ancrée) et par le passage de la TVA dans les prix ; après un choc permanent, l'écart d'inflation
s'éteint ; la réponse des prix à un choc de transferts de ±1 point de PIB est symétrique.
Aucune donnée du dépôt parent n'est lue : chocs synthétiques sur le statu quo.
"""
import inspect
import re
from pathlib import Path

import pytest

from budget_simulator.engine.inflation import InflationMixin
from budget_simulator.simulator import BudgetSimulatorV45

EFFORTS = (-0.08, -0.02, -0.005, -1e-6, 1e-6, 0.005, 0.02, 0.08)
ECARTS_DE_PRODUCTION = (-0.02, 0.0, 0.02)


def _inflation(effort, output_gap, annee=3):
    sim = BudgetSimulatorV45()
    sim.inflation_precedente = 0.015
    etat = {'output_gap': output_gap, 'unemployment_gap': 0.0, 'tva_impact': 0.0,
            'effort_budgetaire': effort}
    return sim.calculate_inflation(annee, etat)


@pytest.mark.parametrize('output_gap', ECARTS_DE_PRODUCTION)
def test_l_inflation_ne_depend_pas_de_l_effort(output_gap):
    """À écart de production donné, l'effort budgétaire ne change pas l'inflation, au bit près.
    v0.8.1 : effort 2 % → −0,24 point, effort −2 % → +0,16 point."""
    reference = _inflation(0.0, output_gap)
    ecarts = {e: _inflation(e, output_gap) - reference for e in EFFORTS}
    assert all(d == 0.0 for d in ecarts.values()), ecarts


def test_calculate_inflation_ne_lit_aucun_effort():
    """Garde de source : aucun terme d'effort ne se réintroduit dans l'équation."""
    assert 'effort' not in inspect.getsource(InflationMixin.calculate_inflation)


def test_l_orchestrateur_ne_transmet_aucun_effort_a_l_inflation():
    """Plomberie : l'état passé à ``calculate_inflation`` ne porte plus d'effort (aucun lecteur)."""
    sim = BudgetSimulatorV45(periods=4, mesures={'tva_rate': {'taux': 0.21}})
    origine, cles = sim.calculate_inflation, set()

    def espion(year, etat):
        cles.update(etat)
        return origine(year, etat)
    sim.calculate_inflation = espion
    sim.simulate()
    assert cles and not {c for c in cles if 'effort' in c}, sorted(cles)


# --- Choc permanent sur le statu quo (moteur complet) -------------------------------------------

PERIODES = 22  # 2025-2047 : horizon h = indice − 1 (budget 2026, effet macro dès 2027)


def _simuler(levier=None, taille=0.0):
    class _Choc(BudgetSimulatorV45):
        def apply_measures(self, year, spending, revenues, gdp, inflation, unemployment):
            sp, rv, imp = super().apply_measures(year, spending, revenues, gdp, inflation, unemployment)
            if levier:
                x = taille * gdp
                imp = dict(imp)
                imp[levier] = {'depenses': x, 'recettes': 0.0}
                sp += x
            return sp, rv, imp
    return _Choc(periods=PERIODES, mesures={}).simulate()


@pytest.fixture(scope='module')
def chocs():
    import budget_simulator.engine.orchestrator as orch
    mp = pytest.MonkeyPatch()
    mp.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
    try:
        base = _simuler()
        return base, {(lev, s): _simuler(lev, s * 0.01)
                      for lev in ('collectivites', 'education', 'retraites') for s in (+1, -1)}
    finally:
        mp.undo()


def _ecarts(base, cas, colonne, table):
    b, c = base[table][colonne].values, cas[table][colonne].values
    return [c[i] - b[i] for i in range(len(b))]


@pytest.mark.parametrize('levier', ['collectivites', 'education', 'retraites'])
@pytest.mark.parametrize('signe', [+1, -1])
def test_l_ecart_d_inflation_s_eteint_apres_un_choc_permanent(chocs, levier, signe):
    """Dépense courante, investissement, transferts : un choc permanent de ±1 point de PIB fait
    bouger l'inflation pendant que l'écart de production est ouvert, puis l'écart d'inflation
    s'éteint (≤ 0,02 point à 20 ans). v0.8.1 : +0,12 à −0,19 point à 20 ans, sans fin."""
    base, cas = chocs
    d_pi = _ecarts(base, cas[(levier, signe)], 'Inflation %', 0)
    d_gap = _ecarts(base, cas[(levier, signe)], 'Output_Gap %', 1)
    assert max(abs(x) for x in d_pi[2:12]) > 0.02, 'NON_VACUITE : le choc ne bouge pas l\'inflation'
    assert abs(d_gap[20]) < 0.1, f'écart de production non refermé à 20 ans : {d_gap[20]:+.3f}'
    assert abs(d_pi[21]) <= 0.02, (
        f'{levier} {signe:+d} pt : écart d\'inflation à 20 ans {d_pi[21]:+.4f} point')


@pytest.mark.parametrize('horizon', [5, 10])
def test_reponse_des_prix_symetrique_pour_les_transferts(chocs, horizon):
    """Transferts (même multiplicateur dans les deux sens) : ±1 point de PIB déplace le niveau des
    prix d'autant dans les deux sens, à 5 % près. v0.8.1 : rapport 1,26 à 5 ans."""
    base, cas = chocs
    hausse = _ecarts(base, cas[('retraites', +1)], 'Déflateur', 1)[horizon + 1]
    coupe = _ecarts(base, cas[('retraites', -1)], 'Déflateur', 1)[horizon + 1]
    assert hausse > 0 > coupe
    assert abs(coupe) / hausse == pytest.approx(1.0, abs=0.05), (hausse, coupe)


def _fr(x):
    """Format des documents : signe explicite, virgule décimale, signe moins typographique."""
    return f'{x:+.2f}'.replace('-', '\u2212').replace('.', ',')


def test_chiffres_publies_du_banc_lies_a_la_mesure(chocs):
    """Lot 1 (15/11/2026) : les chiffres « mesure du moteur actuel » de l'encadré « Terme d'effort
    de l'inflation retiré » de METHODOLOGIE (choc permanent de ±1 point de PIB de dépense courante,
    statu quo, écart du déflateur au statu quo en %, à 5 et à 20 ans) sont recalculés ici et
    cherchés tels quels ; la comparaison aux deux modèles français publiés qui les suit (ThreeME
    0,89 % ; Mésange 1,3 à 1,5 % à 5 ans) est vérifiée sur la même mesure. Les chiffres de v0.8.1,
    avec le terme, sont datés et ne bougent plus. Un chiffre qui cesse de reproduire fait rougir
    la CI."""
    base, cas = chocs

    def ecart_prix(signe, horizon):
        b = base[1]['Déflateur'].values
        c = cas[('collectivites', signe)][1]['Déflateur'].values
        return 100 * (c[horizon + 1] / b[horizon + 1] - 1)
    hausse_5 = ecart_prix(+1, 5)
    attendu = (f"sans lui (mesure du moteur actuel) : {_fr(hausse_5)} / {_fr(ecart_prix(-1, 5))} % à 5 ans, "
               f"{_fr(ecart_prix(+1, 20))} / {_fr(ecart_prix(-1, 20))} % à 20 ans")
    texte = (Path(__file__).resolve().parents[1] / 'docs' / 'METHODOLOGIE.md').read_text(encoding='utf-8')
    texte = ' '.join(re.sub(r'\n>\s?', ' ', texte).split())
    assert attendu in texte, attendu
    # « un peu plus de la moitié de ThreeME (0,89 %) et un tiers environ de Mésange (1,3 à 1,5 %) »
    assert 'un peu plus de la moitié de ThreeME (0,89 %) et un tiers environ de Mésange (1,3 à 1,5 %)' in texte
    assert 0.5 < hausse_5 / 0.89 < 2 / 3, hausse_5
    assert 0.3 < hausse_5 / 1.5 and hausse_5 / 1.3 < 0.45, hausse_5
