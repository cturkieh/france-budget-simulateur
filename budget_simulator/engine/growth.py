"""Bloc moteur — Croissance (PIB potentiel + multiplicateur keynésien).

Méthodes couvertes :
- ``calculate_growth`` : croissance réelle de l'année. Croissance
  potentielle + écart de chômage + debt drag, puis multiplicateur
  keynésien à profils temporels différenciés (impulsion stockée au
  changement de mesures, decay pondéré INVEST/TRANSFERS/TAXES), effet
  confiance, cicatrice austérité, stabilisateurs, crowding-out, bruit
  stochastique, clamp [-3,5 % ; +2,5 %].
- ``update_potential_growth`` : ajuste la croissance POTENTIELLE
  (hystérèse conjoncturelle + effet d'offre structurel ``SUPPLY_EFFECTS``,
  cap +0,20 pt).

Constante de classe ``SUPPLY_EFFECTS`` : portée par ce mixin (et non
plus par ``BudgetSimulatorV45``). Elle était délibérément maintenue sur
l'hôte pendant les splits ``DebtMixin`` / ``ExpendituresMixin`` parce
qu'elle « appartient à growth » ; son unique consommateur est
``update_potential_growth`` — elle migre donc ici avec lui. Les autres
constantes de classe utilisées par ``calculate_growth``
(``DECAY_PROFILE_*``, ``INVESTMENT_FLOW_MEASURES``,
``TRANSFER_MEASURES``) restent sur ``BudgetSimulatorV45`` (config
niveau simulateur, résolues via ``self`` par le MRO) — non migrées.

Paire PRODUCTEUR → CONSOMMATEUR inter-méthodes (invariant load-bearing) :
- ``update_potential_growth`` (appelée APRÈS ``calculate_growth`` dans
  la boucle de ``simulate()``) MUTE ``self.base_params
  ['croissance_potentielle']`` EN PLACE (hystérèse) et réécrit
  ``self._potential_growth_bonus``. ``calculate_growth`` de l'année
  N+1 consomme ces deux valeurs (``croissance = croissance_potentielle
  + _potential_growth_bonus``). Ce sont les SEULS producteurs dans la
  boucle ; ``simulate()`` ne fait que LIRE ``_fiscal_impulses`` /
  ``_potential_growth_bonus`` pour le reporting (jamais réécrire).
- Conséquence non évidente : ``base_params['croissance_potentielle']``
  N'EST PAS immutable — il dérive année après année. L'hôte
  ``_reset_state`` DOIT le restaurer à la valeur utilisateur entre deux
  simulations (il le fait). Ne pas supposer ``base_params`` constant.
- États accumulateurs cross-année mutés par ces méthodes :
  ``_fiscal_impulses`` (dict {year: (effort, mult, profil)}, dédup via
  ``_last_measures_hash``), ``_supply_years`` /
  ``_supply_bonus_by_key`` (dépréciation progressive de l'offre).
  Tous initialisés / réinitialisés par l'hôte (``__init__`` /
  ``_reset_state``), hors périmètre du split (non touché).

Catch large du bloc effet d'offre — GARDE DÉFENSIF INERTE (re-analyse
adverse 2026-05-16) : le ``except Exception`` de
``update_potential_growth`` est **inatteignable en run normal**. Preuve :
aucune opération du bloc ne peut lever (``_get_default_values`` =
return dict littéral pur ; ``.get`` sur dict ; ``isinstance`` neutralise
les types tordus avant arithmétique ; ``np.log2(1+delta)`` avec
``delta>0.1`` garanti ⇒ argument > 1.1, jamais d'exception). Le seul
vecteur théorique (valeur non-dict dans ``self.mesures``) crashe
**bruyamment en amont** dans ``apply_measures`` (en 2026 via
``detect_active_measures``/``params.items()`` ; les autres années via
le ``try`` per-mesure → ``logger.error`` + ``HANDLER_FAILED_KEY``),
AVANT que ce bloc soit atteint — 8 scénarios + 7 adversariaux :
0 déclenchement. Sévérité réelle : LOW / dette défensive,
PAS un silent-failure atteignable. Néanmoins, par conformité à la règle
projet « zéro catch silencieux » et pour qu'un futur refactor qui le
rendrait atteignable ne dégrade pas la croissance potentielle en
silence, le ``except`` émet désormais ``logger.error(exc_info=True)``
(auto-capté Sentry via LoggingIntegration, no-op sans DSN), aligné sur
``apply_measures``. ``_potential_growth_bonus = 0.0`` conservé : le bloc
ne s'exécutant jamais sur input atteignable, golden master byte-identique
(vérifié). Item Phase 2 « catch silencieux » CLÔTURÉ par cette
instrumentation (cf ``docs/REFACTOR_SPLIT_PLAN.md``).

Helpers hôte via MRO : ``self._get_active_measures_hash()``,
``self._get_default_values()``. Lecture seule : ``self.economic_coeffs``,
``self.multipliers`` (instance ``FiscalMultipliers``), ``self.mesures``.
Sink de logs : ``self.debug_logs`` via ``_log_debug``.
Tous attributs d'instance de ``BudgetSimulatorV45``.
"""
import logging
from typing import Dict

import numpy as np

from .._logging import _log_debug

logger = logging.getLogger(__name__)


class GrowthMixin:
    """Bloc moteur — Croissance (PIB potentiel + multiplicateur keynésien)."""

    def calculate_growth(self, year: int, economic_state: Dict) -> float:
        output_gap = economic_state['output_gap']
        unemployment_gap = economic_state['unemployment_gap']
        effort_budgetaire = economic_state['effort_budgetaire']
        part_depenses = economic_state['part_depenses']
        debt_ratio = economic_state['debt_ratio']
        unemployment = economic_state.get('unemployment', 0.076)
        deficit_ratio = economic_state.get('deficit_ratio', -0.054)

        croissance = self.base_params['croissance_potentielle'] + self._potential_growth_bonus
        croissance += self.economic_coeffs['chomage_gap_weight'] * unemployment_gap

        if debt_ratio > 0.9:
            debt_impact = self.economic_coeffs['debt_drag'] * (debt_ratio - 0.9)
            croissance += debt_impact
            _log_debug(self.debug_logs, f"Y{year}: Debt drag {debt_impact*100:.2f}%")

        # === MULTIPLICATEUR KEYNÉSIEN AVEC PROFILS TEMPORELS DIFFÉRENCIÉS ===
        # Une impulsion est stockée quand les mesures changent (hash change).
        # Le profil de décroissance dépend de la composition des mesures :
        # - INVEST : pic en Y2, persistance longue (Bom & Ligthart 2014, FMI 2020)
        # - TRANSFERS : front-loaded, decay rapide (Ramey 2019, FMI 2014)
        # - TAXES : profil intermédiaire (Blanchard & Leigh 2013)
        # Sommes normalisées <= 2.0

        if abs(effort_budgetaire) > 0.001:
            current_hash = self._get_active_measures_hash()

            if current_hash != self._last_measures_hash:
                effort_type = 'consolidation' if effort_budgetaire > 0 else 'expansion'
                eco_state = {
                    'output_gap': output_gap,
                    'debt_ratio': debt_ratio,
                    'unemployment_gap': unemployment_gap,
                    'interest_rate': economic_state.get('interest_rate', 0.023)
                }

                # WEIGHTED BLEND : multiplicateur + profil decay moyens pondérés par mesure
                weighted_mult = 0.0
                total_weight = 0.0
                # Poids par type pour le blend du profil decay
                weight_invest = 0.0
                weight_transfer = 0.0
                weight_tax = 0.0

                for m_id, m_impact in self._last_impacts.items():
                    if not isinstance(m_impact, dict) or 'erreur' in m_impact:
                        continue
                    m_dep = abs(m_impact.get('depenses', 0))
                    m_rev = abs(m_impact.get('recettes', 0))
                    m_effort = m_dep + m_rev
                    if m_effort < 0.01:
                        continue

                    m_total = m_dep + m_rev
                    m_is_inv = m_id in self.INVESTMENT_FLOW_MEASURES
                    composition_m = {
                        'depenses': m_dep / m_total if m_total > 0 else 0,
                        'recettes': m_rev / m_total if m_total > 0 else 0,
                        'investissement': m_dep / m_total if m_is_inv else 0
                    }
                    m_fiscal = m_impact.get('recettes', 0) - m_impact.get('depenses', 0)
                    m_effort_type = 'consolidation' if m_fiscal > 0 else 'expansion'

                    mult_m = self.multipliers.get_multiplier(
                        m_effort_type, composition_m, eco_state, year, m_id
                    )
                    weighted_mult += mult_m * m_effort
                    total_weight += m_effort

                    # Classifier pour le profil decay
                    if m_id in self.INVESTMENT_FLOW_MEASURES:
                        weight_invest += m_effort
                    elif m_id in self.TRANSFER_MEASURES:
                        weight_transfer += m_effort
                    else:
                        weight_tax += m_effort

                if total_weight > 0:
                    multiplicateur = weighted_mult / total_weight
                else:
                    composition_fb = {
                        'depenses': part_depenses,
                        'recettes': 1 - part_depenses,
                        'investissement': economic_state.get('part_investissement', 0)
                    }
                    multiplicateur = self.multipliers.get_multiplier(
                        effort_type, composition_fb, eco_state, year
                    )

                # Blend pondéré du profil decay selon la composition des mesures
                if total_weight > 0:
                    profile_len = len(self.DECAY_PROFILE_TAXES)
                    blended_profile = tuple(
                        (weight_invest * self.DECAY_PROFILE_INVEST[i] +
                         weight_transfer * self.DECAY_PROFILE_TRANSFERS[i] +
                         weight_tax * self.DECAY_PROFILE_TAXES[i]) / total_weight
                        for i in range(profile_len)
                    )
                else:
                    blended_profile = self.DECAY_PROFILE_TAXES

                self._fiscal_impulses[year] = (effort_budgetaire, multiplicateur, blended_profile)
                self._last_measures_hash = current_hash

                profile_type = 'INVEST' if weight_invest > max(weight_transfer, weight_tax) else \
                               'TRANSFER' if weight_transfer > weight_tax else 'TAXES'
                _log_debug(self.debug_logs,
                    f"Y{year}: [IMPULSION] {effort_type.capitalize()} "
                    f"{abs(effort_budgetaire)*100:.2f}% PIB, mult={multiplicateur:.2f}, "
                    f"profil={profile_type} (inv={weight_invest:.0f} trans={weight_transfer:.0f} tax={weight_tax:.0f})")

            # Sommer les effets décroissants de toutes les impulsions passées
            total_multiplier_effect = 0
            for impulse_year, impulse_data in self._fiscal_impulses.items():
                impulse_effort, impulse_mult = impulse_data[0], impulse_data[1]
                # _fiscal_impulses n'est écrit qu'en un point (3-tuple
                # (effort, mult, blended_profile)) → impulse_data[2] toujours
                # présent ; pas d'ancien fallback self.DECAY_PROFILE (mort).
                decay_profile = impulse_data[2]
                age = year - impulse_year
                if age < 0 or age >= len(decay_profile):
                    continue
                decay = decay_profile[age]
                raw_effort = abs(impulse_effort)
                capped_effort = min(raw_effort, 0.02)
                if raw_effort > 0.02 and age == 0:
                    _log_debug(self.debug_logs,
                        f"Y{year}: Effort plafonné: {raw_effort*100:.2f}% → 2.00% PIB")
                effect = impulse_mult * capped_effort * decay
                total_multiplier_effect += effect

            croissance += total_multiplier_effect

            if total_multiplier_effect != 0:
                _log_debug(self.debug_logs,
                    f"Y{year}: Effet multiplicateur total = {total_multiplier_effect*100:.2f}% "
                    f"({len(self._fiscal_impulses)} impulsion(s) actives)")
        else:
            _log_debug(self.debug_logs,
                f"Y{year}: Aucun effort budgétaire → pas de nouvelle impulsion")

        # EFFET CONFIANCE DÉGRESSIF (Alesina & Ardagna 2010)
        # Caps réduits : l'évidence empirique d'Alesina est contestée (IMF 2012, Guajardo et al. 2014)
        # et ne justifie pas un boost >0.2% même dans les conditions les plus favorables.
        if effort_budgetaire > 0.015 and part_depenses > 0.5 and debt_ratio > 1.1:
            if year <= 2:
                multiplier, cap = 0.10, 0.002
            elif year <= 4:
                multiplier, cap = 0.08, 0.0015
            else:
                multiplier, cap = 0.02, 0.0004
            effet_confiance = min(cap, multiplier * effort_budgetaire)
            croissance += effet_confiance
            _log_debug(self.debug_logs,
                f"Y{year}: Effet confiance +{effet_confiance*100:.2f}% "
                f"(dégressif, année {year})"
            )

        # CICATRICE AUSTÉRITÉ (DeLong & Summers 2012, Fatas & Summers 2018)
        # Seule l'austérité TRÈS sévère (>3% PIB) cause des dommages structurels.
        # Les réformes graduelles (retraites, santé, fusion) ne déclenchent pas
        # de cicatrice car elles améliorent l'offre à long terme.
        # Seuil relevé à 3% PIB et coefficient réduit pour éviter le piège
        # où l'utilisateur ne peut trouver aucune solution viable.
        if effort_budgetaire > 0.03:
            severity = effort_budgetaire - 0.03
            scarring = -0.10 * severity  # Pas de duration_factor (simplifié)
            scarring = max(scarring, -0.003)  # Cap à -0.3% max par an
            croissance += scarring
            _log_debug(self.debug_logs,
                f"Y{year}: Cicatrice austérité {scarring*100:.2f}% "
                f"(sévérité {severity*100:.1f}%)"
            )

        # Stabilisateurs automatiques
        if unemployment > 0.09:
            croissance += 0.005
            _log_debug(self.debug_logs, f"Y{year}: Stabilisateur chômage")

        if deficit_ratio < -0.04:
            croissance += 0.001
            _log_debug(self.debug_logs, f"Y{year}: Stabilisateur déficit")

        if effort_budgetaire < 0 and debt_ratio > 1.0:
            # Crowding-out renforcé pour dépenses non-productives :
            # L'investissement productif (éducation, R&D, infra) génère des retours → faible crowding.
            # Les transferts (SMIC, aides) ne créent pas de capacité productive → fort crowding.
            # Le crowding-out capture : hausse taux d'intérêt, éviction investissement privé,
            # perte compétitivité coût, inflation salariale sans productivité.
            part_inv = economic_state.get('part_investissement', 0)
            crowding_intensity = 0.002 + (1 - part_inv) * 0.006  # 0.002 invest pur → 0.008 transferts purs
            crowding_effect = crowding_intensity * effort_budgetaire
            croissance += crowding_effect
            _log_debug(self.debug_logs,
                f"Y{year}: Crowding-out {crowding_effect*100:.3f}% "
                f"(intensité {crowding_intensity:.3f}, inv={part_inv:.0%})")

        croissance += np.random.normal(0, 0.003)
        croissance = np.clip(croissance, -0.035, 0.025)
        if croissance < -0.025:
            _log_debug(self.debug_logs, f"Y{year}: Récession profonde")
        elif croissance > 0.024:
            _log_debug(self.debug_logs, f"Y{year}: Surchauffe")

        return croissance

    # Effet d'offre structurel — constante de classe (pas réallouée chaque appel)
    # Sources : Khan & Luintel 2006, Bom & Ligthart 2014, FMI 2015/2020,
    # OCDE/IEA 2014, Hanushek & Woessmann 2010. Rendements décroissants ln(1+x).
    SUPPLY_EFFECTS = {
        'recherche_publique':    {'coeff': 0.0025, 'delay': 5,  'deprec': 0.15, 'param': 'budget',         'measure_id': 'recherche_publique'},
        'transition_invest':     {'coeff': 0.0020, 'delay': 3,  'deprec': 0.05, 'param': 'investissement',  'measure_id': 'transition_ecologique'},
        'transition_renovation': {'coeff': 0.0010, 'delay': 2,  'deprec': 0.03, 'param': 'renovation',      'measure_id': 'transition_ecologique'},
        'education':             {'coeff': 0.0010, 'delay': 15, 'deprec': 0.05, 'param': 'budget',          'measure_id': 'education'},
    }

    def update_potential_growth(self, growth: float, year: int):
        """Ajuste la croissance potentielle : hystérèse + effet d'offre structurel.
        Cap total +0.20pt. Dépréciation différenciée par type si dépense coupée."""

        # --- Hystérèse conjoncturelle ---
        if growth < -0.020:
            self.base_params['croissance_potentielle'] *= 0.997
            _log_debug(self.debug_logs, f"Y{year}: Hystérèse négative")
        elif growth > 0.020 and year > 3:
            if self.base_params['croissance_potentielle'] < 0.012:
                self.base_params['croissance_potentielle'] *= 1.002
                _log_debug(self.debug_logs, f"Y{year}: Rebond potentiel")

        # --- Effet d'offre structurel ---
        try:
            defaults = self._get_default_values()

            for key, cfg in self.SUPPLY_EFFECTS.items():
                measure_params = self.mesures.get(cfg['measure_id'], {})
                default_val = defaults.get(cfg['measure_id'], {}).get(cfg['param'], 0)
                current_val = measure_params.get(cfg['param'], default_val)

                if not isinstance(current_val, (int, float)) or not isinstance(default_val, (int, float)):
                    continue

                delta = current_val - default_val

                if delta > 0.1:  # > 100 M€ au-dessus du défaut
                    years_active = self._supply_years.get(key, 0) + 1
                    self._supply_years[key] = years_active

                    if years_active >= cfg['delay']:
                        effective_delta = np.log2(1 + delta)  # rendements décroissants
                        self._supply_bonus_by_key[key] = cfg['coeff'] * effective_delta
                else:
                    # Dépréciation progressive avec coefficient différencié
                    prev_bonus = self._supply_bonus_by_key.get(key, 0)
                    if prev_bonus > 0.00001:
                        self._supply_bonus_by_key[key] = prev_bonus * (1 - cfg['deprec'])
                    else:
                        self._supply_bonus_by_key[key] = 0
                    # Décroître aussi le compteur d'années
                    prev_years = self._supply_years.get(key, 0)
                    if prev_years > 0:
                        self._supply_years[key] = max(0, prev_years - 1)

            # Cap total à +0.20pt
            self._potential_growth_bonus = min(sum(self._supply_bonus_by_key.values()), 0.002)

            if self._potential_growth_bonus > 0.0001:
                _log_debug(self.debug_logs,
                    f"Y{year}: Bonus potentiel = +{self._potential_growth_bonus*100:.3f}% "
                    f"(actifs: {', '.join(k for k, v in self._supply_bonus_by_key.items() if v > 0.00001)})")

        except Exception as e:
            # Garde défensif : inatteignable en run normal (la re-analyse
            # adverse a prouvé qu'aucune exception n'est atteignable ici —
            # un input non-dict crashe bruyamment en amont dans
            # apply_measures). Mais SI un refactor futur le rendait
            # atteignable, la dégradation (bonus→0) ne doit pas rester muette :
            # logger.error remonte au monitoring si l'opérateur en a configuré
            # un. Comportement runtime inchangé sur tout input atteignable →
            # golden master byte-identique.
            self._potential_growth_bonus = 0.0
            logger.error("Y%s: supply-side bonus désactivé: %s", year, e, exc_info=True)
            _log_debug(self.debug_logs, f"Y{year}: ERREUR supply-side (bonus désactivé): {e}")

        # Cap final hystérèse (hors bonus supply)
        self.base_params['croissance_potentielle'] = np.clip(
            self.base_params['croissance_potentielle'],
            0.007, 0.012
        )
