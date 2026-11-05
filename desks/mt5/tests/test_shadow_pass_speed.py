"""The shadow pass measures where its time goes and never recomputes an identical replay.

Measured 2026-11-05: the pass took 9,224 s against a 1 h trigger, and 226 of 893 replayed rows
produced results identical to another row's.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(DESK))

import shadow_forward as sf  # noqa: E402


def _frame():
    idx = pd.date_range("2026-10-01", periods=5, freq="h", tz="UTC")
    return pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}, index=idx)


def test_identical_inputs_hit_and_any_difference_misses():
    memo, bars, other = sf.ReplayMemo(), _frame(), _frame()
    factor = _frame()
    k = memo.signal_key("formula", "M5", False, {"a": 1, "b": [1, 2]}, bars, {"f": factor})
    memo.put(k, ["sig"], bars, {"f": factor})
    same = memo.signal_key("formula", "M5", False, {"b": [1, 2], "a": 1}, bars, {"f": factor})
    assert memo.get(same) == ["sig"]                          # key order is canonical
    for miss in (
        memo.signal_key("formula", "M5", False, {"a": 2, "b": [1, 2]}, bars, {"f": factor}),
        memo.signal_key("formula", "M5", True, {"a": 1, "b": [1, 2]}, bars, {"f": factor}),
        memo.signal_key("formula", "M15", False, {"a": 1, "b": [1, 2]}, bars, {"f": factor}),
        memo.signal_key("carry", "M5", False, {"a": 1, "b": [1, 2]}, bars, {"f": factor}),
        memo.signal_key("formula", "M5", False, {"a": 1, "b": [1, 2]}, other, {"f": factor}),
        memo.signal_key("formula", "M5", False, {"a": 1, "b": [1, 2]}, bars, {"f": other}),
        memo.signal_key("formula", "M5", False, {"a": 1, "b": [1, 2]}, bars, {}),
    ):
        assert memo.get(miss) is None


def test_the_simulation_is_keyed_on_costs_too():
    memo, bars = sf.ReplayMemo(), _frame()
    k = memo.signal_key("carry", "H1", False, {}, bars, None)
    memo.put(memo.backtest_key(k, ("spread", 1.0)), "res", bars, None)
    assert memo.get(memo.backtest_key(k, ("spread", 1.0))) == "res"
    assert memo.get(memo.backtest_key(k, ("spread", 1.1))) is None


def test_entries_pin_their_frames_so_an_id_is_never_recycled():
    memo = sf.ReplayMemo()
    bars, factor = _frame(), _frame()
    k = memo.signal_key("x", "H1", False, {}, bars, {"f": factor})
    memo.put(k, "v", bars, {"f": factor})
    _value, held_bars, held_extra, held_refs = memo._store[k]
    assert held_bars is bars and held_extra["f"] is factor
    assert any(r is factor for r in held_refs)
    memo.clear()
    assert memo.get(k) is None


def test_the_profile_reports_phases_rows_and_reuse():
    prof = sf.PassProfile()
    prof.row("A.formula.asia@M5", "formula", "M5")
    with prof.phase("signals"):
        time.sleep(0.01)
    prof.hit("backtest")
    prof.row("B.carry.asia", "carry", "H1")
    mid = prof.report()                                       # a checkpoint mid-pass
    assert mid["rows_timed"] == 2
    rep = prof.report()
    assert rep["phase_calls"] == {"signals": 1} and rep["reused"] == {"backtest": 1}
    assert rep["phase_seconds"]["signals"] >= 0.0
    assert set(rep["family_seconds"]) == {"formula", "carry"}
    assert set(rep["chart_seconds"]) == {"M5", "H1"}
    assert rep["slowest_rows"][0]["key"] == "A.formula.asia@M5"


def test_the_pass_shares_signals_and_simulation_and_publishes_its_profile():
    src = (DESK / "research" / "shadow_forward.py").read_text(encoding="utf-8")
    assert "_sig_key = memo.signal_key(fam, sleeve_tf, _short, call_params, h1, extra)" in src
    assert "_bt_key = memo.backtest_key(_sig_key, costs)" in src
    assert '"profile": prof.report()' in src
    assert "memo.clear()" in src
    cyc = (DESK / "research" / "shadow_cycle.py").read_text(encoding="utf-8")
    assert '"engine_profile"' in cyc and '"stage_seconds": stage_seconds' in cyc


def test_frames_nested_anywhere_in_the_inputs_are_keyed_by_identity():
    memo, bars = sf.ReplayMemo(), _frame()
    a, b = _frame(), _frame()                                 # equal values, different objects
    for shape in (lambda f: {"drivers": {"x": f}}, lambda f: {"factors": [1, f]}):
        k = memo.signal_key("formula", "M5", False, {}, bars, shape(a))
        memo.put(k, "va", bars, shape(a))
        assert memo.get(memo.signal_key("formula", "M5", False, {}, bars, shape(a))) == "va"
        assert memo.get(memo.signal_key("formula", "M5", False, {}, bars, shape(b))) is None
        assert any(r is a for r in memo._store[k][3])         # the nested frame is pinned


def test_non_native_leaves_in_params_are_keyed_by_identity_not_by_repr():
    memo, bars = sf.ReplayMemo(), _frame()
    s1 = pd.Series([1.0, 2.0])
    s2 = pd.Series([1.0, 2.0])
    k = memo.signal_key("x", "H1", False, {"w": s1}, bars, None)
    memo.put(k, "v", bars, None)
    assert memo.get(memo.signal_key("x", "H1", False, {"w": s1}, bars, None)) == "v"
    assert memo.get(memo.signal_key("x", "H1", False, {"w": s2}, bars, None)) is None
