"""Tests-propriétés de la passe v0.6.7 « handlers » (audit externe Codex Astra, 10/2026).

Chaque constat est d'abord reproduit par un test qui échouait sur v0.6.6 (le chiffre
de l'audit est cité dans la docstring), puis verrouillé par une propriété durable.

Lot 1 — effet chômage direct réémis chaque année (bloc A, constat 5).
  ``engine/unemployment.py`` ajoute ``impacts['chomage']`` à l'état AVANT la
  convergence NAIRU (u = 0,94·u + 0,06·nairu) : un terme réémis chaque année y
  converge vers 0,94/0,06 ≈ 15,7 fois sa valeur. Or le code décrit un effet de
  NIVEAU, et tous les autres émetteurs de la clé sont gatés une seule fois
  (``_is_first_year_change`` ou ``_one_time_level``). Deux handlers échappaient à
  la règle : ``cotisations_salariales`` (1 pt : −0,065 pt de chômage en 2027,
  −0,203 en 2030, −0,327 en 2034, au lieu d'un effet de niveau de 0,05 pt) et
  ``rabot_uniforme`` (même motif, repéré par l'inventaire des émetteurs).
"""
import pytest

import budget_simulator.engine.orchestrator as _orchestrator
from budget_simulator.simulator import BudgetSimulatorV45

# Coefficients DÉCLARÉS par les handlers (effet de niveau annoncé) — lus ici pour
# borner l'effet direct, pas pour le recalculer.
NIVEAU_COTIS_SAL_PAR_POINT = 0.0005      # fiscalite_menages._apply_cotisations_salariales
NIVEAU_RABOT_PAR_POINT_DE_TAUX = 0.004   # montaigne._apply_rabot_uniforme


@pytest.fixture
def pleine_precision(monkeypatch):
    """Les colonnes publiées sont arrondies à 0,01 : un écart de deux séries arrondies
    porte ±0,01 pt de bruit, du même ordre que les niveaux testés. Le ``round`` de
    l'orchestrateur ne sert qu'à la sortie ; on le neutralise pour comparer les
    valeurs calculées."""
    monkeypatch.setattr(_orchestrator, 'round', lambda x, n=None: x, raising=False)


class _SansCanalChomage(BudgetSimulatorV45):
    """Le même moteur, avec le canal chômage DIRECT d'un seul levier coupé.

    L'écart entre une simulation normale et celle-ci isole exactement la part du
    chômage due à ``impacts['chomage']`` de ce levier (Okun et le reste inchangés)."""

    cible = None

    def _apply_complex_measure(self, measure, params, year, gdp, inflation, unemployment):
        ds, dr, impacts = super()._apply_complex_measure(
            measure, params, year, gdp, inflation, unemployment)
        if measure['id'] == self.cible:
            impacts = {k: v for k, v in impacts.items() if k != 'chomage'}
        return ds, dr, impacts


def _chomage(mesures, sans_canal=None):
    cls = BudgetSimulatorV45
    if sans_canal is not None:
        cls = type('_Coupe', (_SansCanalChomage,), {'cible': sans_canal})
    df, _, rapport = cls(periods=10, mesures=mesures).simulate()
    return list(df['Chômage %']), rapport['measure_impacts_by_year']


def _ecart_direct(measure_id, mesures):
    """Part du chômage (en points) due au seul canal direct du levier, année par année."""
    avec, _ = _chomage(mesures)
    sans, _ = _chomage(mesures, sans_canal=measure_id)
    return [a - s for a, s in zip(avec, sans)]


@pytest.mark.parametrize('points', [1.0, 2.5])
def test_lot1_cotisations_salariales_effet_direct_borne_par_le_niveau(points, pleine_precision):
    """RED v0.6.6 : à 1 pt, l'effet direct atteignait −0,3 pt en 2034 (6× le niveau
    déclaré de 0,05 pt), à 2,5 pts −0,8 pt. Un effet de niveau émis une fois ne
    peut pas dépasser ce niveau (la convergence NAIRU le ramène ensuite vers 0)."""
    niveau_pt = NIVEAU_COTIS_SAL_PAR_POINT * points * 100
    ecart = _ecart_direct('cotisations_salariales',
                          {'cotisations_salariales': {'baisse_points': points}})
    assert max(abs(e) for e in ecart) <= niveau_pt * 1.02, (
        f"effet direct max {max(abs(e) for e in ecart):.3f} pt > niveau déclaré {niveau_pt:.3f} pt")
    assert ecart[2] < 0, "le canal doit exister (baisse du chômage l'année qui suit l'entrée)"


def test_lot1_rabot_effet_direct_borne_par_le_niveau(pleine_precision):
    """Même motif que les cotisations salariales dans ``_apply_rabot_uniforme`` :
    0,004 × taux réémis chaque année (8 % : effet direct ~0,5 pt au lieu de 0,032)."""
    niveau_pt = NIVEAU_RABOT_PAR_POINT_DE_TAUX * 0.08 * 100
    ecart = _ecart_direct('rabot_uniforme', {'rabot_uniforme': {'taux_reduction': 0.08}})
    assert max(abs(e) for e in ecart) <= niveau_pt * 1.02, (
        f"effet direct max {max(abs(e) for e in ecart):.3f} pt > niveau déclaré {niveau_pt:.3f} pt")
    assert ecart[2] > 0


@pytest.mark.parametrize('mesures,measure_id,niveau', [
    ({'cotisations_salariales': {'baisse_points': 2.5}}, 'cotisations_salariales',
     -NIVEAU_COTIS_SAL_PAR_POINT * 2.5),
    ({'rabot_uniforme': {'taux_reduction': 0.08}}, 'rabot_uniforme',
     NIVEAU_RABOT_PAR_POINT_DE_TAUX * 0.08),
])
def test_lot1_effet_de_niveau_emis_une_seule_fois(mesures, measure_id, niveau):
    """Propriété durable : la SOMME des émissions annuelles vaut le niveau déclaré
    (rampe comprise : le rabot monte à 50 % puis 100 %, il émet donc deux
    incréments de moitié, comme l'ASU depuis v0.6.1)."""
    _, par_annee = _chomage(mesures)
    emis = [an.get(measure_id, {}).get('chomage', 0.0) for an in par_annee]
    assert sum(emis) == pytest.approx(niveau, rel=1e-12)


def _cas_couverts():
    import sys
    from pathlib import Path
    snapshots = Path(__file__).parent / 'snapshots'
    sys.path.insert(0, str(snapshots))
    from coverage_scenarios import build_standalone_scenarios
    from run_scenarios_full import SCENARIOS
    cas = {f'standalone:{k}': v for k, v in build_standalone_scenarios().items()}
    cas.update(SCENARIOS)
    return cas


def test_lot1_aucun_emetteur_chomage_recurrent():
    """Inventaire exécutable des émetteurs de ``impacts['chomage']`` : à politique
    constante, plus aucun levier n'émet d'effet chômage direct une fois sa montée en
    charge finie (2030+), sur les 33 mini-scénarios standalone ET les scénarios
    publiés. Un futur handler qui réémettrait chaque année rougit ici."""
    fautifs = {}
    for nom, mesures in _cas_couverts().items():
        _, par_annee = _chomage(mesures)
        for an in par_annee:
            if an['Année'] < 2030:
                continue
            for mid, imp in an.items():
                if mid != 'Année' and isinstance(imp, dict) and imp.get('chomage', 0.0) != 0.0:
                    fautifs.setdefault(nom, set()).add(mid)
    assert not fautifs, f"émission chômage récurrente : {fautifs}"
