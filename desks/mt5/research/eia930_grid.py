"""EIA-930 GRID DEMAND SURPRISE -- the US hourly electric grid as a nowcast for gas burn and load.

WHAT IT READS. The EIA Hourly Electric Grid Monitor (form EIA-930) publishes, per balancing
authority and per EIA region, actual hourly demand (`D`) and the day-ahead demand forecast the
balancing authority filed the day before (`DF`). The SURPRISE is

    s(region, hour) = (D - DF) / DF

-- how far the hour's load landed from what the grid operator itself expected a day earlier. It
is weather-driven gas burn and industrial load read every hour, a day before any weekly storage
report or monthly industrial-production print can say the same thing.

WHO IT FEEDS (ideas ledger #12, accepted 2026-11-17 23:26Z):
  * XNGUSD (Fusion's natural gas CFD): every mapped region, prior sign +1 (load above the
    operator's forecast is unplanned burn, gas-fired plants are the marginal unit in most hours).
  * US500, US30, NAS100, US2000: the Lower-48 aggregate only (a broad industrial / activity read;
    a single region's weather is noise to a national index). Both sides are judged.
  Single-name share CFDs are never mapped: the two-lane order keeps them out of statistical
  hunting, and `universe_policy.may_hypothesise` is asked for every symbol anyway (fails closed).

ONE PASS (hourly leg `eia930_grid`, `--once --budget-s 240`):
  1. TERMS, REFUSED HOSTS, ROBOTS, KEY -- in that order, each failing closed with a named
     status: the terms row below must read `machine_use_allowed: True`; `libs.data.refused_hosts`
     must not list the host; api.eia.gov/robots.txt must allow the route for our agent (only a
     404/410 means "no rules"; anything unreadable refuses); the EIA key is read BY NAME through
     `research.keyed_sources.resolve_keys` (`EIA_API_KEY` and its accepted aliases) and is never
     printed, logged or stored -- every error string and every stored body passes `redact` /
     `scrub_body` first.
  2. THE API DESCRIBES ITSELF, AND IS BELIEVED ONLY WHEN IT AGREES. The route, frequency, data
     column and facet codes this organ was written against are EXPECTED values, not facts: they
     were not readable from the build container. Once a day the collector reads the API's own
     metadata (`GET v2/electricity/rto/` -> child routes; `GET v2/electricity/rto/region-data/`
     -> frequencies, facets, data columns; `.../facet/type/` and `.../facet/respondent/` ->
     the codes) and refuses with `METADATA_MISMATCH:<what differed>` when any of them differ.
     A data row missing `period`, `respondent`, `type` or `value` is the same refusal.
  3. HARD STOP on 401 / 403 / 429 / 451: no further request this pass, the code is recorded,
     and the organ makes no request for `HARD_STOP_H` hours (451, a legal block, stays stopped
     until a person clears `hard_stop` in the state file). Throttle: one request at most every
     `MIN_INTERVAL_S` seconds and at most `MAX_REQUESTS` per pass (EIA's terms: programs "must
     throttle the number of the requests they make per second and per hour").
  4. STORE, POINT-IN-TIME, APPEND-ONLY, DAILY PARTITIONS: `data/eia930/obs/<YYYY-MM-DD>.jsonl`
     (gitignored, box-local; raw pulled data is never committed). The first value seen for a
     (respondent, type, hour) is the value for ever; a later different value is appended as a
     revision beside it. Re-merging the same rows appends nothing (idempotent).
  5. PUBLISH: the lake series `data/lake/series/eia930_<region>__demand_surprise.csv` in the PIT
     envelope `mt5desk.family_exogenous_conditioner` loads; `reports/EIA930_GRID.json` (latest
     surprise per region, its z-score, the hour it applies to); `reports/EIA930_TRIGGER.json`
     (the live trigger, below).
  6. CELLS: `exogenous_conditioner` cells on each mapped instrument through
     `proposer_common.donate`, a ring slice per pass, every one charged to the trial census.

POINT-IN-TIME RULE. An hour's value describes the hour starting or ending at `period` -- EIA's
convention is not verified from here -- so the hour is treated as complete only at
`period + 1h` (late under either reading). A value seen live is available at
max(period + 1h, first seen). A value from the organ's FIRST successful fetch (backfill) is
available at period + 1h + `BACKFILL_LAG_H`, late by construction, because when EIA first
published it is unknown. The surprise of an hour is available when BOTH its D and DF are.

THE Z-SCORE WINDOW IS DERIVED, NOT CHOSEN: `Z_WINDOW_H = 4 * 168` (four whole weeks, so every
hour-of-day and day-of-week appears equally often in the baseline, and a calendar effect cannot
masquerade as a surprise), and `Z_MIN_H = 168` (one whole week is the least history in which that
balance holds at all). Below it the z is None -- UNMEASURED, never 0.

THE LIVE TRIGGER (`reports/EIA930_TRIGGER.json`). Each pass it flags regions whose latest surprise
z-score satisfies |z| >= z*, where

    z* = Phi^-1(1 - ALPHA / (2 k))

with k = the number of regions measured on that pass and ALPHA = 0.05 the family-wise two-sided
false-alarm rate per hour: a Bonferroni bound, so on an ordinary hour (no region truly surprised)
the whole board raises a false flag at most one hour in twenty. z* is recomputed from k every
pass (about 3.0 for 14 regions); it is not a fiat cap. Every region that cannot fire -- too little
history, stale data, a blocked source -- carries a `missed_growth` line, and so does the
threshold itself (the regions with 1.96 <= |z| < z* it chose not to flag). The trigger sizes
nothing and places nothing.

DESIGNED TO FEED THE LIVE WIRE. `desks/mt5/research/live_wire.py` (branch `claude/gdd-live-wire`,
not yet on LIVE) is the organ that turns live triggers into the desk's feeds duty; this artifact's
shape (`flags[]` with region, hour, z, direction, instruments) is what it should read once it
lands. Nothing here imports it.

    python desks/mt5/research/eia930_grid.py --once [--budget-s 240] [--no-fetch] [--dry-run]
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import product
from pathlib import Path
from statistics import NormalDist
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import keyed_sources as ks  # noqa: E402

SOURCE_ID = "eia930_grid"
SEAT = "eia930_grid"
UNMEASURED = "UNMEASURED"
API = "https://api.eia.gov/v2/"
KEY_ENV = "EIA_API_KEY"

# ------------------------------------------------------------------ terms (checked 2026-11-17)
#: The source's terms row, in the shape `alt_proxies.TERMS_EVIDENCE` records: what was read, where,
#: and what robots said. `machine_use_allowed` is the only switch the collector obeys.
TERMS_EVIDENCE: dict[str, Any] = {
    "terms_url": "https://www.eia.gov/about/copyrights_reuse.php",
    "terms_quote": "U.S. government publications are in the public domain",
    "api_terms_url": "https://www.eia.gov/opendata/terms-of-service.php",
    "api_terms_quote": ("building a service to retrieve EIA data is permitted; EIA asks for "
                        "'EIA' attribution; 'these programs must throttle the number of the "
                        "requests they make per second and per hour' or the key is temporarily "
                        "suspended"),
    "robots": ("www.eia.gov/robots.txt: 'User-agent: * / Allow: /', no Disallow on /opendata/ or "
               "/electricity/. api.eia.gov/robots.txt NOT readable from the build container: "
               "the robots gate below reads it at fetch time and fails closed"),
    "attribution": "Source: U.S. Energy Information Administration (EIA), Form EIA-930",
    "checked_at": "2026-11-17",
    "machine_use_allowed": True,
}

# --------------------------------------------------------------- expected API shape (unverified)
#: What this organ was written against. NOT FACTS: each is checked against the API's own
#: metadata before any data request, and a difference refuses the pass by name.
PARENT_ROUTE = "electricity/rto"
CHILD_ROUTE = "region-data"
FREQUENCY = "hourly"
DATA_COLUMN = "value"
FACET_TYPE = "type"
FACET_RESPONDENT = "respondent"
TYPE_DEMAND = "D"
TYPE_FORECAST = "DF"
#: EIA's Lower-48 aggregate and its large regions, as respondent codes. A code the API does not
#: list is skipped by name; none listed at all is a metadata mismatch.
REGIONS: tuple[str, ...] = ("US48", "CAL", "CAR", "CENT", "FLA", "MIDA", "MIDW", "NE", "NY",
                            "NW", "SE", "SW", "TEN", "TEX")
L48 = "US48"
INDEX_CFDS: tuple[str, ...] = ("US500", "US30", "NAS100", "US2000")
GAS = "XNGUSD"


def instruments_for(region: str) -> dict[str, int]:
    """Region -> {MT5 symbol: prior sign}. Gas for every region; the index CFDs on L48 only."""
    out = {GAS: 1}
    if region == L48:
        out.update(dict.fromkeys(INDEX_CFDS, 1))
    return out


# -------------------------------------------------------------------------- pacing and stops
#: Seconds between two requests, and requests per pass. One pass an hour, so at most
#: MAX_REQUESTS an hour and one a second -- the terms' "per second and per hour" throttle.
MIN_INTERVAL_S = 1.0
MAX_REQUESTS = 24
PAGE_LENGTH = 5000                       # the API's own maximum rows per JSON call
HARD_STOP_CODES = frozenset({401, 403, 429, 451})
HARD_STOP_H = 24
METADATA_TTL_H = 24
TIMEOUT = 30.0
MAX_BYTES = 16 * 1024 * 1024
ROBOTS_AGENT = "quant-desk-research"
UA = f"{ROBOTS_AGENT}/1.0 (eia930_grid; research; honours robots.txt)"

# ------------------------------------------------------------------------------ windows
BACKFILL_DAYS = 45                       # first pass: Z_WINDOW_H plus a margin of whole weeks
REPULL_H = 48                            # later passes re-read two days for revisions
BACKFILL_LAG_H = 24
Z_WINDOW_H = 4 * 168
Z_MIN_H = 168
#: Hours after which the newest measured hour no longer describes "now": DF is a day-ahead
#: forecast, so a surprise more than a day old describes yesterday's grid.
STALE_H = 24
ALPHA = 0.05
NOMINAL_Z = NormalDist().inv_cdf(1 - ALPHA / 2)
#: Points a series needs before cells are minted: a full z window, so the family's own z over
#: `Z_WINDOW_H` is measured on the same baseline the trigger uses.
MIN_POINTS = Z_WINDOW_H
#: Hours the family holds the series back before it conditions a bar: the broker clock runs up
#: to UTC+3, so 3 h absorbs the offset and 1 h more covers the hour's own completion.
LAG_HOURS = 4

MISSED_GROWTH = {
    "blocked": ("source not fetched: the hourly grid surprise reaches no XNGUSD / US index "
                "exogenous_conditioner cell, no lake series and no live trigger until it is"),
    "history": ("region stands down until it holds {need} measured hours (has {have}): a z "
                "without a whole-week baseline would flag calendar effects as surprises"),
    "stale": ("region stands down: its newest measured hour is {age:.1f} h old (> {lim} h); a "
              "flag on yesterday's grid would trade information the market already had"),
    "threshold": ("{n} region(s) at {nom:.2f} <= |z| < z*={zs:.2f} not flagged: the Bonferroni "
                  "bound trades these marginal surprises for a board-wide false-alarm rate of "
                  "{alpha:.0%} per hour"),
}


@dataclass(frozen=True)
class Paths:
    desk: Path = DESK

    @property
    def store(self) -> Path:
        return self.desk / "data" / "eia930"

    @property
    def obs(self) -> Path:
        return self.store / "obs"

    @property
    def state(self) -> Path:
        return self.store / "state.json"

    @property
    def series(self) -> Path:
        return self.desk / "data" / "lake" / "series"

    @property
    def universe(self) -> Path:
        return self.desk / "data" / "universe" / "universe.json"

    @property
    def report(self) -> Path:
        return self.desk / "reports" / "EIA930_GRID.json"

    @property
    def trigger(self) -> Path:
        return self.desk / "reports" / "EIA930_TRIGGER.json"


class Refused(Exception):
    """A named refusal: METADATA_MISMATCH:..., ROBOTS_REFUSED:..., HARD_STOP:<code>, ..."""


# ------------------------------------------------------------------------------- io helpers
def _now() -> datetime:
    return datetime.now(UTC)


def _read(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _atomic(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str), "utf-8")
    os.replace(tmp, p)


def _t(s: Any) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _iso(d: datetime) -> str:
    return d.astimezone(UTC).isoformat(timespec="seconds")


def parse_period(text: Any) -> datetime | None:
    """'2026-11-17T05' (EIA hourly, UTC) -> an aware datetime; anything else None."""
    t = str(text or "").strip()
    for fmt in ("%Y-%m-%dT%H", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(t, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _num(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


# ------------------------------------------------------------------------------- the fetcher
#: (url) -> (HTTP status, body). Injected in tests; `http_get` on the box.
Getter = Callable[[str], tuple[int, bytes]]


class _Redirects(ks.SameHostAuthRedirect):
    """The credential-safe redirect rules, plus the refused-hosts check on every hop."""

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any,
                         newurl: str) -> Any:
        from libs.data import refused_hosts
        why = refused_hosts.refusal(newurl)
        if why:
            raise refused_hosts.RefusedRedirect(f"BLOCKED_ON_TERMS: redirect refused ({why})")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def http_get(url: str) -> tuple[int, bytes]:
    """One GET through the credential-safe opener (a redirect never carries the key off-host,
    nor reaches a refused host). Returns the status instead of raising on 4xx/5xx. The body is
    scrubbed of the key by `Client.json` before anything reads or stores it."""
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=_tls()),
                                         _Redirects())
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with opener.open(req, timeout=TIMEOUT) as resp:
            return int(getattr(resp, "status", 200) or 200), bytes(resp.read(MAX_BYTES))
    except urllib.error.HTTPError as e:
        return int(e.code), b""


def _tls() -> Any:
    with contextlib.suppress(Exception):
        from research import asia_collector
        make: Any = asia_collector._tls_context
        return make()
    return None


class Client:
    """Every request of a pass: throttled, counted, hard-stopped, key redacted from errors."""

    def __init__(self, get: Getter, key: str, *, sleep: Callable[[float], None] = time.sleep,
                 max_requests: int = MAX_REQUESTS, min_interval_s: float = MIN_INTERVAL_S
                 ) -> None:
        self.get, self.key, self.sleep = get, key, sleep
        self.max_requests, self.min_interval_s = max_requests, min_interval_s
        self.requests = 0
        self._last = -math.inf

    def _pace(self) -> None:
        if self.requests >= self.max_requests:
            raise Refused(f"BUDGET:request budget of {self.max_requests} per pass spent")
        wait = self.min_interval_s - (time.monotonic() - self._last)
        if wait > 0 and self.requests:
            self.sleep(wait)
        self._last = time.monotonic()
        self.requests += 1

    def raw(self, url: str) -> tuple[int, bytes]:
        self._pace()
        try:
            status, body = self.get(url)
        except Exception as exc:
            raise Refused("FETCH_ERROR:" + ks.redact(f"{type(exc).__name__}: {exc}",
                                                     [self.key])[:200]) from None
        if status in HARD_STOP_CODES:
            raise Refused(f"HARD_STOP:{status}")
        return status, body

    def json(self, route: str, params: list[tuple[str, str]] | None = None) -> Any:
        q = [("api_key", self.key), *(params or [])]
        url = API + route.strip("/") + "/?" + urllib.parse.urlencode(q)
        status, body = self.raw(url)
        if status != 200:
            raise Refused(f"HTTP_{status}:{route}")
        try:
            doc = json.loads(ks.scrub_body(body, [self.key]).decode("utf-8", errors="replace"))
        except ValueError:
            raise Refused(f"UNPARSEABLE:{route} did not answer JSON") from None
        if not isinstance(doc, dict) or not isinstance(doc.get("response"), dict):
            err = ks.redact(str((doc or {}).get("error") if isinstance(doc, dict) else doc),
                            [self.key])[:160]
            raise Refused(f"API_ERROR:{route}: {err}")
        return doc["response"]


# ------------------------------------------------------------------------------- the gates
def robots_refusal(get: Getter, url: str) -> str | None:
    """None when api.eia.gov's robots.txt allows `url` for our agent, else why not. Only 404 or
    410 means "no rules"; anything unreadable, an HTML page or a stop code refuses."""
    parts = urllib.parse.urlsplit(url)
    try:
        status, body = get(f"{parts.scheme}://{parts.netloc}/robots.txt")
    except Exception as exc:
        return f"ROBOTS_REFUSED:robots.txt unreadable ({type(exc).__name__})"
    if status in (404, 410):
        return None
    if status != 200:
        return f"ROBOTS_REFUSED:robots.txt answered HTTP {status}"
    text = body.decode("utf-8", errors="replace")
    if text.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
        return "ROBOTS_REFUSED:robots.txt answered HTML"
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(text.splitlines())
    if not rp.can_fetch(ROBOTS_AGENT, url):
        return f"ROBOTS_REFUSED:robots.txt disallows {parts.path}"
    return None


def access_refusal(get: Getter) -> str | None:
    """Terms, then the refused-hosts list, then robots -- before any keyed request."""
    if TERMS_EVIDENCE.get("machine_use_allowed") is not True:
        return "BLOCKED_ON_TERMS:machine_use_allowed is not true"
    from libs.data import refused_hosts
    why = refused_hosts.refusal(API)
    if why:
        return f"BLOCKED_ON_TERMS:{why}"
    return robots_refusal(get, API + PARENT_ROUTE + "/" + CHILD_ROUTE + "/data/")


def _ids(rows: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    for r in rows if isinstance(rows, list) else []:
        if isinstance(r, dict) and r.get("id") is not None:
            out[str(r["id"])] = str(r.get("name") or r.get("description") or "")
    return out


def verify_metadata(client: Client) -> dict[str, Any]:
    """The API's own description of the route, checked against what this organ expects.
    Returns {"regions": [...present], "missing_regions": [...]}; raises METADATA_MISMATCH."""
    parent = client.json(PARENT_ROUTE)
    kids = _ids(parent.get("routes"))
    if CHILD_ROUTE not in kids:
        raise Refused(f"METADATA_MISMATCH:{PARENT_ROUTE} lists no child route '{CHILD_ROUTE}' "
                      f"(children: {sorted(kids)[:12]})")
    route = f"{PARENT_ROUTE}/{CHILD_ROUTE}"
    meta = client.json(route)
    freqs = _ids(meta.get("frequency"))
    if FREQUENCY not in freqs:
        raise Refused(f"METADATA_MISMATCH:{route} has no frequency '{FREQUENCY}' "
                      f"(has {sorted(freqs)})")
    facets = _ids(meta.get("facets"))
    for f in (FACET_TYPE, FACET_RESPONDENT):
        if f not in facets:
            raise Refused(f"METADATA_MISMATCH:{route} has no facet '{f}' (has {sorted(facets)})")
    data = meta.get("data")
    if not isinstance(data, dict) or DATA_COLUMN not in data:
        cols = sorted(data) if isinstance(data, dict) else type(data).__name__
        raise Refused(f"METADATA_MISMATCH:{route} has no data column '{DATA_COLUMN}' ({cols})")
    types = _ids(client.json(f"{route}/facet/{FACET_TYPE}").get("facets"))
    d_name, df_name = types.get(TYPE_DEMAND), types.get(TYPE_FORECAST)
    if d_name is None or "demand" not in d_name.lower() or "forecast" in d_name.lower():
        raise Refused(f"METADATA_MISMATCH:type '{TYPE_DEMAND}' is not actual demand "
                      f"({d_name!r})")
    if df_name is None or "forecast" not in df_name.lower():
        raise Refused(f"METADATA_MISMATCH:type '{TYPE_FORECAST}' is not the demand forecast "
                      f"({df_name!r})")
    resp = _ids(client.json(f"{route}/facet/{FACET_RESPONDENT}").get("facets"))
    present = [r for r in REGIONS if r in resp]
    if not present:
        raise Refused(f"METADATA_MISMATCH:none of the regions {list(REGIONS)} is a respondent")
    return {"regions": present, "missing_regions": [r for r in REGIONS if r not in resp],
            "type_names": {TYPE_DEMAND: d_name, TYPE_FORECAST: df_name}}


# ------------------------------------------------------------------------------- data pull
def data_params(regions: Iterable[str], start: datetime, offset: int) -> list[tuple[str, str]]:
    q: list[tuple[str, str]] = [("frequency", FREQUENCY), ("data[0]", DATA_COLUMN)]
    q += [(f"facets[{FACET_TYPE}][]", t) for t in (TYPE_DEMAND, TYPE_FORECAST)]
    q += [(f"facets[{FACET_RESPONDENT}][]", r) for r in regions]
    q += [("start", start.strftime("%Y-%m-%dT%H")), ("sort[0][column]", "period"),
          ("sort[0][direction]", "desc"), ("offset", str(offset)),
          ("length", str(PAGE_LENGTH))]
    return q


def parse_rows(data: Any) -> list[dict[str, Any]]:
    """`response.data[]` -> rows {respondent, type, period, value}. A row without the four fields
    is a METADATA_MISMATCH; a null value is skipped (absence is not a zero)."""
    out: list[dict[str, Any]] = []
    for r in data if isinstance(data, list) else []:
        if not isinstance(r, dict):
            continue
        miss = [k for k in ("period", FACET_RESPONDENT, FACET_TYPE, DATA_COLUMN) if k not in r]
        if miss:
            raise Refused(f"METADATA_MISMATCH:data row lacks {miss}")
        p, v = parse_period(r["period"]), _num(r[DATA_COLUMN])
        if p is None:
            raise Refused(f"METADATA_MISMATCH:period {str(r['period'])[:24]!r} is not hourly")
        if v is None or str(r[FACET_TYPE]) not in (TYPE_DEMAND, TYPE_FORECAST):
            continue
        out.append({"respondent": str(r[FACET_RESPONDENT]), "type": str(r[FACET_TYPE]),
                    "period": p, "value": v})
    return out


def pull(client: Client, regions: list[str], start: datetime
         ) -> tuple[list[dict[str, Any]], bool]:
    """Every page since `start` -> (rows, complete). A pass whose request budget runs out keeps
    the pages it already read (complete=False) and the next pass re-reads from its own start."""
    route = f"{PARENT_ROUTE}/{CHILD_ROUTE}/data"
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        try:
            resp = client.json(route, data_params(regions, start, offset))
        except Refused as r:
            if str(r).startswith("BUDGET:") and rows:
                return rows, False
            raise
        page = resp.get("data")
        rows += parse_rows(page)
        n = len(page) if isinstance(page, list) else 0
        total = _num(resp.get("total"))
        offset += n
        if n < PAGE_LENGTH or (total is not None and offset >= total):
            return rows, True


# --------------------------------------------------------------------- point-in-time store
def obs_key(respondent: str, typ: str, period: str) -> str:
    return f"{respondent}|{typ}|{period}"


def load_store(paths: Paths) -> dict[str, dict[str, Any]]:
    """key -> {first record..., value_last, n_revisions}. The FIRST value is the PIT value."""
    store: dict[str, dict[str, Any]] = {}
    if not paths.obs.exists():
        return store
    for f in sorted(paths.obs.glob("*.jsonl")):
        with contextlib.suppress(OSError):
            for line in f.read_text("utf-8").splitlines():
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                k = r.get("k") if isinstance(r, dict) else None
                if not k:
                    continue
                if k not in store:
                    store[k] = {**r, "value_last": r.get("value"), "n_revisions": 0}
                else:
                    store[k]["value_last"] = r.get("value")
                    store[k]["n_revisions"] = int(store[k].get("n_revisions") or 0) + 1
                    store[k]["revision_time"] = r.get("first_seen_at")
    return store


def merge(paths: Paths, store: dict[str, dict[str, Any]], rows: list[dict[str, Any]],
          seen: datetime, backfill: bool) -> dict[str, int]:
    """Append what is new to the day's partition: a key never seen, or a value that differs from
    the last one stored (a revision). The same rows merged twice append nothing."""
    by_day: dict[str, list[dict[str, Any]]] = {}
    added = revised = 0
    stamp = _iso(seen)
    for r in rows:
        period = _iso(r["period"])
        k = obs_key(r["respondent"], r["type"], period)
        cur = store.get(k)
        end = r["period"] + timedelta(hours=1)
        if cur is None:
            avail = end + timedelta(hours=BACKFILL_LAG_H) if backfill else max(end, seen)
            rec = {"k": k, "respondent": r["respondent"], "type": r["type"], "period": period,
                   "value": r["value"], "first_seen_at": stamp, "available_time": _iso(avail),
                   "pit_quality": "backfill" if backfill else "live", "revision": False}
            store[k] = {**rec, "value_last": r["value"], "n_revisions": 0}
            added += 1
        elif not math.isclose(float(cur.get("value_last") or 0.0), r["value"],
                              rel_tol=1e-9, abs_tol=1e-9):
            rec = {"k": k, "respondent": r["respondent"], "type": r["type"], "period": period,
                   "value": r["value"], "first_seen_at": stamp, "revision": True}
            cur["value_last"] = r["value"]
            cur["n_revisions"] = int(cur.get("n_revisions") or 0) + 1
            cur["revision_time"] = stamp
            revised += 1
        else:
            continue
        by_day.setdefault(period[:10], []).append(rec)
    paths.obs.mkdir(parents=True, exist_ok=True)
    for day, recs in sorted(by_day.items()):
        with (paths.obs / f"{day}.jsonl").open("a", encoding="utf-8") as fh:
            for rec in recs:
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
    return {"added": added, "revised": revised}


# ------------------------------------------------------------------------------ the signal
def surprise(demand: float, forecast: float) -> float | None:
    """(D - DF) / DF; None when the forecast is not a positive number (no ratio to read)."""
    if not (math.isfinite(demand) and math.isfinite(forecast)) or forecast <= 0:
        return None
    return (demand - forecast) / forecast


def zscore(prior: list[float], x: float, window: int = Z_WINDOW_H,
           min_n: int = Z_MIN_H) -> float | None:
    """x against the trailing `window` STRICTLY EARLIER values; None below `min_n` or zero sd."""
    w = prior[-window:]
    if len(w) < min_n:
        return None
    m = sum(w) / len(w)
    sd = math.sqrt(sum((v - m) ** 2 for v in w) / len(w))
    return (x - m) / sd if sd > 0 else None


def surprise_series(store: Mapping[str, Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Per region, hourly points in period order: D, DF (first-seen values), the surprise, its z
    over strictly earlier hours, and the instant both halves were available."""
    halves: dict[tuple[str, str], dict[str, Mapping[str, Any]]] = {}
    for r in store.values():
        halves.setdefault((str(r["respondent"]), str(r["period"])), {})[str(r["type"])] = r
    by: dict[str, list[dict[str, Any]]] = {}
    for (reg, period), h in halves.items():
        d, f = h.get(TYPE_DEMAND), h.get(TYPE_FORECAST)
        if d is None or f is None:
            continue
        s = surprise(float(d["value"]), float(f["value"]))
        if s is None:
            continue
        avail = max(str(d["available_time"]), str(f["available_time"]))
        quality = "live" if "live" == d.get("pit_quality") == f.get("pit_quality") else "backfill"
        by.setdefault(reg, []).append({
            "event_time": period, "available_time": avail,
            "first_seen_at": max(str(d["first_seen_at"]), str(f["first_seen_at"])),
            "revision_time": d.get("revision_time") or f.get("revision_time"),
            "pit_quality": quality, "demand": float(d["value"]),
            "forecast": float(f["value"]), "value": round(s, 8)})
    out: dict[str, list[dict[str, Any]]] = {}
    for reg, pts in by.items():
        pts.sort(key=lambda p: p["event_time"])
        vals: list[float] = []
        for p in pts:
            z = zscore(vals, p["value"])
            p["z"] = None if z is None else round(z, 6)
            vals.append(p["value"])
        out[reg] = pts
    return out


def lake_name(region: str) -> str:
    return f"eia930_{region.lower()}__demand_surprise"


def write_lake(paths: Paths, series: Mapping[str, list[dict[str, Any]]]) -> list[str]:
    import pandas as pd
    paths.series.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for reg, pts in sorted(series.items()):
        if not pts:
            continue
        df = pd.DataFrame([{**p, "source_id": SOURCE_ID,
                            "vintage_id": f"{SOURCE_ID}:{p['first_seen_at']}"} for p in pts])
        target = paths.series / f"{lake_name(reg)}.csv"
        tmp = target.with_suffix(f".tmp{os.getpid()}")
        df.to_csv(tmp, index=False)
        os.replace(tmp, target)
        written.append(target.name)
    return written


# ----------------------------------------------------------------------------- the trigger
def threshold(k: int, alpha: float = ALPHA) -> float | None:
    """z* = Phi^-1(1 - alpha / 2k): the two-sided Bonferroni bound for k regions read at once.
    None when nothing is measured (no board, no bound)."""
    if k <= 0:
        return None
    return NormalDist().inv_cdf(1 - alpha / (2 * k))


def latest_surprise(series: Mapping[str, list[dict[str, Any]]], now: datetime
                    ) -> dict[str, dict[str, Any]]:
    """Per region, the newest point available at `now` (point-in-time: nothing later)."""
    out: dict[str, dict[str, Any]] = {}
    for reg, pts in series.items():
        known = [p for p in pts if (_t(p["available_time"]) or now) <= now]
        if not known:
            continue
        p = known[-1]
        out[reg] = {"hour": p["event_time"],
                    "hour_complete_at": _iso((_t(p["event_time"]) or now) + timedelta(hours=1)),
                    "demand": p["demand"], "forecast": p["forecast"], "surprise": p["value"],
                    "z": p["z"], "available_time": p["available_time"],
                    "pit_quality": p["pit_quality"], "n_points": len(known)}
    return out


def build_trigger(latest: Mapping[str, Mapping[str, Any]], now: datetime, *,
                  source_status: str, regions: Iterable[str] = REGIONS) -> dict[str, Any]:
    stand_down: dict[str, dict[str, str]] = {}
    measured: dict[str, Mapping[str, Any]] = {}
    for reg in regions:
        p = latest.get(reg)
        if p is None:
            why = (source_status if source_status not in ("OK", "EMPTY", "NO_FETCH", "NOT_DUE")
                   else "NO_DATA")
            stand_down[reg] = {"status": "UNMEASURED", "why": why,
                               "missed_growth": MISSED_GROWTH["blocked"]}
            continue
        age = (now - (_t(p["hour_complete_at"]) or now)).total_seconds() / 3600.0
        if age > STALE_H:
            stand_down[reg] = {"status": "STALE", "why": f"newest hour {p['hour']}",
                               "missed_growth": MISSED_GROWTH["stale"].format(age=age,
                                                                             lim=STALE_H)}
            continue
        if p.get("z") is None:
            stand_down[reg] = {"status": "NO_HISTORY",
                               "why": f"{p['n_points']} measured hours < {Z_MIN_H}",
                               "missed_growth": MISSED_GROWTH["history"].format(
                                   need=Z_MIN_H, have=p["n_points"])}
            continue
        measured[reg] = p
    zs = threshold(len(measured))
    flags: list[dict[str, Any]] = []
    marginal: list[str] = []
    for reg, p in sorted(measured.items()):
        z = float(p["z"])
        if zs is not None and abs(z) >= zs:
            direction = 1 if z > 0 else -1
            flags.append({"region": reg, "hour": p["hour"], "z": round(z, 4),
                          "surprise": p["surprise"], "direction": direction,
                          "available_time": p["available_time"],
                          "instruments": {s: sign * direction
                                          for s, sign in instruments_for(reg).items()}})
        elif abs(z) >= NOMINAL_Z:
            marginal.append(reg)
    doc: dict[str, Any] = {
        "generated_at": _iso(now), "writer": "research/eia930_grid.py",
        "source_status": source_status,
        "rule": {"z_star": None if zs is None else round(zs, 4), "k_measured": len(measured),
                 "alpha_familywise": ALPHA,
                 "derivation": "z* = Phi^-1(1 - alpha/(2k)), two-sided Bonferroni over the k "
                               "regions measured this pass; recomputed every pass",
                 "z_window_h": Z_WINDOW_H, "z_min_h": Z_MIN_H, "stale_h": STALE_H},
        "flags": flags, "n_flags": len(flags), "stand_down": stand_down,
        "use": "live trigger for the feeds duty; sizes nothing, places nothing. Designed to "
               "feed research/live_wire.py once it lands on LIVE",
        "attribution": TERMS_EVIDENCE["attribution"]}
    if marginal and zs is not None:
        doc["missed_growth_threshold"] = {
            "regions": marginal,
            "line": MISSED_GROWTH["threshold"].format(n=len(marginal), nom=NOMINAL_Z, zs=zs,
                                                      alpha=ALPHA)}
    if not measured:
        doc["status"] = UNMEASURED
    return doc


# ------------------------------------------------------------------------------------ cells
def build_cells(paths: Paths, series: Mapping[str, list[dict[str, Any]]], now: datetime
                ) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """exogenous_conditioner cells: (region, instrument) x the keyed-sources grid. Fails closed
    without the universe policy; a symbol the registry does not hold is skipped."""
    from keyed_sources import EXO_GRID, universe_gate
    from proposer_common import candidate
    gate, blocker = universe_gate()
    skipped: dict[str, str] = {}
    if gate is None:
        return [], {"universe_policy": str(blocker)}
    uni = _read(paths.universe, {}) or {}
    stamp = _iso(now)
    cells: list[dict[str, Any]] = []
    for reg, pts in sorted(series.items()):
        if len(pts) < MIN_POINTS:
            skipped[reg] = f"{len(pts)} points < {MIN_POINTS}"
            continue
        src = lake_name(reg)
        for sym, prior in sorted(instruments_for(reg).items()):
            if sym not in uni or not gate(sym, "exogenous_conditioner"):
                skipped[f"{reg}.{sym}"] = "not in the universe registry or not hypothesis lane"
                continue
            for t, thr, side in product(*EXO_GRID.values()):
                c = candidate(SEAT, sym, "exogenous_conditioner",
                              {"source": src, "signal": "value", "transform": t,
                               "threshold": thr, "side_when_high": side * prior,
                               "lag_hours": LAG_HOURS, "z_window": Z_WINDOW_H},
                              f"EIA-930 {reg} demand above the day-ahead forecast is unplanned "
                              f"load; it conditions {sym}",
                              f"eia930 {reg} surprise ({t} {thr}) -> {sym}",
                              {"source_row": SOURCE_ID, "series": src, "arm": "direct"})
                c.update({"symbols": [sym], "available_time": stamp, "event_time": stamp,
                          "source_culture": "US/en", "participant_structure": "physical_flow",
                          "failure_mode_hypothesis": (
                              "fails when the operators' own forecasts already carry the weather "
                              "the gas market priced, or when hydro/wind/solar, not gas, fills "
                              "the gap"),
                          "crowding_prior": "low", "credential_var": KEY_ENV,
                          "required_data": [f"desks/mt5/data/lake/series/{src}.csv"],
                          "falsifier": (f"{src} {t} beyond {thr} sd carries no out-of-sample "
                                        f"information about {sym} H1 returns")})
                cells.append(c)
    return cells, skipped


# -------------------------------------------------------------------------------- the pass
def _resolve_key(environ: Mapping[str, str] | None) -> str:
    from keyed_sources import Blocked, resolve_keys
    try:
        return str(resolve_keys({"key_env": [KEY_ENV]}, environ)[KEY_ENV])
    except Blocked as b:
        raise Refused(str(b)) from None


def collect(paths: Paths, state: dict[str, Any], store: dict[str, dict[str, Any]], *,
            get: Getter, now: datetime, environ: Mapping[str, str] | None,
            sleep: Callable[[float], None]) -> dict[str, Any]:
    """One fetch: gates, metadata, data, merge. Returns the record; raises Refused by name."""
    stop = state.get("hard_stop") or {}
    until = _t(stop.get("until"))
    if stop.get("code") == 451 or (until and until > now):
        raise Refused(f"HARD_STOP:{stop.get('code')} (held since {stop.get('at')})")
    refused = access_refusal(get)
    if refused:
        raise Refused(refused)
    key = _resolve_key(environ)
    client = Client(get, key, sleep=sleep)
    rec: dict[str, Any] = {}
    try:
        meta = state.get("metadata") or {}
        verified = _t(meta.get("verified_at"))
        if not verified or (now - verified) > timedelta(hours=METADATA_TTL_H):
            meta = {**verify_metadata(client), "verified_at": _iso(now)}
            state["metadata"] = meta
        regions = list(meta.get("regions") or [])
        rec["missing_regions"] = meta.get("missing_regions") or []
        backfill = not state.get("last_success")
        start = now - (timedelta(days=BACKFILL_DAYS) if backfill else timedelta(hours=REPULL_H))
        rows, complete = pull(client, regions, start)
        rec.update(merge(paths, store, rows, now, backfill), parsed=len(rows),
                   status="OK" if rows else "EMPTY", backfill=backfill, complete=complete)
        if complete:
            state["last_success"] = _iso(now)
    except Refused as r:
        if str(r).startswith("HARD_STOP:"):
            code = int(str(r).split(":", 1)[1])
            state["hard_stop"] = {"code": code, "at": _iso(now),
                                  "until": None if code == 451
                                  else _iso(now + timedelta(hours=HARD_STOP_H))}
        if str(r).startswith("METADATA_MISMATCH"):
            state.pop("metadata", None)
        raise
    finally:
        rec["requests"] = client.requests
        state["last_requests"] = client.requests
    return rec


def run(paths: Paths = Paths(), *, fetch: bool = True, dry_run: bool = False,
        get: Getter | None = None, now: datetime | None = None,
        environ: Mapping[str, str] | None = None, sleep: Callable[[float], None] = time.sleep,
        donate: Callable[[str, list[dict[str, Any]], int], dict[str, Any]] | None = None
        ) -> dict[str, Any]:
    now = now or _now()
    t0 = time.monotonic()
    state = _read(paths.state, {}) or {}
    store = load_store(paths)
    rec: dict[str, Any] = {}
    if not fetch:
        status = "NO_FETCH"
    else:
        state["last_attempt"] = _iso(now)
        getter = get or http_get
        try:
            rec = collect(paths, state, store, get=getter, now=now, environ=environ,
                          sleep=sleep)
            status = str(rec.get("status"))
        except Refused as r:
            status = str(r).split(":", 1)[0]
            rec["why"] = str(r)
            rec["missed_growth"] = MISSED_GROWTH["blocked"]
        if not dry_run:
            _atomic(paths.state, state)
    series = surprise_series(store)
    latest = latest_surprise(series, now)
    lake = [] if dry_run else write_lake(paths, series)
    trigger = build_trigger(latest, now, source_status=status)
    cells, skipped = build_cells(paths, series, now)
    from keyed_sources import PER_PASS, _donate, _ring
    take, nxt = _ring(cells, int(state.get("cell_cursor") or 0), PER_PASS)
    don: dict[str, Any] = {"donated": 0}
    if not dry_run:
        don = (donate or _donate)(SEAT, take, len(take))
        state["cell_cursor"] = nxt
        _atomic(paths.state, state)
        _atomic(paths.trigger, trigger)
    doc = {"generated_at": _iso(now), "writer": "research/eia930_grid.py",
           "source": SOURCE_ID, "terms": TERMS_EVIDENCE, "status": status, "fetch": rec,
           "store_rows": len(store), "lake": lake,
           "regions": {reg: latest.get(reg, {"status": UNMEASURED}) for reg in REGIONS},
           "trigger": {"z_star": trigger["rule"]["z_star"], "n_flags": trigger["n_flags"]},
           "cells": {"grid": len(cells), "built": len(take),
                     "minted": int(don.get("donated") or 0),
                     "trials_charged": 0 if dry_run else len(take), "skipped": skipped,
                     "donation": don},
           "mode": "DRY_RUN" if dry_run else "RAN",
           "seconds": round(time.monotonic() - t0, 1)}
    if not dry_run:
        _atomic(paths.report, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=240.0,
                    help="accepted for the leg contract; the request budget bounds the pass")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(fetch=not a.no_fetch, dry_run=a.dry_run)
    print(json.dumps({"status": doc["status"], "store_rows": doc["store_rows"],
                      "trigger": doc["trigger"], "cells": {k: doc["cells"][k] for k in
                                                          ("grid", "built", "minted")}},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
