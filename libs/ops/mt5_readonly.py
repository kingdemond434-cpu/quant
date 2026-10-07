"""A READ-ONLY MetaTrader5 terminal for everything that is not the order path (ARCH-12).

THE DEFECT (PM delivery check, 2026-10-07). Research modules opened the raw `MetaTrader5` module to
read bars, ticks and symbol facts. The same module object carries `order_send`, `order_delete`
and the package's own `Buy` / `Sell` / `Close` helpers, so a research job on the trading box held
a live connection that COULD place, modify or close an order on the live account -- by a bug, a
copied snippet, or an LLM-suggested line -- with nothing between it and the venue. The
architecture says: research proposes, the gateway's order door executes, and nothing else holds
order authority.

WHAT THIS IS. `readonly_mt5()` returns a proxy over the real module that exposes:
  * every NON-callable attribute (TIMEFRAME_*, COPY_TICKS_*, ORDER_TYPE_* constants...), so
    existing read code keeps working unchanged;
  * ONLY the callables in READ_FUNCS -- data and state reads (bars, ticks, symbols, account and
    terminal info, positions/orders/history reads, margin and profit calculators, the order
    book, `initialize` / `shutdown` / `last_error` / `version`).
Any other callable -- `order_send`, `order_delete`, `Buy`, `Sell`, `Close`, `login`, or a trading
function a future package version adds -- raises `ReadOnlyTerminalError`. It is an ALLOWLIST,
so a new write function is refused by default rather than leaked by omission.

`initialize` refuses `login` / `password` / `server` arguments: research attaches to the terminal
the box already runs and never carries account credentials (ARCH-12: AI researchers hold no
production trading credentials).

The real module is never handed out. The fence `scripts/check_order_authority.py` fails any
module outside the order path that imports MetaTrader5 directly or calls `order_send`.

`ImportError` behaves exactly as `import MetaTrader5` did, so callers' "terminal absent" branches
are unchanged.
"""
from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any

#: The callables a non-order-path module may use. Reads and pure calculators only.
READ_FUNCS: frozenset[str] = frozenset({
    "initialize", "shutdown", "last_error", "version", "terminal_info", "account_info",
    "symbols_total", "symbols_get", "symbol_info", "symbol_info_tick", "symbol_select",
    "market_book_add", "market_book_get", "market_book_release",
    "copy_rates_from", "copy_rates_from_pos", "copy_rates_range",
    "copy_ticks_from", "copy_ticks_range",
    "orders_total", "orders_get", "positions_total", "positions_get",
    "history_orders_total", "history_orders_get", "history_deals_total", "history_deals_get",
    "order_calc_margin", "order_calc_profit",
})
#: Credentials research must never pass to the terminal.
CREDENTIAL_ARGS: frozenset[str] = frozenset({"login", "password", "server"})


class ReadOnlyTerminalError(PermissionError):
    """A non-order-path module reached for a terminal function that is not a read."""


class ReadOnlyMT5:
    """The MetaTrader5 module, minus every way to change the account."""

    __slots__ = ("__mod",)

    def __init__(self, module: ModuleType) -> None:
        object.__setattr__(self, "_ReadOnlyMT5__mod", module)

    def __getattr__(self, name: str) -> Any:
        mod = object.__getattribute__(self, "_ReadOnlyMT5__mod")
        value = getattr(mod, name)
        if not callable(value) or isinstance(value, type):
            return value
        if name not in READ_FUNCS:
            raise ReadOnlyTerminalError(
                f"MetaTrader5.{name} is not a read: research holds a read-only terminal; orders "
                "go through the gateway's order door (desks/mt5/mt5desk/order_door.py)")
        if name == "initialize":
            return _initialize(value)
        return value

    def __setattr__(self, name: str, value: Any) -> None:
        raise ReadOnlyTerminalError("the read-only terminal cannot be modified")

    def __dir__(self) -> list[str]:
        mod = object.__getattribute__(self, "_ReadOnlyMT5__mod")
        return [n for n in dir(mod) if n in READ_FUNCS or not callable(getattr(mod, n, None))]

    def __repr__(self) -> str:
        return "<MetaTrader5 (read-only)>"


def _initialize(fn: Any) -> Any:
    def initialize(*args: Any, **kwargs: Any) -> Any:
        bad = sorted(CREDENTIAL_ARGS & set(kwargs))
        if bad or len(args) > 1:
            raise ReadOnlyTerminalError(
                f"research may not pass account credentials to the terminal ({bad or 'positional'})"
                ": attach to the terminal the box already runs")
        return fn(*args, **kwargs)
    return initialize


def readonly_mt5() -> ReadOnlyMT5:
    """The read-only terminal. Raises ImportError where MetaTrader5 is not installed."""
    return ReadOnlyMT5(importlib.import_module("MetaTrader5"))


def mt5_available() -> bool:
    """Whether the MetaTrader5 package is importable, without handing out the module."""
    try:
        importlib.import_module("MetaTrader5")
    except ImportError:
        return False
    return True
