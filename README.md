# france-budget-simulateur

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Tests](https://github.com/cturkieh/france-budget-simulateur/actions/workflows/test.yml/badge.svg)](https://github.com/cturkieh/france-budget-simulateur/actions/workflows/test.yml)

> Moteur économique open source du budget de l'État français. Simulation macro-budgétaire à 5-10 ans des effets de mesures fiscales, sociales et économiques.

Instance officielle : **[francebudget.fr](https://francebudget.fr)**

---

## Pourquoi ce projet

À l'approche de la campagne présidentielle 2027, journalistes, chercheurs et citoyens ont besoin d'un outil pour vérifier eux-mêmes la cohérence financière des programmes politiques — sans dépendre d'un expert tiers dont la coloration politique influencerait la lecture.

Ce moteur est entièrement public, ses **handlers** sont sourcés (chaque coefficient renvoie à un papier IMF / OFCE / IPP / Banque de France / Cour des comptes), ses **scénarios politiques** sont reproductibles bit-à-bit, et la licence AGPL-3.0 empêche juridiquement qu'un fork privé biaise les coefficients et tourne en SaaS sans publier ses modifications.

## Quickstart

```bash
git clone https://github.com/cturkieh/france-budget-simulateur.git
cd france-budget-simulateur
pip install -r requirements.txt
pytest tests/                       # ~337 tests verts attendus (voir badge CI)
uvicorn api:app --reload            # http://localhost:8000/docs
```

## Structure

```
budget_simulator/        Moteur (engine + handlers thématiques)
tests/                   337 tests + golden master + calibration_guard
docs/METHODOLOGIE.md     Hypothèses économiques + sources académiques
docs/MEASURE_REGISTRY.md Registre 3 niveaux auto-généré (sliders → mesures → handlers)
policy_measures.json     Configuration des mesures (transparence calibration)
api.py                   API FastAPI (4 endpoints, voir ci-dessous)
```

## Endpoints API

| Verbe | Chemin | Description |
|-------|--------|-------------|
| `POST` | `/simulate` | Lance une simulation budgétaire (mesures + horizon en années) |
| `GET` | `/scenarios` | Retourne les scénarios prédéfinis (status_quo, austerite, scandinave, relance_verte) |
| `GET` | `/health` | Health check |
| `GET` | `/` | Info API + liste endpoints |
| `HEAD` | `/` | Variante sans body pour health checks plateforme |

Doc OpenAPI interactive : `/docs` une fois l'API lancée.

Exemple :

```bash
curl -X POST http://localhost:8000/simulate \
  -H "Content-Type: application/json" \
  -d '{"mesures": {"impot_societes": {"taux": 0.30}}, "periods": 10}'
```

## Contribuer

Voir **[CONTRIBUTING.md](CONTRIBUTING.md)** pour le détail (le vrai contrat de paramètres, recettes par cas, checklist PR).

Trois cas typiques :

1. **J'ajoute un nouveau handler** (nouvelle mesure budgétaire) → voir `CONTRIBUTING.md` § *Cas 1*.
2. **Je modifie un coefficient existant** → voir § *Cas 2* (sources obligatoires).
3. **Je touche au moteur macro** (Phillips, dette, taux de change) → voir § *Cas 3*.

Toute PR déclenche la CI (337 tests + golden master + gitleaks). Le mainteneur arbitre sur des chiffres, pas sur de la confiance.

## Méthodologie

- **[docs/METHODOLOGIE.md](docs/METHODOLOGIE.md)** — modèle macro, hypothèses, sources académiques.
- **[docs/MEASURE_REGISTRY.md](docs/MEASURE_REGISTRY.md)** — registre des mesures et leurs paramètres (auto-généré, verrou CI anti-drift).
- **[docs/SCENARIOS_POLITIQUES.md](docs/SCENARIOS_POLITIQUES.md)** — scénarios politiques (LR 2027, Renaissance 2027, etc.) avec paramètres injectés et chiffrages.
- **[docs/EXPLICATION_MODELE_ECONOMIQUE.md](docs/EXPLICATION_MODELE_ECONOMIQUE.md)** — pédagogie du modèle pour non-économistes.

## Licence

**AGPL-3.0** — voir [LICENSE](LICENSE).

L'AGPL est un choix politique, pas technique : elle empêche qu'un acteur (parti, think tank, cabinet de conseil) forke ce moteur en privé, biaise les coefficients, et le fasse tourner en SaaS sans publier ses modifications. La faille SaaS du GPL classique est fermée par l'AGPL §13.

## Auteur & contact

Cyril Turkieh — [@cturkieh](https://github.com/cturkieh)

Les questions méthodologiques (économistes, journalistes, chercheurs) sont les bienvenues via les *Discussions* GitHub ou en *Issue*.
