"""Tests-propriétés de l'assemblage Gini.

Lot 4 (méthode unique ; arbitrage du mainteneur) : l'indice publié de l'année
vaut la base plus la somme des effets émis jusqu'à elle (facteur
GINI_IMPACT_SCALE = 1,0), bornée par [GINI_SOFT_FLOOR ; GINI_HARD_CEILING]
(engine/orchestrator.py, « Calcul Gini centralisé »). La convergence de 35 %
par an et l'amortissement des baisses près du plancher (v0.4.0), sans source,
sont retirés ; la garde de vitesse annuelle (|ΔGini| ≤ 0,01) qui allait avec
devient une limite déclarée (METHODOLOGIE, « Assemblage du Gini ») : l'effet
d'une mesure arrive en entier l'année où elle s'applique.

Propriétés verrouillées :

  (a) le clip dur ne mord JAMAIS : Gini strictement > 0,25 sur tout l'horizon,
      pour tous les scénarios politiques — la saturation (deux programmes
      affichant le même plancher) est l'anti-objectif n°1 ;
  (b) retirée au lot 4 (vitesse annuelle : limite déclarée, voir plus haut) ;
  (c) classement préservé : LFI < PS < RN en 2030 (programmes redistributifs,
      par ampleur) et im_rabot ≥ statu quo (consolidation régressive) — le
      réalisme ne doit pas réordonner les programmes, seulement les ramener
      à des amplitudes défendables ;
  (d) statu quo inerte : 0 levier → Gini = GINI_BASE constant ;
  (e) ancrage (re-déclaré au lot 4) : deux programmes redistributifs figés,
      A plus redistributif que B, réduisent l'indice (A < B < base en 2030) et
      restent distincts à 3 décimales (la résolution d'affichage du
      comparateur) ; la CIBLE non plafonnée de A (avant les bornes de
      sécurité) réduit l'indice d'au plus la réduction que produit le système entier des
      transferts du champ de l'INSEE (V = 0,0923, France, portrait social
      2025, fiche « Redistribution monétaire », figure 2) ; et, à travers
      l'assemblage, un Md€ de prestations ciblées pesé sur leur masse publiée
      retrouve l'ordre de leur contribution publiée (figure 2 : 0,0551), à
      l'écart près entre effet marginal et effet moyen. Programmes figés depuis
      la release de paramètres P (v0.8.1), voir
      ``tests/snapshots/programmes_figes_gini_v040.json``.

Jusqu'au lot 4, (e) exigeait A ∈ [0,255 ; 0,275] en 2030, d'après « IPP/OFCE
2022 : un programme de 5-10 % du PIB ≈ −0,015 à −0,035 de Gini » — un chiffre
dont le passage n'a pas été retrouvé, et qui justifiait à lui seul le facteur
d'atténuation 0,22. Depuis la méthode unique (constants.py § CANAUX GINI), les
coefficients sont physiques et bornés un par un (garde de CI des coefficients
par Md€) : l'ancrage porte sur deux grandeurs publiées, la réduction V (sur la
cible non plafonnée, que le plancher dur ne peut pas masquer) et la contribution
des prestations (à travers l'assemblage, facteur d'atténuation compris).
"""
import sys
from pathlib import Path

import pytest

from budget_simulator.simulator import BudgetSimulatorV45
from budget_simulator.constants import GINI_BASE, GINI_REDUCTION_VERTICALE_FPS2025, GINI_SOFT_FLOOR

SNAPSHOTS_DIR = Path(__file__).parent / 'snapshots'
sys.path.insert(0, str(SNAPSHOTS_DIR))
from run_scenarios_full import SCENARIOS, pour_le_mode  # noqa: E402

# Ancrage (e) : deux programmes FIGÉS (release de paramètres P, 12/11/2026), pour
# que la calibration ne dépende pas d'un ré-encodage de leurs sources.
PROGRAMMES_FIGES = SNAPSHOTS_DIR / 'programmes_figes_gini_v040.json'

YEAR_IDX_2030 = 5
# Le clip dur de l'orchestrator vaut GINI_SOFT_FLOOR par design (plancher
# asymptotique = filet) — importer la constante évite une valeur fantôme ici.
HARD_FLOOR = GINI_SOFT_FLOOR


@pytest.fixture(scope='module')
def ginis():
    """Trajectoires Gini (11 ans) de chaque scénario politique, simulées une fois."""
    out = {}
    for name, mesures in SCENARIOS.items():
        # Mode historique : mesures telles que le mode les accepte (release P).
        df, _, _ = BudgetSimulatorV45(periods=10, mesures=pour_le_mode(mesures)).simulate()
        out[name] = [float(v) for v in df['Gini'].tolist()]
    return out


def _gini_2030_fige(cle):
    import json
    mesures = json.loads(PROGRAMMES_FIGES.read_text(encoding='utf-8'))[cle]
    df, _, _ = BudgetSimulatorV45(periods=10, mesures=mesures).simulate()
    return float(df['Gini'].iloc[YEAR_IDX_2030])


def _cible_finale_figee(cle):
    """Cible cumulée NON plafonnée en fin d'horizon (avant inertie, amortissement
    et clip) : ce que le plancher dur ne peut pas masquer."""
    import json
    mesures = json.loads(PROGRAMMES_FIGES.read_text(encoding='utf-8'))[cle]
    sim = BudgetSimulatorV45(periods=10, mesures=mesures)
    sim.simulate()
    return GINI_BASE + sim.gini_cible_cumul


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


def test_e_ancrage_empirique_et_resolution():
    """Programmes redistributifs figés A et B, 2030 : A < B < base, A ≠ B à la
    résolution d'affichage ; la cible non plafonnée de A réduit l'indice d'au
    plus V (système entier des transferts du champ INSEE). Release de
    paramètres P : deux programmes FIGÉS (``programmes_figes_gini_v040.json``),
    publiés jusqu'à v0.8.0 : le test vérifie la calibration du moteur, pas un
    encodage qui suit ses sources. Pouvoir mesuré : la borne V sur la cible
    rougit dès que l'ensemble des émissions est multiplié par environ 6 ; la
    contribution publiée (test suivant) rougit dès un facteur 1,6."""
    a = _gini_2030_fige('programme_a')
    b = _gini_2030_fige('programme_b')
    assert a < b < GINI_BASE, (
        f"programmes figés : A={a:.4f}, B={b:.4f}, base={GINI_BASE} — attendu A < B < base"
    )
    cible_a = _cible_finale_figee('programme_a')
    assert GINI_BASE - cible_a <= GINI_REDUCTION_VERTICALE_FPS2025, (
        f"programme figé A : cible non plafonnée {cible_a:.4f}, réduction {GINI_BASE - cible_a:.4f} "
        f"supérieure à celle du système entier des transferts du champ INSEE ({GINI_REDUCTION_VERTICALE_FPS2025})"
    )
    assert round(a, 3) != round(b, 3), (
        f"programmes figés A et B indistincts à 3 décimales (A={a:.4f}, B={b:.4f}) — "
        "l'écart entre programmes est de nouveau écrasé"
    )


def test_e_contribution_publiee_des_prestations_a_travers_l_assemblage():
    """INSEE, France, portrait social 2025, figure 2 : les prestations (A = 5,8 %
    du niveau de vie, B = 9,5) contribuent pour |A × B| / 1000 = 0,0551 à la
    réduction de l'indice. Un Md€ de prestations ciblées versé par le levier,
    lu sur la cible de l'assemblage (facteur d'atténuation compris), × leur
    masse publiée (A × Y) doit retrouver cet ordre : entre 60 % et 120 % (effet
    marginal au classement final contre effet moyen ; mesuré : 76 %). Un
    facteur global ×0,22 donnerait 17 %, un facteur ×2, 152 %."""
    from budget_simulator.constants import INSEE_FPS2025_REDISTRIBUTION, MASSE_NIVEAUX_DE_VIE_MD_EUR
    sim = BudgetSimulatorV45(periods=10, mesures={'prestations_menages': {'solidarite': 10.0}})
    sim.simulate()
    par_md = -sim.gini_cible_cumul / 10.0
    a, b = INSEE_FPS2025_REDISTRIBUTION['prestations']
    contribution = a * b / 1000
    effet = par_md * a / 100 * MASSE_NIVEAUX_DE_VIE_MD_EUR
    assert 0.6 * contribution <= effet <= 1.2 * contribution, (effet, contribution)
