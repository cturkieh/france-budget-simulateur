"""Bloc moteur — Charge de la dette (taux d'intérêt + intérêts payés).

Méthodes couvertes :
- ``calculate_interest_rate`` : taux marginal de l'année selon le ratio
  dette/PIB (progression monotone par paliers, spirale > 150 %,
  intervention BCE, prime de risque selon l'effort budgétaire), plafonné
  à 5 % (cohérent BCE TPI). Purement fonctionnelle (lecture seule
  ``self.base_params['taux_interet_base']``, logs ``self.debug_logs``).
- ``calculate_interest_payment`` : charge d'intérêts avec renouvellement
  progressif de la dette (maturité moyenne 8 ans, source AFT 2024).

État partagé ``self.debt_structure['taux_moyen']`` — invariant
load-bearing :
- ``calculate_interest_payment`` en est PRODUCTEUR et CONSOMMATEUR : il
  lit le taux moyen courant pour valoriser la portion de dette NON
  renouvelée, puis réécrit le taux moyen mélangé (neuf + ancien).
  C'est le SEUL producteur de cet état dans la boucle en régime établi :
  l'écriture in-méthode porte réellement la persistance N→N+1 (comme
  ``RevenuesMixin``, ``simulate()`` ne re-persiste PAS — contrairement
  à ``InflationMixin``).
- Init / reset (``debt_structure`` créé dans ``__init__``, ``taux_moyen``
  réamorcé à ``taux_interet_base`` dans ``_reset_state``) relèvent de
  l'hôte ``BudgetSimulatorV45``, hors périmètre du split (non touché).
- ``self.debt_structure['maturite_moyenne']`` est lu en lecture seule.

Garde existant : ``total_interest / debt_total if debt_total > 0 else
marginal_rate``. Pour ``debt_total == 0`` (dette éteinte) c'est un
anti-division-zéro sain, pas un fallback masquant : sans dette, taux
moyen = taux marginal courant (cohérent avec le réamorçage
``_reset_state``). Le garde ``> 0`` route aussi ``debt_total < 0`` vers
la même branche, mais ``debt < 0`` est **INATTEIGNABLE dans les bornes
du modèle** (re-analyse adverse 2026-05-16) : ``debt`` part de ~3461 Md€,
le désendettement est borné par le plafond de mesures 10 % PIB (FMI
2010) + la charge d'intérêts toujours soustraite ; plancher empirique
mesuré = 2238 Md€ sur 8 scénarios + 1 scénario austérité maximale (90
trajectoires-années, jamais ≤ 0). Branche défensive inerte, MÊME statut
que le garde ``gdp <= 0`` de ``ExpendituresMixin`` (variable strictement
positive par construction) — **aucune dette Phase 2**, documentation
seule. Préservé byte-for-byte.

NB : la constante de classe ``SUPPLY_EFFECTS`` qui suit physiquement
``calculate_interest_payment`` dans le monolithe N'appartient PAS à ce
bloc (effet d'offre structurel consommé par ``calculate_growth``) — elle
reste sur ``BudgetSimulatorV45`` et n'est volontairement pas migrée ici.

Sink de logs : ``self.debug_logs`` via ``_log_debug``.
Tous attributs d'instance de ``BudgetSimulatorV45``.
"""
from typing import Tuple

from .._logging import _log_debug


class DebtMixin:
    """Bloc moteur — Charge de la dette (taux d'intérêt + intérêts payés)."""

    def calculate_interest_rate(self, debt_ratio: float, year: int, effort_budgetaire: float = 0) -> float:
        """Taux d'intérêt avec progression CONTINUE - Calibré sur expérience zone euro 2010-2025"""
        base_rate = self.base_params['taux_interet_base']  # 0.019

        # Progression MONOTONE STRICTE
        if debt_ratio < 0.6:
            # Sous Maastricht : prime de confiance
            rate = 0.015
        elif debt_ratio < 0.9:
            # 60-90% : montée progressive
            rate = 0.015 + 0.004 * (debt_ratio - 0.6) / 0.3
            # À 90% : rate = 0.019
        elif debt_ratio < 1.0:
            # 90-100% : stabilisation autour du taux de base
            rate = base_rate
        elif debt_ratio < 1.20:
            # 100-120% : zone stable avec légère hausse
            rate = base_rate + 0.005 * (debt_ratio - 1.0)
            # À 120% : rate = 0.020
        elif debt_ratio < 1.50:  # ← ABAISSÉ de 1.65
            # 120-150% : tension croissante
            rate = base_rate + 0.001 + 0.010 * (debt_ratio - 1.20)
            # À 150% : rate = 0.023
        else:
            # >150% : SPIRALE PROGRESSIVE
            # Phase 1 (150-170%) : pression modérée
            rate = base_rate + 0.0041 + 0.007 * (debt_ratio - 1.50)

            if debt_ratio > 1.70:  # Phase 2 : spirale sévère
                rate += 0.015 * (debt_ratio - 1.70)
                if year > 5:
                    rate += 0.003 * (year - 5)
                _log_debug(self.debug_logs, f"Y{year}: 🚨 CRISE DE CONFIANCE")
            else:
                _log_debug(self.debug_logs, f"Y{year}: ⚠️ SPIRALE DETTE")

        # Intervention BCE si dette > 150% (au lieu de 165%)
        if debt_ratio > 1.50:
            rate -= 0.005
            _log_debug(self.debug_logs, f"Y{year}: Intervention BCE (-0.5%)")

        # Prime de risque selon politique budgétaire
        if debt_ratio > 1.0:
            if effort_budgetaire < -0.01:  # Expansion avec dette élevée
                prime_politique = abs(effort_budgetaire) * 0.15
                rate += prime_politique
                _log_debug(self.debug_logs, f"Y{year}: Prime risque +{prime_politique*100:.2f}%")

                if debt_ratio > 1.2 and effort_budgetaire < -0.015:
                    rate += 0.01
                    _log_debug(self.debug_logs, f"Y{year}: 🚨 ALERTE SOUTENABILITÉ CRITIQUE")

            elif effort_budgetaire > 0.01:  # Consolidation
                prime_credibilite = -min(0.005, effort_budgetaire * 0.10)
                rate += prime_credibilite
                _log_debug(self.debug_logs, f"Y{year}: Bonus crédibilité {prime_credibilite*100:.2f}%")

        # Plafond taux d'intérêt : 5% cohérent avec mécanisme BCE TPI
        # (ancien plafond 3.5% empêchait tout scénario de stress dette,
        #  et le bloc non-linéaire >5% était du dead code car plafonné à 3.5%)
        return min(rate, 0.050)

    def calculate_interest_payment(self, debt_total: float, marginal_rate: float) -> Tuple[float, float]:
        """
        Calcule charge d'intérêts avec renouvellement progressif.
        Maturité moyenne dette française : 8 ans (source: AFT 2024)
        """
        renewal_rate = 1 / self.debt_structure['maturite_moyenne']

        debt_renewed = debt_total * renewal_rate
        debt_old = debt_total * (1 - renewal_rate)

        interest_new = debt_renewed * marginal_rate
        interest_old = debt_old * self.debt_structure['taux_moyen']
        total_interest = interest_new + interest_old

        self.debt_structure['taux_moyen'] = total_interest / debt_total if debt_total > 0 else marginal_rate

        return total_interest, self.debt_structure['taux_moyen']
