"""Garde-fou de domaine des paramètres d'intensité — Lot C Item 1.

Porte unique (consommée par ``engine/orchestrator.py::apply_measures``,
juste avant le dispatch handler) qui valide ``params['intensite']``
contre le domaine légitime du levier (registre ``INTENSITE_DOMAINS``,
``budget_simulator/constants.py``).

Pourquoi : le slider frontend borne déjà l'utilisateur, mais les
entrées HORS-UI (scénarios politiques, API, config) ne passent par
AUCUN clamp backend pour ``optimisation_dette`` / ``isf_climatique`` /
``taxe_superprofits`` / ``exonerations_salaires`` (et un clamp
*silencieux* pour ``fiscalite_patrimoine``). Une valeur aberrante était
donc soit propagée sans alerte, soit écrasée sans trace. Cf.
``docs/MINI_DESIGN_ITEM1_BORNE_INTENSITE.md``.

Dualité STRICT/tolérant — même contrat que le reste du moteur :
- tolérant (prod, service citoyen) : ``logger.warning`` + clamp à la
  borne la plus proche ; NE CASSE JAMAIS le service. Modèle éprouvé
  ``handlers/additionnels.py`` (plafond superprofits/exonérations).
- ``BUDGETLAB_STRICT`` (CI/calibration) : ``raise ValueError``. Capté
  par l'``except`` existant de ``apply_measures`` → annoté
  ``measure_id`` → collecté → remonté dans l'``ExceptionGroup`` de fin
  de boucle. SYNERGIE Lot C Item 3 : aucune mécanique d'escalade
  nouvelle.

Contrainte dure MIXIN_BAD_PARAMS (mini-design §3.3, cf.
``tests/test_handler_failure_flag.py``) : la comparaison numérique se
fait SANS garde ``try/except`` et SANS normaliser une ``str``. Une
``str`` lève ``TypeError`` au premier comparateur — comportement VOULU
(remonte, ``_handler_failed=True``, ``ExceptionGroup`` strict),
strictement identique au contrat pré-Item 1. Le test
``test_str_intensite_*`` est load-bearing.
"""
import logging
from typing import Dict

from ..constants import INTENSITE_DOMAINS

logger = logging.getLogger(__name__)


def validate_intensite_domain(measure_id: str, params: Dict, *, strict: bool) -> Dict:
    """Valide/borne ``params['intensite']`` selon le domaine du levier.

    No-op (objet ``params`` rendu tel quel, sans copie) si le levier
    n'est pas au registre OU si ``intensite`` est absent/``None`` — ce
    dernier cas préserve la branche legacy de
    ``_resolve_intensite_or_legacy`` (taxe_superprofits/
    exonerations_salaires en mode legacy : pas de clé ``intensite``, ou
    ``intensite=None``). No-op aussi pour toute valeur DANS le domaine
    (bornes incluses) → golden master byte-identique sur les entrées
    légitimes. NaN traité hors domaine (sinon propagation silencieuse).

    Hors domaine : ``ValueError`` en ``strict``, sinon ``logger.warning``
    + copie défensive clampée (l'entrée appelante n'est jamais mutée).
    """
    domain = INTENSITE_DOMAINS.get(measure_id)
    # `params.get('intensite') is None` (et NON `'intensite' not in params`) :
    # aligne le no-op sur la sémantique aval de _resolve_intensite_or_legacy
    # (`params.get('intensite', None) is not None`). {'intensite': None} est
    # une entrée legacy LÉGITIME (slider non posé) — pas une erreur à borner.
    if domain is None or params.get('intensite') is None:
        return params
    low, high = domain
    value = params['intensite']
    # Comparaison numérique SANS garde : une str lève TypeError ici
    # (contrat MIXIN_BAD_PARAMS — surtout NE PAS intercepter ; `value !=
    # value` est False pour une str, le TypeError tombe bien sur `< low`).
    # `value != value` n'est vrai que pour NaN : sans ce test un NaN passe
    # `< low` ET `> high` (les deux False) et empoisonne silencieusement
    # TOUTE la trajectoire — exactement la classe d'échec silencieux que
    # ce garde-fou existe pour fermer (pire qu'un clamp tracé).
    if value != value or value < low or value > high:
        if strict:
            raise ValueError(
                f"{measure_id}.intensite={value!r} hors domaine "
                f"[{low}, {high}] (mode BUDGETLAB_STRICT)"
            )
        clamped = high if value > high else low  # NaN / < low → borne basse
        # Token stable INTENSITE_DOMAIN_CLAMP : rend le clamp filtrable/
        # alertable dans Sentry Logs (enable_logs=True expédie les warning),
        # à l'instar de HANDLER_FAILED_KEY pour les crashs.
        logger.warning(
            "INTENSITE_DOMAIN_CLAMP %s.intensite=%r hors domaine [%s, %s] "
            "→ clampé à %s (mode tolérant : service préservé, calibration "
            "à vérifier)",
            measure_id, value, low, high, clamped,
        )
        return {**params, 'intensite': clamped}
    return params
