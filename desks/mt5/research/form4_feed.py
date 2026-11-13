"""SEC FORM 4 INSIDER FILINGS FOR THE DESK'S US SHARE CFDS -> `libs.research.form4` CLUSTERS.

    python desks/mt5/research/form4_feed.py --once --budget-s 600

WHY THIS ORGAN EXISTS (backlog N16, 2026-10-13: "wire the EXISTS-UNWIRED organs").
`libs/research/form4.py` computes and ranks insider-buying clusters, point-in-time, and says of
itself "This module computes and ranks. It does not fetch". Nothing fetched, so the event lane it
was written for (`mt5desk/family_event_reaction`, whose docstring names an insider cluster as its
first example) never received a single cluster. This is the fetch half, on a clock.

WHAT IT READS, AND ONLY THAT. The SEC's own free public archive, under its fair-access policy:

  * `https://www.sec.gov/files/company_tickers.json`  ticker -> CIK, refreshed weekly
  * `https://www.sec.gov/Archives/edgar/daily-index/<Y>/QTR<q>/form.<YYYYMMDD>.idx`  one per day
  * `https://www.sec.gov/Archives/<file>`  the filing itself, ONLY for issuers the desk can trade

A DECLARED USER-AGENT IS REQUIRED (`QUANT_EDGAR_UA`, the same variable every other EDGAR reader on
this desk uses). Without one the organ fetches nothing and publishes UNMEASURED with that reason --
it never invents a contact. Requests are spaced `MIN_INTERVAL_S` apart (well under the SEC's 10/s),
robots.txt is read once per pass and honoured, and nothing behind a login is touched.

THE POINT-IN-TIME RULE IS INHERITED. Every transaction carries the filing's ACCEPTANCE-DATETIME as
`filed_at`; `form4.clusters` dates a cluster at the latest acceptance in it. A transaction date
is recorded for the filing-lag census and never used as a join key.

WHICH ISSUERS. US share CFDs in the MT5 registry (`universe_policy.is_equity`), mapped to SEC
tickers by the symbol's own stem (`AAPL`, `AAPL.24H`, `AAPLUSD` -> AAPL). A symbol that maps to no
SEC ticker is COUNTED as unmapped, not dropped silently. This is the EVENT lane the principal's
two-lane order (2026-09-06) reserves for single names: it mints no statistical hypothesis.

WHAT IT WRITES.
  data/form4/form4_txns.jsonl       every parsed transaction (append-only, deduplicated by filing)
  data/form4/insider_clusters.json  `form4.as_events` rows -- the event-bus shape, `at` = knowable
  data/form4/form4_cursor.json      the last fully processed index day
  reports/FORM4.json                the census: fetched, parsed, dropped by code, clusters, status
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(ROOT), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DATA = BASE / "data" / "form4"
TXNS = DATA / "form4_txns.jsonl"
CLUSTERS = DATA / "insider_clusters.json"
CURSOR = DATA / "form4_cursor.json"
TICKERS_CACHE = DATA / "company_tickers.json"
REPORT = BASE / "reports" / "FORM4.json"

SEC = "https://www.sec.gov"
TICKERS_URL = f"{SEC}/files/company_tickers.json"
#: Spacing between requests. The SEC's fair-access ceiling is 10/s; this stays at a fifth of it.
MIN_INTERVAL_S = 0.5
#: How far back the first pass starts, and the most index days one pass will walk.
BACKFILL_DAYS = 30
TICKERS_MAX_AGE_S = 7 * 86400
#: Transactions older than this are not re-clustered (the issuer baseline needs about a year).
CLUSTER_LOOKBACK_DAYS = 400
DEFAULT_BUDGET_S = 600.0

Fetch = Callable[[str], bytes | None]


def _now() -> datetime:
    return datetime.now(UTC)


def user_agent() -> str:
    return os.environ.get("QUANT_EDGAR_UA", "").strip()


class Fetcher:
    """Throttled GET with the declared User-Agent. Returns None on 404 (no index that day)."""

    def __init__(self, ua: str, interval: float = MIN_INTERVAL_S) -> None:
        self.ua, self.interval, self._last, self.n = ua, interval, 0.0, 0
        self.errors: list[str] = []

    def __call__(self, url: str) -> bytes | None:
        wait = self.interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        self.n += 1
        req = urllib.request.Request(url, headers={"User-Agent": self.ua,
                                                   "Accept-Encoding": "identity"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return bytes(r.read())
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            self.errors.append(f"{exc.code} {url}")
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            self.errors.append(f"{type(exc).__name__} {url}")
            raise


def robots_allows(ua: str, paths: list[str], fetch: Fetch) -> tuple[bool, str]:
    raw = fetch(f"{SEC}/robots.txt")
    if raw is None:
        return True, "no robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(raw.decode("utf-8", "replace").splitlines())
    refused = [p for p in paths if not rp.can_fetch(ua, f"{SEC}{p}")]
    return (not refused), ("refused: " + ", ".join(refused) if refused else "allowed")


# ---------------------------------------------------------------- issuer map

def ticker_stems(symbol: str) -> list[str]:
    """Candidate SEC tickers for an MT5 share-CFD symbol, most specific first."""
    stem = symbol.split(".")[0].upper()
    out = [stem]
    if stem.endswith("USD") and len(stem) > 3:
        out.append(stem[:-3])
    return out


def issuer_map(symbols: list[str], sec_tickers: dict[str, Any]) -> tuple[dict[int, list[str]],
                                                                          list[str]]:
    """CIK -> [MT5 symbols], and the symbols no SEC ticker matched."""
    by_ticker: dict[str, int] = {}
    for row in (sec_tickers.values() if isinstance(sec_tickers, dict) else []):
        try:
            by_ticker[str(row["ticker"]).upper()] = int(row["cik_str"])
        except (KeyError, TypeError, ValueError):
            continue
    ciks: dict[int, list[str]] = {}
    unmapped: list[str] = []
    for sym in symbols:
        cik = next((by_ticker[t] for t in ticker_stems(sym) if t in by_ticker), None)
        if cik is None:
            unmapped.append(sym)
        else:
            ciks.setdefault(cik, []).append(sym)
    return ciks, unmapped


def equity_symbols() -> list[str]:
    try:
        import universe_policy as up
        reg = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))
        return sorted(s for s in reg if up.is_equity(s))
    except Exception:
        return []


# ---------------------------------------------------------------- parsing

_IDX_ROW = re.compile(r"^(\S+)\s+(.+?)\s+(\d+)\s+(\d{8}|\d{4}-\d{2}-\d{2})\s+(\S+)\s*$")


def parse_index(text: str) -> list[dict[str, Any]]:
    """Form 4 rows of a daily `form.idx` (amendments 4/A excluded: they restate, not add)."""
    out = []
    for line in text.splitlines():
        m = _IDX_ROW.match(line)
        if m and m.group(1) == "4":
            out.append({"company": m.group(2).strip(), "cik": int(m.group(3)),
                        "file": m.group(5)})
    return out


def _t(node: Any, path: str) -> str:
    el = node.find(path)
    return "" if el is None or el.text is None else el.text.strip()


def _f(node: Any, path: str) -> float:
    try:
        return float(_t(node, path) or 0.0)
    except ValueError:
        return 0.0


def parse_filing(raw: str) -> list[dict[str, Any]]:
    """Every non-derivative transaction in one Form 4 submission, with its acceptance time."""
    m = re.search(r"<ACCEPTANCE-DATETIME>\s*(\d{14})", raw)
    x = re.search(r"<ownershipDocument>.*?</ownershipDocument>", raw, re.S)
    if not m or not x:
        return []
    body = x.group(0)
    # No DTD and no entities in a Form 4; refusing them makes ElementTree safe on this input.
    if "<!DOCTYPE" in body or "<!ENTITY" in body:
        return []
    # EDGAR stamps acceptance in US Eastern time; reading it as EST (UTC-5) is the conservative
    # (later) reading in summer too, so a cluster is never dated before it was public.
    filed_utc = datetime.strptime(m.group(1) + "-0500", "%Y%m%d%H%M%S%z").astimezone(UTC)
    try:
        doc = ET.fromstring(body)
    except ET.ParseError:
        return []
    issuer_cik = int(_t(doc, "issuer/issuerCik") or 0)
    ticker = _t(doc, "issuer/issuerTradingSymbol").upper()
    owners = doc.findall("reportingOwner")
    name = " & ".join(_t(o, "reportingOwnerId/rptOwnerName") for o in owners) or "?"
    rel = owners[0].find("reportingOwnerRelationship") if owners else None
    title = ""
    if rel is not None:
        title = (_t(rel, "officerTitle")
                 or ("director" if _t(rel, "isDirector") in ("1", "true") else "")
                 or ("10% owner" if _t(rel, "isTenPercentOwner") in ("1", "true") else "")
                 or ("officer" if _t(rel, "isOfficer") in ("1", "true") else "other"))
    rows = []
    for tx in doc.findall("nonDerivativeTable/nonDerivativeTransaction"):
        d = _t(tx, "transactionDate/value")[:10]
        try:
            txd = datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            continue
        rows.append({"issuer_cik": issuer_cik, "ticker": ticker, "insider": name,
                     "title": title, "txn_date": txd.isoformat(),
                     "filed_at": filed_utc.isoformat(),
                     "code": _t(tx, "transactionCoding/transactionCode").upper(),
                     "acq_disp": _t(tx, "transactionAmounts/transactionAcquiredDisposedCode/value"),
                     "shares": _f(tx, "transactionAmounts/transactionShares/value"),
                     "price": _f(tx, "transactionAmounts/transactionPricePerShare/value"),
                     "shares_after": _f(tx, "postTransactionAmounts/"
                                            "sharesOwnedFollowingTransaction/value")})
    return rows


# ---------------------------------------------------------------- state

def _load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _ledger(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or TXNS
    out = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return out


def build_clusters(rows: list[dict[str, Any]], now: datetime) -> tuple[list[dict[str, Any]],
                                                                        dict[str, Any]]:
    from libs.research import form4

    cut = now - timedelta(days=CLUSTER_LOOKBACK_DAYS)
    txns = []
    for r in rows:
        try:
            filed = datetime.fromisoformat(r["filed_at"])
            if filed < cut:
                continue
            txns.append(form4.Form4Txn(
                issuer=str(r["symbol"]), insider=str(r["insider"]), title=str(r["title"]),
                txn_date=datetime.fromisoformat(r["txn_date"]), filed_at=filed,
                code=str(r["code"]), shares=float(r["shares"]), price=float(r["price"]),
                shares_after=float(r.get("shares_after") or 0.0)))
        except (KeyError, TypeError, ValueError):
            continue
    cs = form4.clusters(txns)
    return form4.as_events(cs), form4.census(txns)


def run(budget_s: float = DEFAULT_BUDGET_S, fetch: Fetch | None = None,
        today: date | None = None, symbols: list[str] | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    now = _now()
    today = today or now.date()
    ua = user_agent()
    doc: dict[str, Any] = {"at": now.isoformat(timespec="seconds"), "source": SEC,
                           "consumer": ("data/form4/insider_clusters.json: INSIDER_CLUSTER "
                                        "events, `at` = knowable_at, the input shape of "
                                        "mt5desk/family_event_reaction (event lane only)")}
    if fetch is None:
        if not ua:
            doc.update({"status": "UNMEASURED",
                        "why": "no QUANT_EDGAR_UA: the SEC's fair-access policy requires a "
                               "declared User-Agent naming a contact; nothing was fetched"})
            return _publish(doc, now)
        fetch = Fetcher(ua)
    ok, why = robots_allows(ua or "*", ["/Archives/edgar/daily-index/", "/files/"], fetch)
    if not ok:
        doc.update({"status": "REFUSED", "why": f"robots.txt: {why}"})
        return _publish(doc, now)

    DATA.mkdir(parents=True, exist_ok=True)
    tick = _load(TICKERS_CACHE, {})
    fresh = TICKERS_CACHE.exists() and time.time() - TICKERS_CACHE.stat().st_mtime < \
        TICKERS_MAX_AGE_S
    if not fresh:
        raw = fetch(TICKERS_URL)
        if raw:
            tick = json.loads(raw.decode("utf-8"))
            TICKERS_CACHE.write_text(json.dumps(tick), encoding="utf-8")
    syms = symbols if symbols is not None else equity_symbols()
    ciks, unmapped = issuer_map(syms, tick)

    ledger = _ledger()
    seen = {r.get("file") for r in ledger}
    cur = _load(CURSOR, {})
    try:
        day = date.fromisoformat(str(cur.get("last_day"))) + timedelta(days=1)
    except ValueError:
        day = today - timedelta(days=BACKFILL_DAYS)
    day = max(day, today - timedelta(days=BACKFILL_DAYS))
    new_rows: list[dict[str, Any]] = []
    days_done, filings, out_of_time = 0, 0, False
    last_done: date | None = None
    while day <= today and not out_of_time:
        q = (day.month - 1) // 3 + 1
        raw = fetch(f"{SEC}/Archives/edgar/daily-index/{day.year}/QTR{q}/"
                    f"form.{day:%Y%m%d}.idx")
        rows = parse_index(raw.decode("latin-1")) if raw else []
        complete = True
        for r in rows:
            if r["cik"] not in ciks or r["file"] in seen:
                continue
            if time.monotonic() - t0 > budget_s:
                complete, out_of_time = False, True
                break
            body = fetch(f"{SEC}/Archives/{r['file']}")
            filings += 1
            seen.add(r["file"])
            for tx in parse_filing(body.decode("utf-8", "replace") if body else ""):
                for sym in ciks.get(tx["issuer_cik"], ciks[r["cik"]]):
                    new_rows.append({**tx, "symbol": sym, "file": r["file"]})
        # Today's index is still growing; only a PAST day that was fully walked advances the cursor.
        if complete and day < today:
            last_done = day
            days_done += 1
        if complete:
            day += timedelta(days=1)
    if new_rows:
        with TXNS.open("a", encoding="utf-8") as fh:
            for r in new_rows:
                fh.write(json.dumps(r) + "\n")
    if last_done is not None:
        CURSOR.write_text(json.dumps({"last_day": last_done.isoformat(),
                                      "at": now.isoformat()}), encoding="utf-8")
    events, census = build_clusters(ledger + new_rows, now)
    CLUSTERS.write_text(json.dumps({"at": now.isoformat(timespec="seconds"),
                                    "events": events}, indent=1), encoding="utf-8")
    doc.update({"status": "MEASURED", "why": None,
                "equity_symbols": len(syms), "issuers_mapped": len(ciks),
                "unmapped_symbols": len(unmapped), "unmapped_sample": unmapped[:20],
                "index_days_completed": days_done, "filings_fetched": filings,
                "requests": getattr(fetch, "n", None),
                "fetch_errors": list(getattr(fetch, "errors", []))[:10],
                "new_transactions": len(new_rows), "ledger_transactions": len(ledger) +
                len(new_rows), "clusters": len(events), "top_clusters": events[:10],
                "census": census, "cursor_day": (last_done.isoformat() if last_done
                                                 else cur.get("last_day")),
                "budget_exhausted": out_of_time})
    return _publish(doc, now)


def _publish(doc: dict[str, Any], now: datetime) -> dict[str, Any]:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    a = ap.parse_args(argv)
    try:
        doc = run(budget_s=a.budget_s)
    except Exception as exc:  # a network fault is a verdict on this pass, never a crash
        doc = _publish({"at": _now().isoformat(timespec="seconds"), "status": "UNMEASURED",
                        "why": f"pass failed: {type(exc).__name__}: {exc}"[:300]}, _now())
    print(f"FORM4  {doc.get('at')}  status={doc.get('status')}  "
          f"filings={doc.get('filings_fetched')}  clusters={doc.get('clusters')}  -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
