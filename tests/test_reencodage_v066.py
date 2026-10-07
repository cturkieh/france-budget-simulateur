"""Tests-propriétés du re-encodage d'octobre 2026 (v0.6.6) — RN, Horizons, LR.

Contrat posé par la règle symétrique d'encodage (METHODOLOGIE § « Règle d'encodage
des programmes politiques ») : un scénario de parti ne porte QUE des écarts au droit voté
(`plf_2026`) que sa source vivante chiffre ou paramètre. Tout le reste revient au
droit en vigueur ; un levier absent de la source vivante est retiré.

Entrées (arbitrages du 07/10/2026 sur le dossier de sourcing du même jour) :

  rn_2027       contre-budget 2027 + trajectoire 2027-2032 présentés le 06/10/2026
                (document non publié en ligne : presse convergente). Retraites 62/42
                (60 ans des carrières longues non modélisable par un levier à âge
                unique) ; taxe sur les superprofits et baisse des cotisations
                salariales RETIRÉES (jamais chiffrées, absentes du 06/10) ; tous les
                paramètres hérités sans source revenus au droit voté.
  horizons_2027 réforme des retraites du 29/09/2026 : 65 ans / 45 annuités.
  lr_2027       projet avecretailleau.fr (mesures 24, 25, 34) + effectifs annoncés
                (LCI 22/09) ; durée de cotisation = droit en vigueur (aucune annoncée).

Propriétés verrouillées :
  (a) RN : les deux mesures retirées sont posées au droit voté (pas omises), et
      rn_2027 porte exactement le jeu de leviers de plf_2026 ;
  (b) RN : chaque paramètre hors écarts sourcés vaut EXACTEMENT le droit voté —
      c'est la forme exécutable de « aucune économie ni dépense non sourcée » ;
  (c) RN : les écarts sourcés valent les arbitrages ;
  (d) Horizons / LR : les paramètres re-encodés valent les arbitrages ;
  (e) pourquoi « retirer » = poser au droit voté et JAMAIS omettre la clé : une clé
      absente vaut le DÉFAUT DU MOTEUR (config.py, année 2025), pas la loi votée —
      et pour `taxe_superprofits` le handler à intensité 0 émet encore −0,002 de
      compétitivité (branche `tous_secteurs` fausse, dette moteur tracée v0.6.7),
      que portent les neuf autres scénarios. Omettre la clé chez le seul RN lui
      retirerait cet artefact : traitement asymétrique. La propriété vérifie que la
      trajectoire RN est celle du droit voté pour ces deux leviers, à l'identique.
"""
import sys
from pathlib import Path

import pytest

from budget_simulator.simulator import BudgetSimulatorV45

SNAPSHOTS_DIR = Path(__file__).parent / 'snapshots'
sys.path.insert(0, str(SNAPSHOTS_DIR))
from run_scenarios_full import SCENARIOS  # noqa: E402

_SCENARIOS = pytest.mark.skipif(not SCENARIOS, reason="scenarios.json absent (fork moteur seul)")

RN_CLES_RETIREES = ('taxe_superprofits', 'cotisations_salariales')

# Écarts au droit voté que le contre-budget du 06/10/2026 chiffre ou paramètre
# (table du dossier de sourcing, statut PROUVÉ ou arbitré le 07/10/2026).
RN_ECARTS_SOURCES = {
    ('retraites', 'age_depart'): 62.0,
    ('retraites', 'duree_cotisation'): 42.0,
    ('fonction_publique', 'effectifs'): -201000,     # 85 000 agences + 116 000 collectivités
    ('collectivites', 'dotation'): 109.2,            # 116,6 − 8,2 + 0,8 (part effectifs déjà comptée)
    ('immigration', 'ame'): 0.0,                     # 1,3 Md€ annoncés > budget AME du levier (1,2)
    ('fraude_fiscale', 'effort'): 1.0,               # plafond du levier
    ('tva_energie', 'taux'): 0.055,
    ('impots_production', 'montant'): 80,            # 97 − 17 (CFE + CVAE + C3S)
    ('transition_ecologique', 'renovation'): 3.8,    # 100 % Rénov' 5,1 − MaPrimeRénov' 1,3
    ('transition_ecologique', 'taxe_carbone'): 30.5,  # composante carbone 2017
    ('recherche_publique', 'budget'): 19,            # base 10 + 9 Md€
}

HORIZONS_ATTENDU = {
    ('retraites', 'age_depart'): 65.0,
    ('retraites', 'duree_cotisation'): 45.0,
}

LR_ATTENDU = {
    ('cotisations_patronales', 'taux'): 0.2525,
    ('cotisations_salariales', 'baisse_points'): 2.5,
    ('impots_production', 'montant'): 83,
    ('fonction_publique', 'effectifs'): -300000,
    ('retraites', 'duree_cotisation'): 42.5,
    ('chomage_alloc', 'duree'): 18,
}


def _params(scenario):
    return {(lev, p): v for lev, ps in scenario.items() for p, v in ps.items()}


@_SCENARIOS
def test_a_rn_mesures_retirees_au_droit_vote_et_meme_jeu_de_leviers():
    rn, ref = SCENARIOS['rn_2027'], SCENARIOS['plf_2026']
    for cle in RN_CLES_RETIREES:
        assert rn.get(cle) == ref[cle], (
            f"{cle} : {rn.get(cle)!r} dans rn_2027, droit voté {ref[cle]!r} — "
            "une mesure retirée se pose au droit voté, elle ne s'omet pas (cf. (e))"
        )
    assert set(rn) == set(ref), (
        f"leviers rn_2027 ≠ plf_2026 : en trop={set(rn) - set(ref)} ; "
        f"manquants={set(ref) - set(rn)}"
    )


@_SCENARIOS
def test_b_rn_tout_parametre_non_source_vaut_le_droit_vote():
    rn, ref = _params(SCENARIOS['rn_2027']), _params(SCENARIOS['plf_2026'])
    ecarts = {
        k: (ref.get(k), v) for k, v in rn.items()
        if k not in RN_ECARTS_SOURCES and v != ref.get(k)
    }
    assert not ecarts, f"paramètres RN hérités sans source (droit voté, RN) : {ecarts}"


@_SCENARIOS
@pytest.mark.parametrize('cle,attendu', RN_ECARTS_SOURCES.items(), ids=lambda x: str(x))
def test_c_rn_ecarts_sources(cle, attendu):
    assert _params(SCENARIOS['rn_2027']).get(cle) == attendu


@_SCENARIOS
@pytest.mark.parametrize(
    'sid,cle,attendu',
    [('horizons_2027', k, v) for k, v in HORIZONS_ATTENDU.items()]
    + [('lr_2027', k, v) for k, v in LR_ATTENDU.items()],
    ids=lambda x: str(x),
)
def test_d_horizons_lr_arbitrages(sid, cle, attendu):
    assert _params(SCENARIOS[sid]).get(cle) == attendu


@_SCENARIOS
def test_e_retrait_au_droit_vote_et_non_par_omission():
    """Poser les deux leviers au droit voté ≠ les omettre : l'omission décale la
    trajectoire RN (artefact du handler superprofits à intensité 0) — c'est ce qui
    interdit la forme « clé absente » pour un retrait."""
    rn = SCENARIOS['rn_2027']
    omis = {k: v for k, v in rn.items() if k not in RN_CLES_RETIREES}
    df_vote, _, _ = BudgetSimulatorV45(periods=10, mesures=rn).simulate()
    df_omis, _, _ = BudgetSimulatorV45(periods=10, mesures=omis).simulate()
    assert not df_vote.equals(df_omis), (
        "l'omission est devenue neutre (artefact superprofits corrigé ?) : la "
        "forme « clé absente » redevient admissible — mettre à jour (e) et (a)"
    )
