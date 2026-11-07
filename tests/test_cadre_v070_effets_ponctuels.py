"""v0.7.0, lot B — effets PONCTUELS au changement de paramètre, en mode INCRÉMENT.

Constat (dossier du dépôt parent ``docs/plans/passe-cadre-2027-2032.md`` § 2.3) :
les effets « une fois » (compétitivité, emploi, Gini) étaient déclenchés par
``_is_first_year_change`` et calculés sur le NIVEAU complet du paramètre contre
son défaut, à CHAQUE changement. Deux défauts en découlaient :
- bascule : la part du droit en vigueur qui s'écarte du défaut, comptée en 2026,
  était recomptée en 2028 ;
- rampe : l'effet se redéclenchait chaque année au niveau atteint, soit
  1/5 + 2/5 + … + 5/5 = 3 fois l'effet.

Remède : ``effet = f(p_t) − f(p au dernier déclenchement)`` ; la première fois,
``f(p_t)`` (contre le défaut, comme avant : bit-identique en mode historique, où
les paramètres ne changent jamais en cours de simulation). Le cumul ne dépend
plus que du niveau atteint (propriété d) — exactement si l'effet ne dépend que
des paramètres, à l'état macro de l'année près sinon (cotisations patronales,
impôt sur les sociétés).

Les effets ponctuels CALENDAIRES (``_one_time_level``, année d'entrée en
vigueur) relèvent des horloges (lot C), pas de ce lot.
"""
import copy

import pytest

import budget_simulator.engine.orchestrator as orch
from budget_simulator.engine.cadre import CadreTemporel
from budget_simulator.simulator import BudgetSimulatorV45

from cadre_harness import simuler

DEBUT = 2028
ETAT = dict(year=2026, gdp=3100.0, inflation=0.015, unemployment=0.078)

# (levier, clés d'impact ponctuelles, chemin de paramètres) — le dernier bloc est
# le niveau atteint. Couvre chaque site de l'ancien `_is_first_year_change` et le
# traqueur propre de l'assurance chômage.
CHEMINS = [
    ('niches_fiscales_tge', ('competitivite',), [{'montant': v} for v in (57, 50, 40)]),
    ('niches_sociales_tge', ('competitivite', 'chomage'), [{'montant': v} for v in (68, 60, 50)]),
    ('subventions_tge', ('competitivite',), [{'montant': v} for v in (33, 25, 20)]),
    ('cotisations_patronales', ('competitivite', 'chomage', 'emploi'),
     [{'taux': v} for v in (0.26, 0.25, 0.28)]),
    ('impot_societes', ('competitivite',), [{'taux': v, 'niches': 0} for v in (0.27, 0.30, 0.22)]),
    ('impots_production', ('competitivite', 'chomage'), [{'montant': v} for v in (90, 80, 100)]),
    ('is_exceptionnel_tge', ('competitivite',), [{'montant': v} for v in (7.3, 10, 0)]),
    ('tva_rate', ('gini', 'competitivite'), [{'taux': v} for v in (0.21, 0.22, 0.19)]),
    ('impot_revenu', ('gini', 'competitivite'),
     [{'taux_superieur': t, 'decote': d} for t, d in ((0.5, 1.0), (0.55, 0.9), (0.47, 1.0))]),
    ('csg', ('competitivite',), [{'taux': t, 'progressive': p} for t, p in
                                 ((0.1, 1), (0.105, 1), (0.1, 0))]),
    ('cotisations_salariales', ('gini',), [{'baisse_points': v} for v in (1, 2.5, 4)]),
    ('elargissement_ir', ('gini',), [{'taux_contribuables_cible': v} for v in (0.5, 0.6, 0.55)]),
    ('fiscalite_patrimoine', ('gini', 'competitivite'), [{'intensite': v} for v in (0.1, 0.3, -0.2)]),
    ('transition_ecologique', ('gini',),
     [{'investissement': i, 'renovation': r, 'taxe_carbone': c}
      for i, r, c in ((10, 5, 60), (20, 10, 80), (5, 2, 50))]),
    ('transition_ecologique', ('competitivite',),   # part carbone seule (investissement nul)
     [{'investissement': 0, 'renovation': 0, 'taxe_carbone': c} for c in (60, 80, 30)]),
    ('sante', ('gini',), [{'franchise_participation_taux': v} for v in (150, 200, 50)]),
    ('chomage_alloc', ('gini', 'chomage', 'competitivite'),
     [{'taux_remplacement': t, 'duree': d, 'degressivite': g}
      for t, d, g in ((0.65, 24, False), (0.55, 15, True), (0.62, 20, False))]),
    ('abattement_retraites', ('gini',), [{'reforme_active': v} for v in (1, 0, 0)]),
    ('prestations_indexation', ('gini',), [{'taux_indexation': v} for v in (0.9, 0.8, 0.95)]),
]
IDS = [f"{lev}-{'-'.join(cles)}" for lev, cles, _ in CHEMINS]


def _appel(sim, levier, params):
    handler = sim.measure_handlers[levier]
    _, _, impacts = handler(sim.measure_registry[levier], copy.deepcopy(params), **ETAT)
    return impacts


def _cumul(levier, cles, chemin):
    """Somme des effets ponctuels le long du chemin (chaque bloc vu deux fois :
    la seconde année sans changement ne doit rien émettre)."""
    sim = BudgetSimulatorV45(periods=1)
    total = {c: 0.0 for c in cles}
    for params in chemin:
        for _ in range(2):
            impacts = _appel(sim, levier, params)
            for c in cles:
                total[c] += impacts.get(c, 0.0)
    return total


def _niveau(levier, cles, params):
    impacts = _appel(BudgetSimulatorV45(periods=1), levier, params)
    return {c: impacts.get(c, 0.0) for c in cles}


@pytest.mark.parametrize('levier, cles, chemin', CHEMINS, ids=IDS)
def test_d_cumul_le_long_du_chemin_egal_niveau_atteint(levier, cles, chemin):
    """Propriété (d) au niveau du handler, état macro fixe : quel que soit le
    chemin, le cumul des effets ponctuels vaut l'effet du niveau atteint (contre
    le défaut). En mode NIVEAU (v0.6.11), il valait la somme des niveaux."""
    cumul = _cumul(levier, cles, chemin)
    attendu = _niveau(levier, cles, chemin[-1])
    for c in cles:
        assert cumul[c] == pytest.approx(attendu[c], rel=1e-12, abs=1e-15), (levier, c)


@pytest.mark.parametrize('levier, cles, chemin', CHEMINS, ids=IDS)
def test_d_contre_epreuve_le_chemin_n_est_pas_trivial(levier, cles, chemin):
    """Le test précédent n'est pas vrai par vacuité : le premier niveau du chemin
    a bien un effet, et il diffère du niveau atteint."""
    premier = _niveau(levier, cles, chemin[0])
    dernier = _niveau(levier, cles, chemin[-1])
    assert any(premier[c] != dernier[c] for c in cles), levier


def test_d_premier_declenchement_inchange_au_bit():
    """Mode historique : premier passage = effet du niveau contre le défaut,
    exactement la valeur de l'ancien code (golden masters inchangés)."""
    sim = BudgetSimulatorV45(periods=1)
    assert _appel(sim, 'niches_fiscales_tge', {'montant': 52})['competitivite'] == -(58 - 52) * 0.015
    assert _appel(sim, 'niches_fiscales_tge', {'montant': 52})['competitivite'] == 0.0


def test_retraites_indexation_flux_residuel_continu_a_la_bascule():
    """Gini de l'indexation des pensions : plein effet l'année où l'écart s'ouvre,
    puis un flux résiduel (nouvelles cohortes). À un changement d'indexation, le
    flux de l'ancien niveau court jusqu'à la bascule et l'INCRÉMENT prend le plein
    effet : g(i₁)·R + (g(i₂) − g(i₁)), jamais g(i₂) en entier (recompte)."""
    from budget_simulator.constants import (RETRAITES_GINI_PAR_POINT_DESINDEXATION as G,
                                            RETRAITES_GINI_RESIDU_FLUX as R)
    sim = BudgetSimulatorV45(periods=1)
    p1 = {'indexation': 0.9, 'duree_cotisation': 42.5}
    p2 = {'indexation': 0.8, 'duree_cotisation': 42.5}
    g1, g2 = G * (1.0 - 0.9), G * (1.0 - 0.8)
    assert _appel(sim, 'retraites', p1)['gini'] == g1
    assert _appel(sim, 'retraites', p1)['gini'] == g1 * R
    assert _appel(sim, 'retraites', p2)['gini'] == pytest.approx(g1 * R + (g2 - g1), rel=1e-12)
    assert _appel(sim, 'retraites', p2)['gini'] == g2 * R


# ---------------------------------------------------------------------------
# Dans le moteur : la part héritée n'est jamais recomptée
# ---------------------------------------------------------------------------

def _somme_impact(rapport, levier, cle):
    return sum(y.get(levier, {}).get(cle, 0.0) for y in rapport['measure_impacts_by_year'])


def test_d_part_heritee_non_recomptee_a_la_bascule():
    """Droit en vigueur : niches fiscales des grandes entreprises 57 (défaut 58).
    Programme : 52 dès 2028. Effet de compétitivité cumulé = celui de 52 contre le
    défaut ; en mode niveau, l'effet de 57 (2026) s'y ajoutait une seconde fois."""
    rapport = simuler({'niches_fiscales_tge': {'montant': 52}}, annee_debut=DEBUT)[2]
    assert _somme_impact(rapport, 'niches_fiscales_tge', 'competitivite') == pytest.approx(
        -(58 - 52) * 0.015, rel=1e-12)


class _CadreChemin(CadreTemporel):
    """Cadre de TEST dont le programme suit un chemin année par année (pour
    éprouver l'indépendance au chemin avant la rampe du lot D)."""
    chemin = {}

    def mesures_de_l_annee(self, annee):
        base = super().mesures_de_l_annee(annee)
        if annee in self.chemin:
            m = dict(base)
            m.update(copy.deepcopy(self.chemin[annee]))
            return m
        return base


def _simuler_chemin(chemin, monkeypatch):
    vrai = CadreTemporel.preparer.__func__

    def preparer(cls, *args, **kwargs):
        c = vrai(_CadreChemin, *args, **kwargs)
        c.chemin = chemin
        return c
    monkeypatch.setattr(orch.CadreTemporel, 'preparer', classmethod(preparer))
    final = {k: v for an in sorted(chemin) for k, v in chemin[an].items()}
    return simuler(final, annee_debut=DEBUT)[2]


def test_d_chemin_dans_le_moteur_egal_bascule(monkeypatch):
    """Même niveau atteint par deux chemins (bascule 2028 contre 50 → 45 → 40 sur
    2028-2030) : même cumul d'effet de compétitivité (l'effet des niches ne dépend
    que du paramètre : égalité au bit près de l'ordre des sommes)."""
    bascule = _simuler_chemin({DEBUT + k: {'niches_fiscales_tge': {'montant': 40}}
                               for k in range(8)}, monkeypatch)
    chemin = {DEBUT: {'niches_fiscales_tge': {'montant': 50}},
              DEBUT + 1: {'niches_fiscales_tge': {'montant': 45}},
              **{DEBUT + k: {'niches_fiscales_tge': {'montant': 40}} for k in range(2, 8)}}
    rampe = _simuler_chemin(chemin, monkeypatch)
    assert _somme_impact(rampe, 'niches_fiscales_tge', 'competitivite') == pytest.approx(
        _somme_impact(bascule, 'niches_fiscales_tge', 'competitivite'), rel=1e-12)
    assert _somme_impact(bascule, 'niches_fiscales_tge', 'competitivite') == pytest.approx(
        -(58 - 40) * 0.015, rel=1e-12)


# ---------------------------------------------------------------------------
# RÉFUTEUR du lot B : tenter le double comptage
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('levier, cles, chemin', CHEMINS, ids=IDS)
def test_refuteur_b_aller_retour_s_annule(levier, cles, chemin):
    """A → B → A : l'excursion ne laisse rien ; cumul = effet de A."""
    aller_retour = [chemin[0], chemin[1], chemin[0]]
    cumul = _cumul(levier, cles, aller_retour)
    attendu = _niveau(levier, cles, chemin[0])
    for c in cles:
        assert cumul[c] == pytest.approx(attendu[c], rel=1e-12, abs=1e-15), (levier, c)


def test_refuteur_b_retour_au_defaut_annule_l_effet():
    """Chômage (traqueur initialisé à la référence) : référence → réforme →
    référence = zéro au total, sur les trois canaux."""
    ref = {'taux_remplacement': 0.6, 'duree': 18, 'degressivite': False}
    reforme = {'taux_remplacement': 0.5, 'duree': 12, 'degressivite': True}
    cumul = _cumul('chomage_alloc', ('gini', 'chomage', 'competitivite'), [ref, reforme, ref])
    assert all(abs(v) < 1e-15 for v in cumul.values()), cumul


def test_refuteur_b_rampe_cinq_pas_un_seul_effet():
    """Cinq pas de rampe (1/5 … 5/5) : un effet, pas trois (l'artefact du
    dossier, compétitivité LFI 2032 98,19 → 95,75 dans l'émulation)."""
    pas = [{'montant': 58 - k * (58 - 20) / 5} for k in range(1, 6)]
    cumul = _cumul('niches_fiscales_tge', ('competitivite',), pas)['competitivite']
    assert cumul == pytest.approx(-(58 - 20) * 0.015, rel=1e-12)
    niveau_mode = sum(-(58 - p['montant']) * 0.015 for p in pas)
    assert niveau_mode == pytest.approx(3 * cumul, rel=1e-12)  # ce que l'ancien code comptait


def test_refuteur_b_effet_dependant_de_l_etat():
    """Cotisations patronales : l'effet dépend de la masse salariale (PIB). Sur un
    chemin à PIB variable, le cumul s'écarte du niveau atteint d'un terme d'ordre
    (Δ PIB / PIB) × effet, jamais d'un recompte."""
    sim = BudgetSimulatorV45(periods=1)
    handler = sim.measure_handlers['cotisations_patronales']
    total, pibs = 0.0, (3000.0, 3060.0, 3120.0)
    for pib, taux in zip(pibs, (0.26, 0.25, 0.24)):
        total += handler(sim.measure_registry['cotisations_patronales'], {'taux': taux},
                         2026, pib, 0.015, 0.078)[2]['competitivite']
    final = -((0.24 - 0.27) * pibs[-1] * 0.48) * 0.020
    assert total == pytest.approx(final, rel=0.03)
    assert abs(total - final) < 0.03 * abs(final)
