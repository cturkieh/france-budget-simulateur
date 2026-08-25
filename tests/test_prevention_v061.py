"""Tests-propriétés v0.6.1 — prévention santé (lot 4, items I19 à I21).

Ce que le lot corrige, et pourquoi c'est le DERNIER « repas gratuit » du
moteur :

- **I20 — plafond du taux de compensation.** La v0.5.1 écrivait
  ``roi_cumul = min(annees_roi * 0.25, 2.0)``, avec le commentaire
  « investissement gratuit! ». Sémantique réelle : à ``roi_cumul = 1`` l'euro
  dépensé est intégralement gagé ; à ``roi_cumul = 2`` la mesure **rapporte**
  autant qu'elle coûte, **chaque année, pour toujours**. Un curseur poussé à
  fond réduisait donc la dette. Aucune source ne l'autorise, et trois sources
  primaires l'interdisent :
  - **Cohen J.T., Neumann P.J., Weinstein M.C.**, « Does Preventive Care Save
    Money? Health Economics and the Presidential Candidates », *New England
    Journal of Medicine* 358(7):661-663, 14/02/2008, DOI
    10.1056/NEJMp0708558 — **19 %** seulement des interventions préventives
    sont *cost-saving* (599 études, ~1 500 ratios dont 279 préventifs), à
    peine plus que les traitements curatifs (18 %) ;
  - **van Baal P.H.M. et al.**, « Lifetime Medical Costs of Obesity :
    Prevention No Cure for Increasing Health Expenditure », *PLoS Medicine*
    5(2):e29, 05/02/2008 — « lifetime health expenditure was highest among
    healthy-living people » : le contre-effet des années de vie gagnées ;
  - **Vos T. et al.**, *ACE-Prevention Final Report*, University of
    Queensland / Deakin University, septembre 2010 — les **21 mesures
    dominantes sur 150** rapportent 11 Md AU$ pour 4,6 Md AU$ investis, soit
    un ratio de **2,4** : c'est la **borne haute absolue**, obtenue par
    sélection optimale et sur la vie entière, pas un rendement moyen ;
  - **OCDE**, *The Heavy Burden of Obesity — The Economics of Prevention*,
    2019, **chapitre 6** — la meilleure intervention chiffrée y vaut 13 Md USD
    PPA cumulés 2020-2050 sur 36 pays, soit ≈ **0,012 Md€ par pays et par
    an** : trois ordres de grandeur sous ce que le moteur produisait.

- **I19 — base et amplitude du curseur.** La base 5,0 Md€ du code ne
  correspond à aucune publication : la prévention institutionnelle française
  vaut **7,5 Md€** (DREES) et l'écart à la moyenne OCDE **+3,7 Md€/an**
  (OCDE). L'amplitude du curseur devient sourcée au lieu d'être juste par
  accident.

- **I21 — citations introuvables.** « IGAS 2023 » (ROI 25 %/an), « OMS 2018 »,
  « Lancet 2019 », « vaccins grippe ROI 1:4 » et « dépistages cancers ROI
  1:3 » n'existent pas sous ces références. Elles sont **retirées, pas
  réécrites** : sur un repo public AGPL, une citation fausse coûte plus cher
  qu'une absence de citation.

Sens de la correction (§ C.5 du dossier de sourcing) — il joue dans **un
seul** sens et doit être écrit comme tel : **CONTRE les programmes qui
investissent dans la prévention** (LFI, PS, Institut Montaigne
« compétitivité » dans les scénarios publiés). Le moteur leur offrait
jusqu'à 200 % de compensation récurrente ; il leur en offre désormais 50 % au
maximum, et jamais avant la cinquième année.

Ce que ce fichier NE prétend PAS établir (§ B.3-22 du dossier) : l'effet
budgétaire net d'un euro SUPPLÉMENTAIRE de prévention en France
**n'existe pas** dans la littérature — l'IGAS 2024 (Bras & Monasse) explique
pourquoi (« en l'absence d'une évaluation structurée en France de
l'efficacité et de l'efficience des actions de PPS »). Le plafond central de
0,50 est donc **un choix de modélisation assumé, borné par la littérature
internationale, jamais présenté comme sourcé**. Ce fichier verrouille ce que
les sources permettent d'affirmer : que le taux est **< 1**, qu'il est
**différé**, et qu'il **ne peut plus rendre la prévention gratuite**.
"""
import ast
import inspect
import json
import re
import textwrap
from pathlib import Path

import pytest

from budget_simulator import constants
from budget_simulator.config import load_default_values
from budget_simulator.constants import (
    DEPENSE_COURANTE_SANTE_MD_EUR,
    POLICY_START_YEAR,
    PREVENTION_BASE_MD_EUR,
    PREVENTION_OFFSET_CENTRAL_CAP,
    PREVENTION_OFFSET_HARD_CEILING,
    PREVENTION_OFFSET_LAG_YEARS,
    PREVENTION_OFFSET_RAMP_PER_YEAR,
    PREVENTION_PART_FRANCE,
    PREVENTION_PART_OCDE,
    PREVENTION_PLAFOND_MD_EUR,
)
from budget_simulator.simulator import BudgetSimulatorV45

_RACINE = Path(__file__).resolve().parent.parent
_PACKAGE = _RACINE / "budget_simulator"
# `.absolute()` et PAS `.resolve()` : `tests/` est un SYMLINK depuis le repo
# parent — resolve() retomberait toujours sur la racine du submodule, où
# `frontend-react/` n'existe pas (piège documenté dans
# `test_scenario_params_sync.py`, garde morte pendant des mois).
_RACINE_INVOCATION = Path(__file__).absolute().parents[1]
_SCENARIOS_JSON = _RACINE_INVOCATION / "frontend-react" / "src" / "data" / "scenarios.json"
_LEVER_META_JS = _RACINE_INVOCATION / "frontend-react" / "src" / "data" / "leverMeta.js"

#: Horizon publié du simulateur. Les propriétés « jamais gratuit » doivent
#: tenir au moins jusque-là ; le test de stress pousse à 2050.
ANNEE_HORIZON = 2035


def _delta_prevention(budget, year):
    """Surcoût budgétaire net du curseur prévention, en Md€ (>0 = ça coûte).

    Instance neuve à chaque appel : le gating one-time du Gini santé est un
    état d'instance, et le réutiliser d'une année à l'autre mesurerait autre
    chose que la brique visée.
    """
    params = {'prevention_budget': budget}
    sim = BudgetSimulatorV45(periods=10, mesures={'sante': params})
    _, _, impacts = sim._apply_sante({}, params, year, 3100, 0.015, 0.075)
    return impacts['prevention_budget']


def _taux_compensation(year, budget=None):
    """Taux de compensation effectif de l'année, mesuré sur le handler.

    Mesuré et non lu : c'est la grandeur que le lecteur voit (part de l'euro
    investi qui revient), et la seule dont les sources bornent la valeur.
    """
    budget = PREVENTION_PLAFOND_MD_EUR if budget is None else budget
    var = budget - PREVENTION_BASE_MD_EUR
    assert var > 0, "le taux n'est mesurable que sur un investissement non nul"
    return 1.0 - _delta_prevention(budget, year) / var


def _simuler(mesures=None, periods=10):
    sim = BudgetSimulatorV45(periods=periods, mesures=mesures or {})
    df, _, _ = sim.simulate()
    return df


def _budgets_du_domaine():
    """Les positions du curseur, bornes incluses (pas de 0,5 Md€)."""
    budgets = []
    valeur = PREVENTION_BASE_MD_EUR
    while valeur < PREVENTION_PLAFOND_MD_EUR:
        budgets.append(round(valeur, 2))
        valeur += 0.5
    budgets.append(PREVENTION_PLAFOND_MD_EUR)
    return budgets


_ANNEES_HORIZON = tuple(range(POLICY_START_YEAR, ANNEE_HORIZON + 1))


# ---------------------------------------------------------------------------
# 1. I20 — la prévention n'est plus jamais gratuite
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("budget", _budgets_du_domaine())
def test_prevention_never_free(budget):
    """Pour TOUTE position du curseur et TOUTE année de l'horizon publié, le
    surcoût reste positif ou nul.

    C'est la propriété que la v0.5.1 violait à partir de 2030 : investir dans
    la prévention faisait BAISSER la dépense publique, puis la dette. Une
    mesure de dépense ne peut pas se payer elle-même sans source, et les
    sources disent l'inverse (Cohen 2008 : 19 % seulement des interventions
    préventives sont cost-saving).
    """
    for year in _ANNEES_HORIZON:
        delta = _delta_prevention(budget, year)
        assert delta >= 0.0, (
            f"prévention gratuite en {year} pour un budget de {budget} Md€ : "
            f"delta = {delta:+.3f} Md€ (négatif = la mesure rapporte)"
        )


@pytest.mark.parametrize("budget", [b for b in _budgets_du_domaine()
                                    if b > PREVENTION_BASE_MD_EUR])
def test_prevention_coute_toujours_strictement(budget):
    """Contre-épreuve de `never_free` : le surcoût n'est pas seulement ≥ 0, il
    reste STRICTEMENT positif. Un plafond à 1,00 rendrait la mesure exactement
    gratuite — c'est déjà une affirmation qu'aucune source ne porte."""
    for year in _ANNEES_HORIZON:
        assert _delta_prevention(budget, year) > 0.0, (
            f"surcoût nul en {year} pour {budget} Md€ : l'euro préventif serait "
            "intégralement gagé, ce que la littérature ne permet pas d'affirmer"
        )


@pytest.mark.parametrize("year", list(range(POLICY_START_YEAR, 2051)))
def test_prevention_offset_bounded(year):
    """Le taux de compensation ne franchit JAMAIS le plafond dur, y compris en
    stress (horizon poussé à 2050, bien au-delà des 10 périodes publiées).

    La v0.5.1 atteignait 2,00 — le double du plafond dur — et continuait de
    l'appliquer chaque année indéfiniment.
    """
    taux = _taux_compensation(year)
    assert taux <= PREVENTION_OFFSET_HARD_CEILING + 1e-12, (
        f"taux de compensation {taux:.3f} en {year} > plafond dur "
        f"{PREVENTION_OFFSET_HARD_CEILING}"
    )
    assert taux >= 0.0, f"taux de compensation négatif ({taux:.3f}) en {year}"


@pytest.mark.parametrize("year", [2035, 2040, 2050])
def test_prevention_offset_sature_au_cap_central(year):
    """Passé la rampe, le taux se stabilise exactement au plafond central et
    n'en bouge plus : la rampe est bornée, pas seulement lente."""
    assert _taux_compensation(year) == pytest.approx(
        PREVENTION_OFFSET_CENTRAL_CAP, abs=1e-9)


def test_prevention_trajectoire_publiee():
    """Trajectoire de référence du dossier de sourcing, pour +3 Md€/an.

    | Année        | 2027 | 2029 | 2031 | 2033 | 2035 |
    | v0.5.1       | +2,25| 0,00 |−1,50 |−3,00 |−3,00 |
    | v0.6.1       | +3,00| +3,00| +2,40| +1,80| +1,50 |

    Lecture : +3 Md€/an de prévention **coûtent toujours** de l'argent public,
    mais coûtent **de moins en moins**. C'est le maximum que la littérature
    autorise, et c'est déjà généreux.
    """
    budget = PREVENTION_BASE_MD_EUR + 3.0
    attendu = {2027: 3.00, 2029: 3.00, 2031: 2.40, 2033: 1.80, 2035: 1.50}
    for year, cible in attendu.items():
        assert _delta_prevention(budget, year) == pytest.approx(cible, abs=1e-9), (
            f"trajectoire publiée non respectée en {year}"
        )


def test_prevention_delai_avant_tout_retour():
    """Aucun retour avant la 5e année (délai de 4 ans révolus).

    Le délai de 2 ans de la v0.5.1 est trop court : Cash & Fourcade 2023 § 45
    (« les bénéfices économiques de la prévention sont souvent postérieurs aux
    dépenses engagées ») et ACE-Prevention (14 % de la dépense décaissée en
    année 1) situent le retour bien plus loin.
    """
    premiere_annee_avec_effet = POLICY_START_YEAR + PREVENTION_OFFSET_LAG_YEARS
    for year in range(POLICY_START_YEAR, premiere_annee_avec_effet):
        assert _taux_compensation(year) == 0.0, (
            f"compensation non nulle en {year}, avant la fin du délai "
            f"de {PREVENTION_OFFSET_LAG_YEARS} ans"
        )
    assert _taux_compensation(premiere_annee_avec_effet) == pytest.approx(
        PREVENTION_OFFSET_RAMP_PER_YEAR, abs=1e-12), (
        "la rampe doit démarrer à sa valeur d'un an, ni à zéro (délai de 5 ans "
        "déguisé) ni à deux fois cette valeur (délai de 3 ans déguisé)"
    )


def test_prevention_rampe_lineaire_jusqu_au_cap():
    """La montée est linéaire à `RAMP_PER_YEAR` par an, puis plate.

    Forme fonctionnelle : aucune courbe de rendement décroissant n'est publiée
    (§ B.3-24). La rampe linéaire plafonnée est donc une CONVENTION assumée —
    ce test verrouille la convention, il ne la valide pas.
    """
    for year in range(POLICY_START_YEAR, 2051):
        avant, apres = _taux_compensation(year), _taux_compensation(year + 1)
        pas = apres - avant
        assert pas >= -1e-12, f"la compensation recule entre {year} et {year + 1}"
        assert pas <= PREVENTION_OFFSET_RAMP_PER_YEAR + 1e-12, (
            f"pas de {pas:.4f} entre {year} et {year + 1} : la rampe s'emballe"
        )
        # Sur la rampe elle-même (déjà démarrée, pas encore au plafond), le pas
        # vaut exactement `RAMP_PER_YEAR` : linéarité stricte. Le démarrage
        # (0 → RAMP) est verrouillé par `test_prevention_delai_avant_tout_retour`,
        # la saturation par `test_prevention_offset_sature_au_cap_central`.
        if avant > 0 and apres < PREVENTION_OFFSET_CENTRAL_CAP - 1e-12:
            assert pas == pytest.approx(PREVENTION_OFFSET_RAMP_PER_YEAR, abs=1e-12)


def test_prevention_statu_quo_strictement_inerte():
    """Curseur laissé sur la base : effet rigoureusement nul, toute année.

    Sans cette propriété, la correction de base (I19) déplacerait chaque
    scénario publié sans que personne ne l'ait décidé.
    """
    for year in range(POLICY_START_YEAR, 2051):
        assert _delta_prevention(PREVENTION_BASE_MD_EUR, year) == 0.0


@pytest.mark.parametrize("ecart", [0.5, 1.0, 2.0, 3.0, 3.663])
def test_prevention_symetrique(ecart):
    """Une COUPE de prévention est traitée exactement comme un investissement,
    au signe près.

    La v0.5.1 gatait le retour sur ``prevention_var > 0`` : une coupe rendait
    100 % de son montant en économie, pour toujours, sans aucun retour de
    dépense de santé. C'est la même classe de défaut que le fallback Gini
    ``if spending_impact > 0`` (§ C.4) : une asymétrie silencieuse qui
    avantage un seul bord — ici les programmes qui COUPENT la prévention. La
    même convention appliquée dans les deux sens ne prend pas parti.

    Effet numérique sur les scénarios publiés : NUL (la borne basse du curseur
    est la base elle-même, aucune coupe n'est atteignable par l'UI). C'est une
    garde de neutralité structurelle, pas un recalibrage.
    """
    for year in (2027, 2030, 2033, 2035, 2050):
        hausse = _delta_prevention(PREVENTION_BASE_MD_EUR + ecart, year)
        baisse = _delta_prevention(PREVENTION_BASE_MD_EUR - ecart, year)
        assert baisse == pytest.approx(-hausse, abs=1e-12), (
            f"asymétrie hausse/baisse en {year} : +{ecart} → {hausse:+.4f}, "
            f"−{ecart} → {baisse:+.4f}"
        )


@pytest.mark.parametrize("ecart", [0.5, 1.5, 2.5, 3.663])
def test_prevention_proportionnelle_au_montant(ecart):
    """Le surcoût est proportionnel au montant investi : le taux de
    compensation ne dépend QUE de l'année, jamais du montant.

    Un rendement dépendant du montant serait un rendement décroissant chiffré
    — or aucune courbe n'est publiée (§ B.3-24), et en inventer une déplacerait
    silencieusement les programmes les plus ambitieux.
    """
    for year in (2027, 2031, 2035, 2050):
        reference = _taux_compensation(year, PREVENTION_BASE_MD_EUR + 3.0)
        assert _taux_compensation(year, PREVENTION_BASE_MD_EUR + ecart) == \
            pytest.approx(reference, abs=1e-12)


# ---------------------------------------------------------------------------
# 2. I20 — la propriété macro : le curseur ne peut plus réduire la dette
# ---------------------------------------------------------------------------

def test_prevention_monotone():
    """Le curseur ne peut plus RÉDUIRE la dette : pour toute position et toute
    année, la dette reste au moins égale au statu quo.

    Propriété de bout en bout (simulation complète, tous canaux actifs), pas
    seulement sur le handler : c'est celle qu'un lecteur peut vérifier depuis
    l'interface. La v0.5.1 la violait franchement — +10 Md€/an de prévention
    réduisaient la dette 2035 d'environ 42 Md€.

    Formulation exacte : « jamais en dessous du statu quo », et non « croissante
    entre deux paliers voisins ». La différence n'est pas cosmétique — voir
    `test_seuil_impulsion_preexistant_reste_borne` : le moteur porte un seuil
    d'impulsion budgétaire PRÉ-EXISTANT qui rend la trajectoire de dette
    localement non monotone. Ce test dit ce que le lot garantit ; l'autre
    borne ce qu'il ne corrige pas.
    """
    reference = _simuler({'sante': {'prevention_budget': PREVENTION_BASE_MD_EUR}})
    statu_quo = reference['Dette/PIB %'].to_numpy()
    for budget in _budgets_du_domaine()[1:]:
        courant = _simuler({'sante': {'prevention_budget': budget}})['Dette/PIB %'].to_numpy()
        annees_fautives = [i for i, (a, b) in enumerate(zip(courant, statu_quo))
                           if a < b - 1e-9]
        assert not annees_fautives, (
            f"budget {budget} Md€ : la dette passe SOUS le statu quo aux indices "
            f"{annees_fautives} — la prévention redeviendrait un investissement "
            "qui se paie lui-même"
        )


@pytest.mark.parametrize("year", [2026, 2029, 2030, 2032, 2035, 2050])
def test_prevention_monotone_budgetaire(year):
    """Au niveau du handler — donc sans rétroaction macro — le surcoût est
    STRICTEMENT croissant avec le budget, toute année.

    C'est la propriété exacte que le lot câble ; la propriété de dette
    ci-dessus en est la conséquence macroéconomique, atténuée par le
    multiplicateur budgétaire (dépenser plus élève aussi le PIB, dénominateur
    du ratio).
    """
    budgets = _budgets_du_domaine()
    deltas = [_delta_prevention(b, year) for b in budgets]
    for (b1, d1), (b2, d2) in zip(zip(budgets, deltas), zip(budgets[1:], deltas[1:])):
        assert d2 > d1, (
            f"en {year}, passer de {b1} à {b2} Md€ de prévention ne coûte pas "
            f"davantage ({d1:+.4f} → {d2:+.4f} Md€)"
        )


def test_seuil_impulsion_preexistant_reste_borne():
    """Borne l'anomalie PRÉ-EXISTANTE qui empêche la monotonie stricte du ratio
    de dette entre deux positions voisines du curseur.

    Cause identifiée (et vérifiée sur les journaux de simulation) :
    `engine/growth.py` ne crée une impulsion budgétaire que si l'effort dépasse
    `0,1 % du PIB` — une règle À SEUIL, pas une transition continue. Un budget
    de prévention qui fait franchir ce seuil déclenche d'un coup le
    multiplicateur budgétaire, donc un peu de PIB, donc un ratio de dette plus
    bas qu'au palier précédent. Même classe d'artefact que le plancher
    monétaire accommodant documenté au lot 2 (v0.6.1, I6) : une non-linéarité
    du moteur RÉVÉLÉE par un lot, pas causée par lui — le curseur v0.5.1
    (0 → +3,0 Md€) se tenait déjà sur ce seuil.

    Ce test ne demande PAS que l'anomalie existe (elle disparaîtra si le seuil
    devient une transition continue) : il la BORNE, pour qu'aucune correction
    future ne puisse l'amplifier en silence.
    """
    trajectoires = {
        b: _simuler({'sante': {'prevention_budget': b}})['Dette/PIB %'].to_numpy()
        for b in _budgets_du_domaine()
    }
    budgets = sorted(trajectoires)
    pire = 0.0
    for i, bas in enumerate(budgets):
        for haut in budgets[i + 1:]:
            pire = min(pire, (trajectoires[haut] - trajectoires[bas]).min())
    assert pire > -1.0, (
        f"non-monotonie de {pire:.2f} pt de dette entre deux positions du "
        "curseur : au-delà de 1 pt, le seuil d'impulsion cesse d'être un "
        "artefact de second ordre et doit être traité (item v0.6.2)"
    )


def test_prevention_au_plafond_alourdit_la_dette():
    """Contre-épreuve de monotonie : la garde ne passe pas « par platitude ».

    Sans elle, un handler débranché (delta toujours nul) satisferait
    `test_prevention_monotone` sans rien mesurer.
    """
    base = _simuler({'sante': {'prevention_budget': PREVENTION_BASE_MD_EUR}})
    plafond = _simuler({'sante': {'prevention_budget': PREVENTION_PLAFOND_MD_EUR}})
    ecart_2035 = plafond['Dette/PIB %'].iloc[-1] - base['Dette/PIB %'].iloc[-1]
    assert ecart_2035 > 0.05, (
        f"le curseur poussé à fond ne déplace pas la dette ({ecart_2035:+.3f} pt) : "
        "la monotonie serait vraie par platitude"
    )


@pytest.mark.skipif(not _SCENARIOS_JSON.exists(),
                    reason="frontend-react/ hors périmètre fork moteur seul")
def test_curseur_ne_finance_aucun_scenario_publie():
    """Dans les scénarios RÉELLEMENT publiés — donc avec tous les autres
    leviers actifs, le clip 10 % PIB compris — pousser la prévention au
    plafond ne finance aucun programme.

    C'est la situation qu'un lecteur rencontre, et elle n'est PAS couverte par
    les tests standalone : dans un scénario combiné, le clip cumulatif et les
    règles à seuil du bloc macro peuvent changer le signe local d'un petit
    levier. Mesuré : 7 scénarios sur 9 voient leur dette 2035 MONTER
    (jusqu'à +2,57 pt), les 2 autres baissent de 0,02 et 0,23 pt — résidu du
    seuil d'impulsion décrit ci-dessus, pas un gain de la prévention.

    Contre-épreuve du rouge (rejouée en développement en réinjectant le modèle
    v0.5.1 — délai 2 ans, +25 pts/an, plafond 200 % — dans le handler) : 3
    scénarios sur 9 seulement montaient, et la pire baisse atteignait
    −0,79 pt. Le seuil de 7/9 discrimine donc bien les deux modèles.
    """
    scenarios = json.loads(_SCENARIOS_JSON.read_text(encoding="utf-8"))
    en_hausse, pire = 0, 0.0
    details = {}
    for sid, scenario in scenarios.items():
        mesures = scenario['apiMeasures']
        bas = {**mesures, 'sante': {**mesures['sante'],
                                    'prevention_budget': PREVENTION_BASE_MD_EUR}}
        haut = {**mesures, 'sante': {**mesures['sante'],
                                     'prevention_budget': PREVENTION_PLAFOND_MD_EUR}}
        ecart = (_simuler(haut)['Dette/PIB %'].to_numpy()
                 - _simuler(bas)['Dette/PIB %'].to_numpy())
        details[sid] = (round(float(ecart.min()), 3), round(float(ecart[-1]), 3))
        en_hausse += 1 if ecart[-1] > 0 else 0
        pire = min(pire, float(ecart.min()))
    assert pire > -0.5, (
        f"la prévention finance un scénario publié de {pire:.2f} pt de dette : "
        f"au-delà de 0,5 pt ce n'est plus un résidu de seuil. Détail : {details}"
    )
    assert en_hausse >= 7, (
        f"seulement {en_hausse} scénarios sur {len(scenarios)} voient leur dette "
        f"monter quand la prévention passe au plafond. Détail : {details}"
    )


def test_ancien_modele_produisait_bien_un_repas_gratuit():
    """Chiffre l'objet retiré, sans dépendre de l'ancien code.

    L'ancienne formule est ré-appliquée ICI (et nulle part ailleurs) pour
    mesurer l'écart de correction : en 2035, pour +3 Md€, elle rendait
    −3,00 Md€ (la mesure rapportait) là où le moteur inscrit désormais
    +1,50 Md€. Correction de 4,5 Md€/an CONTRE les programmes qui investissent
    dans la prévention — c'est le sens qui doit figurer au CHANGELOG.
    """
    var = 3.0
    ancien_roi_2035 = min((2035 - POLICY_START_YEAR) * 0.25, 2.0)
    ancien_delta_2035 = var - var * ancien_roi_2035
    assert ancien_delta_2035 == pytest.approx(-3.0)
    nouveau = _delta_prevention(PREVENTION_BASE_MD_EUR + var, 2035)
    assert nouveau - ancien_delta_2035 == pytest.approx(4.5, abs=1e-9)


# ---------------------------------------------------------------------------
# 3. I19 — base et amplitude sourcées
# ---------------------------------------------------------------------------

def test_base_prevention_coherente_avec_la_part_publiee():
    """La base 7,5 Md€ est confirmée par deux sources indépendantes, dans la
    même nomenclature SHA :

    - **DREES**, *Les dépenses de santé en 2023 — Résultats des comptes de la
      santé*, Panoramas édition 2024, **fiche 21, tableau 1** : prévention
      institutionnelle **7 516 M€ en 2023** ; édition 2025 : +0,9 % en 2024,
      soit ≈ 7,6 Md€ ;
    - **OCDE**, *Health at a Glance 2025 — Country note : France*, novembre
      2025 : « France spends **2.3 %** of total health spending on prevention
      […] less than the OECD average of **3.4 %** », soit 2,3 % × 333 Md€ de
      dépense courante de santé = **7,66 Md€**.

    Les deux chemins coïncident à 1 % près — c'est cette coïncidence qui rend
    la base SOLIDE, et le test la verrouille.
    """
    depuis_la_part = PREVENTION_PART_FRANCE * DEPENSE_COURANTE_SANTE_MD_EUR
    assert abs(depuis_la_part - PREVENTION_BASE_MD_EUR) / PREVENTION_BASE_MD_EUR < 0.03


def test_plafond_du_curseur_est_la_convergence_ocde():
    """Borne haute == base + écart à la moyenne OCDE, en constante unique.

    L'amplitude du curseur (0 → +3,7 Md€) devient ainsi **sourcée**, alors que
    l'amplitude de la v0.5.1 (0 → +3,0 Md€) l'était par accident.
    """
    ecart_ocde = (PREVENTION_PART_OCDE - PREVENTION_PART_FRANCE) * DEPENSE_COURANTE_SANTE_MD_EUR
    assert PREVENTION_PLAFOND_MD_EUR == pytest.approx(
        round(PREVENTION_BASE_MD_EUR + ecart_ocde, 1), abs=1e-9)
    assert ecart_ocde == pytest.approx(3.66, abs=0.02)


def test_defaut_moteur_egale_la_base():
    """Le statu quo du moteur EST la base : un utilisateur qui ne touche à rien
    ne doit pas décrire une coupe (ni un investissement) de prévention."""
    assert load_default_values()['sante']['prevention_budget'] == PREVENTION_BASE_MD_EUR


def test_domaine_ui_du_registre_moteur_suit_les_constantes():
    """`policy_measures.json` (registre servi à l'UI) est aligné sur les
    constantes : défaut = base, min = base, max = plafond.

    Sans ce verrou, la base peut être recalibrée côté moteur pendant que le
    curseur continue d'afficher l'ancienne échelle — exactement la dérive
    ×2 des tooltips retraites constatée le 04/08/2026.
    """
    registre = json.loads((_RACINE / "policy_measures.json").read_text(encoding="utf-8"))
    sante = next(m for m in registre['mesures'] if m['id'] == 'sante')
    param = sante['parametres']['prevention_budget']
    assert param['valeur_defaut'] == PREVENTION_BASE_MD_EUR
    assert param['min'] == PREVENTION_BASE_MD_EUR
    assert param['max'] == PREVENTION_PLAFOND_MD_EUR
    # Le pas doit permettre d'ATTEINDRE la borne haute, sinon la convergence
    # OCDE — la seule position sourcée du curseur — reste inaccessible.
    amplitude = PREVENTION_PLAFOND_MD_EUR - PREVENTION_BASE_MD_EUR
    quotient = amplitude / param['step']
    assert abs(quotient - round(quotient)) < 1e-6, (
        f"pas {param['step']} : la borne haute {PREVENTION_PLAFOND_MD_EUR} n'est "
        f"pas atteignable depuis {PREVENTION_BASE_MD_EUR}"
    )


@pytest.mark.skipif(not _LEVER_META_JS.exists(),
                    reason="frontend-react/ hors périmètre fork moteur seul")
def test_domaine_ui_frontend_suit_les_constantes():
    """Même verrou côté frontend (`leverMeta.js`) : c'est CE fichier que le
    curseur consomme, et c'est lui qui portait le tooltip « ROI 25 %/an …
    Source : IGAS 2023 »."""
    texte = _LEVER_META_JS.read_text(encoding="utf-8")
    bloc = re.search(r"prevention_budget:\s*\{(.*?)\n    \}", texte, re.S)
    assert bloc, "bloc `prevention_budget` introuvable dans leverMeta.js"
    corps = bloc.group(1)
    bornes = re.search(r"min:\s*([\d.]+),\s*max:\s*([\d.]+)", corps)
    assert bornes, f"bornes min/max illisibles dans le bloc : {corps[:200]}"
    assert float(bornes.group(1)) == PREVENTION_BASE_MD_EUR
    assert float(bornes.group(2)) == PREVENTION_PLAFOND_MD_EUR


@pytest.mark.skipif(not _SCENARIOS_JSON.exists(),
                    reason="frontend-react/ hors périmètre fork moteur seul")
def test_scenarios_publies_migres_sur_la_nouvelle_base():
    """Aucun scénario publié n'encode un budget INFÉRIEUR à la base.

    Garde de migration, et elle est indispensable : les scénarios encodaient
    des positions sur l'ancienne échelle (5 = statu quo). Laissées telles
    quelles après le passage de la base à 7,5, elles décriraient une COUPE de
    2,5 Md€/an de prévention dans les NEUF scénarios, y compris « la politique
    votée » — un artefact d'encodage à 2,5 Md€/an d'économies fictives. La
    migration est une translation qui PRÉSERVE le différentiel encodé (+0, +1,
    +2, +3), donc les résultats : elle ne recaractérise aucun programme.
    """
    scenarios = json.loads(_SCENARIOS_JSON.read_text(encoding="utf-8"))
    fautifs = {
        sid: mesures['sante']['prevention_budget']
        for sid, scenario in scenarios.items()
        if (mesures := scenario.get('apiMeasures', {})).get('sante', {}).get(
            'prevention_budget') is not None
        and mesures['sante']['prevention_budget'] < PREVENTION_BASE_MD_EUR
    }
    assert not fautifs, (
        "scénarios restés sur l'ancienne échelle (base 5,0) : "
        f"{fautifs} — ils décrivent une coupe de prévention non voulue. "
        f"Migration = +{PREVENTION_BASE_MD_EUR - 5.0} Md€ sur chaque valeur "
        "(le différentiel encodé est préservé, les résultats aussi)."
    )


# ---------------------------------------------------------------------------
# 4. Gardes de source (méta-gardes)
# ---------------------------------------------------------------------------

# Le fichier de garde cite lui-même les motifs qu'il traque (docstrings) :
# exclusion explicite et documentée, sans quoi le verrou se déclencherait sur
# sa propre justification.
_FICHIER_DE_GARDE = Path(__file__).name


def _fichiers_a_auditer():
    """Code du moteur + registre servi à l'UI + docs publiées + tests, hors
    fichier de garde.

    ``policy_measures.json`` est dans le périmètre parce qu'il porte les
    TOOLTIPS : c'est le texte qu'un citoyen lit à côté du curseur, et il
    citait « ROI 25 %/an … plafond 200 % après 8 ans ».
    """
    for chemin in (list(_PACKAGE.rglob("*.py"))
                   + [_RACINE / "policy_measures.json"]
                   + list((_RACINE / "docs").glob("*.md"))
                   + list((_RACINE / "tests").glob("*.py"))):
        if chemin.name != _FICHIER_DE_GARDE:
            yield chemin


#: Les citations « prévention » du code v0.5.1, toutes INTROUVABLES après
#: recherche exhaustive (§ I21 du dossier). Retirées, pas réécrites.
#:
#: `IGAS 2023` est traqué EN CONTEXTE de prévention seulement : le même
#: millésime est cité ailleurs dans METHODOLOGIE.md pour la convergence
#: tarifaire hôpital et les achats groupés — deux affirmations que ce lot n'a
#: PAS auditées. Les bannir au passage reviendrait à retirer une source sur la
#: foi d'une recherche qui ne portait pas sur elle.
_CITATIONS_INTROUVABLES = {
    "OMS 2018": r"OMS\s+2018",
    "Lancet 2019": r"Lancet\s+2019",
    "ROI 1:3 / 1:4 / 1:2-3 (dépistages, vaccins, diabète)": r"ROI\s*1\s*:\s*\d",
    "ROI prévention 25 %/an": r"ROI\s*:?\s*25\s*%\s*/?\s*an|ROI\s+25\s*%",
}


@pytest.mark.parametrize("libelle,motif", sorted(_CITATIONS_INTROUVABLES.items()))
def test_meta_garde_citations_prevention_introuvables(libelle, motif):
    """Aucune des citations introuvables ne subsiste dans le code, le registre
    servi à l'UI, les docs publiées ou les tests.

    PORTÉE / LIMITE : détection TEXTUELLE. Ce verrou empêche la réapparition
    des motifs connus ; il ne prouve pas qu'aucune autre citation fausse
    n'existe. C'est un cliquet, pas une preuve d'absence.

    Pourquoi ce niveau d'exigence : le repo est PUBLIC et sous AGPL, et un
    audit citoyen a déjà relevé des citations fausses. Une référence
    inexistante coûte plus cher à la crédibilité qu'une absence de référence.
    """
    compile_motif = re.compile(motif)
    fautifs = [
        str(c.relative_to(_RACINE)) for c in _fichiers_a_auditer()
        if compile_motif.search(c.read_text(encoding="utf-8"))
    ]
    assert not fautifs, f"citation introuvable « {libelle} » encore présente : {fautifs}"


#: Fenêtre de contexte, en LIGNES, autour d'une citation suspecte. Deux lignes
#: de part et d'autre = la puce et ses voisines immédiates ; au-delà, le
#: verrou attrape des sections voisines sans rapport (mesuré : à ±200
#: caractères, la citation « IGAS 2023 » de la convergence tarifaire hôpital
#: était flaguée à cause d'un « ROI prevention » situé dans le tableau du
#: chapitre précédent).
_FENETRE_CONTEXTE_LIGNES = 2
_CONTEXTE_PREVENTION = re.compile(r"pr[ée]vention|d[ée]pistage|vaccin", re.I)


def _citations_en_contexte_prevention(texte, motif):
    """Occurrences de `motif` dont le voisinage IMMÉDIAT parle de prévention."""
    lignes = texte.splitlines()
    trouvees = []
    for i, ligne in enumerate(lignes):
        if not motif.search(ligne):
            continue
        debut = max(0, i - _FENETRE_CONTEXTE_LIGNES)
        fin = min(len(lignes), i + _FENETRE_CONTEXTE_LIGNES + 1)
        if _CONTEXTE_PREVENTION.search("\n".join(lignes[debut:fin])):
            trouvees.append(i + 1)
    return trouvees


def test_meta_garde_igas_2023_plus_cite_pour_la_prevention():
    """« IGAS 2023 » ne sert plus de source à un chiffrage de PRÉVENTION.

    Les deux rapports IGAS 2024 sur la prévention ne publient **aucun ROI** et
    constatent au contraire l'absence d'évaluation d'efficience — la citation
    du code ne renvoyait à rien.

    PORTÉE : le verrou est CONTEXTUEL, à dessein. « IGAS 2023 » est aussi cité
    dans METHODOLOGIE.md pour la convergence tarifaire hôpital, les achats
    groupés et le plafond de fraude sociale recouvrable : trois affirmations
    que ce lot n'a PAS auditées. Les retirer au passage reviendrait à
    supprimer des sources sur la foi d'une recherche qui ne portait pas sur
    elles — l'exact symétrique de la faute qu'on corrige.
    """
    motif = re.compile(r"IGAS\s+2023")
    fautifs = [
        f"{chemin.relative_to(_RACINE)}:{ligne}"
        for chemin in _fichiers_a_auditer()
        for ligne in _citations_en_contexte_prevention(
            chemin.read_text(encoding="utf-8"), motif)
    ]
    assert not fautifs, (
        f"« IGAS 2023 » encore invoquée en contexte de prévention : {fautifs}"
    )


def test_meta_garde_investissement_gratuit_retire():
    """Le commentaire « investissement gratuit! » n'existe plus.

    Il documentait fidèlement ce que le code faisait : à partir de 2034, la
    mesure rapportait autant qu'elle coûtait. Sa disparition et celle du
    mécanisme vont ensemble.
    """
    motif = re.compile(r"investissement\s+gratuit", re.I)
    fautifs = [
        str(c.relative_to(_RACINE)) for c in _fichiers_a_auditer()
        if motif.search(c.read_text(encoding="utf-8"))
    ]
    assert not fautifs, f"« investissement gratuit » encore présent dans : {fautifs}"


def test_meta_garde_millesime_ocde_perime_retire():
    """Les parts « France 2 % / OCDE 2,8 % » du code datent d'un millésime OCDE
    2020 et sont fausses : *Health at a Glance 2025* publie **2,3 %** pour la
    France et **3,4 %** de moyenne OCDE. Retirées, pas recopiées.

    Le motif vise la forme EXACTE du code v0.5.1 (« ~2.8% », « ~2% depenses
    sante ») et non un « 2,8 » nu, qui sur-matcherait n'importe quel taux de
    la doc — le faux-vert par sur-matching prouvé en revue le 04/08/2026.
    """
    motif = re.compile(r"~\s*2[.,]8\s*%|~\s*2\s*%\s*d[ée]penses\s+sant[ée]", re.I)
    fautifs = [
        str(c.relative_to(_RACINE)) for c in _fichiers_a_auditer()
        if motif.search(c.read_text(encoding="utf-8"))
    ]
    assert not fautifs, f"millésime OCDE périmé (2,8 %) encore présent dans : {fautifs}"


def test_prevention_no_literal():
    """Aucun littéral de calibration prévention dans `_apply_sante` : la base,
    la rampe, le délai et les deux plafonds vivent tous dans `constants.py`.

    PORTÉE / LIMITE : détection SYNTAXIQUE (AST) sur les constantes littérales
    de la méthode. Elle bloque le mode de défaillance réel (recalibrage appliqué
    à moitié, code d'un côté et doc de l'autre) ; elle ne peut pas prouver
    qu'aucune valeur n'est reconstruite par un calcul.
    """
    from budget_simulator.handlers.depenses import DepensesMixin

    # Périmètre = le SEUL bloc prévention. `_apply_sante` porte aussi les trois
    # leviers d'efficience et les franchises, dont les littéraux (2.52, 0.93,
    # 2.0…) sont hors sujet ici : les inclure ferait échouer le test pour des
    # valeurs qu'aucun item du lot ne touche. Les bornes du bloc sont deux
    # commentaires de section ; si l'un disparaît, le test échoue bruyamment
    # (`StopIteration`) au lieu de passer sur un périmètre vide.
    lignes = inspect.getsource(DepensesMixin._apply_sante).splitlines()
    debut = next(i for i, l in enumerate(lignes) if "MESURE 2 : PRÉVENTION" in l)
    fin = next(i for i, l in enumerate(lignes[debut:], debut) if "=== TOTAL" in l)
    source = "\n".join(lignes[debut:fin])
    arbre = ast.parse(textwrap.dedent(source))
    litteraux = {
        noeud.value
        for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.Constant)
        and isinstance(noeud.value, (int, float))
        and not isinstance(noeud.value, bool)
    }
    interdits = {v for v in litteraux
                 if float(v) in {0.25, 2.0, 5.0, 7.5, 11.2, 0.5, 0.1}}
    assert not interdits, (
        f"littéraux de calibration prévention en dur dans _apply_sante : "
        f"{sorted(interdits)} — toute constante de calibration vit dans "
        "budget_simulator/constants.py"
    )
    for nom in ("PREVENTION_BASE_MD_EUR", "PREVENTION_OFFSET_CENTRAL_CAP",
                "PREVENTION_OFFSET_RAMP_PER_YEAR", "PREVENTION_OFFSET_LAG_YEARS"):
        assert nom in source, f"{nom} n'est pas consommée par le handler"


def test_constantes_prevention_dans_leur_domaine():
    """Garde de domaine sur les constantes elles-mêmes.

    Même philosophie que `GINI_SOFT_FLOOR < GINI_BASE < GINI_HARD_CEILING` :
    un recalibrage qui inverserait les bornes (cap central au-dessus du plafond
    dur, rampe négative) produirait une prévention gratuite sans qu'aucun test
    de trajectoire ne le voie sur l'horizon publié.
    """
    assert 0 < PREVENTION_OFFSET_CENTRAL_CAP <= PREVENTION_OFFSET_HARD_CEILING <= 1
    assert PREVENTION_OFFSET_RAMP_PER_YEAR > 0
    assert PREVENTION_OFFSET_LAG_YEARS >= 0
    assert PREVENTION_BASE_MD_EUR < PREVENTION_PLAFOND_MD_EUR
    with pytest.raises(ValueError):
        constants._valider_domaine_prevention(
            cap_central=1.5, plafond_dur=PREVENTION_OFFSET_HARD_CEILING,
            rampe=PREVENTION_OFFSET_RAMP_PER_YEAR, delai=PREVENTION_OFFSET_LAG_YEARS)


# ---------------------------------------------------------------------------
# 5. Ce que la doc publique DOIT dire (verrou CODE → DOC, sens humain)
# ---------------------------------------------------------------------------

def test_methodologie_declare_le_plafond_comme_choix_assume():
    """Le plafond central de 0,50 doit être présenté comme un CHOIX DE
    MODÉLISATION, jamais comme un chiffre sourcé (§ B.3-22).

    Aucune institution française ne publie l'effet budgétaire net d'un euro
    supplémentaire de prévention ; l'IGAS 2024 explique pourquoi. Le dire est
    la condition pour que le chiffre soit défendable.
    """
    texte = (_RACINE / "docs" / "METHODOLOGIE.md").read_text(encoding="utf-8")
    for attendu in ("choix de modelisation", "0,50", "IGAS 2024"):
        assert attendu in texte, f"METHODOLOGIE.md : « {attendu} » absent"


def test_methodologie_documente_les_deux_perimetres_de_prevention():
    """Les deux pièges de lecture de la base doivent être écrits :

    (a) la bosse Covid 2020-2022 (jusqu'à 16,5 Md€ en 2021 : tests, vaccins,
        masques) ne doit JAMAIS servir de base ;
    (b) le périmètre SHA « prévention institutionnelle » (7,5 Md€) exclut la
        prévention en consultation ordinaire, une grande partie de la
        vaccination et la prise en charge des facteurs de risque — en
        périmètre large, la Cour des comptes chiffre l'effort à ≈ 15 Md€/an.
        Le curseur pilote l'agrégat SHA, pas les 15.
    """
    texte = (_RACINE / "docs" / "METHODOLOGIE.md").read_text(encoding="utf-8")
    for attendu in ("16 515", "15 Md EUR", "SHA"):
        assert attendu in texte, f"METHODOLOGIE.md : piège de lecture « {attendu} » absent"
