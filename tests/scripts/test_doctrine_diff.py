"""R0093: a principal_doctrine.txt edit is a principal-surfaced gap and MUST reach the
blind-spot origin gauge as origin=principal -- six doctrine orders produced zero rows
because no wire existed. These tests pin the wire's whole contract."""

from __future__ import annotations

from pathlib import Path

from scripts.check_doctrine_diff import check


class _Capture:
    def __init__(self) -> None:
        self.rows: list[object] = []

    def __call__(self, row: object) -> None:
        self.rows.append(row)


def _paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    return tmp_path / "doctrine.txt", tmp_path / "state.json", tmp_path / "prev.txt"


def test_first_run_baselines_without_a_row(tmp_path: Path) -> None:
    doc, state, prev = _paths(tmp_path)
    doc.write_text("LAW ONE\n", "utf-8")
    cap = _Capture()
    verdict, rc = check(doc, state, prev, cap)
    assert (verdict, rc) == ("BASELINED", 0)
    assert not cap.rows, "the gauge measures orders, not the wiring's birthday"


def test_a_doctrine_edit_logs_exactly_one_principal_row(tmp_path: Path) -> None:
    doc, state, prev = _paths(tmp_path)
    doc.write_text("LAW ONE\n", "utf-8")
    cap = _Capture()
    check(doc, state, prev, cap)
    doc.write_text("LAW ONE\nLAW TWO: new order from the principal\n", "utf-8")
    verdict, rc = check(doc, state, prev, cap)
    assert (verdict, rc) == ("ORDER-LOGGED", 0)
    assert len(cap.rows) == 1
    row = cap.rows[0]
    assert row.origin == "principal", "a doctrine edit IS the failure signal, by definition"
    assert "+1/-0" in row.summary and "LAW TWO" in row.summary


def test_unchanged_doctrine_logs_nothing(tmp_path: Path) -> None:
    doc, state, prev = _paths(tmp_path)
    doc.write_text("LAW ONE\n", "utf-8")
    cap = _Capture()
    check(doc, state, prev, cap)
    verdict, rc = check(doc, state, prev, cap)
    assert (verdict, rc) == ("UNCHANGED", 0)
    assert not cap.rows


def test_absent_doctrine_is_a_failure_not_a_skip(tmp_path: Path) -> None:
    doc, state, prev = _paths(tmp_path)
    verdict, rc = check(doc, state, prev, _Capture())
    assert (verdict, rc) == ("UNREADABLE", 2), "an unrunnable fence counts as FAILED (L1.37)"


def test_corrupt_state_rebaselines_and_the_next_edit_still_fires(tmp_path: Path) -> None:
    doc, state, prev = _paths(tmp_path)
    doc.write_text("LAW ONE\n", "utf-8")
    cap = _Capture()
    check(doc, state, prev, cap)
    state.write_text("{not json", "utf-8")
    verdict, _ = check(doc, state, prev, cap)
    assert verdict == "REBASELINED" and not cap.rows
    doc.write_text("LAW ONE amended\n", "utf-8")
    verdict, _ = check(doc, state, prev, cap)
    assert verdict == "ORDER-LOGGED" and len(cap.rows) == 1, (
        "a corrupt hash store must never weld the gauge shut"
    )
