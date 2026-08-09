"""Pins R0247: the entry gate reads the cost-model size bucket COVERING the intended notional.

run_cost_model measures five size buckets (100/250/500/1000/2500 USDT per leg); `_rt_bps` read
only '500', discarding the d(cost)/d(size) slope every capacity verdict is a statement about.
These tests pin the three contract points of the lookup change:

  * the covering bucket (round UP, never down) is chosen for a given per-leg notional;
  * every degraded input -- no notional, non-positive notional, a single-bucket model, an
    unmeasured chosen bucket -- falls back to the legacy '500' read (current behaviour, never
    looser);
  * a LARGER notional can never gate CHEAPER than a smaller one (monotonicity guard), including
    the clamp against exhausted-snapshot selection effects that can make a big bucket's median
    read below the '500' bucket's.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import scripts.run_cashcarry_executor as ex

_BUCKETS = {
    "100": {"pair_roundtrip_bps": 1.0},
    "250": {"pair_roundtrip_bps": 2.5},
    "500": {"pair_roundtrip_bps": 5.0},
    "1000": {"pair_roundtrip_bps": 10.0},
    "2500": {"pair_roundtrip_bps": 25.0},
}


def _install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
             symbols: dict[str, dict]) -> None:
    cost = tmp_path / "cost_model.json"
    cost.write_text(json.dumps({"symbols": symbols}), "utf-8")
    monkeypatch.setattr(ex, "_COST_MODEL", cost)
    # No realised-fill floor in these tests: the lookup itself is under the microscope.
    monkeypatch.setattr(ex, "_TRADES", tmp_path / "no_trades.json")
    forensics = tmp_path / "trade_forensics.json"
    forensics.write_text(json.dumps({
        "worst_symbols": [{"symbol": "NOMUSDT", "n": 5, "bps": -149.0}]
    }), "utf-8")
    monkeypatch.setattr(ex, "_FORENSICS", forensics)


@pytest.fixture()
def _model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install(tmp_path, monkeypatch, {"BKTUSDT": {"pair": dict(_BUCKETS)}})


def test_covering_bucket_chosen_for_notional(_model: None) -> None:
    # Exact hit takes its own bucket; anything between buckets rounds UP to the covering one
    # (a $300 order is gated at the $500 book walk, never the cheaper $250 one).
    assert ex._rt_bps("BKTUSDT", notional=100.0) == 1.0
    assert ex._rt_bps("BKTUSDT", notional=250.0) == 2.5
    assert ex._rt_bps("BKTUSDT", notional=300.0) == 5.0
    assert ex._rt_bps("BKTUSDT", notional=800.0) == 10.0
    assert ex._rt_bps("BKTUSDT", notional=2500.0) == 25.0


def test_oversize_order_takes_largest_measured_bucket(_model: None) -> None:
    # Past the deepest measured size there is nothing to round up to: the largest bucket is
    # the best measured floor of the true cost -- still 5x tighter than the old fixed '500'.
    assert ex._rt_bps("BKTUSDT", notional=9000.0) == 25.0


def test_no_notional_keeps_legacy_500_lookup(_model: None) -> None:
    # Pre-R0247 callers (and a zero-free-capital tick) are byte-identical: fixed '500'.
    assert ex._rt_bps("BKTUSDT") == 5.0
    assert ex._rt_bps("BKTUSDT", notional=None) == 5.0
    assert ex._rt_bps("BKTUSDT", notional=0.0) == 5.0
    assert ex._rt_bps("BKTUSDT", notional=-100.0) == 5.0


def test_single_bucket_model_falls_back_to_500(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    # A model without the multi-bucket set (old artifact shape) = current behaviour exactly,
    # whatever the notional -- the fallback is never looser than today.
    _install(tmp_path, monkeypatch,
             {"BKTUSDT": {"pair": {"500": {"pair_roundtrip_bps": 5.0}}}})
    assert ex._rt_bps("BKTUSDT", notional=2500.0) == 5.0
    assert ex._rt_bps("BKTUSDT", notional=100.0) == 5.0


def test_unmeasured_chosen_bucket_falls_back_to_500_read(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    # The book exhausted at $2500 in every snapshot (median None): fall back to the LEGACY
    # '500' read, not silently elsewhere -- fallback is current behaviour.
    buckets = dict(_BUCKETS)
    buckets["2500"] = {"pair_roundtrip_bps": None}
    _install(tmp_path, monkeypatch, {"BKTUSDT": {"pair": buckets}})
    assert ex._rt_bps("BKTUSDT", notional=2500.0) == 5.0


def test_larger_notional_never_selects_cheaper_bucket(_model: None) -> None:
    # MONOTONICITY GUARD: walking the intended size up may never walk the gated cost down.
    grid = [50.0, 100.0, 250.0, 400.0, 500.0, 700.0, 1000.0, 1800.0, 2500.0, 10000.0]
    costs = [ex._rt_bps("BKTUSDT", notional=n) for n in grid]
    pairs = list(zip(grid, costs, strict=True))
    assert costs == sorted(costs), f"cost not monotone in size: {pairs}"
    # And at the selection level: the covering bucket key itself is non-decreasing.
    keys = [float(ex._cost_bucket_key(_BUCKETS, n)) for n in grid]
    assert keys == sorted(keys)


def test_non_monotone_bucket_data_never_gates_cheaper_than_500(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Exhausted-snapshot exclusion can make a big bucket's median survive only on deep-book
    # hours and read CHEAPER than '500'. A bigger order may never gate cheaper than the
    # legacy lookup did -- the clamp holds the '500' floor.
    buckets = dict(_BUCKETS)
    buckets["1000"] = {"pair_roundtrip_bps": 3.0}          # "cheaper" than 500's 5.0
    _install(tmp_path, monkeypatch, {"BKTUSDT": {"pair": buckets}})
    assert ex._rt_bps("BKTUSDT", notional=1000.0) == 5.0


def test_entry_gate_moves_with_intended_size(_model: None) -> None:
    # 0.00025/8h over a 24h min hold = 7.5 bps capture. Beats the $500-bucket 5.0 bps but not
    # the $2500-bucket 25.0 bps: the SAME symbol at the SAME funding flips on size alone --
    # exactly the slope the fixed-'500' lookup was blind to.
    assert ex._entry_gate("BKTUSDT", 0.00025, min_hold_h=24.0, notional=400.0) is True
    assert ex._entry_gate("BKTUSDT", 0.00025, min_hold_h=24.0, notional=2000.0) is False
