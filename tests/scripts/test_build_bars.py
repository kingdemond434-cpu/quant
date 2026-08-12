"""TAPE -> BARS: the missing link between 8.2GB of recorded L2 and every screen on this desk.

WHY THE TESTS ARE SHAPED THIS WAY. This module converts the desk's only unreplicable asset into
the form every downstream consumer eats. A quiet defect here does not fail -- it produces bars that
look fine and are wrong, under every screen, permanently. So the suite is mostly about the ways
that could happen silently: reading one recorder schema and not the other, inventing prices where
nothing traded, and averaging a level that should be sampled.
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import scripts.build_bars as B

T0 = 1767225600000          # 2026-01-01T00:00:00Z in ms


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


@pytest.fixture
def tape(tmp_path, monkeypatch):
    monkeypatch.setattr(B, "MOAT", tmp_path / "moat")
    monkeypatch.setattr(B, "OUT", tmp_path / "bars")
    monkeypatch.setattr(B, "REPORT", tmp_path / "r.json")
    return tmp_path / "moat"


# ------------------------------------------------------------------ both schemas or silent loss


def test_BOTH_recorder_schemas_are_read() -> None:
    """THE LOAD-BEARING TEST. Binance stamps trades k='t' with flat p/q; Bybit stamps k='trades'
    with a NESTED list under v. A reader handling one returns clean, plausible, HALF-EMPTY bars
    over the other venue's archive -- the same class of bug that made moat_mine blind to 4.4GB
    until DEPTH_KINDS was added, and equally invisible."""
    binance = {"t": T0, "k": "t", "a": 1, "p": "100.5", "q": "0.5", "m": False}
    bybit = {"t": T0, "k": "trades", "v": [{"T": T0, "p": "100.5", "v": "0.3"}]}
    assert B.trades_from(binance) == [(T0, 100.5, 0.5)]
    assert B.trades_from(bybit) == [(T0, 100.5, 0.3)]


def test_bybit_size_under_either_key_is_accepted() -> None:
    """Bybit labels size `v` on some payloads and `size` on others. A missed quantity becomes
    zero volume -- a bar that looks real and weighs nothing, which every volume-scaled feature
    downstream then inherits."""
    r = {"t": T0, "k": "trades", "v": [{"T": T0, "p": "100", "size": "2.5"}]}
    assert B.trades_from(r) == [(T0, 100.0, 2.5)]


def test_depth_rows_never_become_prices() -> None:
    """Nothing trades at the book mid. Resampling depth into OHLC would put a synthetic price
    series under every screen on the desk, and the resulting IC would be a fact about the book
    rather than about executable prices."""
    depth = {"t": T0, "k": "d", "b": [["100", "1"]], "a": [["101", "1"]]}
    assert B.trades_from(depth) == []
    assert B.trades_from({"t": T0, "k": "depth", "b": [], "a": []}) == []


def test_a_corrupt_line_is_skipped_not_guessed(tape) -> None:
    """A fabricated bar is worse than a missing one: it cannot be detected downstream."""
    p = tape / "fut" / "BTCUSDT" / "20260101_00.jsonl.gz"
    p.parent.mkdir(parents=True)
    with gzip.open(p, "wt", encoding="utf-8") as f:
        f.write(json.dumps({"t": T0, "k": "t", "p": "100", "q": "1"}) + "\n")
        f.write("{not json at all\n")
        f.write(json.dumps({"t": T0 + 1000, "k": "t", "p": "101", "q": "1"}) + "\n")
    _, diag = B.build([p])
    assert diag["trades"] == 2


# ------------------------------------------------------------------ what must not be invented


def test_empty_buckets_are_DROPPED_not_forward_filled(tape) -> None:
    """A bar carried from the previous close is a price nothing traded at. Screens would read the
    flat stretch as genuine low volatility, and every vol-scaled feature downstream would be wrong
    in the same direction -- optimistically."""
    p = tape / "fut" / "BTCUSDT" / "20260101_00.jsonl.gz"
    _write(p, [{"t": T0, "k": "t", "p": "100", "q": "1"},
               {"t": T0 + 3 * 3600_000, "k": "t", "p": "110", "q": "1"}])   # 3h gap
    bars, _ = B.build([p])
    assert len(bars) == 2, "the empty buckets between the two trades were filled"
    assert (bars["trades"] > 0).all()


def test_open_interest_is_SAMPLED_not_summed(tape) -> None:
    """OI is a LEVEL, not a flow. Summing or averaging it invents a quantity the venue never
    reported -- and oi_flush, the one crypto-native detector with a mechanical basis, reads it."""
    rows = [{"t": T0 + i * 1000, "k": "t", "p": "100", "q": "1"} for i in range(10)]
    rows += [{"t": T0 + i * 1000, "k": "meta", "oi": str(1_000_000 + i)} for i in range(10)]
    p = tape / "bybit" / "BTCUSDT" / "20260101_00.jsonl.gz"
    _write(p, rows)
    bars, _ = B.build([p])
    assert bars["open_interest"].iloc[0] == pytest.approx(1_000_009)   # last in bucket
    assert bars["open_interest"].iloc[0] < 1_000_100                   # not a sum


# ------------------------------------------------------------------ honest empty


def test_no_tape_names_the_recorders_not_this_organ(tape) -> None:
    assert B.main() == 0
    rep = json.loads((tape.parent / "r.json").read_text("utf-8"))
    assert rep["state"] == "NO TAPE"
    assert "recorders" in rep["next"]


def test_tape_with_no_TRADES_is_distinguished_from_no_tape(tape) -> None:
    """Depth-only tape is a real and different state: the recorders ARE running, but aggTrades are
    not being captured. Reporting it as 'no tape' would send anyone at the wrong problem."""
    p = tape / "fut" / "BTCUSDT" / "20260101_00.jsonl.gz"
    _write(p, [{"t": T0, "k": "d", "b": [["100", "1"]], "a": [["101", "1"]]}])
    assert B.main() == 0
    rep = json.loads((tape.parent / "r.json").read_text("utf-8"))
    assert rep["state"] == "NO TRADES"
    assert "never from book mid" in rep["reason"]


# ------------------------------------------------------------------ end to end


def test_bars_feed_the_ICT_screen_end_to_end(tape, monkeypatch, tmp_path) -> None:
    """THE POINT OF THE WHOLE MODULE. Tape in, bars out, EVERY detector screened -- the chain that
    reported NO BARS before this existed.

    THIS ASSERTION USED TO READ `== 14` AND BROKE THE MOMENT THE FAMILY GREW to 22. That is the
    second time this session a test of mine pinned a transient number instead of the surviving
    invariant, so it is worth naming: the claim being made is "the chain screens the WHOLE
    registry", and `len(S.DETECTORS)` states that claim. A literal states a snapshot, then fails
    for the one reason it should not -- the desk adding detectors.
    """
    import scripts.screen_ict as S
    rng = np.random.default_rng(2)
    px, rows = 100.0, []
    for i in range(20000):
        px = max(1.0, px + rng.normal(0, 0.05))
        rows.append({"t": T0 + i * 15000, "k": "trades",
                     "v": [{"T": T0 + i * 15000, "p": f"{px:.4f}", "v": "0.3"}]})
    _write(tape / "bybit" / "BTCUSDT" / "20260101_00.jsonl.gz", rows)
    assert B.main() == 0
    monkeypatch.setattr(S, "BARS", tmp_path / "bars")
    monkeypatch.setattr(S, "REPORT", tmp_path / "s.json")
    monkeypatch.setattr(S, "HISTORY", tmp_path / "s.jsonl")
    assert S.main() == 0
    rep = json.loads((tmp_path / "s.json").read_text("utf-8"))
    assert rep["screened"] == len(S.DETECTORS), rep.get("state")
    assert rep["screened"] >= 14, "the family may grow, but it must never silently shrink"
    assert rep["bars"] > 100
    assert rep["interesting"] == [], "a random walk must yield no interesting signal"


def test_TWO_SYMBOLS_NEVER_SHARE_A_BAR_SERIES(tape) -> None:
    """THE DEFECT THIS ENDS, MEASURED ON THE LIVE BOX 2026-08-07.

    `build()` pooled every trade from every file into one list and resampled it into a SINGLE
    OHLCV series. An open from one instrument and a close from another shared a bar -- a price
    series of nothing. It also pinned every consumer to "1 symbol", which made the entire
    cross-sectional half of the expression language permanently unmeasurable: `rank`, `zscore` and
    `group_rank` need peers to rank against and correctly refuse without them. The live sweep read
    898,560 candidates and reported 85.7% UNMEASURED for exactly this reason.

    The symbol was never missing -- the recorders encode it in the path and the builder discarded
    it.
    """
    btc = tape / "spot" / "BTCUSDT" / "a.jsonl.gz"
    eth = tape / "spot" / "ETHUSDT" / "a.jsonl.gz"
    _write(btc, [{"t": T0 + i * 1000, "k": "t", "p": "60000", "q": "1"} for i in range(5)])
    _write(eth, [{"t": T0 + i * 1000, "k": "t", "p": "3000", "q": "1"} for i in range(5)])

    grouped = B.group_by_symbol([btc, eth])
    assert sorted(grouped) == ["BTCUSDT", "ETHUSDT"]

    btc_bars, _ = B.build(grouped["BTCUSDT"])
    eth_bars, _ = B.build(grouped["ETHUSDT"])
    assert float(btc_bars["close"].iloc[0]) == 60000.0
    assert float(eth_bars["close"].iloc[0]) == 3000.0

    # and the pooled version is the bug: one series whose high/low span two instruments
    pooled, _ = B.build([btc, eth])
    assert float(pooled["high"].iloc[0]) == 60000.0 and float(pooled["low"].iloc[0]) == 3000.0, (
        "pooling no longer mixes instruments -- if this changed, update the test; if build() was "
        "made symbol-aware internally, this assertion should be inverted rather than deleted")


def test_THE_FILE_BUDGET_IS_PER_SYMBOL_SO_ONE_STREAM_CANNOT_STARVE_THE_REST(tape) -> None:
    """A global `files[-N:]` gives the whole budget to the busiest stream. Measured on the box:
    400 of 32,440 files yielded ONE venue and ONE symbol, which is not a sampling choice anyone
    made -- it is whichever recorder wrote most recently."""
    import inspect

    src = inspect.getsource(B.main)
    assert "group_by_symbol(files)" in src, "main() no longer groups the tape by symbol"
    assert "FILE_BUDGET // max(1, len(per_symbol))" in src, "the budget is global again"


def test_ONE_ARTIFACT_PER_SYMBOL_SO_CONSUMERS_SEE_A_PANEL(tape) -> None:
    """Every consumer globs data/bars/*.parquet and derives the symbol from the filename, so
    per-symbol files are what turns a single series into a cross-section."""
    import inspect

    src = inspect.getsource(B.main)
    assert 'f"{symbol}_{DEFAULT_FREQ}' in src, "the artifact name no longer carries the symbol"


def test_MEMORY_IS_BOUNDED_BY_BUCKETS_NOT_BY_TRADE_COUNT(tape) -> None:
    """OOM-KILLED ON THE LIVE BOX, 2026-08-08. The previous build accumulated every trade for a
    symbol in a Python list of 3-tuples and only then handed it to pandas, which copies it again.
    On a 4GB machine also running the recorders, BARS_FILE_BUDGET=8000 died -- so the budget looked
    like a knob for how far back the desk could see when it was really an unnamed memory ceiling.

    Streaming makes the footprint a function of BUCKETS, not TRADES: a day of 15-minute bars is 96
    rows whatever the trade count. This plants many trades inside very few buckets and asserts the
    output stays tiny, which is the observable consequence of not holding them all.
    """
    p = tape / "spot" / "BUSYUSDT" / "a.jsonl.gz"
    # 20,000 trades landing in a handful of 15-minute buckets
    rows = [{"t": T0 + (i % 3) * 60_000, "k": "t", "p": str(100 + i % 7), "q": "1"}
            for i in range(20_000)]
    _write(p, rows)
    bars, diag = B.build([p])
    assert diag["trades"] == 20_000
    assert len(bars) <= 2, f"20,000 trades produced {len(bars)} bars -- bucketing is wrong"
    assert float(bars["volume"].iloc[0]) > 0


def test_OPEN_AND_CLOSE_DO_NOT_DEPEND_ON_FILE_ORDER(tape) -> None:
    """Each bucket tracks the timestamp of its own first and last trade, so open/close are correct
    even if files arrive out of order or overlap. The previous `.first()`/`.last()` was right only
    because a global sort had already happened -- an aggregation that silently depends on filename
    ordering stays correct until a recorder changes its filename format."""
    early = tape / "spot" / "ORDUSDT" / "b_early.jsonl.gz"
    late = tape / "spot" / "ORDUSDT" / "a_late.jsonl.gz"      # sorts FIRST, contains LATER trades
    _write(early, [{"t": T0, "k": "t", "p": "10", "q": "1"}])
    _write(late, [{"t": T0 + 60_000, "k": "t", "p": "99", "q": "1"}])

    forward, _ = B.build([early, late])
    reverse, _ = B.build([late, early])
    assert float(forward["open"].iloc[0]) == 10.0 and float(forward["close"].iloc[0]) == 99.0
    assert float(reverse["open"].iloc[0]) == 10.0, "open followed file order, not trade time"
    assert float(reverse["close"].iloc[0]) == 99.0, "close followed file order, not trade time"


def test_THE_BUCKET_WIDTH_IS_DERIVED_FROM_THE_FREQUENCY() -> None:
    """A hardcoded 900_000 beside a configurable `freq` is a bug waiting for whoever changes one."""
    assert B._bucket_ms("15min") == 900_000
    assert B._bucket_ms("1h") == 3_600_000


def test_bybit_price_time_shape_is_read_R0378() -> None:
    """THE SHAPE THE RECORDER ACTUALLY WROTE, which this reader dropped 100% of.

    The parser accepted only Bybit's compressed WS labels (p/T/v). Measured 2026-08-12 over six
    sampled partitions: 221,000 nested entries, every one of them price/time/size, and ZERO
    prints parsed -- the entire bybit trade tape (10,814 partitions, 27% of data/moat) was
    invisible to every consumer of this function. It failed silently because an unparseable entry
    is skipped rather than counted, so `screen_orderbook_state` reported NO-INPUT on every bybit
    cell and looked like a data-poor venue rather than a parse bug.
    """
    row = {"t": T0 + 6_461, "k": "trades", "c": "recv",
           "v": [{"execId": "e7b", "symbol": "QTUMUSDT", "price": "0.6429", "size": "209.4",
                  "side": "Sell", "time": str(T0), "isBlockTrade": False}]}
    assert B.trades_from(row) == [(T0, 0.6429, 209.4)]


def test_bybit_print_uses_the_VENUE_stamp_not_our_receipt_R0378() -> None:
    """One `trades` row is a BATCH: up to ~200 prints sharing a single receipt stamp.

    Measured recv-minus-venue on the real tape: depth is a tight +219ms median, but the trade
    batch stamp spans -2,443ms to +88,858ms (p10/p90) because the batch covers a long window.
    Stamping every print in a batch with the batch's receipt would misplace prints by up to 89
    SECONDS on a 60-second bar. The venue stamp is per-print and is the only correct one.
    """
    row = {"t": T0 + 88_858, "k": "trades",
           "v": [{"price": "1.0", "size": "1.0", "time": str(T0)},
                 {"price": "2.0", "size": "1.0", "time": str(T0 + 30_000)}]}
    assert [ms for ms, _p, _q in B.trades_from(row)] == [T0, T0 + 30_000]


def test_compressed_bybit_labels_still_win_when_present_R0378() -> None:
    """Widening the reader must not un-read the shape it already read."""
    row = {"t": T0 + 5, "k": "trades",
           "v": [{"T": T0, "p": "100.5", "v": "0.3", "price": "999.0", "size": "9.9",
                  "time": str(T0 + 77)}]}
    assert B.trades_from(row) == [(T0, 100.5, 0.3)]


def test_a_priceless_bybit_entry_is_still_dropped_R0378() -> None:
    """The widening must not turn a missing price into a zero-price print."""
    assert B.trades_from({"t": T0, "k": "trades", "v": [{"size": "1.0", "time": str(T0)}]}) == []
    assert B.trades_from({"t": T0, "k": "trades",
                          "v": [{"price": "0", "size": "1.0", "time": str(T0)}]}) == []
