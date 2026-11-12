"""Release P (v0.8.1) — bornes hautes de trois montants relevées jusqu'au plus haut objectif de dépense publié en
part du PIB ou du RNB (décision du mainteneur du 12/11/2026 : ces objectifs sont comptés pour tous ; même règle que
``DMTG_VARIATION_MAX_MD``), arrondi au pas du curseur supérieur, SOURCÉES ; aucun calcul ne change :
- ``recherche_publique.budget`` : 20 → 37 (base 10 Md€ + 1,5 − 0,75 point de PIB de 2032 : objectif publié le plus
  haut de dépense de recherche du secteur public, 1,5 % du PIB en 2032 ; dépense de recherche des administrations,
  0,75 % du PIB en 2024, MESR-SIES, note flash n° 2026-16) ;
- ``transferts_etranger.montant`` : 10 → 10,5 (0,7 − 0,42 point de RNB de 2032 : aide publique au développement à
  0,7 % du RNB ; 0,42 % en 2025, document de politique transversale annexé au projet de loi de finances pour 2027 ;
  RNB = PIB × 3 042 365 / 2 991 055,9, Eurostat 2025) ;
- ``depenses_publiques.credits_etat`` : 20 → 28 (14,6 Md€ de crédits annoncés, plus haut montant écrit par un
  programme publié, + 1 − 0,646 point de PIB de 2032 : dépense publique culturelle à 1 % du PIB ; services culturels
  de toutes les administrations, 18 963,0 M€ en 2024, Eurostat COFOG 08.2, PIB 2024 2 935 236,2 M€).
Le PIB de 2032 est celui de la référence du moteur (mesures vides, début 2028), lu ici. Aucune donnée de programme
publié n'est nommée : les nombres sont les objectifs et niveaux officiels qui sourcent les bornes.
"""
import json
from pathlib import Path

import pytest

import budget_simulator.constants as C
from budget_simulator.constants import PARAM_DOMAINS
from budget_simulator.simulator import BudgetSimulatorV45

from cadre_harness import impacts_par_annee, simuler

RACINE = Path(__file__).absolute().parent.parent
REGISTRE = {m['id']: m for m in json.loads(
    (RACINE / 'policy_measures.json').read_text(encoding='utf-8'))['mesures']}
DEBUT = C.ANNEE_PREMIER_BUDGET_MANDAT
FIN = C.ANNEE_FIN_MANDAT

BORNES = {
    'recherche_publique.budget': ('RECHERCHE_BUDGET_MAX_MD', 37.0, 0.0, 1),
    'transferts_etranger.montant': ('TRANSFERTS_ETRANGER_MAX_MD', 10.5, -32.009, 0.5),
    'depenses_publiques.credits_etat': ('CREDITS_ETAT_MAX_MD', 28.0, -60.0, 1),
}


@pytest.mark.parametrize('cle', sorted(BORNES))
def test_borne_haute_nommee_dans_le_registre_et_le_domaine(cle):
    nom, valeur, mini, pas = BORNES[cle]
    levier, param = cle.split('.')
    assert getattr(C, nom) == valeur
    spec = REGISTRE[levier]['parametres'][param]
    assert (spec['min'], spec['max'], spec['step']) == (mini, valeur, pas)
    assert tuple(PARAM_DOMAINS[levier][param]) == (mini, valeur)


@pytest.fixture(scope='module')
def pib_reference():
    df, _, _ = BudgetSimulatorV45(periods=10, mesures={}, annee_debut=DEBUT).simulate()
    return dict(zip(df['Année'].astype(int), df['PIB'].astype(float)))


# Objectifs publiés les plus hauts et niveaux officiels (sources dans le docstring du module).
RNB_SUR_PIB_2025 = 3042365 / 2991055.9
CULTURE_APU_PART_2024 = 18963.0 / 2935236.2
PLUS_HAUT_OBJECTIF = {
    'recherche_publique.budget': lambda pib: 10 + (0.015 - 0.0075) * pib,
    'transferts_etranger.montant': lambda pib: (0.007 - 0.0042) * pib * RNB_SUR_PIB_2025,
    'depenses_publiques.credits_etat': lambda pib: 14.6 + (0.01 - CULTURE_APU_PART_2024) * pib,
}


@pytest.mark.parametrize('cle', sorted(BORNES))
def test_borne_couvre_le_plus_haut_objectif_publie_a_un_pas_pres(cle, pib_reference):
    """La borne est le plus haut objectif publié au PIB de 2032 de la référence, arrondi au pas
    supérieur du curseur : ni sous l'objectif (il serait écrêté), ni un pas au-dessus."""
    nom, valeur, _, pas = BORNES[cle]
    objectif = PLUS_HAUT_OBJECTIF[cle](pib_reference[FIN])
    assert objectif <= valeur < objectif + pas, (cle, objectif, valeur)


@pytest.mark.parametrize('cle', sorted(BORNES))
def test_borne_acceptee_en_strict_et_ecretee_au_dela_en_tolerant(cle, monkeypatch):
    nom, valeur, _, pas = BORNES[cle]
    levier, param = cle.split('.')
    monkeypatch.setenv('BUDGETLAB_STRICT', '1')
    _, _, rapport = BudgetSimulatorV45(periods=10, mesures={levier: {param: valeur}},
                                       annee_debut=DEBUT).simulate()
    assert rapport['valid'] is True and rapport['leviers_ecretes'] == []
    monkeypatch.setenv('BUDGETLAB_STRICT', '')
    _, _, rapport = BudgetSimulatorV45(periods=10, mesures={levier: {param: valeur + pas}},
                                       annee_debut=DEBUT).simulate()
    lignes = [l for l in rapport['leviers_ecretes'] if l['levier'] == cle]
    assert lignes and lignes[0]['applique'] == valeur


def test_effet_direct_proportionnel_jusqu_a_la_borne():
    """Au-delà de l'ancienne borne, chaque Md€ du curseur reste un Md€ de dépense (aucun
    plafond interne caché derrière la borne du registre)."""
    for cle, (nom, valeur, _, _) in BORNES.items():
        levier, param = cle.split('.')
        _, _, rapport, _ = simuler({levier: {param: valeur}}, annee_debut=DEBUT)
        base = 10 if levier == 'recherche_publique' else 0
        for an, bloc in impacts_par_annee(rapport).items():
            if an >= DEBUT:
                assert bloc[levier]['depenses'] == pytest.approx(valeur - base, abs=1e-9), (cle, an)
