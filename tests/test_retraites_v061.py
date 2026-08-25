"""Tests-propriétés v0.6.1 — retraites : barème d'âge PLAT et SYMÉTRIQUE (I1)
+ référence d'âge = CALENDRIER LÉGAL, plus une valeur figée (I3).

Contexte (dossier de sourcing v0.6.1, § I1 à I5) :

- **I1** — le barème à 2 segments de la v0.6.0 (14,2 Md€/an sous 64 ans, 6,0
  au-delà) reposait sur une **collision numérique** entre deux « 17,7 Md€ »
  sans rapport : celui du Sénat (rapport n° 498 (2023-2024) — produit BRUT
  âge + accélération Touraine, système de retraites, 2030, euros courants,
  montée en charge partielle) et celui de la Cour des comptes (février 2025,
  tableau n° 6 p. 72 — UNE année d'âge, toutes APU, 2035, euros constants
  2024, montée en charge complète). Les deux sources primaires qui chiffrent
  réellement une année d'âge convergent au dixième sur **6,0 Md€** de moindres
  dépenses (DG Trésor, doc n° 12 de la séance plénière du COR du 27/01/2022,
  diapositive 5 ; Cour des comptes, février 2025, T6 p. 72).

- **I3** — la référence figée à 62,75 ans faisait payer (ou créditait) aux
  programmes un écart au droit en vigueur qui est **déjà dans la baseline** :
  la LFSS 2026 suspend l'AOD à 62 ans 9 mois jusqu'au 1er janvier 2028
  SEULEMENT, et le tendanciel de la mission IGF (juillet 2026) sur lequel la
  baseline du moteur est calée intègre la reprise vers 64 ans.

Arbitrage du propriétaire (25/08/2026) — **symétrie stricte** : 6,0 Md€ par
année d'âge dans les DEUX sens. Le facteur d'asymétrie 0,70 (mesuré sur le
seul palier 64→63) est rejeté : rien ne le valide de 62 vers 60, et il
allègerait mécaniquement le coût affiché des programmes d'abaissement de
l'âge — c'est-à-dire prendrait parti (cf. § C.3 du dossier).

NB périmètre : ce fichier ne couvre QUE le canal des moindres dépenses de
pension. Le canal emploi (PIB, chômage, fuite sociale) est livré par le lot 3
et testé dans ``tests/test_emploi_seniors_v061.py`` — d'où l'absence
délibérée, ici, de tout test « aucun effet PIB / chômage ».

MAJ lot 3 : le handler émet désormais l'économie NETTE de la fuite sociale
résiduelle (9,6 %). Les propriétés de ce fichier — platitude, symétrie
stricte, constance du marginal, calendrier légal — sont toutes invariantes
par ce facteur multiplicatif uniforme ; seule la valeur absolue attendue du
test de niveau a été recalée, à partir des DEUX constantes.
"""
import ast
import inspect
import re
import textwrap
from pathlib import Path

import pytest

from budget_simulator.constants import (
    FUITE_SOCIALE_RESIDUELLE,
    PARAM_DOMAINS,
    PHASING_RETRAITES_5ANS,
    POLICY_START_YEAR,
    RETRAITES_COEFF_AGE_MD_EUR,
    RETRAITES_REF_AGE_ANS,
    RETRAITES_REF_AGE_CIBLE_ANS,
    retraites_ref_age_ans,
)
from budget_simulator.config import load_default_values
from budget_simulator.simulator import BudgetSimulatorV45

_GDP, _INFLATION, _UNEMP = 3000.0, 0.015, 0.075

# Première année où le phasing cohortes 5 ans vaut 1,0 (plein régime).
PLEIN_REGIME = POLICY_START_YEAR + PHASING_RETRAITES_5ANS.index(1.00)
# Dernière année de l'horizon publié (2025 + 10 périodes).
DERNIERE_ANNEE = 2035


def _delta_age(age: float, year: int = PLEIN_REGIME) -> float:
    """Impact dépenses du handler retraites (Md€, négatif = économie)."""
    sim = BudgetSimulatorV45(mesures={})
    delta, _, _ = sim._apply_retraites(
        {}, {'age_depart': age}, year, _GDP, _INFLATION, _UNEMP
    )
    return delta


def _economie(ecart_ans: float, year: int = PLEIN_REGIME) -> float:
    """Économie brute (Md€, POSITIF = économie) pour un écart d'âge donné
    par rapport à la référence légale de l'année."""
    return -_delta_age(retraites_ref_age_ans(year) + ecart_ans, year)


# --- I1 : barème plat et strictement symétrique ---------------------------


def test_bareme_plat_une_annee_dage_vaut_le_coefficient_unique():
    """Une année d'âge = RETRAITES_COEFF_AGE_MD_EUR BRUT à plein régime.

    Sources primaires convergentes : DG Trésor (COR 27/01/2022, doc n° 12,
    diapo 5) −0,4 pt de PIB pour 2 ans = 0,20 pt/an × 2 991 Md€ = 5,98 Md€ ;
    Cour des comptes 02/2025, T6 p. 72 = 6,0 Md€ (4,3 base + 1,7 complémentaires).

    RECALIBRATION v0.6.1 lot 3 : le handler émet désormais l'économie NETTE
    de la fuite sociale résiduelle (I9 — 9,6 % des économies brutes partent en
    indemnités journalières et minima sociaux). Le coefficient BRUT reste
    verrouillé sur les deux sources : l'attendu est construit à partir des
    deux constantes, il suit donc un recalibrage de l'une comme de l'autre.
    """
    attendu = RETRAITES_COEFF_AGE_MD_EUR * (1 - FUITE_SOCIALE_RESIDUELLE)
    assert _economie(1.0) == pytest.approx(attendu, abs=1e-9)


@pytest.mark.parametrize("ecart", [0.25, 1.0, 2.75])
def test_symetrie_stricte_du_levier_dage(ecart):
    """economie(ref + x) == -economie(ref - x) : arbitrage C1 du 25/08/2026.

    Le seul choix qui ne demande pas de prendre parti — un coefficient plus
    faible à la baisse allègerait le coût affiché des programmes d'abaissement
    de l'âge, un coefficient plus élevé les alourdirait (§ C.3 du dossier).
    """
    assert _economie(ecart) == pytest.approx(-_economie(-ecart), abs=1e-9)


def test_bareme_plat_sur_tout_le_domaine_ui():
    """Aucune rupture de pente sur [60 ; 67] : le rendement marginal d'une
    année d'âge est constant sur tout le domaine `PARAM_DOMAINS`.

    La falaise de −58 % à 64 ans de la v0.6.0 venait entièrement du premier
    segment erroné, pas d'un phénomène sourcé. Au-delà de 65 ans, prolonger
    le palier est un CHOIX ASSUMÉ (aucune source consultée ne chiffre 65→66
    ni 66→67 — § B.1 point 1 du dossier), déclaré dans METHODOLOGIE.md.
    """
    borne_basse, borne_haute = PARAM_DOMAINS['retraites']['age_depart']
    ages = [borne_basse + i * 0.5 for i in range(int((borne_haute - borne_basse) / 0.5) + 1)]
    marginaux = [
        _delta_age(a2) - _delta_age(a1) for a1, a2 in zip(ages, ages[1:])
    ]
    assert marginaux == pytest.approx([marginaux[0]] * len(marginaux), abs=1e-9)


def test_borne_haute_de_plausibilite_une_annee_dage():
    """Contre-épreuve Cour des comptes 02/2025, T6 p. 72 : une année d'âge
    rapporte au plus 8,4 Md€ toutes APU (6,0 de moindres dépenses + 2,4 de
    cotisations). Le canal cotisations n'est PAS dans le handler (arbitrage
    C2 : il naîtra du canal PIB/emploi), donc le handler seul doit rester
    strictement sous ce plafond.
    """
    assert _economie(1.0) <= 8.4


def test_borne_basse_surcout_dun_abaissement_de_2_75_annees():
    """Un abaissement de 2,75 années sous la référence légale coûte entre
    11,6 et 20,6 Md€/an à plein régime — bande de sensibilité publiée
    (§ I1 du dossier) : borne basse = variante asymétrique Cour (4,2 Md€/an),
    borne haute = périmètre solde du système de retraites (7,5 Md€/an).
    """
    surcout = -_economie(-2.75)
    assert 11.6 <= surcout <= 20.6


# --- I3 : la référence suit le calendrier légal ---------------------------


@pytest.mark.parametrize("year", range(POLICY_START_YEAR, DERNIERE_ANNEE + 1))
def test_statu_quo_neutre_sur_tous_les_millesimes(year):
    """`age_depart = ref(année)` ⇒ impact dépenses NUL, chaque année.

    C'est la propriété que la référence figée violait : à partir de 2028 elle
    créditait (ou faisait payer) un écart au droit en vigueur déjà présent
    dans la baseline — double comptage pur.
    """
    assert _delta_age(retraites_ref_age_ans(year), year) == pytest.approx(0.0, abs=1e-9)


def test_calendrier_legal_post_lfss_2026():
    """AOD gelé à 62 ans 9 mois jusqu'au 1er janvier 2028, puis reprise de la
    montée en charge de la réforme 2023 (+3 mois par génération) jusqu'à
    64 ans, atteints en 2032 (LFSS 2026 ; OFCE, billet du 29/01/2026)."""
    assert retraites_ref_age_ans(2026) == pytest.approx(RETRAITES_REF_AGE_ANS)
    assert retraites_ref_age_ans(2027) == pytest.approx(RETRAITES_REF_AGE_ANS)
    assert retraites_ref_age_ans(2028) == pytest.approx(63.00)
    assert retraites_ref_age_ans(2029) == pytest.approx(63.25)
    assert retraites_ref_age_ans(2030) == pytest.approx(63.50)
    assert retraites_ref_age_ans(2031) == pytest.approx(63.75)
    assert retraites_ref_age_ans(2032) == pytest.approx(RETRAITES_REF_AGE_CIBLE_ANS)


def test_calendrier_legal_monotone_et_plafonne():
    """Monotone non décroissant, jamais au-dessus de la cible légale : aucun
    millésime hors table ne peut faire dériver la référence."""
    valeurs = [retraites_ref_age_ans(y) for y in range(2020, 2061)]
    assert valeurs == sorted(valeurs)
    assert max(valeurs) == pytest.approx(RETRAITES_REF_AGE_CIBLE_ANS)
    assert min(valeurs) == pytest.approx(RETRAITES_REF_AGE_ANS)


def test_maintien_a_64_ans_ne_rapporte_plus_rien_une_fois_le_calendrier_atteint():
    """Un programme « je maintiens 64 ans » n'est plus crédité d'une économie
    que la loi produit déjà : positif tant que le calendrier n'y est pas
    (accélération réelle), nul à partir de 2032."""
    assert _delta_age(RETRAITES_REF_AGE_CIBLE_ANS, POLICY_START_YEAR) < 0
    for year in range(2032, DERNIERE_ANNEE + 1):
        assert _delta_age(RETRAITES_REF_AGE_CIBLE_ANS, year) == pytest.approx(0.0, abs=1e-9)


def test_defaut_de_config_aligne_sur_le_calendrier_de_lannee_de_depart():
    """Le défaut affiché (curseur UI, `/scenarios` de l'API) est l'âge légal
    de l'année où les politiques démarrent — sinon le « statu quo » de
    l'interface ne serait pas le statu quo du moteur."""
    assert load_default_values()['retraites']['age_depart'] == pytest.approx(
        retraites_ref_age_ans(POLICY_START_YEAR)
    )


# --- Méta-gardes : aucun coefficient d'âge en dur, aucune citation fausse --


_RACINE = Path(__file__).resolve().parent.parent
_PACKAGE = _RACINE / "budget_simulator"

# Valeurs de calibration du barème d'âge (barème actuel, barèmes retirés et
# bornes de la bande de sensibilité) + toutes les références d'âge du
# calendrier légal. Aucune ne doit apparaître en littéral hors constants.py.
_VALEURS_CALIBRATION_AGE = {
    4.2, 6.0, 7.5, 14.2, 16.0,           # coefficients Md€ par année d'âge
    60.0, 62.0, 62.75, 63.0, 63.25,      # références / seuils d'âge
    63.5, 63.75, 64.0, 65.0, 66.0, 67.0,
}


def test_meta_garde_aucun_litteral_de_coefficient_dage_dans_le_handler():
    """Le handler retraites ne porte AUCUN littéral de calibration d'âge :
    tout vient de constants.py (source unique, chaque valeur avec sa source
    primaire exacte). Sans ce verrou, un recalibrage peut être appliqué à
    moitié — c'est le mode de défaillance de la dérive ×2 du 04/08/2026."""
    from budget_simulator.handlers.depenses import DepensesMixin

    source = inspect.getsource(DepensesMixin._apply_retraites)
    arbre = ast.parse(textwrap.dedent(source))
    litteraux = {
        noeud.value
        for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.Constant)
        and isinstance(noeud.value, (int, float))
        and not isinstance(noeud.value, bool)
    }
    interdits = {v for v in litteraux if float(v) in _VALEURS_CALIBRATION_AGE}
    assert not interdits, (
        f"littéraux de calibration d'âge en dur dans _apply_retraites : {sorted(interdits)} "
        "— toute constante de calibration vit dans budget_simulator/constants.py"
    )
    assert "RETRAITES_COEFF_AGE_MD_EUR" in source
    # v0.6.1 lot 3 : la référence légale n'est plus lue directement par le
    # handler — elle vient de la SOURCE UNIQUE `_seniors.retraites_ecart_age_ans`,
    # partagée avec les canaux macro (offre de travail, bosse de chômage).
    # Sans partage, un recalibrage du calendrier n'atteindrait qu'un canal.
    assert "retraites_ecart_age_ans" in source

    # Contre-épreuve COMPORTEMENTALE de la source unique (la garde de source
    # ci-dessus est syntaxique) : l'écart vu par le handler et celui vu par le
    # moteur coïncident sur tout le domaine UI et tout l'horizon.
    from budget_simulator._seniors import (
        retraites_ecart_age_ans,
        retraites_ecart_age_ans_moteur,
    )

    borne_basse, borne_haute = PARAM_DOMAINS['retraites']['age_depart']
    for annee in range(POLICY_START_YEAR, POLICY_START_YEAR + 10):
        for age in (borne_basse, 62.75, 64.0, borne_haute):
            assert retraites_ecart_age_ans({'age_depart': age}, annee) == pytest.approx(
                retraites_ecart_age_ans_moteur({'retraites': {'age_depart': age}}, annee),
                abs=1e-12,
            )


def test_meta_garde_aucun_litteral_des_baremes_retires_dans_le_package():
    """Les coefficients retirés (14,2 Md€/an du barème Sénat mal attribué,
    16,0 Md€/an linéaire de la v0.5.1) n'existent plus comme VALEUR calculée
    nulle part dans le moteur. Les commentaires qui expliquent leur retrait
    restent volontairement lisibles : c'est l'historique qu'un auditeur
    externe doit pouvoir suivre."""
    retires = {14.2, 16.0}
    survivances = []
    for chemin in sorted(_PACKAGE.rglob("*.py")):
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if (isinstance(noeud, ast.Constant)
                    and isinstance(noeud.value, float)
                    and noeud.value in retires):
                survivances.append(
                    f"{chemin.relative_to(_RACINE)}:{noeud.lineno} → {noeud.value}"
                )
    assert not survivances, (
        f"un coefficient d'âge retiré subsiste en littéral : {survivances}"
    )


# Le fichier de garde cite lui-même les motifs qu'il traque (docstrings) :
# exclusion explicite et documentée, sans quoi le verrou se déclencherait
# sur sa propre justification.
_FICHIER_DE_GARDE = Path(__file__).name


def _fichiers_a_auditer():
    """Code du moteur + docs publiées + tests, hors fichier de garde."""
    for chemin in list(_PACKAGE.rglob("*.py")) + list((_RACINE / "docs").glob("*.md")) \
            + list((_RACINE / "tests").glob("*.py")):
        if chemin.name != _FICHIER_DE_GARDE:
            yield chemin


def test_meta_garde_aucune_seance_du_cor_a_une_date_inexistante():
    """Il n'existe PAS de séance plénière du COR le 19 mars 2026 : cette date
    est celle de la fuite presse (Le Monde, 18/03), la séance est celle du
    **26 mars 2026** (URL des documents `.../2026-04/Doc_03_..._26032026...`,
    page « Réunion du Conseil du 26 mars 2026 »). Verrou de citation sur un
    repo public — même mode de défaillance que le « rapport Matignon »
    corrigé en v0.6.0."""
    motif = re.compile(r"19[/ -]0?3[/ -]2026|19\s+mars\s+2026")
    fautifs = [
        str(c.relative_to(_RACINE)) for c in _fichiers_a_auditer()
        if motif.search(c.read_text(encoding="utf-8"))
    ]
    assert not fautifs, (
        f"citation d'une séance du COR à une date inexistante dans : {fautifs}"
    )


def test_meta_garde_aucune_attribution_cour_2021_introuvable():
    """L'attribution « Cour des comptes 2021 — 14 Md€ bruts pour 60→62 » est
    INTROUVABLE (recherche exhaustive, § B.1 point 5 du dossier). Elle est
    retirée, pas re-sourcée par approximation : le vrai objet est la
    décomposition DREES (0,43 pt de PIB, horizon 2030) relayée par l'Institut
    Montaigne, dont la note primaire n'a pas été retrouvée en ligne."""
    motif = re.compile(r"Cour\s+(des\s+comptes\s+)?2021")
    fautifs = [
        str(c.relative_to(_RACINE)) for c in _fichiers_a_auditer()
        if motif.search(c.read_text(encoding="utf-8"))
    ]
    assert not fautifs, (
        f"attribution « Cour 2021 » (introuvable) encore présente dans : {fautifs}"
    )


# --- I5 : le piège de lecture du double « 17,7 Md€ » est documenté --------


def test_methodologie_documente_le_piege_du_double_17_7():
    """METHODOLOGIE.md doit porter la table de passage entre les deux
    « 17,7 Md€ » (Sénat n° l23-498 vs Cour des comptes T6) : c'est l'erreur
    qui a produit le barème v0.6.0, elle doit être lisible par un auditeur
    externe avant qu'il ne la refasse."""
    texte = (_RACINE / "docs" / "METHODOLOGIE.md").read_text(encoding="utf-8")
    assert "17,7" in texte
    for attendu in ("l23-498", "tableau n 6", "euros courants", "euros constants 2024"):
        assert attendu in texte, f"table de passage incomplète : « {attendu} » absent"
