"""Effet d'offre structurel : ÉCHELLE — reprise sur le socle de la release E (chantier W6).

Origine : commit ``1e1f714`` de la branche ``feat/v0612-effet-offre-echelle``
(v0.6.12 jamais publiée, basée sur v0.6.11). Contrat de la release E (dépôt
parent, ``docs/plans/contrat-curseurs-release-E-2026-11.md``) : § 0.11 (seuls le
code et le test de ``1e1f714`` sont repris, ni instantanés ni documentation),
§ 6.7 (W6-1 à W6-3), § 7.1 (fichiers du chantier). Plan de la passe :
``docs/plans/moteur-v0612-effet-offre-echelle.md`` du parent (§ 2 sources,
§ 3 forme, § 6 décisions : VALEURS CENTRALES TELLES QUE LIVRÉES).

Constat (revue adverse v0.6.11, reproduit) : le bonus de potentiel d'un levier
valait ``coeff × log2(1 + |Δ|)``, somme clippée à ±0,20 pt. Le plafond était
atteint dès Δ ≈ 1 Md€ (``transition_invest`` : 0,0020 × log2(2)), si bien que
1 Md€ et 50 Md€ d'investissement recevaient la même prime d'offre : sur un
programme publié, ``transition_ecologique.investissement`` 0 → 2 Md€ déplaçait
la dette 2035 de −5,3 pt (1 Md€ suffisait), et sept des dix programmes publiés
recevaient le même −6 à −7 pt de dette 2035 quel que soit leur montant (de
3,8 Md€ de rénovation à 80 Md€). Un défaut d'échelle favorable aux petits
montants.

Forme reprise (``engine/growth.py``, pentes et sources : ``constants.py``, bloc
« RELEASE E — W6 », ``OFFRE_PENTE_*``, ``OFFRE_PLAFOND``) : contribution
LINÉAIRE par canal, ``pente × Δ`` (élasticité au stock de capital public / de
R&D publique, divisée par le stock), somme saturée en douceur vers le plafond
conventionnel : ``bonus = plafond × tanh(Σ / plafond)``.

Organisation du fichier (numéros cités dans le rapport du chantier) :

- W6-1 : les tests de ``1e1f714``, repris tels quels sur le fond. Deux
  adaptations de forme, sans changer aucune propriété : (a) les constantes sont
  lues À L'APPEL (``_c``), pour qu'un socle sans la reprise donne un échec PAR
  TEST, avec son motif, au lieu d'une erreur de collecte qui masquerait le reste
  de la suite ; (b) les scénarios publiés sont lus par le lecteur unique
  ``tests/snapshots/run_scenarios_full.SCENARIOS`` (lien ``frontend-react`` ou
  ``BUDGETLAB_SCENARIOS_JSON``), comme les autres tests du dépôt et la méta-garde
  anti-saut du parent.
- W6-2 : aucun des onze leviers de la release dans ``SUPPLY_EFFECTS`` ; leur
  neutralité au bit (G1) tient avec un effet d'offre actif.
- W6-3 : banc des dix scénarios — hors pytest (page d'expérience du chantier).
- W6-4 à W6-15 : propriétés que la lecture du code rend nécessaires (données
  sourcées, bloc du chantier, table des canaux, forme exacte, saturation de la
  SOMME, neutre au bit, référence sans effet d'offre, profils temporels, retour
  au défaut, solde et PIB, rénovation, porte de domaine), dont quatre tests PAR
  MUTATION qui prouvent qu'un effet compté deux fois fait rougir le test.

Toute valeur attendue est DÉRIVÉE : des constantes nommées de ``constants.py``,
des valeurs par défaut du registre (``load_default_values``), du droit en
vigueur (``droit_en_vigueur.json``) ou des délais et dépréciations du socle
(inchangés par ``1e1f714``, recopiés une fois dans ``DELAIS`` /
``DEPRECIATIONS`` avec leur origine, et verrouillés par W6-6).
"""
import contextlib
import json
import math
import os
import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from budget_simulator import constants as C
from budget_simulator.config import load_default_values
from budget_simulator.engine.cadre import ANNEE_DEBUT_MAX
from budget_simulator.engine.growth import GrowthMixin
from budget_simulator.simulator import BudgetSimulatorV45

RACINE = Path(__file__).absolute().parent.parent
CONSTANTS_PY = RACINE / 'budget_simulator' / 'constants.py'

sys.path.insert(0, str(RACINE / 'tests' / 'snapshots'))
from run_scenarios_full import SCENARIOS  # noqa: E402
from cadre_harness import pour_le_mode, rapport_g1  # noqa: E402

DROIT = json.loads((RACINE / 'budget_simulator' / 'data' / 'droit_en_vigueur.json')
                   .read_text(encoding='utf-8'))['mesures']


def _c(nom):
    """Constante de la reprise, lue à l'appel : sur un socle sans la reprise,
    chaque test échoue avec ce motif (et non une erreur de collecte)."""
    assert hasattr(C, nom), (
        f"constante {nom} absente de constants.py : effet d'offre « échelle » "
        "(commit 1e1f714) non repris — chantier W6 non livré")
    return getattr(C, nom)


def _plafond():
    return _c('OFFRE_PLAFOND')


# ---------------------------------------------------------------------------
# Canaux de l'effet d'offre : (levier, paramètre), délai, dépréciation.
# DELAIS et DEPRECIATIONS = valeurs du socle (``engine/growth.py``,
# ``SUPPLY_EFFECTS`` au commit dba7321), que ``1e1f714`` ne modifie pas (plan § 3 :
# « délais et dépréciations inchangés, non ré-audités ») ; W6-6 vérifie que la
# table du moteur les porte toujours.
# ---------------------------------------------------------------------------
CANAUX = {
    'recherche_publique': ('recherche_publique', 'budget'),
    'transition_invest': ('transition_ecologique', 'investissement'),
    'transition_renovation': ('transition_ecologique', 'renovation'),
    'education': ('education', 'budget'),
    # Revue adverse de la release E (R-2 C2) : l'investissement des
    # collectivités est du capital public comme celui de l'État (même pente,
    # même délai, même dépréciation).
    'collectivites_invest': ('collectivites', 'investissement'),
}
DELAIS = {'recherche_publique': 5, 'transition_invest': 3, 'transition_renovation': 2, 'education': 15,
          'collectivites_invest': 3}
DEPRECIATIONS = {'recherche_publique': 0.15, 'transition_invest': 0.05,
                 'transition_renovation': 0.03, 'education': 0.05, 'collectivites_invest': 0.05}


def _pentes():
    return {
        'recherche_publique': _c('OFFRE_PENTE_RD_PUBLIQUE'),
        'transition_invest': _c('OFFRE_PENTE_CAPITAL_PUBLIC'),
        'transition_renovation': _c('OFFRE_PENTE_RENOVATION'),
        'education': _c('OFFRE_PENTE_EDUCATION'),
        'collectivites_invest': _c('OFFRE_PENTE_CAPITAL_PUBLIC'),
    }


def _defauts():
    """Valeur de référence de chaque canal = défaut du registre (le moteur lit
    l'écart à ``_get_default_values()``, ``engine/growth.py``)."""
    d = load_default_values()
    return {cle: d[levier][param] for cle, (levier, param) in CANAUX.items()}


def _deltas(mesures):
    """Écart au défaut de chaque canal pour un programme constant."""
    defauts = _defauts()
    out = {}
    for cle, (levier, param) in CANAUX.items():
        bloc = mesures.get(levier)
        valeur = bloc.get(param, defauts[cle]) if isinstance(bloc, dict) else defauts[cle]
        out[cle] = valeur - defauts[cle]
    return out


def _bonus_attendu(contributions):
    """``plafond × tanh(Σ contributions / plafond)`` — forme du plan § 3."""
    p = _plafond()
    return p * math.tanh(sum(contributions) / p)


def _bonus_attendu_apres(mesures, annees):
    """Bonus attendu après ``annees`` années d'un programme constant : un canal
    ne contribue que si ``annees ≥ délai`` (compteur d'années actives)."""
    pentes = _pentes()
    return _bonus_attendu([pentes[k] * d for k, d in _deltas(mesures).items()
                           if d != 0 and annees >= DELAIS[k]])


def _simuler(mesures, annee_debut=None, rampe=None, strict=False):
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1' if strict else ''}):
        return BudgetSimulatorV45(periods=10, mesures=mesures, annee_debut=annee_debut,
                                  rampe=rampe).simulate()


@contextlib.contextmanager
def _sans_effet_d_offre():
    """Même moteur, canal d'offre retiré : la différence avec la simulation
    normale est l'effet d'offre SEUL (même dépense, même demande)."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(BudgetSimulatorV45, 'SUPPLY_EFFECTS', {})
        yield


def _bonus_consommes(mesures, annee_debut=None, rampe=None, strict=False):
    """{année: offre structurelle CONSOMMÉE par l'année} (photographie
    ``potentiel_de_l_annee``, celle que lisent croissance, Okun et output gap),
    sans arrondi."""
    journal = []

    def espion(self):
        photo = GrowthMixin.potentiel_de_l_annee(self)
        journal.append(photo.offre_structurelle)
        return photo

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(BudgetSimulatorV45, 'potentiel_de_l_annee', espion)
        df, _, _ = _simuler(mesures, annee_debut, rampe, strict)
    annees = [int(a) for a in df['Année']]
    assert len(journal) == len(annees), (len(journal), annees)
    return dict(zip(annees, journal))


def _canon(x):
    if isinstance(x, dict):
        return {str(k): _canon(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_canon(v) for v in x]
    if isinstance(x, float):
        return x.hex()
    return x


def _identiques_au_bit(a, b, contexte):
    df_a, det_a, rap_a = a
    df_b, det_b, rap_b = b
    assert df_a.equals(df_b), (contexte, 'trajectoire')
    assert det_a.equals(det_b), (contexte, 'détail')
    assert _canon(rap_a) == _canon(rap_b), (contexte, 'rapport')


# ===========================================================================
# W6-1 — tests du commit 1e1f714 (fond inchangé ; voir la docstring du module)
# ===========================================================================

def _bonus_apres(mesures, annees=7):
    s = BudgetSimulatorV45(periods=10, mesures=mesures)
    for y in range(1, annees + 1):
        s.update_potential_growth(0.01, y)
    return s._potential_growth_bonus


def _invest(x):
    return _bonus_apres({'transition_ecologique': {'investissement': x}})


def _recherche(x):
    return _bonus_apres({'recherche_publique': {'budget': x}})


def _scenarios():
    if not SCENARIOS:
        pytest.skip("scenarios.json introuvable (fork moteur public seul)")
    return SCENARIOS


def _dette_2035(mesures, levier, param, x):
    m = {**mesures, levier: {**(mesures.get(levier) or {}), param: x}}
    df, _, _ = BudgetSimulatorV45(periods=10, mesures=m).simulate()
    return float(df['Dette/PIB %'].iloc[-1])


# --- 1. Les constantes sont dérivées, pas des littéraux ---------------------

def test_pentes_derivees_des_elasticites_et_des_stocks():
    assert _c('OFFRE_PENTE_CAPITAL_PUBLIC') == pytest.approx(
        _c('ELASTICITE_PIB_CAPITAL_PUBLIC') * _c('EFFICIENCE_INVESTISSEMENT_PUBLIC')
        / _c('CAPITAL_PUBLIC_PRODUCTIF_MD_EUR'))
    assert _c('OFFRE_PENTE_RD_PUBLIQUE') == pytest.approx(
        _c('ELASTICITE_PIB_CAPITAL_RD_PUBLIC')
        / (_c('INVESTISSEMENT_RD_APU_MD_EUR') / _c('DEPRECIATION_RD_PUBLIQUE')))
    assert _c('OFFRE_PENTE_RENOVATION') == 0.0
    # Ordres de grandeur sourcés : +0,005 pt par Md€/an de capital public,
    # +0,03 pt par Md€/an de R&D publique.
    assert 4e-5 < _c('OFFRE_PENTE_CAPITAL_PUBLIC') < 6e-5
    assert 2.5e-4 < _c('OFFRE_PENTE_RD_PUBLIQUE') < 4e-4
    assert _plafond() == 0.002


def test_la_table_du_moteur_lit_les_constantes():
    tbl = BudgetSimulatorV45.SUPPLY_EFFECTS
    assert tbl['transition_invest'].get('pente') == _c('OFFRE_PENTE_CAPITAL_PUBLIC')
    assert tbl['recherche_publique'].get('pente') == _c('OFFRE_PENTE_RD_PUBLIQUE')
    assert tbl['transition_renovation'].get('pente') == _c('OFFRE_PENTE_RENOVATION')
    assert tbl['education'].get('pente') == _c('OFFRE_PENTE_EDUCATION')
    assert tbl['collectivites_invest'].get('pente') == _c('OFFRE_PENTE_CAPITAL_PUBLIC')
    assert tbl['recherche_publique']['deprec'] == _c('DEPRECIATION_RD_PUBLIQUE')
    assert all('coeff' not in cfg for cfg in tbl.values())


# --- 2. Propriétés de la forme ------------------------------------------------

def test_nul_en_zero_et_continu_a_l_origine():
    assert _invest(0) == 0.0
    assert abs(_invest(1e-6)) < 1e-9
    assert abs(_invest(1e-6) - _invest(0)) < 1e-9


@pytest.mark.parametrize('f', [_invest, _recherche])
def test_monotone_et_strictement_croissant(f):
    xs = [0, 0.1, 0.5, 1, 2, 5, 10, 20, 30, 50]
    if f is _recherche:
        xs = [10 + x for x in [0, 0.1, 0.5, 1, 2, 5, 10]]
    vals = [f(x) for x in xs]
    assert all(b > a for a, b in zip(vals, vals[1:])), vals


def test_proportionnel_aux_petits_montants_1_10_50():
    """1 Md€ ≪ 10 Md€ ≪ 50 Md€ : le rapport des bonus suit le rapport des
    montants tant que la saturation ne mord pas (dérivée 1 à l'origine)."""
    b1, b10, b50 = _invest(1), _invest(10), _invest(50)
    assert b1 < b10 < b50
    assert b10 / b1 == pytest.approx(10, rel=0.03)      # quasi linéaire à 10 Md€
    assert 3 < b50 / b10 < 5                            # saturation visible à 50
    # Forme exacte : plafond × tanh(pente × Δ / plafond).
    p, pente = _plafond(), _c('OFFRE_PENTE_CAPITAL_PUBLIC')
    assert b1 == pytest.approx(p * math.tanh(pente * 1 / p), abs=1e-12)
    assert b50 == pytest.approx(p * math.tanh(pente * 50 / p), abs=1e-12)


def test_impair_symetrie_coupe_hausse():
    assert _recherche(15) == pytest.approx(-_recherche(5), abs=1e-12)


def test_borne_par_le_plafond_sans_marche():
    """Le plafond ±0,20 pt n'est jamais dépassé, et il n'y a plus de clip actif :
    à 50 Md€ de capital public + 20 Md€ de recherche, le bonus reste
    strictement sous le plafond (asymptote)."""
    p = _plafond()
    gros = _bonus_apres({'transition_ecologique': {'investissement': 50, 'renovation': 40},
                         'recherche_publique': {'budget': 20}})
    assert 0.95 * p < gros < p
    coupe = _bonus_apres({'recherche_publique': {'budget': 0},
                          'transition_ecologique': {'investissement': 0, 'renovation': 0},
                          'education': {'budget': 30}}, annees=19)
    assert -p < coupe <= 0


def test_echelle_du_plafond_plusieurs_dizaines_de_md_eur():
    """Mi-plafond (0,10 pt) du capital public à ≈ 22 Md€/an ; 1 Md€ en donne
    moins de 3 %. Jusqu'en v0.6.11, 1 Md€ donnait 100 % du plafond."""
    p = _plafond()
    assert _invest(1) < 0.03 * p
    assert 0.45 * p < _invest(22) < 0.55 * p
    assert _invest(50) > 0.8 * p


def test_renovation_sans_effet_d_offre():
    """ThreeME (Trésor-Éco n° 394) : aucun effet de niveau durable."""
    assert _bonus_apres({'transition_ecologique': {'renovation': 20}}) == 0.0


def test_education_inerte_sur_l_horizon():
    assert _bonus_apres({'education': {'budget': 85}}, annees=10) == 0.0


# --- 3. Le cas de la revue adverse, mesuré en dette ----------------------------

def _programme_publie_sans_investissement_de_transition():
    """Premier programme publié (ordre des identifiants) dont l'investissement de
    transition est au défaut (0) : le cas de la revue adverse v0.6.11, choisi
    par sa propriété et non par son nom."""
    for nom in sorted(_scenarios()):
        sc = _scenarios()[nom]
        if (sc.get('transition_ecologique') or {}).get('investissement', 0) == 0:
            return sc
    pytest.skip("aucun programme publié sans investissement de transition")


def test_2_md_eur_d_investissement_ne_sont_plus_un_plafond():
    """Programme publié sans investissement de transition, porté à 0 → 1 → 2 Md€ :
    l'effet sur la dette 2035 est de l'ordre du montant (dixièmes de point,
    proportionnel : 2 Md€ ≈ 2 × 1 Md€), plus −5,3 pt pour 2 Md€ dont −5,3 dès
    1 Md€ (v0.6.11, plafond atteint)."""
    sc = _programme_publie_sans_investissement_de_transition()
    d0 = _dette_2035(sc, 'transition_ecologique', 'investissement', 0)
    d1 = _dette_2035(sc, 'transition_ecologique', 'investissement', 1)
    d2 = _dette_2035(sc, 'transition_ecologique', 'investissement', 2)
    assert abs(d1 - d0) < 0.3 and abs(d2 - d0) < 0.5          # v0.6.11 : 5,3
    assert (d2 - d0) == pytest.approx(2 * (d1 - d0), rel=0.25)  # proportionnel


def test_effet_par_md_eur_borne_et_decroissant_dans_l_investissement_vert():
    """Budget 2026 voté, curseur d'investissement vert tiré seul : l'effet sur la
    dette 2035 par Md€/an est borné (|Δ| ≤ 0,15 pt par Md€, contre 5,4 pt pour le
    premier Md€ en v0.6.11) et le rendement marginal décroît avec le montant
    (saturation). Le SIGNE n'est pas verrouillé : au central de la littérature
    (élasticité 0,106, FMI WP 15/95 : « the public-debt-to-GDP ratio may actually
    decline »), le ratio baisse encore légèrement — dit dans METHODOLOGIE."""
    sc = DROIT          # le budget 2026 voté, tel que le moteur le tient (droit en vigueur)
    d0 = _dette_2035(sc, 'transition_ecologique', 'investissement', 0)
    effets = {x: _dette_2035(sc, 'transition_ecologique', 'investissement', x) - d0 for x in (1, 5, 20, 50)}
    for x, e in effets.items():
        assert abs(e) <= 0.15 * x, effets
    par_md = {x: abs(e) / x for x, e in effets.items()}
    assert par_md[50] < par_md[20] < par_md[5] <= par_md[1] * 1.02, par_md


# ===========================================================================
# W6-2 — les onze leviers de la release E hors de l'effet d'offre
# ===========================================================================

def _sondes_non_neutres(levier):
    """Une valeur NON neutre par paramètre (à mi-chemin du neutre et de la borne
    haute, de la borne basse si le neutre est la borne haute ; paramètre de mode
    exclusif sans neutre : mi-chemin de 0 et de la borne haute)."""
    entrees = {m['id']: m for m in json.loads(
        (RACINE / 'policy_measures.json').read_text(encoding='utf-8'))['mesures']}
    sondes = []
    for param, spec in entrees[levier]['parametres'].items():
        neutre, bas, haut = spec.get('valeur_defaut', 0), spec['min'], spec['max']
        x = neutre + (haut - neutre) / 2 if haut > neutre else neutre - (neutre - bas) / 2
        sondes.append({param: x})
    return sondes


def _verifier_w6_2_table():
    """Aucun canal d'offre ne lit un levier de la release."""
    leviers_e = set(C.LEVIERS_RELEASE_E)
    assert len(leviers_e) == 11
    lus = {cfg['measure_id'] for cfg in BudgetSimulatorV45.SUPPLY_EFFECTS.values()}
    assert not lus & leviers_e, sorted(lus & leviers_e)


def _verifier_w6_2_trajectoire():
    """Chaque paramètre de chaque levier, à une valeur non neutre, laisse l'offre
    structurelle consommée à 0,0 chaque année, dans les deux modes (porte
    tolérante : un levier encore squelette échoue en signalant son échec, l'offre
    est lue à part, dans ``self.mesures``)."""
    for levier in C.LEVIERS_RELEASE_E:
        for sonde in _sondes_non_neutres(levier):
            for annee_debut in (None, 2028):
                bonus = _bonus_consommes({levier: sonde}, annee_debut)
                assert all(b == 0.0 for b in bonus.values()), (levier, sonde, annee_debut, bonus)


def test_w6_2_aucun_levier_de_la_release_dans_l_effet_d_offre():
    """Contrat § 6.7 W6-2 (cadrage § 7.4) : un montant en Md€ des nouveaux
    curseurs (crédits, transferts en capital, prestations…) n'est pas du capital
    public productif ; lui donner un effet d'offre compterait deux fois un
    investissement déjà porté par ``transition_ecologique.investissement``."""
    _verifier_w6_2_table()
    _verifier_w6_2_trajectoire()


def test_w6_2_mutation_levier_de_la_release_compte_en_capital_rougit():
    """Par mutation : un canal d'offre ajouté sur ``depenses_publiques.credits_etat``
    (même pente et même délai que le capital public) fait rougir les deux
    vérifications de W6-2, la table ET la trajectoire."""
    _verifier_w6_2_table()  # témoins : le moteur livré passe
    _verifier_w6_2_trajectoire()
    table = dict(BudgetSimulatorV45.SUPPLY_EFFECTS)
    table['credits_etat'] = {**table['transition_invest'], 'param': 'credits_etat',
                             'measure_id': 'depenses_publiques'}
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(BudgetSimulatorV45, 'SUPPLY_EFFECTS', table)
        with pytest.raises(AssertionError):
            _verifier_w6_2_table()
        with pytest.raises(AssertionError):
            _verifier_w6_2_trajectoire()


# Bases où l'effet d'offre est ACTIF, disponibles dans le dépôt public seul (les
# dix scénarios publiés sont couverts sur cette branche par
# test_release_e_socle.py::test_g1_neutralite_au_bit, dont sept ont un canal
# d'offre actif) : une hausse sur deux canaux, une coupe sur un canal.
BASES_OFFRE_ACTIVE = {
    'hausse': {'transition_ecologique': {'investissement': 20}, 'recherche_publique': {'budget': 15}},
    'coupe': {'recherche_publique': {'budget': 5}},
}
_CACHE_BASES = {}


def _simuler_base(nom, annee_debut, strict):
    cle = (nom, annee_debut, strict)
    if cle not in _CACHE_BASES:
        _CACHE_BASES[cle] = _simuler(BASES_OFFRE_ACTIVE[nom], annee_debut, strict=strict)
    return _CACHE_BASES[cle]


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
@pytest.mark.parametrize('levier', list(C.LEVIERS_RELEASE_E))
def test_w6_2_g1_neutralite_au_bit_avec_effet_d_offre_actif(levier, annee_debut, strict):
    for nom, base in BASES_OFFRE_ACTIVE.items():
        ref = _simuler_base(nom, annee_debut, strict)
        assert (ref[1]['Bonus_Potentiel_Supply %'] != 0).any(), (nom, 'base sans effet d\'offre')
        avec = _simuler({**base, levier: dict(C.NEUTRES_RELEASE_E[levier])}, annee_debut, strict=strict)
        # Release P : rapport comparé hors la seule différence d'un levier à
        # taux inscrit au droit (cadre_harness.rapport_g1).
        avec = (avec[0], avec[1], rapport_g1(avec[2], levier))
        _identiques_au_bit(avec, ref, (nom, levier, annee_debut, strict))


# ===========================================================================
# W6-4 — données sourcées : valeurs centrales TELLES QUE LIVRÉES (plan § 6)
# ===========================================================================

def test_w6_4_donnees_sourcees_valeurs_centrales_livrees():
    """Valeurs du plan § 2 (sources) et § 3 (dérivation), décision « valeurs
    centrales telles que livrées » : aucune n'est modifiée par la reprise."""
    # Bom & Ligthart (2014), J. Economic Surveys 28(5) : moyenne des 578 estimations.
    assert _c('ELASTICITE_PIB_CAPITAL_PUBLIC') == 0.106
    # FMI (2015), « Making Public Investment More Efficient » : écart d'efficience
    # de 13 % dans les économies avancées.
    assert _c('EFFICIENCE_INVESTISSEMENT_PUBLIC') == 0.87
    assert _c('EFFICIENCE_INVESTISSEMENT_PUBLIC') == pytest.approx(1 - 0.13, abs=1e-15)
    # INSEE, comptes de patrimoine 2025 (via FIPECO 2026) : 2 945 Md€ d'actifs non
    # financiers des APU, dont 37 % de terrains.
    assert _c('CAPITAL_PUBLIC_PRODUCTIF_MD_EUR') == 2945 * (1 - 0.37)
    # Fieldhouse & Mertens (Dallas Fed WP 2305 rév. 2024), R&D non militaire.
    assert _c('ELASTICITE_PIB_CAPITAL_RD_PUBLIC') == 0.06
    # INSEE 2025 (via FIPECO) : 28 Md€ de R&D des APU ; dépréciation du canal.
    assert _c('INVESTISSEMENT_RD_APU_MD_EUR') == 28.0
    assert _c('DEPRECIATION_RD_PUBLIQUE') == DEPRECIATIONS['recherche_publique']
    assert _c('CAPITAL_RD_PUBLIC_MD_EUR') == (_c('INVESTISSEMENT_RD_APU_MD_EUR')
                                              / _c('DEPRECIATION_RD_PUBLIQUE'))
    # Dérivations EXACTES (expressions des noms, jamais un nombre recopié).
    assert _c('OFFRE_PENTE_CAPITAL_PUBLIC') == (
        _c('ELASTICITE_PIB_CAPITAL_PUBLIC') * _c('EFFICIENCE_INVESTISSEMENT_PUBLIC')
        / _c('CAPITAL_PUBLIC_PRODUCTIF_MD_EUR'))
    assert _c('OFFRE_PENTE_RD_PUBLIQUE') == (_c('ELASTICITE_PIB_CAPITAL_RD_PUBLIC')
                                             / _c('CAPITAL_RD_PUBLIC_MD_EUR'))
    # Rénovation : ThreeME (Trésor-Éco n° 394), aucun effet de niveau durable.
    assert _c('OFFRE_PENTE_RENOVATION') == 0.0
    # Éducation : convention v3.1 (rapport 1/2 des anciens coefficients).
    assert _c('OFFRE_PENTE_EDUCATION') == _c('OFFRE_PENTE_CAPITAL_PUBLIC') * 0.5
    # Plafond conventionnel ±0,20 pt, inchangé depuis la v3.1.
    assert _plafond() == 0.002


def test_w6_4_ordres_de_grandeur_publies_par_le_plan():
    """Recoupement avec le tableau du plan § 3 (« +0,005 pt », « +0,032 pt » par
    Md€/an ; mi-plafond 22 et 3,4 Md€/an ; 90 % du plafond à 59 et 9 Md€/an),
    chaque seuil recalculé depuis les constantes : x = plafond × atanh(f) / pente."""
    p = _plafond()
    pc, prd = _c('OFFRE_PENTE_CAPITAL_PUBLIC'), _c('OFFRE_PENTE_RD_PUBLIQUE')
    assert round(100 * pc, 3) == 0.005 and round(100 * prd, 3) == 0.032
    assert round(p * math.atanh(0.5) / pc) == 22 and round(p * math.atanh(0.5) / prd, 1) == 3.4
    assert round(p * math.atanh(0.9) / pc) == 59 and round(p * math.atanh(0.9) / prd) == 9


# ===========================================================================
# W6-5 — les constantes vivent dans le bloc du chantier (contrat § 7.1)
# ===========================================================================

NOMS_W6 = ('ELASTICITE_PIB_CAPITAL_PUBLIC', 'EFFICIENCE_INVESTISSEMENT_PUBLIC',
           'CAPITAL_PUBLIC_PRODUCTIF_MD_EUR', 'ELASTICITE_PIB_CAPITAL_RD_PUBLIC',
           'INVESTISSEMENT_RD_APU_MD_EUR', 'DEPRECIATION_RD_PUBLIQUE', 'CAPITAL_RD_PUBLIC_MD_EUR',
           'OFFRE_PENTE_CAPITAL_PUBLIC', 'OFFRE_PENTE_RD_PUBLIQUE', 'OFFRE_PENTE_RENOVATION',
           'OFFRE_PENTE_EDUCATION', 'OFFRE_PLAFOND')


def test_w6_5_constantes_dans_le_bloc_w6_de_constants_py():
    """Contrat § 7.1 : chaque chantier écrit dans SON bloc balisé de
    ``constants.py`` (fusion des cinq branches sans conflit) ; W6 = les lignes
    de 1e1f714, déplacées dans « RELEASE E — W6 ». Chaque nom y est affecté une
    fois, et nulle part ailleurs. NB : la garde du socle exigeait des blocs de
    chantier vides (état du commit socle, § 7.2-2), ce qui contredisait le
    § 7.1 dès qu'un chantier livre ses constantes ; elle ne vérifie plus que
    l'ordre des balises (``test_release_e_socle.py::test_blocs_balises_dans_l_ordre``)."""
    texte = CONSTANTS_PY.read_text(encoding='utf-8')
    debut = texte.index('# === RELEASE E — W6 ===')
    fin = texte.index('# === FIN RELEASE E ===', debut)
    bloc, dehors = texte[debut:fin], texte[:debut] + texte[fin:]
    for nom in NOMS_W6:
        affectation = re.compile(rf'^{nom}\s*=', re.MULTILINE)
        assert len(affectation.findall(bloc)) == 1, (nom, 'absent du bloc W6')
        assert not affectation.findall(dehors), (nom, 'affecté hors du bloc W6')


# ===========================================================================
# W6-6 — table des canaux : quatre canaux, chacun lu une fois, délais inchangés
# ===========================================================================

def test_w6_6_table_cinq_canaux_uniques_delais_et_depreciations():
    """Anti-double-compte structurel : un (levier, paramètre) n'alimente qu'un
    canal. La reprise ne change que la pente (plan § 3) : délais et
    dépréciations du socle. Un canal ajouté par la revue adverse de la release
    E (R-2 C2) : ``collectivites.investissement``, capital public comme
    l'investissement de l'État (même pente, délai, dépréciation). Remplace la
    version qui verrouillait son exclusion (plan § 6 point 6, sur la prémisse
    fausse qu'aucun programme publié ne l'utilisait)."""
    tbl = BudgetSimulatorV45.SUPPLY_EFFECTS
    assert set(tbl) == set(CANAUX)
    lus = [(cfg['measure_id'], cfg['param']) for cfg in tbl.values()]
    assert len(set(lus)) == len(lus), lus
    for cle, cfg in tbl.items():
        assert (cfg['measure_id'], cfg['param']) == CANAUX[cle]
        assert cfg['delay'] == DELAIS[cle] and cfg['deprec'] == DEPRECIATIONS[cle], cle


# ===========================================================================
# W6-7 — forme exacte : somme des canaux actifs, saturée une fois
# ===========================================================================

CAS_FORME = [
    {'transition_ecologique': {'investissement': 1}},
    {'transition_ecologique': {'investissement': 10}},
    {'transition_ecologique': {'investissement': 50}},
    {'recherche_publique': {'budget': 12}},
    {'recherche_publique': {'budget': 3}},
    {'transition_ecologique': {'investissement': 30, 'renovation': 40}, 'recherche_publique': {'budget': 14}},
    {'transition_ecologique': {'investissement': 50}, 'recherche_publique': {'budget': 20},
     'education': {'budget': 90}},
    {'transition_ecologique': {'investissement': 5}, 'recherche_publique': {'budget': 0}},
]


def _verifier_forme_exacte():
    for mesures in CAS_FORME:
        for annees in (1, 2, 3, 4, 5, 7, 10):
            obtenu = _bonus_apres(mesures, annees)
            attendu = _bonus_attendu_apres(mesures, annees)
            assert obtenu == pytest.approx(attendu, abs=1e-15), (mesures, annees, obtenu, attendu)


def test_w6_7_forme_exacte_somme_saturee_des_canaux_actifs():
    """Bonus = plafond × tanh(Σ_{canaux actifs} pente × Δ / plafond), un canal
    étant actif quand son compteur d'années atteint son délai : un seul
    plafond, appliqué à la SOMME (pas de saturation par canal ni de clip actif)."""
    _verifier_forme_exacte()


def test_w6_7_mutation_canal_compte_deux_fois_rougit():
    """Par mutation : le canal « capital public » présent deux fois dans la
    table (effet compté deux fois) fait rougir W6-7."""
    _verifier_forme_exacte()  # témoin
    table = dict(BudgetSimulatorV45.SUPPLY_EFFECTS)
    table['transition_invest_doublon'] = dict(table['transition_invest'])
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(BudgetSimulatorV45, 'SUPPLY_EFFECTS', table)
        with pytest.raises(AssertionError):
            _verifier_forme_exacte()


# ===========================================================================
# W6-8 — symétrie et saturation de la somme (compensation, seuils exacts)
# ===========================================================================

def test_w6_8_symetrie_impaire_exacte():
    """Coupe = hausse en miroir (v0.6.0) : bonus(défaut + x) = −bonus(défaut − x)."""
    ref = _defauts()['recherche_publique']
    for x in (0.5, 1, 3, 5, 10):
        assert _recherche(ref + x) == pytest.approx(-_recherche(ref - x), abs=1e-15), x
        assert _recherche(ref + x) > 0


def test_w6_8_hausse_et_coupe_de_meme_contribution_s_annulent():
    """Saturation sur la SOMME : 50 Md€ de capital public (au-delà du
    mi-plafond seul) et une coupe de recherche de même contribution s'annulent
    exactement — sous l'ancienne forme (clip de la somme de log2), le bonus
    restait au plafond."""
    pc, prd = _c('OFFRE_PENTE_CAPITAL_PUBLIC'), _c('OFFRE_PENTE_RD_PUBLIQUE')
    coupe = 50 * pc / prd                          # Md€ de recherche de même contribution
    ref = _defauts()['recherche_publique']
    assert 0 < coupe < ref                         # dans le domaine du levier
    b = _bonus_apres({'transition_ecologique': {'investissement': 50},
                      'recherche_publique': {'budget': ref - coupe}})
    assert abs(b) < 1e-15, b


def test_w6_8_mi_plafond_et_neuf_dixiemes_exacts():
    """Seuils dérivés : x(f) = défaut + plafond × atanh(f) / pente donne
    exactement f × plafond (capital public : mi-plafond ; recherche : mi-plafond
    et 90 %, dans le domaine [0 ; 20])."""
    p = _plafond()
    pc, prd = _c('OFFRE_PENTE_CAPITAL_PUBLIC'), _c('OFFRE_PENTE_RD_PUBLIQUE')
    ref = _defauts()['recherche_publique']
    assert _invest(p * math.atanh(0.5) / pc) == pytest.approx(0.5 * p, rel=1e-12)
    assert _recherche(ref + p * math.atanh(0.5) / prd) == pytest.approx(0.5 * p, rel=1e-12)
    assert _recherche(ref + p * math.atanh(0.9) / prd) == pytest.approx(0.9 * p, rel=1e-12)


# ===========================================================================
# W6-9 — neutre : aucun écart d'offre ⇒ sorties identiques AU BIT à un moteur
# sans canal d'offre (dix scénarios, deux modes, deux portes)
# ===========================================================================

BASES_NEUTRE = {'statu_quo': {}, 'droit_en_vigueur': DROIT, **SCENARIOS}


def _au_defaut_sur_l_offre(mesures):
    """Le programme, paramètres d'offre ramenés au défaut (le reste inchangé)."""
    defauts = _defauts()
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in mesures.items()}
    for cle, (levier, param) in CANAUX.items():
        if isinstance(out.get(levier), dict) and param in out[levier]:
            out[levier][param] = defauts[cle]
    return out


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
def test_w6_9_neutre_sorties_identiques_au_bit(annee_debut, strict):
    """La reprise ne fait naître aucun effet à écart nul (pas de « naissance
    d'un coup », v0.6.7) : pour chaque base, paramètres d'offre au défaut,
    simulation identique au bit (trajectoire, détail, rapport) à la même
    simulation sans canal d'offre. Les scénarios publiés dont aucun paramètre
    d'offre ne s'écarte du défaut sont donc inchangés par W6."""
    if len(BASES_NEUTRE) < 12:
        assert len(BASES_NEUTRE) == 2  # dépôt public seul : statu quo et droit en vigueur
    for nom, base in BASES_NEUTRE.items():
        neutre = _au_defaut_sur_l_offre(pour_le_mode(base, annee_debut))
        assert all(d == 0 for d in _deltas(neutre).values()), nom
        avec = _simuler(neutre, annee_debut, strict=strict)
        with _sans_effet_d_offre():
            sans = _simuler(neutre, annee_debut, strict=strict)
        _identiques_au_bit(avec, sans, (nom, annee_debut, strict))


# ===========================================================================
# W6-10 — la référence ne porte aucun effet d'offre
# ===========================================================================

@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
def test_w6_10_droit_en_vigueur_sans_effet_d_offre(annee_debut):
    """Anti-double-compte : le potentiel du moteur est calé avec le droit en
    vigueur ; si le droit s'écartait du défaut sur un canal d'offre, le statu
    quo recevrait un bonus déjà compté dans le tendanciel. Le droit est donc égal
    au défaut sur chaque canal, et le statu quo consomme 0,0 chaque année."""
    defauts = _defauts()
    for cle, (levier, param) in CANAUX.items():
        assert DROIT.get(levier, {}).get(param, defauts[cle]) == defauts[cle], cle
    for base in ({}, DROIT):
        assert all(b == 0.0 for b in _bonus_consommes(base, annee_debut).values())


# ===========================================================================
# W6-11 — profils temporels : délai, origine du programme, rampe
# ===========================================================================

def _attendu_par_annee(cle, valeur_de_l_annee, debut, annees):
    """Offre consommée attendue pour UN canal dont l'écart ne s'annule pas après
    ``debut`` : le compteur atteint le délai à la fin de ``debut + délai − 1`` ;
    la contribution posée en fin d'année a (pente × Δ de l'année a) est
    consommée en a + 1."""
    pente, defaut = _pentes()[cle], _defauts()[cle]
    premiere = debut + DELAIS[cle]
    return {a: (_bonus_attendu([pente * (valeur_de_l_annee(a - 1) - defaut)]) if a >= premiere else 0.0)
            for a in annees}


def _verifier_profil(cle, mesures, annee_debut=None, rampe=None, valeur_de_l_annee=None):
    levier, param = CANAUX[cle]
    debut = annee_debut or C.POLICY_START_YEAR
    if valeur_de_l_annee is None:
        def valeur_de_l_annee(a):
            return mesures[levier][param]
    obtenu = _bonus_consommes(mesures, annee_debut, rampe)
    attendu = _attendu_par_annee(cle, valeur_de_l_annee, debut, obtenu)
    for a in obtenu:
        assert obtenu[a] == pytest.approx(attendu[a], abs=1e-15), (cle, a, obtenu[a], attendu[a])
    return obtenu


def test_w6_11_historique_capital_public_apres_le_delai():
    b = _verifier_profil('transition_invest', {'transition_ecologique': {'investissement': 20}})
    assert min(a for a, v in b.items() if v) == C.POLICY_START_YEAR + DELAIS['transition_invest']


def test_w6_11_historique_coupe_de_recherche_miroir():
    b = _verifier_profil('recherche_publique', {'recherche_publique': {'budget': 0}})
    assert all(v <= 0 for v in b.values()) and any(v < 0 for v in b.values())


def test_w6_11_cadre_rien_avant_le_debut_du_programme_plus_le_delai():
    """Mode cadre : les années avant ``annee_debut`` sont au droit en vigueur
    (aucun écart), le compteur part de ``annee_debut``."""
    b = _verifier_profil('transition_invest', {'transition_ecologique': {'investissement': 20}},
                         annee_debut=2028)
    assert min(a for a, v in b.items() if v) == 2028 + DELAIS['transition_invest']


def test_w6_11_cadre_recherche_hors_du_mandat():
    """Mode cadre dès 2028 : le canal R&D (délai 5) n'est consommé qu'à partir de
    2033, après la dernière année du mandat (``ANNEE_DEBUT_MAX``) : il ne pèse
    sur aucun chiffre publié 2028-2032."""
    b = _verifier_profil('recherche_publique', {'recherche_publique': {'budget': 20}}, annee_debut=2028)
    assert 2028 + DELAIS['recherche_publique'] > ANNEE_DEBUT_MAX
    assert all(v == 0.0 for a, v in b.items() if a <= ANNEE_DEBUT_MAX)
    assert all(v > 0 for a, v in b.items() if a >= 2028 + DELAIS['recherche_publique'])


def test_w6_11_rampe_bonus_lineaire_dans_le_niveau_de_l_annee():
    """Rampe de cinq ans (cadre 2028) : la contribution suit le NIVEAU rampé de
    l'année où elle est posée (``p_ref + (p − p_ref) × k / n``, arithmétique de
    ``_mesures_rampees``), sans cumul ni effet du palier anticipé."""
    n, cible = 5, 50
    p_ref = DROIT['transition_ecologique']['investissement']

    def valeur_de_l_annee(a):
        k = a - 2028 + 1
        return p_ref + (cible - p_ref) * k / n if k < n else cible

    b = _verifier_profil('transition_invest', {'transition_ecologique': {'investissement': cible}},
                         annee_debut=2028,
                         rampe={'annees': n, 'leviers': ['transition_ecologique.investissement']},
                         valeur_de_l_annee=valeur_de_l_annee)
    assert 0 < b[2031] < b[2032] < b[2033] == b[2035]


# ===========================================================================
# W6-12 — retour au défaut : dépréciation de la contribution, une seule année
# ===========================================================================

def _suite_de_bonus(cle, valeurs):
    """Bonus après chaque année quand le paramètre suit ``valeurs`` (une valeur
    par année, le programme changeant d'une année sur l'autre)."""
    levier, param = CANAUX[cle]
    s = BudgetSimulatorV45(periods=10, mesures={})
    out = []
    for y, v in enumerate(valeurs, start=1):
        s.mesures = {levier: {param: v}}
        s.update_potential_growth(0.01, y)
        out.append(s._potential_growth_bonus)
    return out


@pytest.mark.parametrize('cle, ecart, actives, retour', [
    ('transition_invest', 20, 4, 6),
    ('recherche_publique', -10, 6, 4),
])
def test_w6_12_retour_au_defaut_depreciation_de_la_contribution(cle, ecart, actives, retour):
    """Écart pendant ``actives`` années puis retour au défaut : la contribution
    LINÉAIRE du canal décroît de (1 − dépréciation) par an, et la saturation
    s'applique à la contribution dépréciée (jamais au bonus saturé)."""
    defaut = _defauts()[cle]
    obtenu = _suite_de_bonus(cle, [defaut + ecart] * actives + [defaut] * retour)
    contribution, attendu = 0.0, []
    for y in range(1, actives + retour + 1):
        if y <= actives:
            if y >= DELAIS[cle]:
                contribution = _pentes()[cle] * ecart
        else:
            assert abs(contribution) > 1e-5      # au-dessus du seuil d'extinction du moteur
            contribution = contribution * (1 - DEPRECIATIONS[cle])
        attendu.append(_bonus_attendu([contribution]))
    assert obtenu == pytest.approx(attendu, abs=1e-15)
    assert abs(obtenu[-1]) < abs(obtenu[actives - 1])


@pytest.mark.parametrize('cle, ecart', [('transition_invest', 20), ('recherche_publique', 10),
                                        ('recherche_publique', -10)])
def test_w6_12_une_seule_annee_aucun_bonus(cle, ecart):
    """Un écart d'une seule année n'atteint jamais le délai du canal (≥ 2 ans) :
    aucun bonus, retour exact à 0 (propriété du compteur d'années, inchangée par
    la reprise ; c'est le cas du profil « une seule année » de W1)."""
    defaut = _defauts()[cle]
    assert DELAIS[cle] >= 2
    assert _suite_de_bonus(cle, [defaut + ecart] + [defaut] * 9) == [0.0] * 10


# ===========================================================================
# W6-13 — solde et PIB : l'effet d'offre est compté UNE fois
# ===========================================================================

CAS_MACRO = [
    ('transition_invest', {'transition_ecologique': {'investissement': 20}}, None),
    ('transition_invest', {'transition_ecologique': {'investissement': 50}}, 2028),
    ('recherche_publique', {'recherche_publique': {'budget': 20}}, None),
    ('recherche_publique', {'recherche_publique': {'budget': 0}}, None),
]
# Tolérance de l'identité du premier ordre : ±10 % [CALCUL : écart mesuré ≤ 3 %
# sur ces cas (arrondis de sortie à 0,1 Md€, termes du second ordre) ; un effet
# compté deux fois donne un rapport ≈ 2].
TOLERANCE_PREMIER_ORDRE = 0.10
# En dessous de 0,02 pt de PIB, seul le signe est vérifié [CALCUL : recettes et
# dépenses publiées à 0,1 Md€ près, soit ≈ 0,003 pt d'un PIB de ≈ 3 000 Md€].
SEUIL_RAPPORT_PT = 0.02


def _solde_primaire_pct(df, det, i):
    return 100 * (det['Recettes_Totales'].iloc[i] - det['Dépenses_Totales'].iloc[i]) / df['PIB'].iloc[i]


def _verifier_effet_macro_compte_une_fois():
    """Effet d'offre SEUL = simulation normale − même simulation sans canal
    d'offre. Avec b = plafond × tanh(pente × Δ / plafond) consommé chaque année
    à partir de ``début + délai`` et L_n = (1 + b)^n − 1 après n années :
    (i) avant la première année consommée, les deux simulations sont identiques
    au bit ; (ii) niveau du PIB réel : rapport − 1 = L_n ; (iii) solde primaire :
    + (dépenses primaires / PIB) × L_n / (1 + L_n) (recettes d'élasticité 1 au
    PIB, dépenses en euros inchangées) ; (iv) dette/PIB de signe opposé à Δ."""
    for cle, mesures, annee_debut in CAS_MACRO:
        delta = _deltas(mesures)[cle]
        b = _bonus_attendu([_pentes()[cle] * delta])
        premiere = (annee_debut or C.POLICY_START_YEAR) + DELAIS[cle]
        df_on, det_on, _ = _simuler(mesures, annee_debut)
        with _sans_effet_d_offre():
            df_off, det_off, _ = _simuler(mesures, annee_debut)
        for i, a in enumerate(int(x) for x in df_on['Année']):
            n = a - premiere + 1
            if n <= 0:
                assert df_on.iloc[i].equals(df_off.iloc[i]) and det_on.iloc[i].equals(det_off.iloc[i]), (cle, a)
                continue
            niveau = (1 + b) ** n - 1
            pib = det_on['PIB_Réel_Base2025'].iloc[i] / det_off['PIB_Réel_Base2025'].iloc[i] - 1
            assert pib / niveau == pytest.approx(1, abs=TOLERANCE_PREMIER_ORDRE), (cle, a, pib, niveau)
            attendu = (100 * det_off['Dépenses_Totales'].iloc[i] / df_off['PIB'].iloc[i]
                       * niveau / (1 + niveau))
            obtenu = _solde_primaire_pct(df_on, det_on, i) - _solde_primaire_pct(df_off, det_off, i)
            assert math.copysign(1, obtenu) == math.copysign(1, delta), (cle, a, obtenu)
            if abs(attendu) >= SEUIL_RAPPORT_PT:
                assert obtenu / attendu == pytest.approx(1, abs=TOLERANCE_PREMIER_ORDRE), (cle, a, obtenu, attendu)
            dette = df_on['Dette/PIB %'].iloc[i] - df_off['Dette/PIB %'].iloc[i]
            assert math.copysign(1, dette) == -math.copysign(1, delta) and dette != 0, (cle, a, dette)


def test_w6_13_solde_et_pib_signe_et_ordre_de_grandeur():
    _verifier_effet_macro_compte_une_fois()


def test_w6_13_mutation_bonus_applique_deux_fois_rougit():
    """Par mutation : le bonus d'offre ajouté deux fois au potentiel consommé
    (lecteur unique ``croissance_potentielle_totale``) double le niveau du PIB
    et l'effet sur le solde ; W6-13 rougit."""
    _verifier_effet_macro_compte_une_fois()  # témoin
    vrai = GrowthMixin.croissance_potentielle_totale

    def double(self):
        return vrai(self) + self._potential_growth_bonus

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(BudgetSimulatorV45, 'croissance_potentielle_totale', double)
        with pytest.raises(AssertionError):
            _verifier_effet_macro_compte_une_fois()


# ===========================================================================
# W6-14 — rénovation : effet de demande seul (pas d'offre)
# ===========================================================================

def _verifier_renovation_demande_seule():
    for x in (3.8, 20, 40):
        assert _bonus_apres({'transition_ecologique': {'renovation': x}}, annees=10) == 0.0, x
    bonus = _bonus_consommes({'transition_ecologique': {'renovation': 40}})
    assert all(v == 0.0 for v in bonus.values()), bonus


def test_w6_14_renovation_sans_effet_d_offre_sur_la_trajectoire():
    """ThreeME (Trésor-Éco n° 394) : effet de demande transitoire, porté par le
    multiplicateur ; lui ajouter un effet d'offre compterait deux fois le même
    euro de rénovation (plan § 6 point 1, valeur centrale livrée : 0)."""
    _verifier_renovation_demande_seule()


def test_w6_14_mutation_renovation_comptee_en_capital_rougit():
    _verifier_renovation_demande_seule()  # témoin
    table = dict(BudgetSimulatorV45.SUPPLY_EFFECTS)
    table['transition_renovation'] = {**table['transition_renovation'],
                                      'pente': _c('OFFRE_PENTE_CAPITAL_PUBLIC')}
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(BudgetSimulatorV45, 'SUPPLY_EFFECTS', table)
        with pytest.raises(AssertionError):
            _verifier_renovation_demande_seule()


# ===========================================================================
# W6-15 — porte de domaine : hors bornes, l'effet est celui de la borne
# ===========================================================================

def test_w6_15_hors_domaine_effet_de_la_borne():
    """L'offre lit la valeur après la porte tolérante (v0.6.7) : un montant hors
    du domaine du levier donne exactement l'effet de la borne, jamais un effet
    que la dépense écrêtée ne finance pas."""
    from budget_simulator.engine._param_domain import PARAM_DOMAINS
    bas_inv, haut_inv = PARAM_DOMAINS['transition_ecologique']['investissement']
    bas_rd, haut_rd = PARAM_DOMAINS['recherche_publique']['budget']
    assert _invest(haut_inv + 30) == _invest(haut_inv) != 0.0
    assert _recherche(haut_rd + 10) == _recherche(haut_rd) != 0.0
    assert _recherche(bas_rd - 5) == _recherche(bas_rd) != 0.0


# ===========================================================================
# Investissement local : même canal d'offre que l'investissement de l'État
# (revue adverse de la release E, R-2 C2)
# ===========================================================================

@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
@pytest.mark.parametrize('montant', [5, 8, 15, 20])
def test_investissement_local_meme_offre_que_l_investissement_de_l_etat(montant, annee_debut):
    """À montant égal, l'investissement des collectivités et l'investissement
    de transition de l'État produisent la MÊME offre structurelle consommée,
    chaque année (même pente, même délai, même dépréciation, même
    saturation) ; non-vacuité : l'offre est non nulle après le délai, et du
    signe du montant. (Montants dans les deux domaines : l'investissement de
    transition ne descend pas sous 0 ; la coupe de l'investissement local est
    couverte par le test suivant.)"""
    local = _bonus_consommes({'collectivites': {'investissement': montant}}, annee_debut)
    etat = _bonus_consommes({'transition_ecologique': {'investissement': montant}}, annee_debut)
    assert local.keys() == etat.keys()
    for a in local:
        assert local[a] == pytest.approx(etat[a], abs=1e-15), (a, local[a], etat[a])
    assert any(v * montant > 0 for v in local.values()), ('NON_VACUITE', local)


def test_investissement_local_et_de_l_etat_se_somment_avant_saturation():
    """Deux canaux de capital public distincts : leurs contributions linéaires
    s'ajoutent, puis la somme sature une fois (jamais un double compte)."""
    s = BudgetSimulatorV45(periods=10, mesures={'collectivites': {'investissement': 10},
                                                'transition_ecologique': {'investissement': 10}})
    for y in range(1, 8):
        s.update_potential_growth(0.01, y)
    pente = _c('OFFRE_PENTE_CAPITAL_PUBLIC')
    assert s._potential_growth_bonus == pytest.approx(_bonus_attendu([pente * 10, pente * 10]), abs=1e-15)


@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
def test_investissement_local_coupe_symetrique(annee_debut):
    """Effet SYMÉTRIQUE (règle v0.6.0 du canal) : une coupe de l'investissement
    local érode l'offre exactement à l'opposé d'une hausse du même montant."""
    hausse = _bonus_consommes({'collectivites': {'investissement': 10}}, annee_debut)
    coupe = _bonus_consommes({'collectivites': {'investissement': -10}}, annee_debut)
    for a in hausse:
        assert coupe[a] == pytest.approx(-hausse[a], abs=1e-15), a
    assert any(v < 0 for v in coupe.values()), 'NON_VACUITE'
