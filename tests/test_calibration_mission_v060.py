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

--------------------------------------------------------------------------
RÉSIDU (a) DÉFLATEUR : FERMÉ EN v0.6.1 LOT 8 — ET CE QU'IL CACHAIT
--------------------------------------------------------------------------
La version précédente de cette docstring annonçait deux résidus : « (a) le
déflateur réalisé ~1,0 %/an vs ~1,5 % implicite mission — recalage = passe
de sourcing dédiée — et (b) le sentier primaire ». Le lot 8 (Phillips
ancrée, items I12-I15) EST cette passe. Fermer (a) a montré que la v0.6.0
tenait la dette de la mission par la COMPENSATION DE DEUX ERREURS DE SENS
OPPOSÉ, mesurée ici :

    2030, écart à la mission        v0.6.0     v0.6.1 lot 8
    PIB nominal (dénominateur)      −3,09 %      −0,57 %
    solde primaire (numérateur)     +0,53 pt     +0,69 pt
    ⇒ dette/PIB                     +2,41 pt     −1,66 pt

Un PIB nominal 3 % trop bas gonflait mécaniquement le ratio de dette, ce qui
annulait un solde primaire trop favorable. Le lot 8 supprime la première
erreur — le déflateur réalisé passe de 0,89 à 1,40 % de moyenne, écart
annuel ≤ 0,17 pt — et laisse la seconde APPARENTE au lieu de compensée.
C'est un progrès de diagnostic, pas une régression : le corridor de dette
s'est resserré (±2,41 → ±1,68 pt, tolérance abaissée en conséquence) et
celui de déficit s'est ouvert (+0,71 → +1,00 pt) parce qu'il porte désormais
le résidu (b) SEUL.

--------------------------------------------------------------------------
RÉSIDU (b) SENTIER PRIMAIRE — les deux composantes, mesurées
--------------------------------------------------------------------------
1. PRÉ-EXISTANT : le tendanciel de dépense primaire du moteur est moins
   dynamique que celui de la mission. Écart déjà de +0,73 pt en 2029 AVANT
   le lot 8. Ce n'est pas Phillips, c'est le bloc dépenses.
2. INSTRUIT par le lot 8 lui-même (arbitrage I17) : la variable `inflation`
   est calée sur le DÉFLATEUR du PIB (INSEE tranche : c'est lui qui importe
   pour le taux d'emprunt réel des APU), alors que l'indexation LÉGALE des
   pensions suit l'IPC hors tabac. Le biais résiduel déclaré, −0,15 pt/an,
   est CONSERVATEUR : il minore la dépense indexée. Sa taille attendue sur
   ~1 800 Md€ de dépense primaire, ~2,5 Md€/an, cumulée sur quatre ans,
   ≈ 0,3 pt de PIB — soit exactement le déplacement mesuré du déficit 2029
   (+0,71 → +1,00 pt). Le résidu du corridor de déficit n'est donc pas un
   inconnu : c'est le prix, chiffré, d'un arbitrage écrit.

Le solde primaire est désormais borné PAR SON PROPRE TEST
(``test_corridor_solde_primaire``), plus serré que ce que le corridor de
déficit tolérait implicitement : la contrainte totale sur le moteur est
resserrée, pas relâchée.

--------------------------------------------------------------------------
RÉSIDU (b) : RÉDUIT DE MOITIÉ AU LOT 9 — et la cause n'est pas le moteur
--------------------------------------------------------------------------
Le lot 9 re-source le scénario `plf_2026` lui-même. Il ne touche AUCUNE
constante du moteur : il retire du SCÉNARIO l'effort que la loi de finances
2026 ne chiffre pas (réforme des agences, fraude fiscale et sociale au régime,
coupe fantôme de la recherche, économie de gestion de dette sans base) et
encode les recettes votées qui manquaient. Or la mission décrit « la cible
2026 atteinte par la loi, PUIS POLITIQUE INCHANGÉE » : un scénario qui
poursuivait un ajustement non voté ne décrivait tout simplement pas le même
objet qu'elle. Effet mesuré, sans recalibrage d'aucune sorte :

    écart max à la mission          lot 8      lot 9
    déficit                        1,00 pt    0,72 pt
    dette                          1,68 pt    1,27 pt
    charge d'intérêts              4,4 Md€    3,0 Md€
    taux apparent                  0,22 pt    0,18 pt
    solde primaire                 0,91 pt    0,65 pt

Le résidu (b) était donc pour partie un écart d'OBJET, pas un écart de modèle.
Ce qu'il en reste — le tendanciel de dépense primaire moins dynamique que celui
de la mission, et le biais d'indexation I17 déclaré conservateur — appartient
bien au bloc dépenses.

Tolérances — écarts mesurés v0.6.1 lot 9 : déflateur ≤ 0,18 pt, taux
≤ 0,18 pt, charge ≤ 3,0 Md€, dette ≤ 1,27 pt, primaire ≤ 0,65 pt, déficit
≤ 0,72 pt. Les bornes verrouillent la trajectoire contre toute régression
(revenir au taux v0.5.1 sort la charge de ~40 Md€ ; revenir au repricing
géométrique 1/8 sort le taux apparent de ~0,3 pt ; revenir à la Phillips non
ancrée sort le déflateur de ~0,6 pt/an).
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
# Déflateur du PIB : RAA 2026 Tableau n° 2 (2026-2029, avis HCFP n° 2026-3
# du 17/04/2026) prolongé par la mission IGF pour 2030. Le point 2026 (1,3 %)
# est le seul où deux primaires indépendantes coïncident exactement (RAA
# p. 12 « le déflateur du PIB progresserait de +1,3 % et le PIB nominal
# croîtrait de +2,2 % » ; mission IGF T6, nominal 2026 = 2,2 %). 2030 est
# DÉFENDABLE, pas SOLIDE (§B.2 item 17 : aucune institution ne publie le
# déflateur France au-delà de 2029).
CIBLE_DEFLATEUR = [1.3, 1.6, 1.6, 1.5, 1.5]
# Croissance nominale implicite de la mission (Tableau 6).
CIBLE_NOMINAL = [2.2, 2.7, 2.8, 2.6, 2.6]
# Solde PRIMAIRE de la mission, en % du PIB. ⚠️ Série DÉRIVÉE, non publiée
# telle quelle : solde primaire = déficit (T3) + charge d'intérêts (T5),
# rapporté au PIB nominal reconstruit en chaînant CIBLE_NOMINAL sur le PIB
# 2025 du moteur (2 991 Md€). Elle est déclarée dérivée, pas citée comme
# tableau de la mission.
CIBLE_PRIMAIRE = [-2.45, -3.05, -3.08, -3.19, -3.11]

# Tolérances.
# TOL_DEFICIT : mesuré 1,00 pt (2029). Marge de 0,10 pt DÉLIBÉRÉMENT mince —
# le sentier primaire est l'item suivant du chantier, pas un résidu à
# absorber. Le budget de cette borne se lit comme la somme de ses deux
# composantes, chacune bornée séparément : primaire ≤ 1,0 pt + charge
# ≤ 5 Md€ (≈ 0,15 pt de PIB).
# TOUTES RESSERRÉES au lot 9 (sourcing du scénario de référence). Le motif est
# le même pour les cinq et il est structurel, pas cosmétique : la mission décrit
# « la cible 2026 atteinte par la loi de finances, PUIS POLITIQUE INCHANGÉE »,
# alors que le scénario publié encodait +25,5 Md€/an d'effort en 2030 dont
# aucune loi ne porte les neuf dixièmes. En retirant cet effort non voté, le
# scénario se met enfin à décrire le même objet que la mission — et chaque
# écart se referme, sans qu'aucune constante sourcée du moteur ne soit touchée.
TOL_DEFICIT = 0.9   # pt de PIB (mesuré 0,72 ; lot 8 : 1,10 pour 1,00 mesuré)
TOL_DETTE = 1.6     # pt de PIB (mesuré 1,27 ; lot 8 : 2,20 pour 1,68)
TOL_CHARGE = 3.5    # Md€ (mesuré 3,00 ; lot 8 : 5,0 pour 4,4)
TOL_TAUX = 0.22     # pt (mesuré 0,18 ; lot 8 : 0,25 pour 0,22)
# Le déflateur est la SEULE borne non resserrée : mesuré 0,18 contre 0,17 au
# lot 8. Un scénario moins austère désinfle un peu moins — l'effet est dans le
# bon sens (la moyenne 2026-2030 passe de 1,400 à 1,412, elle décolle du
# plancher de la fourchette du dossier signalé au lot 8), mais l'écart annuel
# maximal, lui, s'ouvre de 0,01 pt. Marge restante : 0,02 pt, mince et déclarée.
TOL_DEFLATEUR = 0.2  # pt (I16 test-propriété 3 ; mesuré 0,18)
TOL_NOMINAL = 0.2    # pt, sur la MOYENNE (mesuré 0,106 ; cf. test dédié)
TOL_PRIMAIRE = 0.8   # pt de PIB (mesuré 0,65 ; lot 8 : 1,0 pour 0,91)


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


def test_corridor_solde_primaire(trajectoire):
    """Borne NOUVELLE (v0.6.1 lot 8) : isole le résidu (b).

    Tant que le déflateur était faux, l'écart de solde primaire était
    compensé dans la dette et n'avait donc pas de test propre : le corridor
    de déficit l'absorbait mélangé à l'erreur de dénominateur. Il est
    maintenant borné pour lui-même, plus serré (1,0 pt) que ce que le
    corridor de déficit tolère (1,1 pt). Le sens de l'écart est CONSTANT et
    connu : le moteur est plus favorable que la mission (dépense primaire
    moins dynamique + biais d'indexation I17 déclaré conservateur)."""
    df, b = trajectoire
    for i in range(1, 6):
        primaire = (df['Déficit'].iloc[i] + b['Intérêts_Dette'].iloc[i]) / df['PIB'].iloc[i] * 100
        ecart = primaire - CIBLE_PRIMAIRE[i - 1]
        assert abs(ecart) <= TOL_PRIMAIRE, (
            f"{int(df['Année'].iloc[i])} : solde primaire {primaire:.2f} % "
            f"vs mission {CIBLE_PRIMAIRE[i-1]} (Δ{ecart:+.2f})")


def test_corridor_deflateur(trajectoire):
    """Le déflateur du PIB réalisé suit la cible officielle (v0.6.1 lot 8).

    C'est la cible que la v0.6.0 manquait de 0,6 pt/an (0,89 % réalisé vs
    1,50 % de moyenne officielle, −3,14 pt cumulés sur cinq ans) tout en
    reproduisant la dette de la mission : quelque chose compensait. La
    passe Phillips (I12-I15) referme l'écart PAR LA FORME et le NIVEAU, pas
    par un calage sur la dette."""
    df, _ = trajectoire
    for i in range(1, 6):
        ecart = df['Inflation %'].iloc[i] - CIBLE_DEFLATEUR[i - 1]
        assert abs(ecart) <= TOL_DEFLATEUR, (
            f"{int(df['Année'].iloc[i])} : déflateur {df['Inflation %'].iloc[i]:.2f} % "
            f"vs cible {CIBLE_DEFLATEUR[i-1]} (Δ{ecart:+.2f})")
    # Fourchette du dossier, reprise telle quelle. À déclarer : la moyenne
    # mesurée vaut EXACTEMENT 1,400 — la calibration est au PLANCHER de la
    # fourchette, ce n'est pas un confort. Deux causes identifiées, aucune
    # corrigeable sans sortir du périmètre : (i) l'année 2026 part de la
    # graine d'inertie INFLATION_BASE (1,0 %) avec ρ = 0,50, donc à 1,22 %
    # là où la reproduction standalone du dossier démarre à l'ancrage ;
    # (ii) l'output gap du moteur se referme plus lentement que la décroissance
    # géométrique de cette reproduction. Toute correction ultérieure qui
    # abaisse le déflateur rougira ici — c'est l'objet de la borne.
    moyenne = sum(df['Inflation %'].iloc[i] for i in range(1, 6)) / 5
    assert 1.40 <= moyenne <= 1.60, (
        f"déflateur moyen 2026-2030 = {moyenne:.3f} % hors [1,40 ; 1,60]")


def test_corridor_croissance_nominale(trajectoire):
    """La croissance nominale MOYENNE tient le corridor de la mission.

    Sur la MOYENNE et non année par année, et c'est un constat mesuré, pas
    un confort : le résidu annuel ne vient pas du déflateur (verrouillé à
    ±0,2 pt par le test précédent) mais de la croissance RÉELLE du moteur,
    qui oscille (mesuré 2026-2030 : 1,12 / 1,15 / 0,82 / 1,36 / 0,75 %) là
    où le sentier de la mission est lisse (~0,9 / 1,1 / 1,2 / 1,1 / 1,1 %).
    Cette oscillation appartient au bloc croissance — le lot 8 ne le touche
    pas (I18) — et elle se compense d'une année sur l'autre : c'est le
    CUMUL nominal qui porte le dénominateur du ratio de dette, donc le
    cumul qui doit tenir. Un test annuel à ±0,2 pt ici ne mesurerait pas
    Phillips, il mesurerait le bloc croissance sous un faux nom."""
    df, _ = trajectoire
    nominal = [df['Croissance %'].iloc[i] + df['Inflation %'].iloc[i] for i in range(1, 6)]
    moyenne = sum(nominal) / 5
    cible = sum(CIBLE_NOMINAL) / 5
    assert abs(moyenne - cible) <= TOL_NOMINAL, (
        f"croissance nominale moyenne {moyenne:.2f} % vs mission {cible:.2f} % "
        f"(sentier mesuré : {[round(x, 2) for x in nominal]})")


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
