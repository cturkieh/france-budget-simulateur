import json
import logging

from .constants import POLICY_MEASURES_PATH

logger = logging.getLogger(__name__)

# === CACHE MODULE-LEVEL ===
_POLICY_CONFIG_CACHE = None

# === FONCTIONS INTERFACE ===
def load_default_values():
    """Source unique des valeurs par défaut (statu quo).

    simulator.py::_get_default_values() délègue ici (DRY).
    """
    return {
        'tva_rate': {'taux': 0.20},
        'retraites': {'age_depart': 62.75, 'indexation': 1.0, 'duree_cotisation': 42.5},
        'fonction_publique': {'effectifs': 0, 'point_indice': 0},
        'fonction_publique_reforme': {'fusion_agences': 0, 'digitalisation': 0},
        'impot_societes': {'taux': 0.25, 'niches': 0},
        'sante': {
            'effort_hopital': 0,      # 0-100 : Reforme hopital (convergence tarifs + fermetures GHT + achats groupes) - Max -13 Md euros
            'effort_ambu': 0,         # 0-100 : Reforme ambulatoire (gatekeeping + CPTS/telemedecine + pertinence) - Max -10 Md euros
            'effort_prev_org': 0,     # 0-100 : Prevention & organisation (generiques + IJ + urgences + prevention ROI) - Max -7 Md euros
            'franchise_participation_taux': 100,  # 0-200% : Franchises médicales et forfaits (100% = maintien, 0% = suppression, 200% = doublement)
            'prevention_budget': 5.0  # 5-8 Md€ : Investissement prévention (budget additionnel, ROI 25%/an après 2 ans)
        },
        'chomage_alloc': {'montant': 40, 'duree': 18, 'degressivite': False},  # Réforme avril 2025 : durée 24→18 mois, montant 45→40
        'asu': {'asu_activation': 0, 'asu_plafonnement': 0.65},  # activation: 0/1, plafonnement: 0.5-0.7 (50-70% SMIC)
        'education': {'budget': 65, 'enseignants': 0, 'salaires': 0},
        'transition_ecologique': {'investissement': 0, 'taxe_carbone': 44.6, 'renovation': 0},
        'defense': {'budget': 50},
        'collectivites': {'dotation': 120, 'investissement': 0},
        'fraude_fiscale': {'effort': 0},
        'fraude_sociale': {'effort': 0},
        'optimisation_dette': {'intensite': 0},
        # COMPÉTITIVITÉ DES ENTREPRISES
        'niches_fiscales_tge': {'montant': 58},  # 70% de 83 Md€ total
        'niches_sociales_tge': {'montant': 70},  # 70% de 100 Md€ total
        'subventions_tge': {'montant': 35},      # 70% de 50 Md€ total
        'cotisations_patronales': {'taux': 0.27},
        'impots_production': {'montant': 97},    # INSEE 2024, CAE 2025
        'is_exceptionnel_tge': {'montant': 8},
        'immigration': {'ame': 1.2, 'integration': 0.8},
        'impot_revenu': {'taux_superieur': 0.45, 'decote': 1.0},
        'csg': {'taux': 0.097, 'progressive': 0},  # Taux 2025 (9.2%→9.7%)
        'cotisations_salariales': {'baisse_points': 0},
        'elargissement_ir': {'taux_contribuables_cible': 0.45},  # DGFiP 2024: 19M/41M = 45%
        'fiscalite_patrimoine': {'intensite': 0.0},
        # RECHERCHE PUBLIQUE
        'recherche_publique': {'budget': 10},  # 10 Md€ base actuelle
        # NOUVELLES MESURES PRÉSIDENTIELLE 2027
        'smic': {'montant_brut': 1800},  # ~1800€ brut actuel = 1398€ net
        'isf_climatique': {'intensite': 0},  # 0% = IFI maintenu, 100% = ISF NFP
        'tva_energie': {'taux': 0.20},  # 20% = status quo
        'taxe_superprofits': {'intensite': 0},  # 0-100%
        'exonerations_salaires': {'intensite': 0},  # 0-100%
        # NOUVELLES MESURES 2026 (PLF/PLFSS)
        'abattement_retraites': {'reforme_active': 0},  # 0/1
        # Pas de asu_active/asu_plafonnement ici : l'anti-double-comptage ASU
        # passe par _phasing.asu_is_active(mesures), jamais par un param.
        'prestations_indexation': {'taux_indexation': 1.0}  # 100% = compensation complète inflation
    }

def load_policy_config():
    """Charge la configuration des mesures depuis JSON (cache module-level, source de vérité unique).

    Raises:
        RuntimeError: Si le fichier est introuvable ou corrompu. Le cache n'est
            jamais empoisonné par un fallback vide — un échec transitoire au boot
            sera retenté à la prochaine requête, et un fichier corrompu génère
            une erreur explicite plutôt que des simulations économiquement fausses.
    """
    global _POLICY_CONFIG_CACHE

    if _POLICY_CONFIG_CACHE is not None:
        return _POLICY_CONFIG_CACHE

    last_unicode_err = None
    for encoding in ('utf-8', 'latin-1', 'cp1252'):
        try:
            with open(POLICY_MEASURES_PATH, 'r', encoding=encoding) as f:
                _POLICY_CONFIG_CACHE = json.load(f)
                logger.info("policy_measures.json chargé (encoding=%s)", encoding)
                return _POLICY_CONFIG_CACHE
        except UnicodeDecodeError as e:
            last_unicode_err = e
            continue
        except FileNotFoundError as e:
            raise RuntimeError(
                f"policy_measures.json introuvable à {POLICY_MEASURES_PATH}. "
                "Vérifiez que le fichier est présent à la racine du projet."
            ) from e
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"policy_measures.json malformé (ligne {e.lineno}, col {e.colno}): {e.msg}"
            ) from e

    raise RuntimeError(
        f"policy_measures.json: aucun encodage testé n'a fonctionné "
        f"(dernière erreur: {last_unicode_err})"
    )

