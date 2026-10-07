"""HDS -- holder state from SEC EDGAR ownership filings (13F, 13D/G, Form 4), on this host only.

WHY (DATA-22, the HDS row). Who holds a name, who is accumulating it and who inside the company
is buying or selling it are disclosed to the SEC and published on EDGAR, a US federal source.
Single-name equities are EVENT-LANE ONLY on this desk (CLAUDE.md, the two lanes), so this organ
measures STATE and emits no statistical cell: its numbers go to MARKET_STATE.json for the news
and earnings lane to read.

WHAT IS PARSED (from files already on disk under `data/edgar_ownership/`, any depth):

    13F-HR information table (XML)   holdings per CUSIP: value, shares, put/call; summed across
                                     filers per period, and the change against the prior period
    SC 13D / SC 13G (+ /A) (text)    subject company, filer, percent of class; 13D (an
                                     intention to influence) and 13G (passive) are counted apart
    Form 4 (XML)                     non-derivative transactions: open-market purchases (code P)
                                     and sales (code S), shares and value, per issuer ticker

WHERE THE FILES COME FROM -- HONESTLY: NOTHING ON A CLOCK FETCHES THEM TODAY. The desk's EDGAR
readers are `side_channels/sec_edgar_miner.py` (company index pages, 13F mentions only) and
`research/sandboxes/edgar_transmission.py` (full-text 8-K/10-K/10-Q hits). Neither saves an
ownership document, and a fetcher is not added here silently: with the directory empty the
state is UNMEASURED with that reason, and the parsers are ready for whichever fetcher is wired.

PIT. A filing is knowable at its EDGAR acceptance time when the file carries one
(ACCEPTANCE-DATETIME in the SGML header, read as America/New_York), else at its filing date's
end (23:59 ET, a conservative bound), else it is not read at all.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "data" / "edgar_ownership"
UNMEASURED = "UNMEASURED"
ENGINE = "ownership_state"
NY = ZoneInfo("America/New_York")
WINDOW_DAYS = 90
NO_FETCHER = ("no ownership filing on this host (data/edgar_ownership/ is empty or absent); no "
              "scheduled EDGAR ownership fetcher exists -- side_channels/sec_edgar_miner.py reads "
              "company index pages and sandboxes/edgar_transmission.py caches full-text "
              "8-K/10-K/10-Q hits, neither saves 13F/13D/G/Form 4 documents")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(el: ET.Element | None, *path: str) -> str:
    """Namespace-blind descent: the first child chain matching `path`, its stripped text."""
    cur = el
    for name in path:
        if cur is None:
            return ""
        cur = next((c for c in cur if _local(c.tag) == name), None)
    return (cur.text or "").strip() if cur is not None and cur.text else ""


def _num(s: str) -> float | None:
    try:
        return float(s.replace(",", ""))
    except (AttributeError, ValueError):
        return None


def _xml(text: str) -> ET.Element | None:
    m = re.search(r"<\?xml.*?\?>|<(informationTable|ownershipDocument)\b", text, re.S)
    if not m:
        return None
    body = text[m.start():]
    end = re.search(r"</(informationTable|ownershipDocument)>", body)
    if end:
        body = body[:end.end()]
    try:
        return ET.fromstring(body.encode("utf-8"))
    except ET.ParseError:
        return None


# ============================================================================== PIT stamp
def accepted_at(text: str) -> datetime | None:
    m = re.search(r"ACCEPTANCE-DATETIME>\s*(\d{14})", text)
    if m:
        return datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(tzinfo=NY).astimezone(UTC)
    m = re.search(r"FILED AS OF DATE:\s*(\d{8})", text) or re.search(
        r"<periodOfReport>\s*(\d{4}-\d{2}-\d{2})", text)
    if m:
        raw = m.group(1).replace("-", "")
        d = datetime.strptime(raw, "%Y%m%d").replace(hour=23, minute=59, tzinfo=NY)
        return d.astimezone(UTC)
    return None


# ============================================================================== parsers
def parse_13f(text: str) -> dict[str, Any]:
    """A 13F-HR information table: one row per holding."""
    root = _xml(text)
    if root is None or _local(root.tag) != "informationTable":
        return {"status": "PARSE_FAILED", "why": "no informationTable XML"}
    rows = []
    for it in root:
        if _local(it.tag) != "infoTable":
            continue
        rows.append({"issuer": _text(it, "nameOfIssuer"), "cusip": _text(it, "cusip").upper(),
                     "value": _num(_text(it, "value")),
                     "shares": _num(_text(it, "shrsOrPrnAmt", "sshPrnamt")),
                     "put_call": _text(it, "putCall") or None})
    filer = re.search(r"FILER:.*?COMPANY CONFORMED NAME:\s*(.+)", text, re.S)
    period = re.search(r"CONFORMED PERIOD OF REPORT:\s*(\d{8})", text)
    return {"status": "PARSED", "form": "13F-HR", "holdings": rows,
            "filer": filer.group(1).strip() if filer else "",
            "period": (f"{period.group(1)[:4]}-{period.group(1)[4:6]}-{period.group(1)[6:]}"
                       if period else "")}


def parse_13dg(text: str) -> dict[str, Any]:
    """A Schedule 13D/13G (or amendment) header and cover: who, of what, how much."""
    form = re.search(r"CONFORMED SUBMISSION TYPE:\s*(SC 13[DG](?:/A)?)", text)
    if not form:
        return {"status": "PARSE_FAILED", "why": "no SC 13D/13G submission type"}
    subj = re.search(r"SUBJECT COMPANY:.*?COMPANY CONFORMED NAME:\s*(.+)", text, re.S)
    filer = re.search(r"FILED BY:.*?COMPANY CONFORMED NAME:\s*(.+)", text, re.S)
    pct = re.search(r"PERCENT OF CLASS REPRESENTED BY AMOUNT IN ROW \(?\d+\)?\s*[:\-]?\s*"
                    r"([0-9]+(?:\.[0-9]+)?)\s*%", text, re.I)
    return {"status": "PARSED", "form": form.group(1),
            "kind": "activist" if "13D" in form.group(1) else "passive",
            "subject": subj.group(1).strip() if subj else "",
            "filer": filer.group(1).strip() if filer else "",
            "percent_of_class": float(pct.group(1)) if pct else None}


def parse_form4(text: str) -> dict[str, Any]:
    """A Form 4: issuer and the non-derivative transactions."""
    root = _xml(text)
    if root is None or _local(root.tag) != "ownershipDocument":
        return {"status": "PARSE_FAILED", "why": "no ownershipDocument XML"}
    issuer = next((c for c in root if _local(c.tag) == "issuer"), None)
    owner = next((c for c in root if _local(c.tag) == "reportingOwner"), None)
    txs = []
    table = next((c for c in root if _local(c.tag) == "nonDerivativeTable"), None)
    for t in (table if table is not None else []):
        if _local(t.tag) != "nonDerivativeTransaction":
            continue
        code = _text(t, "transactionCoding", "transactionCode")
        shares = _num(_text(t, "transactionAmounts", "transactionShares", "value"))
        price = _num(_text(t, "transactionAmounts", "transactionPricePerShare", "value"))
        ad = _text(t, "transactionAmounts", "transactionAcquiredDisposedCode", "value")
        txs.append({"date": _text(t, "transactionDate", "value"), "code": code,
                    "shares": shares, "price": price, "acquired_disposed": ad})
    return {"status": "PARSED", "form": "4", "ticker": _text(issuer, "issuerTradingSymbol"),
            "issuer": _text(issuer, "issuerName"),
            "owner": _text(owner, "reportingOwnerId", "rptOwnerName"), "transactions": txs}


def parse(text: str) -> dict[str, Any]:
    if re.search(r"SUBMISSION TYPE:\s*SC 13[DG]", text):
        out = parse_13dg(text)
    elif "<ownershipDocument" in text:
        out = parse_form4(text)
    elif "<informationTable" in text:
        out = parse_13f(text)
    else:
        return {"status": "PARSE_FAILED", "why": "not a 13F, 13D/G or Form 4 document"}
    out["knowable_at"] = (lambda t: t.isoformat() if t else None)(accepted_at(text))
    return out


# ============================================================================== the state
def read_cache(root: Path = CACHE) -> Iterable[tuple[str, str]]:
    if not root.is_dir():
        return []
    files = sorted(p for p in root.rglob("*") if p.is_file()
                   and p.suffix.lower() in (".xml", ".txt", ".htm", ".html"))
    out = []
    for p in files:
        try:
            out.append((str(p.relative_to(root)), p.read_text("utf-8", errors="replace")))
        except OSError:
            continue
    return out


def state(docs: Iterable[tuple[str, str]], now: datetime) -> dict[str, Any]:
    """Holder state as of `now` from (name, text) documents."""
    parsed, failed, unstamped, future = [], 0, 0, 0
    total = 0
    for _name, text in docs:
        total += 1
        d = parse(text)
        if d["status"] != "PARSED":
            failed += 1
            continue
        if not d.get("knowable_at"):
            unstamped += 1
            continue
        if datetime.fromisoformat(d["knowable_at"]) > now:
            future += 1
            continue
        parsed.append(d)
    out: dict[str, Any] = {"engine": ENGINE, "at": now.isoformat(timespec="seconds"),
                           "files": total, "parsed": len(parsed), "parse_failed": failed,
                           "unstamped_skipped": unstamped, "not_yet_knowable": future,
                           "lane": "event (single names): state only, no statistical cell"}
    if total == 0:
        return {**out, "status": UNMEASURED, "why": NO_FETCHER}
    if not parsed:
        return {**out, "status": UNMEASURED,
                "why": "no file parsed as a stamped 13F/13D/G/Form 4 knowable by now"}
    since = now - timedelta(days=WINDOW_DAYS)
    insiders: dict[str, dict[str, Any]] = {}
    for d in (x for x in parsed if x["form"] == "4"):
        if datetime.fromisoformat(d["knowable_at"]) < since:
            continue
        tk = (d.get("ticker") or d.get("issuer") or "?").upper()
        slot = insiders.setdefault(tk, {"buy_value": 0.0, "sell_value": 0.0, "buyers": set(),
                                        "sellers": set(), "filings": 0})
        slot["filings"] += 1
        for t in d["transactions"]:
            v = (t["shares"] or 0.0) * (t["price"] or 0.0)
            if t["code"] == "P":
                slot["buy_value"] += v
                slot["buyers"].add(d["owner"])
            elif t["code"] == "S":
                slot["sell_value"] += v
                slot["sellers"].add(d["owner"])
    out["insider_90d"] = {tk: {"filings": s["filings"], "buy_value": round(s["buy_value"], 2),
                               "sell_value": round(s["sell_value"], 2),
                               "net_value": round(s["buy_value"] - s["sell_value"], 2),
                               "n_buyers": len(s["buyers"]), "n_sellers": len(s["sellers"])}
                          for tk, s in sorted(insiders.items())}
    blocks: dict[str, dict[str, Any]] = {}
    for d in (x for x in parsed if x["form"].startswith("SC 13")):
        if datetime.fromisoformat(d["knowable_at"]) < since:
            continue
        slot = blocks.setdefault(d["subject"] or "?", {"activist": 0, "passive": 0,
                                                       "max_percent": None, "filers": set()})
        slot[d["kind"]] += 1
        slot["filers"].add(d["filer"])
        p = d.get("percent_of_class")
        if p is not None and (slot["max_percent"] is None or p > slot["max_percent"]):
            slot["max_percent"] = p
    out["blockholders_90d"] = {k: {**{kk: vv for kk, vv in v.items() if kk != "filers"},
                                   "n_filers": len(v["filers"])}
                               for k, v in sorted(blocks.items())}
    out["institutional"] = institutional([x for x in parsed if x["form"] == "13F-HR"])
    out["status"] = "MEASURED"
    return out


def institutional(filings: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Shares per CUSIP summed across filers for each period, and the change on the prior one
    (only filers present in BOTH periods are compared, so a new filer is not read as buying)."""
    if not filings:
        return {"status": UNMEASURED, "why": "no 13F-HR information table on this host"}
    by: dict[str, dict[str, dict[str, float]]] = {}
    names: dict[str, str] = {}
    for f in filings:
        per = by.setdefault(str(f.get("period") or "?"), {})
        for h in f["holdings"]:
            if h.get("put_call") or not h["cusip"]:
                continue
            per.setdefault(h["cusip"], {})
            per[h["cusip"]][f["filer"]] = per[h["cusip"]].get(f["filer"], 0.0) + (
                h["shares"] or 0.0)
            names[h["cusip"]] = h["issuer"]
    periods = sorted(by)
    last = periods[-1]
    prev = periods[-2] if len(periods) > 1 else None
    rows = {}
    for cusip, filers in by[last].items():
        row: dict[str, Any] = {"issuer": names.get(cusip, ""), "shares": sum(filers.values()),
                               "n_filers": len(filers)}
        if prev is not None:
            old = by[prev].get(cusip, {})
            common = set(filers) & set(old)
            row["change_common_filers"] = (sum(filers[f] - old[f] for f in common)
                                           if common else None)
            row["n_common_filers"] = len(common)
        rows[cusip] = row
    return {"status": "MEASURED", "period": last, "prior_period": prev, "holdings": rows}


def build(*, now: datetime, root: Path = CACHE) -> dict[str, Any]:
    return state(read_cache(root), now)
