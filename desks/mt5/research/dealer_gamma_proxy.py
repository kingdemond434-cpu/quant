"""DEALER_GAMMA_PROXY -- dealer gamma, option OI and implied vol from free exchange files, as
point-in-time daily series the judge can condition MT5 instruments on.

    python desks/mt5/research/dealer_gamma_proxy.py --ingest     # organs battery: fetch + publish
    python desks/mt5/research/dealer_gamma_proxy.py              # daily proposer: test + donate
    python desks/mt5/research/dealer_gamma_proxy.py --dry-run    # measure, write nothing

WHAT IT MEASURES. For each options book it can read lawfully it computes, at the underlying's
own spot, the standard public dealer-gamma estimate (dealers long the calls and short the puts
customers trade):

    net GEX per 1% = sum_calls(gamma * OI * mult * S^2 * 0.01) - sum_puts(same)

plus the zero-gamma flip (where net GEX changes sign on a +-15% spot grid), the call and put
walls (largest OI strike), the put/call OI ratio and the OI-weighted at-the-money implied vol.
Normalised columns -- `net_gex_norm` (net / gross, in [-1, 1]), `flip_dist` ((spot - flip) /
spot), `pcr_oi`, `atm_iv`, `call_wall_dist`, `put_wall_dist` -- are what the cells read, because
contract sizes differ by orders of magnitude across books.

WHERE IT LANDS. Every ingest writes:
  desks/mt5/data/dealer_gamma_proxy.json          the latest reading per book + the source census
  desks/mt5/data/dealer_gamma/history.jsonl       one row per (book, day), append-only, deduped
  desks/mt5/data/lake/series/dealer_gamma_<SYM>.parquet   the PIT series (`available_time` UTC)
                                                   that `family_exogenous_conditioner` reads

HKEX serves about two days of daily reports and Deribit only the present book, so the history
is SELF-RECORDED: the box must run the ingest every day or the days are lost for good. That is
why it is on the organs battery (hourly rotation, idempotent per day) and not a weekly job.

THE CELLS ARE PRE-DECLARED, NOT MINED (signs fixed here before any data is seen):
  gamma_regime_drift   net_gex_norm level_z; long when dealers are long gamma (vol suppressed,
                       dips bought by hedgers), short when short gamma (hedgers sell into falls)
  gamma_flip_distance  flip_dist level_z; above the flip is the long-gamma side, same sign
  put_call_oi_tilt     pcr_oi level_z; a heavily hedged book is a fearful crowd -- fade it
A cell is donated only once its series holds MIN_HISTORY_DAYS observations and its own
(series, instrument) passed the shuffled-date placebo gain test (`libs.research.nlp_gain_test`),
exactly as `nlp_social_cells` does; before that it is WAITING_FOR_HISTORY, a count of days.

THE FETCH GATE (LAWS 5e act 6). A host is fetched only with its terms on record in TERMS (verbatim
quote, URL, date read); REFUSED_HOSTS never; robots.txt is read at fetch time under an honest
agent and fails closed (only 404/410 means no rules; HTML or any other status refuses);
401/403/429/451 is a hard stop for the run. Cboe is refused (cdn-api answered 403, 2026-11-24).
Crypto option books are reference data informing the MT5 crypto CFDs only (MT5 mandate).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.robotparser
from collections.abc import Callable
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE = "dealer_gamma_proxy"
DATA = DESK / "data"
SNAPSHOT = DATA / "dealer_gamma_proxy.json"
HISTORY = DATA / "dealer_gamma" / "history.jsonl"
SERIES_DIR = DATA / "lake" / "series"
REPORT = DESK / "reports" / "DEALER_GAMMA_CELLS.json"
MIN_HISTORY_DAYS = 60
HORIZONS = (1, 5)
SIGNALS = ("net_gex_norm", "flip_dist", "pcr_oi", "atm_iv", "call_wall_dist", "put_wall_dist")

ROBOTS_AGENT = "quant-desk-research"
HONEST_UA = f"{ROBOTS_AGENT}/1.0 (dealer gamma research; daily public files; honours robots.txt)"
TIMEOUT_S = 30

#: The terms on record for every host this module contacts. A host absent here is never fetched.
TERMS: dict[str, dict[str, str]] = {}

#: Hosts refused by their own terms or by a hard stop; kept so no later edit points a feed at them.
REFUSED_HOSTS: dict[str, str] = {
    "cdn.cboe.com": "Cboe: refused desk-wide (refused_hosts); cdn-api answered 403 2026-11-24",
    "cdn-api.cboe.com": "Cboe: answered 403 on 2026-11-24; refused, never retried",
    "www.cboe.com": "Cboe: refused desk-wide (refused_hosts)",
    # Read 2026-11-24 (/mnt/project-files/terms/gamma_sources_terms_2026-11-24.md). Each host's
    # own terms ban automated collection or non-personal reuse; robots allows the paths on most.
    "www.hkex.com.hk": "HKEX Terms of Use (19 Aug 2025): 'not permitted to conduct ... any text "
                       "or data mining or web scraping'; no 'programmatic ... means'",
    "www.deribit.com": "Deribit Terms 27.1(i) (26 Jan 2026): no 'systematic or automated data "
                       "collection'; 2.10 market data 'for personal use only'",
    "www.cmegroup.com": "CME Data Terms (7 Sep 2023): 'personal use for non-commercial purposes'; "
                        "harvesting 'strictly prohibited'",
    "www.okx.com": "OKX API Agreement (28 Jul 2026): Market Data 'solely for your own personal, "
                   "non-commercial trading', unauthenticated endpoints included",
    "api.bybit.com": "Bybit T&C 6.3(k) (16 Oct 2026): no 'robot, spider ... automatic device'",
    "www.jpx.co.jp": "JPX Terms (29 Jul 2026): 'refrain from automatic information retrieval'",
    "www.nseindia.com": "NSE Terms cl. 9 (29 Oct 2025): no 'systematic or automated data "
                        "collection'",
    "www.eurex.com": "Eurex disclaimer: single copy 'for personal, non-commercial use only'",
}

#: Seconds between requests to one host.
PACE_S: dict[str, float] = {}

Getter = Callable[..., Any]


def _default_get() -> Getter:
    import requests
    return requests.get


class Feed:
    """One run's fetcher: terms, robots (fail closed), honest agent, pacing, hard stops."""

    def __init__(self, get: Getter | None = None, *, pace_s: float | None = None) -> None:
        self.get = get or _default_get()
        self.pace_s = pace_s
        self.refused: dict[str, str] = {}
        self.errors: dict[str, str] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None | str] = {}
        self._last: dict[str, float] = {}

    def refusal(self, url: str) -> str | None:
        parts = urllib.parse.urlsplit(url)
        host = parts.netloc
        if host in REFUSED_HOSTS:
            return f"TERMS_REFUSED: {REFUSED_HOSTS[host]}"
        if host not in TERMS:
            return "TERMS_UNCONFIRMED: no terms on record for this host"
        if host in self.refused and self.refused[host].startswith("HARD_STOP"):
            return self.refused[host]
        if host not in self._robots:
            try:
                resp = self.get(f"{parts.scheme}://{host}/robots.txt",
                                headers={"User-Agent": HONEST_UA}, timeout=TIMEOUT_S)
                status = getattr(resp, "status_code", None)
                body = str(getattr(resp, "text", "") or "")
                if status in (404, 410):
                    self._robots[host] = None
                elif status != 200:
                    self._robots[host] = f"ROBOTS_REFUSED: robots.txt answered {status}"
                elif body.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
                    self._robots[host] = "ROBOTS_REFUSED: robots.txt answered HTML"
                else:
                    rp = urllib.robotparser.RobotFileParser()
                    rp.parse(body.splitlines())
                    self._robots[host] = rp
            except Exception as exc:                        # an unreadable gate refuses
                self._robots[host] = f"ROBOTS_REFUSED: robots.txt unreadable ({type(exc).__name__})"
        rule = self._robots[host]
        if isinstance(rule, str):
            return rule
        if rule is not None and not rule.can_fetch(ROBOTS_AGENT, url):
            return f"ROBOTS_REFUSED: robots.txt disallows {parts.path}"
        return None

    def _pace(self, host: str) -> None:
        gap = self.pace_s if self.pace_s is not None else PACE_S.get(host, 1.5)
        wait = self._last.get(host, 0.0) + gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last[host] = time.monotonic()

    def fetch(self, url: str, *, as_json: bool = False) -> Any:
        host = urllib.parse.urlsplit(url).netloc
        why = self.refusal(url)
        if why:
            self.refused[host] = why
            return None
        self._pace(host)
        try:
            resp = self.get(url, headers={"User-Agent": HONEST_UA}, timeout=TIMEOUT_S)
        except Exception as exc:
            self.errors[host] = f"{type(exc).__name__}"
            return None
        status = getattr(resp, "status_code", None)
        if status in (401, 403, 429, 451):                  # a hard stop: never retried this run
            self.refused[host] = f"HARD_STOP: HTTP {status}"
            return None
        if status != 200:
            self.errors[host] = f"HTTP {status}"
            return None
        if as_json:
            try:
                return resp.json()
            except ValueError:
                self.errors[host] = "unparseable JSON"
                return None
        content = getattr(resp, "content", None)
        if isinstance(content, bytes | bytearray):
            return bytes(content).decode("latin-1")
        return str(getattr(resp, "text", "") or "")


# ------------------------------------------------------------------------------------- the math
Row = tuple[float, float, float, float, bool]          # (strike, T years, iv, OI, is_call)


def bs_gamma(s: float, k: float, t: float, iv: float) -> float:
    if s <= 0 or k <= 0 or t <= 0 or iv <= 0:
        return 0.0
    d1 = (math.log(s / k) + 0.5 * iv * iv * t) / (iv * math.sqrt(t))
    return math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi) / (s * iv * math.sqrt(t))


def _net_gross(rows: list[Row], s: float, mult: float) -> tuple[float, float]:
    net = gross = 0.0
    for k, t, iv, oi, call in rows:
        v = bs_gamma(s, k, t, iv) * oi * mult * s * s * 0.01
        net += v if call else -v
        gross += v
    return net, gross


def profile(rows: list[Row], spot: float, mult: float) -> dict[str, Any]:
    """Net GEX at spot, the zero-gamma flip, walls, put/call OI and OI-weighted ATM vol."""
    net, gross = _net_gross(rows, spot, mult)
    grid = [spot * (0.85 + 0.005 * i) for i in range(61)]
    vals = [_net_gross(rows, g, mult)[0] for g in grid]
    flip = None
    for (a, va), (b, vb) in zip(zip(grid, vals, strict=True), zip(grid[1:], vals[1:], strict=True),
                                strict=False):
        if va == 0 or (va < 0) != (vb < 0):
            flip = a + (b - a) * (abs(va) / ((abs(va) + abs(vb)) or 1.0))
            break
    call_oi: dict[float, float] = {}
    put_oi: dict[float, float] = {}
    for k, _t, _iv, oi, call in rows:
        d = call_oi if call else put_oi
        d[k] = d.get(k, 0.0) + oi
    call_wall = max(call_oi, key=lambda k: call_oi[k]) if call_oi else None
    put_wall = max(put_oi, key=lambda k: put_oi[k]) if put_oi else None
    near = [(oi, iv) for k, _t, iv, oi, _c in rows if abs(k / spot - 1.0) <= 0.03 and oi > 0]
    atm_iv = (sum(o * v for o, v in near) / sum(o for o, _ in near)) if near else None
    tc, tp = sum(call_oi.values()), sum(put_oi.values())
    return {
        "spot": round(spot, 4),
        "net_gex_per_1pct": round(net, 2),
        "gross_gex_per_1pct": round(gross, 2),
        "net_gex_norm": round(net / gross, 6) if gross > 0 else None,
        "regime": "POSITIVE_GAMMA" if net > 0 else "NEGATIVE_GAMMA",
        "zero_gamma_flip": round(flip, 4) if flip else None,
        "flip_dist": round((spot - flip) / spot, 6) if flip else None,
        "call_wall": call_wall, "put_wall": put_wall,
        "call_wall_dist": round(call_wall / spot - 1.0, 6) if call_wall else None,
        "put_wall_dist": round(put_wall / spot - 1.0, 6) if put_wall else None,
        "pcr_oi": round(tp / tc, 6) if tc > 0 else None,
        "atm_iv": round(atm_iv, 6) if atm_iv else None,
        "n_series": len(rows), "total_oi": round(tc + tp, 2),
    }


# ------------------------------------------------------------------------------------- sources
_MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
_MON = {m: i for i, m in enumerate(_MONTHS, 1)}


def hkex_expiry(mon: str) -> dt.date:
    """HSI/HSCEI index options expire on the second-last business day of the month."""
    m, y = mon.split("-")
    year, month = 2000 + int(y), _MON[m]
    d = dt.date(year + (month == 12), month % 12 + 1, 1) - dt.timedelta(days=1)
    biz = 0
    while True:
        if d.weekday() < 5:
            biz += 1
            if biz == 2:
                return d
        d -= dt.timedelta(days=1)


_HKEX_ROW = re.compile(r"^([A-Z]{3}-\d{2})\s+(\d+)\s+([CP])\s+(.*)$", re.M)


def parse_hkex(text: str, day: dt.date, mult: float) -> dict[str, Any] | None:
    """An HKEX daily index-option report -> profile. Spot by put-call parity on the front month."""
    recs = []
    for mon, k, cp, rest in _HKEX_ROW.findall(text):
        nums = [x for x in re.split(r"[\s|]+", rest.strip()) if x]
        try:
            oqp, iv, oi = float(nums[8]), float(nums[10]) / 100, float(nums[-2])
            _MON[mon.split("-")[0]]
        except (IndexError, ValueError, KeyError):
            continue
        recs.append((mon, float(k), cp == "C", oqp, iv, oi))
    if not recs:
        return None
    front = sorted({r[0] for r in recs}, key=hkex_expiry)[0]
    c = {r[1]: r[3] for r in recs if r[0] == front and r[2]}
    p = {r[1]: r[3] for r in recs if r[0] == front and not r[2]}
    ks = [k for k in c if k in p and c[k] > 0 and p[k] > 0]
    if not ks:
        return None
    k0 = min(ks, key=lambda k: abs(c[k] - p[k]))
    spot = k0 + c[k0] - p[k0]
    rows: list[Row] = []
    for mon, k, call, _oqp, iv, oi in recs:
        t = max((hkex_expiry(mon) - day).days, 0.5) / 365.0
        if oi > 0 and iv > 0:
            rows.append((k, t, iv, oi, call))
    if not rows or spot <= 0:
        return None
    out = profile(rows, spot, mult)
    out["front_month"] = front
    return out


def parse_deribit(payload: Any, now: dt.datetime) -> dict[str, Any] | None:
    """Deribit's public option book summary -> profile at the book's own underlying price."""
    res = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(res, list):
        return None
    rows: list[Row] = []
    spot = None
    for r in res:
        try:
            _, exp, k, cp = str(r["instrument_name"]).split("-")
            expiry = dt.datetime.strptime(exp, "%d%b%y").replace(hour=8, tzinfo=dt.UTC)
            t = max((expiry - now).total_seconds(), 3600.0) / 31_536_000.0
            oi, iv = float(r.get("open_interest") or 0), float(r.get("mark_iv") or 0) / 100
            spot = spot or float(r["underlying_price"])
        except (KeyError, ValueError, TypeError):
            continue
        if oi > 0 and iv > 0:
            rows.append((float(k), t, iv, oi, cp == "C"))
    if not rows or not spot:
        return None
    return profile(rows, spot, 1.0)


def _hkex_puller(code: str, mult: float) -> Callable[[Feed, dt.date, dt.datetime], Any]:
    def pull(feed: Feed, day: dt.date, now: dt.datetime) -> dict[str, Any] | None:
        text = feed.fetch(f"https://www.hkex.com.hk/eng/stat/dmstat/dayrpt/{code}{day:%y%m%d}.htm")
        return parse_hkex(text, day, mult) if text else None
    return pull


def _deribit_puller(cur: str) -> Callable[[Feed, dt.date, dt.datetime], Any]:
    def pull(feed: Feed, day: dt.date, now: dt.datetime) -> dict[str, Any] | None:
        payload = feed.fetch("https://www.deribit.com/api/v2/public/get_book_summary_by_currency"
                             f"?currency={cur}&kind=option", as_json=True)
        return parse_deribit(payload, now) if payload else None
    return pull


#: (book, MT5 symbol, host, end_of_day, puller). end_of_day books are read for the last few
#: weekdays (HKEX publishes after its close and keeps ~2 days); live books once per run.
BOOKS: tuple[tuple[str, str, str, bool, Callable[[Feed, dt.date, dt.datetime], Any]], ...] = (
    ("hkex_hsio", "HK50", "www.hkex.com.hk", True, _hkex_puller("hsio", 50.0)),
    ("hkex_hhio", "CHINAH", "www.hkex.com.hk", True, _hkex_puller("hhio", 50.0)),
    ("deribit_btc", "BTCUSD", "www.deribit.com", False, _deribit_puller("BTC")),
    ("deribit_eth", "ETHUSD", "www.deribit.com", False, _deribit_puller("ETH")),
)
EOD_LOOKBACK_DAYS = 4


# --------------------------------------------------------------------------------------- ingest
def _read_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text("utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def _available_time(book_eod: bool, day: dt.date, now: dt.datetime) -> str:
    """When the reading was knowable. An EOD report is stamped at the END of its day (UTC) --
    never earlier than it could have been read -- and a live book at the moment it was read."""
    if book_eod:
        eod = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(0, 0), tzinfo=dt.UTC)
        return eod.isoformat()
    return now.isoformat(timespec="seconds")


def ingest(*, get: Getter | None = None, now: dt.datetime | None = None,
           data_dir: Path = DATA, series_dir: Path | None = None,
           pace_s: float | None = None) -> dict[str, Any]:
    """Pull every book through the gate, append new (book, day) rows, publish the PIT series."""
    now = now or dt.datetime.now(dt.UTC)
    feed = Feed(get, pace_s=pace_s)
    hist_path = data_dir / "dealer_gamma" / "history.jsonl"
    snap_path = data_dir / "dealer_gamma_proxy.json"
    sdir = series_dir or data_dir / "lake" / "series"
    history = _read_history(hist_path)
    seen = {(r.get("book"), r.get("day")) for r in history}
    new: list[dict[str, Any]] = []
    census: dict[str, dict[str, Any]] = {}
    for book, sym, host, eod, pull in BOOKS:
        days = ([now.date() - dt.timedelta(days=i) for i in range(EOD_LOOKBACK_DAYS + 1)]
                if eod else [now.date()])
        got = 0
        for day in days:
            if day.weekday() >= 5 or (book, str(day)) in seen:
                continue
            try:
                prof = pull(feed, day, now)
            except Exception as exc:                    # one book failing never costs the rest
                feed.errors[host] = f"{type(exc).__name__}"
                prof = None
            if not prof:
                continue
            row = {"book": book, "symbol": sym, "day": str(day), "host": host,
                   "available_time": _available_time(eod, day, now),
                   "retrieval_time": now.isoformat(timespec="seconds"), **prof}
            new.append(row)
            seen.add((book, str(day)))
            got += 1
        state = ("LIVE" if got or any(r.get("book") == book for r in history) else
                 "REFUSED" if host in feed.refused else "MISSING")
        census[book] = {"symbol": sym, "host": host, "new_rows": got, "state": state,
                        "refusal": feed.refused.get(host), "error": feed.errors.get(host)}
    if new:
        hist_path.parent.mkdir(parents=True, exist_ok=True)
        with hist_path.open("a", encoding="utf-8") as fh:
            for row in new:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
    allrows = history + new
    published = publish_series(allrows, sdir)
    latest: dict[str, dict[str, Any]] = {}
    for r in allrows:
        b = str(r.get("book"))
        if b not in latest or str(r.get("day")) >= str(latest[b].get("day")):
            latest[b] = r
    snap = {"generated_at": now.isoformat(timespec="seconds"), "source": SOURCE,
            "books": census, "latest": latest, "history_rows": len(allrows),
            "new_rows": len(new), "series": published,
            "history_days": {b: sum(1 for r in allrows if r.get("book") == b) for b in census}}
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = snap_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(snap, indent=1, sort_keys=True), "utf-8")
    os.replace(tmp, snap_path)
    return snap


def publish_series(rows: list[dict[str, Any]], series_dir: Path) -> dict[str, int]:
    """One lake frame per MT5 symbol, one row per day (the latest book reading for that day)."""
    import pandas as pd

    by_sym: dict[str, dict[str, dict[str, Any]]] = {}
    for r in rows:
        sym, day = r.get("symbol"), r.get("day")
        if not sym or not day:
            continue
        prev = by_sym.setdefault(str(sym), {}).get(str(day))
        if prev is None or str(r.get("retrieval_time")) >= str(prev.get("retrieval_time")):
            by_sym[str(sym)][str(day)] = r
    out: dict[str, int] = {}
    for sym, per_day in by_sym.items():
        recs = [{"day": d, "available_time": r["available_time"], "source_id": r.get("book"),
                 **{c: r.get(c) for c in SIGNALS}} for d, r in sorted(per_day.items())]
        frame = pd.DataFrame.from_records(recs)
        frame["available_time"] = pd.to_datetime(frame["available_time"], utc=True)
        for c in SIGNALS:
            frame[c] = pd.to_numeric(frame[c], errors="coerce")
        series_dir.mkdir(parents=True, exist_ok=True)
        path = series_dir / f"dealer_gamma_{sym}.parquet"
        tmp = path.with_suffix(".tmp")
        frame.to_parquet(tmp, index=False)
        os.replace(tmp, path)
        out[sym] = len(frame)
    return out


# ---------------------------------------------------------------------------------------- cells
#: (cell, signal, threshold, side_when_high, ttl_bars, mechanism, payer). Signs are declared here,
#: before any data, and never re-signed by a result.
CELLS: tuple[tuple[str, str, float, int, int, str, str], ...] = (
    ("gamma_regime_drift", "net_gex_norm", 1.0, 1, 24,
     "dealers long gamma buy dips and sell rips (vol suppressed, positive drift); short gamma "
     "they sell into falls and buy into rallies, so downside extends",
     "option dealers delta-hedging their gamma on the exchange's own book"),
    ("gamma_flip_distance", "flip_dist", 1.0, 1, 24,
     "spot far above the zero-gamma flip sits in the dealers' stabilising zone; far below it in "
     "their destabilising zone",
     "option dealers delta-hedging their gamma on the exchange's own book"),
    ("put_call_oi_tilt", "pcr_oi", 1.5, 1, 48,
     "an extreme put/call open-interest ratio is a crowd already hedged; its fear is priced and "
     "the hedges' decay pays the other side",
     "hedgers paying for downside protection at an extreme"),
)


def _series_index(sym: str, col: str, series_dir: Path) -> Any:
    import pandas as pd

    path = series_dir / f"dealer_gamma_{sym}.parquet"
    if not path.exists():
        return None
    try:
        frame = pd.read_parquet(path)
    except (OSError, ValueError, ImportError):
        return None
    if col not in frame.columns:
        return None
    s = pd.Series(pd.to_numeric(frame[col], errors="coerce").to_numpy(),
                  index=pd.to_datetime(frame["day"], errors="coerce")).dropna()
    return s[~s.index.duplicated(keep="last")].sort_index() if len(s) else None


def declared(series_dir: Path = SERIES_DIR) -> tuple[dict[str, Any], list[tuple[str, str]],
                                                     list[dict[str, Any]]]:
    """(indices, (index, instrument) pairs, every declared cell with its history count)."""
    indices: dict[str, Any] = {}
    pairs: list[tuple[str, str]] = []
    cells: list[dict[str, Any]] = []
    for sym in sorted({b[1] for b in BOOKS}):
        for name, col, thr, side, ttl, mech, payer in CELLS:
            idx = f"gamma:{sym}.{col}"
            s = _series_index(sym, col, series_dir)
            n = 0 if s is None else len(s)
            if s is not None:
                indices[idx] = s
                pairs.append((idx, sym))
            cells.append({
                "cell_name": name, "symbol": sym, "index": idx, "history_days": n,
                "params": {"source": f"dealer_gamma_{sym}", "signal": col,
                           "transform": "level_z", "threshold": thr, "side_when_high": side,
                           "ttl_bars": ttl, "lag_hours": 24},
                "mechanism": f"{mech} ({sym})", "payer": payer,
                "economic_actor": "hedging_dealer", "information_source": "options_book",
                "constraint": "dealers must re-hedge delta as spot moves through their gamma"})
    return indices, sorted(set(pairs)), cells


def run(*, dry_run: bool = False, series_dir: Path = SERIES_DIR, out: Path = REPORT,
        n_placebo: int = 200, n_boot: int = 300) -> dict[str, Any]:
    """The daily proposer half: gain-test every ready series, donate the cells that passed."""
    indices, pairs, cells = declared(series_dir)
    ready = [c for c in cells if c["history_days"] >= MIN_HISTORY_DAYS]
    grid: dict[str, Any] = {"tests": [], "n_trials": 0, "verdict": "UNMEASURED"}
    if ready:
        from nlp_social_cells import daily_closes  # type: ignore[import-not-found]

        from libs.research import nlp_gain_test as gt
        closes = {sym: c for sym in sorted({c["symbol"] for c in ready})
                  if (c := daily_closes(sym)) is not None}
        rp = [(i, s) for i, s in pairs if any(c["index"] == i for c in ready)]
        grid = gt.gain_grid({i: indices[i] for i, _ in rp}, closes, rp, horizons=HORIZONS,
                            n_placebo=n_placebo, n_boot=n_boot, seed=20261124)
    passed = {(t.get("index"), t.get("instrument")) for t in grid.get("tests") or []
              if t.get("gain") is True}
    donate = [c for c in ready if (c["index"], c["symbol"]) in passed]
    rep: dict[str, Any] = {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "verdict": grid.get("verdict"), "n_trials": grid.get("n_trials", 0),
        "cells_declared": len(cells), "cells_proposed": len(donate),
        "cells_waiting_for_history": [{"cell": c["cell_name"], "symbol": c["symbol"],
                                       "history_days": c["history_days"],
                                       "needs": MIN_HISTORY_DAYS}
                                      for c in cells if c["history_days"] < MIN_HISTORY_DAYS],
        "cells_failed_gain": [{"cell": c["cell_name"], "symbol": c["symbol"]}
                              for c in ready if c not in donate],
        "dry_run": dry_run}
    if donate and not dry_run:
        from research import proposer_common as pc
        cands = []
        for c in donate:
            cand = pc.candidate(SOURCE, c["symbol"], "exogenous_conditioner", dict(c["params"]),
                                c["mechanism"],
                                title=f"{c['cell_name']} {c['symbol']} <- "
                                      f"{c['params']['source']}.{c['params']['signal']}",
                                evidence={"history_days": c["history_days"]})
            for k in ("cell_name", "payer", "economic_actor", "constraint",
                      "information_source"):
                cand[k] = c[k]
            cand["chart"] = "H1"
            cand["falsifier"] = (f"{c['params']['signal']} of {c['params']['source']} has no "
                                 f"measurable relation to {c['symbol']} out of sample")
            cand["required_data"] = [
                f"desks/mt5/data/lake/series/{c['params']['source']}.parquet"]
            cands.append(cand)
        rep["donated"] = str(pc.donate(SOURCE, cands, int(grid.get("n_trials", 0)) + len(cands)))
    if not dry_run:
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".tmp")
        tmp.write_text(json.dumps(rep, indent=1, default=str), "utf-8")
        os.replace(tmp, out)
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--ingest", action="store_true", help="fetch + publish only (battery)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.ingest:
        snap = ingest()
        print(json.dumps({"new_rows": snap["new_rows"], "books": snap["books"]}, default=str))
        return 0
    rep = run(dry_run=a.dry_run)
    print(f"dealer_gamma_proxy: {rep['cells_proposed']} cell(s) proposed of "
          f"{rep['cells_declared']}; {len(rep['cells_waiting_for_history'])} waiting for history")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
