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
from run_scenarios_full import SCENARIOS, pour_le_mode  # noqa: E402,F401

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


@contextmanager
def droit_sans_valeurs_datees():
    """Remplace le temps du bloc le droit en vigueur livré par le MÊME droit
    sans ses valeurs datées : le droit « constant » de v0.7.0 à v0.8.0, où
    chaque mesure votée se reconduit d'année en année.

    Release de paramètres P (v0.8.1) : le droit livré porte des valeurs datées
    (une mesure votée pour une durée limitée s'arrête, contrat de la release E
    § 5.3). Les tests d'un MÉCANISME qui suppose un droit constant (tables
    d'atterrissage vides, élasticité unitaire des recettes, lecteurs latéraux,
    rampe, éviction nulle de la référence…) s'exécutent dans ce bloc ; la règle
    des valeurs datées a ses propres tests (``test_release_e_w1.py``, W1-7) et
    les sorties publiées passent par le droit livré. Même mécanisme que
    ``atterrissage`` : fichier temporaire, validé par le moteur."""
    import json
    import tempfile
    contenu = json.loads(cadre.DROIT_EN_VIGUEUR_PATH.read_text(encoding='utf-8'))
    assert contenu.pop('valeurs_datees', None), "droit livré sans valeur datée : bloc sans objet"
    with tempfile.TemporaryDirectory() as d, pytest.MonkeyPatch.context() as mp:
        chemin = Path(d) / 'droit_en_vigueur.json'
        chemin.write_text(json.dumps(contenu, ensure_ascii=False), encoding='utf-8')
        mp.setattr(cadre, 'DROIT_EN_VIGUEUR_PATH', chemin)
        cadre.vider_caches()
        try:
            yield
        finally:
            cadre.vider_caches()


def droit_reajuste_courant(debut=2028) -> dict:
    """Droit en vigueur réajusté au début ``debut``, lu dans le droit ACTIF
    (le fichier livré, ou celui d'un bloc ``droit_sans_valeurs_datees``)."""
    return copy.deepcopy(cadre.CadreTemporel.preparer({}, debut).etat.mesures_droit)


def _bloc_neutre(levier, bloc) -> bool:
    """Bloc d'un levier de la release E dont chaque valeur est ``null`` ou égale
    au neutre du paramètre (un taux inscrit au droit vaut son neutre). Une clé
    de mode exclusif (``rendement_*``, neutre = clé absente) n'est jamais
    neutre."""
    import budget_simulator.constants as C
    neutres = C.NEUTRES_RELEASE_E[levier]
    return isinstance(bloc, dict) and all(
        v is None or (p in neutres and v == neutres[p]) for p, v in bloc.items())


def bases_g1(bases: dict, levier: str, annee_debut=None) -> dict:
    """Bases du test G1 (neutralité au bit) d'un levier de la release E : celles
    qui ne l'encodent PAS. Release de paramètres P : des scénarios publiés
    encodent désormais ces leviers ; y poser le bloc neutre retirerait leur
    mesure (remplacement en bloc) : ce n'est plus « ajouter un neutre ». Une
    base où le levier est absent, ``null`` ou au neutre reste une base de G1 ;
    le statu quo l'est toujours. Chaque base est prise telle que le mode
    ``annee_debut`` l'accepte (``pour_le_mode`` : en mode historique, sans la
    recette d'une seule année)."""
    retenues = {nom: pour_le_mode(base, annee_debut) for nom, base in bases.items()
                if base.get(levier) is None or _bloc_neutre(levier, base[levier])}
    assert 'statu_quo' in retenues, "G1 sans le statu quo"
    return retenues


def rapport_g1(rapport: dict, levier: str) -> dict:
    """Rapport comparé par G1, dont est retirée la SEULE différence attendue d'un
    bloc neutre complet sur un levier à taux INSCRIT au droit en vigueur
    (release de paramètres P, contrat de la release E § 0.9) : le droit n'inscrit
    que les taux votés ; les paramètres de comportement du bloc (élasticité,
    érosion, à leur défaut) n'y sont pas, donc, en mode cadre, le levier entre
    dans ``cadre.leviers_modifies`` et ``cadre.mesures_effectives`` (règle
    v0.7.2 « présent = imposé ») sans qu'aucune sortie ne bouge. Toute autre
    différence reste comparée. Copie ; rapport rendu tel quel hors mode cadre
    et pour un levier absent du droit."""
    import budget_simulator.constants as C
    droit = cadre.charger_droit_en_vigueur().mesures
    if levier not in droit or not (rapport.get('cadre') or {}).get('mesures_effectives'):
        return rapport
    out = copy.deepcopy(rapport)
    c = out['cadre']
    effectif = c['mesures_effectives'].get(levier)
    if isinstance(effectif, dict):
        neutres = C.NEUTRES_RELEASE_E[levier]
        c['mesures_effectives'][levier] = {
            p: v for p, v in effectif.items()
            if p in droit[levier] or not (p in neutres and v == neutres[p])}
        if c['mesures_effectives'][levier] == droit[levier]:
            c['leviers_modifies'] = [l for l in c['leviers_modifies'] if l != levier]
    return out


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
