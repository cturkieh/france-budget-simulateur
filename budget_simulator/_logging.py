"""Helpers de logging conditionnel partagés (simulator + handlers).

Ces helpers vivent dans un module dédié pour permettre l'import depuis
``budget_simulator/handlers/`` sans importer ``simulator``.

Sémantique : ``DEBUG_MODE`` est lu une seule fois au load du module. Pour
modifier le mode debug, redémarrer le process — toute mutation runtime
de l'env n'est pas reprise.
"""
import os

DEBUG_MODE = os.environ.get('BUDGET_DEBUG', 'false').lower() in ('true', '1')


def _log_debug(logger_list, message):
    """Helper pour logger uniquement si DEBUG_MODE est activé"""
    if DEBUG_MODE:
        logger_list.append(message)
