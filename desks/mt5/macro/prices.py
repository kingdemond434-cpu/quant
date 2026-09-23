"""THE PRICE INTERFACE -- one narrow protocol, a parquet implementation, and a fake.

WHY A PROTOCOL AND NOT A DIRECT READ. Two reasons, both load-bearing. First, `replay.py` wraps
the reader in a guard that RAISES on any read past the replay clock; that guard is only possible
because every price read in this package goes through one surface. Second, the estimators must be
testable with no data lake and no network, and a fake that satisfies the protocol makes the whole
package exercisable offline -- which is what lets the statistical behaviour be pinned by tests
rather than asserted in a docstring.

THE GRANULARITY PROBLEM, WHICH IS THE REAL CONSTRAINT ON THIS DESK TODAY. `priced.py` asks how
much a price moved between a source publishing and the desk receiving -- typically seconds to a
few minutes. Measured on this tree, `desks/mt5/data/universe/` holds 24 symbols at H1 and 3 at
M15, and no tick tape. An hourly bar CANNOT answer a three-minute question, and the honest
response is `Status.UNMEASURABLE` with the reason, not an hourly move pretending to be a
three-minute one. `bar_span_s` exists so the estimator can check before it asks, and
`coverage()` reports the gap as a named acquisition target: M1 bars or a tick tape for the
instruments the desk most wants to react on.

RETURNS ARE LOG RETURNS, VOL IS TRAILING AND POINT-IN-TIME. `sigma` is computed only from bars
strictly BEFORE the window being measured. Using the event's own bar in the vol estimate would
shrink every event's z toward zero exactly in proportion to how big it was, which is a subtle way
to make big news look ordinary.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

DESK = Path(__file__).resolve().parents[1]
UNIVERSE_DIR = DESK / "data" / "universe"

#: Bars of trailing history required before a sigma is usable. Below this the vol estimate is
#: noise and every z built on it is noise with a decimal point.
MIN_VOL_BARS = 60

__all__ = [
    "MIN_VOL_BARS",
    "FakePriceReader",
    "ParquetPriceReader",
    "PriceReader",
    "Quote",
    "aligned_returns",
    "move_sigma",
]


@dataclass(frozen=True)
class Quote:
    ts: datetime
    price: float


@runtime_checkable
class PriceReader(Protocol):
    """Everything this package is allowed to know about prices."""

    def symbols(self) -> Sequence[str]:
        """Instruments this reader can serve at all."""

    def bar_span_s(self, symbol: str) -> float | None:
        """Seconds per bar for the fastest series available. None when the symbol is unknown.

        The estimators consult this BEFORE asking a question the data cannot answer -- which is
        what turns "we do not have M1 data" from a silently wrong number into a named gap.
        """

    def price_at(self, symbol: str, ts: datetime) -> Quote | None:
        """Last price at or before `ts`. Never interpolates forward: the desk cannot have known
        a price that had not printed yet."""

    def returns_before(self, symbol: str, ts: datetime, n: int) -> Sequence[float]:
        """Up to `n` log returns strictly before `ts`, oldest first. The vol basis."""

    def bars(self, symbol: str, start: datetime | None = None,
             end: datetime | None = None) -> Sequence[Quote]:
        """Quotes in [start, end], ascending. Needed to ALIGN two instruments on a common
        clock: an exposure estimated from two unaligned series measures the calendar, not the
        relationship."""


def _sigma(rets: Sequence[float]) -> float | None:
    vals = [r for r in rets if isinstance(r, int | float) and math.isfinite(r)]
    if len(vals) < MIN_VOL_BARS:
        return None
    m = sum(vals) / len(vals)
    var = sum((r - m) ** 2 for r in vals) / (len(vals) - 1)
    s = math.sqrt(var)
    return s if s > 0 else None


def move_sigma(reader: PriceReader, symbol: str, t0: datetime, t1: datetime,
               *, vol_bars: int = 500) -> tuple[float | None, str]:
    """Signed move from t0 to t1, in units of the trailing per-bar sigma, and why not.

    Returns (value, reason). `reason` is "" on success and names the obstruction otherwise, so
    the caller can put it in the record instead of a zero.
    """
    span = reader.bar_span_s(symbol)
    if span is None:
        return None, f"{symbol}: not served by this reader"
    window = (t1 - t0).total_seconds()
    if window < 0:
        return None, f"{symbol}: window ends before it starts"
    if window < span:
        # The question is finer than the data. Answering anyway would report an hour's move as
        # a three-minute one, which would overstate how much was already priced and could talk
        # the desk out of every trade it should take.
        return None, (f"{symbol}: window {window:.0f}s < bar span {span:.0f}s -- "
                      "UNMEASURABLE at this granularity")
    q0 = reader.price_at(symbol, t0)
    q1 = reader.price_at(symbol, t1)
    if q0 is None or q1 is None or q0.price <= 0 or q1.price <= 0:
        return None, f"{symbol}: no quote at one or both ends"
    if q0.ts == q1.ts:
        return None, f"{symbol}: both ends resolve to the same bar"
    sig = _sigma(reader.returns_before(symbol, t0, vol_bars))
    if sig is None:
        return None, f"{symbol}: fewer than {MIN_VOL_BARS} trailing returns -- sigma UNMEASURED"
    return float(math.log(q1.price / q0.price) / sig), ""


class FakePriceReader:
    """Deterministic in-memory reader. The offline test surface for the whole package.

    `series` maps symbol -> [(ts, price)] ascending. `span_s` maps symbol -> bar span; a symbol
    absent from `span_s` is inferred from its own spacing, which is what a real reader does.
    """

    def __init__(self, series: dict[str, Sequence[tuple[datetime, float]]],
                 span_s: dict[str, float] | None = None) -> None:
        self._series = {s: sorted(v, key=lambda kv: kv[0]) for s, v in series.items()}
        self._span = dict(span_s or {})

    def symbols(self) -> Sequence[str]:
        return sorted(self._series)

    def bar_span_s(self, symbol: str) -> float | None:
        if symbol in self._span:
            return self._span[symbol]
        rows = self._series.get(symbol)
        if not rows or len(rows) < 2:
            return None
        gaps = [(rows[i + 1][0] - rows[i][0]).total_seconds() for i in range(len(rows) - 1)]
        gaps = [g for g in gaps if g > 0]
        if not gaps:
            return None
        return float(sorted(gaps)[len(gaps) // 2])

    def price_at(self, symbol: str, ts: datetime) -> Quote | None:
        rows = self._series.get(symbol)
        if not rows:
            return None
        best: tuple[datetime, float] | None = None
        for t, p in rows:
            if t <= ts:
                best = (t, p)
            else:
                break
        return Quote(best[0], float(best[1])) if best else None

    def returns_before(self, symbol: str, ts: datetime, n: int) -> Sequence[float]:
        rows = [r for r in self._series.get(symbol, ()) if r[0] < ts]
        out: list[float] = []
        for i in range(1, len(rows)):
            p0, p1 = rows[i - 1][1], rows[i][1]
            if p0 > 0 and p1 > 0:
                out.append(math.log(p1 / p0))
        return out[-n:]

    def bars(self, symbol: str, start: datetime | None = None,
             end: datetime | None = None) -> Sequence[Quote]:
        return [Quote(t, float(p)) for t, p in self._series.get(symbol, ())
                if (start is None or t >= start) and (end is None or t <= end)]


class ParquetPriceReader:
    """Reads `desks/mt5/data/universe/<SYM>_<TF>.parquet`, fastest timeframe first.

    Lazy in every direction: pandas is imported on first use and a missing pandas degrades to an
    empty reader rather than an import error, because this package must remain importable on a
    box that has only the ledger. Frames are cached per symbol for the life of the object; the
    files are appended by a separate organ and a long-lived reader would otherwise pin a stale
    view, so the organ constructs a new reader each pass.
    """

    #: Fastest first. The estimator wants the finest granularity available for each symbol.
    TIMEFRAMES: tuple[tuple[str, float], ...] = (
        ("M1", 60.0), ("M5", 300.0), ("M15", 900.0), ("M30", 1800.0),
        ("H1", 3600.0), ("H4", 14400.0), ("D1", 86400.0))

    def __init__(self, base: Path | str | None = None) -> None:
        self.base = Path(base) if base is not None else UNIVERSE_DIR
        self._cache: dict[str, Any] = {}
        self._span: dict[str, float] = {}

    def _load(self, symbol: str) -> Any:
        if symbol in self._cache:
            return self._cache[symbol]
        frame = None
        try:
            import pandas as pd
        except ImportError:
            self._cache[symbol] = None
            return None
        for tf, span in self.TIMEFRAMES:
            path = self.base / f"{symbol}_{tf}.parquet"
            if not path.exists():
                continue
            try:
                df = pd.read_parquet(path, columns=["close"])
            except (OSError, ValueError, ImportError, KeyError):
                continue
            if df.empty:
                continue
            idx = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True, errors="coerce"))
            s = pd.Series(df["close"].to_numpy(dtype=float), index=idx)
            s = s[~s.index.isna()]
            s = s[~s.index.duplicated(keep="last")].sort_index()
            s = s[s.to_numpy() > 0]
            if s.empty:
                continue
            frame = s
            self._span[symbol] = span
            break
        self._cache[symbol] = frame
        return frame

    def symbols(self) -> Sequence[str]:
        if not self.base.exists():
            return ()
        return sorted({p.name.rsplit("_", 1)[0] for p in self.base.glob("*_*.parquet")})

    def bar_span_s(self, symbol: str) -> float | None:
        if self._load(symbol) is None:
            return None
        return self._span.get(symbol)

    def price_at(self, symbol: str, ts: datetime) -> Quote | None:
        s = self._load(symbol)
        if s is None or s.empty:
            return None
        try:
            import pandas as pd
            cut = s.loc[: pd.Timestamp(ts.astimezone(UTC))]
        except (KeyError, ValueError, ImportError):
            return None
        if cut.empty:
            return None
        return Quote(cut.index[-1].to_pydatetime(), float(cut.iloc[-1]))

    def returns_before(self, symbol: str, ts: datetime, n: int) -> Sequence[float]:
        s = self._load(symbol)
        if s is None or s.empty:
            return ()
        try:
            import numpy as np
            import pandas as pd
            cut = s.loc[: pd.Timestamp(ts.astimezone(UTC))]
            if len(cut) < 2:
                return ()
            arr = np.log(cut.to_numpy(dtype=float))
            return [float(x) for x in np.diff(arr)[-n:]]
        except (KeyError, ValueError, ImportError, FloatingPointError):
            return ()

    def bars(self, symbol: str, start: datetime | None = None,
             end: datetime | None = None) -> Sequence[Quote]:
        s = self._load(symbol)
        if s is None or s.empty:
            return ()
        try:
            import pandas as pd
            lo = None if start is None else pd.Timestamp(start.astimezone(UTC))
            hi = None if end is None else pd.Timestamp(end.astimezone(UTC))
            cut = s.loc[lo:hi]
        except (KeyError, ValueError, ImportError):
            return ()
        return [Quote(idx.to_pydatetime(), float(v)) for idx, v in cut.items()]

    def coverage(self) -> dict[str, Any]:
        """What the desk can see, at what granularity, and what that costs the layer.

        The `sub_minute` count is the number that decides whether a priced-versus-unpriced
        estimate is possible for a fast event at all, which is why it is reported rather than
        left to be discovered by a stream of UNMEASURABLE rows.
        """
        by_span: dict[str, list[str]] = {}
        for sym in self.symbols():
            span = self.bar_span_s(sym)
            key = "unavailable" if span is None else f"{int(span)}s"
            by_span.setdefault(key, []).append(sym)
        fast = sum(len(v) for k, v in by_span.items()
                   if k != "unavailable" and int(k[:-1]) <= 60)
        return {
            "base": str(self.base),
            "symbols": sum(len(v) for v in by_span.values()),
            "by_bar_span": {k: sorted(v) for k, v in sorted(by_span.items())},
            "symbols_at_or_below_60s": fast,
            "blind_spot": (
                "NONE" if fast else
                "No sub-minute series on this box. Every priced-versus-unpriced estimate for an "
                "event whose publish-to-receive lag is shorter than the fastest bar returns "
                "UNMEASURABLE, and no such event can earn capital authority. Acquisition "
                "target: M1 bars or a tick tape for the instruments the desk most wants to "
                "react on."),
        }


def aligned_returns(reader: PriceReader, symbols: Sequence[str], *,
                    start: datetime | None = None, end: datetime | None = None,
                    min_obs: int = 100) -> tuple[dict[str, list[float]], list[datetime]]:
    """Log returns for `symbols` on their COMMON timestamps, plus that common index.

    Intersection, not union-with-fill. Forward-filling a slower instrument onto a faster one
    manufactures zero returns at every fill, which drags every measured beta toward zero and
    makes a real exposure look unmeasurable -- the quiet way an expression pipeline goes blind.
    """
    per: dict[str, dict[datetime, float]] = {}
    for sym in symbols:
        rows = reader.bars(sym, start, end)
        if len(rows) < min_obs + 1:
            continue
        per[sym] = {q.ts: q.price for q in rows if q.price > 0}
    if not per:
        return {}, []
    common = set.intersection(*(set(v) for v in per.values())) if per else set()
    index = sorted(common)
    if len(index) < min_obs + 1:
        return {}, index
    out: dict[str, list[float]] = {}
    for sym, prices in per.items():
        rets: list[float] = []
        for i in range(1, len(index)):
            p0, p1 = prices[index[i - 1]], prices[index[i]]
            rets.append(math.log(p1 / p0) if p0 > 0 and p1 > 0 else 0.0)
        out[sym] = rets
    return out, index[1:]


def synthetic_series(start: datetime, n: int, span_s: float, *, p0: float = 100.0,
                     drift: float = 0.0, step: float = 0.001,
                     jump_at: int | None = None,
                     jump: float = 0.0) -> list[tuple[datetime, float]]:
    """A deterministic saw-tooth series for tests. NOT a market model and never used in
    production: it exists so the estimators' arithmetic can be pinned exactly."""
    out: list[tuple[datetime, float]] = []
    price = p0
    for i in range(n):
        price *= math.exp(drift + step * (1 if i % 2 == 0 else -1))
        if jump_at is not None and i == jump_at:
            price *= math.exp(jump)
        out.append((start + timedelta(seconds=span_s * i), price))
    return out
