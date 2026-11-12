"""Release E — prestations versées aux ménages, en montant (1 handler).

Mesure couverte :
- ``prestations_menages`` : prestations de solidarité (minima sociaux, aides
  au logement, prestations familiales) et pensions de retraite, en Md€ par an,
  montant identique chaque année en euros courants (règle R-IDX du contrat).

Contrat du dépôt parent ``docs/plans/contrat-curseurs-release-E-2026-11.md``,
§ 1.1 (R-IDX, retour anticipé, effets ponctuels, règle d'écriture des
coefficients), § 1.2-2 (fiche du levier), § 1.3 (coefficients), § 4.1 (règles
P et R). Chantier W2 ; ce fichier n'appartient qu'à lui.

Calcul, chaque année d'application :
- dépense : ``Δdép = solidarite + pensions``, CONSTANTE en euros courants
  (aucune indexation : le handler ne lit ni l'année, ni le PIB, ni l'inflation,
  ni le chômage qu'il reçoit) ;
- canal ménages : ``prestations = Δdép`` (une hausse est un revenu versé aux
  ménages, une baisse un revenu retiré) ;
- Gini, effet PONCTUEL en incrément (``_effet_ponctuel``, clé
  ``prestations_menages``) : ``GINI_SOLIDARITE_PAR_MD × solidarite +
  GINI_PENSIONS_PAR_MD × pensions``, constantes SIGNÉES du socle (effet d'un
  +1 Md€ versé : négatif, une hausse réduit les inégalités) — le handler
  n'ajoute aucun signe ;
- compétitivité nulle ; aucun effet direct sur le chômage (l'effet de demande
  passe par le multiplicateur des transferts : le socle a inscrit le levier
  dans ``BudgetSimulatorV45.TRANSFER_MEASURES``).

Ce que le handler ne fait PAS (règles P et R, décision D9) : il ne lit ni
n'écrit les masses de dépense (``minima_sociaux``, ``retraites``), ni les
autres leviers ; il n'est donc pas neutralisé par l'allocation sociale unique,
et les leviers d'indexation, du SMIC, de l'assurance chômage et des retraites
restent indépendants de lui (montants additifs). Le domaine de chaque
paramètre est appliqué AVANT le handler par la porte des valeurs de
l'orchestrateur (``validate_param_domains`` : écrêtage tracé en tolérant,
``EntreeInvalide`` en strict, valeurs non finies retirées).

Couplages avec ``BudgetSimulatorV45`` (instance hôte du mixin) :
- LIT ``self._measure_params_tracker`` (traqueur des effets ponctuels), pour
  le seul retour anticipé du § 1.1 : au neutre, sans effet ponctuel en cours,
  rien n'est calculé ni enregistré (neutralité au bit) ;
- APPELLE ``self._effet_ponctuel`` (qui met ce traqueur à jour).
Aucune autre lecture ni écriture d'attribut d'instance.
"""
from typing import TYPE_CHECKING, Dict, Tuple

from ..constants import GINI_PENSIONS_PAR_MD, GINI_SOLIDARITE_PAR_MD, NEUTRES_RELEASE_E
from ._types import ImpactsDict, canaux_menages


# Idiome mixin-self typing : NE PAS factoriser dans _types.py (casse la
# liaison self mypy + risque MRO). Réplication volontaire. Cf Lot D.
if TYPE_CHECKING:
    from ._types import _SimulatorState

    _MixinBase = _SimulatorState
else:
    _MixinBase = object


# Clé du levier dans le traqueur des effets ponctuels (une seule : le levier
# n'a qu'un effet ponctuel, le Gini).
_CLE_PONCTUELLE = 'prestations_menages'


class PrestationsMenagesMixin(_MixinBase):
    """Handler de la release E — prestations versées aux ménages (chantier W2)."""

    def _apply_prestations_menages(self, measure: Dict, params: Dict, year: int,
                                   gdp: float, inflation: float, unemployment: float) -> Tuple[float, float, ImpactsDict]:
        """Prestations versées aux ménages, en Md€ par an (+ = dépense en plus).

        Paramètres (domaine du registre, appliqué par la porte des valeurs) :
        - ``solidarite`` : minima sociaux, aides au logement, prestations
          familiales ;
        - ``pensions`` : pensions de retraite, en montant (hors âge, durée et
          indexation, qui ont leur levier ``retraites``).

        Retour anticipé (§ 1.1) : valeurs neutres ET aucun effet ponctuel en
        cours → ``(0.0, 0.0, {})``. Un levier revenu au neutre après une valeur
        non neutre (profil « une seule année ») calcule encore, pour RENDRE son
        effet Gini (incrément opposé) : sans cela, l'effet resterait cumulé à
        vie."""
        # Défauts écrits comme au socle : le registre public (généré) publie
        # l'expression du défaut telle quelle.
        solidarite = params.get('solidarite', NEUTRES_RELEASE_E['prestations_menages']['solidarite'])
        pensions = params.get('pensions', NEUTRES_RELEASE_E['prestations_menages']['pensions'])
        niveau = {'solidarite': solidarite, 'pensions': pensions}
        if (niveau == NEUTRES_RELEASE_E['prestations_menages']
                and _CLE_PONCTUELLE not in self._measure_params_tracker):
            return 0.0, 0.0, {}

        # R-IDX : montant constant en euros courants, aucune indexation.
        delta_depenses = float(solidarite) + float(pensions)

        # Effet ponctuel en INCRÉMENT : ``effet`` ne lit QUE son dictionnaire
        # (le cumul ne dépend que du niveau atteint, jamais du chemin) ; une
        # fonction ``def`` et non une fonction anonyme (l'extracteur des noms
        # admis lit les paramètres d'une fonction anonyme comme des clés
        # utilisateur).
        def _effet_prestations_menages(p):
            return GINI_SOLIDARITE_PAR_MD * p['solidarite'] + GINI_PENSIONS_PAR_MD * p['pensions']

        gini = self._effet_ponctuel(_CLE_PONCTUELLE, niveau, _effet_prestations_menages)

        impacts = {
            'depenses': delta_depenses,
            'gini': gini,
            'competitivite': 0.0,
            'menages': canaux_menages(prestations=delta_depenses),
        }
        return delta_depenses, 0.0, impacts
