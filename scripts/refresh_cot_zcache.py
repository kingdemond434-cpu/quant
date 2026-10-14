"""INCREMENTAL COT REFRESH -- keep data/cot_zcache.parquet current from CFTC's fast API.

WHY (2026-08-28). The zcache -- 26 years of weekly positioning z-scores for the 11 MT5 symbols
the `cot_positioning` family trades -- had no live producer under the MT5 mandate: the scheduled
COT unit writes the RETIRED crypto cache, and the screen that reads this file is reader-first
(it consumes the cache, never refreshes it). The file sat 67 days stale while every consumer
treated it as current, and the family produced no signals on 297 straight sweep passes.

WHY SOCRATA, NOT THE ZIPS. The history zips are 1.5MB per year and rebuilding 26 years takes
long enough that fixers time out and restore the stale file -- correct behaviour, no progress.
publicreporting.cftc.gov serves the same reports as JSON with a date filter, so this fetches
ONLY the weeks missing from the RAW history (`data/cot_netcache.parquet`) and appends them, then
re-derives every z-score from raw positions. A z cache with no raw history behind it is rebuilt
from source in one filtered query (11 contract codes, ~20k rows) and refused -- banked files left
untouched -- if that fetch comes back short, so banked history cannot be lost to a bad fetch.

Z-SCORES: net non-commercial positioning, 52-REPORT rolling z on raw nets only, daily
forward-fill keyed on the report date (the sweep resamples to W-FRI and lags to release itself).
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cot_zcache.parquet"
API = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
UA = {"User-Agent": "Mozilla/5.0 (quant-desk cot refresh)"}
ZWIN = 52

#: MT5 symbol -> CFTC CONTRACT MARKET CODE (legacy futures-only, 6dca-aqww). THE CODE, NOT THE
#: NAME (2026-10-14). These were market-name SUBSTRING needles, summed per date: "GOLD -" is a
#: substring of "MICRO GOLD - COMMODITY EXCHANGE INC." (088695) and of Coinbase's
#: "GOLD -1 TROY OUNCE" (088LM1), so three contracts of different sizes were added together under
#: XAUUSD; and "CRUDE OIL, LIGHT SWEET -" stopped matching the NYMEX contract when the CFTC renamed
#: it "WTI-PHYSICAL", so XTIUSD silently stopped refreshing. Codes verified 2026-10-14 against
#: publicreporting.cftc.gov 6dca-aqww (weeks after 2026-09-01).
CODES: dict[str, str] = {
    "XAUUSD": "088691",
    "XAGUSD": "084691",
    "XPTUSD": "076651",
    "XPDUSD": "075651",
    "EURUSD": "099741",
    "GBPUSD": "096742",
    "AUDUSD": "232741",
    "USDJPY": "097741",
    "USDCHF": "092741",
    "USDCAD": "090741",
    "XTIUSD": "067651",
}
#: symbols quoted USD-per-foreign invert: a long JPY future is a SHORT USDJPY position.
INVERT = {"USDJPY", "USDCHF", "USDCAD"}


#: raw weekly net non-commercial positioning, one row per REPORT date (the Tuesday as-of date),
#: one column per MT5 symbol, already sign-aligned. The z cache is DERIVED from this file and
#: nothing else; see `zscores_from_raw`.
NETCACHE = ROOT / "data" / "cot_netcache.parquet"
#: a rebuild reaches back this far so the 2000 z-scores have a full window behind them.
REBUILD_SINCE = "1986-01-01"
MIN_PERIODS = 12


def _fetch(since: str) -> list[dict[str, Any]]:
    """Every report for the mapped contract codes strictly after `since` (an ISO date)."""
    codes = ",".join(f"'{c}'" for c in sorted(set(CODES.values())))
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        q = urllib.parse.urlencode({
            "$where": (f"report_date_as_yyyy_mm_dd > '{since}' "
                       f"AND cftc_contract_market_code in ({codes})"),
            "$order": "report_date_as_yyyy_mm_dd ASC, cftc_contract_market_code ASC",
            "$limit": 5000, "$offset": offset,
            "$select": ("market_and_exchange_names,cftc_contract_market_code,"
                        "report_date_as_yyyy_mm_dd,"
                        "noncomm_positions_long_all,noncomm_positions_short_all"),
        })
        req = urllib.request.Request(f"{API}?{q}", headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            batch = json.loads(r.read())
        rows.extend(batch)
        if len(batch) < 5000:
            return rows
        offset += 5000
        if offset > 200000:
            return rows


def raw_nets(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """CFTC rows -> weekly RAW net positioning per MT5 symbol (sign-aligned), keyed on the
    report date. Positions, never z-scores."""
    import pandas as pd

    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["report_date_as_yyyy_mm_dd"], utc=True, errors="coerce")
    for col in ("noncomm_positions_long_all", "noncomm_positions_short_all"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["code"] = (frame.get("cftc_contract_market_code", pd.Series("", index=frame.index))
                     .astype(str).str.strip().str.upper())
    frame = frame.dropna(subset=["date"])
    cols: dict[str, pd.Series] = {}
    for sym, code in CODES.items():
        sub = frame.loc[frame["code"] == code]
        if sub.empty:
            continue
        net = (sub["noncomm_positions_long_all"] - sub["noncomm_positions_short_all"])
        series = net.groupby(sub["date"]).sum().sort_index()
        cols[sym] = -series if sym in INVERT else series
    return pd.DataFrame(cols).sort_index()


def zscores_from_raw(raw: pd.DataFrame) -> pd.DataFrame:
    """52-REPORT rolling z of RAW nets, computed per symbol on its own weekly observations, then
    forward-filled onto a daily calendar index keyed on the report date (the as-of Tuesday; the
    release lag stays at the readers -- see tests/research/test_cot_release_lag.py).

    THE DEFECT THIS REPLACES (2026-10-14). The refresh used to join the BANKED z-scores with the
    new weeks' RAW net positions and take a rolling z over that mixture: every appended week was
    a contract count standardised against a window of z-scores (mean ~0, sd ~1), i.e. a number
    in the tens of thousands of "sigmas", and the window ran over DAILY forward-filled rows, so
    "52" was 52 days of repeated values. The z here sees raw positions only, one per report."""
    import pandas as pd

    out: dict[str, pd.Series] = {}
    for sym in raw.columns:
        s = raw[sym].astype(float).dropna().sort_index()
        s = s[~s.index.duplicated(keep="last")]
        if s.empty:
            continue
        roll = s.rolling(ZWIN, min_periods=MIN_PERIODS)
        out[sym] = (s - roll.mean()) / roll.std(ddof=0)
    if not out:
        return pd.DataFrame()
    weekly = pd.DataFrame(out).sort_index()
    daily = pd.date_range(weekly.index.min().normalize(), weekly.index.max().normalize(),
                          freq="D", tz="UTC")
    return weekly.reindex(weekly.index.union(daily)).ffill()


def needs_rebuild(zcache: pd.DataFrame | None, raw: pd.DataFrame | None) -> str | None:
    """Why the raw history cannot carry the z cache, or None when it can. A z cache with no raw
    history behind it is REBUILT FROM SOURCE -- never extended by mixing z and positions."""
    import pandas as pd

    if raw is None or raw.empty:
        return "no raw net history banked (z-only cache)"
    if zcache is not None and not zcache.empty:
        missing = sorted(set(zcache.columns) - set(raw.columns))
        if missing:
            return f"raw history lacks {missing}"
        if raw.index.min() > zcache.index.min() + pd.Timedelta(days=7):
            return "raw history starts after the z cache"
    return None


def _atomic_parquet(frame: pd.DataFrame, path: Path) -> None:
    tmp = path.with_suffix(".parquet.tmp")
    frame.to_parquet(tmp)
    tmp.replace(path)


def main() -> int:
    import pandas as pd

    zcache = pd.read_parquet(CACHE) if CACHE.exists() else None
    raw = pd.read_parquet(NETCACHE) if NETCACHE.exists() else None
    why = needs_rebuild(zcache, raw)
    if why is not None:
        print(f"REBUILD FROM SOURCE: {why}; fetching every report since {REBUILD_SINCE}")
        fetched = raw_nets(_fetch(REBUILD_SINCE))
        want = set(zcache.columns) if zcache is not None else set(CODES)
        absent = sorted(want - set(fetched.columns))
        if fetched.empty or absent:
            print(f"REFUSING: the rebuild fetch did not return every symbol (absent {absent}); "
                  f"the banked files are left untouched")
            return 1
        if zcache is not None and fetched.index.min() > zcache.index.min():
            print("REFUSING: the rebuild fetch starts after the banked z cache -- a short fetch "
                  "would lose history; the banked files are left untouched")
            return 1
        raw = fetched
        added = len(raw)
    else:
        assert raw is not None
        last = raw.index.max()
        since = last.date().isoformat()
        print(f"raw history holds {len(raw)} reports to {since}; fetching CFTC weeks after that")
        fresh = raw_nets(_fetch(since))
        if fresh.empty:
            print("no new CFTC reports since the last banked week -- nothing to append")
            return 0
        absent = sorted(set(CODES) - set(fresh.columns))
        if len(absent) == len(CODES):
            print("CFTC answered but no mapped contract code matched -- appending NOTHING (a "
                  "code map that stops matching is a defect, not an empty week)")
            return 1
        joined = pd.concat([raw, fresh.reindex(columns=raw.columns.union(fresh.columns))])
        raw = joined[~joined.index.duplicated(keep="last")].sort_index()
        added = int((raw.index > last).sum())

    z = zscores_from_raw(raw)
    _atomic_parquet(raw, NETCACHE)
    _atomic_parquet(z, CACHE)
    print(f"cot_zcache: {len(z)} rows from {len(raw)} raw reports (+{added}) to "
          f"{z.index.max().date()} at {datetime.now(tz=UTC):%Y-%m-%dT%H:%MZ}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
