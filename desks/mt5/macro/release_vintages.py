"""PIT RELEASE VINTAGES -- the calendar's consensus joined to the agency's FIRST PRINT, release by
release, with every revision appended and every surprise variant measured or named UNMEASURED.

THE GAP, MEASURED ON THIS TREE (2026-10-06). The desk has captured the free calendar's consensus
since 2026-08-25 as point-in-time vintages (`data/intelligence/ff_calendar_vintage/`, hourly
rollups: title, scheduled instant, forecast, previous, impact, capture stamp) and has had a
point-in-time FIRST-PRINT lake builder for months (`research/fetch_alfred.py`, every vintage
ALFRED holds). Nothing joined them. `event_surprise` therefore found ZERO pairs with both an
actual and a consensus and reported every scheduled surprise UNMEASURED, and the event atlas
measured reactions to scheduled MOMENTS, never to NEWS. This module is the join.

WHAT A ROW CARRIES (principal 2026-10-05, "ECONOMIC SURPRISE LAYER"): event, country, currency,
reference period, scheduled instant, previous (as the calendar showed it), the prior period's
first print and its revision as of this release, consensus median (the calendar's forecast as
last captured BEFORE the scheduled instant, with that capture's stamp), first actual, every later
revised actual with the vintage it appeared in, impact class and provenance. Survey high/low and
a whisper are not lawfully free and are carried as UNMEASURED with that reason.

THE CLOCKS ARE THE AGENCY'S, NOT OURS. The first print is knowable at the release's SCHEDULED
instant (an official statistical release is published on its schedule), the consensus at the
instant the desk captured it, a revision at its own vintage date and the same time of day. A
consensus captured AFTER the scheduled instant is not a consensus and is refused.

TWO KINDS OF EXPECTATION, NEVER MIXED.
  consensus   the calendar's survey median. History starts 2026-08-25, so its release-specific
              sigma needs ten prints and is UNMEASURED for most releases for months -- stated.
  nowcast     a declared naive model: the exponentially weighted mean (half-life 3) of the
              release's last twelve FIRST prints known at the release. It needs no survey, so
              it has decades of history and a measured sigma today. Its pairs are written under
              their own release id (`<release>|nowcast_ewm12`) so `event_surprise` standardises
              and measures them separately, and no consensus statistic ever sees them.

NOTHING HERE HAS A DIRECTION. Every number is a magnitude handed to `event_surprise`, whose
reaction measurement is the only place a sign is read, and to the sensor ledger.

FAILS CLOSED. Without ALFRED files (FRED_API_KEY unset on this host) no actual is written, the
consensus halves wait in the store for their partner, and the status says BLOCKED_AUTH. A revised
series is never substituted for a first print.
"""
from __future__ import annotations

import gzip
import json
import math
import re
import subprocess
import sys
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
VINTAGES = DESK / "data" / "intelligence" / "ff_calendar_vintage"
ALFRED = DESK / "data" / "lake" / "alfred"
FETCH_ALFRED = DESK / "research" / "fetch_alfred.py"
UNMEASURED = "UNMEASURED"
SOURCE = "release_vintages"
#: The terms hold lives in ONE place (`libs.data.terms_hold`): a pair whose consensus source is
#: held (Forex Factory's survey median) is stored and counted, never donated, until cleared; the
#: ALFRED first print against the desk's own nowcast_ewm12 ships alone until then.
CLEARANCES = ROOT / "desks" / "mt5" / "data" / "terms_clearances.json"
ET = ZoneInfo("America/New_York")
#: ALFRED files older than this are re-fetched (a release lands at most daily per series).
ALFRED_MAX_AGE_H = 20.0
NOWCAST_N = 12
NOWCAST_HALF_LIFE = 3.0
#: Declared transmission targets for a USD release: where to LOOK, never which way.
USD_INSTRUMENTS: tuple[str, ...] = ("XAUUSD", "EURUSD", "USDJPY", "GBPUSD", "AUDUSD",
                                    "USDCAD", "USDCHF", "US500", "NAS100", "US30")


@dataclass(frozen=True)
class ReleaseSpec:
    """One calendar headline and the first-print series whose transform IS that headline."""

    title: str               # the calendar title, currency prefix included
    series: str              # the ALFRED series id
    transform: str           # level | diff | pct_mom | pct_yoy | pct_qoq_saar
    kind: str                # the event ontology's kind
    hour: int                # scheduled hour, US/Eastern
    minute: int = 30
    scale: float = 1.0       # series units -> the calendar's display units
    vintage_rank: int = 1    # 1 = first print; 2 = the second estimate (GDP prelim) ...
    country: str = "US"
    currency: str = "USD"


RELEASES: tuple[ReleaseSpec, ...] = (
    ReleaseSpec("USD Non-Farm Employment Change", "PAYEMS", "diff", "labour_surprise", 8),
    ReleaseSpec("USD Unemployment Rate", "UNRATE", "level", "labour_surprise", 8),
    ReleaseSpec("USD Average Hourly Earnings m/m", "CES0500000003", "pct_mom",
                "labour_surprise", 8),
    ReleaseSpec("USD Unemployment Claims", "ICSA", "level", "labour_surprise", 8,
                scale=1e-3),
    ReleaseSpec("USD CPI m/m", "CPIAUCSL", "pct_mom", "inflation_surprise", 8),
    ReleaseSpec("USD CPI y/y", "CPIAUCNS", "pct_yoy", "inflation_surprise", 8),
    ReleaseSpec("USD Core CPI m/m", "CPILFESL", "pct_mom", "inflation_surprise", 8),
    ReleaseSpec("USD Core CPI y/y", "CPILFENS", "pct_yoy", "inflation_surprise", 8),
    ReleaseSpec("USD Core PCE Price Index m/m", "PCEPILFE", "pct_mom", "inflation_surprise", 8),
    ReleaseSpec("USD PPI m/m", "PPIFIS", "pct_mom", "inflation_surprise", 8),
    ReleaseSpec("USD Core PPI m/m", "PPIFES", "pct_mom", "inflation_surprise", 8),
    ReleaseSpec("USD Retail Sales m/m", "RSAFS", "pct_mom", "other", 8),
    ReleaseSpec("USD Core Retail Sales m/m", "RSFSXMV", "pct_mom", "other", 8),
    ReleaseSpec("USD Durable Goods Orders m/m", "DGORDER", "pct_mom", "other", 8),
    ReleaseSpec("USD Core Durable Goods Orders m/m", "ADXTNO", "pct_mom", "other", 8),
    ReleaseSpec("USD Personal Income m/m", "PI", "pct_mom", "other", 8),
    ReleaseSpec("USD Personal Spending m/m", "PCE", "pct_mom", "other", 8),
    ReleaseSpec("USD Advance GDP q/q", "GDPC1", "pct_qoq_saar", "other", 8),
    ReleaseSpec("USD Prelim GDP q/q", "GDPC1", "pct_qoq_saar", "other", 8, vintage_rank=2),
    ReleaseSpec("USD Final GDP q/q", "GDPC1", "pct_qoq_saar", "other", 8, vintage_rank=3),
    ReleaseSpec("USD Industrial Production m/m", "INDPRO", "pct_mom", "other", 9, 15),
    ReleaseSpec("USD Building Permits", "PERMIT", "level", "other", 8, scale=1e-3),
    ReleaseSpec("USD Housing Starts", "HOUST", "level", "other", 8, scale=1e-3),
    ReleaseSpec("USD JOLTS Job Openings", "JTSJOL", "level", "labour_surprise", 10, 0,
                scale=1e-3),
    ReleaseSpec("USD Trade Balance", "BOPGSTB", "level", "other", 8, scale=1e-3),
    ReleaseSpec("USD New Home Sales", "HSN1F", "level", "other", 10, 0),
)
BY_TITLE = {r.title: r for r in RELEASES}


# ============================================================================== small helpers
def _iso(t: datetime) -> str:
    return t.astimezone(UTC).isoformat(timespec="seconds")


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        got = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return got if got.tzinfo else got.replace(tzinfo=UTC)


_NUM = re.compile(r"^\s*([+-]?\d+(?:\.\d+)?)\s*([%KMBT]?)\s*$", re.IGNORECASE)


def parse_number(text: Any) -> tuple[float | None, int]:
    """The calendar's display number and its decimals: '0.4%' -> (0.4, 1), '55K' -> (55, 0).
    The suffix is the display unit and is NOT applied: the spec's `scale` maps the series to it."""
    m = _NUM.match(str(text or ""))
    if not m:
        return None, 0
    raw = m.group(1)
    decimals = len(raw.split(".", 1)[1]) if "." in raw else 0
    return float(raw), decimals


def scheduled_utc(spec: ReleaseSpec, on: date) -> datetime:
    return datetime(on.year, on.month, on.day, spec.hour, spec.minute, tzinfo=ET).astimezone(UTC)


# ============================================================================== consensus side
def _vintage_rows(folder: Path) -> Iterable[dict[str, Any]]:
    if not folder.is_dir():
        return
    for path in sorted(folder.glob("rollup_*.jsonl.gz")):
        try:
            with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(row, dict):
                        yield row
        except (OSError, EOFError):
            continue
    for path in sorted(folder.glob("discoveries_*.json")):
        try:
            doc = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        rows = doc.get("discoveries") if isinstance(doc, dict) else doc
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict):
                yield row


def consensus_vintages(folder: Path = VINTAGES) -> dict[tuple[str, str], dict[str, Any]]:
    """(title, scheduled ET date) -> the LAST consensus captured BEFORE the scheduled instant.

    Captures at or after the instant are refused: by then the actual exists and a "forecast"
    edited after it is not an expectation. The first capture is kept too, so the drift of the
    consensus into the release is visible.
    """
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in _vintage_rows(folder):
        title = str(row.get("title") or "").strip()
        spec = BY_TITLE.get(title)
        when = _parse_time(row.get("event_date"))
        captured = _parse_time(row.get("captured_at") or row.get("found_at"))
        if spec is None or when is None or captured is None:
            continue
        sched = scheduled_utc(spec, when.astimezone(ET).date())
        if captured >= sched:
            continue
        value, decimals = parse_number(row.get("forecast"))
        prev, _ = parse_number(row.get("previous"))
        key = (title, when.astimezone(ET).date().isoformat())
        cur = out.get(key)
        if value is None:
            if cur is None:
                out[key] = {"consensus": None, "previous_ff": prev, "impact": row.get("impact"),
                            "captured_at": _iso(captured), "first_captured_at": _iso(captured),
                            "decimals": decimals, "scheduled_utc": _iso(sched)}
            continue
        if cur is None or cur.get("consensus") is None or captured.isoformat() > str(
                cur["captured_at"]):
            first = (cur or {}).get("first_captured_at") or _iso(captured)
            first_c = (cur or {}).get("first_consensus", value) if cur else value
            out[key] = {"consensus": value, "previous_ff": prev, "impact": row.get("impact"),
                        "captured_at": _iso(captured), "first_captured_at": first,
                        "first_consensus": first_c, "decimals": decimals,
                        "scheduled_utc": _iso(sched)}
    return out


# ============================================================================== actual side
def load_alfred(series: str, folder: Path = ALFRED) -> Any:
    """(observation_date, realtime_date, value), or None. Never the revised fredgraph file."""
    import pandas as pd
    for ext in (".parquet", ".csv"):
        p = folder / f"{series}{ext}"
        if p.exists():
            try:
                df = pd.read_parquet(p) if ext == ".parquet" else pd.read_csv(p)
            except Exception:                            # pragma: no cover - corrupt file
                return None
            df["observation_date"] = pd.to_datetime(df["observation_date"])
            df["realtime_date"] = pd.to_datetime(df["realtime_date"])
            df["value"] = pd.to_numeric(df["value"], errors="coerce").astype(float)
            return df.dropna().sort_values(["observation_date", "realtime_date"])
    return None


def _lag(obs: Any, transform: str) -> Any:
    import pandas as pd
    if transform in ("pct_mom", "diff"):
        return obs - pd.DateOffset(months=1) if obs.day == 1 else obs - pd.Timedelta(days=7)
    if transform == "pct_yoy":
        return obs - pd.DateOffset(years=1)
    if transform == "pct_qoq_saar":
        return obs - pd.DateOffset(months=3)
    return None


def _value_as_of(df: Any, obs: Any, as_of: Any) -> float | None:
    rows = df[(df["observation_date"] == obs) & (df["realtime_date"] <= as_of)]
    if rows.empty:
        return None
    return float(rows["value"].iloc[-1])


def transformed(df: Any, obs: Any, as_of: Any, spec: ReleaseSpec) -> float | None:
    """The headline number for `obs`, computed ONLY from what was published by `as_of`."""
    x = _value_as_of(df, obs, as_of)
    if x is None:
        return None
    if spec.transform == "level":
        return x * spec.scale
    prev = _value_as_of(df, _lag(obs, spec.transform), as_of)
    if prev is None:
        return None
    if spec.transform == "diff":
        return (x - prev) * spec.scale
    if prev == 0:
        return None
    if spec.transform in ("pct_mom", "pct_yoy"):
        return (x / prev - 1.0) * 100.0
    if spec.transform == "pct_qoq_saar":
        return ((x / prev) ** 4 - 1.0) * 100.0
    return None


def release_vintage(df: Any, spec: ReleaseSpec) -> list[dict[str, Any]]:
    """Every release of the series this spec's rank describes: reference period, the vintage it
    was published in, its value then, the prior period's first print and its value as revised
    at this release, and every later revision of this period with its vintage."""
    import pandas as pd
    out: list[dict[str, Any]] = []
    vints_by_obs = df.groupby("observation_date")["realtime_date"].apply(
        lambda s: sorted(set(s)))
    record_start = df["realtime_date"].min()
    for obs, vints in vints_by_obs.items():
        if len(vints) < spec.vintage_rank:
            continue
        v = vints[spec.vintage_rank - 1]
        # A first print dated at the START of ALFRED's record is the record's start, not the
        # period's publication (fetch_alfred.release_lag says the same): not a release.
        if spec.vintage_rank == 1 and v <= record_start + pd.Timedelta(days=7):
            continue
        actual = transformed(df, obs, v, spec)
        if actual is None:
            continue
        lag_obs = _lag(obs, spec.transform) if spec.transform != "level" else (
            vints_by_obs.index[vints_by_obs.index.get_loc(obs) - 1]
            if vints_by_obs.index.get_loc(obs) > 0 else None)
        prev_first = prev_rev = None
        if lag_obs is not None and lag_obs in vints_by_obs.index:
            lv = vints_by_obs[lag_obs]
            prev_first = transformed(df, lag_obs, lv[0], spec)
            prev_rev = transformed(df, lag_obs, v, spec)
        revisions = []
        last = actual
        for later in vints[spec.vintage_rank:]:
            val = transformed(df, obs, later, spec)
            if val is not None and not math.isclose(val, last, rel_tol=0, abs_tol=1e-9):
                revisions.append({"vintage": later.date().isoformat(), "value": val})
                last = val
        out.append({"reference_period": obs.date().isoformat(),
                    "vintage": v.date().isoformat(), "actual": actual,
                    "previous_first": prev_first, "previous_revised": prev_rev,
                    "revisions": revisions})
    return out


def nowcast(first_prints: Sequence[float]) -> float | None:
    """Declared naive expectation: EWMA (half-life 3) of the last twelve first prints."""
    tail = [x for x in first_prints[-NOWCAST_N:] if x is not None and math.isfinite(x)]
    if len(tail) < 3:
        return None
    w = [0.5 ** ((len(tail) - 1 - i) / NOWCAST_HALF_LIFE) for i in range(len(tail))]
    return sum(a * b for a, b in zip(tail, w, strict=True)) / sum(w)


def _round(x: float | None, decimals: int) -> float | None:
    return None if x is None else round(float(x), max(0, int(decimals)))


# ============================================================================== ALFRED refresh
def gauntlet_terms(source_id: str, clearances: Path | None = None) -> tuple[bool, str]:
    """(may this source's pairs reach the gauntlet?, why) -- `libs.data.terms_hold`, fail closed."""
    root = str(ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from libs.data.terms_hold import gauntlet_terms as held
    except Exception as exc:                             # pragma: no cover - import-context only
        return False, f"HELD_TERMS: terms gate unavailable ({type(exc).__name__})"
    return held(source_id, clearances or CLEARANCES)


def alfred_key_present() -> bool:
    try:
        sys.path.insert(0, str(DESK / "research"))
        import fetch_alfred  # type: ignore[import-not-found]
        return bool(fetch_alfred.api_key())
    except Exception:
        return False


def key_presence() -> dict[str, Any]:
    """Where the FRED key was found (process | machine | user | file | absent) and its length."""
    try:
        sys.path.insert(0, str(DESK / "research"))
        import fetch_alfred  # type: ignore[import-not-found]
        return dict(fetch_alfred.key_presence())
    except Exception as exc:
        return {"present": False, "origin": UNMEASURED, "why": type(exc).__name__}


def refresh_alfred(budget_s: float, series: Sequence[str] | None = None,
                   folder: Path = ALFRED) -> dict[str, Any]:
    """Re-fetch the stale first-print files through the desk's own fetcher, inside a budget.
    No key: BLOCKED_AUTH, nothing fetched, nothing substituted."""
    wanted = sorted(set(series or (r.series for r in RELEASES)))
    if not alfred_key_present():
        return {"status": "BLOCKED_AUTH", "key": key_presence(),
                "why": ("no FRED key in the process environment, the machine or user registry "
                        "environment, or a secrets file on this host; first prints come only "
                        "from ALFRED vintages and none is substituted"),
                "series": wanted}
    now = time.time()
    stale = [s for s in wanted
             if not (folder / f"{s}.parquet").exists()
             or (now - (folder / f"{s}.parquet").stat().st_mtime) / 3600.0 > ALFRED_MAX_AGE_H]
    if not stale:
        return {"status": "FRESH", "series": wanted}
    try:
        r = subprocess.run([sys.executable, str(FETCH_ALFRED), *stale,
                            f"--max-age-h={ALFRED_MAX_AGE_H}"], cwd=str(DESK),
                           capture_output=True, text=True, timeout=max(30.0, budget_s),
                           check=False)
        return {"status": "REFRESHED" if r.returncode == 0 else f"RC_{r.returncode}",
                "stale": stale, "tail": (r.stdout + r.stderr)[-400:]}
    except subprocess.TimeoutExpired:
        return {"status": "BUDGET", "stale": stale,
                "why": "fetch budget reached; the remaining series are owed to the next pass"}


# ============================================================================== the build
def build(*, now: datetime | None = None, vintages: Path = VINTAGES, alfred: Path = ALFRED,
          refresh_budget_s: float = 0.0, conditioning: Mapping[str, Any] | None = None
          ) -> dict[str, Any]:
    """Store rows for `event_surprise`, sensor observations, and the census.

    Store rows are (release, period=scheduled ET date) so `event_surprise.join_sides` pairs a
    consensus half with its actual when both exist, and a lone consensus waits.
    """
    from macro.surprise import composite_z, surprise_family
    when = now or datetime.now(UTC)
    refreshed = (refresh_alfred(refresh_budget_s, folder=alfred) if refresh_budget_s > 0
                 else {"status": "skipped"})
    cons = consensus_vintages(vintages)
    ff_ok, ff_why = gauntlet_terms("ff_calendar_vintage")
    rows: list[dict[str, Any]] = []
    sensors: list[dict[str, Any]] = []
    census: dict[str, Any] = {"releases": {}, "consensus_vintages": len(cons),
                              "alfred_refresh": refreshed, "fred_key": key_presence()}
    z_at_instant: dict[str, dict[str, float | None]] = {}
    frames: dict[str, Any] = {}
    for spec in RELEASES:
        stat: dict[str, Any] = {"series": spec.series, "consensus_rows": 0, "pairs": 0,
                                "nowcast_pairs": 0, "first_prints": 0, "revisions": 0}
        census["releases"][spec.title] = stat
        mine = {d: c for (t, d), c in cons.items() if t == spec.title}
        stat["consensus_rows"] = sum(1 for c in mine.values() if c.get("consensus") is not None)
        df = frames.get(spec.series)
        if df is None and spec.series not in frames:
            df = load_alfred(spec.series, alfred)
            frames[spec.series] = df
        prints = release_vintage(df, spec) if df is not None else []
        stat["first_prints"] = len(prints)
        stat["actual_status"] = ("ALFRED" if df is not None else
                                 ("BLOCKED_AUTH" if not alfred_key_present() else
                                  "NOT_FETCHED"))
        by_day = {p["vintage"]: p for p in prints}
        firsts: list[float] = []
        cons_hist: list[float] = []
        nowcast_errs: list[float] = []
        horizon = (when - timedelta(days=1200)).date().isoformat()
        for p in prints:
            sched = scheduled_utc(spec, date.fromisoformat(p["vintage"]))
            if sched > when:
                break
            exp = nowcast(firsts)
            c = mine.get(p["vintage"])
            decimals = int((c or {}).get("decimals") or (1 if "pct" in spec.transform else 0))
            actual = _round(p["actual"], decimals)
            consensus = (c or {}).get("consensus")
            fam = surprise_family(
                actual, consensus, history=cons_hist,
                previous_first=_round(p["previous_first"], decimals),
                previous_revised=_round(p["previous_revised"], decimals),
                model_expectation=exp, model_history=nowcast_errs,
                conditioning=conditioning, release_id=spec.title)
            base = {"period": p["vintage"], "reference_period": p["reference_period"],
                    "at": _iso(sched), "kind": spec.kind, "instruments": list(USD_INSTRUMENTS),
                    "country": spec.country, "currency": spec.currency,
                    "previous_first": _round(p["previous_first"], decimals),
                    "previous_revised": _round(p["previous_revised"], decimals),
                    "revisions": [{**r, "value": _round(r["value"], decimals)}
                                  for r in p["revisions"]],
                    "impact": (c or {}).get("impact") or UNMEASURED,
                    "pit": {"scheduled_time": _iso(sched), "publication_time": _iso(sched),
                            "knowable_at": _iso(sched),
                            "consensus_knowable_at": (c or {}).get("captured_at", UNMEASURED),
                            "first_vintage": p["vintage"]},
                    "survey_high": UNMEASURED, "survey_low": UNMEASURED,
                    "whisper": UNMEASURED,
                    "family": fam}
            if p["vintage"] >= horizon and exp is not None:
                rows.append({**base, "release": f"{spec.title}|nowcast_ewm12", "actual": actual,
                             "consensus": _round(exp, decimals + 2), "provides": "both",
                             "expectation_kind": "nowcast_ewm12",
                             "source_id": f"alfred:{spec.series}"})
                stat["nowcast_pairs"] += 1
            if consensus is not None:
                # stored and counted whatever the terms say; event_surprise.terms_filter is the
                # gate that keeps a held pair out of the gauntlet (audit #204 item 4)
                if not ff_ok:
                    stat["held_terms"] = int(stat.get("held_terms", 0)) + 1
                rows.append({**base, "release": spec.title, "actual": actual,
                             "consensus": consensus, "provides": "both",
                             "expectation_kind": "consensus_median",
                             "consensus_captured_at": c.get("captured_at"),
                             "previous_ff": c.get("previous_ff"),
                             "source_id": f"ff_calendar_vintage+alfred:{spec.series}"})
                stat["pairs"] += 1
                cons_hist.append(float(actual) - float(consensus))  # type: ignore[arg-type]
                z_at_instant.setdefault(_iso(sched), {})[spec.title] = (
                    fam["z_release"] if isinstance(fam["z_release"], float) else None)
            sensors.append({"spec": spec, "print": p, "actual": actual, "family": fam,
                            "consensus": consensus, "expected": exp, "sched": sched,
                            "decimals": decimals,
                            "consensus_at": (c or {}).get("captured_at")})
            if exp is not None and actual is not None:
                nowcast_errs.append(float(actual) - float(exp))
            firsts.append(float(p["actual"]))
        # CONSENSUS HALVES whose actual is not here yet: they wait, they are never completed.
        for d, c in sorted(mine.items()):
            if d in by_day or c.get("consensus") is None:
                continue
            sched = scheduled_utc(spec, date.fromisoformat(d))
            rows.append({"release": spec.title, "period": d, "at": _iso(sched),
                         "consensus": c["consensus"], "actual": None, "provides": "consensus",
                         "kind": spec.kind, "instruments": list(USD_INSTRUMENTS),
                         "impact": c.get("impact") or UNMEASURED,
                         "consensus_captured_at": c.get("captured_at"),
                         "previous_ff": c.get("previous_ff"),
                         "expectation_kind": "consensus_median",
                         "source_id": "ff_calendar_vintage",
                         "waiting_for": ("the first print (ALFRED)" if df is not None else
                                         f"the first print: actual side {stat['actual_status']}")})
    composites = {at: composite_z(zs) for at, zs in z_at_instant.items() if len(zs) >= 2}
    census["composites"] = len([c for c in composites.values()
                                if c.get("value") != UNMEASURED])
    census["rows"] = len(rows)
    census["terms"] = {"ff_calendar_vintage": ff_why or "admitted",
                       "gauntlet": "HELD" if not ff_ok else "admitted",
                       "nowcast_ewm12": "admitted (ALFRED + the desk's own model)"}
    census["status"] = ("present" if any(r.get("actual") is not None for r in rows) else
                        ("BLOCKED_AUTH" if not alfred_key_present() else UNMEASURED))
    return {"rows": rows, "sensor_inputs": sensors, "composites": composites,
            "census": census}


def sensor_observations(sensor_inputs: Sequence[Mapping[str, Any]], received_at: datetime
                        ) -> list[Any]:
    """The same releases as universal sensor observations: first print, then each revision as
    its own row (the ledger links them), then the consensus as its own observation."""
    from libs.research import sensor_contract as sc
    out = []
    for s in sensor_inputs:
        spec: ReleaseSpec = s["spec"]
        p = s["print"]
        fam = s["family"]
        z = fam.get("z_release")
        pct = fam.get("percentile")
        common = {"sensor_id": "macro:release", "source_id": f"alfred:{spec.series}",
                  "dataset_id": "alfred_first_print", "entity": spec.country,
                  "geography": spec.country, "asset_domain": "macro", "metric": spec.title,
                  "unit": "%" if "pct" in spec.transform else "display", "kind": "state",
                  "sensor_class": "macro_release", "event_time": p["reference_period"],
                  "scheduled_time": s["sched"], "publication_time": s["sched"],
                  "licence": "FRED/ALFRED terms: public data, attribution",
                  "commercial_rights": "public statistics (US federal), attribution"}
        first = sc.make(**common, value=s["actual"], consensus=s["consensus"],
                        expected_value=s["expected"], knowable_at=s["sched"],
                        knowable_basis="calendar", received_at=max(received_at, s["sched"]), parse_complete_at=received_at
                        if received_at >= s["sched"] else s["sched"],
                        surprise_z=z if isinstance(z, float) else None,
                        percentile=pct if isinstance(pct, float) else None,
                        attributes={"vintage": p["vintage"], "family": fam})
        out.append(first)
        for r in p["revisions"]:
            vt = scheduled_utc(spec, date.fromisoformat(r["vintage"]))
            out.append(sc.make(**common, value=_round(r["value"], s["decimals"]),
                               knowable_at=vt, knowable_basis="calendar",
                               received_at=max(received_at, vt),
                               parse_complete_at=max(received_at, vt),
                               attributes={"vintage": r["vintage"], "revision": True}))
        if s["consensus"] is not None and s.get("consensus_at"):
            out.append(sc.make(**{**common, "metric": f"{spec.title}|consensus",
                                  "dataset_id": "ff_calendar_vintage",
                                  "source_id": "ff_calendar_vintage",
                                  "licence": UNMEASURED, "commercial_rights": UNMEASURED},
                               value=s["consensus"], knowable_at=s["consensus_at"],
                               knowable_basis="bounded_by_receipt", received_at=s["consensus_at"],
                               parse_complete_at=s["consensus_at"],
                               attributes={"expectation_kind": "consensus_median"}))
    return out
