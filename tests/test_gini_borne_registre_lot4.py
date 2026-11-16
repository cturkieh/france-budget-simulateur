"""Lot 4 — garde de borne du Gini sur TOUT le registre, sans dépendance aux noms.

Chaque levier du registre public (policy_measures.json), chaque paramètre
numérique porté à son minimum, à son maximum et à deux points intermédiaires
(les autres au défaut), moteur neuf, année d'entrée et année suivante (montant
d'année pleine) : |Gini émis| ≤ (1 + G) / Y × montant (|dépense| + |recette|),
la borne arithmétique de tout instrument (|C − G| ≤ 1 + G). Une constante mal
nommée, un littéral dans un handler ou un levier nouveau ne peuvent pas y
échapper : la garde ne lit ni les noms de constantes ni une liste de leviers.
Garde proposée par la relecture adverse du lot 4 (rouge sur l'état d'avant le
lot : neuf leviers au-dessus de la borne ; rouge sous mutation d'une constante
mal nommée et d'un levier hors liste). Les règles qui ne sont pas en Md€ et
dont le Gini est nul (CSG progressive, faute de source) sont sautées par
construction (Gini émis nul).
"""
import copy
import json
from pathlib import Path

import pytest

import budget_simulator.constants as C
from budget_simulator.simulator import BudgetSimulatorV45

BORNE = (1.0 + C.GINI_BASE) / C.MASSE_NIVEAUX_DE_VIE_MD_EUR
REGISTRE = json.loads((Path(C.__file__).resolve().parents[1] / 'policy_measures.json').read_text(encoding='utf-8'))['mesures']
EXCEPTIONS = set()   # aucune exception depuis que la CSG progressive est à zéro faute de source


def _points(mesure):
    params = mesure.get('parametres', {})
    # Paramètres « nullables » (défaut None, mode montant) : laissés au défaut du handler.
    defauts = {p: v.get('valeur_defaut') for p, v in params.items() if v.get('valeur_defaut') is not None}
    for p, v in params.items():
        lo, hi = v.get('min'), v.get('max')
        if isinstance(lo, bool) or not isinstance(lo, (int, float)) or not isinstance(hi, (int, float)):
            continue
        for x in (lo, lo + (hi - lo) / 3, lo + 2 * (hi - lo) / 3, hi):
            q = dict(defauts)
            q[p] = int(x) if isinstance(v.get('valeur_defaut'), int) and float(x).is_integer() else x
            yield p, x, q


@pytest.mark.parametrize('mesure', REGISTRE, ids=[m['id'] for m in REGISTRE])
def test_gini_par_md_sous_la_borne_sur_tout_le_domaine(mesure):
    lid = mesure['id']
    depassements = []
    for p, x, q in _points(mesure):
        # Deux moteurs neufs : année d'entrée (effets gatés « première année ») et année
        # d'entrée + 1 (montant d'année pleine, phasage achevé) ; on garde le plus grand Gini
        # émis au premier passage et le plus grand montant (borne la plus clémente).
        g, montant = 0.0, 0.0
        for an in (C.POLICY_START_YEAR, C.POLICY_START_YEAR + 1):
            sim = BudgetSimulatorV45(periods=1)
            sim._reset_state()
            sim.mesures = {lid: copy.deepcopy(q)}
            # Hors simulation : PIB des années sources des impôts à taux (règle R-IDX) posé au PIB 2025.
            sim._pib_nominal_par_annee.update({a: float(C.PIB_BASE_2025_MD_EUR) for a in range(2024, 2031)})
            # Idem pour l'indice de prix des années passées (référence datée du
            # SMIC) : posé à l'indice courant.
            sim._indice_prix_par_annee.update({a: sim.indice_prix_depenses() for a in range(2024, 2031)})
            args = (sim.measure_registry[lid], copy.deepcopy(q), an, float(C.PIB_BASE_2025_MD_EUR), 0.016, 0.075)
            dep, rec, imp = (sim.measure_handlers[lid](*args) if lid in sim.measure_handlers
                             else sim._evaluer_formule(*args))
            g = max(g, abs(float((imp or {}).get('gini', 0.0) or 0.0)))
            montant = max(montant, abs(float(dep or 0)) + abs(float(rec or 0)))
        if g == 0.0 or (lid, p) in EXCEPTIONS:
            continue
        if g > BORNE * montant * (1 + 1e-9):
            depassements.append(f'{p}={x:.4g} : |Gini| {g:.6f} > {BORNE:.6f} × {montant:.3f} Md€')
    assert not depassements, f'{lid} : ' + ' ; '.join(depassements[:4])
