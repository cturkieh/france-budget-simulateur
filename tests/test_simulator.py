import logging
from unittest.mock import patch
from budget_simulator import BudgetSimulatorV45, FiscalMultipliers, EconomicValidator

# Fixtures 'simulator' and 'multipliers' are defined in conftest.py

def test_get_multiplier_consolidation(multipliers):
    economic_state = {
        'output_gap': -0.02,
        'unemployment_gap': 0.02,
        'debt_ratio': 1.2,
        'interest_rate': 0.01
    }
    composition = {'recettes': 0.7, 'depenses': 0.3}
    multiplier = multipliers.get_multiplier('consolidation', composition, economic_state, year=1)
    # Weighted blend: (0.7/1.0)*(-0.50) + (0.3/1.0)*(-0.40) = -0.47
    # output_gap=-0.02 is NOT < -0.02, ug=0.02 NOT > 0.02 → no recession adj
    # high_debt (1.2 > 1.10): *0.95 → -0.47 * 0.95 = -0.4465
    expected = -0.4465
    assert abs(multiplier - expected) < 0.01, f"Expected ~{expected:.3f}, got {multiplier:.2f}"

def test_get_multiplier_expansion(multipliers):
    economic_state = {
        'output_gap': 0.021,  # >0.02 pour déclencher expansion
        'unemployment_gap': -0.011,  # < -0.01 pour déclencher expansion
        'debt_ratio': 0.9,
        'interest_rate': 0.023
    }
    composition = {'investissement': 0.6, 'recettes': 0.2, 'depenses': 0.2}
    multiplier = multipliers.get_multiplier('expansion', composition, economic_state, year=3)
    # Weighted blend: part_inv=0.6, part_transfers=max(0,0.2-0.6)=0, part_rev=0.2, total=0.8
    # base = (0.6/0.8)*1.2 + (0/0.8)*0.50 + (0.2/0.8)*0.35 = 0.90 + 0 + 0.0875 = 0.9875
    # Expansion adjustment: *0.85 = 0.8394
    # No Ricardo-Barro (debt < 1.10)
    expected = 0.9875 * 0.85  # ≈ 0.839
    assert abs(multiplier - expected) < 0.01, f"Expected {expected:.2f}, got {multiplier:.2f}"

def test_calculate_growth_austerity(simulator):
    economic_state = {
        'output_gap': -0.015,
        'unemployment_gap': 0.001,
        'effort_budgetaire': 0.034,
        'part_depenses': 0.61,
        'part_investissement': 0.0,
        'debt_ratio': 1.156,
        'unemployment': 0.076,
        'deficit_ratio': -0.054
    }
    with patch('numpy.random.normal', return_value=0):
        growth = simulator.calculate_growth(year=1, economic_state=economic_state)
    # Base + chomage_gap + debt_drag + multiplicateur (ONE-TIME si measures changed)
    # Actual formula: croissance_potentielle + 0.4*unemployment_gap - 0.008*(debt-0.9) + mult*effort
    expected_base = 0.01 + 0.4 * 0.001 - 0.008 * (1.156 - 0.9)
    assert growth < expected_base + 0.01  # Growth is reduced by consolidation
    # Vérification flexible : cherche "CHANGEMENT MESURES" + "Consolidation" dans le log
    assert any("Consolidation" in s for s in simulator.debug_logs), "Log consolidation manquant"

def test_calculate_revenues(simulator):
    growth = 0.01
    inflation = 0.01
    gdp = 2994
    year = 1
    revenues = simulator.calculate_revenues(gdp, growth, inflation, year)
    # Refonte 2026-06 : élasticité unitaire (ELASTICITE_PO_PIB=1.0, HCFP) sur la
    # croissance nominale COMPOSÉE contemporaine ; plus de plancher Y1 ni d'érosion.
    # revenues = 1545 * (1 + ((1.01*1.01)-1) * 1.0) = 1545 * 1.0201 = 1576.05
    expected = 1545 * (1 + ((1 + growth) * (1 + inflation) - 1) * 1.0)
    assert abs(revenues - expected) < 0.1

def test_validate_year():
    validator = EconomicValidator()
    year_data = {
        'Recettes/PIB %': 50,
        'Dépenses/PIB %': 60,
        'Dette/PIB %': 160,
        'Gini': 0.41,
        'Inflation %': 5,
        'Output_Gap %': 4,
        'Taux_Intérêt %': 4
    }
    violations = validator.validate_year(year_data)
    assert "ALERTE: Dette/PIB 160.0% > soutenabilité 140%" in violations

# Test pour _apply_fonction_publique (effectifs + point d'indice)
def test_apply_fonction_publique(simulator):
    measure = {'id': 'fonction_publique', 'type': 'fonction', 'cible': 'depenses'}
    params = {'effectifs': -30000, 'point_indice': -1.0}
    year = 2026
    gdp = 2994
    inflation = 0.01
    unemployment = 0.076
    delta_spending, delta_revenue, impacts = simulator._apply_fonction_publique(measure, params, year, gdp, inflation, unemployment)
    # Calcul attendu :
    # effectifs: -30000 * 60000 / 1e9 = -1.8 Md€
    # point_indice: (-1.0 / 100) * 330 = -3.3 Md€
    # Total = -5.1 Md€
    expected_spending = (-30000 * 60000 / 1e9) + (-1.0 / 100) * 330
    assert abs(delta_spending - expected_spending) < 0.1, f"Expected {expected_spending:.1f} Md€, got {delta_spending:.1f}"
    assert delta_revenue == 0
    assert 'depenses' in impacts
    assert any("FP" in s for s in simulator.debug_logs), "Log FP manquant"

# Test pour calculate_inflation (Phillips augmentée Y1, valeur exacte 0.01731)
def test_calculate_inflation(simulator):
    economic_state = {
        'output_gap': -0.015,
        'unemployment_gap': 0.001,
        'effort_budgetaire': -0.007,  # Expansion légère
        'tva_impact': 0.0071  # TVA +0.71% / PIB
    }
    simulator.inflation_precedente = 0.01  # Inflation précédente 1.0%
    with patch('numpy.random.normal', return_value=0):
        inflation = simulator.calculate_inflation(year=2, economic_state=economic_state)
    # Calcul exact (engine/inflation.py, refonte 2026-06 : intercept ×(1−ρ),
    # pass-through TVA gaté year==2 — impacts t−1 —, random patché à 0) :
    #   base       = (1-0.50)*0.015 + 0.50*0.01 + 0.35*(-0.015) = 0.00725
    #   + effort   = 0.08*abs(-0.007)                (+0.00056) = 0.00781
    #   + TVA (y2) = min(0.0071*0.3, 0.002)          (+0.002)   = 0.00981
    #   pas de seuil défla/infla, pas de rappel BCE (0.008 ≤ 0.00981 ≤ 0.020)
    expected = 0.00981
    assert abs(inflation - expected) < 0.001, f"Expected {expected}, got {inflation:.5f}"

# Test pour validate_trajectory (basé sur Status Quo : croissance moyenne 0.8%, dette 161%, Okun 10/10)
def test_validate_trajectory():
    import pandas as pd
    validator = EconomicValidator()
    # DataFrame mocké avec dette>160% pour déclencher CRITIQUE et valid=False
    df = pd.DataFrame({
        'Année': [2025] + [2025 + i for i in range(1, 11)],
        'Croissance %': [0.7] + [0.8] * 10,  # Moyenne 0.8%
        'Dette/PIB %': [115.6] + [115.6 + 4.63 * i for i in range(1, 11)],  # Fin 161.9% (>160% CRITIQUE)
        'Déficit/PIB %': [-5.11] + [-5.1 - 0.22 * i for i in range(1, 11)],  # Fin -7.30% (déficit élevé)
        'Recettes/PIB %': [51.6] + [51.6 - 0.02 * i for i in range(1, 11)],  # ~49.6%
        'Dépenses/PIB %': [56.7] + [56.7 + 0.02 * i for i in range(1, 11)],  # ~56.9%
        'Chômage %': [7.6] * 11  # Constant pour Okun cohérent
    })
    report = validator.validate_trajectory(df)
    assert report['valid'] is False  # CRITIQUE pour dette>160%
    assert "Croissance moyenne: 0.8%" in report['tests'][0]
    assert "Dette: 115.6% → 161.9%" in report['tests'][1]  # Match arrondi .1f
    assert "Test Okun: 10/10 années cohérentes" in report['tests']  # Okun dans la liste
    assert "CRITIQUE: Dette 2035 insoutenable: 161.9%" in report['critical']
    assert "Dette 162% nécessite excédent primaire >1% pour stabiliser" in report['warnings']  # 161.9 arrondi

# Test pour calculate_unemployment (basé sur Status Quo Y1 : 7.6% → 7.34%)
def test_calculate_unemployment(simulator):
    growth = 0.011  # Croissance Y1 Status Quo
    unemployment_prev = 0.076  # 7.6%
    year = 1
    unemployment = simulator.calculate_unemployment(growth, unemployment_prev, year)
    # Calcul attendu : delta_u = -0.35 * (0.011 - 0.01) + convergence vers NAIRU 7.5%
    delta_u = -0.35 * (0.011 - 0.01)
    expected = 0.94 * 0.076 + 0.06 * 0.075 + delta_u
    assert abs(unemployment - expected) < 0.001, f"Expected ~0.0734, got {unemployment:.4f}"

# Test pour calculate_interest_rate (basé sur Status Quo Y1 : taux=1.91% pour dette=115.6%)
def test_calculate_interest_rate(simulator):
    debt_ratio = 1.156  # 115.6%
    year = 1
    effort_budgetaire = 0  # Status Quo
    rate = simulator.calculate_interest_rate(debt_ratio, year, effort_budgetaire)
    # Calcul attendu : base=0.019 + progression 100-120% : base_rate + 0.005 * (1.156 - 1.0) ≈ 0.0198
    expected = 0.0191
    assert abs(rate - expected) < 0.001, f"Expected ~0.0191, got {rate:.4f}"

# Test pour calculate_growth en consolidation sévère (debt drag + cicatrice austérité activés)
def test_calculate_growth_significant_recession(simulator):
    # Recalibré : multiplicateurs moins négatifs (-0.56 base vs ancien -0.92) et effort
    # plafonné à 2% PIB → la branche stricte "Récession profonde < -0.025" n'est plus
    # déclenchable avec ces seuils (couvert par test_calculate_growth_zlb au year>3).
    # Ce test couvre la consolidation sévère significative : debt drag + cicatrice + croissance
    # nettement négative (delta -2.5pt vs potentiel +0.01).
    economic_state = {
        'output_gap': -0.05,  # < -0.02 → déclenche recession adjustment
        'unemployment_gap': -0.01,  # Négatif → contribution -0.004
        'effort_budgetaire': 0.08,  # Consolidation forte (capped 2%)
        'part_depenses': 0.3,  # part_depenses < 0.5 → pas de bonus Alesina
        'part_investissement': 0.0,
        'debt_ratio': 2.0,  # Très élevé → fort debt drag
        'unemployment': 0.08,  # < 0.09 → pas de stabilisateur chômage
        'deficit_ratio': -0.03  # > -0.04 → pas de stabilisateur déficit
    }
    with patch('numpy.random.normal', return_value=-0.01):  # Bruit négatif
        growth = simulator.calculate_growth(year=1, economic_state=economic_state)

    # Note 2026-05-07 : après triple-audit DG Trésor / COR / Bozio-Wasmer (commit c510c22),
    # la calibration produit des chocs plus modérés. Avec ces params, growth ≈ -0.018
    # (au lieu de < -0.025 avant audit). Le seuil "Récession profonde" (< -0.025) reste
    # activable avec des conditions plus extrêmes (couvert par test_calculate_growth_zlb).
    # Seuil -0.015 : conservateur vs valeur observée (-0.018), au-delà du potentiel (+0.01) =
    # delta de 2.5pt minimum vs baseline → exclut une régression où les chocs disparaissent.
    assert growth < -0.015, f"Récession significative attendue, got {growth:.4f}"
    assert any("Debt drag" in s for s in simulator.debug_logs), \
        "Debt drag activé (debt_ratio 2.0 > 0.9)"
    assert any("Cicatrice austérité" in s for s in simulator.debug_logs), \
        "Cicatrice austérité activée (effort_budgetaire 0.08 > 0.03)"

# Test pour validate_year avec taux intérêt élevé (branche >5.0% plafond BCE TPI)
def test_validate_year_high_interest():
    validator = EconomicValidator()
    year_data = {
        'Recettes/PIB %': 50,
        'Dépenses/PIB %': 60,
        'Dette/PIB %': 160,
        'Gini': 0.41,
        'Inflation %': 5,
        'Output_Gap %': 4,
        'Taux_Intérêt %': 5.5  # >5.0% plafond BCE TPI
    }
    violations = validator.validate_year(year_data)
    assert "CRITIQUE: Taux 5.5% > plafond BCE 5.0%" in violations

# Test pour simulate boucle complète (couverture de la boucle principale)
def test_simulate_full_run(default_simulator):
    """Uses default_simulator fixture (which has all base_params including croissance_2025)."""
    default_simulator.periods = 3  # Short run for speed
    with patch('numpy.random.normal', return_value=0):
        results, details, report = default_simulator.simulate()
    assert len(results) == 4  # 4 années (2025-2028)
    assert results.iloc[0]['Dette/PIB %'] > 100  # Dette initiale > 100%
    assert 'valid' in report  # Report has validation result

# Test pour calculate_expenditures (Y10 Status Quo)
def test_calculate_expenditures(simulator):
    gdp = 3966  # PIB Y10 Status Quo
    inflation = 0.022
    inflation_prev = 0.020  # part indexée sur l'inflation passée (refonte 2026-06)
    unemployment = 0.0806
    year = 10
    output_gap = -0.004
    spending = simulator.calculate_expenditures(gdp, inflation, inflation_prev, unemployment, year, output_gap)
    # Expenditures should be reasonable for Y10
    # Ratio dépenses/PIB calculé sur PIB courant (Fix 6), valeurs plus basses qu'avec PIB fixe
    assert 1500 < spending < 2200, f"Expected spending in 1500-2200 range, got {spending:.0f}"

# Test pour get_multiplier year>5 (no temporal decay in current version)
def test_get_multiplier_long_term(multipliers):
    economic_state = {
        'output_gap': 0.0,
        'unemployment_gap': 0.0,
        'debt_ratio': 1.0,
        'interest_rate': 0.023
    }
    composition = {'investissement': 0.4, 'recettes': 0.3, 'depenses': 0.3}
    multiplier = multipliers.get_multiplier('expansion', composition, economic_state, year=6)
    # Weighted blend: part_inv=0.4, part_transfers=max(0,0.3-0.4)=0, part_rev=0.3, total=0.7
    # base = (0.4/0.7)*1.2 + (0/0.7)*0.50 + (0.3/0.7)*0.35 = 0.6857 + 0 + 0.15 = 0.8357
    # No conjunctural adjustment (output_gap=0, unemployment_gap=0)
    # No Ricardo-Barro (debt < 1.10)
    expected = (0.4/0.7)*1.2 + (0.3/0.7)*0.35  # ≈ 0.836
    assert abs(multiplier - expected) < 0.01, f"Expected {expected:.2f}, got {multiplier:.2f}"

# Test pour apply_measures (somme impacts plafonnés 10% PIB)
def test_apply_measures(simulator):
    year = 2026
    spending_base = 1643.7
    revenues_base = 1554.4
    gdp = 3068.3
    inflation = 0.016
    unemployment = 0.0734
    # Mock mesures pour total impact >10% PIB (plafonné)
    simulator.mesures = {'tva_rate': {'taux': 0.25}, 'retraites': {'age_depart': 65}}  # Impacts forts
    spending, revenues, impacts = simulator.apply_measures(year, spending_base, revenues_base, gdp, inflation, unemployment)
    total_impact = abs(spending - spending_base) + abs(revenues - revenues_base)
    assert total_impact <= 0.10 * gdp  # Plafonné à 10% PIB
    assert len(impacts) >= 1  # Au moins une mesure appliquée

# Tests pour update_potential_growth — splittés en 2 cas indépendants pour éviter l'état
# partagé entre l'effet d'offre et l'hystérèse négative.
# Note 2026-05-07 : API refactorée. Le boost ne modifie plus base_params['croissance_potentielle']
# (clampé [0.007, 0.012]) mais s'accumule dans _potential_growth_bonus via le dict SUPPLY_EFFECTS
# qui scrute self.mesures (et non self._last_impacts comme avant). Sources : Bom & Ligthart (2014),
# Blanchard & Summers (1986).
def test_update_potential_growth_supply_bonus(simulator):
    """Effet d'offre supply-side : investissement structurel +10 Md€ → bonus +0.20pt après délai 3 ans.

    SUPPLY_EFFECTS['transition_invest'] : delay=3 ans, coeff=0.0020 (Bom & Ligthart 2014).
    """
    simulator.mesures = {'transition_ecologique': {'investissement': 10}}

    # T+1, T+2 : pas encore de bonus (years_active < delay=3)
    simulator.update_potential_growth(growth=0.015, year=1)
    simulator.update_potential_growth(growth=0.015, year=2)
    assert simulator._potential_growth_bonus == 0.0, \
        f"Pas de bonus avant délai 3 ans, got {simulator._potential_growth_bonus}"

    # T+3 : years_active = 3 = delay → bonus s'active
    simulator.update_potential_growth(growth=0.015, year=3)
    assert simulator._potential_growth_bonus > 0.0001, \
        f"Bonus offre activé à T+delay, got {simulator._potential_growth_bonus}"
    assert simulator._potential_growth_bonus <= 0.002, \
        f"Cap +0.20pt respecté, got {simulator._potential_growth_bonus}"
    assert any("Bonus potentiel" in s for s in simulator.debug_logs), \
        "Log bonus offre présent"


def test_update_potential_growth_hysteresis_negative(simulator):
    """Hystérèse négative : récession profonde déprécie le potentiel (Blanchard-Summers 1986).

    Test isolé pour ne pas mélanger avec le bonus supply (qui accumule dans _supply_years).
    """
    old_potential = simulator.base_params['croissance_potentielle']
    simulator.update_potential_growth(growth=-0.025, year=1)
    assert simulator.base_params['croissance_potentielle'] < old_potential, \
        "Hystérèse négative appliquée (croissance < -0.020)"
    assert any("Hystérèse négative" in s for s in simulator.debug_logs), \
        "Log hystérèse négative présent"

def test_update_potential_growth_exception_is_observable(simulator, caplog):
    """Garde supply-side : si une exception survient (inatteignable en run
    normal — re-analyse adverse 2026-05-16 — mais possible sur futur
    refactor), la dégradation doit être OBSERVABLE, pas muette.

    Vérifie le contrat d'instrumentation (point 2 du déclassement) :
    - dégradation gracieuse : pas de crash, bonus neutralisé à 0.0
    - observable : logger.error émis avec exc_info (auto-capté Sentry via
      LoggingIntegration), + log debug conservé
    """
    # Injecte une exception dans la 1ère opération du bloc try supply-side.
    def _boom():
        raise RuntimeError("supply-side défaillant (injection test)")
    simulator._get_default_values = _boom

    with caplog.at_level(logging.ERROR, logger="budget_simulator.engine.growth"):
        # Ne doit pas lever : dégradation gracieuse
        simulator.update_potential_growth(growth=0.015, year=4)

    # Bonus neutralisé (dégradation sûre)
    assert simulator._potential_growth_bonus == 0.0, \
        f"Bonus neutralisé sur exception, got {simulator._potential_growth_bonus}"

    # Observable via logger.error + exc_info (donc capté par Sentry LoggingIntegration)
    error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert error_records, "logger.error émis (non silencieux) sur exception supply-side"
    rec = error_records[0]
    assert "supply-side bonus désactivé" in rec.getMessage()
    assert rec.exc_info is not None, "exc_info présent → stacktrace capturée par Sentry"

    # Log debug conservé (traçabilité existante préservée)
    assert any("ERREUR supply-side" in s for s in simulator.debug_logs), \
        "Log debug existant conservé"


def test_calculate_growth_no_synergy_bonus(simulator):
    """Vérifie que le bonus synergie a bien été supprimé (double-comptage avec Alesina & Ardagna)."""
    economic_state = {
        'output_gap': -0.015,
        'unemployment_gap': 0.001,
        'effort_budgetaire': 0.02,
        'part_depenses': 0.5,
        'part_investissement': 0.2,
        'debt_ratio': 1.1,
        'unemployment': 0.08,
        'deficit_ratio': -0.03
    }
    simulator._last_impacts = {
        'retraites': {'depenses': -20},
        'education': {'depenses': 20}
    }
    with patch('numpy.random.normal', return_value=0):
        growth = simulator.calculate_growth(year=3, economic_state=economic_state)
    # Le bonus synergie NE DOIT PAS apparaître
    assert not any("Synergie" in s for s in simulator.debug_logs), "Bonus synergie devrait être supprimé"

def test_calculate_growth_zlb(simulator):
    economic_state = {
        'output_gap': -0.03,  # Récession profonde
        'unemployment_gap': 0.02,
        'effort_budgetaire': -0.01,  # Expansion
        'part_depenses': 0.3,
        'part_investissement': 0.4,
        'debt_ratio': 1.0,
        'unemployment': 0.091,  # > 0.09 pour stabilisateur
        'deficit_ratio': -0.04,
        'interest_rate': 0.01  # < 0.02 pour ZLB
    }
    with patch('numpy.random.normal', return_value=0):
        growth = simulator.calculate_growth(year=1, economic_state=economic_state)
    # Calcul recalibré (weighted blend + crowding-out renforcé) :
    # Base: 0.01
    # Chômage: 0.4 * 0.02 = 0.008
    # Debt drag: -0.008 * (1.0 - 0.9) = -0.0008
    # Multiplicateur blend: part_inv=0.4, part_transfers=0, part_rev=0.7, total=1.1
    #   base = (0.4/1.1)*1.0 + (0.7/1.1)*0.35 = 0.5864
    #   recession (*1.15) = 0.6744, ZLB (*1.3) = 0.8767
    #   effect = 0.8767 * 0.01 * 0.9 = 0.00789
    # Stabilisateur chômage (unemployment > 0.09): +0.005
    # deficit_ratio = -0.04, NOT < -0.04 → pas de stabilisateur déficit
    # Crowding-out (effort < 0, debt_ratio >= 1.0):
    #   intensity = 0.002 + (1-0.4)*0.006 = 0.0056, effect = 0.0056*(-0.01) = -0.000056
    # Total ≈ 0.01 + 0.008 - 0.0008 + 0.00789 + 0.005 - 0.000056 ≈ 0.0300 → clip 0.025
    expected = 0.025  # Clipped
    assert abs(growth - expected) < 0.01, f"Expected ~{expected:.3f}, got {growth:.3f}"
    assert any("Y1: Stabilisateur chômage" in s for s in simulator.debug_logs), "Log stabilisateur manquant"

def test_apply_measures_invalid_input(simulator):
    simulator.mesures = {'invalid_measure': {'param': 'invalid'}}  # Mesure inconnue
    spending, revenues, impacts = simulator.apply_measures(2026, 1698, 1545, 2994, 0.01, 0.076)
    assert spending == 1698, "Dépenses inchangées pour mesure invalide"
    assert revenues == 1545, "Recettes inchangées pour mesure invalide"
    assert not impacts, "Aucun impact pour mesure invalide"
    assert any("Mesure invalid_measure inconnue - ignorée" in s for s in simulator.debug_logs), "Log erreur manquant"

def test_calculate_revenues_laffer(simulator):
    gdp = 2994
    growth = 0.02
    inflation = 0.02
    year = 1
    simulator.recettes_precedentes = 2000  # Ratio > 65% PIB
    revenues = simulator.calculate_revenues(gdp, growth, inflation, year)
    expected = gdp * 0.65  # Plafond Laffer
    assert abs(revenues - expected) < 0.1, f"Expected ~{expected:.1f}, got {revenues:.1f}"
    assert any("Y1: PLAFOND Laffer 65% PIB" in s for s in simulator.debug_logs), "Log Laffer manquant"

def test_calculate_interest_rate_explosive(simulator):
    debt_ratio = 1.80  # > 1.70 pour spirale sévère
    year = 6  # > 5 pour effet année
    effort_budgetaire = -0.02  # Expansion risquée
    rate = simulator.calculate_interest_rate(debt_ratio, year, effort_budgetaire)
    # Base: 0.019 + 0.0041 + 0.007 * (1.80 - 1.50) + 0.015 * (1.80 - 1.70) + 0.003 * (6 - 5)
    # BCE intervention: -0.005
    # Prime risque: 0.15 * 0.02 + 0.01 = 0.013
    expected = 0.019 + 0.0041 + 0.007 * 0.3 + 0.015 * 0.1 + 0.003 * 1 - 0.005 + 0.013
    expected = min(expected, 0.050)  # Plafond BCE TPI (relevé de 3.5% à 5.0%)
    assert abs(rate - expected) < 0.001, f"Expected ~{expected:.4f}, got {rate:.4f}"
    assert any("Y6: 🚨 CRISE DE CONFIANCE" in s for s in simulator.debug_logs), "Log crise manquant"

def test_calculate_revenues_laffer_critique(simulator):
    gdp = 2994
    growth = 0.03
    inflation = 0.03
    year = 1
    simulator.recettes_precedentes = 1780  # Ratio > 0.60 mais < 0.65
    revenues = simulator.calculate_revenues(gdp, growth, inflation, year)
    revenue_ratio = revenues / gdp
    assert 0.60 < revenue_ratio <= 0.65, f"Ratio {revenue_ratio:.3f} non dans zone critique"
    assert any("Y1: Zone Laffer critique" in s for s in simulator.debug_logs), "Log Laffer critique manquant"

def test_validate_year_output_gap_excessif():
    validator = EconomicValidator()
    year_data = {
        'Recettes/PIB %': 50,
        'Dépenses/PIB %': 60,
        'Dette/PIB %': 160,
        'Gini': 0.29,
        'Inflation %': 5,
        'Output_Gap %': 4.0,  # > 3%
        'Taux_Intérêt %': 4
    }
    violations = validator.validate_year(year_data)
    assert any("Output gap 4.0% excessif" in v for v in violations), "Log output gap excessif manquant"

def test_apply_education(simulator):
    measure = {
        'id': 'education',
        'type': 'fonction',
        'cible': 'mixte'
    }
    params = {'budget': 80, 'enseignants': 10000, 'salaires': 5}
    year = 2026
    gdp = 2994
    inflation = 0.01
    unemployment = 0.076
    delta_spending, delta_revenue, impacts = simulator._apply_education(measure, params, year, gdp, inflation, unemployment)
    # Base budget is 65 (PLF 2025), not 70
    # delta_spending = (80 - 65) + 10000 * 65000/1e9 + 5 * 0.01 * 50 = 15 + 0.65 + 2.5 = 18.15
    expected_spending = (80 - 65) + (10000 * 65000 / 1e9) + (5 * 0.01 * 50)
    assert abs(delta_spending - expected_spending) < 0.1, f"Expected ~{expected_spending:.2f} Md€, got {delta_spending:.1f}"
    assert delta_revenue == 0, "Pas de recettes pour education"
    assert 'depenses' in impacts

def test_apply_sante(simulator):
    measure = {
        'id': 'sante',
        'type': 'fonction',
        'cible': 'depenses'
    }
    # Use actual sante parameters: effort_hopital, effort_ambu, effort_prev_org (0-100 scale)
    params = {'effort_hopital': 50, 'effort_ambu': 50, 'effort_prev_org': 50}
    year = 2026
    gdp = 2994
    inflation = 0.01
    unemployment = 0.076
    delta_spending, delta_revenue, impacts = simulator._apply_sante(measure, params, year, gdp, inflation, unemployment)
    # With effort=50% (0.5 after /100), year 2026:
    # Hopital: -13 * 0.5 * 0.20 (phasing_struct) = -1.3
    # Ambu: -10 * 0.5 * (0.70*0.20 + 0.30*0.50) = -10 * 0.5 * 0.29 = -1.45
    # Prev_org: -7 * 0.5 * (0.80*0.50 + 0.20*0.20) = -7 * 0.5 * 0.44 = -1.54
    # Total ≈ -4.29
    assert delta_spending < 0, f"Expected negative spending (savings), got {delta_spending:.1f}"
    assert delta_revenue == 0, "Pas de recettes pour sante"
    assert 'depenses' in impacts

def test_load_default_values():
    from budget_simulator import load_default_values
    defaults = load_default_values()
    assert 'tva_rate' in defaults, "tva_rate manquant"
    assert defaults['tva_rate']['taux'] == 0.20, "Taux TVA par défaut incorrect"
    assert 'retraites' in defaults, "retraites manquant"
    assert defaults['retraites']['age_depart'] == 62.75, "Âge départ par défaut incorrect (COR 2024: 62 ans 9 mois)"

def test_load_measure_config(simulator):
    registry = simulator._load_measure_config()
    assert 'tva_rate' in registry, "tva_rate manquant"
    assert registry['tva_rate']['parametres']['taux']['valeur_defaut'] == 0.20, "Valeur défaut TVA incorrecte"
    assert len(registry) >= 19, "Nombre de mesures insuffisant"  # Ajusté à 19

def test_validate_initial_consistency(simulator):
    simulator._validate_initial_consistency()
    # Check that consistency validation ran (either coherent or with known inconsistencies)
    consistency_ran = any("Configuration cohérente" in s or "INCOHÉRENCES" in s for s in simulator.debug_logs)
    assert consistency_ran, "Validation de cohérence non exécutée"
