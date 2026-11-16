"""Hausse du SMIC : les cinq postes du Trésor, chacun traité selon sa nature (lot SMIC, équation).

Arbitrage du mainteneur (16/11/2026) : le levier ``smic`` reprend les effets d'une hausse de 1 % du
SMIC sur les finances publiques publiés par le groupe d'experts sur le SMIC (rapport 2017, tableau 9,
PDF p. 82, modèle Saphir de la DG Trésor), mis à l'échelle de l'année et de la hausse. Chaque poste
garde sa nature :

- la paie publique passe au canal des rémunérations publiques, donc au traitement des transferts pour
  la croissance (lot 5b) et à l'effet prix sur le PIB en valeur publié (lot 5d) ;
- la baisse des prestations est un transfert (le SMIC est un levier de transfert) ;
- les prélèvements des salariés et l'impôt sur le revenu sont des impôts, les allègements de charges
  des employeurs une baisse d'impôts : un seul flux de recettes, au coefficient et au profil des
  impôts (le même coefficient en hausse et en baisse, ce que vérifie un test ci-dessous).

Le coefficient propre de 0,15 appliqué au solde du SMIC disparaît : ``smic`` sort de
``MESURES_MULTIPLICATEUR_NET``. La fraude fiscale garde le sien, au bit près. L'effet direct sur le
chômage (0,025 point par point de hausse) est conservé. Le revenu des ménages vient de la même source
(tableau 8, PDF p. 81) : +690 M€ par point, sans double compte.
"""
import pytest

from budget_simulator.constants import (
    MULT_BAISSE_IMPOTS,
    MULT_HAUSSE_IMPOTS,
    PART_NETTE_REMUNERATIONS_APU,
    PIB_BASE_2025_MD_EUR,
    SALAIRES_BRUTS_2017_MD,
    SALAIRES_BRUTS_2025_MD,
    SMIC_BRUT_MENSUEL_REFERENCE_EUR,
    SMIC_TRESOR_REVENU_BRUT_PAR_POINT_M_EUR_2017,
    SMIC_TRESOR_REVENU_DISPONIBLE_PAR_POINT_M_EUR_2017,
    SMIC_TRESOR_SOLDE_PAR_POINT_M_EUR_2017,
)
from budget_simulator.engine.growth import flux_par_levier
from budget_simulator.engine.rdb import effet_revenu_md_eur
from budget_simulator.simulator import BudgetSimulatorV45, FiscalMultipliers

S = BudgetSimulatorV45
T = SMIC_TRESOR_SOLDE_PAR_POINT_M_EUR_2017
MONTANT = 1950.0


class _Releve(BudgetSimulatorV45):
    """Le moteur complet, qui garde chaque appel du levier : année, PIB de l'appel, sortie."""

    def _apply_smic(self, measure, params, year, gdp, *args):
        sortie = super()._apply_smic(measure, params, year, gdp, *args)
        self.appels_smic.append((year, gdp, sortie))
        return sortie


def _simuler(mesures, annee_debut=None):
    sim = _Releve(periods=10, mesures=mesures, annee_debut=annee_debut)
    sim.appels_smic = []
    sim.simulate()
    return sim


def _hausse_en_points(sim, montant):
    """Hausse en points de pourcentage, mode historique : contre la référence (tests/test_smic_reference_datee.py)."""
    return 100.0 * (montant - SMIC_BRUT_MENSUEL_REFERENCE_EUR) / SMIC_BRUT_MENSUEL_REFERENCE_EUR


def _echelle(gdp):
    """M€ de 2017 par point de hausse → Md€ de l'année : salaires bruts 2017 → 2025, puis PIB nominal."""
    return SALAIRES_BRUTS_2025_MD / SALAIRES_BRUTS_2017_MD * gdp / PIB_BASE_2025_MD_EUR / 1000.0


def test_les_cinq_postes_du_tableau_9_et_leur_total():
    """Les sources, telles que relues (PDF p. 82 et p. 81) : le total du tableau 9 vaut −240 M€ par point,
    le revenu disponible du tableau 8 = revenu brut − prélèvements des salariés − impôt sur le revenu
    − baisse des prestations."""
    assert T == {'cotisations_employeurs_nettes_des_allegements': -400.0,
                 'prelevements_des_salaries': 240.0, 'paie_publique': -260.0,
                 'prestations': 110.0, 'impot_sur_le_revenu': 70.0}
    assert sum(T.values()) == -240.0
    assert (SMIC_TRESOR_REVENU_BRUT_PAR_POINT_M_EUR_2017 - T['prelevements_des_salaries']
            - T['impot_sur_le_revenu'] - T['prestations']) == SMIC_TRESOR_REVENU_DISPONIBLE_PAR_POINT_M_EUR_2017
    assert (SALAIRES_BRUTS_2017_MD, SALAIRES_BRUTS_2025_MD) == (880.657, 1157.166)


def test_flux_budgetaires_mis_a_l_echelle_de_l_annee_et_de_la_hausse():
    """Chaque année du levier : dépense = paie publique + baisse des prestations, recette = prélèvements
    des salariés + impôt sur le revenu + allègements (négatifs), chacun = poste × échelle × hausse."""
    sim = _simuler({'smic': {'montant_brut': MONTANT}})
    assert len(sim.appels_smic) == 10
    for year, gdp, (dep, rec, imp) in sim.appels_smic:
        k, h = _echelle(gdp), _hausse_en_points(sim, MONTANT)
        paie = -T['paie_publique'] * k * h
        prestations = -T['prestations'] * k * h
        recettes = (T['prelevements_des_salaries'] + T['impot_sur_le_revenu']
                    + T['cotisations_employeurs_nettes_des_allegements']) * k * h
        assert dep == pytest.approx(paie + prestations, rel=1e-12), year
        assert rec == pytest.approx(recettes, rel=1e-12), year
        assert rec - dep == pytest.approx(-240.0 * k * h, rel=1e-12), year
        assert imp['menages']['remunerations_publiques'] == pytest.approx(paie, rel=1e-12)
        assert imp['menages']['prestations'] == pytest.approx(prestations, rel=1e-12)


def test_la_paie_publique_ne_compte_que_l_ecart_au_point_d_indice():
    """Anti-double compte conservé : un point d'indice relevé de p % couvre déjà p points de la hausse
    pour les agents publics ; seule la paie publique en dépend."""
    pi = 2.0
    sim = _simuler({'smic': {'montant_brut': MONTANT}, 'fonction_publique': {'point_indice': pi}})
    for year, gdp, (dep, rec, imp) in sim.appels_smic:
        k, h = _echelle(gdp), _hausse_en_points(sim, MONTANT)
        assert imp['menages']['remunerations_publiques'] == pytest.approx(
            -T['paie_publique'] * k * (h - pi), rel=1e-12)
        assert dep == pytest.approx(-T['paie_publique'] * k * (h - pi) - T['prestations'] * k * h, rel=1e-12)


def test_revenu_des_menages_du_tableau_8_sans_double_compte():
    """Le revenu disponible porté par les canaux ménages = +690 M€ par point mis à l'échelle (tableau 8) :
    salaires nets (brut − prélèvements des salariés), baisse des prestations, impôt sur le revenu ; la part
    des agents publics passe par la règle du moteur (part nette du coût employeur), le reste est le salaire
    net du privé. Les prélèvements des salariés ne sont comptés qu'une fois (dans le salaire net)."""
    sim = _simuler({'smic': {'montant_brut': MONTANT}})
    for year, gdp, (dep, rec, imp) in sim.appels_smic:
        k, h = _echelle(gdp), _hausse_en_points(sim, MONTANT)
        canaux = imp['menages']
        assert effet_revenu_md_eur(canaux) == pytest.approx(
            SMIC_TRESOR_REVENU_DISPONIBLE_PAR_POINT_M_EUR_2017 * k * h, rel=1e-12)
        assert canaux['prelevements_directs'] == pytest.approx(T['impot_sur_le_revenu'] * k * h, rel=1e-12)
        assert canaux['salaires_prives'] == pytest.approx(
            (SMIC_TRESOR_REVENU_BRUT_PAR_POINT_M_EUR_2017 - T['prelevements_des_salaries']
             + PART_NETTE_REMUNERATIONS_APU * T['paie_publique']) * k * h, rel=1e-12)
        assert canaux['prelevements_indirects'] == 0.0


def test_l_effet_direct_sur_le_chomage_est_conserve():
    """0,025 point de chômage par point de hausse, une fois, l'année d'origine du levier."""
    sim = _simuler({'smic': {'montant_brut': MONTANT}})
    (premiere, *suivantes) = sim.appels_smic
    assert premiere[2][2]['chomage'] == pytest.approx(_hausse_en_points(sim, MONTANT) / 100 * 0.025, rel=1e-12)
    assert all(appel[2][2]['chomage'] == 0.0 for appel in suivantes)


def test_le_smic_n_a_plus_de_coefficient_propre():
    """``smic`` est multiplié flux par flux ; ``get_multiplier`` ne lui réserve plus aucun traitement."""
    assert FiscalMultipliers.MESURES_MULTIPLICATEUR_NET == frozenset({'fraude_fiscale'})
    fm = FiscalMultipliers()
    compositions = ({'depenses': 1.0, 'recettes': 0.0, 'investissement': 0.0, 'transferts': 1.0},
                    {'depenses': 0.0, 'recettes': 1.0, 'investissement': 0.0})
    etats = ({'output_gap': 0.0, 'unemployment_gap': 0.0, 'debt_ratio': 1.15, 'interest_rate': 0.02},
             {'output_gap': -0.03, 'unemployment_gap': 0.02, 'debt_ratio': 0.9, 'interest_rate': 0.02},
             {'output_gap': 0.03, 'unemployment_gap': -0.02, 'debt_ratio': 1.2, 'interest_rate': 0.02})
    for sens in ('consolidation', 'expansion'):
        for composition in compositions:
            for etat in etats:
                assert fm.get_multiplier(sens, composition, etat, 2030, 'smic') == \
                    fm.get_multiplier(sens, composition, etat, 2030, None)


def test_fraude_fiscale_garde_son_coefficient_propre_au_bit():
    """La fraude fiscale reste multipliée sur son solde, à −0,40 × ajustement conjoncturel (× 0,95 au-delà
    de 110 % de dette), quelle que soit la composition."""
    fm = FiscalMultipliers()
    for sens in ('consolidation', 'expansion'):
        for composition in ({'depenses': 0.0, 'recettes': 1.0, 'investissement': 0.0},
                            {'depenses': 1.0, 'recettes': 0.0, 'investissement': 1.0}):
            for etat in ({'output_gap': 0.0, 'unemployment_gap': 0.0, 'debt_ratio': 1.15, 'interest_rate': 0.02},
                         {'output_gap': -0.03, 'unemployment_gap': 0.02, 'debt_ratio': 0.9, 'interest_rate': 0.02}):
                attendu = -0.40 * fm._facteur_conjoncturel(etat)
                if etat['debt_ratio'] > 1.10:
                    attendu *= fm.adjustments['high_debt']
                assert fm.get_multiplier(sens, composition, etat, 2030, 'fraude_fiscale') == attendu
    impacts = {'fraude_fiscale': {'depenses': 0.2, 'recettes': 3.0}}
    assert flux_par_levier(impacts, FiscalMultipliers.MESURES_MULTIPLICATEUR_NET,
                           leviers_de_transfert=S.TRANSFER_MEASURES,
                           prestations_non_reclassees=S.PRESTATIONS_NON_RECLASSEES) == {
        ('fraude_fiscale', 'solde'): 2.8}


def test_chaque_flux_du_smic_prend_le_coefficient_et_le_profil_de_sa_nature():
    """Dans le moteur complet : la paie publique et la baisse des prestations au traitement des
    transferts (coefficient et profil), la recette au coefficient et au profil des impôts."""
    sim = _simuler({'smic': {'montant_brut': MONTANT}})
    base = sim.multipliers.base_multipliers
    vus, facteurs = set(), {}
    for (year, m_id, canal, sens), (delta, k, profil) in sim._fiscal_impulses.items():
        if m_id != 'smic':
            continue
        vus.add(canal)
        assert canal in {'remunerations', 'depenses', 'recettes'}, canal
        if canal == 'recettes':
            assert profil == S.DECAY_PROFILE_TAXES
            famille = 'tax_based' if sens == 'consolidation' else 'tax_cuts'
        else:
            assert profil == S.DECAY_PROFILE_TRANSFERS
            famille = 'transferts'
        # Même année : k / coefficient de base de la famille = le même ajustement pour tous les flux.
        facteurs.setdefault(year, []).append(k / abs(base[sens][famille]))
    assert vus == {'remunerations', 'depenses', 'recettes'}
    assert facteurs
    for year, valeurs in facteurs.items():
        assert max(valeurs) == pytest.approx(min(valeurs), rel=1e-12), (year, valeurs)


def test_premisse_un_seul_flux_de_recettes():
    """Prélèvements des salariés (hausse d'impôts) et allègements des employeurs (baisse de charges)
    forment un seul flux de recettes : ce n'est exact que parce que la hausse et la baisse d'impôts ont le
    même coefficient. Si l'un des deux change, il faut deux flux."""
    assert MULT_HAUSSE_IMPOTS == MULT_BAISSE_IMPOTS
