#!/usr/bin/env python3
"""TOR METRICS: per-country Tor usage and censorship events as a slow political-stress state.

WHY THIS EXISTS (principal 2026-10-13, asked 2026-10-29 whether "the darkweb miner" had found
anything; it had not, because no onion lane existed). The lawful, CC0 face of the dark web is the
Tor Project's own measurement of who uses Tor and where it is being censored. A country whose
directly-connecting Tor users fall below the censorship detector's expected range is a country
whose state just blocked something; a country whose bridge users jump is one whose citizens are
routing around a block. Both are political-stress readings, published daily, about countries
whose currencies and indices the desk trades (RU, TR, CN, IR, VE ...).

SOURCE AND TERMS. `metrics.torproject.org/userstats-relay-country.csv` (date,country,users,
lower,upper,frac) and `userstats-bridge-country.csv` (date,country,users,frac -- the bridge file
carries NO detector bounds). The data is CC0; the clause is quoted verbatim in
`libs/data/terms_fence.SOURCE_POLICY["tor_metrics"]`, and this organ fetches nothing unless that
row reads `confirmed` (fail closed). Every request goes through `libs.data.polite_fetch.get`:
honest DESK_UA, robots.txt decides, 401/403/429/WAF is a person-held hard stop.

POINT IN TIME. The publication lag is MEASURED, never assumed: each time a new latest date first
appears in a fetch, `first_seen - (date + 1 day)` is one lag observation (an upper bound, accurate
to the leg's hourly clock). The stamp lag is the p90 of those observations (late-biased: late only
costs edge, early invents it); until one exists the DECLARED_LAG_H seed is used and labelled so.
Each row is stamped

    published_time = date end + lag
    available_time = max(first_seen_at, published_time)

so a row first read in a history backfill is available only from the fetch that read it. The
history therefore collapses onto the first fetch and is labelled `pit_quality: backfill`; the
conditioner needs MIN_LIVE_POINTS live points before a cell can be judged, and until then each
cell is OWED with that reason. A later revised value is recorded as a revision beside the first
value seen, never back-dated.

FEATURES per (kind, country), each using only rows before it (strict prefix):
  users_z     z of log(users) against the trailing Z_WINDOW_D days (min Z_MIN_N)
  censor_flag relay only: -1 users < lower, +1 users > upper, 0 inside; None when the row carries
              no bounds (bridge rows, small countries) -- UNMEASURED, never 0
  flag_28d    trailing 28-day count of censor events (relay): the slow censorship state
  zspike_28d  trailing 28-day count of |users_z| >= 3 (both kinds)

WHERE IT GOES (the doors that already exist, no second lane):
  * lake series `data/lake/series/tor_metrics_<kind>_<cc>.csv` in the PIT envelope that
    `mt5desk.family_exogenous_conditioner` reads by `available_time`;
  * `data/axes/alt_tor_metrics.json` in the axis-door shape (`series[<name>].points`);
  * cells: `libs.moat.registry.record_discovery` + `enqueue_candidate` (family
    exogenous_conditioner, D1), the same door `pack_cells` uses -- the gauntlet judges them;
  * `reports/TOR_METRICS.json`, the leg's artifact, which also carries the onion allowlist
    section (`research/onion_mirrors.py`, OFF until the auditor rules).

COUNTRY -> INSTRUMENT. A country's currency is looked up in the broker's registry
(`data/universe/universe.json`): USD<ccy> (+1: stress weakens the currency), <ccy>USD (-1), else
EUR<ccy> (+1). Countries with no tradable currency map to their nearest instrument in
NEAREST (IR -> gold and Brent, VE -> WTI, BY/KZ -> USDRUB ...). A country that maps to nothing is
RECORDED in the report with its reason, never dropped. Pseudo-codes ('', ??, a1, a2, ap, eu) are
aggregates and map to nothing by definition.

LIVE YIELD IS UNMEASURED UNTIL THE BOX RUNS THIS: the build container's proxy refuses the host.

    python desks/mt5/research/tor_metrics.py --once [--budget-s 240] [--dry-run]
    python desks/mt5/research/tor_metrics.py --once --fixtures tests/fixtures/tor_metrics --dry-run
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import sys
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE = "tor_metrics"
#: The leg's artifact (also `Paths.report` for the desk root).
REPORT = DESK / "reports" / "TOR_METRICS.json"
POLICY_KEY = "tor_metrics"
UNMEASURED = "UNMEASURED"
BASE_URL = "https://metrics.torproject.org/userstats-{kind}-country.csv"
KINDS: tuple[str, ...] = ("relay", "bridge")
#: Days of history read on a first pass, and the overlap re-read on every later pass (so a
#: revised recent value is seen as a revision).
BACKFILL_DAYS = 400
OVERLAP_DAYS = 14
MAX_BYTES = 24_000_000
#: The lag used before any is measured: 72 hours (the 2026-10-29 reading of the site showed
#: 2026-10-26 as the latest date in the early afternoon UTC, i.e. ~2.6 days after the date ended).
DECLARED_LAG_H = 72.0
LAG_QUANTILE = 0.9
LAG_KEEP = 60
Z_WINDOW_D = 90
Z_MIN_N = 28
STATE_WINDOW_D = 28
ZSPIKE = 3.0
#: Live points a lake series needs before its cells are minted -- the conditioner's own floor
#: (`family_exogenous_conditioner.MIN_OBSERVATIONS`).
MIN_LIVE_POINTS = 30
CHART = "D1"
FAMILY = "exogenous_conditioner"
SIGNALS: dict[str, tuple[str, ...]] = {"relay": ("users_z", "flag_28d"),
                                       "bridge": ("users_z", "zspike_28d")}
PSEUDO_CODES = frozenset({"", "??", "a1", "a2", "ap", "eu", "o1", "zz"})


@dataclass(frozen=True)
class Paths:
    desk: Path

    @property
    def state(self) -> Path:
        return self.desk / "data" / "tor_metrics" / "state.json"

    @property
    def series(self) -> Path:
        return self.desk / "data" / "lake" / "series"

    @property
    def axis(self) -> Path:
        return self.desk / "data" / "axes" / "alt_tor_metrics.json"

    @property
    def report(self) -> Path:
        return self.desk / "reports" / "TOR_METRICS.json"

    @property
    def universe(self) -> Path:
        return self.desk / "data" / "universe" / "universe.json"


DEFAULT_PATHS = Paths(DESK)

# ============================================================================ country map
#: ISO 3166 alpha-2 -> ISO 4217. Euro members are listed once as a set below.
EURO = frozenset({"at", "be", "cy", "de", "ee", "es", "fi", "fr", "gr", "hr", "ie", "it", "lt",
                  "lu", "lv", "mt", "nl", "pt", "si", "sk"})
CURRENCY: dict[str, str] = {
    "us": "USD", "gb": "GBP", "jp": "JPY", "ch": "CHF", "ca": "CAD", "au": "AUD", "nz": "NZD",
    "cn": "CNH", "hk": "HKD", "sg": "SGD", "ru": "RUB", "tr": "TRY", "br": "BRL", "mx": "MXN",
    "za": "ZAR", "in": "INR", "id": "IDR", "kr": "KRW", "th": "THB", "il": "ILS", "pl": "PLN",
    "hu": "HUF", "cz": "CZK", "dk": "DKK", "no": "NOK", "se": "SEK", "my": "MYR", "ph": "PHP",
    "tw": "TWD", "ar": "ARS", "cl": "CLP", "co": "COP", "pe": "PEN", "ro": "RON", "bg": "BGN",
    "ua": "UAH", "eg": "EGP", "ng": "NGN", "ke": "KES", "pk": "PKR", "bd": "BDT", "vn": "VND",
    "sa": "SAR", "ae": "AED", "qa": "QAR", "kw": "KWD", "ir": "IRR", "iq": "IQD", "ve": "VES",
    "by": "BYN", "kz": "KZT", "uz": "UZS", "az": "AZN", "ge": "GEL", "am": "AMD", "tm": "TMT",
    "ly": "LYD", "dz": "DZD", "ma": "MAD", "tn": "TND", "et": "ETB", "mm": "MMK", "kh": "KHR",
    "lk": "LKR", "np": "NPR", "cu": "CUP", "ni": "NIO", "rs": "RSD", "is": "ISK", "om": "OMR",
    "sy": "SYP", "lb": "LBP", "jo": "JOD", "af": "AFN", "tj": "TJS", "kg": "KGS",
    **dict.fromkeys(EURO, "EUR")}
#: Countries whose own currency the broker does not quote: the nearest instrument the desk
#: trades, and the sign stress is presumed to push it (a PRIOR; the gauntlet measures the sign).
NEAREST: dict[str, dict[str, int]] = {
    "ir": {"XAUUSD": 1, "XBRUSD": 1}, "iq": {"XBRUSD": 1}, "ly": {"XBRUSD": 1},
    "sa": {"XBRUSD": 1}, "ae": {"XBRUSD": 1}, "qa": {"XNGUSD": 1}, "kw": {"XBRUSD": 1},
    "om": {"XBRUSD": 1}, "ve": {"XTIUSD": 1}, "ng": {"XBRUSD": 1}, "dz": {"XNGUSD": 1},
    "by": {"USDRUB": 1}, "kz": {"USDRUB": 1}, "uz": {"USDRUB": 1}, "tm": {"USDRUB": 1},
    "az": {"USDRUB": 1}, "ge": {"USDRUB": 1}, "am": {"USDRUB": 1}, "tj": {"USDRUB": 1},
    "kg": {"USDRUB": 1}, "ua": {"EURUSD": -1, "XAUUSD": 1}, "eg": {"XAUUSD": 1},
    "sy": {"XAUUSD": 1}, "lb": {"XAUUSD": 1}, "jo": {"XAUUSD": 1}, "af": {"XAUUSD": 1},
    "pk": {"USDINR": 1}, "bd": {"USDINR": 1}, "lk": {"USDINR": 1}, "np": {"USDINR": 1},
    "mm": {"USDTHB": 1}, "kh": {"USDTHB": 1}, "vn": {"USDCNH": 1}, "tw": {"USDCNH": 1},
    "us": {"USDX": -1}, "cn": {"CHINAH": -1, "HK50": -1}, "hk": {"HK50": -1},
}


def universe_symbols(path: Path) -> frozenset[str]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return frozenset()
    return frozenset(k for k, v in doc.items() if isinstance(v, dict)) if isinstance(
        doc, dict) else frozenset()


def instruments_for(cc: str, universe: frozenset[str]) -> tuple[dict[str, int], str]:
    """(symbol -> prior sign, why). Empty with a reason when nothing maps: recorded, not dropped."""
    cc = (cc or "").lower()
    if cc in PSEUDO_CODES:
        return {}, "aggregate or pseudo-code (all countries / unknown / anonymous proxy / region)"
    out: dict[str, int] = {}
    ccy = CURRENCY.get(cc, "")
    if ccy and ccy not in ("USD", "EUR"):
        for sym, sign in ((f"USD{ccy}", 1), (f"{ccy}USD", -1), (f"EUR{ccy}", 1)):
            if sym in universe:
                out[sym] = sign
                break
    elif ccy == "EUR" and "EURUSD" in universe:
        out["EURUSD"] = -1
    for sym, sign in NEAREST.get(cc, {}).items():
        if sym in universe:
            out.setdefault(sym, sign)
    if out:
        return out, ""
    if not universe:
        return {}, "universe registry unreadable on this host: UNMEASURED"
    return {}, (f"no instrument in the registry for currency {ccy}" if ccy
                else "country not in the currency map")


# ============================================================================ parsing
def _num(v: Any) -> float | None:
    try:
        x = float(str(v or "").strip())
    except ValueError:
        return None
    return x if math.isfinite(x) else None


def parse_csv(body: str, kind: str) -> list[dict[str, Any]]:
    """Rows of a userstats CSV; comment lines (#) skipped; bounds None when absent."""
    lines = [ln for ln in body.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if not lines:
        return []
    out: list[dict[str, Any]] = []
    for r in csv.DictReader(io.StringIO("\n".join(lines))):
        try:
            d = date.fromisoformat(str(r.get("date") or "").strip())
            users = float(str(r.get("users") or "").strip())
        except ValueError:
            continue
        if not math.isfinite(users):
            continue

        out.append({"kind": kind, "date": d, "cc": str(r.get("country") or "").strip().lower(),
                    "users": users, "lower": _num(r.get("lower")), "upper": _num(r.get("upper")),
                    "frac": _num(r.get("frac"))})
    return out


# ============================================================================ state
def _read_json(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _atomic(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, default=str, ensure_ascii=False), "utf-8")
    os.replace(tmp, p)


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).isoformat(timespec="seconds")


def _t(s: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def record_lag(state: dict[str, Any], kind: str, rows: list[dict[str, Any]],
               fetched_at: datetime) -> dict[str, Any] | None:
    """One lag observation when this fetch shows a NEW latest date for `kind`."""
    if not rows:
        return None
    latest = max(r["date"] for r in rows)
    lags = state.setdefault("lag", {}).setdefault(kind, {"latest": None, "obs": []})
    prev = lags.get("latest")
    if prev and latest.isoformat() <= str(prev):
        return None
    end = datetime(latest.year, latest.month, latest.day, tzinfo=UTC) + timedelta(days=1)
    hours = round((fetched_at - end).total_seconds() / 3600.0, 2)
    obs = {"date": latest.isoformat(), "first_seen_at": _iso(fetched_at), "lag_h": hours,
           "first_pass": prev is None}
    lags["latest"] = latest.isoformat()
    lags["obs"] = [*list(lags.get("obs") or []), obs][-LAG_KEEP:]
    return obs


def stamp_lag(state: Mapping[str, Any], kind: str) -> tuple[float, str]:
    """(hours, basis): the p90 of measured lags, else the declared seed. A first-pass
    observation counts (it is an upper bound: late-biased, never early)."""
    obs = [float(o["lag_h"]) for o in ((state.get("lag") or {}).get(kind) or {}).get("obs") or []
           if isinstance(o, dict) and isinstance(o.get("lag_h"), (int, float))
           and float(o["lag_h"]) >= 0]
    if not obs:
        return DECLARED_LAG_H, "declared"
    obs.sort()
    i = min(len(obs) - 1, max(0, math.ceil(LAG_QUANTILE * len(obs)) - 1))
    return float(obs[i]), f"measured_p90_n{len(obs)}"


def merge(state: dict[str, Any], rows: Iterable[dict[str, Any]], fetched_at: datetime
          ) -> dict[str, int]:
    """Append-only vintages: a key's FIRST value and first-seen instant never change."""
    store = state.setdefault("rows", {})
    added = revised = 0
    stamp = _iso(fetched_at)
    for r in rows:
        k = f"{r['kind']}|{r['cc']}|{r['date'].isoformat()}"
        cur = store.get(k)
        if cur is None:
            store[k] = {"u": r["users"], "lo": r["lower"], "hi": r["upper"], "fr": r["frac"],
                        "seen": stamp, "u_last": r["users"], "rev": None, "n_rev": 0}
            added += 1
        elif not math.isclose(float(cur.get("u_last") or 0.0), r["users"], rel_tol=1e-9):
            cur["u_last"] = r["users"]
            cur["rev"] = stamp
            cur["n_rev"] = int(cur.get("n_rev") or 0) + 1
            revised += 1
    return {"added": added, "revised": revised}


# ============================================================================ features
def _mean_sd(xs: list[float]) -> tuple[float | None, float | None]:
    if len(xs) < 2:
        return None, None
    m = sum(xs) / len(xs)
    v = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return m, (math.sqrt(v) if v > 0 else None)


def censor_flag(users: float, lower: float | None, upper: float | None) -> int | None:
    if lower is None or upper is None:
        return None
    if users < lower:
        return -1
    if users > upper:
        return 1
    return 0


def build_points(state: Mapping[str, Any], lag_h: Mapping[str, float]
                 ) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Per (kind, cc): PIT points with users_z / censor_flag / flag_28d / zspike_28d.

    Ordered by date (the order the data could be known in: published_time rises with date);
    every statistic at date d reads only rows with an earlier date."""
    by: dict[tuple[str, str], list[tuple[date, dict[str, Any]]]] = {}
    for k, v in (state.get("rows") or {}).items():
        try:
            kind, cc, ds = str(k).split("|")
            by.setdefault((kind, cc), []).append((date.fromisoformat(ds), v))
        except ValueError:
            continue
    out: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for (kind, cc), items in by.items():
        items.sort(key=lambda t: t[0])
        lag = timedelta(hours=float(lag_h.get(kind, DECLARED_LAG_H)))
        logs: list[tuple[date, float]] = []
        flags: list[tuple[date, int]] = []
        spikes: list[tuple[date, int]] = []
        pts: list[dict[str, Any]] = []
        for d, v in items:
            users = float(v["u"])
            lx = math.log(users) if users > 0 else None
            prior = [x for (dd, x) in logs if (d - dd).days <= Z_WINDOW_D]
            z = None
            if lx is not None and len(prior) >= Z_MIN_N:
                m, sd = _mean_sd(prior)
                z = (lx - m) / sd if m is not None and sd else None
            if lx is not None:
                logs.append((d, lx))
            flag = censor_flag(users, v.get("lo"), v.get("hi"))
            if flag is not None:
                flags.append((d, flag))
            if z is not None:
                spikes.append((d, int(abs(z) >= ZSPIKE)))
            win_f = [abs(f) for (dd, f) in flags if 0 <= (d - dd).days < STATE_WINDOW_D]
            win_s = [s for (dd, s) in spikes if 0 <= (d - dd).days < STATE_WINDOW_D]
            end = datetime(d.year, d.month, d.day, tzinfo=UTC) + timedelta(days=1)
            published = end + lag
            seen = _t(v.get("seen")) or published
            available = max(seen, published)
            pts.append({
                "d": d.isoformat(), "event_time": d.isoformat(),
                "published_time": _iso(published), "available_time": _iso(available),
                "retrieval_time": v.get("seen"), "revision_time": v.get("rev"),
                "pit_quality": "live" if seen <= published + timedelta(days=2) else "backfill",
                "users": users, "lower": v.get("lo"), "upper": v.get("hi"), "frac": v.get("fr"),
                "users_z": None if z is None else round(z, 4),
                "censor_flag": flag,
                "flag_28d": sum(win_f) if kind == "relay" and win_f else None,
                "zspike_28d": sum(win_s) if win_s else None})
        out[(kind, cc)] = pts
    return out


# ============================================================================ publishing
def lake_id(kind: str, cc: str) -> str:
    return f"tor_metrics_{kind}_{cc}"


LAKE_COLUMNS = ("event_time", "published_time", "available_time", "retrieval_time",
                "revision_time", "source_id", "vintage_id", "users", "users_z", "censor_flag",
                "flag_28d", "zspike_28d", "frac", "pit_quality")


def write_lake(paths: Paths, points: Mapping[tuple[str, str], list[dict[str, Any]]],
               mapped: Mapping[str, Any]) -> list[str]:
    """One CSV per MAPPED (kind, country), in the envelope `exogenous_conditioner` reads."""
    paths.series.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for (kind, cc), pts in sorted(points.items()):
        if cc not in mapped or not pts:
            continue
        target = paths.series / f"{lake_id(kind, cc)}.csv"
        tmp = target.with_suffix(f".tmp{os.getpid()}")
        with tmp.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(LAKE_COLUMNS)
            for p in pts:
                row = {**p, "source_id": SOURCE,
                       "vintage_id": f"{SOURCE}:{p.get('retrieval_time') or ''}"}
                w.writerow(["" if row.get(c) is None else row.get(c) for c in LAKE_COLUMNS])
        os.replace(tmp, target)
        written.append(target.name)
    return written


def axis_doc(points: Mapping[tuple[str, str], list[dict[str, Any]]], now: datetime
             ) -> dict[str, Any]:
    series: dict[str, Any] = {}
    for (kind, cc), pts in sorted(points.items()):
        for col in ("users", "users_z", "censor_flag", "flag_28d", "zspike_28d"):
            keep = [{"d": p["d"], "v": p[col], "available_time": p["available_time"],
                     "published_time": p["published_time"], "event_time": p["event_time"],
                     "first_seen_at": p["retrieval_time"], "revision_time": p["revision_time"],
                     "pit_quality": p["pit_quality"]} for p in pts if p.get(col) is not None]
            if keep:
                series[f"{kind}_{cc or 'all'}.{col}"] = {
                    "what": f"Tor Metrics {kind} users, {cc or 'all countries'}: {col}",
                    "n": len(keep), "first": keep[0]["d"], "last": keep[-1]["d"],
                    "points": keep}
    return {"axis": "alt_proxy", "id": "alt_tor_metrics", "source": BASE_URL.split("{")[0],
            "credit": "Tor Project, metrics.torproject.org (CC0)",
            "at": _iso(now), "cadence": "daily", "n_series": len(series),
            "pit_fields": ["event_time", "published_time", "available_time", "first_seen_at",
                           "revision_time"],
            "shape": "series[<kind>_<cc>.<column>].points, joined on available_time",
            "series": series}


def latest_events(points: Mapping[tuple[str, str], list[dict[str, Any]]],
                  mapped: Mapping[str, Any], days: int = 7) -> list[dict[str, Any]]:
    """Censorship events (relay flag != 0) and |z| >= ZSPIKE in the last `days` of each series."""
    out: list[dict[str, Any]] = []
    for (kind, cc), pts in sorted(points.items()):
        if not pts or cc in PSEUDO_CODES:
            continue
        last = date.fromisoformat(pts[-1]["d"])
        for p in pts:
            if (last - date.fromisoformat(p["d"])).days >= days:
                continue
            z = p.get("users_z")
            if p.get("censor_flag") or (z is not None and abs(z) >= ZSPIKE):
                out.append({"kind": kind, "country": cc, "date": p["d"],
                            "users": p["users"], "lower": p["lower"], "upper": p["upper"],
                            "censor_flag": p["censor_flag"], "users_z": z,
                            "instruments": sorted((mapped.get(cc) or {}).keys())})
    return out


def emit_cells(points: Mapping[tuple[str, str], list[dict[str, Any]]],
               mapped: Mapping[str, dict[str, int]], *, dry_run: bool) -> dict[str, Any]:
    """Cells through the one door (`libs.moat.registry`), for series with enough LIVE points.

    A series below MIN_LIVE_POINTS is OWED, with its count: its history is backfill stamped at
    the first fetch, which the conditioner collapses to one point."""
    try:
        from research import universe_policy
        lane_ok: Callable[[str], bool] = lambda s: bool(  # noqa: E731
            universe_policy.may_hypothesise(s, FAMILY))
    except Exception:
        lane_ok = lambda s: False  # noqa: E731 -- an unreadable lane order mints nothing
    ready: list[tuple[str, str, str, str, int]] = []
    owed: dict[str, int] = {}
    lane_refused: list[str] = []
    for (kind, cc), pts in sorted(points.items()):
        inst = mapped.get(cc) or {}
        if not inst:
            continue
        live = sum(1 for p in pts if p["pit_quality"] == "live")
        if live < MIN_LIVE_POINTS:
            owed[lake_id(kind, cc)] = live
            continue
        for sym, sign in sorted(inst.items()):
            if not lane_ok(sym):
                lane_refused.append(f"{lake_id(kind, cc)}->{sym}")
                continue
            for sig in SIGNALS[kind]:
                ready.append((kind, cc, sym, sig, sign))
    res: dict[str, Any] = {"cells_ready": len(ready), "enqueued": 0, "created": 0,
                           "owed_live_points": dict(sorted(owed.items())),
                           "owed_why": (f"fewer than {MIN_LIVE_POINTS} live points: history "
                                        "rows are available only from the fetch that first read "
                                        "them, so they collapse to one point"),
                           "lane_refused": lane_refused[:50], "errors": []}
    if dry_run or not ready:
        return res
    try:
        from libs.moat.registry import enqueue_candidate, record_discovery
    except Exception as exc:
        res["errors"].append(f"registry import: {type(exc).__name__}: {str(exc)[:80]}")
        return res
    mech = ("political stress read off Tor usage: a censorship event (users outside the Tor "
            "Project detector's expected range) or a surge in Tor/bridge use marks a state "
            "blocking or a population routing around a block; the country's currency or "
            "nearest instrument reprices that stress")
    try:
        did, _ = record_discovery(source_id=SOURCE, source_type="data_pack", mechanism=mech,
                                  origin=SOURCE, generator=SOURCE,
                                  assets=sorted({r[2] for r in ready}), exact_rule_if_known="",
                                  horizons=[CHART], note="Tor Metrics CC0 per-country series")
    except Exception as exc:
        res["errors"].append(f"record_discovery: {type(exc).__name__}: {str(exc)[:80]}")
        return res
    for kind, cc, sym, sig, sign in ready:
        src = lake_id(kind, cc)
        try:
            _cid, new = enqueue_candidate(
                family=FAMILY, symbol=sym,
                params={"source": src, "signal": sig, "transform": "level_z",
                        "side_when_high": sign},
                origin=SOURCE, mechanism=mech, chart=CHART, horizon=CHART, source_id=SOURCE,
                discovery_id=did or None, generator=SOURCE, department="information",
                asset_class="", transformation="tor_metrics_state",
                required_data=[f"desks/mt5/data/lake/series/{src}.csv"], pit_status="STAMPED",
                causal_rationale=mech,
                falsifier=(f"the level_z of {src}.{sig} has no measurable relation to {sym} at "
                           f"{CHART} out of sample"))
            res["enqueued"] += 1
            res["created"] += int(bool(new))
        except Exception as exc:
            res["errors"].append(f"{src}/{sig}/{sym}: {type(exc).__name__}: {str(exc)[:60]}")
    res["errors"] = res["errors"][:10]
    return res


# ============================================================================ fetching
def terms_ok() -> tuple[bool, str]:
    try:
        from libs.data import terms_fence as tf
        v = tf.terms_verdict(POLICY_KEY)
    except Exception as exc:
        return False, f"terms register unreadable: {type(exc).__name__}"
    return v == "confirmed", v


def fetch_kind(kind: str, start: date, end: date, *, deadline: float | None,
               opener: Any = None, access: Any = None) -> tuple[str, dict[str, Any]]:
    from libs.data import polite_fetch as pf
    url = f"{BASE_URL.format(kind=kind)}?start={start.isoformat()}&end={end.isoformat()}"
    r = pf.get(url, timeout=60.0, retries=2, deadline=deadline, max_bytes=MAX_BYTES,
               leg=SOURCE, opener=opener, access=access, live_input=True)
    meta = {"url": url, "http_status": r.status, "verdict": r.verdict or "",
            "error": r.error[:200], "bytes": len(r.body or b"")}
    return (r.text if r.ok and not r.verdict else ""), meta


def _load_fixture(fixtures: Path, kind: str) -> str | None:
    p = fixtures / f"userstats-{kind}-country.csv"
    return p.read_text("utf-8") if p.exists() else None


# ============================================================================ the pass
def run(paths: Paths = DEFAULT_PATHS, *, budget_s: float = 240.0, dry_run: bool = False,
        fixtures: Path | None = None, now: datetime | None = None,
        fetcher: Callable[..., tuple[str, dict[str, Any]]] | None = None,
        onion: bool = True) -> dict[str, Any]:
    t0 = time.monotonic()
    now = now or datetime.now(UTC)
    deadline = t0 + budget_s * 0.7
    state = _read_json(paths.state, {})
    if not isinstance(state, dict):
        state = {}
    ok, verdict = terms_ok()
    fetches: dict[str, Any] = {}
    merged: dict[str, Any] = {}
    lag_obs: dict[str, Any] = {}
    for kind in KINDS:
        if fixtures is not None:
            body = _load_fixture(fixtures, kind)
            meta: dict[str, Any] = {"fixture": str(fixtures), "found": body is not None}
        elif not ok:
            body, meta = None, {"status": f"{UNMEASURED}:TERMS_{verdict.upper()}"}
        else:
            latest = ((state.get("lag") or {}).get(kind) or {}).get("latest")
            start = (date.fromisoformat(latest) - timedelta(days=OVERLAP_DAYS) if latest
                     else now.date() - timedelta(days=BACKFILL_DAYS))
            body, meta = (fetcher or fetch_kind)(kind, start, now.date(), deadline=deadline)
        rows = parse_csv(body or "", kind)
        meta["rows"] = len(rows)
        if not rows and not meta.get("status"):
            why = meta.get("verdict") or meta.get("error") or "NO_ROWS"
            meta["status"] = f"{UNMEASURED}:{str(why)[:120]}"
        elif rows:
            meta["status"] = "MEASURED"
        fetches[kind] = meta
        if rows:
            lag_obs[kind] = record_lag(state, kind, rows, now)
            merged[kind] = merge(state, rows, now)
    lags = {k: stamp_lag(state, k) for k in KINDS}
    points = build_points(state, {k: v[0] for k, v in lags.items()})
    universe = universe_symbols(paths.universe)
    countries = sorted({cc for (_k, cc) in points})
    mapped: dict[str, dict[str, int]] = {}
    unmapped: dict[str, str] = {}
    for cc in countries:
        inst, why = instruments_for(cc, universe)
        if inst:
            mapped[cc] = inst
        else:
            unmapped[cc or "(all)"] = why
    events = latest_events(points, mapped)
    lake: list[str] = []
    if not dry_run and points:
        lake = write_lake(paths, points, mapped)
        _atomic(paths.axis, axis_doc(points, now))
        _atomic(paths.state, state)
    cells = emit_cells(points, mapped, dry_run=dry_run)
    onion_section: dict[str, Any] = {}
    if onion:
        try:
            from research import onion_mirrors
            onion_section = onion_mirrors.run(dry_run=dry_run)
        except Exception as exc:
            onion_section = {"status": f"{UNMEASURED}:ERROR",
                             "error": f"{type(exc).__name__}: {str(exc)[:160]}"}
    any_rows = any(int(m.get("rows") or 0) for m in fetches.values())
    report = {
        "generated_at": _iso(now), "source": SOURCE, "terms_verdict": verdict,
        "status": "MEASURED" if any_rows else f"{UNMEASURED}:NO_DATA_THIS_PASS",
        "dry_run": dry_run, "fixtures": str(fixtures) if fixtures else None,
        "fetches": fetches, "merged": merged,
        "lag": {k: {"hours": v[0], "basis": v[1], "new_observation": lag_obs.get(k)}
                for k, v in lags.items()},
        "n_series": len(points), "n_countries": len(countries),
        "mapped": {cc: mapped[cc] for cc in sorted(mapped)},
        "unmapped": dict(sorted(unmapped.items())),
        "latest_events": events,
        "n_censorship_events_7d": sum(1 for e in events if e.get("censor_flag")),
        "lake_written": len(lake), "cells": cells,
        "onion_mirrors": onion_section,
        "live_yield": ("UNMEASURED until the trading box runs this leg; the build container's "
                       "proxy refuses metrics.torproject.org"),
        "elapsed_s": round(time.monotonic() - t0, 2)}
    _atomic(paths.report, report)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--dry-run", action="store_true",
                    help="fetch and measure; write only the report (no state, lake or cells)")
    ap.add_argument("--fixtures", type=Path, default=None)
    ap.add_argument("--no-onion", action="store_true")
    a = ap.parse_args(argv)
    rep = run(budget_s=a.budget_s, dry_run=a.dry_run, fixtures=a.fixtures, onion=not a.no_onion)
    print(json.dumps({k: rep[k] for k in ("status", "terms_verdict", "n_series",
                                          "n_censorship_events_7d", "lake_written")},
                     default=str))
    print(f"report: {DEFAULT_PATHS.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
