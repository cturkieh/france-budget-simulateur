"""Symétrie en signe de la DÉPENSE COURANTE (lot 5 des corrections d'équations).

Convention du mainteneur (v0.6.7) : pas d'asymétrie de signe retenue — même instrument, même
coefficient, en hausse comme en baisse. Elle valait pour les transferts, les impôts et
l'investissement, pas pour la dépense courante, c'est-à-dire toute dépense qui n'est ni de
l'investissement productif (``INVESTMENT_CORE_MEASURES``, part ``INVESTISSEMENT_PRODUCTIF_PARTIEL``)
ni un levier de transfert (``TRANSFER_MEASURES``) : défense, dotations des collectivités, postes et
point d'indice, réforme de l'État, crédits des ministères, santé, aide médicale de l'État et
intégration, subventions…

- une BAISSE prenait ``MULT_COUPE_DEPENSES`` : 0,79 point de PIB à 4 ans par point de PIB ;
- une HAUSSE prenait ``MULT_TRANSFERTS`` : la branche « expansion » de
  ``FiscalMultipliers.get_multiplier`` versait toute dépense hors investissement dans la case des
  transferts, faute de case « dépense courante » ; 0,74 point dans ce banc.

Rouge avant la correction : rapport baisse / hausse de 1,05 à 1,10 selon le levier, l'état et
l'horizon. Désormais la hausse prend le coefficient de la coupe.

Contrat verrouillé ici, dans le moteur complet :

1. les leviers sondés ne sont pas écrits à la main : ils sont DÉRIVÉS du registre des paramètres
   (``PARAM_DOMAINS`` et ``INTENSITE_DOMAINS``), en portant chaque paramètre, seul, à chacune des
   bornes de son domaine et en relevant les impulsions que le levier stocke à son nom ; tout levier
   qui stocke une hausse de dépense courante est sondé, et un test vérifie que chaque levier de
   dépense du registre est rangé dans une famille gardée par un test ;
2. une hausse et une baisse permanentes d'un point de PIB d'une même dépense courante déplacent le
   PIB réel en miroir, à 1 % près, les six premières années d'effet, pour chaque levier dérivé
   et un levier synthétique absent de toute liste, dans cinq états (banc historique, mode cadre
   2028, dette haute, écart de production négatif, écart de production positif). Aucune
   non-linéarité n'est neutralisée : la seule précaution est la pleine précision des sorties
   (arrondi de l'orchestrateur retiré, comme dans les autres bancs). Au-delà de six années d'effet,
   le niveau revient vers zéro et le rapport de deux petits nombres n'est plus une mesure (1,9 % la
   8e année d'effet) ;
3. le même miroir par le vrai curseur de la défense (±10 Md€ autour de sa valeur de référence),
   handler compris ;
4. le coefficient de la hausse de dépense courante n'est lu par aucun autre flux : lui donner une
   autre valeur ne change rien, au bit, à un programme qui ne contient aucune hausse de dépense
   courante (transferts, impôts, investissement, coupes, dans les deux sens) ;
5. aucun effet par un autre chemin : pendant des simulations complètes, ce coefficient entre dans
   un appel de ``get_multiplier`` si et seulement si l'appel est une hausse de dépense courante.

Limite (METHODOLOGIE) : le miroir est vérifié sur le PIB, pas sur la dette. Aucune donnée du dépôt
parent n'est lue.
"""
import json
from functools import lru_cache
from pathlib import Path

import pytest

from budget_simulator.constants import INTENSITE_DOMAINS, PARAM_DOMAINS
from budget_simulator.engine.cadre import LEVIERS_REFUSES_EN_MODE_HISTORIQUE, charger_droit_en_vigueur
from budget_simulator.simulator import BudgetSimulatorV45, FiscalMultipliers

S = BudgetSimulatorV45
REGISTRE = Path(__file__).resolve().parent.parent / 'policy_measures.json'


def famille(levier):
    """Famille de multiplicateur d'une dépense du levier, et le test qui garde sa symétrie."""
    if levier in S.MESURES_HORS_DEMANDE_INTERIEURE:
        return 'hors demande intérieure'      # aucune impulsion (tests/test_release_e_w2.py, W2-15)
    if levier in FiscalMultipliers.MESURES_MULTIPLICATEUR_NET:
        return 'coefficient propre'           # tests/test_impulsions_v067.py
    if levier in S.INVESTMENT_CORE_MEASURES:
        return 'investissement'               # tests/test_symetrie_v060.py, banc des multiplicateurs
    if levier in S.TRANSFER_MEASURES:
        return 'transferts'                   # tests/test_symetrie_transferts_v067.py
    return 'dépense courante'                 # ce fichier


FAMILLES_GARDEES = {'hors demande intérieure', 'coefficient propre', 'investissement', 'transferts',
                    'dépense courante'}


def _domaines():
    """Registre des paramètres du moteur : domaines publiés et domaines d'intensité."""
    d = {levier: dict(params) for levier, params in PARAM_DOMAINS.items()}
    for levier, bornes in INTENSITE_DOMAINS.items():
        d.setdefault(levier, {})['intensite'] = bornes
    return d


@lru_cache(maxsize=1)
def balayage():
    """{levier: {(flux, sens)}} : impulsions que chaque levier stocke À SON NOM quand chacun de ses
    paramètres est porté seul à l'une des bornes de son domaine (mode historique ; mode cadre 2028
    pour un levier que le mode historique refuse)."""
    vus = {}
    for levier, params in sorted(_domaines().items()):
        debut = 2028 if levier in LEVIERS_REFUSES_EN_MODE_HISTORIQUE else None
        vus[levier] = set()
        for param, bornes in params.items():
            for valeur in bornes:
                sim = BudgetSimulatorV45(periods=10, mesures={levier: {param: valeur}}, annee_debut=debut)
                sim.simulate()
                vus[levier] |= {(flux, sens) for (_a, m, flux, sens) in sim._fiscal_impulses if m == levier}
    return vus


HAUSSES_COURANTES = tuple(sorted(levier for levier, vus in balayage().items()
                                 if ('depenses', 'expansion') in vus and famille(levier) == 'dépense courante'))
LEVIERS = HAUSSES_COURANTES + ('depense_courante_synthetique',)
# Leviers dont une dépense (hausse ou baisse) est de la dépense courante, y compris ceux qui ne
# montent pas dans leur domaine (fraude sociale, optimisation de la dette, rabot uniforme).
COURANTS_DU_REGISTRE = tuple(sorted(levier for levier, vus in balayage().items()
                                    if famille(levier) == 'dépense courante'
                                    and any(flux == 'depenses' for flux, _ in vus)))

# État : année de début du programme (None = mode historique), premier budget de l'impulsion,
# et réglage de l'état de départ (dette/PIB 2025, écart de production 2025).
ETATS = {
    'banc_historique': dict(annee_debut=None, debut=2026),
    'cadre_2028': dict(annee_debut=2028, debut=2028),
    'dette_haute': dict(annee_debut=None, debut=2026, dette=1.60),
    'ecart_negatif': dict(annee_debut=None, debut=2026, ecart=-0.03),
    'ecart_positif': dict(annee_debut=None, debut=2026, ecart=+0.015),
}
# Lot 6 (calendrier de l'impulsion) : l'impulsion agit dès l'année de son budget, horizon 0. Les
# horizons 0 à 5 sont les six premières années d'effet, celles que couvraient les horizons 1 à 6
# quand l'effet commençait un an après le budget ; l'horizon 6 vaut désormais la 7e année d'effet,
# où le rapport de deux petits nombres n'est plus une mesure (1,2 % à l'état « écart positif »).
HORIZONS = (0, 1, 2, 3, 4, 5)
# Hors du domaine publié (dette à 180 % ou à 85 % du PIB en 2025) et gros choc (1,5 point de PIB) : le
# miroir n'y est vérifié que la première année d'effet. Au-delà, des non-linéarités légitimes,
# communes à toutes les familles, l'écartent de plus de 1 % (prime de taux plafonnée, facteur
# « dette élevée » franchi à 110 %, taille du choc) ; la première année, il est exact à 0,01 % près.
ETATS_PREMIER_AN = {
    'dette_tres_haute': dict(annee_debut=None, debut=2026, dette=1.80),
    'dette_basse': dict(annee_debut=None, debut=2026, dette=0.85),
}
ETATS_MIROIR = tuple(ETATS)
ETATS.update(ETATS_PREMIER_AN)
PERIODES = 10   # 2025-2035 : 6 ans après le budget 2028 = 2034 (indice 9)


def _indice(etat, horizon):
    """Indice de l'année « horizon ans après le premier budget de l'impulsion » (budget 2026, 4 ans
    → 2030 : convention du banc de tests/test_multiplicateurs_centraux_v067.py)."""
    return ETATS[etat]['debut'] - 2025 + horizon


def _simulateur(etat, levier=None, x0=0.0, mesures=None):
    e = ETATS[etat]

    class _Banc(BudgetSimulatorV45):
        def _reset_state(self):
            super()._reset_state()
            if 'ecart' in e:
                self.output_gap_courant = e['ecart']

        def apply_measures(self, year, spending, revenues, gdp, inflation, unemployment):
            sp, rv, imp = super().apply_measures(year, spending, revenues, gdp, inflation, unemployment)
            if levier and x0 and year >= e['debut']:
                # Ajoutée à l'impact du levier, s'il en a déjà un (droit en vigueur en mode cadre).
                x = x0 * gdp
                imp = dict(imp)
                bloc = dict(imp.get(levier) or {})
                bloc['depenses'] = float(bloc.get('depenses', 0) or 0) + x
                bloc['recettes'] = float(bloc.get('recettes', 0) or 0)
                imp[levier] = bloc
                sp += x
            return sp, rv, imp

    sim = _Banc(periods=PERIODES, mesures=mesures or {}, annee_debut=e['annee_debut'])
    if 'dette' in e:
        sim.base_params['dette_ratio'] = e['dette']
    return sim


def _pib_reel(sim):
    return sim.simulate()[1]['PIB_Réel_Base2025'].values


@pytest.fixture(scope='module')
def pleine_precision():
    import budget_simulator.engine.orchestrator as orch
    mp = pytest.MonkeyPatch()
    mp.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
    yield
    mp.undo()


@pytest.fixture(scope='module')
def trajectoires(pleine_precision):
    """PIB réel, calculé une fois par (état, levier, choc)."""
    cache = {}

    def pib(etat, levier=None, x0=0.0):
        cle = (etat, levier, x0)
        if cle not in cache:
            cache[cle] = _pib_reel(_simulateur(etat, levier, x0))
        return cache[cle]
    return pib


def _niveau(trajectoires, etat, levier, x0, horizon):
    i = _indice(etat, horizon)
    return (trajectoires(etat, levier, x0)[i] / trajectoires(etat)[i] - 1) * 100


# --- 1. Leviers dérivés du registre, familles gardées ------------------------------------------

def test_chaque_levier_de_depense_du_registre_est_range_dans_une_famille_gardee():
    """Tout levier de dépense du registre (cible « depenses » ou « mixte » de policy_measures.json)
    a un domaine de paramètres et est balayé ; tout levier qui stocke une impulsion de dépense est
    rangé dans une famille gardée par un test ; toute hausse de dépense courante atteignable est
    sondée par le miroir ci-dessous. Non-vacuité : le balayage retrouve les huit leviers connus au
    lot 5 (il peut en trouver d'autres : ils sont alors sondés d'office)."""
    registre = json.loads(REGISTRE.read_text(encoding='utf-8'))['mesures']
    de_depense = {m['id'] for m in registre if m.get('cible') in ('depenses', 'mixte')}
    assert de_depense <= set(balayage()), sorted(de_depense - set(balayage()))
    avec_depense = {levier for levier, vus in balayage().items()
                    if any(flux in ('depenses', 'investissement') for flux, _ in vus)}
    assert avec_depense, 'NON_VACUITE : aucun levier de dépense balayé'
    for levier in sorted(avec_depense | de_depense):
        assert famille(levier) in FAMILLES_GARDEES, levier
        if famille(levier) == 'dépense courante' and ('depenses', 'expansion') in balayage()[levier]:
            assert levier in LEVIERS, levier
        if famille(levier) == 'transferts':
            assert levier in S.TRANSFER_MEASURES - FiscalMultipliers.MESURES_MULTIPLICATEUR_NET
    assert {'defense', 'collectivites', 'fonction_publique', 'fonction_publique_reforme', 'immigration',
            'depenses_publiques', 'subventions_tge', 'sante'} <= set(HAUSSES_COURANTES), HAUSSES_COURANTES


# --- 2. Miroir dans le moteur complet ----------------------------------------------------------

@pytest.mark.parametrize('horizon', HORIZONS)
@pytest.mark.parametrize('etat', ETATS_MIROIR)
@pytest.mark.parametrize('levier', LEVIERS)
def test_hausse_et_baisse_de_depense_courante_en_miroir(trajectoires, levier, etat, horizon):
    """±1 point de PIB permanent : la hausse rapporte ce que la baisse coûte, à 1 % près, chacune
    des six premières années d'effet (horizons 0 à 5 depuis le lot 6, 1 à 6 avant). Rouge avant le
    lot 5 : rapport de 1,05 à 1,10 (hausse au coefficient des transferts) ; après : de 0,995 à
    1,007 ; après le lot 6 : de 0,996 à 1,006."""
    assert famille(levier) == 'dépense courante'
    hausse = _niveau(trajectoires, etat, levier, +0.01, horizon)
    baisse = _niveau(trajectoires, etat, levier, -0.01, horizon)
    assert hausse > 0 > baisse
    rapport = abs(baisse) / hausse
    assert abs(rapport - 1) < 0.01, (
        f'{levier}, {etat}, {horizon} ans : hausse {hausse:+.4f} %, baisse {baisse:+.4f} % '
        f'(rapport {rapport:.4f})')


# Gros choc : 1,5 point de PIB, où le filet de croissance ne mord pas. Lot 6 (calendrier de
# l'impulsion) : à 2 points, la hausse atteint le filet (+2,5 %, borne de validité des
# multiplicateurs linéaires) dès sa première année d'effet, désormais l'année du budget ; ce cas
# est gardé ci-dessous (test_gros_choc_…), qui exige que l'écart au miroir soit exactement la part
# écrêtée.
@pytest.mark.parametrize('etat, taille', [('dette_tres_haute', 0.01), ('dette_basse', 0.01),
                                           ('banc_historique', 0.015), ('cadre_2028', 0.015)])
@pytest.mark.parametrize('levier', LEVIERS)
def test_miroir_la_premiere_annee_hors_du_domaine_et_pour_un_gros_choc(trajectoires, levier, etat, taille):
    """La première année d'effet, hausse et baisse sont en miroir à 0,1 % près, aussi pour une dette
    hors du domaine publié et pour un choc de 1,5 point de PIB : une asymétrie réservée aux dettes
    très hautes ou basses, ou aux gros montants, s'y verrait. Mesuré : 0,01 % au plus."""
    # Première année d'effet = horizon 0 depuis le lot 6 (calendrier de l'impulsion).
    hausse = _niveau(trajectoires, etat, levier, +taille, 0)
    baisse = _niveau(trajectoires, etat, levier, -taille, 0)
    assert hausse > 0 > baisse
    assert abs(abs(baisse) / hausse - 1) < 0.001, (levier, etat, taille, hausse, baisse)


# Gros choc à 2 points de PIB (lot 6, revue adverse) : gardé, sous la forme qui DIT ce qu'il montre.
GROS_CHOC = 0.02


def _premiere_annee(etat, levier, x0, filet_leve=False):
    """(niveau du PIB réel en % de la référence, croissance de référence, écrêtage consigné par le
    filet l'année du budget ou None), la première année d'effet, pleine précision."""
    import budget_simulator.engine.growth as growth
    i = _indice(etat, 0)
    with pytest.MonkeyPatch.context() as mp:
        if filet_leve:
            mp.setattr(growth, 'CROISSANCE_FILET_MAX', 1.0)
        ref = _pib_reel(_simulateur(etat))
        sim = _simulateur(etat, levier, x0)
        y = _pib_reel(sim)
    assert y[i - 1] == ref[i - 1]          # l'année d'avant le budget ne bouge pas
    ecretage = [(calculee, ecretee) for annee, calculee, ecretee in sim._filet_croissance
                if annee == ETATS[etat]['debut']]
    return (y[i] / ref[i] - 1) * 100, ref[i] / ref[i - 1] - 1, (ecretage[0] if ecretage else None)


@pytest.mark.parametrize('etat', ['banc_historique', 'cadre_2028'])
@pytest.mark.parametrize('levier', LEVIERS)
def test_gros_choc_l_ecart_au_miroir_est_exactement_la_part_ecretee_par_le_filet(pleine_precision, levier, etat):
    """À 2 points de PIB, la hausse peut atteindre le filet de croissance (+2,5 %,
    ``CROISSANCE_FILET_MAX``, borne de validité des multiplicateurs linéaires) dès sa première année
    d'effet, qui est depuis le lot 6 l'année de son budget. Le filet n'est pas une asymétrie de la
    dépense courante ; ce test le montre au lieu de retirer le cas :

    1. la baisse n'est jamais écrêtée ;
    2. filet levé, hausse et baisse sont en miroir à 0,1 % près, comme pour 1,5 point ;
    3. filet en place, si la hausse est écrêtée, l'écart au miroir est EXACTEMENT la part écrêtée :
       niveau de la hausse + (croissance calculée − croissance écrêtée) / (1 + croissance de
       référence) = niveau de la hausse filet levé, à 1e-9 point près ;
    4. sinon (leviers au profil de l'investissement, dont la première année est plus faible), rien
       ne change en levant le filet.

    Mesuré avec les coefficients recalés du lot 6, levier synthétique : hausse +1,245 % contre
    baisse −1,370 % au banc historique (écart au miroir 10 %, croissance calculée 2,627 %), +1,213 %
    contre −1,374 % en mode cadre 2028 (13 %, croissance calculée 2,664 %) ; au commit d'équation,
    0,4 % et 3,6 %. Santé et réforme de l'État (profil de l'investissement) ne sont pas écrêtées."""
    hausse, g_ref, ecrete = _premiere_annee(etat, levier, +GROS_CHOC)
    baisse, _, ecrete_baisse = _premiere_annee(etat, levier, -GROS_CHOC)
    hausse_libre, _, ecrete_libre = _premiere_annee(etat, levier, +GROS_CHOC, filet_leve=True)
    assert ecrete_baisse is None and ecrete_libre is None
    assert hausse_libre > 0 > baisse
    assert abs(abs(baisse) / hausse_libre - 1) < 0.001, (levier, etat, hausse_libre, baisse)
    if ecrete is None:
        assert hausse == hausse_libre, (levier, etat)
    else:
        calculee, ecretee = ecrete
        assert calculee > ecretee
        part = (calculee - ecretee) / (1 + g_ref) * 100
        assert hausse + part == pytest.approx(hausse_libre, abs=1e-9), (levier, etat, hausse, part)


@pytest.mark.parametrize('etat', ['banc_historique', 'cadre_2028'])
def test_gros_choc_le_filet_mord_bien_sur_le_levier_synthetique(pleine_precision, etat):
    """Non-vacuité du test précédent : à 2 points, la hausse du levier synthétique est écrêtée
    l'année de son budget, et l'asymétrie qui en résulte dépasse la tolérance de 0,1 % des autres
    premières années (c'est elle que le passage à 1,5 point avait fait disparaître)."""
    hausse, _, ecrete = _premiere_annee(etat, 'depense_courante_synthetique', +GROS_CHOC)
    baisse, _, _ = _premiere_annee(etat, 'depense_courante_synthetique', -GROS_CHOC)
    assert ecrete is not None
    assert abs(baisse) / hausse - 1 > 0.001, (etat, hausse, baisse)


NOMBRES = {0: 'aucun', 1: 'un seul', 2: 'deux', 3: 'trois', 4: 'quatre', 5: 'cinq'}


def test_limite_du_filet_la_premiere_annee_declaree_et_liee_aux_instantanes():
    """METHODOLOGIE (§ « Calendrier de l'impulsion », limites) déclare combien de programmes publiés
    atteignent le filet de croissance dès leur première année : mode historique, budget 2026 ; mode
    cadre, budget 2028. Les nombres sont relus dans les instantanés des programmes publiés
    (``tests/snapshots``), pas recopiés."""
    import json as _json
    from budget_simulator.constants import CROISSANCE_FILET_MAX
    snap = Path(__file__).resolve().parent / 'snapshots'
    texte = ' '.join((Path(__file__).resolve().parent.parent / 'docs' / 'METHODOLOGIE.md')
                     .read_text(encoding='utf-8').split())

    def au_filet(fichier, indice):
        programmes = _json.loads((snap / fichier).read_text(encoding='utf-8'))
        return len(programmes), sum(1 for p in programmes.values()
                                    if p['data']['Croissance %'][indice] >= CROISSANCE_FILET_MAX * 100 - 1e-9)
    total, historique = au_filet('golden_master_v1.json', 1)
    total_cadre, cadre = au_filet('golden_master_cadre_2028.json', 3)
    assert total == total_cadre == 10
    assert historique >= 1, 'NON_VACUITE'
    attendu = (f'En mode historique (non publié), {NOMBRES[historique]} des dix programmes publiés '
               f"l'atteignent dès leur première année (2026)")
    assert attendu in texte, attendu
    assert f'en mode cadre (publié), {NOMBRES[cadre]}.' in texte, cadre


def test_etats_non_triviaux(trajectoires):
    """Les états sondés diffèrent vraiment du banc historique : l'écart de production négatif
    active le régime de récession (×1,15 au plein régime) ; la dette haute, le mode cadre et l'écart
    de production positif déplacent la référence ; l'écart positif garde l'économie au-dessus de
    son potentiel quand l'impulsion est stockée."""
    h = {etat: _niveau(trajectoires, etat, 'depense_courante_synthetique', +0.01, 4) for etat in ETATS}
    assert h['ecart_negatif'] > 1.05 * h['banc_historique'], h
    for etat in ('dette_haute', 'cadre_2028', 'ecart_negatif', 'ecart_positif', 'dette_tres_haute',
                 'dette_basse'):
        i = _indice(etat, 4)
        assert trajectoires(etat)[i] != trajectoires('banc_historique')[i], etat
    sim = _simulateur('ecart_positif', 'depense_courante_synthetique', +0.01)
    ecarts = []
    origine = sim._stocker_impulsions

    def espion(year, eco_state, niveaux=None):
        ecarts.append(eco_state['output_gap'])
        return origine(year, eco_state, niveaux)
    sim._stocker_impulsions = espion
    sim.simulate()
    # Premier stockage de l'impulsion (budget 2026, stocké en 2026 depuis le lot 6 ; deux appels par
    # année, hors effet propre puis définitif) : écart de production > 0,5 %.
    assert ecarts[0] == ecarts[1] > 0.005, ecarts


# --- 2 bis. Rythme de la dépense courante (option du lot 6, équation) ---------------------------------

@pytest.mark.parametrize('signe', [+1, -1], ids=['hausse', 'baisse'])
@pytest.mark.parametrize('etat', ['banc_historique', 'cadre_2028'])
@pytest.mark.parametrize('levier', ['sante', 'fonction_publique_reforme'])
def test_sante_et_reforme_de_l_etat_au_rythme_de_la_depense_courante(trajectoires, levier, etat, signe):
    """Option du lot 6 (équation, arbitrage du mainteneur à rendre) : la santé et la réforme de l'État,
    qui prennent le COEFFICIENT de la dépense courante depuis la v0.6.0 (« consommation/optimisation
    publique »), en prennent aussi le RYTHME. Jusque-là, ``INVESTMENT_FLOW_MEASURES`` leur donnait le
    profil de l'investissement (classement de la première version publique, sans source) : 0,28 point
    de PIB la première année contre 0,69 pour une dépense courante, avec le profil d'investissement calé
    sur le FMI. Désormais, leur chemin est celui d'un levier de dépense courante de même coefficient
    (levier synthétique, absent de toute liste), au bit près, chaque année d'effet, dans les deux sens
    et les deux modes."""
    for horizon in HORIZONS:
        assert _niveau(trajectoires, etat, levier, signe * 0.01, horizon) == pytest.approx(
            _niveau(trajectoires, etat, 'depense_courante_synthetique', signe * 0.01, horizon),
            abs=1e-12), (levier, etat, signe, horizon)


# --- 3. Le vrai curseur : défense ±10 Md€ autour de sa référence ---------------------------------

# Lot 6 (calendrier de l'impulsion) : deux horizons, l'année d'effet d'avant le lot et l'année
# calendaire d'avant le lot (voir la docstring).
@pytest.mark.parametrize('horizon, tolerance', [(3, 0.01), (4, 0.015)])
@pytest.mark.parametrize('etat', ['banc_historique', 'cadre_2028'])
def test_curseur_defense_en_miroir(pleine_precision, etat, horizon, tolerance):
    """Handler réel (``defense.budget``), ±10 Md€ autour de la valeur par défaut (mode historique)
    ou du droit en vigueur (mode cadre, où la baisse fait passer le flux d'une hausse à une coupe :
    l'impulsion est scindée en zéro). Rouge avant le lot 5 : 1,089 et 1,031 ; après : 1,007.

    Re-déclaré au lot 6 (calendrier de l'impulsion), deux horizons au lieu d'un :
    - horizon 3, la 4e année d'effet, celle que lisait l'horizon 4 avant le lot (l'effet commençait
      un an après le budget) : tolérance de 1 % inchangée ;
    - horizon 4, l'année calendaire d'avant le lot (budget 2026 → 2030), devenue la 5e année
      d'effet : tolérance de 1,5 %. Le curseur est un montant FIXE en Md€, et l'écart au miroir
      croît d'environ 0,2 point par année d'effet ; mesuré au banc historique, années d'effet 2 à 6 :
      1,0038 / 1,0061 / 1,0087 / 1,0108 / 1,0132 avec les coefficients recalés (1,0034 / 1,0056 /
      1,0080 / 1,0099 / 1,0121 au commit d'équation), 1,0020 / 1,0044 / 1,0073 / 1,0099 / 1,0130
      avant le lot (mode cadre 2028 : 1,0091 et 1,0111 aux horizons 3 et 4). Le même
      levier en part FIXE du PIB (banc générique ci-dessus, ±0,33 point) reste sous 0,2 % la 5e
      année. 1,5 % couvre cette dérive connue et rougit toujours l'asymétrie de coefficient que la
      garde vise (1,089 et 1,031 avant le lot 5)."""
    ref = 50.0 if ETATS[etat]['annee_debut'] is None else float(
        charger_droit_en_vigueur().mesures['defense']['budget'])
    i = _indice(etat, horizon)
    y0 = _pib_reel(_simulateur(etat, mesures={'defense': {'budget': ref}}))
    yh = _pib_reel(_simulateur(etat, mesures={'defense': {'budget': ref + 10}}))
    yb = _pib_reel(_simulateur(etat, mesures={'defense': {'budget': ref - 10}}))
    hausse, baisse = yh[i] / y0[i] - 1, yb[i] / y0[i] - 1
    assert hausse > 0 > baisse
    assert abs(abs(baisse) / hausse - 1) < tolerance, (etat, horizon, hausse, baisse)


# --- 4. Le coefficient n'est lu par aucun autre flux -----------------------------------------------

def _sans_hausse_de_depense_courante(sim):
    return not [cle for cle in sim._fiscal_impulses
                if cle[2] == 'depenses' and cle[3] == 'expansion' and famille(cle[1]) == 'dépense courante']


# (levier, flux, signe) injectés au banc historique : aucun n'est une hausse de dépense courante.
PROGRAMMES_SANS_HAUSSE_COURANTE = {
    'hausse_transferts': [('retraites', 'depenses', +1)],
    'coupe_transferts': [('retraites', 'depenses', -1)],
    'hausse_impots': [('tva_rate', 'recettes', +1)],
    'baisse_impots': [('impot_revenu', 'recettes', -1)],
    'hausse_investissement': [('education', 'depenses', +1)],
    'coupe_investissement': [('education', 'depenses', -1)],
    'coupe_depense_courante': [('collectivites', 'depenses', -1)],
    'mixte': [('retraites', 'depenses', +1), ('tva_rate', 'recettes', -1),
              ('education', 'depenses', +1), ('defense', 'depenses', -1)],
}


def _programme(flux, coefficient=None):
    class _Programme(BudgetSimulatorV45):
        def apply_measures(self, year, spending, revenues, gdp, inflation, unemployment):
            sp, rv, imp = super().apply_measures(year, spending, revenues, gdp, inflation, unemployment)
            imp = dict(imp)
            for levier, cote, signe in flux:
                x = 0.01 * gdp * signe
                imp[levier] = {'depenses': x if cote == 'depenses' else 0.0,
                               'recettes': x if cote == 'recettes' else 0.0}
                if cote == 'depenses':
                    sp += x
                else:
                    rv += x
            return sp, rv, imp
    sim = _Programme(periods=PERIODES, mesures={})
    if coefficient is not None:
        sim.multipliers.base_multipliers['expansion']['spending_based'] = coefficient
    df, annuel, _ = sim.simulate()
    return sim, df, annuel


@pytest.mark.parametrize('nom', list(PROGRAMMES_SANS_HAUSSE_COURANTE))
def test_coefficient_sans_effet_hors_hausse_de_depense_courante(nom):
    """Transferts, impôts, investissement (hausses et baisses) et coupes de dépense courante :
    avec le coefficient de la hausse de dépense courante mis à 0 ou à 3, toutes les sorties sont
    identiques au bit."""
    flux = PROGRAMMES_SANS_HAUSSE_COURANTE[nom]
    sim, df, annuel = _programme(flux)
    assert sim._fiscal_impulses and _sans_hausse_de_depense_courante(sim)
    for coefficient in (0.0, 3.0):
        _, df2, annuel2 = _programme(flux, coefficient)
        assert df.equals(df2) and annuel.equals(annuel2), (nom, coefficient)


def test_curseurs_reels_sans_hausse_courante_identiques_au_bit():
    """Programme par les vrais curseurs (mode historique), sans hausse de dépense courante :
    transferts en hausse, TVA en baisse, éducation en hausse, dotations en baisse."""
    mesures = {'retraites': {'indexation': 1.1}, 'tva_rate': {'taux': 0.19},
               'education': {'budget': 80}, 'collectivites': {'dotation': 110},
               'prestations_menages': {'solidarite': 5.0}}

    def run(coefficient=None):
        sim = BudgetSimulatorV45(periods=PERIODES, mesures=mesures)
        if coefficient is not None:
            sim.multipliers.base_multipliers['expansion']['spending_based'] = coefficient
        df, annuel, _ = sim.simulate()
        return sim, df, annuel
    sim, df, annuel = run()
    assert sim._fiscal_impulses and _sans_hausse_de_depense_courante(sim)
    _, df2, annuel2 = run(0.0)
    assert df.equals(df2) and annuel.equals(annuel2)


def test_le_coefficient_porte_bien_la_hausse_de_depense_courante():
    """Non-vacuité du test précédent : sur une hausse de dépense courante, le même changement de
    coefficient déplace la trajectoire."""
    _, df, _ = _programme([('defense', 'depenses', +1)])
    _, df2, _ = _programme([('defense', 'depenses', +1)], 0.0)
    assert not df.equals(df2)


# --- 5. Aucun effet par un autre chemin -------------------------------------------------------------

def _est_hausse_de_depense_courante(sens, composition, levier):
    return (sens == 'expansion' and composition.get('depenses') == 1.0
            and not composition.get('investissement') and not composition.get('transferts')
            and levier not in FiscalMultipliers.MESURES_MULTIPLICATEUR_NET)


@pytest.mark.parametrize('annee_debut', [None, 2028])
def test_le_coefficient_n_entre_que_dans_les_hausses_de_depense_courante(monkeypatch, annee_debut):
    """Espion sur ``get_multiplier`` pendant la simulation complète d'un programme qui touche toutes
    les familles dans les deux sens (vrais curseurs, dont les postes, le point d'indice, la réforme
    de l'État et l'aide médicale de l'État) : chaque appel est rejoué sur une table neuve, avec le
    coefficient de la hausse de dépense courante mis à 0. Les deux valeurs diffèrent si et
    seulement si l'appel est une hausse de dépense courante (ni investissement, ni transfert, ni
    coefficient propre)."""
    mesures = {'defense': {'budget': 62}, 'collectivites': {'dotation': 110, 'investissement': 6},
               'depenses_publiques': {'credits_etat': 8, 'ondam': -3}, 'subventions_tge': {'montant': 30},
               'fonction_publique': {'effectifs': 60000, 'point_indice': 3},
               'fonction_publique_reforme': {'digitalisation': 80}, 'immigration': {'ame': 2.0},
               'retraites': {'indexation': 1.1}, 'prestations_menages': {'solidarite': -4},
               'education': {'budget': 80}, 'recherche_publique': {'budget': 12},
               'tva_rate': {'taux': 0.21}, 'impot_revenu': {'taux_superieur': 0.42},
               'smic': {'montant_brut': 1900}, 'fraude_fiscale': {'effort': 0.5}}
    appels = []
    origine = FiscalMultipliers.get_multiplier

    def espion(self, effort_type, composition, economic_state, year, measure_id=None):
        appels.append((effort_type, dict(composition), dict(economic_state), year, measure_id))
        return origine(self, effort_type, composition, economic_state, year, measure_id)
    monkeypatch.setattr(FiscalMultipliers, 'get_multiplier', espion)
    BudgetSimulatorV45(periods=PERIODES, mesures=mesures, annee_debut=annee_debut).simulate()
    monkeypatch.setattr(FiscalMultipliers, 'get_multiplier', origine)

    familles, hausses_courantes = set(), set()
    for sens, compo, etat, annee, levier in appels:
        normal = FiscalMultipliers().get_multiplier(sens, compo, etat, annee, levier)
        autre = FiscalMultipliers()
        autre.base_multipliers['expansion']['spending_based'] = 0.0
        modifie = autre.get_multiplier(sens, compo, etat, annee, levier)
        attendu = _est_hausse_de_depense_courante(sens, compo, levier)
        assert (normal != modifie) == attendu, (sens, compo, levier, normal, modifie)
        familles.add((sens, attendu, compo.get('recettes') == 1.0, bool(compo.get('investissement')),
                      bool(compo.get('transferts'))))
        if attendu:
            hausses_courantes.add(levier)
    # Non-vacuité : hausses de dépense courante, et au moins une autre famille dans chaque sens.
    assert ('expansion', True, False, False, False) in familles
    assert {('expansion', False, True, False, False), ('consolidation', False, False, False, False)} <= familles
    assert {'defense', 'fonction_publique', 'fonction_publique_reforme', 'immigration'} <= hausses_courantes


@pytest.mark.parametrize('levier', COURANTS_DU_REGISTRE + ('depense_courante_synthetique',))
def test_coefficient_de_la_hausse_egal_a_celui_de_la_coupe(levier):
    """Au niveau de la table : même coefficient dans les deux sens pour chaque levier de dépense
    courante du registre (y compris ceux qui ne montent pas dans leur domaine), dans les régimes
    normal, de récession, d'expansion et de dette basse."""
    compo = {'depenses': 1.0, 'recettes': 0.0, 'investissement': 0.0, 'transferts': 0.0}
    for etat in ({'output_gap': 0.0, 'unemployment_gap': 0.0, 'debt_ratio': 1.15},
                 {'output_gap': -0.03, 'unemployment_gap': 0.02, 'debt_ratio': 1.15},
                 {'output_gap': 0.03, 'unemployment_gap': -0.02, 'debt_ratio': 1.15},
                 {'output_gap': -0.015, 'unemployment_gap': 0.0, 'debt_ratio': 0.9}):
        etat = dict(etat, interest_rate=0.023)
        hausse = FiscalMultipliers().get_multiplier('expansion', compo, etat, 3, levier)
        coupe = FiscalMultipliers().get_multiplier('consolidation', compo, etat, 3, levier)
        assert hausse == pytest.approx(-coupe, abs=1e-12), (levier, etat)
