"""Section 2 — Maîtrise des dépenses.

Mesures couvertes (6 handlers) :
- ``retraites`` : âge de départ, durée de cotisation (réf. 42,5 ans) et
  indexation des pensions. Barème d'âge PLAT et SYMÉTRIQUE à 6,0 Md€/an par
  année d'écart au DROIT EN VIGUEUR de l'année (calendrier légal post-LFSS
  2026 : 62,75 ans jusqu'en 2027, puis +3 mois par an jusqu'à 64,0 en 2032),
  net de 9,6 % de fuite sociale résiduelle, montée en charge 5 ans (cohortes
  COR). Gini/PA modulés selon la mortalité différentielle et la
  désindexation. Le « -16 Md€/an » de la v0.5.1 et le barème à deux segments
  de la v0.6.0 (14,2 sous 64 ans) sont RETIRÉS : ils venaient d'une collision
  entre deux « 17,7 Md€ » sans rapport (cf. constants.py § barème d'âge).
- ``sante`` : réforme structurelle 3 leviers (hôpital, ambulatoire,
  prévention/organisation, potentiel -30 Md€ en 2030, phasing admin vs
  structurel distinct) + franchise/participation forfaitaire + budget
  prévention absolu (base 7,5 Md€ = prévention institutionnelle DREES,
  borne haute 11,2 Md€ = convergence OCDE ; taux de compensation différé de
  4 ans, +10 pts/an, plafonné à 50 % et SYMÉTRIQUE). Le rendement de la
  v0.5.1 — 25 points par an, plafond à 200 % après 8 ans — est RETIRÉ :
  au-delà de 100 % la mesure rapportait plus qu'elle ne coûtait, ce
  qu'aucune source n'autorise (cf. constants.py § prévention).
- ``chomage_alloc`` : assurance chômage Unédic. Taux de remplacement %
  (mode v4.5) ou montant Md€ (mode legacy) × durée, dégressivité
  optionnelle. Impacts Gini/PA/chômage one-time sur changement effectif.
- ``asu`` : Allocation Sociale Unique. Périmètre officiel = RSA + prime
  d'activité + APL (39 Md€) ; les prestations familiales sont HORS
  réforme. Phasing 4 ans, curseur 50-70 % du SMIC pilotant l'EFFORT
  budgétaire pérenne (0 à +2 Md€/an, les deux variantes chiffrées par la
  DREES/Igas), net de la seule économie de gestion défendable
  (0,3 Md€/an) et PLANCHÉ à zéro — la source ne chiffre aucun scénario où
  la réforme rapporte —, plus un coût de transition sur les 4 premières
  années.
  Le modèle de la v0.5.1 — une machine à économies de 11,5 Md€/an, un
  bonus emploi et un Gini amélioré à coût nul — est RETIRÉ : la seule
  évaluation administrative de la réforme chiffre un effet pérenne de 0
  à +2 Md€/an de COÛT (cf. constants.py § ASU).
- ``abattement_retraites`` : réforme de l'abattement fiscal sur pensions
  (PLF 2026, forfait 2000 €). Effet ``recettes`` (+4 Md€ régime permanent,
  phasing 2 ans), Gini légèrement progressif one-time.
- ``prestations_indexation`` : indexation des prestations sociales hors
  pensions (RSA/APL/allocations familiales, base 90 Md€). Érosion composée
  si sous-indexation. Neutralisé EN TOTALITÉ (anti-double-comptage) quand
  l'ASU est active dans le scénario — prédicat SOURCE UNIQUE
  ``_phasing.asu_is_active(self.mesures)``.
  Précision v0.6.1 : le périmètre de l'ASU est un SOUS-ENSEMBLE de cette
  base (39 contre 90), et non son égal comme l'écrivaient la v0.5.1 et
  la v0.6.0. Neutraliser en totalité reste le choix retenu, et c'est un
  choix CONSERVATEUR assumé : il ne peut qu'ÔTER des économies à un
  programme qui cumule les deux leviers, jamais lui en offrir. Re-baser
  le levier d'indexation (dont l'assiette n'est PAS auditée par le lot
  ASU) est un chantier distinct.

Convention d'application :
- Effets ``gini`` / ``competitivite`` (et parfois ``pouvoir_achat`` /
  ``chomage``) en mode NIVEAU one-time, gated par
  ``self._is_first_year_change(<clé>, params)`` (méthode de l'hôte) ou par
  un suivi cross-année dédié (cf ``chomage_alloc`` ci-dessous). Chaque
  sous-effet a sa propre clé de gating (``retraites_gini_indexation``,
  ``sante``, ``chomage_alloc_competitivite``, ``abattement_retraites``,
  ``prestations_indexation``).
  EXCEPTION, et elle est structurelle : le canal d'ÂGE des retraites ne
  passe pas par ``_is_first_year_change`` mais par l'horloge du CHOC
  (``_seniors.retraites_annee_debut_ecart_age_handler``). Sa référence est
  le CALENDRIER LÉGAL, mobile jusqu'en 2032 : l'horloge du run y plaçait
  l'effet plein sur un écart encore nul pour tout programme s'écartant
  après 2026 (cf. le détail dans ``_apply_retraites``).
- Effet ``pouvoir_achat`` de ``retraites`` et ``prestations_indexation``
  est au contraire RÉCURRENT (suit la désindexation chaque année) —
  PRÉSERVÉ tel quel du monolithe.
- Effet ``depenses`` : négatif = économie. ``abattement_retraites`` est le
  seul handler de la section à porter son effet sur ``recettes``.
- Voir docs/METHODOLOGIE.md § "Effets NIVEAU vs FLUX" pour le contrat de
  gating, et § "Sante" pour le détail des leviers santé.

Sources principales :
- COR Rapport annuel 2024, OFCE Brief 124 (15/02/2024) — retraites ;
  DG Trésor (COR 27/01/2022, doc n° 12) et Cour des comptes 02/2025 T6 p. 72
  pour le barème d'âge ; DREES/DARES via Cour 02/2025 p. 67-68 pour la fuite
  sociale résiduelle (détail et URL : constants.py).
- PLFSS 2026, IGAS 2024, CCSS 2024 — santé.
- Unédic 2025, OFCE 2023, INSEE 2024, France Stratégie 2019 — chômage.
- AN mission flash 07/2025 (chiffrages DREES/Igas 06/2024), Cour des comptes
  (prime d'activité, communication au Sénat 01/2026 ; certification des
  comptes de la sécurité sociale 05/2025), IPP octobre 2023 — ASU. Les
  quatre attributions de la v0.5.1 sont RETIRÉES et non réécrites : deux
  étaient introuvables, une nommait un organisme inexistant, une était une
  note de plaidoyer réfutée au fond (motifs détaillés : constants.py § ASU).
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

from ..constants import (
    ASU_GINI_BORNE_PAR_MD_EUR,
    ASU_PERIMETRE_MD_EUR,
    ASU_PLAFONNEMENT_DEFAUT,
    FUITE_SOCIALE_RESIDUELLE,
    PHASING_RETRAITES_5ANS,
    POLICY_START_YEAR,
    PREVENTION_BASE_MD_EUR,
    PREVENTION_OFFSET_CENTRAL_CAP,
    PREVENTION_OFFSET_LAG_YEARS,
    PREVENTION_OFFSET_RAMP_PER_YEAR,
    RDB_MENAGES_MD_EUR,
    RETRAITES_COEFF_AGE_MD_EUR,
    RETRAITES_COEFF_DUREE_MD_EUR,
    RETRAITES_EROSION_INDEXATION_MD_EUR,
    RETRAITES_EROSION_PLATEAU_ANS,
    RETRAITES_GINI_PAR_ANNEE_ECART,
    RETRAITES_GINI_PAR_POINT_DESINDEXATION,
    RETRAITES_GINI_RESIDU_FLUX,
    RETRAITES_PA_GEL_TOTAL,
    RETRAITES_REF_DUREE_ANS,
    asu_cout_transition_md_eur,
    asu_effort_perenne_md_eur,
    asu_plafonnement_borne,
    asu_solde_perenne_md_eur,
)
from .._logging import _log_debug
from .._seniors import (
    retraites_annee_debut_ecart_age_handler,
    retraites_ecart_age_ans,
)
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
        if year < POLICY_START_YEAR:
            return 0, 0, {}
        # Écart au DROIT EN VIGUEUR de l'année simulée (calendrier légal
        # post-LFSS 2026 : 62,75 ans gelés jusqu'en 2027, puis +3 mois par
        # génération jusqu'à 64 ans en 2032). La référence n'est plus figée à
        # 62,75 : la reprise de la montée en charge est DÉJÀ dans la baseline
        # (mission IGF 07/2026), donc la chiffrer une seconde fois serait du
        # double comptage — dans les deux sens (cf. constants.py § référence
        # d'âge).
        # SOURCE UNIQUE `_seniors.retraites_ecart_age_ans` : le canal
        # budgétaire (ici) et les canaux macro du moteur (offre de travail,
        # bosse de chômage) doivent partir du MÊME écart, sans quoi un
        # recalibrage du calendrier légal n'en atteindrait qu'une partie.
        ecart_age = retraites_ecart_age_ans(params, year)
        # NOTE (lot 7) : il n'y a plus de clé d'identité `age` dans le gating
        # one-time du Gini ci-dessous. Elle n'y a plus sa place depuis que le
        # canal d'âge lit l'horloge du CHOC, qui est déjà stable d'une année
        # sur l'autre par construction — l'ancienne clé ne servait qu'à
        # empêcher `_is_first_year_change` de re-déclencher chaque année sous
        # l'effet du calendrier légal 2028-2032.
        indexation = params.get('indexation', 1.0)
        duration = params.get('duree_cotisation', RETRAITES_REF_DUREE_ANS)
        # Montee en charge cohortes 5 ans (COR 2024). Formules SYMETRIQUES
        # autour des references : hausse = economie, baisse = surcout miroir
        # (cf METHODOLOGIE.md § Retraites).
        year_idx = max(0, year - POLICY_START_YEAR)
        # Horloge du RUN — pour les leviers dont l'ecart s'ouvre des la
        # premiere annee simulee (duree de cotisation, indexation : leurs
        # references sont FIXES).
        phasing = _year_phasing(year_idx, PHASING_RETRAITES_5ANS)
        # Horloge du CHOC — pour le levier d'age, dont la reference est un
        # CALENDRIER (I3). Meme montee en charge par cohortes, meme index que
        # les canaux macro, qui l'incluent multiplicativement dans
        # PHASING_OFFRE_SENIORS / PHASING_CHOMAGE_SENIORS. Sans cet alignement
        # (revue adverse 25/08), un programme s'ecartant en 2028 avait les
        # memes generations reputees entrees a 100 % pour les moindres pensions
        # et a 60 % pour l'offre de travail, la meme annee. Les deux horloges
        # COINCIDENT des que l'ecart s'ouvre en 2026, ce qui est le cas de tout
        # age different de la valeur gelee : l'alignement ne deplace que ce
        # seul point du domaine, mais c'est celui du curseur laisse au gel.
        phasing_age = _year_phasing(
            year - retraites_annee_debut_ecart_age_handler(params),
            PHASING_RETRAITES_5ANS)
        delta_spending = 0.0
        # v0.6.1 — barème d'âge PLAT et STRICTEMENT SYMÉTRIQUE : une année
        # d'âge = RETRAITES_COEFF_AGE_MD_EUR de moindres dépenses de pension,
        # partout sur [60 ; 67] et dans les deux sens (DG Trésor, COR
        # 27/01/2022, doc n° 12, diapo 5 ; Cour des comptes 02/2025, T6 p. 72
        # — sources, choix assumés et bande de sensibilité dans constants.py).
        # Le barème v0.6.0 (14,2 sous 64 ans) reposait sur une collision entre
        # deux « 17,7 Md€ » sans rapport ; sa falaise de −58 % à 64 ans venait
        # entièrement de ce premier segment, pas d'un phénomène sourcé.
        economie_brute_age = RETRAITES_COEFF_AGE_MD_EUR * ecart_age
        delta_spending -= economie_brute_age * phasing_age
        # Fuite sociale résiduelle (v0.6.1, I9) : une partie des seniors
        # décalés bascule sur d'autres prestations, ce qui ANNULE une part de
        # l'économie brute. On ne retient que 9,6 % (indemnités journalières
        # 36 % + minima sociaux 12 % de la clé DREES/DARES relayée par la Cour
        # des comptes) et NON les 20 % de la clé complète : la part
        # assurance-chômage (52 %) est déjà produite endogènement par la
        # catégorie de dépense `chomage`, indexée sur le taux de chômage — que
        # la bosse seniors (engine/unemployment.py) fait précisément bouger.
        # SYMÉTRIQUE comme le reste du levier : un abaissement d'âge économise
        # ces mêmes prestations. Sources : constants.py § CANAL EMPLOI SENIORS.
        delta_spending += economie_brute_age * phasing_age * FUITE_SOCIALE_RESIDUELLE
        delta_spending -= RETRAITES_COEFF_DUREE_MD_EUR * (duration - RETRAITES_REF_DUREE_ANS) * phasing
        # Indexation : erosion CUMULATIVE — RETRAITES_EROSION_INDEXATION_MD_EUR
        # par annee ecoulee et par point d'ecart a la pleine indexation,
        # plateau RETRAITES_EROSION_PLATEAU_ANS (renouvellement des cohortes).
        delta_spending -= RETRAITES_EROSION_INDEXATION_MD_EUR * (1 - indexation) * min(
            year_idx + 1, RETRAITES_EROSION_PLATEAU_ANS
        )

        # === IMPACTS MACROÉCONOMIQUES ===
        # Gini : Âge départ ↑ = LÉGÈREMENT INÉGALITAIRE
        # Recul âge pénalise davantage classes populaires (mortalité différentielle)
        # Ouvriers : espérance vie -6 ans vs cadres, taux emploi 55-64 ans 52% vs 71%
        # Règle : +1,25 année d'âge au-dessus du droit en vigueur = +0.001 Gini
        # (COR 2024, « effet hétérogène espérance vie »). v0.6.1 : l'écart est
        # mesuré par rapport à l'âge légal de l'ANNÉE, comme le canal
        # budgétaire, pour que le statu quo reste neutre sur les inégalités.
        # Le coefficient lui-même est INCHANGÉ : l'effet distributif du canal
        # emploi n'est pas établi (hétérogénéité forte documentée), il ne sera
        # pas ajusté hors d'une passe dédiée (constants.py, § B.1-13).
        gini_age = RETRAITES_GINI_PAR_ANNEE_ECART * ecart_age

        # Gini : Indexation ↓ = paupérisation retraités (régressif)
        # Règle : Indexation 100%→90% = +0.005 Gini (OFCE Brief 124, 15/02/2024
        # — valeur et source dans constants.py)
        gini_indexation = RETRAITES_GINI_PAR_POINT_DESINDEXATION * (1.0 - indexation)

        # Guard Gini — plein effet l'année où la mesure OUVRE SON ÉCART, puis
        # RETRAITES_GINI_RESIDU_FLUX (flux annuel des nouvelles cohortes de
        # retraités impactées). DEUX HORLOGES, exactement comme le canal
        # budgétaire ci-dessus (`phasing` vs `phasing_age`), et pour la même
        # raison — les deux composantes n'ont pas la même référence :
        #
        # - INDEXATION : sa référence est FIXE (la pleine indexation). Son
        #   écart s'ouvre donc dès la première année simulée → horloge du RUN,
        #   celle de `_is_first_year_change`, inchangée.
        # - ÂGE : sa référence est le CALENDRIER LÉGAL, mobile jusqu'en 2032
        #   (I3). `gini_age` dérive de l'écart de l'ANNÉE, donc un programme
        #   figeant l'âge à 62,75 a un `gini_age` RIGOUREUSEMENT NUL en
        #   2026-2027. L'horloge du run y servait les 100 % sur zéro, et
        #   l'horizon entier ne recevait plus que le résidu : la mortalité
        #   différentielle d'un gel de la réforme était chiffrée au dixième de
        #   sa valeur (clôture de la revue adverse, lot 7). → horloge du CHOC,
        #   `retraites_annee_debut_ecart_age_handler`, la même que les quatre
        #   autres canaux d'une mesure d'âge. Elle vaut POLICY_START_YEAR quand
        #   l'écart est nul partout, donc les scénarios sans curseur d'âge et
        #   tout âge ≠ 62,75 restent bit-identiques.
        if self._is_first_year_change('retraites_gini_indexation',
                                      {'indexation': indexation}):
            gini = gini_indexation
        else:
            gini = gini_indexation * RETRAITES_GINI_RESIDU_FLUX
        if year == retraites_annee_debut_ecart_age_handler(params):
            gini += gini_age
        else:
            gini += gini_age * RETRAITES_GINI_RESIDU_FLUX

        # Pouvoir d'achat : Impact agrégé via retraités (~26% RDB).
        # Formule : -RETRAITES_PA_GEL_TOTAL × (1 - indexation), appliquée chaque
        # année (effet récurrent). Calibration OFCE Brief 124 (15/02/2024) :
        # élasticité PA-retraités/désindexation ≈ -0.7%/an PA agrégé pour gel
        # TOTAL (indexation=0), proportionnelle au ratio d'écart à la pleine
        # indexation. Cumulé sur 5 ans = -3.5%. Valeur et source : constants.py.
        pouvoir_achat = -RETRAITES_PA_GEL_TOTAL * (1.0 - indexation)

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

        # MESURE 2 : PRÉVENTION (budget ABSOLU de prévention institutionnelle)
        # Paramètre distinct du levier "effort_prev_org" (qui optimise la
        # prévention existante) : ici, investissement additionnel pour
        # AUGMENTER le volume de prévention. Le handler ne consomme que
        # l'ÉCART à la base — la base elle-même ne fait que positionner le
        # curseur, et vaut la prévention institutionnelle réellement observée
        # (DREES, comptes de la santé, fiche 21 ; corroborée par l'OCDE).
        # Base, plafond, périmètre SHA et pièges de lecture : constants.py
        # § CALIBRATION PRÉVENTION SANTÉ.
        prevention_budget_montant = params.get('prevention_budget', PREVENTION_BASE_MD_EUR)
        prevention_var = prevention_budget_montant - PREVENTION_BASE_MD_EUR

        # Taux de compensation = part de l'euro investi que la moindre dépense
        # de santé future rembourse.
        # v0.6.1 (I20) — LE DERNIER « REPAS GRATUIT » DU MOTEUR EST RETIRÉ. La
        # v0.5.1 faisait monter ce taux à 2,00 : au-delà de 1,00 la mesure
        # RAPPORTE autant qu'elle coûte, chaque année et pour toujours
        # (+10 Md€/an de prévention réduisaient la dette 2035 d'environ
        # 42 Md€). Cohen 2008 (NEJM), van Baal 2008 (PLoS Med), ACE-Prevention
        # 2010 et OCDE 2019 ch. 6 bornent le retour très en dessous de 1 ;
        # le plafond central retenu est un CHOIX DE MODÉLISATION ASSUMÉ,
        # jamais présenté comme sourcé (aucune institution française ne publie
        # cet effet — IGAS 2024). Sources exactes : constants.py.
        # Décompte : PREVENTION_OFFSET_LAG_YEARS années pleines sans aucun
        # retour, puis la rampe démarre à sa valeur d'UN an (le « +1 ») — la
        # première année de rampe porte déjà un pas complet, elle n'est pas une
        # année de délai supplémentaire déguisée.
        annees_de_rampe = (year - POLICY_START_YEAR) - PREVENTION_OFFSET_LAG_YEARS + 1
        taux_compensation = min(
            max(annees_de_rampe, 0) * PREVENTION_OFFSET_RAMP_PER_YEAR,
            PREVENTION_OFFSET_CENTRAL_CAP,
        )
        # SYMÉTRIQUE, et c'est une correction de neutralité à part entière :
        # la v0.5.1 gatait le retour sur `prevention_var > 0`, si bien qu'une
        # COUPE de prévention rendait 100 % de son montant en économie, pour
        # toujours, sans aucun retour de dépense de santé. Même classe de
        # défaut que le fallback Gini `if spending_impact > 0` : une asymétrie
        # silencieuse au bénéfice d'un seul bord. La même convention appliquée
        # dans les deux sens ne prend pas parti. Effet numérique sur les
        # scénarios publiés : nul (la borne basse du curseur EST la base).
        delta_prevention = prevention_var * (1.0 - taux_compensation)
        # Trajectoire pour +3 Md€/an (cf. METHODOLOGIE.md § Investissement
        # prevention) : 2027 +3,00 → 2031 +2,40 → 2035 +1,50 Md€. La
        # prévention coûte toujours, mais coûte de moins en moins.

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
        # v0.6.0 (audit 08/2026, constats 5-6) : les mesures d'EFFICIENCE sont
        # réellement neutres — Gini 0, PA 0, compétitivité 0 — conformément à
        # METHODOLOGIE.md (« NEUTRALITE TOTALE »). Le triple bonus v0.5.1
        # (gini −0,002 / PA +0,003 / compétitivité +0,001 par effort) n'avait
        # AUCUNE source : couper 30 Md€ ne coûtait rien dans aucune dimension
        # (repas gratuit). Règle du chantier : contrepartie SOURCÉE ou
        # neutralité réelle. Seules les FRANCHISES gardent leurs impacts,
        # eux sourcés (OFCE 2024, INSEE 2024).
        if self._is_first_year_change('sante', params_sante):
            # Gini: Franchises ↑ = impact RÉGRESSIF (touche + les pauvres)
            # Règle : Franchises 100%→200% (Bayrou) = +0.003 Gini (OFCE 2024)
            gini = 0.003 * (taux_franchise - 100) / 100
        else:
            # Années suivantes : impact déjà intégré
            gini = 0.0

        # Pouvoir d'achat: Impact franchises sur reste à charge
        # Règle : Franchises 100%→200% = -0.001 PA (INSEE 2024)
        pouvoir_achat = -0.001 * (taux_franchise - 100) / 100

        # Compétitivité : neutre (optimisation interne, cf. doc)
        competitivite = 0.0

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
        """Allocation sociale unique (ASU) — v0.6.1, items I22 à I26.

        CE QUE LA RÉFORME EST, d'après la seule évaluation administrative
        publiée : Assemblée nationale, commission des affaires sociales,
        mission « flash » sur l'opportunité et les modalités de la création
        d'une allocation sociale unique, rapporteures N. Colin-Oesterlé et
        S. Runel, juillet 2025, restituant les chiffrages DREES + Igas
        (modèle Ines) de juin 2024. Trois faits en découlent, et ils
        contredisent point par point le modèle de la v0.5.1 :

        1. PÉRIMÈTRE — « une harmonisation des bases de ressources et une
           évolution des barèmes » plutôt qu'« une création d'allocation
           unique » ; en clair : RSA + prime d'activité + APL, via un revenu
           social de référence. Les prestations familiales n'y sont pas
           (même position chez F. Lenglart : « unifier […] et non pas les
           fusionner »). Le handler les fusionnait, et les chiffrait à un
           montant supérieur de 60 % à leur valeur réelle (32,3 Md€ de
           prestations familiales) : deux erreurs en une, le champ ET le
           montant. Chiffres exacts : constants.py § ASU.
        2. SIGNE — les scénarios chiffrés valent 0 (variante à coût
           constant) ou +2 Md€/an de COÛT (variantes +2 Md€ pérennes).
           Aucun ne produit d'économie. Le curseur de plafonnement pilote
           donc désormais cet EFFORT, entre les deux seules valeurs que la
           source publie.
        3. TRANSITION — « un coût cumulé de 2 à 13,4 milliards d'euros »
           sur quatre ans, « hors hausse du taux de recours (2,4 milliards
           d'euros d'après DGALN) ». Réduire le non-recours AUGMENTE la
           dépense : le moteur en faisait un gain redistributif gratuit.

        CE QUI RESTE UNE ÉCONOMIE, ET LA SEULE : la gestion. Elle est bornée
        par l'arithmétique (Cour des comptes, communication au Sénat de
        janvier 2026 : la gestion de TOUTE la branche famille vaut environ
        3 Md€ ; sur RSA + prime d'activité + APL la masse mobilisable est de
        0,8 à 1,0 Md€/an). La valeur retenue, 0,3 Md€/an, est une DÉRIVATION
        assumée : la mission parlementaire déclare explicitement que « les
        moyens à la disposition des rapporteurs durant cette mission n'ont
        pas permis d'en estimer précisément le montant ».

        CE QUI EST SUPPRIMÉ, ET POURQUOI — aucune valeur n'est remplacée par
        une autre valeur : les canaux sont RETIRÉS.
        - Effet emploi et bonus d'incitation au travail. Cour des comptes
          2026, chapitre 3, dont le titre est « Des effets significatifs sur
          les revenus des ménages modestes mais pas d'effets observables sur
          l'emploi » ; l'étude sous-jacente est celle de l'Institut des
          politiques publiques d'octobre 2023, commandée par la Cour. Un
          dispositif de 10,6 Md€ et 4,81 millions de bénéficiaires ne produit
          aucun effet emploi mesurable : il est exclu qu'une refonte de
          barèmes en produise un.
        - Effet de compétitivité : aucune source ne le chiffre.
        - Économie de fraude structurelle : le résiduel de fraude qualifiée
          est déjà porté par le curseur « Fraude sociale » (contrat
          anti-double-comptage `_phasing.asu_phasing`), et la masse
          d'anomalies CAF invoquée mélange des indus ET des rappels dus aux
          allocataires, dont la détection AUGMENTE la dépense (Cour des
          comptes, certification des comptes de la sécurité sociale 2024).
        - Économie de « doublons » : sa source ne désignait aucun organisme
          existant.

        Détail complet des sources, URL comprises, et motif de chaque
        retrait : constants.py, section « CALIBRATION ALLOCATION SOCIALE
        UNIQUE ».

        Paramètres
        ----------
        asu_activation : 0/1 — 0 = système actuel, tout impact nul.
        asu_plafonnement : 0,50 à 0,70 — niveau du plafond en part du SMIC
            net. Borné (jamais extrapolé) par `asu_plafonnement_borne`.

        Conventions du moteur respectées ici
        ------------------------------------
        - `delta_spending` POSITIF = surcoût (le handler en produit
          désormais, c'est tout l'objet du lot) ;
        - `gini` et `pouvoir_achat` sont des effets de NIVEAU : le moteur
          les CUMULE (`gini_cible_cumul += …`) et les COMPOSE
          (`purchasing_power *= …`). Émettre le même delta chaque année en
          ferait un flux perpétuel — une réforme de barème déplace le niveau
          des transferts UNE FOIS. Les deux canaux émettent donc l'INCRÉMENT
          de montée en charge, dont la somme vaut exactement le niveau
          atteint, et zéro une fois le régime permanent atteint.
        """
        # CONTRAT (cf. docs/MEASURE_REGISTRY.md) : asu_activation /
        # asu_plafonnement sont lus ici depuis `params` = mesures['asu']
        # (source canonique, IDENTIQUE à celle lue par
        # _phasing.asu_is_active — le prédicat booléen anti-double-comptage
        # consommé par _apply_prestations_indexation et, via asu_phasing,
        # par la fraude sociale).
        activation = params.get('asu_activation', 0)
        plafonnement = asu_plafonnement_borne(
            params.get('asu_plafonnement', ASU_PLAFONNEMENT_DEFAUT))

        if activation == 0:
            return 0.0, 0.0, {}

        # === MONTÉE EN CHARGE (4 ans) — source unique partagée ===
        # Même calendrier que l'anti-double-comptage côté fraude_sociale
        # (cf asu_phasing). L'INCRÉMENT sert aux effets de NIVEAU.
        phasing = asu_phasing(self.mesures, year)
        increment = phasing - asu_phasing(self.mesures, year - 1)

        effort = asu_effort_perenne_md_eur(plafonnement)

        # === BUDGET ===
        # Pérenne : l'effort de la réforme, NET de l'économie de gestion,
        # tous deux montant en charge sur le même calendrier — et PLANCHÉ à
        # zéro par la source unique `asu_solde_perenne_md_eur` (v0.6.1, lot 7).
        # Sans ce plancher, tout plafond sous 53 % du SMIC — dont le premier
        # cran du curseur — dégageait un gain net PERMANENT de 0,3 Md€/an :
        # l'économie de gestion dérivée y dépassait l'effort interpolé, alors
        # que la variante officielle la moins coûteuse (« à coût constant »)
        # a un solde pérenne EXACTEMENT nul. Motif complet : constants.py.
        # Transition : enveloppe des quatre premières années, indépendante
        # du plafond (aucune source ne les lie).
        transition = asu_cout_transition_md_eur(year)
        delta_spending = transition + phasing * asu_solde_perenne_md_eur(plafonnement)
        delta_revenue = 0.0

        impacts = {
            'depenses': delta_spending,
            'recettes': delta_revenue,
            'description': (
                f"ASU plafond {plafonnement:.0%} SMIC — périmètre "
                f"{ASU_PERIMETRE_MD_EUR:.0f} Md€ (RSA + prime d'activité "
                f"+ APL), effort pérenne {effort:.1f} Md€/an"
            ),
        }

        # === POUVOIR D'ACHAT ===
        # Reconstitution depuis le scénario bis DREES/Igas : 4,6 millions de
        # gagnants à +110 €/mois moins 2,9 millions de perdants à
        # -110 €/mois font un transfert net d'environ +2,3 Md€/an,
        # c'est-à-dire, par construction, l'effort budgétaire lui-même.
        # L'effet sur le revenu disponible agrégé vaut donc l'effort
        # rapporté au RDB — et il est NUL à coût constant, où la réforme
        # compte 4,0 millions de perdants pour 3,9 millions de gagnants.
        impacts['pouvoir_achat'] = (effort / RDB_MENAGES_MD_EUR) * increment

        # === GINI ===
        # AUCUNE source ne publie l'effet Gini de l'ASU (les scénarios
        # officiels donnent un taux de pauvreté). Le moteur ne fabrique pas
        # la conversion : il retient une BORNE THÉORIQUE déclarée — un
        # transfert net entièrement reçu par le tout premier centile, cas
        # limite où l'amélioration est arithmétiquement maximale. Toute
        # concentration réelle est moins extrême, donc l'effet réel est plus
        # PETIT : le moteur MAJORE délibérément le bénéfice redistributif,
        # pour qu'on ne puisse pas lui reprocher de minorer l'apport des
        # programmes généreux. Conditionné à l'effort par construction : à
        # coût nul, l'ASU est un pur transfert entre ménages.
        impacts['gini'] = -ASU_GINI_BORNE_PAR_MD_EUR * effort * increment

        _log_debug(self.debug_logs,
                   f"Y{year}: ASU plaf={plafonnement:.0%} - phasing={phasing:.0%}, "
                   f"effort={effort:.2f}Md€, transition={transition:.2f}Md€, "
                   f"total={delta_spending:+.2f}Md€")

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

        # Anti-double-comptage : le périmètre de l'ASU (39 Md€ : RSA + prime
        # d'activité + APL) est un SOUS-ENSEMBLE de cette base de 90 Md€ —
        # et non son égal, comme l'écrivaient la v0.5.1 et la v0.6.0. On
        # neutralise quand même EN TOTALITÉ : c'est le choix CONSERVATEUR
        # (il ne peut qu'ôter des économies à un scénario qui cumule les deux
        # leviers, jamais lui en offrir), et re-baser le levier d'indexation
        # est un chantier distinct que le lot ASU v0.6.1 n'a pas audité.
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

        # Érosion composée : chaque année, la base de prestations s'écarte de
        # (1 - delta_indexation * inflation) par rapport à l'indexation complète.
        # SYMETRIQUE (aligné sur les retraites, revue 2026-08-04) : sous-
        # indexation = économie, sur-indexation = surcoût miroir — le gate de
        # signe historique (`delta_indexation > 0`) rendait la sur-indexation
        # budgétairement gratuite alors que Gini et PA y répondaient déjà.
        if years_effect > 0 and inflation > 0:
            delta_indexation = indexation_ref - indexation
            adjusted_base = total_prestations * (1 - delta_indexation * inflation) ** max(years_effect - 1, 0)
            delta_spending = -(total_prestations - adjusted_base)  # <0 économie, >0 surcoût
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
