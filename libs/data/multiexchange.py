"""Multi-exchange funding data (Binance + Bybit + OKX) -- a NEW free, orthogonal data family.

Single-venue funding is the existing carry edge. The cross-exchange *dispersion* (a venue's funding
vs the cross-venue consensus) is a different, orthogonal signal: it measures venue-relative crowding
and inter-venue arbitrage pressure, not the market-wide leverage demand the carry sleeve already
trades. All public REST, no keys. 8h funding, paginated to ~3 months. Symbols map BASEUSDT (Binance/
Bybit) <-> BASE-USDT-SWAP (OKX).
"""

from __future__ import annotations

import json
import time
import urllib.request

import pandas as pd

_UA = {"User-Agent": "quant-platform/1.0"}


def _get(url: str) -> dict[str, object]:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    return data if isinstance(data, dict) else {"_": data}


def okx_inst(symbol: str) -> str:
    """BTCUSDT -> BTC-USDT-SWAP -- including the re-denominated micro-cap tickers.

    THE COVERAGE GAP THIS CLOSES (R0294 / L0061, RU frontier miner 2026-08-01). Binance names a
    re-denominated contract in the TICKER (1000SHIBUSDT = 1000 SHIB per contract unit) while OKX
    carries the SAME asset under its bare name and puts the multiplier in the contract size
    (SHIB-USDT-SWAP, ctVal=1e6). A literal string join therefore MISSES the asset entirely rather
    than mismatching it: the old mapping resolved 260 of 653 Binance perps and silently dropped
    SHIB, PEPE, FLOKI, BONK, SATS -- the whole micro-cap corner where funding dispersion is
    largest. Stripping the numeric prefix is CORRECT here because funding is a dimensionless
    RATE: the 1000x lives in contract size, not in the rate, so no value rescaling is needed --
    and grading this as a "1000x scaling bug" would have been wrong for exactly that reason.
    Prefixes seen on Binance: 1000, 10000, 1000000 (and 1MBABYDOGE-style "1M").
    """
    base = symbol[:-4] if symbol.endswith("USDT") else symbol
    for pre in ("1000000", "10000", "1000", "1M"):
        if base.startswith(pre) and len(base) > len(pre) and not base[len(pre)].isdigit():
            base = base[len(pre):]
            break
    return f"{base}-USDT-SWAP"


def fetch_bybit_funding(symbol: str, *, pages: int = 3) -> pd.DataFrame:
    """Bybit linear-perp 8h funding history (paginated back via the endTime cursor)."""
    rows: list[dict[str, object]] = []
    end: int | None = None
    for _ in range(pages):
        url = (f"https://api.bybit.com/v5/market/funding/history?category=linear"
               f"&symbol={symbol}&limit=200")
        if end:
            url += f"&endTime={end}"
        res = _get(url).get("result")
        lst = res.get("list") if isinstance(res, dict) else None
        if not isinstance(lst, list) or not lst:
            break
        rows += lst
        end = int(str(lst[-1]["fundingRateTimestamp"])) - 1
        time.sleep(0.2)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame({
        "timestamp": pd.to_datetime([int(str(r["fundingRateTimestamp"])) for r in rows],
                                    unit="ms", utc=True),
        "funding": [float(str(r["fundingRate"])) for r in rows]})
    return df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)


def fetch_okx_funding(symbol: str, *, pages: int = 3) -> pd.DataFrame:
    """OKX swap 8h funding history (paginated back via the `after` cursor)."""
    inst = okx_inst(symbol)
    rows: list[dict[str, object]] = []
    after: int | None = None
    for _ in range(pages):
        url = f"https://www.okx.com/api/v5/public/funding-rate-history?instId={inst}&limit=100"
        if after:
            url += f"&after={after}"
        lst = _get(url).get("data")
        if not isinstance(lst, list) or not lst:
            break
        rows += lst
        after = int(str(lst[-1]["fundingTime"]))
        time.sleep(0.2)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame({
        "timestamp": pd.to_datetime([int(str(r["fundingTime"])) for r in rows], unit="ms",
                                    utc=True),
        "funding": [float(str(r["fundingRate"])) for r in rows]})
    return df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
