"""Bloc moteur — Dépenses publiques (compounding par catégorie + plafonds).

Méthode couverte :
- ``calculate_expenditures`` : dépenses nominales de l'année. Année 1
  (2026) : formule fermée d'amorçage (« bridging year »). Années ≥ 2 :
  compounding itératif par catégorie (taux propre + ajustements
  démographiques/sectoriels + ajustement cyclique selon ``output_gap``),
  conversion réel→nominal via déflateur cumulé, puis plafonds garde-fou
  en ratio PIB (45 % / 60 %).

État partagé ``self._spending_factors`` — invariant load-bearing :
- Dict de facteurs de croissance cumulés par catégorie.
  ``calculate_expenditures`` en est PRODUCTEUR et CONSOMMATEUR : pour
  chaque catégorie (années ≥ 2) il lit le facteur courant, le multiplie
  par ``(1 + real_growth)``, le plancher à 0,5, puis le réutilise. C'est
  le SEUL producteur dans la boucle en régime établi : la mutation
  in-méthode porte la persistance N→N+1 (comme ``RevenuesMixin`` /
  ``DebtMixin``, ``simulate()`` ne re-persiste PAS).
- Consommateur CROSS-MIXIN : ``MontaigneMixin._apply_rabot_uniforme``
  lit ``self._spending_factors`` (en lecture seule, via ``.get``) pour
  appliquer le rabot sur la base de dépense DYNAMIQUE de l'année. Le
  contrat producteur garanti ici (facteur à jour de l'année courante,
  planché à 0,5) est ce dont ce consommateur dépend.
- Invariant « bridging year » : la branche ``year == 1`` retourne une
  formule fermée et NE TOUCHE délibérément PAS ``_spending_factors``
  (ils restent à 1,0). Les initialiser en Y1 créerait un
  double-comptage en Y2 (le compounding ≥ Y2 repartirait d'une base
  déjà gonflée). Ne pas « optimiser » cette branche sans relire ce
  contrat.
- Init / reset (``{cat: 1.0 ...}`` dans ``__init__`` / ``_reset_state``)
  relèvent de l'hôte ``BudgetSimulatorV45``, hors périmètre du split
  (non touché).

Lecture seule : ``self.spending_categories_base``,
``self.spending_growth_rates``, ``self.deflateur_cumule``,
``self.base_params`` (``amorcage_depenses_y1``, ``chomage_base``).

Garde ``spending_ratio = nominal_spending / gdp if gdp > 0 else 0.55``
: anti-division-zéro défensif. ``gdp`` est un NIVEAU de PIB strictement
positif par construction (composé année après année depuis ~2900 Md€),
donc la branche ``else 0.55`` est morte dans le régime du modèle ;
``0.55`` tombe volontairement dans la fenêtre neutre ``[0.45 ; 0.60]``
→ aucun plafond appliqué si jamais atteinte. PAS de vecteur réel
``gdp <= 0`` — aucune dette Phase 2. Même statut que le garde
``debt_total < 0`` de ``DebtMixin`` (lui aussi prouvé inatteignable par
la re-analyse adverse 2026-05-16 : plancher empirique 2238 Md€) :
deux gardes défensifs inertes, documentation seule.

NB : la constante de classe ``SUPPLY_EFFECTS`` qui suit physiquement
``calculate_expenditures`` dans le monolithe N'appartient PAS à ce bloc
(effet d'offre structurel consommé par ``calculate_growth``) — elle
reste sur ``BudgetSimulatorV45``, non migrée ici.

Sink de logs : ``self.debug_logs`` via ``_log_debug``.
Tous attributs d'instance de ``BudgetSimulatorV45``.
"""
from .._logging import _log_debug


class ExpendituresMixin:
    """Bloc moteur — Dépenses publiques (compounding par catégorie + plafonds)."""

    def calculate_expenditures(self, gdp: float, inflation: float, unemployment: float,
                              year: int, output_gap: float) -> float:
        """Calcul des dépenses avec croissance maîtrisée et effets spécifiques"""

        base_spending_2025 = sum(self.spending_categories_base.values())

        if year == 1:
            # Pattern "bridging year" : Y1 (2025→2026) utilise une formule fermée d'amorçage
            # plutôt que le compounding par catégorie. _spending_factors restent à 1.0 après Y1
            # car ils servent uniquement aux années >=2 ; les initialiser ici créerait un double-comptage Y2.
            # DÉGEL (recalibrage 2026-06) : 2026 suit le taux de croisière réel (amorcage_depenses_y1
            # ≈ tendanciel) + l'inflation PLEINE — ex- inflation*0.5, qui sous-indexait 2026 et fabriquait
            # une austérité fantôme non votée (plus serrée que le PLF). 2026 = année tendancielle normale.
            return base_spending_2025 * (1 + self.base_params['amorcage_depenses_y1'] + inflation)

        # Debug pour années clés
        debug_this_year = year in [2, 5, 10]
        if debug_this_year:
            _log_debug(self.debug_logs, f"\n📊 ANALYSE DÉTAILLÉE DÉPENSES - ANNÉE {year} (an {year+2024}):")

        total_spending_real = 0

        for category, base_amount in self.spending_categories_base.items():
            # CAS SPÉCIAL : Chômage varie directement avec le taux
            if category == 'chomage':
                unemployment_ratio = unemployment / self.base_params['chomage_base']
                real_amount = base_amount * unemployment_ratio
                total_spending_real += real_amount
                if debug_this_year:
                    _log_debug(self.debug_logs, "  Chômage DEBUG:")
                    _log_debug(self.debug_logs, f"    unemployment passé = {unemployment:.4f}")
                    _log_debug(self.debug_logs, f"    chomage_base = {self.base_params['chomage_base']:.4f}")
                    _log_debug(self.debug_logs, f"    ratio = {unemployment_ratio:.4f}")
                    _log_debug(self.debug_logs, f"    base_amount = {base_amount:.1f}")
                    _log_debug(self.debug_logs, f"    montant = {real_amount:.1f}")
                    _log_debug(self.debug_logs, f"  Chômage: ratio={unemployment_ratio:.2f}, montant={real_amount:.0f}")
                continue

            # Taux de croissance de base
            real_growth = self.spending_growth_rates.get(category, 0)

            # AJUSTEMENTS SPÉCIFIQUES PAR CATÉGORIE
            if category == 'retraites' and year >= 5:
                real_growth += 0.002  # Vieillissement progressif

            elif category == 'sante':
                if year >= 3:
                    # Effet vieillissement progressif
                    aging_effect = 0.001 * min(year - 2, 5)
                    real_growth += aging_effect

            elif category == 'dependance' and year >= 5:
                real_growth += 0.003  # Boom des 85+ ans

            elif category == 'collectivites' and year >= 5:
                # Ne peut pas rester gelé éternellement
                real_growth = max(real_growth, 0.001)

            elif category == 'transition_eco':
                # Fort au début, ralentit ensuite
                if year <= 5:
                    real_growth *= 1.5
                else:
                    real_growth *= 0.5

            # AJUSTEMENT CYCLIQUE (neutre en régime normal)
            # Ancien x0.98 créait une austérité fantôme de ~2%/an sur les dépenses
            if output_gap < -0.02:
                real_growth *= 0.90  # Récession : dépenses comprimées
            elif output_gap > 0.02:
                real_growth *= 1.02  # Surchauffe : dépenses en hausse

            # COMPOUNDING ITÉRATIF : utilise le taux de l'année courante uniquement,
            # pas rétroactif. Évite le biais où un ajustement cyclique d'une année
            # est appliqué rétroactivement sur toutes les années passées.
            self._spending_factors[category] *= (1 + real_growth)
            self._spending_factors[category] = max(self._spending_factors[category], 0.5)

            real_amount = base_amount * self._spending_factors[category]
            total_spending_real += real_amount

            # Debug pour catégories importantes
            if debug_this_year and real_amount > 50:
                _log_debug(self.debug_logs, f"  {category}: {base_amount:.0f} → {real_amount:.0f} (x{self._spending_factors[category]:.2f})")

        # Conversion réel → nominal via déflateur cumulé (pas via PIB pour éviter
        # le double levier : dépenses croissent selon leur taux propre + inflation,
        # mais PAS proportionnellement à la croissance réelle du PIB)
        nominal_spending = total_spending_real * self.deflateur_cumule

        # Plafonds en ratio PIB (garde-fous macro)
        spending_ratio = nominal_spending / gdp if gdp > 0 else 0.55
        if spending_ratio > 0.60:
            nominal_spending = 0.60 * gdp
        elif spending_ratio < 0.45:
            nominal_spending = 0.45 * gdp

        if debug_this_year:
            _log_debug(self.debug_logs, f"  TOTAL: {nominal_spending:.1f} Md€ ({spending_ratio*100:.1f}% PIB)")

        _log_debug(self.debug_logs, f"Y{year}: Dépenses {nominal_spending:.1f} Md€")
        return nominal_spending
