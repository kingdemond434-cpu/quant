"""Demo runner — the end-to-end runtime loop on a demo/paper venue (no live capital).

Drives one process through the full stack for each feed batch:
  Feed -> Stage 13.5 SignalEngine -> Stage 14 PortfolioConstructionEngine -> Risk Gate
  -> Execution (PaperBroker) -> Monitoring + immutable audit.

Fail-closed and structural: an order can only be placed with a ``risk_approval_id`` minted by the
risk gate; a rejected intent never reaches the broker. Deterministic given a deterministic feed.
The only thing swapped vs production is the venue (PaperBroker) and the feed (ReplayFeed) — the
decision path is identical to live.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from app.dashboard import DashboardState, build_dashboard
from app.feed import Feed
from libs.execution.broker import BrokerGateway, OrderRequest
from libs.execution.engine import ExecStatus, ExecutionEngine
from libs.execution.journal import TradeJournal
from libs.execution.paper_broker import PaperBroker
from libs.monitoring.models import Op, Severity, Threshold
from libs.monitoring.monitor import MonitorService
from libs.risk.gate import AccountState, OrderIntent, risk_gate
from libs.signal_engine.engine import SignalEngine, SymbolObservation
from libs.signal_engine.models import Direction
from libs.stage14.audit import PortfolioAudit
from libs.stage14.engine import PortfolioConstructionEngine
from libs.store.connection import Database
from libs.store.registries import RiskRegistry
from libs.store.trading import OrderStore


class DemoRunResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticks_processed: int
    signals_generated: int
    allocations: int
    orders_submitted: int
    orders_filled: int
    risk_rejections: int
    dashboard: DashboardState


class DemoRunner:
    """Runs the full stack against a feed on the paper venue (demo only)."""

    def __init__(
        self,
        db: Database,
        *,
        capital: float = 100_000.0,
        default_price: float = 100.0,
        drawdown_alert: float = 0.10,
        broker: BrokerGateway | None = None,
    ) -> None:
        self.db = db
        self.capital = capital
        self.signal_engine = SignalEngine()
        self.portfolio_engine = PortfolioConstructionEngine(audit=PortfolioAudit(db))
        self.broker: BrokerGateway = (
            broker if broker is not None else PaperBroker(default_price=default_price)
        )
        self.execution = ExecutionEngine(OrderStore(db), self.broker, TradeJournal(db))
        self.registry = RiskRegistry(db)
        self.monitor = MonitorService(
            db,
            [Threshold(metric="drawdown", op=Op.GT, value=drawdown_alert,
                       severity=Severity.CRITICAL, message="drawdown breach")],
        )
        self._default_price = default_price

    def run(self, feed: Feed, *, max_ticks: int = 1000) -> DemoRunResult:
        totals = [0, 0, 0, 0, 0]  # signals, allocations, submitted, filled, rejections
        ticks = 0
        while ticks < max_ticks:
            batch = feed.poll()
            if not batch:
                break
            ticks += 1
            counts = self.process_batch(batch, tag=str(ticks))
            totals = [t + c for t, c in zip(totals, counts, strict=True)]
        return DemoRunResult(
            ticks_processed=ticks, signals_generated=totals[0], allocations=totals[1],
            orders_submitted=totals[2], orders_filled=totals[3], risk_rejections=totals[4],
            dashboard=build_dashboard(self.db),
        )

    def process_batch(
        self, observations: Sequence[SymbolObservation], *, tag: str = "live"
    ) -> tuple[int, int, int, int, int]:
        """One pipeline pass: signals -> portfolio -> risk -> execution -> monitoring.

        Returns (signals, allocations, orders_submitted, orders_filled, risk_rejections). Used by
        the offline drain loop AND the live timed loop, so both share one decision path.
        """
        selection = self.signal_engine.evaluate(observations)
        signals = len(selection.approved)
        if not selection.approved:
            self.monitor.record("equity", self.capital)
            return (signals, 0, 0, 0, 0)
        direction_by_symbol = {sp.symbol: sp.direction for sp in selection.approved}
        confidence_by_symbol = {sp.symbol: sp.confidence for sp in selection.approved}
        portfolio = self.portfolio_engine.construct(selection.approved, capital=self.capital)
        submitted = filled = rejections = 0
        for pkg in portfolio.packages:
            direction = direction_by_symbol.get(pkg.symbol, Direction.FLAT)
            if direction is Direction.FLAT:
                continue
            f, s, r = self._execute(
                pkg.symbol, direction, pkg, confidence_by_symbol.get(pkg.symbol, 1.0),
                key=f"{tag}-{pkg.symbol}",
            )
            submitted += s
            filled += f
            rejections += r
        self.monitor.record("equity", self.capital, tags={"tag": tag})
        self.monitor.record("drawdown", 0.0)
        return (signals, len(portfolio.packages), submitted, filled, rejections)

    def _execute(
        self, symbol: str, direction: Direction, pkg: object, confidence: float, *, key: str
    ) -> tuple[int, int, int]:
        """Risk-gate then place one order via the configured venue. -> (filled, submitted, rej)."""
        from libs.stage14.models import PortfolioPackage

        assert isinstance(pkg, PortfolioPackage)
        side = "buy" if direction is Direction.BUY else "sell"
        setter = getattr(self.broker, "set_price", None)
        if callable(setter):
            setter(symbol, self._default_price)  # paper venue only; real venues fill at market
        intent = OrderIntent(
            instrument=symbol, side=side,
            kelly_fraction=max(0.01, pkg.kelly_fraction),
            risk_budget=max(0.001, pkg.allocation),
            risk_per_unit=max(1e-6, self._default_price * 0.01),
            confidence=confidence,
        )
        account = AccountState(equity=self.capital, peak_equity=self.capital, forecast_vol=0.15)
        decision = risk_gate(intent, account, registry=self.registry)
        if not decision.approved or decision.risk_approval_id is None or decision.sized_units <= 0:
            return 0, 0, 1
        request = OrderRequest(
            idempotency_key=key, instrument=symbol, side=side, qty=decision.sized_units,
            order_type="market", risk_approval_id=decision.risk_approval_id,
        )
        result = self.execution.submit_order(request)
        return (1 if result.status is ExecStatus.FILLED else 0), 1, 0
