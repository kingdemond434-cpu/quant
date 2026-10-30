"""ALT-DATA RELEASE DRIFT -- the event lane's executor for a free alt-data release about a share.

THE MECHANISM. `research/alt_proxies.py` publishes free substitutes for paid alt data (Korea's
20-day exports, TSA throughput, GDELT country tone ...) as point-in-time lake series, and its
equity hand-off (`data/digests/alt_proxies_equity_handoff.json`) names the share CFDs each series
bears on with a DECLARED prior sign (Korean semiconductor exports -> NVIDIA, AMD, Micron, TSMC;
airport throughput -> Booking, Airbnb, Uber, Boeing). A release is a dated public datum about the
name's demand that the market reads with a lag: the payer is the holder who does not read a
Korean customs release or a TSA daily count, and the constraint is attention plus the language
and venue barrier. So the share drifts in the direction of the release's SURPRISE (its own
`surprise_z`, sign times the declared prior) after the desk could have read it.

WHY THIS IS THE EVENT LANE, NOT A STATISTICAL HUNT (the two-lane order, principal 2026-09-06, as
amended 2026-09-30). The family fires ONLY on a release -- one dated observation that the desk
first saw at a recorded `available_time` -- and holds for a few days. It never reads the share's
own price path to decide a side; price is read only to size the stop and place the order. That is
what `universe_policy.NEWS_LANE_FAMILIES` admits for a share CFD.

POINT-IN-TIME, BY CONSTRUCTION.
  * Each release is the FIRST vintage of its `event_time` (the earliest `available_time`); a
    later revision of the same period is not a second event.
  * `available_time` is UTC. The bar index is broker time (New York + 7h, the law of
    `libs/regime/session_clock.py`) carrying a UTC tzinfo, so the release instant is moved INTO
    the bars' frame; bars are never moved. Entry is decided at the close of the first bar that
    OPENS at or after the release, and the engine fills at the next open (`wait_bars=1`).

`source` AND `prior_sign` ARE REQUIRED KEYWORD ARGUMENTS on purpose: which lake series bears on
which share with which sign is the hand-off's evidence, not a searched parameter, so the
orthogonal sweep names the family unsuppliable instead of calling it blind.

HONEST LIMITS. No series, no `available_time`, no surprise column, or no release above
`threshold`: the family returns [] -- never a price-only fallback.
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1

#: Where `research/alt_proxies.write_lake_series` lands each series (the same directory
#: `family_exogenous_conditioner` and `cell_modifiers` read).
SERIES_DIR = Path(__file__).resolve().parents[1] / "data" / "lake" / "series"

#: THE BROKER CLOCK (LAWS; `libs/regime/session_clock.py`): server time is New York + 7 hours,
#: so 17:00 New York is 00:00 server all year. Read from that module when it is importable so
#: the two can never disagree; the literal values are its own.
try:  # pragma: no cover - depends on the tree the family runs in
    from libs.regime.session_clock import SERVER_SHIFT_H, SERVER_TZ
except Exception:  # pragma: no cover
    SERVER_TZ, SERVER_SHIFT_H = "America/New_York", 7

_CACHE: dict[tuple[str, float, str], list[tuple[pd.Timestamp, float]]] = {}


def series_path(source: str, root: Path | None = None) -> Path | None:
    base = root or SERIES_DIR
    if not source or any(c in str(source) for c in ("/", "\\", "..")):
        return None
    for suffix in (".parquet", ".csv"):
        p = base / f"{source}{suffix}"
        if p.exists():
            return p
    return None


def to_broker(ts_utc: pd.Timestamp) -> pd.Timestamp:
    """A genuinely-UTC instant as the stamp the broker's bar index would carry (tz=UTC label)."""
    ny = ts_utc.tz_convert(SERVER_TZ).tz_localize(None)
    return (ny + timedelta(hours=int(SERVER_SHIFT_H))).tz_localize("UTC")


def releases(source: str, column: str = "surprise_z", *, root: Path | None = None
             ) -> list[tuple[pd.Timestamp, float]]:
    """(release instant in UTC, column value) per event period, FIRST vintage only, oldest first.
    [] when the series, its stamp or the column is absent -- UNMEASURED, never a fallback."""
    path = series_path(source, root)
    if path is None:
        return []
    key = (str(path), path.stat().st_mtime, column)
    if key in _CACHE:
        return _CACHE[key]
    try:
        df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    except Exception:
        return []
    if df is None or df.empty or column not in df.columns or "available_time" not in df.columns:
        return []
    avail = pd.to_datetime(df["available_time"], errors="coerce", utc=True)
    val = pd.to_numeric(df[column], errors="coerce")
    period = (df["event_time"].astype(str) if "event_time" in df.columns
              else pd.Series(avail.astype(str), index=df.index))
    frame = pd.DataFrame({"period": period, "at": avail, "v": val}).dropna(subset=["at"])
    frame = frame.sort_values("at").drop_duplicates("period", keep="first")
    frame = frame[np.isfinite(frame["v"].to_numpy(dtype=float))]
    out = [(pd.Timestamp(a), float(v)) for a, v in zip(frame["at"], frame["v"], strict=True)]
    if len(_CACHE) > 64:
        _CACHE.clear()
    _CACHE[key] = out
    return out


def family_alt_release_drift(
    df: pd.DataFrame,
    *,
    source: str,
    prior_sign: int,
    column: str = "surprise_z",
    threshold: float = 1.0,
    side: int = 1,
    hold_days: int = 5,
    atr_n: int = 20,
    stop_atr: float = 3.0,
    rr: float = 1.5,
    series_root: Any = None,
) -> list[Signal]:
    """Follow (side=+1) or fade (-1) each release whose |`column`| clears `threshold`, in the
    direction sign(value) x `prior_sign`, holding about `hold_days` trading days."""
    if int(prior_sign) not in (1, -1) or int(side) not in (1, -1):
        return []
    ev = releases(source, column, root=Path(series_root) if series_root else None)
    if not ev:
        return []
    d = _h1(df)
    if len(d) < atr_n + 4:
        return []
    index = pd.DatetimeIndex(d.index)
    if index.tz is None:
        index = index.tz_localize("UTC")
    per_day = max(1, round(float(pd.Series(index.normalize()).value_counts().median())))
    ttl = int(max(1, int(hold_days)) * per_day)
    atr = _atr(d, atr_n).to_numpy()
    close = d["close"].astype(float).to_numpy()
    thr = abs(float(threshold))
    out: list[Signal] = []
    armed_from = -1
    for at, v in ev:
        if abs(v) < thr or v == 0:
            continue
        pos = int(index.searchsorted(to_broker(at), side="left"))  # first bar OPENING after it
        if pos <= armed_from or pos >= len(d) - 1 or pos < atr_n:
            continue
        a = float(atr[pos])
        if not np.isfinite(a) or a <= 0:
            continue
        s = int(side) * int(prior_sign) * (1 if v > 0 else -1)
        px = float(close[pos])
        out.append(Signal(time=d.index[pos], side=s, stop=px - s * stop_atr * a,
                          target=px + s * stop_atr * a * rr, ttl_bars=ttl,
                          tag=f"alt_release_drift:{source}", trigger=None, wait_bars=1))
        armed_from = pos + ttl // 2
    return out
