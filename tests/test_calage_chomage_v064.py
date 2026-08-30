"""Passe v0.6.4 — calage chômage (31/08/2026), tests-propriétés AVANT fix.

CALAGE 1 — base du canal taux : 40 → 36,6 Md€. Le 40 historique (≈ charges
techniques Unédic hors France Travail, 40,02 en 2025) agrégeait des charges
que le taux de remplacement ne met PAS à l'échelle (validation des points de
retraite 2,43 Md€ — assiette = SJR, pas l'allocation ; aides forfaitaires ;
activité partielle). La base recalée = la somme des lignes proportionnelles à
l'allocation dans le rapport financier Unédic 2025 (p. 75-76) : ARE 32,124 +
ARE-F 1,718 + ASR/ASP 1,745 + autres 0,020 + ARCE 0,956 = 36,563 → 36,6.

CALAGE 2 — gini_duree recalé sur les données de bascule fin de droits :
Dares Focus n° 53 (destins à +3 mois : 31 % emploi / 18 % RSA / 11 % ASS /
71 % ni-ni) × DREES E&R n° 1368 (positions distributives observées, ERFS×DRM).
Estimateur par coefficients de concentration (vérification adverse, constat
22) : surpoids k ≈ 1,6 par euro coupé vs canal taux — l'ancien coefficient
(0,002/6 mois) portait un k implicite de 0,556. Forme structurelle : les
termes Gini se construisent sur delta_montant/delta_duree DÉJÀ calculés
(interaction × taux/TAUX_REF ET dégressivité partagées par construction,
constats 23 et 27).

BUG (vérification adverse, constat 27, PRÉ-EXISTANT) — la dégressivité était
un « free lunch » Gini : ses ±15 % d'allocations passaient à la dépense, au
PA et à la compétitivité (fix v0.6.3) mais PAS au Gini. Fix v0.6.4 : le
facteur scale les euros À LA SOURCE — plus aucun canal ne peut l'oublier.
Aucun des 10 scénarios précalculés n'active la dégressivité : zéro cascade.

Choix, alternatives écartées et limites : docs/METHODOLOGIE.md § M35.
"""
import pytest

from budget_simulator.config import load_default_values, load_policy_config
from budget_simulator.constants import (
    ASU_GINI_BORNE_PAR_MD_EUR,
    CHOMAGE_DEGRESSIVITE_FACTEUR_COUPE,
    CHOMAGE_DEGRESSIVITE_FACTEUR_HAUSSE,
    CHOMAGE_DUREE_REF_MOIS,
    CHOMAGE_MONTANT_REF_MD,
    CHOMAGE_TAUX_REF,
    COUT_CHOMAGE_MARGINAL_MOIS_MD,
    GINI_ALLOC_PAR_MD_EUR,
    GINI_BASE,
    GINI_C_ARE,
    GINI_DUREE_SURPOIDS,
    GINI_IMPACT_SCALE,
    PARAM_DOMAINS,
)
from chomage_harness import chomage_ds, chomage_impacts


def _chomage_gini(params):
    return chomage_impacts(params)['gini']


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
        ds = chomage_ds({'taux_remplacement': 0.50, 'duree': 18,
                         'degressivite': False})
        assert ds == pytest.approx(CHOMAGE_MONTANT_REF_MD * (0.50 / 0.60 - 1),
                                   rel=1e-9)
        assert ds == pytest.approx(-6.10, abs=0.005)

    def test_le_defaut_legacy_egale_la_base(self):
        """Le neutre legacy égale la constante PAR IMPORT depuis v0.6.4
        (config.py) — ce test garde la non-régression vers un littéral."""
        defaut = load_default_values()['chomage_alloc']
        assert defaut['montant'] == pytest.approx(CHOMAGE_MONTANT_REF_MD)
        assert defaut['duree'] == CHOMAGE_DUREE_REF_MOIS

    def test_le_registre_public_est_aligne_sur_la_reference(self):
        """policy_measures.json est du JSON — il ne peut pas importer : ses
        valeurs se GARDENT. (45/24 pré-réforme découverts à l'inventaire.)
        Depuis la revue Altitude, le DOMAINE aussi : l'échelle legacy montant
        est une représentation du taux (montant = base × taux/0,60) — min/max
        se dérivent du domaine du taux, sinon déplacer la base re-signifie
        chaque cran du curseur public en silence."""
        mesures = {m['id']: m for m in load_policy_config()['mesures']}
        params = mesures['chomage_alloc']['parametres']
        assert params['montant']['valeur_defaut'] == pytest.approx(
            CHOMAGE_MONTANT_REF_MD)
        assert params['duree']['valeur_defaut'] == CHOMAGE_DUREE_REF_MOIS
        # Le domaine JSON vit DANS le domaine dérivé (PARAM_DOMAINS), qui est
        # lui-même dérivé du domaine du taux — plus de porte legacy hors clamp.
        dom_min, dom_max = PARAM_DOMAINS['chomage_alloc']['montant']
        taux_min, taux_max = PARAM_DOMAINS['chomage_alloc']['taux_remplacement']
        assert dom_min == pytest.approx(
            CHOMAGE_MONTANT_REF_MD * taux_min / CHOMAGE_TAUX_REF)
        assert dom_max == pytest.approx(
            CHOMAGE_MONTANT_REF_MD * taux_max / CHOMAGE_TAUX_REF)
        assert dom_min <= params['montant']['min'] <= params['montant']['max'] <= dom_max
        # Le défaut est atteignable sur la grille du curseur public.
        pas = params['montant']['step']
        crans = (params['montant']['valeur_defaut'] - params['montant']['min']) / pas
        assert crans == pytest.approx(round(crans), abs=1e-9)

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
        """k ∈ [1,29 ; 1,96] : l'enveloppe de l'estimateur par coefficients de
        concentration sur DREES 1368 × Dares 53 (le trou des 71 % « ni-ni »
        porte la largeur). Revue passe 1 : PAS [1,3 ; 2,2] — cette fourchette
        mélangeait le plancher de l'estimateur corrigé et le plafond de
        l'estimateur ÉCARTÉ, et aurait laissé passer k = 2,0 que M35 écarte
        nommément. Sortir de la fourchette = nouvelle source, pas une dérive."""
        assert 1.29 <= GINI_DUREE_SURPOIDS <= 1.96

    def test_la_regle_montant_est_la_source_unique_du_par_euro(self):
        """GINI_ALLOC_PAR_MD_EUR = 0,004/5 (OFCE 2023) : le canal durée
        s'exprime en multiple de la règle montant — réviser l'une propage
        l'autre."""
        assert GINI_ALLOC_PAR_MD_EUR == pytest.approx(0.004 / 5)

    def test_couper_six_mois_emet_k_fois_la_regle_montant(self):
        """18 → 12 mois à taux de référence : gini = k × 0,0008 × (6 × 0,75)
        — le même euro, pesé k fois plus (population fin de droits).
        AVANT recalage : 0,002 (k implicite 0,556)."""
        gini = _chomage_gini({'taux_remplacement': 0.60, 'duree': 12,
                              'degressivite': False})
        attendu = (GINI_DUREE_SURPOIDS * GINI_ALLOC_PAR_MD_EUR
                   * 6 * COUT_CHOMAGE_MARGINAL_MOIS_MD)
        assert gini == pytest.approx(attendu, rel=1e-9)

    def test_le_gini_duree_suit_le_taux_comme_le_canal_euro(self):
        """Constat 23 (bloquant) : les euros du Gini sont LES MÊMES euros que
        le canal € (delta_duree porte × taux/0,60 depuis v0.6.3). À taux
        45 %, la composante durée du Gini est donc × 0,75."""
        gini_duree_seul = (
            _chomage_gini({'taux_remplacement': 0.45, 'duree': 12,
                           'degressivite': False})
            - _chomage_gini({'taux_remplacement': 0.45, 'duree': 18,
                             'degressivite': False}))
        attendu = (GINI_DUREE_SURPOIDS * GINI_ALLOC_PAR_MD_EUR
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
        reel_par_md = (GINI_IMPACT_SCALE * GINI_DUREE_SURPOIDS
                       * GINI_ALLOC_PAR_MD_EUR)
        assert reel_par_md <= ASU_GINI_BORNE_PAR_MD_EUR

    @staticmethod
    def _c_are(rang_moyen_d6_d10):
        """C = 2·F̄ − 1 sur les parts publiées DREES E&R n° 1368, graphique 1
        (personnes en ménages ARE) : D1 13 % (rang 0,05), D2 13 % (0,15),
        bloc D3-D5 37 % (rang moyen 0,35), D6-D10 37 % (rang moyen r,
        paramétré — seule grandeur non publiée de la recette)."""
        f_bar = (0.13 * 0.05 + 0.13 * 0.15 + 0.37 * 0.35
                 + 0.37 * rang_moyen_d6_d10)
        return 2 * f_bar - 1

    def test_le_c_implicite_du_canal_duree_reste_arithmetiquement_valide(self):
        """Contrainte fine (contre-vérification du constat 24) : le surpoids k
        s'interprète comme un coefficient de concentration implicite
        C_durée = G − k × (G − C_ARE), qui doit rester ≥ −1 (un transfert ne
        peut pas être plus concentré que « tout au premier centile »). À
        k = 1,6 : C_durée ≈ −0,39, cohérent avec l'estimation indépendante
        des déciles DREES pour le mix fin-de-droits (−0,27 à −0,49).
        La recette de C_ARE est EXÉCUTÉE (helper _c_are), sa sensibilité au
        rang moyen r de D6-D10 est ASSERTÉE (pas une prose qui périme) — et
        l'invariant tient sur TOUTE la plage de sensibilité, pas au seul
        point central. C_ARE ne dépend pas de GINI_BASE ; seul k_max en
        dépend."""
        # La constante nommée reproduit la recette au point central r = 0,75.
        assert GINI_C_ARE == pytest.approx(self._c_are(0.75), abs=0.001)
        # Sensibilité CALCULÉE (C = 2F̄−1 est croissant en r) : r 0,70 →
        # −0,171 ; r 0,80 → −0,097. NB : la revue adverse annonçait en prose
        # −0,078/−0,226 avec la direction inversée — c'est PRÉCISÉMENT ce
        # qu'une recette exécutée attrape et qu'une prose laisse passer.
        assert self._c_are(0.70) == pytest.approx(-0.171, abs=0.001)
        assert self._c_are(0.80) == pytest.approx(-0.097, abs=0.001)
        # Invariant arithmétique sur toute la plage de sensibilité :
        # C implicite ≥ −1 ⟺ k ≤ (1+G)/(G − C_ARE) (k_max 2,80 à r = 0,70 ;
        # 3,04 à 0,75 ; 3,33 à 0,80 — le pire cas reste > 2,2, la borne
        # haute de la fourchette testée).
        for r in (0.70, 0.75, 0.80):
            c_implicite = GINI_BASE - GINI_DUREE_SURPOIDS * (GINI_BASE - self._c_are(r))
            assert c_implicite >= -1.0
        c_central = GINI_BASE - GINI_DUREE_SURPOIDS * (GINI_BASE - GINI_C_ARE)
        assert c_central == pytest.approx(-0.39, abs=0.02)


# ---------------------------------------------------------------------------
# BUG constat 27 — dégressivité : plus de free lunch Gini
# ---------------------------------------------------------------------------

class TestDegressiviteGini:
    def test_la_degressivite_aggrave_le_gini_d_une_coupe(self):
        """Une coupe avec dégressivité retire 15 % d'allocations EN PLUS : ces
        euros passent au Gini comme à la dépense, au PA et à la compétitivité
        — structurellement, le facteur étant dans les euros eux-mêmes.
        AVANT fix : Gini identique avec et sans."""
        avec = _chomage_gini({'taux_remplacement': 0.50, 'duree': 18,
                              'degressivite': True})
        sans = _chomage_gini({'taux_remplacement': 0.50, 'duree': 18,
                              'degressivite': False})
        assert avec == pytest.approx(
            CHOMAGE_DEGRESSIVITE_FACTEUR_COUPE * sans, rel=1e-9)

    def test_la_degressivite_attenue_le_gini_d_une_hausse(self):
        """Symétrique : une hausse dégressive verse 15 % de moins — son
        bénéfice distributif est atténué d'autant (× 0,85)."""
        avec = _chomage_gini({'taux_remplacement': 0.70, 'duree': 18,
                              'degressivite': True})
        sans = _chomage_gini({'taux_remplacement': 0.70, 'duree': 18,
                              'degressivite': False})
        assert avec == pytest.approx(
            CHOMAGE_DEGRESSIVITE_FACTEUR_HAUSSE * sans, rel=1e-9)

    def test_tous_les_canaux_en_euros_portent_le_facteur(self):
        """Propriété générique (revue Altitude) : le facteur étant DANS les
        euros, dépense, PA et compétitivité valent exactement facteur × leur
        valeur sans dégressivité — c'est ce qui attraperait un futur canal €
        branché en amont du scaling. (Cas à signe unique : une coupe pure.)"""
        params = {'taux_remplacement': 0.50, 'duree': 18}
        avec = chomage_impacts({**params, 'degressivite': True})
        sans = chomage_impacts({**params, 'degressivite': False})
        f = CHOMAGE_DEGRESSIVITE_FACTEUR_COUPE
        assert avec['depenses'] == pytest.approx(f * sans['depenses'], rel=1e-9)
        assert avec['pouvoir_achat'] == pytest.approx(
            f * sans['pouvoir_achat'], rel=1e-9)
        assert avec['competitivite'] == pytest.approx(
            f * sans['competitivite'], rel=1e-9)

    def test_signes_mixtes_chaque_canal_recoit_son_propre_facteur(self):
        """Revue passe 1 : taux ↑ + durée ↓ (configuration politique banale) —
        le facteur se choisit PAR CANAL sur le signe de SES euros, pas sur la
        somme. Choisi sur la somme, le canal minoritaire recevait le facteur
        INVERSE des constantes et le Gini sautait de ~26 % au point où la
        somme change de signe. Ici : la hausse de taux est atténuée (× 0,85),
        la coupe de durée approfondie (× 1,15), chacun selon sa direction."""
        params = {'taux_remplacement': 0.70, 'duree': 12}
        avec = chomage_impacts({**params, 'degressivite': True})
        sans_m = chomage_ds({'taux_remplacement': 0.70, 'duree': 18,
                             'degressivite': False})       # € du canal taux seul
        sans_d = chomage_ds({'taux_remplacement': 0.70, 'duree': 12,
                             'degressivite': False}) - sans_m  # € durée seuls
        attendu_ds = (CHOMAGE_DEGRESSIVITE_FACTEUR_HAUSSE * sans_m
                      + CHOMAGE_DEGRESSIVITE_FACTEUR_COUPE * sans_d)
        assert chomage_ds({**params, 'degressivite': True}) == pytest.approx(
            attendu_ds, rel=1e-9)
        attendu_gini = (GINI_ALLOC_PAR_MD_EUR
                        * (-CHOMAGE_DEGRESSIVITE_FACTEUR_HAUSSE * sans_m
                           - GINI_DUREE_SURPOIDS
                           * CHOMAGE_DEGRESSIVITE_FACTEUR_COUPE * sans_d))
        assert avec['gini'] == pytest.approx(attendu_gini, rel=1e-9)

    def test_l_incitation_emploi_s_ajoute_au_canal_duree(self):
        """Revue passe 1 : l'ancienne branche ÉCRASAIT le canal durée —
        durée 36 + dégressivité basculait de +0,15 à −0,15 pt de chômage
        (0,30 pt de swing sur un booléen). Désormais additive."""
        seul = chomage_impacts({'taux_remplacement': 0.60, 'duree': 36,
                                'degressivite': False})['chomage']
        combine = chomage_impacts({'taux_remplacement': 0.60, 'duree': 36,
                                   'degressivite': True})['chomage']
        assert seul == pytest.approx(0.0015, rel=1e-9)
        assert combine == pytest.approx(seul - 0.0015, rel=1e-9)


class TestDeuxPerimetres:
    def test_la_categorie_baseline_reste_distincte_de_la_base_du_canal_taux(self):
        """Revue Altitude : « deux périmètres = deux constantes » était porté
        par un commentaire — un futur /simplify aurait pu fusionner 36,6 et
        40. La catégorie de dépense baseline (régime ENTIER : allocations +
        aides + points retraite + activité partielle ≈ 39,4) majore
        structurellement la base ∝ allocation du canal taux ; l'écart ≈ les
        lignes exclues par assiette (points retraite 2,43 + forfaitaires)."""
        from budget_simulator.constants import CHOMAGE_DEPENSE_BASELINE_MD
        assert CHOMAGE_DEPENSE_BASELINE_MD > CHOMAGE_MONTANT_REF_MD
        ecart = CHOMAGE_DEPENSE_BASELINE_MD - CHOMAGE_MONTANT_REF_MD
        assert ecart == pytest.approx(2.43 + 0.24 + 0.07 + 0.06 + 0.65, abs=0.6)
