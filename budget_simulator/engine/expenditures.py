"""Bloc moteur — Dépenses publiques (récurrence chaînée + plafonds).

Refonte « assemblage temporel » (2026-06) — remplace l'ancien duo
« bridging year Y1 (formule fermée) + compounding Y≥2 depuis la base 2025 »
par UNE récurrence unique appliquée dès l'année 1, conforme à la pratique
institutionnelle (CBO/OBR/DG Trésor : l'année 1 se distingue par ses
données, jamais par sa mécanique) :

    Dépenses_t = Dépenses_{t-1} × (1 + g_vol,t) × (1 + π_idx,t)

- ``g_vol,t`` : croissance en VOLUME, moyenne des taux réels par catégorie
  (``spending_growth_rates`` + ajustements démographiques/sectoriels/
  cycliques) pondérée par les parts courantes (base × facteur cumulé).
- ``π_idx,t`` : indexation mixte — ``INDEXATION_DEPENSES_INFLATION_PASSEE`` (~54 %)
  de la dépense suit l'inflation PASSÉE (pensions, prestations revalorisées
  sur N−1 : réalité institutionnelle française, FIPECO), le solde suit le
  déflateur CONTEMPORAIN. Symétrique du PIB au dénominateur : plus de
  « lag uniforme » d'un an sur 100 % de la dépense (ex-bug d'assemblage).

Le chaînage sur le niveau précédent rend le « jet de niveau » de l'ancienne
couture impossible PAR CONSTRUCTION : il n'existe plus de chemin qui
reparte de la base 2025 en oubliant la croissance déjà actée.

État partagé (invariants load-bearing) :
- ``self.depenses_primaires_precedentes`` — niveau nominal ORGANIQUE
  (avant mesures, hors intérêts) de l'année précédente. Cette méthode en
  est le SEUL producteur dans la boucle ; ``simulate()`` n'y réinjecte
  délibérément PAS le delta des mesures (symétrique de
  ``recettes_precedentes``, cf. ``RevenuesMixin`` : les handlers retournent
  des deltas TOTAUX cumulés — les compounder ici serait un double-comptage).
  Init/reset à Σ(spending_categories_base) = primaire INSEE par l'hôte.
- ``self._spending_factors`` — facteurs de croissance RÉELLE cumulés par
  catégorie, mis à jour ici dès l'année 1 (plus de régime spécial). Ils ne
  portent PLUS le niveau (porté par le chaînage ci-dessus) : ils servent de
  CLÉ DE RÉPARTITION (poids des catégories dans g_vol,t) et de base
  dynamique pour le consommateur cross-mixin
  ``MontaigneMixin._apply_rabot_uniforme`` (lecture seule via ``.get`` —
  contrat préservé : facteur à jour de l'année courante, planché à 0,5).
  Cas ``chomage`` : facteur = ratio de chômage courant/base (niveau, pas
  compounding), même sémantique que l'ancien cas spécial.

Lecture seule : ``self.spending_categories_base``,
``self.spending_growth_rates``, ``self.base_params['chomage_base']``,
``INDEXATION_DEPENSES_INFLATION_PASSEE``. ``self.deflateur_cumule`` n'est PLUS
consommé ici (le chaînage nominal intègre l'inflation année par année).

Garde ``spending_ratio = ... if gdp > 0 else 0.55`` : anti-division-zéro
défensif inerte (PIB strictement positif par construction), conservé à
l'identique de l'ancien module — documentation seule, pas un chemin réel.

Sink de logs : ``self.debug_logs`` via ``_log_debug``.
Tous attributs d'instance de ``BudgetSimulatorV45``.
"""
from .._logging import _log_debug
from ..constants import INDEXATION_DEPENSES_INFLATION_PASSEE


class ExpendituresMixin:
    """Bloc moteur — Dépenses publiques (récurrence chaînée + plafonds)."""

    def calculate_expenditures(self, gdp: float, inflation: float, inflation_prev: float,
                               unemployment: float, year: int, output_gap: float) -> float:
        """Dépenses primaires nominales de l'année (récurrence unique, toutes années ≥ 1).

        ``inflation`` = inflation CONTEMPORAINE de l'année simulée ;
        ``inflation_prev`` = inflation de l'année précédente (part indexée).
        """
        debug_this_year = year in [1, 2, 5, 10]

        # === 1) Croissance en volume : moyenne pondérée des taux par catégorie ===
        growth_contribution = 0.0
        total_weight = 0.0

        for category, base_amount in self.spending_categories_base.items():
            weight = base_amount * self._spending_factors[category]

            if category == 'chomage':
                # La dépense chômage suit le RATIO de chômage (niveau, pas un trend) :
                # taux de l'année = variation du ratio vs facteur déjà acté.
                # Plancher 0,5 : garde défensive INERTE (chômage clipé [4 %;12 %],
                # base 7,6 % → target ∈ [0,526;1,579] ; division par zéro impossible,
                # facteur précédent ≥ 0,5 > 0). Documentation seule.
                target_factor = unemployment / self.base_params['chomage_base']
                real_growth = target_factor / self._spending_factors[category] - 1
                self._spending_factors[category] = max(target_factor, 0.5)
            else:
                real_growth = self.spending_growth_rates.get(category, 0)

                # AJUSTEMENTS SPÉCIFIQUES PAR CATÉGORIE (inchangés)
                if category == 'retraites' and year >= 5:
                    real_growth += 0.002  # Vieillissement progressif
                elif category == 'sante':
                    if year >= 3:
                        aging_effect = 0.001 * min(year - 2, 5)
                        real_growth += aging_effect
                elif category == 'dependance' and year >= 5:
                    real_growth += 0.003  # Boom des 85+ ans
                elif category == 'collectivites' and year >= 5:
                    real_growth = max(real_growth, 0.001)
                elif category == 'transition_eco':
                    real_growth *= 1.5 if year <= 5 else 0.5

                # AJUSTEMENT CYCLIQUE (neutre en régime normal)
                if output_gap < -0.02:
                    real_growth *= 0.90  # Récession : dépenses comprimées
                elif output_gap > 0.02:
                    real_growth *= 1.02  # Surchauffe : dépenses en hausse

                self._spending_factors[category] = max(
                    self._spending_factors[category] * (1 + real_growth), 0.5
                )

            growth_contribution += weight * real_growth
            total_weight += weight

            if debug_this_year and weight > 50:
                _log_debug(self.debug_logs,
                           f"  {category}: poids {weight:.0f}, taux réel {real_growth*100:+.2f}%")

        # Garde anti-division-zéro INERTE : bases constantes positives jamais
        # mutées + facteurs ≥ 0,5 → total_weight ≥ ~825 Md€. Documentation seule
        # (même statut que le garde gdp > 0 ci-dessous).
        g_vol = growth_contribution / total_weight if total_weight > 0 else 0.0

        # === 2) Indexation mixte des prix (part passée / part contemporaine) ===
        pi_idx = (INDEXATION_DEPENSES_INFLATION_PASSEE * inflation_prev
                  + (1 - INDEXATION_DEPENSES_INFLATION_PASSEE) * inflation)

        # === 3) Récurrence chaînée sur le niveau organique précédent ===
        nominal_spending = (self.depenses_primaires_precedentes
                            * (1 + g_vol) * (1 + pi_idx))

        # === 4) Plafonds en ratio PIB (garde-fous macro) ===
        # L'état chaîné enregistre le niveau ORGANIQUE PRÉ-plafond : le garde-fou
        # écrête le retour de l'année sans réancrer la récurrence (non-sticky,
        # comportement identique à l'avant-refonte où l'état — factors ×
        # déflateur — ignorait l'écrêtage). Un plafond sticky transformerait un
        # garde-fou ponctuel en consolidation permanente silencieuse (revue
        # 2026-06-10). Plafonds inactifs sur les 9 scénarios livrés (ratio
        # primaire max observé 58,2 %) ; s'ils mordent, le log ci-dessous le
        # rend visible (le validateur aval ne peut pas le voir : il borne à
        # 65 % un ratio que le plafond clampe à 60 %).
        self.depenses_primaires_precedentes = nominal_spending

        spending_ratio = nominal_spending / gdp if gdp > 0 else 0.55
        if spending_ratio > 0.60:
            nominal_spending = 0.60 * gdp
            _log_debug(self.debug_logs, f"Y{year}: PLAFOND dépenses 60% PIB (organique {spending_ratio*100:.1f}%)")
        elif spending_ratio < 0.45:
            nominal_spending = 0.45 * gdp
            _log_debug(self.debug_logs, f"Y{year}: PLANCHER dépenses 45% PIB (organique {spending_ratio*100:.1f}%)")

        if debug_this_year:
            _log_debug(self.debug_logs,
                       f"  g_vol={g_vol*100:+.2f}%, π_idx={pi_idx*100:.2f}% "
                       f"(passée {inflation_prev*100:.2f} / contemp. {inflation*100:.2f})")
        _log_debug(self.debug_logs, f"Y{year}: Dépenses {nominal_spending:.1f} Md€")
        return nominal_spending
