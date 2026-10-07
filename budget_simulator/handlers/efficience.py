"""Section 1 — Efficience et organisation (DERNIÈRE section splittée, Phase 1.7).

Mesures couvertes (5 handlers) :
- ``fraude_fiscale`` : lutte contre la fraude fiscale. Cible convertie en
  Md€ (intensité 0-1 → 0-30 Md€, ou legacy direct), montée en puissance
  5 ans (20 % → 100 % en 2030, rendements décroissants ensuite, plancher
  70 %). Recettes réelles = espérées × 68 % (recouvrement DGFiP 2024),
  dépenses = 15 % des espérées. Effet ``recettes`` ET ``depenses``.
- ``fraude_sociale`` : lutte contre la fraude sociale (RSA/APL). ROI 8,75x
  (croisement fichiers CAF/Pôle Emploi, baseline structurelle), phasing
  4 ans, recouvrement 70 %, plafond NIVEAU 13 Md€ puis cap IGAS 8 Md€,
  **puis** anti-double-comptage ASU (-30 %·phasing à plein régime) —
  contrepartie de l'exclusion des gains fraude IA côté ``_apply_asu``
  (cf section Couplages).
- ``fonction_publique_reforme`` : réforme structurelle FP (fusion agences
  + digitalisation). Coûts initiaux 2026-2029 (0,15 Md€/point/an) puis
  gains via non-remplacement : somme de cohortes annuelles de départs
  (157 k/an × taux fonction de l'intensité × efficacité de l'année de la
  cohorte, 0,3 → 1,0, huit cohortes au plus), valorisées au coût complet
  ``COUT_MOYEN_AGENT_FP_EUR``. Pénalité dégradation service si ``fusion``
  > 7 et ``digitalisation`` < 3.
- ``fonction_publique`` : effectifs (±) et point d'indice. Base 5,5 M
  agents, masse salariale 330 Md€, coût moyen 60 k€/agent. La cible
  d'effectifs est atteinte par une rampe linéaire 2027-2032 (v0.6.7) ; une
  réduction puise dans le vivier de départs partagé avec la réforme, au même
  taux maximal de non-remplacement (67 %). Pouvoir d'achat (v0.6.8) : seul
  le point d'indice est un revenu direct des agents (canal
  ``remunerations_publiques``) ; les effectifs, dans les deux sens, passent
  par la croissance (arbitrage du mainteneur). ``int(...)`` sur
  ``variation_effectifs`` au logging : le frontend JSON peut envoyer un
  float (25000.0) là où ``{:+d}`` exige un int — garde-fou Phase 0.8 à
  préserver tel quel.
- ``optimisation_dette`` : optimisation de la gestion de dette. Économie
  ~2,5 Md€ × intensité, effet temporaire 2026-2030 uniquement.

Convention d'application :
- Profil « EFFICIENCE » : récupérer de l'argent dû / optimiser l'interne
  ne crée pas de valeur économique → ``gini`` / ``competitivite`` et canaux
  ménages (``menages``) neutralisés à 0 pour fraude_fiscale, fraude_sociale,
  fonction_publique_reforme, optimisation_dette. Seul ``fonction_publique``
  porte un canal ménages (point d'indice, ``remunerations_publiques``, en
  niveau de l'année). Voir docs/METHODOLOGIE.md § "Lutte contre la Fraude"
  et § "Fonction Publique".
- Garde précoce ``if <cible> == 0: return 0, 0, {}`` dans les 5 handlers
  (mesure inactive = neutre) — PRÉSERVÉ tel quel du monolithe.

Sources principales :
- DGFiP 2024, Cour des comptes 2025 — fraude fiscale.
- Cour des comptes, « Certification des comptes du régime général de
  sécurité sociale et du CPSTI — exercice 2024 », mai 2025 — fraude sociale
  (ordre de grandeur du gisement ET sa nature, cf. `_apply_fraude_sociale`).
  https://www.ccomptes.fr/sites/default/files/2025-05/20250516-certification-comptes-securite-sociale-2024.pdf
- METHODOLOGIE.md § Fonction Publique — réforme FP.
- DGAFP 2024, INSEE 2024 — effectifs / point d'indice FP.
- Cour des comptes 2025, IGF 2024 — optimisation dette.

Couplages avec ``BudgetSimulatorV45`` (instance hôte du mixin) :
- LIT la méthode ``self._is_first_year_change`` et le sink de logs
  ``self.debug_logs`` (via ``_log_debug``, sans incidence sur les sorties
  de simulation), fournis par la base class (simulator.py).
- ``_apply_fraude_sociale`` applique l'anti-double-comptage ASU en
  dérivant le phasing ASU de ``self.mesures`` + l'année via la SOURCE
  UNIQUE ``handlers._phasing.asu_phasing`` (entrée du run, lecture
  seule). **Plus aucun couplage par attribut d'instance** : l'ancien
  contrat producteur/consommateur fragile (lecture de
  ``self.asu_active``/``self.asu_phasing`` posés par ``_apply_asu``,
  sensible à l'ordre d'exécution — items type-design F1/F3) est
  DISSOUS. Le consommateur est auto-suffisant : indépendant de l'ordre
  des handlers et du fait que ``_apply_asu`` ait tourné ou non
  (ASU absente de ``self.mesures`` ou ``asu_activation == 0`` →
  ``asu_phasing`` renvoie 0.0 → réduction nulle = comportement correct ;
  prédicat ``== 0`` et non ``== 1`` à dessein, cf ``asu_phasing``).
- N'ÉCRIT aucun attribut d'instance : les 5 handlers sont purement
  fonctionnels (entrée params → sortie impacts). Aucun état propre au
  mixin. Aucun handler n'appelle un handler d'un autre mixin (invariant
  ADR Phase 1.2).

Sous-sections : ``fraude_fiscale`` / ``fraude_sociale`` (lutte fraude),
puis ``fonction_publique_reforme`` / ``fonction_publique`` /
``optimisation_dette`` (Sous-section 1.2 : Efficience Dépenses).
"""
from typing import TYPE_CHECKING, Dict, Tuple

from ..constants import (
    COUT_MOYEN_AGENT_FP_EUR,
    DEPARTS_ANNUELS_FP,
    FP_TAUX_NON_REMPLACEMENT_MAX,
    FRAUDE_SOCIALE_EFFICACITE_RECUPERATION,
    FRAUDE_SOCIALE_ROI,
    POLICY_START_YEAR,
    fraude_budget_saturant_md_eur,
)
from .._logging import _log_debug
from ._phasing import _year_phasing, asu_phasing
from ._types import ImpactsDict, canaux_menages


# Idiome mixin-self typing : NE PAS factoriser dans _types.py (casse la
# liaison self mypy + risque MRO). Réplication volontaire 7×. Cf Lot D.
if TYPE_CHECKING:
    from ._types import _SimulatorState

    _MixinBase = _SimulatorState
else:
    _MixinBase = object

# Réforme de l'État : une cohorte de départs non remplacés par année à partir de
# 2027 (2026 = préparation, coûts seuls), chacune à l'efficacité de SON année,
# huit cohortes au plus (2027-2034). Cf. ``_reforme_fp_reduction_cumulee``.
REFORME_FP_PREMIERE_COHORTE = 2027
REFORME_FP_MONTEE_EN_CHARGE = (0.3, 0.6, 0.85, 1.0)
REFORME_FP_COHORTES_MAX = 8

# Curseur « effectifs » (v0.6.7, réfutation des handlers, arbitrage de Cyril du
# 07/10/2026) : la cible est un STOCK atteint par une rampe LINÉAIRE, même règle
# pour tous les programmes et dans les deux sens — 0 en 2026 (budget voté, le
# mandat n'a pas commencé), un sixième de la cible par an de 2027 à 2032, cible
# pleine en 2032 (fin du quinquennat, l'année que RN et LR annoncent ; aucune
# source de programme ne donne plus vite). Même première année que la réforme :
# les deux puisent dans le même vivier de départs.
FP_EFFECTIFS_PREMIERE_ANNEE = REFORME_FP_PREMIERE_COHORTE
FP_EFFECTIFS_ANNEE_CIBLE = 2032
_FP_EFFECTIFS_DUREE_RAMPE = FP_EFFECTIFS_ANNEE_CIBLE - FP_EFFECTIFS_PREMIERE_ANNEE + 1


def _fp_effectifs_annees_de_rampe(year: int) -> int:
    """Années de rampe écoulées à ``year`` (0 avant 2027, 6 dès 2032) : la cible
    réalisée vaut cible × ce nombre / ``_FP_EFFECTIFS_DUREE_RAMPE``, en entiers
    pour que la cible tombe juste (−201 000 / 6 = −33 500 exactement)."""
    return min(max(year - FP_EFFECTIFS_PREMIERE_ANNEE + 1, 0), _FP_EFFECTIFS_DUREE_RAMPE)


class EfficienceMixin(_MixinBase):
    """Handlers Section 1 — Efficience et organisation."""

    def _apply_fraude_fiscale(self, measure: Dict, params: Dict, year: int, gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Lutte fraude fiscale avec montée progressive (5 ans). Potentiel 80-100 Md€, ROI 13x (IA intégrée baseline).
        Sources: DGFiP 2024, Cour comptes 2025. Voir METHODOLOGIE.md § Lutte contre la Fraude."""
        # Conversion intensité (0-1) vers Md€ (0-30).
        # v0.6.3 : même dé-bimodalisation que fraude_sociale — la lecture
        # par MAGNITUDE (> 1 = Md€ legacy) créait ici une falaise de
        # −29 Md€ de recettes entre effort 1,0 (cible 30) et 1,01 (cible
        # 1,01), sur un levier 10× plus lourd que son jumeau social, et un
        # effort NÉGATIF détruisait 10-41 Md€/an de recettes sans un log.
        # Tous les scénarios publiés sont ∈ [0;1] (identique au bit) ; le
        # levier entre au registre PARAM_DOMAINS (effort ∈ [0;1]).
        recettes_cible = params.get('effort', 0) * 30  # 0-30 Md€ (Cour des comptes : DGFiP ~15 Md€/an, max réaliste ~30)

        if recettes_cible == 0:
            return 0, 0, {}

        # Année de référence
        years_elapsed = year - POLICY_START_YEAR

        # ===== MONTÉE EN PUISSANCE (5 ANS) =====
        if years_elapsed < 0:
            # Avant 2026 : pas d'effet
            progress = 0.0
        elif years_elapsed == 0:
            # 2026 (Année 1) : 20%
            progress = 0.20
        elif years_elapsed == 1:
            # 2027 (Année 2) : 35%
            progress = 0.35
        elif years_elapsed == 2:
            # 2028 (Année 3) : 50%
            progress = 0.50
        elif years_elapsed == 3:
            # 2029 (Année 4) : 70% (objectif gouvernement 40 Md€ détectés)
            progress = 0.70
        elif years_elapsed == 4:
            # 2030 (Année 5) : 100% (palier maximal atteint)
            progress = 1.0
        else:
            # 2031+ : rendements décroissants (les cas faciles sont traités en premier)
            years_past_peak = years_elapsed - 4
            progress = max(0.70, 1.0 - years_past_peak * 0.05)  # -5%/an après pic, plancher 70%

        # ===== RECETTES ESPÉRÉES =====
        recettes_esperees = recettes_cible * progress

        # ===== RECETTES RÉELLES (68% d'efficacité) =====
        # Taux recouvrement empirique DGFiP 2024 : 11.4 / 16.7 = 68.3%
        efficacite_reelle = 0.68
        delta_revenue = recettes_esperees * efficacite_reelle

        # ===== DÉPENSES (15% des recettes espérées) =====
        # Coût contrôles IT + RH : ~10k agents DGFiP + infrastructure IA
        taux_depenses = 0.15
        delta_spending = recettes_esperees * taux_depenses

        # ===== IMPACTS =====
        # EFFICIENCE : Récupération argent dû, pas de création valeur → impacts macro = 0
        impacts = {
            'depenses': delta_spending,
            'recettes': delta_revenue,
            'gini': 0,  # Pas d'impact redistributif (récupération fraude)
            'menages': canaux_menages(),  # Pas d'impact direct sur ménages
            'competitivite': 0  # Pas d'impact sur compétitivité entreprises
        }

        # ===== LOGS DEBUG =====
        net_benefit = delta_revenue - delta_spending
        roi_observed = delta_revenue / delta_spending if delta_spending > 0 else 0

        _log_debug(self.debug_logs,
            f"Y{year}: Fraude fiscale - Cible {recettes_cible:.0f}Md€, "
            f"Progression {progress*100:.0f}%, "
            f"Espérées {recettes_esperees:.1f}Md€, "
            f"Réelles {delta_revenue:.1f}Md€ (68%), "
            f"Dépenses {delta_spending:.1f}Md€ (15%), "
            f"Net +{net_benefit:.1f}Md€ (ROI {roi_observed:.1f}x IA intégrée)"
        )

        return delta_spending, delta_revenue, impacts

    def _apply_fraude_sociale(self, measure: Dict, params: Dict, year: int,
                              gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Lutte fraude sociale (RSA, APL). Potentiel 13 Md€, ROI 8.75x (numérisation intégrée), phasing 4 ans.
        Voir METHODOLOGIE.md § Lutte contre la Fraude.

        CE QUI EST SOURCÉ — Cour des comptes, « Certification des comptes du
        régime général de sécurité sociale et du CPSTI, exercice 2024 »,
        mai 2025 : le risque financier résiduel sur les prestations CAF vaut
        11,7 % à 9 mois (9,4 Md€) et 8,0 % à 24 mois (6,3 Md€, jamais
        détecté) ; la fraude estimée vaut 4,25 Md€, soit 5,1 % des
        prestations légales (2023).

        CE QUI NE L'EST PAS, ET DOIT ÊTRE DIT — le ROI de 8,75, le taux de
        récupération de 0,70 et le plafond de 13 Md€ sont une calibration
        héritée de la v4.5, qu'AUCUNE source consultée ne porte. Le levier
        `fraude_sociale` n'était pas au périmètre du dossier de sourcing
        v0.6.1 : ces trois valeurs sont donc laissées INCHANGÉES et déclarées
        comme dette d'audit plutôt que rhabillées d'une citation empruntée.
        Deux tensions connues, à instruire dans la passe dédiée :
          - le « potentiel 13 Md€ » dépasse le risque résiduel total mesuré
            par la Cour (9,4 Md€ à 9 mois) ;
          - 30 à 36 % de ce risque sont des RAPPELS, c'est-à-dire de l'argent
            DÛ aux allocataires : les détecter AUGMENTE la dépense. Le
            gisement brut d'indus plafonne donc vers 4,0-4,4 Md€.
        L'attribution qui figurait ici à un « haut conseil » de la protection
        sociale millésimé 2024 est RETIRÉE : l'acronyme employé ne désignait
        aucun organisme. Ce n'est PAS une faute de frappe à réparer — les deux
        institutions réelles au nom voisin (HCFiPS et HCFEA) ont été
        vérifiées, aucune ne publie ces chiffres. L'attribution n'est donc pas
        remplacée par une source de substitution."""
        # Conversion intensité (0-1) vers Md€ (0-3).
        # v0.6.3 (revue type-design) : la lecture BIMODALE historique
        # (≤ 1 = intensité, > 1 = montant Md€ « legacy ») est SUPPRIMÉE — la
        # bascule par MAGNITUDE créait une discontinuité de +1,56 Md€/an
        # exactement à effort = 1,0, la valeur encodée de RN et LR : un
        # re-encodage à 1,1 aurait sauté de mode en silence. Aucun scénario
        # publié n'utilisait le mode Md€ (efforts publiés : 0 à 1,0), et le
        # levier entre au registre PARAM_DOMAINS (effort ∈ [0;1]) — la porte
        # de domaine borne désormais les entrées hors-UI, comme partout.
        budget_controles = params.get('effort', 0) * 3  # 0-3 Md€

        if budget_controles == 0:
            return 0, 0, {}

        # Phasing 4 ans
        years_elapsed = year - POLICY_START_YEAR
        phasing = _year_phasing(years_elapsed, (0.25, 0.50, 0.75, 1.0))

        # ===== ROI : 8.75x (numérisation/data mining intégrée par défaut) =====
        # ANCIEN MODÈLE : 7x base + 25% bonus optionnel si checkbox cochée
        # NOUVEAU MODÈLE : 8.75x baseline (croisement fichiers CAF/Pôle Emploi opérationnel)
        # Justification : CNAF 2023, Plan antifraude 2023-2027 — le croisement
        # de fichiers est bien opérationnel, mais AUCUNE source consultée ne
        # publie ce multiplicateur. Valeur NON AUDITÉE, cf. la docstring
        # ci-dessus (l'attribution retirée ici renvoyait à un organisme
        # inexistant : retirée, non remplacée).
        # Anti-double-comptage ASU : si l'ASU est active, ses contrôles IA
        # intégrés captent déjà une part de la fraude sociale → ce levier
        # n'en récupère que le RÉSIDUEL (jusqu'à -30 % à plein régime,
        # 0.30·phasing). Contrepartie OBLIGATOIRE de l'exclusion symétrique
        # des gains fraude IA (+3-6 Md€) côté `_apply_asu` (cf docstring
        # depenses.py) : sans elle, ces montants ne sont comptés NI là NI
        # ici. Appliqué au GISEMENT (donc aussi au budget saturant, cf.
        # ci-dessous). Dérivé de `self.mesures` + l'année via la source
        # unique `asu_phasing` → AUCUNE dépendance à l'ordre d'exécution
        # des handlers.
        asu_ph = asu_phasing(self.mesures, year)

        # Gisement récupérable : cap IGAS — la fraude sociale réellement
        # recouvrable est estimée 6-8 Md€/an. Plafond de NIVEAU, DISTINCT du
        # mécanisme ASU (ne pas reconfondre — c'est cette confusion qui
        # rendait jadis la réduction ASU inerte : 8 < plafond ASU ∈
        # [9,1 ; 13]). Le « plafond théorique » historique de 13 Md€, shadowé
        # par ce cap depuis toujours, est retiré du calcul (v0.6.3) — il
        # survit dans la docstring, pas dans une expression morte. Le
        # résiduel ASU réduit le gisement. Constantes : source unique
        # constants.py § CALIBRATION FRAUDE SOCIALE (leurs statuts d'audit
        # inégaux y sont déclarés).

        # v0.6.3 (monotonie) : le budget ENGAGÉ sature avec le gisement.
        # L'ancien calcul gardait un budget linéaire face à une récupération
        # plafonnée : au-delà du point de saturation (effort ≈ 0,435 à plein
        # phasing), chaque euro de contrôle coûtait sans rien récupérer —
        # RN/LR à effort 1,0 recevaient ~1,5 Md€/an de MOINS que LFI à 0,5
        # (même famille que la non-monotonie de l'audit Thierry, v0.6.0).
        # Désormais l'excédent n'est pas engagé : on ne finance pas des
        # contrôles dont le gisement IGAS dit qu'ils n'ont rien à récupérer.
        # Le solde net devient FAIBLEMENT monotone en l'effort (flat au-delà
        # de la saturation), strictement croissant en deçà — verrouillé par
        # tests/test_passe_bugs_v063.py. Le seuil vit dans constants.py
        # (fraude_budget_saturant_md_eur — source unique, infini à phasing
        # nul : tout le budget est engagé, rien récupéré, comme toujours).
        rendement_marginal = (FRAUDE_SOCIALE_ROI
                              * FRAUDE_SOCIALE_EFFICACITE_RECUPERATION * phasing)
        budget_engage = min(budget_controles,
                            fraude_budget_saturant_md_eur(phasing, asu_ph))

        economies_reelles = budget_engage * rendement_marginal

        delta_spending = -economies_reelles + budget_engage

        impacts = {
            'depenses': delta_spending,
            'gini': 0.0,
            'menages': canaux_menages(),
            'competitivite': 0.0
        }

        # v0.6.3 : plus de « ROI observé » — depuis la saturation du budget
        # engagé, economies/budget == rendement_marginal par construction,
        # le log affiche donc le rendement lui-même.
        asu_info = (f", anti-double-comptage ASU -{0.30 * asu_ph * 100:.0f}%"
                    if asu_ph > 0 else "")
        saturation_info = (f" (demandé {budget_controles:.1f}, gisement saturé)"
                           if budget_engage < budget_controles else "")
        _log_debug(self.debug_logs,
            f"Y{year}: Fraude sociale - Budget engagé {budget_engage:.1f}Md€{saturation_info}, "
            f"Économies {economies_reelles:.1f}Md€, rendement {rendement_marginal:.1f}x (numérisation intégrée){asu_info}"
        )

        return delta_spending, 0, impacts

    # -----------------------------------------------------------------------
    # Sous-section 1.2 : Efficience Dépenses
    # -----------------------------------------------------------------------


    def _reforme_fp_reduction_cumulee(self, year: int) -> float:
        """Réduction d'effectifs (stock, nombre d'agents) déjà réalisée par la
        réforme de l'État à l'année donnée — fonction déterministe des
        paramètres actifs, SOURCE UNIQUE du vivier de départs partagé entre le
        handler réforme et le curseur effectifs (anti-double-comptage v0.6.0,
        audit 08/2026 constat 4). Taux de non-remplacement selon l'intensité
        (0-50 % jusqu'à 10, 50-67 % au-delà, borné à [0 ; 1]) ; une cohorte de
        départs par année à partir de 2027, chacune à l'efficacité de SON année
        (0,3 / 0,6 / 0,85 puis 1,0) ; huit cohortes au plus (2027-2034).

        v0.6.7 (audit Codex, bloc B constat 1) : le stock valait
        départs × taux × efficacité(année COURANTE) × nombre d'années. Chaque
        année réévaluait donc toutes les cohortes passées, comptait une cohorte
        2026 inexistante (deux cohortes dès 2027) et pouvait croître de plus que
        les départs d'une année (intensité 20 : 525 950 postes en 2030 au lieu de
        289 272, +14 Md€/an d'économies). Un poste non remplacé reste non
        remplacé : le stock est la SOMME des cohortes."""
        params = self.mesures.get('fonction_publique_reforme', {})
        # Bloc null (levier absent, sauté par apply_measures) ou mal formé →
        # 0.0, le même résultat que la clé absente (intensité nulle).
        if not isinstance(params, dict):
            return 0.0

        # Sanitisation locale (revue adverse 24/08) : ce helper lit
        # self.mesures BRUT (pas la porte validate_param_domains des handlers) —
        # un paramètre invalide dans la réforme ne doit ni crasher ni
        # contaminer le handler effectifs qui l'appelle. bool exclu (bool ⊂ int),
        # NaN exclu (NaN != NaN).
        def _num(x):
            if isinstance(x, bool) or not isinstance(x, (int, float)) or x != x:
                return 0.0
            return float(x)

        fusion = _num(params.get('fusion_agences', 0)) / 10
        digitalisation = _num(params.get('digitalisation', 0)) / 10
        intensite_totale = fusion + digitalisation
        if intensite_totale == 0 or year < REFORME_FP_PREMIERE_COHORTE:
            return 0.0
        if intensite_totale <= 10:
            taux_non_remplacement = intensite_totale * 0.05  # 0-50%
        else:
            taux_non_remplacement = 0.50 + (intensite_totale - 10) * 0.017  # 50-67%
        # Borne du vivier : une cohorte ne dépasse pas les départs de son année
        # (taux > 1 hors du domaine publié des curseurs) et n'est jamais une
        # embauche (taux < 0).
        taux_non_remplacement = min(max(taux_non_remplacement, 0.0), 1.0)
        derniere = min(year, REFORME_FP_PREMIERE_COHORTE + REFORME_FP_COHORTES_MAX - 1)
        efficacites = sum(
            _year_phasing(cohorte - REFORME_FP_PREMIERE_COHORTE, REFORME_FP_MONTEE_EN_CHARGE)
            for cohorte in range(REFORME_FP_PREMIERE_COHORTE, derniere + 1))
        return DEPARTS_ANNUELS_FP * taux_non_remplacement * efficacites

    def _apply_fonction_publique_reforme(self, measure: Dict, params: Dict, year: int,
                                         gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Réforme structurelle FP (fusion agences, digitalisation). Coûts 2026-2029, puis
        non-remplacement par cohortes de départs (157 k/an) au coût complet chargé
        COUT_MOYEN_AGENT_FP_EUR. Voir METHODOLOGIE.md § Fonction Publique."""
        # Les sliders sont maintenant en % (0-100), on les convertit en 0-10
        fusion = params.get('fusion_agences', 0) / 10
        digitalisation = params.get('digitalisation', 0) / 10
        year_idx = year - 2025

        # Intensité totale (0-20)
        intensite_totale = fusion + digitalisation

        delta_spending = 0

        # Montants calés en euros 2025 → euros de l'année (v0.6.7) : coûts,
        # pénalité et économies au même indice de prix des dépenses.
        indice = self.indice_prix_depenses()

        # PHASE 1: COÛTS INITIAUX (2026-2029)
        if 1 <= year_idx <= 4:
            # Coûts: audits, formation, systèmes IT
            # Formule: 0.15 Md€ (euros 2025) par point d'intensité/an
            cout_annuel = intensite_totale * 0.15 * indice
            delta_spending += cout_annuel
            _log_debug(self.debug_logs, f"Y{year}: Réforme FP - Coûts investissement: +{cout_annuel:.1f} Md€")

        # PHASE 2: GAINS VIA NON-REMPLACEMENTS (2027+)
        # v0.6.0 : formule extraite dans _reforme_fp_reduction_cumulee (vivier
        # partagé avec le curseur effectifs, anti-double-comptage) et poste
        # valorisé au coût complet chargé COUT_MOYEN_AGENT_FP_EUR (source
        # unique constants.py — le 40 k€ v0.5.1 était sans périmètre), en euros
        # de l'année depuis v0.6.7 (indice de prix des dépenses, comme le curseur).
        if year_idx >= 2:
            postes_cumules = self._reforme_fp_reduction_cumulee(year)
            economie_cumulee = postes_cumules * COUT_MOYEN_AGENT_FP_EUR * indice / 1e9
            delta_spending -= economie_cumulee

            _log_debug(self.debug_logs,
                f"Y{year}: Réforme FP - {postes_cumules:,.0f} postes non remplacés "
                f"(cumul), économies: -{economie_cumulee:.1f} Md€"
            )

        # Impact qualité service si intensité excessive sans digitalisation
        if fusion > 7 and digitalisation < 3 and year_idx >= 3:
            penalite = 0.3 * indice  # Dégradation service public (0,3 Md€ en euros 2025)
            delta_spending += penalite
            _log_debug(self.debug_logs, f"Y{year}: Pénalité dégradation service: +{penalite:.1f} Md€")

        # EFFICIENCE : Optimisation administrative, pas d'impact économique réel → impacts macro = 0
        impacts = {
            'depenses': delta_spending,
            'gini': 0,  # Pas d'impact redistributif (optimisation interne)
            'menages': canaux_menages(),  # Pas d'impact direct sur ménages
            'competitivite': 0  # Gains productivité admin ≠ compétitivité entreprises
        }
        return delta_spending, 0, impacts

    def _apply_fonction_publique(self, measure: Dict, params: Dict, year: int,
                                  gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Effectifs et point d'indice FP. Impacts directs sur masse salariale.
        Base: 5.5M agents, masse salariale 330 Md€, salaire moyen 60k€/an (charges incluses).
        Sources: DGAFP 2024, INSEE 2024."""

        variation_effectifs = params.get('effectifs', 0)  # -100k à +50k
        hausse_point_indice = params.get('point_indice', 0)  # -2% à +5%

        if variation_effectifs == 0 and hausse_point_indice == 0:
            return 0, 0, {}

        # Constantes FP
        masse_salariale_base = 330  # Md€, euros 2025 (exprimée en euros de l'année ci-dessous)
        # Source unique v0.6.0, calée en euros 2025 ; v0.6.7 : en euros de
        # l'année (indice de prix des dépenses, celui de la masse salariale du
        # statu quo) — figé, il valorisait un poste 60 k€ en 2035 comme en 2026.
        cout_moyen_agent = COUT_MOYEN_AGENT_FP_EUR * self.indice_prix_depenses()

        delta_spending = 0

        # 1. VARIATION EFFECTIFS
        # Coût/économie = postes réalisés de l'année × coût moyen agent.
        # v0.6.7 (réfutation des handlers, arbitrage de Cyril du 07/10/2026) :
        # la cible est un STOCK atteint par une rampe linéaire 2027-2032
        # (FP_EFFECTIFS_*), dans les deux sens. Jusqu'en v0.6.6, elle était posée
        # dès 2026 dans la seule limite des départs cumulés : RN et LR
        # supprimaient 157 000 postes dès 2026 et atteignaient leur cible dès
        # 2027, quand leurs sources annoncent une trajectoire 2027-2032 ; les
        # créations étaient instantanées.
        # Anti-double-comptage « plafond de vivier » (v0.6.0, audit 08/2026
        # constat 4) : une RÉDUCTION opère par non-remplacement des départs (pas
        # de licenciement dans la FP), le MÊME vivier que la réforme de l'État.
        # Le curseur reste ADDITIONNEL et cumulable avec la réforme ; le TOTAL
        # (réforme + curseur) ne dépasse jamais FP_TAUX_NON_REMPLACEMENT_MAX des
        # départs cumulés depuis la première cohorte (v0.6.7 : 100 % des départs
        # depuis 2026 auparavant, ce que la réforme, plafonnée à 67 %, ne pouvait
        # pas faire). Une CRÉATION de postes ne puise pas dans le vivier.
        if variation_effectifs != 0:
            cible_annee = (variation_effectifs * _fp_effectifs_annees_de_rampe(year)
                           / _FP_EFFECTIFS_DUREE_RAMPE)
            if cible_annee < 0:
                cohortes = max(0, year - FP_EFFECTIFS_PREMIERE_ANNEE + 1)
                vivier_cumule = FP_TAUX_NON_REMPLACEMENT_MAX * DEPARTS_ANNUELS_FP * cohortes
                deja_reforme = self._reforme_fp_reduction_cumulee(year)
                capacite = max(0.0, vivier_cumule - deja_reforme)
                variation_residuelle = -min(-cible_annee, capacite)
                if variation_residuelle != cible_annee:
                    _log_debug(self.debug_logs,
                        f"Y{year}: FP Effectifs - cible de l'année {cible_annee:,.0f} "
                        f"plafonnée par le vivier ({FP_TAUX_NON_REMPLACEMENT_MAX:.0%} des "
                        f"départs cumulés {vivier_cumule:,.0f}, réforme {deja_reforme:,.0f}) "
                        f"→ réalisé {variation_residuelle:,.0f}")
            else:
                variation_residuelle = cible_annee
            impact_effectifs = variation_residuelle * cout_moyen_agent / 1e9  # en Md€
            delta_spending += impact_effectifs
            # Cast int explicite : JSON frontend peut envoyer 25000.0 (float), `{:+d}` exige int.
            _log_debug(self.debug_logs,
                f"Y{year}: FP Effectifs - objectif {int(variation_effectifs):+d} agents, "
                f"réalisé {variation_residuelle:+,.0f} = {impact_effectifs:+.1f} Md€")

        # 2. POINT D'INDICE
        # Hausse de X% = X% × masse salariale de l'année. v0.6.7 : même indice
        # que le coût d'un agent — figée en euros 2025, la masse sous-estimait
        # le coût d'une hausse de rémunération quand les économies d'une
        # réduction d'effectifs, elles, étaient indexées.
        impact_point_indice = 0.0
        if hausse_point_indice != 0:
            impact_point_indice = ((hausse_point_indice / 100) * masse_salariale_base
                                   * self.indice_prix_depenses())
            delta_spending += impact_point_indice
            _log_debug(self.debug_logs,
                f"Y{year}: FP Point indice - {hausse_point_indice:+.1f}% = {impact_point_indice:+.1f} Md€")

        # IMPACTS MACRO
        # Pouvoir d'achat (v0.6.8, arbitrage du mainteneur) : le point d'indice
        # est un revenu versé aux agents en place — canal
        # ``remunerations_publiques`` au COÛT de l'année, dont l'indice ne
        # retient que la part nette (PART_NETTE_REMUNERATIONS_APU), compté UNE
        # fois (plus de coefficient en sus de la croissance : 0,003/point
        # transmettait 158 % de ses euros). Les EFFECTIFS, créations comme
        # suppressions, n'ont aucun effet direct : ils passent par la
        # croissance, qui contient la production publique de ces agents.

        # Compétitivité : PAS D'IMPACT DIRECT
        # Lien masse salariale FP → compétitivité entreprises trop indirect
        # (Hausse FP → Déficit → Dette → Prélèvements futurs = effet 5-10 ans, négligeable)
        # Compétitivité concerne secteur privé, pas secteur public
        competitivite = 0.0

        # Gini : peu d'impact (salaires FP déjà compressés)
        gini = 0

        impacts = {
            'depenses': delta_spending,
            'gini': gini,
            'competitivite': competitivite,
            'menages': canaux_menages(remunerations_publiques=impact_point_indice),
        }

        _log_debug(self.debug_logs,
            f"Y{year}: FP Total = {delta_spending:+.1f} Md€ (Compét: {competitivite:+.4f})")

        return delta_spending, 0, impacts


    def _apply_optimisation_dette(self, measure: Dict, params: Dict, year: int,
                                  gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Optimisation dette. Potentiel 1-2.5 Md€. Temporaire 2026-2030. Impacts macro=0.
        Sources: Cour comptes 2025, IGF 2024. Voir METHODOLOGIE.md § Notes Methodologiques Generales (pas de section dédiée — levier technique mineur)."""
        intensite = params.get('intensite', 0)

        if intensite == 0:
            return 0, 0, {}

        year_idx = year - 2025

        # Effet temporaire 2026-2030
        if year_idx <= 0 or year_idx > 5:
            delta_spending = 0
        else:
            economie_max = 2.5
            delta_spending = -economie_max * intensite

        impacts = {
            'depenses': delta_spending,
            'gini': 0.0,
            'menages': canaux_menages(),
            'competitivite': 0.0
        }

        _log_debug(self.debug_logs,
            f"Y{year}: Optimisation dette - Intensité {intensite*100:.0f}%, "
            f"Économies {-delta_spending:.1f}Md€"
        )

        return delta_spending, 0, impacts
