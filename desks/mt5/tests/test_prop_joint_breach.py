"""prop_joint_breach (IDEA_QUEUE row 199): same-day breach counts, path sim, FTMO pick."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import prop_joint_breach as pjb  # noqa: E402

E8 = pjb.Rules(100_000, 0.025, 0.10, 0.10)
FT = pjb.FTMO_RULES


def _days(r: list[float], worst: list[float] | None = None) -> pd.DataFrame:
    worst = worst if worst is not None else [min(x, 0.0) for x in r]
    return pd.DataFrame({"r": r, "worst_intraday_r": worst, "n_legs": [1] * len(r)})


def test_e8_rules_from_guard_source():
    r = pjb.e8_rules()
    assert (r.start, r.daily, r.max_dd, r.target) == (100_000.0, 0.025, 0.10, 0.10)


def test_zero_observed_is_a_bound_not_zero():
    out = pjb.same_day_breach(_days([-1.0, 1.0, 0.5]), 0.006, 0.009, E8, FT)
    assert out["both"]["days"] == 0
    assert out["both"]["p_per_day"] is None
    assert out["both"]["p_per_day_upper95"] == pytest.approx(1.0)
    assert out["p_both_given_e8"] == pjb.UNMEASURED


def test_same_day_thresholds_in_r():
    # E8 needs 4.17R at 0.006, FTMO 5.56R at 0.009: a 5R day trips E8 only, a 6R day both
    out = pjb.same_day_breach(_days([-5.0, -6.0, 0.0]), 0.006, 0.009, E8, FT)
    assert out["e8"]["days"] == 2
    assert out["ftmo"]["days"] == 1
    assert out["both"]["days"] == 1
    assert out["p_both_given_e8"] == pytest.approx(0.5)


def test_follower_lag_makes_ftmo_worse():
    d = _days([-5.4])
    assert pjb.same_day_breach(d, 0.006, 0.009, E8, FT)["ftmo"]["days"] == 0
    assert pjb.same_day_breach(d, 0.006, 0.009, E8, FT, follower_lag_r=0.2)["ftmo"]["days"] == 1


def test_simulate_static_floor_and_target_stop():
    idx = np.zeros((3, 40), dtype=int)
    lose = pjb.simulate(np.array([-1.0]), np.array([-1.0]), np.array([1.0]), 0.01, E8, idx)
    assert lose[0].all()                           # ~10.5 losing days reach the static floor
    win = pjb.simulate(np.array([1.0]), np.array([0.0]), np.array([1.0]), 0.01, E8, idx)
    assert not win[0].any()                        # target reached -> stops, never fails


def test_simulate_daily_breach_day_recorded():
    idx = np.array([[0, 1, 0]])
    f, d = pjb.simulate(np.array([0.5, -5.0]), np.array([0.0, -5.0]), np.array([1.0, 1.0]),
                        0.006, E8, idx)
    assert f[0] and d[0] == 1


def test_block_bootstrap_shape_and_contiguity():
    rng = np.random.default_rng(0)
    idx = pjb.block_bootstrap_idx(100, 12, 7, 5, rng)
    assert idx.shape == (7, 12)
    assert ((idx[:, 1] - idx[:, 0]) % 100 == 1).all()


def test_joint_paths_identical_signal_means_both_given_either_high():
    d = _days([-1.0] * 6 + [1.0] * 4)
    jp = pjb.joint_paths(d, 0.009, 0.009, E8, FT, 30, paths=500)
    assert jp["p_e8_fail"] == pytest.approx(jp["p_ftmo_fail"], abs=1e-9)
    assert jp["p_both_fail"] == pytest.approx(jp["p_either_fail"], abs=1e-9)


def test_pick_ftmo_risk():
    sweep = [{"ftmo_risk": 0.005, "p_either_fail": 0.01},
             {"ftmo_risk": 0.007, "p_either_fail": 0.04},
             {"ftmo_risk": 0.009, "p_either_fail": 0.08}]
    assert pjb.pick_ftmo_risk(sweep, 0.05) == 0.007
    assert pjb.pick_ftmo_risk(sweep, 0.001) is None


def test_live_leg_r_reads_only_r(tmp_path):
    f = tmp_path / "l.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in [
        {"sleeve": "gold_asia", "pl_quote": -50.0, "risk_quote": -50.0, "account": 1},
        {"sleeve": "gold_asia", "pl_quote": 25.0, "risk_quote": -50.0, "account": 1},
        {"sleeve": "other", "pl_quote": 9.0, "risk_quote": -1.0},
        "not json"]), encoding="utf-8")
    out = pjb.live_leg_r(f)
    assert out["n"] == 2 and out["worst_r"] == -1.0 and out["mean_r"] == -0.25
    assert "account" not in json.dumps(out)
    assert pjb.live_leg_r(tmp_path / "none.jsonl")["status"] == pjb.UNMEASURED


def test_build_synthetic_has_no_identity_and_marks_unmeasured():
    rng = np.random.default_rng(3)
    idx = pd.date_range("2026-01-05", periods=60 * 24, freq="h", tz="UTC")
    idx = idx[idx.dayofweek < 5]
    close = 2000 + np.cumsum(rng.normal(0, 3, len(idx)))
    op = np.r_[close[0], close[:-1]]
    xau = pd.DataFrame({"open": op, "high": np.maximum(op, close) + 2,
                        "low": np.minimum(op, close) - 2, "close": close}, index=idx)
    doc = pjb.build(xau=xau, paths=50)
    text = json.dumps(doc, default=str)
    assert '"account"' not in text and "login" not in text
    assert doc["target"] == pjb.UNMEASURED
    assert doc["e8_live_leg_r"]["status"] == pjb.UNMEASURED
    assert set(doc["variants"]) == {"base", "slip_tail", "oco_fail"}
    for v in doc["variants"].values():
        assert set(v["ftmo_pick_by_target"]) == {"0.01", "0.05", "0.1"}


def test_build_publishes_no_money_amount():
    rng = np.random.default_rng(4)
    idx = pd.date_range("2026-01-05", periods=40 * 24, freq="h", tz="UTC")
    idx = idx[idx.dayofweek < 5]
    close = 2000 + np.cumsum(rng.normal(0, 3, len(idx)))
    op = np.r_[close[0], close[:-1]]
    xau = pd.DataFrame({"open": op, "high": np.maximum(op, close) + 2,
                        "low": np.minimum(op, close) - 2, "close": close}, index=idx)
    doc = pjb.build(xau=xau, paths=20)
    text = json.dumps(doc, default=str)
    assert "_usd" not in text and '"start"' not in text and "100000" not in text
    head = doc["p17_row207_headline"]
    assert head["e8_loss_frac_of_start"] == pytest.approx(3.5 * doc["e8_risk_per_leg"])
    assert doc["rules"]["E8"] == {"daily": 0.025, "max_dd": 0.10, "target": 0.10}
