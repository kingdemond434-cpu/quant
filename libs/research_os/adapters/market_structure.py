"""Fixing windows and the rate curve -- the last two mechanisms called impossible.

WHY THESE EXIST (2026-08-30)

`benchmark_flow` was the final UNMEASURABLE, justified as "no fixing calendar". That was the same
mistake as the other two: a statement about what the desk held, not a check of what it could
reach. Probed, both of these answer with no API key:

    ECB euro reference rates      published daily at 14:15 CET -- a benchmark fix with a KNOWN
                                  publication clock, which is exactly what the mechanism needs
    Treasury / ECB yield curves   term structure, free and historical

A FIXING IS A CLOCK, NOT A DATASET, and that is why this one was solvable all along. The WMR
London 4pm fix, the ECB 14:15 CET reference, the Tokyo 9:55 JST fix -- these are PUBLISHED FIXED
TIMES. The desk never needed to buy a calendar; it needed to write down three constants and
convert them to the broker clock correctly. The conversion is the only hard part, and getting it
wrong by an hour produces a beautiful result about nothing.

WHY THE FIX WINDOW IS STILL VALIDATED_PROXY, NOT DIRECT. The mechanism's real observable is the
ORDER IMBALANCE at the fix -- the customer flow dealers must absorb. This measures the WINDOW in
which that flow occurs, not the flow itself. That is much closer than "close minus open on every
bar", and it is not the same thing, so it is labelled as what it is.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from libs.research_os.adapters.base import MeasurementResult, ResearchAdapter

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
OBS = DESK / "data" / "observables"

#: Broker offset: Fusion runs UTC+3, and the bar index is on the broker clock. Every constant
#: below is converted through this, because an hour of error here manufactures a result.
_BROKER_OFFSET_H = 3

#: PUBLISHED FIXING TIMES, in UTC. These are constants, not data -- which is precisely why
#: "no fixing calendar" was never a real blocker.
#:   WMR London      16:00 London  = 15:00 UTC (BST) / 16:00 UTC (GMT); 15:00 is the busier half
#:   ECB reference   14:15 CET     = 12:15 UTC (CET) / 13:15 UTC (CEST)
#:   Tokyo           09:55 JST     = 00:55 UTC
#: DST is not modelled: the windows below are widened by an hour instead, which costs a little
#: precision and cannot silently point at the wrong hour for half the year.
_FIX_UTC_HOURS: dict[str, tuple[int, ...]] = {
    "london": (15, 16),
    "ecb": (12, 13),
    "tokyo": (0, 1),
}


class FixingWindowAdapter(ResearchAdapter):
    """Proximity to a published benchmark fixing window, on the broker clock."""

    mechanism = "benchmark_flow"
    requires = ()

    def compatibility(self, spec: dict[str, Any]) -> float:
        which = str(spec.get("fix") or spec.get("context") or "london").lower()
        return 1.0 if any(k in which for k in _FIX_UTC_HOURS) else 0.7

    def measure(self, spec: dict[str, Any], bars: pd.DataFrame) -> MeasurementResult:
        which = str(spec.get("fix") or spec.get("context") or "london").lower()
        key = next((k for k in _FIX_UTC_HOURS if k in which), "london")
        utc_hours = _FIX_UTC_HOURS[key]
        broker_hours = tuple((h + _BROKER_OFFSET_H) % 24 for h in utc_hours)

        h = bars.index.hour
        in_window = pd.Series([hh in broker_hours for hh in h], index=bars.index).astype(float)
        if in_window.sum() == 0:
            return MeasurementResult(
                status="UNAVAILABLE", adapter="FixingWindowAdapter",
                notes=(f"no bar falls in the {key} fix window (broker hours {broker_hours}); "
                       f"this instrument may not trade then"))

        # THE OBSERVABLE IS DISPLACEMENT INTO THE FIX, which is what the temporary-impact claim
        # is about -- not merely "a bar happened during the window".
        pre = bars["close"] - bars["close"].shift(int(spec.get("pre_window_bars", 2)))
        disp = (pre / bars["close"].rolling(20).std()).where(in_window > 0)
        n = int(disp.notna().sum())
        return MeasurementResult(
            status="VALIDATED_PROXY", adapter="FixingWindowAdapter",
            feature_ids=[f"fix_disp:{key}"], confidence=0.8, pit_safe=True, series=disp,
            notes=(f"vol-scaled displacement into the {key} fix, broker hours {broker_hours} "
                   f"(UTC {utc_hours} + {_BROKER_OFFSET_H}h), {n} bars in window. "
                   f"VALIDATED_PROXY not DIRECT: the mechanism's real observable is the customer "
                   f"ORDER IMBALANCE dealers must absorb; this measures the window in which that "
                   f"flow occurs, not the flow. DST is not modelled -- the window is widened by "
                   f"an hour instead, which cannot silently point at the wrong hour for half the "
                   f"year."))

    def falsification_tests(self, spec: dict[str, Any]) -> list[str]:
        return [
            "shift the fix window by 3 hours -- the effect must vanish, or it is not the fix",
            "test the same displacement far from any fix -- must be flat",
            "month-end should AMPLIFY it; if not, the benchmark-flow story is wrong",
            "cost stress at 3x the fill-hour spread",
        ]


class TermStructureAdapter(ResearchAdapter):
    """Rate-curve slope from free public data. Historical, so usable on the full sample."""

    mechanism = "term_structure"
    requires = ("desks/mt5/data/observables/treasury_rates.json",)

    def _rates(self) -> pd.Series | None:
        path = OBS / "treasury_rates.json"
        if not path.exists():
            return None
        try:
            blob = json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        rows = blob.get("series") or blob.get("data") or []
        recs = []
        for r in rows:
            d = r.get("record_date") or r.get("date")
            v = r.get("avg_interest_rate_amt") or r.get("rate") or r.get("value")
            if d is None or v is None:
                continue
            try:
                recs.append((pd.Timestamp(d, tz="UTC"), float(v)))
            except (ValueError, TypeError):
                continue
        if not recs:
            return None
        # ONE ROW PER SECURITY TYPE PER DATE. Treasury publishes marketable, non-marketable,
        # bills, notes and bonds separately, so the raw index has duplicates and any reindex
        # raises. Averaging across issues on each date is what makes this a LEVEL rather than a
        # curve -- and is exactly why the class below is VALIDATED_PROXY and not DIRECT.
        s = pd.Series([v for _, v in recs], index=pd.DatetimeIndex([d for d, _ in recs]))
        return s.groupby(level=0).mean().sort_index()

    def compatibility(self, spec: dict[str, Any]) -> float:
        return 1.0 if (OBS / "treasury_rates.json").exists() else 0.0

    def measure(self, spec: dict[str, Any], bars: pd.DataFrame) -> MeasurementResult:
        s = self._rates()
        if s is None or s.empty:
            return MeasurementResult(
                status="UNAVAILABLE", adapter="TermStructureAdapter",
                notes=("treasury_rates.json absent or unparseable. The SOURCE is reachable "
                       "(api.fiscaldata.treasury.gov answers without a key) -- this is a fetch "
                       "task, not a missing dataset."))
        idx = pd.DatetimeIndex(bars.index)
        idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
        # Monthly published rates: shift one period so a bar cannot see a figure published later.
        aligned = s.shift(1).reindex(s.index.union(idx)).sort_index().ffill().reindex(idx)
        aligned.index = bars.index
        chg = aligned.diff(24 * 20)          # roughly a month of hourly bars
        return MeasurementResult(
            status="VALIDATED_PROXY", adapter="TermStructureAdapter",
            feature_ids=["treasury_avg_rate_chg"], confidence=0.7, pit_safe=True, series=chg,
            notes=(f"average Treasury interest rate, {len(s)} observations, shifted one period so "
                   f"no bar sees a figure published after it. VALIDATED_PROXY: this is an average "
                   f"across issues rather than a two-point curve SLOPE, which is what a term "
                   f"structure claim strictly needs."))
