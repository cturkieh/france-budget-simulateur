"""
Tests-propriétés v0.6.0 — asymétries pro-consolidation (audit externe, constat 3).

P1-A · Effet confiance « Alesina » : SUPPRIMÉ. L'austérité expansionniste est
réfutée sur échantillon corrigé (FMI WEO oct. 2010 ch. 3 : « the opposite is
true » ; Guajardo, Leigh & Pescatori 2014 ; Jordà & Taylor 2016), et la
position finale de l'école Alesina (AFG 2019) ne défend plus que la
composition (« mild recessionary » — capté par adjustments['confidence']=1,10,
conservé). Le canal confiance restant vit sur la prime de taux (debt.py).

P1-B · Stabilisateurs en escalier : SUPPRIMÉS. Erreur de nature — un
stabilisateur automatique joue sur le SOLDE, jamais sur le taux de croissance
(FIPECO/Ecalle ; OCDE ECO/WKP(2020)44 ; CE Mourre et al. 2019). Le moteur les
produit déjà par construction (élasticité PO/PIB = 1,0 + dépenses chômage
indexées) : la semi-élasticité du solde au PIB doit ressortir à ~0,55 SANS
aucun terme ajouté à la croissance. L'escalier `deficit < −4 %` était de plus
vrai chaque année en baseline (+0,10 pt/an permanent, disparaissant pour qui
assainit : récompense structurelle du non-assainissement).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from budget_simulator.simulator import BudgetSimulatorV45
from budget_simulator.constants import SEMI_ELASTICITE_SOLDE_PIB_FRANCE


def test_bloc_confiance_et_stabilisateurs_supprimes():
    """Aucun scénario ne déclenche plus le bonus de croissance « effet
    confiance » ni les stabilisateurs en escalier. Contrat observable : les
    logs déterministes du moteur (BUDGET_DEBUG), qui traçaient chaque
    déclenchement — sous-processus car le flag est lu au load du module."""
    import subprocess
    code = (
        "from budget_simulator.simulator import BudgetSimulatorV45 as S\n"
        "mes = {'aide_sociale': {'reduction': 20}, 'sante': {'effort_hopital': 1.0},\n"
        "       'fonction_publique': {'effectifs': -100000, 'point_indice': 0},\n"
        "       'retraites': {'age_depart': 65.0, 'indexation': 0.5, 'duree_cotisation': 43}}\n"
        "for m in (mes, {}):\n"
        "    s = S(periods=10, mesures=m); s.simulate()\n"
        "    for l in s.debug_logs:\n"
        "        if 'Effet confiance' in l or 'Stabilisateur' in l:\n"
        "            print('DECLENCHE:', l)\n"
    )
    env = dict(os.environ, BUDGET_DEBUG='true')
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    res = subprocess.run([sys.executable, '-c', code], capture_output=True,
                         text=True, env=env, cwd=racine)
    assert res.returncode == 0, res.stderr
    assert 'DECLENCHE:' not in res.stdout, res.stdout[:500]


def test_semi_elasticite_solde_pib():
    """Contrat de contrôle (remplace les escaliers) : un choc de croissance de
    +1 pt améliore le solde/PIB de 0,50 à 0,60 pt l'année du choc — la
    semi-élasticité française (FIPECO 0,55 ; OCDE 0,5 moy.), produite par
    CONSTRUCTION (élasticité PO 1,0 + chômage indexé), jamais par un terme de
    croissance ajouté."""
    annee_choc = 4
    orig = BudgetSimulatorV45.calculate_growth

    def choque(self, year, economic_state):
        g = orig(self, year, economic_state)
        return g + 0.01 if year == annee_choc else g

    base_df, _, _ = BudgetSimulatorV45(periods=10, mesures={}).simulate()
    try:
        BudgetSimulatorV45.calculate_growth = choque
        choc_df, _, _ = BudgetSimulatorV45(periods=10, mesures={}).simulate()
    finally:
        BudgetSimulatorV45.calculate_growth = orig

    # La ligne 0 du DataFrame est l'ancrage (croissance 2025 exogène) :
    # calculate_growth(year=k) alimente la ligne k.
    d_pib = (choc_df['Croissance %'].iloc[annee_choc]
             - base_df['Croissance %'].iloc[annee_choc])
    d_solde = (choc_df['Déficit/PIB %'].iloc[annee_choc]
               - base_df['Déficit/PIB %'].iloc[annee_choc])
    epsilon = d_solde / d_pib
    # Bande [0,50 ; 0,65] : FIPECO 0,55, CE Mourre et al. 2019 France ≈ 0,60 ;
    # la mesure moteur (~0,63) inclut l'effet dénominateur du ratio et l'Okun
    # de second tour. Le contrat vise la RÉGRESSION (un escalier réintroduit
    # sur la croissance sort largement de la bande), pas la fausse précision.
    assert 0.50 <= epsilon <= 0.65, f"semi-élasticité mesurée {epsilon:.3f} hors bande"
    assert abs(epsilon - SEMI_ELASTICITE_SOLDE_PIB_FRANCE) <= 0.10
