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
    return DroitEnVigueur(**{c: contenu[c] for c in _CHAMPS_TEXTE_DROIT}, mesures=mesures)


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

    @classmethod
    def preparer(cls, programme: Dict, annee_debut, *, droit: Optional[DroitEnVigueur] = None,
                 strict: bool = False, warned: Optional[set] = None,
                 corrections: Optional[dict] = None) -> 'CadreTemporel':
        """``programme`` : mesures de l'appelant APRÈS la porte d'entrée
        (``assainir_mesures``). ``droit`` : injecté en test, sinon le fichier."""
        debut = normaliser_annee_debut(annee_debut, strict=strict, warned=warned,
                                       corrections=corrections)
        if debut is None or debut == POLICY_START_YEAR:
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
        return cls(mode=MODE_CADRE, annee_debut=debut, droit=droit,
                   mesures_droit=mesures_droit, programme=effectif,
                   leviers_modifies=modifies)

    @property
    def actif(self) -> bool:
        return self.mode == MODE_CADRE

    def mesures_de_l_annee(self, annee: int) -> Dict:
        """Droit en vigueur avant ``annee_debut``, programme ensuite. Mode
        historique : le programme, toujours (le même objet : bit-identique)."""
        if self.actif and annee < self.annee_debut:
            return self.mesures_droit
        return self.programme

    def rapport(self) -> Dict:
        """Bloc ``cadre`` de la réponse."""
        return {
            'mode': self.mode,
            'annee_debut': self.annee_debut,
            'annees_droit_en_vigueur': (list(range(POLICY_START_YEAR, self.annee_debut))
                                        if self.actif else []),
            'droit_en_vigueur': self.droit.meta() if self.droit is not None else None,
            'leviers_modifies': sorted(self.leviers_modifies),
        }
