"""Effet prix des rémunérations publiques sur le PIB en valeur publié (lot 5d des corrections d'équations).

Règle : le coût employeur de l'année des rémunérations publiques à effectifs constants — le canal ménages
``remunerations_publiques`` de TOUS les leviers, part « agents publics » du SMIC comprise
(``cout_employeur_des_remunerations``, source unique : le canal que lisent l'impulsion du lot 5b et le pouvoir
d'achat) — s'ajoute au PIB en valeur PUBLIÉ, en niveau, dans les deux sens. L'effet prix est une identité
comptable : l'exception du SMIC (coefficient propre) ne vaut que pour la demande. Le déflateur publié en est relevé d'autant (PIB publié = PIB
réel × déflateur publié), l'inflation publiée du déflateur est sa variation, et les ratios publiés (dette,
déficit, recettes, dépenses) sont rapportés au PIB publié. Rien n'entre dans le moteur : PIB nominal, déflateur et
inflation internes, IPC, croissance, chômage, soldes en euros, prime de taux, pouvoir d'achat, Gini restent ceux
de l'état sans effet prix.

Sources (METHODOLOGIE, encadré du lot 5d) : SEC 2010 § 10.28 (production non marchande évaluée à la somme de ses
coûts), § 10.30 et § 10.44 (une hausse de rémunération à effectifs constants est un prix) ; Mésange 2017 p. 92
(le prix de la valeur ajoutée non marchande suit le salaire moyen par tête non marchand) ; Insee Première
n° 1950, mai 2023 (le déflateur de la consommation des APU tiré par la revalorisation du point d'indice).

Contrat verrouillé ici, dans le moteur complet, à la précision machine (arrondi des sorties retiré) :

1. identité publiée : PIB = PIB réel × déflateur, avec et sans rémunération ; inflation publiée = variation du
   déflateur publié ;
2. le PIB publié porte, CHAQUE année, exactement le coût employeur de l'année (somme des canaux de tous les
   leviers, SMIC compris), ni plus (effectifs exclus) ni moins ;
3. ratios publiés = ratios internes × PIB interne / PIB publié ;
4. toute autre colonne (IPC, PIB réel, croissance, chômage, soldes et stocks en euros, recettes et dépenses en
   euros, taux, effort budgétaire, écart de production, potentiel, pouvoir d'achat, Gini, compétitivité) est
   identique au bit à l'état sans effet prix ;
5. sans rémunération, tout est identique au bit ; le SMIC seul relève le PIB publié du montant de son canal, et
   rien d'autre ;
6. symétrie de signe : une hausse et une baisse de même ampleur déplacent le PIB publié en miroir.
"""
import re
import sys
from pathlib import Path

import pytest

import budget_simulator.engine.orchestrator as orch
from budget_simulator.simulator import BudgetSimulatorV45, FiscalMultipliers

S = BudgetSimulatorV45
NETS = FiscalMultipliers.MESURES_MULTIPLICATEUR_NET
RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'tests' / 'snapshots'))
from run_scenarios_full import PROFILS, SCENARIOS, pour_le_mode  # noqa: E402

PROGRAMMES = {
    'point_indice': {'fonction_publique': {'point_indice': 3.0}},
    'enseignants': {'education': {'salaires': 5}},
    'smic': {'smic': {'montant_brut': 2000}},
    'mixte': {'fonction_publique': {'point_indice': -2.0, 'effectifs': -40000},
              'education': {'salaires': 4, 'enseignants': 5000, 'budget': 66},
              'smic': {'montant_brut': 2000}, 'tva_rate': {'taux': 0.21}},
}
SANS_REMUNERATION = {
    'defense_et_tva': {'defense': {'budget': 60}, 'tva_rate': {'taux': 0.21}},
}
RATIOS = ('Dette/PIB %', 'Déficit/PIB %', 'Recettes/PIB %', 'Dépenses/PIB %')
INCHANGEES = {0: ('Croissance %', 'Inflation IPC %', 'Déficit', 'Dette', 'Chômage %', 'Gini', "Pouvoir d'Achat",
                  'Competitivite'),
              1: ('Recettes_Totales', 'Dépenses_Totales', 'Intérêts_Dette', 'Dépenses_Totales_Avec_Intérêts',
                  'Taux_Intérêt %', 'Effort_Budgétaire %', 'Multiplicateur', 'PIB_Réel_Base2025', 'Output_Gap %',
                  'Croissance_Potentielle %', 'Bonus_Potentiel_Supply %', 'Bonus_Offre_Travail %',
                  'Croissance_Potentielle_Totale %', 'RDB_Ménages_Md€', 'RDB_Effet_Mesures_Md€', 'Prix_Consommation')}


class _Canal(BudgetSimulatorV45):
    """Somme, année par année, du canal ``remunerations_publiques`` de tous les leviers (SMIC compris), dans les
    impacts réellement appliqués (après plafonds)."""

    def apply_measures(self, year, spending, revenues, gdp, inflation, unemployment):
        sp, rv, imp = super().apply_measures(year, spending, revenues, gdp, inflation, unemployment)
        total = 0.0
        for m, bloc in imp.items():
            canaux = bloc.get('menages') if isinstance(bloc, dict) else None
            if isinstance(canaux, dict):
                total += float(canaux.get('remunerations_publiques', 0) or 0)
        self.__dict__.setdefault('_canal', {})[year] = total
        return sp, rv, imp


def _run(mesures, annee_debut, sans_effet_prix=False):
    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
        if sans_effet_prix:
            mp.setattr(S, '_cout_remunerations_annee', lambda self, impacts: 0.0)
        sim = _Canal(periods=10, mesures=mesures, annee_debut=annee_debut)
        df, detail, _ = sim.simulate()
        return df.set_index('Année'), detail.set_index('Année'), sim.__dict__.get('_canal', {})
    finally:
        mp.undo()


CAS = [(nom, debut) for nom in list(PROGRAMMES) + list(SANS_REMUNERATION) for debut in (None, 2028)]


def _mesures(nom):
    return PROGRAMMES.get(nom) or SANS_REMUNERATION[nom]


@pytest.fixture(scope='module')
def runs():
    cache = {}

    def run(nom, debut, sans_effet_prix=False):
        cle = (nom, debut, sans_effet_prix)
        if cle not in cache:
            cache[cle] = _run(_mesures(nom), debut, sans_effet_prix)
        return cache[cle]
    return run


@pytest.mark.parametrize('nom, debut', CAS)
def test_identite_publiee_pib_egal_pib_reel_fois_deflateur(runs, nom, debut):
    """PIB publié = PIB réel × déflateur publié, chaque année ; inflation publiée = variation du déflateur
    publié. Rompue si le PIB publié est relevé sans le déflateur."""
    df, detail, _ = runs(nom, debut)
    for an in df.index:
        assert df.at[an, 'PIB'] == pytest.approx(detail.at[an, 'PIB_Réel_Base2025'] * detail.at[an, 'Déflateur'],
                                                 rel=1e-12), (nom, debut, an)
    for an in df.index[1:]:
        assert df.at[an, 'Inflation %'] / 100 == pytest.approx(
            detail.at[an, 'Déflateur'] / detail.at[an - 1, 'Déflateur'] - 1, rel=1e-9, abs=1e-12), (nom, debut, an)


@pytest.mark.parametrize('debut', [None, 2028])
@pytest.mark.parametrize('nom', list(PROGRAMMES))
def test_le_pib_publie_porte_chaque_annee_le_cout_employeur_de_l_annee(runs, nom, debut):
    """Chaque année : PIB publié − PIB interne = somme des canaux de rémunération de tous les leviers, SMIC
    compris (coût de l'année, en niveau), à la précision machine ; les effectifs n'y entrent pas."""
    avec, _, canal = runs(nom, debut)
    sans, _, _ = runs(nom, debut, sans_effet_prix=True)
    assert any(canal.values()), 'non-vacuité : le programme émet des rémunérations'
    for an in avec.index:
        assert avec.at[an, 'PIB'] - sans.at[an, 'PIB'] == pytest.approx(canal.get(an, 0.0), rel=1e-9, abs=1e-9), \
            (nom, debut, an)


@pytest.mark.parametrize('nom, debut', CAS)
def test_ratios_publies_rapportes_au_pib_publie(runs, nom, debut):
    """Ratio publié × PIB publié = ratio interne × PIB interne (dette, déficit, recettes, dépenses)."""
    avec, _, _ = runs(nom, debut)
    sans, _, _ = runs(nom, debut, sans_effet_prix=True)
    for col in RATIOS:
        for an in avec.index:
            assert avec.at[an, col] * avec.at[an, 'PIB'] == pytest.approx(sans.at[an, col] * sans.at[an, 'PIB'],
                                                                          rel=1e-12), (nom, debut, col, an)


@pytest.mark.parametrize('nom, debut', CAS)
def test_tout_le_reste_est_identique_au_bit(runs, nom, debut):
    """IPC, PIB réel, croissance, chômage, soldes et stocks en euros, taux, effort, écart de production,
    potentiel, pouvoir d'achat, Gini, compétitivité : identiques au bit à l'état sans effet prix. L'effet prix
    n'entre ni dans le PIB nominal interne ni dans l'IPC."""
    avec = runs(nom, debut)
    sans = runs(nom, debut, sans_effet_prix=True)
    for table, colonnes in INCHANGEES.items():
        for col in colonnes:
            assert list(avec[table][col]) == list(sans[table][col]), (nom, debut, col)


@pytest.mark.parametrize('nom, debut', [(n, d) for n in SANS_REMUNERATION for d in (None, 2028)])
def test_sans_remuneration_tout_est_identique_au_bit(runs, nom, debut):
    """Sans rémunération publique, le coût est nul et toutes les colonnes publiées sont celles de l'état
    sans effet prix, au bit."""
    avec, d_avec, canal = runs(nom, debut)
    sans, d_sans, _ = runs(nom, debut, sans_effet_prix=True)
    assert not any(canal.values())
    assert avec.equals(sans) and d_avec.equals(d_sans), nom


@pytest.mark.parametrize('debut', [None, 2028])
def test_hausse_et_baisse_en_miroir_sur_le_pib_publie(debut):
    """Point d'indice ±2 % : une hausse relève le PIB publié, une baisse l'abaisse, chaque année, de
    montants en miroir à 1 % près. Le miroir n'est pas exact au bit : le coût de l'année suit la masse
    salariale, indexée sur les prix, un peu différents après une hausse et après une baisse (mesuré :
    0,015 % la première année, 0,34 % la dixième) ; l'égalité exacte porte sur « écart = coût de
    l'année » (test précédent)."""
    ecarts = {}
    for signe in (+1, -1):
        avec, _, _ = _run({'fonction_publique': {'point_indice': 2.0 * signe}}, debut)
        sans, _, _ = _run({'fonction_publique': {'point_indice': 2.0 * signe}}, debut, sans_effet_prix=True)
        ecarts[signe] = (avec['PIB'] - sans['PIB']).values
    assert any(ecarts[+1])
    for h, b in zip(ecarts[+1], ecarts[-1]):
        if h or b:
            assert h > 0 > b, (h, b)
            assert abs(h / -b - 1) < 1e-2, (h, b)


@pytest.mark.parametrize('debut', [None, 2028])
def test_le_smic_seul_releve_le_pib_publie_de_sa_part_agents_publics(runs, debut):
    """La part « agents publics » de la hausse du SMIC est une hausse de rémunération à effectifs constants :
    elle reçoit l'effet prix comme les autres (identité comptable), alors que sa demande reste dans le solde
    du SMIC, au coefficient propre (lot 5b). Le PIB publié est relevé du montant du canal, chaque année ;
    toutes les colonnes internes restent identiques au bit."""
    avec, d_avec, canal = runs('smic', debut)
    sans, d_sans, _ = runs('smic', debut, sans_effet_prix=True)
    assert any(canal.values()), 'non-vacuité : le SMIC émet une part « agents publics »'
    for an in avec.index:
        assert avec.at[an, 'PIB'] - sans.at[an, 'PIB'] == pytest.approx(canal.get(an, 0.0), rel=1e-9, abs=1e-9), an
    for table, colonnes in INCHANGEES.items():
        for col in colonnes:
            assert list((avec, d_avec)[table][col]) == list((sans, d_sans)[table][col]), col


# --- Réfutation B du lot 5d : chiffres de « Ce qui bouge » liés à la mesure -----------------------------------

def _fr(x, decimales, signe=False):
    t = f'{x:+.{decimales}f}' if signe else f'{x:.{decimales}f}'
    return t.replace('-', '−').replace('.', ',')


def _de_a(valeurs, decimales=3, signe=True):
    """« x à y », du plus petit au plus grand écart en valeur absolue."""
    tri = sorted(valeurs, key=abs)
    return f"{_fr(tri[0], decimales, signe)} à {_fr(tri[-1], decimales, signe)}"


def _publie_cadre(nom, leviers='tous'):
    """Scénario publié ``nom`` (None : référence), mode cadre 2028 comme le précalcul, pleine précision. ``leviers`` :
    'tous' (le lot), None (effet prix retiré : l'état du lot 5b) ou l'ensemble des leviers dont le coût compte."""
    from budget_simulator.engine.growth import cout_employeur_des_remunerations
    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
        # Lot 5c (postérieur) neutralisé — part investie de la dotation nulle : les chiffres de l'encadré du lot 5d
        # sont ceux de son état (par rapport au lot 5b), pas ceux de la pile qui le suit.
        mp.setattr(S, 'PARTS_INVESTIES', {'collectivites': {'dotation': 0.0}})
        if leviers is None:
            mp.setattr(S, '_cout_remunerations_annee', lambda self, impacts: 0.0)
        elif leviers != 'tous':
            mp.setattr(S, '_cout_remunerations_annee', lambda self, impacts: cout_employeur_des_remunerations(
                {m: v for m, v in impacts.items() if m in leviers}))
        mesures = pour_le_mode(SCENARIOS[nom], 2028) if nom else {}
        df, _, rapport = S(periods=10, mesures=mesures, annee_debut=2028,
                           profils=(PROFILS.get(nom) or None) if nom else None).simulate()
        df = df.set_index('Année')
        emetteurs = {m for an in rapport['measure_impacts_by_year'] for m, v in an.items()
                     if m != 'Année' and isinstance(v, dict) and isinstance(v.get('menages'), dict)
                     and v['menages'].get('remunerations_publiques')}
        return {'dette': float(df.at[2032, 'Dette/PIB %']), 'deficit': float(df.at[2032, 'Déficit/PIB %']),
                'pib': float(df.at[2032, 'PIB']), 'inflation': [float(df.at[a, 'Inflation %']) for a in range(2028, 2033)],
                'euros_et_reel': [list(df[c]) for c in ('Dette', 'Déficit', 'Croissance %', 'Chômage %', 'Gini',
                                                        "Pouvoir d'Achat", 'Inflation IPC %')],
                'emetteurs': emetteurs}
    finally:
        mp.undo()


@pytest.mark.skipif(not SCENARIOS, reason="scenarios.json absent (fork moteur seul)")
def test_ce_qui_bouge_lie_a_la_mesure():
    """Réfutation B du lot 5d : le paragraphe « Ce qui bouge » de l'encadré (METHODOLOGIE) et la note d'EXPLICATION
    sont recalculés en PLEINE PRÉCISION et cherchés tels quels : dette et déficit 2032 rapportés au PIB, PIB publié
    2032, inflation du déflateur, décomposition par levier (chaque levier seul, et la part du SMIC retirée de
    l'ensemble). Les groupes de programmes sont lus dans les impacts (leviers qui versent une rémunération), sans
    nom de scénario. Vérifié aussi : la dette et le déficit en euros, la croissance, le chômage, le Gini, le pouvoir
    d'achat et l'indice des prix à la consommation sont identiques au bit, et les scénarios sans rémunération en
    tout. Non liés : les rangs."""
    noms = list(SCENARIOS) + [None]
    avant = {n: _publie_cadre(n, None) for n in noms}
    apres = {n: _publie_cadre(n) for n in noms}
    groupes = {'point': [], 'enseignants_et_smic': [], 'enseignants': [], 'aucun': []}
    for n in noms:
        em = apres[n]['emetteurs']
        cle = ('point' if 'fonction_publique' in em else 'enseignants_et_smic' if 'smic' in em
               else 'enseignants' if em else 'aucun')
        groupes[cle].append(n)
        assert apres[n]['euros_et_reel'] == avant[n]['euros_et_reel'], n
        if cle == 'aucun':
            assert apres[n] == avant[n], n
    assert [len(g) for g in groupes.values()] == [2, 1, 4, 4], groupes   # la référence est dans « aucun »
    d = {n: apres[n]['dette'] - avant[n]['dette'] for n in noms}
    point = sorted(groupes['point'], key=lambda n: d[n])
    pib = {n: (apres[n]['pib'] / avant[n]['pib'] - 1) * 100 for n in noms}
    remuneres = groupes['point'] + groupes['enseignants_et_smic'] + groupes['enseignants']
    inflation = {n: [x - y for x, y in zip(apres[n]['inflation'], avant[n]['inflation'])] for n in remuneres}
    seul = {lev: {n: _publie_cadre(n, {lev})['dette'] - avant[n]['dette'] for n in remuneres
                  if lev in apres[n]['emetteurs']} for lev in ('fonction_publique', 'education', 'smic')}
    smic_retire = [d[n] - (_publie_cadre(n, apres[n]['emetteurs'] - {'smic'})['dette'] - avant[n]['dette'])
                   for n in seul['smic']]
    (ens_smic,) = groupes['enseignants_et_smic']
    methodologie = ' '.join(re.sub(r'\n>\s?', ' ', (RACINE / 'docs' / 'METHODOLOGIE.md')
                                   .read_text(encoding='utf-8')).split())
    for attendu in (
            f"Dette rapportée au PIB en 2032 : {_fr(d[point[0]], 3, True)} et {_fr(d[point[1]], 3, True)} point pour "
            f"les deux qui relèvent le point d'indice (PIB publié 2032 plus haut de {_fr(pib[point[0]], 2)} et "
            f"{_fr(pib[point[1]], 2)} %), {_fr(d[ens_smic], 3, True)} point pour un programme qui revalorise les "
            f"enseignants et relève le SMIC, de {_de_a([d[n] for n in groupes['enseignants']])} point pour les "
            f"quatre autres ; déficit 2032 rapporté au PIB plus faible de "
            f"{_de_a([apres[n]['deficit'] - avant[n]['deficit'] for n in remuneres], signe=False)} point",
            f"inflation du déflateur publiée plus haute de "
            f"{_de_a([sum(v) / len(v) for v in inflation.values()], signe=False)} point par an en moyenne sur "
            f"2028-2032 (jusqu'à {_fr(max(max(v) for v in inflation.values()), 2)} point l'année d'une forte hausse)",
            f"le point d'indice seul abaisse la dette rapportée au PIB de 2032 de "
            f"{' et '.join(_fr(-x, 3) for x in sorted(seul['fonction_publique'].values()))} point ; la "
            f"revalorisation des enseignants seule de {_de_a(seul['education'].values(), signe=False).replace('−', '')}"
            f" point ; la part « agents publics » du SMIC seule de "
            f"{_de_a(seul['smic'].values(), signe=False).replace('−', '')} point",
            f"mesurée en retirant la seule part du SMIC de l'ensemble, elle vaut "
            f"{_de_a(smic_retire, signe=False).replace('−', '')} point"):
        assert attendu in methodologie, attendu
    explication = ' '.join((RACINE / 'docs' / 'EXPLICATION_MODELE_ECONOMIQUE.md').read_text(encoding='utf-8').split())
    for attendu in (
            f"baisse donc d'environ {_de_a([d[n] for n in point], 1, False).replace('−', '')} point pour les deux "
            f"programmes qui relèvent fortement le point d'indice, de "
            f"{_de_a([d[n] for n in groupes['enseignants']], 1, False).replace('−', '')} point pour ceux qui "
            f"revalorisent les enseignants",
            f"(jusqu'à {_fr(max(abs(x) for x in seul['smic'].values()), 1)} point pour un programme)"):
        assert attendu in explication, attendu

