"""CFTC Commitments-of-Traders (COT) source -- free weekly speculator positioning.

Pulls legacy futures-only non-commercial (large speculator) positioning from the CFTC public
reporting API and turns it into a per-instrument *positioning z-score* aligned to MT5 symbols. This
is the orthogonal-to-price sleeve: positioning extremes (crowded specs) precede mean reversion, a
documented risk premium not captured by trend/momentum. Weekly data (Tuesday snapshot, published
Friday); we lag it and forward-fill to daily, so no look-ahead.

Sign convention: CFTC FX futures are FOREIGN/USD. EUR/GBP/AUD futures match EURUSD/GBPUSD/AUDUSD
directly; JPY/CHF/CAD futures are the inverse of USDJPY/USDCHF/USDCAD, so their sign is flipped so a
positive z always means "specs crowded long the MT5 instrument".
"""

from __future__ import annotations

import urllib.request
from io import StringIO

import pandas as pd

_BASE = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"

# MT5 symbol -> (CFTC legacy contract_market_code, sign vs the MT5 instrument's direction)
COT_MAP: dict[str, tuple[str, float]] = {
    "XAUUSD": ("088691", +1.0),   # GOLD
    "XAGUSD": ("084691", +1.0),   # SILVER
    "XPTUSD": ("076651", +1.0),   # PLATINUM
    "XPDUSD": ("075651", +1.0),   # PALLADIUM
    "EURUSD": ("099741", +1.0),   # EURO FX  (EUR/USD)
    "GBPUSD": ("096742", +1.0),   # BRITISH POUND (GBP/USD)
    "AUDUSD": ("232741", +1.0),   # AUSTRALIAN DOLLAR (AUD/USD)
    "USDJPY": ("097741", -1.0),   # JAPANESE YEN (JPY/USD) -> invert for USDJPY
    "USDCHF": ("092741", -1.0),   # SWISS FRANC (CHF/USD) -> invert for USDCHF
    "USDCAD": ("090741", -1.0),   # CANADIAN DOLLAR (CAD/USD) -> invert for USDCAD
    "XTIUSD": ("067411", +1.0),   # CRUDE OIL, LIGHT SWEET-WTI
}


def _get(url: str) -> list[dict[str, str]]:
    req = urllib.request.Request(url.replace(" ", "%20"), headers={"User-Agent": "quant-research"})
    with urllib.request.urlopen(req, timeout=40) as r:
        records = pd.read_json(StringIO(r.read().decode("utf-8"))).to_dict("records")
    return [dict(rec) for rec in records]


def fetch_net_spec(code: str) -> pd.Series:
    """Weekly net-speculator positioning as a fraction of open interest for one CFTC contract."""
    url = (f"{_BASE}?$where=cftc_contract_market_code='{code}'"
           "&$select=report_date_as_yyyy_mm_dd,pct_of_oi_noncomm_long_all,"
           "pct_of_oi_noncomm_short_all&$order=report_date_as_yyyy_mm_dd ASC&$limit=5000")
    rows = _get(url)
    if not rows:
        return pd.Series(dtype="float64")
    df = pd.DataFrame(rows)
    dt = pd.to_datetime(df["report_date_as_yyyy_mm_dd"], utc=True)
    net = (df["pct_of_oi_noncomm_long_all"].astype("float64")
           - df["pct_of_oi_noncomm_short_all"].astype("float64")) / 100.0
    return pd.Series(net.to_numpy(), index=dt).sort_index()


def cot_zscore_daily(
    symbols: list[str],
    daily_index: pd.DatetimeIndex,
    *,
    z_weeks: int = 156,
) -> pd.DataFrame:
    """Per-symbol COT positioning z-score (3y rolling), sign-aligned, lagged, daily-ffilled.

    Returns a DataFrame on ``daily_index`` with one column per mapped symbol. A positive value means
    speculators are crowded LONG the MT5 instrument (relative to its own 3-year history).
    """
    cols: dict[str, pd.Series] = {}
    for sym in symbols:
        if sym not in COT_MAP:
            continue
        code, sign = COT_MAP[sym]
        net = fetch_net_spec(code)
        if len(net) < z_weeks // 2:
            continue
        z = (net - net.rolling(z_weeks, min_periods=52).mean()) / net.rolling(
            z_weeks, min_periods=52).std()
        z = (sign * z).shift(1)                          # publication lag (no look-ahead)
        cols[sym] = z.reindex(z.index.union(daily_index)).sort_index().ffill().reindex(daily_index)
    return pd.DataFrame(cols, index=daily_index)
