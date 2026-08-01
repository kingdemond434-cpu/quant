"""Candidates on the RECORDED ORDER BOOK -- the one asset this desk owns and the crowd does not.

WHY THIS FILE AND NOT MORE INDICATORS. On 2026-08-01 the desk ran 129 textbook mechanisms
(Bollinger, RSI, Donchian, CMF, golden cross...) across 10 liquid crypto pairs on daily bars
through the repaired gauntlet. Result: 0 survivors, and the reason was not the gate -- the best
in-sample Sharpe of 1.75 delivered an out-of-sample Sharpe of **0.08**, and across all 129 the
maximum OOS Sharpe was 0.100 with a mean of -0.001. Public indicators on the most liquid pairs
in the market at default parameters are picked clean, which is exactly what should have been
expected and was written down as the prior beforehand.

That result is the argument for this file. The desk's edge was never supposed to be indicators.
It is the tape: 20-level depth polled every ~4s and aggregate trades with aggressor side,
recorded continuously to data/moat/ since 2026-07-21. Nobody backtests order-book imbalance over
a two-year history because that history is not purchasable at retail -- pre-recorder L2 does not
exist free at any venue, which is why an unrecorded day cannot be bought back at any price.

THE ASYMMETRY THAT MAKES THIS WORTH THE SLOTS. A mechanism computable from free daily bars has
been tested by everyone with a laptop; its prior of survival is the 0/129 above. A mechanism that
requires 20-level depth at 4-second cadence has been tested by the people who pay for the data,
which is a far smaller population and one that is not optimising for a £5k book. The edge is not
that these features are cleverer. It is that the search over them is far less crowded.

RECORD FORMATS, both supported because the desk runs two recorders:
    binance (data/moat/fut, data/moat/spot)
        depth  {"t": ms, "k": "d", "u": id, "b": [[px, qty] x20], "a": [[px, qty] x20]}
        trade  {"t": ms, "k": "t", "a": id, "p": px, "q": qty, "m": buyer_is_maker}
    bybit   (data/moat/bybit)
        depth  {"t": ms, "k": "depth", "b": [...], "a": [...]}
        trade  {"t": ms, "k": "trades", "v": [...]}
        meta   {"t": ms, "k": "meta", "fr": funding, "oi": open_interest, "mp": mark}

`m` is the load-bearing field and it is easy to get backwards: it is TRUE when the BUYER was the
maker, which means the aggressor was a SELLER. Signed flow is therefore -1 when m is true. Invert
that and every flow feature changes sign, the backtest still runs, and the result is confidently
wrong -- so it is asserted in the tests rather than trusted.
"""
from __future__ import annotations

import gzip
import json
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any, NamedTuple

import numpy as np

MOAT = Path("data/moat")


def read_partition(path: Path) -> Iterator[dict[str, Any]]:
    """Stream one hourly gzip-jsonl partition, skipping unparseable lines.

    A truncated final line is normal -- the recorder is killed mid-write on every restart -- so a
    partial row is expected and must never abort the read. Dropping the tail of one hour is a gap;
    refusing to read the hour is a lost day."""
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except (OSError, EOFError):
        return


def partitions(symbol: str, venue: str = "fut") -> list[Path]:
    d = MOAT / venue / symbol
    return sorted(d.glob("*.jsonl.gz")) if d.is_dir() else []


class BookState(NamedTuple):
    t_ms: int
    mid: float
    micro: float
    spread_bps: float
    obi: float
    """Order-book imbalance at the touch, in [-1, 1]. Positive = more size bid than offered."""
    obi_deep: float
    """Same, summed over the whole recorded depth -- the crowd cannot compute this without L2."""
    depth_bid: float
    depth_ask: float
    slope: float
    """How fast size accumulates away from the touch. A flat book fills badly."""


def _levels(raw: Any) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for lv in raw or []:
        try:
            out.append((float(lv[0]), float(lv[1])))
        except (TypeError, ValueError, IndexError):
            continue
    return out


def book_state(rec: dict[str, Any]) -> BookState | None:
    """One depth record -> the microstructure primitives. None when the book is crossed or empty.

    A crossed book (bid >= ask) is a venue artifact of stitching two snapshot halves, not a real
    arbitrage. Returning None rather than a huge negative spread stops one bad record from
    dominating every downstream mean.
    """
    bids, asks = _levels(rec.get("b")), _levels(rec.get("a"))
    if not bids or not asks:
        return None
    bp, bq = bids[0]
    ap, aq = asks[0]
    if bp <= 0 or ap <= 0 or bp >= ap or (bq + aq) <= 0:
        return None
    mid = 0.5 * (bp + ap)
    # microprice: the size-weighted touch. Weighted TOWARD the thin side, because that is the
    # side that gets taken -- this is the standard result and the reason micro-mid predicts.
    micro = (bp * aq + ap * bq) / (bq + aq)
    db = sum(q for _, q in bids)
    da = sum(q for _, q in asks)
    obi_deep = (db - da) / (db + da) if (db + da) > 0 else 0.0
    # slope: size per basis point of distance from the touch, averaged over both sides
    def _slope(levels: Sequence[tuple[float, float]], ref: float, sign: float) -> float:
        num = 0.0
        for px, q in levels:
            dist_bps = sign * (px - ref) / ref * 1e4
            if dist_bps > 0:
                num += q / dist_bps
        return num
    slope = 0.5 * (_slope(bids, mid, -1.0) + _slope(asks, mid, 1.0))
    return BookState(int(rec.get("t", 0)), mid, micro, (ap - bp) / mid * 1e4,
                     (bq - aq) / (bq + aq), obi_deep, db, da, slope)


def signed_flow(rec: dict[str, Any]) -> float:
    """Aggressor-signed size for one trade record. NEGATIVE when the buyer was the maker.

    `m=True` means the resting order was a BID, so the aggressor hit it -- a SELL. Getting this
    backwards silently inverts every flow feature, so it is pinned by test."""
    try:
        q = float(rec.get("q", 0.0))
    except (TypeError, ValueError):
        return 0.0
    return -q if bool(rec.get("m")) else q


class Bar(NamedTuple):
    """One resampled interval of microstructure state, aligned so features are causal."""
    t_ms: int
    mid: float
    obi: float
    obi_deep: float
    spread_bps: float
    slope: float
    tfi: float
    """Trade-flow imbalance: signed aggressor volume over the bar, normalised by total volume."""
    volume: float
    depth_total: float
    n_books: int


def resample(records: Iterator[dict[str, Any]], *, ms: int = 60_000) -> list[Bar]:
    """Fold a record stream into fixed-interval bars.

    Book features are AVERAGED over the interval rather than sampled at its close: a single
    snapshot of an order book is dominated by whichever quote happened to be resting at that
    instant, and the average is the quantity with signal in it.
    """
    buckets: dict[int, dict[str, Any]] = {}
    for rec in records:
        k = rec.get("k")
        try:
            t = int(rec.get("t", 0))
        except (TypeError, ValueError):
            continue
        if t <= 0:
            continue
        slot = t // ms
        b = buckets.setdefault(slot, {"obi": [], "obi_deep": [], "spr": [], "slope": [],
                                      "mid": [], "depth": [], "flow": 0.0, "vol": 0.0})
        if k in ("d", "depth"):
            st = book_state(rec)
            if st is not None:
                b["obi"].append(st.obi)
                b["obi_deep"].append(st.obi_deep)
                b["spr"].append(st.spread_bps)
                b["slope"].append(st.slope)
                b["mid"].append(st.mid)
                b["depth"].append(st.depth_bid + st.depth_ask)
        elif k == "t":
            f = signed_flow(rec)
            b["flow"] += f
            b["vol"] += abs(f)
        elif k == "trades":
            for tr in rec.get("v") or []:
                try:
                    q = float(tr.get("size") or tr.get("v") or 0.0)
                    side = str(tr.get("side", "")).lower()
                except (TypeError, ValueError, AttributeError):
                    continue
                f = q if side.startswith("b") else -q
                b["flow"] += f
                b["vol"] += abs(f)

    out: list[Bar] = []
    for slot in sorted(buckets):
        b = buckets[slot]
        if not b["mid"]:
            continue
        vol = float(b["vol"])
        out.append(Bar(
            t_ms=slot * ms, mid=float(np.mean(b["mid"])), obi=float(np.mean(b["obi"])),
            obi_deep=float(np.mean(b["obi_deep"])), spread_bps=float(np.mean(b["spr"])),
            slope=float(np.mean(b["slope"])),
            tfi=(float(b["flow"]) / vol if vol > 0 else 0.0),
            volume=vol, depth_total=float(np.mean(b["depth"])), n_books=len(b["mid"])))
    return out


# --------------------------------------------------------------------------------------------
# CANDIDATES. Each returns a position per bar, decided from bar i and earning bar i+1's move.
# --------------------------------------------------------------------------------------------

def _z(x: np.ndarray, n: int) -> np.ndarray:
    """Trailing z-score against the window BEFORE i, so the current bar is never in its own mean.

    ZERO-VARIANCE WINDOWS ARE THE INTERESTING CASE, not an edge case to skip. The first version
    returned NaN whenever the trailing window was flat, which made liquidity_withdrawal blind to
    a perfectly stable book that suddenly empties -- the most extreme instance of the very event
    it exists to detect. A flat window followed by a move is an unboundedly surprising
    observation, so it scores as one.
    """
    out = np.full(len(x), np.nan)
    for i in range(n, len(x)):
        w = x[i - n:i]
        s = float(np.std(w, ddof=1))
        m = float(np.mean(w))
        if s > 0:
            out[i] = (x[i] - m) / s
        elif x[i] != m:
            out[i] = np.inf if x[i] > m else -np.inf
        else:
            out[i] = 0.0
    return out


def obi_pressure(bars: Sequence[Bar], *, n: int = 60, entry: float = 1.5) -> np.ndarray:
    """Follow deep book imbalance. The most-documented microstructure predictor there is, and it
    is unavailable to anyone without recorded depth."""
    x = np.array([b.obi_deep for b in bars], dtype="float64")
    z = _z(x, n)
    return np.where(np.isnan(z), 0.0, np.where(z > entry, 1.0, np.where(z < -entry, -1.0, 0.0)))


def flow_momentum(bars: Sequence[Bar], *, n: int = 30, entry: float = 1.5) -> np.ndarray:
    """Aggressor flow persists at short horizon: informed orders are worked, not dumped."""
    x = np.array([b.tfi for b in bars], dtype="float64")
    z = _z(x, n)
    return np.where(np.isnan(z), 0.0, np.where(z > entry, 1.0, np.where(z < -entry, -1.0, 0.0)))


def liquidity_withdrawal(bars: Sequence[Bar], *, n: int = 60, drop: float = -2.0) -> np.ndarray:
    """M_LIQUIDITY_WITHDRAWAL: makers pulling depth ahead of a move.

    A sudden collapse in total resting size, with the spread widening, is market makers stepping
    away because they believe the next print is informed. The desk flagged this as a priority
    construction and it was blocked on exactly this data. Flat -- not short -- because the signal
    is about ADVERSE SELECTION RISK rather than direction: the right response to 'the book has
    gone' is to stop trading, not to guess which way.
    """
    d = _z(np.array([b.depth_total for b in bars], dtype="float64"), n)
    s = _z(np.array([b.spread_bps for b in bars], dtype="float64"), n)
    withdrawn = (~np.isnan(d)) & (~np.isnan(s)) & (d < drop) & (s > 1.0)
    return np.where(withdrawn, 0.0, 1.0)


def microprice_reversion(bars: Sequence[Bar], *, n: int = 60, entry: float = 2.0) -> np.ndarray:
    """Fade a mid that has run away from the size-weighted touch.

    micro - mid is the book's own estimate of where the next trade prints. When mid diverges from
    it the quote is stale relative to resting size, and the gap tends to close.
    """
    obi = np.array([b.obi for b in bars], dtype="float64")
    spr = np.array([b.spread_bps for b in bars], dtype="float64")
    dev = obi * spr * 0.5                       # micro-mid in bps, from touch imbalance
    z = _z(dev, n)
    return np.where(np.isnan(z), 0.0, np.where(z > entry, -1.0, np.where(z < -entry, 1.0, 0.0)))


def bar_returns(pos: np.ndarray, bars: Sequence[Bar], *,
                cost_bps: float = 1.0) -> np.ndarray:
    """Position at bar i earns bar i+1's mid-to-mid move, less cost on every change.

    Cost is in BASIS POINTS because these are intrabar horizons where the spread, not the fee,
    dominates -- and at 1-minute bars a strategy that flips constantly pays the spread every time.
    """
    mid = np.array([b.mid for b in bars], dtype="float64")
    p = np.nan_to_num(np.asarray(pos, dtype="float64"))
    if len(mid) < 2:
        return np.zeros(0)
    r = np.diff(mid) / mid[:-1]
    turn = np.abs(np.diff(np.concatenate([[0.0], p[:-1]])))
    return np.asarray(p[:-1] * r - turn * cost_bps * 1e-4)


#: Explicitly typed: mypy infers the dict's value type from the FIRST entry, so an unannotated
#: registry of same-shaped functions rejects every later one on a keyword-name mismatch.
CANDIDATES: dict[str, Callable[..., np.ndarray]] = {
    "obi_pressure": obi_pressure,
    "flow_momentum": flow_momentum,
    "liquidity_withdrawal": liquidity_withdrawal,
    "microprice_reversion": microprice_reversion,
}
