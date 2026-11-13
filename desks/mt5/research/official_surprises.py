"""OFFICIAL-DATA SURPRISES -- scheduled public releases as point-in-time event states for MT5 cells.

WHAT WAS MISSING (wired ledger 2026-11-13, all state D, zero code hits on LIVE):

  N4  BoJ rinban surprise       each JGB purchase operation's offer size against the plan the BoJ
                                pre-announced for that maturity bucket, plus how much the market
                                tried to sell into it (bids / offer). Same-day state for USDJPY,
                                EURJPY, JP225.
  N6  TIC foreign-flow surprise monthly net foreign purchases of US long-term domestic securities
                                (TIC s1, Treasury) against their trailing 12-month median. Values
                                are kept AS FIRST SEEN (the file revises history), so the surprise
                                series accrues from the first read. State for USDJPY, EURUSD,
                                US500.
  N7  USDA export-sales surprise Thursday 08:30 ET net export sales for corn, wheat and soybeans
                                against their own trailing 4-week mean. Event state for the desk's
                                CORN, WHEAT, SOYBEAN CFDs.
  N8  EIA gas-storage surprise  Thursday 10:30 ET working-gas change against the 5-year average
                                change for the same week of the year. Event state for XNGUSD.
  GAP_MAP 68  Fed net liquidity  WALCL - TGA - RRP, weekly delta, published with the H.4.1 on
                                Thursday 16:30 ET. From the publishers, never FRED (terms-refused
                                2026-11-13): TGA from Treasury FiscalData (DTS), ON RRP from the NY
                                Fed Markets API, total assets from the Board's DDP once its series
                                URL is box-verified (until then the drain leg -(TGA + RRP) alone,
                                labelled). Distinct from macro_desk's liquidity z.
  GAP_MAP 64  USD funding stress  SOFR - EFFR (secured over unsecured: repo pressure) and SOFR
                                p99 - SOFR (the repo distribution's tail), NY Fed; and a CIP-basis
                                proxy: the broker's own overnight swap-implied differential minus
                                the overnight cash differential from the rates' publishers (SOFR,
                                ECB EUR STR). Distinct from row 52 (swap drift is the swap's own
                                change; this is its gap to cash).

HOW, end to end -- each stage leaves an artifact:

  1. ROWS, NEVER CODE. `research/official_surprises_sources.json` holds one row per release with
     its adapter, terms state, URLs, key env names, release clock and targets. A row whose terms
     are not OPEN is never fetched and is counted as a named gap with its reason.

  2. HONEST ACCESS. Every URL is checked against the host's robots.txt with our own User-Agent
     before any data request (an unreadable robots.txt is a NO); every request goes through
     `libs.data.polite_fetch` with retries off; 401/403/429/451 is a HARD STOP recorded in the
     futures-state `hard_stops` and never retried until released. A key is read from the
     environment by NAME and never written, printed or logged; a missing key is NEEDS_KEY.

  3. CATALOGUE BEFORE IDS. A series id or commodity code is used only after the source's own
     catalogue returned it (EIA route metadata, the FAS commodity list, the TIC file index). The
     catalogue read is saved under raw/ as the evidence; an id the catalogue does not carry makes
     the row UNMEASURED with the ids it did carry, never a guessed fetch.

  4. POINT IN TIME. Every frame carries `available_time` = the release instant in its own time
     zone plus a short grace, converted to UTC. Holiday weeks move a release LATER, never earlier
     (late stamping is safe; early is lookahead). Rows can carry an exact `calendar.releases`
     map and `calendar.windows` not-before dates (government shutdowns), like the CFTC calendar.
     The TIC release day is not in its file, so it is stamped at a conservative upper bound until
     the release-calendar leg supplies exact dates; that basis is written on every row.

  5. FEATURES. Few columns on purpose: every column mints cells and every cell is charged to the
     program's family-wise budget. Each event series carries `surprise` (actual minus its stated
     baseline) and `surprise_z` (against strictly EARLIER surprises only); state series add one
     level column. Event rows also land in `data/calendar_backfill/` so the event-reaction lane
     sees each release instant.

  6. CELLS. `collect()` returns (oid, frame, meta) to `futures_state.build_market_series`, which
     writes `data/lake/series/<oid>.parquet` and mints each (column x transform x target x chart)
     ONCE as an `exogenous_conditioner` candidate. The hourly `futures_state` leg is the clock.

    python desks/mt5/research/futures_state.py --once --dry-run   # this module runs inside it
    python desks/mt5/research/futures_state.py --once --offline   # features from held raw only
"""
from __future__ import annotations

import gzip
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from research import futures_state as fs  # noqa: E402

REGISTRY = _DESK / "research" / "official_surprises_sources.json"
RAW = fs.RAW / "official"
REPORT = _DESK / "reports" / "OFFICIAL_SURPRISES.json"
UA = "quant-research/1.0 (+https://github.com/kingdemond434-cpu/quant; official_surprises)"
LEG = "official_surprises"
MIN_EVENTS = 30
GRACE = pd.Timedelta(minutes=5)

Text = Callable[[str], str]


# ------------------------------------------------------------------------------ honest access

class Access:
    """One pass's network door: robots first, then a polite GET with our own UA, no retry.

    `text` is injected so tests (and `--offline`) never touch the network. Robots verdicts are
    cached per host for the pass; a refused host is never asked again this pass."""

    def __init__(self, text: Callable[[str, Mapping[str, str]], str] | None,
                 state: dict[str, Any], notes: list[dict[str, Any]],
                 deadline: float | None = None):
        self._text = text
        self.state = state
        self.notes = notes
        self.deadline = deadline
        self._robots: dict[str, Any] = {}

    @property
    def online(self) -> bool:
        return self._text is not None

    def _stopped(self, sid: str) -> bool:
        return sid in (self.state.get("hard_stops") or {})

    def allowed(self, url: str) -> bool:
        import urllib.robotparser
        p = urllib.parse.urlsplit(url)
        host = f"{p.scheme}://{p.netloc}"
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                assert self._text is not None
                rp.parse(self._text(f"{host}/robots.txt", {}).splitlines())
                self._robots[host] = rp
            except fs.FetchError as exc:
                # RFC 9309: a 4xx robots.txt (other than the hard stops) means no rules
                self._robots[host] = (exc.code is not None and 400 <= int(exc.code) < 500)
            except fs.HardStop:
                self._robots[host] = False
            except Exception:
                self._robots[host] = False
        v = self._robots[host]
        return v.can_fetch(UA, url) if hasattr(v, "can_fetch") else bool(v)

    def get(self, sid: str, url: str, headers: Mapping[str, str] | None = None) -> str | None:
        """The body, or None with the reason in notes. Never raises for a refusal."""
        if self._text is None or self._stopped(sid):
            return None
        if self.deadline is not None and time.monotonic() > self.deadline:
            self.notes.append({"source": sid, "status": "DEFERRED", "why": "fetch budget spent"})
            return None
        if not self.allowed(url):
            self.notes.append({"source": sid, "status": "UNMEASURED", "why": "robots disallows",
                               "url": _redact(url)})
            return None
        try:
            return self._text(url, headers or {})
        except fs.HardStop as hs:
            self.state.setdefault("hard_stops", {})[sid] = {"code": hs.code, "at": fs._now()}
            self.notes.append({"source": sid, "status": "HARD_STOP", "code": hs.code})
        except Exception as exc:
            self.notes.append({"source": sid, "error": type(exc).__name__,
                               "url": _redact(url)})
        return None

    def json(self, sid: str, url: str, headers: Mapping[str, str] | None = None) -> Any:
        body = self.get(sid, url, headers)
        if body is None:
            return None
        try:
            return json.loads(body)
        except ValueError:
            self.notes.append({"source": sid, "error": "not JSON", "url": _redact(url)})
            return None


def _redact(url: str) -> str:
    """A URL with every key-like query value replaced, so no note ever carries a key."""
    p = urllib.parse.urlsplit(url)
    q = [(k, "***" if re.search(r"key|token", k, re.I) else v)
         for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True)]
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, urllib.parse.urlencode(q), ""))


class _SameHostRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only within the host first asked: a URL may carry a key in its query,
    and a cross-host redirect would hand that key to a host nobody chose."""

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any,
                         newurl: str) -> Any:
        old_host = urllib.parse.urlsplit(req.full_url).netloc.lower()
        new_host = urllib.parse.urlsplit(urllib.parse.urljoin(req.full_url, newurl)).netloc.lower()
        if new_host != old_host:
            raise fs.FetchError(code, _redact(req.full_url), "cross-host redirect refused")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _opener(req: Any, timeout: float, context: Any = None) -> Any:
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=context),
                                       _SameHostRedirects()).open(req, timeout=timeout)


def polite_text(url: str, headers: Mapping[str, str]) -> str:
    from libs.data import polite_fetch
    r = polite_fetch.get(url, headers={"User-Agent": UA, "Accept": "*/*", **headers},
                         timeout=40.0, retries=0, leg=LEG, opener=_opener)
    if r.status in fs.HARD_STOP:
        raise fs.HardStop(int(r.status or 0), url)
    if not r.ok:
        raise fs.FetchError(r.status, _redact(url), "fetch failed")
    final = urllib.parse.urlsplit(r.final_url or url).netloc.lower()
    if final != urllib.parse.urlsplit(url).netloc.lower():
        raise fs.FetchError(r.status, _redact(url), "cross-host redirect refused")
    return r.text


def key_for(row: Mapping[str, Any]) -> str:
    """The first set env var named by the row. The VALUE never leaves this function's caller."""
    return next((os.environ[k] for k in row.get("key_env") or [] if os.environ.get(k)), "")


# ------------------------------------------------------------------------------ release clocks

def _holidays() -> frozenset[pd.Timestamp]:
    return fs._us_holidays()


def release_instant(days: pd.Series, at: str, tz: str,
                    calendar: Mapping[str, Any] | None = None,
                    holiday_shift: bool = True) -> pd.Series:
    """Scheduled release DAYS -> UTC instants at the local clock time plus grace.

    A release scheduled on a US federal holiday, or in a week where a holiday fell earlier the
    same week, moves one business day LATER (EIA, USDA and the H.4.1 all slip that way; when the
    agency actually published earlier the stamp is merely late, which is safe). Exact dates in
    `calendar.releases` (scheduled day ISO -> real day ISO) win; `calendar.windows` raise a
    not-before date for every scheduled day inside a shutdown window; a scheduled day inside
    `calendar.exclude` (a shutdown and its catch-up, when the real publication dates are not on
    record) yields NaT and the row is dropped rather than stamped on a day it was not public."""
    cal = calendar or {}
    hol = _holidays()
    hh, mm = (int(x) for x in str(at).split(":"))
    out: list[pd.Timestamp] = []
    for d in pd.to_datetime(days, errors="coerce"):
        if pd.isna(d):
            out.append(pd.NaT)
            continue
        day = pd.Timestamp(d).tz_localize(None).normalize()
        exact = (cal.get("releases") or {}).get(day.date().isoformat())
        if exact:
            day = pd.Timestamp(exact).normalize()
        elif holiday_shift:
            week0 = day - pd.Timedelta(days=day.weekday())
            if any(week0 <= h <= day for h in hol):
                day = day + pd.Timedelta(days=1)
                while day.weekday() >= 5 or day in hol:
                    day += pd.Timedelta(days=1)
        for w in cal.get("windows") or []:
            if pd.Timestamp(w["from"]) <= day <= pd.Timestamp(w["to"]):
                day = max(day, pd.Timestamp(w["not_before"]).normalize())
        if not exact and any(pd.Timestamp(w["from"]) <= day <= pd.Timestamp(w["to"])
                             for w in cal.get("exclude") or []):
            out.append(pd.NaT)          # publication date unknown (shutdown backlog): no row
            continue
        local = (day + pd.Timedelta(hours=hh, minutes=mm)).tz_localize(
            tz, nonexistent="shift_forward", ambiguous=False)
        out.append(local.tz_convert("UTC") + GRACE)
    return pd.Series(pd.to_datetime(out, utc=True), index=getattr(days, "index", None))


# ------------------------------------------------------------------------------ features (pure)

def surprise_frame(actual: pd.Series, baseline: pd.Series, window: int = 52) -> pd.DataFrame:
    """[surprise, surprise_z] per event. z uses strictly EARLIER surprises (shifted), so an event
    never scores against itself; under MIN_EVENTS // 2 prior events z is NaN, never a guess."""
    a = pd.to_numeric(actual, errors="coerce").reset_index(drop=True)
    b = pd.to_numeric(baseline, errors="coerce").reset_index(drop=True)
    s = a - b
    past = s.shift(1)
    mu = past.rolling(window, min_periods=MIN_EVENTS // 2).mean()
    sd = past.rolling(window, min_periods=MIN_EVENTS // 2).std(ddof=0)
    return pd.DataFrame({"surprise": s, "surprise_z": (s - mu) / sd.replace(0.0, np.nan)})


def trailing_mean(x: pd.Series, n: int) -> pd.Series:
    """Mean of the n PRIOR values (the release's own value excluded)."""
    return pd.to_numeric(x, errors="coerce").shift(1).rolling(n, min_periods=n).mean()


def trailing_median(x: pd.Series, n: int) -> pd.Series:
    return pd.to_numeric(x, errors="coerce").shift(1).rolling(n, min_periods=n).median()


def same_week_5y_mean(week_end: pd.Series, change: pd.Series, years: int = 5,
                      tol_days: int = 3) -> pd.Series:
    """EIA's own construction: for each report week, the mean change over the same calendar week
    of the PRIOR `years` years (the week whose end is within `tol_days` of the same day-of-year).
    Needs all `years` years present, else NaN -- a partial average is a different baseline."""
    we = pd.to_datetime(week_end).reset_index(drop=True)
    ch = pd.to_numeric(change, errors="coerce").reset_index(drop=True)
    by_day = dict(zip(we, ch, strict=False))
    keys = np.array(list(by_day.keys()), dtype="datetime64[ns]")
    out = []
    for d in we:
        vals = []
        for k in range(1, years + 1):
            try:
                tgt = d.replace(year=d.year - k)
            except ValueError:          # 29 Feb
                tgt = d.replace(year=d.year - k, day=28)
            gap = np.abs((keys - np.datetime64(tgt)).astype("timedelta64[D]").astype(int))
            j = int(gap.argmin()) if len(gap) else -1
            if j >= 0 and gap[j] <= tol_days:
                v = by_day[pd.Timestamp(keys[j])]
                if pd.notna(v):
                    vals.append(float(v))
        out.append(float(np.mean(vals)) if len(vals) == years else np.nan)
    return pd.Series(out)


# ------------------------------------------------------------------------------ calendar rows

def write_calendar(oid: str, row: Mapping[str, Any], instants: pd.Series, basis: str
                   ) -> Path | None:
    """Release instants for the event-reaction lane (outside data/intelligence on purpose: the
    candidate compiler would mint a cell per historical row there)."""
    t = pd.to_datetime(instants, utc=True).dropna()
    if t.empty:
        return None
    lines = [json.dumps({"event_date": (x - GRACE).isoformat(),
                         "currency": str(row.get("currency") or "USD"),
                         "country": str(row.get("country") or "USD"),
                         "title": str(row.get("title") or oid), "impact": "High",
                         "series": oid, "source": "official_surprises",
                         "instant_basis": basis, "backfill": True}, sort_keys=True)
             for x in t]
    fs.CALENDAR_BACKFILL.mkdir(parents=True, exist_ok=True)
    p = fs.CALENDAR_BACKFILL / f"backfill_{oid}.jsonl.gz"
    tmp = p.with_suffix(p.suffix + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    fs._replace(tmp, p)
    return p


def _hold(raw: Path, df: pd.DataFrame | None) -> pd.DataFrame:
    """Persist a fresh read; otherwise serve the last held read (the offline path)."""
    if df is not None and not df.empty:
        RAW.mkdir(parents=True, exist_ok=True)
        fs._atomic_parquet(raw, df, index=False)
        return df
    if raw.exists():
        return pd.read_parquet(raw)
    return pd.DataFrame()


def _evidence(name: str, doc: Any) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    fs._write(RAW / f"catalogue_{name}.json", {"read_utc": fs._now(), "doc": doc})


Out = tuple[str, pd.DataFrame, dict[str, Any]]


def _emit(oid: str, row: Mapping[str, Any], feat: pd.DataFrame, avail: pd.Series,
          event: pd.Series, kind: str, basis: str, extra: Mapping[str, Any] | None = None
          ) -> Out | None:
    ok = avail.notna().to_numpy() & feat.notna().any(axis=1).to_numpy()
    feat, avail, event = (feat[ok].reset_index(drop=True), avail[ok].reset_index(drop=True),
                          event[ok].reset_index(drop=True))
    if len(feat) < MIN_EVENTS:
        return None
    frame = fs.stamped(feat, avail, oid, event)
    if row.get("event_lane", True):
        try:
            first = ~pd.Series(pd.to_datetime(event)).duplicated(keep="first").to_numpy()
            write_calendar(oid, row, avail[first], basis)
        except OSError:
            pass
    meta = {"targets": list(row.get("targets") or []), "kind": kind, "rows": len(frame),
            "last_event": str(pd.to_datetime(event).max()), "why": str(row.get("why") or ""),
            "idea": row.get("idea"), "instant_basis": basis, **(extra or {})}
    return oid, frame, meta


# ------------------------------------------------------------------------- primary US publishers
#
# FRED is terms-refused for every automated desk fetch (governance/fred-terms-ruling-2026-11-13):
# its licence bars use in building a system. The same numbers come from their publishers:
#   NY Fed Markets API   SOFR (with its percentile distribution), EFFR, ON RRP take-up. Terms of
#                        use allow automated business use with attribution (NYFED_NOTICE).
#   Treasury FiscalData  Daily Treasury Statement operating cash balance (the TGA). US
#                        government work, public domain.
#   Federal Reserve      H.4.1 total assets via the Data Download Program CSV. The DDP series
#                        URL is a row field and is fetched only once `verified` is true (a box
#                        read of the DDP page); until then net liquidity carries only its
#                        Treasury + NY Fed legs and says so.

NYFED_NOTICE = ("Content from the New York Fed subject to the Terms of Use at newyorkfed.org "
                "(SOFR, EFFR, reverse repo operations)")
NYFED_RATE = ("https://markets.newyorkfed.org/api/rates/{path}/search.json?"
              "startDate={a}&endDate={b}")
NYFED_RRP = ("https://markets.newyorkfed.org/api/rp/reverserepo/propositions/search.json?"
             "startDate={a}&endDate={b}")
FISCAL_DTS = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/"
              "dts/operating_cash_balance?filter=record_date:gte:{a}&sort=record_date"
              "&page[size]=10000&page[number]={n}")


def _num(v: Any) -> float:
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return float("nan")


def _chunks(start: pd.Timestamp, end: pd.Timestamp, days: int = 365
            ) -> list[tuple[str, str]]:
    out, a = [], start.normalize()
    while a <= end:
        b = min(a + pd.Timedelta(days=days - 1), end)
        out.append((a.date().isoformat(), b.date().isoformat()))
        a = b + pd.Timedelta(days=1)
    return out


def _incremental(raw: Path, first: str, now: pd.Timestamp, overlap_days: int = 10
                 ) -> tuple[pd.DataFrame, pd.Timestamp]:
    held = pd.read_parquet(raw) if raw.exists() else pd.DataFrame()
    start = pd.Timestamp(first)
    if not held.empty:
        start = max(start, pd.to_datetime(held["date"]).max() - pd.Timedelta(days=overlap_days))
    return held, start


def _merge(held: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    if new.empty:
        return held
    df = pd.concat([held, new], ignore_index=True) if not held.empty else new
    df["date"] = pd.to_datetime(df["date"])
    return df.drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)


def nyfed_rate_rows(doc: Any) -> pd.DataFrame:
    """refRates -> [date, rate, p1, p25, p75, p99, volume_bn]."""
    recs = (doc or {}).get("refRates") if isinstance(doc, dict) else None
    rows = [{"date": str(r.get("effectiveDate") or "")[:10], "rate": _num(r.get("percentRate")),
             "p1": _num(r.get("percentPercentile1")), "p25": _num(r.get("percentPercentile25")),
             "p75": _num(r.get("percentPercentile75")),
             "p99": _num(r.get("percentPercentile99")),
             "volume_bn": _num(r.get("volumeInBillions"))}
            for r in recs or [] if isinstance(r, dict)]
    d = pd.DataFrame(rows)
    if d.empty:
        return d
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    return d.dropna(subset=["date", "rate"])


def nyfed_rrp_rows(doc: Any) -> pd.DataFrame:
    """ON RRP operations -> [date, rrp_bn] summed over the day's operations (dollars -> $bn)."""
    ops = (((doc or {}).get("repo") or {}).get("operations")) if isinstance(doc, dict) else None
    rows = [{"date": str(o.get("operationDate") or "")[:10],
             "rrp_bn": _num(o.get("totalAmtAccepted")) / 1e9}
            for o in ops or [] if isinstance(o, dict)]
    d = pd.DataFrame(rows)
    if d.empty:
        return d
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    return d.dropna().groupby("date", as_index=False)["rrp_bn"].sum()


def dts_tga_rows(doc: Any, pattern: str) -> pd.DataFrame:
    """DTS operating cash balance -> [date, tga_bn]. The account row is matched by its own label
    (the TGA closing balance since 2021-10, the Federal Reserve Account before); the balance is
    the closing field where the row has one, else the opening field (the newer format reports
    the TGA closing balance in the opening column of its own closing-balance row)."""
    rows = (doc or {}).get("data") if isinstance(doc, dict) else None
    pat = re.compile(pattern, re.I)
    out = []
    for r in rows or []:
        if not isinstance(r, dict) or not pat.search(str(r.get("account_type") or "")):
            continue
        v = _num(r.get("close_today_bal"))
        if not np.isfinite(v):
            v = _num(r.get("open_today_bal"))
        out.append({"date": str(r.get("record_date") or "")[:10], "tga_bn": v / 1000.0})
    d = pd.DataFrame(out)
    if d.empty:
        return d
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    return d.dropna().drop_duplicates("date", keep="last")


def fed_ddp_rows(text: str) -> pd.DataFrame:
    """A Federal Reserve Data Download Program CSV -> [date, value] scaled by its Multiplier
    row. The data start after the 'Time Period' header row; 'ND' / blank is absent."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    mult, start = 1.0, None
    for i, ln in enumerate(lines[:20]):
        cells = [c.strip().strip('"') for c in ln.split(",")]
        if cells and cells[0].lower().startswith("multiplier") and len(cells) > 1:
            mult = _num(cells[1]) if np.isfinite(_num(cells[1])) else 1.0
        if cells and cells[0].lower().startswith("time period"):
            start = i + 1
    if start is None:
        return pd.DataFrame(columns=["date", "value"])
    rows = []
    for ln in lines[start:]:
        cells = [c.strip().strip('"') for c in ln.split(",")]
        if len(cells) >= 2:
            rows.append({"date": cells[0], "value": _num(cells[1]) * mult})
    d = pd.DataFrame(rows)
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    return d.dropna()


def collect_nyfed_rate(acc: Access, row: Mapping[str, Any], path: str, name: str,
                       now: pd.Timestamp) -> pd.DataFrame:
    raw = RAW / f"{row['id']}_{name}.parquet"
    held, start = _incremental(raw, str(row.get("first_date") or "2018-04-02"), now)
    parts = []
    if acc.online:
        for a, b in _chunks(start, now):
            doc = acc.json(str(row["id"]), NYFED_RATE.format(path=path, a=a, b=b))
            if doc is None:
                break
            parts.append(nyfed_rate_rows(doc))
    new = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    df = _merge(held, new)
    return _hold(raw, df if not new.empty else None)


def collect_rrp(acc: Access, row: Mapping[str, Any], now: pd.Timestamp) -> pd.DataFrame:
    raw = RAW / f"{row['id']}_rrp.parquet"
    held, start = _incremental(raw, str(row.get("rrp_first_date") or "2014-01-01"), now)
    parts = []
    if acc.online:
        for a, b in _chunks(start, now):
            doc = acc.json(str(row["id"]), NYFED_RRP.format(a=a, b=b))
            if doc is None:
                break
            parts.append(nyfed_rrp_rows(doc))
    new = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    return _hold(raw, _merge(held, new) if not new.empty else None)


def collect_tga(acc: Access, row: Mapping[str, Any], now: pd.Timestamp) -> pd.DataFrame:
    raw = RAW / f"{row['id']}_tga.parquet"
    held, start = _incremental(raw, str(row.get("tga_first_date") or "2014-01-01"), now)
    parts = []
    if acc.online:
        for n in range(1, 20):
            doc = acc.json(str(row["id"]), FISCAL_DTS.format(a=start.date().isoformat(), n=n))
            if doc is None:
                break
            parts.append(dts_tga_rows(doc, str(row.get("tga_pattern") or "TGA|Federal Reserve")))
            if not ((doc or {}).get("links") or {}).get("next"):
                break
    new = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    return _hold(raw, _merge(held, new) if not new.empty else None)


def collect_walcl(acc: Access, row: Mapping[str, Any]) -> pd.DataFrame:
    """H.4.1 total assets from the Board's DDP, only once the row's URL is verified."""
    raw = RAW / f"{row['id']}_walcl.parquet"
    src = row.get("walcl") or {}
    fresh = None
    if acc.online and src.get("verified") and src.get("url"):
        body = acc.get(str(row["id"]), str(src["url"]))
        if body:
            fresh = fed_ddp_rows(body)
    elif acc.online:
        acc.notes.append({"source": f"{row['id']}_walcl", "status": "UNMEASURED",
                          "why": "H.4.1 DDP series URL not yet verified by a box read"})
    return _hold(raw, fresh)


def net_liquidity(walcl: pd.DataFrame, tga: pd.DataFrame, rrp: pd.DataFrame) -> pd.DataFrame:
    """Weekly Wednesday frame in $bn: net = WALCL - TGA - RRP when the H.4.1 leg is held, and
    always the Treasury + NY Fed drain leg `drain_bn` = -(TGA + RRP). TGA and RRP are taken AS OF
    each Wednesday (within 6 days), never imputed across a longer gap."""
    def asof(d: pd.DataFrame, col: str, idx: pd.DatetimeIndex) -> pd.Series:
        if d.empty:
            return pd.Series(np.nan, index=idx)
        s = pd.Series(d[col].to_numpy(), index=pd.to_datetime(d["date"])).sort_index()
        s = s[~s.index.duplicated(keep="last")]
        return s.reindex(idx, method="ffill", tolerance=pd.Timedelta(days=6))
    lo = min(pd.to_datetime(x["date"]).min() for x in (tga, rrp) if not x.empty)
    hi = max(pd.to_datetime(x["date"]).max() for x in (tga, rrp) if not x.empty)
    weds = pd.date_range(lo, hi, freq="W-WED")
    t, r = asof(tga, "tga_bn", weds), asof(rrp, "rrp_bn", weds)
    if not rrp.empty:                       # RRP history before the first operation is zero use
        r = r.where(weds >= pd.to_datetime(rrp["date"]).min(), r)
    out = pd.DataFrame({"week": weds, "drain_bn": (-(t + r)).to_numpy()})
    if not walcl.empty:
        w = asof(walcl.rename(columns={"value": "v"}), "v", weds) / 1000.0   # $mn -> $bn
        out["net_liq_bn"] = (w - t - r).to_numpy()
    out = out.dropna(subset=["drain_bn"]).reset_index(drop=True)
    for c in [c for c in ("net_liq_bn", "drain_bn") if c in out.columns]:
        out[f"{c}_d1w"] = out[c].diff()
    return out


def collect_net_liquidity(acc: Access, row: Mapping[str, Any], now: datetime) -> list[Out]:
    t = pd.Timestamp(now).tz_localize(None) if pd.Timestamp(now).tzinfo else pd.Timestamp(now)
    tga, rrp, walcl = collect_tga(acc, row, t), collect_rrp(acc, row, t), collect_walcl(acc, row)
    if tga.empty or rrp.empty:
        return []
    w = net_liquidity(walcl, tga, rrp)
    head = "net_liq_bn" if "net_liq_bn" in w.columns and w["net_liq_bn"].notna().sum() >= \
        MIN_EVENTS else "drain_bn"
    z = surprise_frame(w[f"{head}_d1w"], pd.Series(0.0, index=w.index),
                       int(row.get("window", 52)))["surprise_z"]
    feat = pd.DataFrame({head: w[head], "d1w": w[f"{head}_d1w"], "d1w_z": z})
    rel_day = pd.to_datetime(w["week"]) + pd.Timedelta(days=1)          # H.4.1: Thursday
    avail = release_instant(rel_day, str(row.get("at") or "16:30"), str(row["tz"]),
                            row.get("calendar"))
    out = _emit(f"os_{row['id']}", row, feat, avail, pd.Series(pd.to_datetime(w["week"])),
                "fed_net_liquidity", "h41_thursday_1630_et_holiday_late",
                {"basis": head, "attribution": NYFED_NOTICE,
                 "legs": {"tga": "fiscaldata_dts", "rrp": "nyfed_markets_api",
                          "walcl": "fed_ddp" if head == "net_liq_bn" else "UNMEASURED"}})
    return [out] if out else []


def collect_funding(acc: Access, row: Mapping[str, Any], now: datetime) -> list[Out]:
    """SOFR - EFFR (secured over unsecured overnight: repo pressure) and SOFR p99 - SOFR (the
    tail of the repo distribution: who is paying up), both in bp from the NY Fed, stamped the
    next business day 23:00 UTC (published ~08:00 ET the business day after)."""
    t = pd.Timestamp(now).tz_localize(None) if pd.Timestamp(now).tzinfo else pd.Timestamp(now)
    sofr = collect_nyfed_rate(acc, row, "secured/sofr", "sofr", t)
    effr = collect_nyfed_rate(acc, row, "unsecured/effr", "effr", t)
    if sofr.empty:
        return []
    so = sofr.set_index(pd.to_datetime(sofr["date"])).sort_index()
    legs = {"sofr_effr": so["rate"] - (effr.set_index(pd.to_datetime(effr["date"]))["rate"]
                                       .reindex(so.index) if not effr.empty else np.nan),
            "sofr_tail": so["p99"] - so["rate"]}
    outs: list[Out] = []
    for sid, ser in legs.items():
        s = (pd.Series(ser) * 100.0).dropna()
        if len(s) < fs.MIN_ROWS:
            continue
        feat = fs.dynamics(pd.DataFrame({"bp": s.to_numpy()}), ["bp"],
                           window=int(row.get("window", 252)))[["bp", "bp_chg", "bp_pct"]]
        avail = fs.daily_available(pd.Series(s.index))
        out = _emit(f"os_{row['id']}_{sid}", {**row, "event_lane": False}, feat, avail,
                    pd.Series(s.index), "usd_funding_spread", "nyfed_next_bday_2300utc",
                    {"attribution": NYFED_NOTICE})
        if out:
            outs.append(out)
    return outs


# ------------------------------------------------------------------------------ CIP basis proxy

def swap_implied_diff(swap_points: float, price: float, digits: int, side: str) -> float:
    """Annualised % rate differential implied by an MT5 swap in POINTS per lot per night.

    A points swap is (forward - spot) per night in the quote's smallest unit, so the implied
    base-minus-quote differential is points * 10**-digits / price * 365 * 100, sign by side
    (long earns base, pays quote). A broker's markup sits inside the swap on both sides, so the
    MID of long and short (computed by the caller) is the differential and half their spread is
    the broker's take."""
    v = swap_points * (10.0 ** -digits) / price * 365.0 * 100.0
    return v if side == "long" else -v


ECB_ESTR = ("https://data-api.ecb.europa.eu/service/data/EST/{key}?format=csvdata"
            "&startPeriod={a}")


def ecb_csv_rows(text: str) -> pd.DataFrame:
    """ECB Data Portal csvdata -> [date, rate] from its TIME_PERIOD and OBS_VALUE columns."""
    try:
        d = pd.read_csv(io.StringIO(text))
    except Exception:
        return pd.DataFrame(columns=["date", "rate"])
    if not {"TIME_PERIOD", "OBS_VALUE"} <= set(d.columns):
        return pd.DataFrame(columns=["date", "rate"])
    out = pd.DataFrame({"date": pd.to_datetime(d["TIME_PERIOD"], errors="coerce"),
                        "rate": pd.to_numeric(d["OBS_VALUE"], errors="coerce")})
    return out.dropna().sort_values("date").reset_index(drop=True)


def cash_leg(acc: Access, row: Mapping[str, Any], leg: Mapping[str, Any],
             now: pd.Timestamp) -> pd.Series:
    """One overnight rate from its own publisher, indexed by the day it was PUBLIC
    (next business day: SOFR and EUR STR are both published the morning after)."""
    prov = str(leg.get("provider"))
    if prov == "nyfed":
        df = collect_nyfed_rate(acc, row, str(leg["path"]), str(leg["name"]), now)
    elif prov == "ecb":
        raw = RAW / f"{row['id']}_{leg['name']}.parquet"
        held, start = _incremental(raw, str(leg.get("first_date") or "2019-10-01"), now)
        fresh = None
        if acc.online:
            body = acc.get(str(row["id"]), ECB_ESTR.format(key=leg["key"],
                                                           a=start.date().isoformat()))
            if body:
                fresh = _merge(held, ecb_csv_rows(body))
        df = _hold(raw, fresh)
    else:
        acc.notes.append({"source": row["id"], "status": "UNMEASURED",
                          "why": f"no primary route for provider {prov}"})
        return pd.Series(dtype=float)
    if df.empty:
        return pd.Series(dtype=float)
    s = pd.Series(df["rate"].to_numpy(), index=pd.to_datetime(df["date"])).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    s.index = fs.daily_available(pd.Series(s.index)).to_numpy()
    return s


def collect_cip(acc: Access, row: Mapping[str, Any], swaps: pd.DataFrame | None,
                now: datetime) -> list[Out]:
    """Broker swap-implied overnight differential minus the overnight cash differential from
    the rates' own publishers (SOFR: NY Fed; EUR STR: ECB), per pair. A pair whose foreign
    overnight rate has no primary-publisher row is UNMEASURED by name.

    `swaps` is the broker swap panel (time, symbol, swap_long, swap_short, swap_mode, price,
    digits; price = the last COMPLETED bar's close at capture, true UTC). Only points-mode swaps
    are used. Cash is joined AS OF its public instant, never a later one."""
    if swaps is None or swaps.empty:
        acc.notes.append({"source": row["id"], "status": "UNMEASURED",
                          "why": "no broker swap panel held"})
        return []
    t = pd.Timestamp(now).tz_localize(None) if pd.Timestamp(now).tzinfo else pd.Timestamp(now)
    outs: list[Out] = []
    for pr in row.get("pairs") or []:
        sym = str(pr["symbol"])
        if not pr.get("base") or not pr.get("quote"):
            acc.notes.append({"source": f"{row['id']}_{sym}", "status": "UNMEASURED",
                              "why": "no primary-publisher overnight rate for one leg"})
            continue
        base, quote = cash_leg(acc, row, pr["base"], t), cash_leg(acc, row, pr["quote"], t)
        sw = swaps[(swaps["symbol"] == sym)]
        if "swap_mode" in sw.columns:
            sw = sw[sw["swap_mode"].astype(str).str.lower().isin(("points", "1", "by_points"))]
        if base.empty or quote.empty or sw.empty:
            acc.notes.append({"source": f"{row['id']}_{sym}", "status": "UNMEASURED",
                              "why": "cash leg or points-mode swaps missing"})
            continue
        sw = sw.dropna(subset=["swap_long", "swap_short", "price", "digits"]).copy()
        sw["t"] = pd.to_datetime(sw["time"], utc=True)
        sw = sw.set_index("t").sort_index()
        day = sw.resample("1D").last().dropna(subset=["price"])
        lng = [swap_implied_diff(r.swap_long, r.price, int(r.digits), "long")
               for r in day.itertuples()]
        sht = [swap_implied_diff(r.swap_short, r.price, int(r.digits), "short")
               for r in day.itertuples()]
        implied = pd.Series((np.array(lng) + np.array(sht)) / 2.0, index=day.index)
        take = pd.Series((np.array(sht) - np.array(lng)) / 2.0, index=day.index)
        # the swap day is usable at its end; cash only once published by then
        ends = implied.index + pd.Timedelta(hours=23, minutes=59)

        def asof(c: pd.Series, ends: pd.DatetimeIndex = ends) -> np.ndarray:
            c = c.copy()
            c.index = pd.to_datetime(c.index, utc=True)
            return np.asarray(c.reindex(c.index.union(ends)).ffill().reindex(ends), dtype=float)
        cash = asof(base) - asof(quote)
        basis = pd.Series(implied.to_numpy() - cash, index=implied.index).dropna()
        if len(basis) < fs.MIN_ROWS:
            acc.notes.append({"source": f"{row['id']}_{sym}", "status": "ACCRUING",
                              "rows": len(basis), "need": fs.MIN_ROWS})
            continue
        feat = pd.DataFrame({"basis_pct": basis.to_numpy(),
                             "broker_take_pct": take.reindex(basis.index).to_numpy()})
        feat["basis_chg"] = feat["basis_pct"].diff()
        avail = pd.Series(basis.index + pd.Timedelta(hours=23, minutes=59))
        out = _emit(f"os_{row['id']}_{sym.lower()}",
                    {**row, "event_lane": False, "targets": pr.get("targets") or [sym]},
                    feat, avail, pd.Series(basis.index), "cip_basis_proxy",
                    "broker_swap_panel_day_end", {"attribution": NYFED_NOTICE})
        if out:
            outs.append(out)
    return outs


def load_swap_panel(panel_dir: Path | None = None, terms_dir: Path | None = None,
                    bars_dir: Path | None = None) -> pd.DataFrame:
    """The broker's hourly swap panel joined with its UNITS and a price, one row per capture.

    Swaps come from carry_state's own store (data/intelligence/broker_swaps/: hourly JSON lists
    and the daily jsonl.gz roll-ups), swap_mode and digits from the tape's contract terms, price
    from the symbol's own H1 close on the capture day. A symbol with no contract terms has no
    swap_mode and is left out: the unit of its swap is unknown (carry_state's rule)."""
    from research import carry_state as cs
    pdir = panel_dir or cs._PANEL
    terms = cs._load_terms(terms_dir or cs._TERMS)
    rows: list[dict[str, Any]] = []

    def _take(r: Any) -> None:
        if not isinstance(r, dict) or r.get("kind") != "swap_table" or not r.get("symbols"):
            return
        if r.get("swap_long") is None or r.get("swap_short") is None:
            return
        rows.append({"time": r.get("found_at"), "symbol": str(r["symbols"][0]),
                     "swap_long": float(r["swap_long"]), "swap_short": float(r["swap_short"])})

    for f in sorted(pdir.glob("*.json")) if pdir.exists() else []:
        try:
            doc = json.loads(f.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        for r in doc if isinstance(doc, list) else []:
            _take(r)
    for f in sorted(pdir.glob("*.jsonl.gz")) if pdir.exists() else []:
        try:
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                for ln in fh:
                    try:
                        _take(json.loads(ln))
                    except ValueError:
                        continue
        except OSError:
            continue
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["swap_mode"] = df["symbol"].map(lambda s: (terms.get(s) or {}).get("swap_mode"))
    df["digits"] = df["symbol"].map(lambda s: (terms.get(s) or {}).get("digits"))
    df = df.dropna(subset=["swap_mode", "digits"])
    df["swap_mode"] = df["swap_mode"].map(
        lambda m: "points" if int(m) == cs.SWAP_MODE_POINTS else str(int(m)))
    bdir = bars_dir or cs._UNIVERSE
    px: list[float] = []
    closes: dict[str, pd.Series] = {}
    for r in df.itertuples():
        if r.symbol not in closes:
            closes[r.symbol] = _daily_close(bdir / f"{r.symbol}_H1.parquet")
        c = closes[r.symbol]
        t = pd.Timestamp(r.time).tz_convert("UTC") if pd.Timestamp(r.time).tzinfo else \
            pd.Timestamp(r.time).tz_localize("UTC")
        v = c[c.index <= t].iloc[-1] if len(c) and (c.index <= t).any() else np.nan
        px.append(float(v))
    df["price"] = px
    return df


def _daily_close(p: Path) -> pd.Series:
    """H1 closes indexed by the instant each bar CLOSED, in true UTC (the bar stamp is the
    broker-clock OPEN time; `libs.regime.session_clock.server_to_utc` converts it)."""
    try:
        b = pd.read_parquet(p)
    except Exception:
        return pd.Series(dtype=float)
    if "time" in b.columns:
        b = b.set_index(pd.to_datetime(b["time"]))
    from libs.regime.session_clock import server_to_utc
    opened = server_to_utc(pd.DatetimeIndex(pd.to_datetime(b.index)).tz_localize(None)
                           if pd.DatetimeIndex(pd.to_datetime(b.index)).tz is not None
                           else pd.DatetimeIndex(pd.to_datetime(b.index)))
    closed = pd.DatetimeIndex(opened) + pd.Timedelta(hours=1)
    if closed.tz is None:
        closed = closed.tz_localize("UTC")
    return pd.Series(pd.to_numeric(b["close"], errors="coerce").to_numpy(),
                     index=closed).dropna().sort_index()


# ------------------------------------------------------------------------------ EIA storage (N8)

def eia_storage_frame(rows: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    d = pd.DataFrame(list(rows))
    if d.empty or "period" not in d.columns:
        return pd.DataFrame()
    return (pd.DataFrame({"week_end": pd.to_datetime(d["period"]),
                          "stock_bcf": pd.to_numeric(d["value"], errors="coerce")})
            .dropna().sort_values("week_end").drop_duplicates("week_end", keep="last")
            .reset_index(drop=True))


def collect_eia_storage(acc: Access, row: Mapping[str, Any]) -> list[Out]:
    """Working gas in storage, Lower 48. The route's own metadata is read first and the series id
    must appear in it; the weekly change is then compared with the 5-year same-week mean."""
    raw = RAW / f"{row['id']}.parquet"
    key = key_for(row)
    fresh = None
    if acc.online and key:
        meta = acc.json(row["id"], f"https://api.eia.gov/v2/{row['route']}/facet/series?"
                        + urllib.parse.urlencode({"api_key": key}))
        facets = [str(f.get("id")) for f in ((meta or {}).get("response") or {})
                  .get("facets") or []]
        if meta is not None:
            _evidence(str(row["id"]), {"route": row["route"], "series_ids": facets[:500]})
        if facets and row["series"] not in facets:
            acc.notes.append({"source": row["id"], "status": "UNMEASURED",
                              "why": "series id not in the route's catalogue",
                              "catalogue_sample": facets[:20]})
        elif facets:
            q = urllib.parse.urlencode({"api_key": key, "frequency": "weekly",
                                        "data[0]": "value", "facets[series][]": row["series"],
                                        "sort[0][column]": "period",
                                        "sort[0][direction]": "asc", "length": "5000"})
            doc = acc.json(row["id"], f"https://api.eia.gov/v2/{row['route']}/data/?{q}")
            fresh = eia_storage_frame(((doc or {}).get("response") or {}).get("data") or [])
    elif acc.online:
        acc.notes.append({"source": row["id"], "status": "NEEDS_KEY",
                          "key_env": row.get("key_env")})
    df = _hold(raw, fresh)
    if df.empty:
        return []
    df["week_end"] = pd.to_datetime(df["week_end"])
    df["chg_bcf"] = df["stock_bcf"].diff()
    df.loc[df["week_end"].diff() > pd.Timedelta(days=8), "chg_bcf"] = np.nan
    base = same_week_5y_mean(df["week_end"], df["chg_bcf"])
    sz = surprise_frame(df["chg_bcf"], base, int(row.get("window", 52)))
    feat = pd.DataFrame({"surprise": sz["surprise"], "surprise_z": sz["surprise_z"]})
    rel_day = df["week_end"] + pd.Timedelta(days=6)                    # Fri week end -> Thursday
    avail = release_instant(rel_day, str(row.get("at") or "10:30"), str(row["tz"]),
                            row.get("calendar"))
    out = _emit(f"os_{row['id']}", row, feat, avail, df["week_end"], "eia_storage_surprise",
                "wngsr_thursday_1030_et_holiday_late")
    return [out] if out else []


# ------------------------------------------------------------------------- USDA export sales (N7)

def fas_week_totals(rows: Sequence[Mapping[str, Any]], field: str) -> pd.DataFrame:
    """Country rows -> one total per week ending (net sales summed over destinations)."""
    d = pd.DataFrame(list(rows))
    if d.empty or "weekEndingDate" not in d.columns or field not in d.columns:
        return pd.DataFrame(columns=["week_end", "net_sales"])
    d["week_end"] = pd.to_datetime(d["weekEndingDate"], errors="coerce").dt.tz_localize(None)
    d["v"] = pd.to_numeric(d[field], errors="coerce")
    g = d.dropna(subset=["week_end"]).groupby("week_end", as_index=False)["v"].sum(min_count=1)
    return g.rename(columns={"v": "net_sales"}).sort_values("week_end").reset_index(drop=True)


def collect_usda_esr(acc: Access, row: Mapping[str, Any], now: datetime) -> list[Out]:
    """FAS Export Sales Reporting API. The commodity CODE comes from the API's own commodity list,
    matched by the row's name pattern, never typed in; the API needs a data.gov key in the
    `API_KEY` header (named by the row's key_env)."""
    key = key_for(row)
    outs: list[Out] = []
    if acc.online and not key:
        acc.notes.append({"source": row["id"], "status": "NEEDS_KEY",
                          "key_env": row.get("key_env")})
    hdr = {"API_KEY": key} if key else {}
    base = str(row["api_base"]).rstrip("/")
    codes: dict[str, str] = {}
    if acc.online and key:
        cat = acc.json(row["id"], f"{base}/esr/commodities", hdr) or []
        if cat:
            _evidence(str(row["id"]), cat)
        for c in row.get("commodities") or []:
            pat = re.compile(str(c["name_pattern"]), re.I)
            hit = [x for x in cat if pat.search(str(x.get("commodityName") or ""))]
            if len(hit) == 1:
                codes[str(c["id"])] = str(hit[0].get("commodityCode"))
            elif cat:
                acc.notes.append({"source": f"{row['id']}_{c['id']}", "status": "UNMEASURED",
                                  "why": f"commodity list matched {len(hit)} names",
                                  "names": [x.get("commodityName") for x in hit][:8]})
    for c in row.get("commodities") or []:
        cid = str(c["id"])
        raw = RAW / f"{row['id']}_{cid}.parquet"
        fresh = None
        if cid in codes:
            held = pd.read_parquet(raw) if raw.exists() else pd.DataFrame()
            first = int(row.get("first_market_year", 2010))
            have = set()
            if not held.empty and "market_year" in held.columns:
                have = set(held["market_year"].astype(int))
            parts = [held] if not held.empty else []
            # market years already held are immutable except the two most recent
            for my in range(first, now.year + 2):
                if my in have and my < now.year:
                    continue
                url = f"{base}/esr/exports/commodityCode/{codes[cid]}/allCountries/marketYear/{my}"
                rows = acc.json(f"{row['id']}_{cid}", url, hdr)
                if rows is None:
                    break
                t = fas_week_totals(rows, str(row.get("field") or "currentMYNetSales"))
                t["market_year"] = my
                parts = [p[p["market_year"] != my] if "market_year" in p.columns else p
                         for p in parts] + [t]
            if parts:
                fresh = pd.concat(parts, ignore_index=True)
        df = _hold(raw, fresh)
        if df.empty:
            continue
        # one row per week: across a market-year boundary the old and new year both report the
        # same week; the total of both is the week's net sales
        w = (df.groupby("week_end", as_index=False)["net_sales"].sum(min_count=1)
             .sort_values("week_end").reset_index(drop=True))
        w["week_end"] = pd.to_datetime(w["week_end"])
        base_m = trailing_mean(w["net_sales"], int(row.get("baseline_weeks", 4)))
        sz = surprise_frame(w["net_sales"], base_m, int(row.get("window", 52)))
        rel_day = w["week_end"] + pd.Timedelta(days=7)               # Thu week end -> next Thu
        avail = release_instant(rel_day, str(row.get("at") or "08:30"), str(row["tz"]),
                                row.get("calendar"))
        out = _emit(f"os_{row['id']}_{cid}", {**row, "targets": c.get("targets") or [],
                                              "title": f"USDA export sales {cid}"},
                    sz, avail, w["week_end"], "usda_export_sales_surprise",
                    "fas_esr_thursday_0830_et_holiday_late")
        if out:
            outs.append(out)
    return outs


# ------------------------------------------------------------------------------ TIC (N6)

def tic_s1_parse(text: str, country_pattern: str, domestic_cols: Sequence[int] = (1, 2, 3, 4),
                 sales_offset: int = 6) -> pd.DataFrame:
    """TIC s1 (tab-separated, $mn): -> [month, value] net foreign purchases of US long-term
    DOMESTIC securities in $bn for the row whose country name matches `country_pattern`.

    The header row is the one whose cells read [1] .. [12]; purchases are columns [1]..[6]
    (Treasury, agency, corporate bonds, corporate stocks, foreign bonds, foreign stocks) and
    sales [7]..[12] in the same order, so net = sum([n]) - sum([n + 6]) over the domestic set.
    Columns are located by their [n] labels, never by position."""
    pat = re.compile(country_pattern, re.I)
    lines = text.splitlines()
    pos: dict[int, int] = {}
    hdr = None
    for i, ln in enumerate(lines[:80]):
        cells = [c.strip().strip('"') for c in ln.split("\t")]
        found = {int(m.group(1)): j for j, c in enumerate(cells)
                 if (m := re.fullmatch(r"\[(\d+)\]", c))}
        if len(found) >= 12:
            pos, hdr = found, i
            break
    if hdr is None:
        return pd.DataFrame(columns=["month", "value"])
    need = [*domestic_cols, *(c + sales_offset for c in domestic_cols)]
    if any(c not in pos for c in need):
        return pd.DataFrame(columns=["month", "value"])
    out = []
    for ln in lines[hdr + 1:]:
        cells = [c.strip().strip('"') for c in ln.split("\t")]
        if len(cells) < 3 or not pat.search(cells[0]):
            continue
        m = re.fullmatch(r"((?:19|20)\d\d)-(0[1-9]|1[0-2])", cells[2])
        if not m:
            continue
        def val(c: int, cells: list[str] = cells) -> float:
            j = pos[c]
            return _num(cells[j]) if j < len(cells) else float("nan")
        net = sum(val(c) for c in domestic_cols) - sum(val(c + sales_offset)
                                                       for c in domestic_cols)
        out.append((pd.Timestamp(int(m.group(1)), int(m.group(2)), 1), net / 1000.0))
    d = pd.DataFrame(out, columns=["month", "value"]).dropna()
    return d.drop_duplicates("month", keep="first").sort_values("month").reset_index(drop=True)


def tic_vintage(held: pd.DataFrame, read: pd.DataFrame, read_at: pd.Timestamp
                ) -> pd.DataFrame:
    """Keep each month's value AS FIRST SEEN. The s1 file carries revised values for every past
    month, so a month first read now (other than the newest) is `revised` and never a surprise
    row; only a month that appears for the first time at the head of the file is `first_seen`
    (its first print, stamped no earlier than the read). The first pass marks all history
    revised: the surprise series ACCRUES from then on."""
    cols = ["month", "value", "vintage", "seen_at"]
    h = held[cols] if not held.empty and set(cols) <= set(held.columns) else \
        pd.DataFrame(columns=cols)
    if read.empty:
        return h
    known = set(pd.to_datetime(h["month"])) if not h.empty else set()
    newest_held = max(known) if known else None
    add = []
    for r in read.itertuples():
        m = pd.Timestamp(r.month)
        if m in known:
            continue
        first = newest_held is not None and m > newest_held
        add.append({"month": m, "value": float(r.value),
                    "vintage": "first_seen" if first else "revised",
                    "seen_at": read_at.isoformat()})
    if not add:
        return h
    out = pd.concat([h, pd.DataFrame(add)], ignore_index=True)
    out["month"] = pd.to_datetime(out["month"])
    return out.sort_values("month").reset_index(drop=True)


def collect_tic(acc: Access, row: Mapping[str, Any], now: datetime) -> list[Out]:
    raw = RAW / f"{row['id']}.parquet"
    held = pd.read_parquet(raw) if raw.exists() else pd.DataFrame()
    df = held
    if acc.online:
        body = acc.get(str(row["id"]), str(row["file_url"]))
        if body is not None:
            read = tic_s1_parse(body, str(row["country_pattern"]))
            if read.empty:
                acc.notes.append({"source": row["id"], "status": "UNMEASURED",
                                  "why": "s1 header or the total row not found"})
            else:
                _evidence(str(row["id"]), {"newest_month": str(read["month"].max()),
                                           "rows": len(read)})
                ts = pd.Timestamp(now)
                df = tic_vintage(held, read, ts.tz_convert("UTC") if ts.tzinfo else
                                 ts.tz_localize("UTC"))
                if not df.empty:
                    RAW.mkdir(parents=True, exist_ok=True)
                    fs._atomic_parquet(raw, df, index=False)
    if df.empty:
        return []
    df = df.sort_values("month").reset_index(drop=True)
    df["month"] = pd.to_datetime(df["month"])
    med = trailing_median(df["value"], int(row.get("baseline_months", 12)))
    sz = surprise_frame(df["value"], med, int(row.get("window", 60)))
    keep = (df["vintage"] == "first_seen").to_numpy()
    month_end = df["month"] + pd.offsets.MonthEnd(0)
    rel_day = month_end + pd.Timedelta(days=int(row.get("lag_days", 52)))
    avail = release_instant(rel_day, str(row.get("at") or "16:00"), str(row["tz"]),
                            row.get("calendar"), holiday_shift=False)
    seen = pd.to_datetime(df["seen_at"], utc=True)
    avail = pd.Series(np.where(seen > avail, seen, avail), index=avail.index)
    avail = pd.to_datetime(avail, utc=True)
    feat = sz[keep].reset_index(drop=True)
    out = _emit(f"os_{row['id']}", row, feat, avail[keep].reset_index(drop=True),
                month_end[keep].reset_index(drop=True), "tic_flow_surprise",
                "max(conservative_upper_bound, first_seen_read)",
                {"state_days": int(row.get("state_days", 7)), "vintage": "first_seen",
                 "revised_history_rows": int((~keep).sum()),
                 "state_window": ("UNMEASURED: the conditioner carries a value to the next "
                                  "release; a release+N-day expiry needs a max-age parameter "
                                  "on family_exogenous_conditioner (Judge's family)")})
    if out is None:
        acc.notes.append({"source": row["id"], "status": "ACCRUING",
                          "first_seen_rows": int(keep.sum()), "need": MIN_EVENTS})
    return [out] if out else []


# ------------------------------------------------------------------------------ BoJ rinban (N4)

def rinban_parse(rows: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Operation results -> per operation: offer vs plan for its bucket, and bid cover.

    Each input row: date, bucket, offered (amount the BoJ offered to buy), planned (the bucket's
    per-operation amount from the BoJ's pre-announced monthly schedule), bids (amount the market
    offered to sell). Planned may be absent when the schedule was not read; such an operation
    keeps its cover but has no size surprise."""
    d = pd.DataFrame(list(rows))
    if d.empty:
        return pd.DataFrame()
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    for c in ("offered", "planned", "bids"):
        d[c] = pd.to_numeric(d.get(c), errors="coerce")
    d = d.dropna(subset=["date", "offered"])
    d["size_vs_plan"] = d["offered"] / d["planned"] - 1.0
    d["cover"] = d["bids"] / d["offered"]
    g = d.groupby("date", as_index=False).agg(
        size_vs_plan=("size_vs_plan", "mean"), cover=("cover", "mean"),
        offered=("offered", "sum"))
    return g.sort_values("date").reset_index(drop=True)


def collect_rinban(acc: Access, row: Mapping[str, Any]) -> list[Out]:
    """Held until the terms read is OPEN and the box has read one results page and one schedule
    page (the parser's field map is in the row). Offline it serves held rows."""
    raw = RAW / f"{row['id']}.parquet"
    df = _hold(raw, None)
    if df.empty:
        return []
    ops = rinban_parse(df.to_dict("records"))
    if ops.empty:
        return []
    cover_base = trailing_median(ops["cover"], int(row.get("baseline_ops", 20)))
    sz = surprise_frame(ops["cover"], cover_base, int(row.get("window", 60)))
    feat = pd.DataFrame({"size_vs_plan": ops["size_vs_plan"], "cover_surprise": sz["surprise"],
                         "cover_z": sz["surprise_z"]})
    avail = release_instant(ops["date"], str(row.get("at") or "12:10"), str(row["tz"]),
                            row.get("calendar"), holiday_shift=False)
    out = _emit(f"os_{row['id']}", row, feat, avail, ops["date"], "boj_rinban_surprise",
                "boj_result_release_same_day_jst")
    return [out] if out else []


# ------------------------------------------------------------------------------ the pass

ADAPTERS = ("us_net_liquidity", "us_funding", "cip_basis", "eia_storage", "usda_esr", "tic",
            "boj_rinban")


def collect(*, text: Callable[[str, Mapping[str, str]], str] | None, state: dict[str, Any],
            notes: list[dict[str, Any]], frames: Mapping[str, pd.DataFrame] | None = None,
            now: datetime | None = None, deadline: float | None = None,
            registry: Mapping[str, Any] | None = None,
            swaps: pd.DataFrame | None = None) -> list[Out]:
    """Every row -> outputs. `text=None` is offline (held raw only). Never raises per row."""
    reg = registry if registry is not None else (fs._read(REGISTRY, {}) or {})
    now = now or datetime.now(UTC)
    acc = Access(text, state, notes, deadline)
    out: list[Out] = []
    for row in reg.get("rows") or []:
        sid, ad = str(row.get("id")), str(row.get("adapter"))
        if ad not in ADAPTERS:
            notes.append({"source": sid, "status": "UNMEASURED", "why": f"no adapter {ad}"})
            continue
        if row.get("terms") != "OPEN":
            notes.append({"source": sid, "status": "UNMEASURED",
                          "why": f"terms {row.get('terms')}", "note": row.get("terms_note", "")})
            # a held row still serves what an earlier OPEN pass or a box read already holds
            live = Access(None, state, notes, deadline)
        else:
            live = acc
        try:
            if ad == "us_net_liquidity":
                out += collect_net_liquidity(live, row, now)
            elif ad == "us_funding":
                out += collect_funding(live, row, now)
            elif ad == "cip_basis":
                out += collect_cip(live, row,
                                   swaps if swaps is not None else load_swap_panel(), now)
            elif ad == "eia_storage":
                out += collect_eia_storage(live, row)
            elif ad == "usda_esr":
                out += collect_usda_esr(live, row, now)
            elif ad == "tic":
                out += collect_tic(live, row, now)
            elif ad == "boj_rinban":
                out += collect_rinban(live, row)
        except (fs.HardStop, KeyboardInterrupt):
            raise
        except Exception as exc:
            notes.append({"source": sid, "error": type(exc).__name__})
    return out


def report(outs: Sequence[Out], notes: Sequence[Mapping[str, Any]],
           registry: Mapping[str, Any]) -> dict[str, Any]:
    built = {oid: meta for oid, _f, meta in outs}
    rows = registry.get("rows") or []
    by_row = {}
    for r in rows:
        mine = [o for o in built if o == f"os_{r['id']}" or o.startswith(f"os_{r['id']}_")]
        why = [n for n in notes if str(n.get("source", "")).startswith(str(r["id"]))]
        by_row[r["id"]] = {"idea": r.get("idea"), "adapter": r.get("adapter"),
                           "terms": r.get("terms"), "series": mine,
                           "state": "PRODUCING" if mine else "UNMEASURED",
                           "why_not": why[:4] if not mine else []}
    return {"generated_utc": fs._now(),
            "rule": ("Every official release row reaches cells or is named here with its "
                     "reason. Robots first; 401/403/429/451 hard stop; ids only from the "
                     "source's own catalogue; release instants late, never early."),
            "rows": by_row, "series": built,
            "producing": sum(1 for v in by_row.values() if v["state"] == "PRODUCING"),
            "of": len(rows), "notes": list(notes)}


def write_report(outs: Sequence[Out], notes: Sequence[Mapping[str, Any]],
                 registry: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """reports/OFFICIAL_SURPRISES.json: per row PRODUCING or why not. Written by the futures_state
    leg after every pass (this module has no clock of its own; that leg is its clock)."""
    reg = registry if registry is not None else (fs._read(REGISTRY, {}) or {})
    doc = report(outs, notes, reg)
    fs._write(REPORT, doc)
    return doc
