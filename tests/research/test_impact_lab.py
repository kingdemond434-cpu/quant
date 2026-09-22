"""The impact lab on planted fills: a planted Kyle-lambda is recovered with a permutation null
that clears it, noise is not; the sign conventions hold; every thin cell reads UNMEASURED."""
from __future__ import annotations

import numpy as np

from libs.research import impact_lab as il


def _order(i: int, *, side: int = 1, lots: float = 1.0, requested: float | None = 100.0,
           fill: float | None = 100.0, rejected: bool = False, order_type: str = "market",
           session: str = "london", short: float | None = None, long_: float | None = None,
           latency: float | None = None, filled_frac: float | None = 1.0,
           done: bool | None = None) -> il.OrderRecord:
    return il.OrderRecord(instrument="EURUSD", t_ms=float(i) * 60_000.0, side=side, lots=lots,
                          order_type=order_type, session=session, requested=requested,
                          fill_price=fill, filled_frac=filled_frac, rejected=rejected,
                          reject_reason="invalid_stops" if rejected else "",
                          latency_ms=latency, mid_before=100.0, mid_short=short,
                          mid_long=long_, done=done)


def test_kyle_lambda_recovers_a_planted_impact_and_clears_the_permutation_null() -> None:
    rng = np.random.default_rng(3)
    q = rng.normal(0.0, 1.0, size=120)
    y = 2.0 * q + rng.normal(0.0, 0.5, size=120)
    got = il.kyle_lambda(q, y, permutations=300)
    assert got["status"] == "MEASURED" and got["n"] == 120
    assert abs(got["lambda_bps_per_unit"] - 2.0) < 0.2
    assert got["p_permutation"] < 0.01 and got["r2"] > 0.8


def test_kyle_lambda_on_noise_does_not_clear_the_null_and_is_unmeasured_when_thin() -> None:
    rng = np.random.default_rng(11)
    q = rng.normal(0.0, 1.0, size=200)
    y = rng.normal(0.0, 1.0, size=200)
    got = il.kyle_lambda(q, y, permutations=300)
    assert got["status"] == "MEASURED"
    assert abs(got["lambda_bps_per_unit"]) < 0.25
    assert got["p_permutation"] > 0.05
    assert il.kyle_lambda(q[:5], y[:5])["status"] == "UNMEASURED"
    assert il.kyle_lambda(np.ones(50), y[:50])["status"] == "UNMEASURED"   # no size variation


def test_impact_decomposition_splits_permanent_from_transient() -> None:
    # Buys and sells of varying size; the mid moves 5 bps per unit at 5 s and 2 bps per unit
    # at 5 min, in the flow's direction: permanent 2, transient 3.
    rng = np.random.default_rng(5)
    orders = []
    for i in range(60):
        side = 1 if i % 2 == 0 else -1
        lots = float(rng.choice([0.5, 1.0, 1.5, 2.0]))
        flow = side * lots                                     # median lot is 1.0 -> unit flow
        orders.append(_order(i, side=side, lots=lots,
                             short=100.0 * (1 + side * 5.0 * flow / 1e4),
                             long_=100.0 * (1 + side * 2.0 * flow / 1e4)))
    got = il.impact_decomposition(orders, permutations=200)
    assert got["status"] == "MEASURED"
    assert abs(got["permanent_bps_per_unit"] - 2.0) < 1e-6
    assert abs(got["transient_bps_per_unit"] - 3.0) < 1e-6
    assert got["long_horizon"]["p_permutation"] < 0.01
    assert il.impact_decomposition(orders[:4])["status"] == "UNMEASURED"


def test_fill_probability_counts_rejections_as_unfilled_with_a_wilson_interval() -> None:
    orders = [_order(i) for i in range(15)] + [_order(100 + i, rejected=True, fill=None)
                                               for i in range(5)]
    got = il.fill_probability(orders)["all"]
    assert got["n"] == 20 and got["filled"] == 15 and got["p_fill"] == 0.75
    assert got["ci95"][0] < 0.75 < got["ci95"][1]
    rej = il.rejection_behaviour(orders)
    assert rej["rejected"] == 5 and rej["by_reason"] == {"invalid_stops": 5}
    assert rej["by_session"]["london"] == {"n": 20, "rejected": 5}
    # A DONE retcode with no recorded price is a fill; a price with no DONE is one too.
    assert _order(1, fill=None, done=True).filled
    assert not _order(1, fill=None, done=False).filled
    assert il.fill_probability([])["all"]["status"] == "UNMEASURED"


def test_slippage_sign_partial_fills_and_stop_behaviour() -> None:
    buy_high = _order(1, side=1, requested=100.0, fill=100.01)
    sell_low = _order(2, side=-1, requested=100.0, fill=99.99)
    assert buy_high.slippage_bps() == 1.0 and sell_low.slippage_bps() == 1.0
    assert _order(3, requested=None).slippage_bps() is None
    orders = [_order(i, filled_frac=0.5 if i % 4 == 0 else 1.0) for i in range(12)]
    got = il.partial_fills(orders)
    assert got["n"] == 12 and got["partial"] == 3 and got["rate"] == 0.25
    stops = [_order(i, order_type="pending_stop", fill=None, done=False) for i in range(10)]
    stops += [_order(20, order_type="pending_stop", fill=100.02)]
    st = il.stop_behaviour(stops)
    assert st["n"] == 11 and st["filled"] == 1 and st["slippage_bps"]["n"] == 1
    assert il.slippage(orders)["all"]["n"] == 12


def test_toxicity_is_a_state_with_an_interval() -> None:
    toxic = [_order(i, short=99.99) for i in range(30)]           # every fill runs against
    benign = [_order(i, short=100.01) for i in range(30)]
    assert il.toxicity(toxic)["state"] == "TOXIC"
    assert il.toxicity(benign)["state"] == "BENIGN"
    mixed = toxic[:15] + benign[:15]
    assert il.toxicity(mixed)["state"] == "MIXED"
    thin = il.toxicity(toxic[:5])
    assert thin["state"] == "UNMEASURED" and thin["n"] == 5


def test_queue_latency_effect_and_session_cost_curve() -> None:
    orders = [_order(i, requested=100.0, fill=100.0 + i * 0.0001, latency=float(10 * i))
              for i in range(20)]
    got = il.queue_latency_effect(orders, permutations=200)
    assert got["status"] == "MEASURED" and got["spearman_rho"] > 0.99
    assert got["p_permutation"] < 0.01
    spreads = il.spread_by_session(np.arange(24), np.full(24, 2.0))
    assert set(spreads) == set(il.SESSIONS)
    curve = il.session_cost_curve(orders, {"london": {"p50": 2.0}})
    assert curve["london"]["half_spread_bps"] == 1.0
    assert curve["london"]["cost_bps"] == round(1.0 + np.mean(
        [o.slippage_bps() or 0.0 for o in orders]), 4)
    assert curve["asia"]["status"] == "UNMEASURED"           # no spread, no fills
    assert il.session_of_hour(3) == "asia" and il.session_of_hour(15) == "overlap"


def test_execution_cells_read_measured_only_with_enough_fills() -> None:
    orders = [_order(i, short=99.99 if i % 3 else 100.01) for i in range(12)]
    orders += [_order(50, session="asia")]
    cells = il.execution_cells(orders, {"EURUSD": {"london": {"p50": 1.5}}})
    by = {(c["instrument"], c["session"]): c for c in cells}
    assert by[("EURUSD", "london")]["status"] == "MEASURED"
    assert by[("EURUSD", "london")]["spread_p50_bps"] == 1.5
    assert by[("EURUSD", "asia")]["status"] == "UNMEASURED"
