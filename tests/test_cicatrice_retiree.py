"""Croissance : la « cicatrice d'austérité » est retirée (lot 1 des corrections d'équations).

Jusqu'à v0.8.1, ``calculate_growth`` retirait à la croissance de chaque année 0,10 point par point
de PIB d'effort intérieur au-delà de 3 % du PIB, plafonné à 0,3 point par an, pour les seules
consolidations. Le seuil avait été choisi « pour éviter le piège où l'utilisateur ne peut trouver
aucune solution viable », pas d'après une source. Les deux références citées par le code ne le
portent pas (revue des sources de novembre 2026, textes primaires rouverts) :

- DeLong & Summers (BPEA, printemps 2012) : un effet de NIVEAU sur le PIB potentiel, proportionnel
  à l'impulsion budgétaire (« ΔY^f = ηΔY^n = ηµΔG »), dans une économie déprimée à la borne zéro des
  taux — ni seuil de 3 %, ni plafond, ni sens unique (une relance évite la perte) ;
- Fatás & Summers (NBER WP 22374, 2016 ; JIE 2018) : une régression linéaire de la perte de
  potentiel sur la baisse du PIB due à la politique budgétaire, consolidations de 2010-2011, en
  crise ; « much smaller effects » hors de ces conditions.

La forme du moteur (une pénalité de croissance qui s'accumule tant que l'effort dure, au-delà d'un
seuil, d'un seul côté) n'existe dans aucune des deux. Elle doublait de plus les multiplicateurs,
calés sur l'effet de niveau à 4 ans mesuré, et contredisait le rappel vers le potentiel pour un seul
programme. Retirée sans remplacement (une hystérèse symétrique sur l'écart de production serait un
chantier distinct). Contrat verrouillé ici : la croissance ne dépend pas du niveau de l'effort de
consolidation — à état donné, au bit ; à impulsions données, linéairement ; et, dans le moteur complet,
le multiplicateur effectif d'une consolidation est le même de 1 % à 8 % du PIB, quel que soit l'endroit
où une pénalité à seuil serait réintroduite, y compris une pénalité réservée aux économies déprimées
(pondérée par le régime de récession). L'état transmis à la croissance ne porte plus d'effort
intérieur (sans lecteur). Aucune donnée du dépôt parent n'est lue.

Limite du harnais, non couverte ici : le choc synthétique est injecté APRÈS ``apply_measures`` ; un
mécanisme qui lirait l'effort calculé à l'intérieur de ``BudgetSimulatorV45.apply_measures`` ne
verrait pas ce choc, alors qu'il mordrait sur un vrai programme.
"""
import pytest

from budget_simulator.simulator import BudgetSimulatorV45

EFFORTS = (0.01, 0.029, 0.03, 0.031, 0.035, 0.05, 0.10)


def _croissance(effort, dette):
    sim = BudgetSimulatorV45(periods=1)
    sim._reset_state()
    sim._last_impacts = {}
    etat = {'output_gap': 0.0, 'unemployment_gap': 0.0, 'debt_ratio': dette,
            'effort_budgetaire': effort, 'effort_interieur': effort, 'part_investissement': 0.0,
            'unemployment': 0.075, 'deficit_ratio': -0.05, 'interest_rate': 0.03}
    return sim.calculate_growth(1, etat)


@pytest.mark.parametrize('dette', [0.9, 1.15, 1.5])
def test_croissance_invariante_au_niveau_de_consolidation(dette):
    """À impulsions nulles, aucun niveau d'effort de consolidation (1 % à 10 % du PIB) ne change la
    croissance de l'année, au bit. v0.8.1 : −0,05 point à 3,5 %, −0,3 point (plafond) à 10 %."""
    reference = _croissance(0.0, dette)
    ecarts = {e: _croissance(e, dette) - reference for e in EFFORTS}
    assert all(d == 0.0 for d in ecarts.values()), ecarts


def test_croissance_lineaire_dans_l_impulsion_de_consolidation():
    """À état donné et sans autre impulsion, une consolidation de s point de PIB stockée l'année même
    change la croissance de −k × s × profil(0) : exactement linéaire en s, de 1 % à 8 % du PIB. Une
    pénalité à seuil sur l'effort, quel que soit le chemin par lequel elle lirait l'effort (état
    transmis ou impacts de l'année précédente), casserait cette linéarité."""
    def croissance(s):
        sim = BudgetSimulatorV45(periods=1)
        sim._reset_state()
        sim.pib_nominal = 3000.0
        sim._last_impacts = {'tva_rate': {'depenses': 0.0, 'recettes': s * 3000.0}} if s else {}
        # Écart de production −5 % : le rappel vers le potentiel garde la croissance dans le filet
        # [−3,5 % ; +2,5 %] jusqu'à 8 % du PIB (régime de récession plein, constant sur la grille).
        etat = {'output_gap': -0.05, 'unemployment_gap': 0.0, 'debt_ratio': 1.15, 'interest_rate': 0.03,
                'effort_budgetaire': s, 'effort_interieur': s, 'part_investissement': 0.0,
                'unemployment': 0.075, 'deficit_ratio': -0.05}
        return sim.calculate_growth(1, etat)
    g0 = croissance(0.0)
    pentes = {s: (croissance(s) - g0) / s for s in GRILLE}
    reference = pentes[GRILLE[0]]
    assert reference < 0
    assert all(abs(p - reference) <= 1e-12 for p in pentes.values()), pentes


# --- Multiplicateur effectif d'une consolidation permanente, de 1 % à 8 % du PIB ----------------

GRILLE = (0.01, 0.02, 0.029, 0.035, 0.04, 0.05, 0.065, 0.08)


def _pib_reel(levier=None, flux='depenses', taille=0.0, dette_elevee_neutralisee=True):
    class _Choc(BudgetSimulatorV45):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # Non-linéarité légitime n° 1 : la marche du facteur « dette élevée » ×0,95 à 110 % de
            # dette. Une consolidation de 8 % du PIB fait passer la dette du banc sous ce seuil
            # (k de la hausse d'impôts 0,584 → 0,615), alors qu'elle reste au-dessus dans tout le
            # domaine publié. Neutralisée (facteur 1 partout, ce qui ne change que le niveau commun)
            # pour le test qui va jusqu'à 8 % ; laissée en place pour le test du moteur complet.
            if dette_elevee_neutralisee:
                self.multipliers.adjustments['high_debt'] = 1.0

        def apply_measures(self, year, spending, revenues, gdp, inflation, unemployment):
            sp, rv, imp = super().apply_measures(year, spending, revenues, gdp, inflation, unemployment)
            if levier:
                x = taille * gdp
                imp = dict(imp)
                imp[levier] = {'depenses': x if flux == 'depenses' else 0.0,
                               'recettes': x if flux == 'recettes' else 0.0}
                if flux == 'depenses':
                    sp += x
                else:
                    rv += x
            return sp, rv, imp
    return _Choc(periods=12, mesures={}).simulate()[1]['PIB_Réel_Base2025'].values


@pytest.fixture
def pleine_precision(monkeypatch):
    import budget_simulator.engine.orchestrator as orch
    monkeypatch.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)


@pytest.fixture
def moteur_sans_non_linearites_declarees(pleine_precision, monkeypatch):
    """Pleine précision, et une autre non-linéarité légitime neutralisée le temps du test : n° 2, le
    filet de croissance [−3,5 % ; +2,5 %], un écrêtage atteint à 8 % du PIB. La n° 1 est neutralisée
    dans ``_pib_reel``. Le régime de récession des multiplicateurs (×1,15) n'est PAS neutralisé : sur ce
    banc, le neutraliser ne change aucune sortie, au bit, de 1 % à 8 % du PIB ; il remettait en
    revanche à zéro une cicatrice pondérée par ce régime (lot 1, recontrôle du 15/11/2026)."""
    import budget_simulator.engine.growth as growth_mod
    monkeypatch.setattr(growth_mod, 'CROISSANCE_FILET_MIN', -1.0)
    monkeypatch.setattr(growth_mod, 'CROISSANCE_FILET_MAX', 1.0)


# (levier synthétique, flux, signe d'une CONSOLIDATION). Impôt sur le revenu et non TVA : le passage
# de la TVA dans les prix est plafonné à 0,2 point, une non-linéarité de plus, propre à ce levier.
CONSOLIDATIONS = {'coupe_depenses': ('collectivites', 'depenses', -1),
                  'coupe_transferts': ('retraites', 'depenses', -1),
                  'hausse_impots': ('impot_revenu', 'recettes', +1)}


@pytest.mark.parametrize('famille', list(CONSOLIDATIONS))
def test_multiplicateur_effectif_constant_de_1_a_8_pour_cent_du_pib(moteur_sans_non_linearites_declarees,
                                                                   famille):
    """Niveau du PIB réel à 4 ans par point de PIB de consolidation permanente : le même, à 2 % près,
    pour 1 %, 2 %, 2,9 %, 3,5 %, 4 %, 5 %, 6,5 % et 8 % du PIB. Mesuré : au plus 0,8 %. Une cicatrice
    réintroduite avec un seuil de 3,5 %, 4 % ou 5 % le relève de 8 à 16 % au-delà de son seuil ;
    v0.8.1 (seuil 3 %) : +5 à +6 % dès 3,5 %."""
    _verifier_multiplicateur_constant(famille, GRILLE, dette_elevee_neutralisee=True)


# Moteur complet : aucune non-linéarité neutralisée (facteur « dette élevée », régime de récession,
# filet de croissance), sur la partie de la grille où elles restent dans la tolérance.
GRILLE_MOTEUR_COMPLET = (0.01, 0.02, 0.029, 0.035, 0.04, 0.05, 0.065)


@pytest.mark.parametrize('famille', list(CONSOLIDATIONS))
def test_multiplicateur_effectif_constant_moteur_complet_de_1_a_6_5_pour_cent_du_pib(pleine_precision,
                                                                                    famille):
    """Même contrat, moteur complet, de 1 % à 6,5 % du PIB : rien n'est neutralisé, à part l'arrondi
    des sorties. Mesuré : écart au plus 0,9 % (tolérance 2 %) ; à 8 % du PIB, le facteur « dette
    élevée » et le filet de croissance portent l'écart jusqu'à 6,1 %, d'où le test précédent, qui les
    neutralise, pour ce point. Une cicatrice réservée aux économies déprimées (pondérée par le régime
    de récession, effort lu chez l'orchestrateur) le fait rougir avec un seuil de 2 % à 5 %, comme le
    test précédent (recontrôle du 15/11/2026)."""
    _verifier_multiplicateur_constant(famille, GRILLE_MOTEUR_COMPLET, dette_elevee_neutralisee=False)


def _verifier_multiplicateur_constant(famille, grille, dette_elevee_neutralisee):
    levier, flux, signe = CONSOLIDATIONS[famille]
    base = _pib_reel(dette_elevee_neutralisee=dette_elevee_neutralisee)

    def multiplicateur(s):
        y = _pib_reel(levier, flux, signe * s, dette_elevee_neutralisee=dette_elevee_neutralisee)
        return abs(y[5] - base[5]) / base[5] / s

    m = {s: multiplicateur(s) for s in grille}
    reference = m[grille[0]]
    ecarts = {s: v / reference - 1 for s, v in m.items()}
    assert all(abs(e) <= 0.02 for e in ecarts.values()), (famille, {s: round(e, 4) for s, e in ecarts.items()})


def test_l_etat_de_croissance_ne_porte_plus_d_effort_interieur():
    """Plomberie : l'effort intérieur n'avait plus que la cicatrice pour lecteur ; il n'est plus
    calculé ni transmis. Le principe qu'il portait (un flux vers un agent non résident n'a pas
    d'effet de demande) reste tenu par les impulsions (``MESURES_HORS_DEMANDE_INTERIEURE``)."""
    sim = BudgetSimulatorV45(periods=4, mesures={'transferts_etranger': {'montant': -5.0}})
    origine, cles = sim.calculate_growth, set()

    def espion(year, etat):
        cles.update(etat)
        return origine(year, etat)
    sim.calculate_growth = espion
    sim.simulate()
    assert cles and 'effort_interieur' not in cles, sorted(cles)
    assert not hasattr(sim, '_budget_effort_interieur_prev')
