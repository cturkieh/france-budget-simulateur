"""Release E — chantier W2 : dépenses publiques, prestations aux ménages, flux vers l'étranger.

Tests-propriétés écrits AVANT le code (contrat du dépôt parent,
``docs/plans/contrat-curseurs-release-E-2026-11.md`` : § 1.1, § 1.2-1 à 1.2-3,
§ 1.3, § 4.1 règles C, O, P, R, § 6.1 et § 6.3, tests W2-1 à W2-16).

Trois leviers :

- ``depenses_publiques`` (``credits_etat``, ``ondam``, ``transferts_capital``) :
  formule ASTEVAL posée FINALE par le socle ; ce fichier la verrouille ;
- ``transferts_etranger`` (``montant``) : formule finale du socle, multiplicateur
  intérieur nul par ``MESURES_HORS_DEMANDE_INTERIEURE`` (socle) ;
- ``prestations_menages`` (``solidarite``, ``pensions``) : handler
  ``_apply_prestations_menages``, dont le CORPS est le seul code de production du
  chantier W2 (``handlers/transferts_menages.py``).

État attendu sur le socle (``dba7321``) : ROUGES, pour la raison « squelette »
(``levier_non_livre`` : « levier non encore implémenté … chantier W2 »), tous les
tests qui exercent ``prestations_menages`` hors de ses valeurs neutres ; VERTS les
tests des deux formules (livrées par le socle) et les tests par mutation dont le
détecteur ne dépend pas du handler W2.

Toutes les valeurs attendues sont DÉRIVÉES : des constantes nommées du socle
(``constants.py`` : ``GINI_SOLIDARITE_PAR_MD``, ``GINI_PENSIONS_PAR_MD``,
``DEBT_DRAG_COEFF``…), du registre (``policy_measures.json`` : bornes, neutres,
défaut de ``defense``), du droit en vigueur réajusté lu par le moteur, ou d'une
simulation de référence (égalités « avec / sans »). Les montants d'essai (5, 10…
Md€) sont des ENTRÉES, choisies dans les domaines du registre.

Deux familles de tests portent sur des mécanismes du chantier W1 (profils
temporels ; plafond de 10 % en avertissement) : depuis l'intégration de la
release E, ce sont des tests ordinaires, sans marqueur. Le plafond est en mode
« avertissement » par défaut (décision D6 du mainteneur du 12/11/2026) : le test
de la contre-épreuve pose le mode « reduction » explicitement.

Détecteur anti-double-compte « à état identique » (``_rejouer_sans``) : pendant
une simulation, chaque année, ``apply_measures`` est rejouée sur un CLONE profond
du moteur (mêmes entrées macro, mêmes traqueurs) d'où le levier étudié est
retiré ; les impacts de tous les autres leviers et les masses nominales de toutes
les catégories de dépense doivent être identiques au bit. Une macro qui diverge
les années suivantes (effet légitime du levier) n'entre donc pas dans la
comparaison : seul un levier qui LIT ou ÉCRIT ce que voient les autres la fait
échouer. Chaque règle est accompagnée d'un test par MUTATION qui prouve que le
détecteur rougit quand l'effet est compté deux fois.
"""
import copy
import inspect
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

import budget_simulator.constants as C
import budget_simulator.handlers.transferts_menages as mod_tm
from budget_simulator import EntreeInvalide
from budget_simulator.constants import HANDLER_FAILED_KEY
from budget_simulator.handlers._types import CANAUX_MENAGES, canaux_menages
from budget_simulator.simulator import BudgetSimulatorV45, FiscalMultipliers

from cadre_harness import DROIT, DROIT_REAJUSTE, PROGRAMME_MIXTE, bases_g1, droit_sans_valeurs_datees, pleine_precision

RACINE = Path(__file__).absolute().parent.parent
sys.path.insert(0, str(RACINE / 'tests' / 'snapshots'))
from run_scenarios_full import SCENARIOS  # noqa: E402

REGISTRE = {m['id']: m for m in json.loads(
    (RACINE / 'policy_measures.json').read_text(encoding='utf-8'))['mesures']}

LEVIERS_W2 = ('depenses_publiques', 'prestations_menages', 'transferts_etranger')
FORMULES_W2 = ('depenses_publiques', 'transferts_etranger')
# (levier, paramètre) des six curseurs du chantier, dans l'ordre du registre.
PARAMS_W2 = [(levier, param) for levier in LEVIERS_W2
             for param in REGISTRE[levier]['parametres']]
IDS_PARAMS = [f'{l}.{p}' for l, p in PARAMS_W2]

MODES = {'historique': None, 'cadre2028': C.ANNEE_PREMIER_BUDGET_MANDAT}
PORTES = {'tolerant': False, 'strict': True}
PERIODES = 10
# Dernière année simulée : POLICY_START_YEAR + PERIODES − 1.
DERNIERE_ANNEE = C.POLICY_START_YEAR + PERIODES - 1

# Entrées macro des appels directs du handler : celles de l'année de base du
# moteur (le handler ne doit en lire aucune, règle R-IDX).
MACRO_BASE = dict(gdp=C.PIB_BASE_2025_MD_EUR, inflation=C.INFLATION_BASE,
                  unemployment=C.CHOMAGE_BASE)

# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------

def _borne(levier, param):
    spec = REGISTRE[levier]['parametres'][param]
    return spec['min'], spec['max']


def _essai(levier, param, signe=+1):
    """Montant d'essai DANS le domaine du registre : la moitié de la plus petite
    des deux bornes en valeur absolue (symétrique : +x et −x sont admis)."""
    bas, haut = _borne(levier, param)
    return signe * min(abs(bas), abs(haut)) / 2


def _debut(annee_debut):
    return annee_debut or C.POLICY_START_YEAR


def _annees_application(annee_debut):
    return list(range(_debut(annee_debut), DERNIERE_ANNEE + 1))


def _canon(x):
    """Forme comparable AU BIT (float.hex) d'une sortie du moteur."""
    if isinstance(x, dict):
        return {str(k): _canon(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_canon(v) for v in x]
    if isinstance(x, float):
        return x.hex()
    return x


def _simuler_brut(mesures, annee_debut=None, strict=False, periods=PERIODES, **kwargs):
    """(df, détail, rapport, sim) en PLEINE PRÉCISION (``round`` neutralisé)."""
    with pleine_precision() as mp:
        mp.setenv('BUDGETLAB_STRICT', '1' if strict else '')
        sim = BudgetSimulatorV45(periods=periods, mesures=copy.deepcopy(mesures),
                                 annee_debut=annee_debut, **kwargs)
        df, det, rapport = sim.simulate()
    return df, det, rapport, sim


_CACHE = {}


def _sim(mesures, annee_debut=None, strict=False, periods=PERIODES):
    """``_simuler_brut`` mis en cache (sorties en lecture seule)."""
    cle = (json.dumps(mesures, sort_keys=True), annee_debut, strict, periods)
    if cle not in _CACHE:
        _CACHE[cle] = _simuler_brut(mesures, annee_debut, strict, periods)
    return _CACHE[cle]


def _impacts(rapport):
    """{année: {levier: impact}} du rapport."""
    return {a['Année']: a for a in rapport['measure_impacts_by_year']}


def _impact_applique(rapport, levier, annee):
    """Impact publié du levier l'année ``annee``. Échoue en nommant la cause si
    le levier est en échec (squelette non livré, porte) ou absent."""
    ligne = _impacts(rapport).get(annee, {})
    impact = ligne.get(levier)
    assert impact is not None, f"{levier} absent des impacts publiés en {annee}"
    assert not impact.get(HANDLER_FAILED_KEY), (
        f"{levier} en échec en {annee} : {impact.get('erreur')}")
    return impact


def _code_sans_textes(objet):
    """Code source de ``objet`` SANS commentaires ni chaînes (docstrings
    comprises) : une garde de source ne doit lire que le code exécuté."""
    import io
    import tokenize
    source = inspect.getsource(objet)
    jetons = tokenize.generate_tokens(io.StringIO(source).readline)
    return ''.join(j.string for j in jetons
                   if j.type not in (tokenize.COMMENT, tokenize.STRING, tokenize.NL,
                                     tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT))


def _solde_primaire(det, annee):
    d = det.set_index('Année')
    return d.at[annee, 'Recettes_Totales'] - d.at[annee, 'Dépenses_Totales']


# --- Handler appelé directement ---------------------------------------------

def _handler_prestations():
    """(sim, appel) : ``appel(params, annee=…, **macro)`` appelle
    ``_apply_prestations_menages`` sur un moteur neuf (traqueurs vierges)."""
    sim = BudgetSimulatorV45(periods=1)
    sim._reset_state()
    mesure = sim.measure_registry['prestations_menages']

    def appel(params, annee=C.ANNEE_PREMIER_BUDGET_MANDAT, **macro):
        m = {**MACRO_BASE, **macro}
        return sim._apply_prestations_menages(mesure, dict(params), annee, m['gdp'],
                                              m['inflation'], m['unemployment'])
    return sim, appel


def _gini_attendu(solidarite=0.0, pensions=0.0):
    """Contrat § 1.2-2 : effet ponctuel = constante signée × montant, aucun
    signe ajouté (règle d'écriture du § 1.1)."""
    return C.GINI_SOLIDARITE_PAR_MD * solidarite + C.GINI_PENSIONS_PAR_MD * pensions


# --- Détecteur « à état identique » ------------------------------------------

def _rejouer_sans(mesures, retire, annee_debut=None, strict=False):
    """Simule ``mesures`` en rejouant, chaque année, ``apply_measures`` sur un
    clone profond du moteur d'où ``retire`` est absent (mêmes entrées macro,
    mêmes traqueurs). Rend ``(ecarts, rapport)`` ; ``ecarts`` = liste de
    ``(année, objet, avec, sans)`` où ``objet`` est un levier (ses impacts) ou
    ``masse:<catégorie>`` (masse nominale de la catégorie après les mesures)."""
    ecarts = []
    original = BudgetSimulatorV45.apply_measures

    def espion(self, year, spending, revenues, gdp, inflation, unemployment):
        if getattr(self, '_clone_w2', False):
            return original(self, year, spending, revenues, gdp, inflation, unemployment)
        # L'interpréteur ASTEVAL n'est pas copiable ; partagé (sa table de
        # symboles est réécrite à chaque formule).
        clone = copy.deepcopy(self, memo={id(self.aeval): self.aeval})
        clone._clone_w2 = True
        clone.mesures = {l: b for l, b in self.mesures.items() if l != retire}
        if clone._mondes is not None:
            # Mode cadre : le monde « programme » lit les mêmes mesures.
            clone._mondes['programme'].mesures = clone.mesures
        _, _, sans = clone.apply_measures(year, spending, revenues, gdp, inflation, unemployment)
        sortie = original(self, year, spending, revenues, gdp, inflation, unemployment)
        avec = sortie[2]
        for levier in sorted(set(avec) | set(sans)):
            if levier != retire and _canon(avec.get(levier)) != _canon(sans.get(levier)):
                ecarts.append((year, levier, avec.get(levier), sans.get(levier)))
        for cat in self.spending_categories_base:
            m_avec, m_sans = self.masse_categorie_nominale(cat), clone.masse_categorie_nominale(cat)
            if m_avec != m_sans:
                ecarts.append((year, f'masse:{cat}', m_avec, m_sans))
        return sortie

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(BudgetSimulatorV45, 'apply_measures', espion)
        _, _, rapport, _ = _simuler_brut(mesures, annee_debut, strict)
    return ecarts, rapport


def _mutant_lecteur(nom_handler, levier, param):
    """Mutation « double compte » : le handler existant ``nom_handler`` compte EN
    PLUS, dans ses dépenses, le montant ``levier.param`` (il lit le nouveau
    levier dans ``self.mesures``)."""
    original = getattr(BudgetSimulatorV45, nom_handler)

    def mutant(self, measure, params, year, gdp, inflation, unemployment):
        dep, rec, impacts = original(self, measure, params, year, gdp, inflation, unemployment)
        relu = float((self.mesures.get(levier) or {}).get(param, 0.0))
        impacts = dict(impacts)
        impacts['depenses'] = impacts.get('depenses', 0.0) + relu
        return dep + relu, rec, impacts
    return mutant


def _mutant_ecrivain(categorie, param):
    """Mutation « double compte » du handler W2 : il ajoute AUSSI son montant à
    la masse de base d'une catégorie (que d'autres leviers indexent)."""
    original = BudgetSimulatorV45._apply_prestations_menages

    def mutant(self, measure, params, year, gdp, inflation, unemployment):
        sortie = original(self, measure, params, year, gdp, inflation, unemployment)
        self.spending_categories_base[categorie] += float(params.get(param, 0.0))
        return sortie
    return mutant


# ---------------------------------------------------------------------------
# 0. Livraison : le levier n'est plus un squelette
# ---------------------------------------------------------------------------

def test_w2_livre_prestations_menages_hors_des_leviers_non_livres():
    """Le chantier W2 retire SON levier de ``LEVIERS_NON_LIVRES`` en livrant le
    corps (garde du socle : la liste nomme exactement les squelettes)."""
    assert 'prestations_menages' not in C.LEVIERS_NON_LIVRES
    code = _code_sans_textes(mod_tm.PrestationsMenagesMixin._apply_prestations_menages)
    assert 'levier_non_livre(' not in code


def test_w2_formules_du_socle_non_listees():
    """Les deux formules sont livrées par le socle : jamais listées."""
    assert not set(FORMULES_W2) & C.LEVIERS_NON_LIVRES
    for levier in FORMULES_W2:
        assert REGISTRE[levier]['type'] == 'formule'
        assert levier not in BudgetSimulatorV45(periods=1).measure_handlers


# ---------------------------------------------------------------------------
# 1. W2-1 — G1 (neutralité au bit) et G2 (absent ≡ neutre ≡ droit)
# ---------------------------------------------------------------------------

def _formes_neutres(levier):
    """Écritures d'un bloc NEUTRE : valeurs du registre ; entiers ; un seul
    paramètre écrit −0,0 (égal au neutre 0). Le bloc vide ``{}`` est exclu : il
    porte un avis documenté (PARAM_BLOC_VIDE), trajectoire inchangée."""
    neutres = dict(C.NEUTRES_RELEASE_E[levier])
    premier = next(iter(neutres))
    return {
        'registre': neutres,
        'entiers': {p: int(v) for p, v in neutres.items()},
        'moins_zero': {premier: -0.0},
    }


CAS_G1 = [(levier, forme) for levier in LEVIERS_W2 for forme in _formes_neutres(levier)]
BASES_G1 = {'statu_quo': {}, 'droit_en_vigueur': DROIT, 'programme_mixte': PROGRAMME_MIXTE,
            **SCENARIOS}


@pytest.mark.parametrize('strict', list(PORTES.values()), ids=list(PORTES))
@pytest.mark.parametrize('annee_debut', list(MODES.values()), ids=list(MODES))
@pytest.mark.parametrize('levier, forme', CAS_G1, ids=[f'{l}-{f}' for l, f in CAS_G1])
def test_w2_1_g1_neutralite_au_bit(levier, forme, annee_debut, strict):
    """G1 : pour chaque base (statu quo, droit en vigueur, programme mixte et
    les 10 scénarios publiés quand ``scenarios.json`` est présent), chaque mode
    et chaque porte, ajouter le levier à une valeur neutre ne change NI la
    trajectoire, NI le détail, NI le rapport (``float.hex``)."""
    if not SCENARIOS:
        assert len(BASES_G1) == 3  # dépôt public seul
    bloc = _formes_neutres(levier)[forme]
    # Release de paramètres P : une base qui ENCODE le levier n'est pas une base
    # de G1 (y poser le neutre retirerait sa mesure, cadre_harness.bases_g1).
    for nom, base in bases_g1(BASES_G1, levier, annee_debut).items():
        ref_df, ref_det, ref_rap, _ = _sim(base, annee_debut, strict)
        df, det, rap, _ = _sim({**base, levier: bloc}, annee_debut, strict)
        assert df.equals(ref_df), (nom, levier, forme, 'trajectoire')
        assert det.equals(ref_det), (nom, levier, forme, 'détail')
        assert _canon(rap) == _canon(ref_rap), (nom, levier, forme, 'rapport')


@pytest.mark.parametrize('levier', LEVIERS_W2)
def test_w2_1_g2_absent_du_droit_neutres_nuls(levier):
    """G2 : levier absent du droit en vigueur (« absent du droit = zéro ») ;
    neutre de chaque paramètre = 0 (montant en plus ou en moins), lu dans le
    registre ; en mode cadre, programme vide ≡ droit réajusté ≡ droit réajusté
    + levier au neutre, au bit."""
    assert levier not in DROIT
    assert set(C.NEUTRES_RELEASE_E[levier]) == set(REGISTRE[levier]['parametres'])
    assert all(v == 0 for v in C.NEUTRES_RELEASE_E[levier].values())
    debut = MODES['cadre2028']
    vide = _sim({}, debut)
    droit = _sim(DROIT_REAJUSTE, debut)
    neutre = _sim({**DROIT_REAJUSTE, levier: dict(C.NEUTRES_RELEASE_E[levier])}, debut)
    for sortie in (droit, neutre):
        assert sortie[0].equals(vide[0]) and sortie[1].equals(vide[1])


# ---------------------------------------------------------------------------
# 2. Contrat du handler W2 (appel direct) : W2-12, retour anticipé, R-IDX
# ---------------------------------------------------------------------------

def test_w2_12_constantes_lues_par_le_handler_identite_d_objet():
    """Le module du handler lit les constantes SIGNÉES du socle par leur nom
    (même objet que ``constants.py``), jamais une copie ni un littéral."""
    assert mod_tm.GINI_SOLIDARITE_PAR_MD is C.GINI_SOLIDARITE_PAR_MD
    assert mod_tm.GINI_PENSIONS_PAR_MD is C.GINI_PENSIONS_PAR_MD


def test_w2_12_derivation_des_coefficients_recalculee():
    """§ 1.3, recalculé ici : solidarité = −règle « par Md€ d'allocations » ;
    pensions = Gini CUMULÉ d'un gel total de l'indexation sur le mandat rapporté
    à l'économie de fin de mandat, au signe d'une hausse."""
    n = C.HORIZON_MANDAT_ANNEES
    assert C.GINI_SOLIDARITE_PAR_MD == -C.GINI_ALLOC_PAR_MD_EUR
    assert C.GINI_PENSIONS_PAR_MD == (
        -C.RETRAITES_GINI_PAR_POINT_DESINDEXATION * (1 + C.RETRAITES_GINI_RESIDU_FLUX * (n - 1))
        / (C.MASSE_RETRAITES_2025_MD_EUR * (1 - (1 + C.INFLATION_STRUCTURELLE) ** -n)))


@pytest.mark.parametrize('params', [
    {'solidarite': 12.5}, {'solidarite': -20.0}, {'pensions': 7.5}, {'pensions': -16.0},
    {'solidarite': -9.0, 'pensions': 4.0},
], ids=['sol+', 'sol-', 'pen+', 'pen-', 'mixte'])
def test_w2_12_appel_direct_budget_menages_gini(params):
    """W2-12 (P1) et § 1.2-2 : Δdép = solidarite + pensions, Δrec = 0 ;
    ``menages`` = canal ``prestations`` au montant du budget, les quatre autres
    canaux à zéro ; Gini = constante signée × montant ; compétitivité et
    chômage nuls (absents ou zéro)."""
    s, p = params.get('solidarite', 0.0), params.get('pensions', 0.0)
    _, appel = _handler_prestations()
    dep, rec, impacts = appel(params)
    assert dep == s + p and rec == 0
    assert impacts.get('depenses', dep) == dep
    assert impacts['menages'] == canaux_menages(prestations=dep)
    assert set(impacts['menages']) == set(CANAUX_MENAGES)
    assert impacts['gini'] == pytest.approx(_gini_attendu(s, p), abs=1e-15)
    assert impacts.get('competitivite', 0.0) == 0.0
    assert impacts.get('chomage', 0.0) == 0.0


def test_w2_12_mutation_le_handler_lit_la_constante(monkeypatch):
    """Par MUTATION : doubler la constante du module double l'effet Gini (le
    handler lit le nom à l'appel, pas une copie locale)."""
    _, appel = _handler_prestations()
    ref = appel({'solidarite': 10.0, 'pensions': -5.0})[2]['gini']
    monkeypatch.setattr(mod_tm, 'GINI_SOLIDARITE_PAR_MD', 2 * C.GINI_SOLIDARITE_PAR_MD)
    monkeypatch.setattr(mod_tm, 'GINI_PENSIONS_PAR_MD', 2 * C.GINI_PENSIONS_PAR_MD)
    _, appel = _handler_prestations()
    mut = appel({'solidarite': 10.0, 'pensions': -5.0})[2]['gini']
    assert ref != 0 and mut == pytest.approx(2 * ref, rel=1e-12)


def test_w2_retour_anticipe_au_neutre_sans_cle_ponctuelle():
    """Règle commune du § 1.1 : valeurs neutres ET aucune clé ponctuelle du
    levier dans le traqueur → ``(0.0, 0.0, {})`` avant tout calcul, traqueur
    intact (neutralité au bit G1 en mode historique)."""
    sim, appel = _handler_prestations()
    for neutre in (dict(C.NEUTRES_RELEASE_E['prestations_menages']), {}, {'solidarite': 0}):
        assert appel(neutre) == (0.0, 0.0, {})
    assert 'prestations_menages' not in sim._measure_params_tracker


def test_w2_cle_ponctuelle_prestations_menages():
    """§ 1.2-2 : l'effet Gini passe par ``_effet_ponctuel`` sous la clé
    ``prestations_menages`` (mode incrément), jamais par ``_one_time_level`` ;
    la fonction d'effet est une ``def`` (une lambda polluerait l'extracteur des
    noms admis, leçon v0.7.0)."""
    sim, appel = _handler_prestations()
    appel({'solidarite': 5.0})
    assert 'prestations_menages' in sim._measure_params_tracker
    code = _code_sans_textes(mod_tm.PrestationsMenagesMixin._apply_prestations_menages)
    assert 'self._effet_ponctuel(' in code
    assert '_one_time_level' not in code and 'lambda' not in code


@pytest.mark.parametrize('params', [{'solidarite': 8.0}, {'pensions': -6.0}],
                         ids=['solidarite', 'pensions'])
def test_w2_14_ridx_handler_independant_de_la_macro(params):
    """R-IDX (§ 1.1) au niveau du handler : le montant est CONSTANT en euros
    courants, sans indexation — même Δdép et mêmes canaux quels que soient
    l'année, le PIB, l'inflation et le chômage reçus."""
    x = sum(params.values())
    for annee, gdp, inflation, chomage in [
            (C.POLICY_START_YEAR, C.PIB_BASE_2025_MD_EUR, C.INFLATION_BASE, C.CHOMAGE_BASE),
            (C.ANNEE_FIN_MANDAT, 2 * C.PIB_BASE_2025_MD_EUR, 4 * C.INFLATION_BASE, 2 * C.CHOMAGE_BASE)]:
        _, appel = _handler_prestations()
        dep, rec, impacts = appel(params, annee=annee, gdp=gdp, inflation=inflation,
                                  unemployment=chomage)
        assert dep == x and rec == 0
        assert impacts['menages'] == canaux_menages(prestations=x)


def test_w2_ne_lit_ni_n_ecrit_les_masses_ni_les_autres_leviers():
    """§ 1.2-2 : le handler ne lit ni n'écrit la masse ``minima_sociaux``,
    ``retraites``, ni ``self.mesures`` (ASU comprise : additif, D9). Garde de
    source (code hors commentaires et chaînes) ; la preuve par le comportement
    est le détecteur « à état identique » des sections 7 et 8."""
    code = _code_sans_textes(mod_tm)
    for interdit in ('masse_categorie_nominale', 'spending_categories_base', '_spending_factors',
                     'self.mesures', 'asu_is_active', 'asu_phasing'):
        assert interdit not in code, interdit


# ---------------------------------------------------------------------------
# 3. W2-2 — G8 et G8-retour (effets ponctuels en incrément)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('param, x', [('solidarite', 10.0), ('pensions', -10.0)])
def test_w2_2_g8_rampe_somme_des_increments_egale_au_palier(param, x):
    """G8 au niveau du handler, sur la rampe que posera le cadre (niveaux
    x·k/n, dernière année = valeur exacte) : chaque incrément Gini vaut la
    constante × le pas, leur somme l'effet du palier (à 1e-12)."""
    n = C.HORIZON_MANDAT_ANNEES
    _, appel = _handler_prestations()
    increments = []
    for k in range(1, n + 1):
        niveau = x if k == n else x * k / n
        increments.append(appel({param: niveau}, annee=C.ANNEE_PREMIER_BUDGET_MANDAT + k - 1)[2]['gini'])
    palier = _gini_attendu(**{param: x})
    assert sum(increments) == pytest.approx(palier, abs=1e-12)
    for k, inc in enumerate(increments, start=1):
        pas = (x if k == n else x * k / n) - (x * (k - 1) / n)
        assert inc == pytest.approx(_gini_attendu(**{param: pas}), abs=1e-12)


@pytest.mark.parametrize('param, x', [('solidarite', 10.0), ('pensions', -10.0)])
def test_w2_2_g8_retour_une_seule_annee(param, x):
    """G8-retour au niveau du handler : x une année, neutre la suivante → la
    seconde année rend l'effet (incrément opposé), Σ = 0 à 1e-12, budget et
    canaux nuls ; la troisième année (toujours neutre) n'émet plus rien."""
    _, appel = _handler_prestations()
    annee = C.ANNEE_PREMIER_BUDGET_MANDAT
    premier = appel({param: x}, annee=annee)
    retour = appel({param: 0.0}, annee=annee + 1)
    suite = appel({param: 0.0}, annee=annee + 2)
    assert premier[2]['gini'] == pytest.approx(_gini_attendu(**{param: x}), abs=1e-15)
    assert retour[0] == 0 and retour[1] == 0
    assert premier[2]['gini'] + retour[2].get('gini', 0.0) == pytest.approx(0.0, abs=1e-12)
    assert all(v == 0 for v in retour[2].get('menages', {}).values())
    assert suite[0] == 0 and suite[1] == 0 and suite[2].get('gini', 0.0) == 0.0


def _gini_par_annee(rapport, levier):
    return {a: (imp.get(levier) or {}).get('gini', 0.0) for a, imp in _impacts(rapport).items()}


@pytest.mark.parametrize('annee_debut', list(MODES.values()), ids=list(MODES))
@pytest.mark.parametrize('param, x', [('solidarite', 10.0), ('pensions', -10.0)])
def test_w2_2_g8_emis_une_fois_rien_avant_le_debut(param, x, annee_debut):
    """G8 en simulation complète (profil « plein ») : effet Gini émis UNE fois,
    la première année d'application, égal à la constante × montant ; zéro les
    autres années ; le levier n'apparaît pas avant ``annee_debut``."""
    rapport = _sim({'prestations_menages': {param: x}}, annee_debut)[2]
    debut = _debut(annee_debut)
    gini = _gini_par_annee(rapport, 'prestations_menages')
    for annee in _annees_application(annee_debut):
        _impact_applique(rapport, 'prestations_menages', annee)
        attendu = _gini_attendu(**{param: x}) if annee == debut else 0.0
        assert gini[annee] == pytest.approx(attendu, abs=1e-15), annee
    for annee in range(C.POLICY_START_YEAR, debut):
        assert 'prestations_menages' not in _impacts(rapport)[annee], annee


def test_w2_2_g8_mutation_effet_reemis_chaque_annee(monkeypatch):
    """Par MUTATION (double compte dans le temps) : un handler qui réémettrait
    l'effet de NIVEAU chaque année au lieu de l'incrément ferait rougir G8."""
    x = 10.0
    rapport = _sim({'prestations_menages': {'solidarite': x}})[2]
    _impact_applique(rapport, 'prestations_menages', C.POLICY_START_YEAR)
    original = BudgetSimulatorV45._apply_prestations_menages

    def mutant(self, measure, params, year, gdp, inflation, unemployment):
        dep, rec, impacts = original(self, measure, params, year, gdp, inflation, unemployment)
        return dep, rec, {**impacts, 'gini': _gini_attendu(params.get('solidarite', 0.0),
                                                           params.get('pensions', 0.0))}
    monkeypatch.setattr(BudgetSimulatorV45, '_apply_prestations_menages', mutant)
    mutant_rap = _simuler_brut({'prestations_menages': {'solidarite': x}})[2]
    somme = sum(_gini_par_annee(mutant_rap, 'prestations_menages').values())
    assert somme != pytest.approx(_gini_attendu(solidarite=x), abs=1e-12)


@pytest.mark.integration
@pytest.mark.parametrize('param, x', [('solidarite', 10.0), ('pensions', -10.0)])
def test_w2_2_g8_profil_rampe_simulation(param, x):
    """G8 sous profil « rampe » (W1) : niveaux x·k/n de 2028 à 2031, valeur
    EXACTE dès 2032 (``==``), Σ des incréments Gini = effet du palier."""
    debut = MODES['cadre2028']
    n = C.ANNEE_FIN_MANDAT - debut + 1
    rapport = _simuler_brut({'prestations_menages': {param: x}}, debut,
                            profils={f'prestations_menages.{param}': {'forme': 'rampe'}})[2]
    for annee in _annees_application(debut):
        dep = _impact_applique(rapport, 'prestations_menages', annee)['depenses']
        if annee >= C.ANNEE_FIN_MANDAT:
            assert dep == x, annee
        else:
            assert dep == pytest.approx(x * (annee - debut + 1) / n, abs=1e-12), annee
    somme = sum(_gini_par_annee(rapport, 'prestations_menages').values())
    assert somme == pytest.approx(_gini_attendu(**{param: x}), abs=1e-12)


@pytest.mark.integration
@pytest.mark.parametrize('param, x', [('solidarite', 10.0), ('pensions', -10.0)])
def test_w2_2_g8_retour_profil_une_seule_annee_simulation(param, x):
    """G8-retour sous profil « une seule année » (W1) : montant l'année
    choisie seulement ; Σ des incréments Gini sur l'horizon = 0 à 1e-12 ; effet
    direct sur le solde revenu à zéro l'année suivante."""
    debut, choisie = MODES['cadre2028'], MODES['cadre2028'] + 2
    rapport = _simuler_brut({'prestations_menages': {param: x}}, debut,
                            profils={f'prestations_menages.{param}': {'forme': 'annee', 'annee': choisie}})[2]
    for annee in _annees_application(debut):
        dep = ((_impacts(rapport)[annee].get('prestations_menages') or {}).get('depenses', 0.0))
        assert dep == (x if annee == choisie else 0.0), annee
    assert sum(_gini_par_annee(rapport, 'prestations_menages').values()) == pytest.approx(0.0, abs=1e-12)


# ---------------------------------------------------------------------------
# 4. W2-2 — G4 (domaine), G5 (signe, monotonie), G6 (symétrie), G7 (canaux)
# ---------------------------------------------------------------------------

def _hors_domaine(levier, param):
    bas, haut = _borne(levier, param)
    marge = (haut - bas) / 4
    return [(bas - marge, bas), (haut + marge, haut)]


@pytest.mark.parametrize('levier, param', PARAMS_W2, ids=IDS_PARAMS)
def test_w2_2_g4_hors_bornes_tolerant_ecretage_trace_et_applique(levier, param):
    """G4 tolérant : une valeur hors du domaine du registre est écrêtée à la
    borne, l'écrêtage est tracé (``report.leviers_ecretes``, motif
    ``domaine``) et le levier APPLIQUE la borne (effet budgétaire = borne)."""
    bas, haut = _borne(levier, param)
    for demande, borne in _hors_domaine(levier, param):
        rapport = _sim({levier: {param: demande}})[2]
        assert rapport['valid'] is False
        trace = [e for e in rapport['leviers_ecretes'] if e['levier'] == f'{levier}.{param}']
        assert trace and trace[0]['motif'] == 'domaine', rapport['leviers_ecretes']
        assert trace[0]['applique'] == borne and trace[0]['borne'] == [bas, haut]
        for annee in _annees_application(None):
            assert _impact_applique(rapport, levier, annee)['depenses'] == borne, (demande, annee)


def test_w2_2_g4_borne_sourcee_des_transferts_vers_l_etranger():
    """Borne basse SOURCÉE (D1, jamais relevée) : −(prélèvement sur recettes
    au profit de l'UE + crédits de la mission « Aide publique au
    développement », loi de finances initiale pour 2026), soit −32,009 ; une coupe au-delà est écrêtée à
    cette valeur exacte, tracée."""
    borne = -(C.PSR_UE_2026_MD + C.APD_MISSION_2026_MD)
    assert _borne('transferts_etranger', 'montant')[0] == pytest.approx(borne, abs=1e-9)
    rapport = _sim({'transferts_etranger': {'montant': 2 * borne}})[2]
    trace = [e for e in rapport['leviers_ecretes'] if e['levier'] == 'transferts_etranger.montant']
    assert trace and trace[0]['applique'] == pytest.approx(borne, abs=1e-9)
    assert _impact_applique(rapport, 'transferts_etranger', C.POLICY_START_YEAR)['depenses'] \
        == pytest.approx(borne, abs=1e-9)


@pytest.mark.parametrize('annee_debut', list(MODES.values()), ids=list(MODES))
@pytest.mark.parametrize('levier, param', PARAMS_W2, ids=IDS_PARAMS)
def test_w2_2_g4_hors_bornes_et_non_finis_strict_entree_invalide(levier, param, annee_debut):
    """G4 strict (porte des valeurs, avant le handler) : hors bornes, NaN, ±inf
    → ``ExceptionGroup`` d'``EntreeInvalide`` (422 côté API)."""
    valeurs = [d for d, _ in _hors_domaine(levier, param)] + [math.nan, math.inf, -math.inf]
    for v in valeurs:
        with pytest.raises(ExceptionGroup) as info:
            _simuler_brut({levier: {param: v}}, annee_debut, strict=True)
        feuilles = info.value.exceptions
        assert feuilles and all(isinstance(e, EntreeInvalide) for e in feuilles), (v, feuilles)
        assert any(f'{levier}.{param}' in str(e) for e in feuilles), (v, feuilles)


@pytest.mark.parametrize('levier, param', PARAMS_W2, ids=IDS_PARAMS)
def test_w2_2_g4_non_finis_tolerant_retires_effet_nul(levier, param):
    """G4 tolérant : NaN et ±inf sont retirés (correction tracée,
    ``report.valid = false``), le paramètre retombe sur son neutre : trajectoire
    du statu quo au bit."""
    ref_df = _sim({})[0]
    for v in (math.nan, math.inf, -math.inf):
        df, _, rapport, _ = _simuler_brut({levier: {param: v}})
        assert rapport['valid'] is False
        assert any(f'{levier}.{param}' in w for w in rapport['warnings']), rapport['warnings']
        assert df.equals(ref_df), v


@pytest.fixture(scope='module')
def client_api():
    import importlib.util
    from fastapi.testclient import TestClient
    spec = importlib.util.spec_from_file_location('api_release_e_w2', RACINE / 'api.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return TestClient(module.app, raise_server_exceptions=False)


@pytest.mark.parametrize('levier, param', PARAMS_W2, ids=IDS_PARAMS)
def test_w2_2_g4_api_422_strict_et_ecretage_tolerant(client_api, monkeypatch, levier, param):
    """G4 par l'API : hors bornes → 422 en strict ; 200 en tolérant, écrêtage
    publié et levier appliqué à la borne."""
    (demande, borne), _ = _hors_domaine(levier, param)
    corps = {'mesures': {levier: {param: demande}}, 'periods': 2}
    monkeypatch.setenv('BUDGETLAB_STRICT', '1')
    assert client_api.post('/simulate', json=corps).status_code == 422
    monkeypatch.setenv('BUDGETLAB_STRICT', '')
    reponse = client_api.post('/simulate', json=corps)
    assert reponse.status_code == 200
    corps_rep = reponse.json()
    assert [e['applique'] for e in corps_rep['report']['leviers_ecretes']
            if e['levier'] == f'{levier}.{param}'] == [borne]
    annee = next(a for a in corps_rep['measure_impacts'] if a['Année'] == C.POLICY_START_YEAR)
    impact = annee.get(levier) or {}
    assert not impact.get(HANDLER_FAILED_KEY), impact.get('erreur')
    assert impact.get('depenses') == borne


def _grille(levier, param):
    """Grille du domaine (11 points réguliers, bornes comprises), hors des
    montants sous le seuil de publication du rapport (|x| ≤ 0,1 Md€)."""
    bas, haut = _borne(levier, param)
    return [x for x in np.linspace(bas, haut, 11).tolist() if abs(x) > 0.1]


@pytest.mark.parametrize('annee_debut', list(MODES.values()), ids=list(MODES))
@pytest.mark.parametrize('levier, param', PARAMS_W2, ids=IDS_PARAMS)
def test_w2_2_g5_signe_et_monotonie_sur_tout_le_domaine(levier, param, annee_debut):
    """G5 : sur tout le domaine, l'effet direct sur le solde PRIMAIRE de l'année
    d'entrée vaut −x (une dépense en plus dégrade le solde) ; strictement
    décroissant en x ; aucun point de retournement."""
    debut = _debut(annee_debut)
    ref = _solde_primaire(_sim({}, annee_debut)[1], debut)
    effets = []
    for x in _grille(levier, param):
        _, det, rapport, _ = _sim({levier: {param: x}}, annee_debut)
        assert _impact_applique(rapport, levier, debut)['depenses'] == x
        effet = _solde_primaire(det, debut) - ref
        assert effet == pytest.approx(-x, abs=1e-9), x
        effets.append(effet)
    assert all(a > b for a, b in zip(effets, effets[1:])), effets


@pytest.mark.parametrize('annee_debut', list(MODES.values()), ids=list(MODES))
@pytest.mark.parametrize('levier, param', PARAMS_W2, ids=IDS_PARAMS)
def test_w2_2_g6_symetrie(levier, param, annee_debut):
    """G6 : +x et −x donnent des effets directs opposés (budget, canaux
    ménages, Gini), chaque année d'application."""
    x = _essai(levier, param)
    plus = _sim({levier: {param: x}}, annee_debut)[2]
    moins = _sim({levier: {param: -x}}, annee_debut)[2]
    for annee in _annees_application(annee_debut):
        ip, im = _impact_applique(plus, levier, annee), _impact_applique(moins, levier, annee)
        assert ip['depenses'] == -im['depenses'] == x and ip['recettes'] == im['recettes'] == 0
        assert ip.get('gini', 0.0) == pytest.approx(-im.get('gini', 0.0), abs=1e-15)
        assert set(ip.get('menages', {})) == set(im.get('menages', {}))
        for canal, v in ip.get('menages', {}).items():
            assert v == -im['menages'][canal], (annee, canal)


@pytest.mark.parametrize('annee_debut', list(MODES.values()), ids=list(MODES))
@pytest.mark.parametrize('levier, param', PARAMS_W2, ids=IDS_PARAMS)
def test_w2_2_g7_contrat_des_canaux_menages(levier, param, annee_debut):
    """G7 : ``prestations_menages`` émet ``menages`` = canal ``prestations`` au
    montant du budget chaque année où un euro bouge ; les deux formules
    n'émettent AUCUN canal ménages (arbitrage 2 du moteur ; § 1.2-1 et 1.2-3)."""
    x = _essai(levier, param, signe=-1)
    rapport = _sim({levier: {param: x}}, annee_debut)[2]
    for annee in _annees_application(annee_debut):
        impact = _impact_applique(rapport, levier, annee)
        if levier == 'prestations_menages':
            assert impact['menages'] == canaux_menages(prestations=impact['depenses']), annee
        else:
            assert 'menages' not in impact, (annee, impact)


# ---------------------------------------------------------------------------
# 5. W2-2 — G10' (plafond de 10 %), G11 (signe Gini), G12 / W2-14 (R-IDX)
# ---------------------------------------------------------------------------

def _abaisser_seuil_plafond(monkeypatch, seuil):
    """Pose ``PLAFOND_IMPACT_TOTAL_PIB`` à ``seuil`` dans ``constants`` et dans
    CHAQUE module du moteur qui a importé le nom (le calcul peut changer de
    module avec W1 : la mutation suit le nom, pas un fichier)."""
    for nom, module in list(sys.modules.items()):
        if (nom == 'budget_simulator' or nom.startswith('budget_simulator.')) \
                and hasattr(module, 'PLAFOND_IMPACT_TOTAL_PIB'):
            monkeypatch.setattr(module, 'PLAFOND_IMPACT_TOTAL_PIB', seuil)


def _poser_mode_plafond(monkeypatch, mode):
    """Pose ``PLAFOND_TOTAL_MODE`` à ``mode`` dans chaque module du moteur qui
    porte le nom (même règle que ``_abaisser_seuil_plafond``)."""
    touches = [module for nom, module in list(sys.modules.items())
               if (nom == 'budget_simulator' or nom.startswith('budget_simulator.'))
               and hasattr(module, 'PLAFOND_TOTAL_MODE')]
    assert touches, "PLAFOND_TOTAL_MODE absent du moteur"
    for module in touches:
        monkeypatch.setattr(module, 'PLAFOND_TOTAL_MODE', mode)


def _seuil_plafond_qui_mord(x):
    """Seuil (part du PIB) que |x| Md€ dépasse chaque année de l'horizon et que
    le statu quo (total nul en mode historique) ne dépasse jamais : la moitié de
    |x| rapportée au PIB de base (le PIB nominal reste sous 2 × PIB 2025)."""
    return abs(x) / (2 * C.PIB_BASE_2025_MD_EUR)


@pytest.mark.parametrize('levier, param', PARAMS_W2, ids=IDS_PARAMS)
def test_w2_2_g10_appartenance_au_total_du_plafond(monkeypatch, levier, param):
    """G10' : le levier ENTRE dans le total mesuré contre le seuil du plafond
    (|ΣΔdép| + |ΣΔrec|). Seuil abaissé (constante du moteur) : le statu quo ne
    le franchit jamais, le levier seul le franchit chaque année."""
    x = _essai(levier, param)
    _abaisser_seuil_plafond(monkeypatch, _seuil_plafond_qui_mord(x))
    assert _simuler_brut({})[2]['cadre']['plafond_total']['annees'] == []
    rapport = _simuler_brut({levier: {param: x}})[2]
    _impact_applique(rapport, levier, C.POLICY_START_YEAR)
    assert rapport['cadre']['plafond_total']['annees'] == _annees_application(None)


@pytest.mark.integration
@pytest.mark.parametrize('levier, param', PARAMS_W2, ids=IDS_PARAMS)
def test_w2_2_g10_sans_aucune_reduction(monkeypatch, levier, param):
    """G10' (W1, D6) : en mode « avertissement » — le défaut depuis la
    décision du mainteneur du 12/11/2026 —, au-delà du seuil, AUCUNE réduction :
    le levier garde son montant exact chaque année. Contre-épreuve : le mode
    « reduction », posé explicitement, réduit le levier."""
    x = _essai(levier, param)
    _abaisser_seuil_plafond(monkeypatch, _seuil_plafond_qui_mord(x))
    rapport = _simuler_brut({levier: {param: x}})[2]
    assert rapport['cadre']['plafond_total']['mode'] == C.PLAFOND_TOTAL_MODE == 'avertissement'
    for annee in _annees_application(None):
        assert _impact_applique(rapport, levier, annee)['depenses'] == x, annee
    _poser_mode_plafond(monkeypatch, 'reduction')
    reduit = _simuler_brut({levier: {param: x}})[2]
    assert reduit['cadre']['plafond_total']['mode'] == 'reduction'
    for annee in _annees_application(None):
        assert abs(_impact_applique(reduit, levier, annee)['depenses']) < abs(x), annee


def _gini_conforme(gini, montant):
    """G11 : une BAISSE de prestation augmente le Gini, une hausse le baisse."""
    return (gini > 0) if montant < 0 else (gini < 0)


@pytest.mark.parametrize('param', ['solidarite', 'pensions'])
@pytest.mark.parametrize('signe', [-1, +1], ids=['baisse', 'hausse'])
def test_w2_2_g11_signe_de_l_effet_gini(param, signe):
    """G11 : baisse de prestation → Gini > 0 ; valeur exacte = constante signée
    × montant (aucun signe ajouté) ; même sens sur la colonne Gini publiée
    (fin d'horizon, deux modes)."""
    x = _essai('prestations_menages', param, signe)
    _, appel = _handler_prestations()
    gini = appel({param: x})[2]['gini']
    assert _gini_conforme(gini, x)
    assert gini == pytest.approx(_gini_attendu(**{param: x}), abs=1e-15)
    for annee_debut in MODES.values():
        ref = _sim({}, annee_debut)[0].set_index('Année').at[DERNIERE_ANNEE, 'Gini']
        df, _, rapport, _ = _sim({'prestations_menages': {param: x}}, annee_debut)
        _impact_applique(rapport, 'prestations_menages', _debut(annee_debut))
        publie = df.set_index('Année').at[DERNIERE_ANNEE, 'Gini']
        assert _gini_conforme(publie - ref, x), (annee_debut, publie, ref)


def test_w2_2_g11_mutation_signe_inverse(monkeypatch):
    """Par MUTATION (R-1) : un signe inversé dans la constante lue par le
    handler fait rougir G11."""
    _, appel = _handler_prestations()
    assert _gini_conforme(appel({'solidarite': -10.0})[2]['gini'], -10.0)
    monkeypatch.setattr(mod_tm, 'GINI_SOLIDARITE_PAR_MD', -C.GINI_SOLIDARITE_PAR_MD)
    _, appel = _handler_prestations()
    assert not _gini_conforme(appel({'solidarite': -10.0})[2]['gini'], -10.0)


def _ecarts_ridx(rapport, levier, x, annee_debut):
    """Années d'application où Δdép du levier ≠ x exactement (R-IDX)."""
    return [(a, _impact_applique(rapport, levier, a)['depenses'])
            for a in _annees_application(annee_debut)
            if _impact_applique(rapport, levier, a)['depenses'] != x]


@pytest.mark.parametrize('strict', list(PORTES.values()), ids=list(PORTES))
@pytest.mark.parametrize('annee_debut', list(MODES.values()), ids=list(MODES))
@pytest.mark.parametrize('signe', [-1, +1], ids=['moins', 'plus'])
@pytest.mark.parametrize('levier, param', PARAMS_W2, ids=IDS_PARAMS)
def test_w2_14_g12_montant_constant_chaque_annee(levier, param, signe, annee_debut, strict):
    """W2-14 / G12 (R-IDX) : Δdép_t = x EXACTEMENT chaque année d'application
    (2026-2035 en historique, 2028-2035 en cadre), dans les deux portes ; même
    rapport Δ_t / Δ_origine = 1 pour tous les montants en Md€ ; aucun budget
    avant le début ; ``report.valid`` vrai."""
    x = _essai(levier, param, signe)
    rapport = _sim({levier: {param: x}}, annee_debut, strict)[2]
    assert _ecarts_ridx(rapport, levier, x, annee_debut) == []
    for annee in range(C.POLICY_START_YEAR, _debut(annee_debut)):
        assert levier not in _impacts(rapport)[annee]
    assert rapport['valid'] is True, rapport['warnings']


def test_w2_14_mutation_montant_indexe(monkeypatch):
    """Par MUTATION : un handler qui indexerait son montant (indice de prix des
    dépenses) ferait rougir R-IDX."""
    x = 10.0
    rapport = _sim({'prestations_menages': {'solidarite': x}})[2]
    assert _ecarts_ridx(rapport, 'prestations_menages', x, None) == []
    original = BudgetSimulatorV45._apply_prestations_menages

    def mutant(self, measure, params, year, gdp, inflation, unemployment):
        dep, rec, impacts = original(self, measure, params, year, gdp, inflation, unemployment)
        indice = self.indice_prix_depenses()
        return dep * indice, rec, {**impacts, 'depenses': dep * indice,
                                   'menages': canaux_menages(prestations=dep * indice)}
    monkeypatch.setattr(BudgetSimulatorV45, '_apply_prestations_menages', mutant)
    rapport = _simuler_brut({'prestations_menages': {'solidarite': x}})[2]
    assert _ecarts_ridx(rapport, 'prestations_menages', x, None) != []


# ---------------------------------------------------------------------------
# 6. W2-3 (F1) — la formule de depenses_publiques
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('annee_debut', list(MODES.values()), ids=list(MODES))
def test_w2_3_f1_somme_exacte_sans_canal(annee_debut):
    """F1 : Δdép = credits_etat + ondam + transferts_capital EXACTEMENT chaque
    année (montants dyadiques : somme exacte dans tout ordre) ; aucune clé
    ``gini``, ``menages`` ni ``competitivite``."""
    bloc = {'credits_etat': 3.25, 'ondam': -1.5, 'transferts_capital': 0.75}
    rapport = _sim({'depenses_publiques': bloc}, annee_debut)[2]
    for annee in _annees_application(annee_debut):
        impact = _impact_applique(rapport, 'depenses_publiques', annee)
        assert impact['depenses'] == sum(bloc.values()) and impact['recettes'] == 0
        assert not {'gini', 'menages', 'competitivite', 'chomage'} & set(impact), impact


def test_w2_3_f1_mutation_formule_comptee_deux_fois(monkeypatch):
    """Par MUTATION : une formule qui compterait deux fois un paramètre fait
    rougir F1."""
    bloc = {'credits_etat': 3.25, 'ondam': -1.5, 'transferts_capital': 0.75}
    original = BudgetSimulatorV45.__init__

    def init_mutant(self, *args, **kwargs):
        original(self, *args, **kwargs)
        mesure = dict(self.measure_registry['depenses_publiques'])
        mesure['formule'] = mesure['formule'] + " + p.get('ondam', 0)"
        self.measure_registry = {**self.measure_registry, 'depenses_publiques': mesure}
    monkeypatch.setattr(BudgetSimulatorV45, '__init__', init_mutant)
    rapport = _simuler_brut({'depenses_publiques': bloc})[2]
    impact = _impact_applique(rapport, 'depenses_publiques', C.POLICY_START_YEAR)
    assert impact['depenses'] != sum(bloc.values())


# ---------------------------------------------------------------------------
# 7. Règles O et C (W2-4, W2-5) — détecteur « à état identique »
# ---------------------------------------------------------------------------

def _assert_applique_chaque_annee(rapport, levier, attendu, annee_debut):
    for annee in _annees_application(annee_debut):
        assert _impact_applique(rapport, levier, annee)['depenses'] == attendu, annee


@pytest.mark.parametrize('annee_debut', list(MODES.values()), ids=list(MODES))
@pytest.mark.parametrize('ondam', [5.0, -8.0])
def test_w2_4_f2_regle_o_sante_et_effectifs_independants_de_l_ondam(ondam, annee_debut):
    """W2-4 (F2, règle O) : les sorties des handlers ``sante`` (efforts
    d'efficience, prévention, franchises) et ``fonction_publique`` (postes)
    sont identiques au bit avec ou sans ``ondam``, à état identique ; l'Ondam
    est appliqué en entier (priorité au levier dédié, aucun recouvrement)."""
    programme = {'sante': PROGRAMME_MIXTE['sante'],
                 'fonction_publique': PROGRAMME_MIXTE['fonction_publique'],
                 'depenses_publiques': {'ondam': ondam}}
    ecarts, rapport = _rejouer_sans(programme, 'depenses_publiques', annee_debut)
    assert ecarts == []
    _assert_applique_chaque_annee(rapport, 'depenses_publiques', ondam, annee_debut)


def test_w2_4_mutation_sante_recompte_l_ondam(monkeypatch):
    """Par MUTATION : un handler ``sante`` qui recompterait l'Ondam du nouveau
    levier dans ses dépenses fait rougir le détecteur de W2-4."""
    programme = {'sante': PROGRAMME_MIXTE['sante'], 'depenses_publiques': {'ondam': 5.0}}
    assert _rejouer_sans(programme, 'depenses_publiques')[0] == []
    monkeypatch.setattr(BudgetSimulatorV45, '_apply_sante',
                        _mutant_lecteur('_apply_sante', 'depenses_publiques', 'ondam'))
    ecarts = _rejouer_sans(programme, 'depenses_publiques')[0]
    assert ecarts and {e[1] for e in ecarts} == {'sante'}


# Leviers dédiés de la règle C (§ 4.1) : valeurs d'essai non neutres, dans
# leurs domaines du registre.
LEVIERS_DEDIES_C = {
    'fonction_publique': {'effectifs': -50000, 'point_indice': 1.0},
    'fonction_publique_reforme': {'fusion_agences': 5, 'digitalisation': 5},
    'collectivites': {'dotation': 110, 'investissement': 5},
    'rabot_uniforme': {'taux_reduction': 0.03, 'exclure_dette': 1, 'exclure_defense': 1,
                       'exclure_ue': 1},
    'defense': {'budget': 60},
    'education': {'budget': 70, 'enseignants': 10000, 'salaires': 2},
    'recherche_publique': {'budget': 15},
    'subventions_tge': {'montant': 30},
    'immigration': {'ame': 0.8, 'integration': 1.0},
    'transition_ecologique': {'investissement': 10, 'renovation': 5},
    'transferts_etranger': {'montant': -5.0},
    'prestations_menages': {'solidarite': -10.0, 'pensions': 5.0},
}


@pytest.mark.parametrize('annee_debut', list(MODES.values()), ids=list(MODES))
@pytest.mark.parametrize('dedie', list(LEVIERS_DEDIES_C))
def test_w2_5_f3_regle_c_leviers_dedies_independants_des_credits(dedie, annee_debut):
    """W2-5 (F3, règle C) : chaque levier dédié (postes, agences,
    collectivités, rabot, défense, éducation, recherche, subventions, AME,
    rénovation, étranger, prestations) a des impacts identiques au bit avec ou
    sans ``credits_etat`` à état identique, et tous deux s'appliquent
    (additivité, aucun levier en échec)."""
    credits = -20.0
    programme = {dedie: LEVIERS_DEDIES_C[dedie], 'depenses_publiques': {'credits_etat': credits}}
    ecarts, rapport = _rejouer_sans(programme, 'depenses_publiques', annee_debut)
    assert ecarts == []
    _assert_applique_chaque_annee(rapport, 'depenses_publiques', credits, annee_debut)
    for annee in _annees_application(annee_debut):
        impact = _impacts(rapport)[annee].get(dedie)
        assert not (impact or {}).get(HANDLER_FAILED_KEY), (dedie, annee, (impact or {}).get('erreur'))


def test_w2_5_mutation_effectifs_recomptent_les_credits(monkeypatch):
    """Par MUTATION : un handler ``fonction_publique`` qui recompterait les
    crédits ministériels fait rougir le détecteur de W2-5."""
    programme = {'fonction_publique': LEVIERS_DEDIES_C['fonction_publique'],
                 'depenses_publiques': {'credits_etat': -20.0}}
    assert _rejouer_sans(programme, 'depenses_publiques')[0] == []
    monkeypatch.setattr(BudgetSimulatorV45, '_apply_fonction_publique',
                        _mutant_lecteur('_apply_fonction_publique', 'depenses_publiques',
                                        'credits_etat'))
    ecarts = _rejouer_sans(programme, 'depenses_publiques')[0]
    assert ecarts and {e[1] for e in ecarts} == {'fonction_publique'}


@pytest.mark.parametrize('annee_debut', list(MODES.values()), ids=list(MODES))
def test_w2_x2_rabot_hors_ue_additif_aux_transferts_vers_l_etranger(annee_debut):
    """Règle X2, moitié sans exclusion (l'exclusion elle-même est W1-6) : avec
    ``exclure_ue = 1``, le rabot ne touche pas la contribution européenne ; ses
    impacts sont identiques avec ou sans ``transferts_etranger``, et les deux
    s'appliquent."""
    programme = {'rabot_uniforme': LEVIERS_DEDIES_C['rabot_uniforme'],
                 'transferts_etranger': {'montant': -5.0}}
    ecarts, rapport = _rejouer_sans(programme, 'transferts_etranger', annee_debut)
    assert ecarts == []
    _assert_applique_chaque_annee(rapport, 'transferts_etranger', -5.0, annee_debut)


# ---------------------------------------------------------------------------
# 8. Règles P et R (W2-6 à W2-10) — prestations, ASU, SMIC, chômage, retraites
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('annee_debut', list(MODES.values()), ids=list(MODES))
@pytest.mark.parametrize('solidarite', [-20.0, 10.0, 30.0])
def test_w2_6_p2_indexation_et_masse_des_minima_independantes(solidarite, annee_debut):
    """W2-6 (P2) : masse ``minima_sociaux`` (et toutes les masses) et impacts de
    ``prestations_indexation`` identiques au bit quel que soit ``solidarite``, à
    état identique ; la solidarité est appliquée en entier."""
    programme = {'prestations_indexation': {'taux_indexation': 0.5},
                 'prestations_menages': {'solidarite': solidarite}}
    ecarts, rapport = _rejouer_sans(programme, 'prestations_menages', annee_debut)
    _assert_applique_chaque_annee(rapport, 'prestations_menages', solidarite, annee_debut)
    assert ecarts == []


@pytest.mark.parametrize('annee_debut', list(MODES.values()), ids=list(MODES))
@pytest.mark.parametrize('solidarite', [-15.0, 12.0])
def test_w2_7_p3_d9_sous_asu_solidarite_appliquee_en_entier(solidarite, annee_debut):
    """W2-7 (P3, décision D9) : ASU active → ``solidarite`` appliquée en ENTIER
    (canal ``prestations`` compris), ``prestations_indexation`` neutralisée
    comme avant (Δdép nul), impacts de l'ASU et de l'indexation identiques avec
    ou sans la solidarité."""
    programme = {'asu': {'asu_activation': 1, 'asu_plafonnement': 0.6},
                 'prestations_indexation': {'taux_indexation': 0.5},
                 'prestations_menages': {'solidarite': solidarite}}
    ecarts, rapport = _rejouer_sans(programme, 'prestations_menages', annee_debut)
    for annee in _annees_application(annee_debut):
        impact = _impact_applique(rapport, 'prestations_menages', annee)
        assert impact['depenses'] == solidarite
        assert impact['menages'] == canaux_menages(prestations=solidarite)
        indexation = _impacts(rapport)[annee].get('prestations_indexation') or {}
        assert indexation.get('depenses', 0) == 0, (annee, indexation)
    assert ecarts == []


@pytest.mark.parametrize('annee_debut', list(MODES.values()), ids=list(MODES))
@pytest.mark.parametrize('voisin, bloc', [
    ('smic', {'montant_brut': 1900}),
    ('chomage_alloc', {'montant': 30.0, 'duree': 15}),
], ids=['w2_8_p4_smic', 'w2_9_chomage_alloc'])
def test_w2_8_w2_9_smic_et_chomage_independants(voisin, bloc, annee_debut):
    """W2-8 (P4) et W2-9 : impacts de ``smic`` et de ``chomage_alloc`` (budget
    des allocations en Md€, son propre curseur) identiques au bit avec ou sans
    ``solidarite``, à état identique."""
    programme = {voisin: bloc, 'prestations_menages': {'solidarite': -10.0}}
    ecarts, rapport = _rejouer_sans(programme, 'prestations_menages', annee_debut)
    _assert_applique_chaque_annee(rapport, 'prestations_menages', -10.0, annee_debut)
    assert ecarts == []


@pytest.mark.parametrize('annee_debut', list(MODES.values()), ids=list(MODES))
@pytest.mark.parametrize('pensions', [-10.0, 5.0])
def test_w2_10_regle_r_retraites_et_masse_independantes(pensions, annee_debut):
    """W2-10 (règle R) : impacts de ``retraites`` (indexation, âge) et masse
    ``retraites`` identiques au bit avec ou sans ``pensions``, à état
    identique ; les pensions en montant s'appliquent en entier."""
    programme = {'retraites': {'indexation': 0.8, 'age_depart': 64.0},
                 'prestations_menages': {'pensions': pensions}}
    ecarts, rapport = _rejouer_sans(programme, 'prestations_menages', annee_debut)
    _assert_applique_chaque_annee(rapport, 'prestations_menages', pensions, annee_debut)
    assert ecarts == []


@pytest.mark.parametrize('nom_handler, param', [
    ('_apply_prestations_indexation', 'solidarite'),
    ('_apply_smic', 'solidarite'),
    ('_apply_chomage_alloc', 'solidarite'),
    ('_apply_retraites', 'pensions'),
])
def test_w2_6_a_10_mutation_levier_existant_recompte_le_montant(monkeypatch, nom_handler, param):
    """Par MUTATION (règles P et R) : un levier existant qui recompterait le
    montant de ``prestations_menages`` fait rougir le détecteur."""
    voisin = {'_apply_prestations_indexation': ('prestations_indexation', {'taux_indexation': 0.5}),
              '_apply_smic': ('smic', {'montant_brut': 1900}),
              '_apply_chomage_alloc': ('chomage_alloc', {'montant': 30.0}),
              '_apply_retraites': ('retraites', {'indexation': 0.8})}[nom_handler]
    programme = {voisin[0]: voisin[1], 'prestations_menages': {param: -10.0}}
    monkeypatch.setattr(BudgetSimulatorV45, nom_handler,
                        _mutant_lecteur(nom_handler, 'prestations_menages', param))
    ecarts = _rejouer_sans(programme, 'prestations_menages')[0]
    assert ecarts and voisin[0] in {e[1] for e in ecarts}


@pytest.mark.parametrize('categorie, param, voisin', [
    ('minima_sociaux', 'solidarite', ('prestations_indexation', {'taux_indexation': 0.5})),
    ('retraites', 'pensions', ('retraites', {'indexation': 0.8})),
])
def test_w2_6_w2_10_mutation_handler_w2_ecrit_la_masse(monkeypatch, categorie, param, voisin):
    """Par MUTATION (règles P et R, sens inverse) : un handler W2 qui ajouterait
    AUSSI son montant à la masse ``minima_sociaux`` ou ``retraites`` (que
    l'indexation des prestations et des pensions revalorise) fait rougir le
    détecteur (masse et levier voisin)."""
    programme = {voisin[0]: voisin[1], 'prestations_menages': {param: -10.0}}
    ecarts, rapport = _rejouer_sans(programme, 'prestations_menages')
    _assert_applique_chaque_annee(rapport, 'prestations_menages', -10.0, None)
    assert ecarts == []
    monkeypatch.setattr(BudgetSimulatorV45, '_apply_prestations_menages',
                        _mutant_ecrivain(categorie, param))
    ecarts = _rejouer_sans(programme, 'prestations_menages')[0]
    assert f'masse:{categorie}' in {e[1] for e in ecarts}


# ---------------------------------------------------------------------------
# 9. W2-11 (F4) — credits_etat ≡ défense
# ---------------------------------------------------------------------------

D0_HISTORIQUE = REGISTRE['defense']['parametres']['budget']['valeur_defaut']
D0_CADRE = DROIT_REAJUSTE['defense']['budget']
# Colonne de JOURNAL (orchestrateur, « Multiplicateur pour logs ») : Σ(−k·Δ) /
# Σ|Δ| des impulsions de l'année, levier par levier — un rapport pondéré par
# l'effort BRUT, qui dépend donc de la DÉCOMPOSITION entre leviers et non de
# l'économie simulée. Son numérateur est comparé à part.
COLONNE_JOURNAL = 'Multiplicateur'


def _effet_impulsions_par_annee(sim):
    """Σ(−k·Δ) des impulsions stockées, par rang d'année (numérateur de la
    colonne ``Multiplicateur``)."""
    effet = {}
    for (annee, *_), (delta, k, _p) in sim._fiscal_impulses.items():
        effet[annee] = effet.get(annee, 0.0) - k * delta
    return effet


def _ecart_max(sortie_a, sortie_b, exclure=()):
    pire = (0.0, None, None)
    for cadre_a, cadre_b in ((sortie_a[0], sortie_b[0]), (sortie_a[1], sortie_b[1])):
        a, b = cadre_a.set_index('Année'), cadre_b.set_index('Année')
        for col in a.columns:
            if col in exclure:
                continue
            for annee in a.index:
                ecart = abs(float(a.at[annee, col]) - float(b.at[annee, col]))
                if ecart > pire[0]:
                    pire = (ecart, col, annee)
    return pire


@pytest.mark.parametrize('annee_debut, d0, x', [
    (None, D0_HISTORIQUE, +10.0), (None, D0_HISTORIQUE, -5.0),
    (MODES['cadre2028'], D0_CADRE, +5.0), (MODES['cadre2028'], D0_CADRE, +10.0),
], ids=['historique+10', 'historique-5', 'cadre+5', 'cadre+10'])
def test_w2_11_f4_credits_equivalents_a_la_defense(annee_debut, d0, x):
    """W2-11 (F4) : ``credits_etat = x`` ≡ ``defense.budget = d₀ + x`` à 1e-9 sur
    toutes les colonnes. ``d₀`` est LU : défaut du moteur au registre en mode
    historique (50) ; droit en vigueur RÉAJUSTÉ au début en mode cadre (58,
    ``droit_en_vigueur.json`` + réajustement de l'atterrissage, lu par le
    moteur). Mode cadre : la colonne de journal ``Multiplicateur`` est exclue
    (rapport pondéré par l'effort brut, sensible à la seule décomposition entre
    leviers) et remplacée par son numérateur, Σ(−k·Δ) par année, égal à 1e-12."""
    credits = _sim({'depenses_publiques': {'credits_etat': x}}, annee_debut)
    defense = _sim({'defense': {'budget': d0 + x}}, annee_debut)
    exclure = (COLONNE_JOURNAL,) if annee_debut else ()
    ecart, col, annee = _ecart_max(credits, defense, exclure)
    assert ecart <= 1e-9, (col, annee, ecart)
    effet_c, effet_d = _effet_impulsions_par_annee(credits[3]), _effet_impulsions_par_annee(defense[3])
    assert set(effet_c) == set(effet_d)
    for an in effet_c:
        assert effet_c[an] == pytest.approx(effet_d[an], abs=1e-12), an


def test_w2_11_f4_ecart_documente_coupe_en_mode_cadre():
    """W2-11, x < 0 en mode cadre : l'équivalence n'est PAS requise. Les
    impulsions se lisent levier par levier contre le défaut du moteur : une
    coupe de ``credits_etat`` (de 0 à −5) est une CONSOLIDATION, alors qu'une
    défense ramenée de 58 à 53 reste au-dessus de son défaut (50) : une
    EXPANSION moindre. Ce test documente l'écart et sa cause."""
    debut, x = MODES['cadre2028'], -5.0
    credits = _sim({'depenses_publiques': {'credits_etat': x}}, debut)
    defense = _sim({'defense': {'budget': D0_CADRE + x}}, debut)
    assert D0_CADRE + x > D0_HISTORIQUE
    # Clés du stock d'impulsions : (rang de l'année depuis l'année de base,
    # levier, flux, sens) ; l'impulsion du budget de t est stockée en t+1.
    rang = debut - (C.POLICY_START_YEAR - 1)
    sens_c = {s for (a, m, _c, s) in credits[3]._fiscal_impulses if m == 'depenses_publiques' and a > rang}
    sens_d = {s for (a, m, _c, s) in defense[3]._fiscal_impulses if m == 'defense' and a == rang + 1}
    assert sens_c == {'consolidation'} and sens_d == {'expansion'}
    assert _ecart_max(credits, defense, (COLONNE_JOURNAL,))[0] > 1e-6


# ---------------------------------------------------------------------------
# 10. W2-13 (P5) — multiplicateur des transferts dans les deux sens
# ---------------------------------------------------------------------------

def test_w2_13_p5_transfert_et_profil():
    """W2-13 : ``prestations_menages`` ∈ ``TRANSFER_MEASURES``, profil de
    décroissance des transferts."""
    assert 'prestations_menages' in BudgetSimulatorV45.TRANSFER_MEASURES
    assert (BudgetSimulatorV45._get_decay_profile('prestations_menages')
            == BudgetSimulatorV45.DECAY_PROFILE_TRANSFERS)


def _compositions_multiplicateur(mesures, levier='prestations_menages'):
    """Simule ``mesures`` en notant (sens, composition) de chaque demande de
    multiplicateur pour ``levier``."""
    vus = []
    original = FiscalMultipliers.get_multiplier

    def espion(self, effort_type, composition, economic_state, year, measure_id=None):
        if measure_id == levier:
            vus.append((effort_type, dict(composition)))
        return original(self, effort_type, composition, economic_state, year, measure_id)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(FiscalMultipliers, 'get_multiplier', espion)
        sortie = _simuler_brut(mesures)
    return vus, sortie


@pytest.mark.parametrize('x, sens', [(-10.0, 'consolidation'), (10.0, 'expansion')],
                         ids=['coupe', 'hausse'])
def test_w2_13_p5_multiplicateur_des_transferts_dans_les_deux_sens(x, sens):
    """W2-13 : une coupe comme une hausse de prestation est multipliée au canal
    TRANSFERTS (composition ``transferts = 1``, coefficient des transferts en
    consolidation, distinct de la coupe générique) ; impulsions stockées avec
    le profil des transferts."""
    vus, sortie = _compositions_multiplicateur({'prestations_menages': {'solidarite': x}})
    _impact_applique(sortie[2], 'prestations_menages', C.POLICY_START_YEAR)
    assert vus, "aucune impulsion de prestations_menages multipliée"
    premier_sens, composition = vus[0]
    assert premier_sens == sens
    assert composition == {'depenses': 1.0, 'recettes': 0.0, 'investissement': 0.0,
                           'transferts': 1.0}
    stockees = {cle: v for cle, v in sortie[3]._fiscal_impulses.items()
                if cle[1] == 'prestations_menages'}
    assert stockees and all(v[2] == BudgetSimulatorV45.DECAY_PROFILE_TRANSFERS
                            for v in stockees.values())


def test_w2_13_mutation_hors_des_transferts(monkeypatch):
    """Par MUTATION : retiré de ``TRANSFER_MEASURES``, le levier serait
    multiplié comme une dépense générique — le test W2-13 rougit."""
    vus, sortie = _compositions_multiplicateur({'prestations_menages': {'solidarite': -10.0}})
    _impact_applique(sortie[2], 'prestations_menages', C.POLICY_START_YEAR)
    assert vus and vus[0][1]['transferts'] == 1.0
    monkeypatch.setattr(BudgetSimulatorV45, 'TRANSFER_MEASURES',
                        BudgetSimulatorV45.TRANSFER_MEASURES - {'prestations_menages'})
    vus, _ = _compositions_multiplicateur({'prestations_menages': {'solidarite': -10.0}})
    assert vus and vus[0][1]['transferts'] == 0.0


@pytest.mark.parametrize('x, sens', [(-10.0, 'consolidation'), (10.0, 'expansion')],
                         ids=['coupe', 'hausse'])
def test_w2_depenses_publiques_multiplicateur_generique_profil_taxes(x, sens):
    """§ 1.2-1 : ``depenses_publiques`` n'est ni un investissement productif ni
    un transfert : multiplicateur d'une dépense GÉNÉRIQUE (composition sans
    canal transferts ni investissement : coupe générique en consolidation,
    transferts en expansion par construction de la matrice), profil de
    décroissance des impôts, comme ``defense``."""
    assert 'depenses_publiques' not in BudgetSimulatorV45.TRANSFER_MEASURES
    assert 'depenses_publiques' not in BudgetSimulatorV45.INVESTMENT_CORE_MEASURES
    vus, sortie = _compositions_multiplicateur({'depenses_publiques': {'credits_etat': x}},
                                               'depenses_publiques')
    assert vus and vus[0][0] == sens
    assert vus[0][1] == {'depenses': 1.0, 'recettes': 0.0, 'investissement': 0.0,
                         'transferts': 0.0}
    stockees = [v for cle, v in sortie[3]._fiscal_impulses.items() if cle[1] == 'depenses_publiques']
    assert stockees and all(v[2] == BudgetSimulatorV45.DECAY_PROFILE_TAXES for v in stockees)


# ---------------------------------------------------------------------------
# 11. W2-15 (T1) — multiplicateur intérieur nul des flux vers l'étranger
# ---------------------------------------------------------------------------

def _residu_t_plus_1(annee_debut, x):
    """Écart de croissance réelle de t+1 (fraction) entre ``transferts_etranger
    = x`` et le scénario sans le levier, MOINS le seul canal autre que la
    demande : la TRAÎNÉE DE DETTE (effet d'offre, ``DEBT_DRAG_COEFF`` × écart de
    dette/PIB de fin d'année t, au-delà de ``DEBT_DRAG_SEUIL``). Rend aussi
    l'écart de PIB réel de t+1 et sa valeur attendue par ce canal. Droit
    constant (release P : l'arrêt en 2027 de la surtaxe votée pour 2026 rend
    l'effort de la référence légèrement négatif en 2028, donc une éviction
    dans la référence ; le canal testé ici est celui du levier)."""
    t = _debut(annee_debut)
    with droit_sans_valeurs_datees():
        ref = _simuler_brut({}, annee_debut)
        avec = _simuler_brut({'transferts_etranger': {'montant': x}}, annee_debut)
    r_ref, r_avec = ref[0].set_index('Année'), avec[0].set_index('Année')
    d_ref, d_avec = ref[1].set_index('Année'), avec[1].set_index('Année')
    ratio_ref, ratio_avec = r_ref.at[t, 'Dette/PIB %'] / 100, r_avec.at[t, 'Dette/PIB %'] / 100
    assert min(ratio_ref, ratio_avec) > C.DEBT_DRAG_SEUIL  # canal actif dans les deux
    canal_dette = C.DEBT_DRAG_COEFF * (ratio_avec - ratio_ref)
    ecart_croissance = (r_avec.at[t + 1, 'Croissance %'] - r_ref.at[t + 1, 'Croissance %']) / 100
    ecart_pib = d_avec.at[t + 1, 'PIB_Réel_Base2025'] - d_ref.at[t + 1, 'PIB_Réel_Base2025']
    pib_attendu = d_ref.at[t, 'PIB_Réel_Base2025'] * canal_dette
    return ecart_croissance - canal_dette, ecart_pib, pib_attendu


@pytest.mark.parametrize('annee_debut', list(MODES.values()), ids=list(MODES))
@pytest.mark.parametrize('x', [-5.0, 5.0], ids=['coupe', 'hausse'])
def test_w2_15_t1_a_aucune_impulsion_stockee(annee_debut, x):
    """W2-15 (a) : aucune entrée ``transferts_etranger`` dans le stock
    d'impulsions, alors que le montant est bien dans le budget."""
    _, _, rapport, sim = _sim({'transferts_etranger': {'montant': x}}, annee_debut)
    _assert_applique_chaque_annee(rapport, 'transferts_etranger', x, annee_debut)
    assert not [cle for cle in sim._fiscal_impulses if cle[1] == 'transferts_etranger']


@pytest.mark.parametrize('annee_debut', list(MODES.values()), ids=list(MODES))
def test_w2_15_t1_c_coupe_sans_effet_de_demande_canal_dette_nomme(annee_debut):
    """W2-15 (c) : avec la garde, une coupe de 5 Md€ (consolidation : ni
    éviction ni cicatrice, sous 3 % du PIB) ne laisse en t+1 qu'UN canal, nommé
    et chiffré : la traînée de dette (moindre dette → potentiel moins freiné).
    Résidu de croissance hors ce canal ≤ 1e-12 ; écart de PIB réel de t+1 =
    PIB réel de t × ``DEBT_DRAG_COEFF`` × Δ(dette/PIB) à 1e-9 Md€."""
    residu, ecart_pib, attendu = _residu_t_plus_1(annee_debut, -5.0)
    assert abs(residu) <= 1e-12, residu
    assert ecart_pib == pytest.approx(attendu, abs=1e-9)
    assert ecart_pib > 0  # le canal nommé a le bon signe (coupe → moins de dette)


@pytest.mark.parametrize('annee_debut', list(MODES.values()), ids=list(MODES))
def test_w2_15_t1_d_hausse_effort_et_eviction_conserves(annee_debut):
    """W2-15 (d), arbitrage du contrat (§ 1.2-3 et § 8 : « éviction conservée,
    effet de financement ») : une HAUSSE de 5 Md€ entre dans l'effort
    budgétaire (Δeffort de t = −x / PIB de t, exactement) et, sans impulsion de
    demande, ne laisse en t+1 que deux canaux nommés : traînée de dette et
    éviction (``effet_eviction`` du moteur, part d'investissement nulle : le
    flux n'est pas un investissement productif). Mode historique : seul levier,
    l'éviction mord (|·| > 1e-9) ; mode cadre : l'effort net du droit en vigueur
    reste une consolidation, éviction nulle dans les deux scénarios."""
    from budget_simulator.engine.growth import effet_eviction
    x, t = 5.0, _debut(annee_debut)
    with droit_sans_valeurs_datees():          # droit constant : voir _residu_t_plus_1
        ref = _simuler_brut({}, annee_debut)
        avec = _simuler_brut({'transferts_etranger': {'montant': x}}, annee_debut)
    r_ref, r_avec = ref[0].set_index('Année'), avec[0].set_index('Année')
    d_ref, d_avec = ref[1].set_index('Année'), avec[1].set_index('Année')
    eff_ref = d_ref.at[t, 'Effort_Budgétaire %'] / 100
    eff_avec = d_avec.at[t, 'Effort_Budgétaire %'] / 100
    assert eff_avec - eff_ref == pytest.approx(-x / r_ref.at[t, 'PIB'], abs=1e-15)
    assert eff_ref >= 0  # aucune éviction dans la référence
    ratio_ref, ratio_avec = r_ref.at[t, 'Dette/PIB %'] / 100, r_avec.at[t, 'Dette/PIB %'] / 100
    canal_dette = C.DEBT_DRAG_COEFF * (ratio_avec - ratio_ref)
    eviction = effet_eviction(eff_avec, ratio_avec, 0.0) - effet_eviction(eff_ref, ratio_ref, 0.0)
    if annee_debut is None:
        assert abs(eviction) > 1e-9
    ecart = (r_avec.at[t + 1, 'Croissance %'] - r_ref.at[t + 1, 'Croissance %']) / 100
    assert abs(ecart - canal_dette - eviction) <= 1e-12


@pytest.mark.parametrize('annee_debut', list(MODES.values()), ids=list(MODES))
def test_w2_15_t1_b_mutation_sans_la_garde(monkeypatch, annee_debut):
    """W2-15 (b) par MUTATION : ``MESURES_HORS_DEMANDE_INTERIEURE`` vidé, la
    coupe porte une impulsion keynésienne : le résidu de t+1 hors canal de dette
    dépasse 1e-6 (le test (c) rougit sans la garde)."""
    monkeypatch.setattr(BudgetSimulatorV45, 'MESURES_HORS_DEMANDE_INTERIEURE', frozenset())
    residu, _, _ = _residu_t_plus_1(annee_debut, -5.0)
    assert abs(residu) > 1e-6, residu


# W2-15 (e, f) — revue adverse de la release E : le terme d'inflation lié à
# l'effort et la cicatrice d'austérité sont des effets de DEMANDE ; ils lisent
# l'effort INTÉRIEUR, net des flux vers un agent non résident. Les taux
# d'intérêt et l'éviction (effets de financement) gardent l'effort total.

# Consolidation générique, sans flux vers l'étranger, qui porte l'effort
# au-delà du seuil de la cicatrice (3 % du PIB) dans les deux modes.
CONSOLIDATION_SEVERE = {'depenses_publiques': {'credits_etat': -60.0, 'ondam': -10.0},
                        'prestations_menages': {'solidarite': -30.0, 'pensions': -20.0}}


@pytest.mark.parametrize('annee_debut', list(MODES.values()), ids=list(MODES))
@pytest.mark.parametrize('x', [-32.009, -5.0, 10.0], ids=['borne', 'coupe', 'hausse'])
def test_w2_15_e_inflation_de_t_plus_1_inchangee(annee_debut, x):
    """W2-15 (e) : le flux vers l'étranger entre dans l'effort total de t (non
    vacuité) mais pas dans l'inflation de t+1 : le terme d'effort de la Phillips
    lit l'effort intérieur. Écart d'inflation de t+1 ≤ 1e-12 point (arrondi des
    sommes en Md€ ; ≈ −0,12 point pour −32 Md€ avant la correction)."""
    t = _debut(annee_debut)
    r_ref, d_ref = (s.set_index('Année') for s in _sim({}, annee_debut)[:2])
    r, d = (s.set_index('Année') for s in _sim({'transferts_etranger': {'montant': x}}, annee_debut)[:2])
    assert d.at[t, 'Effort_Budgétaire %'] != d_ref.at[t, 'Effort_Budgétaire %'], 'NON_VACUITE'
    assert abs(r.at[t + 1, 'Inflation %'] - r_ref.at[t + 1, 'Inflation %']) <= 1e-12, (
        r.at[t + 1, 'Inflation %'] - r_ref.at[t + 1, 'Inflation %'])


def _etats_macro(monkeypatch, mesures, annee_debut):
    """{'croissance'|'inflation': {année: état économique reçu}} d'une
    simulation (espions sans effet sur le calcul)."""
    journal = {'croissance': {}, 'inflation': {}}
    for methode, cle in (('calculate_growth', 'croissance'), ('calculate_inflation', 'inflation')):
        original = getattr(BudgetSimulatorV45, methode)

        def espion(self, year, economic_state, _original=original, _cle=cle):
            journal[_cle][self.annee_base + year] = dict(economic_state)
            return _original(self, year, economic_state)
        monkeypatch.setattr(BudgetSimulatorV45, methode, espion)
    _simuler_brut(mesures, annee_debut)
    monkeypatch.undo()
    return journal


@pytest.mark.parametrize('annee_debut', list(MODES.values()), ids=list(MODES))
def test_w2_15_f_cicatrice_et_inflation_lisent_l_effort_interieur(monkeypatch, annee_debut):
    """W2-15 (f) : sur une consolidation sévère, ajouter la borne basse du flux
    vers l'étranger laisse l'effort INTÉRIEUR lu par la croissance (cicatrice)
    et par l'inflation identique (≤ 1e-15) ; l'effort TOTAL (taux d'intérêt,
    éviction, colonne publiée) le contient. Non-vacuité : l'effort total avec le
    flux dépasse le seuil de la cicatrice, et l'écart entre effort total et
    effort intérieur vaut le flux rapporté au PIB (≈ 1 point)."""
    x = -32.009
    mesures = {**CONSOLIDATION_SEVERE, 'transferts_etranger': {'montant': x}}
    base = _etats_macro(monkeypatch, CONSOLIDATION_SEVERE, annee_debut)
    avec = _etats_macro(monkeypatch, mesures, annee_debut)
    pib = _simuler_brut(mesures, annee_debut)[0].set_index('Année')['PIB']
    t = _debut(annee_debut)
    # t+1 lit l'effort de t, année où le flux entre et où le PIB des deux
    # scénarios est encore le même : effort intérieur identique.
    g0, g1 = base['croissance'][t + 1], avec['croissance'][t + 1]
    assert abs(g1['effort_interieur'] - g0['effort_interieur']) <= 1e-15
    assert abs(avec['inflation'][t + 1]['effort_budgetaire']
               - base['inflation'][t + 1]['effort_budgetaire']) <= 1e-15
    # Chaque année : effort total − effort intérieur = flux de l'année
    # précédente rapporté à son PIB (le flux vers l'étranger, lui seul), et
    # l'inflation lit l'effort intérieur.
    for annee in range(t + 1, DERNIERE_ANNEE + 1):
        g1, i1 = avec['croissance'][annee], avec['inflation'][annee]
        assert i1['effort_budgetaire'] == g1['effort_interieur'], annee
        ecart = g1['effort_budgetaire'] - g1['effort_interieur']
        assert ecart == pytest.approx(-x / pib[annee - 1], rel=1e-9), annee
        assert g1['effort_budgetaire'] > 0.03, ('NON_VACUITE : cicatrice', annee)


def test_w2_15_f_la_cicatrice_lit_l_effort_interieur():
    """W2-15 (f), au niveau de ``calculate_growth`` : en consolidation (aucune
    éviction), la croissance ne dépend de l'effort que par la cicatrice, qui lit
    ``effort_interieur`` : effort total 4,5 % et intérieur 2,5 % donnent la
    croissance d'un effort de 2,5 % ; un effort intérieur de 4,5 % la réduit."""
    def croissance(**effort):
        sim = BudgetSimulatorV45(periods=1)
        sim._reset_state()
        etat = {'output_gap': 0.0, 'unemployment_gap': 0.0, 'part_investissement': 0.0,
                'debt_ratio': 1.1, 'unemployment': 0.075, 'deficit_ratio': -0.05, **effort}
        return sim.calculate_growth(1, etat)
    g = croissance(effort_budgetaire=0.045, effort_interieur=0.025)
    assert g == croissance(effort_budgetaire=0.025, effort_interieur=0.025)
    assert croissance(effort_budgetaire=0.045, effort_interieur=0.045) < g


# ---------------------------------------------------------------------------
# 12. W2-16 (T2) — solde primaire et canaux ménages
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('annee_debut', list(MODES.values()), ids=list(MODES))
@pytest.mark.parametrize('x', [-5.0, 5.0], ids=['coupe', 'hausse'])
def test_w2_16_t2_solde_primaire_et_canaux_nuls(annee_debut, x):
    """W2-16 (T2) : Δ solde PRIMAIRE de l'année d'entrée = −montant (le solde
    total en diffère des intérêts de l'année) ; aucun canal ménages : effet des
    mesures sur le revenu disponible inchangé l'année d'entrée ; ni Gini ni
    compétitivité."""
    t = _debut(annee_debut)
    _, det_ref, _, _ = _sim({}, annee_debut)
    _, det, rapport, _ = _sim({'transferts_etranger': {'montant': x}}, annee_debut)
    assert _solde_primaire(det, t) - _solde_primaire(det_ref, t) == pytest.approx(-x, abs=1e-9)
    impact = _impact_applique(rapport, 'transferts_etranger', t)
    assert not {'menages', 'gini', 'competitivite', 'chomage'} & set(impact), impact
    rdb = 'RDB_Effet_Mesures_Md€'
    assert det.set_index('Année').at[t, rdb] == det_ref.set_index('Année').at[t, rdb]
