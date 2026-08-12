#!/usr/bin/env python3
"""STAGE-A RUNNER: mechanical supply release as a schedule-SERIES (census gap #3, score 0.360).

All pre-registration -- mechanism, constructions, horizons, alignment, multiplicity charge --
lives in the module docstring of `libs/research/unlock_supply_series.py` and was written before
any number was computed.  This file only wires it to disk and writes the artifact; it contains
no thresholds and no analysis, so there is nothing here to tune after seeing a result.

TWO DEFECTS FIXED 2026-08-12 (R0385, raised 2026-08-05, never disposed):
  1. libs/research/unlock_supply_series.py's instant parser never consulted the schedule file's
     `ts` (epoch-seconds) field -- data/unlock_events.json carries no `instant`/`timestamp`, only
     `ts` and a bare `date` string that _as_utc correctly rejects as naive. All 24,201 rows were
     silently dropped; the weekly screen ran, exited 0, and reported NOT-READABLE-HERE every time,
     indistinguishable from a healthy quiet screen unless someone opened the artifact.
  2. THIS FILE passed bars=None unconditionally, so run_screen() reported the price panel missing
     regardless of the schedule fix -- the docstring's own "data/binance_vision/" claim named a
     path that was never real; the desk's actual price source is the bronze crypto lake used
     everywhere else (screen_cme_basis.py, run_discovery.py). Now loads D1 closes for exactly the
     symbols the schedule names, skipping (not crashing on) any symbol absent from the lake.

Fixing the parser changes this screen's INPUT from 0 rows to a real count -- a screen re-run with
a real result, not a typo repair -- so the resulting verdict must be read once produced, not
assumed. First real run is this file's own next scheduled fire (Monday 06:25 UTC); check
reports/axis_screens/unlock_supply_series.json's `verdict` and `missing_inputs` then, the same
"built ran exited 0 produced nothing" class this desk has already been burned by once (R0385's own
framing) -- do not assume READABLE until that artifact is actually read.

INTENDED CADENCE (header comment only -- ops/crontab.manifest is owned by another pass):
    # 25 6 * * 1   weekly, Monday 06:25 UTC, after the unlock-calendar and circulating-supply
    #              collectors would have landed.  Weekly because the mechanism is a 7-30 day
    #              forward window: a daily re-read would re-test the same overlapping window and
    #              inflate the trial count without adding independent evidence.

    python scripts/screen_unlock_supply_series.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument  # noqa: E402
from libs.data.lake import Layer, ParquetLake  # noqa: E402
from libs.data.timeframe import Timeframe  # noqa: E402
from libs.research.unlock_supply_series import load_unlock_schedule, run_screen  # noqa: E402

_OUT = _ROOT / "reports/axis_screens/unlock_supply_series.json"
_SCHEDULE = _ROOT / "data/unlock_events.json"
_SUPPLY = _ROOT / "data/circulating_supply.jsonl"


def _load_bars(symbols: set[str]) -> dict[str, tuple[tuple[datetime, ...], np.ndarray]]:
    """D1 closes for exactly the symbols the unlock schedule names, from the bronze crypto lake.

    Ticker -> {TICKER}USDT matches the convention every other crypto screen on this desk uses
    (screen_cme_basis.py, run_discovery.py). A symbol absent from the lake is SKIPPED, never a
    crash -- run_screen() already reports a thin/empty panel as a named missing input."""
    lake = ParquetLake("data/lake")
    out: dict[str, tuple[tuple[datetime, ...], np.ndarray]] = {}
    for sym in sorted(symbols):
        ticker = f"{sym}USDT"
        # ParquetLake.path() resolves through the instrument registry (get_spec), which raises
        # DataError on an unregistered symbol -- register before every read, matching the exact
        # pattern screen_cme_basis.py/run_discovery.py already use for the same lake.
        register_instrument(InstrumentSpec(symbol=ticker, asset_class=AssetClass.CRYPTO,
                                           description=ticker))
        df = lake.read_bars(Layer.BRONZE, ticker, Timeframe.D1)
        if df.empty:
            continue
        instants = tuple(ts.to_pydatetime() for ts in df["timestamp"])
        out[sym] = (instants, df["close"].to_numpy(dtype=float))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="print the artifact to stdout")
    args = ap.parse_args()

    schedule = load_unlock_schedule(_SCHEDULE)
    symbols = {r.symbol for r in schedule.releases}
    bars = _load_bars(symbols) if symbols else {}

    report = run_screen(schedule_path=_SCHEDULE, supply_path=_SUPPLY, bars=bars or None)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=1))
    else:
        print(f"status : {report['status']}")
        print(f"verdict: {report['verdict']}")
        print(f"power  : {report['power']['label']} -- {report['power']['note']}")
        for miss in report.get("missing_inputs", []):
            print(f"MISSING: {miss}")
        print(f"cells declared: {len(report.get('cells_declared', report.get('cells', [])))}")
        print(f"artifact: {_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

