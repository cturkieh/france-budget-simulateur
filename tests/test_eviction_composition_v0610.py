"""Éviction (« crowding-out ») et composition de l'expansion (v0.6.10, contre-audit
externe V2-01 — ``engine/orchestrator.py`` / ``engine/growth.py``).

Constat de l'auditeur (v0.6.7, reproduit au millième sur v0.6.9) : la part
d'investissement lue par l'éviction divisait des flux BRUTS par levier
(Σ |Δdép| des leviers d'investissement) par des flux NETS agrégés
(|Δdép net| + |Δrec net|). Ce n'était pas une part : un investissement financé
en partie par une coupe la portait au-dessus de 1, et l'intensité
``0,002 + (1 − part) × 0,006`` devenait NÉGATIVE — multipliée par un effort
négatif, l'« éviction » SOUTENAIT l'expansion.

- Contre-exemple, entièrement dans les domaines admis : +20 Md€
  d'investissement de transition, dotation des collectivités 120 → 110
  (−10 Md€). Part 2027 = 20 / 10 = 2,000 ; effet 2027 = +0,001303 pt de
  croissance.
- Programme publié IM Compétitivité : part 2,280 en 2027 (effort négatif,
  effet +0,001454 pt), 2,605 au maximum.

Contrat verrouillé ici : la part est une part (dans [0 ; 1]) et l'éviction ne
soutient jamais une expansion.
"""
import json
import os
from pathlib import Path

import pytest

from budget_simulator.simulator import BudgetSimulatorV45

CONTRE_EXEMPLE = {
    'transition_ecologique': {'investissement': 20},
    'collectivites': {'dotation': 110},
}
IDX_2027 = 2  # année 2027 = indice 2 de la boucle (2025 = base, indice 0)


def _scenarios():
    chemin = (os.environ.get('BUDGETLAB_SCENARIOS_JSON') or '').strip()
    if not chemin or not Path(chemin).exists():
        pytest.skip("scenarios.json introuvable (fork moteur public seul)")
    return {k: v['apiMeasures'] for k, v in json.loads(Path(chemin).read_text(encoding='utf-8')).items()}


def _simuler(mesures):
    """Simulation complète ; renvoie, par indice d'année, l'état macro passé à
    ``calculate_growth`` et les impacts par levier rendus par ``apply_measures``."""
    sim = BudgetSimulatorV45(periods=10, mesures=mesures)
    croissance, appliquer = sim.calculate_growth, sim.apply_measures
    etats, impacts = {}, {}

    def espion_croissance(year, etat):
        etats[year] = dict(etat)
        return croissance(year, etat)

    def espion_mesures(year, *args, **kwargs):
        dep, rec, imp = appliquer(year, *args, **kwargs)
        impacts[year] = {m: dict(v) for m, v in imp.items() if isinstance(v, dict)}
        return dep, rec, imp

    sim.calculate_growth, sim.apply_measures = espion_croissance, espion_mesures
    sim.simulate()
    return etats, impacts


def _effet_eviction(etat):
    """Points de croissance dus à l'éviction du moteur dans l'état ``etat`` :
    croissance d'un simulateur frais SANS impulsion stockée à l'effort de l'état,
    MOINS la même à effort nul. À effort négatif, la cicatrice (effort > 3 %)
    est éteinte : la seule différence est le terme d'éviction."""
    assert etat['effort_budgetaire'] < 0

    def croissance(effort):
        sim = BudgetSimulatorV45(periods=10, mesures={})
        sim._last_impacts = {}
        return sim.calculate_growth(IDX_2027, dict(etat, effort_budgetaire=effort))
    return (croissance(etat['effort_budgetaire']) - croissance(0.0)) * 100


# ---------------------------------------------------------------------------
# Reproduction du contre-audit (V2-01)
# ---------------------------------------------------------------------------

def test_contre_exemple_flux_initiaux():
    """Le contre-exemple est bien celui de l'auditeur : +20 Md€ d'investissement,
    −10 Md€ de dotations, rien d'autre (budget 2026, lu par la macro de 2027)."""
    _, impacts = _simuler(CONTRE_EXEMPLE)
    imp = impacts[2026]
    assert round(imp['transition_ecologique']['depenses'], 3) == 20.0
    assert round(imp['collectivites']['depenses'], 3) == -10.0
    autres = {m: v for m, v in imp.items() if m not in CONTRE_EXEMPLE
              and (abs(v.get('depenses', 0) or 0) > 1e-9 or abs(v.get('recettes', 0) or 0) > 1e-9)}
    assert not autres, autres


def test_contre_exemple_part_est_une_part():
    etats, _ = _simuler(CONTRE_EXEMPLE)
    part = etats[IDX_2027]['part_investissement']
    assert 0.0 <= part <= 1.0, f"part d'investissement 2027 = {part:.3f} (hors [0 ; 1])"


def test_contre_exemple_eviction_ne_soutient_pas_l_expansion():
    etats, _ = _simuler(CONTRE_EXEMPLE)
    etat = etats[IDX_2027]
    assert etat['effort_budgetaire'] < 0 and etat['debt_ratio'] > 1.0  # éviction active
    effet = _effet_eviction(etat)
    assert effet <= 0.0, (
        f"éviction 2027 = {effet:+.6f} pt de croissance (part {etat['part_investissement']:.3f}, "
        f"effort {etat['effort_budgetaire']:+.5f}) : elle SOUTIENT l'expansion")


def test_im_competitivite_part_est_une_part_chaque_annee():
    etats, _ = _simuler(_scenarios()['im_competitivite_2029'])
    parts = {2025 + i: float(e['part_investissement']) for i, e in etats.items()}
    hors = {a: round(p, 3) for a, p in parts.items() if not 0.0 <= p <= 1.0}
    assert not hors, f"parts hors [0 ; 1] : {hors} (max {max(parts.values()):.3f})"


def test_im_competitivite_eviction_ne_soutient_pas_l_expansion_2027():
    etats, _ = _simuler(_scenarios()['im_competitivite_2029'])
    etat = etats[IDX_2027]
    assert etat['effort_budgetaire'] < 0 and etat['debt_ratio'] > 1.0  # éviction active
    effet = _effet_eviction(etat)
    assert effet <= 0.0, (
        f"éviction 2027 = {effet:+.6f} pt de croissance (part {etat['part_investissement']:.3f}, "
        f"effort {etat['effort_budgetaire']:+.5f}) : elle SOUTIENT l'expansion")
