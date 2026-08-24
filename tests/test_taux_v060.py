"""
Tests-propriétés v0.6.0 — courbe de taux marginal ré-ancrée (audit externe 08/2026).

Contrat : taux_marginal(dette, effort) = ancre zone euro + spread France piloté.
- Ancre observée : 3,47 % à 117,6 % de dette (AFT, taux moyen pondéré des
  émissions, août 2026).
- Pentes du spread : 2 pb/pt (< 90 %), 3 pb/pt (90-120 %), 5,5 pb/pt
  (120-150 %), 8 pb/pt (> 150 %, extrapolation assumée).
- Monotonie STRICTE en dette à effort constant (le moteur v0.5.1 la violait :
  remise BCE inconditionnelle à > 150 % — contraire au critère d'éligibilité
  TPI, BCE 21/07/2022, qui exige de ne pas être en procédure de déficit
  excessif).
- Prime d'effort continue et symétrique : 20 pb/pt de PIB d'effort
  (FMI WEO oct. 2010 ch. 3 ; Furceri et al. 2025 ; Laubach 2009), amplifiée
  par la dette au-delà de 90 % (ACL, BCE WP 411), cap malus +60 pb,
  plafond bonus −45 pb (mission Jaravel/Ragot/Tavernier/Valla 07/2026,
  encadré 4 : −0,4 pt max sans repasser sous le point bas 2021).
- Plus de falaise +100 pb, plus de terme calendaire, plafond absolu 8 %
  (Portugal 2011 : spread 459 pb).

Sources détaillées : docs/plans (repo parent) + METHODOLOGIE.md § Taux.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from budget_simulator.simulator import BudgetSimulatorV45


@pytest.fixture(scope='module')
def sim():
    return BudgetSimulatorV45()


def _rate(sim, debt_ratio, effort=0.0, year=3):
    return sim.calculate_interest_rate(debt_ratio, year, effort)


# === Courbe : ancrage et forme ===

def test_ancrage_marche_aft(sim):
    """Au ratio de dette observé (117,6 %), le taux marginal doit retrouver le
    taux d'émission observé (3,47 %, AFT août 2026) — le cœur du constat 1."""
    assert 0.0340 <= _rate(sim, 1.176) <= 0.0355


def test_table_ancrage(sim):
    """Points de la table d'ancrage (METHODOLOGIE § Taux), tolérance ±5 pb."""
    attendus = {1.00: 0.0294, 1.15: 0.0339, 1.30: 0.0409, 1.50: 0.0519, 1.70: 0.0679}
    for d, taux in attendus.items():
        assert abs(_rate(sim, d) - taux) <= 0.0005, f"dette {d:.0%} : {_rate(sim, d):.4f} vs {taux:.4f}"


def test_monotonie_stricte_en_dette(sim):
    """Balayage 50 → 200 % par pas de 0,1 pt : le taux ne baisse JAMAIS quand
    la dette monte (échoue en v0.5.1 : 150,0 % → 2,31 % puis 150,1 % → 1,81 %)."""
    prev = -1.0
    d = 0.50
    while d <= 2.00:
        r = _rate(sim, d)
        assert r >= prev, f"violation de monotonie à {d:.1%} : {r:.4f} < {prev:.4f}"
        prev = r
        d = round(d + 0.001, 4)


def test_pas_de_terme_calendaire(sim):
    """Le taux dépend de l'état (dette, effort), jamais du calendrier —
    le terme `year > 5` de v0.5.1 n'avait aucune source."""
    for d in (1.10, 1.55, 1.80):
        assert _rate(sim, d, year=2) == _rate(sim, d, year=9)


def test_plafond_absolu_8_pct(sim):
    """Plafond de stress relevé à 8 % (l'ancien 5 % écrasait toute la branche
    > 146,7 % avec les nouvelles pentes)."""
    assert _rate(sim, 2.50) == pytest.approx(0.080)
    assert _rate(sim, 1.70) < 0.080


def test_consolidation_reduit_le_taux_a_dette_egale(sim):
    """À dette égale, l'effort de consolidation réduit le taux, près du plafond
    de bonus pour un effort soutenu. NB : le fait Grèce < France (2026) n'est
    PAS reproductible par une courbe assise sur le ratio COURANT — les marchés
    pricent la trajectoire anticipée ; limite documentée (METHODOLOGIE § design),
    le plafond de bonus −45 pb (mission 07/2026) prime sur ce fait de niveau."""
    bonus = _rate(sim, 1.435, effort=0.025) - _rate(sim, 1.435, effort=0.0)
    assert -0.0045 <= bonus <= -0.0040


# === Prime d'effort : continue, symétrique, bornée ===

def test_prime_symetrique(sim):
    """prime(+x) = −prime(−x) à dette fixée (symétrie retenue faute de source
    contraire — documentée comme choix § design)."""
    for effort in (0.005, 0.010, 0.015):
        bonus = _rate(sim, 1.15, effort) - _rate(sim, 1.15, 0.0)
        malus = _rate(sim, 1.15, -effort) - _rate(sim, 1.15, 0.0)
        assert bonus == pytest.approx(-malus, abs=1e-6)


def test_prime_continue_pas_de_falaise(sim):
    """Deux efforts distants de 0,01 pt de PIB → |Δtaux| ≤ 1 pb. Interdit la
    réintroduction de la falaise +100 pb de v0.5.1 (le vécu 2024-2026 = +21 pb)."""
    effort = -0.0140
    while effort >= -0.0180:
        r1 = _rate(sim, 1.25, effort)
        r2 = _rate(sim, 1.25, effort - 0.0001)
        assert abs(r2 - r1) <= 0.0001, f"falaise à effort {effort:.4f}"
        effort = round(effort - 0.0001, 6)


def test_prime_bornes(sim):
    """Cap malus +60 pb (≈ 2× le pic France 2024-2026) ; plafond bonus −45 pb
    (mission 07/2026 : −0,4 pt sans repasser sous le point bas 2021)."""
    base = _rate(sim, 1.30)
    assert _rate(sim, 1.30, -0.10) - base <= 0.0060 + 1e-9
    assert _rate(sim, 1.30, 0.10) - base >= -0.0045 - 1e-9


def test_prime_amplifiee_par_la_dette(sim):
    """Même effort, prime plus forte à dette plus haute (non-linéarité ACL) —
    sous le seuil de 90 % la prime reste la prime de base."""
    prime_115 = _rate(sim, 1.15, -0.01) - _rate(sim, 1.15)
    prime_140 = _rate(sim, 1.40, -0.01) - _rate(sim, 1.40)
    assert prime_140 > prime_115 > 0


def test_continuite_aux_frontieres_de_segments(sim):
    """Les segments du spread se raccordent continûment (pas de saut aux
    frontières 90/120/150 % — revue adverse 24/08)."""
    for frontiere in (0.90, 1.20, 1.50):
        gauche = _rate(sim, frontiere - 0.001)
        droite = _rate(sim, frontiere + 0.001)
        assert abs(droite - gauche) < 0.0003, f"saut à {frontiere:.0%}"


def test_monotonie_strictement_croissante_sous_le_plafond(sim):
    """STRICTEMENT croissante tant que le plafond de stress (8 %) n'est pas
    atteint — le plateau n'est admis qu'au plafond."""
    prev = -1.0
    d = 0.50
    while d <= 2.00:
        r = _rate(sim, d)
        if prev < 0.080 - 1e-9:
            assert r > prev, f"non STRICT à {d:.1%}"
        prev = r
        d = round(d + 0.005, 4)
