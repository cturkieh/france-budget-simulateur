"""Release E, revue adverse — domaines élargis pour l'encodage des programmes
(release de paramètres suivante) : créations de postes de la fonction publique
jusqu'à +140 000, budget chômage en montant jusqu'à 24,85 Md€.

Règle des domaines (constants.py, ``_PARAM_DOMAINS_MOTEUR``) : union des bornes
d'interface et des valeurs à encoder, jamais plus étroite. Chaque élargissement
est vérifié sans écrêtage (porte stricte et tolérante), et son effet sur les
plafonds internes du moteur est nommé :

- fonction publique : une CRÉATION de postes ne puise pas dans le vivier des
  départs (seul plafond interne, côté réductions) ; la propriété v0.7.2 « borne
  basse < capacité du vivier du mandat » est inchangée ;
- budget chômage : le montant est une autre écriture du taux de remplacement
  (montant = base × taux / 60 %, modes exclusifs) ; la borne basse du taux est
  DÉRIVÉE de celle du montant, pour que les deux écritures couvrent la même
  plage (aucune porte qui contourne l'autre).
"""
import pytest

from budget_simulator import BudgetSimulatorV45
from budget_simulator.constants import (
    CHOMAGE_MONTANT_REF_MD,
    CHOMAGE_TAUX_REF,
    PARAM_DOMAINS,
)
from budget_simulator.engine._param_domain import EntreeInvalide, ParametreIgnore, validate_param_domains
from budget_simulator.handlers.efficience import FP_EFFECTIFS_ANNEE_CIBLE

DEBUT = 2028
CREATIONS_MAX = 140_000
CHOMAGE_MONTANT_MIN = 24.85


def _simuler(mesures, strict=False, monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.setenv('BUDGETLAB_STRICT', '1' if strict else '')
    return BudgetSimulatorV45(periods=10, mesures=mesures, annee_debut=DEBUT).simulate()


def test_borne_haute_des_effectifs_couvre_140_000_creations():
    bas, haut = PARAM_DOMAINS['fonction_publique']['effectifs']
    assert bas == -500_000.0          # décision du 08/11/2026 inchangée
    assert haut == float(CREATIONS_MAX)


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
def test_140_000_creations_sans_ecretage_ni_plafond_interne(monkeypatch, strict):
    """+140 000 postes, mode cadre 2028 : aucune correction (rapport valide,
    ``leviers_ecretes`` vide), et la dépense suit la rampe de mandat sans
    rabot : sa variation annuelle est constante de 2028 à 2032 (1/5 du stock
    par an), puis nulle hors revalorisation du coût d'un agent."""
    df, det, rapport = _simuler({'fonction_publique': {'effectifs': CREATIONS_MAX}}, strict, monkeypatch)
    assert rapport['valid'] is True, rapport['warnings']
    assert rapport['leviers_ecretes'] == []
    par_annee = {a['Année']: a for a in rapport['measure_impacts_by_year']}
    depenses = {a: par_annee[a]['fonction_publique']['depenses']
                for a in range(DEBUT, FP_EFFECTIFS_ANNEE_CIBLE + 1)}
    assert all(d > 0 for d in depenses.values()), depenses
    # Stock atteint en 2032 : 140 000 postes au coût de l'année (≈ 60 k€ 2025).
    assert depenses[FP_EFFECTIFS_ANNEE_CIBLE] == pytest.approx(
        CREATIONS_MAX * 60_000 / 1e9, rel=0.25), depenses


def test_au_dela_de_140_000_ecrete_en_tolerant_refuse_en_strict():
    ecretages = {}
    out = validate_param_domains('fonction_publique', {'effectifs': 150_000}, strict=False,
                                 corrections={}, ecretages=ecretages)
    assert out['effectifs'] == float(CREATIONS_MAX)
    assert list(ecretages.values())[0]['borne'] == [-500_000.0, float(CREATIONS_MAX)]
    with pytest.raises(EntreeInvalide):
        validate_param_domains('fonction_publique', {'effectifs': 150_000}, strict=True)


def test_borne_basse_du_budget_chomage_en_montant_et_taux_derive():
    """Montant : borne basse 24,85 Md€ ; taux : borne basse DÉRIVÉE (même
    plage dans les deux écritures, à l'arrondi flottant près) ; bornes hautes
    inchangées (80 % ↔ 48,8 Md€)."""
    m_bas, m_haut = PARAM_DOMAINS['chomage_alloc']['montant']
    t_bas, t_haut = PARAM_DOMAINS['chomage_alloc']['taux_remplacement']
    assert m_bas == CHOMAGE_MONTANT_MIN
    assert t_bas == pytest.approx(CHOMAGE_TAUX_REF * CHOMAGE_MONTANT_MIN / CHOMAGE_MONTANT_REF_MD, rel=1e-15)
    assert t_haut == 0.80
    assert m_haut == pytest.approx(CHOMAGE_MONTANT_REF_MD * t_haut / CHOMAGE_TAUX_REF, rel=1e-15)


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
def test_budget_chomage_a_24_85_sans_ecretage(monkeypatch, strict):
    """24,85 Md€ (mode montant, sans taux : modes exclusifs respectés) : aucune
    correction ; dépense du canal taux = 24,85 − base, chaque année."""
    _, _, rapport = _simuler({'chomage_alloc': {'montant': CHOMAGE_MONTANT_MIN, 'duree': 18}},
                             strict, monkeypatch)
    assert rapport['valid'] is True, rapport['warnings']
    assert rapport['leviers_ecretes'] == []
    par_annee = {a['Année']: a for a in rapport['measure_impacts_by_year']}
    assert par_annee[DEBUT]['chomage_alloc']['depenses'] == pytest.approx(
        CHOMAGE_MONTANT_MIN - CHOMAGE_MONTANT_REF_MD, abs=1e-9)


def test_modes_exclusifs_du_budget_chomage_inchanges(monkeypatch):
    """Taux et montant ensemble : toujours refusés en strict (porte des modes
    exclusifs), quel que soit l'élargissement."""
    monkeypatch.setenv('BUDGETLAB_STRICT', '1')
    with pytest.raises(ExceptionGroup) as groupe:   # échecs stricts collectés par l'orchestrateur
        BudgetSimulatorV45(periods=10, annee_debut=DEBUT, mesures={
            'chomage_alloc': {'montant': CHOMAGE_MONTANT_MIN, 'taux_remplacement': 0.5}}).simulate()
    assert any(isinstance(e, ParametreIgnore) for e in groupe.value.exceptions), groupe.value.exceptions
