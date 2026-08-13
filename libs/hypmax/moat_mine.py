"""THE MOAT MINER -- pure, dedicated, maximum-cadence extraction from owned order-book data.

THE DESK'S OWN NUMBERS MADE THIS THE ONLY DEFENSIBLE PLACE TO SPEND EFFORT. Its
information-advantage ranking puts self-recorded order books at 1.03 and the next source at 0.37
-- 5130x the weakest. It sits at 0.4% exploitation with ZERO mechanisms tested. Every other organ
on this desk has been maximised while the one un-replicable asset went unmined.

THIS IS AN EXTRACTOR, NOT A COLLECTOR. run_recorder_bybit already captures depth@1.5s and
trades@10s. Recording is solved; nothing reads it. This turns raw snapshots into the LATENT
SERIES nobody publishes -- the RECONSTRUCT mode from manufacture.py, which is where replication
cost actually lives. A competitor can point a recorder at the same venue tomorrow; they cannot
have OUR timestamps from last month, and they cannot trivially rebuild these derivations.

SEVEN RECONSTRUCTIONS, each chosen because it is invisible in any public feed:

  withdrawal_rate        speed at which resting depth vanishes. The desk's #1 blind spot
                         (M_LIQUIDITY_WITHDRAWAL, advantage 1.03, coverage 0.4%, 0 tested).
  replenishment_halflife how fast a level rebuilds after being taken. Separates real liquidity
                         from quote-stuffing, which no public feed distinguishes.
  book_slope             depth decay away from the touch -- the true shape of available size,
                         not the top-of-book number everyone quotes.
  imbalance              size-weighted bid/ask asymmetry across the visible book.
  microprice_gap         size-weighted fair value minus mid. Where the book thinks price is
                         versus where the tape says it is.
  effective_spread       what a marketable order actually pays, versus the quoted spread.
  resting_stability      churn of the book between snapshots -- how much of the displayed size
                         is real versus flickering.

COVERAGE IS THE PRODUCT, NOT A BYPRODUCT. Every run records which (symbol, mechanism, day) cells
were extracted, so "100% exploration" becomes a measured fraction rather than an aspiration. Any
cell never touched is reported as a HOLE -- and a hole is not a failure, it is the highest-EV
place to point tomorrow's run. The desk cannot currently tell "we mined this and found nothing"
from "we never looked", and those demand opposite responses.

Pure functions over parsed rows. No network, no promotion authority, numpy only.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

__all__ = [
    "DEPTH_KINDS",
    "MECHANISMS",
    "CoverageGrid",
    "MoatCell",
    "book_slope",
    "coverage_report",
    "effective_spread",
    "extract_all",
    "imbalance",
    "microprice_gap",
    "replenishment_halflife",
    "resting_stability",
    "withdrawal_rate",
]

#: mechanism -> (needs, why nobody else has it)
MECHANISMS: dict[str, tuple[str, str]] = {
    "withdrawal_rate": ("depth", "how fast resting size vanishes -- invisible without OUR "
                                 "timestamps; the desk's #1 ranked blind spot"),
    "replenishment_halflife": ("depth", "rebuild speed after a level is taken; separates real "
                                        "liquidity from quote-stuffing"),
    "book_slope": ("depth", "true depth decay away from the touch, not top-of-book"),
    "imbalance": ("depth", "size-weighted asymmetry across the visible book"),
    "microprice_gap": ("depth", "size-weighted fair value vs mid -- where the book disagrees "
                                "with the tape"),
    "effective_spread": ("depth", "what a marketable order actually pays vs the quote"),
    "resting_stability": ("depth", "book churn between snapshots -- displayed size that is real "
                                   "versus flickering"),
}


#: THE DISCRIMINATOR, AND IT IS LOAD-BEARING. The moat is written by three recorders with TWO
#: schemas: run_recorder{,_spot}.py stamp k="d" (30 symbols x {spot,fut}, ~12k hourly files, the
#: 4.4GB that IS the moat) while run_recorder_bybit.py stamps k="depth". A miner that knew only
#: one of them would read ZERO rows from the other and report a clean, confident, empty result --
#: the exact silent-zero failure this module exists to refuse. moat_audit.py has the scar: its
#: first version mis-parsed the mixed stream and declared the whole dataset 82-99% stale.
DEPTH_KINDS = frozenset({"d", "depth"})


def _levels(side: list[Any] | None) -> tuple[np.ndarray, np.ndarray]:
    """Bybit levels arrive as [[price, size], ...] of STRINGS. Bad rows are dropped, never
    coerced to zero -- a zero size is a real and meaningful book state, so inventing one would
    manufacture a withdrawal event that never happened."""
    px, sz = [], []
    for lv in side or ():
        try:
            p, s = float(lv[0]), float(lv[1])
        except (TypeError, ValueError, IndexError):
            continue
        if math.isfinite(p) and math.isfinite(s) and p > 0 and s >= 0:
            px.append(p)
            sz.append(s)
    return np.asarray(px, dtype="float64"), np.asarray(sz, dtype="float64")


def _depth_snaps(rows: list[dict[str, Any]]) -> list[tuple[int, np.ndarray, np.ndarray,
                                                 np.ndarray, np.ndarray]]:
    out = []
    for r in rows:
        if r.get("k") not in DEPTH_KINDS:
            continue
        bp, bs = _levels(r.get("b") or r.get("bids"))
        ap, asz = _levels(r.get("a") or r.get("asks"))
        if not len(bp) or not len(ap):
            continue
        # ORDER IS NOT GUARANTEED BY THE TAPE, and every reconstruction below indexes [0] as the
        # touch. Sorting here rather than trusting the venue costs nothing and removes a whole
        # class of finding that would look like microstructure and be a parse bug.
        bo, ao = np.argsort(-bp), np.argsort(ap)
        bp, bs, ap, asz = bp[bo], bs[bo], ap[ao], asz[ao]
        # CROSSED BOOKS ARE DROPPED, NOT USED. bid >= ask is physically impossible and means a
        # torn or interleaved snapshot; moat_audit.py already measures them per symbol. Feeding
        # one to effective_spread() yields a NEGATIVE cost -- "the venue pays us to trade" -- and
        # that is precisely the kind of artifact that survives review because it is exciting.
        if bp[0] >= ap[0]:
            continue
        out.append((int(r.get("t", 0)), bp, bs, ap, asz))
    out.sort(key=lambda x: x[0])
    return out


def withdrawal_rate(rows: list[dict[str, Any]], *, top_n: int = 10) -> np.ndarray:
    """Per-snapshot fractional DROP in top-N resting size. Positive = liquidity leaving.

    Only the negative changes are kept as withdrawal. Netting additions against removals would
    hide the exact event of interest: size vanishing just before a move is not cancelled out by
    size arriving after it, and treating them as one number is how this signal gets averaged into
    invisibility.
    """
    snaps = _depth_snaps(rows)
    if len(snaps) < 2:
        return np.zeros(0)
    tot = np.array([bs[:top_n].sum() + asz[:top_n].sum() for _, _, bs, _, asz in snaps])
    prev = tot[:-1]
    drop = np.where(prev > 0, (prev - tot[1:]) / np.maximum(prev, 1e-12), 0.0)
    return np.maximum(drop, 0.0)


def replenishment_halflife(rows: list[dict[str, Any]], *, top_n: int = 10) -> float:
    """Median snapshots for depth to recover half of a withdrawal. NaN when nothing withdrew.

    NaN rather than 0.0 on absence, deliberately: zero half-life reads as instant replenishment,
    which is the OPPOSITE of "no withdrawal was observed". A screen fed that would rank a quiet
    book as the most liquid one on the venue.
    """
    snaps = _depth_snaps(rows)
    if len(snaps) < 4:
        return float("nan")
    tot = np.array([bs[:top_n].sum() + asz[:top_n].sum() for _, _, bs, _, asz in snaps])
    lives = []
    for i in range(1, len(tot) - 1):
        if tot[i] >= tot[i - 1] or tot[i - 1] <= 0:
            continue
        target = tot[i] + (tot[i - 1] - tot[i]) / 2.0
        for j in range(i + 1, len(tot)):
            if tot[j] >= target:
                lives.append(j - i)
                break
    return float(np.median(lives)) if lives else float("nan")


def book_slope(rows: list[dict[str, Any]], *, top_n: int = 20) -> np.ndarray:
    """Per-snapshot depth decay: log(cumulative size) regressed on distance from the touch.

    Steep slope = size concentrated at the touch (fragile). Flat = real depth behind the quote.
    The number everyone else trades on is level 1; this is the shape.
    """
    out = []
    for _, bp, bs, ap, asz in _depth_snaps(rows):
        mid = (bp[0] + ap[0]) / 2.0
        px = np.concatenate([bp[:top_n], ap[:top_n]])
        sz = np.concatenate([bs[:top_n], asz[:top_n]])
        d = np.abs(px - mid) / max(mid, 1e-12)
        ok = (d > 0) & (sz > 0)
        if ok.sum() < 4:
            continue
        out.append(float(np.polyfit(d[ok], np.log(sz[ok]), 1)[0]))
    return np.asarray(out, dtype="float64")


def imbalance(rows: list[dict[str, Any]], *, top_n: int = 10) -> np.ndarray:
    """(bid - ask) / (bid + ask) over top-N size. Bounded [-1, 1]."""
    out = []
    for _, _, bs, _, asz in _depth_snaps(rows):
        b, a = bs[:top_n].sum(), asz[:top_n].sum()
        if b + a > 0:
            out.append((b - a) / (b + a))
    return np.asarray(out, dtype="float64")


def microprice_gap(rows: list[dict[str, Any]]) -> np.ndarray:
    """Size-weighted microprice minus mid, in bps. Where the book disagrees with the midpoint."""
    out = []
    for _, bp, bs, ap, asz in _depth_snaps(rows):
        b0, a0, bq, aq = bp[0], ap[0], bs[0], asz[0]
        if bq + aq <= 0:
            continue
        mid = (b0 + a0) / 2.0
        micro = (b0 * aq + a0 * bq) / (bq + aq)     # weighted TOWARD the thinner side
        if mid > 0:
            out.append((micro - mid) / mid * 1e4)
    return np.asarray(out, dtype="float64")


def effective_spread(rows: list[dict[str, Any]], *, notional: float = 500.0) -> np.ndarray:
    """Bps a marketable order of `notional` actually pays, walking the book. NaN if it cannot fill.

    The quoted spread is what the venue advertises; this is what the desk would be charged. The
    gap between them is a cost the desk currently does not model, and unmodelled costs are how a
    backtested edge dies on contact.
    """
    out = []
    for _, bp, _bs, ap, asz in _depth_snaps(rows):
        mid = (bp[0] + ap[0]) / 2.0
        if mid <= 0:
            continue
        need, qty = notional, 0.0
        for p, s in zip(ap, asz, strict=False):
            take = min(need, p * s)        # notional consumed AT this level
            qty += take / p                # ...which buys this much base
            need -= take
            if need <= 0:
                break
        if need > 0 or qty <= 0:
            # The visible book cannot fill the order. NaN, never the best price seen: reporting a
            # partial walk as the cost of a full one understates exactly the trades that matter.
            out.append(float("nan"))
            continue
        vwap = notional / qty
        out.append((vwap / mid - 1.0) * 1e4)
    return np.asarray(out, dtype="float64")


def resting_stability(rows: list[dict[str, Any]], *, top_n: int = 10) -> np.ndarray:
    """1 - churn: fraction of top-N SIZE that persisted between consecutive snapshots.

    High = real resting liquidity. Low = a book being repainted, where displayed size is not
    size you can trade against.
    """
    snaps = _depth_snaps(rows)
    out = []
    for i in range(1, len(snaps)):
        _, bp0, bs0, ap0, as0 = snaps[i - 1]
        _, bp1, bs1, ap1, as1 = snaps[i]
        prev = {**dict(zip(bp0[:top_n], bs0[:top_n], strict=False)),
                **dict(zip(ap0[:top_n], as0[:top_n], strict=False))}
        cur = {**dict(zip(bp1[:top_n], bs1[:top_n], strict=False)),
               **dict(zip(ap1[:top_n], as1[:top_n], strict=False))}
        tot = sum(cur.values())
        if tot <= 0:
            continue
        kept = sum(min(v, prev.get(k, 0.0)) for k, v in cur.items())
        out.append(kept / tot)
    return np.asarray(out, dtype="float64")


#: name -> reconstruction. Typed explicitly because the values have DIFFERENT return types --
#: `replenishment_halflife` is a scalar and the rest are series -- and an inferred join of those
#: signatures is `object`, which makes every call site uncheckable.
_EXTRACTORS: dict[str, Callable[[list[dict[str, Any]]], float | np.ndarray]] = {
    "withdrawal_rate": withdrawal_rate,
    "replenishment_halflife": replenishment_halflife,
    "book_slope": book_slope,
    "imbalance": imbalance,
    "microprice_gap": microprice_gap,
    "effective_spread": effective_spread,
    "resting_stability": resting_stability,
}


def _summary(v: float | np.ndarray) -> dict[str, Any]:
    """Summarise a series without letting NaNs silently become zeros."""
    if isinstance(v, float):
        # n=0 ON NaN, and this is the same rule as the grid's. A scalar reconstruction that could
        # not measure anything must not report n=1 -- that would mark its coverage cell FILLED and
        # retire the cell from the frontier on the strength of a measurement never taken.
        if not math.isfinite(v):
            return {"n": 0, "note": "not measurable from these rows -- NOT zero, unmeasured"}
        return {"value": round(v, 6), "n": 1}
    a = np.asarray(v, dtype="float64")
    ok = a[np.isfinite(a)]
    if ok.size == 0:
        return {"n": 0, "note": "no finite observations -- NOT zero, unmeasured"}
    return {"n": int(ok.size), "n_dropped": int(a.size - ok.size),
            "mean": round(float(ok.mean()), 6), "std": round(float(ok.std()), 6),
            "p50": round(float(np.median(ok)), 6),
            "p95": round(float(np.percentile(ok, 95)), 6),
            "max": round(float(ok.max()), 6)}


def extract_all(sym: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Run every reconstruction over one symbol's rows. Missing data yields an EMPTY cell, never
    a fabricated zero -- a coverage hole and a measured zero are different facts."""
    n_depth = sum(1 for r in rows if r.get("k") in DEPTH_KINDS)
    out: dict[str, Any] = {"symbol": sym, "depth_snapshots": n_depth, "mechanisms": {}}
    for name, fn in _EXTRACTORS.items():
        try:
            out["mechanisms"][name] = _summary(fn(rows))
        except Exception as e:
            out["mechanisms"][name] = {"n": 0, "error": f"{type(e).__name__}: {e}"[:120]}
    return out


@dataclass(frozen=True)
class MoatCell:
    """One (symbol, mechanism, day) unit of the exploration grid."""

    symbol: str
    mechanism: str
    day: str


@dataclass
class CoverageGrid:
    """THE PRODUCT. 100% exploration is a measured fraction, not an aspiration.

    A cell never touched is a HOLE, and a hole is not a failure -- it is the highest-EV place to
    point tomorrow's run, because the desk cannot otherwise tell "mined and empty" from "never
    looked". Those demand opposite responses and the difference is the whole reason to track this.
    """

    filled: set[Any] = field(default_factory=set)

    def mark(self, sym: str, mech: str, day: str, *, n_obs: int) -> None:
        # ZERO OBSERVATIONS IS NOT COVERAGE. A run that produced nothing must leave the cell open,
        # or the grid fills up with cells that were visited and learned nothing, and 100% would
        # mean "we ran everywhere" rather than "we measured everywhere".
        if n_obs > 0:
            self.filled.add((sym, mech, day))

    def report(self, symbols: list[str], days: list[str],
               mechanisms: list[str] | None = None,
               pairs: list[tuple[str, str]] | None = None) -> dict[str, Any]:
        """`pairs` is the list of (symbol, day) units that EXIST on tape. Without it the grid is
        the cartesian product symbols x days -- which counts (symbol, day) combinations that were
        never recorded (listed later, delisted earlier, recorder started mid-window) as HOLES.
        Measured 2026-08-12: 11,004 of 11,004 reported holes were such phantoms while every cell
        with tape was 7/7 measured -- coverage pinned at 53.05% 'STANDING-STILL' with nothing any
        miner could do. A cell with no files is not unexplored edge; it is a listing-window fact
        (the L1.46 class: a venue limitation must never read as a desk defect). Phantoms stay
        COUNTED and published -- excluding them from the denominator is honest only while they
        remain visible."""
        mechs = mechanisms or list(MECHANISMS)
        if pairs is None:
            universe = [(s, d) for s in symbols for d in days]
            phantom = None
        else:
            universe = sorted(set(pairs))
            phantom = len(symbols) * len(days) - len(universe)
        total = len(universe) * len(mechs)
        holes = [MoatCell(s, m, d) for (s, d) in universe for m in mechs
                 if (s, m, d) not in self.filled]
        pct = 0.0 if total == 0 else (total - len(holes)) / total
        by_mech: dict[str, int] = dict.fromkeys(mechs, 0)
        for h in holes:
            by_mech[h.mechanism] += 1
        out = {
            "cells_total": total,
            "cells_filled": total - len(holes),
            "coverage_pct": round(pct * 100, 2),
            "holes": len(holes),
            "holes_by_mechanism": {k: v for k, v in sorted(by_mech.items(), key=lambda x: -x[1])
                                   if v},
            "next_targets": [f"{h.symbol}/{h.mechanism}/{h.day}" for h in holes[:12]],
            "note": ("a hole is the highest-EV place to point tomorrow's run -- it is the "
                     "difference between 'mined and empty' and 'never looked', and those "
                     "demand opposite responses"),
        }
        if phantom is not None:
            out["phantom_pairs_excluded"] = phantom
            out["denominator"] = (
                "cells that exist on tape (recorded (symbol, day) pairs x mechanisms). A pair "
                "with no files cannot be mined at any effort level and is a listing-window "
                "fact, not unexplored edge -- it is counted here, never as a hole.")
        return out


def coverage_report(results: list[dict[str, Any]], symbols: list[str],
                    days: list[str],
                    pairs: list[tuple[str, str]] | None = None) -> dict[str, Any]:
    """Build the grid from a set of extraction results. Pass `pairs` (the (symbol, day) units
    that exist on tape) whenever the caller knows them -- see CoverageGrid.report for why the
    cartesian fallback overstates holes."""
    g = CoverageGrid()
    for r in results:
        day = str(r.get("day", ""))
        for mech, s in (r.get("mechanisms") or {}).items():
            g.mark(str(r.get("symbol", "")), mech, day, n_obs=int(s.get("n", 0)))
    return g.report(symbols, days, pairs=pairs)
