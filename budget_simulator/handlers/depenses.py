"""Section 2 — Maîtrise des dépenses.

Mesures couvertes (6 handlers) :
- ``retraites`` : âge de départ (réf. 62,75 ans), durée de cotisation
  (réf. 42,5 ans) et indexation des pensions. Coefficient stationnaire
  -16 Md€/an pour +1 an d'âge, montée en charge 5 ans (cohortes COR).
  Gini/PA modulés selon la mortalité différentielle et la désindexation.
- ``sante`` : réforme structurelle 3 leviers (hôpital, ambulatoire,
  prévention/organisation, potentiel -30 Md€ en 2030, phasing admin vs
  structurel distinct) + franchise/participation forfaitaire + budget
  prévention absolu (ROI différé 2 ans, plafonné 200 %).
- ``chomage_alloc`` : assurance chômage Unédic. Taux de remplacement %
  (mode v4.5) ou montant Md€ (mode legacy) × durée, dégressivité
  optionnelle. Impacts Gini/PA/chômage one-time sur changement effectif.
- ``asu`` : Allocation Sociale Unique (fusion RSA/Prime activité/APL/
  allocations familiales). Phasing 4 ans, plafonnement 50-70 % SMIC,
  override transition 2026, double effet temporel CT/LT (PA et Gini).
- ``abattement_retraites`` : réforme de l'abattement fiscal sur pensions
  (PLF 2026, forfait 2000 €). Effet ``recettes`` (+4 Md€ régime permanent,
  phasing 2 ans), Gini légèrement progressif one-time.
- ``prestations_indexation`` : indexation des prestations sociales hors
  pensions (RSA/APL/allocations familiales, base 90 Md€). Érosion composée
  si sous-indexation. Neutralisé (anti-double-comptage) quand l'ASU est
  active dans le scénario — prédicat SOURCE UNIQUE
  ``_phasing.asu_is_active(self.mesures)``, l'ASU absorbant exactement
  cette base 90 Md€ et suivant alors le SMIC.

Convention d'application :
- Effets ``gini`` / ``competitivite`` (et parfois ``pouvoir_achat`` /
  ``chomage``) en mode NIVEAU one-time, gated par
  ``self._is_first_year_change(<clé>, params)`` (méthode de l'hôte) ou par
  un suivi cross-année dédié (cf ``chomage_alloc`` ci-dessous). Chaque
  sous-effet a sa propre clé de gating (``retraites_gini``, ``sante``,
  ``chomage_alloc_competitivite``, ``abattement_retraites``,
  ``prestations_indexation``).
- Effet ``pouvoir_achat`` de ``retraites`` et ``prestations_indexation``
  est au contraire RÉCURRENT (suit la désindexation chaque année) —
  PRÉSERVÉ tel quel du monolithe.
- Effet ``depenses`` : négatif = économie. ``abattement_retraites`` est le
  seul handler de la section à porter son effet sur ``recettes``.
- Voir docs/METHODOLOGIE.md § "Effets NIVEAU vs FLUX" pour le contrat de
  gating, et § "Sante" pour le détail des leviers santé.

Sources principales :
- COR Rapport annuel 2024, OFCE Brief 124 (15/02/2024) — retraites.
- PLFSS 2026, IGAS 2024, CCSS 2024 — santé.
- Unédic 2025, OFCE 2023, INSEE 2024, France Stratégie 2019 — chômage.
- IFRAP 2025, HCFPS 2024, DREES, France Stratégie 2024, IPP Bozio 2023 — ASU.
- PLF 2026, DGFiP, France Stratégie 2025 — abattement retraites.
- PLFSS 2026, OFCE 2024, IPP 2023, DREES — prestations indexation.

Couplages avec ``BudgetSimulatorV45`` (instance hôte du mixin) :
- LIT la méthode ``self._is_first_year_change`` et le sink de logs
  ``self.debug_logs`` (via ``_log_debug``, sans incidence sur les sorties
  de simulation), fournis par la base class (simulator.py).
- ``_apply_asu`` n'écrit AUCUN attribut d'instance partagé. Son phasing
  de montée en charge (4 ans) vient de la SOURCE UNIQUE
  ``handlers._phasing.asu_phasing(self.mesures, year)``, la même que le
  consommateur ``efficience._apply_fraude_sociale`` utilise pour son
  anti-double-comptage (-30 %·phasing). L'ancien état d'instance
  ``self.asu_active``/``self.asu_phasing`` (couplage producteur/
  consommateur fragile, sensible à l'ordre d'exécution) a été SUPPRIMÉ
  (état mort une fois le consommateur rendu auto-suffisant — cf
  efficience.py). Plus d'init/reset hôte à maintenir pour cet état.
- ÉCRIT/LIT ``self._chomage_params_prev`` dans ``_apply_chomage_alloc``
  comme état cross-année : détecte un changement effectif des paramètres
  (taux/durée/dégressivité) pour gater l'impact Gini/PA one-time, là où
  ``_is_first_year_change`` ne suffit pas (sémantique de re-trigger
  propre au handler, initialisée paresseusement). La suppression de cet
  attribut entre deux simulations est à la charge de l'hôte.
- Aucun handler n'appelle un handler d'un autre mixin (invariant ADR).

Tolérance ponctuelle au contrat ``ImpactsDict`` : ``_apply_asu`` ajoute
une clé ``description`` (str) à son dict d'impacts. Comme ``rabot_details``
(cf handlers/_types.py), c'est un écart toléré : le moteur filtre par type
avant clip/agrégation, donc pas d'erreur runtime. À aplatir lors d'un
futur chantier de durcissement du contrat (typage strict) — ne pas
reproduire le pattern.
"""
from typing import TYPE_CHECKING, Dict, Tuple

from ..constants import PHASING_RETRAITES_5ANS, POLICY_START_YEAR
from .._logging import _log_debug
from ._phasing import _year_phasing, asu_is_active, asu_phasing
from ._types import ImpactsDict


# Idiome mixin-self typing : NE PAS factoriser dans _types.py (casse la
# liaison self mypy + risque MRO). Réplication volontaire 7×. Cf Lot D.
if TYPE_CHECKING:
    from ._types import _SimulatorState

    _MixinBase = _SimulatorState
else:
    _MixinBase = object


class DepensesMixin(_MixinBase):
    """Handlers Section 2 — Maîtrise des dépenses."""

    def _apply_retraites(self, measure: Dict, params: Dict, year: int, gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        # Convention : les handlers ne sont jamais appeles en annee baseline (year=2025).
        # Garde defensive : si appel direct hors boucle simulate(), retourne neutre.
        if year < 2026:
            return 0, 0, {}
        age = params.get('age_depart', 62.75)
        indexation = params.get('indexation', 1.0)
        duration = params.get('duree_cotisation', 42.5)
        delta_spending = 0
        # Reference 2025: 62.75 ans (62 ans et 9 mois)
        # COR 2024: recul/avance suit montee en charge cohortes (5 ans pour plein effet).
        # Coefficient stationnaire recalibre : -16 Md€/an pour passage 62.75 → 64 ans
        # (cible COR Rapport annuel 2024 "Effets financiers de la reforme 2023" tableau 1.7,
        # ~17.7 Md€ en 2030 et 23 Md€ stationnaire).
        year_idx = max(0, year - POLICY_START_YEAR)
        phasing_age = _year_phasing(year_idx, PHASING_RETRAITES_5ANS)
        if age > 62.75:
            delta_spending = -16.0 * (age - 62.75) * phasing_age
        elif age < 62.75:
            delta_spending = 16.0 * (62.75 - age) * phasing_age
        # Reference 2025: 42.5 ans (170 trimestres)
        # Phasing identique 5 ans, coefficient recalibre ×2 pour coherence.
        phasing_duree = phasing_age
        if duration > 42.5:
            delta_spending -= 4.0 * (duration - 42.5) * phasing_duree
        elif duration < 42.5:
            delta_spending += 4.0 * (42.5 - duration) * phasing_duree
        # Indexation : phasing existant 7 ans (deja phase, calibration inchangee)
        if indexation < 1.0:
            years_effect = min(year_idx + 1, 7)
            delta_spending -= 1.5 * (1 - indexation) * years_effect

        # === IMPACTS MACROÉCONOMIQUES ===
        # Gini : Âge départ ↑ = LÉGÈREMENT INÉGALITAIRE
        # Recul âge pénalise davantage classes populaires (mortalité différentielle)
        # Ouvriers : espérance vie -6 ans vs cadres, taux emploi 55-64 ans 52% vs 71%
        # Règle : 62.75→64 ans = +0.001 Gini (COR 2024 "effet hétérogène espérance vie")
        gini_age = 0.001 * (age - 62.75) / 1.25

        # Gini : Indexation ↓ = paupérisation retraités (régressif)
        # Règle : Indexation 100%→90% = +0.005 Gini (OFCE Brief 124, 15/02/2024)
        gini_indexation = 0.005 * (1.0 - indexation)

        # Guard Gini: plein effet année 1, 10% résiduel les années suivantes
        # (flux annuel des nouvelles cohortes de retraités impactées)
        gini_params = {'age': age, 'indexation': indexation}
        if self._is_first_year_change('retraites_gini', gini_params):
            gini = gini_age + gini_indexation
        else:
            gini = (gini_age + gini_indexation) * 0.10

        # Pouvoir d'achat : Impact agrégé via retraités (~26% RDB).
        # Formule : -0.007 × (1 - indexation), appliquée chaque année (effet récurrent).
        # Calibration OFCE Brief 124 (15/02/2024) : élasticité PA-retraités/désindexation
        # ≈ -0.7%/an PA agrégé pour gel TOTAL (indexation=0), proportionnelle au ratio
        # d'écart à la pleine indexation. Cumulé sur 5 ans = -3.5%.
        pouvoir_achat = -0.007 * (1.0 - indexation)

        # Compétitivité : Pas d'impact direct
        competitivite = 0

        impacts = {
            'depenses': delta_spending,
            'gini': gini,
            'pouvoir_achat': pouvoir_achat,
            'competitivite': competitivite
        }
        return delta_spending, 0, impacts

    def _apply_sante(self, measure: Dict, params: Dict, year: int, gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """
        Mesures santé v2025.1 - Réforme structurelle avec 3 leviers d'action

        Nouveaux paramètres (0-1):
        - effort_hopital: Réforme hospitalière (max -13 Md€)
        - effort_ambu: Réforme ambulatoire (max -10 Md€)
        - effort_prev_org: Prévention & organisation (max -7 Md€)

        Potentiel total: -30 Md€ en 2030

        Phasing progressif:
        - Admin: 50%(2026) → 80%(2027) → 100%(2028+)
        - Structural: 20%(2026) → 40%(2027) → 60%(2028) → 80%(2029) → 100%(2030+)

        Sources: PLFSS 2026, IGAS 2024, CCSS 2024
        Voir METHODOLOGIE.md § Sante
        """

        # === PARAMETRES ===
        # Les sliders sont maintenant en % (0-100), on les convertit en 0-1
        effort_hopital = params.get('effort_hopital', 0) / 100
        effort_ambu = params.get('effort_ambu', 0) / 100
        effort_prev_org = params.get('effort_prev_org', 0) / 100

        # === CONSTANTES ===
        # Potentiels max (Md€)
        POT_HOPITAL = 13.0     # Réforme hospitalière (100% structurel)
        POT_AMBU = 10.0        # Ambulatoire (70% struct + 30% admin)
        POT_PREV_ORG = 7.0     # Prévention & organisation (80% admin + 20% struct)

        # === PHASING ===
        # Déterminer les coefficients de phasing selon l'année
        if year <= 2025:
            phasing_admin = 0
            phasing_struct = 0
        elif year == 2026:
            phasing_admin = 0.50
            phasing_struct = 0.20
        elif year == 2027:
            phasing_admin = 0.80
            phasing_struct = 0.40
        elif year == 2028:
            phasing_admin = 1.00
            phasing_struct = 0.60
        elif year == 2029:
            phasing_admin = 1.00
            phasing_struct = 0.80
        else:  # 2030+
            phasing_admin = 1.00
            phasing_struct = 1.00

        # === LEVIER 1: HOPITAL (100% structurel) ===
        # Composantes:
        # - Réorganisation filières (-5 Md€)
        # - Rationalisation plateau technique (-4 Md€)
        # - Optimisation achats/logistique (-2 Md€)
        # - Efficience RH médicale (-2 Md€)
        econ_hopital = -POT_HOPITAL * effort_hopital * phasing_struct

        # === LEVIER 2: AMBULATOIRE (mixte 70% struct + 30% admin) ===
        # Composantes:
        # - Virage ambulatoire/HAD (-6 Md€, structurel)
        # - Contrôle prescriptions/iatrogénie (-2 Md€, admin)
        # - Forfaits parcours coordonnés (-2 Md€, mixte)
        phasing_ambu = (0.70 * phasing_struct) + (0.30 * phasing_admin)
        econ_ambu = -POT_AMBU * effort_ambu * phasing_ambu

        # === LEVIER 3: PREVENTION & ORGANISATION (mixte 80% admin + 20% struct) ===
        # Composantes:
        # - Numérique santé/DMP (-3 Md€, admin)
        # - Prévention/dépistage (-2 Md€, admin rapide + ROI moyen terme)
        # - Pertinence soins/référentiels HAS (-2 Md€, mixte)
        phasing_prev_org = (0.80 * phasing_admin) + (0.20 * phasing_struct)
        econ_prev_org = -POT_PREV_ORG * effort_prev_org * phasing_prev_org

        # === MESURES ADDITIONNELLES (indépendantes des réformes structurelles) ===

        # MESURE 1: FRANCHISE MÉDICALE ET PARTICIPATION FORFAITAIRE (0-200%)
        # Paramètre distinct du levier "effort_prev_org" (qui concerne l'efficience organisation)
        # Ici: impact direct sur reste à charge patients
        BASE_2025_BRUT = 2.52  # Recettes franchise+participation actuelles (Md€)
        RECOUVREMENT_RATE = 0.93  # Taux de recouvrement sur nouvelles créances
        RENONCEMENT_IMPACT = 0.10  # Baisse du gain brut par renoncement aux soins

        taux_franchise = params.get('franchise_participation_taux', 100)

        if taux_franchise <= 100:
            # Diminution ou suppression : surcoût croissant
            # À 0% → +2.52 Md€ (perte totale des recettes)
            # À 100% → 0 Md€ (statu quo)
            delta_franchise = BASE_2025_BRUT * (1 - taux_franchise / 100)
        else:
            # Augmentation : économies additionnelles
            # Gain brut théorique : 2.0 Md€ si doublement complet
            # Ajusté par : renoncement aux soins (-10%) et non-recouvrement (-7%)
            gain_brut = (taux_franchise - 100) / 100 * 2.0
            gain_net = gain_brut * (1 - RENONCEMENT_IMPACT) * RECOUVREMENT_RATE
            delta_franchise = -gain_net  # Négatif car économies

        # MESURE 2: PRÉVENTION (budget absolu 5-8 Md€)
        # Paramètre distinct du levier "effort_prev_org" (qui optimise la prévention existante)
        # Ici: investissement additionnel pour AUGMENTER le volume prévention
        # Base France 2025: 5 Md€ (~2% dépenses santé) vs OCDE: 8 Md€ (~2.8%)
        prevention_budget_montant = params.get('prevention_budget', 5.0)  # Md€ absolus
        prevention_var = prevention_budget_montant - 5.0  # Différentiel par rapport à la base
        delta_prevention = prevention_var  # Surcoût immédiat

        # ROI après 2 ans : 25% par an, plafonné à 200% après 8 ans
        # Littérature empirique (IGAS 2023, OMS 2018, Lancet 2019):
        # - Dépistages cancers : ROI 1:3 immédiat (détection précoce évite chimio lourde)
        # - Vaccins grippe : ROI 1:4 même année (évite hospitalisations hiver)
        # - Contrôles diabète/HTA : ROI 1:2-3 en 6-12 mois (évite complications)
        # → Hypothèse conservatrice : délai 2 ans, 25%/an cumulatif, plafond 200%
        if year >= 2027 and prevention_var > 0:  # DÉLAI RÉDUIT : 2 ans au lieu de 3
            annees_roi = year - POLICY_START_YEAR  # Années depuis début ROI (2027 = année 1)
            roi_cumul = min(annees_roi * 0.25, 2.0)  # 25%/an, max 200% après 8 ans
            economie_roi = prevention_var * roi_cumul
            delta_prevention = prevention_var - economie_roi
            # Exemples avec +3 Md€:
            # 2027 (an 1): +3 - (3 × 0.25) = +2.25 Md€
            # 2030 (an 4): +3 - (3 × 1.00) = 0 Md€ (break-even en 4 ans)
            # 2034 (an 8): +3 - (3 × 2.00) = -3 Md€ (investissement gratuit!)

        # === TOTAL (réformes structurelles + mesures additionnelles) ===
        delta_spending = econ_hopital + econ_ambu + econ_prev_org + delta_franchise + delta_prevention

        # === PIB SANTE ===
        # Dépenses santé France 2025: 342 Md€ = 11.4% PIB
        # Avec effort max (-30 Md€ en 2030): 312 Md€ = 10.6% PIB
        depenses_sante_base = 342.0  # Md€
        depenses_sante_nouvelle = depenses_sante_base + delta_spending  # delta_spending négatif
        pib_sante_pct = (depenses_sante_nouvelle / gdp) * 100

        # === IMPACTS MACROECONOMIQUES ===
        # Gini: Impact ONE-TIME (réforme structurelle, première année changement)
        params_sante = {
            'hopital': effort_hopital,
            'ambu': effort_ambu,
            'prev_org': effort_prev_org,
            'franchise': taux_franchise,
            'prevention': prevention_budget_montant
        }
        if self._is_first_year_change('sante', params_sante):
            # Gini: Réforme progressive = impact neutre à légèrement positif
            # Améliore accès soins primaires, réduit reste à charge hospitalier (effet redistributif)
            # ATTENTION : "effort" signifie PRODUCTIVITÉ (faire mieux avec moins), pas austérité qualité
            gini_reforme = -0.002 * (effort_hopital + effort_ambu + effort_prev_org) / 3

            # Gini: Franchises ↑ = impact RÉGRESSIF (touche + les pauvres)
            # Règle : Franchises 100%→200% (Bayrou) = +0.003 Gini (OFCE 2024)
            gini_franchise = 0.003 * (taux_franchise - 100) / 100

            gini = gini_reforme + gini_franchise
        else:
            # Années suivantes : impact déjà intégré
            gini = 0.0

        # Pouvoir d'achat: Amélioration via réduction reste à charge
        # Gains PRODUCTIVITÉ santé → moins de coûts pour usagers → PA augmente
        pouvoir_achat_reforme = 0.003 * (effort_hopital + effort_ambu + effort_prev_org) / 3

        # Pouvoir d'achat: Impact franchises sur reste à charge
        # Règle : Franchises 100%→200% = -0.001 PA (INSEE 2024)
        pouvoir_achat_franchise = -0.001 * (taux_franchise - 100) / 100

        pouvoir_achat = pouvoir_achat_reforme + pouvoir_achat_franchise

        # Compétitivité: Réduction charges via efficience système
        # PRODUCTIVITÉ santé → coûts sécu maîtrisés → moins de prélèvements → compétitivité
        competitivite = 0.001 * (effort_hopital + effort_ambu + effort_prev_org) / 3

        impacts = {
            'depenses': delta_spending,
            'hopital': econ_hopital,
            'ambulatoire': econ_ambu,
            'prevention_organisation': econ_prev_org,
            'franchise_forfaits': delta_franchise,
            'prevention_budget': delta_prevention,
            'pib_sante_pct': pib_sante_pct,
            'phasing_admin': phasing_admin,
            'phasing_struct': phasing_struct,
            'gini': gini,
            'pouvoir_achat': pouvoir_achat,
            'competitivite': competitivite
        }

        # Debug
        if hasattr(self, 'debug_logs'):
            _log_debug(self.debug_logs,
                f"Y{year}: Santé v2025.1 - Hôpital={econ_hopital:.1f}, "
                f"Ambu={econ_ambu:.1f}, Prev/Org={econ_prev_org:.1f}, "
                f"Franchise={delta_franchise:+.2f}, PrevBudget={delta_prevention:+.2f}, "
                f"Total={delta_spending:.1f} Md€ (PIB santé={pib_sante_pct:.1f}%)"
            )

        return delta_spending, 0, impacts

    def _apply_chomage_alloc(self, measure: Dict, params: Dict, year: int, gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """
        Allocations chômage - Assurance chômage (Unédic)

        Frontend v4.5+ : Taux de remplacement % (0.45-0.80) + Durée (12-36 mois)
        Legacy : Montant Md€ (30-60) + Durée (12-36 mois)

        Conversion taux → Md€ :
        - Base 2025 (réforme avril) : 60% taux × 18 mois = 40 Md€
        - Formule : Montant = 40 × (taux/0.60) × (durée/18)

        Sources : Unédic 2025, OFCE 2023, INSEE 2024
        Réforme avril 2025 : 18 mois (<55 ans), 22.5 mois (55-56 ans), 27 mois (≥57 ans)
        """
        # Constantes de référence (réforme avril 2025)
        DUREE_REF = 18  # mois - nouvelle référence
        MONTANT_REF = 40  # Md€ pour 60% et 18 mois

        duree = params.get('duree', DUREE_REF)
        if duree <= 0:
            duree = DUREE_REF
        degressivite = params.get('degressivite', False)

        # Tracker première année activation (pour impact Gini one-time)
        if not hasattr(self, '_chomage_params_prev'):
            self._chomage_params_prev = {'taux': 0.60, 'duree': DUREE_REF, 'degressivite': False}

        # Compatibilité : Nouveau mode (taux %) ou Legacy mode (Md€)
        if 'taux_remplacement' in params:
            # Mode nouveau : Taux de remplacement % (0.45-0.80)
            taux_remplacement = params.get('taux_remplacement', 0.60)
            montant = MONTANT_REF * (taux_remplacement / 0.60) * (duree / DUREE_REF)
        else:
            # Mode legacy : Montant direct en Md€
            montant = params.get('montant', MONTANT_REF)
            taux_remplacement = 0.60 * (montant / MONTANT_REF) * (DUREE_REF / duree)  # Rétro-conversion pour logs

        # Détecter si paramètres ont changé (première année activation)
        # IMPORTANT: Inclure dégressivité pour tracker son activation
        params_current = {'taux': taux_remplacement, 'duree': duree, 'degressivite': degressivite}
        is_first_year = (params_current != self._chomage_params_prev)
        self._chomage_params_prev = params_current

        delta_montant = (montant - MONTANT_REF)
        delta_duree = (duree - DUREE_REF) / DUREE_REF * 12 if duree != DUREE_REF else 0  # 12 Md€ pour variation proportionnelle
        delta_spending = delta_montant + delta_duree
        if degressivite:
            delta_spending *= 0.85 if delta_spending > 0 else 1.15

        # === IMPACTS MACROÉCONOMIQUES ===
        # IMPORTANT : Impacts ONE-TIME uniquement (demande, effet niveau)
        # Évite cumul absurde sur 10 ans
        if is_first_year:
            # Gini : Baisse allocations = impact FORT chômeurs (régressif)
            # Règle : Montant 40→35 Md€ = +0.004 Gini (OFCE 2023)
            gini_montant = 0.004 * (MONTANT_REF - montant) / 5

            # Gini : Durée ↓ = impact chômeurs longue durée (régressif)
            # Règle : Durée 18→12 mois = +0.002 Gini
            gini_duree = 0.002 * (DUREE_REF - duree) / 6

            gini = gini_montant + gini_duree

            # Pouvoir d'achat : Impact FORT sur chômeurs (ONE-TIME)
            # Règle : Montant 40→35 Md€ = -0.002 PA (INSEE 2024)
            pouvoir_achat = -0.002 * (MONTANT_REF - montant) / 5
        else:
            # Années suivantes : impacts déjà intégrés dans indices courants
            gini = 0.0
            pouvoir_achat = 0.0

        # Compétitivité : Léger (flexibilité marché du travail) — ONE-TIME
        # Règle : Baisse alloc = +0.0005 compétitivité (réforme Hartz IV)
        if self._is_first_year_change('chomage_alloc_competitivite', params_current):
            competitivite = 0.0005 * (MONTANT_REF - montant) / 5
        else:
            competitivite = 0.0

        # Chômage : Incitation emploi via dégressivité (ONE-TIME)
        # Source: France Stratégie 2019, réforme assurance chômage 2019
        # Dégressivité + durée réduite → Incitation retour emploi rapide
        # Impact: -0.10 à -0.15 points (France Stratégie)
        if is_first_year and degressivite:
            # Dégressivité activée → Fort impact incitation
            impact_chomage = -0.0015  # -0.15 points
        elif is_first_year and duree < DUREE_REF:
            # Durée réduite sous la référence → Impact modéré
            impact_chomage = -0.0005 * (DUREE_REF - duree) / 6  # Durée 12m → -0.05 pt
        else:
            impact_chomage = 0.0

        impacts = {
            'depenses': delta_spending,
            'gini': gini,
            'pouvoir_achat': pouvoir_achat,
            'competitivite': competitivite,
            'chomage': impact_chomage
        }
        _log_debug(self.debug_logs, f"Y{year}: Chômage - taux={taux_remplacement*100:.0f}%, durée={duree}m, montant={montant:.1f}Md€, delta={delta_spending:.1f}Md€")
        return delta_spending, 0, impacts

    def _apply_asu(self, measure: Dict, params: Dict, year: int, gdp: float,
                   inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """
        Allocation Sociale Unique (ASU) - Fusion RSA/Prime activité/APL/Allocations familiales
        Plafond variable: 50-70% SMIC net (~700-1000€ pour personne seule)

        Paramètres:
        - asu_activation (0/1): Activation de l'ASU (0=système actuel, 1=ASU activée)
        - asu_plafonnement (0.5-0.7): Niveau de plafonnement (50-70% du SMIC)

        Budget absorbé (90 Md€): RSA (13) + Prime activité (10) + APL (15) + Allocations familiales (52)

        Économies totales (HORS fraude - déjà comptée dans fraude_sociale):
        Composantes fixes:
        - Simplification gestion CAF/MSA/France Travail: +6.0 Md€ (médiane IFRAP)
        - Doublons CAF/régions/urbanisme: +1.5 Md€ (HCFPS 2024)
        - Fraude structurelle (contrôles automatisés): +2.0 Md€ (30% des 6.3 Md€ erreurs CAF)
        - Protection vulnérables (majorations + complément): -2.0 Md€ (DREES)

        Composante variable (plafonnement):
        - Plafonnement 50%: +8.0 Md€ (effet maximum sur hauts RSA + APL)
        - Plafonnement 60%: +6.0 Md€ (médian, équilibre)
        - Plafonnement 70%: +4.0 Md€ (conservateur, transitions douces)

        Bonus emploi (si plafonnement ≤ 60%):
        - Incitation travail (prime reprise emploi intégrée): jusqu'à +1.0 Md€ économies chômage

        ATTENTION: Gains fraude IA (+3-6 Md€) EXCLUS pour éviter double-comptage
        avec le slider "Fraude sociale" qui réduit son potentiel de 30% si ASU active.

        MODÉLISATION TEMPORALITÉ CT/LT :
        Court terme (2026-2027) :
        - PA : Négatif (plafonnement réduit prestations pour certains allocataires)
        - Gini : Mixte (perte concentrée sur hauts RSA si plafond strict)

        Long terme (2028+) :
        - PA : Positif (incitation emploi → 200k retours emploi estimés)
        - Gini : Amélioration (réduction pauvreté via emploi compense pertes initiales)

        Sources: IFRAP 2025, HCFPS 2024, Cour des comptes, DREES, AN Rapport n°692, CAF,
                 France Stratégie 2024, IPP 2023
        """
        # CONTRAT (cf. docs/MEASURE_REGISTRY.md) : asu_activation /
        # asu_plafonnement sont lus ici depuis `params` = mesures['asu']
        # (source canonique, IDENTIQUE à celle lue par
        # _phasing.asu_is_active — le prédicat booléen anti-double-comptage
        # consommé par _apply_prestations_indexation et, via asu_phasing,
        # par la fraude sociale). Pas d'accesseur partagé volontairement :
        # _apply_asu a besoin des VALEURS, asu_is_active ne renvoie qu'un
        # bool — les router ensemble exigerait une régén golden auditée
        # pour ~zéro gain (dette Item 2 Niveau 2 : documentée, non
        # refactorée).
        activation = params.get('asu_activation', 0)  # 0 ou 1
        plafonnement = params.get('asu_plafonnement', 0.65)  # 0.5-0.7

        # Clamp plafonnement dans la plage valide
        plafonnement = max(0.5, min(0.7, plafonnement))

        if activation == 0:
            return 0.0, 0.0, {}

        # === CONSTANTES ÉCONOMIQUES (chiffres conservateurs validés) ===
        ECO_SIMPLIFICATION = 6.0  # Md€/an (médiane IFRAP: fusion CAF/MSA/FT)
        ECO_DOUBLONS = 1.5        # Md€/an (HCFPS 2024: CAF/régions/urbanisme)
        ECO_FRAUDE_STRUCT = 2.0   # Md€/an (30% des 6.3 Md€ erreurs CAF détectables par IA)
        COUT_PROTECTION = 2.0     # Md€/an (majorations handicap/isolement + complément transition)

        # Économies plafonnement (dépend du niveau choisi, non-linéaire)
        # Formule calibrée sur budget réel: RSA 13 + Prime 10 + APL 15 + Famille 52 = 90 Md€
        if plafonnement <= 0.55:
            eco_plafonnement = 8.0  # Plafonnement strict (50-55%)
        elif plafonnement <= 0.65:
            # Interpolation linéaire: 55% → 8 Md€, 60% → 6 Md€, 65% → 5 Md€
            eco_plafonnement = 8.0 - (plafonnement - 0.50) * 20.0
        else:
            # Plafonnement souple (65-70%)
            eco_plafonnement = 4.0

        # Bonus emploi: si plafonnement ≤ 60%, gain net travail > allocation incite reprise emploi
        # Prime reprise emploi intégrée → réduction dépenses chômage
        if plafonnement <= 0.60:
            bonus_emploi = (0.60 - plafonnement) * 10.0  # Max 1.0 Md€ à 50%
        else:
            bonus_emploi = 0.0

        # === PHASING PROGRESSIF (4 ans) — source unique partagée ===
        # 2026 pilote → 2029+ généralisé. Même calendrier que
        # l'anti-double-comptage côté fraude_sociale (cf asu_phasing).
        phasing = asu_phasing(self.mesures, year)

        # === CALCUL ÉCONOMIES ===
        # Convention: delta_spending NÉGATIF = économies (réduction dépenses)
        # OVERRIDE_2026 : surcoût net de transition pilote (10 départements, IA en
        # déploiement). Choix conservateur (cf. IGF 2024) : écrase le calcul ramping 25%
        # car les économies théoriques Y1 sont jugées trop optimistes. En contrepartie,
        # Y1 devient insensible au paramètre `plafonnement` — seuls Y2+ y répondent.
        OVERRIDE_2026_TRANSITION = 0.5  # Md€, coût net temporaire conservateur
        if year == 2026:
            delta_spending = OVERRIDE_2026_TRANSITION
        else:  # 2027+
            # Économies récurrentes progressives (phasing 50% → 75% → 100%)
            eco_totale = (ECO_SIMPLIFICATION + ECO_DOUBLONS + ECO_FRAUDE_STRUCT +
                         eco_plafonnement + bonus_emploi - COUT_PROTECTION)
            eco_nette = eco_totale * phasing
            delta_spending = -eco_nette  # Signe négatif = économies
            # Exemple plafonnement 60%:
            # 2027 (50%): -(6+1.5+2+6+0.4-2)×0.5 = -6.95 Md€
            # 2028 (75%): -(13.9)×0.75 = -10.4 Md€
            # 2029+ (100%): -(13.9)×1.0 = -13.9 Md€

        # Pas d'impact recettes direct (neutre fiscalement)
        delta_revenue = 0.0

        # === IMPACTS MACROÉCONOMIQUES ===
        impacts = {
            'depenses': delta_spending,
            'recettes': delta_revenue,
            'description': f'ASU plafond {plafonnement*100:.0f}% SMIC - Simpl.+doublons+plafonnement',
        }

        # === POUVOIR D'ACHAT : DOUBLE EFFET TEMPOREL ===
        # 1) EFFET DIRECT (immédiat) : Plafonnement réduit prestations
        # Impact sur 3.5M allocataires RSA/APL (8% population)
        # Plafond 50% = -200€/mois pour hauts RSA → -0.06% PA agrégé (vs 0.70 baseline)
        # Plafond 70% = impact nul (statu quo)
        pa_direct = -0.003 * (0.70 - plafonnement)  # coefficient appliqué à (0.70 - plafond)

        # 2) EFFET EMPLOI (différé, année 3+) : Incitation travail → hausse revenus
        # Hypothèse réaliste IPP Bozio 2023 : 50k retours emploi (vs 200k optimiste France
        # Stratégie 2024). 50k × 1400€ × 12 = 0.85 Md€ ≈ 0.04% RDB → +0.04% PA à plafond 50%.
        # Cohérent avec l'hypothèse 50k retours du bloc Gini LT ci-dessous.
        if year >= 2028:  # Délai comportemental 2-3 ans
            pa_emploi = 0.0015 * (0.70 - plafonnement)  # +0.03% à 50%, 0% à 70%
        else:
            pa_emploi = 0.0

        # TOTAL PA : Négatif CT, positif LT si plafond bas
        impacts['pouvoir_achat'] = (pa_direct + pa_emploi) * phasing

        # === GINI : VISION RÉALISTE - ASU N'EST PAS MIRACLE REDISTRIBUTIF ===
        # IMPORTANT : ASU = simplification administrative avec effets redistributifs AMBIGUS
        #
        # RÉALITÉ EMPIRIQUE (France Stratégie 2019, OFCE 2024, IPP 2023) :
        # - Élasticité emploi faible (0.1-0.3) : incitations financières créent PEU d'emplois
        # - Plafond 50% = RÉGRESSIF : Perdants (1.5M cumulards -150€/mois) > Gagnants (600k non-recours +120€/mois)
        # - Retours emploi réalistes = 50k (et non 200k optimiste) car chômage = problème STRUCTUREL
        # - ASU redistributif SEULEMENT SI : plancher ≥ RSA ET plafond ≥ 70%

        if year <= 2027:  # COURT TERME (avant effets emploi hypothétiques)
            # 1) EFFET DOMINANT : Plafonnement frappe les plus pauvres (RÉGRESSIF)
            # 1.5M ménages cumulards (familles monoparentales, handicap) perdent -50 à -200€/mois
            if plafonnement <= 0.55:
                # Plafond 50% = perte moyenne -150€/mois pour 1.5M ménages
                gini_plafonnement = +0.003 * (0.55 - plafonnement) / 0.05  # +0.003 à 50%
            elif plafonnement <= 0.65:
                # Plafond 65% = perte moyenne -50€/mois
                gini_plafonnement = +0.001  # Léger régressif
            elif plafonnement <= 0.75:
                # Plafond 75% = pertes marginales
                gini_plafonnement = +0.0003
            else:
                gini_plafonnement = 0.0  # Neutre au-dessus de 75%

            # 2) EFFET COMPENSATEUR PARTIEL : Réduction non-recours (600k ménages)
            # Gain +100-150€/mois mais pour ménages MOINS pauvres que cumulards
            gini_non_recours = -0.001  # OFCE 2019 : non-recours 34%→10% = -0.001 Gini

            # TOTAL CT : RÉGRESSIF à 50%, neutre à 65%, léger progressif à 75%
            gini = gini_plafonnement + gini_non_recours

        else:  # LONG TERME (2028+, effets emploi HYPOTHÉTIQUES)
            # 3) EFFET EMPLOI RÉALISTE (divisé par 4 vs hypothèse optimiste)
            # Retours emploi = 50k personnes (et non 200k) car :
            # - Chômage RSA = majoritairement STRUCTUREL (qualif, santé, garde enfants, discrimination)
            # - Élasticité emploi faible (0.1-0.3) : incitations $ créent peu d'emplois
            if plafonnement <= 0.55:
                # 50k retours emploi × 1400€/mois × 12 = 0.84 Md€
                gini_emploi = -0.0005  # Divisé par 4 vs ancien -0.002
            elif plafonnement <= 0.65:
                # 25k retours emploi
                gini_emploi = -0.00025  # Divisé par 4 vs ancien -0.001
            else:
                # Effet emploi négligeable si plafond élevé
                gini_emploi = 0.0

            # Plafonnement + non-recours (effets permanents)
            if plafonnement <= 0.55:
                # Pertes permanentes 1.5M ménages > gains emploi 50k
                gini_plafonnement = +0.0025  # Légèrement augmenté (emploi compense moins)
            elif plafonnement <= 0.65:
                # Pertes modérées, emploi compense partiellement
                gini_plafonnement = +0.0008
            elif plafonnement <= 0.75:
                # Quasi neutre
                gini_plafonnement = +0.0002
            else:
                gini_plafonnement = 0.0

            gini_non_recours = -0.001

            # TOTAL LT : Neutre à légèrement régressif (50%), neutre (65%), légèrement progressif (75%)
            gini = gini_plafonnement + gini_non_recours + gini_emploi

        impacts['gini'] = gini * phasing

        # === COMPÉTITIVITÉ : SIMPLIFICATION ADMIN vs RISQUE SOCIAL ===
        # ASU = simplification majeure (fusion CAF/MSA/France Travail)
        if year <= 2027:  # COURT TERME : Simplification domine
            # Effet positif : Gain temps administratif entreprises, climat affaires
            competitivite_asu = 0.001 * phasing  # +0.001 (effet admin)
        else:  # LONG TERME : Dépend du plafonnement
            if plafonnement <= 0.55:
                # Plafond très bas → risque social compense partiellement simplification
                competitivite_asu = 0.0005
            elif plafonnement <= 0.65:
                # Plafond modéré → effet positif net
                competitivite_asu = 0.001
            else:
                # Plafond élevé → effet positif maximal
                competitivite_asu = 0.0015

        impacts['competitivite'] = competitivite_asu

        # Chômage: incitation emploi via gain net travail (ONE-TIME)
        # Effet structurel sur NAIRU, pas flux annuel récurrent
        # Coefficient 3.0 (médian entre 2 et 5)
        # Source: France Stratégie 2024, études prime activité
        # Effet dès 2028 (montée en charge nécessaire)
        if year >= 2028 and plafonnement <= 0.65:
            # ONE-TIME: Impact appliqué UNIQUEMENT en 2028 (année activation effet emploi)
            # Années suivantes: niveau maintenu via convergence NAIRU, pas d'impact additionnel
            if year == 2028:
                effet_chomage = -0.002 * (0.70 - plafonnement) * 10.0  # Max -0.1 point à 50%
                impacts['chomage'] = effet_chomage * phasing * 3.0  # ONE-TIME en 2028

        _log_debug(self.debug_logs,
                   f"Y{year}: ASU plaf={plafonnement*100:.0f}% - phasing={phasing*100:.0f}%, "
                   f"éco_plaf={eco_plafonnement:.1f}Md€, bonus_emploi={bonus_emploi:.1f}Md€, "
                   f"total={delta_spending:.1f}Md€")

        return delta_spending, delta_revenue, impacts

    # =======================================================================
    # NOUVELLES MESURES 2026 (PLF/PLFSS)
    # =======================================================================

    def _apply_abattement_retraites(self, measure: Dict, params: Dict, year: int,
                                     gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """
        Réforme abattement fiscal sur pensions de retraite

        Système actuel (2025):
        - Abattement 10% sur pensions
        - Plancher: 450€ par personne
        - Plafond: 4399€ par foyer fiscal

        Réforme PLF 2026 (rejetée en commission):
        - Abattement forfaitaire: 2000€ par personne
        - Sans plafond (sauf montant brut pension)

        Impact budgétaire: +1.2 Md€ (2026) → +4 Md€/an (régime permanent)
        Population: 13.4M foyers retraités, 50% concernés

        Sources: PLF 2026, DGFiP, France Stratégie 2025
        """
        reforme = params.get('reforme_active', 0)  # 0 = système actuel, 1 = réforme 2000€
        phasing = 0.0

        # === BUDGET IMPACT ===
        if reforme == 1:
            # Phasing progressif sur 2 ans (montée en charge administrative)
            year_idx = year - 2025
            if year_idx <= 0:
                phasing = 0.0
            elif year_idx == 1:  # 2026
                phasing = 0.3  # +1.2 Md€
            else:  # 2027+
                phasing = 1.0  # +4 Md€

            delta_revenue = 4.0 * phasing  # Positif = gain fiscal (plus d'impôts collectés)
        else:
            delta_revenue = 0

        # === MACRO IMPACTS ===

        # Gini: ONE-TIME (first year only)
        # Réforme = hausse impôts retraités aisés = LÉGÈREMENT PROGRESSIF
        # Mais 10% plus riches = 60% du gain = distribution inégale
        # Rule: Impact modéré car ciblé
        params_tracking = {'reforme': reforme}
        if self._is_first_year_change('abattement_retraites', params_tracking):
            if reforme == 1:
                gini = -0.004  # Légèrement progressif (taxe les riches)
            else:
                gini = 0.0
        else:
            gini = 0.0

        # Purchasing power: Impact négatif sur retraités aisés
        # 50% des foyers concernés (7M foyers)
        # Perte moyenne: ~570€/an pour les concernés
        # Impact global: -0.0015% PA (effet limité car ciblé)
        if reforme == 1:
            pouvoir_achat = -0.0015 * phasing
        else:
            pouvoir_achat = 0

        # Competitiveness: No direct impact
        competitivite = 0

        impacts = {
            'recettes': delta_revenue,  # Positif = gain fiscal
            'gini': gini,
            'pouvoir_achat': pouvoir_achat,
            'competitivite': competitivite
        }

        _log_debug(self.debug_logs,
            f"Y{year}: Abattement retraites - Réforme {'ACTIVE' if reforme == 1 else 'INACTIVE'}, "
            f"Phasing {phasing*100:.0f}%, Recettes {delta_revenue:+.1f}Md€"
        )

        return 0, delta_revenue, impacts

    def _apply_prestations_indexation(self, measure: Dict, params: Dict, year: int,
                                       gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """
        Indexation des prestations sociales (hors pensions de retraite)

        Prestations concernées (90 Md€ total):
        - RSA: 12 Md€
        - APL (aides au logement): 15 Md€
        - Allocations familiales: 50 Md€
        - Autres prestations: 13 Md€

        Indexation par défaut: 100% de l'inflation
        Gel (PLFSS 2026): 0% → économies 2-3 Md€

        CONDITION: Seulement si ASU NON activée
        (Si ASU activée, elle suit automatiquement le SMIC)

        Sources: PLFSS 2026, OFCE 2024, IPP 2023, DREES
        """
        # CONTRAT: taux_indexation est un coefficient (1.0 = 100% inflation, 0 = gel total),
        # PAS un taux d'inflation cible (0.02, 0.025...).
        indexation = params.get('taux_indexation', 1.0)

        # Anti-double-comptage : l'ASU absorbe exactement cette base 90 Md€.
        # Prédicat = SOURCE UNIQUE `mesures['asu']`, PAS `params['asu_active']`
        # (jamais propagé → garde inerte ex. lr_2027). Cf. `asu_is_active`.
        if asu_is_active(self.mesures):
            # ASU suit le SMIC → pas d'indexation séparée
            _log_debug(self.debug_logs,
                f"Y{year}: Prestations indexation - INACTIVE (ASU activée)"
            )
            return 0, 0, {}

        # === BUDGET IMPACT ===
        total_prestations = 90  # Md€
        indexation_ref = 1.0  # Référence: indexation complète

        # Effet cumulatif sur les années (cap à 10 ans)
        year_idx = year - 2025
        if year_idx <= 0:
            years_effect = 0
        else:
            years_effect = min(year_idx, 10)

        # Calcul économies (si sous-indexation)
        # Érosion composée : chaque année, la base de prestations s'érode de
        # (1 - delta_indexation * inflation) par rapport à l'indexation complète.
        # L'ancienne formule (moyenne lissée du cumul) sous-estimait en début
        # de période et surestimait en fin de période.
        if years_effect > 0:
            delta_indexation = indexation_ref - indexation
            if delta_indexation > 0 and inflation > 0:
                eroded_base = total_prestations * (1 - delta_indexation * inflation) ** max(years_effect - 1, 0)
                delta_spending = -(total_prestations - eroded_base)  # Négatif = économie
            else:
                delta_spending = 0
        else:
            delta_spending = 0

        # === MACRO IMPACTS ===

        # Gini: ONE-TIME (first year only)
        # Sous-indexation = paupérisation bénéficiaires = TRÈS RÉGRESSIF
        # Rule: 100%→90% = +0.008 Gini (OFCE 2024)
        # (Plus fort que retraites car population plus pauvre)
        params_tracking = {'indexation': indexation}
        if self._is_first_year_change('prestations_indexation', params_tracking):
            delta_indexation = indexation_ref - indexation
            gini = 0.008 * delta_indexation / 0.10
        else:
            gini = 0.0

        # Purchasing power: STRONG impact (concentrated on bottom 30%)
        # Rule: 100%→90% = -0.003 PA (INSEE 2024)
        # Effet récurrent (suit l'inflation chaque année)
        delta_indexation = indexation_ref - indexation
        pouvoir_achat = -0.003 * delta_indexation / 0.10

        # Competitiveness: No direct impact
        competitivite = 0

        impacts = {
            'depenses': delta_spending,
            'gini': gini,
            'pouvoir_achat': pouvoir_achat,
            'competitivite': competitivite
        }

        _log_debug(self.debug_logs,
            f"Y{year}: Prestations indexation - Taux {indexation*100:.0f}%, "
            f"Inflation {inflation*100:.1f}%, Cumul {years_effect} ans, "
            f"Économies {-delta_spending:+.1f}Md€"
        )

        return delta_spending, 0, impacts
