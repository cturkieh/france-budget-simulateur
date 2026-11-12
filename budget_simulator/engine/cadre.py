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
from typing import Callable, Dict, FrozenSet, Literal, Optional, Tuple, get_args

from ..constants import (
    ANNEE_FIN_MANDAT,
    CHOMAGE_CLIP_MAX,
    CHOMAGE_CLIP_MIN,
    CHOMAGE_MONTANT_REF_MD,
    CHOMAGE_TAUX_REF,
    CONJONCTURE_AMPLITUDE_MAX,
    CONJONCTURE_DERNIERE_ANNEE,
    CONJONCTURE_PREMIERE_ANNEE,
    CROISSANCE_FILET_MAX,
    CROISSANCE_FILET_MIN,
    EXCLUSIONS_MUTUELLES,
    NEUTRES_RELEASE_E,
    PARAM_DOMAINS,
    PLAFOND_IMPACT_TOTAL_PIB,
    PLAFOND_TOTAL_MODE,
    POLICY_START_YEAR,
)
from ._noms_parametres import MODES_EXCLUSIFS, NOMS_PARAMETRES_ADMIS
from ._param_domain import (
    _DETAILS_MAX,
    EntreeInvalide,
    _apercu,
    _apercu_nom,
    _est_fini,
    condition_d_exclusion_vraie,
    validate_intensite_domain,
    validate_param_domains,
    valider_modes_exclusifs,
    valider_noms_parametres,
)

logger = logging.getLogger(__name__)

# Domaine de ``annee_debut`` : 2026 (mode historique) à la fin du quinquennat
# 2027-2032. Au-delà, un programme n'aurait plus d'année d'application dans la
# fenêtre affichée. ANNEE_FIN_MANDAT (constants.py) est aussi la dernière année
# d'une rampe de profil (release E, contrat § 2.1) : une seule source.
ANNEE_DEBUT_MIN = POLICY_START_YEAR
ANNEE_DEBUT_MAX = ANNEE_FIN_MANDAT

MODE_HISTORIQUE = 'historique'
MODE_CADRE = 'cadre'

DROIT_EN_VIGUEUR_PATH = Path(__file__).resolve().parent.parent / 'data' / 'droit_en_vigueur.json'
_CHAMPS_TEXTE_DROIT = ('identifiant', 'libelle', 'source', 'date')
_DATE_ISO = re.compile(r'^\d{4}-\d{2}-\d{2}$')


class AnneeDebutInvalide(EntreeInvalide, ValueError):
    """``annee_debut`` hors de [2026 ; 2032] ou non entière (mode BUDGETLAB_STRICT)."""


class RampeInvalide(EntreeInvalide, ValueError):
    """``rampe`` mal formée, hors domaine ou en mode historique (mode BUDGETLAB_STRICT)."""


class ProfilInvalide(EntreeInvalide, ValueError):
    """``profils`` mal formé, clé non éligible, année hors du mandat, forme
    interdite (recette exceptionnelle), mode historique, ou ``rampe`` et
    ``profils`` ensemble (release E, W1, contrat § 2.1 ; mode BUDGETLAB_STRICT)."""


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
                     corrections: Optional[dict] = None,
                     debut: Optional[int] = None) -> Optional['Rampe']:
    """Rampe effective, ou ``None`` (aucune). Strict : ``RampeInvalide`` au
    premier défaut. Tolérant : WARNING une fois et correction tracée —
    ``annees`` ramenée au domaine, leviers inconnus ou non éligibles retirés,
    clés inconnues ignorées, rampe ignorée en mode historique ou si illisible.

    TAILLE BORNÉE (revue de sécurité, amplification de ressources ; parité avec
    ``_param_domain``) : au plus une entrée par levier éligible
    (``RAMPE_LEVIERS_ELIGIBLES``), sinon rejet sans parcourir la liste ; noms
    dédoublonnés ; les noms retirés font UN avertissement à clé fixe, au plus
    ``_DETAILS_MAX`` noms détaillés et chacun tronqué ; la liste des leviers
    éligibles n'y est jamais répétée (elle vit ici et dans METHODOLOGIE).

    FIN DU MANDAT (contre-vérification m5) : comme un profil « rampe », la
    rampe finit au plus tard en ``ANNEE_FIN_MANDAT`` — ``annees`` est borné à
    ``ANNEE_FIN_MANDAT − debut + 1`` (≤ ``RAMPE_ANNEES_MAX``) : ramené à la
    borne et tracé en tolérant, ``RampeInvalide`` en strict."""
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
    annees_max = (RAMPE_ANNEES_MAX if debut is None
                  else max(RAMPE_ANNEES_MIN, min(RAMPE_ANNEES_MAX, ANNEE_FIN_MANDAT - debut + 1)))
    hors_borne = _annees_hors_borne(annees, annees_max)
    if hors_borne is not None:
        # Strict : refus, avec le domaine (jamais « ramenée à », la requête
        # étant refusée) ; tolérant : ramenée à la borne, comme un profil
        # « rampe » (relecture adverse finale, m-c).
        message, borne = hors_borne
        if strict:
            raise RampeInvalide(f"rampe : {message} (mode BUDGETLAB_STRICT)")
        annees = defaut(f"{message} — ramenée à {borne}", borne, 'annees')
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


# === PROFILS TEMPORELS (release E, chantier W1, contrat § 2) ===
# Calendrier d'un montant en Md€ : « chaque année » (plein), « montée
# progressive jusqu'à la fin du mandat » (rampe), « une seule année » (annee).
# UN seul mécanisme, au niveau du cadre : les handlers reçoivent toujours le
# niveau de l'année (point unique mesures_de_l_annee) ; la rampe v0.7.0 en est
# un cas particulier (alias, mêmes sorties au bit).
# Clés éligibles : celles de la rampe générique, les dix-sept paramètres en
# Md€ de la release E (contrat § 2.1), quatre taux ou niveaux qu'un programme
# écrit avec une montée progressive (PROFILS_TAUX_ET_NIVEAUX) et les deux
# coefficients d'indexation, pour un gel d'une seule année
# (PROFILS_INDEXATIONS). Les autres taux et les durées basculent sans profil.
#
# Taux et niveaux (revue adverse de la release E ; règle du mainteneur : on
# suit le calendrier écrit par le programme) : cotisations salariales
# (points), cotisations patronales (taux), salaires des enseignants (%), budget
# chômage en montant. Formes admises : « plein » et « rampe » (interpolation
# linéaire entre le droit en vigueur de l'année et la cible, cible exacte en
# 2032) ; leurs effets ponctuels sont émis en incréments. « Une seule année »
# est refusée : une réforme de niveau qui s'annule l'année suivante n'est pas
# un calendrier de programme. (Le handler des cotisations salariales, qui
# sortait avant de rendre son effet ponctuel au retour à 0, le rend depuis la
# contre-vérification m4.) Effets ponctuels qui lisent la masse salariale de
# l'année (compétitivité) : cumul dépendant du chemin sous une rampe, limite
# dite dans METHODOLOGIE (contre-vérification m3).
PROFILS_TAUX_ET_NIVEAUX = frozenset({
    'cotisations_salariales.baisse_points', 'cotisations_patronales.taux',
    'education.salaires', 'chomage_alloc.montant',
})
# Coefficients d'indexation des pensions et des prestations sociales (décision
# du mainteneur du 12/11/2026 : gel d'UNE année, revalorisation normale
# ensuite). Le coefficient s'applique à la revalorisation de l'année ; les
# handlers gardent le coefficient de chaque revalorisation écoulée, si bien
# qu'un gel d'une année laisse un écart de NIVEAU permanent (aucun rattrapage)
# et que le retour à la pleine indexation ne rend rien. Formes admises :
# « plein » et « une seule année ». La rampe n'est pas ouverte : une montée
# progressive du coefficient n'est pas un calendrier qu'un programme écrit (il
# écrit un gel ou une sous-indexation, pour une ou plusieurs années).
PROFILS_INDEXATIONS = frozenset({
    'retraites.indexation', 'prestations_indexation.taux_indexation',
})
PROFILS_ELIGIBLES = RAMPE_LEVIERS_ELIGIBLES | PROFILS_TAUX_ET_NIVEAUX | PROFILS_INDEXATIONS | frozenset({
    'depenses_publiques.credits_etat', 'depenses_publiques.ondam',
    'depenses_publiques.transferts_capital',
    'prestations_menages.solidarite', 'prestations_menages.pensions',
    'transferts_etranger.montant', 'droits_succession.variation',
    'fiscalite_capital.rendement_md',
    'multinationales.benefices_recuperes', 'multinationales.rendement_tsn_md',
    'operations_financieres.rendement_ttf_md', 'operations_financieres.rachats_actions',
    'operations_financieres.crypto_actifs',
    'fiscalite_indirecte.tva_ciblee', 'fiscalite_indirecte.accises_energie',
    'impot_revenu_cible.montant', 'recette_exceptionnelle.montant',
})
# Forme « valeurs » (release P, v0.8.1 ; décision du mainteneur du 12/11/2026 sur
# les objectifs écrits en part du PIB ou du RNB) : le montant de CHAQUE année,
# du début à une année ≤ ANNEE_FIN_MANDAT, sans lacune ; ensuite la valeur du
# programme. Les mesures de chaque année passent par le même chemin qu'une
# rampe (``_mesures_profilees``) : aucune équation ne change (égalité au bit
# avec une rampe aux mêmes valeurs, tests/test_release_p_calendrier_valeurs.py).
# Réservée aux montants en Md€ : les taux et niveaux, les coefficients
# d'indexation et la recette d'une seule année ont leurs formes (FORMES_ADMISES).
FORMES_PROFIL = ('plein', 'rampe', 'annee', 'valeurs')
_PROFIL_CLES = frozenset({'forme', 'annee', 'annees', 'valeurs'})
# Une recette exceptionnelle ne s'applique qu'UNE année : seule la forme
# « annee » est admise, et c'est son défaut, à l'année de début (règle 4.2-k du
# plan consolidé) ; en mode historique (aucun calendrier), elle est refusée.
CLE_RECETTE_EXCEPTIONNELLE = 'recette_exceptionnelle.montant'
# Formes admises par clé, quand elles diffèrent de FORMES_PROFIL.
FORMES_ADMISES = {CLE_RECETTE_EXCEPTIONNELLE: ('annee',),
                  **{cle: ('plein', 'rampe') for cle in PROFILS_TAUX_ET_NIVEAUX},
                  **{cle: ('plein', 'annee') for cle in PROFILS_INDEXATIONS}}
# Leviers qu'une demande non neutre fait refuser en mode historique (source
# unique pour les outils qui essaient chaque levier : mini-scénarios
# standalone, balayages ; ils les simulent en mode cadre).
LEVIERS_REFUSES_EN_MODE_HISTORIQUE = frozenset({CLE_RECETTE_EXCEPTIONNELLE.split('.')[0]})


@dataclass(frozen=True)
class Profil:
    """Profil validé d'un paramètre. ``annees`` : durée de rampe explicite
    (alias ``rampe`` v0.7.0 ; facultatif, réservé à la compatibilité) ; sans
    elle, une rampe finit en ``ANNEE_FIN_MANDAT``. Dans ``profils`` comme dans
    l'alias, ``annees`` est borné pour finir au plus tard en
    ``ANNEE_FIN_MANDAT`` (``_lire_profil``, ``normaliser_rampe``)."""
    forme: str
    annee: Optional[int] = None
    annees: Optional[int] = None
    # Forme « valeurs » : ((année, montant), …), du début à la dernière année
    # écrite, sans lacune (``_lire_valeurs``).
    valeurs: Optional[Tuple[Tuple[int, float], ...]] = None

    def publier(self) -> Dict:
        out = {'forme': self.forme}
        if self.forme == 'annee':
            out['annee'] = self.annee
        if self.annees is not None:
            out['annees'] = self.annees
        if self.valeurs is not None:
            out['valeurs'] = {str(an): v for an, v in self.valeurs}
        return out


def _entier(v) -> bool:
    return isinstance(v, numbers.Integral) and not isinstance(v, bool)


def _annee_de_cle(c) -> Optional[int]:
    """Année d'une clé de ``valeurs`` : entier, ou texte de quatre chiffres
    (clé d'un objet JSON) ; ``None`` sinon."""
    if _entier(c):
        return int(c)
    if isinstance(c, str) and re.fullmatch(r'\d{4}', c):
        return int(c)
    return None


def _lire_valeurs(cle: str, brut, debut: int):
    """Montants d'une forme « valeurs » : ``((année, montant), …)`` validés, ou
    le texte (borné) du défaut. Années du début à une année ≤
    ``ANNEE_FIN_MANDAT``, sans lacune ni doublon ; montants finis, dans le
    domaine du paramètre (``PARAM_DOMAINS`` : une valeur datée ne contourne
    jamais la borne d'un curseur). TAILLE BORNÉE (parité avec la rampe, revue
    de sécurité) : au plus ``ANNEE_FIN_MANDAT − début + 1`` entrées, sinon refus
    sans parcourir."""
    if not isinstance(brut, dict) or not brut:
        return (f"{cle} : valeurs = objet {{\"année\": montant}} non vide attendu, reçu "
                f"{_apercu(brut)}")
    n_max = ANNEE_FIN_MANDAT - debut + 1
    if len(brut) > n_max:
        return (f"{cle} : {len(brut)} valeurs pour {n_max} années au plus (de {debut} à "
                f"{ANNEE_FIN_MANDAT})")
    levier, param = cle.split('.')
    domaine = (PARAM_DOMAINS.get(levier) or {}).get(param)
    if domaine is None:
        return f"{cle} : domaine du paramètre inconnu, valeurs refusées"
    lues = {}
    for c, v in brut.items():
        an = _annee_de_cle(c)
        if an is None:
            return f"{cle} : valeurs, année {_apercu(c)} illisible (quatre chiffres attendus)"
        if an in lues:
            return f"{cle} : valeurs, année {an} en double"
        if not _nombre(v) or not _est_fini(v):
            return f"{cle} : valeurs, montant {_apercu(v)} de {an} : nombre fini attendu"
        if not domaine[0] <= v <= domaine[1]:
            return (f"{cle} : valeurs, montant {_apercu(v)} de {an} hors du domaine "
                    f"[{domaine[0]:g} ; {domaine[1]:g}]")
        lues[an] = float(v)
    annees = sorted(lues)
    attendues = list(range(debut, annees[-1] + 1))
    if annees != attendues or annees[-1] > ANNEE_FIN_MANDAT:
        return (f"{cle} : valeurs, années {_resume([str(a) for a in annees])} : chaque année de "
                f"{debut} à une année ≤ {ANNEE_FIN_MANDAT} attendue, sans lacune")
    return tuple((an, lues[an]) for an in annees)


def _annees_hors_borne(annees: int, annees_max: int):
    """Durée de rampe entière hors de [RAMPE_ANNEES_MIN ; ``annees_max``] (la
    rampe finit au plus tard en ``ANNEE_FIN_MANDAT``) : ``(message, borne)``,
    sinon ``None``. SOURCE UNIQUE du profil « rampe » et de l'alias ``rampe``
    (relecture adverse finale, m-c) : même domaine, même message, même borne
    en tolérant."""
    if RAMPE_ANNEES_MIN <= annees <= annees_max:
        return None
    return (f"annees = {_apercu(annees)} hors de [{RAMPE_ANNEES_MIN} ; {annees_max}] (la rampe "
            f"finit au plus tard en {ANNEE_FIN_MANDAT})",
            min(max(annees, RAMPE_ANNEES_MIN), annees_max))


def _lire_profil(cle, brut, debut: int):
    """``Profil`` d'une entrée valide, ``(Profil, texte)`` d'une durée de
    rampe entière hors de sa borne (profil ramené à la borne ; le texte dit le
    défaut, pour le refus strict ou la correction tracée), ou le texte (borné)
    du défaut d'une entrée invalide."""
    if not isinstance(cle, str) or cle not in PROFILS_ELIGIBLES:
        return (f"{_apercu_nom(cle)} : paramètre non éligible ou inconnu (éligibles : montants en "
                f"Md€, quatre taux ou niveaux et deux coefficients d'indexation, engine/cadre.py, "
                f"PROFILS_ELIGIBLES)")
    if not isinstance(brut, dict):
        return f"{cle} : objet {{forme, annee?}} attendu, reçu {_apercu(brut)}"
    inconnues = sorted(_apercu_nom(c) for c in set(brut) - _PROFIL_CLES)
    if inconnues:
        return f"{cle} : clé(s) inconnue(s) {_resume(inconnues)}"
    forme = brut.get('forme')
    if not isinstance(forme, str) or forme not in FORMES_PROFIL:
        return f"{cle} : forme {_apercu(forme)} inconnue (plein, rampe, annee ou valeurs)"
    if cle == CLE_RECETTE_EXCEPTIONNELLE and forme != 'annee':
        return (f"{cle} : seule la forme « annee » est admise pour une recette d'une seule année "
                f"(reçu « {forme} »)")
    if forme not in FORMES_ADMISES.get(cle, FORMES_PROFIL):
        if cle in PROFILS_INDEXATIONS:
            return (f"{cle} : forme « {forme} » non admise pour un coefficient d'indexation "
                    f"(admises : {', '.join(FORMES_ADMISES[cle])} ; le coefficient s'applique à la "
                    f"revalorisation de chaque année, une rampe du coefficient n'est pas un calendrier "
                    f"de programme)")
        return (f"{cle} : forme « {forme} » non admise pour un taux ou un niveau (admises : "
                f"{', '.join(FORMES_ADMISES[cle])} ; une réforme de niveau ne s'annule pas l'année "
                f"suivante)")
    annee, annees = brut.get('annee'), brut.get('annees')
    if forme == 'annee':
        if annee is None:
            return f"{cle} : annee requise pour la forme « annee »"
        if not _entier(annee):
            return (f"{cle} : annee = {_apercu(annee)} : année entière attendue dans "
                    f"[{debut} ; {ANNEE_FIN_MANDAT}]")
        if not debut <= annee <= ANNEE_FIN_MANDAT:
            return f"{cle} : annee = {int(annee)} hors de [{debut} ; {ANNEE_FIN_MANDAT}]"
    elif annee is not None:
        return f"{cle} : annee interdite pour la forme « {forme} » (seulement pour « annee »)"
    hors_borne = None
    if annees is not None:
        if forme != 'rampe':
            return f"{cle} : annees réservé à la forme « rampe »"
        # Une rampe finit au plus tard en ANNEE_FIN_MANDAT (revue adverse de la
        # release E) : début + annees − 1 ≤ 2032 ; l'alias ``rampe`` v0.7.0 suit
        # la même borne (contre-vérification m5, normaliser_rampe). Une durée
        # entière hors de la borne est ramenée à la borne en tolérant, comme
        # pour l'alias (relecture adverse finale, m-c ; avant : profil ignoré,
        # programme en plein dès le début) ; une durée non entière est refusée.
        annees_max = max(RAMPE_ANNEES_MIN, min(RAMPE_ANNEES_MAX, ANNEE_FIN_MANDAT - debut + 1))
        if not _entier(annees):
            return (f"{cle} : annees = {_apercu(annees)} : entier attendu dans "
                    f"[{RAMPE_ANNEES_MIN} ; {annees_max}] (la rampe finit au plus tard en "
                    f"{ANNEE_FIN_MANDAT})")
        hors_borne = _annees_hors_borne(int(annees), annees_max)
        if hors_borne is not None:
            annees = hors_borne[1]
    valeurs = None
    if forme == 'valeurs':
        valeurs = _lire_valeurs(cle, brut.get('valeurs'), debut)
        if isinstance(valeurs, str):
            return valeurs
    elif 'valeurs' in brut:
        return f"{cle} : valeurs interdites pour la forme « {forme} » (seulement pour « valeurs »)"
    profil = Profil(forme=forme, annee=int(annee) if forme == 'annee' else None,
                    annees=None if annees is None else int(annees), valeurs=valeurs)
    return profil if hors_borne is None else (profil, f"{cle} : {hors_borne[0]}")


def normaliser_profils(valeur, *, mode_cadre: bool, debut: int, strict: bool,
                       warned: Optional[set] = None,
                       corrections: Optional[dict] = None) -> Dict[str, Profil]:
    """Profils validés ``{"levier.parametre": Profil}`` (``{}`` sans profil).

    Même contrat dual que ``normaliser_rampe`` : strict, ``ProfilInvalide`` au
    premier défaut ; tolérant, l'entrée fautive est ignorée (les autres sont
    gardées), WARNING une fois et correction tracée (``report.valid =
    false``). Profils non vides en mode historique : refusés en bloc. TAILLE
    BORNÉE (parité avec la rampe, revue de sécurité) : au plus
    ``len(PROFILS_ELIGIBLES)`` entrées, sinon rejet sans parcourir."""
    if valeur is None or (isinstance(valeur, dict) and not valeur):
        return {}
    cle = ('cadre', 'profils')

    def refus(message, sous_cle):
        if strict:
            raise ProfilInvalide(f"profils : {message} (mode BUDGETLAB_STRICT)")
        _signaler(warned, corrections, f"profils : {message}", cle=cle + (sous_cle,))
        return {}

    if not mode_cadre:
        return refus(f"un calendrier exige annee_debut dans [2027 ; {ANNEE_DEBUT_MAX}] (mode "
                     f"historique : programme dès {POLICY_START_YEAR}, sans calendrier) — profils "
                     f"ignorés", 'mode')
    if not isinstance(valeur, dict):
        return refus(f"objet {{\"levier.parametre\": {{forme, annee?}}}} attendu, reçu "
                     f"{type(valeur).__name__} — profils ignorés", 'forme')
    n_max = len(PROFILS_ELIGIBLES)
    if len(valeur) > n_max:
        return refus(f"{len(valeur)} entrées pour {n_max} paramètres éligibles au plus "
                     f"(engine/cadre.py, PROFILS_ELIGIBLES) — profils ignorés", 'taille')
    retenus, defauts, ramenes = {}, [], []
    for cle_profil, brut in valeur.items():
        lu = _lire_profil(cle_profil, brut, debut)
        if isinstance(lu, tuple):
            # Durée de rampe hors de sa borne : refus en strict, ramenée à la
            # borne et tracée en tolérant (comme l'alias, m-c).
            profil, texte = lu
            if strict:
                raise ProfilInvalide(f"profils : {texte} (mode BUDGETLAB_STRICT)")
            ramenes.append(f"{texte} — ramenée à {profil.annees}")
            retenus[cle_profil] = profil
        elif isinstance(lu, Profil):
            retenus[cle_profil] = lu
        elif strict:
            raise ProfilInvalide(f"profils : {lu} (mode BUDGETLAB_STRICT)")
        else:
            defauts.append(lu)
    if defauts:
        _signaler(warned, corrections, f"profils : entrée(s) ignorée(s) — {_resume(defauts)}",
                  cle=cle + ('entrees',))
    if ramenes:
        _signaler(warned, corrections, f"profils : durée de rampe ramenée — {_resume(ramenes)}",
                  cle=cle + ('annees',))
    return retenus


def _sans_recette_exceptionnelle(programme: Dict, *, strict: bool, warned: Optional[set],
                                 corrections: Optional[dict]) -> Dict:
    """Mode historique : une recette exceptionnelle (une seule année, calendrier
    obligatoire) est refusée — strict ``ProfilInvalide``, tolérant levier
    retiré (jamais évalué) et correction tracée. Seul un MONTANT demandé (un
    nombre fini différent du neutre) est refusé : un bloc au neutre ne demande
    rien, et un nom inconnu ou une valeur non numérique restent aux portes des
    noms et des valeurs, qui les qualifient (objet identique)."""
    levier, param = CLE_RECETTE_EXCEPTIONNELLE.split('.')
    bloc = programme.get(levier)
    montant = bloc.get(param) if isinstance(bloc, dict) else None
    if (not _nombre(montant) or not _est_fini(montant)
            or montant == NEUTRES_RELEASE_E[levier][param]):
        return programme
    message = (f"{levier} : une recette d'une seule année exige annee_debut dans [2027 ; "
               f"{ANNEE_DEBUT_MAX}] (mode historique : aucun calendrier) — levier ignoré")
    if strict:
        raise ProfilInvalide(f"{message} (mode BUDGETLAB_STRICT)")
    _signaler(warned, corrections, message, cle=('cadre', 'recette_exceptionnelle'))
    return {k: v for k, v in programme.items() if k != levier}


@dataclass(frozen=True)
class Segment:
    """Valeur datée d'un paramètre du droit en vigueur : de ``de`` à ``a``
    inclus (``a`` absent : segment ouvert, le dernier), avec sa source."""
    de: int
    a: Optional[int]
    valeur: float
    source: str

    def contient(self, annee: int) -> bool:
        return self.de <= annee and (self.a is None or annee <= self.a)


@dataclass(frozen=True)
class DroitEnVigueur:
    """Jeu de paramètres appliqué avant ``annee_debut`` (donnée serveur validée).

    ``valeurs_datees`` (release E, W1, contrat § 5.3) : ``{levier: {paramètre:
    (Segment, …)}}``, segments contigus de 2026 à un dernier segment ouvert ;
    vide quand le fichier n'en porte pas (E est livré sans valeur datée)."""
    identifiant: str
    libelle: str
    source: str
    date: str
    mesures: Dict
    valeurs_datees: Dict = field(default_factory=dict)

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


def _lire_objet_json(chemin: Path, defaut: Callable[[str], RuntimeError]) -> Dict:
    """Objet JSON d'un fichier de données serveur ; ``defaut(message)`` au
    premier défaut (absent, illisible, JSON invalide, pas un objet)."""
    try:
        contenu = json.loads(chemin.read_text(encoding='utf-8'))
    except FileNotFoundError as e:
        raise defaut("fichier introuvable") from e
    except OSError as e:
        raise defaut(f"lecture impossible ({e})") from e
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise defaut(f"JSON illisible : {e}") from e
    if not isinstance(contenu, dict):
        raise defaut("objet JSON attendu")
    return contenu


@functools.lru_cache(maxsize=1)
def _droit_en_vigueur_valide() -> DroitEnVigueur:
    contenu = _lire_objet_json(DROIT_EN_VIGUEUR_PATH, _defaut_serveur)
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
    datees = _lire_valeurs_datees(mesures, contenu.get('valeurs_datees', {}))
    return DroitEnVigueur(**{c: contenu[c] for c in _CHAMPS_TEXTE_DROIT}, mesures=mesures,
                          valeurs_datees=datees)


_SEGMENT_CLES = frozenset({'de', 'a', 'valeur', 'source'})


def _lire_valeurs_datees(mesures: Dict, brut) -> Dict:
    """Valeurs datées validées (release E, W1, contrat § 5.3), ou ``{}``.

    Chaque ``levier.parametre`` daté est inscrit dans ``mesures`` ; ses
    segments sont contigus, le premier commence en ``POLICY_START_YEAR``, le
    dernier est ouvert (sans ``a``), chacun porte une source (texte non vide) ;
    chaque valeur passe les portes d'entrée sans correction et le droit qui en
    résulte reste composable. Tout défaut : ``RuntimeError`` (donnée serveur,
    500), jamais une correction silencieuse."""
    if brut == {}:
        return {}
    if not isinstance(brut, dict):
        raise _defaut_serveur("valeurs_datees : dict {levier: {paramètre: [segments]}} attendu")
    lues = {}
    for levier, params in brut.items():
        if levier not in mesures or not isinstance(params, dict) or not params:
            raise _defaut_serveur(f"valeurs_datees.{_apercu_nom(levier)} : levier inscrit dans "
                                  f"'mesures' et bloc de paramètres non vide attendus")
        for param, segments in params.items():
            chemin = f"valeurs_datees.{levier}.{_apercu_nom(param)}"
            if param not in mesures[levier]:
                raise _defaut_serveur(f"{chemin} : paramètre absent de mesures.{levier}")
            if not isinstance(segments, list) or not segments:
                raise _defaut_serveur(f"{chemin} : liste de segments non vide attendue")
            lus = []
            for i, seg in enumerate(segments):
                ici = f"{chemin}[{i}]"
                if not isinstance(seg, dict) or set(seg) - _SEGMENT_CLES:
                    raise _defaut_serveur(f"{ici} : objet {{de, a?, valeur, source}} attendu")
                de, a = seg.get('de'), seg.get('a')
                if not _entier(de) or (a is not None and not _entier(a)):
                    raise _defaut_serveur(f"{ici} : de et a entiers attendus")
                source = seg.get('source')
                if not isinstance(source, str) or not source.strip():
                    raise _defaut_serveur(f"{ici} : source manquante ou vide")
                if i == 0 and de != POLICY_START_YEAR:
                    raise _defaut_serveur(f"{ici} : le premier segment commence en "
                                          f"{POLICY_START_YEAR} (reçu {de})")
                if i > 0 and de != lus[-1].a + 1:
                    raise _defaut_serveur(f"{ici} : segments non contigus ({lus[-1].a} puis {de})")
                dernier = i == len(segments) - 1
                if dernier and a is not None:
                    raise _defaut_serveur(f"{ici} : le dernier segment est ouvert (sans a)")
                if not dernier and (a is None or a < de):
                    raise _defaut_serveur(f"{ici} : a ≥ de attendu pour un segment fermé")
                valeur = seg.get('valeur')
                if not _nombre(valeur):
                    raise _defaut_serveur(f"{ici} : valeur numérique attendue (reçu {_apercu(valeur)})")
                valider_mesures_serveur({levier: {**mesures[levier], param: valeur}}, ici)
                lus.append(Segment(de=int(de), a=None if a is None else int(a), valeur=valeur,
                                   source=source))
            lues.setdefault(levier, {})[param] = tuple(lus)
    for annee in sorted({s.de for p in lues.values() for segs in p.values() for s in segs}):
        valider_droit_composable(droit_de_l_annee(mesures, None, annee, lues),
                                 f"valeurs_datees ({annee})")
    return lues


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
    # Exclusions mutuelles (release E, W1) : elles sont appliquées au programme
    # de l'appelant, à la porte d'entrée. Un droit en vigueur qui remplirait
    # LUI-MÊME une condition d'exclusion la ferait hériter en silence par un
    # programme qui pose l'autre levier : refusé (composition non implémentée).
    for regle, spec in EXCLUSIONS_MUTUELLES.items():
        for condition in spec['conditions']:
            levier, param = condition[0], condition[1]
            bloc = mesures.get(levier)
            if (isinstance(bloc, dict) and bloc.get(param) is not None
                    and condition_d_exclusion_vraie(mesures, regle, spec, condition)):
                raise _defaut_serveur(
                    f"{origine} : {levier}.{param} = {bloc[param]!r} remplit une condition de "
                    f"l'exclusion {regle} (constants.EXCLUSIONS_MUTUELLES) : un programme qui "
                    f"pose l'autre levier l'hériterait sans contrôle (non implémenté)")


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


def retirer_blocs_neutres(programme: Dict, droit_en_vigueur: Dict) -> Dict:
    """Programme sans les blocs AU NEUTRE des leviers absents du droit en
    vigueur, lus comme un ``null`` (contrat de la release E, § 2.1 « Neutres » ;
    règle avancée au commit socle, que le chantier W1 hérite avec son test).

    Sans elle, un tel bloc ne change aucune trajectoire mais entre dans
    ``leviers_modifies`` et ``mesures_effectives`` (et déclenche la composition
    à trois mondes) : la neutralité au bit du RAPPORT (test G1) ne tiendrait pas
    en mode cadre.

    Portée : les seuls leviers dont le moteur définit le neutre,
    ``constants.NEUTRES_RELEASE_E`` ; tout autre levier garde la règle v0.7.2
    (un bloc présent est appliqué, même égal au défaut du moteur). Un bloc est
    neutre si chacune de ses valeurs est ``null`` (absente) ou un nombre égal au
    neutre du paramètre ; un bloc vide l'est donc ; une clé de mode exclusif
    (``rendement_*``, neutre = clé absente) ne l'est jamais. Rien n'est signalé :
    le bloc ne demandait rien. Programme renvoyé tel quel (même objet) quand
    aucun bloc n'est retiré."""
    def neutre(levier, bloc) -> bool:
        reference = NEUTRES_RELEASE_E.get(levier)
        return (reference is not None and levier not in droit_en_vigueur
                and isinstance(bloc, dict)
                and all(v is None or (p in reference and _nombre(v) and v == reference[p])
                        for p, v in bloc.items()))

    retires = {levier for levier, bloc in programme.items() if neutre(levier, bloc)}
    if not retires:
        return programme
    return {levier: bloc for levier, bloc in programme.items() if levier not in retires}


def heriter_du_droit(programme: Dict, droit_en_vigueur: Dict) -> Dict:
    """Mesures du programme par-dessus le droit en vigueur, réajustements de
    l'atterrissage compris (lot E).

    Règle « présent = imposé, absent = hérité » (v0.7.2, décision du mainteneur
    du 08/11/2026) :

    - un levier absent ou ``null`` est celui du droit en vigueur réajusté ;
    - un paramètre PRÉSENT est appliqué tel quel, même égal au budget voté :
      des franchises demandées à 100 sont appliquées à 100, pas au 120 réajusté ;
    - un paramètre ABSENT (ou ``null``) d'un bloc présent reçoit la valeur du
      droit en vigueur réajusté, jamais le défaut du moteur : un bloc partiel
      vaut le bloc complet qui reprend le droit en vigueur ;
    - exception, un levier à modes exclusifs : on n'y ajoute jamais une clé
      qui en masquerait une autre (le handler y lit alors ses défauts, comme
      en mode historique) ;
    - un levier absent du droit en vigueur reste le bloc du programme.

    Jusqu'en v0.7.1, un « pont » traitait un bloc ou un paramètre égal au voté
    comme non touché et lui substituait le réajusté : une demande explicite
    était remplacée sans le dire."""
    effectif = dict(droit_en_vigueur)
    for levier, bloc in programme.items():
        if bloc is None:
            continue
        reference = droit_en_vigueur.get(levier)
        if (isinstance(bloc, dict) and isinstance(reference, dict)
                and levier not in MODES_EXCLUSIFS):
            # Un paramètre à ``null`` est ABSENT (v0.7.2, revue passe 1) : il
            # hérite, en strict comme en tolérant. Avant, le tolérant le
            # retirait à l'entrée (donc héritait) mais le strict le gardait
            # jusqu'à la porte annuelle, qui le retirait APRÈS l'héritage : le
            # handler appliquait son défaut (défense 57 au lieu du réajusté),
            # sans signal.
            herites = {p: v for p, v in reference.items() if bloc.get(p) is None}
            if herites:
                # Un paramètre hérité est absent ou ``null`` dans ``bloc`` : on
                # n'y garde que les paramètres imposés.
                bloc = {**herites, **{p: v for p, v in bloc.items() if p not in herites}}
        effectif[levier] = bloc
    return effectif


def _aviser_reajustements_annules(programme: Dict, droit_vote: Dict, mesures_droit: Dict,
                                  atterrissage: Optional['Atterrissage'], debut: int,
                                  avis: Dict) -> None:
    """Avis « présent = imposé » (v0.7.2, revue passe 1) : un paramètre PRÉSENT
    qui vaut exactement le budget voté mais diffère du droit en vigueur réajusté
    est appliqué tel quel (``heriter_du_droit``) et annule donc le réajustement
    de l'atterrissage. Ce n'est pas une correction (l'entrée est lue telle
    quelle, ``report.valid`` inchangé) : un avis le dit, pour l'appelant qui
    recopiait le voté en croyant poser le statu quo. Une ligne par paramètre."""
    def texte(x) -> str:
        return f"{x:g}" if isinstance(x, (int, float)) and not isinstance(x, bool) else repr(x)

    for levier, bloc in programme.items():
        vote, reajuste = droit_vote.get(levier), mesures_droit.get(levier)
        if not (isinstance(bloc, dict) and isinstance(vote, dict) and isinstance(reajuste, dict)):
            continue
        for param, valeur in bloc.items():
            if (valeur is None or param not in vote or valeur != vote[param]
                    or reajuste.get(param) == valeur):
                continue
            annees = [an for an in sorted(atterrissage.annees) if an <= debut
                      and param in atterrissage.annees[an].reajustements.get(levier, {})
                      ] if atterrissage is not None else []
            origine = f"le réajustement {annees[-1]}" if annees else "le réajustement"
            avis.setdefault(
                ('cadre', 'impose', levier, param),
                f"{levier}.{param} : {texte(valeur)} imposé (budget voté), annule "
                f"{origine} ({texte(reajuste.get(param))})")


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
    simulation lit son cadre, elle ne le réécrit jamais.

    Release E (W1) : ``profils`` (validés, défaut de la recette exceptionnelle
    compris), ``origines`` (horloge de chaque levier modifié : première année
    où il s'écarte du droit en vigueur), ``mesures_par_annee`` (années du
    programme où un calendrier ou une valeur datée fait varier les mesures ;
    au-delà de la dernière clé, les mesures de la dernière) et
    ``droit_apres_debut`` (droit en vigueur des années postérieures au début
    où une valeur datée change)."""
    droit: DroitEnVigueur
    droit_vote: Dict
    mesures_droit: Dict
    droit_par_annee: Dict[int, Dict]
    leviers_modifies: FrozenSet[str]
    atterrissage: 'Atterrissage'
    rampe: Optional[Rampe] = None
    leviers_rampes: Tuple[str, ...] = ()
    leviers_ignores: Tuple[str, ...] = ()
    mesures_par_annee: Optional[Dict[int, Dict]] = None
    droit_apres_debut: Dict[int, Dict] = field(default_factory=dict)
    profils: Dict[str, Profil] = field(default_factory=dict)
    references: Dict[str, float] = field(default_factory=dict)
    origines: Dict[str, int] = field(default_factory=dict)

    def vote_de_l_annee(self, annee: int) -> Dict:
        """Budget voté de ``annee`` (valeurs datées comprises, réajustements de
        l'atterrissage non compris) : la référence « voté » de la
        décomposition des réajustements."""
        return droit_de_l_annee(self.droit_vote, None, annee, self.droit.valeurs_datees)


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
                 rampe=None, profils=None, strict: bool = False, warned: Optional[set] = None,
                 corrections: Optional[dict] = None,
                 avis: Optional[dict] = None) -> 'CadreTemporel':
        """``programme`` : mesures de l'appelant APRÈS la porte d'entrée
        (``assainir_mesures``). ``droit`` : injecté en test, sinon le fichier.
        ``rampe`` : demande de l'appelant (lot D), validée ici ; alias, depuis la
        release E, d'un profil « rampe » sur chaque levier listé. ``profils`` :
        calendriers de l'appelant (release E, W1), validés ici. ``avis`` : avis
        informatifs (``report.warnings`` sans toucher ``report.valid``)."""
        debut = normaliser_annee_debut(annee_debut, strict=strict, warned=warned,
                                       corrections=corrections)
        historique = debut is None or debut == POLICY_START_YEAR
        if not historique and rampe is not None and profils is not None and profils != {}:
            # Un seul calendrier par requête : ``profils`` (forme de la release
            # E) prime sur l'alias ``rampe``.
            message = ("profils : rampe et profils fournis ensemble — un seul calendrier par "
                       "requête, profils retenu, rampe ignorée")
            if strict:
                raise ProfilInvalide(f"{message} (mode BUDGETLAB_STRICT)")
            _signaler(warned, corrections, message, cle=('cadre', 'profils', 'rampe'))
            rampe = None
        rampe_effective = normaliser_rampe(rampe, mode_cadre=not historique, strict=strict,
                                           warned=warned, corrections=corrections,
                                           debut=None if historique else debut)
        if debut is None or debut == POLICY_START_YEAR:
            normaliser_profils(profils, mode_cadre=False, debut=POLICY_START_YEAR, strict=strict,
                               warned=warned, corrections=corrections)
            programme = _sans_recette_exceptionnelle(programme, strict=strict, warned=warned,
                                                     corrections=corrections)
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
        profils_valides = normaliser_profils(profils, mode_cadre=True, debut=debut, strict=strict,
                                             warned=warned, corrections=corrections)
        # Copie PAR SIMULATION (le droit injecté en test n'est jamais altéré).
        droit_vote = copy.deepcopy(droit.mesures)
        datees = droit.valeurs_datees
        droit_par_annee = {an: droit_de_l_annee(droit_vote, atterrissage, an, datees)
                           for an in range(POLICY_START_YEAR, debut)}
        # Droit en vigueur au début : réajustements et valeurs datées compris.
        mesures_droit = droit_de_l_annee(droit_vote, atterrissage, debut, datees)
        # Ensuite, le même, sauf aux années où une valeur datée change (une
        # mesure votée pour un an ne se reconduit pas, contrat § 5.3).
        droit_apres_debut, precedent = {}, mesures_droit
        for an in sorted({s.de for p in datees.values() for segs in p.values() for s in segs
                          if s.de > debut}):
            courant = droit_de_l_annee(droit_vote, atterrissage, an, datees)
            if courant != precedent:
                droit_apres_debut[an] = precedent = courant
        # Un bloc au neutre d'un levier absent du droit est un ``null``.
        programme = retirer_blocs_neutres(programme, mesures_droit)
        effectif = heriter_du_droit(programme, mesures_droit)
        if avis is not None:
            _aviser_reajustements_annules(programme, droit_de_l_annee(droit_vote, None, debut, datees),
                                          mesures_droit, atterrissage, debut, avis)
        modifies = frozenset(l for l in set(effectif) | set(mesures_droit)
                             if effectif.get(l) != mesures_droit.get(l))
        # Calendriers : l'alias ``rampe`` (v0.7.0) est un profil « rampe » de
        # durée ``annees`` sur chaque levier listé ; sinon les profils validés.
        # La recette exceptionnelle a toujours un profil « une seule année ».
        if rampe_effective is not None:
            demandes = {nom: Profil('rampe', annees=rampe_effective.annees)
                        for nom in rampe_effective.leviers}
        else:
            demandes = dict(profils_valides)
        en_vigueur = dict(demandes)
        en_vigueur.setdefault(CLE_RECETTE_EXCEPTIONNELLE, Profil('annee', annee=debut))
        cal = _mesures_profilees(programme, effectif, mesures_droit, droit_apres_debut, debut,
                                 en_vigueur)
        sans_effet = tuple(nom for nom in demandes if nom not in cal.actifs)
        if rampe_effective is not None:
            rampes = () if rampe_effective.annees == 1 else tuple(
                nom for nom in demandes if nom in cal.actifs)
            if sans_effet:
                # Demande sans effet, lue telle quelle : avis informatif, jamais
                # une correction (``report.valid`` inchangé).
                _signaler(warned, avis,
                          f"rampe : {_resume(list(sans_effet))} égal(s) au droit en vigueur dans "
                          f"le programme — rien à ramper, demande sans effet",
                          cle=('cadre', 'rampe', 'ignores'))
        else:
            rampes = ()
            if sans_effet:
                _signaler(warned, avis,
                          f"profils : {_resume(list(sans_effet))} égal(s) à la référence (droit en "
                          f"vigueur ou neutre) dans le programme — calendrier sans effet",
                          cle=('cadre', 'profils', 'sans_effet'))
        modifies = modifies | frozenset(cal.origines)
        origines = {l: cal.origines.get(l, debut) for l in modifies}
        return cls(annee_debut=debut, programme=effectif, etat=EtatCadre(
            droit=droit, droit_vote=droit_vote, mesures_droit=mesures_droit,
            droit_par_annee=droit_par_annee, leviers_modifies=modifies,
            atterrissage=atterrissage, rampe=rampe_effective, leviers_rampes=rampes,
            leviers_ignores=sans_effet if rampe_effective is not None else (),
            mesures_par_annee=cal.par_annee, droit_apres_debut=droit_apres_debut,
            profils={nom: p for nom, p in en_vigueur.items()
                     if nom in demandes or nom in cal.actifs},
            references=cal.references, origines=origines))

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
        if etat.mesures_par_annee:
            # Calendriers et valeurs datées (release E, W1) : au-delà de la
            # dernière année qui varie, les mesures restent celles-ci.
            return etat.mesures_par_annee[min(annee, max(etat.mesures_par_annee))]
        return self.programme

    def droit_en_vigueur_de(self, annee: int) -> Optional[Dict]:
        """Droit en vigueur de ``annee`` (mode cadre ; ``None`` en mode
        historique) : réajusté avant le début ; au début et ensuite, celui du
        début, sauf aux années où une valeur datée change (release E, W1). Lu
        par l'orchestrateur pour les mondes « droit » de la composition (le
        même objet chaque année sans valeur datée : sorties inchangées)."""
        etat = self.etat
        if etat is None:
            return None
        if annee < self.annee_debut:
            return etat.droit_par_annee.get(annee, etat.mesures_droit)
        ruptures = [an for an in etat.droit_apres_debut if an <= annee]
        return etat.droit_apres_debut[max(ruptures)] if ruptures else etat.mesures_droit

    def origines_de_l_annee(self, annee: int) -> Dict[str, int]:
        """Origine d'horloge de chaque levier MODIFIÉ par le programme, à partir
        de son origine (lot C ; release E, W1 : la première année ≥ début où le
        levier s'écarte du droit en vigueur, le début pour un levier modifié
        sans calendrier « une seule année ») ; ``{}`` avant le début (et en mode
        historique) : tous les leviers comptent alors depuis
        ``POLICY_START_YEAR``. Avant son origine, un levier garde l'horloge
        2026 dans les deux mondes de la composition, où ses valeurs sont
        égales : leur écart est nul. Lue par
        ``BudgetSimulatorV45._origine(levier)``."""
        if self.etat is None or annee < self.annee_debut:
            return {}
        return {levier: origine for levier, origine in self.etat.origines.items()
                if origine <= annee}

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

        def au_modele(entree, cle_ecart):
            # Valeur du modèle, valeur observée et leur écart (``None`` sans cible).
            ecart = (None if entree['observe'] is None
                     else round((entree['observe'] - entree['modele']) * 100, 4))
            return {'modele_pct': pct(entree['modele']), 'observe_pct': pct(entree['observe']),
                    cle_ecart: ecart}

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
                    'croissance': au_modele(j['croissance'], 'choc_pt'),
                    'deflateur': au_modele(j['deflateur'], 'ecart_pt'),
                    'ipc': {'deflateur_pct': pct(ipc['deflateur']), 'observe_pct': pct(ipc['observe']),
                            'coin_pt': pct(ipc['coin'])},
                    'chomage': au_modele(j['chomage'], 'ecart_pt'),
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

    def rapport_profils(self) -> Dict:
        """Bloc ``cadre.profils`` (release E, W1, contrat § 2.1) : pour chaque
        calendrier en vigueur, ``forme`` (``annee`` pour la forme « annee »,
        ``annees`` pour une rampe de durée explicite), ``origine`` (horloge du
        LEVIER : première année où il s'écarte du droit en vigueur ; ``null``
        s'il ne s'en écarte jamais) et ``valeurs`` (valeur appliquée chaque
        année du mandat, du début à ``ANNEE_FIN_MANDAT``). TOUJOURS émis :
        ``{}`` sans calendrier, et en mode historique (signature de contrat
        de la release E, § 5.1). Alias ``rampe`` compris."""
        etat = self.etat
        if etat is None:
            return {}
        out = {}
        for nom in sorted(etat.profils):
            levier, param = nom.split('.')
            reference = etat.references.get(nom)
            valeurs = {}
            for an in range(self.annee_debut, ANNEE_FIN_MANDAT + 1):
                bloc = self.mesures_de_l_annee(an).get(levier)
                valeur = bloc.get(param) if isinstance(bloc, dict) else None
                valeurs[str(an)] = reference if valeur is None else valeur
            out[nom] = {**etat.profils[nom].publier(), 'origine': etat.origines.get(levier),
                        'valeurs': valeurs}
        return out

    def rapport(self, journal_atterrissage: Optional[Dict] = None,
                annees_plafond_total=(), impact_max: Optional[Tuple[int, float]] = None,
                filet_croissance=()) -> Dict:
        """Bloc ``cadre`` de la réponse. ``mesures_effectives`` (mode cadre) :
        les mesures appliquées à partir du début, rampe achevée — le droit en
        vigueur RÉAJUSTÉ et, par-dessus, le programme ; pour le statu quo, le
        droit en vigueur réajusté lui-même. ``plafond_total`` : le plafond de
        l'impact total des mesures (``constants.PLAFOND_IMPACT_TOTAL_PIB``,
        inchangé), sur les écarts au DÉFAUT du moteur, le mode
        (``constants.PLAFOND_TOTAL_MODE`` : ``reduction`` ou ``avertissement``,
        signature de contrat de la release E), les années où il est dépassé,
        l'impact maximal mesuré (avant toute réduction, % du PIB) et son année
        — ``null`` si le seuil n'est jamais dépassé. ``filet_croissance`` : le
        filet de la croissance réelle annuelle (``constants.CROISSANCE_FILET_MIN``
        et ``CROISSANCE_FILET_MAX``, en %), les années où il mord et, pour
        chacune, la croissance calculée et la croissance retenue (en %, 4
        décimales) ; même journal que l'avis texte de ``report.warnings``,
        listes vides si le filet ne mord pas (``bloc_filet_croissance``).
        ``profils`` : calendriers (``rapport_profils``)."""
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
                              'mode': PLAFOND_TOTAL_MODE,
                              'annees': list(annees_plafond_total),
                              'impact_max_pct_pib': (None if impact_max is None
                                                     else round(impact_max[1], 4)),
                              'annee_impact_max': None if impact_max is None else impact_max[0]},
            'filet_croissance': bloc_filet_croissance(filet_croissance),
            'profils': self.rapport_profils(),
        }


def bloc_filet_croissance(ecretages=()) -> Dict:
    """Bloc ``cadre.filet_croissance`` (release E) : la même information que
    l'avis du filet de croissance (``report.warnings``), sans phrase à analyser.
    ``ecretages`` : journal ``(annee, croissance calculée, croissance retenue)``
    du moteur (fractions), dans l'ordre des années ; publié en %."""
    lignes = [{'annee': int(annee),
               'croissance_calculee_pct': round(float(calculee) * 100, 4),
               'croissance_retenue_pct': round(float(retenue) * 100, 6)}
              for annee, calculee, retenue in ecretages]
    return {'borne_min_pct': round(CROISSANCE_FILET_MIN * 100, 6),
            'borne_max_pct': round(CROISSANCE_FILET_MAX * 100, 6),
            'annees': [ligne['annee'] for ligne in lignes],
            'ecretages': lignes}


@dataclass(frozen=True)
class Calendrier:
    """Résultat de ``_mesures_profilees``."""
    actifs: Tuple[str, ...]
    par_annee: Optional[Dict[int, Dict]]
    references: Dict[str, float]
    origines: Dict[str, int]


def reference_du_profil(levier: str, param: str, droit: Dict):
    """Référence ``p_ref`` d'un paramètre profilé (contrat § 2.1) : sa valeur
    dans le droit en vigueur ``droit`` (celui de l'année calculée, le droit du
    début pour la référence publiée) ; à défaut, son neutre
    (``NEUTRES_RELEASE_E``) ; à défaut, le défaut du moteur
    (``config.load_default_values``) ; pour la clé dominante d'un mode exclusif
    en Md€ (``rendement_*``, dont le neutre est l'ABSENCE de la clé), 0 :
    un rendement nul est la recette du neutre [INTERPRÉTATION : au neutre,
    ΔR = 0 dans les deux modes]. ``None`` si aucune n'existe.

    Budget chômage en MONTANT (contre-vérification m2) : le droit l'écrit en
    TAUX de remplacement ; la référence est alors le montant équivalent à ce
    taux, par la formule du handler (``MONTANT_REF × (taux / TAUX_REF)``,
    ``_apply_chomage_alloc``), jamais le défaut du moteur — 36,6 exactement au
    droit livré (taux de référence)."""
    bloc = droit.get(levier)
    if isinstance(bloc, dict) and param in bloc:
        return bloc[param]
    if ((levier, param) == ('chomage_alloc', 'montant') and isinstance(bloc, dict)
            and _nombre(bloc.get('taux_remplacement'))):
        return CHOMAGE_MONTANT_REF_MD * (bloc['taux_remplacement'] / CHOMAGE_TAUX_REF)
    if param in NEUTRES_RELEASE_E.get(levier, {}):
        return NEUTRES_RELEASE_E[levier][param]
    from ..config import load_default_values
    defauts = load_default_values().get(levier) or {}
    if param in defauts:
        return defauts[param]
    if param in MODES_EXCLUSIFS.get(levier, {}):
        return 0.0
    return None


def valeur_du_profil(profil: Profil, p_ref, p, annee: int, debut: int):
    """Valeur appliquée en ``annee`` ≥ ``debut`` (contrat § 2.1) :
    - ``plein`` : ``p`` ;
    - ``rampe`` : ``n`` = ``annees`` (alias v0.7.0) ou ``ANNEE_FIN_MANDAT −
      début + 1`` ; année ``a`` de rang ``k = a − début + 1 < n`` :
      ``p_ref + (p − p_ref) × k / n`` (arithmétique de la rampe v0.7.0) ;
      ensuite la valeur EXACTE ``p``, jamais ``p_ref + (p − p_ref) × 1`` ;
    - ``annee`` : ``p`` l'année choisie, ``p_ref`` toutes les autres ;
    - ``valeurs`` : le montant écrit pour l'année, ``p`` après la dernière."""
    if profil.forme == 'plein':
        return p
    if profil.forme == 'annee':
        return p if annee == profil.annee else p_ref
    if profil.forme == 'valeurs':
        return dict(profil.valeurs).get(annee, p)
    n = profil.annees if profil.annees is not None else ANNEE_FIN_MANDAT - debut + 1
    k = annee - debut + 1
    return p if k >= n else p_ref + (p - p_ref) * k / n


def _derniere_annee_variable(profil: Profil, debut: int) -> int:
    """Dernière année où le profil s'écarte de son régime final."""
    if profil.forme == 'annee':
        return profil.annee + 1
    if profil.forme == 'valeurs':
        return profil.valeurs[-1][0] + 1
    if profil.forme == 'rampe':
        n = profil.annees if profil.annees is not None else ANNEE_FIN_MANDAT - debut + 1
        return debut + n - 1
    return debut


def _ecart_au_droit(levier: str, bloc, droit: Dict) -> bool:
    """Le bloc de l'année s'écarte-t-il du droit en vigueur de l'année ? Levier
    inscrit au droit : comparaison des blocs ; levier absent du droit :
    paramètre par paramètre, contre la référence (neutre, défaut ; un
    paramètre sans référence connue est un écart)."""
    if not isinstance(bloc, dict):
        return False
    reference = droit.get(levier)
    if isinstance(reference, dict):
        return bloc != reference
    for param, valeur in bloc.items():
        if valeur is None:
            continue
        ref = reference_du_profil(levier, param, {})
        if ref is None or valeur != ref:
            return True
    return False


def _mesures_profilees(programme: Dict, effectif: Dict, droit: Dict,
                       droit_apres_debut: Dict[int, Dict], debut: int,
                       profils: Dict[str, Profil]) -> Calendrier:
    """Calendriers (release E, W1, contrat § 2.1) : remplace ``_mesures_rampees``
    (v0.7.0), dont la rampe est un cas particulier au bit.

    ``programme`` : programme de l'appelant (blocs au neutre retirés) ;
    ``effectif`` : le même par-dessus le droit en vigueur au début (``droit``).
    Un profil a un EFFET si son paramètre est posé (non ``null``) dans le
    programme, numérique, et différent de sa référence d'au moins une année.
    La référence d'une année est le droit en vigueur DE CETTE ANNÉE (revue
    adverse de la release E) : une valeur datée qui change après le début
    change la référence du calendrier cette année-là (« une seule année » :
    le droit de l'année les autres années ; « rampe » : interpolation entre le
    droit de l'année et la cible). Rend les profils actifs, les mesures des
    années qui varient (``None`` si aucune : le programme chaque année, comme
    avant), les références (au début, publiées) et les ORIGINES d'horloge qui
    ne sont pas le début (leviers à calendrier « une seule année », et
    leviers dont le droit change après le début)."""
    def droit_de(an: int) -> Dict:
        ruptures = [r for r in droit_apres_debut if r <= an]
        return droit_apres_debut[max(ruptures)] if ruptures else droit

    actifs, references = {}, {}
    for nom in sorted(profils):
        levier, param = nom.split('.')
        bloc = programme.get(levier)
        p = bloc.get(param) if isinstance(bloc, dict) else None
        p_ref = reference_du_profil(levier, param, droit)
        if p_ref is not None:
            references[nom] = p_ref
        refs = [p_ref] + [reference_du_profil(levier, param, d) for _, d in sorted(droit_apres_debut.items())]
        if _nombre(p) and all(_nombre(r) for r in refs) and any(p != r for r in refs):
            actifs[nom] = (levier, param, p_ref, p, profils[nom])
    # Dernière année qui varie : au-delà, les mesures de cette année valent pour
    # toutes les suivantes. Aucune (profils « plein », rampe d'un an, pas de
    # valeur datée après le début) : le programme chaque année, comme avant.
    variables = [an for an in ([_derniere_annee_variable(prof, debut)
                                for *_, prof in actifs.values()] + list(droit_apres_debut))
                 if an > debut]
    if not variables:
        return Calendrier(actifs=tuple(actifs), par_annee=None, references=references,
                          origines={})
    derniere = max(variables)
    par_annee = {}
    for an in range(debut, derniere + 1):
        droit_an = droit_de(an)
        blocs = {}
        for levier, param, p_ref, p, profil in actifs.values():
            # Référence de l'année : le droit de CETTE année (le même objet que
            # ``droit`` sans valeur datée après le début : sorties inchangées).
            p_ref_an = p_ref if droit_an is droit else reference_du_profil(levier, param, droit_an)
            valeur = valeur_du_profil(profil, p_ref_an, p, an, debut)
            if valeur != p:
                blocs.setdefault(levier, dict(programme[levier]))[param] = valeur
        if not blocs and droit_an is droit:
            par_annee[an] = effectif
        else:
            par_annee[an] = heriter_du_droit({**programme, **blocs}, droit_an)
    # Origine d'horloge : première année où le levier s'écarte du droit de
    # l'année, pour les leviers qu'un calendrier « une seule année » ou une
    # valeur datée peut retarder ; les autres leviers modifiés partent au début.
    # Forme « valeurs » : un premier montant égal à la référence retarde l'origine.
    a_dater = {levier for levier, _, _, _, profil in actifs.values()
               if profil.forme in ('annee', 'valeurs')}
    if droit_apres_debut:
        a_dater |= set(programme)
    origines = {}
    for levier in sorted(a_dater):
        for an in range(debut, derniere + 1):
            if _ecart_au_droit(levier, par_annee[an].get(levier), droit_de(an)):
                origines[levier] = an
                break
    return Calendrier(actifs=tuple(actifs), par_annee=par_annee, references=references,
                      origines=origines)


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
    contenu = _lire_objet_json(ATTERRISSAGE_PATH, _defaut_atterrissage)
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


def _segment_de(segments: Tuple[Segment, ...], annee: int) -> int:
    """Rang du segment qui contient ``annee`` (avant 2026 : le premier)."""
    for i, segment in enumerate(segments):
        if segment.contient(annee):
            return i
    return 0


def droit_de_l_annee(droit: Dict, atterrissage: Optional[Atterrissage], annee: int,
                     valeurs_datees: Optional[Dict] = None) -> Dict:
    """Droit en vigueur de ``annee`` (contrat de la release E, § 5.3) : le droit
    voté, où chaque paramètre DATÉ prend la valeur du segment qui contient
    ``annee`` ; puis les réajustements des années observées ≤ ``annee`` (ils
    le suivent ensuite : droit constant), fusion PARAMÈTRE par paramètre (un
    réajustement ne porte que ce qui a dérapé). Un réajustement de l'année
    ``y`` sur un paramètre daté ne vaut que dans le segment de ``y`` : une
    mesure votée pour un an ne se reconduit pas, même réajustée. Sans valeur
    datée : exactement le droit réajusté v0.7.2 (même objet si rien ne
    change) ; résultat validé au chargement."""
    out = None
    for levier, params in (valeurs_datees or {}).items():
        for param, segments in params.items():
            out = dict(droit) if out is None else out
            out[levier] = {**out[levier], param: segments[_segment_de(segments, annee)].valeur}
    if atterrissage is None:
        return droit if out is None else out
    for an in sorted(atterrissage.annees):
        if an > annee:
            break
        for levier, params in atterrissage.annees[an].reajustements.items():
            dates = (valeurs_datees or {}).get(levier, {})
            retenus = {p: v for p, v in params.items()
                       if p not in dates or _segment_de(dates[p], an) == _segment_de(dates[p], annee)}
            if not retenus:
                continue
            out = dict(droit) if out is None else out
            out[levier] = {**out[levier], **retenus}
    return droit if out is None else out


def droit_reajuste(droit: Dict, atterrissage: Optional[Atterrissage], annee: int) -> Dict:
    """Droit en vigueur de ``annee`` SANS valeur datée (v0.7.0 à v0.7.2) :
    ``droit_de_l_annee`` sans son quatrième argument. Conservé pour les
    lecteurs existants ; le moteur appelle ``droit_de_l_annee``."""
    return droit_de_l_annee(droit, atterrissage, annee)


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
