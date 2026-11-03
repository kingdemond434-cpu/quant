"""FORM 4 LANE -- open-market insider purchase CLUSTERS on the share CFDs, dated at SEC acceptance.

RESTORED (2026-11-03, sweep rows A18/A23, item #26). This lane was written on
`claude/land-alt-seat-cells` (2026-10-14..20, last touched at bc6549361) and proposed to LIVE as
draft PR #512, which never merged -- so `libs/research/form4.py` (the point-in-time cluster
scorer) and `family_event_reaction` (whose header names "an insider cluster from
libs.research.form4" as its first input) both described a lane that did not exist on LIVE. This is
that lane brought back on top of what LIVE holds now, with three deliberate differences:

  * SHARE CFDs ONLY. The #512 version also minted an index BREADTH cell (`form4_breadth` ->
    US500/NAS100/US2000). The sweep order for this lane is single-name events with no index
    sizing changes, so the breadth series and its cells are not carried here.
  * NO NEW EXECUTABLE. It is a module, run as a sub-organ of the clocked `alpha_capture` leg
    through `research/insider_event_lane.py`; it has no entry point of its own.
  * ONE EDGAR CLIENT (`EdgarClient`) shared with the buyback blackout calendar, so a pass reads
    each issuer's submissions index ONCE and both readers use it.

WHAT A PASS DOES, BOUNDED BY ITS DEADLINE:

  FETCH   For the broker-listed US share CFDs (`issuers()`: `alpha_capture.TICKERS` intersected
          with the Equities rows of `data/universe/universe.json`), the issuer's filing index
          (`data.sec.gov/submissions/CIK##########.json`) and each new Form 4's raw XML,
          round-robin across issuers, at most 8 requests a second (the SEC's fair-access ceiling
          is 10), with the declared User-Agent from `QUANT_EDGAR_UA`. The UA is sent, NEVER
          printed, logged or written. Without it the lane is UNCONFIGURED and fetches nothing.
  PARSE   Every non-derivative transaction, appended to `transactions.jsonl`, with
          `filed_at` = the SEC ACCEPTANCE time. The submissions API prints acceptance as an
          Eastern wall clock; it is moved to UTC by the LARGER Eastern offset (+5h): an hour late
          in summer, never early. Late only costs edge; early invents it.
  SCORE   Open-market purchases only (code P; `form4.NOT_A_DECISION` names why every other code
          is not a decision), replayed IN ACCEPTANCE ORDER and frozen the first instant a window
          holds `form4.MIN_BUYERS` distinct buyers (`freeze_clusters`), so a later filing can
          start a new cluster but never re-date an old one. `knowable_at` = the latest acceptance
          in the cluster. Appended to `clusters.jsonl`, which `insider_cluster_drift` reads.
  CELLS   `insider_cluster_drift` on each share CFD with `MIN_EVENTS` frozen clusters, through
          the one proposer door (stamped, lane-filtered, pre-registered), each identity once.
          The lane PROPOSES; the sealed gauntlet judges.

A 401, 403 OR 429 IS A HARD STOP. The first one ends the pass's SEC fetching and places a hold in
the lane's state (`hold`, `released_by: null`). Later passes request nothing from the SEC until a
PERSON writes their name into `released_by`; no timer and no Retry-After releases it. Scoring what
is already held still runs. No retry around a refusal, no identity rotation, no other route.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

STATE_DIR = DESK / "data" / "insider_events"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
SOURCE = "form4_lane"
UNMEASURED = "UNMEASURED"
UA_ENV = "QUANT_EDGAR_UA"

#: Ticker, CIK and listing exchange in one public file (the exchange feeds the NAS100 proxy).
TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
FORMS = ("4",)  # an amendment (4/A) restates its original: read once, never twice
#: Periodic reports whose acceptance times the buyback reader needs (XBRL facts carry only a day).
PERIODIC_FORMS = ("10-Q", "10-K", "10-Q/A", "10-K/A")
#: 8-K item 2.02, "Results of Operations and Financial Condition": the earnings release.
EARNINGS_ITEM = "2.02"

#: Seconds between requests: 8 a second, under the SEC's 10.
SPACING_S = 0.125
TIMEOUT_S = 20.0
ISSUERS_PER_PASS = 25
DOCS_PER_ISSUER = 15
LOOKBACK_DAYS = 400
EASTERN_LATE_H = 5

#: Frozen clusters a share CFD needs before its event cell is minted.
MIN_EVENTS = 3
EVENT_FAMILY = "insider_cluster_drift"
EVENT_HOLD_DAYS = 5

#: A refusal that ends the pass and holds the SEC for a person (the project's hard-stop rule).
HARD_STOP_STATUS = frozenset({401, 403, 429})

#: A getter returns (status, body) or (status, body, headers).
Getter = Callable[[str, dict[str, str]], tuple[Any, ...]]


# ------------------------------------------------------------------------------- io helpers

def _now() -> datetime:
    return datetime.now(tz=UTC)


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str), encoding="utf-8")
    os.replace(tmp, path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for ln in fh:
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(r, dict):
                    out.append(r)
    except OSError:
        pass
    return out


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")


def parse_time(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo is not None else t.replace(tzinfo=UTC)


# ------------------------------------------------------------------------------- the client

_CONTACT_RE = re.compile(r"[^\s@<>]+@[^\s@<>]+\.[A-Za-z]{2,}|https?://\S+\.\S+")


def ua_has_contact(ua: str) -> bool:
    """Does the declared User-Agent carry contact details (an email or a URL)? Never prints it."""
    return bool(_CONTACT_RE.search(ua or ""))


def urllib_getter(ua: str) -> Getter:
    """A spaced GET with the declared User-Agent. Never logs the header."""
    last = [0.0]

    def get(url: str, headers: dict[str, str]) -> tuple[int, bytes, dict[str, str]]:
        wait = SPACING_S - (time.monotonic() - last[0])
        if wait > 0:
            time.sleep(wait)
        last[0] = time.monotonic()
        req = urllib.request.Request(url, headers={"User-Agent": ua,
                                                   "Accept-Encoding": "identity", **headers})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return (int(resp.status), resp.read(16 * 1024 * 1024),
                        {str(k): str(v) for k, v in resp.headers.items()})
        except urllib.error.HTTPError as exc:
            hdrs = ({str(k): str(v) for k, v in exc.headers.items()}
                    if exc.headers is not None else {})
            return int(exc.code), b"", hdrs
        except (urllib.error.URLError, TimeoutError, OSError):
            return 0, b"", {}
    return get


class EdgarClient:
    """Every SEC request of a pass: robots-checked, hard-stopped, counted. One per pass.

    `get` is called only while no hold is active and the deadline has not passed. A 401/403/429
    (or a WAF challenge header) places `self.hold`; every later call returns (0, b"") without a
    request. robots.txt is read once a day per host through the same getter and every URL is
    judged against it; an unreadable robots.txt stops the pass (`robots_unavailable`).
    """

    def __init__(self, get: Getter, state: dict[str, Any], *, now: datetime,
                 deadline: float, ua: str = "") -> None:
        self._get = get
        self.state = state
        self.now = now
        self.deadline = deadline
        self.token = re.split(r"[/\s]", (ua or "").strip(), maxsplit=1)[0] or "*"
        self.requests = 0
        self.ok = 0
        self.errors: Counter[str] = Counter()
        self.hold: dict[str, Any] | None = None
        self.robots_unavailable = False
        self.robots_disallowed = 0
        self._parsers: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    @property
    def stopped(self) -> bool:
        return (self.hold is not None or self.robots_unavailable
                or time.monotonic() >= self.deadline)

    def _raw(self, url: str) -> tuple[int, bytes, dict[str, str]]:
        out = self._get(url, {})
        self.requests += 1
        status = int(out[0]) if out else 0
        body = out[1] if len(out) > 1 and isinstance(out[1], bytes | bytearray) else b""
        hdrs = out[2] if len(out) > 2 and isinstance(out[2], dict) else {}
        hdrs = {str(k).lower(): str(v) for k, v in hdrs.items()}
        challenged = hdrs.get("cf-mitigated", "").lower() == "challenge"
        if status in HARD_STOP_STATUS or challenged:
            self.hold = {"status": status, "host": urllib.parse.urlsplit(url).netloc,
                         "url_class": _url_class(url), "at": self.now.isoformat(),
                         "verdict": "NEEDS_KEY" if status == 401 else "METHOD_BLOCKED",
                         "retry_after": hdrs.get("retry-after"), "released_by": None,
                         "release": ("a person sets released_by in the lane state "
                                     "(desks/mt5/data/insider_events/state.json); no timer "
                                     "releases it")}
            return status, b"", hdrs
        return status, bytes(body), hdrs

    def _robots(self, url: str) -> urllib.robotparser.RobotFileParser | None:
        parts = urllib.parse.urlsplit(url)
        host = parts.netloc
        if host in self._parsers:
            return self._parsers[host]
        cache = self.state.setdefault("robots", {})
        hit = cache.get(host) if isinstance(cache.get(host), dict) else None
        fresh = hit and (parse_time(hit.get("at")) or datetime.min.replace(tzinfo=UTC)) \
            > self.now - timedelta(days=1)
        if fresh and hit is not None:
            status, text = int(hit.get("status") or 0), str(hit.get("text") or "")
        else:
            status, raw, _h = self._raw(f"{parts.scheme}://{host}/robots.txt")
            if self.hold is not None:
                self._parsers[host] = None
                return None
            text = raw.decode("utf-8", "replace")
            cache[host] = {"at": self.now.isoformat(), "status": status, "text": text[:65536]}
        rp = urllib.robotparser.RobotFileParser()
        if status == 200:
            rp.parse(text.splitlines())
        elif 400 <= status < 500:
            rp.parse([])                 # no robots.txt published: nothing is disallowed
        else:
            self.robots_unavailable = True
            self._parsers[host] = None
            return None
        self._parsers[host] = rp
        return rp

    def fetch(self, url: str) -> tuple[int, bytes] | None:
        """(status, body), or None when the pass is stopped or robots disallows the URL."""
        if self.stopped:
            return None
        rp = self._robots(url)
        if rp is None or self.stopped:
            return None
        if not rp.can_fetch(self.token, url):
            self.robots_disallowed += 1
            return None
        status, body, _h = self._raw(url)
        if self.hold is not None:
            return None
        if status == 200:
            self.ok += 1
        else:
            self.errors[f"{_url_class(url)} HTTP {status}"] += 1
        return status, body

    def report(self) -> dict[str, Any]:
        return {"requests": self.requests, "ok_responses": self.ok,
                "errors": dict(self.errors), "hold": self.hold,
                "robots_unavailable": self.robots_unavailable,
                "robots_disallowed": self.robots_disallowed}


def _url_class(url: str) -> str:
    path = urllib.parse.urlsplit(url).path
    if path.endswith("robots.txt"):
        return "robots"
    if "/submissions/" in path:
        return "submissions"
    if "/api/xbrl/" in path:
        return "xbrl"
    if path.startswith("/files/"):
        return "ticker_map"
    return "archive"


def active_hold(state: Mapping[str, Any]) -> dict[str, Any] | None:
    """The person-released hold, if one is in force. `released_by` set by a person ends it."""
    h = state.get("hold")
    if isinstance(h, dict) and not str(h.get("released_by") or "").strip():
        return h
    return None


# ------------------------------------------------------------------------------- instruments

def issuers(universe_path: Path | None = None) -> dict[str, str]:
    """Broker-listed share CFD -> US ticker. Only names the universe lists as Equities."""
    try:
        from research.alpha_capture import TICKERS
    except ImportError:                                     # pragma: no cover - layout
        from alpha_capture import TICKERS  # type: ignore[no-redef,import-not-found]
    uni = read_json(universe_path or UNIVERSE, {})
    listed = {str(k) for k, v in (uni.items() if isinstance(uni, dict) else [])
              if isinstance(v, dict) and str(v.get("asset_class") or "") == "Equities"}
    return {k: v for k, v in TICKERS.items() if k in listed}


def cik_map(raw: bytes) -> dict[str, dict[str, Any]]:
    """`company_tickers_exchange.json` (or the plain ticker file) -> {TICKER: {cik, exchange}}."""
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {}
    out: dict[str, dict[str, Any]] = {}
    if isinstance(doc, dict) and isinstance(doc.get("fields"), list):
        fields = [str(f) for f in doc["fields"]]
        for row in doc.get("data") or []:
            r = dict(zip(fields, row, strict=False)) if isinstance(row, list) else {}
            if r.get("ticker") and r.get("cik") is not None:
                try:
                    out[str(r["ticker"]).upper()] = {"cik": int(r["cik"]),
                                                     "exchange": str(r.get("exchange") or "")}
                except (TypeError, ValueError):
                    continue
        return out
    rows = doc.values() if isinstance(doc, dict) else doc if isinstance(doc, list) else []
    for r in rows:
        if isinstance(r, dict) and r.get("ticker") and r.get("cik_str") is not None:
            try:
                out[str(r["ticker"]).upper()] = {"cik": int(r["cik_str"]), "exchange": ""}
            except (TypeError, ValueError):
                continue
    return out


def accepted_utc(wall: str) -> datetime | None:
    """The acceptance wall clock (Eastern, whatever suffix it carries) moved LATE to UTC."""
    m = re.match(r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})", str(wall or ""))
    if not m:
        return None
    try:
        naive = datetime.fromisoformat(f"{m.group(1)}T{m.group(2)}")
    except ValueError:
        return None
    return naive.replace(tzinfo=UTC) + timedelta(hours=EASTERN_LATE_H)


def submissions(raw: bytes) -> dict[str, Any]:
    """One submissions index -> its Form 4s, earnings 8-Ks and periodic-report acceptances."""
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {"form4": [], "earnings": [], "periodic": {}}
    rec = ((doc or {}).get("filings") or {}).get("recent") or {}
    forms = rec.get("form") or []
    items = rec.get("items") or []
    form4: list[dict[str, Any]] = []
    earnings: list[str] = []
    periodic: dict[str, str] = {}
    for i, form in enumerate(forms):
        form = str(form)
        try:
            acc = str(rec["accessionNumber"][i])
            at = accepted_utc(str(rec["acceptanceDateTime"][i]))
        except (KeyError, IndexError, TypeError):
            continue
        if at is None:
            continue
        if form in FORMS:
            try:
                doc_name = str(rec["primaryDocument"][i])
            except (KeyError, IndexError, TypeError):
                continue
            form4.append({"form": form, "accession": acc, "filed_at": at.isoformat(),
                          "document": doc_name.split("/")[-1]})
        elif form == "8-K" and i < len(items) and EARNINGS_ITEM in str(items[i]).split(","):
            earnings.append(at.isoformat())
        elif form in PERIODIC_FORMS:
            periodic[acc] = at.isoformat()
    form4.sort(key=lambda r: r["filed_at"], reverse=True)
    return {"form4": form4, "earnings": sorted(set(earnings)), "periodic": periodic}


def filing_index(raw: bytes) -> list[dict[str, Any]]:
    """The issuer's recent Form 4 filings, newest first (kept for the #512 call sites)."""
    return list(submissions(raw)["form4"])


def _text(node: ET.Element | None, path: str) -> str:
    if node is None:
        return ""
    hit = node.find(path)
    if hit is None:
        return ""
    val = hit.find("value")
    return str((val.text if val is not None else hit.text) or "").strip()


def _float(text: str) -> float | None:
    try:
        f = float(text)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def parse_form4(raw: bytes) -> list[dict[str, Any]]:
    """Every non-derivative transaction in one Form 4 document."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    owner = root.find("reportingOwner")
    name = _text(owner, "reportingOwnerId/rptOwnerName")
    rel = owner.find("reportingOwnerRelationship") if owner is not None else None
    title = _text(rel, "officerTitle")
    if not title and rel is not None:
        flags = [label for tag, label in (("isDirector", "director"), ("isOfficer", "officer"),
                                          ("isTenPercentOwner", "10% owner"))
                 if _text(rel, tag) in {"1", "true"}]
        title = ", ".join(flags) or "other"
    issuer = _text(root, "issuer/issuerTradingSymbol").upper()
    out: list[dict[str, Any]] = []
    for t in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        code = _text(t, "transactionCoding/transactionCode").upper()
        shares = _float(_text(t, "transactionAmounts/transactionShares"))
        price = _float(_text(t, "transactionAmounts/transactionPricePerShare"))
        when = _text(t, "transactionDate")
        if not code or shares is None or not when:
            continue
        out.append({"issuer_ticker": issuer, "insider": name, "title": title,
                    "txn_date": when[:10], "code": code, "shares": shares,
                    "price": price if price is not None else 0.0,
                    "acquired_disposed": _text(t, "transactionAmounts/"
                                                  "transactionAcquiredDisposedCode").upper(),
                    "shares_after": _float(_text(t, "postTransactionAmounts/"
                                                    "sharesOwnedFollowingTransaction")) or 0.0})
    return out


# ------------------------------------------------------------------------------- the fetch

def ensure_ciks(client: EdgarClient, state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """{TICKER: {cik, exchange}}, from state or one ticker-map request (refreshed weekly)."""
    held = state.get("ciks") if isinstance(state.get("ciks"), dict) else {}
    when = parse_time(state.get("ciks_at"))
    if held and when is not None and when > client.now - timedelta(days=7):
        return held
    got = client.fetch(TICKER_MAP_URL)
    if got and got[0] == 200:
        fresh = cik_map(got[1])
        if fresh:
            state["ciks"] = fresh
            state["ciks_at"] = client.now.isoformat()
            return fresh
    return held or {}


def lookup(ciks: Mapping[str, Any], ticker: str) -> dict[str, Any] | None:
    t = ticker.upper()
    hit = ciks.get(t) or ciks.get(t.replace("-", ".")) or ciks.get(t.replace(".", "-"))
    return hit if isinstance(hit, dict) else None


def fetch_pass(client: EdgarClient, state: dict[str, Any], *, names: dict[str, str]
               ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """New transactions this pass. `state` is updated in place, including the per-issuer
    filing facts (`state["filings"][sym]`) the buyback reader uses."""
    now = client.now
    rep: dict[str, Any] = {"issuers_visited": 0, "filings_read": 0, "transactions": 0}
    ciks = ensure_ciks(client, state)
    if not ciks:
        return [], rep
    seen: set[str] = set(state.get("seen") or [])
    backfilled: set[str] = set(state.get("backfilled") or [])
    facts: dict[str, Any] = state.setdefault("filings", {})
    order = sorted(names)
    start = int(state.get("cursor") or 0) % max(1, len(order))
    order = order[start:] + order[:start]
    floor = now - timedelta(days=LOOKBACK_DAYS)
    fresh: list[dict[str, Any]] = []
    visited = 0
    no_cik: list[str] = []
    for sym in order[:ISSUERS_PER_PASS]:
        if client.stopped:
            break
        hit = lookup(ciks, names[sym])
        if not hit:
            no_cik.append(sym)
            backfilled.add(sym)          # the SEC lists no such filer: nothing to backfill
            visited += 1
            continue
        cik = int(hit["cik"])
        got = client.fetch(SUBMISSIONS_URL.format(cik=cik))
        if got is None and client.stopped:
            break                        # hold, robots unavailable or deadline: first next pass
        visited += 1
        if got is None:
            continue                     # robots disallows this index: not fetched, not owed
        if got[0] != 200:
            continue
        sub = submissions(got[1])
        facts[sym] = {"cik": cik, "exchange": str(hit.get("exchange") or ""),
                      "earnings": sub["earnings"], "periodic": sub["periodic"],
                      "at": now.isoformat()}
        index = [f for f in sub["form4"] if f["accession"] not in seen
                 and (parse_time(f["filed_at"]) or now) >= floor]
        done_all = True
        for f in index[:DOCS_PER_ISSUER]:
            acc = f["accession"]
            url = ARCHIVE_URL.format(cik=cik, acc=acc.replace("-", ""), doc=f["document"])
            got = client.fetch(url)
            if got is None or got[0] != 200:
                done_all = False         # unread: it stays owed, never frozen around
                if got is None and client.stopped:
                    break
                continue
            seen.add(acc)
            rep["filings_read"] += 1
            for txn in parse_form4(got[1]):
                txn.update({"symbol": sym, "cik": cik, "accession": acc,
                            "filed_at": f["filed_at"], "form": f["form"],
                            "first_seen_at": now.isoformat(timespec="seconds")})
                fresh.append(txn)
        # THE UNREAD FLOOR: a cluster is exact as of t only when every filing accepted by t is
        # held, so the issuer freezes only strictly before its oldest still-unread acceptance.
        unread = [parse_time(f["filed_at"]) or floor for f in index if f["accession"] not in seen]
        floors = state.setdefault("unread_floor", {})
        if unread:
            floors[sym] = min(unread).isoformat(timespec="seconds")
        else:
            floors.pop(sym, None)
        if done_all and len(index) <= DOCS_PER_ISSUER:
            backfilled.add(sym)
    state["cursor"] = (start + visited) % max(1, len(order))
    state["seen"] = sorted(seen)
    state["backfilled"] = sorted(backfilled)
    rep.update({"issuers_visited": visited, "no_cik": no_cik, "transactions": len(fresh)})
    return fresh, rep


# ------------------------------------------------------------------------------- scoring

def txn_key(r: Mapping[str, Any]) -> str:
    """One transaction's identity in the append-only store (a filing may hold several)."""
    return "|".join(str(r.get(k) or "") for k in ("accession", "insider", "txn_date", "code",
                                                    "shares", "price"))


def _keyed_txns(rows: list[dict[str, Any]]) -> list[tuple[str, Any]]:
    from libs.research.form4 import Form4Txn
    out: list[tuple[str, Any]] = []
    for r in rows:
        filed = parse_time(r.get("filed_at"))
        try:
            txn_date = datetime.fromisoformat(str(r.get("txn_date"))[:10]).replace(tzinfo=UTC)
        except ValueError:
            continue
        if filed is None:
            continue
        out.append((txn_key(r), Form4Txn(
            issuer=str(r.get("symbol")), insider=str(r.get("insider") or ""),
            title=str(r.get("title") or ""), txn_date=txn_date, filed_at=filed,
            code=str(r.get("code") or ""), shares=float(r.get("shares") or 0.0),
            price=float(r.get("price") or 0.0),
            shares_after=float(r.get("shares_after") or 0.0))))
    return out


def freeze_clusters(rows: list[dict[str, Any]], frozen: list[dict[str, Any]],
                    unread_floor: Mapping[str, datetime] | None = None
                    ) -> list[dict[str, Any]]:
    """The clusters NOT yet in `frozen`, each frozen at the first acceptance instant it qualified.

    Transactions are replayed in acceptance order; at each instant t only filings accepted by t
    exist, and a window becomes a cluster the moment it first holds `MIN_BUYERS` distinct buyers
    among transactions no frozen cluster already holds. Its rows, buyers, score (baseline strictly
    before t) and `knowable_at = t` then never change. `unread_floor` stops an issuer's replay at
    its oldest unread filing.
    """
    from libs.research import form4
    used = {k for c in frozen for k in (c.get("rows") or [])}
    held = {(str(c.get("symbol")), str(c.get("knowable_at"))) for c in frozen}
    keyed = [(k, t) for k, t in _keyed_txns(rows) if t.is_open_market_buy]
    all_buys = [t for _k, t in keyed]
    by_issuer: dict[str, list[tuple[str, Any]]] = {}
    for k, t in sorted(keyed, key=lambda kt: (kt[1].filed_at, kt[0])):
        by_issuer.setdefault(t.issuer, []).append((k, t))
    wd = form4.WINDOW_DAYS
    out: list[dict[str, Any]] = []
    for issuer, items in by_issuer.items():
        public: list[tuple[str, Any]] = []
        i = 0
        cut = (unread_floor or {}).get(issuer)
        while i < len(items):
            t_now = items[i][1].filed_at
            if cut is not None and t_now >= cut:
                break
            batch = []
            while i < len(items) and items[i][1].filed_at == t_now:
                batch.append(items[i])
                i += 1
            public.extend(batch)
            for bk, b in batch:
                if bk in used:
                    continue
                pool = [(k, x) for k, x in public if k not in used]
                anchors = sorted(((k, x) for k, x in pool
                                  if 0 <= (b.txn_date - x.txn_date).days <= wd),
                                 key=lambda kx: (kx[1].txn_date, kx[1].filed_at, kx[0]))
                for _ak, a in anchors:
                    win = [(k, x) for k, x in pool if 0 <= (x.txn_date - a.txn_date).days <= wd]
                    people = {x.insider for _k, x in win}
                    if len(people) < form4.MIN_BUYERS:
                        continue
                    rows_in = [x for _k, x in win]
                    med, rate = form4._issuer_baseline(all_buys, issuer, t_now,
                                                       frozenset(rows_in))
                    value = sum(x.value for x in rows_in)
                    comp = form4._score_components(rows_in, people, value, med, rate, wd)
                    c = form4.Cluster(
                        issuer=issuer, knowable_at=t_now,
                        first_txn_date=min(x.txn_date for x in rows_in),
                        buyers=tuple(sorted(people)), value=value,
                        score=round(sum(comp.values()), 4), components=comp,
                        why=(f"{len(people)} insiders bought ${value:,.0f} of {issuer} within "
                             f"{wd}d; public at {t_now.isoformat()} (frozen)"))
                    used |= {k for k, _x in win}
                    rec = {"symbol": issuer, "kind": "INSIDER_CLUSTER", **c.to_dict(),
                           "rows": sorted(k for k, _ in win)}
                    if (issuer, rec["knowable_at"]) not in held:
                        out.append(rec)
                    break
    out.sort(key=lambda r: (r["knowable_at"], r["symbol"]))
    return out


def score(rows: list[dict[str, Any]], frozen: list[dict[str, Any]] | None = None,
          backfilled: set[str] | None = None,
          unread_floor: Mapping[str, datetime] | None = None
          ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """(every frozen cluster, the new ones, the census). Only BACKFILLED issuers freeze: before
    an issuer's history is in hand a cluster could lack a buyer and its baseline is short."""
    from libs.research import form4
    prior = [c for c in (frozen or []) if c.get("rows")]
    ready = rows if backfilled is None else [r for r in rows
                                             if str(r.get("symbol")) in backfilled]
    new = freeze_clusters(ready, prior, unread_floor)
    allc = sorted(prior + new, key=lambda r: (r["knowable_at"], r["symbol"]))
    census = form4.census([t for _k, t in _keyed_txns(rows)])
    if backfilled is not None:
        rest = [r for r in rows if str(r.get("symbol")) not in backfilled]
        census["clusters_ephemeral"] = len(freeze_clusters(rest, []))
    return allc, new, census


# ------------------------------------------------------------------------------- cells

def event_cells(clusters: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    by_sym = Counter(str(c.get("symbol")) for c in clusters)
    cells: list[dict[str, Any]] = []
    accruing: dict[str, int] = {}
    for sym, n in sorted(by_sym.items()):
        if n < MIN_EVENTS:
            accruing[sym] = n
            continue
        cells.append({"symbol": sym, "symbols": [sym], "kind": "hypothesis",
                      "family": EVENT_FAMILY,
                      "params": {"symbol": sym, "source": "form4",
                                 "hold_days": EVENT_HOLD_DAYS, "timeframe": "H1"},
                      "title": f"Form 4 insider purchase cluster -> {sym} drift "
                               f"({n} clusters)"[:120],
                      "mechanism": ("several insiders buying their own stock with their own "
                                    "money inside a few days is information the market "
                                    "under-reacts to; the price drifts toward it after the "
                                    "SEC acceptance makes it public"),
                      "falsifier": (f"{sym} returns over {EVENT_HOLD_DAYS} trading days after "
                                    "each cluster's acceptance time are no better than the "
                                    "name's unconditional drift, net of costs"),
                      "lane": "event"})
    return cells, accruing


def run(client: EdgarClient | None, state: dict[str, Any], *, names: dict[str, str],
        state_dir: Path, now: datetime) -> dict[str, Any]:
    """Fetch (when a client is given), freeze, and return the report plus cells. Writes the
    lane's own append-only stores under `state_dir`; `state` is saved by the caller."""
    txn_path, cl_path = state_dir / "form4_transactions.jsonl", state_dir / "clusters.jsonl"
    fetch: dict[str, Any] = {"status": "SKIPPED"}
    if client is not None:
        fresh, rep = fetch_pass(client, state, names=names)
        fetch = {**rep, "status": "FETCHED" if client.ok else "FAILED" if client.requests
                 else "IDLE"}
        append_jsonl(txn_path, fresh)
    rows = read_jsonl(txn_path)
    stored = read_jsonl(cl_path)
    floors = {str(k): t for k, v in (state.get("unread_floor") or {}).items()
              if (t := parse_time(v)) is not None}
    backfilled = set(state.get("backfilled") or [])
    clusters, new, census = score(rows, stored, backfilled, floors)
    append_jsonl(cl_path, new)                                   # APPEND-ONLY
    cells, accruing = event_cells(clusters)
    return {"fetch": fetch, "transactions": len(rows), "census": census,
            "clusters": len(clusters), "clusters_new": len(new),
            "clusters_by_symbol": dict(Counter(c["symbol"] for c in clusters).most_common()),
            "backfill": {"issuers_backfilled": len(backfilled & set(names)), "of": len(names),
                         "complete": bool(names) and set(names) <= backfilled},
            "event": {"family": EVENT_FAMILY, "cells": len(cells), "min_events": MIN_EVENTS,
                      "accruing": accruing},
            "store": str(cl_path), "_cells": cells}
