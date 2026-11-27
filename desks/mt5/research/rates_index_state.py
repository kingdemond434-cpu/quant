"""RATES AND INDEX STATE -- a point-in-time rates axis for the index and gold cells. REPORT-ONLY.

IDEA_QUEUE row 206. macro_state.json stopped on 2026-09-09 and 14 of its 22 series were never
fetched; the 15 index CFDs and UKGILT have no rates conditioner. This file builds one.

SOURCES ARE PRIMARY PUBLISHERS ONLY, AND EVERY FETCH IS TERMS-GATED.
  FRED / ALFRED (the St. Louis Fed's aggregator, every one of its hosts) is TERMS-REFUSED for
  every automated fetch (governance ruling 2026-11-13). This file never contacts it; a test fails
  if any of its host names appears in the source. The rates come from the publishers instead:
  * US Treasury daily par yield curve CSV (home.treasury.gov): 2y, 5y and 10y nominal.
  * US Treasury daily par REAL yield curve CSV: 10y real. The 10y breakeven is DERIVED as
    nominal 10y minus real 10y on the same date.
  * Cboe VIX is NOT fetched: it is third-party Cboe data, which the 2026-11-13 terms ruling
    allows only from the owner under the owner's terms, so VIX reads UNMEASURED, named.
  * NY Fed ACM term premium, ACMTP10.
  * ICE BofA HY OAS has NO public-domain primary source (ICE licenses it), so it reads
    UNMEASURED, named, on every run.

  Before ANY request the URL is checked against the desk's own terms ledger
  (`libs.research.equivalence_ontology.terms_verdict`, a verbatim permitting clause per publisher
  prefix). Anything but PERMITTED -- including a ledger that cannot be imported -- is NOT fetched
  and reads UNMEASURED with the reason. As of 2026-11-14 the ledger holds home.treasury.gov as HELD
  (no reuse sentence found on its policies page) and carries no row for
  newyorkfed.org, so this report reads UNMEASURED until a terms row lands. That is the gate
  working, not a defect to route around.

POINT IN TIME. None of these files carries vintages. Every row is stamped with the time THIS run
first saw it (`known_at` = fetch time), a file first seen after `as_of` does not exist as of
`as_of`, and an observation dated after `as_of` is dropped. Nothing is backfilled.

Outputs: desks/mt5/reports/RATES_INDEX_STATE.json
  curve level (10y, 2y), slope (10y - 2y), curvature (2x5y - 2y - 10y), real 10y, 10y breakeven,
  ACM 10y term premium and its 20-observation change, HY OAS z (UNMEASURED), VIX level and z.
  Each carries a freshness stamp.

ROBOTS.TXT BEFORE EVERY PERMITTED FETCH, AND NO REDIRECT IS FOLLOWED (Auditor MF2). A URL the
terms ledger PERMITS is fetched only when the host's robots.txt, read under the SAME user agent the
fetch sends, allows that exact path. 404/410 means the host publishes no rules (allowed, the
standard reading). Anything else -- 3xx (a redirect is never followed, robots included), 401, 403,
429, 5xx, a network error -- is UNREADABLE robots, never read as permission: the URL is not
fetched, its inputs read UNMEASURED, and a missed-growth line is published on this artifact
(`missed_growth`, rail `rates_robots_gate`) and carried by research/missed_growth.py. Every request
is sent with allow_redirects=False; a 3xx answer is no fetch, with the reason named.

HTTP 401, 403 or 429, or a network error, from any source is a HARD STOP: no further request is
made to any host and every input not yet fetched reads UNMEASURED. Missing inputs are UNMEASURED,
never 0. The report carries status codes and exception TYPE names only -- never exception text,
never a filesystem path.

NO SCRIPT ENTRY GUARD (birth-obligation law, scripts/check_birth_obligations.py).
The hourly leg `rates_index_state` (research/hourly_cycle.py) calls `main()`
in-process. By hand, from the repo root:
    python -c "import sys; sys.path[:0]=['desks/mt5'];
        from research import rates_index_state as M; M.main()"
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sys
import urllib.robotparser
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import numpy as np

from libs.data import robots_body

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = DESK / "reports" / "RATES_INDEX_STATE.json"

UNMEASURED = "UNMEASURED"
STALE = "STALE"
MEASURED = "MEASURED"
PERMITTED = "PERMITTED"

_TREASURY = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
             "daily-treasury-rates.csv/{yr}/all?type={kind}&field_tdr_date_value={yr}"
             "&page&_format=csv")
TREASURY_NOMINAL = "daily_treasury_yield_curve"
TREASURY_REAL = "daily_treasury_real_yield_curve"
ACM_URL = ("https://www.newyorkfed.org/medialibrary/media/research/data_indicators/"
           "ACMTermPremium.csv")
#: A generic, honest client name. No account, repository or person is named to a publisher.
USER_AGENT = "quant-desk-research/1.0 (report-only; public data)"
HARD_STOP_CODES = (401, 403, 429)
#: robots.txt answers that mean "this host publishes no rules" (allowed). Every other non-200
#: robots answer is UNREADABLE and refuses the fetch.
ROBOTS_ABSENT_CODES = (404, 410)
ROBOTS_RAIL = "rates_robots_gate"

#: series id -> (description, source column)
TREASURY_NOMINAL_SERIES = {
    "UST2Y": ("2y nominal Treasury par yield", "2 YR"),
    "UST5Y": ("5y nominal Treasury par yield (curvature needs a middle tenor)", "5 YR"),
    "UST10Y": ("10y nominal Treasury par yield", "10 YR"),
}
TREASURY_REAL_SERIES = {"USTREAL10Y": ("10y Treasury par real yield", "10 YR")}
NO_PRIMARY_SOURCE = {
    "HY_OAS": ("ICE BofA US High Yield OAS is ICE-licensed and has no terms-permitted "
               "primary route; not fetched"),
    "VIX": ("Cboe VIX is third-party Cboe data: owner-only under the 2026-11-13 terms ruling, "
            "never fetched automatically"),
}

LOOKBACK_YEARS = 2           # Treasury files are per calendar year; this year and last
Z_WINDOW = 252               # observations in the z-score window
Z_MIN_OBS = 120              # fewer than this -> z is UNMEASURED
TP_CHANGE_OBS = 20           # term-premium change horizon, in observations
STALE_BDAYS = 5              # latest observation older than this many business days -> STALE


@dataclass(frozen=True)
class Obs:
    obs_date: date
    value: float
    released: date        # when this run first saw the observation (no vintages exist)


Fetcher = Callable[[str], tuple[int, str]]
TermsGate = Callable[[str], str]


def http_get(url: str) -> tuple[int, str]:
    """GET with an honest, generic UA and NO redirect following. Returns (status, text); a 3xx
    comes back as its own status, and a transport failure returns (-1, <exception type name>) and
    never the exception's message."""
    import requests  # local: tests never import the network stack's side effects

    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60,
                         allow_redirects=False)
    except requests.RequestException as exc:
        return -1, type(exc).__name__
    return r.status_code, r.text


def ledger_terms_verdict(url: str) -> str:
    """The desk's terms ledger verdict for `url`. An unimportable ledger is HELD: fail closed."""
    try:
        from libs.research.equivalence_ontology import terms_verdict
    except Exception:                                    # any failure is HELD
        return "HELD"
    try:
        return str(terms_verdict(url))
    except Exception:                                    # any failure is HELD
        return "HELD"


def host_of(url: str) -> str:
    return urlsplit(url).hostname or "unknown-host"


def treasury_url(kind: str, yr: int) -> str:
    return _TREASURY.format(yr=yr, kind=kind)


# ----------------------------------------------------------------------------- parsers

_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y", "%d-%b-%y")


def _parse_date(s: str) -> date | None:
    s = (s or "").strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=UTC).date()
        except ValueError:
            continue
    return None


def parse_columns(text: str, columns: dict[str, str], known_at: datetime,
                  as_of: date, date_col: str = "DATE") -> dict[str, list[Obs]]:
    """A dated CSV -> {series id: [Obs]} for each `columns` entry (id -> header, case-blind).

    Rows dated after `as_of`, blank cells and non-finite values are dropped. A file first seen
    after `as_of` does not exist as of `as_of`, so every series is empty."""
    out: dict[str, list[Obs]] = {sid: [] for sid in columns}
    if known_at.date() > as_of:
        return out
    header: list[str] | None = None
    for row in csv.reader(io.StringIO(text)):
        if header is None:
            up = [c.strip().upper() for c in row]
            if date_col in up and any(col.upper() in up for col in columns.values()):
                header = up
            continue
        if len(row) < len(header):
            continue
        od = _parse_date(row[header.index(date_col)])
        if od is None or od > as_of:
            continue
        for sid, col in columns.items():
            if col.upper() not in header:
                continue
            try:
                v = float(row[header.index(col.upper())])
            except ValueError:
                continue
            if math.isfinite(v):
                out[sid].append(Obs(od, v, known_at.date()))
    for sid in out:
        dedup = {o.obs_date: o for o in out[sid]}
        out[sid] = sorted(dedup.values(), key=lambda o: o.obs_date)
    return out


def parse_acm_csv(text: str, known_at: datetime, as_of: date) -> list[Obs]:
    """ACMTP10 from the NY Fed CSV. Stamped `known_at` (the file has no vintages)."""
    return parse_columns(text, {"ACMTP10": "ACMTP10"}, known_at, as_of)["ACMTP10"]


# ----------------------------------------------------------------------------- metrics

def _bdays_between(a: date, b: date) -> int:
    return int(np.busday_count(a, b)) if b > a else 0


def freshness(obs: list[Obs], as_of: date) -> dict[str, Any]:
    last = obs[-1]
    age = _bdays_between(last.obs_date, as_of)
    return {"obs_date": last.obs_date.isoformat(), "known_at": last.released.isoformat(),
            "age_business_days": age, "status": MEASURED if age <= STALE_BDAYS else STALE}


def _unmeasured(why: str) -> dict[str, Any]:
    return {"status": UNMEASURED, "value": UNMEASURED, "why": why}


def single(name: str, series: dict[str, list[Obs] | str], as_of: date) -> dict[str, Any]:
    s = series.get(name)
    if not isinstance(s, list) or not s:
        return _unmeasured(f"{name}: {s if isinstance(s, str) else 'no observations'}")
    f = freshness(s, as_of)
    return {"status": f["status"], "value": round(s[-1].value, 4), "series": name,
            "freshness": f}


def _aligned(series: dict[str, list[Obs] | str], names: tuple[str, ...]):
    """Latest observation date common to all `names`, with each one's Obs on it."""
    maps = {}
    for n in names:
        s = series.get(n)
        if not isinstance(s, list) or not s:
            return None, n
        maps[n] = {o.obs_date: o for o in s}
    common = set.intersection(*(set(m) for m in maps.values()))
    if not common:
        return None, "no common observation date"
    d = max(common)
    return {n: maps[n][d] for n in names}, None


def combo(names: tuple[str, ...], fn: Callable[..., float], label: str,
          series: dict[str, list[Obs] | str], as_of: date) -> dict[str, Any]:
    got, missing = _aligned(series, names)
    if got is None:
        return _unmeasured(f"{label}: {missing} missing")
    value = fn(*(got[n].value for n in names))
    od = next(iter(got.values())).obs_date
    age = _bdays_between(od, as_of)
    st = MEASURED if age <= STALE_BDAYS else STALE
    return {"status": st, "value": round(value, 4), "formula": label,
            "freshness": {"obs_date": od.isoformat(),
                          "known_at": max(o.released for o in got.values()).isoformat(),
                          "age_business_days": age, "status": st}}


def zscore(name: str, series: dict[str, list[Obs] | str], as_of: date) -> dict[str, Any]:
    s = series.get(name)
    if not isinstance(s, list) or not s:
        return _unmeasured(f"{name}: {s if isinstance(s, str) else 'no observations'}")
    win = s[-Z_WINDOW:]
    if len(win) < Z_MIN_OBS:
        return _unmeasured(f"{name}: {len(win)} obs < {Z_MIN_OBS} for a z-score")
    vals = np.array([o.value for o in win])
    sd = float(vals.std(ddof=1))
    if sd == 0.0:
        return _unmeasured(f"{name}: zero variance in window")
    f = freshness(s, as_of)
    return {"status": f["status"], "value": round((vals[-1] - vals.mean()) / sd, 4),
            "level": round(float(vals[-1]), 4), "window_obs": len(win),
            "window_mean": round(float(vals.mean()), 4), "window_sd": round(sd, 4),
            "series": name, "freshness": f}


def change(name: str, series: dict[str, list[Obs] | str], as_of: date,
           n: int = TP_CHANGE_OBS) -> dict[str, Any]:
    s = series.get(name)
    if not isinstance(s, list) or len(s) <= n:
        return _unmeasured(f"{name}: fewer than {n + 1} observations")
    f = freshness(s, as_of)
    return {"status": f["status"], "value": round(s[-1].value - s[-1 - n].value, 4),
            "from_obs_date": s[-1 - n].obs_date.isoformat(), "horizon_obs": n,
            "series": name, "freshness": f}


# ----------------------------------------------------------------------------- collect

@dataclass(frozen=True)
class Source:
    key: str
    urls: tuple[str, ...]
    columns: dict[str, str]


def sources(as_of: date, acm_url: str = ACM_URL) -> tuple[Source, ...]:
    years = tuple(range(as_of.year - LOOKBACK_YEARS + 1, as_of.year + 1))
    nominal = {sid: col for sid, (_, col) in TREASURY_NOMINAL_SERIES.items()}
    real = {sid: col for sid, (_, col) in TREASURY_REAL_SERIES.items()}
    return (
        Source("treasury_nominal", tuple(treasury_url(TREASURY_NOMINAL, y) for y in years),
               nominal),
        Source("treasury_real", tuple(treasury_url(TREASURY_REAL, y) for y in years), real),
        Source("nyfed_acm", (acm_url,), {"ACMTP10": "ACMTP10"}),
    )


def robots_url(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}/robots.txt"


#: robots_url -> parsed rules, or the UNREADABLE reason string. One read per host per run.
RobotsCache = dict[str, urllib.robotparser.RobotFileParser | str]


def robots_refusal(url: str, fetch: Fetcher, cache: RobotsCache) -> tuple[str | None, bool]:
    """(None, False) when robots.txt allows this exact path for USER_AGENT; otherwise
    (why, unreadable). robots.txt is fetched through the SAME fetcher, so it carries the same UA
    and follows no redirect. The reply is read by the shared fail-closed reader
    (libs.data.robots_body): an HTML body, 401/403/429/451 or any non-2xx other than 404/410
    is a refusal, never an assumed allow."""
    key = robots_url(url)
    host = host_of(url)
    if key not in cache:
        status, text = fetch(key)
        if status == -1:
            cache[key] = f"robots.txt unreadable at {host} (network error {text[:40]})"
        elif 300 <= status < 400:
            cache[key] = f"robots.txt unreadable at {host} (HTTP {status} redirect not followed)"
        else:
            got = robots_body.robots_rules_or_refusal(status, None, text)
            cache[key] = (f"robots.txt unreadable at {host} ({got})"
                          if isinstance(got, str) else got)
    rules = cache[key]
    if isinstance(rules, str):
        return rules, True
    if not rules.can_fetch(USER_AGENT, url):
        return f"robots.txt at {host} disallows this path for our agent", False
    return None, False


def robots_missed_growth_line(why: str, sids: Iterable[str], now: datetime) -> dict[str, Any]:
    """One missed-growth line in the published-organ shape (run_sharded_gauntlet,
    forward_slot_ranker). The rail register is sealed, so the line rides this artifact and
    research/missed_growth.py carries it; what the unfetched inputs cost in E[log W] is not
    measured, so the value is UNMEASURED."""
    return {"day": now.date().isoformat(), "at": now.isoformat(timespec="seconds"),
            "rail": ROBOTS_RAIL, "kind": "opportunity_cost", "value": None,
            "verdict": UNMEASURED, "units": "rates inputs not fetched",
            "reason": "robots_unreadable", "inputs": sorted(sids),
            "why": (f"{why}: fail closed, so these inputs read UNMEASURED this pass and every "
                    "conditioner that needs them is blind; their E[log W] price is not "
                    "measured")}


def _merge(parts: Iterable[dict[str, list[Obs]]], sids: Iterable[str]) -> dict[str, list[Obs]]:
    out: dict[str, dict[date, Obs]] = {sid: {} for sid in sids}
    for part in parts:
        for sid, obs in part.items():
            for o in obs:
                out.setdefault(sid, {})[o.obs_date] = o
    return {sid: sorted(m.values(), key=lambda o: o.obs_date) for sid, m in out.items()}


def collect(as_of: date, *, fetch: Fetcher = http_get, terms: TermsGate = ledger_terms_verdict,
            acm_text: str | None = None, acm_known_at: datetime | None = None,
            acm_url: str = ACM_URL, now: datetime | None = None
            ) -> tuple[dict[str, list[Obs] | str], dict[str, Any]]:
    now = now or datetime.now(UTC)
    series: dict[str, list[Obs] | str] = {}
    log: dict[str, Any] = {"hard_stop": None, "sources": {}, "missed_growth": []}
    robots: RobotsCache = {}
    stopped = False
    for src in sources(as_of, acm_url):
        sids = tuple(src.columns)
        if src.key == "nyfed_acm" and acm_text is not None:
            series["ACMTP10"] = parse_acm_csv(acm_text, acm_known_at or now, as_of)
            log["sources"][src.key] = {"status": MEASURED, "via": "local file"}
            continue
        if stopped:
            for sid in sids:
                series[sid] = "not fetched: hard stop earlier in this run"
            log["sources"][src.key] = {"status": UNMEASURED, "why": "hard stop earlier"}
            continue
        held = sorted({host_of(u) for u in src.urls if terms(u) != PERMITTED})
        if held:
            why = (f"terms not PERMITTED by the desk terms ledger for {', '.join(held)}; "
                   "not fetched (fail closed)")
            for sid in sids:
                series[sid] = why
            log["sources"][src.key] = {"status": UNMEASURED, "why": why, "hosts": held}
            continue
        parts: list[dict[str, list[Obs]]] = []
        fail: str | None = None
        for url in src.urls:
            refused, unreadable = robots_refusal(url, fetch, robots)
            if refused:
                fail = f"{refused}; not fetched"
                if unreadable:
                    log["missed_growth"].append(robots_missed_growth_line(refused, sids, now))
                continue
            status, text = fetch(url)
            if 300 <= status < 400:
                fail = f"{host_of(url)} HTTP {status}: redirect not followed; no fetch"
                continue
            if status in HARD_STOP_CODES or status == -1:
                what = f"HTTP {status}" if status != -1 else f"network error {text}"
                stopped = True
                fail = f"{host_of(url)} {what} (hard stop)"
                log["hard_stop"] = fail
                break
            if status != 200:
                fail = f"{host_of(url)} HTTP {status}"
                continue
            try:
                parts.append(parse_columns(text, src.columns, now, as_of))
            except (csv.Error, ValueError) as exc:
                fail = f"{host_of(url)} parse failed: {type(exc).__name__}"
        merged = _merge(parts, sids)
        for sid in sids:
            series[sid] = merged.get(sid) or (fail or "no observations on or before as_of")
        log["sources"][src.key] = ({"status": MEASURED} if any(merged.values())
                                   else {"status": UNMEASURED, "why": fail or "no rows"})
    for sid, why in NO_PRIMARY_SOURCE.items():
        series[sid] = why
    return series, log


# ----------------------------------------------------------------------------- build

def build(series: dict[str, list[Obs] | str], log: dict[str, Any], as_of: date,
          now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    metrics = {
        "curve_level_10y": single("UST10Y", series, as_of),
        "curve_level_2y": single("UST2Y", series, as_of),
        "curve_slope_10y2y": combo(("UST10Y", "UST2Y"), lambda a, b: a - b,
                                   "UST10Y - UST2Y", series, as_of),
        "curve_curvature_2s5s10s": combo(("UST2Y", "UST5Y", "UST10Y"),
                                         lambda a, b, c: 2 * b - a - c,
                                         "2 x UST5Y - UST2Y - UST10Y", series, as_of),
        "real_yield_10y": single("USTREAL10Y", series, as_of),
        "breakeven_10y": combo(("UST10Y", "USTREAL10Y"), lambda a, b: a - b,
                               "UST10Y - USTREAL10Y", series, as_of),
        "term_premium_acm_10y": single("ACMTP10", series, as_of),
        "term_premium_acm_10y_change_20obs": change("ACMTP10", series, as_of),
        "hy_oas_z": zscore("HY_OAS", series, as_of),
        "vix_level": single("VIX", series, as_of),
        "vix_z": zscore("VIX", series, as_of),
    }
    inputs = {}
    for sid, s in series.items():
        if isinstance(s, list) and s:
            inputs[sid] = {"status": MEASURED, "n_obs": len(s),
                           "first_obs": s[0].obs_date.isoformat(),
                           "last_obs": s[-1].obs_date.isoformat(),
                           "known_at": s[-1].released.isoformat()}
        else:
            inputs[sid] = {"status": UNMEASURED,
                           "why": s if isinstance(s, str) else "no observations"}
    statuses = {m["status"] for m in metrics.values()}
    overall = (MEASURED if statuses == {MEASURED}
               else UNMEASURED if statuses == {UNMEASURED} else "PARTIAL")
    return {
        "artifact": "RATES_INDEX_STATE", "schema_version": 2, "report_only": True,
        "generated_at": now.isoformat(), "as_of": as_of.isoformat(),
        "source": "desks/mt5/research/rates_index_state.py", "idea_queue_row": 206,
        "status": overall, "hard_stop": log.get("hard_stop"),
        "sources": log.get("sources", {}),
        "missed_growth": list(log.get("missed_growth") or []),
        "robots_rule": ("before any PERMITTED fetch robots.txt is read under the fetch's own "
                        "user agent and only an allow proceeds; unreadable robots (3xx, 401, "
                        "403, 429, 5xx, network) is no fetch plus a missed-growth line; no "
                        "redirect is ever followed."),
        "terms_rule": ("every URL is checked against the desk terms ledger "
                       "(libs/research/equivalence_ontology.py TERMS_EVIDENCE) before any "
                       "request; anything but PERMITTED is not fetched and reads UNMEASURED. "
                       "Terms-refused aggregators are never contacted."),
        "pit_rule": ("no source carries vintages: every row is stamped with the time this run "
                     "first saw it, and rows dated after as_of are dropped."),
        "stale_after_business_days": STALE_BDAYS,
        "metrics": metrics, "inputs": inputs,
        "conditioner_for": ["US500", "NAS100", "US30", "GER40", "JPN225", "UKGILT",
                            "XAUUSD D1", "XAUUSD H4"],
    }


def write(report: dict[str, Any], out: Path = OUT) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, indent=1), encoding="utf-8")
    tmp.replace(out)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--as-of", type=date.fromisoformat, default=None,
                    help="PIT date (default: today UTC)")
    ap.add_argument("--acm-file", type=Path, default=None,
                    help="local copy of the NY Fed ACM CSV; stamped with its mtime")
    ap.add_argument("--acm-url", default=ACM_URL)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    now = datetime.now(UTC)
    as_of = a.as_of or now.date()
    acm_text: str | None = None
    acm_known: datetime | None = None
    if a.acm_file is not None:
        try:
            acm_text = a.acm_file.read_text(encoding="utf-8", errors="replace")
            acm_known = datetime.fromtimestamp(a.acm_file.stat().st_mtime, tz=UTC)
        except OSError as exc:
            print(f"rates_index_state: --acm-file unreadable ({type(exc).__name__}); "
                  "fetching instead", flush=True)
            acm_text = acm_known = None
    series, log = collect(as_of, acm_text=acm_text, acm_known_at=acm_known,
                          acm_url=a.acm_url, now=now)
    rep = build(series, log, as_of, now)
    if a.dry_run:
        print(json.dumps(rep, indent=1))
    else:
        write(rep, a.out)
        print(f"rates_index_state: status={rep['status']} hard_stop={rep['hard_stop']}")
    return 0

