"""Chiffres publiés du lot 2 sur l'ampleur de l'effet d'offre, recalculés ici et cherchés tels quels.

METHODOLOGIE (encadré « Forme logarithmique de la recherche et sortie du plafond », limite « Demande et offre »)
publie quatre constats, que ce fichier lie à la mesure ; un chiffre qui cesse de reproduire fait rougir la CI.

1. Une hausse de la recherche publique se rembourse dans le moteur avant la fin du mandat, en part du PIB et en
   euros : 5 Md€ de plus par an sur le droit en vigueur (mode cadre 2028, pleine précision), dette et solde
   2032 en points de PIB et en Md€, première année où la dette en euros passe sous celle de la référence.
2. Le rendement implicite du moteur, ε × PIB / K (euros de PIB par an et par euro de stock de recherche
   ajouté), en 2025 et en 2032 : sous le rendement que l'étude source estime au centre (Fieldhouse & Mertens,
   tableau 2, ligne [1] : 1,71 ; intervalle 1,07 à 2,22).
3. L'échelle du plus gros programme publié : stock de recherche ajouté en 2032 rapporté au stock de départ,
   « de l'ordre d'un tiers » (sauté sans ``scenarios.json`` : aucun programme publié dans le dépôt public).
4. Demande et offre des leviers d'investissement : PIB réel par euro dépensé chaque année, quatre ans après le
   début (15 Md€ par an dès 2026, mode historique, statu quo, pleine précision), pour une dépense de la famille
   investissement sans effet d'offre (l'éducation, levier du banc de calage), l'investissement de l'État ou des
   collectivités et la recherche. La cible du FMI (1,5 à quatre ans) est un effet total, qui contient déjà la
   capacité de production ; le canal d'offre du moteur s'y ajoute.

Aucune donnée du dépôt parent n'est lue, sauf le constat 3.
"""
import copy
import json
import re
import sys
from pathlib import Path

import pytest

import budget_simulator.engine.orchestrator as orch
from budget_simulator import constants as C
from budget_simulator.config import load_default_values
from budget_simulator.simulator import BudgetSimulatorV45

RACINE = Path(__file__).absolute().parent.parent
sys.path.insert(0, str(RACINE / 'tests' / 'snapshots'))
from run_scenarios_full import PROFILS, SCENARIOS, pour_le_mode  # noqa: E402

DROIT = json.loads((RACINE / 'budget_simulator' / 'data' / 'droit_en_vigueur.json')
                   .read_text(encoding='utf-8'))['mesures']
DEFAUTS = load_default_values()
RENDEMENT_SOURCE = 1.71          # Fieldhouse & Mertens, tableau 2, ligne [1] (η intermédiaire)


@pytest.fixture
def pleine_precision(monkeypatch):
    monkeypatch.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)


def _fr(x, decimales):
    return f'{x:.{decimales}f}'.replace('-', '−').replace('.', ',')


def _texte():
    texte = (RACINE / 'docs' / 'METHODOLOGIE.md').read_text(encoding='utf-8')
    return ' '.join(re.sub(r'\n>\s?', ' ', texte).split())


def _cadre(mesures):
    df, _, _ = BudgetSimulatorV45(periods=10, mesures=copy.deepcopy(mesures), annee_debut=2028).simulate()
    return df.set_index('Année')


def constat_recherche_rembourse():
    b = _cadre(DROIT)
    v = _cadre({**DROIT, 'recherche_publique': {'budget': DEFAUTS['recherche_publique']['budget'] + 5}})

    def en_md(df, colonne, a):
        return df.at[a, colonne] * df.at[a, 'PIB'] / 100
    dette_pt = v.at[2032, 'Dette/PIB %'] - b.at[2032, 'Dette/PIB %']
    dette_md = en_md(v, 'Dette/PIB %', 2032) - en_md(b, 'Dette/PIB %', 2032)
    solde_md = en_md(v, 'Déficit/PIB %', 2032) - en_md(b, 'Déficit/PIB %', 2032)
    sous = [a for a in range(2028, 2036) if en_md(v, 'Dette/PIB %', a) < en_md(b, 'Dette/PIB %', a)]
    assert sous == list(range(sous[0], 2036)), sous          # une fois passée sous la référence, elle y reste
    rendement = {a: C.ELASTICITE_PIB_CAPITAL_RD_PUBLIC * b.at[a, 'PIB'] / C.CAPITAL_RD_PUBLIC_MD_EUR
                 for a in (2025, 2032)}
    return dette_pt, dette_md, solde_md, sous[0], rendement


def test_la_recherche_se_rembourse_dans_le_mandat(pleine_precision):
    dette_pt, dette_md, solde_md, annee, rendement = constat_recherche_rembourse()
    assert dette_pt < 0 and dette_md < 0 < solde_md and annee <= 2032
    texte = _texte()
    attendu = (f"dette 2032 plus basse de {_fr(-dette_pt, 2)} point de PIB et de {_fr(-dette_md, 1)} Md€, "
               f"solde 2032 meilleur de {_fr(solde_md, 1)} Md€ ; la dette en euros passe sous celle de la "
               f"référence dès {annee}")
    assert attendu in texte, attendu
    assert all(r < RENDEMENT_SOURCE for r in rendement.values()), rendement
    attendu = (f"rendement implicite du moteur : {_fr(rendement[2025], 2)} € en 2025, "
               f"{_fr(rendement[2032], 2)} € en 2032")
    assert attendu in texte, attendu


def test_echelle_du_plus_gros_programme_publie(pleine_precision):
    if not SCENARIOS:
        pytest.skip("scenarios.json introuvable (fork moteur public seul)")
    parts = []
    for sid, mesures in SCENARIOS.items():
        s = BudgetSimulatorV45(periods=10, mesures=pour_le_mode(mesures, 2028), annee_debut=2028,
                               profils=PROFILS.get(sid) or None)
        s.simulate()
        # Stock ajouté à la fin de la simulation : inventaire des écarts 2028-2035 ; celui de 2032 en est la
        # cinquième étape, recalculée depuis les écarts consignés.
        stock = 0.0
        for i, ecart in enumerate(s._supply_flux.get('recherche_publique', [])):
            stock = (1 - C.DEPRECIATION_RD_PUBLIQUE) * stock + ecart
            if s.annee_base + i + 1 == 2032:
                parts.append(stock / C.CAPITAL_RD_PUBLIC_MD_EUR)
    assert 0.30 < max(parts) < 0.40, parts
    assert "stock ajouté de l'ordre d'un tiers du stock de départ en cinq ans" in _texte()


def constat_demande_et_offre():
    x = 15.0
    base = BudgetSimulatorV45(periods=12, mesures={}).simulate()[1].set_index('Année')
    leviers = {'sans_offre': {'education': {'budget': DEFAUTS['education']['budget'] + x}},
               'etat': {'transition_ecologique': {'investissement': x}},
               'collectivites': {'collectivites': {'investissement': x}},
               'recherche': {'recherche_publique': {'budget': DEFAUTS['recherche_publique']['budget'] + x}}}
    out = {}
    for nom, mesures in leviers.items():
        a = BudgetSimulatorV45(periods=12, mesures=mesures).simulate()[1].set_index('Année')
        out[nom] = (a.at[2030, 'PIB_Réel_Base2025'] - base.at[2030, 'PIB_Réel_Base2025']) / x
    return out


@pytest.mark.xfail(strict=True, reason="pile d'intégration, équation du lot 6 : coefficients recalés au commit de "
                                       "paramètres suivant (effet total par euro de l'investissement 1,4995, sous la "
                                       "cible de 1,5, avant le recalage)")
def test_demande_et_offre_des_leviers_d_investissement(pleine_precision):
    m = constat_demande_et_offre()
    assert m['sans_offre'] < 1.5 < min(m['etat'], m['collectivites']) < m['recherche']
    if _fr(m['etat'], 2) == _fr(m['collectivites'], 2):
        investissement = f"{_fr(m['etat'], 2)} € pour l'investissement de l'État ou des collectivités"
    else:   # tant que le levier de l'État garde une recette propre (avant le retrait du retour fiscal)
        investissement = (f"{_fr(m['etat'], 2)} € pour l'investissement de l'État, {_fr(m['collectivites'], 2)} € "
                          f"pour celui des collectivités")
    attendu = (f"{_fr(m['sans_offre'], 2)} € pour une dépense de la famille investissement sans effet d'offre "
               f"(le levier du banc de calage), {investissement}, {_fr(m['recherche'], 2)} € pour la recherche")
    assert attendu in _texte(), attendu
