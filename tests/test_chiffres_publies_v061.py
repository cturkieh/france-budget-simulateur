"""Les chiffres MESURÉS que les documents publics citent doivent reproduire.

POURQUOI CE FICHIER EXISTE (clôture de la revue adverse, 2026-08-26)
--------------------------------------------------------------------
Le projet vit sur des générateurs et des gardes ``--check`` : sitemap, llms.txt,
registre des mesures, blocs de doc ancrés, précalculs. Il en restait une classe
entière sans garde — **les chiffres mesurés cités en prose** dans les deux
documents publics. Résultat mesuré au moment de la revue : ``METHODOLOGIE.md``
et ``EXPLICATION_MODELE_ECONOMIQUE.md`` publiaient encore la baseline d'AVANT
le lot 8, que ce même lot avait déplacée de 10 à 12 points — « deficit 2026
-5,05%, dette 2030 ~129,5%, dette 2035 ~150% » contre −5,38 / 130,68 / 162,12
mesurés — et le lot 8 avait édité les lignes ADJACENTES dans le même commit.
Le sentier de déflateur réalisé, qui est le résultat central du lot 8, était
lui aussi périmé d'un lot. Les copies servies au public
(``frontend-react/public/docs/``) étant bit-identiques, ces chiffres étaient
en ligne.

Aucune garde ne couvrait ce cas : ``test_methodologie_consistency.py`` ne
vérifie que des CONSTANTES (INFLATION_STRUCTURELLE, PHILLIPS_PENTE_MT,
OUTPUT_GAP_INITIAL), jamais une sortie mesurée ; le garde du tableau agrégé ne
lit que la colonne d'écarts de dette 2035.

CE QUE CE FICHIER GARDE, ET SA LIMITE
-------------------------------------
Il ne « valide » pas les documents : il verrouille une LISTE EXPLICITE de
grandeurs, chacune recalculée par le moteur à chaque exécution et cherchée
telle quelle dans le texte. Ajouter un chiffre mesuré à un document sans
l'ajouter ici le laisse hors garde — c'est la limite, elle est assumée, et
c'est déjà tout ce qui manquait aux six chiffres périmés trouvés en revue.

DEUX OBJETS, ET C'EST LA MOITIÉ DU DÉFAUT
-----------------------------------------
La revue a montré que deux lignes VOISINES du même tableau ne décrivaient pas
le même objet : « ~128,8 % de dette 2030 statu quo » venait du scénario publié
d'un lot antérieur, « ~162 % en 2035 statu quo » du statu quo NU. Les deux
objets existent et sont légitimes :

- **le scénario de référence** ``plf_2026`` — « Budget 2026 (voté) », ce que le
  site sert comme point de départ et compare à chaque programme ;
- **le statu quo NU** — le moteur sans aucune mesure, qui n'est servi nulle
  part mais qui est l'objet de calibration.

Toute grandeur publiée doit donc NOMMER le sien. Les deux jeux sont mesurés
ci-dessous et le test exige que le document cite le bon.
"""
import json
import os
import pathlib

import pytest

from budget_simulator.simulator import BudgetSimulatorV45

_RACINE = pathlib.Path(__file__).resolve().parent.parent
_DOCS = _RACINE / 'docs'


def _mesures_publiees():
    env = (os.environ.get('BUDGETLAB_SCENARIOS_JSON') or '').strip()
    for chemin in ([pathlib.Path(env)] if env else []) + [
            _RACINE / '..' / '..' / 'frontend-react' / 'src' / 'data' / 'scenarios.json']:
        if chemin.exists():
            return json.loads(chemin.read_text(encoding='utf-8'))['plf_2026']['apiMeasures']
    return None


def _fr(valeur, decimales=2):
    """Format français, tel que les documents l'écrivent."""
    return f"{valeur:.{decimales}f}".replace('.', ',')


@pytest.fixture(scope='module')
def statu_quo_nu():
    df, _, _ = BudgetSimulatorV45(periods=10).simulate()
    return df.set_index('Année')


@pytest.fixture(scope='module')
def reference():
    mesures = _mesures_publiees()
    if mesures is None:
        pytest.skip("scenarios.json introuvable (fork moteur public seul)")
    df, _, _ = BudgetSimulatorV45(periods=10, mesures=mesures).simulate()
    return df.set_index('Année')


def _exiger(nom_fichier, fragments):
    texte = (_DOCS / nom_fichier).read_text(encoding='utf-8')
    absents = [f for f in fragments if f not in texte]
    assert not absents, (
        f"{nom_fichier} : chiffres publiés qui ne reproduisent PLUS sur l'état "
        f"livré — {absents}. Un document public périmé est indiscernable d'un "
        f"document faux pour celui qui le lit.")


def test_la_baseline_publiee_est_celle_du_moteur_livre(statu_quo_nu):
    """Les quatre grandeurs de baseline, dans les deux documents publics.

    Ce sont celles qui étaient périmées d'un lot entier : dette 2035 publiée
    ~150 % contre 162,12 mesurés (+12,1 pt), déficit 2035 ~−7,5 % contre
    −11,27 (3,8 pt). Le moteur du même commit le SAVAIT : le corridor de
    calibration avait été recalé à ``155 < dette < 170`` par ce même lot."""
    fragments = [
        _fr(statu_quo_nu.loc[2026, 'Déficit/PIB %']),
        _fr(statu_quo_nu.loc[2030, 'Dette/PIB %']),
        _fr(statu_quo_nu.loc[2035, 'Dette/PIB %']),
        _fr(statu_quo_nu.loc[2035, 'Déficit/PIB %']),
    ]
    for fichier in ('METHODOLOGIE.md', 'EXPLICATION_MODELE_ECONOMIQUE.md'):
        _exiger(fichier, fragments)


def test_le_scenario_de_reference_publie_ses_propres_chiffres(reference):
    """Le scénario SERVI par le site, nommé comme tel.

    La confusion des deux objets est la moitié du défaut : publier un chiffre
    de scénario de référence sous l'étiquette « statu quo » (ou l'inverse)
    rend le document invérifiable, même quand le chiffre est juste."""
    fragments = [
        _fr(reference.loc[2026, 'Déficit/PIB %']),
        _fr(reference.loc[2030, 'Dette/PIB %']),
        _fr(reference.loc[2035, 'Dette/PIB %']),
    ]
    _exiger('METHODOLOGIE.md', fragments)


def test_le_sentier_de_deflateur_publie_est_celui_du_scenario_servi(reference):
    """Le résultat CENTRAL du lot 8, publié à jour et sur le bon objet.

    Le document publiait « 1,22 / 1,43 / 1,43 / 1,46 / 1,46 % » — une série
    qu'aucun objet de l'état livré ne reproduit : c'était le scénario de
    référence d'AVANT le lot 9. Ni le scénario servi ni le statu quo nu ne
    la rendent."""
    sentier = [reference.loc[an, 'Inflation %'] for an in range(2026, 2031)]
    _exiger('METHODOLOGIE.md', [' / '.join(_fr(x) for x in sentier)])
    moyenne = sum(sentier) / 5
    _exiger('METHODOLOGIE.md', [_fr(moyenne, 3)])


def test_les_deux_documents_ne_publient_plus_les_valeurs_perimees():
    """Garde de non-retour sur les six valeurs exactes trouvées en revue.

    Redondante avec les tests ci-dessus tant que le moteur ne bouge pas —
    délibérément : si une correction future ramenait par coïncidence l'un de
    ces nombres, la garde du dessus deviendrait muette sur lui alors que sa
    présence resterait le symptôme d'un copier-coller d'une version périmée.
    Le coût d'une garde redondante est nul, celui d'un chiffre faux en ligne
    ne l'est pas."""
    perimes = ('-5,05', '~129,5%', '~150%', '~-7,5%', '~128,8%',
               '1,22 / 1,43 / 1,43 / 1,46 / 1,46')
    # Deux contextes ont le droit de citer une valeur périmée, et ce sont les
    # deux seuls : l'HISTORIQUE DES VERSIONS (une entrée de changelog dit ce
    # qu'une version a mesuré à sa date — la réécrire serait falsifier
    # l'historique) et le TEXTE DE CORRECTION lui-même (dire « cette page
    # publiait X » est la façon la plus honnête de corriger, et l'interdire
    # pousserait à corriger en silence). Les deux se reconnaissent à un
    # marqueur explicite sur la ligne.
    marqueurs_historiques = ('**Version ', 'jusque-la', "jusqu'au 26/08/2026",
                             'publiait', 'datai', 'perime', 'périmé')
    for fichier in ('METHODOLOGIE.md', 'EXPLICATION_MODELE_ECONOMIQUE.md'):
        for numero, ligne in enumerate(
                (_DOCS / fichier).read_text(encoding='utf-8').splitlines(), 1):
            if any(m in ligne for m in marqueurs_historiques):
                continue
            presents = [p for p in perimes if p in ligne]
            assert not presents, (
                f"{fichier}:{numero} republie des valeurs de baseline "
                f"perimees {presents}, hors de tout contexte historique")


def test_les_copies_servies_au_public_sont_a_jour():
    """Le document canonique est dans ``docs/`` ; le public lit
    ``frontend-react/public/docs/``. Une garde qui ne lirait que le canonique
    laisserait passer une désynchronisation — c'est-à-dire exactement le cas
    où le lecteur voit un chiffre que le dépôt a déjà corrigé.

    ``scripts/sync_public_docs.py --check`` couvre déjà l'égalité des deux
    copies dans ``make check-docs-sync`` ; ce test la rend visible depuis la
    suite moteur, là où les chiffres eux-mêmes sont vérifiés."""
    public = _RACINE / '..' / '..' / 'frontend-react' / 'public' / 'docs'
    if not public.exists():
        pytest.skip("frontend-react/ hors périmètre du fork moteur public seul")
    for fichier in ('METHODOLOGIE.md', 'EXPLICATION_MODELE_ECONOMIQUE.md',
                    'SCENARIOS_POLITIQUES.md'):
        assert (public / fichier).read_text(encoding='utf-8') == \
            (_DOCS / fichier).read_text(encoding='utf-8'), (
                f"{fichier} : la copie servie au public diverge du canonique")
