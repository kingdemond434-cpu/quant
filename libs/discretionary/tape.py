"""THE MOAT TAPE, READ -- signed trade flow and volume-at-price, for H4 and H5.

WHY THIS EXISTS AND WHY IT DID NOT. `DISCRETIONARY_PLAYBOOK_PREREGISTRATION.md` marks H4 (Auction
Market Theory / Volume Profile) and H5 (order flow / CVD) as **BLOCKED: recorder bringup
(operator)**. That was true when it was written on 2026-08-04.

IT IS NO LONGER TRUE, AND NOTHING NOTICED. `run_recorder_spot` and `run_recorder` have been taping
every aggTrade -- price, quantity, and `m` (isBuyerMaker), which IS the trade's sign -- plus top-20
depth, into hourly gzip partitions under `data/moat/`. Three recorder units are enabled on the box.
So the exact inputs those two hypotheses were waiting for have been accumulating for weeks while
both stayed marked blocked, and the block was a stale note rather than a missing capability.

That is the desk's own defect class from the other side: not an unwired capability, but UNREAD
DATA -- collected daily, at cost, consumed by nothing, with a document explaining why it could not
be consumed. Nobody re-reads a BLOCKED label to ask whether it is still true.

**SIGNED FLOW IS THE THING OHLCV CANNOT GIVE.** A candle body is not delta: a bar can close green
on net selling and red on net buying, and the folk method of inferring flow from candle direction
has no evidence behind it. `m=True` means the BUYER was the maker, so the aggressor was a SELLER --
that mapping is the whole of CVD and getting it backwards inverts every signal built on it.

**VOLUME AT PRICE IS AN ESTIMATE OF THE AUCTION, NOT THE AUCTION.** aggTrades bucket to a price
grid, giving POC/VAH/VAL. That is what Market Profile needs and it is genuinely different from
OHLCV, but it is trade prints rather than the full book, and the module says so rather than
implying a depth-derived profile.
"""

from __future__ import annotations

import gzip
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

__all__ = [
    "MAX_TAPE_AGE_H",
    "MOAT_ROOTS",
    "TapeBar",
    "TapeProfile",
    "cvd",
    "load_trades",
    "tape_bars",
    "volume_profile",
]

#: Where the recorders write. Both are read: a symbol taped on one venue and not the other must
#: not read as "no tape", which is the absence-as-verdict defect on the collection layer.
MOAT_ROOTS: tuple[str, ...] = ("data/moat/spot", "data/moat/perp", "data/moat/fut")

#: Value-area fraction. 70% is Market Profile's own definition, not a desk choice -- H4 is
#: registered as "POC/VAH/VAL reversion", and those letters mean the standard construction.
VALUE_AREA = 0.70

#: Price buckets across the session's range. Enough that the POC is a price rather than a region,
#: few enough that a thin tape does not scatter into singleton bins.
_BINS = 50

#: How old the newest print may be before the profile describes a PAST auction rather than the
#: live one. The recorders write hourly partitions continuously, so a gap this size means a unit
#: stopped -- and fading the value area of a session that ended yesterday is not the registered
#: hypothesis, it is a different and untested one wearing its name.
MAX_TAPE_AGE_H = 3.0

#: Tape bar width. The recorders partition hourly, so this is the finest grid on which a full
#: window is guaranteed complete rather than half-written.
_BAR_MINUTES = 60


@dataclass(frozen=True)
class TapeBar:
    """One time bucket of the tape: OHLC from prints, plus the SIGNED volume over the same bucket.

    THE DELTA IS THE POINT. OHLC is available from any candle source; `delta` is not available from
    any of them at any resolution, and it is the only column here that no other input can supply.
    """

    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    delta: float


@dataclass(frozen=True)
class TapeProfile:
    """Volume-at-price for one window, the signed flow over the same trades, and the bar series
    both were built from. All from ONE pass, so they can never describe different windows.

    **THE WINDOW IS CARRIED, NOT ASSUMED.** The first version handed rules a scalar `cvd` over the
    last 24 hourly partitions, and H5 compared it against a ten-bar extreme taken from a DAILY
    candle frame -- a ten-DAY price move judged against one day of flow. Both numbers were correct
    and the comparison between them meant nothing. Carrying `bars` makes the window a property of
    the object rather than of whichever caller happened to load it.
    """

    poc: float
    vah: float
    val: float
    cvd: float
    n_trades: int
    total_volume: float
    why: str
    first_ts: int = 0
    last_ts: int = 0
    last_price: float = 0.0
    bars: tuple[TapeBar, ...] = ()

    def age_h(self, now_ms: int | None = None) -> float:
        """Hours since the newest print. Refuses a stale auction; never interpolates one."""
        if not self.last_ts:
            return float("inf")
        now = int(now_ms if now_ms is not None else time.time() * 1000)
        return max(0.0, (now - self.last_ts) / 3_600_000.0)

    def fresh(self, now_ms: int | None = None, *, max_age_h: float = MAX_TAPE_AGE_H) -> bool:
        return self.age_h(now_ms) <= max_age_h

    def cum_delta(self) -> tuple[float, ...]:
        """Cumulative signed volume, bar by bar. The series a DIVERGENCE needs -- the scalar `cvd`
        is only its last element, and a level is not a divergence."""
        out: list[float] = []
        acc = 0.0
        for bar in self.bars:
            acc += bar.delta
            out.append(acc)
        return tuple(out)

    def as_row(self) -> dict[str, Any]:
        # BARS ARE SUMMARISED, NOT DUMPED. This row lands in a daily artifact; a thousand OHLC
        # rows per symbol per day would bury the verdict it exists to publish.
        return {"poc": round(self.poc, 8), "vah": round(self.vah, 8), "val": round(self.val, 8),
                "cvd": round(self.cvd, 4), "n_trades": self.n_trades,
                "total_volume": round(self.total_volume, 4), "n_bars": len(self.bars),
                "first_ts": self.first_ts, "last_ts": self.last_ts,
                "last_price": round(self.last_price, 8), "age_h": round(self.age_h(), 2),
                "why": self.why}


def _partitions(symbol: str, roots: tuple[str, ...] = MOAT_ROOTS) -> list[Path]:
    out: list[Path] = []
    for r in roots:
        d = Path(r) / symbol
        if d.is_dir():
            out.extend(sorted(d.glob("*.jsonl.gz")))
    return out


def load_trades(symbol: str, *, max_files: int = 24,
                roots: tuple[str, ...] = MOAT_ROOTS) -> list[tuple[int, float, float, bool]]:
    """Recent aggTrades as (ts_ms, price, qty, is_buyer_maker), oldest first.

    `max_files` bounds the read: partitions are hourly, so 24 is the last day. Unbounded reads on a
    tape that grows forever turn a daily cycle into an outage the first time nobody is watching.

    A CORRUPT LINE IS SKIPPED, NEVER FATAL. A truncated final partition is normal -- the recorder
    may be mid-write -- and losing a day's tape to one bad byte would be a self-inflicted outage.
    """
    files = _partitions(symbol, roots)[-max_files:]
    out: list[tuple[int, float, float, bool]] = []
    for f in files:
        try:
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                for line in fh:
                    if '"k": "t"' not in line and '"k":"t"' not in line:
                        continue          # depth row; cheap string test before the json parse
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if r.get("k") != "t":
                        continue
                    try:
                        out.append((int(r["t"]), float(r["p"]), float(r["q"]), bool(r["m"])))
                    except (KeyError, TypeError, ValueError):
                        continue
        except (OSError, EOFError):
            continue                       # partition mid-write or truncated: skip, do not fail
    out.sort(key=lambda t: t[0])
    return out


def cvd(trades: list[tuple[int, float, float, bool]]) -> float:
    """Cumulative volume delta: aggressor-buy volume minus aggressor-sell volume.

    `m` IS THE MAKER FLAG AND THE SIGN IS ITS INVERSE. `m=True` means the buyer was the MAKER, so
    the trade was lifted by a SELLER and counts negative. Getting this backwards inverts every
    divergence signal built on top and would look like a working strategy with the sign flipped.
    """
    return float(sum((-q if m else q) for _, _, q, m in trades))


def tape_bars(trades: list[tuple[int, float, float, bool]], *,
              minutes: int = _BAR_MINUTES) -> list[TapeBar]:
    """Bucket the tape into OHLC + SIGNED volume bars. Empty list on an empty tape.

    **PRICE AND FLOW MUST SHARE A GRID OR NEITHER CAN DIVERGE FROM THE OTHER.** The whole content
    of H5 is "price made a new extreme and signed flow did not", which is a statement about two
    series over ONE window. Reading the extreme off a daily candle frame and the flow off a
    one-day tape compares a ten-day move to a one-day imbalance: both numbers correct, the
    comparison meaningless. Bucketing here means the two can only ever be measured together.

    ONLY COMPLETE BUCKETS ARE RETURNED. The newest bucket is almost always mid-formation, and a
    partial bar's delta is a fraction of an hour's flow presented as an hour's -- which biases the
    most recent point, the only one any rule acts on.
    """
    if not trades:
        return []
    width = max(1, int(minutes)) * 60_000
    buckets: dict[int, list[tuple[float, float, bool]]] = {}
    for ts, p, q, m in trades:
        buckets.setdefault((ts // width) * width, []).append((p, q, m))
    keys = sorted(buckets)
    if len(keys) > 1:
        keys = keys[:-1]                    # drop the in-progress bucket
    out: list[TapeBar] = []
    for k in keys:
        rows = buckets[k]
        prices = [p for p, _, _ in rows]
        out.append(TapeBar(
            ts=k, open=prices[0], high=max(prices), low=min(prices), close=prices[-1],
            volume=float(sum(q for _, q, _ in rows)),
            delta=float(sum((-q if m else q) for _, q, m in rows))))
    return out


def volume_profile(trades: list[tuple[int, float, float, bool]], *,
                   bins: int = _BINS, value_area: float = VALUE_AREA,
                   bar_minutes: int = _BAR_MINUTES) -> TapeProfile | None:
    """POC / VAH / VAL from trade prints, with the CVD over the same trades.

    Returns None on an empty or degenerate tape -- NOT a zero profile. A POC of 0.0 would be a
    price the market never traded at, and every comparison against it would be nonsense that
    looked numeric.

    THE VALUE AREA GROWS FROM THE POC OUTWARD, taking whichever adjacent bin holds more volume,
    until 70% is enclosed. That is Market Profile's construction; a percentile of the price
    distribution is a different object that happens to produce similar numbers on quiet days.
    """
    # THE PROFILE AND THE BAR SERIES ARE TRIMMED TO THE SAME SPAN, so `cvd` is exactly the last
    # element of `cum_delta()` and can never drift from it. Without this the scalar covers the
    # in-progress bucket that `tape_bars` drops, and the two disagree by a partial hour of flow --
    # a small discrepancy whose only symptom is a rule and its own audit row telling different
    # stories about the same window.
    bars = tuple(tape_bars(trades, minutes=bar_minutes))
    if not bars:
        return None
    span_end = bars[-1].ts + max(1, int(bar_minutes)) * 60_000
    trades = [t for t in trades if t[0] < span_end]
    if len(trades) < 20:
        return None
    px = np.array([p for _, p, _, _ in trades], dtype="float64")
    qty = np.array([q for _, _, q, _ in trades], dtype="float64")
    lo, hi = float(px.min()), float(px.max())
    if not np.isfinite(lo) or hi <= lo or qty.sum() <= 0:
        return None

    edges = np.linspace(lo, hi, bins + 1)
    idx = np.clip(np.digitize(px, edges) - 1, 0, bins - 1)
    vol = np.zeros(bins, dtype="float64")
    np.add.at(vol, idx, qty)
    centres = (edges[:-1] + edges[1:]) / 2.0

    poc_i = int(np.argmax(vol))
    target = value_area * float(vol.sum())
    lo_i = hi_i = poc_i
    acc = float(vol[poc_i])
    while acc < target and (lo_i > 0 or hi_i < bins - 1):
        below = float(vol[lo_i - 1]) if lo_i > 0 else -1.0
        above = float(vol[hi_i + 1]) if hi_i < bins - 1 else -1.0
        if above >= below:
            hi_i += 1
            acc += max(above, 0.0)
        else:
            lo_i -= 1
            acc += max(below, 0.0)

    return TapeProfile(
        poc=float(centres[poc_i]), vah=float(centres[hi_i]), val=float(centres[lo_i]),
        cvd=cvd(trades), n_trades=len(trades), total_volume=float(qty.sum()),
        first_ts=int(trades[0][0]), last_ts=int(trades[-1][0]), last_price=float(bars[-1].close),
        bars=bars,
        why=(f"{len(trades):,} aggTrades over [{lo:.6g}, {hi:.6g}], {bins} price bins, "
             f"{value_area:.0%} value area grown outward from the POC, {len(bars)} complete "
             f"{bar_minutes}m bars. Trade prints, not depth: this estimates the auction, it is "
             "not the book"))
