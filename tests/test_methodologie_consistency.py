"""Garde CI : verrou anti-dérive entre les constantes économiques du code
et leur représentation dans les docs UI (METHODOLOGIE.md, EXPLICATION_MODELE_ECONOMIQUE.md).

Philosophie identique à `test_measure_registry_sync.py` : si une constante
économique change dans le code, la CI rougit tant que la doc UI n'a pas
été mise à jour avec la nouvelle valeur. Direction : CODE → DOC.

Périmètre : ~9 constantes nommées les plus visibles côté lecteur
(journaliste, citoyen, chercheur). Les coefficients inline non nommés
(ex : coefficient Phillips `0.35` directement dans `inflation.py`) ne
sont **pas** verrouillés : non extractibles automatiquement, dérive
plus lente, visible plus tôt côté contributeur que côté lecteur.

Pour ajouter une nouvelle constante au périmètre : entrée dans
`_critical_constants()` ci-dessous (la liste EST la spec).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from budget_simulator import constants
from budget_simulator.simulator import BudgetSimulatorV45

ROOT = Path(__file__).resolve().parent.parent
METHODO = ROOT / "docs" / "METHODOLOGIE.md"
EXPLICATION = ROOT / "docs" / "EXPLICATION_MODELE_ECONOMIQUE.md"
# Copies servies au frontend (téléchargement journalistes/citoyens) —
# synchronisées par scripts/sync_public_docs.py. Inclues dans le verrou
# pour bloquer tout drift entre source et copie publique, même si
# `make check-docs-sync` n'a pas été lancé.
#
# NB : ces chemins n'existent pas dans un fork du repo public seul
# (`frontend-react/` reste sur le repo privé `budgetlab-france`). Les tests
# qui les consomment doivent gérer l'absence — cf `_must_appear_in_existing`
# et la skipif appliquée à `test_critical_constants_appear_in_docs_ui`.
PUBLIC_METHODO = ROOT / "frontend-react" / "public" / "docs" / "METHODOLOGIE.md"
PUBLIC_EXPLICATION = ROOT / "frontend-react" / "public" / "docs" / "EXPLICATION_MODELE_ECONOMIQUE.md"
_ALL_DOCS = (METHODO, EXPLICATION, PUBLIC_METHODO, PUBLIC_EXPLICATION)
# Docs invariablement présentes dans le périmètre public (subtree open source) —
# servent de socle minimal pour la skipif fork-friendly.
_PUBLIC_ONLY_DOCS = (METHODO, EXPLICATION)


@dataclass(frozen=True)
class CriticalConstant:
    """Constante économique citée dans les docs UI à verrouiller.

    `representations` = formes NUMÉRIQUES parsables (verrou valeur↔code).
    `doc_patterns` = motifs de RECHERCHE dans la doc, avec unité/contexte
    (« 16 Md EUR », « plateau 7 ans ») quand le nombre nu serait un
    faux-vert par sur-matching (un « 16 » nu matche n'importe quel 16 de
    la doc — prouvé en revue 2026-08-04 contre la doc pré-fix). Défaut
    vide = les representations servent aussi de motifs (cas des valeurs
    avec % ou format discriminant)."""
    name: str
    source: str
    raw_value: float
    representations: tuple[str, ...]
    must_appear_in: tuple[Path, ...]
    doc_patterns: tuple[str, ...] = ()

    @property
    def search_patterns(self) -> tuple[str, ...]:
        return self.doc_patterns or self.representations


def _critical_constants() -> tuple[CriticalConstant, ...]:
    # `economic_coeffs` est hardcodé dans `simulator.py` (section
    # « economic coefficients ») — on lit la source via une instance.
    _sim = BudgetSimulatorV45()
    coeffs = _sim.economic_coeffs
    mults = _sim.multipliers.base_multipliers
    return (
        CriticalConstant(
            name="PIB_BASE_2025 (Md EUR)",
            source="constants.PIB_BASE_2025_MD_EUR",
            raw_value=constants.PIB_BASE_2025_MD_EUR,
            representations=("2 991", "2991"),
            must_appear_in=(EXPLICATION, PUBLIC_EXPLICATION),
        ),
        CriticalConstant(
            name="DETTE_RATIO_2025 (% PIB)",
            source="constants.DETTE_RATIO_2025",
            raw_value=constants.DETTE_RATIO_2025,
            representations=("115,6%", "115,6 %"),
            must_appear_in=(EXPLICATION, PUBLIC_EXPLICATION),
        ),
        CriticalConstant(
            name="CHOMAGE_BASE (taux)",
            source="constants.CHOMAGE_BASE",
            raw_value=constants.CHOMAGE_BASE,
            representations=("7,6%", "7,6 %"),
            must_appear_in=(EXPLICATION, PUBLIC_EXPLICATION),
        ),
        CriticalConstant(
            name="CHOMAGE_NAIRU (taux)",
            source="constants.CHOMAGE_NAIRU",
            raw_value=constants.CHOMAGE_NAIRU,
            representations=("7,5%", "7,5 %"),
            must_appear_in=_ALL_DOCS,
        ),
        CriticalConstant(
            name="INFLATION_STRUCTURELLE (intercept Phillips)",
            source="constants.INFLATION_STRUCTURELLE",
            raw_value=constants.INFLATION_STRUCTURELLE,
            representations=("1,5%", "1,5 %"),
            must_appear_in=_ALL_DOCS,
        ),
        CriticalConstant(
            name="CROISSANCE_POTENTIELLE",
            source="constants.CROISSANCE_POTENTIELLE",
            raw_value=constants.CROISSANCE_POTENTIELLE,
            representations=("1,1%", "1,1 %"),
            must_appear_in=_ALL_DOCS,
        ),
        CriticalConstant(
            name="TAUX_INTERET_BASE",
            source="constants.TAUX_INTERET_BASE",
            raw_value=constants.TAUX_INTERET_BASE,
            representations=("2,0%", "2,0 %"),
            must_appear_in=(EXPLICATION, PUBLIC_EXPLICATION),
        ),
        CriticalConstant(
            name="okun coefficient",
            source="economic_coeffs['okun']",
            raw_value=coeffs["okun"],
            # METHODO utilise notation anglo-saxonne `-0.35` sur ce point
            representations=("-0.35", "-0,35"),
            must_appear_in=(METHODO, PUBLIC_METHODO),
        ),
        # v0.6.0 : les deux coefficients de consolidation corrigés par l'audit
        # (générique relevé, canal investissement créé) entrent dans le verrou.
        CriticalConstant(
            name="multiplicateur consolidation dépenses générique",
            source="base_multipliers['consolidation']['spending_based']",
            raw_value=mults['consolidation']['spending_based'],
            representations=("-0,60", "-0.60"),
            must_appear_in=(METHODO, PUBLIC_METHODO),
        ),
        CriticalConstant(
            name="multiplicateur coupe d'investissement public",
            source="base_multipliers['consolidation']['investissement']",
            raw_value=mults['consolidation']['investissement'],
            representations=("-1,20", "-1.20", "-1,2", "-1.2"),
            must_appear_in=(METHODO, PUBLIC_METHODO),
        ),
        CriticalConstant(
            name="debt_drag coefficient",
            source="economic_coeffs['debt_drag']",
            raw_value=coeffs["debt_drag"],
            representations=("-0,005", "-0.005"),
            must_appear_in=(METHODO, PUBLIC_METHODO),
        ),
        # Coefficients retraites nommés le 2026-08-04 après dérive ×2 constatée
        # (code 16/4 vs doc et tooltips 8/2 pendant ~10 semaines, repo public).
        # v0.6.1 : les deux segments de la v0.6.0 fusionnent en UN coefficient
        # plat et symétrique (le 14,2 venait d'une collision entre deux
        # « 17,7 Md€ » sans rapport) — un seul verrou, plus de risque de
        # recalibrage à moitié appliqué.
        CriticalConstant(
            name="retraites âge — coefficient unique (Md EUR/an par année d'âge)",
            source="constants.RETRAITES_COEFF_AGE_MD_EUR",
            raw_value=constants.RETRAITES_COEFF_AGE_MD_EUR,
            representations=("6,0", "6.0"),
            must_appear_in=(METHODO, PUBLIC_METHODO),
            doc_patterns=("6,0 Md EUR par annee d'age",),
        ),
        CriticalConstant(
            name="retraites durée (Md EUR/an par année)",
            source="constants.RETRAITES_COEFF_DUREE_MD_EUR",
            raw_value=constants.RETRAITES_COEFF_DUREE_MD_EUR,
            representations=("4",),
            must_appear_in=(METHODO, PUBLIC_METHODO),
            doc_patterns=("4 Md EUR par annee",),
        ),
        CriticalConstant(
            name="retraites érosion indexation (Md EUR/an, gel total)",
            source="constants.RETRAITES_EROSION_INDEXATION_MD_EUR",
            raw_value=constants.RETRAITES_EROSION_INDEXATION_MD_EUR,
            representations=("1,5", "1.5"),
            must_appear_in=(METHODO, PUBLIC_METHODO),
            doc_patterns=("1,5 Md EUR par annee",),
        ),
        CriticalConstant(
            name="retraites plateau érosion (années)",
            source="constants.RETRAITES_EROSION_PLATEAU_ANS",
            raw_value=constants.RETRAITES_EROSION_PLATEAU_ANS,
            representations=("7",),
            must_appear_in=(METHODO, PUBLIC_METHODO),
            doc_patterns=("plateau 7 ans",),
        ),
        CriticalConstant(
            name="retraites référence âge 2026-2027 (ans, gel LFSS 2026)",
            source="constants.RETRAITES_REF_AGE_ANS",
            raw_value=constants.RETRAITES_REF_AGE_ANS,
            representations=("62,75", "62.75"),
            must_appear_in=(METHODO, PUBLIC_METHODO),
            doc_patterns=("62,75 ans",),
        ),
        # v0.6.1 : la référence d'âge est un CALENDRIER, pas une valeur — sa
        # cible doit être lisible dans la doc, sinon le lecteur ne peut pas
        # savoir à quoi le simulateur compare un programme après 2028.
        CriticalConstant(
            name="retraites cible du calendrier légal (ans, atteinte en 2032)",
            source="constants.RETRAITES_REF_AGE_CIBLE_ANS",
            raw_value=constants.RETRAITES_REF_AGE_CIBLE_ANS,
            representations=("64,0", "64.0"),
            must_appear_in=(METHODO, PUBLIC_METHODO),
            doc_patterns=("64,0 ans en 2032",),
        ),
        CriticalConstant(
            name="retraites référence durée 2025 (ans)",
            source="constants.RETRAITES_REF_DUREE_ANS",
            raw_value=constants.RETRAITES_REF_DUREE_ANS,
            representations=("42,5", "42.5"),
            must_appear_in=(METHODO, PUBLIC_METHODO),
            doc_patterns=("42,5 ans",),
        ),
        # v0.6.1 lot 3 — canal emploi seniors. Les trois valeurs qu'un lecteur
        # verra citées (et qu'un contradicteur ira vérifier) entrent au verrou :
        # l'effet PIB, la bosse de chômage (DÉRIVATION MAISON, à publier comme
        # telle) et la fuite sociale (9,6 % et non 20 % — le point le plus
        # contre-intuitif du lot).
        CriticalConstant(
            name="seniors — niveau de PIB par année d'âge (long terme)",
            source="constants.OFFRE_SENIORS_PIB_NIVEAU_LT",
            raw_value=constants.OFFRE_SENIORS_PIB_NIVEAU_LT,
            representations=("0,80%", "0,80 %"),
            must_appear_in=(METHODO, PUBLIC_METHODO),
            doc_patterns=("0,80% de niveau de PIB par annee d'age",),
        ),
        CriticalConstant(
            name="seniors — bosse de chômage au pic par année d'âge",
            source="constants.CHOMAGE_SENIORS_PIC",
            raw_value=constants.CHOMAGE_SENIORS_PIC,
            representations=("0,18%", "0,18 %"),
            must_appear_in=(METHODO, PUBLIC_METHODO),
            doc_patterns=("0,18% au pic par annee d'age",),
        ),
        CriticalConstant(
            name="seniors — fuite sociale résiduelle (part des économies brutes)",
            source="constants.FUITE_SOCIALE_RESIDUELLE",
            raw_value=constants.FUITE_SOCIALE_RESIDUELLE,
            representations=("9,6%", "9,6 %"),
            must_appear_in=(METHODO, PUBLIC_METHODO),
            doc_patterns=("9,6% des economies brutes",),
        ),
        # v0.6.1 lot 4 — prévention. Les trois valeurs qu'un lecteur voit :
        # l'assiette du curseur, sa borne haute (dérivée de l'écart OCDE) et le
        # plafond de compensation — ce dernier étant le seul CHOIX DE
        # MODÉLISATION du lot, donc celui qu'un contradicteur ira vérifier en
        # premier. Le verrou impose qu'un recalibrage passe par la doc.
        CriticalConstant(
            name="prévention — base du curseur (Md EUR, DREES fiche 21)",
            source="constants.PREVENTION_BASE_MD_EUR",
            raw_value=constants.PREVENTION_BASE_MD_EUR,
            representations=("7,5", "7.5"),
            must_appear_in=(METHODO, PUBLIC_METHODO),
            doc_patterns=("7,5 Md EUR",),
        ),
        CriticalConstant(
            name="prévention — borne haute du curseur (Md EUR, convergence OCDE)",
            source="constants.PREVENTION_PLAFOND_MD_EUR",
            raw_value=constants.PREVENTION_PLAFOND_MD_EUR,
            representations=("11,2", "11.2"),
            must_appear_in=(METHODO, PUBLIC_METHODO),
            doc_patterns=("11,2 Md EUR",),
        ),
        CriticalConstant(
            name="prévention — plafond du taux de compensation (choix assumé)",
            source="constants.PREVENTION_OFFSET_CENTRAL_CAP",
            raw_value=constants.PREVENTION_OFFSET_CENTRAL_CAP,
            representations=("0,50", "0.50"),
            must_appear_in=(METHODO, PUBLIC_METHODO),
            doc_patterns=("plafonne a **0,50**",),
        ),
        # v0.6.1 lot 5 — ASU. Les trois valeurs qu'un contradicteur ira
        # verifier : le PERIMETRE (parce que la v0.5.1 en annonçait 90 dont
        # 52 de prestations familiales hors reforme), le SIGNE de l'effort
        # (une reforme qui coute, non qui rapporte) et la seule economie
        # maintenue. Le verrou impose qu'un recalibrage passe par la doc.
        CriticalConstant(
            name="ASU — périmètre de la réforme (Md EUR, RSA + PA + APL)",
            source="constants.ASU_PERIMETRE_MD_EUR",
            raw_value=constants.ASU_PERIMETRE_MD_EUR,
            representations=("39",),
            must_appear_in=(METHODO, PUBLIC_METHODO),
            doc_patterns=("39 Md EUR",),
        ),
        CriticalConstant(
            name="ASU — effort budgétaire pérenne maximal (Md EUR/an)",
            source="constants.ASU_EFFORT_PERENNE_MAX_MD_EUR",
            raw_value=constants.ASU_EFFORT_PERENNE_MAX_MD_EUR,
            representations=("2,0", "2.0"),
            must_appear_in=(METHODO, PUBLIC_METHODO),
            doc_patterns=("+2,0 Md EUR par an",),
        ),
        CriticalConstant(
            name="ASU — économie de gestion retenue (Md EUR/an, dérivation)",
            source="constants.ASU_ECO_SIMPLIFICATION_MD_EUR",
            raw_value=constants.ASU_ECO_SIMPLIFICATION_MD_EUR,
            representations=("0,3", "0.3"),
            must_appear_in=(METHODO, PUBLIC_METHODO),
            doc_patterns=("0,3 Md EUR par an",),
        ),
        # v0.6.1 lot 6 — canaux Gini de la transition écologique. Les deux
        # valeurs sont verrouillées sous la forme que le lecteur voit (l'effet
        # d'un pas de +50 EUR/tCO2 et d'un pas de +5 Md EUR), et non sous la
        # forme du coefficient unitaire : c'est cette forme-là qu'un
        # contradicteur ira comparer à Douenne 2020 / à l'ONRE, et le parseur
        # du verrou ne discrimine pas les valeurs à 1e-5 près.
        CriticalConstant(
            name="Gini — taxe carbone, effet d'un pas de +50 EUR/tCO2",
            source="constants.GINI_TAXE_CARBONE_PAR_EUR_TONNE × 50 EUR/t",
            raw_value=constants.GINI_TAXE_CARBONE_PAR_EUR_TONNE * 50,
            representations=("0,0010", "0.0010"),
            must_appear_in=(METHODO, PUBLIC_METHODO),
            doc_patterns=("+0,0010 de Gini pour",),
        ),
        CriticalConstant(
            name="Gini — rénovation énergétique, effet de +5 Md EUR",
            source="constants.GINI_RENOVATION_PAR_MD_EUR × 5 Md EUR",
            raw_value=constants.GINI_RENOVATION_PAR_MD_EUR * 5,
            representations=("-0,0017", "-0.0017"),
            must_appear_in=(METHODO, PUBLIC_METHODO),
            doc_patterns=("-0,0017",),
        ),
    )


def _parse_representation(rep: str) -> float | None:
    """Parse une représentation textuelle (français ou anglais) en float.

    Retire espaces ASCII + insécables (U+00A0, fréquent dans la doc) et
    convertit la virgule décimale en point. Divise par 100 si `%` présent.
    Retourne `None` si non parsable (ex : "voir section")."""
    cleaned = rep.replace(" ", "").replace(" ", "").replace("%", "").replace(",", ".")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value / 100.0 if "%" in rep else value


def test_critical_constants_representations_match_code():
    """Au moins une `representation` reflète la valeur Python actuelle.

    Échoue AVANT le test de présence si tu changes la valeur du code sans
    mettre à jour les représentations dans ce fichier — message clair sur
    la dérive interne au test (avant de chercher dans la doc).
    """
    failures = []
    for c in _critical_constants():
        match = False
        for rep in c.representations:
            parsed = _parse_representation(rep)
            if parsed is None:
                continue
            if abs(parsed - c.raw_value) < 1e-4:
                match = True
                break
        if not match:
            failures.append(
                f"  - {c.name} = {c.raw_value!r} ({c.source})\n"
                f"    aucune des représentations {c.representations} "
                f"ne correspond à cette valeur après parsing."
            )
    if failures:
        raise AssertionError(
            "Représentations doc désynchronisées de la valeur Python "
            "actuelle :\n" + "\n".join(failures)
            + "\n\nFix : mettre à jour `representations` dans "
            "`tests/test_methodologie_consistency.py::_critical_constants`."
        )


def _matches_with_boundary(rep: str, text: str) -> bool:
    """Cherche `rep` dans `text` avec frontière numérique pour éviter les
    faux-vert par substring matching.

    Sans frontière, `"1,5%"` matche par substring `"21,5%"` ou `"107,6%"`,
    ce qui ferait passer le test à tort quand une valeur du code change
    mais qu'une représentation similaire apparaît ailleurs dans la doc
    pour un concept sans rapport. Lookbehind `(?<!\\d)` et lookahead
    `(?!\\d)` exigent que `rep` ne soit pas immédiatement entouré par un
    chiffre — suffit pour bloquer les ~95 % des cas de drift par bruit
    numérique adjacent. Les autres préfixes (`+`, `-`, `≈`) restent
    légitimes car non-numériques.
    """
    return re.search(r"(?<!\d)" + re.escape(rep) + r"(?!\d)", text) is not None


def test_critical_constants_appear_in_docs_ui():
    """Chaque constante critique apparaît avec une représentation acceptable
    dans la (les) doc(s) cible(s), y compris les copies publiques servies
    au frontend (si présentes — un fork du moteur seul n'a pas le frontend).

    Si la CI rougit ici :
    - soit une constante du code a changé sans MAJ de la doc UI ;
    - soit la doc a reformulé la valeur (ex : "115,6 %" → "115,6 pts") :
      ajouter la nouvelle représentation dans `_critical_constants` ;
    - soit `docs/` et `frontend-react/public/docs/` ont divergé (oubli de
      `python3 scripts/sync_public_docs.py`) — relancer le sync.
    """
    # Skip silencieux des copies publiques absentes (fork du moteur seul) :
    # le périmètre minimal `docs/METHODOLOGIE.md` + `EXPLICATION` est toujours
    # vérifié ; les chemins `frontend-react/public/docs/*` ne sont contrôlés
    # que si présents. Pattern aligné sur test_political_scenarios_2027.py:97-101.
    available_docs = tuple(p for p in _ALL_DOCS if p.exists())
    docs_cache = {path: path.read_text(encoding="utf-8") for path in available_docs}
    failures = []
    for c in _critical_constants():
        for doc_path in c.must_appear_in:
            if doc_path not in docs_cache:
                continue  # doc absente (fork) → skip ce check spécifique
            text = docs_cache[doc_path]
            if not any(_matches_with_boundary(rep, text) for rep in c.search_patterns):
                failures.append(
                    f"  - {c.name} ({c.source}) = {c.raw_value!r}\n"
                    f"    aucun des motifs {c.search_patterns} "
                    f"n'apparaît dans {doc_path.name} avec frontière numérique."
                )
    if failures:
        raise AssertionError(
            "Constantes économiques code↔doc UI désynchronisées :\n"
            + "\n".join(failures)
            + "\n\nFix : MAJ la valeur dans la doc UI concernée. Si le "
            "changement code est délibéré, MAJ aussi `representations` "
            "dans `tests/test_methodologie_consistency.py`. Vérifie aussi "
            "que `python3 scripts/sync_public_docs.py` a été lancé après "
            "l'édition de `docs/`."
        )


# --- Tests de mutation (rouge automatisé) ---------------------------------


def test_drift_detected_when_constant_changes(monkeypatch):
    """Rouge automatisé : muter une constante du code FAIT bien rougir le verrou.

    Garantit que le test de cohérence n'est pas faux-vert. On mute
    `INFLATION_STRUCTURELLE` 0.015 → 0.018 puis on exécute la même
    logique que `test_critical_constants_representations_match_code` —
    elle DOIT lever AssertionError avec un message ciblant la constante.
    """
    monkeypatch.setattr(constants, "INFLATION_STRUCTURELLE", 0.018)

    with pytest.raises(AssertionError, match="INFLATION_STRUCTURELLE"):
        test_critical_constants_representations_match_code()


def test_doc_patterns_derivent_des_representations():
    """Anti-découplage : un motif figé indépendamment de la valeur laisse
    passer un recalibrage (prouvé en revue finale : 16→8 avec representations
    mises à jour et doc_patterns figé = tout vert, doc restée à 16). Chaque
    doc_pattern doit CONTENIR une representation pour suivre la valeur."""
    for c in _critical_constants():
        for pat in c.doc_patterns:
            assert any(rep in pat for rep in c.representations), (
                f"{c.source} : motif {pat!r} ne contient aucune de "
                f"{c.representations} — il ne suivra pas un recalibrage")


def test_drift_detected_when_md_eur_constant_changes(monkeypatch):
    """Même rouge automatisé pour la famille Md€ (sans %) : la revue
    2026-08-04 a montré que la faiblesse des motifs nus est invisible sur
    les constantes en %, il faut donc un cas de mutation dans CETTE famille
    (recalibrage plausible 6 → 8, la dérive historique inversée)."""
    monkeypatch.setattr(constants, "RETRAITES_COEFF_AGE_MD_EUR", 8.0)

    with pytest.raises(AssertionError, match="RETRAITES_COEFF_AGE_MD_EUR"):
        test_critical_constants_representations_match_code()


def test_boundary_matching_blocks_substring_false_positives():
    """Garde-fou sur la frontière numérique : la doc peut citer une valeur
    NUMÉRIQUEMENT différente qui contient par substring une représentation
    verrouillée — sans frontière, faux-vert silencieux.

    Cas concrets représentatifs (extraits réels du repo) :
    - "1,5%" dans "21,5%" (chiffre avant) → DOIT être bloqué
    - "0,8%" dans "10,8%" (chiffre avant) → DOIT être bloqué
    - "2 994" dans "12 9940" (chiffres autour) → DOIT être bloqué
    - "1,5%" dans " 1,5%" (espace avant) → DOIT matcher
    - "0,8%" dans "+0,8%" (signe avant) → DOIT matcher (préfixe non-numérique)
    - "-0.35" dans "X-0.35" → DOIT matcher (préfixe non-numérique)
    """
    # Bloque les faux-verts par préfixe numérique
    assert not _matches_with_boundary("1,5%", "Inflation 21,5% en 2019")
    assert not _matches_with_boundary("0,8%", "Croissance 10,8% volume")
    assert not _matches_with_boundary("2 994", "Total 12 9940 Md")
    # Accepte les contextes légitimes
    assert _matches_with_boundary("1,5%", "Inflation tendancielle 1,5% (Phillips)")
    assert _matches_with_boundary("0,8%", "+0,8% par an depuis 2023")
    assert _matches_with_boundary("-0.35", "Okun β=-0.35 (médiane OFCE)")
    assert _matches_with_boundary("2 994", "PIB 2 994 Md€ (INSEE)")


def test_drift_detected_when_doc_only_has_substring_match(monkeypatch, tmp_path):
    """Rouge automatisé sur le faux-vert substring : si une valeur du code
    n'apparait dans la doc QUE comme substring d'un autre nombre, le test
    DOIT rougir.

    On bricole un cas où la rep cherchée existe en substring dans la doc
    mais avec contexte numérique différent — sans la frontière, ça
    passerait à tort. Avec la frontière, ça rougit comme attendu.
    """
    # Crée une doc factice qui ne contient "1,5%" que comme substring
    # de "21,5%" (cas réel : doc mentionne une stat sans rapport)
    fake_doc = tmp_path / "fake.md"
    fake_doc.write_text(
        "# Fake doc\n\nL'inflation moyenne 2010-2019 était de 21,5%.\n",
        encoding="utf-8",
    )
    # Sans frontière, "1,5%" matcherait par substring "21,5%" → faux-vert
    assert "1,5%" in fake_doc.read_text("utf-8")
    # Avec frontière, le matching exact échoue
    assert not _matches_with_boundary("1,5%", fake_doc.read_text("utf-8"))


def test_parse_representation_handles_french_and_english_formats():
    """Garde-fou sur le parser : couvre les formats utilisés en doc."""
    assert _parse_representation("1,5%") == pytest.approx(0.015)
    assert _parse_representation("1,5 %") == pytest.approx(0.015)
    assert _parse_representation("115,6%") == pytest.approx(1.156)
    assert _parse_representation("2 994") == pytest.approx(2994.0)
    assert _parse_representation("-0,35") == pytest.approx(-0.35)
    assert _parse_representation("-0.35") == pytest.approx(-0.35)
    assert _parse_representation("-0,005") == pytest.approx(-0.005)
    # Cas non parsable → None (pas d'exception)
    assert _parse_representation("voir section") is None
