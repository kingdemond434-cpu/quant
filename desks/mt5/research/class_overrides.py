"""Asset class by symbol pattern, with Fusion's X-prefixed commodity tickers read correctly.

Lives on the RESEARCH side on purpose. `mt5desk.universe.asset_class` is the pattern fallback the
money path uses, and every file under mt5desk/ is money path; this wrapper corrects what research
steering reads without touching it.

THE DEFECT IT FIXES (measured 2026-11-03). XCUUSD, XALUSD, XNIUSD, XZNUSD and XPBUSD are the
industrial metals and XTIUSD, XBRUSD and XNGUSD are WTI, Brent and natural gas; BNBUSD, EOSUSD and
LNKUSD are crypto CFDs. None of those roots is in the fallback's lists, so all eleven fall through
to the FX rule (the quote leg is USD) and read `fx_exotic`. The 11-02 breadth steering listed eight
classes with no energy among them because the three energy CFDs were counted as FX exotics. The
broker registry was right all along; across all 251 registry symbols these were the only
commodity and crypto disagreements.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

#: Root -> class, matched at the START of the symbol and followed by a 3-letter quote or nothing,
#: so a company name that merely contains the letters is never reclassified.
X_ROOTS = {
    "XTI": "energy", "XBR": "energy", "XNG": "energy",
    "XCU": "metal", "XAL": "metal", "XNI": "metal", "XZN": "metal", "XPB": "metal",
    "BNB": "crypto", "EOS": "crypto", "LNK": "crypto",
}
_ROOTED = re.compile(r"^(?P<root>[A-Z]{3})(?:[A-Z]{3})?$")


def asset_class(symbol: str) -> str:
    """`mt5desk.universe.asset_class(symbol)`, except for the X-prefixed tickers above."""
    m = _ROOTED.match(str(symbol).strip().upper())
    if m and m.group("root") in X_ROOTS:
        return X_ROOTS[m.group("root")]
    try:
        from mt5desk.universe import asset_class as _pattern
        return str(_pattern(symbol))
    except Exception:
        return "unknown"
