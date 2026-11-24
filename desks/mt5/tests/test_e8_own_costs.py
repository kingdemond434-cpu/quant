"""E8 is sized on its own measured spread where it has measured it (prop_challenge_allocator)."""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import prop_challenge_allocator as pca  # noqa: E402

NOW = datetime(2026, 11, 24, 22, 0, tzinfo=UTC)
COL = "EURUSD_session_range_breakout_asia"


def _cost(bias: float = 0.02) -> dict:
    return {COL: {"status": "PRICED", "method": "RATIO x BASE_COST_R 0.05", "hour": 1,
                  "charged_spread_px": 0.0001, "bias_r_per_trade": bias}}


def _spreads(median_bps: float, n: int = 12, live: bool = True, age_h: float = 1.0) -> dict:
    return {"generated_utc": (NOW - timedelta(hours=age_h)).isoformat(),
            "by_hour": {"EURUSD": {"1": {"n": n, "median": median_bps}}},
            "liveness": {"EURUSD": {"usable_as_cost": live}},
            "mid": {"EURUSD": 1.0}}


def test_dearer_at_e8_lowers_the_mean_and_cheaper_raises_it() -> None:
    from libs.portfolio.execution_cost import BASE_COST_R, MAX_RATIO
    # 3 bps at mid 1.0 = 0.0003 price = 3x the charged spread.
    d, src = pca.e8_cost_overlay([COL], _cost(), _spreads(3.0), now=NOW)
    want = BASE_COST_R * (min(3.0, MAX_RATIO) - 1.0) - 0.02
    assert abs(d[COL] - round(want, 6)) < 1e-9 and src[COL].startswith("E8_MEASURED")
    # Tighter than the replay charged: E8 bias 0, so the FTMO charge is handed back.
    d, src = pca.e8_cost_overlay([COL], _cost(), _spreads(0.5), now=NOW)
    assert d[COL] == -0.02 and src[COL].startswith("E8_MEASURED")


def test_thin_frozen_stale_or_unmidded_cells_keep_the_ftmo_cost() -> None:
    for doc, why in ((_spreads(3.0, n=9), "n=9"), (_spreads(3.0, live=False), "not live"),
                     (_spreads(3.0, age_h=24 * 8), "old"), ({}, "absent")):
        d, src = pca.e8_cost_overlay([COL], _cost(), doc, now=NOW)
        assert d == {} and src[COL].startswith("FTMO_PROXY") and why in src[COL], src
    doc = _spreads(3.0)
    doc["mid"] = {}
    d, src = pca.e8_cost_overlay([COL], _cost(), doc, now=NOW)
    assert d == {} and "mid unpublished" in src[COL]


def test_only_the_ratio_method_is_repriced() -> None:
    cost = _cost()
    cost[COL]["method"] = "STOP_MEASURED (risk/lot 500)"
    d, src = pca.e8_cost_overlay([COL], cost, _spreads(3.0), now=NOW)
    assert d == {} and "method" in src[COL]


def test_the_solve_draws_its_worlds_after_the_e8_cost_move() -> None:
    src = (DESK / "research" / "prop_challenge_allocator.py").read_text("utf-8")
    body = src[src.index("def solve("):]
    assert body.index("e8_cost_overlay(") < body.index("make_worlds(r, n_paths")


def test_the_sampler_publishes_mids() -> None:
    src = (DESK / "prop" / "e8_spread_sampler.py").read_text("utf-8")
    assert '"mid": dict(mids)' in src
