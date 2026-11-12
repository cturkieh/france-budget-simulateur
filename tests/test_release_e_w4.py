"""Release E — chantier W4 : impôts à taux avec comportement (tests écrits AVANT le code).

Contrat : ``docs/plans/contrat-curseurs-release-E-2026-11.md`` du dépôt parent,
§ 1.2-5 à 1.2-8 (fiches des quatre leviers), § 3 (évitement, décision D3),
§ 4.1 (règles Z, Z-ter, M, K, F), § 6.1 (tests communs G1 à G12) et § 6.5
(W4-1 à W4-19).

Leviers du chantier (``handlers/recettes_taux.py``) :
- ``impot_plancher_patrimoine`` : taux, évitement réglable, imputation de l'ISF ;
  Gini et compétitivité de l'émission EFFECTIVE de l'ISF ;
- ``fiscalite_capital`` : part IR du prélèvement forfaitaire, prélèvements
  sociaux du capital (deux assiettes), élasticité ; mode montant exclusif ;
- ``multinationales`` : bénéfices récupérés (au taux d'IS du scénario), taxe sur
  les services numériques (érosion) ; mode montant exclusif ;
- ``operations_financieres`` : taxe sur les transactions financières (élasticité
  des volumes) ; mode montant exclusif ; rachats d'actions (écart à la taxe de
  8 % en vigueur) ; crypto-actifs.

Règles d'écriture de ce fichier :
- toute valeur attendue est DÉRIVÉE des constantes nommées du socle (bloc
  « RELEASE E — SOCLE » de ``constants.py``) et des neutres du registre
  (``NEUTRES_RELEASE_E``), par les formules du contrat recopiées en section 0 ;
  les seuls nombres posés ici sont des POINTS DE GRILLE (valeurs d'entrée) ;
- le défaut de l'évitement du plancher n'est jamais écrit en dur : sa valeur
  finale est une décision du mainteneur ; les tests le lisent dans
  ``EVITEMENT_PLANCHER_DEFAUT`` et dans le registre, et exigent qu'il soit
  une constante nommée unique ;
- exigence D3 du mainteneur : l'évitement ne contient QUE la réaction des
  contribuables visés ; il n'agit que sur la recette du levier, jamais sur un
  autre canal ni par un effet macro (section 3) ;
- chaque règle anti-double-compte a un test PAR MUTATION : on injecte le double
  compte (enveloppe autour d'un handler) et la vérification doit échouer sur
  son assertion marquée « DOUBLE_COMPTE », après avoir passé sans mutation ;
- chaque vérification d'indépendance exige d'abord que le levier W4 ait eu un
  effet (assertions marquées « NON_VACUITE ») : sur le socle, où les squelettes
  refusent toute valeur non neutre, ces tests sont rouges pour cette raison.

Tests verts dès le socle (gardes de non-régression, dits dans leur docstring) :
portes de domaine en strict, porte des modes exclusifs en strict, extraction
des noms et des modes par le générateur, absence de mode montant du plancher,
défaut de l'évitement égal entre registre et constante.

Les tests de profils temporels (section 9) portent sur un mécanisme du chantier
W1 : depuis l'intégration de la release E, ce sont des tests ordinaires
(marqueur ``xfail`` d'attente retiré).
"""
import copy
import inspect
import json
import os
import re
from functools import lru_cache
from pathlib import Path
from unittest.mock import patch

import pytest

import budget_simulator.constants as C
import budget_simulator.handlers.recettes_taux as mod_taux
from budget_simulator.constants import HANDLER_FAILED_KEY
from budget_simulator.engine._param_domain import EntreeInvalide, ParametreIgnore
from budget_simulator.handlers._types import canaux_menages
from budget_simulator.simulator import BudgetSimulatorV45

from cadre_harness import PROGRAMME_MIXTE, SCENARIOS as _SCENARIOS_PUBLIES, simuler

RACINE = Path(__file__).absolute().parent.parent
REGISTRE = {m['id']: m for m in json.loads(
    (RACINE / 'policy_measures.json').read_text(encoding='utf-8'))['mesures']}
DROIT = json.loads((RACINE / 'budget_simulator' / 'data' / 'droit_en_vigueur.json')
                   .read_text(encoding='utf-8'))['mesures']

W4 = ('impot_plancher_patrimoine', 'fiscalite_capital', 'multinationales', 'operations_financieres')
NEUTRES = C.NEUTRES_RELEASE_E
PIB_2025 = C.PIB_BASE_2025_MD_EUR
DEBUT_HISTORIQUE = C.POLICY_START_YEAR          # première année simulée, horloge historique
ANNEE_PLEINE = DEBUT_HISTORIQUE + 1             # seconde année de l'horloge : phasage plein
FIN_SIMULATION = DEBUT_HISTORIQUE + 9           # periods = 10
DEBUT_CADRE = C.ANNEE_PREMIER_BUDGET_MANDAT     # 2028
FIN_MANDAT = C.ANNEE_FIN_MANDAT                 # 2032


def _borne(levier, param, cote):
    return REGISTRE[levier]['parametres'][param][cote]


# ===========================================================================
# 0. Formules du contrat (§ 1.2-5 à 1.2-8), écrites avec les noms du socle
# ===========================================================================

# Impôt plancher. R_REF_PLANCHER est le rendement SANS comportement du texte au
# taux de 2 % (Sénat, rapport n° 689, 2025 ; contrat § 1.2-5) : 2 % est le taux
# auquel la donnée est sourcée, pas un paramètre.
TAUX_TEXTE_PLANCHER = 0.02
# [CALCUL] assiette statique implicite : R_REF_PLANCHER / 2 % (1 000 Md€).
A_PLANCHER_STATIQUE = C.R_REF_PLANCHER / TAUX_TEXTE_PLANCHER

# Revenus du capital : neutres = droit voté (12,8 % et 18,6 %), lus au registre.
T_IR0 = NEUTRES['fiscalite_capital']['taux_ir_forfaitaire']
T_PS0 = NEUTRES['fiscalite_capital']['prelevements_sociaux_capital']
E_K0 = NEUTRES['fiscalite_capital']['elasticite']
TAU_REF_CAPITAL = T_IR0 + T_PS0

# Multinationales : « Md€/an au taux d'IS de 25 % » (contrat § 1.1) = défaut du
# levier impot_societes au registre ; TSN : neutre 3 % (droit voté).
TAUX_IS_REF = REGISTRE['impot_societes']['parametres']['taux']['valeur_defaut']
T_TSN0 = NEUTRES['multinationales']['taux_tsn']
E_TSN0 = NEUTRES['multinationales']['erosion_tsn']

# TTF : neutre 0,4 % (droit voté) ; élasticité exprimée « par +0,1 point de
# taux » (unité du paramètre, contrat § 1.1).
T_TTF0 = NEUTRES['operations_financieres']['taux_ttf']
E_TTF0 = NEUTRES['operations_financieres']['elasticite_volume']
PAS_ELASTICITE_TTF = 0.001

ANNEE_SOURCE = {
    'impot_plancher_patrimoine': C.ANNEE_SOURCE_PLANCHER,
    'fiscalite_capital': C.ANNEE_SOURCE_CAPITAL,
    'multinationales': C.ANNEE_SOURCE_TSN,
    'operations_financieres': C.ANNEE_SOURCE_TTF,
}


def phasage_plancher(annees_ecoulees):
    """Phasage de la collecte de l'ISF (``ISF_PHASAGE``), horloge du levier."""
    if annees_ecoulees < 0:
        return 0.0
    return C.ISF_PHASAGE[min(annees_ecoulees, len(C.ISF_PHASAGE) - 1)]


def r_ref_plancher(taux, evitement, intensite_isf=0.0):
    """Recette nette d'année pleine HORS indice d'assiette et phasage :
    (1 − évitement) × R_REF × (taux / 2 %) × max(0 ; 1 − intensité ISF × taux
    max de l'ISF / taux). Taux nul → 0 (neutre)."""
    if taux == 0:
        return 0.0
    imputation = max(0.0, 1 - intensite_isf * C.ISF_TAUX_MAX / taux)
    return (1 - evitement) * C.R_REF_PLANCHER * (taux / TAUX_TEXTE_PLANCHER) * imputation


def recette_plancher(taux, evitement, intensite_isf, gdp, annees_ecoulees):
    return (r_ref_plancher(taux, evitement, intensite_isf) * (gdp / PIB_2025)
            * phasage_plancher(annees_ecoulees))


def facteur_capital(t_ir, t_ps, elasticite):
    """f(τ) = max(ETI_PLANCHER_FACTEUR ; 1 + e × ((1 − τ) − (1 − τ_ref)) / (1 − τ_ref)) :
    assiette du prélèvement forfaitaire (A_CAPITAL_IR), au taux total τ = τ_IR + τ_PS."""
    tau = t_ir + t_ps
    return max(C.ETI_PLANCHER_FACTEUR,
               1 + elasticite * ((1 - tau) - (1 - TAU_REF_CAPITAL)) / (1 - TAU_REF_CAPITAL))


def facteur_capital_social(t_ps, elasticite):
    """f_PS = max(ETI_PLANCHER_FACTEUR ; 1 + e × (τ_PS⁰ − τ_PS) / (1 − τ_ref)) : reste de
    l'assiette sociale (A_CAPITAL_PS − A_CAPITAL_IR), qui ne voit que les prélèvements
    sociaux (correction de la revue adverse de la release E)."""
    return max(C.ETI_PLANCHER_FACTEUR, 1 + elasticite * (T_PS0 - t_ps) / (1 - TAU_REF_CAPITAL))


def dr_ref_capital(t_ir, t_ps, elasticite):
    """ΔR hors indice, assiette sociale SCINDÉE : la part soumise au prélèvement
    forfaitaire (A_IR) réagit au taux total ; le reste (A_PS − A_IR) ne réagit qu'aux
    prélèvements sociaux :
    ΔR = [(τ_IR + τ_PS) × f(τ) − τ_ref] × A_IR + [τ_PS × f_PS − τ_PS⁰] × (A_PS − A_IR)."""
    f = facteur_capital(t_ir, t_ps, elasticite)
    f_ps = facteur_capital_social(t_ps, elasticite)
    return (((t_ir + t_ps) * f - TAU_REF_CAPITAL) * C.A_CAPITAL_IR
            + (t_ps * f_ps - T_PS0) * (C.A_CAPITAL_PS - C.A_CAPITAL_IR))


def dr_ref_capital_assiette_commune(t_ir, t_ps, elasticite):
    """Formule de l'assiette COMMUNE (release E avant la revue adverse), recopiée au
    bit (mêmes opérations, même ordre) : le même facteur f(τ) sur les deux assiettes.
    Témoin : une hausse des seuls prélèvements sociaux reste identique au bit après la
    correction."""
    tau_ref = T_IR0 + T_PS0
    tau = t_ir + t_ps
    f = max(C.ETI_PLANCHER_FACTEUR, 1 + elasticite * ((1 - tau) - (1 - tau_ref)) / (1 - tau_ref))
    return (t_ir * f - T_IR0) * C.A_CAPITAL_IR + (t_ps * f - T_PS0) * C.A_CAPITAL_PS


def dr1_benefices(benefices, taux_is):
    return benefices * (taux_is / TAUX_IS_REF)


def dr2_ref_tsn(taux_tsn, erosion):
    return (taux_tsn * max(0.0, 1 - erosion * (taux_tsn - T_TSN0)) - T_TSN0) * C.A_TSN


def volume_ttf(taux, elasticite):
    return C.V_REF_TTF * max(0.0, 1 - elasticite * (taux - T_TTF0) / PAS_ELASTICITE_TTF)


def dr1_ref_ttf(taux, elasticite):
    return taux * volume_ttf(taux, elasticite) - T_TTF0 * C.V_REF_TTF


def _intensite_isf(autres):
    bloc = (autres or {}).get('isf_climatique')   # bloc null = levier absent
    return (bloc or {}).get('intensite', 0.0)


def _taux_is(autres):
    bloc = (autres or {}).get('impot_societes')
    return (bloc or {}).get('taux', TAUX_IS_REF)


@lru_cache(maxsize=None)
def pib_2026_statu_quo():
    """PIB nominal 2026 enregistré par le moteur (statu quo) : année source de
    la TTF, posée dans les simulateurs des tests au niveau du handler."""
    sim = BudgetSimulatorV45(periods=10, mesures={})
    sim.simulate()
    return float(sim._pib_nominal_par_annee[C.ANNEE_SOURCE_TTF])


def attendu(levier, params, *, gdp, annees_ecoulees=1, autres=None, pib_2026=None):
    """(recette, Gini, compétitivité, canaux ménages) attendus du PREMIER appel
    du handler (effets ponctuels contre le neutre), d'après le contrat."""
    p = {**NEUTRES[levier], **params}
    if levier == 'impot_plancher_patrimoine':
        r_ref = r_ref_plancher(p['taux'], p['evitement'], _intensite_isf(autres))
        rec = r_ref * (gdp / PIB_2025) * phasage_plancher(annees_ecoulees)
        return (rec, C.GINI_ISF_EFFECTIF_PAR_MD * r_ref, C.COMPET_ISF_EFFECTIF_PAR_MD * r_ref,
                canaux_menages(prelevements_directs=rec))
    if levier == 'fiscalite_capital':
        if 'rendement_md' in params:
            d_ref = params['rendement_md']
            rec = d_ref
        else:
            d_ref = dr_ref_capital(p['taux_ir_forfaitaire'], p['prelevements_sociaux_capital'],
                                   p['elasticite'])
            rec = d_ref * (gdp / PIB_2025)
        return (rec, C.GINI_PATRIMOINE_PAR_MD * d_ref, C.COMPET_PATRIMOINE_PAR_MD * d_ref,
                canaux_menages(prelevements_directs=rec))
    if levier == 'multinationales':
        r1 = dr1_benefices(p['benefices_recuperes'], _taux_is(autres))
        if 'rendement_tsn_md' in params:
            r2_ref = r2 = params['rendement_tsn_md']
        else:
            r2_ref = dr2_ref_tsn(p['taux_tsn'], p['erosion_tsn'])
            r2 = r2_ref * (gdp / PIB_2025)
        return (r1 + r2, 0.0,
                C.COMPET_IS_PAR_MD * r1 + C.COMPET_IMPOTS_PRODUCTION_PAR_MD * r2_ref, canaux_menages())
    if levier == 'operations_financieres':
        if 'rendement_ttf_md' in params:
            r1_ref = r1 = params['rendement_ttf_md']
        else:
            r1_ref = dr1_ref_ttf(p['taux_ttf'], p['elasticite_volume'])
            r1 = r1_ref * (gdp / (pib_2026 or pib_2026_statu_quo()))
        montants = p['rachats_actions'] + p['crypto_actifs']
        return (r1 + montants, 0.0, C.COMPET_IS_EXCEPTIONNEL_PAR_MD * (r1_ref + montants),
                canaux_menages())
    raise KeyError(levier)


# ===========================================================================
# Outils : appel direct d'un handler, simulation, espion, rejeu, mutation
# ===========================================================================

ETAT = {'inflation': 0.015, 'unemployment': 0.078}   # état macro quelconque (non lu, D3)
CANONIQUES = ('depenses', 'recettes', 'menages', 'gini', 'competitivite', 'chomage')


def _sim(autres=None):
    """Simulateur prêt pour des appels directs : état remis à zéro, PIB 2026
    (année source de la TTF) enregistré, ``mesures`` = ``autres``."""
    sim = BudgetSimulatorV45(periods=1, mesures=copy.deepcopy(autres or {}))
    sim._reset_state()
    sim._pib_nominal_par_annee[C.ANNEE_SOURCE_TTF] = pib_2026_statu_quo()
    return sim


def _appel(sim, levier, params, *, year=ANNEE_PLEINE, gdp=PIB_2025, **etat):
    e = {**ETAT, **etat}
    sim.mesures[levier] = copy.deepcopy(params)
    return sim.measure_handlers[levier](sim.measure_registry[levier], copy.deepcopy(params),
                                        year, gdp, e['inflation'], e['unemployment'])


def _premier_appel(levier, params, *, autres=None, **kw):
    return _appel(_sim(autres), levier, params, **kw)


def _canal(impacts, cle):
    if cle == 'menages':
        return impacts.get('menages', canaux_menages())
    return impacts.get(cle, 0.0)


def _verifier_sortie(sortie, rec, gini, compet, menages, libelle):
    dep, r, imp = sortie
    assert dep == 0, (libelle, 'dépense')
    assert r == pytest.approx(rec, rel=1e-12, abs=1e-10), (libelle, 'recette', r, rec)
    assert imp.get('recettes', r) == pytest.approx(rec, rel=1e-12, abs=1e-10), (libelle, 'impacts')
    assert _canal(imp, 'gini') == pytest.approx(gini, rel=1e-12, abs=1e-15), (libelle, 'gini')
    assert _canal(imp, 'competitivite') == pytest.approx(compet, rel=1e-12, abs=1e-15), (libelle, 'compet')
    m = _canal(imp, 'menages')
    assert set(m) == set(canaux_menages()), (libelle, 'canaux ménages', m)
    for c in m:
        assert m[c] == pytest.approx(menages[c], rel=1e-12, abs=1e-10), (libelle, c)
    assert _canal(imp, 'chomage') == 0.0, (libelle, 'aucun effet direct sur le chômage')


def _impacts_du_levier(rapport, levier):
    """{année: impacts publiés du levier}."""
    return {a['Année']: a[levier] for a in rapport['measure_impacts_by_year'] if levier in a}


def _sans_echec(rapport, levier):
    imp = _impacts_du_levier(rapport, levier)
    echecs = {an: i.get('erreur') for an, i in imp.items() if i.get(HANDLER_FAILED_KEY)}
    assert not echecs, ('NON_VACUITE', levier, 'levier en échec', echecs)


def _debut(annee_debut):
    return DEBUT_HISTORIQUE if annee_debut is None else annee_debut


def _espionner(mp, methode, journal):
    """Enregistre chaque appel du handler ``methode`` (entrées, état lu, sortie)."""
    original = getattr(BudgetSimulatorV45, methode)

    def espion(self, measure, params, year, gdp, inflation, unemployment):
        sortie = original(self, measure, params, year, gdp, inflation, unemployment)
        journal.append({'params': copy.deepcopy(params), 'year': year, 'gdp': gdp,
                        'inflation': inflation, 'unemployment': unemployment,
                        'sortie': copy.deepcopy(sortie),
                        'origines': dict(self._origines_courantes),
                        'pib': dict(self._pib_nominal_par_annee),
                        'inflations': dict(self._inflation_par_annee)})
        return sortie

    mp.setattr(BudgetSimulatorV45, methode, espion)


def _canon(x):
    if isinstance(x, dict):
        return {str(k): _canon(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_canon(v) for v in x]
    if isinstance(x, float):
        return x.hex()
    return x


def _rejouer_et_comparer(methode, journal, mesures_sans, libelle):
    """Rejoue, dans un simulateur dont ``mesures`` NE contient PAS l'autre
    levier, chaque appel enregistré : la sortie doit être identique au bit.
    Mode historique (un seul monde)."""
    levier = methode[len('_apply_'):]
    sim = BudgetSimulatorV45(periods=1, mesures=copy.deepcopy(mesures_sans))
    sim._reset_state()
    for appel in journal:
        sim._origines_courantes = dict(appel['origines'])
        sim._pib_nominal_par_annee = dict(appel['pib'])
        sim._inflation_par_annee = dict(appel['inflations'])
        sortie = getattr(sim, methode)(sim.measure_registry[levier], copy.deepcopy(appel['params']),
                                       appel['year'], appel['gdp'], appel['inflation'],
                                       appel['unemployment'])
        assert _canon(sortie) == _canon(appel['sortie']), (
            'DOUBLE_COMPTE', libelle, levier, appel['year'], sortie, appel['sortie'])


def _muter(mp, methode, transformer):
    """Remplace le handler ``methode`` par ``transformer(self, original, *args)``."""
    original = getattr(BudgetSimulatorV45, methode)

    def mutant(self, measure, params, year, gdp, inflation, unemployment):
        return transformer(self, original, measure, params, year, gdp, inflation, unemployment)

    mp.setattr(BudgetSimulatorV45, methode, mutant)


def _ajouter_recette(sortie, montant):
    dep, rec, imp = sortie
    imp = dict(imp)
    imp['recettes'] = imp.get('recettes', rec) + montant
    return dep, rec + montant, imp


def _sans(mesures, *leviers):
    return {k: v for k, v in mesures.items() if k not in leviers}


# Un bloc représentatif et à effet non nul par levier (recettes > 0,1 Md€).
BLOCS = {
    'impot_plancher_patrimoine': {'taux': 0.02},
    'fiscalite_capital': {'prelevements_sociaux_capital': 0.20},
    'multinationales': {'taux_tsn': 0.06},
    'operations_financieres': {'taux_ttf': 0.006},
}
# Paramètres en Md€ (règle R-IDX : constants en euros courants).
MONTANTS = [
    ('fiscalite_capital', {'rendement_md': 3.0}, 3.0),
    ('multinationales', {'benefices_recuperes': 4.0}, 4.0),
    ('multinationales', {'rendement_tsn_md': 2.0}, 2.0),
    ('operations_financieres', {'rendement_ttf_md': 2.0}, 2.0),
    ('operations_financieres', {'rachats_actions': 1.0}, 1.0),
    ('operations_financieres', {'crypto_actifs': 0.5}, 0.5),
]
IDS_MONTANTS = [f'{l}-{next(iter(p))}' for l, p, _ in MONTANTS]


# ===========================================================================
# 1. Livraison, registre, modes exclusifs, R-MODE
# ===========================================================================

def test_w4_leviers_livres():
    """Le chantier W4 retire ses quatre leviers de ``LEVIERS_NON_LIVRES`` en
    livrant leurs corps (la garde du socle exige que la liste nomme exactement
    les squelettes). Rouge sur le socle : les quatre y sont."""
    assert not set(W4) & C.LEVIERS_NON_LIVRES, sorted(set(W4) & C.LEVIERS_NON_LIVRES)


def test_w4_11_generateur_noms_et_modes_exclusifs_depuis_la_source():
    """W4-11 (garde, verte dès le socle) : depuis la SOURCE des handlers, le
    générateur extrait exactement les noms du contrat (aucune clé de lambda
    lue comme un paramètre) et associe chaque mode montant aux paramètres qu'il
    masque (motif ``if 'rendement_…' in params:``)."""
    from scripts.generate_measure_registry import build_modes_exclusifs, build_noms_admis
    noms, modes = build_noms_admis(), build_modes_exclusifs()
    for levier in W4:
        assert set(noms[levier]) == set(REGISTRE[levier]['parametres']), levier
    assert {k: set(v) for k, v in modes['fiscalite_capital'].items()} == {
        'rendement_md': {'taux_ir_forfaitaire', 'prelevements_sociaux_capital', 'elasticite'}}
    assert {k: set(v) for k, v in modes['multinationales'].items()} == {
        'rendement_tsn_md': {'taux_tsn', 'erosion_tsn'}}
    assert {k: set(v) for k, v in modes['operations_financieres'].items()} == {
        'rendement_ttf_md': {'taux_ttf', 'elasticite_volume'}}
    assert 'impot_plancher_patrimoine' not in modes


def test_r_mode_le_plancher_n_a_pas_de_mode_montant():
    """R-MODE (garde, verte dès le socle) : l'impôt plancher est écrit en taux
    par toutes les sources ; il n'a AUCUN paramètre en Md€ qui échapperait à
    l'évitement."""
    from budget_simulator.engine._noms_parametres import MODES_EXCLUSIFS, NOMS_PARAMETRES_ADMIS
    assert NOMS_PARAMETRES_ADMIS['impot_plancher_patrimoine'] == frozenset({'taux', 'evitement'})
    assert 'impot_plancher_patrimoine' not in MODES_EXCLUSIFS


MODES = [
    ('fiscalite_capital', 'rendement_md', 3.0,
     {'taux_ir_forfaitaire': 0.30, 'prelevements_sociaux_capital': 0.25, 'elasticite': 2.0}),
    ('multinationales', 'rendement_tsn_md', 2.0, {'taux_tsn': 0.08, 'erosion_tsn': 5.0}),
    ('operations_financieres', 'rendement_ttf_md', 2.0, {'taux_ttf': 0.008, 'elasticite_volume': 0.2}),
]


@pytest.mark.parametrize('levier, cle, montant, masques', MODES, ids=[m[0] for m in MODES])
def test_r_mode_montant_net_sans_comportement(levier, cle, montant, masques):
    """R-MODE : un montant en Md€ est un rendement NET annoncé : ni taux, ni
    évitement, ni élasticité, ni indice d'assiette ne s'y appliquent ; les
    paramètres masqués fournis en même temps sont ignorés (sortie identique au
    bit à celle du montant seul)."""
    seul = _premier_appel(levier, {cle: montant}, gdp=PIB_2025 * 1.2)
    avec = _premier_appel(levier, {cle: montant, **masques}, gdp=PIB_2025 * 1.2)
    assert seul[1] == pytest.approx(montant, rel=1e-12)
    assert _canon(avec) == _canon(seul)


@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
@pytest.mark.parametrize('levier, cle, montant, masques', MODES, ids=[m[0] for m in MODES])
def test_w4_11_deux_modes_fournis_tolerant_correction_et_mode_montant_retenu(levier, cle, montant,
                                                                            masques, annee_debut):
    """W4-11 (tolérant) : les deux modes fournis → correction ``PARAM_IGNORE``
    (``report.valid`` faux) et le levier appliqué en mode MONTANT : recette =
    montant chaque année, trajectoire identique au montant seul."""
    debut = _debut(annee_debut)
    df_m, det_m, r_m, _ = simuler({levier: {cle: montant}}, annee_debut=annee_debut)
    df, det, rapport, _ = simuler({levier: {cle: montant, **masques}}, annee_debut=annee_debut)
    _sans_echec(rapport, levier)
    assert rapport['valid'] is False
    assert any('ignoré' in w and levier in w for w in rapport['warnings']), rapport['warnings']
    imp = _impacts_du_levier(rapport, levier)
    for an in range(debut, FIN_SIMULATION + 1):
        assert imp[an]['recettes'] == pytest.approx(montant, rel=1e-12), (an, imp.get(an))
    assert df.equals(df_m) and det.equals(det_m)


@pytest.mark.parametrize('levier, cle, montant, masques', MODES, ids=[m[0] for m in MODES])
def test_w4_11_deux_modes_fournis_strict_parametre_ignore(levier, cle, montant, masques):
    """W4-11 (strict, garde verte dès le socle : la porte précède le handler)."""
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1'}):
        with pytest.raises(ExceptionGroup) as info:
            BudgetSimulatorV45(periods=10, mesures={levier: {cle: montant, **masques}}).simulate()
    assert any(isinstance(e, ParametreIgnore) for e in info.value.exceptions), info.value.exceptions


# ===========================================================================
# 2. Formules exactes au niveau du handler (G7, G11, M1, W4-6, W4-18)
# ===========================================================================

PLANCHER_TAUX = [0.005, 0.01, 0.02, 0.03]
PLANCHER_EVITEMENTS = [0.0, 0.2, C.EVITEMENT_PLANCHER_DEFAUT, 0.95]
PLANCHER_ISF = [0.0, 0.3, 1.0]


@pytest.mark.parametrize('intensite_isf', PLANCHER_ISF)
@pytest.mark.parametrize('evitement', PLANCHER_EVITEMENTS)
@pytest.mark.parametrize('taux', PLANCHER_TAUX)
def test_plancher_formule_exacte(taux, evitement, intensite_isf):
    """§ 1.2-5 : recette = (1 − e) × R_REF × (taux / 2 %) × indice (source 2025)
    × phasage de l'ISF × imputation de l'ISF ; canal ménages = prélèvements
    directs ; Gini et compétitivité = coefficients EFFECTIFS de l'ISF × recette
    nette d'année pleine HORS indice et phasage (G7, G11)."""
    autres = {'isf_climatique': {'intensite': intensite_isf}}
    params = {'taux': taux, 'evitement': evitement}
    for year, gdp in ((DEBUT_HISTORIQUE, PIB_2025), (ANNEE_PLEINE, PIB_2025),
                      (ANNEE_PLEINE, PIB_2025 * 1.15), (ANNEE_PLEINE + 3, PIB_2025 * 1.3)):
        sortie = _premier_appel('impot_plancher_patrimoine', params, autres=autres, year=year, gdp=gdp)
        _verifier_sortie(sortie, *attendu('impot_plancher_patrimoine', params, gdp=gdp,
                                          annees_ecoulees=year - DEBUT_HISTORIQUE, autres=autres),
                         libelle=(params, intensite_isf, year, gdp))


CAPITAL_GRILLE = [
    {'taux_ir_forfaitaire': t_ir, 'prelevements_sociaux_capital': t_ps, 'elasticite': e}
    for t_ir in (0.0, 0.10, T_IR0, 0.20, 0.45)
    for t_ps in (0.0, T_PS0, 0.25, 0.30)
    for e in (0.0, E_K0, 2.0)
]


@pytest.mark.parametrize('params', CAPITAL_GRILLE,
                         ids=[f"{p['taux_ir_forfaitaire']}-{p['prelevements_sociaux_capital']}-{p['elasticite']}"
                              for p in CAPITAL_GRILLE])
def test_capital_formule_exacte(params):
    """§ 1.2-6 : ΔR = {[τ_IR f(τ) − τ_IR⁰] A_IR + [τ_PS f(τ) − τ_PS⁰] A_PS} ×
    indice (source 2025) ; prélèvements directs ; Gini et compétitivité du
    levier patrimoine (arbitrage Q3) × ΔR hors indice."""
    for gdp in (PIB_2025, PIB_2025 * 1.2):
        sortie = _premier_appel('fiscalite_capital', params, gdp=gdp)
        _verifier_sortie(sortie, *attendu('fiscalite_capital', params, gdp=gdp), libelle=(params, gdp))


@pytest.mark.parametrize('montant', [-15.0, -3.0, 0.0, 3.0, 15.0])
def test_capital_mode_montant_exact(montant):
    """Mode montant : ΔR = rendement_md, constant (R-IDX), même Gini et même
    compétitivité par Md€ que le mode taux ; présent à 0 = calcul, effet nul."""
    for gdp in (PIB_2025, PIB_2025 * 1.2):
        params = {'rendement_md': montant}
        sortie = _premier_appel('fiscalite_capital', params, gdp=gdp)
        _verifier_sortie(sortie, *attendu('fiscalite_capital', params, gdp=gdp), libelle=(montant, gdp))


MULTI_GRILLE = [
    ({'benefices_recuperes': b, 'taux_tsn': t, 'erosion_tsn': e}, taux_is)
    for b in (0.0, 2.0, C.BENEFICES_RECUPERES_MAX)
    for t in (0.0, T_TSN0, 0.05, 0.10)
    for e in (0.0, E_TSN0, 10.0)
    for taux_is in (None, 0.15, 0.33)
] + [({'benefices_recuperes': b, 'rendement_tsn_md': r}, taux_is)
     for b in (0.0, 3.0) for r in (-1.0, 0.0, 5.0) for taux_is in (None, 0.30)]


@pytest.mark.parametrize('params, taux_is', MULTI_GRILLE,
                         ids=[f"{'-'.join(f'{v:g}' for v in p.values())}-is{t}" for p, t in MULTI_GRILLE])
def test_multinationales_formule_exacte(params, taux_is):
    """§ 1.2-7 : ΔR₁ = b × τ_IS / 25 % (τ_IS lu dans le levier impot_societes,
    défaut du registre s'il est absent), constant ; ΔR₂ = [τ max(0 ; 1 −
    érosion (τ − 3 %)) − 3 %] × A_TSN × indice (source 2025), ou le montant ;
    aucun canal ménages, Gini nul ; compétitivité = IS × ΔR₁ + impôts de
    production × ΔR₂ hors indice."""
    autres = {} if taux_is is None else {'impot_societes': {'taux': taux_is, 'niches': 0}}
    for gdp in (PIB_2025, PIB_2025 * 1.2):
        sortie = _premier_appel('multinationales', params, autres=autres, gdp=gdp)
        _verifier_sortie(sortie, *attendu('multinationales', params, gdp=gdp, autres=autres),
                         libelle=(params, taux_is, gdp))


OPERATIONS_GRILLE = [
    {'taux_ttf': t, 'elasticite_volume': e, 'rachats_actions': r, 'crypto_actifs': k}
    for t in (0.0, 0.002, T_TTF0, 0.006, 0.01)
    for e in (0.0, E_TTF0, 0.25)
    for r in (_borne('operations_financieres', 'rachats_actions', 'min'), 0.0, 5.0)
    for k in (0.0, 2.0)
] + [{'rendement_ttf_md': m, 'rachats_actions': r} for m in (-3.0, 0.0, 4.0) for r in (0.0, 1.5)]


@pytest.mark.parametrize('params', OPERATIONS_GRILLE,
                         ids=['-'.join(f'{v:g}' for v in p.values()) for p in OPERATIONS_GRILLE])
def test_operations_financieres_formule_exacte(params):
    """§ 1.2-8 : ΔR₁ = [τ V(τ) − 0,4 % V_REF] × indice (source 2026), V(τ) =
    V_REF max(0 ; 1 − ε (τ − 0,4 %) / 0,1 point), ou le montant ; rachats =
    ÉCART à la taxe de 8 % en vigueur ; crypto-actifs = recette nouvelle ; aucun
    canal ménages, Gini nul ; compétitivité = IS exceptionnel × Σ ΔR hors indice."""
    pib_2026 = pib_2026_statu_quo()
    for gdp in (pib_2026, pib_2026 * 1.2):
        sortie = _premier_appel('operations_financieres', params, gdp=gdp)
        _verifier_sortie(sortie, *attendu('operations_financieres', params, gdp=gdp, pib_2026=pib_2026),
                         libelle=(params, gdp))


def test_operations_financieres_indice_lu_sur_le_pib_2026_enregistre():
    """R-IDX : l'assiette de la TTF suit le PIB depuis 2026, PIB lu dans
    l'enregistrement du moteur (et non le PIB 2025 de base)."""
    sim = _sim()
    sim._pib_nominal_par_annee[C.ANNEE_SOURCE_TTF] = 3333.0
    _, rec, _ = _appel(sim, 'operations_financieres', {'taux_ttf': 0.006}, gdp=3333.0 * 1.1)
    assert rec == pytest.approx(dr1_ref_ttf(0.006, E_TTF0) * 1.1, rel=1e-12)


@pytest.mark.parametrize('taux_is', [0.15, 0.25, 0.33])
def test_w4_7_m1_benefices_au_taux_d_is_du_scenario(taux_is):
    """W4-7 (M1) : ΔR₁ = b × τ_IS / 25 % à l'ulp près (l'ordre des opérations
    est libre), τ_IS lu dans le levier impot_societes du scénario."""
    for b in (1.0, 5.0, C.BENEFICES_RECUPERES_MAX):
        _, rec, _ = _premier_appel('multinationales', {'benefices_recuperes': b},
                                   autres={'impot_societes': {'taux': taux_is, 'niches': 0}})
        assert rec == pytest.approx(b * taux_is / TAUX_IS_REF, rel=1e-14), (b, taux_is)


def test_m1_bloc_impot_societes_null_ou_sans_taux_lu_comme_le_defaut():
    """Lecture croisée robuste : un bloc impot_societes ``null`` (levier absent)
    ou sans clé ``taux`` vaut le taux de référence."""
    for autres in ({'impot_societes': None}, {'impot_societes': {'niches': 5}}, {}):
        _, rec, _ = _premier_appel('multinationales', {'benefices_recuperes': 4.0}, autres=autres)
        assert rec == pytest.approx(4.0, rel=1e-14), autres


def test_w4_18_deux_assiettes_du_capital():
    """W4-18 : neutre → 0 exactement ; +0,01 de prélèvements sociaux seul,
    élasticité 0 → 0,01 × A_CAPITAL_PS × indice ; +0,01 de part IR seule,
    élasticité 0 → 0,01 × A_CAPITAL_IR × indice ; ordre de grandeur du contrat :
    ≈ 1,9 Md€ par point de prélèvements sociaux avant comportement."""
    gdp = PIB_2025 * 1.1
    _, rec, _ = _premier_appel('fiscalite_capital', {'elasticite': 0.0}, gdp=gdp)
    assert rec == 0.0
    _, rec_ps, _ = _premier_appel('fiscalite_capital',
                                  {'prelevements_sociaux_capital': T_PS0 + 0.01, 'elasticite': 0.0}, gdp=gdp)
    assert rec_ps == pytest.approx(0.01 * C.A_CAPITAL_PS * gdp / PIB_2025, rel=1e-12)
    _, rec_ir, _ = _premier_appel('fiscalite_capital',
                                  {'taux_ir_forfaitaire': T_IR0 + 0.01, 'elasticite': 0.0}, gdp=gdp)
    assert rec_ir == pytest.approx(0.01 * C.A_CAPITAL_IR * gdp / PIB_2025, rel=1e-12)
    assert 0.01 * C.A_CAPITAL_PS == pytest.approx(1.9, abs=0.05)


@pytest.mark.parametrize('levier, params', [
    ('fiscalite_capital', {'elasticite': 0.0}),
    ('fiscalite_capital', {'elasticite': 2.0}),
    ('fiscalite_capital', {'taux_ir_forfaitaire': T_IR0, 'prelevements_sociaux_capital': T_PS0,
                           'elasticite': 1.3}),
    ('multinationales', {'erosion_tsn': 0.0}),
    ('multinationales', {'erosion_tsn': 10.0, 'benefices_recuperes': 0.0}),
    ('operations_financieres', {'elasticite_volume': 0.0}),
    ('operations_financieres', {'elasticite_volume': 0.25, 'taux_ttf': T_TTF0}),
    ('impot_plancher_patrimoine', {'taux': 0.0, 'evitement': 0.0}),
    ('impot_plancher_patrimoine', {'taux': 0.0, 'evitement': 0.5}),
], ids=lambda x: x if isinstance(x, str) else '-'.join(f'{k}={v:g}' for k, v in x.items()))
def test_w4_13_taux_au_neutre_effet_nul_exactement(levier, params):
    """W4-13 (O1) et neutres des autres taux : un taux au neutre donne un effet
    NUL EXACTEMENT, quel que soit le paramètre de comportement (calcul
    effectué, pas de retour anticipé) ; plancher : taux nul → neutre quels que
    soient l'évitement et l'ISF (aucune division par zéro)."""
    for autres in ({}, {'isf_climatique': {'intensite': 1.0}}):
        dep, rec, imp = _premier_appel(levier, params, autres=autres, gdp=PIB_2025 * 1.2)
        assert (dep, rec) == (0, 0.0) and rec == 0.0, (levier, params, rec)
        assert _canal(imp, 'gini') == 0.0 and _canal(imp, 'competitivite') == 0.0
        assert all(v == 0.0 for v in _canal(imp, 'menages').values())


# --- G11 : signe des effets ponctuels ----------------------------------------

def test_g11_signes():
    """G11 : une hausse de recette sur le patrimoine ou le capital (plancher,
    revenus du capital) donne Gini < 0 et compétitivité < 0 ; une hausse
    d'impôt d'entreprise (multinationales, opérations financières) donne
    compétitivité < 0 et Gini nul ; valeur = constante signée × montant
    (aucun signe ajouté par le handler, vérifié en section 2)."""
    cas = [
        ('impot_plancher_patrimoine', {'taux': 0.02}, True),
        ('fiscalite_capital', {'prelevements_sociaux_capital': 0.22}, True),
        ('fiscalite_capital', {'rendement_md': 4.0}, True),
        ('multinationales', {'benefices_recuperes': 3.0}, False),
        ('multinationales', {'taux_tsn': 0.06}, False),
        ('multinationales', {'rendement_tsn_md': 1.0}, False),
        ('operations_financieres', {'taux_ttf': 0.006}, False),
        ('operations_financieres', {'rachats_actions': 2.0}, False),
        ('operations_financieres', {'crypto_actifs': 1.0}, False),
        ('operations_financieres', {'rendement_ttf_md': 1.0}, False),
    ]
    for levier, params, patrimoine in cas:
        _, rec, imp = _premier_appel(levier, params, gdp=pib_2026_statu_quo())
        assert rec > 0, (levier, params, rec)
        assert _canal(imp, 'competitivite') < 0, (levier, params)
        if patrimoine:
            assert _canal(imp, 'gini') < 0, (levier, params)
        else:
            assert _canal(imp, 'gini') == 0.0, (levier, params)


# Mutation : le handler LIT la constante signée (pas une copie locale ni un signe ajouté).
COEFFICIENTS = [
    ('impot_plancher_patrimoine', {'taux': 0.02}, 'GINI_ISF_EFFECTIF_PAR_MD', 'gini'),
    ('impot_plancher_patrimoine', {'taux': 0.02}, 'COMPET_ISF_EFFECTIF_PAR_MD', 'competitivite'),
    ('fiscalite_capital', {'prelevements_sociaux_capital': 0.22}, 'GINI_PATRIMOINE_PAR_MD', 'gini'),
    ('fiscalite_capital', {'prelevements_sociaux_capital': 0.22}, 'COMPET_PATRIMOINE_PAR_MD', 'competitivite'),
    ('multinationales', {'benefices_recuperes': 3.0}, 'COMPET_IS_PAR_MD', 'competitivite'),
    ('multinationales', {'taux_tsn': 0.06}, 'COMPET_IMPOTS_PRODUCTION_PAR_MD', 'competitivite'),
    ('operations_financieres', {'rachats_actions': 2.0}, 'COMPET_IS_EXCEPTIONNEL_PAR_MD', 'competitivite'),
]


def _patcher_constante(mp, nom, valeur):
    """Pose ``valeur`` sous ``nom`` dans constants.py ET dans le module du
    handler s'il a importé le nom (les deux façons de lire une constante), et
    sous tout ALIAS de la même famille (même objet, nom contenant GINI, COMPET,
    FACTEUR ou EVITEMENT) : un handler qui lirait un alias nommé du bloc W4
    reste couvert ; seul un nombre recopié échappe, et c'est ce qu'on veut
    détecter."""
    original = getattr(C, nom)
    familles = [f for f in ('GINI', 'COMPET', 'FACTEUR', 'EVITEMENT') if f in nom]
    for module in (C, mod_taux):
        for attribut in dir(module):
            if attribut == nom or (familles and any(f in attribut for f in familles)
                                   and getattr(module, attribut) is original):
                mp.setattr(module, attribut, valeur)


@pytest.mark.parametrize('levier, params, nom, cle', COEFFICIENTS, ids=[c[2] for c in COEFFICIENTS])
def test_g11_mutation_le_handler_lit_la_constante_signee(levier, params, nom, cle, monkeypatch):
    """R-1 : G11 rougit si l'on inverse un signe ou recopie un coefficient :
    opposer la constante oppose exactement l'effet."""
    ref = _canal(_premier_appel(levier, params)[2], cle)
    assert ref != 0.0, ('NON_VACUITE', levier, cle)
    _patcher_constante(monkeypatch, nom, -getattr(C, nom))
    mut = _canal(_premier_appel(levier, params)[2], cle)
    assert mut == pytest.approx(-ref, rel=1e-12), (levier, nom, ref, mut)


def test_g11_effets_ponctuels_independants_du_pib_et_du_phasage():
    """§ 1.1 « Effets ponctuels » : ``effet(p)`` ne lit ni le PIB de l'année ni
    l'indice d'assiette, ni (plancher) le phasage : le premier appel émet le
    même Gini et la même compétitivité quels que soient l'année et le PIB."""
    for levier, params in BLOCS.items():
        ref = _premier_appel(levier, params, year=DEBUT_HISTORIQUE, gdp=PIB_2025)[2]
        assert _canal(ref, 'competitivite') != 0.0, ('NON_VACUITE', levier)
        for year, gdp in ((ANNEE_PLEINE, PIB_2025 * 1.3), (ANNEE_PLEINE + 4, PIB_2025 * 0.9)):
            imp = _premier_appel(levier, params, year=year, gdp=gdp)[2]
            for cle in ('gini', 'competitivite'):
                assert _canal(imp, cle) == _canal(ref, cle), (levier, cle, year, gdp)


# ===========================================================================
# 3. D3 — l'évitement ne contient que la réaction des contribuables visés
# ===========================================================================

@pytest.mark.parametrize('taux', PLANCHER_TAUX)
def test_d3_evitement_nul_rendement_statique(taux):
    """EXIGENCE D3 (mainteneur) : à évitement nul, sans ISF, en année pleine, le
    rendement est le rendement STATIQUE taux × assiette (assiette implicite du
    texte, R_REF / 2 %), suivie par le PIB depuis 2025 ; à 2 %, exactement
    R_REF_PLANCHER au PIB 2025."""
    for gdp in (PIB_2025, PIB_2025 * 1.17):
        _, rec, _ = _premier_appel('impot_plancher_patrimoine', {'taux': taux, 'evitement': 0.0}, gdp=gdp)
        assert rec == pytest.approx(taux * A_PLANCHER_STATIQUE * gdp / PIB_2025, rel=1e-12), (taux, gdp)
    _, rec, _ = _premier_appel('impot_plancher_patrimoine',
                               {'taux': TAUX_TEXTE_PLANCHER, 'evitement': 0.0})
    assert rec == pytest.approx(C.R_REF_PLANCHER, rel=1e-12)


@pytest.mark.parametrize('intensite_isf', PLANCHER_ISF)
@pytest.mark.parametrize('taux', PLANCHER_TAUX)
def test_d3_evitement_facteur_pur_sur_tous_les_canaux(taux, intensite_isf):
    """EXIGENCE D3 : l'évitement e est un facteur (1 − e) sur le rendement
    statique, et RIEN d'autre : chaque canal lu par le moteur (recette, canaux
    ménages, Gini, compétitivité) vaut (1 − e) × sa valeur à évitement nul ;
    dépense et chômage restent nuls."""
    autres = {'isf_climatique': {'intensite': intensite_isf}}
    _, rec0, base = _premier_appel('impot_plancher_patrimoine', {'taux': taux, 'evitement': 0.0}, autres=autres)
    for e in (0.1, C.EVITEMENT_PLANCHER_DEFAUT, 0.95):
        dep, rec, imp = _premier_appel('impot_plancher_patrimoine', {'taux': taux, 'evitement': e},
                                       autres=autres)
        assert dep == 0 and _canal(imp, 'chomage') == 0.0
        assert rec == pytest.approx((1 - e) * rec0, rel=1e-12, abs=1e-12)
        for cle in ('gini', 'competitivite'):
            assert _canal(imp, cle) == pytest.approx((1 - e) * _canal(base, cle), rel=1e-12, abs=1e-16)
        for c, v in _canal(imp, 'menages').items():
            assert v == pytest.approx((1 - e) * _canal(base, 'menages')[c], rel=1e-12, abs=1e-12)


EQUIVALENCES_PLANCHER = [  # (taux, évitement) ≡ (taux × (1 − e), 0) : même recette nette
    ((0.02, 0.5), (0.01, 0.0)),
    ((0.03, 0.5), (0.015, 0.0)),
    ((0.02, 0.75), (0.005, 0.0)),
]


def _verifier_equivalence_handler(a, b):
    sa = _premier_appel('impot_plancher_patrimoine', {'taux': a[0], 'evitement': a[1]})
    sb = _premier_appel('impot_plancher_patrimoine', {'taux': b[0], 'evitement': b[1]})
    assert sa[1] != 0.0, ('NON_VACUITE', a)
    for cle in CANONIQUES:
        va, vb = _canal(sa[2], cle), _canal(sb[2], cle)
        if isinstance(va, dict):
            for c in va:
                assert va[c] == pytest.approx(vb[c], rel=1e-12, abs=1e-12), ('DOUBLE_COMPTE', cle, c)
        else:
            assert va == pytest.approx(vb, rel=1e-12, abs=1e-15), ('DOUBLE_COMPTE', cle, va, vb)


@pytest.mark.parametrize('a, b', EQUIVALENCES_PLANCHER, ids=[f'{a}~{b}' for a, b in EQUIVALENCES_PLANCHER])
def test_d3_evitement_equivaut_a_un_taux_plus_bas_au_handler(a, b):
    """EXIGENCE D3 : un évitement e au taux τ est INDISCERNABLE, sur chaque
    canal que lit le moteur, d'un impôt statique au taux τ(1 − e) : l'évitement
    ne transporte aucun effet propre (ni macro, ni compétitivité, ni Gini en
    plus de ceux de la recette perçue)."""
    _verifier_equivalence_handler(a, b)


def _verifier_equivalence_simulation(a, b, annee_debut):
    sa = simuler({'impot_plancher_patrimoine': {'taux': a[0], 'evitement': a[1]}}, annee_debut=annee_debut)
    sb = simuler({'impot_plancher_patrimoine': {'taux': b[0], 'evitement': b[1]}}, annee_debut=annee_debut)
    _sans_echec(sa[2], 'impot_plancher_patrimoine')
    assert sa[2]['valid'] is True, ('NON_VACUITE', sa[2]['warnings'])
    assert _impacts_du_levier(sa[2], 'impot_plancher_patrimoine'), 'NON_VACUITE'
    for cadre_a, cadre_b in ((sa[0], sb[0]), (sa[1], sb[1])):
        for col in cadre_a.columns:
            for va, vb in zip(cadre_a[col], cadre_b[col]):
                assert va == pytest.approx(vb, rel=1e-9, abs=1e-9), ('DOUBLE_COMPTE', col, va, vb)


@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
def test_d3_evitement_equivaut_a_un_taux_plus_bas_simulation_complete(annee_debut):
    """EXIGENCE D3, simulation complète (pleine précision) : (2 %, e = 0,5) et
    (1 %, e = 0) donnent la même trajectoire sur TOUTES les colonnes : aucun
    autre canal du moteur ne voit l'évitement."""
    _verifier_equivalence_simulation((0.02, 0.5), (0.01, 0.0), annee_debut)


def _mutant_evitement_avec_effet_propre(self, original, measure, params, year, gdp, inflation, unemployment):
    """Double compte injecté : l'évitement porte en plus un effet macro propre
    (chômage et compétitivité), que le moteur calcule déjà par la recette."""
    dep, rec, imp = original(self, measure, params, year, gdp, inflation, unemployment)
    e = params.get('evitement', NEUTRES['impot_plancher_patrimoine']['evitement'])
    imp = dict(imp)
    imp['chomage'] = imp.get('chomage', 0.0) + 0.001 * e
    imp['competitivite'] = imp.get('competitivite', 0.0) - 0.01 * e
    return dep, rec, imp


def test_d3_mutation_un_effet_propre_de_l_evitement_est_detecte(monkeypatch):
    """Par MUTATION : un évitement qui porterait un effet propre en plus de la
    recette perdue (double compte de l'effet macro) fait échouer l'équivalence,
    au handler et en simulation complète."""
    _verifier_equivalence_handler((0.02, 0.5), (0.01, 0.0))
    _verifier_equivalence_simulation((0.02, 0.5), (0.01, 0.0), None)
    _muter(monkeypatch, '_apply_impot_plancher_patrimoine', _mutant_evitement_avec_effet_propre)
    with pytest.raises(AssertionError, match='DOUBLE_COMPTE'):
        _verifier_equivalence_handler((0.02, 0.5), (0.01, 0.0))
    with pytest.raises(AssertionError, match='DOUBLE_COMPTE'):
        _verifier_equivalence_simulation((0.02, 0.5), (0.01, 0.0), None)


def test_d3_defaut_de_l_evitement_constante_nommee_unique():
    """Le défaut de l'évitement est UNE constante nommée, facile à changer (sa
    valeur finale est une décision du mainteneur) : le registre (source des
    neutres et du site) porte la même valeur ; une seule définition dans
    constants.py ; aucun littéral de cette valeur dans le handler ; l'infobulle
    affiche ce défaut en pourcentage."""
    defaut = C.EVITEMENT_PLANCHER_DEFAUT
    spec = REGISTRE['impot_plancher_patrimoine']['parametres']['evitement']
    assert spec['valeur_defaut'] == pytest.approx(defaut, abs=1e-12)
    assert NEUTRES['impot_plancher_patrimoine']['evitement'] == pytest.approx(defaut, abs=1e-12)
    assert _borne('impot_plancher_patrimoine', 'evitement', 'min') <= defaut \
        <= _borne('impot_plancher_patrimoine', 'evitement', 'max')
    source = (RACINE / 'budget_simulator' / 'constants.py').read_text(encoding='utf-8')
    definitions = re.findall(r'^(\w*EVITEMENT\w*DEFAUT\w*)\s*=', source, flags=re.MULTILINE)
    assert definitions == ['EVITEMENT_PLANCHER_DEFAUT'], definitions
    code = '\n'.join(l.split('#')[0] for l in inspect.getsource(mod_taux).splitlines())
    assert repr(defaut) not in code and repr(round(defaut, 6)) not in code, 'littéral du défaut dans le handler'
    pct = f'{100 * defaut:.1f}'.rstrip('0').rstrip('.').replace('.', ',')
    assert re.search(rf'\b{re.escape(pct)}[   ]?%', spec['tooltip']), (pct, spec['tooltip'])


def test_d3_defaut_de_l_evitement_lu_par_le_handler():
    """Évitement absent = évitement au défaut nommé ; au calage du contrat
    (2 %, ISF nul, année pleine, PIB 2025) : (1 − défaut) × R_REF."""
    sans = _premier_appel('impot_plancher_patrimoine', {'taux': 0.02})
    avec = _premier_appel('impot_plancher_patrimoine', {'taux': 0.02, 'evitement': C.EVITEMENT_PLANCHER_DEFAUT})
    assert _canon(sans) == _canon(avec)
    assert sans[1] == pytest.approx((1 - C.EVITEMENT_PLANCHER_DEFAUT) * C.R_REF_PLANCHER, rel=1e-9)


def test_d3_mutation_changer_le_defaut_en_un_seul_endroit(monkeypatch):
    """Par MUTATION : changer le défaut à sa source (constante nommée et neutre
    dérivé du registre) suffit ; le handler le suit (aucune copie privée)."""
    nouveau = 0.5 if abs(C.EVITEMENT_PLANCHER_DEFAUT - 0.5) > 1e-9 else 0.25
    _, rec_avant, _ = _premier_appel('impot_plancher_patrimoine', {'taux': 0.02})
    assert rec_avant == pytest.approx((1 - C.EVITEMENT_PLANCHER_DEFAUT) * C.R_REF_PLANCHER, rel=1e-9)
    _patcher_constante(monkeypatch, 'EVITEMENT_PLANCHER_DEFAUT', nouveau)
    monkeypatch.setitem(C.NEUTRES_RELEASE_E['impot_plancher_patrimoine'], 'evitement', nouveau)
    _, rec, _ = _premier_appel('impot_plancher_patrimoine', {'taux': 0.02})
    assert rec == pytest.approx((1 - nouveau) * C.R_REF_PLANCHER, rel=1e-9)


def test_w4_6_calage_du_plancher_derive_des_constantes():
    """W4-6 (valeurs DÉRIVÉES, jamais recopiées) : 2 %, évitement par défaut,
    ISF nul, année pleine, PIB 2025 → (1 − EVITEMENT_PLANCHER_DEFAUT) × R_REF à
    1e-9 ; évitement nul → R_REF ; recette strictement décroissante en
    évitement ; au PIB d'une autre année, × PIB_t / PIB_2025 ; année d'entrée,
    × ISF_PHASAGE[0]."""
    def rec(e, **kw):
        return _premier_appel('impot_plancher_patrimoine', {'taux': 0.02, 'evitement': e}, **kw)[1]

    assert rec(C.EVITEMENT_PLANCHER_DEFAUT) == pytest.approx(
        (1 - C.EVITEMENT_PLANCHER_DEFAUT) * C.R_REF_PLANCHER, abs=1e-9)
    assert rec(0.0) == pytest.approx(C.R_REF_PLANCHER, abs=1e-9)
    e_max = _borne('impot_plancher_patrimoine', 'evitement', 'max')
    grille = _grille(0.0, e_max, 39)
    valeurs = [rec(e) for e in grille]
    assert all(b < a for a, b in zip(valeurs, valeurs[1:])), valeurs
    pib_t = PIB_2025 * 1.21
    assert rec(C.EVITEMENT_PLANCHER_DEFAUT, gdp=pib_t) == pytest.approx(
        (1 - C.EVITEMENT_PLANCHER_DEFAUT) * C.R_REF_PLANCHER * pib_t / PIB_2025, rel=1e-12)
    assert rec(C.EVITEMENT_PLANCHER_DEFAUT, year=DEBUT_HISTORIQUE) == pytest.approx(
        (1 - C.EVITEMENT_PLANCHER_DEFAUT) * C.R_REF_PLANCHER * C.ISF_PHASAGE[0], rel=1e-12)


@pytest.mark.parametrize('levier', W4)
def test_d3_le_handler_ne_lit_pas_l_etat_macro(levier):
    """Règle anti-double-compte du § 3 : un paramètre de comportement ne
    multiplie qu'une recette exprimée en fonction des paramètres et de l'indice
    d'assiette ; le handler ne lit ni l'inflation, ni le chômage, ni l'état
    macro du simulateur (écart de production, dette, recettes)."""
    params = BLOCS[levier]
    ref = _premier_appel(levier, params, gdp=PIB_2025 * 1.1)
    assert ref[1] != 0.0, ('NON_VACUITE', levier)
    sim = _sim()
    sim.output_gap_courant = -0.04
    sim.dette_courante *= 1.3
    sim.recettes_precedentes *= 0.9
    for sortie in (_premier_appel(levier, params, gdp=PIB_2025 * 1.1, inflation=0.06, unemployment=0.12),
                   _premier_appel(levier, params, gdp=PIB_2025 * 1.1, inflation=-0.01, unemployment=0.05),
                   _appel(sim, levier, params, gdp=PIB_2025 * 1.1)):
        assert _canon(sortie) == _canon(ref), levier


LECTURES_CROISEES = {
    'impot_plancher_patrimoine': {'isf_climatique'},
    'fiscalite_capital': set(),
    'multinationales': {'impot_societes'},
    'operations_financieres': set(),
}


@pytest.mark.parametrize('levier', W4)
def test_d3_aucune_lecture_croisee_non_declaree(levier):
    """§ 3 : en dehors des lectures croisées déclarées (ISF pour le plancher,
    taux d'IS pour les bénéfices), la sortie du handler ne dépend d'aucun autre
    levier du programme (programme mixte du harnais du cadre)."""
    autres = _sans(PROGRAMME_MIXTE, *LECTURES_CROISEES[levier])
    seul = _premier_appel(levier, BLOCS[levier])
    assert seul[1] != 0.0, ('NON_VACUITE', levier)
    assert _canon(_premier_appel(levier, BLOCS[levier], autres=autres)) == _canon(seul)


# ===========================================================================
# 4. Signe, monotonie, retournements (G5, W4-10, W4-14)
# ===========================================================================

def _croissante(valeurs, tol=1e-10):
    return all(b >= a - tol for a, b in zip(valeurs, valeurs[1:]))


def _decroissante(valeurs, tol=1e-10):
    return all(b <= a + tol for a, b in zip(valeurs, valeurs[1:]))


def _grille(bas, haut, n=41):
    return [bas + (haut - bas) * i / (n - 1) for i in range(n)]


def test_g5_plancher_signe_et_monotonie():
    """G5 : recette ≥ 0 sur tout le domaine ; croissante en taux (ISF compris :
    recette ∝ max(0 ; τ − intensité × taux max de l'ISF)), décroissante en
    évitement, non croissante en intensité de l'ISF (W4-4)."""
    taux_max = _borne('impot_plancher_patrimoine', 'taux', 'max')
    for i in (0.0, 0.5, 1.0):
        for e in (0.0, C.EVITEMENT_PLANCHER_DEFAUT, 0.95):
            recs = [_premier_appel('impot_plancher_patrimoine', {'taux': t, 'evitement': e},
                                   autres={'isf_climatique': {'intensite': i}})[1]
                    for t in _grille(0.0, taux_max)]
            assert all(r >= 0 for r in recs) and _croissante(recs), (i, e)
            assert recs[-1] > 0, ('NON_VACUITE', i, e)


def _verifier_z3(taux, e):
    recs = [_premier_appel('impot_plancher_patrimoine', {'taux': taux, 'evitement': e},
                           autres={'isf_climatique': {'intensite': i}})[1] for i in _grille(0.0, 1.0, 21)]
    assert recs[0] > 0, ('NON_VACUITE', taux, e)
    assert _decroissante(recs), ('DOUBLE_COMPTE', taux, e, recs)
    # Pas d'empilement au-delà du plancher : R_plancher ≤ (1 − e) × R_méca.
    assert max(recs) <= (1 - e) * C.R_REF_PLANCHER * taux / TAUX_TEXTE_PLANCHER + 1e-9, 'DOUBLE_COMPTE'


@pytest.mark.parametrize('taux', [0.005, 0.01, 0.02, 0.03])
def test_w4_4_z3_imputation_monotone_et_sans_empilement(taux):
    """W4-4 (Z3) : ∂R_plancher/∂intensité_ISF ≤ 0 sur une grille ; la recette
    du plancher ne dépasse jamais (1 − e) × la recette mécanique."""
    for e in (0.0, C.EVITEMENT_PLANCHER_DEFAUT):
        _verifier_z3(taux, e)


def _verifier_z2(annee_debut=None):
    """Z2 : ISF à 1 et plancher à 1 % → recette du plancher nulle (le plancher
    ne recompte pas ce que l'ISF prélève déjà) ; non-vacuité : sans ISF, le
    même plancher rapporte."""
    sans_isf = _premier_appel('impot_plancher_patrimoine', {'taux': C.ISF_TAUX_MAX})
    assert sans_isf[1] > 0, ('NON_VACUITE', sans_isf)
    avec_isf = _premier_appel('impot_plancher_patrimoine', {'taux': C.ISF_TAUX_MAX},
                              autres={'isf_climatique': {'intensite': 1.0}})
    assert avec_isf[1] == pytest.approx(0.0, abs=1e-12), ('DOUBLE_COMPTE', avec_isf)
    _, _, rapport, _ = simuler({'isf_climatique': {'intensite': 1.0},
                                'impot_plancher_patrimoine': {'taux': C.ISF_TAUX_MAX}},
                               annee_debut=annee_debut)
    assert rapport['valid'] is True, ('NON_VACUITE', rapport['warnings'])
    for an, imp in _impacts_du_levier(rapport, 'impot_plancher_patrimoine').items():
        assert imp.get('recettes', 0.0) == pytest.approx(0.0, abs=1e-12), ('DOUBLE_COMPTE', an, imp)


@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
def test_w4_3_z2_isf_complet_et_plancher_au_taux_de_l_isf(annee_debut):
    """W4-3 (Z2) : ISF à 1 et plancher à 1 % (= taux max de l'ISF) → recette du
    plancher 0 à 1e-12, au handler et en simulation complète."""
    _verifier_z2(annee_debut)


def _mutant_sans_imputation(self, original, measure, params, year, gdp, inflation, unemployment):
    """Double compte injecté : le plancher ignore l'ISF (pas d'imputation)."""
    sauve = self.mesures
    self.mesures = _sans(sauve, 'isf_climatique')
    try:
        return original(self, measure, params, year, gdp, inflation, unemployment)
    finally:
        self.mesures = sauve


def test_z_mutation_plancher_sans_imputation_de_l_isf(monkeypatch):
    """Par MUTATION (règle Z) : un plancher qui n'imputerait pas l'ISF compte
    deux fois le même patrimoine ; Z2 et Z3 échouent."""
    _verifier_z2()
    _verifier_z3(0.02, 0.0)
    _muter(monkeypatch, '_apply_impot_plancher_patrimoine', _mutant_sans_imputation)
    with pytest.raises(AssertionError, match='DOUBLE_COMPTE'):
        _verifier_z2()


# --- Revenus du capital : W4-10 (K2) -----------------------------------------

# Plancher du facteur lu UNE fois à l'import : la mutation le change dans le
# moteur, jamais dans la vérification.
PLANCHER_FACTEUR = C.ETI_PLANCHER_FACTEUR


def facteur_implicite(params, rec_ref):
    """Facteur MOYEN déduit de la recette : (ΔR_ref + recette de référence) /
    recette aux nouveaux taux sur l'assiette de référence. Assiette scindée : la
    recette aux nouveaux taux vaut τ f A_IR + τ_PS f_PS (A_PS − A_IR), et
    τ A_IR + τ_PS (A_PS − A_IR) = τ_IR A_IR + τ_PS A_PS : c'est la moyenne des deux
    facteurs pondérée par leurs recettes mécaniques."""
    p = {**NEUTRES['fiscalite_capital'], **params}
    ref = T_IR0 * C.A_CAPITAL_IR + T_PS0 * C.A_CAPITAL_PS
    meca = p['taux_ir_forfaitaire'] * C.A_CAPITAL_IR + p['prelevements_sociaux_capital'] * C.A_CAPITAL_PS
    return (rec_ref + ref) / meca


def facteurs_implicites(t_ir, t_ps, e):
    """(f, f_PS) déduits de DEUX appels du handler : à part IR au neutre, les deux
    facteurs sont égaux et la recette donne f_PS ; la recette au taux demandé
    donne ensuite f sur l'assiette du prélèvement forfaitaire."""
    f_ps = facteur_implicite({'prelevements_sociaux_capital': t_ps, 'elasticite': e},
                             _premier_appel('fiscalite_capital',
                                            {'prelevements_sociaux_capital': t_ps, 'elasticite': e})[1])
    _, rec, _ = _premier_appel('fiscalite_capital', {'taux_ir_forfaitaire': t_ir,
                                                     'prelevements_sociaux_capital': t_ps, 'elasticite': e})
    ref = T_IR0 * C.A_CAPITAL_IR + T_PS0 * C.A_CAPITAL_PS
    f = (rec + ref - t_ps * f_ps * (C.A_CAPITAL_PS - C.A_CAPITAL_IR)) / ((t_ir + t_ps) * C.A_CAPITAL_IR)
    return f, f_ps


def _verifier_k2_plancher_du_facteur():
    tir_max = _borne('fiscalite_capital', 'taux_ir_forfaitaire', 'max')
    tps_max = _borne('fiscalite_capital', 'prelevements_sociaux_capital', 'max')
    e_max = _borne('fiscalite_capital', 'elasticite', 'max')
    vus = []
    for e in (0.0, E_K0, e_max):
        for t_ir in _grille(0.0, tir_max, 10):
            for t_ps in _grille(0.0, tps_max, 7):
                if t_ir + t_ps == 0:
                    continue
                params = {'taux_ir_forfaitaire': t_ir, 'prelevements_sociaux_capital': t_ps, 'elasticite': e}
                _, rec, _ = _premier_appel('fiscalite_capital', params)
                moyen = facteur_implicite(params, rec)
                f, f_ps = facteurs_implicites(t_ir, t_ps, e)
                vus.append(f)
                for valeur in (moyen, f, f_ps):
                    assert valeur >= PLANCHER_FACTEUR - 1e-12, ('DOUBLE_COMPTE', params, moyen, f, f_ps)
    # Non-vacuité : le plancher du facteur de l'assiette du prélèvement forfaitaire
    # est atteint sur la grille (celui du reste de l'assiette sociale ne l'est pas :
    # il faudrait des prélèvements sociaux au-delà de leur borne).
    assert min(vus) == pytest.approx(PLANCHER_FACTEUR, abs=1e-9), ('NON_VACUITE', min(vus))


def test_w4_10_k2_facteur_comportemental_au_moins_le_plancher():
    """W4-10 (K2) : le facteur de comportement ne descend jamais sous
    ``ETI_PLANCHER_FACTEUR`` (forme et plancher de l'IR), sur tout le domaine."""
    _verifier_k2_plancher_du_facteur()


def test_w4_10_k2_mutation_sans_plancher_du_facteur(monkeypatch):
    """Par MUTATION : sans le plancher du facteur (constante mise à 0),
    l'assiette « réagit » au-delà de la forme de l'IR ; K2 échoue."""
    _verifier_k2_plancher_du_facteur()
    _patcher_constante(monkeypatch, 'ETI_PLANCHER_FACTEUR', 0.0)
    with pytest.raises(AssertionError, match='DOUBLE_COMPTE'):
        _verifier_k2_plancher_du_facteur()


def taux_total_au_sommet(elasticite):
    """[CALCUL] taux TOTAL τ* = τ_IR + τ_PS qui maximise la recette de l'assiette du
    prélèvement forfaitaire, g(τ) = τ × (1 + k (τ_ref − τ)), k = e / (1 − τ_ref)
    (facteur non plafonné) : τ* = (1 + k τ_ref) / (2k) = τ_ref / 2 + (1 − τ_ref) / (2e).
    Au défaut (e = 0,9) : ≈ 53,8 %."""
    k = elasticite / (1 - TAU_REF_CAPITAL)
    return (1 + k * TAU_REF_CAPITAL) / (2 * k)


def sommet_part_ir(elasticite, t_ps):
    """[CALCUL] part IR qui maximise la recette totale à τ_PS fixé : seul le terme
    de l'assiette du prélèvement forfaitaire dépend de la part IR (le reste de
    l'assiette sociale ne voit que τ_PS), d'où x* = τ* − τ_PS. Au défaut (e = 0,9,
    τ_PS = 18,6 %) : x* ≈ 35,2 %."""
    return taux_total_au_sommet(elasticite) - t_ps


def sommet_part_sociale(elasticite, t_ir):
    k = elasticite / (1 - TAU_REF_CAPITAL)
    return ((C.A_CAPITAL_PS / k - C.A_CAPITAL_PS * (t_ir - TAU_REF_CAPITAL) - t_ir * C.A_CAPITAL_IR)
            / (2 * C.A_CAPITAL_PS))


def _verifier_forme(recettes, grille, sommet):
    """Croissante avant le sommet, décroissante après (retournement documenté)."""
    avant = [r for t, r in zip(grille, recettes) if t <= sommet]
    apres = [r for t, r in zip(grille, recettes) if t >= sommet]
    assert _croissante(avant), (sommet, avant)
    assert _decroissante(apres), (sommet, apres)


def test_w4_10_k2_monotonie_ou_retournement_documente():
    """W4-10 (K2) : à élasticité nulle, recette strictement croissante en chaque
    taux ; au défaut, la recette suit la forme du contrat, croissante jusqu'au
    sommet dérivé de la formule puis décroissante (retournement documenté : au
    défaut, la part IR culmine vers 35 %, soit un taux total d'environ 54 % ; la
    part sociale croît sur tout son domaine). Le facteur reste non plafonné au
    défaut sur ce domaine, ce qui rend la forme analytique exacte.

    Remplace la version qui verrouillait un sommet de la part IR à 12,93 %
    (assiette commune : la réaction au taux total érodait toute l'assiette
    sociale, revue adverse R-1 C1 / R-2 C1)."""
    tir_max = _borne('fiscalite_capital', 'taux_ir_forfaitaire', 'max')
    tps_max = _borne('fiscalite_capital', 'prelevements_sociaux_capital', 'max')
    g_ir, g_ps = _grille(0.0, tir_max), _grille(0.0, tps_max)
    for grille, cle in ((g_ir, 'taux_ir_forfaitaire'), (g_ps, 'prelevements_sociaux_capital')):
        recs = [_premier_appel('fiscalite_capital', {cle: t, 'elasticite': 0.0})[1] for t in grille]
        assert all(b > a for a, b in zip(recs, recs[1:])), cle
    assert 1 + E_K0 * ((1 - (tir_max + T_PS0)) - (1 - TAU_REF_CAPITAL)) / (1 - TAU_REF_CAPITAL) \
        > C.ETI_PLANCHER_FACTEUR
    recs_ir = [_premier_appel('fiscalite_capital', {'taux_ir_forfaitaire': t})[1] for t in g_ir]
    _verifier_forme(recs_ir, g_ir, sommet_part_ir(E_K0, T_PS0))
    recs_ps = [_premier_appel('fiscalite_capital', {'prelevements_sociaux_capital': t})[1] for t in g_ps]
    sommet_ps = sommet_part_sociale(E_K0, T_IR0)
    _verifier_forme(recs_ps, g_ps, sommet_ps)
    assert sommet_ps > tps_max and _croissante(recs_ps)
    # Non-vacuité du retournement : le sommet de la part IR est DANS son domaine.
    assert 0 < sommet_part_ir(E_K0, T_PS0) < tir_max


# --- Revenus du capital : assiette sociale scindée (revue adverse, R-1 C1 / R-2 C1)

def test_capital_hausse_des_seuls_prelevements_sociaux_identique_au_bit():
    """Une variation des SEULS prélèvements sociaux (part IR au droit voté) rend
    exactement, au bit, la recette de la formule de l'assiette commune : le
    correctif ne touche que ce qui dépend de la part IR. Vérifié sur la fonction
    pure (hors indice) et sur la sortie du handler (indice appliqué), sur tout le
    domaine des prélèvements sociaux et trois élasticités."""
    tps_max = _borne('fiscalite_capital', 'prelevements_sociaux_capital', 'max')
    e_max = _borne('fiscalite_capital', 'elasticite', 'max')
    gdp = PIB_2025 * 1.137
    sim = _sim()
    indice = sim._indice_pib_source(C.ANNEE_SOURCE_CAPITAL, gdp)
    n = 0
    for e in (0.0, E_K0, e_max):
        for t_ps in _grille(0.0, tps_max, 61):
            p = {'taux_ir_forfaitaire': T_IR0, 'prelevements_sociaux_capital': t_ps, 'elasticite': e}
            temoin = dr_ref_capital_assiette_commune(T_IR0, t_ps, e)
            assert mod_taux.variation_capital_hors_indice(p).hex() == temoin.hex(), (e, t_ps)
            _, rec, _ = _premier_appel('fiscalite_capital', {'prelevements_sociaux_capital': t_ps,
                                                             'elasticite': e}, gdp=gdp)
            if p != NEUTRES['fiscalite_capital']:
                assert rec.hex() == (temoin * indice).hex(), (e, t_ps, rec, temoin * indice)
                n += 1
    assert n > 150, ('NON_VACUITE', n)


@pytest.mark.parametrize('hausse', [0.001, 0.01, 0.022, 0.072, 0.15])
def test_capital_hausse_de_la_part_ir_recette_positive_et_gini_en_baisse(hausse):
    """Une hausse de la part IR du prélèvement forfaitaire, sous le sommet de
    recette, RAPPORTE (ΔR > 0) et fait BAISSER le Gini émis et la compétitivité
    (impôt sur le capital), à l'élasticité par défaut. Avec l'assiette commune,
    +1 point rendait −0,06 Md€, +7,2 points −0,37 Md€ et un Gini en hausse."""
    t_ir = T_IR0 + hausse
    assert t_ir < sommet_part_ir(E_K0, T_PS0)
    _, rec, imp = _premier_appel('fiscalite_capital', {'taux_ir_forfaitaire': t_ir})
    assert rec > 0, (hausse, rec)
    assert imp['gini'] < 0, (hausse, imp['gini'])
    assert imp['competitivite'] < 0, (hausse, imp['competitivite'])
    # Et symétriquement, une baisse de la part IR COÛTE de la recette.
    _, rec_baisse, imp_baisse = _premier_appel('fiscalite_capital', {'taux_ir_forfaitaire': T_IR0 - min(hausse, T_IR0)})
    assert rec_baisse < 0 and imp_baisse['gini'] > 0, (hausse, rec_baisse)


def test_capital_hausse_de_la_part_ir_dans_le_moteur_complet():
    """Moteur complet (statu quo, mode cadre 2028, porte stricte et tolérante) :
    relever la part IR à 20 % rapporte chaque année, le Gini ponctuel émis est
    négatif, et la dette 2032 baisse par rapport au statu quo."""
    for strict in (False, True):
        df0 = simuler({}, annee_debut=DEBUT_CADRE, strict=strict)[0]
        df, _, rapport, _ = simuler({'fiscalite_capital': {'taux_ir_forfaitaire': 0.20}},
                                    annee_debut=DEBUT_CADRE, strict=strict)
        impacts = _impacts_du_levier(rapport, 'fiscalite_capital')
        annees = [a for a in impacts if DEBUT_CADRE <= a <= FIN_MANDAT]
        assert len(annees) == FIN_MANDAT - DEBUT_CADRE + 1, ('NON_VACUITE', sorted(impacts))
        assert all(impacts[a]['recettes'] > 0 for a in annees), impacts
        assert sum(impacts[a].get('gini', 0.0) for a in annees) < 0
        dette = df.set_index('Année')['Dette/PIB %']
        dette0 = df0.set_index('Année')['Dette/PIB %']
        assert dette[FIN_MANDAT] < dette0[FIN_MANDAT], (strict, dette[FIN_MANDAT], dette0[FIN_MANDAT])


def test_capital_sommet_de_recette_dans_la_fourchette_publiee():
    """Sommet de recette de la part IR (prélèvements sociaux au droit voté,
    élasticité par défaut), cherché sur la sortie du handler : le taux TOTAL au
    sommet tombe dans la fourchette publiée du taux de Laffer des revenus du
    capital en France, de 43 % (élasticité croisée des revenus du travail
    comprise) à 57 % (sans elle) : Lefebvre, Lehmann et Sicsic, Scandinavian
    Journal of Economics 127(2), 2025, p. 460-489 (constante
    ``TAUX_LAFFER_CAPITAL_FOURCHETTE_PCT``). Avec l'assiette commune, le sommet
    était à 31,5 % de taux total, hors de la fourchette."""
    bas, haut = C.TAUX_LAFFER_CAPITAL_FOURCHETTE_PCT
    pas = 0.0005
    tir_max = _borne('fiscalite_capital', 'taux_ir_forfaitaire', 'max')
    grille = [i * pas for i in range(int(round(tir_max / pas)) + 1)]
    recs = [_premier_appel('fiscalite_capital', {'taux_ir_forfaitaire': t})[1] for t in grille]
    i_max = max(range(len(recs)), key=recs.__getitem__)
    assert 0 < i_max < len(grille) - 1, ('NON_VACUITE : sommet au bord du domaine', grille[i_max])
    total = grille[i_max] + T_PS0
    assert bas / 100 <= total <= haut / 100, (total, (bas, haut))
    # Le sommet trouvé sur la grille est celui de la formule, au pas près.
    assert abs(total - taux_total_au_sommet(E_K0)) <= pas, (total, taux_total_au_sommet(E_K0))


# --- TSN et TTF : W4-14 (O2) et forme -----------------------------------------

def test_w4_14_o2_volume_ttf_positif_et_forme_de_la_recette():
    """W4-14 (O2) : volume de la TTF ≥ 0 sur tout le domaine (déduit de la
    recette) ; recette croissante jusqu'à τ* = (pas + ε τ₀) / (2 ε), puis
    décroissante jusqu'au volume nul, puis constante (perte de toute la
    recette de référence) — retournement documenté, dérivé de la formule ;
    au défaut d'élasticité, croissante sur tout le domaine."""
    pib = pib_2026_statu_quo()
    t_max = _borne('operations_financieres', 'taux_ttf', 'max')
    grille = _grille(0.0, t_max)
    for eps in (0.0, E_TTF0, 0.1, _borne('operations_financieres', 'elasticite_volume', 'max')):
        recs = [_premier_appel('operations_financieres', {'taux_ttf': t, 'elasticite_volume': eps}, gdp=pib)[1]
                for t in grille]
        for t, r in zip(grille, recs):
            if t > 0:
                assert (r + T_TTF0 * C.V_REF_TTF) / t >= -1e-9, ('volume négatif', eps, t, r)
        assert min(recs) >= -T_TTF0 * C.V_REF_TTF - 1e-9
        if eps == 0:
            assert all(b > a for a, b in zip(recs, recs[1:]))
            continue
        sommet = (PAS_ELASTICITE_TTF + eps * T_TTF0) / (2 * eps)
        _verifier_forme(recs, grille, sommet)
        if eps == E_TTF0:
            assert sommet > t_max and _croissante(recs)


def test_g5_tsn_assiette_positive_et_forme_de_la_recette():
    """G5 (TSN) : assiette ≥ 0 sur tout le domaine ; recette croissante jusqu'à
    τ* = (1 + e τ₀) / (2e), décroissante ensuite (retournement documenté) ; au
    défaut d'érosion, croissante sur tout le domaine."""
    t_max = _borne('multinationales', 'taux_tsn', 'max')
    grille = _grille(0.0, t_max)
    for e in (0.0, E_TSN0, 5.0, _borne('multinationales', 'erosion_tsn', 'max')):
        recs = [_premier_appel('multinationales', {'taux_tsn': t, 'erosion_tsn': e})[1] for t in grille]
        for t, r in zip(grille, recs):
            if t > 0:
                assert (r + T_TSN0 * C.A_TSN) / t >= -1e-9, ('assiette négative', e, t, r)
        if e == 0:
            assert all(b > a for a, b in zip(recs, recs[1:]))
            continue
        sommet = (1 + e * T_TSN0) / (2 * e)
        _verifier_forme(recs, grille, sommet)
        if e == E_TSN0:
            assert sommet > t_max and _croissante(recs)


@pytest.mark.parametrize('levier, cle', [
    ('multinationales', 'benefices_recuperes'), ('operations_financieres', 'rachats_actions'),
    ('operations_financieres', 'crypto_actifs'), ('fiscalite_capital', 'rendement_md'),
    ('multinationales', 'rendement_tsn_md'), ('operations_financieres', 'rendement_ttf_md'),
])
def test_g5_montants_lineaires_sur_le_domaine(levier, cle):
    """G5 (montants) : recette = montant sur tout le domaine du paramètre
    (linéaire, croissante, signe du montant)."""
    for x in _grille(_borne(levier, cle, 'min'), _borne(levier, cle, 'max'), 11):
        _, rec, _ = _premier_appel(levier, {cle: x}, gdp=pib_2026_statu_quo())
        assert rec == pytest.approx(x, rel=1e-12, abs=1e-12), (levier, cle, x)


# ===========================================================================
# 5. Symétrie (G6)
# ===========================================================================

SYMETRIES = [
    ('fiscalite_capital', {'rendement_md': 3.0}, {'rendement_md': -3.0}),
    ('multinationales', {'rendement_tsn_md': 1.0}, {'rendement_tsn_md': -1.0}),
    ('operations_financieres', {'rendement_ttf_md': 3.0}, {'rendement_ttf_md': -3.0}),
    ('operations_financieres', {'rachats_actions': 0.2}, {'rachats_actions': -0.2}),
    # Taux à comportement nul : partie mécanique linéaire autour du neutre.
    ('fiscalite_capital', {'taux_ir_forfaitaire': T_IR0 + 0.05, 'elasticite': 0.0},
     {'taux_ir_forfaitaire': T_IR0 - 0.05, 'elasticite': 0.0}),
    ('fiscalite_capital', {'prelevements_sociaux_capital': T_PS0 + 0.04, 'elasticite': 0.0},
     {'prelevements_sociaux_capital': T_PS0 - 0.04, 'elasticite': 0.0}),
    ('multinationales', {'taux_tsn': T_TSN0 + 0.02, 'erosion_tsn': 0.0},
     {'taux_tsn': T_TSN0 - 0.02, 'erosion_tsn': 0.0}),
    ('operations_financieres', {'taux_ttf': T_TTF0 + 0.002, 'elasticite_volume': 0.0},
     {'taux_ttf': T_TTF0 - 0.002, 'elasticite_volume': 0.0}),
]


@pytest.mark.parametrize('levier, plus, moins', SYMETRIES,
                         ids=[f'{l}-{"-".join(p)}' for l, p, _ in SYMETRIES])
def test_g6_symetrie(levier, plus, moins):
    """G6 : +x et −x donnent des effets directs opposés (budget, canaux
    ménages, Gini, compétitivité) ; pour un taux, à comportement nul."""
    gdp = pib_2026_statu_quo()
    _, r_plus, i_plus = _premier_appel(levier, plus, gdp=gdp)
    _, r_moins, i_moins = _premier_appel(levier, moins, gdp=gdp)
    assert r_plus > 0, ('NON_VACUITE', levier, plus)
    assert r_moins == pytest.approx(-r_plus, rel=1e-12, abs=1e-12)
    for cle in ('gini', 'competitivite'):
        assert _canal(i_moins, cle) == pytest.approx(-_canal(i_plus, cle), rel=1e-12, abs=1e-16), cle
    for c, v in _canal(i_plus, 'menages').items():
        assert _canal(i_moins, 'menages')[c] == pytest.approx(-v, rel=1e-12, abs=1e-12), c


# ===========================================================================
# 6. Effets ponctuels en incrément (G8, G8-retour, W4-19)
# ===========================================================================

def _cumul_le_long(levier, chemin, *, autres_par_etape=None):
    """Σ des effets ponctuels (Gini, compétitivité) le long d'un chemin de
    paramètres, chaque bloc vu deux fois (la seconde fois n'émet rien)."""
    sim = _sim()
    total = {'gini': 0.0, 'competitivite': 0.0}
    secondes = []
    for i, params in enumerate(chemin):
        if autres_par_etape is not None:
            sim.mesures = {**copy.deepcopy(autres_par_etape[i]), levier: copy.deepcopy(params)}
        for passage in range(2):
            imp = _appel(sim, levier, params)[2]
            for c in total:
                total[c] += _canal(imp, c)
            if passage == 1:
                secondes.append({c: _canal(imp, c) for c in total})
    return total, secondes


CHEMINS = [
    ('impot_plancher_patrimoine', [{'taux': t} for t in (0.01, 0.02, 0.03)]),
    ('impot_plancher_patrimoine', [{'taux': 0.02, 'evitement': e} for e in (0.6, 0.3, 0.0)]),
    ('fiscalite_capital', [{'prelevements_sociaux_capital': t} for t in (0.19, 0.21, 0.25)]),
    ('fiscalite_capital', [{'rendement_md': k * 5.0 / 5} for k in range(1, 6)]),
    ('multinationales', [{'benefices_recuperes': k * 6.0 / 5} for k in range(1, 6)]),
    ('multinationales', [{'taux_tsn': t} for t in (0.04, 0.06, 0.05)]),
    ('operations_financieres', [{'taux_ttf': t} for t in (0.005, 0.006, 0.008)]),
    ('operations_financieres', [{'rachats_actions': k * 5.0 / 5} for k in range(1, 6)]),
    ('operations_financieres', [{'crypto_actifs': k * 2.0 / 5, 'rendement_ttf_md': k * 1.0}
                                for k in range(1, 6)]),
]
IDS_CHEMINS = [f'{l}-{"-".join(c[0])}' for l, c in CHEMINS]


def _verifier_g8(levier, chemin):
    cumul, secondes = _cumul_le_long(levier, chemin)
    niveau = _premier_appel(levier, chemin[-1])[2]
    assert _canal(niveau, 'competitivite') != 0.0, ('NON_VACUITE', levier)
    assert _canal(_premier_appel(levier, chemin[0])[2], 'competitivite') != _canal(niveau, 'competitivite'), \
        ('NON_VACUITE', 'chemin trivial')
    for c in ('gini', 'competitivite'):
        assert cumul[c] == pytest.approx(_canal(niveau, c), rel=1e-12, abs=1e-15), ('DOUBLE_COMPTE', levier, c)
    assert all(v == 0.0 for s in secondes for v in s.values()), ('émis plus d\'une fois', secondes)


@pytest.mark.parametrize('levier, chemin', CHEMINS, ids=IDS_CHEMINS)
def test_g8_increments_cumul_egal_au_niveau_atteint(levier, chemin):
    """G8 : effets ponctuels émis UNE fois par niveau (le même bloc revu n'émet
    rien) et en INCRÉMENT : le long d'une rampe (cinq paliers d'un montant) ou
    d'un chemin de taux, Σ incréments = effet du niveau atteint."""
    _verifier_g8(levier, chemin)


def _effet_ponctuel_en_niveau(self, cle, params_dict, effet):
    """Ancien mode NIVEAU (v0.6.11) : l'effet complet à chaque changement."""
    statut, _ = self._ponctuel(cle, params_dict)
    valeur = effet(params_dict)
    if statut == 'inchange':
        return tuple(0.0 for _ in valeur) if isinstance(valeur, tuple) else 0.0
    return valeur


def test_g8_mutation_effet_compte_a_chaque_palier(monkeypatch):
    """Par MUTATION : si l'effet ponctuel était recompté au niveau à chaque
    palier (rampe comptée trois fois), G8 échoue."""
    _verifier_g8(*CHEMINS[4])
    monkeypatch.setattr(BudgetSimulatorV45, '_effet_ponctuel', _effet_ponctuel_en_niveau)
    with pytest.raises(AssertionError, match='DOUBLE_COMPTE'):
        _verifier_g8(*CHEMINS[4])


RETOURS = [
    ('impot_plancher_patrimoine', {'taux': 0.02}),
    ('fiscalite_capital', {'prelevements_sociaux_capital': 0.22, 'taux_ir_forfaitaire': 0.15}),
    ('fiscalite_capital', {'rendement_md': 4.0}),
    ('multinationales', {'benefices_recuperes': 5.0, 'taux_tsn': 0.06}),
    ('multinationales', {'rendement_tsn_md': 2.0}),
    ('operations_financieres', {'taux_ttf': 0.006, 'rachats_actions': 1.0, 'crypto_actifs': 0.5}),
    ('operations_financieres', {'rendement_ttf_md': 2.0}),
]


@pytest.mark.parametrize('levier, params', RETOURS, ids=[f'{l}-{"-".join(p)}' for l, p in RETOURS])
def test_g8_retour_au_neutre_rend_l_effet(levier, params):
    """G8-retour (profil « une seule année » vu du handler) : un levier REVENU
    à ses valeurs neutres rend son effet ponctuel (pas de retour anticipé tant
    que le traqueur porte une clé du levier) : Σ Gini et compétitivité = 0 à
    1e-12, recette nulle l'année du retour."""
    neutre = dict(NEUTRES[levier])
    sim = _sim()
    emis = _appel(sim, levier, params)[2]
    assert _canal(emis, 'competitivite') != 0.0, ('NON_VACUITE', levier)
    retour = _appel(sim, levier, neutre)
    suite = _appel(sim, levier, neutre)
    assert retour[1] == 0.0 and suite[1] == 0.0
    for c in ('gini', 'competitivite'):
        assert _canal(retour[2], c) == pytest.approx(-_canal(emis, c), rel=1e-12, abs=1e-15), c
        assert _canal(emis, c) + _canal(retour[2], c) + _canal(suite[2], c) == pytest.approx(0.0, abs=1e-12)


def test_w4_19_lectures_croisees_dans_le_dictionnaire_de_l_effet():
    """W4-19 : chemin de l'ISF (0 puis 1, ou 1 dès le début) et du taux d'IS
    (25 % puis 20 %, ou 20 % dès le début) : Σ des incréments Gini et
    compétitivité du plancher et des bénéfices récupérés identique à 1e-12
    quel que soit le chemin (les lectures croisées sont dans ``p``)."""
    plancher = [{'taux': 0.02}] * 3
    a, _ = _cumul_le_long('impot_plancher_patrimoine', plancher,
                          autres_par_etape=[{'isf_climatique': {'intensite': i}} for i in (0.0, 1.0, 1.0)])
    b, _ = _cumul_le_long('impot_plancher_patrimoine', plancher,
                          autres_par_etape=[{'isf_climatique': {'intensite': 1.0}}] * 3)
    zero, _ = _cumul_le_long('impot_plancher_patrimoine', plancher,
                             autres_par_etape=[{'isf_climatique': {'intensite': 0.0}}] * 3)
    assert b['gini'] != zero['gini'], ('NON_VACUITE', 'l\'ISF change l\'effet')
    for c in a:
        assert a[c] == pytest.approx(b[c], rel=1e-12, abs=1e-15), ('plancher', c, a, b)
    multi = [{'benefices_recuperes': 5.0}] * 3
    a, _ = _cumul_le_long('multinationales', multi,
                          autres_par_etape=[{'impot_societes': {'taux': t, 'niches': 0}}
                                            for t in (0.25, 0.20, 0.20)])
    b, _ = _cumul_le_long('multinationales', multi,
                          autres_par_etape=[{'impot_societes': {'taux': 0.20, 'niches': 0}}] * 3)
    assert a['competitivite'] == pytest.approx(b['competitivite'], rel=1e-12, abs=1e-15), (a, b)
    assert b['competitivite'] == pytest.approx(C.COMPET_IS_PAR_MD * 5.0 * 0.20 / TAUX_IS_REF, rel=1e-12)


# ===========================================================================
# 7. Simulations complètes (G1, G4, G10', G12, W4-12, W4-16, solde)
# ===========================================================================

BASES = {'statu_quo': {}, 'droit_en_vigueur': DROIT, **_SCENARIOS_PUBLIES}
_CACHE = {}


def _simuler_g1(mesures, annee_debut, strict, cache=True):
    if not cache:
        return simuler(mesures, annee_debut=annee_debut, strict=strict)[:3]
    cle = (json.dumps(mesures, sort_keys=True), annee_debut, strict)
    if cle not in _CACHE:
        _CACHE[cle] = simuler(mesures, annee_debut=annee_debut, strict=strict)[:3]
    return _CACHE[cle]


# Blocs NON neutres (un paramètre de comportement hors de son défaut, ou un
# montant présent à zéro) dont l'effet est nul : le handler CALCULE (pas de
# retour anticipé) et doit rendre exactement zéro (W4-1, W4-13).
NEUTRES_EN_CALCUL = [
    ('impot_plancher_patrimoine', {'taux': 0.0, 'evitement': 0.5}),
    ('impot_plancher_patrimoine', {'taux': 0.0, 'evitement': 0.0}),
    ('fiscalite_capital', {'elasticite': 1.5}),
    ('fiscalite_capital', {'taux_ir_forfaitaire': T_IR0, 'prelevements_sociaux_capital': T_PS0,
                           'elasticite': 0.0}),
    ('multinationales', {'erosion_tsn': 5.0}),
    ('multinationales', {'benefices_recuperes': 0.0, 'taux_tsn': T_TSN0, 'erosion_tsn': 0.0}),
    ('operations_financieres', {'elasticite_volume': 0.2}),
    ('operations_financieres', {'taux_ttf': T_TTF0, 'rachats_actions': 0.0, 'crypto_actifs': 0.0,
                                'elasticite_volume': 0.0}),
]


def _verifier_g1(levier, bloc, annee_debut, strict, bases, cache=True):
    """Bases : statu quo et droit en vigueur toujours ; les 10 scénarios publiés
    quand ``scenarios.json`` est disponible (dépôt parent, ou
    ``BUDGETLAB_SCENARIOS_JSON``)."""
    for nom, base in bases.items():
        ref = _simuler_g1(base, annee_debut, strict)
        df, det, rapport = _simuler_g1({**base, levier: bloc}, annee_debut, strict, cache=cache)
        _sans_echec(rapport, levier)
        assert df.equals(ref[0]) and det.equals(ref[1]), ('DOUBLE_COMPTE', nom, levier, bloc)
        assert _canon(rapport['measure_impacts_by_year']) == _canon(ref[2]['measure_impacts_by_year']), \
            ('DOUBLE_COMPTE', nom, levier, bloc)
        assert rapport['valid'] == ref[2]['valid'] and rapport['warnings'] == ref[2]['warnings'], (nom, levier)


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
@pytest.mark.parametrize('levier, bloc', NEUTRES_EN_CALCUL,
                         ids=[f'{l}-{"-".join(f"{k}={v:g}" for k, v in b.items())}' for l, b in NEUTRES_EN_CALCUL])
def test_w4_1_g1_neutralite_au_bit_en_calcul(levier, bloc, annee_debut, strict):
    """W4-1 (G1, G2) : un bloc dont l'EFFET est neutre sans que toutes ses
    valeurs le soient (comportement hors défaut, taux nul) laisse au bit
    trajectoire, détails, impacts par levier, validité et avis, sur le statu
    quo, le droit en vigueur et les 10 scénarios publiés, dans les deux modes et
    les deux portes. (Le bloc entièrement neutre est couvert par le G1 du
    socle.)"""
    _verifier_g1(levier, bloc, annee_debut, strict, BASES)


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
def test_g1_plancher_a_taux_nul_avec_isf_complet(annee_debut, strict):
    """Plancher à taux nul (évitement quelconque) avec l'ISF à 1 : aucune
    division par zéro, sorties de l'ISF seul au bit."""
    _verifier_g1('impot_plancher_patrimoine', {'taux': 0.0, 'evitement': 0.5}, annee_debut, strict,
                 {'isf': {'isf_climatique': {'intensite': 1.0}}})


def _mutant_rachats_compte_la_taxe_existante(self, original, measure, params, year, gdp, inflation, unemployment):
    """Double compte injecté : la taxe de 8 % déjà dans la référence (≈ 0,2 Md€,
    borne basse sourcée de l'écart) est recomptée par le levier."""
    return _ajouter_recette(original(self, measure, params, year, gdp, inflation, unemployment),
                            -_borne('operations_financieres', 'rachats_actions', 'min'))


def test_w4_13_o1_mutation_taxe_existante_recomptee(monkeypatch):
    """Par MUTATION (règle F) : un levier qui recompterait la taxe sur les
    rachats déjà incluse dans la référence casse la neutralité au bit."""
    bloc = NEUTRES_EN_CALCUL[-1][1]
    bases = {'statu_quo': {}}
    _verifier_g1('operations_financieres', bloc, None, False, bases, cache=False)
    _muter(monkeypatch, '_apply_operations_financieres', _mutant_rachats_compte_la_taxe_existante)
    with pytest.raises(AssertionError, match='DOUBLE_COMPTE'):
        _verifier_g1('operations_financieres', bloc, None, False, bases, cache=False)


# --- G4 : domaine ------------------------------------------------------------

HORS_DOMAINE = [  # (levier, contexte, paramètre, valeur demandée, borne attendue)
    ('impot_plancher_patrimoine', {}, 'taux', 0.05, 'max'),
    ('impot_plancher_patrimoine', {'taux': 0.02}, 'evitement', 1.2, 'max'),
    ('fiscalite_capital', {}, 'taux_ir_forfaitaire', 0.6, 'max'),
    ('fiscalite_capital', {}, 'prelevements_sociaux_capital', 0.5, 'max'),
    ('fiscalite_capital', {'taux_ir_forfaitaire': 0.2}, 'elasticite', 3.0, 'max'),
    ('fiscalite_capital', {}, 'rendement_md', 20.0, 'max'),
    ('fiscalite_capital', {}, 'rendement_md', -20.0, 'min'),
    ('multinationales', {}, 'benefices_recuperes', 20.0, 'max'),
    ('multinationales', {}, 'taux_tsn', 0.2, 'max'),
    ('multinationales', {'taux_tsn': 0.06}, 'erosion_tsn', 20.0, 'max'),
    ('multinationales', {}, 'rendement_tsn_md', 15.0, 'max'),
    ('multinationales', {}, 'rendement_tsn_md', -5.0, 'min'),
    ('operations_financieres', {}, 'taux_ttf', 0.02, 'max'),
    ('operations_financieres', {'taux_ttf': 0.006}, 'elasticite_volume', 0.5, 'max'),
    ('operations_financieres', {}, 'rendement_ttf_md', 15.0, 'max'),
    ('operations_financieres', {}, 'rendement_ttf_md', -5.0, 'min'),
    ('operations_financieres', {}, 'rachats_actions', -1.0, 'min'),
    ('operations_financieres', {}, 'rachats_actions', 20.0, 'max'),
    ('operations_financieres', {}, 'crypto_actifs', 10.0, 'max'),
]
IDS_HD = [f'{l}-{p}-{v:g}' for l, _, p, v, _ in HORS_DOMAINE]


@pytest.mark.parametrize('levier, contexte, param, valeur, cote', HORS_DOMAINE, ids=IDS_HD)
def test_g4_hors_domaine_tolerant_ecretage_trace_et_borne_appliquee(levier, contexte, param, valeur, cote):
    """G4 (tolérant) : hors bornes → écrêtage tracé (``leviers_ecretes``, motif
    « domaine », ``valid`` faux) et le levier APPLIQUÉ à la borne : trajectoire
    et impacts du levier identiques au bit à ceux de la borne demandée
    directement. (W4-15 : la borne de ``benefices_recuperes`` est la constante
    nommée ``BENEFICES_RECUPERES_MAX``.)"""
    borne = _borne(levier, param, cote)
    df, det, rapport, _ = simuler({levier: {**contexte, param: valeur}})
    df_b, det_b, rapport_b, _ = simuler({levier: {**contexte, param: borne}})
    _sans_echec(rapport, levier)
    assert _impacts_du_levier(rapport_b, levier), ('NON_VACUITE', levier, param)
    assert rapport['valid'] is False
    assert {'levier': f'{levier}.{param}', 'applique': borne, 'motif': 'domaine'}.items() <= \
        next(e for e in rapport['leviers_ecretes'] if e['levier'] == f'{levier}.{param}').items()
    assert df.equals(df_b) and det.equals(det_b)
    assert _canon(_impacts_du_levier(rapport, levier)) == _canon(_impacts_du_levier(rapport_b, levier))
    if param == 'benefices_recuperes':
        assert borne == pytest.approx(C.BENEFICES_RECUPERES_MAX, abs=1e-9)


@pytest.mark.parametrize('levier, contexte, param, valeur, cote', HORS_DOMAINE, ids=IDS_HD)
def test_g4_hors_domaine_strict_refus(levier, contexte, param, valeur, cote):
    """G4 (strict, garde verte dès le socle : la porte précède le handler)."""
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1'}):
        with pytest.raises(ExceptionGroup) as info:
            BudgetSimulatorV45(periods=10, mesures={levier: {**contexte, param: valeur}}).simulate()
    assert any(isinstance(e, EntreeInvalide) for e in info.value.exceptions), info.value.exceptions


@pytest.mark.parametrize('valeur', [float('nan'), float('inf'), float('-inf')], ids=['nan', 'inf', '-inf'])
@pytest.mark.parametrize('levier, param', [(l, p) for l in W4 for p in REGISTRE[l]['parametres']])
def test_g4_non_finis_refuses_en_strict(levier, param, valeur):
    """G4 : NaN et ±inf refusés en strict (garde verte dès le socle)."""
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1'}):
        with pytest.raises(ExceptionGroup) as info:
            BudgetSimulatorV45(periods=2, mesures={levier: {param: valeur}}).simulate()
    assert any(isinstance(e, EntreeInvalide) for e in info.value.exceptions)


@pytest.mark.parametrize('levier, contexte, param', [
    ('impot_plancher_patrimoine', {'taux': 0.02}, 'evitement'),
    ('fiscalite_capital', {'prelevements_sociaux_capital': 0.2}, 'elasticite'),
    ('multinationales', {'taux_tsn': 0.06}, 'erosion_tsn'),
    ('operations_financieres', {'taux_ttf': 0.006}, 'elasticite_volume'),
])
def test_g4_non_fini_tolerant_retire_et_defaut_applique(levier, contexte, param):
    """G4 (tolérant) : un paramètre de comportement NaN est retiré (correction
    tracée) et le handler applique son défaut : trajectoire identique au bloc
    sans ce paramètre."""
    df, det, rapport, _ = simuler({levier: {**contexte, param: float('nan')}})
    df_d, det_d, rapport_d, _ = simuler({levier: dict(contexte)})
    _sans_echec(rapport, levier)
    assert rapport['valid'] is False and rapport_d['valid'] is True
    assert df.equals(df_d) and det.equals(det_d)


# --- G12 (R-IDX), G8 en simulation, solde ------------------------------------

def _verifier_r_idx_taux(levier, bloc, annee_debut, strict):
    _, _, rapport, sim = simuler({levier: bloc}, annee_debut=annee_debut, strict=strict)
    _sans_echec(rapport, levier)
    debut = _debut(annee_debut)
    imp = _impacts_du_levier(rapport, levier)
    assert sorted(imp) == list(range(debut, FIN_SIMULATION + 1)), ('NON_VACUITE', sorted(imp))
    source = ANNEE_SOURCE[levier]
    pib_source = PIB_2025 if source == 2025 else sim._pib_nominal_par_annee[source]
    r_ref, *_ = attendu(levier, bloc, gdp=pib_source, annees_ecoulees=99, pib_2026=pib_source)
    for an in range(debut, FIN_SIMULATION + 1):
        ph = phasage_plancher(an - debut) if levier == 'impot_plancher_patrimoine' else 1.0
        att = r_ref * ph * sim._pib_nominal_par_annee[an] / pib_source
        assert imp[an]['recettes'] == pytest.approx(att, rel=1e-12), ('DOUBLE_COMPTE', levier, an)


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
@pytest.mark.parametrize('levier', W4)
def test_g12_taux_suit_son_assiette_depuis_l_annee_source(levier, annee_debut, strict):
    """G12 (R-IDX, taux) : ΔR_t / ΔR_s = PIB_t / PIB_s (année source s : 2025,
    ou 2026 pour la TTF, PIB lu dans l'enregistrement du moteur) à 1e-12,
    chaque année d'application, phasage de l'ISF compris pour le plancher ;
    rien avant le début du programme."""
    _verifier_r_idx_taux(levier, BLOCS[levier], annee_debut, strict)


def _verifier_r_idx_montant(levier, bloc, valeur, annee_debut, strict):
    _, _, rapport, _ = simuler({levier: bloc}, annee_debut=annee_debut, strict=strict)
    _sans_echec(rapport, levier)
    debut = _debut(annee_debut)
    imp = _impacts_du_levier(rapport, levier)
    assert sorted(imp) == list(range(debut, FIN_SIMULATION + 1)), ('NON_VACUITE', sorted(imp))
    for an in range(debut, FIN_SIMULATION + 1):
        assert imp[an]['recettes'] == pytest.approx(valeur, rel=1e-12), ('DOUBLE_COMPTE', levier, an, imp[an])


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
@pytest.mark.parametrize('levier, bloc, valeur', MONTANTS, ids=IDS_MONTANTS)
def test_g12_montant_constant_en_euros_courants(levier, bloc, valeur, annee_debut, strict):
    """G12 (R-IDX, montants) : un paramètre en Md€ (modes ``rendement_*``,
    bénéfices récupérés au taux de référence, rachats, crypto-actifs) donne
    Δ_t = montant à 1e-12 chaque année d'application, dans les deux modes et
    les deux portes ; aucun indice."""
    _verifier_r_idx_montant(levier, bloc, valeur, annee_debut, strict)


def _mutant_montants_indexes(self, original, measure, params, year, gdp, inflation, unemployment):
    """Erreur injectée : les montants en Md€ suivent le PIB (indexation interdite
    par R-IDX)."""
    dep, rec, imp = original(self, measure, params, year, gdp, inflation, unemployment)
    return _ajouter_recette((dep, rec, imp), rec * (gdp / PIB_2025 - 1))


def test_g12_mutation_montant_indexe_detecte(monkeypatch):
    """Par MUTATION : un montant indexé sur le PIB fait échouer G12."""
    _verifier_r_idx_montant('operations_financieres', {'rachats_actions': 1.0}, 1.0, None, False)
    _muter(monkeypatch, '_apply_operations_financieres', _mutant_montants_indexes)
    with pytest.raises(AssertionError, match='DOUBLE_COMPTE'):
        _verifier_r_idx_montant('operations_financieres', {'rachats_actions': 1.0}, 1.0, None, False)


@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
@pytest.mark.parametrize('levier', W4)
def test_g8_simulation_effet_emis_une_fois_et_rien_avant_le_debut(levier, annee_debut):
    """G8 en simulation complète : rien avant ``annee_debut`` ; Gini et
    compétitivité émis la PREMIÈRE année d'application seulement, à la valeur
    du contrat (constante signée × recette de référence)."""
    _, _, rapport, _ = simuler({levier: BLOCS[levier]}, annee_debut=annee_debut)
    _sans_echec(rapport, levier)
    debut = _debut(annee_debut)
    imp = _impacts_du_levier(rapport, levier)
    assert all(an >= debut for an in imp) and debut in imp, sorted(imp)
    _, gini, compet, _ = attendu(levier, BLOCS[levier], gdp=PIB_2025)
    assert compet != 0.0
    assert imp[debut].get('gini', 0.0) == pytest.approx(gini, rel=1e-12, abs=1e-15)
    assert imp[debut]['competitivite'] == pytest.approx(compet, rel=1e-12)
    for an in range(debut + 1, FIN_SIMULATION + 1):
        assert imp[an].get('gini', 0.0) == 0.0 and imp[an].get('competitivite', 0.0) == 0.0, an


@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
@pytest.mark.parametrize('levier', W4)
def test_solde_signe_et_ordre_de_grandeur(levier, annee_debut):
    """Signe et ordre de grandeur du solde : l'année d'entrée, Δ recettes
    totales = Δ solde primaire = recette du levier (à 1e-9 ; l'effet de demande
    n'arrive qu'en t+1) ; en fin de mandat, le solde public est meilleur que
    sans le levier (hausse de recette)."""
    debut = _debut(annee_debut)
    a_df, a_det, _, _ = simuler({}, annee_debut=annee_debut)
    b_df, b_det, rapport, _ = simuler({levier: BLOCS[levier]}, annee_debut=annee_debut)
    _sans_echec(rapport, levier)
    rec = _impacts_du_levier(rapport, levier)[debut]['recettes']
    assert rec > 0.1, ('NON_VACUITE', rec)
    a, b = a_df.set_index('Année'), b_df.set_index('Année')
    ad, bd = a_det.set_index('Année'), b_det.set_index('Année')
    assert bd.at[debut, 'Recettes_Totales'] - ad.at[debut, 'Recettes_Totales'] == pytest.approx(rec, abs=1e-9)
    primaire = (b.at[debut, 'Déficit'] + bd.at[debut, 'Intérêts_Dette']) \
        - (a.at[debut, 'Déficit'] + ad.at[debut, 'Intérêts_Dette'])
    assert primaire == pytest.approx(rec, abs=1e-9)
    assert b.at[FIN_MANDAT, 'Déficit/PIB %'] > a.at[FIN_MANDAT, 'Déficit/PIB %']


@pytest.mark.parametrize('levier', W4)
def test_g10_le_levier_entre_dans_le_total_mesure(levier, monkeypatch):
    """G10' (appartenance) : chaque année, la variation de recettes que rend
    ``apply_measures`` (le total mesuré contre le seuil de 10 % du PIB) est la
    somme des recettes des leviers, celle du levier W4 comprise."""
    journal = []
    original = BudgetSimulatorV45.apply_measures

    def espion(self, year, spending, revenues, gdp, inflation, unemployment):
        dep, rec, impacts = original(self, year, spending, revenues, gdp, inflation, unemployment)
        journal.append((year, rec - revenues, copy.deepcopy(impacts)))
        return dep, rec, impacts

    monkeypatch.setattr(BudgetSimulatorV45, 'apply_measures', espion)
    _, _, rapport, _ = simuler({levier: BLOCS[levier], 'defense': {'budget': 55}})
    _sans_echec(rapport, levier)
    assert journal
    for year, delta, impacts in journal:
        assert impacts[levier]['recettes'] > 0.1, ('NON_VACUITE', year)
        total = sum(i.get('recettes', 0.0) for i in impacts.values())
        assert delta == pytest.approx(total, abs=1e-9), year


# --- W4-12 (D3-macro) et W4-16 (année source) --------------------------------

DEFENSE_DEFAUT = REGISTRE['defense']['parametres']['budget']['valeur_defaut']


def _verifier_d3_macro(levier, annee_debut):
    """Deux scénarios ne différant que par un levier étranger (défense + 20 Md€
    sur son défaut) : ΔR_t / PIB_t du levier identique à 1e-12."""
    bloc = BLOCS[levier]
    _, _, r1, s1 = simuler({levier: bloc}, annee_debut=annee_debut)
    _, _, r2, s2 = simuler({levier: bloc, 'defense': {'budget': DEFENSE_DEFAUT + 20}}, annee_debut=annee_debut)
    _sans_echec(r1, levier)
    i1, i2 = _impacts_du_levier(r1, levier), _impacts_du_levier(r2, levier)
    debut = _debut(annee_debut)
    assert sorted(i1) == list(range(debut, FIN_SIMULATION + 1)), ('NON_VACUITE', sorted(i1))
    ecarts = [abs(s1._pib_nominal_par_annee[an] - s2._pib_nominal_par_annee[an]) for an in i1]
    assert max(ecarts) > 1.0, ('NON_VACUITE', 'le levier étranger ne change pas le PIB')
    for an in i1:
        a = i1[an]['recettes'] / s1._pib_nominal_par_annee[an]
        b = i2[an]['recettes'] / s2._pib_nominal_par_annee[an]
        assert a == pytest.approx(b, rel=1e-12), ('DOUBLE_COMPTE', levier, an, a, b)


@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
@pytest.mark.parametrize('levier', W4)
def test_w4_12_d3_macro_le_comportement_ne_transporte_aucun_effet_macro(levier, annee_debut):
    """W4-12 (D3-macro) : pour chaque impôt à taux, la part du PIB de la
    recette ne dépend pas de l'état macro (un levier étranger qui change PIB,
    chômage et inflation ne la change pas)."""
    _verifier_d3_macro(levier, annee_debut)


def _mutant_recette_cyclique(self, original, measure, params, year, gdp, inflation, unemployment):
    """Effet macro injecté dans le comportement : la recette dépend du chômage."""
    dep, rec, imp = original(self, measure, params, year, gdp, inflation, unemployment)
    return _ajouter_recette((dep, rec, imp), -rec * unemployment)


def test_w4_12_mutation_effet_macro_dans_le_comportement(monkeypatch):
    """Par MUTATION : un comportement qui lirait le chômage (effet macro déjà
    calculé par le moteur, compté une seconde fois) fait échouer W4-12."""
    _verifier_d3_macro('impot_plancher_patrimoine', None)
    _muter(monkeypatch, '_apply_impot_plancher_patrimoine', _mutant_recette_cyclique)
    with pytest.raises(AssertionError, match='DOUBLE_COMPTE'):
        _verifier_d3_macro('impot_plancher_patrimoine', None)


@pytest.mark.parametrize('levier', W4)
def test_w4_16_annee_source_aucune_dependance_a_annee_debut(levier):
    """W4-16 : un même taux appliqué dès 2028 ou dès 2030 donne la même recette
    en 2032 à 1e-12 : au handler (même année, même PIB, horloges différentes)
    et en simulation complète (même part du PIB)."""
    sims = []
    for origine in (2028, 2030):
        sim = _sim()
        sim._origines_courantes[levier] = origine
        sims.append(_appel(sim, levier, BLOCS[levier], year=FIN_MANDAT, gdp=PIB_2025 * 1.18)[1])
    assert sims[0] != 0.0, ('NON_VACUITE', levier)
    assert sims[0] == pytest.approx(sims[1], rel=1e-12)
    parts = []
    for annee_debut in (2028, 2030):
        _, _, rapport, sim = simuler({levier: BLOCS[levier]}, annee_debut=annee_debut)
        _sans_echec(rapport, levier)
        parts.append(_impacts_du_levier(rapport, levier)[FIN_MANDAT]['recettes']
                     / sim._pib_nominal_par_annee[FIN_MANDAT])
    assert parts[0] == pytest.approx(parts[1], rel=1e-12), parts


# ===========================================================================
# 8. Anti-double-compte : règles Z4', M, K, Z-ter (§ 4.1), avec mutation
# ===========================================================================

def _verifier_independance(w4, bloc_w4, autres, *, rejouer_w4=False, toutes_annees=False):
    """Indépendance de leviers aux assiettes disjointes :
    (1) mode historique, rejeu : chaque appel des handlers ``autres``
        enregistré dans la simulation AVEC le levier W4, rejoué sans lui, rend
        la même sortie au bit (aucune lecture croisée ni état partagé) ; et
        réciproquement pour le levier W4 si ``rejouer_w4`` ;
    (2) deux modes : la première année d'application (état macro encore
        identique), impacts des leviers ``autres`` identiques au bit avec ou
        sans le levier W4 (toutes les années si leur handler ne lit pas le PIB)."""
    mesures = {**autres, w4: bloc_w4}
    journaux = {m: [] for m in list(autres) + ([w4] if rejouer_w4 else [])}
    with pytest.MonkeyPatch.context() as mp:
        for m, j in journaux.items():
            _espionner(mp, f'_apply_{m}', j)
        _, _, rapport, _ = simuler(mesures)
    _sans_echec(rapport, w4)
    assert rapport['valid'] is True, ('NON_VACUITE', rapport['warnings'])
    assert any(abs(i.get('recettes', 0.0)) > 0.1 for i in _impacts_du_levier(rapport, w4).values()), \
        ('NON_VACUITE', w4)
    for m in autres:
        assert journaux[m], ('NON_VACUITE', m)
        _rejouer_et_comparer(f'_apply_{m}', journaux[m], _sans(mesures, w4), f'{m} sans {w4}')
    if rejouer_w4:
        assert journaux[w4], ('NON_VACUITE', w4)
        _rejouer_et_comparer(f'_apply_{w4}', journaux[w4], {w4: bloc_w4}, f'{w4} sans {sorted(autres)}')
    for annee_debut in (None, 2028):
        debut = _debut(annee_debut)
        _, _, sans_w4, _ = simuler(autres, annee_debut=annee_debut)
        _, _, avec_w4, _ = simuler(mesures, annee_debut=annee_debut)
        annees = range(debut, FIN_SIMULATION + 1) if toutes_annees else [debut]
        for m in autres:
            i_sans, i_avec = _impacts_du_levier(sans_w4, m), _impacts_du_levier(avec_w4, m)
            for an in annees:
                assert _canon(i_avec.get(an)) == _canon(i_sans.get(an)), ('DOUBLE_COMPTE', m, an, annee_debut)


ISF_MOITIE = {'isf_climatique': {'intensite': 0.5}}


def test_w4_5_z4_l_isf_inchange_avec_ou_sans_plancher():
    """W4-5 (Z4') : sorties de ``_apply_isf_climatique`` identiques au bit avec
    ou sans plancher (rejeu, et chaque année des deux modes : la recette de
    l'ISF ne lit pas le PIB) ; le plancher ne lit pas la constante d'évasion
    de l'ISF (paramètre propre, ``evitement``)."""
    _verifier_independance('impot_plancher_patrimoine', {'taux': 0.02}, ISF_MOITIE, toutes_annees=True)
    code = '\n'.join(l.split('#')[0] for l in
                     inspect.getsource(BudgetSimulatorV45._apply_impot_plancher_patrimoine).splitlines())
    assert 'taux_evasion' not in code and not re.search(r'\b0\.15\b', code)


def _mutant_isf_couple_au_plancher(self, original, measure, params, year, gdp, inflation, unemployment):
    sortie = original(self, measure, params, year, gdp, inflation, unemployment)
    if self.mesures.get('impot_plancher_patrimoine'):
        return _ajouter_recette(sortie, 1.0)
    return sortie


def test_w4_5_z4_mutation_isf_couple_au_plancher(monkeypatch):
    """Par MUTATION : une recette du plancher reversée dans l'ISF (même
    patrimoine compté deux fois) fait échouer Z4'."""
    _verifier_independance('impot_plancher_patrimoine', {'taux': 0.02}, ISF_MOITIE, toutes_annees=True)
    _muter(monkeypatch, '_apply_isf_climatique', _mutant_isf_couple_au_plancher)
    with pytest.raises(AssertionError, match='DOUBLE_COMPTE'):
        _verifier_independance('impot_plancher_patrimoine', {'taux': 0.02}, ISF_MOITIE, toutes_annees=True)


IS_ET_SURTAXE = {'impot_societes': {'taux': 0.30, 'niches': 0}, 'is_exceptionnel_tge': {'montant': 12}}
MULTI = {'benefices_recuperes': 5.0, 'taux_tsn': 0.05}


def test_w4_8_m2_is_et_surtaxe_inchanges_avec_ou_sans_multinationales():
    """W4-8 (M2) : impacts de ``impot_societes`` et de ``is_exceptionnel_tge``
    identiques au bit avec ou sans ``multinationales`` (assiettes disjointes ;
    seule la lecture du taux d'IS va dans l'autre sens, par M1)."""
    _verifier_independance('multinationales', MULTI, IS_ET_SURTAXE)


def _mutant_is_recompte_les_benefices(self, original, measure, params, year, gdp, inflation, unemployment):
    sortie = original(self, measure, params, year, gdp, inflation, unemployment)
    multi = self.mesures.get('multinationales') or {}
    return _ajouter_recette(sortie, multi.get('benefices_recuperes', 0.0))


def test_w4_8_m2_mutation_benefices_recomptes_dans_l_is(monkeypatch):
    """Par MUTATION : des bénéfices récupérés recomptés dans l'IS font échouer
    M2."""
    _verifier_independance('multinationales', MULTI, IS_ET_SURTAXE)
    _muter(monkeypatch, '_apply_impot_societes', _mutant_is_recompte_les_benefices)
    with pytest.raises(AssertionError, match='DOUBLE_COMPTE'):
        _verifier_independance('multinationales', MULTI, IS_ET_SURTAXE)


def _mutant_multinationales_sans_taux_is(self, original, measure, params, year, gdp, inflation, unemployment):
    sauve = self.mesures
    self.mesures = _sans(sauve, 'impot_societes')
    try:
        return original(self, measure, params, year, gdp, inflation, unemployment)
    finally:
        self.mesures = sauve


def _verifier_m1_simulation():
    for annee_debut in (None, 2028):
        _, _, rapport, _ = simuler({'impot_societes': {'taux': 0.33, 'niches': 0},
                                    'multinationales': {'benefices_recuperes': 5.0}}, annee_debut=annee_debut)
        _sans_echec(rapport, 'multinationales')
        imp = _impacts_du_levier(rapport, 'multinationales')
        assert imp, 'NON_VACUITE'
        for an, i in imp.items():
            assert i['recettes'] == pytest.approx(5.0 * 0.33 / TAUX_IS_REF, rel=1e-14), ('DOUBLE_COMPTE', an)


def test_w4_7_m1_simulation_et_taux_is_ecrete():
    """W4-7 (M1) en simulation complète, deux modes ; et la lecture croisée
    voit le taux d'IS ÉCRÊTÉ par la porte d'entrée (le même que celui
    qu'applique le levier impot_societes)."""
    _verifier_m1_simulation()
    t_max = REGISTRE['impot_societes']['parametres']['taux']['max']
    _, _, rapport, _ = simuler({'impot_societes': {'taux': t_max + 0.1, 'niches': 0},
                                'multinationales': {'benefices_recuperes': 5.0}})
    _sans_echec(rapport, 'multinationales')
    for an, i in _impacts_du_levier(rapport, 'multinationales').items():
        assert i['recettes'] == pytest.approx(5.0 * t_max / TAUX_IS_REF, rel=1e-14), an


def test_w4_7_m1_mutation_taux_is_ignore(monkeypatch):
    """Par MUTATION : des bénéfices récupérés qui ignoreraient le taux d'IS du
    scénario font échouer M1."""
    _verifier_m1_simulation()
    _muter(monkeypatch, '_apply_multinationales', _mutant_multinationales_sans_taux_is)
    with pytest.raises(AssertionError, match='DOUBLE_COMPTE'):
        _verifier_m1_simulation()


CSG_ET_IR = {'csg': {'taux': 0.105, 'progressive': 0}, 'impot_revenu': {'taux_superieur': 0.50, 'decote': 1.0}}
CAPITAL = {'taux_ir_forfaitaire': 0.20, 'prelevements_sociaux_capital': 0.20}


def test_w4_9_k1_csg_et_ir_inchanges_et_reciproquement():
    """W4-9 (K1) : impacts de ``csg`` et ``impot_revenu`` identiques avec ou
    sans ``fiscalite_capital``, ET réciproquement (rejeu des appels du levier
    capital sans la CSG ni l'IR) : part IR disjointe de la tranche supérieure,
    part sociale additive à une variation générale de CSG."""
    _verifier_independance('fiscalite_capital', CAPITAL, CSG_ET_IR, rejouer_w4=True)


def _mutant_csg_recompte_le_capital(self, original, measure, params, year, gdp, inflation, unemployment):
    sortie = original(self, measure, params, year, gdp, inflation, unemployment)
    capital = self.mesures.get('fiscalite_capital') or {}
    ecart = capital.get('prelevements_sociaux_capital', T_PS0) - T_PS0
    return _ajouter_recette(sortie, ecart * C.A_CAPITAL_PS)


def test_w4_9_k1_mutation_part_sociale_recomptee_dans_la_csg(monkeypatch):
    """Par MUTATION : la hausse des prélèvements sociaux du capital recomptée
    dans la CSG fait échouer K1."""
    _verifier_independance('fiscalite_capital', CAPITAL, CSG_ET_IR, rejouer_w4=True)
    _muter(monkeypatch, '_apply_csg', _mutant_csg_recompte_le_capital)
    with pytest.raises(AssertionError, match='DOUBLE_COMPTE'):
        _verifier_independance('fiscalite_capital', CAPITAL, CSG_ET_IR, rejouer_w4=True)


# --- W4-17 (Z-ter) -----------------------------------------------------------

AVIS_Z_TER = re.compile("Impôts déductibles de l['’]impôt plancher relevés en même temps")
PLANCHER = {'impot_plancher_patrimoine': {'taux': 0.02}}
Z_TER = [  # (mesures, avis attendu)
    ({**PLANCHER, 'fiscalite_capital': {'taux_ir_forfaitaire': 0.20}}, True),
    ({**PLANCHER, 'fiscalite_capital': {'prelevements_sociaux_capital': 0.20}}, True),
    ({**PLANCHER, 'csg': {'taux': 0.105, 'progressive': 0}}, True),
    ({**PLANCHER, 'impot_revenu': {'taux_superieur': 0.50, 'decote': 1.0}}, True),
    (PLANCHER, False),
    ({**PLANCHER, 'csg': {'taux': 0.09, 'progressive': 0}}, False),
    ({**PLANCHER, 'fiscalite_capital': {'taux_ir_forfaitaire': 0.10}}, False),
    ({**PLANCHER, 'impot_revenu': {'taux_superieur': DROIT['impot_revenu']['taux_superieur'],
                                   'decote': 1.0}}, False),
    ({'impot_plancher_patrimoine': {'taux': 0.0, 'evitement': 0.5},
      'csg': {'taux': 0.105, 'progressive': 0}}, False),
    ({'csg': {'taux': 0.105, 'progressive': 0}}, False),
    # Revue adverse de la release E (R-1 C5) : la proposition de loi déduit
    # aussi l'IFI (curseur de la fiscalité du patrimoine) et l'impôt sur le
    # revenu (mesure ciblée en Md€) ; une hausse déclenche l'avis, une baisse non.
    ({**PLANCHER, 'fiscalite_patrimoine': {'intensite': 0.3}}, True),
    ({**PLANCHER, 'fiscalite_patrimoine': {'intensite': -0.3}}, False),
    ({**PLANCHER, 'impot_revenu_cible': {'montant': 5.0}}, True),
    ({**PLANCHER, 'impot_revenu_cible': {'montant': -5.0}}, False),
]


def _verifier_z_ter_sans_calcul(mesures, annee_debut):
    """L'avis n'entraîne aucun calcul : la part du PIB de la recette du plancher
    est la même qu'avec le plancher seul (calage du Trésor à droit constant)."""
    _, _, r_seul, s_seul = simuler(PLANCHER, annee_debut=annee_debut)
    _, _, r, s = simuler(mesures, annee_debut=annee_debut)
    _sans_echec(r, 'impot_plancher_patrimoine')
    i_seul = _impacts_du_levier(r_seul, 'impot_plancher_patrimoine')
    i = _impacts_du_levier(r, 'impot_plancher_patrimoine')
    assert i and sorted(i) == sorted(i_seul), ('NON_VACUITE', sorted(i))
    for an in i:
        a = i[an]['recettes'] / s._pib_nominal_par_annee[an]
        b = i_seul[an]['recettes'] / s_seul._pib_nominal_par_annee[an]
        assert a == pytest.approx(b, rel=1e-12), ('DOUBLE_COMPTE', an, a, b)


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
@pytest.mark.parametrize('mesures, avis', Z_TER,
                         ids=[f'{i}-{"avis" if a else "sans"}' for i, (_, a) in enumerate(Z_TER)])
def test_w4_17_z_ter_avis_si_et_seulement_si_impot_deductible_releve(mesures, avis, annee_debut, strict):
    """W4-17 (Z-ter) : avis (« Avis — Impôts déductibles de l'impôt plancher
    relevés en même temps… ») présent si et seulement si plancher > 0 et
    hausse d'un impôt déductible (revenus du capital au-dessus du neutre, CSG,
    tranche supérieure de l'IR, fiscalité du patrimoine ou IR ciblé au-dessus
    du droit ou, à défaut, du neutre) ; une fois par
    simulation, une ligne, texte borné ; ``valid`` inchangé ; aucun calcul.

    Le test lit le RAPPORT, quel que soit le lieu d'émission de l'avis. Le
    contrat ne le fixe pas (§ 4.1 « implémentation commune » de W1 contre
    § 7.1, qui ne donne à W4 que ``recettes_taux.py``) ; un handler qui
    écrirait ``self._avis`` est refusé par la garde statique
    ``test_cadre_v070_revue_passe1.py::test_m9_ecritures_des_handlers_statique``
    tant que ``_avis`` n'est pas dans ``_PARTAGES_SANS_EFFET`` (précédent :
    ``_rabots_vivier``) — décision de la session."""
    _, _, rapport, _ = simuler(mesures, annee_debut=annee_debut, strict=strict)
    if 'impot_plancher_patrimoine' in mesures:
        _sans_echec(rapport, 'impot_plancher_patrimoine')
    assert rapport['valid'] is True, rapport['warnings']
    lignes = [w for w in rapport['warnings'] if AVIS_Z_TER.search(w)]
    assert len(lignes) == (1 if avis else 0), lignes
    for ligne in lignes:
        assert '\n' not in ligne and len(ligne) <= 400 and ligne.startswith('Avis — '), ligne
    if avis and not strict:
        _verifier_z_ter_sans_calcul(mesures, annee_debut)


def _mutant_plancher_corrige_pour_la_csg(self, original, measure, params, year, gdp, inflation, unemployment):
    dep, rec, imp = original(self, measure, params, year, gdp, inflation, unemployment)
    csg = (self.mesures.get('csg') or {}).get('taux', DROIT['csg']['taux'])
    if csg > DROIT['csg']['taux']:
        return _ajouter_recette((dep, rec, imp), -0.1 * rec)
    return dep, rec, imp


def test_w4_17_z_ter_mutation_correction_inventee(monkeypatch):
    """Par MUTATION : une « correction » de la recette du plancher pour la
    hausse de CSG (répartition non publiée, donc inventée) fait échouer
    l'exigence « aucun calcul »."""
    mesures = {**PLANCHER, 'csg': {'taux': 0.105, 'progressive': 0}}
    _verifier_z_ter_sans_calcul(mesures, None)
    _muter(monkeypatch, '_apply_impot_plancher_patrimoine', _mutant_plancher_corrige_pour_la_csg)
    with pytest.raises(AssertionError, match='DOUBLE_COMPTE'):
        _verifier_z_ter_sans_calcul(mesures, None)


# ===========================================================================
# 9. Profils temporels (W1) appliqués aux paramètres en Md€ du chantier
# ===========================================================================
# Les profils (§ 2.1) sont livrés par W1 ; tests ordinaires depuis l'intégration.

PROFILABLES = [
    ('operations_financieres', 'rachats_actions', 2.0, C.COMPET_IS_EXCEPTIONNEL_PAR_MD),
    ('multinationales', 'benefices_recuperes', 5.0, C.COMPET_IS_PAR_MD),
    ('fiscalite_capital', 'rendement_md', 3.0, C.COMPET_PATRIMOINE_PAR_MD),
]


def _simuler_profil(levier, cle, montant, profil):
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': ''}):
        sim = BudgetSimulatorV45(periods=10, mesures={levier: {cle: montant}}, annee_debut=DEBUT_CADRE,
                                 profils={f'{levier}.{cle}': profil})
        return sim.simulate()[2]


@pytest.mark.parametrize('levier, cle, montant, coef', PROFILABLES, ids=[p[0] for p in PROFILABLES])
def test_g8_profil_rampe_increments_egaux_au_palier(levier, cle, montant, coef):
    """G8 sous profil « rampe » (début 2028) : montant × k/5 de 2028 à 2031,
    montant exact dès 2032 ; Σ incréments de compétitivité = effet du palier."""
    rapport = _simuler_profil(levier, cle, montant, {'forme': 'rampe'})
    imp = _impacts_du_levier(rapport, levier)
    n = FIN_MANDAT - DEBUT_CADRE + 1
    for an in range(DEBUT_CADRE, FIN_MANDAT):
        assert imp[an]['recettes'] == pytest.approx(montant * (an - DEBUT_CADRE + 1) / n, rel=1e-12)
    for an in range(FIN_MANDAT, FIN_SIMULATION + 1):
        assert imp[an]['recettes'] == pytest.approx(montant, rel=1e-12)
    total = sum(i.get('competitivite', 0.0) for i in imp.values())
    assert total == pytest.approx(coef * montant, rel=1e-12)


@pytest.mark.parametrize('levier, cle, montant, coef', PROFILABLES, ids=[p[0] for p in PROFILABLES])
def test_g8_retour_profil_une_seule_annee(levier, cle, montant, coef):
    """G8-retour : profil « une seule année » (2030) → recette l'année choisie
    seulement ; Σ des incréments de Gini et de compétitivité sur l'horizon = 0
    à 1e-12 ; recette nulle dès l'année suivante."""
    rapport = _simuler_profil(levier, cle, montant, {'forme': 'annee', 'annee': 2030})
    imp = _impacts_du_levier(rapport, levier)
    assert imp[2030]['recettes'] == pytest.approx(montant, rel=1e-12)
    assert imp[2030]['competitivite'] == pytest.approx(coef * montant, rel=1e-12)
    for an, i in imp.items():
        if an != 2030:
            assert i.get('recettes', 0.0) == 0.0, an
    for cle_effet in ('gini', 'competitivite'):
        assert sum(i.get(cle_effet, 0.0) for i in imp.values()) == pytest.approx(0.0, abs=1e-12)
