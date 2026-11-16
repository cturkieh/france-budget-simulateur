"""Variantes de sensibilité de la recherche publique, publiées dans METHODOLOGIE seulement (lot 2).

Arbitrage du mainteneur (16/11/2026) : deux variantes mesurées et publiées, au même gabarit pour tous les
scénarios, sans nom de programme ; aucune n'entre dans la version principale.

- (i) Effet deux ans après la dépense : la dépense entre au stock un an plus tard (``delay`` = 1), hypothèse de
  l'OCDE (Guellec & van Pottelsberghe 2001, DSTI/DOC(2001)3 : un retard de deux ans posé a priori, non estimé,
  pour la recherche publique).
- (ii) « Hausse rapide » : 30 % d'une HAUSSE de dépense de recherche partent en salaires des chercheurs et
  n'entrent pas au stock. Goolsbee (1998, NBER WP 6532), étude américaine citée par la revue des sources de
  novembre 2026 : les études usuelles surestiment l'effet de « 30 to 50% » ; sur la hausse de 1980-1984,
  « 7.6% — 30% smaller » que la hausse de la dépense pour l'ensemble de la recherche, « as much as 40-50% » pour
  les métiers les plus demandés. 30 % est le bas de la fourchette, le cas calculé pour la recherche dans son
  ensemble, que finance le levier. En sensibilité seulement : l'élasticité de Fieldhouse & Mertens est estimée
  sur un échantillon où cet effet a déjà joué en moyenne, l'appliquer dans la version principale le compterait
  deux fois.

Chaque nombre du tableau de METHODOLOGIE (encadré « Forme logarithmique de la recherche et sortie du plafond »)
est recalculé ici et cherché tel quel : écart à la version principale de la dette 2032, du déficit 2032 et de
la croissance moyenne 2028-2032, en mode cadre 2028, pleine précision. Les lignes sont repérées par l'écart de
recherche du programme en 2032, jamais par un nom. La ligne d'illustration (droit en vigueur, +5 Md€ par an de
recherche) tourne sans ``scenarios.json`` ; les lignes des scénarios publiés sont sautées sans lui.
"""
import copy
import json
import re
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

import budget_simulator.engine.growth as growth_mod
import budget_simulator.engine.orchestrator as orch
from budget_simulator.config import load_default_values
from budget_simulator.simulator import BudgetSimulatorV45

RACINE = Path(__file__).absolute().parent.parent
sys.path.insert(0, str(RACINE / 'tests' / 'snapshots'))
from run_scenarios_full import PROFILS, SCENARIOS, pour_le_mode  # noqa: E402

DROIT = json.loads((RACINE / 'budget_simulator' / 'data' / 'droit_en_vigueur.json')
                   .read_text(encoding='utf-8'))['mesures']
DEFAUT = load_default_values()['recherche_publique']['budget']
PART_SALAIRES = 0.30            # Goolsbee 1998, ensemble de la recherche (« 30% smaller »), bas de la fourchette 30-50 %
HAUSSE_ILLUSTRATION = 5.0       # Md€ par an, sur le droit en vigueur


@contextmanager
def _variante(nom):
    """Variante en mémoire ; ``None`` = version principale."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
        if nom == 'deux_ans':
            table = dict(BudgetSimulatorV45.SUPPLY_EFFECTS)
            table['recherche_publique'] = {**table['recherche_publique'], 'delay': 1}
            mp.setattr(BudgetSimulatorV45, 'SUPPLY_EFFECTS', table)
        elif nom == 'salaires':
            vraie = growth_mod.validate_param_domains

            def porte(measure_id, params, *a, **k):
                propre = vraie(measure_id, params, *a, **k)
                hausse = propre.get('budget', DEFAUT) - DEFAUT if measure_id == 'recherche_publique' else 0
                if hausse > 0:
                    propre = {**propre, 'budget': DEFAUT + (1 - PART_SALAIRES) * hausse}
                return propre
            mp.setattr(growth_mod, 'validate_param_domains', porte)
        yield


def _indicateurs(mesures, profils=None):
    df, _, _ = BudgetSimulatorV45(periods=10, mesures=copy.deepcopy(mesures), annee_debut=2028,
                                  profils=copy.deepcopy(profils) or None).simulate()
    d = df.set_index('Année')
    return (float(d.at[2032, 'Dette/PIB %']), float(d.at[2032, 'Déficit/PIB %']),
            float(d.loc[2028:2032, 'Croissance %'].mean()))


def _ecarts(cas):
    """{variante: (Δdette, Δdéficit, Δcroissance)} contre la version principale, pour une liste de cas
    (mesures, profils) dont on retient la somme des écarts — un seul cas en pratique."""
    out = {}
    for nom in (None, 'deux_ans', 'salaires'):
        with _variante(nom):
            out[nom] = _indicateurs(*cas)
    return {nom: tuple(v - b for v, b in zip(out[nom], out[None])) for nom in ('deux_ans', 'salaires')}, out[None]


def _fr(x, decimales, signe=True):
    t = f'{x:+.{decimales}f}' if signe else f'{x:.{decimales}f}'
    return t.replace('-', '−').replace('.', ',')


def _cellule(e):
    return f"{_fr(e[0], 2)} / {_fr(e[1], 2)} / {_fr(e[2], 3)}"


def _ecart_recherche_2032(sid):
    profil = (PROFILS.get(sid) or {}).get('recherche_publique.budget')
    if profil:
        assert profil.get('forme') == 'valeurs', profil   # seule forme rencontrée ; une autre doit être lue
        return float(profil['valeurs']['2032']) - DEFAUT
    return float((SCENARIOS[sid].get('recherche_publique') or {}).get('budget', DEFAUT)) - DEFAUT


def lignes_des_scenarios_publies():
    """Lignes du tableau pour les scénarios publiés, repérées par leur écart de recherche en 2032."""
    lignes, sans = [], []
    for sid, mesures in sorted(SCENARIOS.items()):
        ecart = _ecart_recherche_2032(sid)
        e, _ = _ecarts((pour_le_mode(mesures, 2028), PROFILS.get(sid)))
        if ecart == 0:
            sans.append(e)
            continue
        lignes.append((ecart, f"| +{_fr(ecart, 1, signe=False)} Md€ | {_cellule(e['deux_ans'])} | "
                              f"{_cellule(e['salaires'])} |"))
    return [l for _, l in sorted(lignes, reverse=True)], sans


def ligne_d_illustration():
    plus = {**DROIT, 'recherche_publique': {'budget': DEFAUT + HAUSSE_ILLUSTRATION}}
    e, principale = _ecarts((plus, None))
    with _variante(None):
        reference = _indicateurs(DROIT)
    effet = tuple(p - r for p, r in zip(principale, reference))
    return (f"| droit en vigueur, +5 Md€ par an (version principale : {_cellule(effet)}) | "
            f"{_cellule(e['deux_ans'])} | {_cellule(e['salaires'])} |"), effet


def _texte():
    texte = (RACINE / 'docs' / 'METHODOLOGIE.md').read_text(encoding='utf-8')
    return [' '.join(l.split()) for l in texte.splitlines()]


def test_ligne_d_illustration_liee_a_la_mesure():
    """Tourne sans ``scenarios.json`` : droit en vigueur livré avec le moteur."""
    ligne, effet = ligne_d_illustration()
    assert ' '.join(ligne.split()) in _texte(), ligne
    assert effet[0] < 0 < effet[1] and effet[2] > 0   # la hausse de recherche baisse la dette, en version principale


def test_lignes_des_scenarios_publies_liees_a_la_mesure():
    if not SCENARIOS:
        pytest.skip("scenarios.json introuvable (fork moteur public seul)")
    lignes, sans = lignes_des_scenarios_publies()
    texte = _texte()
    assert lignes, 'aucun scénario publié ne modifie la recherche : le tableau serait vide'
    for ligne in lignes:
        assert ' '.join(ligne.split()) in texte, ligne
    # Les scénarios sans écart de recherche ne bougent pas, au bit : ligne « aucun ».
    assert all(v == 0.0 for e in sans for c in e.values() for v in c), sans
    nombre = {3: 'trois', 4: 'quatre', 5: 'cinq', 6: 'six', 7: 'sept', 8: 'huit', 9: 'neuf'}[len(sans)]
    assert f"| aucun ({nombre} scénarios) | 0 | 0 |" in texte


def test_variantes_hors_de_la_version_principale():
    """Garde : la version principale n'a ni décalage ni part salariale (``delay`` 0 ; une hausse entre en
    entier au stock)."""
    assert BudgetSimulatorV45.SUPPLY_EFFECTS['recherche_publique']['delay'] == 0
    s = BudgetSimulatorV45(periods=10, mesures={'recherche_publique': {'budget': DEFAUT + 4}})
    s.update_potential_growth(0.01, 1)
    assert s._supply_stock['recherche_publique'] == 4
    texte = ' '.join(re.sub(r'\n>\s?', ' ', (RACINE / 'docs' / 'METHODOLOGIE.md').read_text(encoding='utf-8')).split())
    assert 'en sensibilité seulement' in texte
