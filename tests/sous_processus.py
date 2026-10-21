"""Lanceur commun des interpréteurs Python enfants de la suite (v0.6.10, V2-05).

Sur un tube, un Python enfant encode sa sortie standard avec l'encodage de la
locale — cp1252 sous Windows sans `PYTHONUTF8=1` — et un parent qui la décode
en UTF-8 lève `UnicodeDecodeError` au premier accent. `lancer_python` fixe les
DEUX côtés du tube avec le même encodage : `PYTHONIOENCODING` chez l'enfant
(il remplace toujours celui hérité) et `encoding=` chez le parent.

C'est le SEUL endroit du dépôt autorisé à désigner `sys.executable` : garde
`tests/test_encodage_portable.py::test_python_enfant_lance_uniquement_par_le_lanceur_commun`.
"""
import os
import subprocess
import sys

# Encodage des fichiers et des sorties du dépôt : une propriété du dépôt,
# jamais de la machine qui exécute la suite.
ENCODAGE_SORTIE_ENFANT = "utf-8"


def lancer_python(*arguments, cwd, env=None, check=False,
                  encodage=ENCODAGE_SORTIE_ENFANT, erreurs="strict"):
    """Lance l'interpréteur de la suite avec `arguments` et capture sa sortie.

    - `env` : environnement de base de l'enfant (`os.environ` par défaut) ;
      sa variable `PYTHONIOENCODING` est TOUJOURS remplacée par
      `<encodage>:<erreurs>`, si bien qu'un environnement hérité en cp1252
      (Windows, ou le rejeu qui le simule) ne peut pas fuir chez l'enfant ;
    - `encodage` / `erreurs` : encodage de la sortie, identique des deux côtés ;
      seul le rejeu de locale Windows en choisit un autre (cp1252) ;
    - `check=True` : `CalledProcessError` si l'enfant sort en erreur.
    """
    env_enfant = dict(os.environ if env is None else env)
    env_enfant["PYTHONIOENCODING"] = f"{encodage}:{erreurs}"
    return subprocess.run(
        [sys.executable, *(str(a) for a in arguments)],
        cwd=cwd, env=env_enfant, capture_output=True,
        encoding=encodage, errors=erreurs, check=check,
    )
