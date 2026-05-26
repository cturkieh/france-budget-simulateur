# Contribuer à France Budget

> **Discipline documentaire :** un domaine = un fichier canonique. Voir `docs/README.md`.
> N'ajoute jamais un nouveau `.md` de "log de chantier" : l'historique git suffit.

Merci de votre intérêt pour ce projet citoyen ! Ce simulateur budgétaire est un outil pédagogique ouvert à tous.

## Comment contribuer

1. **Forkez** le repo
2. Créez une **branche** (`git checkout -b feature/ma-contribution`)
3. Commitez vos changements
4. Ouvrez une **Pull Request** vers `main`

## Le vrai contrat de paramètres (À LIRE avant de toucher un levier)

Il n'existe **pas un** contrat de paramètres unique. Réflexe naturel
piégeux : éditer `policy_measures.json` pour « changer un paramètre ».
**Pour les leviers `type:"fonction"`, ça n'a aucun effet en prod.**

**La référence canonique = [`docs/MEASURE_REGISTRY.md`](docs/MEASURE_REGISTRY.md)**
: registre **généré** depuis les handlers par
`scripts/generate_measure_registry.py`, **verrouillé en CI** par
`tests/test_measure_registry_sync.py` (toute divergence code↔registre fait
échouer la CI). Il liste, pour chaque levier, les clés réellement lues, les
défauts, les domaines d'intensité et des flags d'audit. Ne JAMAIS l'éditer
à la main (regénéré, écrasé).

Sources, du plus trompeur au vrai contrat :

| # | Source | Rôle réel |
|---|---|---|
| 1 | `policy_measures.json` bloc `parametres` | Filtre `measure_id` + formules ASTEVAL (`type:"formule"`) + métadonnées. **PAS le contrat** des leviers `type:"fonction"`. Rétro-aligné sur le registre (blocs morts supprimés) — ne pas y réintroduire de clé non lue. |
| 2 | `budget_simulator/config.py::load_default_values()` | Défauts statu quo (source unique depuis 2026-05-17). |
| 3 | Sliders `frontend-react/src/components/ExploreCreateSection.jsx` (`convertToAPIFormat`) | Ce que l'utilisateur règle réellement. |
| 4 | **`params.get(...)` / `params[...]` / `… in params` dans les handlers `budget_simulator/handlers/`** | **LE vrai contrat. Source de vérité** (extrait automatiquement → registre). |

Pour ajouter/modifier un paramètre d'un levier `type:"fonction"` :
1. Modifier la lecture `params` du handler (le contrat réel).
2. Ajouter la clé+défaut dans `config.py::load_default_values()`.
3. Ajouter le slider dans `ExploreCreateSection.jsx` (`convertToAPIFormat`).
4. Régénérer le registre :
   `python scripts/generate_measure_registry.py` puis recommiter
   `docs/MEASURE_REGISTRY.md` + `tests/snapshots/measure_registry.json`
   (sinon `test_measure_registry_sync` rougit).
5. (Optionnel) Aligner `policy_measures.json.parametres` pour la cohérence
   doc — sans effet calcul.
6. Lancer `make ci` ET `make test-strict` : golden master doit rester vert.

> Les blocs `parametres` JSON morts historiques (`sante.arrets_reforme`…,
> `fonction_publique.remplacement`, `prestations_indexation.asu_active`)
> ont été **supprimés** (rétro-alignement sur le registre, 2026-05-18,
> golden byte-identique). Le registre généré est désormais la liste
> faisant foi — il ne peut plus se périmer (verrou CI).

## Règles pour le moteur de simulation

Le moteur économique (`budget_simulator/simulator.py`) est calibré sur la littérature académique. **Toute modification de coefficient ou de formule doit respecter ces règles** :

### Obligatoire pour chaque PR touchant le simulateur

- [ ] **Source académique** : tout changement de coefficient doit citer un papier (IMF, OFCE, INSEE, Banque de France, etc.)
- [ ] **Tests de calibration** : `pytest tests/test_calibration_guard.py` doit passer
- [ ] **Mode strict** : lancer au moins une fois `BUDGETLAB_STRICT=1 pytest tests/` pour vérifier qu'aucun handler ne crash silencieusement (l'env var accepte `1`, `true` ou `yes` ; en mode strict une exception levée par un handler escalade au lieu d'être avalée)
- [ ] **Simulation avant/après** : joindre les résultats comparatifs pour au moins 3 scénarios (baseline, investissement, austérité)
- [ ] **Pas de régression** : les tests existants (`pytest tests/`) doivent passer
- [ ] **Garde-fou PA gating** : `pytest tests/test_political_scenarios_2027.py::test_pa_2029_garde_fou_gating_one_time` doit passer (8 scénarios, tolérance ±1.5 pt sur PA 2029)
- [ ] **Convention sémantique respectée** : les coefficients d'indexation (`taux_indexation`, `retraites.indexation`) sont des ratios ∈ [0, 1.2] (1.0 = pleine compensation inflation, 0 = gel total). PAS un taux d'inflation cible (0.02, 0.025).
- [ ] **PA NIVEAU gated** : si l'effet PA modifie un NIVEAU (prix, salaire net, barème), le branchement `pouvoir_achat = ... else 0.0` est gardé par `_is_first_year_change('<measure>_pa', {...})` (pattern recommandé) ou `years_elapsed == 0`.
- [ ] **PA FLUX non gated** : si l'effet PA est une perte/gain renouvelé chaque année (primes annuelles, érosion d'indexation), le calcul reste hors gating. Voir `docs/METHODOLOGIE.md` § "Effets NIVEAU vs FLUX" pour la classification des 12 mesures existantes.

### Ce qui NE sera PAS accepté

- Changements de multiplicateurs sans source académique
- Ajout de mécanismes "bonus" sans base empirique
- Modifications qui rendent toute consolidation autofinancée ou toute austérité sans coût
- Code qui hardcode des clés API ou des secrets

### Ce qui est bienvenu

- Corrections de bugs factuels (données INSEE, paramètres PLF)
- Amélioration de l'interface utilisateur
- Nouveaux scénarios politiques sourcés
- Traductions
- Documentation et pédagogie
- Tests supplémentaires

## Règles pour le frontend

- Respecter le design system (voir `frontend-react/CLAUDE.md`)
- Pas de dépendances lourdes sans discussion préalable
- Accessibilité (a11y) : les composants doivent être navigables au clavier

## Setup local

```bash
# Backend Python
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Remplir les clés API

# Frontend React
cd frontend-react
npm install
npm run dev
```

## Comment tester ma modification

Le repo dispose de plusieurs filets de sécurité (golden master, mini-scénarios standalone,
mode strict). Avant chaque PR, lancer **au minimum** :

```bash
make ci   # équivalent local de la CI : test + test-strict + secrets-scan
```

Voir `make help` pour la liste des cibles. Détail des commandes principales :

| Commande | Quand l'utiliser |
|---|---|
| `make test` | Pytest mode tolérant (122 tests). Comportement prod (les exceptions handler sont avalées et flaguées). |
| `make test-strict` | Pytest avec `BUDGETLAB_STRICT=1` : escalade les exceptions handler. **Bloque les régressions silencieuses** — à utiliser systématiquement avant PR. |
| `make snapshot-diff` | Vérifie que la sim actuelle matche les golden masters (3 157 cellules figées sur 41 scénarios). |
| `make snapshot-baseline` | Régénère les golden masters. **À utiliser uniquement après un changement intentionnel de calibration**, pas pour faire passer les tests. Bloqué par défaut, exige `BUDGETLAB_REGEN=1`. |
| `make secrets-scan` | gitleaks sur l'historique git. Doit retourner 0 leak (les faux positifs sont whitelistés via `.gitleaksignore`). |

### Recettes par cas

#### Cas 1 — J'ajoute un nouveau handler (ex: `mon_nouveau_dispositif`)

1. Ajouter la mesure dans `policy_measures.json` avec `parametres` (default + min + max).
2. Ajouter `'mon_nouveau_dispositif': self._apply_mon_nouveau_dispositif` dans le dict `self.measure_handlers` de `BudgetSimulatorV45.__init__` (`budget_simulator/simulator.py`).
3. Implémenter `_apply_mon_nouveau_dispositif(measure, params, year, gdp, inflation, unemployment) -> (delta_spending, delta_revenue, impacts)`. Sources académiques en commentaire au-dessus de chaque coefficient.
4. `BUDGETLAB_REGEN=1 make snapshot-baseline` (un nouveau handler ajoute son scénario standalone au snapshot — flag explicite car régénération volontaire).
5. `make ci` doit être vert. En particulier `test_all_handlers_covered_by_scenarios` valide que le nouveau handler est bien activé dans ≥1 scénario.

#### Cas 2 — Je modifie un coefficient (ex: élasticité TVA)

1. Identifier le coefficient (chercher avec `grep` dans `simulator.py` ou `constants.py`).
2. Mettre à jour la valeur **avec le nouveau commentaire source** (papier, page, lien stable).
3. `make snapshot-diff` va échouer en rouge avec un message exhaustif (scénario / colonne / année / écart).
4. **Vérifier que les écarts sont cohérents avec ta modification** (sens, magnitude). Si oui :
5. `BUDGETLAB_REGEN=1 make snapshot-baseline` pour figer la nouvelle baseline (le flag confirme que tu as validé l'origine des écarts).
6. Joindre à la PR : ancien snapshot, nouveau snapshot, papier source.

#### Cas 3 — Je touche au moteur macro (croissance, inflation, dette, chômage)

1. C'est la zone la plus sensible. Lire `docs/METHODOLOGIE.md` en entier avant de toucher.
2. Tout changement DOIT être justifié par une source académique (DG Trésor, OFCE, COR, Bozio-Wasmer, IMF, etc.).
3. `make ci` doit être vert.
4. `tests/test_calibration_guard.py` (13 garde-fous économiques) **ne doit pas être modifié pour faire passer le test** — si un garde-fou échoue, la modif probablement viole une cohérence économique fondamentale.
5. **PR à reviewer obligatoirement par 2 personnes** (mainteneur + 1 contributeur économique).

### Exemple PR — checklist test

```markdown
## Checklist test

- [ ] `make test` passe (mode tolérant)
- [ ] `make test-strict` passe (mode BUDGETLAB_STRICT)
- [ ] `make snapshot-diff` passe OU les écarts sont documentés et `make snapshot-baseline` a été lancé
- [ ] `make secrets-scan` retourne 0 leak
- [ ] Si modif de coefficient : source académique citée en commentaire
- [ ] Si nouveau handler : entrée dans `policy_measures.json` + handler dans `measure_handlers`
- [ ] `tests/test_calibration_guard.py` passe sans modification
```

## Après un déploiement (gate parité live — OBLIGATOIRE)

Le backend est déployé sur Render en auto-deploy : **ce n'est pas
instantané**. Tant que le redéploiement n'est pas fini, le site sert
encore l'ancien moteur → un visiteur peut voir des chiffres périmés
(incident réel 2026-05-18 : un scénario ASU+fraude affichait 105,74 au
lieu de 106,22).

Donc, **après chaque push sur `main` (= déploiement prod)** :

```
make verify-deploy
```

Ce gate rejoue un scénario canonique en local ET sur le Render live, et
échoue bruyamment s'ils divergent :

- ✓ vert → le live sert bien le moteur du commit courant. Deploy OK.
- ✗ « retard de déploiement » → attendre la fin du redeploy Render puis
  relancer. **Ne pas déclarer le deploy terminé tant que ce n'est pas vert.**
- ✗ persistant après redeploy complet → vraie régression, investiguer
  (debugging systématique, A/B worktrees, cf. historique mémoire).

URL configurable : `RENDER_API_URL=https://… make verify-deploy`.

## Questions ?

Ouvrez une **Issue** sur GitHub ou contactez-nous via [contact@francebudget.fr](mailto:contact@francebudget.fr).

## Licence

Ce projet est sous licence AGPL-3.0. Voir [LICENSE](LICENSE).
