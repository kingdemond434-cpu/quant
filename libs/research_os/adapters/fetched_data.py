"""Adapters for the observables this desk fetched rather than assumed it lacked.

WHY THESE EXIST (2026-08-29)

Three mechanisms carried the note "this desk does not have the data". That was a statement about
what the desk HELD, never a check of what it could REACH. Probed, every one had a free public
source with no API key:

    options_hedging   CBOE delayed quotes -- 28,892 SPX contracts with gamma, IV and open
                      interest, enough to compute real dealer gamma exposure
    macro_release     Fed FOMC calendar as JSON, 2,582 scheduled events
    implied vol       CBOE VIX daily history back to 1990

THE TWO KINDS OF AVAILABILITY, and conflating them is how honest data produces a dishonest
backtest:

    HISTORICAL   VIX and FOMC have real history. A mechanism using them is testable on the full
                 sample today, exactly like a price feature.
    FORWARD-ONLY CBOE publishes no options history. Gamma exposure exists only from the moment
                 the desk started recording -- currently ONE observation. That is not a defect
                 in the data, it is the truth about it, and `GammaExposureAdapter` reports
                 UNAVAILABLE until enough history accrues rather than backfilling a constant
                 across a decade of bars and calling it a measurement.

A CONSTANT IS NOT A SERIES. The tempting shortcut with one snapshot is to broadcast today's GEX
across every historical bar. It would produce a column, a backtest and a number -- and the number
would describe nothing, because a variable that never varies cannot predict anything and any
apparent effect would be the other terms doing the work.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from libs.research_os.adapters.base import MeasurementResult, ResearchAdapter

ROOT = Path(__file__).resolve().parents[3]
OBS = ROOT / "desks" / "mt5" / "data" / "observables"

#: Distinct gamma snapshots before the series can be used at all. Below this there is no
#: variation to condition on, and a flat column would silently become a constant term.
_MIN_GEX_OBSERVATIONS = 30

#: FOMC statements land 19:00 UTC (14:00 ET). Used as the intraday stamp when the calendar gives
#: only a date, so an event is never treated as knowable at that day's open.
_FOMC_UTC_HOUR = 19


def _as_utc_index(idx: pd.Index) -> pd.DatetimeIndex:
    di = pd.DatetimeIndex(idx)
    return di.tz_localize("UTC") if di.tz is None else di.tz_convert("UTC")


class ImpliedVolAdapter(ResearchAdapter):
    """VIX as the implied-volatility observable. Historical, so usable on the full sample."""

    mechanism = "implied_volatility"
    requires = ("desks/mt5/data/observables/cboe_vix_history.json",)

    def compatibility(self, spec: dict[str, Any]) -> float:
        return 1.0 if (OBS / "cboe_vix_history.json").exists() else 0.0

    def measure(self, spec: dict[str, Any], bars: pd.DataFrame) -> MeasurementResult:
        path = OBS / "cboe_vix_history.json"
        if not path.exists():
            return MeasurementResult(
                status="UNAVAILABLE", adapter="ImpliedVolAdapter",
                notes=f"{path.name} absent; run scripts/fetch_free_observables.py")
        try:
            blob = json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return MeasurementResult(status="UNAVAILABLE", adapter="ImpliedVolAdapter",
                                     notes=f"unreadable: {type(exc).__name__}")
        rows = blob.get("series") or []
        if not rows:
            return MeasurementResult(status="UNAVAILABLE", adapter="ImpliedVolAdapter",
                                     notes="VIX history is empty")
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["date", "close"]).sort_values("date")
        # A DAILY CLOSE IS KNOWABLE AFTER THE CLOSE. Shifting by one day is what stops an
        # intraday bar seeing the level its own session will settle at.
        s = pd.Series(df["close"].to_numpy(), index=df["date"]).shift(1)
        idx = _as_utc_index(bars.index)
        aligned = s.reindex(s.index.union(idx)).sort_index().ffill().reindex(idx)
        aligned.index = bars.index
        return MeasurementResult(
            status="DIRECT", adapter="ImpliedVolAdapter",
            feature_ids=["vix_close_lag1"], confidence=1.0, pit_safe=True, series=aligned,
            notes=(f"VIX daily close, {len(df)} rows from {blob.get('first')} to "
                   f"{blob.get('last')}, shifted one day so an intraday bar cannot see the level "
                   f"its own session settles at. Implied volatility is the observable the "
                   f"mechanism names; this is not a proxy."))


class GammaExposureAdapter(ResearchAdapter):
    """Real dealer gamma from the SPX chain. FORWARD-ONLY -- reports its own immaturity."""

    mechanism = "options_hedging"
    requires = ("desks/mt5/data/observables/cboe_spx_options.jsonl",)

    def _snapshots(self) -> pd.DataFrame:
        path = OBS / "cboe_spx_options.jsonl"
        if not path.exists():
            return pd.DataFrame()
        rows = []
        for line in path.read_text("utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return pd.DataFrame(rows)

    def compatibility(self, spec: dict[str, Any]) -> float:
        snaps = self._snapshots()
        if snaps.empty:
            return 0.0
        # Compatibility reflects what is MEASURABLE NOW, so it rises as history accrues rather
        # than claiming full capability from one observation.
        return min(1.0, len(snaps) / _MIN_GEX_OBSERVATIONS)

    def measure(self, spec: dict[str, Any], bars: pd.DataFrame) -> MeasurementResult:
        snaps = self._snapshots()
        if snaps.empty:
            return MeasurementResult(
                status="UNAVAILABLE", adapter="GammaExposureAdapter",
                notes=("no gamma snapshots recorded. CBOE publishes no options HISTORY, so this "
                       "observable only exists from the moment the desk starts recording; run "
                       "scripts/fetch_free_observables.py on a timer."))
        n = len(snaps)
        if n < _MIN_GEX_OBSERVATIONS:
            return MeasurementResult(
                status="UNAVAILABLE", adapter="GammaExposureAdapter",
                confidence=n / _MIN_GEX_OBSERVATIONS,
                notes=(f"{n} gamma snapshot(s) recorded, {_MIN_GEX_OBSERVATIONS} needed. "
                       f"Broadcasting one reading across historical bars would produce a CONSTANT "
                       f"column -- it would yield a backtest and a number, and the number would "
                       f"describe nothing, because a variable that never varies cannot predict "
                       f"and any apparent effect would be the other terms doing the work. "
                       f"This mechanism becomes measurable as the recorder accrues history."))

        snaps["fetched_at"] = pd.to_datetime(snaps["fetched_at"], utc=True, errors="coerce")
        snaps = snaps.dropna(subset=["fetched_at"]).sort_values("fetched_at")
        s = pd.Series(pd.to_numeric(snaps["net_gex"], errors="coerce").to_numpy(),
                      index=snaps["fetched_at"]).dropna()
        idx = _as_utc_index(bars.index)
        aligned = s.reindex(s.index.union(idx)).sort_index().ffill().reindex(idx)
        aligned.index = bars.index
        return MeasurementResult(
            status="DIRECT", adapter="GammaExposureAdapter",
            feature_ids=["spx_net_gex"], confidence=1.0, pit_safe=True, series=aligned,
            notes=(f"net dealer gamma exposure from {n} recorded SPX chain snapshots, stamped at "
                   f"FETCH time (not the source's market timestamp) and forward-filled, so no "
                   f"bar sees a reading before it was taken"))

    def pit_check(self, series: pd.Series, bars: pd.DataFrame) -> tuple[bool, str]:
        return True, ("gamma snapshots are indexed by the desk's own fetch time and "
                      "forward-filled; a bar can only see a reading already taken")


class MacroCalendarAdapter(ResearchAdapter):
    """Scheduled FOMC events. A real event clock, replacing 'previous-bar return'."""

    mechanism = "macro_release"
    requires = ("desks/mt5/data/observables/fomc_calendar.json",)

    #: Event types that MOVE MARKETS. A governor's speech on financial inclusion is on the same
    #: calendar as an FOMC decision and is not the same event; pooling them would dilute the
    #: signal with 568 speeches and then report that macro releases do not matter.
    _MARKET_MOVING = ("FOMC", "Stat", "Beige", "Testimony")

    def _events(self, types: tuple[str, ...] | None = None) -> pd.DatetimeIndex | None:
        """Scheduled events as UTC timestamps, built from month + day + time.

        THE CALENDAR HAS NO DATE FIELD. It carries `month` ('2026-09'), `days` ('3') and `time`
        ('8:30 a.m.') separately. A first version looked for `date`/`startDate`/`eventDate`,
        found none, and reported the whole calendar as unusable -- 2,012 dateable events
        discarded because the parser guessed a schema instead of reading one.
        """
        path = OBS / "fomc_calendar.json"
        if not path.exists():
            return None
        try:
            blob = json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        want = types or self._MARKET_MOVING
        stamps: list[pd.Timestamp] = []
        for ev in blob.get("raw") or []:
            if str(ev.get("type") or "") not in want:
                continue
            month, days = ev.get("month"), ev.get("days")
            if not month or not days:
                continue
            # `days` can be '3' or a range like '17-18'; a multi-day meeting is decided on its
            # LAST day, which is the one that moves the market.
            day = str(days).split("-")[-1].strip()
            try:
                base = pd.Timestamp(f"{month}-{int(day):02d}", tz="UTC")
            except (ValueError, TypeError):
                continue
            hour = _FOMC_UTC_HOUR
            raw_time = str(ev.get("time") or "")
            m = re.match(r"\s*(\d{1,2})[:.](\d{2})\s*(a\.?m\.?|p\.?m\.?)", raw_time, re.I)
            if m:
                h, mins = int(m.group(1)), int(m.group(2))
                if m.group(3).lower().startswith("p") and h != 12:
                    h += 12
                # Fed times are US Eastern; +5 is EST, and an hour of DST error is far cheaper
                # than treating a 14:00 ET statement as knowable at 14:00 UTC.
                base = base + pd.Timedelta(hours=h + 5, minutes=mins)
            else:
                base = base + pd.Timedelta(hours=hour)
            stamps.append(base)
        return pd.DatetimeIndex(sorted(set(stamps))) if stamps else None

    def compatibility(self, spec: dict[str, Any]) -> float:
        ev = self._events()
        return 1.0 if ev is not None and len(ev) > 50 else 0.0

    def measure(self, spec: dict[str, Any], bars: pd.DataFrame) -> MeasurementResult:
        events = self._events()
        if events is None or len(events) == 0:
            return MeasurementResult(
                status="UNAVAILABLE", adapter="MacroCalendarAdapter",
                notes=("no FOMC calendar; run scripts/fetch_free_observables.py. Using a "
                       "previous-bar return instead fires on every bar and tests one-bar "
                       "momentum under a macro label."))
        idx = _as_utc_index(bars.index)
        window = int(spec.get("event_window_bars", 4))
        # HOURS SINCE THE MOST RECENT EVENT AT OR BEFORE THIS BAR. Non-anticipating by
        # construction: `searchsorted(side="right") - 1` can only look backwards.
        pos = events.searchsorted(idx, side="right") - 1
        secs = []
        for i, p in enumerate(pos):
            secs.append(float("nan") if p < 0
                        else (idx[i] - events[p]).total_seconds() / 3600.0)
        hours = pd.Series(secs, index=bars.index)
        # The observable the mechanism wants is PROXIMITY to a release, not a raw age.
        proximity = (hours <= window).astype(float).where(hours.notna())
        n_in = int(proximity.sum())
        return MeasurementResult(
            status="DIRECT" if n_in > 0 else "UNAVAILABLE",
            adapter="MacroCalendarAdapter",
            feature_ids=[f"fomc_within_{window}h"], confidence=1.0, pit_safe=True,
            series=proximity if n_in > 0 else None,
            notes=(f"{len(events)} scheduled FOMC events; {n_in} bars fall within {window}h AFTER "
                   f"a release. Dates without a time are stamped {_FOMC_UTC_HOUR}:00 UTC -- a "
                   f"date is not a time, and midnight would mark the whole session as post-event."
                   if n_in > 0 else
                   f"{len(events)} events but none within {window}h of any bar in this window"))
