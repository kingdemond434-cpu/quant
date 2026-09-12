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
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "desks" / "mt5" / "data" / "account_state.json"


def main() -> int:
    try:
        import MetaTrader5 as mt5
    except Exception as exc:  # the research box has no terminal; absence is not an error
        print(f"MetaTrader5 unavailable: {type(exc).__name__}: {exc}")
        return 0

    if mt5.terminal_info() is None and not mt5.initialize():
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
    closed = 0.0
    for d in mt5.history_deals_get(day0, now) or ():
        closed += float(getattr(d, "profit", 0.0) or 0.0)
        closed += float(getattr(d, "commission", 0.0) or 0.0)
        closed += float(getattr(d, "swap", 0.0) or 0.0)
    floating = sum(float(getattr(p, "profit", 0.0) or 0.0) for p in (mt5.positions_get() or ()))

    rec = {
        "updated_at": now.isoformat(timespec="seconds"),
        "source": "ops/publish_account_state.py",
        "venue": str(getattr(info, "company", "") or "") or None,
        "server": str(getattr(info, "server", "") or "") or None,
        "login": int(info.login),
        "currency": str(info.currency),
        "balance": round(float(info.balance), 2),
        "equity": round(float(info.equity), 2),
        "margin_free": round(float(info.margin_free), 2),
        "today_pnl": round(closed + floating, 2),
        "today_closed_pnl": round(closed, 2),
        "today_floating_pnl": round(floating, 2),
        "open_positions": len(mt5.positions_get() or ()),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    tmp.replace(OUT)          # atomic, so a reader never sees a half-written record
    print(f"wrote {OUT.name}: equity {rec['equity']} {rec['currency']} "
          f"today_pnl {rec['today_pnl']} positions {rec['open_positions']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
