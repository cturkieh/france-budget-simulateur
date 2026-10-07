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
  (a) RN : les deux mesures retirées sont posées au droit voté (pas omises) ;
  (b) RN, LR, Horizons : même jeu de leviers que plf_2026, et chaque paramètre hors
      écarts sourcés vaut EXACTEMENT le droit voté — c'est la forme exécutable de
      « aucune économie ni dépense non sourcée » ;
  (c) RN, LR, Horizons : les écarts sourcés valent les arbitrages ;
  (d) pourquoi « retirer » = poser au droit voté et JAMAIS omettre la clé : une clé
      absente vaut le DÉFAUT DU MOTEUR (config.py, année 2025), pas la loi votée —
      et pour `taxe_superprofits` le handler à intensité 0 émet encore −0,002 de
      compétitivité (branche `tous_secteurs` fausse, dette moteur tracée v0.6.7),
      que portent les six autres scénarios à intensité 0 (trois autres sont à
      intensité positive, cf. docstring du test). Omettre la clé chez le seul RN lui
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

# Invariant « droit en vigueur sauf écart sourcé », appliqué par scénario. Clé = id
# du scénario, valeur = liste EXPLICITE de ses écarts sourcés à plf_2026.
# LR et Horizons : audit levier par levier du 07/10/2026 (tableau au CHANGELOG parent).
LR_ECARTS_SOURCES = {
    ('cotisations_patronales', 'taux'): 0.2525,      # > 25 Md€ coût du travail (avecretailleau.fr)
    ('cotisations_salariales', 'baisse_points'): 2.5,  # ~15 Md€ rendus aux salariés
    ('impots_production', 'montant'): 83,            # 97 − 14 (C3S, CVAE, forfait social, CFE ind.)
    ('fonction_publique', 'effectifs'): -300000,     # ~300 000 postes sur le quinquennat
    ('retraites', 'age_depart'): 65.0,               # taux plein à 65 ans
    ('asu', 'asu_activation'): 1,                    # compte social unique
    ('asu', 'asu_plafonnement'): 0.7,                # plafonné à 70 % du SMIC net
}

HORIZONS_ECARTS_SOURCES = {
    ('retraites', 'age_depart'): 65.0,               # réforme du 29/09/2026
    ('retraites', 'duree_cotisation'): 45.0,
    ('chomage_alloc', 'duree'): 12,                  # 12 mois (sourcé le 30/08/2026)
    ('impots_production', 'montant'): 47,            # pacte fiscal à somme nulle (30/08/2026)
    ('niches_fiscales_tge', 'montant'): 32,
    ('subventions_tge', 'montant'): 8,
    ('is_exceptionnel_tge', 'montant'): 0,           # fin de la surtaxe IS
    ('fonction_publique_reforme', 'fusion_agences'): 10,  # mesure annoncée, intensité = hypothèse écrite à la fiche
    ('fonction_publique_reforme', 'digitalisation'): 20,
}

# PS, LFI, Écologistes, Renaissance : paramètres hérités pas encore passés au crible,
# à ajouter ici à leurs prochains re-sourcings.
ECARTS_SOURCES_PAR_SCENARIO = {
    'rn_2027': RN_ECARTS_SOURCES,
    'lr_2027': LR_ECARTS_SOURCES,
    'horizons_2027': HORIZONS_ECARTS_SOURCES,
}


def _params(scenario):
    return {(lev, p): v for lev, ps in scenario.items() for p, v in ps.items()}


def _ecarts_au_droit_en_vigueur(sid, ecarts_sources):
    """Écarts de `sid` à plf_2026 hors liste sourcée : (1) leviers en trop ou
    manquants, (2) paramètres différents. Itère sur l'UNION des clés : un paramètre
    présent dans plf_2026 et absent du scénario (= défaut moteur) est un écart."""
    scn, ref = SCENARIOS[sid], SCENARIOS['plf_2026']
    leviers = {'en_trop': set(scn) - set(ref), 'manquants': set(ref) - set(scn)}
    p_scn, p_ref = _params(scn), _params(ref)
    params = {
        k: (p_ref.get(k, '<absent>'), p_scn.get(k, '<absent>'))
        for k in set(p_ref) | set(p_scn)
        if k not in ecarts_sources and p_scn.get(k, '<absent>') != p_ref.get(k, '<absent>')
    }
    return leviers, params


@_SCENARIOS
def test_a_rn_mesures_retirees_au_droit_vote():
    rn, ref = SCENARIOS['rn_2027'], SCENARIOS['plf_2026']
    for cle in RN_CLES_RETIREES:
        assert rn.get(cle) == ref[cle], (
            f"{cle} : {rn.get(cle)!r} dans rn_2027, droit voté {ref[cle]!r} — "
            "une mesure retirée se pose au droit voté, elle ne s'omet pas (cf. (d))"
        )


@_SCENARIOS
@pytest.mark.parametrize('sid', sorted(ECARTS_SOURCES_PAR_SCENARIO))
def test_b_tout_parametre_non_source_vaut_le_droit_en_vigueur(sid):
    leviers, params = _ecarts_au_droit_en_vigueur(sid, ECARTS_SOURCES_PAR_SCENARIO[sid])
    assert not leviers['en_trop'] and not leviers['manquants'], f"{sid} leviers : {leviers}"
    assert not params, f"paramètres {sid} hérités sans source (droit en vigueur, {sid}) : {params}"


@_SCENARIOS
@pytest.mark.parametrize(
    'sid,cle,attendu',
    [(sid, k, v) for sid, ecarts in sorted(ECARTS_SOURCES_PAR_SCENARIO.items())
     for k, v in ecarts.items()],
    ids=str,
)
def test_c_ecarts_sources_valent_les_arbitrages(sid, cle, attendu):
    assert _params(SCENARIOS[sid]).get(cle) == attendu


@_SCENARIOS
def test_d_retrait_au_droit_vote_et_non_par_omission():
    """Poser les deux leviers au droit voté ≠ les omettre : l'omission décale la
    trajectoire RN (artefact du handler superprofits à intensité 0) — c'est ce qui
    interdit la forme « clé absente » pour un retrait.

    État de `taxe_superprofits` dans scenarios.json (vérifié le 07/10/2026) : hors RN,
    6 scénarios à intensité 0 (plf_2026, renaissance, horizons, lr, im_rabot,
    im_competitivite) portent l'artefact ; 3 à intensité positive (lfi 1,0, ps 0,5,
    ecologistes 0,5) portent la mesure elle-même."""
    rn = SCENARIOS['rn_2027']
    omis = {k: v for k, v in rn.items() if k not in RN_CLES_RETIREES}
    df_vote, _, _ = BudgetSimulatorV45(periods=10, mesures=rn).simulate()
    df_omis, _, _ = BudgetSimulatorV45(periods=10, mesures=omis).simulate()
    assert not df_vote.equals(df_omis), (
        "l'omission est devenue neutre (artefact superprofits corrigé ?) : la "
        "forme « clé absente » redevient admissible — mettre à jour (d) et (a)"
    )
