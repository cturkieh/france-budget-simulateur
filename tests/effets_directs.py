"""Laboratoire des effets DIRECTS d'une mesure (lot 6, calendrier de l'impulsion).

Jusqu'au lot 6, l'impulsion keynésienne d'un budget n'agissait qu'à partir de l'année suivante :
l'année d'entrée en vigueur, la croissance, le chômage d'Okun, le PIB et les flux organiques ne
réagissaient pas encore aux mesures. Plusieurs bancs lisaient donc, cette année-là, l'effet DIRECT
d'un levier (solde égal à ses euros, indice de pouvoir d'achat égal au statu quo sans canal
ménages, indépendance de deux leviers…). Depuis, l'impulsion agit dès l'année de son budget
(engine/orchestrator.py, « calendrier de l'impulsion ») : ces bancs neutralisent EXPLICITEMENT la
rétroaction keynésienne.

Ce que ce laboratoire rend, mesuré à la revue du lot 6 :
- en mode historique, l'année d'entrée (2026) est, au bit, celle du moteur d'avant le lot, à la
  colonne « Multiplicateur » près (mise à 0 ici) ;
- en mode cadre, il n'est PAS le moteur d'avant : il coupe aussi les impulsions du droit en vigueur
  2026-2027, et son état de 2028 en diffère (25 colonnes au statu quo, dont la croissance 2028 :
  1,292 % contre 1,356 %). Les bancs qui l'emploient en mode cadre n'y lisent que des égalités en
  euros (solde contre montants du levier, indépendance de deux leviers), qui ne dépendent pas de cet
  état.

``SansRetroactionKeynesienne`` : multiplicateurs nuls (``get_multiplier`` rend 0) ; les impulsions
sont stockées, aucune n'agit sur la croissance, cette année ni les suivantes. Tous les autres
canaux sont intacts (effets directs sur l'emploi, passage de la TVA dans les prix, prime de taux,
traînée de dette, offre). Les propriétés qui portent sur la rétroaction elle-même (signe du solde
les années suivantes, etc.) restent vérifiées dans le moteur complet, par chaque banc.
"""
from budget_simulator.simulator import BudgetSimulatorV45


class SansRetroactionKeynesienne(BudgetSimulatorV45):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.multipliers.get_multiplier = lambda *a, **k: 0.0
