"""Garde durable : aucun saut de dette 2035 > ε hors interrupteurs 0/1 déclarés
(v0.6.7, lot 3b).

Sous-ensemble RAPIDE du balayage de ``scripts/scan_discontinuites.py`` (le
balayage complet — 10 scénarios publiés × chaque paramètre de PARAM_DOMAINS ×
41 points — reste un script, à lancer avant toute passe moteur) : TOUS les
scénarios publiés, tous les paramètres continus, 7 points par domaine, bissection
des intervalles suspects. Jusqu'à v0.8.1, deux scénarios seulement (le scénario de
référence et celui en récession profonde, les plus proches des seuils historiques).

Ce que la garde attrape : une marche réintroduite (régime, porte d'activation,
filtre) qui fait sauter la dette 2035 au franchissement d'un seuil — le défaut
corrigé par les commits « régimes continus » et « portes d'activation ». Ce
qu'elle ne garantit pas : un saut noyé dans une pente plus forte que lui sur le
même intervalle (limite déclarée du repérage par contraste ; la porte TVA a été
trouvée par lecture du code). La contre-épreuve vérifie que le repérage voit une
marche réintroduite.

Lot 1 (15/11/2026). Les retraits du lot raidissent la réponse de la dette 2035 aux
budgets. Pour le scénario publié en récession profonde (dette 2035, mode historique,
pleine précision, 1 Md€ de budget de la défense de plus) : 0,058 point en v0.8.1 ;
0,113 une fois retiré le terme d'effort de l'inflation ; 0,190 une fois retirée aussi
la cicatrice ; 0,196 à l'état final du lot. La marche réinjectée par l'ancienne
contre-épreuve, sur ce scénario, y était noyée dans la pente. Deux changements :
la garde porte sur tous les scénarios publiés (aucun saut ; même résolution) ; la
contre-épreuve porte sur un scénario SYNTHÉTIQUE défini ici, qui ne dépend de
l'encodage d'aucun programme publié et tourne aussi sans ``scenarios.json``.
"""
import importlib.util
import json
import os
from pathlib import Path

import pytest

from budget_simulator.constants import LEVIERS_NON_LIVRES
from budget_simulator.engine._param_domain import PARAM_DOMAINS

_SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'scan_discontinuites.py'
_spec = importlib.util.spec_from_file_location('scan_discontinuites', _SCRIPT)
scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scan)

EPSILON_PT = 1e-3
POINTS = 7


def _ids_publies():
    chemin = (os.environ.get('BUDGETLAB_SCENARIOS_JSON') or '').strip()
    if chemin and Path(chemin).exists():
        return list(json.loads(Path(chemin).read_text(encoding='utf-8')))
    return ['scenarios_json_absent']   # le test se saute (_scenarios)


SCENARIOS_GARDES = _ids_publies()


@pytest.fixture
def pleine_precision(monkeypatch):
    import budget_simulator.engine.orchestrator as orch
    monkeypatch.setattr(orch, 'round', lambda x, nd=None: float(x), raising=False)


def _scenarios():
    chemin = (os.environ.get('BUDGETLAB_SCENARIOS_JSON') or '').strip()
    if not chemin or not Path(chemin).exists():
        pytest.skip("scenarios.json introuvable (fork moteur public seul)")
    # Mode historique : mesures telles que le mode les accepte (release P :
    # sans la recette d'une seule année, cadre_harness.pour_le_mode).
    from cadre_harness import pour_le_mode
    return {k: pour_le_mode(v['apiMeasures'])
            for k, v in json.loads(Path(chemin).read_text(encoding='utf-8')).items()}


@pytest.mark.slow
@pytest.mark.parametrize('sid', SCENARIOS_GARDES)
def test_aucun_saut_hors_interrupteurs(sid, pleine_precision):
    mesures = _scenarios()[sid]
    sauts = []
    for levier, domaine in PARAM_DOMAINS.items():
        # Release E : un levier non livré (squelette) refuse toute valeur non
        # neutre ; il est balayé quand son chantier le retire de la liste.
        if levier in LEVIERS_NON_LIVRES:
            continue
        for param, (lo, hi) in domaine.items():
            # v0.6.10 : un paramètre masqué par un mode exclusif n'est pas lu
            # (balayage plat, qui ne testait rien) et la porte le rejette en
            # strict ; son canal est balayé par la clé qui le masque.
            if param in scan.DRAPEAUX or scan.parametre_masque(mesures, levier, param):
                continue
            sauts += [s for s in scan.balayer(mesures, sid, levier, param, float(lo), float(hi), POINTS)
                      if abs(s['saut_dette_2035']) > EPSILON_PT]
    assert not sauts, '\n'.join(
        f"{s['parametre']} @ {s['x']:.6g} : {s['saut_dette_2035']:+.4f} pt (divergence {s['divergence']})"
        for s in sauts)


# Scénario SYNTHÉTIQUE de la contre-épreuve (lot 1) : une consolidation qui monte en
# charge — rabot uniforme de 9 % des dépenses (une première marche l'année 1, une
# seconde l'année 2, sous le plafond de 5 % du PIB par mesure) et 300 000 postes de
# moins dans la fonction publique (environ 0,1 point de PIB de plus par an pendant six
# ans). L'écart de production y passe par −2 % pendant que les impulsions de la montée
# en charge sont stockées : c'est là que l'ancienne marche du régime de récession
# jouait. Mesuré à 7 points, sur les quatre balayages ci-dessous : 2,0 à 2,1 points de
# dette 2035 du retrait du terme d'effort de l'inflation au recalage du coefficient des
# transferts (2,4 en v0.8.1 sur les deux balayages de l'impôt sur le revenu). Le seuil
# de 0,1 point ne décide pas : quand le repérage par contraste ne voit pas la marche, le
# saut rapporté est nul. La marge se lit donc sur l'amplitude de la marche. Mesuré en la
# réduisant (poids du régime 0 → a au franchissement ; a = 1 ici) : la contre-épreuve la
# voit encore à une amplitude 3 à 9 fois plus petite, selon l'état du moteur (a = 0,3
# après le seul retrait du terme d'effort de l'inflation, 0,11 une fois la cicatrice
# retirée, 0,2 en v0.8.1) ; en deçà, elle ne la voit plus et rougit.
SCENARIO_SYNTHETIQUE = {'rabot_uniforme': {'taux_reduction': 0.09},
                        'fonction_publique': {'effectifs': -300000}}
BALAYAGES_DE_LA_CONTRE_EPREUVE = (('impot_revenu', 'taux_superieur'), ('impot_revenu', 'decote'),
                                  ('collectivites', 'investissement'), ('recherche_publique', 'budget'))


def _sauts_synthetiques():
    sauts = []
    for levier, param in BALAYAGES_DE_LA_CONTRE_EPREUVE:
        lo, hi = PARAM_DOMAINS[levier][param]
        sauts += scan.balayer(SCENARIO_SYNTHETIQUE, 'synthetique', levier, param, float(lo), float(hi), POINTS)
    return sauts


def test_la_garde_n_est_pas_vide(pleine_precision, monkeypatch):
    """Contre-épreuve : le repérage de la garde, à ``POINTS`` points, sans marche,
    ne voit rien sur le scénario synthétique ; avec l'ancienne MARCHE du régime de
    récession réinjectée (×1,15 dès gap < −2 % ou écart de chômage > 2 pts), il la
    voit, de plus de 0,1 point de dette 2035.

    Jusqu'au lot 1, la contre-épreuve visait un balayage d'un programme publié (le
    budget de la défense du scénario en récession profonde, −2,06 pt) ; elle dépendait
    de son encodage et sautait sans ``scenarios.json``."""
    assert not [s for s in _sauts_synthetiques() if abs(s['saut_dette_2035']) > EPSILON_PT]
    import budget_simulator.simulator as sim_mod
    monkeypatch.setattr(sim_mod, 'poids_recession',
                        lambda g, u: 1.0 if (g < -0.02 or u > 0.02) else 0.0)
    sauts = _sauts_synthetiques()
    assert max((abs(s['saut_dette_2035']) for s in sauts), default=0.0) > 0.1, sauts
