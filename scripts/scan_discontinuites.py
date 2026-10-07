#!/usr/bin/env python3
"""
Scanner de DISCONTINUITÉS du moteur (v0.6.7, lot 3b).

Propriété visée : une variation infinitésimale d'un paramètre ne déplace jamais
la dette 2035 de plus de ε. Chaque paramètre de ``PARAM_DOMAINS`` est balayé sur
tout son domaine (N points) dans chaque scénario publié ; tout intervalle dont
l'écart de dette 2035 détonne par rapport à ses voisins est réduit par
bissection jusqu'à une largeur de 1e-9 × plage. Un saut qui SURVIT à la
bissection est une discontinuité ; une pente raide s'évanouit.

Heuristique de repérage, pas une preuve : un saut noyé dans une variation
régulière plus forte que lui sur le même intervalle peut échapper au repérage.
Les sauts réels trouvés sont figés en tests (tests/test_continuite_regimes_v067.py).
Les interrupteurs 0/1 (``DRAPEAUX``) sont exclus : leur saut est le levier lui-même.

Usage :
  python3 scripts/scan_discontinuites.py [--points N] [--scenarios a,b] [--json sortie.json]
Scénarios : ``BUDGETLAB_SCENARIOS_JSON`` ou frontend-react/src/data/scenarios.json.
Sortie : un saut par ligne (scénario, levier.paramètre, position, saut de dette
2035, première année où l'état macro diverge) ; code retour 1 si un saut
dépasse ``--seuil`` (0,001 pt par défaut).
"""

import argparse
import json
import logging
import os
import sys
from multiprocessing import Pool
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

DRAPEAUX = {'progressive', 'reforme_active', 'exclure_defense', 'exclure_ue',
            'asu_activation', 'degressivite'}


def _scenarios():
    env = (os.environ.get('BUDGETLAB_SCENARIOS_JSON') or '').strip()
    chemin = Path(env) if env else REPO_ROOT / 'frontend-react' / 'src' / 'data' / 'scenarios.json'
    if not chemin.exists():
        sys.exit(f'scenarios.json introuvable ({chemin}) : poser BUDGETLAB_SCENARIOS_JSON')
    return {k: v['apiMeasures'] for k, v in json.loads(chemin.read_text(encoding='utf-8')).items()}


def _simuler(mesures):
    from budget_simulator.simulator import BudgetSimulatorV45
    df, d2, _ = BudgetSimulatorV45(periods=10, mesures=mesures).simulate()
    return df, d2


def _avec(mesures, levier, param, x):
    return {**mesures, levier: {**(mesures.get(levier) or {}), param: x}}


def _dette(mesures):
    return float(_simuler(mesures)[0]['Dette/PIB %'].iloc[-1])


def pleine_precision():
    """Sorties pleine précision : l'arrondi d'affichage de l'orchestrateur créerait
    de faux sauts de 0,01 pt. Effet global : à n'appeler que dans un processus de
    balayage (le test, lui, passe par monkeypatch)."""
    import budget_simulator.engine.orchestrator as orch
    orch.round = lambda x, nd=None: float(x)


def _balayer(args):
    logging.disable(logging.WARNING)
    pleine_precision()
    return balayer(*args)


def balayer(mesures, sid, levier, param, lo, hi, n):
    """Balaye un paramètre sur [lo ; hi] en n points ; renvoie les sauts survivant à
    la bissection (tous, sans seuil). Suppose les sorties en pleine précision."""
    xs = [lo + (hi - lo) * i / (n - 1) for i in range(n)]
    ds = [_dette(_avec(mesures, levier, param, x)) for x in xs]
    deltas = [b - a for a, b in zip(ds, ds[1:])]
    mediane = sorted(abs(d) for d in deltas)[len(deltas) // 2]
    sauts = []
    for i, d in enumerate(deltas):
        voisins = [abs(deltas[j]) for j in (i - 1, i + 1) if 0 <= j < len(deltas)]
        if not (abs(d) > 4 * mediane + 0.005 and abs(d) > 2.5 * max(voisins + [0.0])):
            continue
        a, b, da, db = xs[i], xs[i + 1], ds[i], ds[i + 1]
        while b - a > 1e-9 * max(1.0, hi - lo):
            c = (a + b) / 2
            dc = _dette(_avec(mesures, levier, param, c))
            if abs(dc - da) >= abs(db - dc):
                b, db = c, dc
            else:
                a, da = c, dc
        dfa, d2a = _simuler(_avec(mesures, levier, param, a))
        dfb, d2b = _simuler(_avec(mesures, levier, param, b))
        divergence = None
        for k in range(1, len(dfa)):
            etat_a = (d2a['Output_Gap %'].iloc[k], dfa['Croissance %'].iloc[k], dfa['Inflation %'].iloc[k], dfa['Chômage %'].iloc[k])
            etat_b = (d2b['Output_Gap %'].iloc[k], dfb['Croissance %'].iloc[k], dfb['Inflation %'].iloc[k], dfb['Chômage %'].iloc[k])
            if any(abs(u - v) > 1e-7 for u, v in zip(etat_a, etat_b)):
                divergence = (int(dfa['Année'].iloc[k]), [round(float(u), 4) for u in etat_a],
                              [round(float(v), 4) for v in etat_b])
                break
        sauts.append({'scenario': sid, 'parametre': f'{levier}.{param}', 'x': (a + b) / 2,
                      'plage': (lo, hi), 'saut_dette_2035': db - da, 'divergence': divergence})
    return sauts


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--points', type=int, default=41)
    ap.add_argument('--scenarios', default='')
    ap.add_argument('--json', default='')
    ap.add_argument('--seuil', type=float, default=1e-3)
    opts = ap.parse_args()
    from budget_simulator.engine._param_domain import PARAM_DOMAINS
    scen = _scenarios()
    if opts.scenarios:
        scen = {k: scen[k] for k in opts.scenarios.split(',')}
    travaux = [(m, sid, levier, param, float(lo), float(hi), opts.points)
               for sid, m in scen.items() for levier, dom in PARAM_DOMAINS.items()
               for param, (lo, hi) in dom.items() if param not in DRAPEAUX]
    with Pool() as pool:
        sauts = [s for lot in pool.map(_balayer, travaux, chunksize=4) for s in lot]
    sauts = [s for s in sauts if abs(s['saut_dette_2035']) > opts.seuil]
    for s in sorted(sauts, key=lambda s: -abs(s['saut_dette_2035'])):
        print(f"{s['scenario']:<22} {s['parametre']:<42} @ {s['x']:<12.6g} "
              f"{s['saut_dette_2035']:+.4f} pt   1re divergence (année, gap, g, π, u) : {s['divergence']}")
    print(f'{len(travaux)} balayages × {opts.points} points : {len(sauts)} saut(s) > {opts.seuil} pt')
    if opts.json:
        Path(opts.json).write_text(json.dumps(sauts, indent=1, ensure_ascii=False), encoding='utf-8')
    return 1 if sauts else 0


if __name__ == '__main__':
    sys.exit(main())
