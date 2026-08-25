"""Tests-propriétés v0.6.1 — la croissance potentielle est lue À L'IDENTIQUE
par les trois blocs qui s'en servent (I6).

Contexte (dossier de sourcing v0.6.1, § I6 — bug PRÉ-EXISTANT, pas une
nouveauté du chantier retraites) :

- ``engine/growth.py`` calculait la croissance réelle à partir de
  ``base_params['croissance_potentielle'] + _potential_growth_bonus`` ;
- ``engine/unemployment.py`` mesurait l'écart d'Okun contre
  ``base_params['croissance_potentielle']`` **seul** ;
- ``engine/orchestrator.py`` mettait à jour l'output gap contre
  ``base_params['croissance_potentielle']`` **seul**.

Conséquence : tout bonus d'offre (``SUPPLY_EFFECTS`` : recherche, éducation,
transition, rénovation) apparaissait aux yeux d'Okun comme une croissance
**de demande** non désirée. L'écart ouvert chaque année vaut
``okun × bonus`` et la convergence NAIRU (``u = 0,94·u + 0,06·nairu``)
l'accumule vers un état stationnaire ``0,94/0,06 = 15,67`` fois plus grand :
avec ``okun = −0,35`` et le bonus plafonné à ±0,20 pt, **±1,10 pt de chômage
permanent** — et symétriquement un output gap permanent de ±0,20 pt qui
alimente ensuite la courbe de Phillips et le choix du multiplicateur.

Un choc d'OFFRE déplace le PIB potentiel : il ne doit créer **ni** écart
d'Okun **ni** output gap. C'est le sens de la correction : les trois lectures
passent désormais par ``croissance_potentielle_totale()``.

Périmètre : le canal emploi seniors (lot I7-I10) n'existe pas encore. L'état
dédié ``_labour_supply_bonus`` est créé ici, **initialisé à 0,0 et jamais
alimenté par le moteur** — les tests qui l'exercent l'injectent explicitement,
via un double de test qui simule le futur producteur SANS préjuger de sa
calibration (aucune valeur de calibration n'est inventée ici, cf. § B.1 du
dossier). Le piège que cet état dédié évite est documenté au § I6 : passer par
``base_params['croissance_potentielle']`` ferait écrêter le canal par le clip
[0,007 ; 0,012] de ``update_potential_growth`` **et** le rendrait permanent
par hystérèse, alors qu'il doit être transitoire.

Sens de la correction (§ C.5) : neutre par construction. Elle retire un bonus
de chômage aux programmes qui investissent dans l'offre (recherche, éducation,
transition) et retire symétriquement la pénalité de chômage aux programmes qui
coupent ces mêmes budgets. Aucun bord n'y gagne : l'artefact jouait dans les
deux sens, proportionnellement au signe du bonus d'offre.
"""
import inspect
import re

import pytest

from budget_simulator.engine.growth import GrowthMixin
from budget_simulator.engine.orchestrator import OrchestratorMixin
from budget_simulator.engine.unemployment import UnemploymentMixin
from budget_simulator.simulator import BudgetSimulatorV45

# Plafond conventionnel du bonus d'offre. COUPLAGE MANUEL ASSUMÉ : la borne
# vit en littéral inline dans ``update_potential_growth``
# (``np.clip(..., -0.002, 0.002)``, growth.py) et non dans ``constants.py`` —
# elle n'est donc pas importable. Conséquence si le plafond moteur changeait
# sans que cette ligne suive : ces tests injecteraient une valeur simplement
# plus faible que le plafond, donc ils resteraient VALIDES (propriété
# d'algèbre vraie pour tout bonus), seulement moins exigeants. Pas de faux
# vert possible. L'extraction de la borne vers constants.py est un item de
# calibration, hors périmètre de cette correction d'algèbre.
BONUS_MAX = 0.002

# Amplificateur de la convergence NAIRU : u = 0,94·u + 0,06·nairu ⇒ un écart
# CONSTANT d de chômage ajouté chaque année converge vers d × 0,94/0,06.
AMPLIFICATION_NAIRU = 0.94 / 0.06  # ≈ 15,67

# Tolérance « neutralité stricte » : 0,01 pt de chômage / d'output gap.
TOL_PT = 0.01


#: Les deux termes d'offre que la croissance potentielle totale doit agréger.
#: ``_potential_growth_bonus`` est l'offre STRUCTURELLE déjà livrée
#: (SUPPLY_EFFECTS : recherche, éducation, transition, rénovation) ;
#: ``_labour_supply_bonus`` est l'état dédié à l'offre de TRAVAIL, créé par ce
#: lot, encore alimenté par personne. La correction doit valoir pour les deux :
#: c'est une propriété du lecteur, pas du canal qui l'alimente.
TERMES_OFFRE = ('_potential_growth_bonus', '_labour_supply_bonus')


def _double_injectant(etat):
    """Double de test : joue le rôle d'un producteur de choc d'offre en
    écrivant un bonus CONSTANT dans ``etat``, À LA PLACE EXACTE du producteur
    réel dans la boucle annuelle.

    Les deux termes d'offre ont des producteurs distincts, et le double doit
    se substituer à chacun au bon moment :
    - ``_potential_growth_bonus`` → ``update_potential_growth``, qui CLÔT
      l'année (offre structurelle, SUPPLY_EFFECTS) ;
    - ``_labour_supply_bonus`` → ``update_labour_supply``, qui OUVRE l'année
      (canal emploi seniors, livré par le lot I7-I10 : le double n'en tient
      plus lieu, il s'AJOUTE à lui pour que la paire avec/sans isole le seul
      bonus injecté).

    La valeur injectée est le PLAFOND conventionnel du moteur, PAS une
    calibration : ces tests mesurent une propriété d'algèbre, ils ne
    chiffrent aucune réforme (§ B.1 du dossier — ne rien combler par
    invention).
    """

    class _Double(BudgetSimulatorV45):
        def update_potential_growth(self, growth, year):
            super().update_potential_growth(growth, year)
            if etat == '_potential_growth_bonus':
                self._potential_growth_bonus = BONUS_MAX

        def update_labour_supply(self, year):
            super().update_labour_supply(year)
            if etat == '_labour_supply_bonus':
                self._labour_supply_bonus += BONUS_MAX

    _Double.__name__ = f'SimulateurAvecBonus{etat}'
    return _Double


def _simuler(cls, mesures=None, debt_drag=None):
    """Lance une simulation 10 ans et renvoie (résultats, résultats détaillés).

    ``debt_drag=0.0`` neutralise le SEUL canal par lequel le NIVEAU du PIB
    rétroagit légitimement sur la croissance de demande (``calculate_growth``
    : ``croissance += debt_drag × (dette/PIB − 0,9)``). C'est l'isolation
    demandée par le test-propriété P1 du dossier.
    """
    sim = cls(periods=10, mesures=mesures or {})
    if debt_drag is not None:
        sim.economic_coeffs['debt_drag'] = debt_drag
    df, detail, _ = sim.simulate()
    return df, detail


def _paire_avec_sans(etat, mesures=None, debt_drag=None):
    """Deux simulations identiques, la seconde avec un bonus d'offre au
    plafond écrit dans ``etat``.

    GARDE INTÉGRÉE : le bonus doit réellement déplacer le PIB. Sans elle, un
    état d'offre que PERSONNE ne lit ferait passer toutes les propriétés de
    neutralité qui suivent — pour la mauvaise raison.
    """
    sans = _simuler(BudgetSimulatorV45, mesures, debt_drag)
    avec = _simuler(_double_injectant(etat), mesures, debt_drag)

    assert avec[0]['PIB'].iloc[-1] > sans[0]['PIB'].iloc[-1] * 1.005, (
        f"le bonus écrit dans {etat} ne déplace pas le PIB : il n'est pas "
        "consommé par la croissance, les tests de neutralité ne prouveraient rien")

    return sans, avec


def _ecart_max(serie_a, serie_b):
    return max(abs(a - b) for a, b in zip(serie_a, serie_b))


# ---------------------------------------------------------------------------
# 1. L'état dédié et le lecteur unique existent
# ---------------------------------------------------------------------------

def test_etat_dedie_offre_travail_initialise_a_zero_et_reinitialise():
    """``_labour_supply_bonus`` est un état d'instance à part entière.

    Il ne doit PAS vivre dans ``base_params['croissance_potentielle']``
    (clippée [0,007 ; 0,012] et mutée en place par l'hystérèse : le canal y
    serait écrêté ET rendu permanent), ni être confondu avec
    ``_potential_growth_bonus`` (qui porte SUPPLY_EFFECTS et son propre
    plafond). Comme tout état muté pendant ``simulate()``, il doit être remis
    à zéro par ``_reset_state`` — sinon deux appels successifs à
    ``simulate()`` ne donnent pas le même résultat.
    """
    sim = BudgetSimulatorV45(periods=1)
    assert sim._labour_supply_bonus == 0.0

    sim._labour_supply_bonus = 0.05
    sim._reset_state()
    assert sim._labour_supply_bonus == 0.0


def test_croissance_potentielle_totale_somme_les_trois_termes():
    """Le lecteur unique = tendanciel + offre structurelle + offre de travail."""
    sim = BudgetSimulatorV45(periods=1)
    sim.base_params['croissance_potentielle'] = 0.010
    sim._potential_growth_bonus = 0.0015
    sim._labour_supply_bonus = 0.0004

    assert sim.croissance_potentielle_totale() == pytest.approx(0.0119, abs=1e-12)


def test_croissance_potentielle_totale_ne_mute_rien():
    """Lecteur PUR : il ne doit pas reverser les bonus dans base_params
    (le clip [0,007 ; 0,012] de l'hystérèse les écrêterait et les figerait)."""
    sim = BudgetSimulatorV45(periods=1)
    sim.base_params['croissance_potentielle'] = 0.010
    sim._potential_growth_bonus = BONUS_MAX
    sim._labour_supply_bonus = BONUS_MAX

    sim.croissance_potentielle_totale()

    assert sim.base_params['croissance_potentielle'] == 0.010
    assert sim._potential_growth_bonus == BONUS_MAX
    assert sim._labour_supply_bonus == BONUS_MAX


# ---------------------------------------------------------------------------
# 2. Okun : un choc d'offre pur ne déplace pas le chômage
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('etat', ['_potential_growth_bonus', '_labour_supply_bonus'])
@pytest.mark.parametrize('signe', [1.0, -1.0])
def test_okun_neutre_sur_un_choc_offre_pur(etat, signe):
    """Économie au NAIRU croissant EXACTEMENT à son potentiel total ⇒ elle y
    reste, quel que soit le terme d'offre qui porte le bonus et son signe.

    Avant correction, Okun comparait la croissance à la seule composante
    tendancielle : le bonus d'offre était compté comme un écart conjoncturel
    et déplaçait le chômage de ``okun × bonus`` dès la première année.
    """
    sim = BudgetSimulatorV45(periods=1)
    setattr(sim, etat, signe * BONUS_MAX)
    nairu = sim.base_params['chomage_nairu']

    croissance = sim.croissance_potentielle_totale()
    resultat = sim.calculate_unemployment(croissance, nairu, year=1)

    assert resultat == pytest.approx(nairu, abs=1e-12)


def test_okun_reste_sensible_a_un_vrai_ecart_conjoncturel():
    """Contre-épreuve : la correction ne débranche pas la loi d'Okun.

    Un point de croissance AU-DESSUS du potentiel total reste un écart
    conjoncturel et fait bien baisser le chômage de ``okun × écart``
    (amorti la première année par la convergence NAIRU, facteur 0,94).
    """
    sim = BudgetSimulatorV45(periods=1)
    sim._potential_growth_bonus = BONUS_MAX
    nairu = sim.base_params['chomage_nairu']
    okun = sim.economic_coeffs['okun']
    ecart = 0.01

    resultat = sim.calculate_unemployment(
        sim.croissance_potentielle_totale() + ecart, nairu, year=1)

    assert resultat == pytest.approx(nairu + 0.94 * okun * ecart, abs=1e-12)


def test_convergence_nairu_ne_derive_plus_pour_un_levier_offre_existant():
    """Le levier d'offre EXISTANT ``recherche_publique`` ne creuse plus
    d'écart d'Okun permanent — et le test chiffre l'artefact retiré.

    Le bonus est construit par le VRAI chemin de code
    (``update_potential_growth`` appelée jusqu'à épuisement du délai de
    5 ans de ``SUPPLY_EFFECTS['recherche_publique']``), pas injecté à la main.
    On itère ensuite la récurrence du chômage jusqu'à convergence, avec une
    croissance égale au potentiel total : le seul moteur de dérive possible
    est l'écart d'Okun mal mesuré.
    """
    sim = BudgetSimulatorV45(periods=1, mesures={'recherche_publique': {'budget': 20.0}})
    for annee in range(1, 8):
        sim.update_potential_growth(0.012, annee)

    bonus = sim._potential_growth_bonus
    assert bonus > 0.0001, f"le levier d'offre doit produire un bonus, obtenu {bonus}"

    nairu = sim.base_params['chomage_nairu']
    okun = sim.economic_coeffs['okun']
    croissance = sim.croissance_potentielle_totale()

    chomage = nairu
    for annee in range(1, 300):
        chomage = sim.calculate_unemployment(croissance, chomage, year=annee)

    assert abs(chomage - nairu) * 100 < TOL_PT, (
        f"chômage de convergence {chomage*100:.3f} % vs NAIRU {nairu*100:.3f} %")

    # Contre-épreuve : l'ancienne algèbre (écart mesuré contre la seule
    # composante tendancielle) aurait ouvert un écart CONSTANT okun × bonus
    # chaque année, amplifié 15,67 fois par la convergence NAIRU.
    artefact_pt = abs(okun * bonus * AMPLIFICATION_NAIRU) * 100
    assert artefact_pt > 0.10, (
        f"l'artefact corrigé doit être significatif, mesuré {artefact_pt:.3f} pt")


# ---------------------------------------------------------------------------
# 3. Bout en bout : ni chômage ni output gap ne bougent sur un choc d'offre
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('etat', TERMES_OFFRE)
def test_p1_chomage_insensible_au_choc_offre_age_65(etat):
    """Test-propriété P1 du dossier (§ I6).

    Deux simulations du scénario ``age_depart = 65``, la seconde avec un bonus
    d'offre au plafond, canal de dette neutralisé. Un choc d'offre doit
    déplacer le PIB, JAMAIS le chômage — l'écart doit rester sous 0,01 pt sur
    les dix années. Mesuré après correction : 0,00 pt.

    Avant correction ce même bonus creusait 0,51 pt d'écart de chômage à
    l'horizon 2035 (et 1,10 pt à convergence longue) : de quoi faire gagner
    des emplois à un programme uniquement parce qu'il touche à l'offre.
    """
    (sans, _), (avec, _) = _paire_avec_sans(
        etat, {'retraites': {'age_depart': 65.0}}, debt_drag=0.0)

    assert _ecart_max(sans['Chômage %'], avec['Chômage %']) < TOL_PT


@pytest.mark.parametrize('etat', TERMES_OFFRE)
def test_chomage_insensible_au_choc_offre_en_baseline(etat):
    """Même propriété sans aucune mesure : l'artefact était indépendant du
    scénario, il naissait de la seule présence d'un bonus d'offre."""
    (sans, _), (avec, _) = _paire_avec_sans(etat, debt_drag=0.0)

    assert _ecart_max(sans['Chômage %'], avec['Chômage %']) < TOL_PT


@pytest.mark.parametrize('etat', TERMES_OFFRE)
def test_output_gap_insensible_au_choc_offre(etat):
    """L'output gap est un écart au POTENTIEL : un choc d'offre déplace les
    deux termes ensemble et ne doit donc pas l'ouvrir.

    Avant correction l'output gap se décalait de +0,19 pt à l'horizon — écart
    qui alimentait ensuite la courbe de Phillips (inflation) et le choix du
    multiplicateur budgétaire (``eco_state['output_gap']``).
    """
    (_, sans), (_, avec) = _paire_avec_sans(etat, debt_drag=0.0)

    assert _ecart_max(sans['Output_Gap %'], avec['Output_Gap %']) < TOL_PT


@pytest.mark.parametrize('etat', TERMES_OFFRE)
def test_residuel_en_regime_complet_est_le_seul_canal_de_dette(etat):
    """En régime complet il reste un petit écart de chômage — il est
    ÉCONOMIQUE, pas un artefact, et ce test le prouve en le faisant
    disparaître.

    Un choc d'offre enrichit l'économie : le PIB nominal monte, le ratio
    dette/PIB baisse, et le ``debt_drag`` de ``calculate_growth``
    (``croissance += debt_drag × (dette/PIB − 0,9)``, Reinhart-Rogoff amendé
    Herndon et al. 2014) mord moins. Cette croissance-là est bien de la
    DEMANDE : Okun doit la voir, et le chômage doit baisser un peu. C'est le
    comportement recherché, pas celui qui vient d'être corrigé.

    Le test verrouille les deux faces : le résidu est petit devant l'artefact
    retiré (0,51 pt), et il tombe EXACTEMENT à zéro dès que le canal de dette
    est neutralisé — donc il ne reste aucune fuite d'Okun.
    """
    (sans_regime, _), (avec_regime, _) = _paire_avec_sans(etat)
    (sans_isole, _), (avec_isole, _) = _paire_avec_sans(etat, debt_drag=0.0)

    residuel = _ecart_max(sans_regime['Chômage %'], avec_regime['Chômage %'])

    assert residuel < 0.10, (
        f"résidu {residuel:.3f} pt : trop grand pour le seul canal de dette")
    assert _ecart_max(sans_isole['Chômage %'], avec_isole['Chômage %']) < TOL_PT


@pytest.mark.parametrize('etat', TERMES_OFFRE)
def test_choc_offre_ne_contamine_pas_la_croissance_potentielle_tendancielle(etat):
    """Piège du § I6 : un canal d'offre ne doit pas transiter par
    ``base_params['croissance_potentielle']``.

    S'il y transitait, le clip [0,007 ; 0,012] de ``update_potential_growth``
    l'écrêterait ET l'hystérèse le rendrait PERMANENT, alors qu'un canal
    d'offre de travail est transitoire. Preuve : la trajectoire de la
    composante tendancielle est identique avec et sans bonus.
    """
    (_, sans), (_, avec) = _paire_avec_sans(etat)

    assert list(sans['Croissance_Potentielle %']) == list(avec['Croissance_Potentielle %'])


@pytest.mark.parametrize('etat', TERMES_OFFRE)
def test_croissance_potentielle_totale_publiee_inclut_les_deux_termes(etat):
    """La colonne publiée ``Croissance_Potentielle_Totale %`` doit être la
    somme réellement consommée par le moteur, sinon la trajectoire exportée
    ne se raccorde plus à la croissance simulée."""
    (_, sans), (_, avec) = _paire_avec_sans(etat)

    ecarts = [a - b for a, b in zip(
        avec['Croissance_Potentielle_Totale %'], sans['Croissance_Potentielle_Totale %'])]

    # Le bonus est écrit en fin d'année : la 1ʳᵉ ligne (2025, hors boucle
    # macro) reste nue, toutes les suivantes portent le bonus.
    assert ecarts[0] == 0.0
    assert all(e == pytest.approx(BONUS_MAX * 100, abs=1e-9) for e in ecarts[1:])


# ---------------------------------------------------------------------------
# 4. Méta-gardes : les trois lectures ne peuvent plus diverger en silence
#
# PORTÉE / LIMITE (à ne pas sur-vendre, cf. `test_mixin_architecture.py`) :
# la détection est SYNTAXIQUE. Elle ne matche que la lecture LITTÉRALE
# ``base_params['croissance_potentielle']`` dans le corps des méthodes
# concernées. Y échapperaient une lecture via une variable intermédiaire,
# ``base_params.get('croissance_potentielle')`` ou une clé construite
# dynamiquement — aucune n'existe dans le code actuel (vérifié), donc
# l'invariant tient réellement aujourd'hui et ces gardes le MAINTIENNENT.
# Ce sont des anti-régressions du motif courant, pas une preuve d'absence.
# Corollaire assumé : un commentaire qui citerait le littéral dans une de
# ces méthodes ferait rougir la garde. C'est voulu — la formulation
# explicative appartient aux docstrings de module, pas au corps du calcul.
# ---------------------------------------------------------------------------

_LECTURE_NUE = "base_params['croissance_potentielle']"


def test_okun_ne_lit_plus_la_composante_tendancielle_nue():
    """Anti-régression I6 : le bug était une lecture DIVERGENTE, pas une
    mauvaise valeur. Seule une garde sur la source empêche qu'un futur
    refactor réintroduise la lecture nue dans le bloc chômage."""
    source = inspect.getsource(UnemploymentMixin.calculate_unemployment)

    assert 'croissance_potentielle_totale()' in source
    assert _LECTURE_NUE not in source


def test_croissance_lit_le_potentiel_total_par_le_lecteur_unique():
    source = inspect.getsource(GrowthMixin.calculate_growth)

    assert 'croissance_potentielle_totale()' in source
    assert _LECTURE_NUE not in source


def test_output_gap_ne_se_mesure_plus_contre_la_composante_tendancielle_nue():
    """L'orchestrateur lit légitimement la composante tendancielle nue pour
    l'amorçage et pour le reporting ; ce qui est interdit, c'est de s'en
    servir comme RÉFÉRENCE d'un écart (``growth - ...``)."""
    source = inspect.getsource(OrchestratorMixin.simulate)

    ecarts_nus = re.findall(r'-\s*self\.' + re.escape(_LECTURE_NUE), source)

    assert ecarts_nus == []
    assert 'croissance_potentielle_totale()' in source
