"""The two stop-geometry constants are solved on kelly_survival's objective, never chosen.

`research/stop_geometry_derivation.py` sets gateway.MIN_STOP_SPREAD_MULT and
decision_core.ENTRY_DRIFT_TOL_FRAC by maximising ruin-counted E[log W] subject to
P(losing 80% within 60 days) <= 5%. These tests pin the trade model, the solve's refusal to move
a money-path number on noise, the aggressiveness flag, and that an absent input reads UNMEASURED.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import stop_geometry_derivation as sgd  # noqa: E402


def test_a_stop_the_widened_quote_reaches_is_lost_whatever_the_edge() -> None:
    # x = 2 spreads: the quote alone takes it once the spread widens 3x (W >= 2x - 1).
    x = np.array([2.0, 2.0])
    r = sgd.trade_r(x, np.full(2, 1.5), np.full(2, 50.0), np.array([3.0, 2.9]),
                    np.array([0.0, 0.0]))
    assert r[0] == pytest.approx(-1.0 - 0.5)            # taken: -1R less the spread in R
    assert r[1] == pytest.approx(1.5 - 0.5)             # not taken: the certain win, less spread


def test_the_price_edge_dilutes_as_the_bracket_widens() -> None:
    """A fixed-hold edge worth `e*x + 1` spreads at geometry x is worth (e*x + 1)/x' R gross at
    x', less 1/x' of spread: the trade-off the solve prices."""
    rng = np.random.default_rng(0)
    n = 200_000
    u = rng.random(n)
    edge = np.full(n, 0.2 * 10 + 1.0)                   # e = 0.2R at x = 10 spreads
    no_widen = np.ones(n)
    at_10 = sgd.trade_r(np.full(n, 10.0), np.full(n, 1.5), edge, no_widen, u).mean()
    at_20 = sgd.trade_r(np.full(n, 20.0), np.full(n, 1.5), edge, no_widen, u).mean()
    assert at_10 == pytest.approx(0.2, abs=0.01)        # the certificate's own net R
    assert at_20 == pytest.approx((3.0 - 1.0) / 20.0, abs=0.01)


def _active(n: int = 400, days: int = 60, slots: int = 3) -> np.ndarray:
    return np.ones((n, days, slots), dtype=bool)


def test_a_flat_objective_never_moves_todays_number() -> None:
    act = _active()
    base = np.random.default_rng(1).normal(0.05, 1.0, act.shape)
    res = sgd._solve((1.0, 2.0, 3.0, 4.0), lambda v: base, act, 0.005, 3.0, "lower")
    assert res["status"] == "TODAY_OPTIMAL_WITHIN_NOISE"
    assert res["derived"] == 3.0 and res["less_aggressive_than_today"] is False
    assert res["tie_rule_value"] == 1.0                 # named, not taken


def test_a_clear_optimum_moves_and_says_which_way() -> None:
    act = _active()
    noise = np.random.default_rng(2).normal(0.0, 0.5, act.shape)
    # E[R] peaks at 2.0: the more aggressive side of today's 3.0 for "lower".
    res = sgd._solve((1.0, 2.0, 3.0, 4.0), lambda v: noise + 0.3 - 0.2 * abs(v - 2.0),
                     act, 0.005, 3.0, "lower")
    assert res["status"] == "OK" and res["derived"] == 2.0
    assert res["less_aggressive_than_today"] is False
    assert res["vs_today"]["delta_elog_per_day"] > 0
    # The same peak read on a "higher is more aggressive" constant below today is flagged.
    res = sgd._solve((1.0, 2.0, 3.0, 4.0), lambda v: noise + 0.3 - 0.2 * abs(v - 2.0),
                     act, 0.005, 3.0, "higher")
    assert res["derived"] == 2.0 and res["less_aggressive_than_today"] is True


def test_every_value_dead_is_stated_and_today_stands() -> None:
    act = _active()
    res = sgd._solve((1.0, 2.0), lambda v: np.full(act.shape, -1.0), act, 0.05, 1.0, "lower")
    assert res["status"].startswith("NO_SURVIVING_VALUE") and res["derived"] is None


def test_a_price_distance_in_the_risk_field_is_not_an_r() -> None:
    # 2026-09-16 family rows: risk_quote is a signed price distance and r_multiple 0.0.
    assert sgd.ledger_r({"r_multiple": 0.0, "pl_quote": -3.24, "risk_quote": -0.00026}) is None
    # A positive MONEY risk is a real denominator: P/L over it is the R.
    assert sgd.ledger_r({"r_multiple": 0.0, "pl_quote": 1.0, "risk_quote": 2.0}) == \
        pytest.approx(0.5)
    assert sgd.ledger_r({"r_multiple": -1.0966, "pl_quote": -6.2, "risk_quote": 5.67}) == \
        pytest.approx(-1.0966)


def test_a_truncated_order_comment_names_its_sleeve() -> None:
    names = {"eurgbp_discovered_asia_p_8e61ea22743f15b7"}
    assert sgd._sleeve_of({"sleeve": "eurgbp_discovered_asia_p_8e"}, names)
    assert not sgd._sleeve_of({"sleeve": "eurgbp"}, names)     # too short to name one sleeve
    assert not sgd._sleeve_of({"sleeve": "audusd_discovered_asia_p_8e"}, names)


def test_spread_geometry_reads_stop_in_spreads_and_widening() -> None:
    n = 40
    df = pd.DataFrame({"high": np.full(n, 101.0), "low": np.full(n, 99.0),
                       "close": np.full(n, 100.0), "spread": np.full(n, 10)})
    df.loc[25, "spread"] = 50
    x, w = sgd.spread_geometry(df, 0.01, 1.0, 14, 3)
    assert x[0] == pytest.approx(2.0 / 0.1)             # ATR 2.0 over a 0.10 spread
    assert w.max() == pytest.approx(5.0) and np.median(w) == pytest.approx(1.0)


def test_absent_inputs_read_unmeasured_never_a_default(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sgd, "SLEEVES", tmp_path / "absent.json")
    monkeypatch.setattr(sgd, "LEDGER", tmp_path / "absent.jsonl")
    doc = sgd.derive()
    assert doc["status"] == "UNMEASURED"
    for k in ("MIN_STOP_SPREAD_MULT", "ENTRY_DRIFT_TOL_FRAC"):
        assert doc[k]["status"].startswith("UNMEASURED")
        assert doc[k].get("derived") is None


def test_the_solve_is_kelly_survivals() -> None:
    import kelly_survival as ks
    assert (sgd.DEATH_LINE, sgd.EPS_DEATH, sgd.HORIZON) == (ks.DEATH_LINE, ks.EPS_DEATH,
                                                             ks.HORIZON)
    assert pytest.approx(0.20) == sgd.DEATH_LINE and pytest.approx(0.05) == sgd.EPS_DEATH
    assert sgd.HORIZON == 60


def test_a_value_kept_on_the_evidence_is_a_solved_constant(monkeypatch) -> None:
    ok = {"status": "OK", "derived": 0.05}
    kept = {"status": "TODAY_OPTIMAL_WITHIN_NOISE", "derived": 3.0}
    monkeypatch.setattr(sgd, "derive_min_stop_spread_mult", lambda deals, **k: dict(kept))
    monkeypatch.setattr(sgd, "derive_entry_drift_tol_frac", lambda deals, **k: dict(ok))
    assert sgd.derive()["status"] == "OK"


# ------------------------------------------------ the robustness gate: two-sided, derived N

def _linear_gap(root: float):
    """A stand-in solve whose candidate-vs-today gap is (edge - root) per day."""
    def fn(deals, edge_override=None, grid=None, against=None, **_k):
        return {"gap_vs_today": {"delta_elog_per_day": float(edge_override) - root}}
    return fn


def test_days_needed_is_two_ses_of_a_day_inside_the_distance_to_break_even() -> None:
    assert sgd.days_needed(1.0, 0.5) == 16          # (2 * 1.0 / 0.5)^2
    assert sgd.days_needed(1.2, 0.1) == 576
    assert sgd.days_needed(1.0, 0.0) >= 10 ** 6       # a decision on the knife-edge never adopts


def test_the_break_even_edge_is_found_on_the_nearer_side() -> None:
    e_star, dist = sgd.break_even_edge(_linear_gap(0.1), [], 0.2, 0.25, 0.05)
    assert e_star == pytest.approx(0.1, abs=0.01) and dist == pytest.approx(0.1, abs=0.01)
    e_star, dist = sgd.break_even_edge(_linear_gap(-5.0), [], 0.2, 0.25, 0.05)
    assert e_star is None and dist == sgd.EDGE_SEARCH_R


def _moved(cand: float, less: bool, live_days: int, measured: int, of: int,
           live_holds: bool = True) -> dict:
    return {"status": "OK", "derived": cand, "today": 0.25, "less_aggressive_than_today": less,
            "gap_vs_today": {"value": cand, "holds": live_holds},
            "inputs": {"rr": 1.5, "coverage": {"measured": measured, "of": of, "unit": "sym"},
                       "edge": {"posterior_r": 0.3, "live_days": live_days,
                                "live_day_mean_sd": None}}}


def test_the_gate_opens_the_same_way_for_a_more_aggressive_move() -> None:
    # Rule 2: a move UP is held to the same three tests, and adopted when they pass.
    fn = _linear_gap(-0.7)                            # break-even 1R away -> few days needed
    res = _moved(0.5, less=False, live_days=40, measured=10, of=16)
    g = sgd.robustness_gate(fn, [], res, {"gap_vs_today": {"holds": True}})
    assert g["adopt"] is True and g["adopt_value"] == 0.5
    assert g["direction"] == "more_aggressive"
    assert g["a_live_days"]["days_needed"] <= 40


def test_thin_live_evidence_publishes_the_value_and_keeps_todays() -> None:
    fn = _linear_gap(0.2)                             # break-even 0.1R from the live edge
    res = _moved(0.05, less=True, live_days=1, measured=3, of=16)
    g = sgd.robustness_gate(fn, [], res, {"gap_vs_today": {"holds": False}})
    assert g["adopt"] is False and g["adopt_value"] == 0.25
    assert g["direction"] == "less_aggressive"
    assert g["a_live_days"]["days_needed"] > 1
    assert "(a)" in g["reason"] and "(b)" in g["reason"] and "(c)" in g["reason"]
    assert "evidence-pending" in g["reason"]


def test_each_test_alone_blocks_adoption() -> None:
    fn = _linear_gap(-0.7)
    ok_prior = {"gap_vs_today": {"holds": True}}
    assert not sgd.robustness_gate(fn, [], _moved(0.5, False, 40, 7, 16), ok_prior)["adopt"]
    assert not sgd.robustness_gate(fn, [], _moved(0.5, False, 40, 10, 16),
                                   {"gap_vs_today": {"holds": False}})["adopt"]
    assert not sgd.robustness_gate(fn, [], _moved(0.5, False, 40, 10, 16, live_holds=False),
                                   ok_prior)["adopt"]
    assert not sgd.robustness_gate(fn, [], _moved(0.5, False, 0, 10, 16), ok_prior)["adopt"]


def test_no_move_has_nothing_to_adopt() -> None:
    g = sgd.robustness_gate(_linear_gap(0.0), [], {"status": "TODAY_OPTIMAL_WITHIN_NOISE",
                                                   "today": 3.0, "why": "flat"}, {})
    assert g == {"adopt": False, "adopt_value": 3.0, "reason": "no move to adopt: flat"}


def test_the_solve_reports_the_paired_gap_of_a_named_value() -> None:
    act = _active()
    noise = np.random.default_rng(2).normal(0.0, 0.5, act.shape)
    res = sgd._solve((1.0, 2.0, 3.0), lambda v: noise + 0.3 - 0.2 * abs(v - 2.0),
                     act, 0.005, 3.0, "lower", against=1.0)
    assert res["gap_vs_today"]["value"] == 1.0 and res["gap_vs_today"]["se"] > 0
