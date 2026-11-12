"""Release E — arbitrages du mainteneur du 12/11/2026 et constats de la
contre-vérification adverse des corrections. Tests écrits AVANT le code (TDD) ;
chaque section correspond à un point et à un commit.

1. Coût d'un point de cotisation salariale : 1 % de la masse salariale brute
   2025 (Insee, comptes de la Nation, tableau 2.101, ligne D11), dérivé de la
   donnée sourcée ; le maximum du curseur devient le taux moyen réel des
   cotisations salariales (D613CE / D11).

Règle d'écriture : chaque valeur attendue est dérivée des constantes nommées de
``constants.py`` ou des données sourcées qu'elles portent, jamais recopiée d'une
sortie du moteur.
"""
import json
import math
import re
from pathlib import Path

import pytest

import budget_simulator.constants as C
from budget_simulator.constants import PARAM_DOMAINS
from budget_simulator.handlers._types import canaux_menages
from budget_simulator.simulator import BudgetSimulatorV45

RACINE = Path(__file__).absolute().parent.parent
CONSTANTS_PY = RACINE / 'budget_simulator' / 'constants.py'
REGISTRE = {m['id']: m for m in json.loads(
    (RACINE / 'policy_measures.json').read_text(encoding='utf-8'))['mesures']}
ETAT = dict(year=2028, gdp=3300.0, inflation=0.015, unemployment=0.078)


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


def _expression(nom):
    """Membre droit de la définition ``NOM = …`` dans constants.py (commentaire retiré)."""
    m = re.search(rf'^{nom} = (.+)$', CONSTANTS_PY.read_text(encoding='utf-8'), flags=re.MULTILINE)
    assert m, f'{nom} : définition introuvable en tête de ligne'
    return m.group(1).split('#')[0].strip()


# ===========================================================================
# 1. Coût d'un point de cotisation salariale (décision 13 du mainteneur)
# ===========================================================================

COTIS = 'cotisations_salariales'


def test_p1_donnees_sourcees_insee_2025():
    """Insee, comptes nationaux annuels (base 2020), tableau 2.101, 2025 :
    D11 (salaires et traitements bruts) = 1 157,166 Md€ ; D613CE (cotisations
    sociales effectives à la charge des salariés, CSG et CRDS exclues) =
    138,217 Md€."""
    assert C.SALAIRES_BRUTS_2025_MD == 1157.166
    assert C.COTIS_SAL_MASSE_2025_MD == 138.217


def test_p1_cout_du_point_derive_de_la_masse_salariale():
    """1 point = 1 % de la masse salariale brute 2025, calculé (jamais écrit en
    dur) : ≈ 11,57 Md€."""
    assert C.COUT_PAR_POINT_COTIS_SAL == C.SALAIRES_BRUTS_2025_MD / 100
    assert C.COUT_PAR_POINT_COTIS_SAL == pytest.approx(11.57, abs=0.005)
    expression = _expression('COUT_PAR_POINT_COTIS_SAL')
    assert 'SALAIRES_BRUTS_2025_MD' in expression and not re.search(r'\d+\.\d+', expression), expression


def test_p1_maximum_egal_au_taux_moyen_reel():
    """Le maximum du curseur (suppression totale des cotisations salariales)
    vaut le taux moyen réel de ces cotisations, en points de salaire brut :
    100 × D613CE / D11 ≈ 11,94 points (et non plus 23,03)."""
    taux_moyen_points = 100 * C.COTIS_SAL_MASSE_2025_MD / C.SALAIRES_BRUTS_2025_MD
    assert C.COTIS_SAL_POINTS_SUPPRESSION == pytest.approx(taux_moyen_points, rel=1e-12)
    assert C.COTIS_SAL_POINTS_SUPPRESSION == pytest.approx(11.94, abs=0.005)
    spec = REGISTRE[COTIS]['parametres']['baisse_points']
    assert spec['max'] == pytest.approx(C.COTIS_SAL_POINTS_SUPPRESSION, abs=1e-9)
    assert PARAM_DOMAINS[COTIS]['baisse_points'][1] == pytest.approx(C.COTIS_SAL_POINTS_SUPPRESSION, abs=1e-9)


def _verifier_recette_d_un_point(sim=None):
    sim = sim if sim is not None else _sim_neuf()
    dep, rec, impacts = _appel(sim, COTIS, {'baisse_points': 1.0})
    assert dep == 0
    assert rec == pytest.approx(-C.SALAIRES_BRUTS_2025_MD / 100, rel=1e-12), rec
    assert impacts['menages'] == canaux_menages(prelevements_directs=rec)


def test_p1_un_point_rend_un_pour_cent_de_la_masse_salariale():
    _verifier_recette_d_un_point()


def test_p1_au_maximum_la_recette_supprime_exactement_la_masse_sourcee():
    haut = PARAM_DOMAINS[COTIS]['baisse_points'][1]
    _, rec, _ = _appel(_sim_neuf(), COTIS, {'baisse_points': haut})
    assert rec == pytest.approx(-C.COTIS_SAL_MASSE_2025_MD, abs=1e-9)


def test_p1_infobulle():
    """Infobulle décidée : « 1 point = 1 % de la masse salariale brute 2025
    (11,6 Md€) », montant arrondi dérivé du coût du point ; plus de « 6 Md€
    par point »."""
    tooltip = REGISTRE[COTIS]['parametres']['baisse_points']['tooltip']
    cout = f'{C.COUT_PAR_POINT_COTIS_SAL:.1f}'.replace('.', ',')
    assert f'1 point = 1 % de la masse salariale brute 2025 ({cout} Md€)' in tooltip, tooltip
    assert '6 Md€ par point' not in tooltip
    maximum = f'{C.COTIS_SAL_POINTS_SUPPRESSION:.1f}'.replace('.', ',')
    assert f'{maximum} points' in tooltip, tooltip


def test_p1_handler_sans_ancien_commentaire_de_six_milliards():
    import inspect
    import budget_simulator.handlers.fiscalite_menages as mod
    source = inspect.getsource(mod.FiscaliteMenagesMixin._apply_cotisations_salariales)
    assert '-6 Md€' not in source and '−6 Md€' not in source, 'commentaire périmé du coût du point'


# ===========================================================================
# 2. Effet des cotisations salariales sur l'indice de Gini : coefficient PAR
#    Md€, estimation de France Budget (décision du mainteneur du 12/11/2026)
# ===========================================================================

def test_p2_coefficient_par_md_nomme():
    """+0,0001 de Gini par Md€ de cotisations rendu aux salariés : une baisse
    accroît légèrement les inégalités (signe positif)."""
    assert C.GINI_COTIS_SAL_PAR_MD == 0.0001


def test_p2_coefficient_documente_comme_estimation_de_france_budget():
    """Le commentaire de la constante dit ce qu'elle est : une estimation de
    France Budget (quintiles Insee 2025), son incertitude (facteur 2) et son
    domaine (baisse uniforme de quelques points) ; aucune « OFCE 2023 »."""
    source = CONSTANTS_PY.read_text(encoding='utf-8')
    debut = source.index('GINI_COTIS_SAL_PAR_MD = ')
    bloc = source[source.rfind('\n\n', 0, debut):debut]
    for motif in ('estimation de France Budget', 'quintiles', 'Insee', 'facteur 2', 'baisse uniforme'):
        assert motif in bloc, (motif, bloc)
    assert 'OFCE 2023' not in bloc


def _gini(points, sim=None):
    return _appel(sim if sim is not None else _sim_neuf(), COTIS, {'baisse_points': points})[2]['gini']


def _verifier_gini_par_md():
    """Gini émis = coefficient × Md€ rendus, quel que soit le nombre de points."""
    for points in (0.5, 1.0, 2.5, 6.0, PARAM_DOMAINS[COTIS]['baisse_points'][1]):
        montant = points * C.COUT_PAR_POINT_COTIS_SAL
        assert _gini(points) == pytest.approx(C.GINI_COTIS_SAL_PAR_MD * montant, rel=1e-12), points


def test_p2_gini_egal_coefficient_fois_montant_rendu():
    _verifier_gini_par_md()


def test_p2_gini_ne_depend_que_du_montant(monkeypatch):
    """Le Gini ne dépend plus de la convention du point : un point deux fois plus
    cher émet deux fois plus de Gini par point, le même par Md€."""
    import budget_simulator.handlers.fiscalite_menages as mod
    g1 = _gini(1.0)
    monkeypatch.setattr(mod, 'COUT_PAR_POINT_COTIS_SAL', 2 * C.COUT_PAR_POINT_COTIS_SAL)
    assert _gini(1.0) == pytest.approx(2 * g1, rel=1e-12)
    assert _gini(0.5) == pytest.approx(g1, rel=1e-12)


def test_p2_suppression_totale_ordre_de_grandeur():
    """Au maximum (138,2 Md€ rendus) : ≈ +0,014 de Gini, contre +0,062 émis par
    l'ancienne règle (+0,0027 par point de 6 Md€ sur 23 points)."""
    haut = PARAM_DOMAINS[COTIS]['baisse_points'][1]
    assert _gini(haut) == pytest.approx(C.GINI_COTIS_SAL_PAR_MD * C.COTIS_SAL_MASSE_2025_MD, rel=1e-9)
    assert 0.013 < _gini(haut) < 0.015


def test_p2_aucune_mention_ofce_2023_pour_ce_levier():
    import inspect
    import budget_simulator.handlers.fiscalite_menages as mod
    source = inspect.getsource(mod.FiscaliteMenagesMixin._apply_cotisations_salariales)
    assert 'OFCE' not in source and '0.0027' not in source and '0,0027' not in source
    tooltip = REGISTRE[COTIS]['parametres']['baisse_points']['tooltip']
    assert 'OFCE' not in tooltip


def test_p2_infobulle_dit_l_estimation():
    tooltip = REGISTRE[COTIS]['parametres']['baisse_points']['tooltip']
    assert 'estimation de France Budget' in tooltip, tooltip
    coefficient = f'{C.GINI_COTIS_SAL_PAR_MD:.4f}'.replace('.', ',')
    assert f'+{coefficient} de Gini par Md€' in tooltip, tooltip


def test_p2_methodologie_dit_l_estimation_sans_ofce():
    texte = (RACINE / 'docs' / 'METHODOLOGIE.md').read_text(encoding='utf-8')
    debut = texte.index('- **Cotisations salariales** : un point vaut')
    fin = texte.index('\n- **', debut + 10)
    bloc = texte[debut:fin]
    assert 'estimation de France Budget' in bloc and 'facteur 2' in bloc, bloc
    # L'ancienne valeur peut être citée comme historique, jamais sa source introuvable.
    assert 'OFCE' not in bloc, bloc


# ===========================================================================
# 3. Gel d'UNE année des pensions et des prestations sociales (décision 4 du
#    mainteneur, précision du 12/11/2026) : le moteur calcule seul un gel de
#    revalorisation en 2028 suivi d'une revalorisation normale ; l'économie
#    persiste par l'effet de niveau (aucun rattrapage).
# ===========================================================================

import budget_simulator.engine.cadre as cadre  # noqa: E402

DEBUT_CADRE = C.ANNEE_PREMIER_BUDGET_MANDAT
INDEXATIONS = {
    'retraites.indexation': ('retraites', 'indexation', 'retraites'),
    'prestations_indexation.taux_indexation': ('prestations_indexation', 'taux_indexation',
                                               'minima_sociaux'),
}


class _Sonde(BudgetSimulatorV45):
    """Moteur instrumenté : sortie COMBINÉE de chaque levier (trois mondes de la
    composition), masses nominales de l'année et mémoire d'inflation, lues au
    moment de l'appel (aucun calcul modifié)."""

    def _evaluer_handler(self, measure, parameters, year, gdp, inflation, unemployment):
        sortie = super()._evaluer_handler(measure, parameters, year, gdp, inflation, unemployment)
        journal = self.__dict__.setdefault('sonde', {})
        journal[(year, measure['id'])] = sortie
        journal[(year, 'masses')] = {c: self.masse_categorie_nominale(c)
                                     for c in ('retraites', 'minima_sociaux')}
        journal['inflation'] = dict(self._inflation_par_annee)
        return sortie


def _simuler_sonde(mesures, profils=None, annee_debut=DEBUT_CADRE):
    sim = _Sonde(periods=10, mesures=mesures, annee_debut=annee_debut, profils=profils)
    df, detail, rapport = sim.simulate()
    return sim, df.set_index('Année'), rapport


def _gel(cles, annee=None):
    """Programme qui gèle les clés données ; profil « une seule année » si
    ``annee`` est donnée, gel permanent sinon."""
    mesures, profils = {}, {}
    for cle in cles:
        levier, param, _ = INDEXATIONS[cle]
        mesures.setdefault(levier, {})[param] = 0.0
        if annee is not None:
            profils[cle] = {'forme': 'annee', 'annee': annee}
    return mesures, (profils or None)


def _part_indexee(levier):
    return C.RETRAITES_PART_MASSE_INDEXEE if levier == 'retraites' else 1.0


# --- 3.0 Constat avant correction : le retour à 1 efface-t-il l'écart ? ----

@pytest.mark.parametrize('cle', list(INDEXATIONS))
def test_p3_retour_a_la_pleine_indexation_conserve_l_ecart_de_niveau(cle):
    """Handler seul, monde unique, horloge au 01/01/2028, inflation 2027 connue :
    gel en 2028 (coefficient 0) puis coefficient 1 en 2029 et 2030. La
    revalorisation gelée de 2028 n'est jamais rattrapée : l'économie de 2029
    et 2030 vaut la masse de l'année × π₂₀₂₇ / (1 + π₂₀₂₇) (× part indexée des
    pensions). Avant la correction, le moteur recalculait tout l'écart au
    coefficient de l'année : économie nulle dès le retour à 1 (rattrapage
    complet implicite)."""
    levier, param, categorie = INDEXATIONS[cle]
    sim = _sim_neuf()
    sim._origines_courantes = {levier: 2028}
    sim._inflation_par_annee = {2026: 0.012, 2027: 0.018, 2028: 0.016, 2029: 0.02}
    pi = sim._inflation_par_annee[2027]
    masse = sim.masse_categorie_nominale(categorie)
    attendu = -_part_indexee(levier) * masse * pi / (1 + pi)
    neutre = {'indexation': 1.0, 'duree_cotisation': C.RETRAITES_REF_DUREE_ANS} if levier == 'retraites' \
        else {param: 1.0}
    gel = {**neutre, param: 0.0}
    for annee, params in ((2028, gel), (2029, neutre), (2030, neutre)):
        dep, _, impacts = _appel(sim, levier, dict(params), year=annee, inflation=0.017)
        assert dep == pytest.approx(attendu, rel=1e-12), (annee, dep, attendu)
        assert impacts['menages'] == canaux_menages(prestations=dep)


# --- 3.1 Calendrier « une seule année » ouvert sur les deux clés ------------

def test_p3_cles_eligibles_une_seule_annee_et_plein():
    for cle in INDEXATIONS:
        assert cle in cadre.PROFILS_ELIGIBLES, cle
        assert cadre.FORMES_ADMISES[cle] == ('plein', 'annee'), cle


@pytest.mark.parametrize('cle', list(INDEXATIONS))
def test_p3_rampe_refusee_sur_un_coefficient_d_indexation(cle):
    """La rampe n'est pas ouverte [choix documenté] : le coefficient s'applique
    à chaque revalorisation annuelle ; une montée progressive du coefficient
    n'est pas un calendrier qu'un programme écrit (gel ou sous-indexation
    d'une ou plusieurs années)."""
    mesures, _ = _gel([cle])
    with pytest.raises(cadre.ProfilInvalide, match='rampe'):
        cadre.CadreTemporel.preparer(mesures, DEBUT_CADRE, profils={cle: {'forme': 'rampe'}}, strict=True)


@pytest.mark.parametrize('cle', list(INDEXATIONS))
def test_p3_calendrier_une_annee_valeurs(cle):
    levier, param, _ = INDEXATIONS[cle]
    mesures, profils = _gel([cle], 2028)
    c = cadre.CadreTemporel.preparer(mesures, DEBUT_CADRE, profils=profils, strict=True)
    assert c.mesures_de_l_annee(2028)[levier][param] == 0.0
    for annee in range(2029, 2036):
        assert c.mesures_de_l_annee(annee)[levier][param] == 1.0, annee


# --- 3.2 Propriétés en simulation complète (mode cadre 2028) ----------------

@pytest.fixture(scope='module')
def _bancs_gel():
    out = {'statu_quo': _simuler_sonde({})}
    for cle in INDEXATIONS:
        out[(cle, 'annee')] = _simuler_sonde(*_gel([cle], 2028))
        out[(cle, 'permanent')] = _simuler_sonde(*_gel([cle]))
        out[(cle, 'annee2030')] = _simuler_sonde(*_gel([cle], 2030))
    out['deux'] = _simuler_sonde(*_gel(list(INDEXATIONS), 2028))
    return out


@pytest.mark.parametrize('cle', list(INDEXATIONS))
def test_p3_rapport_valide_sans_correction(cle, _bancs_gel):
    _, _, rapport = _bancs_gel[(cle, 'annee')]
    assert rapport['valid'] is True, rapport.get('warnings')
    assert rapport['cadre']['profils'][cle]['forme'] == 'annee'


@pytest.mark.parametrize('cle', list(INDEXATIONS))
def test_p3_premiere_annee_egale_au_gel_permanent(cle, _bancs_gel):
    """2028 : le gel d'une année et le gel permanent sont identiques au bit
    (sorties de l'année et impacts de tous les leviers)."""
    sa, da, _ = _bancs_gel[(cle, 'annee')]
    sp, dp, _ = _bancs_gel[(cle, 'permanent')]
    assert da.loc[2028].to_dict() == dp.loc[2028].to_dict()
    for cle_sonde, sortie in sa.sonde.items():
        if isinstance(cle_sonde, tuple) and cle_sonde[0] == 2028:
            assert sortie == sp.sonde[cle_sonde], cle_sonde


@pytest.mark.parametrize('cle', list(INDEXATIONS))
def test_p3_economie_2028_puis_ecart_conserve_et_revalorise(cle, _bancs_gel):
    """Économie de l'année t ≥ 2028 = part indexée × masse nominale de t ×
    π₂₀₂₇ / (1 + π₂₀₂₇) : la revalorisation de 2028 (sur l'inflation 2027) est
    gelée, l'écart de niveau est conservé et revalorisé ensuite avec la masse,
    aucun rattrapage (économie strictement positive chaque année)."""
    levier, _, categorie = INDEXATIONS[cle]
    sim, _, _ = _bancs_gel[(cle, 'annee')]
    pi = sim.sonde['inflation'][2027]
    assert pi > 0
    for annee in range(2028, 2036):
        dep = sim.sonde[(annee, levier)][0]
        masse = sim.sonde[(annee, 'masses')][categorie]
        attendu = -_part_indexee(levier) * masse * pi / (1 + pi)
        assert dep == pytest.approx(attendu, rel=1e-9), (annee, dep, attendu)
        assert dep < 0


@pytest.mark.parametrize('cle', list(INDEXATIONS))
def test_p3_gini_emis_au_gel_puis_part_realisee_au_retour(cle, _bancs_gel):
    """Gini : 2028 = le gel permanent (effet émis à l'ouverture) ; au retour de
    la revalorisation normale en 2029, le levier ne garde que la part réalisée,
    une revalorisation gelée sur son plateau de N (relecture adverse finale,
    I-1 : avant, il gardait tout, autant qu'un gel permanent) ; rien ensuite."""
    levier, _, _ = INDEXATIONS[cle]
    n = C.RETRAITES_EROSION_PLATEAU_ANS if levier == 'retraites' else C.PRESTATIONS_REVALORISATIONS_MAX
    sa, _, _ = _bancs_gel[(cle, 'annee')]
    sp, _, _ = _bancs_gel[(cle, 'permanent')]
    emis = sa.sonde[(2028, levier)][2]['gini']
    assert emis == sp.sonde[(2028, levier)][2]['gini'] > 0
    assert sa.sonde[(2029, levier)][2]['gini'] == pytest.approx(-(1 - 1 / n) * emis, rel=1e-12)
    for annee in range(2030, 2036):
        assert sa.sonde[(annee, levier)][2]['gini'] == pytest.approx(0.0, abs=1e-15), annee


@pytest.mark.parametrize('cle', list(INDEXATIONS))
def test_p3_pouvoir_d_achat_suit_la_depense(cle, _bancs_gel):
    """Canal ménages = la dépense chaque année (revenu retiré aux allocataires) ;
    l'indice de pouvoir d'achat (publié au dixième) reste sous le statu quo,
    strictement l'année du gel."""
    levier, _, _ = INDEXATIONS[cle]
    sa, da, _ = _bancs_gel[(cle, 'annee')]
    _, d0, _ = _bancs_gel['statu_quo']
    for annee in range(2028, 2036):
        dep, _, impacts = sa.sonde[(annee, levier)]
        assert impacts['menages']['prestations'] == pytest.approx(dep, rel=1e-12, abs=1e-12)
        assert da.at[annee, "Pouvoir d'Achat"] <= d0.at[annee, "Pouvoir d'Achat"], annee
    assert da.at[2028, "Pouvoir d'Achat"] < d0.at[2028, "Pouvoir d'Achat"]


@pytest.mark.parametrize('cle', list(INDEXATIONS))
def test_p3_aucun_residu_avant_le_gel(cle, _bancs_gel):
    """Gel en 2030 : jusqu'en 2029, les sorties sont celles du statu quo au bit
    (aucun résidu de la composition des horloges ni du calendrier)."""
    _, d, _ = _bancs_gel[(cle, 'annee2030')]
    _, d0, _ = _bancs_gel['statu_quo']
    for annee in range(2026, 2030):
        assert d.loc[annee].to_dict() == d0.loc[annee].to_dict(), annee


@pytest.mark.parametrize('cle', list(INDEXATIONS))
def test_p3_gel_2030_economie_a_l_inflation_2029(cle, _bancs_gel):
    levier, _, categorie = INDEXATIONS[cle]
    sim, _, _ = _bancs_gel[(cle, 'annee2030')]
    pi = sim.sonde['inflation'][2029]
    for annee in range(2028, 2036):
        dep = sim.sonde[(annee, levier)][0]
        if annee < 2030:
            assert dep == pytest.approx(0.0, abs=1e-12), annee
        else:
            masse = sim.sonde[(annee, 'masses')][categorie]
            assert dep == pytest.approx(-_part_indexee(levier) * masse * pi / (1 + pi), rel=1e-9), annee


def test_p3_deux_gels_ensemble_additifs_au_niveau_du_levier(_bancs_gel):
    """Pensions et prestations gelées ensemble : chaque levier rend sa propre
    économie de niveau (leurs assiettes sont disjointes)."""
    sim, _, rapport = _bancs_gel['deux']
    assert rapport['valid'] is True
    pi = sim.sonde['inflation'][2027]
    for cle, (levier, _, categorie) in INDEXATIONS.items():
        for annee in range(2028, 2033):
            dep = sim.sonde[(annee, levier)][0]
            masse = sim.sonde[(annee, 'masses')][categorie]
            assert dep == pytest.approx(-_part_indexee(levier) * masse * pi / (1 + pi), rel=1e-9)


@pytest.mark.parametrize('cle', list(INDEXATIONS))
def test_p3_api_strict_une_annee_acceptee_rampe_refusee(cle, monkeypatch):
    import importlib.util
    from fastapi.testclient import TestClient
    spec = importlib.util.spec_from_file_location('api_arbitrages_p3', RACINE / 'api.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    client = TestClient(module.app, raise_server_exceptions=False)
    monkeypatch.setenv('BUDGETLAB_STRICT', '1')
    mesures, profils = _gel([cle], 2028)
    r = client.post('/simulate', json={'periods': 10, 'annee_debut': DEBUT_CADRE,
                                        'mesures': mesures, 'profils': profils})
    assert r.status_code == 200, r.text[:500]
    assert r.json()['cadre']['profils'][cle]['forme'] == 'annee'
    r = client.post('/simulate', json={'periods': 10, 'annee_debut': DEBUT_CADRE, 'mesures': mesures,
                                        'profils': {cle: {'forme': 'rampe'}}})
    assert r.status_code == 422, r.text[:500]


# ===========================================================================
# 4. Droits de succession : borne haute +25 Md€ (décision 3 du mainteneur ;
#    la borne +20 n'était pas sourcée) et avertissement sourcé dans
#    l'infobulle, sans décote dans le calcul.
# ===========================================================================

SUCC = 'droits_succession'


def test_p4_borne_haute_nommee_et_appliquee():
    assert C.DMTG_VARIATION_MAX_MD == 25.0
    spec = REGISTRE[SUCC]['parametres']['variation']
    assert spec['max'] == C.DMTG_VARIATION_MAX_MD
    assert spec['min'] == -C.DMTG_2025_MD          # borne basse sourcée inchangée
    assert PARAM_DOMAINS[SUCC]['variation'] == (-C.DMTG_2025_MD, C.DMTG_VARIATION_MAX_MD) or \
        tuple(PARAM_DOMAINS[SUCC]['variation']) == (-C.DMTG_2025_MD, C.DMTG_VARIATION_MAX_MD)


def _verifier_aucune_decote(montant):
    """Recette = montant écrit, chaque année : aucune décote d'évitement."""
    _, rec, impacts = _appel(_sim_neuf(), SUCC, {'variation': montant})
    assert rec == montant
    assert impacts['recettes'] == montant


@pytest.mark.parametrize('montant', [20.0, 22.5, 25.0])
def test_p4_au_dela_de_vingt_sans_decote(montant):
    _verifier_aucune_decote(montant)


def test_p4_vingt_cinq_accepte_en_strict_sans_ecretage():
    import os
    from unittest.mock import patch
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1'}):
        df, _, rapport = BudgetSimulatorV45(periods=10, mesures={SUCC: {'variation': 25.0}},
                                            annee_debut=DEBUT_CADRE).simulate()
    assert rapport['valid'] is True and rapport['leviers_ecretes'] == []
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': ''}):
        _, _, rapport = BudgetSimulatorV45(periods=10, mesures={SUCC: {'variation': 25.5}},
                                           annee_debut=DEBUT_CADRE).simulate()
    lignes = [l for l in rapport['leviers_ecretes'] if l['levier'] == f'{SUCC}.variation']
    assert lignes and lignes[0]['applique'] == C.DMTG_VARIATION_MAX_MD


def test_p4_infobulle_avertissement_source_sans_nom_de_parti():
    """Avertissement sourcé (dossier du dépôt parent
    docs/plans/evitement-successions-sources-2026-11.md, citations vérifiées) :
    au sommet, environ 10 % payés contre 45 % affichés ; pour une forte hausse,
    la part évitée n'est pas chiffrable et dépend de la fermeture des
    dispositifs dérogatoires ; le montant est compté sans décote."""
    tooltip = REGISTRE[SUCC]['parametres']['variation']['tooltip']
    for motif in ('« un taux effectif d’imposition de 10,7 % »', '44,4 %', 'Cour des comptes',
                  '« ne paie qu’à peine 10 % de droits de succession sur l’ensemble de ce patrimoine hérité, '
                  'bien loin du taux marginal de 45 % affiché par le barème »',
                  'dispositifs dérogatoires', 'sans décote'):
        assert motif in tooltip, (motif, tooltip)
    assert 'aucune étude' in tooltip.lower()


@pytest.mark.parametrize('levier, param', [('droits_succession', 'variation'),
                                           ('cotisations_salariales', 'baisse_points'),
                                           ('sante', 'prevention_budget')])
def test_infobulles_modifiees_neutres(levier, param):
    """Aucun nom de parti, de candidat ni d'identifiant de scénario dans les
    infobulles modifiées par ces arbitrages : garde de neutralité de la release
    (liste d'exclusion tenue par empreintes, aucun nom écrit dans le dépôt)."""
    from test_release_e_socle import _nom_politique
    assert _nom_politique(REGISTRE[levier]['parametres'][param]['tooltip']) is None


# ===========================================================================
# 5. Prévention en santé : références corrigées (dossier du dépôt parent
#    docs/plans/prevention-sante-sources-2026-11.md, 57 citations vérifiées) ;
#    infobulle : borne du RETOUR MODÉLISÉ, retour de 50 % = hypothèse haute.
#    Base 7,5 et borne 11,2 inchangées : aucune sortie ne bouge.
# ===========================================================================

_PREV_FICHIERS = ([RACINE / 'budget_simulator' / 'constants.py', RACINE / 'policy_measures.json',
                   RACINE / 'tests' / 'test_prevention_v061.py']
                  + sorted((RACINE / 'docs').glob('*.md'))
                  + sorted((RACINE / 'budget_simulator' / 'handlers').glob('*.py')))
# Références fausses relevées par le dossier : (libellé, motif).
_PREV_FAUSSES = {
    'pseudo-citation IGAS absente du rapport': r"en l.absence d.une [ée]valuation structur[ée]e en France",
    '« Cash & Fourcade 2023 § 45 »': r"Cash\s*&\s*Fourcade\s+2023",
    '« 21 mesures dominantes sur 150 »': r"21 mesures \**(dominantes|DOMINANTES)\** sur 150",
    '« ≈ 7,6 Md€ » en 2024 (série DREES révisée)': r"soit ≈ 7,6 Md€|soit ≈ 7,6 Md EUR",
    'rapport de la Cour des comptes de décembre 2021 dit introuvable':
        r"Cour des comptes daté de 2021 sur le rendement",
}


@pytest.mark.parametrize('libelle, motif', sorted(_PREV_FAUSSES.items()))
def test_p5_references_fausses_retirees(libelle, motif):
    fautifs = [str(f.relative_to(RACINE)) for f in _PREV_FICHIERS
               if re.search(motif, f.read_text(encoding='utf-8'))]
    assert not fautifs, (libelle, fautifs)


def test_p5_references_exactes_presentes():
    constants = CONSTANTS_PY.read_text(encoding='utf-8')
    methodo = (RACINE / 'docs' / 'METHODOLOGIE.md').read_text(encoding='utf-8')
    for texte, nom in ((constants, 'constants.py'), (methodo, 'METHODOLOGIE.md')):
        # Fourcade & Cash, Regards n° 61 (EN3S), mai 2023, p. 41.
        assert re.search(r'Regards\*? n° 61', texte), nom
        # ACE-Prevention : 23 interventions préventives dominantes sur 123.
        assert re.search(r'23 interventions pr[ée]ventives \**dominantes\** sur 123', texte), nom
        # Série DREES révisée, citée avec sa source.
        assert '8 731' in texte and 'PLFSS 2026' in texte, nom
        # Le rapport de la Cour des comptes de décembre 2021 existe.
        assert 'La politique de prévention en santé' in texte, nom
    # Citation IGAS vérifiée au PDF (synthèse, p. 2).
    texte_test = ' '.join((RACINE / 'tests' / 'test_prevention_v061.py').read_text(encoding='utf-8').split())
    assert "est encore peu structuré en France, et mobilise de façon insuffisante des analyses" in texte_test


def test_p5_infobulle_borne_du_retour_et_hypothese_haute():
    tooltip = REGISTRE['sante']['parametres']['prevention_budget']['tooltip']
    # Le curseur borne la DÉPENSE (relecture adverse finale, m-b) ; le surplus
    # se saisit en dépense de soins, sans retour modélisé.
    assert 'borne la dépense de prévention' in tooltip and 'sans retour modélisé' in tooltip, tooltip
    assert 'hypothèse haute' in tooltip, tooltip
    assert '8 731' in tooltip, tooltip


def test_p5_base_et_borne_inchangees():
    assert C.PREVENTION_BASE_MD_EUR == 7.5
    assert C.PREVENTION_PLAFOND_MD_EUR == 11.2
    spec = REGISTRE['sante']['parametres']['prevention_budget']
    assert (spec['min'], spec['max'], spec['valeur_defaut']) == (7.5, 11.2, 7.5)


# ===========================================================================
# 6. TVA à taux réduits : passage dans les prix sur l'INCRÉMENT annuel positif
#    de la recette (contre-vérification I1), chaque marche plafonnée, passage
#    négatif symétrique quand une hausse antérieure est retirée ; règle
#    d'addition avec tva_rate : seules les hausses s'additionnent avant le
#    plafond commun (m1) ; tva_rate inchangé au bit.
# ===========================================================================

PIB_SONDE = 3300.0
PASSAGE_COEF, PASSAGE_PLAFOND = 0.3, 0.002   # règle du passage de tva_rate (inflation.py)


def _etat_neutre(**autres):
    """Entrées de calculate_inflation au point fixe (écart nul, aucun effort) :
    l'inflation reste dans la zone linéaire (ni rappel BCE ni plancher), si bien
    que l'écart entre deux appels égale exactement le passage ajouté."""
    return {'output_gap': 0.0, 'unemployment_gap': 0.0, 'effort_budgetaire': 0.0,
            'tva_impact': 0.0, 'annee_pass_through_tva': 2, 'pib_nominal': PIB_SONDE, **autres}


def _passages(recettes, tva_impacts=None, annee_tva=None):
    """Passage dans les prix année par année (index 1, 2, …) pour une suite de
    recettes de TVA à taux réduits (Md€, lues à t−1) et, facultatif, d'impacts
    de tva_rate (part du PIB) : écart d'inflation entre deux moteurs au même
    état, l'un avec les entrées, l'autre sans."""
    avec, sans = BudgetSimulatorV45(periods=1), BudgetSimulatorV45(periods=1)
    out = []
    for i, recette in enumerate(recettes, start=1):
        inertie = 0.015
        avec.inflation_precedente = sans.inflation_precedente = inertie
        extra = {'tva_reduite_recette_md': recette}
        if tva_impacts is not None:
            extra.update(tva_impact=tva_impacts[i - 1], annee_pass_through_tva=annee_tva)
        pa = avec.calculate_inflation(i, _etat_neutre(**extra))
        ps = sans.calculate_inflation(i, _etat_neutre())
        out.append(pa - ps)
    return out


def _attendu(delta_md):
    return min(PASSAGE_COEF * delta_md / PIB_SONDE, PASSAGE_PLAFOND)


def test_p6_plein_un_seul_passage_inchange():
    """« Chaque année » : la recette apparaît une fois (passage l'année qui suit
    son entrée), puis reste constante : aucun autre passage."""
    p = _passages([0.0, 10.0, 10.0, 10.0])
    assert p[0] == 0.0 and p[2] == 0.0 and p[3] == 0.0
    assert p[1] == pytest.approx(_attendu(10.0), abs=1e-15)


def test_p6_rampe_chaque_marche_passe():
    """Rampe 3 → 15 Md€ : chaque marche positive passe dans les prix ; la somme
    vaut le passage d'une hausse « pleine » de même montant (hors plafond)."""
    marches = [0.0, 3.0, 6.0, 9.0, 12.0, 15.0, 15.0]
    p = _passages(marches)
    for i in range(1, 6):
        assert p[i] == pytest.approx(_attendu(3.0), abs=1e-15), (i, p)
    assert p[6] == 0.0
    assert sum(p) == pytest.approx(_attendu(15.0), abs=1e-15)


def test_p6_chaque_marche_plafonnee():
    """Une marche de 30 Md€ (0,27 point brut au PIB sonde) est plafonnée à
    0,2 point ; la suivante, plafonnée elle aussi, s'y ajoute."""
    p = _passages([0.0, 30.0, 60.0])
    assert p[1] == pytest.approx(PASSAGE_PLAFOND, abs=1e-15)
    assert p[2] == pytest.approx(PASSAGE_PLAFOND, abs=1e-15)


def _verifier_retrait_symetrique():
    """Hausse d'une seule année (+15 puis 0) : le passage de la hausse est
    rendu, au même montant, l'année où elle est retirée ; rien ensuite."""
    p = _passages([0.0, 15.0, 0.0, 0.0])
    assert p[1] == pytest.approx(_attendu(15.0), abs=1e-15)
    assert p[2] == pytest.approx(-p[1], abs=1e-15)
    assert p[3] == 0.0


def test_p6_hausse_retiree_passage_negatif_symetrique():
    _verifier_retrait_symetrique()


def test_p6_retrait_partiel_proportionnel():
    p = _passages([0.0, 15.0, 5.0, 5.0])
    assert p[1] > 0, ('NON_VACUITE', p)
    assert p[2] == pytest.approx(-p[1] * 10.0 / 15.0, abs=1e-15)
    assert p[3] == 0.0


def test_p6_baisse_seule_ne_passe_pas():
    """Une baisse (recette négative) ne passe pas dans les prix (règle de
    tva_rate), ni à l'entrée ni au retrait."""
    assert _passages([0.0, -15.0, -15.0, 0.0]) == [0.0, 0.0, 0.0, 0.0]


def test_p6_tva_rate_inchange_au_bit():
    """tva_rate seul : passage = min(0,3 × impact, 0,2 point), l'année de son
    horloge seulement — la règle de v0.7.2, au bit."""
    for impact in (0.001, 0.004, 0.01, -0.004):
        p = _passages([0.0, 0.0, 0.0], tva_impacts=[0.0, impact, impact], annee_tva=2)
        attendu = min(impact * PASSAGE_COEF, PASSAGE_PLAFOND) if impact > 0 else 0.0
        assert p[1] == attendu or abs(p[1] - attendu) <= 1e-17, (impact, p)
        assert p[0] == p[2] == 0.0


def test_p6_addition_seules_les_hausses_avant_le_plafond_commun():
    """m1 : une baisse de TVA à taux réduits la même année n'annule pas le
    passage d'une hausse de tva_rate ; deux hausses s'additionnent avant le
    plafond commun."""
    impact = 15.0 / PIB_SONDE
    seule = _passages([0.0, 0.0], tva_impacts=[0.0, impact], annee_tva=2)
    melee = _passages([0.0, -15.0], tva_impacts=[0.0, impact], annee_tva=2)
    assert melee[1] == seule[1] > 0
    deux = _passages([0.0, 15.0], tva_impacts=[0.0, impact], annee_tva=2)
    assert deux[1] == pytest.approx(min(PASSAGE_COEF * 2 * impact, PASSAGE_PLAFOND), abs=1e-15)


def test_p6_simulation_hausse_d_une_annee_proche_d_une_recette_exceptionnelle():
    """Mode cadre 2028, +15 Md€ en 2028 seulement : l'inflation monte en 2029
    puis le passage est rendu en 2030 ; l'avantage sur la dette 2032 par
    rapport à une recette exceptionnelle du même montant la même année
    (≈ 0,34 point avant la correction) disparaît presque (< 0,1 point)."""
    def dette(mesures, profils):
        df, _, r = BudgetSimulatorV45(periods=10, mesures=mesures, annee_debut=DEBUT_CADRE,
                                      profils=profils).simulate()
        assert r['valid'] is True, r['warnings']
        return df.set_index('Année')
    tva = dette({'fiscalite_indirecte': {'tva_ciblee': 15.0}},
                {'fiscalite_indirecte.tva_ciblee': {'forme': 'annee', 'annee': 2028}})
    exc = dette({'recette_exceptionnelle': {'montant': 15.0}},
                {'recette_exceptionnelle.montant': {'forme': 'annee', 'annee': 2028}})
    assert abs(tva.at[2032, 'Dette/PIB %'] - exc.at[2032, 'Dette/PIB %']) < 0.1, (
        tva.at[2032, 'Dette/PIB %'], exc.at[2032, 'Dette/PIB %'])
    assert tva.at[2029, 'Inflation %'] > exc.at[2029, 'Inflation %']
    assert tva.at[2030, 'Inflation %'] < exc.at[2030, 'Inflation %']


# ===========================================================================
# 8. Mineurs de la contre-vérification adverse
# ===========================================================================

import copy  # noqa: E402

from budget_simulator.constants import CHOMAGE_MONTANT_REF_MD, CHOMAGE_TAUX_REF  # noqa: E402

_DROIT_FICHIER = json.loads((RACINE / 'budget_simulator' / 'data' / 'droit_en_vigueur.json')
                            .read_text(encoding='utf-8'))


def _droit_injecte(modifier):
    mesures = copy.deepcopy(_DROIT_FICHIER['mesures'])
    modifier(mesures)
    return cadre.DroitEnVigueur('t', 't', 't', '2026-11-12', mesures)


# --- m2 : référence du budget chômage en montant, convertie du taux du droit --

def test_m2_reference_du_montant_convertie_du_taux_du_droit():
    """Le droit écrit le budget chômage en TAUX : la référence d'un calendrier
    sur le MONTANT est le montant équivalent au taux du droit (formule du
    handler : MONTANT_REF × taux / TAUX_REF), jamais le défaut du moteur."""
    for taux in (0.57, 0.60, 0.65):
        droit = {'chomage_alloc': {'taux_remplacement': taux, 'duree': 18, 'degressivite': False}}
        attendu = CHOMAGE_MONTANT_REF_MD * (taux / CHOMAGE_TAUX_REF)
        assert cadre.reference_du_profil('chomage_alloc', 'montant', droit) == attendu, taux
    # Droit livré (0,60 = taux de référence) : 36,6 exactement, au bit.
    assert cadre.reference_du_profil('chomage_alloc', 'montant', _DROIT_FICHIER['mesures']) == \
        CHOMAGE_MONTANT_REF_MD


def test_m2_rampe_part_du_montant_equivalent_au_droit():
    """Droit injecté à 0,57 : la rampe vers 24,85 Md€ part de 34,77 Md€ (montant
    équivalent), pas de 36,6 (défaut du moteur) : ≈ 3,7 Md€ d'économies
    sous-comptées sur 2028-2031 avant la correction (contre-vérification m2)."""
    droit = _droit_injecte(lambda m: m['chomage_alloc'].update(taux_remplacement=0.57))
    c = cadre.CadreTemporel.preparer({'chomage_alloc': {'montant': 24.85}}, DEBUT_CADRE, droit=droit,
                                     profils={'chomage_alloc.montant': {'forme': 'rampe'}}, strict=True)
    ref = CHOMAGE_MONTANT_REF_MD * (0.57 / CHOMAGE_TAUX_REF)
    n = C.ANNEE_FIN_MANDAT - DEBUT_CADRE + 1
    for annee in range(DEBUT_CADRE, C.ANNEE_FIN_MANDAT):
        k = annee - DEBUT_CADRE + 1
        assert c.mesures_de_l_annee(annee)['chomage_alloc']['montant'] == pytest.approx(
            ref + (24.85 - ref) * k / n, rel=1e-12), annee
    assert c.mesures_de_l_annee(C.ANNEE_FIN_MANDAT)['chomage_alloc']['montant'] == 24.85


# --- m4 : retour anticipé des cotisations salariales conditionné au traqueur --

def test_m4_retour_a_zero_rend_l_effet_ponctuel():
    """Handler seul, même monde : 1,2 puis 0,6 puis 0 point. Les émissions de
    Gini (incréments) se somment à 0 au retour au neutre : le handler ne sort
    plus avant de rendre l'incrément quand un effet a été émis."""
    sim = _sim_neuf()
    emis = [_appel(sim, COTIS, {'baisse_points': b})[2].get('gini', 0.0) for b in (1.2, 0.6, 0.0, 0.0)]
    assert emis[0] > 0 and emis[1] < 0
    assert emis[2] == pytest.approx(-(emis[0] + emis[1]), abs=1e-15), emis
    assert sum(emis) == pytest.approx(0.0, abs=1e-15)
    assert emis[3] == 0.0


def test_m4_neutre_sans_effet_emis_sortie_inchangee():
    """Jamais déclenché : sortie anticipée inchangée (0, 0, {}), au bit."""
    assert _appel(_sim_neuf(), COTIS, {'baisse_points': 0}) == (0.0, 0.0, {})


def test_m4_rampe_vers_zero_sous_une_valeur_datee(monkeypatch, tmp_path):
    """Droit injecté : baisse de 3 points datée dès 2030. Programme 0 en rampe
    (référence : le droit de l'année) : 2030 1,2 ; 2031 0,6 ; 2032 0. Le Gini
    émis par le levier se somme à 0, et le Gini publié en 2035 égale celui du
    même programme « chaque année » (preuve du relecteur : +0,00162 de reste)."""
    droit = copy.deepcopy(_DROIT_FICHIER)
    droit['valeurs_datees'] = {'cotisations_salariales': {'baisse_points': [
        {'de': 2026, 'a': 2029, 'valeur': 0, 'source': 'banc'},
        {'de': 2030, 'valeur': 3, 'source': 'banc'}]}}
    chemin = tmp_path / 'droit.json'
    chemin.write_text(json.dumps(droit, ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(cadre, 'DROIT_EN_VIGUEUR_PATH', chemin)
    cadre.vider_caches()
    try:
        rampe = _simuler_sonde({COTIS: {'baisse_points': 0}},
                               {f'{COTIS}.baisse_points': {'forme': 'rampe'}})
        plein = _simuler_sonde({COTIS: {'baisse_points': 0}})
    finally:
        monkeypatch.undo()
        cadre.vider_caches()
    sim, d, rapport = rampe
    assert rapport['valid'] is True
    emis = [sim.sonde[(a, COTIS)][2].get('gini', 0.0) for a in range(2026, 2036)]
    assert any(abs(g) > 0 for g in emis), ('NON_VACUITE', emis)
    assert sum(emis) == pytest.approx(0.0, abs=1e-12), emis
    assert d.at[2035, 'Gini'] == plein[1].at[2035, 'Gini']


# --- m5 : l'alias « rampe » (v0.7.0) borné comme les profils -----------------

@pytest.mark.parametrize('debut, annees, borne', [(2028, 6, 5), (2031, 6, 2), (2032, 3, 1), (2027, 6, 6)])
def test_m5_alias_rampe_finit_au_plus_tard_en_2032(debut, annees, borne):
    """Comme un profil « rampe » : début + annees − 1 ≤ 2032. Tolérant :
    ramené à la borne, correction tracée ; strict : RampeInvalide. Dans le
    domaine (2027, 6 ans), aucune correction."""
    prog = {'defense': {'budget': 70}}
    demande = {'annees': annees, 'leviers': ['defense.budget']}
    corrections = {}
    c = cadre.CadreTemporel.preparer(prog, debut, rampe=demande, strict=False, warned=set(),
                                     corrections=corrections)
    assert c.etat.rampe.annees == borne, (debut, annees, c.etat.rampe)
    assert bool(corrections) is (borne != annees), corrections
    if borne != annees:
        with pytest.raises(cadre.RampeInvalide, match='2032'):
            cadre.CadreTemporel.preparer(prog, debut, rampe=demande, strict=True)
    fin = debut + borne - 1
    assert fin <= C.ANNEE_FIN_MANDAT
    assert c.mesures_de_l_annee(fin)['defense']['budget'] == 70


# --- m6 : filet de croissance [−3,5 % ; +2,5 %] : avis tracé -----------------

PROGRAMME_RELANCE = {'transition_ecologique': {'investissement': 50, 'renovation': 40},
                     'recherche_publique': {'budget': 20}, 'collectivites': {'investissement': 20},
                     'depenses_publiques': {'credits_etat': 20}}


def _avis_filet(rapport):
    return [w for w in rapport['warnings'] if w.startswith('Avis') and 'filet de croissance' in w]


@pytest.mark.parametrize('annee_debut', [None, DEBUT_CADRE], ids=['historique', 'cadre2028'])
def test_m6_filet_de_croissance_avis_trace_sans_invalider(annee_debut):
    """Le filet ramène la croissance dans [−3,5 % ; +2,5 %] : un avis le dit,
    avec chaque année et la valeur calculée avant écrêtage ; le rapport reste
    valide (l'entrée a été lue telle quelle)."""
    df, _, rapport = BudgetSimulatorV45(periods=10, mesures=PROGRAMME_RELANCE,
                                        annee_debut=annee_debut).simulate()
    assert rapport['valid'] is True, rapport['warnings']
    avis = _avis_filet(rapport)
    assert len(avis) == 1, rapport['warnings']
    croissance = df.set_index('Année')['Croissance %']
    annees = [int(a) for a, c in croissance.items() if c == 2.5]
    assert annees, ('NON_VACUITE', croissance.to_dict())
    for annee in annees:
        m = re.search(rf'{annee} \(([\d,]+) % calculés', avis[0])
        assert m, (annee, avis[0])
        assert float(m.group(1).replace(',', '.')) > 2.5, (annee, avis[0])


def test_m6_aucun_avis_sans_filet():
    _, _, rapport = BudgetSimulatorV45(periods=10, mesures={}, annee_debut=DEBUT_CADRE).simulate()
    assert _avis_filet(rapport) == []


def test_m6_bornes_nommees():
    assert (C.CROISSANCE_FILET_MIN, C.CROISSANCE_FILET_MAX) == (-0.035, 0.025)
