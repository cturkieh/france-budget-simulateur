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
sur le stock. Les autres canaux (capital public, rénovation, éducation) restent dans le flux.

Forme logarithmique, sans plafond fixe (arbitrage du mainteneur du 16/11/2026, second commit du lot) : la
contribution d'un pas de stock vaut ε × [ln(K + A_t) − ln(K + A_{t−1})], la calibration à élasticité constante
que Fieldhouse & Mertens donnent pour un modèle (p. PDF 31), ε = 0,06, K = 187 Md€ (stock de départ,
``CAPITAL_RD_PUBLIC_MD_EUR``) ; elle s'ajoute hors de tout plafond (le plafond ±0,20 pt, une convention de la
v3.1 sans source, ne s'applique plus qu'à la somme des canaux en flux, dont la forme stock attend une source).
Verrouillé : forme exacte, aucun plafond fixe pour la recherche, niveau acquis
égal à ε × ln(1 + A/K) (positif après une dépense d'une seule année), rendements décroissants doux, coupe un peu
plus lourde qu'une hausse du même montant, stock de départ jamais épuisé sur le domaine du levier. Aucune donnée
du dépôt parent n'est lue.
"""
import math

import pytest

from budget_simulator import constants as C
from budget_simulator.config import load_default_values
from budget_simulator.engine.growth import GrowthMixin
from budget_simulator.simulator import BudgetSimulatorV45

CLE = 'recherche_publique'
DEFAUT = load_default_values()['recherche_publique']['budget']


EPS, K0 = C.ELASTICITE_PIB_CAPITAL_RD_PUBLIC, C.CAPITAL_RD_PUBLIC_MD_EUR


def _contribution(avant, apres):
    """Contribution d'un pas de stock à la croissance potentielle : ε × [ln(K + A_t) − ln(K + A_{t−1})]."""
    return EPS * (math.log(K0 + apres) - math.log(K0 + avant))


def _bonus(somme):
    """Bonus d'un programme de recherche seule : sa contribution, hors plafond (lot 2)."""
    return somme


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


# --- Forme logarithmique, sans plafond fixe (second commit du lot 2) ---------------------------------

def test_forme_logarithmique_du_canal():
    cfg = BudgetSimulatorV45.SUPPLY_EFFECTS[CLE]
    assert cfg['elasticite'] == C.ELASTICITE_PIB_CAPITAL_RD_PUBLIC == 0.06
    assert cfg['stock'] == C.CAPITAL_RD_PUBLIC_MD_EUR
    assert 'pente' not in cfg


def test_aucun_plafond_fixe():
    """La recherche sort du plafond ±0,20 pt : une forte hausse donne, la première année, le gain de sa
    forme, au-delà de 0,20 pt (0,81 pt pour la borne haute du levier). Le plafond reste celui des seuls canaux
    en flux : avec une forte hausse d'investissement en plus, la part de ces canaux reste sous ±0,20 pt et la
    recherche s'y ajoute."""
    assert not hasattr(C, 'OFFRE_PENTE_RD_PUBLIQUE')
    from budget_simulator.engine._param_domain import PARAM_DOMAINS
    haut = PARAM_DOMAINS['recherche_publique']['budget'][1]
    obtenu, _ = _suite_obtenue([haut])
    assert obtenu[0] == pytest.approx(EPS * math.log1p((haut - DEFAUT) / K0), abs=1e-15)
    assert obtenu[0] > C.OFFRE_PLAFOND
    s = BudgetSimulatorV45(periods=10, mesures={})
    for y in range(1, 8):
        s.mesures = {'recherche_publique': {'budget': haut}, 'transition_ecologique': {'investissement': 50}}
        s.update_potential_growth(0.01, y)
    flux = s._potential_growth_bonus - s._supply_bonus_by_key[CLE]
    assert 0 < flux < C.OFFRE_PLAFOND
    assert flux == pytest.approx(C.OFFRE_PLAFOND * math.tanh(C.OFFRE_PENTE_CAPITAL_PUBLIC * 50 / C.OFFRE_PLAFOND),
                                 abs=1e-15)


def test_niveau_acquis_egal_a_l_elasticite_du_stock():
    """Les contributions s'additionnent sans écrêtage : le niveau acquis après n années vaut
    ε × ln(1 + A_n / K) (somme télescopique), positif après une dépense d'une seule année. Dans l'état du
    premier commit, la saturation du pas annuel le rendait négatif."""
    budgets = [DEFAUT + 10] + [DEFAUT] * 9
    obtenu, s = _suite_obtenue(budgets)
    assert sum(obtenu) == pytest.approx(EPS * math.log1p(s._supply_stock[CLE] / K0), abs=1e-15)
    assert 0 < sum(obtenu) < obtenu[0]


def test_rendements_decroissants_doux_sans_borne_fixe():
    """Niveau de long terme d'une hausse soutenue de x Md€ : ε × ln(1 + x / (δK)). Croissant en x, mais
    moins que proportionnellement, et jamais ramené à une borne commune."""
    def niveau(x, annees=40):
        obtenu, _ = _suite_obtenue([DEFAUT + x] * annees)
        return sum(obtenu)
    n5, n10, n20 = niveau(5), niveau(10), niveau(20)
    assert 0 < n5 < n10 < n20
    assert n10 < 2 * n5 and n20 < 2 * n10
    assert n20 / n10 > 1.5          # pas de saturation : doubler le montant ajoute encore plus de moitié


def test_une_coupe_pese_plus_qu_une_hausse_du_meme_montant():
    """Stock exactement en miroir ; effet logarithmique asymétrique (concavité de ln) : la perte d'une
    coupe dépasse le gain d'une hausse du même montant, d'autant plus que le montant est grand. À long terme
    (stock ajouté x / δ), l'écart vaut −ln(1 − x / (δK)) / ln(1 + x / (δK)) − 1 : 4 % pour 1 Md€ par an,
    20 % pour 5 Md€, 45 % pour 10 Md€ (la plus forte coupe du levier), chiffres de METHODOLOGIE."""
    hausse, sh = _suite_obtenue([DEFAUT + 7] * 6)
    coupe, sc = _suite_obtenue([DEFAUT - 7] * 6)
    assert sc._supply_stock[CLE] == -sh._supply_stock[CLE]
    assert 1 < -sum(coupe) / sum(hausse) < 1.2
    dk = C.DEPRECIATION_RD_PUBLIQUE * K0
    ecarts = {x: round(100 * (-math.log1p(-x / dk) / math.log1p(x / dk) - 1)) for x in (1, 5, 10)}
    assert ecarts == {1: 4, 5: 20, 10: 45}, ecarts
    assert DEFAUT == 10   # « 10 Md€, la plus forte coupe du levier » : budget ramené à 0
    a5 = 10 * (1 - (1 - C.DEPRECIATION_RD_PUBLIQUE) ** 5) / C.DEPRECIATION_RD_PUBLIQUE   # stock après cinq ans
    coupe5, hausse5 = _suite_obtenue([0.0] * 5)[0], _suite_obtenue([20.0] * 5)[0]
    assert round(100 * (-math.log1p(-a5 / K0) / math.log1p(a5 / K0) - 1)) == 22
    assert round(100 * (-sum(coupe5) / sum(hausse5) - 1)) == 22
    from pathlib import Path
    import re
    texte = (Path(__file__).absolute().parent.parent / 'docs' / 'METHODOLOGIE.md').read_text(encoding='utf-8')
    texte = ' '.join(re.sub(r'\n>\s?', ' ', texte).split())
    assert ('de 4 % pour 1 Md€ par an, 20 % pour 5 Md€, 45 % pour 10 Md€, la plus forte coupe du levier ; '
            'après cinq ans, 22 % pour cette coupe' in texte)


def test_stock_de_depart_jamais_epuise_sur_le_domaine():
    """Coupe maximale du levier (budget à la borne basse) soutenue 60 ans : le stock ajouté tend vers
    −défaut / δ, au-dessus de −K ; la forme reste définie et le bonus fini."""
    from budget_simulator.engine._param_domain import PARAM_DOMAINS
    bas = PARAM_DOMAINS['recherche_publique']['budget'][0]
    obtenu, s = _suite_obtenue([bas] * 60)
    assert (bas - DEFAUT) / C.DEPRECIATION_RD_PUBLIQUE > -K0
    assert K0 + s._supply_stock[CLE] > 0
    assert all(math.isfinite(b) and b < 0 for b in obtenu)

