"""Éviction (« crowding-out ») et composition de l'expansion (v0.6.10, contre-audit
externe V2-01) — RE-DÉCLARÉ EN ACTE au lot 1 des corrections d'équations (15/11/2026).

Constat de l'auditeur (v0.6.7, reproduit au millième sur v0.6.9) : la part
d'investissement lue par l'éviction divisait des flux BRUTS par levier par des flux
NETS agrégés ; un investissement financé en partie par une coupe la portait au-dessus
de 1, l'intensité devenait NÉGATIVE et l'« éviction » SOUTENAIT l'expansion
(contre-exemple : +20 Md€ d'investissement de transition, dotation des collectivités
120 → 110 ; part 2027 = 2,000, effet +0,001303 pt de croissance). Corrigé en v0.6.10 :
part dans [0 ; 1] par construction, éviction jamais positive.

Lot 1 : l'éviction est RETIRÉE (arbitrage du mainteneur du 21/10/2026, « option C » ;
garde ``tests/test_eviction_retiree.py``), et avec elle la part d'investissement de
l'expansion, sans autre lecteur. Ce que ce fichier verrouillait n'a plus d'objet et en
est retiré, avec son motif :

- convention et bornes de ``part_investissement_expansion`` (fonction supprimée),
  tirages synthétiques, paires aux bornes des domaines et 200 programmes tirés au
  hasard (ils vérifiaient part ∈ [0 ; 1] et éviction ≤ 0) ;
- intensité aux bornes, constantes ``EVICTION_*`` sans littéral (constantes supprimées) ;
- programme figé du contre-audit (``tests/snapshots/programme_fige_eviction_v0610.json``,
  retiré avec ses deux tests : il ne servait qu'à la part et au signe de l'éviction) ;
- marche du seuil de dette de 100 % (seuil supprimé : plus de marche à lisser).

Ce qui reste vrai, et reste verrouillé ici : les flux du contre-exemple ; la
convention de flux par levier, que lisent les impulsions keynésiennes ; la
disjonction des leviers d'investissement et des leviers à multiplicateur net ;
aucune marche de croissance quand l'effort net change de signe ; des docs publiques
qui déclarent l'éviction retirée.
"""
from pathlib import Path

import pytest

from budget_simulator.engine.growth import flux_par_levier
from budget_simulator.simulator import BudgetSimulatorV45, FiscalMultipliers

CONTRE_EXEMPLE = {
    'transition_ecologique': {'investissement': 20},
    'collectivites': {'dotation': 110},
}
IDX_2027 = 2  # année 2027 = indice 2 de la boucle (2025 = base, indice 0)
INVEST = BudgetSimulatorV45.INVESTMENT_CORE_MEASURES
NETTES = FiscalMultipliers.MESURES_MULTIPLICATEUR_NET


def _impacts(mesures):
    """Impacts par levier rendus par ``apply_measures``, par année civile."""
    sim = BudgetSimulatorV45(periods=10, mesures=mesures)
    appliquer, impacts = sim.apply_measures, {}

    def espion(year, *args, **kwargs):
        dep, rec, imp = appliquer(year, *args, **kwargs)
        impacts[year] = {m: dict(v) for m, v in imp.items() if isinstance(v, dict)}
        return dep, rec, imp

    sim.apply_measures = espion
    sim.simulate()
    return impacts


def test_contre_exemple_flux_initiaux():
    """Le contre-exemple est bien celui de l'auditeur : +20 Md€ d'investissement,
    −10 Md€ de dotations, rien d'autre (budget 2026, lu par la macro de 2027)."""
    imp = _impacts(CONTRE_EXEMPLE)[2026]
    assert round(imp['transition_ecologique']['depenses'], 3) == 20.0
    assert round(imp['collectivites']['depenses'], 3) == -10.0
    autres = {m: v for m, v in imp.items() if m not in CONTRE_EXEMPLE
              and (abs(v.get('depenses', 0) or 0) > 1e-9 or abs(v.get('recettes', 0) or 0) > 1e-9)}
    assert not autres, autres


def test_leviers_investissement_et_leviers_nets_disjoints():
    """Un levier d'investissement compté sur son SOLDE ne serait jamais multiplié comme
    investissement (canal 'solde') : les deux ensembles doivent rester disjoints."""
    assert not INVEST & NETTES


def test_impulsions_lisent_flux_par_levier():
    """Les niveaux d'impulsion sont exactement les flux de ``flux_par_levier`` / PIB
    (avant le lot 1 : « la même décomposition que l'éviction »)."""
    impacts = {'education': {'depenses': 12.0, 'recettes': 0.0}, 'smic': {'depenses': 3.0, 'recettes': 1.0},
               'tva_rate': {'depenses': 0.0, 'recettes': -4.0}}
    sim = BudgetSimulatorV45(periods=10, mesures={})
    sim.pib_nominal = 3000.0
    sim._last_impacts = impacts
    sim._stocker_impulsions(1, dict(output_gap=0.0, debt_ratio=1.1, unemployment_gap=0.0, interest_rate=0.03))
    assert sim._niveaux_impulsion == {k: v / 3000.0 for k, v in flux_par_levier(impacts, NETTES, leviers_de_transfert=BudgetSimulatorV45.TRANSFER_MEASURES, prestations_non_reclassees=BudgetSimulatorV45.PRESTATIONS_NON_RECLASSEES).items()}


def _croissance_et_effort_2027(mesures):
    """(croissance 2027, effort net du budget 2026) du moteur complet, pleine précision."""
    import budget_simulator.engine.orchestrator as orch
    mp = pytest.MonkeyPatch()
    mp.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
    try:
        df, detail, _ = BudgetSimulatorV45(periods=10, mesures=mesures).simulate()
    finally:
        mp.undo()
    return float(df['Croissance %'].iloc[IDX_2027]), float(detail['Effort_Budgétaire %'].iloc[1])


def test_aucune_marche_quand_l_effort_net_change_de_signe():
    """Investissement x financé par −10 Md€ de dotations : l'effort net 2026 s'annule en
    x = 10. Jusqu'en v0.6.9 la part (x / |x − 10|) y divergeait et la croissance 2027
    sautait de +0,002 pt ; un plancher sur l'effort ferait de même. À travers le
    franchissement, la croissance ne varie pas plus que sur un intervalle voisin de même
    largeur. Depuis le lot 1, la croissance ne lit plus l'effort net : la propriété tient
    par construction et reste gardée."""
    d = 1e-4
    (g0, _), (g1, e1), (g2, e2), (g3, _) = (
        _croissance_et_effort_2027(dict(CONTRE_EXEMPLE, transition_ecologique={'investissement': 10 + k * d}))
        for k in (-3, -1, 1, 3))
    assert e1 > 0 > e2  # l'effort net change bien de signe entre les deux points centraux
    assert abs(g2 - g1) <= 2 * max(abs(g1 - g0), abs(g3 - g2)), (g1 - g0, g2 - g1, g3 - g2)


def test_docs_publics_declarent_l_eviction_retiree():
    """Les deux docs publics (copiés sur le site par sync_public_docs) décrivent l'éviction
    telle qu'elle est désormais : retirée. Aucun ne lui prête de source (l'un affichait
    jusqu'en v0.6.10 « Litterature standard sur l'eviction », une source qui n'existe pas)."""
    docs = Path(__file__).resolve().parent.parent / 'docs'
    explication = (docs / 'EXPLICATION_MODELE_ECONOMIQUE.md').read_text(encoding='utf-8')
    section = explication.split('### 3. Crowding-Out', 1)[1].split('\n### ', 1)[0]
    assert 'RETIR' in section and 'option C' in section, section[:300]
    methodo = (docs / 'METHODOLOGIE.md').read_text(encoding='utf-8')
    for nom, texte in (('EXPLICATION', explication), ('METHODOLOGIE', methodo)):
        assert "standard sur l'eviction" not in texte.lower() and 'eviction standard' not in texte.lower(), nom
