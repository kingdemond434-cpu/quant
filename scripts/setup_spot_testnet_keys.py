"""Write Binance SPOT TESTNET keys to data/secrets/binance_spot_testnet.json (gitignored).

Run LOCALLY in your terminal with your testnet.binance.vision keys -- never paste keys into a chat.

    python scripts/setup_spot_testnet_keys.py <KEY> <SECRET>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_OUT = Path("data/secrets/binance_spot_testnet.json")


def main() -> None:
    if len(sys.argv) != 3:
        print("usage: python scripts/setup_spot_testnet_keys.py <KEY> <SECRET>")
        raise SystemExit(2)
    key, secret = sys.argv[1].strip(), sys.argv[2].strip()
    if not key or not secret:
        print("empty key/secret")
        raise SystemExit(2)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps({"key": key, "secret": secret}, indent=2), "utf-8")
    print(f"saved spot-testnet keys -> {_OUT} (key ...{key[-6:]}); "
          f"now run: python scripts/check_spot_testnet.py")


if __name__ == "__main__":
    main()
