"""v0.6.7 — bornes d'entrée et de sortie du moteur (audit externe, oct. 2026).

Constats reproduits (rouges sur v0.6.6) :
- 16 des 55 paramètres bornés par `policy_measures.json` seulement : TVA à
  2 000 % → pouvoir d'achat 2035 de −296,3, `valid: true` ;
- lecteurs latéraux de `self.mesures` (effets d'offre…) servis en valeur BRUTE,
  même quand la porte annuelle clampait le handler ;
- entier JSON géant → OverflowError hors de tout `try` (500 en tolérant) ;
- `defense.budget = "bad"` (formule ASTEVAL) → effet nul, aucun drapeau, même
  en strict ; une ligne ERROR par année simulée ;
- pouvoir d'achat et compétitivité sans aucune borne (signe inversé) ;
- 50 ans de consolidation maximale → dette brute négative, `valid: true`,
  libellés « 2035 » et « 50/10 » ;
- `report.valid` : statu quo `false`, TVA 2 000 % `true`.
"""
import json
import logging
import os
import pathlib
from unittest.mock import patch

import pytest

from budget_simulator.constants import (
    INTENSITE_DOMAINS,
    PARAM_DOMAINS,
    POLICY_MEASURES_PATH,
)
from budget_simulator.simulator import BudgetSimulatorV45

RACINE = pathlib.Path(__file__).resolve().parent.parent
PA = "Pouvoir d'Achat"

# Combinaison de l'audit (bloc C, constat 2) : pour chaque paramètre publié,
# la borne qui minimise la dette 2035 — toutes les valeurs sont DANS le domaine.
CONSOLIDATION_MAXIMALE = {
    "fraude_fiscale": {"effort": 1}, "tva_rate": {"taux": 0.25},
    "impot_societes": {"taux": 0.35, "niches": 25},
    "retraites": {"age_depart": 67.0, "indexation": 0.0, "duree_cotisation": 45.0},
    "sante": {"franchise_participation_taux": 200},
    "chomage_alloc": {"montant": 27.5, "duree": 12},
    "fonction_publique": {"effectifs": -100000, "point_indice": -2.0},
    "fonction_publique_reforme": {"fusion_agences": 10, "digitalisation": 10},
    "education": {"budget": 60, "enseignants": -20000, "salaires": -5},
    "collectivites": {"dotation": 100, "investissement": -10},
    "defense": {"budget": 40},
    "transition_ecologique": {"investissement": 50, "taxe_carbone": 300, "renovation": 20},
    "recherche_publique": {"budget": 20}, "immigration": {"ame": 0.0, "integration": 0.0},
    "impot_revenu": {"taux_superieur": 0.6, "decote": 0.5}, "fraude_sociale": {"effort": 1},
    "optimisation_dette": {"intensite": 1}, "prestations_indexation": {"taux_indexation": 0.0},
    "csg": {"taux": 0.12, "progressive": 1}, "cotisations_patronales": {"taux": 0.35},
    "elargissement_ir": {"taux_contribuables_cible": 0.7},
    "fiscalite_patrimoine": {"intensite": 0.3}, "impots_production": {"montant": 125},
    "is_exceptionnel_tge": {"montant": 15}, "isf_climatique": {"intensite": 1},
    "niches_fiscales_tge": {"montant": 5}, "niches_sociales_tge": {"montant": 10},
    "subventions_tge": {"montant": 5}, "taxe_superprofits": {"intensite": 1},
    "rabot_uniforme": {"taux_reduction": 0.15},
}


@pytest.fixture
def tolerant():
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': ''}):
        yield


def _simuler(mesures, periods=10):
    return BudgetSimulatorV45(periods=periods, mesures=mesures).simulate()


def _corrections(report):
    return [w for w in report['warnings'] if w.startswith('Entrée ou sortie corrigée')]


# --------------------------------------------------------------------------
# Bornes d'entrée : source unique, couverture, curseurs réels
# --------------------------------------------------------------------------

def test_les_55_parametres_bornes_par_le_registre_public_sont_au_moteur():
    """Chaque min/max publié par `policy_measures.json` a un domaine moteur
    (PARAM_DOMAINS, ou INTENSITE_DOMAINS pour les `intensite`)."""
    registre = json.loads(POLICY_MEASURES_PATH.read_text(encoding='utf-8'))
    publies = [(m['id'], p) for m in registre['mesures']
               for p, spec in (m.get('parametres') or {}).items()
               if spec.get('min') is not None and spec.get('max') is not None]
    assert len(publies) == 55
    manquants = [(mid, p) for mid, p in publies
                 if p not in PARAM_DOMAINS.get(mid, {})
                 and not (p == 'intensite' and mid in INTENSITE_DOMAINS)]
    assert not manquants, f"paramètres publiés sans domaine moteur : {manquants}"


def test_les_curseurs_reels_tiennent_dans_les_domaines():
    """Le curseur RÉEL du site (`LEVER_META`, relu par
    generate_measure_registry dans le snapshot GÉNÉRÉ) ne doit jamais pouvoir
    poser une valeur que le moteur clamperait. Rouge en v0.6.6 : la dotation à
    150 était ramenée à 140."""
    snapshot = json.loads((RACINE / 'tests' / 'snapshots' / 'measure_registry.json')
                          .read_text(encoding='utf-8'))
    # Le snapshot porte les bornes en unités d'UI ; un seul curseur borné est
    # converti par convertToAPIFormat (pourcentage → ratio). Un nouveau curseur
    # converti ferait rougir ce test (fausse alerte, jamais faux vert).
    echelle_ui = {'prestations_indexation': 100}
    verifies, hors = 0, []
    for mid, entree in snapshot['mesures'].items():
        for curseur in entree.get('sliders', []):
            curseur = {**curseur, 'min': curseur['min'] / echelle_ui.get(curseur['id'], 1),
                       'max': curseur['max'] / echelle_ui.get(curseur['id'], 1)}
            param = curseur['param']
            domaine = PARAM_DOMAINS.get(mid, {}).get(param)
            if domaine is None and param == 'intensite':
                domaine = INTENSITE_DOMAINS.get(mid)
            if domaine is None:
                continue
            verifies += 1
            if curseur['min'] < domaine[0] or curseur['max'] > domaine[1]:
                hors.append((curseur['id'], curseur['min'], curseur['max'], domaine))
    assert verifies >= 40, f"snapshot sans curseurs relus ({verifies}) : garde vide"
    assert not hors, f"curseurs que le moteur clamperait : {hors}"


# --------------------------------------------------------------------------
# Constats d'entrée reproduits
# --------------------------------------------------------------------------

def test_tva_2000_pct_est_clampee_et_signalee(tolerant):
    """Avant : PA 2035 −296,3 et `valid: true`."""
    df, _, report = _simuler({'tva_rate': {'taux': 20}})
    df_borne, _, _ = _simuler({'tva_rate': {'taux': 0.25}})
    assert df[PA].tolist() == df_borne[PA].tolist()
    assert df[PA].iloc[-1] > 0
    assert report['valid'] is False
    assert any('tva_rate.taux=20' in w for w in _corrections(report))


def test_les_lecteurs_lateraux_lisent_la_valeur_corrigee(tolerant):
    """`education.budget` est aussi lu, hors porte, par l'effet d'offre de
    growth.py : avant, 10**6 était clampé pour le handler mais ajoutait toujours
    ~2 pts de croissance potentielle. La trajectoire doit être celle de la borne."""
    df, _, _ = _simuler({'education': {'budget': 10 ** 6}})
    df_borne, _, _ = _simuler({'education': {'budget': 90}})
    assert df.equals(df_borne)


def test_l_entree_de_l_appelant_n_est_pas_mutee_et_resignale(tolerant):
    mesures = {'tva_rate': {'taux': 20}}
    sim = BudgetSimulatorV45(periods=3, mesures=mesures)
    _, _, r1 = sim.simulate()
    _, _, r2 = sim.simulate()
    assert sim.mesures is mesures and mesures == {'tva_rate': {'taux': 20}}
    assert r1['valid'] is r2['valid'] is False


@pytest.mark.parametrize('valeur', [10 ** 400, float('inf'), float('-inf')],
                         ids=['entier_geant', 'inf', 'moins_inf'])
def test_valeur_non_finie_retiree_et_signalee(tolerant, valeur):
    """Avant : l'entier géant levait OverflowError hors du `try` (500)."""
    df, _, report = _simuler({'csg': {'taux': valeur}})
    df_defaut, _, _ = _simuler({'csg': {}})
    assert df.equals(df_defaut)
    assert report['valid'] is False
    assert any('csg.taux' in w and 'non finie' in w for w in _corrections(report))


@pytest.mark.parametrize('valeur', [10 ** 400, float('inf')], ids=['entier_geant', 'inf'])
def test_valeur_non_finie_rejetee_en_strict(valeur):
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1'}), \
            pytest.raises(ExceptionGroup) as excinfo:
        _simuler({'csg': {'taux': valeur}})
    from budget_simulator import EntreeInvalide
    assert all(isinstance(e, EntreeInvalide) for e in excinfo.value.exceptions)


def test_formule_asteval_valeur_texte_drapeau_et_warning_unique(tolerant, caplog):
    """`defense` passe par une formule ASTEVAL : avant, "bad" → effet nul,
    aucun drapeau dans la réponse, une ERROR par année simulée."""
    with caplog.at_level(logging.WARNING):
        _, _, report = _simuler({'defense': {'budget': 'bad'}})
    impacts = [y['defense'] for y in report['measure_impacts_by_year'] if 'defense' in y]
    assert impacts and all(i.get('_handler_failed') is True for i in impacts)
    assert report['valid'] is False
    assert any(w.startswith('Entrée ou sortie corrigée — defense : levier en échec')
               for w in report['warnings'])
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len([r for r in caplog.records if 'PARAM_INVALIDE' in r.getMessage()]) == 1


def test_formule_asteval_valeur_texte_escalade_en_strict():
    from budget_simulator import EntreeInvalide
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1'}), \
            pytest.raises(ExceptionGroup) as excinfo:
        _simuler({'defense': {'budget': 'bad'}})
    assert all(isinstance(e, EntreeInvalide) and isinstance(e, TypeError)
               for e in excinfo.value.exceptions)


def test_formule_asteval_en_echec_suit_le_chemin_handler(tolerant, caplog):
    """Bug de formule (et non d'entrée) : ERROR UNE fois + drapeau, plus un
    `result = 0` muet."""
    sim = BudgetSimulatorV45(periods=4, mesures={'defense': {'budget': 55}})
    sim.measure_registry['defense'] = {**sim.measure_registry['defense'],
                                       'formule': 'p["budget"] +* 1'}
    with caplog.at_level(logging.ERROR):
        _, _, report = sim.simulate()
    assert any(y.get('defense', {}).get('_handler_failed') for y in report['measure_impacts_by_year'])
    erreurs = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(erreurs) == 1 and 'defense' in erreurs[0].getMessage()


def test_bloc_de_milliers_de_null_une_seule_ligne(tolerant, caplog):
    """Volume Sentry Logs (backlog 2026-10-05 (2)) : une ligne par levier et
    par catégorie, plus une par clé."""
    bloc = {f'cle_{i}': None for i in range(2000)}
    with caplog.at_level(logging.WARNING):
        _simuler({'csg': bloc}, periods=3)
    lignes = [r for r in caplog.records if 'PARAM_NULL' in r.getMessage()]
    assert len(lignes) == 1 and '(+1995 autres)' in lignes[0].getMessage()


def test_bloc_vide_avis_sans_invalider(tolerant):
    _, _, report = _simuler({'taxe_superprofits': {}})
    assert report['valid'] is True
    assert any(w.startswith('Avis — taxe_superprofits={}') for w in report['warnings'])


# --------------------------------------------------------------------------
# Bornes de sortie, horizon, `valid`
# --------------------------------------------------------------------------

def test_statu_quo_valide(tolerant):
    """Avant : `valid: false` (dette 2035 > 160 % jugée « invalide »)."""
    _, _, report = _simuler({})
    assert report['valid'] is True and not _corrections(report)


def test_borne_physique_du_pouvoir_d_achat(tolerant, monkeypatch):
    """Porte d'entrée retirée : seule la borne de sortie protège. Avant : PA
    négatif (variation ≤ −100 %), sans un signal."""
    for mid in list(PARAM_DOMAINS):
        monkeypatch.delitem(PARAM_DOMAINS, mid)
    df, _, report = _simuler({'tva_rate': {'taux': 20}})
    assert (df[PA] > 0).all()
    assert report['valid'] is False
    assert any("Pouvoir d'achat : variation annuelle bornée" in w for w in report['warnings'])


def test_bornes_de_sortie_ne_mordent_sur_aucun_scenario_publie(tolerant):
    """Les bornes de sortie sont des filets : aucun scénario servi ne les
    atteint (sinon elles changeraient un chiffre publié)."""
    env = (os.environ.get('BUDGETLAB_SCENARIOS_JSON') or '').strip()
    chemin = pathlib.Path(env) if env else RACINE / '..' / '..' / 'frontend-react' / 'src' / 'data' / 'scenarios.json'
    if not chemin.exists():
        pytest.skip("scenarios.json introuvable (fork moteur public seul)")
    for nom, contenu in json.loads(chemin.read_text(encoding='utf-8')).items():
        _, _, report = _simuler(contenu.get('apiMeasures') or {})
        assert report['valid'] is True, (nom, _corrections(report))


def test_horizon_long_dette_bornee_a_zero_et_libelles_derives(tolerant):
    """Avant : dette −2 311,7 Md€ en 2075, `valid: true`, « Solde budgétaire
    2035 » (valeur 2075) et « Années excédent budgétaire : 50/10 ».

    v0.6.7 : depuis que chaque marche de la consolidation est multipliée
    (engine/growth.py), la consolidation maximale paie son coût de croissance
    et ne passe plus sous zéro en 50 ans (45,6 % en 2075). Le mécanisme testé
    — borne à 0 et libellés dérivés de l'horizon — ne dépend pas du scénario :
    on part d'une dette initiale de 60 % du PIB pour l'exercer (borne dès 2051).
    """
    sim = BudgetSimulatorV45(periods=50, mesures=CONSOLIDATION_MAXIMALE)
    sim.base_params['dette_ratio'] = 0.60
    df, _, report = sim.simulate()
    assert (df['Dette'] >= 0).all()
    assert report['valid'] is False
    assert any('Dette brute bornée à 0' in w for w in report['warnings'])
    assert any(t.startswith('Solde budgétaire 2075') for t in report['tests'])
    assert any(t.startswith('Années excédent budgétaire: ') and t.endswith('/50')
               for t in report['tests'])
    assert not any('2035' in t or '/10' in t for t in report['tests'])


def test_horizon_10_ans_inchange(tolerant):
    """Sur l'horizon servi, la consolidation maximale ne touche aucune borne."""
    df, _, report = _simuler(CONSOLIDATION_MAXIMALE, periods=10)
    assert df['Dette'].min() > 0 and report['valid'] is True
    assert any(t.startswith('Solde budgétaire 2035') for t in report['tests'])
