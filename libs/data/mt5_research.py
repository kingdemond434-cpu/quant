"""MT5 research-session safety and the canonical liquid intraday universe.

Data collection may use either a demo login or an investor/read-only live login.  A live login is
accepted only when account trading authority is false and the expected broker server is pinned.
This module contains no order API and grants no execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

LIQUID_INTRADAY_CORE: tuple[str, ...] = (
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "USDCHF",
    "AUDUSD",
    "USDCAD",
    "NZDUSD",
    "EURJPY",
    "GBPJPY",
    "EURGBP",
    "AUDJPY",
    "EURAUD",
    "XAUUSD",
    "XAGUSD",
    "XTIUSD",
    "XBRUSD",
    "XNGUSD",
    "US500",
    "NAS100",
    "US30",
    "US2000",
    "GER40",
    "UK100",
    "JPN225",
    "USDX",
    "BTCUSD",
    "ETHUSD",
)


@dataclass(frozen=True)
class ResearchSessionVerdict:
    allowed: bool
    mode: str
    reason: str


def research_session_verdict(
    account: Any,
    terminal: Any,
    *,
    expected_server: str = "",
    allow_readonly_live: bool = False,
) -> ResearchSessionVerdict:
    """Fail closed unless the MT5 session is demo or provably investor/read-only live."""
    if account is None or terminal is None:
        return ResearchSessionVerdict(False, "UNAVAILABLE", "account or terminal info unavailable")
    server = str(getattr(account, "server", ""))
    if expected_server and server != expected_server:
        return ResearchSessionVerdict(
            False, "WRONG_SERVER", f"server {server!r} != expected {expected_server!r}"
        )
    if int(getattr(account, "trade_mode", -1)) == 0:
        return ResearchSessionVerdict(True, "DEMO", "demo account")
    if not allow_readonly_live:
        return ResearchSessionVerdict(
            False, "LIVE_REFUSED", "live account needs explicit read-only mode"
        )
    if not expected_server:
        return ResearchSessionVerdict(
            False, "UNPINNED_LIVE", "read-only live research requires --expected-server"
        )
    if bool(getattr(account, "trade_allowed", True)):
        return ResearchSessionVerdict(False, "ACCOUNT_CAN_TRADE", "account trading flag is enabled")
    # This is a terminal-wide UI switch, not account authority. Brokers commonly leave it enabled
    # for investor logins; the authenticated account's immutable permission is the safety boundary.
    terminal_mode = (
        "terminal-switch-on"
        if bool(getattr(terminal, "trade_allowed", False))
        else "terminal-switch-off"
    )
    return ResearchSessionVerdict(
        True, "INVESTOR_READONLY", f"server-pinned investor account ({terminal_mode})"
    )
