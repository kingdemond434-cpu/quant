"""Fetch CFTC legacy futures-only COT for the full desk universe.

Data: CFTC Socrata "Disaggregated Futures-Only" schema 6dca-aqww (legacy
noncomm/comm series, history to 1986). Weekly, report date = Tuesday,
published Friday ~19:30 UTC. noncomm = large speculators; comm = commercials.

Contracts: gold, silver, FX currencies (each MT5 pair maps to one currency
future), US dollar index, S&P 500, NASDAQ 100 (conditioning-only).

Output: data/cot/{slug}.parquet per contract + data/cot_gold.parquet (legacy).
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

BASE = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
# WRITE WHERE THE READERS LOOK. This wrote to the retired laptop's checkout
# (C:\Users\dell\mt5-research), while `research/edge_search.py` and
# `research/orthogonal_sweep.py` read COT from the desk's own tree. Writer and reader
# never agreed, so the SEARCH and SWEEP legs found no COT and produced nothing -- and
# because the mkdir SUCCEEDS, it failed by filling a directory nobody reads rather than
# by raising. `config.desk_root()` is the single source of truth for every path here.
from mt5desk.config import DATA

OUT = DATA / "cot"
OUT.mkdir(parents=True, exist_ok=True)

SELECT = (
    "report_date_as_yyyy_mm_dd,commodity_name,contract_market_name,open_interest_all,"
    "noncomm_positions_long_all,noncomm_positions_short_all,"
    "comm_positions_long_all,comm_positions_short_all,"
    "change_in_noncomm_long_all,change_in_noncomm_short_all,"
    "change_in_open_interest_all"
)

# commodity_name candidates tried in order (first non-empty wins)
TARGETS: list[tuple[str, list[str]]] = [
    ("gold", ["GOLD"]),
    ("silver", ["SILVER"]),
    ("jpy", ["JAPANESE YEN"]),
    ("eur", ["EURO FX"]),
    ("gbp", ["POUND STERLING"]),
    ("cad", ["CANADIAN DOLLAR"]),
    ("aud", ["AUSTRALIAN DOLLAR"]),
    ("nzd", ["NEW ZEALAND DOLLAR"]),
    ("chf", ["SWISS FRANC"]),
    ("dxy", ["US DOLLAR INDEX", "U.S. DOLLAR INDEX"]),
    ("sp500", ["S&P BROAD BASED STOCK INDICES"]),
    ("nasdaq100", ["NASDAQ  BROADBASED INDICES"]),
]

# MT5 symbol -> cot slug (a pair trades its base-currency future; JPY crosses
# all use the yen contract; conditioning-only symbols DXY/SP500/NDX exposed)
SYMBOL_SLUG = {
    "XAUUSD": "gold", "XAGUSD": "silver",
    "USDJPY": "jpy", "EURJPY": "jpy", "GBPJPY": "jpy", "CADJPY": "jpy",
    "AUDJPY": "jpy", "NZDJPY": "jpy", "CHFJPY": "jpy",
    "EURUSD": "eur", "EURGBP": "eur", "EURCHF": "eur",
    "GBPUSD": "gbp", "USDCAD": "cad", "AUDUSD": "aud", "NZDUSD": "nzd",
    "USDCHF": "chf",
    "DXY": "dxy", "SP500": "sp500", "NDX": "nasdaq100",
}


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
        df["report_date_as_yyyy_mm_dd"], format="ISO8601", utc=True
    )
    for col in df.columns:
        if col not in ("report_date_as_yyyy_mm_dd", "commodity_name",
                       "contract_market_name"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    # prefer the outright contract when multiple markets exist
    best = (df.groupby("contract_market_name").size().idxmax()
            if df["contract_market_name"].nunique() > 1 else df["contract_market_name"].iloc[0])
    df = df[df["contract_market_name"] == best]
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
    # legacy gold alias
    g = OUT / "gold.parquet"
    if g.exists():
        import shutil
        shutil.copy(g, DATA / "cot_gold.parquet")
        print("legacy cot_gold.parquet refreshed")


if __name__ == "__main__":
    main()
