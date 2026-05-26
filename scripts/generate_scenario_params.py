#!/usr/bin/env python3
"""
Générateur DÉTERMINISTE du bloc Markdown « Paramètres injectés ».

Source unique : frontend-react/src/data/scenarios.json
Destination   : docs/SCENARIOS_POLITIQUES.md (entre les marqueurs HTML)

Modes CLI :
  --stdout   Imprime le bloc (marqueurs inclus) sur stdout, n'écrit aucun fichier.
  --check    Régénère en mémoire, compare au contenu actuel dans le fichier cible ;
             exit 0 si identique, exit 1 + diff résumé sur stderr si différent/absent.
  (défaut)   Réécrit le contenu entre les 2 marqueurs dans docs/SCENARIOS_POLITIQUES.md.
             Si le fichier ou les marqueurs sont absents → message clair + exit 1.
"""

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_JSON = REPO_ROOT / "frontend-react" / "src" / "data" / "scenarios.json"
TARGET_DOC = REPO_ROOT / "docs" / "SCENARIOS_POLITIQUES.md"

MARKER_START = "<!-- SCENARIO_PARAMS:START -->"
MARKER_END = "<!-- SCENARIO_PARAMS:END -->"


# ---------------------------------------------------------------------------
# Helpers — formatage de valeur déterministe
# ---------------------------------------------------------------------------

def _format_value(v) -> str:
    """Formatage stable : bool avant int (True/False sont int en Python)."""
    if isinstance(v, bool):
        return str(v).lower()   # true / false
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        # Supprime le .0 si c'est un entier exact (ex. 64.0 → "64") ;
        # conserve les décimales significatives (ex. 0.097 → "0.097").
        if v == int(v):
            return str(int(v))
        return str(v)
    if isinstance(v, str):
        return v
    # Fallback JSON-safe (ne devrait pas arriver sur ce JSON)
    return json.dumps(v, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Génération du bloc
# ---------------------------------------------------------------------------

def load_scenarios() -> dict:
    if not SCENARIOS_JSON.exists():
        print(
            f"ERREUR : fichier source introuvable : {SCENARIOS_JSON}",
            file=sys.stderr,
        )
        sys.exit(1)
    with SCENARIOS_JSON.open(encoding="utf-8") as fh:
        try:
            return json.load(fh)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"scenarios.json corrompu / JSON invalide : {SCENARIOS_JSON} — {e}"
            ) from e


def build_block(data: dict) -> str:
    """
    Construit un tableau Markdown déterministe.

    Colonnes  : scénarios dans l'ordre d'apparition du JSON (dict ordonné Python 3.7+).
    En-tête   : label de chaque scénario (tel quel, pas codé en dur).
    Lignes    : paramètres triés par (mesure, param) ordre alpha stable.
    Cellule   : valeur formatée ; « — » si le scénario ne possède PAS la clé
                (paramètre absent) ; « null » si la clé existe avec valeur None.
    """
    scenario_ids = list(data.keys())
    labels = [data[sid]["label"] for sid in scenario_ids]

    # Collecte l'union de toutes les clés (mesure, param) — tri stable
    all_keys: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for sid in scenario_ids:
        measures = data[sid].get("apiMeasures", {})
        for mesure in sorted(measures.keys()):
            for param in sorted(measures[mesure].keys()):
                key = (mesure, param)
                if key not in seen:
                    all_keys.append(key)
                    seen.add(key)
    # Tri global stable (mesure α puis param α)
    all_keys.sort()

    # En-tête
    header = "| Mesure | Paramètre | " + " | ".join(labels) + " |"
    separator = "|--------|-----------|" + "|".join(
        ["-" * (len(lbl) + 2) for lbl in labels]
    ) + "|"

    rows = []
    for mesure, param in all_keys:
        cells = []
        for sid in scenario_ids:
            measures = data[sid].get("apiMeasures", {})
            params = measures.get(mesure, {})
            if param not in params:
                cells.append("—")
            else:
                val = params[param]
                cells.append("null" if val is None else _format_value(val))
        rows.append(f"| {mesure} | {param} | " + " | ".join(cells) + " |")

    table = "\n".join([header, separator] + rows)
    return f"{MARKER_START}\n{table}\n{MARKER_END}"


# ---------------------------------------------------------------------------
# Lecture/écriture des marqueurs dans le fichier cible
# ---------------------------------------------------------------------------

def _read_target() -> str | None:
    """Renvoie le contenu du fichier cible, ou None s'il n'existe pas."""
    if not TARGET_DOC.exists():
        return None
    return TARGET_DOC.read_text(encoding="utf-8")


def _extract_current_block(content: str) -> str | None:
    """Extrait le bloc entre marqueurs (marqueurs inclus), ou None si absents."""
    if MARKER_START not in content or MARKER_END not in content:
        return None
    idx_start = content.index(MARKER_START)
    idx_end = content.index(MARKER_END) + len(MARKER_END)
    return content[idx_start:idx_end]


def _replace_block(content: str, new_block: str) -> str:
    idx_start = content.index(MARKER_START)
    idx_end = content.index(MARKER_END) + len(MARKER_END)
    return content[:idx_start] + new_block + content[idx_end:]


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

def mode_stdout(data: dict) -> None:
    print(build_block(data))


def mode_update(data: dict) -> None:
    content = _read_target()
    if content is None:
        print(
            f"ERREUR : fichier cible absent : {TARGET_DOC}\n"
            "Ce fichier sera créé dans une tâche ultérieure. "
            "Utilisez --stdout pour afficher le bloc.",
            file=sys.stderr,
        )
        sys.exit(1)
    if MARKER_START not in content or MARKER_END not in content:
        print(
            f"ERREUR : marqueurs absents dans {TARGET_DOC}\n"
            f"Attendus : {MARKER_START!r} et {MARKER_END!r}",
            file=sys.stderr,
        )
        sys.exit(1)
    new_block = build_block(data)
    updated = _replace_block(content, new_block)
    TARGET_DOC.write_text(updated, encoding="utf-8")
    print(f"OK : bloc mis à jour dans {TARGET_DOC}")


def mode_check(data: dict) -> None:
    content = _read_target()
    if content is None:
        print(
            f"SYNC KO : fichier cible absent : {TARGET_DOC}",
            file=sys.stderr,
        )
        sys.exit(1)
    current_block = _extract_current_block(content)
    if current_block is None:
        print(
            f"SYNC KO : marqueurs absents dans {TARGET_DOC}",
            file=sys.stderr,
        )
        sys.exit(1)
    expected_block = build_block(data)
    if current_block == expected_block:
        print("SYNC OK : le bloc est à jour.")
        sys.exit(0)
    else:
        # Diff résumé ligne par ligne
        current_lines = current_block.splitlines()
        expected_lines = expected_block.splitlines()
        diffs = []
        max_lines = max(len(current_lines), len(expected_lines))
        for i in range(max_lines):
            cl = current_lines[i] if i < len(current_lines) else "<absent>"
            el = expected_lines[i] if i < len(expected_lines) else "<absent>"
            if cl != el:
                diffs.append(f"  ligne {i+1}:\n    - {cl}\n    + {el}")
        print(
            f"SYNC KO : le bloc dans {TARGET_DOC} est désynchronisé.\n"
            + "\n".join(diffs[:20])
            + ("\n  ... (diff tronqué)" if len(diffs) > 20 else ""),
            file=sys.stderr,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Entrée
# ---------------------------------------------------------------------------

def main() -> None:
    args = sys.argv[1:]
    data = load_scenarios()

    if "--stdout" in args:
        mode_stdout(data)
    elif "--check" in args:
        mode_check(data)
    else:
        mode_update(data)


if __name__ == "__main__":
    main()
