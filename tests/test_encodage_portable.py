"""Portabilité de l'encodage des fichiers texte (v0.6.10, contre-audit externe V2-05).

Constat de l'audit : sous Windows sans `PYTHONUTF8=1`, `Path.read_text()` sans
`encoding=` décode les fichiers avec l'encodage de la locale (cp1252) ; les noms
de colonnes accentués des snapshots JSON (« Déficit/PIB % », « Chômage % »)
deviennent « DÃ©ficit/PIB % », « ChÃ´mage % », et le golden master standalone
(`tests/test_handler_coverage.py`) échoue alors que le moteur est correct.

Sur macOS et Linux l'encodage de la locale est UTF-8 : le défaut ne s'y voit
pas. Ce module le rend reproductible partout en SIMULANT la locale Windows dans
un sous-processus pytest : tout fichier ouvert en mode texte sans `encoding=`
y est décodé en cp1252, exactement comme sous Windows.

Seconde moitié du défaut : un interpréteur Python ENFANT écrit sa sortie
standard, sur un tube, dans l'encodage de la locale (cp1252 sous Windows) ;
le parent qui la décode en UTF-8 lève `UnicodeDecodeError` dès le premier
accent. Elle est verrouillée par une garde statique (seul le lanceur commun
`tests/sous_processus.py` lance un Python enfant) et par un rejeu dynamique
(les tests à sous-processus relancés sous `PYTHONIOENCODING=cp1252`).
"""
import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from sous_processus import lancer_python

ROOT = Path(__file__).resolve().parent.parent

# Encodage de la locale par défaut d'un Windows occidental (« ANSI code page »
# 1252) — celui que Python applique à un fichier texte ouvert sans `encoding=`
# quand le mode UTF-8 (PEP 540) n'est pas activé.
ENCODAGE_LOCALE_WINDOWS = "cp1252"

# Amorce exécutée dans le sous-processus : substitue l'encodage de la locale
# Windows partout où Python retomberait sur l'encodage de la locale (paramètre
# `encoding` absent). Un appel qui précise `encoding=` n'est PAS affecté.
_AMORCE_LOCALE_WINDOWS = f"""
import builtins, io, sys
_ouvrir = builtins.open
def _text_encoding(encoding, stacklevel=2):
    return {ENCODAGE_LOCALE_WINDOWS!r} if encoding is None else encoding
def _open(file, mode='r', buffering=-1, encoding=None, *args, **kwargs):
    if 'b' not in mode and encoding is None:
        encoding = {ENCODAGE_LOCALE_WINDOWS!r}
    return _ouvrir(file, mode, buffering, encoding, *args, **kwargs)
io.text_encoding = _text_encoding
builtins.open = _open
io.open = _open
import pytest
sys.exit(pytest.main(sys.argv[1:]))
"""

# Tests qui relisent un snapshot JSON aux clés accentuées. Le premier est celui
# que l'audit a vu échouer sur un clone du dépôt public seul ; les deux autres
# exigent les scénarios publiés (BUDGETLAB_SCENARIOS_JSON) et sont ignorés
# sans eux — ils échouaient de la même façon quand ils tournent.
TESTS_LECTEURS_DE_SNAPSHOTS = (
    "tests/test_handler_coverage.py::test_standalone_master_all_scenarios_match",
    "tests/test_golden_master_full.py::test_golden_master_all_scenarios_match",
    "tests/test_baseline_properties.py::test_e_non_regression_deltas_scenarios",
)


def test_snapshots_relus_a_l_identique_sous_locale_windows():
    """Rouge V2-05 (a) : sous une locale cp1252, les lecteurs de snapshots
    doivent passer comme sous UTF-8 — l'encodage d'un fichier du dépôt est une
    propriété du fichier (UTF-8), jamais de la machine qui le lit."""
    res = lancer_python(
        "-c", _AMORCE_LOCALE_WINDOWS, *TESTS_LECTEURS_DE_SNAPSHOTS,
        "-q", "-p", "no:cacheprovider", "--no-header",
        cwd=ROOT, erreurs="replace",
    )
    assert res.returncode == 0, (
        "Sous une locale Windows (cp1252), la relecture des snapshots échoue : "
        "un fichier texte est ouvert sans encoding='utf-8'.\n"
        + res.stdout[-4000:] + res.stderr[-2000:]
    )


# ---------------------------------------------------------------------------
# Garde durable : aucun fichier texte ouvert sans `encoding=` dans le dépôt.
# ---------------------------------------------------------------------------
# Le rouge ci-dessus ne couvre que les lecteurs de snapshots qu'il exécute ;
# cette garde statique (AST) couvre TOUT fichier Python suivi par git — moteur,
# API, scripts, tests — y compris un site ajouté demain, sous les formes que
# reconnaît le détecteur (liste dans la docstring de `sites_sans_encodage`).

# Exceptions explicites : (chemin relatif, ligne) d'un appel volontairement
# dépourvu d'`encoding=` (aucun aujourd'hui). Toute entrée doit dire pourquoi.
EXCEPTIONS_ENCODAGE: frozenset = frozenset()

# Appels du module `subprocess` qui décodent la sortie de l'enfant en texte.
_APPELS_SUBPROCESS = frozenset({"run", "check_output", "Popen", "call", "check_call"})

# Position de `encoding` parmi les arguments positionnels, par fonction :
# open(file, mode, buffering, encoding) ; Path.open(mode, buffering, encoding) ;
# Path.read_text(encoding) ; Path.write_text(data, encoding).
_POSITION_ENCODING = {"open": 3, "Path.open": 2, "read_text": 0, "write_text": 1}


def _encodage_explicite(appel) -> bool:
    """`encoding=` présent ET différent du littéral None (qui vaut absence)."""
    return any(kw.arg == "encoding" and not (
        isinstance(kw.value, ast.Constant) and kw.value.value is None)
        for kw in appel.keywords)


def _mode_binaire(appel, position_mode: int):
    """True/False si le mode est un littéral (binaire ou texte), None sinon."""
    mode = None
    if len(appel.args) > position_mode:
        mode = appel.args[position_mode]
    for kw in appel.keywords:
        if kw.arg == "mode":
            mode = kw.value
    if mode is None:
        return False  # mode par défaut 'r' : texte
    if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
        return "b" in mode.value
    return None  # mode calculé : indécidable statiquement → signalé


def _vrai_litteral(valeur) -> bool:
    return isinstance(valeur, ast.Constant) and bool(valeur.value)


def sites_sans_encodage(source: str, nom_fichier: str = "<source>") -> list:
    """Liste des (ligne, description) des appels texte sans encodage explicite.

    Couvre : `open(...)` / `io.open(...)`, `<chemin>.open(...)`,
    `<chemin>.read_text(...)`, `<chemin>.write_text(...)` en mode texte, et
    `subprocess.<run|check_output|Popen|call|check_call>(..., text=True)`
    (ou `universal_newlines=True`, ou un alias d'import de subprocess ou de
    ces fonctions) sans `encoding=` ; `encoding=None` vaut absence.
    NON couverts (absents du dépôt) : `tempfile.*File('w')`, `os.fdopen`,
    `os.popen`, `io.TextIOWrapper`."""
    sites = []
    arbre = ast.parse(source, filename=nom_fichier)
    imports = [n for n in ast.walk(arbre) if isinstance(n, (ast.Import, ast.ImportFrom))]
    modules_subprocess = {"subprocess"} | {
        a.asname for n in imports if isinstance(n, ast.Import)
        for a in n.names if a.name == "subprocess" and a.asname}
    fonctions_subprocess = {
        a.asname or a.name for n in imports
        if isinstance(n, ast.ImportFrom) and n.module == "subprocess"
        for a in n.names if a.name in _APPELS_SUBPROCESS}
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call):
            continue
        f = noeud.func
        nom = f.id if isinstance(f, ast.Name) else (
            f.attr if isinstance(f, ast.Attribute) else None)
        if nom is None:
            continue
        if _encodage_explicite(noeud):
            continue
        if nom == "open":
            # `open(...)` / `io.open(...)` : (file, mode, buffering, encoding) ;
            # tout autre `<objet>.open(...)` est lu comme Path.open(mode, ...).
            builtin = isinstance(f, ast.Name) or (
                isinstance(f.value, ast.Name) and f.value.id == "io")
            cle, pos_mode = ("open", 1) if builtin else ("Path.open", 0)
            binaire = _mode_binaire(noeud, pos_mode)
            if binaire or len(noeud.args) > _POSITION_ENCODING[cle]:
                continue
            raison = "mode non littéral" if binaire is None else "texte"
            sites.append((noeud.lineno, f"{nom}() {raison} sans encoding="))
        elif nom in ("read_text", "write_text"):
            if len(noeud.args) > _POSITION_ENCODING[nom]:
                continue
            sites.append((noeud.lineno, f"{nom}() sans encoding="))
        elif (isinstance(f, ast.Attribute) and nom in _APPELS_SUBPROCESS
              and isinstance(f.value, ast.Name) and f.value.id in modules_subprocess) \
                or (isinstance(f, ast.Name) and nom in fonctions_subprocess):
            texte = any(kw.arg in ("text", "universal_newlines")
                        and _vrai_litteral(kw.value) for kw in noeud.keywords)
            if texte:
                sites.append((noeud.lineno,
                              f"subprocess.{nom}(text=True) sans encoding="))
    return sites


def _fichiers_python_suivis() -> list:
    """Fichiers .py suivis par git ; repli explicite sur l'arborescence si le
    dépôt n'est pas un clone git (archive) — jamais un ensemble vide muet."""
    try:
        sortie = subprocess.run(
            ["git", "ls-files", "-z", "--", "*.py"], cwd=ROOT,
            capture_output=True, check=True).stdout
        fichiers = [ROOT / p for p in sortie.decode("utf-8").split("\0") if p]
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"[test_encodage_portable] git ls-files indisponible ({exc}) : "
              "repli sur le parcours de l'arborescence", file=sys.stderr)
        fichiers = [p for p in ROOT.rglob("*.py")
                    if not any(part.startswith(".") or part in ("venv", "__pycache__")
                               for part in p.relative_to(ROOT).parts)]
    return fichiers


def test_aucun_fichier_texte_ouvert_sans_encodage():
    """Propriété V2-05 : tout fichier texte du dépôt est ouvert avec un
    encodage explicite — sinon la suite (ou le moteur) dépend de la locale."""
    fichiers = _fichiers_python_suivis()
    assert len(fichiers) > 50, f"inventaire suspect : {len(fichiers)} fichiers .py"
    fautes = []
    for chemin in fichiers:
        rel = chemin.relative_to(ROOT).as_posix()
        for ligne, quoi in sites_sans_encodage(
                chemin.read_text(encoding="utf-8"), rel):
            if (rel, ligne) not in EXCEPTIONS_ENCODAGE:
                fautes.append(f"{rel}:{ligne} — {quoi}")
    assert not fautes, (
        "Fichier texte ouvert sans encodage explicite (dépend de la locale : "
        "cp1252 sous Windows) — ajouter encoding='utf-8' :\n  "
        + "\n  ".join(fautes))


@pytest.mark.parametrize("code,attendu", [
    # Signalés
    ("p.read_text()", 1),
    ("p.write_text(s)", 1),
    ("open(f)", 1),
    ("open(f, 'w')", 1),
    ("io.open(f, 'r')", 1),
    ("p.open()", 1),
    ("p.open('w')", 1),
    ("open(f, mode)", 1),
    ("subprocess.run(c, text=True)", 1),
    ("subprocess.check_output(c, universal_newlines=True)", 1),
    ("p.read_text(encoding=None)", 1),
    ("open(f, encoding=None)", 1),
    ("subprocess.run(c, text=1)", 1),
    ("import subprocess as sp\nsp.run(c, text=True)", 1),
    ("from subprocess import run\nrun(c, text=True)", 1),
    ("from subprocess import check_output as co\nco(c, text=True)", 1),
    # Conformes
    ("p.read_text(encoding='utf-8')", 0),
    ("p.read_text('utf-8')", 0),
    ("p.write_text(s, 'utf-8')", 0),
    ("p.write_text(s, encoding='utf-8')", 0),
    ("open(f, encoding='utf-8')", 0),
    ("open(f, 'r', -1, 'utf-8')", 0),
    ("open(f, 'rb')", 0),
    ("open(f, mode='wb')", 0),
    ("p.open('rb')", 0),
    ("p.open(encoding='utf-8')", 0),
    ("subprocess.run(c, capture_output=True)", 0),
    ("subprocess.run(c, text=True, encoding='utf-8')", 0),
    ("subprocess.run(c, encoding='utf-8')", 0),
    ("subprocess.run(c, text=False)", 0),
    ("from subprocess import run\nrun(c, text=True, encoding='utf-8')", 0),
])
def test_detecteur_encodage(code, attendu):
    """Le détecteur rougit sur chaque forme fautive et laisse passer chaque
    forme conforme — sans quoi la garde ci-dessus serait un faux vert."""
    assert len(sites_sans_encodage(code)) == attendu, sites_sans_encodage(code)


# ---------------------------------------------------------------------------
# Seconde moitié : la sortie standard d'un interpréteur Python enfant.
# ---------------------------------------------------------------------------
# Seul module autorisé à lancer un interpréteur Python enfant : il fixe
# l'encodage des DEUX côtés du tube (PYTHONIOENCODING côté enfant, encoding=
# côté parent). Un appel direct `subprocess.run([sys.executable, ...])` ailleurs
# laisserait l'enfant écrire en cp1252 sous Windows.
MODULE_LANCEUR_PYTHON = "tests/sous_processus.py"

# Racine d'INVOCATION (`.absolute()`, pas `.resolve()`) : depuis le dépôt
# parent, `tests/` est un lien symbolique ; resolve() retomberait sur la racine
# du sous-module, où `frontend-react/` n'existe pas, et les tests à
# sous-processus qui en dépendent seraient ignorés dans le rejeu (faux vert).
RACINE_INVOCATION = Path(__file__).absolute().parent.parent


def lignes_sys_executable(source: str, nom_fichier: str = "<source>") -> list:
    """Lignes où le code désigne l'interpréteur courant (`sys.executable`,
    `from sys import executable`) — c'est-à-dire s'apprête à le relancer."""
    lignes = []
    for noeud in ast.walk(ast.parse(source, filename=nom_fichier)):
        if isinstance(noeud, ast.Attribute) and noeud.attr == "executable" \
                and isinstance(noeud.value, ast.Name) and noeud.value.id == "sys":
            lignes.append(noeud.lineno)
        elif isinstance(noeud, ast.ImportFrom) and noeud.module == "sys" \
                and any(a.name == "executable" for a in noeud.names):
            lignes.append(noeud.lineno)
    return sorted(lignes)


def test_python_enfant_lance_uniquement_par_le_lanceur_commun():
    """Propriété V2-05 (sous-processus) : tout interpréteur Python enfant est
    lancé par `lancer_python` (tests/sous_processus.py), qui force la sortie
    de l'enfant en UTF-8 — sinon elle dépend de la locale (cp1252 sous Windows)."""
    fautes = []
    for chemin in _fichiers_python_suivis():
        rel = chemin.relative_to(ROOT).as_posix()
        if rel == MODULE_LANCEUR_PYTHON:
            continue
        for ligne in lignes_sys_executable(chemin.read_text(encoding="utf-8"), rel):
            fautes.append(f"{rel}:{ligne}")
    assert not fautes, (
        "Interpréteur Python enfant lancé hors du lanceur commun : sous Windows "
        "sa sortie standard serait encodée en cp1252 et le décodage UTF-8 du "
        "parent échouerait — utiliser lancer_python() de "
        f"{MODULE_LANCEUR_PYTHON} :\n  " + "\n  ".join(fautes))


@pytest.mark.parametrize("code,attendu", [
    ("subprocess.run([sys.executable, 'x.py'])", 1),
    ("cmd = [sys.executable]", 1),
    ("from sys import executable", 1),
    ("import sys; sys.argv", 0),
    ("'sys.executable'", 0),
])
def test_detecteur_sys_executable(code, attendu):
    assert len(lignes_sys_executable(code)) == attendu


def _tests_a_sous_processus_python() -> list:
    """Fichiers de test qui lancent un interpréteur Python enfant — détectés
    dans le source, jamais listés à la main (un test ajouté demain y entre)."""
    ici = Path(__file__).name
    trouves = []
    for chemin in sorted((RACINE_INVOCATION / "tests").glob("test_*.py")):
        texte = chemin.read_text(encoding="utf-8")
        if chemin.name != ici and ("lancer_python(" in texte or "sys.executable" in texte):
            trouves.append(chemin.relative_to(RACINE_INVOCATION).as_posix())
    return trouves


def test_sorties_de_sous_processus_relues_sous_locale_windows():
    """Rejeu V2-05 (sous-processus) : les tests qui lancent un Python enfant
    passent quand la sortie standard par défaut est cp1252 (Windows). Les
    petits-enfants héritent de `PYTHONIOENCODING=cp1252` sauf surcharge par le
    lanceur commun ; sans elle, `UnicodeDecodeError` côté parent.

    Depuis un clone du dépôt public seul, les tests qui exigent `frontend-react/`
    sont ignorés : la propriété du lanceur y reste verrouillée par
    `test_lancer_python_sortie_utf8_sous_locale_windows`."""
    fichiers = _tests_a_sous_processus_python()
    assert fichiers, "aucun test à sous-processus détecté : détection cassée"
    # L'enfant pytest reçoit PYTHONIOENCODING=cp1252:replace, hérité par ses
    # propres enfants sauf surcharge — celle du lanceur commun. `replace` : le
    # rapport de pytest lui-même peut contenir des caractères hors cp1252
    # (« → », « ≠ ») ; seul le décodage des petits-enfants est sous test.
    # La variable est AUSSI posée dans `env`, indépendamment du lanceur : un
    # lanceur cassé (qui ne poserait plus PYTHONIOENCODING) ne doit pas
    # neutraliser le rejeu chargé de le détecter.
    locale_windows = f"{ENCODAGE_LOCALE_WINDOWS}:replace"
    res = lancer_python(
        "-c", _AMORCE_LOCALE_WINDOWS, *fichiers,
        "-q", "-p", "no:cacheprovider", "--no-header", "-rs",
        cwd=RACINE_INVOCATION, env=dict(os.environ, PYTHONIOENCODING=locale_windows),
        encodage=ENCODAGE_LOCALE_WINDOWS, erreurs="replace",
    )
    assert res.returncode == 0, (
        "Sous une locale Windows (sortie standard cp1252), un test à "
        "sous-processus échoue : l'enfant n'écrit pas en UTF-8.\n"
        + res.stdout[-4000:] + res.stderr[-2000:]
    )


# Texte imprimé par l'enfant : accents des colonnes du moteur + caractères
# hors cp1252 (« → », « ≠ »), que cp1252 ne sait même pas encoder.
_TEXTE_ACCENTUE = "Déficit/PIB % · Chômage % → ≠"


@pytest.mark.parametrize("par", ["environnement_herite", "env_explicite"])
def test_lancer_python_sortie_utf8_sous_locale_windows(monkeypatch, par):
    """Propriété du lanceur commun (tourne aussi sur un clone du dépôt public
    seul) : même quand l'environnement transmis impose cp1252 à l'enfant
    (Windows, ou le rejeu ci-dessus), sa sortie est relue à l'identique."""
    env = None
    if par == "environnement_herite":
        monkeypatch.setenv("PYTHONIOENCODING", ENCODAGE_LOCALE_WINDOWS)
    else:
        env = dict(os.environ, PYTHONIOENCODING=ENCODAGE_LOCALE_WINDOWS)
    res = lancer_python("-c", f"print({_TEXTE_ACCENTUE!r})", cwd=ROOT, env=env,
                        check=True)
    assert res.stdout == _TEXTE_ACCENTUE + "\n"
