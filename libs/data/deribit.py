"""Deribit options data (free public API) -- implied volatility, a NEW orthogonal data family.

DVOL is Deribit's 30-day implied-volatility index (crypto's VIX), available for BTC and ETH. The
*volatility risk premium* (implied vol minus subsequently realised vol) is a forward-looking,
options-derived signal that is structurally orthogonal to every perp/funding/flow signal we trade.
Public REST, no keys. History ~ months at 12h resolution.
"""

from __future__ import annotations

import json
import time
import urllib.request

import pandas as pd

_BASE = "https://www.deribit.com/api/v2/public"


def _get(url: str) -> dict[str, object]:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-platform/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    return data if isinstance(data, dict) else {"_": data}


def fetch_dvol(currency: str = "BTC", *, days: int = 120, resolution: int = 43200) -> pd.DataFrame:
    """DVOL implied-vol index history (resolution seconds; 43200 = 12h). Columns: (timestamp, dvol).

    `dvol` is the annualised implied vol in percent (e.g. 50.0 = 50% annualised)."""
    end = int(time.time() * 1000)
    start = end - days * 86400 * 1000
    url = (f"{_BASE}/get_volatility_index_data?currency={currency}"
           f"&start_timestamp={start}&end_timestamp={end}&resolution={resolution}")
    res = _get(url).get("result")
    data = res.get("data") if isinstance(res, dict) else None
    if not isinstance(data, list) or not data:
        return pd.DataFrame()
    return pd.DataFrame({
        "timestamp": pd.to_datetime([int(str(r[0])) for r in data], unit="ms", utc=True),
        "dvol": [float(str(r[4])) for r in data]})       # close of [ts, open, high, low, close]


def vol_surface(currency: str = "BTC") -> dict[str, float]:
    """Current vol-surface snapshot from the whole option book (one call): ATM IV, 25-delta-proxy
    skew (OTM-put IV minus OTM-call IV; positive = crash fear), and term slope (front minus ~30d).

    Per-strike IV has NO free history, so this is archived FORWARD (see collect_deribit_surface).
    Returns {} on failure. IVs are in percent."""
    url = f"{_BASE}/get_book_summary_by_currency?currency={currency}&kind=option"
    res = _get(url).get("result")
    if not isinstance(res, list) or not res:
        return {}
    rows = []
    for r in res:
        if not isinstance(r, dict) or not r.get("mark_iv"):
            continue
        parts = str(r.get("instrument_name", "")).split("-")
        if len(parts) != 4:
            continue
        rows.append({"exp": parts[1], "strike": float(parts[2]), "type": parts[3],
                     "iv": float(r["mark_iv"]), "spot": float(r["underlying_price"])})
    if not rows:
        return {}
    df = pd.DataFrame(rows)
    spot = float(df["spot"].median())
    df["dte"] = (pd.to_datetime(df["exp"], format="%d%b%y", utc=True)
                 - pd.Timestamp.now(tz="UTC")).dt.total_seconds() / 86400.0
    df = df[df["dte"] > 1.0]
    if df.empty:
        return {}
    dtes = sorted(df["dte"].unique())
    front = df[df["dte"] == dtes[0]]
    far = df[df["dte"] == min(dtes, key=lambda x: abs(x - 30.0))]

    def _atm(g: pd.DataFrame) -> float:
        return float(g.iloc[int((g["strike"] - spot).abs().to_numpy().argmin())]["iv"]) if len(g) \
            else float("nan")

    atm = _atm(far) if len(far) else _atm(front)
    puts, calls = far[far["type"] == "P"], far[far["type"] == "C"]

    def _iv_near(g: pd.DataFrame, k: float) -> float:
        if not len(g):
            return atm
        return float(g.iloc[int((g["strike"] - k).abs().to_numpy().argmin())]["iv"])

    put_iv, call_iv = _iv_near(puts, 0.9 * spot), _iv_near(calls, 1.1 * spot)
    term = (_atm(front) - _atm(far)) if (len(front) and len(far)) else 0.0
    return {"atm_iv": round(atm, 2), "skew": round(put_iv - call_iv, 2),
            "term": round(float(term) if term == term else 0.0, 2), "spot": round(spot, 1)}
