"""Section 6bis — Scénarios Institut Montaigne.

Mesures couvertes :
- ``rabot_uniforme`` : réduction uniforme (%) sur toutes les catégories de
  dépenses, avec exclusions optionnelles (dette, défense, UE). À 8 %, la
  note vise 138 Md€ (graphique, p. 84) ou 140 Md€ (texte, p. 83) en 2029 ;
  le moteur calcule le rendement du taux sur ses propres catégories de
  dépenses, en euros de l'année, hors défense au périmètre de la note
  (2,7 % du PIB, pensions comprises) et hors contribution à l'Union
  européenne, comprise dans la catégorie « autres » (lot 3).

Convention d'application :
- Phasing progressif sur 2 ans (50 % la première année, 100 % ensuite)
  pour éviter un choc trop brutal qui sortirait du domaine de validité
  des multiplicateurs Keynésiens.
- L'impact croissance est capturé via le multiplicateur Keynésien sur
  ``delta_spending`` ; pas de growth_shock séparé pour éviter le
  double-comptage.

Sources principales :
- Institut Montaigne, *Budget Base Zéro*, novembre 2025.
- Selon ses auteurs, cette approche, « en plus de cristalliser les
  résistances, traduirait une logique d’austérité sans cap plutôt qu’une
  stratégie cohérente de redressement ».

Le mixin accède à ``self.spending_categories_base``, ``self._spending_factors``
et ``self.debug_logs`` — tous attributs d'instance de ``BudgetSimulatorV45``.
"""
from typing import TYPE_CHECKING, Dict, Tuple

from ..constants import (
    AAH_2025_MD_EUR,
    CONTRIBUTION_UE_2025_MD,
    GINI_ALLOC_PAR_MD_EUR,
    GINI_PENSIONS_PAR_MD,
    GINI_SOLIDARITE_PAR_MD,
    MONTAIGNE_DEFENSE_PART_PIB,
    PIB_BASE_2025_MD_EUR,
)
from .._logging import _log_debug
from ._phasing import _year_phasing
from ._types import ImpactsDict, canaux_menages


# Idiome mixin-self typing : NE PAS factoriser dans _types.py (casse la
# liaison self mypy + risque MRO). Réplication volontaire 7×. Cf Lot D.
if TYPE_CHECKING:
    from ._types import _SimulatorState

    _MixinBase = _SimulatorState
else:
    _MixinBase = object

# Montée en charge du rabot : 50 % la première année, 100 % ensuite.
_RABOT_PHASING = (0.5, 1.0)
# Catégories de PRESTATIONS EN ESPÈCES, seules à toucher directement le revenu
# disponible des ménages (v0.6.8) : pensions, allocations chômage, minima
# sociaux, et l'AAH dans « dépendance » (AAH_2025_MD_EUR). La santé et l'APA
# sont des transferts EN NATURE, hors RDB (INSEE) : un euro de santé coupé par
# le rabot vaut zéro de revenu, comme dans le levier santé (_apply_sante, où
# seules les franchises comptent).
_CATEGORIES_ESPECES = ('retraites', 'chomage', 'minima_sociaux')


class MontaigneMixin(_MixinBase):
    """Handlers Section 6bis — Scénarios Institut Montaigne."""

    def _apply_rabot_uniforme(self, measure: Dict, params: Dict, year: int, gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Rabot budgétaire uniforme - Scénario 1 Institut Montaigne.

        Applique une réduction uniforme (%) sur toutes les catégories de dépenses,
        avec possibilité d'exclure certains postes (dette, défense, UE).

        À 8 %, la note vise 138 Md€ (graphique, p. 84) ou 140 Md€ (texte,
        p. 83) en 2029 ; le moteur calcule le rendement du taux.

        Sources: Institut Montaigne "Budget Base Zéro" Nov 2025.
        """
        taux_reduction = params.get('taux_reduction', 0)
        exclure_dette = params.get('exclure_dette', 1)
        exclure_defense = params.get('exclure_defense', 1)
        exclure_ue = params.get('exclure_ue', 1)

        if taux_reduction == 0 and 'rabot_uniforme' not in self._measure_params_tracker:
            # Lot 4 : un retour à 0 après un rabot (déclencheur ponctuel au
            # traqueur) calcule encore, pour RENDRE son effet Gini.
            return 0, 0, {}

        # Année de référence pour phasing — horloge du levier (v0.7.0).
        years_elapsed = year - self._origine('rabot_uniforme')

        # Phasing progressif sur 2 ans (choc trop brutal sinon) :
        # 50 % la première année, 100 % ensuite
        phasing = _year_phasing(years_elapsed, _RABOT_PHASING)

        # ===== CALCUL DES ÉCONOMIES PAR CATÉGORIE =====
        # Assiette en EUROS DE L'ANNÉE (lot 3) : masse nominale de chaque catégorie
        # (base 2025 × facteur de volume × indice de prix des dépenses,
        # masse_categorie_nominale), la méthode de la note (annexe 4, p. 141 :
        # « tendanciel en volume ajusté par le déflateur du PIB », euros de 2029).
        # Jusqu'au lot 3, l'assiette était en volume (euros 2025) : un rabot de 8 %
        # ne valait qu'environ 7,4 % des dépenses de l'année en 2032.
        masses = {c: self.masse_categorie_nominale(c) for c in self.spending_categories_base}

        # Postes incompressibles de la note (242 Md€ en 2029, p. 79-82) :
        # - service de la dette (107 Md€) : hors des catégories du moteur ;
        # - défense (91 Md€ = 2,7 % du PIB, pensions comprises, p. 81 et note 113) :
        #   MONTAIGNE_DEFENSE_PART_PIB × PIB de l'année, dont l'équipement
        #   (catégorie exclue en entier) ; le reste (personnel, pensions,
        #   fonctionnement) est retiré AU PRORATA des autres catégories, faute de
        #   catégorie « défense » dans le moteur (convention déclarée : la
        #   composition sociale de la coupe ne change pas). Jusqu'au lot 3, seul
        #   l'équipement était exclu (25 Md€ en 2025) ;
        # - contribution à l'Union européenne (44 Md€ en 2029 selon la note) :
        #   COMPRISE dans la catégorie « autres », résidu de la dépense des
        #   administrations, qui compte l'opération D76 (ressources propres de
        #   l'UE fondées sur la TVA et le RNB) ; CONTRIBUTION_UE_2025_MD sur le
        #   chemin de sa catégorie (facteur de volume et indice de prix). Exclue,
        #   elle est retirée de l'assiette de « autres » ; non exclue, elle est
        #   rabotée une fois, dans « autres ». Jusqu'au lot 3, elle restait rabotée
        #   même exclue, et sans exclusion 44 Md€ × taux étaient ajoutés par-dessus
        #   (la même dépense coupée deux fois).
        assiettes = dict(masses)
        contribution_ue = 0.0
        if exclure_ue:
            contribution_ue = min(masses['autres'],
                                  CONTRIBUTION_UE_2025_MD * self._spending_factors.get('autres', 1.0)
                                  * self.indice_prix_depenses())
            assiettes['autres'] = masses['autres'] - contribution_ue

        def _part_coupee(m, pib):
            if not exclure_defense:
                return 1.0
            surplus_defense = max(0.0, MONTAIGNE_DEFENSE_PART_PIB * pib - m['defense_equipement'])
            return 1.0 - surplus_defense / sum(v for c, v in m.items() if c != 'defense_equipement')

        part_coupee = _part_coupee(assiettes, gdp)

        total_coupe = 0
        details_coupes = {}

        for categorie, masse in assiettes.items():
            # Exclusions
            if exclure_defense and categorie == 'defense_equipement':
                details_coupes[categorie] = 0
                continue

            coupe = masse * part_coupee * taux_reduction * phasing
            details_coupes[categorie] = coupe
            total_coupe += coupe

        # Note: La dette (107 Md€) est TOUJOURS incompressible (intérêts contractuels)
        # Elle n'est pas dans spending_categories et ne peut être coupée

        delta_spending = -total_coupe  # Économies = dépenses négatives

        # ===== IMPACTS MACROÉCONOMIQUES =====
        # Le rabot est particulièrement nocif car il coupe TOUT sans discernement

        # 1. Impact Gini (inégalités) — lot 4, méthode unique (constants.py
        # § CANAUX GINI) : chaque catégorie de PRESTATIONS EN ESPÈCES coupée à
        # son coefficient par Md€ — minima sociaux et AAH à celui des
        # prestations ciblées de l'INSEE, allocations chômage à la règle
        # montant du chômage (ancre DREES), pensions à la convention des
        # pensions ; santé et APA (en nature) et les autres catégories : 0 (hors
        # du revenu disponible, comme au canal ménages ci-dessous). Montant
        # d'année PLEINE que fixe le taux (base 2025, hors phasage et hors
        # croissance), émis UNE fois au changement du taux, en incrément (et
        # rendu au retour à 0). Jusqu'ici 0,10 × taux × part sociale ×
        # phasage, sans source, RÉÉMIS chaque année dans un agrégateur
        # cumulatif : l'indice dérivait tant que le rabot durait.
        # Lot 3 : le montant porte la même part coupée que la coupe (exclusion de
        # la défense au-delà de l'équipement), lue sur les assiettes de 2025
        # (contribution à l'UE de 2025 retirée de « autres » si elle est exclue)
        # et le PIB de 2025 — montant de l'année source, hors croissance, comme le
        # reste de la règle ; part coupée 1 sans exclusion ou à part nulle.
        base_2025 = self.spending_categories_base
        assiettes_2025 = dict(base_2025)
        if exclure_ue:
            assiettes_2025['autres'] = base_2025['autres'] - min(base_2025['autres'], CONTRIBUTION_UE_2025_MD)
        part_coupee_2025 = _part_coupee(assiettes_2025, PIB_BASE_2025_MD_EUR)

        def _effet_rabot_uniforme(p):
            t = p['taux'] * p['part_coupee']
            return -(GINI_SOLIDARITE_PAR_MD * (base_2025['minima_sociaux'] * t + AAH_2025_MD_EUR * t)
                     - GINI_ALLOC_PAR_MD_EUR * base_2025['chomage'] * t
                     + GINI_PENSIONS_PAR_MD * base_2025['retraites'] * t)

        impact_gini = self._effet_ponctuel('rabot_uniforme', {'taux': taux_reduction, 'part_coupee': part_coupee_2025},
                                           _effet_rabot_uniforme)

        # 2. Pouvoir d'achat (v0.6.8) : les coupes de PRESTATIONS EN ESPÈCES
        # (pensions, chômage, minima sociaux, AAH) sont un revenu retiré aux
        # ménages — canal ``prestations``, en niveau de l'année. Santé, APA
        # (transferts en nature) et autres coupes (masse salariale, assimilée
        # à des effectifs, fonctionnement, investissement, dotations, aides
        # aux entreprises, UE) passent par la croissance. L'ancien « −0,15 ×
        # taux », réémis chaque année, composait −7,6 pts d'indice en 2035
        # pour un rabot de 7,5 %.
        # AAH : part en espèces de « dépendance », même assiette (euros de l'année,
        # même part coupée que sa catégorie).
        coupe_aah = (AAH_2025_MD_EUR * self._spending_factors.get('dependance', 1.0)
                     * self.indice_prix_depenses() * part_coupee * taux_reduction * phasing)
        coupes_prestations = (sum(details_coupes.get(c, 0.0) for c in _CATEGORIES_ESPECES)
                              + coupe_aah)

        # 3. Impact Croissance
        # NOTE: L'impact croissance du rabot est capturé via le multiplicateur Keynésien
        # sur delta_spending. Pas de growth_shock séparé pour éviter le double-comptage.

        # 4. Impact Chômage : PAS d'effet direct (v0.6.7, lot 3). L'ancien terme
        # (+0,004 × taux, « moins de fonctionnaires, moins de commandes
        # publiques », étiqueté Okun) refaisait le chemin coupe → activité →
        # chômage que le moteur fait déjà : le multiplicateur keynésien sur
        # delta_spending (note 3 ci-dessus), puis la loi d'Okun. Même traitement
        # que le levier fonction_publique, dont les suppressions de postes ne
        # passent que par ce canal. Lot 1 : il avait d'abord été ramené de
        # récurrent (×15,7 par la convergence NAIRU) à une émission par incrément.
        # 5. Impact Compétitivité - LÉGÈREMENT POSITIF (moins de prélèvements futurs)
        impact_competitivite = 0.002 * taux_reduction * phasing

        # 6. Impact Services Publics - DÉGRADATION
        # Non modélisé directement mais implicite dans PA et confiance

        impacts = {
            'depenses': delta_spending,
            'gini': impact_gini,
            'competitivite': impact_competitivite,
            'menages': canaux_menages(prestations=-coupes_prestations),
            # Lot 5c (réfutation M1) : la coupe de la ligne « Dotations » (la même que
            # celle du curseur collectivites.dotation) a sa part investie, comme une
            # baisse de dotation : flux d'investissement (impulsion) et, en mode
            # cadre, effet d'offre du capital public local (growth.py).
            'depenses_investissement': self.part_investie_d_une_variation_de_dotation(
                -details_coupes.get('collectivites', 0.0)),
            # Métadonnées de debug. La valeur est un sous-dict, ce qui s'écarte
            # du contrat ImpactsDict = Dict[str, float]. Les agrégateurs du
            # moteur ne lisent que les clés connues (gini, competitivite,
            # chomage, menages, depenses, recettes), donc
            # rabot_details est simplement ignoré sans erreur runtime. À aplatir
            # ou déplacer vers _log_debug lors d'un futur chantier de typage
            # strict (mypy).
            'rabot_details': {
                'taux': taux_reduction,
                'phasing': phasing,
                'total_coupe': total_coupe,
                'contribution_ue_exclue': contribution_ue,
                'exclusions': {
                    'dette': bool(exclure_dette),
                    'defense': bool(exclure_defense),
                    'ue': bool(exclure_ue)
                }
            }
        }

        _log_debug(self.debug_logs,
            f"Y{year}: RABOT UNIFORME - Taux {taux_reduction*100:.0f}%, Phasing {phasing*100:.0f}%, "
            f"Économies {total_coupe:.1f} Md€ (prestations {coupes_prestations:.1f}), Gini {impact_gini:+.4f}"
        )

        return delta_spending, 0, impacts
