"""Data layer for the MT5 research desk.

Reads XAUUSD bars from the gold-desk Vantage cache (read-only, separate desk)
and the quant-platform lake D1 history for long-horizon context.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

_VANTAGE = r"C:\Users\dell\gold-desk\data\bars_vantage"
_LAKE = r"C:\Users\dell\quant-platform\data\lake"
_COT = r"C:\Users\dell\mt5-research\data\cot_gold.parquet"


def load_cot() -> pd.DataFrame:
    """CFTC legacy COT for COMEX GOLD: weekly report_date (Tuesday, UTC)."""
    df = pd.read_parquet(_COT)
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