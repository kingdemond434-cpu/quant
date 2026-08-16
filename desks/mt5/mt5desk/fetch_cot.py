"""Fetch CFTC legacy futures-only COT report for gold into the MT5 desk.

Data: CFTC Socrata "Disaggregated Futures-Only" schema 6dca-aqww (legacy
noncomm/comm series, history to 1986). Weekly, report date = Tuesday,
published Friday ~19:30 UTC. noncomm = large speculators (the crowd);
comm = commercials (the counterparty).
Output: C:\\Users\\dell\\mt5-research\\data\\cot_gold.parquet
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

BASE = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
OUT = Path(r"C:\Users\dell\mt5-research\data\cot_gold.parquet")

SELECT = (
    "report_date_as_yyyy_mm_dd,commodity_name,contract_market_name,open_interest_all,"
    "noncomm_positions_long_all,noncomm_positions_short_all,"
    "comm_positions_long_all,comm_positions_short_all,"
    "change_in_noncomm_long_all,change_in_noncomm_short_all,"
    "change_in_open_interest_all"
)


def fetch_all() -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        params = {
            "$where": "commodity_name like 'GOLD%'",
            "$select": SELECT,
            "$order": "report_date_as_yyyy_mm_dd",
            "$limit": "5000",
            "$offset": str(offset),
        }
        url = f"{BASE}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            batch = json.load(resp)
        rows.extend(batch)
        if len(batch) < 5000:
            break
        offset += 5000
    return rows


def main() -> None:
    rows = fetch_all()
    df = pd.DataFrame(rows)
    print("distinct commodity_name:")
    print(df["commodity_name"].value_counts().to_string())
    print("distinct contract_market_name:")
    print(df["contract_market_name"].value_counts().to_string())
    df = df[df["contract_market_name"] == "GOLD"]
    df["report_date_as_yyyy_mm_dd"] = pd.to_datetime(
        df["report_date_as_yyyy_mm_dd"], format="ISO8601", utc=True
    )
    for col in df.columns:
        if col not in ("report_date_as_yyyy_mm_dd", "commodity_name",
                       "contract_market_name"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.rename(columns={"report_date_as_yyyy_mm_dd": "report_date"})
    df = df.sort_values("report_date").drop_duplicates("report_date", keep="last")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"rows={len(df)}  {df['report_date'].min().date()} -> {df['report_date'].max().date()}")
    print(df.tail(3).to_string())


if __name__ == "__main__":
    main()