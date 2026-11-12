"""Release E — commit SOCLE : constantes nommées et signées (aucun résultat ne bouge).

Contrat : ``docs/plans/contrat-curseurs-release-E-2026-11.md`` du dépôt parent,
§ 1.3 (dérivation des coefficients par Md€) et § 7.2 (contenu du socle).

Ce que ce fichier verrouille :

1. EXTRACTION AU BIT. Les littéraux des handlers existants listés au § 1.3
   deviennent des constantes nommées de MÊME valeur, lues par les handlers dans
   le même ordre d'opérations. La preuve « aucune sortie ne bouge » est portée
   par les golden masters (``make snapshot-diff`` sans régénération) ; ici :
   valeur exacte de chaque constante, et lecture effective par le handler
   (test par MUTATION : doubler la constante double l'effet).
2. DÉRIVATIONS. Chaque coefficient par Md€ des nouveaux leviers est écrit dans
   ``constants.py`` comme une EXPRESSION des noms extraits (jamais un nombre
   recopié) ; le test recalcule la formule du § 1.3 et vérifie l'ordre de
   grandeur annoncé par le contrat.
3. SIGNES (G11 sur les constantes, relecture B1). Une constante « …_PAR_MD »
   vaut l'effet d'un +1 Md€ du paramètre du levier : une hausse de recette sur
   le patrimoine baisse le Gini, une hausse de taxe indirecte l'augmente, une
   hausse de prestation le baisse, un impôt d'entreprise en plus baisse la
   compétitivité. Les handlers n'ajouteront aucun signe.
4. DONNÉES SOURCÉES ET BORNES. Valeurs du § 7.2, chacune avec sa source en
   commentaire dans ``constants.py``.
5. REGISTRE ET SQUELETTES (sections 7 à 10). Onze leviers au registre, neutres
   dérivés, neutralité au bit G1 (deux modes, deux portes, rapport compris),
   squelettes qui refusent toute valeur non neutre ; ``LEVIERS_NON_LIVRES`` =
   exactement les squelettes, vide avant tout tag ; bloc au neutre d'un levier
   absent du droit en vigueur retiré du programme en mode cadre.
"""
import hashlib
import inspect
import math
import re
from pathlib import Path

import pytest

import budget_simulator.constants as C
import budget_simulator.handlers.competitivite as mod_competitivite
import budget_simulator.handlers.fiscalite_menages as mod_fiscalite
from budget_simulator.engine.cadre import ANNEE_DEBUT_MAX
from budget_simulator.simulator import BudgetSimulatorV45

RACINE = Path(__file__).absolute().parent.parent
CONSTANTS_PY = RACINE / 'budget_simulator' / 'constants.py'


# ---------------------------------------------------------------------------
# 1. Extraction au bit : valeurs exactes des constantes extraites
# ---------------------------------------------------------------------------

# (nom, valeur du littéral remplacé, fichier:handler d'origine). Égalité EXACTE
# (==, et même type numérique) : une constante « de même valeur » qui différerait
# d'un ulp changerait les golden masters.
EXTRAITES = [
    ('PATRIMOINE_GINI_PAR_10MD', -0.010, 'fiscalite_menages._apply_fiscalite_patrimoine'),
    ('PATRIMOINE_COMPET_PAR_10MD', -0.002, 'fiscalite_menages._apply_fiscalite_patrimoine'),
    ('ISF_GINI_PAR_12MD', -0.020, 'fiscalite_menages._apply_isf_climatique'),
    ('ISF_COMPET_PAR_12MD', -0.002, 'fiscalite_menages._apply_isf_climatique'),
    ('ISF_TAUX_MAX', 0.01, 'fiscalite_menages._apply_isf_climatique'),
    ('ISF_PHASAGE', (0.5, 1.0), 'fiscalite_menages._apply_isf_climatique'),
    ('IR_GINI_DECOTE', 0.003, 'fiscalite_menages._apply_impot_revenu'),
    ('IR_RECETTE_DECOTE', 7.5, 'fiscalite_menages._apply_impot_revenu'),
    ('IR_GINI_PAR_5PTS', -0.008, 'fiscalite_menages._apply_impot_revenu'),
    ('ETI_PLANCHER_FACTEUR', 0.5, 'fiscalite_menages._apply_impot_revenu'),
    # COUT_PAR_POINT_COTIS_SAL (6.0 extrait au bit par le socle) : remplacé par
    # 1 % de la masse salariale brute 2025 (décision du mainteneur du 12/11/2026),
    # tests/test_release_e_arbitrages.py, point 1.
    ('TVA_GINI_PAR_2PTS', 0.005, 'fiscalite_menages._apply_tva_rate'),
    ('TVA_COMPET_PAR_2PTS', -0.0005, 'fiscalite_menages._apply_tva_rate'),
    ('TVA_ENERGIE_GINI_PAR_TAUX', 0.05, 'fiscalite_menages._apply_tva_energie'),
    ('TVA_ENERGIE_CONSO_ELECTRICITE_MD', 60.0, 'fiscalite_menages._apply_tva_energie'),
    ('TVA_ENERGIE_CONSO_GAZ_MD', 60.0, 'fiscalite_menages._apply_tva_energie'),
    ('IS_COMPET_PAR_MD', 0.015, 'competitivite._apply_impot_societes'),
    ('IMPOTS_PRODUCTION_COMPET_PAR_MD', 0.020, 'competitivite._apply_impots_production'),
    ('IS_EXCEPTIONNEL_COMPET_PAR_MD', 0.003, 'competitivite._apply_is_exceptionnel_tge'),
    ('MASSE_RETRAITES_2025_MD_EUR', 380, 'simulator.spending_categories_base'),
]


@pytest.mark.parametrize('nom, valeur, origine', EXTRAITES, ids=[e[0] for e in EXTRAITES])
def test_constante_extraite_meme_valeur_meme_type(nom, valeur, origine):
    assert hasattr(C, nom), f"{nom} absente de constants.py (extraite de {origine})"
    obtenu = getattr(C, nom)
    assert obtenu == valeur and type(obtenu) is type(valeur), (nom, obtenu, valeur)


# Le littéral ne doit plus figurer dans le corps du handler : il lit le nom.
LITTERAUX_RETIRES = [
    (mod_fiscalite.FiscaliteMenagesMixin._apply_fiscalite_patrimoine,
     ['PATRIMOINE_GINI_PAR_10MD', 'PATRIMOINE_COMPET_PAR_10MD'], [r'-0\.010\b', r'-0\.002\b']),
    (mod_fiscalite.FiscaliteMenagesMixin._apply_isf_climatique,
     ['ISF_GINI_PAR_12MD', 'ISF_COMPET_PAR_12MD', 'ISF_TAUX_MAX', 'ISF_PHASAGE'],
     [r'-0\.020\b', r'-0\.002\b', r'taux_max = 0\.01\b', r'\(0\.5, 1\.0\)']),
    (mod_fiscalite.FiscaliteMenagesMixin._apply_impot_revenu,
     ['IR_GINI_DECOTE', 'IR_RECETTE_DECOTE', 'IR_GINI_PAR_5PTS', 'ETI_PLANCHER_FACTEUR'],
     [r'-0\.008\b', r'0\.003 \*', r'\* 7\.5\b', r'max\(0\.5,']),
    (mod_fiscalite.FiscaliteMenagesMixin._apply_cotisations_salariales,
     ['COUT_PAR_POINT_COTIS_SAL'], [r'COUT_PAR_POINT = 6\.0']),
    (mod_fiscalite.FiscaliteMenagesMixin._apply_tva_rate,
     ['TVA_GINI_PAR_2PTS', 'TVA_COMPET_PAR_2PTS', 'recette_tva_taux'],
     [r'return 0\.005 \*', r'return -0\.0005 \*', r'0\.53 \* gdp']),
    (mod_fiscalite.FiscaliteMenagesMixin._apply_tva_energie,
     ['TVA_ENERGIE_GINI_PAR_TAUX', 'TVA_ENERGIE_CONSO_ELECTRICITE_MD', 'TVA_ENERGIE_CONSO_GAZ_MD'],
     [r'\* 0\.05 \*', r'= 60\.0']),
    (mod_competitivite.CompetitiviteMixin._apply_impot_societes,
     ['IS_COMPET_PAR_MD'], [r'\* 0\.015\b']),
    (mod_competitivite.CompetitiviteMixin._apply_impots_production,
     ['IMPOTS_PRODUCTION_COMPET_PAR_MD'], [r"p\['montant'\]\) \* 0\.020\b"]),
    (mod_competitivite.CompetitiviteMixin._apply_is_exceptionnel_tge,
     ['IS_EXCEPTIONNEL_COMPET_PAR_MD'], [r'\* 0\.003\b']),
]


@pytest.mark.parametrize('handler, noms, motifs', LITTERAUX_RETIRES,
                         ids=[h.__name__ for h, _, _ in LITTERAUX_RETIRES])
def test_handler_lit_le_nom_et_plus_le_litteral(handler, noms, motifs):
    # Lignes de code seulement : les commentaires et docstrings citent légitimement
    # les valeurs (« Règle : TVA +2 % = −0,0005 »).
    lignes = [l.split('#')[0] for l in inspect.getsource(handler).splitlines()]
    code = '\n'.join(l for l in lignes if not l.strip().startswith(('"', "'")))
    for nom in noms:
        assert re.search(rf'\b{nom}\b', code), f"{handler.__name__} ne lit pas {nom}"
    for motif in motifs:
        assert not re.search(motif, code), f"{handler.__name__} garde le littéral {motif!r}"


def test_simulator_lit_la_masse_des_retraites():
    sim = BudgetSimulatorV45(periods=1)
    masse = sim.spending_categories_base['retraites']
    assert masse == C.MASSE_RETRAITES_2025_MD_EUR and type(masse) is int
    source = inspect.getsource(BudgetSimulatorV45.__init__)
    assert "'retraites': MASSE_RETRAITES_2025_MD_EUR" in source


# --- Mutation : le handler LIT la constante (pas une copie locale) ----------

def _sim_handler():
    sim = BudgetSimulatorV45(periods=1)
    sim._reset_state()
    return sim


def test_mutation_patrimoine(monkeypatch):
    sim = _sim_handler()
    _, _, ref = sim._apply_fiscalite_patrimoine({}, {'intensite': 0.2}, 2026, 3000.0, 0.02, 0.076)
    monkeypatch.setattr(mod_fiscalite, 'PATRIMOINE_GINI_PAR_10MD', 2 * C.PATRIMOINE_GINI_PAR_10MD)
    monkeypatch.setattr(mod_fiscalite, 'PATRIMOINE_COMPET_PAR_10MD', 2 * C.PATRIMOINE_COMPET_PAR_10MD)
    sim = _sim_handler()
    _, _, mut = sim._apply_fiscalite_patrimoine({}, {'intensite': 0.2}, 2026, 3000.0, 0.02, 0.076)
    assert mut['gini'] == pytest.approx(2 * ref['gini'], rel=1e-12) and ref['gini'] != 0
    assert mut['competitivite'] == pytest.approx(2 * ref['competitivite'], rel=1e-12)


def test_mutation_isf(monkeypatch):
    sim = _sim_handler()
    _, _, ref = sim._apply_isf_climatique({}, {'intensite': 1.0}, 2026, 3000.0, 0.02, 0.076)
    monkeypatch.setattr(mod_fiscalite, 'ISF_GINI_PAR_12MD', 2 * C.ISF_GINI_PAR_12MD)
    monkeypatch.setattr(mod_fiscalite, 'ISF_COMPET_PAR_12MD', 2 * C.ISF_COMPET_PAR_12MD)
    sim = _sim_handler()
    _, _, mut = sim._apply_isf_climatique({}, {'intensite': 1.0}, 2026, 3000.0, 0.02, 0.076)
    assert mut['gini'] == pytest.approx(2 * ref['gini'], rel=1e-12) and ref['gini'] != 0
    assert mut['competitivite'] == pytest.approx(2 * ref['competitivite'], rel=1e-12)


def test_mutation_competitivite_is(monkeypatch):
    sim = _sim_handler()
    _, _, ref = sim._apply_impot_societes({}, {'taux': 0.30}, 2026, 3000.0, 0.02, 0.076)
    monkeypatch.setattr(mod_competitivite, 'IS_COMPET_PAR_MD', 2 * C.IS_COMPET_PAR_MD)
    sim = _sim_handler()
    _, _, mut = sim._apply_impot_societes({}, {'taux': 0.30}, 2026, 3000.0, 0.02, 0.076)
    assert mut['competitivite'] == pytest.approx(2 * ref['competitivite'], rel=1e-12)
    assert ref['competitivite'] != 0


# ---------------------------------------------------------------------------
# 2. La fonction de recette de tva_rate : le handler l'APPELLE, la dérivation aussi
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('taux', [0.055, 0.10, 0.19, 0.20, 0.21, 0.22, 0.23, 0.25])
@pytest.mark.parametrize('chomage', [0.076, 0.11])
def test_recette_tva_taux_egale_au_handler_au_bit(taux, chomage):
    sim = _sim_handler()
    _, rec, impacts = sim._apply_tva_rate({}, {'taux': taux}, 2026, 3012.5, 0.02, chomage)
    assert rec == C.recette_tva_taux(taux, 3012.5, chomage)
    assert impacts['recettes'] == rec


# ---------------------------------------------------------------------------
# 3. Dérivations du § 1.3, recalculées, et ordres de grandeur du contrat
# ---------------------------------------------------------------------------

def test_horizon_du_mandat():
    assert C.ANNEE_FIN_MANDAT == ANNEE_DEBUT_MAX == 2032
    assert C.ANNEE_PREMIER_BUDGET_MANDAT == 2028
    assert C.HORIZON_MANDAT_ANNEES == C.ANNEE_FIN_MANDAT - C.ANNEE_PREMIER_BUDGET_MANDAT + 1 == 5


def test_gini_pensions_derive_de_l_emission_effective_des_retraites():
    n = C.HORIZON_MANDAT_ANNEES
    attendu = (-C.RETRAITES_GINI_PAR_POINT_DESINDEXATION
               * (1 + C.RETRAITES_GINI_RESIDU_FLUX * (n - 1))
               / (C.MASSE_RETRAITES_2025_MD_EUR * (1 - (1 + C.INFLATION_STRUCTURELLE) ** -n)))
    assert C.GINI_PENSIONS_PAR_MD == attendu
    # Contrat § 1.3 : −0,005 × 1,4 / 28,96 ≈ −0,00024 (ancien contrat 0,00082).
    assert C.GINI_PENSIONS_PAR_MD == pytest.approx(-0.00024, abs=0.000005)


DERIVEES = [
    ('GINI_SOLIDARITE_PAR_MD', lambda: -C.GINI_ALLOC_PAR_MD_EUR, -0.0008),
    ('GINI_PATRIMOINE_PAR_MD', lambda: C.PATRIMOINE_GINI_PAR_10MD / 10, -0.001),
    ('COMPET_PATRIMOINE_PAR_MD', lambda: C.PATRIMOINE_COMPET_PAR_10MD / 10, -0.0002),
    ('GINI_ISF_EFFECTIF_PAR_MD', lambda: C.ISF_GINI_PAR_12MD / 12 * C.ISF_PHASAGE[0] ** 2, -0.00042),
    ('COMPET_ISF_EFFECTIF_PAR_MD', lambda: C.ISF_COMPET_PAR_12MD / 12 * C.ISF_PHASAGE[0] ** 2, -0.000042),
    ('GINI_IR_DECOTE_PAR_MD', lambda: C.IR_GINI_DECOTE / C.IR_RECETTE_DECOTE, 0.0004),
    ('GINI_TVA_PAR_MD',
     lambda: C.TVA_GINI_PAR_2PTS / C.recette_tva_taux(0.22, C.PIB_BASE_2025_MD_EUR, C.CHOMAGE_BASE),
     0.00018),
    ('COMPET_TVA_PAR_MD',
     lambda: C.TVA_COMPET_PAR_2PTS / C.recette_tva_taux(0.22, C.PIB_BASE_2025_MD_EUR, C.CHOMAGE_BASE),
     -0.000018),
    ('GINI_TVA_ENERGIE_PAR_MD',
     lambda: C.TVA_ENERGIE_GINI_PAR_TAUX / (C.TVA_ENERGIE_CONSO_ELECTRICITE_MD + C.TVA_ENERGIE_CONSO_GAZ_MD),
     0.00042),
    ('COMPET_IS_PAR_MD', lambda: -C.IS_COMPET_PAR_MD, -0.015),
    ('COMPET_IMPOTS_PRODUCTION_PAR_MD', lambda: -C.IMPOTS_PRODUCTION_COMPET_PAR_MD, -0.020),
    ('COMPET_IS_EXCEPTIONNEL_PAR_MD', lambda: -C.IS_EXCEPTIONNEL_COMPET_PAR_MD, -0.003),
]


@pytest.mark.parametrize('nom, formule, ordre', DERIVEES, ids=[d[0] for d in DERIVEES])
def test_derivation_recalculee_et_ordre_de_grandeur(nom, formule, ordre):
    valeur = getattr(C, nom)
    assert valeur == formule(), nom
    # Ordre de grandeur annoncé par le contrat (§ 1.3), à 10 % près.
    assert valeur == pytest.approx(ordre, rel=0.10), (nom, valeur, ordre)


def test_derivees_ecrites_comme_expressions_des_noms():
    """« Jamais un nombre recopié » : chaque dérivée est une expression qui cite
    au moins un nom de constante, pas un littéral."""
    source = CONSTANTS_PY.read_text(encoding='utf-8')
    for nom, _, _ in DERIVEES + [('GINI_PENSIONS_PAR_MD', None, None),
                                 ('HORIZON_MANDAT_ANNEES', None, None),
                                 ('EVITEMENT_PLANCHER_DEFAUT', None, None),
                                 ('COTIS_SAL_POINTS_SUPPRESSION', None, None)]:
        m = re.search(rf'^{nom} = (.+)$', source, flags=re.MULTILINE)
        assert m, f"{nom} : définition introuvable en tête de ligne"
        expression = m.group(1).split('#')[0]
        assert re.search(r'[A-Z][A-Z0-9_]{3,}', expression), (nom, expression)


# ---------------------------------------------------------------------------
# 4. Signes (G11 sur les constantes) : +1 Md€ du paramètre du levier
# ---------------------------------------------------------------------------

NEGATIVES = [  # hausse de recette patrimoine/capital, hausse de prestation, impôt d'entreprise
    'GINI_PATRIMOINE_PAR_MD', 'COMPET_PATRIMOINE_PAR_MD',
    'GINI_ISF_EFFECTIF_PAR_MD', 'COMPET_ISF_EFFECTIF_PAR_MD',
    'GINI_SOLIDARITE_PAR_MD', 'GINI_PENSIONS_PAR_MD',
    'COMPET_IS_PAR_MD', 'COMPET_IMPOTS_PRODUCTION_PAR_MD', 'COMPET_IS_EXCEPTIONNEL_PAR_MD',
    'COMPET_TVA_PAR_MD',
]
POSITIVES = [  # taxe indirecte en plus, impôt des classes moyennes en plus
    'GINI_TVA_PAR_MD', 'GINI_TVA_ENERGIE_PAR_MD', 'GINI_IR_DECOTE_PAR_MD',
]


@pytest.mark.parametrize('nom', NEGATIVES)
def test_signe_negatif(nom):
    assert getattr(C, nom) < 0


@pytest.mark.parametrize('nom', POSITIVES)
def test_signe_positif(nom):
    assert getattr(C, nom) > 0


def test_solidarite_plus_forte_que_pensions_par_md():
    """Ordre énoncé par les règles du moteur (depenses.py) : population plus pauvre."""
    assert abs(C.GINI_SOLIDARITE_PAR_MD) > abs(C.GINI_PENSIONS_PAR_MD)


# ---------------------------------------------------------------------------
# 5. Données sourcées et bornes dérivées (§ 7.2-2)
# ---------------------------------------------------------------------------

def test_donnees_sourcees():
    assert C.R_REF_PLANCHER == 20.0
    # Décision du mainteneur (11/11/2026) : milieu de la fourchette publiée
    # 15-55 % ; aucun chiffre non publié (DG Trésor) dans le moteur.
    assert C.EVITEMENT_PLANCHER_FOURCHETTE_PCT == (15, 55)
    assert C.EVITEMENT_PLANCHER_DEFAUT == 0.35
    assert not hasattr(C, 'PLANCHER_RENDEMENT_TRESOR_MILIEU')
    assert C.A_CAPITAL_IR == pytest.approx(56.25, abs=1e-9)
    assert C.A_CAPITAL_PS == 191.0
    assert C.A_TSN == pytest.approx(0.902 / 0.03, abs=1e-12)
    assert C.V_REF_TTF == pytest.approx(722.0, abs=1e-9)
    assert C.DMTG_2025_MD == 21.2
    assert C.PSR_UE_2026_MD == 28.44
    assert C.APD_MISSION_2026_MD == 3.569
    assert C.COTIS_SAL_MASSE_2025_MD == 138.217
    assert C.COTIS_SAL_POINTS_SUPPRESSION == C.COTIS_SAL_MASSE_2025_MD / C.COUT_PAR_POINT_COTIS_SAL
    # Taux moyen réel des cotisations salariales (décision du 12/11/2026).
    assert C.COTIS_SAL_POINTS_SUPPRESSION == pytest.approx(11.9444, abs=1e-4)
    assert (C.ANNEE_SOURCE_PLANCHER, C.ANNEE_SOURCE_CAPITAL, C.ANNEE_SOURCE_TSN,
            C.ANNEE_SOURCE_TTF) == (2025, 2025, 2025, 2026)
    assert C.BENEFICES_RECUPERES_MAX == pytest.approx(12.6, abs=1e-9)


def test_borne_basse_des_transferts_vers_l_etranger_derivee_de_ses_sources():
    """Borne sourcée de ``transferts_etranger`` : −(PSR-UE + mission APD), loi de finances initiale pour 2026."""
    assert -(C.PSR_UE_2026_MD + C.APD_MISSION_2026_MD) == pytest.approx(-32.009, abs=1e-9)


# ---------------------------------------------------------------------------
# 6. Blocs balisés par chantier (§ 7.1) : un chantier n'écrit que dans le sien
# ---------------------------------------------------------------------------

BALISES = ['SOCLE', 'W1', 'W2', 'W3', 'W4', 'W6']


def test_blocs_balises_dans_l_ordre():
    """Balises présentes, uniques et dans l'ordre SOCLE, W1…W6, FIN.

    La vacuité des blocs de chantier était l'état du COMMIT socle (§ 7.2-2,
    « blocs balisés vides pour W1, W2, W3, W4, W6 ») ; elle ne peut pas survivre
    au § 7.1, qui fait écrire à chaque chantier ses constantes dans son bloc
    (W6 : les lignes de ``1e1f714``, verrouillées par
    ``test_effet_offre_echelle_v0612.py::test_w6_5_constantes_dans_le_bloc_w6_de_constants_py``).
    Le contenu de chaque bloc est vérifié par les tests de son chantier."""
    source = CONSTANTS_PY.read_text(encoding='utf-8')
    positions = []
    for b in BALISES:
        motif = f'# === RELEASE E — {b} ==='
        assert source.count(motif) == 1, f"balise {motif!r} absente ou dupliquée"
        positions.append(source.index(motif))
    assert positions == sorted(positions), "balises hors de l'ordre SOCLE, W1…W6"
    assert source.count('# === FIN RELEASE E ===') == 1, "balise de fin absente ou dupliquée"
    assert positions[-1] < source.index('# === FIN RELEASE E ==='), "balise de fin avant le bloc W6"


# ---------------------------------------------------------------------------
# 7. Canaux communs posés par le socle (§ 7.2-4 et 7.2-5) — inertes tant
#    qu'aucun levier de la release ne les emprunte
# ---------------------------------------------------------------------------

ECO_STATE = {'output_gap': -0.003, 'debt_ratio': 1.16, 'unemployment_gap': 0.003,
             'interest_rate': 0.031}


def test_prestations_menages_est_un_transfert():
    """§ 1.2-2 : multiplicateur des transferts dans les deux sens et profil de
    décroissance des transferts."""
    assert 'prestations_menages' in BudgetSimulatorV45.TRANSFER_MEASURES
    assert (BudgetSimulatorV45._get_decay_profile('prestations_menages')
            == BudgetSimulatorV45.DECAY_PROFILE_TRANSFERS)
    # Les transferts existants n'ont pas bougé.
    assert {'chomage_alloc', 'retraites', 'asu', 'smic', 'prestations_indexation',
            'abattement_retraites'} < BudgetSimulatorV45.TRANSFER_MEASURES


def test_mesures_hors_demande_interieure():
    """§ 1.2-3 : contrepartie directe non résidente → multiplicateur intérieur nul."""
    assert BudgetSimulatorV45.MESURES_HORS_DEMANDE_INTERIEURE == frozenset({'transferts_etranger'})


def _impulsions_apres(impacts, monkeypatch=None, vider_garde=False):
    sim = BudgetSimulatorV45(periods=1)
    sim._reset_state()
    if vider_garde:
        monkeypatch.setattr(BudgetSimulatorV45, 'MESURES_HORS_DEMANDE_INTERIEURE', frozenset())
    sim._last_impacts = impacts
    sim._stocker_impulsions(2027, dict(ECO_STATE))
    return {cle[1] for cle in sim._fiscal_impulses}, sim


def test_aucune_impulsion_stockee_pour_un_flux_vers_l_etranger(monkeypatch):
    impacts = {'transferts_etranger': {'depenses': -10.0, 'recettes': 0.0},
               'defense': {'depenses': 10.0, 'recettes': 0.0}}
    leviers, _ = _impulsions_apres(impacts)
    assert leviers == {'defense'}
    # Par MUTATION : sans la garde, le flux vers l'étranger serait multiplié.
    leviers_sans_garde, _ = _impulsions_apres(impacts, monkeypatch, vider_garde=True)
    assert leviers_sans_garde == {'defense', 'transferts_etranger'}


def test_indice_pib_source_annee_2025_est_le_pib_de_base():
    sim = BudgetSimulatorV45(periods=1)
    assert sim._indice_pib_source(2025, C.PIB_BASE_2025_MD_EUR) == 1.0
    assert sim._indice_pib_source(2025, 3250.0) == 3250.0 / C.PIB_BASE_2025_MD_EUR


def test_indice_pib_source_annee_non_enregistree_leve():
    sim = BudgetSimulatorV45(periods=1)
    sim._reset_state()
    with pytest.raises(RuntimeError, match='2026'):
        sim._indice_pib_source(2026, 3100.0)


def _gdp_recus_par_apply_measures(monkeypatch, **kwargs):
    recus = {}
    original = BudgetSimulatorV45.apply_measures

    def espion(self, year, spending, revenues, gdp, inflation, unemployment):
        recus[year] = gdp
        return original(self, year, spending, revenues, gdp, inflation, unemployment)

    monkeypatch.setattr(BudgetSimulatorV45, 'apply_measures', espion)
    sim = BudgetSimulatorV45(periods=10, **kwargs)
    sim.simulate()
    return sim, recus


@pytest.mark.parametrize('annee_debut', [None, 2028])
def test_pib_nominal_enregistre_chaque_annee_et_lu_par_l_indice(monkeypatch, annee_debut):
    sim, recus = _gdp_recus_par_apply_measures(monkeypatch, annee_debut=annee_debut)
    assert sim._pib_nominal_par_annee == recus
    assert sorted(recus) == list(range(2026, 2036))
    pib_2026 = recus[2026]
    assert sim._indice_pib_source(2026, pib_2026) == 1.0
    assert sim._indice_pib_source(2026, 3400.0) == 3400.0 / pib_2026


def test_pib_nominal_remis_a_zero_entre_deux_simulations(monkeypatch):
    sim, _ = _gdp_recus_par_apply_measures(monkeypatch)
    assert sim._pib_nominal_par_annee
    sim._reset_state()
    assert sim._pib_nominal_par_annee == {}
    # Une seconde simulation ré-enregistre exactement les mêmes valeurs.
    premier = dict(_gdp_recus_par_apply_measures(monkeypatch)[0]._pib_nominal_par_annee)
    sim.simulate()
    assert sim._pib_nominal_par_annee == premier


# ---------------------------------------------------------------------------
# 8. Registre des onze leviers, valeurs neutres, squelettes (§ 1.1, § 7.2-1/6/7/9)
# ---------------------------------------------------------------------------
import json  # noqa: E402
import os  # noqa: E402
import sys  # noqa: E402
from unittest.mock import patch  # noqa: E402

from budget_simulator.constants import HANDLER_FAILED_KEY  # noqa: E402

POLICY_JSON = RACINE / 'policy_measures.json'

# Contrat § 1.1 : (valeur neutre ou None pour un mode exclusif « absent », min, max).
DOMAINES_E = {
    # Bornes hautes de credits_etat et de transferts_etranger : objectifs publiés en part du PIB ou
    # du RNB (décision du mainteneur du 12/11/2026, v0.8.1 ; 20 et 10 au contrat, non sourcées).
    'depenses_publiques': {'credits_etat': (0, -60, C.CREDITS_ETAT_MAX_MD), 'ondam': (0, -10, 10),
                           'transferts_capital': (0, -10, 10)},
    'prestations_menages': {'solidarite': (0, -35, 30), 'pensions': (0, -20, 10)},
    'transferts_etranger': {'montant': (0, -(C.PSR_UE_2026_MD + C.APD_MISSION_2026_MD),
                                        C.TRANSFERTS_ETRANGER_MAX_MD)},
    # Borne haute : +25 (décision du mainteneur du 12/11/2026 ; +20 au contrat, non sourcée).
    'droits_succession': {'variation': (0, -C.DMTG_2025_MD, C.DMTG_VARIATION_MAX_MD)},
    'impot_plancher_patrimoine': {'taux': (0, 0, 0.03),
                                  'evitement': (C.EVITEMENT_PLANCHER_DEFAUT, 0, 0.95)},
    'fiscalite_capital': {'taux_ir_forfaitaire': (0.128, 0, 0.45),
                          'prelevements_sociaux_capital': (0.186, 0, 0.30),
                          'elasticite': (0.9, 0, 2), 'rendement_md': (None, -15, 15)},
    'multinationales': {'benefices_recuperes': (0, 0, C.BENEFICES_RECUPERES_MAX),
                        'taux_tsn': (0.03, 0, 0.10), 'erosion_tsn': (1.0, 0, 10),
                        'rendement_tsn_md': (None, -1, 10)},
    'operations_financieres': {'taux_ttf': (0.004, 0, 0.01), 'elasticite_volume': (0.05, 0, 0.25),
                               'rendement_ttf_md': (None, -3, 10), 'rachats_actions': (0, -0.2, 15),
                               'crypto_actifs': (0, 0, 5)},
    'fiscalite_indirecte': {'tva_ciblee': (0, -15, 15), 'accises_energie': (0, -15, 15)},
    'impot_revenu_cible': {'montant': (0, -15, 5)},
    'recette_exceptionnelle': {'montant': (0, 0, 60)},
}
FORMULES_E = {
    'depenses_publiques': "p.get('credits_etat', 0) + p.get('ondam', 0) + p.get('transferts_capital', 0)",
    'transferts_etranger': "p.get('montant', 0)",
}
# Levier → (module du mixin, chantier qui écrira le corps).
SQUELETTES_E = {
    'prestations_menages': ('transferts_menages', 'W2'),
    'droits_succession': ('recettes_montants', 'W3'),
    'fiscalite_indirecte': ('recettes_montants', 'W3'),
    'impot_revenu_cible': ('recettes_montants', 'W3'),
    'recette_exceptionnelle': ('recettes_montants', 'W3'),
    'impot_plancher_patrimoine': ('recettes_taux', 'W4'),
    'fiscalite_capital': ('recettes_taux', 'W4'),
    'multinationales': ('recettes_taux', 'W4'),
    'operations_financieres': ('recettes_taux', 'W4'),
}
MODES_EXCLUSIFS_E = {
    'fiscalite_capital': {'rendement_md': {'taux_ir_forfaitaire', 'prelevements_sociaux_capital',
                                           'elasticite'}},
    'multinationales': {'rendement_tsn_md': {'taux_tsn', 'erosion_tsn'}},
    'operations_financieres': {'rendement_ttf_md': {'taux_ttf', 'elasticite_volume'}},
}


def _entrees_json():
    mesures = json.loads(POLICY_JSON.read_text(encoding='utf-8'))['mesures']
    return {m['id']: m for m in mesures}


def test_onze_leviers_et_vingt_six_parametres():
    assert len(DOMAINES_E) == 11
    assert sum(len(p) for p in DOMAINES_E.values()) == 26
    assert tuple(C.LEVIERS_RELEASE_E) == tuple(DOMAINES_E)
    assert set(SQUELETTES_E) | set(FORMULES_E) == set(DOMAINES_E)


@pytest.mark.parametrize('levier', list(DOMAINES_E))
def test_entree_policy_measures_conforme_au_contrat(levier):
    entree = _entrees_json().get(levier)
    assert entree, f"{levier} absent de policy_measures.json"
    for champ in ('id', 'categorie', 'nom', 'description', 'type', 'cible', 'parametres'):
        assert entree.get(champ) not in (None, ''), (levier, champ)
    assert entree['type'] == ('formule' if levier in FORMULES_E else 'fonction')
    if levier in FORMULES_E:
        assert entree['formule'] == FORMULES_E[levier]
        assert entree['cible'] == 'depenses'
    assert set(entree['parametres']) == set(DOMAINES_E[levier])
    for param, (neutre, bas, haut) in DOMAINES_E[levier].items():
        spec = entree['parametres'][param]
        if neutre is None:
            assert 'valeur_defaut' not in spec, f"{levier}.{param} : mode exclusif sans défaut"
        else:
            assert spec['valeur_defaut'] == pytest.approx(neutre, abs=1e-12), (levier, param)
        assert spec['min'] == pytest.approx(bas, abs=1e-9), (levier, param, 'min')
        assert spec['max'] == pytest.approx(haut, abs=1e-9), (levier, param, 'max')
        assert spec['min'] < spec['max'] and spec['step'] > 0
        assert spec.get('label') and spec.get('tooltip'), (levier, param)


def test_bornes_sourcees_egales_aux_expressions():
    e = _entrees_json()
    assert e['transferts_etranger']['parametres']['montant']['min'] == pytest.approx(
        -(C.PSR_UE_2026_MD + C.APD_MISSION_2026_MD), abs=1e-9)
    assert e['droits_succession']['parametres']['variation']['min'] == pytest.approx(
        -C.DMTG_2025_MD, abs=1e-9)
    assert e['multinationales']['parametres']['benefices_recuperes']['max'] == pytest.approx(
        C.BENEFICES_RECUPERES_MAX, abs=1e-9)
    assert e['impot_plancher_patrimoine']['parametres']['evitement']['valeur_defaut'] == pytest.approx(
        C.EVITEMENT_PLANCHER_DEFAUT, abs=1e-12)


# Garde de neutralité des textes publics (revue adverse de la release E : le
# dépôt public n'écrit aucun nom de parti, de candidat ni d'identifiant de
# scénario politique, pas même dans une liste d'exclusion). Les noms interdits
# (partis, candidats, organismes politiques, identifiants des scénarios
# publiés : identités tenues par le dépôt parent, complétées des organismes
# cités par la revue) sont retenus par leur EMPREINTE SHA-256. Un texte est
# refusé si l'un de ses groupes de 1 à 3 mots consécutifs (``\w+``, sensible à
# la casse comme l'ancienne expression régulière) a l'une de ces empreintes.
_EMPREINTES_NOMS_POLITIQUES = frozenset({
    '096d92ee9c796a7c2419a6ff814b2c0322f13c2eae282894002f99e433ec5641',
    '0ca0029153b61e4103a963db16bdb8aa94dbbf87b3151b0773b0a478f6d4151a',
    '1acd0d1a946ed26236e4ba0eb2bdb0388e285684fb98a65cbbace0b9ecf57f43',
    '234d942822a5b7c00af48a1dc7424d510ebfe9d59a551d913ec991b8efaa3053',
    '240a46f7e2404d24ec78c2d891ea52d6bfe5113b3d620f06778b7652ed9a848d',
    '24e11d4b5993b45f632116bbef057827360efdfc73c87e6789f039e92b98ffc6',
    '290bc371bd06e3376a12a4204b41e2414ae6fc5f5b386854cd50f0624bdc8262',
    '2dc4cff18d1743f71be365d420a4058721311f315ac28b9888162bbea8bf6ca4',
    '2df531f7759ac1c47947b7a5f0bb1c4e383ea9ddd6f7aa404fcd474d6f7ec2c7',
    '328a728b1e753b284346d6880d8dd60748cc32948ef56a7cfc45a469ab81ee55',
    '3e53a8eb7e81ccf65e74c80c9d67f527cf8b785c1bf8d87c3b01032a77db45f5',
    '4bd6a962152d04668ff07654bc32fc3ce79cf253237a6c4593f3d76bfea8bd2b',
    '617b33f10cf5e0442870ceb54620c818a27f31cbcba0fbb8bc3b11b896bd6885',
    '6614ef67c4274045a8537f68719083de2e787a81e793b3a6555862d74172e407',
    '661a6b42453fbdaeaca5f2e6c75d2b6d16401cc553da31ee272d47a1d584cd3b',
    '6a62b6625cbee9618f0276d4881d66666cb64cfc0256ac22522a42941fc9f8f4',
    '6be5d182443dce067c7a1d30f7a0065f61a95948638f0997ddf7ab8f908dfff6',
    '6e48e6795904424c1f313e8091906f356ddbaa21d588ce0e9390bc50bfc78dcd',
    '78246295cb7f713e58adc7ecbbd1f158c3e86d95e76a5d9fd67866e2bb8f1665',
    '7a706d296621ea99cf36e8e9ecf4530a8e82c205c471a5cfc450c8771f5171ae',
    '7ae6ddf44a94992da7135c1898170d6285e1f8e4145bc79c51781b44305d2a84',
    '7d9130c5d40e05e876783ef73bd258910cd1bf8aba75f55bc9b45dac6a3f4588',
    '821381b263b9c3731b15fcab3ccf25a0f17568cd84f74fba6377e43eb1e110c7',
    '82c9e9704ac05a0af89b7fdb01ccd0a14dae25db29c0b164f4a1fba4aea551b4',
    '83421cb4d3faad332bce7c5c29c861ec91102bcfaebf25c1cf2e2125b884d506',
    '848986641ffddd20b97bd48e64c77785ab7aec5dcba310ba939bbb521bedc6dc',
    '8a6cccbe4f895254821171b1eddf152a1a3624b707509c7ab62b89ad1de56c78',
    '8e61705afabf2bd49069b38e19f4725fda1eab3159549bc543b6b5f5be249359',
    '9266f7b357b420ed70c72e1251c7ac13d3f5d6411631643caac13e3923edb976',
    '9f181e96c5b849bdd2d420c82d7d44cb45ab67c2475e3b10c4cea9ba29e4d507',
    'a423326b0cee1a68fe1bcb9dd8446bca60b96c6ea1d552c857257170f125c2ca',
    'a73223a7f978ee809e8d9e0ee2b081404b1505ab8dc6de63a60faff0b301b221',
    'a923f52d9d33ef33f28fe4f1c863e4774bf20bd718cb52ec4ecaf9859a85dc53',
    'ab2b27be10df68eb1d88d0fc7abcc48aac8aa085dcf9c4f2b3b038be754ed91e',
    'b41b5959337d1a2b6345a8f1425bf1c26dcd36be0fec3e90dfa27781c7912c26',
    'b95d39529f30e6546b1d144b163049e085d4653c208d063af151805cb73fcb7d',
    'c2067e8aac754ab971d08ea0611ef37c05b8c9712eb9f9b52504c133e44af384',
    'c27c8b207b60f0c399646ad1082e75b5450ada5726e8847b7c1f46114f3ef486',
    'c373a091f9be16d44b7ba11cd50fb7a031efb47994515dc2f6af121248e5b41d',
    'cd7533b533cc8f16a32bc07b0dc64c5bea4720478c98f27af6163c5f5b025908',
    'cf25077a1a31594fcff8ad8b43dd226e28d59c7ddef9dcdb0bbe950981883962',
    'd52fdbd41442c804085d7112a9d612166dc10a62ff9e06b2d2fc6c06402a49f1',
    'd7ae380a7bfbf027c2239a106b02741d5d33b81217aef0e75b9bfcfe9578e6cc',
    'dd1cd3d60a28bc5624a4a414028d2b67e6c6a62620502e573efb5070701935cd',
    'dfd0203ed26303bbb0981c554a49952fe8c0f8a9cc2b9fea879f230c7eb097cc',
    'e2e405a64d7181c50ce382c825385ed59a5138b939291bdc6107bac5b4a7eb40',
    'e4c05ce6033bfa72c0d8018401648c974774e5d8a188f33be2d8c9468f8eefdf',
    'e8c2f6bdc6c99f3b6eefa82a3929eaba0507939779fb1c87ec65962dac44b663',
    'f2830288c83e4c79ed92320f12e906922987652f6970cb60f2ceb160270e0113',
})


def _groupes_de_mots(texte, n_max=3):
    mots = re.findall(r'\w+', texte)
    for n in range(1, n_max + 1):
        for i in range(len(mots) - n + 1):
            yield ' '.join(mots[i:i + n])


def _nom_politique(texte):
    """Premier groupe de mots du texte dont l'empreinte est interdite, ou None."""
    for groupe in _groupes_de_mots(texte):
        if hashlib.sha256(groupe.encode('utf-8')).hexdigest() in _EMPREINTES_NOMS_POLITIQUES:
            return groupe
    return None


def test_garde_de_neutralite_empreintes():
    """La liste d'exclusion n'est pas vide (49 noms) ; des textes neutres
    proches ne sont pas refusés (pas de faux positif sur les mots du domaine)."""
    assert len(_EMPREINTES_NOMS_POLITIQUES) == 49
    for neutre in ("Taxe sur les transactions financières, rendement en Md€",
                   "renaissance de l'investissement public, horizons de prévision"):
        assert _nom_politique(neutre) is None, neutre


@pytest.mark.parametrize('levier', list(DOMAINES_E))
def test_textes_publics_neutres(levier):
    """Aucun nom de parti, de candidat ni de scénario dans les textes du levier ;
    tout montant en Md€ porte la mention commune « identique chaque année »."""
    entree = _entrees_json()[levier]
    textes = [entree['nom'], entree['description']]
    for param, spec in entree['parametres'].items():
        textes += [spec['label'], spec['tooltip']]
        if 'Md€' in spec['label'] and levier != 'recette_exceptionnelle':
            assert 'identique chaque année' in spec['tooltip'], (levier, param)
    for t in textes:
        assert _nom_politique(t) is None, (levier, t)


def test_neutres_release_e_derives_du_registre():
    e = _entrees_json()
    attendu = {l: {p: spec['valeur_defaut'] for p, spec in e[l]['parametres'].items()
                   if 'valeur_defaut' in spec}
               for l in DOMAINES_E}
    assert C.NEUTRES_RELEASE_E == attendu
    for l, params in DOMAINES_E.items():
        assert set(C.NEUTRES_RELEASE_E[l]) == {p for p, v in params.items() if v[0] is not None}


def test_noms_admis_et_modes_exclusifs_generes():
    from budget_simulator.engine._noms_parametres import MODES_EXCLUSIFS, NOMS_PARAMETRES_ADMIS
    for levier, params in DOMAINES_E.items():
        assert NOMS_PARAMETRES_ADMIS.get(levier) == frozenset(params), levier
    for levier, modes in MODES_EXCLUSIFS_E.items():
        assert {k: set(v) for k, v in MODES_EXCLUSIFS[levier].items()} == modes, levier
    for levier in set(DOMAINES_E) - set(MODES_EXCLUSIFS_E):
        assert levier not in MODES_EXCLUSIFS, levier


def test_quarante_deux_handlers_dont_neuf_squelettes():
    sim = BudgetSimulatorV45(periods=1)
    assert len(sim.measure_handlers) == 42
    for levier, (module, _) in SQUELETTES_E.items():
        fn = sim.measure_handlers[levier]
        assert fn.__name__ == f'_apply_{levier}'
        assert fn.__func__.__module__ == f'budget_simulator.handlers.{module}', levier
    for levier in FORMULES_E:
        assert levier not in sim.measure_handlers
    noms_bases = [b.__name__ for b in BudgetSimulatorV45.__bases__]
    for mixin in ('PrestationsMenagesMixin', 'RecettesMontantsMixin', 'RecettesTauxMixin'):
        assert noms_bases.index(mixin) > noms_bases.index('EfficienceMixin')
        assert noms_bases.index(mixin) < noms_bases.index('InflationMixin')


# --- G1 : neutralité au bit, deux modes, deux portes ------------------------

def _canon(x):
    if isinstance(x, dict):
        return {str(k): _canon(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_canon(v) for v in x]
    if isinstance(x, float):
        return x.hex()
    return x


sys.path.insert(0, str(RACINE / 'tests' / 'snapshots'))
from run_scenarios_full import SCENARIOS as _SCENARIOS_PUBLIES  # noqa: E402
from cadre_harness import bases_g1, rapport_g1  # noqa: E402

_DROIT = json.loads((RACINE / 'budget_simulator' / 'data' / 'droit_en_vigueur.json')
                    .read_text(encoding='utf-8'))['mesures']
# Bases toujours disponibles (dépôt public seul) + les 10 scénarios publiés
# quand scenarios.json est présent (dépôt parent, ou BUDGETLAB_SCENARIOS_JSON).
BASES_G1 = {'statu_quo': {}, 'droit_en_vigueur': _DROIT, **_SCENARIOS_PUBLIES}
_CACHE_G1 = {}


def _simuler_g1(mesures, annee_debut, strict):
    cle = (json.dumps(mesures, sort_keys=True), annee_debut, strict)
    if cle not in _CACHE_G1:
        with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1' if strict else ''}):
            df, detail, rapport = BudgetSimulatorV45(
                periods=10, mesures=mesures, annee_debut=annee_debut).simulate()
        _CACHE_G1[cle] = (df, detail, rapport)
    return _CACHE_G1[cle]


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
@pytest.mark.parametrize('levier', list(DOMAINES_E))
def test_g1_neutralite_au_bit(levier, annee_debut, strict):
    if len(BASES_G1) < 12:
        assert len(BASES_G1) == 2  # dépôt public seul : statu quo et droit en vigueur
    neutre = {levier: dict(C.NEUTRES_RELEASE_E[levier])}
    # Release de paramètres P : les bases qui ENCODENT le levier en sont exclues
    # (y poser le neutre retirerait leur mesure) ; rapport comparé hors la seule
    # différence d'un levier à taux inscrit au droit (cadre_harness.rapport_g1).
    for nom, base in bases_g1(BASES_G1, levier, annee_debut).items():
        ref_df, ref_detail, ref_rapport = _simuler_g1(base, annee_debut, strict)
        df, detail, rapport = _simuler_g1({**base, **neutre}, annee_debut, strict)
        assert df.equals(ref_df), (nom, levier, 'trajectoire')
        assert detail.equals(ref_detail), (nom, levier, 'détail')
        assert _canon(rapport['measure_impacts_by_year']) == _canon(ref_rapport['measure_impacts_by_year']), (nom, levier)
        assert _canon(rapport_g1(rapport, levier)) == _canon(ref_rapport), (nom, levier, 'rapport')


# --- Squelettes : toute valeur non neutre échoue BRUYAMMENT ------------------

_NON_NEUTRES_TOUS = [
    ('prestations_menages', {'solidarite': 5.0}),
    ('prestations_menages', {'pensions': -2.0}),
    ('droits_succession', {'variation': 5.0}),
    ('fiscalite_indirecte', {'tva_ciblee': 2.0}),
    ('fiscalite_indirecte', {'accises_energie': -1.0}),
    ('impot_revenu_cible', {'montant': -3.0}),
    ('recette_exceptionnelle', {'montant': 10.0}),
    ('impot_plancher_patrimoine', {'taux': 0.02}),
    ('impot_plancher_patrimoine', {'evitement': 0.5}),
    ('fiscalite_capital', {'taux_ir_forfaitaire': 0.15}),
    ('fiscalite_capital', {'elasticite': 0.5}),
    ('fiscalite_capital', {'rendement_md': 3.0}),
    ('multinationales', {'benefices_recuperes': 2.0}),
    ('multinationales', {'taux_tsn': 0.05}),
    ('multinationales', {'rendement_tsn_md': 1.0}),
    ('operations_financieres', {'taux_ttf': 0.005}),
    ('operations_financieres', {'rendement_ttf_md': 1.0}),
    ('operations_financieres', {'rachats_actions': 1.0}),
    ('operations_financieres', {'crypto_actifs': 0.5}),
]
# Liste COMPLÈTE des sondes, une version unique (les chantiers ne la retranchent
# pas) ; seule la source unique LEVIERS_NON_LIVRES décide lesquelles s'exécutent.
# Seuls les leviers ENCORE squelettes refusent une valeur non neutre : un
# chantier qui livre son corps retire son levier de ``LEVIERS_NON_LIVRES``, et
# la garde ``test_leviers_non_livres_exactement_les_squelettes_qui_levent``
# exige alors qu'il n'en refuse plus aucune. La liste se filtre sur la source
# unique au lieu de nommer les squelettes en dur (vide après la release : les
# deux tests ci-dessous n'ont alors plus de cas).
NON_NEUTRES = [(levier, params) for levier, params in _NON_NEUTRES_TOUS
               if levier in C.LEVIERS_NON_LIVRES]


def _mode_de_sonde(levier):
    """Mode de la simulation qui sonde un squelette : historique, sauf pour la
    recette exceptionnelle, refusée en mode historique depuis le chantier W1
    (contrat § 2.1 : une seule année, calendrier obligatoire) et sondée en mode
    cadre (2028, son année par défaut)."""
    return 2028 if levier == 'recette_exceptionnelle' else None


@pytest.mark.parametrize('levier, params', NON_NEUTRES,
                         ids=[f'{l}-{next(iter(p))}' for l, p in NON_NEUTRES])
def test_valeur_non_neutre_tolerant_echec_signale_effet_nul(levier, params):
    ref_df, _, _ = _simuler_g1({}, _mode_de_sonde(levier), False)
    df, _, rapport = _simuler_g1({levier: params}, _mode_de_sonde(levier), False)
    assert rapport['valid'] is False
    echecs = [annee[levier] for annee in rapport['measure_impacts_by_year'] if levier in annee]
    assert echecs and all(e.get(HANDLER_FAILED_KEY) for e in echecs), levier
    assert all('non encore implémenté' in e['erreur'] and levier in e['erreur'] for e in echecs)
    assert SQUELETTES_E[levier][1] in echecs[0]['erreur']
    assert any(levier in w and 'échec' in w for w in rapport['warnings']), rapport['warnings']
    # Effet compté nul, jamais un chiffre : la trajectoire est celle du statu quo.
    assert df.equals(ref_df)


@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
@pytest.mark.parametrize('levier, params', NON_NEUTRES,
                         ids=[f'{l}-{next(iter(p))}' for l, p in NON_NEUTRES])
def test_valeur_non_neutre_strict_exceptiongroup(levier, params, annee_debut):
    if levier == 'recette_exceptionnelle' and annee_debut is None:
        # Chantier W1 (contrat § 2.1) : refusée en mode historique avant tout
        # handler, faute d'entrée (422), jamais évaluée.
        from budget_simulator.engine.cadre import ProfilInvalide
        with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1'}):
            with pytest.raises(ProfilInvalide, match=levier):
                BudgetSimulatorV45(periods=10, mesures={levier: params}).simulate()
        return
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1'}):
        with pytest.raises(ExceptionGroup) as info:
            BudgetSimulatorV45(periods=10, mesures={levier: params},
                               annee_debut=annee_debut).simulate()
    feuilles = info.value.exceptions
    assert any(isinstance(e, NotImplementedError) and 'non encore implémenté' in str(e)
               and levier in str(e) for e in feuilles), feuilles


def test_formules_du_socle_effectives():
    """Les deux leviers à formule sont FINAUX dès le socle (§ 1.2-1 et 1.2-3) :
    l'effet sur les dépenses est la somme exacte des paramètres."""
    def annees_de_programme(r):
        # L'année de base (2025) est publiée sans mesure.
        return [a for a in r['measure_impacts_by_year'] if a['Année'] >= 2026]

    _, _, r = _simuler_g1({'depenses_publiques': {'credits_etat': 3.0, 'ondam': 1.0,
                                                  'transferts_capital': 0.5}}, None, False)
    annees = annees_de_programme(r)
    assert len(annees) == 10
    assert all(a['depenses_publiques']['depenses'] == 4.5 for a in annees)
    assert r['valid'] is True
    _, _, r = _simuler_g1({'transferts_etranger': {'montant': -5.0}}, None, False)
    assert all(a['transferts_etranger']['depenses'] == -5.0 for a in annees_de_programme(r))
    assert r['valid'] is True


# ---------------------------------------------------------------------------
# 9. Leviers non livrés (complément du contrat § 7.2, 11/11/2026)
# ---------------------------------------------------------------------------
# Les tests existants qui essaient chaque levier du registre à une valeur non
# neutre (mini-scénarios standalone, balayages de PARAM_DOMAINS) sautent les
# leviers de ``constants.LEVIERS_NON_LIVRES`` : leurs squelettes refusent toute
# valeur non neutre (jamais un levier muet). Deux gardes empêchent cette liste
# de mentir ou de survivre à la release.

def _sondes_non_neutres(levier):
    """Une valeur NON neutre par paramètre du levier, chacune seule : à mi-chemin
    du neutre et de la borne haute (de la borne basse si le neutre est la borne
    haute). Paramètre de mode exclusif (neutre = clé absente) : à mi-chemin de 0
    et de sa borne haute — toute présence est non neutre."""
    sondes = []
    for param, spec in _entrees_json()[levier]['parametres'].items():
        neutre, bas, haut = spec.get('valeur_defaut', 0), spec['min'], spec['max']
        x = neutre + (haut - neutre) / 2 if haut > neutre else neutre - (neutre - bas) / 2
        sondes.append({param: x})
    return sondes


def _refuse_comme_non_livre(levier, params):
    """Vrai si le moteur (tolérant, mode historique — mode cadre pour la recette
    exceptionnelle, ``_mode_de_sonde``) a refusé ``{levier: params}`` par
    l'erreur des squelettes (``_types.levier_non_livre``)."""
    _, _, rapport = _simuler_g1({levier: params}, _mode_de_sonde(levier), False)
    erreurs = [annee[levier].get('erreur', '') for annee in rapport['measure_impacts_by_year']
               if isinstance(annee.get(levier), dict)]
    return any('non encore implémenté' in e for e in erreurs)


def test_leviers_non_livres_exactement_les_squelettes_qui_levent():
    """Garde-fou de la liste : elle nomme EXACTEMENT les handlers squelettes.

    (a) source : les handlers qui appellent ``levier_non_livre`` sont ceux de la
    liste, ni plus ni moins (un chantier qui livre son corps retire son levier) ;
    (b) comportement : un levier listé refuse CHACUN de ses paramètres à une
    valeur non neutre (aucun paramètre muet) ; un levier de la release non listé
    n'en refuse aucun (un corps partiel ne quitte pas la liste)."""
    assert isinstance(C.LEVIERS_NON_LIVRES, frozenset)
    assert C.LEVIERS_NON_LIVRES <= set(C.LEVIERS_RELEASE_E)
    sim = BudgetSimulatorV45(periods=1)
    appelants = {levier for levier, fn in sim.measure_handlers.items()
                 if 'levier_non_livre(' in inspect.getsource(fn)}
    assert appelants == C.LEVIERS_NON_LIVRES
    for levier in C.LEVIERS_RELEASE_E:
        refus = {next(iter(s)): _refuse_comme_non_livre(levier, s)
                 for s in _sondes_non_neutres(levier)}
        if levier in C.LEVIERS_NON_LIVRES:
            assert all(refus.values()), (levier, 'paramètre muet', refus)
        else:
            assert not any(refus.values()), (levier, 'levier livré qui refuse encore', refus)


def test_leviers_non_livres_sans_mini_scenario():
    """Lecteur unique des mini-scénarios standalone : un levier non livré n'en a
    pas (tant qu'il est listé), tout autre handler en a un."""
    sys.path.insert(0, str(RACINE / 'tests' / 'snapshots'))
    from coverage_scenarios import build_standalone_scenarios
    handlers = set(BudgetSimulatorV45(periods=1).measure_handlers)
    assert set(build_standalone_scenarios()) == handlers - C.LEVIERS_NON_LIVRES


@pytest.mark.integration
@pytest.mark.skipif((os.environ.get('BUDGETLAB_RELEASE_E_PRET') or '').strip() != '1',
                    reason="garde d'intégration de la release E : ne s'exécute qu'avec "
                           "BUDGETLAB_RELEASE_E_PRET=1, posée avant tout tag")
def test_aucun_levier_non_livre_avant_le_tag():
    """La liste des leviers non livrés doit être VIDE avant tout tag.

    Pendant les chantiers W2 à W4, la liste est légitimement non vide : le
    test est donc ignoré tant que la variable d'environnement
    ``BUDGETLAB_RELEASE_E_PRET`` ne vaut pas ``1``. L'intégration de la release
    pose ``BUDGETLAB_RELEASE_E_PRET=1`` pour la suite complète (tolérant et
    strict) avant le tag : un levier encore squelette fait alors échouer la
    release, au lieu d'être publié au registre en refusant toute valeur."""
    assert not C.LEVIERS_NON_LIVRES, (
        f"leviers encore squelettes : {sorted(C.LEVIERS_NON_LIVRES)} — aucun tag "
        "de la release E tant qu'un chantier n'a pas livré son corps")


# ---------------------------------------------------------------------------
# 10. Bloc au neutre d'un levier absent du droit en vigueur (contrat § 2.1
#     « Neutres », règle et test W1-12 avancés au socle le 11/11/2026)
# ---------------------------------------------------------------------------

def _cadre_2028(mesures):
    return _simuler_g1(mesures, 2028, False)[2]['cadre']


_LEVIERS_ABSENTS_DU_DROIT = [l for l in DOMAINES_E if l not in _DROIT]
_LEVIERS_INSCRITS_AU_DROIT = [l for l in DOMAINES_E if l in _DROIT]


def test_leviers_inscrits_au_droit_release_p():
    """Release de paramètres P (contrat de la release E § 0.9) : seuls les
    leviers dont le neutre est du droit voté sont inscrits au droit en vigueur,
    à leurs taux votés (paramètres de comportement absents)."""
    assert set(_LEVIERS_INSCRITS_AU_DROIT) == {'fiscalite_capital', 'multinationales',
                                               'operations_financieres'}
    for levier in _LEVIERS_INSCRITS_AU_DROIT:
        neutres = C.NEUTRES_RELEASE_E[levier]
        assert _DROIT[levier] and all(neutres[p] == v for p, v in _DROIT[levier].items()), levier


@pytest.mark.parametrize('levier', _LEVIERS_ABSENTS_DU_DROIT)
def test_bloc_neutre_retire_du_programme_en_mode_cadre(levier):
    """Un bloc dont toutes les valeurs sont neutres (complet, partiel, vide ou à
    ``null``) d'un levier absent du droit en vigueur est lu comme un ``null`` :
    ni dans ``leviers_modifies`` ni dans ``mesures_effectives``."""
    reference = _cadre_2028({})
    neutres = dict(C.NEUTRES_RELEASE_E[levier])
    premier = next(iter(neutres))
    for bloc in (neutres, {premier: neutres[premier]}, {}, {premier: None}):
        cadre = _cadre_2028({levier: bloc})
        assert levier not in cadre['leviers_modifies'], (levier, bloc)
        assert levier not in cadre['mesures_effectives'], (levier, bloc)
        assert cadre['leviers_modifies'] == reference['leviers_modifies'], (levier, bloc)
        assert _canon(cadre['mesures_effectives']) == _canon(reference['mesures_effectives'])


@pytest.mark.parametrize('levier', _LEVIERS_INSCRITS_AU_DROIT)
def test_bloc_neutre_d_un_levier_inscrit_au_droit(levier):
    """Levier à taux INSCRIT au droit en vigueur (release P) : la règle du
    bloc neutre ne s'applique pas (contrat § 2.1 : levier absent du droit).
    Un bloc qui recopie les taux du droit n'est pas un levier modifié ; un bloc
    neutre COMPLET, qui porte aussi les paramètres de comportement à leur
    défaut, entre dans ``leviers_modifies`` (règle v0.7.2 « présent =
    imposé ») sans changer aucune sortie (G1, ``rapport_g1``). État constaté et
    documenté au CHANGELOG (v0.8.1), non corrigé dans une release de
    paramètres."""
    reference = _cadre_2028({})
    assert _cadre_2028({levier: dict(_DROIT[levier])})['leviers_modifies'] == reference['leviers_modifies']
    complet = dict(C.NEUTRES_RELEASE_E[levier])
    cadre = _cadre_2028({levier: complet})
    assert levier in cadre['leviers_modifies']
    assert cadre['mesures_effectives'][levier] == complet
    assert _simuler_g1({levier: complet}, 2028, False)[0].equals(_simuler_g1({}, 2028, False)[0])


def test_bloc_non_neutre_garde_au_programme_en_mode_cadre():
    """La règle ne retire qu'un bloc ENTIÈREMENT neutre : une seule valeur non
    neutre garde le bloc tel quel (levier livré du socle : la formule)."""
    bloc = {'credits_etat': 3.0, 'ondam': 0}
    cadre = _cadre_2028({'depenses_publiques': bloc})
    assert 'depenses_publiques' in cadre['leviers_modifies']
    assert cadre['mesures_effectives']['depenses_publiques'] == bloc


def test_bloc_neutre_hors_release_e_regle_v072_inchangee():
    """Portée minimale : le neutre n'est défini que pour les leviers de la
    release (``NEUTRES_RELEASE_E``). Un autre levier absent du droit, présent à
    ses valeurs par défaut, reste un levier modifié comme en v0.7.2."""
    defauts = {p: spec['valeur_defaut']
               for p, spec in _entrees_json()['rabot_uniforme']['parametres'].items()}
    cadre = _cadre_2028({'rabot_uniforme': dict(defauts)})
    assert 'rabot_uniforme' in cadre['leviers_modifies']
    assert cadre['mesures_effectives']['rabot_uniforme'] == defauts
