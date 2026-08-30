"""Passe v0.6.4 — calage chômage (31/08/2026), tests-propriétés AVANT fix.

CALAGE 1 — base du canal taux : 40 → 36,6 Md€. Le 40 historique agrégeait des
charges que le taux de remplacement ne met PAS à l'échelle (validation des
points de retraite 2,43 Md€ — assiette = SJR, pas l'allocation ; contribution
France Travail 4,98 — assise sur les recettes N−2 ; aides forfaitaires). La
base recalée = la somme des lignes proportionnelles à l'allocation dans le
rapport financier Unédic 2025 (p. 75-76) : ARE 32,124 + ARE-F 1,718 +
ASR/ASP 1,745 + autres 0,020 + ARCE 0,956 = 36,563 → 36,6.

CALAGE 2 — gini_duree recalé sur les données de bascule fin de droits :
Dares Focus n° 53 (destins à +3 mois : 31 % emploi / 18 % RSA / 11 % ASS /
71 % ni-ni) × DREES E&R n° 1368 (positions distributives observées, ERFS×DRM).
Estimateur par coefficients de concentration (vérification adverse, constat
22) : surpoids k ≈ 1,6 par euro coupé vs canal taux — l'ancien coefficient
(0,002/6 mois) portait un k implicite de 0,556. Forme structurelle : les
termes Gini se construisent sur delta_montant/delta_duree DÉJÀ calculés
(l'interaction × taux/TAUX_REF du canal € est partagée par construction,
constat 23).

BUG (vérification adverse, constat 27, PRÉ-EXISTANT) — la dégressivité était
un « free lunch » Gini : ses ±15 % d'allocations passaient à la dépense, au
PA et à la compétitivité (fix v0.6.3) mais PAS au Gini — du revenu retiré aux
ménages à coût distributif nul, la forme exacte que test_asu_no_free_lunch
interdit au handler voisin. Aucun des 10 scénarios précalculés n'active la
dégressivité : fix d'invariant pur, zéro cascade.

Dossier complet : docs/plans/calage-chomage-v064.md (repo parent, gitignoré).
"""
import pytest

from budget_simulator.constants import (
    ASU_GINI_BORNE_PAR_MD_EUR,
    CHOMAGE_DUREE_REF_MOIS,
    CHOMAGE_MONTANT_REF_MD,
    CHOMAGE_TAUX_REF,
    COUT_CHOMAGE_MARGINAL_MOIS_MD,
    GINI_IMPACT_SCALE,
)
from budget_simulator.simulator import BudgetSimulatorV45

_GDP, _INFLATION, _UNEMP = 3000.0, 0.02, 0.075


def _chomage(params):
    sim = BudgetSimulatorV45(periods=10)
    return sim._apply_chomage_alloc({}, params, 2027, _GDP, _INFLATION, _UNEMP)


def _chomage_ds(params):
    return _chomage(params)[0]


def _chomage_gini(params):
    return _chomage(params)[2]['gini']


# ---------------------------------------------------------------------------
# CALAGE 1 — base du canal taux 36,6 Md€
# ---------------------------------------------------------------------------

class TestBaseCanalTaux:
    def test_la_base_vaut_la_somme_des_lignes_proportionnelles(self):
        """36,6 = ARE + ARE-F + ASR/ASP + autres + ARCE (Unédic 2025, p. 75-76,
        M€ exacts). Un futur recalage doit repartir des comptes, pas dériver."""
        somme_sourcee = 32.1237 + 1.7184 + 1.7451 + 0.0201 + 0.9562
        assert CHOMAGE_MONTANT_REF_MD == pytest.approx(36.6, abs=1e-9)
        assert CHOMAGE_MONTANT_REF_MD == pytest.approx(somme_sourcee, abs=0.05)

    def test_le_canal_taux_porte_la_nouvelle_base(self):
        """Taux 60 % → 50 % à durée de référence = 36,6 × (50/60 − 1) = −6,10
        Md€ (au lieu de −6,67 avec la base 40)."""
        ds = _chomage_ds({'taux_remplacement': 0.50, 'duree': 18,
                          'degressivite': False})
        assert ds == pytest.approx(CHOMAGE_MONTANT_REF_MD * (0.50 / 0.60 - 1),
                                   rel=1e-9)
        assert ds == pytest.approx(-6.10, abs=0.005)

    def test_le_defaut_legacy_egale_la_base(self):
        """Le neutre legacy (config.load_default_values) DOIT égaler la
        constante — sinon un appel legacy sans montant encode une hausse
        fantôme de taux (0,60 × 40/36,6)."""
        from budget_simulator.config import load_default_values
        defaut = load_default_values()['chomage_alloc']
        assert defaut['montant'] == pytest.approx(CHOMAGE_MONTANT_REF_MD)
        assert defaut['duree'] == CHOMAGE_DUREE_REF_MOIS

    def test_le_registre_public_est_aligne_sur_la_reference(self):
        """policy_measures.json portait encore les défauts PRÉ-réforme (45/24,
        découverts à l'inventaire v0.6.4) : le registre public doit déclarer
        la même référence que le moteur calcule."""
        from budget_simulator.config import load_policy_config
        mesures = {m['id']: m for m in load_policy_config()['mesures']}
        params = mesures['chomage_alloc']['parametres']
        assert params['montant']['valeur_defaut'] == pytest.approx(
            CHOMAGE_MONTANT_REF_MD)
        assert params['duree']['valeur_defaut'] == CHOMAGE_DUREE_REF_MOIS

    def test_le_contraste_marginal_moyen_survit_au_recalage(self):
        """La dérivation du 0,75 argumente « marginal ≪ moyen » : avec 36,6 le
        moyen vaut 2,03 Md€/mois, rapport 2,7 — l'argument tient."""
        moyen = CHOMAGE_MONTANT_REF_MD / CHOMAGE_DUREE_REF_MOIS
        assert moyen == pytest.approx(2.03, abs=0.01)
        assert moyen / COUT_CHOMAGE_MARGINAL_MOIS_MD > 2.5


# ---------------------------------------------------------------------------
# CALAGE 2 — gini_duree : surpoids k observé, interaction taux structurelle
# ---------------------------------------------------------------------------

class TestGiniDureeRecale:
    def test_le_surpoids_reste_dans_la_fourchette_observee(self):
        """k ∈ [1,3 ; 2,2] : l'encadrement par coefficients de concentration
        sur DREES 1368 × Dares 53 (le trou des 71 % « ni-ni » porte la
        largeur). Sortir de la fourchette = nouvelle source, pas une dérive."""
        from budget_simulator.constants import GINI_DUREE_SURPOIDS
        assert 1.3 <= GINI_DUREE_SURPOIDS <= 2.2

    def test_la_regle_montant_est_la_source_unique_du_par_euro(self):
        """GINI_ALLOC_PAR_MD = 0,004/5 (OFCE 2023) : le canal durée s'exprime
        en multiple de la règle montant — réviser l'une propage l'autre."""
        from budget_simulator.constants import GINI_ALLOC_PAR_MD
        assert GINI_ALLOC_PAR_MD == pytest.approx(0.004 / 5)

    def test_couper_six_mois_emet_k_fois_la_regle_montant(self):
        """18 → 12 mois à taux de référence : gini = k × 0,0008 × (6 × 0,75)
        — le même euro, pesé k fois plus (population fin de droits).
        AVANT recalage : 0,002 (k implicite 0,556)."""
        from budget_simulator.constants import (GINI_ALLOC_PAR_MD,
                                                GINI_DUREE_SURPOIDS)
        gini = _chomage_gini({'taux_remplacement': 0.60, 'duree': 12,
                              'degressivite': False})
        attendu = (GINI_DUREE_SURPOIDS * GINI_ALLOC_PAR_MD
                   * 6 * COUT_CHOMAGE_MARGINAL_MOIS_MD)
        assert gini == pytest.approx(attendu, rel=1e-9)

    def test_le_gini_duree_suit_le_taux_comme_le_canal_euro(self):
        """Constat 23 (bloquant) : les euros du Gini sont LES MÊMES euros que
        le canal € (delta_duree porte × taux/0,60 depuis v0.6.3). À taux
        45 %, la composante durée du Gini est donc × 0,75."""
        from budget_simulator.constants import (GINI_ALLOC_PAR_MD,
                                                GINI_DUREE_SURPOIDS)
        gini_duree_seul = (
            _chomage_gini({'taux_remplacement': 0.45, 'duree': 12,
                           'degressivite': False})
            - _chomage_gini({'taux_remplacement': 0.45, 'duree': 18,
                             'degressivite': False}))
        attendu = (GINI_DUREE_SURPOIDS * GINI_ALLOC_PAR_MD
                   * 6 * COUT_CHOMAGE_MARGINAL_MOIS_MD * (0.45 / 0.60))
        assert gini_duree_seul == pytest.approx(attendu, rel=1e-9)

    def test_allonger_la_duree_reduit_le_gini(self):
        """Symétrie v0.6.3 préservée : des mois de droits en plus sont
        progressifs (signe négatif)."""
        assert _chomage_gini({'taux_remplacement': 0.60, 'duree': 24,
                              'degressivite': False}) < 0

    def test_le_reel_delivre_reste_sous_la_borne_arithmetique(self):
        """Filet physique lâche (constat 24, RECLASSÉ après contre-vérif) :
        après le rescale d'assemblage (× GINI_IMPACT_SCALE), le Gini RÉEL
        délivré par Md€ de durée coupée ne peut pas dépasser la borne C = −1
        (ASU_GINI_BORNE_PAR_MD_EUR) — le maximum arithmétique d'un transfert
        intégralement pris au premier centile. Ne mord qu'à k > 5,3 : c'est le
        garde-fou contre l'erreur grossière (k fantaisiste, scale cassé), pas
        la contrainte fine — celle-ci est le test du C implicite ci-dessous.
        (La comparaison PRÉ-scale croiserait deux familles de calibration —
        NB constants.py, chantier v0.7.)"""
        from budget_simulator.constants import (GINI_ALLOC_PAR_MD,
                                                GINI_DUREE_SURPOIDS)
        reel_par_md = GINI_IMPACT_SCALE * GINI_DUREE_SURPOIDS * GINI_ALLOC_PAR_MD
        assert reel_par_md <= ASU_GINI_BORNE_PAR_MD_EUR

    def test_le_c_implicite_du_canal_duree_reste_arithmetiquement_valide(self):
        """Contrainte fine (contre-vérification du constat 24) : le surpoids k
        s'interprète comme un coefficient de concentration implicite
        C_durée = G − k × (G − C_ARE), qui doit rester ≥ −1 (un transfert ne
        peut pas être plus concentré que « tout au premier centile »). À
        k = 1,6 : C_durée ≈ −0,39, cohérent avec l'estimation indépendante
        des déciles DREES pour le mix fin-de-droits (−0,27 à −0,49).

        C_ARE = 2·F̄ − 1 sur les personnes en ménages ARE, avec la recette de
        recalcul (à refaire si GINI_BASE ou la source DREES bouge) : déciles
        publiés DREES E&R n° 1368, graphique 1 — D1 13 %, D2 13 %, D6-D10
        37 % au rang moyen r = 0,75, bloc D3-D5 (37 %) au rang moyen 0,35 →
        F̄ = 0,13×0,05 + 0,13×0,15 + 0,37×0,35 + 0,37×0,75 ≈ 0,433 →
        C_ARE ≈ −0,134. Sensibilité déclarée : r = 0,70 → C_ARE −0,078
        (k_max 3,5) ; r = 0,80 → −0,226 (k_max 2,5) ; le k_max ≈ 3,04 du
        commentaire constants.py est calculé à r = 0,75."""
        from budget_simulator.constants import GINI_BASE, GINI_DUREE_SURPOIDS
        C_ARE = -0.134
        c_duree_implicite = GINI_BASE - GINI_DUREE_SURPOIDS * (GINI_BASE - C_ARE)
        assert c_duree_implicite >= -1.0
        assert c_duree_implicite == pytest.approx(-0.39, abs=0.02)


# ---------------------------------------------------------------------------
# BUG constat 27 — dégressivité : plus de free lunch Gini
# ---------------------------------------------------------------------------

class TestDegressiviteGini:
    def test_la_degressivite_aggrave_le_gini_d_une_coupe(self):
        """Une coupe avec dégressivité retire 15 % d'allocations EN PLUS : ces
        euros doivent passer au Gini comme ils passent à la dépense, au PA et
        à la compétitivité (v0.6.3). AVANT fix : Gini identique avec et sans."""
        avec = _chomage_gini({'taux_remplacement': 0.50, 'duree': 18,
                              'degressivite': True})
        sans = _chomage_gini({'taux_remplacement': 0.50, 'duree': 18,
                              'degressivite': False})
        assert avec == pytest.approx(1.15 * sans, rel=1e-9)

    def test_la_degressivite_attenue_le_gini_d_une_hausse(self):
        """Symétrique : une hausse dégressive verse 15 % de moins — son
        bénéfice distributif est atténué d'autant (× 0,85)."""
        avec = _chomage_gini({'taux_remplacement': 0.70, 'duree': 18,
                              'degressivite': True})
        sans = _chomage_gini({'taux_remplacement': 0.70, 'duree': 18,
                              'degressivite': False})
        assert avec == pytest.approx(0.85 * sans, rel=1e-9)
