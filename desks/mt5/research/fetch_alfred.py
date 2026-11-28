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

REFUSED ON TERMS (governance/fred-terms-ruling-2026-11-13.md): FRED/ALFRED terms refuse every
automated fetch, so `fetch_vintages` returns None and `main` writes a BLOCKED_ON_TERMS report
before any request is built, key or no key. Vintages already in the lake stay readable through
`vintage_as_of`; the primary publishers (BLS, BEA, Census, Treasury) are the route.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk.config import DATA, REPORTS  # noqa: E402

OUT = DATA / "lake" / "alfred"
OUT.mkdir(parents=True, exist_ok=True)

API = "https://api.stlouisfed.org/fred/series/observations"
RELEASES = "https://api.stlouisfed.org/fred/release/dates"

#: FRED/ALFRED terms refuse every automated fetch (governance/fred-terms-ruling-2026-11-13.md).
#: Nothing here contacts stlouisfed.org; vintages already in the lake stay readable through
#: `vintage_as_of`, and the primary publishers (BLS, BEA, Census, Treasury) are the route.
BLOCKED_ON_TERMS = ("FRED/ALFRED terms refuse automated access "
                    "(governance/fred-terms-ruling-2026-11-13.md)")
MISSED_GROWTH = {"mechanism": "fred_terms_refusal",
                 "what_is_lost": "new ALFRED first-print vintages for macro conditioning",
                 "size": "UNMEASURED",
                 "stand_in": "primary-publisher first prints (BLS and peers) where a reader exists",
                 "reopens_when": "the St. Louis Fed grants written permission for automated use"}

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
    """Every vintage of one series -- REFUSED on terms, so always None, before any request.

    The ALFRED request this used to make (`output_type=2` with the full realtime span) is not
    sent: FRED/ALFRED terms refuse automated access (governance/fred-terms-ruling-2026-11-13.md).
    `key` and `timeout` are kept so existing callers need no change. Vintages already in
    `OUT` stay readable through `vintage_as_of`.
    """
    print(f"  {series_id}: BLOCKED_ON_TERMS -- {BLOCKED_ON_TERMS}", flush=True)
    return None


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
    """Write the BLOCKED_ON_TERMS report and return 2. Nothing is fetched or written to the lake.

    No scheduled leg, box task or hourly_cycle step runs this module (data_scout only names it
    as a `how_to_fetch` string), so the non-zero exit trips no clock.
    """
    argv = sys.argv[1:] if argv is None else argv
    wanted = {s.upper() for s in argv if not s.startswith("--")} or set(SERIES)
    report = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "requested": sorted(wanted),
              "status": "BLOCKED_ON_TERMS", "reason": BLOCKED_ON_TERMS,
              "missed_growth": MISSED_GROWTH, "written": 0,
              "path": str(OUT),
              "usage": "research: from research.fetch_alfred import vintage_as_of"}
    (REPORTS / "alfred_vintages.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"ALFRED BLOCKED_ON_TERMS -- {BLOCKED_ON_TERMS}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
