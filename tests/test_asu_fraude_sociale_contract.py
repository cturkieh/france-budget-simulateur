"""Contrat anti-double-comptage ASU ↔ fraude_sociale (Phase 2, option A).

HISTORIQUE : ce fichier verrouillait en Lot D le fait que l'interaction
était INERTE (cap IGAS shadow le plafond ASU) + un couplage par attribut
d'instance ``self.asu_active``/``self.asu_phasing`` (producteur
``_apply_asu`` → consommateur ``_apply_fraude_sociale``). Décision owner
prise (option A) : RENDRE L'INTERACTION EFFECTIVE. Refonte associée :

- La réduction ASU s'applique désormais APRÈS le cap IGAS (donc mord) :
  ``economies_reelles *= (1 - 0.30 * asu_phasing)``.
- Le phasing ASU vient d'une SOURCE UNIQUE
  ``handlers._phasing.asu_phasing(mesures, year)`` dérivée de l'entrée du
  run → le couplage par attribut d'instance (et sa fragilité d'ordre
  d'exécution, items type-design F1/F3) est SUPPRIMÉ. ``_apply_asu``
  n'écrit plus aucun état partagé ; l'init/reset hôte associé est retiré.

Ces tests verrouillent donc la nouvelle réalité : (a) le calendrier
``asu_phasing`` (linchpin), (b) l'interaction EFFECTIVE (ASU active →
économies fraude strictement < sans ASU), (c) l'INDÉPENDANCE À L'ORDRE
des handlers (la fragilité historique ne doit jamais revenir),
(d) restauration (ASU inactive → levier plein).
"""
import pytest

from budget_simulator.handlers._phasing import asu_phasing
from budget_simulator.simulator import BudgetSimulatorV45

_GDP, _INFLATION, _UNEMP = 3000.0, 0.02, 0.075


# --------------------------------------------------------------------------
# (a) SOURCE UNIQUE asu_phasing — calendrier + prédicat d'activation
# --------------------------------------------------------------------------

@pytest.mark.parametrize("year,expected", [
    (2025, 0.0), (2026, 0.25), (2027, 0.50), (2028, 0.75),
    (2029, 1.00), (2034, 1.00),
])
def test_asu_phasing_calendar_when_active(year, expected):
    assert asu_phasing({'asu': {'asu_activation': 1}}, year) == expected


def test_asu_phasing_zero_when_absent_or_inactive():
    assert asu_phasing({}, 2030) == 0.0
    assert asu_phasing({'asu': {'asu_activation': 0}}, 2030) == 0.0


def test_asu_phasing_predicate_matches_apply_asu_non_zero():
    """Prédicat == 0 (et NON == 1) : un toggle dévié à 0.5 (harnais
    standalone) est traité ACTIF, comme ``_apply_asu`` — garantit
    ``_apply_asu`` byte-identique (golden master standalone inchangé)."""
    assert asu_phasing({'asu': {'asu_activation': 0.5}}, 2030) == 1.00


# --------------------------------------------------------------------------
# (b) INTERACTION EFFECTIVE — ASU active réduit réellement les économies
# --------------------------------------------------------------------------

def _fraude_ds(mesures, year):
    """delta_spending de fraude_sociale pour `mesures` à `year`."""
    sim = BudgetSimulatorV45(periods=10, mesures=mesures)
    ds, _, _ = sim._apply_fraude_sociale(
        {}, mesures['fraude_sociale'], year, _GDP, _INFLATION, _UNEMP)
    return ds


@pytest.mark.parametrize("year", [2027, 2029, 2032])
def test_asu_active_strictly_reduces_fraude_savings(year):
    """ASU active → moins d'économies (delta_spending moins négatif).

    Lock anti-régression de l'inertie SUPPRIMÉE : si ce test repasse à
    « égalité », c'est que le cap IGAS shadow à nouveau la réduction
    (régression du fix option A)."""
    ds_no_asu = _fraude_ds({'fraude_sociale': {'effort': 1.0}}, year)
    ds_asu = _fraude_ds(
        {'fraude_sociale': {'effort': 1.0}, 'asu': {'asu_activation': 1}}, year)
    assert ds_asu > ds_no_asu, (
        f"Y{year}: ASU active devrait réduire les économies "
        f"(ds {ds_asu} doit être > {ds_no_asu}). Interaction redevenue "
        "inerte → régression du fix anti-double-comptage (option A)."
    )
    # Magnitude attendue : réduction = 0.30 * asu_phasing sur les économies.
    ph = asu_phasing({'asu': {'asu_activation': 1}}, year)
    eco_no = -ds_no_asu + 3.0          # ds = -economies + budget_controles (effort 1.0 → 3 Md€)
    eco_asu = -ds_asu + 3.0
    assert eco_asu == pytest.approx(eco_no * (1 - 0.30 * ph), rel=1e-9)


def test_asu_inactive_leaves_fraude_full():
    """ASU absente / inactive → aucune réduction (levier plein)."""
    base = _fraude_ds({'fraude_sociale': {'effort': 1.0}}, 2030)
    assert _fraude_ds(
        {'fraude_sociale': {'effort': 1.0}, 'asu': {'asu_activation': 0}}, 2030) == base


# --------------------------------------------------------------------------
# (c) INDÉPENDANCE À L'ORDRE DES HANDLERS — la fragilité ne doit pas revenir
# --------------------------------------------------------------------------

def test_result_independent_of_measure_key_order():
    """Même résultat que ``fraude_sociale`` soit déclaré avant OU après
    ``asu`` dans le scénario. GARDE-FOU ANTI-RÉGRESSION : la revue adverse
    a établi qu'à HEAD le couplage par attribut était déjà ordre-insensible
    (le producteur re-posait l'état + init hôte à False) ; ce test ne
    reproduit donc pas un bug régressant, il VERROUILLE durablement la
    propriété pour qu'un futur refactor ne réintroduise pas un état
    partagé sensible à l'ordre (risque réel sur l'ancienne architecture
    par attribut, désormais structurellement éliminé : le consommateur
    dérive de ``self.mesures``, pas d'un attribut posé par un
    sibling-handler)."""
    asu_p = {'asu_activation': 1, 'asu_plafonnement': 0.65}
    fs_p = {'effort': 1.0}
    fraude_first = BudgetSimulatorV45(
        periods=10, mesures={'fraude_sociale': fs_p, 'asu': asu_p}).simulate()[0]
    asu_first = BudgetSimulatorV45(
        periods=10, mesures={'asu': asu_p, 'fraude_sociale': fs_p}).simulate()[0]
    assert list(fraude_first['Dette/PIB %']) == list(asu_first['Dette/PIB %'])


# --------------------------------------------------------------------------
# (d) ÉTAT MORT SUPPRIMÉ — plus aucun attribut partagé asu_active/phasing
# --------------------------------------------------------------------------

def test_no_shared_asu_instance_state():
    """``_apply_asu`` n'écrit plus ``self.asu_active``/``self.asu_phasing``
    et l'hôte ne les initialise plus (état mort supprimé, cf Lot A
    « exil fiscal »)."""
    sim = BudgetSimulatorV45(periods=10,
                             mesures={'asu': {'asu_activation': 1}})
    sim.simulate()
    assert not hasattr(sim, 'asu_active')
    assert not hasattr(sim, 'asu_phasing')
