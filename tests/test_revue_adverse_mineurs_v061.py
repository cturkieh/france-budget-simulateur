"""Clôture des MINEURS de la revue adverse v0.6.1 (lot 7) — hygiène.

Ce lot ne change aucune direction politique : il ferme des défauts de forme
que la revue adverse de phase 1 avait relevés sans les traiter, parce
qu'aucun d'eux ne déplaçait un chiffre publié. Ils ont pourtant tous la même
propriété désagréable — ils rendent le moteur MOINS AUDITABLE qu'il ne l'est
réellement, ce qui, sur un dépôt AGPL public, coûte plus cher qu'un écart de
calibration documenté.

Les quatre défauts couverts ici :

1. **L'horloge du garde Gini du levier d'âge** (``handlers/depenses.py``).
   Le moteur applique l'effet redistributif d'une mesure d'âge EN PLEIN
   l'année du changement, puis n'en laisse qu'un résidu de flux. Ce
   déclenchement lisait l'horloge du RUN alors que la grandeur qu'il gate
   (``gini_age``) dérive de l'écart au calendrier légal de l'ANNÉE. Pour un
   programme dont l'écart s'ouvre APRÈS 2026 — c'est-à-dire un programme qui
   fige l'âge à 62,75 ans, la seule valeur du domaine dont l'écart est nul en
   2026-2027 — l'effet plein tombait sur un écart nul, donc sur zéro, et
   l'horizon entier n'était plus chiffré qu'au résidu. Le lot 1 avait déjà
   ré-ancré les quatre autres canaux d'une mesure d'âge sur l'horloge du
   CHOC ; celui-ci était le cinquième, et il avait été oublié.

2. **Un commentaire load-bearing faux** (``engine/orchestrator.py``). Le bloc
   de mise à jour de l'output gap déclarait consommer « l'état d'offre de
   l'année précédente », alors que ``update_labour_supply`` tourne en TÊTE de
   la MÊME année (c'est l'objet même de la correction I6 : croissance, Okun
   et output gap doivent lire le même potentiel, bonus d'offre inclus). Un
   commentaire d'ordonnancement faux est un piège pour la prochaine
   correction : il décrit un lag que le code n'a pas, et invite à « corriger »
   le code vers le commentaire.

3. **Une docstring de test qui nie une différence d'unités réelle**
   (``test_emploi_seniors_v061.py``, P3). Le bouclage budgétaire du canal
   emploi est comparé au tableau n° 6 de la Cour, publié en **Md€ constants
   2024** ; le moteur, lui, rend des recettes 2035 en **euros courants**. La
   fenêtre [14 ; 19] reste valide — elle est justement assez large pour
   contenir les deux lectures — mais elle ne l'est PAS pour la raison que la
   docstring donnait.

4. **Une citation localisée dans la mauvaise note de bas de page**
   (``constants.py``, ``docs/METHODOLOGIE.md``). Le verbatim de la Cour sur
   les recherches micro-économétriques est au CORPS de la page 67 ; la note
   121, elle, porte les chiffres des modèles désavoués (+0,7 pt Mésange,
   +0,5 pt e-mod.fr). Sur un dépôt public dont l'audit citoyen a déjà relevé
   des citations fausses, un locator précis mais faux est pire qu'un locator
   absent. La garde de non-régression vit dans
   ``test_balayage_citations_v061.py``, avec les autres.

Les items 5 (fallback ``impot_societes``), 2-3 (ASU) et 8 (registre) du même
lot vivent dans les fichiers de leur sujet : ``test_gini_v061.py``,
``test_asu_v061.py``, ``test_measure_registry_*.py``.
"""
from __future__ import annotations

import ast
import importlib
import inspect
import re
import textwrap

import pytest

from budget_simulator._seniors import (
    _premiere_annee_ecart_non_nul,
    retraites_annee_debut_ecart_age_handler,
    retraites_ecart_age_ans,
)
from budget_simulator.constants import (
    POLICY_START_YEAR,
    RETRAITES_COEFF_AGE_MD_EUR,
    RETRAITES_GINI_PAR_ANNEE_ECART,
    RETRAITES_GINI_RESIDU_FLUX,
    retraites_ref_age_ans,
)
from budget_simulator.engine import orchestrator
from budget_simulator.simulator import BudgetSimulatorV45

ANNEE_HORIZON = 2035
_ANNEES = tuple(range(POLICY_START_YEAR, ANNEE_HORIZON + 1))
_GDP, _INFLATION, _UNEMP = 3100.0, 0.015, 0.075

#: Le seul âge du domaine dont l'écart au droit en vigueur est NUL en 2026 :
#: la référence légale y est gelée à 62,75 ans jusqu'en 2027, puis monte de
#: trois mois par génération. Poser cet âge, c'est chiffrer la suspension
#: définitive de la réforme — une mesure, pas un statu quo (le statu quo est
#: l'ABSENCE de clé ``age_depart``, cf. lot 1).
AGE_GELE = 62.75


def _serie_gini(age_depart, indexation=1.0, annees=_ANNEES):
    """Série annuelle des émissions ``gini`` du handler retraites.

    UNE SEULE instance pour toute la série : le garde one-time est un état
    d'instance (``_measure_params_tracker``). Réinstancier à chaque année
    ferait croire à un effet plein tous les ans et le test ne mesurerait
    plus rien.
    """
    params = {'age_depart': age_depart, 'indexation': indexation,
              'duree_cotisation': 42.5}
    sim = BudgetSimulatorV45(periods=len(annees), mesures={'retraites': params})
    return {annee: sim._apply_retraites(
        {'id': 'retraites'}, params, annee, _GDP, _INFLATION, _UNEMP,
    )[2]['gini'] for annee in annees}


def _gini_age_theorique(age_depart, annee):
    """Effet redistributif de NIVEAU de l'année, avant tout gating."""
    ecart = age_depart - retraites_ref_age_ans(annee)
    return RETRAITES_GINI_PAR_ANNEE_ECART * ecart


# ===========================================================================
# 1. L'horloge du garde Gini du levier d'âge
# ===========================================================================

def test_l_effet_plein_tombe_sur_la_premiere_annee_d_ecart_non_nul():
    """L'effet de NIVEAU se déclenche quand l'écart s'ouvre, pas quand le run
    commence.

    Un programme figeant l'âge à 62,75 ans n'ouvre son écart qu'en 2028 (la
    référence légale est gelée en 2026-2027). L'ancien garde lisait l'horloge
    du run : il servait les 100 % en 2026, où ``gini_age`` vaut exactement
    zéro, puis ne laissait que le résidu de flux pour tout l'horizon. La
    mortalité différentielle d'un gel de la réforme était donc chiffrée au
    dixième de sa valeur.
    """
    params = {'age_depart': AGE_GELE, 'indexation': 1.0}
    ouverture = retraites_annee_debut_ecart_age_handler(params)
    assert ouverture == 2028, (
        "prémisse du test : l'écart d'un âge figé à 62,75 ans s'ouvre en 2028")

    serie = _serie_gini(AGE_GELE)
    assert serie[ouverture] == pytest.approx(
        _gini_age_theorique(AGE_GELE, ouverture), abs=1e-15), (
        f"l'année d'ouverture {ouverture} ne porte pas l'effet PLEIN")
    for annee in _ANNEES:
        if annee == ouverture:
            continue
        assert serie[annee] == pytest.approx(
            RETRAITES_GINI_RESIDU_FLUX * _gini_age_theorique(AGE_GELE, annee),
            abs=1e-15), f"Y{annee} ne porte pas le seul résidu de flux"


def test_meme_effet_qu_un_programme_dont_l_ecart_est_ouvert_des_2026():
    """Contre-épreuve d'ÉQUIVALENCE, celle qui donne son sens à la correction.

    Deux programmes ayant le MÊME écart au droit en vigueur l'année où cet
    écart s'ouvre doivent recevoir le MÊME effet plein — que cette année soit
    2026 ou 2028. C'est très exactement ce que l'ancien garde ne faisait pas :
    l'un touchait ``k × (−0,25)``, l'autre zéro.

    Le programme témoin est l'âge 62,50 : son écart vaut −0,25 an dès 2026,
    comme celui de l'âge gelé en 2028.
    """
    temoin = AGE_GELE - 0.25
    assert retraites_ecart_age_ans({'age_depart': temoin}, POLICY_START_YEAR) \
        == pytest.approx(retraites_ecart_age_ans({'age_depart': AGE_GELE}, 2028)), (
        "prémisse : les deux programmes ont le même écart à leur ouverture")

    gele = _serie_gini(AGE_GELE)
    ouvert = _serie_gini(temoin)
    assert gele[2028] == pytest.approx(ouvert[POLICY_START_YEAR], abs=1e-15)

    # ... et la même identité de structure sur tout l'horizon : le cumul se
    # décompose en « un effet plein + le résidu partout ailleurs », dans les
    # deux cas. Avant la correction, le premier terme valait zéro pour le
    # programme gelé.
    for serie, age, ouverture in ((gele, AGE_GELE, 2028),
                                  (ouvert, temoin, POLICY_START_YEAR)):
        residus = sum(RETRAITES_GINI_RESIDU_FLUX * _gini_age_theorique(age, a)
                      for a in _ANNEES if a != ouverture)
        assert sum(serie.values()) == pytest.approx(
            _gini_age_theorique(age, ouverture) + residus, abs=1e-14)


@pytest.mark.parametrize("age_depart", [60.0, 62.0, 62.5, 63.0, 64.0, 65.0, 67.0])
def test_les_programmes_dont_l_ecart_s_ouvre_en_2026_sont_inchanges(age_depart):
    """Non-régression : la correction ne déplace QUE l'âge gelé.

    Tout âge différent de 62,75 ouvre son écart dès la première année simulée,
    où les deux horloges coïncident. Les neuf scénarios publiés sont dans ce
    cas (aucun ne pose 62,75) : leurs chiffres restent bit-identiques, ce que
    le golden master vérifie de son côté.
    """
    serie = _serie_gini(age_depart)
    assert serie[POLICY_START_YEAR] == pytest.approx(
        _gini_age_theorique(age_depart, POLICY_START_YEAR), abs=1e-15)


def test_l_indexation_garde_l_horloge_du_run():
    """Deux horloges, pas une : la référence de l'indexation est FIXE.

    ``gini_indexation`` mesure un écart à la PLEINE indexation, référence qui
    ne bouge pas d'une année sur l'autre : son écart s'ouvre donc dès la
    première année simulée. Faire porter au canal indexation l'horloge du choc
    d'ÂGE différerait son effet plein à 2028 pour un programme qui gèle l'âge
    ET désindexe — un couplage qu'aucune source ne décrit.
    """
    serie = _serie_gini(AGE_GELE, indexation=0.9)
    sans_indexation = _serie_gini(AGE_GELE, indexation=1.0)
    part_indexation = {a: serie[a] - sans_indexation[a] for a in _ANNEES}

    plein = part_indexation[POLICY_START_YEAR]
    assert plein > 0, "un gel d'indexation dégrade le Gini : effet attendu > 0"
    for annee in _ANNEES[1:]:
        assert part_indexation[annee] == pytest.approx(
            RETRAITES_GINI_RESIDU_FLUX * plein, abs=1e-15)


def test_le_garde_gini_lit_l_horloge_unique_du_module_seniors():
    """Garde d'architecture : une seule implémentation de l'horloge.

    C'est la raison d'être de ``_seniors`` — un recalibrage du calendrier
    légal doit atteindre les CINQ canaux d'une mesure d'âge, jamais quatre sur
    cinq. Si le handler recalculait son année d'ouverture pour son propre
    compte, ce test rougirait.
    """
    source = textwrap.dedent(
        inspect.getsource(BudgetSimulatorV45._apply_retraites))
    assert 'retraites_annee_debut_ecart_age_handler' in source
    # L'horloge partagée est bien celle du balayage commun de `_seniors`.
    assert _premiere_annee_ecart_non_nul(
        lambda a: retraites_ecart_age_ans({'age_depart': AGE_GELE}, a)) == 2028


def test_le_residu_de_flux_est_une_constante_nommee():
    """Plus de coefficient anonyme dans le handler : le résidu de 10 % est une
    CONVENTION de modélisation (le flux annuel des nouvelles cohortes), pas une
    valeur sourcée — raison de plus pour qu'un auditeur externe puisse la
    nommer et la retrouver."""
    source = textwrap.dedent(
        inspect.getsource(BudgetSimulatorV45._apply_retraites))
    assert 'RETRAITES_GINI_RESIDU_FLUX' in source
    assert 0.0 < RETRAITES_GINI_RESIDU_FLUX < 1.0

    # Sur le CODE seul (arbre syntaxique), jamais sur le texte : les
    # commentaires ont le droit — et le devoir — de citer les valeurs qu'ils
    # expliquent. Ce sont les littéraux EXÉCUTÉS qui doivent tous vivre dans
    # constants.py avec leur source. Seuls 0,0 et 1,0 restent, et ce sont des
    # neutres arithmétiques, pas des calibrations : les quatre coefficients du
    # handler (âge, résidu de flux, désindexation, pouvoir d'achat) sont
    # désormais nommés.
    arbre = ast.parse(source)
    litteraux = {n.value for n in ast.walk(arbre)
                 if isinstance(n, ast.Constant)
                 and isinstance(n.value, float)
                 and not isinstance(n.value, bool)}
    assert litteraux <= {0.0, 1.0}, (
        f"littéral de calibration dans le handler retraites : "
        f"{sorted(litteraux - {0.0, 1.0})}")


# ===========================================================================
# 2. Le commentaire d'ordonnancement de l'output gap
# ===========================================================================

def _corps_de_simulate() -> str:
    return textwrap.dedent(inspect.getsource(orchestrator.OrchestratorMixin.simulate))


def _bloc_de_commentaire_avant_output_gap(source: str) -> str:
    """Commentaires contigus qui précèdent la récurrence de l'output gap."""
    lignes = source.splitlines()
    cible = next(i for i, l in enumerate(lignes)
                 if l.strip().startswith('output_gap = 0.8 * output_gap'))
    bloc = []
    i = cible - 1
    while i >= 0 and lignes[i].strip().startswith('#'):
        bloc.append(lignes[i].strip())
        i -= 1
    return "\n".join(reversed(bloc))


def test_l_offre_de_travail_est_bien_posee_avant_l_output_gap():
    """L'ordre RÉEL, mesuré sur l'arbre syntaxique — c'est lui que le
    commentaire doit décrire.

    ``update_labour_supply`` est appelée en TÊTE de l'itération d'année, avant
    ``calculate_growth``, ``calculate_unemployment`` et la récurrence de
    l'output gap. C'est l'objet même de la correction I6 : les trois lisent le
    MÊME potentiel, bonus d'offre inclus, sinon un choc d'offre ouvre un écart
    d'activité qu'il ne devrait pas ouvrir.
    """
    source = _corps_de_simulate()
    arbre = ast.parse(source)
    positions = {}
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute):
            positions.setdefault(noeud.func.attr, noeud.lineno)
    ligne_output_gap = next(
        i + 1 for i, l in enumerate(source.splitlines())
        if l.strip().startswith('output_gap = 0.8 * output_gap'))

    assert positions['update_labour_supply'] < positions['calculate_growth']
    assert positions['update_labour_supply'] < positions['calculate_unemployment']
    assert positions['update_labour_supply'] < ligne_output_gap
    assert ligne_output_gap < positions['update_potential_growth']


def test_le_commentaire_de_l_output_gap_ne_contredit_pas_cet_ordre():
    """Un commentaire d'ordonnancement FAUX est un piège, pas une imprécision.

    Celui-ci déclarait consommer « l'état d'offre de l'année précédente » :
    il décrivait un lag que le code n'a pas, et invitait la correction
    suivante à aligner le code sur le commentaire — c'est-à-dire à réintroduire
    exactement le bug I6. Le producteur est nommé, et aucune antériorité n'est
    revendiquée.
    """
    bloc = _bloc_de_commentaire_avant_output_gap(_corps_de_simulate())
    assert bloc, "bloc de commentaire de l'output gap introuvable"
    assert 'update_labour_supply' in bloc, (
        "le commentaire ne nomme pas le producteur de l'état d'offre")
    assert re.search(r'courante', bloc, flags=re.IGNORECASE), (
        "le commentaire ne dit pas que l'état d'offre lu est celui de l'année "
        "courante — c'est pourtant tout ce que I6 a corrigé")
    assert not re.search(r'ann[ée]e\s+pr[ée]c[ée]dente', bloc,
                         flags=re.IGNORECASE), (
        f"le commentaire revendique un lag que l'ordre réel dément :\n{bloc}")


# ===========================================================================
# 3. La docstring de P3 et la différence d'unités
# ===========================================================================

def _module_p3():
    """Le fichier de tests du canal emploi seniors, importé par son nom nu.

    ``tests/`` n'est pas un package (pas d'``__init__.py``) : pytest y insère
    le dossier en tête de ``sys.path``, l'import par nom nu est donc le seul
    chemin qui marche à la fois en run complet et en run ciblé.
    """
    return importlib.import_module('test_emploi_seniors_v061')


def _docstring_p3() -> str:
    return inspect.getdoc(_module_p3().test_p3_bouclage_budgetaire_cour_t6) or ""


def test_la_docstring_de_p3_declare_la_difference_d_unites():
    """Ce que P3 compare réellement : un delta de recettes 2035 en euros
    COURANTS à une cible publiée en Md€ CONSTANTS 2024.

    L'ancienne rédaction affirmait que « la comparaison porte donc bien sur le
    même objet que la Cour ». C'est vrai du périmètre (une année d'âge, toutes
    APU, à horizon complet) et faux du millésime. La fenêtre [14 ; 19] reste
    valide, mais parce qu'elle absorbe le déflateur — pas parce qu'il n'y en
    a pas. Un test dont la docstring nie l'approximation qu'il tolère est un
    test qu'un auditeur ne peut pas relire.
    """
    doc = _docstring_p3()
    assert doc, "docstring de P3 introuvable"
    assert re.search(r'courants?', doc, flags=re.IGNORECASE), (
        "la docstring ne dit pas que le moteur rend des euros courants")
    assert re.search(r'constants?', doc, flags=re.IGNORECASE), (
        "la docstring ne dit pas que la cible de la Cour est en euros constants")
    assert 'même objet que la Cour' not in doc, (
        "la docstring affirme encore l'identité d'objet qu'elle contredit")


def test_la_docstring_de_p3_dit_dans_quel_sens_l_ecart_d_unites_joue():
    """Déclarer une approximation ne suffit pas : il faut dire de quel côté
    elle penche.

    C'est la règle de neutralité du projet (§ C du dossier) appliquée à un
    test : le moteur rend 17,5 Md€ courants 2035, soit 14,6 à 15,9 en
    constants 2024 ; la cible de la Cour, elle, vaudrait 19 à 21 Md€ courants.
    Une fois les unités alignées, le canal est donc CONSERVATEUR — contre les
    programmes de report d'âge. Une docstring qui déclarerait l'écart sans
    son sens laisserait croire à un flou symétrique.
    """
    doc = _docstring_p3()
    assert re.search(r'conservat', doc, flags=re.IGNORECASE), (
        "la docstring déclare la différence d'unités sans dire dans quel sens "
        "elle joue")


def test_le_lot_ne_touche_pas_la_fenetre_de_p3():
    """Contre-épreuve de périmètre : ce lot corrige la DOCSTRING, pas le seuil.

    Élargir ou déplacer [14 ; 19] pour « faire coller » les unités reviendrait
    à publier un déflateur qu'aucune institution ne publie au-delà de
    2029-2030 (§ B.2-17). La fenêtre reste ce qu'elle était.
    """
    source = inspect.getsource(
        _module_p3().test_p3_bouclage_budgetaire_cour_t6)
    assert '14.0 <= bouclage <= 19.0' in source, (
        "la fenêtre a bougé : ce lot ne corrige QUE la docstring")


# ===========================================================================
# 4. Méta-garde : le lot ne déplace aucun chiffre publié hors de l'âge gelé
# ===========================================================================

def test_le_bareme_d_age_lui_meme_est_inchange():
    """Sens du lot, vérifié : hygiène, pas recalibrage.

    Ni le barème plat de 6,0 Md€/an, ni le coefficient redistributif de
    0,001 par 1,25 année d'écart (§ B.1-13 du dossier : « ne pas l'ajuster
    hors d'une passe dédiée ») ne bougent.
    """
    assert RETRAITES_COEFF_AGE_MD_EUR == pytest.approx(6.0)
    assert RETRAITES_GINI_PAR_ANNEE_ECART == pytest.approx(0.001 / 1.25)
