# Refactor Split Plan — Modularisation du moteur économique

**Statut** : Phase 0 complète, **Phase 1 COMPLÈTE (7/7 handlers splittés)**, **DÉCOUPAGE MOTEUR MACRO COMPLET (8/8)** — `simulator.py` = squelette pur ~800 lignes (vs ~4900). **Re-analyse adverse des dettes faite (2026-05-16)** : sur les 5 findings silent-failure, 1 confirmé / 3 réfutés / 1 re-qualifié ; docstrings + backlog reclassés ; catch growth instrumenté & clôturé. **PHASE 2 EN COURS** (lots A→E, branche `fix/remove-dead-inflation-elasticity`, pas de merge avant la fin). **Item durcissement (branche élasticité inflation morte) RÉSOLU — option B**. **Lot A ✅ TERMINÉ** : commentaire mal nommé supprimé, état mort « exil fiscal » supprimé (option a), test de contrat handlers ajouté (`test_handler_impact_contract.py`, 4 tests) — tous byte-identiques, double validation adverse. **Lot B.1 ✅ TERMINÉ** (mergé) : helpers `_one_time_level`/`_year_phasing`/`_resolve_intensite_or_legacy` créés (`handlers/_phasing.py`) + `POLICY_START_YEAR`, appliqués à `additionnels.py` (Section 6). **Lot B.2 ✅ TERMINÉ** (branche `refactor/phase2-lotB2`) : migration cross-section byte-identique des helpers sur 6 fichiers (`competitivite`, `depenses`, `efficience`, `fiscalite_menages`, `investissements`, `montaigne`) — golden master vide à chaque handler, 220 tests verts, /simplify (1 fix REUSE : bloc csg progressif → `_one_time_level`) + /review Passe 1&2 (1 fix doc `_phasing.py`) CLEAN. **Lot D ✅ TERMINÉ** (branche `refactor/phase2-lotB2`) : Protocols `Handler`/`_SimulatorState` (`handlers/_types.py`, zéro runtime — pattern `_MixinBase` TYPE_CHECKING/object sur 7 mixins, MRO inchangé), `measure_handlers: Dict[str, Handler]` typé ; tests `test_asu_fraude_sociale_contract.py` (producteur 2 branches + consommateur observable) + `test_mixin_architecture.py` (invariant ADR I3 par AST + plancher mécanique contrat Handler 33/arité) ; golden master vide, 237 tests verts normal+strict, /simplify + /review Passe 1&2 CLEAN. **FINDING Phase 2 RÉSOLU — option A** (branche `fix/asu-fraude-anti-double-comptage`) : interaction ASU↔fraude_sociale rendue EFFECTIVE (réduction `0.30·phasing` appliquée APRÈS le cap IGAS) ; couplage producteur/consommateur fragile DISSOUS (source unique `handlers._phasing.asu_phasing`, état mort `self.asu_active`/`asu_phasing` supprimé, ordre-indépendant) ; double validation adverse (éco VALIDE / sûreté → dissolution couplage imposée & faite) ; golden master régénéré (SEULS renaissance_2027 +0,1→0,4 pt & lr_2027 +0,1→0,5 pt Dette/PIB, sens dette ↑, standalone byte-identique) ; 241 tests verts normal+strict, /simplify + /review Passe 1&2 CLEAN. **Lot E ✅ TERMINÉ** (branche `refactor/phase2-lotB2`) : (E.1) helpers `compare_against_snapshot`/`assert_no_silent_handler_failure` extraits dans `tests/snapshots/_compare.py` (dédup ~60 L, comportement préservé + garde anti-faux-vert `min_scenarios`/`cells_compared` ajoutée), (E.2) `test_critical_log_sites.py` (5 tests caplog des sites clip/échec + `logger.warning` AJOUTÉ au clip 10 % PIB total — angle mort d'observabilité comblé, golden master numérique inchangé), (E.3) fixture `statu_quo` session (dédup 4 sims) + suppression fixture morte `baseline_results`. 242 tests verts normal+strict, golden master vide, /simplify + /review Passe 1&2 CLEAN. **Lot C Item 3 ✅ TERMINÉ** (branche `feat/phase2-lotC-durcissement`) : `ExceptionGroup` en `BUDGETLAB_STRICT` (collecte par année + annotation + invariant documenté), path prod inchangé (golden master byte-identique), tests migrés + helper anti-faux-vert + test de collision de préfixe load-bearing, 242 verts normal+strict, /simplify + /review Passe 1&2 CLEAN. **Lot C Item 1 ✅ TERMINÉ + D3 + D6** (branche `feat/phase2-lotC-finalisation`) : registre `INTENSITE_DOMAINS` (5 leviers, fraude_* exclus→Item 2) + `validate_intensite_domain` (`engine/_param_domain.py`, fonction pure) + porte unique `apply_measures` (ValueError strict → ExceptionGroup Item 3, zéro mécanique nouvelle). D1-D4 prises ; D3 `test_measures.py` `50.0→0.30` (0.30 = max domaine fiscalite_patrimoine ; le 0.50 du mini-design = erreur arithmétique corrigée après re-question owner) ; D6 slider `prestations_indexation` max `120→100`. Durcissements revue : `{'intensite':None}`=legacy (no-op aligné `_resolve_intensite_or_legacy`), NaN fermé (`value!=value` avant `<low`, contrat MIXIN intact), token Sentry `INTENSITE_DOMAIN_CLAMP`. **Golden master byte-identique**, 265 verts normal+strict, /simplify + /review Passe 1&2 (fix test fusionné détecté P2) CLEAN, Render byte-identique au local. **Lot C Item 2 ✅ LIVRÉ & MERGÉ sur `main`** (chantier « One Source of Truth contrat params », commit de merge `55d211a`) : le contrat de paramètres est désormais à source unique — registre généré `docs/MEASURE_REGISTRY.md` + `scripts/generate_measure_registry.py` + tests de synchro CI (`test_measure_registry_sync.py`, `test_measure_registry_extraction.py`, `test_param_contract_cleanup.py`), `policy_measures.json` purgé des clés mortes, golden byte-identique, 296 verts. Les artefacts de cadrage de ce chantier (ancienne note d'arbitrage Item 2, mini-design Item 1) sont **clos et conservés dans l'historique git** (supprimés en Phase 1 nettoyage doc, commit `09d0e01`). **Lot C TERMINÉ (3/3) — Phase 2 close.**
**Dernière mise à jour** : 2026-05-18 (Lot C Items 1+2+3 LIVRÉS & mergés sur `main` ; Item 2 = chantier contrat params clos via merge `55d211a`. Phase 2 + Lot C COMPLETS. Doc réaligné sur la réalité de `main` — liens de chantier morts purgés.)
**Owner** : @cturkieh

**État Phase 0** : 0.1 ☑ · 0.2-0.5 ☑ (commit 910a073) · audit secrets ☑ (gitleaks + trufflehog + grep manuel, 0 fuite réelle, 1 faux positif IndexNow whitelisté) · 0.6 ☑ (golden master 616 cellules, ε=1e-3, détection régression vérifiée) · 0.7 ☑ (flag _handler_failed + BUDGETLAB_STRICT) · 0.8 ☑ (coverage 33/33 handlers + 33 mini-scénarios standalone = 2 541 cellules anti-compensation, a déjà détecté un bug latent _apply_fonction_publique) · 0.9 ☑ (CI GitHub Actions : pytest normal + strict + gitleaks) · 0.10 ☑ (Makefile : test, test-strict, snapshot-baseline, snapshot-diff, secrets-scan, ci) · 0.11 ☑ (CONTRIBUTING "Comment tester" : 3 recettes par cas + checklist PR) · **PHASE 0 COMPLÈTE**

**État Phase 1** :
- **1.1 ☑** — Section 6 (additionnels) splittée en `AdditionnelsMixin`. 3 handlers déplacés byte-for-byte (smic, taxe_superprofits, exonerations_salaires). `_logging.py` extrait pour casser le cycle handlers→simulator. Alias `ImpactsDict` activé. Tests `_handler_failed` paramétrés. Plafonds 20 Md€/15 Md€ promus en `logger.warning`. 128/128 verts.
- **1.2 ☑** — Section 6bis (Institut Montaigne) splittée en `MontaigneMixin`. 1 handler déplacé byte-for-byte (rabot_uniforme). Héritage `class BudgetSimulatorV45(AdditionnelsMixin, MontaigneMixin)`. Test `_handler_failed` paramétré ajouté pour `rabot_uniforme`. Garde-fou commenté sur `rabot_details` (sous-dict métadonnée s'écartant du contrat `ImpactsDict`, à aplatir Phase 2). 130/130 verts mode normal et strict, golden master 3 157 cellules byte-identiques.
- **1.3 ☑** — Section 5 (Investissements stratégiques) splittée en `InvestissementsMixin`. **3 handlers** déplacés byte-for-byte (education, transition_ecologique, recherche_publique) — le plan supposait 2 mais l'audit a révélé un 3ème (`_apply_recherche_publique`). Héritage `class BudgetSimulatorV45(AdditionnelsMixin, MontaigneMixin, InvestissementsMixin)`. 3 tests `_handler_failed` paramétrés ajoutés. Backlog Phase 2 enrichi : 3 schedules de phasing distincts identifiés (4 ans innovation verte, 7 ans capital humain, formule linéaire R&D) à factoriser via `_get_year_phasing(callable | list)` ; nuance sémantique `_is_first_year_change(measure, params)` vs `years_elapsed == 0` à préserver lors de la future extraction. Convention d'ordre des mixins explicitée dans la docstring de `BudgetSimulatorV45` (par date d'extraction, pas alphabétique). 136/136 verts mode normal et strict, golden master 3 157 cellules byte-identiques. simulator.py : 4530 → 4236 lignes (-294).
- **1.4 ☑** — Section 4 (Pression fiscale ménages) splittée en `FiscaliteMenagesMixin`. **8 handlers** déplacés byte-for-byte (tva_rate, tva_energie, impot_revenu, csg, cotisations_salariales, elargissement_ir, fiscalite_patrimoine, isf_climatique) — conforme à la prévision du plan. Audit frontière : `_apply_abattement_retraites` / `_apply_prestations_indexation` sont conceptuellement « fiscalité ménages » mais physiquement en Section 2 → laissés en place (discipline « une section physique par commit », traités au split Section 2). Nouveau couplage vs 1.3 : `from ..constants import ETI_TRANCHE_SUPERIEURE` (effet Laffer IR). Héritage `class BudgetSimulatorV45(AdditionnelsMixin, MontaigneMixin, InvestissementsMixin, FiscaliteMenagesMixin)`. 8 tests `_handler_failed` paramétrés ajoutés (152 verts au total) + commentaire `MIXIN_BAD_PARAMS` corrigé (n'affirmait plus à tort que simulator.py ne contient aucun handler — il en reste 20, Sections 1-3 + 7). **État mort détecté par silent-failure-hunter** : `self.csg_progressive_active`, `self.csg_taux_courant`, `self.cotis_salaries_baisse_pts`, `self.patrimoine_variation_pct` sont écrits (commentaire legacy « pour calcul exil fiscal ») mais AUCUN lecteur n'existe dans le package — état mort hérité du monolithe, préservé tel quel par le split, docstring corrigée pour ne pas supposer un consommateur. À nettoyer/câbler Phase 2. 152/152 verts mode normal et strict, golden master 3 157 cellules byte-identiques (diff vide vérifié 2×). simulator.py : 4236 → 3577 lignes (-659).
- **1.5 ☑** — Section 3 (Compétitivité des entreprises) splittée en `CompetitiviteMixin`. **7 handlers** déplacés byte-for-byte (niches_fiscales_tge, niches_sociales_tge, subventions_tge, cotisations_patronales, impot_societes, impots_production, is_exceptionnel_tge) — conforme à la prévision du plan (0 surprise). **Aucun helper local** dans Section 3 (risque principal de la section écarté à l'audit). **Aucun état partagé écrit** (handlers purement fonctionnels — meilleur profil de couplage des 5 mixins). Nouveaux couplages : `import numpy as np` (1er mixin à en dépendre, `np.clip` dans impot_societes), `self.base_params['pib_base']` lu (état base class, via self), 6 constantes `from ..constants` (COEFF_*/PHASING_NICHES_FISCALES_TGE). **Leçon 1.4 appliquée proactivement** : les 6 constantes devenues mortes dans simulator.py après le split ont été retirées symétriquement DANS LE MÊME COMMIT (pas de finding Passe 2 import mort cette fois — vérifié exhaustivement). Héritage `class BudgetSimulatorV45(AdditionnelsMixin, MontaigneMixin, InvestissementsMixin, FiscaliteMenagesMixin, CompetitiviteMixin)`. 7 tests `_handler_failed` paramétrés ajoutés (166 verts au total) + commentaire `MIXIN_BAD_PARAMS` corrigé (« Sections 1-2 » au lieu de « 1-3 »). Finding type-design P3 corrigé : docstring d'invariant « aucune écriture d'état » reformulée de façon intrinsèque (pas de référence cross-fichier fragile à fiscalite_menages.py) + précision sur le sink de logs `self.debug_logs`. /simplify 3 agents CLEAN, /review LOOP Passe 1 (code-reviewer + silent-failure-hunter CLEAN, type-design 8.0/10) → Passe 2 CLEAN. 166/166 verts mode normal et strict, golden master 3 157 cellules byte-identiques (diff vide vérifié 2×). simulator.py : 3577 → 3232 lignes (-345).
- **1.7 ☑ — PHASE 1 COMPLÈTE** — Section 1 (Efficience et organisation) splittée en `EfficienceMixin`, DERNIÈRE section. **5 handlers** déplacés byte-for-byte (fraude_fiscale, fraude_sociale, fonction_publique_reforme, fonction_publique, optimisation_dette) — **surprise d'audit (cas type 1.3)** : le plan prévoyait 4 handlers, `_apply_optimisation_dette` était aussi en Section 1 → l'audit handler par handler l'a rattrapé. **0 helper local**, **numpy non utilisé**, **aucune constante `..constants` ni constante module-level simulator.py** → profil de couplage le plus simple des 7 splits, **aucun retrait symétrique requis**. **Premier mixin CONSOMMATEUR d'état partagé** : `_apply_fraude_sociale` lit en LECTURE SEULE `self.asu_active`/`self.asu_phasing` (sous garde `hasattr`) — côté symétrique du producteur `depenses.py:_apply_asu` (Phase 1.6). Contrat consommateur documenté de façon **intrinsèque** (invariants numérotés que le mixin garantit lui-même : lecture seule, garde `hasattr` porteuse pour le cas « ASU jamais invoquée », indépendance de l'ordre d'exécution déléguée au contrat producteur total) — référence au producteur **nominale et non fragile** (pas de pointeur de ligne cross-fichier). Cohérence producteur/consommateur démontrée point par point sans contradiction ni duplication risquée. Note cosmétique : commentaire mal nommé `# ===== COMPÉTITIVITÉ DES ENTREPRISES =====` entre fraude_sociale et fonction_publique_reforme préservé byte-for-byte (vestige réorg monolithe, 0 effet runtime), encadré dans la docstring comme dette Phase 2 (analogue tolérances rabot_details/description). Héritage `class BudgetSimulatorV45(AdditionnelsMixin, MontaigneMixin, InvestissementsMixin, FiscaliteMenagesMixin, CompetitiviteMixin, DepensesMixin, EfficienceMixin)`. **5 handlers tous couvrables** (aucune exclusion type abattement_retraites) : 5 tests `_handler_failed` paramétrés ajoutés (186 verts au total) + commentaire d'en-tête MIXIN_BAD_PARAMS réécrit (« Phase 1 COMPLÈTE 7/7 ; simulator.py ne contient plus aucun handler thématique, seuls subsistent `_apply_missing_measure`/`_apply_complex_measure` Section 7 legacy »). /simplify 3 agents CLEAN, /review LOOP Passe 1 (code-reviewer + silent-failure-hunter CLEAN, type-design **8.5/10** — progression vs 1.5/1.6=8.0, finding P3 de 1.5 totalement éliminé) → 0 correction code (3 findings type-design = items backlog Phase 2) → Passe 2 CLEAN. 186/186 verts mode normal et strict, golden master 3 157 cellules byte-identiques (diff vide vérifié 2×). simulator.py : 2432 → 2065 lignes (-367). **simulator.py = squelette pur (moteur macro + dispatch + Section 7 legacy + utilitaires), 0 handler thématique.**
- **1.6 ☑** — Section 2 (Maîtrise des dépenses) splittée en `DepensesMixin`. **6 handlers** déplacés byte-for-byte (retraites, sante, chomage_alloc, asu, abattement_retraites, prestations_indexation) — conforme à la prévision du plan (0 surprise). **Aucun helper local** (risque `_apply_asu` ~255 lignes écarté à l'audit : aucun `def` intermédiaire). **Aucune dépendance numpy** (profil d'import le plus simple des 6 mixins). Couplages : `PHASING_RETRAITES_5ANS` (seule constante `..constants` consommée, par `_apply_retraites`) — retrait symétrique dans le même commit (leçon 1.4/1.5, 0 finding import mort) ; constantes locales `RECOUVREMENT_RATE`/`RENONCEMENT_IMPACT`/`DUREE_REF` définies DANS les handlers (voyagent byte-for-byte, pas d'import). **Premier mixin à ÉCRIRE un état partagé doté d'un consommateur RÉEL** (≠ état mort « exil fiscal » 1.4) : `_apply_asu` pose `self.asu_active`/`self.asu_phasing` sur ses DEUX branches, lus par `_apply_fraude_sociale` (Section 1, encore monolithe, futur `EfficienceMixin` Phase 1.7) pour réduire le plafond anti-fraude jusqu'à -30 % (anti double-comptage contrôles IA/ASU). État cross-année `self._chomage_params_prev` (créé paresseusement par `_apply_chomage_alloc`, `del` par l'hôte au reset). Helper host `self._is_first_year_change` (5/6 handlers, via MRO, conforme ADR). Init/reset hôte (simulator.py:558-559/615-616 asu, 627-628 del _chomage_params_prev) NON touchés par le split (hors hunk Section 2, vérifié). Contrat producteur asu_active/asu_phasing documenté de façon **intrinsèque** dans la docstring (leçon type-design P3 de 1.5 non reproduite — note 8.0/10, expression d'invariant supérieure à 1.5). Tolérance `ImpactsDict` : clé `description` (str) dans `_apply_asu`, encadrée comme `rabot_details` (ADR 1.2). Héritage `class BudgetSimulatorV45(AdditionnelsMixin, MontaigneMixin, InvestissementsMixin, FiscaliteMenagesMixin, CompetitiviteMixin, DepensesMixin)`. 5 tests `_handler_failed` paramétrés ajoutés (176 verts au total) + **`abattement_retraites` volontairement EXCLU de MIXIN_BAD_PARAMS** (son unique param `reforme_active` n'est utilisé qu'en `== 1`, jamais en arithmétique → une str ne raise pas, retombe silencieusement sur la branche inactive ; une entrée serait un faux-vert — couvert par le golden master standalone Phase 0.8). Convention de choix de clé MIXIN_BAD_PARAMS précisée (« première opération typée — arithmétique OU comparaison », car `duree`/chomage_alloc raise au comparateur `if duree <= 0:`) + commentaire couverture corrigé (« Section 1 » au lieu de « Sections 1-2 »). /simplify 3 agents CLEAN, /review LOOP Passe 1 (code-reviewer + silent-failure-hunter CLEAN, type-design 8.0/10) → 1 correction commentaire → Passe 2 CLEAN. 176/176 verts mode normal et strict, golden master 3 157 cellules byte-identiques (diff vide vérifié 2×). simulator.py : 3232 → 2432 lignes (-800).

**Dettes test suite identifiées 2026-05-07** (statut post-Lot E 2026-05-17) :
- **[🟡 DIFFÉRÉ — Lot E, décision de scope]** Pattern `with patch('numpy.random.normal', return_value=0):` (~20 sites, 5 fichiers) → fixture `deterministic_random`. **NON fait** : le déterminisme est DÉJÀ structurellement garanti par `np.random.seed(42)` dans `_reset_state` (exécuté avant chaque `simulate()`) ; ces `patch` sont du belt-and-suspenders redondant. Migrer 20 sites = churn élevé + risque (certains `patch` n'enveloppent qu'une sous-section de test → un fixture élargirait la portée) pour un gain comportemental NUL. Item résiduel mineur conscient (ne pas casser pour un gain nul).
- **[✅ FAIT 2026-05-17 — Lot E.3]** 4 simulations statu quo identiques dans test_validation_pa_indexation.py → fixture `statu_quo` (`conftest`, scope session, déterministe). Fixture morte `baseline_results` (0 consommateur) supprimée dans la foulée.
- Tests qui appellent les méthodes privées `_apply_*` directement → exposer une API publique de test ou marker accessor (résiduel — non Lot E)
- Assertions sur sous-chaînes de log (`"Y6: 🚨 CRISE DE CONFIANCE"`) → fragiles au reformatting, idéalement codes d'événement (résiduel — non Lot E ; les tests caplog Lot E.2 assertent des sous-chaînes stables type `CLIP 5% PIB`)
- **[✅ FAIT 2026-05-17 — Lot E.1]** Loop de comparaison cellule-par-cellule dupliqué (Phase 0.6 / 0.8) → `compare_against_snapshot` dans `tests/snapshots/_compare.py` (+ garde anti-faux-vert `min_scenarios`/`cells_compared` qui n'existait dans AUCUN des 2 originaux).
- **[✅ FAIT 2026-05-17 — Lot E.1]** Test `no_silent_handler_failure` dupliqué → helper commun `assert_no_silent_handler_failure` (`_compare.py`).
- `TRACKED_COLUMNS` défini dans run_scenarios_full.py ET coverage_scenarios.py → risque drift snapshots, extraire en module partagé (résiduel — non traité Lot E, candidat au même `_compare.py`/module partagé ultérieurement)

---

## 1. Pourquoi ce plan

`budget_simulator/simulator.py` fait **4900 lignes** monolithiques. Ce monolithe est :

- **Difficile à reviewer** pour un contributeur qui veut juste comprendre une mesure (TVA, retraites, etc.).
- **Risqué à modifier** : un fix sur la fiscalité entreprise charge en mémoire toute la logique des dépenses sociales.
- **Bloquant pour l'open source** : avant d'inviter des contributeurs externes, il faut un repo lisible bloc par bloc.

Le plan ci-dessous **découpe le monolithe en modules thématiques cohérents** sans changer la moindre ligne de logique métier (validé par golden master strict cellule par cellule).

---

## 2. État actuel — ce qui existe déjà

| Brique | Statut | Détail |
|--------|--------|--------|
| Réorganisation thématique du monolithe | ✅ Appliquée | `simulator.py` est déjà ordonné en 8 sections avec headers ASCII (Sec 1 : Efficience, Sec 2 : Maîtrise dépenses, Sec 3 : Compétitivité, Sec 4 : Pression fiscale ménages, Sec 5 : Investissements, Sec 6 : Paramètres additionnels, Sec 6bis : Institut Montaigne, Sec 7-8 : Legacy + utilitaires) |
| Master test — script de génération | ✅ `tests/snapshots/run_scenarios_full.py` | Joue les 8 scénarios politiques (PLF 2026, RN 2027, LFI 2027, PS, Renaissance, LR, Institut Montaigne Rabot/Compétitivité) avec leurs `apiMeasures` exactes. Produit un JSON : 7 indicateurs × 11 ans × 8 scénarios = 616 cellules |
| Snapshots historiques | ✅ 6 fichiers | `golden_master_pa_before_fix.json`, `snapshot_pa_before_sprint7fixes.json`, `_after_sprint7fixes`, `_after_bug1_fix`, `_after_bug3and4_fix`, `_after_bug4_fix` |
| Test de gating PA | ✅ `tests/test_political_scenarios_2027.py` | Vérifie 8 valeurs PA 2029 figées avec tolérance ±1.5 pt |
| Tests calibration | ✅ `tests/test_calibration_guard.py` | 13 tests de garde-fou (cohérence économique : déficit +∞ baisse dette ❌, etc.) |
| Tests handlers spécifiques | ✅ Partiel | `test_carbon_tax_abrogation.py` (4), `test_decay_profiles.py` (9), `test_measures.py` (22), `test_simulator.py` (29), divers (~99 tests réels au total) |

| Brique | Statut | Manque |
|--------|--------|--------|
| Test golden master strict cellule par cellule | ❌ Manquant | Aucun test pytest ne charge `golden_master.json` et ne diffe avec un run actuel — risque de régression silencieuse |
| `except Exception` qui force les deltas à 0 | ❌ `simulator.py:4487-4490` | L'erreur est loguée (`logger.error(... exc_info=True)` ligne 4488) et stockée dans `impacts[id]['erreur']`, mais les `delta_spending`/`delta_revenue` du handler sont silencieusement zéroés. Si la mesure était à valeur default dans le scénario, le golden master matche (0 attendu, 0 obtenu) → régression passe en vert malgré le crash. |
| Couverture handlers vs scénarios | ❌ Non vérifiée | On ne sait pas si tous les 31 handlers sont déclenchés par au moins un scénario avec une valeur non-default |
| `pytest --collect-only` | ❌ Plante | Bug compatibilité Python 3.14 ou import cassé dans un test_*.py legacy |
| CI sur PR | ❌ Aucun `.github/workflows/` | Aucune protection automatique contre PR cassé |
| Split effectif en modules | ❌ Pas commencé | `budget_simulator/` ne contient que `simulator.py`, `config.py`, `constants.py` |
| Convention typée `Handler` | ❌ Aucune | Pas de Protocol Python définissant la signature standard des handlers |
| `MEASURE_REGISTRY.md` | ❌ Inexistant | Pas de mapping public `measure_id → fichier → params → sources` |

---

## 3. Phase 0 — Renforcer le harnais (PRÉ-REQUIS au split)

**Pas négociable. Ne pas splitter avant d'avoir bouché ces trous, sinon régressions silencieuses garanties.**

### Checklist Phase 0

```
☑ 0.1  RÉSOLU 2026-05-07 — `pytest --collect-only` collecte 113 tests proprement
       (résolution implicite via les archivages 0.2-0.5)
       Note : `pytest .` (avec path explicite, pas utilisé en CI/dev) plante encore
       sur test_simulate_asteval_error (bug upstream pytest 9.0.2 + Python 3.14
       sur la capture I/O). Workaround documenté : utiliser `pytest` ou `pytest tests/`,
       jamais `pytest .`.

☑ 0.2  RÉSOLU 2026-05-07 — ~38 fichiers tests/test_*_debug.py / _simple.py /
       _diagnostic sans assertions pytest réelles archivés (étaient dans
       _archive/test_scripts/). Acceptance atteinte : tests/ ne contient que
       des fichiers avec ≥1 `def test_*`.

☑ 0.3  RÉSOLU 2026-05-07 — ~25 scripts test_*.py / audit_*.py de la racine
       archivés (étaient dans _archive/scripts/). Racine = api.py + utilitaires
       actifs uniquement.

☑ 0.4  RÉSOLU 2026-05-07 — 5 scripts tests/reorganize_*.py legacy archivés
       (étaient dans _archive/reorganize/) ; reorganize_simulator_v2.py conservé
       avec docstring « appliqué, ne plus lancer ».

☑ 0.5  RÉSOLU 2026-05-07 — .md d'analyse exploratoire archivés (étaient dans
       _archive/research/). Racine = README.md, CONTRIBUTING.md, LICENSE,
       api.py, __init__.py. (CHANGELOG-SEO.md / SEO-BACKLOG.md retirés le
       2026-05-18, ménage pré-open-source — hors carte canonique.)

> **Note 2026-05-18 — `_archive/` purgé définitivement** (décision PO,
> ménage pré-open-source). Les 7 sous-dossiers (`test_scripts/`, `scripts/`,
> `reorganize/`, `research/`, `test_legacy/`, `tests_artifacts/`,
> `audits-2026-05/`) ont été supprimés du repo. **L'historique git conserve
> l'intégralité du contenu** (récupérable via `git log --all -- _archive/`).
> Toute instruction résiduelle « déplacer dans `_archive/…` » dans ce
> document est **historique** : ne plus créer ce dossier.

☑ 0.6  RÉSOLU 2026-05-07 — golden master strict cellule par cellule
       Implémenté : tests/test_golden_master_full.py + tests/snapshots/golden_master_v1.json
       — Charge le snapshot, replay les 8 scénarios, compare 616 cellules
         (8 scénarios × 7 colonnes × 11 années) avec tolérance ε=1e-3 (cohérent avec
         arrondi 3 décimales du snapshot ; pas ε=1e-6 car le simulator n'expose pas
         la full précision dans les tests)
       — Failure message exhaustif : scénario/colonne/Y{année}: ancien → actuel (Δ=±X),
         instructions de régénération si intentionnel
       — Test bonus : assert qu'aucun handler n'échoue silencieusement (combine 0.6 et 0.7)
       Détection vérifiée manuellement : perturbation TAUX_INTERET_BASE +0.005 → 320 cellules
       divergentes flaguées, message clair. Déterminisme assuré par np.random.seed(42)
       (simulator.py:363,627). 119/119 verts mode normal et strict.

☑ 0.7  RÉSOLU 2026-05-07 — silent failure flagué
       Implémenté dans simulator.py:4487-4501 :
       — `_handler_failed: True` ajouté au dict d'impact quand un handler raise
       — Mode strict via env var BUDGETLAB_STRICT=1/true/yes : escalade au lieu d'avaler
         (à activer en CI / golden master ; off en prod pour ne pas casser le service)
       Tests : tests/test_handler_failure_flag.py (3 tests : flag set, no flag clean,
       strict mode raises). 117/117 verts.

☑ 0.8  RÉSOLU 2026-05-07 — coverage handlers + golden master standalone
       Implémenté :
       — tests/snapshots/coverage_scenarios.py : `build_standalone_scenarios()` génère
         dynamiquement 33 mini-scénarios depuis policy_measures.json (1 handler activé
         à mi-distance default↔max, autres à default)
       — tests/snapshots/standalone_master_v1.json : snapshot 33×7×11 = 2 541 cellules
       — tests/test_handler_coverage.py : 3 tests
         • test_all_handlers_covered_by_scenarios : 33/33 handlers activés (FULL ∪ standalone)
         • test_standalone_master_all_scenarios_match : 2 541 cellules ε=1e-3
         • test_standalone_no_silent_handler_failure : aucun crash en isolation
       Bug latent détecté et fixé pendant cette phase : `_apply_fonction_publique` ligne 1765
       crashait sur `{variation_effectifs:+d}` quand le frontend JSON envoyait un float
       (25000.0). Fix : `int(variation_effectifs)`. C'est exactement le type de régression
       silencieuse que Phase 0.8 doit révéler.
       122/122 verts mode normal et strict.

☑ 0.9  RÉSOLU 2026-05-07 — CI GitHub Actions
       Implémenté : .github/workflows/test.yml
       — Déclencheurs : pull_request + push main
       — Job pytest : Python 3.13, pip install requirements + `pytest>=8,<10` + `pip check`,
         run mode tolérant puis BUDGETLAB_STRICT=1
       — Job gitleaks : binaire direct v8.30.1 (pinné, garantit exit 1 sur finding) avec
         fetch-depth 0 + lecture automatique du .gitleaksignore racine
       — Permissions: contents: read (moindre privilège, repo public)
       — Concurrency group cancel-in-progress sur PR (économie minutes CI)
       Validation locale : 122/122 verts mode normal et strict ; gitleaks 372 commits, 0 leak.

       **TODO branch protection (config GitHub UI, AVANT ouverture publique)** :
       Settings → Branches → Branch protection rules pour `main` :
       — Require pull request before merging
       — Require status checks to pass : `pytest (normal + strict)` + `Secret scan (gitleaks)`
       — Require branches to be up to date before merging

☑ 0.10 RÉSOLU 2026-05-07 — Makefile aligné CI
       Implémenté : `Makefile` racine
       — `make test` / `make test-strict` (mode tolérant / strict)
       — `make snapshot-baseline` régénère les 2 golden masters (combiné + standalone)
       — `make snapshot-diff` lance les 5 tests de master golden
       — `make secrets-scan` lance gitleaks
       — `make ci` enchaîne test + test-strict + secrets-scan (équivalent local CI)
       — `make help` documente les 6 cibles
       Note : pas de `make lint` (ruff non configuré, à ajouter en Phase ultérieure si besoin)

☑ 0.11 RÉSOLU 2026-05-07 — CONTRIBUTING enrichi
       Section "Comment tester ma modification" ajoutée à CONTRIBUTING.md :
       — Tableau des 6 cibles `make` (test, test-strict, snapshot-diff, snapshot-baseline,
         secrets-scan, ci)
       — 3 recettes par cas : "j'ajoute un handler" / "je modifie un coefficient" /
         "je touche au moteur macro" (scénario par scénario, étapes ordonnées)
       — Bloc checklist PR markdown copy-pastable
       Tests régénérations byte-identiques (déterminisme golden masters confirmé).
```

**Estimation Phase 0** : 4-6h de travail concentré.

---

## 4. Phase 1 — Split par section (un commit par section, validable indépendamment)

### Architecture cible

```
budget_simulator/
├── __init__.py
├── config.py                     # déjà présent — lecture policy_measures.json
├── constants.py                  # déjà présent — POLICY_MEASURES_PATH, etc.
├── core/
│   ├── __init__.py
│   ├── constraints.py            # EconomicConstraints, EconomicValidator
│   ├── multipliers.py            # FiscalMultipliers
│   └── simulator.py              # BudgetSimulatorV45 (squelette + dispatch des handlers)
├── engine/                        # moteur macro (sans handlers de mesures)
│   ├── __init__.py
│   ├── growth.py                 # calculate_growth, update_potential_growth
│   ├── inflation.py              # calculate_inflation
│   ├── unemployment.py           # calculate_unemployment
│   ├── revenues.py               # calculate_revenues
│   ├── expenditures.py           # calculate_expenditures
│   ├── debt.py                   # calculate_interest_rate, calculate_interest_payment
│   ├── micro_impacts.py          # calculate_gini_impact, calculate_competitivite
│   └── orchestrator.py           # apply_measures, simulate
└── handlers/                      # un fichier par section thématique du monolithe actuel
    ├── __init__.py
    ├── _types.py                 # Protocol Handler, types partagés
    ├── efficience.py             # Section 1 — Efficience & organisation
    ├── depenses.py               # Section 2 — Maîtrise des dépenses
    ├── competitivite.py          # Section 3 — Compétitivité entreprises
    ├── fiscalite_menages.py      # Section 4 — Pression fiscale ménages
    ├── investissements.py        # Section 5 — Investissements stratégiques
    ├── additionnels.py           # Section 6 — Paramètres additionnels 2027
    └── montaigne.py              # Section 6bis — Scénarios Institut Montaigne
```

### Convention `Handler` (à définir dans `handlers/_types.py`)

```python
from typing import Protocol, Tuple, Dict

ImpactsDict = Dict[str, float]  # keys : 'depenses', 'recettes', 'pouvoir_achat',
                                #        'gini', 'competitivite', 'chomage'

class Handler(Protocol):
    """Signature standard d'un handler de mesure.

    Args:
        measure: Configuration de la mesure (depuis policy_measures.json).
        params: Paramètres slider envoyés par le frontend (ex: {'taux': 0.20}).
        year: Année simulée (2026-2035).
        gdp: PIB en Md€ pour cette année.
        inflation: Taux d'inflation (ex: 0.022).
        unemployment: Taux de chômage (ex: 0.075).

    Returns:
        delta_spending: Md€ de dépenses additionnelles (positif = hausse).
        delta_revenue: Md€ de recettes additionnelles (positif = hausse).
        impacts: Dict des impacts micro-économiques (toutes les clés optionnelles).
    """
    def __call__(
        self,
        measure: Dict,
        params: Dict,
        year: int,
        gdp: float,
        inflation: float,
        unemployment: float,
    ) -> Tuple[float, float, ImpactsDict]: ...
```

### Phase 1 COMPLÈTE (7/7) — clôture, 2026-05-16

Les 7 sections thématiques sont splittées en mixins (`additionnels`,
`montaigne`, `investissements`, `fiscalite_menages`, `competitivite`,
`depenses`, `efficience`). `simulator.py` est désormais un **squelette
pur** : moteur macro + dispatch `measure_handlers` + Section 7 legacy
(`_apply_missing_measure`/`_apply_complex_measure`, fallback ASTEVAL) +
utilitaires. **Plus aucun handler de mesure thématique** dans le
monolithe. État de référence figé :

```bash
make ci              # 186/186 verts (mode normal + strict), gitleaks 0 leak
make snapshot-diff   # golden masters matchent (3 157 cellules figées)
```

**Convention mixin validée sur 7 splits successifs**, golden master
byte-identique à chaque fois, 0 régression. Leçons capitalisées : retrait
symétrique des constantes mortes dans le même commit (1.4→1.7), docstring
de couplage intrinsèque sans référence cross-fichier fragile (P3 de 1.5
éliminé, jamais reproduit), contrat producteur/consommateur d'état partagé
documenté des deux côtés (producteur 1.6 `depenses.py`, consommateur 1.7
`efficience.py`), exclusion documentée plutôt que faux-vert pour les
params jamais utilisés en arithmétique (abattement_retraites 1.6), audit
handler par handler systématique (a rattrapé `recherche_publique` en 1.3
et `optimisation_dette` en 1.7, non prévus par le plan).

**Découpage du moteur macro : COMPLET (8/8, 2026-05-16)** — package
`engine/` extrait (inflation, unemployment, revenues, debt, expenditures,
micro_impacts, growth, orchestrator), `simulator.py` réduit à un
squelette pur de ~800 lignes assemblant les composants via mixins. Golden
master byte-identique sur les 8 splits. **Prochaine étape : Phase 2**
(factorisation post-split, backlog ci-dessous, enrichi des dettes
identifiées pendant les 8 splits — voir notamment le lot
« validation/garde des entrées moteur » et l'item dédié « catch large
silencieux supply-side »).

### ADR Phase 1.2 — Conventions Mixin pour sections complexes

Le pattern Mixin choisi en Phase 1.1 a parfaitement tenu pour Section 6
(3 handlers, 0 helper local, 0 dépendance cross-section). Mais les sections
plus complexes (`depenses.py`, `efficience.py`) introduisent trois risques que
la convention doit traiter explicitement avant qu'on les rencontre :

1. **Typage de `self` pour mypy** — chaque mixin lit `self.mesures`,
   `self.debug_logs`, et potentiellement d'autres attributs d'instance.
   Sans annotation formelle, mypy ne peut pas vérifier que ces attributs
   existent. Solution : déclarer un Protocol `_SimulatorState` dans
   `handlers/_types.py` qui décrit les attributs attendus, et l'utiliser
   comme bound de `self` dans chaque mixin.

2. **Helpers privés** — quand un mixin a des helpers locaux (ex: une
   formule partagée entre 3 handlers), les nommer `_<section>_<name>` (ex:
   `_depenses_age_pivot_neutre`) pour éviter les collisions de noms entre
   mixins composés sur la même classe. Convention : tout helper qui n'est
   pas un `_apply_<measure>` doit avoir le préfixe section.

3. **Dépendances cross-mixin interdites** — un handler d'un mixin ne doit
   PAS appeler un handler d'un autre mixin (ex: `self._apply_retraites()`
   depuis le mixin investissements). Si un croisement est nécessaire,
   extraire la logique partagée comme méthode du `BudgetSimulatorV45`
   lui-même (donc visible dans le monolithe central, pas dans un mixin).
   Cela évite que le MRO devienne un graphe à raisonner mentalement.

**À appliquer dès Phase 1.2** sur le nouveau mixin, et **rétrofitter
Phase 1.1** quand on voudra typer `self` (cf Phase 2 ci-dessous).

**Commande de démarrage Phase 1.2** :

```bash
git checkout -b refactor/split-montaigne
# Créer budget_simulator/handlers/montaigne.py avec MontaigneMixin
# Suivre la procédure stricte S.1 → S.6 ci-dessous.
```

### Procédure stricte par section

**À répéter pour chaque section, dans l'ordre simple → complexe** (le Makefile fait
office de garde-fou — pas besoin de baseline temporaire car le golden master figé
est la baseline) :

```
□ S.1  Vérifier qu'on part d'un état clean
       make ci   # DOIT ÊTRE 100% VERT (sinon, fixer avant de splitter)

□ S.2  Créer budget_simulator/handlers/<section>.py
       — copier les _apply_* de la section depuis simulator.py
       — copier les helpers locaux dépendants (ex: _is_first_year_change utilisé
         par plusieurs handlers)
       — ajouter docstring d'entête : scope, mesures, sources, conventions
       — typage via Protocol Handler (handlers/_types.py)

□ S.3  Délégation depuis simulator.py
       — `from .handlers.<section> import _apply_xxx, _apply_yyy, ...`
       — supprimer les définitions originales du monolithe
       — vérifier que measure_handlers dict pointe vers les imports

□ S.4  Validation stricte (le golden master + standalone master font le travail)
       make snapshot-diff   # DOIT ÊTRE 100% VERT — toute cellule qui bouge = régression
       make test-strict     # DOIT ÊTRE 100% VERT — aucun handler ne crash silencieusement
       make ci              # safety net global

□ S.5  Si OK : commit "refactor(handlers): split <section> from monolith"
       Si KO : git checkout ., analyser le delta cellule par cellule (le message
       d'erreur de make snapshot-diff indique scénario/colonne/année/écart),
       recommencer.

□ S.6  Le golden master ne doit JAMAIS être régénéré pendant le split (pas de
       BUDGETLAB_REGEN=1 make snapshot-baseline). Si une cellule bouge, c'est une
       bug du split à corriger, pas une nouvelle baseline à figer.
```

### Ordre recommandé du split (du plus simple au plus complexe)

```
☑ Section 6 — additionnels.py    (3 mesures : smic, taxe_superprofits, exonerations_salaires) — Phase 1.1, 2026-05-07
☑ Section 6bis — montaigne.py    (1 handler : rabot_uniforme) — Phase 1.2, 2026-05-07
☑ Section 5 — investissements.py (3 handlers : education, transition_ecologique, recherche_publique) — Phase 1.3, 2026-05-07
☑ Section 4 — fiscalite_menages.py (8 handlers : tva_rate, tva_energie, impot_revenu, csg, cotisations_salariales, elargissement_ir, fiscalite_patrimoine, isf_climatique) — Phase 1.4, 2026-05-16
☑ Section 3 — competitivite.py   (7 handlers : niches_fiscales_tge, niches_sociales_tge, subventions_tge, cotisations_patronales, impot_societes, impots_production, is_exceptionnel_tge) — Phase 1.5, 2026-05-16
☑ Section 2 — depenses.py        (6 handlers : retraites, sante, chomage_alloc, asu, abattement_retraites, prestations_indexation — 0 helper local finalement, écrit l'état partagé asu_active/asu_phasing consommé par fraude_sociale) — Phase 1.6, 2026-05-16
☑ Section 1 — efficience.py      (5 handlers : fraude_fiscale, fraude_sociale, fonction_publique_reforme, fonction_publique, optimisation_dette — 0 helper local, CONSOMME asu_active/asu_phasing produits par depenses.py ; le 5ème handler optimisation_dette non prévu, rattrapé à l'audit) — Phase 1.7, 2026-05-16 — **PHASE 1 COMPLÈTE 7/7**
```

### Découpage du moteur macro (après les handlers)

```
☑ engine/inflation.py     — calculate_inflation (InflationMixin) — 2026-05-16, golden master byte-identique, 195 tests verts, /simplify CLEAN, /review LOOP Passe 1 (1 finding doc silent-failure-hunter corrigé) → Passe 2 RÉSOLU. Backlog Phase 2 enrichi : branche d'élasticité recettes morte par construction + paire d'écritures redondante inflation.py/simulate().
☑ engine/unemployment.py  — calculate_unemployment (UnemploymentMixin) — 2026-05-16, golden master byte-identique, 195 tests verts, /simplify (1 finding sur-documentation docstring corrigé) → /review LOOP Passe 1 (1 finding doc silent-failure-hunter corrigé : « purement fonctionnel » inexact car effet de bord debug_logs) → Passe 2. Backlog Phase 2 enrichi : filtre d'impacts chômage tolérant et silencieux (pré-existant).
☑ engine/revenues.py      — calculate_revenues (RevenuesMixin) — 2026-05-16, golden master byte-identique, 195 tests verts, /simplify (1 imprécision factuelle docstring « bootstrap 2026 »→2025 corrigée) → /review LOOP Passe 1 (code-reviewer + silent-failure-hunter CLEAN — invariant recettes_precedentes base organique pré-mesures validé exact ; 1 micro-précision code-simplifier sur la branche transition year==1 appliquée) → Passe 2. SEUL producteur réel de recettes_precedentes (≠ inflation re-persistée par l'orchestrateur) ; aucun garde mort ; imports minimaux (_log_debug seul, ni numpy ni typing).
☑ engine/expenditures.py  — calculate_expenditures (ExpendituresMixin) — 2026-05-16, golden master byte-identique, 195 tests verts, /simplify 3 agents CLEAN → /review LOOP Passe 1 (code-reviewer + code-simplifier RAS ; silent-failure-hunter : garde `gdp > 0 else 0.55` tranché DIFFÉRENT de debt — gdp≤0 impossible par construction → documenté en docstring, PAS de trace Phase 2) → Passe 2. SUPPLY_EFFECTS (growth) NON migrée. Consommateur cross-mixin documenté (MontaigneMixin lit _spending_factors). Invariant bridging Y1 documenté. AUCUNE dette Phase 2 nouvelle.
☑ engine/debt.py          — calculate_interest_rate + calculate_interest_payment (DebtMixin) — 2026-05-16, golden master byte-identique, 195 tests verts, /simplify 3 agents CLEAN → /review LOOP Passe 1 (code-reviewer + code-simplifier CLEAN ; silent-failure-hunter : 1 finding doc corrigé — garde `> 0` masque dette négative, pas seulement nulle) → Passe 2. SUPPLY_EFFECTS (appartient à growth) volontairement NON migrée, restée sur BudgetSimulatorV45. Backlog Phase 2 enrichi : garde dette éteinte ne distingue pas nulle/négative (pré-existant).
☑ engine/micro_impacts.py — calculate_gini_impact + calculate_competitivite (MicroImpactsMixin) — 2026-05-16, golden master byte-identique, 195 tests verts, /simplify (2 micro-précisions docstring filtre appliquées) → /review LOOP Passe 1 → Passe 2. Purement collectrices (0 état écrit). Tombstones Sections 1-8 préservés dans simulator.py. Backlog Phase 2 : lot « validation/garde des entrées moteur » ÉLARGI (gini+competitivite partagent le filtre silencieux de unemployment — remédiation en 1 point d'entrée pour les 3 collecteurs, pas de doublon).
☑ engine/growth.py        — calculate_growth + update_potential_growth + SUPPLY_EFFECTS (GrowthMixin) — 2026-05-16, golden master byte-identique, 195 tests verts, /simplify 3 agents CLEAN → /review LOOP Passe 1 → Passe 2. Le + gros module (~280 l.). SUPPLY_EFFECTS (gardée sur l'hôte en modules 4-5) MIGRE ici (seul consommateur = update_potential_growth) ; DECAY_PROFILE_*/INVESTMENT_FLOW_MEASURES/TRANSFER_MEASURES restent sur l'hôte. Paire producteur→consommateur documentée (update_potential_growth MUTE base_params['croissance_potentielle'] EN PLACE → calculate_growth N+1 ; reset hôte restaure). Backlog Phase 2 enrichi : catch large silencieux supply-side (item dédié, famille « zéro catch silencieux » distincte du lot validation entrées).
☑ engine/orchestrator.py  — simulate + apply_measures + detect_active_measures + update_demography (OrchestratorMixin) — 2026-05-16, golden master byte-identique, 195 tests verts normal+strict, /simplify 3 agents CLEAN (1 reformulation docstring contrat d'ordre) → /review LOOP Passe 1 (3 agents CLEAN) → Passe 2 CLEAN. **DERNIER MODULE — DÉCOUPAGE MOTEUR MACRO COMPLET 8/8.** Assembleur : ne reduplique pas les contrats producteur/consommateur (référence les mixins) ; porte en propre le CONTRAT D'ORDRE (recettes/dépenses base → apply_measures → growth/inflation → update_potential_growth). Retraits symétriques : `import os`, `_BUDGET_KEYS` (gardé local), imports `CHARGES_INTERET_MD_EUR`/`HANDLER_FAILED_KEY` ; `INDEXATION_BASELINE_RATIO` relocalisé vers `constants.py` (foyer canonique) + import `tests/test_pa_sensibilite.py` corrigé. Catch large d'apply_measures = NON silencieux (logger.error + HANDLER_FAILED_KEY + BUDGETLAB_STRICT), distinct du catch silencieux supply-side de growth.py (tracé Phase 2). simulator.py : squelette pur ~800 lignes (vs ~4900 au départ).
```

Ordre de split retenu : du plus simple/feuille au plus couplé (inflation,
unemployment, revenues, debt, expenditures, micro_impacts, growth), puis
`orchestrator` en dernier car `simulate()` appelle les 13 autres méthodes
macro. Pattern Mixin identique à la Phase 1 (MRO neutre, byte-identique).

À ce stade, `simulator.py` ne contient plus que la classe `BudgetSimulatorV45` qui assemble les composants.

---

### Backlog Phase 2 — Factorisation post-split (à attaquer après les 7 sections)

Findings remontés par `/review` LOOP en Phase 1.1 mais reportés pour préserver
le golden master byte-identique pendant le split. À traiter **une fois les 7
sections splittées et le golden master encore vert** :

- **[✅ FAIT 2026-05-16 — Lot B.1] Helper `_one_time_level`** — créé dans
  `budget_simulator/handlers/_phasing.py` (`value if years_elapsed == 0
  else 0.0`), applique le contrat « effet NIVEAU one-time » à
  `additionnels.py` (smic ×4, taxe_superprofits ×2, exonerations ×3).
  Distinction `_is_first_year_change` (changement de params) vs
  `years_elapsed == 0` (année calendaire) **documentée explicitement**
  dans la docstring du module (NB sémantique). Byte-identique (EXPR
  passées pures, évaluées eagerly — vérifié site par site).
  **[✅ FAIT 2026-05-17 — Lot B.2]** : 8 sites `years_elapsed == 0`
  migrés dans `fiscalite_menages.py` — tva_energie (impact_pa,
  impact_gini), csg (impact_pa_taux, impact_gini_taux + bloc progressif
  pa/gini/emploi via fix /simplify REUSE), isf_climatique (impact_gini,
  impact_pa, impact_competitivite). Toutes `value` vérifiées pures et
  non levantes (divisions par littéraux `0.01`/`12` uniquement) — eager
  eval byte-identique confirmé /review Passe 1&2. Sites NON migrés à
  raison : blocs gardés par `self._is_first_year_change(...)` (csg
  competitivite, etc. — sémantique distincte, cf NB docstring) et
  `ifi_actuel` (croissance composée, hors contrat).
- **[✅ FAIT 2026-05-16 — Lot B.1] Helper `_resolve_intensite_or_legacy`** —
  créé dans `_phasing.py`, appliqué à taxe_superprofits + exonerations
  (`additionnels.py`). Générique (`TypeVar`, fabriques simplifiée/legacy).
  Byte-identique (mêmes defaults, edge case `intensite=0.0` préservé,
  testé). **Lot B.2 : aucune application supplémentaire** — le pattern
  « slider `intensite` unique vs legacy » n'a PAS été reconfirmé tel
  quel dans les 6 fichiers migrés (les handlers à slider y sont
  structurés différemment) ; helper conservé pour `additionnels.py`,
  pas de migration forcée.
> **⚠ RÉVISION 2026-05-17 (vérif 3 sous-agents adverses) — le Lot C
> ci-dessous était SOUS-ESTIMÉ. Lire la mémoire
> `project_phase2_lotC_handoff` + `reference_param_contract_architecture`
> AVANT d'attaquer. Synthèse : Item 3 « ExceptionGroup » = **✅ FAIT
> 2026-05-17** (branche `feat/phase2-lotC-durcissement`, voir puce
> dédiée plus bas ; re-vérif adverse préalable des 10 commits Phase 2
> non poussés = 4/4 PASS). Item 1 « borne intensite » = PAS un gate
> global `[0,1]` (`fiscalite_patrimoine` a un domaine légitime
> `[-0.3,0.3]` ; `test_reforme_fiscale.py:129,157` injecte -0.30,
> `test_measures.py:67` injecte 50.0 → un gate global casse `make ci`)
> → validation PAR DOMAINE de levier. Item 2 « `_validate_params` » =
> PAS une puce mais un chantier de réconciliation du contrat de params
> (~5 sources désynchronisées, 8/8 scénarios golden en faux positif si
> validé naïvement contre policy_measures.json — dette produit
> pré-existante alors documentée dans des notes de chantier depuis
> closes ; voir aussi la collision de nommage `asu_active` trouvée à la
> re-vérif, `depenses.py:803`). **MAJ 2026-05-18 : Item 1 ✅ FAIT
> (validation PAR DOMAINE) ; Item 2 ✅ LIVRÉ & MERGÉ sur `main`
> (chantier « One Source of Truth contrat params », merge `55d211a` —
> registre généré `docs/MEASURE_REGISTRY.md` source unique, tests de
> synchro CI, golden byte-identique). Les notes de cadrage/mini-design
> de ce chantier sont closes et conservées dans l'historique git
> (suppression doc Phase 1, commit `09d0e01`). Lot C 3/3 — Phase 2
> close.**

- **[✅ FAIT 2026-05-17 — Lot C Item 1] Validation des bornes `intensite`
  PAR DOMAINE** — `params.get('intensite')` n'accepte plus silencieusement
  les valeurs aberrantes : registre `INTENSITE_DOMAINS` (5 leviers, NON un
  gate global `[0,1]` — `fiscalite_patrimoine` garde `[-0.3,0.3]`) +
  `validate_intensite_domain` (`engine/_param_domain.py`) en porte unique
  dans `apply_measures`. Tolérant=warning+clamp (Sentry token
  `INTENSITE_DOMAIN_CLAMP`), STRICT=ValueError→ExceptionGroup (synergie
  Item 3). NaN fermé, `{'intensite':None}`=legacy préservé, contrat
  MIXIN_BAD_PARAMS (str→TypeError) intact. Golden byte-identique, 265
  verts normal+strict. (Mini-design et livraison de cet item : note de
  chantier close, conservée dans l'historique git.)
- **[✅ LIVRÉ & MERGÉ 2026-05-18 — Lot C Item 2, chantier contrat params]
  Validation des clés de `params` (silent failure hunter Phase 1.3)** —
  `params.get(key, default)` accepte silencieusement toute clé absente : un
  typo dans le JSON `policy_measures.json` ou côté `apiMeasures` frontend
  (ex: `'budgett'` au lieu de `'budget'`) renvoie le default, le handler
  calcule `delta_spending=0`, la garde précoce `if delta_spending == 0 and ...:
  return 0, 0, {}` s'enclenche, et la mesure est silencieusement neutralisée.
  Pattern pré-existant (vérifié dans `_apply_csg`, les 3 handlers du mixin
  investissements, et probablement ailleurs) — pas introduit par les splits.
  **Risque concret** : drift entre le JSON et les clés réellement consommées
  par les handlers, particulièrement délicat lors d'un renommage de slider
  côté frontend qui ne propage pas côté backend. Solution : helper
  `_validate_params(measure_id, params, allowed_keys)` côté `simulator.py`
  qui raise sur clé inconnue en mode `BUDGETLAB_STRICT` (et logge un
  `logger.warning` en mode tolérant pour ne pas casser le service citoyen).
  À chaîner avec le contrat `intensite` ci-dessus pour offrir une porte
  d'entrée unique aux validations de params. **CHANTIER LIVRÉ & MERGÉ
  sur `main` (commit de merge `55d211a`)** : la solution retenue n'est
  pas un `_validate_params` naïf contre `policy_measures.json` (qui
  aurait produit 8/8 golden en faux positif) mais une **source unique
  générée** — `docs/MEASURE_REGISTRY.md` produit par
  `scripts/generate_measure_registry.py` à partir du corps des handlers,
  garde-fou CI (`test_measure_registry_sync.py`,
  `test_measure_registry_extraction.py`, `test_param_contract_cleanup.py`),
  `policy_measures.json` purgé des clés mortes, golden byte-identique,
  296 verts. La note de cadrage (3 options A/B/C) qui a servi à
  l'arbitrage est close et conservée dans l'historique git (suppression
  doc Phase 1, commit `09d0e01`).
- **[✅ FAIT 2026-05-17 — Lot C Item 3] `raise ExceptionGroup` en mode
  `BUDGETLAB_STRICT`** — `engine/orchestrator.py` ne fait plus un `raise`
  nu fail-fast sur la 1ʳᵉ mesure dont le handler crashe : il annote
  l'exception (`e.add_note(f"measure_id=..., year=...")`), la collecte
  dans `strict_failures`, et lève un `ExceptionGroup` APRÈS la boucle
  `for measure_id` (donc AVANT le cap 10 % PIB et l'application des
  totaux — invariant « aucun code intercalé » documenté inline). Portée
  par année (`apply_measures` appelée 1×/an, `strict_failures` local).
  Path tolérant (prod) **strictement inchangé** (golden master
  byte-identique, 0 régénération). Tests `test_handler_failure_flag.py`
  migrés `pytest.raises(TypeError)` → `raises(ExceptionGroup)` + helper
  `_assert_single_typed_failure` qui asserte le CONTENU (type interne +
  note bornée par `,` anti-faux-vert-par-préfixe) ; `MIXIN_BAD_PARAMS`=32 ;
  nouveau test `test_strict_mode_collects_all_failures_without_prefix_
  collision` (paire réelle `fonction_publique` ⊂ `fonction_publique_
  reforme`, prouvé load-bearing red-green) couvrant la collecte multiple
  + la borne. 242 tests verts normal+strict. /simplify (4 fix : helper,
  borne virgule, renommage locales, commentaires) + /review Passe 1
  (#2 MEDIUM invariant explicité, #4 HIGH test de collision ajouté) &
  Passe 2 CLEAN.
- **[✅ FAIT 2026-05-17 — Lot D] Protocol `Handler` réintroduit** dans
  `handlers/_types.py` + `measure_handlers: Dict[str, Handler]` typé dans
  `simulator.py`. Zéro runtime (Protocol non instancié). Plancher
  mécanique en attendant mypy :
  `test_mixin_architecture.py::test_measure_handlers_match_handler_protocol`
  verrouille compte (33) + arité (6 params).
- **[✅ FAIT 2026-05-17 — Lot D] Protocol `_SimulatorState`** (ADR Phase 1.2)
  pour typer `self` des mixins — union exacte des 9 accès host
  (debug_logs, _is_first_year_change, mesures, base_params,
  spending_categories_base, _spending_factors, asu_active, asu_phasing,
  _chomage_params_prev). Pattern `_MixinBase` (TYPE_CHECKING→Protocol /
  runtime→object) répliqué 7× (commentaire anti-DRY identique : NE PAS
  factoriser, casse la liaison self mypy + risque MRO). Scope : 7 mixins
  de handlers (les mixins moteur `engine/*.py` restent hors Lot D —
  même technique applicable plus tard si besoin).
- **[✅ FAIT 2026-05-17 — Lot D] Test de contrat `_apply_asu` (producteur
  2 branches) + consommateur + archi ADR I3** —
  `tests/test_asu_fraude_sociale_contract.py` : (a) `_apply_asu` pose
  `asu_active`/`asu_phasing` sur SES DEUX branches (pollution inverse
  forcée, 7 cas) ; (b) consommateur `_apply_fraude_sociale` lit l'état
  (observable via `debug_logs`, garde `assert DEBUG_MODE` anti faux-vert).
  `tests/test_mixin_architecture.py` : invariant ADR I3 par AST (limite
  assumée & documentée : détection syntaxique du motif littéral
  `self._apply_*(`, indirection non couverte).
  > ⚠ **PÉRIMÉ — SUPPLANTÉ par le bullet suivant (option A, même jour).**
  > Le couplage 2-branches `asu_active`/`asu_phasing` décrit ici a été
  > DISSOUS : `test_asu_fraude_sociale_contract.py` asserte désormais
  > l'INVERSE (`test_no_shared_asu_instance_state` →
  > `assert not hasattr(sim,'asu_active')`). Conservé pour traçabilité
  > historique, ne décrit PLUS le contrat de test courant.
- **[✅ RÉSOLU 2026-05-17 — option A, décision owner] Interaction
  ASU↔fraude_sociale jadis INERTE → rendue EFFECTIVE.** Constat initial :
  la réduction `plafond = 13.0*(1-0.30·phasing) ∈ [9.1,13]` était
  systématiquement shadowée par `min(economies_reelles, 8.0)` (cap IGAS,
  `8.0 < 9.1`) → interaction sans effet sur la sortie. Argument décisif
  (validation éco adverse) : `_apply_asu` EXCLUT déjà 3-6 Md€ de gains
  fraude IA « pour éviter double-comptage avec le slider qui réduit son
  potentiel de 30% si ASU active » → sans contrepartie effective côté
  fraude_sociale, ces montants n'étaient comptés NI là NI ici (vrai
  biais optimiste, ~+0,1→+0,5 pt Dette/PIB sur renaissance_2027 &
  lr_2027). **Décision owner : option A** (rendre effectif), précédent
  branche inflation (option B/suppression — ici A car le mécanisme est
  économiquement fondé, pas un artefact). **Implémentation** :
  réduction `economies_reelles *= (1 - 0.30·asu_phasing)` appliquée
  APRÈS le cap IGAS ; commentaire IGAS corrigé (plafond de NIVEAU ≠
  mécanisme anti-double-comptage — confusion cause-racine du bug).
  **Refonte associée (validation sûreté adverse : dépendance d'ordre
  des handlers détectée)** : couplage producteur/consommateur par
  attribut d'instance `self.asu_active`/`asu_phasing` DISSOUS — source
  unique `handlers._phasing.asu_phasing(mesures, year)` dérivée de
  l'entrée du run (ordre-indépendante) ; état mort supprimé
  (`_apply_asu` écritures + init/reset hôte + Protocol `_SimulatorState`)
  — clôt aussi les items type-design F1/F3. Golden master régénéré
  (SEULS renaissance_2027 + lr_2027 ; standalone byte-identique car
  `_apply_asu` préservé — prédicat `==0` répliqué). Tests de contrat
  réécrits (`test_asu_fraude_sociale_contract.py`, 14 : calendrier
  source unique, interaction effective + magnitude, ordre-indépendance,
  état mort absent). 241 tests verts normal+strict, double validation
  adverse + /simplify + /review Passe 1&2 CLEAN. **À documenter dans
  METHODOLOGIE.md** : source du 0,30 (overlap ASU/fraude, distinct du
  30% erreurs CAF de `ECO_FRAUDE_STRUCT`) + plafond effectif ~5,6 Md€
  à plein régime ASU (hypothèse conservatrice assumée).
- **[✅ RÉSOLU 2026-05-16 — Lot A] Commentaire mal nommé
  `# ===== COMPÉTITIVITÉ DES ENTREPRISES =====` dans `efficience.py`** —
  supprimé (le header correct `# Sous-section 1.2 : Efficience Dépenses`
  existait déjà juste en dessous). Docstring module réécrite à l'état
  présent. Golden master byte-identique (commentaire, 0 effet runtime).
- **[✅ FAIT 2026-05-17 — Lot B.1 + B.2] Helper `_year_phasing(years_elapsed, schedule)`** —
  créé dans `_phasing.py` (liste de coefficients, bornée à la dernière
  valeur, `< 0 → 0.0`, garde-fou schedule vide → `ValueError`). **Lot B.1** :
  schedule dégénéré ``(1.0,)`` (taxe_superprofits, exonerations —
  Section 6). **Lot B.2** : appliqué à `fraude_sociale`
  ``(0.25,0.50,0.75,1.0)`` (efficience), `rabot_uniforme` ``(0.5,1.0)``
  (montaigne), `tva_energie` ``(1.0,)`` + `isf_climatique` ``(0.5,1.0)``
  (fiscalite_menages), `transition_ecologique` ``(0.3,0.5,0.7,1.0)``
  (investissements), `niches_fiscales_tge` `PHASING_NICHES_FISCALES_TGE`
  (competitivite) et `retraites` `PHASING_RETRAITES_5ANS` (depenses) —
  les 2 derniers conservent `year_idx = max(0, …)` en amont (la branche
  `<0` du helper y est neutralisée, byte-identique). **Décisions de
  scope (NON migrés à raison)** : `fraude_fiscale` (efficience) =
  décroissance dynamique post-pic `max(0.70, 1.0 - n·0.05)` non
  exprimable en schedule statique ; `education` (paliers bi-annuels
  `<=1/<=3/<=5` — un 7-tuple répété serait moins lisible et fragile) et
  `recherche_publique` (formule continue `min(1.0, 0.2+n·0.2)` plus
  lisible qu'un tuple magique) gardent leur forme, seul
  `POLICY_START_YEAR` y est appliqué. Le format `schedule` retenu =
  liste indexée clampée (cohérent `constants.PHASING_*`), PAS de
  variante callable (confirmé : les cas observés se couvrent en tuples ;
  un callable serait sur-ingéniérie). NB : les sites migrés mêlant
  `phasing` ET `self._is_first_year_change(...)` (investissements,
  csg) — seul le `phasing` année-calendaire est passé au helper, les
  appels `_is_first_year_change` sont LAISSÉS intacts (sémantique
  distincte préservée, cf NB docstring `_phasing.py`).
- **[✅ FAIT 2026-05-17 — Lot B.1 + B.2] Constante `POLICY_START_YEAR = 2026`** —
  ajoutée à `constants.py`, appliquée aux 3 handlers `additionnels.py`
  (Lot B.1). **Lot B.2** : tous les `year_start = 2026` / `year - 2026`
  des 6 fichiers migrés (efficience ×2, montaigne ×1, investissements
  ×3, fiscalite_menages ×3, competitivite ×1, depenses ×1 + littéral
  dérivé `annees_roi = year - 2026` depenses). **Hors scope confirmé**
  (laissés intacts à raison) : les sites `year - 2025` (epoch baseline
  distincte — efficience ×2, depenses ×2) ne sont PAS
  `POLICY_START_YEAR`, les migrer changerait le runtime. Plus aucun
  littéral `2026` de policy-start dans les handlers (vérifié grep).
- **[✅ FAIT 2026-05-17 — Lot E] Fusion avec « Dettes test suite
  identifiées »** : helper `_compare_against_snapshot` + `no_silent`
  (E.1) et fixture statu quo (E.3) résolus ; `deterministic_random`
  différé conscient (déterminisme déjà structurel) ; résiduels
  (`TRACKED_COLUMNS` dupliqué, accès `_apply_*` directs, sous-chaînes
  de log) tracés dans le bloc unique « Dettes test suite » ci-dessus —
  plus de double localisation.
- **[✅ FAIT 2026-05-17 — Lot E.2] Tests `caplog` pour les warnings
  critiques** — `tests/test_critical_log_sites.py` couvre : clip 20 Md€
  `taxe_superprofits` + clip 15 Md€ `exonerations_salaires`
  (`additionnels.py`, appel direct), clip individuel 5 % PIB + clip total
  10 % PIB (`orchestrator.py`, handlers factices injectés via
  `monkeypatch.setitem(measure_handlers)`), échec handler absorbé
  (`logger.error` + `HANDLER_FAILED_KEY`, chemin tolérant forcé par
  `monkeypatch.delenv('BUDGETLAB_STRICT')`). **Le site clip 10 % PIB total
  n'émettait qu'un `_log_debug`** (invisible hors `BUDGET_DEBUG`) : un
  `logger.warning` y a été AJOUTÉ (cohérent avec le clip 5 % voisin,
  golden master numérique inchangé — vérifié). Chaque test casse si son
  `logger.warning`/`error` est supprimé (assertion positive, non
  tautologique). L'item ASTEVAL pur (`formule` invalide) est couvert via
  le chemin d'échec handler générique de l'orchestrateur (même
  `logger.error`), pas par injection ASTEVAL dédiée.
- **[✅ RÉSOLU 2026-05-16 — Lot A, option (a) / SUPPRESSION] État mort
  « exil fiscal » (silent-failure-hunter Phase 1.4)** — `csg_progressive_active`,
  `csg_taux_courant`, `cotis_salaries_baisse_pts`, `patrimoine_variation_pct`,
  écrits par `fiscalite_menages.py` + init/reset `simulator.py`, AUCUN
  lecteur (re-vérifié grep exhaustif `budget_simulator/` + `api.py` +
  `tests/` + frontend, accès dynamiques inclus). Option (a) retenue :
  3 sites d'écriture + 2 blocs init/reset supprimés, docstring
  `fiscalite_menages.py` réécrite (« N'écrit aucun attribut d'instance »).
  Le `else: impact_competitivite = 0.0` de `_apply_csg` devenu redondant
  (init en amont) retiré dans la foulée. Golden master byte-identique
  (SHA-256 des 33 scénarios standalone identique avant/après — vérifié
  par code-reviewer adverse), 202/202 normal+strict.
> **RE-ANALYSE ADVERSE 2026-05-16** : les 5 findings silent-failure
> remontés pendant les 8 splits du moteur macro ont été re-challengés
> par 4 agents indépendants à mandat de RÉFUTATION (scripts
> d'instrumentation, pas relecture). Verdict : **1 seul confirmé**
> (branche d'élasticité inflation), **3 réfutés** (debt<0 et catch
> growth inatteignables ; filtres d'impacts sans vecteur réel actuel),
> **1 re-qualifié** (paire d'écritures inflation : pas redondante).
> Reclassement honnête ci-dessous — important avant ouverture open
> source (ne pas léguer aux contributeurs des « dettes » fantômes).

- **[✅ RÉSOLU 2026-05-16 — option B / SUPPRESSION] Branche
  d'ajustement d'élasticité recettes morte par construction
  (`orchestrator.py`)** — `calculate_inflation` réécrit
  `self.inflation_precedente` avec la valeur retournée ; le garde
  `if abs(inflation - self.inflation_precedente) > 0.0005:` de
  `simulate()` comparait donc la valeur à elle-même →
  `revenues_after *= elasticity_adjust` ne s'exécutait jamais
  (0/10 ans en run réel ; 6/10 en contrefactuel si l'écriture
  in-méthode bouge).
  **Décision & justification** : la branche a été **SUPPRIMÉE**
  (option B), PAS réactivée. Raison décisive : `calculate_revenues`
  (`engine/revenues.py:43-94`) modélise **déjà** le canal
  inflation→recettes EN NIVEAU via l'élasticité au PIB nominal
  (`nominal_growth = growth + inflation`, élasticité 1,0–1,12,
  convention HCFP/OFCE ≈ 1). La branche aurait ajouté un second canal
  sur la VARIATION d'inflation → **double-comptage**, biais optimiste
  systématique : quantification contrefactuelle sur les 8 scénarios =
  Dette/PIB **~ -0,26 pt en moyenne, max -0,36 pt** (PS 2027), toujours
  même sens (script `tests/instrumentation/counterfactual_inflation_elasticity.py`).
  Inacceptable pour un outil de référence neutre 2027. **Double
  validation adverse** : `feature-dev:code-architect` (validité
  économique : pas d'effet de second ordre légitime perdu — les
  tranches d'IR ne sont pas modélisées) + `feature-dev:code-reviewer`
  (sûreté : branche morte 100 % par construction, golden master
  byte-identique garanti, aucun lecteur caché). **Écriture in-méthode
  de `inflation_precedente` dans `calculate_inflation` CONSERVÉE**
  (changement minimal, risque zéro, protège un futur refactor —
  décision unanime des 2 agents). Docstrings
  `engine/orchestrator.py` + `engine/inflation.py` mises à jour
  (tombstone inline). Branche `fix/remove-dead-inflation-elasticity`.

- **[RÉFUTÉ comme vecteur réel → LOW préventif] Filtres d'impacts
  tolérants (`unemployment.py`, `micro_impacts.py`)** — le finding
  initial (impact non-dict ou clé mal orthographiée silencieusement
  absorbé) est **sans vecteur atteignable aujourd'hui** (re-analyse
  adverse) : `apply_measures` garantit toujours un dict (un non-dict
  crashe **bruyamment** à `measure_impacts['depenses']` avec
  `logger.error` + `HANDLER_FAILED_KEY` + escalade `BUDGETLAB_STRICT`,
  AVANT d'atteindre les collecteurs) ; grep exhaustif des 33 handlers :
  **aucune** clé `chomage`/`gini`/`competitivite`/`pouvoir_achat` mal
  orthographiée n'existe ; les clés custom (`description`,
  `rabot_details`, `emploi`…) sont ignorées À RAISON (métadonnées, cf
  `_types.py`). Les gardes `isinstance` sont du code défensif inerte.
  Risque résiduel **purement préventif/futur** (typo introduit lors
  d'un futur renommage de handler, non rattrapé). Sévérité **LOW**.
  Réponse proportionnée **[✅ FAITE 2026-05-16 — Lot A]** :
  `tests/test_handler_impact_contract.py` itère les 33 handlers (via
  `build_standalone_scenarios`, toggles forcés à leur valeur activante),
  asserte que le 3ᵉ retour est un dict et que ses clés ⊂ ensemble connu
  (canonique + traçabilité allowlistée bâtie depuis la réalité). 4 tests :
  couverture 33, non-vacuité (anti-faux-négatif `abattement_retraites`),
  no-crash (ferme l'angle mort catch absorbé hors `BUDGETLAB_STRICT`),
  no-clé-inconnue (détecteur de dérive). **PAS** de durcissement des
  collecteurs ni de `_validate_params` (conforme à l'esprit LOW préventif).

- **[RÉFUTÉ — inatteignable, DÉCLASSÉ, aucune Phase 2] Garde
  `debt_total > 0` (`debt.py`)** — le finding « dette négative
  silencieusement absorbée » est **réfuté** : `debt < 0` est
  **mathématiquement inatteignable** dans les bornes du modèle
  (re-analyse adverse, script). `debt` part de ~3461 Md€ ; le
  désendettement est borné par le plafond de mesures 10 % PIB (FMI
  2010) + la charge d'intérêts toujours soustraite. Plancher empirique
  mesuré = **2238 Md€** sur 8 scénarios + 1 scénario austérité maximale
  (90 trajectoires-années, jamais ≤ 0). Statut **identique au garde
  `gdp <= 0` de `ExpendituresMixin`** : branche défensive inerte,
  `debt_total == 0` reste un anti-division-zéro légitime.
  **Aucune dette Phase 2** — correction documentaire seule (faite :
  docstrings `debt.py` + `expenditures.py`).

- **[RÉFUTÉ comme silent-failure atteignable → CLÔTURÉ par
  instrumentation] Catch large supply-side de `update_potential_growth`
  (`growth.py`)** — le `except Exception` est **inatteignable en run
  normal** (re-analyse adverse : aucune opération du bloc ne peut lever
  — `_get_default_values` = dict littéral pur, `isinstance` neutralise
  les types tordus, `np.log2(1+delta)` avec `delta>0.1` garanti ; le
  seul vecteur théorique non-dict crashe **bruyamment en amont** dans
  `detect_active_measures`). Sévérité réelle **LOW / défensif**, pas un
  silent-failure atteignable. **Traité maintenant** (golden-master-safe,
  hors Phase 2, le bloc ne s'exécutant jamais sur input atteignable) :
  ajout de `logger.error(exc_info=True)` (auto-capté Sentry via
  LoggingIntegration, no-op sans DSN) + commentaire d'inatteignabilité,
  `_potential_growth_bonus = 0.0` conservé. Conforme à la règle « zéro
  catch silencieux » pour le cas d'un futur refactor qui le rendrait
  atteignable. **Item Phase 2 supprimé** (résolu). Test d'injection
  d'exception ajouté pour verrouiller la dégradation gracieuse
  observable.

Toutes ces factorisations changent le runtime (helpers extraits, validation
en amont, typing strict). Elles doivent être **vérifiées une à une** avec
`make snapshot-diff` après chaque extraction pour préserver les 3 157 cellules.

---

## 5. Phase 2b — Documentation contributeurs ✅ **LIVRÉE (2026-05-20)**

```
☑ docs/MEASURE_REGISTRY.md (autogénéré)
   ✅ Livré dans le chantier « One Source of Truth contrat params » (Lot C Item 2,
      merge `55d211a` du 2026-05-18). Script `scripts/generate_measure_registry.py`
      (extraction AST des lectures `params.get/[]/in` dans les handlers + lambdas
      legacy + INTENSITE_DOMAINS). Verrou CI `tests/test_measure_registry_sync.py`.

☑ Docstring d'entête par module handlers/<section>.py
   ✅ Déjà en place depuis Phase 1.x (9 modules, ~25-78 lignes par module) :
      scope + sources académiques + conventions gating (NIVEAU/FLUX,
      `_is_first_year_change` vs `years_elapsed == 0`) + couplages hôte +
      tolérances ImpactsDict + renvois METHODOLOGIE.md. Audit Phase 2b
      (2026-05-20) : 4 références à « Phase 2 » périmées corrigées
      (Phase 2 close — `_types.py`, `depenses.py`, `fiscalite_menages.py`,
      `montaigne.py`).

☑ Recettes contributeurs (« j'ajoute un nouveau handler », « je modifie un
   coefficient », « je touche au moteur macro »)
   ✅ ABSORBÉES dans `CONTRIBUTING.md` (§ « Recettes par cas », Cas 1/2/3,
      l.130-153). PAS de fichier `docs/CONTRIBUTING_HANDLERS.md` séparé pour
      éviter le drift entre deux docs contributeurs cohabitantes.

☑ Mise à jour CONTRIBUTING.md + CODEOWNERS GitHub
   ✅ `CONTRIBUTING.md` étoffé (200 lignes) avec « Le vrai contrat de
      paramètres » + checklist PR + recettes par cas + verify-deploy.
   ✅ `.github/CODEOWNERS` créé : mainteneur unique `@cturkieh` (stratégie
      open source sobre, à découper par dossier le jour où il y a >1
      contributeur régulier).

☑ Audit cohérence docs UI ↔ code + verrou CI anti-dérive (ajouté à Phase 2b)
   ✅ Audit Phase 4 inflation : MAJ `METHODOLOGIE.md` §11 (nouvelle section
      « Inflation et Courbe de Phillips », table Calibration Baseline scindée
      terme structurel/cible BCE, Version 3.2).
   ✅ Audit général : 3 divergences corrigées (chômage post-réforme avril 2025,
      impôts production post-suppression CVAE, ASU plafonnement défaut vs max).
   ✅ Verrou CI `tests/test_methodologie_consistency.py` : 9 constantes
      économiques verrouillées (PIB, Dette, Chômage, NAIRU, INFLATION_STRUCTURELLE,
      CROISSANCE_POTENTIELLE, TAUX_INTERET_BASE, okun, debt_drag). 4 tests
      (cohérence parser↔code, présence doc, rouge automatisé par mutation,
      garde-fou parser).
```

**Reste à faire (chemin critique open source 2027)** : Phase 3 split repo
public AGPL (cf § 6 ci-dessous) + emails caution académique OFCE/IPP + presse.

---

## 6. Phase 3 — Open source split

### Stratégie repo

| Composant | Licence/Repo | Justification |
|-----------|--------------|---------------|
| `budget_simulator/` | **Public AGPL-3.0** — `france-budget-simulateur` (nouveau repo) | Moteur scientifique sourcé : doit être auditable par journalistes, chercheurs, citoyens |
| `policy_measures.json` | **Public** | Configuration des mesures, transparence requise pour la calibration |
| `tests/` | **Public** | Garde-fous + master test = essence du sérieux du projet |
| `docs/METHODOLOGIE.md` | **Public** | Documentation des hypothèses économiques |
| `api.py` (endpoints simulate uniquement) | **Public minimal** | Permet à un fork de monter une instance backend |
| Partie analyse IA Kimi (orchestrateur LLM, prompts) | **Privé** — `budgetlab-france` (repo actuel) | Valeur ajoutée produit + clés API |
| `frontend-react/` | **Privé** | Identité visuelle Crimson Swiss + UX = produit |
| Scripts deploy Render/Vercel | **Privé** | Configuration spécifique à l'instance officielle |

### Checklist hygiène pré-split (audit pré-open-source 2026-05-17, re-challengé)

Findings O3/O4/O6 CONFIRMÉS mais NON corrigés dans le repo privé (le
repo privé a légitimement besoin de Kimi/frontend) → à exécuter AU
MOMENT du split, pas avant :

```
□ O3 — api.py PUBLIC réduit : exposer UNIQUEMENT /simulate + /scenarios
   + /health + / (modèles pydantic associés). RETIRER `from sentry_setup
   import`, le bloc KIMI_API_KEY/KIMI_* et l'endpoint /api/claude-analysis
   (l.~14, ~34-44, ~226-296 de l'api.py actuel). NE JAMAIS publier
   l'api.py actuel tel quel (fuite mécanique IA privée).
□ O4 — EXCLURE du subtree tous les artefacts dev racine. (Note : le
   `json_cleanup_plan.txt` historiquement visé ici a depuis été
   supprimé du dépôt — clos, conservé dans l'historique git ; reste
   valable comme garde-fou générique.) Cibles : `*_output.txt`, `*_mapping*.txt`,
   `mesures_a_ajouter.json`, `tests/reorganize_simulator_v2.py`
   (one-shot). Ne garder que le périmètre public déclaré.
□ O6 — README PUBLIC dédié au repo moteur : SANS section
   `cd frontend-react`/`KIMI_API_KEY`/`python api.py` ; liens docs
   limités au périmètre public (docs/METHODOLOGIE.md). Le README actuel
   décrit des étapes impossibles pour un fork du moteur seul.
□ (O5 réfuté : run_scenarios_full.py/coverage_scenarios.py = réf
   frontend en docstring seulement, suite fork verte 255/256 — nettoyage
   docstring optionnel, pas bloquant.)
```

### Mise en œuvre

```
□ Créer le repo public france-budget-simulateur
   — git subtree split du dossier budget_simulator/ + policy_measures.json + tests/ + docs/
   — préserve l'historique git

□ Le repo privé budgetlab-france installe france-budget-simulateur via :
   — pip dependency (préféré : versionnage propre)
   — OU git submodule (plus simple, mais coupling fort)

□ Setup release process sur le repo public
   — semver, tags, CHANGELOG.md
   — pip publish (PyPI : france-budget-simulateur)

□ Communication
   — annonce blog/Twitter/LinkedIn
   — soumission Hacker News / Reddit France / dev.to
   — proposer aux journalistes Le Monde, Decoder, Liberation, Mediapart
```

---

## 7. Procédure de validation à chaque étape (résumé exécutif)

```bash
# 1. Snapshot baseline (1 fois avant la modif)
python tests/snapshots/run_scenarios_full.py --out /tmp/baseline.json

# 2. Faire la modif (split d'une section)
# ...

# 3. Re-snapshot et diff strict
python tests/snapshots/run_scenarios_full.py --out /tmp/post.json
diff /tmp/baseline.json /tmp/post.json   # DOIT ÊTRE VIDE

# 4. Tests pytest
pytest tests/ -v   # DOIT ÊTRE 100% VERT

# 5. Si tout vert : commit. Sinon : rollback, analyser.
git checkout .   # rollback safe (avant commit)
```

Une fois Phase 0.10 terminée, ces 5 étapes deviennent : `make snapshot-diff && make test`.

---

## 8. Conventions de handler

### Signature

Voir `handlers/_types.py:Handler` (Protocol typé).

### Dict `impacts` retourné

| Clé | Type | Sémantique |
|-----|------|-----------|
| `depenses` | float (Md€) | Dépenses publiques additionnelles (positif = hausse) |
| `recettes` | float (Md€) | Recettes fiscales additionnelles (positif = hausse) |
| `pouvoir_achat` | float (% PIB) | Impact sur le pouvoir d'achat des ménages |
| `gini` | float (0-1) | Variation de l'indice de Gini (positif = plus inégalitaire) |
| `competitivite` | float (indice) | Variation de l'indice de compétitivité (positif = mieux) |
| `chomage` | float (pt) | Variation du taux de chômage en points (positif = hausse) |

### Gating one-time vs flux

Voir `docs/METHODOLOGIE.md` § "Effets NIVEAU vs FLUX".

- **NIVEAU (one-time)** : changement de prix, taux, barème → effet appliqué l'année du changement seulement, gated par `_is_first_year_change(<measure>_pa, params)`.
- **FLUX (récurrent)** : prime/aide annuelle, érosion d'indexation → effet appliqué chaque année.

### Sources obligatoires

Tout coefficient doit citer une source académique (papier IMF, OFCE, INSEE, Banque de France, France Stratégie, CAE, Cour des comptes, etc.) dans un commentaire au-dessus de la ligne. Pas de magic number sans justification.

---

## 9. Risques et mitigations

| Risque | Mitigation |
|--------|------------|
| Régression silencieuse pendant le split | Phase 0.6 (golden master strict) + 0.7 (silent failure flagué) + procédure S.4 (diff strict avant commit) |
| Couplage caché entre handlers (helpers locaux) | Audit avant chaque split section : grep `_<helper>` cross-section. Le helper devient un import explicite ou est dupliqué. |
| Perte de l'historique git | `git mv` pour les déplacements. `git subtree split --rejoin` pour la séparation public/privé. |
| Contributeurs perdus dans le code | Phase 2 (doc) avant Phase 3 (open source). MEASURE_REGISTRY.md autogénéré reste à jour. |
| Drift entre simulator backend et apiMeasures frontend | Le master test importe `FULL_SCENARIOS` depuis run_scenarios_full qui duplique manuellement ScenariosPage.jsx. À terme : extraire vers un JSON partagé importable des deux côtés (TODO post-split). |

---

## 10. Suivi

- **État** : voir checkbox dans chaque phase ci-dessus.
- **PR** : 1 PR par section pour la Phase 1, taggée `refactor: split`.
- **Reviewers** : @cturkieh + 1 contributeur externe une fois la Phase 2 livrée.
- **Mise à jour de ce document** : à chaque commit majeur, mettre à jour la date en tête + cocher les cases.
