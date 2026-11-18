#!/usr/bin/env python3
"""SEC FAILS-TO-DELIVER SQUEEZE STATE -- a point-in-time state per US share CFD, EVENT LANE ONLY.

    python desks/mt5/research/sec_ftd_squeeze.py --once [--budget-s 240] [--dry-run] [--offline]

THE SOURCE. The SEC publishes, twice a month, every security's aggregate fails-to-deliver balance
at NSCC per settlement date (`cnsfailsYYYYMM{a,b}.zip`: `a` = settlement days 1-15, `b` = 16 to
month end). It is a US-government work, in the public domain, free with no login; the SEC's
fair-access policy asks for a declared User-Agent naming a contact and at most 10 requests a
second. The UA is the desk's EDGAR contact string, read through `alpha_capture.edgar_ua` (which
reads EDGAR_UA and its aliases through `libs.ops.env_keys.read_key`) and NEVER logged, printed or
written. With no UA set the organ makes no request at all, robots.txt included, and reports
BLOCKED_ON_CONTACT with its missed growth.

HONEST ACCESS. `libs.data.off_limits` first; then robots.txt for www.sec.gov, read under the SAME
User-Agent the file requests send (L0221) and checked for the exact file path (L0187). Only a 404
or 410 means "no rules"; a 5xx, an HTML body or any other failure refuses the pass (L0211). One
request per ~1.1 s through `polite_fetch.GATE`. A 403/429 stops the pass.

POINT IN TIME -- THE PUBLICATION DATE, NEVER THE SETTLEMENT DATE. A file about settlement days
1-15 of October is not knowable on the 15th; it is knowable when the SEC posted it, typically two
weeks later. Every row is stamped `available_time` = the file's HTTP Last-Modified instant
(`pit_basis: last_modified`) or, when the server sends none or one earlier than the period's own
last settlement day, the instant THIS desk first held it (`pit_basis: first_seen`) -- later than
the truth, never earlier. Every derived number on a row reads only files whose `available_time`
is at or before that row's, so a state cannot see a file that was not yet out.

THE STATE, per (share CFD, file). A symbol with no line in a file it was looked for in is a
MEASURED ZERO for each settlement day of that file (L0085), not a missing row.

    fails_mean / fails_max / fails_last   shares failed, over the file's settlement days
    ftd_value_usd_max                     max(fails x the file's own price column)
    persistence_days                      consecutive settlement days with fails > 0 ending at
                                          the file's last day, across contiguous held files
    threshold_streak_days / regsho_proxy  the same streak at >= 10,000 shares; >= 5 days is the
                                          Reg SHO threshold's share-count and duration legs. The
                                          0.5%-of-shares-outstanding leg is NOT measured, so it
                                          is labelled a proxy and never called the list
    surprise_z                            log1p(fails_mean) against the symbol's own earlier
                                          files (>= MIN_HISTORY of them, else NaN = UNMEASURED)
    state                                 SQUEEZE_WATCH | ELEVATED | NORMAL | UNMEASURED

THE LANE (CLAUDE.md "TWO LANES"; `universe_policy`). Single-name share CFDs never mint
statistical hypotheses. This organ mints nothing, donates nothing and never writes under
`data/intelligence/**` (the compiler's intake) or `data/lake/series/` (which `universal_gate`
globs for exogenous conditioners on every instrument). It writes the EVENT LANE's own door:

    data/event_lane/sec_ftd/series/secftd_<symbol>.parquet  one PIT series per share CFD, with
        `available_time`, `event_time` and `surprise_z` -- the exact shape the event lane's
        executor `mt5desk.family_alt_release.releases()` reads (pass `series_root` = this dir)
    data/event_lane/sec_ftd/squeeze_state.json              the newest state per share CFD
    reports/SEC_FTD_SQUEEZE.json                             the pass report

Only symbols `universe_policy.is_equity` admits (the broker registry's own class) and that map to
a US listing in `alpha_capture.TICKERS` are built; every other registry equity is listed as set
aside, with the reason. Nothing here sizes, caps or vetoes anything.

LIVE YIELD IS UNMEASURED UNTIL A BOX WITH THE UA RUNS IT: the build container's egress refuses
www.sec.gov. The parser and the PIT logic are proven offline on recorded-shape fixtures.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE = "sec_ftd_squeeze"
LANE = "event"
CACHE = DESK / "data" / "sec_ftd"
PERIODS = CACHE / "periods"
FETCH_STATE = CACHE / "fetch_state.json"
EVENT_DIR = DESK / "data" / "event_lane" / "sec_ftd"
SERIES_DIR = EVENT_DIR / "series"
STATE_OUT = EVENT_DIR / "squeeze_state.json"
REPORT = DESK / "reports" / "SEC_FTD_SQUEEZE.json"

HOST = "https://www.sec.gov"
FILE_URL = HOST + "/files/data/fails-deliver-data/cnsfails{period}.zip"
TERMS = {"terms": "confirmed", "checked_at": "2026-11-18",
         "url": "https://www.sec.gov/os/accessing-edgar-data",
         "quote": "SEC data is a US-government work in the public domain; 'Anyone can access "
                  "and download this information for free.' Fair access: a declared "
                  "User-Agent and at most 10 requests/second"}

HISTORY_PERIODS = 48          # two years of half-months held
MIN_HISTORY = 6               # earlier files a z needs
MIN_AGE_DAYS = 7              # a period this fresh cannot have been published yet
RETRY_HOURS = 12.0            # a 404 (not yet published) is re-probed after this
MAX_FETCH_PER_PASS = 6
MAX_ZIP_BYTES = 60_000_000
THRESHOLD_SHARES = 10_000     # Reg SHO threshold: share-count leg
THRESHOLD_DAYS = 5            # Reg SHO threshold: five consecutive settlement days
STALE_DAYS = 45
UNMEASURED = "UNMEASURED"
RULE = ("a fails-to-deliver squeeze state per US share CFD, stamped at the SEC file's "
        "publication instant; event lane only -- it mints no hypothesis, donates nothing, "
        "and sizes, caps or vetoes nothing")
MISSED_GROWTH = ("no squeeze state for the event lane's share CFDs until the SEC contact "
                 "User-Agent is set (EDGAR_UA / QUANT_EDGAR_UA, machine scope)")


# ============================================================================= periods
def period_id(year: int, month: int, half: str) -> str:
    return f"{year:04d}{month:02d}{half}"


def period_bounds(pid: str) -> tuple[date, date]:
    y, m, half = int(pid[:4]), int(pid[4:6]), pid[6]
    if half == "a":
        return date(y, m, 1), date(y, m, 15)
    nxt = date(y + (m == 12), m % 12 + 1, 1)
    return date(y, m, 16), nxt - timedelta(days=1)


def previous_period(pid: str) -> str:
    y, m, half = int(pid[:4]), int(pid[4:6]), pid[6]
    if half == "b":
        return period_id(y, m, "a")
    return period_id(y - (m == 1), (m - 2) % 12 + 1, "b")


def candidate_periods(today: date, n: int = HISTORY_PERIODS) -> list[str]:
    """Newest first: every half-month whose last day is at least MIN_AGE_DAYS old, n of them."""
    y, m = today.year, today.month
    pid = period_id(y, m, "b")
    out: list[str] = []
    while len(out) < n:
        if period_bounds(pid)[1] <= today - timedelta(days=MIN_AGE_DAYS):
            out.append(pid)
        pid = previous_period(pid)
    return out


# ============================================================================= instruments
def _norm_ticker(t: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(t).upper())


def event_lane_symbols() -> tuple[dict[str, str], list[dict[str, str]]]:
    """({MT5 share CFD: normalised US ticker}, [set-aside rows]). Admission is the broker
    registry's own class via `universe_policy.is_equity`; the ticker is alpha_capture's table."""
    from research import universe_policy as up
    from research.alpha_capture import TICKERS
    out: dict[str, str] = {}
    aside: list[dict[str, str]] = []
    for sym, tick in TICKERS.items():
        if up.is_equity(sym) and up.lane(sym) == up.EVENT:
            out[sym] = _norm_ticker(tick)
        else:
            aside.append({"symbol": sym, "why": f"not an event-lane equity in the registry "
                                                f"(lane={up.lane(sym)})"})
    mapped = {s.upper() for s in TICKERS}
    for key, row in sorted(up._registry().items()):
        if up.is_equity(key) and key not in mapped:
            aside.append({"symbol": str(row.get("symbol") or key),
                          "why": "registry equity with no mapped US listing"})
    return out, aside


# ============================================================================= parsing
def parse_ftd_lines(lines: Iterable[str], tickers: Iterable[str]
                    ) -> tuple[list[str], dict[str, dict[str, list[float | None]]], int, int]:
    """(settlement days, {ticker: {YYYYMMDD: [fails, price]}}, rows read, rows skipped).

    The file is pipe-delimited: SETTLEMENT DATE|CUSIP|SYMBOL|QUANTITY (FAILS)|DESCRIPTION|PRICE.
    The header and trailer, and any line whose date or quantity does not parse, are skipped and
    COUNTED. Two CUSIPs under one symbol sum. The settlement days are the file's own (every
    symbol), so a wanted ticker absent on a day is a measured zero there."""
    want = {_norm_ticker(t) for t in tickers}
    days: set[str] = set()
    rows: dict[str, dict[str, list[float | None]]] = {}
    read = skipped = 0
    for raw in lines:
        parts = raw.rstrip("\r\n").split("|")
        if len(parts) < 4 or not re.fullmatch(r"\d{8}", parts[0].strip()):
            skipped += 1
            continue
        try:
            qty = float(parts[3].strip())
        except ValueError:
            skipped += 1
            continue
        read += 1
        d = parts[0].strip()
        days.add(d)
        t = _norm_ticker(parts[2])
        if t not in want:
            continue
        try:
            px = float(parts[5].strip()) if len(parts) > 5 else math.nan
        except ValueError:
            px = math.nan
        cell = rows.setdefault(t, {}).setdefault(d, [0.0, None])
        cell[0] = float(cell[0] or 0.0) + qty
        if math.isfinite(px):
            cell[1] = px
    return sorted(days), rows, read, skipped


def parse_zip(raw: bytes, tickers: Iterable[str]) -> tuple[list[str], dict[str, Any], int, int]:
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        if not names:
            raise ValueError("empty archive")
        with zf.open(names[0]) as fh:
            text = io.TextIOWrapper(fh, encoding="latin-1", newline="")
            return parse_ftd_lines(text, tickers)


# ============================================================================= fetching
@dataclass
class Fetched:
    status: int | None = None
    body: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)
    error: str = ""


Fetcher = Callable[[str, Mapping[str, str], float], Fetched]


def default_fetch(url: str, headers: Mapping[str, str], deadline: float) -> Fetched:
    """One GET, binary, no retry. Refuses off-limits hosts and off-limits redirects. The UA is
    in `headers` and is never put into the returned error."""
    from libs.data.off_limits import off_limits, redirected_off_limits
    from libs.data.polite_fetch import GATE, ssl_context
    refused = off_limits(url)
    if refused:
        return Fetched(error=refused)
    GATE.wait(urllib.parse.urlsplit(url).netloc.lower())
    timeout = max(1.0, min(60.0, deadline - time.monotonic()))
    try:
        req = urllib.request.Request(url, headers=dict(headers))
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as fh:
            hop = redirected_off_limits(url, str(getattr(fh, "url", "") or url))
            if hop:
                return Fetched(error=hop)
            body = fh.read(MAX_ZIP_BYTES + 1)
            hdrs = {k.lower(): v for k, v in fh.headers.items()}
            return Fetched(status=int(getattr(fh, "status", 200) or 200), body=body,
                           headers=hdrs)
    except urllib.error.HTTPError as exc:
        try:
            return Fetched(status=int(exc.code), error=f"HTTP {exc.code}")
        finally:
            exc.close()
    except Exception as exc:  # transport: reported, never raised
        return Fetched(error=type(exc).__name__)


def robots_refusal(fetch: Fetcher, ua: str, url: str, deadline: float) -> str | None:
    """None when robots.txt lets THIS agent fetch `url`'s exact path, else why not. Fail closed:
    only 404/410 means no rules."""
    import urllib.robotparser
    got = fetch(HOST + "/robots.txt", {"User-Agent": ua, "Accept": "text/plain"}, deadline)
    if got.status in (404, 410):
        return None
    if got.status is None or not 200 <= got.status < 300:
        return f"ROBOTS_REFUSED: robots.txt {got.error or got.status}"
    body = got.body.decode("utf-8", "replace")
    if body.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
        return "ROBOTS_REFUSED: robots.txt answered HTML"
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(body.splitlines())
    path = urllib.parse.urlsplit(url).path
    return None if rp.can_fetch(ua, url) else f"ROBOTS_REFUSED: robots.txt disallows {path}"


def publication_stamp(headers: Mapping[str, str], pid: str, first_seen: datetime
                      ) -> tuple[datetime, str]:
    """(available_time, basis). Last-Modified when it is a real instant after the period's last
    settlement day; otherwise the instant this desk first held the file (later, never earlier)."""
    lm = headers.get("last-modified") or headers.get("Last-Modified")
    if lm:
        try:
            at = parsedate_to_datetime(str(lm))
            at = at.replace(tzinfo=UTC) if at.tzinfo is None else at.astimezone(UTC)
            end = period_bounds(pid)[1]
            if at.date() > end and at <= first_seen:
                return at, "last_modified"
        except (TypeError, ValueError, IndexError):
            pass
    return first_seen, "first_seen"


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).isoformat(timespec="seconds")


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str, allow_nan=False),
                   "utf-8")
    os.replace(tmp, path)


def collect(*, now: datetime, ua: str, tickers: Sequence[str], fetch: Fetcher,
            deadline: float, periods_dir: Path = PERIODS, state_path: Path = FETCH_STATE,
            max_fetch: int = MAX_FETCH_PER_PASS) -> dict[str, Any]:
    """Fetch the due, uncached half-month files (newest first) into the period cache."""
    rep: dict[str, Any] = {"attempted": 0, "fetched": [], "not_published": [], "errors": {}}
    if not ua:
        return {**rep, "status": "BLOCKED_ON_CONTACT", "missed_growth": MISSED_GROWTH,
                "why": "no EDGAR contact User-Agent set: the SEC fair-access policy requires "
                       "one, so nothing was requested (robots.txt included)"}
    state = _read_json(state_path, {})
    state = state if isinstance(state, dict) else {}
    due = []
    for pid in candidate_periods(now.date()):
        if (periods_dir / f"{pid}.json").exists():
            continue
        last = (state.get(pid) or {}).get("last_probe")
        try:
            if last and (now - datetime.fromisoformat(last)).total_seconds() < RETRY_HOURS * 3600:
                continue
        except ValueError:
            pass
        due.append(pid)
    rep["due"] = len(due)
    if not due:
        return {**rep, "status": "NOTHING_DUE"}
    refused = robots_refusal(fetch, ua, FILE_URL.format(period=due[0]), deadline)
    rep["attempted"] += 1
    if refused:
        return {**rep, "status": "ROBOTS_REFUSED", "why": refused}
    hdr = {"User-Agent": ua, "Accept": "application/zip", "Accept-Encoding": "identity"}
    status = "FETCHED"
    for pid in due[:max_fetch]:
        if time.monotonic() >= deadline:
            status = "BUDGET_SPENT"
            break
        url = FILE_URL.format(period=pid)
        got = fetch(url, hdr, deadline)
        rep["attempted"] += 1
        seen = now
        state[pid] = {"last_probe": _iso(now), "status": got.status, "error": got.error}
        if got.status in (403, 429):
            rep["errors"][pid] = got.error or str(got.status)
            status = "HARD_STOP"          # a refusal is never routed around
            break
        if got.status == 404:
            rep["not_published"].append(pid)
            continue
        if got.status is None or not 200 <= got.status < 300 or not got.body:
            rep["errors"][pid] = got.error or f"HTTP {got.status}"
            continue
        if len(got.body) > MAX_ZIP_BYTES:
            rep["errors"][pid] = "archive larger than the byte cap"
            continue
        try:
            days, rows, n_read, n_skip = parse_zip(got.body, tickers)
        except (zipfile.BadZipFile, ValueError, OSError) as exc:
            rep["errors"][pid] = f"unparseable archive ({type(exc).__name__})"
            continue
        if not days:
            rep["errors"][pid] = "archive held no dated rows"
            continue
        at, basis = publication_stamp(got.headers, pid, seen)
        _write_json(periods_dir / f"{pid}.json", {
            "period": pid, "url": url, "available_time": _iso(at), "pit_basis": basis,
            "first_seen_at": _iso(seen), "last_modified": got.headers.get("last-modified", ""),
            "settlement_days": days, "rows_read": n_read, "rows_skipped": n_skip,
            "tickers_wanted": len(set(tickers)), "rows": rows})
        rep["fetched"].append(pid)
    _write_json(state_path, state)
    return {**rep, "status": status}


# ============================================================================= the state
def load_periods(periods_dir: Path = PERIODS) -> list[dict[str, Any]]:
    out = []
    for p in sorted(periods_dir.glob("*.json")) if periods_dir.is_dir() else []:
        doc = _read_json(p, None)
        if isinstance(doc, dict) and doc.get("period") and doc.get("available_time"):
            out.append(doc)
    return out


def _cell(c: Any) -> tuple[float, float]:
    """(fails, price) of one held cell; an absent cell is a measured zero, an absent price NaN."""
    if not isinstance(c, (list, tuple)) or not c:
        return 0.0, math.nan
    px = c[1] if len(c) > 1 else None
    return float(c[0] or 0.0), (float(px) if px is not None else math.nan)


def _streak(seq: Sequence[float], floor: float) -> int:
    n = 0
    for v in reversed(seq):
        if v > floor:
            n += 1
        else:
            break
    return n


def label(z: float, persistence: int, regsho_proxy: bool) -> str:
    if not math.isfinite(z):
        return UNMEASURED
    if regsho_proxy or (z >= 2.0 and persistence >= THRESHOLD_DAYS):
        return "SQUEEZE_WATCH"
    if z >= 1.0:
        return "ELEVATED"
    return "NORMAL"


def build_states(periods: Sequence[Mapping[str, Any]], symbols: Mapping[str, str]
                 ) -> dict[str, list[dict[str, Any]]]:
    """{symbol: rows oldest first}. Each row reads ONLY files whose available_time is at or
    before its own file's -- the anti-lookahead rule, by construction."""
    docs = sorted(periods, key=lambda d: (str(d["available_time"]), str(d["period"])))
    by_pid = {str(d["period"]): d for d in docs}
    out: dict[str, list[dict[str, Any]]] = {s: [] for s in symbols}
    for doc in docs:
        pid, at = str(doc["period"]), str(doc["available_time"])
        knowable = {p: d for p, d in by_pid.items() if str(d["available_time"]) <= at}
        # the contiguous chain of knowable files ending at this one, oldest first
        chain = [pid]
        while previous_period(chain[0]) in knowable:
            chain.insert(0, previous_period(chain[0]))
        start = period_bounds(pid)[0]
        earlier = [d for p, d in knowable.items() if period_bounds(p)[1] < start]
        for sym, tick in symbols.items():
            def series(d: Mapping[str, Any], tick: str = tick) -> list[tuple[float, float]]:
                cells = (d.get("rows") or {}).get(tick) or {}
                return [_cell(cells.get(day)) for day in d.get("settlement_days") or []]
            own = series(doc)
            if not own:
                continue
            fails = [f for f, _ in own]
            mean = sum(fails) / len(fails)
            hist = []
            for d in earlier:
                fs = [f for f, _ in series(d)]
                if fs:
                    hist.append(math.log1p(sum(fs) / len(fs)))
            z = math.nan
            if len(hist) >= MIN_HISTORY:
                mu = sum(hist) / len(hist)
                sd = math.sqrt(sum((h - mu) ** 2 for h in hist) / (len(hist) - 1))
                if sd > 0:
                    z = (math.log1p(mean) - mu) / sd
            path = [f for p in chain for f, _ in series(knowable[p])]
            persistence = _streak(path, 0.0)
            thr = _streak(path, THRESHOLD_SHARES - 1e-9)
            values = [f * px for f, px in own if math.isfinite(px)]
            lo, hi = period_bounds(pid)
            out[sym].append({
                "symbol": sym, "ticker": tick, "lane": LANE, "event_time": pid,
                "settlement_from": lo.isoformat(), "settlement_to": hi.isoformat(),
                "available_time": at, "pit_basis": str(doc.get("pit_basis") or ""),
                "fails_mean": mean, "fails_max": max(fails), "fails_last": fails[-1],
                "ftd_value_usd_max": max(values) if values else math.nan,
                "persistence_days": persistence, "threshold_streak_days": thr,
                "regsho_proxy": thr >= THRESHOLD_DAYS, "history_files": len(hist),
                "surprise_z": z, "state": label(z, persistence, thr >= THRESHOLD_DAYS)})
    return out


def series_id(symbol: str) -> str:
    return "secftd_" + re.sub(r"[^A-Za-z0-9]", "_", symbol)


def write_series(states: Mapping[str, Sequence[Mapping[str, Any]]], series_dir: Path = SERIES_DIR
                 ) -> dict[str, str]:
    import pandas as pd
    series_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}
    for sym, rows in states.items():
        if not rows:
            continue
        df = pd.DataFrame(list(rows))
        df["available_time"] = pd.to_datetime(df["available_time"], utc=True)
        path = series_dir / f"{series_id(sym)}.parquet"
        tmp = path.with_suffix(".parquet.tmp")
        df.to_parquet(tmp, index=False)
        os.replace(tmp, path)
        written[sym] = series_id(sym)
    return written


def _finite(v: Any) -> Any:
    return None if isinstance(v, float) and not math.isfinite(v) else v


def current_state(states: Mapping[str, Sequence[Mapping[str, Any]]], now: datetime
                  ) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for sym, rows in states.items():
        if not rows:
            out[sym] = {"state": UNMEASURED, "why": "no held SEC file"}
            continue
        last = dict(rows[-1])
        age = (now - datetime.fromisoformat(str(last["available_time"]))).days
        last["stale"] = age > STALE_DAYS
        out[sym] = {k: _finite(v) for k, v in last.items()}
    return out


# ============================================================================= one pass
def run_once(*, now: datetime | None = None, budget_s: float = 240.0, dry_run: bool = False,
             offline: bool = False, fetch: Fetcher | None = None, ua: str | None = None,
             symbols: Mapping[str, str] | None = None, aside: list[dict[str, str]] | None = None,
             periods_dir: Path = PERIODS, state_path: Path = FETCH_STATE,
             series_dir: Path = SERIES_DIR, state_out: Path = STATE_OUT,
             report_path: Path = REPORT) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    deadline = time.monotonic() + max(5.0, budget_s - 10.0)
    if symbols is None:
        symbols, aside = event_lane_symbols()
    aside = aside or []
    if offline:
        fetched: dict[str, Any] = {"status": "OFFLINE", "attempted": 0}
    else:
        if ua is None:
            from research.alpha_capture import edgar_ua
            ua = edgar_ua()
        fetched = collect(now=now, ua=ua, tickers=list(symbols.values()),
                          fetch=fetch or default_fetch, deadline=deadline,
                          periods_dir=periods_dir, state_path=state_path)
    periods = load_periods(periods_dir)
    states = build_states(periods, symbols)
    current = current_state(states, now)
    counts: dict[str, int] = {}
    for row in current.values():
        counts[row["state"]] = counts.get(row["state"], 0) + 1
    written: dict[str, str] = {}
    if not dry_run:
        written = write_series(states, series_dir)
        _write_json(state_out, {"generated_at": _iso(now), "lane": LANE, "rule": RULE,
                                "series_root": str(series_dir.relative_to(DESK))
                                if series_dir.is_relative_to(DESK) else str(series_dir),
                                "states": current})
    report = {
        "generated_at": _iso(now), "source": SOURCE, "lane": LANE, "rule": RULE,
        "terms": TERMS, "fetch": fetched, "dry_run": dry_run,
        "periods_held": sorted(str(p["period"]) for p in periods),
        "symbols_built": len(symbols), "symbols_set_aside": aside,
        "state_counts": counts if periods else {UNMEASURED: len(symbols)},
        "squeeze_watch": sorted(s for s, r in current.items() if r["state"] == "SQUEEZE_WATCH"),
        "series_written": len(written),
        "outputs": {"series_dir": "data/event_lane/sec_ftd/series",
                    "state": "data/event_lane/sec_ftd/squeeze_state.json",
                    "reader": "mt5desk.family_alt_release.releases(series_id, 'surprise_z', "
                              "root=series_dir) -- the event lane's executor"},
        "verdict": (UNMEASURED if not periods else "MEASURED"),
        "why_unmeasured": ("no SEC file is held yet: " + str(fetched.get("status")))
        if not periods else "",
    }
    _write_json(report_path, report)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args(argv)
    rep = run_once(budget_s=a.budget_s, dry_run=a.dry_run, offline=a.offline)
    print(json.dumps({"verdict": rep["verdict"], "fetch": rep["fetch"].get("status"),
                      "periods_held": len(rep["periods_held"]),
                      "state_counts": rep["state_counts"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
