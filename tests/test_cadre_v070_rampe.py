"""v0.7.0, lot D — rampe générique paramétrique sur les leviers en Md€, et rampe de
mandat des postes d'enseignants.

Contrat (dossier du dépôt parent ``docs/plans/passe-cadre-2027-2032.md`` § 2.4,
décision § 6.4 : pas de rampe par défaut, la trajectoire déclarée par le
programme sinon, levier par levier) :

- requête ``rampe = {"annees": n, "leviers": ["levier.parametre", …]}``, n ∈ [1 ; 6],
  mode cadre seulement ; défaut : AUCUNE rampe ;
- p(année) = p_droit + (p_programme − p_droit) × min(max(année − début + 1, 0), n) / n :
  paramètre, pas montant — c'est la seule forme que lisent aussi les lecteurs
  latéraux (effet d'offre) ;
- leviers éligibles : les leviers en Md€ (transition, recherche, éducation,
  défense, collectivités, immigration, prévention santé) et, grâce aux effets
  ponctuels en incrément (lot B), les cinq leviers fiscaux TGE ;
- ``education.enseignants`` suit la règle des effectifs FP (stock atteint
  linéairement en 2032, à partir de max(début, 2027)), en mode cadre ;
- validation : strict → 422 ; tolérant → correction tracée.

Propriété (c) : rampe nulle avant le début, incréments égaux, monotone, pleine à
début + n − 1 ; (d) rampée, un effet ponctuel ne compte qu'une fois.
"""
import copy
import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import budget_simulator.engine.cadre as cadre
from budget_simulator import EntreeInvalide

from cadre_harness import DROIT, DROIT_REAJUSTE, egalite_bit_a_bit, impacts_par_annee, programme_sur_droit, simuler

DEBUT = 2028
API_FILE = Path(__file__).resolve().parent.parent / 'api.py'


def _cadre(programme, rampe, debut=DEBUT):
    return cadre.CadreTemporel.preparer(programme, debut, rampe=rampe)


# Référence d'une rampe : le droit en vigueur EFFECTIF (réajustements de
# l'atterrissage compris : défense 58 au lieu de 57 votés).
DEF_REF = cadre.CadreTemporel.preparer({}, DEBUT).etat.mesures_droit['defense']['budget']


# ---------------------------------------------------------------------------
# (c) la rampe des paramètres
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('n', [1, 3, 5, 6])
def test_c_rampe_nulle_avant_egale_par_pas_monotone_pleine_a_la_fin(n):
    prog = programme_sur_droit(defense={'budget': 70}, collectivites={'dotation': 100.0, 'investissement': 10})
    c = _cadre(prog, {'annees': n, 'leviers': ['defense.budget', 'collectivites.investissement']})
    valeurs = {an: c.mesures_de_l_annee(an)['defense']['budget'] for an in range(2026, 2036)}
    assert all(valeurs[an] == DEF_REF for an in range(2026, DEBUT))
    pas = [valeurs[an] - valeurs[an - 1] for an in range(DEBUT, DEBUT + n)]
    assert all(p == pytest.approx((70 - DEF_REF) / n, rel=1e-12) for p in pas)
    assert valeurs[DEBUT + n - 1] == 70
    assert all(valeurs[an] == 70 for an in range(DEBUT + n - 1, 2036))
    assert all(valeurs[an + 1] >= valeurs[an] for an in range(2026, 2035))
    # levier hors de la liste : bascule sèche ; levier listé, même règle
    assert all(c.mesures_de_l_annee(an)['collectivites']['dotation'] == 100.0
               for an in range(DEBUT, 2036))
    assert c.mesures_de_l_annee(DEBUT)['collectivites']['investissement'] == pytest.approx(10 / n)


def test_c_rampe_par_defaut_aucune():
    c = _cadre(programme_sur_droit(defense={'budget': 70}), None)
    assert c.mesures_de_l_annee(DEBUT)['defense']['budget'] == 70
    assert c.rapport()['rampe'] is None


def test_c_rampe_dans_le_moteur_increments_egaux():
    """Défense (formule linéaire) : l'écart au budget voté monte par cinquièmes."""
    imp = impacts_par_annee(simuler(programme_sur_droit(defense={'budget': 70}), annee_debut=DEBUT,
                           rampe={'annees': 5, 'leviers': ['defense.budget']})[2])
    for k, an in enumerate(range(DEBUT, DEBUT + 5), start=1):
        assert imp[an]['defense']['depenses'] == pytest.approx((DEF_REF - 50) + (70 - DEF_REF) * k / 5, rel=1e-12)
    assert imp[2027]['defense']['depenses'] == DEF_REF - 50


def test_c_rampe_sans_levier_modifie_est_neutre():
    """Statu quo + rampe : rien à ramper, sortie au bit du statu quo."""
    egalite_bit_a_bit(simuler(DROIT_REAJUSTE, annee_debut=DEBUT,
                              rampe={'annees': 5, 'leviers': ['defense.budget', 'education.budget']}),
                      simuler(DROIT_REAJUSTE, annee_debut=DEBUT))


def test_c_effet_d_offre_lit_le_parametre_rampe(monkeypatch):
    """Lecteur latéral : l'effet d'offre de la recherche lit la valeur rampée."""
    import budget_simulator.engine.growth as growth_mod
    vus = {}
    vrai = growth_mod.valeur_brute

    def espion(mesures, levier, param, defaut):
        v = vrai(mesures, levier, param, defaut)
        if levier == 'recherche_publique':
            vus.setdefault(round(v, 9), 0)
            vus[round(v, 9)] += 1
        return v
    monkeypatch.setattr(growth_mod, 'valeur_brute', espion)
    simuler({'recherche_publique': {'budget': 20}}, annee_debut=DEBUT,
            rampe={'annees': 5, 'leviers': ['recherche_publique.budget']})
    assert set(vus) == {10.0, 12.0, 14.0, 16.0, 18.0, 20.0}


# ---------------------------------------------------------------------------
# (d) un effet ponctuel rampé ne compte qu'une fois
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('levier, debut_val, fin_val, defaut, coeff', [
    ('niches_fiscales_tge', 57, 20, 58, -0.015),
    ('niches_sociales_tge', 68, 50, 70, -0.020),
    ('subventions_tge', 33, 20, 35, -0.008),
])
def test_d_rampe_tge_effet_ponctuel_compte_une_fois(levier, debut_val, fin_val, defaut, coeff):
    """L'artefact de l'émulation (compétitivité LFI 2032 98,19 → 95,75 : l'effet
    redéclenché à chaque pas) est fermé : cumul rampé = cumul en bascule = effet du
    niveau atteint contre le défaut."""
    prog = programme_sur_droit(**{levier: {'montant': fin_val}})
    rampe = simuler(prog, annee_debut=DEBUT, rampe={'annees': 5, 'leviers': [f'{levier}.montant']})[2]
    bascule = simuler(prog, annee_debut=DEBUT)[2]
    cumul = lambda r: sum(y.get(levier, {}).get('competitivite', 0.0) for y in r['measure_impacts_by_year'])
    assert cumul(rampe) == pytest.approx(cumul(bascule), rel=1e-12)
    assert cumul(rampe) == pytest.approx(coeff * (defaut - fin_val), rel=1e-12)


# ---------------------------------------------------------------------------
# Postes d'enseignants : la règle des effectifs FP
# ---------------------------------------------------------------------------

def test_enseignants_rampe_de_mandat_en_mode_cadre():
    """30 000 postes : un cinquième du stock par an de 2028 à 2032, au coût du
    handler (65 000 € par poste), en mode cadre ; en mode historique, stock
    entier dès 2026 (v0.6.11, golden master)."""
    education = dict(DROIT['education'], enseignants=30000)
    imp = impacts_par_annee(simuler(programme_sur_droit(education=education), annee_debut=DEBUT)[2])
    for an in range(2026, 2036):
        k = min(max(an - DEBUT + 1, 0), 5)
        assert imp[an].get('education', {}).get('depenses', 0.0) == pytest.approx(
            30000 * k / 5 * 65000 / 1e9, rel=1e-12, abs=1e-12), an
    hist = impacts_par_annee(simuler({'education': education})[2])
    assert hist[2026]['education']['depenses'] == pytest.approx(30000 * 65000 / 1e9, rel=1e-12)


def test_enseignants_non_eligibles_a_la_rampe_generique():
    with pytest.raises(EntreeInvalide, match='enseignants'):
        simuler({'education': {'budget': 65, 'enseignants': 1000}}, strict=True, annee_debut=DEBUT,
                rampe={'annees': 5, 'leviers': ['education.enseignants']})


# ---------------------------------------------------------------------------
# Validation (moteur et API)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('rampe, motif', [
    ({'annees': 0, 'leviers': ['defense.budget']}, 'annees'),
    ({'annees': 7, 'leviers': ['defense.budget']}, 'annees'),
    ({'annees': 2.5, 'leviers': ['defense.budget']}, 'annees'),
    ({'annees': True, 'leviers': ['defense.budget']}, 'annees'),
    ({'annees': 5, 'leviers': ['defense.budgett']}, 'defense.budgett'),
    ({'annees': 5, 'leviers': ['tva_rate.taux']}, 'tva_rate.taux'),
    ({'annees': 5, 'leviers': 'defense.budget'}, 'leviers'),
    ({'annees': 5, 'leviers': ['defense.budget'], 'debut': 2029}, 'debut'),
    ({'leviers': ['defense.budget']}, 'annees'),
    ([5, ['defense.budget']], 'rampe'),
])
def test_rampe_invalide_strict(rampe, motif):
    with pytest.raises(EntreeInvalide, match=motif):
        simuler({'defense': {'budget': 70}}, strict=True, annee_debut=DEBUT, rampe=rampe)


def test_rampe_en_mode_historique_strict_et_tolerant():
    with pytest.raises(EntreeInvalide, match='annee_debut'):
        simuler({'defense': {'budget': 70}}, strict=True, rampe={'annees': 5, 'leviers': ['defense.budget']})
    rapport = simuler({'defense': {'budget': 70}}, rampe={'annees': 5, 'leviers': ['defense.budget']})[2]
    assert rapport['valid'] is False and rapport['cadre']['rampe'] is None
    egalite_bit_a_bit(simuler({'defense': {'budget': 70}}, rampe={'annees': 5, 'leviers': ['defense.budget']}),
                      simuler({'defense': {'budget': 70}}))


@pytest.mark.parametrize('rampe, attendu', [
    ({'annees': 9, 'leviers': ['defense.budget']}, (6, ['defense.budget'])),
    ({'annees': 3, 'leviers': ['defense.budget', 'tva_rate.taux', 'inconnu.x']}, (3, ['defense.budget'])),
])
def test_rampe_tolerant_corrigee(rampe, attendu):
    rapport = simuler({'defense': {'budget': 70}}, annee_debut=DEBUT, rampe=rampe)[2]
    assert rapport['valid'] is False
    assert (rapport['cadre']['rampe']['annees'], rapport['cadre']['rampe']['leviers']) == attendu
    assert any('rampe' in w for w in rapport['warnings'])


@pytest.fixture(scope='module')
def client():
    spec = importlib.util.spec_from_file_location('api_rampe_v070', API_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return TestClient(module.app, raise_server_exceptions=False)


@pytest.mark.parametrize('strict', ['', '1'])
def test_api_rampe_bloc_cadre(client, monkeypatch, strict):
    """Revue passe 1 (LOW 13) : une rampe demandée sur un levier que le
    programme ne modifie pas (recherche à 10, la valeur du droit) est lue telle
    quelle, sans effet : avis INFORMATIF et liste ``leviers_ignores``, jamais une
    correction (``valid`` reste vrai) ni un 422, dans les deux modes."""
    monkeypatch.setenv('BUDGETLAB_STRICT', strict)
    reponse = client.post('/simulate', json={
        'mesures': {'defense': {'budget': 70}, 'recherche_publique': {'budget': 10}},
        'annee_debut': DEBUT,
        'rampe': {'annees': 5, 'leviers': ['defense.budget', 'recherche_publique.budget']}})
    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    r = corps['cadre']['rampe']
    assert r == {'annees': 5, 'leviers': ['defense.budget', 'recherche_publique.budget'],
                 'leviers_rampes': ['defense.budget'],
                 'leviers_ignores': ['recherche_publique.budget']}
    assert corps['report']['valid'] is True
    avis = [w for w in corps['report']['warnings'] if 'recherche_publique.budget' in w]
    assert len(avis) == 1 and avis[0].startswith('Avis — ') and 'sans effet' in avis[0]


def test_rampe_sans_levier_ignore_n_emet_aucun_avis():
    rapport = simuler(programme_sur_droit(defense={'budget': 70}), annee_debut=DEBUT,
                      rampe={'annees': 3, 'leviers': ['defense.budget']})[2]
    assert rapport['cadre']['rampe']['leviers_ignores'] == []
    assert not any('rampe' in w for w in rapport['warnings'])


@pytest.mark.parametrize('rampe', [{'annees': '5', 'leviers': ['defense.budget']},
                                   {'annees': 5, 'leviers': ['defense.budget'], 'x': 1},
                                   {'annees': 5}])
def test_api_rampe_mal_formee_422(client, rampe):
    r = client.post('/simulate', json={'mesures': {}, 'annee_debut': DEBUT, 'rampe': rampe})
    assert r.status_code == 422, r.text


@pytest.mark.parametrize('valeur', [0, 7])
def test_api_rampe_hors_domaine_strict_422(client, monkeypatch, valeur):
    monkeypatch.setenv('BUDGETLAB_STRICT', '1')
    r = client.post('/simulate', json={'mesures': {}, 'annee_debut': DEBUT,
                                       'rampe': {'annees': valeur, 'leviers': ['defense.budget']}})
    assert r.status_code == 422 and 'rampe' in r.json()['detail'], r.text


# ---------------------------------------------------------------------------
# RÉFUTEUR du lot D
# ---------------------------------------------------------------------------

def test_refuteur_d_rampe_d_un_an_egale_bascule_au_bit():
    prog = programme_sur_droit(defense={'budget': 70}, niches_fiscales_tge={'montant': 40})
    egalite_bit_a_bit(simuler(prog, annee_debut=DEBUT,
                              rampe={'annees': 1, 'leviers': ['defense.budget', 'niches_fiscales_tge.montant']}),
                      simuler(prog, annee_debut=DEBUT))


def test_refuteur_d_rampe_au_dela_de_l_horizon():
    """Début 2031, rampe sur 6 ans : la rampe n'est pas finie en 2035 (5/6), sans
    erreur ni extrapolation."""
    c = _cadre(programme_sur_droit(defense={'budget': 69}), {'annees': 6, 'leviers': ['defense.budget']}, debut=2031)
    assert c.mesures_de_l_annee(2035)['defense']['budget'] == pytest.approx(
        DEF_REF + (69 - DEF_REF) * 5 / 6, rel=1e-12)


def test_refuteur_d_rampe_vers_le_bas():
    """Baisse (défense du droit → 45) : même règle, décroissante, jamais sous la cible."""
    c = _cadre(programme_sur_droit(defense={'budget': 45}), {'annees': 4, 'leviers': ['defense.budget']})
    v = [c.mesures_de_l_annee(an)['defense']['budget'] for an in range(2027, 2034)]
    attendu = [DEF_REF] + [DEF_REF + (45 - DEF_REF) * k / 4 for k in (1, 2, 3)] + [45, 45, 45]
    assert v == pytest.approx(attendu, rel=1e-12)
    assert all(a >= b for a, b in zip(v, v[1:]))


def test_refuteur_d_levier_absent_du_droit():
    """Levier rampé absent du droit en vigueur : la référence est le défaut du
    moteur (le droit ne le touche pas)."""
    droit = copy.deepcopy(DROIT)
    del droit['recherche_publique']
    c = cadre.CadreTemporel.preparer({'recherche_publique': {'budget': 20}}, DEBUT,
                                     droit=cadre.DroitEnVigueur('t', 't', 't', '2026-11-07', droit),
                                     rampe={'annees': 5, 'leviers': ['recherche_publique.budget']})
    assert c.mesures_de_l_annee(DEBUT)['recherche_publique']['budget'] == pytest.approx(12.0)


# ---------------------------------------------------------------------------
# Borne de taille de la liste des leviers (revue de sécurité, MEDIUM :
# amplification de ressources) — parité avec les validateurs de _param_domain
# ---------------------------------------------------------------------------

def test_rampe_dix_mille_noms_inconnus_strict_et_tolerant(caplog):
    import logging
    import time
    noms = [f'inconnu_{k}.x' for k in range(10_000)]
    debut = time.perf_counter()
    with pytest.raises(EntreeInvalide, match='rampe'):
        simuler({'defense': {'budget': 70}}, strict=True, annee_debut=DEBUT,
                rampe={'annees': 5, 'leviers': noms})
    with caplog.at_level(logging.WARNING, logger='budget_simulator.engine.cadre'):
        rapport = simuler({'defense': {'budget': 70}}, annee_debut=DEBUT,
                          rampe={'annees': 5, 'leviers': noms})[2]
    assert time.perf_counter() - debut < 2.0
    avertissements = [r for r in caplog.records if r.name == 'budget_simulator.engine.cadre']
    assert len(avertissements) == 1, [r.getMessage()[:80] for r in avertissements]
    assert len(avertissements[0].getMessage()) < 500
    assert rapport['cadre']['rampe'] is None and rapport['valid'] is False
    assert sum('rampe' in w for w in rapport['warnings']) == 1


def test_rampe_noms_retires_un_seul_avertissement_agrege(caplog):
    """Plusieurs noms invalides dans une liste admissible : UN avertissement à
    clé fixe qui liste les noms retirés (borné), sans répéter les éligibles."""
    import logging
    leviers = ['defense.budget', 'tva_rate.taux', 'x' * 60, 'inconnu.y', 'defense.budget']
    with caplog.at_level(logging.WARNING, logger='budget_simulator.engine.cadre'):
        rapport = simuler({'defense': {'budget': 70}}, annee_debut=DEBUT,
                          rampe={'annees': 3, 'leviers': leviers})[2]
    messages = [r.getMessage() for r in caplog.records if r.name == 'budget_simulator.engine.cadre']
    assert len(messages) == 1 and 'tva_rate.taux' in messages[0]
    assert 'transition_ecologique.renovation' not in messages[0]     # liste des éligibles non répétée
    assert rapport['cadre']['rampe']['leviers'] == ['defense.budget']   # dédoublonné


def test_api_rampe_liste_et_noms_bornes(client):
    trop = client.post('/simulate', json={'mesures': {}, 'annee_debut': DEBUT,
                                          'rampe': {'annees': 5, 'leviers': ['defense.budget'] * 16}})
    assert trop.status_code == 422, trop.text
    long_nom = client.post('/simulate', json={'mesures': {}, 'annee_debut': DEBUT,
                                              'rampe': {'annees': 5, 'leviers': ['d' * 65]}})
    assert long_nom.status_code == 422, long_nom.text
    toutes = sorted(cadre.RAMPE_LEVIERS_ELIGIBLES)
    ok = client.post('/simulate', json={'mesures': {}, 'annee_debut': DEBUT,
                                        'rampe': {'annees': 5, 'leviers': toutes}})
    assert ok.status_code == 200, ok.text
