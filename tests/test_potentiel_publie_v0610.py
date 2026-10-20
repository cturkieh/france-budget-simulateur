"""Colonnes de croissance potentielle = potentiel CONSOMMÉ par l'année (v0.6.10,
contre-audit externe du 07/10/2026, réserve V2-02).

Constat : dans la boucle annuelle, l'output gap est mis à jour avec le potentiel
de l'année, PUIS ``update_potential_growth`` clôt l'année (hystérèse du
tendanciel, bonus d'offre structurel préparés pour t+1), PUIS la ligne de sortie
relisait l'état. La colonne ``Croissance_Potentielle_Totale %`` publiait donc le
potentiel de l'année SUIVANTE : l'identité de l'output gap n'était pas
reconstructible depuis les sorties (81 scénarios sur 280 au contre-audit).

Cas du contre-audit, ``{"recherche_publique": {"budget": 20}}``, 2030, valeurs
non arrondies : croissance 1,093783 % ; potentiel consommé 1,048206 % ; colonne
publiée 1,248206 % ; output gap 0,200243 %. Le bonus recherche naît à la
5ᵉ année active (fin 2030) : il ne compte qu'à partir de 2031.

Instrumentation (sans modifier le moteur) : ``round`` neutralisé dans
l'orchestrateur, comme au contre-audit, et sous-classe qui photographie
``croissance_potentielle_totale()`` à l'ENTRÉE de ``update_potential_growth``,
c'est-à-dire la valeur que croissance, Okun et output gap viennent de lire.
"""
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from budget_simulator.engine import orchestrator as orchestrator_module
from budget_simulator.simulator import BudgetSimulatorV45

CAS_AUDIT = {'recherche_publique': {'budget': 20}}
CAS_HYSTERESE = 'levier_transition_invest_50_hysteresis'
ANNEE_AUDIT = 2030


class _SimulateurInstrumente(BudgetSimulatorV45):
    """Photographie le potentiel consommé, juste avant la clôture de l'année."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.potentiel_consomme = {}

    def update_potential_growth(self, growth, year):
        self.potentiel_consomme[self.annee_base + year] = {
            'total': self.croissance_potentielle_totale(),
            'tendanciel': self.base_params['croissance_potentielle'],
            'offre_structurelle': self._potential_growth_bonus,
            'offre_travail': self._labour_supply_bonus,
            'trainee_dette': self._debt_drag,
        }
        super().update_potential_growth(growth, year)


def _simuler_brut(mesures):
    """Simulation 10 ans, colonnes NON arrondies, plus le potentiel consommé."""
    df, detail, sim = _simuler_brut_avec_simulateur(mesures)
    return df, detail, sim.potentiel_consomme


def _simuler_brut_avec_simulateur(mesures):
    """Comme ``_simuler_brut``, en rendant le simulateur (état d'entrée)."""
    sim = _SimulateurInstrumente(periods=10, mesures=mesures)
    with patch.object(orchestrator_module, 'round', lambda x, n=None: float(x), create=True):
        df, detail, _ = sim.simulate()
    return df.set_index('Année'), detail.set_index('Année'), sim


def test_v2_02_colonne_potentiel_total_2030_est_le_potentiel_consomme():
    """Rouge sur v0.6.9 : colonne 1,248206 % contre 1,048206 % consommé."""
    df, detail, consomme = _simuler_brut(CAS_AUDIT)

    # Les chiffres du contre-audit se reproduisent (6 décimales publiées).
    assert df.loc[ANNEE_AUDIT, 'Croissance %'] == pytest.approx(1.093783, abs=5e-7)
    assert detail.loc[ANNEE_AUDIT, 'Output_Gap %'] == pytest.approx(0.200243, abs=5e-7)
    assert consomme[ANNEE_AUDIT]['total'] * 100 == pytest.approx(1.048206, abs=5e-7)

    # La colonne publiée est le potentiel consommé, pas celui préparé pour 2031.
    assert detail.loc[ANNEE_AUDIT, 'Croissance_Potentielle_Totale %'] == pytest.approx(
        consomme[ANNEE_AUDIT]['total'] * 100, abs=1e-12)


# ---------------------------------------------------------------------------
# Tests-propriétés durables : l'identité du gap se reconstruit depuis les SEULES
# colonnes de sortie, pour les programmes publiés, le statu quo et cinq leviers
# isolés qui touchent le potentiel (offre structurelle, offre de travail).
# ---------------------------------------------------------------------------
def _programmes_publies():
    """{id: apiMeasures} de scenarios.json (vide dans un clone du moteur seul)."""
    chemin = (os.environ.get('BUDGETLAB_SCENARIOS_JSON') or '').strip()
    if not chemin or not Path(chemin).exists():
        return {}
    return {k: v['apiMeasures']
            for k, v in json.loads(Path(chemin).read_text(encoding='utf-8')).items()}


CAS = {
    **_programmes_publies(),
    'statu_quo': {},
    # Offre structurelle (SUPPLY_EFFECTS) : naissance du bonus à des dates différentes.
    'levier_recherche_20': CAS_AUDIT,
    'levier_transition_invest_30': {'transition_ecologique': {'investissement': 30}},
    'levier_renovation_20': {'transition_ecologique': {'renovation': 20}},
    'levier_recherche_coupe_0': {'recherche_publique': {'budget': 0}},
    # Offre de travail (canal emploi seniors), posée en tête d'année.
    'levier_retraites_age_65': {'retraites': {'age_depart': 65}},
    # Hystérèse du tendanciel : seul cas PUBLIC qui le fait bouger (les
    # programmes qui le déclenchent exigent scenarios.json, absent du dépôt
    # public) — sans lui, `Croissance_Potentielle %` n'y serait pas testée.
    CAS_HYSTERESE: {'transition_ecologique': {'investissement': 50}},
}

# Demi-unité du dernier chiffre publié (round(·, 2) en points de %) : borne de
# l'erreur d'arrondi de chaque colonne, en taux. Marge flottante 1e-12.
DEMI_UNITE_ARRONDI = 0.5 * 10 ** -2 / 100 + 1e-12


def _residu(gap_prec, croissance, potentiel, gap):
    return (1 + gap) - (1 + gap_prec) * (1 + croissance) / (1 + potentiel)


def test_les_cas_couvrent_les_programmes_publies_quand_ils_sont_disponibles():
    """Garde anti-skip silencieux : avec scenarios.json, les 10 programmes."""
    if (os.environ.get('BUDGETLAB_SCENARIOS_JSON') or '').strip():
        assert len(CAS) == len(_programmes_publies()) + 7
        assert len(_programmes_publies()) >= 10


def test_un_cas_public_deplace_le_tendanciel_par_hysteresis():
    """Garde de couverture : sans scenarios.json, la colonne tendancielle
    n'est testée que si un levier public déclenche l'hystérèse. Si une
    recalibration la rendait inerte pour ce cas, ce test le dit (au lieu
    de laisser `Croissance_Potentielle %` sans protection en silence)."""
    _, _, consomme = _simuler_brut(CAS[CAS_HYSTERESE])
    tendanciels = {etat['tendanciel'] for etat in consomme.values()}
    assert len(tendanciels) > 1, f"{CAS_HYSTERESE} : tendanciel constant {tendanciels}"


@pytest.mark.parametrize('cas', sorted(CAS))
def test_identite_du_gap_depuis_les_colonnes_non_arrondies(cas):
    """Résidu ≤ 1e-12 : même opération flottante que la récurrence du moteur."""
    df, detail, _ = _simuler_brut(CAS[cas])
    for an in df.index[1:]:
        r = _residu(detail.loc[an - 1, 'Output_Gap %'] / 100, df.loc[an, 'Croissance %'] / 100,
                    detail.loc[an, 'Croissance_Potentielle_Totale %'] / 100,
                    detail.loc[an, 'Output_Gap %'] / 100)
        assert abs(r) <= 1e-12, f"{cas} {an} : résidu {r:.3e}"


@pytest.mark.parametrize('cas', sorted(CAS))
def test_identite_du_gap_depuis_les_colonnes_publiees(cas):
    """Colonnes arrondies à 2 décimales, telles que servies par l'API.

    Tolérance CALCULÉE, pas devinée : chaque colonne est à au plus une
    demi-unité d'arrondi (0,005 pt) de sa valeur exacte. Le résidu est
    monotone en chaque variable (croissant en gap_t et en g*, décroissant en
    gap_{t−1} et en g) : son image sur la boîte d'arrondi est l'intervalle
    borné par les deux coins opposés. L'identité exacte (résidu nul) doit
    tomber dans cet intervalle — sa demi-largeur vaut ≈ 4 × 5e-5 = 2e-4, à
    comparer à l'écart de 2e-3 que produisait la colonne de t+1 (v0.6.9).
    """
    df, detail, _ = BudgetSimulatorV45(periods=10, mesures=CAS[cas]).simulate()
    df, detail = df.set_index('Année'), detail.set_index('Année')
    e = DEMI_UNITE_ARRONDI
    for an in df.index[1:]:
        g0 = detail.loc[an - 1, 'Output_Gap %'] / 100
        g = df.loc[an, 'Croissance %'] / 100
        p = detail.loc[an, 'Croissance_Potentielle_Totale %'] / 100
        g1 = detail.loc[an, 'Output_Gap %'] / 100
        bas = _residu(g0 + e, g + e, p - e, g1 - e)
        haut = _residu(g0 - e, g - e, p + e, g1 + e)
        assert bas <= 0.0 <= haut, (
            f"{cas} {an} : identité hors de la boîte d'arrondi [{bas:.2e} ; {haut:.2e}]")


@pytest.mark.parametrize('cas', sorted(CAS))
def test_chaque_colonne_de_potentiel_est_la_valeur_consommee(cas):
    """Les quatre colonnes de potentiel = l'état lu par croissance, Okun et
    output gap de l'année, photographié avant la clôture d'année ; et la
    colonne totale = tendanciel + offre structurelle + offre de travail +
    traînée de dette (la dernière sans colonne propre)."""
    _, detail, consomme = _simuler_brut(CAS[cas])
    colonnes = {'Croissance_Potentielle %': 'tendanciel',
                'Bonus_Potentiel_Supply %': 'offre_structurelle',
                'Bonus_Offre_Travail %': 'offre_travail',
                'Croissance_Potentielle_Totale %': 'total'}
    assert sorted(consomme) == list(detail.index[1:])
    for an, etat in consomme.items():
        for colonne, cle in colonnes.items():
            assert detail.loc[an, colonne] == pytest.approx(etat[cle] * 100, abs=1e-12), (
                f"{cas} {an} {colonne}")
        assert etat['total'] == pytest.approx(
            etat['tendanciel'] + etat['offre_structurelle'] + etat['offre_travail']
            + etat['trainee_dette'], abs=1e-15)


@pytest.mark.parametrize('cas', sorted(CAS))
def test_ligne_de_l_annee_de_base_publie_le_potentiel_d_entree(cas):
    """Ligne 2025 (branche de l'année de base, sans clôture d'année) : le
    potentiel publié est celui d'ENTRÉE de la simulation — tendanciel saisi,
    aucun bonus d'offre (ni structurelle, ni travail : leurs producteurs ne
    tournent qu'à partir de 2026), aucune traînée de dette. Oracle
    indépendant de la photographie : la valeur saisie, conservée par le
    simulateur dans ``_pre_simulate_croissance_potentielle``.
    """
    _, detail, sim = _simuler_brut_avec_simulateur(CAS[cas])
    base = detail.index[0]
    assert base == sim.annee_base
    tendanciel_saisi = sim._pre_simulate_croissance_potentielle * 100
    assert tendanciel_saisi > 0
    assert detail.loc[base, 'Croissance_Potentielle %'] == pytest.approx(tendanciel_saisi, abs=1e-12)
    assert detail.loc[base, 'Croissance_Potentielle_Totale %'] == pytest.approx(
        tendanciel_saisi, abs=1e-12)
    assert detail.loc[base, 'Bonus_Potentiel_Supply %'] == 0.0
    assert detail.loc[base, 'Bonus_Offre_Travail %'] == 0.0
