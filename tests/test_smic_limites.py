"""Hausse du SMIC : les trois limites déclarées de l'ancrage sur le Trésor, chiffres liés à la mesure (lot SMIC).

Arbitrage du mainteneur (16/11/2026) : le coût d'une hausse du SMIC suit le Trésor (groupe d'experts 2017, modèle
statique) ; trois limites sont déclarées dans METHODOLOGIE (§ SMIC), chacune avec son sens et son chiffre, sans
nouvel élément sur les écrans. Ce test recalcule ces chiffres sur les programmes publiés qui relèvent le SMIC
(dérivés des scénarios, mode cadre 2028, pleine précision) et vérifie qu'ils sont ceux de la documentation :

1. coût au bas de la fourchette publiée : l'écart de solde par point entre l'OFCE (2012 : −0,020 ; 2024 : −0,3/12,4
   ≈ −0,024 point de PIB) et le Trésor (−240 M€ de 2017 mis à l'échelle), ajouté en coût budgétaire pur, sans effet de
   demande ;
2. effet direct sur le chômage du moteur (0,025 point par point) ramené à l'effet net de l'OFCE (0,007) ;
3. revenu net des salariés du privé (canal ménages du levier, 2032) et emplois de l'effet net de l'OFCE
   (−2 300 par point à un an), absents du PIB.

Aussi (contre-vérification finale) : la lecture à la valeur du droit en vigueur, seule valeur neutre lue telle
quelle, et ses baisses en mode cadre jusqu'à la référence portée à l'année ; la limite d'une baisse du SMIC (paie
publique non réduite : une baisse coûte au budget et soutient l'activité).
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
# OFCE 2012 : −0,02 point de PIB par point ; OFCE 2024 : −0,3 point pour 12,4 % (tableau 1), non arrondi.
OFCE = {'2012': 0.020, '2024': 0.3 / 12.4}
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


# --- Lecture à la valeur du droit et limite d'une baisse (contre-vérification finale, I1 et m1) -------------------

def _cadre(montant=None, annee_debut=DEBUT):
    mesures = {'smic': {'montant_brut': montant}} if montant is not None else {}
    sim = BudgetSimulatorV45(periods=10, mesures=mesures, annee_debut=annee_debut)
    df, _, rapport = sim.simulate()
    impacts = {an['Année']: an.get('smic') or {} for an in rapport['measure_impacts_by_year']}
    return sim, df.set_index('Année'), impacts


def _pct(x, d=2):
    return _fr(abs(100 * x), d)


def test_lecture_a_la_valeur_du_droit_et_baisse_chiffres_dans_la_documentation(monkeypatch):
    """§ SMIC : la valeur du droit est la seule valeur neutre lue telle quelle ; tout autre montant est un SMIC de
    l'année d'application (saut à la valeur du droit, baisses jusqu'à la référence portée à l'année) ; une baisse
    coûte au budget et soutient l'activité (paie publique non réduite). Chiffres recalculés, mode cadre 2028 contre
    la référence sans programme ; mode historique pour la lecture continue."""
    monkeypatch.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
    REF = C.SMIC_BRUT_MENSUEL_REFERENCE_EUR
    sim0, d0, _ = _cadre()
    idx = sim0._indice_prix_par_annee
    ref_2028 = REF * idx[DEBUT] / idx[C.SMIC_ANNEE_DE_REFERENCE]

    def hausse(montant):
        sim, _, _ = _cadre(montant)
        i = sim._indice_prix_par_annee
        return montant / (REF * i[DEBUT] / i[C.SMIC_ANNEE_DE_REFERENCE]) - 1

    sim_h, _, impacts_h = _cadre(1900.0, annee_debut=None)
    assert impacts_h[2026]['chomage'] == pytest.approx((1900.0 / REF - 1) * 0.025, rel=1e-12)
    h_centime, h_1900, h_1950 = hausse(REF + 0.01), hausse(1900.0), hausse(1950.0)
    assert h_centime < h_1900 < 0 < h_1950

    # Baisse : 20 M€ de 2017 par point (paie publique non réduite), activité soutenue des deux côtés.
    cout_baisse = sum(v for k, v in T.items() if k != 'paie_publique')
    assert cout_baisse == 20.0

    def pib_reel_2032(df):
        g = 1.0
        for a in range(DEBUT, 2033):
            g *= (1 + df.at[a, 'Croissance %'] / 100) / (1 + d0.at[a, 'Croissance %'] / 100)
        return 100 * (g - 1)

    haut, bas = round(ref_2028, 2) + 50, round(ref_2028, 2) - 50
    _, d_haut, _ = _cadre(haut)
    _, d_bas, _ = _cadre(bas)
    assert pib_reel_2032(d_haut) > pib_reel_2032(d_bas) > 0
    minimum = 1400.0
    _, d_min, imp_min = _cadre(minimum)
    solde_min = sum(imp_min[a].get('recettes', 0) - imp_min[a].get('depenses', 0) for a in range(DEBUT, 2033))
    dette_min = d_min.at[2032, 'Dette/PIB %'] - d0.at[2032, 'Dette/PIB %']
    chomage_min = d_min.at[2032, 'Chômage %'] - d0.at[2032, 'Chômage %']
    assert solde_min < 0 and dette_min < 0 and chomage_min < 0

    methodologie = ' '.join(re.sub(r'\n>\s?', ' ', (RACINE / 'docs' / 'METHODOLOGIE.md')
                                   .read_text(encoding='utf-8')).split())
    for attendu in (
            f"(1 900 € : hausse de {_pct(1900.0 / REF - 1)} %)",
            f"En 2028 (référence portée à {f'{ref_2028:,.2f}'.replace(',', ' ').replace('.', ',')} €)",
            f"1 867,03 € une baisse de {_pct(h_centime)} %, 1 900 € une baisse de {_pct(h_1900)} %",
            f"(1 950 € : +{_pct(h_1950)} %)",
            f"Une baisse coûte donc au budget, {_fr(cout_baisse, 0)} M€ de 2017 par point",
            f"à ±{_pct(50 / round(ref_2028, 2))} % autour de la référence portée à l'année, PIB réel 2032 "
            f"+{_fr(pib_reel_2032(d_haut), 3)} % pour la hausse et +{_fr(pib_reel_2032(d_bas), 3)} % pour la baisse",
            f"(1 400 €, baisse de {_pct(hausse(minimum))} %), le solde direct du levier se dégrade de "
            f"{_fr(-solde_min, 1)} Md€ sur 2028-2032, mais la dette 2032 baisse de {_fr(-dette_min, 2)} point",
            f"(chômage 2032 plus bas de {_fr(-chomage_min, 2)} point)"):
        assert attendu in methodologie, attendu
