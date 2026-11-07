"""Bloc moteur — Cadre temporel (v0.7.0) : année de début des programmes,
droit en vigueur et « mesures de l'année ».

Pourquoi : jusqu'en v0.6.11, ``apply_measures`` recevait CHAQUE année le même
dict ``self.mesures`` ; tout écart au défaut s'appliquait donc dès 2026, un an
avant l'élection et deux ans avant le premier budget du nouvel élu. Le cadre
2027-2032 (arbitrages du mainteneur du 07/11/2026) applique les programmes à
partir de leur ``annee_debut`` (2028 pour les programmes et le simulateur), et
le DROIT EN VIGUEUR avant : le budget 2026 voté, reconduit à droit constant en
2027.

Deux modes, déterminés par ``annee_debut`` (paramètre de la simulation) :

- **historique** — ``annee_debut`` absent ou égal à ``POLICY_START_YEAR``
  (2026) : le programme s'applique dès 2026, au bit près comme en v0.6.11. Le
  droit en vigueur n'est pas même lu : une requête sans ``annee_debut`` ne peut
  pas être dégradée par un fichier de données ;
- **cadre** — ``annee_debut`` ∈ [2027 ; ``ANNEE_DEBUT_MAX``] : avant cette
  année, les mesures de l'année SONT le droit en vigueur ; ensuite, le
  programme, levier par levier par-dessus le droit en vigueur (un levier absent
  du programme, ou ``null``, n'est pas touché par le programme : il garde la
  valeur du droit en vigueur — c'est le sens de « le programme ne dit rien »).

POINT UNIQUE : l'orchestrateur pose ``self.mesures = mesures_de_l_annee(année)``
en TÊTE d'année. ``apply_measures`` et les lecteurs LATÉRAUX de
``self.mesures`` (offre et chômage seniors, effet d'offre, phasing ASU, point
d'indice, réforme FP) lisent donc tous les mêmes mesures. Un interrupteur dans
``apply_measures`` seul aurait laissé l'offre de travail, l'effet d'offre et
l'ASU appliquer le programme dès 2026.

``POLICY_START_YEAR`` n'est PAS déplacé : c'est l'horloge du droit en vigueur
(et du mode historique), lue par les handlers. Le déplacer décalerait aussi le
budget voté.

DROIT EN VIGUEUR = fichier de DONNÉES versionné
(``budget_simulator/data/droit_en_vigueur.json``), remplaçable sans code le jour
où une loi de finances pour 2027 est promulguée. Donnée SERVEUR : un fichier
invalide est un défaut du serveur (``RuntimeError`` → 500 + ERROR côté API),
jamais une faute de l'appelant (422) ni une correction silencieuse. Il doit
passer toutes les portes d'entrée sans AUCUNE correction.

Validation de ``annee_debut`` (entrée de l'appelant) : strict →
``AnneeDebutInvalide`` (``EntreeInvalide`` → 422) ; tolérant → WARNING,
correction tracée (``report.valid = false``) : hors domaine, ramenée à la borne ;
non entière, ignorée (mode historique).
"""
import copy
import functools
import json
import logging
import math
import numbers
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, FrozenSet, Optional

from ..constants import POLICY_START_YEAR
from ._noms_parametres import NOMS_PARAMETRES_ADMIS
from ._param_domain import (
    EntreeInvalide,
    validate_intensite_domain,
    validate_param_domains,
    valider_modes_exclusifs,
    valider_noms_parametres,
)

logger = logging.getLogger(__name__)

# Domaine de ``annee_debut`` : 2026 (mode historique) à la fin du quinquennat
# 2027-2032. Au-delà, un programme n'aurait plus d'année d'application dans la
# fenêtre affichée.
ANNEE_DEBUT_MIN = POLICY_START_YEAR
ANNEE_DEBUT_MAX = 2032

MODE_HISTORIQUE = 'historique'
MODE_CADRE = 'cadre'

DROIT_EN_VIGUEUR_PATH = Path(__file__).resolve().parent.parent / 'data' / 'droit_en_vigueur.json'
_CHAMPS_TEXTE_DROIT = ('identifiant', 'libelle', 'source', 'date')
_DATE_ISO = re.compile(r'^\d{4}-\d{2}-\d{2}$')


class AnneeDebutInvalide(EntreeInvalide, ValueError):
    """``annee_debut`` hors de [2026 ; 2032] ou non entière (mode BUDGETLAB_STRICT)."""


class RampeInvalide(EntreeInvalide, ValueError):
    """``rampe`` mal formée, hors domaine ou en mode historique (mode BUDGETLAB_STRICT)."""


# === RAMPE GÉNÉRIQUE (lot D) ===
# Montée en charge PARAMÉTRIQUE d'un levier, de la valeur du droit en vigueur à
# celle du programme, sur ``annees`` budgets à partir de ``annee_debut`` (dossier
# § 2.4 ; décision du 07/11/2026 : aucune rampe par défaut, la trajectoire
# déclarée par le programme sinon). Paramétrique et non sur les montants : les
# lecteurs latéraux (effet d'offre) lisent la valeur du paramètre.
RAMPE_ANNEES_MIN = 1
RAMPE_ANNEES_MAX = 6
# Leviers en Md€ (budgets, dotations, investissements), et les cinq leviers
# fiscaux des grandes entreprises, éligibles depuis que leurs effets ponctuels
# sont émis en incrément (lot B : rampés, ils ne se redéclenchent plus au
# niveau). Les leviers en taux ou en durée basculent sans rampe.
# ``education.enseignants`` n'y est PAS : il suit la rampe de mandat des
# effectifs FP (handlers/investissements.py), une seconde rampe la doublerait.
RAMPE_LEVIERS_ELIGIBLES = frozenset({
    'transition_ecologique.investissement', 'transition_ecologique.renovation',
    'recherche_publique.budget', 'education.budget', 'defense.budget',
    'collectivites.dotation', 'collectivites.investissement',
    'immigration.ame', 'immigration.integration', 'sante.prevention_budget',
    'niches_fiscales_tge.montant', 'niches_sociales_tge.montant',
    'subventions_tge.montant', 'impots_production.montant', 'is_exceptionnel_tge.montant',
})
_RAMPE_CLES = frozenset({'annees', 'leviers'})


@dataclass(frozen=True)
class Rampe:
    annees: int
    leviers: tuple


def normaliser_rampe(valeur, *, mode_cadre: bool, strict: bool,
                     warned: Optional[set] = None,
                     corrections: Optional[dict] = None) -> Optional['Rampe']:
    """Rampe effective, ou ``None`` (aucune). Strict : ``RampeInvalide`` au
    premier défaut. Tolérant : WARNING une fois et correction tracée —
    ``annees`` ramenée au domaine, leviers inconnus ou non éligibles retirés,
    clés inconnues ignorées, rampe ignorée en mode historique ou si illisible."""
    if valeur is None:
        return None
    cle = ('cadre', 'rampe')

    def defaut(message, rendu):
        if strict:
            raise RampeInvalide(f"rampe : {message} (mode BUDGETLAB_STRICT)")
        _signaler(warned, corrections, f"rampe : {message}", cle=cle + (message,))
        return rendu

    if not mode_cadre:
        return defaut("une rampe exige annee_debut dans [2027 ; "
                      f"{ANNEE_DEBUT_MAX}] (mode historique : programme dès "
                      f"{POLICY_START_YEAR}, sans rampe) — rampe ignorée", None)
    if not isinstance(valeur, dict):
        return defaut(f"objet {{annees, leviers}} attendu, reçu {type(valeur).__name__} — "
                      "rampe ignorée", None)
    inconnues = sorted(map(str, set(valeur) - _RAMPE_CLES))
    if inconnues:
        defaut(f"clé(s) inconnue(s) {', '.join(inconnues)} — ignorée(s)", None)
    annees = valeur.get('annees')
    if isinstance(annees, bool) or not isinstance(annees, numbers.Integral):
        return defaut(f"annees = {annees!r} : entier attendu dans "
                      f"[{RAMPE_ANNEES_MIN} ; {RAMPE_ANNEES_MAX}] — rampe ignorée", None)
    if not RAMPE_ANNEES_MIN <= annees <= RAMPE_ANNEES_MAX:
        borne = min(max(int(annees), RAMPE_ANNEES_MIN), RAMPE_ANNEES_MAX)
        annees = defaut(f"annees = {annees} hors de [{RAMPE_ANNEES_MIN} ; "
                        f"{RAMPE_ANNEES_MAX}] — ramenée à {borne}", borne)
    leviers = valeur.get('leviers')
    if not isinstance(leviers, list):
        return defaut(f"leviers = {leviers!r} : liste de « levier.parametre » attendue — "
                      "rampe ignorée", None)
    retenus = []
    for nom in leviers:
        if nom == 'education.enseignants':
            defaut("education.enseignants suit déjà la rampe de mandat des effectifs "
                   "de la fonction publique — retiré de la rampe", None)
        elif not isinstance(nom, str) or nom not in RAMPE_LEVIERS_ELIGIBLES:
            defaut(f"levier {nom!r} inconnu ou non éligible (leviers en Md€ et leviers "
                   f"fiscaux des grandes entreprises : {', '.join(sorted(RAMPE_LEVIERS_ELIGIBLES))})"
                   " — retiré", None)
        elif nom not in retenus:
            retenus.append(nom)
    return Rampe(annees=int(annees), leviers=tuple(retenus)) if retenus else None


@dataclass(frozen=True)
class DroitEnVigueur:
    """Jeu de paramètres appliqué avant ``annee_debut`` (donnée serveur validée)."""
    identifiant: str
    libelle: str
    source: str
    date: str
    mesures: Dict

    def meta(self) -> Dict:
        return {'identifiant': self.identifiant, 'libelle': self.libelle,
                'source': self.source, 'date': self.date}


def _defaut_serveur(message: str) -> RuntimeError:
    return RuntimeError(f"Droit en vigueur invalide ({DROIT_EN_VIGUEUR_PATH.name}) — défaut "
                        f"du serveur, pas de l'appelant : {message}")


def _verifier_finis(chemin: str, valeur) -> None:
    if isinstance(valeur, dict):
        for k, v in valeur.items():
            _verifier_finis(f"{chemin}.{k}", v)
    elif isinstance(valeur, float) and not math.isfinite(valeur):
        raise _defaut_serveur(f"{chemin} = {valeur!r} : valeur non finie")


def valider_mesures_serveur(mesures, origine: str) -> None:
    """Un jeu de mesures livré par le SERVEUR (droit en vigueur, réajustements de
    l'atterrissage) passe toutes les portes d'entrée sans aucune correction :
    leviers connus, blocs explicites (ni ``null`` ni vides), noms lus par le
    levier, valeurs finies dans leur domaine, pas de mode exclusif masqué.
    ``RuntimeError`` au premier défaut."""
    if not isinstance(mesures, dict):
        raise _defaut_serveur(f"{origine} : dict de leviers attendu, reçu {type(mesures).__name__}")
    for levier, bloc in mesures.items():
        if levier not in NOMS_PARAMETRES_ADMIS:
            raise _defaut_serveur(f"{origine} : levier inconnu {levier!r}")
        if not isinstance(bloc, dict) or not bloc:
            raise _defaut_serveur(f"{origine} : {levier} doit être un bloc de paramètres "
                                  f"explicite (reçu {bloc!r})")
        _verifier_finis(f"{origine}.{levier}", bloc)
        try:
            valider_noms_parametres(levier, bloc, strict=True)
            if validate_intensite_domain(levier, bloc, strict=True) is not bloc:
                raise ValueError("valeur corrigée par la porte d'intensité")
            if validate_param_domains(levier, bloc, strict=True) is not bloc:
                raise ValueError("valeur corrigée par la porte des domaines")
            valider_modes_exclusifs(levier, bloc, strict=True)
        except (EntreeInvalide, ValueError, TypeError) as e:
            raise _defaut_serveur(f"{origine} : {levier} : {e}") from e


@functools.lru_cache(maxsize=1)
def charger_droit_en_vigueur() -> DroitEnVigueur:
    """Lit et valide le droit en vigueur (cache : une lecture par processus ;
    ``cache_clear()`` en test). ``RuntimeError`` si le fichier est absent,
    illisible ou invalide."""
    try:
        contenu = json.loads(DROIT_EN_VIGUEUR_PATH.read_text(encoding='utf-8'))
    except FileNotFoundError as e:
        raise _defaut_serveur("fichier introuvable") from e
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise _defaut_serveur(f"JSON illisible : {e}") from e
    if not isinstance(contenu, dict):
        raise _defaut_serveur("objet JSON attendu")
    for champ in _CHAMPS_TEXTE_DROIT:
        valeur = contenu.get(champ)
        if not isinstance(valeur, str) or not valeur.strip():
            raise _defaut_serveur(f"champ {champ!r} manquant ou vide")
    if not _DATE_ISO.match(contenu['date']):
        raise _defaut_serveur(f"date {contenu['date']!r} : format AAAA-MM-JJ attendu")
    mesures = contenu.get('mesures')
    if not isinstance(mesures, dict) or not mesures:
        raise _defaut_serveur("champ 'mesures' : dict de leviers non vide attendu")
    valider_mesures_serveur(mesures, 'mesures')
    valider_droit_composable(mesures, 'mesures')
    return DroitEnVigueur(**{c: contenu[c] for c in _CHAMPS_TEXTE_DROIT}, mesures=mesures)


# Canaux lus HORS des handlers, par des lecteurs latéraux qui n'ont pas de
# composition à trois termes (lot C) : offre et chômage seniors (âge de départ),
# effet d'offre structurel (dépenses productives, compteur de délai propre),
# passage de la TVA dans les prix (porte d'un an après l'entrée en vigueur).
# Tant que le droit en vigueur reste au défaut du moteur sur ces canaux, la part
# héritée y est nulle et la lecture sur l'horloge du programme est EXACTE. Un
# droit en vigueur qui s'en écarte exige d'abord d'implémenter la composition
# pour ces lecteurs : le chargement échoue (RuntimeError), il ne compose pas
# faux en silence. Valeurs : défauts du moteur (config.load_default_values).
CANAUX_LATERAUX_HORS_HANDLERS = {
    'retraites': ('age_depart',),
    'education': ('budget',),
    'recherche_publique': ('budget',),
    'transition_ecologique': ('investissement', 'renovation'),
    'tva_rate': ('taux',),
}


def valider_droit_composable(mesures: Dict, origine: str) -> None:
    """RuntimeError si le jeu de mesures serveur s'écarte du défaut sur un canal
    latéral non composé (cf. ``CANAUX_LATERAUX_HORS_HANDLERS``). ``age_depart``
    doit être ABSENT : le statu quo de l'âge est le calendrier légal, qu'aucun
    scalaire ne décrit (``config.load_default_values``)."""
    from ..config import load_default_values
    defauts = load_default_values()
    for levier, cles in CANAUX_LATERAUX_HORS_HANDLERS.items():
        bloc = mesures.get(levier)
        if not isinstance(bloc, dict):
            continue
        for cle in cles:
            if cle not in bloc:
                continue
            defaut = defauts.get(levier, {}).get(cle)
            if defaut is None or bloc[cle] != defaut:
                raise _defaut_serveur(
                    f"{origine} : {levier}.{cle} = {bloc[cle]!r} s'écarte du défaut du "
                    f"moteur ({'absent' if defaut is None else defaut!r}) sur un canal lu hors "
                    f"des handlers (composition des horloges non implémentée pour ce "
                    f"lecteur — engine/cadre.py, CANAUX_LATERAUX_HORS_HANDLERS)")


def normaliser_annee_debut(valeur, *, strict: bool, warned: Optional[set] = None,
                           corrections: Optional[dict] = None) -> Optional[int]:
    """``annee_debut`` effective, ou ``None`` (mode historique).

    Strict : ``AnneeDebutInvalide`` si non entière (booléen compris) ou hors de
    [``ANNEE_DEBUT_MIN`` ; ``ANNEE_DEBUT_MAX``]. Tolérant : WARNING une fois par
    simulation et correction tracée — hors domaine, ramenée à la borne ; non
    entière, ignorée (mode historique)."""
    if valeur is None:
        return None
    domaine = f"[{ANNEE_DEBUT_MIN} ; {ANNEE_DEBUT_MAX}]"
    if isinstance(valeur, bool) or not isinstance(valeur, numbers.Integral):
        message = (f"annee_debut = {valeur!r} : année entière attendue dans {domaine}")
        if strict:
            raise AnneeDebutInvalide(message + " (mode BUDGETLAB_STRICT)")
        _signaler(warned, corrections, message + " — ignorée, programme appliqué dès "
                  f"{ANNEE_DEBUT_MIN} (mode historique)")
        return None
    if not ANNEE_DEBUT_MIN <= valeur <= ANNEE_DEBUT_MAX:
        borne = min(max(int(valeur), ANNEE_DEBUT_MIN), ANNEE_DEBUT_MAX)
        message = f"annee_debut = {valeur} hors de {domaine}"
        if strict:
            raise AnneeDebutInvalide(message + " (mode BUDGETLAB_STRICT)")
        _signaler(warned, corrections, message + f" — ramenée à {borne}")
        return borne
    return int(valeur)


def _signaler(warned: Optional[set], corrections: Optional[dict], texte: str,
              cle: tuple = ('cadre', 'annee_debut')) -> None:
    if warned is None or cle not in warned:
        logger.warning("CADRE %s", texte)
        if warned is not None:
            warned.add(cle)
    if corrections is not None:
        corrections.setdefault(cle, texte)


def fusionner(droit: Dict, programme: Dict) -> Dict:
    """Mesures d'une année de programme : le droit en vigueur, dont chaque levier
    présent (non ``null``) dans le programme est REMPLACÉ en bloc par celui du
    programme. Remplacement en bloc, pas fusion de paramètres : un mélange
    paramètre par paramètre pourrait créer un mode exclusif masqué
    (``taux`` du droit + ``intensite`` du programme) que personne n'a écrit."""
    effectif = dict(droit)
    for levier, bloc in programme.items():
        if bloc is not None:
            effectif[levier] = bloc
    return effectif


@dataclass
class CadreTemporel:
    """Cadre d'UNE simulation : mode, année de début, droit en vigueur et
    programme effectif. ``mesures_de_l_annee`` est le point unique lu par
    l'orchestrateur en tête d'année."""
    mode: str
    annee_debut: int
    droit: Optional[DroitEnVigueur]
    mesures_droit: Optional[Dict]
    programme: Dict
    leviers_modifies: FrozenSet[str]
    rampe: Optional[Rampe] = None
    leviers_rampes: tuple = ()
    mesures_rampe: Optional[Dict[int, Dict]] = None

    @classmethod
    def preparer(cls, programme: Dict, annee_debut, *, droit: Optional[DroitEnVigueur] = None,
                 rampe=None, strict: bool = False, warned: Optional[set] = None,
                 corrections: Optional[dict] = None) -> 'CadreTemporel':
        """``programme`` : mesures de l'appelant APRÈS la porte d'entrée
        (``assainir_mesures``). ``droit`` : injecté en test, sinon le fichier.
        ``rampe`` : demande de l'appelant (lot D), validée ici."""
        debut = normaliser_annee_debut(annee_debut, strict=strict, warned=warned,
                                       corrections=corrections)
        historique = debut is None or debut == POLICY_START_YEAR
        rampe_effective = normaliser_rampe(rampe, mode_cadre=not historique, strict=strict,
                                           warned=warned, corrections=corrections)
        if historique:
            return cls(mode=MODE_HISTORIQUE, annee_debut=POLICY_START_YEAR, droit=None,
                       mesures_droit=None, programme=programme,
                       leviers_modifies=frozenset())
        droit = droit if droit is not None else charger_droit_en_vigueur()
        # Copie PAR SIMULATION : le droit chargé est partagé par le cache du
        # processus ; aucune simulation ne doit pouvoir l'altérer pour la suivante.
        mesures_droit = copy.deepcopy(droit.mesures)
        effectif = fusionner(mesures_droit, programme)
        modifies = frozenset(l for l in set(effectif) | set(mesures_droit)
                             if effectif.get(l) != mesures_droit.get(l))
        rampes, par_annee = _mesures_rampees(effectif, mesures_droit, debut, rampe_effective)
        return cls(mode=MODE_CADRE, annee_debut=debut, droit=droit,
                   mesures_droit=mesures_droit, programme=effectif,
                   leviers_modifies=modifies, rampe=rampe_effective,
                   leviers_rampes=rampes, mesures_rampe=par_annee)

    @property
    def actif(self) -> bool:
        return self.mode == MODE_CADRE

    def mesures_de_l_annee(self, annee: int) -> Dict:
        """Droit en vigueur avant ``annee_debut``, programme ensuite. Mode
        historique : le programme, toujours (le même objet : bit-identique)."""
        if self.actif and annee < self.annee_debut:
            return self.mesures_droit
        if self.mesures_rampe and annee in self.mesures_rampe:
            return self.mesures_rampe[annee]
        return self.programme

    def origines_de_l_annee(self, annee: int) -> Dict[str, int]:
        """Origine d'horloge de chaque levier MODIFIÉ par le programme, à partir
        du début (lot C) ; ``{}`` avant (et en mode historique) : tous les
        leviers comptent alors depuis ``POLICY_START_YEAR``. Lue par
        ``BudgetSimulatorV45._origine(levier)``."""
        if not self.actif or annee < self.annee_debut:
            return {}
        return {levier: self.annee_debut for levier in self.leviers_modifies}

    def compose(self, annee: int) -> bool:
        """Vrai si l'année exige la composition à trois mondes : mode cadre, à
        partir du début, programme différent du droit en vigueur."""
        return self.actif and annee >= self.annee_debut and bool(self.leviers_modifies)

    def rapport(self) -> Dict:
        """Bloc ``cadre`` de la réponse."""
        return {
            'mode': self.mode,
            'annee_debut': self.annee_debut,
            'annees_droit_en_vigueur': (list(range(POLICY_START_YEAR, self.annee_debut))
                                        if self.actif else []),
            'droit_en_vigueur': self.droit.meta() if self.droit is not None else None,
            'leviers_modifies': sorted(self.leviers_modifies),
            'rampe': (None if self.rampe is None else
                      {'annees': self.rampe.annees, 'leviers': list(self.rampe.leviers),
                       'leviers_rampes': list(self.leviers_rampes)}),
        }


def _mesures_rampees(programme: Dict, droit: Dict, debut: int, rampe: Optional[Rampe]):
    """(leviers effectivement rampés, {année: mesures}) pour les années de rampe
    non pleines (début … début + n − 2) ; ensuite, le programme lui-même (valeur
    EXACTE du programme, jamais p_droit + (p − p_droit) × 1). Référence d'un
    levier absent du droit : le défaut du moteur."""
    if rampe is None or rampe.annees == 1:
        return (), None
    from ..config import load_default_values
    defauts = load_default_values()
    a_ramper = []
    for nom in rampe.leviers:
        levier, param = nom.split('.')
        bloc = programme.get(levier)
        if not isinstance(bloc, dict) or param not in bloc:
            continue
        ref_bloc = droit.get(levier) if isinstance(droit.get(levier), dict) else {}
        p_ref = ref_bloc.get(param, defauts.get(levier, {}).get(param))
        p_prog = bloc[param]
        if _nombre(p_ref) and _nombre(p_prog) and p_prog != p_ref:
            a_ramper.append((nom, levier, param, p_ref, p_prog))
    if not a_ramper:
        return (), None
    par_annee = {}
    for k in range(1, rampe.annees):
        m = dict(programme)
        for _, levier, param, p_ref, p_prog in a_ramper:
            bloc = dict(m[levier])
            bloc[param] = p_ref + (p_prog - p_ref) * k / rampe.annees
            m[levier] = bloc
        par_annee[debut + k - 1] = m
    return tuple(nom for nom, *_ in a_ramper), par_annee


# ---------------------------------------------------------------------------
# Composition des horloges (lot C) : trois mondes d'évaluation des handlers
# ---------------------------------------------------------------------------

@dataclass
class Monde:
    """Un monde d'évaluation des handlers : les mesures que lisent leurs
    lectures croisées (``self.mesures``), les origines d'horloge, et l'état
    PROPRE des déclencheurs ponctuels (traqueur, assurance chômage). Le monde
    ``droit_2026`` n'a pas d'état propre : c'est celui du moteur, continu depuis
    2026 (``principal``)."""
    nom: str
    mesures: Dict
    origines: Dict[str, int]
    principal: bool = False
    traqueur: Optional[Dict] = None
    chomage_prev: Optional[Dict] = None


def creer_mondes(cadre_temporel: 'CadreTemporel') -> Dict[str, Monde]:
    """Les trois mondes d'une simulation en mode cadre. ``programme`` et
    ``droit_debut`` démarrent vides au début du programme ; leurs origines et
    leurs mesures sont posées chaque année par l'orchestrateur."""
    droit = cadre_temporel.mesures_droit
    return {
        'droit_2026': Monde('droit_2026', droit, {}, principal=True),
        'programme': Monde('programme', cadre_temporel.programme, {}, traqueur={}),
        'droit_debut': Monde('droit_debut', droit, {}, traqueur={}),
    }


def _nombre(v) -> bool:
    return isinstance(v, numbers.Real) and not isinstance(v, bool)


def combiner_impacts(a: Dict, b: Dict, c: Dict) -> Dict:
    """``a + (b − c)`` clé par clé (récursif sur les sous-dicts) : la part
    héritée ``a`` (droit, horloge 2026) plus l'incrément du programme ``b − c``
    (programme et droit sur l'horloge du début). Écrit ``a + (b − c)`` et non
    ``a + b − c`` : quand ``b`` et ``c`` sont identiques au bit (levier égal au
    droit, sans lecture croisée d'un levier modifié), l'incrément vaut 0,0
    exactement et le résultat EST ``a``. Valeur non numérique : celle du
    programme, à défaut celle du droit."""
    out = {}
    for cle in list(a) + [k for k in b if k not in a] + [k for k in c if k not in a and k not in b]:
        va, vb, vc = a.get(cle), b.get(cle), c.get(cle)
        if any(isinstance(v, dict) for v in (va, vb, vc)):
            out[cle] = combiner_impacts(va if isinstance(va, dict) else {},
                                        vb if isinstance(vb, dict) else {},
                                        vc if isinstance(vc, dict) else {})
        elif all(v is None or _nombre(v) for v in (va, vb, vc)):
            increment = (0.0 if vb is None else vb) - (0.0 if vc is None else vc)
            out[cle] = increment if va is None else va + increment
        else:
            out[cle] = vb if cle in b else va
    return out


def combiner(sortie_a, sortie_b, sortie_c):
    """Sorties ``(Δdép, Δrec, impacts)`` des trois mondes → sortie composée."""
    (da, ra, ia), (db, rb, ib), (dc, rc, ic) = sortie_a, sortie_b, sortie_c
    return da + (db - dc), ra + (rb - rc), combiner_impacts(ia, ib, ic)
