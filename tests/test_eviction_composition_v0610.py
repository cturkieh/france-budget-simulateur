"""Éviction (« crowding-out ») et composition de l'expansion (v0.6.10, contre-audit
externe V2-01 — ``engine/orchestrator.py`` / ``engine/growth.py``).

Constat de l'auditeur (v0.6.7, reproduit au millième sur v0.6.9) : la part
d'investissement lue par l'éviction divisait des flux BRUTS par levier
(Σ |Δdép| des leviers d'investissement) par des flux NETS agrégés
(|Δdép net| + |Δrec net|). Ce n'était pas une part : un investissement financé
en partie par une coupe la portait au-dessus de 1, et l'intensité
``0,002 + (1 − part) × 0,006`` devenait NÉGATIVE — multipliée par un effort
négatif, l'« éviction » SOUTENAIT l'expansion.

- Contre-exemple, entièrement dans les domaines admis : +20 Md€
  d'investissement de transition, dotation des collectivités 120 → 110
  (−10 Md€). Part 2027 = 20 / 10 = 2,000 ; effet 2027 = +0,001303 pt de
  croissance.
- Programme publié IM Compétitivité : part 2,280 en 2027 (effort négatif,
  effet +0,001454 pt), 2,605 au maximum.

Contrat verrouillé ici : la part est une part (dans [0 ; 1]) et l'éviction ne
soutient jamais une expansion.
"""
import json
import os
from pathlib import Path

import pytest

from budget_simulator.simulator import BudgetSimulatorV45

CONTRE_EXEMPLE = {
    'transition_ecologique': {'investissement': 20},
    'collectivites': {'dotation': 110},
}
IDX_2027 = 2  # année 2027 = indice 2 de la boucle (2025 = base, indice 0)


def _scenarios():
    chemin = (os.environ.get('BUDGETLAB_SCENARIOS_JSON') or '').strip()
    if not chemin or not Path(chemin).exists():
        pytest.skip("scenarios.json introuvable (fork moteur public seul)")
    return {k: v['apiMeasures'] for k, v in json.loads(Path(chemin).read_text(encoding='utf-8')).items()}


def _simuler(mesures):
    """Simulation complète ; renvoie, par indice d'année, l'état macro passé à
    ``calculate_growth`` et les impacts par levier rendus par ``apply_measures``."""
    sim = BudgetSimulatorV45(periods=10, mesures=mesures)
    croissance, appliquer = sim.calculate_growth, sim.apply_measures
    etats, impacts = {}, {}

    def espion_croissance(year, etat):
        etats[year] = dict(etat)
        return croissance(year, etat)

    def espion_mesures(year, *args, **kwargs):
        dep, rec, imp = appliquer(year, *args, **kwargs)
        impacts[year] = {m: dict(v) for m, v in imp.items() if isinstance(v, dict)}
        return dep, rec, imp

    sim.calculate_growth, sim.apply_measures = espion_croissance, espion_mesures
    sim.simulate()
    return etats, impacts


def _effet_eviction(etat):
    """Points de croissance dus à l'éviction du moteur dans l'état ``etat`` :
    croissance d'un simulateur frais SANS impulsion stockée à l'effort de l'état,
    MOINS la même à effort nul. À effort négatif, la cicatrice (effort > 3 %)
    est éteinte : la seule différence est le terme d'éviction."""
    assert etat['effort_budgetaire'] < 0

    def croissance(effort):
        sim = BudgetSimulatorV45(periods=10, mesures={})
        sim._last_impacts = {}
        return sim.calculate_growth(IDX_2027, dict(etat, effort_budgetaire=effort))
    return (croissance(etat['effort_budgetaire']) - croissance(0.0)) * 100


# ---------------------------------------------------------------------------
# Reproduction du contre-audit (V2-01)
# ---------------------------------------------------------------------------

def test_contre_exemple_flux_initiaux():
    """Le contre-exemple est bien celui de l'auditeur : +20 Md€ d'investissement,
    −10 Md€ de dotations, rien d'autre (budget 2026, lu par la macro de 2027)."""
    _, impacts = _simuler(CONTRE_EXEMPLE)
    imp = impacts[2026]
    assert round(imp['transition_ecologique']['depenses'], 3) == 20.0
    assert round(imp['collectivites']['depenses'], 3) == -10.0
    autres = {m: v for m, v in imp.items() if m not in CONTRE_EXEMPLE
              and (abs(v.get('depenses', 0) or 0) > 1e-9 or abs(v.get('recettes', 0) or 0) > 1e-9)}
    assert not autres, autres


def test_contre_exemple_part_est_une_part():
    etats, _ = _simuler(CONTRE_EXEMPLE)
    part = etats[IDX_2027]['part_investissement']
    assert 0.0 <= part <= 1.0, f"part d'investissement 2027 = {part:.3f} (hors [0 ; 1])"


def test_contre_exemple_eviction_ne_soutient_pas_l_expansion():
    etats, _ = _simuler(CONTRE_EXEMPLE)
    etat = etats[IDX_2027]
    assert etat['effort_budgetaire'] < 0 and etat['debt_ratio'] > 1.0  # éviction active
    effet = _effet_eviction(etat)
    assert effet <= 0.0, (
        f"éviction 2027 = {effet:+.6f} pt de croissance (part {etat['part_investissement']:.3f}, "
        f"effort {etat['effort_budgetaire']:+.5f}) : elle SOUTIENT l'expansion")


def test_im_competitivite_part_est_une_part_chaque_annee():
    etats, _ = _simuler(_scenarios()['im_competitivite_2029'])
    parts = {2025 + i: float(e['part_investissement']) for i, e in etats.items()}
    hors = {a: round(p, 3) for a, p in parts.items() if not 0.0 <= p <= 1.0}
    assert not hors, f"parts hors [0 ; 1] : {hors} (max {max(parts.values()):.3f})"


def test_im_competitivite_eviction_ne_soutient_pas_l_expansion_2027():
    etats, _ = _simuler(_scenarios()['im_competitivite_2029'])
    etat = etats[IDX_2027]
    assert etat['effort_budgetaire'] < 0 and etat['debt_ratio'] > 1.0  # éviction active
    effet = _effet_eviction(etat)
    assert effet <= 0.0, (
        f"éviction 2027 = {effet:+.6f} pt de croissance (part {etat['part_investissement']:.3f}, "
        f"effort {etat['effort_budgetaire']:+.5f}) : elle SOUTIENT l'expansion")


# ---------------------------------------------------------------------------
# Propriétés durables (v0.6.10) : la part est une part PAR CONSTRUCTION, et
# l'éviction ne soutient jamais une expansion.
# ---------------------------------------------------------------------------
import ast  # noqa: E402
import inspect  # noqa: E402
import math  # noqa: E402
import random  # noqa: E402

from budget_simulator.constants import (  # noqa: E402
    EVICTION_INTENSITE_INVESTISSEMENT,
    EVICTION_SEUIL_DETTE,
    EVICTION_SURCROIT_NON_PRODUCTIF,
    HANDLER_FAILED_KEY,
    PARAM_DOMAINS,
)
from budget_simulator.engine import growth  # noqa: E402
from budget_simulator.engine.growth import (  # noqa: E402
    effet_eviction,
    flux_par_levier,
    intensite_eviction,
    part_investissement_expansion,
)
from budget_simulator.simulator import FiscalMultipliers  # noqa: E402

INVEST = BudgetSimulatorV45.INVESTMENT_CORE_MEASURES
NETTES = FiscalMultipliers.MESURES_MULTIPLICATEUR_NET
# Interrupteurs 0/1 de PARAM_DOMAINS (même liste que scripts/scan_discontinuites.py).
DRAPEAUX = {'progressive', 'reforme_active', 'exclure_defense', 'exclure_ue',
            'exclure_dette', 'asu_activation', 'degressivite'}
GRAINE = 20261021


def _part(impacts):
    return part_investissement_expansion(impacts, INVEST, NETTES)


def _verifier_etats(nom, etats):
    """Contrat sur chaque état macro d'une simulation : part ∈ [0 ; 1] et
    éviction ≤ 0 (strictement < 0 quand elle joue)."""
    for i, e in etats.items():
        p = e['part_investissement']
        assert 0.0 <= p <= 1.0, f"{nom} {2025 + i} : part {p!r} hors [0 ; 1]"
        effet = effet_eviction(e['effort_budgetaire'], e['debt_ratio'], p)
        if e['effort_budgetaire'] < 0 and e['debt_ratio'] > EVICTION_SEUIL_DETTE:
            assert effet < 0.0, f"{nom} {2025 + i} : éviction {effet!r} ≥ 0 en expansion"
        else:
            assert effet == 0.0


# --- Convention de la part (fonction pure) ---------------------------------

@pytest.mark.parametrize('impacts, attendu', [
    # Contre-exemple V2-01 : investissement financé en partie par une coupe →
    # la relance est 100 % investissement.
    ({'transition_ecologique': {'depenses': 20.0}, 'collectivites': {'depenses': -10.0}}, 1.0),
    # Une COUPE d'investissement n'est pas une part d'investissement de la relance.
    ({'recherche_publique': {'depenses': -10.0}, 'tva_rate': {'recettes': -5.0}}, 0.0),
    # … levier PAR LEVIER : la coupe d'un levier d'investissement ne se compense
    # pas avec la hausse d'un AUTRE (un numérateur d'investissement NET
    # donnerait 10/30) ; elle finance l'expansion au prorata, comme toute coupe.
    ({'education': {'depenses': 20.0}, 'recherche_publique': {'depenses': -10.0},
      'retraites': {'depenses': 10.0}}, 20 / 30),
    # Seules les DÉPENSES d'un levier d'investissement en sont : baisser la taxe
    # carbone (recette du levier transition) est une baisse d'impôt.
    ({'transition_ecologique': {'depenses': 10.0, 'recettes': -30.0}}, 0.25),
    # Prorata : 30 d'investissement sur 60 d'expansion brute (10 de transferts,
    # 20 de baisse d'impôts) ; la hausse d'IS finance au prorata, hors composition.
    ({'education': {'depenses': 30.0}, 'retraites': {'depenses': 10.0},
      'tva_rate': {'recettes': -20.0}, 'impot_societes': {'recettes': 50.0}}, 0.5),
    # Levier à multiplicateur NET (SMIC) : compté sur son solde, comme ses impulsions.
    ({'smic': {'depenses': 10.0, 'recettes': 4.0}, 'education': {'depenses': 6.0}}, 0.5),
    # Levier en échec (0/0) ou entrée non-dict : sans effet.
    ({'education': {'depenses': 5.0}, 'retraites': {'depenses': 0, 'recettes': 0, HANDLER_FAILED_KEY: True},
      'bruit': 3.0}, 1.0),
    # Aucune expansion → 0 (l'éviction ne joue pas : effort ≥ 0).
    ({'tva_rate': {'recettes': 7.0}, 'education': {'depenses': -3.0}}, 0.0),
    ({}, 0.0),
])
def test_convention_part_investissement_expansion(impacts, attendu):
    assert _part(impacts) == attendu


def test_moteur_complet_coupe_d_un_levier_d_investissement_hausse_d_un_autre():
    """Programme admissible : +20 Md€ de transition, −20 000 enseignants (coupe
    du levier d'investissement « éducation », −1,3 Md€ en 2026), dotation des
    collectivités 120 → 130. Expansion brute 30, dont 20 d'investissement : part
    2/3 — et non (20 − 1,3)/30 = 0,623 comme avec un investissement NET."""
    etats, impacts = _simuler({'transition_ecologique': {'investissement': 20},
                               'education': {'enseignants': -20000}, 'collectivites': {'dotation': 130}})
    assert impacts[2026]['education']['depenses'] < 0  # la coupe existe bien
    assert etats[IDX_2027]['part_investissement'] == pytest.approx(2 / 3, abs=1e-3)


# --- Câblage du site d'appel (orchestrateur) ----------------------------------
# SMIC (levier à multiplicateur NET), santé (dépense non productive), éducation
# (investissement productif) : seul cas où les deux ensembles passés par
# l'orchestrateur changent tous deux la part.
SMIC_SANTE_EDUCATION = {'smic': {'montant_brut': 2000}, 'sante': {'prevention_budget': 11.2},
                        'education': {'budget': 80}}


def test_site_d_appel_part_du_budget_de_l_annee_precedente():
    """La part lue par la macro de l'année t est EXACTEMENT
    ``part_investissement_expansion`` du budget de t−1, avec les ensembles du
    moteur (``INVESTMENT_CORE_MEASURES``, ``MESURES_MULTIPLICATEUR_NET``) ; 0 en
    2026 (aucun budget antérieur). Les tests de convention appellent la fonction
    pure : celui-ci verrouille ce que l'orchestrateur lui passe."""
    cas = dict(_scenarios(), contre_exemple=CONTRE_EXEMPLE, smic_sante_education=SMIC_SANTE_EDUCATION)
    for sid, mesures in cas.items():
        etats, impacts = _simuler(mesures)
        assert sorted(etats) == list(range(1, 11)), sid
        assert etats[1]['part_investissement'] == 0.0, sid
        for i in range(2, 11):
            assert etats[i]['part_investissement'] == _part(impacts[2025 + i - 1]), (sid, 2025 + i)


def test_moteur_complet_smic_sur_son_solde_sante_non_productive():
    """Part 2027 = 15 / (15 + 3,7 + 4,04) ≈ 0,660 : éducation +15 Md€
    (investissement), santé +3,7 (non productive), SMIC −4,04 de SOLDE
    (+6,96 de dépenses, +2,92 de recettes). Compter le SMIC flux par flux
    donnerait 0,585 ; prendre le périmètre « flux » de l'investissement, 0,822."""
    etats, _ = _simuler(SMIC_SANTE_EDUCATION)
    assert etats[IDX_2027]['part_investissement'] == pytest.approx(15 / (15 + 3.7 + 4.04), abs=1e-4)


def test_leviers_investissement_et_leviers_nets_disjoints():
    """Un levier d'investissement compté sur son SOLDE ne serait jamais lu comme
    investissement (canal 'solde') : les deux ensembles doivent rester disjoints."""
    assert not INVEST & NETTES


def test_impulsions_et_eviction_lisent_la_meme_decomposition():
    """UNE convention de flux par levier pour les deux canaux de demande : les
    niveaux d'impulsion sont exactement les flux de ``flux_par_levier`` / PIB."""
    impacts = {'education': {'depenses': 12.0, 'recettes': 0.0}, 'smic': {'depenses': 3.0, 'recettes': 1.0},
               'tva_rate': {'depenses': 0.0, 'recettes': -4.0}}
    sim = BudgetSimulatorV45(periods=10, mesures={})
    sim.pib_nominal = 3000.0
    sim._last_impacts = impacts
    sim._stocker_impulsions(1, dict(output_gap=0.0, debt_ratio=1.1, unemployment_gap=0.0, interest_rate=0.03))
    assert sim._niveaux_impulsion == {k: v / 3000.0 for k, v in flux_par_levier(impacts, NETTES).items()}


def test_part_dans_0_1_sur_tirages_synthetiques_y_compris_en_flottants():
    """5 000 budgets synthétiques (graine fixe), flux de toutes tailles et de tous
    signes, levier par levier : la part reste dans [0 ; 1] AU BIT près, et vaut
    exactement 1 quand toute l'expansion est de l'investissement."""
    rng = random.Random(GRAINE)
    leviers = sorted(INVEST) + ['retraites', 'tva_rate', 'collectivites', 'smic', 'fraude_fiscale', 'defense']
    for _ in range(5000):
        impacts = {m: {'depenses': rng.uniform(-1, 1) * 10 ** rng.uniform(-6, 2),
                       'recettes': rng.uniform(-1, 1) * 10 ** rng.uniform(-6, 2)}
                   for m in rng.sample(leviers, rng.randint(1, len(leviers)))}
        p = _part(impacts)
        assert 0.0 <= p <= 1.0, (p, impacts)
        pur = {m: {'depenses': abs(v['depenses']), 'recettes': 0.0} for m, v in impacts.items() if m in INVEST}
        if pur:
            pur['collectivites'] = {'depenses': -rng.uniform(0, 100), 'recettes': rng.uniform(0, 100)}
            assert _part(pur) == 1.0, pur


# --- (i) Part ∈ [0 ; 1] sur les budgets admissibles du moteur complet ---------

def _hausses_investissement():
    """Chaque paramètre d'un levier d'investissement productif poussé à la borne
    qui ACCROÎT la dépense (borne haute ; la taxe carbone est une recette)."""
    return [(m, p, hi) for m in sorted(INVEST) for p, (lo, hi) in PARAM_DOMAINS.get(m, {}).items()
            if p != 'taxe_carbone']


def _autres_bornes():
    return [(m, p, b) for m, dom in PARAM_DOMAINS.items() if m not in INVEST
            for p, (lo, hi) in dom.items() for b in (lo, hi)]


def test_paires_investissement_coupe_aux_bornes_des_domaines():
    """Investissement poussé au maximum de son domaine × chaque autre paramètre à
    chacune de ses bornes (coupe, hausse d'impôt, ou expansion concurrente)."""
    for mi, pi, xi in _hausses_investissement():
        for mo, po, xo in _autres_bornes():
            mesures = {mi: {pi: xi}, mo: {po: xo}}
            etats, _ = _simuler(mesures)
            _verifier_etats(f"{mi}.{pi}={xi} + {mo}.{po}={xo}", etats)


def test_scenarios_publies():
    for sid, mesures in _scenarios().items():
        etats, _ = _simuler(mesures)
        _verifier_etats(sid, etats)


def test_tirages_aleatoires_dans_param_domains():
    """200 programmes tirés à graine fixe : chaque levier présent une fois sur
    deux, chaque paramètre uniforme dans son domaine (interrupteurs : 0 ou 1)."""
    rng = random.Random(GRAINE)
    for k in range(200):
        mesures = {}
        for m, dom in PARAM_DOMAINS.items():
            if rng.random() < 0.5:
                mesures[m] = {p: (rng.choice((lo, hi)) if p in DRAPEAUX else rng.uniform(lo, hi))
                              for p, (lo, hi) in dom.items()}
        etats, _ = _simuler(mesures)
        _verifier_etats(f"tirage {k}", etats)


# --- (ii) L'éviction ne soutient jamais une expansion -------------------------

def test_eviction_negative_pour_toute_expansion_au_dela_du_seuil():
    for effort in (-0.10, -0.03, -0.005, -1e-6, -1e-12):
        for dette in (EVICTION_SEUIL_DETTE + 1e-12, 1.2, 3.0):
            for i in range(101):
                p = i / 100
                assert effet_eviction(effort, dette, p) < 0.0, (effort, dette, p)
    # Hors du domaine de l'éviction : exactement nulle.
    for effort, dette in ((0.0, 1.5), (0.02, 1.5), (-0.02, EVICTION_SEUIL_DETTE), (-0.02, 0.8)):
        assert effet_eviction(effort, dette, 0.3) == 0.0


@pytest.mark.parametrize('part', [-1e-12, 1.0 + 1e-12, 2.0, -0.5, math.nan, math.inf])
def test_part_hors_0_1_est_un_defaut_moteur_bruyant(part):
    """Hors [0 ; 1] l'intensité peut devenir négative : RuntimeError (500 + ERROR
    côté API), jamais un bornage silencieux."""
    with pytest.raises(RuntimeError, match=r"hors \[0 ; 1\]"):
        intensite_eviction(part)
    with pytest.raises(RuntimeError):
        effet_eviction(-0.01, 1.2, part)


def test_eviction_du_moteur_complet_negative_sur_les_scenarios_publies():
    """Mesure au banc (``calculate_growth``), chaque année d'expansion à dette >
    100 % des 10 scénarios publiés et du contre-exemple."""
    cas = dict(_scenarios(), contre_exemple=CONTRE_EXEMPLE)
    vus = 0
    for sid, mesures in cas.items():
        etats, _ = _simuler(mesures)
        for i, e in etats.items():
            if e['effort_budgetaire'] < 0 and e['debt_ratio'] > EVICTION_SEUIL_DETTE:
                vus += 1
                assert _effet_eviction(e) < 0.0, (sid, 2025 + i)
    assert vus >= 20  # anti-faux-vert : l'éviction joue bien sur ces programmes


# --- (iii) Bornes de l'intensité ----------------------------------------------

def test_intensite_aux_bornes_de_la_part():
    assert intensite_eviction(1.0) == EVICTION_INTENSITE_INVESTISSEMENT == 0.002
    assert intensite_eviction(0.0) == EVICTION_INTENSITE_INVESTISSEMENT + EVICTION_SURCROIT_NON_PRODUCTIF == 0.008
    valeurs = [intensite_eviction(i / 1000) for i in range(1001)]
    assert all(a >= b for a, b in zip(valeurs, valeurs[1:]))  # décroissante en la part
    assert min(valeurs) > 0.0


def test_contre_exemple_relance_100_pour_cent_investissement():
    """Le contre-exemple est une relance entièrement faite d'investissement :
    part 1, éviction à l'intensité basse — mesurée dans ``calculate_growth``."""
    etats, _ = _simuler(CONTRE_EXEMPLE)
    e = etats[IDX_2027]
    assert e['part_investissement'] == 1.0
    attendu = EVICTION_INTENSITE_INVESTISSEMENT * e['effort_budgetaire'] * 100
    assert _effet_eviction(e) == pytest.approx(attendu, rel=1e-9, abs=1e-15)


# --- (iv) Constantes nommées, plus de littéraux --------------------------------

def _litteraux_flottants(fonction):
    return {n.value for n in ast.walk(ast.parse(inspect.getsource(fonction).strip()))
            if isinstance(n, ast.Constant) and isinstance(n.value, float)}


def test_constantes_nommees_sans_litteral_dans_l_eviction():
    """Les coefficients de l'éviction vivent dans constants.py (source unique) ;
    les fonctions de l'éviction et ``calculate_growth`` n'en portent plus aucun
    littéral (seuls restent 0 et 1, bornes d'une part et effet nul)."""
    assert (EVICTION_SEUIL_DETTE, EVICTION_INTENSITE_INVESTISSEMENT, EVICTION_SURCROIT_NON_PRODUCTIF) == (1.0, 0.002, 0.006)
    for f in (intensite_eviction, effet_eviction, part_investissement_expansion):
        assert _litteraux_flottants(f) <= {0.0, 1.0}, (f.__name__, _litteraux_flottants(f))
    assert not _litteraux_flottants(growth.GrowthMixin.calculate_growth) & {0.002, 0.006, 0.008}
    assert 'EVICTION_SEUIL_DETTE' in inspect.getsource(effet_eviction)


# --- Docs publics alignés sur le code -----------------------------------------

def test_docs_publics_ne_pretent_aucune_source_a_l_eviction():
    """Les deux docs publics (copiés sur le site par sync_public_docs) décrivent
    l'éviction telle que codée : coefficients SANS source publiée (constants.py),
    part = part d'investissement de l'expansion brute. L'un d'eux affichait
    « Litterature standard sur l'eviction », une source qui n'existe pas."""
    docs = Path(__file__).resolve().parent.parent / 'docs'
    explication = (docs / 'EXPLICATION_MODELE_ECONOMIQUE.md').read_text(encoding='utf-8')
    section = explication.split('### 3. Crowding-Out', 1)[1].split('\n### ', 1)[0]
    assert 'aucune source publiée' in section.lower(), section[:300]
    assert 'expansion brute' in section and '[0 ; 1]' in section, section[:300]
    for nom, texte in (('EXPLICATION', explication),
                       ('METHODOLOGIE', (docs / 'METHODOLOGIE.md').read_text(encoding='utf-8'))):
        assert "standard sur l'eviction" not in texte.lower() and 'eviction standard' not in texte.lower(), nom
