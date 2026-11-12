"""Release E — investissement des collectivités classé investissement productif
(contre-vérification adverse I2 ; point soumis au mainteneur avec son tableau,
réversible par un seul commit).

Constat : à montant égal, 10 Md€ d'investissement public avaient un effet de
signe opposé sur la dette selon qu'ils passaient par l'État
(``transition_ecologique.investissement`` : −0,40 point de dette 2032 en mode
cadre) ou par les collectivités (``collectivites.investissement`` : +0,20).
Cause : la classe de multiplicateur et d'éviction (``INVESTMENT_CORE_MEASURES``) ;
le canal d'offre, lui, est déjà le même.

Correctif : la seule part ``investissement`` de ``collectivites`` (levier à
formule) est publiée dans son impact (clé ``depenses_investissement``) et
forme un flux distinct, ``(collectivites, investissement)``, multiplié et lu
par l'éviction comme l'investissement productif de l'État, avec son profil de
persistance ; la dotation garde la classe de la dépense générique.
"""
import pytest

from budget_simulator.engine.growth import flux_par_levier, part_investissement_expansion
from budget_simulator.simulator import BudgetSimulatorV45, FiscalMultipliers

NETTES = FiscalMultipliers.MESURES_MULTIPLICATEUR_NET
INVEST = BudgetSimulatorV45.INVESTMENT_CORE_MEASURES
DEBUT_CADRE = 2028


def test_part_investissement_declaree():
    assert BudgetSimulatorV45.INVESTISSEMENT_PRODUCTIF_PARTIEL == {'collectivites': 'investissement'}
    assert 'collectivites' not in INVEST   # la dotation n'est pas de l'investissement


def test_flux_distinct_de_la_dotation():
    impacts = {'collectivites': {'depenses': 25.0, 'recettes': 0.0, 'depenses_investissement': 15.0}}
    flux = flux_par_levier(impacts, NETTES)
    assert flux[('collectivites', 'depenses')] == -10.0       # dotation
    assert flux[('collectivites', 'investissement')] == -15.0  # investissement productif
    assert flux[('collectivites', 'recettes')] == 0.0


def test_flux_inchange_sans_part_investissement():
    impacts = {'collectivites': {'depenses': 10.0, 'recettes': 0.0}}
    assert flux_par_levier(impacts, NETTES) == {('collectivites', 'recettes'): 0.0,
                                                ('collectivites', 'depenses'): -10.0}


@pytest.mark.parametrize('montant', [5.0, 15.0])
def test_eviction_meme_part_que_l_etat(montant):
    """La part d'investissement de l'expansion compte l'investissement local
    comme celui de l'État."""
    local = {'collectivites': {'depenses': montant, 'depenses_investissement': montant}}
    etat = {'transition_ecologique': {'depenses': montant}}
    assert part_investissement_expansion(local, INVEST, NETTES) == 1.0
    assert part_investissement_expansion(etat, INVEST, NETTES) == 1.0
    mixte = {'collectivites': {'depenses': 2 * montant, 'depenses_investissement': montant}}
    assert part_investissement_expansion(mixte, INVEST, NETTES) == pytest.approx(0.5, abs=1e-15)


ETAT = dict(output_gap=-0.005, unemployment_gap=0.0, debt_ratio=0.95, unemployment=0.076,
            deficit_ratio=-0.05, interest_rate=0.03)


def _impulsions(impacts):
    sim = BudgetSimulatorV45(periods=10, mesures={})
    sim.pib_nominal = 3000.0
    sim._last_impacts = impacts
    sim._stocker_impulsions(2, dict(ETAT))
    return sim._fiscal_impulses


@pytest.mark.parametrize('montant', [10.0, -10.0])
def test_meme_classe_de_multiplicateur_et_meme_profil_que_l_etat(montant):
    """À montant égal, l'impulsion de l'investissement local a le même
    multiplicateur et le même profil de persistance que celle de
    l'investissement de l'État ; identifiant distinct de la dotation."""
    local = _impulsions({'collectivites': {'depenses': montant, 'recettes': 0.0,
                                           'depenses_investissement': montant}})
    etat = _impulsions({'transition_ecologique': {'depenses': montant, 'recettes': 0.0}})
    sens = 'expansion' if montant > 0 else 'consolidation'
    (d_l, k_l, p_l) = local[(2, 'collectivites', 'investissement', sens)]
    (d_e, k_e, p_e) = etat[(2, 'transition_ecologique', 'depenses', sens)]
    assert d_l == d_e and k_l == k_e and p_l == p_e == BudgetSimulatorV45.DECAY_PROFILE_INVEST
    # Dotation inchangée : aucun flux de dépense générique, l'identifiant de l'impulsion est distinct.
    assert not any(m == 'collectivites' and c == 'depenses' for (_, m, c, _s) in local)


def _simuler(mesures, annee_debut):
    df, _, rapport = BudgetSimulatorV45(periods=10, mesures=mesures, annee_debut=annee_debut).simulate()
    assert rapport['valid'] is True, rapport['warnings']
    return df.set_index('Année'), rapport


@pytest.mark.parametrize('annee_debut', [None, DEBUT_CADRE], ids=['historique', 'cadre2028'])
def test_impact_publie_la_part_investissement(annee_debut):
    _, rapport = _simuler({'collectivites': {'dotation': 130, 'investissement': 8}}, annee_debut)
    debut = annee_debut or 2026
    annees = {int(a['Année']): a for a in rapport['measure_impacts_by_year']}
    for annee in range(debut, 2036):
        assert annees[annee]['collectivites']['depenses_investissement'] == pytest.approx(8.0, abs=1e-12)
    _, sans = _simuler({'collectivites': {'dotation': 130}}, annee_debut)
    assert all('depenses_investissement' not in (a.get('collectivites') or {})
               for a in sans['measure_impacts_by_year'])


@pytest.mark.parametrize('annee_debut, annee', [(DEBUT_CADRE, 2032), (None, 2035)],
                         ids=['cadre2028', 'historique'])
def test_meme_ordre_d_effet_que_l_investissement_de_l_etat(annee_debut, annee):
    """10 Md€ d'investissement public par an : même signe d'effet sur la dette
    (une baisse du ratio) et même ordre de grandeur, qu'ils soient portés par
    l'État ou par les collectivités (avant : +0,20 contre −0,40 point en 2032,
    mode cadre). Le reste d'écart vient de la recette propre du levier de
    l'État (transition écologique)."""
    d0, _ = _simuler({}, annee_debut)
    local, _ = _simuler({'collectivites': {'investissement': 10}}, annee_debut)
    etat, _ = _simuler({'transition_ecologique': {'investissement': 10}}, annee_debut)
    dl = local.at[annee, 'Dette/PIB %'] - d0.at[annee, 'Dette/PIB %']
    de = etat.at[annee, 'Dette/PIB %'] - d0.at[annee, 'Dette/PIB %']
    assert dl < 0 and de < 0, (dl, de)
    assert 0.4 <= dl / de <= 1.6, (dl, de)
