"""Section 3 — Compétitivité des entreprises.

Mesures couvertes (7 handlers) :
- ``niches_fiscales_tge`` : niches fiscales grandes entreprises (base 58 Md€).
  Suppression = +recettes, phasing 3 ans (CIR/ZFU/Dutreil). Effet compétitivité
  one-time.
- ``niches_sociales_tge`` : exonérations cotisations patronales TGE (base
  70 Md€). Coeffs chômage/PA neutralisés à 0 (anti double-comptage, captés par
  le multiplicateur fiscal du moteur — cf constants.py).
- ``subventions_tge`` : soutien public innovation/export/R&D (base 35 Md€).
  Suppression = -dépenses, perte compétitivité innovation LT.
- ``cotisations_patronales`` : taux patronal (base 27 %, range 15-35 %).
  Masse salariale ~48 % PIB. Effets emploi/PA/chômage/compétitivité one-time.
- ``impot_societes`` : taux IS (base 25 %) + niches IS. Assiette = bénéfice
  fiscal imposable (~9,1 % PIB), élasticité DG Trésor 2017, ``np.clip`` sur
  les niches. Effet récession via ``self.base_params['pib_base']``.
- ``impots_production`` : impôts de production (base 97 Md€). Handicap
  compétitif France vs Allemagne, effet emploi capté via ``impact_chomage``.
- ``is_exceptionnel_tge`` : taxe exceptionnelle bénéfices TGE (base 8 Md€,
  max 15 Md€). Signal fiscal one-time.

Convention d'application :
- Effets ``competitivite`` / ``pouvoir_achat`` / ``chomage`` / ``emploi`` en
  mode NIVEAU one-time, gated par ``self._is_first_year_change(<clé>, params)``
  (chaque sous-effet a sa propre clé : ``<measure>``, ``<measure>_pa``,
  ``<measure>_emploi``, etc. — re-trigger sur changement effectif du slider).
  Exception : ``impot_societes`` applique ``pouvoir_achat`` de façon
  inconditionnelle (pas de gating one-time) — PRÉSERVÉ tel quel du monolithe.
- Effet ``recettes`` : delta one-shot (montant_base - montant) pour les
  niches/subventions/IS exceptionnel ; proportionnel à la masse salariale
  pour les cotisations patronales.
- Voir docs/METHODOLOGIE.md § "Effets NIVEAU vs FLUX" pour le contrat de gating.

Sources principales :
- Cour des comptes 2023/2024, PLF 2024 (niches fiscales/subventions TGE).
- Commission des comptes 2024, OCDE 2025, Bozio-Wasmer 2024 (niches sociales).
- Kramarz & Philippon 2001, DARES 2024, DG Trésor 2019 (cotisations patronales).
- DGFiP 2024, INSEE comptes SNF 2023, IPP TAXIPP, DG Trésor 2017 (IS).
- INSEE 2024, France Stratégie 2024, CAE 2025 (impôts production).
- FMI 2023, Fipeco (IS exceptionnel TGE).

Couplages avec ``BudgetSimulatorV45`` (instance hôte du mixin) :
- LIT ``self.debug_logs``, la méthode ``self._is_first_year_change`` et
  ``self.base_params['pib_base']`` (état/méthode de la base class,
  simulator.py).
- N'ÉCRIT aucun attribut d'instance : les 7 handlers sont purement
  fonctionnels (entrée params → sortie impacts). Seul effet de bord : append
  dans le sink de logs ``self.debug_logs`` via ``_log_debug`` (fourni par
  l'hôte, sans incidence sur les sorties de simulation). Aucun état propre
  au mixin. Invariant à préserver lors de tout refactor.
"""
from typing import TYPE_CHECKING, Dict, Tuple

import numpy as np

from ..constants import (
    COEFF_CHOMAGE_NICHES_SOCIALES_TGE,
    COEFF_COMPETITIVITE_NICHES_FISCALES_TGE,
    COEFF_COMPETITIVITE_NICHES_SOCIALES_TGE,
    COEFF_COMPETITIVITE_SUBVENTIONS_TGE,
    COEFF_PA_NICHES_SOCIALES_TGE,
    PHASING_NICHES_FISCALES_TGE,
    POLICY_START_YEAR,
)
from .._logging import _log_debug
from ._phasing import _year_phasing
from ._types import ImpactsDict


# Idiome mixin-self typing : NE PAS factoriser dans _types.py (casse la
# liaison self mypy + risque MRO). Réplication volontaire 7×. Cf Lot D.
if TYPE_CHECKING:
    from ._types import _SimulatorState

    _MixinBase = _SimulatorState
else:
    _MixinBase = object


class CompetitiviteMixin(_MixinBase):
    """Handlers Section 3 — Compétitivité des entreprises."""

    def _apply_niches_fiscales_tge(self, measure: Dict, params: Dict, year: int,
                                    gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Niches fiscales TGE (avantages fiscaux grandes entreprises). Actuel 58 Md€ (70% de 83 Md€ total).
        Sources: Cour Comptes 2024, PLF 2024. Voir METHODOLOGIE.md."""
        montant = params.get('montant', 58)
        montant_base = 58

        # Phasing montee en charge : suppression de niches fiscales prend 3 ans en pratique
        # (CIR contractuel 5 ans, ZFU jusqu'en 2030, Pacte Dutreil...). Cour des comptes 2024 :
        # debouclage 30-50% Y1, 70% Y2, 100% Y3+.
        year_idx = max(0, year - POLICY_START_YEAR)
        phasing = _year_phasing(year_idx, PHASING_NICHES_FISCALES_TGE)
        delta_revenue = (montant_base - montant) * phasing  # Suppression = +recettes

        # Impact compétitivité : ONE-TIME basé sur FISCALITÉ (DG Trésor)
        # Logique : Niches fiscales = avantages compétitifs pour TGE (15k entreprises)
        # Suppression = hausse charge fiscale effective → délocalisation + perte attractivité
        # Coefficient : -0.015 par Md€ (recalibré pour refléter impact réel incluant optimisation fiscale)
        # Référence : Impact moindre que impôts production (fiscalité ciblée vs généralisée)
        # Exemple : Suppression 58 Md€ → -58 × 0.015 = -0.87 compétitivité
        params_niches_fisc = {'montant': montant}
        if self._is_first_year_change('niches_fiscales_tge', params_niches_fisc):
            montant_suppression = montant_base - montant  # Montant supprimé en Md€
            impact_competitivite = -montant_suppression * COEFF_COMPETITIVITE_NICHES_FISCALES_TGE
        else:
            impact_competitivite = 0.0

        impacts = {
            'recettes': delta_revenue,
            'pouvoir_achat': 0,  # Neutre (TGE)
            'competitivite': impact_competitivite
        }

        _log_debug(self.debug_logs, f"Y{year}: Niches fiscales TGE - montant={montant:.0f}Md€, suppression={montant_base - montant:.1f}Md€, impact_compet={impact_competitivite:+.3f}")
        return 0, delta_revenue, impacts

    def _apply_niches_sociales_tge(self, measure: Dict, params: Dict, year: int,
                                    gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Niches sociales TGE (exonérations cotisations patronales). Actuel 70 Md€.
        Sources: Commission Comptes 2024, OCDE 2025. Voir METHODOLOGIE.md."""
        montant = params.get('montant', 70)
        montant_base = 70
        delta_revenue_social = (montant_base - montant)  # Suppression = +recettes sociales

        # Impact compétitivité : ONE-TIME basé sur COÛT UNITAIRE TRAVAIL (OCDE)
        # Logique : Niches sociales = exonérations charges patronales pour TGE
        # Suppression = hausse du coût du travail pour ces entreprises
        # Coefficient : -0.020 par Md€ (symétrique inverse cotisations patronales, recalibré)
        # Référence : Même logique que CICE mais en sens inverse
        # Exemple : Suppression 70 Md€ → -70 × 0.020 = -1.40 compétitivité
        params_niches_soc = {'montant': montant}
        if self._is_first_year_change('niches_sociales_tge', params_niches_soc):
            montant_suppression = montant_base - montant  # Montant supprimé en Md€
            impact_competitivite = -montant_suppression * COEFF_COMPETITIVITE_NICHES_SOCIALES_TGE
        else:
            impact_competitivite = 0.0

        # Impact CHÔMAGE et PA : coefficients à 0 (mai 2026, anti double-comptage).
        # Cible Bozio-Wasmer 2024 (~138k emplois pour suppression 60 Md€) déjà atteinte
        # par le multiplicateur fiscal du moteur (cascade recettes → croissance → Okun).
        # Test runtime : suppression 60 Md€ → -140 630 emplois Y10 sans signal direct.
        # Avec ancien coefficient 0.008/Md€, l'effet était amplifié ×9 à ×95.
        # Voir : constants.py L60-67, METHODOLOGIE.md L8, test_calibration_guard.py
        # test_niches_sociales_tge_suppression_60mds_destroys_jobs.
        # Code conservé (résultats = 0) pour réactivation rapide si moteur évolue.
        if self._is_first_year_change('niches_sociales_tge_emploi', params_niches_soc):
            montant_suppression = montant_base - montant
            impact_chomage = montant_suppression * COEFF_CHOMAGE_NICHES_SOCIALES_TGE
        else:
            impact_chomage = 0.0

        if self._is_first_year_change('niches_sociales_tge_pa', params_niches_soc):
            montant_suppression = montant_base - montant
            impact_pa = -montant_suppression * COEFF_PA_NICHES_SOCIALES_TGE
        else:
            impact_pa = 0.0

        impacts = {
            'recettes': delta_revenue_social,
            'pouvoir_achat': impact_pa,
            'competitivite': impact_competitivite,
            'chomage': impact_chomage,
        }

        _log_debug(self.debug_logs, f"Y{year}: Niches sociales TGE - montant={montant:.0f}Md€, suppression={montant_base - montant:.1f}Md€, impact_compet={impact_competitivite:+.3f}, impact_chomage={impact_chomage:+.3f}")
        return 0, delta_revenue_social, impacts

    def _apply_subventions_tge(self, measure: Dict, params: Dict, year: int,
                               gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Subventions TGE (soutien public innovation, export, R&D). Actuel 35 Md€.
        Sources: Cour Comptes 2023, Attac 2023. Voir METHODOLOGIE.md."""
        montant = params.get('montant', 35)
        montant_base = 35
        delta_spending = -(montant_base - montant)  # Suppression = -dépenses (amélioration)

        # Impact compétitivité : ONE-TIME basé sur SOUTIEN INNOVATION (France Stratégie)
        # Logique : Subventions = soutien innovation, export, R&D, transition pour TGE
        # Suppression = retrait aides stratégiques → perte compétitivité internationale
        # Coefficient : -0.008 par Md€ (impact indirect, capacité d'innovation)
        # Référence : Impact moindre que coût direct, mais affecte position concurrentielle LT
        # Exemple : Suppression 35 Md€ → -35 × 0.008 = -0.28 compétitivité
        params_subv = {'montant': montant}
        if self._is_first_year_change('subventions_tge', params_subv):
            montant_suppression = montant_base - montant  # Montant supprimé en Md€
            impact_competitivite = -montant_suppression * COEFF_COMPETITIVITE_SUBVENTIONS_TGE
        else:
            impact_competitivite = 0.0

        impacts = {
            'depenses': delta_spending,
            'gini': 0,  # Quasi neutre
            'pouvoir_achat': 0,
            'competitivite': impact_competitivite
        }

        _log_debug(self.debug_logs, f"Y{year}: Subventions TGE - montant={montant:.0f}Md€, suppression={montant_base - montant:.1f}Md€, impact_compet={impact_competitivite:+.3f}")
        return delta_spending, 0, impacts

    def _apply_cotisations_patronales(self, measure: Dict, params: Dict, year: int,
                                       gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Cotisations patronales (27% actuel, range 15-35%). Masse salariale 48% PIB. -1 pt = +0.08% emploi.
        Sources: OCDE 2025, France Stratégie 2024. Voir METHODOLOGIE.md § Competitivite des Entreprises."""
        taux = params.get('taux', 0.27)
        taux_actuel = 0.27
        delta_taux = taux - taux_actuel

        # Masse salariale privée (~48% PIB)
        masse_salariale = gdp * 0.48
        delta_revenue_social = delta_taux * masse_salariale

        # Impact emploi (exporté) : -1 point cotisations = +0.08% emploi
        # Source : Kramarz & Philippon 2001 (consensus français)
        # Sur 27M emplois privés en France
        impact_emploi_pct = -delta_taux * 0.08

        # Impact compétitivité : ONE-TIME (changement structure coût travail)
        # Règle : Impact basé sur MONTANT en Md€
        # Baisse cotisations = impact DIRECT sur coût travail de TOUTES les entreprises
        # Hausse cotisations = perte de compétitivité (coût travail augmente)
        # Coefficient : 0.020 par Md€ (DG Trésor 2019, transformation CICE, ajusté pour effets indirects)
        # Référence : -50 Md€ CICE → +0.7 compétitivité observée
        # Recalibré pour refléter l'impact réel incluant emploi/investissement
        params_cotis_pat = {'taux': taux}
        if self._is_first_year_change('cotisations_patronales', params_cotis_pat):
            # delta_revenue_social POSITIF si hausse cotisations (recettes ↑)
            # delta_revenue_social NÉGATIF si baisse cotisations (recettes ↓)
            # Impact: Baisse → +compétitivité, Hausse → -compétitivité
            impact_competitivite = -delta_revenue_social * 0.020  # ONE-TIME (baisse 50 Md€ → +1.0)
        else:
            impact_competitivite = 0.0  # Niveau conservé dans indice

        # Gini : PAS D'IMPACT MICRO (cotisations PATRONALES, pas modification directe salaire net)
        # Effet passe par compétitivité → emploi → distribution revenus = MACRO
        # Impact Gini vient UNIQUEMENT de l'effet macro

        # Impact PA (baisse coût travail → hausse emploi → hausse PA) — ONE-TIME
        # Source: DARES 2024 - Baisse 3 pts = +0.24% emploi = +0.15% PA
        if self._is_first_year_change('cotisations_patronales_pa', params_cotis_pat):
            impact_pa = -delta_taux * 0.05  # -3 pts → +0.15%
        else:
            impact_pa = 0.0

        # Impact chômage via coût travail (ONE-TIME)
        # Élasticité emploi/coût travail = 0.4 (Kramarz & Philippon 2001)
        # Baisse 5 pts cotisations → Baisse coût → +emploi → -0.30 pt chômage
        # Hausse 5 pts cotisations → Hausse coût → -emploi → +0.30 pt chômage
        # Formule: +0.06 pt chômage par point de hausse cotisation
        if self._is_first_year_change('cotisations_patronales_emploi', params_cotis_pat):
            # delta_taux POSITIF si hausse (29%-27% = +0.02)
            # delta_taux NÉGATIF si baisse (25%-27% = -0.02)
            # Impact: Hausse → +chômage, Baisse → -chômage
            impact_chomage = delta_taux * 0.06  # Hausse +5 pts → +0.30 pt, Baisse -5 pts → -0.30 pt
        else:
            impact_chomage = 0.0

        # impact_emploi_pct exporte ONE-TIME pour coherence avec pa/chomage/competitivite (sinon
        # double-comptage si frontend somme sur N annees). Effet de NIVEAU conserve via baseline.
        impact_emploi_export = impact_emploi_pct if self._is_first_year_change('cotisations_patronales_emploi_export', params_cotis_pat) else 0.0

        impacts = {
            'recettes': delta_revenue_social,
            'pouvoir_achat': impact_pa,
            'competitivite': impact_competitivite,
            'chomage': impact_chomage,
            'emploi': impact_emploi_export,  # ONE-TIME (Kramarz-Philippon 2001)
        }

        _log_debug(self.debug_logs, f"Y{year}: Cotisations patronales - taux={taux*100:.0f}%, delta_revenue={delta_revenue_social:+.1f}Md€, impact_emploi={impact_emploi_pct:+.2f}%")
        return 0, delta_revenue_social, impacts

    def _apply_impot_societes(self, measure: Dict, params: Dict, year: int, gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        rate = params.get('taux', 0.25)
        loopholes = params.get('niches', 0)
        recession_factor = 0.8 if gdp < self.base_params['pib_base'] * 0.98 else 1.0

        # Niches IS (efficience)
        delta_niches = np.clip(loopholes * recession_factor, -10, 40)

        # Taux IS — assiette = benefice fiscal IMPOSABLE (apres amortissements,
        # charges fi, reports deficits, niches), pas l'EBE.
        # Sources : DGFiP 2024 (IS net 60 Md€/an), INSEE comptes SNF 2023
        # (benefice avant IS ~280 Md€), IPP TAXIPP (assiette imposable nette ~250 Md€).
        # Reverse-check : 0.091 × 2750 × 0.25 ≈ 62 Md€ ✓ DGFiP.
        # Bug historique corrige : 0.25 × gdp (688 Md€) representait l'EBE, pas l'assiette IS.
        # Elasticite long terme DG Tresor 2017 : passage 33→25% = -10 a -12 Md€/an stationnaire.
        delta_taux = 0
        if rate != 0.25:
            elasticity = -1.0 if rate > 0.25 else -0.6
            tax_base = 0.091 * gdp * recession_factor * (1 + elasticity * (rate - 0.25))
            delta_taux = (rate - 0.25) * tax_base

        delta_revenue = delta_niches + delta_taux

        # === IMPACTS MACROÉCONOMIQUES ===
        # Gini : PAS D'IMPACT MICRO (répercussion prix uniforme sur tous déciles)
        # Hausse IS → répercussion prix -0.01% pour TOUS → écart relatif inchangé
        # Impact Gini vient UNIQUEMENT de l'effet macro (recettes → multiplicateur)

        # Pouvoir d'achat : Léger impact si hausse répercutée sur prix
        # Règle : 20% hausse IS = 0.5% hausse prix → -0.0001 PA (INSEE 2024)
        pouvoir_achat = -0.0001 * (rate - 0.25) / 0.05

        # Compétitivité : Impact ONE-TIME basé sur ATTRACTIVITÉ FISCALE (OCDE)
        # Logique : Taux IS affecte délocalisation/attractivité pour toutes entreprises
        # Hausse taux → délocalisation bénéfices (optimisation fiscale, siège social)
        # Baisse taux → attractivité accrue (investissements étrangers)
        # Coefficient : 0.015 par Md€ (OCDE 2024, effet modéré car assiette mobile, unifié avec autres mesures fiscales)
        # Référence : Moyenne UE 21%, France 25% → écart de compétitivité fiscale
        # Exemple : IS 25%→15% (coût 76 Md€) = +76 × 0.015 = +1.14 compétitivité
        params_is_taux = {'rate': rate}  # Seul le TAUX impacte la compétitivité
        if self._is_first_year_change('impot_societes_taux', params_is_taux):
            montant_baisse_mde = -delta_taux  # delta_taux négatif si baisse taux → montant positif
            competitivite = montant_baisse_mde * 0.015  # ONE-TIME basé sur montant
            _log_debug(self.debug_logs, f"Y{year}: IS TAUX CHANGE DETECTED - rate={rate*100:.0f}%, montant={montant_baisse_mde:.1f}Md€, competitivite={competitivite:+.3f}")
        else:
            competitivite = 0.0  # Niveau conservé dans indice
            _log_debug(self.debug_logs, f"Y{year}: IS taux={rate*100:.0f}% (no change detected)")

        impacts = {
            'recettes': delta_revenue,
            'niches_reduction': delta_niches,
            'taux': delta_taux,
            'pouvoir_achat': pouvoir_achat,
            'competitivite': competitivite
        }

        if recession_factor < 1.0:
            _log_debug(self.debug_logs, f"Y{year}: IS en récession, factor={recession_factor:.2f}")
        return 0, delta_revenue, impacts

    def _apply_impots_production(self, measure: Dict, params: Dict, year: int,
                                  gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Impôts production. Actuel 97 Md€ (~3.5% PIB). -10 Md€ = +0.12% PIB. Effet emploi capté via impact_chomage.
        Sources: INSEE 2024, France Stratégie 2024, CAE 2025. Voir METHODOLOGIE.md § Competitivite des Entreprises."""
        montant = params.get('montant', 97)
        montant_base = 97
        delta_revenue = (montant_base - montant)  # Baisse = -recettes fiscales

        # Impact PIB : -10 Md€ = +0.12% PIB
        impact_pib_pct = delta_revenue * 0.012

        # Impact emploi capté via impact_chomage (canal unique pour éviter double comptabilisation)

        # Impact compétitivité : ONE-TIME (changement structure fiscale)
        # Règle : Impact basé sur MONTANT en Md€
        # Impôts production = handicap compétitif France (97 Md€ vs 40 Md€ Allemagne)
        # Coefficient : 0.020 par Md€ (DG Trésor 2021-2023, ajusté pour effets indirects)
        # Référence empirique : -20 Md€ (2021-2023) → +0.3 compétitivité observée
        # Recalibré pour refléter l'impact réel incluant délocalisation/investissement
        params_impots_prod = {'montant': montant}
        if self._is_first_year_change('impots_production', params_impots_prod):
            impact_competitivite = delta_revenue * 0.020  # ONE-TIME changement montant
        else:
            impact_competitivite = 0.0  # Niveau conservé dans indice

        # Gini : PAS D'IMPACT MICRO (impôts entreprises, pas modification directe revenus ménages)
        # Répercussion prix uniforme sur tous déciles → pas redistributif
        # Impact Gini vient UNIQUEMENT de l'effet macro

        # Chômage : Impôts production → Compétitivité → Emploi (ONE-TIME)
        # IMPORTANT : Hausse impôts production AUGMENTE chômage (impact négatif sur emploi)
        # Sources: CAE 2015, France Stratégie 2019
        # Mécanisme: Impôts production ↑ → Compétitivité ↓ → Délocalisation/investissement ↓ → Emploi ↓
        # Magnitude: +10 Md€ impôts → +0.05 à +0.10 pt chômage
        # Formule conservative: +0.0007 pt chômage par Md€ (coefficient médian)
        # Exemple: Hausse 15 Md€ → delta_revenue = -15 → impact = -(-15) * 0.0001 = +0.0015 pt
        #          Baisse 10 Md€ → delta_revenue = +10 → impact = -(+10) * 0.0001 = -0.0010 pt
        if self._is_first_year_change('impots_production_emploi', params_impots_prod):
            # delta_revenue POSITIF si baisse impôts (97→87 = +10)
            # delta_revenue NÉGATIF si hausse impôts (97→112 = -15)
            # Impact: Hausse 15 Md€ → +0.10 pt, Baisse 10 Md€ → -0.07 pt
            impact_chomage = -delta_revenue * 0.00007  # RECALIBRÉ pour +10 Md€ → +0.07 pt
        else:
            impact_chomage = 0.0

        # Pouvoir d'achat : Impact ONE-TIME (répercussion prix one-time sur consommation, comme TVA/IS).
        if self._is_first_year_change('impots_production_pa', params_impots_prod):
            impact_pa = delta_revenue * 0.001
        else:
            impact_pa = 0.0

        impacts = {
            'recettes': -delta_revenue,  # Négatif car baisse = perte recettes

            'pouvoir_achat': impact_pa,
            'competitivite': impact_competitivite,
            'chomage': impact_chomage
        }

        _log_debug(self.debug_logs, f"Y{year}: Impôts production - montant={montant:.0f}Md€, delta_revenue={-delta_revenue:+.1f}Md€, impact_PIB={impact_pib_pct:+.2f}%")
        return 0, -delta_revenue, impacts

    def _apply_is_exceptionnel_tge(self, measure: Dict, params: Dict, year: int,
                                    gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """IS exceptionnel TGE (taxe exceptionnelle bénéfices). Actuel 8 Md€, max 15 Md€.
        Sources: FMI 2023, Fipeco. Voir METHODOLOGIE.md."""
        montant = params.get('montant', 8)
        montant_base = 8
        delta_revenue = (montant - montant_base)  # Hausse = +recettes

        # Impact compétitivité : ONE-TIME basé sur ATTRACTIVITÉ FISCALE
        # Logique : IS exceptionnel = taxe sur bénéfices exceptionnels TGE
        # Suppression = gain compétitivité fiscale pour TGE
        # Hausse = perte attractivité (signal fiscal négatif)
        # Coefficient : -0.003 par Md€ (impact modéré, taxe ponctuelle)
        # Exemple : Suppression 8 Md€ → +8 × 0.003 = +0.024 compétitivité
        params_is_excep = {'montant': montant}
        if self._is_first_year_change('is_exceptionnel_tge', params_is_excep):
            delta_montant = montant - montant_base  # Hausse positive, baisse négative
            impact_competitivite = -delta_montant * 0.003  # ONE-TIME (hausse = négatif)
            _log_debug(self.debug_logs, f"Y{year}: IS EXCEP TGE CHANGE DETECTED - montant={montant:.0f}Md€, delta={delta_montant:+.0f}Md€, competitivite={impact_competitivite:+.3f}")
        else:
            impact_competitivite = 0.0
            _log_debug(self.debug_logs, f"Y{year}: IS excep TGE montant={montant:.0f}Md€ (no change detected)")

        impacts = {
            'recettes': delta_revenue,
            'pouvoir_achat': 0,
            'competitivite': impact_competitivite
        }

        _log_debug(self.debug_logs, f"Y{year}: IS exceptionnel TGE - montant={montant:.0f}Md€, delta={delta_revenue:+.1f}Md€, impact_compet={impact_competitivite:+.3f}")
        return 0, delta_revenue, impacts

