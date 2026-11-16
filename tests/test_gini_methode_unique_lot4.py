"""Lot 4 — méthode unique du Gini (K × montant) : paramètres, périmètre, bornes.

Règle (constants.py, § CANAUX GINI, « LOT 4 : MÉTHODE UNIQUE ») : pour tout
levier qui passe par le revenu disponible des ménages, ΔGini brut = K × Δmontant
(Md€), K = (C − G) / Y pour une prestation et −(C − G) / Y pour un prélèvement.
Ce fichier verrouille :

  (1) la GARDE DES CONSTANTES : toute constante du module dont le nom suit l'un
      des styles du dépôt (« …GINI…PAR_MD… », « …GINI…PAR_<n>MD » ramenée à
      un Md€) est classée (prélèvement ou prestation) et reste sous sa borne —
      (1 − G) / Y pour un prélèvement, (1 + G) / Y pour une prestation ; une
      constante nouvelle non classée fait rougir le test. Cette garde dépend
      des noms : la garde qui n'en dépend pas balaie tout le registre, levier
      par levier (tests/test_gini_borne_registre_lot4.py) ;
  (2) la RECETTE des coefficients sourcés, EXÉCUTÉE depuis les chiffres publiés
      de l'INSEE au classement FINAL (Revenus et patrimoine des ménages 2024,
      fiches 1.3 et 1.4 : composition du niveau de vie par dixième), avec la
      figure 2 de la fiche « Redistribution monétaire » (France, portrait
      social 2025, classement initial) en recoupement publié ; les plages des
      règles que la fiche ne couvre pas (pensions, abattement, capital, SMIC,
      décote), recalculées depuis les tableaux publiés ; les zéros faute de
      source (IR ciblé, CSG progressive, âge de départ) ;
  (3) le PÉRIMÈTRE : les montants hors du revenu disponible au sens de l'INSEE
      (successions, taxe foncière, TVA, accises, carbone, aides à la
      rénovation, franchises de santé, impôt d'entreprise) émettent 0 ;
  (4) les SIGNES sourcés (CSG : une hausse réduit l'indice) ;
  (5) GINI_BASE = dernière valeur publiée par l'INSEE.
"""
import re

import pytest

import budget_simulator.constants as C
from budget_simulator.simulator import BudgetSimulatorV45

Y = C.MASSE_NIVEAUX_DE_VIE_MD_EUR
G = C.GINI_BASE

# Classement de TOUTES les constantes Gini « par Md€ » du module. Une constante
# ajoutée sans classement fait rougir test_toute_constante_gini_par_md_est_classee.
PRELEVEMENT, PRESTATION = 'prelevement', 'prestation'
CLASSEMENT = {
    'GINI_SOLIDARITE_PAR_MD': PRESTATION,
    'GINI_PENSIONS_PAR_MD': PRESTATION,
    'GINI_ALLOC_PAR_MD_EUR': PRESTATION,          # par Md€ COUPÉ : même borne
    'ASU_GINI_BORNE_PAR_MD_EUR': PRESTATION,      # le cas limite lui-même
    'GINI_BORNE_PRESTATION_PAR_MD': PRESTATION,
    'GINI_RENOVATION_PAR_MD_EUR': PRESTATION,
    'GINI_CSG_PAR_MD': PRELEVEMENT,
    'GINI_COTIS_SAL_PAR_MD': PRELEVEMENT,         # par Md€ RENDU : même borne
    'GINI_HAUT_PATRIMOINE_PAR_MD': PRELEVEMENT,
    'GINI_IR_PAR_MD': PRELEVEMENT,
    'GINI_CAPITAL_PAR_MD': PRELEVEMENT,
    'GINI_IR_CIBLE_PAR_MD': PRELEVEMENT,
    'GINI_IR_DECOTE_PAR_MD': PRELEVEMENT,
    'GINI_ABATTEMENT_RETRAITES_PAR_MD': PRELEVEMENT,
    'GINI_SUCCESSIONS_PAR_MD': PRELEVEMENT,
    'GINI_TAXE_FONCIERE_PAR_MD': PRELEVEMENT,
    'GINI_TVA_PAR_MD': PRELEVEMENT,
    'GINI_TVA_ENERGIE_PAR_MD': PRELEVEMENT,
    'GINI_BORNE_PRELEVEMENT_PAR_MD': PRELEVEMENT,
}
BORNE = {PRELEVEMENT: (1.0 - G) / Y, PRESTATION: (1.0 + G) / Y}
# Styles du dépôt : GINI_X_PAR_MD, X_GINI_PAR_MD et l'historique X_GINI_PAR_10MD
# (effet pour 10 Md€, ramené à un Md€ par la garde).
_MOTIF = re.compile(r'GINI.*PAR_(\d*)MD')


def _constantes_gini_par_md():
    return sorted(n for n in dir(C) if _MOTIF.search(n) and isinstance(getattr(C, n), (int, float)))


def _par_md(nom):
    n = _MOTIF.search(nom).group(1)
    return getattr(C, nom) / (int(n) if n else 1)


def test_toute_constante_gini_par_md_est_classee():
    """Une constante par Md€ qui échapperait au classement échapperait à la borne."""
    non_classees = [n for n in _constantes_gini_par_md() if n not in CLASSEMENT]
    assert not non_classees, f"constantes Gini par Md€ non classées : {non_classees}"
    disparues = [n for n in CLASSEMENT if not hasattr(C, n)]
    assert not disparues, f"classement périmé (constantes absentes) : {disparues}"


@pytest.mark.parametrize('nom', sorted(CLASSEMENT))
def test_borne_arithmetique_de_chaque_coefficient(nom):
    """|K| ≤ (1 − G)/Y (prélèvement) ou (1 + G)/Y (prestation), C ∈ [−1 ; 1].
    Pour un prélèvement, (1 − G)/Y borne la BAISSE de l'indice (tout payé par
    le plus aisé) ; un prélèvement régressif peut l'augmenter jusqu'à
    (1 + G)/Y : le test applique la plus stricte des deux, sans danger."""
    if not hasattr(C, nom):
        pytest.skip('absente (voir le test de classement)')
    k = _par_md(nom)
    borne = BORNE[CLASSEMENT[nom]]
    assert abs(k) <= borne * (1 + 1e-12), f"{nom} = {k:.7f} > borne {borne:.7f}"


def test_canal_duree_du_chomage_sous_la_borne():
    """Le canal durée vaut GINI_DUREE_SURPOIDS fois la règle montant : il reste
    sous la borne d'une prestation (C implicite ≥ −1)."""
    assert C.GINI_DUREE_SURPOIDS * C.GINI_ALLOC_PAR_MD_EUR <= BORNE[PRESTATION]


def test_les_bornes_nommees_sont_les_bornes():
    assert C.GINI_BORNE_PRELEVEMENT_PAR_MD == pytest.approx(BORNE[PRELEVEMENT], rel=1e-15)
    assert C.GINI_BORNE_PRESTATION_PAR_MD == pytest.approx(BORNE[PRESTATION], rel=1e-15)
    assert C.ASU_GINI_BORNE_PAR_MD_EUR == pytest.approx(C.GINI_BORNE_PRESTATION_PAR_MD, rel=1e-15)


def test_la_garde_attrape_un_coefficient_hors_borne(monkeypatch):
    """Mutation : l'ancienne règle du patrimoine (−0,001 par Md€) rougit."""
    monkeypatch.setattr(C, 'GINI_HAUT_PATRIMOINE_PAR_MD', -0.001)
    with pytest.raises(AssertionError):
        test_borne_arithmetique_de_chaque_coefficient('GINI_HAUT_PATRIMOINE_PAR_MD')


def test_la_garde_attrape_le_style_historique(monkeypatch):
    """Mutation : une constante au style historique (« …_GINI_PAR_10MD »), hors
    classement, rougit ; ramenée à un Md€, elle est mesurée contre la borne."""
    monkeypatch.setattr(C, 'CAPITAL_GINI_PAR_10MD', -0.02, raising=False)
    with pytest.raises(AssertionError):
        test_toute_constante_gini_par_md_est_classee()
    assert _par_md('CAPITAL_GINI_PAR_10MD') == pytest.approx(-0.002)


# ---------------------------------------------------------------------------
# (2) Recette INSEE exécutée : classement FINAL (Lerman et Yitzhaki)
# ---------------------------------------------------------------------------

def _concentration(montants, poids=None):
    """Concentration groupée (trapèzes), recalculée ici indépendamment du module."""
    poids = poids or [1.0 / len(montants)] * len(montants)
    total, cumul, aire = sum(montants), 0.0, 0.0
    for m, w in zip(montants, poids):
        suivant = cumul + m / total
        aire += w * (cumul + suivant) / 2
        cumul = suivant
    return 1 - 2 * aire


# INSEE, Revenus et patrimoine des ménages, éd. 2024 : fiche 1.3, figure 1
# (niveau de vie moyen par dixième, 2021, lu p. 82) ; fiche 1.4, figure 1
# (RPM2024-F4.xlsx, part de la composante dans le niveau de vie, en %).
NIVEAU_DE_VIE = [8820, 14010, 16980, 19590, 21980, 24470, 27310, 31020, 37060, 64840]
FIGURE_1_RPM = {
    'Prestations familiales': [14.7, 8.5, 5.4, 3.7, 2.8, 2.2, 1.6, 1.1, 0.7, 0.2],
    'Prestations logement': [12.8, 5.5, 2.1, 0.9, 0.5, 0.3, 0.2, 0.2, 0.1, 0.1],
    'Minima sociaux': [16.7, 7.2, 3.5, 2, 1.1, 0.8, 0.5, 0.4, 0.3, 0.1],
    "Prime d'activité": [3, 3.2, 2.4, 1.5, 0.8, 0.6, 0.3, 0.2, 0.1, 0],
    'Pensions et retraites': [16.9, 25.2, 29.2, 29, 26.9, 28.9, 26.5, 25.8, 24.5, 16],
    'Allocations chômage': [9.2, 6.8, 5.4, 4.5, 3.7, 2.4, 2.3, 2, 1.7, 1.5],
    'Revenus du patrimoine': [2.5, 2.3, 2.8, 2.8, 3, 3.7, 4.5, 5.4, 7.6, 22.7],
    'Salaires': [28.4, 45.6, 55.2, 63.1, 69.2, 70.5, 75.4, 77.3, 78.8, 73.5],
    'Contributions sociales : CSG et CRDS': [-4.6, -6.5, -8, -8.9, -9.8, -10.2, -10.8, -11.3, -11.9, -14.1],
    'Impôt sur le revenu et le patrimoine': [-2, -0.4, -0.6, -0.7, -1.4, -1.9, -3.9, -4.8, -7.3, -14],
}
G_DIXIEMES = _concentration(NIVEAU_DE_VIE)


def _ecart(*lignes):
    """(C − G) / Y au classement final, C et G sur les mêmes dixièmes."""
    montants = [abs(sum(FIGURE_1_RPM[l][i] for l in lignes)) * NIVEAU_DE_VIE[i] for i in range(10)]
    return (_concentration(montants) - G_DIXIEMES) / Y


def test_donnees_rpm_conformes_a_la_figure():
    nv = C.INSEE_RPM2024_NIVEAU_DE_VIE_DIXIEMES
    assert list(nv) == NIVEAU_DE_VIE
    corresp = {'prestations_familiales': 'Prestations familiales', 'prestations_logement': 'Prestations logement',
               'minima_sociaux': 'Minima sociaux', 'prime_activite': "Prime d'activité",
               'pensions_retraites': 'Pensions et retraites', 'allocations_chomage': 'Allocations chômage',
               'revenus_patrimoine': 'Revenus du patrimoine', 'salaires': 'Salaires',
               'csg_crds': 'Contributions sociales : CSG et CRDS',
               'impot_revenu_patrimoine': 'Impôt sur le revenu et le patrimoine'}
    assert set(C.INSEE_RPM2024_COMPOSITION) == set(corresp)
    for cle, ligne in corresp.items():
        assert list(C.INSEE_RPM2024_COMPOSITION[cle]) == [abs(x) for x in FIGURE_1_RPM[ligne]], cle
    assert C.GINI_DIXIEMES_RPM2024 == pytest.approx(G_DIXIEMES, rel=1e-12)
    assert G_DIXIEMES == pytest.approx(0.286, abs=5e-4)   # 0,294 publié en 2021 : le regroupement minore


@pytest.mark.parametrize('nom,lignes,signe,valeur', [
    ('GINI_SOLIDARITE_PAR_MD', ('Prestations familiales', 'Prestations logement', 'Minima sociaux',
                                "Prime d'activité"), +1, -0.000521),
    ('GINI_CSG_PAR_MD', ('Contributions sociales : CSG et CRDS',), -1, -0.0000863),
    ('GINI_IR_PAR_MD', ('Impôt sur le revenu et le patrimoine',), -1, -0.000297),
    ('GINI_ALLOC_PAR_MD_EUR', ('Allocations chômage',), -1, +0.000238),     # par Md€ COUPÉ
    ('GINI_COTIS_SAL_PAR_MD', ('Salaires',), +1, +0.0000541),               # par Md€ RENDU
])
def test_recette_au_classement_final(nom, lignes, signe, valeur):
    """K = ±(C − G)/Y, C de la composante au classement final (fiche 1.4 ×
    fiche 1.3), G des mêmes dixièmes."""
    assert getattr(C, nom) == pytest.approx(signe * _ecart(*lignes), rel=1e-12)
    assert getattr(C, nom) == pytest.approx(valeur, rel=0.002)


# Recoupement publié, classement INITIAL : France, portrait social 2025, fiche
# « Redistribution monétaire », figure 2 (FPORSOC25-F20.xlsx) : (part dans le
# niveau de vie A en %, progressivité B, contribution C en %).
FIGURE_2 = {
    'prelevements': (-16.9, 2.2, 40.3),
    'prestations': (5.8, 9.5, 59.7),
    'cotisations_famille': (-3.1, 0.4, 1.3),
    'contributions_sociales': (-7.3, 0.8, 6.6),
    'impot_revenu': (-6.4, 4.6, 31.7),
    'impot_fortune_immobiliere': (-0.1, 5.2, 0.6),
}


def test_donnees_insee_conformes_a_la_figure():
    for k, (a, b, _) in FIGURE_2.items():
        assert C.INSEE_FPS2025_REDISTRIBUTION[k] == (a, b), k


def test_la_contribution_publiee_est_le_produit_a_fois_b():
    """Note de la figure : « la contribution […] correspond au produit |A×B| en
    pourcentage » — vérifiée sur les lignes publiées, à l'arrondi près (±0,05
    sur A, B et C)."""
    total = sum(abs(FIGURE_2[k][0]) * FIGURE_2[k][1] for k in ('prelevements', 'prestations'))
    for k, (a, b, contribution) in FIGURE_2.items():
        tolerance = 0.05 / abs(a) + 0.05 / b + 0.05 / contribution
        assert 100 * abs(a) * b / total == pytest.approx(contribution, rel=tolerance), k
    assert C.GINI_REDUCTION_VERTICALE_FPS2025 == pytest.approx(total / 1000, rel=1e-15)
    assert C.GINI_REDUCTION_VERTICALE_FPS2025 == pytest.approx(0.0923, abs=1e-4)


def _k_figure_2(transfert, prestation):
    v = C.GINI_REDUCTION_VERTICALE_FPS2025
    b = FIGURE_2[transfert][1]
    return (v - b / 10) / Y if prestation else -(b / 10 + v) / Y


def test_haut_patrimoine_garde_la_figure_2():
    """L'IFI, que la fiche 1.4 ne sépare pas, garde le classement initial."""
    assert C.GINI_HAUT_PATRIMOINE_PAR_MD == pytest.approx(_k_figure_2('impot_fortune_immobiliere', False), rel=1e-12)
    assert C.GINI_HAUT_PATRIMOINE_PAR_MD == pytest.approx(-0.000444, rel=0.01)


@pytest.mark.parametrize('nom,transfert,prestation,facteur', [
    ('GINI_SOLIDARITE_PAR_MD', 'prestations', True, (1.15, 1.25)),
    ('GINI_CSG_PAR_MD', 'contributions_sociales', False, (1.40, 1.50)),
    ('GINI_IR_PAR_MD', 'impot_revenu', False, (1.30, 1.40)),
])
def test_le_classement_initial_majore_les_k(nom, transfert, prestation, facteur):
    """Recoupement : la pente du pseudo-Gini (figure 2) dépasse celle du Gini
    publié (classement final) de 19 à 45 % — même signe, même ordre."""
    rapport = _k_figure_2(transfert, prestation) / getattr(C, nom)
    assert facteur[0] <= rapport <= facteur[1], rapport


def test_cotisations_classement_initial_dans_la_plage_du_12_11():
    """Le proxy de la figure 2 (cotisations famille) donnait +0,0000959, dans la
    plage de la décision du mainteneur du 12/11/2026 (+0,00006 à +0,0001) ; le classement final
    (salaires) donne moins : plafonds non comptés, effet encore majoré."""
    assert 0.00006 <= -_k_figure_2('cotisations_famille', False) <= 0.0001
    assert 0 < C.GINI_COTIS_SAL_PAR_MD < 0.00006


# ---------------------------------------------------------------------------
# (2 bis) Règles à plage publiée, recalculées depuis les tableaux publiés
# ---------------------------------------------------------------------------

# IPP, rapport 2025-2026, chapitre 2, tableau 2.2 (pertes en % du niveau de vie
# des 50 % les plus modestes / 50 à 90 % / 10 % les plus aisés), trois groupes
# pesés par les parts de masse de l'INSEE 2024 (« Niveau de vie et indicateurs
# d'inégalités » : S50 30,1 %, S90 75,1 %).
MASSES_TROIS_GROUPES = [0.301, 0.751 - 0.301, 1 - 0.751]
POIDS_TROIS_GROUPES = [0.5, 0.4, 0.1]


def _ipp_trois_groupes(pertes_pct, prestation):
    g = _concentration(MASSES_TROIS_GROUPES, POIDS_TROIS_GROUPES)
    c = _concentration([p * m for p, m in zip(pertes_pct, MASSES_TROIS_GROUPES)], POIDS_TROIS_GROUPES)
    return (c - g) / Y if prestation else -(c - g) / Y


def _rapport_dix_sur_trois(*lignes):
    """Biais du regroupement en trois groupes, mesuré sur les dixièmes INSEE."""
    nv = NIVEAU_DE_VIE
    m = [abs(sum(FIGURE_1_RPM[l][i] for l in lignes)) * nv[i] for i in range(10)]
    trois = lambda x: [sum(x[:5]), sum(x[5:9]), x[9]]
    c3 = _concentration(trois(m), POIDS_TROIS_GROUPES) - _concentration(trois(nv), POIDS_TROIS_GROUPES)
    return (_concentration(m) - G_DIXIEMES) / c3


def test_pensions_plage_et_centre():
    faible, forte = C.GINI_PENSIONS_PLAGE_PAR_MD
    assert _ecart('Pensions et retraites') == pytest.approx(faible, rel=0.005)
    assert _ipp_trois_groupes([0.21, 0.17, 0.10], True) == pytest.approx(forte, rel=0.005)   # gel 2026
    # Sur les dixièmes INSEE, les trois groupes MAJORENT l'écart des pensions :
    # aucune correction à la hausse n'est légitime.
    assert _rapport_dix_sur_trois('Pensions et retraites') < 1
    assert C.GINI_PENSIONS_PAR_MD == pytest.approx((faible + forte) / 2, rel=1e-15)


def test_abattement_plage_et_centre():
    faible, forte = C.GINI_ABATTEMENT_RETRAITES_PLAGE_PAR_MD
    brut = _ipp_trois_groupes([0.18, 0.40, 0.32], False)   # suppression de l'abattement
    assert brut == pytest.approx(faible, rel=0.005)
    rapport_csg = _rapport_dix_sur_trois('Contributions sociales : CSG et CRDS')
    assert rapport_csg == pytest.approx(1.11, abs=0.005)
    assert brut * rapport_csg == pytest.approx(forte, rel=0.005)
    assert 1 < _rapport_dix_sur_trois('Impôt sur le revenu et le patrimoine') < rapport_csg
    assert C.GINI_ABATTEMENT_RETRAITES_PAR_MD == pytest.approx((faible + forte) / 2, rel=1e-15)


def test_capital_borne_basse_sourcee():
    faible, forte = C.GINI_CAPITAL_PLAGE_PAR_MD
    assert _ipp_trois_groupes([0.08, 0.13, 2.26], False) == pytest.approx(faible, rel=0.005)   # suppression du PFU
    assert forte == pytest.approx(-C.GINI_BORNE_PRELEVEMENT_PAR_MD, rel=0.002)
    assert C.GINI_CAPITAL_PAR_MD == faible
    # Plus lâche : revenus du patrimoine de la fiche 1.4 (toutes assiettes).
    assert abs(-_ecart('Revenus du patrimoine')) < abs(faible)


def test_decote_recalculee():
    """Conseil des prélèvements obligatoires, rapport particulier n° 2 (mai
    2024), tableau n° 34 : gain de la décote par dixième de revenu déclaré par
    unité de consommation (Md€)."""
    c34 = _concentration([0.0, 0.0, 0.1, 0.8, 1.6, 2.0, 1.8, 1.0, 0.2, 0.1])
    assert C.GINI_C_DECOTE == pytest.approx(c34, abs=5e-5)
    assert C.GINI_IR_DECOTE_PAR_MD == pytest.approx((G - C.GINI_C_DECOTE) / Y, rel=1e-15)


def test_smic_plage_et_centre():
    """Groupe d'experts sur le SMIC, rapport du 1er décembre 2017 : gains d'une
    hausse de 1 % par dixième de niveau de vie initial (M€), graphiques n° 41 et
    45 ; effet par unité de hausse = 100 × (C − G) × gains / Y, aux grandeurs de
    2017 (G 0,289, Y ≈ 1 060 Md€) ou de 2024 (G 0,302, Y 1 380, gains × 1,30)."""
    valeurs = []
    for gains in ([30, 60, 90, 100, 110, 100, 80, 60, 40, 20], [30, 60, 90, 110, 110, 100, 80, 60, 40, 20]):
        c = _concentration(gains)
        assert -0.07 < c < -0.06
        for g, y, f in ((0.289, 1060.0, 1.0), (0.302, 1380.0, 1.30)):
            valeurs.append(100 * (c - g) * sum(gains) / 1000 * f / y)
    faible, forte = C.GINI_SMIC_PLAGE_PAR_HAUSSE
    assert min(valeurs, key=abs) == pytest.approx(faible, rel=0.005)
    assert max(valeurs, key=abs) == pytest.approx(forte, rel=0.005)
    # Le tableau n° 12 (« Indice de Gini −0,1 % ») en est l'arrondi : effet
    # relatif de 2017 entre −0,05 et −0,15 %.
    assert -0.0015 < valeurs[0] / 100 / 0.289 < -0.0005
    assert C.GINI_SMIC_PAR_HAUSSE == pytest.approx((faible + forte) / 2, rel=1e-15)


def test_zeros_faute_de_source():
    """Règle du mainteneur : sans source, zéro et limite déclarée."""
    assert C.GINI_IR_CIBLE_PAR_MD == 0.0
    assert C.GINI_CSG_PROGRESSIVE == 0.0
    assert C.RETRAITES_GINI_PAR_ANNEE_ECART == 0.0


def test_la_baisse_de_l_ir_de_2020_montrerait_l_indice_en_hausse():
    """Seule source consultée qui ventile une baisse d'IR par dixième de niveau
    de vie (INSEE, France, portrait social 2022, figure 4 : gains de la baisse
    du taux de la première tranche, €/an) : +0,000109 à +0,000120 par Md€ de
    baisse, cité dans constants.py ; valable pour CET instrument seulement."""
    c = _concentration([0, 0, 10, 20, 70, 140, 230, 290, 250, 160])
    assert c == pytest.approx(0.452, abs=5e-4)
    assert (c - 0.302) / Y == pytest.approx(0.000109, rel=0.005)
    assert (c - G_DIXIEMES) / Y == pytest.approx(0.000120, rel=0.005)


# ---------------------------------------------------------------------------
# (3) Périmètre : hors revenu disponible → 0 ; (4) signes ; (5) base
# ---------------------------------------------------------------------------

# Année = origine de l'horloge d'un levier sur un moteur neuf (POLICY_START_YEAR) :
# les leviers à effet d'entrée en vigueur (CSG, TVA énergie, superprofits) y
# émettent, sinon un test « émet zéro » serait trivialement vert.
ETAT = {'year': C.POLICY_START_YEAR, 'gdp': C.PIB_BASE_2025_MD_EUR,
        'inflation': 0.016, 'unemployment': 0.075}


def _gini(levier, params, mesures=None):
    sim = BudgetSimulatorV45(periods=1)
    sim._reset_state()
    if mesures is not None:
        sim.mesures = mesures
    _, _, impacts = sim.measure_handlers[levier](
        sim.measure_registry[levier], params, ETAT['year'], ETAT['gdp'],
        ETAT['inflation'], ETAT['unemployment'])
    return (impacts or {}).get('gini', 0.0)


@pytest.mark.parametrize('levier,params', [
    ('droits_succession', {'variation': 10.0}),
    ('droits_succession', {'variation': -10.0}),
    ('tva_rate', {'taux': 0.22}),
    ('tva_energie', {'taux': 0.055}),
    ('fiscalite_indirecte', {'tva_ciblee': 5.0, 'accises_energie': 3.0}),
    ('transition_ecologique', {'investissement': 10, 'renovation': 10, 'taxe_carbone': 100}),
    ('taxe_superprofits', {'intensite': 1.0}),
])
def test_hors_revenu_disponible_emet_zero(levier, params):
    assert _gini(levier, params) == 0.0


@pytest.mark.parametrize('taux', [0, 50, 200])
def test_franchises_de_sante_emettent_zero(taux):
    assert _gini('sante', {'effort_hopital': 0, 'effort_ambu': 0, 'effort_prev_org': 0,
                           'franchise_participation_taux': taux}) == 0.0


def test_patrimoine_seul_l_ifi_compte():
    """IFI 2 Md€ × intensité au coefficient de l'IFI ; successions et foncière à 0."""
    assert _gini('fiscalite_patrimoine', {'intensite': 0.3}) == pytest.approx(
        C.GINI_HAUT_PATRIMOINE_PAR_MD * 2.0 * 0.3, rel=1e-12)


def test_csg_une_hausse_reduit_l_indice():
    """Signe sourcé (INSEE : contributions sociales faiblement progressives)."""
    assert _gini('csg', {'taux': 0.107, 'progressive': 0}) < 0
    assert _gini('csg', {'taux': 0.087, 'progressive': 0}) > 0


def test_csg_au_coefficient_par_md():
    """Re-déclaré au commit d'équations du lot 4 : la part du taux qui porte la
    hausse de 2026 sur les revenus du capital (jusqu'au taux du droit en
    vigueur) prend le coefficient du capital ; le reste, celui de la CSG
    (tests/test_gini_equations_lot4.py, section 8)."""
    gini = _gini('csg', {'taux': 0.107, 'progressive': 0})
    recette = 140.0 * (0.107 - 0.097) / 0.097
    capital = 140.0 * (C.CSG_TAUX_DROIT_EN_VIGUEUR_2026 - 0.097) / 0.097
    assert gini == pytest.approx(C.GINI_CAPITAL_PAR_MD * capital + C.GINI_CSG_PAR_MD * (recette - capital), rel=1e-12)


def test_gini_base_derniere_valeur_publiee():
    """INSEE, série « Niveau de vie et indicateurs d'inégalités », parue le
    09/07/2026 : 0,302 en 2024."""
    assert C.GINI_BASE == 0.302


def test_asu_au_coefficient_des_prestations_ciblees():
    """Allocation sociale unique (arbitrage du mainteneur) : le transfert net
    (effort + recours) au coefficient des prestations ciblées de l'INSEE, et
    non plus à la borne théorique C = −1, qui reste au-dessus."""
    from budget_simulator.constants import asu_cout_recours_md_eur
    sim = BudgetSimulatorV45(periods=1)
    sim._reset_state()
    params = {'asu_activation': 1, 'asu_plafonnement': 0.7}
    sim.mesures = {'asu': params}
    g = []
    for an in range(C.POLICY_START_YEAR, C.POLICY_START_YEAR + 6):
        _, _, imp = sim.measure_handlers['asu'](sim.measure_registry['asu'], dict(params), an,
                                                ETAT['gdp'], ETAT['inflation'], ETAT['unemployment'])
        g.append((imp or {}).get('gini', 0.0))
    transfert = C.asu_effort_perenne_md_eur(0.7) + asu_cout_recours_md_eur(1.0)
    assert sum(g) == pytest.approx(C.GINI_SOLIDARITE_PAR_MD * transfert, rel=1e-9)
    assert abs(sum(g)) < C.ASU_GINI_BORNE_PAR_MD_EUR * transfert
