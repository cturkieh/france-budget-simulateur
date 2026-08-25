"""
Corridor de calibration v0.6.0 — statu quo vs tendanciel officiel.

Référence : Jaravel X., Ragot X., Tavernier J.-L., Valla N. (2026), « Mission
sur la transparence des finances publiques — Situation tendancielle des
finances publiques à horizon 2030 », avec l'appui de l'IGF, juillet 2026
(commandée par les ministres Lescure et Amiel — PAS « Matignon »).
Valeurs littérales des Tableaux 3/4/5/6. Même convention stock-flux que le
moteur (ΔDette = déficit, note 3 p. -14-).

Objet comparé : le scénario « Budget 2026 voté » (statu quo du site) TEL QU'IL
EST PUBLIÉ — la mission suppose la cible 2026 (déficit 5,0 %) atteinte par la
loi de finances, puis politique inchangée.

Sur les retraites, les deux objets décrivent désormais la même chose sans
aucun aménagement : la mission retient « suspension de la réforme des retraites
jusqu'en 2028 » PUIS la reprise vers 64 ans, et c'est exactement ce que rend
``constants.retraites_ref_age_ans(year)`` — la référence légale que le moteur
applique quand aucun âge n'est posé (item I3). Le scénario figeait
``age_depart = 62,75`` sur tout l'horizon, ce qui ne décrit plus « la politique
votée » depuis I3 mais « je suspends la réforme DÉFINITIVEMENT » : une mesure,
pas un tendanciel, facturée jusqu'à +4,70 pt de dette 2035 CONTRE le scénario
de référence. La clé a été retirée de `scenarios.json` (clôture de la revue du
lot 3) ; ``test_le_scenario_publie_suit_le_calendrier_legal`` verrouille ce
retrait, pour que le corridor ne puisse plus être remis en état de comparer
deux objets différents.

Tolérances (resserrées post-revue adverse 24/08, repricing linéaire demi-vie
4 ans en place — écarts mesurés : taux ≤ 0,17 pt, charge ≤ 3 Md€, dette
≤ +2,5 pt, déficit ≤ +0,69 pt) : le résidu vient (a) du déflateur réalisé
~1,0 %/an (Phillips tirée par le gap négatif) vs ~1,5 % implicite mission —
recalage = passe de sourcing dédiée (backlog v0.6.1) — et (b) du sentier
primaire. Les bornes verrouillent la trajectoire contre toute régression
(revenir au taux v0.5.1 sort la charge de ~40 Md€ ; revenir au repricing
géométrique 1/8 sort le taux apparent de ~0,3 pt).
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from budget_simulator.simulator import BudgetSimulatorV45

# Cibles mission (Tableaux 3/4/5/6), années 2026-2030.
CIBLE_DEFICIT = [-5.00, -5.88, -6.21, -6.57, -6.76]
CIBLE_DETTE = [118.4, 121.4, 124.2, 127.3, 130.5]
CIBLE_CHARGE = [78, 89, 101, 112, 124]
CIBLE_TAUX = [2.2, 2.4, 2.7, 2.9, 3.1]

# Tolérances (cf. docstring : l'écart déflateur documenté domine).
TOL_DEFICIT = 0.9   # pt de PIB (mesuré ≤ 0,69)
TOL_DETTE = 3.0     # pt de PIB (mesuré ≤ 2,5)
TOL_CHARGE = 5.0    # Md€ (mesuré ≤ 3)
TOL_TAUX = 0.25     # pt (mesuré ≤ 0,17)


def _mesures_publiees():
    """Mesures du scénario de référence, LUES SANS AUCUN AMÉNAGEMENT."""
    # Résolution ROBUSTE (revue adverse 24/08 : abspath ne suit pas le symlink
    # tests/ du parent → le test se skippait dans TOUTES les CI). Ordre :
    # (1) BUDGETLAB_SCENARIOS_JSON — l'env var que le conftest parent expose
    #     PRÉCISÉMENT pour ce piège ;
    # (2) chemin relatif au fichier RÉSOLU (Path.resolve suit les symlinks).
    import pathlib
    candidats = []
    env = (os.environ.get('BUDGETLAB_SCENARIOS_JSON') or '').strip()
    if env:
        candidats.append(pathlib.Path(env))
    racine = pathlib.Path(__file__).resolve().parent.parent
    candidats.append(racine / '..' / '..' / 'frontend-react' / 'src' / 'data' / 'scenarios.json')
    for chemin in candidats:
        if chemin.exists():
            with open(chemin) as f:
                return json.load(f)['plf_2026']['apiMeasures']
    pytest.skip("scenarios.json introuvable (fork moteur public seul) — corridor non exécutable")


@pytest.fixture(scope='module')
def trajectoire():
    df, budget, _ = BudgetSimulatorV45(
        periods=10, mesures=_mesures_publiees()).simulate()
    return df, budget


def test_le_scenario_publie_suit_le_calendrier_legal():
    """Garde permanente : « Budget 2026 (voté) » ne pose PAS d'âge de départ.

    Poser un âge, fût-ce la valeur du gel, y inscrit une MESURE — la
    suspension définitive de la réforme — là où le scénario doit décrire la
    loi votée, c'est-à-dire le calendrier légal lui-même. Depuis l'item I3 le
    moteur applique ce calendrier quand la clé est absente, et alors seulement
    l'impact est rigoureusement nul chaque année.

    Cette garde tient AUSSI le corridor honnête : sans elle, on pourrait le
    faire repasser au vert en neutralisant la clé côté test au lieu de côté
    donnée — c'est exactement ce que faisait le contournement retiré ici."""
    retraites = _mesures_publiees().get('retraites', {})
    assert 'age_depart' not in retraites, (
        "plf_2026 pose un age_depart : le scénario « la politique votée » "
        "décrirait une suspension définitive de la réforme des retraites, "
        "mesurée jusqu'à +4,70 pt de dette 2035 contre lui-même")


def test_corridor_deficit(trajectoire):
    df, _ = trajectoire
    for i in range(1, 6):
        ecart = df['Déficit/PIB %'].iloc[i] - CIBLE_DEFICIT[i - 1]
        assert abs(ecart) <= TOL_DEFICIT, \
            f"{int(df['Année'].iloc[i])} : déficit {df['Déficit/PIB %'].iloc[i]:.2f} vs mission {CIBLE_DEFICIT[i-1]} (Δ{ecart:+.2f})"


def test_corridor_dette(trajectoire):
    df, _ = trajectoire
    for i in range(1, 6):
        ecart = df['Dette/PIB %'].iloc[i] - CIBLE_DETTE[i - 1]
        assert abs(ecart) <= TOL_DETTE, \
            f"{int(df['Année'].iloc[i])} : dette {df['Dette/PIB %'].iloc[i]:.1f} vs mission {CIBLE_DETTE[i-1]} (Δ{ecart:+.1f})"


def test_corridor_charge_dette(trajectoire):
    _, b = trajectoire
    for i in range(1, 6):
        ecart = b['Intérêts_Dette'].iloc[i] - CIBLE_CHARGE[i - 1]
        assert abs(ecart) <= TOL_CHARGE, \
            f"charge {b['Intérêts_Dette'].iloc[i]:.0f} Md€ vs mission {CIBLE_CHARGE[i-1]} (Δ{ecart:+.0f})"


def test_corridor_taux_apparent(trajectoire):
    """Le taux apparent doit suivre la remontée de la mission (2,2 → 3,1 %) —
    ancre 2026 serrée (±0,1, point de calage), suite dans la tolérance large."""
    _, b = trajectoire
    assert abs(b['Taux_Intérêt %'].iloc[1] - CIBLE_TAUX[0]) <= 0.10
    for i in range(2, 6):
        ecart = b['Taux_Intérêt %'].iloc[i] - CIBLE_TAUX[i - 1]
        assert abs(ecart) <= TOL_TAUX
    # Et la remontée est bien monotone (effet boule de neige non étouffé).
    taux = [b['Taux_Intérêt %'].iloc[i] for i in range(1, 6)]
    assert all(t2 > t1 for t1, t2 in zip(taux, taux[1:])), f"taux apparent non croissant : {taux}"
