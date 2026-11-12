"""Release E — impôts à taux, avec paramètre de comportement (4 handlers).

Mesures couvertes (recette calculée par le moteur à partir d'un taux et d'une
assiette qui suit le PIB nominal depuis son année source, règle R-IDX du
contrat ; mode montant ``rendement_*`` exclusif quand la source ne donne qu'un
montant) :
- ``impot_plancher_patrimoine`` : impôt plancher sur les patrimoines de plus
  de 100 M€ (taux, évitement) ;
- ``fiscalite_capital`` : prélèvement forfaitaire sur les revenus du capital
  (part impôt sur le revenu, prélèvements sociaux, élasticité ; ou montant) ;
- ``multinationales`` : bénéfices transférés imposés en France, taxe sur les
  services numériques (taux, érosion ; ou montant) ;
- ``operations_financieres`` : taxe sur les transactions financières (taux,
  élasticité des volumes ; ou montant), rachats d'actions, crypto-actifs.

Contrat du dépôt parent ``docs/plans/contrat-curseurs-release-E-2026-11.md``,
§ 1.1 (règles communes), § 1.2-5 à 1.2-8 (fiches), § 1.3 (coefficients par
Md€), § 3 (évitement, décision D3), § 4.1 (règles Z, Z-ter, M, K, F). Corps
écrits par le chantier W4 ; ce fichier n'appartient qu'à lui.

Règles communes aux quatre handlers :
- **R-IDX** : un TAUX s'applique à une assiette sourcée à une année source
  (``ANNEE_SOURCE_*``), qui suit le PIB nominal depuis cette année
  (``self._indice_pib_source``) : la recette ne dépend pas de l'année d'entrée
  du programme. Un MONTANT en Md€ (modes ``rendement_*``, bénéfices
  récupérés, rachats d'actions, crypto-actifs) est constant en euros courants,
  sans aucun indice.
- **R-MODE** : un mode montant est le rendement NET annoncé par la source :
  ni taux, ni comportement, ni indice ne s'y appliquent, et les paramètres
  qu'il masque sont ignorés (porte ``valider_modes_exclusifs`` : refus en
  strict, correction tracée en tolérant). L'impôt plancher n'a pas de mode
  montant : toutes ses sources l'écrivent en taux.
- **D3 (anti-double-compte, exigence du mainteneur)** : un paramètre de
  comportement (évitement, élasticité, érosion) ne contient QUE la réaction
  des contribuables visés. Il ne multiplie qu'une recette exprimée en fonction
  des PARAMÈTRES du levier et de l'indice d'assiette ; aucun handler ne lit
  l'inflation, le chômage, l'écart de production, la dette ni un autre levier,
  hors des deux lectures croisées déclarées (intensité de l'ISF pour le
  plancher, règle Z ; taux d'IS pour les bénéfices récupérés, règle M1). Les
  effets macro (multiplicateur, compétitivité, Gini) restent ceux que le
  moteur calcule à partir de la recette : à évitement nul, la recette du
  plancher est le rendement statique taux × assiette, et un évitement e au
  taux τ est indiscernable, sur chaque canal, d'un impôt statique au taux
  τ × (1 − e).
- **Retour anticipé** (§ 1.1) : toutes les valeurs reçues neutres ET aucune clé
  ponctuelle du levier au traqueur → ``(0.0, 0.0, {})`` avant tout calcul.
  Sinon le handler calcule, y compris au neutre : un levier revenu au neutre
  (profil « une seule année ») rend son effet ponctuel par
  ``_effet_ponctuel`` (mode incrément). Un mode montant n'a pas de neutre (son
  neutre est l'absence de la clé) : il calcule toujours.
- **Effets ponctuels** (Gini, compétitivité) : ``self._effet_ponctuel`` avec
  une fonction d'effet PURE de ce module, qui ne lit que le dictionnaire de
  niveaux qu'on lui passe (paramètres ET lectures croisées) : ni le PIB, ni
  l'indice d'assiette, ni le phasage ; le cumul ne dépend que du niveau
  atteint. Effet = constante signée du socle × recette de référence (hors
  indice), aucun signe ajouté ici (règle d'écriture B1, § 1.1).
- **Aucun effet direct sur le chômage** : le multiplicateur fiscal du moteur
  porte le canal de la demande (classe « recettes », comme tout prélèvement).
- **Domaine** : les bornes vivent dans ``policy_measures.json`` et sont
  appliquées par les portes du moteur (``engine/_param_domain.py``) ; le
  handler ne réécrête rien en silence.

Couplages avec ``BudgetSimulatorV45`` (instance hôte du mixin) :
- lit ``self.mesures`` : lectures croisées ``isf_climatique`` (plancher) et
  ``impot_societes`` (bénéfices récupérés) ; pour l'avis Z-ter seulement (sans
  effet sur le calcul), ``fiscalite_capital``, ``csg``, ``impot_revenu``,
  ``fiscalite_patrimoine`` et ``impot_revenu_cible`` ;
- lit l'horloge du plancher (``self._origine``), l'indice d'assiette
  (``self._indice_pib_source``) et le traqueur des effets ponctuels
  ``self._measure_params_tracker`` (retour anticipé seulement, sans l'écrire) ;
  appelle ``self._effet_ponctuel`` (simulator.py), qui seul le met à jour ;
- consigne l'avis Z-ter dans ``self._avis`` (``report.warnings``), rapport
  seulement, aucun effet sur le calcul, pour le monde du programme et le mode
  historique seulement : même statut que le journal des rabots du vivier
  (``handlers/efficience._noter_rabot_vivier``).
"""
import math
import numbers
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Tuple

from .._logging import _log_debug
from ..constants import (
    A_CAPITAL_IR,
    A_CAPITAL_PS,
    A_TSN,
    ANNEE_SOURCE_CAPITAL,
    ANNEE_SOURCE_PLANCHER,
    ANNEE_SOURCE_TSN,
    ANNEE_SOURCE_TTF,
    COMPET_IMPOTS_PRODUCTION_PAR_MD,
    COMPET_IS_EXCEPTIONNEL_PAR_MD,
    COMPET_IS_PAR_MD,
    COMPET_ISF_EFFECTIF_PAR_MD,
    COMPET_PATRIMOINE_PAR_MD,
    ETI_PLANCHER_FACTEUR,
    GINI_ISF_EFFECTIF_PAR_MD,
    GINI_PATRIMOINE_PAR_MD,
    ISF_PHASAGE,
    ISF_TAUX_MAX,
    NEUTRES_RELEASE_E,
    PLANCHER_TAUX_TEXTE,
    R_REF_PLANCHER,
    TAUX_IS_REFERENCE_BENEFICES,
    TTF_PAS_ELASTICITE_VOLUME,
    V_REF_TTF,
)
from ..engine.cadre import charger_droit_en_vigueur, reference_du_profil
from ._phasing import _year_phasing
from ._types import ImpactsDict, canaux_menages


# Idiome mixin-self typing : NE PAS factoriser dans _types.py (casse la
# liaison self mypy + risque MRO). Réplication volontaire. Cf Lot D.
if TYPE_CHECKING:
    from ._types import _SimulatorState

    _MixinBase = _SimulatorState
else:
    _MixinBase = object


# Clés des effets ponctuels de chaque levier (une clé par sous-effet, convention
# de ``_ponctuel`` : une clé ne sert qu'à UN appel par année et par levier).
CLES_PONCTUELLES = {
    'impot_plancher_patrimoine': ('impot_plancher_patrimoine', 'impot_plancher_patrimoine_competitivite'),
    'fiscalite_capital': ('fiscalite_capital', 'fiscalite_capital_competitivite'),
    'multinationales': ('multinationales_competitivite',),
    'operations_financieres': ('operations_financieres_competitivite',),
}

# Avis Z-ter (contrat § 4.1) : texte du contrat, sans calcul (le calage du
# rendement est fait à droit constant ; la part des hausses payée par les
# foyers concernés n'est pas publiée).
AVIS_Z_TER = ("Impôts déductibles de l'impôt plancher relevés en même temps : la recette "
              "du plancher est surestimée, au plus de la part de ces hausses payée par les "
              "foyers concernés (non chiffrable faute de répartition publiée).")
# Impôts déductibles du plancher dont une hausse au-dessus du droit en vigueur
# déclenche l'avis (la proposition de loi déduit l'IR, l'IFI, la CSG et les
# autres impôts personnels déjà payés, contrat § 0 point 6) : CSG, tranche
# supérieure de l'IR, fiscalité du patrimoine (IFI) et IR ciblé en Md€ (revue
# adverse de la release E) ; un levier absent du droit en vigueur se compare à
# sa référence (``reference_du_profil`` : neutre, puis défaut du moteur) ;
# ``fiscalite_capital`` se compare à ses neutres (droit voté), lus au registre.
DEDUCTIBLES_AU_DROIT = (('csg', 'taux'), ('impot_revenu', 'taux_superieur'),
                        ('fiscalite_patrimoine', 'intensite'), ('impot_revenu_cible', 'montant'))


def _au_traqueur(traqueur: Dict, cles: Iterable[str]) -> bool:
    """Vrai si l'une des clés ponctuelles du levier a déjà été déclenchée : un
    effet émis peut rester à RENDRE, le handler doit alors calculer même au
    neutre (règle « Retour anticipé » du contrat, § 1.1)."""
    return any(cle in traqueur for cle in cles)


def _nombre_fini(valeur) -> bool:
    return (isinstance(valeur, numbers.Real) and not isinstance(valeur, bool)
            and math.isfinite(valeur))


def _bloc(mesures: Dict, levier: str) -> Dict:
    """Bloc d'un levier dans ``mesures`` ; ``{}`` s'il est absent ou ``null``
    (levier absent, convention de l'orchestrateur)."""
    bloc = mesures.get(levier)
    return bloc if isinstance(bloc, dict) else {}


def intensite_isf_du_programme(mesures: Dict) -> float:
    """Lecture croisée du plancher (règle Z) : intensité de l'ISF du programme,
    0 si le levier est absent, sans intensité ou à ``null`` (défaut de
    ``_apply_isf_climatique`` ; ``null`` = pas de valeur, comme pour la porte
    des paramètres, qui ne retire les ``null`` de ``self.mesures`` qu'en
    tolérant)."""
    intensite = _bloc(mesures, 'isf_climatique').get('intensite')
    return 0.0 if intensite is None else intensite


def taux_is_du_programme(mesures: Dict) -> float:
    """Lecture croisée des bénéfices récupérés (règle M1) : taux d'IS du
    programme (après les portes du moteur), ``TAUX_IS_REFERENCE_BENEFICES`` si
    le levier est absent, sans taux ou à ``null``."""
    taux = _bloc(mesures, 'impot_societes').get('taux')
    return TAUX_IS_REFERENCE_BENEFICES if taux is None else taux


# ---------------------------------------------------------------------------
# Formules du contrat (fonctions PURES : niveaux en entrée, Md€ en sortie)
# ---------------------------------------------------------------------------

def recette_plancher_annee_pleine(p: Dict) -> float:
    """Impôt plancher, recette nette d'année pleine HORS indice d'assiette et
    phasage (§ 1.2-5) : (1 − évitement) × R_REF × (taux / taux du texte) ×
    max(0 ; 1 − intensité de l'ISF × taux max de l'ISF / taux). L'imputation
    de l'ISF retire ce que l'ISF prélève déjà sur le même patrimoine (règle Z) ;
    taux nul → 0 (neutre, aucune division)."""
    taux = p['taux']
    if taux == 0:
        return 0.0
    imputation = max(0.0, 1 - p['intensite_isf'] * ISF_TAUX_MAX / taux)
    return (1 - p['evitement']) * R_REF_PLANCHER * (taux / PLANCHER_TAUX_TEXTE) * imputation


def facteur_capital(p: Dict) -> float:
    """Revenus du capital soumis au prélèvement forfaitaire (assiette
    ``A_CAPITAL_IR`` : dividendes, intérêts, plus-values), part qui demeure au
    taux TOTAL τ = τ_IR + τ_PS (forme et plancher de l'IR, § 1.2-6) :
    max(ETI_PLANCHER_FACTEUR ; 1 + élasticité × ((1 − τ) − (1 − τ_ref)) /
    (1 − τ_ref)), τ_ref = somme des neutres (droit voté). Vaut 1 exactement au
    neutre."""
    neutres = NEUTRES_RELEASE_E['fiscalite_capital']
    tau_ref = neutres['taux_ir_forfaitaire'] + neutres['prelevements_sociaux_capital']
    tau = p['taux_ir_forfaitaire'] + p['prelevements_sociaux_capital']
    return max(ETI_PLANCHER_FACTEUR,
               1 + p['elasticite'] * ((1 - tau) - (1 - tau_ref)) / (1 - tau_ref))


def facteur_capital_social(p: Dict) -> float:
    """Reste de l'assiette sociale (``A_CAPITAL_PS − A_CAPITAL_IR`` : revenus
    fonciers, produits de placement hors prélèvement forfaitaire), part qui
    demeure aux SEULS prélèvements sociaux : f_PS = max(ETI_PLANCHER_FACTEUR ;
    1 + élasticité × (τ_PS⁰ − τ_PS) / (1 − τ_ref)). La part IR du prélèvement
    forfaitaire ne frappe pas ces revenus : ils n'y réagissent pas. Calculé
    comme ``facteur_capital`` à part IR au neutre, donc égal AU BIT à
    ``facteur_capital`` quand seule la part sociale bouge."""
    return facteur_capital({**p, 'taux_ir_forfaitaire':
                            NEUTRES_RELEASE_E['fiscalite_capital']['taux_ir_forfaitaire']})


def variation_capital_hors_indice(p: Dict) -> float:
    """Revenus du capital, ΔR hors indice d'assiette (§ 1.2-6) : en mode
    montant, le rendement annoncé ; en mode taux, recette aux nouveaux taux sur
    l'assiette qui réagit moins recette aux taux de référence, l'assiette
    sociale SCINDÉE (revue adverse de la release E) :

        ΔR = [τ × f(τ) − τ_ref] × A_IR + [τ_PS × f_PS − τ_PS⁰] × (A_PS − A_IR)

    (A_IR, soumise au prélèvement forfaitaire, réagit au taux total ; le reste
    de l'assiette sociale aux seuls prélèvements sociaux). Écrite ci-dessous sous
    une forme algébriquement égale, part IR, prélèvements sociaux sur toute leur
    assiette, puis réaction supplémentaire de A_IR à la part IR :

        ΔR = [τ_IR f − τ_IR⁰] A_IR + [τ_PS f_PS − τ_PS⁰] A_PS + τ_PS (f − f_PS) A_IR

    qui rend AU BIT la formule de l'assiette commune quand seule la part sociale
    bouge (f = f_PS, dernier terme nul). 0 exactement au neutre. Sommet de
    recette de la part IR au défaut : taux total ≈ 53,8 %, dans la fourchette
    publiée (``TAUX_LAFFER_CAPITAL_FOURCHETTE_PCT``, 43-57 %)."""
    if 'rendement_md' in p:
        return p['rendement_md']
    neutres = NEUTRES_RELEASE_E['fiscalite_capital']
    f = facteur_capital(p)
    f_ps = facteur_capital_social(p)
    return ((p['taux_ir_forfaitaire'] * f - neutres['taux_ir_forfaitaire']) * A_CAPITAL_IR
            + (p['prelevements_sociaux_capital'] * f_ps - neutres['prelevements_sociaux_capital']) * A_CAPITAL_PS
            + p['prelevements_sociaux_capital'] * (f - f_ps) * A_CAPITAL_IR)


def benefices_au_taux_is(p: Dict) -> float:
    """Bénéfices récupérés (§ 1.2-7, règle M1) : b × τ_IS / taux de référence,
    constant en euros courants."""
    return p['benefices_recuperes'] * (p['taux_is'] / TAUX_IS_REFERENCE_BENEFICES)


def variation_tsn_hors_indice(p: Dict) -> float:
    """Taxe sur les services numériques, ΔR hors indice (§ 1.2-7) : en mode
    montant, le rendement annoncé ; en mode taux, [τ × max(0 ; 1 − érosion ×
    (τ − τ₀)) − τ₀] × A_TSN, τ₀ = neutre (droit voté). 0 exactement au neutre."""
    if 'rendement_tsn_md' in p:
        return p['rendement_tsn_md']
    t0 = NEUTRES_RELEASE_E['multinationales']['taux_tsn']
    taux = p['taux_tsn']
    return (taux * max(0.0, 1 - p['erosion_tsn'] * (taux - t0)) - t0) * A_TSN


def volume_ttf(taux: float, elasticite: float) -> float:
    """Volume taxable de la TTF (§ 1.2-8) : V_REF × max(0 ; 1 − élasticité ×
    (τ − τ₀) / 0,1 point), τ₀ = neutre (droit voté) ; jamais négatif."""
    t0 = NEUTRES_RELEASE_E['operations_financieres']['taux_ttf']
    return V_REF_TTF * max(0.0, 1 - elasticite * (taux - t0) / TTF_PAS_ELASTICITE_VOLUME)


def variation_ttf_hors_indice(p: Dict) -> float:
    """Taxe sur les transactions financières, ΔR hors indice (§ 1.2-8) : en
    mode montant, le rendement annoncé ; en mode taux, τ × V(τ) − τ₀ × V_REF.
    0 exactement au neutre."""
    if 'rendement_ttf_md' in p:
        return p['rendement_ttf_md']
    t0 = NEUTRES_RELEASE_E['operations_financieres']['taux_ttf']
    return p['taux_ttf'] * volume_ttf(p['taux_ttf'], p['elasticite_volume']) - t0 * V_REF_TTF


# --- Effets ponctuels : constante signée × recette de référence -------------

def _effet_plancher_gini(p: Dict) -> float:
    return GINI_ISF_EFFECTIF_PAR_MD * recette_plancher_annee_pleine(p)


def _effet_plancher_competitivite(p: Dict) -> float:
    return COMPET_ISF_EFFECTIF_PAR_MD * recette_plancher_annee_pleine(p)


def _effet_capital_gini(p: Dict) -> float:
    return GINI_PATRIMOINE_PAR_MD * variation_capital_hors_indice(p)


def _effet_capital_competitivite(p: Dict) -> float:
    return COMPET_PATRIMOINE_PAR_MD * variation_capital_hors_indice(p)


def _effet_multinationales_competitivite(p: Dict) -> float:
    return (COMPET_IS_PAR_MD * benefices_au_taux_is(p)
            + COMPET_IMPOTS_PRODUCTION_PAR_MD * variation_tsn_hors_indice(p))


def _effet_operations_competitivite(p: Dict) -> float:
    return COMPET_IS_EXCEPTIONNEL_PAR_MD * (
        variation_ttf_hors_indice(p) + (p['rachats_actions'] + p['crypto_actifs']))


# --- Avis Z-ter --------------------------------------------------------------

def impots_deductibles_releves(mesures: Dict) -> List[str]:
    """Impôts déductibles du plancher relevés par le programme (règle Z-ter,
    § 4.1) : ``fiscalite_capital`` au-dessus de ses neutres (droit voté) ou
    avec un rendement annoncé positif, un levier de ``DEDUCTIBLES_AU_DROIT``
    au-dessus du droit en vigueur (ou de sa référence s'il en est absent). Une valeur
    non numérique n'est pas une hausse (son levier échoue bruyamment de
    lui-même) ; le droit en vigueur n'est lu que si l'un de ces leviers est
    présent."""
    releves = []
    capital = _bloc(mesures, 'fiscalite_capital')
    if 'rendement_md' in capital:
        if _nombre_fini(capital['rendement_md']) and capital['rendement_md'] > 0:
            releves.append('fiscalite_capital.rendement_md')
    else:
        for cle in ('taux_ir_forfaitaire', 'prelevements_sociaux_capital'):
            if (_nombre_fini(capital.get(cle))
                    and capital[cle] > NEUTRES_RELEASE_E['fiscalite_capital'][cle]):
                releves.append(f'fiscalite_capital.{cle}')
    candidats = [(levier, cle) for levier, cle in DEDUCTIBLES_AU_DROIT
                 if _nombre_fini(_bloc(mesures, levier).get(cle))]
    if candidats:
        droit = charger_droit_en_vigueur().mesures
        for levier, cle in candidats:
            if mesures[levier][cle] > reference_du_profil(levier, cle, droit):
                releves.append(f'{levier}.{cle}')
    return releves


def _noter_avis_z_ter(avis: Optional[Dict], monde: Optional[str]) -> None:
    """Consigne l'avis Z-ter (``report.warnings``, ``report.valid`` inchangé),
    une fois par simulation. Rapport seulement, aucun effet sur le calcul
    (comme le journal des rabots du vivier) ; seuls le monde du programme (mode
    cadre) et le monde unique (mode historique, ``monde`` None) décrivent la
    demande de l'appelant."""
    if avis is None or monde not in (None, 'programme'):
        return
    avis.setdefault(('impot_plancher_patrimoine', 'Z_TER'), AVIS_Z_TER)


class RecettesTauxMixin(_MixinBase):
    """Handlers de la release E — impôts à taux avec comportement (chantier W4)."""

    def _apply_impot_plancher_patrimoine(self, measure: Dict, params: Dict, year: int,
                                         gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Impôt plancher sur les patrimoines de plus de 100 M€ (contrat § 1.2-5).

        Recette = (1 − évitement) × R_REF_PLANCHER × (taux / 2 %) × imputation
        de l'ISF × indice d'assiette (source 2025) × phasage de la collecte de
        l'ISF (0,5 l'année d'entrée, 1 ensuite ; horloge du levier). À
        évitement nul, c'est le rendement statique taux × assiette du texte
        (décision D3) ; l'évitement par défaut est la constante nommée
        ``EVITEMENT_PLANCHER_DEFAUT``, lue au registre comme neutre (jamais un
        littéral ici). Canal ménages : prélèvement direct (comme l'ISF). Gini
        et compétitivité ponctuels : émission EFFECTIVE de l'ISF par Md€
        (``GINI_ISF_EFFECTIF_PAR_MD``, ``COMPET_ISF_EFFECTIF_PAR_MD``,
        négatives) × recette nette d'année pleine, hors indice et phasage.
        L'imputation lit l'intensité de l'ISF du programme (règle Z) ; elle ne
        lit pas l'évasion propre à l'ISF (règle Z4'). Avis Z-ter si un impôt
        déductible est relevé en même temps (aucun calcul).
        """
        taux = params.get('taux', NEUTRES_RELEASE_E['impot_plancher_patrimoine']['taux'])
        evitement = params.get('evitement', NEUTRES_RELEASE_E['impot_plancher_patrimoine']['evitement'])
        if ({'taux': taux, 'evitement': evitement} == NEUTRES_RELEASE_E['impot_plancher_patrimoine']
                and not _au_traqueur(self._measure_params_tracker,
                                     CLES_PONCTUELLES['impot_plancher_patrimoine'])):
            return 0.0, 0.0, {}

        niveau = {'taux': taux, 'evitement': evitement,
                  'intensite_isf': intensite_isf_du_programme(self.mesures)}
        recette_reference = recette_plancher_annee_pleine(niveau)
        phasage = _year_phasing(year - self._origine('impot_plancher_patrimoine'), ISF_PHASAGE)
        delta_revenue = (recette_reference * self._indice_pib_source(ANNEE_SOURCE_PLANCHER, gdp)
                         * phasage)
        impacts = {
            'recettes': delta_revenue,
            'menages': canaux_menages(prelevements_directs=delta_revenue),
            'gini': self._effet_ponctuel('impot_plancher_patrimoine', niveau, _effet_plancher_gini),
            'competitivite': self._effet_ponctuel(
                'impot_plancher_patrimoine_competitivite', niveau, _effet_plancher_competitivite),
        }
        if taux > 0 and impots_deductibles_releves(self.mesures):
            _noter_avis_z_ter(getattr(self, '_avis', None), getattr(self, '_monde_actif', None))

        _log_debug(self.debug_logs,
                   f"Y{year}: Impôt plancher taux {taux:.2%}, évitement {evitement:.1%}, "
                   f"ISF {niveau['intensite_isf']:.2f}, phasage {phasage:.1f} → "
                   f"{delta_revenue:+.2f} Md€")
        return 0.0, delta_revenue, impacts

    def _apply_fiscalite_capital(self, measure: Dict, params: Dict, year: int,
                                 gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Revenus du capital : part IR du prélèvement forfaitaire et
        prélèvements sociaux (contrat § 1.2-6).

        Mode taux : ΔR = {[τ × f(τ) − τ_ref] × A_CAPITAL_IR + [τ_PS × f_PS −
        τ_PS⁰] × (A_CAPITAL_PS − A_CAPITAL_IR)} × indice d'assiette (source
        2025) : l'assiette du prélèvement forfaitaire réagit au taux total τ, le
        reste de l'assiette sociale aux seuls prélèvements sociaux
        (``variation_capital_hors_indice``) ; f, f_PS = forme et plancher de
        l'IR (``ETI_PLANCHER_FACTEUR``) ; neutres = droit voté (registre),
        ΔR = 0 exactement au neutre. L'élasticité (dividendes déclarés et
        versés, mesure micro) est la seule réaction modélisée (D3). Mode montant (``rendement_md``) : rendement net
        annoncé, constant (R-IDX) ; taux et élasticité ignorés. Canal ménages :
        prélèvement direct. Gini et compétitivité ponctuels : règle du levier
        patrimoine par Md€ (arbitrage Q3) × ΔR hors indice. Assiettes
        disjointes de ``impot_revenu.taux_superieur`` ; part sociale additive à
        une variation générale de ``csg.taux`` (règle K) : aucune lecture
        croisée.
        """
        if 'rendement_md' in params:
            # Mode montant (R-MODE) : aucun neutre, le levier calcule toujours.
            niveau = {'rendement_md': params['rendement_md']}
            delta_revenue = variation_capital_hors_indice(niveau)
        else:
            niveau = {
                'taux_ir_forfaitaire': params.get(
                    'taux_ir_forfaitaire', NEUTRES_RELEASE_E['fiscalite_capital']['taux_ir_forfaitaire']),
                'prelevements_sociaux_capital': params.get(
                    'prelevements_sociaux_capital',
                    NEUTRES_RELEASE_E['fiscalite_capital']['prelevements_sociaux_capital']),
                'elasticite': params.get('elasticite', NEUTRES_RELEASE_E['fiscalite_capital']['elasticite']),
            }
            if (niveau == NEUTRES_RELEASE_E['fiscalite_capital']
                    and not _au_traqueur(self._measure_params_tracker,
                                         CLES_PONCTUELLES['fiscalite_capital'])):
                return 0.0, 0.0, {}
            delta_revenue = (variation_capital_hors_indice(niveau)
                             * self._indice_pib_source(ANNEE_SOURCE_CAPITAL, gdp))
        impacts = {
            'recettes': delta_revenue,
            'menages': canaux_menages(prelevements_directs=delta_revenue),
            'gini': self._effet_ponctuel('fiscalite_capital', niveau, _effet_capital_gini),
            'competitivite': self._effet_ponctuel(
                'fiscalite_capital_competitivite', niveau, _effet_capital_competitivite),
        }

        _log_debug(self.debug_logs, f"Y{year}: Revenus du capital {niveau} → {delta_revenue:+.2f} Md€")
        return 0.0, delta_revenue, impacts

    def _apply_multinationales(self, measure: Dict, params: Dict, year: int,
                               gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Multinationales : bénéfices transférés imposés en France et taxe sur
        les services numériques (contrat § 1.2-7).

        Bénéfices récupérés : ΔR₁ = b × τ_IS / 25 % (règle M1), constant
        (R-IDX), τ_IS lu dans le levier ``impot_societes`` du programme (taux
        de référence s'il est absent). TSN, mode taux : ΔR₂ = [τ × max(0 ; 1 −
        érosion × (τ − τ₀)) − τ₀] × A_TSN × indice d'assiette (source 2025) ;
        l'érosion (localisation de la facturation) est la seule réaction
        modélisée (D3). Mode montant (``rendement_tsn_md``) : rendement net
        annoncé, constant ; taux et érosion ignorés. Aucun canal ménages
        (convention des impôts d'entreprise) ; Gini 0 ; compétitivité
        ponctuelle = ``COMPET_IS_PAR_MD`` × ΔR₁ + ``COMPET_IMPOTS_PRODUCTION_PAR_MD``
        × ΔR₂ hors indice. Assiettes disjointes de l'IS et de la surtaxe
        (règle M2) : seule la lecture du taux d'IS les relie.
        """
        benefices_recuperes = params.get('benefices_recuperes',
                                         NEUTRES_RELEASE_E['multinationales']['benefices_recuperes'])
        if 'rendement_tsn_md' in params:
            # Mode montant (R-MODE) : aucun neutre, le levier calcule toujours.
            niveau = {'benefices_recuperes': benefices_recuperes,
                      'taux_is': taux_is_du_programme(self.mesures),
                      'rendement_tsn_md': params['rendement_tsn_md']}
            recette_tsn = variation_tsn_hors_indice(niveau)
        else:
            lus = {
                'benefices_recuperes': benefices_recuperes,
                'taux_tsn': params.get('taux_tsn', NEUTRES_RELEASE_E['multinationales']['taux_tsn']),
                'erosion_tsn': params.get('erosion_tsn', NEUTRES_RELEASE_E['multinationales']['erosion_tsn']),
            }
            if (lus == NEUTRES_RELEASE_E['multinationales']
                    and not _au_traqueur(self._measure_params_tracker,
                                         CLES_PONCTUELLES['multinationales'])):
                return 0.0, 0.0, {}
            niveau = {**lus, 'taux_is': taux_is_du_programme(self.mesures)}
            recette_tsn = (variation_tsn_hors_indice(niveau)
                           * self._indice_pib_source(ANNEE_SOURCE_TSN, gdp))
        delta_revenue = benefices_au_taux_is(niveau) + recette_tsn
        impacts = {
            'recettes': delta_revenue,
            'menages': canaux_menages(),
            'gini': 0.0,
            'competitivite': self._effet_ponctuel(
                'multinationales_competitivite', niveau, _effet_multinationales_competitivite),
        }

        _log_debug(self.debug_logs, f"Y{year}: Multinationales {niveau} → {delta_revenue:+.2f} Md€")
        return 0.0, delta_revenue, impacts

    def _apply_operations_financieres(self, measure: Dict, params: Dict, year: int,
                                      gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Opérations financières : taxe sur les transactions financières, rachats
        d'actions, crypto-actifs (contrat § 1.2-8).

        TTF, mode taux : ΔR₁ = τ × V(τ) − τ₀ × V_REF, × indice d'assiette
        (source 2026, PIB enregistré par le moteur), V(τ) = V_REF × max(0 ; 1 −
        élasticité × (τ − τ₀) / 0,1 point) ; l'élasticité des volumes (titres
        taxés contre non taxés) est la seule réaction modélisée (D3). Mode
        montant (``rendement_ttf_md``) : rendement net annoncé, constant ; taux
        et élasticité ignorés. Rachats d'actions : ÉCART à la taxe de 8 % en
        vigueur (déjà dans la référence, règle F) ; crypto-actifs : recette
        nouvelle ; tous deux constants (R-IDX). Aucun canal ménages ; Gini 0 ;
        compétitivité ponctuelle = ``COMPET_IS_EXCEPTIONNEL_PAR_MD`` × Σ ΔR hors
        indice.
        """
        rachats_actions = params.get('rachats_actions',
                                     NEUTRES_RELEASE_E['operations_financieres']['rachats_actions'])
        crypto_actifs = params.get('crypto_actifs', NEUTRES_RELEASE_E['operations_financieres']['crypto_actifs'])
        if 'rendement_ttf_md' in params:
            # Mode montant (R-MODE) : aucun neutre, le levier calcule toujours.
            niveau = {'rendement_ttf_md': params['rendement_ttf_md'],
                      'rachats_actions': rachats_actions, 'crypto_actifs': crypto_actifs}
            recette_ttf = variation_ttf_hors_indice(niveau)
        else:
            niveau = {
                'taux_ttf': params.get('taux_ttf', NEUTRES_RELEASE_E['operations_financieres']['taux_ttf']),
                'elasticite_volume': params.get(
                    'elasticite_volume', NEUTRES_RELEASE_E['operations_financieres']['elasticite_volume']),
                'rachats_actions': rachats_actions,
                'crypto_actifs': crypto_actifs,
            }
            if (niveau == NEUTRES_RELEASE_E['operations_financieres']
                    and not _au_traqueur(self._measure_params_tracker,
                                         CLES_PONCTUELLES['operations_financieres'])):
                return 0.0, 0.0, {}
            recette_ttf = (variation_ttf_hors_indice(niveau)
                           * self._indice_pib_source(ANNEE_SOURCE_TTF, gdp))
        delta_revenue = recette_ttf + (rachats_actions + crypto_actifs)
        impacts = {
            'recettes': delta_revenue,
            'menages': canaux_menages(),
            'gini': 0.0,
            'competitivite': self._effet_ponctuel(
                'operations_financieres_competitivite', niveau, _effet_operations_competitivite),
        }

        _log_debug(self.debug_logs, f"Y{year}: Opérations financières {niveau} → {delta_revenue:+.2f} Md€")
        return 0.0, delta_revenue, impacts
