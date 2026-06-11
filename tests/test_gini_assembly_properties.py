"""Tests-propriétés de l'assemblage Gini (v0.4.0 — réalisme empirique).

Contrat introduit avec le triptyque rescale + inertie + plancher asymptotique
(constants.py : GINI_IMPACT_SCALE / GINI_CONVERGENCE_RATE / GINI_SOFT_FLOOR ;
application : engine/orchestrator.py, « Calcul Gini centralisé »). Avant lui,
la somme brute des sensibilités par mesure sur-réagissait (~×4 vs
microsimulations IPP/OFCE 2022) et saturait le clip dur 0,25 dès 2027 pour
LFI ET PS — même valeur affichée, écart entre programmes écrasé.

Propriétés verrouillées :

  (a) le clip dur ne mord JAMAIS : Gini strictement > 0,25 sur tout l'horizon,
      pour tous les scénarios politiques — la saturation (deux programmes
      affichant le même plancher) est l'anti-objectif n°1 ;
  (b) vitesse réaliste : |ΔGini| ≤ 0,01/an (série INSEE 25 ans : jamais
      dépassé, même ISF→PFU 2018 ≈ ±0,005) ;
  (c) classement préservé : LFI < PS < RN en 2030 (programmes redistributifs,
      par ampleur) et im_rabot ≥ statu quo (consolidation régressive) — le
      réalisme ne doit pas réordonner les programmes, seulement les ramener
      à des amplitudes défendables ;
  (d) statu quo inerte : 0 levier → Gini = GINI_BASE constant (pas de dérive
      du mécanisme de convergence à cible nulle) ;
  (e) ancrage empirique : LFI 2030 dans [0,255 ; 0,275] (IPP/OFCE : un
      programme de 5-10 % du PIB ≈ −0,015 à −0,035 de Gini), et LFI/PS
      distincts à 3 décimales (la résolution d'affichage du comparateur).

Si un recalibrage des sensibilités handlers fait rougir (e), c'est un
recalibrage de GINI_IMPACT_SCALE qu'il faut discuter — pas un élargissement
des bornes : elles encodent la littérature, pas l'implémentation.
"""
import sys
from pathlib import Path

import pytest

from budget_simulator.simulator import BudgetSimulatorV45
from budget_simulator.constants import GINI_BASE, GINI_SOFT_FLOOR

SNAPSHOTS_DIR = Path(__file__).parent / 'snapshots'
sys.path.insert(0, str(SNAPSHOTS_DIR))
from run_scenarios_full import SCENARIOS  # noqa: E402

YEAR_IDX_2030 = 5
# Le clip dur de l'orchestrator vaut GINI_SOFT_FLOOR par design (plancher
# asymptotique = filet) — importer la constante évite une valeur fantôme ici.
HARD_FLOOR = GINI_SOFT_FLOOR
MAX_ANNUAL_STEP = 0.01


@pytest.fixture(scope='module')
def ginis():
    """Trajectoires Gini (11 ans) de chaque scénario politique, simulées une fois."""
    out = {}
    for name, mesures in SCENARIOS.items():
        df, _, _ = BudgetSimulatorV45(periods=10, mesures=mesures).simulate()
        out[name] = [float(v) for v in df['Gini'].tolist()]
    return out


@pytest.mark.skipif(not SCENARIOS, reason="scenarios.json absent (fork moteur seul)")
def test_a_clip_dur_jamais_atteint(ginis):
    """Aucun scénario ne touche le plancher dur — la saturation est impossible."""
    violations = [
        f"{name} : min={min(traj):.4f}" for name, traj in ginis.items()
        if min(traj) <= HARD_FLOOR
    ]
    assert not violations, (
        "Le clip dur 0,25 a mordu (saturation = écart entre programmes écrasé) : "
        + " ; ".join(violations)
    )


@pytest.mark.skipif(not SCENARIOS, reason="scenarios.json absent (fork moteur seul)")
def test_b_vitesse_annuelle_realiste(ginis):
    """|ΔGini| ≤ 0,01/an — la distribution des revenus a une inertie (INSEE, 25 ans)."""
    violations = []
    for name, traj in ginis.items():
        for i in range(1, len(traj)):
            step = abs(traj[i] - traj[i - 1])
            if step > MAX_ANNUAL_STEP + 1e-9:
                violations.append(f"{name} Y{i} : Δ={step:.4f}")
    assert not violations, (
        f"Pas annuel Gini > {MAX_ANNUAL_STEP} : " + " ; ".join(violations)
    )


@pytest.mark.skipif(not SCENARIOS, reason="scenarios.json absent (fork moteur seul)")
def test_c_classement_2030_preserve(ginis):
    """LFI < PS < RN (redistribution décroissante) ; rabot ≥ statu quo (régressif)."""
    g = {name: traj[YEAR_IDX_2030] for name, traj in ginis.items()}
    assert g['lfi_2027'] < g['ps_2027'] < g['rn_2027'], (
        f"Classement redistributif inversé : LFI={g['lfi_2027']:.4f} "
        f"PS={g['ps_2027']:.4f} RN={g['rn_2027']:.4f}"
    )
    if 'im_rabot_2029' in g and 'plf_2026' in g:
        assert g['im_rabot_2029'] >= g['plf_2026'] - 1e-9, (
            f"Le rabot (régressif) passe sous le statu quo : "
            f"rabot={g['im_rabot_2029']:.4f} < plf={g['plf_2026']:.4f}"
        )


def test_d_statu_quo_inerte():
    """0 levier → cible = base → le mécanisme de convergence ne crée AUCUNE dérive."""
    df, _, _ = BudgetSimulatorV45(periods=10, mesures={}).simulate()
    traj = [float(v) for v in df['Gini'].tolist()]
    assert all(abs(v - GINI_BASE) < 1e-12 for v in traj), (
        f"Statu quo : Gini dérive sans mesure ({traj})"
    )


def test_f_reentrance_sans_fuite_etat():
    """simulate() ×2 sur la même instance → trajectoires identiques.

    Le couple (gini_courant, gini_cible_cumul) est ré-initialisé par
    _reset_state() en tête de simulate() ; un futur oubli dans _reset_state
    ferait fuiter la cible du run précédent SILENCIEUSEMENT (l'API crée une
    instance par requête, donc seul ce test peut l'attraper).
    """
    mesures = {'csg': {'taux': 0.097, 'progressive': 1}}
    sim = BudgetSimulatorV45(periods=10, mesures=mesures)
    df1, _, _ = sim.simulate()
    df2, _, _ = sim.simulate()
    assert df1['Gini'].tolist() == df2['Gini'].tolist(), (
        "Fuite d'état Gini entre deux simulate() sur la même instance"
    )


@pytest.mark.skipif(not SCENARIOS, reason="scenarios.json absent (fork moteur seul)")
def test_e_ancrage_empirique_et_resolution(ginis):
    """LFI 2030 dans la fourchette IPP/OFCE ; LFI ≠ PS à la résolution d'affichage."""
    lfi = ginis['lfi_2027'][YEAR_IDX_2030]
    ps = ginis['ps_2027'][YEAR_IDX_2030]
    assert 0.255 <= lfi <= 0.275, (
        f"LFI 2030 = {lfi:.4f} hors fourchette empirique [0,255 ; 0,275] "
        "(IPP/OFCE : programme 5-10 % PIB ≈ −0,015 à −0,035 de Gini)"
    )
    assert round(lfi, 3) != round(ps, 3), (
        f"LFI et PS indistincts à 3 décimales (LFI={lfi:.4f}, PS={ps:.4f}) — "
        "l'écart entre programmes est de nouveau écrasé"
    )
