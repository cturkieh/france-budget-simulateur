"""v0.7.0, lot E — atterrissage 2026 injecté, en deux temps.

Contrat (arbitrages du mainteneur du 07/11/2026) : le fichier de DONNÉES
``budget_simulator/data/atterrissage_observe.json`` porte, par année observée,
(a) des réajustements du droit en vigueur (leviers réels, chacun sourcé ; trois
en 2026) et (b) les six cibles, toutes écrites (``null`` = non injectée) :
croissance, déflateur, IPC, chômage (moyenne annuelle), déficit, dette. En mode
cadre, le moteur :

- impose la croissance (choc de demande = cible − croissance du modèle, au point
  d'application des chocs observés v0.6.9) ;
- impose le déflateur s'il est donné, jamais l'IPC ;
- impose l'IPC par le COIN DE PRIX de la consommation (pouvoir d'achat seul),
  calculé pour que la colonne « Inflation IPC % » vaille la cible ;
- impose le chômage après Okun ;
- impose le solde : l'écart (cible − modèle, après réajustements) est ajouté au
  NIVEAU ORGANIQUE des recettes, donc PERSISTANT (rebasage) ;
- impose la dette : ajustement stock-flux, une fois ;
- publie la décomposition (bloc ``cadre.atterrissage``, une clé par grandeur) ;
- refuse ``annee_debut`` ≤ dernière année injectée (422 en strict).

Propriétés (e) et (g) ; mode historique : aucun atterrissage (golden masters).
Référence de comparaison : le droit en vigueur (``DROIT``), toujours présent —
jamais le scénario ``plf_2026``, absent de la CI du dépôt public seul.
"""
import copy
import importlib.util
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import budget_simulator.constants as C
import budget_simulator.engine.cadre as cadre
from budget_simulator import EntreeInvalide
from budget_simulator.simulator import BudgetSimulatorV45

from cadre_harness import CAS, DROIT, NOMS, PROGRAMME_MIXTE, atterrissage, egalite_bit_a_bit, simuler

DEBUT = 2028
REFERENCE = 'droit_en_vigueur'
API_FILE = Path(__file__).resolve().parent.parent / 'api.py'
# Valeurs arrêtées par le mainteneur le 07/11/2026 (sources dans le fichier de données).
CIBLES_2026 = {'croissance': 0.004, 'deflateur': 0.015, 'ipc': 0.023, 'chomage': 0.083,
               'deficit': -0.055, 'dette': 1.194}
REAJUSTEMENTS_2026 = {'defense': {'budget': 58}, 'sante': {'franchise_participation_taux': 120},
                      'is_exceptionnel_tge': {'montant': 6.8}}


def _cibles():
    a = cadre.charger_atterrissage()
    return {g: v.valeur for g, v in a.annees[2026].cibles.items() if v is not None}


def _bloc(rapport):
    return rapport['cadre']['atterrissage']


# ---------------------------------------------------------------------------
# Le fichier de données
# ---------------------------------------------------------------------------

def test_fichier_livre_valeurs_des_decisions_du_07_11():
    a = cadre.charger_atterrissage()
    assert sorted(a.annees) == [2026]
    assert _cibles() == CIBLES_2026
    annee = a.annees[2026]
    assert annee.reajustements == REAJUSTEMENTS_2026        # premier temps : trois leviers réels
    for grandeur in CIBLES_2026:
        c = annee.cibles[grandeur]
        assert c.source.strip() and c.date.strip(), grandeur
    assert annee.cibles['chomage'].provisoire is False       # moyenne annuelle sourcée


@pytest.mark.parametrize('modif, motif', [
    (lambda d: d['annees']['2026']['croissance'].update(valeur=float('nan')), 'croissance'),
    (lambda d: d['annees']['2026']['croissance'].update(valeur=0.4), 'croissance'),   # unité : 40 %
    (lambda d: d['annees']['2026']['chomage'].update(valeur=0.20), 'chomage'),
    (lambda d: d['annees']['2026']['dette'].update(source=''), 'source'),
    (lambda d: d['annees'].update({'2025': d['annees']['2026']}), '2025'),
    (lambda d: d['annees']['2026'].update(ipcc={'valeur': 0.02, 'source': 's', 'date': '2026-01-01'}), 'ipcc'),
    (lambda d: d['annees']['2026'].update(reajustements_droit_en_vigueur={'tva_rate': {'tauxx': 0.2}}), 'tauxx'),
    (lambda d: d['annees']['2026'].update(reajustements_droit_en_vigueur={'education': {'budget': 70}}),
     'education'),
])
def test_fichier_invalide_est_un_defaut_serveur(tmp_path, monkeypatch, modif, motif):
    contenu = json.loads(cadre.ATTERRISSAGE_PATH.read_text(encoding='utf-8'))
    modif(contenu)
    chemin = tmp_path / 'att.json'
    chemin.write_text(json.dumps(contenu), encoding='utf-8')
    monkeypatch.setattr(cadre, 'ATTERRISSAGE_PATH', chemin)
    cadre.vider_caches()
    try:
        with pytest.raises(RuntimeError, match=motif):
            cadre.charger_atterrissage()
    finally:
        cadre.vider_caches()


# ---------------------------------------------------------------------------
# (e) les valeurs 2026 reproduites exactement, identiques pour tous
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def sorties():
    return {REFERENCE: simuler(DROIT, annee_debut=DEBUT),
            **{nom: simuler(CAS[nom], annee_debut=DEBUT) for nom in NOMS}}


@pytest.mark.parametrize('nom', [REFERENCE] + NOMS)
def test_e_valeurs_2026_reproduites_exactement(nom, sorties):
    df, det, rapport, _ = sorties[nom]
    a = df.set_index('Année').loc[2026]
    assert a['Croissance %'] == pytest.approx(0.4, abs=1e-12)
    assert a['Inflation %'] == pytest.approx(1.5, abs=1e-12)        # déflateur injecté
    assert a['Inflation IPC %'] == pytest.approx(2.3, abs=1e-12)
    assert a['Chômage %'] == pytest.approx(8.3, abs=1e-12)
    assert a['Déficit/PIB %'] == pytest.approx(-5.5, abs=1e-12)
    assert a['Dette/PIB %'] == pytest.approx(119.4, abs=1e-12)


def test_e_identiques_pour_tous_et_decomposition_publiee(sorties):
    blocs = {nom: _bloc(sortie[2]) for nom, sortie in sorties.items()}
    reference = blocs[REFERENCE]
    assert len(blocs) >= 2 and all(b == reference for b in blocs.values())
    d = reference['annees']['2026']['decomposition']
    assert tuple(d) == cadre.GRANDEURS_ATTERRISSAGE      # une clé par grandeur, le solde sous 'deficit'
    assert d['croissance']['observe_pct'] == pytest.approx(0.4)
    assert d['croissance']['choc_pt'] == pytest.approx(0.4 - d['croissance']['modele_pct'])
    assert d['deflateur']['observe_pct'] == pytest.approx(1.5)
    assert d['deflateur']['ecart_pt'] == pytest.approx(1.5 - d['deflateur']['modele_pct'], abs=1e-4)
    # coin = IPC rapporté au déflateur INJECTÉ (valeurs publiées arrondies à 4 décimales)
    assert d['ipc']['deflateur_pct'] == pytest.approx(1.5)
    assert d['ipc']['coin_pt'] == pytest.approx((1.023 / 1.015 - 1) * 100, abs=2e-4)
    assert d['deficit']['ecart_md_eur'] == pytest.approx(d['deficit']['reajustements_md_eur']
                                                       + d['deficit']['residuel_md_eur'], abs=2e-3)
    assert d['dette']['observe_pct'] == pytest.approx(119.4)
    assert reference['annees']['2026']['cibles']['deficit']['source']


def test_e_reajustements_premier_temps_mesures_levier_par_levier(sorties):
    """Premier temps : effet des trois réajustements sur le solde 2026, mesuré à
    l'état de l'année. Défense +1 Md€ de dépense ; surtaxe IS −0,5 Md€ de
    recettes ; franchises 120 % : 0,4 × (1 − 0,10) × 0,93 = 0,3348 Md€ de moindre
    dépense (handler santé). Le résidu forcé est mesuré APRÈS eux."""
    d = _bloc(sorties[REFERENCE][2])['annees']['2026']['decomposition']
    assert d['deficit']['reajustements_md_eur'] == pytest.approx(-1.0 - 0.5 + 0.4 * 0.9 * 0.93, abs=2e-3)
    assert d['croissance']['choc_pt'] == pytest.approx(0.4 - d['croissance']['modele_pct'], abs=1e-4)


def test_e_ecart_de_solde_persistant():
    """L'écart est rebasé dans le niveau organique des recettes : en 2027 (droit
    constant), le déficit n'y rebondit pas. Contre-épreuve : sans le rebasage
    persistant (écart ponctuel), 2027 serait plus dégradé d'environ 0,4 pt."""
    df = simuler(DROIT, annee_debut=DEBUT)[0].set_index('Année')
    assert df.at[2027, 'Déficit/PIB %'] > -5.75
    d = _bloc(simuler(DROIT, annee_debut=DEBUT)[2])['annees']['2026']['decomposition']
    assert d['deficit']['ecart_md_eur'] > 0


def test_e_jamais_d_ipc_dans_le_deflateur(sorties):
    """L'IPC passe par le coin : le déflateur publié (« Inflation % ») est le
    déflateur INJECTÉ (1,5 %), jamais l'IPC (2,3 %) ; sans déflateur injecté, il
    reste celui du modèle."""
    df = sorties[REFERENCE][0].set_index('Année')
    assert df.at[2026, 'Inflation %'] == pytest.approx(1.5, abs=1e-12)
    assert df.at[2026, 'Inflation IPC %'] == pytest.approx(2.3, abs=1e-12)
    sans_deflateur = {g: v for g, v in CIBLES_2026.items() if g != 'deflateur'}
    with atterrissage({2026: sans_deflateur}):
        modele = simuler(DROIT, annee_debut=DEBUT)[0].set_index('Année')
    with atterrissage({}):
        vide = simuler(DROIT, annee_debut=DEBUT)[0].set_index('Année')
    assert modele.at[2026, 'Inflation %'] == vide.at[2026, 'Inflation %']
    assert modele.at[2026, 'Inflation IPC %'] == pytest.approx(2.3, abs=1e-12)


def test_e_422_si_annee_debut_dans_l_atterrissage():
    with pytest.raises(EntreeInvalide, match='atterrissage'):
        with atterrissage({2026: CIBLES_2026, 2027: {'croissance': 0.01}}):
            simuler({}, strict=True, annee_debut=2027)
    with atterrissage({2026: CIBLES_2026, 2027: {'croissance': 0.01}}):
        rapport = simuler({}, annee_debut=2027)[2]
    assert rapport['cadre']['annee_debut'] == 2028 and rapport['valid'] is False


def test_e_historique_sans_atterrissage():
    """Mode historique (annee_debut absent ou 2026) : aucun atterrissage, sortie
    de v0.6.11 — même avec le fichier rempli (golden master v1 inchangé)."""
    rapport = simuler(PROGRAMME_MIXTE)[2]
    assert rapport['cadre']['atterrissage'] is None
    df = simuler(DROIT)[0].set_index('Année')
    assert df.at[2026, 'Croissance %'] != pytest.approx(0.4, abs=1e-3)


# ---------------------------------------------------------------------------
# (g) tables vides : statu quo du cadre au bit du statu quo historique
# ---------------------------------------------------------------------------

def test_g_tables_vides_statu_quo_au_bit():
    with atterrissage({}):
        egalite_bit_a_bit(simuler(DROIT), simuler(DROIT, annee_debut=DEBUT))


# ---------------------------------------------------------------------------
# Mécanismes un par un (données injectées)
# ---------------------------------------------------------------------------

def test_deflateur_source_impose_si_donne():
    with atterrissage({2026: {**CIBLES_2026, 'deflateur': 0.015}}):
        df, _, rapport, _ = simuler(DROIT, annee_debut=DEBUT)
    a = df.set_index('Année').loc[2026]
    assert a['Inflation %'] == pytest.approx(1.5, abs=1e-12)
    assert a['Inflation IPC %'] == pytest.approx(2.3, abs=1e-12)
    d = _bloc(rapport)['annees']['2026']['decomposition']
    assert d['deflateur']['observe_pct'] == pytest.approx(1.5)
    assert d['ipc']['deflateur_pct'] == pytest.approx(1.5)


def test_reajustements_du_droit_en_vigueur_deux_temps():
    """Premier temps : un levier réel réajusté (défense 57 → 58) entre dans le
    droit en vigueur à partir de 2026 et le suit (droit constant 2027) ; un
    programme qui ne touche pas au levier en hérite ; le RÉSIDU est mesuré après
    lui. Second temps : le résidu forcé. Les cibles restent exactes."""
    with atterrissage({2026: CIBLES_2026}, reajustements={2026: {'defense': {'budget': 58}}}):
        df, _, rapport, sim = simuler(DROIT, annee_debut=DEBUT)
        _, _, rapport_def, _ = simuler(dict(copy.deepcopy(DROIT), defense={'budget': 45}),
                                       annee_debut=DEBUT)
    imp = {y['Année']: y for y in rapport['measure_impacts_by_year']}
    assert all(imp[an]['defense']['depenses'] == 58 - 50 for an in range(2026, 2036))
    d = _bloc(rapport)['annees']['2026']['decomposition']
    assert d['deficit']['reajustements_md_eur'] == pytest.approx(-1.0, abs=1e-9)
    assert d['deficit']['ecart_md_eur'] == pytest.approx(d['deficit']['reajustements_md_eur']
                                                       + d['deficit']['residuel_md_eur'])
    assert df.set_index('Année').at[2026, 'Déficit/PIB %'] == pytest.approx(-5.5, abs=1e-12)
    assert 'defense' not in rapport['cadre']['leviers_modifies']
    # Un programme qui fixe la défense à 45 : son niveau prime à partir du début
    # (droit réajusté avant ; le réajustement ne s'ajoute pas au niveau encodé).
    imp_def = {y['Année']: y for y in rapport_def['measure_impacts_by_year']}
    assert imp_def[2027]['defense']['depenses'] == 58 - 50
    assert imp_def[DEBUT]['defense']['depenses'] == 45 - 50
    assert 'defense' in rapport_def['cadre']['leviers_modifies']


def test_collision_avec_les_tables_v069_defaut_serveur(monkeypatch):
    monkeypatch.setattr(C, 'CHOCS_DEMANDE_OBSERVES', {2026: -0.005})
    with pytest.raises(RuntimeError, match='CHOCS_DEMANDE_OBSERVES'):
        simuler({}, annee_debut=DEBUT)


def test_choc_hors_domaine_du_mecanisme_defaut_serveur():
    """Une cible trop loin du modèle (choc > 3 points) : défaut des données
    serveur, 500 — jamais un écrêtage silencieux."""
    with atterrissage({2026: {**CIBLES_2026, 'croissance': -0.04}}):
        with pytest.raises(RuntimeError, match='croissance'):
            simuler({}, annee_debut=DEBUT)


def test_colonne_ipc_en_mode_historique_egale_au_deflateur_sans_tva():
    df = simuler(DROIT)[0]
    assert (df['Inflation IPC %'] - df['Inflation %']).abs().max() < 1e-9


def test_colonne_ipc_porte_le_coin_fiscal_de_la_tva():
    """Hausse de TVA : le prix de la consommation saute l'année d'entrée, l'IPC
    s'écarte du déflateur ; jamais l'inverse (le déflateur n'est pas touché)."""
    df = simuler({'tva_rate': {'taux': 0.22}})[0].set_index('Année')
    assert df.at[2026, 'Inflation IPC %'] > df.at[2026, 'Inflation %'] + 0.5


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def client():
    spec = importlib.util.spec_from_file_location('api_att_v070', API_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return TestClient(module.app, raise_server_exceptions=False)


def test_api_bloc_atterrissage_et_colonne_ipc(client, monkeypatch):
    monkeypatch.setenv('BUDGETLAB_STRICT', '')
    corps = client.post('/simulate', json={'mesures': {}, 'annee_debut': DEBUT}).json()
    att = corps['cadre']['atterrissage']
    assert att['annees']['2026']['cibles']['croissance']['valeur'] == 0.004
    assert att['annees']['2026']['reajustements_droit_en_vigueur'] == REAJUSTEMENTS_2026
    assert set(att['annees']['2026']['sources_reajustements']) == {
        'defense.budget', 'sante.franchise_participation_taux', 'is_exceptionnel_tge.montant'}
    assert corps['results'][1]['Inflation IPC %'] == 2.3
    assert corps['results'][1]['Inflation %'] == 1.5
    assert corps['results'][1]['Croissance %'] == 0.4
    assert corps['report']['valid'] is True


def test_api_annee_debut_2026_reste_le_mode_historique(client, monkeypatch):
    """2026 = mode historique (programme dès 2026, sans atterrissage) : jamais en
    conflit avec l'année injectée, même en strict."""
    monkeypatch.setenv('BUDGETLAB_STRICT', '1')
    r = client.post('/simulate', json={'mesures': {}, 'annee_debut': 2026})
    assert r.status_code == 200 and r.json()['cadre']['mode'] == 'historique'


# ---------------------------------------------------------------------------
# Propriétés de la baseline en mode cadre (test_baseline_properties.py adapté)
# ---------------------------------------------------------------------------

def test_baseline_cadre_elasticite_unitaire_hors_annee_rebasee():
    """(c) de test_baseline_properties, en mode cadre : élasticité 1,00 ± 0,02
    chaque année SAUF 2026, l'année rebasée (l'écart de solde y entre dans le
    niveau des recettes)."""
    df, det, _, _ = simuler(DROIT, annee_debut=DEBUT)
    rec = [float(C.RECETTES_BASE_MD_EUR)] + [float(det.iloc[i]['Recettes_Totales']) for i in range(1, 11)]
    pib = [float(df.iloc[i]['PIB']) for i in range(0, 11)]
    for i in range(2, 11):
        e = (rec[i] / rec[i - 1] - 1) / (pib[i] / pib[i - 1] - 1)
        assert 0.98 <= e <= 1.02, (2025 + i, e)


# ---------------------------------------------------------------------------
# RÉFUTEUR du lot E
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('debut', [2027, 2030, 2032])
def test_refuteur_e_atterrissage_independant_du_debut_et_du_programme(debut, sorties):
    """2026 est le droit en vigueur pour tout début ≥ 2027 : la décomposition et
    les valeurs injectées ne dépendent ni du début ni du programme."""
    df, _, rapport, _ = simuler(PROGRAMME_MIXTE, annee_debut=debut)
    assert _bloc(rapport) == _bloc(sorties[REFERENCE][2])
    a = df.set_index('Année').loc[2026]
    assert (a['Croissance %'], a['Chômage %']) == pytest.approx((0.4, 8.3), abs=1e-12)


def test_refuteur_e_ecart_jamais_compte_comme_une_impulsion():
    """Le résidu forcé est un rebasage, pas une mesure : il n'entre ni dans
    l'effort budgétaire ni dans les impulsions (multiplicateurs). Compté comme
    une mesure, il porterait l'effort 2026 d'environ +0,28 point de PIB
    (8,5 Md€) ; l'effort publié ne bouge que par le dénominateur et l'état
    macro (< 0,01). Les réajustements, eux, SONT des mesures : présents des
    deux côtés de la comparaison."""
    _, det_avec, rapport, _ = simuler(DROIT, annee_debut=DEBUT)
    # Même droit réajusté (les réajustements SONT des mesures), sans cible.
    with atterrissage({2026: {}}, reajustements={2026: REAJUSTEMENTS_2026}):
        _, det_sans, _, _ = simuler(DROIT, annee_debut=DEBUT)
    a, b = det_avec.set_index('Année'), det_sans.set_index('Année')
    residu = _bloc(rapport)['annees']['2026']['decomposition']['deficit']['residuel_md_eur']
    assert residu / a.at[2026, 'PIB_Réel_Base2025'] * 100 > 0.1   # 10 fois la tolérance
    assert abs(a.at[2026, 'Effort_Budgétaire %'] - b.at[2026, 'Effort_Budgétaire %']) < 0.01


# ---------------------------------------------------------------------------
# Plafond de 10 % du PIB : inchangé, l'avis exposé
# ---------------------------------------------------------------------------

def test_plafond_total_expose_sans_changer_le_calcul():
    """Le plafond (écarts au DÉFAUT du moteur) n'est pas touché par la passe ; ses
    années de morsure sont exposées pour la fiche d'un programme concerné. Le
    texte d'avis existant reste dans report.warnings."""
    programme = CAS.get('lfi_2027', PROGRAMME_MIXTE)
    rapport = simuler(programme, annee_debut=DEBUT)[2]
    p = rapport['cadre']['plafond_total']
    assert p['seuil_pct_pib'] == 10 and p['reference'] == 'defauts_du_moteur'
    assert p['annees'] == sorted(p['annees'])
    assert all(an >= DEBUT for an in p['annees'])
    if p['annees']:
        assert any('plafonné à 10 % du PIB' in w and f"dès {p['annees'][0]}" in w
                   for w in rapport['warnings'])
    assert simuler(DROIT, annee_debut=DEBUT)[2]['cadre']['plafond_total']['annees'] == []


# ---------------------------------------------------------------------------
# Garde : les chiffres publiés dans METHODOLOGIE § Cadre temporel reproduisent
# ---------------------------------------------------------------------------

def test_methodologie_publie_la_decomposition_mesuree():
    """Même règle que test_chiffres_publies_v061 : chaque grandeur mesurée citée
    dans la section « Cadre temporel 2027-2032 » est recalculée ici et cherchée
    telle quelle (format du document) — un chiffre qui cesse de reproduire fait
    rougir la CI."""
    texte = (Path(__file__).resolve().parent.parent / 'docs' / 'METHODOLOGIE.md').read_text(encoding='utf-8')
    debut = texte.index('## Cadre temporel 2027-2032 (v0.7.0)')
    section = texte[debut:texte.index('## Hypotheses Demographiques', debut)]
    df, _, rapport, _ = simuler(DROIT, annee_debut=DEBUT)
    d = _bloc(rapport)['annees']['2026']['decomposition']
    a = df.set_index('Année')

    def fr(x, n):
        return f"{x:.{n}f}".replace('.', ',').replace('-', '−')

    attendus = [
        f"| Croissance | {fr(d['croissance']['modele_pct'], 2)} % | {fr(d['croissance']['observe_pct'], 1)} % | "
        f"choc de {fr(d['croissance']['choc_pt'], 2)} point |",
        f"| Déflateur du PIB | {fr(d['deflateur']['modele_pct'], 2)} % | {fr(d['deflateur']['observe_pct'], 1)} % | "
        f"+{fr(d['deflateur']['ecart_pt'], 2)} point |",
        f"| IPC | déflateur injecté {fr(d['ipc']['deflateur_pct'], 1)} % | {fr(d['ipc']['observe_pct'], 1)} % | "
        f"coin de +{fr(d['ipc']['coin_pt'], 2)} point |",
        f"| Chômage | {fr(d['chomage']['modele_pct'], 2)} % | {fr(d['chomage']['observe_pct'], 1)} % | "
        f"+{fr(d['chomage']['ecart_pt'], 2)} point |",
        f"| Solde | {fr(d['deficit']['modele_pct'], 2)} % du PIB | {fr(d['deficit']['observe_pct'], 1)} % | "
        f"réajustements {fr(d['deficit']['reajustements_md_eur'], 1)} Md€, puis résidu "
        f"+{fr(d['deficit']['residuel_md_eur'], 1)} Md€ de recettes |",
        f"| Dette | {fr(d['dette']['modele_pct'], 2)} % du PIB | {fr(d['dette']['observe_pct'], 1)} % | "
        f"ajustement stock-flux de +{fr(d['dette']['ajustement_stock_flux_md_eur'], 1)} Md€ |",
        f"**déficit de\n{fr(a.at[2027, 'Déficit/PIB %'], 2)} %**",
        f"**dette de {fr(a.at[2027, 'Dette/PIB %'], 2)} %**",
        f"La croissance 2027, {fr(a.at[2027, 'Croissance %'], 2)} %",
    ]
    for attendu in attendus:
        assert attendu in section, attendu


def test_reajustements_herites_parametre_par_parametre():
    """Un programme qui modifie UN paramètre d'un levier réajusté garde le
    réajustement sur les paramètres qu'il reprend du budget voté : modifier la
    prévention ne remet pas les franchises à 100. Un paramètre que le programme
    change garde sa valeur (niveau encodé du programme)."""
    sante_vote = dict(DROIT['sante'])
    reaj = {2026: {'sante': {'franchise_participation_taux': 120}}}
    with atterrissage({2026: CIBLES_2026}, reajustements=reaj):
        autre_param = cadre.CadreTemporel.preparer(
            {'sante': dict(sante_vote, effort_prev_org=20)}, DEBUT)
        franchise_touchee = cadre.CadreTemporel.preparer(
            {'sante': dict(sante_vote, franchise_participation_taux=0)}, DEBUT)
        identique = cadre.CadreTemporel.preparer({'sante': dict(sante_vote)}, DEBUT)
    m = autre_param.mesures_de_l_annee(DEBUT)['sante']
    assert m['franchise_participation_taux'] == 120 and m['effort_prev_org'] == 20
    assert franchise_touchee.mesures_de_l_annee(DEBUT)['sante']['franchise_participation_taux'] == 0
    assert identique.mesures_de_l_annee(DEBUT)['sante']['franchise_participation_taux'] == 120
    assert 'sante' not in identique.leviers_modifies
    assert all(c.mesures_de_l_annee(2027)['sante']['franchise_participation_taux'] == 120
               for c in (autre_param, franchise_touchee, identique))


def test_chaque_reajustement_livre_porte_sa_source():
    a = cadre.charger_atterrissage()
    for an, bloc in a.annees.items():
        for levier, params in bloc.reajustements.items():
            for param in params:
                assert bloc.sources_reajustements.get(f'{levier}.{param}', '').strip(), (an, levier, param)
