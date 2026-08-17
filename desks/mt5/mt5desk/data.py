"""Data layer for the MT5 research desk.

Reads XAUUSD bars from the gold-desk Vantage cache (read-only, separate desk)
and the quant-platform lake D1 history for long-horizon context.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from mt5desk.config import DATA, REPORTS, desk_root  # noqa: E402

_VANTAGE = r"C:\Users\dell\gold-desk\data\bars_vantage"
_LAKE = r"C:\Users\dell\quant-platform\data\lake"
_COT = DATA / "cot"
_COT_LEGACY = DATA / "cot_gold.parquet"

# MT5 symbol -> cot slug (base-currency future; JPY crosses use the yen)
_SYMBOL_SLUG = {
    "XAUUSD": "gold", "XAGUSD": "silver",
    "USDJPY": "jpy", "EURJPY": "jpy", "GBPJPY": "jpy", "CADJPY": "jpy",
    "AUDJPY": "jpy", "NZDJPY": "jpy", "CHFJPY": "jpy",
    "EURUSD": "eur", "EURGBP": "eur", "EURCHF": "eur",
    "GBPUSD": "gbp", "USDCAD": "cad", "AUDUSD": "aud", "NZDUSD": "nzd",
    "USDCHF": "chf",
    "DXY": "dxy", "SP500": "sp500", "NDX": "nasdaq100",
}


def load_cot(symbol: str = "XAUUSD") -> pd.DataFrame:
    """CFTC legacy COT for the symbol's currency/commodity future.

    Weekly report_date (Tuesday, UTC). XAUUSD -> GOLD (legacy alias kept).
    EUR not available in the legacy schema (see data_registry)."""
    slug = _SYMBOL_SLUG.get(symbol)
    if slug is None:
        raise KeyError(f"no COT mapping for {symbol}")
    if symbol == "XAUUSD" and not (_COT / "gold.parquet").exists():
        path = _COT_LEGACY
    else:
        path = _COT / f"{slug}.parquet"
    df = pd.read_parquet(path)
    df["report_date"] = pd.to_datetime(df["report_date"], utc=True)
    return df.sort_values("report_date").reset_index(drop=True)


@dataclass(frozen=True)
class GoldData:
    m5: pd.DataFrame
    m15: pd.DataFrame
    h1: pd.DataFrame
    h4: pd.DataFrame
    d1: pd.DataFrame


def load_gold() -> GoldData:
    def read(tf: str) -> pd.DataFrame:
        df = pd.read_parquet(rf"{_VANTAGE}\XAUUSD_{tf}.parquet")
        df.index = pd.to_datetime(df.index, utc=True)
        df = df.sort_index()
        return df

    lake_d1 = _load_lake_d1()
    return GoldData(
        m5=read("M5"),
        m15=read("M15"),
        h1=read("H1"),
        h4=read("H4"),
        d1=lake_d1 if lake_d1 is not None else read("D1"),
    )


def _load_lake_d1() -> pd.DataFrame | None:
    import glob

    files = sorted(
        glob.glob(rf"{_LAKE}\bronze\metal\XAUUSD\D1\**\part-*.parquet", recursive=True)
    )
    if not files:
        return None
    df = pd.read_parquet(files)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    return df


def load_fx_h4(symbol: str = "EURUSD") -> pd.DataFrame | None:
    import glob

    files = sorted(
        glob.glob(
            rf"{_LAKE}\bronze\fx\{symbol}\H4\**\part-*.parquet", recursive=True
        )
    )
    if not files:
        return None
    df = pd.read_parquet(files)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    return df