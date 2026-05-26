"""Section 4 — Pression fiscale ménages.

Mesures couvertes (8 handlers) :
- ``tva_rate`` : taux de TVA général (base 20 %). Élasticité conso, effet Laffer
  au-delà de 22 %. Effets gini/PA/compétitivité one-time.
- ``tva_energie`` : taux de TVA énergie (gaz + électricité, base 20 %). Slider
  unique vers 5,5 % (NFP/RN). Phasing 1 an, effets NIVEAU one-time.
- ``impot_revenu`` : barème IR — taux 5e tranche + décote. Assiette MARGINALE
  (au-dessus de 160 950 €), effet Laffer via ETI tranche supérieure.
- ``csg`` : taux global CSG (base 9,7 %) + option progressivité par décile
  (neutre recettes, forte réduction Gini). Recettes RÉCURRENTES, PA/Gini one-time.
- ``cotisations_salariales`` : baisse en points (0-5), -6 Md€/pt. PA/Gini one-time.
- ``elargissement_ir`` : % de foyers imposables cible (0,45 → 0,70). Recettes
  classes moyennes D4-D6.
- ``fiscalite_patrimoine`` : IFI + succession + foncière regroupés, slider
  intensité ±0,3. Effet redistributif fort.
- ``isf_climatique`` : ISF avec bonus actifs verts, slider intensité 0-100 %,
  remplace l'IFI (croissance +2 %/an). Phasing 2 ans (cadastre), plafond 18 Md€.

Convention d'application :
- Effets ``gini`` / ``pouvoir_achat`` / ``competitivite`` en mode NIVEAU
  one-time, gated selon DEUX idiomes distincts coexistant dans le monolithe :
  - ``self._is_first_year_change(<measure>, params)`` : tva_rate,
    impot_revenu, elargissement_ir, fiscalite_patrimoine, cotisations_salariales.
  - ``years_elapsed == 0`` : tva_energie, isf_climatique, et csg (pour ses
    effets PA/Gini).
  Cas mixte : ``csg`` combine les deux — PA/Gini gated ``years_elapsed == 0``
  MAIS son sous-effet ``competitivite`` (mode progressif) gated
  ``self._is_first_year_change('csg_competitivite', ...)``. Cette nuance
  sémantique est PRÉSERVÉE telle quelle depuis le monolithe — toute
  unification éventuelle = chantier dédié avec double validation adverse
  + golden master audité (pas une simple refactor cosmétique).
- Effet ``recettes`` : RÉCURRENT (proportionnel au taux) pour csg/tva ;
  one-shot delta pour les barèmes.
- Voir docs/METHODOLOGIE.md § "Effets NIVEAU vs FLUX" pour le contrat de gating.

Sources principales :
- OFCE 2024 (TVA et inégalités, CSG régressive), INSEE 2018 (hausse TVA),
  CAE 2022/2024 (répercussion prix, attractivité).
- DGFiP POTE 2024, DG Trésor 2018, IPP TAXIPP 2024 (barème IR, Laffer).
- DREES 2024, OFCE 2023 (progressivité CSG, modèle Allemagne).
- URSSAF 2024, DARES (cotisations salariales).
- EU Tax Observatory 2024, Gabriel Zucman, IPP 2025 (ISF climatique).

Couplages avec ``BudgetSimulatorV45`` (instance hôte du mixin) :
- Lit ``self.debug_logs`` et la méthode ``self._is_first_year_change`` (base
  class, simulator.py).
- N'écrit aucun attribut d'instance.
"""
from typing import TYPE_CHECKING, Dict, Tuple

from ..constants import ETI_TRANCHE_SUPERIEURE, POLICY_START_YEAR
from .._logging import _log_debug
from ._phasing import _one_time_level, _year_phasing
from ._types import ImpactsDict


# Idiome mixin-self typing : NE PAS factoriser dans _types.py (casse la
# liaison self mypy + risque MRO). Réplication volontaire 7×. Cf Lot D.
if TYPE_CHECKING:
    from ._types import _SimulatorState

    _MixinBase = _SimulatorState
else:
    _MixinBase = object


class FiscaliteMenagesMixin(_MixinBase):
    """Handlers Section 4 — Pression fiscale ménages."""

    def _apply_tva_rate(self, measure: Dict, params: Dict, year: int, gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        rate = params.get('taux', 0.20)
        consumption_base = 0.53 * gdp
        base_elasticity = -0.2 if rate > 0.20 else -0.1
        if unemployment > 0.10:
            base_elasticity *= 1.2
        adjusted_base = consumption_base * (1 + base_elasticity * (rate - 0.20))
        delta_revenue = (rate - 0.20) * adjusted_base * 0.9
        if rate > 0.22:
            delta_revenue *= (1 - 0.2 * (rate - 0.22) / 0.03)

        # === IMPACTS MACROÉCONOMIQUES ===
        # Gini : Impact ONE-TIME (changement structure fiscale)
        if self._is_first_year_change('tva_rate', {'rate': rate}):
            # Gini : TVA = impôt RÉGRESSIF (touche + les pauvres)
            # Règle : TVA 20%→22% = +0.005 Gini (OFCE 2024)
            gini = 0.005 * (rate - 0.20) / 0.02
        else:
            gini = 0.0

        # Pouvoir d'achat : Impact ONE-TIME de NIVEAU (changement structure fiscale).
        # Règle : TVA +1pt = -0.002 PA agrégé (INSEE 2018 "Hausse TVA et inégalités" :
        # +3pt TVA = -0.6% niveau de vie corrigé sur 3 ans → -0.2%/pt).
        # NIVEAU et non flux annuel : la consommation s'ajuste UNE FOIS au nouveau prix relatif.
        if self._is_first_year_change('tva_rate_pa', {'rate': rate}):
            pouvoir_achat = -0.002 * (rate - 0.20) / 0.01
        else:
            pouvoir_achat = 0.0

        # Compétitivité : Impact ONE-TIME (changement structure fiscale)
        # Règle : TVA +2% = -0.0005 compétitivité (CAE 2022, répercussion prix)
        if self._is_first_year_change('tva_rate_competitivite', {'rate': rate}):
            competitivite = -0.0005 * (rate - 0.20) / 0.02  # ONE-TIME changement taux
        else:
            competitivite = 0.0  # Niveau conservé dans indice

        _log_debug(self.debug_logs, f"Mesure tva_rate: Δdép=0.0 Md€, Δrec={delta_revenue:.1f} Md€")
        impacts = {
            'recettes': delta_revenue,
            'gini': gini,
            'pouvoir_achat': pouvoir_achat,
            'competitivite': competitivite
        }
        return 0, delta_revenue, impacts

    def _apply_tva_energie(self, measure: Dict, params: Dict, year: int, gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """TVA énergie (actuel 20%). NFP/RN: 5.5% → -17 Md€ recettes, +1.5% PA. Conso 120 Md€/an. Effets NIVEAU one-time.
        Sources: NFP 2027, OFCE 2024. Voir METHODOLOGIE.md § Mesures Presidentielles 2027."""
        # ===== PARAMÈTRES - TAUX UNIQUE GAZ + ÉLECTRICITÉ =====
        # Slider unique : 20% (status quo) → 5.5% (NFP/RN)
        taux_energie = params.get('taux', 0.20)  # 0.055 à 0.20 (défaut 20%)
        taux_elec = taux_energie
        taux_gaz = taux_energie

        # Année de référence
        years_elapsed = year - POLICY_START_YEAR

        # ===== PHASING 1 AN (mesure législative rapide) =====
        phasing = _year_phasing(years_elapsed, (1.0,))  # effet immédiat dès l'entrée en vigueur

        # ===== CONSOMMATION ÉNERGIE =====
        # Base 2024 : électricité 60 Md€, gaz 60 Md€
        conso_electricite = 60.0  # Md€
        conso_gaz = 60.0  # Md€

        # ===== RECETTES TVA ACTUELLES (20%) =====
        recettes_actuelles_elec = conso_electricite * 0.20
        recettes_actuelles_gaz = conso_gaz * 0.20
        recettes_actuelles_total = recettes_actuelles_elec + recettes_actuelles_gaz  # 24 Md€

        # ===== RECETTES TVA NOUVELLES =====
        recettes_nouvelles_elec = conso_electricite * taux_elec
        recettes_nouvelles_gaz = conso_gaz * taux_gaz
        recettes_nouvelles_total = recettes_nouvelles_elec + recettes_nouvelles_gaz

        # ===== DELTA RECETTES =====
        delta_revenue = (recettes_nouvelles_total - recettes_actuelles_total) * phasing

        # ===== IMPACTS MACROÉCONOMIQUES =====
        # Pouvoir achat : énergie = 10% budget ménages
        # Baisse TVA 20% → 5.5% = -14.5 points → +14.5% baisse prix TTC → +1.45% PA
        # IMPORTANT : Effet NIVEAU (one-time), pas FLUX (recurring)
        # → Impact PA appliqué UNIQUEMENT l'année de mise en œuvre (years_elapsed == 0)
        # CONVENTION : delta_tva = TAUX_NOUVEAU - TAUX_ANCIEN (cohérent avec TVA générale)
        # Ex slider 5.5% : taux_energie=0.055 → delta_tva_moyen = (0.055-0.20) = -0.145
        # Impact PA = -(-0.145) × 0.10 = +0.0145 (+1.45% PA) ✅
        delta_tva_moyen = ((taux_elec + taux_gaz) / 2) - 0.20
        part_energie_budget = 0.10  # Énergie = 10% budget ménages (INSEE 2024)

        # Impact PA = one-time boost l'année de mise en œuvre seulement
        # (années suivantes : niveau déjà atteint, pas d'impact additionnel)
        impact_pa = _one_time_level(years_elapsed, -delta_tva_moyen * part_energie_budget * phasing)

        # Gini : léger effet positif (ménages modestes dépensent + en % pour énergie)
        # Baisse TVA énergie réduit inégalités (énergie = 15% budget classes populaires vs 7% classes aisées)
        # Impact appliqué UNE FOIS (changement structure prix relatifs)
        impact_gini = _one_time_level(years_elapsed, delta_tva_moyen * 0.05 * phasing)

        # Compétitivité : neutre (entreprises ont déjà TVA déductible)
        impact_competitivite = 0.0

        impacts = {
            'recettes': delta_revenue,
            'gini': impact_gini,
            'pouvoir_achat': impact_pa,
            'competitivite': impact_competitivite
        }

        _log_debug(self.debug_logs,
            f"Y{year}: TVA énergie - Élec {taux_elec*100:.1f}%, Gaz {taux_gaz*100:.1f}%, "
            f"Recettes {delta_revenue:+.1f} Md€, PA {impact_pa:+.2%}"
        )

        return 0, delta_revenue, impacts

    def _apply_impot_revenu(self, measure: Dict, params: Dict, year: int, gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        taux_sup = params.get('taux_superieur', 0.45)
        decote = params.get('decote', 1.0)

        # Bareme IR — assiette MARGINALE uniquement (fix bug ×3.6 surestimation).
        # Le delta de taux de la 5e tranche ne s'applique qu'a la fraction du revenu
        # AU-DESSUS du seuil 160 950 EUR (PLF 2025), pas a tout le revenu (220k EUR).
        # Sources : DGFiP POTE 2024, DG Tresor 2018, IPP TAXIPP 2024.
        foyers_riches = 400_000           # Foyers RNI > 160 950 EUR (DGFiP 2024)
        revenu_moyen_tranche = 220_000    # Revenu moyen foyer 5e tranche
        seuil_tranche_sup = 160_950       # Seuil 5e tranche, bareme PLF 2025
        assiette_marginale = revenu_moyen_tranche - seuil_tranche_sup  # ~59 050 EUR

        # Effet mecanique (avant comportement)
        delta_taux_brut = (taux_sup - 0.45) * foyers_riches * assiette_marginale / 1e9

        # Effet Laffer / elasticite revenu imposable (Saez-Diamond 2011, ETI=0.25 sur tranche sup).
        # Taux marginal effectif total = IR + CSG (9.7%) + CEHR (4% en moyenne sur tranche sup).
        # Calibrage 45→55% : 1.95 Md€ post-Laffer (vs DG Tresor 2018 fourchette 1-3 Md€).
        taux_marginal_total_avant = 0.45 + 0.097 + 0.04
        taux_marginal_total_apres = taux_sup + 0.097 + 0.04
        if taux_marginal_total_avant < 1.0 and taux_sup > 0.45:
            delta_net_of_tax = (
                (1 - taux_marginal_total_apres) - (1 - taux_marginal_total_avant)
            ) / (1 - taux_marginal_total_avant)
            facteur_comportemental = max(0.5, 1 + ETI_TRANCHE_SUPERIEURE * delta_net_of_tax)
        else:
            facteur_comportemental = 1.0

        delta_taux = delta_taux_brut * facteur_comportemental
        delta_decote = (1.0 - decote) * 7.5
        delta_revenue = delta_taux + delta_decote

        # === IMPACTS MACROÉCONOMIQUES ===
        # Gini : Impact ONE-TIME (changement barème fiscal)
        if self._is_first_year_change('impot_revenu', {'taux_sup': taux_sup, 'decote': decote}):
            # IR = impôt PROGRESSIF (redistribution forte)
            # Règle : Taux sup 45%→50% = -0.008 Gini (OFCE 2023)
            gini = -0.008 * (taux_sup - 0.45) / 0.05
            # Décote : Baisse décote = hausse impôt classes moyennes = +Gini
            gini += 0.003 * (1.0 - decote)
        else:
            gini = 0.0

        # Pouvoir d'achat : Impact ONE-TIME de NIVEAU (changement barème fiscal).
        # Règle : Hausse taux sup = -0.001 PA (concentré hauts revenus). Décote touche classes moyennes.
        # Le barème modifie le revenu disponible UNE FOIS, pas chaque année (TAXIPP/IPP convention).
        params_ir_pa = {'taux_sup': taux_sup, 'decote': decote}
        if self._is_first_year_change('impot_revenu_pa', params_ir_pa):
            pouvoir_achat = -0.001 * (taux_sup - 0.45) / 0.05
            pouvoir_achat += -0.002 * (1.0 - decote)
        else:
            pouvoir_achat = 0.0

        # Compétitivité : Impact ONE-TIME (changement structure fiscale)
        # Règle : Taux sup 45%→50% = -0.0002 (CAE 2024, attractivité hauts revenus/expatriation)
        params_ir_comp = {'taux_sup': taux_sup, 'decote': decote}
        if self._is_first_year_change('impot_revenu_competitivite', params_ir_comp):
            competitivite = -0.0002 * (taux_sup - 0.45) / 0.05  # ONE-TIME changement taux
        else:
            competitivite = 0.0  # Niveau conservé dans indice

        impacts = {
            'recettes': delta_revenue,
            'gini': gini,
            'pouvoir_achat': pouvoir_achat,
            'competitivite': competitivite
        }
        return 0, delta_revenue, impacts

    def _apply_csg(self, measure: Dict, params: Dict, year: int,
                   gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """
        CSG avec 2 paramètres indépendants:
        - taux (0.08-0.12): Taux global CSG, défaut 0.097
        - progressive (0/1): Activation progressivité par décile

        Mode flat (progressive=0): Tous paient le même taux
        Mode progressif (progressive=1): Taux par décile, neutre recettes
          D1-D3 (30%): taux - 3.7 pts
          D4-D6 (30%): taux - 1.2 pts
          D7-D8 (20%): taux + 0.8 pts
          D9 (10%): taux + 2.8 pts
          D10 (10%): taux + 6.3 pts

        Sources: DREES 2024, OFCE 2023 progressivité CSG, Modèle Allemagne
        """
        taux_global = params.get('taux', 0.097)
        progressive = params.get('progressive', 0)  # 0 ou 1

        CSG_BASE = 0.097  # Taux CSG réel actuel 9.7%
        CSG_RECETTES_BASE = 140.0  # Md€ (DREES 2024)

        # Année de référence pour phasing (impacts one-time)
        years_elapsed = year - POLICY_START_YEAR

        # ===== EFFET 1 : VARIATION TAUX GLOBAL =====
        delta_taux_global = taux_global - CSG_BASE

        # Impact recettes (proportionnel, RÉCURRENT chaque année)
        delta_recettes = CSG_RECETTES_BASE * (delta_taux_global / CSG_BASE)

        # Impact PA et Gini : ONE-TIME (changement de niveau, pas flux annuel)
        # Justification économique : Un changement de taux CSG modifie le niveau
        # du revenu disponible UNE SEULE FOIS (effet de niveau), comme TVA/IR ;
        # années suivantes : niveau déjà atteint, plus d'impact marginal.
        # Impact PA global (inverse, tous déciles touchés également) :
        #   -1 pt CSG = -1% PA (OFCE 2024).
        # Impact Gini du taux : LÉGÈREMENT RÉGRESSIF — CSG touche pensions (taux
        #   remplacement faible) et patrimoine. Règle : CSG +1 pt = +0.002 Gini
        #   (OFCE 2024 "CSG légèrement régressive"). CSG 9.7 % (défaut 2025) →
        #   delta=0 → impact=0 (status quo) ; CSG 10.5 % → delta=+0.8 pt →
        #   impact=+0.0016 Gini.
        impact_pa_taux = _one_time_level(years_elapsed, -0.01 * (delta_taux_global / 0.01))
        impact_gini_taux = _one_time_level(years_elapsed, 0.002 * (delta_taux_global / 0.01))

        # ===== EFFET 2 : PROGRESSIVITÉ (si activée) =====
        impact_pa_progressif = 0.0
        impact_gini_progressif = 0.0
        impact_emploi_progressif = 0.0
        impact_competitivite = 0.0

        if progressive == 1:
            # Recettes : NEUTRE (ajustement automatique des taux par décile)
            # Pas de delta_recettes additionnel

            # IMPACTS ONE-TIME : appliqués uniquement l'année 0 (changement de
            # niveau) ; années suivantes : maintien du niveau (pas de cumul).
            # PA : effet différentiel net POSITIF (+0.4 %) — déciles bas (forte
            #   propension conso) gagnent plus que hauts perdent.
            # Gini : FORTE réduction inégalités (OFCE 2023, modèle Allemagne).
            # Emploi : via boost consommation (multiplicateur 0.6) — +0.73 %
            #   conso → +0.44 % PIB → -0.15 % chômage (Okun -0.35).
            impact_pa_progressif = _one_time_level(years_elapsed, +0.004)
            impact_gini_progressif = _one_time_level(years_elapsed, -0.015)
            impact_emploi_progressif = _one_time_level(years_elapsed, -0.0015)

            # Compétitivité : Impact ONE-TIME (changement structure fiscale)
            # Signal taux marginal D10 → attractivité fiscale
            params_csg_comp = {'progressive': progressive, 'taux': taux_global}
            if self._is_first_year_change('csg_competitivite', params_csg_comp):
                impact_competitivite = -0.003  # ONE-TIME année activation
            else:
                impact_competitivite = 0.0  # Années suivantes (niveau conservé dans indice)
        # progressive != 1 : impact_competitivite reste à 0.0 (init ci-dessus)

        # ===== IMPACTS TOTAUX =====
        impacts = {
            'recettes': delta_recettes,
            'pouvoir_achat': impact_pa_taux + impact_pa_progressif,
            'gini': impact_gini_taux + impact_gini_progressif,
            'chomage': impact_emploi_progressif,
            'competitivite': impact_competitivite
        }

        # Logs détaillés
        if progressive == 1:
            taux_d1_d3 = taux_global - 0.037
            taux_d10 = taux_global + 0.063
            _log_debug(self.debug_logs,
                       f"Y{year}: CSG {taux_global*100:.1f}% progressive - "
                       f"D1-D3:{taux_d1_d3*100:.1f}%, D10:{taux_d10*100:.1f}%, "
                       f"Recettes {delta_recettes:+.1f}Md€, PA {impacts['pouvoir_achat']*100:+.2f}%, "
                       f"Gini {impact_gini_progressif:.3f}")
        else:
            _log_debug(self.debug_logs,
                       f"Y{year}: CSG {taux_global*100:.1f}% flat - "
                       f"Recettes {delta_recettes:+.1f}Md€, PA {impacts['pouvoir_achat']*100:+.2f}%")

        return 0, delta_recettes, impacts

    def _apply_cotisations_salariales(self, measure: Dict, params: Dict, year: int,
                                      gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """
        Baisse cotisations salariales (22% actuellement)

        Paramètre:
        - baisse_points (0-5): Baisse en points de cotisations

        Impact: -1 point = +0.5% pouvoir d'achat, coût 6 Md€
        Sources: URSSAF 2024, DARES pouvoir d'achat, OFCE multiplicateurs
        """
        baisse_points = params.get('baisse_points', 0.0)  # 0.0 à 5.0
        baisse_points = max(0, min(5, baisse_points))  # Clamp 0-5

        if baisse_points == 0:
            return 0.0, 0.0, {}

        # ===== COÛT BUDGÉTAIRE =====
        # -1 point cotisations = -6 Md€ recettes sociales
        COUT_PAR_POINT = 6.0  # Md€
        delta_revenue = -baisse_points * COUT_PAR_POINT

        # ===== IMPACTS MACROÉCONOMIQUES =====
        impacts = {
            'recettes': delta_revenue,
        }

        # ONE-TIME gate: PA et Gini ne s'appliquent que la première année de changement
        is_first_year = self._is_first_year_change('cotisations_salariales', {'baisse_points': baisse_points})

        # Pouvoir d'achat: +0.5% par point (OFCE 2024) — ONE-TIME
        # Baisse cotis → salaire net augmente → PA augmente
        if is_first_year:
            impacts['pouvoir_achat'] = 0.005 * baisse_points
        else:
            impacts['pouvoir_achat'] = 0.0

        # Gini: Impact ONE-TIME (première année changement seulement)
        if is_first_year:
            # Gini: INÉGALITAIRE (bénéfice absolu croît avec revenu)
            # Baisse cotis = MOINS de redistribution sociale → Gini AUGMENTE
            # Mécanisme : -1 pt cotis → -6 Md€ sécu → moins de transferts progressifs
            # Source: OFCE 2023 - Baisse uniforme 3 pts = +0.008 Gini
            # Donc: -1 pt cotis = +0.0027 Gini (hausse inégalités)
            # ATTENTION AU SIGNE : baisse_points POSITIF → Gini AUGMENTE (+)
            impacts['gini'] = 0.0027 * baisse_points
        else:
            # Années suivantes : impact déjà intégré
            impacts['gini'] = 0.0

        # Compétitivité: Neutre (ne change pas coût travail pour entreprises)
        impacts['competitivite'] = 0.0

        # Emploi: Légèrement positif via consommation
        # +0.5% PA → +0.3% conso → +0.05% emploi (multiplier 0.6)
        impacts['chomage'] = -0.0005 * baisse_points

        _log_debug(self.debug_logs,
                   f"Y{year}: Cotisations salariales -{baisse_points:.1f} pts - "
                   f"Taux effectif {22-baisse_points:.1f}%, coût {delta_revenue:.1f}Md€, "
                   f"PA +{impacts['pouvoir_achat']*100:.2f}%")

        return 0, delta_revenue, impacts

    def _apply_elargissement_ir(self, measure: Dict, params: Dict, year: int,
                                gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """
        Élargissement base IR (45% → 70% contribuables)

        Paramètres:
        - taux_contribuables_cible (0.45-0.70): % foyers imposables cible

        Implique plusieurs leviers techniques (baisse seuil entrée, gel barème,
        réduction abattements, plafonnement QF, restriction niches fiscales...)

        Sources: DGFiP 2024 (19M/41M foyers imposés = 45%), France Stratégie, OFCE
        """
        taux_cible = params.get('taux_contribuables_cible', 0.45)  # 0.45-0.70

        # Clamp paramètre
        taux_cible = max(0.45, min(0.70, taux_cible))

        # Statu quo - Mise à jour DGFiP 2024
        TAUX_ACTUEL = 0.45  # 19M foyers / 41M total = 45% (DGFiP 2024)
        FOYERS_TOTAL = 41_000_000  # DGFiP/INSEE 2024

        if taux_cible == TAUX_ACTUEL:
            return 0.0, 0.0, {}

        # ===== NOUVEAUX CONTRIBUABLES =====
        nouveaux_contrib = FOYERS_TOTAL * (taux_cible - TAUX_ACTUEL)

        # ===== RECETTES ADDITIONNELLES =====
        # Nouveaux contribuables: revenus D4-D6 (classes moyennes basses)
        # Revenu imposable moyen: 18,000€
        # Taux effectif moyen: ~3% (après décote)
        REVENU_MOYEN_NOUVEAUX = 18000  # €
        TAUX_EFFECTIF_MOYEN = 0.03

        recettes_nouvelles = (nouveaux_contrib * REVENU_MOYEN_NOUVEAUX *
                             TAUX_EFFECTIF_MOYEN / 1e9)

        delta_revenue = recettes_nouvelles

        # ===== IMPACTS MACROÉCONOMIQUES =====
        impacts = {
            'recettes': delta_revenue,
        }

        delta_contrib = taux_cible - TAUX_ACTUEL

        # Gini: Impact ONE-TIME (changement structure fiscale)
        if self._is_first_year_change('elargissement_ir', {'taux_cible': taux_cible}):
            # Légèrement régressif (élargit mais touche classes moyennes D4-D6)
            impacts['gini'] = 0.005 * (delta_contrib / 0.20)
        else:
            impacts['gini'] = 0.0

        # Pouvoir d'achat: ONE-TIME (changement barème = ajustement revenu disponible une fois)
        if self._is_first_year_change('elargissement_ir_pa', {'taux_cible': taux_cible}):
            impacts['pouvoir_achat'] = -0.0006 * (delta_contrib / 0.20)
        else:
            impacts['pouvoir_achat'] = 0.0

        # Compétitivité: Neutre
        impacts['competitivite'] = 0.0

        _log_debug(self.debug_logs,
                   f"Y{year}: Élargissement IR - "
                   f"Contrib. {taux_cible*100:.1f}% (+{nouveaux_contrib/1e6:.1f}M foyers), "
                   f"Recettes +{delta_revenue:.1f}Md€")

        return 0, delta_revenue, impacts

    def _apply_fiscalite_patrimoine(self, measure: Dict, params: Dict, year: int,
                                    gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """
        Fiscalité patrimoine regroupée: IFI + Succession + Foncière

        Paramètre:
        - intensite (-0.3 à +0.3): Variation fiscalité patrimoine
          -0.3 = baisse 30% (convergence UE)
           0   = statu quo (53 Md€)
          +0.3 = hausse 30%

        Sources: DGFiP 2024, IPP taxation patrimoine UE, OCDE wealth tax
        """
        intensite = params.get('intensite', 0.0)  # -0.3 à +0.3
        # Redondant depuis Lot C Item 1 : la porte unique (engine/orchestrator
        # → _param_domain) borne déjà intensite à [-0.3, 0.3] en amont.
        # Conservé pour défense en profondeur et garantie golden master
        # byte-identique — ne pas retirer sans régénération auditée.
        intensite = max(-0.3, min(0.3, intensite))

        if intensite == 0:
            return 0.0, 0.0, {}

        # ===== BUDGET ACTUEL =====
        IFI_BASE = 2.0      # Md€
        SUCCESSION_BASE = 15.0  # Md€
        FONCIERE_BASE = 36.0    # Md€
        TOTAL_BASE = IFI_BASE + SUCCESSION_BASE + FONCIERE_BASE  # 53 Md€

        # ===== VARIATION =====
        delta_revenue = TOTAL_BASE * intensite

        # ===== IMPACTS MACROÉCONOMIQUES =====
        impacts = {
            'recettes': delta_revenue,
        }

        # Gini: Impact ONE-TIME (changement structure fiscale)
        if self._is_first_year_change('fiscalite_patrimoine', {'intensite': intensite}):
            # Fort effet redistributif si hausse (patrimoine concentré D9-D10)
            impacts['gini'] = -0.010 * (delta_revenue / 10.0)
        else:
            impacts['gini'] = 0.0

        # Pouvoir d'achat: ONE-TIME (changement structure fiscale)
        if self._is_first_year_change('fiscalite_patrimoine_pa', {'intensite': intensite}):
            impacts['pouvoir_achat'] = -0.0005 * intensite
        else:
            impacts['pouvoir_achat'] = 0.0

        # Compétitivité: Impact ONE-TIME (changement structure fiscale)
        # Règle : Hausse 10 Md€ = -0.002 compétitivité (exil fiscal entrepreneurs)
        params_patrimoine_comp = {'intensite': intensite}
        if self._is_first_year_change('fiscalite_patrimoine_competitivite', params_patrimoine_comp):
            impacts['competitivite'] = -0.002 * (delta_revenue / 10.0)  # ONE-TIME changement intensité
        else:
            impacts['competitivite'] = 0.0  # Niveau conservé dans indice

        _log_debug(self.debug_logs,
                   f"Y{year}: Fiscalité patrimoine {intensite*100:+.0f}% - "
                   f"Total = {TOTAL_BASE*(1+intensite):.1f}Md€ "
                   f"(delta {delta_revenue:+.1f}Md€)")

        return 0, delta_revenue, impacts

    def _apply_isf_climatique(self, measure: Dict, params: Dict, year: int, gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """ISF climatique. Slider intensité 0-100%. NFP: seuil 1.3M€, taux 1%, bonus 30% → 0-18 Md€. Remplace IFI (2 Md€).
        Sources: NFP 2027, OFCE 2024, EU Tax Observatory 2024. Voir METHODOLOGIE.md § Mesures Presidentielles 2027."""
        # ===== PARAMÈTRES - SLIDER INTENSITÉ UNIQUE =====
        # intensite : 0% (IFI maintenu) → 100% (ISF NFP maximal)
        # Mapping automatique : intensité → (seuil, taux, bonus)
        intensite = params.get('intensite', 0.0)  # 0.0 à 1.0 (0% à 100%)

        # Interpolation linéaire selon intensité
        # Intensité 0%   : IFI maintenu (seuil 2.0M€, taux 0%)
        # Intensité 50%  : ISF modéré (seuil 1.4M€, taux 0.6%, bonus 25%)
        # Intensité 100% : ISF NFP (seuil 1.3M€, taux 1%, bonus 30%)
        seuil_entree = 2.0 - (intensite * 0.7)  # 2.0 → 1.3 M€
        taux_max = intensite * 0.01  # 0% → 1.0%
        bonus_eco = 0.20 + (intensite * 0.10)  # 20% → 30%

        # Année de référence
        years_elapsed = year - POLICY_START_YEAR

        # ===== IFI DYNAMIQUE =====
        # IFI actuel avec croissance +2%/an (inflation patrimoniale INSEE 2015-2025)
        ifi_actuel = 2.0 * (1.02 ** max(0, years_elapsed))

        # Si maintien IFI actuel (seuil très élevé ou taux nul)
        # → Retourner 0 (pas de changement budgétaire par rapport à la baseline)
        # L'IFI continue à générer ses 2 Md€/an dans la baseline, mais aucun delta ici
        if seuil_entree >= 2.0 or taux_max == 0:
            return 0, 0, {'recettes': 0}

        # ===== PHASING 2 ANS (cadastre fiscal) =====
        # 0.5 l'année de mise en place, 1.0 ensuite (plein effet)
        phasing = _year_phasing(years_elapsed, (0.5, 1.0))

        # ===== NOMBRE DE FOYERS CONCERNÉS =====
        # Distribution patrimoniale française (IPP 2024) :
        # - 0.8M€ : 500k foyers (top 3%)
        # - 1.3M€ : 350k foyers (top 1.5%, proposition NFP)
        # - 1.6M€ : 220k foyers (top 1%)
        # - 2.0M€ : 130k foyers (top 0.5%)
        if seuil_entree <= 0.8:
            foyers_concernes = 500_000
        elif seuil_entree <= 1.3:
            foyers_concernes = 350_000
        elif seuil_entree <= 1.6:
            foyers_concernes = 220_000
        else:
            foyers_concernes = 130_000

        # ===== ASSIETTE MOYENNE PAR FOYER =====
        # Patrimoine moyen au-dessus du seuil (INSEE 2024, IPP 2025)
        # Calibré pour correspondre aux estimations OFCE 2024 (12 Md€ brutes pour NFP)
        if seuil_entree <= 0.8:
            assiette_moyenne = 3.0  # M€ (top 3%)
        elif seuil_entree <= 1.3:
            assiette_moyenne = 4.8  # M€ (top 1.5%, NFP cible)
        elif seuil_entree <= 1.6:
            assiette_moyenne = 5.5  # M€ (top 1%)
        else:
            assiette_moyenne = 6.5  # M€ (ultra-riches top 0.5%)

        # ===== BARÈME PROGRESSIF =====
        # Simplifié : taux effectif moyen = 75% du taux max
        # Barème NFP réel : 0.5% (1.3-2.5M€), 0.7% (2.5-5M€), 1.0% (>5M€)
        # Sources : OFCE 2024, IPP 2025 (estim. recettes 12 Md€ pour NFP)
        taux_effectif_moyen = taux_max * 0.75

        # ===== BONUS ÉCOLOGIQUE =====
        # Abattement sur actifs verts (énergies renouvelables, forêts certifiées)
        # Hypothèse : 20% du patrimoine éligible en moyenne
        part_actifs_verts = 0.20
        reduction_assiette = assiette_moyenne * part_actifs_verts * bonus_eco
        assiette_nette = assiette_moyenne - reduction_assiette

        # ===== RECETTES BRUTES =====
        # foyers × assiette(M€) × taux → millions € → Md€
        recettes_brutes = foyers_concernes * assiette_nette * taux_effectif_moyen * phasing / 1000  # Md€

        # ===== ÉVASION FISCALE =====
        # Exil fiscal et optimisation (Suisse, Luxembourg, trust)
        # Sources : EU Tax Observatory 2024, Gabriel Zucman
        taux_evasion = 0.15  # 15% patrimoine échappe à l'impôt
        recettes_nettes = recettes_brutes * (1 - taux_evasion)

        # ===== PLAFOND RÉALISTE =====
        # EU Tax Observatory 2024 : plafond 18 Md€ (scénarios ambitieux possibles)
        plafond_max = 18.0
        if recettes_nettes > plafond_max:
            recettes_nettes = plafond_max

        # ===== RECETTES NETTES (après remplacement IFI) =====
        # L'ISF Climatique REMPLACE l'IFI actuel
        # → Delta = Recettes ISF - Recettes IFI perdues (avec croissance +2%/an)
        delta_revenue = recettes_nettes - ifi_actuel

        # ===== IMPACTS MACROÉCONOMIQUES =====
        # Basés sur recettes_nettes (assiette totale taxée, effet redistributif absolu)
        # Sources : OFCE 2024, IPP 2025
        # IMPORTANT : Effets NIVEAU (one-time), pas FLUX (recurring)

        # Gini : -0.020 pour 12 Md€ (réduction forte inégalités via redistribution)
        # Impact appliqué UNE FOIS (changement structure revenus/patrimoine)
        impact_gini = _one_time_level(years_elapsed, -0.020 * (recettes_nettes / 12) * phasing)

        # Pouvoir d'achat : -0.001 (quasi-neutre, touche 1% population)
        # Impact appliqué UNE FOIS (changement consommation hauts patrimoines)
        impact_pa = _one_time_level(years_elapsed, -0.001 * (recettes_nettes / 12) * phasing)

        # Compétitivité : -0.002 (risque exil entrepreneurs)
        # Impact appliqué UNE FOIS (changement structure productive)
        impact_competitivite = _one_time_level(years_elapsed, -0.002 * (recettes_nettes / 12) * phasing)

        impacts = {
            'recettes': delta_revenue,
            'gini': impact_gini,
            'pouvoir_achat': impact_pa,
            'competitivite': impact_competitivite
        }

        _log_debug(self.debug_logs,
            f"Y{year}: ISF climatique - Seuil {seuil_entree}M€, Taux {taux_max*100:.1f}%, "
            f"Foyers {foyers_concernes/1000:.0f}k, Brutes {recettes_brutes:.1f} Md€, "
            f"Nettes {recettes_nettes:.1f} Md€, IFI {ifi_actuel:.1f} Md€, Delta {delta_revenue:+.1f} Md€"
        )

        return 0, delta_revenue, impacts

