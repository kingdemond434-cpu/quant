"""One-shot: save your Binance TESTNET keys to the (gitignored) secrets file -- no manual editing.

Usage (paste your two testnet keys in place of the placeholders):
    python scripts/setup_testnet_keys.py  YOUR_API_KEY  YOUR_SECRET_KEY

It writes data/secrets/binance_testnet.json so the executor picks the keys up automatically. Testnet
keys are fake-money keys from testnet.binancefuture.com -- never paste live-account keys here.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

_OUT = Path("data/secrets/binance_testnet.json")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("key", nargs="?", help="testnet API key (optional -- will prompt if omitted)")
    ap.add_argument("secret", nargs="?", help="testnet secret key")
    args = ap.parse_args()
    # Easiest path: run with NO arguments and paste each key when asked (no spaces to get wrong).
    key = (args.key or input("Paste your TESTNET API key, then Enter:\n  ").strip())
    secret = (args.secret or input("Paste your TESTNET SECRET key, then Enter:\n  ").strip())
    if len(key) < 20 or len(secret) < 20:
        raise SystemExit("those don't look like real keys -- copy BOTH (API key AND secret) from "
                         "testnet.binancefuture.com (API Key box)")
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps({"key": args.key, "secret": args.secret}, indent=2), "utf-8")
    print(f"saved testnet keys -> {_OUT}")
    print("next: python scripts/check_testnet.py   (should say CONNECTED)")


if __name__ == "__main__":
    main()
