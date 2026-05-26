"""Tests du flag _handler_failed (Phase 0.7 du plan refactor).

Le simulateur avale les exceptions des handlers individuels en production pour ne
jamais casser le service citoyen, mais cette tolérance peut masquer des régressions
silencieuses. Le flag `_handler_failed: True` est ajouté dans le dict d'impact de
toute mesure dont le handler a raise — il est ensuite asserté à False par le golden
master (Phase 0.6) et utilisable par tout test calibration.

Voir docs/REFACTOR_SPLIT_PLAN.md § Phase 0.7.
"""
import os
from unittest.mock import patch

import pytest

from budget_simulator.constants import HANDLER_FAILED_KEY
from budget_simulator.simulator import BudgetSimulatorV45


def _assert_single_typed_failure(excinfo, measure_id, exc_type=TypeError):
    """Asserte qu'un ExceptionGroup BUDGETLAB_STRICT contient exactement UNE
    exception du type attendu, annotée de la mesure fautive.

    Le séparateur ``,`` borne le champ ``measure_id`` dans la note : sans lui,
    ``measure_id=csg`` matcherait ``measure_id=csg_bis`` (faux-vert par
    préfixe). Asserter le CONTENU — pas seulement ``raises(ExceptionGroup)`` —
    évite qu'un groupe collectant une exception sans rapport passe au vert.
    """
    inner = excinfo.value.exceptions
    assert len(inner) == 1, \
        f"Une seule mesure en échec attendue pour {measure_id} : {inner!r}"
    assert isinstance(inner[0], exc_type), \
        f"{measure_id}: exception interne attendue {exc_type.__name__}, obtenu {inner[0]!r}"
    notes = getattr(inner[0], '__notes__', [])
    assert any(f'measure_id={measure_id},' in note for note in notes), \
        f"{measure_id}: note d'identification manquante ou non bornée : {notes!r}"


def test_handler_failure_flag_set_on_error():
    """Quand un handler raise, le dict d'impact contient _handler_failed=True.

    Test du path tolérant (prod) : on neutralise explicitement BUDGETLAB_STRICT pour
    rester indépendant de l'env CI.
    """
    sim = BudgetSimulatorV45(periods=2)
    sim.mesures = {'csg': {'taux': 'not-a-number'}}  # Force un TypeError dans _apply_csg
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': ''}), \
         patch('numpy.random.normal', return_value=0):
        _, _, report = sim.simulate()

    # Year 0 (2025) est la baseline sans application des mesures (juste {'Année': 2025}).
    # On cherche csg dans la première année où il est censé apparaître.
    csg_records = [
        y_imp['csg']
        for y_imp in report['measure_impacts_by_year']
        if 'csg' in y_imp
    ]
    assert csg_records, "Mesure csg doit apparaître dans au moins une année malgré l'erreur"
    failing_record = csg_records[0]
    assert failing_record.get(HANDLER_FAILED_KEY) is True, \
        f"Flag {HANDLER_FAILED_KEY} manquant ou faux : {failing_record}"
    assert failing_record['depenses'] == 0, "delta_spending doit être 0 en erreur"
    assert failing_record['recettes'] == 0, "delta_revenue doit être 0 en erreur"


def test_no_failure_flag_when_clean():
    """Simulation baseline sans erreur : aucun _handler_failed dans aucune mesure.

    Inclut une presence assertion pour éviter un faux vert : si la simulation
    n'exerçait aucune mesure (ex: `mesures` vide ou détection cassée), itérer sur
    rien matcherait trivialement. On vérifie qu'au moins quelques mesures connues
    sont effectivement traitées.
    """
    sim = BudgetSimulatorV45(periods=3)
    # Active quelques mesures représentatives (recettes + dépenses + macro)
    sim.mesures = {
        'tva_rate': {'taux': 0.21},
        'retraites': {'age_depart': 64.0},
        'education': {'budget': 70},
    }
    with patch('numpy.random.normal', return_value=0):
        _, _, report = sim.simulate()

    measures_seen = set()
    for year_impacts in report['measure_impacts_by_year']:
        for measure_id, data in year_impacts.items():
            if measure_id == 'Année' or not isinstance(data, dict):
                continue
            measures_seen.add(measure_id)
            assert not data.get(HANDLER_FAILED_KEY), \
                f"Mesure {measure_id} a échoué silencieusement : {data}"
    # Anti-faux-vert : au moins les 3 mesures activées doivent avoir tourné.
    expected = {'tva_rate', 'retraites', 'education'}
    assert expected.issubset(measures_seen), \
        f"Mesures activées non traitées : manquantes={expected - measures_seen}"


def test_strict_mode_raises_on_handler_error():
    """En mode BUDGETLAB_STRICT=1, une erreur handler escalade au lieu d'être avalée.

    Garde-fou pour CI / golden master : empêche une régression de passer en silence
    parce que la mesure était à default (delta=0 attendu, 0 obtenu malgré crash).
    L'escalade est un ``ExceptionGroup`` : la boucle collecte toutes les mesures
    en échec d'une même année puis lève une fois (pas de fail-fast sur la
    première qui masquerait les suivantes). Voir docs/REFACTOR_SPLIT_PLAN.md
    Lot C Item 3.
    """
    sim = BudgetSimulatorV45(periods=2)
    sim.mesures = {'csg': {'taux': 'not-a-number'}}  # 'str' - float → TypeError
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1'}), \
         patch('numpy.random.normal', return_value=0), \
         pytest.raises(ExceptionGroup) as excinfo:
        sim.simulate()
    _assert_single_typed_failure(excinfo, 'csg')


def test_strict_mode_collects_all_failures_without_prefix_collision():
    """Cœur d'Item 3 : le mode strict collecte TOUTES les mesures en échec
    d'une année (pas de fail-fast sur la première) et chaque exception est
    annotée SANS collision de préfixe.

    Paire réelle où un measure_id est préfixe de l'autre :
    ``fonction_publique`` ⊂ ``fonction_publique_reforme``. Ce test met sous
    tension deux invariants qu'aucun test mono-mesure n'exerce :

    1. **Collecte exhaustive** : 2 mesures fautives → 2 exceptions dans le
       groupe (un fail-fast n'en remonterait qu'une).
    2. **Borne de note** : la note ``measure_id=fonction_publique,`` ne doit
       matcher QU'UNE exception. Sans le séparateur ``,`` la sous-chaîne
       ``measure_id=fonction_publique`` matcherait aussi
       ``measure_id=fonction_publique_reforme,`` → le compte passerait à 2
       (régression détectée).
    """
    sim = BudgetSimulatorV45(periods=2)
    sim.mesures = {
        'fonction_publique': {'effectifs': 'not-a-number'},
        'fonction_publique_reforme': {'fusion_agences': 'not-a-number'},
    }
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1'}), \
         patch('numpy.random.normal', return_value=0), \
         pytest.raises(ExceptionGroup) as excinfo:
        sim.simulate()

    inner = excinfo.value.exceptions
    assert len(inner) == 2, \
        f"Les 2 mesures fautives doivent être collectées (pas de fail-fast) : {inner!r}"
    assert all(isinstance(exc, TypeError) for exc in inner), \
        f"Toutes les exceptions internes attendues TypeError : {inner!r}"
    all_notes = [note for exc in inner for note in getattr(exc, '__notes__', [])]
    # Borne ',' load-bearing : exactement 1 match pour le préfixe court
    # (vaudrait 2 si la borne sautait → faux-vert par préfixe).
    assert sum('measure_id=fonction_publique,' in n for n in all_notes) == 1, \
        f"Le préfixe court doit matcher exactement 1 note (borne ',') : {all_notes!r}"
    assert sum('measure_id=fonction_publique_reforme,' in n for n in all_notes) == 1, \
        f"La mesure longue doit matcher exactement 1 note : {all_notes!r}"


# Couverture du flag _handler_failed pour les handlers de mesure, tous
# déplacés en mixin (Phases 1.1 → 1.7 — Phase 1 COMPLÈTE, 7/7 sections).
# simulator.py ne contient plus aucun handler thématique : seul subsiste
# `_apply_complex_measure` (Section 7 legacy — dispatch handler Python,
# non concerné par cette liste).
# Convention : la valeur 'not-a-number' produit un TypeError au premier
# opérateur arithmétique. Si un handler ajoute une garde précoce qui retourne {}
# sur input invalide, ces tests deviennent un faux-vert silencieux — mettre à
# jour les bad_params en conséquence.
MIXIN_BAD_PARAMS = [
    ('smic', {'montant_brut': 'not-a-number'}),
    ('taxe_superprofits', {'intensite': 'not-a-number'}),
    ('exonerations_salaires', {'intensite': 'not-a-number'}),
    ('rabot_uniforme', {'taux_reduction': 'not-a-number'}),
    ('education', {'budget': 'not-a-number'}),
    ('transition_ecologique', {'investissement': 'not-a-number'}),
    ('recherche_publique', {'budget': 'not-a-number'}),
    # Section 4 — fiscalité ménages (Phase 1.4, handlers/fiscalite_menages.py)
    ('tva_rate', {'taux': 'not-a-number'}),
    ('tva_energie', {'taux': 'not-a-number'}),
    ('impot_revenu', {'taux_superieur': 'not-a-number'}),
    ('csg', {'taux': 'not-a-number'}),
    ('cotisations_salariales', {'baisse_points': 'not-a-number'}),
    ('elargissement_ir', {'taux_contribuables_cible': 'not-a-number'}),
    ('fiscalite_patrimoine', {'intensite': 'not-a-number'}),
    ('isf_climatique', {'intensite': 'not-a-number'}),
    # Section 3 — compétitivité entreprises (Phase 1.5, handlers/competitivite.py)
    ('niches_fiscales_tge', {'montant': 'not-a-number'}),
    ('niches_sociales_tge', {'montant': 'not-a-number'}),
    ('subventions_tge', {'montant': 'not-a-number'}),
    ('cotisations_patronales', {'taux': 'not-a-number'}),
    ('impot_societes', {'taux': 'not-a-number'}),
    ('impots_production', {'montant': 'not-a-number'}),
    ('is_exceptionnel_tge', {'montant': 'not-a-number'}),
    # Section 2 — maîtrise des dépenses (Phase 1.6, handlers/depenses.py)
    # Clé choisie = première opération typée sur le paramètre (opérateur
    # arithmétique OU comparaison) qui lève un TypeError sur une str. Ex :
    # 'duree' (chomage_alloc) raise au comparateur `if duree <= 0:`, pas en
    # arithmétique — c'est l'usage typé, pas l'opérateur, qui compte.
    # 'asu_plafonnement' : le clamp max(0.5, min(0.7, plafonnement)) raise
    # AVANT la garde `if activation == 0: return {}` (clamp-avant-garde, ici
    # en notre faveur — la valeur invalide ne peut pas être silencieusement
    # neutralisée par l'early-return).
    ('retraites', {'age_depart': 'not-a-number'}),
    ('sante', {'effort_hopital': 'not-a-number'}),
    ('chomage_alloc', {'duree': 'not-a-number'}),
    ('asu', {'asu_plafonnement': 'not-a-number'}),
    ('prestations_indexation', {'taux_indexation': 'not-a-number'}),
    # 'abattement_retraites' VOLONTAIREMENT EXCLU : son unique paramètre
    # `reforme_active` n'est utilisé qu'en comparaison `== 1`, jamais en
    # arithmétique. Une valeur invalide ne raise pas — elle retombe
    # silencieusement sur la branche inactive (delta_revenue=0). La
    # convention 'not-a-number' → TypeError ne s'applique donc pas ; ajouter
    # une entrée serait un faux-vert. Couvert par le golden master standalone
    # (Phase 0.8) qui exerce le handler avec une valeur valide.
    # Section 1 — efficience et organisation (Phase 1.7, handlers/efficience.py)
    # DERNIÈRE section splittée — Phase 1 complète (7/7). Les 5 handlers sont
    # tous couvrables (aucune exclusion type abattement_retraites) : 'effort'
    # (fraude_*) raise au comparateur `if effort_raw <= 1.0:` ; 'fusion_agences'
    # (fonction_publique_reforme) en arithmétique `/ 10` ; 'effectifs'
    # (fonction_publique) en `* cout_moyen_agent` après la garde
    # `== 0 and == 0` (non déclenchée par une str) ; 'intensite'
    # (optimisation_dette) en `-economie_max * intensite` après la garde
    # `if intensite == 0` (non déclenchée par une str) et dans la fenêtre
    # year_idx ∈ [1,5] couverte par simulate(periods=2).
    ('fraude_fiscale', {'effort': 'not-a-number'}),
    ('fraude_sociale', {'effort': 'not-a-number'}),
    ('fonction_publique_reforme', {'fusion_agences': 'not-a-number'}),
    ('fonction_publique', {'effectifs': 'not-a-number'}),
    ('optimisation_dette', {'intensite': 'not-a-number'}),
]


@pytest.mark.parametrize('measure_id,bad_params', MIXIN_BAD_PARAMS)
def test_mixin_handler_failure_flag_set_on_error(measure_id, bad_params):
    """Mode tolérant : un handler du mixin qui raise reçoit _handler_failed=True."""
    sim = BudgetSimulatorV45(periods=2)
    sim.mesures = {measure_id: bad_params}
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': ''}), \
         patch('numpy.random.normal', return_value=0):
        _, _, report = sim.simulate()

    records = [
        y_imp[measure_id]
        for y_imp in report['measure_impacts_by_year']
        if measure_id in y_imp
    ]
    assert records, f"Mesure {measure_id} doit apparaître malgré l'erreur"
    failing_record = records[0]
    assert failing_record.get(HANDLER_FAILED_KEY) is True, \
        f"Flag {HANDLER_FAILED_KEY} manquant ou faux pour {measure_id} : {failing_record}"
    assert failing_record['depenses'] == 0, "delta_spending doit être 0 en erreur"
    assert failing_record['recettes'] == 0, "delta_revenue doit être 0 en erreur"


@pytest.mark.parametrize('measure_id,bad_params', MIXIN_BAD_PARAMS)
def test_mixin_handler_strict_mode_raises(measure_id, bad_params):
    """Mode strict : un handler du mixin qui raise escalade en ExceptionGroup.

    Anti-faux-vert : on asserte que le groupe contient bien UN TypeError annoté
    de la mesure en échec — un ``raises(ExceptionGroup)`` nu passerait même si le
    groupe collectait une exception sans rapport.
    """
    sim = BudgetSimulatorV45(periods=2)
    sim.mesures = {measure_id: bad_params}
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1'}), \
         patch('numpy.random.normal', return_value=0), \
         pytest.raises(ExceptionGroup) as excinfo:
        sim.simulate()
    _assert_single_typed_failure(excinfo, measure_id)
