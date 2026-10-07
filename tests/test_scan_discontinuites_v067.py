"""Garde durable : aucun saut de dette 2035 > ε hors interrupteurs 0/1 déclarés
(v0.6.7, lot 3b).

Sous-ensemble RAPIDE du balayage de ``scripts/scan_discontinuites.py`` (le
balayage complet — 10 scénarios publiés × chaque paramètre de PARAM_DOMAINS ×
41 points — reste un script, à lancer avant toute passe moteur) : les deux
scénarios publiés les plus proches des seuils historiques — « Budget 2026
(voté) », servi par le site, et ``im_rabot_2029``, en récession profonde —, tous
les paramètres continus, 7 points par domaine, bissection des intervalles suspects.

Ce que la garde attrape : une marche réintroduite (régime, porte d'activation,
filtre) qui fait sauter la dette 2035 au franchissement d'un seuil — le défaut
corrigé par les commits « régimes continus » et « portes d'activation ». Ce
qu'elle ne garantit pas : un saut noyé dans une pente plus forte que lui sur le
même intervalle (limite déclarée du repérage par contraste ; la porte TVA a été
trouvée par lecture du code). La contre-épreuve vérifie qu'elle n'est pas vide.
"""
import importlib.util
import json
import os
from pathlib import Path

import pytest

from budget_simulator.engine._param_domain import PARAM_DOMAINS

_SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'scan_discontinuites.py'
_spec = importlib.util.spec_from_file_location('scan_discontinuites', _SCRIPT)
scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scan)

EPSILON_PT = 1e-3
POINTS = 7
SCENARIOS_GARDES = ('plf_2026', 'im_rabot_2029')


@pytest.fixture
def pleine_precision(monkeypatch):
    import budget_simulator.engine.orchestrator as orch
    monkeypatch.setattr(orch, 'round', lambda x, nd=None: float(x), raising=False)


def _scenarios():
    chemin = (os.environ.get('BUDGETLAB_SCENARIOS_JSON') or '').strip()
    if not chemin or not Path(chemin).exists():
        pytest.skip("scenarios.json introuvable (fork moteur public seul)")
    return {k: v['apiMeasures'] for k, v in json.loads(Path(chemin).read_text(encoding='utf-8')).items()}


@pytest.mark.slow
@pytest.mark.parametrize('sid', SCENARIOS_GARDES)
def test_aucun_saut_hors_interrupteurs(sid, pleine_precision):
    mesures = _scenarios()[sid]
    sauts = []
    for levier, domaine in PARAM_DOMAINS.items():
        for param, (lo, hi) in domaine.items():
            if param in scan.DRAPEAUX:
                continue
            sauts += [s for s in scan.balayer(mesures, sid, levier, param, float(lo), float(hi), POINTS)
                      if abs(s['saut_dette_2035']) > EPSILON_PT]
    assert not sauts, '\n'.join(
        f"{s['parametre']} @ {s['x']:.6g} : {s['saut_dette_2035']:+.4f} pt (divergence {s['divergence']})"
        for s in sauts)


def test_la_garde_n_est_pas_vide(pleine_precision, monkeypatch):
    """Contre-épreuve : réinjecter l'ancienne MARCHE du régime récession (×1,15 dès
    gap < −2 % ou écart de chômage > 2 pts) doit être détecté — mesuré −2,06 pt sur
    le budget de la défense de im_rabot_2029 (le même saut, sur le curseur rabot de
    « Budget 2026 (voté) », échappe à 7 points : la pente du curseur le noie — la
    limite déclarée en tête de fichier)."""
    import budget_simulator.simulator as sim_mod
    monkeypatch.setattr(sim_mod, 'poids_recession',
                        lambda g, u: 1.0 if (g < -0.02 or u > 0.02) else 0.0)
    lo, hi = PARAM_DOMAINS['defense']['budget']
    sauts = scan.balayer(_scenarios()['im_rabot_2029'], 'im_rabot_2029', 'defense',
                         'budget', float(lo), float(hi), POINTS)
    assert any(abs(s['saut_dette_2035']) > 0.1 for s in sauts), sauts
