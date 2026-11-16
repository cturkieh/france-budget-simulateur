"""Lot 4 — méthode unique du Gini : ÉQUATIONS (tests écrits avant le code).

Chaque test est rouge sur le commit de paramètres du lot et vert après le commit
d'équations :

  (1) tranche supérieure de l'IR : effet = coefficient de l'IFI (INSEE) × Md€ de
      recette du taux, et non −0,008 par 5 points (jusqu'à 15 fois la borne) ;
  (2) ISF et impôt plancher, corrigés ENSEMBLE : effet = coefficient de l'IFI ×
      recette nette d'année pleine (hors phasage), émis au changement du
      paramètre ; l'ISF ne compte plus son phasage deux fois et ne lit plus la
      recette brute avant remplacement de l'IFI ;
  (3) indexation des prestations : effet = coefficient des prestations ciblées
      × écart en EUROS (euros de 2025), et non 0,008 par 10 points
      d'indexation (jusqu'à 6 fois la borne) ;
  (4) indexation des pensions : effet = coefficient des pensions × écart en
      euros ; le canal d'âge garde son mécanisme (coefficient nul faute de
      source, horloge éprouvée par tests/test_revue_adverse_mineurs_v061.py) ;
  (5) rabot uniforme : effet émis UNE fois au changement du taux, catégorie par
      catégorie (minima et AAH, chômage, pensions ; santé et APA à 0), et non
      réémis chaque année ;
  (6) facteur d'atténuation GINI_IMPACT_SCALE = 1,0 (coefficients physiques),
      cohérent avec la contribution que publie l'INSEE (0,22 la contredit) ;
      aucune règle ne garde l'ancien facteur (plus de constante historique) ;
      le SMIC émet une fois, à sa valeur sourcée ;
  (7) garde de borne au niveau des HANDLERS : pour chaque levier en Md€, l'effet
      émis par Md€ reste sous la borne arithmétique ;
  (8) hausse de 2026 de la CSG sur les revenus du capital (droit en vigueur) :
      la part correspondante du taux de CSG prend le coefficient du capital,
      celui de son retrait par fiscalite_capital — un instrument, un
      coefficient.
"""
import copy
import json
from pathlib import Path

import pytest

import budget_simulator.constants as C
import budget_simulator.engine.orchestrator as orch
import budget_simulator.simulator as mod_simulateur
from budget_simulator.simulator import BudgetSimulatorV45

Y = C.RDB_MENAGES_MD_EUR
G = C.GINI_BASE
BORNE_PRELEVEMENT = (1.0 - G) / Y
BORNE_PRESTATION = (1.0 + G) / Y
ETAT = {'year': C.POLICY_START_YEAR, 'gdp': float(C.PIB_BASE_2025_MD_EUR),
        'inflation': 0.016, 'unemployment': 0.075}


def _sim():
    sim = BudgetSimulatorV45(periods=1)
    sim._reset_state()
    return sim


def _appel(sim, levier, params, year=None, gdp=None):
    return sim.measure_handlers[levier](
        sim.measure_registry[levier], copy.deepcopy(params), year or ETAT['year'],
        gdp or ETAT['gdp'], ETAT['inflation'], ETAT['unemployment'])


def _pleine_precision(monkeypatch):
    monkeypatch.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)


# ---------------------------------------------------------------------------
# (1) Tranche supérieure de l'IR
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('taux', [0.40, 0.47, 0.50, 0.55, 0.60])
def test_ir_taux_superieur_par_md_de_recette(taux):
    _, rec, imp = _appel(_sim(), 'impot_revenu', {'taux_superieur': taux, 'decote': 1.0})
    assert imp['gini'] == pytest.approx(C.GINI_HAUT_PATRIMOINE_PAR_MD * rec, rel=1e-12, abs=1e-15)
    assert abs(imp['gini']) <= BORNE_PRELEVEMENT * abs(rec) + 1e-15


def test_ir_decote_et_taux_additifs():
    _, rec, imp = _appel(_sim(), 'impot_revenu', {'taux_superieur': 0.55, 'decote': 0.5})
    _, rec_t, imp_t = _appel(_sim(), 'impot_revenu', {'taux_superieur': 0.55, 'decote': 1.0})
    decote = rec - rec_t
    assert decote == pytest.approx(0.5 * C.IR_RECETTE_DECOTE, rel=1e-12)
    assert imp['gini'] == pytest.approx(imp_t['gini'] + C.GINI_IR_DECOTE_PAR_MD * decote, rel=1e-12)


# ---------------------------------------------------------------------------
# (2) ISF et impôt plancher, ensemble
# ---------------------------------------------------------------------------

def _isf_recette_pleine(intensite, sim=None):
    """Recette nette de l'ISF hors phasage, IFI de 2025 déduit : la recette du
    levier en régime permanent (deuxième année) moins la croissance de l'IFI."""
    sim = sim or _sim()
    sim._origines_courantes = {'isf_climatique': C.POLICY_START_YEAR}
    _, rec, _ = _appel(sim, 'isf_climatique', {'intensite': intensite}, year=C.POLICY_START_YEAR + 1)
    ifi_deuxieme_annee = 2.0 * 1.02
    return rec + intensite * (ifi_deuxieme_annee - 2.0)


@pytest.mark.parametrize('intensite', [0.3, 0.6, 1.0])
def test_isf_effet_egal_au_coefficient_ifi_fois_recette_pleine(intensite):
    """Première émission (année d'entrée) = K × recette nette d'année pleine,
    l'IFI remplacé déduit ; rien les années suivantes à paramètre inchangé."""
    sim = _sim()
    _, _, imp0 = _appel(sim, 'isf_climatique', {'intensite': intensite}, year=C.POLICY_START_YEAR)
    _, _, imp1 = _appel(sim, 'isf_climatique', {'intensite': intensite}, year=C.POLICY_START_YEAR + 1)
    attendu = C.GINI_HAUT_PATRIMOINE_PAR_MD * _isf_recette_pleine(intensite)
    assert imp0['gini'] == pytest.approx(attendu, rel=1e-12)
    assert imp1.get('gini', 0.0) == 0.0


def test_isf_retour_a_zero_rend_l_effet():
    sim = _sim()
    g0 = _appel(sim, 'isf_climatique', {'intensite': 1.0})[2]['gini']
    g1 = _appel(sim, 'isf_climatique', {'intensite': 0.0}, year=C.POLICY_START_YEAR + 1)[2].get('gini', 0.0)
    assert g0 < 0 and g0 + g1 == pytest.approx(0.0, abs=1e-15)


def test_impot_plancher_au_coefficient_de_l_ifi():
    from budget_simulator.handlers.recettes_taux import recette_plancher_annee_pleine
    sim = _sim()
    params = {'taux': 0.02}
    imp = _appel(sim, 'impot_plancher_patrimoine', params)[2]
    niveau = {'taux': 0.02, 'evitement': C.NEUTRES_RELEASE_E['impot_plancher_patrimoine']['evitement'],
              'intensite_isf': 0.0}
    assert imp['gini'] == pytest.approx(
        C.GINI_HAUT_PATRIMOINE_PAR_MD * recette_plancher_annee_pleine(niveau), rel=1e-12)


def test_isf_et_plancher_lisent_le_meme_coefficient():
    import budget_simulator.handlers.fiscalite_menages as fm
    import budget_simulator.handlers.recettes_taux as rt
    assert fm.GINI_HAUT_PATRIMOINE_PAR_MD is rt.GINI_HAUT_PATRIMOINE_PAR_MD is C.GINI_HAUT_PATRIMOINE_PAR_MD
    assert not hasattr(C, 'GINI_ISF_EFFECTIF_PAR_MD') and not hasattr(C, 'ISF_GINI_PAR_12MD')


# ---------------------------------------------------------------------------
# (3) et (4) Indexation des prestations et des pensions, en euros
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('taux', [0.0, 0.5, 0.9, 1.2])
def test_prestations_indexation_par_euro_d_ecart(taux):
    """Hors simulation (indice des prix 1) : effet = K_solidarité × dépense du
    levier (Md€ versés en plus, négatifs pour une sous-indexation)."""
    dep, _, imp = _appel(_sim(), 'prestations_indexation', {'taux_indexation': taux})
    assert imp['gini'] == pytest.approx(C.GINI_SOLIDARITE_PAR_MD * dep, rel=1e-12, abs=1e-15)
    assert abs(imp['gini']) <= BORNE_PRESTATION * abs(dep) + 1e-15


@pytest.mark.parametrize('indexation', [0.0, 0.5, 0.9, 1.2])
def test_pensions_indexation_par_euro_d_ecart(indexation):
    """Canal indexation seul (âge et durée au droit en vigueur) : effet =
    convention des pensions × dépense du levier."""
    params = {'indexation': indexation, 'duree_cotisation': C.RETRAITES_REF_DUREE_ANS}
    dep, _, imp = _appel(_sim(), 'retraites', params)
    assert imp['gini'] == pytest.approx(C.GINI_PENSIONS_PAR_MD * dep, rel=1e-12, abs=1e-15)


def _parcours(levier, param, chemin, fixes=None):
    sim = _sim()
    sim._origines_courantes = {levier: C.ANNEE_PREMIER_BUDGET_MANDAT}
    sim._inflation_par_annee = {a: 0.012 + 0.0005 * (a - 2025) for a in range(2025, 2050)}
    sorties = []
    for i, c in enumerate(chemin):
        dep, _, imp = _appel(sim, levier, {**(fixes or {}), param: c}, year=C.ANNEE_PREMIER_BUDGET_MANDAT + i)
        sorties.append((dep, imp.get('gini', 0.0)))
    return sorties


@pytest.mark.parametrize('levier,param,k,fixes', [
    ('prestations_indexation', 'taux_indexation', C.GINI_SOLIDARITE_PAR_MD, None),
    ('retraites', 'indexation', C.GINI_PENSIONS_PAR_MD, {'duree_cotisation': C.RETRAITES_REF_DUREE_ANS}),
])
@pytest.mark.parametrize('chemin', [
    [0.0] + [1.0] * 6,            # gel d'une année puis retour
    [0.0] * 7,                    # gel permanent
    [0.9] * 3 + [1.0] * 4,        # sous-indexation de trois ans
    [1.0] * 7 + [0.0] + [1.0] * 3,
])
def test_cumul_egal_au_coefficient_fois_l_ecart_atteint(levier, param, k, fixes, chemin):
    """Quel que soit le calendrier, le cumul des émissions vaut K × l'écart en
    euros de la DERNIÈRE année (hors simulation, indice des prix 1) : un gel
    d'une année garde exactement l'écart qu'il laisse, sans règle séparée."""
    sorties = _parcours(levier, param, chemin, fixes)
    assert sum(g for _, g in sorties) == pytest.approx(k * sorties[-1][0], rel=1e-9, abs=1e-15)


def test_ecart_en_euros_de_2025_en_simulation(monkeypatch):
    """En simulation, l'écart est lu en euros de 2025 (écart de niveau × masse
    de 2025 de la catégorie) : un gel d'une année émet son effet une fois, puis
    rien (l'écart qu'il laisse ne bouge plus)."""
    _pleine_precision(monkeypatch)
    sim = BudgetSimulatorV45(periods=10, mesures={'prestations_indexation': {'taux_indexation': 0.0}},
                             annee_debut=2028,
                             profils={'prestations_indexation.taux_indexation': {'forme': 'annee', 'annee': 2028}})
    _, _, rapport = sim.simulate()
    emis = {b['Année']: b['prestations_indexation']['gini'] for b in rapport['measure_impacts_by_year']
            if isinstance(b.get('prestations_indexation'), dict)}
    premier = emis[2028]
    assert premier > 0
    assert all(emis.get(a, 0.0) == pytest.approx(0.0, abs=1e-15) for a in range(2029, 2036)), emis


# ---------------------------------------------------------------------------
# (5) Rabot émis une fois, par catégorie
# ---------------------------------------------------------------------------

def _effet_rabot_attendu(taux, base):
    """−Σ K × coupe d'année pleine (euros de 2025), par catégorie en espèces."""
    coupe = lambda cat: base[cat] * taux
    return -(C.GINI_SOLIDARITE_PAR_MD * (coupe('minima_sociaux') + C.AAH_2025_MD_EUR * taux)
             - C.GINI_ALLOC_PAR_MD_EUR * coupe('chomage')
             + C.GINI_PENSIONS_PAR_MD * coupe('retraites'))


@pytest.mark.parametrize('taux', [0.02, 0.05, 0.08])
def test_rabot_premiere_emission_par_categorie(taux):
    sim = _sim()
    imp = _appel(sim, 'rabot_uniforme', {'taux_reduction': taux})[2]
    assert imp['gini'] == pytest.approx(_effet_rabot_attendu(taux, sim.spending_categories_base), rel=1e-12)
    assert imp['gini'] > 0


def test_rabot_n_est_plus_reemis_chaque_annee(monkeypatch):
    _pleine_precision(monkeypatch)
    sim = BudgetSimulatorV45(periods=10, mesures={'rabot_uniforme': {'taux_reduction': 0.08}})
    _, _, rapport = sim.simulate()
    emis = [b['rabot_uniforme']['gini'] for b in rapport['measure_impacts_by_year']
            if isinstance(b.get('rabot_uniforme'), dict)]
    assert emis[0] > 0 and all(g == 0.0 for g in emis[1:]), emis
    assert sum(emis) == pytest.approx(_effet_rabot_attendu(0.08, sim.spending_categories_base), rel=1e-12)


def test_rabot_retour_a_zero_rend_l_effet():
    sim = _sim()
    g0 = _appel(sim, 'rabot_uniforme', {'taux_reduction': 0.08})[2]['gini']
    g1 = _appel(sim, 'rabot_uniforme', {'taux_reduction': 0.0}, year=C.POLICY_START_YEAR + 1)[2].get('gini', 0.0)
    assert g0 + g1 == pytest.approx(0.0, abs=1e-15)


# ---------------------------------------------------------------------------
# (6) Facteur d'atténuation 1,0 ; SMIC à sa valeur sourcée
# ---------------------------------------------------------------------------

def test_facteur_d_attenuation_unite():
    assert C.GINI_IMPACT_SCALE == 1.0
    assert not hasattr(C, 'GINI_ATTENUATION_HISTORIQUE')


def test_le_facteur_un_retrouve_la_contribution_publiee():
    """INSEE, France, portrait social 2025, fiche « Redistribution monétaire »,
    figure 2 : les prestations (A = 5,8 % du niveau de vie, B = 9,5) contribuent
    pour |A × B| / 1000 = 0,0551 à la réduction de l'indice. Leur masse, A × Y,
    pesée par le coefficient marginal du classement final, doit retrouver cet
    ordre (écart entre effet marginal et effet moyen, et entre classements) ;
    avec 0,22, l'effet serait environ cinq fois trop petit."""
    a, b = C.INSEE_FPS2025_REDISTRIBUTION['prestations']
    contribution = a * b / 1000
    masse = a / 100 * C.MASSE_NIVEAUX_DE_VIE_MD_EUR
    effet = C.GINI_IMPACT_SCALE * abs(C.GINI_SOLIDARITE_PAR_MD) * masse
    assert 0.6 * contribution <= effet <= 1.2 * contribution, (effet, contribution)
    assert 0.22 * abs(C.GINI_SOLIDARITE_PAR_MD) * masse < 0.25 * contribution


@pytest.mark.parametrize('montant_brut', [1700, 2000, 2180])
def test_smic_valeur_sourcee_emise_une_fois(montant_brut, monkeypatch):
    """Le Gini lit la hausse du levier : SMIC du programme rapporté au SMIC de
    référence de l'année d'application (lot SMIC). Mode historique : origine =
    année de la référence, la référence est le SMIC du Journal officiel ;
    l'effet est émis une fois, l'année d'entrée."""
    import budget_simulator.engine.micro_impacts as mi
    assert C.POLICY_START_YEAR == C.SMIC_ANNEE_DE_REFERENCE
    ref = C.SMIC_BRUT_MENSUEL_REFERENCE_EUR
    hausse = (montant_brut - ref) / ref
    emis = []
    orig = mi.MicroImpactsMixin.calculate_gini_impact

    def espion(self, impacts, gdp):
        emis.append(float((impacts.get('smic') or {}).get('gini', 0.0)))
        return orig(self, impacts, gdp)

    monkeypatch.setattr(mi.MicroImpactsMixin, 'calculate_gini_impact', espion)
    BudgetSimulatorV45(periods=10, mesures={'smic': {'montant_brut': montant_brut}}).simulate()
    assert emis[0] == pytest.approx(hausse * C.GINI_SMIC_PAR_HAUSSE, rel=1e-12)
    assert all(e == 0.0 for e in emis[1:]), emis


# ---------------------------------------------------------------------------
# (7) Borne au niveau des handlers
# ---------------------------------------------------------------------------

PRELEVEMENTS = [
    ('impot_revenu', {'taux_superieur': 0.60, 'decote': 0.0}),
    ('csg', {'taux': 0.12, 'progressive': 0}),
    ('cotisations_salariales', {'baisse_points': 11.0}),
    ('elargissement_ir', {'taux_contribuables_cible': 0.70}),
    ('fiscalite_patrimoine', {'intensite': 0.3}),
    ('isf_climatique', {'intensite': 1.0}),
    ('impot_plancher_patrimoine', {'taux': 0.03}),
    ('fiscalite_capital', {'prelevements_sociaux_capital': 0.25}),
    ('droits_succession', {'variation': 20.0}),
    ('impot_revenu_cible', {'montant': -10.0}),
    ('abattement_retraites', {'reforme_active': 1}),
]
PRESTATIONS = [
    ('prestations_menages', {'solidarite': 20.0, 'pensions': -15.0}),
    ('prestations_indexation', {'taux_indexation': 0.0}),
    ('chomage_alloc', {'taux_remplacement': 0.45, 'duree': 12, 'degressivite': True}),
    ('retraites', {'indexation': 0.0, 'duree_cotisation': C.RETRAITES_REF_DUREE_ANS}),
    ('rabot_uniforme', {'taux_reduction': 0.08}),
    ('asu', {'asu_activation': 1, 'asu_plafonnement': 0.7}),
]


@pytest.mark.parametrize('levier,params', PRELEVEMENTS, ids=[p[0] for p in PRELEVEMENTS])
def test_borne_par_md_au_niveau_du_handler_prelevement(levier, params):
    sim = _sim()
    _, rec, imp = _appel(sim, levier, params)
    if levier in ('isf_climatique', 'impot_plancher_patrimoine', 'abattement_retraites'):
        # Montant d'année pleine (l'année d'entrée ne collecte qu'une part).
        _, rec, _ = _appel(_sim(), levier, params, year=C.POLICY_START_YEAR + 1)
    assert rec != 0
    assert abs(imp.get('gini', 0.0)) <= BORNE_PRELEVEMENT * abs(rec) * (1 + 1e-12), (levier, imp.get('gini'), rec)


@pytest.mark.parametrize('levier,params', PRESTATIONS, ids=[p[0] for p in PRESTATIONS])
def test_borne_par_md_au_niveau_du_handler_prestation(levier, params):
    sim = _sim()
    sim.mesures = {levier: params}
    dep, _, imp = _appel(sim, levier, params)
    montant = abs(dep)
    if levier == 'prestations_menages':
        montant = abs(params['solidarite']) + abs(params['pensions'])
    if levier == 'asu':
        montant = C.asu_effort_perenne_md_eur(0.7) + C.asu_cout_recours_md_eur(1.0)
    assert montant != 0
    assert abs(imp.get('gini', 0.0)) <= BORNE_PRESTATION * montant * (1 + 1e-12), (levier, imp.get('gini'), montant)


# ---------------------------------------------------------------------------
# (8) Hausse de 2026 de la CSG sur les revenus du capital : un coefficient
# ---------------------------------------------------------------------------

CSG_REF, CSG_MASSE = 0.097, 140.0


def _recette_csg(taux):
    return CSG_MASSE * (taux - CSG_REF) / CSG_REF


def test_droit_en_vigueur_au_coefficient_du_capital():
    """Le taux du droit en vigueur (hausse de 2026 sur les revenus du capital)
    émet au coefficient du capital, celui de fiscalite_capital."""
    import json as _json
    droit = _json.loads((Path(C.__file__).parent / 'data' / 'droit_en_vigueur.json').read_text(encoding='utf-8'))
    assert droit['mesures']['csg']['taux'] == C.CSG_TAUX_DROIT_EN_VIGUEUR_2026
    gini = _appel(_sim(), 'csg', {'taux': C.CSG_TAUX_DROIT_EN_VIGUEUR_2026, 'progressive': 0})[2]['gini']
    assert gini == pytest.approx(C.GINI_CAPITAL_PAR_MD * _recette_csg(C.CSG_TAUX_DROIT_EN_VIGUEUR_2026), rel=1e-12)


@pytest.mark.parametrize('taux', [0.087, 0.0975, 0.105, 0.12])
def test_au_dela_de_la_hausse_le_coefficient_de_la_csg(taux):
    part_capital = min(max(taux - CSG_REF, 0.0), C.CSG_TAUX_DROIT_EN_VIGUEUR_2026 - CSG_REF)
    r_cap = _recette_csg(CSG_REF + part_capital)
    attendu = C.GINI_CAPITAL_PAR_MD * r_cap + C.GINI_CSG_PAR_MD * (_recette_csg(taux) - r_cap)
    gini = _appel(_sim(), 'csg', {'taux': taux, 'progressive': 0})[2]['gini']
    assert gini == pytest.approx(attendu, rel=1e-12)


def test_retrait_de_la_hausse_par_fiscalite_capital_meme_coefficient():
    """Un programme qui retire la hausse par fiscalite_capital émet au même
    coefficient par Md€ que la hausse portée par le taux de CSG."""
    imp = _appel(_sim(), 'fiscalite_capital', {'prelevements_sociaux_capital': 0.172})
    rec, gini = imp[1], imp[2]['gini']
    assert rec < 0 and gini == pytest.approx(C.GINI_CAPITAL_PAR_MD * rec, rel=1e-12)
    hausse = _appel(_sim(), 'csg', {'taux': C.CSG_TAUX_DROIT_EN_VIGUEUR_2026, 'progressive': 0})
    assert hausse[2]['gini'] / hausse[1] == pytest.approx(gini / rec, rel=1e-12)


# ---------------------------------------------------------------------------
# (9) Propriétés vues sans scenarios.json (relecture adverse du lot 4) :
#     signe et valeur de l'abattement, même émission dans les deux modes,
#     retour au défaut de l'impôt sur le revenu
# ---------------------------------------------------------------------------

DEBUT_CADRE = 2028


def _emission_a_l_entree(levier, params, annee_debut, decalage=0):
    """Émission du handler à l'année d'origine du levier (+ décalage), moteur neuf
    en mode historique (annee_debut None) ou cadre."""
    sim = (BudgetSimulatorV45(periods=10, annee_debut=annee_debut) if annee_debut
           else BudgetSimulatorV45(periods=10))
    sim._reset_state()
    sim.mesures = {levier: copy.deepcopy(params)}
    annee = sim._origine(levier) + decalage
    dep, rec, imp = _appel(sim, levier, params, year=annee)
    return (imp or {}).get('gini', 0.0), dep, rec


@pytest.mark.parametrize('annee_debut', [None, DEBUT_CADRE], ids=['historique', 'cadre2028'])
def test_abattement_signe_et_valeur(annee_debut):
    """Réforme de l'abattement : prélèvement de régime permanent 4 Md€ au
    coefficient (négatif) de l'abattement, émis à l'entrée, dans les deux modes."""
    gini, _, _ = _emission_a_l_entree('abattement_retraites', {'reforme_active': 1}, annee_debut)
    assert C.GINI_ABATTEMENT_RETRAITES_PAR_MD < 0
    assert gini == pytest.approx(C.GINI_ABATTEMENT_RETRAITES_PAR_MD * 4.0, rel=1e-12)


@pytest.mark.parametrize('levier,params,tolerance', [
    ('rabot_uniforme', {'taux_reduction': 0.08}, 1e-12),
    ('csg', {'taux': 0.105, 'progressive': 0}, 1e-12),
    # ISF : recette nette d'année pleine de l'année d'entrée (assiette qui croît
    # d'environ 2 % par an) : écart de quelques % entre 2026 et 2028 au plus.
    ('isf_climatique', {'intensite': 1.0}, 0.06),
])
def test_meme_regle_dans_les_deux_modes(levier, params, tolerance):
    """Une règle remultipliée dans un seul mode (par l'ancien facteur 0,22, par
    exemple) rougit ici, sans dépendre des instantanés."""
    g_h, _, _ = _emission_a_l_entree(levier, params, None)
    g_c, _, _ = _emission_a_l_entree(levier, params, DEBUT_CADRE)
    assert g_h != 0.0
    assert g_c == pytest.approx(g_h, rel=tolerance), (levier, g_h, g_c)


def test_impot_revenu_retour_au_defaut_rend_l_effet():
    """Chemin 0,55 → 0,45 → 0,45 (décote inchangée) : l'effet est émis, rendu
    au retour au droit en vigueur, puis plus rien."""
    sim = _sim()
    e = [(_appel(sim, 'impot_revenu', {'taux_superieur': t, 'decote': 1.0}, year=C.POLICY_START_YEAR + i)[2] or {})
         .get('gini', 0.0) for i, t in enumerate((0.55, 0.45, 0.45))]
    assert e[0] < 0
    assert e[1] == pytest.approx(-e[0], rel=1e-12)
    assert e[2] == pytest.approx(0.0, abs=1e-15)


# ---------------------------------------------------------------------------
# (10) Assemblage (arbitrage du mainteneur) : ni convergence ni amortissement.
#      L'indice publié de l'année est la base plus la somme des effets émis
#      jusqu'à elle (facteur 1,0), bornée par les seules bornes de sécurité
#      [GINI_SOFT_FLOOR ; GINI_HARD_CEILING].
# ---------------------------------------------------------------------------

def _trajectoire(mesures, annee_debut=None, sonde=None):
    """Gini publié (pleine précision) et cumul des émissions de chaque année."""
    import budget_simulator.engine.micro_impacts as mi
    cumul, total = [], [0.0]
    orig = mi.MicroImpactsMixin.calculate_gini_impact

    def espion(self, impacts, gdp):
        g = orig(self, impacts, gdp) if sonde is None else sonde(len(cumul))
        total[0] += g
        cumul.append(total[0])
        return g

    import pytest as _pytest
    mp = _pytest.MonkeyPatch()
    mp.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
    mp.setattr(mi.MicroImpactsMixin, 'calculate_gini_impact', espion)
    try:
        kw = {'annee_debut': annee_debut} if annee_debut else {}
        df, _, _ = BudgetSimulatorV45(periods=10, mesures=copy.deepcopy(mesures), **kw).simulate()
    finally:
        mp.undo()
    return [float(v) for v in df['Gini'].tolist()][1:], cumul


@pytest.mark.parametrize('mesures', [
    {'prestations_menages': {'solidarite': 10.0}},
    {'prestations_menages': {'solidarite': -10.0}},
    {'smic': {'montant_brut': 2100}},
    {'fiscalite_capital': {'prelevements_sociaux_capital': 0.22}},
], ids=['prestations+', 'prestations-', 'smic', 'capital'])
def test_l_effet_arrive_l_annee_ou_la_mesure_s_applique(mesures):
    """Sans convergence : chaque année, l'indice publié vaut la base plus le
    cumul des émissions, au bit ; une baisse n'est pas amortie, une hausse non
    plus (plus de plancher asymétrique)."""
    gini, cumul = _trajectoire(mesures)
    assert any(c != 0.0 for c in cumul)
    for g, c in zip(gini, cumul):
        assert g == pytest.approx(C.GINI_BASE + C.GINI_IMPACT_SCALE * c, rel=0, abs=1e-15)


def test_plus_de_constante_de_convergence():
    assert not hasattr(C, 'GINI_CONVERGENCE_RATE')


@pytest.mark.parametrize('emission,borne', [(-0.2, C.GINI_SOFT_FLOOR), (+0.2, C.GINI_HARD_CEILING)])
def test_bornes_de_securite_gardees(emission, borne):
    """Les bornes de sécurité restent le seul garde-fou : une cible hors de
    [0,25 ; 0,40] est publiée à la borne, et redevient la cible quand elle y
    rentre."""
    seq = [emission, 0.0, -emission, 0.0] + [0.0] * 6
    gini, cumul = _trajectoire({'prestations_menages': {'solidarite': 1.0}},
                               sonde=lambda i: seq[i] if i < len(seq) else 0.0)
    assert gini[0] == pytest.approx(borne, abs=1e-15)
    assert gini[1] == pytest.approx(borne, abs=1e-15)
    assert gini[2] == pytest.approx(C.GINI_BASE, abs=1e-15)


def test_meme_effet_dans_les_deux_modes_sans_convergence():
    """En mode cadre, la mesure entre en 2028 : l'écart à la trajectoire du statu
    quo du même mode vaut l'effet entier dès 2028 (et rien avant), comme en 2026
    en mode historique. (Le statu quo du mode cadre porte le droit en vigueur,
    dont la hausse de 2026 sur le capital : on lit l'écart.)"""
    m = {'prestations_menages': {'solidarite': 10.0}}
    effet = C.GINI_SOLIDARITE_PAR_MD * 10.0
    g_h, _ = _trajectoire(m)
    sq_h, _ = _trajectoire({})
    assert g_h[0] - sq_h[0] == pytest.approx(effet, abs=1e-15)
    g_c, _ = _trajectoire(m, annee_debut=DEBUT_CADRE)
    sq_c, _ = _trajectoire({}, annee_debut=DEBUT_CADRE)
    i_2028 = DEBUT_CADRE - C.POLICY_START_YEAR
    assert g_c[i_2028] - sq_c[i_2028] == pytest.approx(effet, abs=1e-15)
    assert g_c[i_2028 - 1] - sq_c[i_2028 - 1] == pytest.approx(0.0, abs=1e-15)
