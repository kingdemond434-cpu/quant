"""The moat features must be correct before they are trusted -- a sign error here is invisible.

Every feature is computed from data the crowd does not have, which means nobody else's published
result will contradict us if we get it wrong. That is exactly why these are pinned.
"""
from __future__ import annotations

import gzip
import json

import numpy as np

from libs.research.moat_microstructure import (
    Bar,
    bar_returns,
    book_state,
    flow_momentum,
    liquidity_withdrawal,
    microprice_reversion,
    obi_pressure,
    read_partition,
    resample,
    signed_flow,
)


def _depth(t, bids, asks):
    return {"t": t, "k": "d", "b": [[str(p), str(q)] for p, q in bids],
            "a": [[str(p), str(q)] for p, q in asks]}


def test_buyer_is_maker_means_the_aggressor_sold():
    """THE FIELD THAT IS EASY TO GET BACKWARDS. `m=True` means the resting order was a BID, so the
    aggressor HIT it -- a sell. Invert this and every flow feature silently changes sign, the
    backtest still runs, and the result is confidently wrong."""
    assert signed_flow({"q": "2.5", "m": True}) == -2.5
    assert signed_flow({"q": "2.5", "m": False}) == 2.5
    assert signed_flow({"q": "bad", "m": False}) == 0.0


def test_obi_is_positive_when_the_bid_is_heavier():
    st = book_state(_depth(1, [(100.0, 10.0)], [(101.0, 2.0)]))
    assert st is not None and st.obi > 0
    st2 = book_state(_depth(1, [(100.0, 2.0)], [(101.0, 10.0)]))
    assert st2 is not None and st2.obi < 0


def test_microprice_leans_toward_the_thin_side():
    """The standard result and the reason micro-mid predicts: the thin side is the side that gets
    taken, so the size-weighted touch sits nearer it."""
    st = book_state(_depth(1, [(100.0, 10.0)], [(101.0, 1.0)]))
    assert st is not None
    assert st.micro > st.mid          # heavy bid, thin ask -> micro pulled up toward the ask


def test_a_crossed_book_is_rejected_not_scored():
    """A crossed book is a snapshot-stitching artifact, not an arbitrage. Scoring it would let one
    bad record dominate every downstream mean."""
    assert book_state(_depth(1, [(101.0, 5.0)], [(100.0, 5.0)])) is None
    assert book_state(_depth(1, [], [(100.0, 5.0)])) is None
    assert book_state(_depth(1, [(100.0, 0.0)], [(101.0, 0.0)])) is None


def test_deep_imbalance_uses_the_whole_book_not_just_the_touch():
    """This is the feature that actually requires the moat -- touch imbalance is visible in any
    free ticker, 20-level imbalance is not."""
    st = book_state(_depth(1, [(100.0, 1.0), (99.0, 50.0)], [(101.0, 1.0), (102.0, 2.0)]))
    assert st is not None
    assert abs(st.obi) < 1e-9         # touch is balanced
    assert st.obi_deep > 0.5          # but the book behind it is heavily bid


def test_resample_averages_the_book_rather_than_sampling_it():
    """A single snapshot is dominated by whichever quote happened to rest at that instant."""
    recs = [_depth(1000, [(100.0, 10.0)], [(101.0, 1.0)]),
            _depth(2000, [(100.0, 1.0)], [(101.0, 10.0)])]
    bars = resample(iter(recs), ms=60_000)
    assert len(bars) == 1
    assert abs(bars[0].obi) < 1e-9    # the two opposite books average out
    assert bars[0].n_books == 2


def test_flow_and_volume_separate_direction_from_activity():
    recs = [_depth(1000, [(100.0, 5.0)], [(101.0, 5.0)]),
            {"t": 1100, "k": "t", "q": "3", "m": False},
            {"t": 1200, "k": "t", "q": "1", "m": True}]
    b = resample(iter(recs), ms=60_000)[0]
    assert np.isclose(b.volume, 4.0)             # activity is unsigned
    assert np.isclose(b.tfi, (3.0 - 1.0) / 4.0)  # imbalance is signed and normalised


def test_position_earns_the_next_bar():
    bars = [Bar(0, 100.0, 0, 0, 1, 0, 0, 0, 0, 1), Bar(1, 110.0, 0, 0, 1, 0, 0, 0, 0, 1),
            Bar(2, 121.0, 0, 0, 1, 0, 0, 0, 0, 1)]
    r = bar_returns(np.array([1.0, 1.0, 1.0]), bars, cost_bps=0.0)
    assert len(r) == 2 and np.allclose(r, 0.10)


def test_liquidity_withdrawal_goes_FLAT_not_short():
    """The signal is adverse-selection RISK, not direction. The right response to 'the book has
    gone' is to stop trading, never to guess which way it went."""
    n = 200
    bars = [Bar(i, 100.0, 0, 0, 1.0, 0, 0, 0, 100.0, 1) for i in range(n)]
    bars += [Bar(n, 100.0, 0, 0, 40.0, 0, 0, 0, 1.0, 1)]     # depth gone, spread blown out
    pos = liquidity_withdrawal(bars, n=60)
    assert pos[-1] == 0.0
    assert set(np.unique(pos)) <= {0.0, 1.0}                 # never short


def test_candidates_are_causal():
    rng = np.random.default_rng(1)
    n = 400
    bars = [Bar(i, 100.0 + rng.standard_normal(), float(rng.standard_normal()),
                float(rng.standard_normal()), abs(float(rng.standard_normal())) + 1,
                1.0, float(rng.standard_normal()), 10.0, 100.0, 5) for i in range(n)]
    for fn in (obi_pressure, flow_momentum, microprice_reversion):
        full = fn(bars)
        early = fn(bars[:250])
        assert np.allclose(full[:250], early), f"{fn.__name__} peeks"


def test_a_truncated_partition_still_reads(tmp_path):
    """The recorder is killed mid-write on every restart, so a partial final line is NORMAL.
    Dropping the tail of one hour is a gap; refusing to read the hour is a lost day."""
    p = tmp_path / "x.jsonl.gz"
    with gzip.open(p, "wt", encoding="utf-8") as f:
        f.write(json.dumps({"t": 1, "k": "t", "q": "1", "m": False}) + "\n")
        f.write('{"t": 2, "k": "t", "q": ')          # truncated
    assert len(list(read_partition(p))) == 1


def test_a_missing_partition_is_empty_not_an_exception(tmp_path):
    assert list(read_partition(tmp_path / "nope.jsonl.gz")) == []
