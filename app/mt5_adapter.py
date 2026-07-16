"""MetaTrader5 adapter — the production bridge between the Python stack and the MT5 terminal.

Connects to a running MetaTrader5 terminal via the ``MetaTrader5`` package: login, fetch bars and
ticks, read account/positions. This is the live data + account ingestion path. It CANNOT run in a
headless sandbox (no terminal, package absent); it is guarded so the rest of the stack stays
importable, and every call fails closed with a clear error when MT5 is unavailable.

NOTE: the modern MT5<->Python bridge is this package talking to the terminal directly; an
in-terminal Expert Advisor is only needed for terminal-side automation, not this data/account path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from libs.execution.errors import BrokerError


@dataclass(frozen=True)
class Bar:
    time: int
    open: float
    high: float
    low: float
    close: float
    tick_volume: float


@dataclass(frozen=True)
class Tick:
    time: int
    bid: float
    ask: float


@dataclass(frozen=True)
class AccountInfo:
    login: int
    balance: float
    equity: float
    margin_free: float
    currency: str


class MT5Adapter:  # pragma: no cover - requires a live Windows MT5 terminal + MetaTrader5 package
    """Live connection to a MetaTrader5 terminal. Demo or live account; data + account ingestion."""

    def __init__(
        self,
        *,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        terminal_path: str | None = None,
    ) -> None:
        try:
            import MetaTrader5 as mt5
        except ImportError as exc:
            raise BrokerError("the MetaTrader5 package is not installed") from exc
        self._mt5 = mt5
        ok = mt5.initialize(path=terminal_path) if terminal_path else mt5.initialize()
        if not ok:
            raise BrokerError(f"MT5 initialize() failed: {mt5.last_error()}")
        if login is not None and not mt5.login(login, password=password, server=server):
            raise BrokerError(f"MT5 login() failed: {mt5.last_error()}")

    def fetch_bars(self, symbol: str, *, timeframe: str = "H1", count: int = 500) -> list[Bar]:
        mt5 = self._mt5
        tf = getattr(mt5, f"TIMEFRAME_{timeframe}", mt5.TIMEFRAME_H1)
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None:
            raise BrokerError(f"copy_rates failed for {symbol}: {mt5.last_error()}")
        return [
            Bar(time=int(r["time"]), open=float(r["open"]), high=float(r["high"]),
                low=float(r["low"]), close=float(r["close"]), tick_volume=float(r["tick_volume"]))
            for r in rates
        ]

    def latest_tick(self, symbol: str) -> Tick:
        info = self._mt5.symbol_info_tick(symbol)
        if info is None:
            raise BrokerError(f"symbol_info_tick failed for {symbol}")
        return Tick(time=int(info.time), bid=float(info.bid), ask=float(info.ask))

    def account_info(self) -> AccountInfo:
        info: Any = self._mt5.account_info()
        if info is None:
            raise BrokerError("account_info failed")
        return AccountInfo(
            login=int(info.login), balance=float(info.balance), equity=float(info.equity),
            margin_free=float(info.margin_free), currency=str(info.currency),
        )

    def shutdown(self) -> None:
        self._mt5.shutdown()
