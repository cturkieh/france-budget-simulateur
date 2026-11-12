"""Release E — chantier W1 : compléments écrits avec le code (valeur datée qui
change APRÈS l'année de début).

Les tests du chantier (``test_release_e_w1.py``) couvrent des valeurs datées dont
les segments changent avant le début des programmes (surtaxe votée pour 2026,
programme en 2028). Le contrat (§ 5.3) pose la règle pour TOUTE année : « le droit
de l'année a = mesures avec, pour chaque paramètre daté, la valeur du segment qui
contient a ». Un programme qui commence en 2027 face à une mesure votée pour
2027-2028 seulement voit donc le droit changer en 2029. Ce fichier verrouille ce
chemin du code (``droit_apres_debut``) :

- un levier que le programme ne fixe pas suit le droit DE L'ANNÉE (la mesure ne
  se reconduit pas) ; les mondes « droit » de la composition aussi ;
- un levier que le programme fixe garde sa valeur (« présent = imposé ») ; il
  devient modifié à la première année où il s'écarte du droit (son origine
  d'horloge), et rien ne bouge avant ;
- par mutation : lu sans le changement après le début, le droit reconduirait la
  mesure, et la propriété rougit.

Données de test explicites (aucune n'est une donnée publiée) : 7,3 en 2026, 5 en
2027-2028, 0 dès 2029.
"""
import copy
import json
import tempfile
from contextlib import contextmanager
from pathlib import Path

import pytest

import budget_simulator.engine.cadre as cadre

from cadre_harness import egalite_bit_a_bit, impacts_par_annee, simuler

DEBUT = 2027
SEGMENTS = [{'de': 2026, 'a': 2026, 'valeur': 7.3, 'source': 'donnée de test (W1)'},
            {'de': 2027, 'a': 2028, 'valeur': 5.0, 'source': 'donnée de test (W1)'},
            {'de': 2029, 'valeur': 0, 'source': 'donnée de test (W1)'}]
VALEUR_SEGMENT = {2027: 5.0, 2028: 5.0, **{a: 0 for a in range(2029, 2036)}}


@contextmanager
def droit_a_trois_segments():
    contenu = json.loads(cadre.DROIT_EN_VIGUEUR_PATH.read_text(encoding='utf-8'))
    contenu['valeurs_datees'] = {'is_exceptionnel_tge': {'montant': copy.deepcopy(SEGMENTS)}}
    with tempfile.TemporaryDirectory() as d, pytest.MonkeyPatch.context() as mp:
        chemin = Path(d) / 'droit_en_vigueur.json'
        chemin.write_text(json.dumps(contenu, ensure_ascii=False), encoding='utf-8')
        mp.setattr(cadre, 'DROIT_EN_VIGUEUR_PATH', chemin)
        cadre.vider_caches()
        try:
            yield
        finally:
            cadre.vider_caches()


def _surtaxe(c, annee):
    return c.mesures_de_l_annee(annee)['is_exceptionnel_tge']['montant']


def test_levier_herite_suit_le_droit_de_l_annee():
    with droit_a_trois_segments():
        c = cadre.CadreTemporel.preparer({}, DEBUT)
        assert c.leviers_modifies == frozenset()
        for annee, valeur in VALEUR_SEGMENT.items():
            assert _surtaxe(c, annee) == valeur, annee
            assert c.droit_en_vigueur_de(annee)['is_exceptionnel_tge']['montant'] == valeur, annee


def test_levier_impose_garde_sa_valeur_et_part_a_l_ecart():
    with droit_a_trois_segments():
        c = cadre.CadreTemporel.preparer({'is_exceptionnel_tge': {'montant': 5.0}}, DEBUT)
        assert all(_surtaxe(c, a) == 5.0 for a in range(DEBUT, 2036))
        assert c.leviers_modifies == {'is_exceptionnel_tge'}
        assert c.etat.origines == {'is_exceptionnel_tge': 2029}
        assert c.origines_de_l_annee(2028) == {}
        assert c.origines_de_l_annee(2029) == {'is_exceptionnel_tge': 2029}


def test_simulation_rien_ne_bouge_avant_l_ecart_puis_la_recette_suit_le_droit():
    """Statu quo : la recette du levier suit le droit de chaque année. Programme
    qui garde 5 : trajectoire identique AU BIT au statu quo jusqu'en 2028 (même
    droit, même horloge), recette constante ensuite."""
    with droit_a_trois_segments():
        sq = simuler({}, annee_debut=DEBUT)
        impose = simuler({'is_exceptionnel_tge': {'montant': 5.0}}, annee_debut=DEBUT)
    egalite_bit_a_bit(impose, sq, annees=range(2025, 2029))
    rec = {nom: {a: impacts_par_annee(s[2])[a].get('is_exceptionnel_tge', {}).get('recettes', 0.0)
                 for a in range(2027, 2036)} for nom, s in (('sq', sq), ('impose', impose))}
    assert rec['sq'][2028] == rec['impose'][2028]
    assert all(rec['sq'][a] == rec['sq'][2029] for a in range(2029, 2036))
    assert all(rec['impose'][a] == rec['impose'][2028] for a in range(2029, 2036))
    # 5 Md€ de surtaxe en moins dans le statu quo dès 2029 (montant en Md€ non indexé).
    assert rec['impose'][2029] - rec['sq'][2029] == pytest.approx(5.0, abs=1e-12)
    assert sq[2]['valid'] is True and impose[2]['valid'] is True


def test_mutation_droit_fige_au_debut_reconduit_la_mesure(monkeypatch):
    """Par MUTATION : le droit lu au début et figé ensuite (règle v0.7.2)
    reconduirait la mesure votée pour 2027-2028 ; la propriété le refuse."""
    with droit_a_trois_segments():
        bon = cadre.CadreTemporel.preparer({}, DEBUT)
        assert _surtaxe(bon, 2030) == 0
        monkeypatch.setattr(cadre.CadreTemporel, 'droit_en_vigueur_de',
                            lambda self, annee: self.etat.mesures_droit)
        vrai = cadre._mesures_profilees
        monkeypatch.setattr(cadre, '_mesures_profilees',
                            lambda prog, eff, droit, apres, debut, profils:
                            vrai(prog, eff, droit, {}, debut, profils))
        mutant = cadre.CadreTemporel.preparer({}, DEBUT)
        assert _surtaxe(mutant, 2030) == 5.0


# ---------------------------------------------------------------------------
# Calendriers × valeurs datées (revue adverse de la release E, R-1 C3) : la
# référence d'un calendrier, chaque année, est le droit en vigueur de CETTE
# année. Lue au début et figée, elle reconduisait la mesure datée : un
# calendrier « une seule année » rendait ensuite la valeur du droit du début
# (5) quand le droit de l'année valait 0, soit une recette non demandée.
# ---------------------------------------------------------------------------

CLE = 'is_exceptionnel_tge.montant'
PROFILS_CROISES = {
    'plein': cadre.Profil('plein'),
    'annee_debut': cadre.Profil('annee', annee=DEBUT),
    'annee_2028': cadre.Profil('annee', annee=2028),
    'annee_2030': cadre.Profil('annee', annee=2030),
    'rampe': cadre.Profil('rampe'),
    'rampe_2_ans': cadre.Profil('rampe', annees=2),
    'rampe_4_ans': cadre.Profil('rampe', annees=4),
}


def _attendu(profil, p, annee):
    """Valeur du calendrier (contrat § 2.1), référence = droit de l'ANNÉE."""
    ref = VALEUR_SEGMENT[annee]
    if profil.forme == 'plein':
        return p
    if profil.forme == 'annee':
        return p if annee == profil.annee else ref
    n = profil.annees if profil.annees is not None else cadre.ANNEE_FIN_MANDAT - DEBUT + 1
    k = annee - DEBUT + 1
    return p if k >= n else ref + (p - ref) * k / n


@pytest.mark.parametrize('p', [10.0, 5.0, 0.0, 7.3])
@pytest.mark.parametrize('nom', list(PROFILS_CROISES))
def test_calendrier_reference_au_droit_de_chaque_annee(nom, p):
    """Croisé calendriers × valeurs datées : chaque année du début à la fin de
    la simulation, la valeur appliquée est celle du calendrier calculée avec le
    droit DE L'ANNÉE pour référence (5 en 2027-2028, 0 dès 2029) ; ``plein``
    garde la valeur du programme. Cas p = 5 (égal au droit du début) : le
    calendrier agit quand même dès que le droit change."""
    profil = PROFILS_CROISES[nom]
    with droit_a_trois_segments():
        c = cadre.CadreTemporel.preparer({'is_exceptionnel_tge': {'montant': p}}, DEBUT,
                                         profils={CLE: profil.publier()})
        for annee in range(DEBUT, 2036):
            assert _surtaxe(c, annee) == pytest.approx(_attendu(profil, p, annee), abs=1e-12), (
                nom, p, annee, _surtaxe(c, annee))
        publiees = c.rapport_profils().get(CLE, {}).get('valeurs', {})
        for annee_txt, valeur in publiees.items():
            assert valeur == pytest.approx(_attendu(profil, p, int(annee_txt)), abs=1e-12), (
                nom, p, annee_txt)


def test_calendrier_une_annee_puis_droit_de_l_annee_dans_la_simulation():
    """Simulation complète : surtaxe à 10 pour la seule année de début ; dès
    2029, la recette du levier est celle du statu quo (droit de l'année : 0),
    aucune recette non demandée ; rapport valide."""
    with droit_a_trois_segments():
        sq = simuler({}, annee_debut=DEBUT)
        prog = simuler({'is_exceptionnel_tge': {'montant': 10.0}}, annee_debut=DEBUT,
                       profils={CLE: {'forme': 'annee', 'annee': DEBUT}})
    rec = {nom: {a: impacts_par_annee(s[2])[a].get('is_exceptionnel_tge', {}).get('recettes', 0.0)
                 for a in range(DEBUT, 2036)} for nom, s in (('sq', sq), ('prog', prog))}
    assert rec['prog'][DEBUT] - rec['sq'][DEBUT] == pytest.approx(5.0, abs=1e-12)   # NON_VACUITE
    for a in range(2029, 2036):
        assert rec['prog'][a] == pytest.approx(rec['sq'][a], abs=1e-12), (a, rec['prog'][a], rec['sq'][a])
    assert prog[2]['valid'] is True


# ---------------------------------------------------------------------------
# Rampe à durée explicite (``annees``) : elle finit au plus tard en 2032
# (revue adverse de la release E, R-1 C4). Avant : ``annees`` jusqu'à 6 quel
# que soit le début ; un début en 2028 sur 6 ans n'atteignait la cible qu'en
# 2033 (−25 publié en 2032 pour −30 demandés), rapport valide.
# ---------------------------------------------------------------------------

CLE_RAMPE = 'depenses_publiques.credits_etat'
CIBLE_RAMPE = -30.0


@pytest.mark.parametrize('debut', list(range(2027, cadre.ANNEE_FIN_MANDAT + 1)))
@pytest.mark.parametrize('annees', list(range(cadre.RAMPE_ANNEES_MIN, cadre.RAMPE_ANNEES_MAX + 1)))
def test_rampe_a_duree_explicite_finit_au_plus_tard_en_2032(debut, annees):
    """Admise si début + annees − 1 ≤ 2032 : la cible est alors atteinte au plus
    tard en 2032, exactement. Sinon : ``ProfilInvalide`` en strict ; en
    tolérant, durée ramenée à la borne (la rampe finit en 2032, comme l'alias
    ``rampe``) et correction tracée (relecture adverse finale, m-c ; avant :
    entrée ignorée, calendrier « plein »)."""
    prog = {'depenses_publiques': {'credits_etat': CIBLE_RAMPE}}
    profils = {CLE_RAMPE: {'forme': 'rampe', 'annees': annees}}
    if debut + annees - 1 <= cadre.ANNEE_FIN_MANDAT:
        c = cadre.CadreTemporel.preparer(prog, debut, profils=profils, strict=True)
        valeurs = {a: c.mesures_de_l_annee(a)['depenses_publiques']['credits_etat']
                   for a in range(debut, 2036)}
        assert valeurs[debut + annees - 1] == CIBLE_RAMPE
        assert valeurs[cadre.ANNEE_FIN_MANDAT] == CIBLE_RAMPE
        assert c.rapport_profils()[CLE_RAMPE]['valeurs'][str(cadre.ANNEE_FIN_MANDAT)] == CIBLE_RAMPE
        return
    with pytest.raises(cadre.ProfilInvalide, match='annees'):
        cadre.CadreTemporel.preparer(prog, debut, profils=profils, strict=True)
    corrections, warned = {}, set()
    c = cadre.CadreTemporel.preparer(prog, debut, profils=profils, strict=False,
                                     warned=warned, corrections=corrections)
    assert corrections, 'correction tracée'
    borne = cadre.ANNEE_FIN_MANDAT - debut + 1
    assert c.etat.profils[CLE_RAMPE].annees == borne
    valeurs = {a: c.mesures_de_l_annee(a)['depenses_publiques']['credits_etat']
               for a in range(debut, 2036)}
    assert all(valeurs[a] == CIBLE_RAMPE for a in range(cadre.ANNEE_FIN_MANDAT, 2036)), valeurs
    assert borne == 1 or valeurs[debut] != CIBLE_RAMPE, valeurs


def test_rampe_a_duree_explicite_trop_longue_rapport_invalide_en_simulation():
    """Simulation tolérante, début 2028, 6 ans : rapport invalide, durée
    ramenée à 5 (la cible est publiée en 2032 au bout de la rampe, m-c) ;
    strict : refus."""
    prog = {'depenses_publiques': {'credits_etat': CIBLE_RAMPE}}
    profils = {CLE_RAMPE: {'forme': 'rampe', 'annees': 6}}
    rapport = simuler(prog, annee_debut=2028, profils=profils)[2]
    assert rapport['valid'] is False
    assert rapport['cadre']['profils'][CLE_RAMPE]['annees'] == 5
    assert rapport['cadre']['profils'][CLE_RAMPE]['valeurs'][str(cadre.ANNEE_FIN_MANDAT)] == CIBLE_RAMPE
    with pytest.raises(cadre.ProfilInvalide):
        simuler(prog, annee_debut=2028, profils=profils, strict=True)


@pytest.mark.parametrize('strict, code, valide', [('', 200, False), ('1', 422, None)])
def test_api_rampe_a_duree_explicite_trop_longue(monkeypatch, strict, code, valide):
    """Par l'API (cas de la revue adverse) : début 2028, rampe de 6 ans sur
    un montant ; tolérant : 200 et rapport invalide ; strict : 422."""
    import importlib.util
    from fastapi.testclient import TestClient
    chemin = Path(__file__).resolve().parent.parent / 'api.py'
    spec = importlib.util.spec_from_file_location('api_rampe_annees_e', chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    client = TestClient(module.app, raise_server_exceptions=False)
    monkeypatch.setenv('BUDGETLAB_STRICT', strict)
    reponse = client.post('/simulate', json={
        'mesures': {'depenses_publiques': {'credits_etat': CIBLE_RAMPE}}, 'annee_debut': 2028,
        'profils': {CLE_RAMPE: {'forme': 'rampe', 'annees': 6}}})
    assert reponse.status_code == code, reponse.text
    if valide is not None:
        assert reponse.json()['report']['valid'] is valide


# ---------------------------------------------------------------------------
# Calendriers ouverts à quatre taux et niveaux (revue adverse de la release E,
# règle du mainteneur : on suit le calendrier écrit par le programme) :
# cotisations salariales (points), cotisations patronales (taux), salaires des
# enseignants (%), budget chômage en montant. Formes admises : « plein » et
# « rampe » ; « une seule année » refusée (une réforme de niveau qui s'annule
# l'année suivante n'est pas un calendrier de programme, et le handler des
# cotisations salariales ne rend pas son effet ponctuel au retour à 0).
# ---------------------------------------------------------------------------

TAUX_ET_NIVEAUX = {
    'cotisations_salariales.baisse_points': 6.0,
    'cotisations_patronales.taux': 0.2525,
    'education.salaires': 12.0,
    'chomage_alloc.montant': 30.0,
}


def _programme(cle, valeur):
    levier, param = cle.split('.')
    return {levier: {param: valeur}}


def _valeur(c, cle, annee):
    levier, param = cle.split('.')
    return c.mesures_de_l_annee(annee)[levier][param]


def test_quatre_taux_et_niveaux_eligibles_a_la_rampe_seulement():
    assert set(TAUX_ET_NIVEAUX) == cadre.PROFILS_TAUX_ET_NIVEAUX
    assert cadre.PROFILS_TAUX_ET_NIVEAUX <= cadre.PROFILS_ELIGIBLES
    for cle in TAUX_ET_NIVEAUX:
        assert cadre.FORMES_ADMISES[cle] == ('plein', 'rampe'), cle


@pytest.mark.parametrize('debut', [2027, 2028, 2030])
@pytest.mark.parametrize('cle', list(TAUX_ET_NIVEAUX))
def test_rampe_sur_un_taux_interpolation_lineaire_et_cible_exacte_en_2032(cle, debut):
    """Rampe : chaque année du début à 2031, référence (droit en vigueur au
    début ; pour le montant du budget chômage, que le droit écrit en taux, le
    montant équivalent à ce taux, contre-vérification m2) + (cible − référence)
    × k / n, n = 2032 − début + 1 ; en 2032
    et après, la cible EXACTE ; publiée telle quelle dans ``cadre.profils``."""
    p = TAUX_ET_NIVEAUX[cle]
    levier, param = cle.split('.')
    c = cadre.CadreTemporel.preparer(_programme(cle, p), debut, profils={cle: {'forme': 'rampe'}},
                                     strict=True)
    ref = cadre.reference_du_profil(levier, param, c.etat.mesures_droit)
    assert ref != p, ('NON_VACUITE', cle, ref)
    n = cadre.ANNEE_FIN_MANDAT - debut + 1
    publiees = c.rapport_profils()[cle]['valeurs']
    for annee in range(debut, 2036):
        k = annee - debut + 1
        attendu = p if k >= n else ref + (p - ref) * k / n
        assert _valeur(c, cle, annee) == pytest.approx(attendu, rel=1e-12, abs=1e-12), (cle, annee)
        if annee <= cadre.ANNEE_FIN_MANDAT:
            assert publiees[str(annee)] == pytest.approx(attendu, rel=1e-12, abs=1e-12), (cle, annee)
    assert _valeur(c, cle, cadre.ANNEE_FIN_MANDAT) == p          # exacte, jamais ref + (p − ref) × 1
    pas = [_valeur(c, cle, a) - _valeur(c, cle, a - 1) for a in range(debut + 1, cadre.ANNEE_FIN_MANDAT + 1)]
    assert all(x == pytest.approx((p - ref) / n, rel=1e-9) for x in pas), (cle, pas)


@pytest.mark.parametrize('cle', list(TAUX_ET_NIVEAUX))
def test_une_seule_annee_refusee_pour_un_taux(cle):
    profils = {cle: {'forme': 'annee', 'annee': 2030}}
    with pytest.raises(cadre.ProfilInvalide, match='annee'):
        cadre.CadreTemporel.preparer(_programme(cle, TAUX_ET_NIVEAUX[cle]), 2028, profils=profils,
                                     strict=True)
    corrections = {}
    c = cadre.CadreTemporel.preparer(_programme(cle, TAUX_ET_NIVEAUX[cle]), 2028, profils=profils,
                                     strict=False, warned=set(), corrections=corrections)
    assert corrections and cle not in c.etat.profils


EFFETS_PONCTUELS = {
    # clé : canal émis en effet ponctuel, indépendant du PIB de l'année
    'cotisations_salariales.baisse_points': ('cotisations_salariales', 'gini'),
    'cotisations_patronales.taux': ('cotisations_patronales', 'chomage'),
    'chomage_alloc.montant': ('chomage_alloc', 'gini'),
}


@pytest.mark.parametrize('cle', list(EFFETS_PONCTUELS))
def test_rampe_effets_ponctuels_emis_en_increments_une_seule_fois(cle):
    """Simulation complète, mode cadre 2028 : rampe valide, recette ou dépense
    du levier chaque année proportionnelle au niveau de l'année (non vacuité :
    croissante en valeur absolue), et l'effet ponctuel (indépendant du PIB)
    émis en incréments dont la somme vaut l'effet du palier émis par le
    calendrier « plein » (jamais compté deux fois)."""
    levier, canal = EFFETS_PONCTUELS[cle]
    p = TAUX_ET_NIVEAUX[cle]
    prog = _programme(cle, p)
    rampe = simuler(prog, annee_debut=2028, profils={cle: {'forme': 'rampe'}})
    plein = simuler(prog, annee_debut=2028)
    assert rampe[2]['valid'] is True, rampe[2]['warnings']
    imp_r, imp_p = impacts_par_annee(rampe[2]), impacts_par_annee(plein[2])
    effet = {nom: sum((i.get(levier) or {}).get(canal, 0.0) for a, i in imp.items() if a >= 2028)
             for nom, imp in (('rampe', imp_r), ('plein', imp_p))}
    assert effet['plein'] != 0.0, ('NON_VACUITE', effet)
    assert effet['rampe'] == pytest.approx(effet['plein'], rel=1e-9, abs=1e-12), effet
    emis = [(imp_r.get(a, {}).get(levier) or {}).get(canal, 0.0) for a in range(2028, 2033)]
    assert sum(1 for x in emis if x != 0.0) == 5, ('incréments chaque année de la rampe', emis)
