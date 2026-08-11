"""Gate items 11/12/13: capacity as a continuous economic input, never an admission floor."""
from __future__ import annotations

from libs.research.capacity_curve import (
    capacity_curve,
    portfolio_adjusted_capacity,
    rank_by_marginal_value,
)


def _curve(name="c", gross=40.0, adv=2_000_000.0, spread=4.0, vol=0.03, fee=2.0):
    return capacity_curve(name=name, gross_edge_bps=gross, adv_usd=adv,
                          spread_bps=spread, volatility=vol, fee_bps=fee)


# ------------------------------------------------------------------ item 12: the curve
def test_item12_curve_is_measured_and_costs_grow_with_size() -> None:
    c = _curve()
    assert c.status == "MEASURED" and len(c.points) > 5
    first, last = c.points[0], c.points[-1]
    assert last.impact_bps > first.impact_bps, "impact must grow with participation"
    assert last.net_edge_bps < first.net_edge_bps, "net edge must decay with size"
    assert c.minimum_economic_usd and c.maximum_economic_usd and c.optimum_usd


def test_item12_missing_input_is_unmeasured_never_a_guess() -> None:
    c = capacity_curve(name="x", gross_edge_bps=40.0, adv_usd=None,
                       spread_bps=4.0, volatility=0.03)
    assert c.status == "UNMEASURED" and "adv_usd" in c.why


def test_item12_costs_exceeding_gross_edge_is_a_cost_verdict_not_a_capacity_one() -> None:
    c = _curve(gross=1.0, spread=20.0, fee=10.0)
    assert c.status == "NO-CAPACITY" and "COST verdict" in c.why


def test_item12_optimum_maximises_dollars_not_rate() -> None:
    """Growth RATE per dollar peaks at the smallest size; optimising it would recommend trading
    $100 forever. The optimum must be where total net dollars peak."""
    c = _curve()
    assert c.optimum_usd is not None and c.optimum_usd > c.points[0].capital_usd


# ------------------------------------------------------------------ item 11: no institutional floor
def test_item11_micro_capacity_edge_outranks_a_big_thin_one_at_desk_capital() -> None:
    """THE POINT OF ITEM 11. At this desk's ~$13k equity a $3k-capacity strong edge is worth more
    than a $5M-capacity weak one, and no institutional habit may reverse that."""
    micro = {"name": "micro", "curve": _curve("micro", gross=120.0, adv=60_000.0, spread=6.0)}
    huge = {"name": "huge", "curve": _curve("huge", gross=9.0, adv=500_000_000.0, spread=4.0)}
    ranked = rank_by_marginal_value([huge, micro], current_capital_usd=13_000.0)
    assert ranked[0]["name"] == "micro", [r["name"] for r in ranked]
    assert ranked[0]["status"] == "RANKED"


def test_item11_unmeasured_capacity_ranks_last_but_is_never_rejected() -> None:
    unknown = {"name": "u", "curve": capacity_curve(
        name="u", gross_edge_bps=None, adv_usd=1e6, spread_bps=4.0, volatility=0.03)}
    good = {"name": "g", "curve": _curve("g")}
    ranked = rank_by_marginal_value([unknown, good], current_capital_usd=13_000.0)
    assert ranked[0]["name"] == "g"
    assert ranked[-1]["name"] == "u" and "not zero" in ranked[-1]["why"]


def test_item11_capacity_is_a_ceiling_not_an_admission_floor() -> None:
    """A candidate whose capacity is far BELOW desk capital is still ranked -- it is simply
    deployed at its ceiling rather than turned away."""
    tiny = {"name": "tiny", "curve": _curve("tiny", gross=200.0, adv=20_000.0)}
    ranked = rank_by_marginal_value([tiny], current_capital_usd=13_000.0)
    assert ranked[0]["status"] == "RANKED"
    assert ranked[0]["deployable_usd"] <= 13_000.0
    assert ranked[0]["capacity_ceiling_usd"] is not None


# ------------------------------------------------------------------ item 13: no double-counting
def test_item13_overlapping_strategies_do_not_double_count_liquidity() -> None:
    out = portfolio_adjusted_capacity([
        {"name": "carry_a", "venue": "binance", "asset": "BTCUSDT",
         "capacity_usd": 30_000.0, "window": ["08:00", "16:00"]},
        {"name": "carry_b", "venue": "binance", "asset": "BTCUSDT",
         "capacity_usd": 20_000.0, "window": ["16:00", "00:00"]},
    ])
    assert out["standalone_sum_usd"] == 50_000.0
    assert out["portfolio_adjusted_usd"] == 30_000.0     # one book, its depth
    assert out["cannibalisation_usd"] == 20_000.0
    assert out["pairs"] and out["pairs"][0]["shared_liquidity"]


def test_item13_different_venues_are_additive() -> None:
    out = portfolio_adjusted_capacity([
        {"name": "a", "venue": "binance", "asset": "BTCUSDT",
         "capacity_usd": 30_000.0, "window": ["08:00"]},
        {"name": "b", "venue": "bybit", "asset": "BTCUSDT",
         "capacity_usd": 20_000.0, "window": ["08:00"]},
    ])
    assert out["portfolio_adjusted_usd"] == 50_000.0 and out["cannibalisation_usd"] == 0.0


def test_item13_same_venue_non_overlapping_windows_are_additive() -> None:
    """Sharing a book at different times is not sharing depth at the same time."""
    out = portfolio_adjusted_capacity([
        {"name": "a", "venue": "binance", "asset": "BTCUSDT",
         "capacity_usd": 30_000.0, "window": ["08:00"]},
        {"name": "b", "venue": "binance", "asset": "BTCUSDT",
         "capacity_usd": 20_000.0, "window": ["20:00"]},
    ])
    assert out["portfolio_adjusted_usd"] == 50_000.0 and not out["pairs"]
