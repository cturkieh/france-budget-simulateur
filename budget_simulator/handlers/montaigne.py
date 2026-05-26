"""Section 6bis — Scénarios Institut Montaigne.

Mesures couvertes :
- ``rabot_uniforme`` : réduction uniforme (%) sur toutes les catégories de
  dépenses, avec exclusions optionnelles (dette, défense, UE). À 8 % =
  -138 Md€ selon l'IM (sur base 1 726 Md€) ; sur notre base simulateur
  (1 635 Md€), -130,8 Md€ à 8 %.

Convention d'application :
- Phasing progressif sur 2 ans (50 % la première année, 100 % ensuite)
  pour éviter un choc trop brutal qui sortirait du domaine de validité
  des multiplicateurs Keynésiens.
- L'impact croissance est capturé via le multiplicateur Keynésien sur
  ``delta_spending`` ; pas de growth_shock séparé pour éviter le
  double-comptage.

Sources principales :
- Institut Montaigne, *Budget Base Zéro*, novembre 2025.
- Critique IM elle-même : « cumule les résistances sans réallocation
  stratégique ».

Le mixin accède à ``self.spending_categories_base``, ``self._spending_factors``
et ``self.debug_logs`` — tous attributs d'instance de ``BudgetSimulatorV45``.
"""
from typing import TYPE_CHECKING, Dict, Tuple

from ..constants import POLICY_START_YEAR
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


class MontaigneMixin(_MixinBase):
    """Handlers Section 6bis — Scénarios Institut Montaigne."""

    def _apply_rabot_uniforme(self, measure: Dict, params: Dict, year: int, gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Rabot budgétaire uniforme - Scénario 1 Institut Montaigne.

        Applique une réduction uniforme (%) sur toutes les catégories de dépenses,
        avec possibilité d'exclure certains postes (dette, défense, UE).

        À 8% = -138 Md€ selon IM (sur base 1 726 Md€).
        Notre base simulateur = 1 635 Md€ → -130,8 Md€ à 8%.

        Critique IM: "Cumule les résistances sans réallocation stratégique"

        Sources: Institut Montaigne "Budget Base Zéro" Nov 2025.
        """
        taux_reduction = params.get('taux_reduction', 0)
        exclure_dette = params.get('exclure_dette', 1)
        exclure_defense = params.get('exclure_defense', 1)
        exclure_ue = params.get('exclure_ue', 1)

        if taux_reduction == 0:
            return 0, 0, {}

        # Année de référence pour phasing
        years_elapsed = year - POLICY_START_YEAR

        # Phasing progressif sur 2 ans (choc trop brutal sinon) :
        # 50 % la première année, 100 % ensuite
        phasing = _year_phasing(years_elapsed, (0.5, 1.0))

        # ===== CALCUL DES ÉCONOMIES PAR CATÉGORIE =====
        # NOTE: On utilise la base DYNAMIQUE (2025 * spending_factor) pour que le taux
        # de réduction s'applique aux dépenses réelles de l'année en cours, pas à la
        # base figée 2025. Sans cela, un rabot de 8% ne représente plus que ~7.3%
        # des dépenses réelles en 2035 (sous-estimation de ~13 Md€/an à 8%).
        categories_base = dict(self.spending_categories_base)

        # Postes incompressibles Institut Montaigne (242 Md€)
        # - Service dette: 107 Md€ (pas dans categories_base, géré séparément)
        # - Défense OTAN: 91 Md€ (defense_equipement 25 + partie masse_salariale défense)
        # - Contribution UE: 44 Md€ (pas dans categories_base)

        total_coupe = 0
        details_coupes = {}

        for categorie, montant_base in categories_base.items():
            # Exclusions
            if exclure_defense and categorie == 'defense_equipement':
                details_coupes[categorie] = 0
                continue

            # Base dynamique : dépense réelle de l'année (base 2025 × facteur de croissance cumulé)
            montant_dynamique = montant_base * self._spending_factors.get(categorie, 1.0)

            # Calcul de la coupe sur la base dynamique
            coupe = montant_dynamique * taux_reduction * phasing
            details_coupes[categorie] = coupe
            total_coupe += coupe

        # Ajout coupe UE si non exclue (44 Md€ base, pas dans categories)
        if not exclure_ue:
            coupe_ue = 44 * taux_reduction * phasing
            details_coupes['contribution_ue'] = coupe_ue
            total_coupe += coupe_ue

        # Note: La dette (107 Md€) est TOUJOURS incompressible (intérêts contractuels)
        # Elle n'est pas dans spending_categories et ne peut être coupée

        delta_spending = -total_coupe  # Économies = dépenses négatives

        # ===== IMPACTS MACROÉCONOMIQUES =====
        # Le rabot est particulièrement nocif car il coupe TOUT sans discernement

        # 1. Impact Gini (inégalités) - RÉGRESSIF
        # Coupes sociales touchent plus les bas revenus
        pct_social = (details_coupes.get('retraites', 0) +
                      details_coupes.get('sante', 0) +
                      details_coupes.get('minima_sociaux', 0) +
                      details_coupes.get('dependance', 0)) / max(total_coupe, 0.1)
        impact_gini = 0.10 * taux_reduction * pct_social * phasing  # +0.008 à 8%

        # 2. Impact Pouvoir d'Achat - NÉGATIF
        # Moins de prestations, moins de salaires publics
        impact_pa = -0.15 * taux_reduction * phasing  # -1.2% à 8%

        # 3. Impact Croissance
        # NOTE: L'impact croissance du rabot est capturé via le multiplicateur Keynésien
        # sur delta_spending. Pas de growth_shock séparé pour éviter le double-comptage.

        # 4. Impact Chômage - HAUSSE (Okun)
        # Moins de fonctionnaires, moins de commandes publiques
        impact_chomage = 0.004 * taux_reduction * phasing  # +0.32 pt à 8%

        # 5. Impact Compétitivité - LÉGÈREMENT POSITIF (moins de prélèvements futurs)
        impact_competitivite = 0.002 * taux_reduction * phasing

        # 6. Impact Services Publics - DÉGRADATION
        # Non modélisé directement mais implicite dans PA et confiance

        impacts = {
            'depenses': delta_spending,
            'gini': impact_gini,
            'pouvoir_achat': impact_pa,
            'competitivite': impact_competitivite,
            'chomage': impact_chomage,
            # Métadonnées de debug. La valeur est un sous-dict, ce qui s'écarte
            # du contrat ImpactsDict = Dict[str, float]. Les agrégateurs du
            # moteur ne lisent que les clés numériques connues (gini,
            # competitivite, chomage, pouvoir_achat, depenses, recettes), donc
            # rabot_details est simplement ignoré sans erreur runtime. À aplatir
            # ou déplacer vers _log_debug lors d'un futur chantier de typage
            # strict (mypy).
            'rabot_details': {
                'taux': taux_reduction,
                'phasing': phasing,
                'total_coupe': total_coupe,
                'exclusions': {
                    'dette': bool(exclure_dette),
                    'defense': bool(exclure_defense),
                    'ue': bool(exclure_ue)
                }
            }
        }

        _log_debug(self.debug_logs,
            f"Y{year}: RABOT UNIFORME - Taux {taux_reduction*100:.0f}%, Phasing {phasing*100:.0f}%, "
            f"Économies {total_coupe:.1f} Md€, Gini {impact_gini:+.4f}, PA {impact_pa:+.2%}, "
            f"Chômage {impact_chomage:+.3f} pt"
        )

        return delta_spending, 0, impacts
