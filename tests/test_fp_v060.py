"""
Tests-propriétés v0.6.0 — fonction publique : « plafond de vivier » (constat 4,
redesign revue adverse 24/08).

Les économies de la réforme de l'État (fusion + digitalisation) ET les
réductions du curseur « Variation effectifs FP » opèrent par NON-REMPLACEMENT
des départs (pas de licenciement dans la FP française). v0.5.1 : aucun lien
entre les deux handlers. Premier correctif (résiduel : l'objectif d'effectifs
« servi » par la réforme) REJETÉ par la revue adverse : il rendait le curseur
effectifs inerte dès 2029, inversait l'effet marginal de la réforme (3 ans de
coûts purs) et ne pénalisait qu'un seul scénario.

Design retenu (validé : les deux leviers restent cumulables) : le curseur est
une réduction ADDITIONNELLE ; l'anti-double-comptage plafonne le TOTAL des
non-remplacements (réforme + curseur) aux départs CUMULÉS depuis 2026
(DEPARTS_ANNUELS_FP × années) — on ne supprime pas plus de postes qu'il n'en
part. Un objectif massif monte donc en charge au rythme des départs.
Coût par agent UNIFIÉ au coût complet chargé (60 k€ = 330 Md€ / 5,5 M agents,
DGAFP/INSEE). Périmètre distinct documenté : education.enseignants garde son
coût propre (65 k€, poste enseignant chargé) — recouvrement possible avec le
vivier notée comme limite v0.6.1.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from budget_simulator.simulator import BudgetSimulatorV45
from budget_simulator.constants import COUT_MOYEN_AGENT_FP_EUR, DEPARTS_ANNUELS_FP

REFORME_MAX = {'fusion_agences': 100, 'digitalisation': 100}


def _deltas(mesures, year=2030):
    """delta_spending des deux handlers FP pour une config de mesures donnée."""
    s = BudgetSimulatorV45(periods=10, mesures=mesures)
    d_ref, _, _ = s._apply_fonction_publique_reforme(
        {}, mesures.get('fonction_publique_reforme', {}), year, 3100, 0.015, 0.075)
    d_eff, _, _ = s._apply_fonction_publique(
        {}, mesures.get('fonction_publique', {}), year, 3100, 0.015, 0.075)
    return d_ref, d_eff


def test_cout_agent_unifie():
    """Le handler réforme valorise un poste non remplacé au coût complet
    chargé (source unique constants.py), plus jamais 40 k€ sans périmètre."""
    mesures = {'fonction_publique_reforme': REFORME_MAX}
    d_ref, _ = _deltas(mesures, year=2027)
    # 2027 : taux 0,67, efficacité 0,3, ×2 cohortes (formule héritée v0.5.1,
    # min(annees_ecoulees+1, 8) avec annees_ecoulees = year_idx−1 = 1).
    postes = 157000 * 0.67 * 0.3 * 2
    cout_attendu = 20 * 0.15  # coûts d'investissement (intensité 20 × 0,15 Md€)
    economie_attendue = postes * COUT_MOYEN_AGENT_FP_EUR / 1e9
    assert d_ref == pytest.approx(cout_attendu - economie_attendue, rel=0.02)


def test_effectifs_reste_additionnel_sous_le_vivier():
    """Réforme max + objectif −60 000 en 2030 : le vivier cumulé (785 k) couvre
    largement réforme (~526 k) + curseur → le curseur garde son PLEIN effet
    (le design « résiduel » v0.6.0-rc le rendait inerte — régression tuée)."""
    mesures = {'fonction_publique_reforme': REFORME_MAX,
               'fonction_publique': {'effectifs': -60000, 'point_indice': 0}}
    _, d_eff = _deltas(mesures, year=2030)
    assert d_eff == pytest.approx(-60000 * COUT_MOYEN_AGENT_FP_EUR / 1e9, abs=1e-9)


def test_plafond_vivier_annee_1():
    """2026 : un objectif −200 000 ne peut pas dépasser les départs d'une seule
    année (157 k) — montée en charge réaliste au rythme des départs."""
    mesures = {'fonction_publique': {'effectifs': -200000, 'point_indice': 0}}
    _, d_eff = _deltas(mesures, year=2026)
    assert d_eff == pytest.approx(-DEPARTS_ANNUELS_FP * COUT_MOYEN_AGENT_FP_EUR / 1e9, abs=1e-9)


def test_plafond_vivier_avec_reforme():
    """Saturation : réforme max (~526 k en 2030) + objectif −300 000 → seul le
    solde du vivier (785 k − 526 k ≈ 259 k) est réalisable par le curseur."""
    mesures = {'fonction_publique_reforme': REFORME_MAX,
               'fonction_publique': {'effectifs': -300000, 'point_indice': 0}}
    s = BudgetSimulatorV45(periods=10, mesures=mesures)
    deja = s._reforme_fp_reduction_cumulee(2030)
    capacite = DEPARTS_ANNUELS_FP * 5 - deja
    _, d_eff = _deltas(mesures, year=2030)
    assert 0 < capacite < 300000
    assert d_eff == pytest.approx(-capacite * COUT_MOYEN_AGENT_FP_EUR / 1e9, rel=1e-6)


def test_activer_la_reforme_ameliore_le_solde_en_regime():
    """Effet MARGINAL d'activer la réforme quand un objectif d'effectifs est
    déjà posé : en régime (2030), la réforme apporte ses économies propres —
    plus jamais « 3 ans de coûts purs » (bug du design résiduel)."""
    avec = {'fonction_publique_reforme': {'fusion_agences': 60, 'digitalisation': 50},
            'fonction_publique': {'effectifs': -200000, 'point_indice': 0}}
    sans = {'fonction_publique': {'effectifs': -200000, 'point_indice': 0}}
    ref_avec, eff_avec = _deltas(avec, year=2030)
    _, eff_sans = _deltas(sans, year=2030)
    assert (ref_avec + eff_avec) < eff_sans  # activer la réforme améliore le solde FP


def test_hausse_effectifs_cout_plein():
    """Une CRÉATION de postes ne puise pas dans le vivier : coût plein,
    réforme ou pas."""
    mesures = {'fonction_publique_reforme': REFORME_MAX,
               'fonction_publique': {'effectifs': 50000, 'point_indice': 0}}
    _, d_eff = _deltas(mesures, year=2030)
    assert d_eff == pytest.approx(50000 * COUT_MOYEN_AGENT_FP_EUR / 1e9, abs=1e-9)


def test_helper_sanitise_les_params_invalides():
    """Un paramètre invalide dans la réforme (str, NaN, bool) ne contamine pas
    le handler effectifs : le helper le neutralise (revue adverse 24/08)."""
    for mauvais in ('cent', float('nan'), True, None):
        mesures = {'fonction_publique_reforme': {'fusion_agences': mauvais, 'digitalisation': 50},
                   'fonction_publique': {'effectifs': -50000, 'point_indice': 0}}
        s = BudgetSimulatorV45(periods=10, mesures=mesures)
        # Seul le handler EFFECTIFS est appelé (en prod, le handler réforme
        # reçoit ses params via la porte validate_param_domains ; ici on teste
        # le chemin croisé : helper → mesures BRUTES).
        d_eff, _, _ = s._apply_fonction_publique(
            {}, mesures['fonction_publique'], 2030, 3100, 0.015, 0.075)
        assert d_eff == d_eff  # jamais NaN
        assert d_eff <= 0
