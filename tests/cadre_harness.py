"""Harnais partagé des tests du cadre temporel v0.7.0 (lots A à E).

- ``simuler`` : simulation PLEINE PRÉCISION (``round`` de l'orchestrateur
  neutralisé), mode tolérant sauf demande contraire ;
- ``CAS`` : les scénarios publiés (si ``scenarios.json`` du dépôt parent est
  disponible) + le programme mixte, toujours présent, pour que les propriétés
  tournent aussi dans la CI du dépôt public seul (aucun test n'y suppose
  ``plf_2026`` : la référence « droit en vigueur » est ``DROIT``) ;
- ``egalite_bit_a_bit`` : comparaison exacte de deux sorties (résultats,
  détails, impacts par levier), avec un message qui nomme la première cellule
  qui diffère.

Aucun test ici : module importé par les fichiers ``test_cadre_v070_*.py``.
"""
import copy
import math
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

import budget_simulator.engine.cadre as cadre
import budget_simulator.engine.orchestrator as orch
from budget_simulator.simulator import BudgetSimulatorV45

SNAPSHOTS_DIR = Path(__file__).parent / 'snapshots'
sys.path.insert(0, str(SNAPSHOTS_DIR))
from run_scenarios_full import SCENARIOS  # noqa: E402

PA = "Pouvoir d'Achat"
COLONNES_8 = ['Dette/PIB %', 'Déficit/PIB %', 'Chômage %', 'Croissance %',
              'Inflation %', PA, 'Competitivite', 'Gini']

# Programme mixte : un levier par famille d'horloge et d'effet ponctuel, plus
# des leviers absents du droit en vigueur (rabot) et des lecteurs latéraux
# (âge de départ → offre et chômage seniors ; éducation → effet d'offre ;
# point d'indice → SMIC ; ASU → fraude sociale et prestations).
PROGRAMME_MIXTE = {
    'tva_rate': {'taux': 0.22},
    'retraites': {'indexation': 0.8, 'age_depart': 65.0, 'duree_cotisation': 43.0},
    'impot_revenu': {'taux_superieur': 0.50, 'decote': 1.0},
    'smic': {'montant_brut': 1900},
    'asu': {'asu_activation': 1, 'asu_plafonnement': 0.6},
    'csg': {'taux': 0.1, 'progressive': 1},
    'taxe_superprofits': {'intensite': 1.0},
    'isf_climatique': {'intensite': 0.5},
    'fonction_publique': {'effectifs': -100000, 'point_indice': 2.0},
    'fonction_publique_reforme': {'fusion_agences': 30, 'digitalisation': 30},
    'niches_fiscales_tge': {'montant': 40},
    'cotisations_patronales': {'taux': 0.25},
    'education': {'budget': 75, 'enseignants': 20000, 'salaires': 5},
    'transition_ecologique': {'investissement': 20, 'renovation': 10, 'taxe_carbone': 80},
    'recherche_publique': {'budget': 15},
    'defense': {'budget': 60},
    'sante': {'effort_hopital': 30, 'effort_ambu': 20, 'effort_prev_org': 10,
              'franchise_participation_taux': 150, 'prevention_budget': 9.0},
    'chomage_alloc': {'taux_remplacement': 0.55, 'duree': 15, 'degressivite': True},
    'fraude_fiscale': {'effort': 0.6},
    'fraude_sociale': {'effort': 0.5},
    'optimisation_dette': {'intensite': 0.5},
    'abattement_retraites': {'reforme_active': 1},
    'prestations_indexation': {'taux_indexation': 0.9},
    'tva_energie': {'taux': 0.1},
    'exonerations_salaires': {'intensite': 0.5},
    'rabot_uniforme': {'taux_reduction': 0.03, 'exclure_dette': 1,
                       'exclure_defense': 1, 'exclure_ue': 1},
}

CAS = {'programme_mixte': PROGRAMME_MIXTE, **SCENARIOS}
NOMS = sorted(CAS)
NOMS_PROGRAMMES = [n for n in NOMS if n != 'plf_2026']

# Droit en vigueur livré, tel que VOTÉ (réajustements de l'atterrissage non
# compris) : référence de comparaison des tests du cadre.
DROIT = cadre.charger_droit_en_vigueur().mesures
# Droit en vigueur RÉAJUSTÉ sur l'atterrissage livré, au premier budget du mandat
# (2028) : le point de départ commun du mode cadre, lu dans le moteur. v0.7.2
# (retrait du pont, « présent = imposé ») : un programme « égal au droit en
# vigueur » est CELUI-CI ; poser le voté brut (DROIT) impose 57 / 100 / 7,3.
def _droit_reajuste_livre() -> dict:
    etat = cadre.CadreTemporel.preparer({}, 2028).etat
    assert etat is not None, "mode cadre attendu pour annee_debut = 2028"
    return etat.mesures_droit


DROIT_REAJUSTE = _droit_reajuste_livre()


def programme_sur_droit(**leviers):
    """Le droit en vigueur réajusté, dont les leviers cités sont remplacés (copies)."""
    m = copy.deepcopy(DROIT_REAJUSTE)
    m.update(copy.deepcopy(leviers))
    return m


def impacts_par_annee(rapport):
    """{année: impacts par levier} du rapport d'une simulation."""
    return {y['Année']: y for y in rapport['measure_impacts_by_year']}


@contextmanager
def pleine_precision(monkeypatch=None):
    """``round`` de l'orchestrateur neutralisé le temps du bloc."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
        yield mp


@contextmanager
def atterrissage(cibles_par_annee, reajustements=None):
    """Remplace le temps du bloc le fichier d'atterrissage par des données de
    TEST, qui passent par la vraie validation du moteur. ``cibles_par_annee`` :
    {année: {grandeur: valeur}} ; ``{}`` = aucune année injectée (« tables
    vides ») ; une grandeur non citée est écrite ``null`` (le fichier porte les
    six chaque année). ``reajustements`` : {année: {levier: {paramètre:
    valeur}}}, chacun avec une source de test (aucun réajustement sans source)."""
    import json
    import tempfile
    annees = {}
    for an in sorted(set(cibles_par_annee) | set(reajustements or {})):
        bloc = {g: None for g in cadre.GRANDEURS_ATTERRISSAGE}
        bloc.update({g: {'valeur': v, 'source': 'donnée de test', 'date': '2026-11-07'}
                     for g, v in (cibles_par_annee.get(an) or {}).items()})
        reaj = (reajustements or {}).get(an, {})
        bloc['reajustements_droit_en_vigueur'] = reaj
        bloc['sources_reajustements'] = {f'{l}.{p}': 'source de test'
                                         for l, params in reaj.items() for p in params}
        annees[str(an)] = bloc
    contenu = {'version': 'test', 'date': '2026-11-07', 'description': 'test', 'annees': annees}
    with tempfile.TemporaryDirectory() as d, pytest.MonkeyPatch.context() as mp:
        chemin = Path(d) / 'atterrissage.json'
        chemin.write_text(json.dumps(contenu), encoding='utf-8')
        mp.setattr(cadre, 'ATTERRISSAGE_PATH', chemin)
        cadre.vider_caches()
        try:
            yield
        finally:
            cadre.vider_caches()


def simuler(mesures, periods=10, strict=False, **kwargs):
    """(df, det, rapport, sim) pleine précision. ``kwargs`` : annee_debut, rampe."""
    with pleine_precision() as mp:
        mp.setenv('BUDGETLAB_STRICT', '1' if strict else '')
        sim = BudgetSimulatorV45(periods=periods, mesures=copy.deepcopy(mesures), **kwargs)
        df, det, rapport = sim.simulate()
    return df, det, rapport, sim


def _egal(a, b):
    """Égalité EXACTE, NaN compris (aucune tolérance)."""
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b


def egalite_bit_a_bit(sortie_a, sortie_b, annees=None, libelle=''):
    """Assertion : mêmes valeurs AU BIT pour toutes les colonnes de résultats et
    de détails communes aux deux sorties, et mêmes impacts par levier, sur les
    années demandées (toutes par défaut)."""
    df_a, det_a, rap_a = sortie_a[:3]
    df_b, det_b, rap_b = sortie_b[:3]
    annees = list(df_a['Année']) if annees is None else list(annees)
    for nom_cadre, cadre_a, cadre_b in (('résultats', df_a, df_b), ('détails', det_a, det_b)):
        a = cadre_a.set_index('Année')
        b = cadre_b.set_index('Année')
        for col in a.columns:
            if col not in b.columns:
                continue
            for an in annees:
                va, vb = a.at[an, col], b.at[an, col]
                assert _egal(va, vb), f"{libelle} {nom_cadre} {col} {an} : {va!r} ≠ {vb!r}"
    imp_a = {y['Année']: y for y in rap_a['measure_impacts_by_year']}
    imp_b = {y['Année']: y for y in rap_b['measure_impacts_by_year']}
    for an in annees:
        assert imp_a.get(an) == imp_b.get(an), (
            f"{libelle} impacts {an} : "
            f"{sorted(set(imp_a.get(an, {})) ^ set(imp_b.get(an, {})))} ou valeurs différentes")
