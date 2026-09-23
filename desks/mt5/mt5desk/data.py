"""Data layer for the MT5 research desk.

Reads XAUUSD bars from the gold-desk Vantage cache (read-only, separate desk)
and the quant-platform lake D1 history for long-horizon context.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from mt5desk.config import DATA, desk_root

# EVERY PATH HERE POINTED AT A RETIRED LAPTOP, AND TWO OF THEM FAILED SILENTLY.
#
# `_COT` and `_COT_LEGACY` read `C:\Users\dell\mt5-research\data\cot*`, while the fetchers that
# fill them wrote to the same dead root and `research/edge_search.py` and
# `research/orthogonal_sweep.py` read COT from the DESK'S OWN tree. Writer and reader never
# agreed, so the SEARCH and SWEEP legs found no COT at all.
#
# `_LAKE` is this repository's own parquet lake, addressed through the laptop's checkout path.
# `_load_lake_d1` and `load_fx_h4` return None on "no files found", which is indistinguishable
# from "the lake is empty" -- so a wrong root reads as an empty market rather than an error.
#
# The globs were also backslash-joined f-strings, which cannot match on the Linux VPS that runs
# the research half. Resolved from the repo root through pathlib instead, so one code path
# serves both machines.
_REPO_ROOT = Path(os.environ.get("QUANT_ROOT") or desk_root().parents[1])
_LAKE = Path(os.environ.get("QUANT_LAKE") or _REPO_ROOT / "data" / "lake")

#: A DIFFERENT DESK'S read-only cache, not this repo's. It has no in-tree location to fall back
#: to, so it stays an absolute path and is overridable; `load_gold` reports its absence by name
#: rather than surfacing a bare pandas error about a file nobody named.
_VANTAGE = Path(os.environ.get("MT5_VANTAGE_BARS")
                or r"C:\Users\dell\gold-desk\data\bars_vantage")

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
        p = _VANTAGE / f"XAUUSD_{tf}.parquet"
        if not p.exists():
            # NAME THE ROOT AND THE OVERRIDE. This raised a bare pandas error about a path the
            # reader had no way to trace to a setting, on a box where the separate gold desk
            # this cache belongs to was never installed.
            raise FileNotFoundError(
                f"{p} is missing. This is the SEPARATE gold desk's Vantage bar cache, not this "
                f"repo's data. Point MT5_VANTAGE_BARS at it, or run the desk on a machine that "
                f"has it (current root: {_VANTAGE}).")
        df = pd.read_parquet(p)
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
        glob.glob(str(_LAKE / "bronze" / "metal" / "XAUUSD" / "D1" / "**" / "part-*.parquet"),
                  recursive=True)
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
        glob.glob(str(_LAKE / "bronze" / "fx" / symbol / "H4" / "**" / "part-*.parquet"),
                  recursive=True)
    )
    if not files:
        return None
    df = pd.read_parquet(files)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    return df
