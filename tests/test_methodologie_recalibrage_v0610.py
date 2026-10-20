"""V2-06 (contre-audit externe du 07/10/2026 sur v0.6.7, corrigé en v0.6.10) —
un seul état du recalibrage des multiplicateurs dans la doc publique, et une
portée défendable pour le garde-fou d'autofinancement.

Deux défauts de documentation, sans effet sur les sorties du moteur :

1. DEUX ÉTATS INCOMPATIBLES DU RECALIBRAGE. `docs/METHODOLOGIE.md` gardait un
   paragraphe « Multiplicateur cumulé = k × Σ profil » aux coefficients de la
   v0.6.6 (2,38 pour l'investissement = 1,2 × 1,98) et présentait le recalage du
   profil INVEST comme une question encore ouverte, alors que le paragraphe
   suivant décrit le recalibrage RÉALISÉ en v0.6.7, mesuré dans le moteur
   complet. Il confondait aussi la somme analytique `k × Σ profil` (aucune autre
   équation ne réagit) avec l'effet effectif (rappel vers le potentiel, Phillips,
   Okun, dette). Contrat : la somme analytique n'apparaît que qualifiée comme
   telle et datée (v0.6.6), jamais comme l'effet courant.

2. PORTÉE TROP GÉNÉRALE. Le garde-fou de `tests/test_multiplicateurs_centraux_v067.py`
   vérifie UN choc synthétique permanent de 1 % du PIB sur le levier éducation,
   en configuration de référence ; il ne démontre rien sur tous les
   investissements, intensités, combinaisons et états macroéconomiques. La
   formulation universelle (« aucun investissement ne s'autofinance ») est donc
   bannie du dépôt publié ; METHODOLOGIE énonce la portée restreinte et distingue
   autofinancement budgétaire, dette nominale et ratio dette/PIB (un PIB plus
   haut peut faire baisser le ratio sans rembourser le coût).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
METHODO = ROOT / 'docs' / 'METHODOLOGIE.md'

# Ce fichier CITE les motifs bannis pour les interdire.
_TESTS_EXCLUS = {Path(__file__).name}
_DOCS_EXCLUS = {'backlog.md'}   # gitignoré, hors dépôt public


def _normalise(texte: str) -> str:
    """Espaces et retours à la ligne repliés : la doc est coupée à ~100 colonnes."""
    return ' '.join(texte.split())


def _paragraphes(texte: str) -> list[str]:
    return [_normalise(p) for p in re.split(r'\n\s*\n', texte) if p.strip()]


def _fichiers_publies() -> list[Path]:
    fichiers = sorted((ROOT / 'budget_simulator').rglob('*.py'))
    fichiers += sorted(t for t in (ROOT / 'tests').rglob('*.py') if t.name not in _TESTS_EXCLUS)
    fichiers += [d for d in sorted((ROOT / 'docs').glob('*.md')) if d.name not in _DOCS_EXCLUS]
    fichiers += [ROOT / nom for nom in ('README.md', 'CONTRIBUTING.md', 'CHANGELOG.md')
                 if (ROOT / nom).exists()]
    return fichiers


# --------------------------------------------------------------------------
# 1. Un seul état du recalibrage
# --------------------------------------------------------------------------

_MOTIF_ARBITRAGE_OUVERT = re.compile(r'arbitrage\s+(de\s+calibration\s+)?ouvert', re.IGNORECASE)


def test_recalage_invest_n_est_plus_presente_comme_ouvert():
    """Le recalibrage v0.6.7 est réalisé (INVEST conservé à k = 1,2 : 1,41 mesuré
    pour une cible centrale de 1,5) : plus aucun « arbitrage ouvert »."""
    texte = _normalise(METHODO.read_text(encoding='utf-8'))
    occurrences = [m.group(0) for m in _MOTIF_ARBITRAGE_OUVERT.finditer(texte)]
    assert not occurrences, f'METHODOLOGIE présente encore un arbitrage ouvert : {occurrences}'


def test_somme_analytique_jamais_presentee_comme_effet_courant():
    """Tout paragraphe qui cite 2,38 (= 1,2 × 1,98, somme analytique k × Σ profil
    de l'investissement) la qualifie d'analytique ET la date (v0.6.6)."""
    fautifs = [p[:160] for p in _paragraphes(METHODO.read_text(encoding='utf-8'))
               if '2,38' in p and not ('analytique' in p and 'v0.6.6' in p)]
    assert not fautifs, f'2,38 cité sans « analytique » ni « v0.6.6 » : {fautifs}'


# --------------------------------------------------------------------------
# 2. Portée du garde-fou d'autofinancement
# --------------------------------------------------------------------------

_MOTIFS_UNIVERSELS = (
    re.compile(r"aucun\s+investissement\s+ne\s+s['’]\s*autofinance", re.IGNORECASE),
    re.compile(r"l['’]\s*investissement\s+ne\s+s['’]\s*autofinance", re.IGNORECASE),
    re.compile(r'aucun_investissement_ne_s_autofinance'),
)


def test_autofinancement_jamais_enonce_universellement():
    """Le test vérifie un choc ; la doc, les commentaires et les noms de tests
    ne l'énoncent jamais comme une loi sur tous les investissements."""
    fautes = []
    for f in _fichiers_publies():
        texte = _normalise(f.read_text(encoding='utf-8'))
        for motif in _MOTIFS_UNIVERSELS:
            fautes += [f'{f.relative_to(ROOT)} : {m.group(0)}' for m in motif.finditer(texte)]
    assert not fautes, 'formulation universelle de l\'autofinancement :\n' + '\n'.join(fautes)


def test_portee_restreinte_et_trois_notions_dans_methodologie():
    """METHODOLOGIE énonce la portée défendable et, dans le même paragraphe,
    distingue les trois notions que le contre-audit demande de séparer."""
    porteurs = [p for p in _paragraphes(METHODO.read_text(encoding='utf-8'))
                if "ne s'autofinance pas dans le banc de référence" in p]
    assert porteurs, 'portée restreinte absente de METHODOLOGIE'
    for p in porteurs:
        for notion in ('budgétaire', 'dette nominale', 'ratio dette/PIB'):
            assert notion in p, f'notion « {notion} » absente du paragraphe : {p[:160]}'
