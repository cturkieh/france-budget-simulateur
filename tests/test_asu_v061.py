"""Tests-propriétés v0.6.1 — Allocation sociale unique (lot 5, items I22 à I26).

Ce que le lot corrige, et pourquoi c'est le défaut de signe le plus lourd du
moteur : la v0.5.1 faisait de l'ASU une **machine à économies** (−11,5 Md€/an
à plein régime), alors que la **seule évaluation administrative** de la
réforme chiffre un effet budgétaire pérenne compris entre **0 et +2 Md€/an de
COÛT**.

Sources primaires (toutes recopiées dans ``constants.py`` avec leur URL) :

- **Assemblée nationale, commission des affaires sociales**, *Mission « flash »
  sur l'opportunité et les modalités de la création d'une allocation sociale
  unique*, rapporteures N. Colin-Oesterlé et S. Runel, **juillet 2025**,
  restituant les chiffrages **DREES + Igas, modèle Ines, juin 2024**. Trois
  faits y sont établis :
  1. le périmètre effectif est **RSA + prime d'activité + APL** (« revenu
     social de référence »), **les prestations familiales n'y sont pas** ;
  2. les scénarios chiffrés valent **0** (référence, à coût constant) ou
     **+2 Md€/an** (variantes) — **jamais une économie** ;
  3. le coût de transition est de **2 à 13,4 Md€ cumulés sur quatre ans**,
     **hors** hausse du taux de recours (**+2,4 Md€**, DGALN).
- **Cour des comptes**, *La prime d'activité*, communication au Sénat
  (art. 58-2° LOLF), **janvier 2026**, annexe au rapport d'information
  **Sénat n° 728 (2025-2026)** (MM. Bazin et Barros, 10/06/2026), chapitre
  « Le coût de la gestion par la CNAF », **p. 101-102** : la gestion de TOUTE
  la branche famille vaut ≈ **3 Md€**. Un `ECO_SIMPLIFICATION` de 6,0 Md€/an
  en représentait donc le **double**.
- **Cour des comptes**, *Certification des comptes du régime général…
  exercice 2024*, **mai 2025** : les 6,3 Md€ d'anomalies CAF à 24 mois sont
  une somme algébrique dont **30 à 36 % sont des RAPPELS dus aux
  allocataires** — les détecter **augmente** la dépense.
- **Cour des comptes 2026, chapitre 3** (« Des effets significatifs sur les
  revenus des ménages modestes **mais pas d'effets observables sur
  l'emploi** ») et **IPP**, *La réforme de 2019 de la prime d'activité*,
  **octobre 2023**, publiée par France Stratégie : **aucun effet emploi
  observable**, dans aucune sous-population.

Quatre citations du code sont **retirées, pas réécrites** (§ 6 du dossier de
sourcing) : « HCFPS 2024 » (**organisme inexistant** — les acronymes voisins
sont HCFiPS et HCFEA, et aucun ne publie ce chiffre), « médiane IFRAP »
(think tank auditionné comme partie prenante, réfuté au fond par la Cour),
« France Stratégie 2024 / 200 000 retours à l'emploi » (**introuvable, et
contresens** : ce que France Stratégie publie sur le sujet est précisément
l'étude IPP qui ne trouve AUCUN effet) et « OFCE 2019 » sur le non-recours.

Sens de la correction (§ C.5 du dossier) — il joue dans **un seul** sens et
doit être écrit comme tel : **CONTRE les programmes qui inscrivent l'ASU
comme gage d'économies** (dans les scénarios publiés : `lr_2027` et
`im_competitivite_2029`, tous deux à 70 % du SMIC). Le moteur leur offrait
jusqu'à 11,5 Md€/an d'économies récurrentes ; il ne leur offre plus que la
seule économie de gestion défendable (0,3 Md€/an), et leur facture le
surcoût pérenne et le coût de transition que les documents officiels
chiffrent.

Ce que ce fichier NE prétend PAS établir (§ B.3-25/26 du dossier) :
- l'**effet Gini** de l'ASU n'est publié par personne (les scénarios
  DREES/Igas donnent un **taux de pauvreté**). La conversion retenue est une
  **borne théorique déclarée**, pas une estimation — cf.
  `test_gini_est_une_borne_haute_declaree` ;
- les **économies de gestion** d'une unification : la mission parlementaire
  **déclare ne pas avoir pu les estimer** ; le 0,3 Md€/an est une
  **dérivation** encadrée par la gestion CNAF, jamais une estimation
  officielle.
"""
import ast
import inspect
import re
import textwrap
from pathlib import Path

import pytest

from budget_simulator import constants
from budget_simulator.constants import (
    ASU_COUT_RECOURS_MD_EUR,
    ASU_COUT_TRANSITION_PLAFOND_MD_EUR,
    ASU_COUT_TRANSITION_PLANCHER_MD_EUR,
    ASU_COUT_TRANSITION_RETENU_MD_EUR,
    ASU_ECO_SIMPLIFICATION_MD_EUR,
    ASU_EFFORT_PERENNE_MAX_MD_EUR,
    ASU_GESTION_CNAF_TOTALE_MD_EUR,
    ASU_GESTION_MOBILISABLE_MD_EUR,
    ASU_GINI_BORNE_PAR_MD_EUR,
    ASU_PERIMETRE_MD_EUR,
    ASU_PLAFONNEMENT_DEFAUT,
    ASU_PLAFONNEMENT_MAX,
    ASU_PLAFONNEMENT_MIN,
    ASU_TRANSITION_ANNEES,
    GINI_BASE,
    POLICY_START_YEAR,
    RDB_MENAGES_MD_EUR,
    asu_cout_transition_md_eur,
    asu_effort_perenne_md_eur,
)
from budget_simulator.handlers import depenses
from budget_simulator.handlers._phasing import asu_is_active, asu_phasing
from budget_simulator.simulator import BudgetSimulatorV45

_RACINE = Path(__file__).resolve().parent.parent
_DEPENSES_PY = _RACINE / "budget_simulator" / "handlers" / "depenses.py"

#: Horizon publié du simulateur.
ANNEE_HORIZON = 2035
_ANNEES_HORIZON = tuple(range(2025, ANNEE_HORIZON + 1))

#: Positions réellement atteignables depuis l'UI (leverMeta.js : pas de 0,05).
_POSITIONS_UI = (0.50, 0.55, 0.60, 0.65, 0.70)

#: Grille fine : l'API accepte n'importe quel réel du domaine, les propriétés
#: structurelles doivent tenir entre les crans du curseur aussi.
_GRILLE_FINE = tuple(round(ASU_PLAFONNEMENT_MIN + 0.005 * i, 3) for i in range(41))

_GDP, _INFLATION, _UNEMP = 3100.0, 0.015, 0.075


def _impacts(plafonnement, year, activation=1):
    """(delta_spending, delta_revenue, impacts) du handler ASU.

    Instance neuve à chaque appel : plusieurs handlers du moteur portent un
    gating one-time par état d'instance, et réutiliser une instance d'une
    année à l'autre mesurerait autre chose que la brique visée.
    """
    params = {'asu_activation': activation, 'asu_plafonnement': plafonnement}
    sim = BudgetSimulatorV45(periods=10, mesures={'asu': params})
    return sim._apply_asu({}, params, year, _GDP, _INFLATION, _UNEMP)


def _delta(plafonnement, year):
    return _impacts(plafonnement, year)[0]


def _simuler(mesures=None, periods=10):
    sim = BudgetSimulatorV45(periods=periods, mesures=mesures or {})
    df, _, _ = sim.simulate()
    return df


def _source_apply_asu() -> str:
    return textwrap.dedent(inspect.getsource(BudgetSimulatorV45._apply_asu))


def _extraire_bloc_asu(doc: str) -> str:
    """Puce ``asu`` d'un docstring de module + ses lignes de « Sources ».

    PORTÉE — les citations du bloc ASU vivent à TROIS endroits : la fonction
    ``_apply_asu``, la puce ``asu`` de l'inventaire en tête de module, et la
    ligne ASU de la table « Sources principales ». Purger l'un sans les
    autres laisse la citation fausse dans le repo public.

    CE QUE L'EXTRACTION EXCLUT DÉLIBÉRÉMENT, et c'est le point délicat : la
    puce ``prestations_indexation``, qui MENTIONNE l'ASU (elle décrit
    l'anti-double-comptage) mais décrit un AUTRE levier, dont l'assiette de
    90 Md€ n'est PAS auditée par ce lot. Un filtre naïf « toute ligne
    contenant ASU » l'y ferait entrer, ferait rougir les gardes de périmètre
    sur une valeur que le lot ne prétend pas corriger, et pousserait à
    maquiller la doc d'un levier voisin pour faire passer un test — ou, pire,
    rendrait le résultat dépendant de la façon dont les lignes sont coupées.
    Découpage par PUCE, donc, pas par ligne.
    """
    puces: list[list[str]] = []
    for ligne in doc.splitlines():
        if ligne.startswith('- '):
            puces.append([ligne])
        elif puces and ligne.startswith('  ') and ligne.strip():
            puces[-1].append(ligne)          # continuation de la puce courante
        else:
            puces.append([])                 # hors puce : coupe le rattachement
    retenues = []
    for puce in puces:
        if not puce:
            continue
        texte = "\n".join(puce)
        est_puce_de_handler = puce[0].startswith('- ``')
        if puce[0].startswith('- ``asu``'):
            retenues.append(texte)           # l'inventaire du handler ASU
        elif not est_puce_de_handler and 'ASU' in texte:
            retenues.append(texte)           # la ligne ASU des « Sources »
    return "\n".join(retenues)


def _bloc_asu_du_docstring_module() -> str:
    module = __import__(
        'budget_simulator.handlers.depenses', fromlist=['depenses'])
    return _extraire_bloc_asu(module.__doc__ or "")


def _texte_bloc_asu() -> str:
    """Tout ce qu'un lecteur associe au bloc ASU du moteur."""
    return _source_apply_asu() + "\n" + _bloc_asu_du_docstring_module()


def _section_asu_de_constants() -> str:
    """Bloc « CALIBRATION ALLOCATION SOCIALE UNIQUE » de ``constants.py``.

    Découpé sur les deux commentaires de section qui l'encadrent : si l'un
    disparaît, l'extraction lève au lieu de renvoyer silencieusement tout le
    fichier (un test de citation portant sur ~1 000 lignes de constantes
    passerait au vert sans rien mesurer — faux-vert de la même famille que
    ceux détectés au lot 4).
    """
    source = inspect.getsource(constants)
    debut = source.index("=== CALIBRATION ALLOCATION SOCIALE UNIQUE")
    fin = source.index("=== CALIBRATION ÉCONOMIQUE", debut)
    return source[debut:fin]


def _cite(texte: str, motif: str) -> bool:
    """Le motif apparaît-il (insensible à la casse) dans le texte ?"""
    return re.search(motif, texte, flags=re.IGNORECASE) is not None


# ---------------------------------------------------------------------------
# 1. I26 — le périmètre : 39 Md€, pas 90
# ---------------------------------------------------------------------------

def test_asu_perimetre():
    """La masse de référence du handler vaut 39 Md€ (constante unique).

    Test-propriété du dossier (§ I26). Mesuré sur la SORTIE du handler et pas
    sur la constante seule : la valeur doit être celle que le lecteur voit
    dans le libellé de la mesure, sinon le verrou est tautologique.
    """
    assert ASU_PERIMETRE_MD_EUR == 39.0
    _, _, impacts = _impacts(ASU_PLAFONNEMENT_DEFAUT, 2030)
    description = impacts['description']
    assert f"{ASU_PERIMETRE_MD_EUR:.0f}" in description, (
        f"le périmètre officiel doit être lisible dans le libellé publié : "
        f"{description!r}")


def test_asu_perimetre_exclut_les_prestations_familiales():
    """Les 52 Md€ d'« allocations familiales » du code ont DEUX défauts : le
    montant réel est 32,3 Md€, et surtout la réforme **ne les inclut pas**
    (position F. Lenglart et mission AN : « unifier […] et non pas les
    fusionner »). Ni la masse ni le libellé ne doivent survivre.
    """
    texte = _texte_bloc_asu()
    for interdit in (r"\b90\s*Md", r"\b52\b", r"[Aa]llocations familiales"):
        assert not _cite(texte, interdit), (
            f"le bloc ASU cite encore {interdit!r} : le périmètre officiel est "
            f"RSA + prime d'activité + APL, les prestations familiales sont "
            f"HORS réforme (AN, mission flash juillet 2025)")


def test_perimetre_est_un_libelle_pas_un_coefficient():
    """Le périmètre affiche, il ne multiplie rien.

    Le dossier de sourcing retient 39 Md€ là où la somme des trois lignes
    citées vaut 37,4 (RSA 11,97 + prime d'activité 10 + APL 15,4), et la
    réconciliation des 1,6 Md€ d'écart n'est publiée nulle part. Cet écart
    est signalé dans `constants.py` plutôt que comblé — et c'est tenable
    précisément parce que la constante n'entre dans AUCUN euro : la déplacer
    de 39 à 37,4 ne doit changer que le libellé lu par l'utilisateur.

    Sans ce verrou, un mainteneur pourrait un jour brancher le périmètre sur
    un calcul, et l'écart non réconcilié deviendrait silencieusement une
    erreur de chiffrage.
    """
    from unittest import mock
    reference = [_delta(p, y) for p in _POSITIONS_UI for y in _ANNEES_HORIZON]
    with mock.patch.object(depenses, 'ASU_PERIMETRE_MD_EUR', 37.4):
        modifie = [_delta(p, y) for p in _POSITIONS_UI for y in _ANNEES_HORIZON]
        _, _, impacts = _impacts(ASU_PLAFONNEMENT_DEFAUT, 2030)
    assert modifie == reference, (
        "le périmètre ASU pilote un montant : il doit rester un libellé")
    assert "37" in impacts['description'], (
        "le libellé doit au contraire suivre la constante")


def test_asu_perimetre_est_la_seule_masse_du_handler():
    """Aucune autre masse de prestations en dur dans ``_apply_asu``.

    Garde de source unique : si un mainteneur réintroduit « 13 + 10 + 15 »,
    le périmètre cesse d'être pilotable depuis ``constants.py``.
    """
    arbre = ast.parse(_source_apply_asu())
    litteraux = [n.value for n in ast.walk(arbre)
                 if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
                 and not isinstance(n.value, bool)]
    suspects = [v for v in litteraux if abs(v) >= 2.0]
    assert not suspects, (
        f"littéraux de calibration dans _apply_asu : {suspects} — toute masse "
        f"ou tout coefficient doit vivre dans constants.py (convention projet)")


# ---------------------------------------------------------------------------
# 2. I23 — l'économie de gestion : arithmétiquement bornée
# ---------------------------------------------------------------------------

def test_eco_simplification_sous_la_gestion_totale_de_la_branche():
    """6,0 Md€/an valait le DOUBLE de la gestion de toute la branche famille.

    C'est le cœur de I23 : même en supprimant intégralement la CNAF on
    n'économise que ≈ 3 Md€. La valeur retenue doit rester très en-dessous.
    """
    assert ASU_ECO_SIMPLIFICATION_MD_EUR < ASU_GESTION_CNAF_TOTALE_MD_EUR
    assert ASU_ECO_SIMPLIFICATION_MD_EUR <= ASU_GESTION_MOBILISABLE_MD_EUR
    assert ASU_GESTION_MOBILISABLE_MD_EUR <= ASU_GESTION_CNAF_TOTALE_MD_EUR


def test_garde_de_domaine_bloque_un_retour_du_6_md_eur():
    """Rouge automatisé : réinjecter 6,0 Md€ d'économie de gestion doit lever.

    Sans cette garde, un recalibrage pourrait rétablir en silence exactement
    l'impossibilité arithmétique que ce lot corrige.
    """
    with pytest.raises(ValueError, match="gestion"):
        constants._valider_domaine_asu(
            eco_simplification=6.0,
            mobilisable=ASU_GESTION_MOBILISABLE_MD_EUR,
            gestion_totale=ASU_GESTION_CNAF_TOTALE_MD_EUR,
            effort_max=ASU_EFFORT_PERENNE_MAX_MD_EUR,
            perimetre=ASU_PERIMETRE_MD_EUR,
            transition=ASU_COUT_TRANSITION_RETENU_MD_EUR,
            plancher=ASU_COUT_TRANSITION_PLANCHER_MD_EUR,
            plafond=ASU_COUT_TRANSITION_PLAFOND_MD_EUR,
        )


def test_garde_de_domaine_bloque_une_transition_hors_fourchette():
    """Le coût de transition retenu doit rester dans la fourchette publiée."""
    with pytest.raises(ValueError, match="transition"):
        constants._valider_domaine_asu(
            eco_simplification=ASU_ECO_SIMPLIFICATION_MD_EUR,
            mobilisable=ASU_GESTION_MOBILISABLE_MD_EUR,
            gestion_totale=ASU_GESTION_CNAF_TOTALE_MD_EUR,
            effort_max=ASU_EFFORT_PERENNE_MAX_MD_EUR,
            perimetre=ASU_PERIMETRE_MD_EUR,
            transition=0.0,
            plancher=ASU_COUT_TRANSITION_PLANCHER_MD_EUR,
            plafond=ASU_COUT_TRANSITION_PLAFOND_MD_EUR,
        )


# ---------------------------------------------------------------------------
# 3. I26 — le curseur pilote un EFFORT budgétaire, plus une économie
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("plafonnement,attendu", [
    (0.50, 0.0), (0.55, 0.5), (0.60, 1.0), (0.65, 1.5), (0.70, 2.0),
])
def test_effort_perenne_couvre_exactement_les_scenarios_officiels(plafonnement, attendu):
    """Le curseur balaie exactement l'amplitude chiffrée par la DREES/Igas :
    de la variante « à coût constant » (0) à la variante « +2 Md€ pérennes ».

    Un plafond plus GÉNÉREUX coûte plus cher : c'est le seul sens que la
    source autorise (les gagnants gagnent ce que l'effort finance).
    """
    assert asu_effort_perenne_md_eur(plafonnement) == pytest.approx(attendu)


@pytest.mark.parametrize("plafonnement", _GRILLE_FINE)
def test_effort_perenne_borne_et_positif(plafonnement):
    """Sur tout le domaine, l'effort reste dans [0 ; +2] Md€/an — jamais une
    économie de barème, ce qu'aucun scénario officiel ne produit."""
    effort = asu_effort_perenne_md_eur(plafonnement)
    assert 0.0 <= effort <= ASU_EFFORT_PERENNE_MAX_MD_EUR


@pytest.mark.parametrize("plafonnement", _GRILLE_FINE)
def test_effort_perenne_monotone(plafonnement):
    """Monotonie stricte : un plafond plus haut ne peut jamais coûter moins."""
    if plafonnement >= ASU_PLAFONNEMENT_MAX:
        return
    assert asu_effort_perenne_md_eur(plafonnement + 0.005) > \
        asu_effort_perenne_md_eur(plafonnement)


def test_effort_perenne_borne_hors_domaine():
    """Lecture défensive : une valeur hors domaine (API, scénario) est bornée,
    jamais extrapolée — l'amplitude publiée par la DREES/Igas s'arrête à
    +2 Md€/an."""
    assert asu_effort_perenne_md_eur(0.10) == 0.0
    assert asu_effort_perenne_md_eur(0.99) == ASU_EFFORT_PERENNE_MAX_MD_EUR


# ---------------------------------------------------------------------------
# 4. P1 du dossier — `test_asu_no_free_lunch`
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("year", _ANNEES_HORIZON)
def test_asu_no_free_lunch(year):
    """À coût budgétaire nul, l'ASU ne produit NI amélioration du Gini NI gain
    de pouvoir d'achat agrégé.

    Test-propriété du dossier (§ I26). Mécanisme : le scénario de référence
    DREES/Igas « à coût constant » compte **4,0 M de perdants pour 3,9 M de
    gagnants** — c'est un pur transfert entre ménages, dont l'effet agrégé
    est nul par construction. La v0.5.1 émettait au contraire un Gini
    amélioré et +0,3 % de pouvoir d'achat sans rien dépenser.
    """
    _, _, impacts = _impacts(ASU_PLAFONNEMENT_MIN, year)
    assert impacts.get('gini', 0.0) == 0.0, (
        f"Y{year}: Gini amélioré sans effort budgétaire — "
        f"{impacts.get('gini')!r}")
    # v0.6.3 : le pouvoir d'achat n'est plus nul à effort de barème nul —
    # mais il n'est PAS gratuit : c'est le recours résorbé (2,4 Md€/an,
    # DGALN), désormais FACTURÉ au budget de façon pérenne. La propriété
    # « no free lunch » devient : chaque point de PA est payé, au centime.
    ph = asu_phasing({'asu': {'asu_activation': 1}}, year)
    ph_prev = asu_phasing({'asu': {'asu_activation': 1}}, year - 1)
    attendu_pa = (ASU_COUT_RECOURS_MD_EUR / RDB_MENAGES_MD_EUR) * (ph - ph_prev)
    assert impacts.get('pouvoir_achat', 0.0) == pytest.approx(attendu_pa, abs=1e-12), (
        f"Y{year}: PA ≠ transfert de recours facturé — "
        f"{impacts.get('pouvoir_achat')!r}")


@pytest.mark.parametrize("plafonnement", _GRILLE_FINE)
def test_asu_ne_produit_jamais_plus_que_l_economie_de_gestion(plafonnement):
    """Borne dure : quelle que soit la position du curseur et l'année, l'ASU
    ne peut pas économiser plus que la seule économie défendable — celle de
    gestion (0,3 Md€/an à plein régime).

    C'est la contre-épreuve directe des −11,5 Md€/an de la v0.5.1. Depuis le
    lot 7, la borne qui MORD est plus stricte encore (zéro, cf. § 12) ;
    celle-ci reste comme mesure de la distance parcourue depuis la v0.5.1, et
    parce qu'elle balaie toutes les années, pas seulement le régime permanent.
    """
    for year in _ANNEES_HORIZON:
        delta = _delta(plafonnement, year)
        assert delta >= -ASU_ECO_SIMPLIFICATION_MD_EUR - 1e-9, (
            f"Y{year} à {plafonnement}: l'ASU économise {-delta:.2f} Md€, "
            f"au-delà de la seule économie sourcée "
            f"({ASU_ECO_SIMPLIFICATION_MD_EUR} Md€/an de gestion)")


def test_asu_a_plein_regime_ne_produit_aucune_economie_nette():
    """Chiffrage explicite de l'écart au modèle v0.5.1 (−11,5 Md€/an) : à
    l'année de plein régime, aucune position du curseur ne dégage la moindre
    économie nette.

    RECALIBRAGE ASSUMÉ (lot 7). Ce test bornait l'économie à 0,5 Md€/an, et
    c'était la bonne borne tant que le premier tiers du curseur en dégageait
    0,3 — un reliquat de « repas gratuit » que le lot 5 avait laissé passer
    parce qu'il était vingt fois plus petit que celui qu'il corrigeait. La
    borne est désormais ZÉRO, et elle est la traduction littérale de la
    source : la variante la moins coûteuse chiffrée par la DREES/Igas est « à
    coût constant ».
    """
    economies = [-_delta(p, 2032) for p in _GRILLE_FINE]
    assert max(economies) <= 1e-12, (
        f"économie maximale {max(economies):.3f} Md€/an — la réforme est "
        f"redevenue un gage d'économies")


# ---------------------------------------------------------------------------
# 5. P2 du dossier — `test_asu_gini_conditionne`
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("plafonnement", _GRILLE_FINE)
def test_asu_gini_conditionne(plafonnement):
    """`ΔGini < 0` IMPLIQUE `delta_spending >= 0`.

    Test-propriété du dossier (§ I26), énoncé littéral. L'amélioration des
    inégalités ne peut jamais être servie une année où la réforme rapporte de
    l'argent : le bénéfice se paie.
    """
    for year in _ANNEES_HORIZON:
        delta, _, impacts = _impacts(plafonnement, year)
        gini = impacts.get('gini', 0.0)
        if gini < 0:
            assert delta >= 0, (
                f"Y{year} à {plafonnement}: Gini amélioré ({gini:+.6f}) une "
                f"année où la réforme RAPPORTE {-delta:.2f} Md€ — "
                f"redistribution gratuite")


@pytest.mark.parametrize("plafonnement", _GRILLE_FINE)
def test_asu_gini_jamais_ameliore_sans_effort(plafonnement):
    """Formulation structurelle de la même propriété, sur la grandeur qui la
    porte réellement : l'amélioration est STRICTEMENT proportionnelle à
    l'effort pérenne, donc nulle dès que l'effort est nul."""
    effort = asu_effort_perenne_md_eur(plafonnement)
    for year in _ANNEES_HORIZON:
        gini = _impacts(plafonnement, year)[2].get('gini', 0.0)
        if effort == 0:
            assert gini == 0.0, f"Y{year}: Gini {gini:+.6f} sans effort"
        else:
            assert gini <= 0.0, (
                f"Y{year}: l'effort ne peut pas DÉGRADER le Gini ({gini:+.6f})")


@pytest.mark.parametrize("year", _ANNEES_HORIZON)
def test_gini_strictement_proportionnel_a_l_effort(year):
    """Le Gini est une fonction LINÉAIRE de l'effort, pas une marche d'escalier.

    La v0.5.1 procédait par paliers (``if plafonnement <= 0.55 … elif <= 0.65``)
    avec un terme de non-recours constant : deux positions voisines du curseur
    pouvaient donner le même Gini, et un plafond très bas améliorait le Gini
    sans rien dépenser. Ici le rapport Gini/effort est le MÊME partout — c'est
    la signature d'un canal qui n'a qu'un seul déterminant : ce qu'on dépense.
    """
    ratios = []
    for plafonnement in _POSITIONS_UI:
        effort = asu_effort_perenne_md_eur(plafonnement)
        if effort == 0:
            continue
        ratios.append(_impacts(plafonnement, year)[2].get('gini', 0.0) / effort)
    assert ratios
    assert max(ratios) - min(ratios) < 1e-12, (
        f"Y{year}: le Gini ne dépend pas linéairement de l'effort ({ratios})")


def test_gini_est_une_borne_haute_declaree():
    """Le coefficient Gini est une BORNE, pas une estimation (§ B.3-25).

    Aucune source ne publie l'effet Gini de l'ASU : la conversion retenue
    suppose que la totalité du transfert est reçue par le bas de la
    distribution (coefficient de concentration = −1), ce qui MAJORE l'effet.
    Le total accumulé sur l'horizon doit donc rester égal à cette borne, et
    rester minuscule au regard de l'indice publié.
    """
    borne = ASU_GINI_BORNE_PAR_MD_EUR * ASU_EFFORT_PERENNE_MAX_MD_EUR
    cumul = sum(_impacts(ASU_PLAFONNEMENT_MAX, y)[2].get('gini', 0.0)
                for y in range(2025, 2051))
    assert cumul == pytest.approx(-borne, rel=1e-9)
    assert abs(cumul) < 0.002, (
        f"effet Gini brut {cumul:+.5f} : 2 Md€ sur un revenu disponible de "
        f"{RDB_MENAGES_MD_EUR:.0f} Md€ ne peuvent pas déplacer l'indice de "
        f"plus de quelques dix-millièmes")


def test_gini_derive_de_deux_constantes_nommees():
    """La borne est DÉRIVÉE (Gini de base + revenu disponible), pas saisie.

    Deux moitiés, parce que l'égalité numérique seule serait un faux-vert :
    elle resterait vraie si un mainteneur remplaçait l'expression par le
    littéral qu'elle vaut aujourd'hui, et la borne cesserait alors de suivre
    un recalibrage de `GINI_BASE`. La seconde moitié lit donc la SOURCE de
    `constants.py` et vérifie que l'affectation est bien une expression
    citant les deux constantes.
    """
    assert ASU_GINI_BORNE_PAR_MD_EUR == pytest.approx(
        (1.0 + GINI_BASE) / RDB_MENAGES_MD_EUR)

    arbre = ast.parse(inspect.getsource(constants))
    affectations = [n for n in ast.walk(arbre)
                    if isinstance(n, ast.Assign)
                    and any(isinstance(c, ast.Name)
                            and c.id == 'ASU_GINI_BORNE_PAR_MD_EUR'
                            for c in n.targets)]
    assert len(affectations) == 1, "ASU_GINI_BORNE_PAR_MD_EUR affectée 0 ou 2 fois"
    noms = {n.id for n in ast.walk(affectations[0].value)
            if isinstance(n, ast.Name)}
    assert {'GINI_BASE', 'RDB_MENAGES_MD_EUR'} <= noms, (
        f"la borne Gini doit être DÉRIVÉE des deux constantes nommées, pas "
        f"saisie en dur (noms lus : {noms})")


# ---------------------------------------------------------------------------
# 6. Gini et pouvoir d'achat : effets de NIVEAU, pas de flux
# ---------------------------------------------------------------------------

def test_gini_et_pa_sont_des_niveaux_atteints_pendant_la_montee_en_charge():
    """Une réforme de barème déplace le niveau des transferts UNE FOIS ; elle
    ne réduit pas les inégalités un peu plus chaque année pour toujours.

    Le moteur cumule les impacts Gini (`gini_cible_cumul += …`) et multiplie
    l'indice de pouvoir d'achat (`purchasing_power *= …`) : émettre le même
    delta chaque année en ferait un flux composé. Les deux canaux émettent
    donc l'INCRÉMENT de montée en charge, dont la somme vaut exactement le
    niveau — et zéro une fois le régime permanent atteint.
    """
    annees_regime = [y for y in range(2030, 2051)]
    for year in annees_regime:
        impacts = _impacts(ASU_PLAFONNEMENT_MAX, year)[2]
        assert impacts.get('gini', 0.0) == 0.0, f"Y{year}: Gini encore en flux"
        assert impacts.get('pouvoir_achat', 0.0) == 0.0, (
            f"Y{year}: pouvoir d'achat encore en flux")


def test_pouvoir_achat_egale_l_effort_rapporte_au_revenu_disponible():
    """`pouvoir_achat ≈ effort budgétaire / RDB` (§ I26).

    Dérivation DREES/Igas : 4,6 M de gagnants à +110 €/mois moins 2,9 M de
    perdants à −110 €/mois ≈ +2,3 Md€ nets — c'est-à-dire l'effort budgétaire
    lui-même. Le moteur annonçait +0,3 %, soit plus du double, et sans le
    dépenser.
    """
    for plafonnement in _POSITIONS_UI:
        effort = asu_effort_perenne_md_eur(plafonnement)
        cumul = sum(_impacts(plafonnement, y)[2].get('pouvoir_achat', 0.0)
                    for y in range(2025, 2051))
        # v0.6.3 : + le recours résorbé (2,4 Md€/an), transfert aux ménages
        # au même titre que l'effort de barème — et facturé au budget.
        assert cumul == pytest.approx(
            (effort + ASU_COUT_RECOURS_MD_EUR) / RDB_MENAGES_MD_EUR, rel=1e-9)


def test_pouvoir_achat_maximal_reste_sous_quatre_dixiemes_de_point():
    """Ordre de grandeur publiable : même à +2 Md€/an de barème + 2,4 Md€/an
    de recours résorbé (v0.6.3), le gain de pouvoir d'achat agrégé reste sous
    +0,4 % ((2,0 + 2,4)/1380 ≈ +0,32 % — l'ancienne borne 0,2 % datait du
    monde sans recours pérenne, re-déclarée en acte le 30/08/2026)."""
    cumul = sum(_impacts(ASU_PLAFONNEMENT_MAX, y)[2].get('pouvoir_achat', 0.0)
                for y in range(2025, 2051))
    assert 0.0 < cumul < 0.004


# ---------------------------------------------------------------------------
# 7. P4 du dossier — `test_asu_transition`
# ---------------------------------------------------------------------------

def test_asu_transition():
    """Les 4 premières années portent un coût cumulé ∈ [2 ; 13,4] Md€.

    Test-propriété du dossier (§ I26). Fourchette officielle : « un coût
    cumulé de 2 à 13,4 milliards d'euros [sur quatre ans] » (AN, juillet
    2025). La v0.5.1 ne portait que 0,5 Md€ en 2026, et rien ensuite.
    """
    annees = range(POLICY_START_YEAR, POLICY_START_YEAR + ASU_TRANSITION_ANNEES)
    cumul = sum(asu_cout_transition_md_eur(y) for y in annees)
    assert ASU_COUT_TRANSITION_PLANCHER_MD_EUR <= cumul <= ASU_COUT_TRANSITION_PLAFOND_MD_EUR


@pytest.mark.parametrize("plafonnement", _POSITIONS_UI)
def test_cout_total_des_quatre_premieres_annees_dans_la_fourchette(plafonnement):
    """Contre-épreuve sur le handler complet (transition + effort pérenne −
    économie de gestion) : quelle que soit la position du curseur, la facture
    des quatre premières années reste dans l'enveloppe officielle."""
    annees = range(POLICY_START_YEAR, POLICY_START_YEAR + ASU_TRANSITION_ANNEES)
    cumul = sum(_delta(plafonnement, y) for y in annees)
    assert ASU_COUT_TRANSITION_PLANCHER_MD_EUR <= cumul <= ASU_COUT_TRANSITION_PLAFOND_MD_EUR, (
        f"facture des 4 premières années : {cumul:.2f} Md€ à {plafonnement}")


def test_le_recours_est_facture_en_perenne_pas_en_blip():
    """v0.6.3 : la hausse du recours (2,4 Md€/an, DGALN) est une charge
    PÉRENNE qui monte avec le phasing — plus un blip de transition. L'ancien
    rattachement (0,6 Md€/an × 4 ans puis zéro) n'était soutenu par aucune
    source : une réforme dont l'objet est de résorber le non-recours ne
    cesse pas de le payer en année 5. L'enveloppe de transition, elle,
    revient au plancher officiel seul (2 Md€ cumulés)."""
    annees = range(POLICY_START_YEAR, POLICY_START_YEAR + ASU_TRANSITION_ANNEES)
    cumul_transition = sum(asu_cout_transition_md_eur(y) for y in annees)
    assert cumul_transition == pytest.approx(ASU_COUT_TRANSITION_RETENU_MD_EUR)
    # En régime (transition finie, phasing 1,0), le handler facture toujours
    # le recours : delta = solde pérenne + 2,4, à chaque année, pour toujours.
    for year in (2030, 2035, 2050):
        attendu = (constants.asu_solde_perenne_md_eur(ASU_PLAFONNEMENT_MIN)
                   + ASU_COUT_RECOURS_MD_EUR)
        assert _delta(ASU_PLAFONNEMENT_MIN, year) == pytest.approx(attendu, abs=1e-12), (
            f"Y{year}: le recours a cessé d'être payé")


@pytest.mark.parametrize("year", range(POLICY_START_YEAR,
                                       POLICY_START_YEAR + ASU_TRANSITION_ANNEES))
def test_transition_uniforme_sur_quatre_ans(year):
    """Profil UNIFORME : SIMPLIFICATION ASSUMÉE (v0.6.3 — la justification
    antérieure « la source ne publie jamais de profil annuel » était fausse,
    le rapport de la mission flash contient la table des profils ; cf.
    constants.py, choix (b)). L'enveloppe ne porte plus que le plancher
    officiel : le recours est parti en charge pérenne."""
    attendu = ASU_COUT_TRANSITION_RETENU_MD_EUR / ASU_TRANSITION_ANNEES
    assert asu_cout_transition_md_eur(year) == pytest.approx(attendu)


@pytest.mark.parametrize("year", [2025, 2030, 2035, 2050])
def test_transition_bornee_dans_le_temps(year):
    """Hors des quatre années de montée en charge : aucun coût de transition
    (avant l'entrée en vigueur comme après)."""
    assert asu_cout_transition_md_eur(year) == 0.0


# ---------------------------------------------------------------------------
# 8. I25 — aucun effet emploi, aucune compétitivité
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("plafonnement", _POSITIONS_UI)
def test_aucun_effet_emploi_emis(plafonnement):
    """« La réforme de 2019 de la prime d'activité n'a pas eu d'effets
    observables sur l'emploi » (IPP octobre 2023, étude commandée par la Cour
    des comptes, publiée par France Stratégie ; reprise par la Cour 2026,
    chapitre 3). Un dispositif de 10,6 Md€ et 4,81 M de bénéficiaires ne
    produit aucun effet emploi mesurable : il est exclu qu'une refonte de
    barèmes en produise un.
    """
    for year in _ANNEES_HORIZON:
        impacts = _impacts(plafonnement, year)[2]
        assert 'chomage' not in impacts, (
            f"Y{year}: canal chômage réintroduit ({impacts.get('chomage')!r})")


@pytest.mark.parametrize("plafonnement", _POSITIONS_UI)
def test_aucun_effet_competitivite_emis(plafonnement):
    """Aucune source ne chiffre un effet de compétitivité d'une unification
    des minima sociaux (§ I26). Le canal est retiré, pas mis à zéro par un
    coefficient inventé."""
    for year in _ANNEES_HORIZON:
        impacts = _impacts(plafonnement, year)[2]
        assert 'competitivite' not in impacts, (
            f"Y{year}: canal compétitivité réintroduit")


def _cles_ecrites_par_apply_asu() -> set[str]:
    """Clés littérales du dict d'impacts ÉCRITES par ``_apply_asu`` (AST).

    Couvre les deux formes : le dict littéral de construction et les
    affectations par indice ``impacts['x'] = …``. Analyse syntaxique et non
    textuelle : un commentaire qui NOMME une clé retirée (« pas de clé
    'chomage' : cf. IPP 2023 ») ne doit évidemment pas être compté comme une
    réintroduction — c'est même exactement la documentation qu'on veut.
    """
    arbre = ast.parse(_source_apply_asu())
    cles: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Dict):
            cles |= {c.value for c in noeud.keys
                     if isinstance(c, ast.Constant) and isinstance(c.value, str)}
        if isinstance(noeud, ast.Assign):
            for cible in noeud.targets:
                if isinstance(cible, ast.Subscript) and \
                        isinstance(cible.slice, ast.Constant) and \
                        isinstance(cible.slice.value, str):
                    cles.add(cible.slice.value)
    return cles


def test_meta_garde_aucun_canal_emploi_dans_la_source():
    """Garde structurelle (et non seulement comportementale) : les clés
    `chomage` et `competitivite` ne peuvent pas réapparaître dans le bloc ASU
    sans une source qui les porte.

    PORTÉE / LIMITE : détection SYNTAXIQUE sur l'AST du handler — elle prouve
    qu'aucune écriture directe n'est présente, pas qu'aucun effet n'existe
    (même convention que `test_mixin_architecture.py`).
    """
    cles = _cles_ecrites_par_apply_asu()
    assert 'chomage' not in cles, (
        "canal chômage réintroduit dans _apply_asu — la Cour 2026 ch. 3 et "
        "l'IPP 2023 établissent l'absence d'effet emploi observable")
    assert 'competitivite' not in cles, (
        "canal compétitivité réintroduit dans _apply_asu — aucune source ne "
        "chiffre cet effet")
    assert {'depenses', 'gini', 'pouvoir_achat'} <= cles, (
        f"le handler doit toujours écrire ses trois canaux réels : {cles}")


def test_meta_garde_cles_detecte_bien_une_reintroduction():
    """Rouge automatisé de la garde ci-dessus : appliquée à un handler qui
    réécrit `impacts['chomage']`, l'extraction DOIT la voir. Sans cette
    contre-épreuve, un extracteur trop étroit passerait vert sans mesurer."""
    faux = ("def f():\n"
            "    impacts = {'depenses': 0.0}\n"
            "    impacts['chomage'] = -0.1\n")
    arbre = ast.parse(faux)
    cles = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Dict):
            cles |= {c.value for c in noeud.keys
                     if isinstance(c, ast.Constant) and isinstance(c.value, str)}
        if isinstance(noeud, ast.Assign):
            for cible in noeud.targets:
                if isinstance(cible, ast.Subscript) and \
                        isinstance(cible.slice, ast.Constant) and \
                        isinstance(cible.slice.value, str):
                    cles.add(cible.slice.value)
    assert cles == {'depenses', 'chomage'}


# ---------------------------------------------------------------------------
# 9. I21/I25 — les citations introuvables sont RETIRÉES, pas réécrites
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("motif,raison", [
    (r"HCFPS", "organisme INEXISTANT (les acronymes voisins sont HCFiPS et "
               "HCFEA, et aucun des deux ne publie ce chiffre)"),
    (r"IFRAP", "note de think tank auditionnée comme partie prenante, réfutée "
               "au fond par la Cour des comptes (gestion CNAF totale = 3 Md€)"),
    (r"France Strat[ée]gie 2024", "introuvable — et contresens : ce que France "
                                  "Stratégie publie est l'étude IPP qui ne "
                                  "trouve AUCUN effet emploi"),
    (r"OFCE 2019", "introuvable (§ B.3-31 du dossier de sourcing)"),
    (r"n.\s*692", "référence parlementaire non vérifiée ; le document à jour "
                  "est la mission flash de juillet 2025"),
    (r"200\s*k|200 000 retours", "chiffre introuvable, contredit par l'IPP"),
])
def test_meta_garde_citations_retirees_du_bloc_asu(motif, raison):
    """Aucune des citations introuvables du bloc ASU ne survit.

    Garde CONTEXTUELLE (bloc ASU seulement) et c'est délibéré : « HCFPS » et
    « France Stratégie 2024 » restent cités ailleurs dans le moteur, pour des
    affirmations que CE lot n'a pas auditées. Les bannir au passage serait la
    faute symétrique de celle qu'on corrige.
    """
    assert not _cite(_texte_bloc_asu(), motif), (
        f"le bloc ASU cite encore {motif!r} — {raison}")


_DOC_SYNTHETIQUE = """En-tete.

Mesures couvertes :
- ``asu`` : Allocation Sociale Unique. Sources: IFRAP 2025, HCFPS 2024.
  Suite de la puce ASU, sur une ligne de continuation.
- ``prestations_indexation`` : base 90 Md EUR d'allocations familiales.
  Neutralise quand l'ASU est active (anti-double-comptage).

Sources principales :
- Un organisme, une date — ASU.
- Une autre source — retraites.
"""


def test_extracteur_prend_la_puce_asu_et_pas_celle_du_voisin():
    """Contre-épreuve de l'extracteur, sur les DEUX faces.

    Face 1 (sinon la garde ne mesure rien) : la puce ASU et sa ligne de
    « Sources principales » sont bien capturées, continuations comprises.
    Face 2 (sinon la garde mesure trop) : la puce ``prestations_indexation``
    est exclue MÊME quand elle mentionne l'ASU — c'est un autre levier, dont
    l'assiette de 90 Md€ n'est pas auditée par ce lot. Sans cette moitié, le
    seul moyen de faire passer les gardes de périmètre serait de retoucher la
    doc d'un levier voisin, ce qui n'aurait rien corrigé du tout.
    """
    bloc = _extraire_bloc_asu(_DOC_SYNTHETIQUE)
    assert _cite(bloc, r"IFRAP")
    assert _cite(bloc, r"HCFPS")
    assert _cite(bloc, r"ligne de continuation")
    assert _cite(bloc, r"Un organisme, une date")
    assert not _cite(bloc, r"90 Md")
    assert not _cite(bloc, r"prestations_indexation")
    assert not _cite(bloc, r"retraites")


def test_meta_garde_detecte_bien_l_ancienne_ligne():
    """Rouge automatisé de la garde ci-dessus : appliquée au texte de la
    v0.5.1, elle DOIT flaguer. Sans cette contre-épreuve, un motif mal écrit
    passerait vert sans rien mesurer (faux-vert détecté au lot 4)."""
    ancien = ("        - Doublons CAF/regions/urbanisme: +1.5 Md EUR (HCFPS 2024)\n"
              "        Sources: IFRAP 2025, HCFPS 2024, AN Rapport n 692\n"
              "        # Source: France Strategie 2024, 200k retours emploi\n")
    for motif in (r"HCFPS", r"IFRAP", r"France Strat[ée]gie 2024",
                  r"n.\s*692", r"200\s*k"):
        assert _cite(ancien, motif), f"motif {motif!r} inopérant"


def test_citations_de_remplacement_presentes():
    """Ce qui remplace les citations retirées doit être vérifiable : la source
    pivot (mission flash AN de juillet 2025, chiffrages DREES/Igas) et la
    source qui ferme le canal emploi (Cour 2026 ch. 3 / IPP octobre 2023).

    Scopé au bloc ASU + à la SEULE section ASU de ``constants.py`` : sur le
    fichier de constantes entier, « DREES » ou « Cour des comptes » sont cités
    par une dizaine d'autres lots et le test passerait au vert même si le bloc
    ASU était vide de toute source.
    """
    texte = _texte_bloc_asu() + _section_asu_de_constants()
    for motif in (r"DREES", r"Igas", r"Cour des comptes", r"IPP",
                  r"juillet 2025", r"octobre 2023"):
        assert _cite(texte, motif), f"source de remplacement absente : {motif!r}"


def test_chaque_source_de_remplacement_porte_une_url_verifiable():
    """Un auditeur externe doit pouvoir remonter à la source en un clic.

    Les trois documents qui portent le nouveau chiffrage (mission flash AN,
    communication de la Cour au Sénat, certification des comptes) et l'étude
    IPP sont cités avec leur URL dans la section ASU de ``constants.py``.
    """
    section = _section_asu_de_constants()
    for hote in ("assemblee-nationale.fr", "senat.fr", "ccomptes.fr",
                 "strategie-plan.gouv.fr"):
        assert hote in section, f"URL primaire absente du bloc ASU : {hote}"


# ---------------------------------------------------------------------------
# 10. Contrat `asu_phasing` — préservé (mémoire projet : anti-double-comptage)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("year,attendu", [
    (2025, 0.0), (2026, 0.25), (2027, 0.50), (2028, 0.75),
    (2029, 1.00), (2034, 1.00),
])
def test_le_handler_consomme_toujours_asu_phasing(year, attendu):
    """La montée en charge du handler EST celle de `asu_phasing`.

    Contre-épreuve COMPORTEMENTALE (pas un grep) : la part pérenne du delta
    doit valoir exactement `phasing × (effort − économie de gestion)`. Si un
    mainteneur ré-inlinait un calendrier local, l'anti-double-comptage
    ASU ↔ fraude sociale (source unique `_phasing.asu_phasing`) se
    désynchroniserait en silence.
    """
    assert asu_phasing({'asu': {'asu_activation': 1}}, year) == attendu
    perenne = _delta(ASU_PLAFONNEMENT_MAX, year) - asu_cout_transition_md_eur(year)
    # v0.6.3 : la part pérenne porte aussi le recours résorbé (2,4 Md€/an),
    # sur le MÊME calendrier asu_phasing — c'est précisément l'objet du test.
    attendu_perenne = attendu * (
        asu_effort_perenne_md_eur(ASU_PLAFONNEMENT_MAX)
        - ASU_ECO_SIMPLIFICATION_MD_EUR
        + ASU_COUT_RECOURS_MD_EUR)
    assert perenne == pytest.approx(attendu_perenne, rel=1e-9)


def test_interaction_anti_double_comptage_fraude_toujours_effective():
    """Non-régression du contrat de la Phase 2 (option A) : ASU active →
    économies de fraude sociale strictement réduites. Le lot 5 ne doit pas
    casser ce câblage en retirant `ECO_FRAUDE_STRUCT`."""
    def _fraude(mesures):
        sim = BudgetSimulatorV45(periods=10, mesures=mesures)
        return sim._apply_fraude_sociale(
            {}, mesures['fraude_sociale'], 2030, _GDP, _INFLATION, _UNEMP)[0]

    sans = _fraude({'fraude_sociale': {'effort': 1.0}})
    avec = _fraude({'fraude_sociale': {'effort': 1.0},
                    'asu': {'asu_activation': 1}})
    assert avec > sans, (
        "l'ASU doit toujours réduire le potentiel de fraude sociale "
        "(anti-double-comptage, option A)")


def test_le_double_comptage_fraude_n_est_plus_compte_deux_fois_dans_l_asu():
    """I24 : `ECO_FRAUDE_STRUCT = 2,0` retiré du handler.

    Les 6,3 Md€ d'anomalies CAF à 24 mois sont une somme algébrique dont
    **30 à 36 % sont des RAPPELS dus aux allocataires** (Cour, certification
    2024) : les détecter AUGMENTE la dépense. Le résidu de fraude qualifiée
    est déjà porté par le curseur « Fraude sociale ».
    """
    texte = _texte_bloc_asu()
    assert not _cite(texte, r"ECO_FRAUDE_STRUCT")
    # (?<!v0\.) : le garde vise le chiffre CAF « 6,3 Md€ », pas les
    # étiquettes de version « v0.6.3 » apparues avec la passe du 30/08.
    assert not _cite(texte, r"(?<!v0\.)6[.,]3")


def test_prestations_indexation_toujours_neutralise_par_l_asu():
    """Le périmètre passe de 90 à 39 Md€, mais la neutralisation de
    `prestations_indexation` reste TOTALE — et c'est un choix conservateur
    assumé, pas un oubli.

    Le périmètre ASU (39 Md€) est un SOUS-ENSEMBLE de la base 90 Md€ du
    levier d'indexation, dont la composition (52 Md€ d'« allocations
    familiales » là où les prestations familiales valent 32,3 Md€) n'est PAS
    auditée par ce lot. Neutraliser en totalité ne peut qu'ÔTER des économies
    à un programme qui cumule les deux leviers : l'erreur, s'il y en a une,
    joue contre le programme, jamais en sa faveur. Re-baser le levier
    d'indexation est un chantier à part entière.
    """
    sim = BudgetSimulatorV45(periods=10, mesures={
        'asu': {'asu_activation': 1},
        'prestations_indexation': {'taux_indexation': 0.005},
    })
    ds, _, _ = sim._apply_prestations_indexation(
        {}, {'taux_indexation': 0.005}, 2030, _GDP, _INFLATION, _UNEMP)
    assert ds == 0
    assert asu_is_active(sim.mesures)


def test_la_doc_ne_dit_plus_que_l_asu_absorbe_exactement_la_base_90():
    """Correction documentaire, repo PUBLIC.

    La v0.5.1 et la v0.6.0 justifiaient la neutralisation en écrivant que
    l'ASU absorbe « exactement » la base 90 Md€ de `prestations_indexation`.
    C'est faux depuis que le périmètre officiel (39 Md€) est établi. Le
    COMPORTEMENT est conservé (choix conservateur : neutraliser en totalité
    ne peut qu'ôter des économies à un programme qui cumule les deux
    leviers), mais l'ÉGALITÉ affirmée doit disparaître — un auditeur externe
    qui vérifie les deux montants trouverait une contradiction interne.
    """
    module = __import__(
        'budget_simulator.handlers.depenses', fromlist=['depenses'])
    doc = (module.__doc__ or "") + inspect.getsource(
        BudgetSimulatorV45._apply_prestations_indexation)
    assert not _cite(doc, r"absorb\w*\s+exactement"), (
        "la doc affirme encore une ÉGALITÉ de périmètre entre l'ASU (39 Md€) "
        "et la base d'indexation (90 Md€)")
    assert _cite(doc, r"SOUS-ENSEMBLE|sous-ensemble"), (
        "la doc doit dire ce que le périmètre ASU EST vis-à-vis de cette "
        "base : un sous-ensemble, neutralisé en totalité par choix "
        "conservateur")


# ---------------------------------------------------------------------------
# 11. Statu quo, robustesse, déterminisme
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("year", _ANNEES_HORIZON)
def test_statu_quo_totalement_inerte(year):
    """ASU désactivée → aucun impact d'aucune nature."""
    delta, revenu, impacts = _impacts(ASU_PLAFONNEMENT_DEFAUT, year, activation=0)
    assert (delta, revenu, impacts) == (0.0, 0.0, {})


def test_defaut_du_moteur_coherent_avec_le_curseur():
    """Le défaut de `config.py` doit rester dans le domaine du curseur, sinon
    une simulation par défaut décrirait une réforme que l'UI ne peut pas
    atteindre."""
    from budget_simulator.config import load_default_values
    defauts = load_default_values()['asu']
    assert defauts['asu_activation'] == 0
    assert ASU_PLAFONNEMENT_MIN <= defauts['asu_plafonnement'] <= ASU_PLAFONNEMENT_MAX
    assert defauts['asu_plafonnement'] == ASU_PLAFONNEMENT_DEFAUT


@pytest.mark.parametrize("valeur", [0.30, 0.90])
def test_plafonnement_hors_domaine_borne_pas_extrapole(valeur):
    """Une valeur hors bornes (scénario mal encodé, API) est ramenée dans le
    domaine : le moteur ne chiffre jamais une générosité que la DREES/Igas
    n'a pas simulée."""
    borne = min(max(valeur, ASU_PLAFONNEMENT_MIN), ASU_PLAFONNEMENT_MAX)
    assert _delta(valeur, 2030) == pytest.approx(_delta(borne, 2030))


def test_deterministe():
    """Deux exécutions successives donnent exactement la même trajectoire."""
    mesures = {'asu': {'asu_activation': 1, 'asu_plafonnement': 0.70}}
    a = _simuler(mesures)['Dette/PIB %'].tolist()
    b = _simuler(mesures)['Dette/PIB %'].tolist()
    assert a == b


# ---------------------------------------------------------------------------
# 12. Sens de la correction — mesuré sur une simulation complète
# ---------------------------------------------------------------------------

def test_activer_l_asu_ne_reduit_plus_la_dette():
    """Le sens de la correction, mesuré bout en bout (§ C.5).

    Avant : activer l'ASU faisait BAISSER la dette (−11,5 Md€/an d'économies
    récurrentes). Après : l'activer coûte, comme dans tous les scénarios
    officiels. C'est la correction qui joue **contre les programmes qui
    inscrivent l'ASU comme gage d'économies** — et contre personne d'autre.
    """
    sans = _simuler({})['Dette/PIB %'].iloc[-1]
    avec = _simuler({'asu': {'asu_activation': 1,
                             'asu_plafonnement': 0.70}})['Dette/PIB %'].iloc[-1]
    assert avec > sans, (
        f"activer l'ASU la plus généreuse réduit encore la dette "
        f"({avec:.2f} vs {sans:.2f})")


def test_asu_la_moins_genereuse_coute_le_recours_rien_de_plus():
    """À l'autre extrémité du curseur (variante « à coût constant »), la
    réforme ne rapporte rien — et depuis la v0.6.3 elle COÛTE le recours
    résorbé (2,4 Md€/an pérennes, DGALN), le seul montant que la source
    attache à la réforme hors barème. Mesuré : ≈ +1,0 pt de dette 2035.
    Borne bilatérale : en deçà, le recours aurait cessé d'être payé ; au-delà,
    un coût non sourcé se serait glissé. (Ancienne propriété « quasi neutre »
    < 1,0 pt : re-déclarée en acte le 30/08/2026 — la quasi-neutralité était
    celle d'un monde où résorber le non-recours était gratuit.)"""
    sans = _simuler({})['Dette/PIB %'].iloc[-1]
    avec = _simuler({'asu': {'asu_activation': 1,
                             'asu_plafonnement': 0.50}})['Dette/PIB %'].iloc[-1]
    assert 0.5 < (avec - sans) < 1.6, (
        f"écart de dette 2035 {avec - sans:+.2f} pt pour la variante à coût "
        f"constant — attendu ≈ +1,0 pt (le recours pérenne, rien d'autre)")


# ===========================================================================
# 12. CLÔTURE DES MINEURS DE LA REVUE ADVERSE (lot 7) — hygiène
# ===========================================================================
#
# Deux défauts que la revue de phase 1 avait relevés sans les traiter. Aucun
# ne déplace un chiffre publié — les deux scénarios qui activent l'ASU
# (`lr_2027`, `im_competitivite_2029`) sont tous deux au plafond de 70 % —
# mais tous deux contredisent, sur une position atteignable du curseur, la
# propriété fondatrice du lot 5 : la réforme COÛTE, elle ne rapporte pas.

def test_le_bornage_du_plafond_reste_defini_sur_nan():
    """Une entrée NaN ne doit pas empoisonner toute la trajectoire.

    ``min(max(x, MIN), MAX)`` PROPAGE NaN : les deux fonctions le retiennent
    (``0,50 > nan`` est faux, donc ``max`` garde ``nan`` ; idem pour ``min``).
    Le NaN traversait alors le bornage, contaminait l'effort pérenne, puis
    ``delta_spending``, puis le solde, puis la dette — et le libellé publié du
    handler affichait « plafond nan% ». Le comportement rétabli est celui
    d'avant la refonte : la borne HAUTE, c'est-à-dire la lecture la plus
    COÛTEUSE du domaine. Une valeur illisible ne peut ainsi jamais acheter une
    économie, ce qui est la seule direction conservatrice ici.

    Ce n'est pas un chemin théorique : la porte unique ``validate_param_domains``
    CLAMPE un NaN au lieu de lever (mode tolérant), le handler chiffre donc
    bien ce que le bornage lui rend — exactement le même raisonnement que
    ``_seniors.retraites_ecart_age_ans_moteur``.
    """
    borne = constants.asu_plafonnement_borne(float('nan'))
    assert borne == borne, "le bornage propage encore NaN"
    assert borne == ASU_PLAFONNEMENT_MAX

    effort = asu_effort_perenne_md_eur(float('nan'))
    assert effort == effort and effort == ASU_EFFORT_PERENNE_MAX_MD_EUR

    delta, _, impacts = _impacts(float('nan'), 2032)
    assert delta == delta, f"delta_spending NaN : {delta!r}"
    assert 'nan' not in impacts['description'].lower(), (
        f"libellé publié empoisonné : {impacts['description']!r}")


@pytest.mark.parametrize("plafonnement", _POSITIONS_UI)
def test_aucun_repas_gratuit_au_pas_du_curseur(plafonnement):
    """Le solde pérenne de l'ASU est ≥ 0 sur TOUT le domaine du curseur.

    LE DÉFAUT : l'effort pérenne est interpolé de 0 à +2 Md€/an entre 50 % et
    70 % du SMIC, tandis que l'économie de gestion vaut 0,3 Md€/an, constante.
    En dessous de 53 % — c'est-à-dire au premier cran du curseur, 50 %, et sur
    tout l'intervalle qui le suit — l'économie de gestion dépassait l'effort :
    le régime permanent dégageait un GAIN NET de 0,3 Md€/an, à perpétuité.

    POURQUOI C'EST FAUX, et pas seulement discutable : la variante la moins
    coûteuse que la DREES/Igas ait chiffrée est celle « à coût constant »,
    dont l'effet budgétaire pérenne est EXACTEMENT NUL. Aucun des scénarios
    publiés ne dégage d'économie nette — c'est le fait n° 2 du § I22, et c'est
    précisément ce que le lot 5 avait entrepris de corriger. Une économie de
    gestion défendable ne suffit pas à retourner ce signe : elle peut au mieux
    COMPENSER l'effort qu'elle accompagne (§ B.3-26 : la fourchette 0,2-0,5 est
    une DÉRIVATION, la mission parlementaire déclare n'avoir pas pu l'estimer).

    Balayage au pas réel du curseur (0,05), le seul qu'un utilisateur puisse
    poser depuis l'interface.
    """
    for year in _ANNEES_HORIZON:
        assert _delta(plafonnement, year) >= -1e-12, (
            f"Y{year} à {plafonnement:.0%} : l'ASU dégage "
            f"{-_delta(plafonnement, year):.2f} Md€ de gain net — aucun "
            f"scénario de la source ne fait rapporter la réforme")


@pytest.mark.parametrize("plafonnement", _GRILLE_FINE)
def test_aucun_repas_gratuit_entre_les_crans_du_curseur(plafonnement):
    """Même propriété sur la grille fine : l'API accepte n'importe quel réel
    du domaine, et un scénario encodé à la main n'est pas tenu par le pas de
    l'interface. La fenêtre fautive ]0,50 ; 0,53[ vivait entièrement entre
    deux crans."""
    for year in _ANNEES_HORIZON:
        assert _delta(plafonnement, year) >= -1e-12, (
            f"Y{year} à {plafonnement}: gain net de "
            f"{-_delta(plafonnement, year):.3f} Md€")


@pytest.mark.parametrize("plafonnement", _GRILLE_FINE)
def test_le_solde_perenne_est_la_source_unique_du_plancher(plafonnement):
    """Le plancher vit dans ``constants.py``, pas dans le handler.

    Même contrat que ``asu_effort_perenne_md_eur`` : une seule fonction dit ce
    que la réforme coûte en régime, et le handler ne fait que la consommer et
    la faire monter en charge. Sans cela, le plancher serait re-dérivable
    ailleurs — c'est le mode de défaillance que le lot 5 a fermé pour le
    bornage du plafond."""
    solde = constants.asu_solde_perenne_md_eur(plafonnement)
    effort = asu_effort_perenne_md_eur(plafonnement)
    assert solde >= 0.0
    assert solde == pytest.approx(max(effort - ASU_ECO_SIMPLIFICATION_MD_EUR, 0.0))
    # En régime permanent (phasing = 1, transition terminée), le handler rend
    # exactement ce que la source unique annonce, PLUS le recours pérenne
    # (v0.6.3) — additif et indépendant du plafond, donc hors du plancher.
    assert _delta(plafonnement, 2032) == pytest.approx(
        solde + ASU_COUT_RECOURS_MD_EUR, abs=1e-12)


def test_l_economie_de_gestion_reste_effective_la_ou_elle_a_de_la_place():
    """Contre-épreuve : le plancher n'a pas ANNULÉ l'économie de gestion.

    Sans elle, on pourrait satisfaire la propriété ci-dessus en supprimant
    purement et simplement les 0,3 Md€/an — ce qui serait une correction
    différente, non demandée, et contraire au § I23 (la masse mobilisable sur
    RSA + prime d'activité + APL est de 0,8 à 1,0 Md€/an, la retenir est
    défendable). Partout où l'effort dépasse l'économie de gestion, celle-ci
    continue de s'en déduire intégralement.
    """
    for plafonnement in (0.60, 0.65, ASU_PLAFONNEMENT_MAX):
        effort = asu_effort_perenne_md_eur(plafonnement)
        assert effort > ASU_ECO_SIMPLIFICATION_MD_EUR, "prémisse du cas testé"
        assert constants.asu_solde_perenne_md_eur(plafonnement) == pytest.approx(
            effort - ASU_ECO_SIMPLIFICATION_MD_EUR)


def test_le_plancher_ne_deplace_pas_les_scenarios_publies():
    """Sens du lot, vérifié : hygiène, pas recalibrage.

    Les deux seuls scénarios publiés qui activent l'ASU (`lr_2027` et
    `im_competitivite_2029`) sont au plafond de 70 % du SMIC, où l'effort
    (2,0 Md€/an) dépasse largement l'économie de gestion : le plancher n'y
    mord pas et leurs trajectoires restent bit-identiques."""
    assert constants.asu_solde_perenne_md_eur(ASU_PLAFONNEMENT_MAX) == pytest.approx(
        ASU_EFFORT_PERENNE_MAX_MD_EUR - ASU_ECO_SIMPLIFICATION_MD_EUR)
    # À partir de l'entrée en vigueur seulement : avant POLICY_START_YEAR le
    # phasing vaut 0 et le handler est inerte par construction.
    for year in range(POLICY_START_YEAR, ANNEE_HORIZON + 1):
        assert _delta(ASU_PLAFONNEMENT_MAX, year) > 0


@pytest.mark.parametrize("plafonnement", _GRILLE_FINE)
def test_le_plancher_est_un_plafond_sur_l_economie_de_gestion(plafonnement):
    """L'équivalence qui explique pourquoi Gini et PA restent indexés sur
    l'EFFORT, et non sur le solde.

    ``max(effort − gestion, 0) == effort − min(gestion, effort)`` : plancher le
    solde, c'est PLAFONNER l'économie de gestion à l'effort qu'elle compense.
    Le plancher ne retire donc rien aux ménages — le transfert reste celui que
    la DREES/Igas chiffre — il refuse seulement d'inscrire au budget un gain
    net qu'aucun scénario officiel ne produit.

    Sans cette lecture explicite, la question évidente reste ouverte : « à 52 %
    du SMIC, le solde est nul et le Gini s'améliore, n'est-ce pas un repas
    gratuit ? » Non : l'amélioration est financée par les 0,2 Md€ réellement
    transférés ; c'est le reliquat d'économie de gestion (0,1 Md€) qui n'est
    pas encaissé.
    """
    effort = asu_effort_perenne_md_eur(plafonnement)
    gestion_effective = min(ASU_ECO_SIMPLIFICATION_MD_EUR, effort)
    assert constants.asu_solde_perenne_md_eur(plafonnement) == pytest.approx(
        effort - gestion_effective, abs=1e-12)
    # Et le canal redistributif suit le transfert, pas le solde.
    gini = _impacts(plafonnement, 2027)[2].get('gini', 0.0)
    assert (gini < 0) == (effort > 0), (
        f"à {plafonnement}: Gini {gini:+.8f} pour un effort de {effort} Md€ — "
        "l'amélioration doit suivre le transfert réel vers les ménages")
