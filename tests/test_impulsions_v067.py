"""Impulsions budgétaires et agrégation des multiplicateurs (v0.6.7, audit 10/2026,
bloc A constats 1 et 2 — ``engine/growth.py``).

Ce que la v0.6.6 faisait, mesuré (``docs/plans/audit-codex-2026-10/bloc-A-macro.md``
du repo parent) :

1. **Agrégation** : multiplicateur = moyenne des multiplicateurs SIGNÉS pondérée
   par l'effort BRUT, appliquée à l'effort NET. Banc de l'auditeur (PIB 3 000,
   dette < 100 %) : 40 Md€ d'investissement + 20 Md€ d'impôts → +0,253 pt au
   lieu de la somme mesure par mesure +0,420 ; programme équilibré 40 + 40 → 0
   au lieu de +0,120 ; consolidation nette 40 + 50 → +0,060 au lieu de −0,030
   (signe inversé). Au banc du bloc A (dette 116 %) : 0,235 vs 0,388 ; 0 vs
   0,103 ; +0,057 vs −0,039.
2. **Temporalité** : une impulsion n'était stockée qu'au changement du hash de
   ``self.mesures`` — constant pendant une simulation — donc UNE impulsion par
   scénario, égale au niveau de la première année ; la montée en charge n'était
   jamais multipliée, et les résidus s'arrêtaient net dès que l'effort courant
   repassait sous 0,1 % du PIB.

Contrat verrouillé ici : impulsion(t, m) = VARIATION annuelle de l'effort du
levier m (en % du PIB), effet(t) = Σ_m Σ_âge k_m × impulsion(t−âge, m) ×
profil_m(âge), résidus sommés sans condition sur l'effort courant.
"""
import math

import pytest

from budget_simulator.simulator import BudgetSimulatorV45

PIB = 3000.0
# Banc de l'auditeur : dette < 110 % → pas d'ajustement « dette élevée »
# (l'éviction, retirée au lot 1, ne jouait pas non plus sous 100 %) ; gap −0,5 %
# → pas de régime récession.
ETAT = dict(output_gap=-0.005, unemployment_gap=0.0,
            debt_ratio=0.95, unemployment=0.076, deficit_ratio=-0.05,
            interest_rate=0.03)
P_TAX = BudgetSimulatorV45.DECAY_PROFILE_TAXES
# Profil d'investissement de la table de l'audit (celui de la v3.1). Lot 6 (release de paramètres,
# 16/11/2026) : le profil du moteur est calé sur le tableau du FMI ; le banc garde celui de l'audit,
# comme il garde ses coefficients, sans quoi il ne reproduirait plus les chiffres de l'auditeur.
P_INV = (0.45, 0.65, 0.45, 0.25, 0.12, 0.06)


def _effets(impacts_par_annee, etat=ETAT):
    """Points de croissance dus aux leviers, année par année : simulateur frais
    nourri d'impacts synthétiques (Md€, ceux que ``calculate_growth`` lit dans
    ``_last_impacts``), MOINS la même suite d'appels sans aucun impact (même
    graine → même bruit, même traînée de dette)."""
    def suite(seq):
        profil_du_moteur = BudgetSimulatorV45.DECAY_PROFILE_INVEST
        BudgetSimulatorV45.DECAY_PROFILE_INVEST = P_INV
        try:
            return _suite(seq)
        finally:
            BudgetSimulatorV45.DECAY_PROFILE_INVEST = profil_du_moteur

    def _suite(seq):
        sim = BudgetSimulatorV45(periods=10, mesures={'tva_rate': {'taux': 0.21}})
        # Table de multiplicateurs de l'AUDIT (v0.6.6 : 0,50 / 0,35 / 0,60 / 0,50) :
        # le banc reproduit les chiffres de l'auditeur ; les propriétés testées
        # (somme signée, additivité, résidus) ne dépendent pas des valeurs de k,
        # recalibrées « centrales » plus loin en v0.6.7.
        m = sim.multipliers.base_multipliers
        m['consolidation'].update(tax_based=-0.50, spending_based=-0.60)
        m['expansion'].update(tax_cuts=0.35, transferts=0.50)
        # Investissement de la table de l'audit (1,2 ; recalé à 1,31 au lot 6, release de
        # paramètres) : fixé ici, sans quoi le banc ne reproduirait plus l'auditeur.
        m['expansion'].update(investissement=1.2)
        m['consolidation'].update(investissement=-1.2)
        sim.pib_nominal = PIB
        out = []
        for t, impacts in enumerate(seq, start=1):
            sim._last_impacts = impacts
            # Lot 1 (15/11/2026) : la croissance ne lit plus ni l'effort net ni la
            # composition de l'expansion (éviction retirée) ; seules les impulsions,
            # tirées de _last_impacts, portent le budget.
            out.append(sim.calculate_growth(t, dict(etat)))
        return out
    avec, sans = suite(impacts_par_annee), suite([{}] * len(impacts_par_annee))
    return [(a - b) * 100 for a, b in zip(avec, sans)]


def INV(x):
    return {'transition_ecologique': {'depenses': x, 'recettes': 0.0}}


def TAX(x):
    return {'tva_rate': {'depenses': 0.0, 'recettes': x}}


# ---------------------------------------------------------------------------
# Constat 1 — agrégation : l'effet d'un programme est la SOMME SIGNÉE des
# effets de ses leviers.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('impots, attendu, v066', [
    (20.0, +0.420, +0.253),   # cas de l'auditeur
    (40.0, +0.120, 0.000),    # programme équilibré : effet keynésien non nul
    (50.0, -0.030, +0.060),   # consolidation nette : effet NÉGATIF
], ids=['40inv+20imp', '40inv+40imp_equilibre', '40inv+50imp_consolidation'])
def test_effet_d_un_programme_mixte_est_la_somme_signee(impots, attendu, v066):
    """1,2 × 40/3000 × 0,45 − 0,5 × impôts/3000 × 0,90 (pts) : investissement
    (expansion, profil INVEST) et hausse d'impôts (consolidation, profil TAXES)
    s'additionnent avec leur signe. ``v066`` = valeur de la v0.6.6, pour mémoire."""
    forme_fermee = 100 * (1.2 * 40 / PIB * P_INV[0] - 0.5 * impots / PIB * P_TAX[0])
    assert forme_fermee == pytest.approx(attendu, abs=5e-4)
    joint = _effets([{**INV(40.0), **TAX(impots)}])[0]
    separe = _effets([INV(40.0)])[0] + _effets([TAX(impots)])[0]
    assert joint == pytest.approx(forme_fermee, abs=1e-9), (
        f'joint {joint:+.3f} pt ≠ somme signée {forme_fermee:+.3f} pt (v0.6.6 : {v066:+.3f})')
    assert joint == pytest.approx(separe, abs=1e-9)


def test_banc_du_bloc_A_dette_116_strictement_additif():
    """Banc du bloc A (dette 116 % : ajustement « dette élevée » ×0,95) — v0.6.6 :
    0,235 joint contre 0,388 séparé. Jusqu'au lot 1, le seul terme non additif
    restant était l'éviction, qui portait sur le déficit NET du programme (joint
    0,398 = keynésien + éviction). Lot 1 (15/11/2026, éviction retirée) : le
    programme est STRICTEMENT additif, joint = somme keynésienne = somme des
    leviers séparés, propriété plus forte que la précédente."""
    etat = dict(ETAT, debt_ratio=1.16)
    joint = _effets([{**INV(40.0), **TAX(20.0)}], etat)[0]
    separe = _effets([INV(40.0)], etat)[0] + _effets([TAX(20.0)], etat)[0]
    keynes = 100 * 0.95 * (1.2 * 40 / PIB * P_INV[0] - 0.5 * 20 / PIB * P_TAX[0])
    assert joint == pytest.approx(keynes, abs=1e-9)
    assert joint == pytest.approx(separe, abs=1e-9)
    assert joint == pytest.approx(0.399, abs=5e-4)


# ---------------------------------------------------------------------------
# Constat 2 — temporalité : chaque variation annuelle est une impulsion.
# ---------------------------------------------------------------------------

def test_montee_en_charge_meme_cumul_qu_une_bascule_immediate():
    """Additivité : 0 → X en 4 marches égales produit le MÊME effet cumulé
    qu'une bascule immédiate à X — étalé dans le temps (convolution des
    marches avec le profil), pas amputé des trois quarts."""
    x = 30.0
    rampe = [TAX(x * min(t, 4) / 4) for t in range(1, 11)]
    immediat = [TAX(x)] * 10
    e_rampe, e_imm = _effets(rampe), _effets(immediat)
    k = 0.5 * x / PIB * 100
    assert sum(e_imm) == pytest.approx(-k * sum(P_TAX), abs=1e-9)
    assert sum(e_rampe) == pytest.approx(sum(e_imm), abs=1e-9), (
        f'rampe {sum(e_rampe):+.4f} vs immédiat {sum(e_imm):+.4f} pt cumulés')
    for t in range(10):   # marche s (0..3) d'âge t − s à l'année t
        conv = -k / 4 * sum(P_TAX[t - s] for s in range(min(t, 3) + 1) if t - s < len(P_TAX))
        assert e_rampe[t] == pytest.approx(conv, abs=1e-9), t


def test_residus_survivent_au_retrait_et_le_niveau_revient_a_zero():
    """Mesure temporaire (X trois ans, puis 0) : en v0.6.6 l'effet tombait à 0
    l'année du retrait (résidus sous la condition « effort courant > 0,1 % »).
    Désormais le retrait est une impulsion de signe opposé ; les résidus de
    l'entrée continuent ; l'effet cumulé — l'effet de NIVEAU sur le PIB —
    revient exactement à zéro une fois les deux profils épuisés."""
    x = 30.0
    seq = [TAX(x)] * 3 + [{}] * 7
    e = _effets(seq)
    k = 0.5 * x / PIB * 100
    assert e[3] == pytest.approx(-k * (P_TAX[3] - P_TAX[0]), abs=1e-9)
    assert e[3] > 0   # retrait d'une hausse d'impôts : soutien la 1re année
    assert sum(e) == pytest.approx(0.0, abs=1e-12)


def test_franchissement_de_zero_scinde_l_impulsion():
    """Un flux qui passe d'une baisse à une hausse d'impôts en un an : la part
    « retrait de la baisse » porte le multiplicateur d'une baisse (0,35), la
    part « hausse » celui d'une hausse (0,50). Conséquence : l'effet cumulé ne
    dépend que du niveau final, pas du chemin (même état macro)."""
    x = 30.0
    direct = _effets([TAX(x)] + [TAX(x)] * 9)
    detour = _effets([TAX(-x)] + [TAX(x)] * 9)
    k_hausse, k_baisse = 0.5 * x / PIB * 100, 0.35 * x / PIB * 100
    assert detour[0] == pytest.approx(+k_baisse * P_TAX[0], abs=1e-9)
    assert detour[1] == pytest.approx(k_baisse * (P_TAX[1] - P_TAX[0]) - k_hausse * P_TAX[0], abs=1e-9)
    assert sum(detour) == pytest.approx(sum(direct), abs=1e-9)


def test_multiplicateur_net_des_leviers_a_coefficient_propre():
    """smic et fraude_fiscale portent un coefficient calibré sur leur effet NET
    (FiscalMultipliers : indépendant de la composition) : leurs deux flux sont
    agrégés avant multiplication, les autres leviers sont multipliés flux par
    flux. La liste et les branches de ``get_multiplier`` ne peuvent diverger."""
    from budget_simulator.simulator import FiscalMultipliers
    fm = FiscalMultipliers()
    assert FiscalMultipliers.MESURES_MULTIPLICATEUR_NET == {'smic', 'fraude_fiscale'}
    etat = dict(output_gap=0.0, unemployment_gap=0.0, debt_ratio=0.95, interest_rate=0.03)
    for m in FiscalMultipliers.MESURES_MULTIPLICATEUR_NET:
        vals = {fm.get_multiplier(sens, comp, etat, 2, m)
                for sens in ('consolidation', 'expansion')
                for comp in ({'depenses': 1, 'recettes': 0, 'investissement': 0},
                             {'depenses': 0, 'recettes': 1, 'investissement': 0})}
        assert len(vals) == 1, (m, vals)
    # Fraude : 0,1 Md€ de coût de contrôle + 0,6 Md€ recouvrés = 0,5 net à −0,40.
    e = _effets([{'fraude_fiscale': {'depenses': 0.1, 'recettes': 0.6}}])[0]
    assert e == pytest.approx(-0.40 * 0.5 / PIB * 100 * P_TAX[0], abs=1e-9)


def test_simulation_complete_chaque_variation_est_multipliee_une_fois(monkeypatch):
    """Fraude fiscale seule (effort 1,0) : en v0.6.6, UNE impulsion de 0,104 %
    du PIB stockée en 2027 alors que l'effort monte à 0,469 % en 2030. Désormais
    la somme des impulsions stockées jusqu'à l'année t égale le niveau d'effort
    du budget de t : rien n'est perdu, rien n'est compté deux fois.
    Re-déclaré au lot 6 (calendrier de l'impulsion) : jusque-là, ce niveau était
    celui du budget de t−1 rapporté au PIB de t−1 (impulsion laguée d'un an) ;
    c'est désormais celui du budget de t, évalué hors de son effet propre
    (niveaux rendus par ``_niveaux_hors_effet_propre``), qui agit dès son année.
    Il reste à 1 % près du niveau publié (budget évalué à l'état final) : l'écart est l'effet
    propre du budget sur le PIB de son année. L'égalité EXACTE au niveau publié est vérifiée là
    où cet effet est nul (test suivant, sans rétroaction keynésienne)."""
    import budget_simulator.engine.orchestrator as orch
    monkeypatch.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
    ex_ante = {}

    class _Sonde(BudgetSimulatorV45):
        def _niveaux_hors_effet_propre(self, year, *args):
            niveaux = super()._niveaux_hors_effet_propre(year, *args)
            ex_ante[year] = niveaux.get(('fraude_fiscale', 'solde'), 0.0)
            return niveaux

    sim = _Sonde(periods=10, mesures={'fraude_fiscale': {'effort': 1.0}})
    df, _, rapport = sim.simulate()
    impacts = rapport['measure_impacts_by_year']
    pib = list(df['PIB'])   # PIB nominal pleine précision, index 0 = 2025
    niveaux = []
    for t in range(1, 11):
        cumul = sum(d for (an, m, _c, _s), (d, _k, _p) in sim._fiscal_impulses.items()
                    if m == 'fraude_fiscale' and an <= t)
        niveaux.append(ex_ante[2025 + t])
        assert cumul == pytest.approx(niveaux[-1], rel=1e-12, abs=1e-15), t
        v = impacts[t]['fraude_fiscale']
        assert niveaux[-1] == pytest.approx((v['recettes'] - v['depenses']) / pib[t], rel=1e-2), t
    # Montée 0,10 % (budget 2026) → 0,47 % (2030), puis décrue : toutes les
    # marches, y compris la décrue, sont des impulsions.
    assert niveaux[0] == pytest.approx(0.00104, abs=2e-5)
    assert max(niveaux) == pytest.approx(0.0047, abs=1e-4)


@pytest.mark.parametrize('annee_debut', [None, 2028])
def test_somme_des_impulsions_egale_au_niveau_publie_sans_retroaction(monkeypatch, annee_debut):
    """Lot 6, revue adverse : l'ancrage EXACT au niveau publié. Dans le moteur complet, le niveau
    ex ante (test précédent) est rapporté au PIB de l'année sans l'effet propre du budget, qui
    n'est pas publié : il s'écarte du niveau publié (budget à l'état final) de cet effet propre,
    1 % au plus ici, par construction. Quand la rétroaction keynésienne est neutralisée
    (laboratoire des effets directs, multiplicateurs nuls), l'effet propre est nul, les deux
    évaluations coïncident, et la somme des impulsions stockées jusqu'à t égale EXACTEMENT
    l'effort publié du budget de t (impacts du rapport rapportés au PIB nominal publié), chaque
    année et dans les deux modes : rien n'est perdu, rien n'est compté deux fois."""
    import budget_simulator.engine.orchestrator as orch
    from effets_directs import SansRetroactionKeynesienne
    monkeypatch.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
    sim = SansRetroactionKeynesienne(periods=10, mesures={'fraude_fiscale': {'effort': 1.0}},
                                     annee_debut=annee_debut)
    df, _, rapport = sim.simulate()
    impacts = rapport['measure_impacts_by_year']
    pib = list(df['PIB'])
    non_nuls = 0
    for t in range(1, 11):
        cumul = sum(d for (an, m, _c, _s), (d, _k, _p) in sim._fiscal_impulses.items()
                    if m == 'fraude_fiscale' and an <= t)
        v = impacts[t].get('fraude_fiscale', {'recettes': 0.0, 'depenses': 0.0})
        publie = (v['recettes'] - v['depenses']) / pib[t]
        assert cumul == pytest.approx(publie, rel=1e-12, abs=1e-15), t
        non_nuls += publie != 0.0
    assert non_nuls >= 5


@pytest.mark.parametrize('periods', [1, 3, 10])
def test_aucune_impulsion_au_statu_quo(periods):
    sim = BudgetSimulatorV45(periods=periods, mesures={})
    sim.simulate()
    assert sim._fiscal_impulses == {}
    assert not math.isnan(sim.output_gap_courant)
