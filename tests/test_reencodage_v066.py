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
                (Capital 23/09, Figaro 29/09) ; durée de cotisation = droit en vigueur
                (aucune annoncée) ; tout levier hérité sans source → droit en vigueur
                (arbitrage du 07/10/2026, volet « Comptes publics » encore « à venir »).

Re-encodage du 02/11/2026 (v0.6.11, paramètres seuls, arbitrage du mainteneur du
02/11/2026 « on met à jour tout de suite ») :

  lr_2027       livret « Rétablir l'ordre dans les comptes publics » (15 fiches,
                12/10/2026, lu intégralement) : effectifs −400 000 (fiche 3, 25 Md€),
                assurance chômage 15 mois (fiche 8), AME réduite aux soins essentiels
                0,7 Md€ (fiche 9 → 1,2 − 0,7 = 0,5), impôts de production −15 Md€
                (fiche 14 → 97 − 15 = 82), fraude fiscale +5 Md€ nets (fiche 5 ; régime
                net du levier, même convention que le 0,14 de la LF 2026 →
                0,14 + 0,31 = 0,45), fraude sociale 4 Md€ (fiche 10 ; > capacité du
                levier avec l'ASU active → plafond 1,0, même règle que la fraude
                fiscale du RN), collectivités −10 Md€ de fonctionnement (fiche 12 →
                dotation 116,6 − 10 = 106,6, même levier que l'effort des collectivités
                du RN), énergies intermittentes subventionnées −4 Md€ (fiche 4 →
                subventions aux grandes entreprises 33 − 4 = 29), niches, politique
                de la ville et zonages −4,9 Md€ (fiche 4 → niches fiscales des grandes
                entreprises 57 − 5 = 52, arrondi au pas du curseur ; arbitrage du
                mainteneur : même levier que Renaissance 56, Horizons 32, PS 40,
                Écologistes 25, LFI 20). Les autres lignes du livret n'ont pas de
                levier (liste à la fiche du programme).
  horizons_2027 page « Pour une France plus prospère » réécrite (consultée le
                02/11/2026) : « un tiers des départs en retraite non remplacés, plus
                de 250 000 postes sur le quinquennat » → effectifs −250 000 ; la
                réforme des agences (10/20, intensité posée en hypothèse le 30/08/2026)
                est RETIRÉE (droit voté 0/0) : le candidat chiffre désormais lui-même
                le non-remplacement, même vivier de départs, même règle que le RN
                (agences comptées dans les effectifs, réforme à 0/0). Réponses sur
                l'école (23/10/2026) : +20 % de rémunération moyenne des enseignants
                → education.salaires 20 (coût brut ; le financement « par la baisse
                démographique » n'est pas crédité, règle 3).

Réencodage du 08/11/2026 (v0.7.2, décision du mainteneur) : la référence n'est plus le
droit VOTÉ brut (`plf_2026`) mais le droit en vigueur RÉAJUSTÉ sur l'exécution 2026
(voté + `reajustements_droit_en_vigueur` de `atterrissage_observe.json` : défense 58,
franchises 120, surtaxe IS 6,8), point de départ commun du mode cadre. Un paramètre
non sourcé vaut ce droit réajusté, auquel `plf_2026` est lui-même égal (garde
`test_cadre_v070_mesures_annee`). Ci-dessous, « droit voté » se lit « droit en vigueur
réajusté » partout où le test compare via `DROIT_REAJUSTE`.

Release de paramètres P (moteur v0.8.1, 12/11/2026) : tous les programmes sont
ré-encodés le même jour sur leurs sources, et chaque paramètre qui s'écarte de la
référence porte UNE entrée de source (url officielle, date de lecture, citation
vérifiée, règle, valeur) dans ``scenariosSources.json``, à côté de
``scenarios.json`` dans le dépôt parent. Les tables écrites à la main d'octobre et
de novembre (b, c) sont remplacées par ce registre : (b) et (c) le lisent, pour
tous les programmes. La référence est le droit en vigueur au premier budget du
mandat (2028), valeurs datées comprises (``plf_2026`` lui est égal, garde
``test_cadre_v070_mesures_annee``).

Propriétés verrouillées :
  (a) RN et Horizons : les mesures retirées sont posées au droit voté (pas omises) —
      RN : superprofits et cotisations salariales (07/10/2026) ; Horizons : réforme
      des agences (02/11/2026) ;
  (b) tous les programmes (release P) : chaque paramètre qui s'écarte de la
      référence a une entrée de source, et aucune entrée n'est sans écart — c'est
      la forme exécutable de « aucune économie ni dépense non sourcée » ;
  (c) tous les programmes (release P) : chaque entrée porte la valeur encodée ;
  (d) pourquoi « retirer » = poser au droit voté et JAMAIS omettre la clé : une clé
      absente vaut le DÉFAUT DU MOTEUR (config.py, année 2025), pas la loi votée.
      Historique : en v0.6.6, `taxe_superprofits` à intensité 0 émettait encore
      −0,002 de compétitivité (branche `tous_secteurs` fausse), si bien qu'omettre les
      deux clés retirées du RN décalait SA trajectoire. Artefact corrigé en v0.6.7
      (`tests/test_audit_codex_v067.py`) : (d1) prouve que, pour CES deux clés,
      l'omission est désormais neutre au bit. La règle d'encodage ne change pas pour
      autant, et (d2) la garde exécutable : pour un levier dont le défaut moteur
      diffère du droit voté (`sante` du RN), omettre la clé change bien la
      trajectoire. C'est toujours (a) qui vérifie la valeur des clés retirées.
"""
import json
import sys
from pathlib import Path

import pytest

from budget_simulator.simulator import BudgetSimulatorV45

SNAPSHOTS_DIR = Path(__file__).parent / 'snapshots'
sys.path.insert(0, str(SNAPSHOTS_DIR))
from run_scenarios_full import _SCENARIOS_JSON, SCENARIOS  # noqa: E402


def _droit_reajuste():
    """Droit en vigueur réajusté (08/11/2026) : droit voté du moteur
    (`droit_en_vigueur.json`) + réajustements de toutes les années observées de
    l'atterrissage, reconduits ensuite à droit constant. Lu dans le moteur, jamais
    recopié : un futur réajustement suit sans retoucher ce test. `plf_2026` lui est
    égal (garde test_cadre_v070_mesures_annee)."""
    from budget_simulator.constants import ANNEE_PREMIER_BUDGET_MANDAT
    from budget_simulator.engine.cadre import (charger_atterrissage, charger_droit_en_vigueur,
                                               droit_de_l_annee)
    # Release P : valeurs datées comprises, au premier budget du mandat.
    droit = charger_droit_en_vigueur()
    return droit_de_l_annee(droit.mesures, charger_atterrissage(), ANNEE_PREMIER_BUDGET_MANDAT,
                            droit.valeurs_datees)


DROIT_REAJUSTE = _droit_reajuste()

_SCENARIOS = pytest.mark.skipif(not SCENARIOS, reason="scenarios.json absent (fork moteur seul)")

RN_CLES_RETIREES = ('taxe_superprofits', 'cotisations_salariales')
# Leviers retirés par scénario (posés à la valeur de plf_2026, jamais omis — cf. (d)).
CLES_RETIREES_PAR_SCENARIO = {
    'rn_2027': RN_CLES_RETIREES,
    # 02/11/2026 : le candidat chiffre lui-même les postes non remplacés (250 000) ;
    # l'intensité 10/20 de la réforme des agences, posée en hypothèse le 30/08/2026,
    # puiserait dans le même vivier de départs (double comptage) — retirée.
    'horizons_2027': ('fonction_publique_reforme',),
}

def _registre_des_sources():
    """Entrées de source de la release de paramètres P (``scenariosSources.json``
    du dépôt parent, à côté du ``scenarios.json`` lu) ; ``{}`` hors dépôt parent."""
    if _SCENARIOS_JSON is None:
        return {}
    chemin = _SCENARIOS_JSON.with_name('scenariosSources.json')
    return json.loads(chemin.read_text(encoding='utf-8')) if chemin.exists() else {}


SOURCES = _registre_des_sources()
REFERENCE = 'plf_2026'
PROGRAMMES_SOURCES = sorted(sid for sid in SOURCES if sid != REFERENCE)
_REGISTRE = pytest.mark.skipif(not (SCENARIOS and SOURCES),
                               reason="scenarios.json ou scenariosSources.json absent (fork moteur seul)")


def _a_plat(scenario):
    return {f'{lev}.{p}': v for lev, ps in scenario.items() for p, v in ps.items()}


def _params(scenario):
    return {(lev, p): v for lev, ps in scenario.items() for p, v in ps.items()}


@_SCENARIOS
@pytest.mark.parametrize(
    'sid,cle',
    [(sid, cle) for sid, cles in sorted(CLES_RETIREES_PAR_SCENARIO.items()) for cle in cles],
    ids=str,
)
def test_a_mesures_retirees_au_droit_vote(sid, cle):
    scn, ref = SCENARIOS[sid], DROIT_REAJUSTE
    assert scn.get(cle) == ref[cle], (
        f"{cle} : {scn.get(cle)!r} dans {sid}, droit voté {ref[cle]!r} — "
        "une mesure retirée se pose au droit voté, elle ne s'omet pas (cf. (d))"
    )


@_SCENARIOS
def test_a2_horizons_reforme_des_agences_retiree_pas_a_l_intensite_heritee():
    """02/11/2026 : l'hypothèse d'intensité 10/20 (30/08/2026) ne survit pas au
    chiffre du candidat (250 000 postes) : même vivier, même règle que le RN."""
    assert SCENARIOS['horizons_2027']['fonction_publique_reforme'] == {'fusion_agences': 0, 'digitalisation': 0}
    assert SCENARIOS['horizons_2027']['fonction_publique']['effectifs'] == -250000


@_SCENARIOS
def test_a3_les_valeurs_hors_curseur_sont_dans_le_domaine_moteur():
    """LR −400 000 et Horizons +20 % dépassent le curseur d'UI : le domaine moteur
    (constants.PARAM_DOMAINS, élargi en v0.6.11 à la valeur servie, pas au-delà)
    doit les contenir, sinon le mode strict les refuse et le tolérant les clampe."""
    from budget_simulator.constants import PARAM_DOMAINS
    # v0.7.2 : borne basse portée à −500 000 (tests/test_parametres_v072.py) ;
    # la valeur servie de LR reste dans le domaine.
    assert PARAM_DOMAINS['fonction_publique']['effectifs'][0] <= -400_000.0
    assert PARAM_DOMAINS['education']['salaires'][1] == 20.0
    assert SCENARIOS['lr_2027']['fonction_publique']['effectifs'] == -400000
    assert SCENARIOS['horizons_2027']['education']['salaires'] == 20


@_REGISTRE
def test_b0_registre_et_scenarios_couvrent_les_memes_programmes():
    assert set(SOURCES) == set(SCENARIOS)
    assert REFERENCE in SCENARIOS and _params(SCENARIOS[REFERENCE]) == _params(DROIT_REAJUSTE)


@_REGISTRE
@pytest.mark.parametrize('sid', PROGRAMMES_SOURCES)
def test_b_tout_parametre_non_source_vaut_le_droit_en_vigueur(sid):
    """Tout paramètre qui s'écarte de la référence (présent d'un seul côté
    compris) a une entrée de source ; aucune entrée sans écart."""
    ref, scn = _a_plat(SCENARIOS[REFERENCE]), _a_plat(SCENARIOS[sid])
    ecarts = {k for k in set(ref) | set(scn) if scn.get(k, '<absent>') != ref.get(k, '<absent>')}
    entrees = set((SOURCES[sid].get('parametres') or {}))
    assert not ecarts - entrees, f"paramètres {sid} encodés sans source : {sorted(ecarts - entrees)}"
    assert not entrees - ecarts, f"entrées {sid} sans écart correspondant : {sorted(entrees - ecarts)}"


@_REGISTRE
@pytest.mark.parametrize('sid', PROGRAMMES_SOURCES)
def test_c_ecarts_sources_valent_les_arbitrages(sid):
    """Chaque entrée porte la valeur encodée (``retire`` : paramètre absent)."""
    scn = _a_plat(SCENARIOS[sid])
    for cle, entree in (SOURCES[sid].get('parametres') or {}).items():
        if entree.get('retire'):
            assert cle not in scn and entree.get('valeur') is None, (sid, cle)
        else:
            assert scn.get(cle) == entree['valeur'], (sid, cle, scn.get(cle), entree['valeur'])


@pytest.fixture
def pleine_precision(monkeypatch):
    """Comparer les trajectoires AVANT l'arrondi de sortie de l'orchestrateur (un
    écart de −0,002 point d'indice disparaît dans l'arrondi à 0,01 d'une colonne)."""
    import budget_simulator.engine.orchestrator as orchestrator
    monkeypatch.setattr(orchestrator, 'round', lambda x, n=None: x, raising=False)


def _trajectoires_identiques(a, b):
    (df_a, sec_a, _), (df_b, sec_b, _) = (
        BudgetSimulatorV45(periods=10, mesures=m).simulate() for m in (a, b))
    return df_a.equals(df_b) and sec_a.equals(sec_b)


@_SCENARIOS
def test_d1_omission_des_cles_retirees_desormais_neutre(pleine_precision):
    """v0.6.7 : l'artefact superprofits corrigé, omettre les deux clés retirées du RN
    (posées au droit voté : intensité 0 et 0 point) ne change plus rien, au bit.

    État de `taxe_superprofits` dans scenarios.json (vérifié le 07/10/2026) : 7
    scénarios à intensité 0 (plf_2026, rn, renaissance, horizons, lr, im_rabot,
    im_competitivite), 3 à intensité positive (lfi 1,0, ps 0,5, ecologistes 0,5).
    Si ce test rougit, un handler a de nouveau un effet à intensité nulle."""
    rn = SCENARIOS['rn_2027']
    omis = {k: v for k, v in rn.items() if k not in RN_CLES_RETIREES}
    assert _trajectoires_identiques(rn, omis)


@_SCENARIOS
def test_d2_omettre_une_cle_n_est_pas_poser_le_droit_vote(pleine_precision):
    """La règle « retirer = poser au droit en vigueur » reste nécessaire : `sante` du
    RN vaut le droit réajusté (efforts 15 / 20 / 10, franchises 120 depuis le
    08/11/2026), le défaut moteur vaut 0 / 0 / 0 — omettre la clé changerait la
    trajectoire."""
    from budget_simulator.config import load_default_values
    rn = SCENARIOS['rn_2027']
    assert rn['sante'] == DROIT_REAJUSTE['sante'] != load_default_values()['sante']
    from budget_simulator.engine.cadre import charger_droit_en_vigueur
    assert DROIT_REAJUSTE['sante'] != charger_droit_en_vigueur().mesures['sante']  # réajustement réel
    omis = {k: v for k, v in rn.items() if k != 'sante'}
    assert not _trajectoires_identiques(rn, omis)
