"""INCREMENTAL COT REFRESH -- keep data/cot_zcache.parquet current from CFTC's fast API.

WHY (2026-08-28). The zcache -- 26 years of weekly positioning z-scores for the 11 MT5 symbols
the `cot_positioning` family trades -- had no live producer under the MT5 mandate: the scheduled
COT unit writes the RETIRED crypto cache, and the screen that reads this file is reader-first
(it consumes the cache, never refreshes it). The file sat 67 days stale while every consumer
treated it as current, and the family produced no signals on 297 straight sweep passes.

WHY SOCRATA, NOT THE ZIPS. The history zips are 1.5MB per year and rebuilding 26 years takes
long enough that fixers time out and restore the stale file -- correct behaviour, no progress.
publicreporting.cftc.gov serves the same reports as JSON with a date filter, so this fetches
ONLY the weeks missing from the cache and appends them. History is never re-derived, so the
26 years already banked cannot be lost to a bad fetch.

COVERAGE (2026-11-25). The cache held 11 columns, so 1,411 `cot_positioning` cells probed
`cot_series:<SYM>` and were never judged. It now covers every non-exotic MT5 instrument with a CFTC
contract (`desks/mt5/mt5desk/cot_contracts.py` is the one table):
  * DIRECT contracts outside the original eleven (NZD, Brent, natural gas, copper, the equity
    indices, the dollar index, the two Treasury notes, the softs, BTC, ETH) are REBUILT IN FULL
    every run from 2000-01-01: weekly net, 52-week z, daily forward-fill.
  * FX CROSSES are built from their legs, never fetched: a cross's z is (z_base - z_quote)/sqrt(2),
    the USD leg being zero; JPY/CHF/CAD legs are the negated USDxxx columns. Recomputed every run
    from the leg columns, so a cross can never drift from its legs.
  * Same-underlying symbols (XAUEUR, XAUAUD, XAGEUR) copy their USD column.
  Banked columns are never re-derived. A mapped contract the CFTC feed returns no rows for is
  REPORTED by name and its column left absent, never filled.

Z-SCORES MATCH THE EXISTING SEMANTICS: net non-commercial positioning, 52-week rolling z, daily
forward-fill (the cache is daily-indexed; the sweep resamples to W-FRI itself).
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import importlib.util  # noqa: E402
import math  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def _contracts():
    """`mt5desk/cot_contracts.py` by file path: pure data, no desk package import needed."""
    spec = importlib.util.spec_from_file_location(
        "cot_contracts", ROOT / "desks" / "mt5" / "mt5desk" / "cot_contracts.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("cot_contracts", mod)
    spec.loader.exec_module(mod)
    return mod


CACHE = ROOT / "data" / "cot_zcache.parquet"
API = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
UA = {"User-Agent": "Mozilla/5.0 (quant-desk cot refresh)"}
ZWIN = 52

#: MT5 symbol -> CFTC market-name needles. Explicit, because a substring guess would splice a
#: different contract's positioning under a familiar symbol.
NEEDLES: dict[str, tuple[str, ...]] = {
    "XAUUSD": ("GOLD -",),
    "XAGUSD": ("SILVER -",),
    "XPTUSD": ("PLATINUM -",),
    "XPDUSD": ("PALLADIUM -",),
    "EURUSD": ("EURO FX -",),
    "GBPUSD": ("BRITISH POUND -", "BRITISH POUND STERLING -", "POUND STERLING -"),
    "AUDUSD": ("AUSTRALIAN DOLLAR -",),
    "USDJPY": ("JAPANESE YEN -",),
    "USDCHF": ("SWISS FRANC -",),
    "USDCAD": ("CANADIAN DOLLAR -",),
    "XTIUSD": ("CRUDE OIL, LIGHT SWEET -",),
}
#: symbols quoted USD-per-foreign invert: a long JPY future is a SHORT USDJPY position.
INVERT = {"USDJPY", "USDCHF", "USDCAD"}


def _fetch(since: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        q = urllib.parse.urlencode({
            "$where": f"report_date_as_yyyy_mm_dd > '{since}'",
            "$limit": 5000, "$offset": offset,
            "$select": ("market_and_exchange_names,report_date_as_yyyy_mm_dd,"
                        "noncomm_positions_long_all,noncomm_positions_short_all"),
        })
        req = urllib.request.Request(f"{API}?{q}", headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            batch = json.loads(r.read())
        rows.extend(batch)
        if len(batch) < 5000:
            return rows
        offset += 5000
        if offset > 60000:
            return rows


HIST_SINCE = "2000-01-01"


def _fetch_markets(names: list[str], since: str = HIST_SINCE) -> list[dict]:
    """Every weekly report of the EXACT named markets after `since` (history for new columns)."""
    rows: list[dict] = []
    offset = 0
    quoted = ",".join("'" + n.replace("'", "''") + "'" for n in names)
    while True:
        q = urllib.parse.urlencode({
            "$where": (f"market_and_exchange_names in({quoted}) "
                       f"AND report_date_as_yyyy_mm_dd > '{since}'"),
            "$limit": 5000, "$offset": offset,
            "$select": ("market_and_exchange_names,report_date_as_yyyy_mm_dd,"
                        "noncomm_positions_long_all,noncomm_positions_short_all"),
        })
        req = urllib.request.Request(f"{API}?{q}", headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            batch = json.loads(r.read())
        rows.extend(batch)
        if len(batch) < 5000 or offset > 200000:
            return rows
        offset += 5000


def _zseries(net):
    return (net - net.rolling(ZWIN, min_periods=12).mean()) / net.rolling(ZWIN, min_periods=12
                                                                           ).std(ddof=0)


def backfill_direct(out, direct: dict, fetch_markets=_fetch_markets):
    """(Re)build every DIRECT column from its full history. Returns (out, built, unmatched).

    Rebuilt EVERY run, not appended: these columns have no 26-year bank to protect (they start at
    2000-01-01 and cost one paged JSON fetch), and a rebuild cannot drift from the feed. A fetch
    that fails or returns nothing for a column leaves the banked column as it was.
    """
    import pandas as pd
    todo = dict(direct)
    if not todo:
        return out, [], []
    names = sorted({n for ns in todo.values() for n in ns})
    try:
        raw = fetch_markets(names)
    except Exception as exc:
        print(f"direct-contract history fetch failed ({type(exc).__name__}); columns left as banked")
        return out, [], sorted(todo)
    added: list[str] = []
    unmatched: list[str] = []
    if raw:
        frame = pd.DataFrame(raw)
        frame["date"] = pd.to_datetime(frame["report_date_as_yyyy_mm_dd"], utc=True,
                                       errors="coerce")
        for col in ("noncomm_positions_long_all", "noncomm_positions_short_all"):
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        frame = frame.dropna(subset=["date"])
    for col, wanted in todo.items():
        sub = frame.loc[frame["market_and_exchange_names"].isin(wanted)] if raw else None
        if sub is None or sub.empty:
            unmatched.append(col)
            continue
        net = (sub["noncomm_positions_long_all"] - sub["noncomm_positions_short_all"])
        weekly = net.groupby(sub["date"]).sum().sort_index()
        if len(weekly) < 12:
            unmatched.append(col)
            continue
        out[col] = _zseries(weekly).reindex(out.index, method="ffill")
        added.append(col)
    return out, added, unmatched


def derive_columns(out, cc):
    """FX crosses from their legs, and same-underlying aliases. Returns (out, derived, skipped)."""
    leg: dict[str, object] = {}
    for ccy, col, sign in (("EUR", "EURUSD", 1), ("GBP", "GBPUSD", 1), ("AUD", "AUDUSD", 1),
                           ("NZD", "NZDUSD", 1), ("JPY", "USDJPY", -1), ("CHF", "USDCHF", -1),
                           ("CAD", "USDCAD", -1)):
        if col in out.columns:
            leg[ccy] = out[col] * sign
    derived: list[str] = []
    skipped: dict[str, str] = {}
    for pair in cc.FX_PAIRS:
        b, q = cc.fx_legs(pair)
        if "USD" in (b, q):
            continue                      # a USD pair is a DIRECT column, never derived
        if b not in leg or q not in leg:
            skipped[pair] = f"leg column absent for {b if b not in leg else q}"
            continue
        out[pair] = (leg[b] - leg[q]) / math.sqrt(2.0)
        derived.append(pair)
    for alias, src in cc.ZCACHE_ALIAS.items():
        if src in out.columns:
            out[alias] = out[src]
            derived.append(alias)
        else:
            skipped[alias] = f"source column {src} absent"
    return out, derived, skipped


def refresh_raw_files() -> None:
    """Also keep the raw per-contract parquets (`desks/mt5/data/cot/<slug>.parquet`) current.

    Nothing scheduled ran `mt5desk/fetch_cot.py`, so the four raw COT families read files frozen at
    whenever someone last ran it by hand, and every new slug would never have landed. It runs on
    this clock, after the cache, and can never fail the cache: any error is logged and swallowed.
    """
    try:
        sys.path.insert(0, str(ROOT / "desks" / "mt5"))
        from mt5desk import fetch_cot
        fetch_cot.main()
    except Exception as exc:  # the zcache above is already written
        print(f"raw COT refresh failed ({type(exc).__name__}: {str(exc)[:200]})")


def main() -> int:
    import pandas as pd

    if not CACHE.exists():
        print(f"REFUSING: {CACHE} absent -- this refresher APPENDS to banked history and will "
              f"not re-derive 26 years; restore the cache from backup first")
        return 1
    cache = pd.read_parquet(CACHE)
    last = cache.index.max()
    since = (last.date().isoformat() if hasattr(last, "date") else str(last)[:10])
    print(f"cache holds {len(cache)} rows to {since}; fetching CFTC weeks after that")

    out = cache
    status = 0
    raw = _fetch(since)
    if not raw:
        print("no new CFTC reports since the cache's last week -- nothing to append")
    else:
        got = _append(cache, raw, last)
        if got is None:
            status = 1                   # a needle map that stops matching is a defect
        else:
            out = got
    cc = _contracts()
    out, added, unmatched = backfill_direct(out, cc.ZCACHE_DIRECT)
    out, derived, skipped = derive_columns(out, cc)
    if status == 0 or added:
        tmp = CACHE.with_suffix(".parquet.tmp")
        out.to_parquet(tmp)
        tmp.replace(CACHE)
    print(f"cot_zcache: {len(out)} rows, {len(out.columns)} columns to {out.index.max().date()} "
          f"at {datetime.now(tz=UTC):%Y-%m-%dT%H:%MZ}; rebuilt direct {added}; "
          f"derived {len(derived)}; NO CFTC ROWS FOR {unmatched}; skipped {skipped}")
    refresh_raw_files()
    return status


def _append(cache, raw: list[dict], last):
    """The original incremental append, unchanged in effect. None when nothing matched."""
    import pandas as pd
    frame = pd.DataFrame(raw)
    frame["date"] = pd.to_datetime(frame["report_date_as_yyyy_mm_dd"], utc=True, errors="coerce")
    for col in ("noncomm_positions_long_all", "noncomm_positions_short_all"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["market"] = frame["market_and_exchange_names"].astype(str).str.upper()
    frame = frame.dropna(subset=["date"])

    new_cols: dict[str, pd.Series] = {}
    for sym, needles in NEEDLES.items():
        mask = frame["market"].apply(lambda m, nd=needles: any(n in m for n in nd))
        sub = frame.loc[mask]
        if sub.empty:
            continue
        net = (sub["noncomm_positions_long_all"] - sub["noncomm_positions_short_all"])
        series = net.groupby(sub["date"]).sum().sort_index()
        if sym in INVERT:
            series = -series
        new_cols[sym] = series

    if not new_cols:
        print("CFTC answered but no mapped market matched -- appending NOTHING (a needle map "
              "that stops matching is a defect, not an empty week)")
        return None

    fresh = pd.DataFrame(new_cols)
    # Recompute z on the JOINED history so the rolling window spans the boundary, then keep
    # only the new rows: the banked z-scores stay byte-identical.
    hist_net = cache.copy()
    joined = pd.concat([hist_net, fresh.reindex(columns=cache.columns)], axis=0)
    joined = joined[~joined.index.duplicated(keep="last")].sort_index()
    z = ((joined - joined.rolling(ZWIN, min_periods=12).mean())
         / joined.rolling(ZWIN, min_periods=12).std(ddof=0))
    out = joined.copy()
    fresh_idx = out.index > last
    out.loc[fresh_idx] = z.loc[fresh_idx]
    return out.ffill()


if __name__ == "__main__":
    sys.exit(main())
