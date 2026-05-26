"""Helpers de phasing / gating temporel partagés par les handlers.

Module dédié (importable depuis ``budget_simulator/handlers/`` sans
importer ``simulator``), même convention que ``.._logging._log_debug``.

Trois patterns récurrents y sont factorisés :

- ``_one_time_level`` : effet NIVEAU one-time appliqué la seule année
  d'entrée en vigueur (``years_elapsed == 0``), 0.0 sinon. Rend le
  contrat « NIVEAU vs FLUX » lisible dans la signature de l'appelant
  (cf docs/METHODOLOGIE.md § Effets NIVEAU vs FLUX).

- ``_year_phasing`` : montée en charge indexée par ``years_elapsed``,
  bornée à la dernière valeur du ``schedule`` (même format documenté
  que ``constants.PHASING_RETRAITES_5ANS`` / ``PHASING_NICHES_FISCALES_TGE``).
  Avant l'entrée en vigueur (``years_elapsed < 0``) : 0.0.

- ``_resolve_intensite_or_legacy`` : le pattern « slider unique
  d'intensité ``params['intensite']`` sinon paramètres legacy » dupliqué
  entre handlers convertis au slider simplifié.

NB sémantique : ``_one_time_level`` est gaté sur l'ANNÉE CALENDAIRE
(``years_elapsed == 0``), à NE PAS confondre avec
``BudgetSimulatorV45._is_first_year_change(measure_id, params)`` qui
détecte un changement effectif de ``params`` (re-trigger sur slider
modifié en cours de simulation). Les deux ne sont pas interchangeables.
"""
from typing import Callable, Dict, Sequence, TypeVar

from ..constants import POLICY_START_YEAR

_T = TypeVar('_T')

# Calendrier de montée en charge de l'ASU (4 ans) — SOURCE UNIQUE,
# cf ``asu_phasing``. Identique à l'ancien if/elif de ``_apply_asu``.
ASU_PHASING_SCHEDULE = (0.25, 0.50, 0.75, 1.00)


def _one_time_level(years_elapsed: int, value: float) -> float:
    """``value`` la seule année d'entrée en vigueur, 0.0 sinon.

    ``value`` doit être une expression PURE (sans effet de bord) : elle
    est toujours évaluée par l'appelant, y compris quand le résultat
    retenu est 0.0 — c'est ce qui garde le refactor byte-identique.
    """
    return value if years_elapsed == 0 else 0.0


def _year_phasing(years_elapsed: int, schedule: Sequence[float]) -> float:
    """Coefficient de montée en charge, borné à la dernière valeur.

    ``years_elapsed < 0`` (mesure pas encore en vigueur) → 0.0.
    Sinon ``schedule[min(years_elapsed, len(schedule) - 1)]``.
    Schedule ``(1.0,)`` = plein effet immédiat dès l'entrée en vigueur.

    Un ``schedule`` vide est une erreur de programmation (échec explicite
    plutôt qu'``IndexError`` opaque) — garde-fou défensif : tous les
    appelants actuels (Lots B.1 & B.2) passent un schedule littéral ou une
    constante non vide, la branche n'est donc pas atteignable aujourd'hui.
    """
    if not schedule:
        raise ValueError("_year_phasing: schedule vide (au moins 1 coefficient attendu)")
    if years_elapsed < 0:
        return 0.0
    return schedule[min(years_elapsed, len(schedule) - 1)]


def _resolve_intensite_or_legacy(
    params: Dict,
    simplified: Callable[[float], _T],
    legacy: Callable[[Dict], _T],
) -> _T:
    """``simplified(params['intensite'])`` si présent, sinon ``legacy(params)``.

    Factorise le contrôle « slider unique d'intensité vs paramètres
    legacy » sans figer la forme du résultat (les deux fabriques
    retournent le tuple propre à chaque handler).
    """
    intensite = params.get('intensite', None)
    if intensite is not None:
        return simplified(intensite)
    return legacy(params)


def asu_is_active(mesures: Dict) -> bool:
    """ASU active ssi ``mesures['asu']`` existe et ``asu_activation != 0``.

    Source unique consommée par ``asu_phasing`` ET
    ``depenses._apply_prestations_indexation`` (anti-double-comptage des
    90 Md€ absorbés par l'ASU) : aucune dépendance à un param fantôme ni
    à l'ordre des handlers. ``_apply_asu`` garde sa lecture inline
    (``params``) pour rester byte-identique au golden master — ne pas le
    router ici sans régénération auditée (dette connue, Item 2 contrat
    de params).
    """
    asu = mesures.get('asu')
    return bool(asu) and asu.get('asu_activation', 0) != 0


def asu_phasing(mesures: Dict, year: int) -> float:
    """Phasing de montée en charge de l'ASU pour ``year``, 0.0 si ASU inactive.

    SOURCE UNIQUE du calendrier ASU (activation + montée 4 ans), partagée
    par le producteur ``depenses._apply_asu`` et le consommateur
    ``efficience._apply_fraude_sociale`` (anti-double-comptage). Dérivée
    de ``mesures`` (entrée du run) + l'année → AUCUNE dépendance à l'ordre
    d'exécution des handlers (le consommateur n'a pas besoin que le
    producteur ait déjà tourné cette année-là). C'est ce qui dissout la
    fragilité producteur/consommateur (ex type-design F1/F3) : l'état
    n'est plus un attribut d'instance posé par un sibling-handler.

    ASU active ssi ``mesures['asu']`` existe et ``asu_activation != 0`` —
    EXACTEMENT le prédicat de ``_apply_asu`` (``if activation == 0:
    return``, sinon actif). Le test est ``== 0`` et NON ``== 1`` à
    dessein : le harnais standalone dévie le toggle à 0.5 (mi-distance),
    que ``_apply_asu`` traite comme actif — répliquer ce prédicat garde
    ``_apply_asu`` byte-identique (golden master inchangé sur ``asu``).
    Calendrier : ≤2025 → 0 %, 2026 → 25 %, 2027 → 50 %, 2028 → 75 %,
    2029+ → 100 %.
    """
    if not asu_is_active(mesures):
        return 0.0
    return _year_phasing(year - POLICY_START_YEAR, ASU_PHASING_SCHEDULE)


__all__ = [
    '_one_time_level', '_year_phasing', '_resolve_intensite_or_legacy',
    'asu_is_active', 'asu_phasing', 'ASU_PHASING_SCHEDULE',
]
