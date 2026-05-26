## Description

<!-- 1-2 phrases : quoi et pourquoi -->

## Type de changement

- [ ] Correction de bug factuel (donnée INSEE, paramètre PLF, etc.)
- [ ] Modification d'un coefficient économique (avec source académique)
- [ ] Ajout d'un nouveau handler (mesure)
- [ ] Modification du moteur macro (croissance, inflation, dette, chômage)
- [ ] Frontend / UI / accessibilité
- [ ] Documentation
- [ ] Autre (préciser)

## Source académique

<!-- Obligatoire pour toute modification du moteur de simulation. Format : auteur, année, titre, lien stable.
     Voir CONTRIBUTING.md § Règles pour le moteur de simulation. Laisser vide si N/A. -->

## Checklist test

- [ ] `make test` passe (mode tolérant)
- [ ] `make test-strict` passe (mode `BUDGETLAB_STRICT=1`)
- [ ] `make snapshot-diff` passe **OU** les écarts sont documentés ci-dessous et `BUDGETLAB_REGEN=1 make snapshot-baseline` a été lancé
- [ ] `make secrets-scan` retourne 0 leak
- [ ] Si modif de coefficient : source académique citée en commentaire
- [ ] Si nouveau handler : entrée dans `policy_measures.json` + handler dans `measure_handlers`
- [ ] `tests/test_calibration_guard.py` passe sans modification

## Écarts golden master (si applicable)

<!-- Si snapshot-diff est rouge et le changement est intentionnel, copier ici les premiers
     écarts remontés par pytest et expliquer le sens (ex: hausse coef X = baisse PA Y2030 attendue). -->
