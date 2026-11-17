"""NATURAL-HAZARD SHOCK -- trade the bars after a public hazard notice (novel-style lane N3).

THE MECHANISM, AND WHO PAYS. A large earthquake near Japan, Taiwan or Chile, or a storm cone over
the Gulf of Mexico, is a physical shock to a NAMED supply chain or balance sheet: Japanese
insurers and corporates repatriate (yen bid, Nikkei offered), Chilean copper mines and ports halt
(copper bid), Gulf platforms and refineries shut in (crude and gas bid, the peso offered). The
payer is whoever holds the exposure and must hedge or liquidate in the hours after the notice,
before the damage is measured. The two claims are kept as separate modes:

    drift   the shock is information: trade the declared direction (`prior_side`, times the
            `side` polarity) from the first bar that OPENS at or after the notice.
    fade    the shock is an over-reaction: after `fade_after` bars, trade against the move the
            market made since the notice.

POINT IN TIME. Events are read from the lake frame `natural_hazard_events` (written by
`research/geoint_hazards.py`): `event_id, kind, region, magnitude, event_time, available_time`.
`available_time` is the PUBLICATION instant (a USGS origin time plus a late-biased publication
slack; an NHC cone's own advisory issuance time), never the origin. Entry is the first bar that
opens at or after it, converted into the bars' broker frame by `libs.research.bar_clock` when
`clock="utc"`; an unconvertible stamp is dropped, never used raw.

REFUSES (returns []) without the frame, the kind, or a measurable ATR. Absence is UNMEASURED.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1
from mt5desk.family_generic import _hold_bars

from libs.research.bar_clock import to_bar_time

SERIES_DIR = Path(__file__).resolve().parents[1] / "data" / "lake" / "series"
SERIES_ID = "natural_hazard_events"
KINDS = ("quake_jp", "quake_tw", "quake_cl", "storm_gulf")
MODES = ("drift", "fade")
CLOCKS = ("bars", "utc")

_CACHE: dict[str, Any] = {}


def load_events(root: Path | None = None) -> pd.DataFrame | None:
    base = root or SERIES_DIR
    p = next((base / f"{SERIES_ID}{s}" for s in (".parquet", ".csv")
              if (base / f"{SERIES_ID}{s}").exists()), None)
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
    if df is None or df.empty or not {"kind", "available_time"}.issubset(df.columns):
        return None
    df = df.copy()
    df["available_time"] = pd.to_datetime(df["available_time"], errors="coerce", utc=True)
    df["magnitude"] = pd.to_numeric(df.get("magnitude"), errors="coerce")
    df = df.dropna(subset=["available_time"])
    _CACHE.update({"key": key, "df": df})
    return df


def _to_bars(ts: pd.Timestamp, clock: str) -> pd.Timestamp | None:
    if clock == "bars":
        return ts
    moved, _status, _why = to_bar_time(ts.to_pydatetime())
    return None if moved is None else pd.Timestamp(moved)


def family_hazard_shock(
    bars: pd.DataFrame,
    side: int = 1,
    *,
    symbol: str,
    kind: str,
    prior_side: int = 1,
    mode: str = "drift",
    min_magnitude: float = 0.0,
    hold_bars: int = 24,
    fade_after: int = 6,
    stop_atr: float = 2.0,
    rr: float = 1.5,
    atr_n: int = 20,
    clock: str = "bars",
    series_root: Path | None = None,
) -> list[Signal]:
    """Signals after each public notice of `kind`. `symbol` names the instrument for the
    caller's records; the event set is the kind's, not the symbol's."""
    if (kind not in KINDS or mode not in MODES or clock not in CLOCKS
            or int(side) not in (1, -1) or int(prior_side) not in (1, -1)):
        return []
    if not str(symbol or "").strip() or not isinstance(bars, pd.DataFrame) or bars.empty:
        return []
    ev = load_events(series_root)
    if ev is None:
        return []
    mine = ev[ev["kind"] == kind]
    if min_magnitude > 0:
        mine = mine[mine["magnitude"].fillna(0.0) >= float(min_magnitude)]
    if mine.empty:
        return []
    d = _h1(bars)
    if len(d) < int(atr_n) + 3:
        return []
    # NO TIMEFRAME RESTRICTION: `hold_bars` and `fade_after` are HOURS of market time (H1 bars),
    # turned into this chart's own bars, so the rule means the same thing on every rung.
    hold = _hold_bars(max(1, int(hold_bars)), d)
    fade = _hold_bars(max(1, int(fade_after)), d)
    index = pd.DatetimeIndex(d.index)
    atr = _atr(d, int(atr_n)).to_numpy()
    close = d["close"].astype(float).to_numpy()
    polarity = 1 if int(side) > 0 else -1
    signals: list[Signal] = []
    busy_until = -1
    for ts in sorted(mine["available_time"]):
        at = _to_bars(pd.Timestamp(ts), clock)
        if at is None:
            continue
        pos = int(index.searchsorted(at, side="left"))     # first bar OPENING at/after notice
        if pos < int(atr_n) or pos >= len(d) - 1 or pos <= busy_until:
            continue
        if mode == "drift":
            i, direction = pos, polarity * int(prior_side)
        else:
            i = pos + fade
            if i >= len(d) - 1:
                continue
            move = float(close[i] - close[pos - 1])
            if not np.isfinite(move) or move == 0.0:
                continue
            direction = polarity * (-1 if move > 0 else 1)
        a = float(atr[i])
        px = float(close[i])
        if not np.isfinite(a) or a <= 0 or not np.isfinite(px):
            continue
        risk = float(stop_atr) * a
        signals.append(Signal(time=index[i], side=direction, stop=px - direction * risk,
                              target=px + direction * risk * float(rr),
                              ttl_bars=hold,
                              tag=f"hazard_shock.{kind}.{mode}", trigger=None, wait_bars=1))
        busy_until = i + hold
    return signals
