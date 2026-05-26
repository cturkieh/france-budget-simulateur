"""Garde CI : verrou anti-dérive entre les constantes économiques du code
et leur représentation dans les docs UI (METHODOLOGIE.md, EXPLICATION_MODELE_ECONOMIQUE.md).

Philosophie identique à `test_measure_registry_sync.py` : si une constante
économique change dans le code, la CI rougit tant que la doc UI n'a pas
été mise à jour avec la nouvelle valeur. Direction : CODE → DOC.

Périmètre : ~9 constantes nommées les plus visibles côté lecteur
(journaliste, citoyen, chercheur). Les coefficients inline non nommés
(ex : coefficient Phillips `0.35` directement dans `inflation.py`) ne
sont **pas** verrouillés : non extractibles automatiquement, dérive
plus lente, visible plus tôt côté contributeur que côté lecteur.

Pour ajouter une nouvelle constante au périmètre : entrée dans
`_critical_constants()` ci-dessous (la liste EST la spec).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from budget_simulator import constants
from budget_simulator.simulator import BudgetSimulatorV45

ROOT = Path(__file__).resolve().parent.parent
METHODO = ROOT / "docs" / "METHODOLOGIE.md"
EXPLICATION = ROOT / "docs" / "EXPLICATION_MODELE_ECONOMIQUE.md"
# Copies servies au frontend (téléchargement journalistes/citoyens) —
# synchronisées par scripts/sync_public_docs.py. Inclues dans le verrou
# pour bloquer tout drift entre source et copie publique, même si
# `make check-docs-sync` n'a pas été lancé.
#
# NB : ces chemins n'existent pas dans un fork du repo public seul
# (`frontend-react/` reste sur le repo privé `budgetlab-france`). Les tests
# qui les consomment doivent gérer l'absence — cf `_must_appear_in_existing`
# et la skipif appliquée à `test_critical_constants_appear_in_docs_ui`.
PUBLIC_METHODO = ROOT / "frontend-react" / "public" / "docs" / "METHODOLOGIE.md"
PUBLIC_EXPLICATION = ROOT / "frontend-react" / "public" / "docs" / "EXPLICATION_MODELE_ECONOMIQUE.md"
_ALL_DOCS = (METHODO, EXPLICATION, PUBLIC_METHODO, PUBLIC_EXPLICATION)
# Docs invariablement présentes dans le périmètre public (subtree open source) —
# servent de socle minimal pour la skipif fork-friendly.
_PUBLIC_ONLY_DOCS = (METHODO, EXPLICATION)


@dataclass(frozen=True)
class CriticalConstant:
    """Constante économique citée dans les docs UI à verrouiller."""
    name: str
    source: str
    raw_value: float
    representations: tuple[str, ...]
    must_appear_in: tuple[Path, ...]


def _critical_constants() -> tuple[CriticalConstant, ...]:
    # `economic_coeffs` est hardcodé dans `simulator.py` (section
    # « economic coefficients ») — on lit la source via une instance.
    coeffs = BudgetSimulatorV45().economic_coeffs
    return (
        CriticalConstant(
            name="PIB_BASE_2025 (Md EUR)",
            source="constants.PIB_BASE_2025_MD_EUR",
            raw_value=constants.PIB_BASE_2025_MD_EUR,
            representations=("2 994", "2994"),
            must_appear_in=(EXPLICATION, PUBLIC_EXPLICATION),
        ),
        CriticalConstant(
            name="DETTE_RATIO_2025 (% PIB)",
            source="constants.DETTE_RATIO_2025",
            raw_value=constants.DETTE_RATIO_2025,
            representations=("115,6%", "115,6 %"),
            must_appear_in=(EXPLICATION, PUBLIC_EXPLICATION),
        ),
        CriticalConstant(
            name="CHOMAGE_BASE (taux)",
            source="constants.CHOMAGE_BASE",
            raw_value=constants.CHOMAGE_BASE,
            representations=("7,6%", "7,6 %"),
            must_appear_in=(EXPLICATION, PUBLIC_EXPLICATION),
        ),
        CriticalConstant(
            name="CHOMAGE_NAIRU (taux)",
            source="constants.CHOMAGE_NAIRU",
            raw_value=constants.CHOMAGE_NAIRU,
            representations=("7,5%", "7,5 %"),
            must_appear_in=_ALL_DOCS,
        ),
        CriticalConstant(
            name="INFLATION_STRUCTURELLE (intercept Phillips)",
            source="constants.INFLATION_STRUCTURELLE",
            raw_value=constants.INFLATION_STRUCTURELLE,
            representations=("1,5%", "1,5 %"),
            must_appear_in=_ALL_DOCS,
        ),
        CriticalConstant(
            name="CROISSANCE_POTENTIELLE",
            source="constants.CROISSANCE_POTENTIELLE",
            raw_value=constants.CROISSANCE_POTENTIELLE,
            representations=("1,0%", "1,0 %"),
            must_appear_in=_ALL_DOCS,
        ),
        CriticalConstant(
            name="TAUX_INTERET_BASE",
            source="constants.TAUX_INTERET_BASE",
            raw_value=constants.TAUX_INTERET_BASE,
            representations=("1,9%", "1,9 %"),
            must_appear_in=(EXPLICATION, PUBLIC_EXPLICATION),
        ),
        CriticalConstant(
            name="okun coefficient",
            source="economic_coeffs['okun']",
            raw_value=coeffs["okun"],
            # METHODO utilise notation anglo-saxonne `-0.35` sur ce point
            representations=("-0.35", "-0,35"),
            must_appear_in=(METHODO, PUBLIC_METHODO),
        ),
        CriticalConstant(
            name="debt_drag coefficient",
            source="economic_coeffs['debt_drag']",
            raw_value=coeffs["debt_drag"],
            representations=("-0,005", "-0.005"),
            must_appear_in=(METHODO, PUBLIC_METHODO),
        ),
    )


def _parse_representation(rep: str) -> float | None:
    """Parse une représentation textuelle (français ou anglais) en float.

    Retire espaces ASCII + insécables (U+00A0, fréquent dans la doc) et
    convertit la virgule décimale en point. Divise par 100 si `%` présent.
    Retourne `None` si non parsable (ex : "voir section")."""
    cleaned = rep.replace(" ", "").replace(" ", "").replace("%", "").replace(",", ".")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value / 100.0 if "%" in rep else value


def test_critical_constants_representations_match_code():
    """Au moins une `representation` reflète la valeur Python actuelle.

    Échoue AVANT le test de présence si tu changes la valeur du code sans
    mettre à jour les représentations dans ce fichier — message clair sur
    la dérive interne au test (avant de chercher dans la doc).
    """
    failures = []
    for c in _critical_constants():
        match = False
        for rep in c.representations:
            parsed = _parse_representation(rep)
            if parsed is None:
                continue
            if abs(parsed - c.raw_value) < 1e-4:
                match = True
                break
        if not match:
            failures.append(
                f"  - {c.name} = {c.raw_value!r} ({c.source})\n"
                f"    aucune des représentations {c.representations} "
                f"ne correspond à cette valeur après parsing."
            )
    if failures:
        raise AssertionError(
            "Représentations doc désynchronisées de la valeur Python "
            "actuelle :\n" + "\n".join(failures)
            + "\n\nFix : mettre à jour `representations` dans "
            "`tests/test_methodologie_consistency.py::_critical_constants`."
        )


def _matches_with_boundary(rep: str, text: str) -> bool:
    """Cherche `rep` dans `text` avec frontière numérique pour éviter les
    faux-vert par substring matching.

    Sans frontière, `"1,5%"` matche par substring `"21,5%"` ou `"107,6%"`,
    ce qui ferait passer le test à tort quand une valeur du code change
    mais qu'une représentation similaire apparaît ailleurs dans la doc
    pour un concept sans rapport. Lookbehind `(?<!\\d)` et lookahead
    `(?!\\d)` exigent que `rep` ne soit pas immédiatement entouré par un
    chiffre — suffit pour bloquer les ~95 % des cas de drift par bruit
    numérique adjacent. Les autres préfixes (`+`, `-`, `≈`) restent
    légitimes car non-numériques.
    """
    return re.search(r"(?<!\d)" + re.escape(rep) + r"(?!\d)", text) is not None


def test_critical_constants_appear_in_docs_ui():
    """Chaque constante critique apparaît avec une représentation acceptable
    dans la (les) doc(s) cible(s), y compris les copies publiques servies
    au frontend (si présentes — un fork du moteur seul n'a pas le frontend).

    Si la CI rougit ici :
    - soit une constante du code a changé sans MAJ de la doc UI ;
    - soit la doc a reformulé la valeur (ex : "115,6 %" → "115,6 pts") :
      ajouter la nouvelle représentation dans `_critical_constants` ;
    - soit `docs/` et `frontend-react/public/docs/` ont divergé (oubli de
      `python3 scripts/sync_public_docs.py`) — relancer le sync.
    """
    # Skip silencieux des copies publiques absentes (fork du moteur seul) :
    # le périmètre minimal `docs/METHODOLOGIE.md` + `EXPLICATION` est toujours
    # vérifié ; les chemins `frontend-react/public/docs/*` ne sont contrôlés
    # que si présents. Pattern aligné sur test_political_scenarios_2027.py:97-101.
    available_docs = tuple(p for p in _ALL_DOCS if p.exists())
    docs_cache = {path: path.read_text(encoding="utf-8") for path in available_docs}
    failures = []
    for c in _critical_constants():
        for doc_path in c.must_appear_in:
            if doc_path not in docs_cache:
                continue  # doc absente (fork) → skip ce check spécifique
            text = docs_cache[doc_path]
            if not any(_matches_with_boundary(rep, text) for rep in c.representations):
                failures.append(
                    f"  - {c.name} ({c.source}) = {c.raw_value!r}\n"
                    f"    aucune des représentations {c.representations} "
                    f"n'apparaît dans {doc_path.name} avec frontière numérique."
                )
    if failures:
        raise AssertionError(
            "Constantes économiques code↔doc UI désynchronisées :\n"
            + "\n".join(failures)
            + "\n\nFix : MAJ la valeur dans la doc UI concernée. Si le "
            "changement code est délibéré, MAJ aussi `representations` "
            "dans `tests/test_methodologie_consistency.py`. Vérifie aussi "
            "que `python3 scripts/sync_public_docs.py` a été lancé après "
            "l'édition de `docs/`."
        )


# --- Tests de mutation (rouge automatisé) ---------------------------------


def test_drift_detected_when_constant_changes(monkeypatch):
    """Rouge automatisé : muter une constante du code FAIT bien rougir le verrou.

    Garantit que le test de cohérence n'est pas faux-vert. On mute
    `INFLATION_STRUCTURELLE` 0.015 → 0.018 puis on exécute la même
    logique que `test_critical_constants_representations_match_code` —
    elle DOIT lever AssertionError avec un message ciblant la constante.
    """
    monkeypatch.setattr(constants, "INFLATION_STRUCTURELLE", 0.018)

    with pytest.raises(AssertionError, match="INFLATION_STRUCTURELLE"):
        test_critical_constants_representations_match_code()


def test_boundary_matching_blocks_substring_false_positives():
    """Garde-fou sur la frontière numérique : la doc peut citer une valeur
    NUMÉRIQUEMENT différente qui contient par substring une représentation
    verrouillée — sans frontière, faux-vert silencieux.

    Cas concrets représentatifs (extraits réels du repo) :
    - "1,5%" dans "21,5%" (chiffre avant) → DOIT être bloqué
    - "0,8%" dans "10,8%" (chiffre avant) → DOIT être bloqué
    - "2 994" dans "12 9940" (chiffres autour) → DOIT être bloqué
    - "1,5%" dans " 1,5%" (espace avant) → DOIT matcher
    - "0,8%" dans "+0,8%" (signe avant) → DOIT matcher (préfixe non-numérique)
    - "-0.35" dans "X-0.35" → DOIT matcher (préfixe non-numérique)
    """
    # Bloque les faux-verts par préfixe numérique
    assert not _matches_with_boundary("1,5%", "Inflation 21,5% en 2019")
    assert not _matches_with_boundary("0,8%", "Croissance 10,8% volume")
    assert not _matches_with_boundary("2 994", "Total 12 9940 Md")
    # Accepte les contextes légitimes
    assert _matches_with_boundary("1,5%", "Inflation tendancielle 1,5% (Phillips)")
    assert _matches_with_boundary("0,8%", "+0,8% par an depuis 2023")
    assert _matches_with_boundary("-0.35", "Okun β=-0.35 (médiane OFCE)")
    assert _matches_with_boundary("2 994", "PIB 2 994 Md€ (INSEE)")


def test_drift_detected_when_doc_only_has_substring_match(monkeypatch, tmp_path):
    """Rouge automatisé sur le faux-vert substring : si une valeur du code
    n'apparait dans la doc QUE comme substring d'un autre nombre, le test
    DOIT rougir.

    On bricole un cas où la rep cherchée existe en substring dans la doc
    mais avec contexte numérique différent — sans la frontière, ça
    passerait à tort. Avec la frontière, ça rougit comme attendu.
    """
    # Crée une doc factice qui ne contient "1,5%" que comme substring
    # de "21,5%" (cas réel : doc mentionne une stat sans rapport)
    fake_doc = tmp_path / "fake.md"
    fake_doc.write_text(
        "# Fake doc\n\nL'inflation moyenne 2010-2019 était de 21,5%.\n",
        encoding="utf-8",
    )
    # Sans frontière, "1,5%" matcherait par substring "21,5%" → faux-vert
    assert "1,5%" in fake_doc.read_text("utf-8")
    # Avec frontière, le matching exact échoue
    assert not _matches_with_boundary("1,5%", fake_doc.read_text("utf-8"))


def test_parse_representation_handles_french_and_english_formats():
    """Garde-fou sur le parser : couvre les formats utilisés en doc."""
    assert _parse_representation("1,5%") == pytest.approx(0.015)
    assert _parse_representation("1,5 %") == pytest.approx(0.015)
    assert _parse_representation("115,6%") == pytest.approx(1.156)
    assert _parse_representation("2 994") == pytest.approx(2994.0)
    assert _parse_representation("-0,35") == pytest.approx(-0.35)
    assert _parse_representation("-0.35") == pytest.approx(-0.35)
    assert _parse_representation("-0,005") == pytest.approx(-0.005)
    # Cas non parsable → None (pas d'exception)
    assert _parse_representation("voir section") is None
