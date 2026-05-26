"""Types partagés pour les handlers de mesures budgétaires.

``ImpactsDict`` est le contrat de retour des handlers (3ème élément du
``Tuple[float, float, ImpactsDict]``).

Le moteur macro lit principalement les clés agrégées : ``depenses``,
``recettes``, ``pouvoir_achat``, ``gini``, ``competitivite``, ``chomage``.
Les handlers peuvent ajouter des clés additionnelles à des fins de
traçabilité (ex: ``fp``, ``aides_sociales``, ``cotisations`` dans
``_apply_smic``) — elles sont conservées dans le retour mais ignorées
par l'agrégation macro. Toutes les clés sont optionnelles.

Tolérance ponctuelle : ``rabot_details`` dans ``_apply_rabot_uniforme``
est un sous-dict métadonnée qui s'écarte du contrat ``Dict[str, float]``.
Les agrégateurs du moteur (``micro_impacts.py``, ``unemployment.py``,
``growth.py``) ne lisent que les clés numériques connues (``gini``,
``competitivite``, ``chomage``, ``pouvoir_achat``, ``depenses``,
``recettes``) ; ``rabot_details`` est donc simplement ignorée car non
listée, pas filtrée par type — pas d'erreur runtime. Cas unique à
aplatir lors d'un futur chantier de typage strict (cf
``docs/REFACTOR_SPLIT_PLAN.md`` § « Typage de ``self`` pour mypy ») —
ne pas reproduire le pattern.

Protocols (Lot D — typage mixins, Phase 2 ✅ livrée) — purement
statiques, AUCUN impact runtime
(non instanciés ; hérités uniquement sous ``TYPE_CHECKING`` via le
pattern ``_MixinBase`` des mixins : base ``object`` au runtime, Protocol
au type-check, MRO inchangé) :

- ``Handler`` : contrat d'appel des 33 handlers thématiques. Permet de
  typer ``BudgetSimulatorV45.measure_handlers: Dict[str, Handler]`` et
  d'activer la vérification mypy/pyright de tous les handlers gratuitement.
- ``_SimulatorState`` : union exacte de l'état hôte (``BudgetSimulatorV45``)
  que les mixins lisent/écrivent sur ``self`` sans le définir eux-mêmes
  (cf ADR Phase 1.2 + inventaire Lot D). Borne de typage de ``self``.
"""
from typing import Dict, Protocol, Tuple

ImpactsDict = Dict[str, float]


class Handler(Protocol):
    """Contrat d'appel d'un handler de mesure (méthode liée ``self._apply_*``).

    Les 33 handlers thématiques partagent cette signature (seul le style
    mono-/multi-ligne diffère). Plancher mécanique :
    ``tests/test_mixin_architecture.py::test_measure_handlers_match_handler_protocol``
    verrouille déjà le compte (33) et l'arité (6 paramètres) ; mypy/pyright
    une fois branché ajoutera la vérification fine des TYPES de paramètres.
    Le ``self`` est absorbé par la liaison de méthode → signature d'appel
    à 6 paramètres positionnels. Le dispatcher legacy
    ``_apply_complex_measure`` (Section 7, retour
    ``Tuple[float, float, Dict]``) n'est volontairement PAS couvert
    (hors des 33, contrat de retour plus large).
    """

    def __call__(
        self,
        measure: Dict,
        params: Dict,
        year: int,
        gdp: float,
        inflation: float,
        unemployment: float,
    ) -> Tuple[float, float, ImpactsDict]:
        ...


class _SimulatorState(Protocol):
    """État hôte (``BudgetSimulatorV45``) requis par les mixins de handlers.

    Union EXACTE des attributs/méthodes que les mixins lisent ou écrivent
    sur ``self`` sans les définir eux-mêmes (cf ADR Phase 1.2 + inventaire
    Lot D). Sert de borne de typage de ``self`` via le pattern
    ``_MixinBase`` (base = ``object`` au runtime, ce Protocol sous
    ``TYPE_CHECKING``) : zéro impact runtime, MRO inchangé.

    NB : l'ancien état partagé ``asu_active`` / ``asu_phasing`` (couplage
    producteur/consommateur ASU↔fraude_sociale) a été SUPPRIMÉ — le
    consommateur dérive désormais le phasing ASU de ``self.mesures`` via
    ``handlers._phasing.asu_phasing`` (source unique, indépendante de
    l'ordre d'exécution). Plus aucun attribut d'instance partagé entre
    handlers de mixins différents pour ce besoin.
    ``_chomage_params_prev`` : état cross-année créé paresseusement par
    ``depenses._apply_chomage_alloc`` et supprimé par le reset hôte.
    Déclaré non-``Optional`` DÉLIBÉRÉMENT : le Protocol type la *forme*
    quand l'attribut existe ; sa présence est garantie dynamiquement par
    les gardes ``hasattr`` (handler ET reset), pas par le typage statique.
    Ne pas « corriger » en ``Optional`` (propagerait de faux checks
    ``None``) ni supprimer les gardes en se fiant à ce type.
    """

    # --- Sink de logs + helper de gating one-time (via MRO de l'hôte) ---
    debug_logs: list

    def _is_first_year_change(self, measure_id: str, params: Dict) -> bool:
        ...

    # --- Attributs hôte lus par les mixins ---
    mesures: Dict[str, Dict]
    base_params: Dict[str, float]
    spending_categories_base: Dict[str, float]
    _spending_factors: Dict[str, float]

    # --- État cross-année propre à un seul handler (lu ET écrit) ---
    _chomage_params_prev: Dict


__all__ = ['ImpactsDict', 'Handler', '_SimulatorState']
