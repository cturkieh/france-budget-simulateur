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

Lot 1 (15/11/2026) : l'éviction est retirée (tests/test_eviction_retiree.py) ;
le test « même part d'investissement de l'expansion que l'État » l'est avec
elle. Ce qui reste du correctif — même classe de multiplicateur et même
profil — est verrouillé par ``test_meme_classe_de_multiplicateur_et_meme_profil_que_l_etat``.
"""
from pathlib import Path

import pytest

from budget_simulator.engine.growth import flux_par_levier
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
    mode cadre, soit 0,06 point par Md€ d'écart). Le reste d'écart venait de la
    recette propre du levier de l'État (transition écologique), retirée au lot 2
    (16/11/2026) : les deux leviers donnent désormais le même effet, au bit
    (tests/test_transition_sans_retour_fiscal.py).

    « Même ordre de grandeur » : écart absolu d'au plus 0,02 point de dette par
    Md€ (l'ancien défaut en donnait 0,06). Jusqu'à v0.8.1, aussi un rapport
    local / État dans [0,4 ; 1,6]. Lot 1, retrait du terme d'effort de
    l'inflation (15/11/2026) : ce terme donnait à toute relance un bonus de
    dénominateur commun aux deux leviers ; sans lui, les deux effets sont proches
    de zéro (−0,06 et −0,16 point en 2035, mode historique) et le rapport tombe à
    0,375, hors de l'intervalle, alors que l'écart (−0,08 → −0,10 point) ne bouge
    presque pas : à cet état du moteur, seule l'assertion d'écart absolu tenait.
    Lot 1, retrait de l'éviction : les deux effets s'écartent de zéro (−0,08 et −0,18
    point en 2035, mode historique) et le rapport revient dans l'intervalle (0,444 ;
    0,727 en 2032, mode cadre ; 0,800 après le recalage du coefficient des transferts).
    Les deux assertions sont donc gardées.

    Re-déclaré au lot 6 (release de paramètres, profil de l'investissement calé sur le tableau du
    FMI, 16/11/2026) : la demande de l'investissement est plus faible dès la première année ; en mode
    historique 2035, les deux effets reviennent près de zéro et de part et d'autre (+0,07 pour
    l'investissement local, −0,03 pour l'État), où ni le signe ni le rapport ne mesurent plus rien.
    L'écart absolu (0,02 point par Md€, inchangé) est vérifié dans les deux modes ; le signe et le
    rapport, là où les effets s'écartent de zéro (mode cadre 2032 : −0,13 et −0,15)."""
    d0, _ = _simuler({}, annee_debut)
    local, _ = _simuler({'collectivites': {'investissement': 10}}, annee_debut)
    etat, _ = _simuler({'transition_ecologique': {'investissement': 10}}, annee_debut)
    dl = local.at[annee, 'Dette/PIB %'] - d0.at[annee, 'Dette/PIB %']
    de = etat.at[annee, 'Dette/PIB %'] - d0.at[annee, 'Dette/PIB %']
    assert abs(dl - de) <= 0.02 * 10, (dl, de)
    if annee_debut is not None:
        assert dl < 0 and de < 0, (dl, de)
        assert 0.4 <= dl / de <= 1.6, (dl, de)


def _fr(x):
    return f'{x:.2f}'.replace('-', '\u2212').replace('.', ',')


def test_chiffres_publies_lies_a_la_mesure():
    """Lot 1 (15/11/2026) : les quatre valeurs que METHODOLOGIE publie pour 10 Md€ par
    an d'investissement local et de l'État (« Mesure du moteur actuel », § Classe de
    multiplicateur) sont recalculées ici et cherchées telles quelles. Le chiffre 2035
    était juste en v0.8.1 et il était devenu faux d'un facteur 4 à 8 sans qu'aucun
    test rougisse."""
    ecarts = {}
    for annee_debut, annee in ((DEBUT_CADRE, 2032), (None, 2035)):
        d0, _ = _simuler({}, annee_debut)
        for nom, mesures in (('local', {'collectivites': {'investissement': 10}}),
                             ('etat', {'transition_ecologique': {'investissement': 10}})):
            df, _ = _simuler(mesures, annee_debut)
            ecarts[(nom, annee)] = df.at[annee, 'Dette/PIB %'] - d0.at[annee, 'Dette/PIB %']
    attendu = (f"Mesure du moteur actuel, 10 Md€ par an : {_fr(ecarts[('local', 2032)])} point de dette 2032 "
               f"(mode cadre) contre {_fr(ecarts[('etat', 2032)])} pour l'État, {_fr(ecarts[('local', 2035)])} "
               f"contre {_fr(ecarts[('etat', 2035)])} en 2035 (mode historique)")
    texte = ' '.join((Path(__file__).resolve().parent.parent / 'docs' / 'METHODOLOGIE.md')
                     .read_text(encoding='utf-8').split())
    assert attendu in texte, attendu
