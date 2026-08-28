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

ROOT = Path(__file__).resolve().parent.parent
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

    raw = _fetch(since)
    if not raw:
        print("no new CFTC reports since the cache's last week -- nothing to append")
        return 0

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
        return 1

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
    out = out.ffill()

    tmp = CACHE.with_suffix(".parquet.tmp")
    out.to_parquet(tmp)
    tmp.replace(CACHE)
    print(f"cot_zcache: {len(out)} rows (+{int(fresh_idx.sum())} new) to "
          f"{out.index.max().date()} at {datetime.now(tz=UTC):%Y-%m-%dT%H:%MZ}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
