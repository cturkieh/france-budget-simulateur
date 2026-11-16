"""Point de TVA du curseur « taux normal » (``tva_rate``) : rendement net du seul taux de 20 %.

Source rouverte : DG Trésor, *Trésor-Éco* n° 371 (septembre 2025), « Analyse de la composition des
recettes de TVA », p. 4, tableau 2 « Rendement d'un point TVA 2025 net total et par taux » : 20 % =
7,5 Md€ (ensemble des taux 11,4 ; taux réduits 0,4 + 2,0 + 1,6). Net = après retrait de la TVA payée
par les administrations publiques sur leurs propres achats : le moteur compte le solde de toutes les
administrations et n'augmente pas leur dépense quand la TVA monte, le net est donc le chiffre
cohérent. Le point est « vieilli avec l'évolution des recettes totales de TVA en comptabilité
nationale » (note 5) : calé sur les recettes encaissées.

Avant le lot 3 : 0,53 × PIB × 0,9 = 14,24 Md€ par point au PIB 2025 — toute la consommation des
ménages, taux réduits compris, plus que le point brut de TOUS les taux (13,7). La forme de la
fonction (assiette en part du PIB de l'année, élasticité −0,2 / −0,1, majoration en chômage élevé,
coude au-delà de 22 %) ne change pas : seul le coefficient d'assiette change.
"""
import pytest

import budget_simulator.constants as C
from budget_simulator.constants import CHOMAGE_BASE, PIB_BASE_2025_MD_EUR, recette_tva_taux


def _ancienne_recette(taux, pib, chomage):
    """Formule d'avant le lot 3, recopiée pour la seule preuve de forme (coefficient 0,53 × 0,9)."""
    base = 0.53 * pib
    e = -0.2 if taux > 0.20 else -0.1
    if chomage > 0.10:
        e *= 1.2
    r = (taux - 0.20) * base * (1 + e * (taux - 0.20)) * 0.9
    if taux > 0.22:
        r *= (1 - 0.2 * (taux - 0.22) / 0.03)
    return r


def test_un_point_vaut_le_point_net_du_taux_de_20_pour_cent():
    """Rendement statique d'un point au PIB 2025 (limite sans comportement) = 7,5 Md€."""
    h = 1e-7
    statique = recette_tva_taux(0.20 + h, PIB_BASE_2025_MD_EUR, CHOMAGE_BASE) / (h * 100)
    assert statique == pytest.approx(7.5, rel=1e-5)
    assert C.TVA_POINT_NET_TAUX_NORMAL_2025_MD == 7.5


@pytest.mark.parametrize('pib', [2800.0, PIB_BASE_2025_MD_EUR, 3300.0, 3700.0])
def test_assiette_en_part_du_pib_de_l_annee(pib):
    r = recette_tva_taux(0.21, pib, CHOMAGE_BASE)
    r_base = recette_tva_taux(0.21, PIB_BASE_2025_MD_EUR, CHOMAGE_BASE)
    assert r == pytest.approx(r_base * pib / PIB_BASE_2025_MD_EUR, rel=1e-12)


@pytest.mark.parametrize('taux', [0.15, 0.18, 0.195, 0.205, 0.21, 0.22, 0.225, 0.24, 0.25])
@pytest.mark.parametrize('chomage', [CHOMAGE_BASE, 0.11])
def test_seul_le_coefficient_d_assiette_change(taux, chomage):
    """Même forme qu'avant (élasticités, chômage, coude) : rapport constant à l'ancienne formule."""
    rapport = C.TVA_ASSIETTE_TAUX_NORMAL_PART_PIB / (0.53 * 0.9)
    assert recette_tva_taux(taux, 3100.0, chomage) == pytest.approx(
        _ancienne_recette(taux, 3100.0, chomage) * rapport, rel=1e-12)
    assert recette_tva_taux(0.20, 3100.0, chomage) == 0.0
