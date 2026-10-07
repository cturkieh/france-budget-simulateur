"""Curseur « effectifs » de la fonction publique : rampe 2027-2032 et vivier
partagé avec la réforme de l'État (v0.6.7, réfutation des handlers, arbitrage
de Cyril du 07/10/2026).

v0.6.6 : la cible était posée dès 2026, dans la seule limite des départs
cumulés depuis 2026 (157 000 par an, 100 % non remplacés) : RN (−201 000) et
LR (−300 000) supprimaient 157 000 postes dès 2026 et atteignaient leur cible
dès 2027, alors que leurs sources annoncent une trajectoire 2027-2032 ou « sur
le quinquennat » ; les +60 000 postes de LFI étaient recrutés en un an. Le
curseur pouvait en outre ne remplacer AUCUN départ (100 %), ce que la réforme
de l'État, qui puise dans le même vivier, ne peut pas faire (67 % au plus).

Contrat : la cible est un STOCK atteint par une rampe linéaire, même règle pour
tous les programmes et dans les deux sens — 0 en 2026 (budget voté, le mandat
n'a pas commencé), un sixième de la cible par an de 2027 à 2032, la cible pleine
ensuite. Une réduction puise dans le vivier des départs : réforme + curseur ne
dépassent jamais FP_TAUX_NON_REMPLACEMENT_MAX (le taux de la réforme à son
intensité maximale) des départs cumulés depuis la première cohorte (2027).
"""
import pytest

from budget_simulator.constants import (
    COUT_MOYEN_AGENT_FP_EUR,
    DEPARTS_ANNUELS_FP,
    FP_TAUX_NON_REMPLACEMENT_MAX,
)
from budget_simulator.handlers.efficience import (
    FP_EFFECTIFS_ANNEE_CIBLE,
    FP_EFFECTIFS_PREMIERE_ANNEE,
    REFORME_FP_PREMIERE_COHORTE,
)
from budget_simulator.simulator import BudgetSimulatorV45

REFORME_MAX = {'fusion_agences': 100, 'digitalisation': 100}


def _postes(mesures, annee):
    """Postes réalisés par le curseur l'année donnée (hors simulation : coût d'un
    agent = COUT_MOYEN_AGENT_FP_EUR), réforme lue dans `mesures`."""
    sim = BudgetSimulatorV45(periods=10, mesures=mesures)
    d_eff, _, _ = sim._apply_fonction_publique(
        {}, {**mesures['fonction_publique'], 'point_indice': 0}, annee, 3100, 0.015, 0.075)
    return d_eff * 1e9 / COUT_MOYEN_AGENT_FP_EUR, sim


def test_regle_calendaire_2027_2032():
    """Première année = première cohorte de la réforme (même vivier), cible en
    2032 : six années de rampe."""
    assert FP_EFFECTIFS_PREMIERE_ANNEE == REFORME_FP_PREMIERE_COHORTE == 2027
    assert FP_EFFECTIFS_ANNEE_CIBLE == 2032


@pytest.mark.parametrize('cible', [-201_000, -300_000, -3_119, 60_000, 20_000])
def test_rampe_lineaire_de_la_cible(cible):
    """RED v0.6.6 : RN −157 000 dès 2026 et −201 000 dès 2027. Désormais 0 en
    2026, −33 500 en 2027, un sixième de plus chaque année, −201 000 en 2032 et
    au-delà ; même rampe pour une création (LFI +60 000 : +10 000 en 2027)."""
    mesures = {'fonction_publique': {'effectifs': cible}}
    attendu = {2026: 0.0, 2027: cible / 6, 2028: cible * 2 / 6, 2030: cible * 4 / 6,
               2031: cible * 5 / 6, 2032: cible, 2033: cible, 2035: cible}
    for annee, postes in attendu.items():
        realise, _ = _postes(mesures, annee)
        assert realise == pytest.approx(postes, rel=1e-12, abs=1e-6), annee
    if cible == -201_000:
        assert _postes(mesures, 2027)[0] == pytest.approx(-33_500, abs=1e-6)


def test_taux_maximal_de_la_reforme_partage():
    """Le taux maximal partagé EST celui de la réforme à son intensité maximale :
    les deux ne peuvent pas dériver l'un de l'autre."""
    sim = BudgetSimulatorV45(periods=10, mesures={'fonction_publique_reforme': REFORME_MAX})
    cohorte_pleine = (sim._reforme_fp_reduction_cumulee(2031)
                      - sim._reforme_fp_reduction_cumulee(2030))
    assert cohorte_pleine == pytest.approx(FP_TAUX_NON_REMPLACEMENT_MAX * DEPARTS_ANNUELS_FP,
                                           rel=1e-12)


@pytest.mark.parametrize('reforme', [{}, {'fusion_agences': 50, 'digitalisation': 50},
                                     {'fusion_agences': 60, 'digitalisation': 50}, REFORME_MAX])
@pytest.mark.parametrize('cible', [-60_000, -300_000, -900_000])
def test_curseur_effectifs_ne_depasse_pas_le_taux_max_du_vivier_reforme(cible, reforme):
    """RED réfutation (angle 1) : en 2026, −300 000 réalisait 157 000
    non-remplacements, 100 % des départs (zéro recrutement dans toute la FP),
    quand la réforme du même vivier plafonne à 67 %. Désormais, chaque année :
    réforme + curseur ≤ 67 % des départs cumulés depuis 2027, et le curseur ne
    dépasse jamais la part de sa cible que la rampe autorise."""
    mesures = {'fonction_publique_reforme': reforme,
               'fonction_publique': {'effectifs': cible}}
    for annee in range(2026, 2036):
        realise, sim = _postes(mesures, annee)
        cohortes = max(0, annee - FP_EFFECTIFS_PREMIERE_ANNEE + 1)
        total = -realise + sim._reforme_fp_reduction_cumulee(annee)
        assert total <= FP_TAUX_NON_REMPLACEMENT_MAX * DEPARTS_ANNUELS_FP * cohortes * (1 + 1e-12) + 1e-6, annee
        assert -realise <= -cible * min(cohortes, 6) / 6 * (1 + 1e-12) + 1e-6, annee
        assert realise <= 0


def test_plafond_mord_quand_la_reforme_sature_le_vivier():
    """Réforme maximale (67 % de chaque cohorte, montée 0,3 → 1,0) + objectif
    −900 000 hors domaine (appel direct, la porte est contournée) : le curseur
    n'obtient que le solde du vivier, jamais plus."""
    mesures = {'fonction_publique_reforme': REFORME_MAX,
               'fonction_publique': {'effectifs': -900_000}}
    for annee in (2027, 2030, 2035):
        realise, sim = _postes(mesures, annee)
        cohortes = annee - 2026
        solde = (FP_TAUX_NON_REMPLACEMENT_MAX * DEPARTS_ANNUELS_FP * cohortes
                 - sim._reforme_fp_reduction_cumulee(annee))
        assert 0 < solde < 900_000 * min(cohortes, 6) / 6
        assert -realise == pytest.approx(solde, rel=1e-12), annee


def test_creation_de_postes_hors_vivier():
    """Une création ne puise pas dans le vivier : la réforme maximale ne la
    réduit pas (seule la rampe s'applique)."""
    avec, _ = _postes({'fonction_publique_reforme': REFORME_MAX,
                       'fonction_publique': {'effectifs': 60_000}}, 2030)
    sans, _ = _postes({'fonction_publique': {'effectifs': 60_000}}, 2030)
    assert avec == sans == pytest.approx(40_000, rel=1e-12)


def _pa_fp(mesures):
    _, _, rapport = BudgetSimulatorV45(periods=10, mesures=mesures).simulate()
    return {an['Année']: an.get('fonction_publique', {}).get('pouvoir_achat', 0.0)
            for an in rapport['measure_impacts_by_year'] if an['Année'] >= 2026}


def test_pouvoir_achat_des_creations_suit_la_rampe():
    """L'effet NIVEAU des créations (+10 000 postes = +0,00025) n'est plus servi
    en 2026 pour des postes créés de 2027 à 2032 : chaque année émet l'INCRÉMENT
    de la rampe (convention de l'ASU), la somme vaut le niveau atteint."""
    pa = _pa_fp({'fonction_publique': {'effectifs': 60_000, 'point_indice': 0}})
    assert pa[2026] == 0.0
    for annee in range(2027, 2033):
        assert pa[annee] == pytest.approx(10_000 / 40_000 * 0.001, rel=1e-12), annee
    assert all(pa[a] == 0.0 for a in (2033, 2034, 2035))
    assert sum(pa.values()) == pytest.approx(60_000 / 40_000 * 0.001, rel=1e-12)


def test_pouvoir_achat_du_point_d_indice_inchange():
    """Le point d'indice reste un effet one-time immédiat (2026), sans rampe."""
    pa = _pa_fp({'fonction_publique': {'effectifs': 0, 'point_indice': 3.0}})
    assert pa[2026] == pytest.approx(3.0 * 0.003, rel=1e-12)
    assert all(pa[a] == 0.0 for a in range(2027, 2036))


def test_scenario_rn_trajectoire_publiee():
    """De bout en bout : RN encode −201 000 (85 000 agences + 116 000
    collectivités, trajectoire 2027-2032). Le levier ne rapporte rien en 2026."""
    _, _, rapport = BudgetSimulatorV45(periods=10, mesures={
        'fonction_publique': {'effectifs': -201_000, 'point_indice': 0}}).simulate()
    par_an = {an['Année']: an.get('fonction_publique', {}).get('depenses', 0.0)
              for an in rapport['measure_impacts_by_year']}
    assert par_an[2026] == 0.0
    assert par_an[2027] < 0 and par_an[2032] < par_an[2031] < par_an[2027]
