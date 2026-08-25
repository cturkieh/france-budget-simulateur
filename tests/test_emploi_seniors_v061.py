"""Tests-propriétés v0.6.1 — canal emploi seniors (lot 3, items I7 à I11).

Ce que le lot câble, et pourquoi les trois briques sont indissociables
(elles forment une identité comptable — COR, séance plénière du 26 mars 2026,
Document n° 3, encadré 2) :

- **I7 — canal d'offre → PIB.** Un report de l'âge d'ouverture des droits (AOD)
  augmente l'offre de travail, donc le PIB POTENTIEL : ``+0,80 pt de NIVEAU de
  PIB par année d'AOD à long terme`` (COR 26/03/2026, Doc n° 2 T4, consensus
  des trois équipes : « 0,7 à 0,9 point »). Profilé par le produit de
  l'absorption macroéconomique (moyenne des trois modèles) et de la montée en
  charge par cohortes.
- **I8 — bosse de chômage transitoire.** ``+0,18 pt au pic par année d'AOD``,
  résorbée selon le profil OFCE. C'est une DÉRIVATION MAISON (trois routes
  0,13 / 0,19 / 0,21) — jamais une estimation officielle : la valeur ex ante
  est irréductiblement NON TRANCHÉE (COR 26/03/2026 Doc n° 2 T4 : DG Trésor
  0,00 / I-MIP −0,40 / OFCE +0,55 à 1 an).
- **I9 — fuite sociale résiduelle.** ``+9,6 %`` de la moindre dépense brute
  (= IJ 36 % + minima 12 % de la clé DREES/DARES) et NON 20 % : la part
  assurance-chômage (52 %) est déjà produite endogènement par la catégorie de
  dépense ``chomage``, indexée sur le taux de chômage.
- **I10 — anti-double-comptage des cotisations.** Traité PAR CONSTRUCTION
  (arbitrage C2 du propriétaire, 25/08/2026) : le handler n'inscrit que la
  ligne A (moindres dépenses de pension) ; cotisations (B) et autres recettes
  (C) naissent entièrement du canal PIB. Aucun coefficient correcteur n'est
  inventé — la garde est structurelle, et ce fichier la mesure (P3, P4).

Sens des corrections (§ C.5 du dossier) — les deux sens sont câblés dans le
même lot, c'est ce qui rend l'ensemble neutre :
- I7 joue **POUR** les programmes de report d'âge (canal PIB positif, absent
  depuis la v0.6.0) ;
- I8 et I9 jouent **CONTRE** eux (bosse de chômage et fuite sociale, absentes
  aujourd'hui).
Et tout est **strictement symétrique** (arbitrage C1) : un abaissement d'un an
retire au PIB exactement ce qu'un report d'un an lui apporte.

Pièges verrouillés ici :
1. **NIVEAU ≠ TAUX** (P7). La v0.6.0 ajoutait « +0,8 pt » au TAUX de croissance
   chaque année, ce qui composait à ~+8 % de PIB en dix ans. Le canal est un
   effet de NIVEAU : la table pilote le niveau, le moteur ne consomme que son
   INCRÉMENT annuel (+0,12 pt maximum une seule année).
2. **Amplification AR(1)** (P2). ``calculate_unemployment`` enchaîne
   Okun → impacts directs → convergence NAIRU (``u = 0,94·u + 0,06·nairu``).
   Un écart injecté avant la convergence — ou laissé s'accumuler d'une année
   sur l'autre — converge vers ``15,67 ×`` sa valeur. La bosse est donc un
   écart de NIVEAU explicite : la part de l'année précédente est retirée avant
   la récurrence, l'écart mesuré vaut exactement la table.

Sources primaires (toutes consultées le 24/08/2026, cf. dossier de sourcing) :
- COR, séance plénière du 26 mars 2026, « Impact macroéconomique des leviers
  d'équilibre financier d'un système de retraite », Doc n° 2 (SG-COR, T4),
  Doc n° 3 (DG Trésor, T4 p. 7 et encadré 2), Doc n° 5 (OFCE/EmeRaude),
  Dossier en bref.
- Cour des comptes, « Situation financière et perspectives du système de
  retraites », février 2025 : tableau n° 6 p. 72 (bouclage 17,7 Md€),
  p. 67-68 note 125 (clé DREES/DARES).
- Dubois & Koubi (Insee DT G2016/08, 2016) ; Rabaté & Rochut (JPEF 19(3),
  2020, p. 293-308) — parts « chômage » 26-27 %, deux méthodologies
  indépendantes.
"""
import ast
import inspect
from pathlib import Path

import pytest

from budget_simulator import _seniors
from budget_simulator import constants
from budget_simulator.constants import (
    ABSORPTION_OFFRE_SENIORS,
    CHOMAGE_SENIORS_PIC,
    FUITE_SOCIALE_RESIDUELLE,
    OFFRE_SENIORS_PIB_NIVEAU_LT,
    PHASING_CHOMAGE_SENIORS,
    PHASING_OFFRE_SENIORS,
    PHASING_RETRAITES_5ANS,
    POLICY_START_YEAR,
    RESORPTION_CHOMAGE_SENIORS,
    RETRAITES_COEFF_AGE_MD_EUR,
    RETRAITES_PART_COTISATIONS_PO,
    retraites_ref_age_ans,
)
from budget_simulator.simulator import BudgetSimulatorV45

PACKAGE = Path(constants.__file__).resolve().parent

#: Horizon simulé par défaut (2026 → 2035), soit dix millésimes de politique.
ANNEES = tuple(range(POLICY_START_YEAR, POLICY_START_YEAR + 10))

#: Écart de chômage publié, en POINTS, pour un écart CONSTANT d'une année
#: d'AOD (dossier de sourcing, brique E, table Y1-Y10). Y1 est à 0,035 et non
#: 0,036 : le dossier arrondit 0,98 × 0,20 × 0,18 = 0,03528 vers le haut, la
#: table du moteur reproduit le produit exact.
ECART_CHOMAGE_PUBLIE_PT = (
    0.035, 0.072, 0.089, 0.097, 0.100, 0.091, 0.084, 0.077, 0.070, 0.064,
)

#: Niveau de PIB publié, en POINTS, pour un écart constant d'une année d'AOD.
NIVEAU_PIB_PUBLIE_PT = (
    0.02, 0.11, 0.19, 0.29, 0.41, 0.43, 0.46, 0.49, 0.53, 0.56,
)


def _mesures_ecart(ecart_ans, year):
    """Mesures produisant un écart d'``ecart_ans`` au droit en vigueur de ``year``.

    L'âge légal de référence MONTE (62,75 en 2026-2027 puis +3 mois par an
    jusqu'à 64,0 en 2032) : un scénario à ``age_depart`` figé ne décrit donc
    PAS un écart constant. Pour mesurer les profils publiés — qui sont tous
    définis « par année d'AOD » — il faut reconstruire l'âge année par année.
    """
    return {'retraites': {'age_depart': retraites_ref_age_ans(year) + ecart_ans}}


def _simuler(mesures=None, periods=10, debt_drag=None):
    """Simulation 10 ans. ``debt_drag=0.0`` neutralise le seul canal par lequel
    le NIVEAU du PIB rétroagit sur la croissance de DEMANDE — l'isolation déjà
    utilisée par ``test_okun_potentiel_v061.py``."""
    sim = BudgetSimulatorV45(periods=periods, mesures=mesures or {})
    if debt_drag is not None:
        sim.economic_coeffs['debt_drag'] = debt_drag
    df, detail, rapport = sim.simulate()
    return sim, df, detail, rapport


def _neutraliser(monkeypatch, nom_table):
    """Met une table de profil à zéro — isolation d'une brique du canal.

    Permet de mesurer une brique par DIFFÉRENCE entre deux simulations par
    ailleurs identiques : tous les autres canaux (impulsion budgétaire,
    multiplicateur, canal de dette) sont présents des deux côtés et se
    compensent exactement.
    """
    zero = tuple(0.0 for _ in getattr(_seniors, nom_table))
    monkeypatch.setattr(_seniors, nom_table, zero)


# ---------------------------------------------------------------------------
# 1. Les profils câblés SONT ceux des sources (verrou de sourcing)
# ---------------------------------------------------------------------------

def test_profil_offre_est_le_produit_absorption_x_cohortes():
    """``PHASING_OFFRE_SENIORS`` = absorption COR × montée en charge cohortes.

    Le produit des deux profils est un CHOIX À ASSUMER (§ B.1-11 : les deux
    phénomènes sont distincts, mais le produit n'est mesuré par personne).
    Ce test rend le choix auditable : la table câblée doit rester le produit
    exact de ses deux facteurs, chacun publié séparément.
    """
    for idx, (attendu, absorption) in enumerate(
            zip(PHASING_OFFRE_SENIORS, ABSORPTION_OFFRE_SENIORS)):
        cohortes = PHASING_RETRAITES_5ANS[min(idx, len(PHASING_RETRAITES_5ANS) - 1)]
        assert attendu == pytest.approx(absorption * cohortes, abs=1e-3), (
            f"Y{idx + 1} : {attendu} != {absorption} × {cohortes}")


def test_profil_chomage_est_le_produit_resorption_x_cohortes():
    """``PHASING_CHOMAGE_SENIORS`` = résorption OFCE × montée en charge cohortes."""
    for idx, (attendu, resorption) in enumerate(
            zip(PHASING_CHOMAGE_SENIORS, RESORPTION_CHOMAGE_SENIORS)):
        cohortes = PHASING_RETRAITES_5ANS[min(idx, len(PHASING_RETRAITES_5ANS) - 1)]
        assert attendu == pytest.approx(resorption * cohortes, abs=1e-3), (
            f"Y{idx + 1} : {attendu} != {resorption} × {cohortes}")


@pytest.mark.parametrize('idx', range(10))
def test_niveau_pib_reproduit_la_table_publiee(idx):
    """Le niveau de PIB par année d'AOD suit la table publiée (brique D)."""
    year = POLICY_START_YEAR + idx
    niveau = _seniors.offre_seniors_niveau_pib(_mesures_ecart(1.0, year), year)

    assert niveau * 100 == pytest.approx(NIVEAU_PIB_PUBLIE_PT[idx], abs=5e-3)


@pytest.mark.parametrize('idx', range(10))
def test_ecart_chomage_reproduit_la_table_publiee(idx):
    """L'écart de chômage par année d'AOD suit la table publiée (brique E)."""
    year = POLICY_START_YEAR + idx
    ecart = _seniors.chomage_seniors_ecart(_mesures_ecart(1.0, year), year)

    assert ecart * 100 == pytest.approx(ECART_CHOMAGE_PUBLIE_PT[idx], abs=1e-3)


def test_valeur_de_long_terme_est_le_consensus_cor():
    """+0,80 pt de PIB par année d'AOD à long terme = milieu du consensus COR
    (« 0,7 à 0,9 point », Dossier en bref du 26/03/2026)."""
    assert 0.007 <= OFFRE_SENIORS_PIB_NIVEAU_LT <= 0.009


def test_pic_de_chomage_reste_entre_dg_tresor_et_ofce():
    """+0,18 pt est une DÉRIVATION MAISON, à situer dans le débat, jamais à
    présenter comme publiée : DG Trésor 0,00 / OFCE +0,55 à 1 an
    (COR 26/03/2026 Doc n° 2 T4), Mésange +0,7 que la Cour désavoue
    explicitement (fév. 2025, p. 67, note 121). Les trois routes de la
    dérivation donnent 0,13 / 0,19 / 0,21."""
    assert 0.0013 < CHOMAGE_SENIORS_PIC < 0.0021


# ---------------------------------------------------------------------------
# 2. I7 — NIVEAU de PIB, pas TAUX de croissance (P7)
# ---------------------------------------------------------------------------

def test_p7_increment_de_croissance_jamais_au_dessus_de_015_pt():
    """P7 — pour UNE année d'AOD, l'incrément annuel de croissance imputable
    au canal ne dépasse JAMAIS +0,15 pt.

    C'est le garde-fou contre l'erreur retirée de la v0.6.0 : un « +0,8 pt »
    appliqué au TAUX de croissance chaque année compose à ~+8 % de PIB en dix
    ans, soit quatorze fois l'effet publié.
    """
    sim = BudgetSimulatorV45(periods=10)
    increments = []
    for year in ANNEES:
        sim.mesures = _mesures_ecart(1.0, year)
        sim.update_labour_supply(year)
        increments.append(sim._labour_supply_bonus)

    assert max(increments) < 0.0015, (
        f"incrément maximal {max(increments) * 100:+.3f} pt > 0,15 pt")
    # L'incrément maximal publié est de +0,120 pt, atteint une seule année (Y5).
    assert max(increments) * 100 == pytest.approx(0.120, abs=5e-3)
    assert increments.index(max(increments)) == 4


def test_increment_est_la_difference_du_niveau():
    """Le moteur ne consomme que l'INCRÉMENT : la somme des incréments d'une
    trajectoire reconstitue exactement le niveau visé de l'année."""
    sim = BudgetSimulatorV45(periods=10)
    cumul = 0.0
    for year in ANNEES:
        sim.mesures = _mesures_ecart(1.0, year)
        sim.update_labour_supply(year)
        cumul += sim._labour_supply_bonus
        attendu = _seniors.offre_seniors_niveau_pib(sim.mesures, year)
        assert cumul == pytest.approx(attendu, abs=1e-12)


def test_effet_de_niveau_borne_le_pib_a_dix_ans():
    """Bout en bout : à 2035, un scénario « 65 ans » (soit exactement UNE
    année au-dessus du droit en vigueur, qui vaut 64,0 ans depuis 2032)
    ajoute ~0,56 pt de PIB réel — le niveau publié — et NON ~8 % (v0.6.0)."""
    _, _, detail_sans, _ = _simuler()
    _, _, detail_avec, _ = _simuler({'retraites': {'age_depart': 65.0}})

    ecart_pct = (detail_avec['PIB_Réel_Base2025'].iloc[-1]
                 / detail_sans['PIB_Réel_Base2025'].iloc[-1] - 1) * 100

    assert 0.35 < ecart_pct < 0.80, (
        f"niveau de PIB 2035 {ecart_pct:+.2f} % hors de la fenêtre publiée")


def test_canal_offre_strictement_symetrique():
    """Arbitrage C1 — symétrie stricte : abaisser l'AOD d'un an retire au PIB
    exactement ce qu'un report d'un an lui apporte. Le facteur d'asymétrie
    0,70 publié par la Cour est REJETÉ (il allégerait mécaniquement le coût
    affiché des programmes d'abaissement, donc prendrait parti)."""
    for ecart in (0.25, 1.0, 2.25):
        for year in ANNEES:
            hausse = _seniors.offre_seniors_niveau_pib(_mesures_ecart(ecart, year), year)
            baisse = _seniors.offre_seniors_niveau_pib(_mesures_ecart(-ecart, year), year)
            assert hausse == pytest.approx(-baisse, abs=1e-15)


def test_statu_quo_neutre_sur_le_canal_offre():
    """Un curseur laissé sur le droit en vigueur ne produit AUCUN bonus
    d'offre, aucune année — sinon le statu quo ne serait plus le statu quo."""
    sim = BudgetSimulatorV45(periods=10)
    for year in ANNEES:
        sim.mesures = _mesures_ecart(0.0, year)
        sim.update_labour_supply(year)
        assert sim._labour_supply_bonus == 0.0


def test_canal_offre_ne_transite_pas_par_la_potentielle_tendancielle():
    """Piège du § I6 : le canal ne doit pas passer par
    ``base_params['croissance_potentielle']``, que ``update_potential_growth``
    clippe dans [0,007 ; 0,012] et mute en place (hystérèse). Il y serait
    écrêté ET rendu permanent, alors qu'il est transitoire."""
    _, _, detail_sans, _ = _simuler()
    _, _, detail_avec, _ = _simuler({'retraites': {'age_depart': 65.0}})

    assert (list(detail_sans['Croissance_Potentielle %'])
            == list(detail_avec['Croissance_Potentielle %']))


def test_colonne_bonus_offre_travail_publiee():
    """La trajectoire détaillée expose le canal : sans colonne dédiée, un
    lecteur ne peut pas séparer l'offre de TRAVAIL de l'offre STRUCTURELLE
    dans ``Croissance_Potentielle_Totale %``."""
    _, _, detail, _ = _simuler({'retraites': {'age_depart': 65.0}})

    assert 'Bonus_Offre_Travail %' in detail.columns
    assert detail['Bonus_Offre_Travail %'].iloc[0] == 0.0
    assert detail['Bonus_Offre_Travail %'].abs().max() > 0.0


# ---------------------------------------------------------------------------
# 3. I8 — la bosse de chômage, et le piège AR(1) (P2)
# ---------------------------------------------------------------------------

def test_p2_profil_maximal_en_y4_y5_puis_decroissant():
    """P2, volet profil — pour un écart CONSTANT d'une année d'AOD, l'écart de
    chômage culmine en Y4-Y5 puis décroît strictement."""
    ecarts = [_seniors.chomage_seniors_ecart(_mesures_ecart(1.0, y), y) for y in ANNEES]

    assert ecarts.index(max(ecarts)) in (3, 4), (
        f"pic en Y{ecarts.index(max(ecarts)) + 1}, attendu Y4 ou Y5")
    assert all(a > b for a, b in zip(ecarts[4:], ecarts[5:])), (
        "l'écart doit décroître strictement après le pic")
    assert max(ecarts) * 100 == pytest.approx(0.100, abs=5e-3)


def test_p2_ecart_a_dix_ans_est_bien_celui_de_la_source():
    """P2, volet horizon — RECALIBRATION DOCUMENTÉE.

    Le dossier consolidé écrit « < 0,03 pt en Y10 ». C'est une erreur de
    transcription : 0,029 pt est la valeur à VINGT ans du profil de résorption
    OFCE, pas à dix. À dix ans la source donne 0,18 × 0,357 = 0,064 pt, et
    c'est cette valeur — publiée dans la table de la brique E — qui est
    câblée. On ne comble ni ne rabote une source pour faire passer un seuil :
    on teste la valeur sourcée et on dit d'où vient l'écart.

    Ce qui compte pour la propriété visée (résorption réelle) est verrouillé
    quand même : à dix ans l'écart vaut moins des deux tiers du pic.
    """
    ecarts = [_seniors.chomage_seniors_ecart(_mesures_ecart(1.0, y), y) for y in ANNEES]

    assert ecarts[-1] * 100 == pytest.approx(0.064, abs=1e-3)
    assert ecarts[-1] < 0.66 * max(ecarts)


def test_p2_pas_amplification_ar1_bout_en_bout(monkeypatch):
    """P2, volet load-bearing — l'écart de chômage MESURÉ par le moteur vaut
    la table, pas 15,67 fois la table.

    ``calculate_unemployment`` enchaîne Okun → impacts directs → convergence
    NAIRU (``u = 0,94·u + 0,06·nairu``). Un terme injecté via
    ``impacts['chomage']`` obéirait à ``d_t = 0,94·(d_{t−1} + c)``, d'état
    stationnaire ``15,67·c`` : +0,10 pt deviendrait +1,57 pt. Laisser la bosse
    s'accumuler d'une année sur l'autre donnerait ``c/0,06 = 16,67·c``, pire
    encore. La bosse est donc un écart de NIVEAU : la part de l'année
    précédente est retirée avant la récurrence.

    Isolation : les deux simulations portent le MÊME scénario, seule la table
    de la bosse est neutralisée dans la seconde. Toute la mécanique
    budgétaire (moindres dépenses, fuite sociale, multiplicateur, canal de
    dette, canal d'offre) est présente des deux côtés et se compense.
    """
    mesures = {'retraites': {'age_depart': 65.0}}
    # Table de référence calculée AVANT la neutralisation (qui la met à zéro).
    attendu = [_seniors.chomage_seniors_ecart(mesures, y) * 100 for y in ANNEES]

    _, df_avec, _, _ = _simuler(mesures)
    _neutraliser(monkeypatch, 'PHASING_CHOMAGE_SENIORS')
    _, df_sans, _, _ = _simuler(mesures)

    mesure = [a - b for a, b in zip(df_avec['Chômage %'][1:], df_sans['Chômage %'][1:])]

    for annee, (obtenu, cible) in enumerate(zip(mesure, attendu), start=1):
        assert obtenu == pytest.approx(cible, abs=0.01), (
            f"Y{annee} : écart mesuré {obtenu:+.3f} pt vs table {cible:+.3f} pt")


def test_bosse_chomage_symetrique():
    """Symétrie stricte (C1) : abaisser l'AOD retire du chômage ce qu'un
    report en ajoute. Le canal ne prend pas parti."""
    for year in ANNEES:
        hausse = _seniors.chomage_seniors_ecart(_mesures_ecart(1.0, year), year)
        baisse = _seniors.chomage_seniors_ecart(_mesures_ecart(-1.0, year), year)
        assert hausse == pytest.approx(-baisse, abs=1e-15)


def test_bosse_ne_passe_pas_par_impacts_chomage():
    """Méta-garde du piège : le handler retraites ne doit émettre AUCUNE clé
    ``chomage``, sous peine de repasser par le canal amplifié ×15,67."""
    sim = BudgetSimulatorV45(periods=1, mesures={'retraites': {'age_depart': 65.0}})
    _, _, impacts = sim._apply_retraites(
        {'id': 'retraites'}, {'age_depart': 65.0}, 2030, 2991, 0.015, 0.076)

    assert 'chomage' not in impacts

    # Garde de source, sur les CHAÎNES du code seul (les commentaires du
    # handler parlent légitimement de la catégorie de dépense `chomage`).
    arbre = ast.parse(inspect.getsource(type(sim)._apply_retraites).lstrip())
    chaines = {n.value for n in ast.walk(arbre)
               if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert 'chomage' not in chaines


def test_bosse_ne_derive_pas_apres_le_pic(monkeypatch):
    """Contre-épreuve d'accumulation : si la bosse s'accumulait, l'écart
    mesuré CROÎTRAIT encore à dix ans alors que la table décroît."""
    mesures = {'retraites': {'age_depart': 65.0}}
    _, df_avec, _, _ = _simuler(mesures)
    _neutraliser(monkeypatch, 'PHASING_CHOMAGE_SENIORS')
    _, df_sans, _, _ = _simuler(mesures)

    mesure = [a - b for a, b in zip(df_avec['Chômage %'][1:], df_sans['Chômage %'][1:])]

    assert mesure[-1] < mesure[4], (
        f"écart Y10 {mesure[-1]:+.3f} pt >= écart Y5 {mesure[4]:+.3f} pt : "
        "la bosse s'accumule au lieu de se résorber")


# ---------------------------------------------------------------------------
# 4. I9 — fuite sociale résiduelle (P5)
# ---------------------------------------------------------------------------

def test_fuite_sociale_est_96_pct_de_la_moindre_depense_brute():
    """La fuite retenue est 9,6 % (= 48 % × 20 %) et NON 20 % : la part
    assurance-chômage de la clé DREES/DARES (52 %) est déjà produite
    endogènement par la catégorie de dépense ``chomage``."""
    sim = BudgetSimulatorV45(periods=1)
    year = 2035  # phasing cohortes = 1,00 ; référence légale = 64,0 ans
    params = {'age_depart': 65.0, 'indexation': 1.0, 'duree_cotisation': 42.5}

    delta, _, _ = sim._apply_retraites({'id': 'retraites'}, params, year, 2991, 0.015, 0.076)

    brut = RETRAITES_COEFF_AGE_MD_EUR * 1.0
    assert delta == pytest.approx(-brut * (1 - FUITE_SOCIALE_RESIDUELLE), abs=1e-9)
    assert FUITE_SOCIALE_RESIDUELLE == pytest.approx(0.48 * 0.20, abs=1e-9)


def test_fuite_sociale_symetrique():
    """Un abaissement d'âge produit une fuite sociale de signe inverse (moins
    d'indemnités journalières et de minima sociaux) — symétrie C1."""
    sim = BudgetSimulatorV45(periods=1)
    year = 2035
    base = {'indexation': 1.0, 'duree_cotisation': 42.5}

    hausse, _, _ = sim._apply_retraites(
        {'id': 'retraites'}, {**base, 'age_depart': 65.0}, year, 2991, 0.015, 0.076)
    baisse, _, _ = sim._apply_retraites(
        {'id': 'retraites'}, {**base, 'age_depart': 63.0}, year, 2991, 0.015, 0.076)

    assert hausse == pytest.approx(-baisse, abs=1e-9)


def test_p5_depense_chomage_au_pic(monkeypatch):
    """P5 — la dépense supplémentaire de la catégorie ``chomage`` au pic vaut
    0,45 à 0,70 Md€ par année d'AOD (cible 0,62 = 52 % × 20 % × 6,0 Md€).

    C'est la vérification croisée qui justifie de retenir 9,6 % et non 20 % :
    si le canal endogène du moteur reproduit bien la brique assurance-chômage
    de la clé DREES/DARES, l'inscrire en plus dans le handler serait un
    double comptage.
    """
    mesures = {'retraites': {'age_depart': 65.0}}
    sim_avec, df_avec, _, _ = _simuler(mesures)
    _neutraliser(monkeypatch, 'PHASING_CHOMAGE_SENIORS')
    _, df_sans, _, _ = _simuler(mesures)

    base_chomage = sim_avec.spending_categories_base['chomage']
    u_base = sim_avec.base_params['chomage_base']

    depenses_par_an_aod = []
    for idx, year in enumerate(ANNEES, start=1):
        ecart_u = (df_avec['Chômage %'].iloc[idx] - df_sans['Chômage %'].iloc[idx]) / 100
        ecart_age = _seniors.retraites_ecart_age_ans_moteur(mesures, year)
        depenses_par_an_aod.append(base_chomage * ecart_u / u_base / ecart_age)

    pic = max(depenses_par_an_aod)
    assert 0.45 <= pic <= 0.70, (
        f"dépense chômage au pic {pic:.2f} Md€ par année d'AOD hors fenêtre")


# ---------------------------------------------------------------------------
# 5. I10 — bouclage budgétaire et anti-double-comptage (P3, P4)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('avec_multiplication', [True, False])
def test_p3_bouclage_budgetaire_cour_t6(monkeypatch, avec_multiplication):
    """P3 — pour UNE année d'AOD à horizon dix ans, ``Δrecettes + Δ(−dépenses)``
    ∈ [14 ; 19] Md€, cible 17,7 (Cour des comptes fév. 2025, T6 p. 72 :
    dépenses +6,0 / cotisations retraite +2,4 / autres recettes +9,3).

    Le scénario « 65 ans » vaut exactement UNE année au-dessus du droit en
    vigueur à 2035 (la référence légale ayant atteint 64,0 ans en 2032) : la
    comparaison porte donc bien sur le même objet que la Cour.

    Le test tourne AVEC et SANS la multiplication du profil d'absorption par
    la montée en charge par cohortes — c'est le test de sensibilité exigé par
    le § B.1-11 (le produit des deux profils est un choix assumé, non mesuré).
    Les deux profils coïncident à partir de Y5, donc le bouclage à dix ans ne
    doit pas dépendre de ce choix : c'est précisément ce que le test prouve.
    """
    if not avec_multiplication:
        monkeypatch.setattr(_seniors, 'PHASING_OFFRE_SENIORS', ABSORPTION_OFFRE_SENIORS)

    mesures = {'retraites': {'age_depart': 65.0}}
    _, _, detail_avec, rapport = _simuler(mesures)
    monkeypatch.setattr(
        _seniors, 'PHASING_OFFRE_SENIORS',
        tuple(0.0 for _ in _seniors.PHASING_OFFRE_SENIORS))
    _, _, detail_sans, _ = _simuler(mesures)

    recettes_canal = (detail_avec['Recettes_Totales'].iloc[-1]
                      - detail_sans['Recettes_Totales'].iloc[-1])
    moindres_depenses = -rapport['measure_impacts_by_year'][-1]['retraites']['depenses']

    bouclage = recettes_canal + moindres_depenses
    assert 14.0 <= bouclage <= 19.0, (
        f"bouclage {bouclage:.1f} Md€ hors [14 ; 19] "
        f"(recettes canal {recettes_canal:.1f}, moindres dépenses "
        f"{moindres_depenses:.1f})")


def test_p3_bouclage_robuste_au_canal_de_dette(monkeypatch):
    """P3, contre-épreuve d'isolation.

    La recette du canal est mesurée par différence entre deux simulations. Il
    subsiste dans cette différence un canal ÉCONOMIQUE légitime mais absent de
    la comptabilité de la Cour : un PIB plus élevé abaisse le ratio de dette,
    donc le ``debt_drag`` de ``calculate_growth`` mord moins, donc un peu de
    croissance de demande en plus. Ce test vérifie que le bouclage tient AUSSI
    sans lui — sinon la concordance avec les 17,7 Md€ tiendrait à un effet de
    second ordre plutôt qu'au canal lui-même.

    Mesuré : 17,5 Md€ en régime complet, 16,1 Md€ canal de dette neutralisé.
    """
    mesures = {'retraites': {'age_depart': 65.0}}
    _, _, detail_avec, rapport = _simuler(mesures, debt_drag=0.0)
    _neutraliser(monkeypatch, 'PHASING_OFFRE_SENIORS')
    _, _, detail_sans, _ = _simuler(mesures, debt_drag=0.0)

    bouclage = (detail_avec['Recettes_Totales'].iloc[-1]
                - detail_sans['Recettes_Totales'].iloc[-1]
                - rapport['measure_impacts_by_year'][-1]['retraites']['depenses'])

    assert 14.0 <= bouclage <= 19.0, (
        f"bouclage canal de dette neutralisé {bouclage:.1f} Md€ hors [14 ; 19]")


def test_p4_part_des_cotisations_deja_comptee(monkeypatch):
    """P4 — la recette engendrée par le canal d'offre, multipliée par 20,5 %,
    doit approcher la ligne B de la Cour (2,4 Md€) à ±25 %.

    20,5 % = 2,4 / (2,4 + 9,3), Cour fév. 2025 T6 p. 72. C'est la mesure du
    double comptage ÉVITÉ : la DG Trésor applique 53 % au surcroît de PIB NET
    des cotisations retraites (COR 26/03/2026, Doc n° 3, encadré 2, note 6)
    parce qu'elles sont déjà comptées dans le solde du système ; le moteur
    applique une élasticité unitaire au PIB, donc il produit les DEUX lignes —
    ce qui n'est correct QUE parce que le handler n'a plus de slot
    cotisations (arbitrage C2).
    """
    mesures = {'retraites': {'age_depart': 65.0}}
    _, _, detail_avec, _ = _simuler(mesures)
    _neutraliser(monkeypatch, 'PHASING_OFFRE_SENIORS')
    _, _, detail_sans, _ = _simuler(mesures)

    recettes_canal = (detail_avec['Recettes_Totales'].iloc[-1]
                      - detail_sans['Recettes_Totales'].iloc[-1])
    cotisations = recettes_canal * RETRAITES_PART_COTISATIONS_PO

    assert 1.8 <= cotisations <= 3.0, (
        f"cotisations reconstituées {cotisations:.2f} Md€ hors 2,4 ±25 % "
        f"(recettes canal {recettes_canal:.1f} Md€)")


def test_aucun_slot_cotisations_dans_le_handler():
    """Arbitrage C2 — le handler n'inscrit que la ligne A. Un slot recettes
    rendrait le double comptage possible ; son absence le rend structurellement
    impossible."""
    sim = BudgetSimulatorV45(periods=1)
    for age in (60.0, 62.75, 65.0, 67.0):
        _, delta_revenue, impacts = sim._apply_retraites(
            {'id': 'retraites'},
            {'age_depart': age, 'indexation': 1.0, 'duree_cotisation': 42.5},
            2035, 2991, 0.015, 0.076)
        assert delta_revenue == 0
        assert 'recettes' not in impacts

    assert RETRAITES_PART_COTISATIONS_PO == pytest.approx(2.4 / 11.7, abs=1e-3)


# ---------------------------------------------------------------------------
# 6. I11 — sobriété : ce qui ne doit PAS être câblé (P8)
# ---------------------------------------------------------------------------

#: Valeurs rondes que le canal seniors partage par COÏNCIDENCE avec des
#: calibrations sans rapport déjà présentes dans le moteur (0,008 = plafond
#: d'un crowding-out et une pente de spread ; 0,025 = plafond de croissance et
#: seuil d'inflation ; 0,4 = un profil de phasing de niches ; 0,98 = un seuil
#: de détection de récession dans le handler impôt sur les sociétés). Les
#: inclure rendrait la garde bruyante sans rien ajouter : ce sont les valeurs
#: DISCRIMINANTES qui trahissent une duplication du canal.
_VALEURS_AMBIGUES = frozenset({0.008, 0.025, 0.4, 0.98})

#: Valeurs de calibration du canal seniors. Aucune ne doit apparaître en
#: littéral ailleurs que dans ``constants.py`` — même règle que les bornes
#: Gini (source unique, recalibrage impossible à moitié).
_VALEURS_INTERDITES = frozenset(
    [OFFRE_SENIORS_PIB_NIVEAU_LT, CHOMAGE_SENIORS_PIC,
     FUITE_SOCIALE_RESIDUELLE, RETRAITES_PART_COTISATIONS_PO]
    + list(PHASING_OFFRE_SENIORS)
    + list(PHASING_CHOMAGE_SENIORS)
    + list(ABSORPTION_OFFRE_SENIORS)
    + list(RESORPTION_CHOMAGE_SENIORS)
) - _VALEURS_AMBIGUES - frozenset({0.0, 1.0})


def test_p8_aucun_litteral_de_calibration_seniors_hors_constants():
    """P8 — méta-garde de source unique.

    PORTÉE / LIMITE (même contrat que ``test_okun_potentiel_v061.py``) : la
    détection est SYNTAXIQUE, sur les littéraux numériques du package. Une
    valeur reconstruite (``0.05 + 0.046``) y échapperait. C'est une
    anti-régression du motif courant, pas une preuve d'absence.
    """
    fautes = []
    for chemin in sorted(PACKAGE.rglob('*.py')):
        if chemin.name == 'constants.py':
            continue
        arbre = ast.parse(chemin.read_text(encoding='utf-8'), filename=str(chemin))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Constant) and isinstance(noeud.value, float):
                if noeud.value in _VALEURS_INTERDITES:
                    fautes.append(
                        f"{chemin.relative_to(PACKAGE)}:{noeud.lineno} → {noeud.value}")

    assert fautes == [], (
        "valeurs de calibration du canal seniors en littéral hors "
        "constants.py :\n" + "\n".join(fautes))


def test_p8_canaux_ecartes_non_cables():
    """Les quatre tentations que le dossier écarte explicitement ne doivent
    apparaître nulle part dans le moteur :

    - **éviction de l'emploi des jeunes** : consensus macro sur l'absence
      d'effet (Kalwij, Kapteyn & De Vos 2010 sur 22 pays OCDE 1960-2008 ;
      Gruber, Milligan & Wise 2009 ; Ben Salem, Blanchet, Bozio & Roger 2010 ;
      Munnell & Wu 2012 ; Carta, D'Amuri & von Wachter 2025) — l'effet existe
      au niveau de la FIRME et ne remonte pas au macro ;
    - **effet sur la productivité** : « la littérature empirique ne met pas en
      évidence d'effet négatif systématique » (COR 26/03/2026, Doc n° 6, p. 8) ;
    - **baisse de l'épargne par anticipation** (canal I-MIP) : non identifiable
      en France, la DG Trésor émet elle-même un doute (COR Doc n° 3, annexe
      p. 8-9) ;
    - **élasticité OFCE 0,30 emploi/population active** : décrit un choc
      « soudain » et indifférencié, quand l'ex post français donne 0,60-0,70.
    """
    interdits = ('eviction_jeunes', 'éviction_jeunes', 'productivite_seniors',
                 'epargne_anticipation', 'elasticite_ofce')
    fautes = []
    for chemin in sorted(PACKAGE.rglob('*.py')):
        texte = chemin.read_text(encoding='utf-8').lower()
        for token in interdits:
            if token in texte:
                fautes.append(f"{chemin.relative_to(PACKAGE)} → {token}")

    assert fautes == [], "canal explicitement écarté par le dossier : " + str(fautes)


# ---------------------------------------------------------------------------
# 7. Hygiène d'état : le canal est transitoire, jamais reporté
# ---------------------------------------------------------------------------

def test_etats_du_canal_reinitialises_entre_deux_simulations():
    """Le niveau d'offre cumulé et l'écart de chômage de l'année précédente
    sont des accumulateurs : sans reset, une seconde simulation partirait de
    l'état final de la première."""
    sim = BudgetSimulatorV45(periods=10, mesures={'retraites': {'age_depart': 65.0}})
    df1, _, _ = sim.simulate()
    df2, _, _ = sim.simulate()

    assert list(df1['Chômage %']) == list(df2['Chômage %'])
    assert list(df1['PIB']) == list(df2['PIB'])


def test_lecture_defensive_du_parametre_age():
    """Le canal macro lit ``mesures`` en amont de la boucle des mesures : il
    doit y être DÉFENSIF sur le type. La porte unique tracée reste
    ``apply_measures`` (logger.error + ``HANDLER_FAILED_KEY``, ExceptionGroup
    en mode STRICT) — lever ici court-circuiterait ce contrat, et l'anomalie
    ne serait pas rendue plus visible."""
    for valeur in ('pas-un-nombre', None, float('nan'), True):
        mesures = {'retraites': {'age_depart': valeur}}
        assert _seniors.retraites_ecart_age_ans_moteur(mesures, 2030) == 0.0

    assert _seniors.retraites_ecart_age_ans_moteur({}, 2030) == 0.0


def test_ecart_age_borne_par_le_registre_de_domaines():
    """Le canal macro et le canal budgétaire doivent voir le MÊME âge : sans
    bornage par ``PARAM_DOMAINS``, une entrée hors domaine (scénario, API)
    ferait diverger les deux. Le WARNING (ou le raise STRICT) reste émis par
    la porte unique, pas ici : ce bornage aligne, il ne masque pas."""
    low, high = constants.PARAM_DOMAINS['retraites']['age_depart']
    ref = retraites_ref_age_ans(2030)

    assert _seniors.retraites_ecart_age_ans_moteur(
        {'retraites': {'age_depart': 99.0}}, 2030) == pytest.approx(high - ref)
    assert _seniors.retraites_ecart_age_ans_moteur(
        {'retraites': {'age_depart': 10.0}}, 2030) == pytest.approx(low - ref)


def test_au_dela_de_dix_ans_les_profils_sont_geles_et_conservateurs():
    """Convention déclarée au-delà de l'horizon publié.

    L'horizon du simulateur est de dix ans, mais l'API accepte ``periods``
    jusqu'à 50. Les deux tables comptent dix millésimes et le phasing borne à
    la dernière valeur : l'absorption reste à 0,702 (au lieu de monter vers
    0,846 à vingt ans) et la résorption du chômage reste à 0,357 (au lieu de
    descendre vers 0,161).

    Ce test verrouille le fait — et son SENS : les deux gels vont dans la même
    direction, ils sous-estiment le gain de PIB d'un report d'âge ET
    surestiment sa bosse de chômage. Le chiffrage au-delà de dix ans est donc
    conservateur CONTRE les programmes de report d'âge. Étendre les tables
    demanderait d'interpoler neuf millésimes que le COR ne publie pas : c'est
    une décision à prendre explicitement, pas un effet de bord.
    """
    horizon = POLICY_START_YEAR + 9
    for annee in (horizon + 1, horizon + 5, horizon + 20):
        assert (_seniors.offre_seniors_niveau_pib(_mesures_ecart(1.0, annee), annee)
                == pytest.approx(OFFRE_SENIORS_PIB_NIVEAU_LT * PHASING_OFFRE_SENIORS[-1]))
        assert (_seniors.chomage_seniors_ecart(_mesures_ecart(1.0, annee), annee)
                == pytest.approx(CHOMAGE_SENIORS_PIC * PHASING_CHOMAGE_SENIORS[-1]))

    # Le sens du gel : sous le long terme côté PIB, au-dessus de zéro côté
    # chômage — les deux jouent contre le report d'âge.
    assert PHASING_OFFRE_SENIORS[-1] < 1.0
    assert PHASING_CHOMAGE_SENIORS[-1] > 0.0


def test_source_unique_de_lecart_dage():
    """Le handler (canal budgétaire) et le moteur (canaux macro) dérivent leur
    écart d'âge de la MÊME fonction : sans source unique, un recalibrage du
    calendrier légal n'atteindrait qu'un des deux canaux."""
    source = inspect.getsource(BudgetSimulatorV45._apply_retraites)

    assert 'retraites_ecart_age_ans' in source

    # Contre-épreuve comportementale : sur tout le domaine UI et tout
    # l'horizon, le handler et le moteur voient le même écart.
    borne_basse, borne_haute = constants.PARAM_DOMAINS['retraites']['age_depart']
    for annee in ANNEES:
        for age in (borne_basse, 62.75, 64.0, borne_haute):
            assert _seniors.retraites_ecart_age_ans({'age_depart': age}, annee) == (
                _seniors.retraites_ecart_age_ans_moteur(
                    {'retraites': {'age_depart': age}}, annee))
