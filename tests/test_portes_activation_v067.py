"""Portes d'activation continues (v0.6.7, lot 3b) — suite de
tests/test_continuite_regimes_v067.py.

Une PORTE est un seuil sous lequel un effet proportionnel à la taille d'un levier
est mis à zéro : l'effet vaut déjà 0 en 0, la porte ne fait que créer une marche
à son seuil. Quatre portes du moteur, quatre sauts mesurés sur 23723db :
- effet d'offre (growth.py, ``abs(delta) > 0.1``) : le bonus de potentiel naissait
  d'un coup à coeff × log2(1,1) — transition_ecologique.investissement à 0,1 Md€ :
  −0,80 pt de dette 2035 (plf_2026, Horizons, LR), −0,36 Renaissance, −0,33 Rabot ;
- pass-through TVA (inflation.py, ``tva_impact > 0.003``) : +0,09 pt d'inflation
  2027 d'un coup — curseur TVA à 20,63 % : −0,30 pt de dette 2035, statu quo
  compris (trouvé par lecture du code : le balayage, dont la pente TVA noie ce
  saut, ne l'avait pas repéré) ;
- effort budgétaire dans l'inflation (inflation.py, ``abs(effort) > 0.001``) :
  −0,04 pt (plf_2026, education.enseignants) ;
- filtre des impacts (orchestrator.py, ``|Δ| > 0,1 Md€``) : un levier sous le seuil
  avait son BUDGET compté mais ni multiplicateur, ni effet direct sur le chômage,
  ni impact TVA — l'artefact d'origine du brief (prévention de im_rabot_2029 à
  7,6 Md€) en garde −0,006 pt une fois le régime récession lissé ; sur 08810ad il
  déclenchait la bascule de régime (−1,67 pt). Le filtre ne sert plus qu'au
  RAPPORT (``measure_impacts`` de l'API, inchangé).
"""
import json
import os
from pathlib import Path

import pytest

from budget_simulator.simulator import BudgetSimulatorV45

D = 1e-9
EPSILON_PT = 1e-3


def _inflation(year=3, **etat):
    s = BudgetSimulatorV45()
    s.inflation_precedente = 0.015
    base = {'output_gap': 0.0, 'unemployment_gap': 0.0, 'effort_budgetaire': 0.0, 'tva_impact': 0}
    return s.calculate_inflation(year=year, economic_state={**base, **etat})


@pytest.mark.parametrize('seuil', [0.001, -0.001])
def test_inflation_continue_en_effort(seuil):
    assert abs(_inflation(effort_budgetaire=seuil + D) - _inflation(effort_budgetaire=seuil - D)) < 1e-6


def test_pass_through_tva_continu():
    # Un-shot à l'année 2 (impacts de t−1) : l'ancienne porte était à 0,3 % du PIB.
    assert abs(_inflation(year=2, tva_impact=0.003 + D) - _inflation(year=2, tva_impact=0.003 - D)) < 1e-6
    assert abs(_inflation(year=2, tva_impact=D) - _inflation(year=2, tva_impact=0.0)) < 1e-6


def _scenarios():
    chemin = (os.environ.get('BUDGETLAB_SCENARIOS_JSON') or '').strip()
    if not chemin or not Path(chemin).exists():
        pytest.skip("scenarios.json introuvable (fork moteur public seul)")
    sc = {k: v['apiMeasures'] for k, v in json.loads(Path(chemin).read_text(encoding='utf-8')).items()}
    sc['statu_quo'] = {}
    return sc


def _dette_2035(mesures, levier, param, x):
    m = {**mesures, levier: {**(mesures.get(levier) or {}), param: x}}
    df, _, _ = BudgetSimulatorV45(periods=10, mesures=m).simulate()
    return float(df['Dette/PIB %'].iloc[-1])


# (scénario, levier, paramètre, x du saut sur 23723db, demi-écart sondé) — saut mesuré
POINTS_DE_SAUT = [
    ('lr_2027', 'transition_ecologique', 'investissement', 0.1, 5e-6),          # −0,824
    ('plf_2026', 'transition_ecologique', 'investissement', 0.1, 5e-6),         # −0,805
    ('horizons_2027', 'transition_ecologique', 'investissement', 0.1, 5e-6),    # −0,804
    ('renaissance_2027', 'transition_ecologique', 'investissement', 0.1, 5e-6),  # −0,357
    ('im_rabot_2029', 'transition_ecologique', 'investissement', 0.1, 5e-6),    # −0,334
    ('statu_quo', 'tva_rate', 'taux', 0.20629724, 1e-6),                        # −0,302
    ('plf_2026', 'tva_rate', 'taux', 0.20629724, 1e-6),                         # −0,300
    ('lfi_2027', 'tva_rate', 'taux', 0.20703827, 1e-6),                         # −0,249
    ('plf_2026', 'education', 'enseignants', 9299.712866544724, 8e-3),          # −0,040
    ('im_rabot_2029', 'sante', 'prevention_budget', 7.6, 1e-9),                 # −0,006
]


@pytest.mark.parametrize('sid,levier,param,x,d', POINTS_DE_SAUT,
                         ids=[f'{p[0]}-{p[1]}.{p[2]}@{p[3]:.6g}' for p in POINTS_DE_SAUT])
def test_variation_infinitesimale_ne_deplace_pas_la_dette(sid, levier, param, x, d):
    mesures = _scenarios()[sid]
    ecart = _dette_2035(mesures, levier, param, x + d) - _dette_2035(mesures, levier, param, x - d)
    assert abs(ecart) < EPSILON_PT, (
        f"{sid} {levier}.{param} = {x:.8g} ± {d:.1e} : dette 2035 déplacée de {ecart:+.4f} pt")


def test_activation_d_un_levier_d_offre_depuis_son_defaut_est_continue():
    """Sortir un levier d'offre de son défaut d'un millionième ne doit pas créer
    d'un coup un bonus de potentiel (ancienne porte : rien jusqu'à 0,1 Md€)."""
    sc = _scenarios()['plf_2026']
    assert abs(_dette_2035(sc, 'transition_ecologique', 'investissement', 1e-6)
               - _dette_2035(sc, 'transition_ecologique', 'investissement', 0.0)) < EPSILON_PT


def test_un_petit_levier_est_lu_par_le_moteur_mais_pas_publie_au_rapport():
    """Le filtre de significativité (|Δ| > 0,1 Md€ ou effet micro > 1e-4) ne décide
    plus que du RAPPORT : la charge utile ``measure_impacts`` de l'API est inchangée,
    mais le moteur consomme le levier (impulsions, chômage direct, TVA)."""
    s = BudgetSimulatorV45(periods=3, mesures={'sante': {'prevention_budget': 7.55}})  # Δ 0,05 Md€
    _, _, rapport = s.simulate()
    assert 'sante' in s._last_impacts
    assert 0 < s._last_impacts['sante']['depenses'] <= 0.05  # rampe de compensation déduite
    assert all('sante' not in annee for annee in rapport['measure_impacts_by_year'])
