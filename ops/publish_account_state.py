"""Publish the live account to `desks/mt5/data/account_state.json`, on a clock.

WHY THIS EXISTS. `build_zentech_state` reads the account two ways: `_mt5_snapshot()` straight
from the terminal, and `desks/mt5/data/account_state.json` as the fallback. On 2026-09-11 the
dashboard published

    account: {'venue': 'UNMEASURED', 'currency': 'UNMEASURED',
              'balance': None, 'equity': None}

on a box whose terminal was connected and answering -- `_mt5_snapshot()` returns the right
numbers when called by hand (equity 607.81 EUR, today_pnl -144.70), but the builder runs on a
schedule alongside the gateway, which holds its own terminal connection every minute, and a
snapshot that loses that race falls through to the file. The file is then consulted and

    NOTHING IN THIS REPOSITORY WRITES IT.

Every reference to account_state.json is a reader or a path list -- `release_identity`'s state
prefixes, `libs.ops.release`, the dashboard builder, a test. The fallback for the desk's most
-read number was a path nobody produced, so the panel read UNMEASURED whenever the live read
missed. That is III.16 exactly: a consumer wired to a producer that does not exist.

WHY A SEPARATE ORGAN AND NOT A LINE IN THE GATEWAY. The gateway is the money path; every edit
there costs a re-seal and a restart of the thing that trades. This needs none of that -- it
reads and writes one small artifact, holds no order authority, and a failed pass leaves the
previous file in place with its own timestamp so staleness stays visible rather than being
papered over with a stale number presented as current.

    python ops/publish_account_state.py
"""
from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "desks" / "mt5" / "data" / "account_state.json"
sys.path.insert(0, str(ROOT / "desks" / "mt5"))
if str(ROOT) not in sys.path:  # libs.ops.mt5_readonly (ARCH-12)
    sys.path.insert(0, str(ROOT))
from research.mt5_session import attach_or_initialize  # noqa: E402

#: Fields copied from each open position (MT5 `TradePosition`). The comment is the sleeve tag
#: the gateway writes, and the ticket is the order that opened it -- what the reconciliation
#: (`desks/mt5/research/execution_reconcile.py`) joins to the order door's ledger.
POSITION_FIELDS = ("ticket", "symbol", "type", "volume", "price_open", "sl", "tp", "profit",
                   "swap", "magic", "comment", "time", "identifier")


def _f(x: Any, nd: int = 2) -> float | None:
    """A finite rounded float, or None: a non-number never reaches the ledger as a number."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, nd) if math.isfinite(v) else None


def _position(p: Any) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for k in POSITION_FIELDS:
        v = getattr(p, k, None)
        if k in ("ticket", "type", "magic", "time", "identifier"):
            try:
                row[k] = int(v) if v is not None else None
            except (TypeError, ValueError):
                row[k] = None
        elif k in ("symbol", "comment"):
            row[k] = str(v) if v is not None else None
        else:
            row[k] = _f(v, 8 if k in ("price_open", "sl", "tp", "volume") else 2)
    return row


def build_record(info: Any, deals: Any, positions: Any, now: datetime) -> dict[str, Any]:
    """The account ledger record: cash, margin, financing and every open position in ONE file.

    THE ACCOUNT LEDGER WAS NOT AUTHORITATIVE (ARCH-06, recovery_drills row `account_ledger`).
    This published balance, equity, free margin and a position COUNT -- so used margin, the
    margin level, the swap the book is carrying and which positions are open were in no artifact
    at all, and nothing could reconcile the venue's positions against the order door's ledger.
    `margin`, `margin_level`, `swap` (open financing) and `positions` close that; the totals are
    recomputed from the positions so a reader can check the record against itself
    (`ledger_check`).
    """
    closed = 0.0
    for d in deals:
        closed += float(getattr(d, "profit", 0.0) or 0.0)
        closed += float(getattr(d, "commission", 0.0) or 0.0)
        closed += float(getattr(d, "swap", 0.0) or 0.0)
    rows = [_position(p) for p in positions]
    floating = sum(float(getattr(p, "profit", 0.0) or 0.0) for p in positions)
    swap_open = sum(float(getattr(p, "swap", 0.0) or 0.0) for p in positions)
    balance = float(info.balance)
    equity = float(info.equity)
    margin = _f(getattr(info, "margin", None))
    level = _f(getattr(info, "margin_level", None))
    if level is None and margin:
        level = round(equity / margin * 100.0, 2)     # MT5's own definition, in percent
    # equity = balance + floating P&L + open swap (commission is charged at the deal): the
    # residual is what a reader would otherwise have to discover by hand.
    residual = round(equity - (balance + floating + swap_open), 2)
    return {
        "updated_at": now.isoformat(timespec="seconds"),
        "source": "ops/publish_account_state.py",
        "venue": str(getattr(info, "company", "") or "") or None,
        "server": str(getattr(info, "server", "") or "") or None,
        # The login is WITHHELD: this file is committed by the box, and a tracked file must never
        # name the live account (tests/ops/test_live_infrastructure_is_not_published.py). No
        # reader takes it from here; provenance reads mt5.account_info().login from the terminal.
        "login_withheld": info.login is not None,
        "currency": str(info.currency),
        "balance": round(balance, 2),
        "equity": round(equity, 2),
        "margin": margin,
        "margin_free": round(float(info.margin_free), 2),
        "margin_level": level,
        "swap": round(swap_open, 2),
        "today_pnl": round(closed + floating, 2),
        "today_closed_pnl": round(closed, 2),
        "today_floating_pnl": round(floating, 2),
        "open_positions": len(rows),
        "positions": rows,
        "ledger_check": {
            "equity_minus_balance_floating_swap": residual,
            "consistent": abs(residual) <= max(0.05, abs(equity) * 1e-4),
            "rule": "equity == balance + sum(position profit) + sum(position swap)",
        },
    }


def main() -> int:
    try:
        from libs.ops.mt5_readonly import readonly_mt5  # read-only terminal (ARCH-12)
        mt5 = readonly_mt5()
    except Exception as exc:  # the research box has no terminal; absence is not an error
        print(f"MetaTrader5 unavailable: {type(exc).__name__}: {exc}")
        return 0

    if not attach_or_initialize(mt5, timeout=15000):
        # LEAVE THE OLD FILE ALONE. Writing a null-filled record here would turn "I could not
        # reach the terminal this minute" into a published verdict that the account is empty --
        # the same confusion the dashboard already shipped once.
        print(f"terminal unreachable: {mt5.last_error()}; previous file left in place")
        return 1

    info = mt5.account_info()
    if info is None:
        print("account_info() returned None; previous file left in place")
        return 1

    now = datetime.now(UTC)
    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    deals = mt5.history_deals_get(day0, now)
    positions = mt5.positions_get()
    if deals is None or positions is None:
        print("broker history or positions unavailable; previous file left in place")
        return 1
    rec = build_record(info, deals, positions, now)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    tmp.replace(OUT)          # atomic, so a reader never sees a half-written record
    print(f"wrote {OUT.name}: equity {rec['equity']} {rec['currency']} "
          f"today_pnl {rec['today_pnl']} positions {rec['open_positions']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
