"""INFORMED CAPITAL -- what insiders, activists, institutions, legislators and prediction markets
disclosed, parsed deterministically and dated at the instant the public could first read it.

WHAT THIS MODULE IS. The pure half of `desks/mt5/research/informed_capital.py`: parsers for the
public records (no network here), the one point-in-time door, and the observation builder the
organ's tracker and the `informed_flow_drift` family BOTH read -- so the gauntlet replays exactly
the events the tracker measured, never a re-derivation of them.

    SEC Form 3/4/5         ownership XML inside the complete-submission .txt (role, code, shares,
                           price, 10b5-1 flag) and the quarterly Insider Transactions Data Sets
                           (SUBMISSION / REPORTINGOWNER / NONDERIV_TRANS .tsv in a ZIP)
    SC 13D / SC 13G        rows of the EDGAR daily form index, dated by the filing header
    13F-HR                 the information table XML, diffed against the filer's previous one
    House PTRs             the Clerk's e-filed PDF text (the yearly index is
                           `libs.data.free_stack.parse_house_fd_index`, reused, not copied)
    Senate PTRs            the eFD report table HTML
    Kalshi / Polymarket    public market lists and daily price histories

THE TWO CLOCKS, AND WHY ONLY ONE OF THEM MAY EVER REACH A CELL.
  OBSERVABLE  the SEC acceptance datetime (America/New_York in the header, converted to UTC
              here). A record carrying only a DATE is placed at the next UTC day 04:00 -- after
              EDGAR's 22:00 ET close in both seasons -- plus a posting lag for the congressional
              sites, whose index date can precede the document being reachable.
  ORACLE      the transaction date's close. It is what a study dated on the trade would read, and
              it is a document that did not exist yet. It is computed so the DECAY (oracle minus
              observable) can be published per source; it feeds no cell, no family and no axis.

TRANSACTION CODES ARE NOT INTERCHANGEABLE (`libs.research.form4.NOT_A_DECISION`, reused): only
`P` (open-market purchase) and `S` (open-market sale) carry a direction, and a trade flagged as a
Rule 10b5-1 plan was scheduled months earlier, so it is counted and set aside, never signed.

TRANSMISSION TO THE MT5 UNIVERSE (the universe law in CLAUDE.md):
  direct     a filing ABOUT an issuer the desk quotes as a share CFD -> that CFD. Share CFDs may
             mint only in the news lane, and `informed_flow_drift` is registered there.
  aggregate  the day's insider (or congressional) buy share across EVERY issuer, against its own
             trailing baseline -> the US index CFDs. This is the main target: it needs no single
             name to be quoted at all.
  odds       a macro prediction-market contract's daily probability move -> the FX, index, gold,
             oil and rates legs its category names.

No fetch, no capital, no sizing. Stdlib + numpy only.
"""
from __future__ import annotations

import csv
import hashlib
import io
import itertools
import json
import math
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any

from libs.research import analyst_views as av
from libs.research import form4

UNMEASURED = "UNMEASURED"

#: Families of record, and the clock precision each one carries.
FAMILIES: tuple[str, ...] = ("form4", "form345_ds", "sc13d", "sc13g", "13f", "house_ptr",
                             "senate_ptr", "kalshi", "polymarket")

#: Extra days a congressional index date may precede the document being reachable. Not measured
#: on this box (the sites were unreachable where this was built); conservative by one day.
POSTING_LAG_D: dict[str, int] = {"house_ptr": 1, "senate_ptr": 1}

#: The index CFDs an aggregate of US insider or congressional breadth transmits into.
AGG_TARGETS: tuple[str, ...] = ("US500", "NAS100", "US30", "US2000")

#: A day's buy share must stand this many trailing standard deviations from its own baseline.
AGG_Z = 1.5
AGG_BASELINE_DAYS = 60
AGG_MIN_BASELINE = 20
AGG_MIN_ISSUERS = 5

#: Role classes, most senior first. A filer holding several roles is classed by the senior one.
ROLE_ORDER: tuple[str, ...] = ("ceo", "cfo", "coo", "president", "chair", "officer", "director",
                               "10pct", "other")
EXEC_ROLES = frozenset({"ceo", "cfo", "coo", "president", "chair", "officer"})

#: Prediction-market categories -> the MT5 legs a probability move about them transmits into.
ODDS_TARGETS: dict[str, tuple[str, ...]] = {
    "fed": ("USDX", "EURUSD", "USDJPY", "XAUUSD", "US500", "NAS100", "UST10Y"),
    "inflation": ("USDX", "EURUSD", "XAUUSD", "US500", "UST10Y"),
    "jobs": ("USDX", "USDJPY", "US500", "US2000", "XAUUSD"),
    "growth": ("US500", "NAS100", "US2000", "USDJPY", "XAUUSD", "XTIUSD"),
    "oil": ("XTIUSD", "XBRUSD", "USDCAD"),
    "gold": ("XAUUSD", "XAGUSD"),
    "ecb": ("EURUSD", "EURGBP", "GER40"),
    "boe": ("GBPUSD", "EURGBP", "UK100"),
    "boj": ("USDJPY", "JPN225"),
    "trade": ("USDCNH", "USDMXN", "USDCAD", "US500", "EURUSD"),
    "fiscal": ("US500", "XAUUSD", "USDX", "UST10Y"),
}
#: Ordered: the first category whose words appear in the question wins.
ODDS_WORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ecb", ("ecb", "european central bank")),
    ("boe", ("bank of england", "boe ")),
    ("boj", ("bank of japan", "boj")),
    ("fed", ("fed ", "fed's", "fomc", "federal funds", "fed funds", "interest rate",
             "rate cut", "rate hike", "powell")),
    ("inflation", ("cpi", "inflation", "pce")),
    ("jobs", ("payroll", "unemployment", "jobs report", "nonfarm", "jobless")),
    ("growth", ("gdp", "recession")),
    ("oil", ("oil", "crude", "wti", "brent", "opec")),
    ("gold", ("gold price", "price of gold", "gold above", "gold below")),
    ("trade", ("tariff", "trade deal", "trade war")),
    ("fiscal", ("government shutdown", "debt ceiling", "shutdown")),
)
_UP_WORDS = ("hike", "raise", "increase", "above", "higher", "more than", "over ", "exceed",
             "at least", "greater than", "rise")
_DOWN_WORDS = ("cut", "lower", "decrease", "below", "less than", "under ", "fewer", "fall",
               "reduce")
#: A daily probability move smaller than this is noise, not an event.
ODDS_MOVE = 0.05


# ------------------------------------------------------------------------------ time
def _second_sunday(year: int, month: int) -> date:
    d = date(year, month, 1)
    first = d + timedelta(days=(6 - d.weekday()) % 7)
    return first + timedelta(days=7)


def _first_sunday(year: int, month: int) -> date:
    d = date(year, month, 1)
    return d + timedelta(days=(6 - d.weekday()) % 7)


def eastern_to_utc(local: datetime) -> datetime:
    """America/New_York wall time -> UTC by the US rule since 2007, with no tz database needed
    (the trading box's Windows Python may carry none). Ambiguous fall-back hours resolve to the
    LATER instant, which can only move an event later -- the conservative direction."""
    y = local.year
    start = datetime.combine(_second_sunday(y, 3), datetime.min.time()).replace(hour=2)
    end = datetime.combine(_first_sunday(y, 11), datetime.min.time()).replace(hour=1)
    naive = local.replace(tzinfo=None)
    offset = 4 if start <= naive < end else 5
    return (naive + timedelta(hours=offset)).replace(tzinfo=UTC)


def utc_to_eastern_date(when: datetime) -> date:
    """The America/New_York calendar date of a UTC instant (the EDGAR filing day)."""
    naive = when.astimezone(UTC).replace(tzinfo=None)
    for off in (4, 5):
        local = naive - timedelta(hours=off)
        if eastern_to_utc(local).replace(tzinfo=None) == naive:
            return local.date()
    return (naive - timedelta(hours=5)).date()


def parse_acceptance(raw: Any) -> datetime | None:
    """`20261102163015` (EDGAR header, Eastern) -> UTC. None when absent or malformed."""
    s = re.sub(r"\D", "", str(raw or ""))[:14]
    if len(s) != 14:
        return None
    try:
        return eastern_to_utc(datetime.strptime(s, "%Y%m%d%H%M%S").replace(tzinfo=UTC))
    except ValueError:
        return None


def parse_day(raw: Any) -> str | None:
    """Any of 2026-11-02, 20261102, 11/02/2026, 02-NOV-2026 -> ISO date. None otherwise."""
    s = str(raw or "").strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%m/%d/%Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(s[:11].strip(), fmt).replace(tzinfo=UTC).date().isoformat()
        except ValueError:
            continue
    return None


def knowable_at(row: Mapping[str, Any]) -> tuple[datetime | None, str]:
    """THE ONE POINT-IN-TIME DOOR. (instant, precision) -- never a transaction date."""
    acc = av.parse_time(row.get("accepted_at"))
    if acc is not None:
        return acc, "datetime"
    obs = av.parse_time(row.get("observed_at"))
    if obs is not None:
        return obs, "observed"
    filed = parse_day(row.get("filed_date"))
    if filed is None:
        return None, UNMEASURED
    lag = POSTING_LAG_D.get(str(row.get("family") or ""), 0)
    d = date.fromisoformat(filed) + timedelta(days=1 + lag)
    return datetime(d.year, d.month, d.day, 4, 0, tzinfo=UTC), "date"


def filing_day(row: Mapping[str, Any]) -> date | None:
    """The US filing day an event belongs to: the Eastern date of its acceptance, else the
    record's own filing date. Aggregates are counted per filing day, never per trade day."""
    acc = av.parse_time(row.get("accepted_at"))
    if acc is not None:
        return utc_to_eastern_date(acc)
    d = parse_day(row.get("filed_date"))
    return date.fromisoformat(d) if d else None


def oracle_at(row: Mapping[str, Any]) -> datetime | None:
    """THE ORACLE CLOCK: the transaction date's US close (21:00 UTC). Research only."""
    d = parse_day(row.get("txn_date"))
    if d is None:
        return None
    x = date.fromisoformat(d)
    return datetime(x.year, x.month, x.day, 21, 0, tzinfo=UTC)


# ------------------------------------------------------------------------------ roles
def role_class(*, title: str = "", is_director: bool = False, is_officer: bool = False,
               is_ten_pct: bool = False, relationship: str = "") -> str:
    """CEO/CFO/COO/PRESIDENT/CHAIR/OFFICER/DIRECTOR/10PCT from a filing's relationship block."""
    t = f" {title or ''} {relationship or ''} ".lower()
    rel = (relationship or "").lower()
    if re.search(r"chief executive|\bceo\b", t):
        return "ceo"
    if re.search(r"chief financial|\bcfo\b|principal financial|treasurer", t):
        return "cfo"
    if re.search(r"chief operating|\bcoo\b", t):
        return "coo"
    if re.search(r"\bpresident\b", t) and "vice president" not in t:
        return "president"
    if re.search(r"\bchair", t):
        return "chair"
    if is_officer or "officer" in rel:
        return "officer"
    if is_director or "director" in rel:
        return "director"
    if is_ten_pct or "tenpercent" in rel.replace(" ", "").replace("%", "percent") or "10%" in rel:
        return "10pct"
    return "other"


def senior(roles: Iterable[str]) -> str:
    rs = list(roles)
    return min(rs, key=ROLE_ORDER.index) if rs else "other"


def role_group(role: str) -> str:
    return "exec" if role in EXEC_ROLES else role


# ------------------------------------------------------------------------------ EDGAR index
_IDX_ROW = re.compile(r"^(?P<form>\S.*?)\s{2,}(?P<company>\S.*?)\s{2,}(?P<cik>\d{1,10})\s+"
                      r"(?P<date>\d{8}|\d{4}-\d{2}-\d{2})\s+(?P<file>edgar/\S+)\s*$")


def parse_form_idx(text: str) -> list[dict[str, str]]:
    """EDGAR daily `form.YYYYMMDD.idx` -> one row per (form, entity, filing). A 13D appears once
    per entity (subject and filer), so callers group by `accession`."""
    out: list[dict[str, str]] = []
    for line in (text or "").splitlines():
        m = _IDX_ROW.match(line.rstrip())
        if not m:
            continue
        fname = m.group("file")
        acc = fname.rsplit("/", 1)[-1].removesuffix(".txt")
        out.append({"form": m.group("form").strip().upper(), "company": m.group("company").strip(),
                    "cik": str(int(m.group("cik"))), "date": parse_day(m.group("date")) or "",
                    "file": fname, "accession": acc})
    return out


def is_13d(form: str) -> bool:
    return form in ("SC 13D", "SCHEDULE 13D")


def is_13g(form: str) -> bool:
    return form in ("SC 13G", "SCHEDULE 13G")


def parse_header(text: str) -> dict[str, Any]:
    """An EDGAR SEC-HEADER (`.txt` or `.hdr.sgml`): acceptance instant, form, subject and filer
    CIKs. Both spellings are read: `ACCEPTANCE-DATETIME:\\t2026...` and `<ACCEPTANCE-DATETIME>2026`.
    """
    t = text or ""
    acc = re.search(r"ACCEPTANCE-DATETIME>?:?\s*(\d{14})", t)
    form = re.search(r"(?:CONFORMED SUBMISSION TYPE:|<TYPE>)\s*([^\r\n<]+)", t)

    def cik_after(label_txt: str, label_sgml: str) -> str:
        m = re.search(label_txt + r".*?CENTRAL INDEX KEY:\s*(\d+)", t, re.S)
        if not m:
            m = re.search(label_sgml + r".*?<CIK>\s*(\d+)", t, re.S)
        return str(int(m.group(1))) if m else ""

    when = parse_acceptance(acc.group(1)) if acc else None
    return {"accepted_at": when.isoformat() if when is not None else None,
            "form": form.group(1).strip().upper() if form else "",
            "subject_cik": cik_after("SUBJECT COMPANY:", "<SUBJECT-COMPANY>"),
            "filer_cik": cik_after("FILED BY:", "<FILED-BY>")}


# ------------------------------------------------------------------------------ XML helpers
def _xml(text: str) -> ET.Element | None:
    """Parse untrusted XML with no DTD and no entities -- refused, never expanded."""
    if not text or re.search(r"<!DOCTYPE|<!ENTITY", text, re.I):
        return None
    try:
        root = ET.fromstring(text)            # DOCTYPE/ENTITY refused above
    except ET.ParseError:
        return None
    for el in root.iter():                       # drop namespaces: 13F tables carry them
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def _txt(el: ET.Element | None, path: str) -> str:
    if el is None:
        return ""
    node = el.find(path)
    if node is None:
        return ""
    v = node.find("value")
    return ((v.text if v is not None else node.text) or "").strip()


def _num(raw: str) -> float | None:
    try:
        x = float(str(raw).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _cik(raw: Any) -> str:
    """CIKs to one spelling: `0001234567` == `1234567`; anything else kept as written."""
    s = str(raw or "").strip()
    return str(int(s)) if s.isdigit() else s


def _flag(raw: str) -> bool:
    return str(raw).strip().lower() in ("1", "true", "y", "yes")


# ------------------------------------------------------------------------------ Form 3/4/5
def parse_ownership(text: str, *, accepted_at: str | None = None, filed_date: str = "",
                    family: str = "form4", accession: str = "") -> list[dict[str, Any]]:
    """One complete-submission `.txt` (or bare ownership XML) -> one event per reporting owner.

    Direction is the sign of open-market purchases minus open-market sales in shares; a filing
    whose discretionary lines net to zero, or that carries only grants, exercises and tax
    withholding, has direction 0 and is kept for the census. Rule 10b5-1 lines are counted under
    `planned_shares` and never signed. A Form 3 carries holdings, not transactions: direction 0.
    """
    hdr = parse_header(text) if "ACCEPTANCE-DATETIME" in (text or "") else {}
    accepted_at = accepted_at or hdr.get("accepted_at")
    m = re.search(r"<ownershipDocument>.*?</ownershipDocument>", text or "", re.S)
    root = _xml(m.group(0)) if m else None
    if root is None:
        return []
    doc_type = (root.findtext("documentType") or "").strip().upper()
    if doc_type.endswith("/A"):
        return []                                # an amendment restates; it is not new news
    issuer = root.find("issuer")
    ticker = (issuer.findtext("issuerTradingSymbol") if issuer is not None else "") or ""
    ticker = ticker.strip().upper().split()[0] if ticker.strip() else ""
    issuer_cik = str(int(issuer.findtext("issuerCik") or 0)) if issuer is not None else ""
    plan_doc = _flag(root.findtext("aff10b5One") or "")
    buys = sells = planned = 0.0
    value = 0.0
    first_txn: str | None = None
    codes: dict[str, int] = defaultdict(int)
    for tx in root.iter("nonDerivativeTransaction"):
        code = (_txt(tx, "transactionCoding/transactionCode") or "").upper()
        codes[code or "?"] += 1
        sh = _num(_txt(tx, "transactionAmounts/transactionShares")) or 0.0
        px = _num(_txt(tx, "transactionAmounts/transactionPricePerShare")) or 0.0
        d = parse_day(_txt(tx, "transactionDate"))
        plan = plan_doc or _flag(_txt(tx, "transactionCoding/aff10b5One"))
        if code not in ("P", "S"):
            continue
        if plan:
            planned += sh
            continue
        if code == "P":
            buys += sh
        else:
            sells += sh
        value += sh * px
        if d and (first_txn is None or d < first_txn):
            first_txn = d
    out: list[dict[str, Any]] = []
    owners: list[ET.Element | None] = list(root.iter("reportingOwner")) or [None]
    for ow in owners:
        rel = ow.find("reportingOwnerRelationship") if ow is not None else None
        role = role_class(title=(rel.findtext("officerTitle") or "") if rel is not None else "",
                          is_director=_flag(rel.findtext("isDirector") or "") if rel is not None
                          else False,
                          is_officer=_flag(rel.findtext("isOfficer") or "") if rel is not None
                          else False,
                          is_ten_pct=_flag(rel.findtext("isTenPercentOwner") or "")
                          if rel is not None else False)
        owner_cik = (ow.findtext("reportingOwnerId/rptOwnerCik") if ow is not None else "") or ""
        net = buys - sells
        out.append(_filing_row(
            family=family, accession=accession, owner=_cik(owner_cik), role=role,
            ticker=ticker, issuer_cik=issuer_cik, doc_type=doc_type or "4",
            direction=(1 if net > 0 else -1 if net < 0 else 0), accepted_at=accepted_at,
            filed_date=filed_date, txn_date=first_txn, value_usd=round(value, 2),
            extra={"buy_shares": buys, "sell_shares": sells, "planned_shares": planned,
                   "codes": dict(codes)}))
    return out


def _filing_row(*, family: str, accession: str, owner: str, role: str, ticker: str,
                issuer_cik: str, doc_type: str, direction: int, accepted_at: str | None,
                filed_date: str, txn_date: str | None, value_usd: float | None,
                extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    eid = f"{accession}|{owner}" if accession else hashlib.sha256(
        json.dumps([family, ticker, owner, txn_date, filed_date]).encode()).hexdigest()[:20]
    return {"event_id": eid, "family": family, "kind": "filing", "doc_type": doc_type,
            "role": role, "ticker": ticker, "issuer_cik": issuer_cik, "owner": owner,
            "direction": int(direction), "accepted_at": accepted_at,
            "filed_date": parse_day(filed_date) or "", "txn_date": txn_date,
            "value_usd": value_usd, "accession": accession, **dict(extra or {})}


def parse_form345_dataset(raw: bytes, *, family: str = "form345_ds"
                          ) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """The SEC's quarterly Insider Transactions Data Set ZIP -> (events, census).

    DATE PRECISION ONLY: SUBMISSION.tsv carries FILING_DATE, not the acceptance instant, so every
    event is placed at the next UTC day 04:00 by `knowable_at`. A datetime-precision event for the
    same accession (from the live .txt path) supersedes it in the store.
    """
    census: dict[str, int] = defaultdict(int)
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        return [], {"bad_zip": 1}
    names = {n.rsplit("/", 1)[-1].upper(): n for n in zf.namelist()}

    def rows(name: str) -> Iterable[dict[str, str]]:
        if name not in names:
            return []
        fh = io.TextIOWrapper(zf.open(names[name]), encoding="utf-8", errors="replace")
        return csv.DictReader(fh, delimiter="\t")

    subs: dict[str, dict[str, str]] = {}
    for r in rows("SUBMISSION.TSV"):
        dt = (r.get("DOCUMENT_TYPE") or "").strip().upper()
        if dt.endswith("/A"):
            census["amendment"] += 1
            continue
        subs[r.get("ACCESSION_NUMBER", "")] = {
            "doc_type": dt, "filed": r.get("FILING_DATE", ""),
            "ticker": (r.get("ISSUERTRADINGSYMBOL") or "").strip().upper(),
            "cik": (r.get("ISSUERCIK") or "").strip().lstrip("0"),
            "plan": r.get("AFF10B5ONE", "")}
    owners: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for r in rows("REPORTINGOWNER.TSV"):
        acc = r.get("ACCESSION_NUMBER", "")
        if acc in subs:
            owners[acc].append((_cik(r.get("RPTOWNERCIK")),
                                role_class(title=r.get("RPTOWNER_TITLE") or "",
                                           relationship=r.get("RPTOWNER_RELATIONSHIP") or "")))
    agg: dict[str, dict[str, Any]] = {}
    for r in rows("NONDERIV_TRANS.TSV"):
        acc = r.get("ACCESSION_NUMBER", "")
        sub = subs.get(acc)
        if sub is None:
            continue
        code = (r.get("TRANS_CODE") or "").strip().upper()
        census[f"code_{code or '?'}"] += 1
        if code not in ("P", "S"):
            continue
        sh = _num(r.get("TRANS_SHARES") or "") or 0.0
        if _flag(sub["plan"]):
            census["planned_10b5_1"] += 1
            continue
        a = agg.setdefault(acc, {"buy": 0.0, "sell": 0.0, "value": 0.0, "first": None})
        a["buy" if code == "P" else "sell"] += sh
        a["value"] += sh * (_num(r.get("TRANS_PRICEPERSHARE") or "") or 0.0)
        d = parse_day(r.get("TRANS_DATE"))
        if d and (a["first"] is None or d < a["first"]):
            a["first"] = d
    out: list[dict[str, Any]] = []
    for acc, a in agg.items():
        sub = subs[acc]
        net = a["buy"] - a["sell"]
        if net == 0:
            census["nets_to_zero"] += 1
            continue
        own = owners.get(acc) or [("", "other")]
        role = senior(r for _, r in own)
        out.append(_filing_row(
            family=family, accession=acc, owner=own[0][0], role=role, ticker=sub["ticker"],
            issuer_cik=sub["cik"], doc_type=sub["doc_type"], direction=1 if net > 0 else -1,
            accepted_at=None, filed_date=sub["filed"], txn_date=a["first"],
            value_usd=round(a["value"], 2),
            extra={"buy_shares": a["buy"], "sell_shares": a["sell"]}))
    census["events"] = len(out)
    return out, dict(census)


# ------------------------------------------------------------------------------ 13D / 13G
def schedule_rows(idx_rows: Sequence[Mapping[str, str]], cik_ticker: Mapping[str, str]
                  ) -> list[dict[str, Any]]:
    """Original SC 13D / SC 13G filings (amendments carry a change of unknown sign and are left
    out) -> one event per accession about the SUBJECT, the entity the ticker map knows. Date
    precision until the organ reads the header's acceptance instant."""
    by_acc: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for r in idx_rows:
        if is_13d(r["form"]) or is_13g(r["form"]):
            by_acc[r["accession"]].append(r)
    out: list[dict[str, Any]] = []
    for acc, rs in by_acc.items():
        quoted = [r for r in rs if r["cik"] in cik_ticker]
        if len(quoted) != 1:
            continue                      # no subject the map knows, or ambiguous: not guessed
        r = quoted[0]
        filer = next((x["cik"] for x in rs if x["cik"] != r["cik"]), "")
        fam = "sc13d" if is_13d(r["form"]) else "sc13g"
        out.append(_filing_row(
            family=fam, accession=acc, owner=filer, role="activist" if fam == "sc13d"
            else "passive", ticker=cik_ticker[r["cik"]], issuer_cik=r["cik"],
            doc_type=r["form"], direction=1, accepted_at=None, filed_date=r["date"],
            txn_date=None, value_usd=None, extra={"file": r["file"], "subject_cik": r["cik"]}))
    return out


# ------------------------------------------------------------------------------ 13F
def normalise_name(name: str) -> str:
    """Issuer names to a join key: `APPLE INC` == `Apple Inc.` == `APPLE INC COM`."""
    s = re.sub(r"[^a-z0-9 ]", " ", (name or "").lower())
    s = re.sub(r"\b(the|inc|incorporated|corp|corporation|co|company|ltd|limited|plc|holdings?|"
               r"group|class [a-c]|cl [a-c]|com|new|del|sa|nv|ag|se|adr|ads)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_13f_table(text: str) -> dict[str, dict[str, Any]]:
    """A 13F information table -> {cusip: {name, shares}} (shares only; options and principal
    amounts are not ownership of the common)."""
    root = _xml(text)
    out: dict[str, dict[str, Any]] = {}
    if root is None:
        return out
    for it in root.iter("infoTable"):
        if (it.findtext("putCall") or "").strip():
            continue
        kind = (it.findtext("shrsOrPrnAmt/sshPrnamtType") or "SH").strip().upper()
        if kind != "SH":
            continue
        cusip = (it.findtext("cusip") or "").strip().upper()
        sh = _num(it.findtext("shrsOrPrnAmt/sshPrnamt") or "") or 0.0
        if not cusip:
            continue
        row = out.setdefault(cusip, {"name": (it.findtext("nameOfIssuer") or "").strip(),
                                     "shares": 0.0})
        row["shares"] += sh
    return out


def diff_13f(current: Mapping[str, Mapping[str, Any]], prior: Mapping[str, Mapping[str, Any]],
             *, min_change: float = 0.2) -> list[dict[str, Any]]:
    """New or enlarged (>= +20%) positions -> +1; exits or cuts (<= -20%) -> -1."""
    out: list[dict[str, Any]] = []
    for cusip in sorted(set(current) | set(prior)):
        cur = float((current.get(cusip) or {}).get("shares") or 0.0)
        old = float((prior.get(cusip) or {}).get("shares") or 0.0)
        name = str((current.get(cusip) or prior.get(cusip) or {}).get("name") or "")
        if old <= 0 < cur:
            d, ch = 1, None
        elif cur <= 0 < old:
            d, ch = -1, -1.0
        elif old > 0:
            ch = cur / old - 1.0
            d = 1 if ch >= min_change else -1 if ch <= -min_change else 0
        else:
            continue
        if d:
            out.append({"cusip": cusip, "name": name, "direction": d,
                        "change": None if ch is None else round(ch, 4)})
    return out


# ------------------------------------------------------------------------------ congress
_HOUSE_TX = re.compile(
    r"\(([A-Z][A-Z0-9.\-]{0,6})\)\s*\[(ST|OP)\]\s*(P|S\s*\(partial\)|S)\s+"
    r"(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+\$([\d,]+)", re.S)


def parse_house_ptr_text(text: str, *, doc_id: str, filed_date: str) -> list[dict[str, Any]]:
    """Text of one e-filed House PTR PDF -> one event per (ticker) net of the report's lines.
    A scanned (paper) PTR yields no text and therefore no rows; the organ counts it."""
    net: dict[str, dict[str, Any]] = {}
    for m in _HOUSE_TX.finditer(re.sub(r"[ \t]+", " ", text or "")):
        ticker, _kind, typ, txd, _note, amt = m.groups()
        side = 1 if typ.startswith("P") else -1
        n = net.setdefault(ticker, {"net": 0, "first": None, "value": 0.0})
        n["net"] += side
        n["value"] += _num(amt) or 0.0
        d = parse_day(txd)
        if d and (n["first"] is None or d < n["first"]):
            n["first"] = d
    return [_filing_row(family="house_ptr", accession=f"house:{doc_id}:{t}", owner=doc_id,
                        role="member", ticker=t, issuer_cik="", doc_type="PTR",
                        direction=(1 if n["net"] > 0 else -1), accepted_at=None,
                        filed_date=filed_date, txn_date=n["first"], value_usd=n["value"])
            for t, n in sorted(net.items()) if n["net"] != 0]


def _cells(tr: str) -> list[str]:
    return [re.sub(r"<[^>]+>", " ", c).strip() for c in
            re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S | re.I)]


def parse_senate_ptr_html(html: str, *, report_id: str, filed_date: str
                          ) -> list[dict[str, Any]]:
    """One eFD PTR page (`/search/view/ptr/<id>/`) -> one event per ticker, net of its lines."""
    net: dict[str, dict[str, Any]] = {}
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html or "", re.S | re.I):
        c = [re.sub(r"\s+", " ", x) for x in _cells(tr)]
        if len(c) < 8:
            continue
        ticker = c[3].strip().upper()
        typ = c[6].lower()
        if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,6}", ticker) or "stock" not in c[5].lower():
            continue
        side = 1 if "purchase" in typ else -1 if "sale" in typ else 0
        if not side:
            continue
        n = net.setdefault(ticker, {"net": 0, "first": None})
        n["net"] += side
        d = parse_day(c[1])
        if d and (n["first"] is None or d < n["first"]):
            n["first"] = d
    return [_filing_row(family="senate_ptr", accession=f"senate:{report_id}:{t}",
                        owner=report_id, role="member", ticker=t, issuer_cik="",
                        doc_type="PTR", direction=(1 if n["net"] > 0 else -1),
                        accepted_at=None, filed_date=filed_date, txn_date=n["first"],
                        value_usd=None)
            for t, n in sorted(net.items()) if n["net"] != 0]


def parse_senate_search(doc: Any) -> list[dict[str, str]]:
    """eFD `/search/report/data/` JSON -> [{report_id, filed_date}] for e-filed PTRs only."""
    out: list[dict[str, str]] = []
    for row in (doc.get("data") if isinstance(doc, dict) else None) or []:
        if not isinstance(row, list) or len(row) < 5:
            continue
        m = re.search(r"/search/view/ptr/([0-9a-fA-F\-]{8,})/", str(row[3]))
        d = parse_day(row[4])
        if m and d:
            out.append({"report_id": m.group(1), "filed_date": d})
    return out


# ------------------------------------------------------------------------------ odds
def odds_category(question: str) -> str | None:
    q = f" {(question or '').lower()} "
    for cat, words in ODDS_WORDS:
        if any(w in q for w in words):
            return cat
    return None


def odds_polarity(question: str) -> int:
    """+1 when YES is the 'more' outcome (hike, above, higher), -1 when it is the 'less' one."""
    q = f" {(question or '').lower()} "
    up = any(w in q for w in _UP_WORDS)
    down = any(w in q for w in _DOWN_WORDS)
    if up == down:
        return 1 if not up else 0
    return 1 if up else -1


def odds_events(venue: str, market_id: str, question: str,
                series: Sequence[tuple[datetime, float]], *, move: float = ODDS_MOVE
                ) -> list[dict[str, Any]]:
    """A contract's daily probability path -> one event per day whose move clears `move`.

    `observed_at` is the timestamp of the LATER price of the pair -- the instant the move had
    happened on the venue's public tape. Direction = polarity x sign(move); a question whose
    polarity cannot be read is not signed."""
    cat = odds_category(question)
    pol = odds_polarity(question)
    if cat is None or pol == 0:
        return []
    pts = sorted((t, p) for t, p in series if 0.0 <= p <= 1.0)
    out: list[dict[str, Any]] = []
    for (_t0, p0), (t1, p1) in itertools.pairwise(pts):
        dp = p1 - p0
        if abs(dp) < move:
            continue
        out.append({"event_id": f"{venue}|{market_id}|{t1.date().isoformat()}",
                    "family": venue, "kind": "odds", "category": cat, "market": market_id,
                    "question": question[:200], "observed_at": t1.isoformat(),
                    "p_from": round(p0, 4), "p_to": round(p1, 4),
                    "direction": pol * (1 if dp > 0 else -1)})
    return out


def parse_kalshi_markets(doc: Any) -> list[dict[str, Any]]:
    out = []
    for m in (doc.get("markets") if isinstance(doc, dict) else None) or []:
        if isinstance(m, dict) and m.get("ticker"):
            out.append({"ticker": str(m["ticker"]),
                        "question": " ".join(str(m.get(k) or "") for k in
                                             ("title", "subtitle", "yes_sub_title")).strip()})
    return out


def parse_kalshi_candles(doc: Any) -> list[tuple[datetime, float]]:
    """Kalshi candlesticks -> [(period end, close probability)], cents or dollars."""
    out: list[tuple[datetime, float]] = []
    for c in (doc.get("candlesticks") if isinstance(doc, dict) else None) or []:
        if not isinstance(c, dict):
            continue
        ts = c.get("end_period_ts")
        pr = c.get("price")
        price: dict[str, Any] = pr if isinstance(pr, dict) else {}
        raw = (price.get("close_dollars") if price.get("close_dollars") is not None
               else price.get("close"))
        if raw is None:
            bid, ask = c.get("yes_bid"), c.get("yes_ask")
            yb = bid.get("close") if isinstance(bid, dict) else None
            ya = ask.get("close") if isinstance(ask, dict) else None
            raw = (yb + ya) / 2 if isinstance(yb, int | float) and isinstance(ya, int | float) \
                else None
        p = _num(str(raw)) if raw is not None else None
        if ts is None or p is None:
            continue
        p = p / 100.0 if p > 1.0 else p
        out.append((datetime.fromtimestamp(int(ts), tz=UTC), p))
    return out


def parse_polymarket_markets(doc: Any) -> list[dict[str, Any]]:
    out = []
    for m in doc if isinstance(doc, list) else []:
        if not isinstance(m, dict):
            continue
        try:
            outcomes = json.loads(m.get("outcomes") or "[]")
            tokens = json.loads(m.get("clobTokenIds") or "[]")
        except (TypeError, ValueError):
            continue
        if outcomes[:2] != ["Yes", "No"] or len(tokens) < 1:
            continue
        out.append({"id": str(m.get("id") or tokens[0]), "token": str(tokens[0]),
                    "question": str(m.get("question") or "")})
    return out


def parse_clob_history(doc: Any) -> list[tuple[datetime, float]]:
    hist = doc.get("history") if isinstance(doc, dict) else None
    out = []
    for h in hist or []:
        try:
            out.append((datetime.fromtimestamp(int(h["t"]), tz=UTC), float(h["p"])))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def daily_points(series: Sequence[tuple[datetime, float]]) -> list[tuple[datetime, float]]:
    """Last point per UTC day -- so the move is a day-over-day move whatever the venue's grain."""
    last: dict[date, tuple[datetime, float]] = {}
    for t, p in sorted(series):
        last[t.date()] = (t, p)
    return [last[d] for d in sorted(last)]


# ------------------------------------------------------------------------------ observations
def latest_rows(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """One row per event_id: the last written, except that a datetime-precision row is never
    replaced by a date-precision one for the same accession (the data set re-reporting it)."""
    keep: dict[str, Mapping[str, Any]] = {}
    for r in rows:
        eid = str(r.get("event_id") or "")
        if not eid:
            continue
        old = keep.get(eid)
        if old is not None and old.get("accepted_at") and not r.get("accepted_at"):
            continue
        keep[eid] = r
    by_acc: dict[str, Mapping[str, Any]] = {}
    for r in keep.values():
        acc = str(r.get("accession") or "")
        owner = str(r.get("owner") or "")
        k = f"{acc}|{owner}" if acc else str(r["event_id"])
        old = by_acc.get(k)
        if old is None or (r.get("accepted_at") and not old.get("accepted_at")):
            by_acc[k] = r
    return list(by_acc.values())


def source_of(row: Mapping[str, Any]) -> str:
    """The cell's source: actor family x actor class (the role split the design asks for)."""
    fam = str(row.get("family") or "")
    if row.get("kind") == "odds":
        return f"{fam}:{row.get('category')}"
    if fam in ("form4", "form345_ds"):
        return f"form4:{row.get('role') or 'other'}"
    if fam in ("house_ptr", "senate_ptr"):
        return f"{fam.split('_')[0]}:member"
    return f"{fam}:{row.get('role') or 'filer'}"


def _obs(target: str, relation: str, lead: str, source: str, at: datetime, d: int
         ) -> av.Observation:
    return av.Observation(target, relation, lead, source, "", at, int(d))


def aggregate_days(rows: Sequence[Mapping[str, Any]], *, prefix: str, group: str,
                   members: Iterable[str] | None = None, clock: str = "observable"
                   ) -> list[tuple[datetime, int, dict[str, Any]]]:
    """Per US filing day: the share of issuers whose filers BOUGHT, against its own trailing
    baseline (strictly earlier days). |z| >= AGG_Z -> a dated breadth event. The event is
    placed at the LATEST knowable instant among the day's members -- the day's count did not
    exist before its last filing did."""
    fams = set(members) if members is not None else None
    per: dict[date, dict[str, Any]] = {}
    for r in rows:
        if r.get("kind") != "filing" or not int(r.get("direction") or 0):
            continue
        if fams is not None and str(r.get("family")) not in fams:
            continue
        if group != "all" and role_group(str(r.get("role") or "")) != group:
            continue
        if clock == "oracle":
            at = oracle_at(r)
        else:
            at, _ = knowable_at(r)
        if at is None:
            continue
        day = filing_day(r) if clock != "oracle" else at.date()
        if day is None:
            continue
        p = per.setdefault(day, {"buy": set(), "sell": set(), "at": at})
        issuer = str(r.get("ticker") or r.get("issuer_cik") or r.get("event_id"))
        p["buy" if int(r["direction"]) > 0 else "sell"].add(issuer)
        p["at"] = max(p["at"], at)
    out: list[tuple[datetime, int, dict[str, Any]]] = []
    hist: list[float] = []
    for day in sorted(per):
        p = per[day]
        n = len(p["buy"] | p["sell"])
        if n < AGG_MIN_ISSUERS:
            continue
        share = len(p["buy"]) / n
        base = hist[-AGG_BASELINE_DAYS:]
        if len(base) >= AGG_MIN_BASELINE:
            mu = sum(base) / len(base)
            sd = math.sqrt(sum((x - mu) ** 2 for x in base) / (len(base) - 1))
            z = (share - mu) / sd if sd > 0 else 0.0
            if abs(z) >= AGG_Z:
                out.append((p["at"], 1 if z > 0 else -1,
                            {"day": day.isoformat(), "z": round(z, 3), "n_issuers": n,
                             "buy_share": round(share, 4), "source": f"{prefix}:{group}"}))
        hist.append(share)
    return out


#: The aggregate breadth sources: (source prefix, role group, families).
AGG_SOURCES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("form4_agg", "exec", ("form4", "form345_ds")),
    ("form4_agg", "director", ("form4", "form345_ds")),
    ("form4_agg", "all", ("form4", "form345_ds")),
    ("congress_agg", "all", ("house_ptr", "senate_ptr")),
)


def cluster_observations(rows: Sequence[Mapping[str, Any]], ticker_cfd: Mapping[str, str],
                         universe: set[str] | None) -> list[av.Observation]:
    """`libs.research.form4.clusters` (reused, never re-implemented) over the stored open-market
    buys: >= 2 distinct insiders inside 5 days, dated at the latest acceptance -> +1 direct."""
    txns: list[form4.Form4Txn] = []
    for r in rows:
        if r.get("family") not in ("form4", "form345_ds") or int(r.get("direction") or 0) <= 0:
            continue
        at, _ = knowable_at(r)
        txd = oracle_at(r)
        cfd = (str(r.get("instrument") or "")
               or ticker_cfd.get(str(r.get("ticker") or "")))
        if at is None or txd is None or not cfd or (universe is not None and cfd not in universe):
            continue
        txns.append(form4.Form4Txn(issuer=cfd, insider=str(r.get("owner") or r["event_id"]),
                                   title=str(r.get("role") or ""), txn_date=txd, filed_at=at,
                                   code="P", shares=float(r.get("buy_shares") or 1.0),
                                   price=1.0))
    return [_obs(c.issuer, "direct", "", "form4:cluster", c.knowable_at, 1)
            for c in form4.clusters(txns)]


def observations(rows: Iterable[Mapping[str, Any]], *,
                 ticker_cfd: Mapping[str, str] | None = None,
                 universe: set[str] | None = None, clock: str = "observable"
                 ) -> tuple[list[av.Observation], dict[str, int]]:
    """Every stored event -> observations on the MT5 universe. `clock="observable"` is the only
    clock a cell, family or axis uses; `clock="oracle"` is the transaction-date reading the decay
    table is computed from and is labelled research-only wherever it is published."""
    rows = latest_rows(rows)
    ticker_cfd = ticker_cfd or {}
    census: dict[str, int] = defaultdict(int)
    out: list[av.Observation] = []

    def ok(sym: str) -> bool:
        return universe is None or sym in universe

    for r in rows:
        d = int(r.get("direction") or 0)
        if not d:
            census["no_direction"] += 1
            continue
        if r.get("kind") == "odds":
            if clock == "oracle":
                continue
            at, _ = knowable_at(r)
            if at is None:
                census["unknowable"] += 1
                continue
            cat = str(r.get("category") or "")
            tg = [t for t in ODDS_TARGETS.get(cat, ()) if ok(t)]
            if not tg:
                census["no_quoted_target"] += 1
            for t in tg:
                out.append(_obs(t, "odds", cat, source_of(r), at, d))
            continue
        cfd = (str(r.get("instrument") or "")
               or ticker_cfd.get(str(r.get("ticker") or "")))
        if not cfd or not ok(cfd):
            census["not_quoted_direct"] += 1
            continue
        at = oracle_at(r) if clock == "oracle" else knowable_at(r)[0]
        if at is None:
            census["unknowable"] += 1
            continue
        out.append(_obs(cfd, "direct", "", source_of(r), at, d))
    for prefix, group, fams in AGG_SOURCES:
        for at, d, _meta in aggregate_days(rows, prefix=prefix, group=group, members=fams,
                                           clock=clock):
            for t in AGG_TARGETS:
                if ok(t):
                    out.append(_obs(t, "aggregate", f"{prefix}:{group}", f"{prefix}:{group}",
                                    at, d))
    if clock != "oracle":
        out.extend(cluster_observations(rows, ticker_cfd, universe))
    out.sort(key=lambda o: (o.at, o.target, o.source))
    return out, dict(census)


def pit_violations(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Events whose observable instant precedes their own transaction date -- impossible for a
    real disclosure, so each one is a parser or clock defect (the RED check reads this)."""
    bad = []
    for r in rows:
        if r.get("kind") != "filing":
            continue
        at, _ = knowable_at(r)
        txd = parse_day(r.get("txn_date"))
        if at is not None and txd is not None and at.date() < date.fromisoformat(txd):
            bad.append({"event_id": r.get("event_id"), "knowable_at": at.isoformat(),
                        "txn_date": txd})
    return bad
