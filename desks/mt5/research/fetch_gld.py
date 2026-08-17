"""SPDR GLD physical holdings fetcher (free XLSX) + GraniteShares BAR fallback.

GLD: daily ounces + NAV, trade-date accounting. The physical bar list is
settlement-date based (different timestamps) - keep separate if mined later.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from mt5desk.config import DATA, REPORTS, desk_root  # noqa: E402

OUT = DATA / "lake"
OUT.mkdir(parents=True, exist_ok=True)

GLD_XLSX = "https://www.spdrgoldshares.com/usa/assets/uploads/GLD_US_holdings.xlsx"


def main() -> None:
    r = requests.get(GLD_XLSX, timeout=60)
    r.raise_for_status()
    xl = pd.ExcelFile(io := r.content)
    # sheet 1: holdings history (Date | Shares | Holdings in oz | Value | NAV)
    df = xl.parse(xl.sheet_names[0])
    date_col = [c for c in df.columns if "date" in str(c).lower()][0]
    oz_col = [c for c in df.columns if "oz" in str(c).lower() or "holdings" in str(c).lower()][0]
    df = df[[date_col, oz_col]].rename(columns={date_col: "date", oz_col: "ounces"})
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = df.dropna().sort_values("date").set_index("date")
    df.to_parquet(OUT / "gld_holdings.parquet")
    state = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": GLD_XLSX,
        "rows": len(df),
        "first": str(df.index.min()),
        "last": str(df.index.max()),
        "latest_ounces": float(df["ounces"].iloc[-1]),
        "note": "trade-date accounting; bar list (settlement-date) is a separate mine target",
    }
    (OUT / "gld_fetch_state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()