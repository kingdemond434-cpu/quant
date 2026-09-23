"""The proposers: plumbing, transition alpha, the weak-signal compiler, the fund playbook.

Every proposer shares one screen (`proposer_common`) and one door (the miner contract). What is
pinned here is the part that was learned the hard way today: a bar-construction artifact is not
an edge, a control that preserves the artifact is not a control, and a signal moved in time must
be re-anchored or the placebo is a different trade.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk.families_orthogonal import FAMILY_INPUTS, ORTHOGONAL_FAMILIES  # noqa: E402
from mt5desk.family_clock_transition import CATALOGUE, stamp_hours_for  # noqa: E402
from research.miner_candidate_compiler import compile_row  # noqa: E402

from research import fund_playbook, plumbing_miner  # noqa: E402
from research import proposer_common as pc


def _bars(days: int = 400, seed: int = 0, mark_hour: int | None = None,
          mark_bp: float = -1.7) -> pd.DataFrame:
    """Hourly bars; optionally with the open at one hour marked off the prior close every day."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=days * 24, freq="h", tz="UTC")
    c = np.exp(np.cumsum(rng.normal(scale=0.0008, size=idx.size))) * 100
    o = np.concatenate([[c[0]], c[:-1]])
    if mark_hour is not None:
        at = idx.hour == mark_hour
        o = o * np.where(at, 1.0 + mark_bp / 1e4, 1.0)
    h = np.maximum(o, c) * 1.0005
    lo = np.minimum(o, c) * 0.9995
    return pd.DataFrame({"open": o, "high": h, "low": lo, "close": c,
                         "tick_volume": rng.integers(100, 1000, size=idx.size)}, index=idx)


# ------------------------------------------------------------------------------------------
# The shared screen
# ------------------------------------------------------------------------------------------

def test_a_marked_open_is_detected_as_an_artifact_hour():
    d = _bars(mark_hour=0)
    hours = pc.artifact_hours(d)
    assert 0 in hours, "a 1.7bp daily mark at hour 0 must be flagged"
    assert not set(hours) - {0}, f"only the marked hour should be flagged, got {hours}"


def test_an_unmarked_feed_has_no_artifact_hours():
    assert pc.artifact_hours(_bars()) == {}


def test_the_hour_after_a_daily_gap_is_refused_as_a_reopen():
    d = _bars()
    d = d[d.index.hour != 22]                       # a 23-hour contract: no bar at 22
    hours = pc.artifact_hours(d)
    assert 23 in hours, "the bar after the daily gap is a reopen, not a price"


def test_the_screen_refuses_fills_at_and_windows_across_artifact_hours():
    from mt5desk.engine import Signal
    d = _bars(mark_hour=0)
    idx = d.index
    sigs = [Signal(time=idx[i], side=1, stop=0.0, target=1e9, ttl_bars=2, tag="t",
                   trigger=None, wait_bars=1)
            for i in range(24 * 50, 24 * 300, 24)]                # signal at hour 0 daily
    # entry would be hour 1, window hours 1..3: no artifact -> accepted
    sc = pc.screen(d, sigs, 0.0, {0: -11.0})
    assert sc is not None and sc["refused_unfillable"] == 0
    sigs23 = [Signal(time=idx[i - 1], side=1, stop=0.0, target=1e9, ttl_bars=2, tag="t",
                     trigger=None, wait_bars=1) for i in range(24 * 50, 24 * 300, 24)]
    # signal at 23 -> fill at hour 0, the marked open -> every one refused
    sc23 = pc.screen(d, sigs23, 0.0, {0: -11.0})
    assert sc23 is None or sc23["refused_unfillable"] == len(sigs23)
    sigs21 = [Signal(time=idx[i - 3], side=1, stop=0.0, target=1e9, ttl_bars=4, tag="t",
                     trigger=None, wait_bars=1) for i in range(24 * 50, 24 * 300, 24)]
    # signal at 21 -> fill at 22, window 23..2 CROSSES the marked open -> refused
    sc21 = pc.screen(d, sigs21, 0.0, {0: -11.0})
    assert sc21 is None or sc21["refused_unfillable"] == len(sigs21)


def test_deflation_charges_every_row_and_one_proposal_per_cell():
    rows = [{"cell": "A", "t_gross": 5.0, "clears_cost": True, "n_independent": 100, "params": {"x": i}}
            for i in range(3)] + [{"cell": "B", "t_gross": 0.1, "clears_cost": False,
                                   "n_independent": 100, "params": {}}]
    rows = pc.deflate(rows)
    assert all(r["n_tests_sweep"] == 4 for r in rows)
    best = pc.best_per_cell(rows)
    assert len(best) == 1 and best[0]["cell"] == "A"


def test_a_candidate_from_a_proposer_compiles_as_an_exact_recipe():
    c = pc.candidate("plumbing", "XAUUSD", "clock_transition",
                     {"label": "london_fix", "stamp_hour": 18, "mode": "fade", "side": 1,
                      "lead_bars": 2, "hold_bars": 4}, "m", "t", {"t_gross": 3.0})
    produced, disp = compile_row("plumbing", c, {"XAUUSD"})
    assert disp == "EXACT_RECIPE" and produced[0]["family"] == "clock_transition"


# ------------------------------------------------------------------------------------------
# Plumbing
# ------------------------------------------------------------------------------------------

def test_the_catalogue_converts_utc_to_stamp_hours_by_offset():
    assert set(stamp_hours_for("london_fix", 3)) == {18, 19}
    assert set(stamp_hours_for("london_fix", 0)) == {15, 16}
    assert set(stamp_hours_for("broker_rollover", 3)) == {23, 0}, "rollover is already in stamp"
    assert stamp_hours_for("nonsense", 3) == ()


def test_every_catalogue_moment_carries_its_economic_reason():
    for label, spec in CATALOGUE.items():
        assert len(spec["why"]) > 20, label


def test_the_family_refuses_off_catalogue_moments_and_bad_modes():
    fam = ORTHOGONAL_FAMILIES["clock_transition"]
    d = _bars()
    assert fam(d, label="made_up", stamp_hour=10) == []
    assert fam(d, label="london_fix", stamp_hour=10, mode="sideways") == []
    assert fam(d, label="london_fix", stamp_hour=99) == []
    assert fam(d, label="london_fix", stamp_hour=10, mode="out_of", side=1)


def test_the_three_modes_produce_distinct_entry_times():
    fam = ORTHOGONAL_FAMILIES["clock_transition"]
    d = _bars()
    into = {s.time.hour for s in fam(d, label="london_fix", stamp_hour=10, mode="into",
                                     lead_bars=2)}
    out = {s.time.hour for s in fam(d, label="london_fix", stamp_hour=10, mode="out_of")}
    assert into == {8} and out == {10}


def test_the_miner_refuses_to_run_without_a_broker_offset(monkeypatch):
    import research.session_phase as sp
    monkeypatch.setattr(sp, "broker_utc_offset_h", lambda: (None, "unknown"))
    rep = plumbing_miner.run(symbols=["XAUUSD"], budget_s=10, _inner=True)
    assert rep["tests_run"] == 0
    assert "refusing" in rep["skipped"].get("*", "")


def test_the_control_relabels_the_clock_rather_than_shuffling_returns():
    src = inspect.getsource(plumbing_miner._relabel_clock)
    assert "Timedelta(hours=shift)" in src
    d = _bars()
    r = plumbing_miner._relabel_clock(d, seed=1)
    assert np.array_equal(r["close"].to_numpy(), d["close"].to_numpy()), "bars must be untouched"
    assert (r.index != d.index).all()


def test_proposal_requires_beating_the_same_cell_under_a_relabelled_clock():
    src = inspect.getsource(plumbing_miner.run)
    assert "t_over_control" in src
    assert "> pc.PROPOSE_T" in src


# ------------------------------------------------------------------------------------------
# Fund playbook
# ------------------------------------------------------------------------------------------

def test_every_card_has_a_fund_a_grade_and_a_claim():
    for c in fund_playbook.CARDS:
        assert c["fund"] and c["grade"] in ("A", "B", "C") and len(c["claim"]) > 15


def test_executable_cards_name_registered_families_and_blocked_ones_name_the_blocker():
    donate, deepen, _info = fund_playbook.rows()
    assert donate, "no executable cards at all"
    for r in donate:
        assert r["family"] in ORTHOGONAL_FAMILIES or r["family"] in {"session_range_breakout"}
        assert r["evidence_grade"] in ("A", "B", "C")
    for r in deepen:
        assert r.get("blocked_on"), r


def test_grades_travel_with_the_row_but_change_nothing_in_the_compiler():
    donate, _d, _i = fund_playbook.rows()
    a = next(r for r in donate if r["evidence_grade"] == "A")
    c = next((r for r in donate if r["evidence_grade"] == "C"), None)
    # The compiler's universe is `known_symbols()`, which upper-cases parquet stems.
    uni = {a["symbol"].upper()} | ({c["symbol"].upper()} if c else set())
    _pa, da = compile_row("fund_playbook", a, uni)
    assert da == "EXACT_RECIPE"
    if c is not None:
        pc_, dc = compile_row("fund_playbook", c, uni)
        assert dc == "EXACT_RECIPE", "a C-grade card faces the same gauntlet as an A-grade one"


def test_no_card_targets_a_crypto_exchange_universe():
    for c in fund_playbook.CARDS:
        text = json.dumps(c).lower()
        for banned in ("binance", "bybit", "okx", "hyperliquid", "funding rate", "perp"):
            assert banned not in text, f"card touches a forbidden venue: {c['claim'][:60]}"


# ------------------------------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------------------------------

def test_new_families_are_registered_with_their_inputs():
    for fam in ("clock_transition", "multi_speed_trend", "ensemble"):
        assert fam in ORTHOGONAL_FAMILIES and fam in FAMILY_INPUTS


def test_multi_speed_trend_votes_across_speeds_and_the_crisis_variant_is_sparser():
    fam = ORTHOGONAL_FAMILIES["multi_speed_trend"]
    rng = np.random.default_rng(2)
    idx = pd.date_range("2019-01-01", periods=24 * 900, freq="h", tz="UTC")
    drift = np.where((np.arange(idx.size) // (24 * 120)) % 2 == 0, 0.0002, -0.0002)
    c = np.exp(np.cumsum(drift + rng.normal(scale=0.0006, size=idx.size))) * 100
    d = pd.DataFrame({"open": c, "high": c * 1.001, "low": c * 0.999, "close": c}, index=idx)
    all_ = fam(d)
    crisis = fam(d, crisis_only=True)
    assert all_ and len(crisis) < len(all_)
    assert fam(d, speeds=[]) == []
    assert fam(d, min_agreement=0.0) == []


def test_the_ensemble_refuses_without_a_runner_and_votes_with_one():
    from mt5desk.engine import Signal
    fam = ORTHOGONAL_FAMILIES["ensemble"]
    d = _bars(days=200)
    members = [{"symbol": "X", "family": "a", "params": {}}, {"symbol": "X", "family": "b",
                                                                "params": {}}]
    assert fam(d, members=members) == []
    times = list(d.index[24 * 30:24 * 30 + 200:10])

    def runner(sym, family, params, df):
        return [Signal(time=t, side=1, stop=0.0, target=1e9, ttl_bars=4, tag=family,
                       trigger=None, wait_bars=1) for t in times]
    sigs = fam(d, members=members, weights=[1.0, 1.0], threshold=0.5, hold_bars=4,
               _runner=runner)
    assert sigs and all(s.side == 1 for s in sigs)
    assert fam(d, members=members, weights=[1.0], _runner=runner) == [], "weight/member mismatch"
