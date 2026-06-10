"""Bloc moteur — Inflation (courbe de Phillips augmentée).

Méthode couverte :
- ``calculate_inflation`` : inflation de l'année à partir de l'état
  économique (output gap, unemployment gap, impact TVA, effort
  budgétaire), avec rappel de politique monétaire BCE et bruit
  stochastique.

Forme retenue : Phillips augmentée en ``output_gap`` uniquement (pas
de terme ``unemployment_gap`` direct, déjà corrélé via Okun → évite le
double-comptage). Coefficient 0,35 recalibré (cf commentaire inline).

État partagé ``self.inflation_precedente`` :
- Lu en entrée (terme d'inertie ``inflation_inertia *
  inflation_precedente``) puis réécrit par la DERNIÈRE instruction de
  ``calculate_inflation`` (``self.inflation_precedente = inflation``).
- Persistance inter-années N→N+1 : portée par ``simulate()`` (qui
  réaffecte ``inflation_precedente`` en fin de boucle annuelle), PAS
  par cette écriture in-méthode. Init / reset relèvent de l'hôte
  ``BudgetSimulatorV45``.
- Cette écriture in-méthode est conservée VOLONTAIREMENT bien qu'elle
  n'ait plus d'effet observable sur ``simulate()`` : elle neutralisait
  jadis un garde d'ajustement d'élasticité recettes (placé juste après
  l'appel), garde **SUPPRIMÉ en Phase 2 (2026-05-16, option B)** car
  mort par construction ET en double-comptage avec l'élasticité au PIB
  nominal de ``calculate_revenues``. Maintenue pour cohérence
  intra-méthode (inertie correcte si ``calculate_inflation`` était
  appelée 2× dans la même boucle). Détail/chiffrage : tombstone dans
  ``engine/orchestrator.py`` et ``docs/REFACTOR_SPLIT_PLAN.md``.

Lecture seule : ``self.economic_coeffs['inflation_inertia']``.
Sink de logs : ``self.debug_logs`` via ``_log_debug``.
Tous attributs d'instance de ``BudgetSimulatorV45``.
"""
from typing import Dict

import numpy as np

from .._logging import _log_debug
from ..constants import BCE_CIBLE_INFLATION, INFLATION_STRUCTURELLE


class InflationMixin:
    """Bloc moteur — Inflation (courbe de Phillips augmentée)."""

    def calculate_inflation(self, year: int, economic_state: Dict) -> float:
        """Courbe de Phillips augmentée"""
        output_gap = economic_state['output_gap']
        unemployment_gap = economic_state['unemployment_gap']
        tva_impact = economic_state.get('tva_impact', 0)
        effort_budgetaire = economic_state.get('effort_budgetaire', 0)

        # Phillips augmentée (forme output_gap uniquement, évite le double-comptage
        # output_gap/unemployment_gap corrélés via Okun)
        # Coefficient 0.35 recalibré : ancienne sensibilité totale ≈ 0.08 + 0.10/0.35 ≈ 0.37
        #
        # Intercept × (1 − inertie) — refonte 2026-06 : dans un AR(1)
        # i_t = c + ρ·i_{t-1}, le point fixe est c/(1−ρ), PAS c. L'ancien code
        # posait c = INFLATION_STRUCTURELLE (1,5 %) avec ρ = 0,5, soit un
        # attracteur caché à 3,0 % que le rappel BCE bridait en équilibre
        # permanent à 2,33 % (« politique restrictive » chaque année du statu
        # quo). La forme correcte (1−ρ)·π* + ρ·i_{t-1} fait de
        # INFLATION_STRUCTURELLE le point fixe RÉEL (1,5 %) : l'inflation
        # converge vers la tendancielle et la BCE redevient un garde-fou de
        # surchauffe, conformément à l'intention de calibration (décision PO
        # 2026-05-18 Option C, jamais traduite correctement en formule).
        inertia = self.economic_coeffs['inflation_inertia']
        inflation = (
            (1 - inertia) * INFLATION_STRUCTURELLE +
            inertia * self.inflation_precedente +
            0.35 * output_gap
        )

        if abs(effort_budgetaire) > 0.001:
            if effort_budgetaire > 0:
                inflation_impact = -0.12 * effort_budgetaire
                inflation += inflation_impact
                if abs(inflation_impact) > 0.002:
                    _log_debug(self.debug_logs, f"Y{year}: Impact déflationniste: {inflation_impact*100:.2f}%")
            else:
                inflation_impact = 0.08 * abs(effort_budgetaire)
                inflation += inflation_impact
                if abs(inflation_impact) > 0.002:
                    _log_debug(self.debug_logs, f"Y{year}: Impact inflationniste: {inflation_impact*100:.2f}%")

        if output_gap < -0.025 and unemployment_gap > 0.01:
            inflation *= 0.80
            _log_debug(self.debug_logs, f"Y{year}: Pressions déflationnistes")
        elif output_gap > 0.020 and unemployment_gap < -0.01:
            inflation = min(inflation * 1.08, 0.030)
            _log_debug(self.debug_logs, f"Y{year}: Tensions inflationnistes")

        # Pass-through TVA — gate temporel UNIQUE (l'orchestrateur transmet la
        # valeur sans condition d'année). Depuis la refonte 2026-06, l'inflation
        # de t est calculée AVANT les mesures de t : le tva_impact vient des
        # impacts de t−1, donc le pass-through frappe à year == 2 (l'année qui
        # suit l'entrée en vigueur des mesures, toutes actives dès Y1 dans ce
        # moteur — POLICY_START_YEAR). One-shot délibéré : pas de re-pass-through
        # les années suivantes (la persistance passe par l'inertie ρ = 0,5).
        if year == 2 and tva_impact > 0.003:
            tva_pass_through = min(tva_impact * 0.3, 0.002)
            inflation += tva_pass_through
            _log_debug(self.debug_logs, f"Y{year}: Impact TVA +{tva_pass_through*100:.2f}%")

        # Rappel BCE — garde-fou de SURCHAUFFE (refonte 2026-06) : seuil abaissé
        # de 2,3 % à 2,0 % (cible BCE) pour qu'il CONTIENNE l'inflation au-dessus
        # de la cible au lieu de servir de thermostat permanent (l'ancien couple
        # attracteur 3 % / seuil 2,3 % stabilisait à 2,33 % à perpétuité).
        # En statu quo (point fixe 1,5 %), il ne se déclenche plus.
        if inflation > BCE_CIBLE_INFLATION:
            inflation = 0.50 * inflation + 0.50 * BCE_CIBLE_INFLATION
            _log_debug(self.debug_logs, f"Y{year}: Politique monétaire restrictive")
        elif inflation < 0.008:
            # Plancher accommodant : tiré vers la TENDANCIELLE (et non plus 2 %,
            # qui contredisait le point fixe du régime).
            inflation = 0.70 * inflation + 0.30 * INFLATION_STRUCTURELLE
            _log_debug(self.debug_logs, f"Y{year}: Politique monétaire accommodante")

        inflation += np.random.normal(0, 0.0005)
        inflation = np.clip(inflation, -0.003, 0.030)

        self.inflation_precedente = inflation
        return inflation
