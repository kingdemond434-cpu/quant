"""The pre-warm's per-family cost record: report-only, and it never needs a worker's help."""
from __future__ import annotations

import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK), str(DESK / "scripts"), str(DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

import external_gauntlet as eg  # noqa: E402


def _summary() -> dict:
    return {"worker_seconds": {}, "by_family": {}}


def test_seconds_are_summed_per_status_and_family() -> None:
    s = _summary()
    eg._cost(s, {"family": "a"}, "WARMED", 2.0)
    eg._cost(s, {"family": "a"}, "HIT", 0.5)
    eg._cost(s, {"family": "b"}, "WARMED", 7.25)
    assert s["worker_seconds"] == {"WARMED": 9.25, "HIT": 0.5}
    assert s["by_family"]["a"] == {"n": 2, "s": 2.5, "max_s": 2.0, "warmed": 1}
    assert s["by_family"]["b"]["max_s"] == 7.25


def test_a_result_without_seconds_is_not_counted() -> None:
    s = _summary()
    eg._cost(s, {"family": "a"}, "WARMED", None)
    assert s == _summary()


def test_the_published_table_keeps_the_costliest_and_folds_the_rest() -> None:
    s = _summary()
    for i in range(eg.PREWARM_COST_TOP + 3):
        eg._cost(s, {"family": f"f{i}"}, "WARMED", float(i + 1))
    top = eg._top_families(s["by_family"])
    assert list(top)[0] == f"f{eg.PREWARM_COST_TOP + 2}"
    assert top["_rest"] == {"families": 3, "n": 3, "s": 6.0}


def test_warm_one_reports_its_own_seconds(monkeypatch) -> None:
    monkeypatch.setattr(eg, "_bars_for", lambda sym, tf: None)
    out = eg._warm_one_timed({"sym": "EURUSD", "family": "x", "params": {}}, {})
    assert out["status"] == "NOT_RUN_DATA_MISSING" and out["seconds"] >= 0.0
