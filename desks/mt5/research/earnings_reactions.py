"""EARNINGS REACTIONS: SEC 8-K item 2.02 acceptance times joined to the share-CFD price reaction.

EVENT LANE ONLY (the two-lane order, 2026-09-06, amended 2026-09-30). Single-name equities are
traded on news, reports and earnings reaction and never hunted for statistical hypotheses. This
module is a DATASET organ: it writes per-filing reaction rows and a daily breadth aggregate, and
nothing else. It mints no hypothesis, no candidate, no cell and charges no trial; it writes nothing
under `data/intelligence/` or `data/hypotheses/`. The index-side family that reads the daily
breadth (earnings-season breadth into US500 / NAS100) is a separate organ on the hypothesis lane,
where the instrument it trades is an index.

WHY IT EXISTS. `sandboxes/edgar_transmission.py` counts 8-K 2.02 bursts from full-text search, but
full-text search carries the FILING DATE only: no acceptance time, so no session bucket and no
reaction. The submissions API (`data.sec.gov/submissions/CIK##########.json`) carries
`acceptanceDateTime`, which is what lets a filing be put before, during or after the US session
and joined to the first bar that could have priced it.

THE ACCEPTANCE STAMP IS EASTERN, WHATEVER ITS SUFFIX SAYS. The submissions API writes
`acceptanceDateTime` as `2024-08-01T16:30:42.000Z`; the clock behind it is EDGAR's, which is US
Eastern, and the trailing `Z` is not an offset. It is read as America/New_York wall time and
converted to UTC (the filing-index form `20240801163042` is read the same way). The raw string is
kept on every row so a reader can check the reading.

BARS ARE BROKER-STAMPED. The universe parquets carry MetaTrader's bar-open stamps (New York wall
time + 7 h) labelled UTC; `libs.regime.session_clock.server_to_utc` is the desk's one conversion
and every bar instant here goes through it before it is compared with an acceptance time.

FIELDS. Per filing, on the finest chart the loader has (M15, then M5, then H1):
  pre_close     the close of the last bar that ENDED at or before acceptance
  ret_open      pre_close -> close of the first bar after the next session open (09:30 ET)
  gap           pre_close -> the open of that bar
  ret_1h        +1 h from the reaction start (acceptance when intraday, else the next open)
  ret_1d        pre_close -> close of the reaction session (day 0)
  ret_5d        pre_close -> close of the fifth session counting day 0
  abn_*         the same window minus US500's return over the same instants
  volume_ratio  day-0 tick volume / mean daily tick volume of the 20 sessions before it
Day 0 is the acceptance date for an intraday filing, the first session on or after it for a
pre-market one, and the first session after it for a post-market one.

UNMEASURED IS A VALUE (L1.28a). A field that cannot be measured is null with its reason in
`unmeasured`, never a zero. A reason starting `PENDING` names a horizon not yet in the bars; the
row is re-measured on a later pass and, if anything changed, a NEW row is appended with
`revision` + 1 (append-only; readers take the last row per accession).

SEC FAIR ACCESS. A declared User-Agent (`QUANT_EDGAR_UA`, else an honest generic one), at most
five requests a second through `polite_fetch`, no retry, and a HARD STOP on 401/403/429/451: the
pass stops fetching, the refusal is recorded, and the host stays closed until its robots.txt,
read afresh on a later pass, admits us again. Every host's robots.txt is read once per pass
under our own User-Agent before any request: a Disallow stops the pass, 401/403/429/451 on
robots.txt is a refusal, 5xx or no answer stops the pass and is read again next pass, and
404/410 means no rules.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd  # noqa: E402

ORGAN = "earnings_reactions"
NY = ZoneInfo("America/New_York")
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
UA_ENV = "QUANT_EDGAR_UA"
FALLBACK_UA = "quant-research-earnings/1.0 (+public research reader)"
#: SEC fair access allows ten a second; this organ takes half.
MIN_INTERVAL_S = 0.2
HARD_STOP_STATUS = frozenset({401, 403, 429, 451})
#: robots.txt answers, under the desk ruling of 2026-11-10: 404/410 (and any other 4xx that is
#: not a refusal) means no rules, so fetch; 401/403/429/451 is a refusal; 5xx, a timeout or an
#: unreadable answer stops the pass and is read again next pass.
ROBOTS_ABSENT_STATUS = frozenset({404, 410})
TICKERS_MAX_AGE_H = 24.0
CIK_MAX_AGE_H = 20.0
MAX_FETCH_PER_PASS = 300
FETCH_SHARE = 0.7
MAX_BYTES = 12_000_000
ITEM = "2.02"
BENCH = "US500"
TIMEFRAMES = ("M15", "M5", "H1")
BAR_LEN = {"M5": timedelta(minutes=5), "M15": timedelta(minutes=15), "H1": timedelta(hours=1)}
OPEN_T = (9, 30)
CLOSE_T = (16, 0)
PRE, INTRA, POST = "pre_market", "intraday", "post_market"
BUCKETS = (PRE, INTRA, POST)
PENDING = "PENDING"
MAX_PRE_GAP = timedelta(days=5)
BENCH_STALE = timedelta(hours=2)
VOL_LOOKBACK = 20
VOL_MIN_SESSIONS = 5
WINDOWS = ("gap", "ret_open", "ret_1h", "ret_1d", "ret_5d")

Getter = Callable[..., Any]
Loader = Callable[[str, str], "pd.DataFrame | None"]


@dataclass(frozen=True)
class Paths:
    desk: Path = DESK

    @property
    def data(self) -> Path:
        return self.desk / "data"

    @property
    def cache(self) -> Path:
        return self.data / "edgar_cache" / "earnings"

    @property
    def state(self) -> Path:
        return self.cache / "state.json"

    @property
    def tickers(self) -> Path:
        return self.cache / "company_tickers.json"

    def cik_file(self, cik: int) -> Path:
        return self.cache / f"CIK{int(cik):010d}.json"

    @property
    def rows(self) -> Path:
        return self.data / "earnings_reactions.jsonl"

    @property
    def breadth(self) -> Path:
        return self.data / "earnings_breadth_daily.json"

    @property
    def census(self) -> Path:
        return self.desk / "reports" / "EARNINGS_REACTIONS.json"

    @property
    def universe(self) -> Path:
        return self.data / "universe" / "universe.json"


class HardStop(Exception):
    """The SEC refused this client (401/403/429/451): stop fetching for the pass."""

    def __init__(self, url: str, status: int) -> None:
        super().__init__(f"HTTP {status} from {url}")
        self.url, self.status = url, int(status)


class RobotsStop(Exception):
    """robots.txt did not admit this URL: a Disallow, or an unreadable file. Stop the pass."""

    def __init__(self, url: str, label: str, why: str) -> None:
        super().__init__(f"{label}: {why}")
        self.url, self.label, self.why = url, label, why


# ------------------------------------------------------------------------------ small helpers
def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(dt: datetime | None) -> str | None:
    return None if dt is None else dt.astimezone(UTC).isoformat(timespec="seconds")


def _parse_iso(s: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(s))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False), "utf-8")
    os.replace(tmp, path)


def user_agent() -> str:
    return os.environ.get(UA_ENV, "").strip() or FALLBACK_UA


def _age_h(stamp: Any, now: datetime) -> float:
    dt = _parse_iso(stamp)
    return math.inf if dt is None else (now - dt).total_seconds() / 3600.0


# ------------------------------------------------------------------------------ the instruments
def share_cfds(universe_doc: Mapping[str, Any],
               is_equity: Callable[[str], bool] | None = None) -> list[str]:
    """The registry's share CFDs, by ASSET CLASS (`universe_policy.is_equity`), never a list."""
    if is_equity is None:
        from research import universe_policy
        is_equity = universe_policy.is_equity
    return sorted(s for s in universe_doc if isinstance(universe_doc.get(s), dict)
                  and is_equity(str(s)))


def _desk_ticker_table() -> dict[str, str]:
    """The desk's one MT5-name -> US-ticker table (`alpha_capture.TICKERS`, pinned there against
    universe.json). Fusion names share CFDs by company ("Apple"), so a suffix strip alone maps
    almost nothing; the strip below is the fallback for a code-named symbol."""
    try:
        from research.alpha_capture import TICKERS
        return dict(TICKERS)
    except Exception:                                      # pragma: no cover - import context
        return {}


def _strip_suffix(symbol: str) -> str:
    s = str(symbol).strip().upper().split(".")[0]          # AAPL.24H, AAPL.US -> AAPL
    if s.endswith("USD") and len(s) > 3:                    # AAPLUSD -> AAPL
        s = s[:-3]
    return s.replace("_", "-")


def map_tickers(symbols: Iterable[str], sec: Mapping[str, int],
                table: Mapping[str, str] | None = None) -> tuple[dict[str, dict[str, Any]],
                                                                  dict[str, str]]:
    """symbol -> {ticker, cik, via}; and symbol -> reason for every symbol left unmapped."""
    table = _desk_ticker_table() if table is None else table
    mapped: dict[str, dict[str, Any]] = {}
    unmapped: dict[str, str] = {}
    for sym in symbols:
        cands = [(str(table[sym]).upper(), "desk_ticker_table")] if sym in table else []
        cands.append((_strip_suffix(sym), "suffix_strip"))
        hit = next(((t, via) for t, via in cands if t in sec), None)
        if hit is None:
            unmapped[sym] = ("ticker not in SEC company_tickers: "
                             + ", ".join(sorted({t for t, _ in cands})))
            continue
        mapped[sym] = {"ticker": hit[0], "cik": int(sec[hit[0]]), "via": hit[1]}
    return mapped, unmapped


def parse_company_tickers(doc: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    rows = doc.values() if isinstance(doc, dict) else (doc or [])
    for r in rows:
        if isinstance(r, dict) and r.get("ticker") and r.get("cik_str") is not None:
            try:
                out[str(r["ticker"]).upper()] = int(r["cik_str"])
            except (TypeError, ValueError):
                continue
    return out


# ------------------------------------------------------------------------------ the filings
def acceptance_to_utc(raw: Any) -> datetime | None:
    """EDGAR's acceptance stamp (US Eastern wall time, whatever its suffix) as a UTC instant."""
    s = str(raw or "").strip()
    if not s:
        return None
    try:
        if s.isdigit() and len(s) == 14:
            wall = datetime(int(s[:4]), int(s[4:6]), int(s[6:8]), int(s[8:10]),  # noqa: DTZ001
                            int(s[10:12]), int(s[12:14]))
        else:
            wall = datetime.fromisoformat(s.rstrip("Zz").split("+")[0]).replace(tzinfo=None)
    except ValueError:
        return None
    return wall.replace(tzinfo=NY).astimezone(UTC)


def has_item(items: Any, item: str = ITEM) -> bool:
    parts = items if isinstance(items, (list, tuple)) else str(items or "").split(",")
    return any(str(p).strip() == item for p in parts)


def parse_submissions(doc: Any) -> list[dict[str, Any]]:
    """Form 8-K (and 8-K/A) rows carrying item 2.02, from `filings.recent`'s parallel arrays."""
    recent = ((doc or {}).get("filings") or {}).get("recent") if isinstance(doc, dict) else None
    if not isinstance(recent, dict):
        return []
    forms = recent.get("form") or []
    out = []
    for i, form in enumerate(forms):
        def col(k: str, i: int = i) -> Any:
            v = recent.get(k) or []
            return v[i] if i < len(v) else None
        if str(form) not in ("8-K", "8-K/A") or not has_item(col("items")):
            continue
        acc = acceptance_to_utc(col("acceptanceDateTime"))
        out.append({"accession": str(col("accessionNumber") or ""), "form": str(form),
                    "items": str(col("items") or ""), "filing_date": str(col("filingDate") or ""),
                    "acceptance_raw": str(col("acceptanceDateTime") or ""),
                    "acceptance_utc": _iso(acc)})
    return [r for r in out if r["accession"]]


def session_bucket(acc_utc: datetime) -> str:
    t = acc_utc.astimezone(NY).time()
    if (t.hour, t.minute) < OPEN_T:
        return PRE
    if (t.hour, t.minute) < CLOSE_T:
        return INTRA
    return POST


# ------------------------------------------------------------------------------ fetching
class Fetcher:
    """One polite SEC client: declared UA, MIN_INTERVAL_S spacing, no retry, hard stop."""

    def __init__(self, getter: Getter | None = None, *, deadline: float | None = None,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        from libs.data import polite_fetch as pf
        self.pf = pf
        self.get = getter or pf.get
        self.gate = pf.HostGate(default_s=MIN_INTERVAL_S)
        self.deadline = deadline
        self.sleep = sleep
        self.ua = user_agent()
        self.fetched = 0
        self.failed: list[dict[str, Any]] = []
        self.robots: dict[str, Any] = {}          # host -> parsed rules, or None when absent

    def robots_read(self, url: str) -> None:
        """Read the host's robots.txt once per pass, under our own User-Agent, and stop unless
        it admits `url`. A refusal of robots.txt itself is a HardStop like any other."""
        import urllib.robotparser
        from urllib.parse import urlsplit
        parts = urlsplit(url)
        host = parts.netloc.lower()
        if host not in self.robots:
            robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
            r = self.get(robots_url, headers={"User-Agent": self.ua, "Accept": "text/plain"},
                         retries=0, deadline=self.deadline, max_bytes=1_000_000, leg=ORGAN,
                         gate=self.gate, sleep=self.sleep)
            self.fetched += 1
            status = getattr(r, "status", None)
            code = int(status) if status is not None else None
            if code in HARD_STOP_STATUS:
                raise HardStop(robots_url, int(code))
            if getattr(r, "ok", False):
                rp = urllib.robotparser.RobotFileParser()
                rp.parse((getattr(r, "text", "") or "").splitlines())
                self.robots[host] = rp
            elif code is not None and 400 <= code < 500:
                self.robots[host] = None                 # absent: no rules
            else:
                raise RobotsStop(url, "ROBOTS_UNREACHABLE",
                                 f"robots.txt answered {code or getattr(r, 'error', '') or 'nothing'}"
                                 "; read again next pass")
        rules = self.robots[host]
        if rules is not None and not rules.can_fetch(self.ua, url):
            raise RobotsStop(url, "DISALLOWED", f"robots.txt disallows {parts.path} for our agent")

    def json(self, url: str) -> Any:
        self.robots_read(url)
        r = self.get(url, headers={"User-Agent": self.ua, "Accept": "application/json",
                                   "Accept-Encoding": "gzip, deflate"},
                     retries=0, deadline=self.deadline, max_bytes=MAX_BYTES, leg=ORGAN,
                     gate=self.gate, sleep=self.sleep)
        self.fetched += 1
        status = getattr(r, "status", None)
        if status is not None and int(status) in HARD_STOP_STATUS:
            raise HardStop(url, int(status))
        if not getattr(r, "ok", False):
            self.failed.append({"url": url, "status": status, "error": getattr(r, "error", "")})
            return None
        try:
            return json.loads(getattr(r, "text", "") or "")
        except ValueError:
            self.failed.append({"url": url, "status": status, "error": "not JSON"})
            return None


def machine_use(url: str) -> tuple[bool, str]:
    try:
        from research.sandboxes.edgar_transmission import machine_use_allowed
        return machine_use_allowed(url)
    except Exception as exc:                               # pragma: no cover - import context
        return True, f"classifier unavailable ({type(exc).__name__}); public federal filings"


def load_sec_tickers(paths: Paths, fetcher: Fetcher | None, now: datetime,
                     census: dict[str, Any]) -> dict[str, int]:
    cached = _read_json(paths.tickers)
    fresh = isinstance(cached, dict) and _age_h(cached.get("fetched_at"), now) < TICKERS_MAX_AGE_H
    if fetcher is not None and not fresh:
        doc = fetcher.json(TICKERS_URL)                     # HardStop propagates
        tickers = parse_company_tickers(doc)
        if tickers:
            cached = {"fetched_at": _iso(now), "source": TICKERS_URL, "tickers": tickers}
            _write_json(paths.tickers, cached)
            census["tickers_fetched"] = True
    if not isinstance(cached, dict):
        return {}
    census["tickers_as_of"] = cached.get("fetched_at")
    return {str(k): int(v) for k, v in (cached.get("tickers") or {}).items()}


def due_ciks(paths: Paths, ciks: Sequence[int], cursor: int, now: datetime,
             cap: int = MAX_FETCH_PER_PASS) -> tuple[list[int], int]:
    """The CIKs whose cache is older than CIK_MAX_AGE_H, rotating from `cursor`, at most `cap`."""
    order = sorted({int(c) for c in ciks})
    if not order:
        return [], 0
    start = cursor % len(order)
    rotated = order[start:] + order[:start]
    due: list[int] = []
    last = start
    for k, cik in enumerate(rotated):
        if len(due) >= cap:
            break
        last = (start + k + 1) % len(order)
        doc = _read_json(paths.cik_file(cik))
        if isinstance(doc, dict) and _age_h(doc.get("fetched_at"), now) < CIK_MAX_AGE_H:
            continue
        due.append(cik)
    return due, last


def fetch_cik(paths: Paths, fetcher: Fetcher, cik: int, now: datetime) -> int | None:
    doc = fetcher.json(SUBMISSIONS_URL.format(cik=int(cik)))
    if doc is None:
        return None
    filings = parse_submissions(doc)
    _write_json(paths.cik_file(cik), {"cik": int(cik), "fetched_at": _iso(now),
                                      "name": str(doc.get("name") or ""), "filings": filings,
                                      "note": "filings.recent only (EDGAR's last ~1000 filings)"})
    return len(filings)


# ------------------------------------------------------------------------------ bars
def _read_bars(symbol: str, timeframe: str) -> pd.DataFrame | None:
    """The hourly legs' loader (`proposer_common.bars`) for H1; the same rules for M15/M5."""
    if timeframe == "H1":
        try:
            from research.proposer_common import bars
            return bars(symbol)
        except Exception:                                  # pragma: no cover - import context
            return None
    p = DESK / "data" / "universe" / f"{symbol}_{timeframe}.parquet"
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p)
    except (OSError, ValueError, ImportError):
        return None
    if df.empty or "close" not in df.columns:
        return None
    df.index = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True, errors="coerce"))
    return df[~df.index.isna()]


@dataclass
class Chart:
    tf: str
    start: pd.DatetimeIndex            # true UTC bar-open instants
    end: pd.DatetimeIndex              # start + bar length
    open: Any
    close: Any
    ny_date: list[date]
    ny_min: list[int]                   # minutes after NY midnight of the bar's open
    days: list[date]                    # session days: a bar overlapping 09:30-16:00 ET
    open_i: dict[date, int]             # the first bar overlapping the open, per session day
    close_i: dict[date, int]            # the last bar starting before 16:00, per session day
    day_volume: dict[date, float] | None  # None when the chart carries no usable volume


def to_chart(frame: pd.DataFrame | None, tf: str) -> Chart | None:
    if frame is None or len(frame) == 0 or "close" not in frame.columns:
        return None
    from libs.regime.session_clock import server_to_utc
    f = frame.sort_index()
    f = f[~f.index.duplicated(keep="last")]
    start = server_to_utc(f.index)
    ny = start.tz_convert(NY)
    ny_date = [d.date() for d in ny]
    ny_min = [d.hour * 60 + d.minute for d in ny]
    o, c = OPEN_T[0] * 60 + OPEN_T[1], CLOSE_T[0] * 60 + CLOSE_T[1]
    blen = int(BAR_LEN[tf].total_seconds() // 60)
    open_i: dict[date, int] = {}
    close_i: dict[date, int] = {}
    for i, (d, m) in enumerate(zip(ny_date, ny_min, strict=True)):
        if m < c:
            close_i[d] = i
            if m + blen > o and d not in open_i:
                open_i[d] = i
    day_volume: dict[date, float] | None = None
    for col in ("tick_volume", "real_volume", "volume"):
        if col not in f.columns:
            continue
        v = pd.to_numeric(f[col], errors="coerce").to_numpy(dtype=float)
        if float(pd.Series(v).fillna(0).sum()) <= 0:
            continue
        day_volume = defaultdict(float)
        for d, x in zip(ny_date, v, strict=True):
            if math.isfinite(x):
                day_volume[d] += float(x)
        day_volume = dict(day_volume)
        break
    return Chart(tf=tf, start=start, end=start + BAR_LEN[tf],
                 open=f["open"].to_numpy(dtype=float) if "open" in f.columns else None,
                 close=f["close"].to_numpy(dtype=float), ny_date=ny_date, ny_min=ny_min,
                 days=sorted(open_i), open_i=open_i, close_i=close_i, day_volume=day_volume)


def load_chart(symbol: str, loader: Loader, tfs: Sequence[str] = TIMEFRAMES) -> Chart | None:
    for tf in tfs:
        try:
            frame = loader(symbol, tf)
        except Exception:
            frame = None
        ch = to_chart(frame, tf)
        if ch is not None:
            return ch
    return None


def _last_end_at_or_before(ch: Chart, t: pd.Timestamp) -> int | None:
    k = int(ch.end.searchsorted(t, side="right")) - 1
    return k if k >= 0 else None


def _ny_open(day: date) -> pd.Timestamp:
    return pd.Timestamp(datetime(day.year, day.month, day.day, *OPEN_T, tzinfo=NY)).tz_convert(UTC)


def _ret(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or not math.isfinite(a) or not math.isfinite(b) or a <= 0:
        return None
    return float(b / a - 1.0)


# ------------------------------------------------------------------------------ the reaction
def reaction(acc_utc: datetime, ch: Chart | None, bench: Chart | None) -> dict[str, Any]:
    """Every reaction field for one acceptance instant; a field that cannot be measured is None
    with its reason in `unmeasured` (a reason starting PENDING may still arrive)."""
    out: dict[str, Any] = dict.fromkeys((*WINDOWS, *(f"abn_{w}" for w in WINDOWS), "pre_close",
                                         "pre_close_utc", "next_open_date", "day0",
                                         "volume_ratio", "timeframe"))
    um: dict[str, str] = {}
    out["unmeasured"] = um
    bucket = session_bucket(acc_utc)
    if ch is None:
        for f in (*WINDOWS, "pre_close", "volume_ratio"):
            um[f] = "no bars for the symbol on any chart"
        for w in WINDOWS:
            um[f"abn_{w}"] = "no bars for the symbol"
        return out
    out["timeframe"] = ch.tf
    t_acc = pd.Timestamp(acc_utc)
    last_end = ch.end[-1]
    pre = _last_end_at_or_before(ch, t_acc)
    if pre is None:
        for f in (*WINDOWS, *(f"abn_{w}" for w in WINDOWS), "pre_close", "volume_ratio"):
            um[f] = "no bar closed before acceptance (filing predates the bar history)"
        return out
    if t_acc - ch.end[pre] > MAX_PRE_GAP:
        for f in (*WINDOWS, *(f"abn_{w}" for w in WINDOWS), "pre_close", "volume_ratio"):
            um[f] = (PENDING + ": bars end before acceptance" if pre == len(ch.end) - 1
                     else "bar gap of more than 5 days before acceptance")
        return out
    pre_px = float(ch.close[pre])
    out["pre_close"], out["pre_close_utc"] = pre_px, _iso(ch.end[pre].to_pydatetime())
    days = ch.days
    acc_day = acc_utc.astimezone(NY).date()
    next_open_days = [d for d in days if (d >= acc_day if bucket == PRE else d > acc_day)]
    day0_days = [d for d in days if (d >= acc_day if bucket in (PRE, INTRA) else d > acc_day)]
    if bucket == INTRA and acc_day not in days:
        day0_days = [d for d in days if d > acc_day]
    pend = PENDING + ": horizon not yet in the bars"

    # the instants each window ends at: (bar index, window start instant for the benchmark)
    ends: dict[str, int | None] = {}
    starts: dict[str, pd.Timestamp] = {}
    open_i = ch.open_i.get(next_open_days[0]) if next_open_days else None
    if open_i is None:
        for w in ("gap", "ret_open"):
            um[w] = pend
    else:
        out["next_open_date"] = next_open_days[0].isoformat()
        ends["ret_open"] = open_i
        if ch.open is not None and math.isfinite(float(ch.open[open_i])):
            out["gap"] = _ret(pre_px, float(ch.open[open_i]))
            starts["gap"] = ch.start[open_i]
        else:
            um["gap"] = "chart carries no open price"
        out["ret_open"] = _ret(pre_px, float(ch.close[open_i]))
    # +1 h from the reaction start, on the same session day
    r_start = t_acc if bucket == INTRA else (_ny_open(next_open_days[0]) if next_open_days
                                             else None)
    if r_start is None:
        um["ret_1h"] = pend
    else:
        target = r_start + pd.Timedelta(hours=1)
        k = int(ch.end.searchsorted(target, side="left"))
        same_day = r_start.tz_convert(NY).date()
        if k < len(ch.end) and ch.ny_date[k] == same_day and \
                ch.ny_min[k] < CLOSE_T[0] * 60 + CLOSE_T[1] and ch.start[k] < target:
            ends["ret_1h"] = k
            out["ret_1h"] = _ret(pre_px, float(ch.close[k]))
        elif target > last_end:
            um["ret_1h"] = pend
        else:
            um["ret_1h"] = "session closed (or no bar) within the hour after the reaction start"
    for w, n in (("ret_1d", 1), ("ret_5d", 5)):
        if len(day0_days) < n:
            um[w] = pend
            continue
        kc = ch.close_i.get(day0_days[n - 1])
        if kc is None or (ch.end[kc] == last_end and ch.ny_min[kc] + BAR_LEN[ch.tf]
                          .total_seconds() / 60 < CLOSE_T[0] * 60 + CLOSE_T[1]):
            um[w] = pend                                    # the last session is still printing
            continue
        ends[w] = kc
        out[w] = _ret(pre_px, float(ch.close[kc]))
    if day0_days:
        out["day0"] = day0_days[0].isoformat()
    for w in WINDOWS:
        if out[w] is None and w not in um:
            um[w] = "non-positive or non-finite price"

    # abnormal versus the benchmark, over the same instants
    def bench_px(t: pd.Timestamp) -> float | None:
        if bench is None:
            return None
        j = _last_end_at_or_before(bench, t)
        if j is None or t - bench.end[j] > BENCH_STALE:
            return None
        return float(bench.close[j])
    b_pre = bench_px(ch.end[pre])
    for w in WINDOWS:
        key = f"abn_{w}"
        if out[w] is None:
            um[key] = "the symbol's window is unmeasured"
            continue
        if bench is None:
            um[key] = f"no {BENCH} bars"
            continue
        t_end = starts[w] if w == "gap" else ch.end[ends[w]]
        b_end = bench_px(t_end)
        rb = _ret(b_pre, b_end)
        if rb is None:
            um[key] = (PENDING + f": {BENCH} bars end before the window" if t_end > bench.end[-1]
                       else f"no {BENCH} bar within 2h of the window's instants")
            continue
        out[key] = float(out[w] - rb)

    # day-0 volume against the 20 sessions before it
    if ch.day_volume is None:
        um["volume_ratio"] = "chart carries no volume"
    elif not day0_days or "ret_1d" not in ends:
        um["volume_ratio"] = pend if not day0_days or um.get("ret_1d") == pend else \
            "day-0 session unmeasured"
    else:
        by_day = ch.day_volume
        d0 = day0_days[0]
        prior = [by_day.get(d, 0.0) for d in days if d < d0][-VOL_LOOKBACK:]
        prior = [v for v in prior if v > 0]
        if len(prior) < VOL_MIN_SESSIONS:
            um["volume_ratio"] = f"fewer than {VOL_MIN_SESSIONS} prior sessions with volume"
        else:
            out["volume_ratio"] = float(by_day.get(d0, 0.0) / statistics.fmean(prior))
    return out


# ------------------------------------------------------------------------------ the ledger
def read_rows(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    doc = json.loads(line)
                except ValueError:
                    continue
                if isinstance(doc, dict) and doc.get("accession"):
                    out.append(doc)
    except OSError:
        return []
    return out


def latest_by_accession(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        out[str(r["accession"])] = dict(r)
    return out


_MEASURE_KEYS = (*WINDOWS, *(f"abn_{w}" for w in WINDOWS), "pre_close", "volume_ratio",
                 "next_open_date", "day0", "timeframe", "unmeasured", "symbol")


def _is_final(row: Mapping[str, Any]) -> bool:
    return not any(str(v).startswith(PENDING) for v in (row.get("unmeasured") or {}).values())


def _same(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    def norm(v: Any) -> Any:
        return round(v, 10) if isinstance(v, float) else v
    return all(norm(a.get(k)) == norm(b.get(k)) for k in _MEASURE_KEYS if k != "unmeasured") \
        and (a.get("unmeasured") or {}) == (b.get("unmeasured") or {})


def build_rows(filings_by_symbol: Mapping[str, list[dict[str, Any]]],
               mapping: Mapping[str, Mapping[str, Any]],
               existing: Mapping[str, Mapping[str, Any]], loader: Loader, now: datetime,
               deadline: float | None = None) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """New rows to append: one per accession not yet final, only when it differs from the last.

    ONE ROW PER ACCESSION. Two share classes of one issuer (Alphabet-A / -C) carry the same
    filing; the first symbol in sorted order owns it and the others are named in `also_symbols`.
    """
    stats: Counter[str] = Counter()
    owner: dict[str, str] = {}
    also: dict[str, list[str]] = defaultdict(list)
    for sym in sorted(filings_by_symbol):
        for f in filings_by_symbol[sym]:
            acc = f["accession"]
            if acc in owner:
                also[acc].append(sym)
            else:
                owner[acc] = sym
    bench = load_chart(BENCH, loader)
    charts: dict[str, Chart | None] = {}
    new: list[dict[str, Any]] = []
    for sym in sorted(filings_by_symbol):
        for f in filings_by_symbol[sym]:
            acc = f["accession"]
            if owner.get(acc) != sym:
                continue
            prev = existing.get(acc)
            if prev is not None and _is_final(prev):
                stats["already_final"] += 1
                continue
            if deadline is not None and time.monotonic() >= deadline:
                stats["deferred_by_budget"] += 1
                continue
            acc_utc = _parse_iso(f.get("acceptance_utc"))
            if acc_utc is None:
                stats["no_acceptance_time"] += 1
                continue
            if sym not in charts:
                charts[sym] = load_chart(sym, loader)
            rx = reaction(acc_utc, charts[sym], bench)
            m = mapping.get(sym) or {}
            row = {"accession": acc, "symbol": sym, "also_symbols": sorted(also.get(acc, [])),
                   "ticker": m.get("ticker"), "cik": m.get("cik"), "form": f.get("form"),
                   "items": f.get("items"), "filing_date": f.get("filing_date"),
                   "acceptance_raw": f.get("acceptance_raw"),
                   "acceptance_utc": f.get("acceptance_utc"),
                   "us_date": acc_utc.astimezone(NY).date().isoformat(),
                   "session_bucket": session_bucket(acc_utc), "benchmark": BENCH,
                   "lane": "event", **rx}
            if prev is not None and _same(prev, row):
                stats["unchanged"] += 1
                continue
            row["revision"] = int((prev or {}).get("revision", -1)) + 1
            row["measured_at"] = _iso(now)
            row["final"] = _is_final(row)
            new.append(row)
            stats["appended"] += 1
    return new, dict(stats)


def append_rows(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n")


def _agg(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    abn = [float(r["abn_ret_open"]) for r in rows if isinstance(r.get("abn_ret_open"), float)]
    abn1 = [float(r["abn_ret_1d"]) for r in rows if isinstance(r.get("abn_ret_1d"), float)]
    buckets = Counter(str(r.get("session_bucket")) for r in rows)
    return {
        "filers": len({r.get("cik") or r.get("symbol") for r in rows}),
        "filings": len(rows),
        "n_measured": len(abn),
        "share_positive_abnormal": (sum(1 for a in abn if a > 0) / len(abn)) if abn else None,
        "mean_abnormal": statistics.fmean(abn) if abn else None,
        "median_abnormal": statistics.median(abn) if abn else None,
        "mean_abnormal_1d": statistics.fmean(abn1) if abn1 else None,
        "by_session": {b: int(buckets.get(b, 0)) for b in BUCKETS},
        **({} if abn else {"unmeasured": "no filing that day has a measured abnormal reaction"}),
    }


def breadth(latest: Mapping[str, Mapping[str, Any]], now: datetime) -> dict[str, Any]:
    """Per US date: filers, share of positive abnormal reactions, mean/median abnormal return
    (window `abn_ret_open`: pre-close -> first close after the next open, net of US500) and the
    count by session bucket. Keyed by the filing's US/Eastern date (`days`) and by the reaction
    session it priced into (`by_reaction_date`), which is the date an index family trades on."""
    by_us: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    by_rx: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for r in latest.values():
        if r.get("us_date"):
            by_us[str(r["us_date"])].append(r)
        if r.get("next_open_date"):
            by_rx[str(r["next_open_date"])].append(r)
    return {"generated_at": _iso(now), "organ": ORGAN, "lane": "event", "benchmark": BENCH,
            "window": "abn_ret_open", "rows": len(latest),
            "days": {d: _agg(by_us[d]) for d in sorted(by_us)},
            "by_reaction_date": {d: _agg(by_rx[d]) for d in sorted(by_rx)}}


# ------------------------------------------------------------------------------ the pass
def run(*, budget_s: float = 240.0, offline: bool = False, paths: Paths | None = None,
        getter: Getter | None = None, loader: Loader | None = None,
        is_equity: Callable[[str], bool] | None = None, ticker_table: Mapping[str, str] | None
        = None, now: datetime | None = None, sleep: Callable[[float], None] = time.sleep,
        write: bool = True) -> dict[str, Any]:
    paths = paths or Paths()
    now = now or _now()
    t0 = time.monotonic()
    deadline = t0 + max(1.0, float(budget_s))
    fetch_deadline = t0 + max(1.0, float(budget_s) * FETCH_SHARE)
    loader = loader or _read_bars
    census: dict[str, Any] = {"organ": ORGAN, "at": _iso(now), "lane": "event",
                              "mints_hypotheses": False, "offline": bool(offline),
                              "user_agent_declared": bool(os.environ.get(UA_ENV, "").strip()),
                              "refused": [], "fetch_failures": [], "fetched_ciks": 0,
                              "tickers_fetched": False}
    state = _read_json(paths.state) or {}
    universe_doc = _read_json(paths.universe) or {}
    symbols = share_cfds(universe_doc if isinstance(universe_doc, dict) else {}, is_equity)
    census["share_cfds"] = len(symbols)

    fetcher: Fetcher | None = None
    why_no_net = ""
    census["robots_stops"] = []

    def hard_stop(exc: HardStop) -> None:
        census["refused"].append({"url": exc.url, "status": exc.status, "at": _iso(now)})
        state["blocked"] = {"url": exc.url, "status": exc.status, "at": _iso(now)}
        state["last_refusal"] = state["blocked"]

    def robots_stop(exc: RobotsStop) -> None:
        census["robots_stops"].append({"url": exc.url, "label": exc.label, "why": exc.why,
                                       "at": _iso(now)})

    if offline:
        why_no_net = "--offline"
    else:
        ok, why = machine_use(TICKERS_URL)
        if not ok:
            why_no_net = f"HARD BOUNDARY: {why}"
        else:
            fetcher = Fetcher(getter, deadline=fetch_deadline, sleep=sleep)
            blocked = state.get("blocked")
            if isinstance(blocked, dict) and blocked.get("url"):
                # A host that refused us stays closed until its robots.txt, read afresh, admits
                # us again: no fixed timer, and the refusing URL itself is not retried to find out.
                try:
                    fetcher.robots_read(str(blocked["url"]))
                    state.pop("blocked", None)
                    census["unblocked"] = {"after": blocked, "robots": "admits"}
                except HardStop as exc:
                    hard_stop(exc)
                    why_no_net = f"still refused: {exc}"
                    fetcher = None
                except RobotsStop as exc:
                    robots_stop(exc)
                    why_no_net = f"blocked since {blocked.get('at')}: {exc}"
                    fetcher = None
    census["network"] = {"used": fetcher is not None, "why_not": why_no_net}

    try:
        sec = load_sec_tickers(paths, fetcher, now, census)
    except (HardStop, RobotsStop) as exc:
        if isinstance(exc, HardStop):
            hard_stop(exc)
        else:
            robots_stop(exc)
        fetcher = None
        sec = load_sec_tickers(paths, None, now, census)
    mapping, unmapped = map_tickers(symbols, sec, ticker_table)
    census["mapped"] = {s: m["ticker"] for s, m in sorted(mapping.items())}
    census["unmapped"] = dict(sorted(unmapped.items()))
    if not sec:
        census["unmapped_reason"] = "no SEC ticker table (never fetched and no cache)"

    ciks = sorted({int(m["cik"]) for m in mapping.values()})
    if fetcher is not None and ciks:
        due, cursor = due_ciks(paths, ciks, int(state.get("cursor") or 0), now)
        census["due_ciks"] = len(due)
        done_upto = 0
        for i, cik in enumerate(due):
            if time.monotonic() >= fetch_deadline:
                census["fetch_stopped"] = "fetch share of the budget spent"
                break
            try:
                got = fetch_cik(paths, fetcher, cik, now)
            except HardStop as exc:
                hard_stop(exc)
                break
            except RobotsStop as exc:
                robots_stop(exc)
                break
            if got is not None:
                census["fetched_ciks"] += 1
            done_upto = i + 1
        # resume at the first CIK this pass did not reach, else where the rotation stopped
        state["cursor"] = cursor if done_upto >= len(due) else ciks.index(due[done_upto])
        census["fetch_failures"] = fetcher.failed[:20]
        census["requests"] = fetcher.fetched

    filings_by_symbol: dict[str, list[dict[str, Any]]] = {}
    cached_ciks = 0
    for sym, m in mapping.items():
        doc = _read_json(paths.cik_file(int(m["cik"])))
        if isinstance(doc, dict):
            cached_ciks += 1
            filings_by_symbol[sym] = [f for f in doc.get("filings") or [] if isinstance(f, dict)
                                      and f.get("accession") and has_item(f.get("items"))]
    census["ciks_cached"] = cached_ciks
    census["filings"] = len({f["accession"] for fs in filings_by_symbol.values() for f in fs})

    existing = latest_by_accession(read_rows(paths.rows))
    new, stats = build_rows(filings_by_symbol, mapping, existing, loader, now, deadline)
    latest = dict(existing)
    for r in new:
        latest[r["accession"]] = r
    census["join"] = stats
    census["rows_appended"] = len(new)
    census["rows_total"] = len(latest)
    census["joined_rows"] = sum(1 for r in latest.values()
                                if isinstance(r.get("ret_open"), float))
    census["rows_final"] = sum(1 for r in latest.values() if _is_final(r))
    census["elapsed_s"] = round(time.monotonic() - t0, 2)
    bd = breadth(latest, now)
    census["breadth_days"] = len(bd["days"])
    if write:
        append_rows(paths.rows, new)
        _write_json(paths.breadth, bd)
        _write_json(paths.state, state)
        _write_json(paths.census, census)
    return census


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SEC 8-K 2.02 acceptance -> share-CFD reaction rows")
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--offline", action="store_true", help="fetch nothing; join the cache")
    ap.add_argument("--dry-run", action="store_true", help="measure and print; write nothing")
    a = ap.parse_args(argv)
    budget = a.budget_s
    env_cap = os.environ.get("QUANT_LEG_BUDGET_S")
    if env_cap:
        with contextlib.suppress(ValueError):
            budget = min(budget, max(30.0, float(env_cap) - 30.0))
    c = run(budget_s=budget, offline=a.offline, write=not a.dry_run)
    print(f"{ORGAN} at={c['at']} elapsed={c['elapsed_s']}s network={c['network']}")
    print(f"  share CFDs {c['share_cfds']}  mapped {len(c['mapped'])}  unmapped "
          f"{len(c['unmapped'])}  fetched {c['fetched_ciks']}  refused {len(c['refused'])}")
    print(f"  filings {c['filings']}  appended {c['rows_appended']}  rows {c['rows_total']}  "
          f"joined {c['joined_rows']}  final {c['rows_final']}  breadth days {c['breadth_days']}")
    return 0


if __name__ == "__main__":                                       # pragma: no cover - CLI
    raise SystemExit(main())
