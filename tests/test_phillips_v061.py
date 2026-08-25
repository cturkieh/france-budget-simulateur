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
