"""Mesure contrefactuelle — branche d'élasticité inflation→recettes (ARCHIVE).

⚠️ ARCHIVE HISTORIQUE (2026-05-16) : la branche d'élasticité analysée par ce
script a depuis été SUPPRIMÉE du moteur (Phase 2, option B — double-comptage
avec l'élasticité au PIB nominal de `calculate_revenues`). Ce script est
conservé tel quel car il documente la mesure d'impact qui a justifié la
décision (Dette/PIB ~ -0,26 pt moyen, max -0,36 pt si réactivée). Il ne
tourne plus contre le code de production (le monkeypatch `REACTIVE` reste
valide ; le mode `BASELINE` reflète désormais l'état courant = branche
absente, et non plus « branche morte »). Voir docs/REFACTOR_SPLIT_PLAN.md.

Compare, sur les 8 scénarios politiques (mêmes apiMeasures que le golden master),
deux variantes du moteur :

  BASELINE   : code d'origine = branche morte par construction
               (`calculate_inflation` réécrivait `self.inflation_precedente`
                avec la valeur courante AVANT le garde → `abs(X - X) > 0.0005`
                jamais vrai). Depuis la suppression Phase 2, ce mode reflète
                l'état courant (branche absente).

  REACTIVE   : option A (NON retenue) = la branche s'exécuterait correctement.
               On neutralise UNIQUEMENT l'écriture in-méthode de
               `calculate_inflation`. `self.inflation_precedente` reste donc
               égal à l'inflation N-1 jusqu'au garde, qui compare alors I_n vs
               I_{n-1} (vraie surprise d'inflation). La persistance
               inter-années est assurée par `simulate()` (fin de boucle
               annuelle, inchangé). C'est exactement le "déplacement de
               l'écriture in-méthode" évoqué par la re-analyse adverse
               2026-05-16.

Le monkeypatch porte sur l'attribut de CLASSE `InflationMixin.calculate_inflation`
(global au process, PAS local) ; `main()` le restaure systématiquement via
`try/finally`. Aucune modification de fichier source.

Usage:
    python3 tests/instrumentation/counterfactual_inflation_elasticity.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from budget_simulator.simulator import BudgetSimulatorV45
from budget_simulator.engine.inflation import InflationMixin
from tests.snapshots.run_scenarios_full import SCENARIOS

_ORIG_CALC_INFLATION = InflationMixin.calculate_inflation


def _calc_inflation_no_inmethod_write(self, year, economic_state):
    """calculate_inflation SANS l'écriture in-méthode de inflation_precedente.

    On capture la valeur d'entrée et on la restaure après l'appel original :
    le garde (ex-orchestrator) verrait alors I_{n-1} (genuine), pas I_n.
    """
    prev = self.inflation_precedente
    result = _ORIG_CALC_INFLATION(self, year, economic_state)
    self.inflation_precedente = prev  # annule l'écriture in-méthode
    return result


COLS = ['Dette/PIB %', 'Déficit/PIB %', 'Croissance %', 'Inflation %',
        "Pouvoir d'Achat", 'Chômage %']


def run(mesures, reactive: bool):
    if reactive:
        InflationMixin.calculate_inflation = _calc_inflation_no_inmethod_write
    else:
        InflationMixin.calculate_inflation = _ORIG_CALC_INFLATION
    sim = BudgetSimulatorV45(periods=10, mesures=mesures)
    df, _, _ = sim.simulate()
    return {c: [float(v) if v is not None else None for v in df[c].tolist()]
            for c in COLS if c in df.columns}


def main():
    print(f"{'Scénario':<22} {'Métrique':<14} {'2029 base':>10} {'2029 A':>10} "
          f"{'Δ2029':>9} {'2035 base':>10} {'2035 A':>10} {'Δ2035':>9} {'Δmax|an':>9}")
    print("-" * 110)

    Y2029, Y2035 = 4, 10  # year_idx : 2025=0 ... 2035=10
    agg = {}

    try:
        for name, mesures in SCENARIOS.items():
            base = run(mesures, reactive=False)
            reac = run(mesures, reactive=True)

            for metric in ['Dette/PIB %', 'Déficit/PIB %', 'Croissance %', "Pouvoir d'Achat"]:
                if metric not in base or metric not in reac:
                    continue
                b, r = base[metric], reac[metric]
                deltas = [(r[i] - b[i]) for i in range(len(b))
                          if b[i] is not None and r[i] is not None]
                dmax = max(deltas, key=abs) if deltas else 0.0
                agg.setdefault(metric, []).append(abs(dmax))
                print(f"{name:<22} {metric:<14} "
                      f"{b[Y2029]:>10.3f} {r[Y2029]:>10.3f} {r[Y2029]-b[Y2029]:>+9.3f} "
                      f"{b[Y2035]:>10.3f} {r[Y2035]:>10.3f} {r[Y2035]-b[Y2035]:>+9.3f} "
                      f"{dmax:>+9.3f}")
            print()

        print("=" * 110)
        print("SYNTHÈSE — écart absolu max par métrique (pire scénario, toutes années)")
        for metric, vals in agg.items():
            print(f"  {metric:<16} : max |Δ| = {max(vals):.3f}  | moyenne = {sum(vals)/len(vals):.3f}")
    finally:
        # Restaure l'attribut de CLASSE patché par run() (global au process).
        InflationMixin.calculate_inflation = _ORIG_CALC_INFLATION


if __name__ == "__main__":
    main()
