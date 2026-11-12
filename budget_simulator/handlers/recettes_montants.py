"""Release E — recettes en Md€, sans paramètre de comportement (4 handlers).

Mesures couvertes (montant identique chaque année en euros courants, règle
R-IDX du contrat) :
- ``droits_succession`` : droits de succession et de donation ;
- ``fiscalite_indirecte`` : TVA à taux réduits et accises sur l'énergie ;
- ``impot_revenu_cible`` : mesure ciblée d'impôt sur le revenu ;
- ``recette_exceptionnelle`` : recette d'une seule année.

Contrat du dépôt parent ``docs/plans/contrat-curseurs-release-E-2026-11.md``,
§ 1.1 (règles communes), § 1.2-4 et § 1.2-9 à 1.2-11 (fiches), § 1.3
(coefficients par Md€). Corps écrits par le chantier W3 ; ce fichier
n'appartient qu'à lui.

Règles communes aux quatre handlers :
- **R-IDX** : la recette de l'année EST le montant écrit par le programme. Le
  résultat ne dépend ni de l'année (citée dans le seul journal de débogage),
  ni du PIB, ni de l'inflation, ni du chômage : un montant en Md€ n'est pas
  revalorisé (même convention que les leviers en Md€ existants, ``defense``
  par exemple).
- **Retour anticipé** (§ 1.1) : toutes les valeurs reçues neutres ET aucune clé
  ponctuelle du levier au traqueur → ``(0.0, 0.0, {})`` avant tout calcul.
  Sinon le handler calcule, y compris au neutre : un levier revenu au neutre
  (profil « une seule année ») rend son effet Gini et compétitivité par
  ``_effet_ponctuel`` (mode incrément), faute de quoi l'effet resterait cumulé
  à vie.
- **Effets ponctuels** (Gini, compétitivité) : ``self._effet_ponctuel`` avec une
  fonction d'effet qui ne lit QUE le dictionnaire de niveaux qu'on lui passe ;
  effet = constante signée du socle × montant, aucun signe ajouté ici (règle
  d'écriture B1, § 1.1). Les fonctions d'effet sont des ``def`` locales (une
  lambda serait lue comme une clé utilisateur par l'extracteur du registre).
- **Aucun effet direct sur l'emploi** (règle v0.6.7, lot 3) : le multiplicateur
  fiscal du moteur porte déjà le canal de la demande ; les quatre leviers
  prennent la classe « recettes » du multiplicateur, comme tout prélèvement.
- **Domaine** : les bornes vivent dans ``policy_measures.json`` et sont
  appliquées par les portes du moteur (``engine/_param_domain.py`` : écrêtage
  tracé dans ``report.leviers_ecretes`` en tolérant, ``ValeurInvalide`` en
  strict) ; le handler ne réécrête rien en silence.

Couplages avec ``BudgetSimulatorV45`` (instance hôte du mixin) :
- lit le traqueur des effets ponctuels ``self._measure_params_tracker`` (retour
  anticipé seulement, sans l'écrire) et appelle ``self._effet_ponctuel`` (base
  class, simulator.py), qui seul le met à jour ;
- n'écrit aucun attribut d'instance.
"""
from typing import TYPE_CHECKING, Dict, Iterable, Tuple

from .._logging import _log_debug
from ..constants import (
    COMPET_PATRIMOINE_PAR_MD,
    COMPET_TVA_PAR_MD,
    GINI_IR_DECOTE_PAR_MD,
    GINI_PATRIMOINE_PAR_MD,
    GINI_TVA_ENERGIE_PAR_MD,
    GINI_TVA_PAR_MD,
    NEUTRES_RELEASE_E,
    PART_CONSOMMATION_MENAGES_TVA_TOTALE,
)
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
    'droits_succession': ('droits_succession', 'droits_succession_competitivite'),
    'fiscalite_indirecte': ('fiscalite_indirecte', 'fiscalite_indirecte_competitivite'),
    'impot_revenu_cible': ('impot_revenu_cible',),
    'recette_exceptionnelle': (),
}


def _effet_ponctuel_au_traqueur(traqueur: Dict, cles: Iterable[str]) -> bool:
    """Vrai si l'une des clés ponctuelles du levier a déjà été déclenchée : un
    effet émis peut rester à RENDRE, le handler doit alors calculer même au
    neutre (règle « Retour anticipé » du contrat, § 1.1)."""
    return any(cle in traqueur for cle in cles)


class RecettesMontantsMixin(_MixinBase):
    """Handlers de la release E — recettes en Md€ (chantier W3)."""

    def _apply_droits_succession(self, measure: Dict, params: Dict, year: int,
                                 gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Droits de succession et de donation, en Md€ par an (contrat § 1.2-4).

        Recette = ``variation`` chaque année (R-IDX), sans paramètre
        d'évitement : le montant est le rendement écrit par le programme.
        Aucun canal ménages : un droit de mutation à titre gratuit est un
        transfert en capital, hors du revenu disponible (convention du levier
        ``fiscalite_patrimoine``). Gini et compétitivité ponctuels : règle du
        levier patrimoine par Md€ (``GINI_PATRIMOINE_PAR_MD``,
        ``COMPET_PATRIMOINE_PAR_MD``, constantes signées négatives : une
        hausse de recette réduit le Gini et la compétitivité). Domaine
        [−DMTG_2025_MD ; DMTG_VARIATION_MAX_MD] : la borne basse est la recette
        2025 sourcée, la borne haute (+25) une décision du mainteneur du
        12/11/2026 ; aucune décote d'évitement (constants.py).
        """
        variation = params.get('variation', NEUTRES_RELEASE_E['droits_succession']['variation'])
        if ({'variation': variation} == NEUTRES_RELEASE_E['droits_succession']
                and not _effet_ponctuel_au_traqueur(self._measure_params_tracker,
                                                    CLES_PONCTUELLES['droits_succession'])):
            return 0.0, 0.0, {}

        delta_revenue = variation
        impacts = {
            'recettes': delta_revenue,
            'menages': canaux_menages(),
        }

        niveau = {'variation': variation}

        def _effet_droits_succession(p):
            return GINI_PATRIMOINE_PAR_MD * p['variation']

        def _effet_droits_succession_competitivite(p):
            return COMPET_PATRIMOINE_PAR_MD * p['variation']

        impacts['gini'] = self._effet_ponctuel(
            'droits_succession', niveau, _effet_droits_succession)
        impacts['competitivite'] = self._effet_ponctuel(
            'droits_succession_competitivite', niveau, _effet_droits_succession_competitivite)

        _log_debug(self.debug_logs,
                   f"Y{year}: Droits de succession et de donation {delta_revenue:+.1f} Md€")
        return 0.0, delta_revenue, impacts

    def _apply_fiscalite_indirecte(self, measure: Dict, params: Dict, year: int,
                                   gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """TVA à taux réduits et accises sur l'énergie, en Md€ par an (contrat
        § 1.2-9).

        Recette = ``tva_ciblee + accises_energie`` chaque année (R-IDX), toutes
        administrations publiques. Canal ménages (prix) : la TVA à 100 %
        (convention de ``tva_rate``), les accises à la part payée par la
        consommation des ménages (``PART_CONSOMMATION_MENAGES_TVA_TOTALE``,
        convention de ``tva_energie`` ; part propre aux accises À SOURCER).
        Passage dans les prix l'année qui suit l'entrée en vigueur du levier
        (horloge du levier) : la part TVA (clé ``recettes_tva``) suit la règle
        de ``tva_rate`` (30 % de la recette en % du PIB, plafonné à 0,2 point,
        hausse seulement). Gini ponctuel : règle de ``tva_rate`` par Md€ pour la TVA, de
        ``tva_energie`` pour les accises (constantes positives : une hausse
        accroît le Gini) ; compétitivité ponctuelle : TVA seule (convention de
        ``tva_energie`` : 0 pour les accises, limite dite au contrat).
        Indépendant de ``tva_rate``, ``tva_energie`` et de la taxe carbone
        (règle I) : aucune lecture croisée.
        """
        tva_ciblee = params.get('tva_ciblee', NEUTRES_RELEASE_E['fiscalite_indirecte']['tva_ciblee'])
        accises_energie = params.get('accises_energie',
                                     NEUTRES_RELEASE_E['fiscalite_indirecte']['accises_energie'])
        if ({'tva_ciblee': tva_ciblee, 'accises_energie': accises_energie}
                == NEUTRES_RELEASE_E['fiscalite_indirecte']
                and not _effet_ponctuel_au_traqueur(self._measure_params_tracker,
                                                    CLES_PONCTUELLES['fiscalite_indirecte'])):
            return 0.0, 0.0, {}

        delta_revenue = tva_ciblee + accises_energie
        impacts = {
            'recettes': delta_revenue,
            # Part TVA de la recette (Md€), lue par le passage dans les prix de
            # l'année suivante (orchestrateur → calculate_inflation), comme la
            # recette de ``tva_rate`` : même canal à recette égale (revue
            # adverse de la release E). Les accises n'y passent pas.
            'recettes_tva': tva_ciblee,
            'menages': canaux_menages(prelevements_indirects=(
                tva_ciblee + PART_CONSOMMATION_MENAGES_TVA_TOTALE * accises_energie)),
        }

        niveau = {'tva_ciblee': tva_ciblee, 'accises_energie': accises_energie}

        def _effet_fiscalite_indirecte(p):
            return GINI_TVA_PAR_MD * p['tva_ciblee'] + GINI_TVA_ENERGIE_PAR_MD * p['accises_energie']

        def _effet_fiscalite_indirecte_competitivite(p):
            return COMPET_TVA_PAR_MD * p['tva_ciblee']

        impacts['gini'] = self._effet_ponctuel(
            'fiscalite_indirecte', niveau, _effet_fiscalite_indirecte)
        impacts['competitivite'] = self._effet_ponctuel(
            'fiscalite_indirecte_competitivite', niveau, _effet_fiscalite_indirecte_competitivite)

        _log_debug(self.debug_logs,
                   f"Y{year}: Fiscalité indirecte ciblée TVA {tva_ciblee:+.1f} Md€, "
                   f"accises {accises_energie:+.1f} Md€")
        return 0.0, delta_revenue, impacts

    def _apply_impot_revenu_cible(self, measure: Dict, params: Dict, year: int,
                                  gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Impôt sur le revenu, mesure ciblée en Md€ par an (contrat § 1.2-10).

        Recette = ``montant`` chaque année (R-IDX) ; canal ménages :
        prélèvement direct du même montant. Gini ponctuel : règle de la décote
        par Md€ (``GINI_IR_DECOTE_PAR_MD``, positive), seule règle IR du moteur
        dont l'incidence porte sur le milieu de la distribution (interprétation
        du contrat) ; compétitivité 0. Indépendant de ``impot_revenu``,
        ``elargissement_ir`` et ``abattement_retraites`` (règle IR).
        """
        montant = params.get('montant', NEUTRES_RELEASE_E['impot_revenu_cible']['montant'])
        if ({'montant': montant} == NEUTRES_RELEASE_E['impot_revenu_cible']
                and not _effet_ponctuel_au_traqueur(self._measure_params_tracker,
                                                    CLES_PONCTUELLES['impot_revenu_cible'])):
            return 0.0, 0.0, {}

        delta_revenue = montant
        impacts = {
            'recettes': delta_revenue,
            'menages': canaux_menages(prelevements_directs=delta_revenue),
        }

        def _effet_impot_revenu_cible(p):
            return GINI_IR_DECOTE_PAR_MD * p['montant']

        impacts['gini'] = self._effet_ponctuel(
            'impot_revenu_cible', {'montant': montant}, _effet_impot_revenu_cible)
        impacts['competitivite'] = 0.0

        _log_debug(self.debug_logs,
                   f"Y{year}: Impôt sur le revenu, mesure ciblée {delta_revenue:+.1f} Md€")
        return 0.0, delta_revenue, impacts

    def _apply_recette_exceptionnelle(self, measure: Dict, params: Dict, year: int,
                                      gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Recette exceptionnelle d'une seule année, en Md€ (contrat § 1.2-11).

        Le handler rend le montant qu'il reçoit, sans lire l'année : c'est le
        cadre temporel qui pose le montant à zéro hors de l'année choisie
        (profil imposé « une seule année », chantier W1). Classe « recettes » du
        multiplicateur fiscal, comme tout prélèvement : la recette freine la
        croissance l'année suivante, puis l'effet s'inverse (effet transitoire
        dit dans l'infobulle). Canaux ménages nuls, Gini 0, compétitivité 0 :
        aucun effet ponctuel, donc aucune clé au traqueur.
        """
        montant = params.get('montant', NEUTRES_RELEASE_E['recette_exceptionnelle']['montant'])
        if ({'montant': montant} == NEUTRES_RELEASE_E['recette_exceptionnelle']
                and not _effet_ponctuel_au_traqueur(self._measure_params_tracker,
                                                    CLES_PONCTUELLES['recette_exceptionnelle'])):
            return 0.0, 0.0, {}

        delta_revenue = montant
        impacts = {
            'recettes': delta_revenue,
            'menages': canaux_menages(),
        }

        _log_debug(self.debug_logs,
                   f"Y{year}: Recette exceptionnelle {delta_revenue:+.1f} Md€")
        return 0.0, delta_revenue, impacts
