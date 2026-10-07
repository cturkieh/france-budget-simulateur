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


# ---------------------------------------------------------------------------
# Lot 1 — assiette de l'IS (bloc B, constat 4).
# ``competitivite._apply_impot_societes`` calculait (taux − 25 %) × assiette_NOUVELLE :
# il manquait la recette perdue au taux de 25 % sur l'assiette qui s'en va. La
# bonne écriture est R(taux) − R(25 %), avec R(t) = t × assiette(t). À PIB 3 000 et
# 35 % : 24,570 Md€ au lieu de 17,745 (chiffres de l'audit, reproduits).
# ---------------------------------------------------------------------------

IS_PART_ASSIETTE_PIB = 0.091            # competitivite.py (DGFiP 2024 : ~62 Md€ à 25 %)
IS_ELASTICITE_HAUSSE, IS_ELASTICITE_BAISSE = -1.0, -0.6
# PIB des propriétés : loin au-dessus du seuil de récession du handler (98 % de
# pib_base), où l'assiette est réduite de 20 % — un état macro, pas la formule.
_GDP_IS = 3300.0


def _delta_is(taux, gdp=_GDP_IS):
    sim = BudgetSimulatorV45(periods=10, mesures={})
    _, recettes, impacts = sim._apply_impot_societes(
        {}, {'taux': taux, 'niches': 0}, 2030, gdp, 0.015, 0.075)
    assert impacts['taux'] == recettes   # niches = 0 : tout vient du taux
    return recettes


def _assiette(taux, gdp=_GDP_IS):
    e = IS_ELASTICITE_HAUSSE if taux > 0.25 else IS_ELASTICITE_BAISSE
    return IS_PART_ASSIETTE_PIB * gdp * (1 + e * (taux - 0.25))


def test_lot1_is_chiffre_de_l_audit():
    """RED v0.6.6 : 24,570 Md€ à 35 % (PIB 3 000) ; attendu 17,745."""
    assert _delta_is(0.35, gdp=3000.0) == pytest.approx(17.745, abs=5e-4)


def test_lot1_is_ancre_dg_tresor_2017():
    """La source que cite le handler : passer de 33 % à 25 % coûte 10 à 12 Md€/an en
    régime stationnaire (DG Trésor 2017). Au PIB 2017 (~2 300 Md€, ordre de grandeur),
    la formule corrigée donne 11,2 ; l'ancienne 15,4, hors de la fourchette. Hors
    récession, l'effet est proportionnel au PIB : on le calcule au PIB des propriétés
    et on le ramène à 2 300 (appeler le handler à 2 300 déclencherait sa branche
    récession, conçue pour un PIB qui chute, pas pour une autre année)."""
    assert 10.0 <= _delta_is(0.33) * 2300.0 / _GDP_IS <= 12.0


@pytest.mark.parametrize('taux', [0.15, 0.20, 0.24, 0.26, 0.27, 0.30, 0.35])
def test_lot1_is_recette_nouvelle_moins_recette_perdue(taux):
    """Décomposition exacte, dans les deux sens : effet statique (Δtaux × assiette
    initiale) + effet de comportement (nouveau taux × variation d'assiette)."""
    b0, b1 = _assiette(0.25), _assiette(taux)
    statique, comportement = (taux - 0.25) * b0, taux * (b1 - b0)
    assert _delta_is(taux) == pytest.approx(statique + comportement, rel=1e-12)
    assert _delta_is(taux) == pytest.approx(taux * b1 - 0.25 * b0, rel=1e-12)


@pytest.mark.parametrize('taux', [0.15, 0.20, 0.24, 0.26, 0.30, 0.35])
def test_lot1_is_le_comportement_reduit_l_effet_dans_les_deux_sens(taux):
    """Symétrie de principe : l'assiette réagit contre le contribuable dans les deux
    sens, donc l'effet réel est PLUS PETIT que l'effet statique, que le taux monte
    ou baisse. L'ancienne formule faisait l'inverse pour une baisse (−17 % à 20 % :
    perte surestimée au-delà de l'effet mécanique)."""
    statique = (taux - 0.25) * _assiette(0.25)
    reel = _delta_is(taux)
    assert reel * statique > 0, "même signe que l'effet statique"
    assert abs(reel) < abs(statique)


def test_lot1_is_monotone_et_continu_en_25():
    """Recette strictement croissante en taux sur le domaine publié [15 % ; 35 %], et
    nulle au taux en vigueur (continuité de part et d'autre de 25 %)."""
    grille = [0.15 + 0.005 * i for i in range(41)]
    deltas = [_delta_is(t) for t in grille]
    assert all(b > a for a, b in zip(deltas, deltas[1:]))
    assert _delta_is(0.25) == 0
    assert abs(_delta_is(0.2501)) < 0.05 and abs(_delta_is(0.2499)) < 0.05
