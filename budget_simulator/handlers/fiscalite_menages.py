"""Section 4 — Pression fiscale ménages.

Mesures couvertes (8 handlers) :
- ``tva_rate`` : taux de TVA général (base 20 %). Élasticité conso, effet Laffer
  au-delà de 22 %. Effets gini/compétitivité one-time.
- ``tva_energie`` : taux de TVA énergie (gaz + électricité, base 20 %). Slider
  unique vers 5,5 % (NFP/RN). Phasing 1 an, effets NIVEAU one-time.
- ``impot_revenu`` : barème IR — taux 5e tranche + décote. Assiette MARGINALE
  (au-dessus de 160 950 €), effet Laffer via ETI tranche supérieure.
- ``csg`` : taux global CSG (base 9,7 %) + option progressivité par décile
  (neutre recettes, forte réduction Gini). Recettes RÉCURRENTES, Gini one-time.
- ``cotisations_salariales`` : baisse en points (0 à la suppression totale de la
  masse sourcée, release E), 1 % de la masse salariale brute 2025 par point
  (≈ 11,57 Md€). Gini one-time.
- ``elargissement_ir`` : % de foyers imposables cible (0,45 → 0,70). Recettes
  classes moyennes D4-D6.
- ``fiscalite_patrimoine`` : IFI + succession + foncière regroupés, slider
  intensité ±0,3. Effet redistributif fort.
- ``isf_climatique`` : ISF avec bonus actifs verts, slider intensité 0-100 %,
  remplace l'IFI (croissance +2 %/an). Phasing 2 ans (cadastre), plafond 18 Md€.

Convention d'application :
- Pouvoir d'achat (v0.6.8) : chaque handler émet ses montants par canal
  ménages (clé ``menages``, ``handlers/_types.canaux_menages``) — prélèvements
  DIRECTS (IR, CSG, cotisations salariales, patrimoine) ou INDIRECTS (TVA) ;
  l'indice RDB-moteur (``engine/rdb.py``) les lit chaque année, en niveau.
  Les coefficients forfaitaires ``pouvoir_achat`` (non sourcés) ont disparu.
- Effets ``gini`` / ``competitivite`` PONCTUELS, émis selon DEUX idiomes
  distincts coexistant dans le monolithe :
  - au CHANGEMENT de paramètre, ``self._effet_ponctuel(<clé>, params, effet)``
    (v0.7.0 : en INCRÉMENT, effet du niveau atteint moins effet du niveau au
    dernier déclenchement) : tva_rate, impot_revenu, elargissement_ir,
    fiscalite_patrimoine, cotisations_salariales ;
  - à l'ANNÉE d'entrée en vigueur, ``years_elapsed == 0`` : tva_energie,
    isf_climatique, et csg (pour ses effets Gini) — horloge du levier.
  Cas mixte : ``csg`` combine les deux — Gini gated ``years_elapsed == 0``
  MAIS son sous-effet ``competitivite`` (progressivité) passe par
  ``self._effet_ponctuel('csg_competitivite', ...)``, appelé quel que soit le
  mode depuis v0.7.0 (le retrait de la progressivité rend l'effet). Toute
  unification des deux idiomes = chantier dédié avec double validation adverse
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
- Lit ``self.debug_logs`` et la méthode ``self._effet_ponctuel`` (base
  class, simulator.py ; seul son traqueur, tenu par l'hôte, est écrit).
- N'écrit aucun attribut d'instance.
"""
from typing import TYPE_CHECKING, Dict, Tuple

from ..constants import (
    COUT_PAR_POINT_COTIS_SAL,
    ETI_PLANCHER_FACTEUR,
    ETI_TRANCHE_SUPERIEURE,
    GINI_COTIS_SAL_PAR_MD,
    IR_GINI_DECOTE,
    IR_GINI_PAR_5PTS,
    IR_RECETTE_DECOTE,
    ISF_COMPET_PAR_12MD,
    ISF_GINI_PAR_12MD,
    ISF_PHASAGE,
    ISF_TAUX_MAX,
    PART_CONSOMMATION_MENAGES_TVA_TOTALE,
    PART_MENAGES_TAXE_FONCIERE,
    PATRIMOINE_COMPET_PAR_10MD,
    PATRIMOINE_GINI_PAR_10MD,
    POLICY_START_YEAR,
    TVA_COMPET_PAR_2PTS,
    TVA_ENERGIE_CONSO_ELECTRICITE_MD,
    TVA_ENERGIE_CONSO_GAZ_MD,
    TVA_ENERGIE_GINI_PAR_TAUX,
    TVA_GINI_PAR_2PTS,
    recette_tva_taux,
)
from .._logging import _log_debug
from ._phasing import _one_time_level, _year_phasing
from ._types import ImpactsDict, canaux_menages


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
        # Recette : fonction de constants.py, extraite au bit de ce handler
        # (release E, socle) pour que les coefficients par Md€ de la TVA la
        # LISENT au lieu de la recopier.
        delta_revenue = recette_tva_taux(rate, gdp, unemployment)

        # === IMPACTS MACROÉCONOMIQUES ===
        # Gini : Impact ONE-TIME (changement structure fiscale), en INCRÉMENT
        # (v0.7.0, simulator._effet_ponctuel).
        # Gini : TVA = impôt RÉGRESSIF (touche + les pauvres)
        # Règle : TVA 20%→22% = +0.005 Gini (OFCE 2024)
        def _effet_tva_rate(p):
            return TVA_GINI_PAR_2PTS * (p['rate'] - 0.20) / 0.02

        gini = self._effet_ponctuel('tva_rate', {'rate': rate}, _effet_tva_rate)

        # Compétitivité : Impact ONE-TIME (changement structure fiscale)
        # Règle : TVA +2% = -0.0005 compétitivité (CAE 2022, répercussion prix)
        def _effet_tva_rate_competitivite(p):
            return TVA_COMPET_PAR_2PTS * (p['rate'] - 0.20) / 0.02

        competitivite = self._effet_ponctuel('tva_rate_competitivite', {'rate': rate}, _effet_tva_rate_competitivite)

        _log_debug(self.debug_logs, f"Mesure tva_rate: Δdép=0.0 Md€, Δrec={delta_revenue:.1f} Md€")
        impacts = {
            'recettes': delta_revenue,
            'gini': gini,
            'competitivite': competitivite,
            # Base = consommation des ménages : toute la recette pèse sur
            # elle (part 1,0, constants.py § part de la fiscalité indirecte).
            'menages': canaux_menages(prelevements_indirects=delta_revenue),
        }
        return 0, delta_revenue, impacts

    def _apply_tva_energie(self, measure: Dict, params: Dict, year: int, gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """TVA énergie (actuel 20%). NFP/RN: 5.5% → -17 Md€ recettes. Conso 120 Md€/an. Effets NIVEAU one-time.
        Sources: NFP 2027, OFCE 2024. Voir METHODOLOGIE.md § Mesures Presidentielles 2027."""
        # ===== PARAMÈTRES - TAUX UNIQUE GAZ + ÉLECTRICITÉ =====
        # Slider unique : 20% (status quo) → 5.5% (NFP/RN)
        taux_energie = params.get('taux', 0.20)  # 0.055 à 0.20 (défaut 20%)
        taux_elec = taux_energie
        taux_gaz = taux_energie

        # Année de référence — horloge du levier (v0.7.0).
        years_elapsed = year - self._origine('tva_energie')

        # ===== PHASING 1 AN (mesure législative rapide) =====
        phasing = _year_phasing(years_elapsed, (1.0,))  # effet immédiat dès l'entrée en vigueur

        # ===== CONSOMMATION ÉNERGIE =====
        # Base 2024 : électricité 60 Md€, gaz 60 Md€
        conso_electricite = TVA_ENERGIE_CONSO_ELECTRICITE_MD  # Md€
        conso_gaz = TVA_ENERGIE_CONSO_GAZ_MD  # Md€

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
        # CONVENTION : delta_tva = TAUX_NOUVEAU - TAUX_ANCIEN (cohérent avec TVA générale)
        # Pouvoir d'achat (v0.6.8) : la variation de recettes passe par les prix
        # (canal ``prelevements_indirects``, engine/rdb.py) ; l'ancien « −Δtaux ×
        # 10 % du budget » comptait la baisse ENTIÈRE sur les prix, sans part
        # ménages ni répercussion partielle d'une baisse.
        delta_tva_moyen = ((taux_elec + taux_gaz) / 2) - 0.20

        # Gini : léger effet positif (ménages modestes dépensent + en % pour énergie)
        # Baisse TVA énergie réduit inégalités (énergie = 15% budget classes populaires vs 7% classes aisées)
        # Impact appliqué UNE FOIS (changement structure prix relatifs)
        impact_gini = _one_time_level(years_elapsed, delta_tva_moyen * TVA_ENERGIE_GINI_PAR_TAUX * phasing)

        # Compétitivité : neutre (entreprises ont déjà TVA déductible)
        impact_competitivite = 0.0

        impacts = {
            'recettes': delta_revenue,
            'gini': impact_gini,
            'competitivite': impact_competitivite,
            # Base = toute la consommation d'énergie (entreprises comprises) :
            # seule la part de la TVA nette sur la consommation des ménages.
            'menages': canaux_menages(prelevements_indirects=(
                PART_CONSOMMATION_MENAGES_TVA_TOTALE * delta_revenue)),
        }

        _log_debug(self.debug_logs,
            f"Y{year}: TVA énergie - Élec {taux_elec*100:.1f}%, Gaz {taux_gaz*100:.1f}%, "
            f"Recettes {delta_revenue:+.1f} Md€"
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
            facteur_comportemental = max(ETI_PLANCHER_FACTEUR, 1 + ETI_TRANCHE_SUPERIEURE * delta_net_of_tax)
        else:
            facteur_comportemental = 1.0

        delta_taux = delta_taux_brut * facteur_comportemental
        delta_decote = (1.0 - decote) * IR_RECETTE_DECOTE
        delta_revenue = delta_taux + delta_decote

        # === IMPACTS MACROÉCONOMIQUES ===
        # Gini : Impact ONE-TIME (changement barème fiscal), en INCRÉMENT (v0.7.0)
        # IR = impôt PROGRESSIF (redistribution forte)
        # Règle : Taux sup 45%→50% = -0.008 Gini (OFCE 2023)
        # Décote : Baisse décote = hausse impôt classes moyennes = +Gini
        def _effet_impot_revenu(p):
            return IR_GINI_PAR_5PTS * (p['taux_sup'] - 0.45) / 0.05 + IR_GINI_DECOTE * (1.0 - p['decote'])

        gini = self._effet_ponctuel(
            'impot_revenu', {'taux_sup': taux_sup, 'decote': decote}, _effet_impot_revenu)

        # Compétitivité : Impact ONE-TIME (changement structure fiscale)
        # Règle : Taux sup 45%→50% = -0.0002 (CAE 2024, attractivité hauts revenus/expatriation)
        params_ir_comp = {'taux_sup': taux_sup, 'decote': decote}
        def _effet_impot_revenu_competitivite(p):
            return -0.0002 * (p['taux_sup'] - 0.45) / 0.05

        competitivite = self._effet_ponctuel(
            'impot_revenu_competitivite', params_ir_comp, _effet_impot_revenu_competitivite)

        impacts = {
            'recettes': delta_revenue,
            'gini': gini,
            'competitivite': competitivite,
            'menages': canaux_menages(prelevements_directs=delta_revenue),
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

        # Année de référence pour phasing (impacts one-time) — horloge du
        # levier (v0.7.0).
        years_elapsed = year - self._origine('csg')

        # ===== EFFET 1 : VARIATION TAUX GLOBAL =====
        delta_taux_global = taux_global - CSG_BASE

        # Impact recettes (proportionnel, RÉCURRENT chaque année)
        delta_recettes = CSG_RECETTES_BASE * (delta_taux_global / CSG_BASE)

        # Impact Gini : ONE-TIME (changement de niveau, pas flux annuel).
        # Pouvoir d'achat (v0.6.8) : la recette EST le revenu retiré aux ménages
        # (canal ``prelevements_directs``) ; l'ancien « −1 pt = −1 % de PA »
        # transmettait 111 % de ses euros au RDB.
        # Impact Gini du taux : LÉGÈREMENT RÉGRESSIF — CSG touche pensions (taux
        #   remplacement faible) et patrimoine. Règle : CSG +1 pt = +0.002 Gini
        #   (OFCE 2024 "CSG légèrement régressive"). CSG 9.7 % (défaut 2025) →
        #   delta=0 → impact=0 (status quo) ; CSG 10.5 % → delta=+0.8 pt →
        #   impact=+0.0016 Gini.
        impact_gini_taux = _one_time_level(years_elapsed, 0.002 * (delta_taux_global / 0.01))

        # ===== EFFET 2 : PROGRESSIVITÉ (si activée) =====
        impact_gini_progressif = 0.0
        impact_emploi_progressif = 0.0
        impact_competitivite = 0.0

        if progressive == 1:
            # Recettes : NEUTRE (ajustement automatique des taux par décile)
            # Pas de delta_recettes additionnel

            # IMPACTS ONE-TIME : appliqués uniquement l'année 0 (changement de
            # niveau) ; années suivantes : maintien du niveau (pas de cumul).
            # PA (v0.6.8) : NUL en agrégé — à recette nulle, le RDB total ne
            #   bouge pas (transfert entre déciles, porté par le Gini). L'ancien
            #   +0,4 % comptait un effet de consommation, que l'emploi ci-dessous
            #   porte déjà.
            # Gini : FORTE réduction inégalités (OFCE 2023, modèle Allemagne).
            # Emploi : via boost consommation (multiplicateur 0.6) — +0.73 %
            #   conso → +0.44 % PIB → -0.15 % chômage (Okun -0.35).
            impact_gini_progressif = _one_time_level(years_elapsed, -0.015)
            impact_emploi_progressif = _one_time_level(years_elapsed, -0.0015)

        # Compétitivité : Impact ONE-TIME (changement structure fiscale)
        # Signal taux marginal D10 → attractivité fiscale : −0,003 l'année où la
        # progressivité s'active. v0.7.0 : déclencheur appelé QUEL QUE SOIT le
        # mode, en INCRÉMENT — un programme qui retire la progressivité rend le
        # −0,003 (jusqu'en v0.6.11, la branche n'était pas atteinte) ; un
        # changement de taux sans changement de progressivité n'émet plus rien
        # (il réémettait −0,003). Mode historique : 0,0 si progressive ≠ 1,
        # −0,003 l'année d'activation, comme avant.
        params_csg_comp = {'progressive': progressive, 'taux': taux_global}
        def _effet_csg_competitivite(p):
            return -0.003 if p['progressive'] == 1 else 0.0

        impact_competitivite = self._effet_ponctuel(
            'csg_competitivite', params_csg_comp, _effet_csg_competitivite)

        # ===== IMPACTS TOTAUX =====
        impacts = {
            'recettes': delta_recettes,
            'gini': impact_gini_taux + impact_gini_progressif,
            'chomage': impact_emploi_progressif,
            'competitivite': impact_competitivite,
            'menages': canaux_menages(prelevements_directs=delta_recettes),
        }

        # Logs détaillés
        if progressive == 1:
            taux_d1_d3 = taux_global - 0.037
            taux_d10 = taux_global + 0.063
            _log_debug(self.debug_logs,
                       f"Y{year}: CSG {taux_global*100:.1f}% progressive - "
                       f"D1-D3:{taux_d1_d3*100:.1f}%, D10:{taux_d10*100:.1f}%, "
                       f"Recettes {delta_recettes:+.1f}Md€, "
                       f"Gini {impact_gini_progressif:.3f}")
        else:
            _log_debug(self.debug_logs,
                       f"Y{year}: CSG {taux_global*100:.1f}% flat - "
                       f"Recettes {delta_recettes:+.1f}Md€")

        return 0, delta_recettes, impacts

    def _apply_cotisations_salariales(self, measure: Dict, params: Dict, year: int,
                                      gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """
        Baisse des cotisations sociales à la charge des salariés, hors CSG et
        CRDS (classées en impôts dans les comptes nationaux ; curseur CSG).

        Paramètre:
        - baisse_points : baisse en points de cotisation, de 0 à
          ``COTIS_SAL_POINTS_SUPPRESSION`` (release E, déplafonnement, contrat
          du dépôt parent § 1.2-D) : au maximum, le levier retire exactement la
          masse sourcée ``COTIS_SAL_MASSE_2025_MD`` (D613CE, Insee 2025), au
          coût du point du moteur. La borne vit dans policy_measures.json et
          est appliquée par les portes du moteur (écrêtage tracé en tolérant,
          refus en strict) : le handler ne réécrête plus (l'ancien plafond de
          5 points est retiré ; calcul identique au bit jusqu'à 5 points).

        Impact: -1 point = COUT_PAR_POINT_COTIS_SAL Md€ rendus aux salariés
        (canal prélèvements directs), loi linéaire sur tout le domaine. Le coût
        du point est 1 % de la masse salariale brute 2025 (Insee, tableau
        2.101, ligne D11) : le maximum est le taux moyen réel des cotisations
        salariales (décision du mainteneur du 12/11/2026, constants.py).
        """
        baisse_points = params.get('baisse_points', 0.0)

        # Retour anticipé au neutre SEULEMENT si aucun effet ponctuel n'a été
        # émis dans ce monde (contre-vérification m4, règle « Retour anticipé »
        # des handlers de la release E) : une baisse qui revient à 0 (rampe vers
        # 0 sous une valeur datée du droit) doit rendre son incrément de Gini.
        if baisse_points == 0 and 'cotisations_salariales' not in self._measure_params_tracker:
            return 0.0, 0.0, {}

        # ===== COÛT BUDGÉTAIRE =====
        # Un point de baisse = 1 % de la masse salariale brute 2025 rendu aux
        # salariés (COUT_PAR_POINT_COTIS_SAL, constants.py).
        delta_revenue = -baisse_points * COUT_PAR_POINT_COTIS_SAL

        # ===== IMPACTS MACROÉCONOMIQUES =====
        impacts = {
            'recettes': delta_revenue,
            # Baisse de cotisations → salaire net ↑ du montant rendu (v0.6.8).
            'menages': canaux_menages(prelevements_directs=delta_revenue),
        }

        # Gini : effet ONE-TIME au changement, en INCRÉMENT (v0.7.0). Une baisse
        # proportionnelle au salaire profite davantage, en euros, aux hauts
        # salaires : le Gini du niveau de vie AUGMENTE (baisse_points positif →
        # Gini +). Coefficient PAR Md€ rendu aux salariés
        # (GINI_COTIS_SAL_PAR_MD, estimation de France Budget, constants.py) :
        # le Gini ne dépend pas de la convention du point.
        def _effet_cotisations_salariales(p):
            return GINI_COTIS_SAL_PAR_MD * (p['baisse_points'] * COUT_PAR_POINT_COTIS_SAL)

        impacts['gini'] = self._effet_ponctuel(
            'cotisations_salariales', {'baisse_points': baisse_points}, _effet_cotisations_salariales)

        # Compétitivité: Neutre (ne change pas coût travail pour entreprises)
        impacts['competitivite'] = 0.0

        # Emploi : PAS d'effet chômage direct (v0.6.7, lot 3). L'ancien terme
        # (−0,05 pt par point, « +0,5 % PA → +0,3 % conso → +0,05 % emploi,
        # multiplier 0.6 ») chiffrait le canal CONSOMMATION — celui que le
        # multiplicateur keynésien applique déjà à la baisse de recettes de ce
        # levier (baisse d'impôts, engine/growth.py), puis Okun : double
        # comptage. Règle : un effet chômage direct de demande n'est légitime que
        # pour une mesure SANS flux budgétaire (ex. CSG progressive à recette
        # nulle, invisible du multiplicateur). Lot 1 : il avait d'abord été
        # ramené de récurrent (×15,7 par la convergence NAIRU) à une émission.

        _log_debug(self.debug_logs,
                   f"Y{year}: Cotisations salariales -{baisse_points:.1f} pts - "
                   f"coût {delta_revenue:.1f}Md€")

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
            'menages': canaux_menages(prelevements_directs=delta_revenue),
        }

        # Gini: Impact ONE-TIME (changement structure fiscale), en INCRÉMENT (v0.7.0)
        # Légèrement régressif (élargit mais touche classes moyennes D4-D6)
        def _effet_elargissement_ir(p):
            return 0.005 * ((p['taux_cible'] - TAUX_ACTUEL) / 0.20)

        impacts['gini'] = self._effet_ponctuel(
            'elargissement_ir', {'taux_cible': taux_cible}, _effet_elargissement_ir)

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
        # Revenu disponible (v0.6.8) : l'IFI et la part MÉNAGES de la taxe
        # foncière sont des impôts COURANTS des ménages ; la foncière des
        # entreprises est un impôt d'entreprise (par la croissance) et les
        # droits de succession un transfert en capital, hors du RDB au sens
        # de l'INSEE — exclus du canal ménages.
        impacts = {
            'recettes': delta_revenue,
            'menages': canaux_menages(prelevements_directs=(
                intensite * (IFI_BASE + PART_MENAGES_TAXE_FONCIERE * FONCIERE_BASE))),
        }

        # Gini: Impact ONE-TIME (changement structure fiscale), en INCRÉMENT (v0.7.0)
        # Fort effet redistributif si hausse (patrimoine concentré D9-D10)
        def _effet_fiscalite_patrimoine(p):
            return PATRIMOINE_GINI_PAR_10MD * ((TOTAL_BASE * p['intensite']) / 10.0)

        impacts['gini'] = self._effet_ponctuel(
            'fiscalite_patrimoine', {'intensite': intensite}, _effet_fiscalite_patrimoine)

        # Compétitivité: Impact ONE-TIME (changement structure fiscale)
        # Règle : Hausse 10 Md€ = -0.002 compétitivité (exil fiscal entrepreneurs)
        params_patrimoine_comp = {'intensite': intensite}
        def _effet_fiscalite_patrimoine_competitivite(p):
            return PATRIMOINE_COMPET_PAR_10MD * ((TOTAL_BASE * p['intensite']) / 10.0)

        impacts['competitivite'] = self._effet_ponctuel(
            'fiscalite_patrimoine_competitivite', params_patrimoine_comp, _effet_fiscalite_patrimoine_competitivite)

        _log_debug(self.debug_logs,
                   f"Y{year}: Fiscalité patrimoine {intensite*100:+.0f}% - "
                   f"Total = {TOTAL_BASE*(1+intensite):.1f}Md€ "
                   f"(delta {delta_revenue:+.1f}Md€)")

        return 0, delta_revenue, impacts

    def _apply_isf_climatique(self, measure: Dict, params: Dict, year: int, gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """ISF climatique. Slider intensité 0-100%. NFP: seuil 1.3M€, taux 1%, bonus 30% → 0-18 Md€. Remplace IFI (2 Md€).
        Sources: NFP 2027, OFCE 2024, EU Tax Observatory 2024. Voir METHODOLOGIE.md § Mesures Presidentielles 2027."""
        # ===== PARAMÈTRES - SLIDER INTENSITÉ UNIQUE =====
        # v0.6.7 (audit Codex 10/2026, bloc B constat 5 — arbitrage du mainteneur) :
        # COURBE CONTINUE. Recette totale = IFI (droit en vigueur) + intensité ×
        # (ISF complet − IFI) ; l'écart au statu quo vaut donc intensité ×
        # (ISF complet − IFI), et les effets macro sont interpolés de même.
        # « ISF complet » = point NFP (seuil 1,3 M€, taux 1 %, bonus vert 30 %),
        # déjà servi à l'intensité 1 — recette identique au bit en 0 et en 1.
        # Jusqu'en v0.6.6 l'intensité pilotait seuil, taux et bonus, avec des
        # paliers de foyers et d'assiette en escalier : dès 10⁻⁶ l'IFI était
        # supprimé (−2,2 Md€), puis deux falaises (+1,3 Md€ à 0,571 ; +2,8 Md€
        # entre 0,999 et 1). Δ recettes 2030 : 0 → 0 ; 10⁻⁶ → −2,17 ; 0,571 →
        # +0,75 ; 0,572 → +2,02 ; 1 → +7,90.
        intensite = params.get('intensite', 0.0)  # 0.0 à 1.0 (0% à 100%)
        if intensite == 0:
            # IFI maintenu : aucun changement budgétaire vs la baseline (l'IFI
            # continue à y générer ses ~2 Md€/an).
            return 0, 0, {'recettes': 0}
        seuil_entree = 1.3   # M€ (barème du levier)
        taux_max = ISF_TAUX_MAX      # 1 % (barème du levier)
        bonus_eco = 0.20 + 0.10  # abattement vert 30 % (barème du levier), écrit comme l'ancienne interpolation à l'intensité 1 : identité au bit

        # Année de référence — horloge du levier (v0.7.0) : phasage et effets
        # d'entrée en vigueur.
        years_elapsed = year - self._origine('isf_climatique')

        # ===== IFI DYNAMIQUE =====
        # IFI actuel avec croissance +2%/an (inflation patrimoniale INSEE 2015-2025).
        # CALENDAIRE (v0.7.0) : l'IFI remplacé croît depuis 2026 quelle que soit
        # l'année d'entrée de l'ISF — ce n'est pas l'horloge du programme.
        ifi_actuel = 2.0 * (1.02 ** max(0, year - POLICY_START_YEAR))

        # ===== PHASING 2 ANS (cadastre fiscal) =====
        # 0.5 l'année de mise en place, 1.0 ensuite (plein effet)
        phasing = _year_phasing(years_elapsed, ISF_PHASAGE)

        # ===== NOMBRE DE FOYERS CONCERNÉS =====
        # Distribution patrimoniale française (IPP 2024) : 350k foyers au-dessus
        # de 1,3 M€ (top 1,5 %, proposition NFP).
        foyers_concernes = 350_000

        # ===== ASSIETTE MOYENNE PAR FOYER =====
        # Patrimoine moyen au-dessus du seuil (INSEE 2024, IPP 2025) — calibré
        # pour correspondre aux estimations OFCE 2024 (12 Md€ brutes pour NFP)
        assiette_moyenne = 4.8  # M€ (top 1.5%, NFP cible)

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

        # ===== RECETTES NETTES (après remplacement IFI), INTERPOLÉES =====
        # L'ISF complet REMPLACE l'IFI ; l'intensité règle la part du chemin.
        delta_revenue = intensite * (recettes_nettes - ifi_actuel)

        # ===== IMPACTS MACROÉCONOMIQUES =====
        # Basés sur recettes_nettes (assiette totale taxée, effet redistributif absolu)
        # Sources : OFCE 2024, IPP 2025
        # IMPORTANT : Effets NIVEAU (one-time), pas FLUX (recurring)

        # Gini : -0.020 pour 12 Md€ (réduction forte inégalités via redistribution)
        # Impact appliqué UNE FOIS (changement structure revenus/patrimoine)
        impact_gini = _one_time_level(years_elapsed, ISF_GINI_PAR_12MD * (recettes_nettes / 12) * phasing)

        # Compétitivité : -0.002 (risque exil entrepreneurs)
        # Impact appliqué UNE FOIS (changement structure productive)
        impact_competitivite = _one_time_level(years_elapsed, ISF_COMPET_PAR_12MD * (recettes_nettes / 12) * phasing)

        impacts = {
            'recettes': delta_revenue,
            'gini': intensite * impact_gini,
            'competitivite': intensite * impact_competitivite,
            'menages': canaux_menages(prelevements_directs=delta_revenue),
        }

        _log_debug(self.debug_logs,
            f"Y{year}: ISF climatique - intensité {intensite:.2f} du point NFP (seuil {seuil_entree}M€, taux {taux_max*100:.1f}%), "
            f"Foyers {foyers_concernes/1000:.0f}k, Brutes {recettes_brutes:.1f} Md€, "
            f"Nettes {recettes_nettes:.1f} Md€, IFI {ifi_actuel:.1f} Md€, Delta {delta_revenue:+.1f} Md€"
        )

        return 0, delta_revenue, impacts

