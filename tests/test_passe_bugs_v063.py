"""Passe v0.6.3 — 2 bugs vérifiés (30/08/2026), tests-propriétés AVANT fix.

BUG 1 — chômage : la durée d'indemnisation était comptée DEUX FOIS dans
``_apply_chomage_alloc`` : une fois DANS ``montant`` (× duree/18) puis une
seconde fois via ``delta_duree`` additif → coût marginal ~2,89 Md€ par mois
de durée, contre ~0,75 Md€/an réel (ancre Unédic — le marginal est très
inférieur au moyen 40/18 ≈ 2,2 car seule une minorité d'allocataires épuise
ses droits). Contrat post-fix : le canal TAUX (montant) et le canal DURÉE
(coût marginal sourcé ``COUT_CHOMAGE_MARGINAL_MOIS_MD``, constants.py) sont
ORTHOGONAUX ; la durée ne passe QUE par le canal marginal.

BUG 2 — fraude sociale : récupération plafonnée (cap IGAS 8 Md€) mais budget
de contrôle linéaire → au-delà du point de saturation (effort ≈ 0,435 à
plein phasing), chaque euro de contrôle supplémentaire coûtait sans rien
récupérer : RN/LR à effort 1,0 recevaient ~1,5 Md€/an de MOINS que LFI à
0,5. Même famille que la non-monotonie de l'audit Thierry (v0.6.0).
Contrat post-fix : le budget ENGAGÉ sature avec le gisement récupérable
(l'excédent n'est pas dépensé) → le solde net est FAIBLEMENT MONOTONE en
l'effort, strictement croissant sous saturation.
"""
import pytest

from budget_simulator.constants import COUT_CHOMAGE_MARGINAL_MOIS_MD
from budget_simulator.simulator import BudgetSimulatorV45

_GDP, _INFLATION, _UNEMP = 3000.0, 0.02, 0.075


def _chomage_ds(params):
    sim = BudgetSimulatorV45(periods=10, mesures={'chomage_alloc': params})
    ds, _, _ = sim._apply_chomage_alloc(
        {}, params, 2027, _GDP, _INFLATION, _UNEMP)
    return ds


def _fraude_ds(params, year, mesures_extra=None):
    mesures = {'fraude_sociale': params, **(mesures_extra or {})}
    sim = BudgetSimulatorV45(periods=10, mesures=mesures)
    ds, _, _ = sim._apply_fraude_sociale(
        {}, params, year, _GDP, _INFLATION, _UNEMP)
    return ds


# ---------------------------------------------------------------------------
# BUG 1 — chômage : orthogonalité taux / durée, plus de double comptage
# ---------------------------------------------------------------------------

class TestChomageDuree:
    def test_l_ancre_marginale_est_dans_la_fourchette_sourcee(self):
        """La constante vit dans constants.py (source unique) et reste dans
        la fourchette sourcée Unédic (chiffrage direct 4,5 Md€/6 mois = 0,75 ;
        routes stock et consommation : 0,70 et 0,67) — un recalage hors
        fourchette doit être un acte conscient (nouvelle source), pas une
        dérive."""
        assert 0.65 <= COUT_CHOMAGE_MARGINAL_MOIS_MD <= 0.85

    def test_un_mois_de_plus_coute_le_marginal_pas_le_moyen(self):
        """+1 mois à taux de référence = exactement l'ancre marginale.
        AVANT fix : 40/18 + 12/18 ≈ 2,89 Md€ (double comptage)."""
        base = _chomage_ds({'taux_remplacement': 0.60, 'duree': 18, 'degressivite': False})
        plus1 = _chomage_ds({'taux_remplacement': 0.60, 'duree': 19, 'degressivite': False})
        assert plus1 - base == pytest.approx(COUT_CHOMAGE_MARGINAL_MOIS_MD, rel=1e-9)

    def test_la_duree_ne_passe_que_par_le_canal_marginal(self):
        """À taux de référence, +12 mois = 12 × marginal, rien d'autre."""
        ds = _chomage_ds({'taux_remplacement': 0.60, 'duree': 30, 'degressivite': False})
        assert ds == pytest.approx(12 * COUT_CHOMAGE_MARGINAL_MOIS_MD, rel=1e-9)

    def test_le_canal_taux_est_inchange_par_le_fix(self):
        """À durée de référence, le canal taux garde sa base 40 Md€/60 %."""
        ds = _chomage_ds({'taux_remplacement': 0.70, 'duree': 18, 'degressivite': False})
        assert ds == pytest.approx(40 * (0.70 / 0.60 - 1), rel=1e-9)

    def test_interaction_le_mois_marginal_suit_le_taux(self):
        """Un mois de droits à taux 70 % coûte proportionnellement plus
        qu'à 60 % (les allocations versées ce mois-là sont plus élevées)."""
        ds = _chomage_ds({'taux_remplacement': 0.70, 'duree': 24, 'degressivite': False})
        attendu = 40 * (0.70 / 0.60 - 1) \
            + 6 * COUT_CHOMAGE_MARGINAL_MOIS_MD * (0.70 / 0.60)
        assert ds == pytest.approx(attendu, rel=1e-9)

    def test_symetrie_reduire_la_duree_economise_le_marginal(self):
        """18→12 mois = −6 × marginal (symétrie stricte du canal durée)."""
        ds = _chomage_ds({'taux_remplacement': 0.60, 'duree': 12, 'degressivite': False})
        assert ds == pytest.approx(-6 * COUT_CHOMAGE_MARGINAL_MOIS_MD, rel=1e-9)

    def test_legacy_defaut_reste_neutre(self):
        """Le défaut config {'montant': 40, 'duree': 18} vaut zéro delta."""
        ds = _chomage_ds({'montant': 40, 'duree': 18, 'degressivite': False})
        assert ds == pytest.approx(0.0, abs=1e-12)


def _chomage_impacts(params):
    sim = BudgetSimulatorV45(periods=10, mesures={'chomage_alloc': params})
    _, _, impacts = sim._apply_chomage_alloc(
        {}, params, 2027, _GDP, _INFLATION, _UNEMP)
    return impacts


class TestChomagePouvoirAchatDuree:
    """v0.6.3 : la fin du double comptage avait laissé le pouvoir d'achat
    SANS canal durée (le Gini a gini_duree, le PA n'avait plus rien) — or
    couper des mois de droits est un choc de revenu réel pour les ~30 %
    d'entrants qui épuisent leurs droits (Unédic ex-post 18/12/2025 p. 10-11).
    Le PA suit désormais le canal € TOTAL, même règle INSEE (−0,002 / 5 Md€)."""

    def test_couper_la_duree_frappe_le_pouvoir_d_achat(self):
        """18→12 mois à taux constant : PA = 0,002 × (−4,5)/5 = −0,0018
        (AVANT le fix v0.6.3 du double comptage : −0,0053 gonflé ;
        APRÈS le fix mais AVANT ce patch : 0, canal disparu)."""
        pa = _chomage_impacts({'taux_remplacement': 0.60, 'duree': 12,
                               'degressivite': False})['pouvoir_achat']
        assert pa == pytest.approx(0.002 * (-6 * 0.75) / 5, rel=1e-9)

    def test_allonger_la_duree_est_symetrique(self):
        pa = _chomage_impacts({'taux_remplacement': 0.60, 'duree': 24,
                               'degressivite': False})['pouvoir_achat']
        assert pa == pytest.approx(0.002 * (6 * 0.75) / 5, rel=1e-9)

    def test_le_canal_taux_du_pa_est_inchange(self):
        """À durée de référence, la formule est bit-identique à l'ancienne
        −0,002 × (40 − montant)/5 : aucun scénario taux-seul ne bouge."""
        pa = _chomage_impacts({'taux_remplacement': 0.55, 'duree': 18,
                               'degressivite': False})['pouvoir_achat']
        montant = 40 * (0.55 / 0.60)
        assert pa == pytest.approx(-0.002 * (40 - montant) / 5, rel=1e-9)

    def test_le_gini_duree_est_conserve_sans_double_comptage(self):
        """gini = gini_montant (taux seul) + gini_duree — la durée ne passe
        plus par montant, donc plus par gini_montant (facteur 6,3 d'avant)."""
        gini = _chomage_impacts({'taux_remplacement': 0.60, 'duree': 12,
                                 'degressivite': False})['gini']
        assert gini == pytest.approx(0.002 * (18 - 12) / 6, rel=1e-9)


# ---------------------------------------------------------------------------
# BUG 2 — fraude sociale : solde net faiblement monotone en l'effort
# ---------------------------------------------------------------------------

class TestFraudeMonotone:
    @pytest.mark.parametrize("year", [2026, 2027, 2029, 2032])
    def test_le_solde_net_est_faiblement_monotone_en_l_effort(self, year):
        """Plus d'effort anti-fraude ⇒ jamais un solde net pire.
        AVANT fix : au-delà d'effort ≈ 0,435 (plein phasing), ds REMONTAIT
        (budget linéaire, récupération plafonnée)."""
        grid = [i / 20 for i in range(21)]  # 0.00 … 1.00
        prev = None
        for effort in grid:
            ds = _fraude_ds({'effort': effort}, year)
            if prev is not None:
                assert ds <= prev + 1e-9, (
                    f"non-monotonie à effort={effort:.2f} (année {year}) : "
                    f"ds={ds:.4f} > {prev:.4f}")
            prev = ds

    def test_strictement_croissant_sous_la_saturation(self):
        """Sous le point de saturation du gisement, chaque cran d'effort
        rapporte strictement (pas d'aplatissement artificiel)."""
        ds_01 = _fraude_ds({'effort': 0.1}, 2030)
        ds_03 = _fraude_ds({'effort': 0.3}, 2030)
        assert ds_03 < ds_01 - 1e-9

    def test_au_dela_de_la_saturation_pas_de_penalite(self):
        """RN/LR (effort 1,0) ne reçoivent plus MOINS que LFI (0,5) : au-delà
        de la saturation du gisement IGAS, le solde est identique — le budget
        de contrôle excédentaire n'est pas engagé."""
        ds_05 = _fraude_ds({'effort': 0.5}, 2030)
        ds_10 = _fraude_ds({'effort': 1.0}, 2030)
        assert ds_10 == pytest.approx(ds_05, abs=1e-9)

    def test_le_budget_engage_sature_avec_le_gisement(self):
        """À plein phasing, le solde net vaut −(cap IGAS) + budget saturant :
        −8 + 8/(8,75 × 0,70) ≈ −6,69 Md€ — pas −8 + 3 = −5 (budget plein)."""
        ds = _fraude_ds({'effort': 1.0}, 2030)
        budget_saturant = 8.0 / (8.75 * 0.70)
        assert ds == pytest.approx(-8.0 + budget_saturant, rel=1e-9)

    def test_annees_de_montee_en_charge_comportement_inchange(self):
        """En 2026 (phasing 0,25), le gisement n'est pas saturable même à
        effort 1,0 (budget saturant ≈ 5,2 > 3) : le calcul d'avant-fix reste
        valable au bit près — le fix ne touche QUE la zone saturée."""
        ds = _fraude_ds({'effort': 1.0}, 2026)
        attendu = -(3.0 * 8.75 * 0.25 * 0.70) + 3.0
        assert ds == pytest.approx(attendu, rel=1e-9)

    @pytest.mark.parametrize("year", [2027, 2030])
    def test_monotonie_preservee_avec_asu_active(self, year):
        """L'anti-double-comptage ASU réduit le gisement récupérable — la
        monotonie doit tenir aussi dans ce régime (budget saturant réduit)."""
        asu = {'asu': {'asu_activation': 1}}
        grid = [i / 10 for i in range(11)]
        prev = None
        for effort in grid:
            ds = _fraude_ds({'effort': effort}, year, mesures_extra=asu)
            if prev is not None:
                assert ds <= prev + 1e-9, (
                    f"non-monotonie sous ASU à effort={effort:.1f} ({year})")
            prev = ds

    def test_asu_reduit_toujours_strictement_les_economies(self):
        """Le contrat ASU↔fraude (option A) survit au fix : ASU active ⇒
        solde strictement moins favorable qu'ASU inactive, à effort saturant."""
        sans = _fraude_ds({'effort': 1.0}, 2030)
        avec = _fraude_ds({'effort': 1.0}, 2030,
                          mesures_extra={'asu': {'asu_activation': 1}})
        assert avec > sans + 1e-9
