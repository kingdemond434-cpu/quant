"""FORM 4 LANE -- insider purchase clusters as an index BREADTH STATE and a share-CFD EVENT LANE.

WHY THIS EXISTS. `libs/research/form4.py` -- a point-in-time Form 4 P-code cluster scorer, with
the acceptance-time rule, the transaction-code discipline and the issuer-baseline rarity term all
written and tested -- was imported by its test and by nothing else. The desk's only EDGAR seat
(`side_channels/sec_edgar_miner.py`) emits a constant "this fund has a recent 13F" notice that
carries no information (`alt_seat_cells` refuses it as NO_INFORMATION). So the one EDGAR filing
that IS timely -- due within two business days, not 45 after quarter end -- was never read.

WHAT THIS DOES, EVERY HOUR, BOUNDED:

  FETCH   For the Fusion share CFDs with a US listing (`alpha_capture.TICKERS`), the issuer's
          filing index (`data.sec.gov/submissions/CIK##########.json`) and each new Form 4's own
          XML from the EDGAR archive, round-robin across issuers so a pass never exceeds its
          budget, at most 8 requests a second (the SEC's fair-access ceiling is 10), with the
          User-Agent the SEC requires from `QUANT_EDGAR_UA`. The UA is read and sent, NEVER
          printed, logged or written; without it the lane reads UNCONFIGURED and fetches nothing.
  PARSE   Every non-derivative transaction, kept append-only in `data/form4/transactions.jsonl`,
          with `filed_at` = the SEC ACCEPTANCE time. The submissions API prints acceptance as an
          Eastern wall clock, so it is read as such and moved to UTC by the LARGER of the two
          Eastern offsets (+5h): in summer that is an hour late, never early. Late only costs
          edge; early invents it.
  SCORE   `libs.research.form4.clusters` over open-market purchases (code P only), dated at the
          latest acceptance time in each cluster (`knowable_at`). Written to
          `data/form4/clusters.jsonl`, which the event family reads.
  STATE   `data/lake/series/form4_breadth.csv`: per UTC day, the summed cluster score and the
          cluster count over the trailing 30 days, as known at the END of that day. The family
          (`exogenous_conditioner`) then holds it back a further publication day.
  CELLS   Through `proposer_common.donate` (stamped, lane-filtered, pre-registered), once each:
            breadth   `exogenous_conditioner` on US500, NAS100 and US2000 -- aggregate insider
                      buying at an extreme of its own history is bought (Lakonishok & Lee 2001:
                      aggregate insider purchases lead the market). Minted only once every
                      issuer has been backfilled once and the series has `MIN_POINTS` days.
            event     `insider_cluster_drift` on each share CFD with `MIN_EVENTS` clusters in the
                      store (the news lane; `universe_policy.NEWS_LANE_FAMILIES`).
          One cell is one trial, charged at the docket; nothing is donated twice.

A 401, 403 OR 429 IS A HARD STOP. The first one ends the pass's SEC fetching; the lane records
METHOD_BLOCKED (403/429) or NEEDS_KEY (401) with the status, URL class and time, and places a
person-released hold (`hard_stop.hold_record`, `released_by` null) in the desk's register
`data/intelligence/blocked_sources.json`: later passes request nothing until a named person
releases it (`python -m desks.mt5.research.hard_stop --release <key> --by <name>`). Retry-After is
recorded and never releases a hold; no timer does. Scoring what is already held still runs, and
the report reads UNMEASURED for new data. No retry around the block, no identity rotation, no
other route to the same content.

    python desks/mt5/research/form4_lane.py --once [--budget-s 300]
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

STATE_DIR = DESK / "data" / "form4"
SERIES_DIR = DESK / "data" / "lake" / "series"
REPORT = DESK / "reports" / "FORM4_LANE.json"
SOURCE = "form4"
UNMEASURED = "UNMEASURED"
UA_ENV = "QUANT_EDGAR_UA"

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
FORMS = ("4",)  # an amendment (4/A) restates its original: read once, never twice

#: Seconds between requests: 8 a second, under the SEC's 10.
SPACING_S = 0.125
TIMEOUT_S = 20.0
#: Issuers visited per pass and new filings read per issuer per pass. The cursor rotates, so the
#: whole list is reached across passes; what a pass leaves is owed, never refused.
ISSUERS_PER_PASS = 25
DOCS_PER_ISSUER = 15
#: How far back a first visit reads an issuer's Form 4 history.
LOOKBACK_DAYS = 400
#: The Eastern-to-UTC shift applied to the acceptance wall clock: the larger offset, so late.
EASTERN_LATE_H = 5

BREADTH_SERIES = "form4_breadth"
BREADTH_TARGETS = ("US500", "NAS100", "US2000")
BREADTH_WINDOW_D = 30
#: Days the breadth series needs before its cells are minted (the conditioner's 30 + warm-up).
MIN_POINTS = 35
#: Clusters a share CFD needs in the store before its event cell is minted.
MIN_EVENTS = 3
EVENT_FAMILY = "insider_cluster_drift"
EVENT_HOLD_DAYS = 5

#: A getter returns (status, body) or (status, body, response headers); the headers are read
#: only for Retry-After.
Getter = Callable[[str, dict[str, str]], tuple[Any, ...]]

#: THE HARD STOP (standing project rule; one implementation in `research/hard_stop.py`). A 401,
#: 403, 429 or WAF challenge ends the pass's SEC fetching on the spot and places a hold on the
#: refusing host that only a PERSON releases (`python -m desks.mt5.research.hard_stop --release
#: site:<host> --by <name>`); until then no SEC host is sent a request, whatever time has passed.
#: The lane still scores what it already holds. It never retries around the hold, rotates identity
#: or takes another route to the same gated content.
try:
    from research import hard_stop as _hs
except ImportError:                                         # pragma: no cover - layout
    import hard_stop as _hs  # type: ignore[no-redef,import-not-found]
HARD_STOP = _hs.HARD_STOP
BLOCKED_REGISTER = _hs.BLOCKED_REGISTER
#: Every SEC host the lane requests; a hold on any one stops the lane's fetching.
SEC_HOSTS = ("www.sec.gov", "data.sec.gov")
retry_after_s = _hs.retry_after_s
REGISTER_KEY = "sec_edgar_form4"


# ------------------------------------------------------------------------------- io helpers

def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _jsonl(path: Path) -> list[dict[str, Any]]:
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


def _parse_time(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo is not None else t.replace(tzinfo=UTC)


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
                return (int(resp.status), resp.read(8 * 1024 * 1024),
                        {str(k): str(v) for k, v in resp.headers.items()})
        except urllib.error.HTTPError as exc:
            # Every response header and the error body go back, so the hard stop sees
            # Retry-After and a WAF challenge (cf-mitigated / challenge page) on a refusal.
            hdrs = ({str(k): str(v) for k, v in exc.headers.items()}
                    if exc.headers is not None else {})
            try:
                err_body = exc.read(64 * 1024)
            except OSError:
                err_body = b""
            return int(exc.code), err_body, hdrs
        except (urllib.error.URLError, TimeoutError, OSError):
            return 0, b"", {}
    return get


_CONTACT_RE = re.compile(r"[^\s@<>]+@[^\s@<>]+\.[A-Za-z]{2,}|https?://\S+\.\S+")


def ua_has_contact(ua: str) -> bool:
    """Does the declared User-Agent carry contact details (an email or a URL)? Never prints it."""
    return bool(_CONTACT_RE.search(ua or ""))


def _call(get: Getter, url: str) -> tuple[int, bytes, dict[str, str]]:
    out = get(url, {})
    status, body = int(out[0]), out[1]
    headers = out[2] if len(out) > 2 and isinstance(out[2], dict) else {}
    return status, body, {str(k).lower(): str(v) for k, v in headers.items()}


def record_block(record: dict[str, Any], register: Path) -> None:
    """Place the person-released hold in the desk's existing blocked-sources register."""
    _hs.place_hold(record, register, source_key=REGISTER_KEY, region="US")


# ------------------------------------------------------------------------------- instruments

def us_issuers() -> dict[str, str]:
    """MT5 share CFD -> US ticker, from the one hand table the desk already keeps."""
    try:
        from research.alpha_capture import TICKERS
    except ImportError:                                     # pragma: no cover - layout
        from alpha_capture import TICKERS  # type: ignore[no-redef,import-not-found]
    return dict(TICKERS)


def cik_map(raw: bytes) -> dict[str, int]:
    """`company_tickers.json` -> {TICKER: cik}. Class shares keep the SEC's dash (BRK-B)."""
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {}
    out: dict[str, int] = {}
    rows = doc.values() if isinstance(doc, dict) else doc if isinstance(doc, list) else []
    for r in rows:
        if isinstance(r, dict) and r.get("ticker") and r.get("cik_str") is not None:
            try:
                out[str(r["ticker"]).upper()] = int(r["cik_str"])
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


def filing_index(raw: bytes) -> list[dict[str, Any]]:
    """The issuer's recent Form 4 filings from the submissions JSON, newest first."""
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return []
    rec = ((doc or {}).get("filings") or {}).get("recent") or {}
    forms = rec.get("form") or []
    out: list[dict[str, Any]] = []
    for i, form in enumerate(forms):
        if str(form) not in FORMS:
            continue
        try:
            acc = str(rec["accessionNumber"][i])
            wall = str(rec["acceptanceDateTime"][i])
            doc_name = str(rec["primaryDocument"][i])
        except (KeyError, IndexError, TypeError):
            continue
        at = accepted_utc(wall)
        if at is None:
            continue
        out.append({"form": str(form), "accession": acc, "filed_at": at.isoformat(),
                    "document": doc_name.split("/")[-1]})
    out.sort(key=lambda r: r["filed_at"], reverse=True)
    return out


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

def fetch_pass(get: Getter, state: dict[str, Any], deadline: float, *, now: datetime,
               issuers: dict[str, str], ua: str = ""
               ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """New transactions this pass, and what the pass did. `state` is updated in place.

    ROBOTS (audit 0b66b08de MF5; principal's scope rule 2026-10-13). Before the first request to
    a host (www.sec.gov, data.sec.gov) its robots.txt is read through the same getter, so under
    the same declared User-Agent, at most once a day (`state["robots"]`), and every URL is judged
    by its exact path against the group naming the desk's product AND the group naming the token
    of the UA actually sent; either disallowing it means it is not fetched (`skip`). An
    unavailable robots.txt means no fetch from the lane this pass (`stop`, re-read next pass); a
    401/403/429 or challenge on robots.txt itself is a person-held hold. The UA is used only for
    its product token and never recorded."""
    rep: dict[str, Any] = {"requests": 0, "errors": Counter(), "issuers_visited": 0,
                           "filings_read": 0, "transactions": 0, "block": None,
                           "ok_responses": 0, "data_responses": 0, "robots": {},
                           "robots_disallowed": 0, "robots_unavailable": False}
    cache: dict[str, Any] = state.setdefault("robots", {})
    sent_token = re.split(r"[/\s]", (ua or "").strip(), maxsplit=1)[0].lower()

    def stopped(status: int, url: str, headers: dict[str, str], body: bytes = b"") -> bool:
        verdict = _hs.refusal(status, headers, body)
        if verdict is None:
            return False
        if (ra := retry_after_s(headers.get("retry-after"), now)) is not None:
            rep["retry_after_s"] = ra                       # recorded; it releases nothing
        if url.endswith("/robots.txt") and verdict == _hs.VERDICT_HARD_STOP:
            verdict = _hs.VERDICT_ROBOTS_HOLD
        rep["block"] = _hs.hold_record(verdict, status, url, now)
        return True

    def robots_gate(url: str) -> str:
        """"ok", "skip" (robots disallows this URL) or "stop" (hold placed, or robots.txt
        unavailable: nothing more from the lane this pass)."""
        hit = _hs.robots_cached(cache, url, now)
        if hit is None:
            ru = _hs.robots_url(url)
            status, raw, hdr = _call(get, ru)
            rep["requests"] += 1
            if stopped(status, ru, hdr, raw):
                return "stop"
            _hs.robots_remember(cache, url, status, raw, now)
            hit = (status, raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw))
        verdicts = [_hs.robots_verdict(url, hit[0], hit[1])]
        if sent_token and sent_token != _hs.DESK_UA_PRODUCT:
            verdicts.append(_hs.robots_verdict(url, hit[0], hit[1], product=sent_token))
        worst = next((v for v in verdicts if not v["allowed"]), verdicts[0])
        rep["robots"][urllib.parse.urlsplit(url).netloc] = worst["state"]
        if worst["state"] == "UNAVAILABLE":
            rep["robots_unavailable"] = True
            return "stop"
        if not worst["allowed"]:
            rep["robots_disallowed"] += 1
            return "skip"
        return "ok"

    ciks: dict[str, int] = {k: int(v) for k, v in (state.get("ciks") or {}).items()}
    if not ciks:
        if robots_gate(TICKER_MAP_URL) != "ok":
            rep["errors"] = dict(rep["errors"])
            return [], rep
        status, raw, hdr = _call(get, TICKER_MAP_URL)
        rep["requests"] += 1
        rep["ok_responses"] += int(status == 200)
        if stopped(status, TICKER_MAP_URL, hdr, raw):
            rep["errors"] = dict(rep["errors"])
            return [], rep
        if status != 200:
            rep["errors"][f"ticker map HTTP {status}"] += 1
            return [], rep
        ciks = cik_map(raw)
        state["ciks"] = ciks
    seen: set[str] = set(state.get("seen") or [])
    backfilled: set[str] = set(state.get("backfilled") or [])
    order = sorted(issuers)
    start = int(state.get("cursor") or 0) % max(1, len(order))
    order = order[start:] + order[:start]
    floor = now - timedelta(days=LOOKBACK_DAYS)
    fresh: list[dict[str, Any]] = []
    visited = 0
    no_cik: list[str] = []
    for sym in order[:ISSUERS_PER_PASS]:
        if time.monotonic() >= deadline:
            break
        ticker = issuers[sym].upper()
        cik = ciks.get(ticker) or ciks.get(ticker.replace("-", "."))
        visited += 1
        if not cik:
            no_cik.append(sym)
            backfilled.add(sym)          # nothing to backfill: the SEC lists no such filer
            continue
        gate = robots_gate(SUBMISSIONS_URL.format(cik=cik))
        if gate == "stop":
            visited -= 1                 # the held issuer is first in line after the hold
            break
        if gate == "skip":
            continue                     # robots disallows this issuer's index: not fetched
        status, raw, hdr = _call(get, SUBMISSIONS_URL.format(cik=cik))
        rep["requests"] += 1
        rep["ok_responses"] += int(status == 200)
        rep["data_responses"] += int(status == 200)
        if stopped(status, SUBMISSIONS_URL.format(cik=cik), hdr, raw):
            visited -= 1                 # the refused issuer is first in line after the backoff
            break
        if status != 200:
            rep["errors"][f"submissions HTTP {status}"] += 1
            continue
        index = [f for f in filing_index(raw)
                 if f["accession"] not in seen
                 and (_parse_time(f["filed_at"]) or now) >= floor]
        done_all = True
        for f in index[:DOCS_PER_ISSUER]:
            if time.monotonic() >= deadline:
                done_all = False
                break
            acc = f["accession"]
            url = ARCHIVE_URL.format(cik=cik, acc=acc.replace("-", ""), doc=f["document"])
            gate = robots_gate(url)
            if gate != "ok":
                done_all = False         # unread: it stays owed, never frozen around
                if gate == "stop":
                    break
                continue
            status, body, hdr = _call(get, url)
            rep["requests"] += 1
            rep["ok_responses"] += int(status == 200)
            rep["data_responses"] += int(status == 200)
            if stopped(status, url, hdr, body):
                done_all = False
                break
            if status != 200:
                rep["errors"][f"document HTTP {status}"] += 1
                done_all = False
                continue
            seen.add(acc)
            rep["filings_read"] += 1
            for txn in parse_form4(body):
                txn.update({"symbol": sym, "cik": cik, "accession": acc,
                            "filed_at": f["filed_at"], "form": f["form"],
                            "first_seen_at": now.isoformat(timespec="seconds")})
                fresh.append(txn)
        # THE UNREAD FLOOR (audit 0b66b08de, MF4). EDGAR is read newest first, DOCS_PER_ISSUER a
        # pass, so a post-backfill burst larger than that leaves its OLDER filings unread while
        # its newer ones are in hand. A cluster is exact as of t only when every filing accepted
        # by t is held, so `score` freezes this issuer only strictly before the acceptance time
        # of the oldest filing still unread; the rest freeze on the pass that reads it.
        unread = [_parse_time(f["filed_at"]) or floor for f in index if f["accession"] not in seen]
        floors = state.setdefault("unread_floor", {})
        if unread:
            floors[sym] = min(unread).isoformat(timespec="seconds")
        else:
            floors.pop(sym, None)
        if rep["block"] is not None or rep["robots_unavailable"]:
            visited -= 1                 # the hard stop: no further SEC request this pass
            break
        if done_all and len(index) <= DOCS_PER_ISSUER:
            backfilled.add(sym)
    state["cursor"] = (start + visited) % max(1, len(order))
    state["seen"] = sorted(seen)
    state["backfilled"] = sorted(backfilled)
    rep["issuers_visited"] = visited
    rep["no_cik"] = no_cik
    rep["transactions"] = len(fresh)
    rep["errors"] = dict(rep["errors"])
    return fresh, rep


# ------------------------------------------------------------------------------- scoring

def txn_key(r: dict[str, Any]) -> str:
    """One transaction's identity in the append-only store (a filing may hold several)."""
    return "|".join(str(r.get(k) or "") for k in ("accession", "insider", "txn_date", "code",
                                                    "shares", "price"))


def to_txns(rows: list[dict[str, Any]]) -> list[Any]:
    return [t for _k, t in _keyed_txns(rows)]


def _keyed_txns(rows: list[dict[str, Any]]) -> list[tuple[str, Any]]:
    from libs.research.form4 import Form4Txn
    out: list[tuple[str, Any]] = []
    for r in rows:
        filed = _parse_time(r.get("filed_at"))
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

    APPEND-ONLY, AS OF EACH ACCEPTANCE (audit 2026-10-14, MUST-FIX 1). `form4.clusters` over the
    full history lets a filing accepted LATER join an earlier window and move the cluster's
    `knowable_at` to its own acceptance -- buyers A and B public on 05-06, C filed on 05-20 with a
    transaction date inside the window, and the 05-06 cluster vanished from the 05-06..05-09
    breadth points. Here the transactions are replayed in acceptance order; at each instant t
    only filings accepted by t exist, and a window becomes a cluster the moment it first holds
    `MIN_BUYERS` distinct buyers among transactions no frozen cluster already holds. It is then
    frozen: its rows, buyers, score (baseline strictly before t) and `knowable_at = t` never
    change. A later filing can start a NEW cluster; it never rewrites one.

    `unread_floor` maps an issuer to the acceptance time of its oldest filing still UNREAD: the
    replay for that issuer stops there, because from that instant on the store would be missing
    a filing that was public (audit 0b66b08de, MF4).
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
                break                    # an older filing is unread: not exact from here on
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
                    rec = {"symbol": issuer, **c.to_dict(), "rows": sorted(k for k, _ in win)}
                    if (issuer, rec["knowable_at"]) not in held:
                        out.append(rec)
                    break
    out.sort(key=lambda r: (r["knowable_at"], r["symbol"]))
    return out


def score(rows: list[dict[str, Any]], frozen: list[dict[str, Any]] | None = None,
          backfilled: set[str] | None = None,
          unread_floor: Mapping[str, datetime] | None = None
          ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """(every frozen cluster -- prior then new --, the new ones, the census).

    FROZEN ONLY ONCE THE ISSUER IS BACKFILLED (audit 2026-10-14, MF2). EDGAR is read newest
    first, so before an issuer's backfill completes its older filings are missing: a cluster
    frozen then could lack a buyer, and its baseline (the issuer's earlier buying) is short --
    200 of 200 probe stores differed from a full replay. With `backfilled` given, only those
    issuers' transactions are frozen; the rest are scored EPHEMERALLY (counted in the census as
    `clusters_ephemeral`, never stored, never in the breadth series or the event store), and
    freeze for the first time on the pass their backfill completes -- with every filing in hand,
    so the store equals a full replay whatever the fetch order. `backfilled=None` freezes every
    issuer (a store built from a complete history). `unread_floor` (issuer -> acceptance time
    of its oldest filing still unread) stops a backfilled issuer's freezing there: see
    `freeze_clusters`.
    """
    from libs.research import form4
    prior = [c for c in (frozen or []) if c.get("rows")]
    ready = rows if backfilled is None else [r for r in rows
                                             if str(r.get("symbol")) in backfilled]
    new = freeze_clusters(ready, prior, unread_floor)
    allc = sorted(prior + new, key=lambda r: (r["knowable_at"], r["symbol"]))
    census = form4.census(to_txns(rows))
    if backfilled is not None:
        rest = [r for r in rows if str(r.get("symbol")) not in backfilled]
        census["clusters_ephemeral"] = len(freeze_clusters(rest, []))
    return allc, new, census


def breadth_points(clusters: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    """Per complete UTC day: trailing-30-day summed cluster score and count, known at day end."""
    stamped = sorted((t, float(c.get("score") or 0.0)) for c in clusters
                     if (t := _parse_time(c.get("knowable_at"))) is not None)
    if not stamped:
        return []
    first = stamped[0][0].date()
    last = (now - timedelta(days=1)).date()
    out: list[dict[str, Any]] = []
    d = first
    lo = 0
    while d <= last:
        end = datetime(d.year, d.month, d.day, tzinfo=UTC) + timedelta(days=1)
        start = end - timedelta(days=BREADTH_WINDOW_D)
        while lo < len(stamped) and stamped[lo][0] < start:
            lo += 1
        window = [s for t, s in stamped[lo:] if t < end]
        out.append({"event_time": d.isoformat(), "available_time": end.isoformat(),
                    "cluster_score_30d": round(sum(window), 6),
                    "n_clusters_30d": len(window)})
        d += timedelta(days=1)
    return out


def write_breadth(points: list[dict[str, Any]], root: Path | None = None) -> Path | None:
    if not points:
        return None
    import csv
    base = root or SERIES_DIR
    base.mkdir(parents=True, exist_ok=True)
    target = base / f"{BREADTH_SERIES}.csv"
    head = ["event_time", "available_time", "source_id", "vintage_id", "cluster_score_30d",
            "n_clusters_30d"]
    tmp = target.with_name(f"{target.name}.tmp{os.getpid()}")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=head)
        w.writeheader()
        for p in points:
            w.writerow({**p, "source_id": BREADTH_SERIES, "vintage_id": p["available_time"]})
    os.replace(tmp, target)
    return target


# ------------------------------------------------------------------------------- cells

#: THE ISSUER SET IS TODAY'S, NOT A POINT-IN-TIME ONE (audit SHOULD-FIX). The breadth score sums
#: clusters over the share CFDs Fusion lists NOW (`alpha_capture.TICKERS`); the desk holds no
#: point-in-time membership list, so names delisted or dropped before today are absent from the
#: past and names listed later are present in it. Carried on every breadth cell and the report.
BREADTH_CAVEATS = (
    "SURVIVORSHIP: the issuer set is today's Fusion share-CFD list (alpha_capture.TICKERS), not "
    "a point-in-time membership list -- none exists on this desk; issuers that delisted or left "
    "the list before today are missing from the history, so the past breadth level is built "
    "from survivors",
)


def breadth_cells(points: int, backfill_complete: bool) -> tuple[list[dict[str, Any]], str]:
    if not backfill_complete:
        return [], "BREADTH_BACKFILLING: not every issuer has been read back to the lookback"
    if points < MIN_POINTS:
        return [], f"SERIES_ACCRUING: {points} of {MIN_POINTS} days"
    params = {"source": BREADTH_SERIES, "signal": "cluster_score_30d", "transform": "level_z",
              "threshold": 1.0, "side_when_high": 1, "lag_hours": 24, "timeframe": "H1"}
    return [{"symbol": s, "symbols": [s], "kind": "hypothesis",
             "family": "exogenous_conditioner", "params": dict(params),
             "title": f"Form 4 aggregate insider buying (30d cluster score) -> {s} long"[:120],
             "mechanism": ("aggregate open-market insider purchases at an extreme of their own "
                           "history lead the index: insiders buy their own stock when the market "
                           "is cheap relative to what they know (Lakonishok & Lee 2001)"),
             "falsifier": (f"{s} H1 returns while the 30-day insider cluster score sits above "
                           "+1 sd of its own history are no better than unconditional, net of "
                           "the fill-hour spread"),
             "caveats": list(BREADTH_CAVEATS),
             "lane": "breadth"} for s in BREADTH_TARGETS], "OK"


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
                      "params": {"symbol": sym, "hold_days": EVENT_HOLD_DAYS, "timeframe": "H1"},
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


def _identity(c: dict[str, Any]) -> str:
    return json.dumps({"symbol": c["symbol"], "family": c["family"], "params": c["params"]},
                      sort_keys=True)


def donate_new(cells: list[dict[str, Any]], state: dict[str, Any], *, dry_run: bool
               ) -> dict[str, Any]:
    """Donate the cells never donated before; one trial each at the docket."""
    done = set(state.get("donated") or [])
    new = [c for c in cells if _identity(c) not in done]
    out: dict[str, Any] = {"new": len(new), "already": len(cells) - len(new)}
    if not new or dry_run:
        return out
    try:
        from research import proposer_common as pc
    except ImportError:                                     # pragma: no cover - layout
        import proposer_common as pc  # type: ignore[no-redef,import-not-found]
    path = pc.donate(SOURCE, new, tests_run=len(new))
    out["path"] = str(path) if path else None
    out["donation"] = {k: pc.LAST_DONATION.get(k) for k in
                       ("donated", "refused_unstamped", "refused_wrong_lane")}
    if path:
        state["donated"] = sorted(done | {_identity(c) for c in new})
    return out


# ------------------------------------------------------------------------------- the pass

def run(*, get: Getter | None = None, budget_s: float = 300.0, now: datetime | None = None,
        state_dir: Path | None = None, series_root: Path | None = None,
        dry_run: bool = False, register: Path | None = None) -> dict[str, Any]:
    now = now or _now()
    sd = state_dir or STATE_DIR
    state_path, txn_path, cl_path = sd / "state.json", sd / "transactions.jsonl", \
        sd / "clusters.jsonl"
    state: dict[str, Any] = _read_json(state_path, {})
    issuers = us_issuers()
    report: dict[str, Any] = {"generated_utc": now.isoformat(timespec="seconds"),
                              "issuers": len(issuers), "user_agent_configured": False}
    ua = os.environ.get(UA_ENV, "").strip()
    fetch: dict[str, Any]
    prior = state.get("block") if isinstance(state.get("block"), dict) else None
    reg_path = register or BLOCKED_REGISTER
    held = _hs.active_hold(reg_path, [_hs.host_key(h) for h in SEC_HOSTS], prior)
    if prior is not None and held is None:
        state.pop("block", None)         # a person released it: this copy is spent
    if held is not None:
        # HELD FOR A PERSON. Nothing is requested, however long ago the refusal was; the data
        # already held is still scored below.
        fetch = {"status": _hs.pass_status(held), "requests": 0, "skipped": True,
                 "why": (f"{held.get('verdict')} HTTP {held.get('status')} from "
                         f"{held.get('host')}: held until a person releases {held.get('key')}"),
                 "block": held}
    elif get is None and not ua:
        fetch = {"status": "UNCONFIGURED",
                 "why": f"no {UA_ENV}: the SEC's fair-access policy requires a declared "
                        "User-Agent, so nothing was fetched (a configuration gap, not a "
                        "closed source)"}
    elif get is None and not ua_has_contact(ua):
        # The value is never echoed: only that it lacks a contact.
        fetch = {"status": "UNCONFIGURED",
                 "why": f"{UA_ENV} is set but names no contact (an email address or a URL); "
                        "the SEC's fair-access policy asks for one, so nothing was fetched"}
    else:
        report["user_agent_configured"] = bool(ua) or get is not None
        getter = get or urllib_getter(ua)
        fresh, rep = fetch_pass(getter, state, time.monotonic() + budget_s * 0.8, now=now,
                                issuers=issuers, ua=ua)
        # MEASURED ONLY ON AN ANSWER (audit MUST-FIX 2). A ticker-map 500, a dead network
        # (status 0) or 5xx on every request is a pass that learned nothing; it must not read
        # OK/MEASURED. At least one 200 is required.
        # ...and the 200 must be ISSUER DATA (a submissions index or a filing): a ticker-map 200
        # with every submissions request failing is a pass that learned nothing.
        fetch = {**rep, "status": ("FETCHED" if rep["data_responses"] else
                                   "FAILED" if rep["requests"] else "IDLE")}
        if rep["block"] is not None:
            state["block"] = rep["block"]
            fetch["status"] = _hs.pass_status(rep["block"])
            try:                         # the lane's own copy above holds even if this fails
                record_block(rep["block"], reg_path)
            except OSError as exc:
                fetch["persist_error"] = f"{type(exc).__name__}: {exc}"[:200]
        elif rep["robots_unavailable"] and not rep["data_responses"]:
            fetch["status"] = "ROBOTS_UNAVAILABLE"
        elif rep["robots_disallowed"] and not rep["data_responses"]:
            fetch["status"] = "ROBOTS_DISALLOWED"     # not a hold: robots is re-read daily
            with contextlib.suppress(OSError):
                _hs.note_robots({"robots_url": "sec.gov robots.txt", "states": rep["robots"]},
                                reg_path, source_key=REGISTER_KEY, region="US")
        if fresh:
            sd.mkdir(parents=True, exist_ok=True)
            with txn_path.open("a", encoding="utf-8") as fh:
                for r in fresh:
                    fh.write(json.dumps(r, sort_keys=True) + "\n")
    report["fetch"] = fetch
    rows = _jsonl(txn_path)
    stored = _jsonl(cl_path)
    floors = {str(k): t for k, v in (state.get("unread_floor") or {}).items()
              if (t := _parse_time(v)) is not None}
    clusters, new_clusters, census = score(rows, stored,
                                           set(state.get("backfilled") or []), floors)
    census["issuers_held_unread"] = len(floors)
    sd.mkdir(parents=True, exist_ok=True)
    if any(not c.get("rows") for c in stored):
        # A store written before freezing carried no row identities, so it cannot be honoured
        # as frozen; it is rebuilt once, as of each acceptance, and appended from then on.
        tmp = cl_path.with_name(f"{cl_path.name}.tmp{os.getpid()}")
        tmp.write_text("".join(json.dumps(c, sort_keys=True) + "\n" for c in clusters),
                       encoding="utf-8")
        os.replace(tmp, cl_path)
    elif new_clusters:
        with cl_path.open("a", encoding="utf-8") as fh:      # APPEND-ONLY
            for c in new_clusters:
                fh.write(json.dumps(c, sort_keys=True) + "\n")
    pts = breadth_points(clusters, now)
    written = write_breadth(pts, series_root)
    backfilled = set(state.get("backfilled") or [])
    complete = bool(issuers) and set(issuers) <= backfilled
    b_cells, b_state = breadth_cells(len(pts), complete)
    e_cells, accruing = event_cells(clusters)
    donated = donate_new(b_cells + e_cells, state, dry_run=dry_run)
    _write_json(state_path, state)
    report.update({
        "transactions": len(rows), "census": census, "clusters": len(clusters),
        "clusters_new": len(new_clusters),
        "clusters_by_symbol": dict(Counter(c["symbol"] for c in clusters).most_common()),
        "backfill": {"issuers_backfilled": len(backfilled & set(issuers)),
                     "of": len(issuers), "complete": complete},
        "breadth": {"series": BREADTH_SERIES, "points": len(pts),
                    "written": str(written) if written else None, "state": b_state,
                    "cells": len(b_cells), "targets": list(BREADTH_TARGETS),
                    "caveats": list(BREADTH_CAVEATS)},
        "event": {"family": EVENT_FAMILY, "cells": len(e_cells), "min_events": MIN_EVENTS,
                  "accruing": accruing},
        "donated": donated,
        "new_data": "MEASURED" if fetch.get("status") == "FETCHED" else UNMEASURED,
        "status": "OK" if fetch.get("status") == "FETCHED" else UNMEASURED})
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--dry-run", action="store_true", help="fetch and score, donate nothing")
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, dry_run=a.dry_run)
    _write_json(REPORT, doc)
    f = doc.get("fetch") or {}
    print(f"form4_lane: {doc['status']} -- fetch {f.get('status')}, transactions "
          f"{doc['transactions']}, clusters {doc['clusters']}, breadth "
          f"{doc['breadth']['state']}, event cells {doc['event']['cells']}, donated "
          f"{doc['donated'].get('new')}")
    return 0


if __name__ == "__main__":                                              # pragma: no cover
    raise SystemExit(main())
