"""Release E — chantier W3 : recettes en Md€ sans comportement, déplafonnement
des cotisations salariales. Tests-propriétés écrits AVANT le code (TDD).

Contrat : ``docs/plans/contrat-curseurs-release-E-2026-11.md`` du dépôt parent,
§ 1.1 (table des leviers, règle R-IDX), § 1.2-4 et § 1.2-9 à 1.2-11 (fiches),
§ 1.2-D (déplafonnement), § 1.3 (coefficients par Md€), § 4.1 (règles I, IR,
E, D ; X1 pour mémoire), § 6.1 (tests communs G1 à G12, AD) et § 6.4 (W3-1 à
W3-11).

Leviers du chantier : ``droits_succession`` (variation), ``fiscalite_indirecte``
(tva_ciblee, accises_energie), ``impot_revenu_cible`` (montant),
``recette_exceptionnelle`` (montant, une seule année) ; déplafonnement de
``cotisations_salariales.baisse_points``.

Règles d'écriture de ce fichier :

- Chaque valeur ATTENDUE est dérivée des constantes nommées du socle
  (``constants.py``, bloc « RELEASE E — SOCLE ») et des assiettes sourcées
  (``DMTG_2025_MD``, ``COTIS_SAL_MASSE_2025_MD``…), jamais recopiée. Les
  valeurs ESSAYÉES sont tirées du domaine du registre (``policy_measures.json``).
- Chaque propriété est un VÉRIFICATEUR (fonction qui lève ``AssertionError``)
  appelé par son test, puis rejoué sur un moteur MUTÉ : effet compté deux fois,
  effet ponctuel recompté chaque année, retour anticipé au neutre, fuite vers un
  autre levier, signe inversé, montant indexé. Le test de mutation exige d'abord
  que le vérificateur passe SANS mutation (sinon il prouverait n'importe quoi),
  puis qu'il rougisse AVEC.
- Mécanismes du chantier W1 (profils temporels, contrat § 2) : les propriétés
  qui exigent la forme « une seule année », la rampe générale ou le refus de la
  recette exceptionnelle en mode historique sont, depuis l'intégration de la
  release E, des tests ordinaires (marqueur ``xfail`` d'attente retiré).
"""
import ast
import importlib.util
import inspect
import json
import math
import os
import re
import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import budget_simulator.constants as C
import budget_simulator.engine.orchestrator as mod_orchestrateur
import budget_simulator.handlers.fiscalite_menages as mod_fiscalite
import budget_simulator.handlers.recettes_montants as mod_recettes
from budget_simulator import EntreeInvalide
from budget_simulator.constants import HANDLER_FAILED_KEY, PARAM_DOMAINS
from budget_simulator.engine._param_domain import ValeurInvalide
from budget_simulator.handlers._types import CANAUX_MENAGES, canaux_menages
from budget_simulator.simulator import BudgetSimulatorV45

RACINE = Path(__file__).absolute().parent.parent
REGISTRE = {m['id']: m for m in json.loads(
    (RACINE / 'policy_measures.json').read_text(encoding='utf-8'))['mesures']}
_DROIT = json.loads((RACINE / 'budget_simulator' / 'data' / 'droit_en_vigueur.json')
                    .read_text(encoding='utf-8'))['mesures']

sys.path.insert(0, str(RACINE / 'tests' / 'snapshots'))
from run_scenarios_full import SCENARIOS as _SCENARIOS_PUBLIES  # noqa: E402
from cadre_harness import bases_g1  # noqa: E402

# Leviers du chantier (contrat § 1.1, colonne « Chantier » = W3).
W3 = ('droits_succession', 'fiscalite_indirecte', 'impot_revenu_cible', 'recette_exceptionnelle')
# Leviers appliqués chaque année (R-IDX : montant constant en euros courants).
RECURRENTS = ('droits_succession', 'fiscalite_indirecte', 'impot_revenu_cible')
DEBUT = C.POLICY_START_YEAR          # première année simulée (mode historique)
DEBUT_CADRE = C.ANNEE_PREMIER_BUDGET_MANDAT  # premier budget du mandat (mode cadre)
FIN_MANDAT = C.ANNEE_FIN_MANDAT


# ---------------------------------------------------------------------------
# Domaine du registre et valeurs essayées
# ---------------------------------------------------------------------------

def _spec(levier, param):
    return REGISTRE[levier]['parametres'][param]


def _neutre(levier, param):
    return C.NEUTRES_RELEASE_E[levier][param]


def _mi_haut(levier, param):
    """Mi-chemin du neutre et de la borne haute (convention des sondes du socle)."""
    n, s = _neutre(levier, param), _spec(levier, param)
    return n + (s['max'] - n) / 2


def _mi_bas(levier, param):
    n, s = _neutre(levier, param), _spec(levier, param)
    return n - (n - s['min']) / 2


def _signe(levier, param):
    """Paramètre signé : le domaine s'étend des deux côtés du neutre."""
    s, n = _spec(levier, param), _neutre(levier, param)
    return s['min'] < n < s['max']


def _symetrique(levier, param):
    """x > 0 tel que ±x (autour du neutre) restent dans le domaine."""
    s, n = _spec(levier, param), _neutre(levier, param)
    return min(s['max'] - n, n - s['min']) / 2


def _cas_non_neutres():
    cas = []
    for levier in W3:
        for param in C.NEUTRES_RELEASE_E[levier]:
            cas.append((levier, {param: _mi_haut(levier, param)}))
            if _signe(levier, param):
                cas.append((levier, {param: _mi_bas(levier, param)}))
    # Les deux paramètres de la fiscalité indirecte ensemble, de signes opposés.
    cas.append(('fiscalite_indirecte', {'tva_ciblee': _mi_haut('fiscalite_indirecte', 'tva_ciblee'),
                                        'accises_energie': _mi_bas('fiscalite_indirecte', 'accises_energie')}))
    return cas


CAS = _cas_non_neutres()
IDS = [f"{l}-{'-'.join(f'{k}={v:g}' for k, v in p.items())}" for l, p in CAS]
CAS_RECURRENTS = [(l, p) for l, p in CAS if l in RECURRENTS]
IDS_RECURRENTS = [i for (l, _), i in zip(CAS, IDS) if l in RECURRENTS]
# Un cas par levier (première sonde haute), pour les tests coûteux.
UN_PAR_LEVIER = [next((l, p) for l, p in CAS if l == levier) for levier in W3]
UN_PAR_RECURRENT = [c for c in UN_PAR_LEVIER if c[0] in RECURRENTS]


# ---------------------------------------------------------------------------
# Attendus du contrat (§ 1.2), dérivés des constantes nommées
# ---------------------------------------------------------------------------

def attendu(levier, params):
    """Effet direct d'UNE année d'application, au niveau ``params`` (paramètres
    absents = neutres) : Δdép, Δrec, canaux ménages, Gini et compétitivité
    ponctuels (valeur de PREMIÈRE émission, = effet du niveau, § 1.1 « Effets
    ponctuels »). Signes : constante signée × montant, aucun signe ajouté
    (règle d'écriture du § 1.1, relecture B1)."""
    p = {**C.NEUTRES_RELEASE_E[levier], **params}
    if levier == 'droits_succession':
        v = p['variation']
        # § 1.2-4 : aucun canal ménages (transfert en capital) ; règle du levier
        # patrimoine (GINI_PATRIMOINE_PAR_MD, COMPET_PATRIMOINE_PAR_MD).
        return dict(dep=0.0, rec=v, menages=canaux_menages(),
                    gini=C.GINI_PATRIMOINE_PAR_MD * v, compet=C.COMPET_PATRIMOINE_PAR_MD * v)
    if levier == 'fiscalite_indirecte':
        t, a = p['tva_ciblee'], p['accises_energie']
        # § 1.2-9 : TVA à 100 % sur les prix des ménages, accises à la part de
        # consommation des ménages (convention de tva_energie) ; compétitivité
        # de la TVA seule (convention de tva_energie : 0 pour les accises).
        return dict(dep=0.0, rec=t + a,
                    menages=canaux_menages(
                        prelevements_indirects=t + C.PART_CONSOMMATION_MENAGES_TVA_TOTALE * a),
                    gini=C.GINI_TVA_PAR_MD * t + C.GINI_TVA_ENERGIE_PAR_MD * a,
                    compet=C.COMPET_TVA_PAR_MD * t)
    if levier == 'impot_revenu_cible':
        m = p['montant']
        # § 1.2-10 : prélèvement direct ; règle de la décote ; compétitivité 0.
        return dict(dep=0.0, rec=m, menages=canaux_menages(prelevements_directs=m),
                    gini=C.GINI_IR_DECOTE_PAR_MD * m, compet=0.0)
    if levier == 'recette_exceptionnelle':
        m = p['montant']
        # § 1.2-11 : canaux ménages nuls, Gini 0, compétitivité 0.
        return dict(dep=0.0, rec=m, menages=canaux_menages(), gini=0.0, compet=0.0)
    raise KeyError(levier)


# ---------------------------------------------------------------------------
# Outils : appel direct d'un handler, simulation
# ---------------------------------------------------------------------------

ETAT = {'year': DEBUT_CADRE, 'gdp': float(C.PIB_BASE_2025_MD_EUR),
        'inflation': C.INFLATION_STRUCTURELLE, 'unemployment': C.CHOMAGE_BASE}


def _sim_neuf(mesures=None):
    sim = BudgetSimulatorV45(periods=1)
    sim._reset_state()
    if mesures is not None:
        sim.mesures = mesures
    return sim


def _appel(sim, levier, params, **etat):
    e = {**ETAT, **etat}
    return sim.measure_handlers[levier](sim.measure_registry[levier], params, e['year'],
                                        e['gdp'], e['inflation'], e['unemployment'])


def _canon(x):
    if isinstance(x, dict):
        return {str(k): _canon(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_canon(v) for v in x]
    if isinstance(x, float):
        return x.hex()
    return x


_CACHE = {}


def _simuler(mesures, annee_debut=None, strict=False, *, cache=True, pleine=False):
    """(df, détail, rapport) ; ``cache=False`` pour un moteur muté ;
    ``pleine=True`` neutralise l'arrondi des sorties tabulaires de
    l'orchestrateur (même procédé que ``cadre_harness.pleine_precision``), pour
    les égalités à 1e-9 sur des montants quelconques."""
    cle = (json.dumps(mesures, sort_keys=True), annee_debut, strict, pleine)
    if cache and cle in _CACHE:
        return _CACHE[cle]
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv('BUDGETLAB_STRICT', '1' if strict else '')
        if pleine:
            mp.setattr(mod_orchestrateur, 'round', lambda x, n=None: float(x), raising=False)
        sortie = BudgetSimulatorV45(periods=10, mesures=mesures, annee_debut=annee_debut).simulate()
    if cache:
        _CACHE[cle] = sortie
    return sortie


def _par_annee(rapport):
    return {int(a['Année']): a for a in rapport['measure_impacts_by_year']}


def _effets(rapport, levier):
    """{année: impacts du levier ou None} pour les années simulées (≥ 2026)."""
    return {an: a.get(levier) for an, a in _par_annee(rapport).items() if an >= DEBUT}


def _leve_entree_invalide(fonction, classe=EntreeInvalide):
    """Vrai si ``fonction()`` lève une erreur d'ENTRÉE (``classe``, par défaut
    ``EntreeInvalide``), seule ou dans l'``ExceptionGroup`` du mode strict."""
    try:
        fonction()
    except BaseExceptionGroup as groupe:
        entrees, _ = groupe.split(classe)
        return entrees is not None
    except classe:
        return True
    return False


# ===========================================================================
# 0. Livraison : les leviers du chantier ne sont plus des squelettes
# ===========================================================================

def test_leviers_w3_retires_de_la_liste_des_non_livres():
    """Socle § 9 : un chantier qui livre ses corps retire SES leviers de
    ``LEVIERS_NON_LIVRES`` (ligne « Chantier W3 » de constants.py). Les gardes
    du socle vérifient ensuite que la liste nomme exactement les squelettes."""
    assert not set(W3) & C.LEVIERS_NON_LIVRES, sorted(set(W3) & C.LEVIERS_NON_LIVRES)


@pytest.mark.parametrize('levier', W3)
def test_handler_w3_n_appelle_plus_le_squelette(levier):
    source = inspect.getsource(getattr(BudgetSimulatorV45, f'_apply_{levier}'))
    assert 'levier_non_livre(' not in source, levier


# ===========================================================================
# 1. G2 et retour anticipé : absent ≡ neutre ≡ droit en vigueur
# ===========================================================================

@pytest.mark.parametrize('levier', W3)
def test_g2_levier_absent_du_droit_en_vigueur(levier):
    """§ 0.9 : un montant écrit par un programme est sans objet dans le droit
    (« absent du droit = zéro ») ; le neutre du registre est zéro."""
    assert levier not in _DROIT
    assert set(C.NEUTRES_RELEASE_E[levier].values()) == {0}


def test_g2_cotisations_salariales_au_neutre_dans_le_droit():
    """Le déplafonnement ne touche pas la référence : le droit en vigueur pose
    0 point, valeur neutre du registre."""
    assert _DROIT['cotisations_salariales'] == {
        'baisse_points': REGISTRE['cotisations_salariales']['parametres']['baisse_points']['valeur_defaut']}


@pytest.mark.parametrize('levier', W3)
@pytest.mark.parametrize('bloc', ['complet', 'zero_flottant', 'zero_negatif', 'partiel'])
def test_retour_anticipe_au_neutre_moteur_vierge(levier, bloc):
    """§ 1.1 « Retour anticipé » : toutes les valeurs neutres et aucune clé
    ponctuelle du levier dans le traqueur → ``(0.0, 0.0, {})`` avant tout
    calcul, quelle que soit l'écriture du zéro."""
    neutres = dict(C.NEUTRES_RELEASE_E[levier])
    params = {'complet': neutres,
              'zero_flottant': {k: 0.0 for k in neutres},
              'zero_negatif': {k: -0.0 for k in neutres},
              'partiel': {next(iter(neutres)): 0.0}}[bloc]
    sim = _sim_neuf()
    sortie = _appel(sim, levier, params)
    assert sortie == (0.0, 0.0, {}), (levier, params, sortie)
    assert not any(k.startswith(levier) for k in sim._measure_params_tracker), sim._measure_params_tracker


# ===========================================================================
# 2. Effet direct au niveau du handler (G7, G11, W3-3, W3-5, W3-7)
# ===========================================================================

def _verifier_effet_direct(levier, params, sim=None):
    sim = sim if sim is not None else _sim_neuf()
    dep, rec, impacts = _appel(sim, levier, params)
    a = attendu(levier, params)
    assert dep == 0, (levier, params, 'dépenses', dep)
    # W3-5 / R-IDX : la recette de l'année EST le montant écrit, exactement.
    assert rec == a['rec'], (levier, params, 'recettes', rec, a['rec'])
    # G7 : clé `menages` présente dès qu'un euro bouge, cinq canaux.
    assert 'menages' in impacts and set(impacts['menages']) == set(CANAUX_MENAGES), impacts
    for canal in CANAUX_MENAGES:
        assert impacts['menages'][canal] == pytest.approx(a['menages'][canal], abs=1e-12), (
            levier, params, canal, impacts['menages'][canal], a['menages'][canal])
    # G11 : valeur exacte = constante signée × montant (première émission).
    assert impacts.get('gini', 0.0) == pytest.approx(a['gini'], abs=1e-12), (
        levier, params, 'gini', impacts.get('gini'), a['gini'])
    assert impacts.get('competitivite', 0.0) == pytest.approx(a['compet'], abs=1e-12), (
        levier, params, 'competitivite', impacts.get('competitivite'), a['compet'])
    # Règle v0.6.7 (lot 3) : un levier à flux budgétaire n'a pas d'effet direct
    # sur l'emploi — le multiplicateur porte déjà le canal de la demande.
    assert impacts.get('chomage', 0.0) == 0.0, (levier, params, 'chomage', impacts.get('chomage'))


@pytest.mark.parametrize('levier, params', CAS, ids=IDS)
def test_effet_direct_conforme_au_contrat(levier, params):
    _verifier_effet_direct(levier, params)


@pytest.mark.parametrize('levier, params', CAS, ids=IDS)
def test_g11_signe_des_effets_ponctuels(levier, params):
    """G11 : hausse de recette sur le patrimoine → Gini < 0 et compétitivité < 0 ;
    hausse de taxe indirecte → Gini > 0 ; IR ciblé (règle de la décote) : une
    hausse → Gini > 0 ; recette exceptionnelle : ni Gini ni compétitivité.
    Le signe suit celui du montant (aucun signe ajouté dans le handler)."""
    _, _, impacts = _appel(_sim_neuf(), levier, params)
    gini, compet = impacts.get('gini', 0.0), impacts.get('competitivite', 0.0)
    if levier == 'droits_succession':
        s = math.copysign(1, params['variation'])
        assert s * gini < 0 and s * compet < 0, (params, gini, compet)
    elif levier == 'fiscalite_indirecte':
        t, a = params.get('tva_ciblee', 0.0), params.get('accises_energie', 0.0)
        if t and not a:
            assert math.copysign(1, t) * gini > 0 and math.copysign(1, t) * compet < 0, (params, gini, compet)
        if a and not t:
            assert math.copysign(1, a) * gini > 0 and compet == 0.0, (params, gini, compet)
    elif levier == 'impot_revenu_cible':
        assert math.copysign(1, params['montant']) * gini > 0 and compet == 0.0, (params, gini, compet)
    else:
        assert gini == 0.0 and compet == 0.0, (params, gini, compet)


def test_w3_3_successions_plus_vingt_milliards():
    """W3-3 (S2) : +20 Md€ → Gini −0,020 et compétitivité −0,004 à 1e-12, canaux
    ménages nuls. Valeurs attendues dérivées : 20 × GINI_PATRIMOINE_PAR_MD et
    20 × COMPET_PATRIMOINE_PAR_MD (règle du levier patrimoine)."""
    haut = _spec('droits_succession', 'variation')['max']
    _, rec, impacts = _appel(_sim_neuf(), 'droits_succession', {'variation': haut})
    assert rec == haut
    assert impacts['gini'] == pytest.approx(haut * C.PATRIMOINE_GINI_PAR_10MD / 10, abs=1e-12)
    assert impacts['competitivite'] == pytest.approx(haut * C.PATRIMOINE_COMPET_PAR_10MD / 10, abs=1e-12)
    assert impacts['menages'] == canaux_menages()


def test_w3_7_canaux_indirects():
    """W3-7 : la TVA à taux réduits pèse à 100 % sur les prix des ménages, les
    accises à ``PART_CONSOMMATION_MENAGES_TVA_TOTALE`` (convention de
    ``tva_energie``) ; aucun autre canal."""
    t = _mi_haut('fiscalite_indirecte', 'tva_ciblee')
    a = _mi_haut('fiscalite_indirecte', 'accises_energie')
    _, _, seul_t = _appel(_sim_neuf(), 'fiscalite_indirecte', {'tva_ciblee': t})
    _, _, seul_a = _appel(_sim_neuf(), 'fiscalite_indirecte', {'accises_energie': a})
    assert seul_t['menages'] == canaux_menages(prelevements_indirects=t)
    assert seul_a['menages']['prelevements_indirects'] == pytest.approx(
        C.PART_CONSOMMATION_MENAGES_TVA_TOTALE * a, abs=1e-12)
    assert all(v == 0.0 for c, v in seul_a['menages'].items() if c != 'prelevements_indirects')


@pytest.mark.parametrize('levier, params', CAS, ids=IDS)
def test_g12_r_idx_independant_du_pib_de_l_annee_et_des_prix(levier, params):
    """G12 / R-IDX (§ 1.1) : un montant en Md€ est CONSTANT en euros courants —
    la sortie du handler ne dépend ni de l'année, ni du PIB, ni de l'inflation,
    ni du chômage (aucune indexation, aucun indice d'assiette)."""
    _verifier_r_idx_handler(levier, params)


def _verifier_r_idx_handler(levier, params):
    reference = _canon(_appel(_sim_neuf(), levier, params))
    for etat in ({'year': FIN_MANDAT}, {'year': DEBUT}, {'gdp': 1.25 * C.PIB_BASE_2025_MD_EUR},
                 {'inflation': 0.05}, {'unemployment': 0.11}):
        assert _canon(_appel(_sim_neuf(), levier, params, **etat)) == reference, (levier, params, etat)
    assert _appel(_sim_neuf(), levier, params)[1] == attendu(levier, params)['rec']


def test_recette_exceptionnelle_ne_lit_pas_l_annee():
    """§ 1.2-11 : le handler rend le montant qu'il reçoit ; c'est le cadre qui
    pose le montant à zéro hors de l'année choisie (profil, chantier W1)."""
    m = _mi_haut('recette_exceptionnelle', 'montant')
    sorties = {an: _canon(_appel(_sim_neuf(), 'recette_exceptionnelle', {'montant': m}, year=an))
               for an in range(DEBUT, DEBUT + 10)}
    assert len({json.dumps(s, sort_keys=True) for s in sorties.values()}) == 1
    assert _appel(_sim_neuf(), 'recette_exceptionnelle', {'montant': m})[1] == m


# --- G5 : signe et monotonie de l'effet direct sur le solde -----------------

@pytest.mark.parametrize('levier, param', [(l, p) for l in W3 for p in C.NEUTRES_RELEASE_E[l]])
def test_g5_effet_direct_sur_le_solde_monotone_sur_tout_le_domaine(levier, param):
    """G5 : sur 11 points du domaine, Δsolde direct = Δrec − Δdép = x exactement,
    strictement croissant, du signe de x (aucun point de retournement)."""
    s = _spec(levier, param)
    grille = [s['min'] + (s['max'] - s['min']) * k / 10 for k in range(11)]
    soldes = []
    for x in grille:
        dep, rec, _ = _appel(_sim_neuf(), levier, {param: x})
        soldes.append(rec - dep)
        assert rec - dep == x, (levier, param, x, rec, dep)
        assert (rec - dep > 0) == (x > 0) and (rec - dep < 0) == (x < 0)
    assert all(b > a for a, b in zip(soldes, soldes[1:])), soldes


# --- G6 : symétrie ------------------------------------------------------------

@pytest.mark.parametrize('levier, param', [(l, p) for l in W3 for p in C.NEUTRES_RELEASE_E[l]
                                           if _signe(l, p)])
def test_g6_symetrie(levier, param):
    """G6 : +x et −x donnent des effets directs opposés (budget, canaux ménages,
    Gini, compétitivité). ``recette_exceptionnelle`` (domaine [0 ; 60]) n'est pas
    signée."""
    x = _symetrique(levier, param)
    dp, rp, ip = _appel(_sim_neuf(), levier, {param: x})
    dm, rm, im = _appel(_sim_neuf(), levier, {param: -x})
    assert rp == -rm and rp != 0 and dp == -dm
    for canal in CANAUX_MENAGES:
        assert ip['menages'][canal] == pytest.approx(-im['menages'][canal], abs=1e-15)
    assert ip.get('gini', 0.0) == pytest.approx(-im.get('gini', 0.0), abs=1e-15)
    assert ip.get('competitivite', 0.0) == pytest.approx(-im.get('competitivite', 0.0), abs=1e-15)


def test_recette_exceptionnelle_non_signee():
    s = _spec('recette_exceptionnelle', 'montant')
    assert s['min'] == _neutre('recette_exceptionnelle', 'montant') == 0 < s['max']


# --- Coefficients réutilisés : nommés, jamais recopiés (§ 1.1, § 1.3) --------

LECTURES = {
    'droits_succession': ('GINI_PATRIMOINE_PAR_MD', 'COMPET_PATRIMOINE_PAR_MD'),
    'fiscalite_indirecte': ('GINI_TVA_PAR_MD', 'GINI_TVA_ENERGIE_PAR_MD', 'COMPET_TVA_PAR_MD',
                            'PART_CONSOMMATION_MENAGES_TVA_TOTALE'),
    'impot_revenu_cible': ('GINI_IR_DECOTE_PAR_MD',),
}


def _flottants_du_code(fonction):
    """Constantes flottantes du CODE d'une fonction (docstring et commentaires
    exclus), hors zéro."""
    arbre = ast.parse(textwrap.dedent(inspect.getsource(fonction)))
    corps = arbre.body[0]
    noeuds = corps.body[1:] if (corps.body and isinstance(corps.body[0], ast.Expr)
                                and isinstance(getattr(corps.body[0], 'value', None), ast.Constant)
                                and isinstance(corps.body[0].value.value, str)) else corps.body
    trouves = []
    for noeud in noeuds:
        for n in ast.walk(noeud):
            if isinstance(n, ast.Constant) and isinstance(n.value, float) and n.value != 0.0:
                trouves.append(n.value)
    return trouves


@pytest.mark.parametrize('levier', list(LECTURES))
def test_handler_lit_les_constantes_nommees(levier):
    fonction = getattr(mod_recettes.RecettesMontantsMixin, f'_apply_{levier}')
    source = inspect.getsource(fonction)
    for nom in LECTURES[levier]:
        assert re.search(rf'\b{nom}\b', source), f"_apply_{levier} ne lit pas {nom}"
        assert hasattr(mod_recettes, nom), f"recettes_montants n'importe pas {nom}"
    assert not _flottants_du_code(fonction), (levier, _flottants_du_code(fonction))


@pytest.mark.parametrize('levier', list(LECTURES))
def test_mutation_constante_doublee_double_l_effet(levier, monkeypatch):
    """Le handler LIT la constante du module (pas une copie locale) : doubler
    chaque coefficient Gini/compétitivité double les effets ponctuels."""
    params = {p: _mi_haut(levier, p) for p in C.NEUTRES_RELEASE_E[levier]}
    _, _, ref = _appel(_sim_neuf(), levier, params)
    for nom in LECTURES[levier]:
        if nom.startswith(('GINI_', 'COMPET_')):
            assert hasattr(mod_recettes, nom), nom
            monkeypatch.setattr(mod_recettes, nom, 2 * getattr(C, nom))
    _, _, mut = _appel(_sim_neuf(), levier, params)
    assert ref.get('gini', 0.0) != 0.0
    assert mut.get('gini', 0.0) == pytest.approx(2 * ref['gini'], rel=1e-12)
    assert mut.get('competitivite', 0.0) == pytest.approx(2 * ref.get('competitivite', 0.0), rel=1e-12)


@pytest.mark.parametrize('levier, nom', [(l, n) for l, noms in LECTURES.items() for n in noms
                                         if n.startswith('GINI_')])
def test_mutation_signe_inverse_rougit_g11(levier, nom, monkeypatch):
    """R-1 (§ 6.8) : G11 rouge si on inverse un signe. Précondition : le
    vérificateur passe sur le moteur réel."""
    params = {p: _mi_haut(levier, p) for p in C.NEUTRES_RELEASE_E[levier]}
    _verifier_effet_direct(levier, params)
    assert hasattr(mod_recettes, nom), nom
    monkeypatch.setattr(mod_recettes, nom, -getattr(C, nom))
    with pytest.raises(AssertionError):
        _verifier_effet_direct(levier, params)


# ===========================================================================
# 3. Effets ponctuels en incrément (G8, G8-retour), niveau handler
# ===========================================================================

def _verifier_ponctuel_handler(levier, params):
    """Émis une fois ; sous une montée par paliers, Σ incréments = effet du
    palier ; retour au neutre → l'effet est RENDU (Σ = 0)."""
    a = attendu(levier, params)
    # (1) Émis une fois.
    sim = _sim_neuf()
    ginis = [_appel(sim, levier, params, year=an)[2].get('gini', 0.0) for an in (2028, 2029, 2030)]
    assert ginis[0] == pytest.approx(a['gini'], abs=1e-12) and ginis[1:] == [0.0, 0.0], ginis
    # (2) Rampe en cinq paliers (cadre § 2.1 : k/5 puis la valeur exacte).
    sim = _sim_neuf()
    paliers = [{k: v * j / 5 for k, v in params.items()} for j in range(1, 5)] + [params, params]
    ginis, compets = [], []
    for an, p in zip(range(2028, 2034), paliers):
        impacts = _appel(sim, levier, p, year=an)[2]
        ginis.append(impacts.get('gini', 0.0))
        compets.append(impacts.get('competitivite', 0.0))
    assert sum(ginis) == pytest.approx(a['gini'], abs=1e-12), ginis
    assert sum(compets) == pytest.approx(a['compet'], abs=1e-12), compets
    assert ginis[-1] == 0.0
    # (3) G8-retour : niveau, puis neutre deux années.
    _verifier_retour_handler(levier, params)


def _verifier_retour_handler(levier, params):
    a = attendu(levier, params)
    neutre = dict(C.NEUTRES_RELEASE_E[levier])
    sim = _sim_neuf()
    sorties = [_appel(sim, levier, p, year=an) for an, p in zip((2028, 2029, 2030), (params, neutre, neutre))]
    ginis = [s[2].get('gini', 0.0) for s in sorties]
    compets = [s[2].get('competitivite', 0.0) for s in sorties]
    assert sorties[1][1] == 0 and sorties[2][1] == 0, 'recette non revenue à zéro au neutre'
    assert ginis[1] == pytest.approx(-a['gini'], abs=1e-12), ('effet Gini non rendu au retour', ginis)
    assert sum(ginis) == pytest.approx(0.0, abs=1e-12), ginis
    assert sum(compets) == pytest.approx(0.0, abs=1e-12), compets


@pytest.mark.parametrize('levier, params', CAS, ids=IDS)
def test_g8_effets_ponctuels_en_increment(levier, params):
    _verifier_ponctuel_handler(levier, params)


# ===========================================================================
# 4. Simulation complète (G4, G5, G8, G10', G12, deux portes)
# ===========================================================================

def _verifier_r_idx_simulation(levier, params, annee_debut, *, cache=True):
    """G12 / W3-5 : Δrec_t = montant à 1e-12 chaque année d'application (2026-2035
    en historique, 2028-2035 en cadre), rien avant le début, levier sans échec."""
    _, _, rapport = _simuler({levier: params}, annee_debut, cache=cache)
    a = attendu(levier, params)
    debut = annee_debut or DEBUT
    effets = _effets(rapport, levier)
    assert sorted(effets) == list(range(DEBUT, DEBUT + 10))
    for an, e in effets.items():
        if an < debut:
            assert e is None or (e.get('recettes', 0) == 0 and e.get('depenses', 0) == 0), (an, e)
            continue
        assert e is not None and not e.get(HANDLER_FAILED_KEY), (levier, an, e)
        assert e['recettes'] == pytest.approx(a['rec'], abs=1e-12), (levier, params, an, e['recettes'])
        assert e.get('depenses', 0) == 0, (levier, an, e)
    assert rapport['valid'] is True, rapport['warnings']


@pytest.mark.parametrize('annee_debut', [None, DEBUT_CADRE], ids=['historique', 'cadre2028'])
@pytest.mark.parametrize('levier, params', CAS_RECURRENTS, ids=IDS_RECURRENTS)
def test_g12_w3_5_montant_constant_chaque_annee(levier, params, annee_debut):
    _verifier_r_idx_simulation(levier, params, annee_debut)


def test_g12_recette_exceptionnelle_montant_l_annee_de_debut():
    """Recette exceptionnelle (mode cadre ; refusée en historique par W1) : le
    montant entier l'année de début. Les autres années relèvent du profil
    « une seule année » (W1, test W3-9 plus bas)."""
    m = _mi_haut('recette_exceptionnelle', 'montant')
    _, _, rapport = _simuler({'recette_exceptionnelle': {'montant': m}}, DEBUT_CADRE)
    effets = _effets(rapport, 'recette_exceptionnelle')
    assert effets[DEBUT_CADRE] is not None and not effets[DEBUT_CADRE].get(HANDLER_FAILED_KEY)
    assert effets[DEBUT_CADRE]['recettes'] == m
    assert all(effets[an] is None for an in range(DEBUT, DEBUT_CADRE))
    assert rapport['valid'] is True, rapport['warnings']


def _verifier_ponctuel_simulation(levier, params, annee_debut, *, cache=True):
    """G8 : Gini et compétitivité émis UNE fois, l'année d'entrée, égaux à
    l'effet du niveau ; zéro les autres années ; rien avant le début."""
    _, _, rapport = _simuler({levier: params}, annee_debut, cache=cache)
    a = attendu(levier, params)
    debut = annee_debut or DEBUT
    for canal, cle in (('gini', 'gini'), ('compet', 'competitivite')):
        serie = {an: (e or {}).get(cle, 0.0) for an, e in _effets(rapport, levier).items()}
        assert serie[debut] == pytest.approx(a[canal], abs=1e-12), (levier, canal, serie)
        assert all(abs(v) <= 1e-15 for an, v in serie.items() if an != debut), (levier, canal, serie)
        assert sum(serie.values()) == pytest.approx(a[canal], abs=1e-12)


@pytest.mark.parametrize('annee_debut', [None, DEBUT_CADRE], ids=['historique', 'cadre2028'])
@pytest.mark.parametrize('levier, params', CAS_RECURRENTS, ids=IDS_RECURRENTS)
def test_g8_simulation_emis_une_fois(levier, params, annee_debut):
    _verifier_ponctuel_simulation(levier, params, annee_debut)


def _solde_primaire(detail):
    return (detail['Recettes_Totales'] - detail['Dépenses_Totales']).tolist()


# Recette exceptionnelle : mode cadre seulement (refusée en mode historique par
# W1, contrat § 2.1).
CAS_SOLDE = [(l, p, ad) for l, p in CAS for ad in (None, DEBUT_CADRE)
             if not (l == 'recette_exceptionnelle' and ad is None)]
IDS_SOLDE = [f"{i}-{'historique' if ad is None else 'cadre2028'}"
             for (l, p), i in zip(CAS, IDS) for ad in (None, DEBUT_CADRE)
             if not (l == 'recette_exceptionnelle' and ad is None)]


@pytest.mark.parametrize('levier, params, annee_debut', CAS_SOLDE, ids=IDS_SOLDE)
def test_g5_signe_et_ordre_de_grandeur_du_solde(levier, params, annee_debut):
    """Solde primaire (Md€), écart au même scénario sans le levier :
    - année d'entrée : = Δrec exactement (1e-9) — les impulsions agissent en t+1
      (``_stocker_impulsions`` lit ``_last_impacts``) et le levier n'a pas
      d'effet direct sur l'emploi ;
    - avant : 0 ;
    - après, pour un levier récurrent : du signe du montant chaque année (le
      retour du multiplicateur fiscal ne renverse jamais le sens de l'effet).
      Pas de borne d'amplitude ici : à long terme, une baisse de recette peut
      creuser le solde primaire d'un peu plus que son montant (traînée de dette
      sur la croissance potentielle, ``growth.py``) ; l'ordre de grandeur est
      verrouillé par le test suivant (même trajectoire que tout levier W3 de
      même montant). Montant net nul (TVA et accises opposées) : aucun écart
      jusqu'à l'année d'entrée ; ensuite, la hausse de TVA passe dans les prix
      l'année suivante (canal de prix de la TVA, revue adverse de la release
      E), pas les accises : l'écart n'est plus nul, et son signe n'est pas
      contraint ici (verrouillé par les tests du passage dans les prix).
    Recette exceptionnelle : année d'entrée seulement (elle cesse ensuite)."""
    _, d0, _ = _simuler({}, annee_debut, pleine=True)
    _, d1, rapport = _simuler({levier: params}, annee_debut, pleine=True)
    assert rapport['valid'] is True, rapport['warnings']
    annees = [int(a) for a in d1['Année']]
    ecart = {an: b - a for an, a, b in zip(annees, _solde_primaire(d0), _solde_primaire(d1))}
    rec = attendu(levier, params)['rec']
    debut = annee_debut or DEBUT
    assert ecart[debut] == pytest.approx(rec, abs=1e-9), (levier, params, ecart)
    assert all(abs(ecart[an]) <= 1e-9 for an in annees if an < debut), ecart
    if levier in RECURRENTS and rec == 0 and params.get('tva_ciblee', 0.0) > 0:
        assert all(abs(ecart[an]) <= 1e-9 for an in annees if an <= debut), ecart
        assert any(abs(ecart[an]) > 1e-6 for an in annees if an > debut), ('NON_VACUITE', ecart)
    elif levier in RECURRENTS and rec == 0:
        assert all(abs(v) <= 1e-9 for v in ecart.values()), ecart
    elif levier in RECURRENTS:
        for an in annees:
            if an > debut:
                assert ecart[an] * rec > 0, (levier, params, an, ecart)


# Colonnes macro et budgétaires : tout sauf les indicateurs propres à chaque
# levier (Gini, compétitivité, pouvoir d'achat) et l'inflation IPC, que la
# fiscalité indirecte déplace par le coin de prix (engine/rdb.py), sans
# rétroaction sur le budget ni sur la croissance.
COLONNES_MACRO = ['PIB', 'Croissance %', 'Inflation %', 'Déficit', 'Déficit/PIB %', 'Dette',
                  'Dette/PIB %', 'Chômage %', 'Recettes/PIB %', 'Dépenses/PIB %']
COLONNES_DETAIL = ['Recettes_Totales', 'Dépenses_Totales', 'Intérêts_Dette', 'Multiplicateur',
                   'PIB_Réel_Base2025', 'Output_Gap %']


def _meme_montant(montant):
    """Un bloc par levier récurrent (et par paramètre de la fiscalité
    indirecte) portant la même recette ``montant``."""
    return [('droits_succession', {'variation': montant}),
            ('fiscalite_indirecte', {'tva_ciblee': montant}),
            ('fiscalite_indirecte', {'accises_energie': montant}),
            ('impot_revenu_cible', {'montant': montant})]


# Montant commun : le plus grand |x| que les quatre domaines admettent des deux
# côtés du neutre, divisé par deux (sonde symétrique).
MONTANT_COMMUN = min(_symetrique(l, p) for l, b in _meme_montant(1.0) for p in b)


@pytest.mark.parametrize('annee_debut', [None, DEBUT_CADRE], ids=['historique', 'cadre2028'])
@pytest.mark.parametrize('signe', [1, -1], ids=['hausse', 'baisse'])
def test_g5_meme_montant_meme_trajectoire_macro(signe, annee_debut):
    """Ordre de grandeur du solde et neutralité de traitement (§ 1.2-4, 9, 10 :
    canal « recettes » du multiplicateur fiscal, aucun effet direct sur l'emploi
    ni sur l'offre) : à recette égale, les trois leviers récurrents donnent la
    MÊME trajectoire macro et budgétaire, en pleine précision, à 1e-12 en
    relatif (pas au bit : en mode cadre, l'ordre de sommation des impulsions
    suit la place du levier parmi ceux du droit en vigueur, écart d'un ulp sur
    la colonne « Multiplicateur »). Un canal caché (emploi, offre, indexation)
    propre à un levier fait rougir ce test de plusieurs ordres de grandeur.

    Seule exception, nommée : une HAUSSE de TVA à taux réduits passe dans les
    prix l'année qui suit son entrée en vigueur, comme la TVA normale (revue
    adverse de la release E ; une baisse n'y passe pas, règle de ``tva_rate``).
    En hausse, la TVA a donc la même trajectoire jusqu'à l'année d'entrée
    comprise, puis une inflation plus forte l'année suivante."""
    m = signe * MONTANT_COMMUN
    sorties = [(l, p, _simuler({l: p}, annee_debut, pleine=True)) for l, p in _meme_montant(m)]
    (l0, p0, (df0, det0, r0)) = sorties[0]
    assert r0['valid'] is True, r0['warnings']
    debut = annee_debut or DEBUT
    for levier, params, (df, det, rapport) in sorties[1:]:
        assert rapport['valid'] is True, rapport['warnings']
        prix = signe > 0 and 'tva_ciblee' in params
        lignes = (df['Année'] <= debut) if prix else slice(None)
        for c in COLONNES_MACRO:
            assert df[c][lignes].tolist() == pytest.approx(df0[c][lignes].tolist(), rel=1e-12, abs=1e-12), (
                levier, params, c)
        for c in COLONNES_DETAIL:
            assert det[c][lignes].tolist() == pytest.approx(det0[c][lignes].tolist(), rel=1e-12, abs=1e-12), (
                levier, params, c)
        if prix:
            i, i0 = (dict(zip(x['Année'], x['Inflation %'])) for x in (df, df0))
            assert i[debut + 1] - i0[debut + 1] > 1e-3, (i[debut + 1], i0[debut + 1])
    # Le coin de prix : une hausse de TVA renchérit la consommation des ménages
    # l'année d'entrée, une hausse d'impôt direct non.
    ipc = {(l, tuple(p)): dict(zip(df['Année'], df['Inflation IPC %'])) for l, p, (df, _, _) in sorties}
    tva, ir = ipc[('fiscalite_indirecte', ('tva_ciblee',))], ipc[('impot_revenu_cible', ('montant',))]
    assert signe * (tva[debut] - ir[debut]) > 0, (tva[debut], ir[debut])


@pytest.mark.parametrize('levier, params', CAS, ids=IDS)
def test_deux_portes_strict_identique_au_tolerant_dans_le_domaine(levier, params):
    """Dans le domaine, aucune correction : la porte stricte ne lève pas et rend
    les mêmes sorties au bit que la porte tolérante (mode cadre)."""
    df_t, det_t, rap_t = _simuler({levier: params}, DEBUT_CADRE, strict=False)
    df_s, det_s, rap_s = _simuler({levier: params}, DEBUT_CADRE, strict=True)
    assert df_s.equals(df_t) and det_s.equals(det_t)
    assert _canon(rap_s) == _canon(rap_t)
    assert rap_t['valid'] is True and not rap_t['leviers_ecretes'], rap_t['warnings']


# --- G4 : domaine ---------------------------------------------------------------

HORS_DOMAINE = [(l, p, sens) for l in W3 for p in C.NEUTRES_RELEASE_E[l] for sens in ('haut', 'bas')]


@pytest.mark.parametrize('levier, param, sens', HORS_DOMAINE,
                         ids=[f'{l}.{p}-{s}' for l, p, s in HORS_DOMAINE])
def test_g4_hors_domaine_ecretage_trace_et_effet_a_la_borne(levier, param, sens):
    """G4, W3-4 : au-delà d'une borne, tolérant → valeur ramenée à la borne,
    tracée (``report.leviers_ecretes``, motif ``domaine``), effet calculé à la
    borne ; strict → erreur d'entrée. Borne basse de ``droits_succession`` =
    ``−DMTG_2025_MD`` (sourcée, jamais relevée)."""
    s = _spec(levier, param)
    largeur = s['max'] - s['min']
    demande = s['max'] + largeur if sens == 'haut' else s['min'] - largeur
    borne = s['max'] if sens == 'haut' else s['min']
    if levier == 'droits_succession' and sens == 'bas':
        assert borne == pytest.approx(-C.DMTG_2025_MD, abs=1e-9)
    _, _, rapport = _simuler({levier: {param: demande}}, DEBUT_CADRE)
    assert rapport['valid'] is False
    assert {'levier': f'{levier}.{param}', 'demande': demande, 'applique': float(borne),
            'borne': list(PARAM_DOMAINS[levier][param]), 'motif': 'domaine'} in rapport['leviers_ecretes']
    e = _effets(rapport, levier)[DEBUT_CADRE]
    attendu_rec = attendu(levier, {param: borne})['rec']
    if attendu_rec == 0:
        assert e is None or e.get('recettes', 0) == 0
    else:
        assert e is not None and not e.get(HANDLER_FAILED_KEY), e
        assert e['recettes'] == pytest.approx(attendu_rec, abs=1e-12)
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1'}):
        assert _leve_entree_invalide(lambda: BudgetSimulatorV45(
            periods=10, mesures={levier: {param: demande}}, annee_debut=DEBUT_CADRE).simulate(),
            ValeurInvalide)


def test_w3_4_successions_moins_vingt_cinq():
    """W3-4 (S4) : −25 Md€ → écrêté à −DMTG_2025_MD, effet appliqué à la borne."""
    _, _, rapport = _simuler({'droits_succession': {'variation': -25.0}}, None)
    lignes = [l for l in rapport['leviers_ecretes'] if l['levier'] == 'droits_succession.variation']
    assert lignes and lignes[0]['applique'] == pytest.approx(-C.DMTG_2025_MD, abs=1e-12)
    effets = _effets(rapport, 'droits_succession')
    assert all(e is not None and e['recettes'] == pytest.approx(-C.DMTG_2025_MD, abs=1e-12)
               for e in effets.values()), effets


@pytest.mark.parametrize('valeur', [math.nan, math.inf, -math.inf], ids=['nan', 'inf', '-inf'])
@pytest.mark.parametrize('levier', W3)
def test_g4_valeurs_non_finies_refusees(levier, valeur):
    """G4 : NaN et ±inf → tolérant : clé retirée, levier au neutre, correction
    tracée ; strict : erreur d'entrée. Jamais un chiffre empoisonné."""
    param = next(iter(C.NEUTRES_RELEASE_E[levier]))
    df_ref, _, _ = _simuler({}, DEBUT_CADRE)
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': ''}):
        df, _, rapport = BudgetSimulatorV45(periods=10, mesures={levier: {param: valeur}},
                                            annee_debut=DEBUT_CADRE).simulate()
    assert rapport['valid'] is False
    assert any('non finie' in w for w in rapport['warnings']), rapport['warnings']
    assert df.equals(df_ref)
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1'}):
        assert _leve_entree_invalide(lambda: BudgetSimulatorV45(
            periods=10, mesures={levier: {param: valeur}}, annee_debut=DEBUT_CADRE).simulate())


# --- G10' : appartenance au total mesuré contre le seuil de 10 % -------------

def _abaisser_le_seuil(monkeypatch, seuil):
    """Seuil de l'impact total abaissé pour le test : la constante garde son nom
    (contrat § 5.4) ; on la remplace là où le calcul la lit (orchestrateur) et
    à sa source (constants), pour rester valable si W1 déplace la lecture."""
    monkeypatch.setattr(C, 'PLAFOND_IMPACT_TOTAL_PIB', seuil)
    monkeypatch.setattr(mod_orchestrateur, 'PLAFOND_IMPACT_TOTAL_PIB', seuil, raising=False)


@pytest.mark.parametrize('levier, params', UN_PAR_RECURRENT, ids=[c[0] for c in UN_PAR_RECURRENT])
def test_g10_prime_le_levier_entre_dans_le_total_mesure(levier, params, monkeypatch):
    """G10' (appartenance) : en mode historique, le statu quo ne mesure aucun
    écart (total nul) ; avec le seuil abaissé à la moitié du levier, le levier
    SEUL franchit le seuil chaque année (``cadre.plafond_total.annees``). La
    suppression de la réduction relève de W1 (W1-8)."""
    rec = abs(attendu(levier, params)['rec'])
    _abaisser_le_seuil(monkeypatch, rec / (2 * C.PIB_BASE_2025_MD_EUR))
    _, _, sans = _simuler({}, None, cache=False)
    _, _, avec = _simuler({levier: params}, None, cache=False)
    assert sans['cadre']['plafond_total']['annees'] == []
    assert avec['cadre']['plafond_total']['annees'] == list(range(DEBUT, DEBUT + 10))


def test_g10_prime_recette_exceptionnelle_l_annee_de_debut(monkeypatch):
    """Même propriété pour la recette exceptionnelle, en mode cadre : le seuil
    est posé entre le total du statu quo de 2028 (écarts du droit en vigueur
    au défaut du moteur, relus dans le rapport) et ce total + le montant."""
    m = _spec('recette_exceptionnelle', 'montant')['max']
    sim = BudgetSimulatorV45(periods=10, mesures={}, annee_debut=DEBUT_CADRE)
    _, _, base = sim.simulate()
    e = _par_annee(base)[DEBUT_CADRE]
    total = (abs(sum(v.get('depenses', 0) for v in e.values() if isinstance(v, dict)))
             + abs(sum(v.get('recettes', 0) for v in e.values() if isinstance(v, dict))))
    pib = sim._pib_nominal_par_annee[DEBUT_CADRE]
    _abaisser_le_seuil(monkeypatch, (total + m / 2) / pib)
    _, _, sans = _simuler({}, DEBUT_CADRE, cache=False)
    _, _, avec = _simuler({'recette_exceptionnelle': {'montant': m}}, DEBUT_CADRE, cache=False)
    assert DEBUT_CADRE not in sans['cadre']['plafond_total']['annees']
    assert DEBUT_CADRE in avec['cadre']['plafond_total']['annees']


# --- API : deux portes -----------------------------------------------------------

@pytest.fixture(scope='module')
def _client():
    spec = importlib.util.spec_from_file_location('api_release_e_w3', RACINE / 'api.py')
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return TestClient(module.app, raise_server_exceptions=False)


@pytest.mark.parametrize('levier, params', UN_PAR_LEVIER, ids=[c[0] for c in UN_PAR_LEVIER])
def test_api_strict_accepte_une_valeur_du_domaine(levier, params, _client, monkeypatch):
    monkeypatch.setenv('BUDGETLAB_STRICT', '1')
    r = _client.post('/simulate', json={'periods': 10, 'annee_debut': DEBUT_CADRE,
                                        'mesures': {levier: params}})
    assert r.status_code == 200, r.text[:500]
    assert r.json()['report']['valid'] is True


@pytest.mark.parametrize('levier', W3)
def test_api_strict_refuse_hors_domaine(levier, _client, monkeypatch):
    param = next(iter(C.NEUTRES_RELEASE_E[levier]))
    s = _spec(levier, param)
    monkeypatch.setenv('BUDGETLAB_STRICT', '1')
    r = _client.post('/simulate', json={'periods': 10, 'annee_debut': DEBUT_CADRE,
                                        'mesures': {levier: {param: s['max'] + (s['max'] - s['min'])}}})
    assert r.status_code == 422, r.text[:500]


# --- G1 : écritures du neutre, 10 scénarios publiés, deux modes, deux portes -

BASES_G1 = {'statu_quo': {}, 'droit_en_vigueur': _DROIT, **_SCENARIOS_PUBLIES}
VARIANTES_NEUTRES = [
    ('droits_succession', {'variation': 0.0}),
    ('droits_succession', {'variation': -0.0}),
    ('fiscalite_indirecte', {'accises_energie': 0.0}),
    ('fiscalite_indirecte', {'tva_ciblee': -0.0, 'accises_energie': 0.0}),
    ('impot_revenu_cible', {'montant': 0.0}),
    ('recette_exceptionnelle', {'montant': -0.0}),
]


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
@pytest.mark.parametrize('annee_debut', [None, DEBUT_CADRE], ids=['historique', 'cadre2028'])
@pytest.mark.parametrize('levier, bloc', VARIANTES_NEUTRES,
                         ids=[f'{l}-{json.dumps(b)}' for l, b in VARIANTES_NEUTRES])
def test_g1_ecritures_du_neutre_identiques_au_bit(levier, bloc, annee_debut, strict):
    """G1 (W3-1) : complète le G1 du socle (bloc des neutres du registre) par les
    écritures du zéro qu'un programme peut envoyer (flottant, zéro négatif, bloc
    partiel) : sorties identiques au bit, rapport compris, sur le statu quo, le
    droit en vigueur et les 10 scénarios publiés (dépôt parent)."""
    if len(BASES_G1) < 12:
        assert len(BASES_G1) == 2  # dépôt public seul
    # Release de paramètres P : une base qui ENCODE le levier n'est pas une base
    # de G1 (y poser le neutre retirerait sa mesure, cadre_harness.bases_g1).
    for nom, base in bases_g1(BASES_G1, levier, annee_debut).items():
        ref_df, ref_det, ref_rap = _simuler(base, annee_debut, strict)
        df, det, rap = _simuler({**base, levier: bloc}, annee_debut, strict)
        assert df.equals(ref_df), (nom, levier, bloc, 'trajectoire')
        assert det.equals(ref_det), (nom, levier, bloc, 'détail')
        assert _canon(rap) == _canon(ref_rap), (nom, levier, bloc, 'rapport')


def test_g1_recette_exceptionnelle_neutre_acceptee_en_mode_historique():
    """Le refus de la recette exceptionnelle en mode historique (W1, § 2.1) ne
    vise qu'un montant NON nul : un bloc neutre reste un statu quo, rapport
    valide (cohérence avec le G1 du socle)."""
    ref = _simuler({}, None)
    sortie = _simuler({'recette_exceptionnelle': {'montant': 0}}, None)
    assert sortie[0].equals(ref[0]) and _canon(sortie[2]) == _canon(ref[2])
    assert sortie[2]['valid'] is True


# ===========================================================================
# 5. Anti-double-compte (§ 4.1 : règles I, IR, E, D ; S pour les successions)
# ===========================================================================

def _sonde_param(levier, param):
    """Valeur non neutre d'un paramètre d'un levier EXISTANT, tirée du registre :
    mi-chemin du défaut et de la borne haute (vers la basse si le défaut est la
    borne haute), comme les sondes du socle ; un interrupteur (``toggle``) est
    basculé."""
    spec = REGISTRE[levier]['parametres'][param]
    d = spec['valeur_defaut']
    if spec.get('type') == 'toggle':
        return spec['max'] if d != spec['max'] else spec['min']
    return d + (spec['max'] - d) / 2 if spec['max'] > d else d - (d - spec['min']) / 2


# Paramètre sondé de chaque levier existant concerné par une règle du § 4.1 :
# celui que la règle nomme (taxe carbone pour I), sinon le premier du registre.
PARAM_SONDE = {'tva_rate': 'taux', 'tva_energie': 'taux', 'transition_ecologique': 'taxe_carbone',
               'impot_revenu': 'taux_superieur', 'elargissement_ir': 'taux_contribuables_cible',
               'abattement_retraites': 'reforme_active', 'taxe_superprofits': 'intensite',
               'fiscalite_patrimoine': 'intensite', 'csg': 'taux'}


def _sonde(levier):
    param = PARAM_SONDE[levier]
    return {param: _sonde_param(levier, param)}


# Règle → (levier W3, paramètres, leviers existants qui ne doivent pas bouger, mode).
REGLES = {
    'I': ('fiscalite_indirecte', {'tva_ciblee': _mi_haut('fiscalite_indirecte', 'tva_ciblee'),
                                  'accises_energie': _mi_haut('fiscalite_indirecte', 'accises_energie')},
          ('tva_rate', 'tva_energie', 'transition_ecologique'), None),
    'IR': ('impot_revenu_cible', {'montant': _mi_bas('impot_revenu_cible', 'montant')},
           ('impot_revenu', 'elargissement_ir', 'abattement_retraites'), None),
    'E': ('recette_exceptionnelle', {'montant': _mi_haut('recette_exceptionnelle', 'montant')},
          ('taxe_superprofits',), DEBUT_CADRE),
    'S': ('droits_succession', {'variation': _mi_haut('droits_succession', 'variation')},
          ('fiscalite_patrimoine',), None),
}


def _bloc(levier):
    return _sonde(levier)


def _verifier_independance_handler(levier_w3, params_w3, autre):
    """Aucune lecture croisée : l'autre levier rend la même sortie au bit avec
    ou sans le levier W3 dans ``self.mesures``, et réciproquement. Précondition :
    le levier W3 est appliqué (effet direct du contrat)."""
    _verifier_effet_direct(levier_w3, params_w3)
    p_autre = _bloc(autre)
    sans = _appel(_sim_neuf({autre: p_autre}), autre, p_autre)
    avec = _appel(_sim_neuf({autre: p_autre, levier_w3: params_w3}), autre, p_autre)
    assert _canon(avec) == _canon(sans), (autre, 'lit', levier_w3)
    sans = _appel(_sim_neuf({levier_w3: params_w3}), levier_w3, params_w3)
    avec = _appel(_sim_neuf({levier_w3: params_w3, autre: p_autre}), levier_w3, params_w3)
    assert _canon(avec) == _canon(sans), (levier_w3, 'lit', autre)


@pytest.mark.parametrize('regle, autre', [(r, a) for r, (_, _, autres, _) in REGLES.items() for a in autres])
def test_ad_independance_au_niveau_du_handler(regle, autre):
    """§ 4.1 : I (W3-6), IR (W3-8), E (W3-10) ; S : successions × patrimoine,
    dont l'exclusion mutuelle en simulation est la règle X1 de W1 (W1-5)."""
    levier, params, _, _ = REGLES[regle]
    _verifier_independance_handler(levier, params, autre)


def _verifier_independance_simulation(regle, *, cache=True):
    """Année d'entrée (même état macro avec et sans le levier W3) : impacts des
    leviers existants identiques au bit avec ou sans le levier W3 ; impact du
    levier W3 identique à celui qu'il a seul. Précondition : levier W3 appliqué."""
    levier, params, autres, annee_debut = REGLES[regle]
    base = {a: _bloc(a) for a in autres}
    entree = annee_debut or DEBUT
    sans = _par_annee(_simuler(base, annee_debut, cache=cache)[2])[entree]
    avec = _par_annee(_simuler({**base, levier: params}, annee_debut, cache=cache)[2])[entree]
    seul = _par_annee(_simuler({levier: params}, annee_debut, cache=cache)[2])[entree]
    assert levier in avec and not avec[levier].get(HANDLER_FAILED_KEY), avec.get(levier)
    assert avec[levier]['recettes'] == pytest.approx(attendu(levier, params)['rec'], abs=1e-12)
    for autre in autres:
        assert autre in sans, (autre, 'sonde sans effet publié')
        assert _canon(avec[autre]) == _canon(sans[autre]), (regle, autre)
    assert _canon(avec[levier]) == _canon(seul[levier]), (regle, levier)


@pytest.mark.parametrize('regle', ['I', 'IR', 'E'])
def test_ad_independance_en_simulation_annee_d_entree(regle):
    """W3-6, W3-8, W3-10 en simulation complète (année d'entrée)."""
    _verifier_independance_simulation(regle)


def test_ad_successions_meme_traitement_que_le_levier_patrimoine():
    """§ 1.2-4 et R-2 (iv) : un Md€ de recette patrimoniale a le même effet Gini et
    compétitivité, qu'il passe par ``droits_succession`` ou par
    ``fiscalite_patrimoine`` (même règle, traitement identique des programmes)."""
    intensite = _sonde('fiscalite_patrimoine')['intensite']
    _, rec_p, imp_p = _appel(_sim_neuf(), 'fiscalite_patrimoine', {'intensite': intensite})
    _, rec_s, imp_s = _appel(_sim_neuf(), 'droits_succession', {'variation': rec_p})
    assert rec_s == rec_p
    assert imp_s['gini'] == pytest.approx(imp_p['gini'], rel=1e-12)
    assert imp_s['competitivite'] == pytest.approx(imp_p['competitivite'], rel=1e-12)


# ===========================================================================
# 6. Mutations : le test rougit si l'effet est compté deux fois
# ===========================================================================

def _doubler_recette(original):
    def double(self, measure, params, year, gdp, inflation, unemployment):
        dep, rec, impacts = original(self, measure, params, year, gdp, inflation, unemployment)
        impacts = dict(impacts)
        if 'recettes' in impacts:
            impacts['recettes'] = 2 * impacts['recettes']
        return dep, 2 * rec, impacts
    return double


@pytest.mark.parametrize('levier, params', UN_PAR_LEVIER, ids=[c[0] for c in UN_PAR_LEVIER])
def test_mutation_montant_compte_deux_fois(levier, params, monkeypatch):
    """Le montant compté deux fois (handler muté qui double sa recette) fait
    rougir l'effet direct et, pour un levier récurrent, R-IDX en simulation."""
    _verifier_effet_direct(levier, params)
    if levier in RECURRENTS:
        _verifier_r_idx_simulation(levier, params, None)
    nom = f'_apply_{levier}'
    monkeypatch.setattr(BudgetSimulatorV45, nom, _doubler_recette(getattr(BudgetSimulatorV45, nom)))
    with pytest.raises(AssertionError):
        _verifier_effet_direct(levier, params)
    if levier in RECURRENTS:
        with pytest.raises(AssertionError):
            _verifier_r_idx_simulation(levier, params, None, cache=False)


@pytest.mark.parametrize('levier, params', UN_PAR_RECURRENT, ids=[c[0] for c in UN_PAR_RECURRENT])
def test_mutation_effet_ponctuel_recompte_chaque_annee(levier, params, monkeypatch):
    """L'effet Gini/compétitivité recompté chaque année (déclencheur ponctuel
    remplacé par l'effet du niveau) fait rougir G8 en simulation et au handler.
    (La recette exceptionnelle n'a pas d'effet ponctuel : mutation sans objet.)"""
    _verifier_ponctuel_simulation(levier, params, None)
    _verifier_ponctuel_handler(levier, params)
    monkeypatch.setattr(BudgetSimulatorV45, '_effet_ponctuel',
                        lambda self, cle, params_dict, effet: effet(params_dict))
    with pytest.raises(AssertionError):
        _verifier_ponctuel_simulation(levier, params, None, cache=False)
    with pytest.raises(AssertionError):
        _verifier_ponctuel_handler(levier, params)


@pytest.mark.parametrize('levier, params', UN_PAR_RECURRENT, ids=[c[0] for c in UN_PAR_RECURRENT])
def test_mutation_retour_anticipe_sans_garde_du_traqueur(levier, params, monkeypatch):
    """G8-retour : un handler qui sort au neutre SANS regarder le traqueur garde
    l'effet Gini cumulé à vie — le vérificateur doit rougir."""
    _verifier_retour_handler(levier, params)
    nom = f'_apply_{levier}'
    original = getattr(BudgetSimulatorV45, nom)
    neutres = C.NEUTRES_RELEASE_E[levier]

    def sans_garde(self, measure, p, year, gdp, inflation, unemployment):
        if all(p.get(k, v) == v for k, v in neutres.items()):
            return 0.0, 0.0, {}
        return original(self, measure, p, year, gdp, inflation, unemployment)

    monkeypatch.setattr(BudgetSimulatorV45, nom, sans_garde)
    with pytest.raises(AssertionError):
        _verifier_retour_handler(levier, params)


@pytest.mark.parametrize('levier, params', UN_PAR_LEVIER, ids=[c[0] for c in UN_PAR_LEVIER])
def test_mutation_montant_indexe_rougit_r_idx(levier, params, monkeypatch):
    """R-IDX : un montant indexé sur le PIB de l'année (règle écartée, Q1) fait
    rougir le vérificateur d'indépendance au PIB."""
    _verifier_r_idx_handler(levier, params)
    nom = f'_apply_{levier}'
    original = getattr(BudgetSimulatorV45, nom)

    def indexe(self, measure, p, year, gdp, inflation, unemployment):
        dep, rec, impacts = original(self, measure, p, year, gdp, inflation, unemployment)
        return dep, rec * gdp / C.PIB_BASE_2025_MD_EUR, impacts

    monkeypatch.setattr(BudgetSimulatorV45, nom, indexe)
    with pytest.raises(AssertionError):
        _verifier_r_idx_handler(levier, params)


# Fuite d'un levier W3 vers un levier existant (double compte) : le levier
# existant ajoute la recette du levier W3 à la sienne.
FUITES = {'I': ('tva_rate', 'fiscalite_indirecte', 'tva_ciblee'),
          'IR': ('impot_revenu', 'impot_revenu_cible', 'montant'),
          'E': ('taxe_superprofits', 'recette_exceptionnelle', 'montant'),
          'S': ('fiscalite_patrimoine', 'droits_succession', 'variation')}


def _fuite(original, levier_w3, param):
    def fuit(self, measure, p, year, gdp, inflation, unemployment):
        dep, rec, impacts = original(self, measure, p, year, gdp, inflation, unemployment)
        en_plus = (self.mesures.get(levier_w3) or {}).get(param, 0.0)
        impacts = dict(impacts)
        impacts['recettes'] = impacts.get('recettes', rec) + en_plus
        return dep, rec + en_plus, impacts
    return fuit


@pytest.mark.parametrize('regle', list(FUITES))
def test_mutation_fuite_vers_un_levier_existant_rougit_l_independance(regle, monkeypatch):
    """§ 6.8 R-1 : chaque règle d'indépendance a un test qui rougit si l'euro est
    compté une seconde fois par le levier existant."""
    autre, levier_w3, param = FUITES[regle]
    _verifier_independance_handler(REGLES[regle][0], REGLES[regle][1], autre)
    if regle != 'S':
        _verifier_independance_simulation(regle)
    nom = f'_apply_{autre}'
    monkeypatch.setattr(BudgetSimulatorV45, nom, _fuite(getattr(BudgetSimulatorV45, nom), levier_w3, param))
    with pytest.raises(AssertionError):
        _verifier_independance_handler(REGLES[regle][0], REGLES[regle][1], autre)
    if regle != 'S':
        with pytest.raises(AssertionError):
            _verifier_independance_simulation(regle, cache=False)


# ===========================================================================
# 7. Déplafonnement de cotisations_salariales (§ 1.2-D, W3-11, règle D)
# ===========================================================================

COTIS = 'cotisations_salariales'


def _cotis(points, sim=None):
    sim = sim if sim is not None else _sim_neuf()
    return _appel(sim, COTIS, {'baisse_points': points})


def test_w3_11_borne_haute_derivee_de_la_masse_sourcee():
    """Max du registre (policy_measures.json) et domaine du moteur
    (PARAM_DOMAINS) = COTIS_SAL_MASSE_2025_MD / COUT_PAR_POINT_COTIS_SAL à 1e-9 ;
    borne basse 0 inchangée."""
    attendu_max = C.COTIS_SAL_MASSE_2025_MD / C.COUT_PAR_POINT_COTIS_SAL
    assert attendu_max == C.COTIS_SAL_POINTS_SUPPRESSION
    spec = REGISTRE[COTIS]['parametres']['baisse_points']
    assert spec['max'] == pytest.approx(attendu_max, abs=1e-9)
    assert spec['min'] == 0 and spec['valeur_defaut'] == 0
    bas, haut = PARAM_DOMAINS[COTIS]['baisse_points']
    assert bas == 0 and haut == pytest.approx(attendu_max, abs=1e-9)


def test_w3_11_au_maximum_la_recette_supprime_exactement_la_masse_sourcee():
    _verifier_max_egale_masse()


def _max_cotis():
    """Borne haute EFFECTIVE (domaine du moteur, dérivé du registre), égale à la
    borne dérivée de la masse sourcée. La simulation reçoit la borne du registre,
    jamais la constante : un JSON arrondi serait sinon écrêté d'un ulp."""
    haut = PARAM_DOMAINS[COTIS]['baisse_points'][1]
    assert haut == pytest.approx(C.COTIS_SAL_POINTS_SUPPRESSION, abs=1e-9), (
        'borne haute du registre', haut, C.COTIS_SAL_POINTS_SUPPRESSION)
    return haut


def _verifier_max_egale_masse():
    haut = _max_cotis()
    dep, rec, impacts = _cotis(haut)
    assert dep == 0
    assert rec == pytest.approx(-C.COTIS_SAL_MASSE_2025_MD, abs=1e-9), rec
    assert impacts['menages'] == canaux_menages(prelevements_directs=rec)


def test_mutation_cout_du_point_compte_deux_fois_rougit_la_borne(monkeypatch):
    """Règle D (§ 4.1) : la borne tient parce que le point ne compte que les
    cotisations D613CE (hors CSG et CRDS). Un coût du point qui compterait une
    seconde assiette (ici doublé) ferait dépasser la masse sourcée au maximum :
    le vérificateur rougit."""
    _verifier_max_egale_masse()
    monkeypatch.setattr(mod_fiscalite, 'COUT_PAR_POINT_COTIS_SAL', 2 * C.COUT_PAR_POINT_COTIS_SAL)
    with pytest.raises(AssertionError):
        _verifier_max_egale_masse()


def _grille_points(bas, haut, n=11):
    return [bas + (haut - bas) * k / (n - 1) for k in range(n)]


PLAFOND_V072_POINTS = 5  # ancien clamp de _apply_cotisations_salariales (v0.7.2), contrat § 1.2-D


@pytest.mark.parametrize('points', _grille_points(0.5, PLAFOND_V072_POINTS, 10))
def test_w3_11_jusqu_a_cinq_points_forme_exacte_de_v072(points):
    """Jusqu'à 5 points, sortie identique au bit à v0.7.2 : (0, −b × coût du
    point, {recettes, ménages = recette, Gini = b × Gini d'un point,
    compétitivité 0}). Les golden masters (scénarios publiés, ≤ 5 points)
    portent la preuve sur la trajectoire complète, sans régénération."""
    dep, rec, impacts = _cotis(points)
    _, _, un_point = _cotis(1.0)
    assert dep == 0 and rec == -points * C.COUT_PAR_POINT_COTIS_SAL
    assert impacts['recettes'] == rec
    assert impacts['menages'] == canaux_menages(prelevements_directs=rec)
    # Gini par Md€ (décision du 12/11/2026) : linéaire, à l'arrondi du produit près.
    assert impacts['gini'] == pytest.approx(un_point['gini'] * points, rel=1e-12)
    assert impacts['competitivite'] == 0.0


def test_w3_11_gini_d_un_point():
    """Gini d'un point = coefficient par Md€ × coût du point (décision du
    mainteneur du 12/11/2026, estimation de France Budget ; jusque-là 0,0027
    par point, source introuvable), positif : une baisse de cotisations accroît
    les inégalités (G11)."""
    _, _, un_point = _cotis(1.0)
    assert un_point['gini'] == pytest.approx(C.GINI_COTIS_SAL_PAR_MD * C.COUT_PAR_POINT_COTIS_SAL,
                                             rel=1e-12) and un_point['gini'] > 0


def test_w3_11_publies_sous_cinq_points():
    """G1 du déplafonnement (release E) : le droit en vigueur reste dans
    [0 ; 5] points, où le calcul est inchangé. Release de paramètres P : un
    programme publié peut désormais écrire au-delà de 5 points (c'est l'objet
    du déplafonnement) ; tout scénario publié reste dans le domaine
    [0 ; ``COTIS_SAL_POINTS_SUPPRESSION``]. Les valeurs ≤ 5 points gardent le
    calcul de v0.7.2 (``test_w3_11_lineaire_de_cinq_au_maximum`` pour le reste)."""
    assert 0 <= (_DROIT.get(COTIS) or {}).get('baisse_points', 0) <= PLAFOND_V072_POINTS
    for nom, base in _SCENARIOS_PUBLIES.items():
        points = (base.get(COTIS) or {}).get('baisse_points', 0)
        assert 0 <= points <= C.COTIS_SAL_POINTS_SUPPRESSION, (nom, points)


@pytest.mark.parametrize('points', _grille_points(PLAFOND_V072_POINTS, C.COTIS_SAL_POINTS_SUPPRESSION, 6)[1:])
def test_w3_11_lineaire_de_cinq_au_maximum(points):
    """Au-delà de 5 points (clamp retiré), même loi linéaire jusqu'au maximum."""
    dep, rec, impacts = _cotis(points)
    _, _, un_point = _cotis(1.0)
    assert rec == -points * C.COUT_PAR_POINT_COTIS_SAL, (points, rec)
    assert impacts['menages'] == canaux_menages(prelevements_directs=rec)
    assert impacts['gini'] == pytest.approx(un_point['gini'] * points, abs=1e-15)
    assert impacts.get('competitivite', 0.0) == 0.0


@pytest.mark.parametrize('annee_debut', [None, DEBUT_CADRE], ids=['historique', 'cadre2028'])
def test_w3_11_au_maximum_simulation_sans_clip_ni_correction(annee_debut):
    """Au maximum : recette = −masse chaque année d'application, aucun écrêtage,
    rapport valide, et le plafond de 5 % du PIB par mesure ne mord pas (masse
    D613CE < 5 % du PIB 2025, contrat W3-11)."""
    assert C.COTIS_SAL_MASSE_2025_MD < 0.05 * C.PIB_BASE_2025_MD_EUR  # plafond par mesure, orchestrator.apply_measures
    haut = _max_cotis()
    _, _, rapport = _simuler({COTIS: {'baisse_points': haut}}, annee_debut)
    assert rapport['valid'] is True, rapport['warnings']
    assert rapport['leviers_ecretes'] == []
    assert not any(COTIS in w and '5 %' in w for w in rapport['warnings']), rapport['warnings']
    debut = annee_debut or DEBUT
    for an, e in _effets(rapport, COTIS).items():
        if an >= debut:
            assert e['recettes'] == pytest.approx(-C.COTIS_SAL_MASSE_2025_MD, abs=1e-9), (an, e)


def test_w3_11_au_dela_du_maximum_ecretage_trace_et_strict_refuse():
    haut = _max_cotis()
    demande = haut + 1
    _, _, rapport = _simuler({COTIS: {'baisse_points': demande}}, None)
    assert rapport['valid'] is False
    lignes = [l for l in rapport['leviers_ecretes'] if l['levier'] == f'{COTIS}.baisse_points']
    assert lignes and lignes[0]['applique'] == pytest.approx(haut, abs=1e-9), rapport['leviers_ecretes']
    assert all(e['recettes'] == pytest.approx(-C.COTIS_SAL_MASSE_2025_MD, abs=1e-9)
               for e in _effets(rapport, COTIS).values())
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1'}):
        assert _leve_entree_invalide(lambda: BudgetSimulatorV45(
            periods=10, mesures={COTIS: {'baisse_points': demande}}).simulate())


def test_w3_11_api_strict(_client, monkeypatch):
    """API strict : 10 points (au-delà de l'ancien clamp, dans le nouveau
    domaine) → 200 ; au-delà du maximum → 422."""
    monkeypatch.setenv('BUDGETLAB_STRICT', '1')
    dix = 2 * PLAFOND_V072_POINTS
    r = _client.post('/simulate', json={'periods': 10, 'mesures': {COTIS: {'baisse_points': dix}}})
    assert r.status_code == 200, r.text[:500]
    r = _client.post('/simulate', json={'periods': 10, 'mesures': {
        COTIS: {'baisse_points': C.COTIS_SAL_POINTS_SUPPRESSION + 1}}})
    assert r.status_code == 422, r.text[:500]


def test_w3_11_textes_publics():
    """Libellé du contrat (§ 1.2-D) ; infobulle sans « 22 » (taux qui comptait la
    CSG et la CRDS, relecture I5a), qui nomme l'exclusion de la CSG et de la
    CRDS, le coût du point du moteur et la masse supprimée au maximum."""
    entree = REGISTRE[COTIS]
    spec = entree['parametres']['baisse_points']
    assert spec['label'] == 'Baisse des cotisations salariales (points)'
    textes = [entree['nom'], entree['description'], spec['label'], spec['tooltip']]
    assert not any(re.search(r'(?<![\d,.])22(?![\d,])', t) for t in textes), textes
    assert 'CSG' in spec['tooltip'] and 'CRDS' in spec['tooltip']
    # Coût du point arrondi au dixième (décision du mainteneur du 12/11/2026).
    assert f"{C.COUT_PAR_POINT_COTIS_SAL:.1f}".replace('.', ',') + ' Md€' in spec['tooltip']
    assert f'{math.floor(C.COTIS_SAL_MASSE_2025_MD)}' in spec['tooltip']


def test_w3_11_handler_sans_clamp_ni_taux_a_22():
    """Lecture du code : le clamp `min(5, …)` est retiré (contrat § 1.2-D) et le
    code n'écrit plus le taux de 22 % (CSG comprise) — il produisait un « taux
    effectif » négatif au-delà de 22 points dans le journal."""
    arbre = ast.parse(textwrap.dedent(inspect.getsource(
        mod_fiscalite.FiscaliteMenagesMixin._apply_cotisations_salariales)))
    entiers = {n.value for n in ast.walk(arbre) if isinstance(n, ast.Constant)
               and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)}
    assert not entiers & {5, 22}, entiers


def _verifier_independance_cotis_csg():
    """Règle D : assiettes disjointes (D613CE hors CSG et CRDS) — la CSG ne lit
    pas les cotisations et réciproquement. Précondition : le maximum est
    appliqué sans clamp."""
    _verifier_max_egale_masse()
    p_cotis, p_csg = {'baisse_points': _max_cotis()}, _sonde('csg')
    sans = _appel(_sim_neuf({'csg': p_csg}), 'csg', p_csg)
    avec = _appel(_sim_neuf({'csg': p_csg, COTIS: p_cotis}), 'csg', p_csg)
    assert _canon(avec) == _canon(sans)
    sans = _appel(_sim_neuf({COTIS: p_cotis}), COTIS, p_cotis)
    avec = _appel(_sim_neuf({COTIS: p_cotis, 'csg': p_csg}), COTIS, p_cotis)
    assert _canon(avec) == _canon(sans)
    # Simulation, année d'entrée.
    e0 = _par_annee(_simuler({'csg': p_csg}, None)[2])[DEBUT]
    e1 = _par_annee(_simuler({'csg': p_csg, COTIS: p_cotis}, None)[2])[DEBUT]
    assert _canon(e1['csg']) == _canon(e0['csg'])
    assert e1[COTIS]['recettes'] == pytest.approx(-C.COTIS_SAL_MASSE_2025_MD, abs=1e-9)


def test_ad_regle_d_cotisations_et_csg_independantes():
    _verifier_independance_cotis_csg()


# ===========================================================================
# 8. Propriétés qui exigent les profils temporels du chantier W1 (§ 2)
# ===========================================================================


def _simuler_profils(mesures, annee_debut, profils, strict=False):
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1' if strict else ''}):
        return BudgetSimulatorV45(periods=10, mesures=mesures, annee_debut=annee_debut,
                                  profils=profils).simulate()


def _recettes_par_annee(rapport, levier):
    return {an: (e or {}).get('recettes', 0.0) for an, e in _effets(rapport, levier).items()}


def test_w3_profils_eligibles():
    """§ 2.1 : les paramètres en Md€ du chantier sont éligibles aux profils."""
    import budget_simulator.engine.cadre as cadre
    eligibles = getattr(cadre, 'PROFILS_ELIGIBLES', None)
    assert eligibles is not None
    for levier in W3:
        for param in C.NEUTRES_RELEASE_E[levier]:
            assert f'{levier}.{param}' in eligibles, (levier, param)


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
@pytest.mark.parametrize('annee_debut', [DEBUT_CADRE, DEBUT_CADRE + 2])
def test_w3_9_recette_exceptionnelle_sans_profil_l_annee_de_debut_seulement(annee_debut, strict):
    """W3-9 : sans profil, défaut {forme « annee », annee = annee_debut} : le
    montant l'année de début, 0 toutes les autres."""
    m = _mi_haut('recette_exceptionnelle', 'montant')
    _, _, rapport = _simuler_profils({'recette_exceptionnelle': {'montant': m}}, annee_debut, {}, strict)
    rec = _recettes_par_annee(rapport, 'recette_exceptionnelle')
    assert rec[annee_debut] == m
    assert all(v == 0 for an, v in rec.items() if an != annee_debut), rec
    assert rapport['valid'] is True


def test_w3_9_recette_exceptionnelle_profil_annee_2030():
    m = _mi_haut('recette_exceptionnelle', 'montant')
    choisie = DEBUT_CADRE + 2
    _, _, rapport = _simuler_profils({'recette_exceptionnelle': {'montant': m}}, DEBUT_CADRE,
                                     {'recette_exceptionnelle.montant': {'forme': 'annee', 'annee': choisie}})
    rec = _recettes_par_annee(rapport, 'recette_exceptionnelle')
    assert rec[choisie] == m and all(v == 0 for an, v in rec.items() if an != choisie), rec


@pytest.mark.parametrize('forme', ['plein', 'rampe'])
def test_w3_9_recette_exceptionnelle_formes_plein_et_rampe_refusees(forme):
    """W3-9 : seule la forme « annee » est admise. Strict → erreur d'entrée ;
    tolérant → correction tracée, profil ignoré (le défaut s'applique)."""
    m = _mi_haut('recette_exceptionnelle', 'montant')
    profils = {'recette_exceptionnelle.montant': {'forme': forme}}
    assert _leve_entree_invalide(lambda: _simuler_profils(
        {'recette_exceptionnelle': {'montant': m}}, DEBUT_CADRE, profils, strict=True))
    _, _, rapport = _simuler_profils({'recette_exceptionnelle': {'montant': m}}, DEBUT_CADRE, profils)
    assert rapport['valid'] is False
    assert any('recette_exceptionnelle' in w for w in rapport['warnings']), rapport['warnings']
    rec = _recettes_par_annee(rapport, 'recette_exceptionnelle')
    assert rec[DEBUT_CADRE] == m and all(v == 0 for an, v in rec.items() if an != DEBUT_CADRE), rec


def test_w3_9_recette_exceptionnelle_refusee_en_mode_historique(_client, monkeypatch):
    """W3-9 : mode historique (sans ``annee_debut``) → strict : erreur d'entrée
    (422 à l'API) ; tolérant : recette ignorée, correction tracée."""
    m = _mi_haut('recette_exceptionnelle', 'montant')
    mesures = {'recette_exceptionnelle': {'montant': m}}
    assert _leve_entree_invalide(lambda: _simuler_profils(mesures, None, {}, strict=True))
    _, _, rapport = _simuler_profils(mesures, None, {})
    assert rapport['valid'] is False
    assert all(v == 0 for v in _recettes_par_annee(rapport, 'recette_exceptionnelle').values())
    monkeypatch.setenv('BUDGETLAB_STRICT', '1')
    r = _client.post('/simulate', json={'periods': 10, 'mesures': mesures})
    assert r.status_code == 422, r.text[:300]


@pytest.mark.parametrize('levier, params', UN_PAR_RECURRENT, ids=[c[0] for c in UN_PAR_RECURRENT])
def test_g8_profil_rampe_somme_des_increments_egale_au_palier(levier, params):
    """G8 sous profil « rampe » (début 2028) : recette k/5 de 2028 à 2031, valeur
    exacte dès 2032 ; Σ incréments Gini et compétitivité = effet du palier."""
    profils = {f'{levier}.{p}': {'forme': 'rampe'} for p in params}
    _, _, rapport = _simuler_profils({levier: params}, DEBUT_CADRE, profils)
    a = attendu(levier, params)
    n = FIN_MANDAT - DEBUT_CADRE + 1
    effets = _effets(rapport, levier)
    for an in range(DEBUT_CADRE, DEBUT + 10):
        niveau = ({k: 0 + (v - 0) * (an - DEBUT_CADRE + 1) / n for k, v in params.items()}
                  if an < FIN_MANDAT else params)
        assert effets[an]['recettes'] == pytest.approx(attendu(levier, niveau)['rec'], abs=1e-12), an
    assert effets[FIN_MANDAT]['recettes'] == a['rec']
    for canal, cle in (('gini', 'gini'), ('compet', 'competitivite')):
        somme = sum((e or {}).get(cle, 0.0) for e in effets.values())
        assert somme == pytest.approx(a[canal], abs=1e-12), (levier, canal)


@pytest.mark.parametrize('levier, params', UN_PAR_RECURRENT, ids=[c[0] for c in UN_PAR_RECURRENT])
def test_g8_retour_profil_une_seule_annee(levier, params):
    """G8-retour (simulation) : profil « annee 2030 » → recette en 2030 seulement,
    revenue à zéro en 2031 ; Σ des incréments Gini et compétitivité = 0 à 1e-12
    (effet émis puis rendu)."""
    choisie = DEBUT_CADRE + 2
    profils = {f'{levier}.{p}': {'forme': 'annee', 'annee': choisie} for p in params}
    _, _, rapport = _simuler_profils({levier: params}, DEBUT_CADRE, profils)
    a = attendu(levier, params)
    rec = _recettes_par_annee(rapport, levier)
    assert rec[choisie] == a['rec'] and rec[choisie + 1] == 0
    assert all(v == 0 for an, v in rec.items() if an != choisie), rec
    effets = _effets(rapport, levier)
    for cle in ('gini', 'competitivite'):
        assert sum((e or {}).get(cle, 0.0) for e in effets.values()) == pytest.approx(0.0, abs=1e-12)
    assert (effets[choisie] or {}).get('gini', 0.0) == pytest.approx(a['gini'], abs=1e-12)


@pytest.mark.parametrize('annee_debut', [None, DEBUT_CADRE], ids=['historique', 'cadre2028'])
def test_x1_successions_et_patrimoine_exclusifs(annee_debut):
    """Règle X1 (§ 4.1, mécanisme de W1, test W1-5) vue depuis le levier W3 : les
    successions varient déjà dans ``fiscalite_patrimoine`` ; les deux ensemble →
    strict : erreur d'entrée ; tolérant : ``droits_succession`` ignoré, correction
    lisible, trajectoire égale AU BIT à celle du patrimoine seul (aucun euro de
    succession compté deux fois)."""
    patrimoine = {'fiscalite_patrimoine': _sonde('fiscalite_patrimoine')}
    deux = {**patrimoine, 'droits_succession': {'variation': _mi_haut('droits_succession', 'variation')}}
    assert _leve_entree_invalide(lambda: _simuler_profils(deux, annee_debut, {}, strict=True))
    df_p, det_p, _ = _simuler_profils(patrimoine, annee_debut, {})
    df_d, det_d, rapport = _simuler_profils(deux, annee_debut, {})
    assert rapport['valid'] is False
    assert any('droits_succession' in w for w in rapport['warnings']), rapport['warnings']
    assert df_d.equals(df_p) and det_d.equals(det_p)


def test_recette_exceptionnelle_effet_transitoire_annonce():
    """§ 1.2-11 (relecture I8) : l'infobulle dit qu'une recette exceptionnelle
    freine la croissance l'année suivante, « puis l'effet s'inverse ». Montant de
    l'exemple du contrat (50 Md€ en 2028) ; signes seulement."""
    m = 50.0
    df0, _, _ = _simuler_profils({}, DEBUT_CADRE, {})
    df1, _, _ = _simuler_profils({'recette_exceptionnelle': {'montant': m}}, DEBUT_CADRE, {})
    c0 = dict(zip(df0['Année'], df0['Croissance %']))
    c1 = dict(zip(df1['Année'], df1['Croissance %']))
    assert c1[DEBUT_CADRE + 1] < c0[DEBUT_CADRE + 1]
    assert any(c1[an] > c0[an] for an in range(DEBUT_CADRE + 2, FIN_MANDAT + 1)), (c0, c1)


# ---------------------------------------------------------------------------
# TVA à taux réduits : même canal de prix que la TVA normale (revue adverse de
# la release E, R-2 C4). À recette égale, la hausse du taux normal passait dans
# les prix l'année suivante (+0,09 point d'inflation) et celle des taux réduits
# non (−0,05) : 0,35 point de dette 2032 d'écart par ce seul canal.
# ---------------------------------------------------------------------------

def _inflation(mesures, annee_debut, profils=None):
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv('BUDGETLAB_STRICT', '')
        mp.setattr(mod_orchestrateur, 'round', lambda x, n=None: float(x), raising=False)
        df, _, rapport = BudgetSimulatorV45(periods=10, mesures=mesures, annee_debut=annee_debut,
                                            profils=profils).simulate()
    return df.set_index('Année')['Inflation %'], rapport


@pytest.mark.parametrize('annee_debut', [None, DEBUT_CADRE], ids=['historique', 'cadre2028'])
@pytest.mark.parametrize('taux', [0.203, 0.205, 0.209])
def test_tva_reduite_meme_passage_dans_les_prix_a_recette_egale(annee_debut, taux):
    """À recette égale l'année d'entrée (montant des taux réduits = recette du
    taux normal cette année-là, lue dans le rapport), l'écart d'inflation au
    statu quo de l'année qui suit est le même (≤ 1e-12 point) : les entrées de
    l'inflation de cette année-là (écart de production et chômage de fin
    d'année d'entrée, effort intérieur, recette de TVA de l'année d'entrée)
    sont les mêmes. Non-vacuité : cet écart est positif (passage dans les
    prix)."""
    t = annee_debut or DEBUT
    ref, _ = _inflation({}, annee_debut)
    normale, rapport = _inflation({'tva_rate': {'taux': taux}}, annee_debut)
    recette = _par_annee(rapport)[t]['tva_rate']['recettes']
    # Taux choisis pour une recette dans le domaine du montant (sans écrêtage).
    assert 0 < recette < _spec('fiscalite_indirecte', 'tva_ciblee')['max'], recette
    reduite, _ = _inflation({'fiscalite_indirecte': {'tva_ciblee': recette}}, annee_debut)
    d_normale, d_reduite = normale[t + 1] - ref[t + 1], reduite[t + 1] - ref[t + 1]
    assert d_normale > 0, ('NON_VACUITE', d_normale)
    assert abs(d_reduite - d_normale) <= 1e-12, (d_normale, d_reduite)


def test_tva_reduite_passage_dans_les_prix_a_l_horloge_de_son_levier():
    """Même montant de TVA à taux réduits ou d'accises, une seule année (2030),
    programme commençant en 2028 : inflations identiques jusqu'en 2030 ; en
    2031, l'année qui SUIT l'entrée en vigueur du levier (son horloge, pas le
    début du programme), la TVA passe dans les prix, les accises non."""
    profils_tva = {'fiscalite_indirecte.tva_ciblee': {'forme': 'annee', 'annee': 2030}}
    profils_acc = {'fiscalite_indirecte.accises_energie': {'forme': 'annee', 'annee': 2030}}
    tva, rapport = _inflation({'fiscalite_indirecte': {'tva_ciblee': 10.0}}, DEBUT_CADRE, profils_tva)
    acc, _ = _inflation({'fiscalite_indirecte': {'accises_energie': 10.0}}, DEBUT_CADRE, profils_acc)
    assert rapport['cadre']['profils']['fiscalite_indirecte.tva_ciblee']['origine'] == 2030
    for annee in range(DEBUT_CADRE, 2031):
        assert abs(tva[annee] - acc[annee]) <= 1e-12, annee
    assert tva[2031] - acc[2031] > 1e-3, (tva[2031], acc[2031])
