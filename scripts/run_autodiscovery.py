"""Autonomous research lab — continuously generate, validate, archive, and promote hypotheses.

Connects to MetaTrader5 READ-ONLY, then runs AutoDiscoveryLab cycles over the fixed 12-family
hypothesis universe. Idempotent (dedup by content hash) and resumable (the candidate ledger +
checkpoint survive any restart). Writes daily/weekly/monthly-style report JSON each cycle. No real
capital is ever allocated; survivors land in REGISTRY for human review only.

Usage:
    python scripts/run_autodiscovery.py --once                 # one cycle, then exit (verification)
    python scripts/run_autodiscovery.py --cycles 0 --interval 3600   # continuous (0 = forever)
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from migrations import MIGRATIONS

from libs.autodiscovery.memory import CandidateStore
from libs.autodiscovery.models import MarketSeries
from libs.autodiscovery.orchestrator import AutoDiscoveryLab
from libs.autodiscovery.reports import (
    discovery_efficiency_report,
    failure_analysis_report,
    family_performance_report,
    pipeline_health_report,
    research_report,
    survivor_report,
)
from libs.autodiscovery.validation import SESSION_DAYS_PER_YEAR
from libs.data.timeframe import Timeframe
from libs.store.connection import Database
from libs.store.migrations import run_migrations

_OUT = Path("reports/autodiscovery")


def _mt5_cost_provider(mt5):  # type: ignore[no-untyped-def]
    """Build a per-symbol per-side cost fraction from REAL MT5 symbol_info (committee T1/T2)."""
    from libs.costs.mt5_calibration import calibrate, per_side_cost_fraction
    from libs.data.instruments import asset_class_for_group

    cache: dict[str, float] = {}

    def cost_for(symbol: str) -> float:
        if symbol in cache:
            return cache[symbol]
        info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if info is None or tick is None or tick.ask <= 0:
            cache[symbol] = 0.0003  # conservative flat fallback
            return cache[symbol]
        ac = asset_class_for_group(info.path)
        params = calibrate(symbol, info, asset_class=ac)
        cache[symbol] = per_side_cost_fraction(params, float(tick.ask))
        return cache[symbol]

    return cost_for


def _mt5_provider(timeframe: str, bars: int, expected_server: str = ""):
    import MetaTrader5 as mt5

    if not mt5.initialize():
        raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")
    acct = mt5.account_info()
    if acct is None or int(acct.trade_mode) != 0:
        mt5.shutdown()
        raise SystemExit("refusing to run: not connected to a DEMO account")
    if expected_server and acct.server != expected_server:
        mt5.shutdown()
        raise SystemExit(f"wrong terminal: got {acct.server!r}, expected {expected_server!r}")
    print(f"connected: server={acct.server} trade_mode=DEMO")
    tf = getattr(mt5, f"TIMEFRAME_{timeframe}", mt5.TIMEFRAME_H1)

    def provider(symbol: str) -> MarketSeries | None:
        mt5.symbol_select(symbol, True)
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)
        if rates is None or len(rates) < 250:
            return None
        hours = np.array([(int(r["time"]) // 3600) % 24 for r in rates], dtype="float64")
        return MarketSeries(
            close=np.array([r["close"] for r in rates], dtype="float64"),
            high=np.array([r["high"] for r in rates], dtype="float64"),
            low=np.array([r["low"] for r in rates], dtype="float64"),
            volume=np.array([r["tick_volume"] for r in rates], dtype="float64"),
            hour=hours,
        )

    return provider


def _write_reports(store: CandidateStore) -> None:
    _OUT.mkdir(parents=True, exist_ok=True)
    reports = {
        "research_report": research_report(store),
        "failure_analysis_report": failure_analysis_report(store),
        "survivor_report": survivor_report(store),
        "family_performance_report": family_performance_report(store),
        "discovery_efficiency_report": discovery_efficiency_report(store),
        "pipeline_health_report": pipeline_health_report(store),
    }
    for name, payload in reports.items():
        (_OUT / f"{name}.json").write_text(json.dumps(payload, indent=2), "utf-8")
    print(f"reports written to {_OUT}/")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default="EURUSD,XAUUSD,US500")
    parser.add_argument("--bars", type=int, default=6000)
    parser.add_argument("--timeframe", default="H1")
    parser.add_argument("--db", default="data/sor_autodiscovery.sqlite")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--cycles", type=int, default=1)  # 0 = forever
    parser.add_argument("--interval", type=float, default=3600.0)
    parser.add_argument("--families", default="", help="comma-separated families; empty = all 12")
    parser.add_argument("--expected-server", default="",
                        help="assert MT5 connected to this server (reproducibility guard)")
    args = parser.parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    from libs.autodiscovery.models import Family

    families = [Family(f.strip()) for f in args.families.split(",") if f.strip()] or None

    db = Database(Path(args.db))
    run_migrations(db, MIGRATIONS)
    provider = _mt5_provider(args.timeframe, args.bars, args.expected_server)
    import MetaTrader5 as mt5  # already initialized by _mt5_provider

    # THE ANNUALISER MUST BE THE BARS ACTUALLY FETCHED (R0086). `_mt5_provider` resolves the
    # timeframe with getattr(..., mt5.TIMEFRAME_H1) -- a silent fallback -- so parse it strictly
    # here first: an interval this desk cannot name is refused loudly rather than fetched as one
    # thing and annualised as another. MT5 instruments are FX/metals/indices, so the session
    # calendar (~252 days) applies, not crypto's 365.
    try:
        bar = Timeframe(str(args.timeframe).upper())
    except ValueError:
        raise SystemExit(
            f"--timeframe {args.timeframe!r} is not a bar interval this desk can annualise; "
            f"use one of {', '.join(t.value for t in Timeframe)}"
        ) from None
    lab = AutoDiscoveryLab(
        db, provider, bar=bar, days_per_year=SESSION_DAYS_PER_YEAR,
        cost_provider=_mt5_cost_provider(mt5), families=families
    )
    print("net-of-cost: per-symbol cost calibrated from live MT5 symbol_info")
    if families:
        print(f"focused families: {[f.value for f in families]}")

    cycles_target = 1 if args.once else args.cycles
    done = 0
    try:
        while cycles_target == 0 or done < cycles_target:
            result = lab.cycle(symbols)
            done += 1
            print(f"[cycle {done}] tested={result.tested} skipped_dup={result.skipped_duplicate} "
                  f"survivors={result.survivors} rejected={result.rejected}")
            _write_reports(lab.store)
            if result.survivors == 0:
                print("  zero survivors this cycle (honest result; nothing promoted).")
            if args.once or (cycles_target and done >= cycles_target):
                break
            time.sleep(args.interval)
    finally:
        import MetaTrader5 as mt5

        mt5.shutdown()
        db.close()


if __name__ == "__main__":
    main()
