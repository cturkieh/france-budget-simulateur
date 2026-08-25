"""Section 5 — Investissements stratégiques.

Mesures couvertes :
- ``education`` : budget Éducation nationale (PLF 2025 base 64,5 Md€), recrutements
  enseignants, hausses salariales. Effet capital humain progressif sur 7 ans.
- ``transition_ecologique`` : investissements verts, primes rénovation, taxe
  carbone. Effet innovation verte progressif sur 4 ans (Porter Hypothesis).
- ``recherche_publique`` : R&D publique (base 10 Md€ hors CIR). Effet innovation
  progressif sur 5 ans (élasticité OECD 0.17).

Convention d'application :
- Effet ``competitivite`` PROGRESSIF (capital humain / innovation = long terme),
  pas gated sur ``years_elapsed == 0`` mais avec un ``phasing`` croissant.
- Effets ``pouvoir_achat`` et ``gini`` en mode NIVEAU one-time, gated par
  ``self._is_first_year_change(<measure>, params)``.
- Effet ``recettes`` (transition_ecologique uniquement) : taxe carbone récurrente
  + retours fiscaux phase-in dès 2027 (5-8 % selon OECD/Cour des comptes).
- Voir docs/METHODOLOGIE.md § "Effets NIVEAU vs FLUX" pour le contrat de gating.

Sources principales :
- Hanushek & Woessmann 2015, OECD Education at a Glance 2024, UK Gov K4D HDR 2018,
  Harvard Aghion et al. (éducation).
- IMF 2023 "Green Innovation and Diffusion", Porter & van der Linde 1995, CAE 2023,
  France Stratégie 2023 (transition écologique).
- OECD 2017 "Impact of Public R&D Expenditure", Oxford Academic 2021,
  Guellec & Van Pottelsberghe 2004, France Stratégie 2023 (recherche publique).

Le mixin accède à ``self.debug_logs`` et ``self._is_first_year_change``,
attribut/méthode d'instance de ``BudgetSimulatorV45``.
"""
from typing import TYPE_CHECKING, Dict, Tuple

from ..constants import (
    CARBONE_PRIX_REFERENCE_EUR_T,
    GINI_RENOVATION_PAR_MD_EUR,
    GINI_TAXE_CARBONE_PAR_EUR_TONNE,
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


class InvestissementsMixin(_MixinBase):
    """Handlers Section 5 — Investissements stratégiques."""

    def _apply_education(self, measure: Dict, params: Dict, year: int, gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Éducation nationale. PLF 2025 : 64,5 Md€ mission enseignement scolaire.

        SOURCES EMPIRIQUES COMPÉTITIVITÉ (IMD Infrastructure pilier) :
        - Hanushek & Woessmann (2015) : +1 écart-type qualité éducation = +2 pts croissance PIB/an sur 40 ans
        - OCDE (2024) : +1 pt % PIB éducation = +0.34-0.76% croissance PIB/capita long terme
        - UK Gov (2018) : réforme qualité 20 ans = +5% PIB cumulé
        - Harvard (Aghion et al.) : éducation supérieure = canal principal croissance OECD

        CALIBRAGE : +15 Md€ éducation = +0.10 compétitivité (progressif sur 7 ans)
        L'éducation représente 5% du poids IMD (pilier Infrastructure → sous-facteur Éducation)

        Sources: Hanushek & Woessmann 2015, OECD Education at a Glance 2024,
                 UK Gov K4D HDR 2018, Harvard Aghion et al.
        """
        budget = params.get('budget', 65)  # PLF 2025 : 64,5 Md€ mission enseignement scolaire
        teachers = params.get('enseignants', 0)
        salaries = params.get('salaires', 0)

        delta_spending = (budget - 65) + teachers * 65000 / 1e9 + salaries * 0.01 * 50

        if delta_spending == 0 and teachers == 0 and salaries == 0:
            return 0, 0, {}

        years_elapsed = max(0, year - POLICY_START_YEAR)

        # === POUVOIR D'ACHAT : EFFET EMPLOI (ONE-TIME) ===
        # - Salaires enseignants : +1% = +0.0002 PA (première année uniquement)
        # - Recrutements : +10k postes = +0.001 PA (emplois publics stables)
        params_education = {'budget': budget, 'teachers': teachers, 'salaries': salaries}
        if self._is_first_year_change('education', params_education):
            pouvoir_achat = 0.0002 * salaries + 0.0001 * (teachers / 1000)
        else:
            pouvoir_achat = 0.0

        # === COMPÉTITIVITÉ : EFFET CAPITAL HUMAIN (PROGRESSIF LONG TERME) ===
        # Éducation = investissement dans le capital humain (effet différé 5-15 ans)
        # IMD classe l'éducation dans le pilier Infrastructure (5% du score total)
        #
        # CALIBRAGE EMPIRIQUE :
        # - Hanushek & Woessmann : +1 écart-type qualité = +2 pts croissance/an
        # - OECD : +1% PIB éducation → +0.34% à +0.76% croissance PIB/capita
        # - Notre coefficient : 0.001 par Md€ × phasing (effet retardé)
        #
        # Phase-in : Capital humain = très long terme (génération étudiants)
        #   Année 1-2: 10%, Année 3-4: 30%, Année 5-6: 60%, Année 7+: 100%
        #   (formation d'une cohorte = 3-7 ans minimum)

        if years_elapsed <= 1:
            phasing_edu = 0.1
        elif years_elapsed <= 3:
            phasing_edu = 0.3
        elif years_elapsed <= 5:
            phasing_edu = 0.6
        else:
            phasing_edu = 1.0

        # Coefficient calibré : 0.001 par Md€ (élasticité OECD moyenne 0.5, ajustée)
        # +15 Md€ → +0.015 compétitivité après maturation complète
        delta_budget = budget - 65
        competitivite_budget = delta_budget * 0.001 * phasing_edu

        # Bonus enseignants : qualité > quantité (Hanushek)
        # +10k enseignants avec meilleurs salaires = meilleure qualité
        competitivite_teachers = 0.0005 * (teachers / 1000) * phasing_edu
        competitivite_salaires = 0.0003 * salaries * phasing_edu  # Attractivité métier

        competitivite = competitivite_budget + competitivite_teachers + competitivite_salaires

        # === GINI : ZÉRO PAR CONSTRUCTION DE L'INDICATEUR (v0.6.1, item I27) ===
        # L'indice publié est le Gini du NIVEAU DE VIE (revenu disponible par
        # unité de consommation, définition INSEE). Une dépense d'éducation est
        # un transfert EN NATURE : elle n'entre pas dans le revenu disponible.
        # L'effet mécanique direct est donc exactement nul — par PÉRIMÈTRE de
        # l'indicateur, pas par oubli du modèle.
        #
        # Le zéro est émis EXPLICITEMENT, et c'est le cœur de la correction :
        # tant que la clé était absente, la mesure retombait dans un fallback
        # générique de engine/micro_impacts.py qui retranchait 0,04 × (dépense
        # / PIB) — coefficient sans aucune source, appliqué UNIQUEMENT aux
        # hausses (une coupe d'éducation émettait 0, avantage silencieux aux
        # programmes de coupe) et RÉPÉTÉ chaque année dans un agrégateur
        # cumulatif. Cf. constants.py § CANAUX GINI pour les sources et l'ordre
        # de grandeur sur l'indicateur ÉLARGI, qui n'est pas celui du site.
        gini = 0.0

        impacts = {
            'depenses': delta_spending,
            'gini': gini,
            'pouvoir_achat': pouvoir_achat,
            'competitivite': competitivite
        }

        _log_debug(self.debug_logs,
            f"Y{year}: Éducation - Budget {budget:.0f} Md€ (Δ{delta_budget:+.1f}), "
            f"Enseignants {teachers:+.0f}, Salaires +{salaries}%, "
            f"Phasing {phasing_edu*100:.0f}%, Compét {competitivite:+.4f}")

        return delta_spending, 0, impacts

    def _apply_transition_ecologique(self, measure: Dict, params: Dict, year: int, gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Transition écologique : investissements verts, rénovation, taxe carbone.

        SOURCES EMPIRIQUES COMPÉTITIVITÉ (IMD Infrastructure technologique) :
        - IMF Staff Discussion Notes (2023) : Green innovation → productivité + compétitivité
        - Porter Hypothesis (confirmé empiriquement) : régulation environnementale bien conçue
          → innovation → gains compétitivité (compensation effect)
        - ScienceDirect (2024) : Environmental regulation + market competition = green innovation
        - EIB (2024) : Digital + green transition = positive effect on firm performance
        - Nature (2023) : Main burden transition = R&D investment → green sector productivity

        CALIBRAGE : +20 Md€ transition = +0.015 compétitivité (progressif sur 4 ans)
        L'infrastructure technologique représente 5% du poids IMD

        Sources: IMF 2023 "Green Innovation and Diffusion",
                 Porter & van der Linde 1995, CAE 2023, France Stratégie 2023
        """
        investment = params.get('investissement', 0)
        # SOURCE UNIQUE du prix de référence : cinq littéraux du même prix
        # cohabitaient ici (valeur par défaut, recettes, Gini, pouvoir d'achat,
        # compétitivité) — un recalibrage de la référence n'en aurait atteint
        # qu'une partie.
        carbon_tax = params.get('taxe_carbone', CARBONE_PRIX_REFERENCE_EUR_T)
        renovation = params.get('renovation', 0)

        delta_spending = investment + renovation

        # Recettes taxe carbone : ~6 Md€ pour 100€/tCO2, proportionnel
        # Référence : CARBONE_PRIX_REFERENCE_EUR_T = statu quo (composante
        # carbone française gelée depuis 2018), donc delta = (taxe - réf) * 0.06
        delta_revenue = (carbon_tax - CARBONE_PRIX_REFERENCE_EUR_T) * 0.06
        if year >= 2027:
            # [FIX] Retours fiscaux de la transition — 5-8% avec phase-in.
            # L'ancien taux de 20% impliquait 16 Md€/an de retour pour 80 Md€ de dépense,
            # soit ~144 Md€ cumulés sur 10 ans — absurdement élevé.
            # OECD (2021) "Getting Infrastructure Right" : retour fiscal de l'investissement
            # public = 5-8% via emplois induits (IR, cotisations) et activité (TVA).
            # Cour des comptes (2023) : retour TVA sur investissements publics ~8-10%.
            # Phase-in : années 1-2 = 0% (construction), années 3-4 = 5%, années 5+ = 8%
            years_since_2027 = year - 2027
            if years_since_2027 < 2:
                fiscal_return_rate = 0.0
            elif years_since_2027 < 4:
                fiscal_return_rate = 0.05
            else:
                fiscal_return_rate = 0.08
            delta_revenue += delta_spending * fiscal_return_rate

        years_elapsed = max(0, year - POLICY_START_YEAR)

        # === GINI : Impact ONE-TIME (structure fiscale/redistributive) ===
        params_transition = {
            'investissement': investment,
            'carbon_tax': carbon_tax,
            'renovation': renovation
        }
        if self._is_first_year_change('transition_ecologique', params_transition):
            # 1) Aides à la rénovation = REDISTRIBUTIF (v0.6.1, item I29)
            # -0,00034 de Gini par Md€, soit -0,0017 pour +5 Md€.
            # Sources : ONRE/SDES fév. 2023 (MaPrimeRénov' concentre 60 % des
            # économies d'énergie sur D1-D4) + ONPE 2024 (67 % des dossiers
            # engagés en 2023 = ménages modestes et très modestes).
            # Contrairement à l'éducation, c'est un transfert MONÉTAIRE aux
            # ménages : le canal est pleinement dans le périmètre du Gini du
            # niveau de vie. Le coefficient de la v0.6.0 (-0,001 pour 5 Md€)
            # avait le bon signe mais était ~1,7× trop faible, et citait une
            # source introuvable. Détail de la dérivation et hypothèse
            # déclarée : constants.py § CANAUX GINI.
            gini_renovation = GINI_RENOVATION_PAR_MD_EUR * renovation

            # 2) Taxe carbone = RÉGRESSIF (v0.6.1, item I28)
            # +0,0010 de Gini pour +50 €/tCO2. Sources : Douenne (2020),
            # The Energy Journal 41(3) + Note IPP n° 34 (juillet 2018) :
            # taux d'effort D1 = 0,55 % du revenu disponible contre
            # D10 = 0,20-0,21 %. La v0.6.0 était exactement au DOUBLE, sur
            # une source introuvable.
            # ⚠️ Valable SOUS CONDITION D'ABSENCE DE RECYCLAGE des recettes
            # — ce qui est bien le cas ici (la taxe abonde le budget
            # général). Avec une compensation forfaitaire, Douenne montre que
            # D1-D5 deviennent gagnants et que le SIGNE S'INVERSE.
            gini_carbon = GINI_TAXE_CARBONE_PAR_EUR_TONNE * (
                carbon_tax - CARBONE_PRIX_REFERENCE_EUR_T)

            gini = gini_renovation + gini_carbon
        else:
            gini = 0.0

        # === POUVOIR D'ACHAT ===
        # Rénovation = vrai flux annuel récurrent (primes versées chaque année aux ménages bénéficiaires)
        # Taxe carbone = ONE-TIME (changement de niveau de prix relatif, comme tva_energie déjà gated)
        pouvoir_achat_renovation = 0.001 * renovation / 5
        if self._is_first_year_change('transition_carbone_pa', {'carbon_tax': carbon_tax}):
            pouvoir_achat_carbone = -0.0005 * (
                carbon_tax - CARBONE_PRIX_REFERENCE_EUR_T) / 50
        else:
            pouvoir_achat_carbone = 0.0
        pouvoir_achat = pouvoir_achat_renovation + pouvoir_achat_carbone

        # === COMPÉTITIVITÉ : INNOVATION VERTE (PROGRESSIF) vs TAXE CARBONE (ONE-TIME) ===
        #
        # PORTER HYPOTHESIS (confirmé empiriquement) :
        # - Investissements verts → innovation → gains compétitivité
        # - "Innovation compensation effect" peut compenser coûts réglementaires
        #
        # Phase-in : Technologies vertes = moyen terme (3-5 ans pour déploiement)
        #   Année 1: 30%, Année 2: 50%, Année 3: 70%, Année 4+: 100%
        #   (plus rapide que R&D pure car technologies existantes)

        phasing_green = _year_phasing(years_elapsed, (0.3, 0.5, 0.7, 1.0))

        # 1) Investissement : Impact RÉCURRENT positif (IMF 2023, Porter)
        # Coefficient calibré : 0.00075 par Md€ (légèrement supérieur à ancien 0.0005)
        # Logique : green tech = avantage first-mover + efficacité énergétique
        # +20 Md€ → +0.015 compétitivité/an après 4 ans
        competitivite_invest = (investment + renovation) * 0.00075 * phasing_green

        # 2) Taxe carbone : Impact ONE-TIME négatif (coût industries énergivores)
        # MAIS atténué par CBAM (mécanisme ajustement carbone frontière UE 2026)
        # CAE 2023 : impact négatif court terme, neutre long terme avec CBAM
        params_carbon = {'carbon_tax': carbon_tax}
        if self._is_first_year_change('taxe_carbone', params_carbon):
            # Coefficient réduit car CBAM atténue l'effet (protège industrie UE)
            competitivite_carbon = -0.002 * (
                carbon_tax - CARBONE_PRIX_REFERENCE_EUR_T) / 50  # Réduit de -0.003 à -0.002
        else:
            competitivite_carbon = 0.0

        competitivite = competitivite_invest + competitivite_carbon

        impacts = {
            'depenses': delta_spending,
            'recettes': delta_revenue,
            'gini': gini,
            'pouvoir_achat': pouvoir_achat,
            'competitivite': competitivite
        }

        _log_debug(self.debug_logs,
            f"Y{year}: Transition éco - Invest {investment:.0f} + Rénov {renovation:.0f} Md€, "
            f"Carbone {carbon_tax:.0f}€/t, Phasing {phasing_green*100:.0f}%, Compét {competitivite:+.4f}")

        return delta_spending, delta_revenue, impacts

    def _apply_recherche_publique(self, measure: Dict, params: Dict, year: int,
                                   gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Recherche publique (R&D). Actuel ~10 Md€ (hors CIR 7 Md€).

        SOURCES EMPIRIQUES COMPÉTITIVITÉ :
        - Guellec & Van Pottelsberghe (OECD 2004) : élasticité output R&D public = 0.17 (16 pays OECD)
        - Moyenne élasticité R&D OECD = 0.21 (panel 16 pays)
        - 1$ R&D public → 1.70$ R&D privé en moyenne (crowding-in, OECD 2017)
        - Effet spillover fort pour pays petits (10-15% productivité, Oxford Academic 2021)

        CALIBRAGE : +10 Md€ R&D = +0.15 compétitivité (progressif sur 5 ans)
        Référence : élasticité 0.17 × effet multiplicateur × phasing

        Sources: OECD 2017 "Impact of Public R&D Expenditure",
                 Oxford Academic 2021 "Economic impact of public R&D",
                 France Stratégie 2023 "Dépenses R&D"
        """
        budget = params.get('budget', 10)  # 10 Md€ base actuelle (hors CIR)
        budget_base = 10

        # Dépenses additionnelles
        delta_spending = budget - budget_base

        if delta_spending == 0:
            return 0, 0, {}

        years_elapsed = max(0, year - POLICY_START_YEAR)

        # === COMPÉTITIVITÉ : EFFET PROGRESSIF LONG-TERME ===
        # R&D public → innovation → productivité → compétitivité (délai 3-7 ans)
        # Élasticité OECD : 0.17-0.21 pour R&D public
        #
        # Phase-in : effet croissant sur 5 ans (R&D = investissement long terme)
        #   Année 1: 20%, Année 2: 40%, Année 3: 60%, Année 4: 80%, Année 5+: 100%
        #
        # Coefficient : 0.0015 par Md€ (recalibré élasticité OECD 0.17)
        #   +10 Md€ → +0.015 compétitivité/an après 5 ans
        #   Cumulatif car effet innovation est durable

        phasing_rd = min(1.0, 0.2 + years_elapsed * 0.2)  # 20% → 100% sur 5 ans

        # Impact récurrent (R&D crée stock de connaissances = avantage durable)
        # Coefficient calibré sur élasticité OECD 0.17, ajusté pour notre échelle
        competitivite = delta_spending * 0.0015 * phasing_rd

        # === POUVOIR D'ACHAT : EFFET EMPLOI R&D ===
        # Recrutements chercheurs = emplois qualifiés (+10 Md€ ≈ +50k emplois)
        # Impact ONE-TIME première année
        params_rd = {'budget': budget}
        if self._is_first_year_change('recherche_publique', params_rd):
            # Calibration empirique (MESR/SIES "État de l'ESR" 2024 : ~100k chercheurs publics,
            # salaire moyen 3500€) : +10 Md€ R&D ≈ 50k chercheurs × 3500€ × 12 = 2.1 Md€ masse
            # salariale ≈ 0.13% RDB. Coefficient 0.0001 → +0.1% PA Y1, conservatif (net ~70%).
            pouvoir_achat = 0.0001 * delta_spending
        else:
            pouvoir_achat = 0.0

        # === GINI : ZÉRO ASSUMÉ ET ARGUMENTÉ (v0.6.1, item I30) ===
        # Aucune étude, française ou internationale, n'estime l'incidence
        # distributive de la dépense publique de R&D sur les ménages. Ce n'est
        # pas un trou de la collecte, c'est un trou de la LITTÉRATURE : la R&D
        # publique s'évalue par ses RENDEMENTS (Guellec & van Pottelsberghe,
        # élasticité 0,17 — celle qu'utilise le canal compétitivité
        # ci-dessus), pas par son incidence sur la distribution des revenus.
        # Ce qui existe à la place est une CONVENTION comptable : l'INSEE
        # classe la diffusion de la recherche parmi les dépenses de
        # consommation COLLECTIVE (non individualisables), aux côtés de la
        # défense, de la police et de la justice — réparties par hypothèse,
        # avec trois variantes publiées (uniforme, proportionnelle au revenu,
        # mixte) et l'avertissement de l'INSEE que ces hypothèses « sont
        # déterminantes ».
        # Le motif affiché par la v0.6.0 était tout autre : il AFFIRMAIT une
        # incidence distributive — non sourcée, et de signe opposé au zéro
        # qu'elle prétendait justifier.
        gini = 0.0

        impacts = {
            'depenses': delta_spending,
            'pouvoir_achat': pouvoir_achat,
            'gini': gini,
            'competitivite': competitivite
        }

        _log_debug(self.debug_logs,
            f"Y{year}: Recherche publique - Budget {budget:.0f} Md€ (Δ{delta_spending:+.1f}), "
            f"Phasing {phasing_rd*100:.0f}%, Compét {competitivite:+.4f}")

        return delta_spending, 0, impacts
