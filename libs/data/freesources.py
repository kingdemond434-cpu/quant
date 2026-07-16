"""Free, key-less crypto data families -- breadth + depth at zero cost.

Each fetcher is read-only public REST. Captures the genuinely-new free advantages that the earlier
campaign had not tapped: market-wide RISK-REGIME signals (Fear & Greed, BTC dominance / total mcap)
and extra cross-venue / term-structure CARRY breadth (Hyperliquid funding across ~230 assets,
Binance dated-quarterly calendar basis). No alpha logic here -- sleeves/gauntlets consume these.
"""

from __future__ import annotations

import json
import time
import urllib.request
from typing import Any

import pandas as pd

_FAPI = "https://fapi.binance.com"
_FNG = "https://api.alternative.me/fng"
_CG = "https://api.coingecko.com/api/v3"
_HL = "https://api.hyperliquid.xyz/info"


def _get(url: str, *, data: bytes | None = None, hdr: dict[str, str] | None = None,
         tries: int = 3) -> Any:
    last: Exception | None = None
    headers = {"User-Agent": "quant-platform/1.0", **(hdr or {})}
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read())
        except Exception as exc:  # transient network / rate-limit
            last = exc
            time.sleep(1.5)
    raise RuntimeError(f"GET failed: {url} :: {last}")


def fear_greed(*, limit: int = 0) -> pd.DataFrame:
    """Crypto Fear & Greed index (alternative.me), full daily history. (timestamp, fng) in 0-100."""
    d = _get(f"{_FNG}/?limit={limit}&format=json")
    rows = d.get("data", []) if isinstance(d, dict) else []
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame({
        "timestamp": pd.to_datetime([int(r["timestamp"]) for r in rows], unit="s", utc=True),
        "fng": [float(r["value"]) for r in rows],
    })
    return df.sort_values("timestamp").reset_index(drop=True)


def coingecko_global() -> dict[str, float]:
    """Market-wide regime snapshot: total mcap (USD), BTC dominance %, 24h mcap change %."""
    g = _get(f"{_CG}/global")
    data = g.get("data", {}) if isinstance(g, dict) else {}
    if not data:
        return {}
    return {
        "total_mcap_usd": float(data.get("total_market_cap", {}).get("usd", 0.0)),
        "btc_dominance": float(data.get("market_cap_percentage", {}).get("btc", 0.0)),
        "eth_dominance": float(data.get("market_cap_percentage", {}).get("eth", 0.0)),
        "mcap_change_24h": float(data.get("market_cap_change_percentage_24h_usd", 0.0)),
    }


def hyperliquid_funding() -> dict[str, float]:
    """Current funding rate per asset on Hyperliquid (~230 perps) -- extra cross-venue breadth."""
    body = json.dumps({"type": "metaAndAssetCtxs"}).encode()
    h = _get(_HL, data=body, hdr={"Content-Type": "application/json"})
    if not (isinstance(h, list) and len(h) == 2):
        return {}
    universe = h[0].get("universe", [])
    ctx = h[1]
    out: dict[str, float] = {}
    for meta, c in zip(universe, ctx, strict=False):
        f = c.get("funding") if isinstance(c, dict) else None
        if f is not None:
            out[str(meta.get("name"))] = float(f)
    return out


def dated_quarterly_symbols() -> list[str]:
    """Binance USD-M dated (quarterly) delivery contracts -- the calendar-basis universe."""
    info = _get(f"{_FAPI}/fapi/v1/exchangeInfo")
    syms = info.get("symbols", []) if isinstance(info, dict) else []
    return sorted(s["symbol"] for s in syms
                  if s.get("contractType") in ("CURRENT_QUARTER", "NEXT_QUARTER")
                  and s.get("status") == "TRADING")


def calendar_basis() -> dict[str, float]:
    """Annualised perp->quarterly calendar basis per base asset (BTC, ETH). Positive = contango.

    basis = (quarter_price / perp_price - 1) annualised by days-to-expiry. A clean term-structure
    carry signal: high contango -> richer cash-and-carry; backwardation -> stress.
    """
    out: dict[str, float] = {}
    quarters = dated_quarterly_symbols()
    if not quarters:
        return out
    px = _get(f"{_FAPI}/fapi/v1/ticker/price")
    perp = {d["symbol"]: float(d["price"]) for d in px} if isinstance(px, list) else {}
    now_ms = int(time.time() * 1000)
    for q in quarters:
        base, _, expiry = q.partition("_")            # e.g. BTCUSDT_260925
        if base not in perp or len(expiry) != 6:
            continue
        qpx = _get(f"{_FAPI}/fapi/v1/ticker/price?symbol={q}")
        qp = float(qpx["price"]) if isinstance(qpx, dict) and "price" in qpx else 0.0
        if qp <= 0 or perp[base] <= 0:
            continue
        exp = pd.Timestamp(f"20{expiry[:2]}-{expiry[2:4]}-{expiry[4:6]}", tz="UTC")
        exp_ms = int(exp.timestamp() * 1000)
        days = max((exp_ms - now_ms) / 86_400_000, 1.0)
        ann = (qp / perp[base] - 1.0) * (365.0 / days)
        if base not in out or "_NEXT" in q:           # keep the nearest by default
            out[base] = round(ann, 5)
    return out
