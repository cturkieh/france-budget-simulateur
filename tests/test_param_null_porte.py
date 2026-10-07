"""JSON ``null`` dans l'entrée d'une mesure = « pas de valeur » (Sentry FRANCE-BUDGET-Z).

Constat (prod, 70 événements en 31 s) : ``POST /simulate`` avec
``{"impots_production": {"montant": null}}``. ``params.get('montant', 97)``
rend ``None`` (la clé EXISTE, sa valeur est nulle) au lieu du défaut, et
``97 - None`` lève ``TypeError``. L'``except`` d'``apply_measures`` l'absorbe
(``logger.error`` + ``HANDLER_FAILED_KEY``) une fois PAR ANNÉE simulée : la
mesure est comptée à 0 et le logger ouvre une issue Sentry par année.

Cause racine : la porte de finitude universelle (``_refuser_non_finis``)
retire un NaN parce qu'il « dit pas de valeur », mais laissait passer
``None``, qui dit exactement la même chose. Contrat posé ici, par PROPRIÉTÉ
et non levier par levier : pour CHAQUE mesure du registre et CHAQUE
paramètre nommé, ``None`` produit le résultat BIT-IDENTIQUE de la clé
absente, sans exception, sans ``HANDLER_FAILED_KEY``, sans ERROR — en mode
tolérant ET en ``BUDGETLAB_STRICT``. Un WARNING ``PARAM_NULL`` dédupliqué
garde la trace (l'appelant devrait omettre la clé).

Inventaire des lecteurs (leçon v0.6.x) : plusieurs canaux lisent
``self.mesures`` BRUT, sans passer par la porte. La propriété est donc
vérifiée deux fois : mesure isolée, puis TOUTES les mesures présentes —
c'est la seconde qui attrape un canal latéral (ex. le SMIC qui lit
``fonction_publique.point_indice``).

Même logique un cran plus haut : un bloc ``{"levier": null}`` équivaut au
levier ABSENT — et non à ``{"levier": {}}``, qui n'est pas neutre :
``{"taxe_superprofits": {}}`` applique la taxe à 25 % tous secteurs (choix de
conception antérieur). Sur un outil dont la neutralité est l'argument
central, « pas de valeur » doit donner exactement le résultat sans le levier,
y compris dans les lecteurs latéraux (hash des mesures, effets d'offre, SMIC,
ASU, seniors, réforme FP). Un bloc mal formé (liste, nombre, str) reste, lui,
un échec BRUYANT par la porte unique (décision verrouillée,
``test_asu_prestations_indexation_contract.py``) — mais il ne doit plus faire
tomber TOUTE la simulation (constat de la même passe : le hash des mesures
levait hors de tout ``try`` → 500 sur l'API dès qu'une autre mesure bougeait).
"""
import json
import logging
import math
import os
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from budget_simulator.constants import HANDLER_FAILED_KEY, INTENSITE_DOMAINS, PARAM_DOMAINS
from budget_simulator.engine._param_domain import validate_param_domains, valeur_brute
from budget_simulator.simulator import BudgetSimulatorV45

# `.absolute()` et non `.resolve()` : tests/ est un symlink depuis le parent.
ROOT = Path(__file__).absolute().parent.parent
REGISTRE_JSON = ROOT / 'tests' / 'snapshots' / 'measure_registry.json'

PERIODES = 10
_SIM = BudgetSimulatorV45(periods=1)
_REGISTRE = json.loads(REGISTRE_JSON.read_text())['mesures']


def _paires_mesure_param():
    """(mesure, paramètre) — union de TROIS sources pour ne rater aucun
    lecteur : le registre généré depuis l'AST des handlers, les défauts
    moteur, et les ``parametres`` déclarés de ``policy_measures.json`` (seule
    source pour les mesures ASTEVAL)."""
    paires = set()
    for mesure, cfg in _REGISTRE.items():
        for param in (cfg.get('params') or {}):
            paires.add((mesure, param))
    for mesure, params in _SIM._get_default_values().items():
        for param in params:
            paires.add((mesure, param))
    for mesure, cfg in _SIM.measure_registry.items():
        for param in (cfg.get('parametres') or {}):
            paires.add((mesure, param))
    return sorted(p for p in paires if p[0] in _SIM.measure_registry)


def _base_toutes_actives():
    """Chaque levier dévié à la borne HAUTE de son curseur (registre généré),
    ramenée dans le domaine moteur quand il en déclare un (sinon le strict
    lèverait pour hors-domaine, pas pour null). Sert à exercer les canaux
    latéraux avec un CONSOMMATEUR actif : à ses défauts, un handler sort
    souvent avant de lire la mesure voisine (constaté : SMIC)."""
    base = {}
    for mesure, cfg in _REGISTRE.items():
        for curseur in cfg.get('sliders') or []:
            param, haut = curseur.get('param'), curseur.get('max')
            if not param or haut is None:
                continue
            if param == 'intensite' and mesure in INTENSITE_DOMAINS:
                haut = INTENSITE_DOMAINS[mesure][1]
            elif param in PARAM_DOMAINS.get(mesure, {}):
                haut = PARAM_DOMAINS[mesure][param][1]
            base.setdefault(mesure, {})[param] = haut
    return base


PAIRES = _paires_mesure_param()
MESURES = sorted(_SIM.measure_registry)
BASE_ACTIVE = _base_toutes_actives()


def test_inventaire_non_vide_et_contient_le_cas_prod():
    """Anti-faux-vert : une propriété sur une liste vide est vraie par vacuité."""
    assert len(PAIRES) >= 60, f"inventaire anormalement court : {len(PAIRES)}"
    assert ('impots_production', 'montant') in PAIRES
    assert len(MESURES) >= 36
    assert len(BASE_ACTIVE) >= 30, f"base active anormalement courte : {len(BASE_ACTIVE)}"
    assert BASE_ACTIVE['smic'] and BASE_ACTIVE['fraude_sociale'] and BASE_ACTIVE['asu']


def _simuler(mesures, strict):
    sim = BudgetSimulatorV45(periods=PERIODES, mesures=mesures)
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1' if strict else ''}):
        df, detail, rapport = sim.simulate()
    return df, detail, rapport['measure_impacts_by_year']


_REFERENCES = {}


def _simuler_reference(mesures, strict):
    """Résultat de RÉFÉRENCE (sans null), mémoïsé : des centaines de cas
    partagent la même référence (ex. toutes les paires d'une mesure, ou la
    base « toutes mesures présentes »). Le moteur est déterministe et les
    résultats ne sont que lus (``assert_frame_equal``)."""
    cle = (json.dumps(mesures, sort_keys=True), strict)
    if cle not in _REFERENCES:
        _REFERENCES[cle] = _simuler(mesures, strict)
    return _REFERENCES[cle]


def _autre_mesure_active(mesure):
    """Une mesure ACTIVE autre que ``mesure`` : sans effort non nul, le hash
    des mesures n'est jamais calculé."""
    return {'tva_rate': {'taux': 0.22}} if mesure != 'tva_rate' else {'csg': {'taux': 0.10}}


def _assert_aucun_echec(impacts, contexte):
    for annee in impacts:
        for mesure, data in annee.items():
            if isinstance(data, dict):
                assert not data.get(HANDLER_FAILED_KEY), \
                    f"{contexte} : {mesure} en échec — {data.get('erreur')}"


def _assert_identiques(attendu, obtenu, contexte):
    df_a, det_a, imp_a = attendu
    df_o, det_o, imp_o = obtenu
    pd.testing.assert_frame_equal(df_a, df_o, check_exact=True, obj=contexte)
    pd.testing.assert_frame_equal(det_a, det_o, check_exact=True, obj=contexte)
    assert imp_a == imp_o, f"{contexte} : impacts par mesure divergents"


def _verifier(avec_null, sans_cle, strict, caplog, contexte, jeton):
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        obtenu = _simuler(avec_null, strict)
    erreurs = [r.getMessage()[:160] for r in caplog.records if r.levelno >= logging.ERROR]
    assert not erreurs, f"{contexte} : ERROR loggé(s) {erreurs}"
    _assert_aucun_echec(obtenu[2], contexte)
    warnings = [r.getMessage() for r in caplog.records
                if r.levelno == logging.WARNING and r.getMessage().startswith('PARAM_NULL')]
    assert any(jeton in w for w in warnings), \
        f"{contexte} : WARNING PARAM_NULL attendu pour {jeton}, obtenu {warnings}"
    # Dédup : une seule ligne par (mesure, clé) sur toute la simulation, pas
    # une par année (c'est le bruit Sentry du constat de prod).
    assert sum(jeton in w for w in warnings) == 1, \
        f"{contexte} : WARNING non dédupliqué ({len(warnings)} lignes)"
    _assert_identiques(_simuler_reference(sans_cle, strict), obtenu, contexte)
    return obtenu


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
@pytest.mark.parametrize('mesure,param', PAIRES)
def test_null_equivaut_a_cle_absente_mesure_isolee(mesure, param, strict, caplog):
    _verifier({mesure: {param: None}}, {mesure: {}}, strict, caplog,
              f"{mesure}.{param}=None isolée", f"{mesure}.{param}=None")


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
@pytest.mark.parametrize('mesure,param', PAIRES)
def test_null_equivaut_a_cle_absente_toutes_mesures_presentes(mesure, param, strict, caplog):
    """Toutes les mesures présentes (à leurs défauts) : exerce les canaux
    latéraux qui lisent ``self.mesures`` brut pour une AUTRE mesure."""
    base = {m: {} for m in MESURES}
    _verifier({**base, mesure: {param: None}}, base, strict, caplog,
              f"{mesure}.{param}=None (toutes mesures)", f"{mesure}.{param}=None")


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
@pytest.mark.parametrize('mesure,param', PAIRES)
def test_null_equivaut_a_cle_absente_toutes_mesures_actives(mesure, param, strict, caplog):
    """Toutes les mesures DÉVIÉES : un canal latéral dont le consommateur est
    actif voit la valeur de la voisine. ``None`` = la clé retirée de CETTE
    base (pas le défaut d'une base vide) — c'est l'équivalence exacte."""
    avec_null = {m: dict(p) for m, p in BASE_ACTIVE.items()}
    avec_null.setdefault(mesure, {})[param] = None
    sans_cle = {m: {k: v for k, v in p.items() if (m, k) != (mesure, param)}
                for m, p in avec_null.items()}
    _verifier(avec_null, sans_cle, strict, caplog,
              f"{mesure}.{param}=None (toutes actives)", f"{mesure}.{param}=None")


def _assert_levier_absent_des_impacts(impacts, mesure, contexte):
    for annee in impacts:
        assert mesure not in annee, f"{contexte} : {mesure} présent dans les impacts"


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
@pytest.mark.parametrize('mesure', MESURES)
def test_bloc_null_equivaut_a_levier_absent_base_neutre(mesure, strict, caplog):
    """``{"levier": null}`` = levier ABSENT, avec une autre mesure ACTIVE —
    sans elle l'effort est nul et le hash des mesures (qui faisait tomber
    toute la simulation, et qui doit voir le bloc null comme absent) n'est
    jamais calculé."""
    actif = _autre_mesure_active(mesure)
    obtenu = _verifier({**actif, mesure: None}, actif, strict, caplog,
                       f"bloc {mesure}=None (base neutre)", f"{mesure}=None")
    _assert_levier_absent_des_impacts(obtenu[2], mesure, f"bloc {mesure}=None")


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
@pytest.mark.parametrize('mesure', MESURES)
def test_bloc_null_equivaut_a_levier_absent_toutes_actives(mesure, strict, caplog):
    """Toutes les AUTRES mesures déviées : les lecteurs latéraux de
    ``self.mesures`` brut (SMIC ← point d'indice, fraude ← ASU, effets
    d'offre, seniors, réforme FP, hash) ont un consommateur actif et doivent
    voir le bloc null exactement comme la clé retirée de cette base."""
    sans_levier = {m: dict(p) for m, p in BASE_ACTIVE.items() if m != mesure}
    _verifier({**sans_levier, mesure: None}, sans_levier, strict, caplog,
              f"bloc {mesure}=None (toutes actives)", f"{mesure}=None")


def test_inventaire_bloc_null_couvre_les_lecteurs_lateraux():
    """Anti-faux-vert : la base active doit contenir les leviers dont un
    lecteur latéral lit le bloc brut, sinon la propriété « toutes actives »
    ne les exercerait pas."""
    for levier in ('fonction_publique', 'asu', 'retraites', 'smic', 'fraude_sociale'):
        assert levier in BASE_ACTIVE and levier in MESURES, levier
    assert 'taxe_superprofits' in MESURES


@pytest.mark.parametrize('mesure', MESURES)
def test_journal_voit_le_bloc_null_comme_absent(mesure):
    """Lecteur latéral dont l'écart n'est PAS observable dans les résultats (la
    liste des leviers déviés n'est que journalisée) : la règle « bloc null =
    levier absent » y est vérifiée directement. (Le hash des mesures, second
    lecteur de ce type, a disparu en v0.6.7 : les impulsions budgétaires se
    lisent désormais dans les impacts, où un bloc null est déjà absent.)"""
    actif = _autre_mesure_active(mesure)
    avec_null = BudgetSimulatorV45(periods=1, mesures={**actif, mesure: None})
    sans = BudgetSimulatorV45(periods=1, mesures=dict(actif))
    assert avec_null.detect_active_measures() == sans.detect_active_measures()
    seul = BudgetSimulatorV45(periods=1, mesures={mesure: None})
    assert seul.detect_active_measures() == []


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
def test_taxe_superprofits_null_n_applique_pas_la_taxe(strict, caplog):
    """Cas nommé : ``{"taxe_superprofits": null}`` appliquait
    la taxe (25 % tous secteurs, comme ``{}``) alors que l'API annonce « clé
    absente ». ``null`` = levier absent ; ``{}`` garde son sens (le levier à
    ses défauts) — la distinction est vérifiée pour ne pas être neutralisée
    par accident."""
    df_null, _, imp_null = _verifier({'taxe_superprofits': None}, {}, strict, caplog,
                                     "taxe_superprofits=None", "taxe_superprofits=None")
    df_vide, _, _ = _simuler({'taxe_superprofits': {}}, strict)
    _assert_levier_absent_des_impacts(imp_null, 'taxe_superprofits', "taxe_superprofits=None")
    assert not df_null['Déficit/PIB %'].equals(df_vide['Déficit/PIB %']), \
        "{} doit rester le levier appliqué à ses défauts, distinct de null"


# --------------------------------------------------------------------------
# Canaux latéraux ACTIFS : la propriété à défauts ne voit pas une divergence
# de VALEUR quand le consommateur est lui-même à son point neutre.
# --------------------------------------------------------------------------

@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
@pytest.mark.parametrize('valeur_fp', [None, 'bloc_null'])
def test_smic_ne_herite_pas_d_un_null_de_fonction_publique(valeur_fp, strict, caplog):
    """Le SMIC lit ``fonction_publique.point_indice`` brut (anti-double
    comptage). Un null là-bas faisait échouer le SMIC lui-même."""
    smic = {'smic': {'montant_brut': 1900}}
    if valeur_fp == 'bloc_null':
        # Bloc null = levier ABSENT (et non `{}`).
        avec_null, sans = {**smic, 'fonction_publique': None}, smic
        jeton = 'fonction_publique=None'
    else:
        avec_null = {**smic, 'fonction_publique': {'point_indice': None}}
        sans = {**smic, 'fonction_publique': {}}
        jeton = 'fonction_publique.point_indice=None'
    _verifier(avec_null, sans, strict, caplog, f"smic + fonction_publique {valeur_fp}", jeton)


@pytest.mark.parametrize('strict', [False, True], ids=['tolerant', 'strict'])
def test_asu_null_n_est_pas_une_asu_fantome(strict, caplog):
    """``asu_is_active`` lit ``mesures['asu']`` brut : ``None != 0`` la
    déclarait ACTIVE alors que ``_apply_asu`` (défaut 0) n'émet rien — la
    fraude sociale perdait 30 % de son gisement pour une réforme jamais
    appliquée. Même classe que l'ASU fantôme NaN (v0.6.x)."""
    fraude = {'fraude_sociale': {'effort': 1.0}}
    _verifier({**fraude, 'asu': {'asu_activation': None}}, {**fraude, 'asu': {}},
              strict, caplog, "fraude_sociale + asu_activation=None", 'asu.asu_activation=None')


# --------------------------------------------------------------------------
# Unitaires de la porte
# --------------------------------------------------------------------------

@pytest.mark.parametrize('strict', [False, True])
def test_porte_retire_none_dans_les_deux_modes(strict, caplog):
    """None n'est pas une erreur à escalader (contrairement au NaN, poison de
    calcul) : c'est l'absence, déjà légitime en strict pour ``intensite``
    (``test_noop_when_intensite_is_none_preserves_legacy_path``). Retirée
    dans les deux modes, entrée appelante jamais mutée, WARNING dédupliqué."""
    params = {'indexation': None, 'age_depart': 63.0}
    warned = set()
    with caplog.at_level(logging.WARNING):
        out1 = validate_param_domains('retraites', params, strict=strict, warned=warned)
        out2 = validate_param_domains('retraites', params, strict=strict, warned=warned)
    assert out1 == out2 == {'age_depart': 63.0}
    assert params == {'indexation': None, 'age_depart': 63.0}, "entrée mutée"
    lignes = [r for r in caplog.records if 'PARAM_NULL' in r.getMessage()]
    assert len(lignes) == 1 and lignes[0].levelno == logging.WARNING


def test_porte_ne_touche_pas_une_entree_sans_null():
    """Byte-identité golden : aucune copie quand rien n'est retiré."""
    params = {'indexation': 1.0, 'age_depart': 63.0}
    assert validate_param_domains('retraites', params, strict=True) is params


@pytest.mark.parametrize('mesures', [
    {}, {'csg': None}, {'csg': [1]}, {'csg': 42}, {'csg': {}}, {'csg': {'taux': None}},
], ids=['levier_absent', 'bloc_null', 'bloc_liste', 'bloc_nombre', 'cle_absente', 'cle_null'])
def test_valeur_brute_rend_le_defaut_sans_valeur(mesures):
    """Accès partagé des lecteurs latéraux : toute forme de « pas de valeur »
    (et le bloc mal formé, neutre hors porte) rend le défaut."""
    assert valeur_brute(mesures, 'csg', 'taux', 0.092) == 0.092


def test_valeur_brute_rend_la_valeur_telle_quelle():
    """Valeur présente (même non finie ou non numérique) rendue sans filtre :
    la neutralisation reste au lecteur, comme documenté."""
    assert valeur_brute({'csg': {'taux': 0.1}}, 'csg', 'taux', 0.092) == 0.1
    assert math.isnan(valeur_brute({'csg': {'taux': math.nan}}, 'csg', 'taux', 0.092))
    assert valeur_brute({'csg': {'taux': 'x'}}, 'csg', 'taux', 0.092) == 'x'


def test_le_contrat_str_reste_un_echec_bruyant():
    """MIXIN_BAD_PARAMS n'est pas affaibli : une str n'est PAS un null."""
    with pytest.raises(TypeError):
        validate_param_domains('retraites', {'indexation': 'x'}, strict=False)


def test_nan_reste_escalade_en_strict():
    """La porte de finitude garde son contrat : NaN lève en strict."""
    with pytest.raises(ValueError, match='non fini'):
        validate_param_domains('csg', {'taux': math.nan}, strict=True)


@pytest.mark.parametrize('charge', [[1], 42, 'x'])
def test_bloc_mal_forme_echoue_bruyamment_sans_tomber_la_simulation(charge, caplog):
    """Décision verrouillée conservée : un bloc mal formé (≠ null) passe par
    le chemin tracé (ERROR + ``HANDLER_FAILED_KEY``). Mais la simulation
    entière ne doit plus lever (hash des mesures hors ``try`` → 500 API)."""
    mesures = {'impots_production': charge, 'tva_rate': {'taux': 0.22}}
    sim = BudgetSimulatorV45(periods=PERIODES, mesures=mesures)
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': ''}), caplog.at_level(logging.ERROR):
        df, _, rapport = sim.simulate()
    assert df['Dette/PIB %'].notna().all()
    assert any(r.levelno == logging.ERROR for r in caplog.records)
    assert any(annee.get('impots_production', {}).get(HANDLER_FAILED_KEY)
               for annee in rapport['measure_impacts_by_year'])
