"""TVA ciblée (``fiscalite_indirecte.tva_ciblee``) : les coefficients de Gini et de compétitivité par Md€ ne
dépendent pas du rendement d'un point du taux normal.

Avant : ``GINI_TVA_PAR_MD`` et ``COMPET_TVA_PAR_MD`` étaient dérivés en appelant ``recette_tva_taux``, la fonction
du curseur du taux NORMAL (règle de +2 points rapportée à la recette de +2 points). Corriger le rendement d'un
point du taux normal aurait donc presque doublé, en silence, l'effet par Md€ d'un AUTRE levier : la compétitivité
d'une baisse de TVA ciblée ne doit pas changer parce que le point du taux normal est mieux chiffré. Désormais la
recette de référence de ces coefficients est figée à sa valeur de v0.8.1, même calcul, au bit
(``TVA_RECETTE_REFERENCE_TVA_CIBLEE_MD``) ; leur révision relève d'une passe dédiée.
"""
import ast
from pathlib import Path

import budget_simulator.constants as C

ARBRE = ast.parse(Path(C.__file__).read_text(encoding='utf-8'))
AFFECTATIONS = {}
for noeud in ARBRE.body:
    if isinstance(noeud, ast.Assign):
        for cible in noeud.targets:
            if isinstance(cible, ast.Name):
                AFFECTATIONS[cible.id] = noeud.value


def _dependances(nom, vus=None):
    """Noms lus, de proche en proche, par l'affectation de module de ``nom``."""
    vus = set() if vus is None else vus
    valeur = AFFECTATIONS.get(nom)
    if valeur is None:
        return vus
    for n in ast.walk(valeur):
        if isinstance(n, ast.Name) and n.id not in vus:
            vus.add(n.id)
            _dependances(n.id, vus)
    return vus


def test_coefficients_independants_du_point_du_taux_normal():
    for nom in ('GINI_TVA_PAR_MD', 'COMPET_TVA_PAR_MD'):
        deps = _dependances(nom)
        assert 'recette_tva_taux' not in deps, nom
        assert not any(d.startswith(('TVA_ASSIETTE', 'TVA_POINT')) for d in deps), (nom, sorted(deps))


def test_valeurs_de_v081_au_bit():
    """La recette de référence est celle que rendait la fonction du taux normal en v0.8.1 à +2 points (22 %), au
    PIB et au chômage de base (0,53 × PIB, élasticité −0,2, × 0,9) : mêmes opérations, même ordre."""
    assert C.CHOMAGE_BASE <= 0.10  # pas de majoration de l'élasticité en chômage élevé
    reference = (0.22 - 0.20) * (0.53 * C.PIB_BASE_2025_MD_EUR * (1 + -0.2 * (0.22 - 0.20))) * 0.9
    assert reference == 28.420003439999984
    assert getattr(C, 'TVA_RECETTE_REFERENCE_TVA_CIBLEE_MD', None) == reference
    assert C.GINI_TVA_PAR_MD == C.TVA_GINI_PAR_2PTS / reference
    assert C.COMPET_TVA_PAR_MD == C.TVA_COMPET_PAR_2PTS / reference
