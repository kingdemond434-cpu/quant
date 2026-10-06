"""No UNKNOWN verdict leaves the sealed judge without a named cause and a non-empty failed_gates.

Ships WITH patch `unknown_verdict_named.patch` (external_gauntlet.py is sealed): it fails on the
unpatched judge, where `_append_gate_ledger` wrote `terminal_gate: UNKNOWN` and nothing else.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "scripts"), str(DESK), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import external_gauntlet as eg  # noqa: E402


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(eg, "GATE_LEDGER", tmp_path / "gate_verdict_ledger.jsonl")
    monkeypatch.setattr(eg, "GATE_INDEX", tmp_path / "gate_verdict_index.json")
    return tmp_path / "gate_verdict_ledger.jsonl"


def _rows(path: Path) -> list[dict]:
    return [json.loads(ln) for ln in path.read_text("utf-8").splitlines() if ln.strip()]


def test_no_unknown_row_is_written_without_a_reason(ledger) -> None:
    verdicts = [
        # the unmeasured branch as it is emitted now
        {"cell": "A.f.p=1", "sym": "A", "family": "f", "days": 0, "passed": False,
         "unmeasured": True, "unknown_reason": "no_signals", "failed_gates": ["observations"]},
        # an unmeasured row from before the patch: no reason, no failed_gates
        {"cell": "B.f.p=2", "sym": "B", "family": "f", "days": 12, "passed": False,
         "unmeasured": True},
        # a verdict with no terminal gate and no unmeasured flag at all
        {"cell": "C.f.p=3", "sym": "C", "family": "f", "passed": False},
        # an empty failed_gates list is not a reason either
        {"cell": "D.f.p=4", "sym": "D", "family": "f", "passed": False, "unmeasured": True,
         "failed_gates": []},
        # judged rows are untouched
        {"cell": "E.f.p=5", "sym": "E", "family": "f", "passed": False,
         "terminal_gate": "cpcv", "failed_gates": ["cpcv"]},
    ]
    assert eg._append_gate_ledger(verdicts)["appended"] == 5
    rows = {r["cell"]: r for r in _rows(ledger)}
    unknown = [r for r in rows.values() if r["terminal_gate"] == "UNKNOWN"]
    assert len(unknown) == 4
    for r in unknown:
        assert r["failed_gates"] and all(str(g) for g in r["failed_gates"]), r
        assert str(r["unknown_reason"]), r
    assert rows["A.f.p=1"]["unknown_reason"] == "no_signals"
    assert rows["B.f.p=2"]["unknown_reason"] == "observations_under_60_days"
    assert rows["B.f.p=2"]["days"] == 12
    assert rows["C.f.p=3"]["unknown_reason"] == "no_terminal_gate_recorded"
    assert rows["D.f.p=4"]["failed_gates"] == ["observations"]
    assert "unknown_reason" not in rows["E.f.p=5"], "a named ruling needs no UNKNOWN reason"


def test_the_reasons_a_writer_may_give_are_the_declared_set() -> None:
    idx = pd.to_datetime(["2026-01-01", "2026-01-02"])
    empty = pd.Series([], dtype=float)
    cases = [
        (eg.classify_unknown(None, None, 5, errored=True), "series_exception"),
        (eg.classify_unknown(None, None, None), "no_series"),
        (eg.classify_unknown(empty, 219, 400), "lockbox_consumed_history"),
        (eg.classify_unknown(empty, 0, 0), "no_signals"),
        (eg.classify_unknown(empty, 0, 7), "signals_no_trades"),
        # it traded, on 41 days, every one after the campaign cut: a short history, not a fill
        (eg.classify_unknown(empty, 41, 7), "short_history_after_cut"),
        (eg.classify_unknown(empty, 41, None), "short_history_after_cut"),
        (eg.classify_unknown(empty, 0, None), "no_trades"),
        (eg.classify_unknown(pd.Series([0.1, 0.2], index=idx), 2, 9), "too_rare"),
    ]
    for got, want in cases:
        assert got == want and got in eg.UNKNOWN_REASONS


def test_the_unmeasured_branch_itself_carries_its_reason() -> None:
    """Every dict the judge builds with `unmeasured: True` names failed_gates and a reason."""
    tree = ast.parse(Path(eg.__file__).read_text("utf-8"))
    found = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        flag = [v for k, v in zip(node.keys, node.values, strict=True)
                if isinstance(k, ast.Constant) and k.value == "unmeasured"]
        if not (flag and isinstance(flag[0], ast.Constant) and flag[0].value is True):
            continue
        keys = {k.value for k in node.keys if isinstance(k, ast.Constant)}
        found += 1
        assert {"failed_gates", "unknown_reason"} <= keys, sorted(keys)
    assert found >= 1


def test_a_peer_family_with_no_peer_fails_the_build_by_name() -> None:
    """`peer=None` returned [] and the cell read UNKNOWN/never_fires; now the build names it."""
    if eg._bars_for("EURUSD", "H1") is None:
        pytest.skip("EURUSD_H1.parquet absent from this checkout")
    meta = json.loads((eg.UNI / "universe.json").read_text("utf-8"))
    for fam in ("relative_value", "correlation_regime"):
        assert eg.build_cell("EURUSD", fam, {}, meta) is None
        assert "no peer_symbol" in str(eg.LAST_BUILD_FAILURE)
        assert eg.build_cell("EURUSD", fam, {"peer_symbol": "NO_SUCH_SYMBOL"}, meta) is None
        assert "no H1 bars for peer NO_SUCH_SYMBOL" in str(eg.LAST_BUILD_FAILURE)


def test_a_triangle_with_no_legs_fails_the_build_by_name() -> None:
    """A triangle missing a leg returned [] and read UNKNOWN/never_fires; now the build names it."""
    if eg._bars_for("EURJPY", "H1") is None or eg._bars_for("EURUSD", "H1") is None:
        pytest.skip("EURJPY_H1 / EURUSD_H1 parquet absent from this checkout")
    meta = json.loads((eg.UNI / "universe.json").read_text("utf-8"))
    assert eg.build_cell("EURJPY", "triangle", {}, meta) is None
    assert "triangle: no leg_b_symbol" in str(eg.LAST_BUILD_FAILURE)
    assert eg.build_cell("EURJPY", "triangle", {"leg_b_symbol": "EURUSD"}, meta) is None
    assert "triangle: no leg_c_symbol" in str(eg.LAST_BUILD_FAILURE)
    assert eg.build_cell("EURJPY", "triangle",
                         {"leg_b_symbol": "EURUSD", "leg_c_symbol": "NO_SUCH_SYMBOL"},
                         meta) is None
    assert "triangle leg missing: no H1 bars for NO_SUCH_SYMBOL" in str(eg.LAST_BUILD_FAILURE)
