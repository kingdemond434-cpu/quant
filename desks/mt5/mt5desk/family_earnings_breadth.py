"""Trade a US INDEX CFD on the breadth of the day's earnings reactions: one family.

    reaction(r)  = log( first close >= one full session after r's release / last close before it )
                   on r's own share-CFD bars
    breadth(d)   = over the reporters whose reaction window CLOSED on broker day d:
                   stat "share_up"  the share of them with reaction > 0
                   stat "median"    their median reaction
    reading(d)   = z( breadth(d) ) against the `window` qualifying days BEFORE d
    event        = reading on the named side (`move` "up": >= +min_abs, "down": <= -min_abs) on a
                   day with at least `min_reporters` reporters
    signal       = `direction`, on the first index bar that opens after the close completing d

MECHANISM. An earnings season is a sequence of samples of aggregate corporate earnings. Each
reporter's first-session reaction is the market's verdict on its own report, and the share of
reporters rising on a day (or the median reaction) is a noisy read of what the season says about
the aggregate. Index holders under-react to the cross-section -- each reporter is priced as its
own news -- so a day of unusually broad positive or negative reactions is information the index
absorbs over the following days. Falsifiable per cell: it fails when its events carry no forward
return on the index net of cost.

THE TWO LANES (2026-09-06, amended 2026-09-30). Single-name share CFDs are never hunted for a
statistical hypothesis. Here they are read ONLY as an aggregate input: no share symbol is ever a
traded symbol or a cell. The family trades the frame it is handed, and refuses ([]) a frame whose
recipe names a share CFD (`symbol`) -- the proposer mints cells only on `INDEX_SYMBOLS` that the
registry classes as indices, which route to the hypothesis lane.

INPUTS, NO NETWORK, NO NEW SOURCE.
  - Release instants: SEC 8-K item 2.02 ("Results of Operations") filings from the cache the
    desk's EDGAR cell already keeps (`data/edgar_cache/*.json`, written by
    `research/sandboxes/edgar_transmission.py`). Both shapes that cell reads are read here: a raw
    EDGAR full-text response (`hits.hits[]._source`) and the cell's own row list (`hits: [...]`).
    A filer is identified by its ticker (`ticker` / `tickers`, or the "(TICKER)" in EDGAR's
    `display_names`); the CIK is kept beside it for de-duplication. The release instant is the
    filing's acceptance time (`accepted` / `acceptance_datetime` / `acceptanceDateTime`) when the
    row carries one; otherwise only its filing DAY is known.
  - Ticker -> share CFD: `libs.data.free_stack.TICKER_CFD` (the desk's fact table), admitted only
    when MetaTrader's own registry classes the name as a share CFD
    (`universe_policy.is_equity`).
  - Share-CFD bars: the desk's own parquet bars on the cell's chart, through
    `family_inputs.bars_named` (the reader `build_cell` uses for peers). A caller that already
    holds them passes `reporters` and nothing is read from disk.
  No other dated earnings calendar in the desk carries a point-in-time stamp
  (`side_channels/earnings_miner.py` writes undated stubs), so none is read.

THE CLOCK (copied from `family_macro_fair_value`'s broker-offset handling). Bars are labelled in
broker time, UTC+2 in winter and UTC+3 in summer.
  - An acceptance INSTANT (UTC) is placed in the bar frame twice: its LATEST possible bar-frame
    label (+`BROKER_MAX_OFFSET_H`) bounds the reaction window's END, its EARLIEST
    (+`BROKER_MIN_OFFSET_H`) bounds the pre-release close. Either way no window straddles the
    release in either season.
  - A filing DAY carries no hour. EDGAR dates a filing accepted after 17:30 ET to the next
    business day, so a day-only release lies in [day-1 20:00 UTC, day+1 00:00 UTC): the
    pre-release close is the last bar closed by the early end, and the window ends after the
    late end (`DAY_EARLY_UTC_H`, and 00:00 UTC of the FOLLOWING day exactly as the macro family
    takes a knowable day).
  - "At least one full session after": the reaction ends at the LAST close of the first broker
    day whose FIRST bar opens at or after the release's latest bar-frame instant.
  - A reporter counts on the broker day its window closed, and day d's breadth is complete at the
    latest such close; entry is the first index bar opening at or after it.

LOOK-AHEAD. A reporter whose window has not closed by d is not in breadth(d) -- it sits on a later
day or, if its window never closes in the bars, nowhere. The z of day d reads only qualifying
days before d (`prior_z`).

AN ABSENT INPUT IS A NAMED REFUSAL, NOT A CELL THAT NEVER FIRES (L1.28a): no cache, no 8-K 2.02
filing with a ticker, or no reporter mapping to a share CFD with bars raises
`EarningsBreadthUnavailable` with code `earnings_breadth_absent`. It is also a TypeError on
purpose -- the sealed builder catches only TypeError on its first family call and names the
failure on its retry -- the pattern `MacroFairValueUnavailable` (and `CbToneUnavailable`) use.

REFUSES (returns []) on an unknown stat, move or direction, a negative threshold, a window < 2,
min_reporters < 1, a share-CFD `symbol`, or a frame without closes.
"""
from __future__ import annotations

import json
import re
import sys
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.families import Signal
from mt5desk.family_event_reaction import family_event_reaction

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
CACHE = DESK / "data" / "edgar_cache"
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

STATS = ("share_up", "median")
MOVES = ("up", "down")
DIRECTIONS = {"long": 1, "short": -1}
#: The traded instruments: US index CFDs, used when the registry carries them.
INDEX_SYMBOLS = ("US500", "NAS100", "US30", "US2000")
#: The largest / smallest measured broker-time offset from UTC (summer / winter).
BROKER_MAX_OFFSET_H = 3
BROKER_MIN_OFFSET_H = 2
#: A day-only filing may have been accepted after 17:30 ET the previous business day; 20:00 UTC
#: of the previous calendar day is at or before that in both seasons (16:00 ET summer close).
DAY_EARLY_UTC_H = -4
ABSENT = "earnings_breadth_absent"
_EVENT_SYMBOL = "EARNINGS_BREADTH"
_TICKER_IN_NAME = re.compile(r"\(([A-Z][A-Z0-9.\-]{0,9})\)")


class EarningsBreadthUnavailable(LookupError, TypeError):
    """The recipe needs earnings releases or share-CFD bars this host does not hold."""


# ------------------------------------------------------------------------------ the filings
def _items(src: Mapping[str, Any]) -> list[str]:
    raw = src.get("items") or []
    if isinstance(raw, str):
        raw = re.split(r"[,\s]+", raw)
    return [str(i) for i in raw]


def _tickers(src: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    for key in ("ticker", "tickers"):
        v = src.get(key)
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, (list, tuple)):
            out.extend(str(x) for x in v)
    for name in src.get("display_names") or []:
        out.extend(_TICKER_IN_NAME.findall(str(name)))
    seen: list[str] = []
    for t in out:
        t = t.strip().upper().split(",")[0]
        if t and t not in seen:
            seen.append(t)
    return seen


def _accepted(src: Mapping[str, Any]) -> str:
    for key in ("accepted", "acceptance_datetime", "acceptanceDateTime", "accepted_at"):
        v = src.get(key)
        if v:
            return str(v)
    return ""


def filing_rows(doc: Any) -> list[dict[str, Any]]:
    """8-K item 2.02 rows {tickers, cik, filed, accepted} from either cache shape."""
    if not isinstance(doc, dict):
        return []
    if isinstance(doc.get("hits"), dict):
        srcs = [dict(h.get("_source") or {}) for h in doc["hits"].get("hits") or []
                if isinstance(h, dict)]
        for s in srcs:
            s.setdefault("filed", s.get("file_date"))
    elif isinstance(doc.get("hits"), list):
        srcs = [dict(h) for h in doc["hits"] if isinstance(h, dict)]
    else:
        return []
    out = []
    for s in srcs:
        if str(s.get("form") or "") != "8-K":
            continue
        if not any(i.startswith("2.02") for i in _items(s)):
            continue
        tick = _tickers(s)
        if not tick:
            continue
        ciks = s.get("ciks") or s.get("cik") or []
        cik = str(ciks[0] if isinstance(ciks, (list, tuple)) and ciks else ciks or "")
        out.append({"tickers": tick, "cik": cik, "filed": str(s.get("filed") or "")[:10],
                    "accepted": _accepted(s)})
    return out


def _cache_key() -> tuple[tuple[str, int], ...]:
    try:
        return tuple((p.name, p.stat().st_mtime_ns) for p in sorted(Path(CACHE).glob("*.json")))
    except OSError:
        return ()


@lru_cache(maxsize=4)
def _cached_filings(cache: str, key: tuple[tuple[str, int], ...]) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for name, _m in key:
        try:
            rows.extend(filing_rows(json.loads((Path(cache) / name).read_text("utf-8-sig"))))
        except (OSError, ValueError):
            continue
    return tuple(rows)


def cached_filings() -> list[dict[str, Any]]:
    """Every 8-K 2.02 row with a ticker in the cache; refuses by name when there are none."""
    key = _cache_key()
    rows = list(_cached_filings(str(CACHE), key)) if key else []
    if not rows:
        what = ("no cache files under" if not key
                else "no 8-K item 2.02 filing with a ticker in")
        raise EarningsBreadthUnavailable(
            f"{ABSENT}: {what} {CACHE}; "
            "earnings reaction breadth is unmeasured on this host and the cell is unjudged")
    return rows


def ticker_cfd() -> dict[str, str]:
    from libs.data.free_stack import TICKER_CFD
    return dict(TICKER_CFD)


def _is_share(symbol: str) -> bool:
    try:
        from research.universe_policy import is_equity
    except ImportError:                                   # pragma: no cover -- desk on sys.path
        from universe_policy import is_equity  # type: ignore[no-redef]
    return bool(is_equity(symbol))


def release_bounds(row: Mapping[str, Any]) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    """(earliest, latest) release instant in the BAR frame, or None when unreadable."""
    acc = str(row.get("accepted") or "")
    if acc and len(acc) > 10:
        try:
            ts = pd.Timestamp(acc)
        except (ValueError, TypeError):
            ts = None
        if ts is not None:
            ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
            return (ts + pd.Timedelta(hours=BROKER_MIN_OFFSET_H),
                    ts + pd.Timedelta(hours=BROKER_MAX_OFFSET_H))
    day = str(row.get("filed") or acc)[:10]
    try:
        d = pd.Timestamp(day, tz="UTC")
    except (ValueError, TypeError):
        return None
    early = d + pd.Timedelta(hours=DAY_EARLY_UTC_H + BROKER_MIN_OFFSET_H)
    late = d + pd.Timedelta(days=1) + pd.Timedelta(hours=BROKER_MAX_OFFSET_H)
    return early, late


def reaction(bars: pd.DataFrame, early: pd.Timestamp,
             late: pd.Timestamp) -> tuple[float, pd.Timestamp] | None:
    """(log reaction, bar-frame instant its window closed) for one reporter, or None."""
    idx = bars.index
    if len(idx) < 3:
        return None
    step = pd.Timedelta(minutes=_bar_minutes(idx))
    close = bars["close"].to_numpy(dtype=float)
    # last bar whose CLOSE (label + one bar) is at or before the earliest release instant
    pre = int(idx.searchsorted(early - step, side="right")) - 1
    if pre < 0:
        return None
    first = int(idx.searchsorted(late, side="left"))
    while first < len(idx):
        day = idx[first].normalize()
        if int(idx.searchsorted(day, side="left")) == first:
            break                          # the first bar of its day opens after the release
        # the day's session began before the release -- the next day is the first full one
        first = int(idx.searchsorted(day + pd.Timedelta(days=1), side="left"))
    if first >= len(idx):
        return None
    day = idx[first].normalize()
    last = int(idx.searchsorted(day + pd.Timedelta(days=1), side="left")) - 1
    if last + 1 >= len(idx):
        return None                       # the day may still be open: the window has not closed
    a, b = close[pre], close[last]
    if not (np.isfinite(a) and np.isfinite(b) and a > 0 and b > 0):
        return None
    return float(np.log(b / a)), idx[last] + step


def _bar_minutes(idx: pd.DatetimeIndex) -> int:
    if len(idx) < 2:
        return 60
    diffs = np.diff(idx.asi8[: min(len(idx), 500)]) // 60_000_000_000
    diffs = diffs[diffs > 0]
    return int(np.median(diffs)) if len(diffs) else 60


def reporter_reactions(like: pd.DataFrame, filings: Sequence[Mapping[str, Any]] | None = None,
                       reporters: Mapping[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    """One row per (share CFD, release): reaction and the bar-frame instant its window closed."""
    rows = list(filings) if filings is not None else cached_filings()
    tmap = ticker_cfd()
    frames: dict[str, pd.DataFrame | None] = {}
    seen: set[tuple[str, str]] = set()
    out = []
    mapped = 0
    for r in rows:
        cfd = next((tmap[t] for t in r.get("tickers") or () if t in tmap), None)
        if cfd is None:
            continue
        if reporters is not None:
            if cfd not in reporters:
                continue
        elif not _is_share(cfd):
            continue
        key = (cfd, str(r.get("filed") or r.get("accepted") or "")[:10])
        if key in seen:
            continue
        seen.add(key)
        if cfd not in frames:
            f = (reporters or {}).get(cfd)
            if f is None and reporters is None:
                from mt5desk.family_inputs import bars_named
                f = bars_named(cfd, like)
            frames[cfd] = f if f is not None and "close" in getattr(f, "columns", ()) else None
        f = frames[cfd]
        if f is None:
            continue
        mapped += 1
        b = release_bounds(r)
        if b is None:
            continue
        got = reaction(f, *b)
        if got is None:
            continue
        out.append({"symbol": cfd, "reaction": got[0], "closed_at": got[1]})
    if not mapped:
        raise EarningsBreadthUnavailable(
            f"{ABSENT}: {len(rows)} 8-K 2.02 filing(s), none on a share CFD with bars on this "
            "chart; earnings reaction breadth is unmeasured and the cell is unjudged")
    return pd.DataFrame(out, columns=["symbol", "reaction", "closed_at"])


def daily_breadth(rx: pd.DataFrame, stat: str, min_reporters: int) -> pd.DataFrame:
    """Per broker day d with >= min_reporters closed windows: breadth and the completing close."""
    if rx.empty:
        return pd.DataFrame(columns=["breadth", "n", "complete_at"])
    day = pd.DatetimeIndex(rx["closed_at"]).normalize()
    g = rx.assign(day=day).groupby("day")
    if stat == "share_up":
        val = g["reaction"].apply(lambda s: float((s > 0).mean()))
    else:
        val = g["reaction"].median()
    out = pd.DataFrame({"breadth": val, "n": g.size(), "complete_at": g["closed_at"].max()})
    return out[out["n"] >= int(min_reporters)].sort_index()


def prior_z(vals: pd.Series, window: int) -> pd.Series:
    """Each value against the mean and deviation of the `window` values BEFORE it."""
    prior = vals.shift(1).rolling(int(window), min_periods=int(window))
    sd = prior.std()
    return ((vals - prior.mean()) / sd.where(sd > 0)).dropna()


def event_times(df: pd.DataFrame, *, stat: str, move: str, min_abs: float, min_reporters: int,
                window: int, filings: Sequence[Mapping[str, Any]] | None = None,
                reporters: Mapping[str, pd.DataFrame] | None = None) -> list[pd.Timestamp]:
    """Bar-frame instants at which a qualifying breadth day is complete."""
    days = daily_breadth(reporter_reactions(df, filings, reporters), stat, min_reporters)
    if days.empty:
        return []
    z = prior_z(days["breadth"].astype(float), window)
    hit = z >= float(min_abs) if move == "up" else z <= -float(min_abs)
    return [pd.Timestamp(t) for t in days.loc[z.index[hit.to_numpy()], "complete_at"]]


def family_earnings_breadth(
    df: pd.DataFrame,
    *,
    side: int | None = None,
    symbol: str = "",
    stat: str = "share_up",
    move: str = "up",
    min_abs: float = 1.5,
    min_reporters: int = 10,
    direction: str = "long",
    window: int = 20,
    hold_bars: int = 24,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
    filings: Sequence[Mapping[str, Any]] | None = None,
    reporters: Mapping[str, pd.DataFrame] | None = None,
) -> list[Signal]:
    # THE RECIPE'S `direction` IS THE SIDE (as in `macro_fair_value`): the sealed gauntlet always
    # passes side=1 and the forward clock passes the cell's own side.
    del side
    flip = DIRECTIONS.get(str(direction))
    if (stat not in STATS or flip is None or move not in MOVES or float(min_abs) < 0
            or int(window) < 2 or int(min_reporters) < 1 or "close" not in df.columns):
        return []
    if symbol and _is_share(str(symbol)):
        return []                         # the two lanes: a share CFD is never the traded leg
    times = event_times(df, stat=str(stat), move=str(move), min_abs=float(min_abs),
                        min_reporters=int(min_reporters), window=int(window),
                        filings=filings, reporters=reporters)
    if not times:
        return []
    events: list[dict[str, Any]] = [{"symbol": _EVENT_SYMBOL, "at": ts} for ts in times]
    out = family_event_reaction(
        df, events=events, symbol=_EVENT_SYMBOL, mode="drift", side=flip,
        hold_bars=int(hold_bars), atr_n=int(atr_n), stop_atr=float(stop_atr), rr=float(rr),
        ttl_bars=int(hold_bars), cooldown_bars=int(hold_bars), clock="bars")
    tag = f"earnings_breadth:{stat}:{move}:{direction}"
    return [Signal(time=s.time, side=s.side, stop=s.stop, target=s.target, ttl_bars=s.ttl_bars,
                   tag=tag, trigger=s.trigger, wait_bars=s.wait_bars) for s in out]
