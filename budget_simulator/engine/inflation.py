"""Bloc moteur — Inflation (courbe de Phillips ANCRÉE).

Méthode couverte :
- ``calculate_inflation`` : inflation de l'année à partir de l'état
  économique (output gap, unemployment gap, impact TVA, effort
  budgétaire), avec rappel de politique monétaire BCE. Déterministe
  (bruit tiré retiré en v0.6.7).

Forme retenue : Phillips augmentée en ``output_gap`` uniquement (pas
de terme ``unemployment_gap`` direct, déjà corrélé via Okun → évite le
double-comptage), sous forme **ancrée** depuis la v0.6.1 (I12/R1) :

    π_t = (1−ρ)·(π* + κ_LR·gap_t) + ρ·π_{t−1}

soit, pour un gap constant, le point fixe π̄ = π* + κ_LR·gap.

Pourquoi cette réécriture — c'est une correction d'ALGÈBRE, pas de
calibration. La v0.6.0 posait ``(1−ρ)·π* + ρ·π_{t−1} + κ·gap`` avec le
terme de gap HORS de l'ancrage : son point fixe valait π* + [κ/(1−ρ)]·gap,
donc la grandeur homologue de la « pente de moyen terme » de la littérature
valait 0,35/0,50 = 0,70 — un nombre écrit nulle part et sourcé nulle part,
pendant que le code affichait 0,35. C'est le MÊME défaut de forme que
l'intercept AR(1) ≠ point fixe corrigé en v0.3.0, déplacé d'un terme. Les
deux formes sont équivalentes à κ = κ_LR·(1−ρ) près : ce qui change est que
le paramètre du code (``PHILLIPS_PENTE_MT``) est DÉSORMAIS directement la
pente estimable, et que ρ redevient un simple paramètre de VITESSE au lieu
d'un multiplicateur caché de la pente.

CE QUE « VITESSE ET NON NIVEAU » NE VEUT PAS DIRE (clôture de la revue
adverse, 2026-08-26). La propriété est vraie une fois le transitoire éteint —
écart entre ρ = 0,25 et ρ = 0,50 : 0,010 pt en moyenne 2031-2035, 0,000 pt en
2035. Elle ne dit RIEN de la fenêtre 2026-2030, qui EST le transitoire : le
moteur part de la graine ``INFLATION_BASE`` (1,0 %) et monte vers son ancrage
π* + κ_LR·gap ≈ 1,46 %, soit 0,46 pt plus haut. Sur cinq ans de montée, une
vitesse déplace la moyenne — mesuré 0,062 pt, contre 0,02 pt annoncé par le
dossier. Le corollaire du dossier (« ρ = 0,50 est de second ordre, ne pas
dépenser de crédibilité sur ce paramètre ») reste défendable, mais pour une
raison qui doit être TESTÉE et non supposée : la conformité au corridor de
déflateur tient sur toute la plage plausible de ρ (0,20 à 0,50), et c'est ce
que verrouille ``tests/test_phillips_v061.py``. La marge est mince et
déclarée : à la valeur livrée (0,50) la moyenne 2026-2030 est à 0,012 pt du
plancher de la fourchette.

Ancrage des anticipations (ce qui légitime la forme ancrée plutôt qu'un
AR(1) pur) : BCE, Survey of Professional Forecasters T3 2026 —
anticipations de long terme à 2,0 %, révision 0,0 malgré un IPCH 2026 à
2,7-3,0 % ; Banque de France, Billet de blog n° 335 (déc. 2023) — dans les
pays sans clause d'indexation, dont la France depuis 1983, la transmission
de l'inflation réalisée aux anticipations tombe sous 1/3 de sa valeur de
court terme aux horizons longs.

--------------------------------------------------------------------------
CE QUE MESURE LA VARIABLE ``inflation`` (arbitrage I17, v0.6.1)
--------------------------------------------------------------------------
Une seule variable sert TROIS indices économiquement différents :
  (i)   **déflateur du PIB** — ``self.deflateur_cumule *= (1 + inflation)``
        dans ``engine/orchestrator.py``, donc le DÉNOMINATEUR du ratio de
        dette, c'est-à-dire la sortie principale du site ;
  (ii)  **IPC**, pour le pouvoir d'achat — jusqu'en v0.6.6 seulement
        (``pa_macro = growth − inflation + 0,54 × inflation``, double
        retranchement : depuis v0.6.7 l'indice suit la croissance RÉELLE, que
        le déflateur affecte déjà) ;
  (iii) **indice d'indexation** des pensions et prestations (désindexations,
        ``handlers/depenses.py``, et part indexée de la dépense,
        ``INDEXATION_DEPENSES_INFLATION_PASSEE``).

Arbitrage v0.6.1 : la variable est CALÉE SUR LE DÉFLATEUR. L'INSEE tranche
explicitement (blog « Inflation : les déflateurs en comptabilité
nationale », sept. 2022) : « les ressources publiques étant plus ou moins
fonction du PIB en valeur plutôt que de la seule consommation, c'est plutôt
le déflateur du PIB qui importe pour apprécier le taux d'emprunt réel des
administrations publiques ». L'indexation LÉGALE des pensions se fait, elle,
sur l'IPC hors tabac.

**Biais résiduel DÉCLARÉ : −0,15 pt/an** sur les rôles (ii) et (iii) —
écart déflateur − prix à la consommation mesuré à −0,1/−0,2 pt en régime
normal (jusqu'à −0,6/−0,8 pt en année de choc énergétique).

CE BIAIS N'EST PAS CONSERVATEUR — IL FLATTE (correction du 2026-08-26). La
docstring a longtemps écrit l'inverse, en donnant pour preuve qu'il « minore
la dépense indexée ET minore la perte de pouvoir d'achat ». Les deux effets
nommés vont dans le MÊME sens, et c'est le sens favorable : une dépense
minorée AMÉLIORE le déficit et la dette — la sortie titre du site — et une
perte de pouvoir d'achat minorée est un indicateur embelli. Sur un simulateur
budgétaire, « conservateur » désigne l'erreur qui joue contre soi ; celle-ci
joue pour soi, dans les deux rôles à la fois.

MAGNITUDE, MESURÉE PAR CONTRE-ÉPREUVE (``tests/test_phillips_v061.py`` :
dépense primaire indexée sur l'IPC = déflateur + 0,15 pt, tout le reste
identique) : déficit 2030 −6,40 → −6,86 (+0,46 pt), déficit 2035 −10,70 →
−11,95 (+1,25 pt) ; dette 2030 129,65 → 130,93 (+1,28 pt), **dette 2035
159,35 → 164,85, soit 5,5 points de PIB**. Ce n'est pas un résidu de second
ordre : c'est l'ordre de grandeur d'un lot entier de corrections.

Il n'est PAS corrigé ici : tous les handlers consomment ``inflation``,
scinder en trois variables est un changement d'architecture qui s'instruit
séparément (la constante à créer serait alors un coin ``ECART_IPC_DEFLATEUR``,
jamais un littéral dupliqué). Ce qui change ici est ce qu'on en DIT — et
c'est précisément ce que la règle du projet exige : dire dans quel sens joue
chaque choix, sous peine d'être pire que le silence.

--------------------------------------------------------------------------
DETTE CONNUE, HORS PÉRIMÈTRE v0.6.1 (I18)
--------------------------------------------------------------------------
Les termes ``effort_budgetaire`` ci-dessous (−0,12 à la consolidation,
+0,08 à l'expansion) sont NON SOURCÉS, ASYMÉTRIQUES et en double-comptage
partiel avec le canal output gap. Trois défauts réels — donc une
instruction à eux seuls (v0.6.2), pas un effet de bord de la recalibration.
Aucune non-linéarité en L inversé n'est introduite : elle est sourcée mais
asymétrique par construction (plate en bas, raide en haut), ce qui en fait
une décision de neutralité et non un réglage.

État partagé ``self.inflation_precedente`` :
- Lu en entrée (terme d'inertie ``inflation_inertia *
  inflation_precedente``) puis réécrit par la DERNIÈRE instruction de
  ``calculate_inflation`` (``self.inflation_precedente = inflation``).
- Persistance inter-années N→N+1 : portée par ``simulate()`` (qui
  réaffecte ``inflation_precedente`` en fin de boucle annuelle), PAS
  par cette écriture in-méthode. Init / reset relèvent de l'hôte
  ``BudgetSimulatorV45``.
- Cette écriture in-méthode est conservée VOLONTAIREMENT bien qu'elle
  n'ait plus d'effet observable sur ``simulate()`` : elle neutralisait
  jadis un garde d'ajustement d'élasticité recettes (placé juste après
  l'appel), garde **SUPPRIMÉ en Phase 2 (2026-05-16, option B)** car
  mort par construction ET en double-comptage avec l'élasticité au PIB
  nominal de ``calculate_revenues``. Maintenue pour cohérence
  intra-méthode (inertie correcte si ``calculate_inflation`` était
  appelée 2× dans la même boucle). Détail/chiffrage : tombstone dans
  ``engine/orchestrator.py`` et ``docs/REFACTOR_SPLIT_PLAN.md``.

Lecture seule : ``self.economic_coeffs['inflation_inertia']``.
Sink de logs : ``self.debug_logs`` via ``_log_debug``.
Tous attributs d'instance de ``BudgetSimulatorV45``.
"""
from typing import Dict

import numpy as np

from .._logging import _log_debug
from ._regimes import au_dessus, en_dessous, poids_expansion
from ..constants import (
    BCE_CIBLE_INFLATION,
    BCE_PLANCHER_ACCOMMODANT,
    INFLATION_STRUCTURELLE,
    PHILLIPS_PENTE_MT,
    REGIME_DEMI_LARGEUR_INFLATION,
)


def point_fixe_phillips_ancree(output_gap: float) -> float:
    """π̄ = π* + κ_LR · gap — l'ancrage vers lequel converge le régime.

    Source UNIQUE de la courbe : ``calculate_inflation`` ne fait que la
    pondérer par l'inertie. La conséquence est testable directement — la
    pente observée sur le point fixe EST ``PHILLIPS_PENTE_MT`` — et la
    courbe est linéaire, donc symétrique autour de π* par construction.
    """
    return INFLATION_STRUCTURELLE + PHILLIPS_PENTE_MT * output_gap


def rappel_bce(inflation: float) -> float:
    """Règle monétaire du moteur — garde-fou, PAS thermostat de convergence.

    Extraite en fonction pure en v0.6.1 (comportement inchangé) pour que
    son inertie soit MESURABLE : un point fixe tenu par un clip ne serait
    pas un point fixe du modèle. En v0.6.0 le plancher accommodant se
    déclenchait dès l'année 1 du statu quo (0,725 % pré-garde → 0,95 %
    publiée) et soutenait donc artificiellement la calibration ; depuis le
    recalage Phillips (I12-I15) les deux branches sont inertes en statu quo,
    ce que verrouille ``tests/test_phillips_v061.py``.

    À DÉCLARER, car ce n'est vrai qu'en statu quo. Décomptes mesurés sur les
    neuf scénarios publiés, dix années chacun :

        plancher accommodant     v0.6.0        v0.6.1
        les 7 programmes          1 à 2 fois    0 fois
        im_competitivite_2029     5 fois        0 fois
        im_rabot_2029            10 fois        8 fois

    Autrement dit, la v0.6.0 faisait porter à un clip une partie de la
    désinflation de TOUS les scénarios, et la TOTALITÉ de celle du plus
    austère. Ce n'est plus le cas que pour ``im_rabot_2029``, dont l'output
    gap est assez négatif pour que la courbe descende légitimement sous le
    seuil — c'est le rôle d'un garde-fou. La conséquence de neutralité est
    dite dans METHODOLOGIE.md § « ce que la version déplace, EN AGRÉGÉ » :
    le clip soutenait la croissance nominale des programmes de consolidation,
    donc leur dénominateur de dette.

    Les deux poids de mélange restent des paramètres de la RÈGLE MONÉTAIRE
    (vitesse de rappel), pas de la courbe de Phillips : hors périmètre du
    lot 8, inchangés.
    """
    if inflation > BCE_CIBLE_INFLATION:
        # Rappel de SURCHAUFFE (refonte 2026-06) : seuil = cible BCE, pour
        # qu'il CONTIENNE l'inflation au-dessus de la cible au lieu de servir
        # de thermostat permanent (l'ancien couple attracteur 3 % / seuil
        # 2,3 % stabilisait à 2,33 % à perpétuité).
        return 0.50 * inflation + 0.50 * BCE_CIBLE_INFLATION
    # Plancher accommodant : tiré vers la TENDANCIELLE (et non plus 2 %, qui
    # contredisait le point fixe du régime). À transition CONTINUE depuis la
    # v0.6.7 (lot 3b, engine/_regimes.py, ±0,3 pt autour de 0,8 %) : c'était une
    # marche qui faisait REMONTER l'inflation de 0,80 à 1,04 % au franchissement
    # (curseur rabot de « Budget 2026 (voté) » : −0,66 pt de dette 2035 pour un
    # millionième de taux). Plein régime (π ≤ 0,5 %) inchangé au bit.
    w = en_dessous(inflation, BCE_PLANCHER_ACCOMMODANT, REGIME_DEMI_LARGEUR_INFLATION)
    if w > 0:
        return (1 - w) * inflation + w * (0.70 * inflation + 0.30 * INFLATION_STRUCTURELLE)
    return inflation


class InflationMixin:
    """Bloc moteur — Inflation (courbe de Phillips ancrée)."""

    def calculate_inflation(self, year: int, economic_state: Dict) -> float:
        """Courbe de Phillips ancrée + ajustements + règle monétaire."""
        output_gap = economic_state['output_gap']
        unemployment_gap = economic_state['unemployment_gap']
        tva_impact = economic_state.get('tva_impact', 0)
        effort_budgetaire = economic_state.get('effort_budgetaire', 0)

        # Phillips ANCRÉE (forme output_gap uniquement, évite le double-comptage
        # output_gap/unemployment_gap corrélés via Okun) :
        #
        #     π_t = (1−ρ)·(π* + κ_LR·gap_t) + ρ·π_{t−1}
        #
        # L'ancrage TOUT ENTIER — tendancielle ET écart d'activité — est pondéré
        # par (1−ρ). Deux corrections successives du même piège :
        #  - v0.3.0 : dans un AR(1) i_t = c + ρ·i_{t-1} le point fixe est
        #    c/(1−ρ), pas c. L'intercept a été mis sous (1−ρ).
        #  - v0.6.1 (I12/R1) : le terme de gap était RESTÉ hors de l'ancrage,
        #    donc le point fixe valait π* + [κ/(1−ρ)]·gap et ρ multipliait
        #    silencieusement la pente — le code affichait 0,35 quand la
        #    grandeur homologue de la littérature valait 0,70, non sourcée.
        # Le paramètre du code EST désormais la pente de moyen terme.
        inertia = self.economic_coeffs['inflation_inertia']
        inflation = (
            (1 - inertia) * point_fixe_phillips_ancree(output_gap) +
            inertia * self.inflation_precedente
        )

        # v0.6.7 (lot 3b) : plus de porte à 0,1 % du PIB — l'effet, proportionnel
        # à l'effort, vaut déjà 0 en 0 (la porte créait un saut de 0,012 pt).
        if effort_budgetaire != 0:
            if effort_budgetaire > 0:
                inflation_impact = -0.12 * effort_budgetaire
                inflation += inflation_impact
                if abs(inflation_impact) > 0.002:
                    _log_debug(self.debug_logs, f"Y{year}: Impact déflationniste: {inflation_impact*100:.2f}%")
            else:
                inflation_impact = 0.08 * abs(effort_budgetaire)
                inflation += inflation_impact
                if abs(inflation_impact) > 0.002:
                    _log_debug(self.debug_logs, f"Y{year}: Impact inflationniste: {inflation_impact*100:.2f}%")

        # Régimes déflation (×0,80 : gap < −2,5 % ET écart de chômage > 1 pt) et
        # tensions (×1,08 plafonné à 3 % : gap > 2 % ET écart < −1 pt), à
        # transition CONTINUE (v0.6.7, engine/_regimes.py) : la réponse est la
        # moyenne des deux régimes pondérée par w. C'étaient des marches (LFI :
        # jusqu'à +0,55 pt de dette 2035 pour un SMIC déplacé d'un millionième).
        w_deflation = min(en_dessous(output_gap, -0.025), au_dessus(unemployment_gap, 0.01))
        w_tensions = poids_expansion(output_gap, unemployment_gap)
        if w_deflation > 0:
            inflation *= 1 + (0.80 - 1) * w_deflation
            _log_debug(self.debug_logs, f"Y{year}: Pressions déflationnistes (poids {w_deflation:.2f})")
        if w_tensions > 0:
            inflation = (1 - w_tensions) * inflation + w_tensions * min(inflation * 1.08, 0.030)
            _log_debug(self.debug_logs, f"Y{year}: Tensions inflationnistes (poids {w_tensions:.2f})")

        # Pass-through TVA — gate temporel UNIQUE (l'orchestrateur transmet la
        # valeur sans condition d'année). Depuis la refonte 2026-06, l'inflation
        # de t est calculée AVANT les mesures de t : le tva_impact vient des
        # impacts de t−1, donc le pass-through frappe à year == 2 (l'année qui
        # suit l'entrée en vigueur des mesures, toutes actives dès Y1 dans ce
        # moteur — POLICY_START_YEAR). One-shot délibéré : pas de re-pass-through
        # les années suivantes (la persistance passe par l'inertie ρ = 0,5).
        # v0.6.7 (lot 3b) : plus de porte à 0,3 % du PIB de recettes de TVA — le
        # pass-through (30 %, plafonné à 0,2 pt) vaut déjà 0 en 0 ; la porte le
        # faisait naître d'un coup à +0,09 pt (curseur TVA à 20,63 % : −0,30 pt
        # de dette 2035, statu quo compris).
        if year == 2 and tva_impact > 0:
            tva_pass_through = min(tva_impact * 0.3, 0.002)
            inflation += tva_pass_through
            _log_debug(self.debug_logs, f"Y{year}: Impact TVA +{tva_pass_through*100:.2f}%")

        # Règle monétaire — source unique dans `rappel_bce` (fonction pure).
        # En statu quo v0.6.1, aucune des deux branches ne se déclenche : la
        # calibration est portée par le modèle, pas par un clip.
        avant_bce = inflation
        inflation = rappel_bce(inflation)
        if inflation != avant_bce:
            sens = "restrictive" if avant_bce > BCE_CIBLE_INFLATION else "accommodante"
            _log_debug(self.debug_logs, f"Y{year}: Politique monétaire {sens}")

        # Bruit N(0 ; 0,05 %) RETIRÉ en v0.6.7, même raison que la croissance
        # (engine/growth.py) : un tirage à graine fixe n'est pas une calibration.
        inflation = np.clip(inflation, -0.003, 0.030)

        self.inflation_precedente = inflation
        return inflation
