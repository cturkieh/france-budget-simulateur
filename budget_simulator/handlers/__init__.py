"""Handlers de mesures budgétaires, splittés par section thématique du simulator.

Convention de nommage : un mixin par section, nommé ``<Section>Mixin``
(le suffixe ``Handlers`` est redondant avec le chemin ``handlers/<section>.py``).

Les handlers restent des méthodes liées (``self._apply_*``) pour préserver
l'API publique existante : le dict ``measure_handlers`` du simulator et les
tests qui appellent directement les méthodes continuent de fonctionner sans
modification.

Release E : trois modules de plus (``transferts_menages``,
``recettes_montants``, ``recettes_taux``), soit 42 handlers câblés par
``measure_handlers`` ; ils naissent squelettes au commit socle (effet nul aux
valeurs neutres, toute autre valeur refusée) et chaque chantier écrit les
corps de SON module.

Voir ``docs/REFACTOR_SPLIT_PLAN.md`` pour la liste autoritative des sections,
l'ordre de split, et les conventions sur le typage de ``self``, les helpers
privés, et les dépendances cross-mixin.
"""
