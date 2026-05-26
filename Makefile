# france-budget-simulateur — commandes développeur
# Aligné avec la CI GitHub Actions (.github/workflows/test.yml).
# Chaque cible est self-contained ; aucune dépendance entre cibles sauf `ci`.

.PHONY: help test test-strict snapshot-baseline snapshot-diff secrets-scan check-docs-sync ci

help:
	@echo "france-budget-simulateur — cibles make disponibles"
	@echo ""
	@echo "  make test              pytest tests/ en mode tolérant (prod-like)"
	@echo "  make test-strict       pytest tests/ avec BUDGETLAB_STRICT=1"
	@echo "                         (escalade les exceptions handler — bloque les"
	@echo "                          régressions silencieuses, à utiliser avant PR)"
	@echo ""
	@echo "  make snapshot-baseline régénère les 2 golden masters (combiné + standalone)"
	@echo "                         à utiliser après un changement intentionnel de calibration"
	@echo "  make snapshot-diff     vérifie que la sim actuelle matche les golden masters"
	@echo ""
	@echo "  make secrets-scan      scan gitleaks de l'historique git complet"
	@echo "                         (faux positifs whitelistés via .gitleaksignore)"
	@echo ""
	@echo "  make check-docs-sync   vérifie que le bloc scénarios de SCENARIOS_POLITIQUES.md"
	@echo "                         est à jour vis-à-vis de la source canonique"
	@echo ""
	@echo "  make ci                équivalent local de la CI GitHub Actions"
	@echo "                         (test + test-strict + secrets-scan + check-docs-sync)"

test:
	pytest tests/ -v

test-strict:
	BUDGETLAB_STRICT=1 pytest tests/ -v

snapshot-baseline:
	@if [ "$(BUDGETLAB_REGEN)" != "1" ]; then \
		echo "✗ Régénération des golden masters bloquée par défaut."; \
		echo ""; \
		echo "Cette commande écrase les snapshots de référence. Si make snapshot-diff"; \
		echo "échoue, c'est probablement parce que ta modif introduit une régression."; \
		echo "Régénérer SANS valider l'origine des écarts fige la régression."; \
		echo ""; \
		echo "À n'utiliser que SI le changement de calibration est intentionnel et sourcé."; \
		echo "Voir CONTRIBUTING.md § Comment tester ma modification (Cas 2)."; \
		echo ""; \
		echo "Pour confirmer : BUDGETLAB_REGEN=1 make snapshot-baseline"; \
		exit 1; \
	fi
	python tests/snapshots/run_scenarios_full.py --out tests/snapshots/golden_master_v1.json
	python tests/snapshots/coverage_scenarios.py --out tests/snapshots/standalone_master_v1.json

snapshot-diff:
	pytest tests/test_golden_master_full.py tests/test_handler_coverage.py -v

secrets-scan:
	# --exit-code 1 garantit l'alignement avec la CI : un finding échoue le scan local
	# (sans cela, gitleaks affiche les findings mais peut retourner 0).
	gitleaks detect --source . --exit-code 1 --no-banner

check-docs-sync:
	python3 scripts/generate_scenario_params.py --check

ci: test test-strict secrets-scan check-docs-sync
