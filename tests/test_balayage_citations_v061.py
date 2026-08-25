"""Balayage de citations v0.6.1 — ce qui est banni, et ce qui reste en dette.

Ce dépôt est PUBLIC et un audit citoyen y a déjà relevé des citations fausses.
Chaque lot de la v0.6.1 a posé ses propres méta-gardes, chacune scopée à son
périmètre. Ce fichier ferme les deux angles morts que ce découpage laisse :

1. UNE ATTRIBUTION À UN ORGANISME INEXISTANT EST FAUSSE PARTOUT. Le lot 5 avait
   scopé sa garde « HCFPS » au seul bloc ASU, au motif que l'acronyme « reste
   cité ailleurs pour des affirmations que ce lot n'a pas auditées ». Le
   raisonnement vaut pour un chiffre non audité — il ne vaut pas ici : le
   dossier de sourcing établit que **« HCFPS » ne désigne aucun organisme**
   (les acronymes réels voisins sont HCFiPS, Haut Conseil du financement de la
   protection sociale, et HCFEA). Ce n'est pas une question de calibration,
   c'est une question de fait, et elle se tranche à l'échelle du dépôt.

2. LA DETTE D'AUDIT DOIT ÊTRE VISIBLE EN CI, PAS SEULEMENT DANS UN RAPPORT.
   Deux citations signalées au balayage n'ont **pas** été auditées par le
   dossier : les bannir « au passage » serait la faute symétrique de celle
   qu'on corrige. Elles sont donc CONSERVÉES, mais inventoriées ici, à
   l'emplacement exact où elles vivent. La carte rougit si l'une disparaît
   sans que l'inventaire suive, ou si une nouvelle apparaît ailleurs.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# `docs/backlog.md` est gitignoré (état de travail local, hors dépôt public) :
# il ne fait pas partie de ce qu'un auditeur externe peut lire.
_DOCS_EXCLUS = {'backlog.md'}
# Ce fichier et celui du lot 5 CITENT les motifs pour les interdire.
_TESTS_EXCLUS = {'test_balayage_citations_v061.py', 'test_asu_v061.py'}


def _fichiers_publies():
    fichiers = sorted((ROOT / 'budget_simulator').rglob('*.py'))
    fichiers += [d for d in sorted((ROOT / 'docs').glob('*.md'))
                 if d.name not in _DOCS_EXCLUS]
    manifeste = ROOT / 'policy_measures.json'
    if manifeste.exists():
        fichiers.append(manifeste)
    return fichiers


# --------------------------------------------------------------------------
# 1. Organisme inexistant : banni à l'échelle du dépôt
# --------------------------------------------------------------------------

_MOTIF_HCFPS = re.compile(r"HCFPS")


def test_aucune_attribution_a_un_organisme_inexistant():
    """« HCFPS » ne désigne aucun organisme — retiré, jamais réécrit.

    Le remplacement N'EST PAS une simple correction d'orthographe vers
    « HCFiPS » : le dossier de sourcing a vérifié que ni le HCFiPS ni le HCFEA
    ne publient les chiffres qui lui étaient attribués. Re-sourcer par
    approximation, ici, reviendrait à fabriquer une source."""
    fautifs = [str(f.relative_to(ROOT)) for f in _fichiers_publies()
               if _MOTIF_HCFPS.search(f.read_text(encoding='utf-8'))]
    assert not fautifs, (
        f"attribution à « HCFPS » (organisme inexistant) encore présente dans : {fautifs}")


# Lignes EXACTES de l'état d'avant, recopiées telles quelles — cible de la
# contre-épreuve. On ne relit PAS `git show HEAD` : après le commit de ce
# balayage, HEAD porterait le texte corrigé et la contre-épreuve serait
# vacuelle (défaut réel constaté et corrigé au lot 6).
_TEXTE_FAUTIF_AVANT = (
    "- HCFPS 2024, CNAF 2023, Cour des comptes 2025 - fraude sociale.\n"
    "        Sources: HCFPS 2024, Cour comptes 2025.\n"
    "        # Justification : CNAF 2023, HCFPS 2024, Plan antifraude 2023-2027\n"
)


def test_contre_epreuve_le_motif_attrape_bien_le_texte_d_avant():
    """Une garde de citation peut être verte parce qu'elle cherche mal."""
    assert _MOTIF_HCFPS.search(_TEXTE_FAUTIF_AVANT)


# --------------------------------------------------------------------------
# 2. Carte de la dette d'audit : ce qui survit, et où, DÉLIBÉRÉMENT
# --------------------------------------------------------------------------

#: motif -> (emplacements attendus, pourquoi il survit).
#: Toute entrée de cette carte est une DETTE : une affirmation que le dossier
#: de sourcing v0.6.1 n'a pas auditée, laissée en place parce que la retirer
#: sans l'avoir vérifiée serait aussi arbitraire que l'avoir écrite.
_DETTE_D_AUDIT = {
    r"IGAS 2023": (
        {'docs/METHODOLOGIE.md'},
        "porte trois affirmations HORS périmètre du lot prévention : "
        "convergence tarifaire hôpital, achats groupés, et plafond de fraude "
        "sociale recouvrable. Le lot 4 a délibérément scopé sa garde au bloc "
        "prévention pour ne pas les bannir sans les avoir vérifiées",
    ),
    r"France Strat[ée]gie 2024": (
        {'budget_simulator/handlers/competitivite.py'},
        "le dossier ne l'a réfutée que pour l'effet EMPLOI de la prime "
        "d'activité (bloc ASU, retiré au lot 5). Son usage ici — impôts de "
        "production, coût du travail — n'a JAMAIS été audité",
    ),
}


@pytest.mark.parametrize("motif", sorted(_DETTE_D_AUDIT))
def test_carte_de_la_dette_d_audit(motif):
    """L'inventaire des citations non auditées est EXACT.

    Ni plus (une nouvelle occurrence ailleurs = une dette non déclarée), ni
    moins (une disparition = soit un audit fait sans mettre à jour la carte,
    soit un bannissement au passage, les deux devant se voir)."""
    attendus, raison = _DETTE_D_AUDIT[motif]
    compile_ = re.compile(motif)
    trouves = {str(f.relative_to(ROOT)) for f in _fichiers_publies()
               if compile_.search(f.read_text(encoding='utf-8'))}
    assert trouves == attendus, (
        f"carte de dette d'audit périmée pour {motif!r} — attendu {sorted(attendus)}, "
        f"trouvé {sorted(trouves)}. Raison de la dette : {raison}")


def test_la_carte_n_est_pas_vide():
    """Garde de la garde : une carte vidée passerait tous les tests ci-dessus
    sans rien mesurer. Tant qu'une dette existe, elle doit être nommée."""
    assert _DETTE_D_AUDIT, "la carte de dette d'audit ne doit pas être vidée en silence"


# --------------------------------------------------------------------------
# 3. Un locator ajouté AU-DELÀ de ce que la collecte a établi
# --------------------------------------------------------------------------

#: Motifs bannis sur la SEULE valeur maison du chantier (la bosse de chômage
#: +0,18 pt). Le §B.1-8 du dossier exige qu'elle soit publiée avec ses trois
#: routes ; il n'établit NI la note 122 de la Cour de février 2025 (les notes
#: qu'il cite pour ce rapport sont 121 et 125), NI une base « cohorte annuelle
#: ~800 000 ». Cette base ne reconstitue d'ailleurs pas le résultat publié
#: (+0,13 pt) : appliquée à la formule des deux autres routes elle donne
#: +0,47 pt. C'est exactement le mode de défaillance de la séance du COR datée
#: d'un jour où elle n'a pas eu lieu, que le lot 1 a retirée (cf.
#: `test_meta_garde_aucune_seance_du_cor_a_une_date_inexistante`) — un locator
#: précis ajouté au-delà de la collecte, sur un dépôt public.
_LOCATORS_NON_ETABLIS = {
    r"note\s*n?°?\s*122": "la Cour de février 2025 n'est citée par le dossier "
                          "que pour ses notes 121 et 125",
    r"cohorte annuelle": "aucune base « cohorte annuelle » n'est établie par la "
                         "collecte, et elle ne reconstitue pas le +0,13 pt publié",
    # Lot 7 — un locator PRÉCIS mais FAUX est pire qu'un locator absent : il
    # se vérifie, et il ne se vérifie pas. Le dossier (§ I8) place le verbatim
    # sur les recherches micro-économétriques au CORPS de la page 67 ; la
    # note 121 porte les chiffres des deux modèles désavoués (+0,7 pt Mésange,
    # +0,5 pt e-mod.fr). Le motif attrape la seule construction fautive :
    # « note 121 » suivie, avant la fin de la phrase, du verbatim.
    r"note\s*n?°?\s*121\s*:\s*«?\s*(?:les|Les)\s+recherches":
        "le verbatim sur les recherches micro-économétriques est au corps de "
        "la p. 67 ; la note 121 porte les chiffres Mésange / e-mod.fr",
}


@pytest.mark.parametrize("motif", sorted(_LOCATORS_NON_ETABLIS))
def test_aucun_locator_ajoute_au_dela_de_la_collecte(motif):
    """Ce que la collecte n'a pas établi n'est pas publié comme une source.

    Règle du dossier (§B) : quand un point est INTROUVABLE ou NON ÉTABLI, on
    RETIRE — on ne re-source pas par approximation. Une valeur maison reste
    publiable ; sa localisation dans un document ne l'est que si elle a été lue.
    """
    regex = re.compile(motif)
    fautifs = [f"{f.relative_to(ROOT)}:{i}"
               for f in _fichiers_publies()
               for i, ligne in enumerate(f.read_text(encoding='utf-8').splitlines(), 1)
               if regex.search(ligne)]
    assert not fautifs, (
        f"locator non établi « {motif} » ({_LOCATORS_NON_ETABLIS[motif]}) : "
        f"{fautifs}")


#: Lignes EXACTES d'avant le lot 7, recopiées telles quelles (même raison qu'au
#: § 1 : après le commit, `git show HEAD` porterait le texte corrigé et la
#: contre-épreuve serait vacuelle). Une garde de citation peut être verte
#: parce qu'elle cherche mal — c'est le mode de défaillance le plus courant
#: de ce fichier, et il se ferme motif par motif.
_TEXTE_FAUTIF_NOTE_121 = (
    "# explicitement (février 2025, p. 67, note 121 : « les recherches\n"
    "(fevrier 2025, p. 67, note 121 : « les recherches micro-econometriques menees\n"
)


def test_contre_epreuve_le_motif_note_121_attrape_bien_le_texte_d_avant():
    """Le motif du lot 7 attrape les DEUX rédactions d'avant (code et doc)."""
    regex = re.compile(
        next(m for m in _LOCATORS_NON_ETABLIS if '121' in m))
    attrapees = [l for l in _TEXTE_FAUTIF_NOTE_121.splitlines() if regex.search(l)]
    assert len(attrapees) == 2, (
        f"le motif n'attrape que {len(attrapees)} des deux lignes fautives")


def test_le_desaveu_et_ses_chiffres_restent_cites_apres_recalage():
    """Recaler n'est pas retirer : les deux localisations restent PUBLIÉES.

    Le § B du dossier impose de retirer ce qui est introuvable ; ici rien
    n'est introuvable — la note 121 existe et le verbatim aussi, ils ne sont
    simplement pas au même endroit. Supprimer l'un des deux « pour être sûr »
    appauvrirait la traçabilité sans rien corriger."""
    textes = {f: f.read_text(encoding='utf-8') for f in _fichiers_publies()}
    porteurs = [str(f.relative_to(ROOT)) for f, t in textes.items()
                if 'note 121' in t]
    assert porteurs, "la note 121 (chiffres Mésange / e-mod.fr) a disparu"
    verbatim = [str(f.relative_to(ROOT)) for f, t in textes.items()
                if re.search(r'recherches micro-[ée]conom[ée]triques', t)]
    assert verbatim, "le verbatim du désaveu de la Cour a disparu"
