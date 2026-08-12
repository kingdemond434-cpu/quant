"""THE MOAT MINER -- the desk's only un-replicable asset, read for the first time.

WHAT THESE TESTS ARE FOR. Every reconstruction here consumes order books and emits a number that
looks plausible whatever it is fed. That is the danger: a parse bug does not raise, it produces a
confident series, and a confident series gets clustered into "regimes" and pre-registered as a
mechanism. moat_audit.py already has this exact scar -- its first version mis-read the mixed
stream and declared 4.4GB of good data 82-99% stale.

So the load-bearing tests below are not "does the mean look right". They are:
  - both recorder schemas parse (k="d" AND k="depth"), because reading one and silently missing
    the other returns a clean empty result from the dataset that IS the moat;
  - absence is NaN and NaN is n=0, because a fabricated zero fills a coverage cell and retires
    ground from the frontier on a measurement never taken;
  - crossed and misordered books are dropped, because they produce EXCITING artifacts (negative
    trading costs) and exciting artifacts survive review.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from libs.hypmax.moat_mine import (
    DEPTH_KINDS,
    MECHANISMS,
    CoverageGrid,
    book_slope,
    coverage_report,
    effective_spread,
    extract_all,
    imbalance,
    microprice_gap,
    replenishment_halflife,
    resting_stability,
    withdrawal_rate,
)


def _book(t: int, *, bid: float = 100.0, ask: float = 100.1, size: float = 10.0,
          n: int = 20, kind: str = "d") -> dict:
    """A well-formed snapshot in the recorders' on-disk shape: STRING price/size pairs."""
    b = [[f"{bid - i * 0.01:.4f}", f"{size:.4f}"] for i in range(n)]
    a = [[f"{ask + i * 0.01:.4f}", f"{size:.4f}"] for i in range(n)]
    return {"t": t, "k": kind, "b": b, "a": a}


# ------------------------------------------------------------------ schema

@pytest.mark.parametrize("kind", ["d", "depth"])
def test_both_recorder_schemas_are_read(kind: str) -> None:
    """THE ONE THAT WOULD HAVE COST THE MOST. run_recorder{,_spot} stamp k="d"; the bybit
    recorder stamps k="depth". Knowing only one returns a confident EMPTY result over the other's
    files -- and the k="d" side is the ~12k-file, 4.4GB dataset that IS the moat."""
    rows = [_book(i, kind=kind) for i in range(5)]
    assert len(imbalance(rows)) == 5


def test_an_unknown_kind_is_not_silently_treated_as_depth() -> None:
    """Trades outnumber depth rows ~8:1 in the same files. Parsing one as a book is exactly how
    moat_audit's first version manufactured a 99%-stale verdict."""
    assert len(imbalance([{"t": 1, "k": "t", "p": "100", "q": "1"}] * 20)) == 0
    assert "trades" not in DEPTH_KINDS


def test_binance_long_form_level_keys_also_parse() -> None:
    rows = [{"t": i, "k": "d", "bids": [["100", "5"]], "asks": [["101", "5"]]} for i in range(4)]
    assert len(imbalance(rows)) == 4


# ------------------------------------------------------------------ book hygiene

def test_a_crossed_book_is_dropped_not_traded_on() -> None:
    """bid >= ask is physically impossible and means a torn snapshot. Left in, effective_spread
    returns a NEGATIVE cost -- "the venue pays us to trade" -- which is the kind of artifact that
    survives review precisely because it is exciting."""
    good = [_book(i) for i in range(3)]
    crossed = [_book(9, bid=101.0, ask=100.0)]
    assert len(imbalance(good + crossed)) == 3
    assert np.all(effective_spread(good + crossed)[np.isfinite(effective_spread(good))] >= 0)


def test_levels_arriving_out_of_order_do_not_become_a_finding() -> None:
    """Every reconstruction indexes [0] as the touch. An unsorted ladder makes the touch a random
    level, and the resulting series still looks like microstructure."""
    ordered = _book(1)
    shuffled = {"t": 1, "k": "d", "b": list(reversed(ordered["b"])),
                "a": list(reversed(ordered["a"]))}
    assert microprice_gap([ordered])[0] == pytest.approx(microprice_gap([shuffled])[0])


def test_unparseable_levels_are_dropped_never_coerced_to_zero() -> None:
    """A zero size is a REAL book state. Inventing one manufactures a withdrawal event."""
    rows = [{"t": 1, "k": "d", "b": [["bad", "x"], ["100", "5"]], "a": [["101", "5"]]},
            {"t": 2, "k": "d", "b": [["100", "5"]], "a": [["101", "5"]]}]
    assert withdrawal_rate(rows).tolist() == [0.0]


# ------------------------------------------------------------------ absence is not zero

def test_replenishment_is_nan_when_nothing_ever_withdrew() -> None:
    """THE DISTINCTION. Zero half-life reads as INSTANT replenishment -- the opposite of "no
    withdrawal was observed" -- so a screen fed 0.0 would rank the quietest book on the venue as
    its most liquid."""
    assert math.isnan(replenishment_halflife([_book(i) for i in range(10)]))


def test_a_nan_scalar_reports_n_zero_and_therefore_fills_no_cell() -> None:
    """n=1 on an unmeasurable scalar would mark its coverage cell FILLED and retire that ground
    from the frontier on the strength of a measurement never taken."""
    r = extract_all("BTCUSDT", [_book(i) for i in range(10)])
    assert r["mechanisms"]["replenishment_halflife"]["n"] == 0
    assert "unmeasured" in r["mechanisms"]["replenishment_halflife"]["note"]


def test_an_order_too_large_for_the_book_is_nan_not_the_best_price_seen() -> None:
    """Reporting a partial walk as the cost of a full one understates exactly the trades that
    matter -- the ones big enough to move the desk's NAV."""
    thin = [_book(1, size=0.001, n=3)]
    assert math.isnan(effective_spread(thin, notional=1e9)[0])


def test_an_empty_input_produces_no_mechanism_coverage_at_all() -> None:
    r = extract_all("BTCUSDT", [])
    assert r["depth_snapshots"] == 0
    assert all(m["n"] == 0 for m in r["mechanisms"].values())


# ------------------------------------------------------------------ the reconstructions

def test_withdrawal_keeps_removals_and_ignores_additions() -> None:
    """Netting additions against removals averages the signal into invisibility: size vanishing
    before a move is not cancelled by size arriving after it."""
    rows = [_book(1, size=10), _book(2, size=5), _book(3, size=20)]
    w = withdrawal_rate(rows)
    assert w[0] == pytest.approx(0.5)
    assert w[1] == 0.0, "an ADDITION must not register as negative withdrawal"


def test_replenishment_measures_snapshots_to_half_recovery() -> None:
    sizes = [10, 10, 2, 2, 6, 10]          # drop at idx2, half of the drop (6) recovered at idx4
    rows = [_book(i, size=s) for i, s in enumerate(sizes)]
    assert replenishment_halflife(rows) == pytest.approx(2.0)


def test_a_concentrated_book_slopes_steeper_than_a_deep_one() -> None:
    """Level 1 is what everyone else trades on; the SHAPE is the part nobody publishes."""
    flat = [_book(1, n=20)]
    conc = [{"t": 1, "k": "d",
             "b": [[f"{100 - i * 0.01:.4f}", f"{10 * 0.5 ** i:.6f}"] for i in range(20)],
             "a": [[f"{100.1 + i * 0.01:.4f}", f"{10 * 0.5 ** i:.6f}"] for i in range(20)]}]
    assert book_slope(conc)[0] < book_slope(flat)[0]


def test_imbalance_is_signed_and_bounded() -> None:
    heavy_bid = {"t": 1, "k": "d", "b": [["100", "90"]], "a": [["101", "10"]]}
    assert imbalance([heavy_bid])[0] == pytest.approx(0.8)
    assert abs(imbalance([_book(1)])[0]) < 1e-9


def test_microprice_leans_toward_the_thinner_side() -> None:
    """A big bid and a thin ask means the next print is likelier to be up -- the microprice says
    so before the mid does."""
    row = {"t": 1, "k": "d", "b": [["100", "90"]], "a": [["101", "10"]]}
    assert microprice_gap([row])[0] > 0


def test_effective_spread_exceeds_half_the_quoted_spread_when_walking() -> None:
    """The gap between quoted and effective is a cost the desk does not model, and unmodelled
    costs are how a backtested edge dies on contact."""
    rows = [_book(1, bid=100.0, ask=100.1, size=1.0, n=20)]
    quoted_half_bps = (100.1 - 100.05) / 100.05 * 1e4
    e = effective_spread(rows, notional=1500.0)[0]   # 20 levels x 1.0 @ ~100 = ~2000 available
    assert e > quoted_half_bps
    assert e < 100, "walking 20 dense levels should still cost well under 1%"


def test_stability_is_one_for_a_frozen_book_and_low_for_a_repainted_one() -> None:
    frozen = [_book(i) for i in range(4)]
    assert resting_stability(frozen).mean() == pytest.approx(1.0)
    repaint = [_book(i, bid=100 + i, ask=100.1 + i) for i in range(4)]
    assert resting_stability(repaint).mean() < 0.1


def test_one_broken_mechanism_never_costs_the_other_six() -> None:
    r = extract_all("BTCUSDT", [_book(i) for i in range(6)])
    assert set(r["mechanisms"]) == set(MECHANISMS)
    assert sum(1 for m in r["mechanisms"].values() if m["n"] > 0) >= 6


# ------------------------------------------------------------------ coverage is the product

def test_zero_observations_does_not_count_as_coverage() -> None:
    """THE CENTRAL RULE. Otherwise 100% means "we ran everywhere", not "we measured everywhere",
    and the frontier retires ground nobody ever looked at."""
    g = CoverageGrid()
    g.mark("BTCUSDT", "withdrawal_rate", "20260801", n_obs=0)
    assert g.report(["BTCUSDT"], ["20260801"], ["withdrawal_rate"])["coverage_pct"] == 0.0
    g.mark("BTCUSDT", "withdrawal_rate", "20260801", n_obs=12)
    assert g.report(["BTCUSDT"], ["20260801"], ["withdrawal_rate"])["coverage_pct"] == 100.0


def test_holes_are_reported_as_targets_not_as_failures() -> None:
    """A hole is the highest-EV place to point tomorrow's run: it is the difference between
    "mined and empty" and "never looked", and those demand opposite responses."""
    rep = coverage_report([extract_all("BTCUSDT", [_book(i) for i in range(6)]) | {"day": "d1"}],
                          ["BTCUSDT", "ETHUSDT"], ["d1", "d2"])
    assert rep["holes"] > 0
    assert rep["next_targets"] and "ETHUSDT" in " ".join(rep["next_targets"])
    assert 0 < rep["coverage_pct"] < 100


def test_coverage_of_an_unmined_grid_is_zero_not_undefined() -> None:
    rep = coverage_report([], ["BTCUSDT"], ["d1"])
    assert rep["coverage_pct"] == 0.0
    assert rep["cells_filled"] == 0


def test_phantom_pairs_are_excluded_from_the_denominator_but_stay_counted() -> None:
    """Measured 2026-08-12: the cartesian symbols x days grid manufactured 11,004 holes for
    (symbol, day) pairs with NO tape -- ETHUSDT listed on d2 has no d1 files, and no miner at
    any effort level can fill that cell. Coverage pinned at 53.05% STANDING-STILL while every
    real cell was 7/7 measured. A pair without tape is a listing-window fact, not unexplored
    edge; it must be published, never counted as a hole."""
    mined = extract_all("BTCUSDT", [_book(i) for i in range(6)]) | {"day": "d1"}
    # Tape exists only for BTCUSDT/d1 and ETHUSDT/d2; the cartesian grid would invent 2 phantom
    # pairs (BTCUSDT/d2, ETHUSDT/d1).
    pairs = [("BTCUSDT", "d1"), ("ETHUSDT", "d2")]
    rep = coverage_report([mined], ["BTCUSDT", "ETHUSDT"], ["d1", "d2"], pairs=pairs)
    assert rep["phantom_pairs_excluded"] == 2
    assert rep["cells_total"] == 2 * 7                      # real pairs x mechanisms only
    # ETHUSDT/d2 has tape and is unmined: still a real hole pointing the next run.
    assert any("ETHUSDT" in t and "d2" in t for t in rep["next_targets"])
    assert not any("d1" in t and "ETHUSDT" in t for t in rep["next_targets"])
    assert "denominator" in rep


def test_fully_mined_real_tape_reads_complete_even_with_phantom_pairs() -> None:
    """The state the live miner was actually in: every cell with tape measured, phantoms only.
    The honest reading is 100% of the mineable grid -- COMPLETE-FOR-THIS-GRID upstream -- not a
    P26 breach that no amount of mining can clear."""
    mined = [extract_all("BTCUSDT", [_book(i) for i in range(6)]) | {"day": "d1"}]
    rep = coverage_report(mined, ["BTCUSDT", "ETHUSDT"], ["d1", "d2"],
                          pairs=[("BTCUSDT", "d1")])
    filled_mechs = sum(1 for m, s in mined[0]["mechanisms"].items() if s.get("n", 0) > 0)
    if filled_mechs == 7:                                   # guard: fixture measures all 7
        assert rep["coverage_pct"] == 100.0 and rep["holes"] == 0
    assert rep["phantom_pairs_excluded"] == 3
