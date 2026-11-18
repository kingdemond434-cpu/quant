#!/usr/bin/env python3
"""CHINA AND HONG KONG STRUCTURAL STATE -- the fix gap, the band edge and the closure calendar.

    python desks/mt5/research/cn_hk_structural_state.py --once
    python desks/mt5/research/cn_hk_structural_state.py --once --offline   # held data only
    python desks/mt5/research/cn_hk_structural_state.py --once --dry-run   # build, mint nothing

Build-check rows 107 (China structural cells) and 108 (Stock Connect flow cells), one hourly leg.

WHAT IT BUILDS, each as a stamped series in `data/lake/series/<id>.parquet` and, through the one
registry door (`libs.moat.registry.enqueue_candidate`), as `exogenous_conditioner` cells on the
targets the account quotes (USDCNH, HK50, CHINAH). Each cell is minted ONCE in its life.

  * `cn_parity_dev` -- USDCNH just before the fix minus the central parity, in pips and percent,
    and the BAND STATE: the deviation as a fraction of the +/-2% onshore band, plus a signed
    edge level (0 inside half the band, 1 past half, 2 past 75%, 3 past 90%). The band binds the
    ONSHORE price, which this broker does not quote, so the offshore deviation measures pressure
    against the band. It is not the band's own position.
  * `cn_golden_week` -- trading days to the National Day closure and since its reopening (within
    a 15-day window, empty outside it), the length of the next mainland closure, and a flag for a
    weekday on which the mainland is shut while HK50, CHINAH and USDCNH trade.

THE PARITY SOURCE, AND WHY IT IS NOT CFETS OR THE PBOC SITE. CFETS (chinamoney.com.cn) is refused
on terms (#250). The PBOC's own site (pbc.gov.cn) was checked 2026-11-18. The container's proxy
refuses a CONNECT to it, and the fetch agent reported `robots_disallowed` for the host, the home
page and the English index. The site statement could not be read, so its terms are UNREAD.
The row stays HELD and nothing is fetched from it. Each pass reads pbc.gov.cn/robots.txt once
a day under this module's own UA and records the verdict, so the hold has evidence behind it.
The parity is taken instead from the BIS, which republishes the PBOC's reported daily USD/CNY
rate in `WS_XRU` (`D.CN.CNY.A`). The BIS terms were read on the box 2026-11-11 (data.bis.org
help/legal: use is unrestricted when the BIS is cited); `futures_state_sources.json` row
`bis_stats` records that reading. The vault established that this BIS CNY leg is the onshore
fix and not a clock-shifted CNH (data_axis_watchlist card 79). Card 85 names the residual as
the CNH-CNY basis axis that this module builds.

POINT IN TIME. The parity is announced at 09:15 Beijing (01:15 UTC) and the row is stamped
01:30 UTC on its day. The CNH side is the close of the last H1 bar that ENDS by 01:00 UTC, with
broker stamps converted by `libs.regime.session_clock.server_to_utc`, so neither leg is seen
before it existed. The BIS delivers the value days later. That delay limits live freshness
(reported as `parity_age_days`), never the stamp. The closure calendar is the State Council's
published arrangement in `countries/cn/pack.py` (2026 is DERIVED there and labelled so), stamped
00:00 UTC on the day it describes.

FENCED, NOT FETCHED (their clauses verbatim in `FENCES` and in the report):
  * HKEX Stock Connect daily northbound/southbound flows: TERMS_BLOCKED. HKEX's terms of use,
    section 5, forbid any bot or scraper and any "programmatic, scripted or other mechanical
    means" of access, and allow personal use only.
  * Mainland limit-breadth (the count of A-shares at the daily limit): TERMS_BLOCKED on the SSE's
    own legal statement, which allows only non-commercial browsing and downloading and names
    "电子抓取系统" among the restricted uses. The SZSE statement could not be read (TO_CONFIRM).
    One exchange is blocked, so no whole-market breadth series is built, and none is faked from
    index bars.

UNMEASURED IS AN ANSWER. No bars on this host, no parity held, a refused robots file: each is
named in `reports/CN_HK_STRUCTURAL_STATE.json` and mints nothing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.robotparser
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

STATE_DIR = DESK / "data" / "cn_hk_state"
RAW_PARITY = STATE_DIR / "bis_cny_parity.parquet"
STATE = STATE_DIR / "state.json"
SERIES = DESK / "data" / "lake" / "series"
OUT = DESK / "reports" / "CN_HK_STRUCTURAL_STATE.json"

UA = "quant-research/1.0 (+https://github.com/kingdemond434-cpu/quant; cn_hk_structural_state)"
HARD_STOP = frozenset({401, 403, 429, 451})
BIS_URL = ("https://stats.bis.org/api/v1/data/WS_XRU/D.CN.CNY.A"
           "?format=csv&detail=dataonly&startPeriod={start}")
BIS_HISTORY_START = "2015-08-11"     # the fix reform; the formula before it is another regime
BIS_REFETCH_H = 20
BIS_MAX_CHARS = 1_900_000
PBOC_ROBOTS_URL = "https://www.pbc.gov.cn/robots.txt"
PBOC_PARITY_PATH = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/index.html"
PBOC_ROBOTS_EVERY_H = 24

#: The quoted targets. CN50 (FTSE China A50) is named by the build row but the account's MT5
#: registry has no such symbol, so it stays as a target the mint reports UNQUOTED.
TARGETS: tuple[str, ...] = ("USDCNH", "HK50", "CHINAH", "CN50")
TRANSFORMS: tuple[str, ...] = ("level_z", "delta", "delta_z")
CHARTS: tuple[str, ...] = ("H1", "H4", "D1")
MIN_ROWS = 30
PCT_WINDOW = 250
BAND_PCT = 2.0                       # +/-2% around the parity since 2014-03-17
FIX_UTC = (1, 15)                    # 09:15 Beijing
STAMP_PAD_MIN = 15
GW_WINDOW = 15                       # trading days either side of the National Day block
MAX_MINT_PER_PASS = 500
CNY_SANE = (5.0, 9.5)                # CNY per USD; anything outside is a key or unit error

#: Sources this module will NOT fetch, each with the reading that settled it.
FENCES: tuple[dict[str, Any], ...] = (
    {"id": "hkex_stock_connect_flows", "status": "TERMS_BLOCKED", "row": 108,
     "url": "https://www.hkex.com.hk/Global/Exchange/Terms-of-Use?sc_lang=en",
     "read": "2026-11-18, HKEX Terms of Use section 5 (read by the fetch agent; the container "
             "proxy refuses a CONNECT to hkex.com.hk)",
     "clause": ("You are not permitted to conduct, facilitate, enable, authorise or permit any "
                "text or data mining or web scraping in relation to this Website or any "
                "services provided via, or in relation to, this Website for any purpose ... "
                "This includes using, permitting, authorising or attempting the use of: (i) any "
                "\"robot\", \"bot\", \"spider\", \"scraper\" or other automated device, program, "
                "tool, algorithm, code, process or methodology to access, obtain, copy, monitor "
                "or republish any portion of the Website or any Information accessed via the "
                "same ... (iii) use any programmatic, scripted or other mechanical means to "
                "access this Website or any Information"),
     "permitted": ("download, print, store temporarily, retrieve and display Information ... "
                   "for your personal use"),
     "targets": ("HK50", "CHINAH", "USDCNH"),
     "what_it_would_be": "daily northbound and southbound net buying, PIT-stamped at the HK "
                         "close, as a flow state for HK50, CHINAH and USDCNH"},
    {"id": "sse_limit_breadth", "status": "TERMS_BLOCKED", "row": 107,
     "url": "https://www.sse.com.cn/home/legal/",
     "read": "2026-11-18, SSE 法律声明 section 3 (read by the fetch agent)",
     "clause": (  # verbatim, full-width punctuation kept as published
         "在遵守中国有关法律与本声明的前提下，任何机构或者个人可基于非商业目的浏览、下"  # noqa: RUF001
         "载本网站的内容。未经上海证券交易所书面许可，任何机构或者个人不得以向他人出售"  # noqa: RUF001
         "牟利为目的，使用本网站的任何内容，此种使用包括但不限于拷贝、下载、存贮、通过"  # noqa: RUF001
         "硬拷贝或电子抓取系统获取、发送、转换、出租、演示、转载、复制、修改、销售、传"
         "播、出版或任何其它形式的散发。"),
     "permitted": "non-commercial browsing and downloading",
     "targets": ("CHINAH", "HK50", "USDCNH"),
     "what_it_would_be": "the share of A-shares closing at the +/-10% (20% on STAR/ChiNext) "
                         "limit, the limit-breadth state"},
    {"id": "szse_limit_breadth", "status": "TO_CONFIRM", "row": 107,
     "url": "https://www.szse.cn/",
     "read": "2026-11-18: the legal statement page returned a client error to the fetch agent; "
             "terms UNREAD, so nothing is fetched",
     "clause": "", "permitted": "", "targets": ("CHINAH", "HK50", "USDCNH"),
     "what_it_would_be": "the Shenzhen half of limit-breadth"},
    {"id": "pboc_central_parity", "status": "HELD", "row": 107,
     "url": PBOC_PARITY_PATH,
     "read": "2026-11-18: the fetch agent reported robots_disallowed for www.pbc.gov.cn (robots, "
             "home page and English index); the container proxy refuses a CONNECT; the site "
             "statement is UNREAD. The box re-reads robots.txt daily under this module's UA "
             "(`pboc_robots` in the report); data is never fetched until the terms are read",
     "clause": "", "permitted": "", "targets": ("USDCNH", "HK50", "CHINAH"),
     "what_it_would_be": "the parity from its publisher. The BIS republication stands in"},
    {"id": "cfets_central_parity", "status": "TERMS_BLOCKED", "row": 107,
     "url": "https://www.chinamoney.com.cn/",
     "read": "refused on terms, PR #250", "clause": "see #250", "permitted": "",
     "targets": ("USDCNH",), "what_it_would_be": "the parity and the CFETS basket"},
)


class HardStop(Exception):
    def __init__(self, code: int, url: str):
        super().__init__(f"HTTP {code}")
        self.code, self.url = code, url


class FetchError(Exception):
    def __init__(self, code: int | None, url: str, why: str):
        super().__init__(why)
        self.code, self.url = code, url


def _now() -> datetime:
    return datetime.now(UTC)


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(p: Path, doc: Any) -> None:
    from research.futures_state import _replace
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str, ensure_ascii=False), encoding="utf-8")
    _replace(tmp, p)


def fetch_text(url: str, timeout: float = 40.0) -> str:
    """One honest GET through the desk's polite fetcher: own UA, no retry, refusal = hard stop.
    A host on `libs.data.refused_hosts` is never contacted."""
    from libs.data import polite_fetch, refused_hosts
    why = refused_hosts.refusal(url)
    if why:
        raise FetchError(None, url, f"refused host: {why}")
    r = polite_fetch.get(url, headers={"User-Agent": UA, "Accept": "text/csv,text/plain,*/*"},
                         timeout=timeout, retries=0, leg="cn_hk_structural_state")
    if r.status in HARD_STOP:
        raise HardStop(int(r.status or 0), url)
    if not r.ok:
        raise FetchError(r.status, url, r.error or f"HTTP {r.status}")
    return r.text


def robots_verdict(url: str, get_text: Callable[[str], str]) -> tuple[bool, str]:
    """(allowed, why) for this exact path under our own UA. A 404 robots allows (RFC 9309); any
    other failure to read it does not, so an unread policy is never a yes."""
    p = urllib.parse.urlsplit(url)
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.parse(get_text(f"{p.scheme}://{p.netloc}/robots.txt").splitlines())
    except HardStop as hs:
        return False, f"robots.txt answered HTTP {hs.code}"
    except FetchError as exc:
        if exc.code == 404:
            return True, "no robots.txt (404)"
        return False, f"robots.txt unreadable ({exc})"
    except Exception as exc:
        return False, f"robots.txt unreadable ({type(exc).__name__})"
    ok = rp.can_fetch(UA, url)
    return ok, "allowed for this UA and path" if ok else "Disallow for this UA and path"


# ------------------------------------------------------------------------------- parity ---
def parse_bis_xru(text: str) -> pd.Series:
    """BIS SDMX CSV for D.CN.CNY.A -> a daily Series of CNY per USD, indexed by date (UTC)."""
    import csv
    import io
    out: dict[pd.Timestamp, float] = {}
    try:
        rows = csv.DictReader(io.StringIO(text))
        if not {"TIME_PERIOD", "OBS_VALUE"} <= set(rows.fieldnames or []):
            return pd.Series(dtype=float)
        for r in rows:
            if r.get("REF_AREA") not in (None, "", "CN"):
                continue
            t = pd.to_datetime(str(r.get("TIME_PERIOD")), utc=True, errors="coerce")
            v = pd.to_numeric(r.get("OBS_VALUE"), errors="coerce")
            if pd.notna(t) and pd.notna(v):
                out[t.normalize()] = float(v)
    except csv.Error:
        return pd.Series(dtype=float)
    return pd.Series(out, dtype=float).sort_index()


def collect_parity(get_text: Callable[[str], str] | None, state: dict[str, Any],
                   notes: list[dict[str, Any]], now: datetime) -> pd.Series:
    held = pd.Series(dtype=float)
    if RAW_PARITY.exists():
        try:
            f = pd.read_parquet(RAW_PARITY)
            held = pd.Series(f["parity"].to_numpy(dtype=float),
                             index=pd.to_datetime(f["date"], utc=True))
        except (OSError, ValueError, KeyError):
            notes.append({"source": "bis_xru_cny", "status": "RAW_UNREADABLE"})
    last = pd.to_datetime(state.get("bis_last_fetch"), utc=True, errors="coerce")
    due = pd.isna(last) or (pd.Timestamp(now) - last) >= pd.Timedelta(hours=BIS_REFETCH_H)
    if get_text is None or not due or "bis_xru_cny" in state.get("hard_stops", {}):
        return held
    start = (BIS_HISTORY_START if held.empty
             else (held.index.max() - pd.Timedelta(days=45)).strftime("%Y-%m-%d"))
    url = BIS_URL.format(start=start)
    try:
        ok, why = robots_verdict(url, get_text)
        if not ok:
            notes.append({"source": "bis_xru_cny", "status": "UNMEASURED", "why": why})
            return held
        text = get_text(url)
        if len(text) >= BIS_MAX_CHARS:
            notes.append({"source": "bis_xru_cny", "status": "TRUNCATED"})
            return held
        new = parse_bis_xru(text)
        if new.empty:
            notes.append({"source": "bis_xru_cny", "status": "UNPARSED"})
            return held
        med = float(new.median())
        if not CNY_SANE[0] <= med <= CNY_SANE[1]:
            notes.append({"source": "bis_xru_cny", "status": "INSANE_UNITS", "median": med})
            return held
        merged = new.combine_first(held).sort_index()
        from research.futures_state import _atomic_parquet
        _atomic_parquet(RAW_PARITY, pd.DataFrame({"date": merged.index,
                                                  "parity": merged.to_numpy()}), index=False)
        state["bis_last_fetch"] = now.isoformat(timespec="seconds")
        return merged
    except HardStop as hs:
        state.setdefault("hard_stops", {})["bis_xru_cny"] = {
            "code": hs.code, "at": now.isoformat(timespec="seconds")}
    except FetchError as exc:
        notes.append({"source": "bis_xru_cny", "status": "NO_REPLY", "code": exc.code})
    except Exception as exc:
        notes.append({"source": "bis_xru_cny", "error": type(exc).__name__})
    return held


def pboc_robots(get_text: Callable[[str], str] | None, state: dict[str, Any],
                now: datetime) -> dict[str, Any]:
    """The PBOC hold's evidence: robots.txt read once a day under our UA. Data is never fetched."""
    prev = dict(state.get("pboc_robots") or {})
    last = pd.to_datetime(prev.get("at"), utc=True, errors="coerce")
    if get_text is None or (pd.notna(last) and
                            pd.Timestamp(now) - last < pd.Timedelta(hours=PBOC_ROBOTS_EVERY_H)):
        return prev or {"status": "NOT_READ", "why": "offline or not due"}
    ok, why = robots_verdict(PBOC_PARITY_PATH, get_text)
    doc = {"at": now.isoformat(timespec="seconds"), "path": PBOC_PARITY_PATH,
           "robots_allows": ok, "why": why,
           "data_fetched": False,
           "hold": "terms UNREAD: the parity is never fetched from pbc.gov.cn until the site "
                   "statement is read and recorded clean"}
    state["pboc_robots"] = doc
    return doc


def cnh_before_fix(bars: pd.DataFrame | None) -> pd.Series:
    """USDCNH close of the last H1 bar that ENDS by 01:00 UTC, per UTC date."""
    if bars is None or bars.empty or "close" not in bars.columns:
        return pd.Series(dtype=float)
    from libs.regime.session_clock import server_to_utc
    start = pd.DatetimeIndex(server_to_utc(pd.DatetimeIndex(bars.index)))
    end = start + pd.Timedelta(hours=1)
    close = pd.Series(pd.to_numeric(bars["close"], errors="coerce").to_numpy(), index=end)
    close = close[~close.index.duplicated(keep="last")].dropna().sort_index()
    cutoff_hour = FIX_UTC[0]
    days = close.index.normalize()
    ok = (close.index - days) <= pd.Timedelta(hours=cutoff_hour)
    pre = close[ok]
    return pre.groupby(pre.index.normalize()).last().astype(float)


def band_level(use: float) -> float:
    a = abs(use)
    lvl = 0.0 if a < 0.5 else 1.0 if a < 0.75 else 2.0 if a < 0.9 else 3.0
    return float(np.sign(use)) * lvl


def _rolling_pct(s: pd.Series, window: int = PCT_WINDOW) -> pd.Series:
    from research.futures_state import rolling_pct
    return rolling_pct(s, window)


def parity_frame(parity: pd.Series, cnh: pd.Series) -> pd.DataFrame:
    """One row per fix day with both legs held: the deviation, the band state and dynamics."""
    if parity.empty or cnh.empty:
        return pd.DataFrame()
    j = pd.DataFrame({"parity": parity, "cnh_pre_fix": cnh}).dropna()
    if j.empty:
        return pd.DataFrame()
    dev = j["cnh_pre_fix"] - j["parity"]
    dev_pct = (j["cnh_pre_fix"] / j["parity"] - 1.0) * 100.0
    use = dev_pct / BAND_PCT
    f = pd.DataFrame({
        "parity": j["parity"], "cnh_pre_fix": j["cnh_pre_fix"],
        "dev_pips": dev * 10_000.0, "dev_pct": dev_pct, "band_use": use,
        "band_edge_level": use.map(band_level),
        "parity_chg_pips": j["parity"].diff() * 10_000.0,
    }, index=j.index)
    f["dev_pips_chg"] = f["dev_pips"].diff()
    f["dev_pct_pct"] = _rolling_pct(f["dev_pct"])
    f["band_use_pct"] = _rolling_pct(f["band_use"].abs())
    stamp = (pd.DatetimeIndex(j.index).normalize()
             + pd.Timedelta(hours=FIX_UTC[0], minutes=FIX_UTC[1] + STAMP_PAD_MIN))
    f = f.reset_index(drop=True)
    f["event_time"] = pd.DatetimeIndex(j.index).normalize()
    f["available_time"] = stamp
    f["source_id"] = "cn_parity_dev"
    f["retrieval_time"] = _now().isoformat(timespec="seconds")
    return f


# ------------------------------------------------------------------------------ calendar ---
def _closed(day: date, holidays: Callable[[int], Mapping[str, str]]) -> bool:
    return day.weekday() >= 5 or day.isoformat() in holidays(day.year)


def golden_week_frame(years: list[int], holidays: Callable[[int], Mapping[str, str]],
                      closures: Callable[[int], tuple[Mapping[str, str], ...]],
                      status: Mapping[int, str] | None = None) -> pd.DataFrame:
    """Per weekday: trading days to the National Day block and since its reopening (each inside
    GW_WINDOW, else empty), the length of the next mainland closure within 10 days, and a flag
    for a weekday the mainland is shut while the offshore books trade. Untabulated years: none."""
    years = [y for y in years if holidays(y)]
    if not years:
        return pd.DataFrame()
    blocks = [c for y in years for c in closures(y) if "国庆" in str(c.get("name", ""))]
    all_closures = [c for y in years for c in closures(y)]
    rows: list[dict[str, Any]] = []
    day = date(min(years), 1, 1)
    end = date(max(years), 12, 31)
    while day <= end:
        if day.weekday() < 5:
            r: dict[str, Any] = {"day": day,
                                 "mainland_closed_weekday": 1.0 if _closed(day, holidays) else 0.0}
            to_gw = since_gw = np.nan
            for b in blocks:
                s, ro = date.fromisoformat(b["start"]), date.fromisoformat(b["reopen"])
                if day < s:
                    open_days = sum(1 for o in range(day.toordinal(), s.toordinal())
                                    if not _closed(date.fromordinal(o), holidays))
                    if open_days <= GW_WINDOW:
                        to_gw = float(open_days)
                elif day >= ro:
                    n = sum(1 for o in range(ro.toordinal(), day.toordinal() + 1)
                            if not _closed(date.fromordinal(o), holidays))
                    if n <= GW_WINDOW:
                        since_gw = float(n)
            r["gw_days_to"], r["gw_days_since"] = to_gw, since_gw
            nxt = [c for c in all_closures
                   if 0 <= (date.fromisoformat(c["start"]) - day).days <= 10]
            r["next_closure_days"] = float(min(nxt, key=lambda c: c["start"])["days"]) \
                if nxt else np.nan
            r["calendar_status"] = str((status or {}).get(day.year, "GAZETTED"))[:40]
            rows.append(r)
        day += timedelta(days=1)
    f = pd.DataFrame(rows)
    f["event_time"] = pd.to_datetime(f.pop("day")).dt.tz_localize("UTC")
    f["available_time"] = f["event_time"]
    f["source_id"] = "cn_golden_week"
    f["retrieval_time"] = _now().isoformat(timespec="seconds")
    return f


# ---------------------------------------------------------------------------------- cells ---
_STAMP = {"available_time", "event_time", "source_id", "retrieval_time", "calendar_status"}

MECHANISMS: dict[str, str] = {
    "cn_parity_dev": (
        "the PBOC sets USD/CNY's central parity at 09:15 Beijing and defends a +/-2% onshore "
        "band around it; offshore USDCNH is free. The gap between the pre-fix CNH and the fix "
        "is the official signal against market pressure, and a gap near the band edge marks a "
        "constraint the central bank must lean on (counter-cyclical factor, state-bank dollar "
        "sales). That pressure transmits to USDCNH and to the China-exposed Hong Kong indices"),
    "cn_golden_week": (
        "the mainland cash market and northbound Connect shut for the National Day block while "
        "USDCNH, HK50 and CHINAH trade on; positioning is forced into the days before the "
        "closure and the reopening has to absorb what the offshore books priced meanwhile"),
}


def feature_cols(frame: pd.DataFrame) -> list[str]:
    cols = []
    for c in frame.columns:
        if c in _STAMP:
            continue
        s = pd.to_numeric(frame[c], errors="coerce")
        if s.notna().sum() >= MIN_ROWS and s.nunique(dropna=True) >= 4:
            cols.append(str(c))
    return cols


def cell_hash(sid: str, col: str, tf: str, sym: str, chart: str) -> str:
    return hashlib.sha1(f"cnhk|{sid}|{col}|{tf}|{sym}|{chart}".encode()).hexdigest()[:16]


def mint(frames: Mapping[str, pd.DataFrame], universe: frozenset[str], state: dict[str, Any],
         *, dry_run: bool, enqueue: Callable[..., Any] | None,
         limit: int = MAX_MINT_PER_PASS) -> dict[str, Any]:
    minted = set(state.get("minted") or [])
    plan = [(sid, col, tf, sym, chart)
            for sid, f in sorted(frames.items()) for col in feature_cols(f)
            for tf in (("level_z",) if col.endswith(("_chg", "_pct")) else TRANSFORMS)
            for sym in TARGETS if sym in universe for chart in CHARTS]
    new, errors = 0, []
    for sid, col, tf, sym, chart in plan:
        h = cell_hash(sid, col, tf, sym, chart)
        if h in minted or dry_run or enqueue is None or new >= limit:
            continue
        mech = MECHANISMS[sid]
        try:
            enqueue(family="exogenous_conditioner", symbol=sym,
                    params={"source": sid, "signal": col, "transform": tf},
                    origin="cn_hk_structural_state", mechanism=mech, chart=chart,
                    horizon=chart, source_id=sid, generator="cn_hk_structural_state",
                    department="information", asset_class="",
                    transformation="cn_hk_structural_feature",
                    required_data=[f"desks/mt5/data/lake/series/{sid}.parquet"],
                    pit_status="STAMPED", causal_rationale=mech,
                    falsifier=(f"the {tf} of {sid}.{col} has no measurable relation to "
                               f"{sym} at {chart} out of sample"))
            minted.add(h)
            new += 1
        except Exception as exc:
            errors.append(f"{sid}/{col}/{sym}: {type(exc).__name__}: {str(exc)[:60]}")
    state["minted"] = sorted(minted)
    planned = {cell_hash(*p) for p in plan}
    return {"cells_planned": len(plan), "cells_minted_this_pass": new,
            "cells_minted_total": len(minted),
            "cells_queued": len(planned - minted),
            "unquoted_targets": [t for t in TARGETS if t not in universe],
            "errors": errors[:10]}


# ----------------------------------------------------------------------------------- pass ---
def _universe() -> frozenset[str]:
    doc = _read(DESK / "data" / "universe" / "universe.json", {}) or {}
    return frozenset(str(k) for k in doc) if isinstance(doc, dict) else frozenset()


def build(*, dry_run: bool = False, offline: bool = False,
          get_text: Callable[[str], str] | None = None,
          bars: Callable[[str], pd.DataFrame | None] | None = None,
          enqueue: Callable[..., Any] | None = None, now: datetime | None = None,
          out: Path | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    now = now or _now()
    state: dict[str, Any] = _read(STATE, {}) or {}
    notes: list[dict[str, Any]] = []
    getter = None if offline else (get_text or fetch_text)
    if bars is None:
        try:
            from research.proposer_common import bars as _bars
            bars = _bars
        except Exception:
            def bars(sym: str) -> pd.DataFrame | None:
                return None
    from research.countries.cn import pack as cn
    parity = collect_parity(getter, state, notes, now)
    pboc = pboc_robots(getter, state, now)
    cnh = cnh_before_fix(bars("USDCNH"))
    frames: dict[str, pd.DataFrame] = {}
    series: dict[str, Any] = {}
    pf = parity_frame(parity, cnh)
    if len(pf) >= MIN_ROWS:
        frames["cn_parity_dev"] = pf
        last = pf.iloc[-1]
        series["cn_parity_dev"] = {
            "rows": len(pf), "last_fix_day": str(last["event_time"])[:10],
            "parity_age_days": (pd.Timestamp(now) - pd.Timestamp(last["event_time"])).days,
            "latest": {k: (None if pd.isna(last[k]) else round(float(last[k]), 6))
                       for k in ("parity", "cnh_pre_fix", "dev_pips", "dev_pct", "band_use",
                                 "band_edge_level")}}
    else:
        notes.append({"series": "cn_parity_dev", "status": "UNMEASURED",
                      "why": (f"parity rows held {len(parity)}, USDCNH pre-fix days {len(cnh)}, "
                              f"joined {len(pf)} < {MIN_ROWS}")})
    status = {int(k): str(v) for k, v in (cn.HOLIDAYS_RULE.get("status") or {}).items()}
    years = sorted(int(y) for y in (cn.HOLIDAYS_RULE.get("table") or {}))
    gw = golden_week_frame(years, cn.holidays, cn.cn_long_closures, status)
    if len(gw) >= MIN_ROWS:
        frames["cn_golden_week"] = gw
        series["cn_golden_week"] = {
            "rows": len(gw), "years": years, "calendar_status": status,
            "national_day_blocks": [c for y in years for c in cn.cn_long_closures(y)
                                    if "国庆" in str(c.get("name", ""))]}
    else:
        notes.append({"series": "cn_golden_week", "status": "UNMEASURED",
                      "why": "no tabulated closure year"})
    if not dry_run:
        from research.futures_state import _atomic_parquet
        for sid, f in frames.items():
            _atomic_parquet(SERIES / f"{sid}.parquet", f, index=False)
        if enqueue is None:
            try:
                from libs.moat.registry import enqueue_candidate
                enqueue = enqueue_candidate
            except Exception as exc:
                notes.append({"registry": "UNAVAILABLE", "why": type(exc).__name__})
    cells = mint(frames, _universe(), state, dry_run=dry_run, enqueue=enqueue)
    doc = {
        "generated_utc": now.isoformat(timespec="seconds"),
        "organ": "desks/mt5/research/cn_hk_structural_state.py",
        "rows": {"107": "China structural cells", "108": "Stock Connect flow cells"},
        "rule": ("Every series reaches cells or is named here with its reason. Fenced sources "
                 "are never fetched; a cell is minted once in its life."),
        "status": "MEASURED" if frames else "UNMEASURED",
        "series": series, "cells": cells,
        "parity_source": {
            "carrier": "BIS WS_XRU D.CN.CNY.A (the PBOC-reported daily USD/CNY rate)",
            "terms": "BIS terms of permitted use, read on the box 2026-11-11 "
                     "(futures_state_sources.json bis_stats): unrestricted with citation",
            "citation": "Source: Bank for International Settlements, US dollar exchange rates "
                        "(WS_XRU), BIS Data Portal, https://data.bis.org",
            "held_rows": len(parity),
            "last_held": str(parity.index.max())[:10] if len(parity) else None,
            "user_agent": UA},
        "pboc_robots": pboc,
        "fences": [dict(f) for f in FENCES],
        "point_in_time": {
            "cn_parity_dev": "available 01:30 UTC on the fix day (fix 01:15 UTC + 15 min); CNH "
                             "leg is the last H1 close ending by 01:00 UTC (broker -> UTC)",
            "cn_golden_week": "the published State Council arrangement, 00:00 UTC on its day"},
        "hard_stops": state.get("hard_stops", {}),
        "notes": notes,
        "consumer": ("mt5desk/family_exogenous_conditioner.py through libs.moat.registry "
                     "(read-only use of the family; no family file is edited)"),
        "seconds": round(time.monotonic() - t0, 2),
    }
    if not dry_run:
        _write_json(STATE, state)
        _write_json(out or OUT, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="China/HK structural state (rows 107, 108)")
    ap.add_argument("--once", action="store_true", help="one pass (the scheduled form)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args(argv)
    doc = build(dry_run=a.dry_run, offline=a.offline)
    c = doc["cells"]
    print(f"cn_hk_structural_state: {doc['status']} series={sorted(doc['series'])} "
          f"cells planned={c['cells_planned']} minted={c['cells_minted_this_pass']} "
          f"queued={c['cells_queued']} fences={len(doc['fences'])} -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
