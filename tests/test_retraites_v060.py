"""
Tests-propriétés v0.6.0 — retraites : barème d'âge à rendement décroissant.

Le rendement d'une année d'âge décroît : ~14,2 Md€/an sur 62,75→64 (Sénat
l23-498 : 17,7 Md€ en 2030 / 1,25 an) mais ~6 Md€/an au-delà de 64 (COR
19/03/2026, Doc n° 3, tableau 4 : 0,2 pt de PIB au palier 64→65 — le pic des
liquidations à 62 ans n'existe plus au-delà). v0.5.1 : 16,0 linéaire partout,
+13 % au-dessus de sa propre cible ET surestimation forte des scénarios à
65 ans (LR, Horizons).

NB : le lot « fuite sociale 20 % + volet emploi COR » (jumelles
indissociables) a été implémenté puis RETIRÉ par la revue adverse du
24/08/2026 — sur-calibrage ~+49 % vs Cour 02/2025 T5, écho Okun divergent,
conflit de sources Sénat/Cour à réconcilier. Cf. constants.py § retraites et
le plan v0.6.1 (repo parent).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from budget_simulator.simulator import BudgetSimulatorV45
from budget_simulator.constants import (
    RETRAITES_COEFF_AGE_AVANT_SEUIL_MD_EUR,
    RETRAITES_COEFF_AGE_APRES_SEUIL_MD_EUR,
)

PLEIN_REGIME = 2031  # phasing 5 ans complet


def _delta_age(age, year=PLEIN_REGIME):
    s = BudgetSimulatorV45(periods=10, mesures={'retraites': {'age_depart': age}})
    d, _, _ = s._apply_retraites({}, {'age_depart': age}, year, 3100, 0.015, 0.075)
    return d


def test_bareme_segment_avant_64():
    """62,75 → 64 ans à plein régime : économie brute = 14,2 × 1,25 = 17,75 Md€
    (cible Sénat l23-498 pour 2030)."""
    attendu = -RETRAITES_COEFF_AGE_AVANT_SEUIL_MD_EUR * 1.25
    assert _delta_age(64.0) == pytest.approx(attendu, abs=1e-9)


def test_bareme_decroissant_au_dela_de_64():
    """L'année 64 → 65 rapporte ~6 Md€ bruts/an (COR T4), pas 14,2."""
    marginal_65 = _delta_age(65.0) - _delta_age(64.0)
    assert marginal_65 == pytest.approx(-RETRAITES_COEFF_AGE_APRES_SEUIL_MD_EUR, abs=1e-9)


def test_bareme_continu_en_64():
    """Pas de saut au franchissement du seuil (barème continu)."""
    assert abs(_delta_age(64.01) - _delta_age(64.0)) < 0.1


def test_bareme_symetrique_sous_la_reference():
    """Abaisser l'âge coûte le miroir du segment < 64 (choix prolongé par
    défaut sous 62,75 — la Cour 2021 suggère MOINS pour 60→62, surcoût des
    abaissements possiblement surestimé : documenté, à trancher v0.6.1)."""
    assert _delta_age(61.5) == pytest.approx(
        RETRAITES_COEFF_AGE_AVANT_SEUIL_MD_EUR * 1.25, abs=1e-9)
