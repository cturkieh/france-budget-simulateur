"""Section 6 — Paramètres additionnels (Débats Présidentielle 2027).

Mesures couvertes :
- ``smic`` : hausse du SMIC brut ; cinq postes de finances publiques du Trésor
  (groupe d'experts 2017, tableau 9), mis à l'échelle de l'année et de la hausse.
- ``taxe_superprofits`` : taxe 25% sur bénéfices >120% moyenne historique
  (temporaire 3 ans : 2026-2028 en mode historique, trois ans à partir de
  annee_debut sinon — v0.7.0).
- ``exonerations_salaires`` : exonération cotisations patronales sur hausses
  salariales >1% (NFP 2027).

Convention d'application :
- Tous les handlers de ce mixin appliquent les effets micro
  (``gini``, ``competitivite``, ``chomage``) en mode NIVEAU one-time, gated
  sur ``years_elapsed == 0``.
- Pouvoir d'achat (v0.6.8) : canaux ménages en euros de l'année (clé
  ``menages``). ``smic`` : revenu disponible du tableau 8 du Trésor (salaires
  nets privés, rémunérations publiques, baisse des prestations, impôt sur le
  revenu) ; ``taxe_superprofits`` et ``exonerations_salaires``
  (cotisations PATRONALES) : aucun effet direct, par la croissance et
  l'emploi (arbitrage du mainteneur).
- Voir docs/METHODOLOGIE.md § "Effets NIVEAU vs FLUX" pour le contrat de gating.

Sources principales :
- OFCE 2024, DARES 2024, Trésor-Éco 97 (2012), Cahuc & Carcillo 2014,
  Kramarz & Philippon (2001), Abowd et al. (2000), INSEE 2024,
  IPP Bozio 2018, OFCE Plane 2014.
- Voir docs/METHODOLOGIE.md § Mesures Presidentielles 2027.

Le mixin accède à ``self.mesures`` et ``self.debug_logs``, attributs
d'instance de ``BudgetSimulatorV45``.
"""
import logging
import math
from typing import TYPE_CHECKING, Dict, Tuple

from ..constants import (
    GINI_SMIC_PAR_HAUSSE,
    PART_NETTE_DU_BRUT_SMIC,
    PART_NETTE_REMUNERATIONS_APU,
    SALAIRES_BRUTS_2017_MD,
    SALAIRES_BRUTS_2025_MD,
    SMIC_ANNEE_DE_REFERENCE,
    SMIC_BRUT_MENSUEL_REFERENCE_EUR,
    SMIC_TRESOR_REVENU_BRUT_PAR_POINT_M_EUR_2017,
    SMIC_TRESOR_SOLDE_PAR_POINT_M_EUR_2017,
)
from .._logging import _log_debug
from ..engine._param_domain import valeur_brute
from ._phasing import _one_time_level, _resolve_intensite_or_legacy, _year_phasing
from ._types import ImpactsDict, canaux_menages

logger = logging.getLogger(__name__)


def _point_indice_fp_brut(mesures: Dict) -> float:
    """``fonction_publique.point_indice`` lu par le SMIC (anti-double comptage).

    Lecture CROISÉE de ``mesures`` BRUT — hors de la porte unique, qui ne
    filtre que les ``params`` du levier dispatché. Elle doit donc rendre ce
    que le handler ``fonction_publique`` aura effectivement appliqué : son
    défaut (0) quand la porte retire la valeur (``None`` / NaN / ±inf), ou
    quand le bloc est absent ou ``null`` (``valeur_brute``). Valeur non
    numérique ou bloc mal formé → 0 aussi : NEUTRE ici, l'anomalie est
    signalée par la porte de ``fonction_publique`` elle-même (même
    convention que ``_seniors``). Sans cette garde, un ``null`` sur le point
    d'indice faisait échouer le SMIC (Sentry FRANCE-BUDGET-Z). Un booléen est
    neutre aussi : la porte le refuse sur une quantité (gardes d'entrée du
    lot 3). Valeur légitime → rendue telle quelle (golden byte-identique)."""
    valeur = valeur_brute(mesures, 'fonction_publique', 'point_indice', 0.0)
    if isinstance(valeur, (int, float)) and not isinstance(valeur, bool) and math.isfinite(valeur):
        return valeur
    return 0.0


def smic_brut_du_net(net: float) -> float:
    """SMIC brut mensuel d'un montant écrit en net : net / part nette officielle
    du SMIC (``PART_NETTE_DU_BRUT_SMIC``, 1 477,93 / 1 867,02 au 1er juin 2026).
    Règle d'encodage d'un programme qui écrit son SMIC en net (lot SMIC)."""
    return net / PART_NETTE_DU_BRUT_SMIC


# Taxe sur les superprofits : mesure TEMPORAIRE, trois années d'application
# (crise d'inflation 2022-2024, programme NFP), comptées sur l'horloge du levier
# (2026-2028 en mode historique ; à partir de annee_debut sinon, v0.7.0).
TAXE_SUPERPROFITS_DUREE_ANS = 3


# Idiome mixin-self typing : NE PAS factoriser dans _types.py (casse la
# liaison self mypy + risque MRO). Réplication volontaire 7×. Cf Lot D.
if TYPE_CHECKING:
    from ._types import _SimulatorState

    _MixinBase = _SimulatorState
else:
    _MixinBase = object


class AdditionnelsMixin(_MixinBase):
    """Handlers Section 6 — Paramètres additionnels Présidentielle 2027."""

    def _indice_prix_de(self, annee: int, year: int) -> float:
        """Indice de prix des dépenses de l'année ``annee``, tel que le moteur l'a
        calculé cette année-là (``_indice_prix_par_annee``) ; l'année en cours
        hors simulation (appel direct d'un handler) : l'indice courant. Une
        année passée absente est un défaut du moteur : ``RuntimeError``, jamais
        un 1,0 silencieux."""
        indice = self._indice_prix_par_annee.get(annee)
        if indice is not None:
            return indice
        if annee == year:
            return self.indice_prix_depenses()
        raise RuntimeError(
            f"indice de prix de l'année {annee} non enregistré (année {year} ; années "
            f"connues : {sorted(self._indice_prix_par_annee)}) — référence du SMIC lue "
            "avant que l'année ait été simulée")

    def _smic_de_reference(self, montant, origine: int, year: int) -> float:
        """SMIC brut mensuel contre lequel se lit ``montant`` (lot SMIC,
        arbitrage du mainteneur du 16/11/2026).

        Un montant de programme est un SMIC de son année d'application,
        l'origine du levier : la référence (``SMIC_BRUT_MENSUEL_REFERENCE_EUR``,
        année ``SMIC_ANNEE_DE_REFERENCE``) y est portée avec l'indice de prix
        des dépenses du moteur ; la revalorisation légale fait déjà partie du
        statu quo. La valeur du droit en vigueur de l'année
        (``_reference_du_calendrier``), elle, se lit dans les euros de l'année
        de référence : elle est neutre à toute origine. Sans cette règle, le
        monde « droit au début » de la composition (horloge du programme) verrait
        une baisse du SMIC, que la composition ajouterait à la hausse du
        programme. En mode historique, l'origine est l'année de référence : les
        deux lectures coïncident, au bit."""
        if montant == self._reference_du_calendrier('smic', 'montant_brut', year):
            return SMIC_BRUT_MENSUEL_REFERENCE_EUR
        rapport = (self._indice_prix_de(origine, year)
                   / self._indice_prix_de(SMIC_ANNEE_DE_REFERENCE, year))
        return SMIC_BRUT_MENSUEL_REFERENCE_EUR * rapport

    def _apply_smic(self, measure: Dict, params: Dict, year: int, gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """SMIC brut mensuel. Finances publiques : les cinq postes du Trésor par point de hausse
        (groupe d'experts 2017, tableau 9), chacun selon sa nature (lot SMIC, arbitrage du mainteneur
        du 16/11/2026). Effets NIVEAU one-time (chômage, compétitivité, Gini). Voir METHODOLOGIE.md
        § SMIC."""
        smic_brut = params.get('montant_brut', SMIC_BRUT_MENSUEL_REFERENCE_EUR)

        # Année de mise en œuvre — horloge du levier (v0.7.0 : annee_debut du
        # programme s'il le modifie, POLICY_START_YEAR sinon).
        origine = self._origine('smic')
        years_elapsed = year - origine

        # Hausse fixée l'année d'origine, contre la référence datée (lot SMIC).
        reference = self._smic_de_reference(smic_brut, origine, year)
        if smic_brut == reference:
            return 0, 0, {}

        # ===== CALCUL IMPACTS =====
        hausse_pct = (smic_brut - reference) / reference
        points = 100.0 * hausse_pct

        # Les cinq postes du Trésor (lot SMIC, arbitrage du mainteneur du
        # 16/11/2026 ; constants.SMIC_TRESOR_SOLDE_PAR_POINT_M_EUR_2017,
        # tableau 9 du groupe d'experts 2017), en Md€ de l'année : M€ de 2017
        # par point × salaires bruts 2025 / 2017 × PIB nominal de l'année / 2025,
        # × la hausse en points. Chacun garde sa nature (engine/growth.py,
        # flux_par_levier et _stocker_impulsions).
        echelle = (SALAIRES_BRUTS_2025_MD / SALAIRES_BRUTS_2017_MD
                   * self._indice_pib_source(2025, gdp) / 1000.0)
        postes = SMIC_TRESOR_SOLDE_PAR_POINT_M_EUR_2017

        # 1. Paie publique (dépense) : au canal des rémunérations publiques, donc
        # au traitement des transferts (lot 5b) et à l'effet prix (lot 5d).
        # Anti-double compte : un point d'indice relevé de p % couvre déjà p
        # points de la hausse pour les agents ; aucune économie pour une baisse.
        points_point_indice = _point_indice_fp_brut(self.mesures)
        delta_fp = -postes['paie_publique'] * echelle * max(0.0, points - points_point_indice)

        # 2. Prestations (dépense) : la hausse du SMIC les BAISSE (prime
        # d'activité, aides au logement, prestations familiales, minima :
        # tableau 8) ; un transfert, comme tout le levier.
        delta_aides = -postes['prestations'] * echelle * points

        # 3. Recettes : prélèvements des salariés et impôt sur le revenu (une
        # hausse d'impôts), cotisations des employeurs nettes des allègements
        # (une baisse de charges). Un seul flux de recettes : la hausse et la
        # baisse d'impôts ont le même coefficient (tests/test_smic_flux_tresor.py).
        impot_revenu = postes['impot_sur_le_revenu'] * echelle * points
        delta_cotisations = ((postes['prelevements_des_salaries']
                              + postes['cotisations_employeurs_nettes_des_allegements'])
                             * echelle * points)

        # 4. TOTAL : solde = −240 M€ par point, mis à l'échelle.
        delta_spending = delta_fp + delta_aides
        delta_revenue = delta_cotisations + impot_revenu

        # ===== IMPACTS MACROÉCONOMIQUES =====
        # Pouvoir d'achat : revenu disponible du tableau 8 (+690 M€ par point),
        # sans double compte. Salaires nets = revenu brut − prélèvements des
        # salariés ; la part des agents publics passe par la règle du moteur
        # (canal des rémunérations publiques, part nette du coût employeur), le
        # reste est le salaire net du privé ; baisse des prestations ; impôt sur
        # le revenu en prélèvement direct.
        salaires_nets_prives = ((SMIC_TRESOR_REVENU_BRUT_PAR_POINT_M_EUR_2017
                                 - postes['prelevements_des_salaries']
                                 + PART_NETTE_REMUNERATIONS_APU * postes['paie_publique'])
                                * echelle * points)

        # Compétitivité : -0.25% pour +10% SMIC (coût travail entreprises)
        # Impact permanent sur coût travail, mais appliqué une fois (structure de coûts)
        # Élasticité : 0.025 (DG Trésor 2023 - effet modéré car SMIC = 15% masse salariale)
        impact_competitivite = _one_time_level(years_elapsed, -hausse_pct * 0.025)

        # Gini : réduction pour une hausse, appliquée une fois (structure des
        # revenus). Lot 4 : GINI_SMIC_PAR_HAUSSE, centre de la plage tirée des
        # gains par dixième du groupe d'experts sur le SMIC (2017, DG Trésor :
        # graphiques n° 41 et 45), chiffrage statique pour +1 %, extrapolé
        # linéairement (convention déclarée, constants.py § CANAUX GINI).
        # Jusqu'ici −0,03 × hausse, « INSEE 2024 », sans passage retrouvé.
        impact_gini = _one_time_level(years_elapsed, hausse_pct * GINI_SMIC_PAR_HAUSSE)

        # Chômage : Hausse SMIC → Hausse coût travail → Destruction emplois non qualifiés (ONE-TIME)
        # IMPORTANT : Impact NÉGATIF sur emploi (hausse SMIC augmente chômage)
        # Sources: Kramarz & Philippon (2001), Abowd et al. (2000)
        # Élasticité emploi/SMIC = -0.10 à -0.30 pour France (consensus)
        # Mécanisme: Coût travail ↑ → Substitution capital/travail → Destruction emplois bas qualifications
        # Formule conservative: +0.025 pt chômage par % de hausse SMIC (2.5 pt par 100% hausse)
        # Exemple: Hausse 10% (hausse_pct=0.10) → +0.10 * 0.025 = +0.0025 = +0.25 pt chômage
        #          Hausse 5% (hausse_pct=0.05) → +0.05 * 0.025 = +0.00125 = +0.125 pt chômage
        # POSITIF car hausse SMIC augmente le chômage (one-time)
        impact_chomage = _one_time_level(years_elapsed, hausse_pct * 0.025)

        impacts = {
            'depenses': delta_spending,
            'recettes': delta_revenue,
            'fp': delta_fp,
            'aides_sociales': delta_aides,
            'cotisations': delta_cotisations,
            'competitivite': impact_competitivite,
            'gini': impact_gini,
            'chomage': impact_chomage,
            'menages': canaux_menages(salaires_prives=salaires_nets_prives,
                                      remunerations_publiques=delta_fp,
                                      prestations=delta_aides,
                                      prelevements_directs=impot_revenu),
        }

        _log_debug(self.debug_logs,
            f"Y{year}: SMIC {smic_brut}€ brut ({hausse_pct*100:+.1f}%) → "
            f"Paie publique {delta_fp:.2f} Md€, prestations {delta_aides:+.2f} Md€, "
            f"recettes {delta_revenue:+.2f} Md€, solde {delta_revenue-delta_spending:+.2f} Md€"
        )

        return delta_spending, delta_revenue, impacts

    def _apply_taxe_superprofits(self, measure: Dict, params: Dict, year: int, gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Taxe superprofits. NFP: 25% >120% moy → +15 Md€. Temporaire 3 ans (2026-2028). Effets NIVEAU one-time.
        Sources: NFP 2027, OFCE 2024. Voir METHODOLOGIE.md § Mesures Presidentielles 2027.

        Contrat d'entrée (documenté v0.6.7) : sans clé ``intensite``, le handler est
        en mode LEGACY, dont les défauts sont ceux du programme NFP (taux 25 %, seuil
        120 %, tous secteurs). Un bloc VIDE ``{"taxe_superprofits": {}}`` applique
        donc la taxe pleine (+15 Md€/an 2026-2028), pas la mesure inactive : pour
        désactiver le levier, poser ``{"intensite": 0}`` (défaut du moteur) ou
        omettre la clé — les deux sont neutres au bit depuis v0.6.7."""
        # Mode simplifié (slider unique d'intensité) sinon mode legacy.
        # Simplifié : taux = 0.25·i ; seuil = 1.0 + 0.20·i (NFP 100 % →
        # 25 % tous secteurs, seuil 120 %) ; tous_secteurs = i > 0.
        taux_taxe, seuil_hausse, tous_secteurs = _resolve_intensite_or_legacy(
            params,
            lambda i: (0.25 * i, 1.0 + 0.20 * i, i > 0),
            lambda p: (
                p.get('taux', 0.25),
                p.get('seuil_hausse', 1.20),
                p.get('tous_secteurs', True),
            ),
        )

        # Taxe nulle = mesure inactive, neutre sur TOUS les canaux (même garde
        # précoce que les autres handlers). v0.6.7 : à intensité 0, le mode
        # simplifié pose tous_secteurs = False, et la branche « énergie seule »
        # de la compétitivité émettait −0,002 sans qu'aucune taxe soit levée —
        # artefact porté par les 7 scénarios publiés à intensité 0.
        if taux_taxe == 0:
            return 0, 0, {}

        # Année de référence — horloge du levier (v0.7.0).
        years_elapsed = year - self._origine('taxe_superprofits')

        # ===== PHASING : plein effet immédiat dès l'entrée en vigueur =====
        phasing = _year_phasing(years_elapsed, (1.0,))

        # ===== TEMPORAIRE 3 ANS (crise inflation 2022-2024) =====
        # Trois ans d'application, puis les superprofits disparaissent (retour
        # normalité) : 2026-2028 en mode historique, à partir du début du
        # programme sinon (v0.7.0 : « year >= 2029 » écrit en dur jusqu'ici).
        if years_elapsed >= TAXE_SUPERPROFITS_DUREE_ANS:
            return 0, 0, {'recettes': 0}

        # ===== ASSIETTE SUPERPROFITS =====
        if tous_secteurs:
            # Tous secteurs : énergie (40 Md€) + banques (10 Md€) + luxe (5 Md€) + tech (5 Md€)
            superprofits_total = 60.0  # Md€ (2022-2024)
        else:
            # Énergie uniquement (TotalEnergies, Engie, etc.)
            superprofits_total = 40.0  # Md€

        # Ajustement selon seuil : si seuil 150%, seuls les très gros superprofits taxés
        if seuil_hausse > 1.20:
            reduction_assiette = (seuil_hausse - 1.20) / 0.30  # 30% de hausse max
            superprofits_total *= (1 - reduction_assiette * 0.5)

        # ===== RECETTES =====
        delta_revenue = superprofits_total * taux_taxe * phasing

        # Plafond réaliste 20 Md€ — logger.warning visible hors mode debug
        # pour qu'une calibration aberrante ne soit pas masquée par le clip.
        if delta_revenue > 20.0:
            logger.warning(
                "taxe_superprofits Y%d : recettes plafonnées à 20.0 Md€ "
                "(calcul brut : %.1f Md€, taux=%.2f, secteurs=%s)",
                year, delta_revenue, taux_taxe,
                "tous" if tous_secteurs else "energie",
            )
            delta_revenue = 20.0

        # ===== IMPACTS MACROÉCONOMIQUES =====
        # IMPORTANT : Effets NIVEAU (one-time), pas FLUX (recurring)
        # Gini (lot 4, PÉRIMÈTRE) : 0. Impôt payé par des sociétés, sans canal
        # ménages (ci-dessous) : il ne touche pas le revenu disponible des
        # ménages au sens de l'INSEE, comme l'impôt sur les sociétés, dont le
        # Gini est 0 (constants.py § CANAUX GINI). Jusqu'ici −0,01 pour
        # 15 Md€, sans source.
        # PA : aucun effet direct (taxe entreprises, pas ménages)
        # Compétitivité : -0.005 (risque délocalisation marginale)
        impact_gini = 0.0
        impact_competitivite = _one_time_level(
            years_elapsed,
            -0.005 * (delta_revenue / 15) * phasing if tous_secteurs else -0.002,
        )
        impacts = {
            'recettes': delta_revenue,
            'gini': impact_gini,
            'competitivite': impact_competitivite,
            'menages': canaux_menages(),
        }

        _log_debug(self.debug_logs,
            f"Y{year}: Taxe superprofits - Taux {taux_taxe*100:.0f}%, Seuil {seuil_hausse*100:.0f}%, "
            f"Secteurs {'tous' if tous_secteurs else 'énergie'}, Recettes {delta_revenue:.1f} Md€"
        )

        return 0, delta_revenue, impacts

    def _apply_exonerations_salaires(self, measure: Dict, params: Dict, year: int, gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Exonérations hausses salaires. NFP: exo 100% hausses >1% → -12 Md€. Masse salariale 800 Md€. Effets NIVEAU one-time.
        Sources: NFP 2027, OFCE 2024. Voir METHODOLOGIE.md § Mesures Presidentielles 2027."""
        # Mode simplifié (slider unique : exo 100% seuil 1%) sinon legacy.
        taux_exo, seuil = _resolve_intensite_or_legacy(
            params,
            lambda i: (i, 0.01),
            lambda p: (p.get('taux_exoneration', 0.0), p.get('seuil_hausse', 0.01)),
        )

        if taux_exo == 0:
            return 0, 0, {}

        # Année de référence — horloge du levier (v0.7.0).
        years_elapsed = year - self._origine('exonerations_salaires')

        # ===== PHASING : plein effet immédiat dès l'entrée en vigueur =====
        phasing = _year_phasing(years_elapsed, (1.0,))

        # ===== MASSE SALARIALE CONCERNÉE =====
        # Hausse salariale moyenne suit l'inflation observée + ~1pt productivité (consensus OFCE).
        # Borne basse 1% pour éviter les hausses négatives en cas de déflation simulée.
        # Cohérent avec calibration NFP -12 Md€ à inflation 2% (hypothèse de référence).
        masse_salariale_privee = 800.0  # Md€
        hausse_sal_moyenne = max(0.01, inflation + 0.01)

        # Hausses au-dessus du seuil
        hausse_eligibles = max(0, hausse_sal_moyenne - seuil)
        masse_hausse = masse_salariale_privee * hausse_eligibles

        # ===== COÛT EXONÉRATIONS =====
        taux_cotis_patronales = 0.45
        cout_exonerations = masse_hausse * taux_cotis_patronales * taux_exo * phasing

        # ===== EFFET MULTIPLICATEUR =====
        # Si exonération attractive, entreprises augmentent + les salaires
        multiplicateur = 1.5 if taux_exo >= 0.75 else 1.2
        cout_total = cout_exonerations * multiplicateur

        # Plafond 15 Md€ — logger.warning visible hors mode debug pour qu'une
        # calibration aberrante ne soit pas masquée par le clip.
        if cout_total > 15.0:
            logger.warning(
                "exonerations_salaires Y%d : coût plafonné à 15.0 Md€ "
                "(calcul brut : %.1f Md€, taux_exo=%.2f)",
                year, cout_total, taux_exo,
            )
            cout_total = 15.0

        delta_revenue = -cout_total  # Perte recettes cotisations

        # ===== IMPACTS MACROÉCONOMIQUES =====
        # IMPORTANT : Effets NIVEAU (one-time), pas FLUX (recurring)
        # PA (v0.6.8) : aucun effet direct — cotisations PATRONALES, l'emploi
        #   créé passe par le chômage puis la croissance.
        # Gini : PAS D'IMPACT MICRO (incitation entreprises, pas transfert direct garanti)
        # Les hausses de salaires ne sont PAS garanties, seulement incitées
        # Impact Gini vient UNIQUEMENT de l'effet macro (si hausses effectives)
        # Compétitivité : +0.003 (coût travail stable malgré hausses)
        # Tous one-time (NIVEAU) l'année d'entrée en vigueur :
        # Compét — calibration Trésor-Éco 97 (2012) : 22 Md€ allègements
        #   → ~250k emplois par 12 Md€.
        # Chômage — Cahuc & Carcillo 2014 (allègements ciblés), DARES 2019 :
        #   ciblage bas salaires, -0.03 pt par Md€ (12 Md€ → -0.36 pt).
        impact_competitivite = _one_time_level(
            years_elapsed, 0.003 * (cout_total / 12) * phasing
        )
        impact_chomage = _one_time_level(years_elapsed, -0.0003 * cout_total * phasing)

        impacts = {
            'recettes': delta_revenue,
            'competitivite': impact_competitivite,
            'chomage': impact_chomage,
            'menages': canaux_menages(),
        }

        _log_debug(self.debug_logs,
            f"Y{year}: Exonérations salaires - Taux {taux_exo*100:.0f}%, Seuil {seuil*100:.1f}%, "
            f"Coût {cout_total:.1f} Md€"
        )

        return 0, delta_revenue, impacts
