"""Fetch CFTC Traders in Financial Futures (TFF) futures-only positioning.

Free official bulk files (fut_fin_txt_YYYY.zip). 4-category breakdown:
Dealers, Asset Managers, Leveraged Money (hedge funds), Other Reportables.
Weekly, Tuesday as-of date, published Friday. FX/metals history from 2006.

Output: data/cot_tff/{slug}.parquet with report_date + oi + dealer/am/lm
long+short. Symbol mapping mirrors data.py _SYMBOL_SLUG.
"""

from __future__ import annotations

import io
import ssl
import urllib.request
import zipfile

import pandas as pd

# WRITE WHERE THE READERS LOOK. This wrote to the retired laptop's checkout
# (C:\Users\dell\mt5-research), while `research/edge_search.py` and
# `research/orthogonal_sweep.py` read COT from the desk's own tree. Writer and reader
# never agreed, so the SEARCH and SWEEP legs found no COT and produced nothing -- and
# because the mkdir SUCCEEDS, it failed by filling a directory nobody reads rather than
# by raising. `config.desk_root()` is the single source of truth for every path here.
from mt5desk.config import DATA

OUT = DATA / "cot_tff"
OUT.mkdir(parents=True, exist_ok=True)
YEARS = list(range(2018, 2027))

# Metals are NOT in TFF (financial futures only): gold/silver coverage comes
# from the legacy (1986+) and disaggregated (2006+) COT reports instead.
# DXY has no TFF entry (ICE dollar index not reported in this view).
# (slug, CFTC_Contract_Market_Code). KEYED ON THE CODE (2026-10-14): this was a case-insensitive
# SUBSTRING of the market name, so "EURO FX" also took "EURO FX/BRITISH POUND XRATE" (299741) and
# "EURO FX/JAPANESE YEN XRATE" (399741), "BRITISH POUND" and "JAPANESE YEN" took the same crosses,
# and "S&P 500"/"NASDAQ" took every micro, sector and dividend contract -- and the per-date
# `drop_duplicates(keep="last")` below then kept WHICHEVER contract the file listed last. Codes
# verified 2026-10-14 against publicreporting.cftc.gov (6dca-aqww, the same codes the TFF report
# carries).
TARGETS = [
    ("jpy", "097741"),
    ("eur", "099741"),
    ("gbp", "096742"),
    ("cad", "090741"),
    ("aud", "232741"),
    ("nzd", "112741"),
    ("chf", "092741"),
    ("sp500", "13874A"),
    ("nasdaq100", "209742"),
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


def pick(df: pd.DataFrame, code: str) -> pd.DataFrame:
    """The rows of ONE contract, chosen by its CFTC contract market code -- never by its name."""
    if "CFTC_Contract_Market_Code" not in df.columns:
        return df.iloc[0:0]
    mask = (df["CFTC_Contract_Market_Code"].astype(str).str.strip().str.strip('"').str.upper()
            == code.upper())
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
