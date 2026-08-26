"""Courbe de Phillips ANCRÉE et déflateur — v0.6.1 lot 8 (items I12 à I18).

Ce que ce module verrouille, et pourquoi.

--------------------------------------------------------------------------
1. LA FORME (I12/R1) — correction d'algèbre, pas de calibration
--------------------------------------------------------------------------
Forme v0.6.0 : ``π_t = (1−ρ)·π* + ρ·π_{t−1} + κ·gap_t`` avec κ = 0,35 hors
de l'ancrage. Point fixe pour un gap constant :

    π̄ = π* + [κ/(1−ρ)]·gap = π* + 0,70·gap   (avec ρ = 0,50)

Le nombre lisible dans le code (0,35) N'ÉTAIT PAS la grandeur estimée par la
littérature : la grandeur homologue de la « pente de moyen terme » valait
0,35/0,50 = 0,70, jamais écrite nulle part et sans source. C'est le MÊME
défaut de forme que l'intercept AR(1) ≠ point fixe corrigé en v0.3.0,
déplacé d'un terme : ρ y jouait le rôle de multiplicateur caché de la pente.

Forme v0.6.1 : ``π_t = (1−ρ)·(π* + κ_LR·gap_t) + ρ·π_{t−1}`` — exactement
l'ancienne avec κ = κ_LR·(1−ρ). Le paramètre du code devient DIRECTEMENT la
pente de moyen terme, et ρ redevient un simple paramètre de vitesse
(cf. ``test_moyenne_invariante_a_l_inertie``).

--------------------------------------------------------------------------
2. LA PENTE (I13/R2) — un choix de calibration ENCADRÉ, pas une estimation
--------------------------------------------------------------------------
``PHILLIPS_PENTE_MT = 0,20``. À déclarer comme tel partout (§B.2 item 14) :
**il n'existe pas d'estimation publiée de la pente de Phillips sur la France
seule, sur l'output gap**. Les deux bornes qui l'encadrent :

- Banque de France, Berson, de Charsonville, Diev, Faubert, Ferrara,
  Guilloux-Nefussi, Kalantzis, Lalliard, Matheron, Mogliani (2018), « La
  courbe de Phillips existe-t-elle encore ? », *Rue de la Banque* n° 56,
  fév. 2018, T1 et graphique G3 — pente de moyen terme 4·c₂/(1−c₁) ≈ 0,40
  (zone euro, IPCH, trimestriel 1999-2017) ;
- BCE, Beschin, Paredes, Polichetti, Renault (2025), *The slope of the euro
  area price Phillips curve: evidence from regional data*, ECB WP n° 3133,
  oct. 2025 — ≈ 0,065 / 0,041 / 0,007 converti sur l'output gap selon le jeu
  d'effets fixes.

Motif du 0,20 : dans les scénarios français de référence l'output gap est
négatif sur tout l'horizon, donc sur le segment PLAT au sens de
Benigno & Eggertsson (NBER WP 31197) — régime où les estimations avec
anticipations contrôlées (0,05-0,12) sont les plus pertinentes. Retenir 0,40
(valeur tous régimes) sur-punirait la conjoncture basse.

--------------------------------------------------------------------------
3. LE NIVEAU (I14/R3 et I15/R4)
--------------------------------------------------------------------------
``OUTPUT_GAP_INITIAL`` et ``INFLATION_STRUCTURELLE`` : sources dans
``constants.py``, à côté des valeurs. Ici on ne teste que l'invariant de
structure (source unique, pas de littéral dupliqué) et le résultat mesuré.

--------------------------------------------------------------------------
4. CE QUE CE LOT NE FAIT PAS (I18) — à ne pas « réparer » par mégarde
--------------------------------------------------------------------------
- Les termes ``effort_budgetaire`` (−0,12 / +0,08) restent en place : non
  sourcés, asymétriques et en double-comptage partiel avec le canal output
  gap — trois défauts réels, donc une instruction à eux seuls (v0.6.2).
- Aucune non-linéarité en L inversé : elle est sourcée mais **asymétrique par
  construction** (plate en bas, raide en haut), donc elle retirerait la
  désinflation aux programmes de consolidation tout en facturant le surcoût
  aux programmes d'expansion. ``test_symetrie_de_la_courbe`` est la garde
  anti-régression correspondante.
"""
import inspect
import json
import os
import pathlib
import re
from unittest.mock import patch

import pytest

from budget_simulator import constants
from budget_simulator.engine import inflation as inflation_mod
from budget_simulator.simulator import BudgetSimulatorV45


# --- Outillage de mesure du point fixe ------------------------------------

_ETAT_NEUTRE = {
    'unemployment_gap': 0.0,   # neutralise les deux régimes défla/inflationnistes
    'effort_budgetaire': 0.0,  # neutralise les termes I18 laissés en place
    'tva_impact': 0.0,
}


def _point_fixe(output_gap, inertia=None, iterations=200):
    """π̄ : l'inflation vers laquelle converge le régime à gap CONSTANT.

    Mesurée à travers ``calculate_inflation`` COMPLET (garde-fous BCE
    compris), pas seulement le noyau : un point fixe qui ne tiendrait que
    parce qu'un clip le tient ne serait pas un point fixe du modèle.
    L'année 1 est utilisée pour rester hors du gate ``year == 2`` du
    pass-through TVA (source unique du gate, cf. ``inflation.py``).
    """
    sim = BudgetSimulatorV45(periods=1)
    if inertia is not None:
        sim.economic_coeffs['inflation_inertia'] = inertia
    sim.inflation_precedente = constants.INFLATION_BASE
    etat = {'output_gap': output_gap, **_ETAT_NEUTRE}
    valeur = sim.inflation_precedente
    with patch('numpy.random.normal', return_value=0.0):
        for _ in range(iterations):
            valeur = sim.calculate_inflation(year=1, economic_state=etat)
            sim.inflation_precedente = valeur
    return valeur


# --- I12/R1 — la forme ----------------------------------------------------

def test_point_fixe_a_gap_nul_egale_l_inflation_structurelle():
    """π̄(gap = 0) == INFLATION_STRUCTURELLE, à 1e-9.

    C'est la définition même d'une courbe ANCRÉE : à écart d'activité nul,
    le régime converge vers la tendancielle, sans résidu."""
    assert _point_fixe(0.0) == pytest.approx(constants.INFLATION_STRUCTURELLE, abs=1e-9)


def test_pente_de_moyen_terme_est_le_parametre_du_code():
    """[π̄(+1 pt) − π̄(−1 pt)] / 2 pt == PHILLIPS_PENTE_MT.

    C'est LE test qui distingue les deux formes : avec la forme v0.6.0, la
    pente observée valait κ/(1−ρ), soit le double du paramètre écrit dans le
    code à ρ = 0,50. Désormais le paramètre EST la pente."""
    haut = _point_fixe(+0.01)
    bas = _point_fixe(-0.01)
    pente = (haut - bas) / 0.02
    assert pente == pytest.approx(constants.PHILLIPS_PENTE_MT, abs=1e-6), (
        f"pente de moyen terme observée {pente:.4f} vs paramètre "
        f"{constants.PHILLIPS_PENTE_MT} — la forme n'est plus ancrée "
        f"(le paramètre du code doit être DIRECTEMENT la pente)")


def test_l_inertie_est_une_vitesse_pas_un_niveau():
    """ρ ne doit plus déplacer le NIVEAU, seulement la vitesse d'approche.

    C'est le corollaire testable de la forme ancrée, et la propriété qui
    sépare EXACTEMENT les deux formes. Contrefactuel mesuré (forme v0.6.0
    remontée à l'identique, gap initial −1,5 %, ρ = 0,25 contre ρ = 0,50) :

        fenêtre            v0.6.0     v0.6.1
        moyenne 2026-2030  0,116 pt   0,062 pt
        moyenne 2031-2035  0,152 pt   0,010 pt
        année 2035         0,130 pt   0,000 pt

    Sous l'ancienne forme l'écart NE MOURAIT PAS — il croissait avec
    l'horizon, signature d'un effet de niveau permanent (ρ multipliait la
    pente). Sous la forme ancrée il est confiné au transitoire : le moteur
    part d'une graine d'inertie (``INFLATION_BASE``, 1,0 %) située sous
    l'ancrage, et ρ ne décide que de la vitesse à laquelle on y monte.

    Le test ne borne donc PAS le transitoire par un nombre choisi : il
    vérifie que le résidu DÉCROÎT et s'annule, ce qui est infalsifiable
    par un simple élargissement de tolérance."""
    sentiers = {}
    for rho in (0.25, 0.50):
        sim = BudgetSimulatorV45(periods=10)
        sim.economic_coeffs['inflation_inertia'] = rho
        df, _, _ = sim.simulate()
        sentiers[rho] = [df['Inflation %'].iloc[i] for i in range(1, 11)]

    def _moyenne(rho, debut, fin):
        return sum(sentiers[rho][debut:fin]) / (fin - debut)

    transitoire = abs(_moyenne(0.25, 0, 5) - _moyenne(0.50, 0, 5))
    etabli = abs(_moyenne(0.25, 5, 10) - _moyenne(0.50, 5, 10))
    terminal = abs(sentiers[0.25][-1] - sentiers[0.50][-1])

    assert etabli < 0.05, (
        f"moyenne 2031-2035 : écart {etabli:.3f} pt entre ρ=0,25 et ρ=0,50 — "
        f"ρ pèse encore sur le NIVEAU une fois le transitoire éteint")
    assert terminal < 0.01, (
        f"année 2035 : écart {terminal:.3f} pt — le régime établi doit être "
        f"strictement indépendant de ρ")
    assert etabli < transitoire / 3, (
        f"le résidu ne s'éteint pas : transitoire {transitoire:.3f} pt → "
        f"établi {etabli:.3f} pt. Sous la forme NON ancrée il croissait "
        f"(0,116 → 0,152 pt mesurés)")


# --- I12, test-propriété 5 : la fenêtre 2026-2030 ------------------------
# TROISIÈME ÉCART AU BRIEF, ajouté à la clôture de la revue adverse
# (2026-08-26). Le lot 8 en déclarait deux ; celui-ci manquait, et il est le
# plus lourd des trois parce qu'il porte sur une propriété que le brief
# DEMANDAIT et que le moteur livré FAIT ÉCHOUER.
#
# Brief I12, propriété 5 : « la moyenne 2026-2030 varie de moins de 0,05 pt
# quand ρ passe de 0,25 à 0,50 ». Mesuré sur le moteur livré : 0,0620 pt
# (1,5040 → 1,4420 en statu quo). Le test livré au lot 8, lui, déplaçait la
# fenêtre sur 2031-2035 (0,010 pt) : la fenêtre du brief — qui est AUSSI celle
# du corridor de déflateur — n'était bornée par rien.
#
# POURQUOI LE BRIEF SE TROMPE DE 3,4× (0,02 pt annoncé, 0,062 mesuré), et
# pourquoi ce n'est pas un défaut de la forme ancrée : la fenêtre 2026-2030
# EST le transitoire. Le moteur part de la graine d'inertie INFLATION_BASE
# (1,0 %) et converge vers son ancrage, π* + κ_LR·gap ≈ 1,46 % — 0,46 pt plus
# haut. ρ ne décide de rien d'autre que de la VITESSE de cette montée ; sur
# cinq ans de montée, une vitesse déplace évidemment la moyenne. La propriété
# « ρ est une vitesse et non un niveau » est donc vraie (elle se vérifie une
# fois le transitoire éteint : 0,010 pt sur 2031-2035, 0,000 pt en 2035) et
# la propriété 5, telle qu'elle est écrite, ne la teste pas.
#
# CE QUI DOIT ÊTRE BORNÉ SUR CETTE FENÊTRE, ET NE L'ÉTAIT PAS : la
# CONCLUSION que le brief tire de sa propriété 5 — « ρ = 0,50 est acceptable
# et de second ordre, ne pas dépenser de crédibilité sur ce paramètre ». Elle
# est vérifiable directement, et c'est ce que fait le test ci-dessous : la
# conformité de la calibration au corridor du dossier ne doit dépendre
# d'AUCUNE valeur plausible de ρ. C'est une garde plus forte que la
# propriété 5, pas plus faible — la propriété 5 borne un écart entre deux
# variantes, celle-ci borne la variante la PIRE.

_FOURCHETTE_DEFLATEUR = (1.40, 1.60)  # I16, test-propriété 3 (dossier v0.6.1)


def _mesures_publiees():
    """Scénario de référence, LU SANS AMÉNAGEMENT (même résolution robuste que
    les deux autres fichiers qui en dépendent : piège resolve()/symlink)."""
    env = (os.environ.get('BUDGETLAB_SCENARIOS_JSON') or '').strip()
    racine = pathlib.Path(__file__).resolve().parent.parent
    for chemin in ([pathlib.Path(env)] if env else []) + [
            racine / '..' / '..' / 'frontend-react' / 'src' / 'data' / 'scenarios.json']:
        if chemin.exists():
            return json.loads(chemin.read_text(encoding='utf-8'))['plf_2026']['apiMeasures']
    return None


def _moyenne_deflateur_2026_2030(rho, mesures=None):
    sim = BudgetSimulatorV45(periods=10, mesures=mesures) if mesures \
        else BudgetSimulatorV45(periods=10)
    sim.economic_coeffs['inflation_inertia'] = rho
    df, _, _ = sim.simulate()
    return sum(df['Inflation %'].iloc[i] for i in range(1, 6)) / 5


@pytest.mark.parametrize('rho', [0.20, 0.25, 0.30, 0.40, 0.50])
def test_la_conformite_du_corridor_2026_2030_ne_depend_pas_de_l_inertie(rho):
    """Aucune valeur plausible de ρ ne sort la calibration du corridor.

    C'est la forme testable du corollaire d'I12 (« ρ est de second ordre »),
    sur la fenêtre du brief. Elle rougirait si la calibration dérivait vers
    le bas OU si quelqu'un montait ρ : à ρ = 0,60 la moyenne tombe à 1,372 %
    et sort du corridor — la garde n'est donc pas vacue.

    MARGE À DÉCLARER, et elle est mince : à la valeur LIVRÉE (ρ = 0,50) la
    moyenne vaut 1,412 % sur le scénario publié, soit 0,012 pt au-dessus du
    plancher. Le lot 8 l'écrivait déjà pour ρ seul (« EXACTEMENT 1,400 ») ;
    ce qui manquait, c'est que cette marge est du même ordre de grandeur que
    la sensibilité à ρ (0,062 pt). Autrement dit : la conformité tient, mais
    elle ne tient pas AVEC BEAUCOUP DE MARGE, et le paramètre qui la
    mangerait est celui que le dossier invitait à ne pas regarder."""
    bas, haut = _FOURCHETTE_DEFLATEUR
    publiees = _mesures_publiees()
    objets = [('statu quo', None)]
    if publiees is not None:  # fork moteur public seul : statu quo seul
        objets.append(('scénario publié', publiees))
    for etiquette, mesures in objets:
        moyenne = _moyenne_deflateur_2026_2030(rho, mesures)
        assert bas <= moyenne <= haut, (
            f"{etiquette}, ρ={rho} : déflateur moyen 2026-2030 = "
            f"{moyenne:.4f} % hors [{bas} ; {haut}] — la calibration est "
            f"portée par la valeur d'inertie, pas par le modèle")


def test_la_sensibilite_a_l_inertie_sur_la_fenetre_du_brief_est_publiee():
    """ÉCART AU BRIEF, mesuré et encadré DES DEUX CÔTÉS.

    Le brief annonçait 0,02 pt et exigeait < 0,05 ; le moteur en fait 0,062.
    L'encadrement est bilatéral à dessein : une borne haute seule se
    desserrerait à la prochaine dérive, une borne basse seule laisserait
    passer une correction qui, en éteignant le transitoire, ferait disparaître
    l'écart sans que personne ne s'en aperçoive. Toute évolution de ce nombre
    doit être un acte, pas un effet de bord."""
    ecart = abs(_moyenne_deflateur_2026_2030(0.25)
                - _moyenne_deflateur_2026_2030(0.50))
    assert 0.055 <= ecart <= 0.070, (
        f"sensibilité de la moyenne 2026-2030 à ρ = {ecart:.4f} pt "
        f"(mesurée 0,0620 au 2026-08-26 ; le brief annonçait 0,02 et "
        f"demandait < 0,05 — écart assumé et déclaré)")


# --- I13/R2 — la pente ----------------------------------------------------

def test_pente_dans_la_fourchette_encadree_et_declaree_non_estimee():
    """0,15 ≤ κ_LR ≤ 0,25, strictement entre les deux bornes publiées.

    §B.2 item 14 : la valeur est un CHOIX DE CALIBRATION encadré, jamais une
    estimation France — aucune n'existe sur l'output gap. Le test verrouille
    l'encadrement (BCE WP 3133 ≈ 0,065 en bas, BdF RdB 56 ≈ 0,40 en haut) et
    la fourchette de travail du dossier."""
    kappa = constants.PHILLIPS_PENTE_MT
    assert 0.15 <= kappa <= 0.25, (
        f"PHILLIPS_PENTE_MT = {kappa} hors de la fourchette 0,15-0,25 du dossier")
    assert 0.065 < kappa < 0.40, (
        "la pente doit rester STRICTEMENT encadrée par les deux bornes "
        "publiées (BCE WP 3133 ≈ 0,065 ; BdF RdB 56 ≈ 0,40)")


# --- I18 / §C.4 — symétrie (garde anti-régression) ------------------------

@pytest.mark.parametrize('x', [0.005, 0.01, 0.02])
def test_symetrie_de_la_courbe(x):
    """π̄(+x) − π* == −(π̄(−x) − π*) : la courbe est symétrique.

    Garde de NEUTRALITÉ (§C.4) : une non-linéarité en L inversé rendrait la
    courbe plate en bas (plus de désinflation pour les programmes de
    consolidation) et raide en haut (surcoût pour les programmes
    d'expansion) — asymétrie politique par construction. Si quelqu'un
    l'introduit un jour, ce test rougit.

    Mesure sur le NOYAU ancré et non sur ``calculate_inflation`` complet :
    les garde-fous BCE sont, eux, délibérément asymétriques (rappel de
    surchauffe à 2,0 % vs plancher accommodant à 0,8 %), et à x = 2 pt le
    point fixe haut vaut exactement 2,00 % — pile sur le seuil de rappel.
    Ce qu'on protège ici est la COURBE, pas la règle monétaire."""
    pi_etoile = constants.INFLATION_STRUCTURELLE
    haut = inflation_mod.point_fixe_phillips_ancree(+x)
    bas = inflation_mod.point_fixe_phillips_ancree(-x)
    assert (haut - pi_etoile) == pytest.approx(-(bas - pi_etoile), abs=1e-12)


# --- I16 test 7 — les garde-fous ne portent pas la calibration ------------

def test_gardes_fous_bce_inertes_en_statu_quo():
    """En statu quo, ni le rappel BCE ni le plancher ne se déclenchent.

    Sinon la calibration serait portée par un clip et non par le modèle.
    C'était le cas en v0.6.0 : avec un déflateur réalisé autour de 0,9 %, le
    plancher accommodant (0,8 %) soutenait artificiellement l'année 1.

    Mesure exacte : on intercepte ``rappel_bce`` (fonction pure, source
    unique de la règle monétaire) et on vérifie qu'elle est l'IDENTITÉ à
    chaque appel. Un test qui se contenterait de borner l'inflation publiée
    serait faux : quand le plancher tire une valeur basse VERS la bande, la
    valeur publiée est dans la bande précisément PARCE QUE le garde a joué.

    Portée exacte, à ne pas surinterpréter : la propriété est verrouillée
    EN STATU QUO. Sur les scénarios publiés, le décompte mesuré passe de
    « 1 à 10 déclenchements sur les 9 scénarios » (v0.6.0) à « 0 sur 8, et
    8 sur ``im_rabot_2029`` » (v0.6.1) — cf. le tableau dans la docstring de
    ``rappel_bce``. Ce résidu est légitime (gap très négatif, le garde-fou
    fait son office) et n'est pas testé ici : il dépendrait de
    ``scenarios.json``, absent d'un fork du moteur seul."""
    appels = []
    original = inflation_mod.rappel_bce

    def _espion(inflation):
        sortie = original(inflation)
        appels.append((inflation, sortie))
        return sortie

    with patch.object(inflation_mod, 'rappel_bce', _espion):
        BudgetSimulatorV45(periods=10).simulate()

    assert appels, "rappel_bce n'a pas été appelée — l'espion ne mesure rien"
    declenches = [(e, s) for e, s in appels if e != s]
    assert not declenches, (
        f"{len(declenches)} déclenchement(s) de garde-fou BCE en statu quo "
        f"sur {len(appels)} années : {[(round(e*100, 3), round(s*100, 3)) for e, s in declenches]} "
        f"(en %) — la calibration serait portée par un clip, pas par le modèle")


# --- I14/R3 + méta-garde — source unique, aucun littéral dupliqué ---------

def test_output_gap_initial_est_une_constante_unique():
    """Le niveau initial de l'output gap vit dans ``constants.py``, une fois.

    En v0.6.0 le littéral ``-0.015`` était écrit DEUX fois dans
    ``simulator.py`` (``__init__`` et ``_reset_state``) et ne portait aucun
    commentaire de source (§B.2 item 19)."""
    assert hasattr(constants, 'OUTPUT_GAP_INITIAL'), (
        "constants.OUTPUT_GAP_INITIAL doit exister : source unique du niveau "
        "initial de l'output gap")
    assert -0.010 <= constants.OUTPUT_GAP_INITIAL <= -0.004, (
        f"OUTPUT_GAP_INITIAL = {constants.OUTPUT_GAP_INITIAL} hors de "
        "l'encadrement des deux primaires : RAA 2026 T2 p. 20 / HCFP "
        "n° 2026-3 (−0,7 %) et FMI Art. IV Table 1 (−0,4 %)")


def test_le_gap_initial_alimente_bien_la_premiere_annee():
    """Le gap lu par la Phillips de 2026 est EXACTEMENT la constante.

    L'année de base (2025) ne passe pas par la récurrence : la valeur posée
    est donc celle qui entre dans la première année simulée. Ce test verrouille
    ce chaînage — sans lui, un déplacement de l'initialisation passerait
    inaperçu."""
    sim = BudgetSimulatorV45(periods=2)
    vus = []
    original = inflation_mod.InflationMixin.calculate_inflation

    def _espion(self, year, economic_state):
        vus.append((year, economic_state['output_gap']))
        return original(self, year, economic_state)

    with patch.object(inflation_mod.InflationMixin, 'calculate_inflation', _espion):
        sim.simulate()

    premier = [gap for annee, gap in vus if annee == 1]
    assert premier, "aucun appel de calculate_inflation en année 1"
    assert premier[0] == pytest.approx(constants.OUTPUT_GAP_INITIAL, abs=1e-12)


_LITTERAUX_INTERDITS = {
    'budget_simulator/engine/inflation.py': (r'0\.35\b', r'0\.015\b'),
    # `0.35` N'EST PAS interdit dans simulator.py : ce fichier porte deux
    # autres paramètres qui valent 0,35 et n'ont rien à voir avec Phillips —
    # le coefficient d'Okun (−0,35, §B.2 item 21 : non recherché dans cette
    # collecte) et le multiplicateur budgétaire `tax_cuts` (0,35, FMI
    # 0,1-0,5). Les interdire ici forcerait un changement hors périmètre du
    # lot 8, ou pire, une garde qui ment sur ce qu'elle protège.
    'budget_simulator/simulator.py': (r'0\.015\b',),
}


@pytest.mark.parametrize('fichier,motifs', sorted(_LITTERAUX_INTERDITS.items()))
def test_meta_garde_aucun_litteral_de_calibration_phillips(fichier, motifs):
    """Méta-garde : les valeurs Phillips ne peuvent revenir en littéral.

    Elles vivent dans ``constants.py`` avec leur source. Les commentaires
    français du moteur écrivent les nombres à la virgule (« 0,35 »), ce
    grep ne vise donc que les littéraux Python (point décimal)."""
    from pathlib import Path
    racine = Path(__file__).resolve().parent.parent
    texte = (racine / fichier).read_text(encoding='utf-8')
    for motif in motifs:
        trouves = [
            f"L{i}: {ligne.strip()}"
            for i, ligne in enumerate(texte.splitlines(), 1)
            if re.search(motif, ligne)
        ]
        assert not trouves, (
            f"littéral de calibration Phillips interdit dans {fichier} "
            f"(motif {motif!r}) : {trouves}")


# --- I17 — la variable unique est calée sur le DÉFLATEUR ------------------

def test_le_role_de_la_variable_inflation_est_declare():
    """La variable unique ``inflation`` sert trois indices différents.

    (i) déflateur du PIB (dénominateur du ratio de dette), (ii) IPC pour le
    pouvoir d'achat, (iii) indice d'indexation des prestations. L'arbitrage
    v0.6.1 est de la caler sur le DÉFLATEUR — INSEE tranche explicitement
    (blog sept. 2022 : « c'est plutôt le déflateur du PIB qui importe pour
    apprécier le taux d'emprunt réel des administrations publiques ») — et
    de DÉCLARER le biais résiduel de −0,15 pt/an sur les deux autres rôles,
    biais conservateur (il minore la dépense indexée ET la perte de pouvoir
    d'achat). Scinder en trois variables est un changement d'architecture
    instruit séparément : ce test verrouille la DÉCLARATION, pas la scission.
    """
    doc = inflation_mod.__doc__ or ''
    for attendu in ('déflateur', '−0,15', 'pouvoir d'"'"'achat', 'indexation'):
        assert attendu in doc, (
            f"la docstring de engine/inflation.py doit déclarer le rôle de la "
            f"variable et son biais résiduel — « {attendu} » absent")


# --- I17 — LE SENS du biais résiduel, mesuré et non plus affirmé ----------
# Clôture de la revue adverse (2026-08-26). Le biais d'indexation était publié
# comme « CONSERVATEUR » dans QUATRE artefacts, dont deux servis au public,
# avec pour justification qu'il « minore la dépense indexée ET la perte de
# pouvoir d'achat ». Les deux effets nommés à l'appui du mot vont pourtant
# DANS LE MÊME SENS, et c'est le sens flatteur : une dépense minorée améliore
# le déficit et la dette — la sortie titre du site — et une perte de pouvoir
# d'achat minorée est un indicateur embelli. Sur un simulateur budgétaire,
# « conservateur » désigne l'erreur qui va contre soi. Celle-ci va pour soi.
#
# Le coin vit ICI et pas dans constants.py : la scission déflateur/IPC n'est
# pas instruite (cf. test_pas_de_scission_prematuree_en_trois_variables, qui
# interdit l'apparition de la constante). Ce n'est pas une calibration du
# moteur, c'est l'instrument de mesure d'une contre-épreuve.
_COIN_IPC_DEFLATEUR = 0.0015  # +0,15 pt/an — écart déflateur − prix conso
# Sources du quantum : INSEE, blog « Inflation : les déflateurs en
# comptabilité nationale », sept. 2022 (−0,1 à −0,2 pt en régime normal) ;
# décomposition officielle 2026 du RAA p. 12 (−0,4 pt de prix de la demande
# intérieure, −0,2 pt de termes de l'échange). DÉFENDABLE, pas SOLIDE (§B).


def _dette_2035_si_indexation_sur_ipc(mesures):
    """Contre-épreuve : la dépense primaire indexée sur l'IPC (= le déflateur
    du moteur + le coin), tout le reste identique.

    C'est ce que l'indexation LÉGALE des pensions suit réellement (IPC hors
    tabac). On enveloppe ``calculate_expenditures`` plutôt que de toucher au
    moteur : la mesure doit être reproductible sans rien livrer."""
    from budget_simulator.engine import expenditures as expenditures_mod

    originale = expenditures_mod.ExpendituresMixin.calculate_expenditures

    def indexee_sur_ipc(self, gdp, inflation, inflation_prev, unemployment,
                        year, output_gap):
        return originale(self, gdp, inflation + _COIN_IPC_DEFLATEUR,
                         inflation_prev + _COIN_IPC_DEFLATEUR, unemployment,
                         year, output_gap)

    expenditures_mod.ExpendituresMixin.calculate_expenditures = indexee_sur_ipc
    try:
        sim = BudgetSimulatorV45(periods=10, mesures=mesures) if mesures \
            else BudgetSimulatorV45(periods=10)
        df, _, _ = sim.simulate()
    finally:
        expenditures_mod.ExpendituresMixin.calculate_expenditures = originale
    return df


def test_le_biais_d_indexation_flatte_la_sortie_titre_du_site():
    """MESURE du sens : indexer sur l'IPC DÉGRADE la dette et le déficit.

    Donc l'arbitrage livré — indexer sur le déflateur — les AMÉLIORE. Ce
    n'est pas une opinion sur le mot « conservateur », c'est une contre-
    épreuve : on refait tourner le moteur avec la dépense primaire indexée
    sur l'indice que la loi suit, et on lit l'écart.

    Mesuré (scénario publié) : déficit 2030 −6,40 → −6,86 (+0,46 pt), déficit
    2035 −10,70 → −11,95 (+1,25 pt) ; dette 2030 129,65 → 130,93 (+1,28 pt),
    dette 2035 159,35 → 164,85 (+5,50 pt). L'ordre de grandeur est cohérent
    avec le chiffrage du projet lui-même : ~1 800 Md€ de dépense primaire ×
    0,15 pt ≈ 2,5 Md€/an, cumulés et capitalisés."""
    for mesures in (None, _mesures_publiees()):
        if mesures is None:
            reference, _, _ = BudgetSimulatorV45(periods=10).simulate()
        else:
            reference, _, _ = BudgetSimulatorV45(periods=10, mesures=mesures).simulate()
        contre = _dette_2035_si_indexation_sur_ipc(mesures)
        ecart_dette = contre['Dette/PIB %'].iloc[10] - reference['Dette/PIB %'].iloc[10]
        ecart_deficit = (reference['Déficit/PIB %'].iloc[10]
                         - contre['Déficit/PIB %'].iloc[10])
        assert ecart_dette > 0, (
            f"la contre-épreuve DOIT dégrader la dette ({ecart_dette:+.2f} pt) : "
            f"si elle l'améliorait, le biais serait bien conservateur et toute "
            f"la déclaration du § I17 serait à réécrire dans l'autre sens")
        assert ecart_deficit > 0, (
            f"la contre-épreuve doit dégrader le déficit ({ecart_deficit:+.2f} pt)")
        assert 5.0 <= ecart_dette <= 6.0, (
            f"écart de dette 2035 {ecart_dette:+.2f} pt — mesuré 5,50 au "
            f"2026-08-26 ; encadré des deux côtés pour que sa dérive soit un "
            f"acte et non un effet de bord")


def test_le_sens_du_biais_d_indexation_est_publie_sans_euphemisme():
    """Le mot « conservateur » est INTERDIT sur ce biais, partout.

    Il l'était dans quatre artefacts, dont deux servis au public
    (METHODOLOGIE.md et EXPLICATION_MODELE_ECONOMIQUE.md). Un simulateur
    citoyen n'a pas le droit de qualifier de prudente une approximation qui
    embellit son chiffre-titre : c'est la seule erreur de sens qu'un lecteur
    ne peut pas rattraper lui-même. La règle du projet (§C) est de dire dans
    quel sens joue chaque choix — la dire à l'envers est pire que se taire.

    Le test exige aussi que la MAGNITUDE soit publiée : un sens sans ordre de
    grandeur laisse croire à un détail, et 5,5 points de dette 2035 n'en est
    pas un."""
    import re

    racine = pathlib.Path(__file__).resolve().parent.parent
    artefacts = {
        'engine/inflation.py (docstring)': inflation_mod.__doc__ or '',
        'docs/METHODOLOGIE.md': (racine / 'docs' / 'METHODOLOGIE.md').read_text(encoding='utf-8'),
        'docs/EXPLICATION_MODELE_ECONOMIQUE.md': (
            racine / 'docs' / 'EXPLICATION_MODELE_ECONOMIQUE.md').read_text(encoding='utf-8'),
        'tests/test_calibration_mission_v060.py': (
            racine / 'tests' / 'test_calibration_mission_v060.py').read_text(encoding='utf-8'),
    }
    # Les quatre formulations AFFIRMATIVES exactes qui existaient, telles
    # qu'elles existaient. Bannir le mot « conservateur » tout court
    # interdirait de citer l'erreur pour l'expliquer — or c'est précisément
    # ce que la correction fait, et ce qu'elle doit pouvoir continuer de faire.
    interdits = (
        'Ce biais est CONSERVATEUR',
        'Ce biais est **conservateur**',
        'il est conservateur (il minore',
        "biais d'indexation I17 déclaré conservateur",
    )
    for nom, brut in artefacts.items():
        texte = re.sub(r'\s+', ' ', brut)
        for phrase in interdits:
            assert phrase not in texte, (
                f"{nom} qualifie encore le biais d'indexation de "
                f"« conservateur » — il FLATTE la dette et le déficit publiés")
        assert 'flatte' in texte.lower(), (
            f"{nom} doit dire dans quel sens joue le biais d'indexation : il "
            f"FLATTE les chiffres publiés. Le taire est moins grave que "
            f"l'écrire à l'envers, mais la règle du projet est de le dire.")
    # Et la magnitude, dans les deux documents publics.
    for nom in ('docs/METHODOLOGIE.md', 'docs/EXPLICATION_MODELE_ECONOMIQUE.md'):
        assert '5,5' in artefacts[nom], (
            f"{nom} doit publier l'ordre de grandeur du biais (5,5 pt de dette "
            f"2035) : un sens sans magnitude se lit comme un detail")


def test_pas_de_scission_prematuree_en_trois_variables():
    """Garde inverse : personne n'a introduit le coin IPC/déflateur en douce.

    Le dossier prévoit ``ECART_IPC_DEFLATEUR = 0,0015`` SI la scission est
    un jour instruite. Tant qu'elle ne l'est pas, la constante ne doit pas
    exister : une constante inerte fait croire à une architecture qui
    n'existe pas."""
    assert not hasattr(constants, 'ECART_IPC_DEFLATEUR'), (
        "ECART_IPC_DEFLATEUR est apparue : la scission déflateur/IPC est un "
        "changement d'architecture (tous les handlers consomment `inflation`) "
        "qui s'instruit hors v0.6.1")
