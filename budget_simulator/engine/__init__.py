"""Moteur macroéconomique, splitté par bloc fonctionnel du simulator.

Convention de nommage : un mixin par bloc, nommé ``<Bloc>Mixin``
(le suffixe ``Engine`` est redondant avec le chemin ``engine/<bloc>.py``).

Symétrique du package ``handlers/`` : là où ``handlers/`` regroupe les
*mesures* politiques (``_apply_*``), ``engine/`` regroupe le *moteur*
macroéconomique (croissance, inflation, chômage, recettes, dépenses,
dette, impacts micro, orchestration).

Les méthodes restent liées (``self.calculate_*``) pour préserver l'API
publique : ``simulate()`` et les tests qui appellent directement les
méthodes continuent de fonctionner sans modification, le MRO de
``BudgetSimulatorV45`` résolvant ``self.calculate_inflation()`` &c.
exactement comme avant le split.

Voir ``docs/REFACTOR_SPLIT_PLAN.md`` § « Découpage du moteur macro »
pour la liste autoritative des blocs, l'ordre de split, et les
conventions de typage de ``self`` / helpers / dépendances cross-mixin.
"""
