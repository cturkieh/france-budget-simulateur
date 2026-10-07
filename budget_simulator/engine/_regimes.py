"""Poids de régime conjoncturel, à transition CONTINUE (v0.6.7, lot 3b).

Jusqu'en v0.6.6, chaque dépendance du moteur à la conjoncture était une marche
(``if output_gap < -0.02: multiplier *= 1.15``) : un paramètre qui faisait
franchir le seuil d'un millionième de point déplaçait la dette 2035 de 0,2 à
1,9 pt. Chaque régime passe désormais par un poids w ∈ [0 ; 1], et la réponse
est la moyenne des réponses des deux régimes pondérée par w :
``x *= 1 + (F − 1) × w`` (F = facteur du plein régime). Forme, sources et
demi-largeurs : constants.py, ``REGIME_DEMI_LARGEUR_*``.

Le seuil historique reste écrit au point d'appel, sous la forme de la condition
qu'il remplace : ``output_gap < -0.02`` devient ``en_dessous(output_gap, -0.02)``.
Conditions composées : « A ou B » → ``max``, « A et B » → ``min`` — continus, et
égaux à la logique booléenne d'origine hors des zones de transition.

Exactitude au bit des deux plateaux (statu quo et plein régime inchangés) :
w vaut exactement 0,0 ou 1,0 hors zone (``min``/``max``), et pour F ∈ [0,5 ; 2],
F − 1 est exact (lemme de Sterbenz) donc 1 + (F − 1) × 1,0 = F exactement.
"""
from ..constants import REGIME_DEMI_LARGEUR_ECART

__all__ = ['au_dessus', 'en_dessous', 'poids_recession', 'poids_expansion']


def au_dessus(x: float, seuil: float, demi_largeur: float = REGIME_DEMI_LARGEUR_ECART) -> float:
    """Poids de la condition « x > seuil » : 0 jusqu'à seuil − h, 1 dès
    seuil + h, linéaire entre (0,5 au seuil)."""
    return min(max((x - seuil + demi_largeur) / (2.0 * demi_largeur), 0.0), 1.0)


def en_dessous(x: float, seuil: float, demi_largeur: float = REGIME_DEMI_LARGEUR_ECART) -> float:
    """Poids de la condition « x < seuil » (miroir de ``au_dessus``)."""
    return au_dessus(-x, -seuil, demi_largeur)


def poids_recession(output_gap: float, unemployment_gap: float) -> float:
    """Ex-« gap < −2 % OU écart de chômage > 2 pts » (multiplicateurs)."""
    return max(en_dessous(output_gap, -0.02), au_dessus(unemployment_gap, 0.02))


def poids_expansion(output_gap: float, unemployment_gap: float) -> float:
    """Ex-« gap > 2 % ET écart de chômage < −1 pt » (multiplicateurs, et
    tensions inflationnistes : même condition)."""
    return min(au_dessus(output_gap, 0.02), en_dessous(unemployment_gap, -0.01))
