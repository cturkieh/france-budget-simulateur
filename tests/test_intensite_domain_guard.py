"""Lot C Item 1 — Garde-fou de domaine des paramètres d'intensité.

Le slider frontend borne déjà l'utilisateur ; ce garde-fou protège les
entrées HORS-UI (scénarios, API, config) qui n'ont aucun clamp backend
(`optimisation_dette`, `isf_climatique`, `taxe_superprofits`,
`exonerations_salaires`, `fiscalite_patrimoine`). Voir
docs/MINI_DESIGN_ITEM1_BORNE_INTENSITE.md.

Deux niveaux :
- fonction pure `validate_intensite_domain` (logique isolée, porte unique) ;
- intégration via le simulateur, qui prouve le branchement orchestrateur
  ET la synergie avec Lot C Item 3 (ValueError → ExceptionGroup STRICT).

Contrainte MIXIN_BAD_PARAMS (mini-design §3.3, cf.
test_handler_failure_flag) : une `str` doit TOUJOURS lever TypeError
(jamais ValueError silencieux ni early-return {}) — sinon les 32
MIXIN_BAD_PARAMS deviennent un faux-vert. Le test
`test_str_intensite_*` est load-bearing : il prouve que l'ordre des
comparaisons ne masque pas le TypeError naturel.
"""
import os
from unittest.mock import patch

import pytest

from budget_simulator.constants import HANDLER_FAILED_KEY, INTENSITE_DOMAINS
from budget_simulator.engine._param_domain import validate_intensite_domain
from budget_simulator.simulator import BudgetSimulatorV45


# --------------------------------------------------------------------------
# Fonction pure (logique du garde-fou, testable d'un seul point — Option A)
# --------------------------------------------------------------------------

def test_noop_for_measure_not_in_registry():
    """Mesure hors registre : params rendus tels quels (objet identique)."""
    params = {'intensite': 999.0}
    out = validate_intensite_domain('mesure_inconnue', params, strict=True)
    assert out is params  # aucune copie, aucun raise, aucun clamp


def test_noop_when_intensite_absent_preserves_legacy_path():
    """`intensite` absent → params inchangés (préserve la branche legacy de
    _resolve_intensite_or_legacy : taxe_superprofits/exonerations_salaires
    en mode legacy n'ont pas de clé `intensite`)."""
    params = {'taux_exoneration': 0.5}
    out = validate_intensite_domain('exonerations_salaires', params, strict=True)
    assert out is params


@pytest.mark.parametrize('strict', [True, False])
def test_noop_when_intensite_is_none_preserves_legacy_path(strict):
    """`{'intensite': None}` = entrée legacy légitime (slider non posé) :
    no-op dans LES DEUX modes. Aligne le contrat sur _resolve_intensite_
    or_legacy (`params.get('intensite', None) is not None`) — sans ce
    correctif `None < low` lèverait TypeError et casserait une entrée
    auparavant fonctionnelle (régression de contrat fin, revue Passe 1)."""
    params = {'intensite': None, 'taux_exoneration': 0.5}
    out = validate_intensite_domain('taxe_superprofits', params, strict=strict)
    assert out is params


def test_nan_intensite_treated_out_of_domain():
    """NaN n'est ni < low ni > high (les deux comparaisons False) : sans
    garde explicite il passe le filet et empoisonne TOUTE la trajectoire
    en silence. Doit être traité hors domaine : ValueError en strict,
    clamp+warning en tolérant (revue Passe 1, silent-failure-hunter)."""
    nan = float('nan')
    params = {'intensite': nan}
    with pytest.raises(ValueError, match='hors domaine'):
        validate_intensite_domain('optimisation_dette', params, strict=True)
    out = validate_intensite_domain('optimisation_dette', params, strict=False)
    assert out is not params  # copie défensive
    assert out['intensite'] == 0.0  # NaN → borne basse du domaine [0,1]


def test_in_domain_value_returns_same_object():
    """Valeur valide → objet params identique (garantit golden byte-identique :
    le garde-fou est un no-op pur sur toute entrée légitime)."""
    params = {'intensite': 0.6}
    out = validate_intensite_domain('isf_climatique', params, strict=True)
    assert out is params


@pytest.mark.parametrize('value', [-0.3, 0.3, 0.0])
def test_boundary_values_are_inclusive(value):
    """Bornes incluses : fiscalite_patrimoine accepte -0.3 et +0.3 (injectés
    légitimement par test_reforme_fiscale)."""
    params = {'intensite': value}
    out = validate_intensite_domain('fiscalite_patrimoine', params, strict=True)
    assert out is params


def test_tolerant_clamps_above_max_to_bound():
    """Mode tolérant, intensite > max → copie clampée à la borne haute."""
    params = {'intensite': 1.5}
    out = validate_intensite_domain('optimisation_dette', params, strict=False)
    assert out is not params  # copie défensive (pas de mutation de l'entrée)
    assert out['intensite'] == 1.0
    assert params['intensite'] == 1.5  # entrée d'origine intacte


def test_tolerant_clamps_below_min_to_bound():
    """Mode tolérant, intensite < min → copie clampée à la borne basse."""
    params = {'intensite': -0.9}
    out = validate_intensite_domain('fiscalite_patrimoine', params, strict=False)
    assert out['intensite'] == -0.3


def test_strict_raises_valueerror_out_of_domain():
    """Mode strict, hors domaine → ValueError (capté en aval par l'except
    orchestrateur → ExceptionGroup Item 3)."""
    with pytest.raises(ValueError, match='hors domaine'):
        validate_intensite_domain(
            'taxe_superprofits', {'intensite': 5.0}, strict=True
        )


@pytest.mark.parametrize('strict', [True, False])
def test_str_intensite_raises_typeerror_not_valueerror(strict):
    """LOAD-BEARING (mini-design §3.3) : une `str` lève TypeError à la
    comparaison numérique, JAMAIS ValueError ni early-return. Préserve le
    contrat MIXIN_BAD_PARAMS (str → TypeError → _handler_failed →
    ExceptionGroup). Vrai dans les DEUX modes (le TypeError précède la
    bifurcation strict/tolérant)."""
    with pytest.raises(TypeError):
        validate_intensite_domain(
            'optimisation_dette', {'intensite': 'not-a-number'}, strict=strict
        )


def test_registry_excludes_bimodal_effort_levers():
    """fraude_* (`effort` bimodal intensité-vs-Md€) HORS périmètre v1
    (renvoyé au chantier Item 2). Garde-fou anti-régression de périmètre."""
    assert 'fraude_fiscale' not in INTENSITE_DOMAINS
    assert 'fraude_sociale' not in INTENSITE_DOMAINS
    assert set(INTENSITE_DOMAINS) == {
        'optimisation_dette', 'isf_climatique', 'taxe_superprofits',
        'exonerations_salaires', 'fiscalite_patrimoine',
    }


# --------------------------------------------------------------------------
# Intégration simulateur : branchement orchestrateur + synergie Item 3
# --------------------------------------------------------------------------

def _impacts_records(report, measure_id):
    return [
        y[measure_id]
        for y in report['measure_impacts_by_year']
        if measure_id in y
    ]


def test_tolerant_out_of_domain_runs_clamped_no_handler_failure():
    """Bout-en-bout tolérant : optimisation_dette intensite=1.5 ne casse pas
    le service (pas de _handler_failed) ET produit la trajectoire EXACTE de
    intensite=1.0 (preuve que la valeur effective est la borne, pas 1.5)."""
    sim_oob = BudgetSimulatorV45(periods=3)
    sim_oob.mesures = {'optimisation_dette': {'intensite': 1.5}}
    sim_bound = BudgetSimulatorV45(periods=3)
    sim_bound.mesures = {'optimisation_dette': {'intensite': 1.0}}
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': ''}), \
         patch('numpy.random.normal', return_value=0):
        res_oob, _, rep_oob = sim_oob.simulate()
        res_bound, _, _ = sim_bound.simulate()

    for rec in _impacts_records(rep_oob, 'optimisation_dette'):
        assert not rec.get(HANDLER_FAILED_KEY), \
            f"clamp tolérant ne doit pas faire échouer le handler : {rec}"
    assert res_oob.to_dict(orient='records') == res_bound.to_dict(orient='records'), \
        "intensite=1.5 clampé doit produire la trajectoire de intensite=1.0"


def test_strict_out_of_domain_escalates_as_exceptiongroup_valueerror():
    """Bout-en-bout strict : intensite hors domaine → ExceptionGroup
    contenant UN ValueError annoté measure_id (synergie Lot C Item 3, aucune
    mécanique d'escalade nouvelle)."""
    sim = BudgetSimulatorV45(periods=2)
    sim.mesures = {'optimisation_dette': {'intensite': 1.5}}
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1'}), \
         patch('numpy.random.normal', return_value=0), \
         pytest.raises(ExceptionGroup) as excinfo:
        sim.simulate()
    inner = excinfo.value.exceptions
    assert len(inner) == 1, f"une seule mesure fautive attendue : {inner!r}"
    assert isinstance(inner[0], ValueError), \
        f"ValueError attendu dans le groupe, obtenu {inner[0]!r}"
    notes = getattr(inner[0], '__notes__', [])
    assert any('measure_id=optimisation_dette,' in n for n in notes), \
        f"note d'identification bornée manquante : {notes!r}"


def test_strict_str_intensite_still_typeerror_not_valueerror():
    """LOAD-BEARING : post-Item 1, optimisation_dette intensite='not-a-number'
    en STRICT escalade toujours en TypeError (PAS ValueError). Prouve que le
    garde-fou n'a pas transformé le contrat MIXIN_BAD_PARAMS en faux-vert
    (str interceptée comme 'hors domaine' aurait été une régression)."""
    sim = BudgetSimulatorV45(periods=2)
    sim.mesures = {'optimisation_dette': {'intensite': 'not-a-number'}}
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1'}), \
         patch('numpy.random.normal', return_value=0), \
         pytest.raises(ExceptionGroup) as excinfo:
        sim.simulate()
    inner = excinfo.value.exceptions
    assert len(inner) == 1
    assert isinstance(inner[0], TypeError), \
        f"str doit rester TypeError (contrat MIXIN), obtenu {inner[0]!r}"
