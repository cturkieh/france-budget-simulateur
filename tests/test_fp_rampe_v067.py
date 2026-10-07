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


def _fp(mesures):
    """{année: impacts du levier fonction_publique} (canaux ménages v0.6.8)."""
    _, _, rapport = BudgetSimulatorV45(periods=10, mesures=mesures).simulate()
    return {an['Année']: an.get('fonction_publique', {})
            for an in rapport['measure_impacts_by_year'] if an['Année'] >= 2026}


def test_creations_de_postes_sans_effet_direct_sur_le_pouvoir_d_achat():
    """v0.6.8 (arbitrage du mainteneur) : les embauches publiques n'ont aucun
    effet DIRECT sur le pouvoir d'achat — elles passent par la croissance, qui
    contient la production publique de ces agents. Remplace le test v0.6.7
    « l'incrément de la rampe × 0,001 / 40 000 postes »."""
    fp = _fp({'fonction_publique': {'effectifs': 60_000, 'point_indice': 0}})
    assert any(imp.get('depenses', 0.0) > 0 for imp in fp.values())
    for annee, imp in fp.items():
        if imp:
            assert set(imp['menages'].values()) == {0.0}, annee


def test_point_d_indice_canal_remunerations_publiques_en_niveau():
    """Le point d'indice est un revenu des agents en place : canal
    ``remunerations_publiques`` au coût de l'ANNÉE, chaque année (niveau lu par
    l'indice RDB-moteur, plus d'effet one-time 2026 de 0,003/point)."""
    fp = _fp({'fonction_publique': {'effectifs': 0, 'point_indice': 3.0}})
    for annee in range(2026, 2036):
        assert fp[annee]['menages']['remunerations_publiques'] == pytest.approx(
            fp[annee]['depenses'], rel=1e-12), annee
        assert fp[annee]['depenses'] > 0


def test_scenario_rn_trajectoire_publiee():
    """De bout en bout : RN encode −201 000 (85 000 agences + 116 000
    collectivités, trajectoire 2027-2032). Le levier ne rapporte rien en 2026."""
    _, _, rapport = BudgetSimulatorV45(periods=10, mesures={
        'fonction_publique': {'effectifs': -201_000, 'point_indice': 0}}).simulate()
    par_an = {an['Année']: an.get('fonction_publique', {}).get('depenses', 0.0)
              for an in rapport['measure_impacts_by_year']}
    assert par_an[2026] == 0.0
    assert par_an[2027] < 0 and par_an[2032] < par_an[2031] < par_an[2027]


# ---------------------------------------------------------------------------
# Coût d'un agent indexé (v0.6.7) : COUT_MOYEN_AGENT_FP_EUR est calé en euros
# 2025 ; il valorisait un poste au même montant en 2035 (60 k€), dans un moteur
# où tout le reste est en euros courants — sous-estimant les économies d'une
# réduction et le coût d'une création. Désormais × l'indice de prix des
# dépenses du moteur (celui qui fait croître la masse salariale du statu quo),
# dans les DEUX handlers FP : un poste vaut le même coût pour la réforme et
# pour le curseur, chaque année.
# ---------------------------------------------------------------------------

class _Releve(BudgetSimulatorV45):
    """Relève, à chaque appel des handlers FP, l'indice de prix des dépenses par
    un chemin indépendant (masse nominale de la catégorie / volume) et les
    postes réalisés."""

    def _apply_fonction_publique(self, measure, params, year, gdp, inflation, unemployment):
        ms = 'masse_salariale'
        self.indice[year] = (self.masse_categorie_nominale(ms)
                             / (self.spending_categories_base[ms] * self._spending_factors[ms]))
        return super()._apply_fonction_publique(measure, params, year, gdp, inflation, unemployment)


def _trajectoire_fp(mesures):
    sim = _Releve(periods=10, mesures=mesures)
    sim.indice = {}
    _, _, rapport = sim.simulate()
    par_an = {an['Année']: an for an in rapport['measure_impacts_by_year']}
    return sim, par_an


def test_cout_agent_hors_simulation_reste_le_cout_2025():
    """Hors simulation (appel direct d'un handler), l'indice vaut exactement 1 :
    les appels unitaires gardent 60 k€ par poste."""
    sim = BudgetSimulatorV45(periods=10, mesures={})
    assert sim.indice_prix_depenses() == 1.0


def test_cout_agent_suit_l_indice_de_prix_des_depenses():
    """RED v0.6.6 : 60 k€ par poste en 2035 comme en 2026. Désormais, chaque
    année, économie d'un poste non remplacé = COUT_MOYEN_AGENT_FP_EUR × indice
    de prix des dépenses de l'année (~70 k€ en 2035)."""
    cible = -201_000
    sim, par_an = _trajectoire_fp({'fonction_publique': {'effectifs': cible, 'point_indice': 0}})
    for annee in range(2027, 2036):
        postes = cible * min(annee - 2026, 6) / 6
        attendu = postes * COUT_MOYEN_AGENT_FP_EUR * sim.indice[annee] / 1e9
        assert par_an[annee]['fonction_publique']['depenses'] == pytest.approx(attendu, rel=1e-9), annee
    assert 66_000 < COUT_MOYEN_AGENT_FP_EUR * sim.indice[2035] < 74_000
    assert sim.indice[2026] > 1.0


def test_reforme_et_curseur_valorisent_un_poste_au_meme_cout():
    """Source unique du coût d'un poste (v0.6.0) PRÉSERVÉE sous l'indexation :
    l'économie de la réforme par poste non remplacé est celle du curseur."""
    mesures = {'fonction_publique_reforme': {'fusion_agences': 50, 'digitalisation': 50}}
    sim, par_an = _trajectoire_fp({**mesures, 'fonction_publique': {'effectifs': 60_000, 'point_indice': 0}})
    for annee in (2031, 2033, 2035):   # après la phase de coûts (2026-2029)
        postes = sim._reforme_fp_reduction_cumulee(annee)
        economie = -par_an[annee]['fonction_publique_reforme']['depenses']
        assert economie == pytest.approx(postes * COUT_MOYEN_AGENT_FP_EUR * sim.indice[annee] / 1e9,
                                         rel=1e-9), annee


# ---------------------------------------------------------------------------
# Toute masse de la fonction publique en euros de l'année (v0.6.7, suite de
# la réfutation) : après l'indexation du coût d'un agent, trois montants FP
# restaient en euros 2025 — la masse salariale du point d'indice (330 Md€), la
# part FP de la hausse du SMIC (50 Md€) et les coûts de la réforme de l'État
# (0,15 Md€ par point d'intensité, pénalité 0,3 Md€). Les économies d'une
# réduction d'effectifs étaient indexées, pas le coût d'une hausse de
# rémunération : asymétrie résiduelle. Même indice pour tous.
# ---------------------------------------------------------------------------

class _ReleveFP(BudgetSimulatorV45):
    """Relève l'indice de prix des dépenses par un chemin indépendant (masse
    nominale de la catégorie / volume) à chaque appel d'un handler FP."""

    def _relever(self, year):
        ms = 'masse_salariale'
        self.indice[year] = (self.masse_categorie_nominale(ms)
                             / (self.spending_categories_base[ms] * self._spending_factors[ms]))

    def _apply_fonction_publique(self, measure, params, year, *args):
        self._relever(year)
        return super()._apply_fonction_publique(measure, params, year, *args)

    def _apply_fonction_publique_reforme(self, measure, params, year, *args):
        self._relever(year)
        return super()._apply_fonction_publique_reforme(measure, params, year, *args)

    def _apply_smic(self, measure, params, year, *args):
        self._relever(year)
        return super()._apply_smic(measure, params, year, *args)


def _depenses_fp(mesures, levier):
    sim = _ReleveFP(periods=10, mesures=mesures)
    sim.indice = {}
    _, _, rapport = sim.simulate()
    return sim, {an['Année']: an.get(levier, {}).get('depenses', 0.0)
                 for an in rapport['measure_impacts_by_year'] if an['Année'] >= 2026}


def test_point_d_indice_sur_la_masse_salariale_de_l_annee():
    """RED : +3 % de point d'indice = 9,9 Md€ en 2035 comme en 2026."""
    sim, dep = _depenses_fp({'fonction_publique': {'effectifs': 0, 'point_indice': 3.0}},
                            'fonction_publique')
    for annee in range(2026, 2036):
        assert dep[annee] == pytest.approx(0.03 * 330 * sim.indice[annee], rel=1e-9), annee
    assert sim.indice[2035] > 1.1


def test_part_fp_du_smic_sur_la_masse_de_l_annee():
    """RED : la part FP d'une hausse du SMIC (15 % des agents, 50 Md€ de masse)
    restait en euros 2025 ; la part « aides sociales » n'est pas une masse FP."""
    hausse = (2000 - 1800) / 1800
    sim, dep = _depenses_fp({'smic': {'montant_brut': 2000}}, 'smic')
    for annee in range(2026, 2036):
        part_fp = dep[annee] - 12 * hausse
        assert part_fp == pytest.approx(50 * hausse * sim.indice[annee], rel=1e-9), annee


def test_couts_de_la_reforme_sur_l_indice_de_l_annee():
    """RED : 0,15 Md€ par point d'intensité et par an (2026-2029) en euros 2025.
    En 2026 la réforme n'a que des coûts ; ensuite coûts − économies, les deux
    au même indice."""
    # Intensité 20 : soldes 2026-2029 tous au-delà du filtre de significativité
    # du rapport (|Δ| > 0,1 Md€) ; à intensité 10, 2027 y tombe (+0,09).
    sim, dep = _depenses_fp({'fonction_publique_reforme': REFORME_MAX}, 'fonction_publique_reforme')
    for annee in range(2026, 2030):
        postes = sim._reforme_fp_reduction_cumulee(annee)
        attendu = (20 * 0.15 - postes * COUT_MOYEN_AGENT_FP_EUR / 1e9) * sim.indice[annee]
        assert dep[annee] == pytest.approx(attendu, rel=1e-9), annee


def test_penalite_de_degradation_du_service_indexee():
    """Fusion > 70 sans numérisation : +0,3 Md€/an dès 2028, au même indice."""
    params = {'fusion_agences': 80, 'digitalisation': 0}
    sim, dep = _depenses_fp({'fonction_publique_reforme': params}, 'fonction_publique_reforme')
    for annee in (2030, 2035):
        postes = sim._reforme_fp_reduction_cumulee(annee)
        attendu = (0.3 - postes * COUT_MOYEN_AGENT_FP_EUR / 1e9) * sim.indice[annee]
        assert dep[annee] == pytest.approx(attendu, rel=1e-9), annee
