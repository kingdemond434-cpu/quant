"""Trade the bars after a scheduled public release whose SIZE surprised its own baseline.

Ideas N4, N6, N7, N8 ("Closing the gap to tier 1 firms", noon CRO batch 2026-11-11/13), one
family, five bases, every reading built only from what was knowable at its release instant:

  basis "eia_gas_storage"   N8  reading = z( weekly Lower-48 working-gas change
                                 - the five-year average change for the same week )
                                 (EIA weekly storage report, Thursday 10:30 ET)
  basis "usda_export_sales" N7  reading = z( net export sales this week
                                 - mean of the four weeks before ), one crop named on the recipe
                                 (`crop`: CORN, WHEAT or SOYBEAN; USDA FAS, Thursday 08:30 ET)
  basis "tic_flow"          N6  reading = z( monthly net foreign purchases of US long-term
                                 securities - median of the twelve months before ), FIRST PRINTS
                                 ONLY (TIC revises; a revised frame never reaches a cell)
  basis "boj_rinban_size"   N4  reading = z( yen bought across the day's outright JGB purchase
                                 operations - the yen the Bank had announced for them )
  basis "boj_rinban_cover"  N4  reading = z( offers / purchases across the day's operations ),
                                 the dealers' appetite to sell JGBs to the Bank

  event  = the release instant of a reading on the named side (`move` "up": >= +min_abs,
           "down": <= -min_abs)
  signal = `direction`, on the first bar that opens after the release instant

MECHANISM, PER BASIS (each falsifiable per cell: it fails when its events carry no forward
return net of cost).
  EIA STORAGE: injections larger than the seasonal norm (or withdrawals smaller) say supply is
  loose against weather-driven demand; front-month gas reprices lower over the days after, and the
  reverse for a tight print. The five-year same-week average is the industry's own yardstick, so
  the market's reference point and the reading are the same object.
  USDA EXPORT SALES: a week of net sales far above its recent run is new foreign demand booked
  against US stocks; the grain prices up as exporters cover. The four-week mean is the run-rate
  the trade already priced.
  TIC: foreign buying of US long-term assets well above its typical month is a capital inflow
  that has to be bought in dollars; the dollar crosses and US equity drift toward it as the flow
  is recognised. Twelve-month median is robust to the one-off months TIC is known for.
  BOJ RINBAN: the Bank buying more yen of JGBs than it announced is a stealth easing (yen weaker,
  JPN225 firmer); a high offer-to-purchase ratio is dealers dumping JGBs on the Bank, a yield
  pressure signal that has led the yen in every taper episode.

THE INPUT IS THE DESK'S OWN AXIS, `data/axes/release_surprise.json`, written only by
`research/release_surprise_ingest.py` with each row's `knowable_at` instant and `vintage`. A row
whose vintage is not admitted (`backfill_latest`: a revised history) is never read. The baseline
uses only rows knowable BEFORE the row being scored; the scale (z) uses only the `window` prior
deviations. A caller that already holds the rows passes `rows` and nothing is read from disk.

THE EVENT CLOCK. A release instant is UTC to the minute. The bar index is broker time (UTC+2
winter, UTC+3 summer). Each instant is moved into the bars' frame by the desk's measured clock
(`libs.research.bar_clock.to_bar_time`); when that cannot place it, the instant plus
`BROKER_MAX_OFFSET_H` (3h) is used, which is on or after the release in both seasons -- at most
an hour late, never early. The entry is the first bar whose label is at or after that point.

AN ABSENT INPUT IS A NAMED REFUSAL, NOT A CELL THAT NEVER FIRES (L1.28a): a basis with no
admitted rows raises `ReleaseSurpriseUnavailable` (a TypeError, so the sealed builder's first-call
door names it, as `CbToneUnavailable` and `MacroFairValueUnavailable` do).

REFUSES (returns []) on an unknown basis, move or direction, a negative threshold, an unknown
crop for the USDA basis, or a frame without closes.
"""
from __future__ import annotations

import json
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
AXIS = DESK / "data" / "axes" / "release_surprise.json"
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

BASES = ("eia_gas_storage", "usda_export_sales", "tic_flow", "boj_rinban_size",
         "boj_rinban_cover")
SOURCE_OF = {"eia_gas_storage": "eia_gas_storage", "usda_export_sales": "usda_export_sales",
             "tic_flow": "tic_flow", "boj_rinban_size": "boj_rinban",
             "boj_rinban_cover": "boj_rinban"}
CROPS = ("CORN", "WHEAT", "SOYBEAN")
MOVES = ("up", "down")
DIRECTIONS = {"long": 1, "short": -1}
ADMITTED_VINTAGES = frozenset({"first_print", "backfill_stable"})
#: Same-week matching tolerance when building the five-year average (days either side).
SAME_WEEK_TOL_D = 3
#: Years of same-week changes a five-year average needs before it is a number.
MIN_YEARS = 3
USDA_RUN_WEEKS = 4
TIC_MEDIAN_MONTHS = 12
BROKER_MAX_OFFSET_H = 3
_EVENT_SYMBOL = "RELEASE_SURPRISE"

ABSENT = "release_surprise_absent"


class ReleaseSurpriseUnavailable(LookupError, TypeError):
    """The recipe names a release this host holds no admitted rows for."""


def _mtime(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return -1


@lru_cache(maxsize=4)
def _rows_on_disk(path: str, mtime_ns: int) -> tuple[dict[str, Any], ...]:
    try:
        doc = json.loads(Path(path).read_text("utf-8"))
    except (OSError, ValueError):
        return ()
    rows = doc.get("rows") if isinstance(doc, dict) else None
    return tuple(r for r in rows or () if isinstance(r, dict))


def admitted(rows: Sequence[Mapping[str, Any]] | None, source: str,
             series: str | None = None) -> pd.DataFrame:
    """Admitted rows of one source (and series), as a frame indexed by knowable instant:
    columns period, value, offered_bn, planned_bn, bucket. Revisions are never read."""
    src = rows if rows is not None else _rows_on_disk(str(AXIS), _mtime(AXIS))
    keep = []
    for r in src:
        if r.get("source") != source or r.get("vintage") not in ADMITTED_VINTAGES:
            continue
        if series is not None and r.get("series") != series:
            continue
        try:
            at = pd.Timestamp(r["knowable_at"])
            val = float(r["value"])
            per = pd.Timestamp(str(r["period"]))
        except (KeyError, TypeError, ValueError):
            continue
        if at.tzinfo is None:
            at = at.tz_localize("UTC")
        if not np.isfinite(val):
            continue
        keep.append({"at": at.tz_convert("UTC"), "period": per, "value": val,
                     "series": r.get("series"), "bucket": r.get("bucket"),
                     "offered_bn": r.get("offered_bn"), "planned_bn": r.get("planned_bn")})
    if not keep:
        return pd.DataFrame(columns=["at", "period", "value", "series", "bucket",
                                     "offered_bn", "planned_bn"])
    f = pd.DataFrame(keep).sort_values(["period", "at"])
    return f.drop_duplicates(["series", "period"], keep="first").reset_index(drop=True)


def prior_z(dev: pd.Series, window: int) -> pd.Series:
    """Each deviation against the mean and deviation of the `window` deviations BEFORE it."""
    prior = dev.shift(1).rolling(int(window), min_periods=max(8, int(window) // 2))
    sd = prior.std()
    return ((dev - prior.mean()) / sd.where(sd > 0)).dropna()


def _unavailable(basis: str, detail: str) -> ReleaseSurpriseUnavailable:
    return ReleaseSurpriseUnavailable(
        f"{ABSENT}: {basis} -- {detail}; the reading is unmeasured on this host and the cell "
        "is unjudged")


def eia_surprise(rows: Sequence[Mapping[str, Any]] | None = None) -> pd.Series:
    """{release instant: weekly change - five-year same-week average change}, in Bcf."""
    f = admitted(rows, "eia_gas_storage", "R48_WORKING_GAS_BCF")
    if len(f) < 60:
        raise _unavailable("eia_gas_storage", f"{len(f)} admitted weekly levels (< 60)")
    f = f.set_index("period").sort_index()
    gap = f.index.to_series().diff().dt.days
    chg = (f["value"].diff()).where(gap.between(5, 9))
    weeks = pd.DataFrame({"chg": chg, "at": f["at"]}).dropna()
    per = weeks.index
    out = {}
    for p, row in weeks.iterrows():
        past = []
        for y in range(1, 6):
            target = p - pd.Timedelta(weeks=52 * y)
            j = per.searchsorted(target)
            best = None
            for k in (j - 1, j):
                gap_k = abs((per[k] - target).days) if 0 <= k < len(per) else None
                if gap_k is not None and gap_k <= SAME_WEEK_TOL_D and (
                        best is None or gap_k < abs((per[best] - target).days)):
                    best = k
            if best is not None and weeks["at"].iloc[best] < row["at"]:
                past.append(float(weeks["chg"].iloc[best]))
        if len(past) >= MIN_YEARS:
            out[row["at"]] = float(row["chg"]) - float(np.mean(past))
    if not out:
        raise _unavailable("eia_gas_storage", "no week has three prior years of the same week")
    return pd.Series(out, dtype=float).sort_index()


def usda_surprise(crop: str, rows: Sequence[Mapping[str, Any]] | None = None) -> pd.Series:
    """{release instant: net sales - mean of the four prior weeks}, thousand tonnes."""
    crop = str(crop).upper()
    f = admitted(rows, "usda_export_sales", f"{crop}_NET_SALES_KMT")
    if len(f) < 20:
        raise _unavailable("usda_export_sales", f"{crop}: {len(f)} admitted weeks (< 20)")
    f = f.sort_values("period").reset_index(drop=True)
    run = f["value"].shift(1).rolling(USDA_RUN_WEEKS, min_periods=USDA_RUN_WEEKS).mean()
    dev = (f["value"] - run)
    s = pd.Series(dev.to_numpy(), index=pd.DatetimeIndex(f["at"])).dropna()
    return s[~s.index.duplicated(keep="first")].sort_index()


def tic_surprise(rows: Sequence[Mapping[str, Any]] | None = None) -> pd.Series:
    """{knowable instant: net foreign LT purchases - median of the twelve prior first prints}."""
    f = admitted(rows, "tic_flow", "NET_FOREIGN_PURCHASES_LT_USD_MN")
    if len(f) < TIC_MEDIAN_MONTHS + 6:
        raise _unavailable("tic_flow", f"{len(f)} admitted monthly first prints "
                           f"(< {TIC_MEDIAN_MONTHS + 6}); history is revised, so only prints "
                           "captured live count")
    f = f.sort_values("period").reset_index(drop=True)
    med = f["value"].shift(1).rolling(TIC_MEDIAN_MONTHS, min_periods=TIC_MEDIAN_MONTHS).median()
    s = pd.Series((f["value"] - med).to_numpy(), index=pd.DatetimeIndex(f["at"])).dropna()
    return s[~s.index.duplicated(keep="first")].sort_index()


def boj_daily(rows: Sequence[Mapping[str, Any]] | None = None) -> pd.DataFrame:
    """Per operation day: bought, offered, and the announced amount. The announced amount is
    the operation's own planned figure when the results page states it, otherwise the
    previous operation's amount in the same maturity bucket (the Bank pre-announces a constant
    per-operation amount per bucket for the quarter, so a change IS the surprise)."""
    f = admitted(rows, "boj_rinban")
    if f.empty:
        raise _unavailable("boj_rinban", "no admitted JGB purchase operations")
    f = f.sort_values(["bucket", "period"]).copy()
    f["plan"] = pd.to_numeric(f["planned_bn"], errors="coerce")
    prev = f.groupby("bucket")["value"].shift(1)
    f["plan"] = f["plan"].fillna(prev)
    f["offered"] = pd.to_numeric(f["offered_bn"], errors="coerce")
    f = f.dropna(subset=["plan", "offered"])
    if f.empty:
        raise _unavailable("boj_rinban", "no operation with an announced amount to compare")
    g = f.groupby("period").agg(at=("at", "max"), bought=("value", "sum"),
                                planned=("plan", "sum"), offered=("offered", "sum"))
    return g.sort_index()


def boj_reading(kind: str, rows: Sequence[Mapping[str, Any]] | None = None) -> pd.Series:
    g = boj_daily(rows)
    if len(g) < 30:
        raise _unavailable(f"boj_rinban_{kind}", f"{len(g)} operation days (< 30)")
    v = (g["bought"] - g["planned"]) if kind == "size" else (g["offered"] /
                                                             g["bought"].where(g["bought"] > 0))
    s = pd.Series(v.to_numpy(), index=pd.DatetimeIndex(g["at"])).dropna()
    return s[~s.index.duplicated(keep="last")].sort_index()


def reading(basis: str, *, crop: str = "", window: int = 52,
            rows: Sequence[Mapping[str, Any]] | None = None) -> pd.Series:
    """{release instant (UTC): z of the basis's surprise against its own prior `window`}."""
    if basis == "eia_gas_storage":
        dev = eia_surprise(rows)
    elif basis == "usda_export_sales":
        dev = usda_surprise(crop, rows)
    elif basis == "tic_flow":
        dev = tic_surprise(rows)
    elif basis == "boj_rinban_size":
        dev = boj_reading("size", rows)
    elif basis == "boj_rinban_cover":
        dev = boj_reading("cover", rows)
    else:
        return pd.Series(dtype=float)
    return prior_z(dev, window)


def _onsets(z: pd.Series, move: str, min_abs: float) -> pd.Index:
    on = z >= float(min_abs) if move == "up" else z <= -float(min_abs)
    return z.index[(on & (z != 0.0)).to_numpy()]


def to_bar_frame(instants: Sequence[pd.Timestamp]) -> list[pd.Timestamp]:
    """UTC release instants -> bar-frame instants, never earlier than the release."""
    out = []
    try:
        from libs.research.bar_clock import to_bar_time
    except ImportError:                                     # pragma: no cover
        to_bar_time = None
    for ts in instants:
        t = pd.Timestamp(ts)
        t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
        floor = t + pd.Timedelta(hours=BROKER_MAX_OFFSET_H)
        moved = None
        if to_bar_time is not None:
            try:
                moved, _status, _why = to_bar_time(t.to_pydatetime(), fallback=True)
            except Exception:
                moved = None
        # The measured clock answers +2 (winter) or +3 (summer) inside the spans it measured;
        # outside them it returns None and the +3h ceiling is used -- late, never early.
        m = pd.Timestamp(moved) if moved is not None else floor
        m = m.tz_localize("UTC") if m.tzinfo is None else m
        out.append(m if m >= t + pd.Timedelta(hours=2) else floor)
    return out


def family_release_surprise(
    df: pd.DataFrame,
    *,
    side: int | None = None,
    basis: str = "",
    crop: str = "",
    move: str = "up",
    min_abs: float = 1.5,
    direction: str = "long",
    window: int = 52,
    hold_bars: int = 24,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
    rows: Sequence[Mapping[str, Any]] | None = None,
) -> list[Signal]:
    # THE RECIPE'S `direction` IS THE SIDE (as in cb_tone_event / macro_fair_value): the sealed
    # gauntlet passes side=1 and the forward clock the cell's side; honouring `side` would make
    # the two callers build different trades from one identity.
    del side
    flip = DIRECTIONS.get(str(direction))
    if (basis not in BASES or flip is None or move not in MOVES or float(min_abs) < 0
            or int(window) < 8 or "close" not in df.columns or len(df) < atr_n + 4):
        return []
    if basis == "usda_export_sales" and str(crop).upper() not in CROPS:
        return []
    z = reading(basis, crop=str(crop), window=int(window), rows=rows)
    if z.empty:
        return []
    times = to_bar_frame(list(_onsets(z, move, float(min_abs))))
    if not times:
        return []
    events: list[dict[str, Any]] = [{"symbol": _EVENT_SYMBOL, "at": ts} for ts in times]
    out = family_event_reaction(
        df, events=events, symbol=_EVENT_SYMBOL, mode="drift", side=flip,
        hold_bars=int(hold_bars), atr_n=int(atr_n), stop_atr=float(stop_atr), rr=float(rr),
        ttl_bars=int(hold_bars), cooldown_bars=int(hold_bars), clock="bars")
    tag = f"release_surprise:{basis}:{str(crop).upper() or '-'}:{move}:{direction}"
    return [Signal(time=s.time, side=s.side, stop=s.stop, target=s.target, ttl_bars=s.ttl_bars,
                   tag=tag, trigger=s.trigger, wait_bars=s.wait_bars) for s in out]
