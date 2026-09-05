"""The tape-only features, tested against hand-built tapes with known answers.

These are the numbers that justify the disk bill, so each one is checked against a case where
the right answer is arithmetic rather than opinion: a spread of exactly 12 points must produce an
effective spread of exactly 6 at zero latency, a mid that walks away from a fill by a known
amount must produce exactly that much price impact, and a bar whose high is printed in its first
minute must report high_first.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import microstructure as ms  # noqa: E402

POINT = 1e-5
T0 = 1_780_000_000_000


def _frame(bid_pts: list[int] | np.ndarray, spread_pts: int | list[int] = 12,
           step_ms: int = 1000) -> pd.DataFrame:
    bid_pts = np.asarray(bid_pts, dtype=np.int64)
    sp = (np.full(bid_pts.size, spread_pts, dtype=np.int64)
          if isinstance(spread_pts, int) else np.asarray(spread_pts, dtype=np.int64))
    df = pd.DataFrame({
        "time_msc": T0 + np.arange(bid_pts.size, dtype=np.int64) * step_ms,
        "bid": np.round(bid_pts * POINT, 5),
        "ask": np.round((bid_pts + sp) * POINT, 5),
        "last": 0.0, "volume": 0, "flags": 6,
    })
    return ms.quote_frame(df, POINT)


# ------------------------------------------------------------------ quote_frame --
def test_a_one_sided_quote_is_dropped_rather_than_read_as_a_price_of_zero() -> None:
    """`bid == 0` on an MT5 tick means the field did not update, and treating it as a price
    produces a spread of the entire quote."""
    raw = pd.DataFrame({"time_msc": [T0, T0 + 1, T0 + 2],
                        "bid": [1.10000, 0.0, 1.10002],
                        "ask": [1.10012, 1.10013, 0.0],
                        "last": 0.0, "volume": 0, "flags": 6})
    out = ms.quote_frame(raw, POINT)
    assert len(out) == 1


def test_the_unit_is_never_guessed() -> None:
    with pytest.raises(ValueError, match="never guessed"):
        ms.quote_frame(_frame([100_000]), 0.0)


def test_the_microprice_degrades_to_the_mid_and_says_so() -> None:
    """A CFD feed has no per-side size. Inventing one to make the formula run produces a model
    of the invention."""
    df = _frame([100_000, 100_001, 100_002])
    assert (df["microprice"] == df["mid"]).all()
    assert set(df["microprice_basis"]) == {"mid_fallback"}


# ------------------------------------------------------------ effective spread --
def test_effective_spread_at_zero_latency_is_exactly_half_the_quoted_spread() -> None:
    """The reference point of the whole cost surface. If this is not exactly 6 on a 12-point
    spread, every number built on it is off by a constant nobody will find."""
    df = _frame([100_000] * 100, spread_pts=12)
    eff = ms.effective_spread_pts(df, 0, POINT)
    assert eff.size == 100, "at zero latency every tick is its own fill"
    assert np.allclose(eff, 6.0, atol=1e-6)


def test_effective_spread_grows_with_latency_when_the_market_moves_against_you() -> None:
    """THE TERM EVERY COST MODEL ON THIS DESK CURRENTLY SETS TO ZERO. A bar's spread column
    cannot see it: it is the distance the quote travelled while the order was in flight."""
    df = _frame(100_000 + np.arange(600), spread_pts=12, step_ms=1000)   # +1 point per second
    at0 = float(np.median(ms.effective_spread_pts(df, 0, POINT)))
    at10s = float(np.median(ms.effective_spread_pts(df, 10_000, POINT)))
    assert at0 == pytest.approx(6.0, abs=1e-6)
    # A buy pays 10 points more; a sell saves 10; the two-sided mean is unchanged BY DESIGN,
    # so the asymmetry is checked on the side that actually pays it.
    buy0 = float(np.median(ms.effective_spread_pts(df, 0, POINT, side="buy")))
    buy10 = float(np.median(ms.effective_spread_pts(df, 10_000, POINT, side="buy")))
    assert buy10 - buy0 == pytest.approx(10.0, abs=0.5), (
        "a decision at t filled 10s later on a market moving 1 point/s must cost 10 more points")
    assert at10s == pytest.approx(at0, abs=0.5)


def test_a_decision_whose_fill_falls_outside_the_tape_is_dropped_not_filled_forward() -> None:
    """Reporting the cost of a fill that did not happen inside the data is a fabricated number."""
    df = _frame([100_000] * 20, step_ms=1000)          # 19 seconds of tape
    assert ms.effective_spread_pts(df, 0, POINT).size == 20
    assert ms.effective_spread_pts(df, 10_000, POINT).size == 10
    assert ms.effective_spread_pts(df, 60_000, POINT).size == 0


# ------------------------------------------------------------- realised spread --
def test_price_impact_is_positive_when_the_mid_runs_away_from_fills() -> None:
    """Quoted minus realised spread separates 'this symbol is expensive' from 'this desk is
    trading it just before it moves'. No bar-level spread column can do that."""
    trending = _frame(100_000 + np.arange(400), spread_pts=20, step_ms=1000)
    st = ms.hour_cell(trending, "TREND", 0, POINT, min_ticks=50)
    impact = ms.price_impact_pts(st, 30_000)
    assert impact is not None and impact > 0, (
        f"a mid walking away from every fill must show adverse selection, got {impact}")
    # 1 point per second over 30s, doubled by the decomposition's factor of two.
    assert impact == pytest.approx(60.0, rel=0.05)

    flat = _frame([100_000] * 400, spread_pts=20, step_ms=1000)
    st_flat = ms.hour_cell(flat, "FLAT", 0, POINT, min_ticks=50)
    assert ms.price_impact_pts(st_flat, 30_000) == pytest.approx(0.0, abs=1e-6), (
        "on a mid that never moves the whole quoted spread is a fee, not a warning")


def test_the_two_sided_average_realised_spread_is_identically_the_quoted_spread() -> None:
    """REGRESSION, and the reason `realised_spread_pts` takes a side.

    buy + sell = 2*(ask - mid_h) + 2*(mid_h - bid) = 2*(ask - bid). The mid terms cancel exactly,
    so an averaged 'realised spread' is the quoted spread on every tape ever recorded and any
    price impact derived from it is zero by construction -- a number that looks like a
    measurement and carries no information at all.
    """
    df = _frame(100_000 + np.arange(400), spread_pts=20, step_ms=1000)
    buy = ms.realised_spread_pts(df, 30_000, POINT, side="buy")
    sell = ms.realised_spread_pts(df, 30_000, POINT, side="sell")
    assert np.allclose((buy + sell) / 2.0, 20.0, atol=1e-6)
    assert not np.allclose(buy, sell), "the sides must differ on a market that is moving"


# ----------------------------------------------------------------- intensity --
def test_quote_intensity_counts_updates_per_minute() -> None:
    df = _frame([100_000] * 300, step_ms=1000)         # 1 per second, 5 minutes
    inten = ms.quote_intensity(df, "1min")
    # The first and last buckets are partial (T0 is not on a minute boundary), so the full
    # interior buckets are the ones with a known answer.
    assert inten.iloc[1:-1].eq(60.0).all()
    assert inten.sum() == 300.0


def test_burstiness_is_near_one_for_an_even_feed_and_above_one_for_a_clustered_one() -> None:
    """1.0 is a Poisson feed. Above 1 the feed CLUSTERS, which is what a real quote stream does
    around news -- and which a bar's tick count averages away entirely."""
    even = pd.Series([60.0] * 40)
    assert ms.burstiness(even) == pytest.approx(0.0, abs=1e-9)
    clustered = pd.Series([0.0] * 20 + [120.0] * 20)
    b = ms.burstiness(clustered)
    assert b is not None and b > 5.0


def test_a_series_with_too_few_buckets_returns_none_rather_than_a_number() -> None:
    assert ms.burstiness(pd.Series([1.0, 2.0])) is None


def test_stale_fraction_finds_a_republishing_feed() -> None:
    """A high stale fraction with a high tick count is a feed republishing itself, which looks
    like a busy market to anything counting ticks."""
    df = _frame([100_000] * 100)
    assert ms.stale_fraction(df) == pytest.approx(1.0)
    df2 = _frame(100_000 + np.arange(100))
    assert ms.stale_fraction(df2) == pytest.approx(0.0)


# ----------------------------------------------------------------------- OFI --
def test_the_flow_proxy_is_always_labelled_a_proxy() -> None:
    """A CFD feed has no aggressor flag. Anything calling itself order flow here would be a model
    of the naming, not of the flow."""
    df = _frame(100_000 + np.arange(50))
    e, basis = ms.order_flow_imbalance(df)
    assert basis == "sign_only"
    assert e.size == 49
    # A bid walking up with a constant spread is one-sided buy pressure under the sign rule.
    assert (e > 0).all()


# --------------------------------------------------------------- intrabar path --
def test_the_true_intrabar_path_says_which_extreme_came_first() -> None:
    """THE ASSUMPTION THIS RETIRES. Assuming the favourable extreme came first flatters every
    strategy; assuming the adverse one did buries real ones. Neither is a measurement."""
    # Up to +50 in the first ten minutes, then down to -50: the high is printed FIRST.
    pts = np.concatenate([100_000 + np.arange(0, 51), 100_050 - np.arange(1, 101)])
    df = _frame(pts, step_ms=1000)
    path = ms.intrabar_path(df, "1h")
    assert len(path) == 1
    row = path.iloc[0]
    assert bool(row["high_first"]) is True
    assert row["t_high_ms"] < row["t_low_ms"]
    assert row["path_ticks"] == len(pts)

    reversed_pts = pts[::-1]
    row2 = ms.intrabar_path(_frame(reversed_pts, step_ms=1000), "1h").iloc[0]
    assert bool(row2["high_first"]) is False


def test_excursions_are_reported_in_points_for_a_long_at_the_open() -> None:
    pts = np.concatenate([[100_000], 100_000 + np.array([30, -20, 10])])
    path = ms.path_excursions(ms.intrabar_path(_frame(pts), "1h"), POINT)
    row = path.iloc[0]
    assert row["mfe_pts"] == pytest.approx(30.0, abs=1e-6)
    assert row["mae_pts"] == pytest.approx(20.0, abs=1e-6)


def test_a_random_walk_prints_its_high_first_about_half_the_time() -> None:
    """A sanity check with a known answer: on a driftless walk the two extremes are exchangeable,
    so a materially different rate means the path measurement itself is wrong."""
    rng = np.random.default_rng(11)
    pts = 100_000 + np.cumsum(rng.choice([-1, 1], size=60_000))
    path = ms.intrabar_path(_frame(pts, step_ms=100), "1min")   # ~100 bars of ~600 ticks each
    assert len(path) >= 40, "a handful of bars cannot evidence a rate"
    frac = float(path["high_first"].mean())
    # n>=40 gives a binomial sd of ~0.079 under the null, so +-3sd is roughly [0.26, 0.74].
    assert 0.3 < frac < 0.7, frac


# ------------------------------------------------------------------ hour cells --
def test_a_thin_cell_is_unmeasured_and_carries_its_n() -> None:
    """A percentile over 30 quotes is a percentile wearing a costume."""
    st = ms.hour_cell(_frame([100_000] * 30), "THIN", 3, POINT)
    assert st.status == "UNMEASURED"
    assert st.n_ticks == 30
    assert st.quoted_spread_pts_p50 is None
    assert st.effective_spread_pts == {}


def test_zero_spread_rows_are_excluded_from_the_percentile_but_their_share_is_published() -> None:
    """Fusion ZERO is commission-only and 24 of 251 symbols genuinely quote 0.0. That is real,
    but it is not a spread OBSERVATION, and a symbol that is mostly zero must not be able to
    report a confident cheap number."""
    sp = np.array([0] * 300 + [12] * 300, dtype=np.int64)
    df = _frame([100_000] * 600, spread_pts=list(sp))
    st = ms.hour_cell(df, "ZERO", 5, POINT, min_ticks=200)
    assert st.zero_spread_frac == pytest.approx(0.5, abs=0.01)
    assert st.quoted_spread_pts_p50 == pytest.approx(12.0, abs=1e-6), (
        "the median must be of the PRICED rows, not dragged to 6 by the free ones")


def test_the_latency_slip_is_reported_on_top_of_the_half_spread_not_including_it() -> None:
    """A consumer that already charges the half-spread must not double-charge it."""
    df = _frame([100_000] * 500, spread_pts=12, step_ms=100)
    st = ms.hour_cell(df, "FLAT", 7, POINT, min_ticks=100)
    assert st.effective_spread_pts["0"] == pytest.approx(6.0, abs=1e-6)
    assert st.latency_slip_pts["0"] == pytest.approx(0.0, abs=1e-6)
    assert st.latency_slip_pts["1000"] == pytest.approx(0.0, abs=1e-6)


def test_the_latency_grid_matches_the_module_that_prices_latency() -> None:
    """`mt5desk/latency.py` asks what latency is WORTH; this measures what it COSTS. A shared
    grid is what makes one answer usable by the other."""
    from mt5desk.latency import GRID_MS
    assert ms.LATENCY_GRID_MS == GRID_MS
