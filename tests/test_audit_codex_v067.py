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
    # v0.6.7 lot 3 : le canal direct est RETIRÉ (double comptage du canal
    # consommation, que le multiplicateur keynésien applique déjà à la baisse de
    # recettes) — l'écart est nul toutes les années.
    assert all(e == 0.0 for e in ecart), ecart


def test_lot1_rabot_effet_direct_borne_par_le_niveau(pleine_precision):
    """Même motif que les cotisations salariales dans ``_apply_rabot_uniforme`` :
    0,004 × taux réémis chaque année (8 % : effet direct ~0,5 pt au lieu de 0,032)."""
    niveau_pt = NIVEAU_RABOT_PAR_POINT_DE_TAUX * 0.08 * 100
    ecart = _ecart_direct('rabot_uniforme', {'rabot_uniforme': {'taux_reduction': 0.08}})
    assert max(abs(e) for e in ecart) <= niveau_pt * 1.02, (
        f"effet direct max {max(abs(e) for e in ecart):.3f} pt > niveau déclaré {niveau_pt:.3f} pt")
    # v0.6.7 lot 3 : canal direct RETIRÉ (double comptage de coupe → activité →
    # Okun, que le multiplicateur sur la dépense fait déjà) — écart nul.
    assert all(e == 0.0 for e in ecart), ecart


@pytest.mark.parametrize('mesures,measure_id,niveau', [
    ({'cotisations_salariales': {'baisse_points': 2.5}}, 'cotisations_salariales', 0.0),
    ({'rabot_uniforme': {'taux_reduction': 0.08}}, 'rabot_uniforme', 0.0),
])
def test_lot1_effet_de_niveau_emis_une_seule_fois(mesures, measure_id, niveau):
    """Propriété durable : la SOMME des émissions annuelles vaut le niveau déclaré.
    v0.6.7 lot 3 : niveau déclaré NUL pour ces deux leviers — leur effet direct
    (−0,05 pt par point de cotisations ; +0,004 × taux de rabot) refaisait le
    chemin demande → activité → Okun que le multiplicateur keynésien fait déjà
    sur leur flux budgétaire. Un effet direct de demande n'est légitime que pour
    une mesure sans flux budgétaire (CSG progressive à recette nulle)."""
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


# ---------------------------------------------------------------------------
# Lot 2 — cohortes de la réforme de l'État (bloc B, constat 1).
# ``efficience._reforme_fp_reduction_cumulee`` calculait
# départs × taux × efficacité(année COURANTE) × nombre d'années : chaque année
# réévaluait toutes les cohortes passées à l'efficacité du jour, comptait une
# cohorte 2026 qui n'existe pas (2 cohortes dès 2027), et pouvait faire croître le
# stock de plus que les départs d'une année. Intensité 20 (taux 67 %) : 63 114 /
# 525 950 postes en 2027 / 2030 au lieu de 31 557 / 289 272 (chiffres de l'audit).
# ---------------------------------------------------------------------------

from budget_simulator.constants import DEPARTS_ANNUELS_FP  # noqa: E402

EFFICACITE_COHORTE = {2027: 0.3, 2028: 0.6, 2029: 0.85}   # 2030+ : 1,0 (handler)
REFORME_MAX = {'fusion_agences': 100, 'digitalisation': 100}   # intensité 20 → 67 %


def _stock_reforme(params, annees=range(2025, 2041)):
    sim = BudgetSimulatorV45(periods=10, mesures={'fonction_publique_reforme': params})
    return {a: sim._reforme_fp_reduction_cumulee(a) for a in annees}


def test_lot2_fp_chiffres_de_l_audit():
    """RED v0.6.6 : 63 114 postes en 2027 et 525 950 en 2030 ; attendu 31 557 et
    289 272 (somme des cohortes 2027-2030 à leur propre efficacité), 710 032 au
    plateau de 8 cohortes (2034-2035)."""
    stock = _stock_reforme(REFORME_MAX)
    flux = DEPARTS_ANNUELS_FP * 0.67
    assert stock[2027] == pytest.approx(flux * 0.3)
    assert stock[2030] == pytest.approx(flux * (0.3 + 0.6 + 0.85 + 1.0))
    assert round(stock[2030]) == 289272
    assert stock[2034] == stock[2035] == pytest.approx(flux * (0.3 + 0.6 + 0.85 + 5 * 1.0))


@pytest.mark.parametrize('params', [
    REFORME_MAX,
    {'fusion_agences': 50, 'digitalisation': 50},    # renaissance_2027 (intensité 10)
    {'fusion_agences': 60, 'digitalisation': 50},    # im_competitivite_2029 (11)
    {'fusion_agences': 10, 'digitalisation': 20},    # horizons_2027 (3)
    {'fusion_agences': 0, 'digitalisation': 10},     # lfi_2027 (1)
])
def test_lot2_fp_somme_de_cohortes_historique_conserve(params):
    """Propriétés durables : pas de cohorte 2026 ; chaque année ajoute UNE cohorte,
    à l'efficacité de SON année (les cohortes passées ne sont jamais réévaluées) ;
    huit cohortes au plus (2027-2034) ; l'incrément annuel ne dépasse jamais le
    vivier d'une année de départs."""
    stock = _stock_reforme(params)
    assert stock[2025] == stock[2026] == 0.0
    taux = stock[2030] - stock[2029]          # cohorte à efficacité 1,0 = départs × taux
    for annee in range(2027, 2041):
        increment = stock[annee] - stock[annee - 1]
        attendu = taux * EFFICACITE_COHORTE.get(annee, 1.0) if annee <= 2034 else 0.0
        assert increment == pytest.approx(attendu, abs=1e-6), annee
        assert 0.0 <= increment <= DEPARTS_ANNUELS_FP
    assert stock[2034] == stock[2040]


def test_lot2_fp_cohorte_bornee_par_le_vivier_annuel():
    """Hors du domaine publié (curseurs > 100 %), le taux de non-remplacement
    implicite dépasse 1 : une cohorte ne peut pas pour autant excéder les départs de
    son année, ni devenir négative (un non-remplacement n'est pas une embauche)."""
    for params in ({'fusion_agences': 1000, 'digitalisation': 1000},
                   {'fusion_agences': -100, 'digitalisation': 0}):
        stock = _stock_reforme(params)
        for annee in range(2027, 2041):
            assert 0.0 <= stock[annee] - stock[annee - 1] <= DEPARTS_ANNUELS_FP, (params, annee)


@pytest.mark.parametrize('effectifs', [-60000, -300000, -900000])
def test_lot2_fp_reforme_et_curseur_jamais_au_dela_des_departs_cumules(effectifs):
    """Anti-double-comptage v0.6.0 PRÉSERVÉ : réforme + curseur effectifs ne
    suppriment jamais plus de postes que les départs cumulés depuis 2026."""
    from budget_simulator.constants import COUT_MOYEN_AGENT_FP_EUR
    mesures = {'fonction_publique_reforme': REFORME_MAX,
               'fonction_publique': {'effectifs': effectifs, 'point_indice': 0}}
    sim = BudgetSimulatorV45(periods=10, mesures=mesures)
    for annee in range(2026, 2036):
        d_eff, _, _ = sim._apply_fonction_publique(
            {}, mesures['fonction_publique'], annee, 3100, 0.015, 0.075)
        curseur = -d_eff * 1e9 / COUT_MOYEN_AGENT_FP_EUR
        total = curseur + sim._reforme_fp_reduction_cumulee(annee)
        assert total <= DEPARTS_ANNUELS_FP * (annee - 2025) * (1 + 1e-12), annee
        assert curseur <= -effectifs * (1 + 1e-12)


# ---------------------------------------------------------------------------
# Lot 2 — artefact ``taxe_superprofits`` à intensité 0 (backlog v0.6.6).
# Le mode simplifié pose ``tous_secteurs = intensite > 0`` : à 0, la branche
# « énergie seule » émettait une compétitivité CONSTANTE de −0,002 en 2026, sans
# aucune taxe levée. Les 7 scénarios publiés à intensité 0 la portaient.
# ---------------------------------------------------------------------------

def _superprofits(params, year=2026):
    sim = BudgetSimulatorV45(periods=10, mesures={'taxe_superprofits': params})
    return sim._apply_taxe_superprofits({}, params, year, 3100.0, 0.015, 0.075)


@pytest.mark.parametrize('params', [{'intensite': 0}, {'intensite': 0.0},
                                    {'taux': 0}, {'taux': 0.0, 'tous_secteurs': False}])
def test_lot2_superprofits_nul_a_intensite_zero(params):
    """RED v0.6.6 : competitivite = −0,002 en 2026 à intensité 0. Une taxe qui ne
    lève rien n'a aucun effet, sur aucun canal, aucune année."""
    for annee in range(2026, 2031):
        ds, dr, impacts = _superprofits(params, annee)
        assert ds == dr == 0
        assert all(v == 0 for v in impacts.values()), (annee, impacts)


def test_lot2_superprofits_competitivite_continue_et_monotone():
    """Propriété : l'effet compétitivité (année d'entrée) est continu en 0 et ne
    remonte jamais quand l'intensité augmente (plus de taxe, pas moins de risque de
    délocalisation). La falaise de v0.6.6 (−0,002 à 0, ~0 juste au-dessus) violait
    les deux."""
    grille = [i / 100 for i in range(0, 101)]
    comp = [_superprofits({'intensite': i})[2].get('competitivite', 0.0) for i in grille]
    assert comp[0] == 0.0
    assert all(b <= a for a, b in zip(comp, comp[1:]))


def test_lot2_superprofits_omis_ou_pose_a_zero_bit_identique(pleine_precision):
    """Conséquence en simulation : poser le levier à 0 ou l'omettre donne la même
    trajectoire, au bit (toutes colonnes, deux tableaux, AVANT l'arrondi de sortie :
    −0,002 point d'indice disparaît dans l'arrondi à 0,01 de la colonne seule)."""
    df_0, sec_0, _ = BudgetSimulatorV45(
        periods=10, mesures={'taxe_superprofits': {'intensite': 0}}).simulate()
    df_omis, sec_omis, _ = BudgetSimulatorV45(periods=10, mesures={}).simulate()
    assert df_0.equals(df_omis) and sec_0.equals(sec_omis)


# ---------------------------------------------------------------------------
# Lot 2 — désindexation des prestations : historique d'inflation (bloc B, constat 2).
# ``depenses._apply_prestations_indexation`` calculait 90 × [1 − (1 − δ·π_t)^k] :
# l'inflation COURANTE élevée au nombre de revalorisations écoulées. L'écart déjà
# constitué était donc réécrit chaque année à l'inflation du jour (gel total, 2027 à
# π = 2 % : −1,80 Md€ ; 2028 à π = 0 : 0,00 — l'écart de 2027 disparaissait).
# Correction : produit des revalorisations RÉELLEMENT écoulées, Π (1 − δ·π_s).
# ---------------------------------------------------------------------------

# v0.6.7 lot 3C : assiette = masse NOMINALE de la catégorie `minima_sociaux` de
# l'année (90 Md€ en 2025), première revalorisation en 2026 — même convention que
# les pensions (tests/test_desindexation_v067.py). Les propriétés du lot 2
# (mémoire de l'écart, inflation variable) sont conservées, exprimées en PART de
# la masse.


class _InflationScriptee(BudgetSimulatorV45):
    """Le moteur, avec une trajectoire d'inflation imposée (année civile → π) ;
    relève l'assiette nominale lue par le handler chaque année."""

    script = {}

    def calculate_inflation(self, year, economic_state):
        return self.script[self.annee_base + year]

    def _apply_prestations_indexation(self, measure, params, year, gdp, inflation, unemployment):
        self.assiettes[year] = self.masse_categorie_nominale('minima_sociaux')
        return super()._apply_prestations_indexation(measure, params, year, gdp, inflation, unemployment)


def _prestations(taux, script):
    """Écart en PART de l'assiette de l'année (négatif = économie)."""
    cls = type('_Script', (_InflationScriptee,), {'script': script})
    sim = cls(periods=10, mesures={'prestations_indexation': {'taux_indexation': taux}})
    sim.assiettes = {}
    _, _, rapport = sim.simulate()
    return {an['Année']: an['prestations_indexation']['depenses'] / sim.assiettes[an['Année']]
            for an in rapport['measure_impacts_by_year'] if an['Année'] >= 2026}


def _ecart_attendu(delta, script, annee):
    """Écart de niveau (part de l'assiette) après les revalorisations 2026..annee,
    dix au plus."""
    facteur = 1.0
    for s in range(2026, min(annee, 2035) + 1):
        facteur *= 1 - delta * max(script[s], 0.0)
    return -(1 - facteur)


def test_lot2_prestations_l_ecart_constitue_ne_disparait_pas():
    """RED v0.6.6 : gel total, π = 2 % jusqu'en 2027 puis 0 : −1,80 Md€ en 2027,
    0,00 en 2028. Une année sans inflation n'ouvre pas d'écart NOUVEAU ; elle ne
    rembourse pas pour autant celui des années passées (deux revalorisations
    évitées, 2026 et 2027 : 1 − 0,98² de l'assiette)."""
    script = {a: (0.02 if a <= 2027 else 0.0) for a in range(2025, 2036)}
    dep = _prestations(0.0, script)
    assert dep[2026] == pytest.approx(-0.02, abs=1e-12)
    for annee in range(2027, 2036):
        assert dep[annee] == pytest.approx(-(1 - 0.98 ** 2), abs=1e-12), annee


def test_lot2_prestations_historique_conserve_inflation_variable():
    """Propriété durable : sur une trajectoire d'inflation quelconque (déflation
    comprise — une revalorisation n'est jamais négative), l'écart vaut le produit des
    revalorisations écoulées, et une sous-indexation n'en rend jamais une partie."""
    pis = [0.011, 0.01, 0.03, 0.005, -0.01, 0.02, 0.0, 0.015, 0.04, 0.012, 0.018]
    script = dict(zip(range(2025, 2036), pis))
    dep = _prestations(0.8, script)
    for annee in range(2026, 2036):
        assert dep[annee] == pytest.approx(_ecart_attendu(0.2, script, annee), rel=1e-12, abs=1e-12)
    # (tolérance d'un ulp : part = montant / assiette, recalculée chaque année)
    assert all(dep[a + 1] <= dep[a] + 1e-15 for a in range(2026, 2035))


def test_lot2_prestations_inflation_constante_puissance():
    """À inflation constante, le produit historisé est la puissance du nombre de
    revalorisations (2026 incluse depuis v0.6.7)."""
    script = {a: 0.015 for a in range(2025, 2036)}
    dep = _prestations(0.8, script)
    for annee in range(2026, 2036):
        k = annee - 2025
        assert dep[annee] == pytest.approx(-(1 - (1 - 0.2 * 0.015) ** k), rel=1e-12, abs=1e-12)


# ---------------------------------------------------------------------------
# Hygiène — restes moteur du 05/10/2026 (backlog, item 1).
# ---------------------------------------------------------------------------

def _trajectoire(mesures):
    df, sec, _ = BudgetSimulatorV45(periods=10, mesures=mesures).simulate()
    return df, sec


@pytest.mark.parametrize('valeur', [float('inf'), float('-inf'), float('nan')])
def test_hygiene_offre_non_finie_vaut_le_defaut(valeur, monkeypatch, pleine_precision):
    """RED v0.6.6 : ``update_potential_growth`` lisait ``self.mesures`` BRUT. En mode
    tolérant, la porte retire ``recherche_publique.budget = inf`` (le handler retombe
    sur son défaut) mais le canal d'offre lisait ``inf`` : +0,2 pt de croissance
    potentielle (dette 2035 158,42 au lieu de 161,79). Les deux lecteurs du même
    paramètre doivent lire la même valeur."""
    monkeypatch.delenv('BUDGETLAB_STRICT', raising=False)
    df_v, sec_v = _trajectoire({'recherche_publique': {'budget': valeur}})
    df_d, sec_d = _trajectoire({'recherche_publique': {}})
    assert df_v.equals(df_d) and sec_v.equals(sec_d)


def test_hygiene_offre_bornee_comme_le_handler(monkeypatch, pleine_precision):
    """Même porte, deuxième étage : hors du domaine publié ([0 ; 20] Md€), le handler
    lit la valeur CLAMPÉE ; le canal d'offre lisait la valeur brute. Le bonus de
    recherche seul sature le plafond ±0,2 pt dès 0,74 Md€ d'écart : le défaut ne se
    voit qu'en SOMME avec un effet d'offre de signe opposé (investissement de
    transition), d'où la combinaison. RED v0.6.6 : bonus 2035 −0,20 pt au lieu de
    +0,086, dette 2035 164,8 au lieu de 159,9."""
    monkeypatch.delenv('BUDGETLAB_STRICT', raising=False)
    from budget_simulator.constants import PARAM_DOMAINS
    borne_basse = PARAM_DOMAINS['recherche_publique']['budget'][0]
    transition = {'investissement': 26}   # défaut moteur 0
    df_hors, sec_hors = _trajectoire({'transition_ecologique': transition,
                                      'recherche_publique': {'budget': borne_basse - 30}})
    df_borne, sec_borne = _trajectoire({'transition_ecologique': transition,
                                        'recherche_publique': {'budget': borne_basse}})
    assert df_hors.equals(df_borne) and sec_hors.equals(sec_borne)


def test_hygiene_entier_geant_ne_casse_pas_la_simulation_toleree(monkeypatch):
    """RED v0.6.6 : un entier JSON de 400 chiffres levait OverflowError dans
    ``detect_active_measures`` (journal des leviers déviés, appelé en 2026 HORS du
    ``try`` par mesure) : 500 en mode tolérant. Le journal ignore désormais la valeur
    illisible, et les autres leviers déviés restent journalisés.

    Contrat de la porte d'entrée (arbitrage d'intégration v0.6.7 avec le lot API,
    branche ``feat/v067-audit-api``) : un entier hors de la plage des flottants est
    une ENTRÉE NON FINIE, traitée comme ``inf`` — clé retirée, défaut du levier
    appliqué, correction tracée dans ``report['warnings']`` et ``valid: False``. Ce
    n'est pas un échec de handler. ⚠️ Ce test n'est vert qu'une fois les deux
    branches fusionnées (la porte d'entrée vient du lot API)."""
    from budget_simulator.constants import HANDLER_FAILED_KEY
    monkeypatch.delenv('BUDGETLAB_STRICT', raising=False)
    sim = BudgetSimulatorV45(periods=10, mesures={'recherche_publique': {'budget': 10 ** 400},
                                                  'defense': {'budget': 60}})
    _, _, rapport = sim.simulate()
    assert rapport['valid'] is False
    assert any('recherche_publique.budget' in w for w in rapport['warnings'])
    assert HANDLER_FAILED_KEY not in rapport['measure_impacts_by_year'][1].get('recherche_publique', {})
    assert 'defense.budget=60.00' in sim.detect_active_measures()


@pytest.mark.parametrize('bloc', ['oui', [1], 1, ('asu_activation', 1)])
def test_hygiene_bloc_asu_mal_forme_n_emporte_pas_les_autres_leviers(bloc, monkeypatch):
    """RED v0.6.6 : ``asu_is_active`` faisait ``.get`` sur tout bloc non vide — un
    bloc ``asu`` mal formé levait DANS les handlers prestations et fraude sociale,
    qui échouaient à sa place (désindexation perdue, échec attribué au mauvais
    levier). Un bloc mal formé est inactif pour ses lecteurs latéraux, comme dans
    ``valeur_brute`` ; seule la porte d'``asu`` le signale."""
    from budget_simulator.constants import HANDLER_FAILED_KEY
    from budget_simulator.handlers._phasing import asu_is_active, asu_phasing
    monkeypatch.delenv('BUDGETLAB_STRICT', raising=False)
    assert asu_is_active({'asu': bloc}) is False
    assert asu_phasing({'asu': bloc}, 2030) == 0.0
    mesures = {'asu': bloc, 'prestations_indexation': {'taux_indexation': 0.8},
               'fraude_sociale': {'effort': 0.5}}
    _, _, rapport = BudgetSimulatorV45(periods=10, mesures=mesures).simulate()
    an_2030 = rapport['measure_impacts_by_year'][5]
    for levier in ('prestations_indexation', 'fraude_sociale'):
        assert HANDLER_FAILED_KEY not in an_2030[levier], levier
    assert an_2030['prestations_indexation']['depenses'] < 0
    assert an_2030['asu'][HANDLER_FAILED_KEY] is True   # l'anomalie reste signalée, sur asu


def test_hygiene_bloc_superprofits_vide_contrat_documente():
    """Contrat DOCUMENTÉ (docstring du handler, METHODOLOGIE § Taxe Superprofits) :
    un bloc vide est le mode legacy à ses défauts NFP, donc la taxe pleine — pas la
    mesure inactive. Si ce comportement change, la documentation doit changer avec."""
    for annee, attendu in ((2026, 15.0), (2028, 15.0), (2029, 0.0)):
        _, recettes, _ = _superprofits({}, annee)
        assert recettes == pytest.approx(attendu), annee
