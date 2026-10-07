"""v0.6.8 — indice de pouvoir d'achat RDB-moteur : fonctions pures (engine/rdb.py).

Identités comptables du module, indépendantes du reste du moteur : un euro
de prestation vaut un euro de RDB, un euro de point d'indice sa part nette,
une hausse de TVA des ménages renchérit les prix de τ+, une baisse de τ−.
"""
import pytest

from budget_simulator.constants import (
    CROISSANCE_UC_ANNUELLE,
    PART_NETTE_REMUNERATIONS_APU,
    RDB_MENAGES_2025_MD_EUR,
    REPERCUSSION_BAISSE_FISCALITE_INDIRECTE,
    REPERCUSSION_HAUSSE_FISCALITE_INDIRECTE,
    TAUX_EPARGNE_MENAGES_2025,
)
from budget_simulator.engine import rdb
from budget_simulator.handlers._types import CANAUX_MENAGES, canaux_menages

PIB0 = 2900.0


def _une_mesure(**canaux):
    return {'m': {'depenses': 0.0, 'menages': canaux_menages(**canaux)}}


def test_indice_2025_vaut_100():
    assert rdb.rdb_annee({}, PIB0, PIB0, 1.0, 1.0, 0).indice == pytest.approx(100.0, abs=1e-12)


def test_sans_mesure_la_part_privee_suit_le_pib_nominal_et_la_publique_son_indice():
    an = rdb.rdb_annee({}, PIB0 * 1.03, PIB0, 1.01, 1.02, 1)
    pub = rdb.REMUNERATIONS_PUBLIQUES_NETTES_2025_MD_EUR
    assert an.rdb_base == pytest.approx((RDB_MENAGES_2025_MD_EUR - pub) * 1.03 + pub * 1.02)
    assert an.prix == pytest.approx(1.01)
    assert an.indice == pytest.approx(
        100 * an.rdb_base / RDB_MENAGES_2025_MD_EUR / 1.01 / (1 + CROISSANCE_UC_ANNUELLE))


@pytest.mark.parametrize('canal, euros_rdb', [
    ('prestations', 1.0),
    ('prelevements_directs', -1.0),
    ('salaires_prives', 1.0),
    ('remunerations_publiques', PART_NETTE_REMUNERATIONS_APU),
    ('prelevements_indirects', 0.0),   # passe par les prix, pas par le revenu
])
def test_un_milliard_par_canal(canal, euros_rdb):
    an = rdb.rdb_annee(_une_mesure(**{canal: 1.0}), PIB0, PIB0, 1.0, 1.0, 1)
    assert an.effet_mesures == pytest.approx(euros_rdb)


@pytest.mark.parametrize('montant, tau', [
    (10.0, REPERCUSSION_HAUSSE_FISCALITE_INDIRECTE),
    (-10.0, REPERCUSSION_BAISSE_FISCALITE_INDIRECTE),
])
def test_fiscalite_indirecte_repercussion_asymetrique(montant, tau):
    an = rdb.rdb_annee(_une_mesure(prelevements_indirects=montant), PIB0, PIB0, 1.0, 1.0, 1)
    conso = (1 - TAUX_EPARGNE_MENAGES_2025) * an.rdb_base
    # Le canal est déjà la part qui pèse sur la consommation des ménages.
    assert an.coin_indirect == pytest.approx(tau * montant)
    assert an.prix == pytest.approx(1 + tau * montant / conso)


def test_repercussion_baisse_moitie_de_la_hausse():
    """Benzarti, Carloni, Harju & Kosonen (JPE 2020) : « prices respond twice
    as much to VAT increases as to VAT decreases »."""
    assert REPERCUSSION_BAISSE_FISCALITE_INDIRECTE == pytest.approx(
        REPERCUSSION_HAUSSE_FISCALITE_INDIRECTE / 2)


def test_signe_par_mesure_pas_sur_le_solde():
    """Une hausse et une baisse de même montant ne s'annulent pas : la
    répercussion s'applique au signe de chaque mesure (asymétrie)."""
    impacts = {'a': {'menages': canaux_menages(prelevements_indirects=5.0)},
               'b': {'menages': canaux_menages(prelevements_indirects=-5.0)}}
    an = rdb.rdb_annee(impacts, PIB0, PIB0, 1.0, 1.0, 1)
    assert an.coin_indirect == pytest.approx(5.0 * (1.0 - 0.5))


def test_mesure_sans_canal_menages_ignoree():
    """Formule ASTEVAL ou handler inactif : pas de clé `menages`, pas d'effet."""
    an = rdb.rdb_annee({'f': {'depenses': 5.0}, 'g': {}}, PIB0, PIB0, 1.0, 1.0, 1)
    assert an.effet_mesures == 0.0 and an.coin_indirect == 0.0


def test_canal_inconnu_refuse():
    with pytest.raises(KeyError):
        canaux_menages(pouvoir_achat=1.0)
    assert set(canaux_menages()) == set(CANAUX_MENAGES)


def test_part_nette_remunerations_publiques():
    """Part nette du brut des agents, REDÉRIVÉE ici des taux légaux de
    service-public.fr (fiche F468), indépendamment de la constante du code :
    retenue pour pension 11,10 % du traitement indiciaire ; CSG-CRDS 9,7 % sur
    98,25 % du brut ; RAFP 5 % des primes, primes plafonnées à 20 % du
    traitement ; avec des primes de 20 à 30 % du brut (non sourcé) → 0,808 à
    0,820 (0,814 à 25 %). La constante (0,80) est cette dérivation arrondie
    par défaut : tolérance 0,01 sous la fourchette, pas au-dessus (borne haute
    du revenu des agents déjà assumée : avant impôt sur le revenu)."""
    def net_du_brut(part_primes):
        traitement = 1 - part_primes
        rafp = 0.05 * min(part_primes, 0.20 * traitement)
        return 1 - 0.111 * traitement - 0.097 * 0.9825 - rafp
    bas, haut = net_du_brut(0.20), net_du_brut(0.30)
    from budget_simulator.constants import PART_NETTE_DU_BRUT_AGENTS_PUBLICS
    assert bas - 0.01 <= PART_NETTE_DU_BRUT_AGENTS_PUBLICS <= haut, (bas, haut)
    assert 247.6 / 370.0 * (bas - 0.01) <= PART_NETTE_REMUNERATIONS_APU <= 247.6 / 370.0 * haut


def test_croissance_uc_conforme_insee_2026():
    """INSEE, Note de conjoncture de juin 2026 : pouvoir d'achat 2026 −0,3 %,
    −0,7 % par UC → croissance implicite des UC 0,4 % (tolérance 0,1 pt)."""
    implicite = (1 - 0.003) / (1 - 0.007) - 1
    assert CROISSANCE_UC_ANNUELLE == pytest.approx(implicite, abs=0.001)
