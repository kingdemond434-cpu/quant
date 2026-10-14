"""FX OPTION-EXPIRY STRIKE PINNING INTO THE 10:00 NEW YORK CUT, THEN RELEASE (novel-style lane N1).

THE MECHANISM, AND WHO PAYS. Vanilla FX options on the majors expire at the 10:00 New York cut.
When a LARGE notional sits at one strike for today's expiry and spot trades near it, the dealers
who are long that gamma re-hedge against every move away from the strike (sell rallies above it,
buy dips below it), and the dealers short it are pulled the same way by their own stop-outs; spot
gravitates toward the strike into the cut. At 10:00 New York the options die and so does the
hedge, so the price is RELEASED: whatever was being held at the strike is free to move.

    pin       on an expiry day, `lead_bars` before the cut, the largest strike for that expiry
              whose PIT notional is at least `min_notional_usd` and which sits within
              `proximity_atr` ATRs of the close: trade TOWARD it, target the strike, exit by the
              cut (`ttl` ends on the cut bar).
    release   on the first bar that closes AFTER the cut, when the close at the cut was within
              `proximity_atr` ATRs of such a strike (pinned): trade the direction the price leaves
              the strike in, `rr` times the stop.

`side` is a POLARITY (+1 tests the claim, -1 its mirror), as in `family_forced_flow`.

POINT IN TIME. The strike ladder is read from the lake frame `fx_option_expiry_strikes`
(written by `research/novel_style_lanes.py` from public FX-option prints), one row per print:
`pair, expiry_date, strike, notional_usd, available_time`. A print counts only when its
`available_time` is at or before the decision instant MINUS `lag_minutes`; the notional at a
strike is the sum of the prints known by then. The cut is computed by rule (10:00 in
America/New_York through `zoneinfo`, so the UTC hour moves with US daylight saving and the
expiry date alone fixes it). `clock="utc"` moves the cut into the bars' broker frame through
`libs.research.bar_clock`; an unconvertible cut is DROPPED, never used raw.

REFUSES (returns []) without the frame, the pair, a measurable ATR or a strike that qualifies.
That absence is UNMEASURED, never a reason to fall back to a price pattern.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1, bar_minutes

from libs.research.bar_clock import to_bar_time

SERIES_DIR = Path(__file__).resolve().parents[1] / "data" / "lake" / "series"
#: The lake frame's bare id (`<SERIES_DIR>/<SERIES_ID>.csv|.parquet`).
SERIES_ID = "fx_option_expiry_strikes"
#: The four majors the lane is declared on. A pair absent here is not refused by the family
#: (the frame decides), but the organ mints cells only on these.
PAIRS: tuple[str, ...] = ("EURUSD", "USDJPY", "AUDUSD", "GBPUSD")
NY = ZoneInfo("America/New_York")
CUT_LOCAL = time(10, 0)
MODES = ("pin", "release")
CLOCKS = ("bars", "utc")

_CACHE: dict[str, Any] = {}


def cut_utc(expiry: date) -> datetime:
    """10:00 New York on the expiry date, in UTC (14:00 in EDT, 15:00 in EST)."""
    return datetime.combine(expiry, CUT_LOCAL, tzinfo=NY).astimezone(UTC)


def series_path(root: Path | None = None) -> Path | None:
    base = root or SERIES_DIR
    for suffix in (".parquet", ".csv"):
        p = base / f"{SERIES_ID}{suffix}"
        if p.exists():
            return p
    return None


def load_prints(root: Path | None = None) -> pd.DataFrame | None:
    """The strike prints frame, or None (UNMEASURED). Cached on (path, mtime, size)."""
    p = series_path(root)
    if p is None:
        return None
    st = p.stat()
    key = f"{p}|{st.st_mtime_ns}|{st.st_size}"
    if _CACHE.get("key") == key:
        cached = _CACHE.get("df")
        return cached if isinstance(cached, pd.DataFrame) else None
    try:
        df = pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p)
    except Exception:
        return None
    need = {"pair", "expiry_date", "strike", "notional_usd", "available_time"}
    if df is None or df.empty or not need.issubset(df.columns):
        return None
    df = df.copy()
    df["pair"] = df["pair"].astype(str).str.upper()
    df["expiry_date"] = pd.to_datetime(df["expiry_date"], errors="coerce").dt.date
    df["strike"] = pd.to_numeric(df["strike"], errors="coerce")
    df["notional_usd"] = pd.to_numeric(df["notional_usd"], errors="coerce")
    df["available_time"] = pd.to_datetime(df["available_time"], errors="coerce", utc=True)
    df = df.dropna(subset=["expiry_date", "strike", "notional_usd", "available_time"])
    _CACHE.update({"key": key, "df": df})
    return df


def strikes_known(prints: pd.DataFrame, pair: str, expiry: date, asof: datetime
                  ) -> dict[float, float]:
    """Notional (USD) per strike for one pair and expiry, from the prints known at `asof`."""
    m = ((prints["pair"] == pair) & (prints["expiry_date"] == expiry)
         & (prints["available_time"] <= pd.Timestamp(asof)))
    if not bool(m.any()):
        return {}
    g = prints.loc[m].groupby("strike")["notional_usd"].sum()
    return {float(k): float(v) for k, v in g.items()}


def _to_bars(ts: datetime, clock: str) -> pd.Timestamp | None:
    if clock == "bars":
        return pd.Timestamp(ts)
    moved, _status, _why = to_bar_time(ts)
    return None if moved is None else pd.Timestamp(moved)


def _pick(strikes: dict[float, float], px: float, band: float, floor: float) -> float | None:
    """The largest qualifying strike within `band` of `px`; ties go to the nearer strike."""
    best: tuple[float, float, float] | None = None
    for k, n in strikes.items():
        if n < floor or abs(k - px) > band:
            continue
        cand = (n, -abs(k - px), k)
        if best is None or cand > best:
            best = cand
    return None if best is None else best[2]


def family_fx_expiry_pin(
    bars: pd.DataFrame,
    side: int = 1,
    *,
    symbol: str,
    mode: str = "pin",
    proximity_atr: float = 0.5,
    min_notional_usd: float = 1.0e9,
    lead_bars: int = 3,
    release_bars: int = 6,
    lag_minutes: int = 120,
    stop_atr: float = 1.0,
    rr: float = 1.5,
    atr_n: int = 14,
    clock: str = "bars",
    series_root: Path | None = None,
) -> list[Signal]:
    """Signals into (pin) or out of (release) the 10:00 New York cut around a large strike.

    `symbol` is REQUIRED: the strike ladder is per pair, and a caller who does not name the pair
    cannot be told which strikes bear on these bars.
    """
    if mode not in MODES or clock not in CLOCKS or int(side) not in (1, -1):
        return []
    pair = str(symbol or "").strip().upper()
    if not pair or not isinstance(bars, pd.DataFrame) or bars.empty:
        return []
    prints = load_prints(series_root)
    if prints is None:
        return []
    mine = prints[prints["pair"] == pair]
    if mine.empty:
        return []
    d = _h1(bars)
    if len(d) < int(atr_n) + 3:
        return []
    index = pd.DatetimeIndex(d.index)
    step = int(bar_minutes(d) or 60)
    atr = _atr(d, int(atr_n)).to_numpy()
    close = d["close"].astype(float).to_numpy()
    polarity = 1 if int(side) > 0 else -1
    lo, hi = index[0].date() - timedelta(days=1), index[-1].date() + timedelta(days=1)
    signals: list[Signal] = []
    for expiry in sorted({e for e in mine["expiry_date"] if lo <= e <= hi}):
        if expiry.weekday() >= 5:
            continue
        cut = cut_utc(expiry)
        cut_bar = _to_bars(cut, clock)
        if cut_bar is None:
            continue                         # an unconvertible cut is dropped, never used raw
        # Bars are labelled by their OPEN: the bar holding the cut minute opens at `c`.
        c = int(index.searchsorted(cut_bar, side="right")) - 1
        if c < int(atr_n) or c >= len(d) - 1:
            continue
        if mode == "pin":
            i = c - max(1, int(lead_bars))
            if i < int(atr_n):
                continue
            # The decision instant, read EARLY on purpose (bar i's open, one bar before its
            # close): a print is admitted only if it was known before that, so the join can
            # only lose information, never see it early.
            decided = cut - timedelta(minutes=step * (c - i))
        else:
            i = c + 1                        # the first bar that closes after the cut
            if i >= len(d) - 1:
                continue
            decided = cut + timedelta(minutes=step)
        asof = decided - timedelta(minutes=max(0, int(lag_minutes)))
        known = strikes_known(mine, pair, expiry, asof)
        a = float(atr[i])
        if not known or not np.isfinite(a) or a <= 0:
            continue
        band = float(proximity_atr) * a
        if mode == "pin":
            px = float(close[i])
            k = _pick(known, px, band, float(min_notional_usd))
            if k is None or k == px:
                continue
            direction = polarity * (1 if k > px else -1)
            target = k if polarity > 0 else px + direction * abs(k - px)
            signals.append(Signal(
                time=index[i], side=direction, stop=px - direction * float(stop_atr) * a,
                target=target, ttl_bars=max(1, c - i), tag="fx_expiry_pin.pin",
                trigger=None, wait_bars=1))
        else:
            pinned_px = float(close[c])
            k = _pick(known, pinned_px, band, float(min_notional_usd))
            px = float(close[i])
            if k is None or px == k:
                continue
            direction = polarity * (1 if px > k else -1)
            risk = float(stop_atr) * a
            signals.append(Signal(
                time=index[i], side=direction, stop=px - direction * risk,
                target=px + direction * risk * float(rr), ttl_bars=max(1, int(release_bars)),
                tag="fx_expiry_pin.release", trigger=None, wait_bars=1))
    return signals
