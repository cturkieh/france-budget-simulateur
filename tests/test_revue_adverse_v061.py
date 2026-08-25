"""Clôture de la revue adverse v0.6.1 — la sémantique de l'item I3 propagée partout.

L'item I3 a changé la SIGNIFICATION de la valeur 62,75 : la référence d'âge
n'est plus un scalaire figé mais le calendrier légal (62,75 ans en 2026-2027,
puis +3 mois par génération jusqu'à 64,0 ans en 2032). Poser 62,75 sur tout
l'horizon ne décrit donc plus « je ne touche à rien » mais « je suspends la
réforme DÉFINITIVEMENT » — une mesure, facturée jusqu'à 6,78 Md€/an de pensions
à partir de 2032.

Le lot 3 a retiré cet encodage du seul scénario de référence `plf_2026`. La
revue adverse a montré que l'artefact survivait sur DEUX autres surfaces
publiées — le défaut du moteur (donc `/scenarios → status_quo`, donc le point
de départ du simulateur) et le programme de parti `renaissance_2027` — et que
le canal budgétaire gardait une horloge de montée en charge différente de celle
des canaux macro.

Ce fichier porte les gardes permanentes de cette clôture. Chaque test nomme la
surface qu'il protège : ce sont toutes des surfaces PUBLIÉES.
"""
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from budget_simulator._seniors import (
    retraites_annee_debut_ecart_age,
    retraites_ecart_age_ans,
)
from budget_simulator.config import load_default_values
from budget_simulator.constants import POLICY_START_YEAR, RETRAITES_REF_AGE_ANS
from budget_simulator.simulator import BudgetSimulatorV45

# Fenêtre de vérification : l'horizon publié (10 ans) plus une décennie, pour
# couvrir le plateau du calendrier légal (2032) et au-delà.
_MILLESIMES = tuple(range(POLICY_START_YEAR, POLICY_START_YEAR + 20))

_RACINE = pathlib.Path(__file__).resolve().parent.parent
_SCENARIOS_JSON = _RACINE / '..' / '..' / 'frontend-react' / 'src' / 'data' / 'scenarios.json'


def _scenarios_publies():
    """Scénarios réellement publiés, lus SANS aménagement (même résolution que
    le corridor de calibration : l'env var d'abord, le chemin résolu ensuite)."""
    candidats = []
    env = (os.environ.get('BUDGETLAB_SCENARIOS_JSON') or '').strip()
    if env:
        candidats.append(pathlib.Path(env))
    candidats.append(_SCENARIOS_JSON)
    for chemin in candidats:
        if chemin.exists():
            return json.loads(chemin.read_text(encoding='utf-8'))
    pytest.skip("scenarios.json introuvable (fork moteur public seul)")


# ---------------------------------------------------------------------------
# 1. Le défaut du moteur — « statu quo » de `/scenarios` et du simulateur
# ---------------------------------------------------------------------------


@pytest.mark.parametrize('year', _MILLESIMES)
def test_le_defaut_du_moteur_est_neutre_sur_tous_les_millesimes(year):
    """Le défaut livré doit avoir un écart RIGOUREUSEMENT nul chaque année.

    C'est la définition opératoire du statu quo depuis I3, et elle ne peut pas
    être satisfaite par un scalaire : la référence bouge de 62,75 à 64,0 entre
    2026 et 2032. Un défaut figé à 62,75 devient une mesure dès 2028 — mesurée
    à +3,65 pt de dette 2035 sur le tendanciel.
    """
    assert retraites_ecart_age_ans(load_default_values()['retraites'], year) == 0.0


def test_le_defaut_du_moteur_ne_change_pas_la_trajectoire():
    """Même invariant, vu du seul endroit qui compte : la trajectoire publiée.

    Simuler le bloc `retraites` par défaut doit rendre exactement la même dette
    que simuler ce bloc privé de tout âge — sinon le « statu quo » de l'API
    chiffre une réforme des retraites que personne n'a demandée.
    """
    defauts = load_default_values()['retraites']
    sans_age = {k: v for k, v in defauts.items() if k != 'age_depart'}
    avec = BudgetSimulatorV45(periods=10, mesures={'retraites': defauts}).simulate()[0]
    sans = BudgetSimulatorV45(periods=10, mesures={'retraites': sans_age}).simulate()[0]
    assert avec['Dette/PIB %'].iloc[-1] == pytest.approx(sans['Dette/PIB %'].iloc[-1], abs=1e-9)


# ---------------------------------------------------------------------------
# 2. Les scénarios publiés — traitement identique du référentiel et des partis
# ---------------------------------------------------------------------------


def test_aucun_scenario_publie_nencode_le_gel_comme_statu_quo():
    """Garde de NEUTRALITÉ, étendue des seuls `plf_2026` à TOUS les scénarios.

    `RETRAITES_REF_AGE_ANS` (62,75) est la valeur qui a changé de sens avec
    I3 : elle était l'encodage conventionnel de « je ne touche pas aux
    retraites », elle décrit désormais la suspension définitive de la réforme
    — 4,01 pt de dette 2035 sur `renaissance_2027`, dont la fiche programme
    n'annonce aucune mesure d'âge.

    Le lot 3 n'avait nettoyé que le comparateur implicite (`plf_2026`) : un
    programme de parti restait facturé l'artefact que le scénario de référence
    venait de perdre. Exonérer le référentiel et pas les programmes est
    exactement le biais que cet outil ne peut pas se permettre.

    Un futur scénario qui voudrait VRAIMENT chiffrer une suspension définitive
    reste possible — mais il devra modifier cette garde et le dire dans sa
    fiche, ce qui est le but.
    """
    fautifs = {
        nom: bloc['apiMeasures']['retraites']['age_depart']
        for nom, bloc in _scenarios_publies().items()
        if (bloc.get('apiMeasures', {}).get('retraites', {}).get('age_depart')
            == RETRAITES_REF_AGE_ANS)
    }
    assert not fautifs, (
        f"scénario(s) encodant l'âge gelé {RETRAITES_REF_AGE_ANS} comme statu quo : "
        f"{sorted(fautifs)} — depuis I3 cette valeur chiffre une suspension "
        "définitive de la réforme des retraites, pas une absence de mesure"
    )


# ---------------------------------------------------------------------------
# 3. Une seule horloge pour une seule montée en charge par cohortes
# ---------------------------------------------------------------------------


_GDP, _INFLATION, _UNEMP = 3000.0, 0.015, 0.075


def _ligne_pension(age, year):
    """Impact dépenses du handler retraites, âge seul (Md€, négatif = économie)."""
    sim = BudgetSimulatorV45(mesures={})
    delta, _, _ = sim._apply_retraites(
        {}, {'age_depart': age}, year, _GDP, _INFLATION, _UNEMP)
    return delta


@pytest.mark.parametrize('age', [60.0, 61.5, 62.0, 62.75, 63.0, 64.0, 65.0, 67.0])
def test_le_handler_date_le_choc_comme_les_canaux_macro(age):
    """Le canal budgétaire et les canaux macro doivent dater le choc PAREIL.

    Les quatre canaux d'une mesure d'âge lisent la MÊME montée en charge par
    cohortes : `PHASING_RETRAITES_5ANS` côté handler, et le même facteur inclus
    multiplicativement dans `PHASING_OFFRE_SENIORS` /
    `PHASING_CHOMAGE_SENIORS` côté moteur. La clôture du lot 3 a ré-ancré les
    seuls profils macro sur le début de l'écart et laissé le handler indexé sur
    `year - POLICY_START_YEAR`.

    Conséquence pour un programme dont l'écart s'ouvre en 2028 (âge 62,75) :
    les mêmes générations étaient réputées entrées à 100 % pour les moindres
    pensions et à 60 % pour l'offre de travail, la même année — soit ≈4,3 Md€
    cumulés imputés en avance de phase sur 2028-2031.

    Le test reconstruit la ligne de pension attendue à partir des constantes,
    avec l'horloge du CHOC. Il ne fige aucun littéral : il suit un recalibrage
    du barème, de la fuite ou du calendrier légal.
    """
    from budget_simulator.constants import (
        FUITE_SOCIALE_RESIDUELLE,
        PHASING_RETRAITES_5ANS,
        RETRAITES_COEFF_AGE_MD_EUR,
    )
    from budget_simulator.handlers._phasing import _year_phasing

    mesures = {'retraites': {'age_depart': age}}
    debut = retraites_annee_debut_ecart_age(mesures)
    for year in range(POLICY_START_YEAR, POLICY_START_YEAR + 10):
        ecart = retraites_ecart_age_ans({'age_depart': age}, year)
        attendu = -(RETRAITES_COEFF_AGE_MD_EUR * ecart
                    * _year_phasing(year - debut, PHASING_RETRAITES_5ANS)
                    * (1 - FUITE_SOCIALE_RESIDUELLE))
        assert _ligne_pension(age, year) == pytest.approx(attendu, abs=1e-9), (
            f"âge {age}, année {year} : le handler n'utilise pas l'horloge du "
            f"choc (écart ouvert en {debut})")


# ---------------------------------------------------------------------------
# 4. Le tooltip public du levier d'âge — verrou CODE → DOC sur leverMeta.js
# ---------------------------------------------------------------------------


_LEVER_META_JS = _RACINE / '..' / '..' / 'frontend-react' / 'src' / 'data' / 'leverMeta.js'


def _bloc_lever_meta(nom):
    texte = _LEVER_META_JS.read_text(encoding='utf-8')
    bloc = re.search(rf"\n    {nom}: \{{(.*?)\n    \}}", texte, re.S)
    assert bloc, f"bloc `{nom}` introuvable dans leverMeta.js"
    return bloc.group(1)


@pytest.mark.skipif(not _LEVER_META_JS.exists(),
                    reason="frontend-react/ hors périmètre fork moteur seul")
def test_le_tooltip_public_du_levier_dage_suit_les_constantes():
    """Verrou CODE → DOC sur le fichier que le CURSEUR consomme.

    Le tooltip du levier le plus regardé du site publiait encore le
    coefficient de la v0.5.1 (« ±16 Md€/an par année d'âge »), soit 2,7 fois
    le barème que le lot 1 a établi, une « référence 2025 : 62,75 ans » que
    l'item I3 rend fausse, et une attribution « COR 2024 » là où la valeur est
    portée par la DG Trésor et la Cour des comptes. La cascade de tooltips
    avait été faite pour la prévention, l'ASU et la fraude sociale — pas pour
    le seul levier dont la branche corrige le coefficient d'un facteur 2,4.

    L'attendu est CONSTRUIT à partir des constantes : un recalibrage du barème
    ou de la fuite fait rougir ce test, il ne le contourne pas.
    """
    from budget_simulator.constants import (
        FUITE_SOCIALE_RESIDUELLE,
        RETRAITES_COEFF_AGE_MD_EUR,
        RETRAITES_REF_AGE_CIBLE_ANS,
    )

    corps = _bloc_lever_meta('retraites_age')
    brut = f"{RETRAITES_COEFF_AGE_MD_EUR:.1f}".replace('.', ',')
    net = f"{RETRAITES_COEFF_AGE_MD_EUR * (1 - FUITE_SOCIALE_RESIDUELLE):.1f}".replace('.', ',')
    cible = f"{RETRAITES_REF_AGE_CIBLE_ANS:g}".replace('.', ',')

    assert f"±{brut} Md€/an" in corps, (
        f"le tooltip ne publie pas le barème brut {brut} Md€/an : {corps[-400:]}")
    assert f"{net} Md€/an" in corps, (
        f"le tooltip ne publie pas le barème net de la fuite sociale ({net}) : {corps[-400:]}")
    assert f"{cible} ans en 2032" in corps, "le tooltip ne publie pas la cible du calendrier légal"
    # Sources primaires du barème (dossier §A) — jamais « COR 2024 », qui ne
    # porte pas cette valeur.
    assert 'DG Trésor' in corps and 'Cour des comptes' in corps, \
        "le tooltip n'attribue pas le barème à ses deux sources primaires"
    for perime in ('±16 Md€', 'référence 2025', 'Source : COR 2024'):
        assert perime not in corps, f"formulation périmée encore publiée : « {perime} »"


# ---------------------------------------------------------------------------
# 5. L'asymétrie durée ↔ âge : non corrigée, mais DITE
# ---------------------------------------------------------------------------


_METHODO = _RACINE / 'docs' / 'METHODOLOGIE.md'


@pytest.mark.parametrize('year', _MILLESIMES[:10])
def test_le_canal_emploi_seniors_ignore_la_duree_de_cotisation(year):
    """Le canal emploi n'est câblé que sur `age_depart` — verrouillé EXPLICITE.

    Ce n'est pas un test de non-régression décoratif : le levier
    `duree_cotisation` déplace le MÊME âge effectif de départ (40 annuités au
    lieu de 42,5, c'est partir plus tôt) et n'ouvre pourtant ni offre de
    travail → PIB, ni bosse de chômage, ni fuite sociale. Deux leviers de la
    même réforme, décrivant le même choc d'offre, sont chiffrés selon deux
    physiques différentes.

    Le calibrage du levier de durée est un chantier distinct (dossier §A.1
    rang 4, items 19-20) : on ne le corrige pas ici. Mais §C.4 exige que les
    asymétries silencieuses soient supprimées ou DÉCLARÉES — ce test rend
    celle-ci visible en CI, et le test suivant la rend visible au lecteur.
    """
    from budget_simulator._seniors import chomage_seniors_ecart, offre_seniors_niveau_pib
    mesures = {'retraites': {'duree_cotisation': 40.0}}
    assert offre_seniors_niveau_pib(mesures, year) == 0.0
    assert chomage_seniors_ecart(mesures, year) == 0.0


def test_lasymetrie_duree_vs_age_est_declaree_dans_la_methodologie():
    """…et elle est écrite là où un lecteur la cherchera.

    Le tableau « Ce qui n'est délibérément PAS modélisé » listait quatre
    tentations écartées (éviction des jeunes, productivité, épargne,
    élasticité OFCE) et pas ce trou-là, qui est pourtant le seul à créer un
    écart de traitement entre deux leviers du même levier de réforme.
    """
    texte = _METHODO.read_text(encoding='utf-8')
    assert 'duree de cotisation' in texte and 'Canal emploi' in texte, \
        "METHODOLOGIE.md ne declare pas l'asymetrie duree <-> age du canal emploi"
