"""Verify the Binance SPOT TESTNET connection: keys present, account reachable, balances + price.

    python scripts/check_spot_testnet.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.execution import binance_spot_testnet as spot  # noqa: E402


def main() -> None:
    print(f"spot-testnet keys present: {spot.has_keys()}")
    if not spot.has_keys():
        print("  -> add them: python scripts/setup_spot_testnet_keys.py <KEY> <SECRET>")
        return
    try:
        bal = spot.balances()
        print(f"  USDT balance       : {bal.get('USDT', 0.0)}")
        print(f"  assets held        : {dict(sorted(((k, round(v, 6)) for k, v in bal.items())))}")
        print(f"  account value (USDT): {spot.account_value_usdt()}")
        print(f"  BTCUSDT spot price : {spot.prices().get('BTCUSDT')}")
        print("  CONNECTED OK -- spot leg ready for paper cash-and-carry.")
    except Exception as e:
        print(f"  ERROR: {e!r}"[:180])
        print("  (check the key has spot permissions and is a testnet.binance.vision key)")


if __name__ == "__main__":
    main()
