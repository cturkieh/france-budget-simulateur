"""Dotation aux collectivités : une variation pèse pour moitié sur l'investissement local (lot 5c des
corrections d'équations).

Arbitrage du mainteneur du 16/11/2026 : une variation de ``collectivites.dotation`` est prise pour une part
(``PART_DOTATION_INVESTIE``, 0,5) comme une variation d'investissement local, pour le reste comme de la
dépense courante, dans les deux sens. L'effet direct sur le déficit reste d'un euro pour un euro. Avant :
la dotation entière était de la dépense courante.

Sources (METHODOLOGIE, encadré du lot 5c) : Caisse des Dépôts, Éclairages n° 8 (2015), élasticité de
l'investissement local aux dotations, symétrique à court terme ; Cour des comptes, Les finances publiques
locales (2018), bilan de la baisse 2014-2017. « La moitié » est le centre de la fourchette des baisses
durables, pas un chiffre publié (fourchette publiée : 20 % à 60 %).

Deux références, déclarées : l'IMPULSION de la part investie se compte depuis le défaut du moteur, comme
toute dépense ; son EFFET D'OFFRE, en mode cadre seulement, depuis la dotation du droit en vigueur de
l'année, pour que le statu quo, qui applique ce droit, ne consomme aucune offre (contrat W6-10,
``test_effet_offre_echelle_v0612.py``, inchangé). Le mode historique n'applique pas le droit en vigueur :
la part investie n'y a pas d'effet d'offre, et le fichier du droit n'y est pas lu.

Contrat verrouillé ici, dans le moteur complet :

1. la part est une constante nommée de ``constants.py`` lue par le registre ``PARTS_INVESTIES`` ;
2. (non-vacuité des deux références) le droit en vigueur porte une dotation différente du défaut ;
3. IMPULSION, deux modes : la part investie a exactement l'impulsion du curseur
   ``collectivites.investissement`` à part × (dotation − défaut), dépense compensée (effet d'offre retiré
   des deux côtés) — identique au bit en mode historique, à 1e-12 près en relatif en mode cadre ;
4. OFFRE, mode cadre : la part investie a exactement l'effet d'offre du curseur à
   part × (dotation − dotation du droit) ;
5. OFFRE, mode historique : aucune, et aucune lecture du droit en vigueur (espion sur son chargeur) ;
6. une variation de dotation n'a plus le traitement de la seule dépense courante (non-vacuité) ;
7. hausse et baisse de dotation en miroir sur le PIB, de 1 à 4 ans, dans les deux modes ;
8. les chiffres publiés du lot (METHODOLOGIE, EXPLICATION) sont ceux du moteur.
"""
import copy
import re
import sys
from pathlib import Path

import pytest

from budget_simulator import constants as C
from budget_simulator.engine import cadre as cadre_mod
from budget_simulator.simulator import BudgetSimulatorV45

S = BudgetSimulatorV45
RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'tests' / 'snapshots'))
from run_scenarios_full import PROFILS, SCENARIOS, pour_le_mode  # noqa: E402
DEFAUT_DOTATION = 120.0   # défaut du registre (policy_measures.json), relu ci-dessous
COLONNES = {0: ('Dette/PIB %', 'Déficit/PIB %', 'Croissance %', 'Chômage %', 'Inflation %', 'PIB', 'Dette'),
            1: ('PIB_Réel_Base2025', 'Output_Gap %', 'Taux_Intérêt %', 'Recettes_Totales', 'Intérêts_Dette',
                'Croissance_Potentielle_Totale %')}


def test_la_part_est_une_constante_nommee_lue_par_le_registre():
    assert C.PART_DOTATION_INVESTIE == 0.5
    assert S.PARTS_INVESTIES == {'collectivites': {'dotation': C.PART_DOTATION_INVESTIE}}
    assert S.INVESTISSEMENT_PRODUCTIF_PARTIEL == {'collectivites': 'investissement'}
    assert S()._get_default_values()['collectivites']['dotation'] == DEFAUT_DOTATION


def _droit_dotation():
    return float(cadre_mod.charger_droit_en_vigueur().mesures['collectivites']['dotation'])


def test_le_droit_en_vigueur_porte_une_dotation_differente_du_defaut():
    """Non-vacuité des tests 4 et 5 : ils ne distinguent les deux références que si elles diffèrent. Le
    jour où le défaut du moteur serait aligné sur le droit, la condition de mode deviendrait inutile
    (METHODOLOGIE, encadré du lot 5c) : ce test le signalera."""
    assert _droit_dotation() != DEFAUT_DOTATION


def _run(mesures, annee_debut, part=None, droit_investissement=None, compenser_investissement=False,
         sans_offre=False):
    """Simulation complète, pleine précision. ``part`` remplace la part investie (0 = dotation sans part
    investie) ; ``droit_investissement`` pose ``collectivites.investissement`` dans le droit en vigueur
    (mode cadre) ; ``compenser_investissement`` retire de la dépense, chaque année, le montant du curseur
    d'investissement (la dépense totale du levier reste celle de la dotation, la part investie passe par
    le curseur) ; ``sans_offre`` retire tout canal d'offre (l'impulsion seule est comparée)."""
    import budget_simulator.engine.orchestrator as orch
    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
        if part is not None:
            mp.setattr(S, 'PARTS_INVESTIES', {'collectivites': {'dotation': part}})
        if sans_offre:
            mp.setattr(S, 'SUPPLY_EFFECTS', {})
        if droit_investissement is not None:
            origine = cadre_mod.charger_droit_en_vigueur

            def droit_modifie():
                d = copy.deepcopy(origine())
                d.mesures['collectivites'] = dict(d.mesures['collectivites'], investissement=droit_investissement)
                return d
            mp.setattr(cadre_mod, 'charger_droit_en_vigueur', droit_modifie)

        class _Banc(S):
            def apply_measures(self, year, spending, revenues, gdp, inflation, unemployment):
                sp, rv, imp = super().apply_measures(year, spending, revenues, gdp, inflation, unemployment)
                if compenser_investissement:
                    inv = float((self.mesures.get('collectivites') or {}).get('investissement', 0) or 0)
                    if inv and isinstance(imp.get('collectivites'), dict):
                        imp = dict(imp)
                        bloc = dict(imp['collectivites'])
                        bloc['depenses'] = float(bloc['depenses']) - inv
                        imp['collectivites'] = bloc
                        sp -= inv
                return sp, rv, imp
        return _Banc(periods=10, mesures=mesures, annee_debut=annee_debut).simulate()
    finally:
        mp.undo()


def _egales(a, b, rel=1e-12, abs_=1e-9):
    ecarts = []
    for table, colonnes in COLONNES.items():
        for col in colonnes:
            for i, (x, y) in enumerate(zip(a[table][col].values, b[table][col].values)):
                if x != pytest.approx(y, rel=rel, abs=abs_):
                    ecarts.append((col, i, x, y))
    return ecarts


@pytest.mark.parametrize('ecart', [-10.0, +10.0])
@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
def test_l_impulsion_de_la_part_investie_est_celle_du_curseur_depuis_le_defaut(annee_debut, ecart):
    """Dotation au droit applicable + ``ecart`` (défaut en mode historique, droit en vigueur en mode
    cadre), effet d'offre retiré : même trajectoire que la dotation sans part investie, plus le curseur
    d'investissement à part × (dotation − DÉFAUT) — dans le droit en vigueur aussi en mode cadre —, sa
    dépense compensée. Identique au bit en mode historique ; en mode cadre, l'écart relatif mesuré est de
    1,7e-15 (arithmétique flottante, x + y − y au dernier bit, sur la dotation du droit)."""
    part = C.PART_DOTATION_INVESTIE
    ref = DEFAUT_DOTATION if annee_debut is None else _droit_dotation()
    dotation = ref + ecart
    a = _run({'collectivites': {'dotation': dotation}}, annee_debut, sans_offre=True)
    droit_inv = part * (_droit_dotation() - DEFAUT_DOTATION) if annee_debut else None
    b = _run({'collectivites': {'dotation': dotation, 'investissement': part * (dotation - DEFAUT_DOTATION)}},
             annee_debut, part=0.0, droit_investissement=droit_inv, compenser_investissement=True,
             sans_offre=True)
    ecarts = _egales(a, b, rel=0.0 if annee_debut is None else 1e-12, abs_=0.0 if annee_debut is None else 1e-9)
    assert not ecarts, ecarts[:5]


def _offre_du_canal(mesures, annee_debut, part=None):
    """Contribution du canal ``collectivites_invest`` à l'offre structurelle, année par année."""
    mp = pytest.MonkeyPatch()
    try:
        if part is not None:
            mp.setattr(S, 'PARTS_INVESTIES', {'collectivites': {'dotation': part}})
        sim = S(periods=10, mesures=mesures, annee_debut=annee_debut)
        vus = []
        origine = sim.update_potential_growth

        def espion(growth, year):
            r = origine(growth, year)
            vus.append(sim._supply_bonus_by_key.get('collectivites_invest', 0.0))
            return r
        sim.update_potential_growth = espion
        sim.simulate()
        return vus
    finally:
        mp.undo()


@pytest.mark.parametrize('ecart', [-10.0, +10.0])
def test_mode_cadre_l_offre_de_la_part_investie_est_celle_du_curseur_depuis_le_droit(ecart):
    """Mode cadre, dotation du droit + ``ecart`` : sur le canal ``collectivites_invest``, exactement la
    contribution du curseur d'investissement à part × (dotation − dotation DU DROIT), sans part investie.
    Une offre comptée depuis le défaut donnerait au statu quo un bonus (W6-10) : la mutation rougit ici."""
    part = C.PART_DOTATION_INVESTIE
    dotation = _droit_dotation() + ecart
    par_dotation = _offre_du_canal({'collectivites': {'dotation': dotation}}, 2028)
    par_curseur = _offre_du_canal({'collectivites': {'investissement': part * (dotation - _droit_dotation())}},
                                  2028, part=0.0)
    assert any(par_dotation) and par_dotation == par_curseur, (par_dotation, par_curseur)


@pytest.mark.parametrize('ecart, investissement', [(-10.0, 10.0), (10.0, 10.0), (-10.0, -4.0)])
def test_la_part_investie_s_ajoute_a_l_ecart_du_curseur(ecart, investissement):
    """Mode cadre, dotation du droit + ``ecart`` ET curseur d'investissement bougés ensemble : sur le canal
    ``collectivites_invest``, exactement la contribution du curseur seul porté à
    ``investissement + part × ecart`` (sans part investie) : la part investie S'AJOUTE à l'écart du curseur.
    Une part qui le remplacerait (``delta = …`` au lieu de ``delta += …``) rougit ici ; sans ce test, toute la
    suite restait verte (aucun scénario publié ne bouge le curseur), pour un écart de +0,2 à +0,4 point de dette
    2032 sur un tel programme. Curseur dans son domaine [−10 ; 20]."""
    part = C.PART_DOTATION_INVESTIE
    ensemble = _offre_du_canal({'collectivites': {'dotation': _droit_dotation() + ecart,
                                                  'investissement': investissement}}, 2028)
    curseur = _offre_du_canal({'collectivites': {'investissement': investissement + part * ecart}}, 2028, part=0.0)
    assert any(ensemble) and ensemble == pytest.approx(curseur, rel=1e-12, abs=1e-15), (ensemble, curseur)


def _offre_et_coupe_du_rabot(mesures):
    """Contribution du canal ``collectivites_invest`` et part investie publiée de la coupe du rabot, année par
    année (la part que lit le moteur la même année, dans ``_last_impacts``)."""
    sim = S(periods=10, mesures=mesures, annee_debut=2028)
    vus = []
    origine = sim.update_potential_growth

    def espion(growth, year):
        r = origine(growth, year)
        rabot = (sim._last_impacts or {}).get('rabot_uniforme')
        part = float(rabot.get('depenses_investissement', 0) or 0) if isinstance(rabot, dict) else 0.0
        vus.append((sim._supply_bonus_by_key.get('collectivites_invest', 0.0), part))
        return r
    sim.update_potential_growth = espion
    sim.simulate()
    return vus


@pytest.mark.parametrize('ecart, investissement', [(-10.0, 10.0), (10.0, -4.0)])
def test_rabot_dotation_et_curseur_ensemble_les_trois_parts_s_ajoutent(ecart, investissement):
    """Même contrat avec la coupe de dotation du rabot (M1) : rabot, dotation et curseur bougés ensemble. Chaque
    année où le canal est actif, sa contribution est celle du curseur seul porté à ``investissement + part ×
    ecart``, plus la pente du canal × la part investie publiée de la coupe du rabot de l'année ; les années où il
    ne l'est pas encore (délai du canal), aucune contribution. Une part du rabot qui remplacerait les deux autres,
    ou une part de la dotation qui remplacerait l'écart du curseur, rougit ici."""
    part = C.PART_DOTATION_INVESTIE
    pente = S.SUPPLY_EFFECTS['collectivites_invest']['pente']
    avec = _offre_et_coupe_du_rabot({'rabot_uniforme': {'taux_reduction': 0.08},
                                     'collectivites': {'dotation': _droit_dotation() + ecart,
                                                       'investissement': investissement}})
    curseur = _offre_du_canal({'collectivites': {'investissement': investissement + part * ecart}}, 2028, part=0.0)
    assert len(avec) == len(curseur)
    actives = [(bonus, coupe, ref) for (bonus, coupe), ref in zip(avec, curseur) if ref]
    assert len(actives) >= 3 and all(coupe < 0 for _, coupe, _ in actives), 'non-vacuité : coupe publiée'
    for (bonus, coupe), ref in zip(avec, curseur):
        attendu = ref + pente * coupe if ref else 0.0
        assert bonus == pytest.approx(attendu, rel=1e-12, abs=1e-15), (bonus, coupe, ref)


def test_mode_historique_aucune_offre_de_la_part_investie_et_aucune_lecture_du_droit():
    """Mode historique, dotation à défaut − 10 : aucune contribution de la part investie au canal
    ``collectivites_invest``, et le chargeur du droit en vigueur n'est jamais appelé (contrat de
    non-lecture du mode historique, ``test_release_e_w1.py``) — par construction, pas par une exception
    rattrapée. Témoin : le même espion voit le chargeur en mode cadre."""
    appels = []
    origine = cadre_mod._droit_en_vigueur_valide

    def espion():
        appels.append(1)
        return origine()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(cadre_mod, '_droit_en_vigueur_valide', espion)
        offre = _offre_du_canal({'collectivites': {'dotation': DEFAUT_DOTATION - 10}}, None)
        assert offre and all(x == 0.0 for x in offre), offre
        assert appels == []
        _offre_du_canal({'collectivites': {'dotation': DEFAUT_DOTATION - 10}}, 2028)
        assert appels, "témoin : l'espion doit voir le chargeur en mode cadre"


@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
def test_la_dotation_n_est_plus_de_la_seule_depense_courante(annee_debut):
    """Non-vacuité : sans part investie, la même baisse de dotation donne une autre trajectoire."""
    ref = DEFAUT_DOTATION if annee_debut is None else _droit_dotation()
    a = _run({'collectivites': {'dotation': ref - 10}}, annee_debut)
    b = _run({'collectivites': {'dotation': ref - 10}}, annee_debut, part=0.0)
    assert abs(a[0]['Dette/PIB %'].values[-1] - b[0]['Dette/PIB %'].values[-1]) > 0.05


@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
def test_hausse_et_baisse_de_dotation_en_miroir(annee_debut):
    """±10 Md€ de dotation autour du droit applicable : PIB réel en miroir à 1 % près de 1 à 4 ans
    (mesuré : au plus 0,5 % sur le lot 5c seul ; au plus 0,9 % sur la pile d'intégration, lots 2 et 6
    appliqués : le budget agit dès son année, le choc fixe en euros pèse un an plus tôt sur un PIB plus petit). Au-delà, le niveau d'un choc fixe en euros revient vers zéro et l'écart
    dépasse 1 % à 6 ans, déjà avant le lot 5c (1,3 %) : ce n'est pas une propriété de ce levier."""
    ref = DEFAUT_DOTATION if annee_debut is None else _droit_dotation()
    y0 = _run({}, annee_debut)[1]['PIB_Réel_Base2025'].values
    yh = _run({'collectivites': {'dotation': ref + 10}}, annee_debut)[1]['PIB_Réel_Base2025'].values
    yb = _run({'collectivites': {'dotation': ref - 10}}, annee_debut)[1]['PIB_Réel_Base2025'].values
    debut = (annee_debut or 2026) - 2025
    for h in range(1, 5):
        i = debut + h
        hausse, baisse = yh[i] / y0[i] - 1, yb[i] / y0[i] - 1
        assert hausse > 0 > baisse, (h, hausse, baisse)
        assert abs(abs(baisse) / hausse - 1) < 0.01, (annee_debut, h, hausse, baisse)


def _fr(x, decimales=2, signe=False):
    t = f'{x:+.{decimales}f}' if signe else f'{x:.{decimales}f}'
    return t.replace('-', '−').replace('.', ',')


def _dette_2032_cadre(mesures, part=None, offre_depuis_le_defaut=False):
    mp = pytest.MonkeyPatch()
    try:
        if offre_depuis_le_defaut:
            origine = S.references_d_offre_des_parts_investies
            mp.setattr(S, 'references_d_offre_des_parts_investies',
                       lambda self, m, a: None if origine(self, m, a) is None else {})
        return float(_run(mesures, 2028, part=part)[0].set_index('Année').at[2032, 'Dette/PIB %'])
    finally:
        mp.undo()


def test_chiffres_publies_du_lot_lies_a_la_mesure():
    """Les chiffres de l'encadré du lot 5c (METHODOLOGIE) et de la note d'EXPLICATION sont recalculés ici et
    cherchés tels quels (mode cadre 2028, dette 2032) : l'écart entre les deux références, son effet sur la
    référence sans programme, ce qu'y ajouterait une offre comptée depuis le défaut, et les variantes à 20 %
    et 60 % d'une baisse durable de 10 Md€ sous le droit."""
    part, droit = C.PART_DOTATION_INVESTIE, _droit_dotation()
    ref_0, ref = _dette_2032_cadre({}, part=0.0), _dette_2032_cadre({})
    depuis_le_defaut = _dette_2032_cadre({}, offre_depuis_le_defaut=True)
    coupe = {'collectivites': {'dotation': droit - 10}}
    avant = _dette_2032_cadre(coupe, part=0.0) - ref_0
    effet = {p: (_dette_2032_cadre(coupe, part=p) - _dette_2032_cadre({}, part=p)) - avant for p in (0.2, 0.5, 0.6)}
    assert effet[0.2] < effet[0.5] < effet[0.6]
    ecart = part * (DEFAUT_DOTATION - droit)
    methodologie = ' '.join(re.sub(r'\n>\s?', ' ', (RACINE / 'docs' / 'METHODOLOGIE.md')
                                   .read_text(encoding='utf-8')).split())
    for attendu in (
            f"Tant que le droit ({_fr(droit, 1)} Md€) reste sous le défaut ({DEFAUT_DOTATION:g} Md€), les deux "
            f"montants diffèrent de {_fr(ecart, 1)} Md€ par an",
            f"de {_fr(ecart, 1)} Md€ par an ({_fr(ref - ref_0, signe=True)} point de dette 2032), sans son effet "
            f"d'offre, qui lui ajouterait {_fr(depuis_le_defaut - ref)} point de dette 2032",
            f"{_fr(effet[0.5], signe=True)} point à la part retenue (50 %), {_fr(effet[0.2], signe=True)} point "
            f"à 20 % et {_fr(effet[0.6], signe=True)} point à 60 %"):
        assert attendu in methodologie, attendu
    explication = ' '.join((RACINE / 'docs' / 'EXPLICATION_MODELE_ECONOMIQUE.md').read_text(encoding='utf-8').split())
    for attendu in (f"alourdit la dette 2032 de {_fr(effet[0.5])} point de plus qu'avant",
                    f"la dotation {_fr(DEFAUT_DOTATION - droit, 1)} Md€ sous la valeur de base du moteur",
                    f"({_fr(ref - ref_0, signe=True)} point de dette 2032 pour la référence)"):
        assert attendu in explication, attendu


def _indicateurs_cadre(nom, part, sans_offre=False, sans_coupe_du_rabot=False):
    """Scénario publié ``nom`` (None : référence sans programme), mode cadre 2028 comme le précalcul (profils
    compris), pleine précision : dette et déficit 2032, croissance moyenne 2028-2032, Gini 2032. ``part``
    remplace la part investie (0 : état d'avant le lot) ; ``sans_offre`` retire l'effet d'offre de la part
    investie (curseur de dotation et coupe du rabot) ; ``sans_coupe_du_rabot`` retire la part investie de la
    coupe du rabot (impulsion et offre)."""
    import budget_simulator.engine.orchestrator as orch
    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
        mp.setattr(S, 'PARTS_INVESTIES', {'collectivites': {'dotation': part}})
        if sans_offre:
            mp.setattr(S, 'references_d_offre_des_parts_investies', lambda self, m, a: None)
        if sans_offre or sans_coupe_du_rabot:
            mp.setattr(S, 'part_investie_des_coupes_de_dotation', lambda self: 0.0)
        if sans_coupe_du_rabot:
            mp.setattr(S, 'part_investie_d_une_variation_de_dotation', lambda self, variation: 0.0)
        mesures = pour_le_mode(SCENARIOS[nom], 2028) if nom else {}
        df = S(periods=10, mesures=mesures, annee_debut=2028,
               profils=(PROFILS.get(nom) or None) if nom else None).simulate()[0].set_index('Année')
        return {'dette': float(df.at[2032, 'Dette/PIB %']), 'deficit': float(df.at[2032, 'Déficit/PIB %']),
                'croissance': float(sum(df.at[a, 'Croissance %'] for a in range(2028, 2033)) / 5),
                'gini': float(df.at[2032, 'Gini'])}
    finally:
        mp.undo()


def _de_a(valeurs, signe=True):
    """« x à y », du plus petit au plus grand écart en valeur absolue, au millième."""
    tri = sorted(valeurs, key=abs)
    return f"{_fr(tri[0], 3, signe)} à {_fr(tri[-1], 3, signe)}"


@pytest.mark.skipif(not SCENARIOS, reason="scenarios.json absent (fork moteur seul)")
def test_ce_qui_bouge_et_decomposition_lies_a_la_mesure():
    """Réfutation B du lot 5c : le paragraphe « Ce qui bouge » et la décomposition de l'encadré du lot sont
    recalculés ici en PLEINE PRÉCISION (et non sur les sorties arrondies) et cherchés tels quels : dette 2032
    des trois groupes (dotation du droit gardée, dotation baissée, rabot uniforme), effet de la coupe du rabot,
    déficit 2032, croissance moyenne 2028-2032, Gini ; décomposition avec le profil de l'investissement (sans
    effet d'offre) et avec l'effet d'offre ; double compte demande + offre de la limite (5). Les groupes sont
    lus dans les mesures des scénarios. Non liés : le
    « coefficient seul » (il faudrait substituer le profil des impulsions) et les rangs."""
    part, droit = C.PART_DOTATION_INVESTIE, _droit_dotation()
    noms = list(SCENARIOS) + [None]
    avant = {n: _indicateurs_cadre(n, 0.0) for n in noms}
    apres = {n: _indicateurs_cadre(n, part) for n in noms}
    ecart = {n: {k: apres[n][k] - avant[n][k] for k in apres[n]} for n in noms}
    groupes = {'garde': [], 'baisse': [], 'rabot': []}
    baisses = []
    for n in SCENARIOS:
        mesures = pour_le_mode(SCENARIOS[n], 2028)
        dotation = (mesures.get('collectivites') or {}).get('dotation', droit)
        if ((mesures.get('rabot_uniforme') or {}).get('taux_reduction') or 0) > 0:
            groupes['rabot'].append(n)
        elif dotation < droit - 1e-9:
            groupes['baisse'].append(n)
            baisses.append(droit - dotation)
        else:
            assert dotation == pytest.approx(droit), n
            groupes['garde'].append(n)
    assert [len(g) for g in groupes.values()] == [6, 3, 1], groupes
    (rabot,) = groupes['rabot']
    coupe = ecart[rabot]['dette'] - (_indicateurs_cadre(rabot, part, sans_coupe_du_rabot=True)['dette']
                                     - avant[rabot]['dette'])
    tous = list(SCENARIOS)
    assert max(abs(ecart[n]['gini']) for n in noms) < 1e-4
    sans_offre = {n: _indicateurs_cadre(n, part, sans_offre=True)['dette'] - avant[n]['dette']
                  for n in groupes['baisse'] + groupes['rabot'] + [None]}
    double_compte = [ecart[n]['dette'] - sans_offre[n] for n in groupes['baisse'] + groupes['rabot']]
    methodologie = ' '.join(re.sub(r'\n>\s?', ' ', (RACINE / 'docs' / 'METHODOLOGIE.md')
                                   .read_text(encoding='utf-8')).split())
    for attendu in (
            f"dette 2032 de {_de_a([ecart[n]['dette'] for n in groupes['garde']])} point pour les six qui gardent la "
            f"dotation du droit (référence : {_fr(ecart[None]['dette'], 3, True)}), "
            f"de {_de_a([ecart[n]['dette'] for n in groupes['baisse']])} point pour les trois programmes qui la "
            f"baissent de {min(baisses):.0f} à {max(baisses):.0f} Md€, {_fr(ecart[rabot]['dette'], 3, True)} point "
            f"pour celui qui utilise le rabot uniforme (dont {_fr(coupe, 3, True)} pour sa coupe de dotation) ; "
            f"déficit 2032 de {_de_a([ecart[n]['deficit'] for n in tous])} point ; croissance moyenne 2028-2032 "
            f"de {_de_a([ecart[n]['croissance'] for n in tous])} point ; Gini inchangé (écart inférieur à 0,0001)",
            f"avec le profil de l'investissement, "
            f"{_de_a([sans_offre[n] - sans_offre[None] for n in groupes['baisse']])} point",
            f"avec aussi l'effet d'offre (ce commit), "
            f"{_de_a([ecart[n]['dette'] - ecart[None]['dette'] for n in groupes['baisse']])} point",
            f"qui pèse ici de {_de_a(double_compte, signe=False)} point de dette 2032 pour les quatre scénarios qui "
            f"baissent la dotation, celui du rabot uniforme compris"):
        assert attendu in methodologie, attendu


# --- Réfutation du lot 5c : coupe de dotation du rabot (M1), levier en échec (m1) ----------------------

def test_le_rabot_coupe_la_meme_ligne_que_le_curseur_de_dotation():
    """Périmètre (M1) : la catégorie « collectivites » des dépenses, que coupe le rabot uniforme, est la ligne
    « Dotations » que déplace le curseur ``collectivites.dotation`` (même montant de base, son défaut)."""
    sim = S()
    assert sim.spending_categories_base['collectivites'] == DEFAUT_DOTATION
    assert S.COUPES_DE_DOTATION == {'rabot_uniforme'}


class _Rabot(BudgetSimulatorV45):
    """Rabot uniforme : coupe de la ligne « Dotations » de l'année, recalculée comme le levier la calcule
    (base de l'année × taux × phasing), et part investie publiée dans son impact."""

    def _apply_rabot_uniforme(self, measure, params, year, gdp, inflation, unemployment):
        dep, rec, imp = super()._apply_rabot_uniforme(measure, params, year, gdp, inflation, unemployment)
        if imp:
            d = imp['rabot_details']
            coupe = (self.spending_categories_base['collectivites']
                     * self._spending_factors.get('collectivites', 1.0) * d['taux'] * d['phasing'])
            self.__dict__.setdefault('_coupes', []).append((coupe, imp['depenses_investissement']))
        return dep, rec, imp


@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
def test_la_coupe_de_dotation_du_rabot_a_sa_part_investie(annee_debut):
    """M1 : la coupe de la ligne « Dotations » par le rabot prend la règle du lot, par la même part :
    ``depenses_investissement`` du rabot = part × (−coupe) chaque année (impulsion d'investissement)."""
    sim = _Rabot(periods=10, mesures={'rabot_uniforme': {'taux_reduction': 0.08}}, annee_debut=annee_debut)
    sim.simulate()
    assert sim._coupes
    for coupe, part_investie in sim._coupes:
        assert coupe > 0
        assert part_investie == pytest.approx(-C.PART_DOTATION_INVESTIE * coupe, rel=1e-12)


@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
def test_la_coupe_de_dotation_du_rabot_nourrit_l_offre_en_mode_cadre(annee_debut):
    """M1 : en mode cadre, la part investie de la coupe nourrit le canal ``collectivites_invest`` (une
    contribution négative, une coupe) ; en mode historique, aucune offre, comme pour le curseur. Sans part
    investie, aucune contribution."""
    mesures = {'rabot_uniforme': {'taux_reduction': 0.08}}
    avec = _offre_du_canal(mesures, annee_debut)
    sans = _offre_du_canal(mesures, annee_debut, part=0.0)
    assert not any(sans)
    if annee_debut is None:
        assert not any(avec)
    else:
        assert any(avec) and all(x <= 0 for x in avec)


class _Rabot_par_annee(BudgetSimulatorV45):
    """Rabot uniforme : coupe de la ligne « Dotations » de chaque année civile, recalculée comme le levier la
    calcule (base de l'année × taux × phasing), et contribution du canal ``collectivites_invest`` de l'année."""

    def _apply_rabot_uniforme(self, measure, params, year, gdp, inflation, unemployment):
        dep, rec, imp = super()._apply_rabot_uniforme(measure, params, year, gdp, inflation, unemployment)
        if imp:
            d = imp['rabot_details']
            self.__dict__.setdefault('_coupe_par_an', {})[year] = (
                self.spending_categories_base['collectivites'] * self._spending_factors.get('collectivites', 1.0)
                * d['taux'] * d['phasing'])
        return dep, rec, imp

    def update_potential_growth(self, growth, year):
        r = super().update_potential_growth(growth, year)
        self.__dict__.setdefault('_offre_par_an', {})[self.annee_base + year] = (
            self._supply_bonus_by_key.get('collectivites_invest', 0.0))
        return r


def test_l_offre_de_la_coupe_du_rabot_est_celle_du_curseur_pour_part_x_coupe():
    """Le MONTANT, pas seulement le signe : en mode cadre, rabot seul, chaque année active du canal, sa
    contribution est pente × (−part × coupe), la coupe recalculée comme le levier la calcule, c'est-à-dire la
    contribution qu'aurait le curseur d'investissement porté à −part × coupe, à la précision machine ; avant le
    délai du canal, aucune. Une offre du rabot doublée (impulsion inchangée) rougit ici, sans les scénarios
    publiés."""
    part, cfg = C.PART_DOTATION_INVESTIE, S.SUPPLY_EFFECTS['collectivites_invest']
    sim = _Rabot_par_annee(periods=10, mesures={'rabot_uniforme': {'taux_reduction': 0.08}}, annee_debut=2028)
    sim.simulate()
    premiere = min(sim._coupe_par_an)
    actives = sorted(a for a, v in sim._offre_par_an.items() if v)
    assert actives == [a for a in sorted(sim._offre_par_an) if a >= premiere + cfg['delay'] - 1], actives
    assert len(actives) >= 3
    for a in actives:
        assert sim._offre_par_an[a] == pytest.approx(cfg['pente'] * (-part * sim._coupe_par_an[a]), rel=1e-12), a


@pytest.mark.parametrize('annee_debut', [None, 2028], ids=['historique', 'cadre2028'])
@pytest.mark.parametrize('mesures', [{'collectivites': {'dotation': 'x'}},
                                     {'collectivites': {'dotation': 'x', 'investissement': 5}}],
                         ids=['dotation_non_numerique', 'avec_curseur'])
def test_un_levier_en_echec_n_a_ni_impulsion_ni_offre(monkeypatch, mesures, annee_debut):
    """m1 : une dotation non numérique fait échouer le levier (ni dépense ni impulsion) ; il n'a pas
    d'effet d'offre non plus, ni par la part investie de la dotation, ni par son curseur
    d'investissement (avant : +1,7 Md€ d'offre « fantôme », depuis le défaut du registre). Mode
    tolérant posé ici : en mode strict, la même valeur est refusée à l'entrée."""
    monkeypatch.setenv('BUDGETLAB_STRICT', '')
    sim = _Canal_offre(periods=10, mesures=mesures, annee_debut=annee_debut)
    sim.simulate()
    assert sim._echecs, 'non-vacuité : le levier échoue'
    assert not any(sim._offres), sim._offres
    assert ('collectivites', 'investissement') not in sim._niveaux_impulsion


class _Canal_offre(BudgetSimulatorV45):
    def update_potential_growth(self, growth, year):
        r = super().update_potential_growth(growth, year)
        self.__dict__.setdefault('_offres', []).append(self._supply_bonus_by_key.get('collectivites_invest', 0.0))
        imp = (self._last_impacts or {}).get('collectivites')
        if isinstance(imp, dict) and imp.get('_handler_failed'):
            self.__dict__.setdefault('_echecs', []).append(year)
        return r
