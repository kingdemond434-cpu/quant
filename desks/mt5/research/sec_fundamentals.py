#!/usr/bin/env python3
"""REFRESH POINT-IN-TIME FUNDAMENTALS FOR EVERY SHARE CFD FROM SEC EDGAR, AND SAY WHAT IS COVERED.

    python desks/mt5/research/sec_fundamentals.py --once --budget-s 600
    python desks/mt5/research/sec_fundamentals.py --once --fixtures <dir>   # offline, recorded

WHY. The desk quotes 103 single-name share CFDs and held no fundamentals for any of them
(reports/asia_quant_gap_2026-09-30.md row 9), so no quantamental book could exist. This leg builds
the dataset `mt5desk/families_quantamental.py` ranks on.

SOURCES, FREE AND MACHINE-USE-ALLOWED. SEC EDGAR only, keyless:
  * https://www.sec.gov/files/company_tickers.json          ticker -> CIK (weekly)
  * https://data.sec.gov/submissions/CIK##########.json     filings list + acceptance times
  * https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json   every XBRL fact filed
  * https://www.sec.gov/Archives/edgar/cik-lookup-data.txt   every entity name EDGAR knows,
    including issuers that no longer trade (read once, only to resolve DELISTED_ISSUERS' CIKs)
The SEC's fair-access policy asks for a User-Agent NAMING THE REQUESTER and at most 10 requests
a second. The UA is read from the environment, first set wins: QUANT_EDGAR_UA,
SEC_EDGAR_USER_AGENT, SEC_EDGAR_UA. WHEN NONE IS SET THE LEG SENDS NOTHING: the pass is
UNMEASURED with the reason named, previous snapshots stand, and no placeholder identity ever
reaches the SEC. The value itself is never printed or written -- only the variable's NAME is.
Requests are spaced REQUEST_GAP_S apart.

SURVIVORSHIP. The registry is today's survivors. `universe_policy.DELISTED_ISSUERS` names issuers
that were acquired or taken private; their CIKs are resolved from EDGAR's own entity list (a name
that does not resolve to exactly one CIK is reported, never guessed), their fundamentals are built
like any other name's, and the filing history's Form 25 / 15 dates when each stopped trading.
They join the class books' RANKING HISTORY and are never placed. Every ticker the SEC list has
ever shown is also remembered (`ticker_history.json`), so a registry name whose ticker leaves the
current list (Walgreens, taken private 2025) still resolves by its CIK.

WHAT A PASS DOES.
  1. Map every share CFD in the broker registry (`universe_policy.is_equity`) to its US ticker
     (`ISSUER_TICKERS`, identity data, since the broker spells names not tickers) and the ticker
     to a CIK. A name with no ticker, or a ticker the SEC does not list, is REPORTED.
  2. Stalest first, within the budget: fetch `submissions`; if the newest periodic filing's
     accession is the one already built, the name is fresh and nothing else is fetched. Otherwise
     fetch `companyfacts` and rebuild that name's point-in-time snapshots
     (`fundamentals_pit.build_snapshots`: each value stamped with its ACCEPTANCE time, never its
     period end).
  3. Write `data/lake/fundamentals/sec_pit.parquet` (+ `.pit.json` sidecar) and
     `reports/FUNDAMENTALS_COVERAGE.json`: names covered, fields present per name, staleness,
     the reason each uncovered name is uncovered, and the current P/E, P/B, EV/Sales and earnings
     yield against the bar store's last close.

A NETWORK REFUSAL IS UNMEASURED, NEVER ZERO. A 403 from the proxy or the SEC leaves every name's
previous snapshots in place and is reported per name with the status code.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = Path(__file__).resolve().parent.parent          # desks/mt5
ROOT = BASE.parent.parent
for _p in (str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from mt5desk import fundamentals_pit as fp  # noqa: E402

LAKE = BASE / "data" / "lake" / "fundamentals"
STATE = LAKE / "sec_state.json"
TICKERS_CACHE = LAKE / "company_tickers.json"
OUT = BASE / "reports" / "FUNDAMENTALS_COVERAGE.json"
#: The ALLOCATION use of the dataset: each class's valuation/quality state and its daily history.
VALUATION_STATE = BASE / "reports" / "SECTOR_VALUATION_STATE.json"
#: Daily rows of regime history the state artifact carries (a rank window for a consumer).
STATE_HISTORY_D = 500
UNIVERSE_DIR = BASE / "data" / "universe"
UNMEASURED = "UNMEASURED"

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
CIK_LOOKUP_URL = "https://www.sec.gov/Archives/edgar/cik-lookup-data.txt"
#: Environment variables that may carry the EDGAR User-Agent, first set wins. Names only: the
#: value is never logged, printed or written to an artifact.
UA_ENV_VARS = ("QUANT_EDGAR_UA", "SEC_EDGAR_USER_AGENT", "SEC_EDGAR_UA")
#: Every ticker -> CIK the SEC list has ever shown on this host (LAKE/ticker_history.json), and
#: the delisted issuers' resolved CIKs (LAKE/delisted_ciks.json). Read through LAKE at call time.
TICKER_HISTORY_NAME = "ticker_history.json"
DELISTED_CIKS_NAME = "delisted_ciks.json"
#: An unresolved delisted issuer is looked up again after this long.
DELISTED_RETRY_S = 7 * 86400
#: Forms that end an issuer's listing or registration: the filing history's own delisting date.
DELISTING_FORMS = frozenset({"25", "25-NSE", "15-12B", "15-12G", "15-15D", "15-12B/A",
                             "15-12G/A", "15-15D/A"})
REQUEST_GAP_S = 0.15            # under the SEC's 10 requests a second
TICKERS_MAX_AGE_S = 7 * 86400
#: A name is re-checked at most once in this window; the leg runs hourly, so every name is
#: checked about daily and a new 10-Q lands in the table within a day of acceptance.
RECHECK_S = 20 * 3600
PERIODIC_FORMS = frozenset({"10-K", "10-Q", "10-K/A", "10-Q/A", "20-F", "20-F/A", "40-F",
                            "40-F/A", "10-KT"})

#: Broker share-CFD name -> US ticker. IDENTITY DATA, not a routing decision: the broker spells a
#: company, the SEC keys it by ticker, and nothing derives one from the other reliably ("Snapchat"
#: is SNAP, "Pepsi" is PEP). A registry equity missing here is reported as `no_ticker_mapping`.
ISSUER_TICKERS: dict[str, str] = {
    "3M": "MMM", "ADP": "ADP", "AMD": "AMD", "AT&T": "T", "Accenture": "ACN", "Adobe": "ADBE",
    "Airbnb": "ABNB", "AlibabaGroup": "BABA", "Alphabet-A": "GOOGL", "Alphabet-C": "GOOG",
    "Amazon": "AMZN", "AmericanExpress": "AXP", "Amgen": "AMGN", "Apple": "AAPL",
    "AppliedMaterials": "AMAT", "Atlassian": "TEAM", "Baidu": "BIDU",
    "BankofAmericaCorp": "BAC", "Berkshire": "BRK-B", "BlackRock": "BLK", "Boeing": "BA",
    "Booking": "BKNG", "Broadcom": "AVGO", "CVSHealth": "CVS", "Caterpillar": "CAT",
    "CharlesSchwab": "SCHW", "Charter": "CHTR", "Chevron": "CVX", "Cisco": "CSCO",
    "Citigroup": "C", "Coca-Cola": "KO", "Coinbase": "COIN", "Comcast": "CMCSA",
    "CostcoWholesale": "COST", "DocuSign": "DOCU", "Doordash": "DASH", "Dow": "DOW",
    "ElectronicArts": "EA", "ExxonMobil": "XOM", "Ford": "F", "GeneralElectric": "GE",
    "GeneralMotors": "GM", "GileadSciences": "GILD", "GoldmanSachs": "GS", "HomeDepot": "HD",
    "Honeywell": "HON", "IBM": "IBM", "Intel": "INTC", "Intuit": "INTU",
    "IntuitiveSurgical": "ISRG", "JPMorganChase": "JPM", "Johnson&Johnson": "JNJ",
    "LucidGroup": "LCID", "Lyft": "LYFT", "Mastercard": "MA", "McDonalds": "MCD",
    "Medtronic": "MDT", "Merck": "MRK", "Meta": "META", "MicronTechnology": "MU",
    "Microsoft": "MSFT", "MorganStanley": "MS", "NIO": "NIO", "NVIDIA": "NVDA",
    "Netflix": "NFLX", "Nike": "NKE", "Oracle": "ORCL", "PayPal": "PYPL", "Pepsi": "PEP",
    "Pfizer": "PFE", "PhilipMorrisInternational": "PM", "Pinterest": "PINS",
    "Procter&Gamble": "PG", "Qualcomm": "QCOM", "RobinhoodMarkets": "HOOD", "Roku": "ROKU",
    "S&PGlobal": "SPGI", "Salesforce": "CRM", "ServiceNow": "NOW", "Shopify": "SHOP",
    "Snapchat": "SNAP", "Snowflake": "SNOW", "Spotify": "SPOT", "Starbucks": "SBUX",
    "TMEGroup": "TME", "TSMC": "TSM", "Target": "TGT", "Tesla": "TSLA",
    "TexasInstruments": "TXN", "ThermoFisherScientific": "TMO", "Toyota": "TM",
    "Travelers": "TRV", "Twilio": "TWLO", "Uber": "UBER", "UnionPacific": "UNP",
    "UnitedHealth": "UNH", "UnitedParcelService": "UPS", "Verizon": "VZ", "Visa": "V",
    "Walmart": "WMT", "WaltDisney": "DIS", "WellsFargo": "WFC", "eBay": "EBAY",
    # registry rows with no asset_class of their own, classified as share CFDs by the pattern
    # classifier (universe_policy.asset_class_of). Block trades as XYZ since 2025-01; Walgreens
    # went private in 2025, so the SEC list may no longer carry WBA -- reported, never guessed.
    "BEYONDMEAT": "BYND", "BLOCKINC": "XYZ", "WALGREENS": "WBA",
}

#: Names whose per-share facts do not describe the share the CFD quotes, so their price ratios
#: would be wrong by a constant. Reported and excluded from the panel, never silently used.
PER_SHARE_MISMATCH = {
    "Berkshire": "per-share facts are per class A share while the CFD quotes class B (1:1500)",
}


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(path)


# ------------------------------------------------------------------------------ the network ---
Fetcher = Callable[[str], tuple[int, Any]]


LineFetcher = Callable[[str], tuple[int, Iterable[str]]]


def edgar_user_agent() -> tuple[str | None, str | None]:
    """(value, the NAME of the variable it came from), or (None, None) when none is set.
    Callers report the name only; the value never leaves this process except as the header."""
    for name in UA_ENV_VARS:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value, name
    return None, None


def http_fetcher(ua: str) -> Fetcher:
    """GET a JSON document from the SEC: (status, parsed or None). Never raises."""
    last = [0.0]

    def fetch(url: str) -> tuple[int, Any]:
        gap = REQUEST_GAP_S - (time.monotonic() - last[0])
        if gap > 0:
            time.sleep(gap)
        last[0] = time.monotonic()
        req = Request(url, headers={"User-Agent": ua, "Accept": "application/json",
                                    "Accept-Encoding": "gzip"})
        try:
            with urlopen(req, timeout=30) as resp:
                body = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                return int(resp.status), json.loads(body.decode("utf-8"))
        except HTTPError as exc:
            return int(exc.code), None
        except (URLError, TimeoutError, OSError, ValueError):
            return 0, None
    return fetch


def http_lines(ua: str) -> LineFetcher:
    """Stream a text document from the SEC line by line: (status, lines). Never raises; a failed
    request answers (code, [])."""
    def fetch(url: str) -> tuple[int, Iterable[str]]:
        req = Request(url, headers={"User-Agent": ua, "Accept": "text/plain"})
        try:
            resp = urlopen(req, timeout=120)
        except HTTPError as exc:
            return int(exc.code), []
        except (URLError, TimeoutError, OSError, ValueError):
            return 0, []

        def lines() -> Iterator[str]:
            with resp:
                for raw in resp:
                    yield raw.decode("latin-1", "replace")
        return int(resp.status), lines()
    return fetch


def fixture_lines(directory: Path) -> LineFetcher:
    """Recorded text documents by the URL's last segment; a missing file answers 404."""
    def fetch(url: str) -> tuple[int, Iterable[str]]:
        path = Path(directory) / url.rsplit("/", 1)[-1]
        try:
            return 200, path.read_text("latin-1").splitlines()
        except OSError:
            return 404, []
    return fetch


def fixture_fetcher(directory: Path) -> Fetcher:
    """Recorded SEC documents: company_tickers.json, submissions_CIK##########.json and
    companyfacts_CIK##########.json. A missing file answers 404."""
    def fetch(url: str) -> tuple[int, Any]:
        name = url.rsplit("/", 1)[-1]
        if "/submissions/" in url:
            name = "submissions_" + name
        elif "/companyfacts/" in url:
            name = "companyfacts_" + name
        doc = _read(Path(directory) / name)
        return (200, doc) if doc is not None else (404, None)
    return fetch


# ---------------------------------------------------------------------------- the universe ---
def registry_equities() -> list[str]:
    """Every share CFD in the broker registry, in the registry's casing."""
    from research import universe_policy as up
    return sorted(str(v.get("symbol") or k) for k, v in up._registry().items()
                  if up.is_equity(k))


def ticker_to_cik(fetch: Fetcher, now: datetime) -> tuple[dict[str, int], str]:
    doc = _read(TICKERS_CACHE)
    try:
        fresh = (now.timestamp() - TICKERS_CACHE.stat().st_mtime) < TICKERS_MAX_AGE_S
    except OSError:
        fresh = False
    status = "cached"
    if not (isinstance(doc, dict) and fresh):
        code, got = fetch(TICKERS_URL)
        if code == 200 and isinstance(got, dict):
            doc, status = got, "fetched"
            _write_json(TICKERS_CACHE, got)
        else:
            status = f"fetch failed ({code}); {'stale cache' if doc else 'no cache'}"
    out: dict[str, int] = {}
    for row in (doc or {}).values() if isinstance(doc, dict) else []:
        if isinstance(row, dict) and row.get("ticker") and row.get("cik_str") is not None:
            out.setdefault(str(row["ticker"]).upper(), int(row["cik_str"]))
    _remember_tickers(out, now)
    return out, status


def _remember_tickers(current: dict[str, int], now: datetime) -> None:
    """Accumulate every ticker -> CIK the SEC list has shown, so a name that LEAVES the list (a
    delisting, a take-private) still resolves by the CIK it filed under."""
    if not current:
        return
    hist = _read(LAKE / TICKER_HISTORY_NAME)
    hist = hist if isinstance(hist, dict) else {}
    stamp = now.isoformat(timespec="seconds")
    for ticker, cik in current.items():
        row = hist.get(ticker) if isinstance(hist.get(ticker), dict) else {}
        hist[ticker] = {"cik": int(cik), "first_seen": row.get("first_seen") or stamp,
                        "last_seen": stamp}
    _write_json(LAKE / TICKER_HISTORY_NAME, hist)


def ticker_history() -> dict[str, int]:
    hist = _read(LAKE / TICKER_HISTORY_NAME)
    return {str(k).upper(): int(v["cik"]) for k, v in (hist or {}).items()
            if isinstance(v, dict) and v.get("cik") is not None} if isinstance(hist, dict) else {}


def _norm_name(name: str) -> str:
    """EDGAR conformed name, normalised: upper case, a trailing /XX/ state tag dropped,
    punctuation removed, spaces collapsed ("MONSANTO CO /NEW/" -> "MONSANTO CO")."""
    s = str(name).upper().strip()
    while s.endswith("/"):
        cut = s.rfind("/", 0, len(s) - 1)
        if cut < 0:
            break
        s = s[:cut].strip()
    s = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in s)
    return " ".join(s.split())


def resolve_delisted(lines: LineFetcher | None, now: datetime) -> dict[str, Any]:
    """{issuer: {"cik": int} | {"status": "ambiguous"|"absent"|"UNMEASURED ...", ...}} for every
    `universe_policy.DELISTED_ISSUERS` entry, from EDGAR's entity list. Resolved CIKs are kept
    forever (a CIK never changes); an unresolved one is retried after DELISTED_RETRY_S."""
    from research import universe_policy as up
    cache = _read(LAKE / DELISTED_CIKS_NAME)
    cache = cache if isinstance(cache, dict) else {}
    want: dict[str, set[str]] = {}
    for issuer, spec in up.DELISTED_ISSUERS.items():
        row = cache.get(issuer) if isinstance(cache.get(issuer), dict) else {}
        if row.get("cik") is not None:
            continue
        tried = row.get("tried_at")
        if tried and (now - datetime.fromisoformat(tried)).total_seconds() < DELISTED_RETRY_S:
            continue
        want[issuer] = {_norm_name(n) for n in spec.get("edgar_names") or ()}
    if not want:
        return cache
    stamp = now.isoformat(timespec="seconds")
    if lines is None:
        for issuer in want:
            cache[issuer] = {"status": "UNMEASURED: no EDGAR entity list this pass",
                             "tried_at": stamp}
        return cache
    code, body = lines(CIK_LOOKUP_URL)
    if code != 200:
        for issuer in want:
            cache[issuer] = {"status": f"UNMEASURED: entity list HTTP {code}", "tried_at": stamp}
        _write_json(LAKE / DELISTED_CIKS_NAME, cache)
        return cache
    by_name: dict[str, set[str]] = {}
    for n in set().union(*want.values()):
        by_name[n] = set()
    for line in body:
        parts = line.rstrip("\r\n").rsplit(":", 2)
        if len(parts) < 3 or not parts[1].strip().isdigit():
            continue
        key = _norm_name(parts[0])
        if key in by_name:
            by_name[key].add(parts[1].strip())
    for issuer, names in want.items():
        ciks = sorted(set().union(*(by_name.get(n, set()) for n in names)))
        if len(ciks) == 1:
            cache[issuer] = {"cik": int(ciks[0]), "resolved_at": stamp,
                             "matched": sorted(names)}
        elif ciks:
            cache[issuer] = {"status": "ambiguous", "candidates": [int(c) for c in ciks],
                             "tried_at": stamp}
        else:
            cache[issuer] = {"status": "absent", "tried_at": stamp}
    _write_json(LAKE / DELISTED_CIKS_NAME, cache)
    return cache


def delisting_date(submissions: dict | None) -> str | None:
    """The filing history's own delisting date: the latest Form 25 / 15 filing date, or None."""
    recent = ((submissions or {}).get("filings") or {}).get("recent") or {}
    dates = [str(d) for f, d in zip(recent.get("form") or [], recent.get("filingDate") or [],
                                    strict=False) if str(f) in DELISTING_FORMS]
    return max(dates) if dates else None


def newest_periodic(submissions: dict | None) -> str | None:
    recent = ((submissions or {}).get("filings") or {}).get("recent") or {}
    for form, accn in zip(recent.get("form") or [], recent.get("accessionNumber") or [],
                          strict=False):
        if str(form) in PERIODIC_FORMS:
            return str(accn)
    return None


# -------------------------------------------------------------------------------- the pass ---
def refresh(*, fetch: Fetcher, budget_s: float = 600.0, force: bool = False,
            symbols: list[str] | None = None, lines: LineFetcher | None = None,
            ua_source: str | None = None) -> dict[str, Any]:
    started = time.monotonic()
    now = _now()
    state = _read(STATE)
    names: dict[str, Any] = (state or {}).get("names") if isinstance(state, dict) else None
    names = names if isinstance(names, dict) else {}
    table = fp.read_table()
    frames: dict[str, pd.DataFrame] = {
        str(s): g.drop(columns=["symbol"]) for s, g in table.groupby("symbol", sort=False)
    } if len(table) else {}
    from research import universe_policy as up
    equities = symbols or registry_equities()
    ciks, tick_status = ticker_to_cik(fetch, now)
    remembered = ticker_history()
    delisted = resolve_delisted(lines, now)
    targets = [*equities, *(d for d in up.DELISTED_ISSUERS if d not in equities)]
    order = sorted(targets, key=lambda s: str((names.get(s) or {}).get("checked_at") or ""))
    touched = rebuilt = 0
    stopped = "all names visited"
    for sym in order:
        row = dict(names.get(sym) or {})
        if sym in up.DELISTED_ISSUERS:
            spec = up.DELISTED_ISSUERS[sym]
            res = delisted.get(sym) if isinstance(delisted.get(sym), dict) else {}
            row.update(ticker=spec.get("ticker"), delisted=True, tradable_now=False,
                       ended=spec.get("why"))
            cik = res.get("cik")
            if cik is None:
                row["status"] = f"cik_unresolved: {res.get('status') or UNMEASURED}"
                if res.get("candidates"):
                    row["candidates"] = res["candidates"]
                names[sym] = row
                continue
        else:
            ticker = ISSUER_TICKERS.get(sym)
            row["ticker"] = ticker
            if ticker is None:
                row["status"] = "no_ticker_mapping"
                names[sym] = row
                continue
            cik = ciks.get(ticker.upper())
            row["ticker_in_sec_list"] = cik is not None if ciks else UNMEASURED
            if cik is None:
                cik = remembered.get(ticker.upper())
            if cik is None:
                row["status"] = ("ticker_not_in_sec_list" if ciks
                                 else f"UNMEASURED: SEC ticker list unavailable ({tick_status})")
                names[sym] = row
                continue
        row["cik"] = cik
        last = row.get("checked_at")
        if not force and last and (now - datetime.fromisoformat(last)).total_seconds() < RECHECK_S:
            names[sym] = row
            continue
        if time.monotonic() - started > budget_s:
            stopped = f"time budget {budget_s:g}s reached; resumes stalest-first next pass"
            break
        touched += 1
        code, subs = fetch(SUBMISSIONS_URL.format(cik=cik))
        if code != 200 or not isinstance(subs, dict):
            row["status"] = f"UNMEASURED: submissions HTTP {code}"
            row["checked_at"] = now.isoformat(timespec="seconds")
            names[sym] = row
            continue
        newest = newest_periodic(subs)
        row["delisting_filed"] = delisting_date(subs)
        if newest and newest == row.get("built_from") and sym in frames and not force:
            row.update(status="fresh", checked_at=now.isoformat(timespec="seconds"))
            names[sym] = row
            continue
        code, facts = fetch(FACTS_URL.format(cik=cik))
        row["checked_at"] = now.isoformat(timespec="seconds")
        if code != 200 or not isinstance(facts, dict):
            row["status"] = f"UNMEASURED: companyfacts HTTP {code}"
            names[sym] = row
            continue
        snaps = fp.build_snapshots(facts, subs)
        if sym in PER_SHARE_MISMATCH:
            row["status"] = "excluded: " + PER_SHARE_MISMATCH[sym]
            frames.pop(sym, None)
        elif not len(snaps):
            row["status"] = "no_usd_facts (foreign-currency filer or no XBRL)"
            frames.pop(sym, None)
        else:
            frames[sym] = snaps
            row["status"] = "covered"
            rebuilt += 1
        row["built_from"] = newest
        row["entity"] = facts.get("entityName")
        names[sym] = row
    fp.write_table(sorted(frames.items()))
    _write_json(fp.PIT_PATH.with_suffix(".pit.json"), {
        "source": "SEC EDGAR XBRL companyfacts + submissions",
        "captured_at": now.isoformat(timespec="seconds"),
        "row_time": "available (UTC): the SEC acceptance time of the filing carrying the value, "
                    "read as Eastern at +5h; filed date + 1 day 06:00 UTC when not in the "
                    "submissions list. NEVER the period end.",
        "fields": list(fp.FIELDS)})
    _write_json(STATE, {"updated": now.isoformat(timespec="seconds"), "names": names})
    return {"status": "OK", "elapsed_s": round(time.monotonic() - started, 2),
            "stopped_because": stopped, "names_fetched_this_pass": touched,
            "names_rebuilt_this_pass": rebuilt, "ticker_list": tick_status,
            "user_agent_source": ua_source or "fixture fetcher (no network)"}


# ---------------------------------------------------------------------------- the coverage ---
def _last_close(symbol: str) -> tuple[float, int] | None:
    path = UNIVERSE_DIR / f"{symbol}_H1.parquet"
    try:
        frame = pd.read_parquet(path, columns=["close"])
    except Exception:
        try:
            frame = pd.read_parquet(path)
        except Exception:
            return None
    if not len(frame) or "close" not in frame.columns:
        return None
    idx = frame.index
    if not isinstance(idx, pd.DatetimeIndex):
        return None
    idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    return float(frame["close"].iloc[-1]), int(idx[-1].value)


def _culture(symbol: str) -> dict[str, str]:
    """The name's culture provenance, from the class-book producer's one rule (principal
    2026-09-30 14:18: every row carries source_culture / participant_structure /
    failure_mode_hypothesis)."""
    try:
        from research.cross_sectional_breadth import culture
        return culture(symbol, "equity", "quantamental_value")
    except Exception:
        return {"source_culture": UNMEASURED, "participant_structure": UNMEASURED,
                "failure_mode_hypothesis": UNMEASURED}


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(BASE))
    except ValueError:
        return str(path)


def coverage(pass_doc: dict[str, Any]) -> dict[str, Any]:
    now = _now()
    state = _read(STATE) or {}
    names = state.get("names") or {}
    table = fp.read_table()
    equities = registry_equities()
    per_name: dict[str, Any] = {}
    field_counts = dict.fromkeys(fp.FIELDS, 0)
    covered = 0
    for sym in equities:
        row = names.get(sym) or {}
        snaps = table[table["symbol"] == sym] if len(table) else table
        entry: dict[str, Any] = {"ticker": ISSUER_TICKERS.get(sym),
                                 "status": row.get("status") or UNMEASURED,
                                 "checked_at": row.get("checked_at"),
                                 **_culture(sym)}
        if len(snaps):
            covered += 1
            last = snaps.sort_values("available").iloc[-1]
            av = pd.Timestamp(last["available"])
            av = av.tz_localize("UTC") if av.tzinfo is None else av.tz_convert("UTC")
            present = [f for f in fp.FIELDS if pd.notna(last.get(f))]
            for f in present:
                field_counts[f] += 1
            entry.update(snapshots=len(snaps),
                         last_available=av.isoformat(),
                         last_period_end=str(last.get("period_end")),
                         staleness_days=round((now - av.to_pydatetime()).total_seconds() / 86400,
                                              1),
                         fields_present=present,
                         fields_missing=[f for f in fp.FIELDS if f not in present])
            close = _last_close(sym)
            if close is None:
                entry["valuation_now"] = {"status": UNMEASURED, "why": "no bars in the store"}
            else:
                v = fp.valuation(sym, np.array([close[1]]), np.array([close[0]]))
                entry["valuation_now"] = {k: (round(float(a[0]), 6)
                                              if np.isfinite(a[0]) else None)
                                          for k, a in v.items()}
                entry["valuation_now"]["price"] = close[0]
        per_name[sym] = entry
    from research import universe_policy as up
    survivors: dict[str, Any] = {}
    for sym, spec in up.DELISTED_ISSUERS.items():
        row = names.get(sym) or {}
        snaps = table[table["symbol"] == sym] if len(table) else table
        has_bars = _last_close(sym) is not None
        survivors[sym] = {
            "former_ticker": spec.get("ticker"), "ended": spec.get("why"),
            "classes": list(spec.get("classes") or ()), "tradable_now": False,
            "cik": row.get("cik"), "status": row.get("status") or UNMEASURED,
            "delisting_filed": row.get("delisting_filed"),
            "snapshots": len(snaps),
            "last_available": (str(pd.Timestamp(snaps["available"].max()))
                               if len(snaps) else None),
            "in_ranking_history": {
                "price_free_ranks": bool(len(snaps)),
                "price_ranks": has_bars or ("UNMEASURED: no bars in the store, so the price "
                                            "and price-ratio ranks cannot include it")}}
    uncovered: dict[str, list[str]] = {}
    for sym, e in per_name.items():
        if "snapshots" not in e:
            uncovered.setdefault(str(e["status"]), []).append(sym)
    return {
        "at": now.isoformat(timespec="seconds"),
        "organ": "desks/mt5/research/sec_fundamentals.py",
        "dataset": _rel(fp.PIT_PATH),
        "rule": ("every value is stamped with the SEC acceptance time of the filing that carried "
                 "it, never the period end; ratios are computed against the bar store's close at "
                 "the decision bar; foreign-currency filers are uncovered, never converted"),
        "names_in_registry": len(equities),
        "names_covered": covered,
        "names_uncovered": len(equities) - covered,
        "uncovered_by_reason": {k: sorted(v) for k, v in sorted(uncovered.items())},
        "names_with_field": field_counts,
        "pass": pass_doc,
        "per_name": per_name,
        "survivorship": {
            "rule": ("delisted issuers (universe_policy.DELISTED_ISSUERS) join the class books' "
                     "RANKING HISTORY on the dates their filings were live and are NEVER placed; "
                     "a CIK is resolved from EDGAR's entity list or reported, never guessed"),
            "declared": len(survivors),
            "resolved": sum(1 for v in survivors.values() if v["cik"] is not None),
            "with_fundamentals": sum(1 for v in survivors.values() if v["snapshots"]),
            "issuers": survivors},
        "consumer": ("mt5desk/families_quantamental.py (quantamental_value, quantamental_quality, "
                     "quantamental_earnings_yield) -> research/cross_sectional_breadth.py -> the "
                     "docket -> scripts/external_gauntlet.py"),
    }


def valuation_state() -> dict[str, Any]:
    """The allocation-state artifact: every regime `mt5desk.valuation_regime` defines, measured
    on weekday 22:00 bar stamps (broker clock) over the store -- its level now, percentile in its
    own history, the state a conditioned cell reads, and the daily level and trailing percentile
    rank (the shape `libs/portfolio/macro_state` ranks its FRED dimensions in)."""
    from mt5desk import valuation_regime as vr
    stamps = vr.daily_stamps(days=int(STATE_HISTORY_D * 1.5) + 400)
    regimes = vr.state_now(stamps)
    history: dict[str, list[dict[str, Any]]] = {}
    for regime in vr.REGIMES:
        level = pd.Series(vr.regime_level(regime, stamps),
                          index=pd.DatetimeIndex(stamps, tz="UTC").strftime("%Y-%m-%d"))
        rank = level.rolling(250, min_periods=60).apply(
            lambda w: float((w <= w[-1]).mean()), raw=True)
        tail = pd.DataFrame({"level": level, "rank": rank}).dropna(subset=["level"]).tail(
            STATE_HISTORY_D)
        history[regime] = [{"date": d, "level": round(float(lv), 6),
                            "rank": (None if pd.isna(rk) else round(float(rk), 4))}
                           for d, lv, rk in zip(tail.index, tail["level"], tail["rank"],
                                                strict=True)]
    return {
        "at": _now().isoformat(timespec="seconds"),
        "organ": "desks/mt5/research/sec_fundamentals.py (valuation_state)",
        "rule": ("levels use fundamentals ACCEPTED by each stamp and the bar store's close at it; "
                 "a state compares the PREVIOUS day's level with its trailing median; a regime "
                 "with fewer than 5 covered members is UNMEASURED, never neutral"),
        "regimes": regimes,
        "history": history,
        "uses": {
            "direct": ["mt5desk/families_quantamental.py", "mt5desk/families_sector.py"],
            "indirect": ["mt5desk/valuation_regime.py family_valuation_regime_conditioned "
                         "(equity, index and semis class-book legs)"],
            "allocation": ["this artifact; consumer patch for libs/portfolio/macro_state.py "
                           "(money path, not applied here): "
                           "/mnt/project-files/patches/sector_valuation_state/"]},
    }


def run(*, fetch: Fetcher | None = None, budget_s: float = 600.0, force: bool = False,
        symbols: list[str] | None = None, out: Path | None = None,
        lines: LineFetcher | None = None) -> dict[str, Any]:
    ua_source: str | None = None
    if fetch is None:
        ua, ua_source = edgar_user_agent()
        if ua is None:
            pass_doc: dict[str, Any] = {
                "status": UNMEASURED, "blocked": True,
                "why": ("no EDGAR User-Agent: set one of " + ", ".join(UA_ENV_VARS) + " to a "
                        "string naming the requester (the SEC fair-access policy). Nothing was "
                        "sent; previous snapshots stand."),
                "user_agent_source": None}
            fetch = None
        else:
            fetch, lines = http_fetcher(ua), (lines or http_lines(ua))
    if fetch is not None:
        try:
            pass_doc = refresh(fetch=fetch, budget_s=budget_s, force=force, symbols=symbols,
                               lines=lines, ua_source=ua_source)
        except Exception as exc:                      # the coverage artifact is still written
            pass_doc = {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"[:300]}
    doc = coverage(pass_doc)
    try:
        state = valuation_state()
    except Exception as exc:
        state = {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"[:300]}
    _write_json(VALUATION_STATE, state)
    doc["valuation_state"] = {k: (v.get("state_next") if isinstance(v, dict) else v)
                              for k, v in (state.get("regimes") or {}).items()}
    _write_json(out or OUT, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true", help="one pass (the scheduled form)")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--force", action="store_true", help="refetch every name now")
    ap.add_argument("--fixtures", type=Path, default=None, help="recorded SEC documents")
    ap.add_argument("--symbols", nargs="*", default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    fetch = fixture_fetcher(args.fixtures) if args.fixtures else None
    lines = fixture_lines(args.fixtures) if args.fixtures else None
    doc = run(fetch=fetch, budget_s=args.budget_s, force=args.force, symbols=args.symbols,
              out=args.out, lines=lines)
    p = doc.get("pass") or {}
    print(f"sec_fundamentals: {p.get('status')} covered={doc['names_covered']}/"
          f"{doc['names_in_registry']} fetched={p.get('names_fetched_this_pass')} "
          f"rebuilt={p.get('names_rebuilt_this_pass')} stopped={p.get('stopped_because')!r} "
          f"-> {args.out or OUT}")
    if p.get("blocked"):
        print(f"  BLOCKED: {p.get('why')}")
    for reason, syms in (doc.get("uncovered_by_reason") or {}).items():
        print(f"  uncovered [{reason}]: {len(syms)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
