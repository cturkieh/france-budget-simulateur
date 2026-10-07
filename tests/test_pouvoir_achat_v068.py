"""v0.6.8 — indice de pouvoir d'achat RDB-moteur, dans le moteur complet.

Les 9 tests RED du diagnostic (commit 37db8ba, docs/plans/v068-pouvoir-achat.md
du dépôt parent) mesuraient la part « micro » de la variation de l'ancien
indice (variation − croissance, capturée à l'entrée de `_borner_variation`).
Cette grandeur n'existe plus : l'indice est désormais un NIVEAU, RDB des
ménages / prix de la consommation / UC (engine/rdb.py). Chaque défaut prouvé
est donc re-testé dans la définition B, sur la même identité comptable :

- l'année d'entrée en vigueur (2026), la croissance, l'inflation et la masse
  salariale publique ne réagissent pas encore aux mesures (impulsion
  budgétaire laguée d'un an) : l'écart d'indice au statu quo est l'effet
  DIRECT, comparable aux euros que le levier déplace ;
- l'indice d'une année ne lit que les montants de cette année (aucune
  composition, aucune atténuation calendaire), vérifié sur la décomposition
  non arrondie `sim._rdb_trace`.
"""
import logging

import pytest

from budget_simulator.constants import (
    CROISSANCE_UC_ANNUELLE,
    HANDLER_FAILED_KEY,
    PART_MENAGES_FISCALITE_INDIRECTE,
    PART_NETTE_REMUNERATIONS_APU,
    REPERCUSSION_BAISSE_FISCALITE_INDIRECTE,
    REPERCUSSION_HAUSSE_FISCALITE_INDIRECTE,
    TAUX_EPARGNE_MENAGES_2025,
)
from budget_simulator.engine import rdb as rdb_module
from budget_simulator.handlers._types import canaux_menages
from budget_simulator.simulator import BudgetSimulatorV45

PA = "Pouvoir d'Achat"
AN1 = 2026


def _run(mesures, periods=10):
    """(simulateur, impacts par année {année: {mesure: impacts}}) — non arrondi."""
    sim = BudgetSimulatorV45(periods=periods, mesures=mesures)
    _, _, rapport = sim.simulate()
    impacts = {an['Année']: an for an in rapport['measure_impacts_by_year']}
    return sim, impacts


@pytest.fixture(scope='module')
def statu_quo():
    return _run({})[0]._rdb_trace


def _ecart_an1(trace, sq):
    """Écart relatif d'indice au statu quo en 2026 (effet direct)."""
    return trace[AN1].indice / sq[AN1].indice - 1


def _standalone(nom):
    import pathlib
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).parent / 'snapshots'))
    from coverage_scenarios import build_standalone_scenarios
    return build_standalone_scenarios()[nom]


def _conso(an):
    return (1 - TAUX_EPARGNE_MENAGES_2025) * an.rdb_base


# --- Les 9 défauts du diagnostic, re-testés en définition B -----------------

def test_tva_taux_normal_repercussion_sourcee(statu_quo):
    """+1 pt de TVA : le prix des ménages monte de τ+ × part ménages × Δrecettes
    / consommation ; τ implicite ∈ [0,6 ; 1] (Benzarti et al. 2020).
    v0.6.7 : τ implicite 0,22 (−0,2 %/pt fixe)."""
    sim, impacts = _run({'tva_rate': {'taux': 0.21}})
    an = sim._rdb_trace[AN1]
    assert an.rdb_base == pytest.approx(statu_quo[AN1].rdb_base, rel=1e-12)
    delta_rec = impacts[AN1]['tva_rate']['recettes']
    hausse_prix = an.prix / statu_quo[AN1].prix - 1
    tau = hausse_prix * _conso(an) / (PART_MENAGES_FISCALITE_INDIRECTE * delta_rec)
    assert 0.6 <= tau <= 1.0 + 1e-9, f"répercussion implicite τ = {tau:.2f}"
    assert tau == pytest.approx(REPERCUSSION_HAUSSE_FISCALITE_INDIRECTE, rel=1e-9)
    assert _ecart_an1(sim._rdb_trace, statu_quo) == pytest.approx(1 / (1 + hausse_prix) - 1)


@pytest.mark.parametrize('nom', ['impots_production', 'impot_revenu',
                                 'cotisations_salariales', 'csg', 'tva_energie',
                                 'point_indice'])
def test_aucun_levier_ne_transmet_plus_que_ses_euros(statu_quo, nom):
    """|ΔPA| ≤ |Δ euros du levier| / assiette (RDB, ou consommation pour un
    prélèvement indirect) : transmission ≤ 100 %. v0.6.7 : impôts de
    production 160 %, point d'indice 144 %, IR 142 %, cotisations 133 %, TVA
    énergie 133 %, CSG 111 % (borne indulgente RDB = 1 600 Md€)."""
    mesures = ({'fonction_publique': {'point_indice': 3.0}} if nom == 'point_indice'
               else _standalone(nom))
    sim, impacts = _run(mesures)
    an = sim._rdb_trace[AN1]
    mesure = 'fonction_publique' if nom == 'point_indice' else nom
    imp = impacts[AN1][mesure]
    euros = abs(imp.get('recettes', 0.0) - imp.get('depenses', 0.0))
    assert euros > 0.1, 'levier sans euros en 2026 : test sans objet'
    assiette = _conso(an) if nom == 'tva_energie' else an.rdb_base
    ecart = abs(_ecart_an1(sim._rdb_trace, statu_quo))
    assert ecart <= euros / assiette * 1.001, (
        f"PA {ecart:.4%} > borne comptable {euros / assiette:.4%} "
        f"(Δ = {euros:.1f} Md€, transmission {ecart / (euros / assiette):.0%})")


def test_un_niveau_permanent_ne_compose_pas(statu_quo):
    """Rabot de 7,5 % : chaque année, l'effet direct est le montant des coupes
    de prestations DE L'ANNÉE — pas la somme des années passées. v0.6.7 :
    8 années stables, micro cumulé −4,50 % (un niveau devenait une croissance)."""
    sim, impacts = _run({'rabot_uniforme': {'taux_reduction': 0.075}})
    stables = 0
    for an, decomposition in sim._rdb_trace.items():
        if an == 2025:
            continue
        canal = impacts[an]['rabot_uniforme']['menages']['prestations']
        assert decomposition.effet_mesures == pytest.approx(canal, rel=1e-12), an
        precedent = impacts.get(an - 1, {}).get('rabot_uniforme')
        if precedent and abs(canal - precedent['menages']['prestations']) < 0.02 * abs(canal):
            stables += 1
            # Montant stable → part dans le RDB stable (aucune dérive composée).
            part = decomposition.effet_mesures / decomposition.rdb_base
            part_prec = sim._rdb_trace[an - 1].effet_mesures / sim._rdb_trace[an - 1].rdb_base
            assert part == pytest.approx(part_prec, rel=0.05), an
    assert stables >= 5, 'montant jamais stabilisé : test sans objet'


def test_pas_d_attenuation_calendaire():
    """Un niveau émis en 2027+ compte en entier : ASU (montée en charge sur
    quatre ans). v0.6.7 : × 0,5 selon l'ANNÉE CALENDAIRE (effectifs FP :
    part retenue 0,50) — les effectifs n'ont plus d'effet direct (arbitrage
    du mainteneur), le test porte sur un transfert phasé."""
    sim, impacts = _run({'asu': {'asu_activation': 1}})
    tardives = [an for an in range(2027, 2036)
                if impacts[an]['asu']['menages']['prestations'] > 0]
    assert len(tardives) >= 5
    for an in tardives:
        canal = impacts[an]['asu']['menages']['prestations']
        assert sim._rdb_trace[an].effet_mesures / canal == pytest.approx(1.0, abs=1e-12), an


# --- Arbitrages du mainteneur (v0.6.8) ---------------------------------------

@pytest.mark.parametrize('nom', ['impots_production', 'impot_societes',
                                 'cotisations_patronales', 'niches_sociales_tge',
                                 'exonerations_salaires', 'taxe_superprofits'])
def test_impots_entreprises_sans_effet_direct(statu_quo, nom):
    """Arbitrage 1 : un impôt sur les entreprises n'a AUCUN effet direct sur le
    pouvoir d'achat ; il passe par la croissance et l'emploi. En 2026 la
    croissance n'a pas encore réagi : indice identique au statu quo."""
    sim, impacts = _run(_standalone(nom))
    assert any(abs(imp.get(nom, {}).get('recettes', 0.0)) > 0.1 for imp in impacts.values())
    for an, decomposition in sim._rdb_trace.items():
        assert decomposition.effet_mesures == 0.0 and decomposition.coin_indirect == 0.0, an
    assert sim._rdb_trace[AN1].indice == pytest.approx(statu_quo[AN1].indice, rel=1e-12)


@pytest.mark.parametrize('mesures', [
    {'fonction_publique': {'effectifs': 60_000}},
    {'education': {'enseignants': 20_000, 'budget': 70}},
    {'recherche_publique': {'budget': 18}},
    {'transition_ecologique': {'investissement': 10, 'renovation': 5}},
])
def test_depense_publique_sans_effet_direct(statu_quo, mesures):
    """Arbitrage 2 : embauches, investissement, rénovation, recherche — aucun
    effet direct, par la croissance seulement."""
    sim, _ = _run(mesures)
    assert all(d.effet_mesures == 0.0 for d in sim._rdb_trace.values())
    assert sim._rdb_trace[AN1].indice == pytest.approx(statu_quo[AN1].indice, rel=1e-12)


def test_point_d_indice_compte_une_fois_a_sa_part_nette(statu_quo):
    """Arbitrage 2, exception : le point d'indice est un revenu des agents en
    place, compté UNE fois à sa part nette (n ≈ 0,535) ; la masse salariale
    publique de base suit la dépense organique, pas la croissance."""
    sim, impacts = _run({'fonction_publique': {'point_indice': 3.0}})
    cout = impacts[AN1]['fonction_publique']['depenses']
    an = sim._rdb_trace[AN1]
    assert an.effet_mesures == pytest.approx(PART_NETTE_REMUNERATIONS_APU * cout, rel=1e-12)
    assert _ecart_an1(sim._rdb_trace, statu_quo) == pytest.approx(
        PART_NETTE_REMUNERATIONS_APU * cout / an.rdb_base, rel=1e-9)


def test_tva_hausse_et_baisse_asymetriques(statu_quo):
    """Arbitrage 3 : une baisse de TVA est répercutée moitié moins qu'une
    hausse (τ− / τ+ = 0,5), à euros égaux."""
    taus = {}
    for taux in (0.21, 0.19):
        sim, impacts = _run({'tva_rate': {'taux': taux}})
        delta = impacts[AN1]['tva_rate']['recettes']
        an = sim._rdb_trace[AN1]
        taus[taux] = (an.prix / statu_quo[AN1].prix - 1) * _conso(an) / (
            PART_MENAGES_FISCALITE_INDIRECTE * delta)
    assert taus[0.19] / taus[0.21] == pytest.approx(
        REPERCUSSION_BAISSE_FISCALITE_INDIRECTE / REPERCUSSION_HAUSSE_FISCALITE_INDIRECTE,
        rel=1e-9)


def test_prelevement_direct_symetrique(statu_quo):
    """Un prélèvement direct est symétrique : ±1 pt de CSG déplace l'indice de
    ±Δ€ / RDB, au même coefficient (aucune asymétrie sans source)."""
    ecarts = {}
    for taux in (0.087, 0.107):
        sim, impacts = _run({'csg': {'taux': taux}})
        delta = impacts[AN1]['csg']['recettes']
        ecarts[taux] = _ecart_an1(sim._rdb_trace, statu_quo) / (-delta / sim._rdb_trace[AN1].rdb_base)
    assert ecarts[0.087] == pytest.approx(1.0, rel=1e-9)
    assert ecarts[0.107] == pytest.approx(1.0, rel=1e-9)


# --- Formule exacte et ancrage INSEE -----------------------------------------

def test_formule_exacte_rejouee(monkeypatch):
    """La formule publiée (METHODOLOGIE § Pouvoir d'achat), rejouée de bout en
    bout sur un programme mixte à partir des SORTIES publiques (colonnes PIB,
    Déflateur, RDB_Ménages_Md€ et impacts par mesure de l'API) : canaux € de
    l'année, prix = déflateur × coin fiscal, indice par UC. Remplace les tests
    de la formule v0.6.7 (croissance + Σ coefficients × 0,5 après 2026)."""
    import budget_simulator.engine.orchestrator as orch
    monkeypatch.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
    mesures = {'tva_rate': {'taux': 0.22}, 'retraites': {'indexation': 0.8},
               'impot_revenu': {'taux_superieur': 0.50}, 'smic': {'montant_brut': 1900}}
    sim = BudgetSimulatorV45(periods=10, mesures=mesures)
    df, det, rapport = sim.simulate()
    df, det = df.set_index('Année'), det.set_index('Année')
    for i, an in enumerate(range(2025, 2036)):
        canaux = [v['menages'] for k, v in rapport['measure_impacts_by_year'][i].items()
                  if k != 'Année' and 'menages' in v]
        effet = sum(rdb_module.effet_revenu_md_eur(c) for c in canaux)
        coin = sum(rdb_module.coin_indirect_md_eur(c) for c in canaux)
        rdb = det.loc[an, 'RDB_Ménages_Md€']
        base = rdb - effet
        prix = det.loc[an, 'Déflateur'] * (1 + coin / ((1 - TAUX_EPARGNE_MENAGES_2025) * base))
        attendu = (100 * rdb / rdb_module.RDB_MENAGES_2025_MD_EUR / prix
                   / (1 + CROISSANCE_UC_ANNUELLE) ** i)
        assert df.loc[an, PA] == pytest.approx(attendu, rel=1e-12), an
        assert det.loc[an, 'Prix_Consommation'] == pytest.approx(prix, rel=1e-12), an
    assert det.loc[2030, 'RDB_Effet_Mesures_Md€'] != 0


def test_inflation_neutre_sur_le_revenu_de_base(monkeypatch):
    """Deux inflations (0,5 % et 3 %) : la part privée RÉELLE vaut exactement sa
    part 2025 × l'indice du PIB réel, et la part publique RÉELLE suit son seul
    volume tendanciel (0,6 %/an) — l'inflation ne touche le revenu de base qu'à
    travers la croissance réelle. (Constat du réfuteur v0.6.8 : indexée sur la
    catégorie de dépense organique, la masse publique perdait 1,3 % réel l'année
    d'une hausse d'inflation et suivait l'écart de production.)"""
    import budget_simulator.engine.orchestrator as orch
    monkeypatch.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)

    class _Inflation(BudgetSimulatorV45):
        pi = 0.0

        def calculate_inflation(self, year, economic_state):
            return self.pi

    pub = rdb_module.REMUNERATIONS_PUBLIQUES_NETTES_2025_MD_EUR
    prive_2025 = rdb_module.RDB_MENAGES_2025_MD_EUR - pub
    for pi in (0.005, 0.03):
        sim = type('_I', (_Inflation,), {'pi': pi})(periods=10, mesures={})
        _, det, _ = sim.simulate()
        pib_reel = det.set_index('Année')['PIB_Réel_Base2025']
        volume = 1 + sim.spending_growth_rates['masse_salariale']
        for i, (an, t) in enumerate(sim._rdb_trace.items()):
            assert t.rdb_prive / t.prix == pytest.approx(
                prive_2025 * pib_reel[an] / pib_reel[2025], rel=1e-12), (pi, an)
            assert (t.rdb_base - t.rdb_prive) / t.prix == pytest.approx(
                pub * volume ** i, rel=1e-12), (pi, an)


def test_masse_publique_de_base_identique_entre_scenarios():
    """Arbitrage 2 : la masse salariale publique de base, en réel, ne dépend
    d'aucune mesure (ni de la croissance qu'elles induisent) — seuls les canaux
    de rémunération la déplacent. Vérifié sur les dix scénarios publiés."""
    import pathlib
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).parent / 'snapshots'))
    from run_scenarios_full import SCENARIOS
    def reel(t):
        # Déflatée par le DÉFLATEUR (le coin fiscal indirect est un effet prix
        # des mesures, pas un effet sur la base).
        deflateur = t.prix / (1 + t.coin_indirect / ((1 - TAUX_EPARGNE_MENAGES_2025) * t.rdb_base))
        return (t.rdb_base - t.rdb_prive) / deflateur

    sq = _run({})[0]._rdb_trace
    for nom, mesures in SCENARIOS.items():
        trace = _run(mesures)[0]._rdb_trace
        for an, t in trace.items():
            assert reel(t) == pytest.approx(reel(sq[an]), rel=1e-12), (nom, an)


def test_ancrage_statu_quo_tendance_longue_insee():
    """Ancrage 1 (tendance) : sans mesure, le pouvoir d'achat par UC croît en
    moyenne de 0,0 à 1,0 %/an sur 2026-2035 — INSEE : +0,4 %/an en 2011-2019
    (« La consommation des ménages en 2025 », fig. 3), +0,5 %/an depuis 2010
    (France portrait social 2025). Tolérance explicite ±0,5 pt autour de 0,5."""
    sim, _ = _run({})
    pa = [t.indice for t in sim._rdb_trace.values()]
    moyenne = ((pa[-1] / pa[0]) ** (1 / (len(pa) - 1)) - 1) * 100
    assert 0.0 <= moyenne <= 1.0, f"{moyenne:.2f} %/an"


def test_ancrage_statu_quo_2026_ordre_de_grandeur_insee():
    """Ancrage 2 (année 1) : INSEE, Note de conjoncture de juin 2026, pouvoir
    d'achat par UC 2026 −0,7 % (après −0,7 % en 2025). Le statu quo du moteur
    sert +0,8 % : l'indice suit le PIB réel par UC (identité vérifiée ici à
    0,15 pt près), et la croissance 2026 du moteur (1,24 %) comme son déflateur
    (1,34 %) précèdent le choc énergétique documenté par l'INSEE en juin 2026
    (inflation +2,4 % sur un an en mai). L'écart vient donc de la MACRO de
    l'année, pas du passage au RDB. Tolérance explicite : 1,6 pt — question
    ouverte (recalage 2026 de la croissance et de l'inflation, release dédiée :
    il bougerait toutes les colonnes)."""
    sim = BudgetSimulatorV45(periods=10, mesures={})
    df, _, _ = sim.simulate()
    pa_uc_2026 = (sim._rdb_trace[2026].indice / 100 - 1) * 100
    croissance = df.set_index('Année').loc[2026, 'Croissance %']
    assert pa_uc_2026 == pytest.approx(croissance - CROISSANCE_UC_ANNUELLE * 100, abs=0.15)
    assert abs(pa_uc_2026 - (-0.7)) <= 1.6, f"{pa_uc_2026:+.2f} % vs INSEE −0,7 %"


# --- Contrat : zéro échec silencieux ----------------------------------------

def test_handler_sans_canaux_menages_echoue_bruyamment(monkeypatch, caplog):
    """Un handler qui déplace des euros sans dire lesquels touchent les ménages
    serait compté nul sans le dire : il échoue (ERROR + HANDLER_FAILED_KEY en
    tolérant)."""
    monkeypatch.delenv('BUDGETLAB_STRICT', raising=False)
    sim = BudgetSimulatorV45(periods=2, mesures={'impot_revenu': {'taux_superieur': 0.5}})

    def _sans_canaux(measure, params, year, gdp, inflation, unemployment):
        return 0.0, 5.0, {'recettes': 5.0}

    monkeypatch.setitem(sim.measure_handlers, 'impot_revenu', _sans_canaux)
    with caplog.at_level(logging.ERROR):
        _, _, rapport = sim.simulate()
    assert rapport['measure_impacts_by_year'][1]['impot_revenu'][HANDLER_FAILED_KEY] is True
    assert any('sans canaux ménages' in r.getMessage() for r in caplog.records)


# --- Constats du réfuteur v0.6.8 et leviers dans les deux sens ---------------

def _base_publique_reelle(t):
    """Masse publique de base déflatée par le DÉFLATEUR (hors coin fiscal)."""
    deflateur = t.prix / (1 + t.coin_indirect / ((1 - TAUX_EPARGNE_MENAGES_2025) * t.rdb_base))
    return (t.rdb_base - t.rdb_prive) / deflateur


@pytest.mark.parametrize('mesures', [
    {'rabot_uniforme': {'taux_reduction': 0.08, 'exclure_dette': 1,
                        'exclure_defense': 1, 'exclure_ue': 1}},
    {'fonction_publique': {'point_indice': 5.0}},
    {'sante': {'effort_hopital': 15, 'effort_ambu': 20, 'effort_prev_org': 10}},
])
def test_constats_1_2_masse_publique_de_base_insensible_aux_mesures(statu_quo, mesures):
    """Réfuteur v0.6.8, constats 1-2 (RED sur 403c549) : indexée sur la catégorie
    de dépense organique, la masse publique de base suivait l'écart de
    production (volume) et l'inflation passée (prix) — rabot 8 % : −16,4 Md€
    nominaux en 2035 ; point d'indice +5 : +2,35 Md€ en 2035 EN PLUS de son
    canal. Désormais identique en réel au statu quo, chaque année."""
    trace = _run(mesures)[0]._rdb_trace
    for an, t in trace.items():
        assert _base_publique_reelle(t) == pytest.approx(
            _base_publique_reelle(statu_quo[an]), rel=1e-12), an


def test_constat_5_canal_sans_contrepartie_budgetaire_plafonne(monkeypatch):
    """Réfuteur v0.6.8, constat 5 : un canal ménages sans dépense ni recette
    échappait au plafond de 5 % du PIB par mesure. Il est borné, avec l'avis."""
    sim = BudgetSimulatorV45(periods=2, mesures={'impot_revenu': {'taux_superieur': 0.5}})

    def _sans_budget(measure, params, year, gdp, inflation, unemployment):
        return 0.0, 0.0, {'menages': canaux_menages(prestations=1.0e6)}

    monkeypatch.setitem(sim.measure_handlers, 'impot_revenu', _sans_budget)
    df, _, rapport = sim.simulate()
    pib_2026 = df.set_index('Année').loc[2026, 'PIB']
    assert sim._rdb_trace[2026].effet_mesures == pytest.approx(0.05 * pib_2026, rel=1e-3)
    assert any('plafonné à 5 % du PIB' in w for w in rapport['warnings'])


def test_constat_5_rdb_de_base_non_positif_leve():
    with pytest.raises(ValueError):
        rdb_module.rdb_annee({}, 0.0, 2900.0, 1.0, 0.0, 1)


def _canal_et_trace(mesures, mesure, canal):
    sim, impacts = _run(mesures)
    return sim._rdb_trace, {an: imp[mesure] for an, imp in impacts.items() if mesure in imp}


@pytest.mark.parametrize('plafonnement', [0.5, 0.65, 0.7])
def test_asu_identite_et_signe(plafonnement):
    """ASU : transfert = effort × montée en charge + recours (identité),
    toujours ≥ 0 (le handler n'a pas de barème moins généreux que l'actuel :
    effort ∈ [0 ; 2] Md€ sur le domaine) ; l'indice le lit tel quel."""
    from budget_simulator.constants import asu_cout_recours_md_eur, asu_effort_perenne_md_eur
    from budget_simulator.handlers._phasing import asu_phasing
    mesures = {'asu': {'asu_activation': 1, 'asu_plafonnement': plafonnement}}
    trace, imp = _canal_et_trace(mesures, 'asu', 'prestations')
    for an, i in imp.items():
        ph = asu_phasing(mesures, an)
        attendu = asu_effort_perenne_md_eur(plafonnement) * ph + asu_cout_recours_md_eur(ph)
        assert i['menages']['prestations'] == pytest.approx(attendu, abs=1e-12), an
        assert i['menages']['prestations'] >= 0
        assert trace[an].effet_mesures == pytest.approx(attendu, abs=1e-12), an


@pytest.mark.parametrize('params, signe', [
    ({'indexation': 0.8}, -1), ({'indexation': 1.2}, +1),
    ({'age_depart': 64.0}, -1), ({'age_depart': 61.0}, +1),
    ({'duree_cotisation': 44.0}, -1), ({'duree_cotisation': 41.0}, +1),
])
def test_retraites_deux_sens(statu_quo, params, signe):
    """Retraites : pensions non versées (ou versées en plus) = la dépense du
    levier, chaque année (identité), de signe attendu dans les deux sens ;
    l'année où le canal s'ouvre, l'écart d'indice au statu quo est −Δ€/RDB
    (le revenu d'activité des seniors maintenus en emploi passe par la
    croissance, laguée)."""
    sim, impacts = _run({'retraites': params})
    actives = [an for an, i in impacts.items()
               if abs(i.get('retraites', {}).get('depenses', 0.0)) > 1e-9]
    assert actives, 'levier sans effet : test sans objet'
    for an in actives:
        i = impacts[an]['retraites']
        assert i['menages']['prestations'] == pytest.approx(i['depenses'], rel=1e-12), an
        assert sim._rdb_trace[an].effet_mesures == pytest.approx(i['depenses'], rel=1e-12), an
        assert signe * i['menages']['prestations'] > 0, an


@pytest.mark.parametrize('intensite', [-0.3, 0.3])
def test_fiscalite_patrimoine_deux_sens(statu_quo, intensite):
    """IFI + foncière (impôts courants des ménages) entrent au RDB, pas les
    droits de succession (transfert en capital, INSEE) : part 38/53 de la
    recette ; signe opposé à l'intensité, symétrique."""
    sim, impacts = _run({'fiscalite_patrimoine': {'intensite': intensite}})
    i = impacts[AN1]['fiscalite_patrimoine']
    assert i['menages']['prelevements_directs'] == pytest.approx(i['recettes'] * 38 / 53, rel=1e-12)
    ecart = _ecart_an1(sim._rdb_trace, statu_quo)
    assert ecart == pytest.approx(-i['menages']['prelevements_directs']
                                  / sim._rdb_trace[AN1].rdb_base, rel=1e-9)
    assert ecart * intensite < 0


# Part EN ESPÈCES de chaque catégorie de prestations du rabot, posée À LA MAIN
# depuis les sources (pas depuis le code) : pensions, allocations chômage et
# minima sociaux sont des revenus ; la santé est un transfert EN NATURE (hors
# RDB, comme dans le levier santé) ; « dépendance » (APA + AAH, 35 Md€) n'est
# en espèces que pour l'AAH, 15,9 Md€ en 2025 (Sénat, avis PLF 2025 n° 147
# t. V) — l'APA est une prestation en nature (DREES).
_PART_ESPECES_ATTENDUE = {'retraites': 1.0, 'chomage': 1.0, 'minima_sociaux': 1.0,
                          'dependance': 15.9 / 35.0, 'sante': 0.0}


@pytest.mark.parametrize('taux', [0.05, 0.10])
def test_rabot_details_coupes(taux):
    """Rabot uniforme : seules les coupes de prestations EN ESPÈCES entrent au
    RDB, au montant de l'année (recalculé depuis les facteurs de volume du
    moteur et les parts posées à la main) ; linéaire dans le taux."""
    sim = BudgetSimulatorV45(periods=1, mesures={'rabot_uniforme': {'taux_reduction': taux}})
    _, _, rapport = sim.simulate()
    canal = rapport['measure_impacts_by_year'][1]['rabot_uniforme']['menages']['prestations']
    phasing_2026 = 0.5
    attendu = -sum(sim.spending_categories_base[c] * sim._spending_factors[c] * part
                   for c, part in _PART_ESPECES_ATTENDUE.items()) * taux * phasing_2026
    assert canal == pytest.approx(attendu, rel=1e-12)
    assert canal < 0
    assert sim._rdb_trace[AN1].effet_mesures == pytest.approx(canal, rel=1e-12)


def _rabot_direct(base_sante=None, base_dependance=None):
    """Handler du rabot appelé seul (facteurs de volume à 1), bases modifiables."""
    sim = BudgetSimulatorV45(periods=1, mesures={})
    if base_sante is not None:
        sim.spending_categories_base['sante'] = base_sante
    if base_dependance is not None:
        sim.spending_categories_base['dependance'] = base_dependance
    dep, _, imp = sim._apply_rabot_uniforme({}, {'taux_reduction': 0.08}, 2027, 3000.0, 0.02, 0.075)
    return dep, imp['menages']['prestations']


def test_meme_euro_de_sante_meme_effet_rabot_et_levier_sante():
    """Revue passe 1, M1 : un euro de dépense de santé économisé vaut le MÊME
    effet direct sur le RDB par le rabot et par le levier santé — zéro (transfert
    en nature, hors RDB INSEE ; seules les franchises touchent le revenu)."""
    sim = BudgetSimulatorV45(periods=1, mesures={})
    dep_sante, _, imp_sante = sim._apply_sante(
        {}, {'effort_hopital': 50, 'effort_ambu': 50}, 2028, 3000.0, 0.02, 0.075)
    assert dep_sante < -1.0
    par_euro_levier = imp_sante['menages']['prestations'] / dep_sante

    dep_a, canal_a = _rabot_direct(base_sante=250.0)
    dep_b, canal_b = _rabot_direct(base_sante=350.0)
    assert dep_b - dep_a == pytest.approx(-0.08 * 100.0)
    par_euro_rabot = (canal_b - canal_a) / (dep_b - dep_a)
    assert par_euro_rabot == pytest.approx(par_euro_levier, abs=1e-12)
    assert par_euro_levier == 0.0


def test_rabot_dependance_seule_l_aah_est_un_revenu():
    """Un euro de dépendance coupé retire 15,9/35 € de revenu (part AAH) : la
    part APA, prestation en nature, n'entre pas au RDB."""
    dep_a, canal_a = _rabot_direct()
    dep_b, canal_b = _rabot_direct(base_dependance=45.0)
    # La part en espèces suit le niveau d'AAH (15,9 Md€), pas la base : 10 Md€
    # de dépendance en plus sont 10 Md€ de prestations en nature.
    assert dep_b - dep_a == pytest.approx(-0.08 * 10.0)
    assert canal_b - canal_a == pytest.approx(0.0, abs=1e-12)
    _, canal = _rabot_direct()
    assert canal == pytest.approx(-0.08 * (380 + 15.9 + 90 + _chomage_base()), rel=1e-12)


def _chomage_base():
    return BudgetSimulatorV45(periods=1, mesures={}).spending_categories_base['chomage']
