"""FRED MACRO AXIS FETCH: retried, classified, point-in-time stamped. The `fred` axis's ingester.

WHAT WAS WRONG (measured 2026-09-30, the D18 fence after #168).

  1. `data/axes/fred.json` (committed from the box 2026-09-12) holds 0 series and 7 failures:
     `TimeoutError` and `ConnectionResetError [WinError 10054]` -- the box's IP was reset by the
     publisher's edge. The cloud container fails too, differently: its egress proxy refuses the
     CONNECT (`Tunnel connection failed: 403`). Neither answer came FROM FRED, and neither says
     anything about the dataset -- yet the fence counted `macro:fred` and `registry:fred_macro`
     UNFED, as if the desk had the data and ignored it. Each failure is now CLASSIFIED:
         FETCH_FAILED_ENV   no HTTP answer from the publisher (proxy refusal, reset, timeout,
                            DNS): the environment failed, not the dataset. The fence reads the
                            dataset UNMEASURED with this reason until a host fetches it.
         FETCH_FAILED_HTTP  the publisher answered with an error status.
     and one pass tries each series `ATTEMPTS` times with exponential backoff before giving up.
  2. One failed pass OVERWROTE the axis record with an empty one (`axis_ingest_all` writes
     whatever the ingester returns). A series that fails now keeps its previous points and says
     so (`carried_from`), because a failed fetch is not evidence the series vanished.
  3. POINT-IN-TIME. `mt5desk.dataset_series.macro_raw` stamped every series-shaped point at its
     date + 1 day. For a daily print published the next business day that is already a little
     early over a weekend, and for a MONTHLY series dated at the period's first day (FRED's
     convention) it is weeks of lookahead. Every point written here carries its own `k`
     (knowable_at), in this order of authority:
         ALFRED first release   `output_type=4` gives each observation's first-release
                                `realtime_start` (needs a FRED API key; never logged);
         the release rule       daily: end of the next business day; weekly: +10 days;
                                monthly: period END + the series' release lag
                                (`RELEASE_LAG_DAYS`, conservative); quarterly: period end + 95d.
     Being late costs a little edge; being early invents it.

ROUTES, first success wins, each point's route recorded:
    ALFRED API (key)      https://api.stlouisfed.org/fred/series/observations, output_type=4
    fredgraph CSV         https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SID>  (keyless)
    DBnomics mirror       scripts/data_alternates.DBNOMICS_MIRROR (same series, other host;
                          only ids mapped and probed there -- never a guessed id)
Every request sends this organ's own identifying User-Agent; none is ever changed to pass a wall.

    python desks/mt5/research/fred_fetch.py [--apply]
"""
from __future__ import annotations

import csv
import io
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

AXES = DESK / "data" / "axes"
UA = "quant-desk-axis-ingest/1.0 (research)"
TIMEOUT = 40
ATTEMPTS = 4
BACKOFF_S = 2.0
FREDGRAPH = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
API = "https://api.stlouisfed.org/fred/series/observations"

OK = "OK"
PARTIAL = "PARTIAL"
ENV = "FETCH_FAILED_ENV"
HTTP = "FETCH_FAILED_HTTP"

#: The axis's series (axis_ingest.FRED_SERIES is the list of record; this mirrors it when that
#: module is absent) and each one's publication frequency.
FRED_SERIES: dict[str, str] = {
    "DGS10": "US 10y constant-maturity yield",
    "DGS2": "US 2y constant-maturity yield",
    "T10Y2Y": "10y-2y term spread",
    "DTWEXBGS": "broad trade-weighted USD index",
    "T10YIE": "10y breakeven inflation",
    "BAMLH0A0HYM2": "US high-yield OAS -- credit appetite",
    "VIXCLS": "VIX",
}
#: Frequency by series id. DTWEXBGS is a daily series RELEASED WEEKLY (H.10, Mondays).
FREQUENCY: dict[str, str] = {"DTWEXBGS": "W"}
#: Days after a monthly period's END before its first print is public (conservative).
RELEASE_LAG_DAYS: dict[str, int] = {
    "PAYEMS": 10, "UNRATE": 10, "CPIAUCSL": 17, "CPILFESL": 17, "PCEPI": 35, "PCEPILFE": 35,
    "INDPRO": 20, "RSAFS": 20, "HOUST": 22, "DGORDER": 30, "BUSINV": 50, "M2SL": 30,
}
DEFAULT_MONTHLY_LAG_DAYS = 45
QUARTERLY_LAG_DAYS = 95


# ------------------------------------------------------------------ classification
def classify(exc: BaseException | str) -> str:
    """FETCH_FAILED_HTTP when the publisher answered with an error status; FETCH_FAILED_ENV when
    no answer came from it at all (proxy CONNECT refusal, reset, timeout, DNS)."""
    if isinstance(exc, urllib.error.HTTPError):
        return HTTP
    text = exc if isinstance(exc, str) else f"{type(exc).__name__}: {exc}"
    if text.startswith("HTTPError") or "HTTP Error" in text:
        return HTTP
    return ENV


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code == 429 or exc.code >= 500
    return isinstance(exc, (urllib.error.URLError, TimeoutError, socket.timeout,
                            ConnectionError, OSError))


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:  # noqa: S310 - https only
        return r.read()


def fetch_with_retry(url: str, *, get: Callable[[str], bytes] | None = None,
                     attempts: int = ATTEMPTS, backoff_s: float = BACKOFF_S,
                     sleep: Callable[[float], None] = time.sleep
                     ) -> tuple[bytes | None, dict[str, Any]]:
    """(body, attempt log). Exponential backoff on an environment failure, a 429 or a 5xx; an
    HTTP 4xx other than 429 is the publisher's answer and is not retried."""
    get = get or _get
    log: dict[str, Any] = {"attempts": 0, "errors": []}
    for i in range(max(1, attempts)):
        log["attempts"] = i + 1
        try:
            return get(url), log
        except Exception as exc:
            log["errors"].append(f"{type(exc).__name__}: {str(exc)[:80]}")
            log["status"] = classify(exc)
            if not _retryable(exc) or i == attempts - 1:
                break
            sleep(backoff_s * (2 ** i))
    return None, log


# ------------------------------------------------------------------ point-in-time
def frequency_of(sid: str, dates: list[str]) -> str:
    """D / W / M / Q: the declared frequency, else inferred from the dates' median spacing."""
    if sid in FREQUENCY:
        return FREQUENCY[sid]
    ds = sorted(datetime.fromisoformat(d[:10]) for d in dates[-60:] if d)
    gaps = sorted((b - a).days for a, b in zip(ds, ds[1:], strict=False))
    if not gaps:
        return "D"
    g = gaps[len(gaps) // 2]
    return "D" if g <= 4 else "W" if g <= 10 else "M" if g <= 40 else "Q"


def _next_bday(d: datetime) -> datetime:
    d = d + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def knowable_at(sid: str, date: str, freq: str, realtime_start: str | None = None) -> str:
    """When the desk could first have read `sid`'s observation dated `date` (ISO, UTC midnight).

    ALFRED's first-release `realtime_start` wins (known from the start of that day's END, i.e.
    the next midnight, because the release time within the day is not given). Otherwise the
    release rule for its frequency. FRED dates a monthly or quarterly observation at the
    period's FIRST day, so the period end is computed before the lag is added."""
    if realtime_start:
        t = datetime.fromisoformat(realtime_start[:10]) + timedelta(days=1)
        return t.strftime("%Y-%m-%dT00:00:00+00:00")
    d = datetime.fromisoformat(date[:10])
    if freq == "D":
        t = _next_bday(d) + timedelta(days=1)            # end of the next business day
    elif freq == "W":
        t = d + timedelta(days=10)
    elif freq == "M":
        nxt = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        t = nxt + timedelta(days=RELEASE_LAG_DAYS.get(sid, DEFAULT_MONTHLY_LAG_DAYS))
    else:
        q_end_month = ((d.month - 1) // 3 + 1) * 3
        nxt = (d.replace(month=q_end_month, day=28) + timedelta(days=4)).replace(day=1)
        t = nxt + timedelta(days=QUARTERLY_LAG_DAYS)
    return t.strftime("%Y-%m-%dT00:00:00+00:00")


# ------------------------------------------------------------------ routes
def api_key() -> str | None:
    """FRED_API_KEY from the environment or data/secrets/fred_api_key. Never logged."""
    k = os.environ.get("FRED_API_KEY", "").strip()
    if k:
        return k
    for p in (ROOT / "data" / "secrets" / "fred_api_key", ROOT / "secrets" / "fred_api_key",
              DESK / "secrets" / "fred_api_key"):
        try:
            k = p.read_text("utf-8").strip()
        except OSError:
            continue
        if k:
            return k
    return None


def parse_fredgraph(text: str, sid: str) -> list[tuple[str, float, str | None]]:
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return []
    out = []
    for r in rows[1:]:
        if len(r) < 2 or r[1] in ("", "."):
            continue
        try:
            out.append((r[0][:10], float(r[1]), None))
        except ValueError:
            continue
    return out


def parse_alfred_initial(body: bytes) -> list[tuple[str, float, str | None]]:
    doc = json.loads(body.decode("utf-8", "replace"))
    out = []
    for o in doc.get("observations") or []:
        v = o.get("value")
        if v in (None, "", "."):
            continue
        try:
            out.append((str(o["date"])[:10], float(v), str(o.get("realtime_start") or "")[:10]
                        or None))
        except (KeyError, ValueError):
            continue
    return out


def route_alfred(sid: str, key: str, get: Callable[[str], bytes] | None = None,
                 **kw: Any) -> tuple[list[tuple[str, float, str | None]], dict[str, Any]]:
    q = urllib.parse.urlencode({"series_id": sid, "api_key": key, "file_type": "json",
                                "output_type": 4, "realtime_start": "1776-07-04",
                                "realtime_end": "9999-12-31"})
    body, log = fetch_with_retry(f"{API}?{q}", get=get, **kw)
    return (parse_alfred_initial(body) if body else []), log


def route_fredgraph(sid: str, get: Callable[[str], bytes] | None = None,
                    **kw: Any) -> tuple[list[tuple[str, float, str | None]], dict[str, Any]]:
    body, log = fetch_with_retry(FREDGRAPH.format(sid=sid), get=get, **kw)
    return (parse_fredgraph(body.decode("utf-8", "replace"), sid) if body else []), log


def route_dbnomics(sid: str, get: Callable[[str], bytes] | None = None,
                   **kw: Any) -> tuple[list[tuple[str, float, str | None]], dict[str, Any]]:
    try:
        from data_alternates import DBNOMICS_MIRROR  # type: ignore[import-not-found,unused-ignore]
    except Exception:
        return [], {"attempts": 0, "errors": ["data_alternates unavailable"], "status": ENV}
    triple = DBNOMICS_MIRROR.get(sid)
    if triple is None:
        return [], {"attempts": 0, "errors": ["no probed DBnomics mirror for this id"],
                    "status": "NO_ROUTE"}
    prov, ds, code = triple
    body, log = fetch_with_retry(f"https://api.db.nomics.world/v22/series/{prov}/{ds}/{code}"
                                 "?observations=1&format=json", get=get, **kw)
    out: list[tuple[str, float, str | None]] = []
    if body:
        doc = json.loads(body.decode("utf-8", "replace"))
        docs = (doc.get("series") or {}).get("docs") or []
        if docs:
            for per, val in zip(docs[0].get("period") or [], docs[0].get("value") or [],
                                strict=False):
                day = str(per)[:10] + ("-01" if len(str(per)) == 7 else "")
                try:
                    out.append((day, float(val), None))
                except (TypeError, ValueError):
                    continue
    return out, log


def fetch_series(sid: str, *, get: Callable[[str], bytes] | None = None,
                 key: str | None = None, **kw: Any) -> dict[str, Any]:
    """One series through the routes. {"points": [...], "route", "status", "tries": {...}}."""
    tries: dict[str, Any] = {}
    routes: list[tuple[str, Callable[..., Any]]] = []
    if key:
        routes.append(("alfred_initial_release", lambda: route_alfred(sid, key, get, **kw)))
    routes += [("fredgraph_csv", lambda: route_fredgraph(sid, get, **kw)),
               ("dbnomics_mirror", lambda: route_dbnomics(sid, get, **kw))]
    for name, fn in routes:
        pts, log = fn()
        tries[name] = {k: v for k, v in log.items() if k != "errors"} | {
            "errors": log.get("errors", [])[-2:]}
        if pts:
            freq = frequency_of(sid, [p[0] for p in pts])
            return {"route": name, "status": OK, "frequency": freq, "tries": tries,
                    "points": [{"d": d, "v": v, "k": knowable_at(sid, d, freq, rs)}
                               for d, v, rs in sorted(pts)]}
    statuses = [t.get("status") for t in tries.values() if t.get("status")]
    return {"route": None, "status": HTTP if HTTP in statuses else ENV, "tries": tries,
            "points": []}


def ingest_fred(*, get: Callable[[str], bytes] | None = None, previous: dict[str, Any] | None
                = None, series: dict[str, str] | None = None, **kw: Any) -> dict[str, Any]:
    """The `fred` axis record. A series that fails keeps its previous points (`carried_from`)."""
    key = api_key()
    prev_series = (previous or {}).get("series") if isinstance(previous, dict) else None
    out_series: dict[str, Any] = {}
    failed: dict[str, str] = {}
    fetch: dict[str, Any] = {}
    for sid, what in (series or FRED_SERIES).items():
        got = fetch_series(sid, get=get, key=key, **kw)
        fetch[sid] = {"status": got["status"], "route": got["route"], "tries": got["tries"]}
        if got["points"]:
            pts = got["points"]
            out_series[sid] = {"what": what, "n": len(pts), "first": pts[0]["d"],
                               "last": pts[-1]["d"], "frequency": got["frequency"],
                               "route": got["route"], "points": pts}
            continue
        last_err = next((t["errors"][-1] for t in got["tries"].values() if t.get("errors")),
                        got["status"])
        failed[sid] = f"{got['status']}: {last_err}"
        old = (prev_series or {}).get(sid) if isinstance(prev_series, dict) else None
        if isinstance(old, dict) and old.get("points"):
            out_series[sid] = {**old, "carried_from": (previous or {}).get("at"),
                               "carried_why": f"this pass {got['status']}"}
    statuses = {v["status"] for v in fetch.values()}
    fetched = sum(1 for v in fetch.values() if v["status"] == OK)
    status = (OK if fetched == len(fetch) else PARTIAL if fetched else
              HTTP if HTTP in statuses else ENV)
    return {"axis": "macro_state", "id": "fred_series", "source": "fred (alfred/fredgraph/"
            "dbnomics)", "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "host": socket.gethostname(), "fetch_status": status,
            "n_series": len(out_series), "n_fetched": fetched, "n_failed": len(failed),
            "failed": failed, "fetch": fetch,
            "vintage_note": ("each point carries `k`, its knowable_at: ALFRED's first-release "
                             "date when a key is present, else the release rule for its "
                             "frequency (fred_fetch.knowable_at). Daily market series barely "
                             "revise; a monthly series from fredgraph is the CURRENT vintage "
                             "stamped at its first release rule, and says so."),
            "shape": "series[sid].points -- {d, v, k} one dated state variable each",
            "series": out_series}


def write_axis(doc: dict[str, Any], axes: Path | None = None) -> Path:
    """Write fred.json, never replacing a record that holds series with one that holds none."""
    base = axes or AXES
    base.mkdir(parents=True, exist_ok=True)
    p = base / "fred.json"
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1), "utf-8")
    os.replace(tmp, p)
    return p


def previous(axes: Path | None = None) -> dict[str, Any] | None:
    try:
        doc = json.loads(((axes or AXES) / "fred.json").read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    doc = ingest_fred(previous=previous())
    print(f"fred: {doc['fetch_status']} -- {doc['n_fetched']}/{len(FRED_SERIES)} fetched, "
          f"{doc['n_series']} series held")
    for sid, f in doc["fetch"].items():
        print(f"  {sid:<14} {f['status']:<18} {f['route'] or ''}")
    if a.apply:
        print(f"-> {write_axis(doc)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
