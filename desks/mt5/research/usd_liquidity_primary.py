"""USD LIQUIDITY FROM ITS PRIMARY PUBLISHERS -- the four series FRED used to relay, fetched from the
institutions that publish them, each stamped with when the desk could actually have known it.

WHY (BACKLOG 609, 2026-11-18). `shadow_institutional`'s usd_liquidity latent read WRESBAL, WTREGEN,
RRPONTSYD and SOFR from `data/axes/fred.json`. FRED is refused for every automated fetch (terms
ruling 2026-11-13), so that axis is frozen and empty. FRED never owned these numbers; it relayed
them. Each one has a first-party publisher whose own terms permit automated use, read and quoted
below (`SOURCES[...]["terms"]`), and this module goes there instead.

    WRESBAL     Fed Board H.4.1 (Data Download Program), RESH4R_XAW_N.WW, week average, $mn
    RRPONTSYD   NY Fed reverse repo operations API, total accepted per operation date, $
    SOFR        NY Fed reference rates API, percent
    WTREGEN     Treasury FiscalData, Daily Treasury Statement, TGA closing balance, $mn
                (DAILY from the DTS -- FRED's WTREGEN is the weekly Wednesday H.4.1 line; the
                name is kept so the sensor table reads the same, and `what` says which it is)

EVERY POINT CARRIES ITS OWN CLOCK. `event_time` is the date the value describes; `available_time`
is when the publisher released it, on its stated schedule and a conservative side of it:

    WRESBAL     week ending Wednesday -> next federal business day 21:30 UTC (H.4.1: Thu 16:30 ET)
    RRPONTSYD   operation date        -> same day 18:30 UTC (results ~13:15 ET)
    SOFR        effective date        -> next federal business day 13:30 UTC (published ~08:00 ET)
    WTREGEN     record date           -> next federal business day 21:30 UTC (DTS ~16:00 ET)

`knowable_at` (what `shadow_institutional.read_axis_points` dates a point by) is `available_time`,
so the latent can never condition on a value before it was published. Late costs a little edge;
early invents it.

THE DOOR IS STRICT. Every request: `libs.data.refused_hosts` first, then the host's robots.txt read
with this module's honest UA (a Disallow on the path, or robots that cannot be read, stops the
fetch; 404/410 means no rules), then the GET. 401, 403, 429 and 451, or an HTML wall where data was
expected, is a HARD STOP for that host for the pass: recorded with its missed-growth line, never
retried, never routed around. No key, no paid API, no browser UA.

    python desks/mt5/research/usd_liquidity_primary.py            # fetch and print, write nothing
    python desks/mt5/research/usd_liquidity_primary.py --apply    # write the usd_liquidity axis
"""
from __future__ import annotations

import argparse
import csv
import functools
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data.refused_hosts import refusal  # noqa: E402 -- no list, no module: fail closed

AXIS = "usd_liquidity"
OUT = DESK / "data" / "axes" / f"{AXIS}.json"
#: The desk's one honest User-Agent (libs/data/honest_ua.HONEST_UA on #1320): it names what the
#: client is and that it honours robots.txt, and carries no person, repository or contact.
UA = "quant-desk-research/1.0 (automated research; honours robots.txt)"
TIMEOUT = 40
START = "2018-04-02"            # SOFR's first publication; every series is read from here
HARD_STOP = frozenset({401, 403, 429, 451})
STATUS_REFUSED = "BLOCKED_ON_TERMS"
STATUS_HARD_STOP = "HARD_STOP"

H41_CODE = "RESH4R_XAW_N.WW"
#: The H.4.1 DDP package that holds the four "Reserve balances with Federal Reserve Banks" series
#: (week average, Wednesday level and the two changes), read 2026-11-18 from the DDP review page.
H41_PACKAGE = "2704b6bc9b50bc034baf9660364dfb26"
DTCC_NOTICE = ("The Secured Overnight Financing Rate (SOFR) Data and Broad General Collateral "
               "Rate (BGCR) Data are calculated using data provided under a license granted to "
               "the New York Fed by DTCC Solutions LLC (“Solutions”), an affiliate of "
               "The Depository Trust & Clearing Corporation. Solutions, its affiliates, and third "
               "parties from which they obtained data have no liability for the content of this "
               "material.")
NYFED_ATTRIBUTION = ("Content from the New York Fed subject to the Terms of Use at "
                     "newyorkfed.org.")

_FED_TERMS = {
    "url": "https://www.federalreserve.gov/disclaimer.htm",
    "read": "2026-11-18",
    "clause": ("information on Board's website is in the public domain and may be copied and "
               "distributed without permission ... Please cite to the Board as the source of the "
               "information."),
}
_NYFED_TERMS = {
    "url": "https://www.newyorkfed.org/privacy/termsofuse",
    "read": "2026-11-18",
    "clause": ("The New York Fed grants you a non-exclusive license, subject to the Terms, to use, "
               "copy, and distribute Content for your personal or business purposes. You may: "
               "Access the Content, manually or through an automated process or device, provided "
               "your access does not have the effect of disabling, damaging, or interfering with "
               "the function of the Website ... These Terms generally apply to Content accessed "
               "through those other distribution channels as well."),
}
_FISCAL_TERMS = {
    "url": "https://fiscaldata.treasury.gov/api-documentation/",
    "read": "2026-11-18",
    "clause": ("The data is offered free, without restriction, and available to copy, adapt, "
               "redistribute, or otherwise use for non-commercial or commercial purposes. ... "
               "Our API is open, meaning that it does not require a user account or registration "
               "for a token."),
}


# ------------------------------------------------------------------------------ publication clocks
def _next_business_day(d: date) -> date:
    """The next US federal business day after `d` (weekends and federal holidays skipped)."""
    import pandas as pd
    from pandas.tseries.holiday import USFederalHolidayCalendar
    from pandas.tseries.offsets import CustomBusinessDay
    nxt = pd.Timestamp(d) + CustomBusinessDay(calendar=USFederalHolidayCalendar())
    out: date = nxt.date()
    return out


def _stamp(d: date, at: time) -> str:
    return datetime.combine(d, at, tzinfo=UTC).isoformat(timespec="seconds")


#: SIFMA's recommended full closes that are not federal holidays and have no rule: national days
#: of mourning. Good Friday is added by rule below. A SIFMA EARLY close still publishes SOFR, and
#: Good Friday is sometimes only an early close (when payrolls fall on it): treating it as a
#: non-publication day then stamps the print one business day LATE, which costs a day of
#: freshness and never looks ahead.
SIFMA_EXTRA_CLOSES: frozenset[date] = frozenset({date(2018, 12, 5)})


@functools.lru_cache(maxsize=1)
def _sifma_offset() -> Any:
    import pandas as pd
    from pandas.tseries.holiday import GoodFriday, USFederalHolidayCalendar
    from pandas.tseries.offsets import CustomBusinessDay

    lo, hi = pd.Timestamp("2000-01-01"), pd.Timestamp("2100-12-31")
    hol = list(USFederalHolidayCalendar().holidays(start=lo, end=hi))
    hol += list(GoodFriday.dates(lo, hi))
    hol += [pd.Timestamp(x) for x in SIFMA_EXTRA_CLOSES]
    return CustomBusinessDay(holidays=hol)


def _next_sifma_day(d: date) -> date:
    """The next SIFMA business day after `d`: federal holidays, Good Friday and the listed
    mourning closes skipped. SOFR is published on SIFMA business days, not federal ones."""
    import pandas as pd
    out: date = (pd.Timestamp(d) + _sifma_offset()).date()
    return out


def available_h41(d: date) -> str:
    return _stamp(_next_business_day(d), time(21, 30))


def available_rrp(d: date) -> str:
    return _stamp(d, time(18, 30))


def available_sofr(d: date) -> str:
    return _stamp(_next_sifma_day(d), time(13, 30))


def available_dts(d: date) -> str:
    return _stamp(_next_business_day(d), time(21, 30))


# ------------------------------------------------------------------------------------- parsers
def _num(v: Any) -> float | None:
    try:
        f = float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def _day(v: Any) -> date | None:
    try:
        return date.fromisoformat(str(v).strip()[:10])
    except ValueError:
        return None


def parse_h41_csv(text: str, code: str = H41_CODE) -> list[tuple[date, float]]:
    """The DDP CSV (layout=seriescolumn, label=include): header rows, then a 'Time Period' row
    naming each column's series, then one row per date. 'ND'/'NA' are absent values."""
    rows = list(csv.reader(io.StringIO(text)))
    col = None
    start = 0
    for i, r in enumerate(rows):
        if r and r[0].strip().strip('"') == "Time Period":
            for j, cell in enumerate(r):
                if cell.strip().endswith(code):
                    col = j
            start = i + 1
            break
    if col is None:
        return []
    out = []
    for r in rows[start:]:
        if len(r) <= col:
            continue
        d, v = _day(r[0]), _num(r[col])
        if d and v is not None:
            out.append((d, v))
    return sorted(out)


def parse_nyfed_rrp(doc: Mapping[str, Any]) -> list[tuple[date, float]]:
    """Reverse repo operations -> total accepted ($) per operation date."""
    ops = ((doc.get("repo") or {}).get("operations")) or []
    tally: dict[date, float] = {}
    for op in ops:
        if "reverse" not in str(op.get("operationType") or "").lower():
            continue
        d, v = _day(op.get("operationDate")), _num(op.get("totalAmtAccepted"))
        if d and v is not None:
            tally[d] = tally.get(d, 0.0) + v
    return sorted(tally.items())


def parse_nyfed_sofr(doc: Mapping[str, Any]) -> list[tuple[date, float]]:
    out = {}
    for r in doc.get("refRates") or []:
        if str(r.get("type") or "SOFR").upper() != "SOFR":
            continue
        d, v = _day(r.get("effectiveDate")), _num(r.get("percentRate"))
        if d and v is not None:
            out[d] = v
    return sorted(out.items())


def parse_dts_tga(doc: Mapping[str, Any]) -> list[tuple[date, float]]:
    """DTS operating cash balance -> the TGA closing balance ($mn) per record date.

    Since 2021-10-01 the table carries a 'Treasury General Account (TGA) Closing Balance' row,
    whose value sits in `open_today_bal` because `close_today_bal` is null from 2022-04-18 (the
    dataset page says so). Before that, the 'Federal Reserve Account' row's closing balance is
    the TGA. The closing-balance row wins where both exist."""
    best: dict[date, tuple[int, float]] = {}
    for r in doc.get("data") or []:
        d = _day(r.get("record_date"))
        acct = str(r.get("account_type") or "")
        if not d:
            continue
        if "closing balance" in acct.lower() and "tga" in acct.lower():
            rank, v = 2, _num(r.get("close_today_bal"))
            if v is None:
                v = _num(r.get("open_today_bal"))
        elif acct.strip().lower() == "federal reserve account":
            rank, v = 1, _num(r.get("close_today_bal"))
        else:
            continue
        if v is not None and rank >= best.get(d, (0, 0.0))[0]:
            best[d] = (rank, v)
    return sorted((d, v) for d, (_r, v) in best.items())


# ------------------------------------------------------------------------------------- sources
def _h41_url(start: str) -> str:
    y, m, d = start.split("-")
    q = {"rel": "H41", "series": H41_PACKAGE, "lastobs": "", "from": f"{m}/{d}/{y}",
         "to": "12/31/2099", "filetype": "csv", "label": "include", "layout": "seriescolumn"}
    return "https://www.federalreserve.gov/datadownload/Output.aspx?" + urllib.parse.urlencode(q)


def _rrp_url(start: str) -> str:
    return ("https://markets.newyorkfed.org/api/rp/reverserepo/propositions/search.json?"
            + urllib.parse.urlencode({"startDate": start}))


def _sofr_url(start: str) -> str:
    end = datetime.now(tz=UTC).date().isoformat()
    return ("https://markets.newyorkfed.org/api/rates/secured/sofr/search.json?"
            + urllib.parse.urlencode({"startDate": start, "endDate": end}))


def _dts_url(start: str, page: int) -> str:
    q = {"fields": "record_date,account_type,open_today_bal,close_today_bal",
         "filter": f"record_date:gte:{start}", "sort": "-record_date",
         "page[size]": "10000", "page[number]": str(page)}
    return ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/"
            "operating_cash_balance?" + urllib.parse.urlencode(q))


SOURCES: dict[str, dict[str, Any]] = {
    "WRESBAL": {"what": "reserve balances with Federal Reserve Banks, week average",
                "publisher": "Federal Reserve Board, H.4.1 (Data Download Program)",
                "unit": "millions of USD", "cadence": "weekly", "kind": "csv",
                "url": _h41_url, "parse": parse_h41_csv, "available": available_h41,
                "terms": _FED_TERMS, "attribution": "Source: Board of Governors of the Federal "
                "Reserve System, H.4.1"},
    "RRPONTSYD": {"what": "overnight reverse repo, total accepted per operation date",
                  "publisher": "Federal Reserve Bank of New York, markets API",
                  "unit": "USD", "cadence": "daily", "kind": "json",
                  "url": _rrp_url, "parse": parse_nyfed_rrp, "available": available_rrp,
                  "terms": _NYFED_TERMS, "attribution": NYFED_ATTRIBUTION},
    "SOFR": {"what": "Secured Overnight Financing Rate",
             "publisher": "Federal Reserve Bank of New York, reference rates API",
             "unit": "percent", "cadence": "daily", "kind": "json",
             "url": _sofr_url, "parse": parse_nyfed_sofr, "available": available_sofr,
             "terms": _NYFED_TERMS, "attribution": f"{NYFED_ATTRIBUTION} {DTCC_NOTICE}"},
    "WTREGEN": {"what": ("Treasury General Account closing balance, DAILY from the Daily "
                         "Treasury Statement (FRED's WTREGEN is the weekly H.4.1 line)"),
                "publisher": "US Treasury, Bureau of the Fiscal Service (FiscalData DTS)",
                "unit": "millions of USD", "cadence": "daily", "kind": "json_paged",
                "url": _dts_url, "parse": parse_dts_tga, "available": available_dts,
                "terms": _FISCAL_TERMS, "attribution": "Source: U.S. Treasury, Daily Treasury "
                "Statement (fiscaldata.treasury.gov)"},
}


def missed_growth(sid: str, why: str) -> dict[str, str]:
    return {"mechanism": f"usd_liquidity_{sid.lower()}_unreached",
            "lost": f"{sid} ({SOURCES[sid]['what']}) for the usd_liquidity latent this pass",
            "why": why[:200],
            "stand_in": "the series already on disk in data/axes/usd_liquidity.json, if any",
            "verdict": "a gap, not a zero"}


# ------------------------------------------------------------------------------------- the door
class Stop(Exception):
    """This request may not, or must not again, be made. `status` is the recorded word."""

    def __init__(self, status: str, why: str) -> None:
        super().__init__(f"{status}: {why}")
        self.status = status
        self.why = why


Opener = Callable[[urllib.request.Request, float], tuple[int, str, bytes]]


def _urlopen(req: urllib.request.Request, timeout: float) -> tuple[int, str, bytes]:
    from libs.data.refused_hosts import opener
    try:
        with opener().open(req, timeout=timeout) as r:
            return (int(getattr(r, "status", 200) or 200),
                    str(r.headers.get("Content-Type") or ""), r.read(50_000_000))
    except urllib.error.HTTPError as exc:
        try:
            return int(exc.code), str(exc.headers.get("Content-Type") or ""), b""
        finally:
            exc.close()


class Door:
    """refused_hosts -> robots.txt -> GET, with hard stops remembered per host for the pass."""

    def __init__(self, open_: Opener | None = None) -> None:
        self.open = open_ or _urlopen
        self.robots: dict[str, urllib.robotparser.RobotFileParser | str] = {}
        self.stopped: dict[str, str] = {}

    def _robots(self, scheme: str, host: str) -> urllib.robotparser.RobotFileParser | str:
        key = f"{scheme}://{host}"
        if key not in self.robots:
            req = urllib.request.Request(f"{key}/robots.txt", headers={"User-Agent": UA})
            try:
                code, _ct, body = self.open(req, 15.0)
            except Exception as exc:
                self.robots[key] = f"robots.txt unreadable ({type(exc).__name__})"
                return self.robots[key]
            rp = urllib.robotparser.RobotFileParser()
            if code in HARD_STOP:
                self.stopped[host] = f"robots.txt answered HTTP {code}"
                raise Stop(STATUS_HARD_STOP, self.stopped[host])
            if code in (404, 410):
                rp.parse([])
            elif 200 <= code < 300:
                text = body.decode("utf-8", "replace")
                if text.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
                    # A page in place of rules parses as allow-all: that is unread, not a yes.
                    self.robots[key] = "robots.txt answered HTML"
                    return self.robots[key]
                rp.parse(text.splitlines())
            else:
                self.robots[key] = f"robots.txt unreadable (HTTP {code})"
                return self.robots[key]
            self.robots[key] = rp
        return self.robots[key]

    def get(self, url: str, expect: str) -> bytes:
        why = refusal(url)
        if why:
            raise Stop(STATUS_REFUSED, why)
        parts = urllib.parse.urlsplit(url)
        host = parts.netloc.lower()
        if host in self.stopped:
            raise Stop(STATUS_HARD_STOP, f"host stopped earlier this pass: {self.stopped[host]}")
        rules = self._robots(parts.scheme, host)
        if isinstance(rules, str):
            raise Stop(STATUS_REFUSED, f"{rules}; unread robots are not permission")
        if not rules.can_fetch(UA, url):
            raise Stop(STATUS_REFUSED, "robots.txt disallows this path for our agent")
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": expect})
        code, ctype, body = self.open(req, float(TIMEOUT))
        if code in HARD_STOP:
            self.stopped[host] = f"HTTP {code}"
            raise Stop(STATUS_HARD_STOP, f"HTTP {code}")
        if not 200 <= code < 300:
            raise Stop("FETCH_FAILED", f"HTTP {code}")
        if "html" in ctype.lower() and "html" not in expect:
            self.stopped[host] = "an HTML page where data was expected (a wall or a captcha)"
            raise Stop(STATUS_HARD_STOP, self.stopped[host])
        return body


# ------------------------------------------------------------------------------------- ingest
def _points(sid: str, pts: list[tuple[date, float]]) -> list[dict[str, Any]]:
    avail = SOURCES[sid]["available"]
    out = []
    for d, v in pts:
        at = avail(d)
        out.append({"d": d.isoformat(), "v": v, "event_time": d.isoformat(),
                    "available_time": at, "knowable_at": at})
    return out


def fetch_series(sid: str, door: Door, start: str = START) -> list[tuple[date, float]]:
    src = SOURCES[sid]
    kind = src["kind"]
    parse: Callable[[Any], list[tuple[date, float]]] = src["parse"]
    if kind == "csv":
        return parse(door.get(src["url"](start), "text/csv").decode("utf-8", "replace"))
    if kind == "json":
        return parse(json.loads(door.get(src["url"](start), "application/json")))
    rows: list[Any] = []
    for page in range(1, 21):                       # DTS: paged, newest first, bounded
        doc = json.loads(door.get(src["url"](start, page), "application/json"))
        rows.extend(doc.get("data") or [])
        if not (doc.get("links") or {}).get("next") or not doc.get("data"):
            break
    return parse({"data": rows})


def ingest(door: Door | None = None, start: str = START) -> dict[str, Any]:
    """The axis document, in the `series[sid].points` shape every axis reader takes."""
    door = door or Door()
    series: dict[str, Any] = {}
    failed: dict[str, dict[str, Any]] = {}
    for sid, src in SOURCES.items():
        try:
            pts = fetch_series(sid, door, start)
        except Stop as stop:
            failed[sid] = {"status": stop.status, "why": stop.why,
                           "missed_growth": missed_growth(sid, stop.why)}
            continue
        except Exception as exc:
            why = f"{type(exc).__name__}: {str(exc)[:120]}"
            failed[sid] = {"status": "FETCH_FAILED", "why": why,
                           "missed_growth": missed_growth(sid, why)}
            continue
        if not pts:
            failed[sid] = {"status": "EMPTY", "why": "the publisher answered with no points",
                           "missed_growth": missed_growth(sid, "empty answer")}
            continue
        series[sid] = {"what": src["what"], "publisher": src["publisher"], "unit": src["unit"],
                       "cadence": src["cadence"], "terms": src["terms"],
                       "attribution": src["attribution"], "n": len(pts),
                       "first": pts[0][0].isoformat(), "last": pts[-1][0].isoformat(),
                       "points": _points(sid, pts)}
    return {"axis": AXIS, "id": "usd_liquidity_primary",
            "source": "primary publishers (Fed Board H.4.1, NY Fed, Treasury FiscalData)",
            "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "n_series": len(series), "n_failed": len(failed), "failed": failed,
            # Every writer (this module's `write` and axis_ingest_all's `_write_axis`) refuses a
            # pass that landed fewer series than the file holds.
            "never_fewer_series": True,
            "replaces": "data/axes/fred.json for WRESBAL, WTREGEN, RRPONTSYD, SOFR (BACKLOG 609)",
            "clock": ("event_time = the date the value describes; available_time = knowable_at "
                      "= the publisher's release time, on the conservative side"),
            "notice": DTCC_NOTICE,
            "shape": "series[sid].points -- one dated state variable each",
            "series": series}


def write(doc: dict[str, Any], path: Path = OUT) -> dict[str, Any]:
    """Atomic, and never replaces a populated axis with a pass that landed fewer series."""
    held = 0
    try:
        held = int(json.loads(path.read_text(encoding="utf-8")).get("n_series") or 0)
    except (OSError, ValueError, AttributeError):
        held = 0
    if doc["n_series"] < held:
        return {"written": False, "why": f"this pass landed {doc['n_series']} < {held} held"}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    try:
        os.replace(tmp, path)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        return {"written": False, "why": f"{type(exc).__name__}: {exc}"}
    return {"written": True, "path": str(path)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    doc = ingest()
    print(f"{AXIS}: {doc['n_series']} series, {doc['n_failed']} failed")
    for k, v in doc["series"].items():
        print(f"    {k:<10} {v['n']:>6} pts  {v['first']} -> {v['last']}  {v['publisher'][:40]}")
    for k, v in doc["failed"].items():
        print(f"    {k:<10} {v['status']}  {v['why'][:70]}")
    if a.apply:
        print(f"  {write(doc)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
