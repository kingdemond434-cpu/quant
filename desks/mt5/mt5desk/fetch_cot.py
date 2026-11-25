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


def _frame(rows: list[dict]) -> pd.DataFrame | None:
    """The legacy-schema frame the readers expect, from raw Socrata rows."""
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df["report_date_as_yyyy_mm_dd"] = pd.to_datetime(
        df["report_date_as_yyyy_mm_dd"], format="ISO8601", utc=True
    )
    for col in df.columns:
        if col not in ("report_date_as_yyyy_mm_dd", "commodity_name",
                       "contract_market_name", "market_and_exchange_names"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.rename(columns={"report_date_as_yyyy_mm_dd": "report_date"})
    return df.sort_values("report_date").drop_duplicates("report_date", keep="last")


def _page(where: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        params = {"$where": where, "$select": SELECT, "$order": "report_date_as_yyyy_mm_dd",
                  "$limit": "5000", "$offset": str(offset)}
        url = f"{BASE}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=90) as resp:
            batch = json.load(resp)
        rows.extend(batch)
        if len(batch) < 5000:
            return rows
        offset += 5000


def fetch_market(market: str) -> pd.DataFrame | None:
    """One contract by its EXACT CFTC market name (`mt5desk.cot_contracts.MARKETS`)."""
    q = market.replace("'", "''")
    return _frame(_page(f"market_and_exchange_names='{q}'"))


def fetch_code(code: str) -> pd.DataFrame | None:
    """One contract by CFTC contract_market_code (`cot_contracts.CODES`, from COT_MAP)."""
    return _frame(_page(f"cftc_contract_market_code='{code}'"))


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


def _targets() -> list[tuple[str, list[str], str | None, str | None]]:
    """(slug, commodity candidates, exact market fallback, code fallback) for every raw file.

    The legacy slugs are tried by `commodity_name` first, exactly as before, then by their exact
    market name -- `eur.parquet` never landed on the commodity route (36 cells probed
    `cot_file:eur.parquet`). Every other slug has no commodity route: its market name or its
    COT_MAP code is the only address.
    """
    from mt5desk import cot_contracts as cc
    out = [(slug, cands, cc.MARKETS.get(slug), cc.CODES.get(slug)) for slug, cands in TARGETS]
    seen = {t[0] for t in out}
    for slug in sorted(set(cc.SYMBOL_SLUG.values()) - seen):
        out.append((slug, [], cc.MARKETS.get(slug), cc.CODES.get(slug)))
    return out


def main() -> None:
    missing: list[str] = []
    for slug, candidates, market, code in _targets():
        df = None
        for cand in candidates:
            df = fetch_contract(cand)
            if df is not None:
                break
        if df is None and market:
            df = fetch_market(market)
            candidates = [*candidates, market]
        if df is None and code:
            df = fetch_code(code)
            candidates = [*candidates, f"code {code}"]
        if df is None or df.empty:
            print(f"{slug:>10}: FAILED (no rows for {candidates})")
            missing.append(slug)
            continue
        df.to_parquet(OUT / f"{slug}.parquet", index=False)
        print(f"{slug:>10}: {len(df)} rows  "
              f"{df['report_date'].min().date()} -> {df['report_date'].max().date()}"
              f"  market={df['contract_market_name'].iloc[0]}")
    if missing:
        print(f"UNFETCHED: {missing} -- those symbols stay probed cot_file until they land")
    # legacy gold alias
    g = OUT / "gold.parquet"
    if g.exists():
        import shutil
        shutil.copy(g, DATA / "cot_gold.parquet")
        print("legacy cot_gold.parquet refreshed")


if __name__ == "__main__":
    main()
