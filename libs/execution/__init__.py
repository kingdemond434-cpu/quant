"""``libs.execution`` — the MT5 execution engine.

Submits approved orders to a broker gateway with idempotency and safe retries, tracks positions,
reconciles against the broker (the source of truth), and journals every event immutably. No
duplicate orders; safe restart; fail closed.
"""

from __future__ import annotations

from libs.execution.algos import ChildOrder, ExecutionPlan, ExecutionScheduler
from libs.execution.broker import (
    BrokerGateway,
    BrokerOrderResult,
    BrokerPosition,
    MT5Broker,
    OrderRequest,
)
from libs.execution.ea_bridge import EABridge, dump_record, load_record
from libs.execution.engine import (
    ExecStatus,
    ExecutionEngine,
    ExecutionResult,
    ReconciliationReport,
)
from libs.execution.errors import (
    BrokerError,
    BrokerTimeout,
    ExecutionError,
    ReconciliationError,
    TransientBrokerError,
)
from libs.execution.journal import TradeJournal
from libs.execution.paper_broker import PaperBroker
from libs.execution.retry import retry_call
from libs.execution.tca import PostTradeTCA, SlippageAttribution, TcaResult

__all__ = [  # noqa: RUF022  # grouped by concern
    # broker
    "BrokerGateway",
    "OrderRequest",
    "BrokerOrderResult",
    "BrokerPosition",
    "MT5Broker",
    "PaperBroker",
    "EABridge",
    "dump_record",
    "load_record",
    # engine
    "ExecutionEngine",
    "ExecutionResult",
    "ReconciliationReport",
    "ExecStatus",
    # execution algos
    "ExecutionScheduler",
    "ExecutionPlan",
    "ChildOrder",
    # post-trade TCA
    "PostTradeTCA",
    "SlippageAttribution",
    "TcaResult",
    # journal + retry
    "TradeJournal",
    "retry_call",
    # errors
    "ExecutionError",
    "BrokerError",
    "TransientBrokerError",
    "BrokerTimeout",
    "ReconciliationError",
]
