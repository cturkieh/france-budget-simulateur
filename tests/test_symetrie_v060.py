"""
Tests-propriétés v0.6.0 — symétrie des multiplicateurs (audit externe, constat 2).

La littérature ne modélise AUCUNE asymétrie par le signe d'une mesure : Gechert
(2015, méta-analyse 104 études) et Gechert & Rannenberg (2018) posent la
linéarité « in scale and sign » ; le modèle officiel français Mésange
(Insee/DG Trésor 2017) : multiplicateurs « identiques » à la hausse et à la
baisse ; le seul résultat d'asymétrie de rang A (Barnichon et al. 2022,
REStud) va dans le sens OPPOSÉ au moteur v0.5.1 (coupes PLUS coûteuses).
v0.5.1 : coupe d'investissement −0,35 vs hausse +1,14 — pas un coefficient,
une ABSENCE de canal investissement dans la branche consolidation.

v0.6.0 :
- canal « coupe d'investissement » = −1,2 base (symétrique de +1,2), exempté
  de l'atténuation confiance (Alesina-Favero-Giavazzi 2019 : « almost no
  austerity plans where the main component is a cut in public investment » —
  leur résultat d'atténuation ne couvre pas ce cas ; le FMI WEO oct. 2010
  place au contraire ces coupes au haut de l'échelle de coût) ;
- générique consolidation-dépense relevé −0,40 → −0,60 (bas de fourchette
  Ramey 2019 « 0,6 to 1 » ; Gechert & Rannenberg 0,4-0,7 ; OFCE PB146 1,0) ;
- la seule non-linéarité conservée est le RÉGIME (récession ×1,15).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from budget_simulator.simulator import BudgetSimulatorV45


@pytest.fixture(scope='module')
def sim():
    return BudgetSimulatorV45()


ETAT_NEUTRE = {
    'output_gap': 0.0, 'unemployment_gap': 0.0,
    'debt_ratio': 1.15, 'interest_rate': 0.034,
}
COMPO_INVEST = {'depenses': 1.0, 'recettes': 0.0, 'investissement': 1.0}
COMPO_DEPENSE = {'depenses': 1.0, 'recettes': 0.0, 'investissement': 0.0}


def test_symetrie_canal_investissement(sim):
    """Pompe à PIB interdite : couper 1 € d'investissement public coûte autant
    de PIB que l'ajouter en rapporte (même année, même état économique)."""
    hausse = sim.multipliers.get_multiplier('expansion', COMPO_INVEST, ETAT_NEUTRE, 3, 'education')
    coupe = sim.multipliers.get_multiplier('consolidation', COMPO_INVEST, ETAT_NEUTRE, 3, 'education')
    assert coupe == pytest.approx(-hausse, abs=1e-9)
    assert hausse == pytest.approx(1.2 * 0.95, abs=1e-9)  # high_debt s'applique aux deux


def test_generique_consolidation_releve(sim):
    """Coupe de dépense NON-investissement : base −0,60 (bas de fourchette
    Ramey/Gechert), × high_debt 0,95 ÷ confiance 1,10 (atténuation conservée,
    AFG 2019)."""
    coupe = sim.multipliers.get_multiplier('consolidation', COMPO_DEPENSE, ETAT_NEUTRE, 3, 'aide_sociale')
    assert coupe == pytest.approx(-0.60 * 0.95 / 1.10, abs=1e-9)


def test_confiance_pas_sur_investissement(sim):
    """L'atténuation confiance (÷1,10) ne s'applique qu'à la part
    non-investissement d'une consolidation mixte."""
    compo_mixte = {'depenses': 1.0, 'recettes': 0.0, 'investissement': 0.5}
    mixte = sim.multipliers.get_multiplier('consolidation', compo_mixte, ETAT_NEUTRE, 3, 'mix')
    attendu = (0.5 * -1.2 + 0.5 * (-0.60 / 1.10)) * 0.95
    assert mixte == pytest.approx(attendu, abs=1e-9)


def test_regime_recession_amplifie_les_deux_sens(sim):
    """La modulation par le régime (seule non-linéarité documentée, Gechert &
    Rannenberg 2018) s'applique identiquement aux hausses et aux coupes."""
    etat_recession = dict(ETAT_NEUTRE, output_gap=-0.03)
    h = sim.multipliers.get_multiplier('expansion', COMPO_INVEST, etat_recession, 3, 'education')
    c = sim.multipliers.get_multiplier('consolidation', COMPO_INVEST, etat_recession, 3, 'education')
    assert c == pytest.approx(-h, abs=1e-9)
    assert abs(h) == pytest.approx(1.2 * 0.95 * 1.15, abs=1e-9)


# === P0-C · Effet d'offre symétrique (Bom & Ligthart 2014 : élasticité de
# fonction de production sur le STOCK — symétrique par construction ; FMI WEO
# oct. 2010 ch. 3 : couper l'investissement productif peut annuler le bénéfice
# long terme d'une consolidation ; Fieldhouse & Mertens 2025 appliquent leurs
# rendements R&D aux coupes) ===

def _bonus_apres(mesures, annees=7):
    s = BudgetSimulatorV45(periods=10, mesures=mesures)
    for y in range(1, annees + 1):
        s.update_potential_growth(0.01, y)
    return s._potential_growth_bonus


def test_offre_statu_quo_neutre():
    """Sans mesure, aucun bonus ni malus d'offre (corridor mission : la
    potentielle du statu quo ne bouge pas)."""
    assert _bonus_apres({}) == 0


def test_offre_symetrique():
    """Une coupe sous le défaut érode la croissance potentielle exactement
    comme une hausse l'augmente (même délai, même ampleur log2). v0.5.1 :
    la coupe ne produisait JAMAIS de malus (garde `delta > 0.1` à sens unique)."""
    bonus = _bonus_apres({'recherche_publique': {'budget': 18}})
    malus = _bonus_apres({'recherche_publique': {'budget': 2}})
    assert bonus > 0
    assert malus == pytest.approx(-bonus, abs=1e-9)


def test_offre_plancher_symetrique():
    """Plancher −0,20 pt en miroir du cap +0,20 pt (bornes conventionnelles
    assumées, METHODOLOGIE § design)."""
    mesures_coupe_totale = {
        'recherche_publique': {'budget': 0},
        'education': {'budget': 30},
        'transition_ecologique': {'investissement': 0, 'renovation': 0},
    }
    s = BudgetSimulatorV45(periods=10, mesures=mesures_coupe_totale)
    for y in range(1, 20):
        s.update_potential_growth(0.01, y)
    assert s._potential_growth_bonus >= -0.002 - 1e-12


def test_balayage_education_monotone_et_directionnel():
    """Le balayage de l'audit (constat 2) : la dette 2035 est STRICTEMENT
    monotone DÉCROISSANTE le long du curseur éducation (couper coûte, investir
    améliore le ratio — direction documentée : multiplicateur investissement
    1,2 FMI/OFCE + dénominateur, symétrique en coupe). Et en EUROS : couper
    RÉDUIT la dette, dépenser l'AUGMENTE — pas d'autofinancement magique en
    niveau sur ce curseur (revue adverse 24/08)."""
    dettes, euros = [], []
    for v in (45, 65, 85):
        df, _, _ = BudgetSimulatorV45(periods=10, mesures={'education': {'budget': v}}).simulate()
        dettes.append(df['Dette/PIB %'].iloc[-1])
        euros.append(df['Dette'].iloc[-1])
    assert dettes[0] > dettes[1] > dettes[2], f"ratio non décroissant : {dettes}"
    assert euros[0] < euros[1] < euros[2], f"euros non croissants : {euros}"


def test_balayage_defense_direction():
    """Curseur NON-investissement (défense, multiplicateur transfert) : plus
    de dépense = plus de dette, en ratio ET en euros."""
    df_base, _, _ = BudgetSimulatorV45(periods=10, mesures={}).simulate()
    df_def, _, _ = BudgetSimulatorV45(periods=10, mesures={'defense': {'budget': 70}}).simulate()
    assert df_def['Dette/PIB %'].iloc[-1] > df_base['Dette/PIB %'].iloc[-1] + 1.5
    assert df_def['Dette'].iloc[-1] > df_base['Dette'].iloc[-1] + 100


def test_residu_pompe_a_pib_borne():
    """Séquence hausse-puis-coupe de même montant : le résidu de PIB 2035
    (différence seconde) reste borné — mesuré ~0,58 % du PIB (v0.5.1 : ~2 %).
    Un moteur dynamique à états ne peut pas être exactement nul ; le contrat
    borne la régression (revue adverse 24/08)."""
    def pib35(mes):
        df, _, _ = BudgetSimulatorV45(periods=10, mesures=mes).simulate()
        return df['PIB'].iloc[-1]
    p0 = pib35({})
    residu = pib35({'education': {'budget': 85}}) + pib35({'education': {'budget': 45}}) - 2 * p0
    assert abs(residu) / p0 < 0.010, f"résidu de pompe {residu:+.1f} Md€ = {residu/p0*100:.2f} % PIB"
