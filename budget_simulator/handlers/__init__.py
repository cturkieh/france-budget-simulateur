"""Handlers de mesures budgétaires, splittés par section thématique du simulator.

Convention de nommage : un mixin par section, nommé ``<Section>Mixin``
(le suffixe ``Handlers`` est redondant avec le chemin ``handlers/<section>.py``).

Les handlers restent des méthodes liées (``self._apply_*``) pour préserver
l'API publique existante : le dict ``measure_handlers`` du simulator et les
tests qui appellent directement les méthodes continuent de fonctionner sans
modification.

Voir ``docs/REFACTOR_SPLIT_PLAN.md`` pour la liste autoritative des sections,
l'ordre de split, et les conventions sur le typage de ``self``, les helpers
privés, et les dépendances cross-mixin.
"""
