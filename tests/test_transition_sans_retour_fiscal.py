"""Investissement de transition : plus de retour fiscal propre ; le levier réel n'est pas autofinancé (lot 2).

Jusqu'au lot 2, ``_apply_transition_ecologique`` ajoutait à ses recettes 0 %, puis 5 %, puis 8 % de la dépense
d'investissement et de rénovation, au titre des impôts et cotisations de l'activité induite. Deux défauts,
établis par la revue des sources de novembre 2026 : les deux références citées ne portent pas ce chiffre (OCDE,
« Getting Infrastructure Right », un cadre de gouvernance ; « Cour des comptes 2023 », introuvable) ; et c'était
un double compte, les recettes du moteur suivant déjà le PIB nominal avec une élasticité de 1,0, ce canal
portant précisément les impôts de l'activité induite. Ni l'investissement des collectivités ni la recherche ne
recevaient ce surplus. Arbitrage du mainteneur (15/11/2026) : retrait, et une garde « pas d'autofinancement » sur
le levier réel, que les gardes de calibrage (un choc passé par l'éducation) ne couvraient pas.

Contrat verrouillé ici : les recettes propres du levier se limitent à la taxe carbone, chaque année ; tiré seul
sur le droit en vigueur (mode cadre 2028, deux montants pour chaque paramètre), l'investissement comme la
rénovation alourdissent la dette et le déficit EN EUROS chaque année de 2028 à 2035 (une amélioration en part du
PIB peut venir du dénominateur, pas d'un remboursement) ; un retour fiscal réintroduit qui rembourserait la
dépense fait rougir la garde ; l'investissement de l'État et celui des collectivités ont le même effet, au bit.

Renforcé après réfutation (16/11/2026) : (a) propriété générique, sur les impacts que le moteur utilise
réellement (rapport de simulation), pour les cinq leviers d'investissement — investissement et rénovation de la
transition, investissement des collectivités, recherche publique, éducation : relever le montant ne crée aucune
recette propre au levier, chaque année, dans les deux modes ; un retour fiscal remis hors du handler, sur
n'importe lequel, la fait rougir. (b) La garde « pas d'autofinancement » vérifie aussi que le levier ne relève
jamais la part des recettes dans le PIB : avec une élasticité de 1,0, l'activité induite fait croître les
recettes comme le PIB ; seule une recette propre relève cette part. L'ancien barème (0 / 5 / 8 %), qui
n'autofinançait rien, la fait donc rougir. Aucune donnée du dépôt parent n'est lue.
"""
import json
from pathlib import Path

import pytest

import budget_simulator.engine.orchestrator as orch
from budget_simulator.constants import CARBONE_PRIX_REFERENCE_EUR_T
from budget_simulator.handlers import investissements
from budget_simulator.simulator import BudgetSimulatorV45

RACINE = Path(__file__).absolute().parent.parent
DROIT = json.loads((RACINE / 'budget_simulator' / 'data' / 'droit_en_vigueur.json')
                   .read_text(encoding='utf-8'))['mesures']
PIB = 3000.0


def _recettes_du_levier(annee, investissement=0.0, renovation=0.0, carbone=CARBONE_PRIX_REFERENCE_EUR_T):
    sim = BudgetSimulatorV45(periods=1)
    sim.debug_logs = []
    params = {'investissement': investissement, 'renovation': renovation, 'taxe_carbone': carbone}
    _, recettes, impacts = sim._apply_transition_ecologique({'id': 'transition_ecologique'}, params, annee,
                                                           PIB, 0.01, 0.076)
    assert impacts['recettes'] == recettes
    return recettes


@pytest.mark.parametrize('carbone', [CARBONE_PRIX_REFERENCE_EUR_T, 100.0])
def test_recettes_propres_limitees_a_la_taxe_carbone(carbone):
    """Dix années d'application, 20 Md€ d'investissement et 10 de rénovation : les recettes du levier sont
    celles de la taxe carbone, chaque année (nulles au prix de référence). Jusqu'au lot 2 : +1,5 Md€ les
    années 3 et 4, +2,4 Md€ ensuite."""
    from budget_simulator.constants import POLICY_START_YEAR
    for annee in range(POLICY_START_YEAR, POLICY_START_YEAR + 10):
        avec = _recettes_du_levier(annee, investissement=20.0, renovation=10.0, carbone=carbone)
        sans = _recettes_du_levier(annee, carbone=carbone)
        assert avec == sans == pytest.approx((carbone - CARBONE_PRIX_REFERENCE_EUR_T) * 0.06, abs=1e-12), annee


def test_aucun_taux_de_retour_dans_le_handler():
    """Garde de source : aucun taux de retour fiscal ne se réintroduit dans le handler."""
    import inspect
    source = inspect.getsource(investissements.InvestissementsMixin._apply_transition_ecologique)
    code = '\n'.join(l.split('#')[0] for l in source.splitlines())
    assert 'fiscal_return' not in code and 'retour' not in code.lower()


@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
def test_meme_effet_que_l_investissement_local(annee_debut):
    """Un euro d'investissement public reçoit désormais le même retour, celui de l'élasticité des recettes,
    qu'il passe par l'État (transition) ou par les collectivités : 10 Md€ par an donnent la même dette, le même
    déficit, la même croissance et le même chômage, au bit. Jusqu'au lot 2, le retour propre du levier de l'État
    faisait l'écart (−0,11 contre −0,08 point de dette 2032 en mode cadre)."""
    colonnes = ['Dette/PIB %', 'Déficit/PIB %', 'Croissance %', 'Chômage %']
    etat, _, _ = BudgetSimulatorV45(periods=10, mesures={'transition_ecologique': {'investissement': 10}},
                                    annee_debut=annee_debut).simulate()
    local, _, _ = BudgetSimulatorV45(periods=10, mesures={'collectivites': {'investissement': 10}},
                                     annee_debut=annee_debut).simulate()
    assert etat[colonnes].equals(local[colonnes])
    reference, _, _ = BudgetSimulatorV45(periods=10, mesures={}, annee_debut=annee_debut).simulate()
    assert not etat['Dette/PIB %'].equals(reference['Dette/PIB %'])   # non-vacuité


def _en_euros(mesures):
    """{année: (dette, solde, part des recettes dans le PIB)}, dette et solde en Md€, mode cadre 2028, pleine
    précision (dette = ratio × PIB nominal)."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
        df, det, _ = BudgetSimulatorV45(periods=10, mesures=mesures, annee_debut=2028).simulate()
    d, e = df.set_index('Année'), det.set_index('Année')
    return {a: (d.at[a, 'Dette/PIB %'] * d.at[a, 'PIB'] / 100, d.at[a, 'Déficit/PIB %'] * d.at[a, 'PIB'] / 100,
                e.at[a, 'Recettes_Totales'] / d.at[a, 'PIB'])
            for a in range(2028, 2036)}


CAS = [('investissement', 10.0), ('investissement', 40.0), ('renovation', 10.0), ('renovation', 40.0)]


def _verifier_pas_d_autofinancement():
    base = _en_euros(DROIT)
    for param, montant in CAS:
        bloc = {**DROIT['transition_ecologique'], param: montant}
        avec = _en_euros({**DROIT, 'transition_ecologique': bloc})
        for annee in avec:
            dette_b, solde_b, part_b = base[annee]
            dette, solde, part = avec[annee]
            assert dette > dette_b, (param, montant, annee, dette - dette_b)
            assert solde < solde_b, (param, montant, annee, solde - solde_b)
            # La part des recettes dans le PIB ne monte pas (elle baisse un peu : les recettes fixes en euros
            # du droit en vigueur sont rapportées à un PIB plus grand).
            assert part <= part_b + 1e-12, (param, montant, annee, 100 * (part - part_b))


def test_le_levier_reel_n_est_pas_autofinance():
    """Investissement et rénovation de transition tirés seuls sur le droit en vigueur, mode cadre 2028 :
    chaque année de 2028 à 2035, dette plus haute et solde plus lourd, en euros, et part des recettes dans le
    PIB jamais plus haute."""
    _verifier_pas_d_autofinancement()


def test_mutation_retour_qui_rembourse_la_depense_rougit(monkeypatch):
    """Par mutation : un retour fiscal réintroduit à 120 % de la dépense (un levier qui se rembourserait) fait
    rougir la garde."""
    _verifier_pas_d_autofinancement()   # témoin
    vrai = investissements.InvestissementsMixin._apply_transition_ecologique

    def avec_retour(self, measure, params, year, gdp, inflation, unemployment):
        dep, rec, impacts = vrai(self, measure, params, year, gdp, inflation, unemployment)
        rec += 1.2 * dep
        impacts = {**impacts, 'recettes': rec}
        return dep, rec, impacts
    monkeypatch.setattr(investissements.InvestissementsMixin, '_apply_transition_ecologique', avec_retour)
    with pytest.raises(AssertionError):
        _verifier_pas_d_autofinancement()


def test_mutation_ancien_bareme_rougit(monkeypatch):
    """Par mutation : l'ancien retour fiscal (0 % les deux premières années, 5 % les deux suivantes, 8 %
    ensuite), qui n'autofinançait rien, relève la part des recettes dans le PIB ; la garde rougit."""
    _verifier_pas_d_autofinancement()   # témoin
    vrai = investissements.InvestissementsMixin._apply_transition_ecologique

    def ancien(self, measure, params, year, gdp, inflation, unemployment):
        dep, rec, impacts = vrai(self, measure, params, year, gdp, inflation, unemployment)
        ecoulees = year - self._origine('transition_ecologique')
        taux = 0.0 if ecoulees < 3 else (0.05 if ecoulees < 5 else 0.08)
        rec += taux * dep
        return dep, rec, {**impacts, 'recettes': rec}
    monkeypatch.setattr(investissements.InvestissementsMixin, '_apply_transition_ecologique', ancien)
    with pytest.raises(AssertionError):
        _verifier_pas_d_autofinancement()


# --- Propriété générique : aucun levier d'investissement ne crée de recette propre -----------------------

LEVIERS_D_INVESTISSEMENT = [('transition_ecologique', 'investissement', 40.0),
                            ('transition_ecologique', 'renovation', 40.0),
                            ('collectivites', 'investissement', 10.0),
                            ('recherche_publique', 'budget', 20.0),
                            ('education', 'budget', 75.0)]


def _recettes_du_levier_par_annee(mesures, levier, annee_debut):
    _, _, rapport = BudgetSimulatorV45(periods=10, mesures=mesures, annee_debut=annee_debut).simulate()
    return {y['Année']: float((y.get(levier) or {}).get('recettes', 0) or 0)
            for y in rapport['measure_impacts_by_year']}


def _verifier_aucune_recette_propre(annee_debut):
    for levier, param, montant in LEVIERS_D_INVESTISSEMENT:
        base = _recettes_du_levier_par_annee(DROIT, levier, annee_debut)
        programme = {**DROIT, levier: {**(DROIT.get(levier) or {}), param: montant}}
        avec = _recettes_du_levier_par_annee(programme, levier, annee_debut)
        assert avec == base, (levier, param, {a: avec[a] - base[a] for a in avec if avec[a] != base[a]})


@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
def test_aucun_levier_d_investissement_ne_cree_de_recette_propre(annee_debut):
    """Relever l'investissement ou la rénovation de la transition, l'investissement des collectivités, la
    recherche ou l'éducation ne change pas, une seule année, les recettes que le levier publie dans les impacts
    utilisés par le moteur : sa seule recette propre est sa taxe explicite (la taxe carbone, inchangée ici)."""
    _verifier_aucune_recette_propre(annee_debut)


@pytest.mark.parametrize('levier, param', [('transition_ecologique', 'renovation'), ('recherche_publique', 'budget'),
                                           ('collectivites', 'investissement')])
def test_mutation_retour_remis_hors_du_handler_rougit(monkeypatch, levier, param):
    """Par mutation : un retour fiscal 0 / 5 / 8 % remis après les handlers (dans ``apply_measures``), sur la
    rénovation, la recherche ou l'investissement des collectivités, fait rougir la propriété générique."""
    _verifier_aucune_recette_propre(2028)   # témoin
    from budget_simulator.config import load_default_values
    defaut = (load_default_values().get(levier) or {}).get(param, 0) or 0
    vrai = BudgetSimulatorV45.apply_measures

    def apply_measures(self, year, spending, revenues, gdp, inflation, unemployment):
        sp, rv, imp = vrai(self, year, spending, revenues, gdp, inflation, unemployment)
        valeur = ((self.mesures or {}).get(levier) or {}).get(param)
        bloc = imp.get(levier)
        if isinstance(bloc, dict) and isinstance(valeur, (int, float)):
            ecoulees = year - self._origine(levier)
            r = (0.0 if ecoulees < 3 else (0.05 if ecoulees < 5 else 0.08)) * (valeur - defaut)
            if r:
                imp = {**imp, levier: {**bloc, 'recettes': float(bloc.get('recettes', 0) or 0) + r}}
                rv += r
        return sp, rv, imp
    monkeypatch.setattr(BudgetSimulatorV45, 'apply_measures', apply_measures)
    with pytest.raises(AssertionError):
        _verifier_aucune_recette_propre(2028)

