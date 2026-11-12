"""Release P (v0.8.1) — calendrier « valeurs » (forme de profil) : le montant de chaque année, du début à une année
≤ 2032, sans lacune ; ensuite la valeur du programme (décision du mainteneur du 12/11/2026 : un objectif écrit en part
du PIB ou du RNB se compte, après l'année visée, par un montant qui suit la richesse nationale). Les handlers lisent ces
valeurs comme celles d'une rampe (même chemin : ``_mesures_profilees``) ; aucune équation ne change, ce que prouve
l'égalité AU BIT avec une rampe aux mêmes valeurs. Réservé aux montants en Md€ (ni taux, ni coefficient d'indexation,
ni recette d'une seule année) ; chaque valeur est dans le domaine du paramètre. Strict : 422 (``ProfilInvalide``) ;
tolérant : entrée ignorée, correction tracée. Données de test : aucune n'est un programme publié.
"""
import copy
import math
from pathlib import Path

import pytest

import budget_simulator.constants as C
import budget_simulator.engine.cadre as cadre

from cadre_harness import egalite_bit_a_bit, impacts_par_annee, simuler

RACINE = Path(__file__).absolute().parent.parent
DEBUT = C.ANNEE_PREMIER_BUDGET_MANDAT
FIN = C.ANNEE_FIN_MANDAT

CLES_MONTANTS = sorted(cadre.PROFILS_ELIGIBLES - cadre.PROFILS_TAUX_ET_NIVEAUX
                       - cadre.PROFILS_INDEXATIONS - {cadre.CLE_RECETTE_EXCEPTIONNELLE})
CLES_SANS_VALEURS = sorted(cadre.PROFILS_TAUX_ET_NIVEAUX | cadre.PROFILS_INDEXATIONS
                           | {cadre.CLE_RECETTE_EXCEPTIONNELLE})
# Données de test (aucune n'est un programme publié).
CLE = 'recherche_publique.budget'
VALEURS = {'2028': 12.5, '2029': 15.0, '2030': 17.5, '2031': 17.9, '2032': 18.3}
P = 18.3


def _programme(cle, valeur):
    levier, param = cle.split('.')
    return {levier: {param: valeur}}


def _valeur(c, cle, annee):
    levier, param = cle.split('.')
    return c.mesures_de_l_annee(annee)[levier][param]


def _preparer(profils, programme=None, debut=DEBUT, strict=True, corrections=None):
    return cadre.CadreTemporel.preparer(programme if programme is not None else _programme(CLE, P),
                                        debut, profils=profils, strict=strict, warned=set(),
                                        corrections=corrections)


def test_forme_valeurs_admise_pour_les_montants_seulement():
    assert 'valeurs' in cadre.FORMES_PROFIL
    for cle in CLES_MONTANTS:
        assert 'valeurs' in cadre.FORMES_ADMISES.get(cle, cadre.FORMES_PROFIL), cle
    for cle in CLES_SANS_VALEURS:
        assert 'valeurs' not in cadre.FORMES_ADMISES[cle], cle
    assert {'recherche_publique.budget', 'transferts_etranger.montant',
            'depenses_publiques.credits_etat'} <= set(CLES_MONTANTS)


@pytest.mark.parametrize('cle', CLES_SANS_VALEURS)
def test_forme_valeurs_refusee_hors_montants(cle):
    with pytest.raises(cadre.ProfilInvalide, match='valeurs'):
        _preparer({cle: {'forme': 'valeurs', 'valeurs': {'2028': 1.0}}}, programme=_programme(cle, 1.0))


@pytest.mark.parametrize('debut', [2027, 2028, 2030])
def test_valeurs_appliquees_chaque_annee_puis_la_valeur_du_programme(debut):
    valeurs = {str(a): 11.0 + (a - debut) * 1.5 for a in range(debut, FIN + 1)}
    p = 30.0
    c = _preparer({CLE: {'forme': 'valeurs', 'valeurs': valeurs}}, programme=_programme(CLE, p),
                  debut=debut)
    for an in range(debut, 2036):
        attendu = valeurs[str(an)] if an <= FIN else p
        assert _valeur(c, CLE, an) == attendu, an
    publie = c.rapport_profils()[CLE]
    assert publie['forme'] == 'valeurs'
    assert publie['valeurs'] == {str(a): valeurs[str(a)] for a in range(debut, FIN + 1)}
    assert publie['origine'] == debut


def test_valeurs_jusqu_a_une_annee_anterieure_a_2032():
    c = _preparer({CLE: {'forme': 'valeurs', 'valeurs': {'2028': 12.0, '2029': 14.0}}},
                  programme=_programme(CLE, 16.0))
    assert [_valeur(c, CLE, a) for a in range(2028, 2034)] == [12.0, 14.0, 16.0, 16.0, 16.0, 16.0]


def test_cles_d_annee_entieres_acceptees_comme_le_texte():
    a = _preparer({CLE: {'forme': 'valeurs', 'valeurs': VALEURS}})
    b = _preparer({CLE: {'forme': 'valeurs', 'valeurs': {int(k): v for k, v in VALEURS.items()}}})
    assert [_valeur(a, CLE, y) for y in range(2028, 2036)] == [_valeur(b, CLE, y) for y in range(2028, 2036)]


def test_valeurs_sans_effet_si_la_valeur_du_programme_egale_la_reference():
    """Règle de tous les calendriers : un paramètre que le programme laisse à sa référence n'a
    rien à étaler (avis « calendrier sans effet »). Un calendrier « valeurs » dont TOUS les montants
    égalent la référence est accepté avec cet avis (rien n'est perdu, ``report.valid`` inchangé)."""
    avis, corrections = {}, {}
    c = cadre.CadreTemporel.preparer(_programme('transferts_etranger.montant', 0.0), DEBUT,
                                     profils={'transferts_etranger.montant': {
                                         'forme': 'valeurs', 'valeurs': {'2028': 0.0, '2029': 0}}},
                                     strict=True, warned=set(), avis=avis, corrections=corrections)
    for an in range(DEBUT, 2036):
        assert 'transferts_etranger' not in c.mesures_de_l_annee(an), an
    assert avis and not corrections


# Montants datés qui s'écartent de la référence (0 Md€ au droit livré) alors que la valeur du
# programme l'égale ou est absente : ils seraient ignorés (zéro échec silencieux, revue du moteur).
SANS_EFFET_FAUTIFS = {
    'programme à la référence': _programme('transferts_etranger.montant', 0.0),
    'levier absent du programme': {},
}


@pytest.mark.parametrize('nom', sorted(SANS_EFFET_FAUTIFS))
def test_valeurs_qui_s_ecartent_d_une_reference_inchangee_refusees_en_strict(nom):
    with pytest.raises(cadre.ProfilInvalide, match=r'transferts_etranger\.montant.*valeurs.*référence'):
        cadre.CadreTemporel.preparer(copy.deepcopy(SANS_EFFET_FAUTIFS[nom]), DEBUT, strict=True,
                                     warned=set(), avis={},
                                     profils={'transferts_etranger.montant': {
                                         'forme': 'valeurs', 'valeurs': {'2028': 1.0, '2029': 0.0}}})


@pytest.mark.parametrize('nom', sorted(SANS_EFFET_FAUTIFS))
def test_valeurs_qui_s_ecartent_d_une_reference_inchangee_ignorees_et_tracees_en_tolerant(nom):
    avis, corrections = {}, {}
    c = cadre.CadreTemporel.preparer(copy.deepcopy(SANS_EFFET_FAUTIFS[nom]), DEBUT, strict=False,
                                     warned=set(), avis=avis, corrections=corrections,
                                     profils={'transferts_etranger.montant': {
                                         'forme': 'valeurs', 'valeurs': {'2028': 1.0, '2029': 2.0}}})
    assert any('transferts_etranger.montant' in t and 'référence' in t for t in corrections.values()), \
        corrections
    assert 'transferts_etranger.montant' not in c.etat.profils
    assert 'transferts_etranger.montant' not in c.rapport_profils()
    for an in range(DEBUT, 2036):
        assert 'transferts_etranger' not in c.mesures_de_l_annee(an), an
    # Une correction, pas un avis : l'entrée n'est pas comptée deux fois.
    assert not any('transferts_etranger' in t for t in avis.values()), avis


def test_valeurs_sans_effet_fautives_n_alterent_pas_les_autres_calendriers():
    """Tolérant : seule l'entrée fautive est ignorée ; un autre calendrier de la requête reste appliqué
    au bit comme sans elle."""
    programme = {**_programme(CLE, P)}
    seul = _preparer({CLE: {'forme': 'valeurs', 'valeurs': VALEURS}}, programme=programme, strict=False,
                     corrections={})
    corrections = {}
    avec = _preparer({CLE: {'forme': 'valeurs', 'valeurs': VALEURS},
                      'transferts_etranger.montant': {'forme': 'valeurs', 'valeurs': {'2028': 3.0}}},
                     programme=programme, strict=False, corrections=corrections)
    assert corrections
    for an in range(DEBUT, 2036):
        assert avec.mesures_de_l_annee(an) == seul.mesures_de_l_annee(an), an
    assert avec.rapport_profils() == seul.rapport_profils()


def test_api_valeurs_sans_effet_fautives_422_en_strict_et_valid_false_en_tolerant(monkeypatch):
    corps = {'periods': 10, 'annee_debut': DEBUT, 'mesures': {},
             'profils': {'transferts_etranger.montant': {'forme': 'valeurs', 'valeurs': {'2028': 2.0}}}}
    monkeypatch.setenv('BUDGETLAB_STRICT', '1')
    client = _client()
    r = client.post('/simulate', json=corps)
    assert r.status_code == 422, r.text[:500]
    assert 'transferts_etranger.montant' in r.json()['detail'] and 'référence' in r.json()['detail']
    monkeypatch.setenv('BUDGETLAB_STRICT', '')
    r = client.post('/simulate', json=corps)
    assert r.status_code == 200, r.text[:500]
    rapport = r.json()['report']
    assert rapport['valid'] is False
    assert any('transferts_etranger.montant' in str(w) for w in rapport['warnings'])
    assert 'transferts_etranger.montant' not in r.json()['cadre']['profils']


@pytest.mark.parametrize('cle,p', [('recherche_publique.budget', 36.0),
                                   ('transferts_etranger.montant', 10.0),
                                   ('depenses_publiques.credits_etat', 26.0)])
def test_egal_au_bit_a_une_rampe_aux_memes_valeurs(cle, p):
    """Aucune équation nouvelle : un calendrier « valeurs » aux valeurs d'une rampe donne les
    mêmes résultats AU BIT que la rampe (mêmes mesures de chaque année, même chemin)."""
    programme = _programme(cle, p)
    rampe = simuler(programme, annee_debut=DEBUT, profils={cle: {'forme': 'rampe'}}, strict=True)
    appliquees = rampe[2]['cadre']['profils'][cle]['valeurs']
    datees = simuler(programme, annee_debut=DEBUT, strict=True,
                     profils={cle: {'forme': 'valeurs', 'valeurs': appliquees}})
    assert datees[2]['cadre']['profils'][cle]['valeurs'] == appliquees
    egalite_bit_a_bit(rampe, datees, libelle=cle)


def test_effet_direct_de_chaque_annee_egal_au_montant_date():
    _, _, rapport, _ = simuler(_programme(CLE, P), annee_debut=DEBUT, strict=True,
                               profils={CLE: {'forme': 'valeurs', 'valeurs': VALEURS}})
    impacts = impacts_par_annee(rapport)
    for an in range(DEBUT, 2036):
        attendu = (VALEURS[str(an)] if an <= FIN else P) - 10
        assert impacts[an]['recherche_publique']['depenses'] == pytest.approx(attendu, abs=1e-9), an


DEFAUTS = {
    'valeurs absentes': {'forme': 'valeurs'},
    'valeurs non objet': {'forme': 'valeurs', 'valeurs': [12.0, 13.0]},
    'valeurs vides': {'forme': 'valeurs', 'valeurs': {}},
    'première année après le début': {'forme': 'valeurs', 'valeurs': {'2029': 12.0}},
    'année manquante': {'forme': 'valeurs', 'valeurs': {'2028': 12.0, '2030': 13.0}},
    'année après 2032': {'forme': 'valeurs', 'valeurs': {str(a): 12.0 for a in range(2028, 2034)}},
    'année illisible': {'forme': 'valeurs', 'valeurs': {'2028': 12.0, 'deux-mille': 13.0}},
    'année décimale': {'forme': 'valeurs', 'valeurs': {'2028': 12.0, '2029.5': 13.0}},
    'année en double': {'forme': 'valeurs', 'valeurs': {'2028': 12.0, 2028: 12.0}},
    'valeur texte': {'forme': 'valeurs', 'valeurs': {'2028': '12'}},
    'valeur booléenne': {'forme': 'valeurs', 'valeurs': {'2028': True}},
    'valeur non finie': {'forme': 'valeurs', 'valeurs': {'2028': math.inf}},
    'valeur NaN': {'forme': 'valeurs', 'valeurs': {'2028': math.nan}},
    'valeur au-dessus du domaine': {'forme': 'valeurs', 'valeurs': {'2028': 37.5}},
    'valeur sous le domaine': {'forme': 'valeurs', 'valeurs': {'2028': -0.5}},
    'trop de valeurs': {'forme': 'valeurs', 'valeurs': {str(a): 12.0 for a in range(2020, 2033)}},
    'année avec valeurs': {'forme': 'valeurs', 'annee': 2028, 'valeurs': {'2028': 12.0}},
    'durée avec valeurs': {'forme': 'valeurs', 'annees': 2, 'valeurs': {'2028': 12.0}},
    'valeurs sur une rampe': {'forme': 'rampe', 'valeurs': {'2028': 12.0}},
    'valeurs sur plein': {'forme': 'plein', 'valeurs': {'2028': 12.0}},
}


@pytest.mark.parametrize('nom', sorted(DEFAUTS))
def test_defaut_refuse_en_strict_ignore_et_trace_en_tolerant(nom):
    profil = DEFAUTS[nom]
    with pytest.raises(cadre.ProfilInvalide):
        _preparer({CLE: copy.deepcopy(profil)})
    corrections = {}
    c = _preparer({CLE: copy.deepcopy(profil)}, strict=False, corrections=corrections)
    assert corrections, nom
    assert CLE not in c.etat.profils
    assert [_valeur(c, CLE, a) for a in range(2028, 2033)] == [P] * 5   # programme plein


def test_mode_historique_refuse_les_valeurs_comme_tout_calendrier():
    with pytest.raises(cadre.ProfilInvalide):
        cadre.CadreTemporel.preparer(_programme(CLE, P), None, strict=True,
                                     profils={CLE: {'forme': 'valeurs', 'valeurs': VALEURS}})


def _client():
    import importlib.util
    from fastapi.testclient import TestClient
    spec = importlib.util.spec_from_file_location('api_objectifs_part', RACINE / 'api.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return TestClient(module.app, raise_server_exceptions=False)


def test_api_accepte_les_valeurs_et_les_publie(monkeypatch):
    monkeypatch.setenv('BUDGETLAB_STRICT', '1')
    r = _client().post('/simulate', json={
        'periods': 10, 'annee_debut': DEBUT, 'mesures': _programme(CLE, P),
        'profils': {CLE: {'forme': 'valeurs', 'valeurs': VALEURS}}})
    assert r.status_code == 200, r.text[:500]
    publie = r.json()['cadre']['profils'][CLE]
    assert publie['forme'] == 'valeurs' and publie['valeurs'] == VALEURS


@pytest.mark.parametrize('profil', [
    {'forme': 'valeurs', 'valeurs': [12.0]},
    {'forme': 'valeurs', 'valeurs': {'2028': 'douze'}},
    {'forme': 'valeurs', 'valeurs': {'2028': 12.0, '2030': 13.0}},
    {'forme': 'valeurs', 'valeurs': {'2028': 99.0}},
    {'forme': 'rampe', 'valeurs': {'2028': 12.0}},
])
def test_api_refuse_les_valeurs_mal_formees_en_strict(profil, monkeypatch):
    monkeypatch.setenv('BUDGETLAB_STRICT', '1')
    r = _client().post('/simulate', json={'periods': 10, 'annee_debut': DEBUT,
                                          'mesures': _programme(CLE, P), 'profils': {CLE: profil}})
    assert r.status_code == 422, r.text[:500]


def test_generateur_des_parametres_publie_les_montants_dates():
    """Le bloc généré des paramètres des scénarios (docs/SCENARIOS_POLITIQUES.md) écrit chaque montant daté."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('generateur_params_p', RACINE / 'scripts' / 'generate_scenario_params.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    texte = module._texte_calendrier(CLE, {'forme': 'valeurs', 'valeurs': VALEURS})
    assert texte.startswith('montant fixé pour chaque année') and texte.endswith('(valeurs)')
    for an, v in VALEURS.items():
        assert f'{an} : {module._format_value(v)}' in texte, an
    with pytest.raises(RuntimeError):
        module._texte_calendrier(CLE, {'forme': 'valeurs'})


# --- Revue du moteur (v0.8.1) : années en chiffres ASCII, doublons JSON, trajectoire libre, atterrissage

@pytest.mark.parametrize('cle_annee', ['\u0662\u0660\u0662\u0668',   # chiffres arabes-indiens
                                       '\uff12\uff10\uff12\uff18',   # chiffres pleine largeur
                                       '\u0968\u0966\u0968\u096e'])  # chiffres dévanagari
def test_annee_en_chiffres_non_ascii_illisible(cle_annee):
    assert int(cle_annee) == 2028          # Python les lit comme 2028…
    assert cadre._annee_de_cle(cle_annee) is None   # … le contrat n'admet que 0-9
    with pytest.raises(cadre.ProfilInvalide, match='illisible'):
        _preparer({CLE: {'forme': 'valeurs', 'valeurs': {cle_annee: 12.0}}})
    corrections = {}
    c = _preparer({CLE: {'forme': 'valeurs', 'valeurs': {cle_annee: 12.0}}}, strict=False,
                  corrections=corrections)
    assert corrections and CLE not in c.etat.profils


def test_api_annee_en_double_dans_le_json_la_derniere_gagne(monkeypatch):
    """Comportement standard du JSON (documenté au contrat) : un objet qui répète une clé garde la
    DERNIÈRE valeur, avant toute validation ; le moteur ne voit qu'une année."""
    monkeypatch.setenv('BUDGETLAB_STRICT', '1')
    corps = ('{"periods":10,"annee_debut":%d,"mesures":{"recherche_publique":{"budget":%s}},'
             '"profils":{"%s":{"forme":"valeurs","valeurs":{"2028":12.0,"2029":14.0,"2028":13.0}}}}'
             % (DEBUT, P, CLE))
    r = _client().post('/simulate', content=corps, headers={'content-type': 'application/json'})
    assert r.status_code == 200, r.text[:500]
    publie = r.json()['cadre']['profils'][CLE]
    assert publie['valeurs']['2028'] == 13.0 and publie['valeurs']['2029'] == 14.0
    assert r.json()['report']['valid'] is True


def test_trajectoire_non_monotone_appliquee_telle_quelle():
    """Aucune règle de monotonie : les montants datés sont appliqués tels qu'écrits (baisse puis hausse)."""
    valeurs = {'2028': 15.0, '2029': 12.0, '2030': 17.0, '2031': 11.0}
    c = _preparer({CLE: {'forme': 'valeurs', 'valeurs': valeurs}}, programme=_programme(CLE, 16.0))
    assert [_valeur(c, CLE, a) for a in range(2028, 2034)] == [15.0, 12.0, 17.0, 11.0, 16.0, 16.0]


def test_debut_ramene_par_l_atterrissage_en_tolerant_valeurs_du_debut_demande_ignorees():
    """Tolérant, début demandé dans l'atterrissage : le début est ramené après la dernière année
    observée (correction tracée) ; un calendrier « valeurs » écrit dès le début DEMANDÉ ne commence plus
    au début retenu : ignoré, correction tracée (jamais décalé en silence). Strict : 422 sur le début."""
    from cadre_harness import atterrissage
    profils = {CLE: {'forme': 'valeurs', 'valeurs': {'2027': 11.0, '2028': 12.0, '2029': 14.0}}}
    with atterrissage({2026: {}, 2027: {}}):
        with pytest.raises(cadre.AnneeDebutInvalide):
            cadre.CadreTemporel.preparer(_programme(CLE, P), 2027, strict=True, warned=set(),
                                         profils=copy.deepcopy(profils))
        corrections = {}
        c = cadre.CadreTemporel.preparer(_programme(CLE, P), 2027, strict=False, warned=set(),
                                         profils=copy.deepcopy(profils), corrections=corrections)
    assert c.annee_debut == 2028
    assert ('cadre', 'annee_debut_atterrissage') in corrections
    assert ('cadre', 'profils', 'entrees') in corrections, corrections
    assert CLE not in c.etat.profils
    assert [_valeur(c, CLE, a) for a in range(2028, 2033)] == [P] * 5
