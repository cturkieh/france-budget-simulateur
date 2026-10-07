"""Régimes conjoncturels à transition CONTINUE (v0.6.7, lot 3b).

Propriété : une variation infinitésimale d'un paramètre ne déplace jamais la
dette 2035 de plus de ε. Jusqu'en v0.6.6, chaque dépendance du moteur à la
conjoncture était une MARCHE :
- multiplicateurs ×1,15 si gap < −2 % ou écart de chômage > 2 pts, ×0,85 si
  gap > 2 % et écart < −1 pt, ×1,3 (ZLB) si taux < 2 % et gap < −2 %
  (simulator.py, FiscalMultipliers) ;
- dépenses en volume ×0,90 si gap < −2 %, ×1,02 si gap > 2 % (expenditures.py) ;
- inflation ×0,80 si gap < −2,5 % et écart > 1 pt, ×1,08 si gap > 2 % et
  écart < −1 pt (inflation.py) ;
- chômage +0,2 pt si croissance < −1,5 %, −0,1 pt si croissance > 2 % au-dessus
  du NAIRU (unemployment.py) ;
- potentiel ×0,997 si croissance < −2 %, ×1,002 si > 2 % (growth.py) — ces deux
  hystérèses lisent depuis le ré-ancrage du potentiel la croissance CYCLIQUE
  (seuils ré-exprimés en écart au potentiel : −2,6 / +0,9 pt et ±… cf. constants) ;
- plancher monétaire : sous 0,8 % d'inflation, π → 0,7 π + 0,3 π* (inflation.py,
  ``rappel_bce``) — saut de 0,80 à 1,04 % au franchissement, règle non monotone.
Une marche transforme une variation de 10⁻⁹ en saut. RED reproduit : sur 08810ad,
la prévention de im_rabot_2029 à 7,6 Md€ ± 10⁻⁹ coûtait −1,67 pt de dette 2035 ;
sur fd1bf6f (sans bruit), le scanner (scripts/scan_discontinuites.py, chaque
paramètre de PARAM_DOMAINS × 10 scénarios publiés, bissection à 10⁻⁹) trouve les
26 points de ``POINTS_DE_SAUT`` (20 couples scénario × paramètre), de +1,92
à −0,20 pt ; deux de plus (plancher BCE, −0,66 et −0,69 pt) sont apparus une fois
la marche récession lissée, qui les masquait.

Forme retenue (engine/_regimes.py) : celle des modèles à transition lisse
d'Auerbach & Gorodnichenko (2012) — la réponse est une moyenne des réponses des
deux régimes pondérée par un poids continu de l'état —, en rampe linéaire à
support compact : poids 0 (régime normal, au bit) hors de la zone, 1 (plein
régime, au bit) au-delà, 0,5 au seuil historique.
"""
import json
import os
from pathlib import Path

import pytest

from budget_simulator.simulator import BudgetSimulatorV45, FiscalMultipliers

D = 1e-9
COMPO_GENERIQUE = {'depenses': 1.0, 'recettes': 0.0, 'investissement': 0.0}
ETAT_NEUTRE = {'output_gap': 0.0, 'unemployment_gap': 0.0, 'debt_ratio': 1.0, 'interest_rate': 0.023}


def _mult(sens='consolidation', **etat):
    # Instance NEUVE à chaque appel : le cache de get_multiplier arrondit le gap
    # au millième dans sa clé et rendrait deux états voisins identiques par
    # construction — le test serait vert sur une marche.
    return FiscalMultipliers().get_multiplier(sens, COMPO_GENERIQUE, {**ETAT_NEUTRE, **etat}, 3, 'collectivites')


# --- 1. Continuité de chaque régime à son seuil historique --------------------

@pytest.mark.parametrize('sens', ['consolidation', 'expansion'])
@pytest.mark.parametrize('etat,cle', [
    ({'output_gap': -0.02}, 'output_gap'),                                  # récession (gap)
    ({'unemployment_gap': 0.02}, 'unemployment_gap'),                       # récession (chômage)
    ({'output_gap': 0.02, 'unemployment_gap': -0.03}, 'output_gap'),        # expansion (gap)
    ({'output_gap': 0.04, 'unemployment_gap': -0.01}, 'unemployment_gap'),  # expansion (chômage)
    ({'output_gap': -0.02, 'interest_rate': 0.01}, 'output_gap'),           # ZLB
])
def test_multiplicateur_continu_au_seuil(sens, etat, cle):
    bas = _mult(sens, **{**etat, cle: etat[cle] - D})
    haut = _mult(sens, **{**etat, cle: etat[cle] + D})
    assert abs(haut - bas) < 1e-6, (etat, bas, haut)


def _inflation(**etat):
    s = BudgetSimulatorV45()
    s.inflation_precedente = 0.015
    base = {'output_gap': 0.0, 'unemployment_gap': 0.0, 'effort_budgetaire': 0.0, 'tva_impact': 0}
    return s.calculate_inflation(year=3, economic_state={**base, **etat})


@pytest.mark.parametrize('etat,cle', [
    ({'output_gap': -0.025, 'unemployment_gap': 0.03}, 'output_gap'),     # déflation (gap)
    ({'output_gap': -0.05, 'unemployment_gap': 0.01}, 'unemployment_gap'),  # déflation (chômage)
    ({'output_gap': 0.02, 'unemployment_gap': -0.03}, 'output_gap'),      # tensions (gap)
    ({'output_gap': 0.04, 'unemployment_gap': -0.01}, 'unemployment_gap'),  # tensions (chômage)
])
def test_inflation_continue_au_seuil(etat, cle):
    bas = _inflation(**{**etat, cle: etat[cle] - D})
    haut = _inflation(**{**etat, cle: etat[cle] + D})
    assert abs(haut - bas) < 1e-6, (etat, bas, haut)


def _depenses(output_gap):
    s = BudgetSimulatorV45()
    s._reset_state()
    return s.calculate_expenditures(3000.0, 0.015, 0.015, 0.075, 3, output_gap)


@pytest.mark.parametrize('seuil', [-0.02, 0.02])
def test_depenses_continues_au_seuil(seuil):
    assert abs(_depenses(seuil + D) - _depenses(seuil - D)) < 1e-3  # Md€


def _chomage(growth, u_prev=0.085):
    s = BudgetSimulatorV45()
    s._reset_state()
    return s.calculate_unemployment(growth, u_prev, 3, {})


def _potentiel_total():
    s = BudgetSimulatorV45()
    s._reset_state()
    return s.croissance_potentielle_totale()


# Seuils lus sur la croissance CYCLIQUE (écart au potentiel total) depuis le
# ré-ancrage du potentiel (constants.py, HYSTERESE_*_ECART_*).
@pytest.mark.parametrize('nom', ['HYSTERESE_CHOMAGE_ECART_BAS', 'HYSTERESE_CHOMAGE_ECART_HAUT'])
def test_hysterese_chomage_continue_au_seuil(nom):
    from budget_simulator import constants
    seuil = _potentiel_total() + getattr(constants, nom)
    assert abs(_chomage(seuil + D) - _chomage(seuil - D)) < 1e-6


def test_hysterese_chomage_continue_au_nairu():
    """Croissance au plein régime de « rebond » (3 %) : seule la condition « u au-
    dessus du NAIRU » joue. Elle porte sur le chômage APRÈS Okun et convergence
    (u = 0,94·(u_prev + Δ_Okun) + 0,06·NAIRU), qui vaut le NAIRU exactement pour
    u_prev* = NAIRU − Δ_Okun."""
    s = BudgetSimulatorV45()
    s._reset_state()
    nairu = s.base_params['chomage_nairu']
    u_etoile = nairu - s.economic_coeffs['okun'] * (0.03 - s.croissance_potentielle_totale())
    assert abs(_chomage(0.03, u_etoile + D) - _chomage(0.03, u_etoile - D)) < 1e-6


def _potentiel(growth, year=5):
    s = BudgetSimulatorV45()
    s._reset_state()
    s.update_potential_growth(growth, year)
    return s.base_params['croissance_potentielle']


@pytest.mark.parametrize('nom', ['HYSTERESE_POTENTIEL_ECART_BAS', 'HYSTERESE_POTENTIEL_ECART_HAUT'])
def test_hysterese_potentiel_continue_au_seuil(nom):
    from budget_simulator import constants
    seuil = _potentiel_total() + getattr(constants, nom)
    assert abs(_potentiel(seuil + D) - _potentiel(seuil - D)) < 1e-9


def test_plancher_bce_continu_et_croissant():
    """Le plancher accommodant ne fait plus REMONTER l'inflation : la règle est
    continue au seuil et strictement croissante sur toute la plage du moteur
    (clip −0,3 % ; plafond 3 %) — l'ancienne marche envoyait 0,7999 % à 1,04 %."""
    from budget_simulator.constants import BCE_PLANCHER_ACCOMMODANT
    from budget_simulator.engine.inflation import rappel_bce
    assert abs(rappel_bce(BCE_PLANCHER_ACCOMMODANT + D) - rappel_bce(BCE_PLANCHER_ACCOMMODANT - D)) < 1e-6
    xs = [-0.003 + i * 1e-5 for i in range(3301)]
    ys = [rappel_bce(x) for x in xs]
    assert all(b > a for a, b in zip(ys, ys[1:]))


def test_plancher_bce_plateaux_identiques_au_bit():
    from budget_simulator.constants import INFLATION_STRUCTURELLE
    from budget_simulator.engine.inflation import rappel_bce
    for x in (-0.003, 0.0, 0.004, 0.005):      # plein régime (≤ 0,5 %)
        assert rappel_bce(x) == 0.70 * x + 0.30 * INFLATION_STRUCTURELLE
    for x in (0.011, 0.0134, 0.016, 0.02):     # hors zone, jusqu'à la cible BCE
        assert rappel_bce(x) == x


# --- 2. La transition garde les deux régimes et la valeur médiane -------------

def test_plateaux_identiques_au_bit_et_mediane_au_seuil():
    from budget_simulator.constants import REGIME_DEMI_LARGEUR_ECART
    fm = FiscalMultipliers()
    base = _mult(output_gap=0.0)
    h = REGIME_DEMI_LARGEUR_ECART
    # Hors zone : régime normal exact ; au-delà : plein régime exact (×1,15).
    assert _mult(output_gap=-0.02 + h) == base
    assert _mult(output_gap=-0.02 - h) == base * fm.adjustments['recession']
    assert _mult(output_gap=-0.06) == base * fm.adjustments['recession']
    # Au seuil historique : la moitié du chemin (A&G : poids 0,5).
    assert _mult(output_gap=-0.02) == pytest.approx(base * (1 + fm.adjustments['recession']) / 2, rel=1e-12)
    assert _mult('expansion', output_gap=0.06, unemployment_gap=-0.03) == pytest.approx(
        _mult('expansion') * fm.adjustments['expansion'], rel=1e-12)


def test_demi_largeurs_declarees():
    from budget_simulator.constants import REGIME_DEMI_LARGEUR_CROISSANCE, REGIME_DEMI_LARGEUR_ECART
    # ±1 pt sur le gap et l'écart de chômage (zone −3 % → −1 % autour de −2 %) ;
    # ±0,5 pt sur la croissance : avec ±1 pt, la zone du seuil +2 % commencerait
    # à +1 % et engloberait la croissance NORMALE (0,9-1,2 % au statu quo).
    assert REGIME_DEMI_LARGEUR_ECART == 0.01
    assert REGIME_DEMI_LARGEUR_CROISSANCE == 0.005
    # ±0,3 pt sur l'inflation : la plus petite valeur ronde qui garde le plancher
    # BCE croissant avec marge (±0,2 pt : décroissant par endroits).
    from budget_simulator.constants import REGIME_DEMI_LARGEUR_INFLATION
    assert REGIME_DEMI_LARGEUR_INFLATION == 0.003


# --- 3. Les sauts réels trouvés par le scanner (scénarios publiés) -------------

# (scénario, levier, paramètre, x du saut sur fd1bf6f, borne basse, borne haute) — saut mesuré
POINTS_DE_SAUT = [
    ('plf_2026', 'rabot_uniforme', 'taux_reduction', 0.08992468401789665, 0.0, 0.15),            # +1,917
    ('horizons_2027', 'rabot_uniforme', 'taux_reduction', 0.08199266776442528, 0.0, 0.15),       # +1,732
    # Plancher BCE : masqué par la marche récession tant qu'elle existait, révélé
    # après son lissage (même curseur, π 2028 de 0,80 à 1,04 %).
    ('plf_2026', 'rabot_uniforme', 'taux_reduction', 0.06616201177239414, 0.0, 0.15),            # −0,663
    ('horizons_2027', 'rabot_uniforme', 'taux_reduction', 0.06585099354386331, 0.0, 0.15),       # −0,687
    ('lfi_2027', 'smic', 'montant_brut', 1814.4217589497566, 1400.0, 2200.0),                    # +0,201
    ('lfi_2027', 'smic', 'montant_brut', 1969.9858686327934, 1400.0, 2200.0),                    # +0,548
    ('lfi_2027', 'smic', 'montant_brut', 2170.714266002178, 1400.0, 2200.0),                     # +0,259
    ('im_rabot_2029', 'impot_societes', 'taux', 0.1552862522006035, 0.15, 0.35),                 # +1,396
    ('im_rabot_2029', 'chomage_alloc', 'duree', 29.086094346642497, 12.0, 36.0),                 # −0,281
    ('im_rabot_2029', 'chomage_alloc', 'taux_remplacement', 0.7347616835311055, 0.45, 0.8),      # −0,281
    ('im_rabot_2029', 'fonction_publique', 'point_indice', 4.6526683703064915, -2.0, 10.0),      # −1,395
    ('im_rabot_2029', 'education', 'budget', 68.70132765546441, 60.0, 90.0),                     # −0,280
    ('im_rabot_2029', 'education', 'budget', 83.16906667873263, 60.0, 90.0),                     # −1,366
    ('im_rabot_2029', 'education', 'enseignants', 56943.502336740494, -20000.0, 60000.0),        # −0,280
    ('im_rabot_2029', 'education', 'salaires', 7.40265529602766, -5.0, 15.0),                    # −0,280
    ('im_rabot_2029', 'collectivites', 'dotation', 124.98244257830083, 95.0, 150.0),             # −1,394
    ('im_rabot_2029', 'collectivites', 'investissement', 8.00581269338727, -10.0, 20.0),         # −0,281
    ('im_rabot_2029', 'collectivites', 'investissement', 14.982442568987608, -10.0, 20.0),       # −1,394
    ('im_rabot_2029', 'defense', 'budget', 58.22046270594001, 40.0, 70.0),                       # −0,281
    ('im_rabot_2029', 'defense', 'budget', 65.35380560532212, 40.0, 70.0),                       # −1,395
    ('im_rabot_2029', 'transition_ecologique', 'investissement', 18.169066701084375, 0.0, 50.0),  # −1,340
    ('im_rabot_2029', 'transition_ecologique', 'renovation', 18.169066682457924, 0.0, 40.0),     # −1,347
    ('im_rabot_2029', 'recherche_publique', 'budget', 3.70132764428854, 0.0, 20.0),              # −0,280
    ('im_rabot_2029', 'recherche_publique', 'budget', 18.169066689908504, 0.0, 20.0),            # −1,333
    ('im_rabot_2029', 'csg', 'taux', 0.08180337572097779, 0.08, 0.12),                           # +1,406
    ('im_rabot_2029', 'cotisations_salariales', 'baisse_points', 3.9933808241039515, 0.0, 5.0),  # −1,406
    ('im_rabot_2029', 'impots_production', 'montant', 73.03971507251262, 37.0, 125.0),           # +1,403
    ('im_rabot_2029', 'subventions_tge', 'montant', 47.242396688088775, 5.0, 50.0),              # −1,395
]
EPSILON_PT = 1e-3  # pt de dette 2035 ; un saut de régime en vaut 200 à 1 900


def _scenarios():
    chemin = (os.environ.get('BUDGETLAB_SCENARIOS_JSON') or '').strip()
    if not chemin or not Path(chemin).exists():
        pytest.skip("scenarios.json introuvable (fork moteur public seul)")
    return {k: v['apiMeasures'] for k, v in json.loads(Path(chemin).read_text(encoding='utf-8')).items()}


def _dette_2035(mesures, levier, param, x):
    m = {**mesures, levier: {**(mesures.get(levier) or {}), param: x}}
    df, _, _ = BudgetSimulatorV45(periods=10, mesures=m).simulate()
    return float(df['Dette/PIB %'].iloc[-1])


@pytest.mark.parametrize('sid,levier,param,x,lo,hi', POINTS_DE_SAUT,
                         ids=[f'{p[0]}-{p[1]}.{p[2]}@{p[3]:.4g}' for p in POINTS_DE_SAUT])
def test_variation_infinitesimale_ne_deplace_pas_la_dette(sid, levier, param, x, lo, hi):
    mesures = _scenarios()[sid]
    d = 1e-7 * (hi - lo)  # > largeur de la bissection (1e-9 × plage) : le saut est dedans
    ecart = _dette_2035(mesures, levier, param, x + d) - _dette_2035(mesures, levier, param, x - d)
    assert abs(ecart) < EPSILON_PT, (
        f"{sid} {levier}.{param} = {x:.6g} ± {d:.1e} : dette 2035 déplacée de {ecart:+.4f} pt")
