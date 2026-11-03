from __future__ import annotations

import numpy as np
import pandas as pd

from libs.research import carry_crash as cc


def _days(n: int) -> pd.DatetimeIndex:
    return pd.bdate_range("2019-01-01", periods=n)


def test_a_hazard_that_predicts_crashes_is_proven_and_two_sided():
    rng = np.random.default_rng(0)
    d = _days(1600)
    h = pd.Series(rng.normal(size=d.size), index=d)
    r = pd.Series(0.06 + 0.5 * rng.normal(size=d.size), index=d)
    r[h > 1.0] -= 0.8                     # crashes when the hazard is high
    p = cc.prove(r, r - 0.01, h)
    assert p.armed, p.reason
    assert p.cut < 1.0 and p.delta_elog_per_day > 0 and p.lower_bound > 0
    assert p.trials == len(cc.GRID)
    cur = cc.current(pd.DataFrame({"hazard": h, "crowding": h, "vix_shock": h,
                                   "drawdown": h}), p)
    assert cur["multiplier"] == cur["proposed_multiplier"]


def test_a_hazard_that_says_nothing_is_not_armed():
    rng = np.random.default_rng(1)
    d = _days(1600)
    h = pd.Series(rng.normal(size=d.size), index=d)
    r = pd.Series(0.03 + 0.5 * rng.normal(size=d.size), index=d)
    p = cc.prove(r, None, h)
    assert not p.armed
    cur = cc.current(pd.DataFrame({"hazard": h, "crowding": h, "vix_shock": h,
                                   "drawdown": h}), p)
    assert cur["multiplier"] == 1.0


def test_short_history_is_unmeasured_never_armed():
    d = _days(300)
    p = cc.prove(pd.Series(0.1, index=d), None, pd.Series(0.0, index=d))
    assert not p.armed and p.reason.startswith("UNMEASURED")


def test_cot_is_used_only_after_publication():
    rd = pd.date_range("2020-01-07", periods=200, freq="7D", tz="UTC")   # Tuesdays
    rng = np.random.default_rng(2)
    cot = pd.DataFrame({"report_date": rd, "oi": 1000.0,
                        "lm_l": rng.uniform(100, 300, rd.size), "lm_s": 200.0})
    days = pd.date_range("2020-01-01", "2023-12-31", freq="D")
    z = cc.cot_crowding(cot, days)
    last = rd[-1].tz_localize(None)
    # the report dated Tuesday is not known until Saturday (lag 4 days)
    assert z.loc[last + pd.Timedelta(days=3)] == z.loc[last - pd.Timedelta(days=1)]
    assert z.loc[last + pd.Timedelta(days=4)] != z.loc[last - pd.Timedelta(days=1)]


def test_drawdown_uses_only_past_returns():
    d = _days(400)
    r = pd.Series(0.0, index=d)
    r.iloc[-1] = -10.0
    dd = cc.carry_drawdown(r)
    assert np.isnan(dd.iloc[-1]) or dd.iloc[-1] == dd.iloc[-2]
