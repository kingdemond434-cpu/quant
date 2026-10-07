"""Fetch CFTC Traders in Financial Futures (TFF) futures-only positioning.

    python mt5desk/fetch_tff.py                  # full history 2018 .. this year
    python mt5desk/fetch_tff.py --recent         # this year and last, merged into the files
    python mt5desk/fetch_tff.py --repair-local   # no network: re-select the outright contract

Free official bulk files (fut_fin_txt_YYYY.zip). 4-category breakdown:
Dealers, Asset Managers, Leveraged Money (hedge funds), Other Reportables.
Weekly, Tuesday as-of date, published Friday (later in holiday and shutdown weeks:
`mt5desk.cot_frames.release_schedule`).

Output: data/cot_tff/{slug}.parquet with report_date + market + cftc_code + oi + dealer/am/lm
long+short, ONE row per report date, all from ONE contract.

ONE CONTRACT PER FILE, CHOSEN BY ITS CFTC CODE (2026-10-07). The name token used to be a
substring match ("EURO FX" also matches "EURO FX/BRITISH POUND XRATE" and "EURO FX/JAPANESE YEN
XRATE"), every matching market was concatenated, and `drop_duplicates("report_date")` then kept
whichever row sorted LAST -- often a cross-rate. Measured on the committed files: EUR kept the
outright Euro FX contract on 189 of 450 report dates, GBP on 247, JPY on 338; the rest of each
history was a different contract, so downstream the outright series had 55-86 missing weeks and
every "weekly" change across one was a 1-12 week change. The outright contract is now selected by
`CFTC_Contract_Market_Code` (stable across renames: NZD's "NEW ZEALAND DOLLAR" became "NZ DOLLAR"
in 2022 and the old token stopped matching, ending that file at 2022-02-01), with the exact
market-name prefixes as the fallback for a file that lacks the code column.
"""

from __future__ import annotations

import argparse
import io
import json
import ssl
import sys
import urllib.request
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

# WRITE WHERE THE READERS LOOK. This wrote to the retired laptop's checkout
# (C:\Users\dell\mt5-research), while `research/edge_search.py` and
# `research/orthogonal_sweep.py` read COT from the desk's own tree. Writer and reader
# never agreed, so the SEARCH and SWEEP legs found no COT and produced nothing -- and
# because the mkdir SUCCEEDS, it failed by filling a directory nobody reads rather than
# by raising. `config.desk_root()` is the single source of truth for every path here.
_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))
from mt5desk.config import DATA  # noqa: E402

OUT = DATA / "cot_tff"
FIRST_YEAR = 2018
CODE_COL = "CFTC_Contract_Market_Code"
NAME_COL = "Market_and_Exchange_Names"

# Metals are NOT in TFF (financial futures only): gold/silver coverage comes
# from the legacy (1986+) and disaggregated (2006+) COT reports instead.
# DXY has no TFF entry (ICE dollar index not reported in this view).
#: (slug, CFTC contract market code of the OUTRIGHT contract, exact market-name prefixes).
#: Codes read from the CFTC's own TFF report (financial_lf.htm, as of 2026-09-29).
TARGETS: list[tuple[str, str, tuple[str, ...]]] = [
    ("jpy", "097741", ("JAPANESE YEN - ",)),
    ("eur", "099741", ("EURO FX - ",)),
    ("gbp", "096742", ("BRITISH POUND - ", "BRITISH POUND STERLING - ")),
    ("cad", "090741", ("CANADIAN DOLLAR - ",)),
    ("aud", "232741", ("AUSTRALIAN DOLLAR - ",)),
    # Renamed in 2022: "NEW ZEALAND DOLLAR" -> "NZ DOLLAR", same CME contract and code.
    ("nzd", "112741", ("NEW ZEALAND DOLLAR - ", "NZ DOLLAR - ")),
    ("chf", "092741", ("SWISS FRANC - ",)),
    ("sp500", "13874A", ("E-MINI S&P 500 - ", "E-MINI S&P 500 STOCK INDEX - ")),
    ("nasdaq100", "209742", ("NASDAQ MINI - ", "NASDAQ-100 STOCK INDEX (MINI) - ")),
]

ctx = ssl.create_default_context()


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
    df = pd.read_csv(io.StringIO(text), quotechar='"', skipinitialspace=True, dtype=str)
    df.columns = cols
    return df


def _norm_code(v: object) -> str:
    return str(v).strip().strip('"').upper()


def outright_rows(df: pd.DataFrame, code: str, prefixes: tuple[str, ...]) -> pd.DataFrame:
    """The rows of exactly one contract: by CFTC code, else by exact market-name prefix.

    Works on a raw CFTC frame (`CFTC_Contract_Market_Code`, `Market_and_Exchange_Names`) and on
    a written file (`cftc_code`, `market`). A prefix ends in " - " so a cross-rate
    ("EURO FX/BRITISH POUND XRATE - ...") can never match its leg's name."""
    code_col = next((c for c in (CODE_COL, "cftc_code") if c in df.columns), None)
    if code_col is not None:
        by_code = df[df[code_col].map(_norm_code) == code.upper()]
        if not by_code.empty:
            return by_code
    name_col = NAME_COL if NAME_COL in df.columns else "market"
    names = df[name_col].astype(str).str.strip().str.upper()
    want = tuple(p.upper() for p in prefixes)
    return df[names.map(lambda m: m.startswith(want))]


def pick(df: pd.DataFrame, code: str, prefixes: tuple[str, ...]) -> pd.DataFrame:
    sub = outright_rows(df, code, prefixes).copy()
    if sub.empty:
        return sub
    oi = next((c for c in sub.columns if c == "Open_Interest_All"), None)

    def pos(tok: str) -> str | None:
        return next((c for c in sub.columns if c.startswith(tok)), None)
    keep = {
        "report_date": "Report_Date_as_YYYY-MM-DD",
        "market": NAME_COL,
        "oi": oi,
        "dealer_l": pos("Dealer_Positions_Long_All"),
        "dealer_s": pos("Dealer_Positions_Short_All"),
        "am_l": pos("Asset_Mgr_Positions_Long_All"),
        "am_s": pos("Asset_Mgr_Positions_Short_All"),
        "lm_l": pos("Lev_Money_Positions_Long_All"),
        "lm_s": pos("Lev_Money_Positions_Short_All"),
    }
    present = {k: v for k, v in keep.items() if v is not None}
    out = sub[list(present.values())].rename(columns={v: k for k, v in present.items()})
    out["cftc_code"] = (sub[CODE_COL].map(_norm_code) if CODE_COL in sub.columns
                        else code.upper())
    out["market"] = out["market"].astype(str).str.strip()
    out["report_date"] = pd.to_datetime(out["report_date"], utc=True)
    for c in out.columns:
        if c not in ("report_date", "market", "cftc_code"):
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def merge(existing: pd.DataFrame | None, new: list[pd.DataFrame], code: str,
          prefixes: tuple[str, ...]) -> pd.DataFrame:
    """Existing rows (re-selected to the outright contract) + new rows; a re-fetched report date
    replaces the stored one. One row per report date from one contract, or it raises."""
    parts: list[pd.DataFrame] = []
    if existing is not None and not existing.empty:
        old = outright_rows(existing, code, prefixes).copy()
        if "cftc_code" not in old.columns:
            old["cftc_code"] = code.upper()
        old["report_date"] = pd.to_datetime(old["report_date"], utc=True)
        parts.append(old)
    parts.extend(f for f in new if f is not None and not f.empty)
    if not parts:
        return pd.DataFrame()
    df = pd.concat(parts, ignore_index=True)
    df = df.sort_values("report_date", kind="stable").drop_duplicates("report_date", keep="last")
    if df["cftc_code"].map(_norm_code).nunique() > 1:
        raise ValueError(f"{code}: more than one contract survived selection")
    return df.reset_index(drop=True)


def _read_existing(path: Path) -> pd.DataFrame | None:
    try:
        return pd.read_parquet(path) if path.exists() else None
    except Exception:
        return None


def run(years: list[int], *, keep_existing: bool, out: Path = OUT,
        loader: Callable[[int], pd.DataFrame | None] | None = load_year) -> dict:
    """Fetch `years`, select each outright contract, write. A slug whose fetch yields nothing
    keeps its stored rows (re-selected), never overwritten with less."""
    out.mkdir(parents=True, exist_ok=True)
    frames: dict[str, list[pd.DataFrame]] = {slug: [] for slug, _c, _p in TARGETS}
    fetched: list[int] = []
    failed: list[int] = []
    for year in years:
        df = None if loader is None else loader(year)
        if df is None:
            failed.append(year)
            continue
        fetched.append(year)
        for slug, code, prefixes in TARGETS:
            sub = pick(df, code, prefixes)
            if not sub.empty:
                frames[slug].append(sub)
    files: dict[str, dict] = {}
    for slug, code, prefixes in TARGETS:
        path = out / f"{slug}.parquet"
        existing = _read_existing(path) if (keep_existing or not frames[slug]) else None
        df = merge(existing, frames[slug], code, prefixes)
        if df.empty:
            files[slug] = {"status": "NO_ROWS"}
            continue
        df.to_parquet(path, index=False)
        files[slug] = {"status": "WRITTEN", "rows": len(df),
                       "first": str(df["report_date"].min().date()),
                       "last": str(df["report_date"].max().date()),
                       "markets": sorted(df["market"].astype(str).unique())}
    return {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"), "years": years,
            "fetched": fetched, "failed": failed, "files": files}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--recent", action="store_true",
                    help="fetch this year and last only, merged into the existing files")
    ap.add_argument("--repair-local", action="store_true",
                    help="no network: re-select the outright contract in the existing files")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    this_year = datetime.now(tz=UTC).year
    if args.repair_local:
        doc = run([], keep_existing=True, loader=None)
    elif args.recent:
        doc = run([this_year - 1, this_year], keep_existing=True)
    else:
        doc = run(list(range(FIRST_YEAR, this_year + 1)), keep_existing=False)
    if args.json:
        print(json.dumps(doc, indent=1))
    else:
        for slug, f in doc["files"].items():
            print(f"{slug:>10}: {f}")
        if doc["failed"]:
            print(f"download failed for {doc['failed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
