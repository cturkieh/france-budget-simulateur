"""Bloc moteur — Croissance (PIB potentiel + multiplicateur keynésien).

Méthodes couvertes :
- ``calculate_growth`` : croissance réelle de l'année. Croissance
  potentielle + écart de chômage + debt drag, puis multiplicateur
  keynésien à profils temporels différenciés (v0.6.7 : une impulsion par
  levier, par flux et par année où son effort varie, profil du levier
  INVEST/TRANSFERS/TAXES — ``_stocker_impulsions``), cicatrice austérité,
  crowding-out, clamp [-3,5 % ; +2,5 %]. Déterministe (bruit tiré
  retiré en v0.6.7).
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

LECTEUR UNIQUE de la croissance potentielle (v0.6.1, correction I6) :
``croissance_potentielle_totale()`` agrège les trois composantes
(tendanciel + offre structurelle + offre de travail). Ses TROIS
consommateurs — ``calculate_growth`` ici, ``calculate_unemployment``
(loi d'Okun, ``engine/unemployment.py``) et la mise à jour de l'output
gap (``engine/orchestrator.py``) — doivent passer par lui. Jusqu'en
v0.6.0 les deux derniers lisaient la composante tendancielle NUE : tout
bonus d'offre était alors lu comme un excès de demande et ouvrait un
écart d'Okun permanent (amplifié ≈15,67× par la convergence NAIRU) et
un output gap permanent. Le contrat est verrouillé en CI par
``tests/test_okun_potentiel_v061.py``, gardes de source incluses.

Paire PRODUCTEUR → CONSOMMATEUR inter-méthodes (invariant load-bearing) :
- ``update_potential_growth`` (appelée APRÈS ``calculate_growth`` dans
  la boucle de ``simulate()``) MUTE ``self.base_params
  ['croissance_potentielle']`` EN PLACE (hystérèse) et réécrit
  ``self._potential_growth_bonus``. ``calculate_growth`` de l'année
  N+1 consomme ces deux valeurs (via
  ``croissance_potentielle_totale()``). Ce sont les SEULS producteurs
  dans la boucle ; ``simulate()`` ne fait que LIRE ``_fiscal_impulses``
  / ``_potential_growth_bonus`` pour le reporting (jamais réécrire).
- ``_labour_supply_bonus`` (offre de TRAVAIL) est le troisième terme du
  lecteur unique. Son producteur est ``update_labour_supply``, appelée en
  TÊTE de l'année par ``simulate()`` (et non en fin, comme
  ``update_potential_growth``) : un choc d'offre de travail ne dépend que
  du paramètre de politique et du calendrier légal, il n'entre dans
  aucune boucle de rétroaction qu'il faudrait casser par un lag. Elle
  écrit aussi ``_labour_supply_level``, le NIVEAU de PIB déjà acquis, dont
  le bonus de l'année est l'incrément. Il vit hors du tendanciel à
  dessein — voir la docstring de ``croissance_potentielle_totale``.
- Conséquence non évidente : ``base_params['croissance_potentielle']``
  N'EST PAS immutable — il dérive année après année. L'hôte
  ``_reset_state`` DOIT le restaurer à la valeur utilisateur entre deux
  simulations (il le fait). Ne pas supposer ``base_params`` constant.
- États accumulateurs cross-année mutés par ces méthodes :
  ``_fiscal_impulses`` (dict {(année, levier, flux, sens): (variation,
  k, profil)}) et ``_niveaux_impulsion`` (effort de chaque (levier, flux) au
  budget précédent), ``_supply_years`` /
  ``_supply_bonus_by_key`` (dépréciation progressive de l'offre).
  Tous initialisés / réinitialisés par l'hôte (``__init__`` /
  ``_reset_state``), hors périmètre du split (non touché).

Catch large du bloc effet d'offre — GARDE DÉFENSIF INERTE (re-analyse
adverse 2026-05-16) : le ``except Exception`` de
``update_potential_growth`` est **inatteignable en run normal**. Preuve :
aucune opération du bloc ne peut lever (``_get_default_values`` =
return dict littéral pur ; ``.get`` sur dict ; ``isinstance`` neutralise
les types tordus avant arithmétique ; ``np.log2(1+delta)`` avec
``delta>0.1`` garanti ⇒ argument > 1.1, jamais d'exception ; depuis v0.6.7
la valeur passe par la porte ``validate_param_domains`` — non finie →
défaut, hors domaine → clampée —, exactement comme côté handler). Exception
connue : un entier hors de la plage des flottants (JSON de 400 chiffres)
lève OverflowError, attrapée et tracée ci-dessous. Le seul autre
vecteur (bloc non-dict dans ``self.mesures`` : ``null`` ou mal formé)
n'est PAS arrêté en amont — ``apply_measures`` saute un bloc null et
absorbe un bloc mal formé dans son ``try`` per-mesure — : il est
neutralisé dans la boucle par ``valeur_brute`` (levier lu comme absent,
l'anomalie d'un bloc mal formé restant signalée par la porte unique,
Sentry FRANCE-BUDGET-Z). Sévérité réelle : LOW / dette défensive,
PAS un silent-failure atteignable. Néanmoins, par conformité à la règle
projet « zéro catch silencieux » et pour qu'un futur refactor qui le
rendrait atteignable ne dégrade pas la croissance potentielle en
silence, le ``except`` émet désormais ``logger.error(exc_info=True)``
(auto-capté Sentry via LoggingIntegration, no-op sans DSN), aligné sur
``apply_measures``. ``_potential_growth_bonus = 0.0`` conservé : le bloc
ne s'exécutant jamais sur input atteignable, golden master byte-identique
(vérifié). Item Phase 2 « catch silencieux » CLÔTURÉ par cette
instrumentation (cf ``docs/REFACTOR_SPLIT_PLAN.md``).

Helpers hôte via MRO : ``self._get_decay_profile()``,
``self._get_default_values()``. Lecture seule : ``self.economic_coeffs``,
``self.multipliers`` (instance ``FiscalMultipliers``), ``self.mesures``.
Sink de logs : ``self.debug_logs`` via ``_log_debug``.
Tous attributs d'instance de ``BudgetSimulatorV45``.
"""
import logging
from typing import Dict

import numpy as np

from .._logging import _log_debug
from .._seniors import offre_seniors_niveau_pib
from ..constants import OUTPUT_GAP_RAPPEL, REGIME_DEMI_LARGEUR_CROISSANCE
from ._regimes import au_dessus, en_dessous
from ._param_domain import validate_param_domains, valeur_brute

logger = logging.getLogger(__name__)


class GrowthMixin:
    """Bloc moteur — Croissance (PIB potentiel + multiplicateur keynésien)."""

    def croissance_potentielle_totale(self) -> float:
        """Croissance potentielle TOTALE — lecteur unique de la trajectoire
        d'offre (v0.6.1, correction I6).

        Trois blocs du moteur ont besoin de cette valeur : la croissance
        (point de départ de l'année), la loi d'Okun (référence de l'écart
        conjoncturel) et l'output gap (référence de l'écart d'activité).
        Jusqu'en v0.6.0 seul le premier ajoutait les bonus d'offre, les deux
        autres se contentaient de la composante tendancielle
        ``base_params['croissance_potentielle']`` : tout choc d'OFFRE était
        donc lu par Okun comme un excès de DEMANDE. L'écart ouvert chaque
        année valait ``okun × bonus`` et la convergence NAIRU
        (``u = 0,94·u + 0,06·nairu``) l'accumulait vers un état stationnaire
        ``0,94/0,06 ≈ 15,67`` fois plus grand — soit ±1,10 pt de chômage
        permanent au plafond de bonus ±0,20 pt, plus un output gap permanent
        de ±0,20 pt réinjecté dans la courbe de Phillips et dans le choix du
        multiplicateur budgétaire.

        Un choc d'offre déplace le PIB potentiel : par construction il ne
        crée ni écart d'Okun ni output gap. Les trois lectures passent donc
        par cette méthode, et l'égalité entre elles est verrouillée en CI
        (``tests/test_okun_potentiel_v061.py``).

        Trois composantes, volontairement séparées :

        - ``base_params['croissance_potentielle']`` — tendanciel, MUTÉ en
          place par l'hystérèse de ``update_potential_growth`` puis clippé
          dans [0,007 ; 0,012] ;
        - ``_potential_growth_bonus`` — offre STRUCTURELLE (``SUPPLY_EFFECTS``
          : recherche, éducation, transition, rénovation), plafonnée ±0,20 pt ;
        - ``_labour_supply_bonus`` — offre de TRAVAIL (canal emploi seniors,
          v0.6.1) : INCRÉMENT annuel d'un effet de NIVEAU de PIB, produit par
          ``update_labour_supply``.

        - ``_debt_drag`` (v0.6.7, B3) — traînée de dette, effet d'OFFRE :
          ``debt_drag × (dette/PIB − 0,9)`` au-delà de 90 %, posé par
          ``calculate_growth`` en tête d'année (premier des trois lecteurs).
          Jusqu'en v0.6.6 il frappait la croissance EFFECTIVE sans toucher le
          potentiel : la loi d'Okun le lisait comme un choc de demande et, avec
          un output gap en niveau, il ouvrait un écart permanent (−2,0 pts
          cumulés au statu quo en 2035). La littérature le place sur la
          croissance de long terme (cf. constants.py, DEBT_DRAG_*).

        Les deux bonus vivent hors du tendanciel À DESSEIN : les reverser
        dans ``base_params['croissance_potentielle']`` les ferait écrêter par
        le clip ET figer par l'hystérèse, alors qu'ils sont transitoires.
        Lecteur PUR : cette méthode ne mute rien.
        """
        return (self.base_params['croissance_potentielle']
                + self._potential_growth_bonus
                + self._labour_supply_bonus
                + self._debt_drag)

    def update_labour_supply(self, year: int) -> None:
        """Canal d'offre de travail seniors → croissance potentielle (v0.6.1, I7).

        Une mesure d'âge augmente l'offre de travail, donc le PIB POTENTIEL :
        ``+0,80 pt de NIVEAU de PIB par année d'AOD`` à long terme (consensus
        des trois équipes du COR, séance du 26/03/2026 : « 0,7 à 0,9 point »,
        « 210 000 à 240 000 emplois »). Sources, profils et choix assumés :
        ``constants.py``, section « CANAL EMPLOI SENIORS ».

        NIVEAU ≠ TAUX — c'est tout l'objet de cette méthode. La table décrit
        un NIVEAU de PIB ; ``calculate_growth`` consomme un TAUX. Le bonus de
        l'année est donc l'INCRÉMENT du niveau : la somme des incréments
        reconstitue exactement le niveau visé, et l'incrément maximal vaut
        +0,12 pt de croissance une seule année (Y5). La v0.6.0 ajoutait
        « +0,8 pt » au taux CHAQUE année — ~+8 % de PIB en dix ans, quatorze
        fois l'effet publié : c'est l'une des deux raisons de son retrait.

        Le niveau se recalcule à chaque année à partir de l'écart d'âge de
        l'ANNÉE (la référence légale monte jusqu'en 2032) : un incrément
        NÉGATIF est donc normal et voulu quand l'avance d'un programme sur le
        droit en vigueur se réduit.

        Appelée en TÊTE de l'année simulée (``simulate()``), à la différence
        de ``update_potential_growth`` qui la clôt. Ce n'est pas une entorse
        au lag d'un an de l'impulsion budgétaire : ce lag existe pour casser
        la circularité mesures → macro → flux → mesures, alors qu'un choc
        d'offre de travail ne dépend QUE du paramètre de politique et du
        calendrier légal — aucune circularité à casser, et lagger décalerait
        d'un an tout le profil publié.
        """
        niveau = offre_seniors_niveau_pib(self.mesures, year)
        self._labour_supply_bonus = niveau - self._labour_supply_level
        self._labour_supply_level = niveau

        if abs(self._labour_supply_bonus) > 0.00001:
            _log_debug(self.debug_logs,
                f"Y{year}: Offre de travail seniors = {self._labour_supply_bonus*100:+.3f}% "
                f"(niveau cumule {niveau*100:+.3f}% de PIB)")

    def _stocker_impulsions(self, year: int, eco_state: Dict) -> None:
        """Impulsions budgétaires de l'année, levier par levier (v0.6.7, audit
        10/2026, bloc A constats 1 et 2).

        Une impulsion est la VARIATION de l'effort d'un levier entre deux
        budgets successifs, en % du PIB nominal de son année — la définition
        usuelle de l'impulsion budgétaire (variation du solde, FMI/CE). Elle est
        lue dans ``_last_impacts`` (budget de t−1 : lag d'un an, cf.
        l'orchestrateur) et comparée au niveau mémorisé l'appel précédent
        (``_niveaux_impulsion``). Convention de signe : effort > 0 =
        consolidation, donc effet sur la croissance = −k × impulsion, k ≥ 0.

        Ce que cela remplace (v0.6.6, deux erreurs de calcul) :
        - une impulsion n'était stockée qu'au changement du hash de
          ``self.mesures``, constant pendant une simulation : UNE impulsion par
          scénario, égale au NIVEAU de la première année ; la montée en charge
          (fraude : 0,10 → 0,47 % du PIB) n'était jamais multipliée ;
        - un seul multiplicateur par scénario, moyenne des multiplicateurs
          SIGNÉS pondérée par l'effort BRUT puis appliquée à l'effort NET : un
          programme équilibré n'avait aucun effet keynésien et une consolidation
          nette pouvait être comptée comme une relance.

        Granularité : chaque levier est multiplié FLUX PAR FLUX (recettes au
        canal fiscal, dépenses au canal investissement ou transferts/générique),
        sans quoi la même compensation se reproduirait à l'intérieur d'un levier
        à deux flux. Exception : les leviers dont le coefficient est calibré sur
        l'effet NET (``FiscalMultipliers.MESURES_MULTIPLICATEUR_NET``) sont
        multipliés sur leur solde. Profil : celui du levier
        (``_get_decay_profile``), pour ses deux flux.

        Sens (consolidation / expansion) : celui du NIVEAU du flux par rapport
        au statu quo, pas celui de la variation. Retirer une hausse d'impôts
        porte donc le multiplicateur d'une hausse : l'effet cumulé d'une mesure
        retirée revient exactement à zéro, et le cumul ne dépend que du niveau
        atteint, pas du chemin (même état macro). Un flux qui change de signe
        dans l'année est scindé en zéro.

        Aucun plafond sur la taille : la littérature qui calibre ces
        coefficients estime des effets linéaires dans la taille de l'ajustement
        (Guajardo, Leigh & Pescatori 2014 ; FMI, WEO oct. 2010 ch. 3) et
        Blanchard & Leigh (2013) trouvent des effets PLUS forts, jamais plus
        faibles, pour les grandes consolidations. L'ancien plafond (niveau
        d'effort ≤ 2 % du PIB) tronquait le coût — ou le gain — des seuls
        programmes les plus brutaux. Le filet reste le clip de croissance
        [−3,5 % ; +2,5 %] ; l'effet est une convolution finie (6 ans) des
        impulsions, borné par k_max × 1,15 × 1,3 × Σ|impulsions récentes|.
        """
        pib = self.pib_nominal
        niveaux: Dict = {}
        for m_id, m_impact in self._last_impacts.items():
            if not isinstance(m_impact, dict):
                continue
            # Un levier en échec porte 0/0 (HANDLER_FAILED_KEY) : niveau nul,
            # comme dans le budget de l'année.
            dep = float(m_impact.get('depenses', 0) or 0)
            rec = float(m_impact.get('recettes', 0) or 0)
            if m_id in self.multipliers.MESURES_MULTIPLICATEUR_NET:
                niveaux[(m_id, 'solde')] = (rec - dep) / pib
            else:
                niveaux[(m_id, 'recettes')] = rec / pib
                niveaux[(m_id, 'depenses')] = -dep / pib

        compositions = {
            'recettes': {'depenses': 0.0, 'recettes': 1.0, 'investissement': 0.0},
            'solde': {'depenses': 0.0, 'recettes': 1.0, 'investissement': 0.0},
        }
        for cle in sorted(set(niveaux) | set(self._niveaux_impulsion)):
            m_id, canal = cle
            avant = self._niveaux_impulsion.get(cle, 0.0)
            apres = niveaux.get(cle, 0.0)
            troncons = [(avant, 0.0), (0.0, apres)] if avant * apres < 0 else [(avant, apres)]
            for debut, fin in troncons:
                delta = fin - debut
                if delta == 0.0:
                    continue
                sens = 'consolidation' if debut + fin > 0 else 'expansion'
                if canal == 'depenses':
                    composition = {'depenses': 1.0, 'recettes': 0.0,
                                   'investissement': 1.0 if m_id in self.INVESTMENT_CORE_MEASURES else 0.0}
                else:
                    composition = compositions[canal]
                # La matrice porte le signe de l'effet (négatif en
                # consolidation) ; ici le signe vient de l'impulsion, la
                # matrice n'en donne que l'amplitude.
                k = abs(self.multipliers.get_multiplier(sens, composition, eco_state, year, m_id))
                self._fiscal_impulses[(year, m_id, canal, sens)] = (
                    delta, k, self._get_decay_profile(m_id))
                if abs(delta) > 0.0005:
                    _log_debug(self.debug_logs,
                        f"Y{year}: [IMPULSION] {m_id}/{canal} {sens} "
                        f"{delta*100:+.3f}% PIB, k={k:.2f}")
        self._niveaux_impulsion = niveaux

    def calculate_growth(self, year: int, economic_state: Dict) -> float:
        output_gap = economic_state['output_gap']
        unemployment_gap = economic_state['unemployment_gap']
        effort_budgetaire = economic_state['effort_budgetaire']
        debt_ratio = economic_state['debt_ratio']
        unemployment = economic_state.get('unemployment', 0.076)
        deficit_ratio = economic_state.get('deficit_ratio', -0.054)

        # Traînée de dette = effet d'OFFRE (v0.6.7, B3) : elle abaisse le
        # POTENTIEL de l'année, que lisent ensuite les trois lecteurs (croissance,
        # Okun, output gap) — elle n'ouvre donc ni écart d'Okun ni output gap.
        self._debt_drag = (self.economic_coeffs['debt_drag'] * (debt_ratio - 0.9)
                           if debt_ratio > 0.9 else 0.0)
        if self._debt_drag:
            _log_debug(self.debug_logs, f"Y{year}: Debt drag {self._debt_drag*100:.2f}% (potentiel)")

        croissance = self.croissance_potentielle_totale()
        croissance += self.economic_coeffs['chomage_gap_weight'] * unemployment_gap

        # Rappel vers le potentiel (v0.6.7, B3) : avec un output gap en NIVEAU,
        # rien ne ramenait le PIB vers son potentiel — un choc de demande restait
        # un écart permanent. La croissance de l'année corrige une fraction
        # OUTPUT_GAP_RAPPEL de l'écart de fin d'année précédente : persistance
        # 1 − λ = 0,8 par an, la forme des modèles semi-structurels du FMI
        # (cf. constants.py). Vitesse de croisière = potentiel ; écart → rappel.
        rappel = -OUTPUT_GAP_RAPPEL * output_gap
        croissance += rappel
        if abs(rappel) > 0.0005:
            _log_debug(self.debug_logs, f"Y{year}: Rappel vers le potentiel {rappel*100:+.2f}% (gap {output_gap*100:+.2f}%)")

        # === MULTIPLICATEUR KEYNÉSIEN — IMPULSIONS PAR LEVIER (v0.6.7) ===
        # effet(t) = Σ_levier Σ_âge −k × impulsion(t − âge) × profil(âge), où
        # l'impulsion est la VARIATION annuelle de l'effort du levier (en % du
        # PIB) : cf. `_stocker_impulsions`. Profils de décroissance par levier :
        # - INVEST : pic en Y2, persistance longue (Bom & Ligthart 2014, FMI 2020)
        # - TRANSFERS : front-loaded, decay rapide (Ramey 2019, FMI 2014)
        # - TAXES : profil intermédiaire (Blanchard & Leigh 2013)
        # Sommes normalisées <= 2.0
        eco_state = {
            'output_gap': output_gap,
            'debt_ratio': debt_ratio,
            'unemployment_gap': unemployment_gap,
            'interest_rate': economic_state.get('interest_rate', 0.023)
        }
        self._stocker_impulsions(year, eco_state)

        # Résidus de TOUTES les impulsions passées, sans condition sur l'effort
        # courant : jusqu'en v0.6.6 cette somme vivait sous `abs(effort) >
        # 0,001` et s'arrêtait net l'année où l'effort repassait sous 0,1 % du
        # PIB (taxe superprofits : −0,07 pt prévu en 2030, 0 servi).
        total_multiplier_effect = 0.0
        for (impulse_year, _m, _canal, _sens), (delta, k, profil) in self._fiscal_impulses.items():
            age = year - impulse_year
            if 0 <= age < len(profil):
                total_multiplier_effect -= k * delta * profil[age]
        croissance += total_multiplier_effect

        if total_multiplier_effect != 0:
            _log_debug(self.debug_logs,
                f"Y{year}: Effet multiplicateur total = {total_multiplier_effect*100:.3f}% "
                f"({len(self._fiscal_impulses)} impulsion(s) stockées)")

        # EFFET CONFIANCE « Alesina » : SUPPRIMÉ en v0.6.0 (audit 08/2026).
        # L'austérité expansionniste est réfutée sur échantillon corrigé (FMI
        # WEO oct. 2010 ch. 3 : « the opposite is true » ; Guajardo, Leigh &
        # Pescatori 2014 ; Jordà & Taylor 2016) ; la position finale de l'école
        # Alesina (AFG 2019) ne défend que la composition — captée par
        # adjustments['confidence'] = 1,10 (simulator.py, conservé). Le canal
        # confiance mesurable vit sur la prime de taux (engine/debt.py) :
        # consolidation → prime plus basse → charge d'intérêts plus faible.
        # Ne PAS réintroduire de bonus sur le taux de croissance, même réduit.

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

        # Stabilisateurs automatiques : les escaliers v0.5.1 (+0,5 pt si
        # chômage > 9 %, +0,1 pt si déficit < −4 %) sont SUPPRIMÉS en v0.6.0.
        # Erreur de nature : un stabilisateur joue sur le SOLDE, pas sur le
        # taux de croissance (FIPECO/Ecalle ; OCDE ECO/WKP(2020)44 ; CE Mourre
        # et al. 2019) — et le second était vrai chaque année en baseline
        # (+0,10 pt/an permanent disparaissant pour qui assainit). Le moteur
        # produit la stabilisation par CONSTRUCTION (élasticité PO 1,0 +
        # dépenses chômage indexées) ; contrat vérifié en CI :
        # SEMI_ELASTICITE_SOLDE_PIB_FRANCE (constants.py) ∈ [0,50 ; 0,60].

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

        # NB v0.6.1 : le « volet emploi seniors » (COR, séance plénière du
        # 26 mars 2026, Document n° 2 — consensus des trois équipes :
        # +0,7-0,9 pt de PIB par année d'AOD) a été implémenté ICI en v0.6.0
        # PUIS RETIRÉ. Il est RÉINTRODUIT en v0.6.1, mais PAS à cet endroit —
        # et les trois défauts qui avaient motivé son retrait sont fermés par
        # construction, pas par un coefficient :
        #  1. écho de chômage divergent : il était routé comme un choc de
        #     DEMANDE. Il passe désormais par la croissance POTENTIELLE
        #     (update_labour_supply → croissance_potentielle_totale), donc
        #     Okun et l'output gap ne le voient pas (correction I6) ;
        #  2. sur-calibrage ~+49 % : « +0,8 pt » était ajouté au TAUX de
        #     croissance chaque année, alors que la source publie un effet de
        #     NIVEAU de PIB. Le moteur ne consomme plus que son incrément ;
        #  3. double comptage des cotisations retraite : le handler retraites
        #     n'a plus AUCUN slot recettes, la ligne naît du seul canal PIB.
        # Ne pas réintroduire de terme seniors dans ce bloc de DEMANDE.

        # Bruit stochastique RETIRÉ (v0.6.7, recalage du corridor) : un tirage
        # N(0 ; 0,3 %) à graine fixe, identique pour tous les scénarios, ne porte
        # aucune information. Avec l'output gap en NIVEAU il devenait un choc de
        # demande persistant (+0,6 % de PIB en 2029) qui sortait à lui seul le
        # scénario de référence du corridor de la mission (dette 2029 −2,26 pt ;
        # sans lui −0,39). Ne pas réintroduire : une incertitude se publie en
        # variante, pas en tirage caché dans la trajectoire centrale.
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
        # ×0,997 si croissance < −2 %, ×1,002 si > 2 % (après l'an 3), à
        # transition CONTINUE (v0.6.7, engine/_regimes.py, ±0,5 pt) : c'étaient
        # des marches. Seul im_rabot_2029 effleure la zone négative (+0,01 pt de
        # dette 2035, mesuré au lot 3b).
        w_negative = en_dessous(growth, -0.020, REGIME_DEMI_LARGEUR_CROISSANCE)
        w_rebond = au_dessus(growth, 0.020, REGIME_DEMI_LARGEUR_CROISSANCE) if year > 3 else 0.0
        if w_negative > 0:
            self.base_params['croissance_potentielle'] *= 1 + (0.997 - 1) * w_negative
            _log_debug(self.debug_logs, f"Y{year}: Hystérèse négative (poids {w_negative:.2f})")
        if w_rebond > 0 and self.base_params['croissance_potentielle'] < 0.012:
            self.base_params['croissance_potentielle'] *= 1 + (1.002 - 1) * w_rebond
            _log_debug(self.debug_logs, f"Y{year}: Rebond potentiel (poids {w_rebond:.2f})")

        # --- Effet d'offre structurel ---
        try:
            defaults = self._get_default_values()

            for key, cfg in self.SUPPLY_EFFECTS.items():
                default_val = defaults.get(cfg['measure_id'], {}).get(cfg['param'], 0)
                # Lecture BRUTE de self.mesures (hors porte unique) : bloc
                # null/mal formé ou clé à None → défaut, delta nul.
                current_val = valeur_brute(self.mesures, cfg['measure_id'],
                                           cfg['param'], default_val)

                if not isinstance(current_val, (int, float)) or not isinstance(default_val, (int, float)):
                    continue
                # v0.6.7 : la valeur passe par la MÊME porte que celle que lit le
                # handler (apply_measures, mode tolérant) — non finie → défaut,
                # hors domaine PARAM_DOMAINS → clampée. Lue brute, un
                # `recherche_publique.budget = inf` retiré côté dépense donnait
                # ici +0,2 pt de croissance potentielle, et un budget hors domaine
                # un effet d'offre que la dépense clampée ne finance pas. En
                # strict, la porte a déjà levé dans apply_measures la même année.
                propre = validate_param_domains(
                    cfg['measure_id'], {cfg['param']: current_val}, strict=False,
                    warned=getattr(self, '_domain_clamp_warned', None))
                current_val = propre.get(cfg['param'], default_val)

                delta = current_val - default_val

                # v0.6.0 (audit 08/2026) : effet SYMÉTRIQUE. Une coupe sous le
                # défaut érode la croissance potentielle comme une hausse
                # l'augmente — même délai, même forme log2, même dépréciation.
                # L'élasticité d'output au capital public porte sur le STOCK,
                # donc joue dans les deux sens par construction (Bom & Ligthart
                # 2014, méta-analyse 578 estimations, élasticité moyenne 0,106 ;
                # FMI WEO oct. 2010 ch. 3 ; Fieldhouse & Mertens 2025 pour la
                # R&D). v0.5.1 ne testait que `delta > 0.1` : les coupes
                # étaient structurellement gratuites côté offre.
                # v0.6.7 (lot 3b) : plus de porte à 0,1 Md€. Le bonus vaut
                # coeff × log2(1 + |delta|), nul en 0 : la porte ne faisait que le
                # faire naître d'un coup à coeff × log2(1,1) (transition_ecologique
                # à 0,1 Md€ : −0,80 pt de dette 2035 sur « Budget 2026 (voté) »).
                if delta != 0:
                    years_active = self._supply_years.get(key, 0) + 1
                    self._supply_years[key] = years_active

                    if years_active >= cfg['delay']:
                        signe = 1.0 if delta > 0 else -1.0
                        effective_delta = np.log2(1 + abs(delta))  # rendements décroissants
                        self._supply_bonus_by_key[key] = signe * cfg['coeff'] * effective_delta
                else:
                    # Dépréciation progressive avec coefficient différencié
                    # (symétrique : l'amplitude décroît quel que soit le signe)
                    prev_bonus = self._supply_bonus_by_key.get(key, 0)
                    if abs(prev_bonus) > 0.00001:
                        self._supply_bonus_by_key[key] = prev_bonus * (1 - cfg['deprec'])
                    else:
                        self._supply_bonus_by_key[key] = 0
                    # Décroître aussi le compteur d'années
                    prev_years = self._supply_years.get(key, 0)
                    if prev_years > 0:
                        self._supply_years[key] = max(0, prev_years - 1)

            # Cap +0.20pt et plancher symétrique −0.20pt (bornes conventionnelles
            # assumées, METHODOLOGIE § design)
            self._potential_growth_bonus = float(np.clip(
                sum(self._supply_bonus_by_key.values()), -0.002, 0.002))

            if abs(self._potential_growth_bonus) > 0.0001:
                _log_debug(self.debug_logs,
                    f"Y{year}: Effet d'offre potentiel = {self._potential_growth_bonus*100:+.3f}% "
                    f"(actifs: {', '.join(k for k, v in self._supply_bonus_by_key.items() if abs(v) > 0.00001)})")

        except Exception as e:
            # Garde défensif : inatteignable en run normal — un bloc non-dict
            # (null ou mal formé) est neutralisé par `valeur_brute`, une valeur
            # non numérique par la garde de type avant l'arithmétique (cf.
            # docstring du module). Mais SI un refactor futur le rendait
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
