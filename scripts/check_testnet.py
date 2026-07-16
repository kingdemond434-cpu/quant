"""Verify the Binance testnet connection -- run this right after adding your keys.

Confirms the keys are picked up, the account is reachable, and shows balance, open positions, and
the last few recorded trades. Read-only -- places no orders. Run before --live to confirm wiring.

    python scripts/check_testnet.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from libs.execution import binance_testnet as bt

_DB = Path("data/crypto_trades.sqlite")


def main() -> None:
    print(f"endpoint : {bt._BASE}   (pinned testnet -- cannot touch a live account)")
    print(f"keys     : {'FOUND' if bt.has_keys() else 'MISSING'}")
    if not bt.has_keys():
        print("\n-> add keys to data/secrets/binance_testnet.json (copy the .example.json) "
              "OR set BINANCE_TESTNET_KEY / BINANCE_TESTNET_SECRET, then re-run.")
        return
    try:
        bal = bt.account_balance()
        pos = bt.positions()
    except Exception as e:  # bad keys / network
        print(f"\nCONNECTION FAILED: {e!r}")
        print("-> check the key/secret are TESTNET keys from testnet.binancefuture.com")
        return
    print(f"\nCONNECTED. USDT balance = {bal:.2f}")
    print(f"open positions: {len(pos)}")
    for sym, amt in sorted(pos.items()):
        print(f"  {sym:14} {amt:+}")
    if _DB.exists():
        con = sqlite3.connect(_DB)
        rows = con.execute("SELECT ts,symbol,side,qty,status FROM trades "
                           "ORDER BY ts DESC LIMIT 8").fetchall()
        con.close()
        if rows:
            print("\nlast trades (local DB):")
            for ts, sym, side, qty, status in rows:
                print(f"  {ts[:19]}  {side:4} {qty:>10} {sym:12} {status}")
    print("\nlooks good -> run: python scripts/run_crypto_testnet.py --live --gross-leverage 2")


if __name__ == "__main__":
    main()
