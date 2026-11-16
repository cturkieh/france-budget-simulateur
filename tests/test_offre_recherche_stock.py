"""Effet d'offre de la recherche publique en forme STOCK (lot 2 des corrections d'équations).

Jusqu'au lot 2, le bonus de croissance potentielle du canal « recherche publique » valait pente × Δ, où Δ est
l'écart du budget de l'année au défaut (Md€/an), compté seulement après cinq années consécutives d'écart. Trois
conséquences : une dépense d'une seule année n'avait aucun effet, quelle que soit sa taille ; un programme qui
commence en 2028 n'agissait pas avant 2033, après le mandat ; un surcroît de dépense qui dure n'était jamais
déprécié, alors que le stock de recherche l'est. Aucune source citée ne soutenait le délai de cinq ans :

- Fieldhouse & Mertens (Dallas Fed WP 2305, rév. 11/2024), d'où le moteur tire déjà l'élasticité (0,06 pour la
  recherche civile) : leurs « 8 à 15 ans » séparent un VOTE de crédits de l'effet significatif, et viennent
  surtout du temps que mettent les crédits à devenir dépense, puis stock. Leur équation structurelle relie la
  productivité au stock, sans délai propre (éq. (6) : Δtfp_t = ϕ Δk_t, k_t log du stock de R&D publique) ; ils
  posent ce calendrier puis le vérifient sur leurs réponses estimées (annexe E.1). C'est une hypothèse vérifiée,
  pas un délai mesuré, sur données américaines ; aucune source française n'a été trouvée.
- Khan & Luintel (2006), cités par le moteur pour les délais : des stocks retardés d'un à deux ans.

Arbitrage du mainteneur (15/11/2026) : forme stock, effet à partir de l'année qui suit la dépense, sans délai
ajouté. Contrat verrouillé ici : inventaire permanent exact, ``A_t = (1 − δ) A_{t−1} + Δ_t`` (δ = 15 %/an,
``DEPRECIATION_RD_PUBLIQUE`` : OCDE 2001 et Khan & Luintel 2006 ; 0,16 au BEA selon Fieldhouse & Mertens),
contribution posée en fin d'année et consommée l'année suivante ; effet dès l'année qui suit le début du
programme, dans les deux modes ; gain temporaire pour une dépense d'une seule année ; coupe et hausse en miroir
sur le stock. Les autres canaux (capital public, rénovation, éducation) ne changent pas dans ce commit. Aucune
donnée du dépôt parent n'est lue.
"""
import math

import pytest

from budget_simulator import constants as C
from budget_simulator.config import load_default_values
from budget_simulator.engine.growth import GrowthMixin
from budget_simulator.simulator import BudgetSimulatorV45

CLE = 'recherche_publique'
DEFAUT = load_default_values()['recherche_publique']['budget']


def _contribution(avant, apres):
    """Contribution d'un pas de stock à la croissance potentielle (forme du moteur)."""
    return C.OFFRE_PENTE_RD_PUBLIQUE * (apres - avant)


def _bonus(somme):
    """Bonus total à partir de la somme des contributions (saturation commune du moteur)."""
    return C.OFFRE_PLAFOND * math.tanh(somme / C.OFFRE_PLAFOND)


def _suite_attendue(budgets):
    """Bonus attendu après chaque année quand le budget de recherche suit ``budgets``."""
    stock, out = 0.0, []
    for b in budgets:
        avant, stock = stock, (1 - C.DEPRECIATION_RD_PUBLIQUE) * stock + (b - DEFAUT)
        out.append(_bonus(_contribution(avant, stock)))
    return out


def _suite_obtenue(budgets):
    """Bonus du moteur après chaque année, le budget de recherche suivant ``budgets``."""
    s = BudgetSimulatorV45(periods=10, mesures={})
    out = []
    for y, b in enumerate(budgets, start=1):
        s.mesures = {'recherche_publique': {'budget': b}}
        s.update_potential_growth(0.01, y)
        out.append(s._potential_growth_bonus)
    return out, s


def _offre_consommee(mesures, annee_debut=None):
    """{année: offre structurelle CONSOMMÉE par l'année} (photographie ``potentiel_de_l_annee``)."""
    journal = []

    def espion(self):
        photo = GrowthMixin.potentiel_de_l_annee(self)
        journal.append(photo.offre_structurelle)
        return photo

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(BudgetSimulatorV45, 'potentiel_de_l_annee', espion)
        df, _, _ = BudgetSimulatorV45(periods=10, mesures=mesures, annee_debut=annee_debut).simulate()
    return dict(zip((int(a) for a in df['Année']), journal))


def test_canal_recherche_en_forme_stock_sans_delai_ajoute():
    cfg = BudgetSimulatorV45.SUPPLY_EFFECTS[CLE]
    assert cfg['forme'] == 'stock'
    assert cfg['delay'] == 0
    assert cfg['deprec'] == C.DEPRECIATION_RD_PUBLIQUE == 0.15
    assert (cfg['measure_id'], cfg['param']) == ('recherche_publique', 'budget')
    # Les autres canaux restent dans le flux : leur dépréciation et leur délai, en forme stock, n'ont pas
    # de source arrêtée (METHODOLOGIE, « Limites dites »).
    autres = {k: v for k, v in BudgetSimulatorV45.SUPPLY_EFFECTS.items() if k != CLE}
    assert all(v.get('forme') != 'stock' for v in autres.values()), autres


@pytest.mark.parametrize('budgets', [
    [DEFAUT + 10] * 10,                                   # hausse soutenue
    [DEFAUT - 6] * 10,                                    # coupe soutenue
    [DEFAUT + 4, DEFAUT + 9, DEFAUT + 15, DEFAUT + 15, DEFAUT, DEFAUT, DEFAUT - 3, DEFAUT, DEFAUT, DEFAUT],
])
def test_inventaire_permanent_exact(budgets):
    """Chaque année : A_t = (1 − δ) A_{t−1} + Δ_t, bonus = contribution du pas de stock (saturée par la
    forme commune du moteur), au bit près à 1e-15."""
    obtenu, s = _suite_obtenue(budgets)
    assert obtenu == pytest.approx(_suite_attendue(budgets), abs=1e-15)
    stock = 0.0
    for b in budgets:
        stock = (1 - C.DEPRECIATION_RD_PUBLIQUE) * stock + (b - DEFAUT)
    assert s._supply_stock[CLE] == pytest.approx(stock, abs=1e-12)


def test_une_seule_annee_donne_un_gain_temporaire():
    """Une hausse d'une seule année : gain dès l'année suivante, puis le stock s'use (contributions
    négatives) et le niveau acquis s'efface au rythme de la dépréciation. Jusqu'au lot 2 : aucun effet
    (délai de cinq ans)."""
    obtenu, s = _suite_obtenue([DEFAUT + 10] + [DEFAUT] * 9)
    assert obtenu[0] > 0
    assert all(b < 0 for b in obtenu[1:]), obtenu
    assert s._supply_stock[CLE] == pytest.approx(10 * (1 - C.DEPRECIATION_RD_PUBLIQUE) ** 9, rel=1e-12)
    assert sum(obtenu) < obtenu[0]


def test_coupe_et_hausse_en_miroir_sur_le_stock():
    hausse, sh = _suite_obtenue([DEFAUT + 7] * 6)
    coupe, sc = _suite_obtenue([DEFAUT - 7] * 6)
    assert sc._supply_stock[CLE] == -sh._supply_stock[CLE] != 0
    assert all(b > 0 for b in hausse) and all(b < 0 for b in coupe)


@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
def test_effet_des_l_annee_qui_suit_le_debut_du_programme(annee_debut):
    """Le programme commence en 2026 (historique) ou en 2028 (cadre) : rien n'est consommé jusqu'à
    cette année incluse, l'offre est positive dès l'année suivante, et chaque année ensuite jusqu'à
    2035. Jusqu'au lot 2 : rien avant 2031 (historique) ni avant 2033 (cadre, après le mandat)."""
    debut = annee_debut or C.POLICY_START_YEAR
    b = _offre_consommee({'recherche_publique': {'budget': DEFAUT + 10}}, annee_debut)
    assert all(v == 0.0 for a, v in b.items() if a <= debut), b
    assert all(v > 0 for a, v in b.items() if a > debut), b


def test_budget_par_defaut_stock_nul():
    """Budget de recherche au défaut chaque année : écart nul, stock nul, bonus 0,0. Le droit en vigueur, qui
    garde ce budget, est couvert à part (``test_effet_offre_echelle_v0612.py``, W6-10)."""
    obtenu, s = _suite_obtenue([DEFAUT] * 10)
    assert obtenu == [0.0] * 10
    assert s._supply_stock[CLE] == 0.0


def test_deux_simulations_du_meme_objet_identiques():
    """Le stock ajouté et les écarts de dépense de chaque année sont remis à zéro entre deux simulations du
    même simulateur (``_reset_state``) : la seconde redonne la première au bit, et le stock d'après la seconde
    est celui d'une seule simulation. Sans remise à zéro, le stock de la première s'ajouterait à la seconde
    (mesuré : 4,5 points de dette 2035 d'écart entre les deux simulations de ce programme)."""
    s = BudgetSimulatorV45(periods=10, mesures={'recherche_publique': {'budget': DEFAUT + 10}})
    premiere = s.simulate()
    stock = s._supply_stock[CLE]
    seconde = s.simulate()
    assert premiere[0].equals(seconde[0]) and premiere[1].equals(seconde[1])
    assert s._supply_stock[CLE] == stock and len(s._supply_flux[CLE]) == len(premiere[0]) - 1
