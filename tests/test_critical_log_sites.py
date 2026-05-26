"""Couverture caplog des sites de log critiques du moteur (Lot E, Phase 2).

Une régression silencieuse qui supprimerait l'un de ces ``logger.warning`` /
``logger.error`` (clip de plafond, échec handler) passerait aujourd'hui
totalement inaperçue (golden master = chiffres, pas logs). Ces tests
verrouillent l'OBSERVABILITÉ de chaque clip/échec.

Sites couverts (cf REFACTOR_SPLIT_PLAN.md, Backlog Phase 2) :
- (a) ``taxe_superprofits`` recettes plafonnées à 20 Md€ — handlers.additionnels
- (b) ``exonerations_salaires`` coût plafonné à 15 Md€ — handlers.additionnels
- (c) clip individuel 5 % PIB par mesure — engine.orchestrator
- (d) clip total 10 % PIB (warning AJOUTÉ en Lot E : le site n'émettait
      qu'un ``_log_debug`` invisible hors BUDGET_DEBUG) — engine.orchestrator
- (e) échec handler absorbé en mode tolérant — engine.orchestrator

Les sites (c)/(d)/(e) sont inatteignables via les handlers calibrés réels
(plafonds internes en amont) : on injecte des handlers factices via
``monkeypatch`` sur ``measure_handlers`` (le dispatch
``_apply_complex_measure`` les appelle sans liaison ``self``).
"""
import logging

from budget_simulator.simulator import BudgetSimulatorV45

_ADDITIONNELS_LOGGER = 'budget_simulator.handlers.additionnels'
_ORCHESTRATOR_LOGGER = 'budget_simulator.engine.orchestrator'


def _messages(caplog, logger_name, level):
    return [r.getMessage() for r in caplog.records
            if r.name == logger_name and r.levelno == level]


# --------------------------------------------------------------------------
# (a) / (b) — plafonds handlers (appel direct, expressions pures)
# --------------------------------------------------------------------------

def test_taxe_superprofits_cap_20_emits_warning(default_simulator, caplog):
    """Recettes brutes > 20 Md€ (legacy taux 0.40, tous secteurs) → warning."""
    with caplog.at_level(logging.WARNING, logger=_ADDITIONNELS_LOGGER):
        default_simulator._apply_taxe_superprofits(
            {}, {'taux': 0.40, 'seuil_hausse': 1.20, 'tous_secteurs': True},
            2026, 3000.0, 0.02, 0.075,
        )
    msgs = _messages(caplog, _ADDITIONNELS_LOGGER, logging.WARNING)
    assert any('taxe_superprofits' in m and 'plafonnées à 20.0 Md€' in m for m in msgs), msgs


def test_exonerations_cap_15_emits_warning(default_simulator, caplog):
    """Coût brut > 15 Md€ (intensité 1.0, inflation 4 %) → warning."""
    with caplog.at_level(logging.WARNING, logger=_ADDITIONNELS_LOGGER):
        default_simulator._apply_exonerations_salaires(
            {}, {'intensite': 1.0}, 2030, 3000.0, 0.04, 0.075,
        )
    msgs = _messages(caplog, _ADDITIONNELS_LOGGER, logging.WARNING)
    assert any('exonerations_salaires' in m and 'plafonné à 15.0 Md€' in m for m in msgs), msgs


# --------------------------------------------------------------------------
# (c) / (d) / (e) — orchestrateur (handlers factices injectés)
# --------------------------------------------------------------------------

def _huge(measure, params, year, gdp, inflation, unemployment):
    """Handler factice : impact volontairement > 5 % PIB (déclenche le clip)."""
    return 1.0e9, 1.0e9, {'depenses': 1.0e9, 'recettes': 1.0e9}


def _boom(measure, params, year, gdp, inflation, unemployment):
    """Handler factice : crash systématique (déclenche le chemin tolérant)."""
    raise RuntimeError("boom-test injecté (Lot E)")


def test_clip_5pct_pib_per_measure_emits_warning(monkeypatch, caplog):
    """Une mesure dépassant 5 % PIB → warning CLIP 5% PIB de l'orchestrateur."""
    sim = BudgetSimulatorV45(periods=10, mesures={'fraude_fiscale': {'effort': 1.0}})
    monkeypatch.setitem(sim.measure_handlers, 'fraude_fiscale', _huge)
    with caplog.at_level(logging.WARNING, logger=_ORCHESTRATOR_LOGGER):
        sim.simulate()
    msgs = _messages(caplog, _ORCHESTRATOR_LOGGER, logging.WARNING)
    assert any('CLIP 5% PIB' in m and 'fraude_fiscale' in m for m in msgs), msgs


def test_clip_10pct_pib_total_emits_warning(monkeypatch, caplog):
    """Total > 10 % PIB (3 mesures énormes) → warning CLIP 10% PIB TOTAL.

    Ce warning a été AJOUTÉ en Lot E (le site n'émettait qu'un
    ``_log_debug`` invisible hors BUDGET_DEBUG — angle mort d'observabilité).
    """
    ids = ['fraude_fiscale', 'fraude_sociale', 'optimisation_dette']
    sim = BudgetSimulatorV45(periods=10, mesures={i: {} for i in ids})
    for i in ids:
        monkeypatch.setitem(sim.measure_handlers, i, _huge)
    with caplog.at_level(logging.WARNING, logger=_ORCHESTRATOR_LOGGER):
        sim.simulate()
    msgs = _messages(caplog, _ORCHESTRATOR_LOGGER, logging.WARNING)
    assert any('CLIP 10% PIB TOTAL' in m for m in msgs), msgs


def test_handler_failure_absorbed_emits_error(monkeypatch, caplog):
    """Handler qui crash (mode tolérant) → logger.error + flag HANDLER_FAILED.

    ``BUDGETLAB_STRICT`` est retiré localement : ce test cible
    explicitement le chemin TOLÉRANT (prod / service citoyen), pas le
    fail-fast CI — indépendamment du mode d'exécution de la suite.
    """
    monkeypatch.delenv('BUDGETLAB_STRICT', raising=False)
    from budget_simulator.constants import HANDLER_FAILED_KEY

    sim = BudgetSimulatorV45(periods=10, mesures={'fraude_fiscale': {'effort': 1.0}})
    monkeypatch.setitem(sim.measure_handlers, 'fraude_fiscale', _boom)
    with caplog.at_level(logging.ERROR, logger=_ORCHESTRATOR_LOGGER):
        _, _, report = sim.simulate()

    errors = _messages(caplog, _ORCHESTRATOR_LOGGER, logging.ERROR)
    assert any('fraude_fiscale' in m and 'échouée' in m for m in errors), errors

    flagged = any(
        isinstance(data, dict) and data.get(HANDLER_FAILED_KEY)
        for year_block in report['measure_impacts_by_year']
        for mid, data in year_block.items()
        if mid != 'Année'
    )
    assert flagged, "HANDLER_FAILED_KEY non posé malgré le crash absorbé"
