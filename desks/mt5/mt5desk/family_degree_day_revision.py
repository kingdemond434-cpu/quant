"""Trade natural gas on a REVISION of the NOAA CPC degree-day forecast, never on its level.

    reading = z( <region>_<measure>_rev of issue k ) against the `window` non-null revisions of
              the issues BEFORE k (same product, region and measure)
    event   = an issue whose reading is on the named side (`move` "up": >= +min_abs, "down":
              <= -min_abs) and whose revision is not zero
    signal  = `direction`, on the first bar that opens after the issue was knowable

MECHANISM. Gas burn follows the weather the market EXPECTS. CPC re-issues its 7-day degree-day
forecast every day at 0000 UTC; when an issue says the coming week holds more heating degree days
(winter) or cooling degree days (summer, gas-fired power at the margin) than the previous issue
said for the same days, expected residential/commercial and power-sector burn rises, storage
expectations tighten, and gas reprices over the following hours to days. The level is what
everybody already priced; the REVISION is the news. The claim is falsifiable per cell: it fails
when its events carry no forward return net of cost.

THE INPUT IS THE LAKE'S PIT SERIES, READ BY PATH. `research/noaa_forecast_vintage.py` writes
`data/lake/series/noaa_<product>.parquet`, one row per issue in the lake's PIT envelope
(`available_time`, `event_time` = the issue instant, `source_id`, `vintage_id`, `retrieval_time`)
plus numeric `<region>_<measure>_rev` (the revision summed over the targets the issue shares with
the issue before it; NULL on a first issue, never 0), `_lvl` and `_nov` (shared targets). Products
are `cpc_dd7_gas_hdd`, `cpc_dd7_elec_hdd`, `cpc_dd7_pop_hdd`, `cpc_dd7_pop_cdd` (daily) and
`cpc_dd_monthly`; regions are the nine census divisions plus `conus`. The product, region and
measure are named on the recipe and loaded HERE, so the sweep, the sealed gauntlet's `build_cell`
and the forward clock rebuild the same signals from the same identity.

THE EVENT CLOCK IS `available_time`. The producer stamps it as
max(issue, min(fetch, issue + 24h)) -- and, for a revision, as the later of the two issues'
knowable instants -- so it is never before the market could read both forecasts. It is a UTC
INSTANT; the bar index is BROKER time under a UTC tzinfo (+2 winter, +3 summer, see
`family_event_reaction._event_times`), so a UTC instant compared straight to a bar label lands two
to three hours EARLY. The entry bar must therefore be labelled at or after
available_time + `BROKER_MAX_OFFSET_H` (3h), the same offset `family_cb_tone` and
`family_macro_fair_value` use: on or after the knowable instant in BOTH seasons, at most one hour
late in winter, never early. A stamp that carries no hour (a bare date string) could be any hour
of that UTC day, so it is placed on 00:00 UTC of the FOLLOWING day first, as `family_cb_tone`
does; the parquet's own datetime column always carries the hour.

A NULL REVISION IS NEVER AN EVENT. A first issue (or one that shares no target with the issue
before it) has no revision: it is UNMEASURED, it is not scored, and it does not count toward any
later issue's window. A zero revision is not news and never fires either.

THE Z-SCORE READS ONLY THE PAST. Issue k is scored against the mean and deviation of the `window`
non-null revisions of the issues before it (ordered by issue time); issue k itself and every later
issue are outside its window, so rewriting the future changes no z already computed.

AN ABSENT INPUT IS A NAMED REFUSAL, NOT A CELL THAT NEVER FIRES (L1.28a): no parquet for the
product, an unknown product, or a parquet without the named `<region>_<measure>_rev` column (or
without `available_time`) raises `DegreeDayUnavailable` with code `noaa_degree_day_absent`. It is
also a TypeError on purpose -- the sealed builder catches only TypeError on its first family call
and names the failure on its retry, so the refusal goes through the builder's own door, exactly as
`CbToneUnavailable` does.

REFUSES (returns []) on an unknown region, measure, move or direction, a negative threshold, a
window below 2, or too few bars.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.families import Signal
from mt5desk.family_event_reaction import family_event_reaction

DESK = Path(__file__).resolve().parents[1]
#: Where `research/noaa_forecast_vintage.write_series` lands `noaa_<product>.parquet`. Named from
#: this file's own location so a test tree and the box agree without an environment variable.
SERIES_DIR = DESK / "data" / "lake" / "series"

PRODUCTS = ("cpc_dd7_gas_hdd", "cpc_dd7_elec_hdd", "cpc_dd7_pop_hdd", "cpc_dd7_pop_cdd",
            "cpc_dd_monthly")
DEFAULT_PRODUCT = "cpc_dd7_gas_hdd"
REGIONS = ("new_england", "middle_atlantic", "east_north_central", "west_north_central",
           "south_atlantic", "east_south_central", "west_south_central", "mountain", "pacific",
           "conus")
MEASURES = ("hdd", "cdd")
MOVES = ("up", "down")
DIRECTIONS = {"long": 1, "short": -1}
#: The instruments this family may be judged on: natural gas only (universe.json carries no power
#: instrument).
SYMBOLS = ("XNGUSD",)
#: The largest measured broker-time offset from UTC (summer). Adding it to a UTC instant gives a
#: bar label that is on or after that instant in both seasons.
BROKER_MAX_OFFSET_H = 3
_EVENT_SYMBOL = "NOAA_DEGREE_DAY"

ABSENT = "noaa_degree_day_absent"


class DegreeDayUnavailable(LookupError, TypeError):
    """The recipe names a NOAA degree-day series this host does not hold."""


def series_path(product: str) -> Path:
    return Path(SERIES_DIR) / f"noaa_{product}.parquet"


def _mtime(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return -1


@lru_cache(maxsize=16)
def _frame(path: str, mtime_ns: int) -> pd.DataFrame | None:
    if mtime_ns < 0:
        return None
    try:
        return pd.read_parquet(path)
    except (OSError, ValueError, ImportError):
        return None


def _knowable(raw: pd.Series) -> pd.Series:
    """`available_time` as a UTC instant. A bare-date string carries no hour, so it is placed on
    00:00 UTC of the following day (it could have been posted at any hour of the day it names)."""
    bare = raw.astype(str).str.len().eq(10) if raw.dtype == object else pd.Series(
        False, index=raw.index)
    at = pd.to_datetime(raw, errors="coerce", utc=True)
    return at.where(~bare, at + pd.Timedelta(days=1))


def revisions(product: str, region: str, measure: str) -> pd.DataFrame:
    """Per issue with a measured (non-null) revision: `available_time` (UTC) and `rev`, ordered
    by issue time. Raises `DegreeDayUnavailable` when the product or column is absent."""
    if product not in PRODUCTS:
        raise DegreeDayUnavailable(
            f"{ABSENT}: {product!r} is not a NOAA degree-day product "
            f"(declared: {', '.join(PRODUCTS)})")
    path = series_path(product)
    df = _frame(str(path), _mtime(path))
    if df is None:
        raise DegreeDayUnavailable(
            f"{ABSENT}: {path} is absent or unreadable; the {product} revision is unmeasured on "
            "this host and the cell is unjudged")
    col = f"{region}_{measure}_rev"
    missing = [c for c in ("available_time", "event_time", col) if c not in df.columns]
    if missing:
        raise DegreeDayUnavailable(
            f"{ABSENT}: {path.name} carries no {', '.join(missing)}; the {region} {measure} "
            "revision is unmeasured and the cell is unjudged")
    out = pd.DataFrame({
        "issue": pd.to_datetime(df["event_time"], errors="coerce", utc=True),
        "available_time": _knowable(df["available_time"]),
        "rev": pd.to_numeric(df[col], errors="coerce").astype(float)})
    out = out.dropna(subset=["issue", "available_time"]).sort_values("issue", kind="stable")
    out = out.drop_duplicates("issue", keep="last")
    out = out[np.isfinite(out["rev"].to_numpy())]           # a null revision is never an event
    return out.reset_index(drop=True)


def prior_z(rev: pd.Series, window: int) -> pd.Series:
    """Each revision against the mean and deviation of the `window` revisions BEFORE it."""
    prior = rev.shift(1).rolling(int(window), min_periods=int(window))
    sd = prior.std()
    return (rev - prior.mean()) / sd.where(sd > 0)


def event_times(*, product: str, region: str, measure: str, move: str, min_abs: float,
                window: int) -> list[pd.Timestamp]:
    """Bar-frame instants (broker labels) from which each qualifying revision is knowable."""
    r = revisions(product, region, measure)
    z = prior_z(r["rev"], window)
    on = z >= float(min_abs) if move == "up" else z <= -float(min_abs)
    on &= r["rev"].ne(0.0) & z.notna()
    step = pd.Timedelta(hours=BROKER_MAX_OFFSET_H)
    return [pd.Timestamp(t) + step for t in r.loc[on.to_numpy(), "available_time"]]


def family_degree_day_revision(
    df: pd.DataFrame,
    *,
    side: int | None = None,
    product: str = DEFAULT_PRODUCT,
    region: str = "conus",
    measure: str = "hdd",
    move: str = "up",
    min_abs: float = 2.0,
    direction: str = "long",
    window: int = 60,
    hold_bars: int = 24,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
) -> list[Signal]:
    # THE RECIPE'S `direction` IS THE SIDE (as in `cb_tone_event` and `macro_fair_value`): the
    # sealed gauntlet always passes side=1 and the forward clock passes the cell's own side, so
    # honouring `side` would make the two callers build different trades from one identity.
    del side
    flip = DIRECTIONS.get(str(direction))
    if (flip is None or region not in REGIONS or measure not in MEASURES or move not in MOVES
            or float(min_abs) < 0 or int(window) < 2 or "close" not in df.columns):
        return []
    times = event_times(product=str(product), region=str(region), measure=str(measure),
                        move=str(move), min_abs=float(min_abs), window=int(window))
    if not times:
        return []
    events: list[dict[str, Any]] = [{"symbol": _EVENT_SYMBOL, "at": ts} for ts in times]
    out = family_event_reaction(
        df, events=events, symbol=_EVENT_SYMBOL, mode="drift", side=flip,
        hold_bars=int(hold_bars), atr_n=int(atr_n), stop_atr=float(stop_atr), rr=float(rr),
        ttl_bars=int(hold_bars), cooldown_bars=int(hold_bars), clock="bars")
    tag = f"degree_day_revision:{product}:{region}_{measure}:{move}:{direction}"
    return [Signal(time=s.time, side=s.side, stop=s.stop, target=s.target, ttl_bars=s.ttl_bars,
                   tag=tag, trigger=s.trigger, wait_bars=s.wait_bars) for s in out]
