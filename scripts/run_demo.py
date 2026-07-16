"""Run the end-to-end demo on a deterministic replay feed + PaperBroker (no live capital).

Usage: python scripts/run_demo.py [--db data/sor_demo.sqlite] [--ticks 10]
Demonstrates: signals -> portfolio -> risk gate -> paper execution -> monitoring -> audit,
then prints the resulting dashboard snapshot. For a live MT5 feed, swap ReplayFeed for MT5Feed
(requires the MetaTrader5 package + a running terminal; see config/mt5.example.yaml).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from migrations import MIGRATIONS

from app.demo_runner import DemoRunner
from app.feed import ReplayFeed
from libs.signal_engine.engine import SymbolObservation
from libs.signal_engine.models import AlphaSignal, Direction, MarketState, Regime
from libs.store.connection import Database
from libs.store.migrations import run_migrations


def _scripted_tick() -> list[SymbolObservation]:
    """A single, corroborated BUY observation for EURUSD (deterministic demo input)."""
    signals = [
        AlphaSignal(
            alpha_id=f"{name}_1", symbol="EURUSD", direction=Direction.BUY, strength=0.9,
            expected_return=0.01, win_rate=0.6, avg_win=0.012, avg_loss=0.008, profit_factor=1.8,
            sharpe=1.8, health_score=95.0, regime_affinity={Regime.TREND.value: 1.0},
            governance_passed=True,
        )
        for name in ("trend", "momentum")
    ]
    state = MarketState(symbol="EURUSD", regime=Regime.TREND, predicted_regime=Regime.TREND,
                        volatility_state=0.2)
    return [SymbolObservation(signals=signals, state=state)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/sor_demo.sqlite")
    parser.add_argument("--ticks", type=int, default=5)
    args = parser.parse_args()

    path = Path(args.db)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(path)
    try:
        run_migrations(db, MIGRATIONS)
        feed = ReplayFeed([_scripted_tick() for _ in range(args.ticks)])
        result = DemoRunner(db).run(feed)
    finally:
        db.close()

    print(f"ticks={result.ticks_processed} signals={result.signals_generated} "
          f"allocations={result.allocations} orders_filled={result.orders_filled} "
          f"risk_rejections={result.risk_rejections}")
    print("dashboard:", result.dashboard.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
