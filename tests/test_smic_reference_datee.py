"""Hausse du SMIC : référence datée, portée à l'année d'application (lot SMIC, équation).

Arbitrage du mainteneur (16/11/2026) : un montant de programme se lit tel qu'il est écrit, comme un SMIC brut
mensuel de son année d'application ; il est comparé au SMIC de référence porté à cette année avec l'indice de
prix des dépenses du moteur (la revalorisation légale fait déjà partie du statu quo). La hausse, fixée l'année
d'origine du levier, est ensuite conservée en pourcentage.

Contrat verrouillé ici, dans le moteur complet :

1. mode cadre : hausse = montant / (référence × indice(origine) / indice(année de référence)) − 1, l'année
   d'origine, et la même hausse les années suivantes ;
2. la valeur du droit en vigueur est neutre à toute origine : elle se lit dans les euros de l'année de
   référence. Sans cette règle, le monde « droit au début » de la composition, à l'horloge du programme,
   verrait une baisse du SMIC, que la composition ajouterait à la hausse du programme ;
3. mode historique : l'origine est l'année de référence, la règle ne change rien, au bit ;
4. l'indice de chaque année est celui que le moteur a calculé cette année-là.
"""
import copy

import pytest

from budget_simulator.constants import (
    PIB_BASE_2025_MD_EUR,
    SALAIRES_BRUTS_2017_MD,
    SALAIRES_BRUTS_2025_MD,
    SMIC_ANNEE_DE_REFERENCE,
    SMIC_BRUT_MENSUEL_REFERENCE_EUR,
    SMIC_TRESOR_SOLDE_PAR_POINT_M_EUR_2017,
)
from budget_simulator.simulator import BudgetSimulatorV45

MONTANT = 2100.0
DEBUT = 2028


class _Releve(BudgetSimulatorV45):
    """Le moteur complet ; garde chaque appel du levier (année, mesures du monde, origine, sortie) et l'indice
    de prix des dépenses lu par le levier."""

    def _apply_smic(self, measure, params, year, gdp, *args):
        sortie = super()._apply_smic(measure, params, year, gdp, *args)
        # Copie : l'orchestrateur complète ensuite le dictionnaire rendu (dépenses, recettes).
        self.appels_smic.append((year, params.get('montant_brut'), self._origine('smic'), gdp,
                                 copy.deepcopy(sortie)))
        self.indices_lus[year] = self.indice_prix_depenses()
        return sortie


def _simuler(mesures, annee_debut=None):
    sim = _Releve(periods=10, mesures=mesures, annee_debut=annee_debut)
    sim.appels_smic, sim.indices_lus = [], {}
    sim.simulate()
    return sim


def _echelle(gdp):
    return SALAIRES_BRUTS_2025_MD / SALAIRES_BRUTS_2017_MD * gdp / PIB_BASE_2025_MD_EUR / 1000.0


def _points(dep, gdp):
    """Hausse en points lue sur la dépense du levier (paie publique + prestations : 150 M€ par point)."""
    t = SMIC_TRESOR_SOLDE_PAR_POINT_M_EUR_2017
    return dep / (-(t['paie_publique'] + t['prestations']) * _echelle(gdp))


def test_l_indice_de_chaque_annee_est_memorise():
    sim = _simuler({'smic': {'montant_brut': MONTANT}}, DEBUT)
    assert set(sim.indices_lus) <= set(sim._indice_prix_par_annee)
    for annee, indice in sim.indices_lus.items():
        assert sim._indice_prix_par_annee[annee] == indice
    assert SMIC_ANNEE_DE_REFERENCE in sim._indice_prix_par_annee


def test_mode_cadre_hausse_contre_la_reference_portee_a_l_annee_d_application():
    sim = _simuler({'smic': {'montant_brut': MONTANT}}, DEBUT)
    idx = sim._indice_prix_par_annee
    reference = SMIC_BRUT_MENSUEL_REFERENCE_EUR * idx[DEBUT] / idx[SMIC_ANNEE_DE_REFERENCE]
    attendu = 100.0 * (MONTANT / reference - 1.0)
    programme = [a for a in sim.appels_smic if a[1] == MONTANT]
    assert {a[0] for a in programme} == set(range(DEBUT, 2036))
    for year, _, origine, gdp, (dep, rec, imp) in programme:
        assert origine == DEBUT
        assert _points(dep, gdp) == pytest.approx(attendu, rel=1e-12), year
        if year == DEBUT:
            assert imp['chomage'] == pytest.approx(attendu / 100 * 0.025, rel=1e-12)
    # L'écart à la référence de 2026 prise telle quelle (sans les prix) est réel : la règle mord.
    assert attendu < 100.0 * (MONTANT / SMIC_BRUT_MENSUEL_REFERENCE_EUR - 1.0) - 0.5


def test_la_valeur_du_droit_en_vigueur_est_neutre_a_toute_origine():
    """Les mondes du droit en vigueur (y compris celui « au début », à l'horloge 2028) ne portent aucune hausse ;
    l'impact composé publié est exactement celui du programme."""
    sim = _simuler({'smic': {'montant_brut': MONTANT}}, DEBUT)
    droit = [a for a in sim.appels_smic if a[1] != MONTANT]
    assert any(a[2] == DEBUT for a in droit), 'non-vacuité : le monde « droit au début » appelle le levier'
    for year, montant, origine, gdp, (dep, rec, imp) in droit:
        assert (dep, rec, imp) == (0, 0, {}), (year, montant, origine)


def test_mode_historique_inchange():
    """Origine = année de référence : hausse = montant / référence − 1, au bit, chaque année."""
    sim = _simuler({'smic': {'montant_brut': MONTANT}})
    attendu = (MONTANT - SMIC_BRUT_MENSUEL_REFERENCE_EUR) / SMIC_BRUT_MENSUEL_REFERENCE_EUR
    for year, _, origine, gdp, (dep, rec, imp) in sim.appels_smic:
        assert origine == SMIC_ANNEE_DE_REFERENCE
        assert _points(dep, gdp) == pytest.approx(100.0 * attendu, rel=1e-12), year
    assert sim.appels_smic[0][4][2]['chomage'] == attendu * 0.025


def test_le_defaut_du_moteur_est_neutre():
    for annee_debut in (None, DEBUT):
        sim = _simuler({'smic': {'montant_brut': SMIC_BRUT_MENSUEL_REFERENCE_EUR}}, annee_debut)
        assert all(a[4] == (0, 0, {}) for a in sim.appels_smic)
