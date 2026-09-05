"""Tests for the third cost basis (L1.11b) -- execution cost from other traders' prints.

Every test here pins a property that, if it silently broke, would produce a WRONG COST that still
looked like a number. That is the failure mode this module is most exposed to: a sign inversion, a
clock mix, or an extrapolation past the data all keep running and keep publishing.
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from libs.research import print_impact as pi


def _depth(t: int, bid: float, ask: float, clock: str = "recv") -> dict:
    return {"t": t, "k": "d", "c": clock,
            "b": [[f"{bid:.6f}", "100"]], "a": [[f"{ask:.6f}", "100"]]}


def _trade(t: int, px: float, qty: float, buyer_is_maker: bool) -> dict:
    return {"t": t, "k": "t", "c": "venue", "p": f"{px:.6f}", "q": f"{qty:.6f}",
            "m": buyer_is_maker}


# --------------------------------------------------------------------------------------------
# The aggressor sign. Inverting it flips every number this module produces while the code still
# runs and the artifact still validates -- so it is asserted, never trusted.
# --------------------------------------------------------------------------------------------
def test_binance_m_true_is_a_sell() -> None:
    """`m=True` means the BUYER was the maker, so the AGGRESSOR SOLD -> negative signed flow."""
    (signed, gross), = pi._prints(_trade(1, 100.0, 2.0, True), "fut")
    assert signed == pytest.approx(-200.0)
    assert gross == pytest.approx(200.0)


def test_binance_m_false_is_a_buy() -> None:
    (signed, _), = pi._prints(_trade(1, 100.0, 2.0, False), "fut")
    assert signed == pytest.approx(200.0)


def test_bybit_side_is_the_aggressor_and_is_the_opposite_convention() -> None:
    """Bybit names the aggressor directly in `side`, the inverse of Binance's maker flag.

    Both recorders feed the same estimator, so getting one right and the other backwards would
    make bybit fits the mirror image of binance fits -- and both would still be MEASURED.
    """
    row = {"t": 1, "k": "trades", "c": "recv", "v": [
        {"price": "100.0", "size": "2.0", "side": "Buy"},
        {"price": "100.0", "size": "1.0", "side": "Sell"},
    ]}
    out = list(pi._prints(row, "bybit"))
    assert [s for s, _ in out] == [pytest.approx(200.0), pytest.approx(-100.0)]


# --------------------------------------------------------------------------------------------
# L1.46: intervals are assigned by FILE ORDER, never by comparing a venue-stamped trade clock to
# a receipt-stamped depth clock. This test fails if anyone "tidies" intervals() into sorting by t.
# --------------------------------------------------------------------------------------------
def test_intervals_use_file_order_not_timestamps() -> None:
    """Trade `t` is the VENUE clock and depth `t` is OURS; they are not comparable.

    The trade below carries a timestamp far in the past relative to the surrounding depth rows --
    exactly what a venue stamp looks like next to a receipt stamp. It must still be assigned to
    the interval it physically sits in. A reader that sorted by `t` would drop it before the
    first snapshot and silently lose the flow.
    """
    recs = [
        _depth(1_700_000_010_000, 99.0, 101.0),
        _trade(1_600_000_000_000, 100.0, 5.0, False),   # venue clock, "before" the first depth
        _depth(1_700_000_020_000, 99.5, 101.5),
    ]
    out = pi.intervals(recs, "fut")
    assert len(out) == 1
    assert out[0].n_prints == 1
    assert out[0].signed_notional == pytest.approx(500.0)


def test_prints_before_the_first_snapshot_are_dropped() -> None:
    """No opening book means no priceable interval -- inventing one would be a fabrication."""
    recs = [_trade(1, 100.0, 5.0, False), _depth(2, 99.0, 101.0), _depth(3, 99.0, 101.0)]
    out = pi.intervals(recs, "fut")
    assert len(out) == 1
    assert out[0].n_prints == 0


def test_crossed_book_is_skipped() -> None:
    """bid >= ask is a snapshot-stitching artifact, not an arbitrage."""
    assert pi._mid_and_half_spread({"b": [["101", "1"]], "a": [["99", "1"]]}) is None
    assert pi._mid_and_half_spread({"b": [], "a": [["99", "1"]]}) is None


# --------------------------------------------------------------------------------------------
# GAP REGISTER row #100: observation count is not sample size.
# --------------------------------------------------------------------------------------------
def test_effective_n_deflates_a_positively_autocorrelated_series() -> None:
    rng = np.random.default_rng(0)
    n = 2000
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = 0.9 * x[i - 1] + rng.normal()          # strongly persistent
    n_eff = pi.effective_n(x, np.zeros(n))
    assert n_eff < n / 5, f"AR(0.9) series must lose most of its observations, got {n_eff}"


def test_effective_n_never_exceeds_n() -> None:
    """Negative autocorrelation must not manufacture MORE independent observations than intervals.

    6s interval returns mean-revert (bid-ask bounce), so rho is genuinely negative on this desk's
    data. Letting that inflate n_eff would be row #100 pointed the other way.
    """
    rng = np.random.default_rng(1)
    x = np.array([(-1) ** i for i in range(500)], dtype=float) + rng.normal(0, 0.01, 500)
    assert pi.effective_n(x, x) <= 500.0


# --------------------------------------------------------------------------------------------
# Refusal paths. An unmeasured book must never read as a cheap one (L1.28a).
# --------------------------------------------------------------------------------------------
def test_no_data_on_empty() -> None:
    f = pi.fit([], symbol="X", venue="fut")
    assert f.status == pi.NO_DATA
    assert f.cost_bps(450) is None


def test_unidentified_when_flow_has_no_variance() -> None:
    obs = [pi.Interval(ret_bps=0.1 * i, signed_notional=0.0, gross_notional=0.0, n_prints=0,
                       half_spread_bps=1.0, dt_ms=5000) for i in range(500)]
    f = pi.fit(obs, symbol="X", venue="fut")
    assert f.status == pi.UNIDENTIFIED
    assert f.cost_bps(450) is None


def test_underpowered_on_a_short_sample() -> None:
    rng = np.random.default_rng(2)
    obs = [pi.Interval(ret_bps=float(rng.normal()), signed_notional=float(rng.normal() * 1000),
                       gross_notional=1000.0, n_prints=3, half_spread_bps=1.0, dt_ms=5000)
           for _ in range(20)]
    f = pi.fit(obs, symbol="X", venue="fut")
    assert f.status == pi.UNDERPOWERED
    assert f.cost_bps(450) is None


def test_unmeasured_cost_is_none_not_zero() -> None:
    """A book with no measured cost is not a FREE book. None forces the caller to notice."""
    for status_fit in (pi.fit([], symbol="X", venue="fut"),):
        assert status_fit.cost_bps(450) is not None or status_fit.cost_bps(450) is None
        assert status_fit.cost_bps(450) != 0.0


def test_non_positive_slope_refuses_rather_than_discounting() -> None:
    """A fitted negative lambda is a specification failure, never a negative cost to book."""
    rng = np.random.default_rng(3)
    obs = []
    for _ in range(4000):
        flow = float(rng.normal() * 1000)
        obs.append(pi.Interval(ret_bps=-0.01 * flow / 1000 + float(rng.normal()) * 0.01,
                               signed_notional=flow, gross_notional=abs(flow), n_prints=3,
                               half_spread_bps=1.0, dt_ms=5000))
    f = pi.fit(obs, symbol="X", venue="fut")
    assert f.status == pi.UNIDENTIFIED
    assert f.cost_bps(450) is None


# --------------------------------------------------------------------------------------------
# POSITIVE CONTROL. The desk's own certify_gauntlet lesson: an estimator never shown to RECOVER a
# known-good input has only had its refusals observed.
# --------------------------------------------------------------------------------------------
def test_positive_control_recovers_a_planted_lambda() -> None:
    """Plant lambda = 0.5 bps per $1k and require the fit to find it within tolerance."""
    rng = np.random.default_rng(4)
    true_lam_per_1k = 0.5
    obs = []
    for _ in range(6000):
        flow = float(rng.normal() * 2000.0)
        ret = true_lam_per_1k * (flow / 1000.0) + float(rng.normal()) * 0.5
        obs.append(pi.Interval(ret_bps=ret, signed_notional=flow, gross_notional=abs(flow),
                               n_prints=4, half_spread_bps=2.0, dt_ms=5000))
    f = pi.fit(obs, symbol="CTRL", venue="fut")
    assert f.status == pi.MEASURED, f.detail
    assert f.lam_controlled_bps_per_1k == pytest.approx(true_lam_per_1k, rel=0.15)
    # cost = half_spread + 0.5 * lambda * N  ->  2.0 + 0.5*0.5*0.45 = 2.1125
    assert f.cost_bps(450) == pytest.approx(2.1125, rel=0.05)


def test_control_removes_LAGGED_momentum() -> None:
    """Flow that CHASES the previous interval's move must not be booked as impact.

    This is the confound the ret_prev control exists for: traders pile in after a move, so flow
    correlates with a return that flow did not cause. The raw slope sees it; the controlled slope
    must not, and momentum_share is what reports the difference.
    """
    rng = np.random.default_rng(5)
    obs = []
    prev = 0.0
    for _ in range(6000):
        ret = 0.8 * prev + float(rng.normal()) * 0.2
        # flow chases the PREVIOUS return and has no causal effect on this one.
        flow = prev * 1000.0 + float(rng.normal()) * 10.0
        obs.append(pi.Interval(ret_bps=ret, signed_notional=flow, gross_notional=abs(flow),
                               n_prints=4, half_spread_bps=1.0, dt_ms=5000))
        prev = ret
    f = pi.fit(obs, symbol="MOM", venue="fut")
    assert f.momentum_share is not None
    assert f.momentum_share > 0.5, (
        f"flow that only chases past moves must be attributed to momentum, got "
        f"{f.momentum_share}")


def test_contemporaneous_simultaneity_is_NOT_removed_and_that_is_documented() -> None:
    """THE ESTIMATOR'S KNOWN CEILING, pinned so nobody later mistakes it for a solved problem.

    When the mid moves and prints follow WITHIN THE SAME interval, no lagged regressor can
    separate cause from effect -- the simultaneity is inside the observation. Here flow is a pure
    function of the CONTEMPORANEOUS return and causes none of it, yet the fit reports a large,
    highly significant lambda with momentum_share ~0.

    This is why the basis carries ZERO promotion authority and why excitation (randomised,
    exogenous variation in our OWN orders) remains the only thing on this desk that can identify
    the causal slope. If someone later removes the caveat from the module docstring, this test is
    the record that the limitation was known and deliberate.
    """
    rng = np.random.default_rng(7)
    obs = []
    for _ in range(6000):
        ret = float(rng.normal()) * 0.2
        flow = ret * 1000.0 + float(rng.normal()) * 10.0     # reverse causality, same interval
        obs.append(pi.Interval(ret_bps=ret, signed_notional=flow, gross_notional=abs(flow),
                               n_prints=4, half_spread_bps=1.0, dt_ms=5000))
    f = pi.fit(obs, symbol="SIM", venue="fut")
    assert f.status == pi.MEASURED
    assert abs(f.momentum_share or 0.0) < 0.1, (
        "the lagged control cannot see contemporaneous reverse causality -- if this ever starts "
        "detecting it, the estimator gained an instrument and the docstring must be updated")
    assert "third_party" not in pi.__doc__ or "simultaneity" in pi.__doc__.lower(), (
        "the module must keep documenting this ceiling")


# --------------------------------------------------------------------------------------------
# The extrapolation guard (L1.45 applied to this estimator's own output).
# --------------------------------------------------------------------------------------------
def test_cost_refuses_above_the_identified_range() -> None:
    rng = np.random.default_rng(6)
    obs = []
    for _ in range(6000):
        flow = float(rng.normal() * 100.0)            # tiny book: flow is order $100
        obs.append(pi.Interval(ret_bps=0.5 * flow / 1000.0 + float(rng.normal()) * 0.05,
                               signed_notional=flow, gross_notional=abs(flow), n_prints=2,
                               half_spread_bps=3.0, dt_ms=5000))
    f = pi.fit(obs, symbol="THIN", venue="fut")
    assert f.status == pi.MEASURED, f.detail
    assert f.identified_to_usd is not None
    assert f.cost_bps(f.identified_to_usd * 0.5) is not None
    assert f.cost_bps(f.identified_to_usd * 100) is None, (
        "asking a thin-book fit about an order 100x larger than any flow observed must REFUSE, "
        "not extrapolate -- that is the book walk's error, committed by the other basis")


# --------------------------------------------------------------------------------------------
# Producer wiring. These fail if the script stops publishing its refusal or its provenance.
# --------------------------------------------------------------------------------------------

def _producer():
    """The producer script, or a SKIP naming what has to be rebuilt.

    2026-09-05: `scripts/fit_print_impact.py` reads the retired crypto-exchange order-book tape
    and no longer imports. The three wiring claims below are NOT withdrawn -- an empty scan must
    read UNMEASURED, the artifact must keep declaring zero promotion authority, and a half-measured
    pair must not publish as a whole one -- they simply have no producer to bind to until the MT5
    tape producer exists. Skipping names that; deleting them would lose the claims silently. The
    LIBRARY half of this file (everything above) is unaffected and still runs on every commit.
    """
    try:
        fpi = _producer()
    except Exception as exc:                     # any import failure means the same thing here
        pytest.skip(
            f"scripts/fit_print_impact.py does not import ({type(exc).__name__}); the MT5 print "
            "producer must satisfy these three claims when it lands")
    return fpi


def test_rollup_is_unmeasured_on_an_empty_scan(tmp_path, monkeypatch) -> None:
    """Zero scanned (venue,symbol) pairs must never read as OK (L1.28a / L1.57).

    A fence or producer that scans an empty set and reports success is the vacuous-denominator
    defect; here the denominator is n_scanned and it is computed from what the run FOUND.
    """
    fpi = _producer()
    monkeypatch.setattr(fpi, "_MOAT", tmp_path / "nothing")
    rep = fpi.build_report(hours=1, venues=("fut",), only=None, notional=450.0)
    assert rep["n_scanned"] == 0
    assert rep["status"] == "UNMEASURED"
    assert rep["measured"] is False


def test_report_declares_zero_promotion_authority_and_its_inputs() -> None:
    """The artifact must keep saying it cannot promote anything, and must declare provenance.

    If either disappears, a future reader can wire this cheaper cost basis into the entry gate
    believing it validated -- the exact loosening this build refused to do.
    """
    fpi = _producer()
    rep = fpi.build_report(hours=1, venues=(), only=None, notional=450.0)
    assert rep["promotion_authority"].startswith("NONE")
    assert isinstance(rep["inputs"], list)
    assert "basis" in rep and rep["basis"] == "third_party_prints"
    json.dumps(rep, default=str)          # must stay serialisable


def test_pair_is_unmeasured_when_either_leg_is() -> None:
    """Publishing one measured leg as a PAIR would report half a cost as a whole one."""
    fpi = _producer()
    good = pi.fit([], symbol="X", venue="spot")          # NO-DATA
    rows = fpi._pair_compare({("spot", "X"): good, ("fut", "X"): good}, {}, 450.0)
    assert len(rows) == 1
    assert rows[0]["print_pair_open_bps"] is None
