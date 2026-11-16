"""Release E — relecture adverse finale du 12/11/2026. Tests écrits AVANT le code
(TDD) ; une section par constat.

I-1. Gini d'un gel d'UNE année des pensions ou des prestations. L'effet émis
     l'année du gel était gardé en entier au retour de la revalorisation
     normale, autant qu'un gel permanent, et ce retour ne se reconnaissait qu'à
     l'égalité au littéral 1,0 : avec un droit en vigueur à 0,9999, le même gel
     rendait presque tout. La release E l'avait corrigé par une part gardée
     min(k, N)/N d'un effet « par point ». Lot 4 (méthode unique du Gini) : le
     Gini suit directement l'ÉCART EN EUROS de l'année (euros de 2025), au
     coefficient par Md€ du levier, en incrément — la part gardée est l'écart
     en euros qu'un gel laisse (aucun rattrapage), sans règle séparée au
     retour, quelle que soit la référence du calendrier. Les propriétés de la
     relecture (gel d'une année sous le gel permanent, monotonie, continuité
     autour de 1,0, valeur datée) sont re-déclarées sous cette forme.
m-b. Infobulle de la prévention : le curseur borne la DÉPENSE de prévention ;
     un effort supplémentaire se saisit en dépense de soins, sans retour
     modélisé.
m-c. Calendrier trop long : même comportement tolérant pour un profil « rampe »
     et pour l'alias ``rampe`` (ramené à la borne, correction tracée) ; en
     strict, un message exact (refus, sans « ramené »).
H-1. Hors périmètre de la passe, signalé par le relecteur : un entier géant sur
     la réforme de la fonction publique faisait répondre 500 en strict (lecteur
     latéral) au lieu de 422.

Règle d'écriture : chaque valeur attendue est dérivée des constantes nommées de
``constants.py`` ou de la règle écrite du levier, jamais recopiée d'une sortie
du moteur.
"""
import copy
import json
import math
from pathlib import Path

import pytest

import budget_simulator.constants as C
import budget_simulator.engine.cadre as cadre
import budget_simulator.engine.orchestrator as orch
from budget_simulator.simulator import BudgetSimulatorV45

RACINE = Path(__file__).absolute().parent.parent
# Documents du MOTEUR (CHANGELOG, METHODOLOGIE) : `resolve()` suit le lien
# tests/ du dépôt parent jusqu'au sous-module ; sous `RACINE`, le dépôt parent
# a son propre CHANGELOG.md, celui du site.
RACINE_MOTEUR = Path(__file__).resolve().parent.parent
REGISTRE = {m['id']: m for m in json.loads(
    (RACINE / 'policy_measures.json').read_text(encoding='utf-8'))['mesures']}
DEBUT = C.ANNEE_PREMIER_BUDGET_MANDAT
FIN = C.ANNEE_FIN_MANDAT

# ===========================================================================
# I-1. Gini d'un gel d'une année : proportionnel à l'écart de niveau accumulé
# ===========================================================================

LEVIERS = {
    'retraites': ('indexation', {'duree_cotisation': C.RETRAITES_REF_DUREE_ANS}),
    'prestations_indexation': ('taux_indexation', {}),
}
CLES = {'retraites': 'retraites.indexation',
        'prestations_indexation': 'prestations_indexation.taux_indexation'}
# Coefficient par Md€ VERSÉ de chaque levier (lot 4, constants.py § CANAUX GINI).
K = {'retraites': C.GINI_PENSIONS_PAR_MD, 'prestations_indexation': C.GINI_SOLIDARITE_PAR_MD}


def _plateau(levier):
    """N : revalorisations comptées au plus dans l'écart de niveau du levier."""
    if levier == 'retraites':
        return C.RETRAITES_EROSION_PLATEAU_ANS
    return getattr(C, 'PRESTATIONS_REVALORISATIONS_MAX', 10)


def _sim_neuf():
    sim = BudgetSimulatorV45(periods=1)
    sim._reset_state()
    return sim


def _parcours(levier, chemin, *, debut=DEBUT, origine=DEBUT):
    """Handler seul, un monde, hors simulation (indice des prix 1) : coefficient
    ``chemin[i]`` l'année ``debut + i``, horloge du levier à ``origine``. Rend
    [(dépense, gini)] par année."""
    param, fixes = LEVIERS[levier]
    sim = _sim_neuf()
    sim._origines_courantes = {levier: origine}
    sim._inflation_par_annee = {a: 0.012 + 0.0005 * (a - 2025) for a in range(2025, 2050)}
    sorties = []
    for i, c in enumerate(chemin):
        dep, _, impacts = sim.measure_handlers[levier](
            sim.measure_registry[levier], {**fixes, param: c}, debut + i, 3300.0, 0.015, 0.078)
        sorties.append((dep, impacts.get('gini', 0.0)))
    return sorties


def _cumul(sorties):
    return sum(g for _, g in sorties)


def test_i1_plateaux_nommes_et_retour_sans_egalite_au_litteral():
    """N vient des constantes nommées (7 et 10, vérifiés dans le code), et le
    retour ne se reconnaît plus à l'égalité au littéral 1,0."""
    assert C.RETRAITES_EROSION_PLATEAU_ANS == 7
    assert getattr(C, 'PRESTATIONS_REVALORISATIONS_MAX', None) == 10
    source = (RACINE / 'budget_simulator' / 'handlers' / 'depenses.py').read_text(encoding='utf-8')
    assert 'PRESTATIONS_REVALORISATIONS_MAX' in source
    assert '== INDEXATION_PLEINE' not in source
    assert 'indexation == indexation_ref' not in source


@pytest.mark.parametrize('levier', list(LEVIERS))
def test_i1_gel_d_une_annee_garde_l_ecart_en_euros(levier):
    """Gel d'une année puis pleine indexation (droit livré) : l'année du gel
    émet K × l'écart en euros qu'il ouvre, puis l'incrément de l'écart (nul
    hors simulation, masse constante) ; cumul = K × l'écart laissé, non nul,
    sous le gel permanent (lot 4 ; jusqu'ici g par point, puis g/N gardé)."""
    sorties = _parcours(levier, [0.0] + [1.0] * 6)
    emis = [g for _, g in sorties]
    assert emis[0] == pytest.approx(K[levier] * sorties[0][0], rel=1e-12) and emis[0] > 0
    assert _cumul(sorties) == pytest.approx(K[levier] * sorties[-1][0], rel=1e-12)
    permanent = _parcours(levier, [0.0] * 7)
    assert 0 < _cumul(sorties) < _cumul(permanent)


@pytest.mark.parametrize('levier', list(LEVIERS))
@pytest.mark.parametrize('coef, reference', [(0.0, 1.0), (0.5, 1.0), (1.2, 1.0), (0.0, 0.9),
                                             (0.95, 0.9), (0.0, 0.9999)])
def test_i1_part_gardee_est_l_ecart_en_euros_quelle_que_soit_la_reference(levier, coef, reference):
    """k années au coefficient ``coef`` puis retour à la référence (quelle que
    soit sa valeur) : écart au chemin de référence = K × l'écart en euros des
    deux chemins la dernière année, et il croît avec k jusqu'au plateau."""
    n = _plateau(levier)
    precedent = None
    for k in range(1, n + 3):
        gel = _parcours(levier, [coef] * k + [reference] * 3)
        ref = _parcours(levier, [reference] * (k + 3))
        ecart = _cumul(gel) - _cumul(ref)
        assert ecart == pytest.approx(K[levier] * (gel[-1][0] - ref[-1][0]), rel=1e-9, abs=1e-15), (k,)
        if precedent is not None and k <= n:
            assert abs(ecart) > abs(precedent), (k, ecart, precedent)
        precedent = ecart


@pytest.mark.parametrize('levier', list(LEVIERS))
def test_i1_monotone_dans_le_nombre_d_annees_gelees_et_sous_le_gel_permanent(levier):
    """(c) Gel de k années puis retour : cumul croissant avec k (strictement
    jusqu'au plateau), sous le gel permanent du même horizon (au plus égal
    au-delà du plateau)."""
    n = _plateau(levier)
    horizon = n + 5
    cumuls = [_cumul(_parcours(levier, [0.0] * k + [1.0] * (horizon - k))) for k in range(1, n + 3)]
    permanent = _cumul(_parcours(levier, [0.0] * horizon))
    assert all(b > a for a, b in zip(cumuls[:n], cumuls[1:n])), cumuls
    assert all(b >= a for a, b in zip(cumuls, cumuls[1:])), cumuls
    assert all(c < permanent for c in cumuls[:n - 1]), (cumuls, permanent)
    assert all(c <= permanent * (1 + 1e-12) for c in cumuls), (cumuls, permanent)
    assert cumuls[0] < permanent / 2


@pytest.mark.parametrize('levier', list(LEVIERS))
@pytest.mark.parametrize('coef', [0.0, 0.9, 1.0, 1.2])
def test_i1_coefficient_constant_emissions_egales_a_l_increment_de_l_ecart(levier, coef):
    """(d) Coefficient constant : chaque année émet K × l'incrément de l'écart en
    euros ; rien après le plateau (l'écart cesse de croître) ; rien à la pleine
    indexation (lot 4 ; jusqu'ici g puis le flux des cohortes)."""
    sorties = _parcours(levier, [coef] * 12)
    deps = [0.0] + [d for d, _ in sorties]
    for t, (_, g) in enumerate(sorties):
        assert g == pytest.approx(K[levier] * (deps[t + 1] - deps[t]), rel=1e-9, abs=1e-15), t
    n = _plateau(levier)
    assert all(g == pytest.approx(0.0, abs=1e-15) for _, g in sorties[n:]), sorties[n:]
    if coef == 1.0:
        assert all(g == 0.0 for _, g in sorties)


@pytest.mark.parametrize('levier', list(LEVIERS))
def test_i1_aucun_effet_quand_le_gel_n_a_porte_sur_aucune_revalorisation(levier):
    """(e) Gel posé l'année qui suit la dernière revalorisation comptée
    (fenêtre [origine ; origine + N − 1] épuisée) puis retiré : il n'ouvre aucun
    écart en euros, donc n'émet rien (jusqu'ici l'effet « par point » était
    émis à son ouverture puis rendu en entier)."""
    n = _plateau(levier)
    sorties = _parcours(levier, [1.0] * n + [0.0] + [1.0] * 3, debut=2026, origine=2026)
    assert sorties[n] == (0.0, 0.0), sorties[n]
    assert _cumul(sorties) == pytest.approx(0.0, abs=1e-15), sorties


# --- En simulation complète (mode cadre) ------------------------------------

def _pleine_precision(monkeypatch):
    """Sorties publiées sans arrondi (le Gini est publié au millième)."""
    monkeypatch.setattr(orch, 'round', lambda x, nd=None: float(x), raising=False)


class _Sonde(BudgetSimulatorV45):
    """Moteur instrumenté : sortie COMBINÉE de chaque levier, chaque année (les
    trois mondes de la composition en mode cadre), lue au moment de l'appel —
    y compris pour un levier égal au droit en vigueur, que le rapport ne
    publie pas — et la masse nominale de l'année des deux catégories indexées
    (les écarts en euros de 2025 du lot 4 : écart de niveau × masse de 2025).
    Aucun calcul modifié."""

    def _evaluer_handler(self, measure, parameters, year, gdp, inflation, unemployment):
        sortie = super()._evaluer_handler(measure, parameters, year, gdp, inflation, unemployment)
        self.__dict__.setdefault('sonde', {})[(year, measure['id'])] = sortie
        self.__dict__.setdefault('masses', {})[year] = {
            cat: self.masse_categorie_nominale(cat) for cat in ('retraites', 'minima_sociaux')}
        return sortie


def _simuler(mesures, profils=None, annee_debut=DEBUT):
    sim = _Sonde(periods=10, mesures=copy.deepcopy(mesures), annee_debut=annee_debut, profils=profils)
    df, _, rapport = sim.simulate()
    return df.set_index('Année'), rapport, sim


def _emis(sim, levier, jusqu_a=2035):
    """Gini émis par le levier (sortie combinée), cumulé jusqu'à ``jusqu_a``."""
    return sum(sortie[2].get('gini', 0.0) for (annee, nom), sortie in sim.sonde.items()
               if nom == levier and annee <= jusqu_a)


def _depense(sim, levier, annee):
    sortie = sim.sonde.get((annee, levier))
    return 0.0 if sortie is None else sortie[0]


_CATEGORIE = {'retraites': 'retraites', 'prestations_indexation': 'minima_sociaux'}


def _ecart_2025(sim, levier, annee):
    """Écart en euros de 2025 du levier (sortie combinée) l'année ``annee`` :
    la dépense de l'année ramenée à la masse de 2025 de sa catégorie."""
    cat = _CATEGORIE[levier]
    return (_depense(sim, levier, annee) * sim.spending_categories_base[cat]
            / sim.masses[annee][cat])


def _gel(leviers, coef=0.0, annee=None):
    mesures, profils = {}, {}
    for levier in leviers:
        param, _ = LEVIERS[levier]
        mesures[levier] = {param: coef}
        if annee is not None:
            profils[CLES[levier]] = {'forme': 'annee', 'annee': annee}
    return mesures, (profils or None)


@pytest.fixture(scope='module')
def _bancs():
    out = {'sq': _simuler({})}
    for nom, leviers in (('deux', list(LEVIERS)), *((l, [l]) for l in LEVIERS)):
        out[(nom, 'annee')] = _simuler(*_gel(leviers, annee=DEBUT))
        out[(nom, 'permanent')] = _simuler(*_gel(leviers))
        out[(nom, 'sous09')] = _simuler(*_gel(leviers, coef=0.9))
    return out


@pytest.mark.parametrize('levier', list(LEVIERS))
@pytest.mark.parametrize('ecriture', ['annee', 'permanent', 'sous09'])
def test_i1_simulation_cumul_egal_a_k_fois_l_ecart_en_euros_de_2025(levier, ecriture, _bancs):
    """Gel 2028, gel permanent, sous-indexation à 0,9, mode cadre : Gini émis
    jusqu'en 2035 = K × l'écart en euros de 2025 de 2035 (sortie combinée des
    trois mondes)."""
    _, r, s = _bancs[(levier, ecriture)]
    assert r['valid'] is True, r['warnings']
    assert _emis(s, levier) == pytest.approx(K[levier] * _ecart_2025(s, levier, 2035), rel=1e-9)
    assert _emis(s, levier) > 0


@pytest.mark.parametrize('levier', list(LEVIERS))
def test_i1_simulation_gel_d_une_annee_sous_le_gel_permanent(levier, _bancs):
    """(c) En simulation : émis jusqu'en 2032 du gel d'une année < la moitié
    de celui du gel permanent, pour chaque levier (avant : égaux pour les
    prestations, 0,005 contre 0,007 pour les pensions)."""
    s0 = _bancs['sq'][2]
    annee = _emis(_bancs[(levier, 'annee')][2], levier, FIN) - _emis(s0, levier, FIN)
    permanent = _emis(_bancs[(levier, 'permanent')][2], levier, FIN) - _emis(s0, levier, FIN)
    assert 0 < annee < permanent / 2, (annee, permanent)


@pytest.mark.parametrize('levier', list(LEVIERS))
@pytest.mark.parametrize('ecriture', ['permanent', 'sous09'])
def test_i1_simulation_coefficient_constant_rien_avant_le_debut(levier, ecriture, _bancs):
    """(d) En simulation, coefficient constant : rien avant le début (droit en
    vigueur), puis chaque année K × l'incrément de l'écart en euros de 2025 ;
    en mode historique, dès 2026. Émissions lues à la sonde (sortie combinée
    du levier) : le rapport de l'API ne publie un levier qu'au-delà d'un seuil
    de significativité, sans effet sur le calcul."""
    coef = 0.0 if ecriture == 'permanent' else 0.9
    for debut, (_, r, s) in ((DEBUT, _bancs[(levier, ecriture)]),
                             (C.POLICY_START_YEAR, _simuler(*_gel([levier], coef=coef), annee_debut=None))):
        emis = {annee: sortie[2].get('gini', 0.0) for (annee, nom), sortie in s.sonde.items()
                if nom == levier}
        assert all(emis[a] == 0.0 for a in emis if a < debut), (debut, emis)
        assert emis[debut] > 0, (debut, emis)
        precedent = 0.0
        for annee in range(debut, 2036):
            v = _ecart_2025(s, levier, annee)
            assert emis[annee] == pytest.approx(K[levier] * (v - precedent), rel=1e-9, abs=1e-15), annee
            precedent = v


def _memes_euros(sim, s0, leviers, annee=FIN):
    """Programme en MONTANT (prestations_menages) qui retire en ``annee`` les
    mêmes euros que l'écriture en coefficient."""
    montant = {}
    if 'retraites' in leviers:
        montant['pensions'] = _depense(sim, 'retraites', annee) - _depense(s0, 'retraites', annee)
    if 'prestations_indexation' in leviers:
        montant['solidarite'] = (_depense(sim, 'prestations_indexation', annee)
                                 - _depense(s0, 'prestations_indexation', annee))
    return {'prestations_menages': montant}


def _emis_total(sim, s0, jusqu_a=FIN):
    leviers = ('retraites', 'prestations_indexation', 'prestations_menages')
    return sum(_emis(sim, l, jusqu_a) - _emis(s0, l, jusqu_a) for l in leviers)


@pytest.mark.parametrize('nom', ['deux', 'retraites', 'prestations_indexation'])
def test_i1_memes_euros_meme_effet_aux_euros_de_2025_pres(nom, _bancs):
    """(a) Mêmes euros de 2032, écrits en gel d'une année, en sous-indexation
    permanente ou en montant (prestations_menages) : même coefficient par Md€
    (lot 4, méthode unique) : le Gini émis jusqu'en 2032 est K × l'écart en
    euros de 2025 pour l'écriture en coefficient, K × le montant pour
    l'écriture en montant — leur rapport est exactement celui des euros de
    2025 aux euros courants de 2032 (masse de 2025 / masse de 2032 de la
    catégorie). Avant le lot 4 : environ 14 pour les prestations (écart des
    règles par Md€ des deux leviers), et jusqu'à 35 avant la relecture."""
    leviers = list(LEVIERS) if nom == 'deux' else [nom]
    s0 = _bancs['sq'][2]
    for ecriture in ('annee', 'sous09'):
        s = _bancs[(nom, ecriture)][2]
        _, rm, sm = _simuler(_memes_euros(s, s0, leviers))
        assert rm['valid'] is True, rm['warnings']
        montant = _emis_total(sm, s0)
        assert montant > 0, ('NON_VACUITE', ecriture, montant)
        attendu = sum(K[l] * (_ecart_2025(s, l, FIN) - _ecart_2025(s0, l, FIN)) for l in leviers)
        par_montant = sum(K[l] * (_depense(s, l, FIN) - _depense(s0, l, FIN)) for l in leviers)
        assert _emis_total(s, s0) == pytest.approx(attendu, rel=1e-9), ecriture
        assert montant == pytest.approx(par_montant, rel=1e-9), ecriture


def _droit_indexation(idx, tmp_path):
    droit = json.loads((RACINE / 'budget_simulator' / 'data' / 'droit_en_vigueur.json')
                       .read_text(encoding='utf-8'))
    droit['mesures']['retraites']['indexation'] = idx
    droit['mesures']['prestations_indexation']['taux_indexation'] = idx
    chemin = tmp_path / f'droit_{idx}.json'
    chemin.write_text(json.dumps(droit, ensure_ascii=False), encoding='utf-8')
    return chemin


def test_i1_continuite_entre_droit_a_1_0_9999_et_0_9(monkeypatch, tmp_path):
    """(b) Droit en vigueur (fichier remplaçable sans code) à 1,0, 0,9999 et
    0,9 : le gel 2028 des deux coefficients émet, net du statu quo de ce droit,
    K × (écart en euros de 2025 du gel − celui du statu quo) par levier —
    continu en l'écart gelé ; et le Gini publié en 2032 suit, à la précision
    du calcul (avant la relecture : 0,0165 à 1,0 contre 0,0013 à 0,9999)."""
    _pleine_precision(monkeypatch)
    deltas = {}
    for idx in (1.0, 0.9999, 0.9):
        monkeypatch.setattr(cadre, 'DROIT_EN_VIGUEUR_PATH', _droit_indexation(idx, tmp_path))
        cadre.vider_caches()
        try:
            d0, _, s0 = _simuler({})
            d, r, s = _simuler(*_gel(list(LEVIERS), annee=DEBUT))
        finally:
            cadre.vider_caches()
        assert r['valid'] is True, r['warnings']
        for levier in LEVIERS:
            emis = _emis(s, levier) - _emis(s0, levier)
            attendu = K[levier] * (_ecart_2025(s, levier, 2035) - _ecart_2025(s0, levier, 2035))
            assert emis == pytest.approx(attendu, rel=1e-9), (idx, levier, emis, attendu)
        deltas[idx] = d.at[FIN, 'Gini'] - d0.at[FIN, 'Gini']
    monkeypatch.undo()
    cadre.vider_caches()
    assert deltas[1.0] > 0
    assert deltas[0.9999] == pytest.approx(deltas[1.0], rel=1e-3), deltas
    assert deltas[0.9] == pytest.approx(0.9 * deltas[1.0], rel=0.05), deltas


def test_i1_valeur_datee_du_droit_regle_d_increment(monkeypatch, tmp_path):
    """Droit en vigueur avec une valeur datée des deux coefficients (1,0 jusqu'en
    2029, 0,9 ensuite) : le statu quo n'émet rien avant 2030 et, à partir de
    2030, K × l'incrément de son écart en euros ; un gel 2028 garde, net du
    statu quo, K × la différence des écarts en euros de 2035."""
    droit = json.loads((RACINE / 'budget_simulator' / 'data' / 'droit_en_vigueur.json')
                       .read_text(encoding='utf-8'))
    droit['valeurs_datees'] = {levier: {param: [
        {'de': 2026, 'a': 2029, 'valeur': 1.0, 'source': 'banc'},
        {'de': 2030, 'valeur': 0.9, 'source': 'banc'}]} for levier, (param, _) in LEVIERS.items()}
    chemin = tmp_path / 'droit_date.json'
    chemin.write_text(json.dumps(droit, ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(cadre, 'DROIT_EN_VIGUEUR_PATH', chemin)
    cadre.vider_caches()
    try:
        _, _, s0 = _simuler({})
        _, r, s = _simuler(*_gel(list(LEVIERS), annee=DEBUT))
    finally:
        monkeypatch.undo()
        cadre.vider_caches()
    assert r['valid'] is True, r['warnings']
    for levier in LEVIERS:
        assert _emis(s0, levier, 2029) == 0.0
        assert s0.sonde[(2030, levier)][2]['gini'] == pytest.approx(
            K[levier] * (_ecart_2025(s0, levier, 2030) - _ecart_2025(s0, levier, 2029)), rel=1e-9)
        assert s0.sonde[(2030, levier)][2]['gini'] > 0
        emis = _emis(s, levier) - _emis(s0, levier)
        attendu = K[levier] * (_ecart_2025(s, levier, 2035) - _ecart_2025(s0, levier, 2035))
        assert emis == pytest.approx(attendu, rel=1e-9), (levier, emis)


def test_i1_methodologie_et_changelog_disent_l_ordre_de_grandeur():
    texte = (RACINE_MOTEUR / 'docs' / 'METHODOLOGIE.md').read_text(encoding='utf-8')
    assert 'min(k, N)/N' in texte           # historique de la relecture, conservé
    assert 'écart en euros' in texte        # règle du lot 4
    assert 'majore vraisemblablement' not in texte
    changelog = (RACINE_MOTEUR / 'CHANGELOG.md').read_text(encoding='utf-8')
    assert 'jamais rendu' not in changelog
    assert 'min(k, N)/N' in changelog


# ===========================================================================
# m-b. Infobulle de la prévention
# ===========================================================================

def test_mb_infobulle_prevention_le_curseur_borne_la_depense():
    """Le curseur borne la DÉPENSE de prévention (PARAM_DOMAINS : 7,5 à 11,2,
    422 en strict au-delà) ; un effort supplémentaire se saisit en dépense de
    soins (curseur nommé), sans retour modélisé."""
    tooltip = REGISTRE['sante']['parametres']['prevention_budget']['tooltip']
    assert 'pas de la dépense' not in tooltip, tooltip
    assert C.PARAM_DOMAINS['sante']['prevention_budget'] == (7.5, 11.2)
    assert 'borne la dépense de prévention à 11,2 Md€' in tooltip, tooltip
    soins = REGISTRE['depenses_publiques']['parametres']['ondam']['label'].rsplit(' (', 1)[0]
    assert f'« {soins} »' in tooltip, (soins, tooltip)
    assert 'sans retour modélisé' in tooltip, tooltip
    assert 'hypothèse haute' in tooltip and '8 731' in tooltip, tooltip


# ===========================================================================
# m-c. Calendrier trop long : profil et alias, même comportement
# ===========================================================================

CLE_M5 = 'defense.budget'
PROG_M5 = {'defense': {'budget': 70}}


@pytest.mark.parametrize('debut, annees, borne', [(2028, 6, 5), (2031, 6, 2), (2032, 3, 1),
                                                  (2030, 0, 1)])
def test_mc_profil_et_alias_ramenes_a_la_borne_traces(debut, annees, borne):
    """Tolérant : un profil « rampe » trop long est ramené à la borne et tracé,
    exactement comme l'alias ``rampe`` (avant : profil ignoré, programme en
    plein dès le début ; alias ramené) ; mêmes mesures chaque année."""
    corr_p, corr_a = {}, {}
    p = cadre.CadreTemporel.preparer(PROG_M5, debut, profils={CLE_M5: {'forme': 'rampe', 'annees': annees}},
                                     strict=False, warned=set(), corrections=corr_p)
    a = cadre.CadreTemporel.preparer(PROG_M5, debut, rampe={'annees': annees, 'leviers': [CLE_M5]},
                                     strict=False, warned=set(), corrections=corr_a)
    assert a.etat.rampe.annees == borne
    assert CLE_M5 in p.etat.profils and p.etat.profils[CLE_M5].annees == borne, p.etat.profils
    for an in range(debut, 2036):
        assert p.mesures_de_l_annee(an) == a.mesures_de_l_annee(an), an
    for corrections in (corr_p, corr_a):
        textes = ' '.join(str(v) for v in corrections.values())
        assert f'ramenée à {borne}' in textes, corrections


@pytest.mark.parametrize('demande', ['profils', 'rampe'])
def test_mc_strict_message_exact_sans_ramene(demande):
    """Strict : refus, avec le domaine et la raison ; jamais « ramenée à »."""
    kw = ({'profils': {CLE_M5: {'forme': 'rampe', 'annees': 6}}} if demande == 'profils'
          else {'rampe': {'annees': 6, 'leviers': [CLE_M5]}})
    with pytest.raises((cadre.ProfilInvalide, cadre.RampeInvalide)) as e:
        cadre.CadreTemporel.preparer(PROG_M5, 2028, strict=True, **kw)
    message = str(e.value)
    assert 'annees = 6 hors de [1 ; 5] (la rampe finit au plus tard en 2032)' in message, message
    assert 'ramen' not in message, message


def test_mc_simulation_profil_trop_long_rapport_invalide_calendrier_publie(monkeypatch):
    """Simulation tolérante : rapport invalide (correction), calendrier publié
    avec la durée ramenée, cible atteinte en 2032."""
    monkeypatch.delenv('BUDGETLAB_STRICT', raising=False)
    df, _, rapport = BudgetSimulatorV45(periods=10, mesures=PROG_M5, annee_debut=2028,
                                        profils={CLE_M5: {'forme': 'rampe', 'annees': 6}}).simulate()
    assert rapport['valid'] is False
    prof = rapport['cadre']['profils'][CLE_M5]
    assert prof['annees'] == 5 and prof['valeurs'][str(FIN)] == 70, prof
    assert prof['valeurs'][str(DEBUT)] < 70, prof


# ===========================================================================
# H-1. Entier géant sur la réforme de la fonction publique : 422, jamais 500
# ===========================================================================

def _client(monkeypatch, strict):
    import importlib.util
    from fastapi.testclient import TestClient
    spec = importlib.util.spec_from_file_location('api_relecture_finale', RACINE / 'api.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv('BUDGETLAB_STRICT', strict)
    return TestClient(module.app, raise_server_exceptions=False)


@pytest.mark.parametrize('param', ['fusion_agences', 'digitalisation'])
@pytest.mark.parametrize('signe', [1, -1])
@pytest.mark.parametrize('debut', [DEBUT, 2031])
def test_h1_entier_geant_reforme_fp_422_en_strict_200_en_tolerant(monkeypatch, param, signe, debut):
    corps = {'periods': 10, 'annee_debut': debut,
             'mesures': {'fonction_publique_reforme': {param: signe * 10 ** 400}}}
    r = _client(monkeypatch, '1').post('/simulate', json=corps)
    assert r.status_code == 422, r.text[:300]
    r = _client(monkeypatch, '').post('/simulate', json=corps)
    assert r.status_code == 200, r.text[:300]
    assert r.json()['report']['valid'] is False


@pytest.mark.parametrize('valeur', [10 ** 400, -10 ** 400, math.inf, -math.inf, math.nan])
def test_h1_lecteur_lateral_valeur_non_finie_comme_cle_absente(valeur):
    """Le lecteur latéral du vivier (effectifs) lit la réforme BRUTE : une valeur
    non finie ou hors des flottants y vaut la clé absente — ce que la porte des
    valeurs fait de la même entrée (clé retirée en tolérant, refus en strict) —
    au lieu de lever (entier géant) ou d'emporter le taux à son maximum (inf)."""
    def stock(reforme):
        sim = _sim_neuf()
        sim.mesures = {'fonction_publique_reforme': reforme}
        return sim._reforme_fp_reduction_cumulee(2030)
    assert stock({'fusion_agences': valeur, 'digitalisation': 30}) == stock({'digitalisation': 30})
    assert stock({'fusion_agences': 30, 'digitalisation': 30}) > stock({'digitalisation': 30}) > 0
