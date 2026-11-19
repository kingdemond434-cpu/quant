"""The worst historical day of a prop book stays under 60% of the firm's daily limit."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from prop import stress  # noqa: E402


def _days(cols: list[str], r: list[list[float]]) -> tuple[list[str], np.ndarray]:
    return cols, np.asarray(r, dtype=float)[None, :, :]


def test_worst_day_uses_the_joint_history_and_charges_absent_columns_in_full() -> None:
    days = _days(["a", "b"], [[-1.0, 1.0], [-1.0, -1.0], [0.5, 0.5]])
    w = stress.worst_day(["a", "b", "c"], [0.01, 0.01, 0.002], days)
    assert abs(w["loss"] - 0.022) < 1e-12
    assert w["unmeasured"] == ["c"]
    blind = stress.worst_day(["a", "b"], [0.01, 0.01], None)
    assert blind["loss"] == 0.02 and blind["status"].startswith("UNMEASURED")


def test_cap_cuts_the_weakest_sleeve_of_the_family_that_lost_most() -> None:
    # Family X's two sleeves lose together; Y hedges. 3 x 0.6% = 1.8% worst day > 60% x 2.5%.
    days = _days(["x1", "x2", "y1"], [[-1.0, -1.0, -1.0], [1.0, 1.0, 1.0]])
    rows = [{"c": "x1", "f": "X"}, {"c": "x2", "f": "X"}, {"c": "y1", "f": "Y"}]
    out = stress.cap_book(rows, risk_of=lambda r: 0.006, family_of=lambda r: r["f"],
                          daily_limit=0.025, days=days, col_of=lambda r: r["c"])
    assert [r["c"] for r in out["kept"]] == ["x1", "y1"]
    assert out["cuts"][0]["column"] == "x2" and out["cuts"][0]["missed_growth_risk_frac"] == 0.006
    assert out["after"]["loss"] <= 0.6 * 0.025 + 1e-12
    assert out["before"]["x_limit"] == 0.72 and not out["kill_criterion_met"]


def test_fixed_lane_risk_counts_and_is_never_cut() -> None:
    days = _days(["s", "gold_asia"], [[-1.0, -1.0]])
    rows = [{"c": "s", "f": "S"}]
    out = stress.cap_book(rows, risk_of=lambda r: 0.01, family_of=lambda r: r["f"],
                          daily_limit=0.025, days=days, col_of=lambda r: r["c"],
                          fixed={"gold_asia": 0.006})
    assert out["kept"] == [] and out["after"]["loss"] == 0.006


def test_kill_criterion_and_revert_switch(monkeypatch) -> None:
    days = _days(["a"], [[-1.0]])
    rows = [{"c": "a", "f": "A"}]
    small = stress.cap_book(rows, risk_of=lambda r: 0.001, family_of=lambda r: r["f"],
                            daily_limit=0.025, days=days, col_of=lambda r: r["c"])
    assert small["kill_criterion_met"] and not small["cuts"]
    monkeypatch.setattr(stress, "STRESS_CAP_FRAC", None)
    big = stress.cap_book(rows, risk_of=lambda r: 0.05, family_of=lambda r: r["f"],
                          daily_limit=0.025, days=days, col_of=lambda r: r["c"])
    assert big["kept"] == rows and not big["cuts"]
