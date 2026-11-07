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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, FrozenSet, Literal, Optional, Tuple, get_args

from ..constants import (
    CHOMAGE_CLIP_MAX,
    CHOMAGE_CLIP_MIN,
    CONJONCTURE_AMPLITUDE_MAX,
    CONJONCTURE_DERNIERE_ANNEE,
    CONJONCTURE_PREMIERE_ANNEE,
    PLAFOND_IMPACT_TOTAL_PIB,
    POLICY_START_YEAR,
)
from ._noms_parametres import MODES_EXCLUSIFS, NOMS_PARAMETRES_ADMIS
from ._param_domain import (
    _DETAILS_MAX,
    EntreeInvalide,
    _apercu,
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
    leviers: Tuple[str, ...]


def normaliser_rampe(valeur, *, mode_cadre: bool, strict: bool,
                     warned: Optional[set] = None,
                     corrections: Optional[dict] = None) -> Optional['Rampe']:
    """Rampe effective, ou ``None`` (aucune). Strict : ``RampeInvalide`` au
    premier défaut. Tolérant : WARNING une fois et correction tracée —
    ``annees`` ramenée au domaine, leviers inconnus ou non éligibles retirés,
    clés inconnues ignorées, rampe ignorée en mode historique ou si illisible.

    TAILLE BORNÉE (revue de sécurité, amplification de ressources ; parité avec
    ``_param_domain``) : au plus une entrée par levier éligible
    (``RAMPE_LEVIERS_ELIGIBLES``), sinon rejet sans parcourir la liste ; noms
    dédoublonnés ; les noms retirés font UN avertissement à clé fixe, au plus
    ``_DETAILS_MAX`` noms détaillés et chacun tronqué ; la liste des leviers
    éligibles n'y est jamais répétée (elle vit ici et dans METHODOLOGIE)."""
    if valeur is None:
        return None
    cle = ('cadre', 'rampe')

    def defaut(message, rendu, sous_cle):
        if strict:
            raise RampeInvalide(f"rampe : {message} (mode BUDGETLAB_STRICT)")
        _signaler(warned, corrections, f"rampe : {message}", cle=cle + (sous_cle,))
        return rendu

    if not mode_cadre:
        return defaut("une rampe exige annee_debut dans [2027 ; "
                      f"{ANNEE_DEBUT_MAX}] (mode historique : programme dès "
                      f"{POLICY_START_YEAR}, sans rampe) — rampe ignorée", None, 'mode')
    if not isinstance(valeur, dict):
        return defaut(f"objet {{annees, leviers}} attendu, reçu {type(valeur).__name__} — "
                      "rampe ignorée", None, 'forme')
    inconnues = sorted(_apercu(k) for k in set(valeur) - _RAMPE_CLES)
    if inconnues:
        defaut(f"clé(s) inconnue(s) {_resume(inconnues)} — ignorée(s)", None, 'cles')
    annees = valeur.get('annees')
    if isinstance(annees, bool) or not isinstance(annees, numbers.Integral):
        return defaut(f"annees = {_apercu(annees)} : entier attendu dans "
                      f"[{RAMPE_ANNEES_MIN} ; {RAMPE_ANNEES_MAX}] — rampe ignorée", None, 'annees')
    annees = int(annees)
    if not RAMPE_ANNEES_MIN <= annees <= RAMPE_ANNEES_MAX:
        borne = min(max(annees, RAMPE_ANNEES_MIN), RAMPE_ANNEES_MAX)
        annees = defaut(f"annees = {_apercu(annees)} hors de [{RAMPE_ANNEES_MIN} ; "
                        f"{RAMPE_ANNEES_MAX}] — ramenée à {borne}", borne, 'annees')
    leviers = valeur.get('leviers')
    if not isinstance(leviers, list):
        return defaut(f"leviers = {_apercu(leviers)} : liste de « levier.parametre » attendue — "
                      "rampe ignorée", None, 'leviers')
    n_max = len(RAMPE_LEVIERS_ELIGIBLES)
    if len(leviers) > n_max:
        return defaut(f"leviers : {len(leviers)} entrées pour {n_max} leviers éligibles au plus "
                      f"(engine/cadre.py, RAMPE_LEVIERS_ELIGIBLES) — rampe ignorée", None, 'leviers')
    retenus, retires = [], []
    for nom in leviers:
        if isinstance(nom, str) and nom in RAMPE_LEVIERS_ELIGIBLES:
            if nom not in retenus:
                retenus.append(nom)
        elif nom == 'education.enseignants':
            defaut("education.enseignants suit déjà la rampe de mandat des effectifs "
                   "de la fonction publique — retiré de la rampe", None, 'enseignants')
        else:
            retires.append(_apercu(nom))
    if retires:
        defaut(f"levier(s) inconnu(s) ou non éligible(s) {_resume(sorted(set(retires)))} — "
               "retiré(s) (éligibles : engine/cadre.py, RAMPE_LEVIERS_ELIGIBLES)", None, 'retires')
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


def charger_droit_en_vigueur() -> DroitEnVigueur:
    """Droit en vigueur validé, en COPIE PROFONDE à chaque appel : le cache du
    processus (une lecture, ``vider_caches()`` en test) ne peut pas être altéré
    par un appelant pour la simulation suivante. ``RuntimeError`` si le fichier
    est absent, illisible ou invalide."""
    return copy.deepcopy(_droit_en_vigueur_valide())


def vider_caches() -> None:
    """Vide les caches des deux fichiers de données serveur (tests ; un
    remplacement à chaud du fichier en production passe par un redémarrage)."""
    _droit_en_vigueur_valide.cache_clear()
    _atterrissage_valide.cache_clear()


@functools.lru_cache(maxsize=1)
def _droit_en_vigueur_valide() -> DroitEnVigueur:
    try:
        contenu = json.loads(DROIT_EN_VIGUEUR_PATH.read_text(encoding='utf-8'))
    except FileNotFoundError as e:
        raise _defaut_serveur("fichier introuvable") from e
    except OSError as e:
        raise _defaut_serveur(f"lecture impossible ({e})") from e
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
    valeur = int(valeur)
    if not ANNEE_DEBUT_MIN <= valeur <= ANNEE_DEBUT_MAX:
        borne = min(max(valeur, ANNEE_DEBUT_MIN), ANNEE_DEBUT_MAX)
        message = f"annee_debut = {valeur} hors de {domaine}"
        if strict:
            raise AnneeDebutInvalide(message + " (mode BUDGETLAB_STRICT)")
        _signaler(warned, corrections, message + f" — ramenée à {borne}")
        return borne
    return valeur


def _resume(noms: list) -> str:
    """Au plus ``_DETAILS_MAX`` noms, puis « (+N autres) » : un message borné."""
    texte = ', '.join(noms[:_DETAILS_MAX])
    return texte + (f" (+{len(noms) - _DETAILS_MAX} autres)" if len(noms) > _DETAILS_MAX else '')


def _signaler(warned: Optional[set], corrections: Optional[dict], texte: str,
              cle: tuple = ('cadre', 'annee_debut')) -> None:
    if warned is None or cle not in warned:
        logger.warning("CADRE %s", texte)
        if warned is not None:
            warned.add(cle)
    if corrections is not None:
        corrections.setdefault(cle, texte)


def heriter_du_droit(programme: Dict, droit_vote: Dict, droit_en_vigueur: Dict) -> Dict:
    """Mesures du programme par-dessus le droit en vigueur, réajustements de
    l'atterrissage compris (lot E).

    Un levier absent ou ``null``, ou dont le programme reprend le bloc VOTÉ, est
    celui du droit en vigueur. Un levier que le programme modifie est COMPLÉTÉ
    paramètre par paramètre (revue passe 1) :

    - un paramètre que le programme change garde la valeur du programme (son
      niveau encodé) ;
    - un paramètre que le programme reprend du budget voté reçoit le
      réajustement (modifier la prévention ne remet pas les franchises à leur
      valeur votée) ;
    - un paramètre ABSENT du bloc reçoit la valeur du droit en vigueur
      (réajustée ou votée), jamais le défaut du moteur : un bloc partiel vaut le
      bloc complet qui reprend le droit en vigueur. Sauf pour un levier à modes
      exclusifs : on n'y ajoute jamais une clé qui en masquerait une autre (le
      handler y lit alors ses défauts, comme en mode historique).

    Un levier absent du droit en vigueur reste le bloc du programme."""
    effectif = dict(droit_en_vigueur)
    for levier, bloc in programme.items():
        if bloc is None:
            continue
        vote = droit_vote.get(levier)
        if bloc == vote:
            continue
        reference = droit_en_vigueur.get(levier)
        if isinstance(bloc, dict) and isinstance(reference, dict):
            vote = vote if isinstance(vote, dict) else {}
            herites = ({} if levier in MODES_EXCLUSIFS else
                       {p: v for p, v in reference.items() if p not in bloc})
            reajustes = {p: reference[p] for p, v in bloc.items()
                         if p in vote and v == vote[p] and p in reference and reference[p] != v}
            if herites or reajustes:
                bloc = {**herites, **bloc, **reajustes}
        effectif[levier] = bloc
    return effectif


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


@dataclass(frozen=True)
class EtatCadre:
    """Champs du MODE CADRE (revue passe 1) : tous présents dès que le mode est
    établi, jamais optionnels ; absents en mode historique, où
    ``CadreTemporel.etat`` vaut ``None``. Un seul test, ``actif``. Gelé : une
    simulation lit son cadre, elle ne le réécrit jamais."""
    droit: DroitEnVigueur
    droit_vote: Dict
    mesures_droit: Dict
    droit_par_annee: Dict[int, Dict]
    leviers_modifies: FrozenSet[str]
    atterrissage: 'Atterrissage'
    rampe: Optional[Rampe] = None
    leviers_rampes: Tuple[str, ...] = ()
    leviers_ignores: Tuple[str, ...] = ()
    mesures_rampe: Optional[Dict[int, Dict]] = None


@dataclass(frozen=True)
class CadreTemporel:
    """Cadre d'UNE simulation : année de début, programme effectif et, en mode
    cadre, son état (``etat``). ``mesures_de_l_annee`` est le point unique lu
    par l'orchestrateur en tête d'année."""
    annee_debut: int
    programme: Dict
    etat: Optional[EtatCadre] = None

    @classmethod
    def preparer(cls, programme: Dict, annee_debut, *, droit: Optional[DroitEnVigueur] = None,
                 rampe=None, strict: bool = False, warned: Optional[set] = None,
                 corrections: Optional[dict] = None,
                 avis: Optional[dict] = None) -> 'CadreTemporel':
        """``programme`` : mesures de l'appelant APRÈS la porte d'entrée
        (``assainir_mesures``). ``droit`` : injecté en test, sinon le fichier.
        ``rampe`` : demande de l'appelant (lot D), validée ici. ``avis`` : avis
        informatifs (``report.warnings`` sans toucher ``report.valid``)."""
        debut = normaliser_annee_debut(annee_debut, strict=strict, warned=warned,
                                       corrections=corrections)
        historique = debut is None or debut == POLICY_START_YEAR
        rampe_effective = normaliser_rampe(rampe, mode_cadre=not historique, strict=strict,
                                           warned=warned, corrections=corrections)
        if debut is None or debut == POLICY_START_YEAR:
            return cls(annee_debut=POLICY_START_YEAR, programme=programme)
        droit = droit if droit is not None else charger_droit_en_vigueur()
        atterrissage = charger_atterrissage()
        # Un atterrissage ÉCRASE des niveaux : il exige que le programme
        # commence après la dernière année injectée (dossier § 2.5).
        derniere = atterrissage.derniere_annee
        if derniere is not None and debut <= derniere:
            if derniere + 1 > ANNEE_DEBUT_MAX:
                raise _defaut_atterrissage(f"l'atterrissage couvre jusqu'à {derniere} : plus "
                                           f"aucune année de début possible")
            message = (f"annee_debut = {debut} : l'atterrissage observé couvre jusqu'à "
                       f"{derniere}, le programme doit commencer après")
            if strict:
                raise AnneeDebutInvalide(message + " (mode BUDGETLAB_STRICT)")
            _signaler(warned, corrections, message + f" — ramenée à {derniere + 1}",
                      cle=('cadre', 'annee_debut_atterrissage'))
            debut = derniere + 1
        # Copie PAR SIMULATION (le droit injecté en test n'est jamais altéré).
        droit_vote = copy.deepcopy(droit.mesures)
        droit_par_annee = {an: droit_reajuste(droit_vote, atterrissage, an)
                           for an in range(POLICY_START_YEAR, debut)}
        # Droit en vigueur au début (et ensuite) : réajustements compris.
        mesures_droit = droit_reajuste(droit_vote, atterrissage, debut)
        effectif = heriter_du_droit(programme, droit_vote, mesures_droit)
        modifies = frozenset(l for l in set(effectif) | set(mesures_droit)
                             if effectif.get(l) != mesures_droit.get(l))
        rampes, ignores, par_annee = _mesures_rampees(effectif, mesures_droit, debut,
                                                      rampe_effective)
        if ignores:
            # Demande sans effet, lue telle quelle : avis informatif, jamais une
            # correction (``report.valid`` inchangé).
            _signaler(warned, avis,
                      f"rampe : {_resume(list(ignores))} égal(s) au droit en vigueur dans le "
                      f"programme — rien à ramper, demande sans effet",
                      cle=('cadre', 'rampe', 'ignores'))
        return cls(annee_debut=debut, programme=effectif, etat=EtatCadre(
            droit=droit, droit_vote=droit_vote, mesures_droit=mesures_droit,
            droit_par_annee=droit_par_annee, leviers_modifies=modifies,
            atterrissage=atterrissage, rampe=rampe_effective, leviers_rampes=rampes,
            leviers_ignores=ignores, mesures_rampe=par_annee))

    @property
    def actif(self) -> bool:
        return self.etat is not None

    @property
    def mode(self) -> str:
        return MODE_CADRE if self.etat is not None else MODE_HISTORIQUE

    @property
    def leviers_modifies(self) -> FrozenSet[str]:
        return self.etat.leviers_modifies if self.etat is not None else frozenset()

    def mesures_de_l_annee(self, annee: int) -> Dict:
        """Droit en vigueur avant ``annee_debut``, programme ensuite. Mode
        historique : le programme, toujours (le même objet : bit-identique)."""
        etat = self.etat
        if etat is None:
            return self.programme
        if annee < self.annee_debut:
            return etat.droit_par_annee.get(annee, etat.mesures_droit)
        if etat.mesures_rampe and annee in etat.mesures_rampe:
            return etat.mesures_rampe[annee]
        return self.programme

    def origines_de_l_annee(self, annee: int) -> Dict[str, int]:
        """Origine d'horloge de chaque levier MODIFIÉ par le programme, à partir
        du début (lot C) ; ``{}`` avant (et en mode historique) : tous les
        leviers comptent alors depuis ``POLICY_START_YEAR``. Lue par
        ``BudgetSimulatorV45._origine(levier)``."""
        if self.etat is None or annee < self.annee_debut:
            return {}
        return {levier: self.annee_debut for levier in self.etat.leviers_modifies}

    def cible(self, annee: int, grandeur: 'Grandeur') -> Optional[float]:
        """Valeur injectée de ``grandeur`` pour ``annee`` (mode cadre), sinon
        None. Une grandeur hors de ``GRANDEURS_ATTERRISSAGE`` est une faute de
        programmation : ``ValueError``, jamais « non injectée »."""
        verifier_grandeur(grandeur)
        if self.etat is None:
            return None
        bloc = self.etat.atterrissage.annees.get(annee)
        c = bloc.cibles.get(grandeur) if bloc is not None else None
        return None if c is None else c.valeur

    def compose(self, annee: int) -> bool:
        """Vrai si l'année exige la composition à trois mondes : mode cadre, à
        partir du début, programme différent du droit en vigueur."""
        return (self.etat is not None and annee >= self.annee_debut
                and bool(self.etat.leviers_modifies))

    def rapport_atterrissage(self, journal: Optional[Dict] = None) -> Optional[Dict]:
        """Bloc ``cadre.atterrissage`` : cibles sourcées, réajustements, et la
        DÉCOMPOSITION de chaque année simulée (valeur du modèle, valeur observée,
        choc de croissance, coin IPC, écart de solde réajustements + résidu,
        ajustement stock-flux), en % du PIB et en Md€. Identique pour tous les
        scénarios (l'année injectée est le droit en vigueur pour tous).

        Clés de la décomposition = ``GRANDEURS_ATTERRISSAGE`` (le solde sous
        ``deficit``, comme sa cible). ``journal`` : {année simulée: entrées} ;
        une année injectée hors de l'horizon simulé n'y figure pas
        (décomposition ``None``) ; une année simulée au journal incomplet est
        un défaut du moteur : ``RuntimeError``, jamais une décomposition
        partielle publiée en silence. Montant sans objet (cible ``null``) :
        ``None``, jamais 0,0."""
        etat = self.etat
        if etat is None:
            return None
        journal = journal or {}

        # Arrondis de PUBLICATION (le calcul reste en pleine précision) : 4
        # décimales en points de pourcentage, 3 en Md€.
        def pct(x):
            return None if x is None else round(x * 100, 4)

        def ecart(entree):
            return None if entree['observe'] is None else round((entree['observe'] - entree['modele']) * 100, 4)

        def md(x):
            return None if x is None else round(x, 3)

        annees = {}
        for an, bloc in sorted(etat.atterrissage.annees.items()):
            decomposition = None
            if an in journal:
                j = journal[an]
                manquantes = [c for c in CLES_JOURNAL_ATTERRISSAGE if c not in j]
                if manquantes:
                    raise RuntimeError(
                        f"Atterrissage {an} : journal incomplet ({', '.join(manquantes)}) — "
                        f"défaut du moteur : l'année simulée n'a pas été atterrie en entier")
                deficit, dette, ipc = j['deficit'], j['dette'], j['ipc']
                reaj, residuel = j['reajustements_md_eur'], deficit['residuel_md_eur']
                decomposition = {
                    'croissance': {'modele_pct': pct(j['croissance']['modele']),
                                   'observe_pct': pct(j['croissance']['observe']),
                                   'choc_pt': ecart(j['croissance'])},
                    'deflateur': {'modele_pct': pct(j['deflateur']['modele']),
                                  'observe_pct': pct(j['deflateur']['observe']),
                                  'ecart_pt': ecart(j['deflateur'])},
                    'ipc': {'deflateur_pct': pct(ipc['deflateur']), 'observe_pct': pct(ipc['observe']),
                            'coin_pt': pct(ipc['coin'])},
                    'chomage': {'modele_pct': pct(j['chomage']['modele']),
                                'observe_pct': pct(j['chomage']['observe']),
                                'ecart_pt': ecart(j['chomage'])},
                    'deficit': {'modele_pct': pct(deficit['modele']),
                                'observe_pct': pct(deficit['observe']),
                                'reajustements_md_eur': md(reaj),
                                'residuel_md_eur': md(residuel),
                                'ecart_md_eur': (None if reaj is None or residuel is None
                                                 else md(reaj + residuel))},
                    'dette': {'modele_pct': pct(dette['modele']), 'observe_pct': pct(dette['observe']),
                              'ajustement_stock_flux_md_eur': md(dette['ajustement_md_eur'])},
                }
            annees[str(an)] = {
                'cibles': {g: (None if c is None else c.publier()) for g, c in bloc.cibles.items()},
                'reajustements_droit_en_vigueur': copy.deepcopy(bloc.reajustements),
                'sources_reajustements': dict(bloc.sources_reajustements),
                'decomposition': decomposition,
            }
        return {'version': etat.atterrissage.version, 'date': etat.atterrissage.date,
                'description': etat.atterrissage.description, 'annees': annees}

    def rapport(self, journal_atterrissage: Optional[Dict] = None,
                annees_plafond_total=()) -> Dict:
        """Bloc ``cadre`` de la réponse. ``mesures_effectives`` (mode cadre) :
        les mesures appliquées à partir du début, rampe achevée — le droit en
        vigueur RÉAJUSTÉ et, par-dessus, le programme ; pour le statu quo, le
        droit en vigueur réajusté lui-même. ``plafond_total`` : le plafond de
        l'impact total des mesures (``constants.PLAFOND_IMPACT_TOTAL_PIB``,
        inchangé), sur les écarts au DÉFAUT du moteur, et les années où il
        mord."""
        etat = self.etat
        return {
            'mode': self.mode,
            'annee_debut': self.annee_debut,
            'annees_droit_en_vigueur': (list(range(POLICY_START_YEAR, self.annee_debut))
                                        if etat is not None else []),
            'droit_en_vigueur': etat.droit.meta() if etat is not None else None,
            'leviers_modifies': sorted(self.leviers_modifies),
            'mesures_effectives': copy.deepcopy(self.programme) if etat is not None else None,
            'rampe': (None if etat is None or etat.rampe is None else
                      {'annees': etat.rampe.annees, 'leviers': list(etat.rampe.leviers),
                       'leviers_rampes': list(etat.leviers_rampes),
                       'leviers_ignores': list(etat.leviers_ignores)}),
            'atterrissage': self.rapport_atterrissage(journal_atterrissage),
            'plafond_total': {'seuil_pct_pib': round(PLAFOND_IMPACT_TOTAL_PIB * 100, 6),
                              'reference': 'defauts_du_moteur',
                              'annees': list(annees_plafond_total)},
        }


def _mesures_rampees(programme: Dict, droit: Dict, debut: int, rampe: Optional[Rampe]):
    """(leviers effectivement rampés, leviers demandés SANS effet, {année:
    mesures}) pour les années de rampe non pleines (début … début + n − 2) ;
    ensuite, le programme lui-même (valeur EXACTE du programme, jamais p_droit +
    (p − p_droit) × 1). Référence d'un levier absent du droit : le défaut du
    moteur. Sans effet : paramètre égal à la référence (levier non modifié par
    le programme) ou non numérique."""
    if rampe is None:
        return (), (), None
    from ..config import load_default_values
    defauts = load_default_values()
    a_ramper, ignores = [], []
    for nom in rampe.leviers:
        levier, param = nom.split('.')
        bloc = programme.get(levier)
        if not isinstance(bloc, dict) or param not in bloc:
            ignores.append(nom)
            continue
        ref_bloc = droit.get(levier)
        ref_bloc = ref_bloc if isinstance(ref_bloc, dict) else {}
        p_ref = ref_bloc.get(param, defauts.get(levier, {}).get(param))
        p_prog = bloc[param]
        if _nombre(p_ref) and _nombre(p_prog) and p_prog != p_ref:
            a_ramper.append((nom, levier, param, p_ref, p_prog))
        else:
            ignores.append(nom)
    if not a_ramper or rampe.annees == 1:
        return (), tuple(ignores), None
    par_annee = {}
    for k in range(1, rampe.annees):
        m = dict(programme)
        for _, levier, param, p_ref, p_prog in a_ramper:
            bloc = dict(m[levier])
            bloc[param] = p_ref + (p_prog - p_ref) * k / rampe.annees
            m[levier] = bloc
        par_annee[debut + k - 1] = m
    return tuple(nom for nom, *_ in a_ramper), tuple(ignores), par_annee


# ---------------------------------------------------------------------------
# Atterrissage observé (lot E) : données serveur, appliquées en mode cadre
# ---------------------------------------------------------------------------

ATTERRISSAGE_PATH = Path(__file__).resolve().parent.parent / 'data' / 'atterrissage_observe.json'
# Grandeurs injectables, dans l'ordre d'application de l'année : SOURCE UNIQUE
# des clés du fichier (toutes présentes chaque année, ``null`` = non injectée),
# du journal de l'orchestrateur et de la décomposition publiée.
Grandeur = Literal['croissance', 'deflateur', 'ipc', 'chomage', 'deficit', 'dette']
GRANDEURS_ATTERRISSAGE: Tuple[str, ...] = get_args(Grandeur)
# Entrées du journal d'une année simulée : les six grandeurs et l'effet des
# réajustements (premier temps).
CLES_JOURNAL_ATTERRISSAGE: Tuple[str, ...] = GRANDEURS_ATTERRISSAGE + ('reajustements_md_eur',)
# Domaine des VALEURS (fractions) : garde d'unité et de plausibilité.
DOMAINES_ATTERRISSAGE = {
    'croissance': (-0.10, 0.10), 'deflateur': (-0.05, 0.15), 'ipc': (-0.05, 0.15),
    'chomage': (CHOMAGE_CLIP_MIN, CHOMAGE_CLIP_MAX), 'deficit': (-0.20, 0.05),
    'dette': (0.30, 2.50),
}
# Domaine du MÉCANISME : écart maximal entre la valeur du modèle et la cible
# (fraction ; pour le solde et la dette, en part du PIB). Même borne que les
# tables de conjoncture v0.6.9 (CONJONCTURE_AMPLITUDE_MAX) : au-delà, les filets
# du modèle écrêteraient en silence les années suivantes. Un écart plus grand
# est un défaut des données ou du modèle, à instruire : RuntimeError.
ECART_ATTERRISSAGE_MAX = CONJONCTURE_AMPLITUDE_MAX
_CLE_REAJUSTEMENTS = 'reajustements_droit_en_vigueur'
_CLE_SOURCES_REAJUSTEMENTS = 'sources_reajustements'
_CHAMPS_CIBLE = frozenset({'valeur', 'source', 'date', 'provisoire', 'note'})


def verifier_grandeur(grandeur) -> None:
    """``ValueError`` si ``grandeur`` n'est pas une grandeur d'atterrissage :
    une faute de frappe (« solde », « pib ») rendrait sinon « non injectée »
    en silence."""
    if grandeur not in GRANDEURS_ATTERRISSAGE:
        raise ValueError(f"grandeur d'atterrissage inconnue {grandeur!r} "
                         f"(attendues : {', '.join(GRANDEURS_ATTERRISSAGE)})")


@dataclass(frozen=True)
class Cible:
    valeur: float
    source: str
    date: str
    provisoire: bool = False
    note: str = ''

    def publier(self) -> Dict:
        return {'valeur': self.valeur, 'source': self.source, 'date': self.date,
                'provisoire': self.provisoire, 'note': self.note}


@dataclass(frozen=True)
class AtterrissageAnnee:
    cibles: Dict[str, Optional[Cible]]
    reajustements: Dict
    sources_reajustements: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Atterrissage:
    version: str
    date: str
    description: str
    annees: Dict[int, AtterrissageAnnee]

    @property
    def derniere_annee(self) -> Optional[int]:
        return max(self.annees) if self.annees else None


def _defaut_atterrissage(message: str) -> RuntimeError:
    return RuntimeError(f"Atterrissage invalide ({ATTERRISSAGE_PATH.name}) — défaut du serveur, "
                        f"pas de l'appelant : {message}")


def _lire_cible(annee: int, grandeur: str, brut) -> Optional[Cible]:
    if brut is None:
        return None
    if not isinstance(brut, dict):
        raise _defaut_atterrissage(f"{annee}.{grandeur} : objet {{valeur, source, date}} ou null attendu")
    inconnus = sorted(map(str, set(brut) - _CHAMPS_CIBLE))
    if inconnus:
        raise _defaut_atterrissage(f"{annee}.{grandeur} : champ(s) inconnu(s) {', '.join(inconnus)}")
    valeur = brut.get('valeur')
    if isinstance(valeur, bool) or not isinstance(valeur, numbers.Real) or not math.isfinite(valeur):
        raise _defaut_atterrissage(f"{annee}.{grandeur}.valeur = {valeur!r} : nombre fini attendu")
    valeur = float(valeur)
    bas, haut = DOMAINES_ATTERRISSAGE[grandeur]
    if not bas <= valeur <= haut:
        raise _defaut_atterrissage(f"{annee}.{grandeur}.valeur = {valeur!r} hors de [{bas} ; {haut}] "
                                   f"(fraction attendue : 0.004 pour 0,4 %)")
    for champ in ('source', 'date'):
        if not isinstance(brut.get(champ), str) or not brut[champ].strip():
            raise _defaut_atterrissage(f"{annee}.{grandeur}.{champ} manquant ou vide")
    provisoire = brut.get('provisoire', False)
    if not isinstance(provisoire, bool):
        raise _defaut_atterrissage(f"{annee}.{grandeur}.provisoire : booléen attendu")
    return Cible(valeur=valeur, source=brut['source'], date=brut['date'],
                 provisoire=provisoire, note=str(brut.get('note', '')))


def charger_atterrissage() -> Atterrissage:
    """Atterrissage observé validé, en COPIE PROFONDE à chaque appel (même
    règle que ``charger_droit_en_vigueur`` ; ``vider_caches()`` en test).
    Réajustements validés sur le droit en vigueur qu'ils modifient (mêmes portes,
    sans aucune correction, et même garde de composabilité)."""
    return copy.deepcopy(_atterrissage_valide())


@functools.lru_cache(maxsize=1)
def _atterrissage_valide() -> Atterrissage:
    try:
        contenu = json.loads(ATTERRISSAGE_PATH.read_text(encoding='utf-8'))
    except FileNotFoundError as e:
        raise _defaut_atterrissage("fichier introuvable") from e
    except OSError as e:
        raise _defaut_atterrissage(f"lecture impossible ({e})") from e
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise _defaut_atterrissage(f"JSON illisible : {e}") from e
    if not isinstance(contenu, dict):
        raise _defaut_atterrissage("objet JSON attendu")
    for champ in ('version', 'date', 'description'):
        if not isinstance(contenu.get(champ), str) or not contenu[champ].strip():
            raise _defaut_atterrissage(f"champ {champ!r} manquant ou vide")
    brutes = contenu.get('annees')
    if not isinstance(brutes, dict):
        raise _defaut_atterrissage("champ 'annees' : dict {année: bloc} attendu")
    droit = charger_droit_en_vigueur().mesures
    cumul = copy.deepcopy(droit)
    annees = {}
    for cle in sorted(brutes, key=str):
        if not (isinstance(cle, str) and cle.isdigit()):
            raise _defaut_atterrissage(f"année {cle!r} : entier attendu")
        annee = int(cle)
        if not CONJONCTURE_PREMIERE_ANNEE <= annee <= CONJONCTURE_DERNIERE_ANNEE:
            raise _defaut_atterrissage(f"année {annee} hors de [{CONJONCTURE_PREMIERE_ANNEE} ; "
                                       f"{CONJONCTURE_DERNIERE_ANNEE}] (2025 est l'année de base)")
        bloc = brutes[cle]
        if not isinstance(bloc, dict):
            raise _defaut_atterrissage(f"{annee} : objet attendu")
        inconnus = sorted(map(str, set(bloc) - set(GRANDEURS_ATTERRISSAGE)
                              - {_CLE_REAJUSTEMENTS, _CLE_SOURCES_REAJUSTEMENTS}))
        if inconnus:
            raise _defaut_atterrissage(f"{annee} : grandeur(s) inconnue(s) {', '.join(inconnus)}")
        # Les six grandeurs sont ÉCRITES chaque année (``null`` = non injectée) :
        # une clé oubliée ne vaut jamais « non injectée » en silence.
        absentes = [g for g in GRANDEURS_ATTERRISSAGE if g not in bloc]
        if absentes:
            raise _defaut_atterrissage(f"{annee} : grandeur(s) absente(s) {', '.join(absentes)} "
                                       f"(null pour « non injectée »)")
        reaj = bloc.get(_CLE_REAJUSTEMENTS, {})
        if not isinstance(reaj, dict):
            raise _defaut_atterrissage(f"{annee}.{_CLE_REAJUSTEMENTS} : dict de leviers attendu")
        for levier, params in reaj.items():
            if levier not in cumul or not isinstance(params, dict) or not params:
                raise _defaut_atterrissage(
                    f"{annee}.{_CLE_REAJUSTEMENTS}.{levier} : levier du droit en vigueur et bloc "
                    f"de paramètres non vide attendus")
            cumul[levier] = {**cumul[levier], **params}
        try:
            valider_mesures_serveur(cumul, f"{annee}.{_CLE_REAJUSTEMENTS}")
            valider_droit_composable(cumul, f"{annee}.{_CLE_REAJUSTEMENTS}")
        except RuntimeError as e:
            raise _defaut_atterrissage(str(e)) from e
        # Chaque paramètre réajusté porte sa source (aucun chiffre sans source) ;
        # une source sans réajustement est une erreur d'écriture.
        sources = bloc.get(_CLE_SOURCES_REAJUSTEMENTS, {})
        if not isinstance(sources, dict):
            raise _defaut_atterrissage(f"{annee}.{_CLE_SOURCES_REAJUSTEMENTS} : dict attendu")
        attendues = {f"{l}.{prm}" for l, params in reaj.items() for prm in params}
        for cle_source, texte in sources.items():
            if cle_source not in attendues or not isinstance(texte, str) or not texte.strip():
                raise _defaut_atterrissage(f"{annee}.{_CLE_SOURCES_REAJUSTEMENTS}.{cle_source} : "
                                           f"source d'un paramètre réajusté, texte non vide attendu")
        manquantes = sorted(attendues - set(sources))
        if manquantes:
            raise _defaut_atterrissage(f"{annee} : réajustement(s) sans source : {', '.join(manquantes)}")
        annees[annee] = AtterrissageAnnee(
            cibles={g: _lire_cible(annee, g, bloc.get(g)) for g in GRANDEURS_ATTERRISSAGE},
            reajustements=copy.deepcopy(reaj), sources_reajustements=dict(sources))
    return Atterrissage(version=contenu['version'], date=contenu['date'],
                        description=contenu['description'], annees=annees)


def droit_reajuste(droit: Dict, atterrissage: Optional[Atterrissage], annee: int) -> Dict:
    """Droit en vigueur de ``annee`` : le droit voté, et les réajustements des
    années observées ≤ ``annee`` (ils le suivent ensuite : droit constant).
    Fusion PARAMÈTRE par paramètre (un réajustement ne porte que ce qui a
    dérapé) ; résultat validé au chargement."""
    if atterrissage is None:
        return droit
    out = None
    for an in sorted(atterrissage.annees):
        if an > annee:
            break
        for levier, params in atterrissage.annees[an].reajustements.items():
            out = dict(droit) if out is None else out
            out[levier] = {**out[levier], **params}
    return droit if out is None else out


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


# Attributs du simulateur que les handlers ÉCRIVENT, donc PROPRES à chaque monde
# (échangés par ``_dans_le_monde`` : ``Monde.traqueur``, ``Monde.chomage_prev``).
# Un handler qui écrirait un autre attribut le ferait fuir d'un monde à l'autre
# en silence : la garde de test_cadre_v070_horloges.py (revue passe 1) le refuse.
ETATS_PAR_MONDE = frozenset({'_measure_params_tracker', '_chomage_params_prev'})


def creer_mondes(cadre_temporel: 'CadreTemporel') -> Dict[str, Monde]:
    """Les trois mondes d'une simulation en mode cadre. ``programme`` et
    ``droit_debut`` démarrent vides au début du programme ; leurs origines et
    leurs mesures sont posées chaque année par l'orchestrateur."""
    if cadre_temporel.etat is None:
        raise ValueError("creer_mondes : mode cadre attendu (mode historique : un seul monde)")
    droit = cadre_temporel.etat.mesures_droit
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
