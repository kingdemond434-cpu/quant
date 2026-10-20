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
# EXACT CONTRACT NAMES, NEVER A SUBSTRING (measured 2026-10-20). The old token match made
# "EURO FX" also take "EURO FX/JAPANESE YEN XRATE" and "EURO FX/BRITISH POUND XRATE", "S&P 500"
# take the dividend, micro and consolidated contracts, and `drop_duplicates(keep="last")` then
# kept whichever contract happened to sort last each week: eur.parquet was 189 EURO FX weeks,
# 184 EUR/GBP cross and 77 EUR/JPY cross. Each slug is now ONE contract, listed with its CFTC
# renames (oldest first), matched case-insensitively on the full name.
_CME = " - CHICAGO MERCANTILE EXCHANGE"
TARGETS: list[tuple[str, tuple[str, ...]]] = [
    ("jpy", ("JAPANESE YEN" + _CME,)),
    ("eur", ("EURO FX" + _CME,)),
    ("gbp", ("BRITISH POUND STERLING" + _CME, "BRITISH POUND" + _CME)),
    ("cad", ("CANADIAN DOLLAR" + _CME,)),
    ("aud", ("AUSTRALIAN DOLLAR" + _CME,)),
    ("nzd", ("NEW ZEALAND DOLLAR" + _CME, "NZ DOLLAR" + _CME)),
    ("chf", ("SWISS FRANC" + _CME,)),
    ("eurjpy", ("EURO FX/JAPANESE YEN XRATE" + _CME,)),
    ("eurgbp", ("EURO FX/BRITISH POUND XRATE" + _CME,)),
    ("sp500", ("E-MINI S&P 500 STOCK INDEX" + _CME, "E-MINI S&P 500" + _CME)),
    ("nasdaq100", ("NASDAQ-100 STOCK INDEX (MINI)" + _CME, "NASDAQ MINI" + _CME)),
]

UA = "quant-research/1.0 (+https://github.com/kingdemond434-cpu/quant; fetch_tff)"
ctx = ssl.create_default_context()


def load_year(year: int) -> pd.DataFrame | None:
    url = f"https://www.cftc.gov/files/dea/history/fut_fin_txt_{year}.zip"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
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


def pick(df: pd.DataFrame, names: tuple[str, ...] | str) -> pd.DataFrame:
    wanted = {names.upper()} if isinstance(names, str) else {n.upper() for n in names}
    mask = df["Market_and_Exchange_Names"].astype(str).str.strip().str.upper().isin(wanted)
    sub = df[mask].copy()
    if sub.empty:
        return sub
    oi = next((c for c in sub.columns if c == "Open_Interest_All"), None)
    def pos(tok: str) -> str | None:
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
        all_df = pd.concat(frames[slug], ignore_index=True).sort_values("report_date")
        if all_df.duplicated("report_date").any():
            # Two of a slug's names on one date is a CFTC overlap, not a choice to make silently.
            dup = sorted(set(all_df.loc[all_df.duplicated("report_date", keep=False), "market"]))
            print(f"{slug:>10}: REFUSED -- {len(dup)} names report the same week: {dup}")
            continue
        all_df.to_parquet(OUT / f"{slug}.parquet", index=False)
        print(f"{slug:>10}: {len(all_df)} rows  "
              f"{all_df['report_date'].min().date()} -> "
              f"{all_df['report_date'].max().date()}  "
              f"market={all_df['market'].iloc[0]}")


if __name__ == "__main__":
    main()
