import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from asteval import Interpreter

from ._logging import _log_debug
from .constants import (
    PIB_BASE_2025_MD_EUR, DETTE_RATIO_2025, RECETTES_BASE_MD_EUR,
    DEPENSES_BASE_MD_EUR, CHOMAGE_BASE, CHOMAGE_NAIRU, GINI_BASE,
    INFLATION_BASE, CROISSANCE_POTENTIELLE, CROISSANCE_2025,
    TAUX_INTERET_BASE,
)
from .handlers.additionnels import AdditionnelsMixin
from .handlers.competitivite import CompetitiviteMixin
from .handlers.depenses import DepensesMixin
from .handlers.efficience import EfficienceMixin
from .handlers.fiscalite_menages import FiscaliteMenagesMixin
from .handlers.investissements import InvestissementsMixin
from .handlers.montaigne import MontaigneMixin
from .handlers._types import Handler

from .engine.inflation import InflationMixin
from .engine.unemployment import UnemploymentMixin
from .engine.revenues import RevenuesMixin
from .engine.debt import DebtMixin
from .engine.expenditures import ExpendituresMixin
from .engine.micro_impacts import MicroImpactsMixin
from .engine.growth import GrowthMixin
from .engine.orchestrator import OrchestratorMixin

logger = logging.getLogger(__name__)


# === CONFIGURATION DE PERFORMANCE ===
ENABLE_VALIDATION_LOGS = True  # Garder les logs de validation

# === CLASSES DE VALIDATION ÉCONOMIQUE AMÉLIORÉES ===
@dataclass
class EconomicConstraints:
    """Contraintes économiques basées sur normes internationales"""
    rec_pib_min: float = 0.45
    rec_pib_max: float = 0.65
    dep_pib_min: float = 0.48
    dep_pib_max: float = 0.65
    dette_pib_min: float = 0.60
    dette_pib_max: float = 2.50
    croissance_min: float = -0.035
    croissance_max: float = 0.025
    deficit_pib_max: float = 0.10
    chomage_min: float = 0.04
    chomage_max: float = 0.12
    gini_min: float = 0.25
    gini_max: float = 0.40
    inflation_min: float = -0.005
    inflation_max: float = 0.042
    output_gap_max: float = 0.03
    taux_interet_max: float = 0.050  # Cohérent avec plafond BCE TPI

class EconomicValidator:
    """Validateur de cohérence économique avec tests améliorés"""

    def __init__(self):
        self.constraints = EconomicConstraints()
        self.test_results = []

    def validate_year(self, year_data: dict) -> List[str]:
        """Valide les données d'une année - AMÉLIORÉ"""
        violations = []

        rec_pib = year_data.get('Recettes/PIB %', 0) / 100
        if not self.constraints.rec_pib_min <= rec_pib <= self.constraints.rec_pib_max:
            violations.append(f"Recettes/PIB {rec_pib:.1%} hors bornes [{self.constraints.rec_pib_min:.0%}-{self.constraints.rec_pib_max:.0%}]")

        dep_pib = year_data.get('Dépenses/PIB %', 0) / 100
        if dep_pib < self.constraints.dep_pib_min:
            violations.append(f"ALERTE: Dépenses/PIB {dep_pib:.1%} < minimum services essentiels {self.constraints.dep_pib_min:.0%}")
        elif dep_pib > self.constraints.dep_pib_max:
            violations.append(f"Dépenses/PIB {dep_pib:.1%} > seuil soutenable {self.constraints.dep_pib_max:.0%}")

        dette_pib = year_data.get('Dette/PIB %', 0) / 100
        # AJOUTER alertes progressives
        if dette_pib > 1.60:
            violations.append(f"CRITIQUE: Dette/PIB {dette_pib:.1%} > seuil critique 160%")
        elif dette_pib > 1.40:
            violations.append(f"ALERTE: Dette/PIB {dette_pib:.1%} > soutenabilité 140%")

        # NOUVEAU : Test output gap
        output_gap = year_data.get('Output_Gap %', 0) / 100
        if abs(output_gap) > self.constraints.output_gap_max:
            violations.append(f"Output gap {output_gap:.1%} excessif")

        # NOUVEAU : Test taux intérêt
        taux = year_data.get('Taux_Intérêt %', 0) / 100
        if taux > self.constraints.taux_interet_max:
            violations.append(f"CRITIQUE: Taux {taux:.1%} > plafond BCE {self.constraints.taux_interet_max:.1%}")

        gini = year_data.get('Gini', 0)
        if not self.constraints.gini_min <= gini <= self.constraints.gini_max:
            violations.append(f"Gini {gini:.2f} hors bornes")

        inflation = year_data.get('Inflation %', 0) / 100
        if not self.constraints.inflation_min <= inflation <= self.constraints.inflation_max:
            violations.append(f"Inflation {inflation:.1%} hors bornes")

        return violations

    def validate_trajectory(self, results: pd.DataFrame) -> Dict:
        """Valide la trajectoire complète avec tests économiques"""
        report = {'valid': True, 'warnings': [], 'critical': [], 'tests': []}

        # Tests existants...
        croissance_moy = results['Croissance %'].iloc[1:].mean()
        if croissance_moy < 0.3:
            report['warnings'].append(f"Croissance moyenne très faible: {croissance_moy:.1f}%")
        elif croissance_moy > 2.2:
            report['warnings'].append(f"Croissance moyenne irréaliste: {croissance_moy:.1f}%")
        report['tests'].append(f"Croissance moyenne: {croissance_moy:.1f}%")

        dette_2035 = results.iloc[-1]['Dette/PIB %']
        dette_2025 = results.iloc[0]['Dette/PIB %']
        delta_dette = dette_2035 - dette_2025

        if dette_2035 > 160:
            report['critical'].append(f"CRITIQUE: Dette 2035 insoutenable: {dette_2035:.1f}%")
            report['valid'] = False
        elif delta_dette > 30:
            report['warnings'].append(f"Forte hausse dette: +{delta_dette:.0f} pts")
        report['tests'].append(f"Dette: {dette_2025:.1f}% → {dette_2035:.1f}% (Δ{delta_dette:+.1f}pts)")
        # Analyse solde budgétaire
        # Solde budgétaire total (intérêts inclus dans Dépenses/PIB)
        total_balance = (results['Recettes/PIB %'] - results['Dépenses/PIB %'])
        balance_final = total_balance.iloc[-1]
        surplus_years = (total_balance > 0).sum()

        report['tests'].append(f"Solde budgétaire 2035: {balance_final:.1f}% PIB")
        report['tests'].append(f"Années excédent budgétaire: {surplus_years}/10")

        if surplus_years < 3:
            report['warnings'].append(
                f"Solde budgétaire déficitaire {10-surplus_years}/10 ans - "
                f"stabilisation dette compromise"
            )

        # Règle de Domar simplifiée
        final_debt = results.iloc[-1]['Dette/PIB %'] / 100
        if final_debt > 1.2:
            report['warnings'].append(
                f"Dette {final_debt*100:.0f}% nécessite excédent primaire >1% pour stabiliser"
            )
        # Test Okun
        okun_violations = 0
        for i in range(1, len(results)):
            delta_growth = results.iloc[i]['Croissance %'] - results.iloc[i-1]['Croissance %']
            delta_unemployment = results.iloc[i]['Chômage %'] - results.iloc[i-1]['Chômage %']
            okun_expected = -0.35 * delta_growth / 100
            if abs((delta_unemployment/100) - okun_expected) > 0.02:
                okun_violations += 1

        if okun_violations > 3:
            report['warnings'].append(f"Incohérences Okun: {okun_violations} années")
        report['tests'].append(f"Test Okun: {10-okun_violations}/10 années cohérentes")

        deficit_col = 'Déficit/PIB %' if 'Déficit/PIB %' in results.columns else None
        if deficit_col:
            deficit_final = results.iloc[-1][deficit_col]
            if deficit_final < -5:
                report['warnings'].append(f"Déficit 2035 élevé: {deficit_final:.1f}% PIB")
            report['tests'].append(f"Déficit final: {deficit_final:.1f}% PIB")
        else:
            report['warnings'].append("Colonne Déficit/PIB % manquante")

        return report

# === MATRICE DES MULTIPLICATEURS FISCAUX AJUSTÉE ===
class FiscalMultipliers:
    """Gestionnaire des multiplicateurs - ajustements suite retour Grok"""

    def __init__(self):
        # Cache pour les multiplicateurs (évite recalcul)
        self._multiplier_cache = {}

        # Multiplicateurs de base calibrés sur littérature :
        # - IMF Fiscal Monitor 2014 : investment 0.9-1.5, transfers 0.3-0.6, tax 0.5-1.0
        # - Alesina & Ardagna 2010 : spending cuts 0.5-0.7
        # - Romer & Romer 2010 : tax multiplier 0.5-1.0 (milieu de fourchette)
        self.base_multipliers = {
            'consolidation': {
                'tax_based': -0.50,     # Hausse impôts anticipée (Blanchard & Leigh 2013: 0.3-0.5)
                'spending_based': -0.40, # Coupes dépenses anticipées (Alesina: 0.3-0.5 pour graduel)
            },
            'expansion': {
                'tax_cuts': 0.35,        # Baisses impôts (IMF: 0.1-0.5)
                'transferts': 0.50,      # Transferts sociaux (IMF: 0.3-0.6)
                'investissement': 1.2,   # Investissement public (IMF: 0.9-1.5, OFCE: 1.0-1.3)
            }
        }

        self.adjustments = {
            'recession': 1.15,
            'expansion': 0.85,
            'high_debt': 0.95,
            'confidence': 1.10,
        }

    def get_multiplier(self, effort_type: str, composition: Dict,
                       economic_state: Dict, year: int, measure_id: str = None) -> float:
        """Calcule le multiplicateur ajusté selon le contexte"""

        # Cache: créer une clé unique pour les paramètres
        cache_key = (
            effort_type,
            tuple(sorted(composition.items())),
            round(economic_state.get('output_gap', 0), 3),
            round(economic_state.get('unemployment_gap', 0), 3),
            round(economic_state.get('debt_ratio', 0), 2),
            round(economic_state.get('interest_rate', 0), 3),
            year,
            measure_id
        )

        if cache_key in self._multiplier_cache:
            return self._multiplier_cache[cache_key]

        # TRAITEMENTS SPÉCIAUX par measure_id
        # Le SMIC a un multiplicateur quasi-nul : la hausse du coût du travail
        # (destruction emplois non qualifiés, Kramarz & Philippon 2001) compense
        # le boost de consommation. Effet net sur la croissance ~0.
        # Multiplicateur 0.15 (bien en dessous des transferts standards 0.50).
        if measure_id == 'smic':
            mult_base = 0.15
            multiplier = mult_base
            if economic_state.get('output_gap', 0) < -0.02 or economic_state.get('unemployment_gap', 0) > 0.02:
                multiplier *= self.adjustments['recession']
            elif economic_state.get('output_gap', 0) > 0.02 and economic_state.get('unemployment_gap', 0) < -0.01:
                multiplier *= self.adjustments['expansion']
            if economic_state.get('debt_ratio', 0) > 1.10:
                multiplier *= self.adjustments['high_debt']
            self._multiplier_cache[cache_key] = multiplier
            return multiplier

        # Fraude fiscale (enforcement, pas nouvelle taxe)
        if measure_id == 'fraude_fiscale':
            # La fraude fiscale n'est ni une hausse fiscale ni une baisse de dépenses
            # C'est une meilleure application de la loi existante
            # Multiplicateur modéré -0.40 (entre -0.70 et -0.50)
            mult_base = -0.40
            multiplier = mult_base

            # Ajustements contextuels conservés
            if economic_state.get('output_gap', 0) < -0.02 or economic_state.get('unemployment_gap', 0) > 0.02:
                multiplier *= self.adjustments['recession']
            elif economic_state.get('output_gap', 0) > 0.02 and economic_state.get('unemployment_gap', 0) < -0.01:
                multiplier *= self.adjustments['expansion']

            if economic_state.get('debt_ratio', 0) > 1.10:
                multiplier *= self.adjustments['high_debt']

            # Stocker dans le cache avant de retourner
            self._multiplier_cache[cache_key] = multiplier
            return multiplier

        # Sélection du multiplicateur de base — blend pondéré par composition.
        # Chaque canal (taxe, dépenses, investissement) contribue proportionnellement
        # à son poids dans la mesure. Évite les seuils binaires qui traitent le SMIC
        # (transfert, mult 0.5) comme de l'investissement (mult 1.0).
        if effort_type == 'consolidation':
            part_rev = composition.get('recettes', 0)
            part_dep = composition.get('depenses', 0)
            total = part_rev + part_dep
            if total > 0:
                mult_base = (
                    (part_rev / total) * self.base_multipliers['consolidation']['tax_based'] +
                    (part_dep / total) * self.base_multipliers['consolidation']['spending_based']
                )
            else:
                mult_base = self.base_multipliers['consolidation']['spending_based']
        else:
            part_inv = composition.get('investissement', 0)
            part_rev = composition.get('recettes', 0)
            part_dep = composition.get('depenses', 0)
            part_transfers = max(0, part_dep - part_inv)
            total = part_inv + part_transfers + part_rev
            if total > 0:
                mult_base = (
                    (part_inv / total) * self.base_multipliers['expansion']['investissement'] +
                    (part_transfers / total) * self.base_multipliers['expansion']['transferts'] +
                    (part_rev / total) * self.base_multipliers['expansion']['tax_cuts']
                )
            else:
                mult_base = self.base_multipliers['expansion']['transferts']

        multiplier = mult_base

        # Ajustement conjoncturel
        if economic_state.get('output_gap', 0) < -0.02 or economic_state.get('unemployment_gap', 0) > 0.02:
            multiplier *= self.adjustments['recession']
        elif economic_state.get('output_gap', 0) > 0.02 and economic_state.get('unemployment_gap', 0) < -0.01:
            multiplier *= self.adjustments['expansion']

        # Effet Ricardo-Barro
        if economic_state.get('debt_ratio', 0) > 1.10:
            multiplier *= self.adjustments['high_debt']

        # Effet confiance
        if effort_type == 'consolidation' and composition.get('depenses', 0) > 0.5 and year > 1:
            if multiplier < 0:
                multiplier /= self.adjustments['confidence']

        # Effet ZLB
        if economic_state.get('interest_rate', 0.023) < 0.02 and economic_state.get('output_gap', 0) < -0.02:
            multiplier *= 1.3

        # Stocker dans le cache avant de retourner
        self._multiplier_cache[cache_key] = multiplier
        return multiplier

# === MOTEUR ÉCONOMIQUE PRINCIPAL V4.5 AJUSTÉ ===
class BudgetSimulatorV45(AdditionnelsMixin, MontaigneMixin, InvestissementsMixin, FiscaliteMenagesMixin, CompetitiviteMixin, DepensesMixin, EfficienceMixin,
                         InflationMixin, UnemploymentMixin, RevenuesMixin, DebtMixin,
                         ExpendituresMixin, MicroImpactsMixin, GrowthMixin,
                         OrchestratorMixin):
    """Version 4.5 avec ajustements suite retour Grok.

    Handlers de mesures budgétaires regroupés par thématique dans
    ``budget_simulator/handlers/`` et moteur macroéconomique regroupé par
    bloc dans ``budget_simulator/engine/``, tous deux composés ici via
    mixins (voir la liste d'héritage ci-dessus). Voir
    ``docs/REFACTOR_SPLIT_PLAN.md`` pour la liste autoritative des sections
    / blocs et l'historique des migrations.

    Convention d'ordre des mixins : par date d'extraction (le plus ancien
    d'abord), pas alphabétique ni numéro de section ; les mixins
    ``handlers/`` (Phase 1) précèdent les mixins ``engine/`` (Phase
    « moteur macro »). Aucune méthode n'est dupliquée entre mixins, donc
    l'ordre MRO est neutre sur le runtime — ce choix est purement éditorial
    pour faciliter le diff blame entre phases.
    """

    # Profils temporels par type de mesure.
    # Calibrés sur IMF (2014/2020), Blanchard & Leigh (2013), Bom & Ligthart (2014).
    # CONTRAINTE : somme <= 2.0 (somme 2.65 = autofinancé = absurde)
    DECAY_PROFILE_TAXES     = (0.90, 0.50, 0.30, 0.15, 0.10, 0.05)  # somme 2.00
    DECAY_PROFILE_TRANSFERS = (0.90, 0.50, 0.20, 0.10, 0.05, 0.02)  # somme 1.77 — front-loaded
    DECAY_PROFILE_INVEST    = (0.45, 0.65, 0.45, 0.25, 0.12, 0.06)  # somme 1.98 — pic Y2
    # Alias d'API PUBLIQUE conservé volontairement : surface stable pour un
    # consommateur externe du moteur open source (≠ code mort interne — plus
    # aucun lecteur runtime depuis le retrait du fallback growth.py, mais
    # verrouillé par test_decay_profiles.py::test_backward_compat_alias).
    # Ne pas retirer sans bump majeur de version (rupture d'API).
    DECAY_PROFILE           = DECAY_PROFILE_TAXES

    # Mesures générant un flux de dépenses productives CHAQUE ANNÉE
    INVESTMENT_FLOW_MEASURES = frozenset([
        'education', 'transition_ecologique', 'recherche_publique',
        'sante', 'fonction_publique_reforme',
    ])

    # Mesures de transfert direct (decay rapide)
    TRANSFER_MEASURES = frozenset([
        'chomage_alloc', 'retraites', 'asu', 'smic',
        'prestations_indexation', 'abattement_retraites',
    ])

    @staticmethod
    def _get_decay_profile(measure_id):
        """Retourne le profil de décroissance adapté au type de mesure."""
        if measure_id in BudgetSimulatorV45.INVESTMENT_FLOW_MEASURES:
            return BudgetSimulatorV45.DECAY_PROFILE_INVEST
        if measure_id in BudgetSimulatorV45.TRANSFER_MEASURES:
            return BudgetSimulatorV45.DECAY_PROFILE_TRANSFERS
        return BudgetSimulatorV45.DECAY_PROFILE_TAXES

    def __init__(self, periods: int = 10, mesures: Dict = None):

        np.random.seed(42)
        # Paramètres de base INSEE/Eurostat 2025 (from constants.py)
        self.base_params = {
            'pib_base': PIB_BASE_2025_MD_EUR,
            'dette_ratio': DETTE_RATIO_2025,
            'recettes_base': RECETTES_BASE_MD_EUR,
            'depenses_base': DEPENSES_BASE_MD_EUR,
            'chomage_base': CHOMAGE_BASE,
            'chomage_nairu': CHOMAGE_NAIRU,
            'gini_base': GINI_BASE,
            'inflation_base': INFLATION_BASE,
            'croissance_potentielle': CROISSANCE_POTENTIELLE,
            'croissance_2025': CROISSANCE_2025,
            'taux_interet_base': TAUX_INTERET_BASE,
            # amorcage_depenses_y1 / erosion_recettes : RETIRÉS (refonte 2026-06).
            # L'amorçage Y1 disparaît avec la bridging year (récurrence unique
            # dès Y1) ; l'érosion forfaitaire disparaît avec l'élasticité
            # unitaire (cf. tombstones dans constants.py).
        }

        self.economic_coeffs = {
            'okun': -0.35,
            'debt_drag': -0.005,  # Compromis entre -0.008 (Reinhart-Rogoff) et -0.003 (Herndon et al. 2014)
            'inflation_inertia': 0.50,
            # FIX: ancien 0.40 (positif) signifiait "chômage élevé → plus de croissance"
            # ce qui est économiquement faux. Quand le SMIC augmente le chômage,
            # l'ancien code récompensait ce chômage par un boost de croissance.
            # Le canal chômage→croissance est DÉJÀ capturé par l'output_gap
            # (via Okun : croissance → chômage → output_gap → croissance future).
            # Mettre à 0 élimine le double-comptage sans affecter le baseline
            # (chômage France ~7.6% ≈ NAIRU 7.5%, gap quasi-nul).
            'chomage_gap_weight': 0.0,
        }

        self.demography = {
            'population': 68.6,
            'taux_natalite': 0.010,
            'taux_mortalite': 0.009,
            'solde_migratoire': 0.002,
            'taux_vieillissement': 0.003
        }

        self.spending_categories_base = {
            # PRESTATIONS SOCIALES
            'retraites': 380,              # Pensions (fusionné)
            'sante': 250,                  # Remboursements + ALD (fusionné)
            'chomage': 40,                 # Allocations chômage
            'dependance': 35,              # APA + AAH (fusionné)
            'minima_sociaux': 90,          # RSA + Prime activité + APL + Allocations famille (avant ASU)

            # MASSES SALARIALES
            'masse_salariale': 490,        # TOUTES les masses salariales regroupées

            # FONCTIONNEMENT
            'education_fonct': 25,         # Hors salaires enseignants
            'defense_equipement': 25,      # Armement
            'collectivites': 120,          # Dotations
            'investissements': 60,         # Infrastructure + recherche

            # SUBVENTIONS
            'aides_entreprises': 35,       # CICE, CIR
            'transition_eco': 15,          # MaPrimeRénov

            # AUTRES
            'autres': 84.3                 # Résiduelle ré-ancrée INSEE 2025 : primaire 1649,3 (=1714−64,7) − 1565 catégories identifiées = 84,3 EXACT (refonte 2026-06 : Σ catégories == primaire officiel, testé par test_baseline_properties::test_d)
        }

        # Facteurs de croissance réelle cumulés par catégorie. Depuis la refonte
        # « assemblage temporel » (2026-06), ils ne portent PLUS le niveau des
        # dépenses (porté par le chaînage depenses_primaires_precedentes) : ils
        # servent de clé de répartition (poids dans g_vol) et de base dynamique
        # pour le rabot Montaigne (consommateur cross-mixin).
        self._spending_factors = {cat: 1.0 for cat in self.spending_categories_base}

        # Niveau nominal ORGANIQUE (avant mesures, hors intérêts) de l'année
        # précédente — état chaîné de la récurrence unique des dépenses
        # (engine/expenditures.py). Init = Σ catégories = primaire INSEE 1649,3.
        self.depenses_primaires_precedentes = sum(self.spending_categories_base.values())

        # Impulsion budgétaire de l'année précédente, consommée par la macro de
        # l'année courante (lag standard d'un an — refonte 2026-06, étape 1 du
        # bloc REFONTE de simulate()).
        self._budget_effort_prev = 0.0
        self._parts_prev = {'depenses': 0.0, 'investissement': 0.0}

        # Sauvegarde de la baseline initiale pour reset entre simulations.
        # Les réformes structurelles ajustent spending_categories_base pour que
        # les années suivantes partent d'une base cohérente avec les mesures.
        self._spending_categories_base_initial = dict(self.spending_categories_base)

        # Taux de croissance RÉELS par catégorie — calibrés sur littérature officielle :
        # Cour des comptes (fév 2026), COR (juin 2025), OFCE, LPM 2024-2030, ONDAM
        # La croissance réelle pondérée cible : +1.0 à +1.3%/an (observé +1.3% en 2025)
        self.spending_growth_rates = {
            'retraites': 0.012,            # COR 2025 : 13.9→14.0% PIB, indexation + vieillissement
            'sante': 0.020,                # ONDAM tendanciel haut, réel ~+2% (ex-0.018, re-pente tendanciel)
            'chomage': -0.003,             # Stable, réforme assurance chômage compense
            'dependance': 0.025,           # Baby-boomers 85+ d'ici 2030, plan autonomie
            'minima_sociaux': 0.007,       # Indexation inflation pleine + montée prime activité (ex-0.005)
            'masse_salariale': 0.006,      # GVT + point d'indice (réalisé > +0,3% ; ex-0.003)
            'education_fonct': 0.005,      # Rénovation, numérique (ex-0.003)
            'defense_equipement': 0.030,   # LPM 2024-2030 moyenne lissée (~+3%/an réel)
            'collectivites': 0.008,        # Cour des comptes : dépense locale dynamique (ex-0.005)
            'investissements': 0.010,      # France 2030, rythme stabilisé
            'aides_entreprises': 0.000,    # CIR/CICE stables, pas de baisse programmée
            'transition_eco': 0.025,       # MaPrimeRénov, croissance modérée post-montée en charge
            'autres': 0.005                # Résiduelle alignée tendanciel (ex-0.002)
        }

        self.public_service = {
            'effectifs': 5500000,
            'departs_annuels': 275000,
            'cout_moyen': 54545
        }

        self.periods = periods
        self.annee_base = 2025
        self.mesures = mesures or {}
        self.debug_logs = []
        self._last_impacts = {}  # Initialisation par défaut pour éviter AttributeError

        self.measure_handlers: Dict[str, Handler] = {
            # EFFICIENCE RECETTES & DÉPENSES
            'fraude_fiscale': self._apply_fraude_fiscale,
            'fraude_sociale': self._apply_fraude_sociale,
            'optimisation_dette': self._apply_optimisation_dette,
            # COMPÉTITIVITÉ DES ENTREPRISES
            'niches_fiscales_tge': self._apply_niches_fiscales_tge,
            'niches_sociales_tge': self._apply_niches_sociales_tge,
            'subventions_tge': self._apply_subventions_tge,
            'cotisations_patronales': self._apply_cotisations_patronales,
            'impots_production': self._apply_impots_production,
            'is_exceptionnel_tge': self._apply_is_exceptionnel_tge,
            # FONCTION PUBLIQUE
            'fonction_publique_reforme': self._apply_fonction_publique_reforme,
            'fonction_publique': self._apply_fonction_publique,
            # FISCALITÉ CLASSIQUE
            'impot_societes': self._apply_impot_societes,
            'tva_rate': self._apply_tva_rate,
            'impot_revenu': self._apply_impot_revenu,
            'csg': self._apply_csg,
            'cotisations_salariales': self._apply_cotisations_salariales,
            'elargissement_ir': self._apply_elargissement_ir,
            'fiscalite_patrimoine': self._apply_fiscalite_patrimoine,
            # SOCIAL & RETRAITES
            'retraites': self._apply_retraites,
            'chomage_alloc': self._apply_chomage_alloc,
            'sante': self._apply_sante,
            'asu': self._apply_asu,
            # NOUVELLES MESURES 2026 (PLF/PLFSS)
            'abattement_retraites': self._apply_abattement_retraites,
            'prestations_indexation': self._apply_prestations_indexation,
            # INVESTISSEMENTS STRATÉGIQUES (Compétitivité long terme - IMD/OCDE)
            'transition_ecologique': self._apply_transition_ecologique,
            'education': self._apply_education,
            'recherche_publique': self._apply_recherche_publique,
            # NOUVELLES MESURES PRÉSIDENTIELLE 2027
            'smic': self._apply_smic,
            'isf_climatique': self._apply_isf_climatique,
            'tva_energie': self._apply_tva_energie,
            'taxe_superprofits': self._apply_taxe_superprofits,
            'exonerations_salaires': self._apply_exonerations_salaires,
            # SCÉNARIOS INSTITUT MONTAIGNE
            'rabot_uniforme': self._apply_rabot_uniforme,
        }
        self.validator = EconomicValidator()
        self.multipliers = FiscalMultipliers()
        self.aeval = Interpreter()

        self.dette_courante = self.base_params['pib_base'] * self.base_params['dette_ratio']
        self.recettes_precedentes = self.base_params['recettes_base']
        self.gini_courant = self.base_params['gini_base']
        self.inflation_precedente = self.base_params['inflation_base']
        # croissance_precedente : RETIRÉ (refonte 2026-06) — état devenu write-only
        # (les flux consomment désormais la croissance contemporaine, la macro
        # l'impulsion t−1 via _budget_effort_prev/_parts_prev).

        self.pib_reel_base2025 = self.base_params['pib_base']
        self.pib_nominal = self.base_params['pib_base']
        self.deflateur_cumule = 1.000

        self.output_gap_courant = -0.015
        self.debt_structure = {
            'taux_moyen': 0.019,
            'taux_marginal': 0.036,
            'maturite_moyenne': 8.0
        }

        # Tracker paramètres mesures (pour impacts Gini one-time)
        self._measure_params_tracker = {}
        self._last_measures_hash = None  # Pour détecter changements de mesures (multiplicateur temporal)
        # Profils temporels des impulsions budgétaires (littérature Mésange/OFCE).
        # Chaque impulsion est stockée l'année où les mesures changent, puis
        # son effet décroît selon un profil empirique sur 5-6 ans.
        self._fiscal_impulses = {}  # {year: (effort, multiplier, decay_profile)}
        self.measure_registry = self._load_measure_config()
        self.debug_logs.append(f"Measure registry: {list(self.measure_registry.keys())}")
        self.mesures = mesures or {}
        self.debug_logs.append(f"Mesures actives: {list(self.mesures.keys())}")

        self._potential_growth_bonus = 0.0   # Bonus potentiel structurel (offre)
        self._supply_years = {}              # {measure_key: années actives}
        self._supply_bonus_by_key = {}       # {measure_key: bonus accumulé} pour dépréciation progressive

        # Valeur user de croissance_potentielle avant mutation par simulate()
        self._pre_simulate_croissance_potentielle = self.base_params['croissance_potentielle']

        self._validate_initial_consistency()
        _log_debug(self.debug_logs, f"FIN __init__: recettes_precedentes = {self.recettes_precedentes:.1f}")

    def _reset_state(self):
        """Réinitialise tous les attributs mutés pendant simulate() à leurs valeurs initiales.

        Sans ce reset, un second appel à simulate() démarre depuis l'état final
        du premier appel (dette accumulée, PIB dévié, output gap décalé, etc.)
        et produit des résultats complètement différents.
        """
        # Restaurer croissance_potentielle à la valeur user (mutée par _update_potential_growth)
        self.base_params['croissance_potentielle'] = self._pre_simulate_croissance_potentielle

        # --- Comptabilité macro ---
        self.dette_courante = self.base_params['pib_base'] * self.base_params['dette_ratio']
        self.pib_nominal = self.base_params['pib_base']
        self.pib_reel_base2025 = self.base_params['pib_base']
        self.output_gap_courant = -0.015
        self.deflateur_cumule = 1.000

        # --- Mémoire inter-années ---
        self.inflation_precedente = self.base_params['inflation_base']
        self.recettes_precedentes = self.base_params['recettes_base']
        self.gini_courant = self.base_params['gini_base']

        # --- Structure de dette ---
        self.debt_structure['taux_moyen'] = self.base_params['taux_interet_base']

        # --- Démographie ---
        self.demography['population'] = 68.6

        # --- Historique et trackers ---
        self._last_impacts = {}
        self._measure_params_tracker = {}
        self._last_measures_hash = None
        self._fiscal_impulses = {}  # Reset profils temporels multiplicateurs
        self._potential_growth_bonus = 0.0
        self._supply_years = {}
        self._supply_bonus_by_key = {}

        # --- Spending baseline et compound itératif ---
        self.spending_categories_base = dict(self._spending_categories_base_initial)
        self._spending_factors = {cat: 1.0 for cat in self.spending_categories_base}
        self.depenses_primaires_precedentes = sum(self.spending_categories_base.values())
        self._budget_effort_prev = 0.0
        self._parts_prev = {'depenses': 0.0, 'investissement': 0.0}

        # --- Attributs créés dynamiquement pendant la simulation ---
        if hasattr(self, '_chomage_params_prev'):
            del self._chomage_params_prev

        # --- Debug logs (repartir propre) ---
        self.debug_logs = []

        # --- Random seed (résultats reproductibles) ---
        np.random.seed(42)

    def _get_active_measures_hash(self) -> str:
        """Hash des mesures actives basé sur self.mesures pour détecter changements"""
        if not self.mesures:
            return "no_measures"

        # Créer snapshot des mesures actuelles
        snapshot = {}
        for measure_id, params in self.mesures.items():
            # Garder seulement les valeurs sérialisables
            snapshot[measure_id] = {
                k: v for k, v in params.items()
                if isinstance(v, (int, float, str, bool))
            }

        # Créer hash MD5
        return hashlib.md5(
            json.dumps(snapshot, sort_keys=True).encode()
        ).hexdigest()

    def _load_measure_config(self):
        """Charge la configuration des mesures depuis JSON.

        Délègue le chargement (et le cache module-level) à config.load_policy_config(),
        qui lève RuntimeError de manière explicite en cas de fichier manquant ou corrompu.
        """
        from .config import load_policy_config
        self.policy_config = load_policy_config()
        self.measure_registry = {m['id']: m for m in self.policy_config.get('mesures', [])}
        _log_debug(self.debug_logs, f"✓ {len(self.measure_registry)} mesures chargées")

        # IMPORTANT: Ajouter automatiquement TOUTES les mesures avec handlers
        # (même si elles existent dans JSON, pour garantir que handlers sont disponibles)
        for measure_id in self.measure_handlers.keys():
            if measure_id not in self.measure_registry:
                self.measure_registry[measure_id] = {
                    'id': measure_id,
                    'type': 'complexe',
                    'cible': 'mixte'
                }
                _log_debug(self.debug_logs, f"✓ Mesure {measure_id} ajoutée au registry (fallback handler)")

        return self.measure_registry

    def _validate_initial_consistency(self):
        """Valide la cohérence des paramètres initiaux"""
        defaults_code = self._get_default_values()
        inconsistencies = []

        for measure_id in self.measure_registry:
            if measure_id not in defaults_code:
                inconsistencies.append(f"Mesure {measure_id} dans JSON mais pas dans defaults")

        if inconsistencies:
            _log_debug(self.debug_logs, "⚠ INCOHÉRENCES CONFIGURATION:")
            for inc in inconsistencies:
                _log_debug(self.debug_logs, f"  - {inc}")
        else:
            self.debug_logs.append("✓ Configuration cohérente")

    def _get_default_values(self) -> Dict:
        # Source unique des défauts : config.load_default_values() (DRY,
        # pas de dict ré-inliné — verrouillé par test_param_contract_cleanup).
        from .config import load_default_values
        return load_default_values()

    def _is_first_year_change(self, measure_id: str, params_dict: Dict) -> bool:
        """
        Helper pour détecter si c'est la première année où une mesure change.
        Utilisé pour impacts Gini one-time (éviter cumul absurde).

        Args:
            measure_id: ID unique de la mesure (ex: 'cotisations_salariales')
            params_dict: Dict des paramètres actuels à tracker

        Returns:
            True si première année de changement, False sinon
        """
        if measure_id not in self._measure_params_tracker:
            # Première fois qu'on voit cette mesure
            self._measure_params_tracker[measure_id] = params_dict.copy()
            return True

        # Comparer avec paramètres précédents
        prev_params = self._measure_params_tracker[measure_id]
        is_changed = (params_dict != prev_params)

        # Mettre à jour tracker
        if is_changed:
            self._measure_params_tracker[measure_id] = params_dict.copy()

        return is_changed

    # =======================================================================
    # SECTION 1 (Efficience et organisation) → budget_simulator/handlers/efficience.py
    # =======================================================================

    # =======================================================================
    # SECTION 2 (Maîtrise des dépenses) → budget_simulator/handlers/depenses.py
    # =======================================================================

    # =======================================================================
    # SECTION 3 (Compétitivité des entreprises) → budget_simulator/handlers/competitivite.py
    # =======================================================================

    # =======================================================================
    # SECTION 4 (Pression fiscale ménages) → budget_simulator/handlers/fiscalite_menages.py
    # =======================================================================

    # =======================================================================
    # SECTION 5 (Investissements) → budget_simulator/handlers/investissements.py
    # =======================================================================

    # =======================================================================
    # SECTION 6 (Présidentielle 2027) → budget_simulator/handlers/additionnels.py
    # =======================================================================

    # =======================================================================
    # SECTION 6bis (Institut Montaigne) → budget_simulator/handlers/montaigne.py
    # =======================================================================

    # =======================================================================
    # SECTION 7 : AUTRES MESURES (Legacy - non dans ExploreCreateSection)
    # =======================================================================

    # =======================================================================
    # SECTION 8 : UTILITAIRES
    # =======================================================================


    def _apply_complex_measure(self, measure: Dict, params: Dict, year: int,
                              gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, Dict]:
        measure_id = measure['id']
        # INVARIANT : l'unique appelant (engine/orchestrator.py::apply_measures)
        # ne route ici que sous garde `if measure_id in self.measure_handlers`.
        # L'indexation directe est donc sûre — un KeyError signalerait une
        # violation de ce contrat (échec bruyant voulu, pas de fallback muet).
        handler = self.measure_handlers[measure_id]
        delta_spending, delta_revenue, impacts = handler(measure, params, year, gdp, inflation, unemployment)
        return delta_spending, delta_revenue, impacts
