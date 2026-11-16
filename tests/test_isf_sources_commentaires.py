"""Sources de l'ISF citées par le code = celles de la documentation publique (aucun calcul ne change).

Le code de ``handlers/fiscalite_menages.py`` attribuait le taux d'évasion de 15 % et le plafond de
18 Md€ de l'ISF à l'« EU Tax Observatory 2024 ». Ni le *Global Tax Evasion Report 2024* ni le
*Blueprint* G20 ne contiennent ces chiffres ; la documentation publique dit déjà ce qu'ils sont :

- 15 % : « convention de Saez et Zucman (2019), impôt américain à assiette complète ; pas une
  mesure française » (``docs/METHODOLOGIE.md``, § Hypothèses de comportement des impôts à taux).
  Source rouverte : Saez et Zucman, « Progressive Wealth Taxation », *Brookings Papers on Economic
  Activity*, automne 2019, tableau 2 p. 461, ligne « Strong enforcement: 15% evasion rate ».
- 18 Md€ : plafond sans source (« Plafonds réalistes »), qui ne mord jamais.

Le test garde les deux : le commentaire du code cite la convention que la documentation décrit,
et le plafond reste au-dessus de la recette nette maximale, calculée par le moteur lui-même.
"""
import re
from pathlib import Path

from budget_simulator.simulator import BudgetSimulatorV45

ROOT = Path(__file__).absolute().parent.parent
HANDLER = ROOT / 'budget_simulator' / 'handlers' / 'fiscalite_menages.py'
METHODO = ROOT / 'docs' / 'METHODOLOGIE.md'


def test_aucune_source_introuvable_attribuee_dans_le_code():
    texte = HANDLER.read_text(encoding='utf-8')
    assert 'EU Tax Observatory' not in texte


def test_le_taux_d_evasion_cite_la_convention_de_la_documentation():
    doc = METHODO.read_text(encoding='utf-8')
    assert re.search(r'\| ISF \| évasion \| 15 % \| convention de Saez et Zucman \(2019\)', doc)
    code = HANDLER.read_text(encoding='utf-8')
    bloc = code[code.index('# ===== ÉVASION FISCALE ====='):code.index('recettes_nettes = recettes_brutes')]
    assert 'Saez et Zucman' in bloc and '2019' in bloc
    assert 'taux_evasion = 0.15' in bloc


def test_le_plafond_de_18_md_ne_mord_jamais():
    """Recette nette de l'ISF complet à phasage plein (intensité 1, deuxième année) : sous le
    plafond, lue dans le journal du handler (« Nettes … Md€ »), jamais recopiée."""
    sim = BudgetSimulatorV45(periods=10, mesures={'isf_climatique': {'intensite': 1.0}}, annee_debut=2028)
    sim.simulate()
    nettes = [float(m.group(1)) for ligne in sim.debug_logs
              for m in [re.search(r'ISF climatique .*Nettes ([0-9.]+) Md€', ligne)] if m]
    assert nettes, "journal de l'ISF introuvable"
    assert max(nettes) < 18.0
    assert 10.0 < max(nettes) < 10.2  # ≈ 350 000 × 4,512 M€ × 0,75 % × 0,85 = 10,07 Md€
