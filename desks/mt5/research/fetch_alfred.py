"""ALFRED point-in-time macro vintages: what the desk COULD HAVE KNOWN, when it could know it.

WHY THIS EXISTS SEPARATELY FROM fetch_fred.py

`fetch_fred.py` pulls the fredgraph CSV, and its own docstring states the limitation honestly:
that endpoint returns the CURRENT VINTAGE ONLY. Every value in it is the latest revision.

Backtesting on revised macro data is the same defect as `run_hunt12.day_states` labelling a
morning with its own afternoon, arriving by a different route. Q1 GDP is first published at the
end of April, revised in May, revised again in June, and revised annually for years afterwards. A
strategy that reads today's DGS10 file for 2020-04-30 is reading a number that did not exist on
2020-04-30. The direction of the error is not neutral: revisions systematically move data toward
what actually happened, so backtests on revised series are optimistic in exactly the way that
looks like skill.

That lookahead produced 180 false survivors when it happened in the state labels. There is no
reason to expect it to be smaller here.

WHAT POINT-IN-TIME MEANS PRECISELY

Two dates, never one:

    observation_date   the period the number describes   ("Q1 2020 GDP")
    realtime_date      the date that number was PUBLISHED or revised

A backtest running on day D may use only values whose realtime_date <= D. This module stores
both, so `vintage_as_of` can answer "what did the desk know about this series on that morning?"

IT FAILS CLOSED. Without an ALFRED API key this module writes NOTHING and reports UNAVAILABLE.
It does not fall back to fetch_fred's revised series, because a revised series labelled
point-in-time is worse than no series at all: the first is a silent lookahead in every backtest
that touches it, the second is a visible gap. Absence of a vintage is never permission to use the
revision.

    Free key, 30 seconds, no cost: https://fredaccount.stlouisfed.org/apikeys
    Save it to secrets/fred_api_key (one line), or set FRED_API_KEY.

    python research/fetch_alfred.py                # all series
    python research/fetch_alfred.py DGS10 T10YIE   # a subset
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk.config import DATA, REPORTS  # noqa: E402

OUT = DATA / "lake" / "alfred"
OUT.mkdir(parents=True, exist_ok=True)

API = "https://api.stlouisfed.org/fred/series/observations"
RELEASES = "https://api.stlouisfed.org/fred/release/dates"

#: The series where revision actually bites. Daily market series (DGS10, VIXCLS) are essentially
#: never revised, so they are omitted -- pulling every vintage of a series that has one is a large
#: download that answers a question nobody asked. These are the released, revised, surprising ones.
SERIES = {
    "GDPC1": "real GDP, revised twice then annually",
    "PAYEMS": "nonfarm payrolls, revised for two months then benchmarked",
    "UNRATE": "unemployment rate",
    "CPIAUCSL": "CPI, seasonal factors revised annually",
    "CPILFESL": "core CPI",
    "PCEPI": "PCE price index, the Fed's actual target",
    "PCEPILFE": "core PCE",
    "INDPRO": "industrial production",
    "RSAFS": "retail sales",
    "HOUST": "housing starts",
    "DGORDER": "durable goods orders",
    "BUSINV": "business inventories",
    "M2SL": "M2 money stock",
    "WALCL": "Fed balance sheet",
}


def api_key() -> str | None:
    """Key from the environment or secrets/. Never logged, never written to a report."""
    env = os.environ.get("FRED_API_KEY", "").strip()
    if env:
        return env
    for p in (Path(__file__).resolve().parents[3] / "secrets" / "fred_api_key",
              Path(__file__).resolve().parent.parent / "secrets" / "fred_api_key"):
        if p.exists():
            k = p.read_text(encoding="utf-8").strip()
            if k:
                return k
    return None


def fetch_vintages(series_id: str, key: str, timeout: int = 60) -> pd.DataFrame | None:
    """Every vintage of one series, as a tidy frame.

    `output_type=2` asks ALFRED for ALL vintages in one response: one column per vintage date,
    one row per observation date. That is the whole revision history in a single request, which
    matters because the alternative is one request per vintage per series.
    """
    # THE REALTIME SPAN IS NOT OPTIONAL, and omitting it fails SILENTLY in the worst possible
    # way. `output_type=2` asks for observations by vintage date, but FRED defaults
    # realtime_start and realtime_end to TODAY -- so the response contains exactly one vintage,
    # today's, which is the fully revised series this module exists to refuse. It returns 200,
    # parses cleanly, writes a file, and reports success.
    #
    # The tell was the release lag: 14,575 days for CPI. That is not a publication delay, it is
    # 1947 to today -- the distance from the oldest observation to the only vintage present.
    # A number that absurd is the file saying it has one vintage without knowing how to say so.
    r = requests.get(API, params={"series_id": series_id, "api_key": key,
                                  "file_type": "json", "output_type": 2,
                                  "realtime_start": "1776-07-04",   # FRED's minimum
                                  "realtime_end": "9999-12-31"},    # FRED's maximum
                     timeout=timeout)
    if r.status_code != 200:
        print(f"  {series_id}: HTTP {r.status_code} {r.text[:120]}", flush=True)
        return None
    obs = r.json().get("observations", [])
    if not obs:
        return None

    # VECTORISED, BECAUSE THE PYTHON LOOP OOM-KILLED A 4GB BOX. CPI carries ~950 observations
    # across ~800 vintages: the previous version built 760,000 dicts in a list before touching
    # pandas, which is roughly 150MB of dict overhead alone, then doubled it constructing the
    # DataFrame. The process was killed mid-series and left a partial lake behind.
    #
    # Reshaping wide->long with melt does the same work inside pandas, and float32 halves what
    # survives it. Precision is irrelevant here: these are macro prints with 1-3 significant
    # decimals, not prices.
    wide = pd.DataFrame(obs)
    del obs
    vint_cols = [c for c in wide.columns
                 if c != "date" and "_" in c
                 and (s := c.rsplit("_", 1)[-1]).isdigit() and len(s) == 8]
    if not vint_cols:
        return None
    long = wide[["date"] + vint_cols].melt(
        id_vars="date", var_name="_vintage", value_name="value")
    del wide
    long = long[long["value"].ne(".") & long["value"].notna()]
    if long.empty:
        return None
    long["value"] = pd.to_numeric(long["value"], errors="coerce", downcast="float")
    long = long[long["value"].notna()]
    long["observation_date"] = pd.to_datetime(long["date"], errors="coerce")
    long["realtime_date"] = pd.to_datetime(
        long["_vintage"].str.rsplit("_", n=1).str[-1], format="%Y%m%d", errors="coerce")
    long = long[long["observation_date"].notna() & long["realtime_date"].notna()]
    out = long[["observation_date", "realtime_date", "value"]]
    del long
    return out.sort_values(["observation_date", "realtime_date"]).reset_index(drop=True)


def vintage_as_of(df: pd.DataFrame, as_of: str | datetime) -> pd.Series:
    """The series AS IT LOOKED on `as_of`. The only function research should call.

    For every observation date, takes the latest revision published on or before `as_of`, and
    drops observations not yet published at all. This is the whole point of the module: a
    backtest on day D calls this with D and cannot see a number that did not exist.
    """
    cut = pd.Timestamp(as_of)
    known = df[df["realtime_date"] <= cut]
    if known.empty:
        return pd.Series(dtype=float)
    latest = known.sort_values("realtime_date").groupby("observation_date").tail(1)
    return latest.set_index("observation_date")["value"].sort_index()


def release_lag(df: pd.DataFrame) -> dict:
    """How long after the period does the first print arrive? The tradeable-latency question.

    A signal that reads Q1 GDP must know that Q1 GDP is not knowable until late April. Reported
    per series so a strategy's assumed information timing can be checked against reality rather
    than assumed.
    """
    first = df.sort_values("realtime_date").groupby("observation_date").head(1)
    if first.empty:
        return {}

    # OBSERVATIONS THAT PREDATE ALFRED'S VINTAGE RECORD HAVE NO OBSERVABLE FIRST PRINT, and
    # including them corrupts the median badly enough to fail a series that is perfectly fine.
    #
    # ALFRED's vintage coverage begins at different dates per series, while the OBSERVATION
    # history usually runs back much further. GDPC1 has observations from 1947 and vintages from
    # ~1991: every pre-1991 quarter therefore appears to have been "first published" in 1991,
    # giving apparent lags up to 44 years. With 44 contaminated years against 35 clean ones, the
    # MEDIAN itself lands in the contaminated region -- 1,936 days -- and the series was rejected
    # as broken when it was merely old.
    #
    # CPIAUCSL passed the same check at 50 days for exactly this reason: its vintages start ~1953
    # against observations from 1947, so only six years are contaminated and the median is clean.
    # The rejections were not detecting a bad fetch, they were detecting long histories.
    #
    # So the lag is measured only where a first print is actually observable: after the earliest
    # vintage in the file. The excluded count is reported rather than dropped silently, because a
    # series with almost nothing left is a different problem and should look like one.
    vintage_start = df["realtime_date"].min()
    observable = first[first["realtime_date"] > vintage_start + pd.Timedelta(days=7)]
    excluded = int(len(first) - len(observable))
    if observable.empty:
        return {"median_days": float("nan"), "n_observations": 0,
                "excluded_predating_vintage_record": excluded,
                "why": ("every observation predates this series' vintage record, so no first "
                        "print is observable and the release lag cannot be measured")}
    lag = (observable["realtime_date"] - observable["observation_date"]).dt.days
    return {"median_days": float(lag.median()), "min_days": int(lag.min()),
            "max_days": int(lag.max()), "n_observations": int(len(lag)),
            "excluded_predating_vintage_record": excluded,
            "vintage_record_starts": str(vintage_start.date())}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    wanted = {s.upper() for s in argv} or set(SERIES)

    key = api_key()
    report = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "requested": sorted(wanted)}

    if not key:
        # FAILS CLOSED. The tempting fallback -- reuse fetch_fred's revised series and label it
        # point-in-time -- would put a silent lookahead into every backtest that touched it.
        report.update({
            "status": "UNAVAILABLE",
            "reason": ("no ALFRED/FRED API key. Point-in-time vintages REQUIRE one. This module "
                       "refuses to fall back to the revised series in data/lake, because a "
                       "revised series labelled point-in-time is a silent lookahead in every "
                       "backtest that reads it -- the same defect class as the day_states join "
                       "that manufactured 180 false survivors."),
            "fix": ("free key at https://fredaccount.stlouisfed.org/apikeys, then write it to "
                    "secrets/fred_api_key (one line) or export FRED_API_KEY"),
            "written": 0})
        (REPORTS / "alfred_vintages.json").write_text(json.dumps(report, indent=2),
                                                      encoding="utf-8")
        print("ALFRED UNAVAILABLE -- no API key.")
        print(report["fix"])
        return 2

    force = "--force" in argv
    written, lags, failed, skipped = 0, {}, [], []
    for sid in sorted(wanted):
        # RESUMABLE. A full vintage history is a large download and the box has 4GB; if the OOM
        # killer takes the process mid-run, restarting must not re-fetch what already landed.
        # Each series is written before the next is requested, so completed work survives.
        out_path = OUT / f"{sid}.parquet"
        if out_path.exists() and not force:
            skipped.append(sid)
            print(f"{sid}: already on disk, skipping (--force to refetch)", flush=True)
            continue
        print(f"{sid}: fetching all vintages...", flush=True)
        try:
            df = fetch_vintages(sid, key)
        except Exception as exc:                                    # noqa: BLE001
            print(f"  {sid}: {type(exc).__name__}: {exc}", flush=True)
            failed.append(sid)
            continue
        if df is None or df.empty:
            failed.append(sid)
            continue
        n_vint = df["realtime_date"].nunique()
        lag = release_lag(df)
        # A SINGLE VINTAGE IS A FAILED FETCH, NOT A NEVER-REVISED SERIES. Every series in SERIES
        # was chosen BECAUSE revision bites it -- GDP, payrolls, CPI are revised for years. One
        # vintage means the request returned the current revision, which is precisely the data
        # this module refuses. Rejected rather than written, because a revised series sitting in
        # the point-in-time lake is a silent lookahead in every backtest that reads it.
        if n_vint < 2:
            failed.append(sid)
            print(f"  {sid}: REJECTED -- only {n_vint} vintage returned. This is the revised "
                  f"series, not a point-in-time history. Not written.", flush=True)
            continue
        # Same check from the other side: a first-print lag of decades is arithmetic on a single
        # vintage, not a publication delay. Monthly data prints within ~60 days; quarterly ~120.
        _med = lag.get("median_days") if lag else None
        if _med is not None and _med == _med and _med > 400:
            failed.append(sid)
            print(f"  {sid}: REJECTED -- median release lag {lag['median_days']:.0f}d is not a "
                  f"publication delay. The vintage history is wrong. Not written.", flush=True)
            continue
        df.to_parquet(out_path, index=False)
        lags[sid] = lag
        written += 1
        _exc = lag.get("excluded_predating_vintage_record", 0)
        print(f"  {sid}: {len(df):,} rows, {n_vint} vintages, "
              f"median release lag {lag.get('median_days', float('nan')):.0f}d"
              + (f" ({_exc} obs predate the vintage record, excluded from the lag)"
                 if _exc else ""), flush=True)
        # Released before the next request, not at the next garbage collection. On a 4GB box the
        # peak that matters is two series held at once, and that peak is what got the process
        # killed.
        del df
        import gc; gc.collect()

    report.update({"status": "OK" if (written or skipped) else "EMPTY", "written": written,
                   "skipped_already_present": skipped,
                   "failed": failed, "release_lag_days": lags,
                   "path": str(OUT),
                   "usage": "research: from research.fetch_alfred import vintage_as_of"})
    (REPORTS / "alfred_vintages.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n{written} written to {OUT}"
          + (f", {len(skipped)} already present" if skipped else "")
          + (f", {len(failed)} REJECTED/failed: {', '.join(failed)}" if failed else ""))
    return 0 if (written or skipped) else 1


if __name__ == "__main__":
    raise SystemExit(main())
