"""Helpers de comparaison snapshot partagés (dédup Lot E, Phase 2).

La boucle de comparaison cellule-par-cellule et la détection de silent
handler failure étaient dupliquées (~60 lignes) entre :
- ``tests/test_golden_master_full.py`` (Phase 0.6, golden master combiné) ;
- ``tests/test_handler_coverage.py`` (Phase 0.8, standalone master).

Comportement STRICTEMENT préservé. Les deux variantes diffèrent par :
libellé du message d'échec, hint de régénération (golden seul), et
traitement d'une colonne absente (golden : ignorée car la garde
structurelle ``tracked_columns`` la signale déjà ; standalone : reportée
« colonne disparue »). Ces écarts sont PARAMÉTRÉS ici, pas effacés —
toute autre ligne est commune et factorisée à l'identique.
"""
import pytest

from budget_simulator.constants import HANDLER_FAILED_KEY

_MAX_DELTAS_SHOWN = 30


def compare_against_snapshot(name_to_df, snapshot, *, label, missing_msg,
                             tolerance, min_scenarios, regen_hint=None,
                             tracked_columns=None, report_missing_column=False):
    """Compare cellule par cellule chaque df au snapshot ; ``pytest.fail`` si écart.

    - ``name_to_df`` : mapping ``{nom_scénario: DataFrame}`` déjà simulé.
    - ``snapshot`` : dict ``{nom: {'years': [...], 'data': {col: [vals]}}}``.
    - ``label`` : préfixe du message d'échec (« golden master » / « standalone master »).
    - ``missing_msg`` : template ``str`` avec ``{name}`` si un scénario manque au snapshot.
    - ``regen_hint`` : commande de régénération ajoutée au message (golden seul).
    - ``tracked_columns`` : si fourni (mode golden), active la garde structurelle
      « colonne tracked apparue/disparue » et IGNORE une colonne absente du df
      (déjà signalée par la garde). Sinon (mode standalone), une colonne absente
      est reportée si ``report_missing_column``.
    - ``min_scenarios`` / garde ``cells_compared`` : anti-faux-vert. Une fixture
      cassée (dict vide) ou un snapshot ``data`` vide ferait passer le test
      SANS rien comparer — pire qu'absence de filet. Symétrique du garde
      ``measures_inspected > 0`` de ``assert_no_silent_handler_failure``.
    """
    assert len(name_to_df) >= min_scenarios, (
        f"{label}: {len(name_to_df)} scénario(s) à comparer (attendu ≥ "
        f"{min_scenarios}) → fixture cassée en amont, faux vert évité"
    )
    deltas = []
    cells_compared = 0
    for name, df in name_to_df.items():
        assert name in snapshot, missing_msg.format(name=name)
        expected = snapshot[name]['data']
        years = snapshot[name]['years']

        if df.index.tolist() != years:
            deltas.append(f"{name}: years drift {years} → {df.index.tolist()}")
            continue

        if tracked_columns is not None:
            snapshot_cols = set(expected.keys())
            actual_tracked = {c for c in tracked_columns if c in df.columns}
            if actual_tracked != snapshot_cols:
                new_cols = actual_tracked - snapshot_cols
                removed_cols = snapshot_cols - actual_tracked
                if new_cols:
                    deltas.append(f"{name}: nouvelles colonnes tracked non snapshot: {sorted(new_cols)}")
                if removed_cols:
                    deltas.append(f"{name}: colonnes disparues: {sorted(removed_cols)}")

        for col, expected_values in expected.items():
            if col not in df.columns:
                if report_missing_column:
                    deltas.append(f"{name}/{col}: colonne disparue")
                # sinon ignoré : garde structurelle (golden) ou non suivi (standalone)
                continue
            for idx, year in enumerate(years):
                a, e = df[col].iloc[idx], expected_values[idx]
                cells_compared += 1
                if a is None and e is None:
                    continue
                if a is None or e is None:
                    deltas.append(f"{name}/{col}/Y{year}: {e} → {a} (None mismatch)")
                    continue
                if abs(a - e) >= tolerance:
                    deltas.append(f"{name}/{col}/Y{year}: {e:.3f} → {a:.3f} (Δ={a - e:+.4f})")

    assert cells_compared > 0, (
        f"{label}: 0 cellule comparée sur {len(name_to_df)} scénario(s) → "
        f"snapshot 'data' vide ou colonnes toutes absentes, faux vert évité"
    )

    if deltas:
        overflow = (f"\n  ... ({len(deltas) - _MAX_DELTAS_SHOWN} de plus)"
                    if len(deltas) > _MAX_DELTAS_SHOWN else "")
        regen = f"\n\nSi le changement est intentionnel, régénérer :\n  {regen_hint}" if regen_hint else ""
        pytest.fail(
            f"\n{len(deltas)} divergence(s) du {label} :\n  "
            + "\n  ".join(deltas[:_MAX_DELTAS_SHOWN])
            + overflow
            + regen
        )


def assert_no_silent_handler_failure(name_to_report, *, label,
                                     empty_report_msg, no_inspection_msg):
    """Aucun handler n'a posé ``HANDLER_FAILED_KEY`` ; ``pytest.fail`` sinon.

    - ``name_to_report`` : mapping ``{nom: report}`` (``report['measure_impacts_by_year']``).
    - ``empty_report_msg`` : template ``{name}`` si ``measure_impacts_by_year`` vide.
    - ``no_inspection_msg`` : message si AUCUNE mesure inspectée (anti-faux-vert).
    """
    failures = []
    measures_inspected = 0

    for name, report in name_to_report.items():
        impacts_by_year = report['measure_impacts_by_year']
        assert impacts_by_year, empty_report_msg.format(name=name)

        for year_impacts in impacts_by_year:
            for measure_id, data in year_impacts.items():
                if measure_id == 'Année' or not isinstance(data, dict):
                    continue
                measures_inspected += 1
                if data.get(HANDLER_FAILED_KEY):
                    failures.append(
                        f"{name}/{measure_id}/Y{year_impacts.get('Année', '?')}: "
                        f"{data.get('erreur', '?')}"
                    )

    assert measures_inspected > 0, no_inspection_msg

    if failures:
        pytest.fail(
            f"\n{len(failures)} handler(s) {label} :\n  "
            + "\n  ".join(failures[:20])
        )
