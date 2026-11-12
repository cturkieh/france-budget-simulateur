"""v0.7.0 — corrections de la revue passe 1, une section par correction.

Chaque test verrouille le contrat retenu ; « Avant : » dit ce que faisait le
code d'avant la correction quand ce n'est pas évident. Les corrections portées par des
tests existants, adaptés en place : CRITICAL 1 (références « droit en vigueur »
au lieu du scénario ``plf_2026``, test_cadre_v070_atterrissage.py) et LOW 13
(rampe sans effet, test_cadre_v070_rampe.py). LOW 10 (commentaire du
déflateur) n'a pas de test : c'est un commentaire.
"""
import ast
import copy
import dataclasses
import importlib.util
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import budget_simulator.constants as C
import budget_simulator.engine.cadre as cadre
import budget_simulator.engine.orchestrator as orch
from budget_simulator.engine._noms_parametres import MODES_EXCLUSIFS
from budget_simulator.simulator import BudgetSimulatorV45

from cadre_harness import CAS, DROIT, NOMS, PROGRAMME_MIXTE, atterrissage, egalite_bit_a_bit, simuler

DEBUT = 2028
RACINE = Path(__file__).resolve().parent.parent
API_FILE = RACINE / 'api.py'


def _droit_reajuste():
    return cadre.CadreTemporel.preparer({}, DEBUT).etat.mesures_droit


def _decomposition(rapport, an='2026'):
    return rapport['cadre']['atterrissage']['annees'][an]['decomposition']


def _charger_modifie(tmp_path, monkeypatch, modif):
    """Charge l'atterrissage LIVRÉ, modifié par ``modif`` (fichier temporaire)."""
    contenu = json.loads(cadre.ATTERRISSAGE_PATH.read_text(encoding='utf-8'))
    modif(contenu)
    chemin = tmp_path / 'att.json'
    chemin.write_text(json.dumps(contenu), encoding='utf-8')
    monkeypatch.setattr(cadre, 'ATTERRISSAGE_PATH', chemin)
    cadre.vider_caches()
    try:
        return cadre.charger_atterrissage()
    finally:
        cadre.vider_caches()


# ---------------------------------------------------------------------------
# MEDIUM 2 — un bloc partiel hérite du droit en vigueur, paramètre par paramètre
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('levier, partiel', [
    ('sante', {'effort_prev_org': 20}),       # levier RÉAJUSTÉ (franchises 100 → 120)
    ('retraites', {'indexation': 0.8}),       # levier non réajusté
    ('education', {'enseignants': 20000}),    # lecteur latéral (effet d'offre)
    ('collectivites', {'investissement': 5}),
])
def test_m2_bloc_partiel_egal_au_bloc_complet(levier, partiel):
    """Avant : le bloc partiel REMPLAÇAIT celui du droit, les paramètres absents
    tombaient au défaut du moteur (franchises 100 % au lieu de 120 %, durée de
    cotisation par défaut au lieu de 42,5 ans)."""
    complet = {levier: {**_droit_reajuste()[levier], **partiel}}
    a = cadre.CadreTemporel.preparer({levier: partiel}, DEBUT)
    b = cadre.CadreTemporel.preparer(complet, DEBUT)
    assert a.programme == b.programme
    assert a.leviers_modifies == b.leviers_modifies == frozenset({levier})
    egalite_bit_a_bit(simuler({levier: partiel}, annee_debut=DEBUT),
                      simuler(complet, annee_debut=DEBUT), libelle=levier)


def test_m2_bloc_partiel_egal_au_droit_ne_modifie_rien():
    c = cadre.CadreTemporel.preparer({'sante': {'effort_prev_org': 10}}, DEBUT)
    assert c.leviers_modifies == frozenset()
    assert c.programme['sante'] == _droit_reajuste()['sante']


@pytest.mark.parametrize('levier, partiel', [
    ('chomage_alloc', {'duree': 12}),
    ('taxe_superprofits', {'taux': 0.1}),     # compléter par `intensite` masquerait `taux`
])
def test_m2_levier_a_modes_exclusifs_jamais_complete(levier, partiel):
    assert levier in MODES_EXCLUSIFS
    c = cadre.CadreTemporel.preparer({levier: partiel}, DEBUT)
    assert c.programme[levier] == partiel
    simuler({levier: partiel}, strict=True, annee_debut=DEBUT)   # aucun mode masqué : pas de 422


def test_m2_mode_historique_inchange():
    """Le mode historique ne compose rien : un bloc partiel y reste partiel."""
    c = cadre.CadreTemporel.preparer({'sante': {'effort_prev_org': 20}}, None)
    assert c.programme == {'sante': {'effort_prev_org': 20}}


# ---------------------------------------------------------------------------
# MEDIUM 3 — aucun réajustement sans source ; MEDIUM 4 — six grandeurs écrites
# ---------------------------------------------------------------------------

def test_m3_reajustements_sans_aucune_source_defaut_serveur(tmp_path, monkeypatch):
    """Avant : la garde ne mordait que si AU MOINS une source était donnée ; un
    bloc de réajustements sans clé ``sources_reajustements`` passait."""
    with pytest.raises(RuntimeError, match='sans source'):
        _charger_modifie(tmp_path, monkeypatch,
                         lambda d: d['annees']['2026'].pop('sources_reajustements'))


@pytest.mark.parametrize('grandeur', cadre.GRANDEURS_ATTERRISSAGE)
def test_m4_grandeur_absente_defaut_serveur(tmp_path, monkeypatch, grandeur):
    with pytest.raises(RuntimeError, match=f'absente.*{grandeur}'):
        _charger_modifie(tmp_path, monkeypatch, lambda d: d['annees']['2026'].pop(grandeur))


def test_m4_null_reste_permis(tmp_path, monkeypatch):
    a = _charger_modifie(tmp_path, monkeypatch,
                         lambda d: d['annees']['2026'].update(deflateur=None))
    assert a.annees[2026].cibles['deflateur'] is None


# ---------------------------------------------------------------------------
# MEDIUM 5 — montant sans objet : None, jamais 0,0
# ---------------------------------------------------------------------------

def test_m5_cibles_null_publient_none():
    with atterrissage({2026: {'croissance': 0.004}}):
        d = _decomposition(simuler(DROIT, annee_debut=DEBUT)[2])
    assert d['deficit']['observe_pct'] is None
    assert d['deficit']['residuel_md_eur'] is None
    assert d['deficit']['ecart_md_eur'] is None
    assert d['dette']['ajustement_stock_flux_md_eur'] is None
    assert d['deficit']['reajustements_md_eur'] == 0.0        # mesuré : aucun réajustement


def test_m5_reajustements_mesures_meme_sans_cible_de_solde():
    with atterrissage({2026: {}}, reajustements={2026: {'defense': {'budget': 58}}}):
        d = _decomposition(simuler(DROIT, annee_debut=DEBUT)[2])
    assert d['deficit']['reajustements_md_eur'] == pytest.approx(-1.0, abs=1e-9)
    assert d['deficit']['residuel_md_eur'] is None and d['deficit']['ecart_md_eur'] is None


# ---------------------------------------------------------------------------
# MEDIUM 6 — grandeurs fermées, journal complet, clé du solde = 'deficit'
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('debut', [None, DEBUT])
@pytest.mark.parametrize('grandeur', ['solde', 'pib', 'Croissance', ''])
def test_m6_grandeur_inconnue_refusee(debut, grandeur):
    """Avant : ``cible(2026, 'solde')`` rendait None (« non injectée »)."""
    with pytest.raises(ValueError, match="grandeur d'atterrissage inconnue"):
        cadre.CadreTemporel.preparer({}, debut).cible(2026, grandeur)
    sim = BudgetSimulatorV45(periods=1, mesures={}, annee_debut=debut)
    sim._journal_atterrissage = {2026: {}}
    with pytest.raises(ValueError, match="grandeur d'atterrissage inconnue"):
        sim._atterrir(2026, grandeur, 0.01)


def test_m6_journal_incomplet_leve():
    """Avant : un journal incomplet publiait ``decomposition: null`` en silence."""
    journal = simuler(DROIT, annee_debut=DEBUT)[3]._journal_atterrissage
    c = cadre.CadreTemporel.preparer({}, DEBUT)
    assert set(journal[2026]) == set(cadre.CLES_JOURNAL_ATTERRISSAGE)
    assert c.rapport_atterrissage(journal)['annees']['2026']['decomposition'] is not None
    for cle in cadre.CLES_JOURNAL_ATTERRISSAGE:
        incomplet = copy.deepcopy(journal)
        del incomplet[2026][cle]
        with pytest.raises(RuntimeError, match=f'journal incomplet.*{cle}'):
            c.rapport_atterrissage(incomplet)


def test_m6_annee_injectee_hors_horizon_sans_decomposition():
    """Horizon qui s'arrête avant l'année injectée : pas de journal, pas
    d'erreur, décomposition ``None`` (cibles publiées)."""
    _, _, rapport = BudgetSimulatorV45(periods=0, mesures={}, annee_debut=DEBUT).simulate()
    bloc = rapport['cadre']['atterrissage']['annees']['2026']
    assert bloc['decomposition'] is None and bloc['cibles']['croissance']['valeur'] == 0.004


def test_m6_cles_de_decomposition_egales_aux_grandeurs():
    d = _decomposition(simuler(DROIT, annee_debut=DEBUT)[2])
    assert tuple(d) == cadre.GRANDEURS_ATTERRISSAGE
    assert 'solde' not in d


# ---------------------------------------------------------------------------
# MEDIUM 7 — plafond de 10 % : une constante, lue par le calcul et le rapport
# ---------------------------------------------------------------------------

def test_m7_plafond_constante_nommee_valeur_inchangee():
    assert C.PLAFOND_IMPACT_TOTAL_PIB == 0.10
    source = Path(orch.__file__).read_text(encoding='utf-8')
    assert '0.10 * gdp' not in source and source.count('PLAFOND_IMPACT_TOTAL_PIB * gdp') >= 2
    bloc = cadre.CadreTemporel.preparer({}, None).rapport(None, [2030])['plafond_total']
    # Release E (chantier W1, contrat § 5.4) : le bloc publie aussi le mode du
    # plafond et l'impact maximal mesuré (sans objet ici) ; les trois champs
    # v0.7.0 sont inchangés.
    assert {k: bloc[k] for k in ('seuil_pct_pib', 'reference', 'annees')} == {
        'seuil_pct_pib': 10, 'reference': 'defauts_du_moteur', 'annees': [2030]}
    assert bloc['mode'] == C.PLAFOND_TOTAL_MODE
    assert bloc['impact_max_pct_pib'] is None and bloc['annee_impact_max'] is None


def test_m7_calcul_et_rapport_lisent_la_constante(monkeypatch):
    """Un plafond abaissé (test seulement) mord dès 2026 et le rapport publie le
    même seuil : les deux lisent la constante, aucun ne garde un littéral."""
    assert simuler(PROGRAMME_MIXTE)[2]['cadre']['plafond_total']['annees'][:1] != [2026]
    monkeypatch.setattr(orch, 'PLAFOND_IMPACT_TOTAL_PIB', 0.001)
    monkeypatch.setattr(cadre, 'PLAFOND_IMPACT_TOTAL_PIB', 0.001)
    rapport = simuler(PROGRAMME_MIXTE)[2]
    bloc = rapport['cadre']['plafond_total']
    assert bloc['seuil_pct_pib'] == 0.1 and bloc['annees'][0] == 2026
    # Avis du mode par défaut (« avertissement » depuis la décision D6 du
    # 12/11/2026 ; « plafonné à » en mode « reduction ») : même seuil lu.
    assert any('au-delà de 0.1 % du PIB' in w for w in rapport['warnings'])


# ---------------------------------------------------------------------------
# MEDIUM 8 — état du mode cadre gelé, un seul test d'activité
# ---------------------------------------------------------------------------

def test_m8_etat_cadre_gele_et_absent_en_historique():
    c = cadre.CadreTemporel.preparer({'defense': {'budget': 70}}, DEBUT)
    assert c.actif and c.mode == 'cadre' and isinstance(c.etat, cadre.EtatCadre)
    for objet, champ, valeur in ((c, 'annee_debut', 2030), (c, 'etat', None),
                                 (c.etat, 'leviers_modifies', frozenset()),
                                 (c.etat, 'mesures_droit', {})):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(objet, champ, valeur)
    h = cadre.CadreTemporel.preparer({'defense': {'budget': 70}}, None)
    assert h.etat is None and not h.actif and h.mode == 'historique'
    assert h.leviers_modifies == frozenset() and not h.compose(2030)
    assert h.rapport()['atterrissage'] is None


# ---------------------------------------------------------------------------
# MEDIUM 9 — les handlers n'écrivent que les états propres à chaque monde
# ---------------------------------------------------------------------------

_MUTATEURS = frozenset({'update', 'setdefault', 'append', 'add', 'pop', 'clear', 'extend',
                        'remove', 'discard', 'popitem', 'insert'})
# Écrit pendant un handler, commun aux mondes PAR CONSTRUCTION et sans effet sur
# le calcul : le journal de débogage (``_log_debug(self.debug_logs, …)``, jamais
# relu par le moteur), et le journal des rabots du vivier (v0.7.2, revue passe 1 :
# ``_noter_rabot_vivier``, rapport seulement, écrit pour le seul monde du programme),
# et les avis du rapport (release E, W4 : avis Z-ter de l'impôt plancher,
# ``recettes_taux._noter_avis_z_ter``, rapport seulement, jamais relu par un
# calcul, écrit pour le seul monde du programme et le mode historique).
_PARTAGES_SANS_EFFET = frozenset({'debug_logs', '_rabots_vivier', '_avis'})


def _attribut_de_self(noeud):
    """``X`` pour ``self.X``, ``self.X[...]``, ``self.X.y`` ; sinon None."""
    while isinstance(noeud, (ast.Subscript, ast.Attribute)):
        if (isinstance(noeud, ast.Attribute) and isinstance(noeud.value, ast.Name)
                and noeud.value.id == 'self'):
            return noeud.attr
        noeud = noeud.value
    return None


def test_m9_ecritures_des_handlers_statique():
    """Fermeture transitive : tout handler (budget_simulator/handlers, _seniors)
    et toute méthode ``self.m()`` qu'il appelle (simulateur, moteur). Un
    attribut écrit hors de ``ETATS_PAR_MONDE`` fuirait d'un monde à l'autre :
    l'ajouter à ``_dans_le_monde`` (et à la liste) ou le justifier ici."""
    pkg = RACINE / 'budget_simulator'
    handlers = sorted((pkg / 'handlers').glob('*.py')) + [pkg / '_seniors.py']
    autres = [pkg / 'simulator.py'] + sorted((pkg / 'engine').glob('*.py'))
    fonctions, pile = {}, []
    for f in handlers + autres:
        for n in ast.walk(ast.parse(f.read_text(encoding='utf-8'))):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fonctions.setdefault(n.name, []).append(n)
                if f in handlers:
                    pile.append(n)
    vues, ecrits = set(), {}
    while pile:
        fn = pile.pop()
        if id(fn) in vues:
            continue
        vues.add(id(fn))
        for n in ast.walk(fn):
            cibles = (n.targets if isinstance(n, (ast.Assign, ast.Delete)) else
                      [n.target] if isinstance(n, (ast.AugAssign, ast.AnnAssign)) else [])
            for c in cibles:
                for e in (c.elts if isinstance(c, ast.Tuple) else [c]):
                    if _attribut_de_self(e):
                        ecrits.setdefault(_attribut_de_self(e), set()).add(fn.name)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ('setattr', 'delattr'):
                ecrits.setdefault('<setattr/delattr>', set()).add(fn.name)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                if n.func.attr in _MUTATEURS and _attribut_de_self(n.func.value):
                    ecrits.setdefault(_attribut_de_self(n.func.value), set()).add(fn.name)
                if isinstance(n.func.value, ast.Name) and n.func.value.id == 'self':
                    pile.extend(fonctions.get(n.func.attr, []))
    assert len(vues) > 50                                   # le parcours a bien suivi les appels
    hors_mondes = {a: sorted(f) for a, f in ecrits.items() if a not in cadre.ETATS_PAR_MONDE}
    assert not hors_mondes, f"états écrits par les handlers hors des mondes : {hors_mondes}"
    assert set(ecrits) == cadre.ETATS_PAR_MONDE             # la liste n'a pas d'entrée morte


def _ecrits_pendant_les_handlers(monkeypatch, programmes, annee_debut=DEBUT):
    """Attributs de ``self`` ajoutés, retirés, réassignés ou mutés au premier
    niveau pendant un appel de handler, sur ``programmes``."""
    vrai = BudgetSimulatorV45._apply_complex_measure
    ecrits = set()

    def empreinte(v):
        return id(v), (copy.copy(v) if isinstance(v, (dict, list, set)) else None)

    def espion(self, *args, **kwargs):
        avant = {n: empreinte(v) for n, v in vars(self).items()}
        try:
            return vrai(self, *args, **kwargs)
        finally:
            apres = vars(self)
            for n in set(avant) | set(apres):
                if n not in avant or n not in apres:
                    ecrits.add(n)
                elif id(apres[n]) != avant[n][0] or (avant[n][1] is not None and avant[n][1] != apres[n]):
                    ecrits.add(n)

    monkeypatch.setattr(BudgetSimulatorV45, '_apply_complex_measure', espion)
    for mesures in programmes:
        simuler(mesures, annee_debut=annee_debut)
    monkeypatch.undo()
    return ecrits


def test_m9_ecritures_des_handlers_dynamique(monkeypatch):
    """Même garde à l'exécution, sur tous les programmes du harnais en mode
    cadre (trois mondes) : attributs ajoutés, retirés, réassignés ou mutés au
    premier niveau pendant un appel de handler."""
    ecrits = _ecrits_pendant_les_handlers(monkeypatch, [CAS[nom] for nom in NOMS])
    assert ecrits - _PARTAGES_SANS_EFFET == cadre.ETATS_PAR_MONDE


@pytest.mark.parametrize('annee_debut', [None, DEBUT], ids=['historique', 'cadre2028'])
def test_m9_avis_z_ter_seul_partage_ecrit_par_le_plancher(monkeypatch, annee_debut):
    """Release E (W4, avis Z-ter) : un impôt plancher combiné à une hausse de
    CSG fait écrire ``_avis`` PENDANT un handler (non vacuité : la garde
    dynamique ci-dessus ne voit aucun programme du harnais qui le déclenche),
    et c'est le seul état partagé ajouté ; ``_avis`` est sans effet sur le
    calcul (trajectoire identique quand on vide les avis au fil de l'eau)."""
    mesures = {'impot_plancher_patrimoine': {'taux': 0.02},
               'csg': {'taux': DROIT['csg']['taux'] + 0.008, 'progressive': 0}}
    ecrits = _ecrits_pendant_les_handlers(monkeypatch, [mesures], annee_debut)
    assert '_avis' in ecrits, sorted(ecrits)
    assert ecrits - _PARTAGES_SANS_EFFET <= cadre.ETATS_PAR_MONDE, sorted(ecrits)
    df, detail, rapport = simuler(mesures, annee_debut=annee_debut)[:3]
    assert any('impôt plancher' in w for w in rapport['warnings']), rapport['warnings']
    from budget_simulator.handlers import recettes_taux
    monkeypatch.setattr(recettes_taux, '_noter_avis_z_ter', lambda avis, monde: None)
    df_sans, detail_sans = simuler(mesures, annee_debut=annee_debut)[:2]
    assert df.equals(df_sans) and detail.equals(detail_sans)


# ---------------------------------------------------------------------------
# LOW 11 — évaluation isolée des réajustements : même politique que le chemin principal
# ---------------------------------------------------------------------------

def _solde_isole_en_echec(self, measure_id, *args, **kwargs):
    raise ZeroDivisionError(f"échec simulé ({measure_id})")


def test_l11_echec_tolerant_trace_et_trajectoire_intacte(monkeypatch, caplog):
    reference = simuler(DROIT, annee_debut=DEBUT)
    monkeypatch.setattr(BudgetSimulatorV45, '_solde_isole', _solde_isole_en_echec)
    import logging
    with caplog.at_level(logging.ERROR):
        sortie = simuler(DROIT, annee_debut=DEBUT)
    egalite_bit_a_bit(sortie, reference)                   # la trajectoire n'en dépend pas
    rapport = sortie[2]
    d = _decomposition(rapport)
    assert d['deficit']['reajustements_md_eur'] is None and d['deficit']['ecart_md_eur'] is None
    assert d['deficit']['residuel_md_eur'] == _decomposition(reference[2])['deficit']['residuel_md_eur']
    assert rapport['valid'] is False
    assert any('réajustement' in w and 'non mesuré' in w for w in rapport['warnings'])
    assert sum('non mesuré' in r.getMessage() for r in caplog.records if r.levelno == logging.ERROR) == 1


def test_l11_echec_strict_remonte(monkeypatch):
    monkeypatch.setattr(BudgetSimulatorV45, '_solde_isole', _solde_isole_en_echec)
    with pytest.raises(ZeroDivisionError) as e:
        simuler(DROIT, strict=True, annee_debut=DEBUT)
    assert any('évaluation isolée' in note for note in getattr(e.value, '__notes__', []))


# ---------------------------------------------------------------------------
# LOW 12 — toute erreur de lecture est un défaut du serveur
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('chemin_attr, charger', [
    ('DROIT_EN_VIGUEUR_PATH', 'charger_droit_en_vigueur'),
    ('ATTERRISSAGE_PATH', 'charger_atterrissage'),
])
@pytest.mark.parametrize('defaut', ['dossier', 'illisible'])
def test_l12_oserror_defaut_serveur(tmp_path, monkeypatch, chemin_attr, charger, defaut):
    """Avant : seul ``FileNotFoundError`` était enveloppé ; un dossier ou un
    fichier sans droit de lecture remontait en ``OSError`` brute."""
    if defaut == 'dossier':
        chemin = tmp_path
    else:
        chemin = tmp_path / 'f.json'
        chemin.write_text('{}', encoding='utf-8')
        chemin.chmod(0)
        try:
            chemin.read_text(encoding='utf-8')
            pytest.skip("droits de lecture non appliqués (exécution en administrateur)")
        except PermissionError:
            pass
    monkeypatch.setattr(cadre, chemin_attr, chemin)
    cadre.vider_caches()
    try:
        with pytest.raises(RuntimeError, match='défaut du serveur.*lecture impossible'):
            getattr(cadre, charger)()
    finally:
        cadre.vider_caches()
        if defaut == 'illisible':
            chemin.chmod(0o600)


# ---------------------------------------------------------------------------
# LOW 14 — les données en cache ne sont jamais altérables par un appelant
# ---------------------------------------------------------------------------

def test_l14_caches_proteges_par_copie():
    d = cadre.charger_droit_en_vigueur()
    d.mesures['defense']['budget'] = 999
    d.mesures.pop('sante')
    a = cadre.charger_atterrissage()
    a.annees[2026].reajustements['defense']['budget'] = 999
    a.annees[2026].cibles['croissance'] = None
    a.annees.clear()
    assert cadre.charger_droit_en_vigueur().mesures['defense']['budget'] == 57
    assert 'sante' in cadre.charger_droit_en_vigueur().mesures
    a2 = cadre.charger_atterrissage()
    assert a2.annees[2026].reajustements['defense']['budget'] == 58
    assert a2.annees[2026].cibles['croissance'].valeur == 0.004
    df = simuler({}, annee_debut=DEBUT)[0].set_index('Année')
    assert df.at[2026, 'Croissance %'] == pytest.approx(0.4, abs=1e-12)


# ---------------------------------------------------------------------------
# AJOUT 15 — mesures effectives exposées
# ---------------------------------------------------------------------------

def test_a15_mesures_effectives_statu_quo_droit_reajuste():
    m = simuler({}, annee_debut=DEBUT)[2]['cadre']['mesures_effectives']
    assert m['defense'] == {'budget': 58}
    assert m['sante']['franchise_participation_taux'] == 120
    assert m['is_exceptionnel_tge'] == {'montant': 6.8}
    assert m == _droit_reajuste()
    assert m['fraude_fiscale'] == DROIT['fraude_fiscale']              # non réajusté : voté


def test_a15_mesures_effectives_programme_par_dessus_le_droit():
    rapport = simuler({'defense': {'budget': 60}, 'sante': {'effort_prev_org': 20}},
                      annee_debut=DEBUT)[2]
    m = rapport['cadre']['mesures_effectives']
    assert m['defense'] == {'budget': 60}
    assert m['sante'] == {**_droit_reajuste()['sante'], 'effort_prev_org': 20}
    assert m['is_exceptionnel_tge'] == {'montant': 6.8}
    assert simuler({'defense': {'budget': 60}})[2]['cadre']['mesures_effectives'] is None


def test_a15_mesures_effectives_par_l_api(monkeypatch):
    spec = importlib.util.spec_from_file_location('api_revue_passe1_v070', API_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    client = TestClient(module.app, raise_server_exceptions=False)
    monkeypatch.setenv('BUDGETLAB_STRICT', '')
    corps = client.post('/simulate', json={'mesures': {}, 'annee_debut': DEBUT}).json()
    assert corps['cadre']['mesures_effectives']['defense'] == {'budget': 58}
    corps = client.post('/simulate', json={'mesures': {}}).json()
    assert corps['cadre']['mesures_effectives'] is None
