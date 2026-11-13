"""DataHub contracts for the federation's DATA-SOURCE adapters (audit 2026-11-13).

Three adapters in `libs/research/adapters/` are data surfaces, not research engines: akshare,
tushare and openbb. Each was an import probe whose data either reached the desk by another
organ that did not say so (akshare and tushare through the free-stack hunter) or did not reach it
at all (OpenBB). This module registers ONE contract per source on the desk's hub, bound to the
lake series the judge's own conditioner reads, with the clock that refreshes it and the organ
that turns it into cells -- so "is this adapter feeding cells" is a lookup, not an archaeology:

    cnmkt.akshare   data/lake/series/fs_akshare.parquet   hourly_cycle:free_stack_hunt
                    AKShare's public upstreams (Eastmoney index klines, Sina futures klines);
                    cells: free_stack_proposer -> exogenous_conditioner / alt_series_momentum
    cnmkt.tushare   data/lake/series/fs_tushare.parquet   hourly_cycle:free_stack_hunt
                    TuShare Pro index_daily / shibor, TUSHARE_TOKEN from the box environment;
                    NEEDS_CREDENTIAL (measured) when the token is not set
    oecd.cli        data/lake/series/oecd_cli_<eco>.parquet  hourly_cycle:adapter_data
                    OECD composite leading indicators -- the keyless provider OpenBB wraps,
                    fetched directly by research/adapter_data.py; cells minted there

Names never collide with `ais.*`, `tanker.*`, `openbb.*`, `micro.*`, `tape.*`,
`macro.fred_daily` or `cot.positioning` (other threads' namespaces); a test pins that.
Nothing here sizes, vetoes or gates; it is a door and a description of who keeps it fresh.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
SERIES = DESK / "data" / "lake" / "series"

#: Namespaces other threads own; a contract here may never start with one of them.
RESERVED_PREFIXES: tuple[str, ...] = ("ais.", "tanker.", "openbb.", "micro.", "tape.",
                                      "macro.fred_daily", "cot.positioning")


@dataclass(frozen=True)
class AdapterContract:
    name: str
    adapter: str
    series: str
    clock: str
    consumer: str
    description: str
    #: The yield row (reports/FREE_STACK_YIELD.json sources[<id>]) that measures the feed, when
    #: the free-stack hunter is the collector.
    yield_source: str = ""


CONTRACTS: tuple[AdapterContract, ...] = (
    AdapterContract("cnmkt.akshare", "akshare", "fs_akshare", "hourly_cycle:free_stack_hunt",
                    "research/free_stack_proposer.py:build_grid",
                    "CN onshore index and SHFE/INE futures returns via AKShare's public "
                    "upstreams, PIT first vintage", yield_source="akshare"),
    AdapterContract("cnmkt.tushare", "tushare", "fs_tushare", "hourly_cycle:free_stack_hunt",
                    "research/free_stack_proposer.py:build_grid",
                    "CSI300 and SHIBOR from TuShare Pro (TUSHARE_TOKEN on the box)",
                    yield_source="tushare"),
    AdapterContract("oecd.cli", "openbb", "oecd_cli_", "hourly_cycle:adapter_data",
                    "research/adapter_data.py:mint",
                    "OECD composite leading indicators (amplitude adjusted) per economy, "
                    "stamped at a conservative publication lag"),
)


def series_path(c: AdapterContract, economy: str = "") -> Path:
    """The lake file a contract serves. A series name ending in `_` is a per-economy family
    (`oecd.cli` -> `oecd_cli_usa`), so the economy is a keyword of the request."""
    name = c.series + economy.lower() if c.series.endswith("_") else c.series
    return SERIES / f"{name}.parquet"


def _loader(c: AdapterContract) -> Any:
    def load(**kw: Any) -> Any:
        p = series_path(c, str(kw.get("economy") or ""))
        if not p.exists():
            return None
        import pandas as pd
        return pd.read_parquet(p)
    return load


def extend(hub: Any) -> Any:
    """Register every adapter contract on `hub` (a `libs.data.datahub.DataHub`)."""
    from libs.data.datahub import Contract, Provider
    for c in CONTRACTS:
        hub.register(Contract(c.name, "frame", description=c.description,
                              providers=[Provider(f"lake:{c.series}", _loader(c), "primary")]))
    return hub
