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
        """Taux marginal des émissions nouvelles = ancre zone euro + spread France.

        v0.6.0 (audit externe 08/2026) : ré-ancrage sur le marché observé —
        3,47 % à 117,6 % de dette (AFT 08/2026) contre 1,99 % pour l'ancienne
        courbe, pentes de spread sourcées (Laubach, Pamies, ACL — cf.
        constants.py), prime d'effort continue et symétrique. Supprimés, avec
        source : remise BCE inconditionnelle (le TPI exige de ne PAS être en
        procédure de déficit excessif — la France y est, BCE 21/07/2022),
        terme calendaire ``year > 5`` (aucune source), falaise +100 pb (vécu
        France 2024-2026 : +21 pb). Monotone STRICT en dette jusqu'au plafond
        de stress (8 %), vérifié par test-propriété.
        Le paramètre ``year`` n'entre plus dans le calcul (signature conservée
        pour les appels existants).
        """
        from ..constants import (
            ANCRE_TAUX_ZONE_EURO, SPREAD_ANCRAGE, SPREAD_ANCRAGE_DETTE,
            SPREAD_PENTE_SOUS_90, SPREAD_PENTE_90_120, SPREAD_PENTE_120_150,
            SPREAD_PENTE_SUP_150, TAUX_PLAFOND_ABSOLU,
            PRIME_TAUX_PAR_PT_EFFORT, PRIME_TAUX_SEUIL_DETTE,
            PRIME_TAUX_PENTE_DETTE, PRIME_TAUX_CAP_MALUS, PRIME_TAUX_CAP_BONUS,
        )

        def _pts(x: float) -> float:
            """Ratio de dette → points de PIB (1 pt = 0.01 de ratio)."""
            return x * 100.0

        # --- Spread France : segments intégrés depuis le point d'ancrage AFT ---
        # spread(90 %) dérivé de l'ancre : 82 pb − 3 pb × (117,6 − 90) ≈ −0,8 pb
        spread_90 = SPREAD_ANCRAGE - SPREAD_PENTE_90_120 * (_pts(SPREAD_ANCRAGE_DETTE) - 90.0)
        spread_120 = spread_90 + SPREAD_PENTE_90_120 * 30.0
        spread_150 = spread_120 + SPREAD_PENTE_120_150 * 30.0

        if debt_ratio < 0.90:
            spread = spread_90 - SPREAD_PENTE_SOUS_90 * (90.0 - _pts(debt_ratio))
        elif debt_ratio < 1.20:
            spread = spread_90 + SPREAD_PENTE_90_120 * (_pts(debt_ratio) - 90.0)
        elif debt_ratio < 1.50:
            spread = spread_120 + SPREAD_PENTE_120_150 * (_pts(debt_ratio) - 120.0)
        else:
            spread = spread_150 + SPREAD_PENTE_SUP_150 * (_pts(debt_ratio) - 150.0)
            _log_debug(self.debug_logs, f"Y{year}: ⚠️ SPIRALE DETTE (spread {spread*100:.2f} pt, extrapolation >150%)")

        rate = ANCRE_TAUX_ZONE_EURO + spread

        # --- Prime d'effort : 20 pb/pt de PIB, amplifiée par la dette > 90 % ---
        # effort_budgetaire est une fraction du PIB (+0.01 = consolidation 1 pt).
        if effort_budgetaire != 0:
            facteur_dette = 1.0 + PRIME_TAUX_PENTE_DETTE * max(0.0, debt_ratio - PRIME_TAUX_SEUIL_DETTE)
            prime = -PRIME_TAUX_PAR_PT_EFFORT * (effort_budgetaire * 100.0) * facteur_dette
            prime = max(-PRIME_TAUX_CAP_BONUS, min(PRIME_TAUX_CAP_MALUS, prime))
            rate += prime
            _log_debug(self.debug_logs, f"Y{year}: Prime d'effort {prime*100:+.2f} pt (effort {effort_budgetaire*100:+.2f} pt PIB)")

        return min(rate, TAUX_PLAFOND_ABSOLU)

    def calculate_interest_payment(self, debt_total: float, marginal_rate: float) -> Tuple[float, float]:
        """
        Calcule charge d'intérêts avec renouvellement progressif.
        Maturité moyenne dette française : 8 ans (source: AFT 2024).

        v0.6.0 — repricing LINÉAIRE approximé (revue adverse 24/08) : le taux
        géométrique 1/maturité donnait une demi-vie de repricing ~7 ans, alors
        qu'un portefeuille amorti linéairement de maturité moyenne 8 ans
        reprice la moitié de son stock en maturité/2 = 4 ans. Taux équivalent :
        k = 1 − 0,5^(2/maturité) ≈ 0,159. C'est ce profil qu'utilise la
        mission IGF 07/2026 (taux apparent 2,2 → 3,1 % en 5 ans, Tableau 6) —
        vérifié par le corridor tests/test_calibration_mission_v060.py.
        """
        renewal_rate = 1 - 0.5 ** (2 / self.debt_structure['maturite_moyenne'])

        debt_renewed = debt_total * renewal_rate
        debt_old = debt_total * (1 - renewal_rate)

        interest_new = debt_renewed * marginal_rate
        interest_old = debt_old * self.debt_structure['taux_moyen']
        total_interest = interest_new + interest_old

        self.debt_structure['taux_moyen'] = total_interest / debt_total if debt_total > 0 else marginal_rate

        return total_interest, self.debt_structure['taux_moyen']
