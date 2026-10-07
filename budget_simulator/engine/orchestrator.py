"""Bloc moteur — Orchestrateur (boucle de simulation + dispatch des mesures).

Méthodes couvertes :
- ``simulate`` : boucle de simulation principale (année par année).
  Réinitialise l'état, amorce 2025, puis pour chaque année : démographie,
  recettes/dépenses de base, application des mesures, croissance,
  inflation, dette, chômage, Gini, pouvoir d'achat, compétitivité,
  validation, agrégation des résultats. Orchestre les 11 méthodes macro
  des autres mixins (10 ``calculate_*`` + ``update_potential_growth`` ;
  ``update_demography`` est propre à l'orchestrateur).
- ``apply_measures`` : dispatch central des mesures (handler Python
  prioritaire, sinon formule ASTEVAL), plafonds 5 % PIB / mesure et
  10 % PIB total (FMI 2010), flag ``HANDLER_FAILED_KEY`` + mode
  ``BUDGETLAB_STRICT``.
- ``detect_active_measures`` : liste les mesures écartées de leur valeur
  par défaut (log de débogage en 2026).
- ``update_demography`` : met à jour la population (taux net +
  vieillissement post-2030).

Ce mixin est l'ASSEMBLEUR : il ne porte presque aucune logique
économique propre (déléguée aux mixins ``handlers/`` et ``engine/`` via
``self``), mais lit/écrit massivement l'état d'instance de
``BudgetSimulatorV45``. Le contrat producteur/consommateur DÉTAILLÉ de
chaque état partagé (``recettes_precedentes``, ``inflation_precedente``,
``_potential_growth_bonus``, ``_fiscal_impulses``, ``debt_structure``,
``_spending_factors``, ...) est documenté côté mixin PRODUCTEUR
(``engine/revenues.py``, ``engine/inflation.py``, ``engine/growth.py``,
``engine/debt.py``, ``engine/expenditures.py``) — non redupliqué ici
pour éviter la dérive documentaire.

Le SEUL invariant que ce mixin porte en propre (non documentable côté
producteur, car imposé par ``simulate`` seul) est le CONTRAT D'ORDRE
des appels dans la boucle annuelle (refonte « assemblage temporel »
2026-06) :
``calculate_growth`` / ``calculate_inflation`` (macro de l'année,
consomment l'impulsion budgétaire de t−1 : ``_budget_effort_prev`` /
``_parts_prev`` / ``_last_impacts``) → mise à jour PIB (déflateur
contemporain) → ``calculate_unemployment`` (Okun sur la croissance de
l'année) → ``calculate_revenues`` / ``calculate_expenditures`` (flux
organiques AUX PRIX DE L'ANNÉE) → ``apply_measures`` (deltas mesures ;
``budget_effort`` de l'année stocké pour t+1) →
``update_potential_growth`` (clôt l'année). Réordonner ces appels casse
les contrats producteur/consommateur même si chaque méthode reste
byte-identique — l'enforcement observable est porté par
``tests/test_baseline_properties.py`` (l'élasticité 1,00 ± 0,02 et le
déflatage contemporain dévient immédiatement si les flux repassent sur
la macro de t−1).

Note historique (Phase 2, 2026-05-16) : un ajustement d'élasticité
recettes post-``calculate_inflation`` a été supprimé — voir le
tombstone inline (boucle annuelle) et ``docs/REFACTOR_SPLIT_PLAN.md``.

Helpers / état hôte via MRO (NON migrés, restent sur
``BudgetSimulatorV45``) : ``_reset_state``, ``_get_default_values``,
``_apply_complex_measure`` (Section 7 legacy : dispatch handler Python,
sous garde `measure_id in measure_handlers` côté ``apply_measures``),
``validator`` (``EconomicValidator``), ``aeval``
(``asteval.Interpreter``), ``measure_registry`` / ``measure_handlers``,
constantes de classe (``INVESTMENT_FLOW_MEASURES`` ...), et tout l'état
d'instance initialisé dans ``__init__`` / ``_reset_state``.

``_BUDGET_KEYS`` (détail interne, aucun consommateur externe) est
local à ce module. (``INDEXATION_BASELINE_RATIO``, « protection
d'indexation » du pouvoir d'achat, a été SUPPRIMÉE en v0.6.7 : elle ne
compensait qu'une double soustraction de l'inflation, cf. bloc PA de
``simulate``.)

Catch large pré-existant : ``apply_measures`` enveloppe chaque mesure
d'un ``except Exception`` qui logge ``logger.error(exc_info=True)`` +
pose ``HANDLER_FAILED_KEY`` dans ``impacts`` + escalade si
``BUDGETLAB_STRICT`` (fail-fast CI). Ce catch-ci n'est PAS silencieux
(``logger.error`` + flag d'état observable + golden master Phase 0.7) —
à distinguer du catch silencieux supply-side de ``update_potential_growth``
(``engine/growth.py``, tracé Phase 2). Préservé byte-for-byte.

Sink de logs : ``self.debug_logs`` via ``_log_debug``.
Tous attributs d'instance de ``BudgetSimulatorV45``.
"""
import functools
import logging
import os
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from .._logging import _log_debug
from ..constants import (
    CHARGES_INTERET_MD_EUR,
    GINI_CONVERGENCE_RATE,
    GINI_HARD_CEILING,
    GINI_IMPACT_SCALE,
    GINI_SOFT_FLOOR,
    COMPETITIVITE_VARIATION_ANNUELLE_MAX,
    HANDLER_FAILED_KEY,
    PA_VARIATION_ANNUELLE_MAX,
)
from .rdb import borner_canaux, rdb_annee
from ._param_domain import (
    EntreeInvalide,
    assainir_mesures,
    leviers_presents,
    tracer_si_levier_null,
    validate_intensite_domain,
    validate_param_domains,
)

logger = logging.getLogger(__name__)


def _mode_strict() -> bool:
    """BUDGETLAB_STRICT (CI/calibration) : escalade au lieu d'absorber."""
    return os.environ.get('BUDGETLAB_STRICT', '').strip().lower() in ('1', 'true', 'yes')


def _entree_retablie(simulate):
    """Porte d'ENTRÉE (v0.6.7) : le temps de la simulation, ``self.mesures``
    est la version corrigée de l'entrée (``assainir_mesures``), pour que les
    lecteurs latéraux lisent les valeurs corrigées et non les brutes. L'entrée
    de l'appelant est rétablie ensuite (y compris sur exception), pour qu'un
    second ``simulate()`` re-signale les mêmes corrections."""
    @functools.wraps(simulate)
    def enveloppe(self):
        brutes = self.mesures
        try:
            return simulate(self)
        finally:
            self.mesures = brutes
    return enveloppe


def _borner_variation(valeur: float, borne: float) -> tuple[float, bool]:
    """Variation annuelle bornée à ±``borne`` — rend aussi si la borne a mordu."""
    if -borne <= valeur <= borne:
        return valeur, False
    return float(np.clip(valeur, -borne, borne)), True

_BUDGET_KEYS = frozenset({'depenses', 'recettes'})


class OrchestratorMixin:
    """Bloc moteur — Orchestrateur (boucle de simulation + dispatch des mesures)."""

    @staticmethod
    def prochain_output_gap(gap: float, croissance: float, croissance_potentielle: float) -> float:
        """Output gap en NIVEAU (v0.6.7, audit Codex 10/2026, bloc A constat 3).

        Définition BCE / OCDE / FMI / Commission européenne : écart du PIB réel
        à son potentiel, rapporté au potentiel. Les deux niveaux croissant à g
        et g*, (1 + gap_t) = (1 + gap_{t−1}) × (1 + g_t) / (1 + g*_t) — une
        identité, sans paramètre.

        Jusqu'en v0.6.6 : ``0,8·gap + 0,2·(g − g*)``, moyenne mobile de l'écart
        de CROISSANCE qui effaçait chaque année 20 % d'un écart de niveau réel
        (statu quo 2034 : −0,40 % servi contre −2,68 % mesuré en niveau). Le
        gap ne se referme plus par décret : seulement si la croissance dépasse
        le potentiel. Aucun terme de fermeture n'est ajouté ici — une fermeture
        dans la seule statistique de gap la rendrait différente de l'écart de
        niveau effectivement simulé (le PIB, lui, ne revient pas au potentiel) ;
        un retour au potentiel est une propriété de l'équation de CROISSANCE.
        """
        return (1 + gap) * (1 + croissance) / (1 + croissance_potentielle) - 1

    def detect_active_measures(self) -> List[str]:
        """Détecte les mesures activement modifiées"""
        defaults = self._get_default_values()
        active_measures = []

        # Levier à `null` = absent (même règle qu'apply_measures).
        for measure_id, params in leviers_presents(self.mesures).items():
            if measure_id not in defaults:
                continue
            # Auxiliaire de JOURNALISATION uniquement (appelé une fois, en
            # 2026, pour lister les leviers déviés). Un payload illisible ne
            # doit donc jamais y décider du sort de la simulation : sans cette
            # garde, un `mesures['x']` non-dict levait ici une AttributeError
            # AVANT `apply_measures`, c'est-à-dire hors du `try` per-mesure qui
            # trace (logger.error + HANDLER_FAILED_KEY). On l'ignore ici pour
            # que l'anomalie ressorte par la porte unique, qui la qualifie.
            if not isinstance(params, dict):
                continue
            for param_name, value in params.items():
                if param_name not in defaults[measure_id]:
                    continue
                default_val = defaults[measure_id][param_name]

                if isinstance(value, bool):
                    if value != default_val:
                        active_measures.append(f"{measure_id}.{param_name}={value}")
                elif isinstance(value, (int, float)):
                    threshold = 0.5 if isinstance(default_val, int) else 0.01
                    # Même règle que pour un bloc illisible ci-dessus : un entier
                    # hors de la plage des flottants (JSON de 400 chiffres) levait
                    # OverflowError au formatage, hors du `try` per-mesure → 500
                    # en tolérant (v0.6.7). La valeur est ignorée par ce journal ;
                    # la porte d'apply_measures la qualifie (échec tracé).
                    try:
                        if abs(value - default_val) > threshold:
                            active_measures.append(f"{measure_id}.{param_name}={value:.2f}")
                    except (OverflowError, TypeError, ValueError):
                        continue

        return active_measures

    def update_demography(self, annee: int):
        """Met à jour la démographie"""
        taux_net = (
            self.demography['taux_natalite'] -
            self.demography['taux_mortalite'] +
            self.demography['solde_migratoire']
        )

        if annee >= 2030:
            taux_net -= self.demography['taux_vieillissement'] * 0.5

        self.demography['population'] *= (1 + taux_net)
        _log_debug(self.debug_logs, f"Y{annee-2025}: Population {self.demography['population']:.1f}M")

    def apply_measures(self, year: int, spending: float, revenues: float,
                       gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, Dict]:
        """
        Applique les mesures budgétaires pour ajuster dépenses et recettes.
        - Type "formule" : utilise ASTEVAL avec post-traitement (ex. CSG avec effet Laffer).
        - Type "fonction" : traitement spécifique via _apply_complex_measure.
        - Plafonne les impacts à 5% PIB par mesure, 10% PIB total (FMI, 2010).
        Returns: (dépenses ajustées, recettes ajustées, dictionnaire des impacts).
        """
        delta_spending_total = 0
        delta_revenue_total = 0
        impacts = {}
        # Leviers publiés au RAPPORT (measure_impacts de l'API) — cf. le filtre de
        # significativité plus bas ; le moteur, lui, lit `impacts` en entier.
        self._impacts_publies = set()
        # Log des mesures actives en 2026 pour débogage
        if year == 2026:
            active_measures = self.detect_active_measures()
            if active_measures:
                _log_debug(self.debug_logs, "=== MESURES ACTIVES ===")
                for measure in active_measures:
                    _log_debug(self.debug_logs, f" • {measure}")
            else:
                _log_debug(self.debug_logs, "=== STATUS QUO - Aucune mesure active ===")
        # Traite chaque mesure définie dans self.mesures
        # BUDGETLAB_STRICT (CI/calibration) : collecter toutes les mesures en
        # échec d'une même année et lever un ExceptionGroup APRÈS la boucle,
        # plutôt qu'un fail-fast sur la première (qui masquerait les suivantes).
        strict_mode = _mode_strict()
        strict_failures: list[Exception] = []
        # `warned` : dédup des WARNING de la porte sur la durée d'une
        # simulation (reset dans _reset_state) — le clamp/retrait reste
        # appliqué chaque année, seule la journalisation est dédupliquée.
        # Initialisés ici si apply_measures est appelée hors simulate()
        # (tests unitaires).
        if not hasattr(self, '_domain_clamp_warned'):
            self._domain_clamp_warned = set()
        if not hasattr(self, '_corrections'):
            self._corrections, self._avis = {}, {}
        for measure_id, parameters in self.mesures.items():
            if measure_id not in self.measure_registry:
                _log_debug(self.debug_logs, f"⚠ Mesure {measure_id} inconnue - ignorée")
                continue
            measure = self.measure_registry[measure_id]
            delta_spending, delta_revenue = 0, 0
            # Bloc `null` = levier ABSENT : sauté, absent de `impacts` (≠ `{}` ;
            # un bloc mal formé, lui, échoue bruyamment ci-dessous).
            if tracer_si_levier_null(measure_id, parameters,
                                     warned=self._domain_clamp_warned):
                continue
            try:
                # Porte unique Lot C Item 1 : borne intensite par domaine
                # AVANT le dispatch. Tolérant = warning+clamp ; STRICT =
                # ValueError capté par l'except infra → ExceptionGroup
                # (synergie Item 3). No-op (objet identique) hors registre
                # ou intensite valide → golden master byte-identique.
                parameters = validate_intensite_domain(
                    measure_id, parameters, strict=strict_mode,
                    warned=self._domain_clamp_warned,
                    corrections=self._corrections,
                )
                # Même porte pour les paramètres NOMMÉS des handlers
                # symétrisés (PARAM_DOMAINS, revue 2026-08-04) : ferme la
                # propagation silencieuse de NaN et la bande hors-UI ; retire
                # aussi les clés à `None` (null = pas de valeur → défaut du
                # handler, Sentry FRANCE-BUDGET-Z).
                parameters = validate_param_domains(
                    measure_id, parameters, strict=strict_mode,
                    warned=self._domain_clamp_warned,
                    corrections=self._corrections,
                )
                if measure_id in self.measure_handlers:
                    # Python handler takes precedence over ASTEVAL formula
                    delta_spending, delta_revenue, measure_impacts = self._apply_complex_measure(
                        measure, parameters, year, gdp, inflation, unemployment
                    )
                    # Contrat v0.6.8 : un handler qui déplace des euros dit
                    # lesquels touchent les ménages (clé `menages`, à zéro si
                    # aucun). Sans elle, l'indice de pouvoir d'achat compterait
                    # le levier nul SANS le dire : échec bruyant (ERROR +
                    # HANDLER_FAILED_KEY, escalade stricte) par l'except infra.
                    if (delta_spending or delta_revenue) and 'menages' not in measure_impacts:
                        raise RuntimeError(
                            f"handler {measure_id} sans canaux ménages (clé 'menages')")
                elif measure.get('type') == 'formule':
                    # Fall back to ASTEVAL formula
                    context = {
                        'p': parameters,
                        'annee': year,
                        'pib': gdp,
                        'consommation': 0.53 * gdp,
                        'masse_salariale': 0.52 * gdp,
                        'profits': 0.25 * gdp,
                        'inflation': inflation,
                        'chomage': unemployment
                    }
                    self.aeval.symtable = context
                    result = self.aeval(measure['formule'])
                    if self.aeval.error:
                        # v0.6.7 : l'échec d'une formule suit le chemin d'un
                        # handler qui lève (except ci-dessous : ERROR,
                        # HANDLER_FAILED_KEY, escalade stricte). Avant : ERROR
                        # puis `result = 0`, levier compté nul SANS drapeau
                        # dans la réponse et sans escalade même en strict.
                        error_msgs = [str(e.get_error()) for e in self.aeval.error]
                        self.aeval.error = []
                        raise RuntimeError(
                            f"formule ASTEVAL en échec : {'; '.join(error_msgs)}")
                    elif result is None:
                        result = 0
                    # Post-traitement pour ajustements spécifiques (ex. effet Laffer CSG)
                    if measure.get('cible') == 'depenses':
                        delta_spending = result
                        measure_impacts = {'depenses': delta_spending}
                    elif measure.get('cible') == 'recettes':
                        delta_revenue = result
                        measure_impacts = {'recettes': delta_revenue}
                    elif measure.get('cible') == 'mixte':
                        delta_spending = result * 0.6
                        delta_revenue = result * 0.4
                        measure_impacts = {'depenses': delta_spending, 'recettes': delta_revenue}
                    # Contrat v0.6.8 (revue passe 1, L2) : une formule ne pose
                    # aucun canal ménages. Côté dépenses, zéro effet direct est
                    # l'arbitrage 2 ; côté recettes, l'indice compterait la taxe
                    # nulle SANS le dire → avis explicite (une fois par levier).
                    if delta_revenue and (measure_id, 'FORMULE_MENAGES') not in self._domain_clamp_warned:
                        self._domain_clamp_warned.add((measure_id, 'FORMULE_MENAGES'))
                        logger.warning(
                            "Formule %s côté recettes sans canal ménages : effet direct "
                            "sur le pouvoir d'achat compté nul", measure_id)
                        self._avis.setdefault(
                            (measure_id, 'FORMULE_MENAGES'),
                            f"{measure_id} : mesure « formule » côté recettes, sans "
                            f"canal ménages — effet direct sur le pouvoir d'achat "
                            f"compté nul (seul l'effet par la croissance), dès {year}")
                else:
                    # No handler and no formula - skip
                    _log_debug(self.debug_logs, f"Mesure {measure_id}: ni handler Python ni formule ASTEVAL - ignoree")
                    continue
                # Plafonne impacts individuels à 5% PIB (FMI, 2010)
                max_impact = 0.05 * gdp
                # Detection clip : signal une mesure aux ordres de grandeur suspects (calibration ou bug)
                if abs(delta_spending) > max_impact or abs(delta_revenue) > max_impact:
                    # Une ligne par levier et par simulation (v0.6.7) : le
                    # plafond mord en général chaque année, à l'identique.
                    if (measure_id, 'CLIP_5') not in self._domain_clamp_warned:
                        self._domain_clamp_warned.add((measure_id, 'CLIP_5'))
                        logger.warning(
                            "CLIP 5%% PIB Y%d %s : delta_spending=%.1f delta_revenue=%.1f (max=%.1f)",
                            year, measure_id, delta_spending, delta_revenue, max_impact,
                        )
                    self._avis.setdefault(
                        (measure_id, 'CLIP_5'),
                        f"{measure_id} : impact plafonné à 5 % du PIB par "
                        f"mesure (plafond du modèle, FMI 2010), dès {year}")
                clip_dep = np.clip(delta_spending, -max_impact, max_impact)
                clip_rec = np.clip(delta_revenue, -max_impact, max_impact)
                if 'menages' in measure_impacts:
                    # Même plafond pour les euros des ménages que pour le budget
                    # dont ils sont issus, côté par côté, puis le plafond lui-même
                    # sur chaque canal (un canal sans contrepartie budgétaire ne
                    # lui échappe pas). No-op sur les scénarios publiés.
                    canaux = borner_canaux(
                        measure_impacts['menages'],
                        clip_dep / delta_spending if delta_spending else 1.0,
                        clip_rec / delta_revenue if delta_revenue else 1.0)
                    bornes = {c: float(np.clip(v, -max_impact, max_impact))
                              for c, v in canaux.items()}
                    if bornes != canaux:
                        self._avis.setdefault(
                            (measure_id, 'CLIP_5'),
                            f"{measure_id} : impact plafonné à 5 % du PIB par "
                            f"mesure (plafond du modèle, FMI 2010), dès {year}")
                    measure_impacts['menages'] = bornes
                delta_spending, delta_revenue = clip_dep, clip_rec
                # Propager le clip aux measure_impacts (sinon multiplicateur calculé sur valeur
                # non-clip mais budget appliqué sur valeur clip → incohérence interne)
                measure_impacts['depenses'] = delta_spending
                measure_impacts['recettes'] = delta_revenue
                delta_spending_total += delta_spending
                delta_revenue_total += delta_revenue

                # Vérifier si la mesure a un impact budgétaire OU macroéconomique significatif
                has_budget_impact = abs(delta_spending) > 0.1 or abs(delta_revenue) > 0.1
                has_macro_impact = (
                    abs(measure_impacts.get('gini', 0)) > 0.0001 or
                    abs(measure_impacts.get('competitivite', 0)) > 0.0001 or
                    any(abs(v) > 0.1 for v in measure_impacts.get('menages', {}).values())
                )

                # v0.6.7 (lot 3b) : TOUT levier évalué entre dans `impacts`, que lit
                # le moteur (impulsions et multiplicateurs, effets directs sur le
                # chômage, impact TVA, Gini, compétitivité, clip 10 %) ; un levier
                # aux effets nuls n'y change rien. Le filtre de significativité ne
                # décide plus que du RAPPORT (measure_impacts de l'API, inchangé).
                # Appliqué au moteur, il comptait le BUDGET d'un levier à |Δ| ≤ 0,1
                # Md€ sans son effet macro, qui « apparaissait » d'un coup au seuil :
                # prévention de im_rabot_2029 à 7,6 Md€, gap 2027 −2,0002 → −1,9992,
                # bascule de régime, −1,67 pt de dette 2035 (08810ad).
                impacts[measure_id] = measure_impacts
                if has_budget_impact or has_macro_impact:
                    self._impacts_publies.add(measure_id)
                    if has_budget_impact:
                        _log_debug(self.debug_logs,
                            f"Mesure {measure_id}: "
                            f"Δdép={delta_spending:.1f} Md€, "
                            f"Δrec={delta_revenue:.1f} Md€"
                        )
            except Exception as e:
                # Une ligne par levier et par simulation (v0.6.7 : avant, une
                # par année simulée — 50 événements Sentry pour periods=50).
                # Faute de l'APPELANT (valeur non numérique, hors domaine en
                # strict) → WARNING ; tout le reste est un bug moteur → ERROR.
                if isinstance(e, EntreeInvalide):
                    if (measure_id, 'PARAM_INVALIDE') not in self._domain_clamp_warned:
                        self._domain_clamp_warned.add((measure_id, 'PARAM_INVALIDE'))
                        logger.warning(
                            "PARAM_INVALIDE %s : %s — levier en échec, effet "
                            "compté nul (entrée appelante à corriger)", measure_id, e,
                        )
                    cause = str(e)
                elif (measure_id, 'ECHEC') not in self._domain_clamp_warned:
                    self._domain_clamp_warned.add((measure_id, 'ECHEC'))
                    logger.error("Mesure %s échouée: %s", measure_id, e, exc_info=True)
                    cause = "erreur interne du moteur"
                else:
                    cause = "erreur interne du moteur"
                self._corrections.setdefault(
                    (measure_id, 'ECHEC'),
                    f"{measure_id} : levier en échec ({cause}), effet compté nul")
                _log_debug(self.debug_logs, f"⚠ Erreur mesure {measure_id}: {e}")
                # _handler_failed évite qu'une régression silencieuse passe quand la mesure
                # était à default (delta=0 attendu == 0 obtenu sur crash). Voir
                # docs/REFACTOR_SPLIT_PLAN.md Phase 0.7.
                self._impacts_publies.add(measure_id)  # un échec est toujours publié
                impacts[measure_id] = {
                    'erreur': str(e),
                    'depenses': 0,
                    'recettes': 0,
                    HANDLER_FAILED_KEY: True,
                }
                # BUDGETLAB_STRICT (CI/calibration) escalade ; prod absorbe pour
                # ne pas casser le service citoyen. On annote l'exception de la
                # mesure fautive et on la collecte : l'ExceptionGroup est levé
                # après la boucle (cf. strict_failures supra).
                if strict_mode:
                    e.add_note(f"measure_id={measure_id}, year={year}")
                    strict_failures.append(e)
        # Fail-fast STRICT : lever en une fois toutes les exceptions handler
        # collectées, AVANT d'appliquer des totaux issus d'un calcul partiel.
        # apply_measures est appelée une fois PAR ANNÉE → strict_failures est
        # borné à l'année courante (pas d'accumulation inter-annuelle).
        # INVARIANT : aucun code exécutable ne doit s'intercaler entre la fin
        # de la boucle ci-dessus et ce raise — sinon une exception levée là
        # masquerait silencieusement les strict_failures collectées.
        if strict_failures:
            raise ExceptionGroup(
                f"{len(strict_failures)} handler(s) en échec en mode BUDGETLAB_STRICT",
                strict_failures,
            )
        # Plafonne l'impact total à 10% PIB (FMI, 2010)
        total_impact = abs(delta_spending_total) + abs(delta_revenue_total)
        if total_impact > 0.10 * gdp:
            scaling_factor = (0.10 * gdp) / total_impact
            # Plafond systémique (FMI 2010) : signal visible hors mode debug —
            # cohérent avec le CLIP 5 % PIB par mesure (un total >10 % PIB
            # traduit une calibration agrégée aberrante, pas un cas nominal).
            # Une ligne par simulation (v0.6.7) : le plafond mord en général
            # chaque année — avant, 10 WARNING par requête sur 10 ans.
            if ('*', 'CLIP_10') not in self._domain_clamp_warned:
                self._domain_clamp_warned.add(('*', 'CLIP_10'))
                logger.warning(
                    "CLIP 10%% PIB TOTAL Y%d : impact total %.1f Md€ > 10%% PIB "
                    "(plafond=%.1f Md€) → scaling ×%.4f",
                    year, total_impact, 0.10 * gdp, scaling_factor,
                )
            self._avis.setdefault(
                ('*', 'CLIP_10'),
                f"impact total des mesures plafonné à 10 % du PIB (plafond du "
                f"modèle, FMI 2010), dès {year}")
            delta_spending_total *= scaling_factor
            delta_revenue_total *= scaling_factor
            for measure_id in impacts:
                for key, val in impacts[measure_id].items():
                    if key in _BUDGET_KEYS and isinstance(val, (int, float, np.integer, np.floating)):
                        impacts[measure_id][key] = val * scaling_factor
                if 'menages' in impacts[measure_id]:
                    impacts[measure_id]['menages'] = borner_canaux(
                        impacts[measure_id]['menages'], scaling_factor, scaling_factor)
            _log_debug(self.debug_logs, f"Y{year}: Mesures plafonnées à 10% PIB")
        # Mise à jour des dépenses et recettes
        spending += delta_spending_total
        revenues += delta_revenue_total

        if year == 2026 or abs(delta_revenue_total) > 10:
            _log_debug(self.debug_logs, f"Y{year}: 📊 RECETTES FINALES:")
            _log_debug(self.debug_logs, f"  Base (avant mesures): {revenues - delta_revenue_total:.1f} Md€")
            _log_debug(self.debug_logs, f"  Delta mesures: {delta_revenue_total:.1f} Md€")
            _log_debug(self.debug_logs, f"  TOTAL: {revenues:.1f} Md€")
            _log_debug(self.debug_logs, f"  Ratio/PIB: {revenues/gdp*100:.1f}%")

        return spending, revenues, impacts

    @_entree_retablie
    def simulate(self) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
        """
        Simulation principale V4.5 avec OUTPUT_GAP DYNAMIQUE CORRIGÉ
        """
        # Réinitialiser TOUT l'état mutable avant chaque simulation
        # Sans cela, un second appel démarre depuis l'état final du premier
        self._reset_state()
        # Porte d'ENTRÉE (v0.6.7), cf. _entree_retablie. Objet identique si
        # tout est valide (golden master byte-identique).
        self.mesures = assainir_mesures(
            self.mesures, strict=_mode_strict(),
            warned=self._domain_clamp_warned,
            corrections=self._corrections, avis=self._avis,
        )

        # Guard: PIB_BASE doit être > 0 pour éviter divisions par zéro
        if self.base_params['pib_base'] <= 0:
            raise ValueError(f"PIB_BASE invalide: {self.base_params['pib_base']}. Doit être > 0.")

        results_list = []
        results_detailed = []
        validation_log = []
        measure_impacts_by_year = []  # NOUVEAU: stockage des impacts par mesure par année

        # État initial
        gdp_nominal = self.pib_nominal
        gdp_real = self.pib_reel_base2025
        debt = self.dette_courante
        unemployment = self.base_params['chomage_base']
        inflation = self.base_params['inflation_base']
        growth = self.base_params['croissance_potentielle']
        output_gap = self.output_gap_courant  # init = OUTPUT_GAP_INITIAL (constants.py, source unique)
        purchasing_power = 100.0  # Initialisation avant la boucle (base 100 en 2025)
        pib_nominal_2025 = gdp_nominal
        # Décomposition de l'indice de pouvoir d'achat par année (engine/rdb.py),
        # non arrondie : traçabilité et tests.
        self._rdb_trace = {}
        competitivite_index = 100.0  # Indice de compétitivité des entreprises (base 100 en 2025)

        # Boucle de simulation
        for year_idx in range(0, self.periods + 1):
            year = self.annee_base + year_idx
            _log_debug(self.debug_logs, f"\n{'='*50}")
            _log_debug(self.debug_logs, f"ANNÉE {year}")
            _log_debug(self.debug_logs, '='*50)

            if year_idx == 0:
                _log_debug(self.debug_logs, f"AVANT Y2026: recettes_precedentes = {self.recettes_precedentes:.1f}")
                # Année 2025 (réalisé INSEE provisoire 2025)
                revenues = self.base_params['recettes_base']  # 1562
                spending = self.base_params['depenses_base'] - CHARGES_INTERET_MD_EUR  # 1714 - 64,7 = 1649,3
                interest_rate = self.base_params['taux_interet_base']
                interests = CHARGES_INTERET_MD_EUR
                deficit = revenues - (spending + interests)  # 1562 - 1714 = -152 (≈ -5,1% PIB)
                impacts = {}
                budget_effort = 0
                multiplier = 1.0
                growth = self.base_params['croissance_2025']  # INSEE: 0.9%
                inflation = self.base_params['inflation_base']  # source unique : INFLATION_BASE (seed inertie)
                self.recettes_precedentes = revenues  # 1545 Md€
                self.inflation_precedente = inflation    # 1.0%

                # NOUVEAU: Stocker impacts vides pour 2025
                measure_impacts_by_year.append({'Année': year})
            else:
                # Variables d'état
                unemployment_gap = unemployment - self.base_params['chomage_nairu']
                debt_ratio = debt / gdp_nominal

                self.update_demography(year)

                # Canal d'offre de travail seniors (v0.6.1, I7) : posé en TÊTE
                # d'année, avant calculate_growth. Contrairement à l'impulsion
                # budgétaire (laguée d'un an pour casser la circularité
                # mesures → macro → flux → mesures), un choc d'offre de travail
                # ne dépend que du paramètre de politique et du calendrier légal
                # de l'AOD : rien à casser, et le lagger décalerait d'un an tout
                # le profil publié. Conséquence recherchée : croissance, Okun et
                # output gap de l'année lisent TOUS le même potentiel, bonus
                # inclus — le choc d'offre n'ouvre donc aucun écart (I6).
                self.update_labour_supply(year)

                _log_debug(self.debug_logs, f"Y{year_idx}: Output gap = {output_gap:.3f}")

                # ============================================================
                # REFONTE « assemblage temporel » (2026-06) — ordre de calcul :
                #   1. macro de l'année (growth, inflation) avec l'IMPULSION
                #      BUDGÉTAIRE DE t−1 (lag standard : casse la circularité
                #      mesures→macro→flux→mesures sans recherche de point fixe) ;
                #   2. PIB nominal de l'année (déflateur contemporain) ;
                #   3. chômage contemporain (Okun sur la croissance de l'année) ;
                #   4. flux budgétaires AUX PRIX DE L'ANNÉE ;
                #   5. mesures de l'année, impulsion stockée pour t+1.
                # L'ancien ordre calculait les flux avec growth/inflation de
                # t−1 pendant que le PIB portait celles de t : le numérateur
                # des ratios vivait un an derrière le dénominateur (bug
                # d'assemblage, cf. docs/plans/refonte-annee1-assemblage.md
                # du repo parent, diagnostic 2026-06-10).
                # ============================================================

                # π_{t−1} sauvegardée AVANT calculate_inflation (qui réécrit
                # self.inflation_precedente en interne) : alimente la part
                # indexée sur l'inflation passée dans calculate_expenditures.
                inflation_prev_year = self.inflation_precedente

                # --- 1. Macro de l'année, impulsion budgétaire de t−1 ---
                economic_state_growth = {
                    'output_gap': output_gap,
                    'unemployment_gap': unemployment_gap,
                    'effort_budgetaire': self._budget_effort_prev,
                    'part_depenses': self._parts_prev['depenses'],
                    'part_investissement': self._parts_prev['investissement'],
                    'debt_ratio': debt_ratio,
                    'interest_rate': self.base_params['taux_interet_base'],
                    'unemployment': unemployment,
                    'deficit_ratio': deficit / gdp_nominal  # déficit t−1 / PIB fin t−1
                }
                growth = self.calculate_growth(year_idx, economic_state_growth)
                _log_debug(self.debug_logs, f"Y{year_idx}: Croissance = {growth:.3f}")

                economic_state_inflation = {
                    'output_gap': output_gap,
                    'unemployment_gap': unemployment_gap,
                    'effort_budgetaire': self._budget_effort_prev,
                    # Impacts de t−1 (_last_impacts) : les mesures de t ne sont
                    # pas encore calculées. Le gate temporel (one-shot à
                    # year == 2) vit dans calculate_inflation — source unique.
                    'tva_impact': self._last_impacts.get('tva_rate', {}).get('recettes', 0) / gdp_nominal
                }
                inflation = self.calculate_inflation(year_idx, economic_state_inflation)
                _log_debug(self.debug_logs, f"Y{year_idx}: Inflation = {inflation:.3f}")

                # [SUPPRIMÉ Phase 2 — 2026-05-16, option B] Un ajustement
                # d'élasticité recettes sur la VARIATION d'inflation se
                # trouvait après le calcul d'inflation (`revenues_after *= 1 +
                # (inflation - inflation_precedente) * 0.5`). NE PAS
                # réactiver : (1) mort par construction — calculate_inflation
                # réécrit self.inflation_precedente avant ce point (0/10 ans) ;
                # (2) double-comptage — calculate_revenues (engine/revenues.py)
                # modélise déjà inflation→recettes via l'élasticité au PIB
                # nominal. Réactivation = biais optimiste systématique de la
                # dette. Chiffrage + décision : docs/REFACTOR_SPLIT_PLAN.md
                # (item Phase 2 résolu).

                # --- 2. PIB de l'année (déflateur contemporain) ---
                gdp_real *= (1 + growth)
                self.deflateur_cumule *= (1 + inflation)
                gdp_nominal = gdp_real * self.deflateur_cumule
                _log_debug(self.debug_logs, f"Y{year_idx}: PIB nominal = {gdp_nominal:.1f}")

                # --- 3. Chômage contemporain (impacts directs des mesures :
                #        t−1 via _last_impacts, cohérent avec l'impulsion macro
                #        laguée d'un an) ---
                unemployment = self.calculate_unemployment(growth, unemployment, year_idx, self._last_impacts)

                # --- 4. Flux budgétaires aux prix de l'année ---
                revenues_base = self.calculate_revenues(gdp_nominal, growth, inflation, year_idx)
                spending_base = self.calculate_expenditures(
                    gdp_nominal,
                    inflation,            # déflateur contemporain (part non indexée)
                    inflation_prev_year,  # part indexée sur l'inflation passée
                    unemployment,
                    year_idx,
                    output_gap
                )

                _log_debug(self.debug_logs, f"Y{year_idx}: Base: rec={revenues_base:.1f}, dep={spending_base:.1f}")

                # --- 5. Mesures de l'année (handlers à l'inflation contemporaine) ---
                # Mémoire de l'inflation par année civile, lue par les handlers
                # qui cumulent un écart de prix sur plusieurs revalorisations
                # (v0.6.7 : désindexation des prestations — sans elle, l'écart
                # passé était réécrit à l'inflation du jour).
                self._inflation_par_annee[year] = inflation
                spending_after, revenues_after, impacts = self.apply_measures(
                    year, spending_base, revenues_base, gdp_nominal,
                    inflation, unemployment
                )

                self._last_impacts = impacts

                # NOUVEAU: Stocker les impacts de cette année pour le frontend
                year_impacts = {'Année': year}
                for measure_id, measure_data in impacts.items():
                    if isinstance(measure_data, dict) and measure_id in self._impacts_publies:
                        year_impacts[measure_id] = measure_data.copy()
                measure_impacts_by_year.append(year_impacts)

                # Effort budgétaire
                delta_spending = spending_after - spending_base

                # NOTE: Ajustement baseline dépenses DÉSACTIVÉ.
                # Les handlers retournent le delta TOTAL cumulé, pas marginal.
                # L'appliquer à la baseline créait un double-comptage (delta via handler
                # + baseline réduite). Nécessite un tracking per-handler des deltas
                # marginaux pour être implémenté correctement.

                delta_revenue = revenues_after - revenues_base

                # NOTE: Revenue compounding DÉSACTIVÉ (même bug que Fix 2).
                # Les handlers retournent le delta TOTAL chaque année, pas marginal.
                # Ajouter le delta total à recettes_precedentes créait un double-comptage :
                # TVA +7 Md€ compoundait à +77 Md€ en 10 ans au lieu de ~8 Md€.
                # recettes_precedentes reste la base organique (avant mesures).

                fiscal_impulse = delta_revenue - delta_spending
                budget_effort = fiscal_impulse / gdp_nominal

                total_measures = abs(delta_spending) + abs(delta_revenue)
                part_spending = abs(delta_spending) / total_measures if total_measures > 0 else 0
                part_revenue = 1 - part_spending

                # Seules les dépenses d'investissement PRODUCTIF comptent pour le multiplicateur élevé.
                # Utilise le frozenset de classe INVESTMENT_FLOW_MEASURES (centralisé)
                part_investment = sum(
                    abs(impacts.get(m, {}).get('depenses', 0))
                    for m in self.INVESTMENT_CORE_MEASURES
                ) / total_measures if total_measures > 0 else 0

                _log_debug(self.debug_logs, f"Y{year_idx}: Effort budgétaire = {budget_effort:.3f}")
                _log_debug(self.debug_logs, f"Composition: rec={part_revenue:.2f}, dep={part_spending:.2f}, inv={part_investment:.2f}")

                # Impulsion budgétaire de l'année stockée pour la macro de t+1
                # (lag standard d'un an, cf. en-tête du bloc REFONTE ci-dessus :
                # growth/inflation de t+1 consommeront cet effort et ces parts).
                self._budget_effort_prev = budget_effort
                self._parts_prev = {'depenses': part_spending, 'investissement': part_investment}

                revenues = revenues_after
                spending = spending_after

                # Taux d'intérêt et déficit
                marginal_rate = self.calculate_interest_rate(debt_ratio, year_idx, budget_effort)
                interests, interest_rate = self.calculate_interest_payment(debt, marginal_rate)
                deficit = revenues - spending - interests

                # (Chômage : calculé plus haut, étape 3 du bloc REFONTE — avant
                # les flux, pour que la dépense chômage de l'année suive le taux
                # contemporain.)

                # Dette
                nominal_growth = growth + inflation

                # Calcul principal - équation comptable
                debt = debt - deficit  # Déficit négatif = augmentation de dette
                # Borne 0 (v0.6.7) : une dette brute négative serait un stock
                # d'ACTIFS nets, que le modèle ne représente pas (ni intérêts
                # reçus, ni rendement : la courbe de taux n'a pas de plancher).
                # Inatteignable sur l'horizon servi par l'API (10 ans) ; un
                # appel direct sur 50 ans y arrivait (−37,7 % du PIB en 2075).
                if debt < 0:
                    self._corrections.setdefault(
                        ('Dette', 'SORTIE'),
                        f"Dette brute bornée à 0 dès {year} : excédents "
                        f"accumulés, actifs nets non modélisés")
                    debt = 0.0

                # Analyse Domar complémentaire (pour logs uniquement)
                if year_idx > 0:
                    debt_ratio = debt / gdp_nominal  # RECALCULER avec la nouvelle dette
                    r_minus_g = interest_rate - nominal_growth

                    # Vérification de cohérence
                    expected_debt_change = -deficit
                    actual_debt_change = debt - self.dette_courante

                    if abs(actual_debt_change - expected_debt_change) > 1:
                        _log_debug(self.debug_logs,
                            f"Y{year_idx}: ⚠️ Incohérence dette: "
                            f"Δ={actual_debt_change:.1f} vs déficit={-deficit:.1f}"
                        )

                    # Alerte soutenabilité
                    if r_minus_g > 0.01 and revenues - spending < 0:
                        _log_debug(self.debug_logs,
                            f"Y{year_idx}: 🚨 Dynamique explosive (r-g={r_minus_g*100:.2f}%)"
                        )

                # MISE À JOUR OUTPUT GAP - CRITIQUE !
                # Référence = croissance potentielle TOTALE, bonus d'offre
                # inclus (v0.6.1, correction I6, même raison que la loi
                # d'Okun) : l'output gap mesure un écart d'activité au
                # potentiel, un choc d'offre déplace les deux termes ensemble
                # et ne doit donc pas l'ouvrir. Lu contre la seule composante
                # tendancielle, il se décalait de ±0,20 pt en permanence et
                # contaminait la courbe de Phillips (inflation) puis le choix
                # du multiplicateur budgétaire.
                # ORDRE PRODUCTEUR → CONSOMMATEURS, sans aucun lag :
                # `update_labour_supply` est le PRODUCTEUR du bonus d'offre de
                # travail, et il tourne en TÊTE de CETTE itération d'année,
                # avant `calculate_growth`. Les trois consommateurs de
                # `croissance_potentielle_totale()` — la croissance, la loi
                # d'Okun (`calculate_unemployment`) et cette récurrence — lisent
                # donc TOUS l'état d'offre de l'année COURANTE. C'est l'objet
                # même de la correction I6 : lu contre un potentiel différent
                # du leur, l'output gap se décalait en permanence de ±0,20 pt.
                # Le seul appel qui vient APRÈS est `update_potential_growth`
                # (ligne suivante), qui clôt l'année : il mute le tendanciel
                # pour l'année d'après, et ne doit donc pas être lu ici.
                output_gap = self.prochain_output_gap(
                    output_gap, growth, self.croissance_potentielle_totale())
                _log_debug(self.debug_logs, f"Y{year_idx}: Nouveau output gap = {output_gap:.3f}")

                # Mise à jour croissance potentielle
                self.update_potential_growth(growth, year_idx)

                # Multiplicateur pour logs (colonne `Multiplicateur`) : effet
                # d'impact des impulsions de l'année par unité d'impulsion
                # BRUTE, signé (> 0 = soutien), Σ(−k·Δ) / Σ|Δ|. Une année sans
                # impulsion garde la valeur de la dernière année qui en a eu.
                du_jour = [(d, k) for (an, *_), (d, k, _p) in self._fiscal_impulses.items()
                           if an == year_idx]
                if du_jour:
                    multiplier = (sum(-k * d for d, k in du_jour)
                                  / sum(abs(d) for d, _ in du_jour))

                # Stockage pour année suivante
                self.inflation_precedente = inflation
                self.dette_courante = debt
                self.pib_nominal = gdp_nominal
                self.pib_reel_base2025 = gdp_real
                self.output_gap_courant = output_gap  # IMPORTANT

            # Calcul Gini centralisé
            # CORRECTION V4.6 : Application CHAQUE année pour capturer phasing/temporalité
            # Évite double-comptage car impacts sont calculés en DELTA, pas en cumulatif
            # v0.4.0 RÉALISME : la somme brute des sensibilités par mesure sur-réagissait
            # (~×4 vs microsimulations IPP/OFCE) et arrivait quasi en one-time Y1 →
            # LFI/PS saturaient le clip dur 0,25 dès 2027 (même valeur affichée, écart
            # entre programmes écrasé). Trois étages (constantes sourcées, constants.py) :
            # 1) la somme rescalée alimente une CIBLE cumulée (les ratios entre partis
            #    sont préservés — un seul facteur global, pas de re-calage par handler) ;
            # 2) le Gini courant CONVERGE vers la cible (lag du 1er ordre : une réforme
            #    fiscale met des années à se diffuser dans la distribution des revenus) ;
            # 3) les pas NÉGATIFS sont amortis proportionnellement à la distance au
            #    plancher souple (rendements décroissants de la redistribution près des
            #    niveaux Slovaquie/Belgique). Asymétrie voulue : le plafond 0,40 est
            #    loin et non saturé en pratique. Le clip dur reste en filet ultime ;
            #    qu'il ne morde plus jamais est verrouillé par test de propriété.
            if year_idx > 0:  # Pas d'impact pour année base (2025)
                gini_impact = self.calculate_gini_impact(impacts, gdp_nominal)
                # Garde de finitude : un NaN/inf émis par un handler (division
                # numpy par 0.0 → pas d'exception, juste un RuntimeWarning)
                # empoisonnerait gini_cible_cumul pour TOUTES les années
                # restantes puis ressortirait du clip comme une valeur
                # plausible (np.clip(inf)=0.40) — 200 OK, zéro trace.
                if not np.isfinite(gini_impact):
                    raise RuntimeError(
                        f"Y{year_idx}: impact Gini agrégé non fini ({gini_impact!r}) — "
                        f"un handler émet NaN/inf (mesures actives : {sorted(leviers_presents(self.mesures))})"
                    )
                if gini_impact != 0:
                    _log_debug(self.debug_logs, f"Y{year_idx}: Impact Gini brut annuel = {gini_impact:.6f}")
                self.gini_cible_cumul += GINI_IMPACT_SCALE * gini_impact
                gini_cible = self.base_params['gini_base'] + self.gini_cible_cumul
                step = GINI_CONVERGENCE_RATE * (gini_cible - self.gini_courant)
                if step < 0:
                    amortissement = (self.gini_courant - GINI_SOFT_FLOOR) / (
                        self.base_params['gini_base'] - GINI_SOFT_FLOOR
                    )
                    step *= float(np.clip(amortissement, 0.0, 1.0))
                    if amortissement < 1.0:
                        # Sans cette ligne, un pas écrasé par le plancher serait
                        # indistinguable d'une convergence achevée dans les logs.
                        _log_debug(self.debug_logs, f"Y{year_idx}: amortissement plancher = {amortissement:.3f}")
                if step != 0:
                    _log_debug(
                        self.debug_logs,
                        f"Y{year_idx}: Gini cible={gini_cible:.4f} pas={step:+.5f}",
                    )
                self.gini_courant += step
                if not GINI_SOFT_FLOOR <= self.gini_courant <= GINI_HARD_CEILING:
                    self._corrections.setdefault(
                        ('Gini', 'SORTIE'),
                        f"Gini borné à [{GINI_SOFT_FLOOR}, {GINI_HARD_CEILING}] "
                        f"dès {year} (filet ultime du modèle : résultat hors "
                        f"de son domaine de validité)")
                self.gini_courant = np.clip(self.gini_courant, GINI_SOFT_FLOOR, GINI_HARD_CEILING)

            # Indice de pouvoir d'achat RDB-MOTEUR (v0.6.8, engine/rdb.py) : RDB des
            # ménages déflaté par le prix de leur consommation, par unité de
            # consommation, base 100 en 2025 — la définition de l'INSEE. Indice de
            # NIVEAU : l'année t ne lit que les grandeurs de t (PIB nominal,
            # déflateur, euros des mesures par canal ménages). La masse salariale
            # publique de BASE suit le volume tendanciel du statu quo
            # (spending_growth_rates, 0,6 %/an) au prix du déflateur : identique en
            # réel pour tous les scénarios, ni la croissance, ni l'écart de
            # production, ni l'indexation passée n'y touchent (arbitrage 2 : seules
            # les mesures de rémunération la déplacent, par leur canal). Remplace « croissance du PIB + Σ coefficients
            # forfaitaires × 0,5 après 2026 » de la v0.6.7 (formule et tableau
            # avant/après : METHODOLOGIE § Indice de pouvoir d'achat).
            rdb = rdb_annee(
                impacts, gdp_nominal, pib_nominal_2025, self.deflateur_cumule,
                ((1 + self.spending_growth_rates['masse_salariale']) ** year_idx
                 * self.deflateur_cumule),
                year_idx)
            self._rdb_trace[year] = rdb
            # Même garde de finitude que le Gini : un NaN/inf ressortirait de la
            # borne comme une valeur plausible.
            if not np.isfinite(rdb.indice):
                raise RuntimeError(
                    f"Y{year_idx}: indice de pouvoir d'achat non fini ({rdb.indice!r}) — "
                    f"mesures actives : {sorted(leviers_presents(self.mesures))}")
            if year_idx > 0:
                # Borne physique (v0.6.7, PA_VARIATION_ANNUELLE_MAX) sur la
                # variation de l'indice : un RDB rendu négatif ou un prix
                # démultiplié (TVA à 2 000 %) sortent du domaine du modèle. Ne
                # mord sur aucun scénario publié.
                variation_pa, bornee = _borner_variation(
                    rdb.indice / purchasing_power - 1, PA_VARIATION_ANNUELLE_MAX)
                if bornee:
                    self._corrections.setdefault(
                        ('Pouvoir d\'Achat', 'SORTIE'),
                        f"Pouvoir d'achat : variation annuelle bornée à "
                        f"±{PA_VARIATION_ANNUELLE_MAX:.0%} dès {year} "
                        f"(résultat hors du domaine de validité du modèle)")
                purchasing_power *= (1 + variation_pa)
                if rdb.effet_mesures or rdb.coin_indirect:
                    _log_debug(self.debug_logs,
                        f"Y{year}: PA = {purchasing_power:.1f} (RDB {rdb.rdb:.1f} Md€ dont "
                        f"mesures {rdb.effet_mesures:+.1f}, prix ×{rdb.prix:.4f})")

            # Compétitivité des entreprises - Mise à jour MULTIPLICATIVE (comme PA)
            # Sources : OCDE 2024, Banque de France, DG Trésor
            # IMPORTANT : Appliqué CHAQUE ANNÉE pour cumuler impacts RÉCURRENT (éducation, transition)
            # Les impacts ONE-TIME sont automatiquement filtrés par _is_first_year_change()
            competitivite_delta = self.calculate_competitivite(impacts, gdp_nominal, year)
            # Même borne physique que le PA (v0.6.7) : l'indice était sans
            # aucune borne, et une variation ≤ −100 points inversait son signe.
            competitivite_delta, bornee = _borner_variation(
                competitivite_delta, COMPETITIVITE_VARIATION_ANNUELLE_MAX)
            if bornee:
                self._corrections.setdefault(
                    ('Competitivite', 'SORTIE'),
                    f"Compétitivité : variation annuelle bornée à "
                    f"±{COMPETITIVITE_VARIATION_ANNUELLE_MAX:.0f} % dès {year} "
                    f"(résultat hors du domaine de validité du modèle)")
            if abs(competitivite_delta) > 0.0001:
                # Conversion points d'indice → pourcentage : 0.795 pts = 0.795% = 0.00795
                competitivite_index *= (1 + competitivite_delta / 100)  # Application multiplicative

                if abs(competitivite_delta) > 0.001:
                    _log_debug(self.debug_logs,
                        f"Y{year}: Compétitivité = {competitivite_index:.2f} (delta {competitivite_delta:+.3f} pts = {competitivite_delta/100:+.2%})")

            # Validation
            year_data = {
                'Recettes/PIB %': revenues / gdp_nominal * 100,
                # Aligné sur la métrique AFFICHÉE (avec intérêts) — revue
                # 2026-06-10 : le validateur bornait un ratio primaire que
                # personne ne voit (écart 2-3 pts vs colonne publiée).
                'Dépenses/PIB %': (spending + interests) / gdp_nominal * 100,
                'Dette/PIB %': debt / gdp_nominal * 100,
                'Gini': self.gini_courant,
                'Inflation %': inflation * 100,
                'Output_Gap %': output_gap * 100,
                'Taux_Intérêt %': interest_rate * 100
            }

            violations = self.validator.validate_year(year_data)
            if violations:
                validation_log.append(f"An {year}: {', '.join(violations)}")

            # Résultats
            results_list.append({
                'Année': year,
                'PIB': round(gdp_nominal, 1),
                'Croissance %': round(growth * 100, 2),
                'Inflation %': round(inflation * 100, 2),
                'Déficit': round(deficit, 1),
                'Déficit/PIB %': round(deficit / gdp_nominal * 100, 2),
                'Dette': round(debt, 1),
                'Dette/PIB %': round(debt / gdp_nominal * 100, 2),
                'Chômage %': round(unemployment * 100, 2),
                'Gini': round(self.gini_courant, 3),
                'Pouvoir d\'Achat': round(purchasing_power, 1),
                'Competitivite': round(competitivite_index, 2),
                'Recettes/PIB %': round(revenues / gdp_nominal * 100, 1),
                'Dépenses/PIB %': round((spending + interests) / gdp_nominal * 100, 1),  # AVEC intérêts
            })

            results_detailed.append({
                'Année': year,
                'Recettes_Totales': round(revenues, 1),
                'Dépenses_Totales': round(spending, 1),
                'Intérêts_Dette': round(interests, 1),
                'Dépenses_Totales_Avec_Intérêts': round(spending + interests, 1),
                'Taux_Intérêt %': round(interest_rate * 100, 2),
                'Effort_Budgétaire %': round(budget_effort * 100, 2) if year_idx > 0 else 0,
                'Multiplicateur': round(multiplier, 2),
                'PIB_Réel_Base2025': round(gdp_real, 1),
                'Déflateur': round(self.deflateur_cumule, 3),
                'Output_Gap %': round(output_gap * 100, 2),
                'Croissance_Potentielle %': round(self.base_params['croissance_potentielle'] * 100, 2),
                'Bonus_Potentiel_Supply %': round(self._potential_growth_bonus * 100, 3),
                # Canal emploi seniors (v0.6.1) : INCRÉMENT de l'année, exposé
                # séparément de l'offre STRUCTURELLE ci-dessus — sans colonne
                # dédiée, un lecteur ne peut pas décomposer la croissance
                # potentielle totale entre offre de travail et capital public.
                'Bonus_Offre_Travail %': round(self._labour_supply_bonus * 100, 3),
                # Somme réellement consommée par le moteur (tendanciel + offre
                # structurelle + offre de travail) — v0.6.1 : passe par le
                # lecteur unique pour que la colonne publiée ne puisse plus
                # diverger de la croissance simulée.
                'Croissance_Potentielle_Totale %': round(self.croissance_potentielle_totale() * 100, 2),
                # Indice de pouvoir d'achat RDB-moteur (v0.6.8) : RDB nominal des
                # ménages, dont effet direct des mesures, et prix de la
                # consommation (2025 = 1). Décomposition complète : engine/rdb.py.
                'RDB_Ménages_Md€': round(rdb.rdb, 1),
                'RDB_Effet_Mesures_Md€': round(rdb.effet_mesures, 2),
                'Prix_Consommation': round(rdb.prix, 4),
            })

        # Validation finale
        results_df = pd.DataFrame(results_list)
        trajectory_report = self.validator.validate_trajectory(results_df)

        if validation_log:
            _log_debug(self.debug_logs, "\n" + "="*50)
            _log_debug(self.debug_logs, "ALERTES VALIDATION")
            for alert in validation_log:
                _log_debug(self.debug_logs, f"⚠ {alert}")

        if trajectory_report['warnings']:
            _log_debug(self.debug_logs, "\n" + "="*50)
            _log_debug(self.debug_logs, "AVERTISSEMENTS")
            for warning in trajectory_report['warnings']:
                _log_debug(self.debug_logs, f"⚠ {warning}")

        if trajectory_report['critical']:
            _log_debug(self.debug_logs, "\n" + "="*50)
            _log_debug(self.debug_logs, "ALERTES CRITIQUES")
            for critical in trajectory_report['critical']:
                _log_debug(self.debug_logs, f"🚨 {critical}")

        if trajectory_report['tests']:
            _log_debug(self.debug_logs, "\n" + "="*50)
            _log_debug(self.debug_logs, "TESTS ÉCONOMIQUES")
            for test in trajectory_report['tests']:
                _log_debug(self.debug_logs, f"📊 {test}")

        # Rapport d'entrée/sortie (v0.6.7). `valid` = le résultat se lit TEL
        # QUEL : aucune entrée corrigée (clamp, retrait d'un non-fini), aucun
        # levier en échec, aucune borne de sortie atteinte. Avant : `valid`
        # valait « dette finale < 160 % » (jugement macro, déjà porté par
        # `critical`) — le statu quo sortait `false`, une TVA à 2 000 % `true`.
        # Les avis (bloc vide, plafond 5 % PIB du modèle) informent sans
        # invalider : l'entrée a été lue telle quelle.
        corrections = list(self._corrections.values())
        trajectory_report['valid'] = not corrections
        trajectory_report['warnings'] = (
            [f"Entrée ou sortie corrigée — {texte}" for texte in corrections]
            + [f"Avis — {texte}" for texte in self._avis.values()]
            + trajectory_report['warnings']
        )

        # NOUVEAU: Ajouter les impacts détaillés au rapport
        trajectory_report['measure_impacts_by_year'] = measure_impacts_by_year

        return results_df, pd.DataFrame(results_detailed), trajectory_report
