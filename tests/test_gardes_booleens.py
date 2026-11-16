"""Gardes d'entrée : un booléen n'est pas un nombre, un nombre n'est pas un booléen.

Deux entrées passaient la porte des valeurs sans trace (`report.valid: true`) :

- ``{"fonction_publique": {"effectifs": true}}`` : Python compare ``True`` comme 1,
  donc dans le domaine [−500 000 ; 140 000] — un poste créé, en silence. Même chose
  pour toute quantité (``isf_climatique.intensite: true`` = ISF complet,
  ``fraude_fiscale.effort: true`` = effort maximal).
- ``{"chomage_alloc": {"degressivite": 5}}`` : le paramètre est déclaré booléen
  (``policy_measures.json``, ``type: boolean``), le handler le lit par sa
  vérité, donc 5 (ou 0,5, ou −1) active la dégressivité, en silence.

Contrat posé, par PROPRIÉTÉ sur le registre public et non levier par levier :

1. Sur un paramètre NUMÉRIQUE borné (``PARAM_DOMAINS``, ``INTENSITE_DOMAINS``) qui
   n'est pas un interrupteur 0/1, un booléen est une valeur non numérique :
   ``ValeurNonNumerique``, comme une chaîne (contrat MIXIN_BAD_PARAMS : levier en
   échec, compté nul, ``report.valid = false`` en tolérant ; ``ExceptionGroup`` en
   strict).
2. Sur un INTERRUPTEUR 0/1 (registre : ``type: toggle``, ou min 0, max 1, pas 1), un
   booléen reste lu comme 0/1, comme avant (identique au bit).
3. Sur un paramètre BOOLÉEN (registre : ``type: boolean``), seules les valeurs
   ``true``/``false``/0/1 sont admises, avec le comportement d'avant ; toute autre
   valeur numérique est hors domaine : ``ValeurInvalide`` en strict, et en tolérant
   la clé est retirée (le levier applique son défaut) avec une correction
   (``report.valid = false``) — aucune valeur de repli inventée. Une chaîne est une
   valeur non numérique (comme pour un nombre).

Aucune entrée valide ne change : les scénarios publiés et le golden master sont
identiques au bit (``tests/test_golden_master_full.py``).
"""
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

import budget_simulator.constants as C
from budget_simulator.constants import INTENSITE_DOMAINS, PARAM_DOMAINS, POLICY_MEASURES_PATH
from budget_simulator.engine._param_domain import (
    ValeurInvalide,
    ValeurNonNumerique,
    validate_intensite_domain,
    validate_param_domains,
)
from budget_simulator.simulator import BudgetSimulatorV45

ROOT = Path(__file__).absolute().parent.parent
# Lus par attribut : le test d'existence ci-dessous échoue si l'un manque.
PARAM_BOOLEENS = getattr(C, 'PARAM_BOOLEENS', {})
PARAM_INTERRUPTEURS = getattr(C, 'PARAM_INTERRUPTEURS', {})
_REGISTRE = json.loads(POLICY_MEASURES_PATH.read_text(encoding='utf-8'))


def _simuler(mesures, strict=False):
    env = {'BUDGETLAB_STRICT': '1'} if strict else {}
    with patch.dict(os.environ, env, clear=False):
        if not strict:
            os.environ.pop('BUDGETLAB_STRICT', None)
        sim = BudgetSimulatorV45(periods=6, mesures=mesures, annee_debut=2028)
        return sim.simulate()


def _dette(df):
    return [float(v) for v in df['Dette/PIB %'].tolist()]


# ---------------------------------------------------------------------------
# Registres dérivés du registre public (jamais une liste à la main)
# ---------------------------------------------------------------------------

def test_registres_derives_du_registre_public():
    """Interrupteurs et booléens viennent de ``policy_measures.json`` : type
    ``boolean`` d'un côté, ``toggle`` ou (min 0, max 1, pas 1) de l'autre."""
    attendus_bool, attendus_inter = {}, {}
    for mesure in _REGISTRE['mesures']:
        for param, spec in (mesure.get('parametres') or {}).items():
            if spec.get('type') == 'boolean':
                attendus_bool.setdefault(mesure['id'], set()).add(param)
            elif spec.get('type') == 'toggle' or (
                    spec.get('min') == 0 and spec.get('max') == 1 and spec.get('step') == 1):
                attendus_inter.setdefault(mesure['id'], set()).add(param)
    assert hasattr(C, 'PARAM_BOOLEENS') and hasattr(C, 'PARAM_INTERRUPTEURS')
    assert {k: set(v) for k, v in PARAM_BOOLEENS.items()} == attendus_bool
    assert {k: set(v) for k, v in PARAM_INTERRUPTEURS.items()} == attendus_inter
    # Repères lus dans le registre au 16/11/2026.
    assert 'degressivite' in PARAM_BOOLEENS['chomage_alloc']
    assert 'progressive' in PARAM_INTERRUPTEURS['csg']
    assert 'effectifs' not in PARAM_INTERRUPTEURS.get('fonction_publique', set())


def _quantites():
    """(mesure, paramètre) numériques bornés qui ne sont pas des interrupteurs."""
    paires = [(m, p) for m, params in PARAM_DOMAINS.items() for p in params
              if p not in PARAM_INTERRUPTEURS.get(m, set())]
    return sorted(paires)


# ---------------------------------------------------------------------------
# 1. Booléen sur une quantité : refusé comme une chaîne
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('measure_id,param', _quantites())
@pytest.mark.parametrize('valeur', [True, False])
@pytest.mark.parametrize('strict', [True, False])
def test_booleen_sur_quantite_refuse(measure_id, param, valeur, strict):
    with pytest.raises(ValeurNonNumerique, match='booléen'):
        validate_param_domains(measure_id, {param: valeur}, strict=strict)


@pytest.mark.parametrize('measure_id', sorted(INTENSITE_DOMAINS))
@pytest.mark.parametrize('strict', [True, False])
def test_booleen_sur_intensite_refuse(measure_id, strict):
    with pytest.raises(ValeurNonNumerique, match='booléen'):
        validate_intensite_domain(measure_id, {'intensite': True}, strict=strict)


def test_effectifs_true_bout_en_bout():
    """Le cas de l'audit : tolérant = levier en échec, compté nul, résultat
    invalidé, exactement comme une chaîne (contrat MIXIN_BAD_PARAMS : le levier
    en échec reste présent dans le programme, donc pas forcément identique au
    levier absent) ; strict = ExceptionGroup."""
    df_chaine, _, _ = _simuler({'fonction_publique': {'effectifs': 'x'}})
    df, _, rapport = _simuler({'fonction_publique': {'effectifs': True}})
    assert rapport['valid'] is False
    assert any('booléen' in w for w in rapport['warnings'])
    assert _dette(df) == _dette(df_chaine)
    with pytest.raises(ExceptionGroup):
        _simuler({'fonction_publique': {'effectifs': True}}, strict=True)


# ---------------------------------------------------------------------------
# 2. Interrupteurs 0/1 : un booléen reste lu comme 0/1 (identique au bit)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('measure_id,param', sorted(
    (m, p) for m, params in PARAM_INTERRUPTEURS.items() for p in params))
def test_interrupteur_accepte_le_booleen(measure_id, param):
    params = {param: True}
    assert validate_param_domains(measure_id, params, strict=True) is params


def test_csg_progressive_true_identique_a_1():
    df_true, _, r_true = _simuler({'csg': {'progressive': True}})
    df_un, _, r_un = _simuler({'csg': {'progressive': 1}})
    assert r_true['valid'] is True
    assert _dette(df_true) == _dette(df_un)


# ---------------------------------------------------------------------------
# 3. Paramètres booléens : {true, false, 0, 1} seulement
# ---------------------------------------------------------------------------

def _booleens():
    return sorted((m, p) for m, params in PARAM_BOOLEENS.items() for p in params)


@pytest.mark.parametrize('measure_id,param', _booleens())
@pytest.mark.parametrize('valeur', [True, False, 0, 1, 0.0, 1.0])
def test_booleen_valeurs_admises_inchangees(measure_id, param, valeur):
    params = {param: valeur}
    assert validate_param_domains(measure_id, params, strict=True) is params


@pytest.mark.parametrize('measure_id,param', _booleens())
@pytest.mark.parametrize('valeur', [5, 0.5, -1, 2.0])
def test_booleen_hors_domaine(measure_id, param, valeur):
    with pytest.raises(ValeurInvalide, match='booléen'):
        validate_param_domains(measure_id, {param: valeur}, strict=True)
    corrections = {}
    out = validate_param_domains(measure_id, {param: valeur, 'autre': 1}, strict=False,
                                 corrections=corrections)
    assert out == {'autre': 1}  # clé retirée : le levier applique son défaut
    assert any('booléen' in texte for texte in corrections.values())


@pytest.mark.parametrize('measure_id,param', _booleens())
def test_booleen_chaine_refusee(measure_id, param):
    for strict in (True, False):
        with pytest.raises(ValeurNonNumerique):
            validate_param_domains(measure_id, {param: 'oui'}, strict=strict)


def test_degressivite_5_bout_en_bout():
    """Le cas de l'audit : tolérant = trajectoire de la clé absente (défaut :
    pas de dégressivité), résultat invalidé ; strict = ExceptionGroup. Les
    valeurs admises gardent leur effet d'avant (True ≡ 1)."""
    df_abs, _, _ = _simuler({'chomage_alloc': {'duree': 18}})
    df5, _, r5 = _simuler({'chomage_alloc': {'duree': 18, 'degressivite': 5}})
    assert r5['valid'] is False
    assert any('booléen' in w for w in r5['warnings'])
    assert _dette(df5) == _dette(df_abs)
    with pytest.raises(ExceptionGroup):
        _simuler({'chomage_alloc': {'duree': 18, 'degressivite': 5}}, strict=True)
    df_true, _, r_true = _simuler({'chomage_alloc': {'duree': 18, 'degressivite': True}})
    df_un, _, _ = _simuler({'chomage_alloc': {'duree': 18, 'degressivite': 1}})
    assert r_true['valid'] is True
    assert _dette(df_true) == _dette(df_un)
    assert _dette(df_true) != _dette(df_abs)  # la dégressivité a bien un effet


# ---------------------------------------------------------------------------
# 4. Lecteurs latéraux alignés : un booléen refusé est neutre PARTOUT
# ---------------------------------------------------------------------------
# Plusieurs canaux lisent `self.mesures` BRUT, hors de la porte (offre et chômage
# des seniors, point d'indice lu par le SMIC, ISF lu par l'impôt plancher, IS lu
# par les bénéfices récupérés, effet d'offre, conditions des exclusions
# mutuelles). Règle d'alignement (`_seniors.retraites_ecart_age_ans_moteur`) : ce
# qui fait LEVER la porte est neutre dans ces canaux. Propriété : pour chaque
# quantité bornée, un booléen donne EXACTEMENT la trajectoire d'une chaîne (les
# deux font échouer le levier), avec les leviers qui la lisent latéralement.

_VOISINS = {  # un lecteur latéral neutre pour une chaîne comme pour un booléen
    ('fonction_publique', 'point_indice'): {'smic': {'montant_brut': 1900.0}},
    ('fiscalite_patrimoine', 'intensite'): {'droits_succession': {'variation': 5.0}},
    # Effet d'offre : un levier refusé ne doit pas éteindre celui d'un AUTRE levier.
    ('recherche_publique', 'budget'): {'collectivites': {'investissement': 10.0}},
    ('collectivites', 'investissement'): {'recherche_publique': {'budget': 20.0}},
}


def _toutes_quantites():
    paires = set(_quantites()) | {(m, 'intensite') for m in INTENSITE_DOMAINS}
    return sorted(paires)


@pytest.mark.parametrize('measure_id,param', _toutes_quantites())
def test_booleen_neutre_comme_une_chaine_dans_tous_les_canaux(measure_id, param):
    voisins = _VOISINS.get((measure_id, param), {})
    df_b, _, r_b = _simuler({measure_id: {param: True}, **voisins})
    df_s, _, r_s = _simuler({measure_id: {param: 'x'}, **voisins})
    assert r_b['valid'] is False and r_s['valid'] is False
    for col in df_b.columns:
        assert df_b[col].tolist() == df_s[col].tolist(), f'{measure_id}.{param} : colonne {col}'


@pytest.mark.parametrize('levier,param,neutre,lecteur', [
    ('isf_climatique', 'intensite', 0.0, {'impot_plancher_patrimoine': {'taux': 0.02}}),
    ('impot_societes', 'taux', 0.25, {'multinationales': {'benefices_recuperes': 5.0}}),
])
def test_booleen_lu_comme_le_levier_au_neutre_par_ses_lecteurs(levier, param, neutre, lecteur):
    """L'impôt plancher lit l'intensité de l'ISF (imputation), les bénéfices
    récupérés lisent le taux d'IS. Un booléen fait échouer le levier lu (compté
    nul) : son lecteur le voit au neutre, et non à 1 (avant : ISF complet imputé
    sur le plancher, pendant que l'ISF n'était plus compté)."""
    df_b, _, r_b = _simuler({levier: {param: True}, **lecteur})
    df_n, _, _ = _simuler({levier: {param: neutre}, **lecteur})
    assert r_b['valid'] is False
    for col in df_b.columns:
        assert df_b[col].tolist() == df_n[col].tolist(), f'{levier}.{param} : colonne {col}'
