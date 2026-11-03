"""The preregistered EB-shrinkage OOS harness: no look-ahead, bars applied as registered."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import eb_shrinkage_oos as oos  # noqa: E402

from libs.portfolio.robust_elog import SleeveEvidence  # noqa: E402


def test_truncation_sees_no_day_after_the_origin() -> None:
    e = SleeveEvidence(name="a", daily_r=np.arange(300, dtype=float), forward_days=9,
                       live_days=4, macro_w=np.ones(300))
    t = oos._truncate(e, 0, 200)
    assert t.daily_r.max() == 199 and t.forward_days == 0 and t.live_days == 0
    assert t.macro_w.size == 0


def test_verdict_requires_both_bars() -> None:
    win = {"mse_fixed": 2.0, "mse_eb": 1.0, "elog_fixed": 0.01, "elog_eb": 0.02}
    lose_growth = {"mse_fixed": 2.0, "mse_eb": 1.0, "elog_fixed": 0.02, "elog_eb": 0.01}
    assert oos.verdict([win] * 4)["verdict"] == "PASS"
    assert oos.verdict([lose_growth] * 4)["verdict"] == "FAIL"
    assert oos.verdict([])["verdict"] == "UNMEASURED"


def test_harness_runs_end_to_end_on_a_synthetic_book() -> None:
    rng = np.random.default_rng(0)
    ev = [SleeveEvidence(name=f"f{f}_{i}", daily_r=rng.normal(mu, 1.0, 500),
                         family=f"fam{f}", symbol=sym)
          for f, (mu, sym) in enumerate([(0.1, "XAUUSD"), (0.05, "EURUSD")])
          for i in range(4)]
    res = oos.run_folds(ev, with_books=True)
    assert res["verdict"] in ("PASS", "FAIL") and len(res["folds"]) == oos.N_FOLDS
    for f in res["folds"]:          # solved as production: never below the floor fill
        assert f["heat_eb"] >= oos.HEAT_FLOOR - 0.01 and f["heat_fixed"] >= oos.HEAT_FLOOR - 0.01
