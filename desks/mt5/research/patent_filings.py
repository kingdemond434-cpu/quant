"""PATENT FILINGS PER SECTOR -> index and commodity CFDs: weekly counts from the offices' own APIs.

THE MECHANISM. A technology's patent publications are its R&D pipeline made public, eighteen
months after filing and years before revenue. When a sector's share of all publications rises,
capital and engineering have already moved there; the instruments that sector's inputs and
outputs price -- copper and nickel for batteries, platinum for electrolysers, silver for solar,
the Nasdaq for compute, crude for drilling -- are a different asset at the extremes of that share
than at its middle. The bet is on the EXOGENOUS series, and the gauntlet decides whether it pays.

WHAT IS COUNTED. Per completed ISO week and per sector (a fixed set of CPC subclasses), the
number of publications, plus the week's total, from each office route:

    epo_ops    EPO Open Patent Services, CQL `pd within "<mon> <sun>" and (cpc=X or ...)`,
               the count read from `total-result-count`. Free registration (consumer key and
               secret); automated use is what OPS exists for, inside its fair-use quota.
    uspto_odp  USPTO Open Data Portal application search, filtered by CPC and filing date, the
               count read from `count`. Free API key. The query shape is the documented one but
               UNVERIFIED from the build container (no route to api.uspto.gov there); a response
               without an integer `count` is SHAPE_UNRECOGNISED, never a zero.

Neither office offers a keyless count API, and PatentsView's search host stopped resolving
2026-09-15 (`index_discovery.RETIRED`). So each route FAILS CLOSED without its key --
NEEDS_CREDENTIAL with the file it looks for -- and the report says so every pass. Keys live in
`data/secrets/epo_ops.json` ({"key", "secret"}) / `data/secrets/uspto_odp.json` ({"key"}) or the
environment, are sent in a header and nowhere else, and are never printed or written.

POINT IN TIME. A publication's date is fixed when it is published, so a week's count is a fact
from the end of that week; offices index within days. `available_time` is therefore the week's
Sunday + `INDEX_LAG_D` days, and a week retrieved long after (backfill) carries `backfilled` so a
reader can see which rows were read late. The derived columns are trailing-13-week:
`<sector>_share13` (sector / all publications) and `<sector>_yoy13` (log change against the same
13 weeks a year earlier).

THE CLOCK. Hourly leg; each pass spends at most `MAX_REQUESTS` per route, newest missing week
first, so the backfill fills over a day and then the leg asks one week a week. Cells
(`exogenous_conditioner`) are minted once per identity into `data/intelligence/patent_filings/`.

    python desks/mt5/research/patent_filings.py --once [--budget-s 600]
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from itertools import product
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SEAT = "patent_filings"
STATE_DIR = DESK / "data" / "patent_filings"
COUNTS = STATE_DIR / "counts.json"
MINTED = STATE_DIR / "minted.json"
SERIES_DIR = DESK / "data" / "lake" / "series"
REPORT = DESK / "reports" / "PATENT_FILINGS.json"
SECRETS = ROOT / "data" / "secrets"

#: sector -> (CPC subclasses, hypothesis-lane MT5 instruments it bears on, why)
SECTORS: dict[str, tuple[tuple[str, ...], tuple[str, ...], str]] = {
    "compute_semis": (("G06F", "G06N", "H01L", "H10B"), ("NAS100", "JPN225"),
                      "compute and semiconductor R&D is the Nasdaq's and the Nikkei's tech weight"),
    "batteries_ev": (("H01M", "B60L"), ("XCUUSD", "XNIUSD"),
                     "battery and EV traction filings lead copper and nickel demand"),
    "hydrogen": (("C25B", "C01B"), ("XPTUSD", "XPDUSD"),
                 "electrolyser and hydrogen chemistry filings lead PGM catalyst demand"),
    "solar_wind": (("H02S", "F03D"), ("XAGUSD", "XCUUSD"),
                   "photovoltaic paste is silver; wind and grid are copper"),
    "oil_gas": (("E21B", "C10G"), ("XTIUSD", "XBRUSD"),
                "drilling and refining R&D tracks upstream capex"),
    "pharma_bio": (("A61K", "A61P", "C07K", "C12N"), ("US500",),
                   "health-care R&D is the largest R&D weight in the S&P"),
    "autos": (("B60W", "B62D", "F02D"), ("GER40", "JPN225"),
              "vehicle R&D is the DAX's and the Nikkei's industrial core"),
    "telecom": (("H04L", "H04W"), ("NAS100", "HK50"),
                "network R&D is US and Hong Kong platform weight"),
    "metallurgy": (("C22B", "C22C", "B22F"), ("XCUUSD", "XALUSD", "XZNUSD"),
                   "extraction and alloy filings follow base-metal process capex"),
    "agri": (("A01B", "A01C", "A01N"), ("CORN",),
             "seed, tillage and crop-protection R&D follows grain economics"),
}
SIGNALS: tuple[str, ...] = ("share13", "yoy13")
GRID = {"transform": ("level_z",), "threshold": (1.5,), "side_when_high": (1, -1)}
CHART = "H4"
#: Weeks of history the backfill reaches for; enough for a 52-week change and a z window.
BACKFILL_WEEKS = 156
#: Requests per route per pass. Each week costs 1 + len(SECTORS).
MAX_REQUESTS = 66
INDEX_LAG_D = 7
#: A week is first asked for once it ended this many days ago.
MIN_AGE_D = 7
BACKFILL_AFTER_D = 21
MIN_ROWS = 30
ROLL = 13

ROUTES: tuple[str, ...] = ("epo_ops", "uspto_odp")
EPO_AUTH = "https://ops.epo.org/3.2/auth/accesstoken"
EPO_SEARCH = "https://ops.epo.org/3.2/rest-services/published-data/search"
USPTO_SEARCH = "https://api.uspto.gov/api/v1/patent/applications/search"

#: http(method, url, headers, body) -> (status, body bytes). Injected so tests never touch a host.
Http = Callable[[str, str, Mapping[str, str], bytes | None], tuple[int, bytes]]


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1, default=str), "utf-8")


def _http(ua: str) -> Http:
    def call(method: str, url: str, headers: Mapping[str, str], body: bytes | None
             ) -> tuple[int, bytes]:
        req = urllib.request.Request(url, data=body, method=method,
                                     headers={"User-Agent": ua, **dict(headers)})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return int(getattr(r, "status", 200) or 200), r.read(2_000_000)
        except urllib.error.HTTPError as exc:
            return int(exc.code or 0), b""
        except Exception:
            return 0, b""
    return call


# ------------------------------------------------------------------------------- credentials

def credential(route: str, env: Mapping[str, str] | None = None,
               secrets: Path = SECRETS) -> dict[str, str] | None:
    """The route's key material, or None. Never printed; the report names only the SOURCE."""
    env = os.environ if env is None else env
    if route == "epo_ops":
        k, s = env.get("EPO_OPS_KEY", ""), env.get("EPO_OPS_SECRET", "")
        if not (k and s):
            d = _read(secrets / "epo_ops.json", {}) or {}
            k, s = str(d.get("key") or ""), str(d.get("secret") or "")
        return {"key": k, "secret": s} if k and s else None
    if route == "uspto_odp":
        k = env.get("USPTO_API_KEY", "") or str(
            (_read(secrets / "uspto_odp.json", {}) or {}).get("key") or "")
        return {"key": k} if k else None
    return None


CRED_WHERE = {"epo_ops": "data/secrets/epo_ops.json {key, secret} or EPO_OPS_KEY/EPO_OPS_SECRET",
              "uspto_odp": "data/secrets/uspto_odp.json {key} or USPTO_API_KEY"}


# ------------------------------------------------------------------------------------- weeks

def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def due_weeks(now: datetime, have: Mapping[str, Any]) -> list[date]:
    """Completed weeks not yet counted, newest first."""
    last = week_start((now - timedelta(days=MIN_AGE_D)).date()) - timedelta(days=7)
    out = []
    for i in range(BACKFILL_WEEKS):
        w = last - timedelta(days=7 * i)
        if w.isoformat() not in have:
            out.append(w)
    return out


# -------------------------------------------------------------------------------- the routes

_TOTAL = re.compile(rb'total-result-count="(\d+)"')


def epo_query(w: date, cpcs: tuple[str, ...] | None) -> str:
    span = f'pd within "{w:%Y%m%d} {w + timedelta(days=6):%Y%m%d}"'
    if not cpcs:
        return span
    return span + " and (" + " or ".join(f"cpc={c}" for c in cpcs) + ")"


class EpoRoute:
    name = "epo_ops"

    def __init__(self, cred: Mapping[str, str], http: Http) -> None:
        self.cred, self.http, self.token = cred, http, ""

    def _auth(self) -> str | None:
        basic = base64.b64encode(f"{self.cred['key']}:{self.cred['secret']}".encode()).decode()
        st, body = self.http("POST", EPO_AUTH,
                             {"Authorization": f"Basic {basic}",
                              "Content-Type": "application/x-www-form-urlencoded"},
                             b"grant_type=client_credentials")
        if st != 200:
            return f"auth HTTP {st}"
        try:
            self.token = str(json.loads(body.decode("utf-8")).get("access_token") or "")
        except ValueError:
            return "auth body not JSON"
        return None if self.token else "auth returned no access_token"

    def url(self, w: date, cpcs: tuple[str, ...] | None) -> str:
        return EPO_SEARCH + "?" + urllib.parse.urlencode({"q": epo_query(w, cpcs),
                                                          "Range": "1-1"})

    def count(self, w: date, cpcs: tuple[str, ...] | None) -> tuple[int | None, str]:
        if not self.token:
            why = self._auth()
            if why:
                return None, why
        st, body = self.http("GET", self.url(w, cpcs),
                             {"Authorization": f"Bearer {self.token}",
                              "Accept": "application/xml"}, None)
        if st == 404:
            return 0, "HTTP 404: OPS answers a search with no hits as not found"
        if st != 200:
            return None, f"HTTP {st}"
        m = _TOTAL.search(body)
        return (int(m.group(1)), "ok") if m else (None, "SHAPE_UNRECOGNISED")


class UsptoRoute:
    name = "uspto_odp"

    def __init__(self, cred: Mapping[str, str], http: Http) -> None:
        self.cred, self.http = cred, http

    def url(self, w: date, cpcs: tuple[str, ...] | None) -> str:
        q = ("applicationMetaData.cpcClassificationBag:(" + " OR ".join(f"{c}*" for c in cpcs)
             + ")") if cpcs else "*"
        rng = f"applicationMetaData.filingDate {w:%Y-%m-%d}:{w + timedelta(days=6):%Y-%m-%d}"
        return USPTO_SEARCH + "?" + urllib.parse.urlencode(
            {"q": q, "rangeFilters": rng, "limit": "1"})

    def count(self, w: date, cpcs: tuple[str, ...] | None) -> tuple[int | None, str]:
        st, body = self.http("GET", self.url(w, cpcs),
                             {"X-API-KEY": self.cred["key"], "Accept": "application/json"},
                             None)
        if st == 404:
            return 0, "HTTP 404: no applications match"
        if st != 200:
            return None, f"HTTP {st}"
        try:
            n = json.loads(body.decode("utf-8")).get("count")
        except (ValueError, AttributeError):
            return None, "SHAPE_UNRECOGNISED"
        return (int(n), "ok") if isinstance(n, int) else (None, "SHAPE_UNRECOGNISED")


def fetch_route(route: Any, have: dict[str, Any], now: datetime, gate: Any, *,
                max_requests: int, deadline: float) -> dict[str, Any]:
    """Fill the newest missing weeks for one route. A week is stored only when complete."""
    rep: dict[str, Any] = {"weeks_added": [], "requests": 0, "errors": {}}
    for w in due_weeks(now, have):
        if rep["requests"] + 1 + len(SECTORS) > max_requests or time.monotonic() > deadline:
            rep["stopped"] = "request or time budget; the rest is next pass's"
            break
        row: dict[str, Any] = {}
        why = gate.refusal(route.url(w, None)) if gate is not None else None
        if why:
            rep["errors"]["robots"] = why
            rep["stopped"] = f"REFUSED by robots gate: {why}"
            break
        for sector, cpcs in [("_total", None), *[(s, v[0]) for s, v in SECTORS.items()]]:
            n, msg = route.count(w, cpcs)
            rep["requests"] += 1
            if n is None:
                rep["errors"][msg] = rep["errors"].get(msg, 0) + 1
                row = {}
                break
            row[sector] = n
        if not row:
            rep["stopped"] = "a count failed; the week is retried whole next pass"
            break
        row["retrieved"] = now.isoformat(timespec="seconds")
        have[w.isoformat()] = row
        rep["weeks_added"].append(w.isoformat())
    return rep


# ------------------------------------------------------------------------------- the series

def series_frame(weeks: Mapping[str, Any]) -> Any:
    """Weekly frame: available_time, week_start, counts, and the derived PIT columns."""
    import numpy as np
    import pandas as pd
    cols = ["available_time", "week_start", "backfilled"]
    if not weeks:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame.from_dict(dict(weeks), orient="index")
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    grid = pd.date_range(df.index.min(), df.index.max(), freq="7D")
    df = df.reindex(grid)
    out = pd.DataFrame(index=grid)
    out["week_start"] = grid
    week_end = grid + pd.Timedelta(days=6)
    out["available_time"] = (week_end + pd.Timedelta(days=1 + INDEX_LAG_D)).tz_localize(UTC)
    retrieved = pd.to_datetime(df.get("retrieved"), errors="coerce", utc=True)
    out["backfilled"] = (retrieved - out["available_time"]) > pd.Timedelta(
        days=BACKFILL_AFTER_D)
    total = pd.to_numeric(df.get("_total"), errors="coerce")
    tot13 = total.rolling(ROLL, min_periods=ROLL).sum()
    for sector in SECTORS:
        n = pd.to_numeric(df.get(sector), errors="coerce")
        s13 = n.rolling(ROLL, min_periods=ROLL).sum()
        out[f"{sector}_count"] = n
        out[f"{sector}_share13"] = (s13 / tot13.replace(0, np.nan))
        prior = s13.shift(52)
        out[f"{sector}_yoy13"] = np.log((s13 + 1.0) / (prior + 1.0)).where(prior.notna())
    return out.reset_index(drop=True)


# --------------------------------------------------------------------------------- the cells

def grid(frames: Mapping[str, Any]) -> list[dict[str, Any]]:
    from proposer_common import candidate
    out: list[dict[str, Any]] = []
    for route in sorted(frames):
        df = frames[route]
        src = f"patent_filings_{route}"
        for sector, (cpcs, syms, why) in SECTORS.items():
            for sig in SIGNALS:
                col = f"{sector}_{sig}"
                if col not in df.columns or int(df[col].notna().sum()) < MIN_ROWS:
                    continue
                for sym, (t, thr, side) in product(syms, product(*GRID.values())):
                    params = {"source": src, "signal": col, "transform": t, "threshold": thr,
                              "side_when_high": side, "lag_hours": 24, "timeframe": CHART}
                    c = candidate(SEAT, sym, "exogenous_conditioner", params,
                                  f"{why}; {route} weekly {sector} ({'/'.join(cpcs)}) {sig}",
                                  f"exogenous_conditioner on {src}.{col} -> {sym} {CHART}",
                                  {"source_row": f"{route}:{sector}", "column": col,
                                   "arm": "direct:level", "cpc": list(cpcs)})
                    c["chart"] = CHART
                    c["required_data"] = [f"desks/mt5/data/lake/series/{src}.parquet"]
                    c["falsifier"] = (f"{src}.{col} at |z|>={thr} has no measurable relation "
                                      f"to {sym} at {CHART} out of sample")
                    out.append(c)
    return out


def mint(cells: list[dict[str, Any]], *, dry_run: bool, state_path: Path = MINTED
         ) -> dict[str, Any]:
    from proposer_common import identity
    state = _read(state_path, {}) or {}
    seen = set(state.get("identities") or [])
    new = [c for c in cells if identity(c["symbol"], c["family"], c["params"]) not in seen]
    rep: dict[str, Any] = {"grid": len(cells), "already_minted": len(cells) - len(new),
                           "new": len(new), "minted": 0, "contract": None}
    if not new or dry_run:
        return rep
    from proposer_common import donate, donation_counts
    path = donate(source=SEAT, candidates=new, tests_run=len(new))
    counts = donation_counts()
    rep.update({"minted": int(counts.get("donated") or 0),
                "refused_wrong_lane": int(counts.get("refused_wrong_lane") or 0),
                "refused_unstamped": int(counts.get("refused_unstamped") or 0),
                "contract": str(path) if path else None,
                "trials_charged": len(new) if path else 0})
    seen.update(identity(c["symbol"], c["family"], c["params"]) for c in new)
    _write_json(state_path, {"identities": sorted(seen), "updated": _now().isoformat()})
    return rep


# ------------------------------------------------------------------------------------- main

def run(*, budget_s: float = 600.0, dry_run: bool = False, now: datetime | None = None,
        http: Http | None = None, gate: Any = None, env: Mapping[str, str] | None = None,
        secrets: Path = SECRETS) -> dict[str, Any]:
    import pandas as pd
    now = now or _now()
    deadline = time.monotonic() + budget_s
    counts: dict[str, Any] = _read(COUNTS, {}) or {}
    if gate is None:
        from libs.data.robots_gate import RobotsGate
        gate = RobotsGate("patent_filings")
    http = http or _http(gate.ua)
    routes_rep: dict[str, Any] = {}
    for name in ROUTES:
        cred = credential(name, env, secrets)
        have = counts.setdefault(name, {})
        if cred is None:
            routes_rep[name] = {"status": "NEEDS_CREDENTIAL",
                                "why": f"no key: {CRED_WHERE[name]} (free registration)",
                                "weeks_held": len(have)}
            continue
        route = EpoRoute(cred, http) if name == "epo_ops" else UsptoRoute(cred, http)
        r = fetch_route(route, have, now, gate, max_requests=MAX_REQUESTS, deadline=deadline)
        r["status"] = "RAN" if r["weeks_added"] or not r["errors"] else "FAILED"
        r["weeks_held"] = len(have)
        routes_rep[name] = r
        _write_json(COUNTS, counts)
    frames: dict[str, Any] = {}
    lake: dict[str, Any] = {}
    for name in ROUTES:
        weeks = counts.get(name) or {}
        if not weeks:
            lake[name] = {"status": "UNMEASURED", "why": "no weeks counted on this host"}
            continue
        df = series_frame(weeks)
        SERIES_DIR.mkdir(parents=True, exist_ok=True)
        dst = SERIES_DIR / f"patent_filings_{name}.parquet"
        tmp = dst.with_suffix(".parquet.tmp")
        df.to_parquet(tmp, index=False)
        os.replace(tmp, dst)
        frames[name] = df
        lake[name] = {"status": "OK", "weeks": len(df),
                      "first_week": str(pd.Timestamp(df["week_start"].iloc[0]).date()),
                      "last_week": str(pd.Timestamp(df["week_start"].iloc[-1]).date())}
    cells = grid(frames)
    doc = {"generated_utc": now.isoformat(timespec="seconds"),
           "writer": "research/patent_filings.py", "seat": SEAT,
           "sectors": {s: {"cpc": list(v[0]), "instruments": list(v[1]), "why": v[2]}
                       for s, v in SECTORS.items()},
           "routes": routes_rep, "robots": gate.consulted, "lake": lake,
           "mint": mint(cells, dry_run=dry_run)}
    ok = [n for n, v in lake.items() if v.get("status") == "OK"]
    doc["status"] = "OK" if ok else "UNMEASURED"
    if not ok:
        doc["why"] = ("no route has counted a week on this host: "
                      + "; ".join(f"{n}: {v.get('status')}" for n, v in routes_rep.items()))
    _write_json(REPORT, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, dry_run=a.dry_run)
    print(f"patent_filings: {doc['status']}; routes "
          + ", ".join(f"{k}={v.get('status')}" for k, v in doc["routes"].items())
          + f"; minted {doc['mint'].get('minted')} of {doc['mint'].get('new')} new")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
