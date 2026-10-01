"""ANALYST REVISION DRIFT and CROSS-MARKET ANALYST LEAD -- the executors for the Alpha Capture
substitute (`desks/mt5/research/alpha_capture.py`).

THE MECHANISM. A broker upgrade, a target raise, a company guidance raise or a TDnet forecast
revision is information that diffuses slowly: investors under-react to it (the payer), because
attention is finite and the arbitrageur who would close the gap faces limits -- capital, the
short-sale cost on a downgrade, the benchmark that stops a long-only book leaving an index weight
(the constraint). So the instrument drifts in the direction of the revision after the desk could
have read it. `analyst_revision_drift` trades that on the instrument the view is ABOUT.
`analyst_cross_market_lead` trades it on an instrument ANOTHER market's view is about -- Korean
semiconductor research read into the US semis and USDKRW, Chinese research breadth into CHINAH,
HK50 and USDCNH, TDnet forecast revisions into JPN225 and USDJPY -- where the slow venue is the
payer and the language barrier is part of the constraint.

THE FAMILY LOADS ITS OWN EVIDENCE, AND ONLY THE POINT-IN-TIME PART OF IT. The events come from the
append-only store the organ writes, read through `libs.research.analyst_views.observations` with
basis `first_seen`: an event is placed at `max(first_seen_at, published_at + precision lag)` and a
backfilled view (first seen long after its publication) is never an event here. The stamp is UTC;
the bar index is broker time, so it is converted with `libs.research.bar_clock` and an
unconvertible stamp is DROPPED, never used raw -- the same rule `family_event_reaction` enforces.
Entry is the first bar that OPENS at or after the knowable instant.

`symbol` AND `source` ARE REQUIRED KEYWORD ARGUMENTS on purpose: the sweep cannot call this family
blind (`orthogonal_sweep._unsuppliable` names them), because which store rows belong to which
instrument is the proposer's measured evidence, not a searched parameter.

`side` IS THE MEASURED SIGN. +1 follows the revision (the drift hypothesis), -1 fades it; the
proposer donates the sign its tracker measured, and for a cross-market lead -- where no sign is
declared anywhere -- that is the only place a sign comes from.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.engine import Signal
from mt5desk.families import _atr, _h1

from libs.research import analyst_views as av

#: The organ's store. An environment override exists for tests and for a box with a moved tree.
STORE = Path(__file__).resolve().parents[1] / "data" / "alpha_capture" / "analyst_views.jsonl"
_CACHE: dict[str, Any] = {}


def store_path() -> Path:
    raw = os.environ.get("QUANT_ALPHA_CAPTURE_STORE", "")
    return Path(raw) if raw else STORE


def _rows(path: Path) -> list[dict[str, Any]]:
    """The store's rows, cached on (path, mtime, size) so a sweep of cells reads it once."""
    try:
        st = path.stat()
    except OSError:
        return []
    key = f"{path}|{st.st_mtime_ns}|{st.st_size}"
    if _CACHE.get("key") != key:
        _CACHE["key"] = key
        _CACHE["rows"] = av.AnalystViewStore(path).rows()
    rows = _CACHE.get("rows")
    return rows if isinstance(rows, list) else []


def event_times(symbol: str, source: str, relation: str, lead: str = "", *,
                path: Path | None = None) -> list[tuple[pd.Timestamp, int]]:
    """(knowable instant in the BARS' clock, net direction) per daily-netted observation."""
    obs, _ = av.observations(_rows(path or store_path()), basis="first_seen")
    mine = [o for o in obs if o.target == symbol and o.source == source
            and o.relation == relation and (not lead or o.lead == lead)]
    clock = av.bar_clock()
    out: list[tuple[pd.Timestamp, int]] = []
    for o in av.daily_net(mine):
        moved = clock(o.at)
        if moved is None:
            continue                      # an unplaceable stamp is dropped, never used raw
        out.append((pd.Timestamp(moved), o.direction))
    out.sort(key=lambda x: x[0])
    return out


def _signals(df: pd.DataFrame, events: list[tuple[pd.Timestamp, int]], *, side: int,
             hold_days: int, atr_n: int, stop_atr: float, rr: float, tag: str) -> list[Signal]:
    if not events or side not in (1, -1):
        return []
    d = _h1(df)
    if len(d) < atr_n + 4:
        return []
    index = pd.DatetimeIndex(d.index)
    per_day = max(1, round(float(pd.Series(index.normalize()).value_counts().median())))
    ttl = int(max(1, hold_days) * per_day)
    atr = _atr(d, atr_n).to_numpy()
    close = d["close"].astype(float).to_numpy()
    signals: list[Signal] = []
    armed_from = -1
    for ts, direction in events:
        pos = int(index.searchsorted(ts, side="left"))   # first bar OPENING at/after the news
        if pos <= armed_from or pos >= len(d) - 1 or pos < atr_n:
            continue
        a = float(atr[pos])
        if not np.isfinite(a) or a <= 0:
            continue
        s = int(side * direction)
        px = float(close[pos])
        signals.append(Signal(time=index[pos], side=s, stop=px - s * stop_atr * a,
                              target=px + s * stop_atr * a * rr, ttl_bars=ttl, tag=tag,
                              trigger=None, wait_bars=1))
        armed_from = pos + ttl // 2
    return signals


def family_analyst_revision_drift(
    df: pd.DataFrame,
    *,
    symbol: str,
    source: str,
    side: int = 1,
    hold_days: int = 5,
    atr_n: int = 20,
    stop_atr: float = 3.0,
    rr: float = 1.5,
) -> list[Signal]:
    """Follow (side=+1) or fade (-1) the net direction of the day's first-seen views ABOUT
    `symbol` from `source`, holding about `hold_days` trading days. No store, no signals."""
    ev = event_times(symbol, source, "direct")
    return _signals(df, ev, side=side, hold_days=hold_days, atr_n=atr_n, stop_atr=stop_atr,
                    rr=rr, tag="analyst_revision_drift")


def family_analyst_cross_market_lead(
    df: pd.DataFrame,
    *,
    symbol: str,
    source: str,
    lead: str,
    side: int = 1,
    hold_days: int = 5,
    atr_n: int = 20,
    stop_atr: float = 3.0,
    rr: float = 1.5,
) -> list[Signal]:
    """Trade `symbol` on the net direction of another market's first-seen views in lead group
    `lead` (`analyst_views.LEAD_TARGETS`); `side` is the tracker's MEASURED sign."""
    if lead not in av.LEAD_TARGETS or symbol not in av.LEAD_TARGETS[lead]:
        return []
    ev = event_times(symbol, source, "lead", lead)
    return _signals(df, ev, side=side, hold_days=hold_days, atr_n=atr_n, stop_atr=stop_atr,
                    rr=rr, tag="analyst_cross_market_lead")
