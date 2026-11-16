"""Hausse du SMIC : les trois limites déclarées de l'ancrage sur le Trésor, chiffres liés à la mesure (lot SMIC).

Arbitrage du mainteneur (16/11/2026) : le coût d'une hausse du SMIC suit le Trésor (groupe d'experts 2017, modèle
statique) ; trois limites sont déclarées dans METHODOLOGIE (§ SMIC), chacune avec son sens et son chiffre, sans
nouvel élément sur les écrans. Ce test recalcule ces chiffres sur les programmes publiés qui relèvent le SMIC
(dérivés des scénarios, mode cadre 2028, pleine précision) et vérifie qu'ils sont ceux de la documentation :

1. coût au bas de la fourchette publiée : l'écart de solde par point entre l'OFCE (2012 : −0,020 ; 2024 : −0,024
   point de PIB) et le Trésor (−240 M€ de 2017 mis à l'échelle), ajouté en coût budgétaire pur, sans effet de
   demande ;
2. effet direct sur le chômage du moteur (0,025 point par point) ramené à l'effet net de l'OFCE (0,007) ;
3. revenu net des salariés du privé (canal ménages du levier, 2032) et emplois de l'effet net de l'OFCE
   (−2 300 par point à un an), absents du PIB.
"""
import json
import os
import re
from pathlib import Path

import pytest

import budget_simulator.engine.orchestrator as orch
from budget_simulator import constants as C
from budget_simulator.simulator import BudgetSimulatorV45

RACINE = Path(__file__).resolve().parents[1]
DEBUT = 2028
T = C.SMIC_TRESOR_SOLDE_PAR_POINT_M_EUR_2017
# Solde par point du Trésor, en point de PIB (statique : il ne dépend pas de l'année).
TRESOR_PT_PIB = -sum(T.values()) * C.SALAIRES_BRUTS_2025_MD / C.SALAIRES_BRUTS_2017_MD / C.PIB_BASE_2025_MD_EUR / 10
OFCE = {'2012': 0.020, '2024': 0.024}
CHOMAGE_OFCE_NET = 0.007
EMPLOIS_OFCE_NET_PAR_POINT = 2300


def _scenarios():
    chemin = (os.environ.get('BUDGETLAB_SCENARIOS_JSON') or '').strip()
    if not chemin or not Path(chemin).exists():
        pytest.skip('scénarios publiés absents (BUDGETLAB_SCENARIOS_JSON)')
    return json.loads(Path(chemin).read_text(encoding='utf-8'))


def _points(impact, gdp):
    echelle = C.SALAIRES_BRUTS_2025_MD / C.SALAIRES_BRUTS_2017_MD * gdp / C.PIB_BASE_2025_MD_EUR / 1000
    t = (T['prelevements_des_salaries'] + T['impot_sur_le_revenu']
         + T['cotisations_employeurs_nettes_des_allegements'])
    return float(impact.get('recettes', 0) or 0) / (t * echelle)


class _Variante(BudgetSimulatorV45):
    cout_ofce = None
    chomage = None
    MESURES_HORS_DEMANDE_INTERIEURE = BudgetSimulatorV45.MESURES_HORS_DEMANDE_INTERIEURE | {'zz_ecart_ofce'}

    def apply_measures(self, year, spending, revenues, gdp, inflation, unemployment):
        sp, rv, imp = super().apply_measures(year, spending, revenues, gdp, inflation, unemployment)
        x = imp.get('smic')
        if not isinstance(x, dict) or not x.get('recettes'):
            return sp, rv, imp
        h = _points(x, gdp)
        self.journal[year] = (h, float(x['menages']['salaires_prives']))
        imp = dict(imp)
        if self.cout_ofce is not None:
            extra = (self.cout_ofce - TRESOR_PT_PIB) / 100 * h * gdp
            imp['zz_ecart_ofce'] = {'depenses': extra, 'recettes': 0.0}
            sp += extra
        if self.chomage is not None and x.get('chomage'):
            imp['smic'] = {**x, 'chomage': x['chomage'] * self.chomage / 0.025}
        return sp, rv, imp


def _run(scenario, **variante):
    classe = type('V', (_Variante,), variante)
    sim = classe(periods=10, mesures=scenario['apiMeasures'], annee_debut=DEBUT,
                 profils=scenario.get('profils') or None)
    sim.journal = {}
    return sim.simulate()[0].set_index('Année'), sim.journal


def _fr(x, d):
    return f"{x:.{d}f}".replace('.', ',')


def _de_a(valeurs, d):
    bas, haut = _fr(min(valeurs), d), _fr(max(valeurs), d)
    return bas if bas == haut else f"{bas} à {haut}"


def _emplois(x):
    return f"{int(round(x, -2)):,}".replace(',', ' ')


@pytest.fixture(scope='module')
def mesures(request):
    scenarios = _scenarios()
    mp = pytest.MonkeyPatch()
    mp.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
    try:
        concernes = {n: s for n, s in scenarios.items()
                     if (s['apiMeasures'].get('smic') or {}).get('montant_brut', C.SMIC_BRUT_MENSUEL_REFERENCE_EUR)
                     != C.SMIC_BRUT_MENSUEL_REFERENCE_EUR}
        out = {}
        for nom, s in concernes.items():
            base, journal = _run(s)
            r = {'points': journal[DEBUT][0], 'salaires_2032': journal[2032][1]}
            for cle, kw in (('2012', {'cout_ofce': OFCE['2012']}), ('2024', {'cout_ofce': OFCE['2024']}),
                            ('chomage', {'chomage': CHOMAGE_OFCE_NET})):
                v, _ = _run(s, **kw)
                r[cle] = {c: float(v.at[2032, col] - base.at[2032, col])
                          for c, col in (('dette', 'Dette/PIB %'), ('chomage', 'Chômage %'))}
            out[nom] = r
        return out
    finally:
        mp.undo()


def test_non_vacuite_et_sens(mesures):
    assert len(mesures) >= 2, 'non-vacuité : au moins deux programmes publiés relèvent le SMIC'
    for r in mesures.values():
        assert r['points'] > 0
        assert r['2024']['dette'] > r['2012']['dette'] > 0        # (1) favorable aux programmes : coût sous-estimé
        assert r['chomage']['chomage'] < 0 and r['chomage']['dette'] < 0   # (2) sens contraire
        assert r['salaires_2032'] > 0


def test_chiffres_des_limites_dans_la_documentation(mesures):
    v = list(mesures.values())
    methodologie = ' '.join(re.sub(r'\n>\s?', ' ', (RACINE / 'docs' / 'METHODOLOGIE.md')
                                   .read_text(encoding='utf-8')).split())
    for attendu in (
            f"Le Trésor chiffre −{_fr(TRESOR_PT_PIB, 4)} point de PIB par point de hausse",
            f"la dette 2032 serait plus haute de {_de_a([r['2012']['dette'] for r in v], 2)} point (écart de "
            f"l'OFCE 2012) et de {_de_a([r['2024']['dette'] for r in v], 2)} point (OFCE 2024)",
            f"le chômage 2032 serait plus bas de {_de_a([-r['chomage']['chomage'] for r in v], 2)} point et la "
            f"dette 2032 plus basse de {_de_a([-r['chomage']['dette'] for r in v], 2)} point",
            f"(de {_de_a([r['salaires_2032'] for r in v], 1)} Md€ en 2032)",
            f"soit de {_emplois(min(EMPLOIS_OFCE_NET_PAR_POINT * r['points'] for r in v))} à "
            f"{_emplois(max(EMPLOIS_OFCE_NET_PAR_POINT * r['points'] for r in v))} emplois"):
        assert attendu in methodologie, attendu
