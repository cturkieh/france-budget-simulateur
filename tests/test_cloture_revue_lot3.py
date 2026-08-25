"""Clôture de la revue intermédiaire du lot 3 (canal emploi seniors, v0.6.1).

Le lot 3 a été commité avant que sa revue n'ait rendu son rapport : les cinq
constats ci-dessous n'avaient jamais été appliqués. Ce fichier les verrouille,
un bloc par constat.

(a) ANCRAGE DU PHASING — RACINE. Les deux profils macro (``PHASING_OFFRE_
    SENIORS``, ``PHASING_CHOMAGE_SENIORS``) étaient indexés sur
    ``year - POLICY_START_YEAR``, c'est-à-dire sur le début de la SIMULATION.
    Or l'écart au droit en vigueur d'un programme ne s'ouvre pas forcément en
    2026 : depuis l'item I3, la référence légale monte de 62,75 ans (2026-2027)
    à 64,0 ans (2032), donc un programme qui pose l'âge à 62,75 a un écart
    RIGOUREUSEMENT NUL en 2026-2027 et ne diverge qu'à partir de 2028. Le
    profil de résorption du chômage était alors lu à son index 2 dès la
    première année de choc — la bosse s'appliquait déjà en phase de
    résorption — et le niveau de PIB apparaissait presque formé.

(d) SANITISATION vs CLAMP. Le canal budgétaire reçoit un paramètre qui a
    traversé ``validate_param_domains`` (mode tolérant : NaN et booléens sont
    clampés à la borne BASSE du domaine, 60 ans). Les canaux macro, eux,
    dégradaient ces mêmes valeurs à un écart NUL. Le moteur chiffrait donc une
    réforme de −2,75 à −4 ans côté dépenses pendant que l'offre de travail et
    le chômage restaient neutres.

(e) PAYLOAD NON-DICT. ``mesures['retraites']`` non-dict levait une
    ``AttributeError`` en tête de boucle d'année, hors du ``try`` per-mesure
    qui trace (``logger.error`` + ``HANDLER_FAILED_KEY``).

(f) CLIP ET RÉTRACTION. ``_chomage_seniors_prev`` était écrit AVANT le clip
    [4 % ; 12 %] : si le clip mordait, l'année suivante rétractait une bosse
    qui n'avait jamais été intégralement appliquée.

Convention : aucun littéral de calibration ici — les attendus sont construits
à partir des constantes nommées, pour qu'un recalibrage des tables déplace le
test avec le code.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from budget_simulator._seniors import (  # noqa: E402
    chomage_seniors_ecart,
    offre_seniors_niveau_pib,
    retraites_annee_debut_ecart_age,
    retraites_ecart_age_ans,
    retraites_ecart_age_ans_moteur,
)
from budget_simulator.constants import (  # noqa: E402
    CHOMAGE_CLIP_MAX,
    CHOMAGE_CLIP_MIN,
    CHOMAGE_SENIORS_PIC,
    OFFRE_SENIORS_PIB_NIVEAU_LT,
    PARAM_DOMAINS,
    PHASING_CHOMAGE_SENIORS,
    PHASING_OFFRE_SENIORS,
    POLICY_START_YEAR,
    retraites_ref_age_ans,
)
from budget_simulator.engine._param_domain import validate_param_domains  # noqa: E402
from budget_simulator.handlers._phasing import _year_phasing  # noqa: E402
from budget_simulator.simulator import BudgetSimulatorV45  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'snapshots'))
from run_scenarios_full import SCENARIOS  # noqa: E402

# Âge du gel légal : un programme qui le pose décrit « je suspends la réforme »,
# son écart au droit en vigueur est nul jusqu'à la fin du gel puis s'ouvre.
AGE_GEL = retraites_ref_age_ans(POLICY_START_YEAR)
PREMIERE_ANNEE_ECART = POLICY_START_YEAR + 2  # 2028 : première année post-gel
HORIZON = range(POLICY_START_YEAR, POLICY_START_YEAR + 10)


def _mesures(age):
    return {'retraites': {'age_depart': age}}


# ==========================================================================
# (a) — ancrage du phasing sur le DÉBUT DE L'ÉCART, pas sur le début du run
# ==========================================================================

def test_annee_debut_ecart_suit_le_calendrier_legal():
    """Un programme calé sur le gel n'ouvre son écart qu'à la fin du gel."""
    assert retraites_annee_debut_ecart_age(_mesures(AGE_GEL)) == PREMIERE_ANNEE_ECART


def test_annee_debut_ecart_vaut_le_depart_pour_un_programme_immediat():
    """Un programme qui dévie dès la première année garde l'ancrage actuel —
    c'est le cas de huit des neuf scénarios publiés (non-régression)."""
    for age in (60.0, 61.5, 62.0, 64.0, 65.0, 67.0):
        assert retraites_annee_debut_ecart_age(_mesures(age)) == POLICY_START_YEAR


def test_annee_debut_ecart_sans_curseur_retombe_sur_l_annee_de_depart():
    """Écart identiquement nul (pas de curseur d'âge) : l'ancrage n'a aucun
    effet observable, la fonction doit rendre le défaut sans lever ni boucler."""
    assert retraites_annee_debut_ecart_age({}) == POLICY_START_YEAR
    assert retraites_annee_debut_ecart_age({'retraites': {}}) == POLICY_START_YEAR
    assert retraites_annee_debut_ecart_age(
        {'retraites': {'indexation': 0.9}}) == POLICY_START_YEAR


@pytest.mark.parametrize('annee', list(range(POLICY_START_YEAR + 2,
                                             POLICY_START_YEAR + 10)))
def test_phasing_offre_ancre_sur_le_debut_de_l_ecart(annee):
    mesures = _mesures(AGE_GEL)
    attendu = (OFFRE_SENIORS_PIB_NIVEAU_LT
               * _year_phasing(annee - PREMIERE_ANNEE_ECART, PHASING_OFFRE_SENIORS)
               * retraites_ecart_age_ans_moteur(mesures, annee))
    assert offre_seniors_niveau_pib(mesures, annee) == pytest.approx(attendu, abs=1e-15)


@pytest.mark.parametrize('annee', list(range(POLICY_START_YEAR + 2,
                                             POLICY_START_YEAR + 10)))
def test_phasing_chomage_ancre_sur_le_debut_de_l_ecart(annee):
    mesures = _mesures(AGE_GEL)
    attendu = (CHOMAGE_SENIORS_PIC
               * _year_phasing(annee - PREMIERE_ANNEE_ECART, PHASING_CHOMAGE_SENIORS)
               * retraites_ecart_age_ans_moteur(mesures, annee))
    assert chomage_seniors_ecart(mesures, annee) == pytest.approx(attendu, abs=1e-18)


def test_la_bosse_de_chomage_ne_demarre_plus_en_phase_de_resorption():
    """LE DÉFAUT, dit dans les termes du phénomène : le profil de résorption
    monte vers son pic puis redescend. Sur les premières années de l'écart, le
    coefficient lu doit donc être CROISSANT. Il était décroissant dès la
    troisième année de choc — la bosse démarrait déjà résorbée."""
    mesures = _mesures(AGE_GEL)
    annees = range(PREMIERE_ANNEE_ECART, PREMIERE_ANNEE_ECART + 5)
    coeffs = [chomage_seniors_ecart(mesures, y) / retraites_ecart_age_ans_moteur(mesures, y)
              for y in annees]
    assert all(b > a for a, b in zip(coeffs, coeffs[1:])), coeffs


def test_le_niveau_de_pib_ne_saute_plus_presque_forme():
    """Contre-épreuve d'amplitude : la première année d'écart doit porter le
    PREMIER coefficient d'absorption, pas un coefficient de mi-parcours."""
    mesures = _mesures(AGE_GEL)
    annee = PREMIERE_ANNEE_ECART
    part = (offre_seniors_niveau_pib(mesures, annee)
            / (OFFRE_SENIORS_PIB_NIVEAU_LT * retraites_ecart_age_ans_moteur(mesures, annee)))
    assert part == pytest.approx(PHASING_OFFRE_SENIORS[0], abs=1e-15)


@pytest.mark.parametrize('age', [60.0, 65.0])
@pytest.mark.parametrize('decalage', list(range(10)))
def test_programme_immediat_bit_identique(age, decalage):
    """Non-régression : pour les programmes dont l'écart s'ouvre en première
    année, l'ancrage vaut POLICY_START_YEAR — l'indexation est inchangée."""
    mesures = _mesures(age)
    annee = POLICY_START_YEAR + decalage
    ecart = retraites_ecart_age_ans_moteur(mesures, annee)
    assert offre_seniors_niveau_pib(mesures, annee) == pytest.approx(
        OFFRE_SENIORS_PIB_NIVEAU_LT * _year_phasing(decalage, PHASING_OFFRE_SENIORS) * ecart,
        abs=1e-15)
    assert chomage_seniors_ecart(mesures, annee) == pytest.approx(
        CHOMAGE_SENIORS_PIC * _year_phasing(decalage, PHASING_CHOMAGE_SENIORS) * ecart,
        abs=1e-18)


def test_les_deux_canaux_partagent_le_meme_ancrage():
    """Source unique : offre et chômage ne peuvent pas diverger d'un an."""
    for age in (AGE_GEL, 60.0, 64.0, 65.0):
        mesures = _mesures(age)
        debut = retraites_annee_debut_ecart_age(mesures)
        for annee in HORIZON:
            ecart = retraites_ecart_age_ans_moteur(mesures, annee)
            if ecart == 0:
                continue
            idx_offre = (offre_seniors_niveau_pib(mesures, annee)
                         / (OFFRE_SENIORS_PIB_NIVEAU_LT * ecart))
            idx_chom = chomage_seniors_ecart(mesures, annee) / (CHOMAGE_SENIORS_PIC * ecart)
            attendu = annee - debut
            assert idx_offre == pytest.approx(
                _year_phasing(attendu, PHASING_OFFRE_SENIORS), abs=1e-15)
            assert idx_chom == pytest.approx(
                _year_phasing(attendu, PHASING_CHOMAGE_SENIORS), abs=1e-15)


# ==========================================================================
# (d) — la sanitisation des canaux macro suit le clamp de domaine
# ==========================================================================

@pytest.mark.parametrize('valeur', [float('nan'), True, False])
@pytest.mark.parametrize('annee', [POLICY_START_YEAR, POLICY_START_YEAR + 6])
def test_canaux_macro_et_canal_budgetaire_voient_le_meme_ecart(valeur, annee):
    """Contre-épreuve COMPORTEMENTALE, pas un grep : on fait passer la valeur
    par la porte unique (mode tolérant) comme le fait l'orchestrateur, et on
    compare ce que price le handler à ce que voient les canaux macro."""
    brut = {'age_depart': valeur}
    borne = validate_param_domains('retraites', brut, strict=False)
    attendu = retraites_ecart_age_ans(borne, annee)
    obtenu = retraites_ecart_age_ans_moteur({'retraites': brut}, annee)
    assert obtenu == pytest.approx(attendu), (
        f"canal budgetaire {attendu:+.3f} an vs canaux macro {obtenu:+.3f} an")


def test_nan_produit_la_meme_trajectoire_qu_un_age_pose_a_la_borne_basse():
    """Bout-en-bout : le clamp tolérant amène l'âge à la borne basse du
    domaine. Toute la simulation — dette ET chômage — doit alors décrire
    exactement ce programme-là, pas un programme hybride."""
    borne_basse = PARAM_DOMAINS['retraites']['age_depart'][0]
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': ''}):
        nan_df, _, _ = BudgetSimulatorV45(
            periods=10, mesures=_mesures(float('nan'))).simulate()
        ref_df, _, _ = BudgetSimulatorV45(
            periods=10, mesures=_mesures(borne_basse)).simulate()
    assert nan_df['Dette/PIB %'].iloc[10] == pytest.approx(ref_df['Dette/PIB %'].iloc[10])
    assert nan_df['Chômage %'].iloc[10] == pytest.approx(ref_df['Chômage %'].iloc[10])
    assert nan_df['PIB'].iloc[10] == pytest.approx(ref_df['PIB'].iloc[10])


def test_une_valeur_non_numerique_reste_neutre_cote_moteur():
    """Contrat MIXIN_BAD_PARAMS préservé : une ``str`` doit lever DANS le
    handler (seul endroit tracé). Y lever depuis les canaux macro, évalués en
    amont de la boucle des mesures, court-circuiterait la porte unique — on
    dégrade donc à neutre, sans rien avaler (le handler alerte la même année)."""
    assert retraites_ecart_age_ans_moteur(_mesures('soixante'), 2030) == 0.0
    assert retraites_ecart_age_ans_moteur(_mesures(None), 2030) == 0.0


def test_une_valeur_hors_domaine_reste_bornee_comme_la_porte_unique():
    """Non-régression du bornage introduit au lot 3."""
    basse, haute = PARAM_DOMAINS['retraites']['age_depart']
    annee = POLICY_START_YEAR + 6
    ref = retraites_ref_age_ans(annee)
    assert retraites_ecart_age_ans_moteur(_mesures(haute + 10), annee) == pytest.approx(haute - ref)
    assert retraites_ecart_age_ans_moteur(_mesures(basse - 10), annee) == pytest.approx(basse - ref)


# ==========================================================================
# (e) — un payload `retraites` non-dict ne casse plus les canaux macro
# ==========================================================================

@pytest.mark.parametrize('charge', [[62.75], 'retraites', 42, (62.75,), 3.5])
def test_payload_retraites_non_dict_laisse_les_canaux_macro_neutres(charge):
    mesures = {'retraites': charge}
    assert retraites_ecart_age_ans_moteur(mesures, 2030) == 0.0
    assert offre_seniors_niveau_pib(mesures, 2030) == 0.0
    assert chomage_seniors_ecart(mesures, 2030) == 0.0
    assert retraites_annee_debut_ecart_age(mesures) == POLICY_START_YEAR


def test_payload_non_dict_passe_par_le_chemin_trace(caplog):
    """Zéro échec silencieux : l'anomalie doit ressortir par la porte unique
    (``logger.error`` + ``HANDLER_FAILED_KEY``), pas par une AttributeError
    non tracée levée en tête de boucle d'année."""
    sim = BudgetSimulatorV45(periods=3, mesures={'retraites': [62.75]})
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': ''}), caplog.at_level('ERROR'):
        df, _, _ = sim.simulate()
    assert df['Dette/PIB %'].notna().all(), "trajectoire NaN = échec silencieux"
    assert any(rec.levelname == 'ERROR' for rec in caplog.records), \
        "un payload illisible doit laisser une trace filtrable"


# ==========================================================================
# (f) — le clip du chômage et la rétraction de la bosse
# ==========================================================================

def _appel(sim, mesures, u_prev, growth, year_idx):
    """Un appel isolé de ``calculate_unemployment``, état de bosse remis à zéro."""
    sim.mesures = mesures
    sim._chomage_seniors_prev = 0.0
    return sim.calculate_unemployment(growth, u_prev, year_idx, None)


def test_la_bosse_retractee_est_celle_reellement_appliquee_quand_le_clip_mord():
    """Si le clip [4 % ; 12 %] mord, l'année suivante doit rétracter la part
    RÉELLEMENT entrée dans le taux publié — sinon elle retire une bosse qui
    n'a jamais été appliquée et fait dériver la série vers le bas."""
    sim = BudgetSimulatorV45(periods=10, mesures={})
    haute = PARAM_DOMAINS['retraites']['age_depart'][1]
    annee_idx = 5
    croissance = sim.base_params['croissance_potentielle']
    u_prev = CHOMAGE_CLIP_MAX - 0.0001  # trajectoire déjà collée au plafond

    u_avec = _appel(sim, _mesures(haute), u_prev, croissance, annee_idx)
    retractee = sim._chomage_seniors_prev
    u_sans = _appel(sim, {}, u_prev, croissance, annee_idx)

    assert u_avec == pytest.approx(CHOMAGE_CLIP_MAX), "le clip doit mordre, sinon le test est vide"
    assert u_avec - retractee == pytest.approx(u_sans, abs=1e-15)


def test_la_bosse_retractee_vaut_la_table_quand_le_clip_ne_mord_pas():
    """Non-régression : hors bout de course, la rétraction reste exactement
    la table — la correction est neutre sur tout état atteignable."""
    sim = BudgetSimulatorV45(periods=10, mesures={})
    annee_idx = 5
    mesures = _mesures(65.0)
    _appel(sim, mesures, sim.base_params['chomage_nairu'],
           sim.base_params['croissance_potentielle'], annee_idx)
    attendu = chomage_seniors_ecart(mesures, sim.annee_base + annee_idx)
    assert sim._chomage_seniors_prev == pytest.approx(attendu, abs=1e-18)
    assert attendu != 0.0


@pytest.mark.skipif(not SCENARIOS, reason="scenarios.json absent (fork moteur seul)")
def test_le_clip_du_chomage_reste_inatteignable_sur_les_scenarios_publies():
    """Mesure, et non hypothèse : la correction ci-dessus est bit-identique sur
    le produit livré tant que la trajectoire reste à l'intérieur du clip. Ce
    test le VÉRIFIE scénario par scénario au lieu de l'affirmer."""
    marges = {}
    for nom, mesures in SCENARIOS.items():
        df, _, _ = BudgetSimulatorV45(periods=10, mesures=mesures).simulate()
        taux = df['Chômage %'] / 100.0
        marges[nom] = (taux.min() - CHOMAGE_CLIP_MIN, CHOMAGE_CLIP_MAX - taux.max())
    for nom, (marge_bas, marge_haut) in marges.items():
        assert marge_bas > 0.0 and marge_haut > 0.0, f"{nom} : clip atteint {marges[nom]}"
