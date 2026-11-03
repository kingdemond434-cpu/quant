"""Fetch CFTC Traders in Financial Futures (TFF) futures-only positioning.

Free official bulk files (fut_fin_txt_YYYY.zip). 4-category breakdown:
Dealers, Asset Managers, Leveraged Money (hedge funds), Other Reportables.
Weekly, Tuesday as-of date, published Friday. FX/metals history from 2006.

Output: data/cot_tff/{slug}.parquet with report_date + oi + dealer/am/lm
long+short. Symbol mapping mirrors data.py _SYMBOL_SLUG.

ON A CLOCK SINCE 2026-11-03. This is where EURO FX positioning lives (the legacy schema has no
euro), and like `fetch_cot` it was a one-shot from the retired laptop that nothing on Contabo
ran. `research/cot_fx_refresh.py` now runs it on the cot_fx leg's clock with the same rule:
fetch only after the Friday release that should carry a newer report. A refresh pulls the
current year's file only (and last year's in January) and merges it into what is on disk; an
empty store pulls the whole history. Manners are fetch_cot's: the desk's honest UA (it sent
"Mozilla/5.0"), robots.txt first and fail closed, 401/403/429 or a non-zip answer a HardStop,
certificate verification ON (it ran with verification disabled), atomic writes.
"""

from __future__ import annotations

import io
import re
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

# WRITE WHERE THE READERS LOOK. This wrote to the retired laptop's checkout
# (C:\Users\dell\mt5-research), while `research/edge_search.py` and
# `research/orthogonal_sweep.py` read COT from the desk's own tree. Writer and reader
# never agreed, so the SEARCH and SWEEP legs found no COT and produced nothing -- and
# because the mkdir SUCCEEDS, it failed by filling a directory nobody reads rather than
# by raising. `config.desk_root()` is the single source of truth for every path here.
from mt5desk.config import DATA
from mt5desk.fetch_cot import (
    HARD_STOP_STATUS,
    UA,
    HardStop,
    Opener,
    _atomic_parquet,
    _open,
    _terms_check,
    robots_allows,
)

OUT = DATA / "cot_tff"
URL = "https://www.cftc.gov/files/dea/history/fut_fin_txt_{year}.zip"
YEARS = list(range(2018, 2027))

# Metals are NOT in TFF (financial futures only): gold/silver coverage comes
# from the legacy (1986+) and disaggregated (2006+) COT reports instead.
# DXY has no TFF entry (ICE dollar index not reported in this view).
TARGETS = [
    ("jpy", "JAPANESE YEN"),
    ("eur", "EURO FX"),
    ("gbp", "BRITISH POUND"),
    ("cad", "CANADIAN DOLLAR"),
    ("aud", "AUSTRALIAN DOLLAR"),
    ("nzd", "NEW ZEALAND DOLLAR"),
    ("chf", "SWISS FRANC"),
    ("sp500", "S&P 500"),
    ("nasdaq100", "NASDAQ"),
]

def load_year(year: int, opener: Opener = _open) -> pd.DataFrame | None:
    """One year's bulk file; None when it is absent (404) or unreadable. A refusal, or an answer
    that is not a zip (a WAF or challenge page), raises HardStop."""
    url = URL.format(year=year)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with opener(req, 180) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code in HARD_STOP_STATUS:
            raise HardStop(f"HTTP {exc.code} from {url}") from exc
        return None
    except OSError:
        return None
    if not data.startswith(b"PK"):
        raise HardStop(f"non-zip answer from {url} (a WAF or challenge page)")
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


def years_to_fetch(out: Path, now: datetime) -> list[int]:
    """The whole history for an empty store; else this year (and last year in January, when a
    report dated in December can still be published into last year's file)."""
    if not any(out.glob("*.parquet")):
        return [y for y in YEARS if y <= now.year] or [now.year]
    return [now.year - 1, now.year] if now.month == 1 else [now.year]


def fetch_all(out: Path | None = None, opener: Opener = _open,
              log: Callable[[str], None] = print,
              now: datetime | None = None) -> dict[str, Any]:
    """Refresh every TARGETS slug into `out/<slug>.parquet`, merged with what is on disk.
    Raises HardStop on a refusal; nothing after it is fetched."""
    out = out or OUT
    now = now or datetime.now(UTC)
    out.mkdir(parents=True, exist_ok=True)
    probe = URL.format(year=now.year)
    _terms_check(probe)
    ok, why = robots_allows(probe, opener)
    if not ok:
        raise HardStop(why)
    frames: dict[str, list[pd.DataFrame]] = {slug: [] for slug, _ in TARGETS}
    years = years_to_fetch(out, now)
    loaded = 0
    for year in years:
        df = load_year(year, opener)
        if df is None:
            log(f"{year}: download failed")
            continue
        loaded += 1
        for slug, token in TARGETS:
            sub = pick(df, token)
            if not sub.empty:
                frames[slug].append(sub)
        log(f"{year}: ok")
    got: dict[str, Any] = {"years": years, "years_loaded": loaded}
    for slug, _ in TARGETS:
        if not frames[slug]:
            got[slug] = {"rows": 0, "why": "no rows in the fetched years"}
            continue
        prior = out / f"{slug}.parquet"
        parts = list(frames[slug])
        if prior.exists():
            try:
                parts.insert(0, pd.read_parquet(prior))
            except Exception as exc:
                log(f"{slug}: prior file unreadable ({type(exc).__name__}); rewritten from "
                    "the fetched years only")
        all_df = pd.concat(parts, ignore_index=True)
        all_df = (all_df.sort_values("report_date")
                  .drop_duplicates("report_date", keep="last"))
        _atomic_parquet(all_df, prior)
        got[slug] = {"rows": len(all_df), "newest": str(all_df["report_date"].max().date())}
        log(f"{slug:>10}: {len(all_df)} rows  "
            f"{all_df['report_date'].min().date()} -> "
            f"{all_df['report_date'].max().date()}  "
            f"market={all_df['market'].iloc[0]}")
    return got


def main() -> None:
    fetch_all()


if __name__ == "__main__":
    main()
