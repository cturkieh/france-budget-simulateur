"""Bloc moteur — Indice de pouvoir d'achat « RDB-moteur » (v0.6.8).

Remplace l'indice SYNTHÉTIQUE v0.6.7 (croissance du PIB + somme de vingt
coefficients forfaitaires, dont un seul nommé et aucun sourcé). L'indice suit
la définition de l'INSEE : revenu disponible brut (RDB) des ménages, déflaté
par le prix de leur consommation, rapporté au nombre d'unités de consommation
(UC), base 100 en 2025 :

    RDB_t = (RDB_2025 − R_pub) × PIB_t / PIB_2025     revenus privés et de base
          + R_pub × M_t                               rémunérations publiques nettes
          + Σ_mesures [prestations − prélèvements directs
                       + n × rémunérations publiques + salaires privés nets]
    P_t   = D_t × (1 + Σ_mesures τ± × indirects_ménages / C_t)
    PA_t  = 100 × (RDB_t / RDB_2025) / P_t / (1 + γ_UC)^(t − 2025)

- ``PIB_t`` (nominal) porte la croissance RÉELLE et le déflateur du moteur :
  salaires privés, revenus des indépendants, du patrimoine, prestations et
  prélèvements de base évoluent à parts constantes du PIB (hypothèse affichée).
  C'est le seul canal de la croissance : une mesure qui agit sur le PIB
  (impôts d'entreprise, embauches, investissement) n'agit sur l'indice que par
  lui.
- ``R_pub`` = part nette (``n``) de la masse salariale publique 2025 ; ``M_t`` =
  volume TENDANCIEL du statu quo du moteur (``spending_growth_rates``, 0,6 %/an)
  × déflateur : identique en réel pour tous les scénarios. Ni la croissance, ni
  l'écart de production, ni l'indexation passée n'y touchent — la croissance
  n'agit que sur la part privée. Un euro de point d'indice est compté UNE fois,
  par son canal, à sa part nette.
- Canaux € : émis par chaque handler (clé ``menages``, cf.
  ``handlers/_types.CANAUX_MENAGES``), en euros de l'année, écart au statu
  quo. Indice de NIVEAU : l'année t ne lit que les montants de t (aucune
  composition d'une année sur l'autre, aucune atténuation calendaire).
- ``P_t`` : déflateur du moteur ``D_t`` × coin fiscal indirect. ``τ+`` = 1,0 pour
  une hausse, ``τ−`` = 0,5 pour une baisse (Benzarti et al. 2020), appliqué au
  signe de CHAQUE mesure ; ``C_t`` = (1 − taux d'épargne) × RDB de base. Le
  canal ``prelevements_indirects`` est DÉJÀ la part qui pèse sur la
  consommation des ménages : elle dépend de la base de chaque handler, qui
  l'applique (``constants.py`` § part de la fiscalité indirecte).
- ``γ_UC`` : croissance des UC (INSEE), identique pour tous les scénarios.

Sources et valeurs : ``constants.py`` § INDICE DE POUVOIR D'ACHAT. Fonctions
PURES (aucun état d'instance) : l'orchestrateur leur passe les grandeurs de
l'année.
"""
from dataclasses import dataclass
from typing import Dict, Iterable, Mapping

from ..constants import (
    CROISSANCE_UC_ANNUELLE,
    PART_NETTE_REMUNERATIONS_APU,
    RDB_MENAGES_2025_MD_EUR,
    REMUNERATIONS_APU_2025_MD_EUR,
    REPERCUSSION_BAISSE_FISCALITE_INDIRECTE,
    REPERCUSSION_HAUSSE_FISCALITE_INDIRECTE,
    TAUX_EPARGNE_MENAGES_2025,
)

# Rémunérations publiques NETTES perçues par les ménages en 2025 (Md€).
REMUNERATIONS_PUBLIQUES_NETTES_2025_MD_EUR = (PART_NETTE_REMUNERATIONS_APU
                                              * REMUNERATIONS_APU_2025_MD_EUR)


@dataclass(frozen=True)
class RdbAnnee:
    """Décomposition de l'indice d'une année (Md€ courants, prix base 2025 = 1)."""
    rdb_base: float        # RDB sans effet direct des mesures
    rdb_prive: float       # dont part « privée et de base », au PIB nominal
    effet_mesures: float   # Σ canaux de revenu des mesures
    coin_indirect: float   # Σ τ × fiscalité indirecte des ménages (Md€)
    prix: float            # prix de la consommation des ménages
    indice: float          # indice brut (avant la borne de variation annuelle)

    @property
    def rdb(self) -> float:
        return self.rdb_base + self.effet_mesures


def repercussion(montant_md_eur: float) -> float:
    """τ : part d'une variation de fiscalité indirecte répercutée sur les prix."""
    return (REPERCUSSION_HAUSSE_FISCALITE_INDIRECTE if montant_md_eur > 0
            else REPERCUSSION_BAISSE_FISCALITE_INDIRECTE)


def effet_revenu_md_eur(canaux: Mapping[str, float]) -> float:
    """Variation du RDB nominal portée par les canaux d'UNE mesure (Md€)."""
    return (canaux['prestations'] - canaux['prelevements_directs']
            + PART_NETTE_REMUNERATIONS_APU * canaux['remunerations_publiques']
            + canaux['salaires_prives'])


def coin_indirect_md_eur(canaux: Mapping[str, float]) -> float:
    """Fiscalité indirecte d'UNE mesure répercutée sur les prix des ménages (Md€).

    Le canal porte déjà la seule part qui pèse sur la consommation des ménages
    (appliquée par le handler, selon sa base)."""
    montant = canaux['prelevements_indirects']
    return repercussion(montant) * montant


def borner_canaux(canaux: Mapping[str, float], facteur_depenses: float,
                  facteur_recettes: float) -> Dict[str, float]:
    """Canaux d'une mesure dont le budget a été plafonné (5 % / 10 % du PIB) :
    même facteur que le côté budgétaire dont chaque canal est issu."""
    cote_depenses = ('prestations', 'remunerations_publiques')
    return {canal: float(montant) * (facteur_depenses if canal in cote_depenses
                                     else facteur_recettes)
            for canal, montant in canaux.items()}


def canaux_des_mesures(impacts: Mapping[str, object]) -> Iterable[Mapping[str, float]]:
    """Canaux ``menages`` émis par les mesures de l'année (les autres : aucun)."""
    for donnees in impacts.values():
        if isinstance(donnees, dict) and isinstance(donnees.get('menages'), dict):
            yield donnees['menages']


def rdb_base_md_eur(pib_nominal: float, pib_nominal_2025: float,
                    indice_masse_publique: float) -> float:
    """RDB sans mesures : part privée au PIB nominal, part publique à sa masse."""
    privee = RDB_MENAGES_2025_MD_EUR - REMUNERATIONS_PUBLIQUES_NETTES_2025_MD_EUR
    return (privee * pib_nominal / pib_nominal_2025
            + REMUNERATIONS_PUBLIQUES_NETTES_2025_MD_EUR * indice_masse_publique)


def indice_pouvoir_achat(rdb: float, prix: float, annees: int) -> float:
    """100 × RDB réel par UC rapporté à 2025."""
    return (100.0 * rdb / RDB_MENAGES_2025_MD_EUR / prix
            / (1 + CROISSANCE_UC_ANNUELLE) ** annees)


def rdb_annee(impacts: Mapping[str, object], pib_nominal: float, pib_nominal_2025: float,
              deflateur: float, indice_masse_publique: float, annees: int) -> RdbAnnee:
    """Indice de l'année à partir des grandeurs de l'année (aucun état)."""
    base = rdb_base_md_eur(pib_nominal, pib_nominal_2025, indice_masse_publique)
    if not base > 0:
        # PIB nominal et déflateur sont strictement positifs par construction :
        # une base nulle ou négative est un bug d'appel, pas une entrée.
        raise ValueError(f"RDB de base non positif ({base!r})")
    prive = base - REMUNERATIONS_PUBLIQUES_NETTES_2025_MD_EUR * indice_masse_publique
    canaux = list(canaux_des_mesures(impacts))
    effet = sum(effet_revenu_md_eur(c) for c in canaux)
    coin = sum(coin_indirect_md_eur(c) for c in canaux)
    consommation = (1 - TAUX_EPARGNE_MENAGES_2025) * base
    prix = deflateur * (1 + coin / consommation)
    return RdbAnnee(rdb_base=base, rdb_prive=prive, effet_mesures=effet,
                    coin_indirect=coin, prix=prix,
                    indice=indice_pouvoir_achat(base + effet, prix, annees))
