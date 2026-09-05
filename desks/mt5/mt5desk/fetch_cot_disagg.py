"""Fetch CFTC Disaggregated futures-only COT (modern 4-category breakdown).

Categories: MM = managed money (leveraged funds), SW = swap dealers (dealers),
OT = other reportables (asset managers for FX). Free, weekly, Tuesday report
date, published Friday. History: FX/GC from 2006.

Output: data/cot_disagg/{slug}.parquet per contract.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

BASE = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"
# WRITE WHERE THE READERS LOOK. This wrote to the retired laptop's checkout
# (C:\Users\dell\mt5-research), while `research/edge_search.py` and
# `research/orthogonal_sweep.py` read COT from the desk's own tree. Writer and reader
# never agreed, so the SEARCH and SWEEP legs found no COT and produced nothing -- and
# because the mkdir SUCCEEDS, it failed by filling a directory nobody reads rather than
# by raising. `config.desk_root()` is the single source of truth for every path here.
from mt5desk.config import DATA

OUT = DATA / "cot_disagg"
OUT.mkdir(parents=True, exist_ok=True)

SELECT = (
    "report_date_as_yyyy_mm_dd,commodity_name,contract_market_name,"
    "futonly_or_combined,open_interest_all,"
    "m_money_positions_long_all,m_money_positions_short_all,"
    "swap_positions_long_all,swap__positions_short_all,"
    "other_rept_positions_long,other_rept_positions_short,"
    "conc_net_le_4_tdr_long_all,conc_net_le_4_tdr_short_all"
)

TARGETS: list[tuple[str, list[str]]] = [
    ("gold", ["GOLD"]),
    ("silver", ["SILVER"]),
    ("jpy", ["JAPANESE YEN"]),
    ("eur", ["EURO FX"]),
    ("gbp", ["BRITISH POUND STERLING"]),
    ("cad", ["CANADIAN DOLLAR"]),
    ("aud", ["AUSTRALIAN DOLLAR"]),
    ("nzd", ["NEW ZEALAND DOLLAR"]),
    ("chf", ["SWISS FRANC"]),
    ("dxy", ["US DOLLAR INDEX", "U.S. DOLLAR INDEX"]),
    ("sp500", ["S&P 500 STOCK INDEX", "S&P 500 STOCK INDEX (OUTRIGHT)"]),
    ("nasdaq100", ["NASDAQ 100 STOCK INDEX", "NASDAQ-100 STOCK INDEX"]),
]


def fetch_contract(commodity: str) -> pd.DataFrame | None:
    rows: list[dict] = []
    offset = 0
    while True:
        params = {
            "$where": f"commodity_name='{commodity}'",
            "$select": SELECT,
            "$order": "report_date_as_yyyy_mm_dd",
            "$limit": "5000",
            "$offset": str(offset),
        }
        url = f"{BASE}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=90) as resp:
            batch = json.load(resp)
        rows.extend(batch)
        if len(batch) < 5000:
            break
        offset += 5000
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df["report_date_as_yyyy_mm_dd"] = pd.to_datetime(
        df["report_date_as_yyyy_mm_dd"], format="ISO8601", utc=True)
    for col in df.columns:
        if col not in ("report_date_as_yyyy_mm_dd", "commodity_name",
                       "contract_market_name", "futonly_or_combined"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    best = (df.groupby("contract_market_name").size().idxmax()
            if df["contract_market_name"].nunique() > 1
            else df["contract_market_name"].iloc[0])
    df = df[df["contract_market_name"] == best]
    if "futonly_or_combined" in df.columns:
        df = df[df["futonly_or_combined"].astype(str).str.lower() == "futonly"]
    df = df.rename(columns={"report_date_as_yyyy_mm_dd": "report_date"})
    df = df.sort_values("report_date").drop_duplicates("report_date", keep="last")
    return df


def main() -> None:
    for slug, candidates in TARGETS:
        df = None
        for cand in candidates:
            df = fetch_contract(cand)
            if df is not None:
                break
        if df is None or df.empty:
            print(f"{slug:>10}: FAILED (no rows for {candidates})")
            continue
        df.to_parquet(OUT / f"{slug}.parquet", index=False)
        print(f"{slug:>10}: {len(df)} rows  "
              f"{df['report_date'].min().date()} -> {df['report_date'].max().date()}"
              f"  market={df['contract_market_name'].iloc[0]}")


if __name__ == "__main__":
    main()
