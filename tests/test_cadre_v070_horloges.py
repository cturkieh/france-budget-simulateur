"""v0.7.0, lot C — horloges des handlers : la part héritée garde son horloge,
l'incrément du programme démarre la sienne.

Constat (dossier du dépôt parent ``docs/plans/passe-cadre-2027-2032.md`` § 2.2) :
les handlers comptaient le temps depuis ``POLICY_START_YEAR`` (2026) ou depuis
des années écrites en dur (santé 2026-2030, transition 2027, abattement,
optimisation de la dette, superprofits « jusqu'en 2028 »). Un programme entrant
en 2028 arrivait donc au milieu de son phasage (rabot à 100 % dès 2028 au lieu
de 50 %).

Règle, pour chaque levier, à partir de ``annee_debut`` :

    H(année) = H(droit, horloge 2026) + [H(programme, horloge début) − H(droit, horloge début)]

— trois « mondes » d'évaluation des handlers (droit sur l'horloge 2026, état du
moteur avant le début ; programme et droit sur l'horloge du début, états
propres), combinés clé par clé. Un levier ÉGAL au droit en vigueur, qui ne lit
aucun levier modifié, a deux derniers termes identiques au bit : il garde ses
impacts du droit en vigueur, au bit (propriété b). Les lectures CROISÉES
(fraude sociale ← ASU, SMIC ← point d'indice, effectifs ← réforme FP,
prestations ← ASU) suivent l'horloge du levier lu. Les rampes de mandat
(effectifs FP, cohortes de la réforme FP) démarrent à max(début, 2027) et
finissent en 2032. Le passage de la TVA dans les prix suit l'horloge de la TVA.
Les lecteurs latéraux hors handlers (offre et chômage seniors) prennent
l'horloge du levier des retraites ; la composition à trois termes n'y est pas
nécessaire tant que le droit en vigueur ne s'écarte pas du défaut sur ces
canaux — garde au chargement du droit en vigueur.

Mode historique : aucune horloge ne bouge (golden masters inchangés).
"""
import copy
import json
from pathlib import Path

import pytest

import budget_simulator.engine.cadre as cadre
from budget_simulator import _seniors
from budget_simulator.config import load_policy_config
from budget_simulator.constants import (
    ASU_COUT_RECOURS_MD_EUR,
    OFFRE_SENIORS_PIB_NIVEAU_LT,
    PHASING_OFFRE_SENIORS,
    POLICY_START_YEAR,
    asu_effort_perenne_md_eur,
)
from budget_simulator.simulator import BudgetSimulatorV45

from cadre_harness import CAS, NOMS_PROGRAMMES, PROGRAMME_MIXTE, egalite_bit_a_bit, simuler

DEBUT = 2028
DROIT = cadre.charger_droit_en_vigueur().mesures


def _programme(**leviers):
    m = copy.deepcopy(DROIT)
    m.update(copy.deepcopy(leviers))
    return m


def _impacts(rapport):
    return {y['Année']: y for y in rapport['measure_impacts_by_year']}


def _progression_fraude(e):
    """Montée en puissance documentée de la fraude fiscale (handler, années écoulées)."""
    if e < 0:
        return 0.0
    if e <= 4:
        return (0.20, 0.35, 0.50, 0.70, 1.0)[e]
    return max(0.70, 1.0 - (e - 4) * 0.05)


# ---------------------------------------------------------------------------
# Les origines d'horloge
# ---------------------------------------------------------------------------

class _SimOrigines(BudgetSimulatorV45):
    def update_labour_supply(self, year):
        self.vues = getattr(self, 'vues', {})
        self.vues[year] = dict(self._origines_courantes)
        return super().update_labour_supply(year)


def test_c_origines_debut_pour_les_leviers_modifies_seulement():
    sim = _SimOrigines(periods=10, mesures=_programme(fraude_fiscale={'effort': 0.6}),
                       annee_debut=DEBUT)
    sim.simulate()
    for an, origines in sim.vues.items():
        assert origines == ({} if an < DEBUT else {'fraude_fiscale': DEBUT}), an


def test_c_mode_historique_aucune_horloge_ne_bouge():
    sim = _SimOrigines(periods=10, mesures=PROGRAMME_MIXTE)
    sim.simulate()
    assert all(o == {} for o in sim.vues.values())


# ---------------------------------------------------------------------------
# Chaque horloge démarre au début du programme
# ---------------------------------------------------------------------------

def test_c_rabot_demarre_a_cinquante_pour_cent():
    imp = _impacts(simuler({'rabot_uniforme': {'taux_reduction': 0.05}}, annee_debut=DEBUT)[2])
    assert 'rabot_uniforme' not in imp[2027]
    assert imp[DEBUT]['rabot_uniforme']['rabot_details']['phasing'] == 0.5
    assert imp[DEBUT + 1]['rabot_uniforme']['rabot_details']['phasing'] == 1.0


def test_c_fraude_fiscale_increment_sur_l_horloge_du_programme():
    """Droit 0,14, programme 0,60 : la part héritée continue sur 2026, l'incrément
    0,46 démarre à 20 % en 2028."""
    imp = _impacts(simuler(_programme(fraude_fiscale={'effort': 0.6}), annee_debut=DEBUT)[2])
    for an in range(2026, 2036):
        attendu = 0.68 * 30 * (0.14 * _progression_fraude(an - 2026)
                               + (0.6 - 0.14) * _progression_fraude(an - DEBUT))
        assert imp[an]['fraude_fiscale']['recettes'] == pytest.approx(attendu, rel=1e-12), an


def test_c_sante_phasing_de_l_increment_redemarre():
    """Hôpital : droit 15, programme 30 — l'incrément suit 20/40/60/80/100 % à
    partir de 2028, la part héritée garde son phasage de 2026."""
    struct = {0: 0.2, 1: 0.4, 2: 0.6, 3: 0.8}
    sante = dict(DROIT['sante'], effort_hopital=30)
    imp = _impacts(simuler(_programme(sante=sante), annee_debut=DEBUT)[2])
    for an in range(DEBUT, 2036):
        ph = lambda e: struct.get(e, 1.0) if e >= 0 else 0.0
        attendu = -13.0 * 0.15 * ph(an - 2026) + (-13.0 * 0.30 * ph(an - DEBUT) - (-13.0 * 0.15 * ph(an - DEBUT)))
        assert imp[an]['sante']['hopital'] == pytest.approx(attendu, rel=1e-12), an


def test_c_superprofits_trois_ans_a_partir_du_debut():
    imp = _impacts(simuler({'taxe_superprofits': {'intensite': 1.0}}, annee_debut=DEBUT)[2])
    actives = [an for an in range(2026, 2036)
               if imp[an].get('taxe_superprofits', {}).get('recettes', 0) > 0]
    assert actives == [DEBUT, DEBUT + 1, DEBUT + 2]


def test_c_isf_phasage_du_programme_ifi_calendaire():
    """ISF climatique : phasage 50 % l'année d'entrée (2028), mais l'IFI remplacé
    croît depuis 2026 (calendrier, pas horloge du programme). Différence avec
    l'entrée en 2026 du mode historique : exactement l'IFI de deux ans de plus."""
    i = 0.5
    cadre_2028 = _impacts(simuler({'isf_climatique': {'intensite': i}}, annee_debut=DEBUT)[2])
    hist_2026 = _impacts(simuler({'isf_climatique': {'intensite': i}})[2])
    ecart = cadre_2028[DEBUT]['isf_climatique']['recettes'] - hist_2026[2026]['isf_climatique']['recettes']
    assert ecart == pytest.approx(i * (2.0 - 2.0 * 1.02 ** 2), rel=1e-9)


def test_c_seniors_horloge_du_choc_au_debut():
    m = {'retraites': {'age_depart': 65.0}}
    assert _seniors.retraites_annee_debut_ecart_age(m) == POLICY_START_YEAR
    assert _seniors.retraites_annee_debut_ecart_age(m, origine=DEBUT) == DEBUT
    # gel à 62,75 : l'écart s'ouvre en 2028 dans les deux cas
    gel = {'retraites': {'age_depart': 62.75}}
    assert _seniors.retraites_annee_debut_ecart_age(gel) == 2028
    assert _seniors.retraites_annee_debut_ecart_age(gel, origine=DEBUT) == 2028
    det = simuler(_programme(retraites=dict(DROIT['retraites'], age_depart=65.0)),
                  annee_debut=DEBUT)[1].set_index('Année')
    assert all(det.at[an, 'Bonus_Offre_Travail %'] == 0 for an in range(2026, DEBUT))
    ecart_2028 = 65.0 - 63.0
    assert det.at[DEBUT, 'Bonus_Offre_Travail %'] == pytest.approx(
        OFFRE_SENIORS_PIB_NIVEAU_LT * PHASING_OFFRE_SENIORS[0] * ecart_2028 * 100, rel=1e-12)


def test_c_passage_tva_dans_les_prix_l_annee_qui_suit_le_debut():
    portes = {}

    class Espion(BudgetSimulatorV45):
        def calculate_inflation(self, year, economic_state):
            portes[year] = (economic_state['annee_pass_through_tva'], economic_state['tva_impact'])
            return super().calculate_inflation(year, economic_state)

    Espion(periods=10, mesures={'tva_rate': {'taux': 0.22}}, annee_debut=DEBUT).simulate()
    porte_programme = DEBUT - 2025 + 1
    # Avant le début, la TVA est celle du droit en vigueur (au défaut) : porte
    # de l'horloge 2026, rien à faire passer.
    assert all(portes[i] == (2, 0.0) for i in range(1, DEBUT - 2025)), portes
    assert all(portes[i][0] == porte_programme for i in range(DEBUT - 2025, 11))
    assert portes[porte_programme][1] > 0     # l'impact de 2028 est bien lu en 2029
    portes.clear()
    Espion(periods=10, mesures={'tva_rate': {'taux': 0.22}}).simulate()
    assert {p for p, _ in portes.values()} == {2}


class _SimFP(BudgetSimulatorV45):
    """Relève, par année et par monde, les postes réalisés par le curseur effectifs."""
    def _apply_fonction_publique(self, measure, params, year, gdp, inflation, unemployment):
        dep, rec, imp = super()._apply_fonction_publique(measure, params, year, gdp, inflation, unemployment)
        from budget_simulator.constants import COUT_MOYEN_AGENT_FP_EUR
        cout = COUT_MOYEN_AGENT_FP_EUR * self.indice_prix_depenses()
        self.releve = getattr(self, 'releve', {})
        self.releve.setdefault(year, []).append(dep * 1e9 / cout if dep else 0.0)
        return dep, rec, imp


def test_c_effectifs_fp_rampe_de_mandat_2028_2032():
    """Droit −3 119 postes (rampe 2027-2032, horloge 2026) ; programme −100 000 :
    l'incrément −96 881 se réalise par cinquièmes de 2028 à 2032."""
    sim = _SimFP(periods=10, mesures=_programme(fonction_publique={'effectifs': -100000, 'point_indice': 0}),
                 annee_debut=DEBUT)
    _, _, rapport = sim.simulate()
    imp = _impacts(rapport)
    for an in range(2026, 2036):
        k_droit = min(max(an - 2027 + 1, 0), 6)
        k_prog = min(max(an - DEBUT + 1, 0), 5)
        postes = -3119 * k_droit / 6 + (-100000 * k_prog / 5 - (-3119) * k_prog / 5)
        assert sim.releve[an][0] == pytest.approx(-3119 * k_droit / 6, rel=1e-9, abs=1e-6), an
        realises = sum(sim.releve[an]) if an < DEBUT else (
            sim.releve[an][0] + sim.releve[an][1] - sim.releve[an][2])
        assert realises == pytest.approx(postes, rel=1e-9, abs=1e-6), an
    assert imp[2032]['fonction_publique']['depenses'] < imp[2031]['fonction_publique']['depenses']


def test_c_reforme_fp_premiere_cohorte_au_debut():
    vu = {}

    class Sim(BudgetSimulatorV45):
        def _reforme_fp_reduction_cumulee(self, year):
            r = super()._reforme_fp_reduction_cumulee(year)
            if self.mesures.get('fonction_publique_reforme', {}).get('fusion_agences'):
                vu.setdefault(year, set()).add(r)
            return r

    reforme = {'fusion_agences': 30, 'digitalisation': 30}
    Sim(periods=10, mesures=_programme(fonction_publique_reforme=reforme), annee_debut=DEBUT).simulate()
    assert min(vu) == DEBUT and max(vu[DEBUT]) > 0


def test_c_asu_montee_en_charge_au_debut():
    """ASU activée par le programme : 25 % en 2028 comme en 2026 dans le mode
    historique (même transfert aux ménages, indépendant de l'état macro)."""
    asu = {'asu_activation': 1, 'asu_plafonnement': 0.6}
    cadre_ = _impacts(simuler({'asu': asu}, annee_debut=DEBUT)[2])
    hist = _impacts(simuler({'asu': asu})[2])
    assert cadre_[DEBUT]['asu']['menages']['prestations'] == hist[2026]['asu']['menages']['prestations']
    assert cadre_[DEBUT]['asu']['menages']['prestations'] == pytest.approx(
        asu_effort_perenne_md_eur(0.6) * 0.25 + ASU_COUT_RECOURS_MD_EUR * 0.25, rel=1e-12)


def test_c_lecture_croisee_suit_l_horloge_du_levier_lu():
    """Fraude sociale INCHANGÉE (droit 0,1), ASU activée par le programme : son
    anti-double-comptage lit l'ASU sur l'horloge de l'ASU (25 % en 2028)."""
    lus = []
    import budget_simulator.handlers.efficience as eff
    vrai = eff.asu_phasing

    def espion(mesures, year, origine=POLICY_START_YEAR):
        r = vrai(mesures, year, origine)
        if r:
            lus.append((year, origine, r))
        return r

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(eff, 'asu_phasing', espion)
        simuler({'asu': {'asu_activation': 1, 'asu_plafonnement': 0.6}}, annee_debut=DEBUT)
    assert lus and min(lus)[0] == DEBUT and min(lus)[1:] == (DEBUT, 0.25)


# ---------------------------------------------------------------------------
# (b) levier égal au droit en vigueur : impacts bit-identiques chaque année
# ---------------------------------------------------------------------------

class _SimMondes(BudgetSimulatorV45):
    def _apply_complex_measure(self, measure, params, year, gdp, inflation, unemployment):
        out = super()._apply_complex_measure(measure, params, year, gdp, inflation, unemployment)
        self.sorties = getattr(self, 'sorties', {})
        self.sorties.setdefault((year, measure['id']), []).append(
            (getattr(self, '_monde_actif', None), copy.deepcopy(out)))
        return out


LECTEURS_CROISES = {'fraude_sociale', 'prestations_indexation', 'asu', 'smic', 'fonction_publique'}


@pytest.mark.parametrize('levier, bloc', [
    ('niches_fiscales_tge', {'montant': 40}),
    ('fraude_fiscale', {'effort': 0.6}),
    ('retraites', {'indexation': 1.0, 'duree_cotisation': 43.0, 'age_depart': 65.0}),
    ('sante', dict(DROIT['sante'], effort_hopital=30)),
])
def test_b_levier_egal_au_droit_garde_ses_impacts_au_bit(levier, bloc):
    sim = _SimMondes(periods=10, mesures=_programme(**{levier: bloc}), annee_debut=DEBUT)
    _, _, rapport = sim.simulate()
    imp = _impacts(rapport)
    verifies = 0
    for (an, mid), sorties in sim.sorties.items():
        if an < DEBUT or mid == levier or mid in LECTEURS_CROISES:
            continue
        mondes = dict(sorties)
        assert set(mondes) == {'droit_2026', 'programme', 'droit_debut'}, (an, mid)
        assert mondes['programme'] == mondes['droit_debut'], (an, mid)
        if mid in imp[an]:
            dep, rec, i_droit = mondes['droit_2026']
            for cle, v in i_droit.items():
                if isinstance(v, float):
                    assert imp[an][mid][cle] == v, (an, mid, cle)
        verifies += 1
    assert verifies > 100


def test_b_programme_identique_au_droit_un_seul_monde():
    """Statu quo du cadre : aucun levier modifié, aucune composition (un seul
    appel par levier et par année)."""
    sim = _SimMondes(periods=10, mesures=copy.deepcopy(DROIT), annee_debut=DEBUT)
    sim.simulate()
    # Hors évaluations isolées de la décomposition de l'atterrissage (2026, monde « isole »).
    annuels = {k: [x for x in v if x[0] != 'isole'] for k, v in sim.sorties.items()}
    assert all(len(s) == 1 and s[0][0] is None for s in annuels.values() if s)


# ---------------------------------------------------------------------------
# Gardes de périmètre
# ---------------------------------------------------------------------------

def test_formules_asteval_sans_horloge():
    """Les leviers à formule (défense, collectivités, recherche, immigration)
    n'ont pas d'horloge : ils sont évalués une fois, sans composition. Garde :
    aucune formule ne lit l'année."""
    for m in load_policy_config()['mesures']:
        if m.get('type') == 'formule':
            assert 'annee' not in m['formule'], m['id']


@pytest.mark.parametrize('bloc, motif', [
    ({'retraites': {'indexation': 1.0, 'duree_cotisation': 42.5, 'age_depart': 63.0}}, 'retraites'),
    ({'education': {'budget': 70, 'enseignants': 0, 'salaires': 0}}, 'education'),
    ({'recherche_publique': {'budget': 12}}, 'recherche_publique'),
    ({'transition_ecologique': {'investissement': 5, 'renovation': 0, 'taxe_carbone': 44.6}},
     'transition_ecologique'),
    ({'tva_rate': {'taux': 0.21}}, 'tva_rate'),
])
def test_droit_non_composable_refuse_au_chargement(tmp_path, monkeypatch, bloc, motif):
    """Lecteurs latéraux hors handlers (offre et chômage seniors, effet d'offre,
    passage de la TVA dans les prix) : la composition à trois termes n'y est pas
    implémentée. Un droit en vigueur qui s'en écarte doit faire échouer le
    chargement — jamais une composition fausse en silence."""
    contenu = json.loads(cadre.DROIT_EN_VIGUEUR_PATH.read_text(encoding='utf-8'))
    contenu['mesures'].update(bloc)
    chemin = tmp_path / 'droit.json'
    chemin.write_text(json.dumps(contenu), encoding='utf-8')
    monkeypatch.setattr(cadre, 'DROIT_EN_VIGUEUR_PATH', chemin)
    cadre.charger_droit_en_vigueur.cache_clear()
    try:
        with pytest.raises(RuntimeError, match=motif):
            cadre.charger_droit_en_vigueur()
    finally:
        cadre.charger_droit_en_vigueur.cache_clear()


# ---------------------------------------------------------------------------
# RÉFUTEUR du lot C : bascule au milieu d'une horloge
# ---------------------------------------------------------------------------

def test_refuteur_c_levier_herite_ne_redemarre_pas():
    """Le programme change un AUTRE levier : la fraude fiscale du droit (0,14)
    continue sur l'horloge 2026 (50 % en 2028), elle ne repart pas à 20 %."""
    imp = _impacts(simuler(_programme(defense={'budget': 60}), annee_debut=DEBUT)[2])
    for an in range(2026, 2036):
        assert imp[an]['fraude_fiscale']['recettes'] == pytest.approx(
            0.68 * 30 * 0.14 * _progression_fraude(an - 2026), rel=1e-12), an


def test_refuteur_c_retrait_d_une_mesure_heritee():
    """Le programme ramène la fraude fiscale à 0 : l'effort hérité continue, le
    retrait (−0,14) entre sur l'horloge du programme — superposition linéaire,
    jamais une coupure sèche ni un recompte."""
    imp = _impacts(simuler(_programme(fraude_fiscale={'effort': 0}), annee_debut=DEBUT)[2])
    for an in range(2026, 2036):
        attendu = 0.68 * 30 * 0.14 * (_progression_fraude(an - 2026) - _progression_fraude(an - DEBUT))
        assert imp[an].get('fraude_fiscale', {}).get('recettes', 0.0) == pytest.approx(
            attendu, rel=1e-12, abs=1e-12), an


@pytest.mark.parametrize('nom', NOMS_PROGRAMMES)
def test_refuteur_c_avant_le_debut_toujours_le_droit(nom):
    """La composition n'existe qu'à partir du début : avant, chaque programme
    reste au bit le droit en vigueur (propriété a, après le lot C)."""
    egalite_bit_a_bit(simuler(CAS[nom], annee_debut=DEBUT), simuler(DROIT, annee_debut=DEBUT),
                      annees=range(2025, DEBUT), libelle=nom)


def test_refuteur_c_debut_2032_rampe_de_mandat_d_un_an():
    """Début 2032 : la rampe de mandat (effectifs) se réalise en une année."""
    sim = _SimFP(periods=10, mesures=_programme(fonction_publique={'effectifs': -50000, 'point_indice': 0}),
                 annee_debut=2032)
    sim.simulate()
    r = sim.releve[2032]
    assert r[0] + r[1] - r[2] == pytest.approx(-3119 * 6 / 6 + (-50000 + 3119), rel=1e-9)
