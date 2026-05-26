"""Section 6 — Paramètres additionnels (Débats Présidentielle 2027).

Mesures couvertes :
- ``smic`` : hausse SMIC brut (NFP 2027 : 1600€ net / +14.4%, 3.2M salariés concernés).
- ``taxe_superprofits`` : taxe 25% sur bénéfices >120% moyenne historique
  (temporaire 3 ans 2026-2028).
- ``exonerations_salaires`` : exonération cotisations patronales sur hausses
  salariales >1% (NFP 2027).

Convention d'application :
- Tous les handlers de ce mixin appliquent les effets micro
  (``pouvoir_achat``, ``gini``, ``competitivite``, ``chomage``) en mode
  NIVEAU one-time, gated sur ``years_elapsed == 0``.
- Voir docs/METHODOLOGIE.md § "Effets NIVEAU vs FLUX" pour le contrat de gating.

Sources principales :
- OFCE 2024, DARES 2024, Trésor-Éco 97 (2012), Cahuc & Carcillo 2014,
  Kramarz & Philippon (2001), Abowd et al. (2000), INSEE 2024,
  IPP Bozio 2018, OFCE Plane 2014.
- Voir docs/METHODOLOGIE.md § Mesures Presidentielles 2027.

Le mixin accède à ``self.mesures`` et ``self.debug_logs``, attributs
d'instance de ``BudgetSimulatorV45``.
"""
import logging
from typing import TYPE_CHECKING, Dict, Tuple

from ..constants import POLICY_START_YEAR
from .._logging import _log_debug
from ._phasing import _one_time_level, _resolve_intensite_or_legacy, _year_phasing
from ._types import ImpactsDict

logger = logging.getLogger(__name__)


# Idiome mixin-self typing : NE PAS factoriser dans _types.py (casse la
# liaison self mypy + risque MRO). Réplication volontaire 7×. Cf Lot D.
if TYPE_CHECKING:
    from ._types import _SimulatorState

    _MixinBase = _SimulatorState
else:
    _MixinBase = object


class AdditionnelsMixin(_MixinBase):
    """Handlers Section 6 — Paramètres additionnels Présidentielle 2027."""

    def _apply_smic(self, measure: Dict, params: Dict, year: int, gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """SMIC (actuel 1800€ brut). NFP: 1600€ net (+14.4%). 3.2M salariés concernés. Effets NIVEAU one-time.
        Sources: OFCE 2024, DARES 2024. Voir METHODOLOGIE.md § Mesures Presidentielles 2027."""
        smic_brut = params.get('montant_brut', 1800)  # Actuel 2024 : ~1800€ brut
        smic_actuel = 1800  # Baseline 2025

        if smic_brut == smic_actuel:
            return 0, 0, {}

        # Année de mise en œuvre
        years_elapsed = year - POLICY_START_YEAR

        # ===== CALCUL IMPACTS =====
        delta_brut = smic_brut - smic_actuel
        hausse_pct = delta_brut / smic_actuel

        # 1. DÉPENSES FONCTION PUBLIQUE
        # 15% des agents FP cat. C concernés (masse salariale ~50 Md€)
        # Correction double-comptage : si le point d'indice augmente aussi,
        # la hausse FP est déjà partiellement couverte. Surcoût SMIC net = max(0, hausse - PI).
        masse_salariale_fp_concernee = 50  # Md€
        hausse_pi_pct = 0.0
        if 'fonction_publique' in self.mesures:
            hausse_pi_pct = self.mesures['fonction_publique'].get('point_indice', 0) / 100
        delta_fp = masse_salariale_fp_concernee * max(0, hausse_pct - hausse_pi_pct)

        # 2. DÉPENSES AIDES SOCIALES (indexées sur SMIC : RSA, prime activité)
        # RSA = 0.5 SMIC, Prime activité indexée
        delta_aides = 12 * hausse_pct  # RSA + prime activité ~12 Md€

        # 3. RECETTES COTISATIONS SOCIALES
        # Hausse cotisations sur masse salariale privée
        # Salariés privés SMIC : ~2.7M × 12 mois × hausse × taux cotisations (45%)
        # LIMITATION ASSUMÉE : pas d'effet de diffusion 20-30% au-dessus du SMIC
        # (OFCE Plane 2014, IPP Bozio 2018). Sous-estime probablement coûts/recettes
        # de ~25-30% pour des hausses SMIC importantes. Choix de simplification pédagogique.
        salaries_prives_smic = 2.7  # millions
        delta_cotisations = salaries_prives_smic * 12 * delta_brut * 0.45 / 1000  # Md€

        # 4. TOTAL
        delta_spending = delta_fp + delta_aides
        delta_revenue = delta_cotisations

        # ===== IMPACTS MACROÉCONOMIQUES =====
        # Pouvoir achat : Effet NIVEAU one-time appliqué l'année de mise en œuvre.
        # Élasticité 0.06 : +10% SMIC → +0.6% PA agrégé (OFCE Plane 2014, IPP Bozio 2018,
        # 15% pop active directe + diffusion partielle 20-30% au-dessus du SMIC).
        # Cohérent avec règle METHODOLOGIE "+100€ SMIC ≈ +0.5% PA" (≈ +7% hausse → élasticité ~0.07).
        impact_pa = _one_time_level(years_elapsed, hausse_pct * 0.06)

        # Compétitivité : -0.25% pour +10% SMIC (coût travail entreprises)
        # Impact permanent sur coût travail, mais appliqué une fois (structure de coûts)
        # Élasticité : 0.025 (DG Trésor 2023 - effet modéré car SMIC = 15% masse salariale)
        impact_competitivite = _one_time_level(years_elapsed, -hausse_pct * 0.025)

        # Gini : -0.003 pour +10% SMIC (redistribution vers bas salaires)
        # Impact permanent sur distribution, mais appliqué une fois (structure revenus)
        # Élasticité : 0.03 (INSEE 2024 - effet concentré sur D1-D2)
        impact_gini = _one_time_level(years_elapsed, -hausse_pct * 0.03)

        # Chômage : Hausse SMIC → Hausse coût travail → Destruction emplois non qualifiés (ONE-TIME)
        # IMPORTANT : Impact NÉGATIF sur emploi (hausse SMIC augmente chômage)
        # Sources: Kramarz & Philippon (2001), Abowd et al. (2000)
        # Élasticité emploi/SMIC = -0.10 à -0.30 pour France (consensus)
        # Mécanisme: Coût travail ↑ → Substitution capital/travail → Destruction emplois bas qualifications
        # Formule conservative: +0.025 pt chômage par % de hausse SMIC (2.5 pt par 100% hausse)
        # Exemple: Hausse 10% (hausse_pct=0.10) → +0.10 * 0.025 = +0.0025 = +0.25 pt chômage
        #          Hausse 5% (hausse_pct=0.05) → +0.05 * 0.025 = +0.00125 = +0.125 pt chômage
        # POSITIF car hausse SMIC augmente le chômage (one-time)
        impact_chomage = _one_time_level(years_elapsed, hausse_pct * 0.025)

        impacts = {
            'depenses': delta_spending,
            'recettes': delta_revenue,
            'fp': delta_fp,
            'aides_sociales': delta_aides,
            'cotisations': delta_cotisations,
            'pouvoir_achat': impact_pa,
            'competitivite': impact_competitivite,
            'gini': impact_gini,
            'chomage': impact_chomage
        }

        _log_debug(self.debug_logs,
            f"Y{year}: SMIC {smic_brut}€ brut ({hausse_pct*100:+.1f}%) → "
            f"Dép. FP {delta_fp:.1f} Md€, Aides {delta_aides:.1f} Md€, "
            f"Cotis. +{delta_cotisations:.1f} Md€, Net {delta_spending-delta_revenue:+.1f} Md€"
        )

        return delta_spending, delta_revenue, impacts

    def _apply_taxe_superprofits(self, measure: Dict, params: Dict, year: int, gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Taxe superprofits. NFP: 25% >120% moy → +15 Md€. Temporaire 3 ans (2026-2028). Effets NIVEAU one-time.
        Sources: NFP 2027, OFCE 2024. Voir METHODOLOGIE.md § Mesures Presidentielles 2027."""
        # Mode simplifié (slider unique d'intensité) sinon mode legacy.
        # Simplifié : taux = 0.25·i ; seuil = 1.0 + 0.20·i (NFP 100 % →
        # 25 % tous secteurs, seuil 120 %) ; tous_secteurs = i > 0.
        taux_taxe, seuil_hausse, tous_secteurs = _resolve_intensite_or_legacy(
            params,
            lambda i: (0.25 * i, 1.0 + 0.20 * i, i > 0),
            lambda p: (
                p.get('taux', 0.25),
                p.get('seuil_hausse', 1.20),
                p.get('tous_secteurs', True),
            ),
        )

        # Année de référence
        years_elapsed = year - POLICY_START_YEAR

        # ===== PHASING : plein effet immédiat dès l'entrée en vigueur =====
        phasing = _year_phasing(years_elapsed, (1.0,))

        # ===== TEMPORAIRE 3 ANS (crise inflation 2022-2024) =====
        # Après 2028, superprofits disparaissent (retour normalité)
        if year >= 2029:
            return 0, 0, {'recettes': 0}

        # ===== ASSIETTE SUPERPROFITS =====
        if tous_secteurs:
            # Tous secteurs : énergie (40 Md€) + banques (10 Md€) + luxe (5 Md€) + tech (5 Md€)
            superprofits_total = 60.0  # Md€ (2022-2024)
        else:
            # Énergie uniquement (TotalEnergies, Engie, etc.)
            superprofits_total = 40.0  # Md€

        # Ajustement selon seuil : si seuil 150%, seuls les très gros superprofits taxés
        if seuil_hausse > 1.20:
            reduction_assiette = (seuil_hausse - 1.20) / 0.30  # 30% de hausse max
            superprofits_total *= (1 - reduction_assiette * 0.5)

        # ===== RECETTES =====
        delta_revenue = superprofits_total * taux_taxe * phasing

        # Plafond réaliste 20 Md€ — logger.warning visible hors mode debug
        # pour qu'une calibration aberrante ne soit pas masquée par le clip.
        if delta_revenue > 20.0:
            logger.warning(
                "taxe_superprofits Y%d : recettes plafonnées à 20.0 Md€ "
                "(calcul brut : %.1f Md€, taux=%.2f, secteurs=%s)",
                year, delta_revenue, taux_taxe,
                "tous" if tous_secteurs else "energie",
            )
            delta_revenue = 20.0

        # ===== IMPACTS MACROÉCONOMIQUES =====
        # IMPORTANT : Effets NIVEAU (one-time), pas FLUX (recurring)
        # Gini : -0.01 (redistribution capital → État)
        # PA : neutre (taxe entreprises, pas ménages)
        # Compétitivité : -0.005 (risque délocalisation marginale)
        impact_gini = _one_time_level(
            years_elapsed, -0.01 * (delta_revenue / 15) * phasing
        )
        impact_competitivite = _one_time_level(
            years_elapsed,
            -0.005 * (delta_revenue / 15) * phasing if tous_secteurs else -0.002,
        )
        impact_pa = 0.0

        impacts = {
            'recettes': delta_revenue,
            'gini': impact_gini,
            'pouvoir_achat': impact_pa,
            'competitivite': impact_competitivite
        }

        _log_debug(self.debug_logs,
            f"Y{year}: Taxe superprofits - Taux {taux_taxe*100:.0f}%, Seuil {seuil_hausse*100:.0f}%, "
            f"Secteurs {'tous' if tous_secteurs else 'énergie'}, Recettes {delta_revenue:.1f} Md€"
        )

        return 0, delta_revenue, impacts

    def _apply_exonerations_salaires(self, measure: Dict, params: Dict, year: int, gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Exonérations hausses salaires. NFP: exo 100% hausses >1% → -12 Md€. Masse salariale 800 Md€. Effets NIVEAU one-time.
        Sources: NFP 2027, OFCE 2024. Voir METHODOLOGIE.md § Mesures Presidentielles 2027."""
        # Mode simplifié (slider unique : exo 100% seuil 1%) sinon legacy.
        taux_exo, seuil = _resolve_intensite_or_legacy(
            params,
            lambda i: (i, 0.01),
            lambda p: (p.get('taux_exoneration', 0.0), p.get('seuil_hausse', 0.01)),
        )

        if taux_exo == 0:
            return 0, 0, {}

        # Année de référence
        years_elapsed = year - POLICY_START_YEAR

        # ===== PHASING : plein effet immédiat dès l'entrée en vigueur =====
        phasing = _year_phasing(years_elapsed, (1.0,))

        # ===== MASSE SALARIALE CONCERNÉE =====
        # Hausse salariale moyenne suit l'inflation observée + ~1pt productivité (consensus OFCE).
        # Borne basse 1% pour éviter les hausses négatives en cas de déflation simulée.
        # Cohérent avec calibration NFP -12 Md€ à inflation 2% (hypothèse de référence).
        masse_salariale_privee = 800.0  # Md€
        hausse_sal_moyenne = max(0.01, inflation + 0.01)

        # Hausses au-dessus du seuil
        hausse_eligibles = max(0, hausse_sal_moyenne - seuil)
        masse_hausse = masse_salariale_privee * hausse_eligibles

        # ===== COÛT EXONÉRATIONS =====
        taux_cotis_patronales = 0.45
        cout_exonerations = masse_hausse * taux_cotis_patronales * taux_exo * phasing

        # ===== EFFET MULTIPLICATEUR =====
        # Si exonération attractive, entreprises augmentent + les salaires
        multiplicateur = 1.5 if taux_exo >= 0.75 else 1.2
        cout_total = cout_exonerations * multiplicateur

        # Plafond 15 Md€ — logger.warning visible hors mode debug pour qu'une
        # calibration aberrante ne soit pas masquée par le clip.
        if cout_total > 15.0:
            logger.warning(
                "exonerations_salaires Y%d : coût plafonné à 15.0 Md€ "
                "(calcul brut : %.1f Md€, taux_exo=%.2f)",
                year, cout_total, taux_exo,
            )
            cout_total = 15.0

        delta_revenue = -cout_total  # Perte recettes cotisations

        # ===== IMPACTS MACROÉCONOMIQUES =====
        # IMPORTANT : Effets NIVEAU (one-time), pas FLUX (recurring)
        # PA : +0.15% pour 12 Md€ exonérations (Trésor-Éco 97 calibration emploi)
        # Gini : PAS D'IMPACT MICRO (incitation entreprises, pas transfert direct garanti)
        # Les hausses de salaires ne sont PAS garanties, seulement incitées
        # Impact Gini vient UNIQUEMENT de l'effet macro (si hausses effectives)
        # Compétitivité : +0.003 (coût travail stable malgré hausses)
        # Tous one-time (NIVEAU) l'année d'entrée en vigueur :
        # PA/Compét — calibration Trésor-Éco 97 (2012) : 22 Md€ allègements
        #   → ~250k emplois par 12 Md€ × 1500€/mois × 12 ≈ ~0.15% RDB → +0.15% PA / 12 Md€.
        # Chômage — Cahuc & Carcillo 2014 (allègements ciblés), DARES 2019 :
        #   ciblage bas salaires, -0.03 pt par Md€ (12 Md€ → -0.36 pt).
        impact_pa = _one_time_level(years_elapsed, 0.0015 * (cout_total / 12) * phasing)
        impact_competitivite = _one_time_level(
            years_elapsed, 0.003 * (cout_total / 12) * phasing
        )
        impact_chomage = _one_time_level(years_elapsed, -0.0003 * cout_total * phasing)

        impacts = {
            'recettes': delta_revenue,
            'pouvoir_achat': impact_pa,
            'competitivite': impact_competitivite,
            'chomage': impact_chomage
        }

        _log_debug(self.debug_logs,
            f"Y{year}: Exonérations salaires - Taux {taux_exo*100:.0f}%, Seuil {seuil*100:.1f}%, "
            f"Coût {cout_total:.1f} Md€, PA {impact_pa:+.2%}"
        )

        return 0, delta_revenue, impacts
