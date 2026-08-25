"""v0.6.1 lot 6 — canaux Gini : sources réelles, symétrie, périmètre (I27 à I30).

Ce que le lot corrige, et pourquoi c'est un enjeu de repo PUBLIC :

* **I27 — éducation.** Le handler `_apply_education` n'émettait aucune clé
  `gini` : la mesure tombait dans un *fallback générique* de
  `engine/micro_impacts.py` qui retranchait `0,04 × (dépense / PIB)`
  **si et seulement si la dépense augmentait**. Trois défauts cumulés :
  le coefficient 0,04 n'a AUCUNE source (0 occurrence dans
  `METHODOLOGIE.md`) ; la règle est ASYMÉTRIQUE (une COUPE d'éducation
  émettait exactement 0, ce qui avantage silencieusement les programmes de
  coupe) ; et l'émission était RÉCURRENTE, donc une politique constante
  faisait dériver le Gini linéairement avec l'horizon.
  Le fond du sujet n'est pas le coefficient mais le PÉRIMÈTRE : le Gini
  affiché est celui du **niveau de vie** (revenu disponible par unité de
  consommation, INSEE) ; les dépenses d'éducation n'y entrent pas. L'effet
  mécanique direct est **zéro par construction de l'indicateur**, pas par
  oubli — et c'est ce que le handler doit dire explicitement.

* **I28 — taxe carbone.** Le moteur était exactement au DOUBLE du
  coefficient dérivable des deux évaluations françaises publiées
  (Douenne 2020 ; Note IPP n° 34), et citait une source INTROUVABLE
  (« OFCE 2019 "taxe carbone régressive" »).

* **I29 — rénovation énergétique.** Même signe mais ~1,7× trop faible, et
  citait une source INTROUVABLE (« ADEME 2024 »).

* **I30 — recherche publique.** L'effet reste 0,0 — mais le commentaire
  qui le justifiait (« R&D = emplois qualifiés (favorise classes moyennes
  supérieures) ») AFFIRMAIT une incidence distributive sans source. Le
  motif réel est un trou de la littérature + une convention comptable
  INSEE (la diffusion de la recherche est classée en consommation
  COLLECTIVE, non individualisable).

PORTÉE / LIMITE des méta-gardes de ce fichier : elles sont SYNTAXIQUES
(lecture de l'AST ou du texte source). Elles empêchent la réapparition
d'une forme connue de défaut ; elles ne prouvent pas l'absence de toute
variante future. Même contrat que `tests/test_mixin_architecture.py`.

CE QUE CE LOT NE CORRIGE PAS, ET LE DIT : le mécanisme d'agrégation
`gini_cible_cumul += …` accumule un FLUX annuel. Trois handlers émettent
encore une contribution récurrente non convergente ; ils sont ÉNUMÉRÉS et
verrouillés par `test_carte_des_emissions_gini_recurrentes`, pas corrigés
(chantier v0.7, § B.4-33 du dossier de sourcing : « ne pas bricoler »).
"""
from __future__ import annotations

import ast
import inspect
import json
import sys
from pathlib import Path

import pytest

from budget_simulator import constants
from budget_simulator.constants import (
    CARBONE_PRIX_REFERENCE_EUR_T,
    GINI_FALLBACK_IMPOT_SOCIETES_NON_SOURCE,
    GINI_RENOVATION_PAR_MD_EUR,
    GINI_TAXE_CARBONE_PAR_EUR_TONNE,
    POLICY_START_YEAR,
)
from budget_simulator.engine import micro_impacts
from budget_simulator.handlers import investissements
from budget_simulator.simulator import BudgetSimulatorV45

ROOT = Path(__file__).resolve().parent.parent
PIB = 2994.0

# Fourchettes des tests-propriétés du dossier de sourcing v0.6.1 § I28/I29.
# Elles encodent la LITTÉRATURE (robustesse sur 4 spécifications pour le
# carbone, 3 profils de déciles pour la rénovation), pas l'implémentation :
# si un recalibrage les fait rougir, c'est le recalibrage qu'il faut
# discuter, pas les bornes qu'il faut élargir.
CARBONE_PAS_EUR_T = 50.0
CARBONE_CIBLE = (0.0009, 0.0011)
RENOVATION_PAS_MD_EUR = 5.0
RENOVATION_CIBLE = (-0.0019, -0.0017)


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------

def _sim() -> BudgetSimulatorV45:
    """Simulateur neuf (l'état de gating `_is_first_year_change` doit l'être)."""
    sim = BudgetSimulatorV45(periods=1)
    sim.debug_logs = []
    return sim


def _gini_transition(sim, *, carbone=None, renovation=0.0, investissement=0.0,
                     year=POLICY_START_YEAR) -> float:
    """Impact Gini émis par `_apply_transition_ecologique` pour ces paramètres."""
    params = {
        'investissement': investissement,
        'taxe_carbone': CARBONE_PRIX_REFERENCE_EUR_T if carbone is None else carbone,
        'renovation': renovation,
    }
    _, _, impacts = sim._apply_transition_ecologique(
        {'id': 'transition_ecologique'}, params, year, PIB, 0.01, 0.076)
    return impacts['gini']


def _impacts_education(sim, *, budget=65.0, enseignants=0.0, salaires=0.0,
                       year=POLICY_START_YEAR) -> dict:
    _, _, impacts = sim._apply_education(
        {'id': 'education'},
        {'budget': budget, 'enseignants': enseignants, 'salaires': salaires},
        year, PIB, 0.01, 0.076)
    return impacts


def _cumul_gini(mesures: dict, periods: int = 10) -> float:
    """Décalage Gini cumulé (avant arrondi d'affichage) d'une simulation.

    `df['Gini']` est arrondi à 3 décimales : inutilisable pour une propriété
    de symétrie à 1e-5 près. On lit l'état interne, qui EST la grandeur que
    les handlers alimentent."""
    sim = BudgetSimulatorV45(periods=periods, mesures=mesures)
    sim.simulate()
    return float(sim.gini_cible_cumul)


def _serie_emissions(mesures: dict, periods: int) -> list[float]:
    """Série année par année des impacts Gini agrégés bruts."""
    serie: list[float] = []
    original = micro_impacts.MicroImpactsMixin.calculate_gini_impact

    def espion(self, impacts, gdp):
        valeur = original(self, impacts, gdp)
        serie.append(valeur)
        return valeur

    micro_impacts.MicroImpactsMixin.calculate_gini_impact = espion
    try:
        BudgetSimulatorV45(periods=periods, mesures=mesures).simulate()
    finally:
        micro_impacts.MicroImpactsMixin.calculate_gini_impact = original
    return serie


def _source(fonction) -> str:
    return inspect.getsource(fonction)


def _constantes_numeriques(fonction, noms_cibles: set[str]) -> list[float]:
    """Littéraux numériques présents dans les expressions affectées à `noms_cibles`.

    LÈVE si aucune des cibles n'est trouvée : une garde qui ne trouve plus
    son objet doit échouer bruyamment, jamais passer vert par défaut."""
    arbre = ast.parse(inspect.getsource(fonction).lstrip())
    trouvees: set[str] = set()
    litteraux: list[float] = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Assign):
            continue
        for cible in noeud.targets:
            if isinstance(cible, ast.Name) and cible.id in noms_cibles:
                trouvees.add(cible.id)
                for sous in ast.walk(noeud.value):
                    if isinstance(sous, ast.Constant) and isinstance(sous.value, (int, float)) \
                            and not isinstance(sous.value, bool):
                        litteraux.append(float(sous.value))
    manquantes = noms_cibles - trouvees
    if manquantes:
        raise AssertionError(
            f"variables {sorted(manquantes)} introuvables dans "
            f"{fonction.__qualname__} — la garde ne mesure plus son objet, "
            "elle a été renommée ou supprimée : la remettre à jour, pas la "
            "désarmer.")
    return litteraux


def _ajoute_snapshots_au_path() -> None:
    """Rend `tests/snapshots/` importable, sans empiler des doublons dans
    `sys.path` à chaque appel (deux tests en ont besoin)."""
    chemin = str(ROOT / 'tests' / 'snapshots')
    if chemin not in sys.path:
        sys.path.insert(0, chemin)


def _bloc_gini(fonction) -> str:
    """Extrait le bloc `=== GINI …` d'un handler, jusqu'à l'assemblage `impacts`.

    Extraction BORNÉE : si l'un des deux marqueurs disparaît, la fonction
    LÈVE au lieu de renvoyer une chaîne vide qui rendrait toute garde
    vertement inutile."""
    lignes = _source(fonction).splitlines()
    debuts = [i for i, l in enumerate(lignes) if '=== GINI' in l]
    if not debuts:
        raise AssertionError(
            f"marqueur '=== GINI' absent de {fonction.__qualname__} : "
            "l'extracteur ne trouve plus son objet")
    debut = debuts[0]
    fins = [i for i, l in enumerate(lignes[debut:], debut)
            if l.strip().startswith('impacts = {')]
    if not fins:
        raise AssertionError(
            f"marqueur 'impacts = {{' absent après le bloc Gini de "
            f"{fonction.__qualname__}")
    return '\n'.join(lignes[debut:fins[0]])


def _domaines_publies(measure_id: str) -> dict[str, tuple[float, ...]]:
    """Amplitude publiée de chaque paramètre numérique d'un levier.

    Source : `policy_measures.json`, le contrat que l'UI expose au public —
    le bon périmètre pour prouver qu'une branche est morte « pour toutes les
    valeurs qu'un utilisateur peut réellement produire ». `PARAM_DOMAINS`
    ne couvre que deux leviers, il ne conviendrait pas ici."""
    config = json.loads((ROOT / 'policy_measures.json').read_text(encoding='utf-8'))
    for mesure in config['mesures']:
        if mesure['id'] != measure_id:
            continue
        domaines = {}
        for nom, cfg in mesure.get('parametres', {}).items():
            if not isinstance(cfg, dict):
                continue
            valeurs = tuple(sorted({v for v in (cfg.get('min'), cfg.get('valeur_defaut'),
                                                cfg.get('max'))
                                    if isinstance(v, (int, float))
                                    and not isinstance(v, bool)}))
            if valeurs:
                domaines[nom] = valeurs
        return domaines
    return {}


def _chaines_du_fallback() -> set[str]:
    """`measure_id` encore cités en dur dans `calculate_gini_impact`."""
    arbre = ast.parse(_source(micro_impacts.MicroImpactsMixin.calculate_gini_impact).lstrip())
    return {n.value for n in ast.walk(arbre)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)}


# ===========================================================================
# 1. I28 — taxe carbone : le coefficient est celui des sources, pas son double
# ===========================================================================

def test_gini_carbone_50_euros_dans_la_fourchette_sourcee():
    """+50 €/tCO2 déplace le Gini de +0,0010 [0,0009 ; 0,0011].

    Dérivation : Douenne (2020) et Note IPP n° 34 évaluent le passage
    22 → 44,6 €/tCO2 (4,1 Md€/an de recettes, hors électricité) ; taux
    d'effort D1 = 0,55 % du revenu disponible contre D10 = 0,20-0,21 %,
    soit un coefficient de concentration de la taxe ≈ +0,12 à +0,13, robuste
    sur 4 spécifications, et +1,1 × 10⁻⁴ de Gini par Md€ de recettes.
    Le taux de conversion IPP (0,181 Md€ par €/tCO2) donne les +0,0010.
    """
    bas, haut = CARBONE_CIBLE
    obtenu = _gini_transition(_sim(),
                              carbone=CARBONE_PRIX_REFERENCE_EUR_T + CARBONE_PAS_EUR_T)
    assert bas <= obtenu <= haut, (
        f"+{CARBONE_PAS_EUR_T:.0f} EUR/tCO2 doit donner un Gini dans "
        f"[{bas} ; {haut}] (Douenne 2020 + Note IPP n° 34), obtenu {obtenu:.6f}")


def test_gini_carbone_est_la_moitie_de_la_v060():
    """Le sens de la correction : la pénalité Gini du carbone est DIVISÉE PAR 2.

    Le moteur v0.6.0 émettait 0,002 pour +50 €/t, soit exactement le double
    de ce que les deux sources françaises permettent de dériver. Ce test
    fixe la DIRECTION (§ C.5 du dossier : divise par deux la pénalité Gini
    des programmes écologistes) pour qu'un retour en arrière soit visible."""
    v060 = 0.002 * CARBONE_PAS_EUR_T / 50  # formule littérale de la v0.6.0
    obtenu = _gini_transition(_sim(),
                              carbone=CARBONE_PRIX_REFERENCE_EUR_T + CARBONE_PAS_EUR_T)
    assert obtenu == pytest.approx(v060 / 2, rel=1e-12)


@pytest.mark.parametrize("ecart", [-40.0, -20.0, -5.0, 5.0, 20.0, 40.0])
def test_gini_carbone_lineaire_et_symetrique(ecart):
    """Le canal carbone est strictement linéaire et symétrique autour de 44,6.

    Symétrie : une BAISSE du prix du carbone doit rendre exactement ce qu'une
    hausse de même ampleur prélève. C'est la propriété que le fallback
    éducation violait (`if > 0`) et qu'aucun canal Gini ne doit violer."""
    attendu = GINI_TAXE_CARBONE_PAR_EUR_TONNE * ecart
    obtenu = _gini_transition(_sim(), carbone=CARBONE_PRIX_REFERENCE_EUR_T + ecart)
    assert obtenu == pytest.approx(attendu, abs=1e-15)
    miroir = _gini_transition(_sim(), carbone=CARBONE_PRIX_REFERENCE_EUR_T - ecart)
    assert obtenu == pytest.approx(-miroir, abs=1e-15)


def test_gini_carbone_nul_au_statu_quo():
    """Prix inchangé (44,6 €/t) ⇒ aucun effet Gini. Pas de dérive de référence."""
    assert _gini_transition(_sim()) == 0.0


# ===========================================================================
# 2. I29 — rénovation énergétique : coefficient ×1,7
# ===========================================================================

def test_gini_renovation_5_mds_dans_la_fourchette_sourcee():
    """+5 Md€ de rénovation déplacent le Gini de −0,0017 [−0,0019 ; −0,0017].

    Dérivation : ONRE/SDES (février 2023) mesure que MaPrimeRénov' concentre
    60 % des économies d'énergie sur les déciles D1-D4 ; l'ONPE (édition
    2024, données Anah 2023) relève que 67 % des 505 126 dossiers engagés
    concernent des ménages modestes et très modestes. D'où un coefficient de
    concentration C ≈ −0,25 [−0,24 ; −0,26], robuste sur 3 profils de
    déciles compatibles avec la contrainte ONRE, soit −3,4 × 10⁻⁴ par Md€.

    HYPOTHÈSE DÉCLARÉE (le coefficient est DÉFENDABLE, jamais SOLIDE) :
    aucune publication ne ventile les MONTANTS par décile — on suppose que
    les euros suivent le profil des ÉCONOMIES D'ÉNERGIE. Hypothèse
    conservatrice : les taux de prise en charge plus élevés pour les ménages
    Bleu/Jaune rendraient le profil en euros PLUS pro-pauvres."""
    bas, haut = RENOVATION_CIBLE
    obtenu = _gini_transition(_sim(), renovation=RENOVATION_PAS_MD_EUR)
    assert bas <= obtenu <= haut, (
        f"+{RENOVATION_PAS_MD_EUR:.0f} Md EUR de rénovation doivent donner un "
        f"Gini dans [{bas} ; {haut}] (ONRE 2023 + ONPE 2024), "
        f"obtenu {obtenu:.6f}")


def test_gini_renovation_est_1_7_fois_la_v060():
    """Le sens de la correction : le gain Gini de la rénovation est AMPLIFIÉ.

    v0.6.0 : −0,001 pour +5 Md€ (soit −2,0 × 10⁻⁴/Md€). v0.6.1 :
    −3,4 × 10⁻⁴/Md€, même signe, 1,7× plus fort."""
    v060 = -0.001 * RENOVATION_PAS_MD_EUR / 5
    obtenu = _gini_transition(_sim(), renovation=RENOVATION_PAS_MD_EUR)
    assert obtenu / v060 == pytest.approx(1.7, abs=0.01)


@pytest.mark.parametrize("montant", [-30.0, -5.0, -1.0, 1.0, 5.0, 30.0])
def test_gini_renovation_lineaire_et_symetrique(montant):
    """Canal rénovation strictement linéaire et symétrique.

    Une COUPE des aides à la rénovation doit coûter exactement ce qu'une
    hausse de même ampleur rapporte — sinon les programmes de coupe
    bénéficient d'une asymétrie silencieuse."""
    attendu = GINI_RENOVATION_PAR_MD_EUR * montant
    obtenu = _gini_transition(_sim(), renovation=montant)
    assert obtenu == pytest.approx(attendu, abs=1e-15)
    miroir = _gini_transition(_sim(), renovation=-montant)
    assert obtenu == pytest.approx(-miroir, abs=1e-15)


def test_gini_transition_est_la_somme_de_ses_deux_canaux():
    """Aucun terme croisé caché : le Gini de la transition = carbone + rénovation."""
    sim = _sim()
    ensemble = _gini_transition(sim, carbone=CARBONE_PRIX_REFERENCE_EUR_T + 30,
                                renovation=12.0, investissement=20.0)
    attendu = (GINI_TAXE_CARBONE_PAR_EUR_TONNE * 30
               + GINI_RENOVATION_PAR_MD_EUR * 12.0)
    assert ensemble == pytest.approx(attendu, abs=1e-15)


def test_investissement_vert_seul_n_a_pas_d_effet_gini():
    """L'investissement vert n'a AUCUN canal Gini — et c'est délibéré.

    Aucune source ne donne l'incidence distributive d'un euro
    d'investissement vert (≠ des aides à la rénovation, qui sont un
    transfert monétaire aux ménages). On ne fabrique pas le chiffre."""
    assert _gini_transition(_sim(), investissement=50.0) == 0.0


# ===========================================================================
# 3. I27 — éducation : zéro EXPLICITE, symétrique, non récurrent
# ===========================================================================

def test_education_emet_une_cle_gini_explicite():
    """`_apply_education` émet `gini` — le seul handler de dépense qui ne le
    faisait pas, d'où sa chute dans le fallback générique."""
    impacts = _impacts_education(_sim(), budget=80.0)
    assert 'gini' in impacts, (
        "sans clé 'gini' explicite, la mesure retombe dans le fallback "
        "générique de micro_impacts.py — c'est exactement le défaut I27")
    assert impacts['gini'] == 0.0


@pytest.mark.parametrize("budget,enseignants,salaires", [
    (80.0, 0.0, 0.0), (50.0, 0.0, 0.0),
    (65.0, 60000.0, 0.0), (65.0, -60000.0, 0.0),
    (65.0, 0.0, 15.0), (65.0, 0.0, -15.0),
    (85.0, 60000.0, 15.0), (45.0, -60000.0, -15.0),
])
def test_education_gini_nul_dans_les_deux_sens(budget, enseignants, salaires):
    """Zéro PAR CONSTRUCTION de l'indicateur, quel que soit le sens et le levier.

    Le Gini publié est celui du NIVEAU DE VIE (revenu disponible par unité de
    consommation, INSEE) : une dépense d'éducation, qui est un transfert EN
    NATURE, n'entre pas dans son assiette. Sur l'indicateur ÉLARGI — qui
    n'est pas celui du site — l'effet existe mais reste du second ordre :
    déplacer le Gini élargi de 0,01 demanderait ≈ 72 Md€, soit +70 % du
    budget de l'éducation nationale."""
    impacts = _impacts_education(_sim(), budget=budget, enseignants=enseignants,
                                 salaires=salaires)
    assert impacts['gini'] == 0.0


@pytest.mark.parametrize("delta", [5.0, 15.0, 25.0])
def test_symetrie_stricte_education_sur_simulation_complete(delta):
    """+X et −X Md€ d'éducation ⇒ ΔGini == 0 dans les DEUX cas.

    C'est le test-propriété central de I27. Avant correction, +15 Md€
    donnaient −0,000197 par an tandis que −15 Md€ donnaient exactement 0 :
    un avantage silencieux aux programmes de coupe."""
    statu_quo = _cumul_gini({})
    hausse = _cumul_gini({'education': {'budget': 65.0 + delta}})
    baisse = _cumul_gini({'education': {'budget': 65.0 - delta}})
    assert hausse == statu_quo, (
        f"+{delta} Md EUR d'éducation déplacent encore le Gini "
        f"({hausse - statu_quo:+.6f}) : le fallback non sourcé survit")
    assert baisse == statu_quo, (
        f"-{delta} Md EUR d'éducation déplacent le Gini "
        f"({baisse - statu_quo:+.6f})")
    assert hausse == baisse


def test_education_ne_derive_plus_avec_l_horizon():
    """Une politique d'éducation CONSTANTE ne fait plus dériver le Gini.

    Défaut structurel corrigé ici pour ce levier : `gini_cible_cumul`
    ACCUMULE l'émission annuelle. Une redistribution permanente est un
    NIVEAU, pas un flux qui s'empile — +15 Md€ chaque année ne rendent pas
    la société dix fois plus égalitaire en dix ans. Avant correction, la
    série valait −0,000197 en Y1 et encore −0,000137 en Y25 (cumul
    −0,00396) ; elle vaut désormais 0 partout."""
    serie = _serie_emissions({'education': {'budget': 80.0}}, periods=25)
    assert all(v == 0.0 for v in serie), (
        f"émissions non nulles : Y1={serie[0]:+.6f}, Y25={serie[-1]:+.6f}, "
        f"cumul={sum(serie):+.6f}")


def test_education_conserve_ses_autres_canaux():
    """Contre-épreuve : I27 ne débranche QUE le Gini.

    Sans elle, mettre le handler entier à zéro ferait passer les tests
    ci-dessus tout en supprimant l'effet réel de la mesure."""
    impacts = _impacts_education(_sim(), budget=80.0, enseignants=10000.0, salaires=5.0)
    assert impacts['depenses'] > 0
    assert impacts['competitivite'] > 0
    assert impacts['pouvoir_achat'] > 0


# ===========================================================================
# 4. Audit du fallback générique : branches MORTES supprimées, VIVANTE déclarée
# ===========================================================================

# Branches du fallback v0.6.0. `mort=True` ⇒ le handler émet déjà `gini`,
# la branche ne peut jamais s'exécuter ⇒ code mort non traçable, supprimé.
_BRANCHES_V060 = {
    'retraites': True,
    'sante': True,
    'chomage_alloc': True,
    'tva_rate': True,
    'transition_ecologique': True,
    'education': True,          # rendue morte PAR ce lot (gini explicite)
    'impot_societes': False,    # VIVANTE — dette connue, cf. ci-dessous
}
_MORTES = sorted(k for k, v in _BRANCHES_V060.items() if v)


def test_branches_mortes_du_fallback_supprimees():
    """Les six branches mortes disparaissent du moteur.

    « Inerte » n'est pas « inoffensif » : sur un repo AGPL public, un
    coefficient sans source que personne ne peut relier à un document reste
    lisible par un auditeur, et rien ne garantit qu'un futur handler ne
    cessera pas d'émettre `gini` — auquel cas le coefficient fantôme
    reprendrait vie sans que personne l'ait décidé."""
    cites = _chaines_du_fallback()
    survivantes = sorted(set(_MORTES) & cites)
    assert not survivantes, (
        f"branches mortes encore présentes dans calculate_gini_impact : "
        f"{survivantes}")


@pytest.mark.parametrize("measure_id", _MORTES)
def test_les_handlers_des_branches_mortes_emettent_bien_gini(measure_id):
    """Contre-épreuve COMPORTEMENTALE de la suppression : elle ne change aucun euro.

    Une suppression de « code mort » n'est légitime que si le code est
    réellement mort. On balaye TOUS les paramètres du levier sur toute leur
    amplitude publiée (`policy_measures.json`, min / défaut / max) et sur
    deux millésimes, et on exige que le handler émette TOUJOURS une clé
    `gini` — ou des impacts vides, auquel cas le fallback ne trouvait de
    toute façon aucune dépense à laquelle s'appliquer. Sans ce test, la
    garde syntaxique ci-dessus validerait aussi bien une suppression qui,
    elle, déplacerait des chiffres publiés."""
    domaines = _domaines_publies(measure_id)
    assert domaines, f"{measure_id} absent de policy_measures.json — garde à revoir"
    for nom, valeurs in sorted(domaines.items()):
        for valeur in valeurs:
            for annee in (POLICY_START_YEAR, POLICY_START_YEAR + 5):
                sim = _sim()
                _, _, impacts = sim.measure_handlers[measure_id](
                    {'id': measure_id}, {nom: valeur}, annee, PIB, 0.01, 0.076)
                if not impacts:
                    continue
                assert 'gini' in impacts, (
                    f"{measure_id}({nom}={valeur}, {annee}) n'émet pas 'gini' : "
                    "la branche du fallback n'était pas morte, la supprimer "
                    "déplacerait des chiffres publiés")


def test_impot_societes_est_la_seule_branche_survivante():
    """La seule branche VIVANTE est conservée et NOMMÉE — elle n'est pas corrigée ici.

    DETTE CONNUE, documentée plutôt que bricolée. `_apply_impot_societes`
    n'émet délibérément pas de clé `gini` (son commentaire dit « PAS
    D'IMPACT MICRO : répercussion prix uniforme sur tous déciles »), mais le
    fallback en émettait un dans son dos — et de façon ASYMÉTRIQUE
    (`if recettes > 0` : une BAISSE d'IS émet 0). Le dossier de sourcing la
    croyait inerte comme les cinq autres ; le balayage empirique de ce lot
    montre qu'elle est ACTIVE, y compris dans deux scénarios publiés (LFI à
    30 % et PS à 27 % d'IS).

    Pourquoi ne pas la retirer dans le même geste : elle DÉPLACE des
    chiffres publiés, et aucune source de ce lot ne dit par quoi la
    remplacer. La retirer ou la symétriser sans source, c'est remplacer un
    biais par un autre. Elle est donc nommée en constante, déclarée NON
    SOURCÉE, et renvoyée au chantier v0.7 (§ B.4-33 : « ne pas bricoler »)."""
    cites = _chaines_du_fallback()
    assert 'impot_societes' in cites
    assert cites & set(_BRANCHES_V060) == {'impot_societes'}


def test_dette_fallback_impot_societes_caracterisee():
    """Caractérisation chiffrée de la dette : elle ne peut plus bouger en silence.

    Verrouille À LA FOIS la valeur (0,03 × recettes/PIB) et l'asymétrie
    (une baisse d'IS émet 0). Le jour où quelqu'un corrige l'un ou l'autre,
    ce test rougit et l'oblige à l'écrire — ce qui est exactement le but."""
    sim = _sim()
    impacts = {'impot_societes': {'recettes': 30.0}}
    assert 'gini' not in impacts['impot_societes'], (
        "prémisse du test : le handler IS n'émet pas de clé 'gini'")
    obtenu = sim.calculate_gini_impact(impacts, PIB)
    assert obtenu == pytest.approx(
        -GINI_FALLBACK_IMPOT_SOCIETES_NON_SOURCE * 30.0 / PIB, abs=1e-15)
    miroir = sim.calculate_gini_impact({'impot_societes': {'recettes': -30.0}}, PIB)
    assert miroir == 0.0, (
        "asymétrie connue : une BAISSE d'IS n'émet rien. Si ce test rougit, "
        "c'est que la dette a été traitée — mettre à jour la doc et le "
        "changelog, la correction n'est pas neutre")


def test_fallback_ne_contient_plus_de_litteral_de_calibration():
    """Plus aucun coefficient anonyme dans le collecteur Gini.

    Les six coefficients 0,10 / 0,15 / 0,08 / 0,04 / 0,05 (branches mortes)
    disparaissent ; le seul survivant est nommé en constante."""
    arbre = ast.parse(_source(
        micro_impacts.MicroImpactsMixin.calculate_gini_impact).lstrip())
    litteraux = [n.value for n in ast.walk(arbre)
                 if isinstance(n, ast.Constant)
                 and isinstance(n.value, (int, float))
                 and not isinstance(n.value, bool)]
    interdits = [v for v in litteraux if v not in (0, 1)]
    assert not interdits, (
        f"littéraux de calibration dans calculate_gini_impact : {interdits} — "
        "toute valeur de calibration vit dans constants.py avec sa source")


def test_le_collecteur_gini_a_le_meme_profil_que_le_collecteur_competitivite():
    """Après I27, `calculate_gini_impact` est (presque) un pur collecteur.

    Il ne reste qu'un seul cas particulier, celui de la dette ci-dessus.
    Cette garde borne la dérive : si un deuxième cas particulier apparaît,
    elle rougit et impose de le justifier."""
    arbre = ast.parse(_source(
        micro_impacts.MicroImpactsMixin.calculate_gini_impact).lstrip())
    comparaisons = [n for n in ast.walk(arbre) if isinstance(n, ast.Compare)]
    assert len(comparaisons) <= 3, (
        f"{len(comparaisons)} comparaisons dans le collecteur Gini — un "
        "deuxième cas particulier a été ajouté sans passer par un handler")


# ===========================================================================
# 5. I30 — recherche publique : 0,0 conservé, motif réécrit
# ===========================================================================

def test_recherche_publique_gini_reste_nul():
    """Aucune étude, FR ou EN, n'estime l'incidence distributive de la R&D
    publique sur les ménages. Trou de la LITTÉRATURE, pas de la collecte :
    la R&D publique s'évalue par ses RENDEMENTS (Guellec & van
    Pottelsberghe, élasticité 0,17 — déjà utilisée par le canal
    compétitivité de ce même handler), pas par son incidence."""
    sim = _sim()
    _, _, impacts = sim._apply_recherche_publique(
        {'id': 'recherche_publique'}, {'budget': 20.0},
        POLICY_START_YEAR, PIB, 0.01, 0.076)
    assert impacts['gini'] == 0.0
    sim2 = _sim()
    _, _, baisse = sim2._apply_recherche_publique(
        {'id': 'recherche_publique'}, {'budget': 5.0},
        POLICY_START_YEAR, PIB, 0.01, 0.076)
    assert baisse['gini'] == 0.0


def test_motif_du_zero_recherche_ne_pretend_plus_a_une_incidence():
    """Le commentaire ne doit plus AFFIRMER une incidence sans source.

    « R&D = emplois qualifiés (favorise classes moyennes supérieures) » est
    une affirmation distributive — non sourcée, et de surcroît de signe
    OPPOSÉ au zéro qu'elle prétend justifier.

    Garde SCOPÉE au bloc Gini du handler, et c'est délibéré : « emplois
    qualifiés » reste une description légitime du canal POUVOIR D'ACHAT du
    même handler (des recrutements de chercheurs le sont). Bannir
    l'expression dans toute la fonction serait la faute symétrique de celle
    qu'on corrige."""
    bloc = _bloc_gini(investissements.InvestissementsMixin._apply_recherche_publique)
    assert 'emplois qualifi' not in bloc, (
        "le motif du zéro affirme encore une incidence distributive")
    assert 'classes moyennes' not in bloc
    assert 'collective' in bloc.lower(), (
        "le motif réel — convention comptable INSEE de consommation "
        "COLLECTIVE non individualisable — doit être écrit")


_HANDLER_SYNTHETIQUE = '''    def _apply_bidon(self):
        # === POUVOIR D'ACHAT ===
        # Recrutements = emplois qualifies.
        pa = 0.0

        # === GINI : ZERO ASSUME ===
        # Convention comptable INSEE : consommation collective.
        gini = 0.0

        impacts = {'gini': gini}
        return impacts
'''


def test_extracteur_prend_le_bloc_gini_et_pas_celui_du_voisin():
    """Contre-épreuve de `_bloc_gini`, sur les DEUX faces.

    Face 1 (sinon la garde ne mesure rien) : le bloc Gini et ses commentaires
    sont bien capturés. Face 2 (sinon la garde mesure trop) : le bloc
    POUVOIR D'ACHAT qui le précède est bien exclu, MÊME quand il contient un
    des motifs interdits — sans quoi le seul moyen de faire passer la garde
    serait de retoucher un canal que ce lot n'audite pas."""
    lignes = _HANDLER_SYNTHETIQUE.splitlines()
    debut = next(i for i, l in enumerate(lignes) if '=== GINI' in l)
    fin = next(i for i, l in enumerate(lignes[debut:], debut)
               if l.strip().startswith('impacts = {'))
    bloc = '\n'.join(lignes[debut:fin])
    assert 'consommation collective' in bloc.lower()
    assert 'emplois qualifies' not in bloc


def test_extracteur_leve_si_le_marqueur_disparait():
    """Un extracteur qui ne trouve plus son objet doit LEVER, pas rendre ''."""
    with pytest.raises(AssertionError, match="=== GINI"):
        _bloc_gini(micro_impacts.MicroImpactsMixin.calculate_competitivite)


# ===========================================================================
# 6. Méta-gardes de citation (repo PUBLIC — un audit citoyen a déjà relevé
#    des citations fausses)
# ===========================================================================

_MOTIFS_INTROUVABLES = [
    ("ADEME 2024", "source INTROUVABLE (§ B.4-31) : le coefficient rénovation "
                   "s'appuie désormais sur ONRE/SDES fév. 2023 + ONPE 2024"),
    ("OFCE 2019", "source INTROUVABLE (§ B.4-31) : le coefficient carbone "
                  "s'appuie désormais sur Douenne 2020 + Note IPP n° 34"),
    ("taxe carbone régressive", "titre d'un document qui n'existe pas"),
]


@pytest.mark.parametrize("motif,raison", _MOTIFS_INTROUVABLES)
def test_meta_garde_citations_introuvables_retirees(motif, raison):
    """Aucune des citations introuvables ne survit dans le moteur ni la doc.

    Périmètre : le package `budget_simulator/` et les docs publiques
    `docs/*.md`. Il est VOLONTAIREMENT plus large que le bloc transition —
    contrairement au cas « IGAS 2023 » du lot 4, ni « ADEME » ni « OFCE
    2019 » ne portent une autre affirmation légitime ailleurs dans ce
    dépôt (vérifié par balayage). Ce fichier de tests est exclu : il CITE
    les motifs pour les interdire."""
    fichiers = sorted((ROOT / 'budget_simulator').rglob('*.py'))
    fichiers += sorted((ROOT / 'docs').glob('*.md'))
    fautifs = [str(f.relative_to(ROOT)) for f in fichiers
               if motif in f.read_text(encoding='utf-8')]
    assert not fautifs, f"{motif!r} encore cité dans {fautifs} — {raison}"


# Les deux lignes EXACTES de la v0.6.0, recopiées telles quelles. Servent de
# cible à la contre-épreuve ci-dessous : une garde de citation peut être verte
# parce qu'elle cherche au mauvais endroit (défaut réel constaté au lot 4), et
# le seul moyen de le savoir est de la faire tourner sur le texte fautif.
# NB : on ne relit PAS `git show HEAD` — après le commit de ce lot, HEAD
# porterait le texte corrigé et la contre-épreuve deviendrait vacuelle.
_TEXTE_FAUTIF_V060 = (
    "            # Règle : +5 Md€ rénovation = -0.001 Gini (ADEME 2024)\n"
    "            gini_renovation = -0.001 * renovation / 5\n"
    "            # Règle : +50€/tCO2 = +0.002 Gini "
    "(OFCE 2019 \"taxe carbone régressive\")\n"
    "            gini_carbon = 0.002 * (carbon_tax - 44.6) / 50\n"
)


@pytest.mark.parametrize("motif,_raison", _MOTIFS_INTROUVABLES)
def test_meta_garde_attrape_bien_le_texte_d_avant(motif, _raison):
    """Rouge automatisé : chaque motif DÉTECTE bien la version pré-correctif.

    Si l'un des trois motifs ne matchait pas le texte qu'il est censé
    interdire, la garde correspondante serait un faux-vert permanent."""
    assert motif in _TEXTE_FAUTIF_V060, (
        f"le motif {motif!r} ne matche pas la ligne v0.6.0 qu'il interdit : "
        "la garde ne mesure rien")


def test_sources_de_remplacement_presentes_dans_le_bloc_transition():
    """Les sources qui remplacent les citations retirées sont là, à l'endroit
    exact où l'auditeur les cherchera : DANS le handler.

    Elles vivent au long dans `constants.py` (URL, tableaux, page) ; le
    handler doit au minimum les NOMMER, sinon un lecteur qui ouvre la
    formule ne sait pas à quoi elle se rattache — c'était le défaut de la
    v0.6.0, dont les deux lignes citaient une source par formule."""
    texte = _source(investissements.InvestissementsMixin._apply_transition_ecologique)
    for attendu in ("Douenne", "IPP", "ONRE", "ONPE"):
        assert attendu in texte, (
            f"{attendu} absent du handler : le coefficient a changé sans que "
            "sa source l'accompagne")


def test_condition_de_validite_du_canal_carbone_documentee():
    """La condition qui peut INVERSER le signe doit être écrite noir sur blanc,
    dans le code ET dans la doc publique.

    Le coefficient suppose l'ABSENCE DE RECYCLAGE des recettes — cohérent
    avec le moteur, où la taxe carbone abonde le budget général. Si un
    scénario ajoutait une compensation forfaitaire, Douenne montre que les
    déciles D1-D5 deviennent gagnants et que le signe s'inverse. Un lecteur
    à qui l'on dit « la taxe carbone est régressive » sans cette condition
    reçoit une demi-vérité."""
    assert 'recyclage' in inspect.getsource(constants).lower()
    methodo = (ROOT / 'docs' / 'METHODOLOGIE.md').read_text(encoding='utf-8')
    assert 'recyclage' in methodo.lower(), (
        "la condition de validité n'est pas dans METHODOLOGIE.md — c'est "
        "pourtant le document que lisent les journalistes et les citoyens")


# ===========================================================================
# 7. Conventions du projet
# ===========================================================================

def test_aucun_litteral_de_calibration_dans_les_canaux_gini():
    """Les deux canaux Gini de la transition ne portent aucun nombre en dur.

    Convention du projet : toute valeur de calibration vit dans
    `constants.py` avec sa source primaire exacte. C'est ce qui permet à un
    auditeur externe de remonter de la formule au document."""
    litteraux = _constantes_numeriques(
        investissements.InvestissementsMixin._apply_transition_ecologique,
        {'gini_renovation', 'gini_carbon'})
    assert litteraux == [], (
        f"littéraux de calibration dans les canaux Gini : {litteraux}")


def test_constantes_gini_dans_les_domaines_attendus():
    """Signes et ordres de grandeur — garde anti-faute de frappe.

    Le carbone est RÉGRESSIF (signe +, il creuse les inégalités), la
    rénovation REDISTRIBUTIVE (signe −)."""
    assert GINI_TAXE_CARBONE_PAR_EUR_TONNE > 0
    assert GINI_RENOVATION_PAR_MD_EUR < 0
    assert GINI_TAXE_CARBONE_PAR_EUR_TONNE * CARBONE_PAS_EUR_T == pytest.approx(0.001)
    assert GINI_RENOVATION_PAR_MD_EUR == pytest.approx(-0.00034)
    assert CARBONE_PRIX_REFERENCE_EUR_T == 44.6


def test_prix_de_reference_du_carbone_a_une_source_unique():
    """44,6 €/tCO2 ne doit plus être répliqué en littéral dans le handler.

    Quatre occurrences en dur cohabitaient (défaut, recettes, Gini, pouvoir
    d'achat) : un recalibrage de la référence n'en aurait atteint qu'une
    partie."""
    texte = _source(investissements.InvestissementsMixin._apply_transition_ecologique)
    assert '44.6' not in texte and '44,6' not in texte, (
        "le prix de référence du carbone est encore écrit en dur")


# ===========================================================================
# 8. NIVEAU vs FLUX — carte des émissions récurrentes (documentée, non corrigée)
# ===========================================================================

# Handlers dont l'émission Gini annuelle ne converge PAS vers zéro pour une
# politique constante. `gini_cible_cumul` les ACCUMULE : leur effet croît
# indéfiniment avec l'horizon. Ce lot en retire un (`education`) parce qu'il
# était non sourcé et asymétrique ; il ne touche pas aux trois autres, qui
# demandent chacun une décision de modélisation propre :
#
#   * `impot_societes` — via le fallback, dette connue (cf. § 4 ci-dessus) ;
#   * `retraites`      — résidu de 10 %/an, DÉLIBÉRÉ et documenté dans le
#                        handler (« flux annuel des nouvelles cohortes de
#                        retraités impactées ») ; c'est un choix de
#                        modélisation défendable, pas un oubli ;
#   * `rabot_uniforme` — émission croissante, la plus grosse des trois
#                        (cumul ≈ +0,09 sur 25 ans) ; jamais auditée.
#
# Chantier v0.7 (§ B.4-33 du dossier : la valeur de GINI_IMPACT_SCALE n'est
# « pas calculable en l'état » tant que les coefficients ne sont pas tous
# sourcés — « ne pas bricoler »).
_EMETTEURS_RECURRENTS_CONNUS = {'impot_societes', 'retraites', 'rabot_uniforme'}


def test_carte_des_emissions_gini_recurrentes():
    """Aucun NOUVEL émetteur récurrent, et `education` a bien quitté la liste.

    Balayage des 33 leviers, un à la fois, sur 25 ans à politique CONSTANTE.
    Un handler dont l'émission annuelle ne tend pas vers zéro fait dériver
    le Gini linéairement avec l'horizon : la liste ci-dessus est la dette
    connue, et elle ne doit que RÉTRÉCIR."""
    _ajoute_snapshots_au_path()
    from coverage_scenarios import build_standalone_scenarios  # noqa: E402

    recurrents = set()
    for nom, mesures in build_standalone_scenarios().items():
        serie = _serie_emissions(mesures, periods=25)
        if abs(serie[-1]) > 1e-9:
            recurrents.add(nom)
    nouveaux = recurrents - _EMETTEURS_RECURRENTS_CONNUS
    assert not nouveaux, (
        f"nouveaux émetteurs Gini récurrents : {sorted(nouveaux)} — un effet "
        "de NIVEAU émis chaque année est composé à l'infini par "
        "gini_cible_cumul")
    assert 'education' not in recurrents, (
        "l'éducation émet encore un flux annuel : I27 n'est pas appliqué")


def test_le_golden_master_standalone_couvre_bien_le_gini():
    """Trou de couverture trouvé PAR ce lot : le snapshot standalone n'avait
    aucune colonne d'inégalités.

    `coverage_scenarios.TRACKED_COLUMNS` demandait une colonne `Inegalites`
    qui n'existe dans AUCUN DataFrame du moteur (la colonne publiée s'appelle
    `Gini`), et `build_snapshot` filtrait SILENCIEUSEMENT les colonnes
    absentes. Résultat : les 33 mini-scénarios standalone ne verrouillaient
    rien du canal redistributif — un recalibrage Gini pouvait passer sans
    faire bouger un seul octet du snapshot, ce qui aurait laissé croire à une
    isolation parfaite.

    Exactement le même défaut avait déjà été trouvé et corrigé dans
    `run_scenarios_full.py` (snapshot des 9 scénarios complets) ; le remède
    n'avait pas été appliqué au fichier jumeau. Il l'est ici, à l'identique :
    `Gini` ajouté EN DERNIER, donc ajout purement additif, l'ordre des
    colonnes existantes est préservé."""
    _ajoute_snapshots_au_path()
    import coverage_scenarios  # noqa: E402

    df, _, _ = BudgetSimulatorV45(periods=2, mesures={}).simulate()
    absentes = [c for c in coverage_scenarios.TRACKED_COLUMNS if c not in df.columns]
    assert not absentes, (
        f"colonnes suivies mais inexistantes : {absentes} — elles sont "
        "filtrées en silence, la couverture qu'elles promettent est fictive")
    assert 'Gini' in coverage_scenarios.TRACKED_COLUMNS

    snapshot = json.loads(
        (ROOT / 'tests' / 'snapshots' / 'standalone_master_v1.json').read_text(
            encoding='utf-8'))
    manquants = [nom for nom, bloc in snapshot.items()
                 if 'Gini' not in bloc.get('data', {})]
    assert not manquants, (
        f"{len(manquants)} mini-scénarios sans série Gini dans le golden "
        f"master standalone : {manquants[:5]} — régénérer le snapshot")


def test_transition_ecologique_reste_un_effet_de_niveau():
    """Les deux canaux corrigés restent gatés en NIVEAU one-time.

    Contre-épreuve du test précédent côté transition : recalibrer un
    coefficient ne doit jamais reclasser l'effet en flux."""
    serie = _serie_emissions(
        {'transition_ecologique': {'renovation': 20.0, 'taxe_carbone': 100.0}},
        periods=20)
    assert serie[0] != 0.0
    assert all(v == 0.0 for v in serie[1:]), (
        f"émission encore active après Y1 : {serie[1:4]}")
