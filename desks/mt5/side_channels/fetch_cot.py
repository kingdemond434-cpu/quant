#!/usr/bin/env python3
"""
Fetch CFTC Commitments of Traders (COT) futures-only data for BTC and ETH.

Source: publicreporting.cftc.gov (free, published every Friday ~15:30 ET).
Covers BITCOIN/ETHER futures on CME + Coinbase Derivatives perp-style.
Writes data/cot/{btc,eth}.parquet with weekly series:

    date        report date (Tuesday snapshot)
    pub_date    publication date (report date + 4 calendar days; COT is known to the
                market only after Friday 15:30 ET, and D1 bars timestamp at bar START,
                so +4d is the honest "available from" stamp -- conservative by design)
    spec_long/spec_short   non-commercial (speculative) positions
    comm_long/comm_short   commercial (hedger) positions
    oi          open interest
    net_spec    spec_long - spec_short
    net_comm    comm_long - comm_short

All COT filters per report date. This is a WEEKLY series; downstream adapters
reindex onto daily bars with past-only ffill keyed on pub_date (no lookahead).
"""

from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

CFTC_URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
OUT = Path("data/cot")

MARKETS = {
    "btc": "%25BITCOIN%25CHICAGO%25",
    "eth": "%25ETHER%25CHICAGO%25",
}


def fetch_all(market_filter: str) -> list[dict]:
    """Fetch the full history for one market filter (paged)."""
    rows: list[dict] = []
    offset = 0
    limit = 50000
    while True:
        url = (
            f"{CFTC_URL}?$where=market_and_exchange_names%20like%20%22{market_filter}%22"
            f"&$order=report_date_as_yyyy_mm_dd%20ASC&$limit={limit}&$offset={offset}"
            "&$select=report_date_as_yyyy_mm_dd,market_and_exchange_names,"
            "noncomm_positions_long_all,noncomm_positions_short_all,"
            "comm_positions_long_all,comm_positions_short_all,open_interest_all"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            batch = json.loads(resp.read())
        if not batch:
            break
        rows.extend(batch)
        offset += limit
        if len(batch) < limit:
            break
    return rows


def to_frame(rows: list[dict]) -> pd.DataFrame:
    recs = []
    for r in rows:
        name = r.get("market_and_exchange_names", "")
        d = r.get("report_date_as_yyyy_mm_dd", "")[:10]
        if not d:
            continue
        recs.append({
            "date": pd.Timestamp(d),
            "market": name,
            "spec_long": float(r.get("noncomm_positions_long_all") or 0.0),
            "spec_short": float(r.get("noncomm_positions_short_all") or 0.0),
            "comm_long": float(r.get("comm_positions_long_all") or 0.0),
            "comm_short": float(r.get("comm_positions_short_all") or 0.0),
            "oi": float(r.get("open_interest_all") or 0.0),
        })
    df = pd.DataFrame(recs)
    if df.empty:
        return df
    df = df.groupby("date", as_index=False).agg(
        {c: "sum" for c in ["spec_long", "spec_short", "comm_long", "comm_short", "oi"]}
    )
    df["pub_date"] = df["date"] + pd.Timedelta(days=4)
    df["net_spec"] = df["spec_long"] - df["spec_short"]
    df["net_comm"] = df["comm_long"] - df["comm_short"]
    df["spec_share"] = df["net_spec"] / df["oi"].clip(lower=1.0)
    df["comm_share"] = df["net_comm"] / df["oi"].clip(lower=1.0)
    return df.sort_values("date").reset_index(drop=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for key, filt in MARKETS.items():
        rows = fetch_all(filt)
        df = to_frame(rows)
        if df.empty:
            print(f"{key}: no rows")
            continue
        path = OUT / f"{key}.parquet"
        df.to_parquet(path, index=False)
        print(f"{key}: {len(df)} weekly rows, {df['date'].min().date()}..{df['date'].max().date()} -> {path}")


if __name__ == "__main__":
    main()