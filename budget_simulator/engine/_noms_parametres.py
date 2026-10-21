"""Noms de paramètres admis par levier — GÉNÉRÉ, NE PAS ÉDITER.

Généré par ``scripts/generate_measure_registry.py`` depuis le code : les
lectures du dict ``params`` dans le corps des handlers (même extracteur
que ``docs/MEASURE_REGISTRY.md``), ``intensite`` pour les leviers
d'``INTENSITE_DOMAINS``, et les lectures ``p.get(...)`` des formules
ASTEVAL de ``policy_measures.json`` pour les leviers sans handler.

``MODES_EXCLUSIFS`` : noms admis mais IGNORÉS quand un autre est fourni
(lambda héritée de ``_resolve_intensite_or_legacy``, branche « absent »
d'un ``if 'k' in params``) — réfutation de V2-04.

Consommé par la porte des noms (``engine/_param_domain.py``,
``valider_noms_parametres``, v0.6.10 — contre-audit externe V2-04).
Synchronisation verrouillée par ``tests/test_noms_parametres_sync.py``
(``--noms --check``). Régénérer :
``python scripts/generate_measure_registry.py --noms``.
"""

NOMS_PARAMETRES_ADMIS: dict[str, frozenset[str]] = {
    'abattement_retraites': frozenset({'reforme_active'}),
    'asu': frozenset({'asu_activation', 'asu_plafonnement'}),
    'chomage_alloc': frozenset({'degressivite', 'duree', 'montant', 'taux_remplacement'}),
    'collectivites': frozenset({'dotation', 'investissement'}),
    'cotisations_patronales': frozenset({'taux'}),
    'cotisations_salariales': frozenset({'baisse_points'}),
    'csg': frozenset({'progressive', 'taux'}),
    'defense': frozenset({'budget'}),
    'education': frozenset({'budget', 'enseignants', 'salaires'}),
    'elargissement_ir': frozenset({'taux_contribuables_cible'}),
    'exonerations_salaires': frozenset({'intensite', 'seuil_hausse', 'taux_exoneration'}),
    'fiscalite_patrimoine': frozenset({'intensite'}),
    'fonction_publique': frozenset({'effectifs', 'point_indice'}),
    'fonction_publique_reforme': frozenset({'digitalisation', 'fusion_agences'}),
    'fraude_fiscale': frozenset({'effort'}),
    'fraude_sociale': frozenset({'effort'}),
    'immigration': frozenset({'ame', 'integration'}),
    'impot_revenu': frozenset({'decote', 'taux_superieur'}),
    'impot_societes': frozenset({'niches', 'taux'}),
    'impots_production': frozenset({'montant'}),
    'is_exceptionnel_tge': frozenset({'montant'}),
    'isf_climatique': frozenset({'intensite'}),
    'niches_fiscales_tge': frozenset({'montant'}),
    'niches_sociales_tge': frozenset({'montant'}),
    'optimisation_dette': frozenset({'intensite'}),
    'prestations_indexation': frozenset({'taux_indexation'}),
    'rabot_uniforme': frozenset({'exclure_defense', 'exclure_dette', 'exclure_ue', 'taux_reduction'}),
    'recherche_publique': frozenset({'budget'}),
    'retraites': frozenset({'age_depart', 'duree_cotisation', 'indexation'}),
    'sante': frozenset({'effort_ambu', 'effort_hopital', 'effort_prev_org', 'franchise_participation_taux', 'prevention_budget'}),
    'smic': frozenset({'montant_brut'}),
    'subventions_tge': frozenset({'montant'}),
    'taxe_superprofits': frozenset({'intensite', 'seuil_hausse', 'taux', 'tous_secteurs'}),
    'transition_ecologique': frozenset({'investissement', 'renovation', 'taxe_carbone'}),
    'tva_energie': frozenset({'taux'}),
    'tva_rate': frozenset({'taux'}),
}

MODES_EXCLUSIFS: dict[str, dict[str, frozenset[str]]] = {
    'chomage_alloc': {
        'taux_remplacement': frozenset({'montant'}),
    },
    'exonerations_salaires': {
        'intensite': frozenset({'seuil_hausse', 'taux_exoneration'}),
    },
    'taxe_superprofits': {
        'intensite': frozenset({'seuil_hausse', 'taux', 'tous_secteurs'}),
    },
}
