"""Revue 2026-08-04 — domaines des paramètres NOMMÉS (PARAM_DOMAINS).

La symétrisation des handlers retraites/prestations remplace les if/elif
directionnels par de l'arithmétique uniforme : un NaN qui était neutralisé
PAR ACCIDENT (comparaisons toutes False → terme sauté) se propagerait
désormais jusqu'au DataFrame — déficit/dette NaN 2026-2035, aucun signal
(pas de HANDLER_FAILED, pas de CLIP, mesure absente de measure_impacts),
HTTP 500 opaque à la sérialisation. Prouvé en revue (silent-failure-hunter).
S'y ajoute la bande silencieuse hors-UI (indexation=-10 → -21 pts de dette,
HTTP 200, zéro trace).

Même philosophie et même contrat dual qu'INTENSITE_DOMAINS (Lot C Item 1) :
tolérant = warning PARAM_DOMAIN_CLAMP + clamp ; BUDGETLAB_STRICT =
ValueError → ExceptionGroup. Une `str` lève TOUJOURS TypeError (contrat
MIXIN_BAD_PARAMS préservé).
"""
import os
from unittest.mock import patch

import pytest

from budget_simulator.constants import PARAM_DOMAINS
from budget_simulator.engine._param_domain import validate_param_domains
from budget_simulator.simulator import BudgetSimulatorV45


# --------------------------------------------------------------------------
# Fonction pure
# --------------------------------------------------------------------------

def test_noop_for_measure_without_named_domains():
    """Mesure hors registre : params rendus tels quels (objet identique)."""
    params = {'taux': 999.0}
    out = validate_param_domains('tva_rate', params, strict=True)
    assert out is params


def test_noop_when_param_absent_or_none():
    """Paramètre absent ou None → no-op (les défauts du handler font foi)."""
    params = {'age_depart': 62.75}  # indexation/duree absents
    out = validate_param_domains('retraites', params, strict=True)
    assert out is params
    params_none = {'indexation': None}
    out_none = validate_param_domains('retraites', params_none, strict=True)
    assert out_none is params_none


def test_in_domain_values_return_same_object():
    """Valeurs légitimes (bornes incluses) → objet identique (golden
    master byte-identique sur toute entrée valide)."""
    params = {'age_depart': 60.0, 'indexation': 1.2, 'duree_cotisation': 45.0}
    out = validate_param_domains('retraites', params, strict=True)
    assert out is params


def test_nan_indexation_traite_hors_domaine():
    """NaN n'est ni < low ni > high : sans garde explicite il empoisonne
    toute la trajectoire en silence. Strict = ValueError, tolérant = copie
    défensive SANS la clé.

    Recalé le 2026-08-26 (clôture de la revue adverse) : le repli tolérant
    était « clamp à la borne basse », soit `indexation = 0.0` — le GEL TOTAL
    des pensions. Une valeur absente ne dit pas « trop bas », elle dit « pas
    de valeur » ; le seul repli qui n'invente pas une politique est le défaut
    du handler, obtenu en retirant la clé. Le clamp reste la règle pour les
    valeurs FINIES et aberrantes (test suivant), qui, elles, portent bien une
    direction."""
    nan = float('nan')
    params = {'indexation': nan}
    with pytest.raises(ValueError, match='non fini'):
        validate_param_domains('retraites', params, strict=True)
    out = validate_param_domains('retraites', params, strict=False)
    assert out is not params
    assert 'indexation' not in out


def test_hors_domaine_clampe_a_la_borne_la_plus_proche():
    """-10 → borne basse ; 100 → borne haute (tolérant)."""
    out_low = validate_param_domains('retraites', {'indexation': -10.0}, strict=False)
    assert out_low['indexation'] == 0.0
    out_high = validate_param_domains('retraites', {'indexation': 100.0}, strict=False)
    assert out_high['indexation'] == 1.2


def test_str_param_leve_toujours_typeerror():
    """LOAD-BEARING (contrat MIXIN_BAD_PARAMS) : une str lève TypeError au
    comparateur, dans les deux modes — jamais ValueError ni early-return."""
    for strict in (True, False):
        with pytest.raises(TypeError):
            validate_param_domains('retraites', {'indexation': 'abc'}, strict=strict)


def test_prestations_taux_indexation_couvert():
    """Le levier frère symétrisé le même jour est au registre lui aussi.
    Forme du registre : {measure_id: {param: (low, high)}} — lookup O(1)
    par mesure, aligné sur INTENSITE_DOMAINS (finition revue finale)."""
    assert 'taux_indexation' in PARAM_DOMAINS['prestations_indexation']
    out = validate_param_domains(
        'prestations_indexation', {'taux_indexation': -10.0}, strict=False)
    assert out['taux_indexation'] == 0.0


def test_warning_deduplique_par_simulation(caplog):
    """Finition revue finale : le clamp d'une même (mesure, param) hors
    domaine se journalise UNE fois par simulation, pas une fois par année
    simulée (mesuré avant : ~10 lignes WARNING pour une seule erreur —
    bruit pur pour Sentry Logs, l'info est identique chaque année)."""
    sim = BudgetSimulatorV45(mesures={'retraites': {'indexation': -10.0}})
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': ''}), \
         caplog.at_level('WARNING'):
        sim.simulate()
    clamps = [r for r in caplog.records if 'PARAM_DOMAIN_CLAMP' in r.message]
    assert len(clamps) == 1, f"{len(clamps)} warnings pour une seule erreur"
    # Et une 2e simulation sur la même instance ré-alerte (état par run).
    caplog.clear()
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': ''}), \
         caplog.at_level('WARNING'):
        sim.simulate()
    clamps2 = [r for r in caplog.records if 'PARAM_DOMAIN_CLAMP' in r.message]
    assert len(clamps2) == 1, "le reset par simulation doit ré-armer l'alerte"


# --------------------------------------------------------------------------
# Intégration (branchement orchestrateur)
# --------------------------------------------------------------------------

def test_nan_indexation_ne_pollue_plus_la_trajectoire(caplog):
    """Bout-en-bout tolérant : NaN → trajectoire ENTIÈREMENT finie + trace
    PARAM_DOMAIN_CLAMP (avant ce garde : déficit/dette NaN sans un signal)."""
    sim = BudgetSimulatorV45(mesures={'retraites': {'indexation': float('nan')}})
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': ''}), \
         caplog.at_level('WARNING'):
        df, _, _ = sim.simulate()
    assert df['Déficit/PIB %'].notna().all(), "trajectoire NaN = échec silencieux"
    assert df['Dette/PIB %'].notna().all()
    assert any('PARAM_NON_FINI' in rec.message for rec in caplog.records), \
        "le retrait doit laisser une trace filtrable (Sentry Logs)"


def test_strict_nan_escalade_en_exceptiongroup_valueerror():
    """Bout-en-bout strict : NaN → ExceptionGroup contenant un ValueError
    (synergie Lot C Item 3, aucune mécanique nouvelle)."""
    sim = BudgetSimulatorV45(mesures={'retraites': {'indexation': float('nan')}})
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1'}), \
         pytest.raises(ExceptionGroup) as excinfo:
        sim.simulate()
    inner = excinfo.value.exceptions
    assert len(inner) == 1 and isinstance(inner[0], ValueError)


# --------------------------------------------------------------------------
# PORTE DE FINITUDE — clôture revue phase 2 (2026-08-26)
# --------------------------------------------------------------------------
# La revue adverse du lot 9 a montré que le registre ci-dessus ne ferme le
# trou que LEVIER PAR LEVIER, alors que le mode de défaillance qu'il décrit
# (« un NaN … empoisonnerait toute la trajectoire sans signal ») est celui de
# la PORTE. Deux paramètres que le lot 9 vient précisément de rendre porteurs
# — `csg.taux` et `collectivites.dotation` — n'étaient pas au registre : un
# NaN les traversait, rendait déficit ET dette `nan` sur tout l'horizon, et
# ne levait rien MÊME sous BUDGETLAB_STRICT=1. Le durcissement du lot 7
# (`asu.asu_plafonnement`) avait été fait de la même façon, un levier à la
# fois : c'est la classe de correction qui laisse toujours le prochain levier
# ouvert.
#
# La garde de finitude est donc UNIVERSELLE : elle porte sur tout paramètre
# NUMÉRIQUE de toute mesure, qu'un domaine soit déclaré pour lui ou non.
# Elle ne remplace pas PARAM_DOMAINS (qui borne des valeurs FINIES mais
# aberrantes) : elle en est le socle.

# Cinq leviers, dont les trois que le lot 9 rend porteurs et deux qui n'ont
# et n'auront pas de domaine déclaré : la garde ne doit dépendre d'AUCUN
# registre, c'est tout son objet.
_LEVIERS = [
    ('csg', 'taux'),
    ('collectivites', 'dotation'),
    ('recherche_publique', 'budget'),
    ('fraude_fiscale', 'effort'),
    ('sante', 'prevention_budget'),
    ('retraites', 'indexation'),
]


@pytest.mark.parametrize('measure_id,param', _LEVIERS)
@pytest.mark.parametrize('valeur', [float('nan'), float('inf'), float('-inf')])
def test_valeur_non_finie_refusee_sur_tout_parametre_numerique(measure_id, param, valeur):
    """Aucun paramètre numérique ne peut porter NaN/±inf, domaine ou pas.

    Strict : ValueError. Tolérant : la clé est RETIRÉE (le handler retombe
    sur son défaut, c'est-à-dire sur le neutre) et le retrait est tracé —
    jamais clampée à une borne inventée, puisqu'aucune borne n'est déclarée
    pour ce paramètre."""
    with pytest.raises(ValueError, match='non fini'):
        validate_param_domains(measure_id, {param: valeur}, strict=True)
    out = validate_param_domains(measure_id, {param: valeur}, strict=False)
    assert param not in out, "le paramètre non fini doit être retiré, pas propagé"


@pytest.mark.parametrize('measure_id,param', [('csg', 'taux'),
                                              ('collectivites', 'dotation'),
                                              ('recherche_publique', 'budget')])
def test_strict_nan_hors_registre_escalade_bout_en_bout(measure_id, param):
    """Le trou tel qu'il a été mesuré : STRICT + NaN → aucune exception, et
    déficit/dette `nan` publiés. Ce test rougissait sur l'état livré."""
    sim = BudgetSimulatorV45(mesures={measure_id: {param: float('nan')}})
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': '1'}), \
         pytest.raises(ExceptionGroup):
        sim.simulate()


@pytest.mark.parametrize('measure_id,param', [('csg', 'taux'),
                                              ('collectivites', 'dotation'),
                                              ('recherche_publique', 'budget')])
def test_tolerant_nan_hors_registre_ne_pollue_pas_la_trajectoire(measure_id, param, caplog):
    """Contrat dual : en prod le service ne casse pas, mais il ne publie pas
    non plus une trajectoire NaN — et il laisse une trace filtrable."""
    sim = BudgetSimulatorV45(mesures={measure_id: {param: float('nan')}})
    with patch.dict(os.environ, {'BUDGETLAB_STRICT': ''}), \
         caplog.at_level('WARNING'):
        df, _, _ = sim.simulate()
    assert df['Déficit/PIB %'].notna().all(), "trajectoire NaN = échec silencieux"
    assert df['Dette/PIB %'].notna().all()
    assert any('PARAM_NON_FINI' in rec.message for rec in caplog.records)


def test_str_reste_typeerror_meme_hors_registre():
    """LOAD-BEARING : la porte de finitude ne doit PAS avaler une `str`.

    Contrat MIXIN_BAD_PARAMS — une `str` remonte en TypeError, elle ne
    devient ni un ValueError de domaine ni un retrait silencieux. La garde
    ne regarde donc que les valeurs déjà numériques."""
    with pytest.raises(TypeError):
        validate_param_domains('csg', {'taux': 'douze'}, strict=True)


def test_les_deux_parametres_rendus_porteurs_par_le_lot_9_sont_bornes():
    """`csg.taux` et `collectivites.dotation` ne sont plus seulement finis :
    ils sont BORNÉS, aux bornes que le registre public publie déjà
    (`policy_measures.json` : taux ∈ [0,08 ; 0,12], dotation ∈ [100 ; 140]).

    Sans borne, `csg.taux = True` (soit 1,0 — 100 % de CSG) était accepté en
    silence et rendait la dette 2030 à 112,9 % au lieu de 129,6 %."""
    assert PARAM_DOMAINS['csg']['taux'] == (0.08, 0.12)
    assert PARAM_DOMAINS['collectivites']['dotation'] == (95.0, 140.0)
    with pytest.raises(ValueError, match='hors domaine'):
        validate_param_domains('csg', {'taux': True}, strict=True)


def test_les_bornes_contiennent_ui_et_scenarios_publies():
    """Source unique : un domaine moteur n'est pas un second jeu de valeurs
    à maintenir à la main. Il doit CONTENIR (a) le `min`/`max` que
    `policy_measures.json` publie pour le même paramètre — c'est ce que
    l'utilisateur peut poser depuis l'UI — et (b) toute valeur que les
    scénarios publiés posent réellement. Un domaine plus étroit que l'un des
    deux clamperait en silence quelque chose que le site sert déjà.

    Il en sort une divergence PRÉ-EXISTANTE, qui est la raison d'être de la
    seconde assertion : `im_competitivite_2029` pose
    `collectivites.dotation = 95` alors que le registre public annonce un
    minimum de 100. Le scénario est servi, la borne d'UI est publiée, et les
    deux se contredisent depuis avant ce lot."""
    import json
    import pathlib
    racine = pathlib.Path(__file__).resolve().parent.parent
    registre = {m['id']: m for m in json.loads(
        (racine / 'policy_measures.json').read_text(encoding='utf-8'))['mesures']}
    for measure_id, domaines in PARAM_DOMAINS.items():
        parametres = registre.get(measure_id, {}).get('parametres', {})
        for param, (low, high) in domaines.items():
            publie = parametres.get(param)
            if publie is None or publie.get('min') is None:
                continue  # paramètre non exposé à l'UI : borne moteur seule
            assert low <= float(publie['min']) and high >= float(publie['max']), (
                f"{measure_id}.{param} : domaine moteur {(low, high)} plus "
                f"étroit que la borne d'UI publiée "
                f"({publie['min']}, {publie['max']}) — l'utilisateur peut "
                f"poser une valeur que le moteur clampe en silence")


def test_les_bornes_couvrent_tous_les_scenarios_publies():
    """Aucun scénario servi ne doit être clampé par un domaine.

    Cette garde est le pendant du golden master pour les BORNES : sans elle,
    resserrer un domaine déplacerait une trajectoire publiée par le clamp,
    et le seul signe serait une ligne WARNING dans les logs de production."""
    import json
    import pathlib
    chemin = None
    env = (os.environ.get('BUDGETLAB_SCENARIOS_JSON') or '').strip()
    racine = pathlib.Path(__file__).resolve().parent.parent
    for candidat in ([pathlib.Path(env)] if env else []) + [
            racine / '..' / '..' / 'frontend-react' / 'src' / 'data' / 'scenarios.json']:
        if candidat.exists():
            chemin = candidat
            break
    if chemin is None:
        pytest.skip("scenarios.json introuvable (fork moteur public seul)")
    scenarios = json.loads(chemin.read_text(encoding='utf-8'))
    for nom, contenu in scenarios.items():
        for measure_id, params in (contenu.get('apiMeasures') or {}).items():
            for param, (low, high) in PARAM_DOMAINS.get(measure_id, {}).items():
                valeur = params.get(param)
                if valeur is None:
                    continue
                assert low <= valeur <= high, (
                    f"{nom}.{measure_id}.{param}={valeur} hors du domaine "
                    f"moteur [{low}, {high}] : ce scénario est SERVI et se "
                    f"ferait clamper")
