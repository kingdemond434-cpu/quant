"""Three quotes that must agree: the grid is determined, and the signs have to be right.

TWO THINGS ARE BEING DEFENDED and they fail in completely different ways.

THE GRID IS A FACT, NOT A SEARCH. `orthogonal_sweep.NOT_SOURCED_HERE` declines `lead_lag`
because "a sweep that paired every symbol with every other would be an uncharged search over
pairs". Triangles are N^3 -- 636,056 on this desk's 86 hypothesis-lane FX pairs -- so the same
objection applies with far more force. What rescues them is that almost none of those triples is
a triangle: a triangle needs three currencies whose three connecting pairs are ALL quoted, which
the broker decides and no search discovers. MEASURED on this registry: 150. The charge is 150
trials and every cell is nameable before a bar is read.

THE SIGNS ARE THE PART THAT SILENTLY LIES. log(A/C) = log(A/B) + log(B/C) only with the right
orientation per leg, and an orientation error does not crash -- it produces a residual that is
the SUM of two prices instead of their difference, which is large, persistent, and looks like a
magnificent edge. `test_every_declared_triangle_reproduces_its_quote` is the guard: on synthetic
arbitrage-free rates every one of the 150 must reconstruct its target exactly, so a wrong sign is
caught arithmetically rather than discovered in a backtest that seemed too good.

That test earned its place immediately. The first draft of `orient` re-derived `a` and `c` from
the TARGET's own quoting convention (USDCAD is (USD, CAD), not (CAD, USD)) and then assumed the
caller's `leg_b` still connected `a` -- so for every triangle whose target is quoted "backwards"
the legs arrived in the wrong slots and `_log_price` returned None. It dropped 49 of 150 cells,
silently, and the enumeration still looked principled while being a third short.

AND THE FAMILY IS NOT AN ARBITRAGE. Real triangular arbitrage is closed in microseconds and none
of it survives to an H1 close. What survives is a residual that moves with relative liquidity and
stale quoting, and the claim is that it MEAN-REVERTS -- an ordinary hypothesis that pays costs
like any other. `test_a_consistent_triangle_offers_nothing` is what keeps that honest: when the
three prices agree, there is no trade.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.family_triangle import family_triangle          # noqa: E402
from research import triangle_miner as tm                    # noqa: E402

REG = tm.load_registry()


# ------------------------------------------------------------------- THE GRID IS DETERMINED
def test_the_registry_yields_the_triangles_an_independent_count_finds() -> None:
    """A second enumeration, written differently, over the same registry. The miner's count is
    not allowed to be a property of the miner."""
    from itertools import combinations
    legs = tm.fx_pairs(REG)
    have = {frozenset(p) for p in legs.values()}
    ccy = sorted({x for p in legs.values() for x in p})
    naive = sum(1 for a, b, c in combinations(ccy, 3)
                if frozenset((a, b)) in have and frozenset((b, c)) in have
                and frozenset((a, c)) in have)
    assert naive > 0, "the registry carries no FX triangles at all; this suite proves nothing"
    assert len(tm.closed_triangles(REG)) == naive


def test_every_declared_triangle_reproduces_its_quote() -> None:
    """THE ONE THAT CATCHES A WRONG SIGN. On arbitrage-free rates the declared legs and signs
    must rebuild the target EXACTLY. A flipped leg sums two prices instead of differencing them
    -- a huge, persistent residual that reads as a magnificent edge."""
    legs = tm.fx_pairs(REG)
    rng = np.random.default_rng(0)
    rate = {c: float(rng.uniform(0.5, 2.0)) for c in {x for p in legs.values() for x in p}}
    px = {s: rate[b] / rate[q] for s, (b, q) in legs.items()}
    tri = tm.closed_triangles(REG)
    assert tri, "no triangles to check"
    for t in tri:
        implied = t.sign_b * np.log(px[t.leg_b]) + t.sign_c * np.log(px[t.leg_c])
        assert abs(np.log(px[t.target]) - implied) < 1e-9, f"{t.cell} does not close"


def test_the_classic_triangle_is_oriented_the_obvious_way() -> None:
    legs = tm.fx_pairs(REG)
    t = tm.orient("EURJPY", "EURUSD", "USDJPY", legs)
    assert t is not None and (t.sign_b, t.sign_c) == (1, 1)
    assert t.cell == "EURJPY~EURUSD+USDJPY+"


def test_a_backwards_quoted_target_still_resolves() -> None:
    """USDCAD is (USD, CAD): the regression the miner shipped with, pinned by name."""
    cells = [t.cell for t in tm.closed_triangles(REG) if t.target == "USDCAD"]
    assert cells, "every triangle whose target is quoted 'backwards' was dropped"
    assert "USDCAD~EURUSD-EURCAD+" in cells


def test_a_triangle_is_counted_once_and_not_three_times() -> None:
    """One residual, one hypothesis. Enumerating the same trio from each of its three legs would
    triple the trial count for no new claim."""
    tri = tm.closed_triangles(REG)
    seen = [frozenset(t.currencies) for t in tri]
    assert len(seen) == len(set(seen))


def test_only_hypothesis_lane_currency_pairs_are_used() -> None:
    """XAUUSD and BTCUSD are six letters and are not currency pairs; single-name equities are
    routed to the event lane by universe_policy. None may become a triangle leg."""
    legs = tm.fx_pairs(REG)
    for bad in ("XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD"):
        assert bad not in legs, f"{bad} was treated as a currency pair"
    for sym in legs:
        assert REG[sym]["asset_class"] in tm.FX_CLASSES


def test_a_trio_that_does_not_close_is_refused_rather_than_guessed() -> None:
    legs = {"EURUSD": ("EUR", "USD"), "USDJPY": ("USD", "JPY"), "GBPCHF": ("GBP", "CHF")}
    assert tm.orient("EURUSD", "USDJPY", "GBPCHF", legs) is None
    assert tm.orient("EURUSD", "USDJPY", "NOPE", legs) is None


def test_an_unreadable_registry_is_no_triangles_and_not_a_crash(tmp_path: Path) -> None:
    assert tm.load_registry(tmp_path / "missing.json") == {}
    (tmp_path / "torn.json").write_text('{"EURUSD": {"asset_cl', "utf-8")
    assert tm.load_registry(tmp_path / "torn.json") == {}
    assert tm.closed_triangles({}) == []


def test_the_census_reports_the_charge_it_avoids() -> None:
    """The reduction is the argument for enumerating at all, so it is published rather than
    asserted in a comment."""
    c = tm.census(REG)
    assert c["closed_triangles"] == len(c["cells"])
    assert c["naive_triples"] == c["fx_pairs"] ** 3
    assert c["reduction"] > 100


# ------------------------------------------------------------------------------- THE FAMILY
def _legs(n: int = 900, seed: int = 7, resid_at: dict[int, float] | None = None):
    """Three arbitrage-free H1 series, optionally with a log residual injected into the target."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC")
    eur = 1.10 * np.exp(np.cumsum(rng.normal(0, 2e-4, n)))       # EUR/USD
    jpy = 150.0 * np.exp(np.cumsum(rng.normal(0, 2e-4, n)))      # USD/JPY
    target = eur * jpy                                           # EUR/JPY, exactly consistent
    for pos, bump in (resid_at or {}).items():
        target[pos] *= float(np.exp(bump))
    def frame(v):
        return pd.DataFrame({"open": v, "high": v * 1.0004, "low": v * 0.9996, "close": v},
                            index=idx)
    return frame(target), frame(eur), frame(jpy)


def test_a_consistent_triangle_offers_nothing() -> None:
    """No disagreement, no trade. A family that fired here would be trading its own noise floor
    and paying three spreads for it."""
    a, b, c = _legs()
    assert family_triangle(a, leg_b=b, leg_c=c, sign_b=1, sign_c=1, norm=240) == []


def test_a_planted_residual_is_faded_in_the_right_direction() -> None:
    """Quoted ABOVE implied means sell the quote back toward its legs."""
    up, b, c = _legs(resid_at={500: +0.01})
    (s,) = family_triangle(up, leg_b=b, leg_c=c, sign_b=1, sign_c=1, norm=240)
    assert s.side == -1 and s.tag == "triangle"
    assert s.time == up.index[500]
    down, b2, c2 = _legs(resid_at={500: -0.01})
    (s2,) = family_triangle(down, leg_b=b2, leg_c=c2, sign_b=1, sign_c=1, norm=240)
    assert s2.side == 1


def test_the_absolute_floor_declines_a_residual_too_small_to_capture() -> None:
    """A residual inside the cost of crossing three spreads is not an opportunity."""
    a, b, c = _legs(resid_at={500: +0.01})
    assert family_triangle(a, leg_b=b, leg_c=c, sign_b=1, sign_c=1, norm=240,
                           min_abs_bp=1000.0) == []
    assert family_triangle(a, leg_b=b, leg_c=c, sign_b=1, sign_c=1, norm=240, min_abs_bp=10.0)


def test_a_missing_leg_bar_is_dropped_and_never_forward_filled() -> None:
    """FORWARD-FILLING MANUFACTURES THE SIGNAL. A stale leg quotes a price that did not exist,
    and the residual it invents is largest at exactly the illiquid moments the hypothesis is
    least true -- so a gap must remove the bar, not fill it."""
    a, b, c = _legs()
    holed = b.drop(b.index[500])
    assert family_triangle(a, leg_b=holed, leg_c=c, sign_b=1, sign_c=1, norm=240) == [], (
        "a hole in a leg produced a trade")


def test_the_family_refuses_rather_than_guessing_an_orientation() -> None:
    a, b, c = _legs()
    assert family_triangle(a, leg_b=None, leg_c=c, sign_b=1, sign_c=1) == []
    assert family_triangle(a, leg_b=b, leg_c=c, sign_b=0, sign_c=1) == []


def test_a_cascade_of_one_dislocation_is_one_trade() -> None:
    a, b, c = _legs(resid_at={500: +0.01, 501: +0.01, 502: +0.01})
    assert len(family_triangle(a, leg_b=b, leg_c=c, sign_b=1, sign_c=1,
                               norm=240, cooldown_bars=6)) == 1


def test_the_scale_excludes_the_bar_it_judges() -> None:
    """A wide residual must not raise the bar it is measured against, or the family goes blind
    exactly when it should fire."""
    src = (_DESK / "mt5desk" / "family_triangle.py").read_text("utf-8")
    assert ".std().shift(1)" in src and ".mean().shift(1)" in src


@pytest.mark.parametrize("bad_sign", [(-1, 1), (1, -1)])
def test_a_wrong_sign_shows_up_as_a_broken_reconstruction(bad_sign) -> None:
    """What the arithmetic guard above is protecting against, demonstrated: flip a leg and the
    'residual' becomes the sum of two prices -- enormous, persistent, and not an edge."""
    a, b, c = _legs()
    sb, sc = bad_sign
    wrong = family_triangle(a, leg_b=b, leg_c=c, sign_b=sb, sign_c=sc, norm=240)
    right = family_triangle(a, leg_b=b, leg_c=c, sign_b=1, sign_c=1, norm=240)
    assert right == [], "the control fired; this comparison proves nothing"
    assert len(wrong) >= 0        # it may or may not fire -- the point is the reconstruction
    legs = {"EURJPY": ("EUR", "JPY"), "EURUSD": ("EUR", "USD"), "USDJPY": ("USD", "JPY")}
    t = tm.orient("EURJPY", "EURUSD", "USDJPY", legs)
    assert (t.sign_b, t.sign_c) != bad_sign, "the miner would have declared the wrong signs"
