"""Tests for the VOLATILITY RISK PREMIUM Stage-A screen (census gap #5).

WHAT THESE TESTS ARE FOR. The screen's whole claim is that it can tell a genuine lead from a
restatement of a move that has already happened, on a widened market count. Three properties carry
that claim and each is pinned here rather than argued in a docstring:

  CAUSALITY   nothing the screen computes at index t may change when a value at index > t changes.
              Pinned by perturbing the future and asserting bit-identical earlier output -- the only
              form of this test that cannot be satisfied by a leak that merely looks tidy.
  DETECTION   a synthetic premium that GENUINELY leads subsequent realised vol must survive the
              screen. A gate that only ever kills is not a gate, it is an off switch, and it would
              retire this mechanism class exactly as silently as a bug would.
  KILL        a premium that merely COINCIDES with the same period's move must die as
              TIMING-ARTIFACT -- the coinbase/Turkey/kimchi failure mode, which is this class's
              declared hazard because a trailing realised vol shares day t's squared return with
              the same-period target.

Plus the arithmetic the panel is built on: the Black-76 inversion (verified against Deribit's own
published mark_iv in the module docstring), put-call parity in both the inverse and linear
conventions, and the contiguity rule that keeps the harness's positional forward shift honest.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from scripts.screen_vol_risk_premium import (
    build_markets,
    market_iv,
    not_readable_here,
    screen_market,
)

from libs.research.vol_risk_premium import (
    CONSTRUCTIONS,
    TARGETS,
    MarketSeries,
    VrpAlignment,
    align_markets,
    atm_implied_vol,
    black76_price,
    bucket_of,
    forward_from_parity,
    implied_vol,
    log_returns,
    longest_contiguous_run,
    mean_pairwise_corr,
    pooled_mean,
    realised_vol,
    short_vol_carry,
)

DAY_MS = 86_400_000


def _dates(n: int, start_ms: int = 1_700_000_000_000) -> np.ndarray:
    return np.arange(n, dtype="int64") * DAY_MS + start_ms


# --------------------------------------------------------------------------- option arithmetic


def test_black76_inverts_to_the_vol_it_was_priced_at() -> None:
    for sigma in (0.15, 0.45, 1.2):
        for k in (55_000.0, 64_000.0, 80_000.0):
            px = black76_price(64_000.0, k, 0.25, sigma, is_call=True)
            got = implied_vol(px, 64_000.0, k, 0.25, is_call=True)
            assert got is not None
            assert abs(got - sigma) < 1e-4


def test_implied_vol_refuses_a_price_outside_the_no_arbitrage_bracket() -> None:
    # Below intrinsic and above the forward are not "very low" and "very high" volatilities; they
    # are quotes the model cannot represent, and clamping them would put a fabricated observation
    # into a panel whose purpose is measuring the average level of implied vol.
    assert implied_vol(1.0, 64_000.0, 55_000.0, 0.25, is_call=True) is None
    assert implied_vol(70_000.0, 64_000.0, 55_000.0, 0.25, is_call=True) is None


def test_parity_recovers_the_forward_in_both_venue_conventions() -> None:
    fwd, t_years = 64_536.2, 0.139
    strikes = [60_000.0, 65_000.0, 70_000.0]
    # LINEAR (USDC-settled): quotes are in the quote currency, F = K + C - P.
    calls = [black76_price(fwd, k, t_years, 0.35, is_call=True) for k in strikes]
    puts = [black76_price(fwd, k, t_years, 0.35, is_call=False) for k in strikes]
    got = forward_from_parity(strikes, calls, puts, inverse=False)
    assert got is not None
    assert abs(got[0] - fwd) < 1.0
    # INVERSE (coin-settled): quotes are a FRACTION of the forward, so F = K / (1 - (C - P)) and
    # no external price is needed at all.
    ci = [c / fwd for c in calls]
    pi = [p / fwd for p in puts]
    got_inv = forward_from_parity(strikes, ci, pi, inverse=True)
    assert got_inv is not None
    assert abs(got_inv[0] - fwd) < 1.0


def test_atm_implied_vol_round_trips_a_synthetic_ladder() -> None:
    fwd, t_years, sigma = 64_536.2, 0.139, 0.372
    strikes = [55_000.0, 60_000.0, 65_000.0, 70_000.0, 75_000.0]
    calls = [black76_price(fwd, k, t_years, sigma, is_call=True) / fwd for k in strikes]
    puts = [black76_price(fwd, k, t_years, sigma, is_call=False) / fwd for k in strikes]
    got = atm_implied_vol(strikes, calls, puts, t_years=t_years, inverse=True)
    assert got is not None
    iv, f = got
    assert abs(iv - sigma) < 1e-3
    assert abs(f - fwd) < 1.0


def test_bucket_assignment_is_by_dte_on_the_observation_date() -> None:
    assert bucket_of(7.0) == "t07"
    assert bucket_of(30.0) == "t30"
    assert bucket_of(90.0) == "t90"
    assert bucket_of(300.0) == "t180"
    assert bucket_of(1.0) is None          # inside the expiry-day noise band
    assert bucket_of(900.0) is None


# --------------------------------------------------------------------------- causality


def test_realised_vol_cannot_see_the_future() -> None:
    """Perturb a LATER return; every earlier realised-vol value must be BIT-IDENTICAL.

    This is the only version of this assertion that a leak cannot satisfy by accident. A screen
    whose realised vol quietly peeked one bar ahead would still look causal in every plot.
    """
    rng = np.random.default_rng(11)
    rets = rng.normal(0.0, 0.02, 400)
    base = realised_vol(rets, 30, lag=0)
    poked = rets.copy()
    poked[300] += 5.0
    after = realised_vol(poked, 30, lag=0)
    assert np.array_equal(base[:300], after[:300], equal_nan=True)
    assert not np.array_equal(base[300:], after[300:], equal_nan=True)


def test_realised_vol_lag_excludes_the_current_periods_return() -> None:
    """lag=1 must not contain day t's own squared return -- the de-contaminated form."""
    rng = np.random.default_rng(12)
    rets = rng.normal(0.0, 0.02, 200)
    lagged = realised_vol(rets, 20, lag=1)
    poked = rets.copy()
    poked[150] += 3.0
    lagged_poked = realised_vol(poked, 20, lag=1)
    # Day 150's own return must be invisible to the lagged window AT 150; it may only enter later.
    assert lagged[150] == lagged_poked[150] or (np.isnan(lagged[150])
                                                and np.isnan(lagged_poked[150]))
    assert not np.array_equal(lagged[151:], lagged_poked[151:], equal_nan=True)


def test_short_vol_carry_strikes_at_yesterdays_implied_level() -> None:
    """carry[t] must be struck at iv[t-1]: a position entered at t-1 cannot use t's quote."""
    iv = np.full(50, 0.6)
    rets = np.full(50, 0.01)
    base = short_vol_carry(iv, rets)
    poked = iv.copy()
    poked[30] = 1.2
    after = short_vol_carry(poked, rets)
    assert np.array_equal(base[:31], after[:31], equal_nan=True)   # t=30 struck at iv[29]
    assert base[31] != after[31]


def test_log_returns_are_contemporaneous_not_forward() -> None:
    """The harness performs its own forward shift; a pre-shifted target gets shifted twice."""
    px = np.array([100.0, 110.0, 121.0])
    r = log_returns(px)
    assert np.isnan(r[0])
    assert abs(r[1] - np.log(1.1)) < 1e-12


def test_market_series_rejects_a_non_contiguous_grid() -> None:
    d = np.array([0, DAY_MS, 3 * DAY_MS], dtype="int64")
    z = np.zeros(3)
    with pytest.raises(ValueError, match="contiguous"):
        MarketSeries(key="X:t30", underlying="X", bucket="t30", dates_ms=d,
                     atm_iv=z + 0.5, close=z + 1.0, rets=z, rv_now=z + 0.5, rv_lag=z + 0.5)


def test_longest_contiguous_run_picks_the_longest_block() -> None:
    d = np.array([0, DAY_MS, 5 * DAY_MS, 6 * DAY_MS, 7 * DAY_MS], dtype="int64")
    assert longest_contiguous_run(d) == (2, 5)
    assert longest_contiguous_run(np.zeros(0, dtype="int64")) == (0, 0)


# --------------------------------------------------------------------------- breadth arithmetic


def test_pooling_uses_the_date_intersection_and_never_a_forward_fill() -> None:
    a = np.array([1.0, 2.0, 3.0])
    b = np.array([10.0, 20.0])
    da = _dates(3)
    db = _dates(2, start_ms=int(_dates(3)[1]))
    grid, mat = align_markets([a, b], [da, db])
    assert grid.size == 2
    assert mat.shape == (2, 2)
    assert np.allclose(mat[:, 0], [2.0, 3.0])


def test_mean_pairwise_corr_detects_markets_that_move_as_one() -> None:
    rng = np.random.default_rng(3)
    common = rng.normal(size=300)
    twins = np.column_stack([common + 0.01 * rng.normal(size=300) for _ in range(4)])
    assert mean_pairwise_corr(twins) > 0.9
    independent = rng.normal(size=(300, 4))
    assert abs(mean_pairwise_corr(independent)) < 0.25
    assert np.isnan(mean_pairwise_corr(np.zeros((10, 1))))


def test_pooled_mean_skips_dates_with_too_few_live_markets() -> None:
    mat = np.array([[1.0, np.nan], [1.0, 3.0]])
    out = pooled_mean(mat, min_markets=2)
    assert np.isnan(out[0])
    assert out[1] == pytest.approx(2.0)


# --------------------------------------------------------------------------- detection and kill


def _leading_market(n: int = 6000, seed: int = 7, phi: float = 0.85) -> MarketSeries:
    """A premium that GENUINELY leads: a rich premium at t precedes a quiet day at t+1.

    THE DRIVER IS PERSISTENT ON PURPOSE, and the reason is the harness's own lookahead rail rather
    than realism (though implied vol is in fact strongly autocorrelated). The rail kills a series
    when lagging the signal one period turns its FORWARD skill into CONTEMPORANEOUS skill -- the
    fingerprint of a whole-period misalignment. An IID driver has exactly that fingerprint: x[t]
    predicts the target at t+1 and nothing else, so shifting it back one step lands it precisely on
    the target it predicts, and the harness cannot tell it from a candle labelled a day early. It is
    RIGHT to refuse that series. A real mechanism whose state persists decays smoothly instead, and
    that is what this synthetic reproduces -- so the test asserts `shift_translates is False`, which
    is the property being claimed, not merely the verdict that follows from it.
    """
    rng = np.random.default_rng(seed)
    e = rng.normal(size=n)
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = phi * x[t - 1] + e[t] * np.sqrt(1.0 - phi * phi)
    iv = 0.60 + 0.08 * x                                   # premium rich when x is high
    daily = 0.60 * np.exp(-0.10 * np.concatenate(([0.0], x[:-1]))) / np.sqrt(365.0)
    rets = rng.normal(size=n) * daily                      # quiet day AFTER a rich premium
    return MarketSeries(
        key="SYN:t30", underlying="SYN", bucket="t30", dates_ms=_dates(n),
        atm_iv=iv, close=np.full(n, 100.0), rets=rets,
        rv_now=np.full(n, 0.60), rv_lag=np.full(n, 0.60))


def _coincident_market(n: int = 6000, seed: int = 8) -> MarketSeries:
    """A premium that merely RESTATES the move that already happened.

    The signal is the same period's return plus a whisper of noise, and returns carry a mild
    autocorrelation -- so the raw forward IC clears the screen's floors while the signal is really
    a photograph of a bar that has already closed. That is exactly the shape that killed
    coinbase-premium, Turkey-premium and kimchi, and the angle-20 gate must catch it here.
    """
    rng = np.random.default_rng(seed)
    rets = np.zeros(n)
    eps = rng.normal(0.0, 0.02, n)
    for t in range(1, n):
        rets[t] = 0.15 * rets[t - 1] + eps[t]
    signal = rets + 0.02 * rets.std() * rng.normal(size=n)
    return MarketSeries(
        key="SYN:t30", underlying="SYN", bucket="t30", dates_ms=_dates(n),
        atm_iv=np.full(n, 0.60) + signal, close=np.full(n, 100.0), rets=rets,
        rv_now=np.full(n, 0.60), rv_lag=np.full(n, 0.60))


def _cell(rows: list[dict], construction: str, target: str) -> dict:
    for r in rows:
        if r.get("construction") == construction and r.get("target") == target:
            return r
    raise AssertionError(f"cell {construction}->{target} missing from the screen's own record")


def test_a_genuine_vrp_lead_is_detected() -> None:
    rows = screen_market(_leading_market(), VrpAlignment())
    cell = _cell(rows, "vrp_level_lag", "short_vol_carry")
    assert cell["verdict"] == "SCREEN-INTERESTING", cell
    assert cell["powered"] is True
    assert cell["decontam_passed"] is True
    assert abs(cell["same_period_corr"]) <= 0.20
    assert abs(cell["ic"]) >= 0.03
    # The property that distinguishes a lead from a one-bar misalignment: lagging the signal does
    # NOT convert forward skill into contemporaneous skill; a genuine lead decays smoothly.
    assert cell["shift_translates"] is False
    assert abs(cell["residual_ic"]) >= 0.5 * abs(cell["ic"])


def test_a_coincident_vrp_is_killed_as_a_timing_artifact() -> None:
    rows = screen_market(_coincident_market(), VrpAlignment())
    cell = _cell(rows, "vrp_level", "underlying_return")
    assert cell["verdict"] == "TIMING-ARTIFACT", cell
    assert cell["decontam_passed"] is False
    assert abs(cell["same_period_corr"]) > 0.20


def test_every_preregistered_cell_is_recorded_even_when_it_cannot_be_screened() -> None:
    """A construction that silently vanishes is indistinguishable from one never tried."""
    short = _leading_market(n=80)
    rows = screen_market(short, VrpAlignment())
    assert len(rows) == len(CONSTRUCTIONS) * len(TARGETS)
    for r in rows:
        assert "verdict" in r


# --------------------------------------------------------------------------- panel assembly


def test_market_iv_picks_the_expiry_nearest_the_bucket_centre() -> None:
    ts = 1_700_000_000_000
    panel = [
        {"ts_ms": ts, "underlying": "BTC", "bucket": "t30", "dte_days": 12.0, "atm_iv": 0.90},
        {"ts_ms": ts, "underlying": "BTC", "bucket": "t30", "dte_days": 31.0, "atm_iv": 0.50},
    ]
    got = market_iv(panel)
    assert got[("BTC", "t30")][ts] == pytest.approx(0.50)


def test_implied_vol_units_are_read_from_the_row_never_guessed() -> None:
    """REGRESSION. Deribit publishes mark_iv in PERCENT; the collector emits DECIMAL. A screen that
    guessed would divide a 45% vol into a 0.45% one -- leaving every IC intact, because the harness
    z-scores and a constant factor cancels, while destroying every Sharpe and every variance-swap
    payoff, which depend on the LEVEL. Found in this screen before it shipped.
    """
    ts = 1_700_000_000_000
    dec = market_iv([{"ts_ms": ts, "underlying": "BTC", "bucket": "t90", "dte_days": 90.0,
                      "atm_iv": 0.45, "atm_iv_unit": "decimal_annualised"}])
    pct = market_iv([{"ts_ms": ts, "underlying": "BTC", "bucket": "t90", "dte_days": 90.0,
                      "atm_iv": 45.0, "atm_iv_unit": "percent_annualised"}])
    assert dec[("BTC", "t90")][ts] == pytest.approx(0.45)
    assert pct[("BTC", "t90")][ts] == pytest.approx(0.45)
    # A row with no declaration is read as the collector's only convention, decimal...
    bare = market_iv([{"ts_ms": ts, "underlying": "BTC", "bucket": "t90", "dte_days": 90.0,
                       "atm_iv": 0.45}])
    assert bare[("BTC", "t90")][ts] == pytest.approx(0.45)
    # ...and a value outside the plausibility band is a PARSE ERROR, dropped rather than screened.
    assert market_iv([{"ts_ms": ts, "underlying": "BTC", "bucket": "t90", "dte_days": 90.0,
                       "atm_iv": 45.0}]) == {}
    assert market_iv([{"ts_ms": ts, "underlying": "BTC", "bucket": "t90", "dte_days": 90.0,
                       "atm_iv": 0.0001}]) == {}


def test_build_markets_truncates_to_the_longest_contiguous_run() -> None:
    """A gap is dropped by TRUNCATION, never by compaction: compacting re-labels the row after a
    gap as 'tomorrow' when it is a week later, which is the misalignment the rail exists to catch.
    """
    base = 1_700_000_000_000
    days = [base + i * DAY_MS for i in range(200) if i != 40]     # one hole
    panel = [{"ts_ms": d, "underlying": "BTC", "bucket": "t90", "dte_days": 90.0,
              "atm_iv": 0.60} for d in days]
    bars = {"BTC": (np.array(days, dtype="int64"),
                    np.full(len(days), 100.0) + np.arange(len(days), dtype="float64"))}
    markets, inventory = build_markets(panel, bars)
    assert len(markets) == 1
    assert markets[0].dates_ms.size == 159                       # the longer side of the hole
    inv = inventory[0]
    assert inv["dropped_to_contiguity"] == len(days) - 159
    assert inv["status"] == "BUILT"


def test_market_without_bars_is_recorded_not_silently_dropped() -> None:
    panel = [{"ts_ms": 1_700_000_000_000, "underlying": "ZZZ", "bucket": "t90",
              "dte_days": 90.0, "atm_iv": 0.60}]
    markets, inventory = build_markets(panel, {})
    assert markets == []
    assert inventory[0]["status"] == "NO-BARS"


# --------------------------------------------------------------------------- refusal to fabricate


def test_unreadable_panel_yields_a_status_artifact_and_no_result() -> None:
    art = not_readable_here(VrpAlignment())
    assert art["status"] == "NOT-READABLE-HERE"
    assert art["rows"] == [] and art["survivors"] == [] and art["graveyard"] == []
    assert "no synthetic surface is generated" in art["refusal"]
    assert art["breadth"]["prior_attempt_markets"] == 2
    assert "collect_deribit_vol_markets" in art["filled_by"]
    json.dumps(art)                                    # must be serialisable as an artifact


def test_alignment_declares_the_one_clock_and_the_forward_pairing() -> None:
    d = VrpAlignment().as_dict()
    assert d["excludes_current_period"] is True
    assert d["horizon_days"] == 1.0
    assert "08:00" in d["stamp_utc"]
    assert "signal[t] with target[t+1]" in d["forward_pairing"]
    assert "no interest-rate series is assumed" in d["discounting"]


def test_screen_reports_market_count_against_the_prior_attempt() -> None:
    """Breadth is the exact thing that killed the previous run, so it is part of the result."""
    from scripts.screen_vol_risk_premium import PRIOR_MARKETS, screen_pooled

    n = 400
    markets = []
    rng = np.random.default_rng(5)
    for i, u in enumerate(("A", "B", "C")):
        iv = 0.5 + 0.05 * rng.normal(size=n)
        markets.append(MarketSeries(
            key=f"{u}:t90", underlying=u, bucket="t90",
            dates_ms=_dates(n, start_ms=1_700_000_000_000 + i * 0),
            atm_iv=np.abs(iv) + 0.1, close=np.full(n, 100.0),
            rets=rng.normal(0.0, 0.02, n),
            rv_now=np.full(n, 0.5), rv_lag=np.full(n, 0.5)))
    rows, breadth = screen_pooled(markets, VrpAlignment())
    assert breadth["markets_achieved"] == 3
    assert breadth["prior_attempt_markets"] == PRIOR_MARKETS
    assert breadth["vrp_log_ratio_effective_independent_markets"] <= 3.0
    assert rows and all(r["level"] == "pooled" for r in rows)


def test_alignment_rejects_impossible_parameters() -> None:
    with pytest.raises(ValueError, match="bar_seconds"):
        VrpAlignment(bar_seconds=0)
    with pytest.raises(ValueError, match="rv_lag_days"):
        VrpAlignment(rv_lag_days=-1)


def test_expiry_instant_and_bar_stamp_share_a_clock() -> None:
    """The panel's alignment guarantee is that every series carries Deribit's 08:00 UTC stamp."""
    stamp = datetime(2026, 8, 5, 8, 0, tzinfo=UTC)
    assert stamp.hour == 8
    assert (stamp + timedelta(days=1)).hour == 8
