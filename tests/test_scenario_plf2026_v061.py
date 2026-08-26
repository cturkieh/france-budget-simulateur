"""
Scénario de référence « Budget 2026 (voté) » — sourcing et garde de gouvernance
(v0.6.1, lot 9, items I33-I39 du dossier consolidé).

POURQUOI CE FICHIER EXISTE
--------------------------
`plf_2026` n'est plus une colonne parmi neuf : depuis le 24/08 c'est le POINT DE
DÉPART du simulateur et le comparateur implicite de tous les programmes de
parti. Un paramétrage calé sur le déficit de l'année 1 — et non construit mesure
par mesure — y devient un biais systématique en faveur de « la politique
votée ». La quantification (I33, reproduite par ``effort_net_annuel`` ci-dessous
et vérifiée contre le dossier) donnait :

    net encodé   2026 +2,93   2027 +8,00   2030 +25,51   2035 +27,02  Md€/an

soit ~0,75 pt de PIB d'effort permanent en 2030 qu'AUCUNE loi de finances n'a
voté, dont 90 % venaient de trois leviers non chiffrés par le texte
(`fonction_publique_reforme`, fraude fiscale + sociale, `sante`).

LA CORRECTION EST EN DEUX TEMPS, ET LES DEUX SONT DANS LE MÊME LOT
------------------------------------------------------------------
Temps 1 (I34) : retirer ce que la source primaire CONTREDIT.
Temps 2 (I35) : encoder les recettes réellement votées et absentes.
Livrer le premier seul remplacerait un biais par un autre — et ferait manquer
la cible votée de −5,0 % (mesuré : −5,41 % avec le temps 1 seul, hors des
±0,3 pt que ``test_non_regression_deficit_2026`` verrouille).

SOURCE DE RÉFÉRENCE DU LOT
--------------------------
Madec P., Plane M. et al., « Budget 2026 : un déficit de compromis », *OFCE
Policy brief* n° 154, 26 février 2026, **Tableaux 2, 3 et 4** —
https://sciencespo.hal.science/hal-05528644/file/OFCEpbrief154.pdf
Textes : loi n° 2026-103 du 19/02/2026 de finances pour 2026 ; loi
n° 2025-1403 du 30/12/2025 de financement de la sécurité sociale pour 2026.

⚠️ PIÈGE DE COMPARAISON, à ne jamais oublier en lisant les bornes ci-dessous :
les « économies structurelles » de l'OFCE sont mesurées contre une
contrefactuelle de croissance potentielle nominale (2,5 % en 2026) ; la
baseline du moteur est calée sur le tendanciel IGF. Les deux contrefactuelles
ne sont PAS les mêmes. Les chiffres OFCE servent ici d'ORDRE DE GRANDEUR et de
test de vraisemblance — jamais de cible à égaliser, et aucune borne de ce
fichier ne demande au moteur de reproduire une ligne du Tableau 4.
"""
import json
import os
import pathlib
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from budget_simulator.simulator import BudgetSimulatorV45  # noqa: E402

_RACINE = pathlib.Path(__file__).resolve().parent.parent


def _chemin_scenarios():
    """Résolution ROBUSTE de scenarios.json (piège resolve()/symlink).

    Même ordre que ``test_calibration_mission_v060.py`` : (1) l'env var que le
    conftest du repo privé expose PRÉCISÉMENT pour ce piège, (2) le chemin
    relatif au fichier RÉSOLU. Sans (1), un test lancé depuis le symlink
    ``tests/`` du parent cherche dans le repo public, où le fichier n'existe
    pas — et se skippe silencieusement dans TOUTES les CI."""
    env = (os.environ.get('BUDGETLAB_SCENARIOS_JSON') or '').strip()
    for chemin in ([pathlib.Path(env)] if env else []) + [
            _RACINE / '..' / '..' / 'frontend-react' / 'src' / 'data' / 'scenarios.json']:
        if chemin.exists():
            return chemin
    return None


def _mesures_publiees():
    chemin = _chemin_scenarios()
    if chemin is None:
        pytest.skip("scenarios.json introuvable (fork moteur public seul)")
    with open(chemin) as f:
        return json.load(f)['plf_2026']['apiMeasures']


_SANS_FRONTEND = pytest.mark.skipif(
    _chemin_scenarios() is None,
    reason="frontend-react/ hors périmètre du fork moteur public seul")


# ---------------------------------------------------------------------------
# Mesure de l'effort net encodé — la méthode d'I33, reproductible
# ---------------------------------------------------------------------------

# La mesure balaie TOUS les leviers que le scénario pose — jamais une liste
# tenue à la main. Une liste blanche transformerait la garde en trompe-l'œil :
# il suffirait d'ajouter au scénario un levier hors liste pour y loger un
# effort invisible, ce qui est précisément le mode de défaillance qu'elle
# surveille. `defense`, `collectivites` et `immigration` n'ont pas de handler
# Python : ils sont évalués par leur formule ASTEVAL, LUE dans le registre
# plutôt que recopiée en dur (sinon la mesure dériverait du moteur qu'elle
# prétend mesurer).
#
# Conditions de mesure : PIB 3 000 Md€, inflation 1,5 %, chômage 7,5 %. Ce sont
# celles de l'annexe B du dossier ; elles isolent l'effort ENCODÉ du bouclage
# macro (qui, lui, est mesuré par les corridors de calibration).
_PIB_MESURE = 3000.0
_INFLATION_MESURE = 0.015
_CHOMAGE_MESURE = 0.075


def effort_net_annuel(mesures, annees=range(2026, 2036)):
    """Effet net sur le solde public de chaque écart au défaut, en Md€/an.

    Positif = améliore le solde. C'est la grandeur d'I33 : ce que le scénario
    ENCODE comme effort, hors bouclage macroéconomique."""
    from asteval import Interpreter

    sim = BudgetSimulatorV45(periods=12, mesures=mesures)
    total = [0.0] * len(annees)
    for levier in mesures:
        if levier not in sim.measure_handlers:
            continue
        # Une instance NEUVE par levier : les handlers portent des gates
        # one-time (`_is_first_year_change`) dont l'état est par simulation.
        local = BudgetSimulatorV45(periods=12, mesures=mesures)
        handler = local.measure_handlers[levier]
        for i, an in enumerate(annees):
            depense, recette, _ = handler({'id': levier}, mesures[levier], an,
                                          _PIB_MESURE, _INFLATION_MESURE, _CHOMAGE_MESURE)
            total[i] += recette - depense

    registre = {m['id']: m for m in json.loads(
        (_RACINE / 'policy_measures.json').read_text(encoding='utf-8'))['mesures']}
    aeval = Interpreter()
    for levier, mesure in registre.items():
        if levier in sim.measure_handlers or mesure.get('type') != 'formule':
            continue
        if levier not in mesures:
            continue
        aeval.symtable = {
            'p': mesures[levier], 'annee': 2026, 'pib': _PIB_MESURE,
            'consommation': 0.53 * _PIB_MESURE, 'masse_salariale': 0.52 * _PIB_MESURE,
            'profits': 0.25 * _PIB_MESURE, 'inflation': _INFLATION_MESURE,
            'chomage': _CHOMAGE_MESURE,
        }
        resultat = aeval(mesure['formule']) or 0
        signe = -1 if mesure.get('cible') == 'depenses' else 1
        for i in range(len(total)):
            total[i] += signe * resultat
    return total


# ---------------------------------------------------------------------------
# TEMPS 1 (I34) — les six paramètres que la source primaire contredit
# ---------------------------------------------------------------------------

@_SANS_FRONTEND
def test_recherche_publique_ne_code_plus_une_coupe_fantome():
    """La LF 2026 AUGMENTE les crédits de la recherche ; le scénario codait −2 Md€.

    MESR, communiqué du 03/02/2026 : « une augmentation de 725 millions d'euros
    des crédits de la MIRES, qui s'élèvent à 31 milliards d'euros pour 2026 ».
    Sénat, rapport général n° 139 (2025-2026) t. III annexe 23 (Rapin /
    Paoli-Gagin, 24/11/2025) : le périmètre du levier (programmes 172 + 193)
    vaut 9,98 Md€ en LFI 2025 et 10,06 Md€ au PLF 2026 — plat à ~10 Md€ ; le
    CIR est inchangé (7,8 Md€). Coder 8 inventait une coupe de 2 Md€/an que
    personne n'a votée."""
    assert _mesures_publiees()['recherche_publique']['budget'] == 10


@_SANS_FRONTEND
def test_optimisation_dette_sans_source_est_neutralisee():
    """0,75 Md€/an offerts sans AUCUNE contrepartie textuelle.

    Rien dans la loi de finances ne vote d'économie de gestion de dette — et la
    charge d'intérêts AUGMENTE de +5,8 Md€ en 2026 (OFCE PB 154, Tableau 4) et
    de 46 Md€ entre 2026 et 2030 dans le tendanciel IGF. Le tooltip renvoyait à
    « Cour fév. 2025, IGF 2024 » sans montant. §B.5-38 : « toute base
    d'économie de gestion de dette en 2026 » N'EXISTE PAS — donc 0, et surtout
    pas une valeur re-sourcée par approximation."""
    assert _mesures_publiees()['optimisation_dette']['intensite'] == 0


# Bornes en Md€/an — les grandeurs que les sources chiffrent réellement.
# LF 2026 : « Lutte contre les fraudes fiscales : 2,3 Md€ » (OFCE PB 154,
# Tableau 4). Loi n° 2026-534 du 25/06/2026 : « récupérer plus de 1,5 milliard
# d'euros supplémentaires, chaque année » — fiscal ET social confondus
# (https://www.vie-publique.fr/loi/300456-lutte-contre-les-fraudes-sociales-et-fiscales-loi-du-25-juin-2026).
LF2026_FRAUDE_FISCALE_MDE = 2.3
LOI_2026_534_SUPPLEMENT_ANNUEL_MDE = 1.5
# ⚠️ SOMME DÉCLARÉE DÉRIVÉE, pas citée : 2,3 (LF, fiscal) + 1,5 (loi du
# 25/06, fiscal ET social). C'est la seule enveloppe de régime que les deux
# primaires soutiennent CONJOINTEMENT, chacune employée une fois et une seule.
# Elle est un PLAFOND d'ordre de grandeur, jamais une cible à égaliser
# (cf. le piège de comparaison en tête de fichier).
PLAFOND_REGIME_FRAUDE_MDE = (LF2026_FRAUDE_FISCALE_MDE
                             + LOI_2026_534_SUPPLEMENT_ANNUEL_MDE)


def _regime_mde(levier, mesures):
    """Rendement maximal du levier sur l'horizon, en Md€/an — la grandeur que
    les sources bornent. Mêmes conditions que ``effort_net_annuel``."""
    local = BudgetSimulatorV45(periods=12, mesures=mesures)
    handler = local.measure_handlers[levier]
    return max(
        recette - depense
        for depense, recette, _ in (
            handler({'id': levier}, mesures[levier], an, _PIB_MESURE,
                    _INFLATION_MESURE, _CHOMAGE_MESURE)
            for an in range(2026, 2036))
    )


@_SANS_FRONTEND
def test_fraude_fiscale_bornee_par_le_chiffrage_de_la_loi():
    """Le régime doit tenir dans le chiffrage de la loi — EN Md€, pas en curseur.

    Ce test bornait la valeur BRUTE du curseur (`effort == 0,20`,
    `effort <= 0,25`), jamais le rendement. Or le curseur est adimensionnel :
    aucune source ne le chiffre. La docstring affirmait « 0,20 place le régime
    dans cette fourchette » — la mesure la contredisait : le régime valait
    3,18 Md€/an pour la fraude fiscale seule, soit 1,4× la borne haute citée,
    et 4,72 Md€/an avec la fraude sociale, soit 2,1×. C'est la même classe de
    défaut que celle que le lot 9 corrige (un chiffrage qu'aucun texte ne
    porte), logée cette fois dans la garde censée l'empêcher.

    Constat de la revue adverse, clôturé le 2026-08-26. La borne porte
    désormais sur le RÉGIME, en Md€/an, et le curseur en découle."""
    mesures = _mesures_publiees()
    regime = _regime_mde('fraude_fiscale', mesures)
    assert regime <= LF2026_FRAUDE_FISCALE_MDE, (
        f"régime encodé {regime:.2f} Md€/an > chiffrage de la LF 2026 "
        f"({LF2026_FRAUDE_FISCALE_MDE} Md€) : le scénario « la politique "
        f"votée » vote un rendement que la loi ne chiffre pas")


@_SANS_FRONTEND
def test_le_regime_fraude_total_tient_dans_les_deux_textes():
    """Fiscal + social ≤ 2,3 + 1,5 Md€/an — chaque primaire employée UNE fois.

    La borne totale est indispensable et ne se déduit pas de la précédente :
    la loi du 25/06/2026 chiffre un supplément annuel qui couvre le fiscal ET
    le social. Sans cette garde, on pourrait respecter la borne fiscale et
    reloger le dépassement dans `fraude_sociale`, dont §B.5-35 établit
    qu'AUCUN chiffrage distinct n'existe — c'est-à-dire compter deux fois la
    même annonce. Mesuré avant : 4,72 Md€/an, soit 40 % de l'effort net 2030
    du scénario de référence, dans la direction exacte du biais que le lot 9
    prétend fermer."""
    mesures = _mesures_publiees()
    total = sum(_regime_mde(levier, mesures)
                for levier in ('fraude_fiscale', 'fraude_sociale'))
    assert total <= PLAFOND_REGIME_FRAUDE_MDE, (
        f"régime fraude fiscale + sociale {total:.2f} Md€/an > "
        f"{PLAFOND_REGIME_FRAUDE_MDE} Md€ (LF 2026 : "
        f"{LF2026_FRAUDE_FISCALE_MDE} ; loi n° 2026-534 : "
        f"{LOI_2026_534_SUPPLEMENT_ANNUEL_MDE}, fiscal ET social)")


@_SANS_FRONTEND
def test_le_curseur_fraude_fiscale_est_la_plus_grande_valeur_admissible():
    """Le curseur n'est pas choisi, il est DÉDUIT de la borne en Md€.

    0,14 est la plus grande valeur au centième dont le régime (2,23 Md€/an)
    reste sous le chiffrage de la loi (2,3) — le levier étant linéaire en
    `effort` (vérifié ci-dessous). Poser 0,15 rendrait 2,39 et sortirait.
    Ce test existe pour que la valeur ne redevienne jamais un réglage : si
    la borne source change, c'est elle qu'on édite, et le curseur suit."""
    mesures = _mesures_publiees()
    effort = mesures['fraude_fiscale']['effort']
    assert effort == pytest.approx(0.14)
    # Linéarité : le régime d'un curseur double vaut le double.
    double = {**mesures, 'fraude_fiscale': {**mesures['fraude_fiscale'],
                                            'effort': effort * 2}}
    assert _regime_mde('fraude_fiscale', double) == pytest.approx(
        2 * _regime_mde('fraude_fiscale', mesures), rel=1e-9)
    # Le cran au-dessus sortirait : la valeur est bien la plus grande admissible.
    suivant = {**mesures, 'fraude_fiscale': {**mesures['fraude_fiscale'],
                                             'effort': 0.15}}
    assert _regime_mde('fraude_fiscale', suivant) > LF2026_FRAUDE_FISCALE_MDE


@_SANS_FRONTEND
def test_fraude_sociale_borne_basse_prudente():
    """AUCUN chiffrage distinct de la fraude sociale n'existe (§B.5-35).

    Le Tableau 4 de l'OFCE ne mentionne que la fraude fiscale ; les économies
    Sécu (4,1 Md€) ne sont pas décomposées. La loi du 25/06/2026 chiffre un
    total fiscal + social, déjà porté par `fraude_fiscale`. La valeur retenue
    est donc une BORNE BASSE PRUDENTE assumée, pas une estimation — c'est
    exactement ce que le statut « NON ÉTABLI » autorise, et rien de plus."""
    assert _mesures_publiees()['fraude_sociale']['effort'] == pytest.approx(0.10)


@_SANS_FRONTEND
def test_fonction_publique_reforme_non_votee_est_retiree():
    """Le poste non sourcé le plus lourd : +11,3 Md€/an en 2035.

    §B.5-36 : un chiffrage du gain attendu d'une réforme des agences et
    opérateurs dans la LF 2026 N'EXISTE PAS. Il n'y a qu'une ANNONCE
    (A. de Montchalin, avril 2025, « un tiers des agences ») et une
    « réflexion sur les doublons » non chiffrée (Bercy). Une annonce n'est pas
    une loi de finances : le scénario « la politique votée » ne peut pas
    l'encoder."""
    reforme = _mesures_publiees()['fonction_publique_reforme']
    assert reforme['fusion_agences'] == 0
    assert reforme['digitalisation'] == 0


@_SANS_FRONTEND
def test_niches_fiscales_tge_le_volet_menages_a_saute_en_lf():
    """Les 5 Md€ du PLF ont été supprimés en LF : volet ménages 2,8 → 0,0.

    OFCE PB 154, Tableau 3. Ce qui subsiste (Dutreil resserré, Madelin/IR-PME
    recentrée) n'est chiffré NULLE PART (§B.5-34) : le résidu, champ
    entreprises, reste non établi. 56 (soit 2 Md€ d'effort en régime) n'était
    plus tenable sans note ; 57 encode 1 Md€, ordre de grandeur du seul volet
    survivant, et la note dit que le résidu n'est pas chiffré."""
    assert _mesures_publiees()['niches_fiscales_tge']['montant'] == 57


# ---------------------------------------------------------------------------
# TEMPS 2 (I35) — les recettes réellement votées, jusque-là absentes
# ---------------------------------------------------------------------------

@_SANS_FRONTEND
def test_csg_capital_votee_est_encodee():
    """« Hausse de 1,4 pt de CSG sur les revenus financiers et flat tax : 1,5 Md€ »

    OFCE PB 154, Tableau 4. Le rendement encodé est celui de la loi ; le levier
    `csg` porte un taux GLOBAL, donc la valeur posée est celle qui produit
    +1,5 Md€ sur l'assiette du levier, pas les 1,4 pt du texte (qui ne portent
    que sur les revenus du capital)."""
    mesures = _mesures_publiees()
    local = BudgetSimulatorV45(periods=12, mesures=mesures)
    _, recette, _ = local.measure_handlers['csg'](
        {'id': 'csg'}, mesures['csg'], 2026, _PIB_MESURE, _INFLATION_MESURE, _CHOMAGE_MESURE)
    assert recette == pytest.approx(1.5, abs=0.01)


@_SANS_FRONTEND
def test_effort_des_collectivites_vote_est_encode():
    """« Économies des collectivités locales (dont Dilico 740 M€) : 3,4 Md€ »

    OFCE PB 154, Tableaux 2 et 4. La DGF elle-même n'est ni réduite ni
    revalorisée — `dotation = 120` était juste POUR LA DGF, mais ratait
    l'effort demandé aux collectivités, qui passe par d'autres canaux
    (Dilico notamment). Le levier `collectivites` étant une formule en niveau
    de dotation, l'effort s'y encode comme un retrait de 3,4 Md€."""
    mesures = _mesures_publiees()
    assert mesures['collectivites']['dotation'] == pytest.approx(116.6)
    assert mesures['collectivites']['investissement'] == 0


@_SANS_FRONTEND
def test_le_perimetre_non_representable_est_declare():
    """Ce que le simulateur NE PEUT PAS encoder doit être écrit, pas tu.

    Cinq mesures votées ne sont pas représentables par un levier existant sans
    lui faire dire autre chose que ce qu'il calcule (CNRACL, TICFE, malus auto,
    CDHR, taxe sur les complémentaires santé), et le Tableau 4 porte aussi des
    lignes de DÉPENSE qui jouent en sens inverse. Les taire ferait de la
    correction un tri favorable ; SCENARIOS_POLITIQUES.md doit les lister."""
    # `docs/` du moteur = la source CANONIQUE (frontend-react/public/docs/ en
    # est une copie synchronisée par scripts/sync_public_docs.py). Lire le
    # canonique fait voyager la garde avec le repo public.
    texte = (_RACINE / 'docs' / 'SCENARIOS_POLITIQUES.md').read_text(encoding='utf-8')
    for mesure in ('CNRACL', 'TICFE', 'malus', 'CDHR', 'complémentaires', 'PSR-UE'):
        assert mesure in texte, (
            f"« {mesure} » manque au perimetre declare de plf_2026 : une mesure "
            f"votee non encodee et non dite est un tri silencieux")


def test_optimisation_dette_ne_fait_pas_porter_son_chiffrage_a_une_institution():
    """Le pendant PUBLIC d'I34-b : le paramètre passe à 0, le libellé doit suivre.

    Le registre publié annonçait « Refinancement stratégique (1-2.5 Md€) » avec
    pour tooltip « Sources : Cour des comptes fév. 2025, IGF 2024 ». Or §B.5-38
    du dossier établit que **toute base d'économie de gestion de dette en 2026
    N'EXISTE PAS**, et le dossier note explicitement que ce tooltip renvoie à
    ces deux institutions « sans montant ». Retirer le levier du scénario de
    référence tout en laissant le simulateur dire au visiteur que la Cour
    chiffre le gain, c'est exactement la dérive libellé ↔ calcul dont ce projet
    a déjà payé le prix.

    Le chiffre N'EST PAS retiré — le handler calcule bien un plafond de
    2,5 Md€/an, et l'effacer du libellé recréerait la dérive dans l'autre sens.
    C'est l'ATTRIBUTION qui est retirée : la borne redevient ce qu'elle est, une
    convention de modélisation du simulateur, sur le modèle déjà retenu pour le
    plafond de rendement de la prévention (§B.3-22)."""
    registre = {m['id']: m for m in json.loads(
        (_RACINE / 'policy_measures.json').read_text(encoding='utf-8'))['mesures']}
    levier = registre['optimisation_dette']
    textes = [levier.get('description', ''),
              levier['parametres']['intensite'].get('tooltip', '')]
    joints = ' '.join(textes)
    assert 'Cour des comptes' not in joints and 'IGF 2024' not in joints, (
        "le registre public attribue encore le chiffrage du refinancement a la "
        "Cour des comptes ou a l'IGF, alors qu'aucune des deux ne le publie "
        "(§B.5-38 : cette base n'existe pas)")
    assert 'convention de modélisation' in joints, (
        "la borne du levier doit etre annoncee pour ce qu'elle est — une "
        "convention du simulateur — et non laissee sans statut")


# ---------------------------------------------------------------------------
# I38 — la mine ASTEVAL latente du registre
# ---------------------------------------------------------------------------

def test_la_formule_recherche_publique_est_un_delta_pas_un_niveau():
    """Bonus latent : la formule rendrait 10 Md€ de dépenses au lieu d'un delta.

    Elle est INERTE aujourd'hui (le handler Python a la priorité dans
    ``orchestrator.apply_measures``), mais elle est armée pour le chantier
    « Fix A », qui retire précisément le couplage frontend et peut faire
    retomber des leviers sur leur formule. Toutes les autres formules du
    registre sont des deltas (`p.get('budget', 50) - 50` pour `defense`,
    `(p.get('dotation', 120) - 120) + ...` pour `collectivites`) : celle-ci
    était la seule à publier un NIVEAU."""
    registre = {m['id']: m for m in json.loads(
        (_RACINE / 'policy_measures.json').read_text(encoding='utf-8'))['mesures']}
    recherche = registre['recherche_publique']
    defaut = recherche['parametres']['budget']['valeur_defaut']
    from asteval import Interpreter
    aeval = Interpreter()
    aeval.symtable = {'p': {'budget': defaut}}
    assert aeval(recherche['formule']) == 0, (
        "au defaut du registre, la formule doit rendre 0 : elle exprime un "
        "ecart au defaut, pas un niveau de budget")


# ---------------------------------------------------------------------------
# I39 — LA GARDE DE GOUVERNANCE (le plus important de l'axe 6)
# ---------------------------------------------------------------------------

# Effort structurel de la LF 2026 chiffré par l'OFCE : 0,5 pt de PIB (PB 154,
# p. 3, « l'écart PLF → LF ramène l'effort structurel de 0,8 à 0,5 pt de PIB »).
# Utilisé comme PLAFOND D'ORDRE DE GRANDEUR sur l'année votée, jamais comme
# cible : cf. le piège de comparaison en tête de fichier.
OFCE_EFFORT_STRUCTUREL_2026_PT_PIB = 0.5

# Marge d'I39 : « ≤ 0,5 pt de PIB d'effort au-delà du chiffrage OFCE ».
TOLERANCE_DERIVE_PT_PIB = 0.5

# Cible de déficit votée pour 2026 : −5,0 % du PIB (loi n° 2026-103 ;
# Vie-publique LF 2026 ; OFCE PB 154). ±0,3 pt : le scénario doit rester une
# description de la loi, sans être calé À la décimale dessus — c'est
# précisément le calage-sur-l'année-1 qui a produit la dérive corrigée ici.
CIBLE_DEFICIT_2026 = -5.0
TOLERANCE_DEFICIT_2026 = 0.3


@_SANS_FRONTEND
def test_gouvernance_effort_2030_ne_derive_pas_au_dela_de_lannee_votee():
    """GARDE PERMANENTE : le scénario ne doit pas voter à la place du législateur.

    Une loi de finances est ANNUELLE. Le scénario « Budget 2026 (voté) » peut
    légitimement porter l'effort chiffré pour 2026 et faire l'hypothèse,
    déclarée, que les mesures structurelles persistent. Ce qu'il ne peut pas
    faire, c'est ACCÉLÉRER : un effort qui croît d'année en année au-delà de ce
    que le texte chiffre n'est plus « la politique votée », c'est un programme
    d'ajustement anonyme — et il pénalise mécaniquement tout programme de parti
    comparé à lui.

    Mesuré avant le lot 9 : +2,93 Md€ en 2026 → +25,51 en 2030, soit une dérive
    de +22,58 Md€ = 0,75 pt de PIB. Ce test rougissait donc sur l'état publié
    jusqu'au 25/08/2026 — c'est sa raison d'être. Mesuré après : 0,26 pt.

    DEUX bornes, parce qu'une seule se contournerait : borner la seule dérive
    laisserait passer un scénario qui gonfle l'année 1 pour aplatir la pente ;
    borner le seul niveau laisserait passer la dérive que ce lot corrige. Le
    niveau de l'année votée est en outre tenu par le bas par
    ``test_non_regression_deficit_2026``."""
    mesures = _mesures_publiees()
    net = effort_net_annuel(mesures)
    net_2026, net_2030 = net[0], net[4]
    derive_pt_pib = (net_2030 - net_2026) / _PIB_MESURE * 100
    assert derive_pt_pib <= TOLERANCE_DERIVE_PT_PIB, (
        f"effort encodé {net_2026:+.2f} Md€ en 2026 → {net_2030:+.2f} en 2030 : "
        f"dérive {derive_pt_pib:+.3f} pt de PIB au-delà de l'année votée "
        f"(plafond {TOLERANCE_DERIVE_PT_PIB}) — le scénario de référence vote "
        f"un ajustement que le législateur n'a pas voté")
    plafond_2026 = OFCE_EFFORT_STRUCTUREL_2026_PT_PIB / 100 * _PIB_MESURE
    assert net_2026 <= plafond_2026, (
        f"effort encodé pour l'année votée {net_2026:+.2f} Md€ > effort "
        f"structurel chiffré par l'OFCE ({plafond_2026:.1f} Md€) : ordre de "
        f"grandeur incompatible avec la loi de finances 2026")


@_SANS_FRONTEND
def test_non_regression_deficit_2026():
    """Le scénario corrigé retombe sur la cible votée SANS levier inventé.

    C'est la preuve que les deux temps se tiennent : le temps 1 seul donne
    −5,41 % (hors tolérance) ; le temps 2 encode ≈4,9 Md€ de recettes
    RÉELLEMENT votées et le déficit revient dans le corridor. Ce test interdit
    de re-livrer un jour le temps 1 sans le temps 2 — ou l'inverse."""
    df, _, _ = BudgetSimulatorV45(periods=10, mesures=_mesures_publiees()).simulate()
    deficit = df['Déficit/PIB %'].iloc[1]
    assert abs(deficit - CIBLE_DEFICIT_2026) <= TOLERANCE_DEFICIT_2026, (
        f"deficit 2026 {deficit:.2f} % vs cible votee {CIBLE_DEFICIT_2026} % "
        f"(tolerance ±{TOLERANCE_DEFICIT_2026})")
