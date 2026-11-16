"""Rabot uniforme : assiette en euros de l'année.

Source rouverte : Institut Montaigne, « Budget base zéro : décider sous la contrainte », novembre 2025
(PDF de 146 pages, retéléchargé), annexe 4, p. 141 : les dépenses sont projetées « selon ce tendanciel en
volume ajusté par le déflateur du PIB » — en euros COURANTS de 2029 ; p. 87 : « ce rabot uniforme devrait
s'élever à 8 % sur l'ensemble des services publics et prestations sociales ».

Avant : l'assiette était en VOLUME (base 2025 × facteurs de volume, qui « ne portent que le volume ») :
un rabot de 8 % ne valait qu'environ 7,4 % des dépenses de l'année en 2032. Désormais : masses nominales
de l'année (``masse_categorie_nominale``) ; l'AAH, part en espèces de « dépendance », à la même assiette.
"""
import pytest

from budget_simulator.simulator import BudgetSimulatorV45


def _coupes(mesures, annee_debut=2028):
    """{année: coupe totale (Md€)} lue dans les détails du handler, et le contexte de l'appel."""
    sim = BudgetSimulatorV45(periods=10, mesures=mesures, annee_debut=annee_debut)
    coupes, contexte = {}, {}
    original = sim._apply_rabot_uniforme

    def espion(measure, params, year, gdp, inflation, unemployment):
        out = original(measure, params, year, gdp, inflation, unemployment)
        if out[2]:
            coupes[year] = out[2]['rabot_details']['total_coupe']
            masses = {c: sim.masse_categorie_nominale(c) for c in sim.spending_categories_base}
            contexte[year] = {'gdp': gdp, 'masses': masses, 'phasing': out[2]['rabot_details']['phasing'],
                              'facteur_autres': sim._spending_factors['autres'],
                              'indice_prix': sim.indice_prix_depenses(),
                              'ue_exclue': out[2]['rabot_details'].get('contribution_ue_exclue')}
        return out

    sim.measure_handlers['rabot_uniforme'] = espion
    sim._apply_rabot_uniforme = espion
    sim.simulate()
    return coupes, contexte


@pytest.mark.parametrize('annee', [2029, 2030, 2032, 2035])
def test_sans_exclusion_de_la_defense_toute_l_assiette_nominale(annee):
    """Coupe = taux × phasage × Σ masses NOMINALES de l'année (défense et contribution à l'UE non exclues)."""
    coupes, ctx = _coupes({'rabot_uniforme': {'taux_reduction': 0.08, 'exclure_defense': 0, 'exclure_ue': 0}})
    c = ctx[annee]
    assert coupes[annee] == pytest.approx(0.08 * c['phasing'] * sum(c['masses'].values()), rel=1e-12)


def test_la_coupe_suit_les_prix_pas_seulement_le_volume():
    """En 2032, l'indice de prix des dépenses dépasse 1 : la coupe en euros de l'année est plus grande que la
    coupe sur les volumes (base 2025 × facteurs), à taux égal."""
    coupes, ctx = _coupes({'rabot_uniforme': {'taux_reduction': 0.08, 'exclure_defense': 0, 'exclure_ue': 0}})
    c = ctx[2032]
    assert c['indice_prix'] > 1.05
    volume = sum(c['masses'].values()) / c['indice_prix']
    assert coupes[2032] == pytest.approx(0.08 * c['phasing'] * volume * c['indice_prix'], rel=1e-12)
    assert coupes[2032] > 0.08 * c['phasing'] * volume * 1.05


def test_part_reelle_de_l_ancienne_assiette_publiee_liee_a_la_mesure():
    """METHODOLOGIE et CHANGELOG écrivent qu'avec l'ancienne assiette en volume, un rabot de 8 % ne valait
    qu'environ 7,4 % des dépenses de l'année en 2032 : 8 % / indice de prix des dépenses de 2032."""
    from pathlib import Path
    _, ctx = _coupes({'rabot_uniforme': {'taux_reduction': 0.08, 'exclure_defense': 0, 'exclure_ue': 0}})
    part = f"{8 / ctx[2032]['indice_prix']:.1f}".replace('.', ',')
    assert part == '7,4'
    racine = Path(__file__).absolute().parent.parent
    for doc in ('docs/METHODOLOGIE.md', 'CHANGELOG.md'):
        texte = ' '.join((racine / doc).read_text(encoding='utf-8').split())
        assert f"environ {part} % des dépenses de l'année en 2032" in texte, doc


# --- Défense : mécanisme de retrait au-delà des équipements (équation, valeur neutre) ------------------
# La défense exclue vaut une part du PIB de l'année (MONTAIGNE_DEFENSE_PART_PIB), dont la catégorie
# « equipements » (exclue en entier) ; le reste est retiré AU PRORATA des autres catégories, faute de catégorie
# « défense » hors équipement dans le moteur (convention déclarée : la composition sociale de la coupe ne change
# pas). Valeur neutre 0,0 : seule la catégorie « équipements » est exclue, comme avant ; la valeur de la note
# est posée par une release de paramètres distincte.
import budget_simulator.handlers.montaigne as MT  # noqa: E402


@pytest.mark.parametrize('part', [0.02, 0.03])
@pytest.mark.parametrize('annee', [2029, 2032])
def test_defense_exclue_a_une_part_du_pib(monkeypatch, part, annee):
    """Coupe = taux × phasage × (Σ masses nominales − part × PIB de l'année)."""
    monkeypatch.setattr(MT, 'MONTAIGNE_DEFENSE_PART_PIB', part, raising=False)
    coupes, ctx = _coupes({'rabot_uniforme': {'taux_reduction': 0.08, 'exclure_ue': 0}})
    c = ctx[annee]
    assert part * c['gdp'] > c['masses']['defense_equipement']
    attendu = 0.08 * c['phasing'] * (sum(c['masses'].values()) - part * c['gdp'])
    assert coupes[annee] == pytest.approx(attendu, rel=1e-12)


def test_part_neutre_seuls_les_equipements_exclus(monkeypatch):
    """Part 0 : le mécanisme rend exactement l'exclusion d'avant (catégorie « équipements » seule)."""
    monkeypatch.setattr(MT, 'MONTAIGNE_DEFENSE_PART_PIB', 0.0, raising=False)
    coupes, ctx = _coupes({'rabot_uniforme': {'taux_reduction': 0.08, 'exclure_ue': 0}})
    for annee in (2029, 2032):
        c = ctx[annee]
        attendu = 0.08 * c['phasing'] * (sum(c['masses'].values()) - c['masses']['defense_equipement'])
        assert coupes[annee] == pytest.approx(attendu, rel=1e-12)


@pytest.mark.parametrize('part', [0.0, 0.027, 0.03])
@pytest.mark.parametrize('exclure_defense', [0, 1])
@pytest.mark.parametrize('exclure_ue', [0, 1])
def test_gini_du_rabot_sur_la_part_coupee(monkeypatch, part, exclure_defense, exclure_ue):
    """Composition avec la méthode unique du Gini (lot 4 : coefficient × montant d'année pleine de l'année source,
    émis une fois) : le montant des prestations en espèces coupées porte la même part coupée que la coupe, lue sur
    les assiettes de 2025 (contribution à l'UE de 2025 retirée de « autres » si elle est exclue) et le PIB de 2025
    (hors croissance, comme le reste de la règle). Part 0 ou défense non exclue : part coupée 1, le Gini d'avant."""
    import budget_simulator.constants as C
    monkeypatch.setattr(MT, 'MONTAIGNE_DEFENSE_PART_PIB', part, raising=False)
    sim = BudgetSimulatorV45(periods=1)
    sim._reset_state()
    params = {'taux_reduction': 0.08, 'exclure_defense': exclure_defense, 'exclure_ue': exclure_ue}
    _, _, imp = sim._apply_rabot_uniforme({}, params, C.POLICY_START_YEAR, float(C.PIB_BASE_2025_MD_EUR),
                                          0.016, 0.075)
    base = dict(sim.spending_categories_base)
    if exclure_ue:
        base['autres'] -= min(base['autres'], C.CONTRIBUTION_UE_2025_MD)
    if exclure_defense:
        surplus = max(0.0, part * C.PIB_BASE_2025_MD_EUR - base['defense_equipement'])
        part_coupee = 1.0 - surplus / sum(v for c, v in base.items() if c != 'defense_equipement')
    else:
        part_coupee = 1.0
    t = 0.08 * part_coupee
    attendu = -(C.GINI_SOLIDARITE_PAR_MD * (base['minima_sociaux'] + C.AAH_2025_MD_EUR) * t
                - C.GINI_ALLOC_PAR_MD_EUR * base['chomage'] * t
                + C.GINI_PENSIONS_PAR_MD * base['retraites'] * t)
    assert imp['gini'] == pytest.approx(attendu, rel=1e-12)


# --- Défense au périmètre de la note (valeur sourcée) ----------------------------------------------------
# Source rouverte : Institut Montaigne, même note, p. 81 : « dépenses de défense portées à 2,7 % du PIB d'ici
# 2029, soit 91 Md€ », note 113 : « En intégrant les pensions, comme le fait l'OTAN pour le chiffre de 3,5 % » —
# dépenses « incompressibles », exclues de l'assiette avec la charge de la dette et la contribution à l'Union
# européenne. Convention déclarée, aucune source ne tranchant : la part de 2,7 % est gardée chaque année du rabot,
# 2028 compris (la note la fixe pour 2029).
import budget_simulator.constants as C  # noqa: E402

RABOT_NOTE = {'rabot_uniforme': {'taux_reduction': 0.08}}


def test_part_de_defense_de_la_note():
    assert C.MONTAIGNE_DEFENSE_PART_PIB == 0.027


def _contribution_ue(c):
    """Contribution à l'UE de l'année : montant 2025 sur le chemin de la catégorie « autres »."""
    return getattr(C, 'CONTRIBUTION_UE_2025_MD', 0.0) * c['facteur_autres'] * c['indice_prix']


@pytest.mark.parametrize('annee', [2028, 2029, 2030, 2032, 2035])
def test_defense_de_la_note_exclue(annee):
    """Coupe = taux × phasage × (Σ masses nominales − défense à 2,7 % du PIB de l'année − contribution à l'UE),
    dès 2028 (exclusions par défaut de la note)."""
    coupes, ctx = _coupes(RABOT_NOTE)
    c = ctx[annee]
    defense = C.MONTAIGNE_DEFENSE_PART_PIB * c['gdp']
    assert defense > c['masses']['defense_equipement']
    attendu = 0.08 * c['phasing'] * (sum(c['masses'].values()) - defense - _contribution_ue(c))
    assert coupes[annee] == pytest.approx(attendu, rel=1e-12)


# --- Contribution à l'Union européenne : périmètre de l'exclusion (correction) ----------------------------
# Les catégories du moteur somment la dépense primaire des administrations publiques (Insee, tableau 3.201) ;
# « autres » en est le résidu. Cette dépense compte l'opération D76 « Ressources propres de l'UE fondées sur la
# TVA et le RNB » (nomenclature de la page Insee « Dépenses et recettes des administrations publiques en
# 2025 ») : la contribution à l'UE est donc dans « autres ». Montant 2025 : Eurostat, comptes nationaux
# annuels des secteurs (nasa_10_nf_tr), France, administrations publiques (S13), D76 versé = 22 983 M€
# (provisoire). Avant : avec exclure_ue = 1, la contribution restait rabotée dans « autres » ; avec
# exclure_ue = 0, 44 Md€ × taux étaient ajoutés par-dessus, la même dépense coupée deux fois.

def test_contribution_ue_de_2025():
    assert getattr(C, 'CONTRIBUTION_UE_2025_MD', None) == 22.983


@pytest.mark.parametrize('annee', [2029, 2032])
def test_sans_exclusion_de_l_ue_pas_de_double_coupe(annee):
    """exclure_ue = 0 : la contribution, déjà dans « autres », est rabotée une fois, sans montant ajouté."""
    coupes, ctx = _coupes({'rabot_uniforme': {'taux_reduction': 0.08, 'exclure_ue': 0}})
    c = ctx[annee]
    defense = C.MONTAIGNE_DEFENSE_PART_PIB * c['gdp']
    assert coupes[annee] == pytest.approx(0.08 * c['phasing'] * (sum(c['masses'].values()) - defense), rel=1e-12)


@pytest.mark.parametrize('annee', [2028, 2029, 2032])
def test_exclure_ue_retire_exactement_la_contribution(annee):
    """La part retirée de « autres » est la contribution de l'année ; à 8 %, environ 2 Md€ de coupe en moins."""
    _, ctx = _coupes(RABOT_NOTE)
    c = ctx[annee]
    assert c['ue_exclue'] == pytest.approx(_contribution_ue(c), rel=1e-12)
    assert 0 < c['ue_exclue'] < c['masses']['autres']
    if annee >= 2029:
        assert 0.08 * c['phasing'] * c['ue_exclue'] > 1.5


def test_coupe_2029_publiee_liee_a_la_mesure():
    """METHODOLOGIE (§ rabot uniforme) publie la coupe 2029 du scénario de la note (premier budget 2028, 8 %,
    exclusions par défaut) : le chiffre écrit est celui que rend le moteur (arrondi à 0,1 Md€)."""
    from pathlib import Path
    coupes, _ = _coupes(RABOT_NOTE)
    ecrit = f"{coupes[2029]:.1f}".replace('.', ',') + ' Md€ en 2029'
    doc = (Path(__file__).absolute().parent.parent / 'docs' / 'METHODOLOGIE.md').read_text(encoding='utf-8')
    assert ecrit in doc, ecrit
