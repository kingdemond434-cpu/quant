"""THE ALPHA CAPTURE SUBSTITUTE -- public analyst, broker, guidance and forecast-revision views,
stored point-in-time, tracked after publication, and turned into gauntlet cells.

WHAT IT REPLACES. A buy-side desk with an Alpha Capture feed reads sell-side trade ideas the
moment they are submitted and scores each contributor on what the instrument did afterwards
(ResearchAlum does the same for published research). This desk has neither subscription. What it
does have, with no login, is five public surfaces that carry the same object -- a dated view on an
instrument -- and this organ reads them:

    yahoo_upgrades      Yahoo Finance upgradeDowngradeHistory (crumb flow)   US share CFDs
    sec_8k_guidance     SEC EDGAR full-text search over 8-K text             US share CFDs
    eastmoney_reports   reportapi.eastmoney.com/report/list (stock+industry) CN ADRs; CHINAH,
                                                                             HK50, USDCNH; US semis
    naver_research      finance.naver.com research lists + detail pages      USDKRW; US semis
    tdnet_revisions     TDnet via the keyless webapi.yanoshin.jp mirror      Toyota; JPN225, USDJPY

ONE PASS, FIVE STEPS, EVERY ONE WRITING SOMETHING.
  1. COLLECT the sources that are due, politely (`libs.data.polite_fetch`: per-host spacing,
     bounded retries, no retry on 403/404), each tolerant of any field it does not find: a
     missing target is UNMEASURED and listed, never a 0.
  2. STORE every view in the append-only store (`libs.research.analyst_views.AnalystViewStore`),
     stamped at the one PIT door; `first_seen_at` is the instant this box first held it.
  3. TRACK the cumulative return after each view at +1/+5/+21 trading days from the first close
     known after `first_seen_at` (never `published_at` alone), long upgrades and short downgrades,
     by source, broker and instrument, with n and t -- and the admission CONTRACT: drift t by
     source against a placebo of randomly shifted publication dates.
  4. EMIT through the three doors the desk already reads:
       direct_cells      `proposer_common.donate` -> the compiler -> the gauntlet
                         (`analyst_revision_drift`, `analyst_cross_market_lead`)
       indirect_cells    `data/axes/analyst_views.json`, rows keyed by symbol + knowable_at, the
                         shape `libs.research.alpha_dsl.axis_fields` binds for the expression
                         factory and `causal_lab` conditions on
       allocation_intel  `reports/ALPHA_CAPTURE_ALLOCATION_INTEL.json`, a per-instrument, per-day
                         summary the allocator MAY read (nothing here sizes)
  5. REPORT `reports/ALPHA_CAPTURE.json` and the contract `reports/ALPHA_CAPTURE_CONTRACT.json`.

LIVE YIELD IS UNMEASURED UNTIL THE TRADING BOX RUNS IT. It was built in a container whose network
policy refuses all five hosts; the parsers are proven on recorded payload shapes (tests), and every
source reports `UNMEASURED_LIVE_YIELD` until a pass on the box actually fetches it.

    python desks/mt5/research/alpha_capture.py --once [--budget-s 300] [--dry-run] [--no-collect]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from statistics import NormalDist
from typing import Any
from urllib.parse import quote, urlencode

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import analyst_views as av  # noqa: E402
from libs.research.analyst_views import UNMEASURED, AnalystView  # noqa: E402

SOURCE = "alpha_capture"
DATA = DESK / "data" / "alpha_capture"
STORE = DATA / "analyst_views.jsonl"
STATE = DATA / "collector_state.json"
AXIS = DESK / "data" / "axes" / "analyst_views.json"
REPORT = DESK / "reports" / "ALPHA_CAPTURE.json"
CONTRACT = DESK / "reports" / "ALPHA_CAPTURE_CONTRACT.json"
INTEL = DESK / "reports" / "ALPHA_CAPTURE_ALLOCATION_INTEL.json"
UNIVERSE = DESK / "data" / "universe" / "universe.json"

UNMEASURED_LIVE_YIELD = "UNMEASURED_LIVE_YIELD"
MAX_DONATIONS = 20
ALPHA = 0.05
PROPOSE_T = 2.0
CONTRACT_HORIZON_D = 5
KST = timezone(timedelta(hours=9))
JST = KST
CST = timezone(timedelta(hours=8))

# ------------------------------------------------------------------------------ instruments
#: MT5 share CFD -> its US listing's ticker. The broker registry carries no ticker, so this is
#: the one hand table; `test_every_mapped_symbol_is_quoted` pins it against universe.json.
TICKERS: dict[str, str] = {
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
}
BY_TICKER: dict[str, str] = {t: s for s, t in TICKERS.items()}
#: A share CFD's CAR is net of the US index it trades beside; indices and FX are raw returns.
BENCHMARK = "US500"

#: Chinese issuer names (eastmoney `stockName`) -> MT5 instruments the view is ABOUT.
CN_NAMES: dict[str, str] = {"阿里巴巴": "AlibabaGroup", "百度": "Baidu", "蔚来": "NIO",
                            "腾讯音乐": "TMEGroup", "台积电": "TSMC", "丰田": "Toyota"}
#: Industry words (eastmoney `industryName`/`indvInduName`) -> lead groups.
CN_INDUSTRY_LEADS: tuple[tuple[str, str], ...] = (
    ("半导体", "cn_semis"), ("集成电路", "cn_semis"), ("电子", "cn_semis"), ("芯片", "cn_semis"),
    ("汽车", "cn_auto"), ("互联网", "cn_internet"), ("传媒", "cn_internet"),
    ("游戏", "cn_internet"), ("软件", "cn_internet"), ("文化", "cn_internet"))
#: Korean semiconductor issuers (Naver `code=`) whose views lead the US semis and the won.
KR_SEMIS: dict[str, str] = {"005930": "삼성전자", "000660": "SK하이닉스", "042700": "한미반도체",
                            "009150": "삼성전기", "000990": "DB하이텍", "240810": "원익IPS",
                            "058470": "리노공업", "039030": "이오테크닉스", "403870": "HPSP"}
KR_SEMIS_WORDS = ("반도체", "semiconductor", "메모리", "HBM")
#: TDnet company codes -> MT5 instruments the revision is ABOUT.
JP_CODES: dict[str, str] = {"72030": "Toyota", "7203": "Toyota"}

# ------------------------------------------------------------------------------ the roster
#: One row per source: how it is reached, how it is stamped, which of the three uses it feeds,
#: and the culture fields Tier S's orthogonality test reads.
SOURCES: dict[str, dict[str, Any]] = {
    "yahoo_upgrades": {
        "name": "Yahoo Finance upgrade/downgrade history",
        "url": "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
               "?modules=upgradeDowngradeHistory",
        "region": "US", "language": "en", "cadence_s": 3600, "auth": "cookie",
        "licence": "Yahoo terms: personal/non-commercial display of public quote data; "
                   "a session cookie + crumb (no login) is required; per-host 1.1s spacing",
        "cursor": "round-robin over the 103 tickers (35 per pass); dedupe by event_id "
                  "(ticker|firm|epochGradeDate|toGrade|fromGrade)",
        "pit": "published_at = epochGradeDate (date precision when it is a UTC midnight); "
               "first_seen_at = this pass's clock",
        "uses": ["direct_cells", "indirect_cells", "allocation_intel"],
        "source_culture": "US/en", "participant_structure": ["institutional", "broker_specific"],
        "failure_mode_hypothesis": (
            "the most arbitraged version of revision drift: it should fail when US attention is "
            "saturated (earnings season, mega-cap coverage) and revision-momentum quant books are "
            "crowded, not on Asian policy or flow calendars"),
        "crowding_prior": "high"},
    "sec_8k_guidance": {
        "name": "SEC EDGAR 8-K full-text search for guidance changes",
        "url": "https://efts.sec.gov/LATEST/search-index?q=%22raises%20guidance%22&forms=8-K",
        "region": "US", "language": "en", "cadence_s": 6 * 3600, "auth": "none",
        "licence": "US federal public record; SEC fair access (<=10 req/s) with a declared "
                   "User-Agent from QUANT_EDGAR_UA -- unconfigured means not fetched",
        "cursor": "dateRange startdt = last pass minus 3 days; dedupe by accession (adsh)",
        "pit": "published_at = file_date (date precision); first_seen_at = this pass's clock",
        "uses": ["direct_cells", "indirect_cells", "allocation_intel"],
        "source_culture": "US/en", "participant_structure": ["institutional"],
        "failure_mode_hypothesis": (
            "company guidance language is machine-read by every headline vendor within seconds; "
            "it should fail whenever news-parsing algos are active and survive only in thinly "
            "covered names, on the US disclosure calendar"),
        "crowding_prior": "high"},
    "eastmoney_reports": {
        "name": "eastmoney research report list (stock and industry)",
        "url": "https://reportapi.eastmoney.com/report/list",
        "region": "CN", "language": "zh", "cadence_s": 3600, "auth": "none",
        "licence": "public list API behind data.eastmoney.com/report; no key; list metadata "
                   "only (the PDFs are not fetched); polite spacing",
        "cursor": "beginTime = last pass minus 3 days, pages until an empty page (<= 3 per "
                  "qType); dedupe by infoCode",
        "pit": "published_at = publishDate in CST (date precision when 00:00:00); "
               "first_seen_at = this pass's clock",
        "uses": ["direct_cells", "indirect_cells", "allocation_intel"],
        "source_culture": "CN/zh",
        "participant_structure": ["retail_heavy", "policy_driven", "broker_specific"],
        "failure_mode_hypothesis": (
            "A-share sell-side ratings are structurally optimistic and retail-read, so the "
            "information is in the rare downgrade and the target move; it should fail around "
            "policy shifts (state-fund support, CSRC windows, Golden Week) rather than at US "
            "earnings-season crowding"),
        "crowding_prior": "low"},
    "naver_research": {
        "name": "Naver Finance research (company, industry, economy lists)",
        "url": "https://finance.naver.com/research/company_list.naver",
        "region": "KR", "language": "ko", "cadence_s": 3600, "auth": "none",
        "licence": "public research index pages; broker PDFs are not fetched; target and "
                   "opinion read from the public detail page; polite spacing",
        "cursor": "list pages until a seen nid (<= 3 pages); detail pages for up to 40 new "
                  "company nids per pass, the rest queued in collector_state",
        "pit": "published_at = list date yy.mm.dd (date precision, KST); first_seen_at = this "
               "pass's clock; the previous target comes from the same broker's earlier row",
        "uses": ["direct_cells", "indirect_cells", "allocation_intel"],
        "source_culture": "KR/ko",
        "participant_structure": ["retail_heavy", "broker_specific", "institutional"],
        "failure_mode_hypothesis": (
            "Korean brokers rate almost everything Buy, so the signal is the target change; it "
            "should fail when foreign flow (MSCI rebalances, won funding stress, export data) "
            "dominates the tape, not when US attention does"),
        "crowding_prior": "low"},
    "tdnet_revisions": {
        "name": "TDnet timely disclosures (forecast and dividend revisions) via yanoshin",
        "url": "https://webapi.yanoshin.jp/webapi/tdnet/list/recent.json?limit=300",
        "region": "JP", "language": "ja", "cadence_s": 3600, "auth": "none",
        "licence": "public exchange disclosures mirrored by a keyless community API; titles "
                   "only (PDFs not fetched); polite spacing",
        "cursor": "the recent list each pass; dedupe by the mirror's id",
        "pit": "published_at = pubdate JST -> UTC (datetime precision); first_seen_at = this "
               "pass's clock",
        "uses": ["direct_cells", "indirect_cells", "allocation_intel"],
        "source_culture": "JP/ja", "participant_structure": ["institutional", "policy_driven"],
        "failure_mode_hypothesis": (
            "Japanese guidance is conservative by custom and revised up through the year, so the "
            "drift should fail at fiscal-year-end and when the BoJ/yen regime reprices exporters "
            "-- a calendar that differs from the US guidance cycle"),
        "crowding_prior": "low"},
}

#: What every cell says about why the edge exists (spec fields in `lead_schema.SPEC_FIELDS`).
MECHANISM = ("slow diffusion of broker and company information: a dated public view moves the "
             "instrument in its direction after the desk could have read it")
PAYER = "investors who under-react to published revisions (and, for a lead, the slow venue)"
CONSTRAINT = ("attention is finite and arbitrage is limited: capital, short-sale cost on "
              "downgrades, benchmark-bound long-only books, and a language barrier for the "
              "non-English sources")


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _universe() -> set[str]:
    doc = _read_json(UNIVERSE, {})
    return {str(k) for k in doc} if isinstance(doc, dict) else set()


# ------------------------------------------------------------------------------ parsers
def _date_utc(d: date) -> str:
    return datetime(d.year, d.month, d.day, tzinfo=UTC).isoformat(timespec="seconds")


def parse_yahoo(symbol: str, doc: Any) -> list[AnalystView]:
    """quoteSummary upgradeDowngradeHistory -> views about `symbol`. Tolerant of any absence."""
    try:
        result = (doc.get("quoteSummary") or {}).get("result") or []
        hist = ((result[0] or {}).get("upgradeDowngradeHistory") or {}).get("history") or []
    except (AttributeError, IndexError, TypeError):
        return []
    ticker = TICKERS.get(symbol, symbol)
    out: list[AnalystView] = []
    for h in hist:
        if not isinstance(h, dict):
            continue
        epoch = h.get("epochGradeDate")
        pub: str | None = None
        precision = UNMEASURED
        if isinstance(epoch, (int, float)) and epoch > 0:
            when = datetime.fromtimestamp(float(epoch), tz=UTC)
            pub = when.isoformat(timespec="seconds")
            precision = "date" if int(epoch) % 86400 == 0 else "datetime"
        act = str(h.get("action") or "").lower()
        action = {"up": "up", "down": "down", "init": "init", "main": "reiterate",
                  "reit": "reiterate"}.get(act, UNMEASURED)
        firm = str(h.get("firm") or "").strip() or None
        v = AnalystView(
            source="yahoo_upgrades", published_at=pub, published_precision=precision,
            issuer=ticker, issuer_name=symbol, instrument=symbol, broker=firm, action=action,
            rating_old_raw=(str(h.get("fromGrade")) if h.get("fromGrade") else None),
            rating_new_raw=(str(h.get("toGrade")) if h.get("toGrade") else None),
            target_old=h.get("priorPriceTarget"), target_new=h.get("currentPriceTarget"),
            language="en", region="US", kind="broker_rating",
            title=f"{firm or '?'} {act or '?'} {ticker}: {h.get('fromGrade') or '?'} -> "
                  f"{h.get('toGrade') or '?'}",
            url=f"https://finance.yahoo.com/quote/{ticker}/analysis",
            native_id=f"{ticker}|{firm}|{epoch}|{h.get('toGrade')}|{h.get('fromGrade')}")
        out.append(v.finish())
    return out


_WORD = {"up": "raise", "down": "cut", UNMEASURED: "mixed"}
_EFTS_TICKER = re.compile(r"\(([A-Z][A-Z.\-]{0,6})\)\s*\(CIK")


def parse_sec_efts(docs: Mapping[int, Sequence[Any]]) -> list[AnalystView]:
    """EDGAR full-text hits grouped by the direction of the phrase that matched them.

    A filing that matched BOTH an up and a down phrase has no direction (a press release that
    raises one line and cuts another); it is stored with action UNMEASURED.
    """
    by_adsh: dict[str, dict[str, Any]] = {}
    for direction, pages in docs.items():
        for doc in pages:
            hits = (((doc or {}).get("hits") or {}).get("hits") or []) if isinstance(
                doc, dict) else []
            for hit in hits:
                src = (hit or {}).get("_source") or {}
                adsh = str(src.get("adsh") or str(hit.get("_id") or "").split(":")[0])
                if not adsh:
                    continue
                rec = by_adsh.setdefault(adsh, {"dirs": set(), "src": src,
                                                "id": str(hit.get("_id") or "")})
                rec["dirs"].add(int(direction))
    out: list[AnalystView] = []
    for adsh, rec in by_adsh.items():
        src = rec["src"]
        names = " ".join(str(x) for x in (src.get("display_names") or []))
        m = _EFTS_TICKER.search(names)
        ticker = m.group(1) if m else ""
        symbol = BY_TICKER.get(ticker) or BY_TICKER.get(ticker.replace(".", "-"))
        fd = str(src.get("file_date") or "")
        pub = None
        try:
            pub = _date_utc(date.fromisoformat(fd[:10])) if fd else None
        except ValueError:
            pub = None
        dirs = rec["dirs"]
        action = ("up" if dirs == {1} else "down" if dirs == {-1} else UNMEASURED)
        cik = str((src.get("ciks") or [""])[0])
        doc_name = rec["id"].split(":", 1)[1] if ":" in rec["id"] else ""
        v = AnalystView(
            source="sec_8k_guidance", published_at=pub,
            published_precision="date" if pub else UNMEASURED, issuer=ticker or cik,
            issuer_name=names[:120], instrument=symbol, broker="issuer", action=action,
            language="en", region="US", kind="company_guidance",
            title=f"8-K guidance {_WORD[action]} {ticker or cik} {fd}",
            url=(f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/"
                 f"{adsh.replace('-', '')}/{doc_name}" if cik and doc_name else ""),
            native_id=adsh)
        out.append(v.finish())
    return out


def _jsonp(text: str) -> Any:
    """eastmoney answers JSON, or JSONP when a callback is named; either is read."""
    t = text.strip()
    if t and t[0] not in "{[":
        m = re.search(r"\((\{.*\})\)\s*;?\s*$", t, re.S)
        t = m.group(1) if m else t
    return json.loads(t)


def _cn_published(raw: Any) -> tuple[str | None, str]:
    s = str(raw or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?", s)
    if not m:
        return None, UNMEASURED
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hh, mm, ss = (int(m.group(4) or 0), int(m.group(5) or 0), int(m.group(6) or 0))
    if hh == mm == ss == 0:
        return _date_utc(date(y, mo, d)), "date"
    local = datetime(y, mo, d, hh, mm, ss, tzinfo=CST)
    return local.astimezone(UTC).isoformat(timespec="seconds"), "datetime"


def _cn_leads(*texts: str) -> list[str]:
    joined = " ".join(t for t in texts if t)
    return sorted({lead for word, lead in CN_INDUSTRY_LEADS if word in joined})


def parse_eastmoney(doc: Any, qtype: int) -> list[AnalystView]:
    """report/list rows -> views. qType 0 = stock reports, 1 = industry reports."""
    rows = (doc or {}).get("data") if isinstance(doc, dict) else None
    out: list[AnalystView] = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        pub, precision = _cn_published(r.get("publishDate"))
        title = str(r.get("title") or "")
        name = str(r.get("stockName") or "")
        industry = str(r.get("industryName") or r.get("indvInduName") or "")
        instrument = next((sym for key, sym in CN_NAMES.items() if key in name), None)
        leads = _cn_leads(industry, title if qtype == 1 else "")
        if qtype == 0:
            leads = sorted({*leads, "cn_market"})
        new_raw = str(r.get("emRatingName") or r.get("sRatingName") or "").strip() or None
        old_raw = str(r.get("lastEmRatingName") or "").strip() or None
        action = UNMEASURED
        if old_raw is None and new_raw and ("首次" in title):
            action = "init"
        broker = str(r.get("orgSName") or r.get("orgName") or "").strip() or None
        code = str(r.get("infoCode") or "")
        v = AnalystView(
            source="eastmoney_reports", published_at=pub, published_precision=precision,
            issuer=str(r.get("stockCode") or industry or "industry"),
            issuer_name=name or industry, instrument=instrument, leads=leads, broker=broker,
            action=action, rating_old_raw=old_raw, rating_new_raw=new_raw,
            target_new=r.get("indvAimPriceT") or r.get("indvAimPriceL"),
            language="zh", region="CN", kind="broker_rating" if qtype == 0 else "industry_view",
            title=title, url=(f"https://data.eastmoney.com/report/info/{code}.html"
                              if code else ""),
            native_id=code)
        out.append(v.finish())
    return out


_TD = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", _TAG.sub(" ", html)).strip()


def parse_naver_list(html: str, kind: str) -> list[dict[str, Any]]:
    """One research list page -> rows {nid, code, name, industry, title, broker, date}.

    `kind` is company | industry | economy. Columns are found by what they CONTAIN (the nid link,
    the code link, the yy.mm.dd date), not by position, so a reordered table still reads.
    """
    out: list[dict[str, Any]] = []
    for tr in re.split(r"<tr[^>]*>", html, flags=re.I)[1:]:
        tds = _TD.findall(tr)
        if len(tds) < 3:
            continue
        nid_idx = next((i for i, td in enumerate(tds) if re.search(r"_read\.naver\?nid=\d+", td)),
                       None)
        if nid_idx is None:
            continue
        nid = re.search(r"nid=(\d+)", tds[nid_idx])
        code = re.search(r"code=(\d{6})", tr)
        dt = next((m.group(0) for td in tds for m in [re.search(r"\b\d{2}\.\d{2}\.\d{2}\b", td)]
                   if m), None)
        name = _text(tds[0]) if kind == "company" else ""
        industry = _text(tds[0]) if kind == "industry" else ""
        broker = _text(tds[nid_idx + 1]) if nid_idx + 1 < len(tds) else ""
        out.append({"nid": nid.group(1) if nid else "", "code": code.group(1) if code else "",
                    "name": name, "industry": industry, "title": _text(tds[nid_idx]),
                    "broker": broker or None, "date": dt, "kind": kind})
    return out


def parse_naver_detail(html: str) -> tuple[float | None, str | None]:
    """(target price, opinion) from a company_read page; each None when the page omits it."""
    target: float | None = None
    opinion: str | None = None
    # The number must follow the label through TAGS ONLY: the title often says "목표가 상향"
    # (target raised) and the next digits after it are the date, which is not a price.
    m = re.search(r"목표가\s*(?:<[^>]+>\s*)*(\d[\d,]*)", html)
    if m:
        target = av._num(m.group(1))
    o = re.search(r"투자의견\s*(?:<[^>]+>\s*)*([^<\s|][^<|]*)", html)
    if o:
        opinion = o.group(1).strip() or None
    return target, opinion


def naver_views(rows: Sequence[Mapping[str, Any]],
                details: Mapping[str, tuple[float | None, str | None]]) -> list[AnalystView]:
    out: list[AnalystView] = []
    for r in rows:
        dt = r.get("date")
        pub = None
        if dt:
            try:
                yy, mm, dd = (int(x) for x in str(dt).split("."))
                pub = _date_utc(date(2000 + yy, mm, dd))
            except ValueError:
                pub = None
        kind = str(r.get("kind") or "company")
        code = str(r.get("code") or "")
        text = f"{r.get('industry') or ''} {r.get('title') or ''}"
        if kind == "company":
            leads = ["kr_semis"] if code in KR_SEMIS else ["kr_market"]
        elif kind == "industry":
            leads = (["kr_semis"] if any(w.lower() in text.lower() for w in KR_SEMIS_WORDS)
                     else ["kr_market"])
        else:
            leads = ["kr_market"]
        target, opinion = details.get(str(r.get("nid") or ""), (None, None))
        v = AnalystView(
            source="naver_research", published_at=pub,
            published_precision="date" if pub else UNMEASURED,
            issuer=code or str(r.get("industry") or kind), issuer_name=str(r.get("name") or ""),
            instrument=None, leads=leads, broker=r.get("broker"), rating_new_raw=opinion,
            target_new=target, language="ko", region="KR",
            kind={"company": "broker_rating", "industry": "industry_view"}.get(kind, "macro_view"),
            title=str(r.get("title") or ""),
            url=f"https://finance.naver.com/research/{kind}_read.naver?nid={r.get('nid')}",
            native_id=f"{kind}|{r.get('nid')}")
        out.append(v.finish())
    return out


_TDNET_WORDS = ("業績予想", "配当予想", "上方修正", "下方修正", "業績見通し")


def parse_tdnet(doc: Any) -> list[AnalystView]:
    """yanoshin tdnet list -> forecast/dividend revision views. Other disclosures are skipped."""
    items = (doc or {}).get("items") if isinstance(doc, dict) else None
    out: list[AnalystView] = []
    for it in items or []:
        t = (it or {}).get("Tdnet") if isinstance(it, dict) else None
        if not isinstance(t, dict):
            continue
        title = str(t.get("title") or "")
        if not any(w in title for w in _TDNET_WORDS):
            continue
        if "上方修正" in title or "増配" in title:
            action = "up"
        elif "下方修正" in title or "減配" in title or "無配" in title:
            action = "down"
        else:
            action = UNMEASURED
        pub = None
        m = re.match(r"(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})(?::(\d{2}))?",
                     str(t.get("pubdate") or ""))
        if m:
            g = [int(m.group(i) or 0) for i in range(1, 7)]
            local = datetime(g[0], g[1], g[2], g[3], g[4], g[5], tzinfo=JST)
            pub = local.astimezone(UTC).isoformat(timespec="seconds")
        code = str(t.get("company_code") or "")
        v = AnalystView(
            source="tdnet_revisions", published_at=pub,
            published_precision="datetime" if pub else UNMEASURED, issuer=code,
            issuer_name=str(t.get("company_name") or ""), instrument=JP_CODES.get(code),
            leads=["jp_market"], broker="issuer", action=action, language="ja", region="JP",
            kind="company_guidance", title=title, url=str(t.get("document_url") or ""),
            native_id=str(t.get("id") or ""))
        out.append(v.finish())
    return out


# ------------------------------------------------------------------------------ fetchers
Getter = Callable[..., Any]


def _default_get() -> Getter:
    from libs.data import polite_fetch
    return polite_fetch.get


def _cookie_opener() -> Callable[..., Any]:
    """An opener that keeps cookies across calls, in the shape `polite_fetch.get(opener=)` takes.
    Yahoo's crumb is bound to the session cookie `fc.yahoo.com` sets; nothing else is stored."""
    import urllib.request
    from http.cookiejar import CookieJar

    from libs.data import polite_fetch
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()),
                                         urllib.request.HTTPSHandler(
                                             context=polite_fetch.ssl_context()))

    def _open(req: Any, timeout: float = 20.0, context: Any = None) -> Any:
        return opener.open(req, timeout=timeout)
    return _open


def _ok(resp: Any) -> bool:
    return bool(getattr(resp, "ok", False))


def _err(resp: Any) -> str:
    return str(getattr(resp, "error", "") or f"HTTP {getattr(resp, 'status', None)}")


def fetch_yahoo(get: Getter, state: dict[str, Any], deadline: float, *,
                per_pass: int = 35, opener: Any = None) -> tuple[list[AnalystView], dict[str, Any]]:
    rep: dict[str, Any] = {"attempted": 0, "ok": 0, "errors": Counter()}
    opener = opener if opener is not None else _cookie_opener()
    get(("https://fc.yahoo.com"), opener=opener, retries=0, leg="alpha_capture:yahoo",
        deadline=deadline)                                   # sets the session cookie; 404 is fine
    crumb_resp = get("https://query2.finance.yahoo.com/v1/test/getcrumb", opener=opener,
                     leg="alpha_capture:yahoo", deadline=deadline)
    crumb = str(getattr(crumb_resp, "text", "") or "").strip()
    if not _ok(crumb_resp) or not crumb or "<" in crumb or len(crumb) > 64:
        rep["status"] = "NO_CRUMB"
        rep["why"] = f"crumb flow failed ({_err(crumb_resp)}); nothing fetched, which is a verdict"
        return [], rep
    symbols = list(TICKERS)
    start = int(state.get("cursor") or 0) % len(symbols)
    order = symbols[start:] + symbols[:start]
    views: list[AnalystView] = []
    done = 0
    for sym in order[:per_pass]:
        if time.monotonic() >= deadline:
            break
        url = (SOURCES["yahoo_upgrades"]["url"].format(ticker=quote(TICKERS[sym]))
               + f"&crumb={quote(crumb)}")
        resp = get(url, opener=opener, leg="alpha_capture:yahoo", deadline=deadline)
        rep["attempted"] += 1
        done += 1
        if not _ok(resp):
            rep["errors"][_err(resp)] += 1
            continue
        try:
            views.extend(parse_yahoo(sym, json.loads(resp.text)))
            rep["ok"] += 1
        except ValueError:
            rep["errors"]["unparseable JSON"] += 1
    state["cursor"] = (start + done) % len(symbols)
    rep["status"] = "FETCHED" if rep["ok"] else "FAILED"
    return views, rep


SEC_PHRASES: dict[int, tuple[str, ...]] = {
    1: ('"raises guidance"', '"raised guidance"', '"raising guidance"', '"raises full-year"',
        '"raises its full-year"', '"increases guidance"'),
    -1: ('"lowers guidance"', '"lowered guidance"', '"lowering guidance"', '"cuts guidance"',
         '"reduces guidance"', '"lowers full-year"'),
}


def fetch_sec(get: Getter, state: dict[str, Any], deadline: float, *, now: datetime
              ) -> tuple[list[AnalystView], dict[str, Any]]:
    ua = os.environ.get("QUANT_EDGAR_UA", "").strip()
    if not ua:
        return [], {"status": "UNCONFIGURED", "attempted": 0,
                    "why": "no QUANT_EDGAR_UA: the SEC's fair-access policy requires a declared "
                           "User-Agent, so nothing was fetched (a configuration gap, not a "
                           "closed source)"}
    since = (now - timedelta(days=3)).date().isoformat()
    until = now.date().isoformat()
    docs: dict[int, list[Any]] = {1: [], -1: []}
    rep: dict[str, Any] = {"attempted": 0, "ok": 0, "errors": Counter()}
    for direction, phrases in SEC_PHRASES.items():
        for phrase in phrases:
            if time.monotonic() >= deadline:
                break
            url = "https://efts.sec.gov/LATEST/search-index?" + urlencode(
                {"q": phrase, "forms": "8-K", "dateRange": "custom", "startdt": since,
                 "enddt": until})
            resp = get(url, headers={"User-Agent": ua, "Accept": "application/json"},
                       leg="alpha_capture:sec", deadline=deadline)
            rep["attempted"] += 1
            if not _ok(resp):
                rep["errors"][_err(resp)] += 1
                continue
            try:
                docs[direction].append(json.loads(resp.text))
                rep["ok"] += 1
            except ValueError:
                rep["errors"]["unparseable JSON"] += 1
    state["since"] = since
    rep["status"] = "FETCHED" if rep["ok"] else "FAILED"
    return parse_sec_efts(docs), rep


def fetch_eastmoney(get: Getter, state: dict[str, Any], deadline: float, *, now: datetime,
                    max_pages: int = 3) -> tuple[list[AnalystView], dict[str, Any]]:
    begin = (now.astimezone(CST) - timedelta(days=3)).date().isoformat()
    end = now.astimezone(CST).date().isoformat()
    rep: dict[str, Any] = {"attempted": 0, "ok": 0, "errors": Counter()}
    views: list[AnalystView] = []
    for qtype in (0, 1):
        for page in range(1, max_pages + 1):
            if time.monotonic() >= deadline:
                break
            params = {"industryCode": "*", "pageSize": 100, "industry": "*", "rating": "*",
                      "ratingChange": "*", "beginTime": begin, "endTime": end, "pageNo": page,
                      "fields": "", "qType": qtype, "orgCode": "", "code": "*", "rcode": "",
                      "p": page, "pageNum": page}
            resp = get(SOURCES["eastmoney_reports"]["url"] + "?" + urlencode(params),
                       headers={"Referer": "https://data.eastmoney.com/report/"},
                       leg="alpha_capture:eastmoney", deadline=deadline)
            rep["attempted"] += 1
            if not _ok(resp):
                rep["errors"][_err(resp)] += 1
                break
            try:
                doc = _jsonp(resp.text)
            except ValueError:
                rep["errors"]["unparseable JSON"] += 1
                break
            rep["ok"] += 1
            got = parse_eastmoney(doc, qtype)
            views.extend(got)
            if len(got) < 100:
                break
    state["begin"] = begin
    rep["status"] = "FETCHED" if rep["ok"] else "FAILED"
    return views, rep


def fetch_naver(get: Getter, state: dict[str, Any], deadline: float, *, max_pages: int = 3,
                max_details: int = 40) -> tuple[list[AnalystView], dict[str, Any]]:
    rep: dict[str, Any] = {"attempted": 0, "ok": 0, "errors": Counter(), "details": 0}
    seen: set[str] = set(state.get("seen_nids") or [])
    rows: list[dict[str, Any]] = []
    for kind in ("company", "industry", "economy"):
        for page in range(1, max_pages + 1):
            if time.monotonic() >= deadline:
                break
            url = f"https://finance.naver.com/research/{kind}_list.naver?&page={page}"
            resp = get(url, leg="alpha_capture:naver", deadline=deadline)
            rep["attempted"] += 1
            if not _ok(resp):
                rep["errors"][_err(resp)] += 1
                break
            rep["ok"] += 1
            got = parse_naver_list(resp.text, kind)
            fresh = [r for r in got if f"{kind}|{r['nid']}" not in seen]
            seen |= {f"{kind}|{r['nid']}" for r in fresh}
            rows.extend(fresh)
            if len(fresh) < len(got) or not got:
                break                                         # reached what we already hold
    pending: list[str] = list(state.get("pending_details") or [])
    pending += [r["nid"] for r in rows if r["kind"] == "company" and r["nid"]]
    details: dict[str, tuple[float | None, str | None]] = {}
    left: list[str] = []
    for nid in dict.fromkeys(pending):
        if len(details) >= max_details or time.monotonic() >= deadline:
            left.append(nid)
            continue
        resp = get(f"https://finance.naver.com/research/company_read.naver?nid={nid}&page=1",
                   leg="alpha_capture:naver", deadline=deadline)
        rep["attempted"] += 1
        if _ok(resp):
            details[nid] = parse_naver_detail(resp.text)
            rep["details"] += 1
        else:
            rep["errors"][_err(resp)] += 1
            left.append(nid)
    # A detail fetched on a LATER pass belongs to a row seen earlier; re-emitting that row with its
    # target is a revision of the same event_id, so the original first_seen_at stands.
    held = {str(r.get("nid")): r for r in state.get("held_rows") or []}
    for r in rows:
        held[str(r["nid"])] = r
    carry = [held[n] for n in details if n in held and held[n] not in rows]
    state["pending_details"] = left[-500:]
    state["held_rows"] = [held[n] for n in left if n in held][-500:]
    # newest nids kept: they are what the next pass's pages will show again
    state["seen_nids"] = sorted(seen, key=lambda s: int(s.rpartition("|")[2] or 0))[-5000:]
    rep["status"] = "FETCHED" if rep["ok"] else "FAILED"
    return naver_views([*rows, *carry], details), rep


def fetch_tdnet(get: Getter, state: dict[str, Any], deadline: float
                ) -> tuple[list[AnalystView], dict[str, Any]]:
    resp = get(SOURCES["tdnet_revisions"]["url"], leg="alpha_capture:tdnet", deadline=deadline)
    if not _ok(resp):
        return [], {"status": "FAILED", "attempted": 1, "ok": 0, "errors": {_err(resp): 1}}
    try:
        views = parse_tdnet(json.loads(resp.text))
    except ValueError:
        return [], {"status": "FAILED", "attempted": 1, "ok": 0,
                    "errors": {"unparseable JSON": 1}}
    return views, {"status": "FETCHED", "attempted": 1, "ok": 1, "errors": {}}


def _due(state: Mapping[str, Any], sid: str, now: datetime) -> bool:
    last = av.parse_time((state.get(sid) or {}).get("last_attempt"))
    return last is None or (now - last).total_seconds() >= float(SOURCES[sid]["cadence_s"])


def collect(*, now: datetime, budget_s: float, get: Getter | None = None,
            only: Sequence[str] | None = None, state: dict[str, Any] | None = None,
            yahoo_opener: Any = None) -> tuple[list[AnalystView], dict[str, Any],
                                               dict[str, Any]]:
    """Fetch every due source inside the budget. Returns (views, per-source report, state)."""
    get = get or _default_get()
    state = dict(state if state is not None else _read_json(STATE, {}))
    began = time.monotonic()
    views: list[AnalystView] = []
    report: dict[str, Any] = {}
    todo = [s for s in SOURCES if (not only or s in only)]
    for i, sid in enumerate(todo):
        if not _due(state, sid, now):
            report[sid] = {"status": "NOT_DUE", "cadence_s": SOURCES[sid]["cadence_s"]}
            continue
        remaining = budget_s - (time.monotonic() - began)
        if remaining <= 1:
            report[sid] = {"status": "NOT_REACHED", "why": "the pass budget ran out first"}
            continue
        share = remaining / max(1, len(todo) - i)
        deadline = time.monotonic() + share
        sstate = dict(state.get(sid) or {})
        try:
            if sid == "yahoo_upgrades":
                got, rep = fetch_yahoo(get, sstate, deadline, opener=yahoo_opener)
            elif sid == "sec_8k_guidance":
                got, rep = fetch_sec(get, sstate, deadline, now=now)
            elif sid == "eastmoney_reports":
                got, rep = fetch_eastmoney(get, sstate, deadline, now=now)
            elif sid == "naver_research":
                got, rep = fetch_naver(get, sstate, deadline)
            else:
                got, rep = fetch_tdnet(get, sstate, deadline)
        except Exception as exc:                      # one source never takes the others down
            got, rep = [], {"status": "FAILED", "why": f"{type(exc).__name__}: {exc}"}
        if rep.get("status") != "UNCONFIGURED":
            sstate["last_attempt"] = now.isoformat(timespec="seconds")
        if rep.get("status") == "FETCHED":
            sstate["last_success"] = now.isoformat(timespec="seconds")
        rep["errors"] = dict(rep.get("errors") or {})
        rep["views_parsed"] = len(got)
        state[sid] = sstate
        report[sid] = rep
        views.extend(got)
    return views, report, state


# ------------------------------------------------------------------------------ measurement
def _bars_loader() -> Callable[[str], Any]:
    try:
        from research.proposer_common import bars
    except Exception:                                         # pragma: no cover - import context
        return lambda _s: None
    return bars


def daily_bars(symbols: Sequence[str], loader: Callable[[str], Any]
               ) -> dict[str, av.DailyBars | None]:
    out: dict[str, av.DailyBars | None] = {}
    for sym in symbols:
        try:
            frame = loader(sym)
        except Exception:
            frame = None
        out[sym] = av.to_daily(frame) if frame is not None else None
    return out


def _bench_map(targets: Sequence[str], universe_doc: Mapping[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for t in targets:
        row = universe_doc.get(t) if isinstance(universe_doc, Mapping) else None
        if isinstance(row, dict) and str(row.get("asset_class") or "") == "Equities":
            out[t] = BENCHMARK
    return out


def _bonferroni_t(n: int, alpha: float = ALPHA) -> float:
    return float("inf") if n <= 0 else float(NormalDist().inv_cdf(1 - alpha / (2 * n)))


def measure(rows: Sequence[Mapping[str, Any]], *, loader: Callable[[str], Any],
            universe_doc: Mapping[str, Any], clock: av.Clock | None = None,
            n_placebo: int = 200) -> dict[str, Any]:
    """Tracker, broker table, the placebo contract and the research-only vendor stratum."""
    clock = clock or av.bar_clock()
    universe = set(universe_doc) if universe_doc else None
    obs, census = av.observations(rows, basis="first_seen", universe=universe)
    net = av.daily_net(obs)
    net_b = av.daily_net(obs, by_broker=True)
    vend, vcensus = av.observations(rows, basis="vendor_dated", universe=universe)
    vnet = av.daily_net(vend)
    targets = sorted({o.target for o in [*net, *vnet]})
    bench = _bench_map(targets, universe_doc)
    bars = daily_bars(sorted({*targets, *bench.values()}), loader)
    tracked, tcensus = av.track(net, bars, bench=bench, clock=clock)
    tracked_b, _ = av.track(net_b, bars, bench=bench, clock=clock)
    vtracked, _ = av.track(vnet, bars, bench=bench, clock=clock)
    contract = av.placebo_contract(net, bars, horizon=CONTRACT_HORIZON_D, clock=clock,
                                   n_placebo=n_placebo)
    return {
        "observations": {"views_with_direction_first_seen": len(obs), "daily_net": len(net),
                         "refused": census, "tracked": len(tracked), "tracker": tcensus,
                         "bars_held": sorted(k for k, v in bars.items() if v is not None)},
        "by_source": av.aggregate(tracked, ("source",)),
        "by_broker": av.aggregate(tracked_b, ("source", "broker")),
        "by_group": av.aggregate(tracked, ("target", "source", "relation", "lead")),
        "by_relation": av.aggregate(tracked, ("source", "relation")),
        "contract": contract,
        "research_only_vendor_dated": {
            "rule": ("NOT POINT-IN-TIME FOR THIS DESK: returns from the vendor's own published_at "
                     "(+ precision lag) on views first seen later. Research reading only; it feeds "
                     "no cell, no axis, no allocation intel and no contract verdict"),
            "refused": vcensus, "n_daily": len(vnet),
            "by_source": av.aggregate(vtracked, ("source",))},
    }


# ------------------------------------------------------------------------------ direct cells
def cell_rows(by_group: Sequence[Mapping[str, Any]], contract: Mapping[str, Any], *,
              limit: int = MAX_DONATIONS) -> tuple[list[dict[str, Any]], int, list[dict[str, Any]]]:
    """(candidates, trials charged, refusals). One cell per (target, source, relation, lead): its
    strongest horizon, when |t| clears Bonferroni over every measured (group, horizon) and 2.0."""
    measured: list[tuple[Mapping[str, Any], int, Mapping[str, Any]]] = []
    for g in by_group:
        for h in av.HORIZONS_D:
            s = g.get(f"{h}d") or {}
            if s.get("status") == "MEASURED" and s.get("t") is not None:
                measured.append((g, h, s))
    trials = len(measured)
    bar = max(PROPOSE_T, _bonferroni_t(trials))
    best: dict[tuple[str, ...], tuple[Mapping[str, Any], int, Mapping[str, Any]]] = {}
    for g, h, s in measured:
        if abs(float(s["t"])) < bar:
            continue
        key = (str(g["target"]), str(g["source"]), str(g["relation"]), str(g["lead"]))
        if key not in best or abs(float(s["t"])) > abs(float(best[key][2]["t"])):
            best[key] = (g, h, s)
    out: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []
    for (target, src, relation, lead), (_g, h, s) in sorted(
            best.items(), key=lambda kv: -abs(float(kv[1][2]["t"]))):
        if len(out) >= limit:
            refused.append({"cell": f"{target}|{src}|{relation}|{lead}",
                            "why": f"over the {limit}-donation pass limit; it leads next pass"})
            continue
        side = 1 if float(s["mean_bp"]) > 0 else -1
        family = "analyst_revision_drift" if relation == "direct" else "analyst_cross_market_lead"
        params: dict[str, Any] = {"symbol": target, "source": src, "side": side, "hold_days": h,
                                  "atr_n": 20, "stop_atr": 3.0, "rr": 1.5}
        if relation == "lead":
            params["lead"] = lead
        meta = SOURCES.get(src, {})
        culture = {k: meta.get(k) for k in ("source_culture", "participant_structure",
                                            "failure_mode_hypothesis", "crowding_prior")}
        cell = hashlib.sha256(json.dumps([target, family, params], sort_keys=True).encode()
                              ).hexdigest()[:16]
        verdict = (contract.get(src) or {}).get("status", UNMEASURED)
        mech = (f"{MECHANISM}. {src} views "
                + ("about" if relation == "direct"
                   else f"in lead group {lead} (another market) for")
                + f" {target}: signed {h}d CAR mean {s['mean_bp']}bp, t={s['t']}, n={s['n']} "
                  f"daily-netted first-seen events; side {side:+d} is the MEASURED sign")
        out.append({
            "source": SOURCE, "kind": "hypothesis", "symbol": target, "symbols": [target],
            "family": family, "params": params, "cell": cell,
            "url": str(meta.get("url") or ""),
            "title": f"{family} {target} <- {src}{'/' + lead if lead else ''} {h}d"[:120],
            "mechanism": mech[:400], "payer": PAYER, "constraint": CONSTRAINT, **culture,
            "structured": {"actor": PAYER, "constraint": CONSTRAINT,
                           "counterparty": "the analyst's early readers",
                           "mechanism": MECHANISM,
                           "why_edge_can_persist": "attention and arbitrage limits (above)",
                           "asset_mapping": f"{src} -> {target} ({relation})",
                           "horizon": f"{h}d", "session": "all",
                           "required_data": "desks/mt5/data/alpha_capture/analyst_views.jsonl",
                           "pit_status": "PIT_CLEAN", "expected_cost": UNMEASURED,
                           "falsifier": "placebo-shifted publication dates show the same drift",
                           "source": src, "language": str(meta.get("language") or "")},
            "provenance": {"organ": "research/alpha_capture.py", "source_id": src,
                           "relation": relation, "lead": lead, **culture},
            "declared_width": trials,
            "evidence": {"n": s["n"], "t": s["t"], "mean_bp": s["mean_bp"], "sd_bp": s["sd_bp"],
                         "hit": s["hit"], "horizon_d": h, "bonferroni_t": round(bar, 3),
                         "trials": trials, "contract_status": verdict,
                         "screen": "signed CAR after first_seen_at, daily-netted, Bonferroni "
                                   "over every measured (group, horizon)"}})
    return out, trials, refused


def _donate(candidates: list[dict[str, Any]], tests_run: int) -> Any:
    """The seam: one import, one call, so a test can watch what leaves."""
    from research.proposer_common import donate
    return donate(SOURCE, candidates, tests_run)


# ------------------------------------------------------------------------------ axis + intel
def axis_doc(rows: Sequence[Mapping[str, Any]], universe: set[str] | None, now: datetime
             ) -> dict[str, Any]:
    days = av.rows_by_day(rows, universe=universe)
    axis_rows = [{k: r[k] for k in ("symbol", "knowable_at", "as_of", "n_views", "net_breadth",
                                    "n_views_21d", "breadth_21d")} for r in days]
    return {"axis": "analyst_views", "id": "analyst_views", "source": "research/alpha_capture.py",
            "at": now.isoformat(timespec="seconds"),
            "status": "present" if axis_rows else UNMEASURED,
            "shape": "rows keyed by symbol + knowable_at (first_seen basis): net analyst breadth "
                     "per instrument per day and over the trailing 21 days",
            "pit_rule": "knowable_at = the latest first-seen knowable instant in the day; "
                        "backfilled views are absent, never back-dated",
            "n_rows": len(axis_rows), "symbols": sorted({r["symbol"] for r in axis_rows}),
            "rows": axis_rows}


def intel_doc(rows: Sequence[Mapping[str, Any]], measured: Mapping[str, Any],
              universe: set[str] | None, now: datetime) -> dict[str, Any]:
    days = av.rows_by_day(rows, universe=universe)
    per: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in days:
        per[str(r["symbol"])].append(r)
    groups = defaultdict(list)
    for g in measured.get("by_group") or []:
        groups[str(g.get("target"))].append(g)
    out: dict[str, Any] = {}
    cutoff = (now - timedelta(days=30)).date().isoformat()
    for sym in sorted(set(per) | set(groups)):
        recent = [r for r in per.get(sym, []) if str(r["as_of"]) >= cutoff]
        out[sym] = {
            "latest": (per[sym][-1] if per.get(sym) else None),
            "days_30": recent,
            "measured_drift": [{k: g.get(k) for k in ("source", "relation", "lead", "n_up",
                                                       "n_down", "1d", "5d", "21d")}
                               for g in groups.get(sym, [])] or UNMEASURED}
    return {"at": now.isoformat(timespec="seconds"), "kind": "evidence",
            "basis": "first_seen", "producer": "research/alpha_capture.py",
            "rule": ("ADVISORY. Per instrument, per day: first-seen analyst breadth and the "
                     "tracker's measured post-publication drift. Nothing here sizes, caps or "
                     "vetoes; an allocator that reads it must prove the tilt raises forward "
                     "E[log W] (Rule 1) and apply it two-sided"),
            "contract": {k: v.get("status") for k, v in (measured.get("contract") or {}).items()},
            "n_instruments": len(out), "instruments": out}


def roster_rows() -> list[dict[str, Any]]:
    """The roster rows for the shared sources.yaml, one per source."""
    out = []
    for sid, m in SOURCES.items():
        out.append({"id": sid, "name": m["name"], "url": m["url"], "region": m["region"],
                    "language": m["language"], "cadence": f"{int(m['cadence_s']) // 60}m",
                    "auth": m["auth"], "licence": m["licence"], "cursor": m["cursor"],
                    "pit": m["pit"], "uses": list(m["uses"]),
                    "consumer": "desks/mt5/research/alpha_capture.py",
                    "status": UNMEASURED_LIVE_YIELD,
                    **{k: m[k] for k in ("source_culture", "participant_structure",
                                         "failure_mode_hypothesis", "crowding_prior")}})
    return out


# ------------------------------------------------------------------------------ the organ
def run(*, budget_s: float = 300.0, apply: bool = True, collect_enabled: bool = True,
        now: datetime | None = None, get: Getter | None = None,
        loader: Callable[[str], Any] | None = None, clock: av.Clock | None = None,
        universe_doc: Mapping[str, Any] | None = None, only: Sequence[str] | None = None,
        n_placebo: int = 200, yahoo_opener: Any = None) -> dict[str, Any]:
    """One pass. Returns the report; writes only when `apply`."""
    started = time.monotonic()
    now = now or _now()
    store = av.AnalystViewStore(STORE)
    if collect_enabled:
        views, col, state = collect(now=now, budget_s=budget_s * 0.6, get=get, only=only,
                                    yahoo_opener=yahoo_opener)
    else:
        views, col, state = [], {s: {"status": "SKIPPED"} for s in SOURCES}, None
    history = store.rows()
    filled = av.fill_prior(views, history)
    stored = (store.append(views, now=now) if (apply and views) else
              {"added": 0, "revised": 0, "unchanged": 0, "refused_unstamped": 0,
               "dry_run": not apply})
    if apply and state is not None:
        _atomic(STATE, json.dumps(state, indent=1, default=str))
    rows = store.rows() if apply else [*history, *[
        {**asdict(v), "first_seen_at": now.isoformat(timespec="seconds")} for v in views]]
    udoc = universe_doc if universe_doc is not None else _read_json(UNIVERSE, {})
    universe = set(udoc) if udoc else None
    measured = measure(rows, loader=loader or _bars_loader(), universe_doc=udoc, clock=clock,
                       n_placebo=n_placebo)
    cands, trials, refused = cell_rows(measured["by_group"], measured["contract"])
    path = _donate(cands, max(trials, len(cands))) if (apply and cands) else None
    axis = axis_doc(rows, universe, now)
    intel = intel_doc(rows, measured, universe, now)
    per_source: dict[str, Any] = {}
    counts = Counter(str(r.get("source")) for r in rows)
    for sid in SOURCES:
        rep = col.get(sid) or {}
        live = (rep.get("status") == "FETCHED")
        per_source[sid] = {
            **rep, "rows_in_store": counts.get(sid, 0),
            "live_yield": ({"status": "MEASURED", "views_parsed": rep.get("views_parsed"),
                            "at": now.isoformat(timespec="seconds")} if live else
                           {"status": UNMEASURED_LIVE_YIELD,
                            "why": "no successful fetch on this pass; yield is measured only "
                                   "where the source was actually reached"}),
            "uses": SOURCES[sid]["uses"]}
    report = {
        "at": now.isoformat(timespec="seconds"), "source": SOURCE,
        "elapsed_s": round(time.monotonic() - started, 2),
        "rule": ("every view is stamped at first_seen_at; every return starts after it; a "
                 "backfilled view is stored and never an observation; absence is UNMEASURED"),
        "sources": per_source,
        "store": {**stored, "rows_total": len(rows), "prior_filled": filled,
                  "path": str(STORE)},
        "observations": measured["observations"],
        "by_source": measured["by_source"], "by_relation": measured["by_relation"],
        "by_broker": sorted(measured["by_broker"],
                            key=lambda g: -int((g.get("5d") or {}).get("n") or 0))[:60],
        "contract": measured["contract"],
        "research_only_vendor_dated": measured["research_only_vendor_dated"],
        "cells": {"trials_charged": trials, "candidates": len(cands),
                  "donated": len(cands) if path else 0, "path": str(path) if path else None,
                  "refused": refused[:20],
                  "status": ("donated" if path else
                             "nothing cleared the screen yet: first-seen history accrues one "
                             "pass at a time" if not cands else "dry run")},
        "indirect": {"axis": str(AXIS), "n_rows": axis["n_rows"], "status": axis["status"]},
        "allocation_intel": {"path": str(INTEL), "n_instruments": intel["n_instruments"]},
    }
    contract_doc = {"at": report["at"], "rule": (
        "SUBSYSTEM ADMISSION: per source, the t-statistic of signed +5-trading-day returns after "
        "first-seen views against a placebo of the same views at randomly shifted dates. ADMIT "
        "when n >= 12, |t| >= 2 and placebo p <= 0.05; below the floor the verdict is "
        "UNMEASURED, never a pass"), "sources": measured["contract"],
        "unmeasured_sources": sorted(s for s in SOURCES if s not in measured["contract"])}
    if apply:
        _atomic(AXIS, json.dumps(axis, indent=1, ensure_ascii=False))
        _atomic(INTEL, json.dumps(intel, indent=1, ensure_ascii=False, default=str))
        _atomic(CONTRACT, json.dumps(contract_doc, indent=1, default=str))
        _atomic(REPORT, json.dumps(report, indent=1, ensure_ascii=False, default=str))
    report["contract_doc"] = contract_doc
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the Alpha Capture substitute: analyst views")
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--dry-run", action="store_true", help="measure and print; write nothing")
    ap.add_argument("--no-collect", action="store_true", help="fetch nothing; measure the store")
    ap.add_argument("--sources", default="", help="comma list of source ids to fetch")
    ap.add_argument("--roster", action="store_true", help="print the roster rows as JSON")
    a = ap.parse_args(argv)
    if a.roster:
        print(json.dumps(roster_rows(), indent=1, ensure_ascii=False))
        return 0
    only = [s for s in a.sources.split(",") if s] or None
    rep = run(budget_s=a.budget_s, apply=not a.dry_run,
              collect_enabled=not a.no_collect and not a.dry_run, only=only)
    print(f"alpha_capture at={rep['at']} elapsed={rep['elapsed_s']}s")
    for sid, s in rep["sources"].items():
        print(f"  {sid:18} {s.get('status', '?'):12} parsed={s.get('views_parsed', 0)} "
              f"store={s['rows_in_store']} yield={s['live_yield']['status']}")
    st = rep["store"]
    print(f"  store      +{st['added']} new, {st['revised']} revised, {st['rows_total']} rows")
    ob = rep["observations"]
    print(f"  tracked    {ob['tracked']} daily events of {ob['daily_net']}; "
          f"refused {ob['refused']}")
    for src, c in rep["contract"].items():
        print(f"  contract   {src:18} {c.get('status')} n={c.get('n')} t={c.get('t')} "
              f"p={c.get('p_placebo', '-')}")
    print(f"  cells      {rep['cells']['candidates']} candidate(s), trials "
          f"{rep['cells']['trials_charged']}, donated {rep['cells']['donated']}")
    print(f"  axis       {rep['indirect']['n_rows']} row(s) -> {AXIS.name}")
    print(f"  intel      {rep['allocation_intel']['n_instruments']} instrument(s) -> {INTEL.name}")
    return 0


if __name__ == "__main__":                                       # pragma: no cover - CLI
    raise SystemExit(main())
