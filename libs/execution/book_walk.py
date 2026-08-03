"""EXACT FILLS FROM RECORDED DEPTH -- impact MEASURED on our own tape, not assumed from a formula.

WHAT THIS REPLACES, AND A CORRECTION I OWE. I rated execution modelling "near ceiling, blocked on
book depth nobody has recorded". That was wrong, and wrong in the most embarrassing direction: the
desk has 8.2GB of self-recorded 15-second L2 depth across three venues, and `asymmetry_ledger.py`
grades it the single EXCLUSIVE asset the desk owns. The data was never missing. It was unused.

`libs/signal_engine/market_impact_forecaster.py` is a square-root participation model with
literature coefficients. That is a reasonable prior and it is not a measurement: it says what
impact USUALLY looks like for a generic instrument, on a desk that holds the actual book for its
actual pairs. Walking the recorded book is arithmetic on ground truth and it dominates any
parametric guess for the instruments the desk trades.

THREE THINGS THIS MAKES POSSIBLE THAT THE PARAMETRIC MODEL CANNOT:

  EXACT SLIPPAGE FOR A GIVEN SIZE. Consume levels until the order is filled and report the
  volume-weighted price. No coefficient, no calibration, no assumption -- just what the book on
  the other side would have paid.
  CAPACITY. The size at which impact exceeds the edge is a property of THIS book on THIS pair,
  and it is the number that decides how much capital a strategy can carry. A parametric model
  cannot produce it because it does not know the depth.
  QUEUE-AWARE FILL PROBABILITY. This closes an open question the ICT work left explicitly
  unresolved. `run_ict_strategy.py` reports two bounds -- filled at the level (+14.9bp/trade on
  controls) and filled at the close (-15.6bp) -- and says the truth depends on book depth the desk
  has not measured. It has. Given resting size ahead of us at a level and the trade volume that
  actually arrived, the fill probability is measurable rather than bracketed.

THE CROSSED-BOOK AND ORDERING GUARDS ARE COPIED FROM moat_mine DELIBERATELY. Venue order is not
guaranteed and a torn snapshot with bid >= ask yields NEGATIVE slippage -- "the venue pays us to
trade" -- which is exactly the kind of artifact that survives review because it is exciting.

Pure numpy. No I/O, no network.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from libs.backtest.queue_fill import maker_fill

__all__ = [
    "DEPTH_KINDS",
    "BookSide",
    "FillResult",
    "book_from_row",
    "calibrate_impact",
    "capacity_at_impact",
    "fill_probability",
    "queue_ahead_at",
    "walk_book",
]

#: Both recorder schemas. Binance stamps depth `k="d"` with `b`/`a`; Bybit uses `k="depth"`.
#: Reading one and not the other returns clean, plausible, half-empty results over the other
#: venue's archive -- the bug that made moat_mine blind to 4.4GB until DEPTH_KINDS existed.
DEPTH_KINDS = frozenset({"d", "depth"})


@dataclass(frozen=True)
class BookSide:
    """One side of a book, sorted best-first, with prices and resting sizes aligned."""

    price: np.ndarray
    size: np.ndarray

    def __len__(self) -> int:
        return int(self.price.size)

    @property
    def notional(self) -> float:
        return float((self.price * self.size).sum())


@dataclass(frozen=True)
class FillResult:
    """What an order would actually have paid against this book."""

    filled: float                 # base units actually filled
    vwap: float                   # volume-weighted fill price
    slippage_bps: float           # vs the touch, signed so positive is always a COST
    levels_consumed: int
    exhausted: bool               # the book ran out before the order did
    touch: float

    @property
    def complete(self) -> bool:
        return not self.exhausted


def _levels(raw) -> tuple[np.ndarray, np.ndarray]:
    """[[price, size], ...] as strings or floats -> aligned float arrays."""
    if not raw:
        return np.empty(0), np.empty(0)
    px, sz = [], []
    for lvl in raw:
        try:
            px.append(float(lvl[0]))
            sz.append(float(lvl[1]))
        except (TypeError, ValueError, IndexError):
            continue           # a malformed level is skipped, never guessed at
    return np.asarray(px, dtype="float64"), np.asarray(sz, dtype="float64")


def book_from_row(row: dict) -> tuple[BookSide, BookSide] | None:
    """(bids, asks) from a recorded depth row, or None if the snapshot is unusable.

    Sorting is done here rather than trusted from the venue: every consumer indexes [0] as the
    touch, and a tape that is merely usually sorted produces a finding that looks like
    microstructure and is a parse bug. A crossed book (bid >= ask) is DROPPED -- it is physically
    impossible, means a torn snapshot, and would yield negative slippage.
    """
    if row.get("k") not in DEPTH_KINDS:
        return None
    bp, bs = _levels(row.get("b") or row.get("bids"))
    ap, asz = _levels(row.get("a") or row.get("asks"))
    if not bp.size or not ap.size:
        return None
    bo, ao = np.argsort(-bp), np.argsort(ap)
    bp, bs, ap, asz = bp[bo], bs[bo], ap[ao], asz[ao]
    if bp[0] >= ap[0]:
        return None
    return BookSide(bp, bs), BookSide(ap, asz)


def walk_book(side: BookSide, qty: float, *, is_buy: bool) -> FillResult:
    """Consume levels until `qty` is filled. THE measurement, with no model in it.

    `side` is the side being TAKEN FROM -- asks for a buy, bids for a sell. Slippage is signed so
    that positive always means a cost, in both directions; a sign convention that flips with
    direction is how a short book ends up looking profitable to trade into.
    """
    if qty <= 0:
        raise ValueError("qty must be positive")
    if len(side) == 0:
        raise ValueError("empty book side -- no fill is possible and reporting one would invent it")

    touch = float(side.price[0])
    take = np.minimum(side.size, np.maximum(qty - np.concatenate(([0.0],
                                                                 np.cumsum(side.size)[:-1])), 0.0))
    take = np.clip(take, 0.0, None)
    filled = float(take.sum())
    if filled <= 0:
        raise ValueError("book has zero resting size")
    vwap = float((side.price * take).sum() / filled)
    # Positive = cost, whichever way we are going.
    slip = (vwap - touch) / touch if is_buy else (touch - vwap) / touch
    return FillResult(filled=filled, vwap=vwap, slippage_bps=float(slip * 10_000.0),
                      levels_consumed=int((take > 0).sum()),
                      exhausted=filled + 1e-12 < qty, touch=touch)


def capacity_at_impact(side: BookSide, *, max_bps: float, is_buy: bool = True,
                       steps: int = 64) -> float:
    """Largest order whose slippage stays under `max_bps`. THE number that sizes a strategy.

    This is what a parametric model cannot give: capacity is a property of THIS book on THIS pair
    at THIS moment, and it is the constraint that decides how much capital an edge can carry. An
    alpha with a 30bp edge and 5bp of capacity at the size it needs is not an alpha.

    Bisection on the exact walk rather than inversion of a fitted curve -- the walk is ground
    truth and inverting a fit would reintroduce the assumption this module exists to remove.
    """
    total = float(side.size.sum())
    if total <= 0:
        return 0.0
    if walk_book(side, total, is_buy=is_buy).slippage_bps <= max_bps:
        return total                       # the whole visible book is inside the budget
    lo, hi = 0.0, total
    for _ in range(steps):
        mid = (lo + hi) / 2.0
        if mid <= 0:
            break
        if walk_book(side, mid, is_buy=is_buy).slippage_bps <= max_bps:
            lo = mid
        else:
            hi = mid
    return lo


def calibrate_impact(books: Sequence[BookSide], sizes: Sequence[float], *,
                     is_buy: bool = True) -> dict[str, float]:
    """Fit slippage_bps = k * sqrt(participation) on the desk's OWN books.

    The square-root law is the standard functional form and is kept; what changes is that `k` is
    MEASURED on the instruments the desk actually trades rather than taken from a paper about
    large-cap equities. Participation is order size over visible resting size, which is the
    quantity the book itself defines.

    Returns the coefficient, the fit quality, and the sample size -- and r2 is returned so a bad
    fit is visible rather than a coefficient being used because it was produced.
    """
    part, slip = [], []
    for b, q in zip(books, sizes, strict=False):
        total = float(b.size.sum())
        if total <= 0 or q <= 0:
            continue
        try:
            r = walk_book(b, min(q, total), is_buy=is_buy)
        except ValueError:
            continue
        part.append(min(q, total) / total)
        slip.append(r.slippage_bps)
    if len(part) < 8:
        return {"k": float("nan"), "r2": float("nan"), "n": float(len(part)),
                "note": "fewer than 8 usable snapshots -- a coefficient fitted here is noise"}
    x = np.sqrt(np.asarray(part, dtype="float64"))
    y = np.asarray(slip, dtype="float64")
    k = float((x @ y) / (x @ x)) if float(x @ x) > 0 else float("nan")
    resid = y - k * x
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - float((resid ** 2).sum()) / ss_tot if ss_tot > 0 else float("nan")
    return {"k": k, "r2": r2, "n": float(len(part))}


def queue_ahead_at(side: BookSide, level_price: float, *, is_bid: bool) -> float:
    """Resting size at or better than `level_price` -- the queue a passive order joins BEHIND.

    This is the input the desk's existing maker-fill model was missing. `libs/backtest/queue_fill`
    models queue priority, latency and partial fills properly; what it could not know was how much
    size actually sits in front, because that is a fact about the recorded book. This supplies it.
    """
    if len(side) == 0:
        return 0.0
    better = side.price >= level_price if is_bid else side.price <= level_price
    return float(side.size[better].sum())


def fill_probability(depth_ahead: float, traded_volume: float, *,
                     own_size: float = 0.0) -> float:
    """Fraction of a resting order filled, given size queued ahead and volume that arrived.

    THIS DELEGATES, AND AN EARLIER VERSION DID NOT -- WHICH WAS A DEFECT OF MINE. I wrote a
    standalone probability here without checking whether the desk already modelled passive fills.
    It did: `libs/backtest/queue_fill.maker_fill` is a port of the hftbacktest mechanism and is
    strictly richer, carrying feed latency and partial fills that my version simply lacked. Two
    implementations of the same mechanism is worse than either alone, because the one that gets
    used is whichever the caller happened to import.

    So the mechanism lives in one place and this is the thin adapter that feeds it from a recorded
    book. It remains an UPPER BOUND on realised fills: book replenishment, cancellations shrinking
    the queue and price-level jumps are documented as unmodelled there, and all push the true
    figure down.
    """
    if depth_ahead < 0 or traded_volume < 0 or own_size < 0:
        raise ValueError("sizes cannot be negative")
    size = own_size if own_size > 0 else 1.0
    if depth_ahead <= 0 and own_size <= 0:
        return 1.0
    return float(maker_fill(order_size=size, queue_ahead=depth_ahead,
                            through_volume=traded_volume).fill_fraction)
