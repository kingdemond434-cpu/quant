"""THE ONE ASSET THIS DESK OWNS AND THE CROWD DOES NOT -- 165 statements, zero tests until now.

On 2026-08-01 the desk ran 129 textbook mechanisms across 10 liquid pairs on daily bars through
the repaired gauntlet: 0 survivors, best in-sample Sharpe 1.75 delivering OOS 0.08, max OOS across
all 129 of 0.100 and a mean of -0.001. Public indicators on the most liquid pairs at default
parameters are picked clean. That result is the argument for this file: the edge was never
supposed to be indicators, it is the tape -- 20-level depth at ~4s cadence recorded since
2026-07-21, which cannot be bought back for an unrecorded day at any price.

WHICH MAKES AN UNTESTED PARSER THE WORST PLACE TO HAVE ONE. Every candidate downstream is built on
`book_state` and `signed_flow`, and the module's own docstring names the trap by name:

    `m` is TRUE when the BUYER was the maker, which means the aggressor was a SELLER. Signed flow
    is therefore -1 when m is true. Invert that and every flow feature changes sign, the backtest
    still runs, and the result is confidently wrong.

"so it is asserted in the tests rather than trusted" -- and there were no tests. That assertion is
the first one below.

The other three properties worth more than line coverage:
  * a CROSSED book returns None rather than a huge negative spread, so one stitched snapshot
    cannot dominate every downstream mean;
  * `_z` scores a FLAT window followed by a move as unboundedly surprising rather than NaN --
    without that, `liquidity_withdrawal` is blind to a perfectly stable book that suddenly empties,
    which is the most extreme instance of the exact event it exists to detect;
  * positions are causal: bar i's decision earns bar i+1's move, and costs are charged on every
    change, because at 1-minute bars a strategy that flips constantly pays the spread every time.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import pytest

from libs.research import moat_microstructure as MM

#: 2026-01-01T00:00:00Z in epoch ms. The fixtures originally used t=0, which is 1970 and which
#: `resample` correctly rejects -- so every bucketing assertion was silently testing the reject
#: path. The module was right and the fixture was wrong: an epoch-ms stamp of 0 is not a time.
_T0 = 1_767_225_600_000


def _depth(t: int, bid: float = 100.0, ask: float = 100.1, bq: float = 5.0, aq: float = 5.0,
           levels: int = 5, kind: str = "d") -> dict:
    b = [[bid - i * 0.01, bq] for i in range(levels)]
    a = [[ask + i * 0.01, aq] for i in range(levels)]
    return {"t": t, "k": kind, "b": b, "a": a}


def _trade(t: int, q: float, buyer_is_maker: bool) -> dict:
    return {"t": t, "k": "t", "p": "100.0", "q": q, "m": buyer_is_maker}


# ============================================================ the sign that inverts everything

def test_m_TRUE_means_the_AGGRESSOR_WAS_A_SELLER() -> None:
    """THE FIELD THE MODULE NAMES AS EASY TO GET BACKWARDS. `m=True` means the resting order was a
    BID, so the aggressor hit it -- a SELL. Invert this and every flow feature changes sign, the
    backtest still runs, and the result is confidently wrong."""
    assert MM.signed_flow({"q": 3.0, "m": True}) == -3.0
    assert MM.signed_flow({"q": 3.0, "m": False}) == 3.0


def test_a_missing_m_field_is_read_as_a_BUY_not_as_zero() -> None:
    """Absent means falsy means the seller was the maker means the aggressor bought. Reading it as
    zero would silently drop every record from a recorder that omits the field."""
    assert MM.signed_flow({"q": 2.0}) == 2.0


@pytest.mark.parametrize("bad", [{"q": "abc"}, {"q": None}, {}])
def test_an_unparseable_size_contributes_ZERO_flow(bad) -> None:
    assert MM.signed_flow(bad) == 0.0


# ============================================================ book_state

def test_the_microprice_is_weighted_TOWARD_THE_THIN_SIDE() -> None:
    """The standard result and the reason micro-mid predicts: the thin side is the side that gets
    taken. Weighting the other way would invert `microprice_reversion` while still producing a
    plausible-looking series."""
    st = MM.book_state(_depth(1, bid=100.0, ask=100.1, bq=100.0, aq=1.0))
    assert st is not None
    assert st.micro > st.mid, "heavy bid, thin ask -- the microprice must sit toward the ask"

    st2 = MM.book_state(_depth(1, bid=100.0, ask=100.1, bq=1.0, aq=100.0))
    assert st2 is not None and st2.micro < st2.mid


def test_a_CROSSED_book_returns_None_rather_than_a_huge_negative_spread() -> None:
    """A crossed book is a venue artifact of stitching two snapshot halves, not an arbitrage.
    Returning a spread of -8000bps lets ONE bad record dominate every downstream mean."""
    assert MM.book_state({"t": 1, "b": [[101.0, 1.0]], "a": [[100.0, 1.0]]}) is None
    assert MM.book_state({"t": 1, "b": [[100.0, 1.0]], "a": [[100.0, 1.0]]}) is None, "locked too"


@pytest.mark.parametrize("rec", [
    {"t": 1, "b": [], "a": [[100.0, 1.0]]},
    {"t": 1, "b": [[100.0, 1.0]], "a": []},
    {"t": 1},
    {"t": 1, "b": [[0.0, 1.0]], "a": [[100.0, 1.0]]},
    {"t": 1, "b": [[100.0, 0.0]], "a": [[100.1, 0.0]]},
])
def test_an_unusable_book_is_None_and_never_a_fabricated_state(rec) -> None:
    assert MM.book_state(rec) is None


def test_malformed_levels_are_skipped_rather_than_taking_the_record_down() -> None:
    """A recorder writing a partial level is normal. Losing the whole snapshot for it is not."""
    st = MM.book_state({"t": 1, "b": [["bad"], [100.0, 5.0]], "a": [[100.1, 5.0], None]})
    assert st is not None and st.mid == pytest.approx(100.05)


def test_touch_imbalance_and_DEEP_imbalance_are_different_measurements() -> None:
    """`obi_deep` is the one the crowd cannot compute without L2 -- it is the whole reason this
    file exists. If it collapsed to the touch value, the moat feature would be a public one."""
    rec = {"t": 1, "k": "d",
           "b": [[100.0, 1.0], [99.9, 50.0], [99.8, 50.0]],
           "a": [[100.1, 1.0], [100.2, 1.0], [100.3, 1.0]]}
    st = MM.book_state(rec)
    assert st is not None
    assert st.obi == pytest.approx(0.0), "the touch is balanced"
    assert st.obi_deep > 0.9, "the depth is overwhelmingly bid"


@pytest.mark.parametrize("bq,aq,sign", [(9.0, 1.0, 1), (1.0, 9.0, -1), (5.0, 5.0, 0)])
def test_touch_imbalance_is_bounded_and_signed_bid_positive(bq, aq, sign) -> None:
    st = MM.book_state(_depth(1, bq=bq, aq=aq, levels=1))
    assert st is not None
    assert -1.0 <= st.obi <= 1.0
    assert (st.obi > 0) == (sign > 0) and (st.obi < 0) == (sign < 0)


def test_the_slope_is_larger_for_a_book_that_thickens_close_to_the_touch() -> None:
    """A flat book fills badly, and `slope` is what says so. If it did not separate these two the
    feature would be noise with a name."""
    tight = MM.book_state({"t": 1, "b": [[100.0, 1.0], [99.99, 100.0]],
                           "a": [[100.1, 1.0], [100.11, 100.0]]})
    flat = MM.book_state({"t": 1, "b": [[100.0, 1.0], [99.0, 1.0]],
                          "a": [[100.1, 1.0], [101.1, 1.0]]})
    assert tight is not None and flat is not None
    assert tight.slope > flat.slope


def test_the_spread_is_reported_in_basis_points_of_mid() -> None:
    st = MM.book_state(_depth(1, bid=100.0, ask=100.1, levels=1))
    assert st is not None
    assert st.spread_bps == pytest.approx(0.1 / 100.05 * 1e4, rel=1e-6)


# ============================================================ resample

def test_book_features_are_AVERAGED_over_the_interval_not_sampled_at_its_close() -> None:
    """A single snapshot is dominated by whichever quote happened to be resting at that instant.
    The average is the quantity with signal in it -- and last-value sampling would look identical
    on a smooth series and diverge exactly where the book is interesting."""
    recs = [_depth(_T0, bq=9.0, aq=1.0, levels=1), _depth(_T0 + 1_000, bq=1.0, aq=9.0, levels=1),
            _depth(_T0 + 2_000, bq=5.0, aq=5.0, levels=1)]
    bars = MM.resample(iter(recs), ms=60_000)
    assert len(bars) == 1
    assert bars[0].obi == pytest.approx(0.0, abs=1e-9), "0.8, -0.8 and 0.0 average to zero"
    assert bars[0].n_books == 3


def test_trade_flow_imbalance_is_NORMALISED_by_total_volume() -> None:
    """Raw signed flow scales with activity, so a quiet hour and a busy one would not be
    comparable and the z-score would be measuring volume."""
    recs = [_depth(_T0, levels=1),
            _trade(_T0 + 1, 8.0, buyer_is_maker=False),   # +8 aggressive buy
            _trade(_T0 + 2, 2.0, buyer_is_maker=True)]    # -2 aggressive sell
    bars = MM.resample(iter(recs), ms=60_000)
    assert bars[0].tfi == pytest.approx(6.0 / 10.0)
    assert bars[0].volume == pytest.approx(10.0)


def test_a_bar_with_no_trades_has_tfi_ZERO_rather_than_NaN() -> None:
    """NaN would propagate into the z-score and blank the feature for the whole window; a quiet
    minute is a real observation of no imbalance."""
    bars = MM.resample(iter([_depth(_T0, levels=1)]), ms=60_000)
    assert bars[0].tfi == 0.0 and bars[0].volume == 0.0


def test_a_bucket_with_TRADES_BUT_NO_BOOK_is_dropped() -> None:
    """Every feature in a Bar is a book feature except tfi. Emitting a bar with a fabricated mid
    would put an invented price into the return series."""
    assert MM.resample(iter([_trade(_T0, 5.0, False)]), ms=60_000) == []


def test_records_are_bucketed_by_the_declared_interval() -> None:
    recs = [_depth(_T0, levels=1), _depth(_T0 + 59_999, levels=1), _depth(_T0 + 60_000, levels=1)]
    bars = MM.resample(iter(recs), ms=60_000)
    assert [b.t_ms for b in bars] == [_T0, _T0 + 60_000]
    assert [b.n_books for b in bars] == [2, 1]


def test_bars_come_out_in_TIME_ORDER_whatever_order_the_records_arrive() -> None:
    """A recorder restart can interleave partitions. An out-of-order bar list would make `np.diff`
    compute a return between two unrelated instants."""
    recs = [_depth(_T0 + 120_000, levels=1), _depth(_T0, levels=1),
            _depth(_T0 + 60_000, levels=1)]
    got = [b.t_ms for b in MM.resample(iter(recs), ms=60_000)]
    assert got == [_T0, _T0 + 60_000, _T0 + 120_000]


@pytest.mark.parametrize("bad_t", [{"t": "x"}, {"t": None}, {"t": 0}, {"t": -5}])
def test_a_record_with_no_usable_timestamp_is_skipped(bad_t) -> None:
    rec = {**_depth(_T0, levels=1), **bad_t}
    assert MM.resample(iter([rec]), ms=60_000) == []


def test_the_BYBIT_record_shapes_are_supported_alongside_binance() -> None:
    """The desk runs two recorders. Supporting only one silently halves the archive."""
    recs = [
        _depth(_T0, levels=1, kind="depth"),
        {"t": _T0 + 1, "k": "trades", "v": [{"side": "Buy", "size": "7"},
                                      {"side": "Sell", "size": "3"}]},
    ]
    bars = MM.resample(iter(recs), ms=60_000)
    assert len(bars) == 1
    assert bars[0].tfi == pytest.approx(4.0 / 10.0)


def test_a_malformed_bybit_inner_trade_is_skipped_not_fatal() -> None:
    recs = [_depth(_T0, levels=1),
            {"t": _T0 + 1, "k": "trades", "v": [{"side": "Buy", "size": "x"}, "junk",
                                          {"side": "Buy", "size": 5.0}]}]
    bars = MM.resample(iter(recs), ms=60_000)
    assert bars[0].volume == pytest.approx(5.0)


# ============================================================ the trailing z-score

def test_the_z_score_never_includes_the_CURRENT_bar_in_its_own_mean() -> None:
    """The window is [i-n, i). Including bar i shrinks its own deviation and every entry
    threshold becomes unreachable in exactly the moments that matter."""
    x = np.concatenate([np.zeros(10), [100.0]])
    z = MM._z(x, 10)
    assert np.isinf(z[10]) or z[10] > 5, "a huge move against a flat history must score huge"


def test_a_FLAT_WINDOW_FOLLOWED_BY_A_MOVE_is_unboundedly_surprising() -> None:
    """NOT NaN. The first version returned NaN on a zero-variance window, which made
    `liquidity_withdrawal` blind to a perfectly stable book that suddenly empties -- the most
    extreme instance of the very event it exists to detect."""
    x = np.concatenate([np.full(10, 5.0), [1.0], [9.0]])
    z = MM._z(x, 10)
    assert z[10] == -np.inf
    assert np.isfinite(z[11]) or z[11] > 0


def test_a_flat_window_followed_by_NO_move_scores_exactly_zero() -> None:
    z = MM._z(np.full(12, 5.0), 10)
    assert z[10] == 0.0 and z[11] == 0.0


def test_the_warmup_is_NaN_rather_than_a_fabricated_zero() -> None:
    z = MM._z(np.arange(20, dtype="float64"), 10)
    assert np.all(np.isnan(z[:10]))
    assert np.all(np.isfinite(z[10:]))


# ============================================================ the candidates

def _bars(n: int, **series) -> list[MM.Bar]:
    def col(name: str, default: float) -> np.ndarray:
        v = series.get(name, default)
        return np.full(n, v, dtype="float64") if np.isscalar(v) else np.asarray(v, dtype="float64")
    return [MM.Bar(t_ms=i * 60_000, mid=float(col("mid", 100.0)[i]),
                   obi=float(col("obi", 0.0)[i]), obi_deep=float(col("obi_deep", 0.0)[i]),
                   spread_bps=float(col("spread_bps", 1.0)[i]),
                   slope=float(col("slope", 1.0)[i]), tfi=float(col("tfi", 0.0)[i]),
                   volume=float(col("volume", 1.0)[i]),
                   depth_total=float(col("depth_total", 100.0)[i]), n_books=5)
            for i in range(n)]


@pytest.mark.parametrize("name", sorted(MM.CANDIDATES))
def test_every_candidate_returns_one_position_per_bar_in_minus_one_to_one(name: str) -> None:
    rng = np.random.default_rng(3)
    n = 200
    bars = _bars(n, obi_deep=rng.normal(size=n), tfi=rng.normal(size=n),
                 depth_total=100 + rng.normal(size=n), spread_bps=1 + rng.normal(size=n) * 0.1,
                 obi=rng.normal(size=n) * 0.1)
    pos = MM.CANDIDATES[name](bars)
    assert pos.shape == (n,)
    assert np.all(np.abs(pos) <= 1.0)
    assert not np.isnan(pos).any(), "a NaN position is an unhedged, unstated exposure"


@pytest.mark.parametrize("name", sorted(MM.CANDIDATES))
def test_every_candidate_is_CAUSAL_by_truncation(name: str) -> None:
    """The only test that actually proves causality: recomputing on the prefix must reproduce the
    value. A centred window passes every other check and fails this."""
    rng = np.random.default_rng(4)
    n = 200
    kw = {"obi_deep": rng.normal(size=n), "tfi": rng.normal(size=n),
          "depth_total": 100 + rng.normal(size=n),
          "spread_bps": 1 + np.abs(rng.normal(size=n)) * 0.2, "obi": rng.normal(size=n) * 0.1}
    bars = _bars(n, **kw)
    full = MM.CANDIDATES[name](bars)
    for t in (120, 199):
        assert MM.CANDIDATES[name](bars[:t + 1])[t] == pytest.approx(full[t])


def test_obi_pressure_FOLLOWS_deep_imbalance() -> None:
    x = np.concatenate([np.zeros(60), [5.0]])
    bars = _bars(61, obi_deep=x)
    assert MM.obi_pressure(bars, n=60)[60] == 1.0
    bars_dn = _bars(61, obi_deep=-x)
    assert MM.obi_pressure(bars_dn, n=60)[60] == -1.0


def test_flow_momentum_FOLLOWS_aggressor_flow() -> None:
    x = np.concatenate([np.zeros(30), [5.0]])
    assert MM.flow_momentum(_bars(31, tfi=x), n=30)[30] == 1.0


def test_microprice_reversion_FADES_the_divergence() -> None:
    """It is a reversion candidate: a positive deviation must produce a SHORT. If this ever
    followed instead of faded, the module would hold two momentum candidates and no hedge."""
    obi = np.concatenate([np.zeros(60), [1.0]])
    pos = MM.microprice_reversion(_bars(61, obi=obi, spread_bps=1.0), n=60)
    assert pos[60] == -1.0


def test_liquidity_withdrawal_goes_FLAT_and_never_short() -> None:
    """The signal is about ADVERSE SELECTION RISK, not direction. The right response to 'the book
    has gone' is to stop trading, not to guess which way -- and a short here would be taking a
    directional view on the strength of a liquidity observation."""
    depth = np.concatenate([np.full(60, 100.0), [1.0]])
    spread = np.concatenate([np.full(60, 1.0), [50.0]])
    pos = MM.liquidity_withdrawal(_bars(61, depth_total=depth, spread_bps=spread), n=60)
    assert set(np.unique(pos)) <= {0.0, 1.0}
    assert pos[60] == 0.0, "depth collapsed and the spread widened -- stand aside"


def test_liquidity_withdrawal_needs_BOTH_the_depth_drop_and_the_widening() -> None:
    """Depth falling on a stable spread is a quiet market, not makers stepping away. Firing on one
    leg would take the desk flat every time volume dipped."""
    depth = np.concatenate([np.full(60, 100.0), [1.0]])
    pos = MM.liquidity_withdrawal(_bars(61, depth_total=depth, spread_bps=1.0), n=60)
    assert pos[60] == 1.0


def test_a_short_series_yields_all_flat_rather_than_an_index_error() -> None:
    for name, fn in MM.CANDIDATES.items():
        pos = fn(_bars(5))
        assert pos.shape == (5,), name


# ============================================================ returns and costs

def test_position_at_bar_i_earns_bar_i_PLUS_ONE_s_move() -> None:
    """Off by one here is a time machine, and it is the single most flattering bug available."""
    bars = _bars(3, mid=np.array([100.0, 101.0, 102.0]))
    r = MM.bar_returns(np.array([1.0, 0.0, 0.0]), bars, cost_bps=0.0)
    assert r[0] == pytest.approx(0.01), "the position held at bar 0 earns 100->101"
    assert r[1] == pytest.approx(0.0), "flat at bar 1 earns nothing from 101->102"


def test_cost_is_charged_on_every_CHANGE_of_position() -> None:
    """At 1-minute bars a strategy that flips constantly pays the spread every time, and the
    spread -- not the fee -- is what dominates at this horizon."""
    bars = _bars(4, mid=np.full(4, 100.0))
    flipping = MM.bar_returns(np.array([1.0, -1.0, 1.0, -1.0]), bars, cost_bps=10.0)
    holding = MM.bar_returns(np.array([1.0, 1.0, 1.0, 1.0]), bars, cost_bps=10.0)
    assert flipping.sum() < holding.sum()


def test_ENTERING_from_flat_is_itself_a_turn() -> None:
    """The first position is a trade. Starting the turnover series at the first CHANGE would give
    every strategy one free entry, which flatters the high-frequency ones most."""
    bars = _bars(2, mid=np.full(2, 100.0))
    r = MM.bar_returns(np.array([1.0, 1.0]), bars, cost_bps=10.0)
    assert r[0] < 0.0


def test_fewer_than_two_bars_returns_an_EMPTY_series_not_a_crash() -> None:
    assert MM.bar_returns(np.array([1.0]), _bars(1)).shape == (0,)
    assert MM.bar_returns(np.array([]), []).shape == (0,)


def test_a_NaN_position_is_treated_as_FLAT_rather_than_poisoning_the_series() -> None:
    """One NaN in a cumulative return makes every later value NaN, and NaN comparisons are False
    everywhere -- so the failure would be silent and total."""
    bars = _bars(3, mid=np.array([100.0, 101.0, 102.0]))
    r = MM.bar_returns(np.array([np.nan, 1.0, 1.0]), bars, cost_bps=0.0)
    assert np.all(np.isfinite(r))
    assert r[0] == pytest.approx(0.0)


# ============================================================ the tape reader

def test_a_TRUNCATED_FINAL_LINE_costs_one_row_and_not_the_hour(tmp_path: Path) -> None:
    """The recorder is killed mid-write on every restart, so a partial row is EXPECTED. Dropping
    the tail of one hour is a gap; refusing to read the hour is a lost day -- and an unrecorded
    day cannot be bought back at any price."""
    p = tmp_path / "20260806_00.jsonl.gz"
    with gzip.open(p, "wt", encoding="utf-8") as f:
        f.write(json.dumps(_depth(_T0, levels=1)) + "\n")
        f.write(json.dumps(_depth(_T0 + 1_000, levels=1)) + "\n")
        f.write('{"t": 2000, "k": "d", "b": [[10')          # killed mid-write
    assert len(list(MM.read_partition(p))) == 2


def test_an_unreadable_partition_yields_NOTHING_rather_than_raising(tmp_path: Path) -> None:
    """A corrupt gzip member must not take down a screen that is walking thousands of files."""
    p = tmp_path / "bad.jsonl.gz"
    p.write_bytes(b"this is not gzip at all")
    assert list(MM.read_partition(p)) == []
    assert list(MM.read_partition(tmp_path / "absent.jsonl.gz")) == []


def test_partitions_are_returned_in_DAY_ORDER(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(MM, "MOAT", tmp_path)
    d = tmp_path / "fut" / "BTCUSDT"
    d.mkdir(parents=True)
    for name in ("20260806_00.jsonl.gz", "20260805_00.jsonl.gz", "20260805_12.jsonl.gz"):
        (d / name).write_bytes(b"")
    got = [p.name for p in MM.partitions("BTCUSDT")]
    assert got == ["20260805_00.jsonl.gz", "20260805_12.jsonl.gz", "20260806_00.jsonl.gz"]


def test_an_absent_symbol_or_venue_is_an_EMPTY_LIST(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(MM, "MOAT", tmp_path)
    assert MM.partitions("NOSUCHUSDT") == []
    assert MM.partitions("BTCUSDT", venue="nosuchvenue") == []


# ============================================================ the registry

def test_the_registry_holds_a_MIX_of_directions() -> None:
    """Four momentum candidates would be one bet in four costumes -- exactly what
    `cohort_independence` measures and `marginal_admission` refuses. The registry is the first
    place that can go wrong."""
    assert len(MM.CANDIDATES) >= 4
    assert "microprice_reversion" in MM.CANDIDATES, "the only mean-reverting candidate"
    assert "liquidity_withdrawal" in MM.CANDIDATES, "the only risk-off (flat) candidate"


def test_every_registered_candidate_is_callable_with_bars_alone() -> None:
    """A candidate needing extra arguments cannot be swept by the screen, which calls them
    uniformly -- and it would be silently skipped rather than reported."""
    for name, fn in MM.CANDIDATES.items():
        assert callable(fn)
        assert fn(_bars(80)).shape == (80,), name
