"""Fetch CFTC Traders in Financial Futures (TFF) futures-only positioning.

Free official bulk files (fut_fin_txt_YYYY.zip). 4-category breakdown:
Dealers, Asset Managers, Leveraged Money (hedge funds), Other Reportables.
Weekly, Tuesday as-of date, published Friday. FX/metals history from 2006.

Output: data/cot_tff/{slug}.parquet with report_date + oi + dealer/am/lm
long+short. Symbol mapping mirrors data.py _SYMBOL_SLUG.
"""

from __future__ import annotations

import io
import re
import ssl
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd
from mt5desk.config import DATA, REPORTS, desk_root  # noqa: E402

OUT = DATA / "cot_tff"
OUT.mkdir(parents=True, exist_ok=True)
YEARS = list(range(2018, 2027))

# (slug, market-name token)
TARGETS = [
    ("gold", "GOLD"),
    ("silver", "SILVER"),
    ("jpy", "JAPANESE YEN"),
    ("eur", "EURO FX"),
    ("gbp", "BRITISH POUND"),
    ("cad", "CANADIAN DOLLAR"),
    ("aud", "AUSTRALIAN DOLLAR"),
    ("nzd", "NEW ZEALAND DOLLAR"),
    ("chf", "SWISS FRANC"),
    ("dxy", "US DOLLAR INDEX"),
    ("sp500", "S&P 500"),
    ("nasdaq100", "NASDAQ"),
]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def load_year(year: int) -> pd.DataFrame | None:
    url = f"https://www.cftc.gov/files/dea/history/fut_fin_txt_{year}.zip"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        data = urllib.request.urlopen(req, timeout=180, context=ctx).read()
    except Exception:
        return None
    z = zipfile.ZipFile(io.BytesIO(data))
    member = [n for n in z.namelist() if n.lower().endswith(".txt")]
    if not member:
        return None
    text = z.read(member[0]).decode("utf-8", errors="replace")
    header = text.splitlines()[0]
    cols = [c.strip().strip('"') for c in header.split(",")]
    df = pd.read_csv(io.StringIO(text), quotechar='"', skipinitialspace=True)
    df.columns = cols
    return df


def pick(df: pd.DataFrame, token: str) -> pd.DataFrame:
    pat = re.compile(re.escape(token), re.IGNORECASE)
    mask = df["Market_and_Exchange_Names"].astype(str).str.contains(
        pat.pattern, regex=True, na=False)
    sub = df[mask].copy()
    if sub.empty:
        return sub
    oi = next((c for c in sub.columns if c == "Open_Interest_All"), None)
    def pos(tok: str) -> str:
        return next((c for c in sub.columns if c.startswith(tok)), None)
    keep = {
        "report_date": "Report_Date_as_YYYY-MM-DD",
        "market": "Market_and_Exchange_Names",
        "oi": oi,
        "dealer_l": pos("Dealer_Positions_Long_All"),
        "dealer_s": pos("Dealer_Positions_Short_All"),
        "am_l": pos("Asset_Mgr_Positions_Long_All"),
        "am_s": pos("Asset_Mgr_Positions_Short_All"),
        "lm_l": pos("Lev_Money_Positions_Long_All"),
        "lm_s": pos("Lev_Money_Positions_Short_All"),
    }
    keep = {k: v for k, v in keep.items() if v is not None}
    sub = sub[list(keep.values())].rename(columns={v: k for k, v in keep.items()})
    sub["report_date"] = pd.to_datetime(sub["report_date"], utc=True)
    for c in sub.columns:
        if c not in ("report_date", "market"):
            sub[c] = pd.to_numeric(sub[c], errors="coerce")
    return sub


def main() -> None:
    frames: dict[str, list[pd.DataFrame]] = {slug: [] for slug, _ in TARGETS}
    for year in YEARS:
        df = load_year(year)
        if df is None:
            print(f"{year}: download failed")
            continue
        for slug, token in TARGETS:
            sub = pick(df, token)
            if not sub.empty:
                frames[slug].append(sub)
        print(f"{year}: ok")
    for slug, _ in TARGETS:
        if not frames[slug]:
            print(f"{slug:>10}: FAILED (no rows)")
            continue
        all_df = pd.concat(frames[slug], ignore_index=True)
        all_df = (all_df.sort_values("report_date")
                  .drop_duplicates("report_date", keep="last"))
        all_df.to_parquet(OUT / f"{slug}.parquet", index=False)
        print(f"{slug:>10}: {len(all_df)} rows  "
              f"{all_df['report_date'].min().date()} -> "
              f"{all_df['report_date'].max().date()}  "
              f"market={all_df['market'].iloc[0]}")


if __name__ == "__main__":
    main()