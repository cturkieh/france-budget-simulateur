"""Multiplicateurs « centraux » mesurés dans le MOTEUR COMPLET (v0.6.7, arbitrage du
mainteneur du 07/10/2026).

Chaque famille est calée sur la valeur centrale de la littérature (constants.py,
MULT_CIBLE_NIVEAU_4ANS : FMI WEO oct. 2014 ch. 3, Gechert 2015, Ramey 2019), en
EFFET DE NIVEAU sur le PIB réel 4 ans après le début d'une impulsion permanente de
1 % du PIB — mesuré avec tout le moteur (rappel vers le potentiel, Phillips, Okun,
dette), pas en k × Σ profil analytique. Garde-fou : le choc d'investissement de
calibrage (1 % du PIB permanent, levier éducation, statu quo) ne s'autofinance pas
dans ce banc, ni en multiplicateur cumulé × taux de prélèvements, ni en solde
public mesuré. Portée : CE choc, pas tout investissement, toute intensité ou tout
état macroéconomique (contre-audit externe V2-06, METHODOLOGIE § Multiplicateurs).
"""
from pathlib import Path

import pytest

from budget_simulator import constants
from budget_simulator.constants import (CHEMIN_CIBLE_INVESTISSEMENT, MULT_CIBLE_NIVEAU_4ANS,
                                        TAUX_PRELEVEMENTS_AUTOFINANCEMENT)
from budget_simulator.simulator import BudgetSimulatorV45

# famille → (levier synthétique, flux, signe) : dépense + = expansion, recette + = hausse
FAMILLES = {
    'investissement': ('education', 'depenses', +1),
    'transferts': ('retraites', 'depenses', +1),
    'hausse_impots': ('tva_rate', 'recettes', +1),
    'baisse_impots': ('tva_rate', 'recettes', -1),
    'coupe_depenses': ('collectivites', 'depenses', -1),
    # Lot 5 : la hausse de la même dépense courante, même cible et même tolérance que la coupe
    # (symétrie par instrument, tests/test_symetrie_depense_courante.py).
    'hausse_depenses': ('collectivites', 'depenses', +1),
}


def _simuler(famille=None, periods=12):
    levier, flux, signe = FAMILLES[famille] if famille else (None, None, 0)

    class _Impulsion(BudgetSimulatorV45):
        def apply_measures(self, year, spending, revenues, gdp, inflation, unemployment):
            sp, rv, imp = super().apply_measures(year, spending, revenues, gdp, inflation, unemployment)
            if levier:
                x = 0.01 * gdp * signe
                imp = dict(imp)
                imp[levier] = {'depenses': x if flux == 'depenses' else 0.0,
                               'recettes': x if flux == 'recettes' else 0.0}
                if flux == 'depenses':
                    sp += x
                else:
                    rv += x
            return sp, rv, imp

    return _Impulsion(periods=periods, mesures={}).simulate()


@pytest.fixture(scope='module')
def mesures(request):
    import budget_simulator.engine.orchestrator as orch
    mp = pytest.MonkeyPatch()
    mp.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
    try:
        base = _simuler()
        return base, {f: _simuler(f) for f in FAMILLES}
    finally:
        mp.undo()


def _niveaux(base, cas):
    yb, yr = base[1]['PIB_Réel_Base2025'], cas[1]['PIB_Réel_Base2025']
    # impulsion au budget 2026 (index 1), qui agit dès 2026 depuis le lot 6 (jusque-là, dès 2027 :
    # lag d'un an) : horizon H = index − 1, H0 = année du choc, H4 = 2030 (« quatre ans après »)
    return [abs(yr[i] - yb[i]) / yb[i] * 100 for i in range(len(yr))]


# Lot 6 (paramètres, arbitrage du mainteneur : le profil suit le tableau du FMI, source citée) : la cible de la
# famille investissement porte sur le TOTAL (demande et canal d'offre) d'un levier de capital public,
# sur tout le chemin H0-H4 (test_chemin_de_l_investissement_sur_le_tableau_du_fmi, plus bas) ; le
# niveau de la demande seule (levier éducation de ce banc, 1,28 à 4 ans) n'est plus comparé à 1,5.
@pytest.mark.parametrize('famille', [f for f in FAMILLES if f != 'investissement'])
def test_niveau_a_4_ans_sur_la_valeur_centrale(mesures, famille):
    base, cas = mesures
    niveau_4 = _niveaux(base, cas[famille])[5]
    cible = MULT_CIBLE_NIVEAU_4ANS[famille]
    # Investissement : non retouché (1,41 vs 1,5). Transferts : recalés au lot 1 (release de
    # paramètres, 15/11/2026) une fois l'éviction retirée — le coefficient 0,71 compensait
    # l'éviction d'une relance 100 % transferts (0,672 sans elle, +3,4 %) : tolérance resserrée à
    # 1 %, comme la symétrie coupe/hausse (tests/test_symetrie_transferts_v067.py).
    # Lot 6 (calendrier de l'impulsion, release de paramètres) : coefficients recalés pour retrouver
    # le niveau d'avant le lot (la trajectoire n'est plus décalée d'un an) ; cibles et tolérances
    # inchangées (investissement 1,41, toujours −6 % de sa cible).
    tolerance = {'investissement': 0.10, 'transferts': 0.01}.get(famille, 0.05)
    assert niveau_4 == pytest.approx(cible, rel=tolerance), (
        f'{famille} : niveau à 4 ans {niveau_4:.3f} vs cible centrale {cible}')


def test_choc_investissement_de_calibrage_ne_s_autofinance_pas_dans_le_banc(mesures):
    """Portée : le choc de calibrage de ce fichier (1 % du PIB permanent sur le
    levier éducation, statu quo, 2026-2036), pas tout investissement.

    Trois notions distinctes (contre-audit externe V2-06) :
    - autofinancement BUDGÉTAIRE, deux mesures distinctes : (a) part du coût
      brut récupérée par le SOLDE public (intérêts compris), solde NET des
      recettes induites et des dépenses induites hors impulsion (indexation,
      intérêts) — mesurée 0,13 en v0.6.10, 0,08 depuis le lot 1 (terme d'effort
      de l'inflation retiré) ; (b) en volume, sans prix ni intérêts :
      multiplicateur cumulé (Ramey, ΣΔY/ΣΔG sur 10 ans) × taux de
      prélèvements < 1 ;
    - dette NOMINALE : plus haute que le statu quo en fin d'horizon ;
    - ratio dette/PIB : non vérifié année par année (un PIB NOMINAL plus haut
      peut le faire passer sous le statu quo sans rembourser le coût : c'était
      le cas jusqu'à v0.8.1, −0,05 pt en 2030, quand le terme d'effort de
      l'inflation gonflait les prix d'une relance) ; seule sa
      valeur de fin d'horizon est bornée ici. Les chiffres publiés sont liés à
      la mesure par test_chiffres_publies_du_banc_lies_a_la_mesure."""
    base, cas = mesures
    n = _niveaux(base, cas['investissement'])
    cumule_10 = sum(n[2:12]) / 10
    assert cumule_10 * TAUX_PRELEVEMENTS_AUTOFINANCEMENT < 1
    df0, df = base[0], cas['investissement'][0]
    cout = sum(0.01 * df['PIB'][i] for i in range(1, 12))
    degradation = sum(df0['Déficit'][i] - df['Déficit'][i] for i in range(1, 12))
    assert degradation > 0.5 * cout   # l'essentiel du coût reste à la charge des finances publiques
    assert df['Dette'][11] > df0['Dette'][11]                   # dette nominale 2036
    assert df['Dette/PIB %'][11] > df0['Dette/PIB %'][11]       # ratio 2036


METHODO = Path(__file__).resolve().parent.parent / 'docs' / 'METHODOLOGIE.md'


def _fr(x, decimales=0, signe=False):
    """Format de la doc : virgule décimale, signe moins typographique (U+2212)."""
    s = f'{x:+.{decimales}f}' if signe else f'{x:.{decimales}f}'
    return s.replace('-', '\u2212').replace('.', ',')


def _banc_autofinancement(base, cas):
    """Les grandeurs que METHODOLOGIE publie sur le banc d'autofinancement
    (choc de calibrage, 2026-2036 = index 1 à 11)."""
    (df0, ann0, _), (df, ann, _) = base, cas
    periode = range(1, 12)
    n = _niveaux(base, cas)
    cout = sum(0.01 * df['PIB'][i] for i in periode)   # = impulsion injectée (0,01 × PIB de l'année)
    d_rec = sum(ann['Recettes_Totales'][i] - ann0['Recettes_Totales'][i] for i in periode)
    d_dep = sum(ann['Dépenses_Totales'][i] - ann0['Dépenses_Totales'][i] for i in periode)
    d_int = sum(ann['Intérêts_Dette'][i] - ann0['Intérêts_Dette'][i] for i in periode)
    degradation = sum(df0['Déficit'][i] - df['Déficit'][i] for i in periode)
    return {
        'cout': cout, 'd_recettes': d_rec, 'd_depenses_hors_impulsion': d_dep - cout,
        'd_interets': d_int, 'degradation': degradation, 'part_rendue': 1 - degradation / cout,
        'volume': sum(n[2:12]) / 10 * TAUX_PRELEVEMENTS_AUTOFINANCEMENT,
        'niveau_4': n[5], 'niveau_10': n[11], 'nominal_2030': (df['PIB'][5] / df0['PIB'][5] - 1) * 100,
        'dette': {i: df['Dette'][i] - df0['Dette'][i] for i in periode},
        'ratio': {i: df['Dette/PIB %'][i] - df0['Dette/PIB %'][i] for i in periode},
    }


def test_chiffres_publies_du_banc_lies_a_la_mesure(mesures):
    """Reprise après réfutation (V2-06) : chaque chiffre que METHODOLOGIE publie
    sur le banc d'autofinancement est RECALCULÉ ici et doit figurer tel quel dans
    la doc. Une dérive du moteur casse la doc au lieu de la laisser se périmer —
    c'est ainsi qu'un « 11 % » mesuré avant la fin des lots v0.6.7 a survécu.
    L'identité comptable (dégradation = Δdépenses + Δintérêts − Δrecettes)
    garantit que la décomposition publiée explique bien le solde."""
    base, cas = mesures
    m = _banc_autofinancement(base, cas['investissement'])
    d_dep_total = m['d_depenses_hors_impulsion'] + m['d_interets']
    assert m['degradation'] == pytest.approx(m['cout'] + d_dep_total - m['d_recettes'], abs=0.5)
    attendus = {
        'part rendue': f"ne récupère que {_fr(100 * m['part_rendue'])} % du coût brut ({_fr(m['cout'])} Md EUR",
        'recettes induites': f"recettes induites (+{_fr(m['d_recettes'])} Md EUR",
        'dépenses induites': (f"(+{_fr(d_dep_total)} Md EUR : dépenses indexées sur les prix "
                              f"+{_fr(m['d_depenses_hors_impulsion'])}, intérêts +{_fr(m['d_interets'])})"),
        'volume': f"× {_fr(TAUX_PRELEVEMENTS_AUTOFINANCEMENT, 2)} = {_fr(m['volume'], 2)} < 1",
        'dette nominale': f"+{_fr(m['dette'][5])} Md EUR en 2030, +{_fr(m['dette'][11])} Md EUR en 2036",
        'PIB nominal 2030': f"{_fr(m['nominal_2030'], 2, True)} % en 2030 pour {_fr(m['niveau_4'], 2, True)} % en volume",
        'ratio 2030-2031': (f"en 2030 ({_fr(m['ratio'][5], 2, True)} pt) "
                            f"et 2031 ({_fr(m['ratio'][6], 2, True)} pt)"),
        'ratio 2035': f"({_fr(m['ratio'][10], 1, True)} pt en 2035)",
        'niveau 4 ans': f"effet de niveau de {_fr(m['niveau_4'], 2)} % du PIB à 4 ans",
        'niveau 10 ans': f"et de {_fr(m['niveau_10'], 2)} % à 10 ans",
    }
    texte = ' '.join(METHODO.read_text(encoding='utf-8').split())
    manquants = [f'{nom} : « {chaine} »' for nom, chaine in attendus.items() if chaine not in texte]
    assert not manquants, ('METHODOLOGIE ne publie plus la mesure du banc (moteur ou doc à '
                           'réaligner) :\n' + '\n'.join(manquants))


# Dernière colonne du tableau « Recalibrage central des familles » de METHODOLOGIE
# (lot 1, 15/11/2026) : l'état du moteur, recalculé ici.
LIGNES_DU_TABLEAU = {
    'investissement': '| Investissement public (INVEST) |',
    'coupe_depenses': '| Coupe de dépenses générique (TAXES) |',
    'hausse_depenses': '| Hausse de dépense courante (TAXES) |',
    'transferts': '| Transferts (TRANSFERS) |',
    'hausse_impots': "| Hausse d'impôts (TAXES) |",
    'baisse_impots': "| Baisse d'impôts (TAXES) |",
}
COEFFICIENT_DE_LA_FAMILLE = {
    'investissement': 'MULT_INVESTISSEMENT', 'coupe_depenses': 'MULT_COUPE_DEPENSES',
    'hausse_depenses': 'MULT_COUPE_DEPENSES',   # lot 5 : même coefficient que la coupe
    'transferts': 'MULT_TRANSFERTS', 'hausse_impots': 'MULT_HAUSSE_IMPOTS',
    'baisse_impots': 'MULT_BAISSE_IMPOTS',
}


def cellule_moteur_actuel(base, cas, famille):
    """« 4 ans (k) ; 10 ans niveau / cumulé 10 ans (Ramey) », au format du document."""
    n = _niveaux(base, cas)
    k = f'{getattr(constants, COEFFICIENT_DE_LA_FAMILLE[famille]):g}'.replace('.', ',')
    return f"{_fr(n[5], 2)} (k = {k}) ; {_fr(n[11], 2)} / {_fr(sum(n[2:12]) / 10, 2)}"


def test_tableau_des_familles_lie_a_la_mesure(mesures):
    """Lot 1 (15/11/2026) : la colonne « Moteur actuel » du tableau des familles est
    recalculée sur ce banc et doit figurer telle quelle. Les colonnes « Moteur après »
    et « 10 ans » datent de la v0.6.7 ; la colonne « 10 ans » était restée à l'état
    de la v0.8.1 quand le paragraphe au-dessus, lié à la mesure, avait changé."""
    base, cas = mesures
    lignes = METHODO.read_text(encoding='utf-8').splitlines()
    ecarts = {}
    for famille, debut in LIGNES_DU_TABLEAU.items():
        ligne = next(l for l in lignes if l.startswith(debut))
        publie = ligne.rstrip().rstrip('|').rsplit('|', 1)[-1].strip()
        attendu = cellule_moteur_actuel(base, cas[famille], famille)
        if publie != attendu:
            ecarts[famille] = (publie, attendu)
    assert not ecarts, ecarts


def test_le_statu_quo_ne_depend_pas_des_multiplicateurs():
    """Sans aucune impulsion, la table des multiplicateurs n'est jamais lue : le
    recalibrage laisse le statu quo identique au bit."""
    from budget_simulator.simulator import FiscalMultipliers
    a = BudgetSimulatorV45(periods=10, mesures={}).simulate()[0]
    sim = BudgetSimulatorV45(periods=10, mesures={})

    class _Interdit(FiscalMultipliers):
        def get_multiplier(self, *args, **kwargs):
            raise AssertionError('multiplicateur lu au statu quo')

    sim.multipliers = _Interdit()
    b = sim.simulate()[0]
    assert a.equals(b)


# --- Lot 6, paramètres : le chemin de l'investissement calé sur le tableau du FMI ---------------------
# Protocole (METHODOLOGIE, « Calendrier de l'impulsion ») : mode historique, choc permanent de 1 % du
# PIB par an dès 2026 ; levier de référence à canal d'offre actif = transition écologique : impulsion
# de demande injectée sur le levier (son impact propre remplacé), canal d'offre alimenté par son
# paramètre « investissement », constant, égal à 1 % du PIB nominal 2026.
PRECISION_DU_TABLEAU = 0.0005   # demi-unité de la 3e décimale publiée par le FMI


def _chemin(levier, s=1.0, mode='historique', offre=True, flux='depenses', canal=None, annee_offre=None):
    """Niveau du PIB réel en % de la référence, par point de PIB de choc, H0 à H9. ``annee_offre`` :
    année dont le PIB nominal fixe l'entrée (constante) du canal d'offre ; par défaut, celle du choc."""
    import budget_simulator.engine.orchestrator as orch
    from budget_simulator.constants import PARAM_DOMAINS
    debut, ad = (2028, 2028) if mode == 'cadre' else (2026, None)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(orch, 'round', lambda x, n=None: float(x), raising=False)
        base = BudgetSimulatorV45(periods=12, mesures={}, annee_debut=ad).simulate()[1].set_index('Année')
        mesures = {}
        if offre and canal:
            param, defaut = canal
            a_offre = annee_offre or debut
            pib = float(base.at[a_offre, 'PIB_Réel_Base2025'] * base.at[a_offre, 'Déflateur'])
            valeur = min(defaut + s / 100 * pib, PARAM_DOMAINS[levier][param][1])
            mesures = {levier: {param: valeur}}

        class _Choc(BudgetSimulatorV45):
            def apply_measures(self, year, spending, revenues, gdp, inflation, unemployment):
                sp, rv, imp = super().apply_measures(year, spending, revenues, gdp, inflation, unemployment)
                if year < debut:
                    return sp, rv, imp
                imp = dict(imp)
                propre = imp.get(levier) if isinstance(imp.get(levier), dict) else {}
                sp -= float(propre.get('depenses', 0) or 0)
                rv -= float(propre.get('recettes', 0) or 0)
                x = s / 100 * gdp
                imp[levier] = {'depenses': x, 'recettes': 0.0}
                if flux == 'investissement':
                    imp[levier]['depenses_investissement'] = x
                return sp + x, rv, imp
        cas = _Choc(periods=12, mesures=mesures, annee_debut=ad).simulate()[1].set_index('Année')
    return [(cas.at[debut + h, 'PIB_Réel_Base2025'] / base.at[debut + h, 'PIB_Réel_Base2025'] - 1) * 100 / s
            for h in range(10)]


TRANSITION = dict(levier='transition_ecologique', canal=('investissement', 0.0))


def _defaut(levier, param):
    import json
    from pathlib import Path
    mesures = json.loads((Path(__file__).resolve().parents[1] / 'policy_measures.json').read_text(encoding='utf-8'))
    return {m['id']: m for m in mesures['mesures']}[levier]['parametres'][param]['valeur_defaut']


def test_chemin_de_l_investissement_sur_le_tableau_du_fmi():
    """Lot 6, paramètres (arbitrage du mainteneur) : le TOTAL, demande et canal d'offre, d'un levier
    de capital public reproduit année par année, H0 à H4, le tableau 3.4, colonne (1), du FMI
    (``CHEMIN_CIBLE_INVESTISSEMENT``), à la précision du tableau. Rouge avant le recalage du profil :
    0,553 / 1,247 / 1,562 / 1,696 / 1,669. Non-vacuité : le canal d'offre porte bien une part du
    total (sinon la cible serait lue sur la demande seule)."""
    total = _chemin(**TRANSITION)
    demande = _chemin(**TRANSITION, offre=False)
    ecarts = [round(total[h] - CHEMIN_CIBLE_INVESTISSEMENT[h], 5) for h in range(5)]
    assert all(abs(e) < PRECISION_DU_TABLEAU for e in ecarts), (total[:5], ecarts)
    assert total[4] - demande[4] > 0.2 and total[3] - demande[3] > 0.1, (total[:5], demande[:5])


def test_limites_du_chemin_liees_a_la_mesure():
    """METHODOLOGIE (« Calendrier de l'impulsion ») déclare ce que le calage ne fixe pas : le même
    choc en mode cadre, la dépendance à la taille du choc (offre plafonnée), et le chemin des leviers
    qui portent ce profil sans canal d'offre actif sur l'horizon. Chiffres recalculés ici."""
    cadre = _chemin(**TRANSITION, mode='cadre')
    petit, gros = _chemin(**TRANSITION, s=0.5), _chemin(**TRANSITION, s=1.5)
    offre_2030 = _chemin(**TRANSITION, annee_offre=2030)
    sans_offre = _chemin('education')
    sans_offre_cadre = _chemin('education', mode='cadre')
    fmi = sum(CHEMIN_CIBLE_INVESTISSEMENT)
    mesange = 1.31 + 1.38 + 1.22 + (1.22 + 0.93) / 2 + 0.93   # p. 102 ; « 4 ans » au milieu de 3 et 5 ans

    def ecart(cumul, source):
        return _fr(100 * (cumul / source - 1), 1, True)
    recherche = _chemin('recherche_publique', canal=('budget', _defaut('recherche_publique', 'budget')))
    attendus = [
        (f"son total dépasse le tableau : {_fr(recherche[3], 2)} et {_fr(recherche[4], 2)} les deux dernières "
         f"années"),
        f"en mode cadre (choc posé en 2028), {_fr(cadre[3], 2)} et {_fr(cadre[4], 2)} les deux dernières",
        (f"{_fr(petit[4], 2)} à quatre ans pour un choc de 0,5 % du PIB, {_fr(gros[4], 2)} pour un choc "
         f"de 1,5 %"),
        (f"la demande seule : {_fr(sans_offre[3], 2)} et {_fr(sans_offre[4], 2)} les deux dernières "
         f"années, contre {_fr(CHEMIN_CIBLE_INVESTISSEMENT[3], 2)} et "
         f"{_fr(CHEMIN_CIBLE_INVESTISSEMENT[4], 2)}"),
        (f"alimenté par 1 % du PIB nominal de 2030, la cinquième année vaut {_fr(offre_2030[4], 2)} au lieu de "
         f"1,539 ({_fr(offre_2030[4] - CHEMIN_CIBLE_INVESTISSEMENT[4], 3, True)})"),
        (f"un levier à canal d'offre actif est à {ecart(sum(cadre[:5]), fmi)} % du FMI et à "
         f"{ecart(sum(cadre[:5]), mesange)} % de Mésange ; un levier sans canal d'offre, à "
         f"{ecart(sum(sans_offre_cadre[:5]), fmi)} % et {ecart(sum(sans_offre_cadre[:5]), mesange)} %"),
    ]
    # Option du lot 6 (équation) : la santé et la réforme de l'État ne portent plus ce profil ; leur
    # chemin est gardé par tests/test_symetrie_depense_courante.py (celui de la dépense courante).
    texte = ' '.join(METHODO.read_text(encoding='utf-8').split())
    manquants = [a for a in attendus if a not in texte]
    assert not manquants, manquants


def test_cible_affichee_de_l_investissement_est_l_arrondi_du_chemin():
    """``MULT_CIBLE_NIVEAU_4ANS['investissement']`` (1,5) n'est plus lue par le banc depuis le lot 6 : la cible
    opposable est le chemin complet ``CHEMIN_CIBLE_INVESTISSEMENT``. La valeur affichée en reste l'arrondi
    du dernier terme (1,539 → 1,5, comme le texte du FMI p. 82, « 1.5 percent four years after ») : les
    deux ne peuvent pas diverger."""
    assert round(CHEMIN_CIBLE_INVESTISSEMENT[4], 1) == MULT_CIBLE_NIVEAU_4ANS['investissement']
