"""Release E — chantier W1 : contrat et garde-fous (tests écrits AVANT le code).

Contrat : ``docs/plans/contrat-curseurs-release-E-2026-11.md`` du dépôt parent,
§ 2 (profils temporels), § 4.1 (exclusions X1 et X2), § 5.1 (porte des leviers
inconnus, signature de contrat), § 5.3 (valeurs datées du droit en vigueur),
§ 5.4 (plafond de 10 % du PIB) et § 6.2 (tests W1-1 à W1-17).

Ce fichier ne contient AUCUN code de production : il fixe le comportement que
le code du chantier W1 doit atteindre. Sur le commit socle, ses tests sont
rouges parce que la fonction manque (nom absent du moteur, argument
``profils`` inconnu, champ de rapport absent) ou parce que le moteur fait
encore l'ancien choix (levier inconnu ignoré en silence, surtaxe d'un an
reconduite, levier exclu toujours appliqué). Les tests de non-régression
(API qui refuse déjà un levier inconnu, fichier de droit sans valeur datée,
mode historique qui ne lit pas le droit) sont verts dès le socle : ils
gardent ce qui doit le rester.

Points que le contrat laisse muets, TRANCHÉS ici au minimum (à confirmer par
la session) :

1. ``report.corrections`` (contrat § 4.1 et W5-15 : « correction lisible dans
   ``report.corrections`` ») : liste toujours présente, vide sans correction ;
   une entrée par règle déclenchée, de forme ``{"regle": "X1" | "X2" |
   "LEVIER_INCONNU", "leviers_ignores": [noms], "message": texte}``, le texte
   figurant aussi dans ``report.warnings``. Noms nus (sans guillemets de
   ``repr``), au plus ``_DETAILS_MAX``, chacun tronqué à 40 caractères. Les
   autres corrections (domaines, échecs) n'y sont pas exigées.
2. Condition d'arrêt D6 : le banc W1 (10 scénarios, deux modes, deux portes,
   11/11/2026) montre que, sans réduction, le filet de croissance
   [−3,5 % ; +2,5 %] mord DAVANTAGE sur le seul scénario publié au-delà du seuil (croissance avant filet
   2029, cadre 2028 : 2,79 % avec réduction, 2,87 % sans ; 2028 en mode
   historique : 2,84 % → 3,00 %). Interrupteur ``constants.PLAFOND_TOTAL_MODE``
   (bloc W1), valeurs ``PLAFOND_TOTAL_MODES = ('reduction', 'avertissement')``.
   Décision du mainteneur du 12/11/2026 : défaut ``'avertissement'`` (aucune
   réduction, un avis) ; le mode ``'reduction'`` reste disponible et testé.
   L'interrupteur est relu à chaque simulation (les tests le remplacent dans
   chaque module du moteur qui le porte).
   ``cadre.plafond_total.mode`` publie le mode actif : la signature E est
   « champ ``mode`` présent », pas « ``mode == 'avertissement'`` ».
3. Garde G9 côté moteur : ``tests/snapshots/measure_registry.json`` (lu par le
   site) ne liste que les leviers à handler ; il doit exposer TOUS les noms
   admis (formules comprises) sous ``noms_parametres_admis``.
4. Runner des golden masters : expose ``PROFILS`` ({scénario: profils}) à
   côté de ``SCENARIOS``.

Exceptions attendues : ``_param_domain.LevierInconnu`` et
``_param_domain.LeviersIncompatibles`` ; ``cadre.ProfilInvalide`` (toutes
``EntreeInvalide`` et ``ValueError`` : 422 côté API). En mode strict, elles
sont acceptées levées directement OU dans l'``ExceptionGroup`` de la porte
annuelle.

Mutations : chaque garde anti-double-compte a son test « par mutation » qui
montre que la propriété ROUGIT quand l'effet est compté deux fois (table
d'exclusions vidée, valeurs datées ignorées, une seule année lue comme
« chaque année », réduction du plafond rétablie). La table d'exclusions et
l'interrupteur du plafond sont donc relus à chaque simulation.

À l'attention du code W1 (tests existants qui encodent l'état d'avant, à
adapter avec le code, hors de ce fichier) :
``test_release_e_socle.py::test_blocs_balises_dans_l_ordre_et_chantiers_vides``
(bloc W1 vide) ; ``test_cadre_v070_revue_passe1.py::test_m7_plafond_constante_nommee_valeur_inchangee``
(bloc ``plafond_total`` comparé à un dict exact) ; les appels à
``cadre.droit_reajuste`` (``test_cadre_v070_mesures_annee.py``,
``test_parametres_v072.py``) si la fonction est renommée
``droit_de_l_annee`` (contrat § 5.3). Le test W1-12 (bloc au neutre retiré du
programme en mode cadre) est déjà porté par le socle
(``test_release_e_socle.py::test_bloc_neutre_retire_du_programme_en_mode_cadre``).
"""
import copy
import importlib.util
import json
import logging
import math
import os
import re
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import budget_simulator.constants as C
import budget_simulator.engine._param_domain as porte
import budget_simulator.engine.cadre as cadre
from budget_simulator.config import load_default_values
from budget_simulator.engine._noms_parametres import NOMS_PARAMETRES_ADMIS
from budget_simulator.simulator import BudgetSimulatorV45

from cadre_harness import (CAS, DROIT, DROIT_REAJUSTE, PROGRAMME_MIXTE, droit_reajuste_courant,
                           droit_sans_valeurs_datees, egalite_bit_a_bit, impacts_par_annee, pour_le_mode, programme_sur_droit,
                           simuler)
from sous_processus import lancer_python

# `.absolute()` et PAS `.resolve()` : tests/ est monté en lien symbolique par le
# dépôt parent (piège documenté, test_noms_parametres_sync.py).
RACINE = Path(__file__).absolute().parent.parent
CONSTANTS_PY = RACINE / 'budget_simulator' / 'constants.py'
POLICY_JSON = RACINE / 'policy_measures.json'
API_FILE = RACINE / 'api.py'
RUNNER = RACINE / 'tests' / 'snapshots' / 'run_scenarios_full.py'
GENERATEUR_PARAMS = RACINE / 'scripts' / 'generate_scenario_params.py'

DEBUT = C.ANNEE_PREMIER_BUDGET_MANDAT          # 2028, premier budget du mandat
FIN = C.ANNEE_FIN_MANDAT                       # 2032, contrat § 2.1
N_RAMPE = FIN - DEBUT + 1                      # 5 budgets de 2028 à 2032
HORIZON = range(2026, 2036)                    # années simulées (periods = 10)
INCONNU = 'levier_inexistant_w1'

PUBLIES = {nom: m for nom, m in CAS.items() if nom != 'programme_mixte'}
# Bases toujours disponibles (dépôt public seul) + les 10 scénarios publiés
# quand scenarios.json est présent (dépôt parent, ou BUDGETLAB_SCENARIOS_JSON).
BASES = {'statu_quo': {}, 'droit_en_vigueur': DROIT, **PUBLIES}
MODES_PLAFOND = ('reduction', 'avertissement')


def _entrees():
    return {m['id']: m for m in json.loads(POLICY_JSON.read_text(encoding='utf-8'))['mesures']}


# Paramètres en Md€ de la release, DÉRIVÉS du registre (libellé « Md€ ») :
# contrat § 2.1, 17 clés éligibles aux profils en plus des 15 de la rampe.
NOUVEAUX_ELIGIBLES = frozenset(
    f'{levier}.{param}' for levier in C.LEVIERS_RELEASE_E
    for param, spec in _entrees()[levier]['parametres'].items() if 'Md€' in spec['label'])

# Référence du droit en vigueur au début du mandat (réajustements compris).
DEF_REF = DROIT_REAJUSTE['defense']['budget']
DEFENSE_DEFAUT_MOTEUR = load_default_values()['defense']['budget']   # formule p.get('budget', 50) - 50


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------

def _nouveau(module, nom):
    """Nom que le chantier W1 doit livrer : échec explicite tant qu'il manque."""
    if not hasattr(module, nom):
        pytest.fail(f"{module.__name__}.{nom} absent : non livré (chantier W1)")
    return getattr(module, nom)


def _exceptions(exc):
    if isinstance(exc, BaseExceptionGroup):
        for e in exc.exceptions:
            yield from _exceptions(e)
    else:
        yield exc


def _leve(classe, fn):
    """Exige une exception ``classe``, directe ou dans un ExceptionGroup (porte
    annuelle du mode strict) ; la rend."""
    try:
        fn()
    except BaseException as e:  # noqa: BLE001 — on inspecte, on ne masque rien
        trouvees = [x for x in _exceptions(e) if isinstance(x, classe)]
        assert trouvees, f"{classe.__name__} attendue, reçu {e!r}"
        return trouvees[0]
    pytest.fail(f"{classe.__name__} attendue : aucune exception levée")


def _corrections(rapport):
    """``report.corrections`` (point tranché 1 de l'en-tête)."""
    assert 'corrections' in rapport, "report.corrections absent (contrat § 4.1, W5-15)"
    corrections = rapport['corrections']
    assert isinstance(corrections, list)
    for entree in corrections:
        assert {'regle', 'leviers_ignores', 'message'} <= set(entree), entree
    return corrections


def _modules_moteur():
    return [m for n, m in list(sys.modules.items())
            if m is not None and (n == 'budget_simulator' or n.startswith('budget_simulator.'))]


def _remplacer_partout(mp, nom, valeur):
    """Remplace ``nom`` dans chaque module du moteur qui le porte (constante
    importée par nom ou lue par le module) : la mutation atteint le lecteur
    quelle que soit sa façon d'importer."""
    touches = [m for m in _modules_moteur() if nom in vars(m)]
    if not touches:
        pytest.fail(f"{nom} absent du moteur : non livré (chantier W1)")
    for m in touches:
        mp.setattr(m, nom, valeur)


@contextmanager
def _mode_plafond(mode):
    with pytest.MonkeyPatch.context() as mp:
        _remplacer_partout(mp, 'PLAFOND_TOTAL_MODE', mode)
        yield


@contextmanager
def _seuil_plafond(valeur):
    with pytest.MonkeyPatch.context() as mp:
        if valeur is not None:
            _remplacer_partout(mp, 'PLAFOND_IMPACT_TOTAL_PIB', valeur)
        yield


def _canon(x):
    if isinstance(x, dict):
        return {str(k): _canon(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_canon(v) for v in x]
    if isinstance(x, float):
        return x.hex()
    return x


_CACHE = {}


def _sim(mesures, annee_debut=None, strict=False, **kwargs):
    """``simuler`` du harnais (pleine précision), mis en cache. À n'utiliser
    que hors de tout monkeypatch."""
    cle = (json.dumps(mesures, sort_keys=True, default=str), annee_debut, strict,
           json.dumps(kwargs, sort_keys=True, default=str))
    if cle not in _CACHE:
        _CACHE[cle] = simuler(copy.deepcopy(mesures), annee_debut=annee_debut, strict=strict,
                              **copy.deepcopy(kwargs))
    return _CACHE[cle]


def _cadre(programme, profils=None, debut=DEBUT, **kwargs):
    """Cadre temporel préparé ; ``profils`` n'est passé que s'il est donné (le
    défaut de la recette exceptionnelle doit tenir SANS argument)."""
    if profils is not None:
        kwargs['profils'] = copy.deepcopy(profils)
    return cadre.CadreTemporel.preparer(copy.deepcopy(programme), debut, **kwargs)


def _valeur(c, annee, levier, param, defaut=None):
    bloc = c.mesures_de_l_annee(annee).get(levier)
    return defaut if not isinstance(bloc, dict) else bloc.get(param, defaut)


def _impact(imp, annee, levier, cle):
    return imp[annee].get(levier, {}).get(cle, 0.0)


def _primaire(sortie, annee):
    """Solde primaire en Md€ (recettes − dépenses hors intérêts), pleine précision."""
    det = sortie[1].set_index('Année')
    return det.at[annee, 'Recettes_Totales'] - det.at[annee, 'Dépenses_Totales']


def _simuler_avec_totaux(programme, annee_debut, strict=False):
    """Simulation + total mesuré chaque année, |ΣΔdép| + |ΣΔrec| en % du PIB,
    lu sur les impacts que rend ``apply_measures`` (le total que compare le
    plafond, contrat § 5.4)."""
    totaux = {}
    vrai = BudgetSimulatorV45.apply_measures

    def espion(self, year, spending, revenues, gdp, inflation, unemployment):
        dep_apres, rec_apres, impacts = vrai(self, year, spending, revenues, gdp, inflation,
                                             unemployment)
        dep = sum(v.get('depenses', 0.0) for v in impacts.values() if isinstance(v, dict))
        rec = sum(v.get('recettes', 0.0) for v in impacts.values() if isinstance(v, dict))
        totaux[year] = (abs(dep) + abs(rec)) / gdp * 100
        return dep_apres, rec_apres, impacts

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(BudgetSimulatorV45, 'apply_measures', espion)
        sortie = simuler(copy.deepcopy(programme), annee_debut=annee_debut, strict=strict)
    return sortie, totaux


@pytest.fixture(scope='module')
def client():
    spec = importlib.util.spec_from_file_location('api_release_e_w1', API_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return TestClient(module.app, raise_server_exceptions=False), module


# ===========================================================================
# 1. Porte des leviers inconnus (contrat § 5.1 ; W1-1 à W1-4)
# ===========================================================================

def test_w1_1_exception_levier_inconnu():
    LevierInconnu = _nouveau(porte, 'LevierInconnu')
    assert issubclass(LevierInconnu, porte.EntreeInvalide)
    assert issubclass(LevierInconnu, ValueError)


@pytest.mark.parametrize('bloc', [{'x': 1.0}, None], ids=['bloc', 'null'])
@pytest.mark.parametrize('annee_debut', [None, DEBUT], ids=['historique', 'cadre2028'])
def test_w1_1_levier_inconnu_tolerant_signale_et_ignore(annee_debut, bloc):
    """Tolérant : correction tracée (``report.valid = false``), une ligne dans
    ``report.warnings``, une entrée ``LEVIER_INCONNU`` dans
    ``report.corrections`` ; trajectoire, détails, impacts et bloc ``cadre``
    identiques AU BIT à la requête sans le levier. Bloc ``null`` d'un levier
    inconnu : même traitement (contrat § 5.1)."""
    for nom, base in (('statu_quo', {}), ('droit_en_vigueur', DROIT)):
        ref = _sim(base, annee_debut)
        out = _sim({**base, INCONNU: bloc}, annee_debut)
        egalite_bit_a_bit(out, ref, libelle=nom)
        assert _canon(out[2]['cadre']) == _canon(ref[2]['cadre']), nom
        rapport = out[2]
        assert rapport['valid'] is False, nom
        lignes = [w for w in rapport['warnings'] if INCONNU in w]
        assert len(lignes) == 1 and 'inconnu' in lignes[0], lignes
        assert lignes[0].startswith('Entrée ou sortie corrigée'), lignes[0]
        entrees = [c for c in _corrections(rapport) if c['regle'] == 'LEVIER_INCONNU']
        assert len(entrees) == 1 and entrees[0]['leviers_ignores'] == [INCONNU], entrees
        assert any(entrees[0]['message'] in w for w in rapport['warnings'])


@pytest.mark.parametrize('bloc', [{'x': 1.0}, None], ids=['bloc', 'null'])
@pytest.mark.parametrize('annee_debut', [None, DEBUT], ids=['historique', 'cadre2028'])
def test_w1_1_levier_inconnu_strict_leve(annee_debut, bloc):
    LevierInconnu = _nouveau(porte, 'LevierInconnu')
    e = _leve(LevierInconnu, lambda: simuler({INCONNU: bloc}, strict=True, annee_debut=annee_debut))
    assert INCONNU in str(e)


def test_w1_1_levier_connu_a_null_reste_absent():
    """Non-régression (contrat § 5.1) : ``null`` d'un levier CONNU = levier absent,
    sans correction."""
    ref = _sim({}, None)
    out = _sim({'defense': None}, None)
    egalite_bit_a_bit(out, ref)
    assert out[2]['valid'] is True


def test_w1_1_second_simulate_resignale_la_correction(monkeypatch):
    """La porte d'entrée corrige la copie de travail, jamais l'entrée de
    l'appelant (``_entree_retablie``) : un second ``simulate()`` re-signale.
    Porte TOLÉRANTE posée explicitement : en ``BUDGETLAB_STRICT=1`` (suite
    stricte), le même levier lève ``LevierInconnu`` (test strict ci-dessus)."""
    monkeypatch.setenv('BUDGETLAB_STRICT', '')
    sim = BudgetSimulatorV45(periods=10, mesures={INCONNU: {'x': 1.0}})
    premier = sim.simulate()[2]
    assert INCONNU in sim.mesures
    second = sim.simulate()[2]
    assert premier['valid'] is False and second['valid'] is False
    assert [w for w in premier['warnings'] if INCONNU in w] == [w for w in second['warnings'] if INCONNU in w]


def test_w1_2_mille_leviers_inconnus_un_seul_avertissement_borne(caplog):
    """Un seul WARNING par simulation et une seule ligne de rapport, au plus
    ``_DETAILS_MAX`` noms, chacun tronqué à 40 caractères (``_apercu``) ; le
    nombre total reste lisible."""
    noms = [f"{'z' * 60}_{k}" for k in range(1000)]
    t0 = time.perf_counter()
    with caplog.at_level(logging.WARNING):
        sortie = simuler({nom: {'x': 1.0} for nom in noms})
    assert time.perf_counter() - t0 < 5.0
    egalite_bit_a_bit(sortie, _sim({}, None))
    rapport = sortie[2]
    lignes = [w for w in rapport['warnings'] if 'z' * 30 in w]
    assert len(lignes) == 1, len(lignes)
    ligne = lignes[0]
    assert '\n' not in ligne
    assert ligne.count('z' * 30) <= porte._DETAILS_MAX
    assert 'z' * 41 not in ligne                       # chaque nom tronqué (≤ 40 caractères)
    assert re.search(r'\b(1000|995)\b', ligne), ligne   # le volume reste lisible
    assert len(ligne) <= 300 + porte._DETAILS_MAX * 45, len(ligne)
    logs = [r for r in caplog.records if r.levelno == logging.WARNING and 'z' * 30 in r.getMessage()]
    assert len(logs) == 1 and len(logs[0].getMessage()) < 1000
    entrees = [c for c in _corrections(rapport) if c['regle'] == 'LEVIER_INCONNU']
    assert len(entrees) == 1
    assert len(entrees[0]['leviers_ignores']) <= porte._DETAILS_MAX
    assert all(len(n) <= 40 for n in entrees[0]['leviers_ignores'])


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
def test_w1_3_levier_inconnu_apres_la_porte_est_un_defaut_du_moteur(monkeypatch, strict):
    """Le ``continue`` silencieux d'``apply_measures`` devient ``RuntimeError``
    (défaut du moteur, jamais une faute de l'appelant) : branche inatteignable
    derrière la porte d'entrée, atteinte ici en appelant directement."""
    monkeypatch.setenv('BUDGETLAB_STRICT', '1' if strict else '')
    sim = BudgetSimulatorV45(periods=1)
    sim._reset_state()
    sim.mesures = {INCONNU: {'x': 1.0}}
    with pytest.raises(RuntimeError, match='inconnu') as info:
        sim.apply_measures(2027, 1650.0, 1560.0, 3100.0, 0.015, 0.075)
    assert not isinstance(info.value, porte.EntreeInvalide)


def test_w1_4_constat_avant_du_cadrage():
    """Cadrage § 1.3 : le budget 2026 voté + ``{"droits_succession": {"montant": 20},
    "impot_plancher": {"taux": 0.02}}`` passait en silence (``valid: true``).
    Désormais : ``impot_plancher`` refusé comme levier inconnu,
    ``droits_succession.montant`` refusé par la porte des noms ; aucun des deux
    ne change la trajectoire."""
    base = DROIT        # le budget 2026 voté, tel que le moteur le tient (droit en vigueur)
    demande = {**base, 'droits_succession': {'montant': 20}, 'impot_plancher': {'taux': 0.02}}
    out = _sim(demande, None)
    egalite_bit_a_bit(out, _sim(base, None))
    rapport = out[2]
    assert rapport['valid'] is False
    assert any('impot_plancher' in w and 'inconnu' in w for w in rapport['warnings']), rapport['warnings']
    assert any('droits_succession' in w and 'montant' in w and 'inconnu' in w for w in rapport['warnings'])
    assert [c['leviers_ignores'] for c in _corrections(rapport)
            if c['regle'] == 'LEVIER_INCONNU'] == [['impot_plancher']]
    LevierInconnu = _nouveau(porte, 'LevierInconnu')
    _leve(LevierInconnu, lambda: simuler(demande, strict=True))
    # Sans le levier inconnu, le strict refuse le NOM inconnu (porte des noms, v0.6.10).
    _leve(porte.ParametreInconnu,
          lambda: simuler({**base, 'droits_succession': {'montant': 20}}, strict=True))


# ===========================================================================
# 2. Garde G9 côté moteur (contrat § 5.2 : le site lit les noms admis dans le
#    registre généré du sous-module)
# ===========================================================================

def test_g9_tout_groupe_admis_est_connu_du_registre_du_moteur():
    """Non-régression : un groupe admis n'est jamais refusé par l'API (422 des
    leviers inconnus) ; les onze leviers de la release sont admis."""
    sim = BudgetSimulatorV45(periods=1)
    assert set(NOMS_PARAMETRES_ADMIS) <= set(sim.measure_registry)
    assert set(C.LEVIERS_RELEASE_E) <= set(NOMS_PARAMETRES_ADMIS)


def test_g9_registre_genere_expose_tous_les_noms_admis():
    """Le registre lu par le site (``measure_registry.json``) ne liste que les
    leviers à handler : les leviers à formule (``depenses_publiques``,
    ``transferts_etranger``, ``defense``…) lui échappent, et le test G9 du site
    (``KNOWN_API_GROUPS`` ⊇ noms admis) passerait à vide pour eux. Point tranché
    3 de l'en-tête : bloc généré ``noms_parametres_admis`` = module des noms
    admis, au nom près (par le générateur, jamais à la main)."""
    snapshot = json.loads((RACINE / 'tests' / 'snapshots' / 'measure_registry.json')
                          .read_text(encoding='utf-8'))
    noms = snapshot.get('noms_parametres_admis')
    assert noms is not None, "measure_registry.json sans bloc noms_parametres_admis"
    assert {l: sorted(v) for l, v in noms.items()} == {
        l: sorted(v) for l, v in NOMS_PARAMETRES_ADMIS.items()}
    for formule in ('depenses_publiques', 'transferts_etranger'):
        assert formule in noms


# ===========================================================================
# 3. Exclusions mutuelles X1 et X2 (contrat § 4.1 ; W1-5, W1-6)
# ===========================================================================

X1 = {'droits_succession': {'variation': 5.0}, 'fiscalite_patrimoine': {'intensite': 0.2}}
X2 = {'transferts_etranger': {'montant': -5.0},
      'rabot_uniforme': {'taux_reduction': 0.03, 'exclure_dette': 1, 'exclure_defense': 1,
                         'exclure_ue': 0}}
CAS_EXCLUSION = [('X1', X1, 'droits_succession', 'fiscalite_patrimoine'),
                 ('X2', X2, 'transferts_etranger', 'rabot_uniforme')]
IDS_EXCLUSION = [c[0] for c in CAS_EXCLUSION]


def _sans(programme, levier):
    return {k: v for k, v in programme.items() if k != levier}


def test_exclusions_table_du_contrat():
    """Table ``EXCLUSIONS_MUTUELLES`` dans le bloc W1 de ``constants.py`` : deux
    règles, chacune nomme ses deux leviers (le second est le levier ignoré)."""
    table = _nouveau(C, 'EXCLUSIONS_MUTUELLES')
    entrees = list(table.values()) if isinstance(table, dict) else list(table)
    assert len(entrees) == 2
    textes = [repr(e) for e in entrees]
    assert any('droits_succession' in t and 'fiscalite_patrimoine' in t for t in textes), textes
    assert any('transferts_etranger' in t and 'rabot_uniforme' in t for t in textes), textes
    source = CONSTANTS_PY.read_text(encoding='utf-8')
    bloc = source[source.index('# === RELEASE E — W1 ==='):source.index('# === RELEASE E — W2 ===')]
    assert re.search(r'^EXCLUSIONS_MUTUELLES\b', bloc, flags=re.MULTILINE)


def test_exclusions_exception_stricte():
    LeviersIncompatibles = _nouveau(porte, 'LeviersIncompatibles')
    assert issubclass(LeviersIncompatibles, porte.EntreeInvalide)
    assert issubclass(LeviersIncompatibles, ValueError)


@pytest.mark.parametrize('annee_debut', [None, DEBUT], ids=['historique', 'cadre2028'])
@pytest.mark.parametrize('regle, programme, ignore, garde', CAS_EXCLUSION, ids=IDS_EXCLUSION)
def test_w1_5_6_exclusion_tolerante(regle, programme, ignore, garde, annee_debut):
    """Tolérant : le levier désigné est retiré (jamais appliqué, absent des
    impacts) ; trajectoire = celle de l'autre levier seul, AU BIT (anti-double-
    compte : les successions ne sont pas comptées par deux leviers ; la
    contribution à l'UE n'est pas coupée deux fois) ; correction tracée et
    lisible dans ``report.corrections``."""
    out = _sim(programme, annee_debut)
    ref = _sim(_sans(programme, ignore), annee_debut)
    egalite_bit_a_bit(out, ref, libelle=regle)
    rapport = out[2]
    assert rapport['valid'] is False
    assert all(ignore not in an for an in rapport['measure_impacts_by_year'])
    entrees = [c for c in _corrections(rapport) if c['regle'] == regle]
    assert len(entrees) == 1 and entrees[0]['leviers_ignores'] == [ignore], entrees
    assert garde in entrees[0]['message'] and ignore in entrees[0]['message']
    assert any(entrees[0]['message'] in w for w in rapport['warnings'])
    if annee_debut is not None:
        assert ignore not in rapport['cadre']['leviers_modifies']
        assert ignore not in rapport['cadre']['mesures_effectives']


@pytest.mark.parametrize('annee_debut', [None, DEBUT], ids=['historique', 'cadre2028'])
@pytest.mark.parametrize('regle, programme, ignore, garde', CAS_EXCLUSION, ids=IDS_EXCLUSION)
def test_w1_5_6_exclusion_stricte(regle, programme, ignore, garde, annee_debut):
    LeviersIncompatibles = _nouveau(porte, 'LeviersIncompatibles')
    e = _leve(LeviersIncompatibles, lambda: simuler(programme, strict=True, annee_debut=annee_debut))
    assert ignore in str(e) and garde in str(e)


RABOT_UE_EXCLUE = {'taux_reduction': 0.03, 'exclure_dette': 1, 'exclure_defense': 1, 'exclure_ue': 1}
NON_EXCLUSIONS = [
    ('X1', {'droits_succession': {'variation': 0.0}, 'fiscalite_patrimoine': {'intensite': 0.2}}),
    ('X1', {'droits_succession': {'variation': 5.0}, 'fiscalite_patrimoine': {'intensite': 0.0}}),
    ('X1', {'droits_succession': {'variation': 5.0}}),
    ('X2', {'transferts_etranger': {'montant': -5.0}, 'rabot_uniforme': RABOT_UE_EXCLUE}),
    ('X2', {'transferts_etranger': {'montant': -5.0}, 'rabot_uniforme': {'taux_reduction': 0.03}}),
    ('X2', {'transferts_etranger': {'montant': -5.0},
            'rabot_uniforme': {'taux_reduction': 0.0, 'exclure_ue': 0}}),
    ('X2', {'transferts_etranger': {'montant': 0.0},
            'rabot_uniforme': {'taux_reduction': 0.03, 'exclure_ue': 0}}),
]


@pytest.mark.parametrize('annee_debut', [None, DEBUT], ids=['historique', 'cadre2028'])
@pytest.mark.parametrize('regle, programme', NON_EXCLUSIONS,
                         ids=[f'{r}-{k}' for k, (r, _) in enumerate(NON_EXCLUSIONS)])
def test_exclusion_seulement_si_les_deux_conditions(regle, programme, annee_debut):
    """Une seule des deux conditions (montant neutre, rabot sans la part UE ou
    nul, patrimoine au neutre ou absent) : aucune exclusion, dans les deux
    portes ; le levier non neutre est bien évalué."""
    rapport = _sim(programme, annee_debut)[2]
    assert not [c for c in _corrections(rapport) if c['regle'] == regle]
    if programme.get('transferts_etranger', {}).get('montant'):
        assert any('transferts_etranger' in an for an in rapport['measure_impacts_by_year'])
    if programme.get('droits_succession', {}).get('variation'):
        assert any('droits_succession' in an for an in rapport['measure_impacts_by_year'])
    try:
        simuler(programme, strict=True, annee_debut=annee_debut)
    except BaseException as e:  # noqa: BLE001 — un squelette non livré peut lever ; pas une exclusion
        assert not any(type(x).__name__ == 'LeviersIncompatibles' for x in _exceptions(e)), e


@pytest.mark.parametrize('annee_debut', [None, DEBUT], ids=['historique', 'cadre2028'])
def test_aucune_correction_sur_les_scenarios_publies(annee_debut):
    """Neutralité des garde-fous W1 sur les 10 scénarios (et les deux bases) :
    aucune exclusion ni levier inconnu, ``report.corrections`` vide, résultat
    valide. Mode historique : chaque base telle que le mode l'accepte
    (``pour_le_mode`` : sans la recette d'une seule année, release P)."""
    for nom, base in BASES.items():
        rapport = _sim(pour_le_mode(base, annee_debut), annee_debut)[2]
        assert _corrections(rapport) == [], nom
        assert rapport['valid'] is True, nom


@pytest.mark.parametrize('regle, programme, ignore, garde', CAS_EXCLUSION, ids=IDS_EXCLUSION)
def test_mutation_sans_la_table_le_double_compte_reapparait(regle, programme, ignore, garde):
    """Par MUTATION : table vidée (elle est relue à chaque simulation), le
    levier exclu redevient évalué (le même euro compté par deux leviers) et la
    propriété du test W1-5/W1-6 rougit."""
    table = _nouveau(C, 'EXCLUSIONS_MUTUELLES')
    with pytest.MonkeyPatch.context() as mp:
        _remplacer_partout(mp, 'EXCLUSIONS_MUTUELLES', type(table)())
        out = simuler(programme)
        ref = simuler(_sans(programme, ignore))
    assert any(ignore in an for an in out[2]['measure_impacts_by_year'])
    with pytest.raises(AssertionError):
        egalite_bit_a_bit(out, ref)


# ===========================================================================
# 4. Profils temporels (contrat § 2 ; W1-9 à W1-11, W1-14, W1-16)
# ===========================================================================

def test_profils_eligibles_et_fin_de_mandat():
    """``PROFILS_ELIGIBLES`` = rampe existante ∪ les 17 paramètres en Md€ de la
    release ∪ les 4 taux et niveaux ouverts après la revue adverse
    (``PROFILS_TAUX_ET_NIVEAUX``, forme « annee » exclue) ∪ les 2 coefficients
    d'indexation (``PROFILS_INDEXATIONS``, gel d'une année, décision du
    mainteneur du 12/11/2026 ; forme « rampe » exclue) ; ``ANNEE_FIN_MANDAT``
    lu de ``constants`` (jamais un second littéral), égal à ``ANNEE_DEBUT_MAX`` ;
    une seule implémentation (``_mesures_profilees`` remplace ``_mesures_rampees``)."""
    assert len(NOUVEAUX_ELIGIBLES) == 17
    assert len(cadre.PROFILS_TAUX_ET_NIVEAUX) == 4
    assert len(cadre.PROFILS_INDEXATIONS) == 2
    eligibles = _nouveau(cadre, 'PROFILS_ELIGIBLES')
    assert eligibles == (cadre.RAMPE_LEVIERS_ELIGIBLES | NOUVEAUX_ELIGIBLES | cadre.PROFILS_TAUX_ET_NIVEAUX
                         | cadre.PROFILS_INDEXATIONS)
    assert _nouveau(cadre, 'ANNEE_FIN_MANDAT') == C.ANNEE_FIN_MANDAT == cadre.ANNEE_DEBUT_MAX
    for cle in eligibles:
        levier, param = cle.split('.')
        assert param in NOMS_PARAMETRES_ADMIS[levier], cle
    assert hasattr(cadre, '_mesures_profilees') and not hasattr(cadre, '_mesures_rampees')


def test_profil_exception():
    ProfilInvalide = _nouveau(cadre, 'ProfilInvalide')
    assert issubclass(ProfilInvalide, porte.EntreeInvalide) and issubclass(ProfilInvalide, ValueError)


# --- Neutralité : absent ≡ {} ≡ None ≡ « plein » ---------------------------

@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
@pytest.mark.parametrize('annee_debut', [None, DEBUT], ids=['historique', 'cadre2028'])
def test_profils_vides_neutres_au_bit_sur_les_scenarios(annee_debut, strict):
    """``profils`` absent, ``{}`` ou ``None`` : sorties ET rapport identiques au
    bit, sur les 10 scénarios et les deux bases, deux modes, deux portes
    (chaque base telle que le mode l'accepte, ``pour_le_mode``)."""
    for nom, base in BASES.items():
        base = pour_le_mode(base, annee_debut)
        ref = _sim(base, annee_debut, strict)
        for vide in ({}, None):
            out = _sim(base, annee_debut, strict, profils=vide)
            egalite_bit_a_bit(out, ref, libelle=nom)
            assert _canon(out[2]) == _canon(ref[2]), (nom, vide)


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
def test_w1_9_plein_egal_absent_au_bit_sur_les_scenarios(strict):
    """Forme ``plein`` posée sur chaque paramètre éligible que le scénario
    règle (hors recette exceptionnelle, qui n'admet que ``annee``) : sorties
    identiques au bit à la requête sans profil (mode cadre)."""
    eligibles = _nouveau(cadre, 'PROFILS_ELIGIBLES')
    for nom, base in {**BASES, 'programme_mixte': PROGRAMME_MIXTE}.items():
        plein = {cle: {'forme': 'plein'} for cle in sorted(eligibles)
                 if cle != 'recette_exceptionnelle.montant'
                 and isinstance(base.get(cle.split('.')[0]), dict)
                 and cle.split('.')[1] in base[cle.split('.')[0]]}
        egalite_bit_a_bit(_sim(base, DEBUT, strict, profils=plein), _sim(base, DEBUT, strict),
                          libelle=nom)


def test_profils_sur_leviers_non_modifies_sans_effet():
    """Un profil sur chacun des paramètres éligibles (taille maximale admise),
    programme = statu quo : rien à étaler, sorties identiques au bit."""
    eligibles = _nouveau(cadre, 'PROFILS_ELIGIBLES')
    profils = {cle: ({'forme': 'annee', 'annee': 2030} if cle == 'recette_exceptionnelle.montant'
                     else {'forme': 'rampe'}) for cle in eligibles}
    assert len(profils) == len(eligibles)
    egalite_bit_a_bit(_sim({}, DEBUT, profils=profils), _sim({}, DEBUT))


# --- Rampe jusqu'en 2032 -----------------------------------------------------

def test_w1_9_rampe_jusqu_a_la_fin_du_mandat_et_valeur_exacte_en_2032():
    """``rampe`` : n = FIN − début + 1 ; année a de début à FIN − 1 :
    p_ref + (p − p_ref) × (a − début + 1) / n (même arithmétique que la rampe
    v0.7.0) ; à partir de FIN, la valeur EXACTE du programme (``==``). Référence
    d'un levier du droit : le droit réajusté ; d'un levier absent du droit : son
    neutre (``NEUTRES_RELEASE_E``). Droit constant (release P : la surtaxe
    datée vaut 0 dès 2027, la formule y deviendrait exacte et la garde du test
    sans objet ; les valeurs datées ont leurs tests W1-7)."""
    with droit_sans_valeurs_datees():
        p_ref = droit_reajuste_courant(DEBUT)['is_exceptionnel_tge']['montant']
        p = 13.4
        # Garde du test : ici la formule « p_ref + (p − p_ref) × n / n » N'EST PAS
        # exacte ; un code qui l'appliquerait aussi en 2032 serait pris.
        assert p_ref + (p - p_ref) * N_RAMPE / N_RAMPE != p
        credits = 10.0
        neutre = C.NEUTRES_RELEASE_E['depenses_publiques']['credits_etat']
        c = _cadre(programme_sur_droit(is_exceptionnel_tge={'montant': p},
                                       depenses_publiques={'credits_etat': credits}),
                   {'is_exceptionnel_tge.montant': {'forme': 'rampe'},
                    'depenses_publiques.credits_etat': {'forme': 'rampe'}})
    for a in range(2026, DEBUT):
        assert _valeur(c, a, 'is_exceptionnel_tge', 'montant') == p_ref
        assert _valeur(c, a, 'depenses_publiques', 'credits_etat', neutre) == neutre
    for k, a in enumerate(range(DEBUT, FIN), start=1):
        assert _valeur(c, a, 'is_exceptionnel_tge', 'montant') == p_ref + (p - p_ref) * k / N_RAMPE, a
        assert _valeur(c, a, 'depenses_publiques', 'credits_etat') == neutre + (credits - neutre) * k / N_RAMPE
    for a in range(FIN, 2036):
        assert _valeur(c, a, 'is_exceptionnel_tge', 'montant') == p, a
        assert _valeur(c, a, 'depenses_publiques', 'credits_etat') == credits, a


@pytest.mark.parametrize('debut', [2029, 2031])
def test_rampe_fin_de_mandat_quel_que_soit_le_debut(debut):
    """La rampe finit TOUJOURS en 2032 : n = 2032 − début + 1."""
    n = FIN - debut + 1
    c = _cadre(programme_sur_droit(defense={'budget': 70}), {'defense.budget': {'forme': 'rampe'}},
               debut=debut)
    for k, a in enumerate(range(debut, FIN), start=1):
        assert _valeur(c, a, 'defense', 'budget') == DEF_REF + (70 - DEF_REF) * k / n
    assert all(_valeur(c, a, 'defense', 'budget') == 70 for a in range(FIN, 2036))


def test_w1_9_alias_rampe_egal_profil_rampe_au_bit():
    """La requête ``rampe: {annees: 5, leviers}`` v0.7.0 est un alias de
    ``profils`` ``rampe`` (début 2028 : mêmes cinq budgets) ; une seule
    implémentation, sorties identiques au bit. (Les tests de
    ``test_cadre_v070_rampe.py`` restent verts sans modification.)"""
    prog = programme_sur_droit(defense={'budget': 70}, niches_fiscales_tge={'montant': 40})
    cles = ['defense.budget', 'niches_fiscales_tge.montant']
    alias = _sim(prog, DEBUT, rampe={'annees': N_RAMPE, 'leviers': cles})
    profils = _sim(prog, DEBUT, profils={cle: {'forme': 'rampe'} for cle in cles})
    egalite_bit_a_bit(profils, alias)


@pytest.mark.parametrize('forme', [{'forme': 'plein'}, {'forme': 'rampe'},
                                   {'forme': 'annee', 'annee': 2030}],
                         ids=['plein', 'rampe', 'annee2030'])
@pytest.mark.parametrize('cle, x', [('depenses_publiques.credits_etat', 10.0),
                                    ('transferts_etranger.montant', 5.0)],
                         ids=['credits_etat', 'transferts_etranger'])
def test_profils_effet_direct_signe_symetrie_et_solde(cle, x, forme):
    """Leviers en Md€ à formule (finaux dès le socle) : effet direct de chaque
    année = valeur du profil ; +x et −x opposés au bit (symétrie) ; première
    année d'application : solde primaire = statu quo − x exactement (signe et
    ordre de grandeur), les années d'avant inchangées."""
    levier, param = cle.split('.')
    neutre = C.NEUTRES_RELEASE_E[levier][param]

    def attendu(a, v):
        if a < DEBUT:
            return 0.0
        if forme['forme'] == 'plein':
            return v
        if forme['forme'] == 'annee':
            return v if a == forme['annee'] else 0.0
        return neutre + (v - neutre) * (a - DEBUT + 1) / N_RAMPE if a < FIN else v

    sorties = {}
    for signe in (+1, -1):
        sorties[signe] = _sim({levier: {param: signe * x}}, DEBUT, profils={cle: forme})
        imp = impacts_par_annee(sorties[signe][2])
        for a in HORIZON:
            assert _impact(imp, a, levier, 'depenses') == attendu(a, signe * x), (signe, a)
    plus, moins = (impacts_par_annee(sorties[s][2]) for s in (+1, -1))
    for a in HORIZON:
        assert _impact(plus, a, levier, 'depenses') == -_impact(moins, a, levier, 'depenses')
    sq = _sim({}, DEBUT)
    premiere = forme.get('annee', DEBUT)
    for a in range(2026, premiere):
        assert _primaire(sorties[+1], a) == _primaire(sq, a), a
    assert _primaire(sorties[+1], premiere) - _primaire(sq, premiere) == pytest.approx(
        -attendu(premiere, x), abs=1e-9)


# --- Une seule année ---------------------------------------------------------

def test_w1_10_une_seule_annee_defense():
    """``annee`` : la valeur du programme l'année choisie SEULEMENT, le droit
    en vigueur avant et après (contrat § 2.1)."""
    profil = {'defense.budget': {'forme': 'annee', 'annee': 2030}}
    prog = programme_sur_droit(defense={'budget': 70})
    c = _cadre(prog, profil)
    for a in HORIZON:
        assert _valeur(c, a, 'defense', 'budget') == (70 if a == 2030 else DEF_REF), a
    imp = impacts_par_annee(_sim(prog, DEBUT, profils=profil)[2])
    for a in HORIZON:
        assert _impact(imp, a, 'defense', 'depenses') == (70 if a == 2030 else DEF_REF) - DEFENSE_DEFAUT_MOTEUR


def test_w1_10_g8_retour_effet_ponctuel_emis_puis_rendu():
    """G8-retour (``is_exceptionnel_tge``, effet ponctuel de compétitivité) :
    émis l'année choisie, rendu l'année suivante, Σ des incréments sur
    l'horizon = 0 à 1e-12 ; rien avant ; l'effet direct sur le solde revient au
    statu quo l'année suivante."""
    p_ref = DROIT_REAJUSTE['is_exceptionnel_tge']['montant']
    p = 12.0
    une = impacts_par_annee(_sim(programme_sur_droit(is_exceptionnel_tge={'montant': p}), DEBUT,
                                 profils={'is_exceptionnel_tge.montant': {'forme': 'annee',
                                                                          'annee': 2030}})[2])
    sq = impacts_par_annee(_sim(DROIT_REAJUSTE, DEBUT)[2])
    ecarts = {a: _impact(une, a, 'is_exceptionnel_tge', 'competitivite')
              - _impact(sq, a, 'is_exceptionnel_tge', 'competitivite') for a in HORIZON}
    effet = -(p - p_ref) * C.IS_EXCEPTIONNEL_COMPET_PAR_MD
    assert ecarts[2030] == pytest.approx(effet, rel=1e-12)
    assert ecarts[2031] == pytest.approx(-effet, rel=1e-12)
    assert abs(sum(ecarts.values())) <= 1e-12
    assert all(ecarts[a] == 0 for a in range(2026, 2030))
    recettes = {a: _impact(une, a, 'is_exceptionnel_tge', 'recettes')
                - _impact(sq, a, 'is_exceptionnel_tge', 'recettes') for a in HORIZON}
    assert recettes[2030] == pytest.approx(p - p_ref, rel=1e-12)
    assert all(recettes[a] == 0 for a in HORIZON if a != 2030), recettes


def test_g8_profil_rampe_effet_ponctuel_compte_une_fois():
    """Sous ``rampe``, Σ des incréments = effet du palier atteint, une fois."""
    p_ref = DROIT_REAJUSTE['is_exceptionnel_tge']['montant']
    p = 12.0
    rampe = impacts_par_annee(_sim(programme_sur_droit(is_exceptionnel_tge={'montant': p}), DEBUT,
                                   profils={'is_exceptionnel_tge.montant': {'forme': 'rampe'}})[2])
    sq = impacts_par_annee(_sim(DROIT_REAJUSTE, DEBUT)[2])
    ecarts = [_impact(rampe, a, 'is_exceptionnel_tge', 'competitivite')
              - _impact(sq, a, 'is_exceptionnel_tge', 'competitivite') for a in HORIZON]
    assert sum(ecarts) == pytest.approx(-(p - p_ref) * C.IS_EXCEPTIONNEL_COMPET_PAR_MD, rel=1e-12)
    assert ecarts[:DEBUT - 2026] == [0.0] * (DEBUT - 2026)


def _une_seule_annee(c, levier, param, annee, p, p_ref):
    """Propriété « une seule année » sur un cadre préparé."""
    return all(_valeur(c, a, levier, param, p_ref) == (p if a == annee else p_ref) for a in HORIZON)


def test_mutation_une_seule_annee_lue_chaque_annee_est_detectee():
    """Par MUTATION : la même demande lue « chaque année » (forme ``plein``)
    compterait l'effet d'un an cinq fois ; la propriété le refuse."""
    prog = programme_sur_droit(defense={'budget': 70})
    bon = _cadre(prog, {'defense.budget': {'forme': 'annee', 'annee': 2030}})
    assert _une_seule_annee(bon, 'defense', 'budget', 2030, 70, DEF_REF)
    mutant = _cadre(prog, {'defense.budget': {'forme': 'plein'}})
    assert not _une_seule_annee(mutant, 'defense', 'budget', 2030, 70, DEF_REF)


# --- Recette exceptionnelle : une seule année, toujours ----------------------

def test_recette_exceptionnelle_une_seule_annee_par_defaut():
    """Défaut de ``recette_exceptionnelle.montant`` : ``{forme: annee, annee:
    annee_debut}`` (règle 4.2-k du plan), sans aucun argument ``profils`` ;
    profil ``annee 2030`` : 2030 seulement."""
    neutre = C.NEUTRES_RELEASE_E['recette_exceptionnelle']['montant']
    for debut in (DEBUT, 2030):
        c = _cadre({'recette_exceptionnelle': {'montant': 10.0}}, debut=debut)
        assert _une_seule_annee(c, 'recette_exceptionnelle', 'montant', debut, 10.0, neutre), debut
    c = _cadre({'recette_exceptionnelle': {'montant': 10.0}},
               {'recette_exceptionnelle.montant': {'forme': 'annee', 'annee': 2030}})
    assert _une_seule_annee(c, 'recette_exceptionnelle', 'montant', 2030, 10.0, neutre)


@pytest.mark.parametrize('forme', [{'forme': 'plein'}, {'forme': 'rampe'}], ids=['plein', 'rampe'])
def test_recette_exceptionnelle_refuse_toute_autre_forme(forme):
    """Seule la forme ``annee`` est admise : strict → ``ProfilInvalide`` ;
    tolérant → profil ignoré (défaut : l'année de début), correction tracée."""
    ProfilInvalide = _nouveau(cadre, 'ProfilInvalide')
    profils = {'recette_exceptionnelle.montant': forme}
    with pytest.raises(ProfilInvalide, match='recette_exceptionnelle'):
        _cadre({'recette_exceptionnelle': {'montant': 10.0}}, profils, strict=True)
    corrections = {}
    c = _cadre({'recette_exceptionnelle': {'montant': 10.0}}, profils, corrections=corrections,
               warned=set())
    assert corrections, "correction attendue en tolérant"
    neutre = C.NEUTRES_RELEASE_E['recette_exceptionnelle']['montant']
    assert _une_seule_annee(c, 'recette_exceptionnelle', 'montant', DEBUT, 10.0, neutre)


def test_recette_exceptionnelle_refusee_en_mode_historique():
    """Mode historique (aucun calendrier) : strict → ``ProfilInvalide`` ;
    tolérant → levier ignoré (jamais évalué), correction tracée."""
    ProfilInvalide = _nouveau(cadre, 'ProfilInvalide')
    demande = {'recette_exceptionnelle': {'montant': 10.0}}
    _leve(ProfilInvalide, lambda: simuler(demande, strict=True))
    out = _sim(demande, None)
    egalite_bit_a_bit(out, _sim({}, None))
    assert out[2]['valid'] is False
    assert any('recette_exceptionnelle' in w for w in out[2]['warnings'])
    assert all('recette_exceptionnelle' not in an for an in out[2]['measure_impacts_by_year'])


# --- Horloge d'un levier profilé (contrat § 2.1, relecture I4 ; W1-14) ------

def test_w1_14_horloge_une_annee_niches_fiscales():
    """``niches_fiscales_tge.montant`` en ``annee 2031`` : la montée en charge
    démarre en 2031 — recette 2031 = ``PHASING_NICHES_FISCALES_TGE[0]`` × écart
    (et non l'écart entier, horloge 2028) ; ``origine`` rapportée = 2031."""
    p_ref = DROIT_REAJUSTE['niches_fiscales_tge']['montant']
    p = 40.0
    profils = {'niches_fiscales_tge.montant': {'forme': 'annee', 'annee': 2031}}
    out = _sim(programme_sur_droit(niches_fiscales_tge={'montant': p}), DEBUT, profils=profils)
    une, sq = impacts_par_annee(out[2]), impacts_par_annee(_sim(DROIT_REAJUSTE, DEBUT)[2])
    ecart = {a: _impact(une, a, 'niches_fiscales_tge', 'recettes')
             - _impact(sq, a, 'niches_fiscales_tge', 'recettes') for a in HORIZON}
    assert ecart[2031] == pytest.approx(C.PHASING_NICHES_FISCALES_TGE[0] * (p_ref - p), rel=1e-12)
    assert all(ecart[a] == 0 for a in HORIZON if a != 2031), ecart
    assert out[2]['cadre']['profils']['niches_fiscales_tge.montant']['origine'] == 2031


def test_w1_14_horloge_une_annee_transition_premiere_annee():
    """``transition_ecologique.investissement`` en ``annee 2032`` : retour
    fiscal et compétitivité de 2032 = ceux de la PREMIÈRE année d'application
    (mesurés sur le même investissement appliqué dès 2028, sa première
    année), et non ceux de la cinquième."""
    tr = dict(DROIT_REAJUSTE['transition_ecologique'], investissement=20.0)
    prog = programme_sur_droit(transition_ecologique=tr)
    une = impacts_par_annee(_sim(prog, DEBUT, profils={
        'transition_ecologique.investissement': {'forme': 'annee', 'annee': 2032}})[2])
    plein = impacts_par_annee(_sim(prog, DEBUT)[2])
    sq = impacts_par_annee(_sim(DROIT_REAJUSTE, DEBUT)[2])

    def ecart(imp, a, cle):
        return (_impact(imp, a, 'transition_ecologique', cle)
                - _impact(sq, a, 'transition_ecologique', cle))
    for cle in ('depenses', 'recettes', 'competitivite'):
        assert ecart(une, FIN, cle) == pytest.approx(ecart(plein, DEBUT, cle), rel=1e-12, abs=1e-15), cle
    # Garde du test : sur l'horloge 2028, 2032 serait la cinquième année
    # (retour fiscal et compétitivité différents de la première).
    assert ecart(plein, FIN, 'recettes') != pytest.approx(ecart(plein, DEBUT, 'recettes'))
    assert ecart(plein, FIN, 'competitivite') != pytest.approx(ecart(plein, DEBUT, 'competitivite'))


def test_horloge_origine_premiere_annee_ou_un_parametre_du_levier_s_ecarte():
    """L'origine est celle du LEVIER : un autre de ses paramètres modifié dès
    2028 (taxe carbone, ``plein``) la fixe à 2028, même si l'investissement
    n'entre qu'en 2032 ; ``plein`` et ``rampe`` : origine = début."""
    tr = dict(DROIT_REAJUSTE['transition_ecologique'], investissement=20.0, taxe_carbone=80.0)
    rapport = _sim(programme_sur_droit(transition_ecologique=tr), DEBUT, profils={
        'transition_ecologique.investissement': {'forme': 'annee', 'annee': 2032}})[2]
    assert rapport['cadre']['profils']['transition_ecologique.investissement']['origine'] == DEBUT
    for forme in ({'forme': 'plein'}, {'forme': 'rampe'}):
        r = _sim(programme_sur_droit(defense={'budget': 70}), DEBUT, profils={'defense.budget': forme})[2]
        assert r['cadre']['profils']['defense.budget']['origine'] == DEBUT, forme


@pytest.mark.parametrize('forme', [{'forme': 'plein'}, {'forme': 'rampe'},
                                   {'forme': 'annee', 'annee': 2030}],
                         ids=['plein', 'rampe', 'annee2030'])
def test_rapport_cadre_profils(forme):
    """Bloc ``cadre.profils`` : ``{"levier.parametre": {forme, annee?, origine,
    valeurs: {"2028": x, …}}}`` ; ``annee`` présente pour la seule forme
    ``annee`` ; ``valeurs`` = valeur appliquée chaque année du mandat."""
    profils = {'defense.budget': forme}
    prog = programme_sur_droit(defense={'budget': 70})
    bloc = _sim(prog, DEBUT, profils=profils)[2]['cadre']['profils']['defense.budget']
    assert bloc['forme'] == forme['forme']
    assert ('annee' in bloc) == (forme['forme'] == 'annee')
    if forme['forme'] == 'annee':
        assert bloc['annee'] == forme['annee']
    c = _cadre(prog, profils)
    for a in range(DEBUT, FIN + 1):
        assert bloc['valeurs'][str(a)] == _valeur(c, a, 'defense', 'budget'), a


# --- Validation (W1-11) ------------------------------------------------------

PROFILS_INVALIDES = [
    ({'tva_rate.taux': {'forme': 'rampe'}}, 'tva_rate.taux'),                 # taux : non éligible
    ({'inconnu.x': {'forme': 'rampe'}}, 'inconnu.x'),                         # clé inconnue
    ({'defense.budget': {'forme': 'lineaire'}}, 'lineaire'),                  # forme inconnue
    ({'defense.budget': {'forme': 'annee', 'annee': DEBUT - 1}}, str(DEBUT - 1)),  # avant le début
    ({'defense.budget': {'forme': 'annee', 'annee': FIN + 1}}, str(FIN + 1)),      # après 2032
    ({'defense.budget': {'forme': 'annee'}}, 'annee'),                        # année manquante
    ({'defense.budget': {'forme': 'annee', 'annee': 2030.0}}, 'annee'),       # année non entière
    ({'defense.budget': {'forme': 'annee', 'annee': True}}, 'annee'),
    ({'defense.budget': {'forme': 'rampe', 'annee': 2030}}, 'annee'),         # année sur une rampe
    ({'defense.budget': {'forme': 'plein', 'annee': 2030}}, 'annee'),
    ({'defense.budget': 'rampe'}, 'defense.budget'),                          # mal formé
    (['defense.budget'], 'profils'),
]
IDS_INVALIDES = ['non_eligible', 'inconnue', 'forme', 'avant_debut', 'apres_2032', 'sans_annee',
                 'annee_flottante', 'annee_booleen', 'annee_sur_rampe', 'annee_sur_plein',
                 'mal_forme', 'pas_un_objet']


@pytest.mark.parametrize('profils, motif', PROFILS_INVALIDES, ids=IDS_INVALIDES)
def test_w1_11_profil_invalide_strict(profils, motif):
    ProfilInvalide = _nouveau(cadre, 'ProfilInvalide')
    e = _leve(ProfilInvalide, lambda: simuler(programme_sur_droit(defense={'budget': 70}), strict=True,
                                              annee_debut=DEBUT, profils=copy.deepcopy(profils)))
    assert motif in str(e), str(e)


@pytest.mark.parametrize('profils, motif', PROFILS_INVALIDES, ids=IDS_INVALIDES)
def test_w1_11_profil_invalide_tolerant_ignore(profils, motif):
    """Tolérant : WARNING une fois, correction tracée (``report.valid = false``),
    profil ignoré : sorties identiques au bit à la requête sans lui."""
    prog = programme_sur_droit(defense={'budget': 70})
    out = _sim(prog, DEBUT, profils=profils)
    egalite_bit_a_bit(out, _sim(prog, DEBUT))
    assert out[2]['valid'] is False
    assert any('profil' in w for w in out[2]['warnings']), out[2]['warnings']


def test_w1_11_entree_invalide_ignoree_les_autres_gardees():
    prog = programme_sur_droit(defense={'budget': 70})
    valide = {'defense.budget': {'forme': 'annee', 'annee': 2030}}
    out = _sim(prog, DEBUT, profils={**valide, 'tva_rate.taux': {'forme': 'rampe'}})
    egalite_bit_a_bit(out, _sim(prog, DEBUT, profils=valide))
    assert out[2]['valid'] is False


def test_w1_11_profils_en_mode_historique():
    """Profils non vides sans ``annee_debut`` : strict → ``ProfilInvalide`` ;
    tolérant → ignorés, correction ; vides : rien à dire."""
    ProfilInvalide = _nouveau(cadre, 'ProfilInvalide')
    profils = {'defense.budget': {'forme': 'rampe'}}
    _leve(ProfilInvalide, lambda: simuler({'defense': {'budget': 70}}, strict=True, profils=profils))
    out = _sim({'defense': {'budget': 70}}, None, profils=profils)
    egalite_bit_a_bit(out, _sim({'defense': {'budget': 70}}, None))
    assert out[2]['valid'] is False and any('profil' in w for w in out[2]['warnings'])
    assert out[2]['cadre']['profils'] == {}
    assert _sim({'defense': {'budget': 70}}, None, profils={})[2]['valid'] is True


def test_w1_11_rampe_et_profils_ensemble():
    """``rampe`` ET ``profils`` dans la même requête : strict →
    ``ProfilInvalide`` ; tolérant → ``profils`` retenu, correction tracée."""
    ProfilInvalide = _nouveau(cadre, 'ProfilInvalide')
    prog = programme_sur_droit(defense={'budget': 70})
    rampe = {'annees': 3, 'leviers': ['defense.budget']}
    profils = {'defense.budget': {'forme': 'annee', 'annee': 2030}}
    _leve(ProfilInvalide, lambda: simuler(prog, strict=True, annee_debut=DEBUT, rampe=rampe,
                                          profils=profils))
    out = _sim(prog, DEBUT, rampe=rampe, profils=profils)
    egalite_bit_a_bit(out, _sim(prog, DEBUT, profils=profils))
    assert out[2]['valid'] is False


def test_w1_11_taille_bornee_sans_parcours(caplog):
    """Au plus ``len(PROFILS_ELIGIBLES)`` entrées, sinon rejet SANS parcourir
    (parité avec la rampe, revue de sécurité) : un seul WARNING borné."""
    ProfilInvalide = _nouveau(cadre, 'ProfilInvalide')
    trop = {f'inconnu_{k}.x': {'forme': 'rampe'} for k in range(10_000)}
    prog = programme_sur_droit(defense={'budget': 70})
    t0 = time.perf_counter()
    _leve(ProfilInvalide, lambda: simuler(prog, strict=True, annee_debut=DEBUT, profils=trop))
    with caplog.at_level(logging.WARNING, logger='budget_simulator.engine.cadre'):
        out = simuler(prog, annee_debut=DEBUT, profils=trop)
    assert time.perf_counter() - t0 < 2.0
    messages = [r.getMessage() for r in caplog.records if r.name == 'budget_simulator.engine.cadre']
    assert len(messages) == 1 and len(messages[0]) < 500, [m[:80] for m in messages]
    egalite_bit_a_bit(out, _sim(prog, DEBUT))
    assert out[2]['valid'] is False and sum('profil' in w for w in out[2]['warnings']) == 1


# --- Chaîne des scénarios : runner et paramètres publiés (§ 2.3 ; W1-16) -----

SCENARIOS_DE_TEST = {
    'avec_profils': {
        'label': 'Avec calendrier',
        'apiMeasures': {'defense': {'budget': 70}, 'depenses_publiques': {'credits_etat': -10.0}},
        'profils': {'defense.budget': {'forme': 'annee', 'annee': 2030},
                    'depenses_publiques.credits_etat': {'forme': 'rampe'}},
    },
    'sans_profils': {'label': 'Sans calendrier', 'apiMeasures': {'defense': {'budget': 60}}},
}


def test_w1_16_runner_transmet_les_profils(tmp_path, monkeypatch):
    """``run_scenarios_full.py`` lit ``profils`` d'un ``scenarios.json`` et les
    transmet : résultat égal au bit (après l'arrondi du runner) à
    ``BudgetSimulatorV45(…, profils=…)`` direct ; sans profils, la sortie
    v0.7.2. Le module expose ``PROFILS`` ({scénario: profils}, ``{}`` sans)."""
    source = tmp_path / 'scenarios.json'
    source.write_text(json.dumps(SCENARIOS_DE_TEST, ensure_ascii=False), encoding='utf-8')
    sortie = tmp_path / 'golden.json'
    env = dict(os.environ, BUDGETLAB_SCENARIOS_JSON=str(source))
    r = lancer_python(RUNNER, '--annee-debut', str(DEBUT), '--out', sortie, cwd=RACINE, env=env)
    assert r.returncode == 0, r.stderr[-2000:]
    snapshot = json.loads(sortie.read_text(encoding='utf-8'))

    def direct(sid, **kwargs):
        df, _, _ = BudgetSimulatorV45(periods=10, annee_debut=DEBUT,
                                      mesures=copy.deepcopy(SCENARIOS_DE_TEST[sid]['apiMeasures']),
                                      **kwargs).simulate()
        return {col: [round(float(v), 3) for v in df[col].tolist()] for col in snapshot[sid]['columns']}

    avec = direct('avec_profils', profils=copy.deepcopy(SCENARIOS_DE_TEST['avec_profils']['profils']))
    assert snapshot['avec_profils']['data'] == avec
    assert avec != direct('avec_profils')          # garde : les profils changent bien le résultat
    assert snapshot['sans_profils']['data'] == direct('sans_profils')

    monkeypatch.setenv('BUDGETLAB_SCENARIOS_JSON', str(source))
    spec = importlib.util.spec_from_file_location('runner_release_e_w1', RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert _nouveau(module, 'PROFILS') == {'avec_profils': SCENARIOS_DE_TEST['avec_profils']['profils'],
                                          'sans_profils': {}}


def test_generateur_des_parametres_publie_les_calendriers():
    """Copie sous-module de ``generate_scenario_params.py`` (contrat § 2.3) :
    une ligne « Calendrier » par paramètre profilé ; sans profils, bloc
    inchangé (aucune ligne « Calendrier »)."""
    spec = importlib.util.spec_from_file_location('generateur_params_w1', GENERATEUR_PARAMS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    donnees = copy.deepcopy(SCENARIOS_DE_TEST)
    bloc = module.build_block(donnees)
    calendriers = [l for l in bloc.splitlines() if 'Calendrier' in l]
    assert len(calendriers) == 2, calendriers
    ligne_defense = next(l for l in calendriers if 'defense' in l and 'budget' in l)
    assert '2030' in ligne_defense
    assert any('credits_etat' in l and ('rampe' in l or 'progressi' in l) for l in calendriers)
    sans = {sid: {k: v for k, v in d.items() if k != 'profils'} for sid, d in donnees.items()}
    assert 'Calendrier' not in module.build_block(sans)


# ===========================================================================
# 5. Valeurs datées du droit en vigueur (contrat § 5.3 ; W1-7)
# ===========================================================================

VOTE_SURTAXE = DROIT['is_exceptionnel_tge']['montant']            # 7,3 votés (budget 2026)
# 6,8 : réajustement de l'atterrissage 2026 (lu dans le fichier livré ; depuis la
# release P, le droit réajusté de 2028 porte 0, la surtaxe s'arrêtant dès 2027).
REAJUSTE_SURTAXE = cadre.charger_atterrissage().annees[2026].reajustements['is_exceptionnel_tge']['montant']


def _segment(de, valeur, a=None, source='donnée de test (release E, W1)'):
    seg = {'de': de, 'valeur': valeur}
    if a is not None:
        seg['a'] = a
    if source is not None:
        seg['source'] = source
    return seg


SURTAXE_UN_AN = {'is_exceptionnel_tge': {'montant': [_segment(2026, VOTE_SURTAXE, a=2026),
                                                     _segment(2027, 0)]}}


@contextmanager
def droit_de_test(valeurs_datees=None, mesures_en_plus=None):
    """Droit en vigueur de TEST : le fichier livré, plus ``valeurs_datees`` et
    des leviers ajoutés, écrit dans un fichier temporaire qui passe par la
    vraie validation du moteur (même mécanisme que l'atterrissage du
    harnais)."""
    contenu = json.loads(cadre.DROIT_EN_VIGUEUR_PATH.read_text(encoding='utf-8'))
    contenu['mesures'].update(copy.deepcopy(mesures_en_plus or {}))
    if valeurs_datees is not None:
        contenu['valeurs_datees'] = copy.deepcopy(valeurs_datees)
    with tempfile.TemporaryDirectory() as d, pytest.MonkeyPatch.context() as mp:
        chemin = Path(d) / 'droit_en_vigueur.json'
        chemin.write_text(json.dumps(contenu, ensure_ascii=False), encoding='utf-8')
        mp.setattr(cadre, 'DROIT_EN_VIGUEUR_PATH', chemin)
        cadre.vider_caches()
        try:
            yield
        finally:
            cadre.vider_caches()


def test_w1_7_v1_fichier_livre_avec_la_surtaxe_datee():
    """E était livré SANS valeur datée ; la release de paramètres P écrit la
    seule valeur datée décidée : surtaxe d'IS votée pour 2026 (base votée),
    0 dès 2027 (aucune loi de finances pour 2027 votée), chaque segment avec sa
    source. Le réajustement 2026 reste dans l'atterrissage."""
    contenu = json.loads(cadre.DROIT_EN_VIGUEUR_PATH.read_text(encoding='utf-8'))
    datees = contenu['valeurs_datees']
    assert list(datees) == ['is_exceptionnel_tge'] and list(datees['is_exceptionnel_tge']) == ['montant']
    segments = datees['is_exceptionnel_tge']['montant']
    assert [{k: v for k, v in s.items() if k != 'source'} for s in segments] == [
        {'de': 2026, 'a': 2026, 'valeur': VOTE_SURTAXE}, {'de': 2027, 'valeur': 0}]
    assert all(s['source'].strip() for s in segments)
    assert REAJUSTE_SURTAXE != VOTE_SURTAXE      # prémisse : l'atterrissage 2026 réajuste la surtaxe


@pytest.mark.parametrize('debut', [2027, DEBUT])
def test_w1_7_v2_mesure_votee_pour_un_an_ne_se_reconduit_pas(debut):
    """Surtaxe d'IS votée pour 2026 seulement, 0 dès 2027, réajustée à 6,8 par
    l'atterrissage 2026 : droit 2026 = réajusté ; 2027 et suivantes = 0 (le
    réajustement ne quitte pas son segment) ; droit au début = 0."""
    with droit_de_test(SURTAXE_UN_AN):
        c = cadre.CadreTemporel.preparer({}, debut)
        assert _valeur(c, 2026, 'is_exceptionnel_tge', 'montant') == REAJUSTE_SURTAXE
        for a in range(2027, 2036):
            assert _valeur(c, a, 'is_exceptionnel_tge', 'montant') == 0, a
        assert c.etat.mesures_droit['is_exceptionnel_tge']['montant'] == 0


def test_w1_7_v6_valeur_datee_sur_un_levier_a_taux():
    """Un levier à taux inscrit au droit (P y inscrira les neutres des taux) :
    TTF 0,4 % en 2026, plus haute dès 2027 → droit 2027 = la valeur datée."""
    neutre = C.NEUTRES_RELEASE_E['operations_financieres']['taux_ttf']
    hausse = neutre + 0.001                      # donnée de test, dans le domaine
    datees = {'operations_financieres': {'taux_ttf': [_segment(2026, neutre, a=2026),
                                                      _segment(2027, hausse)]}}
    with droit_de_test(datees, mesures_en_plus={'operations_financieres': {'taux_ttf': neutre}}):
        c = cadre.CadreTemporel.preparer({}, DEBUT)
        assert _valeur(c, 2026, 'operations_financieres', 'taux_ttf') == neutre
        assert _valeur(c, 2027, 'operations_financieres', 'taux_ttf') == hausse
        assert c.etat.mesures_droit['operations_financieres']['taux_ttf'] == hausse


_DOMAINE_SURTAXE = C.PARAM_DOMAINS['is_exceptionnel_tge']['montant']
DATEES_INVALIDES = [
    ({'is_exceptionnel_tge': {'montant': [_segment(2026, VOTE_SURTAXE, a=2026), _segment(2028, 0)]}},
     'non_contigus'),
    ({'is_exceptionnel_tge': {'montant': [_segment(2026, VOTE_SURTAXE, a=2027), _segment(2027, 0)]}},
     'chevauchement'),
    ({'is_exceptionnel_tge': {'montant': [_segment(2026, VOTE_SURTAXE, a=2026, source=''),
                                          _segment(2027, 0)]}}, 'source_vide'),
    ({'is_exceptionnel_tge': {'montant': [_segment(2026, VOTE_SURTAXE, a=2026, source=None),
                                          _segment(2027, 0)]}}, 'sans_source'),
    ({'is_exceptionnel_tge': {'montant': [_segment(2027, 0)]}}, 'premier_apres_2026'),
    ({'is_exceptionnel_tge': {'montant': [_segment(2026, VOTE_SURTAXE, a=2026),
                                          _segment(2027, 0, a=2030)]}}, 'dernier_ferme'),
    ({'is_exceptionnel_tge': {'montant': [_segment(2026, VOTE_SURTAXE, a=2026),
                                          _segment(2027, _DOMAINE_SURTAXE[1] + 1)]}}, 'hors_domaine'),
    ({'is_exceptionnel_tge': {'montantt': [_segment(2026, VOTE_SURTAXE)]}}, 'parametre_inconnu'),
    ({INCONNU: {'x': [_segment(2026, 1.0)]}}, 'levier_inconnu'),
]


@pytest.mark.parametrize('datees, cas', DATEES_INVALIDES, ids=[c for _, c in DATEES_INVALIDES])
def test_w1_7_v3_fichier_invalide_defaut_du_serveur(datees, cas):
    """Segments non contigus, chevauchants, sans source, commençant après 2026,
    dernier non ouvert, valeur hors domaine, nom inconnu : ``RuntimeError``
    (défaut du serveur, 500), jamais une correction silencieuse."""
    with droit_de_test(datees):
        with pytest.raises(RuntimeError):
            cadre.charger_droit_en_vigueur()


def test_w1_7_v4_ecart_de_solde_2027_egal_a_l_effet_isole():
    """Statu quo en mode cadre : l'écart de solde primaire 2027 entre le droit
    à surtaxe d'un an et le droit livré (surtaxe reconduite) est l'effet isolé
    du handler (``_solde_isole``), à 1e-9 ; 2026 inchangé."""
    # Release P : le droit livré EST le droit à surtaxe d'un an ; la référence
    # « surtaxe reconduite » est le même droit sans valeur datée.
    with droit_sans_valeurs_datees():
        ref = simuler({}, annee_debut=DEBUT)
    with droit_de_test(SURTAXE_UN_AN):
        out = simuler({}, annee_debut=DEBUT)
    assert _primaire(out, 2026) == _primaire(ref, 2026)
    df = out[0].set_index('Année')
    etat = (df.at[2027, 'PIB'], df.at[2027, 'Inflation %'] / 100, df.at[2027, 'Chômage %'] / 100)
    sim = BudgetSimulatorV45(periods=1)
    sim._reset_state()
    attendu = (sim._solde_isole('is_exceptionnel_tge', {'montant': 0}, 2027, *etat, DROIT_REAJUSTE)
               - sim._solde_isole('is_exceptionnel_tge', {'montant': REAJUSTE_SURTAXE}, 2027, *etat,
                                  DROIT_REAJUSTE))
    assert attendu != 0
    assert _primaire(out, 2027) - _primaire(ref, 2027) == pytest.approx(attendu, abs=1e-9)


def test_w1_7_v5_mode_historique_ne_lit_pas_le_droit(tmp_path):
    """Non-régression : sans ``annee_debut``, le fichier n'est pas même lu."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(cadre, 'DROIT_EN_VIGUEUR_PATH', tmp_path / 'absent.json')
        cadre.vider_caches()
        try:
            BudgetSimulatorV45(periods=10, mesures={}).simulate()
        finally:
            cadre.vider_caches()


def _surtaxe_non_reconduite(c):
    return all(_valeur(c, a, 'is_exceptionnel_tge', 'montant') == 0 for a in range(2027, 2036))


def test_mutation_valeurs_datees_ignorees_la_surtaxe_est_comptee_chaque_annee():
    """Par MUTATION : le droit lu sans ses valeurs datées (lecture v0.7.2)
    reconduit la surtaxe d'un an chaque année — une recette comptée cinq fois
    de trop ; la propriété le refuse."""
    with droit_de_test(SURTAXE_UN_AN):
        assert _surtaxe_non_reconduite(cadre.CadreTemporel.preparer({}, DEBUT))
    assert _surtaxe_non_reconduite(cadre.CadreTemporel.preparer({}, DEBUT))   # droit livré (P)
    with droit_sans_valeurs_datees():
        assert not _surtaxe_non_reconduite(cadre.CadreTemporel.preparer({}, DEBUT))


# ===========================================================================
# 6. Plafond de 10 % du PIB (contrat § 5.4, décision D6 et sa condition d'arrêt ;
#    W1-8)
# ===========================================================================

# Programmes au-delà du seuil : le programme mixte du harnais sous un seuil
# abaissé (toujours disponible, ~1,4 à 2,1 % du PIB par an), et, au seuil réel,
# chaque scénario publié qui le dépasse (trouvé par sa propriété, jamais nommé ;
# un seul aujourd'hui) quand scenarios.json est présent.
def _scenarios_publies_au_dela_du_seuil():
    return [nom for nom, m in sorted(CAS.items()) if nom != 'programme_mixte'
            and simuler(copy.deepcopy(m), annee_debut=DEBUT)[2]['cadre']['plafond_total']['annees']]


CAS_PLAFOND = [('programme_mixte', 0.015)] + [(nom, None) for nom in _scenarios_publies_au_dela_du_seuil()]
IDS_PLAFOND = [c[0] for c in CAS_PLAFOND]


def test_plafond_interrupteur_et_decision_d6():
    """Interrupteur du bloc W1 ; défaut ``'avertissement'`` : décision D6 du
    mainteneur du 12/11/2026 (en-tête, point 2), après le banc W1 qui montrait
    la condition d'arrêt (filet de croissance plus mordant sans réduction)."""
    modes = _nouveau(C, 'PLAFOND_TOTAL_MODES')
    assert tuple(modes) == MODES_PLAFOND
    assert _nouveau(C, 'PLAFOND_TOTAL_MODE') == 'avertissement'
    source = CONSTANTS_PY.read_text(encoding='utf-8')
    bloc = source[source.index('# === RELEASE E — W1 ==='):source.index('# === RELEASE E — W2 ===')]
    assert re.search(r'^PLAFOND_TOTAL_MODE\b', bloc, flags=re.MULTILINE)
    assert C.PLAFOND_IMPACT_TOTAL_PIB == 0.10     # la constante garde son nom et sa valeur


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
@pytest.mark.parametrize('annee_debut', [None, DEBUT], ids=['historique', 'cadre2028'])
@pytest.mark.parametrize('nom, seuil', CAS_PLAFOND, ids=IDS_PLAFOND)
def test_w1_8_mode_avertissement_sans_reduction(nom, seuil, annee_debut, strict):
    """Mode ``'avertissement'`` (défaut, décision du 12/11/2026) : aucune réduction —
    sorties identiques au bit à celles d'un plafond infini (Σ impacts = Σ des
    sorties des handlers clippées à 5 %) ; bloc ``plafond_total`` :
    ``mode``, ``annees`` = années au-delà du seuil, ``impact_max_pct_pib`` et
    ``annee_impact_max`` mesurés ; un AVIS (``report.valid`` inchangé), plus
    aucun « plafonné »."""
    programme = CAS[nom]
    with _seuil_plafond(seuil):
        seuil_pct = C.PLAFOND_IMPACT_TOTAL_PIB * 100
        with _mode_plafond('avertissement'):
            avert, totaux = _simuler_avec_totaux(programme, annee_debut, strict)
        with _mode_plafond('reduction'):
            reduit = simuler(copy.deepcopy(programme), annee_debut=annee_debut, strict=strict)
    with _seuil_plafond(math.inf), _mode_plafond('reduction'):
        sans = simuler(copy.deepcopy(programme), annee_debut=annee_debut, strict=strict)
    egalite_bit_a_bit(avert, sans, libelle=nom)
    au_dela = sorted(a for a, v in totaux.items() if v > seuil_pct)
    assert au_dela, f"{nom} : aucun dépassement, cas de test sans objet"
    bloc = avert[2]['cadre']['plafond_total']
    assert bloc['mode'] == 'avertissement'
    assert bloc['seuil_pct_pib'] == pytest.approx(seuil_pct) and bloc['reference'] == 'defauts_du_moteur'
    assert bloc['annees'] == au_dela
    annee_max = max(totaux, key=totaux.get)
    assert bloc['annee_impact_max'] == annee_max
    assert bloc['impact_max_pct_pib'] == pytest.approx(totaux[annee_max], abs=0.05)
    assert bloc['impact_max_pct_pib'] > seuil_pct
    avis = [w for w in avert[2]['warnings'] if f'au-delà de {seuil_pct:g} % du PIB' in w]
    assert len(avis) == 1 and avis[0].startswith('Avis'), avert[2]['warnings']
    assert str(au_dela[0]) in avis[0] and 'domaine de validité' in avis[0]
    assert not any('plafonné à' in w for w in avert[2]['warnings'])
    assert avert[2]['valid'] == reduit[2]['valid']


@pytest.mark.parametrize('annee_debut', [None, DEBUT], ids=['historique', 'cadre2028'])
@pytest.mark.parametrize('nom, seuil', CAS_PLAFOND, ids=IDS_PLAFOND)
def test_plafond_par_defaut_aucune_reduction(nom, seuil, annee_debut):
    """Défaut (décision D6 du 12/11/2026) : au-delà du seuil, AUCUNE
    réduction — sorties du défaut identiques au bit à celles d'un plafond
    infini ; le bloc publie ``mode = 'avertissement'`` et les années."""
    programme = CAS[nom]
    with _seuil_plafond(seuil):
        defaut = simuler(copy.deepcopy(programme), annee_debut=annee_debut)
    with _seuil_plafond(math.inf):
        sans = simuler(copy.deepcopy(programme), annee_debut=annee_debut)
    egalite_bit_a_bit(defaut, sans, libelle=nom)
    bloc = defaut[2]['cadre']['plafond_total']
    assert bloc['mode'] == 'avertissement'
    assert bloc['annees'] and bloc['annee_impact_max'] in bloc['annees']


@pytest.mark.parametrize('annee_debut', [None, DEBUT], ids=['historique', 'cadre2028'])
@pytest.mark.parametrize('nom, seuil', CAS_PLAFOND, ids=IDS_PLAFOND)
def test_plafond_mode_reduction_comportement_v072(nom, seuil, annee_debut):
    """Mode ``'reduction'`` (posé explicitement, plus le défaut) : la réduction
    proportionnelle de v0.7.2 — trajectoire DIFFÉRENTE de celle sans plafond
    (la réduction mord), avis « plafonné » inchangé ; le bloc publie
    ``mode = 'reduction'`` et les années ; l'impact mesuré avant réduction
    dépasse le seuil."""
    programme = CAS[nom]
    with _seuil_plafond(seuil), _mode_plafond('reduction'):
        seuil_pct = C.PLAFOND_IMPACT_TOTAL_PIB * 100
        defaut = simuler(copy.deepcopy(programme), annee_debut=annee_debut)
    with _seuil_plafond(math.inf):
        sans = simuler(copy.deepcopy(programme), annee_debut=annee_debut)
    with pytest.raises(AssertionError):
        egalite_bit_a_bit(defaut, sans)            # MUTATION : la réduction mord bien
    bloc = defaut[2]['cadre']['plafond_total']
    assert bloc['mode'] == 'reduction'
    assert bloc['annees'] and bloc['annee_impact_max'] in bloc['annees']
    assert bloc['impact_max_pct_pib'] > seuil_pct
    assert any(f'plafonné à {seuil_pct:g} % du PIB' in w for w in defaut[2]['warnings'])


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
@pytest.mark.parametrize('annee_debut', [None, DEBUT], ids=['historique', 'cadre2028'])
def test_w1_8_scenarios_sous_le_seuil_identiques_dans_les_deux_modes(annee_debut, strict):
    """Les scénarios (et bases) qui ne dépassent jamais le seuil : sorties
    identiques au bit dans les deux modes ; ``annees`` vide, ``impact_max_pct_pib``
    et ``annee_impact_max`` à ``None`` (chaque base telle que le mode
    l'accepte, ``pour_le_mode``)."""
    for nom, base in BASES.items():
        base = pour_le_mode(base, annee_debut)
        with _mode_plafond('reduction'):
            reduit = simuler(copy.deepcopy(base), annee_debut=annee_debut, strict=strict)
        if reduit[2]['cadre']['plafond_total']['annees']:
            continue                                # au-delà du seuil : test ci-dessus
        with _mode_plafond('avertissement'):
            avert = simuler(copy.deepcopy(base), annee_debut=annee_debut, strict=strict)
        egalite_bit_a_bit(avert, reduit, libelle=nom)
        bloc = avert[2]['cadre']['plafond_total']
        assert bloc['mode'] == 'avertissement' and bloc['annees'] == []
        assert bloc['impact_max_pct_pib'] is None and bloc['annee_impact_max'] is None
        assert avert[2]['warnings'] == reduit[2]['warnings']


# ===========================================================================
# 7. Signature de contrat E et API (contrat § 5.1 ; W1-15, W1-17)
# ===========================================================================

# Bloc ``cadre`` figé au format v0.7.2 (réponse du moteur publié avant E).
FIXTURE_CADRE_V072 = {
    'mode': 'cadre', 'annee_debut': 2028, 'annees_droit_en_vigueur': [2026, 2027],
    'droit_en_vigueur': {'identifiant': 'budget-2026-vote', 'libelle': '…', 'source': '…',
                         'date': '2026-11-07'},
    'leviers_modifies': [], 'mesures_effectives': {}, 'rampe': None, 'atterrissage': None,
    'plafond_total': {'seuil_pct_pib': 10, 'reference': 'defauts_du_moteur', 'annees': []},
}


def _porte_la_signature_e(bloc_cadre):
    """Signature de contrat E (point tranché 2) : ``cadre.profils`` toujours
    présent (objet) et ``cadre.plafond_total.mode`` présent."""
    return (isinstance(bloc_cadre.get('profils'), dict)
            and (bloc_cadre.get('plafond_total') or {}).get('mode') in MODES_PLAFOND)


@pytest.mark.parametrize('annee_debut', [None, DEBUT], ids=['historique', 'cadre2028'])
def test_w1_15_signature_e(annee_debut):
    bloc = _sim({}, annee_debut)[2]['cadre']
    assert bloc['profils'] == {}
    assert bloc['plafond_total']['mode'] == _nouveau(C, 'PLAFOND_TOTAL_MODE')
    assert _porte_la_signature_e(bloc)
    assert not _porte_la_signature_e(FIXTURE_CADRE_V072)


@pytest.mark.parametrize('strict', ['', '1'], ids=['tolerant', 'strict'])
@pytest.mark.parametrize('annee_debut', [None, DEBUT], ids=['historique', 'cadre2028'])
@pytest.mark.parametrize('bloc', [{'x': 1}, None], ids=['bloc', 'null'])
def test_w1_17_api_levier_inconnu_422(client, monkeypatch, strict, annee_debut, bloc):
    """Non-régression : l'API refuse en 422 tout levier de premier niveau
    inconnu, dans les deux modes et les deux portes, même à ``null``."""
    monkeypatch.setenv('BUDGETLAB_STRICT', strict)
    corps = {'mesures': {INCONNU: bloc}}
    if annee_debut is not None:
        corps['annee_debut'] = annee_debut
    r = client[0].post('/simulate', json=corps)
    assert r.status_code == 422 and INCONNU in r.text, r.text


@pytest.mark.parametrize('strict', ['', '1'], ids=['tolerant', 'strict'])
def test_w1_17_api_profils_acceptes_et_signature(client, monkeypatch, strict):
    monkeypatch.setenv('BUDGETLAB_STRICT', strict)
    api, module = client
    # Dépôt parent : api.py y est l'enveloppe, qui importe l'api du moteur sous
    # le nom ``moteur_api`` ; le schéma vit dans ce dernier.
    schema = _nouveau(getattr(module, 'moteur_api', module), 'ProfilRequete')
    assert schema.model_config.get('extra') == 'forbid'
    r = api.post('/simulate', json={'mesures': {'defense': {'budget': 70}}, 'annee_debut': DEBUT,
                                    'profils': {'defense.budget': {'forme': 'annee', 'annee': 2030}}})
    assert r.status_code == 200, r.text
    corps = r.json()
    assert _porte_la_signature_e(corps['cadre'])
    profil = corps['cadre']['profils']['defense.budget']
    assert (profil['forme'], profil['annee'], profil['origine']) == ('annee', 2030, 2030)
    imp = {y['Année']: y for y in corps['measure_impacts']}
    assert imp[2030]['defense']['depenses'] == pytest.approx(70 - DEFENSE_DEFAUT_MOTEUR)
    assert imp[2029]['defense']['depenses'] == pytest.approx(DEF_REF - DEFENSE_DEFAUT_MOTEUR)
    assert corps['report']['valid'] is True and corps['report']['corrections'] == []
    sans = api.post('/simulate', json={'mesures': {}, 'annee_debut': DEBUT}).json()
    assert sans['cadre']['profils'] == {} and _porte_la_signature_e(sans['cadre'])


PROFILS_MAL_FORMES = [
    {'defense.budget': {'forme': 'plein', 'x': 1}},           # extra='forbid'
    {'defense.budget': {'forme': 'lineaire'}},                 # forme littérale
    {'defense.budget': {'forme': 'annee', 'annee': '2030'}},   # entier strict
    {'defense.budget': {'forme': 'annee', 'annee': 2030.5}},
    {'defense.budget': {'forme': 'annee', 'annee': True}},
    {'defense.budget': 'rampe'},
]


@pytest.mark.parametrize('profils', PROFILS_MAL_FORMES,
                         ids=['cle_en_trop', 'forme', 'annee_texte', 'annee_flottante',
                              'annee_booleen', 'pas_un_objet'])
def test_w1_17_api_profil_mal_forme_422_meme_en_tolerant(client, monkeypatch, profils):
    """Schéma ``ProfilRequete`` : forme refusée en 422 avant le moteur, même en
    tolérant ; témoin : le même corps avec un profil bien formé passe (200)."""
    monkeypatch.setenv('BUDGETLAB_STRICT', '')
    api = client[0]
    base = {'mesures': {'defense': {'budget': 70}}, 'annee_debut': DEBUT}
    temoin = api.post('/simulate', json={**base, 'profils': {'defense.budget': {'forme': 'rampe'}}})
    assert temoin.status_code == 200, temoin.text
    r = api.post('/simulate', json={**base, 'profils': profils})
    assert r.status_code == 422, r.text


@pytest.mark.parametrize('cas', ['hors_mandat', 'rampe_et_profils'])
def test_w1_17_api_profil_invalide_422_strict_200_tolerant(client, monkeypatch, cas):
    api = client[0]
    corps = {'mesures': {'defense': {'budget': 70}}, 'annee_debut': DEBUT}
    if cas == 'hors_mandat':
        corps['profils'] = {'defense.budget': {'forme': 'annee', 'annee': FIN + 1}}
    else:
        corps['profils'] = {'defense.budget': {'forme': 'annee', 'annee': 2030}}
        corps['rampe'] = {'annees': 3, 'leviers': ['defense.budget']}
    monkeypatch.setenv('BUDGETLAB_STRICT', '1')
    r = api.post('/simulate', json=corps)
    assert r.status_code == 422 and 'profil' in r.text, r.text
    monkeypatch.setenv('BUDGETLAB_STRICT', '')
    r = api.post('/simulate', json=corps)
    assert r.status_code == 200 and r.json()['report']['valid'] is False, r.text


@pytest.mark.parametrize('strict', ['', '1'], ids=['tolerant', 'strict'])
def test_w1_17_api_exclusion(client, monkeypatch, strict):
    """X2 par l'API : 422 en strict ; 200 en tolérant, correction lisible par le
    site dans ``report.corrections``."""
    monkeypatch.setenv('BUDGETLAB_STRICT', strict)
    r = client[0].post('/simulate', json={'mesures': X2, 'annee_debut': DEBUT})
    if strict:
        assert r.status_code == 422, r.text
        return
    assert r.status_code == 200, r.text
    corrections = r.json()['report']['corrections']
    assert [c['leviers_ignores'] for c in corrections if c['regle'] == 'X2'] == [['transferts_etranger']]
