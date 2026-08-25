"""Bloc moteur — Impacts micro agrégés (Gini + compétitivité).

Méthodes couvertes :
- ``calculate_gini_impact`` : agrège la variation d'indice de Gini à partir
  de l'impact ``gini`` calculé par chaque handler. Le fallback générique
  par ``measure_id`` de la v4.5 comptait SEPT règles, toutes sans source :
  six sont SUPPRIMÉES (v0.6.1 lot 6, item I27) — cinq inatteignables, la
  sixième active et asymétrique. La septième, celle d'``impot_societes``,
  est conservée en l'état, déclarée non sourcée et documentée comme dette
  (cf. docstring de la méthode).
- ``calculate_competitivite`` : COLLECTE (ne calcule pas) les impacts
  ``competitivite`` produits par chaque handler ``_apply_*``.
  Méthodologie CUT OCDE / DG Trésor (cf METHODOLOGIE.md § Compétitivité).

Profil de couplage : **purement collectrices**. Lecture seule du dict
``impacts`` (sortie des handlers) et de ``gdp`` ; aucun état d'instance
écrit, aucun contrat producteur/consommateur (≠ ``InflationMixin`` /
``RevenuesMixin`` / ``DebtMixin`` / ``ExpendituresMixin``).

Filtre tolérant : les deux méthodes sautent tout ``impact`` non-dict.
``calculate_competitivite`` n'agrège que la clé ``'competitivite'``
(aucun fallback) ; ``calculate_gini_impact`` agrège ``'gini'`` et ne
conserve qu'une seule règle par ``measure_id``, déclarée non sourcée
(``impot_societes``). La re-analyse adverse
(2026-05-16) a RÉFUTÉ le « masquage silencieux » comme risque actuel :
``apply_measures`` garantit toujours un dict (un non-dict crashe
bruyamment en amont avec ``logger.error`` + ``HANDLER_FAILED_KEY``), et
aucun des 33 handlers n'émet ``'gini'``/``'competitivite'`` mal
orthographiée (grep exhaustif). Les clés custom (``description``,
``rabot_details``, ``emploi``…) sont ignorées À RAISON (métadonnées, cf
``_types.py``). Garde ``isinstance`` = défensif inerte aujourd'hui ;
risque résiduel purement PRÉVENTIF/FUTUR (typo lors d'un futur
renommage). Sévérité LOW — même lot reclassé que ``UnemploymentMixin``
(réponse proportionnée = test de contrat sur les 33 handlers, PAS
durcissement des collecteurs ; cf ``docs/REFACTOR_SPLIT_PLAN.md``).

Sink de logs : ``self.debug_logs`` via ``_log_debug``
(``calculate_competitivite`` uniquement).
Tous attributs d'instance de ``BudgetSimulatorV45``.
"""
from typing import Dict

from .._logging import _log_debug
from ..constants import GINI_FALLBACK_IMPOT_SOCIETES_NON_SOURCE


class MicroImpactsMixin:
    """Bloc moteur — Impacts micro agrégés (Gini + compétitivité)."""

    def calculate_gini_impact(self, impacts: Dict, gdp: float) -> float:
        """Agrège les impacts Gini émis par les handlers ``_apply_*``.

        COLLECTEUR, comme ``calculate_competitivite`` : chaque handler est
        responsable de son propre canal redistributif et l'émet sous la clé
        ``'gini'``. Un handler qui ne l'émet pas déclare, par ce silence,
        qu'il n'a pas d'effet direct sur le Gini du NIVEAU DE VIE (revenu
        disponible par unité de consommation, définition INSEE).

        v0.6.1 lot 6 — SUPPRESSION DU FALLBACK GÉNÉRIQUE (item I27). Six
        règles par ``measure_id`` survivaient ici depuis la v4.5 :
        ``retraites`` 0,10 / ``chomage_alloc`` 0,15 / ``sante`` 0,08 /
        ``tva_rate`` 0,05 / ``transition_ecologique`` et ``education`` 0,04.
        Aucune n'avait de source (0 occurrence dans METHODOLOGIE.md), et
        cinq d'entre elles étaient MORTES — leurs handlers émettent tous
        ``'gini'``, la branche ne pouvait jamais s'exécuter. Du code mort
        non traçable dans un dépôt public.

        La sixième, ``education``, était VIVANTE et portait trois défauts
        cumulés : coefficient non sourcé, règle ASYMÉTRIQUE (``if > 0`` :
        une COUPE d'éducation émettait exactement 0, ce qui avantageait
        silencieusement les programmes de coupe) et émission RÉCURRENTE
        alors que ``gini_cible_cumul`` accumule. ``_apply_education`` émet
        désormais ``'gini': 0.0`` explicitement, avec son motif de
        PÉRIMÈTRE : une dépense d'éducation est un transfert EN NATURE,
        elle n'entre pas dans le revenu disponible — zéro par construction
        de l'indicateur, pas par oubli du modèle.

        ⚠️ IL RESTE UN CAS PARTICULIER, ET IL EST DÉCLARÉ : ``impot_societes``
        (cf. ``GINI_FALLBACK_IMPOT_SOCIETES_NON_SOURCE`` dans constants.py).
        Son handler n'émet volontairement pas de clé ``'gini'``, mais cette
        règle en produit un dans son dos, de façon asymétrique. Elle est
        ACTIVE — y compris dans deux scénarios publiés (``lfi_2027``, IS à
        30 %, et ``ps_2027``, IS à 27 %). Elle n'est pas
        corrigée ici parce qu'elle déplace des chiffres publiés et qu'aucune
        source de ce lot ne dit par quoi la remplacer : la retirer ou la
        symétriser sans source remplacerait un biais par un autre. Dette
        renvoyée au chantier v0.7 avec la re-dérivation de
        ``GINI_IMPACT_SCALE``.
        """
        gini_change = 0

        for measure_id, impact in impacts.items():
            if not isinstance(impact, dict):
                continue

            # Cas normal : le handler a calculé son propre impact.
            if 'gini' in impact:
                gini_change += impact['gini']
                continue

            # DETTE CONNUE, seul survivant du fallback v4.5 (cf. docstring).
            if measure_id == 'impot_societes':
                revenue_impact = impact.get('recettes', 0)
                if revenue_impact > 0:
                    gini_change -= GINI_FALLBACK_IMPOT_SOCIETES_NON_SOURCE * (
                        revenue_impact / gdp)

        return gini_change

    def calculate_competitivite(self, impacts: Dict, gdp: float, year: int) -> float:
        """Collecte les impacts compétitivité calculés dans chaque fonction _apply_*.

        Méthodologie basée sur Coût Unitaire Travail (OCDE) et indicateurs DG Trésor.
        Chaque mesure calcule son propre impact selon sa nature économique.
        Cette fonction ne fait que COLLECTER les impacts, pas les calculer.

        Sources: OCDE 2024 (CUT), DG Trésor 2021-2024, France Stratégie CNP.
        Voir METHODOLOGIE.md § Compétitivité."""

        competitivite_delta = 0
        impacts_details = []

        for measure_id, impact in impacts.items():
            if not isinstance(impact, dict):
                continue

            # Collecter l'impact compétitivité calculé directement par la mesure
            if 'competitivite' in impact:
                comp_value = impact['competitivite']
                if abs(comp_value) > 0.0001:  # Seuil pour log
                    impacts_details.append(f"{measure_id}={comp_value:+.3f}")
                competitivite_delta += comp_value

        if impacts_details:
            _log_debug(self.debug_logs, f"Y{year}: COMPETITIVITE TOTALE = {competitivite_delta:+.3f} ({', '.join(impacts_details)})")

        return competitivite_delta
