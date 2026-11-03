#!/usr/bin/env python3
"""INFORMED CAPITAL -- insider roles, activist and institutional stakes, congressional trades and
prediction-market odds, read from free public records, stamped at the instant they became public,
tracked against the MT5 universe and turned into gauntlet cells.

    SOURCE              ENDPOINT (free, public, no login)                      CLOCK
    sec_form4           EDGAR daily form index + each Form 4/5 complete .txt   acceptance datetime
    sec_form345_ds      SEC Insider Transactions Data Sets (quarterly ZIP)     filing date (+1d 04Z)
    sec_13d             EDGAR daily form index, SC 13D / SC 13G, .hdr.sgml     acceptance datetime
    sec_13f             EDGAR 13F-HR info tables, diffed against the prior one acceptance (as ET)
    house_ptr           Clerk yearly FD index + e-filed PTR PDFs               filing date (+2d 04Z)
    senate_ptr          eFD search API + PTR pages (OFF by default, see below) filing date (+2d 04Z)
    kalshi              trade-api/v2 series, markets, daily candlesticks       candle end
    polymarket          gamma-api markets + clob prices-history                price timestamp

ONE PASS, FIVE STEPS, EVERY ONE WRITING SOMETHING.
  1. COLLECT what is due, politely (`libs.data.polite_fetch`; www.sec.gov / data.sec.gov spaced at
     0.25 s, under the SEC's 10 req/s fair-access ceiling, with a declared User-Agent from
     QUANT_EDGAR_UA or EDGAR_UA -- unconfigured means the SEC sources are UNCONFIGURED, never 0).
  2. STORE each event in the append-only `data/informed_capital/events.jsonl`, with its MT5
     instrument resolved at write time and `first_seen_at` recorded beside the observable clock.
  3. TRACK signed +1/+5/+21-trading-day returns after the OBSERVABLE instant per (target, source,
     relation, lead) -- `libs.research.analyst_views.track` / `placebo_contract`, reused -- and the
     same events on the ORACLE clock (transaction date) for the per-source DECAY table, which is
     research-only and feeds nothing.
  4. EMIT `informed_flow_drift` cells through `proposer_common.donate` -> the compiler -> the one
     canonical gauntlet: |t| over Bonferroni across every measured (cell, horizon) AND the cell's
     own shifted-date placebo ADMIT. Share CFDs reach the docket only because the family is in
     `universe_policy.NEWS_LANE_FAMILIES`; the main targets are the index, FX, gold and oil legs.
  5. REPORT `reports/INFORMED_CAPITAL.json`, with a FENCE (GREEN / RED / UNMEASURED) that the
     issue board reads: RED on a point-in-time violation, a configured source failing three passes
     running, or a store that has stopped growing.

THE SENATE COLLECTOR IS OFF UNTIL THE PRINCIPAL SAYS OTHERWISE. eFD shows every visitor an
agreement that the reports will not be used for a commercial purpose (5 U.S.C. 13107(c)) and
requires clicking it before the search API answers. Clicking an attestation is not this
session's call to make for a trading desk; the parser is built and tested, and
`QUANT_SENATE_EFD_ATTEST=1` turns the collector on. The House site carries the same statute with
no click-through; the desk already reads its index in `libs/data/free_stack.fetch_congress`, so
it is read here too, and the note rides on every row's provenance.

LIVE YIELD IS UNMEASURED UNTIL THE TRADING BOX RUNS IT: the container this was built in reaches
none of these hosts. The parsers are proven on recorded payload shapes (tests).

    python desks/mt5/research/informed_capital.py --once [--budget-s 300] [--dry-run] [--no-collect]
    python desks/mt5/research/informed_capital.py --check     # exit 1 when the fence is RED
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from http.cookiejar import CookieJar
from pathlib import Path
from statistics import NormalDist
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import analyst_views as av  # noqa: E402
from libs.research import informed_capital as ic  # noqa: E402

SOURCE = "informed_capital"
FAMILY = "informed_flow_drift"
DATA = DESK / "data" / "informed_capital"
STORE = DATA / "events.jsonl"
STATE = DATA / "collector_state.json"
TICKERS_CACHE = DATA / "company_tickers.json"
REPORT = DESK / "reports" / "INFORMED_CAPITAL.json"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
UNMEASURED = ic.UNMEASURED

MAX_DONATIONS = 20
ALPHA = 0.05
PROPOSE_T = 2.0
CONTRACT_HORIZON_D = 5
#: How far back the quarterly data sets are backfilled, one quarter per pass.
BACKFILL_QUARTERS = 8
#: Days the EDGAR index cursor may catch up in one pass.
INDEX_DAYS_PER_PASS = 5
QUEUE_CAP = 20_000
MAX_13F_PER_PASS = 4
MAX_HOUSE_PDFS = 40
MAX_SENATE_REPORTS = 40
MAX_ODDS_MARKETS = 60
#: Consecutive failed passes after which a configured source turns the fence RED.
RED_AFTER_FAILURES = 3
#: A store that gained nothing for this long, with a source configured, turns the fence RED.
STALL_DAYS = 7

SEC_HOSTS = {"www.sec.gov": 0.25, "data.sec.gov": 0.25, "efts.sec.gov": 0.25}
HOUSE_PDF = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc}.pdf"
SENATE = "https://efdsearch.senate.gov"
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_CATEGORIES = ("Economics", "Financials")

MECHANISM = ("informed flow diffuses slowly: a disclosed insider, activist, institutional or "
             "legislator trade, or a macro contract's probability move, is followed by drift in "
             "the instrument after the instant it became public")
PAYER = "holders who do not read filings or prediction markets, and benchmark-bound books"
CONSTRAINT = ("reading disclosures is costly, short-sale cost limits acting on a sale, and an "
              "aggregate breadth move is never news about any one name")
STATUTE = ("5 U.S.C. 13107(c): congressional financial disclosure reports may not be used for a "
           "commercial purpose; the principal decides whether this desk's use is one")

#: The roster: how each source is reached, stamped and labelled (the terms gate's fields).
SOURCES: dict[str, dict[str, Any]] = {
    "sec_form4": {"host": "www.sec.gov", "access_label": "PUBLIC", "cadence_s": 3600,
                  "auth": "declared User-Agent", "pit": "ACCEPTANCE-DATETIME (ET) -> UTC",
                  "licence": "US federal public record; SEC fair access <= 10 req/s"},
    "sec_form345_ds": {"host": "www.sec.gov", "access_label": "PUBLIC", "cadence_s": 3600,
                       "auth": "declared User-Agent",
                       "pit": "FILING_DATE only -> next UTC day 04:00",
                       "licence": "US federal public record; SEC fair access <= 10 req/s"},
    "sec_13d": {"host": "www.sec.gov", "access_label": "PUBLIC", "cadence_s": 3600,
                "auth": "declared User-Agent", "pit": "header ACCEPTANCE-DATETIME (ET) -> UTC",
                "licence": "US federal public record; SEC fair access <= 10 req/s"},
    "sec_13f": {"host": "www.sec.gov", "access_label": "PUBLIC", "cadence_s": 3600,
                "auth": "declared User-Agent",
                "pit": "submissions acceptanceDateTime read as ET (conservative: never earlier)",
                "licence": "US federal public record; SEC fair access <= 10 req/s"},
    "house_ptr": {"host": "disclosures-clerk.house.gov", "access_label": "PUBLIC_WITH_TERMS",
                  "cadence_s": 6 * 3600, "auth": "none",
                  "pit": "index FilingDate -> +2 UTC days 04:00 (posting lag)",
                  "licence": STATUTE},
    "senate_ptr": {"host": "efdsearch.senate.gov", "access_label": "PUBLIC_WITH_TERMS",
                   "cadence_s": 6 * 3600, "auth": "click-through attestation",
                   "pit": "date received -> +2 UTC days 04:00 (posting lag)",
                   "licence": STATUTE + "; the site requires clicking that agreement, so the "
                              "collector runs only with QUANT_SENATE_EFD_ATTEST=1"},
    "kalshi": {"host": "api.elections.kalshi.com", "venue": "kalshi", "cadence_s": 3600,
               "auth": "none (public market data)", "pit": "candle end_period_ts",
               "licence": "terms gate: research.prediction_markets.BY_NAME['kalshi']"},
    "polymarket": {"host": "gamma-api.polymarket.com", "venue": "polymarket", "cadence_s": 3600,
                   "auth": "none (public market data)", "pit": "clob prices-history t",
                   "licence": "terms gate: research.prediction_markets.BY_NAME['polymarket']"},
}
SEC_SOURCES = ("sec_form4", "sec_form345_ds", "sec_13d", "sec_13f")


# ------------------------------------------------------------------------------ helpers
def _now() -> datetime:
    return datetime.now(tz=UTC).replace(microsecond=0)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def edgar_ua() -> str:
    return (os.environ.get("QUANT_EDGAR_UA") or os.environ.get("EDGAR_UA") or "").strip()


def _ticker_maps() -> tuple[dict[str, str], dict[str, str]]:
    """(ticker -> MT5 share CFD, MT5 -> ticker), from the Alpha Capture roster (reused)."""
    try:
        from research.alpha_capture import BY_TICKER, TICKERS
        return dict(BY_TICKER), dict(TICKERS)
    except Exception:                                         # pragma: no cover - import context
        return {}, {}


def terms_gate(source: str) -> dict[str, Any]:
    """The access decision for a source, from the desk's own labels (LAWS 5e): the prediction
    venues through `research.prediction_markets.BY_NAME`, the rest from `source_civilizations`.
    A refused label is never fetched."""
    meta = SOURCES[source]
    try:
        if meta.get("venue"):
            from research.prediction_markets import BY_NAME
            v = BY_NAME[str(meta["venue"])]
            return {"allowed": v.machine_use_allowed, "label": v.access_label,
                    "note": v.terms_note, "redistribute": v.redistribute_allowed}
        from research import source_civilizations as SC
        b = SC.ACCESS_BEHAVIOUR[str(meta["access_label"])]
        return {"allowed": bool(b["machine_use_allowed"]), "label": meta["access_label"],
                "note": str(meta.get("licence") or b["why"]),
                "redistribute": bool(b["redistribute_allowed"])}
    except Exception as exc:
        return {"allowed": False, "label": UNMEASURED,
                "note": f"terms gate unreadable ({type(exc).__name__}): not fetched"}


# ------------------------------------------------------------------------------ http
class Http:
    """The fetch seam. Text through `polite_fetch.get` (per-host spacing, bounded retries, never
    raises); bytes and the Senate form POST through one cookie-keeping opener that honours the
    same per-host gate. Tests pass a fake with the same three methods."""

    def __init__(self) -> None:
        from libs.data import polite_fetch as pf
        self.pf = pf
        self.gate = pf.HostGate(per_host={**pf.HOST_INTERVAL_S, **SEC_HOSTS})
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(CookieJar()),
            urllib.request.HTTPSHandler(context=pf.ssl_context()))

    def text(self, url: str, *, headers: Mapping[str, str] | None = None,
             deadline: float | None = None, leg: str = SOURCE) -> tuple[int | None, str, str]:
        r = self.pf.get(url, headers=dict(headers or {}), deadline=deadline, leg=leg,
                        gate=self.gate, max_bytes=8_000_000)
        return r.status, r.text if r.ok else "", r.error

    def _open(self, req: urllib.request.Request, deadline: float | None,
              max_bytes: int) -> tuple[int | None, bytes, str]:
        host = urllib.parse.urlparse(req.full_url).netloc.lower()
        self.gate.wait(host)
        timeout = 60.0 if deadline is None else max(1.0, min(60.0, deadline - time.monotonic()))
        try:
            with self.opener.open(req, timeout=timeout) as fh:
                return int(getattr(fh, "status", 200) or 200), fh.read(max_bytes), ""
        except urllib.error.HTTPError as exc:
            exc.close()
            return int(exc.code), b"", f"HTTP {exc.code}"
        except Exception as exc:
            return None, b"", f"{type(exc).__name__}: {str(exc)[:120]}"

    def bytes(self, url: str, *, headers: Mapping[str, str] | None = None,
              deadline: float | None = None, max_bytes: int = 120_000_000
              ) -> tuple[int | None, bytes, str]:
        hdr = {**self.pf.BROWSER_HEADERS, **dict(headers or {})}
        hdr.pop("Accept-Encoding", None)            # raw bytes: no transfer compression to undo
        return self._open(urllib.request.Request(url, headers=hdr), deadline, max_bytes)

    def post(self, url: str, data: Mapping[str, str], *, headers: Mapping[str, str] | None = None,
             deadline: float | None = None) -> tuple[int | None, str, str]:
        hdr = {**self.pf.BROWSER_HEADERS, **dict(headers or {})}
        hdr.pop("Accept-Encoding", None)
        body = urllib.parse.urlencode(data).encode()
        st, raw, err = self._open(urllib.request.Request(url, data=body, headers=hdr,
                                                         method="POST"), deadline, 8_000_000)
        return st, raw.decode("utf-8", "replace"), err

    def cookie(self, name: str) -> str:
        for h in self.opener.handlers:
            jar = getattr(h, "cookiejar", None)
            for c in jar or []:
                if c.name == name:
                    return str(c.value or "")
        return ""


def _ok(status: int | None) -> bool:
    return status is not None and 200 <= status < 300


# ------------------------------------------------------------------------------ collectors
def _quarter(d: date) -> int:
    return (d.month - 1) // 3 + 1


def collect_tickers(http: Any, state: dict[str, Any], deadline: float, ua: str, now: datetime
                    ) -> dict[str, str]:
    """CIK -> ticker from the SEC's own company_tickers.json, refreshed daily and cached."""
    cached = _read_json(TICKERS_CACHE, {})
    fresh = str(state.get("tickers_at") or "") >= (now - timedelta(days=1)).isoformat()
    if not fresh and ua:
        st, text, _err = http.text("https://www.sec.gov/files/company_tickers.json",
                                   headers={"User-Agent": ua}, deadline=deadline)
        try:
            doc = json.loads(text) if _ok(st) else None
        except ValueError:
            doc = None
        if isinstance(doc, dict):
            cached = {str(int(v["cik_str"])): str(v["ticker"]).upper() for v in doc.values()
                      if isinstance(v, dict) and v.get("ticker") and v.get("cik_str")}
            cached["_titles"] = {str(v["ticker"]).upper(): str(v.get("title") or "")
                                 for v in doc.values() if isinstance(v, dict) and v.get("ticker")}
            _atomic(TICKERS_CACHE, json.dumps(cached))
            state["tickers_at"] = now.isoformat()
    return cached if isinstance(cached, dict) else {}


def collect_edgar_index(http: Any, state: dict[str, Any], deadline: float, ua: str,
                        now: datetime) -> dict[str, Any]:
    """Advance the daily-index cursor (one file per US filing day) and queue Form 4/5, SC 13D/G
    and 13F-HR filings. A 404 on a past day is a weekend or holiday and closes that day."""
    rep: dict[str, Any] = {"days": 0, "queued": 0, "errors": Counter(), "form3_seen": 0}
    queue: list[list[str]] = state.setdefault("queue", [])
    seen = set(state.get("queued_ids") or [])
    cursor = date.fromisoformat(str(state.get("index_next") or
                                    (now.date() - timedelta(days=7)).isoformat()))
    last_closed = now.date() - timedelta(days=1)
    while cursor <= last_closed and rep["days"] < INDEX_DAYS_PER_PASS:
        if time.monotonic() >= deadline:
            break
        url = (f"https://www.sec.gov/Archives/edgar/daily-index/{cursor.year}/"
               f"QTR{_quarter(cursor)}/form.{cursor:%Y%m%d}.idx")
        st, text, err = http.text(url, headers={"User-Agent": ua}, deadline=deadline)
        if st == 404:
            if cursor < last_closed:      # yesterday's file may not be published yet
                cursor += timedelta(days=1)
                state["index_next"] = cursor.isoformat()
            else:
                break
            continue
        if not _ok(st):
            rep["errors"][err or f"HTTP {st}"] += 1
            break
        for r in ic.parse_form_idx(text):
            f = r["form"]
            if f == "3":
                rep["form3_seen"] += 1
                continue
            if f in ("4", "5") or ic.is_13d(f) or ic.is_13g(f) or f == "13F-HR":
                key = f"{f}|{r['accession']}|{r['cik']}"
                if r["accession"] in seen and f not in ("4", "5"):
                    continue
                if key in seen:
                    continue
                seen.add(key)
                seen.add(r["accession"])
                queue.append([f, r["cik"], r["file"], r["date"], r["accession"], r["company"]])
                rep["queued"] += 1
        rep["days"] += 1
        cursor += timedelta(days=1)
        state["index_next"] = cursor.isoformat()
    state["queue"] = queue[-QUEUE_CAP:]
    state["queued_ids"] = sorted(seen)[-4 * QUEUE_CAP:]
    rep["queue_len"] = len(state["queue"])
    rep["errors"] = dict(rep["errors"])
    return rep


def _accession_path(cik: str, acc: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}"


def drain_queue(http: Any, state: dict[str, Any], deadline: float, ua: str,
                cik_ticker: Mapping[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch queued filings until the budget ends. Form 4/5 -> the complete .txt (header + XML);
    SC 13D/G -> the small .hdr.sgml for the acceptance instant; 13F-HR -> bounded per pass."""
    rows: list[dict[str, Any]] = []
    rep: dict[str, Any] = {"fetched": Counter(), "errors": Counter(), "events": Counter()}
    queue: list[list[str]] = list(state.get("queue") or [])
    schedule_seen: set[str] = set()
    n13f = 0
    left: list[list[str]] = []
    for item in queue:
        if time.monotonic() >= deadline:
            left.append(item)
            continue
        form, cik, fname, day, acc, _company = (list(item) + [""] * 6)[:6]
        if form in ("4", "5"):
            st, text, err = http.text(f"https://www.sec.gov/Archives/{fname}",
                                      headers={"User-Agent": ua}, deadline=deadline)
            if not _ok(st):
                rep["errors"][err or f"HTTP {st}"] += 1
                if st not in (404, 403):
                    left.append(item)
                continue
            rep["fetched"]["form4"] += 1
            got = ic.parse_ownership(text, filed_date=day, family="form4", accession=acc)
            rows.extend(got)
            rep["events"]["form4"] += len(got)
        elif ic.is_13d(form) or ic.is_13g(form):
            if acc in schedule_seen:
                continue
            schedule_seen.add(acc)
            st, text, err = http.text(f"{_accession_path(cik, acc)}/{acc}.hdr.sgml",
                                      headers={"User-Agent": ua}, deadline=deadline)
            hdr = ic.parse_header(text) if _ok(st) else {}
            subject = str(hdr.get("subject_cik") or cik)
            ticker = cik_ticker.get(subject)
            if not ticker:
                rep["events"]["schedule_unquoted_subject"] += 1
                continue
            fam = "sc13d" if ic.is_13d(form) else "sc13g"
            rows.append(ic._filing_row(
                family=fam, accession=acc, owner=str(hdr.get("filer_cik") or ""),
                role="activist" if fam == "sc13d" else "passive", ticker=ticker,
                issuer_cik=subject, doc_type=form, direction=1,
                accepted_at=hdr.get("accepted_at"), filed_date=day, txn_date=None,
                value_usd=None))
            rep["fetched"][fam] += 1
            rep["events"][fam] += 1
        elif form == "13F-HR":
            if n13f >= MAX_13F_PER_PASS:
                left.append(item)
                continue
            n13f += 1
            got, err13 = collect_13f(http, cik, acc, deadline, ua, cik_ticker)
            if err13:
                rep["errors"][err13] += 1
            rows.extend(got)
            rep["fetched"]["13f"] += 1
            rep["events"]["13f"] += len(got)
    state["queue"] = left
    rep["queue_left"] = len(left)
    return rows, {k: dict(v) if isinstance(v, Counter) else v for k, v in rep.items()}


def _infotable(http: Any, cik: str, acc: str, deadline: float, ua: str
               ) -> dict[str, dict[str, Any]] | None:
    st, text, _err = http.text(f"{_accession_path(cik, acc)}/index.json",
                               headers={"User-Agent": ua}, deadline=deadline)
    try:
        items = json.loads(text)["directory"]["item"] if _ok(st) else []
    except (ValueError, KeyError, TypeError):
        items = []
    xmls = [str(i.get("name")) for i in items if isinstance(i, dict)
            and str(i.get("name", "")).lower().endswith(".xml")
            and "primary_doc" not in str(i.get("name", "")).lower()]
    if not xmls:
        return None
    st, text, _err = http.text(f"{_accession_path(cik, acc)}/{xmls[0]}",
                               headers={"User-Agent": ua}, deadline=deadline)
    return ic.parse_13f_table(text) if _ok(st) else None


def collect_13f(http: Any, cik: str, acc: str, deadline: float, ua: str,
                cik_ticker: Mapping[str, Any]) -> tuple[list[dict[str, Any]], str]:
    """One 13F-HR diffed against the same filer's previous 13F-HR (submissions JSON)."""
    st, text, err = http.text(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json",
                              headers={"User-Agent": ua}, deadline=deadline)
    try:
        recent = json.loads(text)["filings"]["recent"] if _ok(st) else None
    except (ValueError, KeyError, TypeError):
        recent = None
    if not isinstance(recent, dict):
        return [], err or "13f submissions unreadable"
    forms = list(recent.get("form") or [])
    accs = list(recent.get("accessionNumber") or [])
    times = list(recent.get("acceptanceDateTime") or [])
    idx = [i for i, f in enumerate(forms) if f == "13F-HR"]
    pos = next((k for k, i in enumerate(idx) if accs[i] == acc), None)
    if pos is None or pos + 1 >= len(idx):
        return [], "13f no prior filing"
    cur = _infotable(http, cik, acc, deadline, ua)
    old = _infotable(http, cik, accs[idx[pos + 1]], deadline, ua)
    if cur is None or old is None:
        return [], "13f info table unreadable"
    raw_t = str(times[idx[pos]] if idx[pos] < len(times) else "")
    # READ AS EASTERN, WHATEVER THE SUFFIX SAYS: if the stamp is really UTC this places the
    # event four or five hours LATER than the truth, which is the only safe direction to be wrong.
    acc_at = ic.parse_acceptance(raw_t.replace("T", "").replace("-", "").replace(":", "")[:14])
    titles = {ic.normalise_name(t): tk for tk, t in
              dict(cik_ticker.get("_titles") or {}).items()} if isinstance(
        cik_ticker.get("_titles"), dict) else {}
    out: list[dict[str, Any]] = []
    for d in ic.diff_13f(cur, old):
        tk = titles.get(ic.normalise_name(d["name"]))
        if not tk:
            continue
        out.append(ic._filing_row(
            family="13f", accession=f"{acc}:{d['cusip']}", owner=cik, role="institution",
            ticker=tk, issuer_cik="", doc_type="13F-HR", direction=int(d["direction"]),
            accepted_at=acc_at.isoformat() if acc_at else None, filed_date="",
            txn_date=None, value_usd=None, extra={"cusip": d["cusip"], "change": d["change"]}))
    return out, ""


def collect_form345_ds(http: Any, state: dict[str, Any], deadline: float, ua: str,
                       now: datetime) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Backfill one completed quarter per pass from the SEC's Insider Transactions Data Sets."""
    done = set(state.get("ds_done") or [])
    tried: dict[str, str] = dict(state.get("ds_tried") or {})
    q_end = date(now.year, 3 * ((now.month - 1) // 3) + 1, 1) - timedelta(days=1)
    quarters: list[str] = []
    d = q_end
    for _ in range(BACKFILL_QUARTERS):
        quarters.append(f"{d.year}q{_quarter(d)}")
        d = date(d.year, 3 * (_quarter(d) - 1) + 1, 1) - timedelta(days=1)
    due = [q for q in quarters if q not in done
           and tried.get(q, "") < (now - timedelta(days=1)).isoformat()]
    if not due:
        return [], {"status": "UP_TO_DATE", "done": sorted(done)}
    q = due[0]
    url = ("https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/"
           f"{q}_form345.zip")
    st, raw, err = http.bytes(url, headers={"User-Agent": ua}, deadline=deadline)
    tried[q] = now.isoformat()
    state["ds_tried"] = tried
    if not _ok(st):
        return [], {"status": "FAILED", "quarter": q, "error": err or f"HTTP {st}"}
    rows, census = ic.parse_form345_dataset(raw)
    done.add(q)
    state["ds_done"] = sorted(done)
    return rows, {"status": "FETCHED", "quarter": q, "events": len(rows), "census": census}


def collect_house(http: Any, state: dict[str, Any], deadline: float, now: datetime
                  ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The Clerk's yearly index (parsed by `free_stack.parse_house_fd_index`, reused), then the
    e-filed PTR PDFs not yet read. A PDF with no extractable text is a paper filing: counted."""
    from libs.data.free_stack import HOUSE_FD_ZIP, parse_house_fd_index
    try:
        from pypdf import PdfReader
    except ImportError:
        return [], {"status": UNMEASURED, "why": "pypdf is not installed on this host"}
    done = set(state.get("house_done") or [])
    rep: dict[str, Any] = {"pdfs": 0, "no_text": 0, "errors": Counter()}
    todo: list[tuple[str, str, int]] = []
    for year in sorted({now.year, (now - timedelta(days=45)).year}):
        st, raw, err = http.bytes(HOUSE_FD_ZIP.format(year=year), deadline=deadline)
        if not _ok(st):
            rep["errors"][err or f"HTTP {st}"] += 1
            continue
        for r in parse_house_fd_index(raw):
            if r.get("type") == "P" and r.get("doc") and r["doc"] not in done:
                todo.append((r["doc"], ic.parse_day(r.get("date")) or "", year))
    rows: list[dict[str, Any]] = []
    for doc, filed, year in sorted(todo, key=lambda x: x[1], reverse=True)[:MAX_HOUSE_PDFS]:
        if time.monotonic() >= deadline or not filed:
            break
        st, raw, err = http.bytes(HOUSE_PDF.format(year=year, doc=doc), deadline=deadline,
                                  max_bytes=20_000_000)
        if not _ok(st):
            rep["errors"][err or f"HTTP {st}"] += 1
            continue
        try:
            import io
            text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(raw)).pages)
        except Exception:
            text = ""
        rep["pdfs"] += 1
        done.add(doc)
        if not text.strip():
            rep["no_text"] += 1
            continue
        rows.extend(ic.parse_house_ptr_text(text, doc_id=doc, filed_date=filed))
    state["house_done"] = sorted(done)[-50_000:]
    rep["events"] = len(rows)
    rep["status"] = "FETCHED" if rep["pdfs"] or not rep["errors"] else "FAILED"
    rep["errors"] = dict(rep["errors"])
    return rows, rep


def collect_senate(http: Any, state: dict[str, Any], deadline: float, now: datetime
                   ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if os.environ.get("QUANT_SENATE_EFD_ATTEST", "").strip() != "1":
        return [], {"status": "AWAITING_PRINCIPAL",
                    "why": "eFD requires clicking a non-commercial-use attestation "
                           "(5 U.S.C. 13107(c)); QUANT_SENATE_EFD_ATTEST=1 is the principal's "
                           "switch. The parser is built and tested."}
    done = set(state.get("senate_done") or [])
    st, _t, err = http.text(f"{SENATE}/search/home/", deadline=deadline)
    token = http.cookie("csrftoken")
    if not _ok(st) or not token:
        return [], {"status": "FAILED", "error": err or "no csrf token"}
    hdr = {"Referer": f"{SENATE}/search/home/", "X-CSRFToken": token}
    http.post(f"{SENATE}/search/home/", {"prohibition_agreement": "1",
                                         "csrfmiddlewaretoken": token}, headers=hdr,
              deadline=deadline)
    since = (now - timedelta(days=30)).strftime("%m/%d/%Y 00:00:00")
    st, text, err = http.post(f"{SENATE}/search/report/data/", {
        "start": "0", "length": "100", "report_types": "[11]", "filer_types": "[]",
        "submitted_start_date": since, "submitted_end_date": "", "candidate_state": "",
        "senator_state": "", "office_id": "", "first_name": "", "last_name": "",
        "csrfmiddlewaretoken": http.cookie("csrftoken") or token},
        headers={**hdr, "Referer": f"{SENATE}/search/"}, deadline=deadline)
    try:
        reports = ic.parse_senate_search(json.loads(text)) if _ok(st) else []
    except ValueError:
        reports = []
    rows: list[dict[str, Any]] = []
    n = 0
    for r in reports:
        if r["report_id"] in done or n >= MAX_SENATE_REPORTS or time.monotonic() >= deadline:
            continue
        st, html, _err = http.text(f"{SENATE}/search/view/ptr/{r['report_id']}/",
                                   deadline=deadline)
        if not _ok(st):
            continue
        n += 1
        done.add(r["report_id"])
        rows.extend(ic.parse_senate_ptr_html(html, report_id=r["report_id"],
                                             filed_date=r["filed_date"]))
    state["senate_done"] = sorted(done)[-50_000:]
    return rows, {"status": "FETCHED" if n else "FAILED", "reports": n, "events": len(rows)}


def collect_kalshi(http: Any, state: dict[str, Any], deadline: float, now: datetime
                   ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Public Kalshi series in the macro categories, their open markets, and daily candles."""
    rows: list[dict[str, Any]] = []
    rep: dict[str, Any] = {"series": 0, "markets": 0, "errors": Counter()}
    series: list[str] = []
    for cat in KALSHI_CATEGORIES:
        st, text, err = http.text(f"{KALSHI}/series?category={cat}", deadline=deadline)
        try:
            doc = json.loads(text) if _ok(st) else {}
        except ValueError:
            doc = {}
        if not _ok(st):
            rep["errors"][err or f"HTTP {st}"] += 1
        for s in (doc.get("series") if isinstance(doc, dict) else None) or []:
            if isinstance(s, dict) and s.get("ticker") and ic.odds_category(
                    f"{s.get('title', '')} {s.get('ticker', '')}"):
                series.append(str(s["ticker"]))
    rep["series"] = len(series)
    start = int((now - timedelta(days=120)).timestamp())
    end = int(now.timestamp())
    for s in series:
        if time.monotonic() >= deadline or rep["markets"] >= MAX_ODDS_MARKETS:
            break
        st, text, _err = http.text(f"{KALSHI}/markets?series_ticker={s}&status=open&limit=20",
                                   deadline=deadline)
        try:
            markets = ic.parse_kalshi_markets(json.loads(text)) if _ok(st) else []
        except ValueError:
            markets = []
        for m in markets[:5]:
            if time.monotonic() >= deadline or rep["markets"] >= MAX_ODDS_MARKETS:
                break
            st, text, _err = http.text(
                f"{KALSHI}/series/{s}/markets/{m['ticker']}/candlesticks?start_ts={start}"
                f"&end_ts={end}&period_interval=1440", deadline=deadline)
            try:
                pts = ic.parse_kalshi_candles(json.loads(text)) if _ok(st) else []
            except ValueError:
                pts = []
            rep["markets"] += 1
            question = f"{m['question']} {s}"
            rows.extend(ic.odds_events("kalshi", m["ticker"], question, ic.daily_points(pts)))
    rep["events"] = len(rows)
    rep["status"] = "FETCHED" if rep["markets"] else "FAILED"
    rep["errors"] = dict(rep["errors"])
    return rows, rep


def collect_polymarket(http: Any, state: dict[str, Any], deadline: float, now: datetime
                       ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Open Polymarket markets by 24h volume, the macro ones by question, and their daily path
    from the CLOB price history (endpoints shared with `libs.data.prediction_markets`)."""
    from libs.data.prediction_markets import _CLOB, _GAMMA
    st, text, err = http.text(f"{_GAMMA}/markets?closed=false&limit=500&order=volume24hr"
                              "&ascending=false", deadline=deadline)
    try:
        markets = ic.parse_polymarket_markets(json.loads(text)) if _ok(st) else []
    except ValueError:
        markets = []
    if not _ok(st):
        return [], {"status": "FAILED", "error": err or f"HTTP {st}"}
    macro = [m for m in markets if ic.odds_category(m["question"])][:MAX_ODDS_MARKETS]
    rows: list[dict[str, Any]] = []
    n = 0
    for m in macro:
        if time.monotonic() >= deadline:
            break
        st, text, _err = http.text(f"{_CLOB}/prices-history?market={m['token']}&interval=max"
                                   "&fidelity=1440", deadline=deadline)
        try:
            pts = ic.parse_clob_history(json.loads(text)) if _ok(st) else []
        except ValueError:
            pts = []
        n += 1
        rows.extend(ic.odds_events("polymarket", m["id"], m["question"], ic.daily_points(pts)))
    return rows, {"status": "FETCHED" if n else "FAILED", "markets_listed": len(markets),
                  "macro_markets": len(macro), "histories": n, "events": len(rows)}


def _due(state: Mapping[str, Any], sid: str, now: datetime) -> bool:
    last = str((state.get("last_run") or {}).get(sid) or "")
    return not last or last <= (now - timedelta(seconds=int(SOURCES[sid]["cadence_s"]) - 300)
                                ).isoformat()


def collect(*, now: datetime, budget_s: float, http: Any = None,
            only: Sequence[str] | None = None
            ) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Every due, permitted source within `budget_s`. Returns (rows, per-source report, state)."""
    http = http or Http()
    state: dict[str, Any] = _read_json(STATE, {})
    t0 = time.monotonic()
    ua = edgar_ua()
    report: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    wanted = [s for s in SOURCES if not only or s in only]
    gates = {s: terms_gate(s) for s in wanted}
    for s in wanted:
        if not gates[s]["allowed"]:
            report[s] = {"status": "REFUSED", "terms": gates[s]}
    sec = [s for s in wanted if s in SEC_SOURCES and gates[s]["allowed"]]
    if sec and not ua:
        for s in sec:
            report[s] = {"status": "UNCONFIGURED",
                         "why": "no QUANT_EDGAR_UA / EDGAR_UA: the SEC's fair-access policy "
                                "requires a declared User-Agent, so nothing was fetched (a "
                                "configuration gap, not a closed source)"}
        sec = []
    if sec:
        dl = t0 + budget_s * 0.6
        cik_ticker = collect_tickers(http, state, dl, ua, now)
        if "sec_form4" in sec or "sec_13d" in sec or "sec_13f" in sec:
            idx = collect_edgar_index(http, state, dl, ua, now)
            got, drained = drain_queue(http, state, dl, ua, cik_ticker)
            rows.extend(got)
            for s in ("sec_form4", "sec_13d", "sec_13f"):
                if s in sec:
                    report[s] = {"status": "FETCHED" if idx["days"] or sum(
                        drained["fetched"].values()) else "FAILED", "index": idx,
                        "drain": drained}
        if "sec_form345_ds" in sec and time.monotonic() < dl:
            got, rep = collect_form345_ds(http, state, dl, ua, now)
            rows.extend(got)
            report["sec_form345_ds"] = rep
    others: list[tuple[str, Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]]]] = [
        ("kalshi", collect_kalshi), ("polymarket", collect_polymarket),
        ("house_ptr", collect_house), ("senate_ptr", collect_senate)]
    for sid, fn in others:
        if sid not in wanted or not gates[sid]["allowed"]:
            continue
        if not _due(state, sid, now):
            report[sid] = {"status": "NOT_DUE"}
            continue
        dl = min(t0 + budget_s * 0.95, time.monotonic() + budget_s * 0.12)
        try:
            got, rep = fn(http, state, dl, now)
        except Exception as exc:                         # one source never takes the pass down
            got, rep = [], {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"[:200]}
        rows.extend(got)
        report[sid] = rep
        if rep.get("status") == "FETCHED":
            state.setdefault("last_run", {})[sid] = now.isoformat()
    fails = dict(state.get("failures") or {})
    for sid, rep in report.items():
        st = str(rep.get("status"))
        if st == "FAILED":
            fails[sid] = int(fails.get(sid, 0)) + 1
        elif st in ("FETCHED", "UP_TO_DATE"):
            fails[sid] = 0
    state["failures"] = fails
    for sid in report:
        report[sid]["terms"] = gates.get(sid)
    return rows, report, state


# ------------------------------------------------------------------------------ store
def _content_hash(row: Mapping[str, Any]) -> str:
    keep = {k: v for k, v in row.items() if k not in ("first_seen_at", "_h")}
    return hashlib.sha256(json.dumps(keep, sort_keys=True, default=str).encode()).hexdigest()[:16]


def store_rows(path: Path = STORE) -> list[dict[str, Any]]:
    from mt5desk.family_informed_flow import read_rows
    return read_rows(path)


def append(rows: Sequence[Mapping[str, Any]], *, now: datetime, path: Path = STORE,
           ticker_cfd: Mapping[str, str] | None = None) -> dict[str, int]:
    """Append new or changed events; `instrument` is resolved here so the family needs no map."""
    have = {(str(r.get("event_id")), str(r.get("_h"))) for r in store_rows(path)}
    tmap = ticker_cfd or {}
    added = unchanged = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for r in rows:
            row = dict(r)
            if row.get("kind") == "filing" and not row.get("instrument"):
                row["instrument"] = tmap.get(str(row.get("ticker") or "")) or None
            h = _content_hash(row)
            if (str(row.get("event_id")), h) in have:
                unchanged += 1
                continue
            have.add((str(row.get("event_id")), h))
            row["_h"] = h
            row["first_seen_at"] = now.isoformat()
            fh.write(json.dumps(row, default=str) + "\n")
            added += 1
    return {"added": added, "unchanged": unchanged}


# ------------------------------------------------------------------------------ measurement
def _bonferroni_t(n: int, alpha: float = ALPHA) -> float:
    return float("inf") if n <= 0 else float(NormalDist().inv_cdf(1 - alpha / (2 * n)))


def _bench_map(targets: Sequence[str], universe_doc: Mapping[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for t in targets:
        row = universe_doc.get(t) if isinstance(universe_doc, Mapping) else None
        if isinstance(row, dict) and str(row.get("asset_class") or "") == "Equities":
            out[t] = "US500"
    return out


def _bars_loader() -> Callable[[str], Any]:
    try:
        from research.proposer_common import bars
    except Exception:                                         # pragma: no cover - import context
        return lambda _s: None
    return bars


def measure(rows: Sequence[Mapping[str, Any]], *, loader: Callable[[str], Any],
            universe_doc: Mapping[str, Any], clock: av.Clock | None = None,
            n_placebo: int = 200) -> dict[str, Any]:
    """Tracker, per-cell placebo, and the two-clock decay table."""
    clock = clock or av.bar_clock()
    universe = set(universe_doc) if universe_doc else None
    obs, census = ic.observations(rows, universe=universe)
    net = av.daily_net(obs)
    oracle, _ = ic.observations(rows, universe=universe, clock="oracle")
    onet = av.daily_net(oracle)
    targets = sorted({o.target for o in [*net, *onet]})
    bench = _bench_map(targets, universe_doc)
    bars: dict[str, av.DailyBars | None] = {}
    for sym in sorted({*targets, *bench.values()}):
        try:
            frame = loader(sym)
        except Exception:
            frame = None
        bars[sym] = av.to_daily(frame) if frame is not None else None
    tracked, tcensus = av.track(net, bars, bench=bench, clock=clock)
    otracked, _ = av.track(onet, bars, bench=bench, clock=clock)
    cell_placebo = {f"{h}d": av.placebo_contract(net, bars, horizon=h, clock=clock,
                                                 n_placebo=n_placebo, key=av.cell_key)
                    for h in av.HORIZONS_D}
    by_src = av.aggregate(tracked, ("source",))
    by_src_oracle = {g["source"]: g for g in av.aggregate(otracked, ("source",))}
    decay = []
    for g in by_src:
        o = by_src_oracle.get(g["source"]) or {}
        row: dict[str, Any] = {"source": g["source"]}
        for h in av.HORIZONS_D:
            a, b = g.get(f"{h}d") or {}, o.get(f"{h}d") or {}
            row[f"{h}d"] = {"observable_bp": a.get("mean_bp"), "oracle_bp": b.get("mean_bp"),
                            "decay_bp": (round(float(b["mean_bp"]) - float(a["mean_bp"]), 3)
                                         if a.get("mean_bp") is not None
                                         and b.get("mean_bp") is not None else UNMEASURED),
                            "n_observable": a.get("n"), "n_oracle": b.get("n")}
        decay.append(row)
    return {"observations": {"n": len(obs), "daily_net": len(net), "refused": census,
                             "tracked": len(tracked), "tracker": tcensus,
                             "bars_held": sorted(k for k, v in bars.items() if v is not None)},
            "by_source": by_src,
            "by_group": av.aggregate(tracked, ("target", "source", "relation", "lead")),
            "cell_placebo": cell_placebo,
            "two_clock_decay": {
                "rule": ("RESEARCH ONLY: the oracle clock is the transaction date, a document "
                         "that did not exist yet. decay_bp = oracle - observable; it feeds no "
                         "cell, no family and no axis"), "by_source": decay}}


def cell_rows(by_group: Sequence[Mapping[str, Any]],
              cell_placebo: Mapping[str, Mapping[str, Any]] | None, *,
              limit: int = MAX_DONATIONS
              ) -> tuple[list[dict[str, Any]], int, list[dict[str, Any]]]:
    """(candidates, trials charged, refusals). The Alpha Capture screen, reused in shape: one
    cell per (target, source, relation, lead) at its strongest horizon, when |t| clears
    Bonferroni over every measured (group, horizon) and 2.0 AND the cell's own shifted-date
    placebo ADMITTED it. No placebo verdict, no donation."""
    measured = [(g, h, g.get(f"{h}d") or {}) for g in by_group for h in av.HORIZONS_D]
    measured = [(g, h, s) for g, h, s in measured
                if s.get("status") == "MEASURED" and s.get("t") is not None]
    trials = len(measured)
    bar = max(PROPOSE_T, _bonferroni_t(trials))
    best: dict[tuple[str, ...], tuple[int, Mapping[str, Any]]] = {}
    refused: list[dict[str, Any]] = []
    for g, h, s in measured:
        if abs(float(s["t"])) < bar:
            continue
        key = (str(g["target"]), str(g["source"]), str(g["relation"]), str(g["lead"]))
        gate = ((cell_placebo or {}).get(f"{h}d") or {}).get("|".join(key)) or {}
        if gate.get("status") != "ADMIT":
            refused.append({"cell": "|".join(key), "horizon_d": h,
                            "why": f"placebo gate {gate.get('status', UNMEASURED)}"})
            continue
        if key not in best or abs(float(s["t"])) > abs(float(best[key][1]["t"])):
            best[key] = (h, s)
    out: list[dict[str, Any]] = []
    for (target, src, relation, lead), (h, s) in sorted(
            best.items(), key=lambda kv: -abs(float(kv[1][1]["t"]))):
        if len(out) >= limit:
            refused.append({"cell": f"{target}|{src}|{relation}|{lead}",
                            "why": f"over the {limit}-donation pass limit; it leads next pass"})
            continue
        side = 1 if float(s["mean_bp"]) > 0 else -1
        params: dict[str, Any] = {"symbol": target, "source": src, "relation": relation,
                                  "lead": lead, "side": side, "hold_days": h, "atr_n": 20,
                                  "stop_atr": 3.0, "rr": 1.5}
        cell = hashlib.sha256(json.dumps([target, FAMILY, params], sort_keys=True).encode()
                              ).hexdigest()[:16]
        gate = dict(((cell_placebo or {}).get(f"{h}d") or {}).get(
            f"{target}|{src}|{relation}|{lead}") or {})
        mech = (f"{MECHANISM}. {src} ({relation}{'/' + lead if lead else ''}) on {target}: "
                f"signed {h}d CAR mean {s['mean_bp']}bp, t={s['t']}, n={s['n']} daily-netted "
                f"events on the OBSERVABLE clock; side {side:+d} is the MEASURED sign")
        out.append({
            "source": SOURCE, "kind": "hypothesis", "symbol": target, "symbols": [target],
            "family": FAMILY, "params": params, "cell": cell,
            "title": f"{FAMILY} {target} <- {src} {relation} {h}d"[:120],
            "mechanism": mech[:400], "payer": PAYER, "constraint": CONSTRAINT,
            "structured": {"actor": src.split(":")[0], "constraint": CONSTRAINT,
                           "counterparty": "holders who read the disclosure late",
                           "mechanism": MECHANISM,
                           "why_edge_can_persist": "attention and arbitrage limits (above)",
                           "asset_mapping": f"{src} -> {target} ({relation})",
                           "horizon": f"{h}d", "session": "all",
                           "required_data": "desks/mt5/data/informed_capital/events.jsonl",
                           "pit_status": "PIT_CLEAN", "expected_cost": UNMEASURED,
                           "falsifier": "placebo-shifted disclosure dates show the same drift",
                           "source": src},
            "provenance": {"organ": "research/informed_capital.py", "source_id": src,
                           "relation": relation, "lead": lead,
                           "clock": "observable (acceptance / filing date +1d / venue tape)"},
            "declared_width": trials,
            "evidence": {"n": s["n"], "t": s["t"], "mean_bp": s["mean_bp"], "sd_bp": s["sd_bp"],
                         "hit": s["hit"], "horizon_d": h, "bonferroni_t": round(bar, 3),
                         "trials": trials, "cell_placebo": gate,
                         "screen": "signed CAR after the observable instant, daily-netted, "
                                   "Bonferroni over every measured (cell, horizon), and the "
                                   "cell's own shifted-date placebo ADMIT"}})
    return out, trials, refused


def _donate(candidates: list[dict[str, Any]], tests_run: int) -> Any:
    """The seam: one import, one call, so a test can watch what leaves."""
    from research.proposer_common import donate
    return donate(SOURCE, candidates, tests_run)


# ------------------------------------------------------------------------------ the fence
def fence(*, rows: Sequence[Mapping[str, Any]], sources: Mapping[str, Any],
          state: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    """GREEN / RED / UNMEASURED, with every reason named. Absence is never GREEN."""
    red: list[str] = []
    unmeasured: list[str] = []
    bad = ic.pit_violations(ic.latest_rows(rows))
    if bad:
        red.append(f"{len(bad)} event(s) observable BEFORE their own transaction date "
                   f"(first: {bad[0]})")
    for sid, n in sorted((state.get("failures") or {}).items()):
        if int(n) >= RED_AFTER_FAILURES:
            red.append(f"{sid} has FAILED {n} passes running")
    configured = [s for s, r in sources.items()
                  if str(r.get("status")) not in ("UNCONFIGURED", "REFUSED", "AWAITING_PRINCIPAL")]
    seen = [str(r.get("first_seen_at") or "") for r in rows]
    newest = max(seen) if seen else ""
    if configured and newest and newest < (now - timedelta(days=STALL_DAYS)).isoformat():
        red.append(f"the store has gained nothing since {newest} with {len(configured)} "
                   "source(s) configured")
    for sid, r in sources.items():
        if str(r.get("status")) in ("UNCONFIGURED", "AWAITING_PRINCIPAL"):
            unmeasured.append(f"{sid}: {r.get('status')}")
    if not rows:
        unmeasured.append("the store holds no event yet")
    status = "RED" if red else ("UNMEASURED" if not rows or not configured else "GREEN")
    return {"fence": status, "red": red, "unmeasured": unmeasured,
            "pit_violations": len(bad), "at": now.isoformat()}


# ------------------------------------------------------------------------------ the organ
def run(*, budget_s: float = 300.0, apply: bool = True, collect_enabled: bool = True,
        now: datetime | None = None, http: Any = None,
        loader: Callable[[str], Any] | None = None, clock: av.Clock | None = None,
        universe_doc: Mapping[str, Any] | None = None, only: Sequence[str] | None = None,
        n_placebo: int = 200, store: Path | None = None) -> dict[str, Any]:
    """One pass. Returns the report; writes only when `apply`."""
    started = time.monotonic()
    now = now or _now()
    store = store or STORE
    by_ticker, _ = _ticker_maps()
    if collect_enabled:
        got, sources, state = collect(now=now, budget_s=budget_s * 0.7, http=http, only=only)
    else:
        got, sources, state = [], {s: {"status": "SKIPPED"} for s in SOURCES}, _read_json(
            STATE, {})
    stored = (append(got, now=now, path=store, ticker_cfd=by_ticker) if apply and got
              else {"added": 0, "unchanged": 0, "dry_run": not apply})
    if apply and collect_enabled:
        _atomic(STATE, json.dumps(state, indent=1, default=str))
    rows = store_rows(store) if apply else [
        *store_rows(store), *[{**r, "instrument": r.get("instrument") or by_ticker.get(
            str(r.get("ticker") or "")), "first_seen_at": now.isoformat()} for r in got]]
    udoc = universe_doc if universe_doc is not None else _read_json(UNIVERSE, {})
    measured = measure(rows, loader=loader or _bars_loader(), universe_doc=udoc, clock=clock,
                       n_placebo=n_placebo)
    cands, trials, refused = cell_rows(measured["by_group"], measured["cell_placebo"])
    path = _donate(cands, max(trials, len(cands))) if (apply and cands) else None
    fam_counts = Counter(str(r.get("family")) for r in rows)
    fnc = fence(rows=rows, sources=sources, state=state, now=now)
    report = {
        "at": now.isoformat(), "source": SOURCE, "family": FAMILY,
        "elapsed_s": round(time.monotonic() - started, 2),
        "rule": ("every event is placed at its OBSERVABLE instant (SEC acceptance, a date-only "
                 "filing at the next UTC day 04:00 plus any posting lag, or the venue's own "
                 "price stamp); the transaction date feeds only the research-only decay table; "
                 "absence is UNMEASURED"),
        "fence": fnc,
        "sources": sources,
        "store": {**stored, "rows_total": len(rows), "by_family": dict(fam_counts),
                  "path": str(store)},
        "observations": measured["observations"],
        "by_source": measured["by_source"],
        "two_clock_decay": measured["two_clock_decay"],
        "cells": {"trials_charged": trials, "candidates": len(cands),
                  "donated": len(cands) if path else 0, "path": str(path) if path else None,
                  "refused": refused[:20],
                  "status": ("donated" if path else
                             "nothing cleared the screen yet: history accrues one pass and one "
                             "backfilled quarter at a time" if not cands else "dry run")},
        "transmission": {"direct": "share CFDs (news lane: informed_flow_drift is in "
                                   "universe_policy.NEWS_LANE_FAMILIES)",
                         "aggregate": list(ic.AGG_TARGETS),
                         "odds": {k: list(v) for k, v in ic.ODDS_TARGETS.items()}},
    }
    if apply:
        _atomic(REPORT, json.dumps(report, indent=1, ensure_ascii=False, default=str))
    return report


def check(path: Path = REPORT, *, max_age_s: float = 3 * 3600, now: datetime | None = None
          ) -> tuple[int, str]:
    """The RED check: exit 1 on a RED fence or a report missing or older than `max_age_s`."""
    now = now or _now()
    doc = _read_json(path, None)
    if not isinstance(doc, dict):
        return 1, f"RED: {path.name} is missing or unreadable"
    at = av.parse_time(doc.get("at"))
    if at is None or (now - at).total_seconds() > max_age_s:
        return 1, f"RED: {path.name} is stale (at={doc.get('at')})"
    f = doc.get("fence") or {}
    status = str(f.get("fence") or UNMEASURED)
    why = "; ".join(f.get("red") or f.get("unmeasured") or [])
    return (1 if status == "RED" else 0), f"{status}: {why}" if why else status


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="informed capital: insiders, stakes, congress, odds")
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--dry-run", action="store_true", help="measure and print; write nothing")
    ap.add_argument("--no-collect", action="store_true", help="fetch nothing; measure the store")
    ap.add_argument("--sources", default="", help="comma list of source ids to fetch")
    ap.add_argument("--check", action="store_true", help="exit 1 when the fence is RED")
    a = ap.parse_args(argv)
    if a.check:
        code, msg = check()
        print(msg)
        return code
    only = [s for s in a.sources.split(",") if s] or None
    rep = run(budget_s=a.budget_s, apply=not a.dry_run,
              collect_enabled=not a.no_collect and not a.dry_run, only=only)
    print(f"informed_capital at={rep['at']} elapsed={rep['elapsed_s']}s "
          f"fence={rep['fence']['fence']}")
    for sid, s in rep["sources"].items():
        print(f"  {sid:15} {s.get('status', '?')}")
    st = rep["store"]
    print(f"  store      +{st['added']} new, {st['rows_total']} rows {st.get('by_family')}")
    ob = rep["observations"]
    print(f"  tracked    {ob['tracked']} daily events of {ob['daily_net']}")
    c = rep["cells"]
    print(f"  cells      {c['candidates']} candidate(s), trials {c['trials_charged']}, "
          f"donated {c['donated']}")
    return 0


if __name__ == "__main__":                                       # pragma: no cover - CLI
    raise SystemExit(main())
