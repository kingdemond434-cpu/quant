"""LIVE DEMO TRADING ENTRYPOINT — connect MT5, generate signals, place demo trades.

This is the only script that does all three on a live MT5 DEMO account:
  1. Connects to the MetaTrader5 terminal (aborts unless the account is a DEMO account).
  2. Pulls real bars and generates signals via the pre-registered strategy layer
     (app.signal_builder.build_live_signals) -> Stage 13.5 -> Stage 14 -> risk gate.
  3. Places demo trades through the execution venue:
       --venue ea    : via the hardened MT5 Execution EA (QuantPlatformExecutor.mq5, must be
                       attached to a chart). Python -> file queue -> EA -> demo account.  [default]
       --venue paper : via the in-process PaperBroker (no real orders) — for a dry run.

It loops every --interval seconds for --minutes, then stops. NO live (real-money) trading: the
script refuses any account whose trade_mode is not DEMO.

Usage (from the project root, venv active):
    python scripts/run_live_demo.py --minutes 30 --interval 60 --venue ea \
        --symbols EURUSD,XAUUSD --comm-dir "<MT5 common>/Files/quant_ea"
"""

from __future__ import annotations

import argparse
import time
from datetime import UTC, datetime
from pathlib import Path

from migrations import MIGRATIONS

from app.demo_runner import DemoRunner
from app.feed import MT5Feed
from app.mt5_adapter import MT5Adapter
from app.signal_builder import build_live_signals
from libs.execution.broker import BrokerGateway
from libs.execution.ea_bridge import EABridge
from libs.execution.paper_broker import PaperBroker
from libs.store.connection import Database
from libs.store.migrations import run_migrations


def _make_broker(venue: str, comm_dir: str) -> BrokerGateway:
    if venue == "ea":
        return EABridge(Path(comm_dir))  # Python -> file queue -> the MT5 Execution EA
    if venue == "paper":
        return PaperBroker()
    raise SystemExit(f"unknown venue {venue!r} (use 'ea' or 'paper')")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default="EURUSD,XAUUSD")
    parser.add_argument("--minutes", type=float, default=30.0)
    parser.add_argument("--interval", type=float, default=60.0)
    parser.add_argument("--venue", choices=("ea", "paper"), default="ea")
    parser.add_argument("--comm-dir", default="data/quant_ea")
    parser.add_argument("--db", default="data/sor_live_demo.sqlite")
    parser.add_argument("--capital", type=float, default=100_000.0)
    parser.add_argument("--timeframe", default="H1")
    args = parser.parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

    # 1) Connect to MT5 and HARD-GATE on a demo account.
    adapter = MT5Adapter()
    acct = adapter.account_info()
    if acct.login and getattr(acct, "currency", None) is None:
        adapter.shutdown()
        raise SystemExit("could not read MT5 account info")
    mode = _trade_mode(adapter)
    if mode != 0:
        adapter.shutdown()
        raise SystemExit(f"refusing to run: account trade_mode={mode} is not DEMO (0)")
    print(f"connected: login={acct.login} currency={acct.currency} trade_mode=DEMO")

    # 2) Wire the live feed (real bars -> pre-registered signals) and the venue.
    feed = MT5Feed(adapter, symbols, signal_builder=build_live_signals, timeframe=args.timeframe)
    broker = _make_broker(args.venue, args.comm_dir)
    db = Database(Path(args.db))
    run_migrations(db, MIGRATIONS)
    runner = DemoRunner(db, capital=args.capital, broker=broker)

    # 3) Live loop: poll -> full pipeline -> place demo trades -> heartbeat -> sleep.
    deadline = time.monotonic() + args.minutes * 60.0
    totals = [0, 0, 0, 0, 0]
    try:
        while time.monotonic() < deadline:
            if isinstance(broker, EABridge):
                broker.write_heartbeat()
            observations = feed.poll()
            counts = runner.process_batch(observations, tag=datetime.now(UTC).strftime("%H%M%S"))
            totals = [t + c for t, c in zip(totals, counts, strict=True)]
            print(f"[{datetime.now(UTC):%H:%M:%S}] signals={counts[0]} alloc={counts[1]} "
                  f"submitted={counts[2]} filled={counts[3]} rejected={counts[4]}")
            time.sleep(args.interval)
    finally:
        adapter.shutdown()
        db.close()

    print(f"\nLIVE DEMO SESSION DONE: signals={totals[0]} allocations={totals[1]} "
          f"orders_submitted={totals[2]} orders_filled={totals[3]} risk_rejections={totals[4]}")


def _trade_mode(adapter: MT5Adapter) -> int:
    import MetaTrader5 as mt5

    info = mt5.account_info()
    return int(info.trade_mode) if info is not None else -1


if __name__ == "__main__":
    main()
