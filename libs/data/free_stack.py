"""THE FREE STACK -- fetchers and parsers for the public alt-data sources the Asia gap report
measured MISSING on 2026-09-30 (`reports/asia_quant_gap_2026-09-30.md`, rows 14-17 and 20).

WHAT IS HERE, one fetcher per source row of `desks/mt5/data/free_stack_sources.json`:

    app_rank_apple     Apple's public marketing RSS top charts, per country and chart -- a
                       point-in-time archive of consumer app rankings (the MoonFox method:
                       snapshot the public ranking every day, never backfill it), mapped from
                       publisher to listed company to share CFD and index proxy
    cn_weibo / cn_xueqiu / cn_zhihu / cn_guba
                       CN retail forum posts per instrument keyword, bot-filtered (HKMA-style
                       account and content heuristics), scored with SnowNLP when importable and
                       a DECLARED LEXICON FALLBACK otherwise, aggregated to a weekly per-ticker
                       sentiment index
    jp_ir_transcripts  JP investor-relations pages: transcript / Q&A links, tone and its delta
                       against the company's previous call
    jp_patents         JP patent publications from a bulk file the box holds (JPO / IIP bulk
                       data), clustered by IPC subclass, momentum per applicant company
    gtrends            Google Trends interest over time via the public widget API (the route
                       `pytrends` wraps -- pytrends is not in the requirements files)
    congress_house / congress_stockwatcher
                       US House periodic-transaction-report filings (the Clerk's public
                       index) and the community transaction mirror
    coinpaprika        keyless coin market data, for Fusion's crypto CFDs ONLY -- the bases are
                       read off the broker registry, never an exchange universe
    reddit / telegram  public subreddit listings and public channel web previews, as datasets of
                       per-instrument mention counts and tone
    akshare_direct     the public upstreams AKShare wraps (Eastmoney index klines, Sina futures
                       klines) fetched directly; AKShare itself when it is importable
    tushare            the TuShare Pro HTTP API, token from the box environment
    baostock / jqdatasdk
                       their own client packages only (neither is in the requirements files)
    catalogue          open dataset catalogues (awesome-* lists, AltData.wiki, Brickroad's
                       public index) parsed into dataset candidates

NOTHING HERE PRINTS OR STORES A CREDENTIAL, and nothing here stores a person: forum authors are
reduced to a salted hash used only by the bot filter, and only AGGREGATES leave this module.

EVERY FETCHER RETURNS THE SAME SHAPE -- `Harvest` -- so the hunter needs no branch per source:
observations (key, period_end, value), the columns' target instruments, raw rows kept for the
point-in-time archive, and cursor updates. A fetcher that cannot run says WHY in `status`
(NEEDS_CREDENTIAL, NOT_INSTALLED, BLOCKED, NO_ROUTE) and returns no numbers -- never a zero.
"""
from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import math
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from typing import Any

from libs.ops.env_keys import read_key

UNMEASURED = "UNMEASURED"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Safari/537.36 quant-desk-free-stack/1.0 (research)")
HTTP_TIMEOUT_S = 25.0
MAX_BYTES = 40 * 1024 * 1024

#: fetch(url, headers, body) -> bytes. Injected so every fetcher runs on recorded fixtures.
Fetch = Callable[[str, Mapping[str, str] | None, bytes | None], bytes]


class FetchError(RuntimeError):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}"[:300])
        self.reason = reason
        self.detail = detail


def classify(exc: BaseException) -> str:
    """One word for why a request failed, so a yield row can be grouped and argued with."""
    if isinstance(exc, FetchError):
        return exc.reason
    if isinstance(exc, urllib.error.HTTPError):
        return f"http_{exc.code}"
    text = f"{type(exc).__name__} {exc}".lower()
    for needle, label in (("timed out", "timeout"), ("timeout", "timeout"),
                          ("name or service", "dns"), ("getaddrinfo", "dns"),
                          ("certificate", "tls"), ("ssl", "tls"), ("refused", "refused"),
                          ("reset", "reset"), ("tunnel", "proxy"), ("proxy", "proxy")):
        if needle in text:
            return label
    return type(exc).__name__


def http_fetch(url: str, headers: Mapping[str, str] | None = None,
               body: bytes | None = None) -> bytes:
    """The live transport. urllib only: `requests` is pinned but adds nothing here."""
    hdr = {"User-Agent": UA, "Accept": "*/*"}
    hdr.update(dict(headers or {}))
    req = urllib.request.Request(url, headers=hdr, data=body,
                                 method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            raw: bytes = resp.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise FetchError(f"http_{exc.code}", url) from exc
    except Exception as exc:
        raise FetchError(classify(exc), url) from exc
    if len(raw) > MAX_BYTES:
        raise FetchError("too_large", url)
    return raw


@dataclass
class Harvest:
    """What one fetch produced. `status` OK means at least one observation or raw row landed."""
    source_id: str
    status: str = "OK"
    detail: str = ""
    #: {"key", "period_end" (ISO date or datetime), "value"} -- numbers only
    obs: list[dict[str, Any]] = field(default_factory=list)
    #: column key -> {"hypothesis": [...symbols], "event": [...share CFDs], "why": str}
    columns: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: rows kept verbatim (minus personal fields) for the point-in-time archive
    raw: list[dict[str, Any]] = field(default_factory=list)
    #: per-source cursor fields to persist (seen ids, last page, ...)
    cursor: dict[str, Any] = field(default_factory=dict)
    requests: int = 0
    failures: Counter[str] = field(default_factory=Counter)
    notes: list[str] = field(default_factory=list)
    #: catalogue fetchers: discovered dataset candidates
    datasets: list[dict[str, Any]] = field(default_factory=list)


def _get(fetch: Fetch, h: Harvest, url: str, headers: Mapping[str, str] | None = None,
         body: bytes | None = None) -> bytes | None:
    h.requests += 1
    try:
        return fetch(url, headers, body)
    except Exception as exc:
        h.failures[classify(exc)] += 1
        h.notes.append(f"{classify(exc)}: {url[:120]}")
        return None


def _json(raw: bytes | None) -> Any:
    if not raw:
        return None
    text = raw.decode("utf-8", "replace").strip()
    if text.startswith(")]}'"):                 # Google's XSSI guard
        text = text.split("\n", 1)[1] if "\n" in text else text[5:]
    m = re.match(r"^[\w$.\s=]*\((.*)\)\s*;?\s*$", text, re.S)   # JSONP
    if m and not text.startswith(("{", "[")):
        text = m.group(1)
    try:
        return json.loads(text)
    except ValueError:
        return None


def _text(raw: str) -> str:
    """Strip tags, THEN decode entities (decoding first turns &lt;em&gt; into a real tag)."""
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw))).strip()


def _day(ts: datetime) -> str:
    return ts.astimezone(UTC).date().isoformat()


def _week_end(d: date) -> date:
    """The Sunday closing the ISO week that holds `d`."""
    return d + timedelta(days=6 - d.weekday())


def author_hash(name: Any) -> str:
    """A person reduced to 12 hex characters, salted per box. Used by the bot filter only."""
    salt = os.environ.get("QUANT_AUTHOR_SALT", "free-stack")
    return hashlib.sha256(f"{salt}|{name}".encode()).hexdigest()[:12]


# ================================================================ instrument fact tables
#: US ticker -> the broker's share-CFD name. A FACT TABLE (a ticker is a fact about a company),
#: not a universe: which rows reach an instrument is decided against the registry at run time.
TICKER_CFD: dict[str, str] = {
    "MMM": "3M", "ADP": "ADP", "AMD": "AMD", "T": "AT&T", "ACN": "Accenture", "ADBE": "Adobe",
    "ABNB": "Airbnb", "BABA": "AlibabaGroup", "GOOGL": "Alphabet-A", "GOOG": "Alphabet-C",
    "AMZN": "Amazon", "AXP": "AmericanExpress", "AMGN": "Amgen", "AAPL": "Apple",
    "AMAT": "AppliedMaterials", "TEAM": "Atlassian", "BIDU": "Baidu",
    "BAC": "BankofAmericaCorp", "BRK.B": "Berkshire", "BLK": "BlackRock", "BA": "Boeing",
    "BKNG": "Booking", "AVGO": "Broadcom", "CVS": "CVSHealth", "CAT": "Caterpillar",
    "SCHW": "CharlesSchwab", "CHTR": "Charter", "CVX": "Chevron", "CSCO": "Cisco",
    "C": "Citigroup", "KO": "Coca-Cola", "COIN": "Coinbase", "CMCSA": "Comcast",
    "COST": "CostcoWholesale", "DOCU": "DocuSign", "DASH": "Doordash", "DOW": "Dow",
    "EA": "ElectronicArts", "XOM": "ExxonMobil", "F": "Ford", "GE": "GeneralElectric",
    "GM": "GeneralMotors", "GILD": "GileadSciences", "GS": "GoldmanSachs", "HD": "HomeDepot",
    "HON": "Honeywell", "IBM": "IBM", "INTC": "Intel", "INTU": "Intuit",
    "ISRG": "IntuitiveSurgical", "JPM": "JPMorganChase", "JNJ": "Johnson&Johnson",
    "LCID": "LucidGroup", "LYFT": "Lyft", "MA": "Mastercard", "MCD": "McDonalds",
    "MDT": "Medtronic", "MRK": "Merck", "META": "Meta", "MU": "MicronTechnology",
    "MSFT": "Microsoft", "MS": "MorganStanley", "NIO": "NIO", "NVDA": "NVIDIA",
    "NFLX": "Netflix", "NKE": "Nike", "ORCL": "Oracle", "PYPL": "PayPal", "PEP": "Pepsi",
    "PFE": "Pfizer", "PM": "PhilipMorrisInternational", "PINS": "Pinterest",
    "PG": "Procter&Gamble", "QCOM": "Qualcomm", "HOOD": "RobinhoodMarkets", "ROKU": "Roku",
    "SPGI": "S&PGlobal", "CRM": "Salesforce", "NOW": "ServiceNow", "SHOP": "Shopify",
    "SNAP": "Snapchat", "SNOW": "Snowflake", "SPOT": "Spotify", "SBUX": "Starbucks",
    "TME": "TMEGroup", "TSM": "TSMC", "TGT": "Target", "TSLA": "Tesla",
    "TXN": "TexasInstruments", "TMO": "ThermoFisherScientific", "TM": "Toyota",
    "TRV": "Travelers", "TWLO": "Twilio", "UBER": "Uber", "UNP": "UnionPacific",
    "UNH": "UnitedHealth", "UPS": "UnitedParcelService", "VZ": "Verizon", "V": "Visa",
    "WMT": "Walmart", "DIS": "WaltDisney", "WFC": "WellsFargo", "EBAY": "eBay",
}
CFD_TICKER: dict[str, str] = {v: k for k, v in TICKER_CFD.items()}

#: Where a company's information is expressed in the HYPOTHESIS lane (share CFDs are event-lane
#: instruments; the two-lane order routes their statistical cells to an index or FX proxy).
HOME_PROXIES: dict[str, tuple[str, ...]] = {
    "us": ("US500", "NAS100"), "us_old": ("US500", "US30"), "cn": ("CHINAH", "HK50", "USDCNH"),
    "jp": ("JPN225", "USDJPY"), "tw": ("NAS100",), "hk": ("HK50", "CHINAH"),
    "kr": ("NAS100",),
}
_CN_CFDS = {"AlibabaGroup", "Baidu", "NIO", "TMEGroup"}
_OLD_ECONOMY = {"3M", "Boeing", "Caterpillar", "Chevron", "Coca-Cola", "Dow", "ExxonMobil",
                "GoldmanSachs", "HomeDepot", "Honeywell", "IBM", "JPMorganChase",
                "Johnson&Johnson", "McDonalds", "Merck", "Nike", "Procter&Gamble", "Travelers",
                "UnitedHealth", "Verizon", "Visa", "Walmart", "WaltDisney", "AmericanExpress"}


def proxies_for_company(cfd: str | None, home: str | None = None) -> tuple[str, ...]:
    if home:
        return HOME_PROXIES.get(home, ())
    if not cfd:
        return ()
    if cfd in _CN_CFDS:
        return HOME_PROXIES["cn"]
    if cfd == "Toyota":
        return HOME_PROXIES["jp"]
    if cfd == "TSMC":
        return HOME_PROXIES["tw"]
    if cfd in _OLD_ECONOMY:
        return HOME_PROXIES["us_old"]
    return HOME_PROXIES["us"]


# ======================================================================= sentiment
#: THE LEXICON FALLBACK, DECLARED. SnowNLP is not in the requirements files; when it is not
#: importable every Chinese score carries method "lexicon_cn_v1" so no reader mistakes it for
#: SnowNLP's naive-Bayes sentiment. Terms are the retail-forum vocabulary of bull and bear.
CN_POS: tuple[str, ...] = ("涨", "大涨", "看多", "做多", "利好", "牛", "突破", "买入", "加仓",
                           "反弹", "强势", "新高", "抄底", "起飞", "稳了", "满仓", "上攻", "拉升",
                           "爆发", "超预期", "增持", "红了", "吃肉")
CN_NEG: tuple[str, ...] = ("跌", "大跌", "看空", "做空", "利空", "熊", "暴跌", "卖出", "减仓",
                           "跳水", "割肉", "崩", "新低", "套牢", "清仓", "破位", "下跌", "亏",
                           "绿了", "爆雷", "减持", "不及预期", "腰斩", "闪崩")
#: English finance tone words (a compact Loughran-McDonald-style list, declared here).
EN_POS: frozenset[str] = frozenset(
    ["beat", "beats", "bullish", "buy", "calls", "gain", "gains", "growth", "improve",
     "improved", "improving", "moon", "outperform", "positive", "rally", "record", "robust",
     "rose", "soar", "soared", "strong", "stronger", "surge", "surged", "upgrade", "upside",
     "accelerate", "accelerating", "exceed", "exceeded", "expand", "expansion", "favorable",
     "momentum", "pump", "rip", "breakout", "higher", "long"])
EN_NEG: frozenset[str] = frozenset(
    ["bearish", "crash", "decline", "declined", "declining", "downgrade", "dump", "fall", "fell",
     "loss", "losses", "miss", "missed", "negative", "plunge", "plunged", "puts", "recession",
     "risk", "sell", "selloff", "short", "slump", "weak", "weaker", "worse", "headwind",
     "headwinds", "impairment", "uncertainty", "uncertain", "lower", "decrease", "decreased",
     "challenging", "difficult", "deteriorate", "deteriorating", "bagholder", "rekt", "tank",
     "tanked"])
EN_UNCERTAIN: frozenset[str] = frozenset(
    ["approximately", "assume", "believe", "could", "depend", "depends", "may", "might",
     "possible", "possibly", "perhaps", "uncertain", "uncertainty", "unclear", "unknown",
     "volatile", "volatility", "risk", "risks"])
#: Russian market-channel tone stems (declared, compact), for the RU Telegram channels.
RU_POS: tuple[str, ...] = ("рост", "вырос", "растет", "растёт", "позитив", "покупк", "подорож",
                           "укреп", "ралли", "максимум")
RU_NEG: tuple[str, ...] = ("паден", "упал", "снижен", "негатив", "продаж", "обвал", "подешев",
                           "ослаб", "минимум", "санкци")
#: Japanese IR tone words (declared, compact): improvement / growth vs decline / severe.
JA_POS: tuple[str, ...] = ("増収", "増益", "上方修正", "好調", "回復", "成長", "拡大", "過去最高",
                           "改善", "順調", "堅調", "伸長")
JA_NEG: tuple[str, ...] = ("減収", "減益", "下方修正", "低迷", "悪化", "縮小", "厳しい", "減速",
                           "赤字", "損失", "不透明", "懸念")


def lexicon_counts(text: str, pos_terms: Sequence[str], neg_terms: Sequence[str]
                   ) -> tuple[int, int]:
    """LONGEST MATCH FIRST, each character counted once: "暴跌" is one bearish word, not "暴跌"
    plus the "跌" inside it, and "不及预期" is not also a "预期"."""
    terms = sorted([(t, 1) for t in pos_terms] + [(t, -1) for t in neg_terms],
                   key=lambda x: -len(x[0]))
    pos = neg = 0
    for term, sign in terms:
        n = text.count(term)
        if n:
            text = text.replace(term, " ")
            if sign > 0:
                pos += n
            else:
                neg += n
    return pos, neg


def snownlp_available() -> bool:
    import importlib.util
    try:
        return importlib.util.find_spec("snownlp") is not None
    except (ImportError, ValueError):
        return False


def sentiment_cn(text: str) -> tuple[float, str]:
    """(score in [-1, 1], method). SnowNLP when importable, the declared lexicon otherwise."""
    if snownlp_available():
        try:
            from snownlp import SnowNLP  # type: ignore[import-not-found]
            return float(SnowNLP(text).sentiments) * 2.0 - 1.0, "snownlp"
        except Exception:
            pass
    pos, neg = lexicon_counts(text, CN_POS, CN_NEG)
    if pos + neg <= 0:
        return 0.0, "lexicon_cn_v1"
    return (pos - neg) / (pos + neg), "lexicon_cn_v1"


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z][a-z']+", text.lower())


def tone_en(text: str) -> dict[str, float]:
    w = _words(text)
    pos = sum(1 for x in w if x in EN_POS)
    neg = sum(1 for x in w if x in EN_NEG)
    unc = sum(1 for x in w if x in EN_UNCERTAIN)
    n = max(1, len(w))
    return {"tone": (pos - neg) / max(1, pos + neg), "pos": pos, "neg": neg,
            "uncertainty": unc / n, "words": len(w)}


def tone_social(text: str) -> tuple[float, str]:
    """English lexicon plus the Russian stems: one tone for a multilingual channel."""
    t = tone_en(text)
    rp, rn = lexicon_counts(text.lower(), RU_POS, RU_NEG)
    pos, neg = int(t["pos"]) + rp, int(t["neg"]) + rn
    return (pos - neg) / max(1, pos + neg), "lexicon_en_ru_v1"


def tone_ja(text: str) -> dict[str, float]:
    pos, neg = lexicon_counts(text, JA_POS, JA_NEG)
    return {"tone": (pos - neg) / max(1, pos + neg), "pos": pos, "neg": neg,
            "uncertainty": text.count("不透明") / max(1, len(text) / 100), "words": len(text)}


# ======================================================================= bot filter
#: HKMA-STYLE BOT AND SPAM FILTER. The HKMA's social-media sentiment work drops accounts and
#: posts whose behaviour is not an investor's: promotional contact bait, copy-paste floods,
#: follower-starved high-volume accounts, and posts with no content. Each rule is a named reason
#: and every drop is counted, so the kept share is a published number, never a silent filter.
PROMO = ("加微信", "加v", "加V", "vx", "VX", "微信号", "私信", "荐股", "带单", "进群", "群号",
         "扫码", "免费领", "内部消息", "牛股推荐", "telegram.me", "t.me/", "whatsapp", "dm me",
         "join my", "signal group", "free signals", "promo code", "referral")


def bot_filter(posts: Sequence[Mapping[str, Any]], *, flood_copies: int = 3,
               max_per_author: int = 20) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """(kept posts, drop counts by reason). Posts carry text, author (hashed), and optionally
    followers / statuses (account totals) when the platform exposes them."""
    norm = [re.sub(r"\W+", "", str(p.get("text") or "").lower())[:120] for p in posts]
    copies = Counter(n for n in norm if n)
    per_author = Counter(str(p.get("author") or "") for p in posts)
    kept: list[dict[str, Any]] = []
    why: Counter[str] = Counter()
    for p, n in zip(posts, norm, strict=True):
        text = str(p.get("text") or "")
        low = text.lower()
        followers = p.get("followers")
        statuses = p.get("statuses")
        if len(n) < 4:
            why["empty_or_too_short"] += 1
        elif any(k.lower() in low for k in PROMO):
            why["promotional_contact_bait"] += 1
        elif copies[n] >= flood_copies:
            why["copy_paste_flood"] += 1
        elif (isinstance(followers, (int, float)) and isinstance(statuses, (int, float))
              and followers < 10 and statuses > 5000):
            why["follower_starved_high_volume"] += 1
        elif per_author[str(p.get("author") or "")] > max_per_author and p.get("author"):
            why["author_burst"] += 1
        elif len(re.findall(r"https?://", low)) >= 3 or low.count("#") >= 6:
            why["link_or_hashtag_spam"] += 1
        else:
            kept.append(dict(p))
            continue
    stats = dict(why)
    stats["seen"] = len(posts)
    stats["kept"] = len(kept)
    return kept, stats


def bullishness(pos: int, neg: int) -> float:
    """Antweiler-Frank bullishness: ln((1 + bull) / (1 + bear))."""
    return math.log((1.0 + pos) / (1.0 + neg))


# ==================================================================== 1. app rankings
APPLE_RSS = "https://rss.applemarketingtools.com/api/v2/{cc}/apps/{chart}/100/apps.json"
APP_COUNTRIES: tuple[str, ...] = ("us", "cn", "jp", "kr", "gb", "de", "hk", "tw", "fr", "au")
APP_CHARTS: tuple[str, ...] = ("top-free", "top-paid")
#: publisher text -> (share CFD or None, home proxy region). Unlisted publishers are absent.
PUBLISHERS: tuple[tuple[str, str, str | None, str], ...] = (
    (r"\bgoogle\b", "Alphabet-A", "Alphabet-A", "us"),
    (r"\bmeta platforms|instagram|whatsapp|facebook", "Meta", "Meta", "us"),
    (r"\bmicrosoft", "Microsoft", "Microsoft", "us"),
    (r"\bamazon(?! web)", "Amazon", "Amazon", "us"),
    (r"^apple\b", "Apple", "Apple", "us"),
    (r"\bnetflix", "Netflix", "Netflix", "us"),
    (r"\bspotify", "Spotify", "Spotify", "us"),
    (r"\buber technologies|\buber\b", "Uber", "Uber", "us"),
    (r"\blyft", "Lyft", "Lyft", "us"),
    (r"\bairbnb", "Airbnb", "Airbnb", "us"),
    (r"\bbooking\.com|\bpriceline", "Booking", "Booking", "us"),
    (r"\bdoordash", "Doordash", "Doordash", "us"),
    (r"\bpaypal|\bvenmo", "PayPal", "PayPal", "us"),
    (r"\bebay", "eBay", "eBay", "us"),
    (r"\bsnap,? inc", "Snapchat", "Snapchat", "us"),
    (r"\bpinterest", "Pinterest", "Pinterest", "us"),
    (r"\brobinhood", "RobinhoodMarkets", "RobinhoodMarkets", "us"),
    (r"\bcoinbase", "Coinbase", "Coinbase", "us"),
    (r"\broku", "Roku", "Roku", "us"),
    (r"\bshopify", "Shopify", "Shopify", "us"),
    (r"\bwalmart", "Walmart", "Walmart", "us"),
    (r"\btarget corp", "Target", "Target", "us"),
    (r"\bstarbucks", "Starbucks", "Starbucks", "us"),
    (r"\bmcdonald", "McDonalds", "McDonalds", "us"),
    (r"\bnike", "Nike", "Nike", "us"),
    (r"\bdisney", "WaltDisney", "WaltDisney", "us"),
    (r"\belectronic arts", "ElectronicArts", "ElectronicArts", "us"),
    (r"\btesla", "Tesla", "Tesla", "us"),
    (r"\bintuit", "Intuit", "Intuit", "us"),
    (r"\bdocusign", "DocuSign", "DocuSign", "us"),
    (r"\bcomcast", "Comcast", "Comcast", "us"),
    (r"\bverizon", "Verizon", "Verizon", "us"),
    (r"\bat&t", "AT&T", "AT&T", "us"),
    (r"\bjpmorgan|\bchase\b", "JPMorganChase", "JPMorganChase", "us"),
    (r"\bbank of america", "BankofAmericaCorp", "BankofAmericaCorp", "us"),
    (r"\bwells fargo", "WellsFargo", "WellsFargo", "us"),
    (r"\bciti(group|bank)?\b", "Citigroup", "Citigroup", "us"),
    (r"\bamerican express", "AmericanExpress", "AmericanExpress", "us"),
    (r"\bcharles schwab", "CharlesSchwab", "CharlesSchwab", "us"),
    (r"\bcostco", "CostcoWholesale", "CostcoWholesale", "us"),
    (r"\bhome depot", "HomeDepot", "HomeDepot", "us"),
    (r"\bcvs\b", "CVSHealth", "CVSHealth", "us"),
    (r"\balibaba|\btaobao|\btmall|淘宝|阿里巴巴|天猫", "AlibabaGroup", "AlibabaGroup", "cn"),
    (r"\bbaidu|百度", "Baidu", "Baidu", "cn"),
    (r"\bnio\b|蔚来", "NIO", "NIO", "cn"),
    (r"\btencent music|腾讯音乐", "TMEGroup", "TMEGroup", "cn"),
    (r"\btoyota|トヨタ", "Toyota", "Toyota", "jp"),
    (r"\btencent|腾讯", "Tencent", None, "hk"),
    (r"\bnetease|网易", "Netease", None, "hk"),
    (r"\bmeituan|美团", "Meituan", None, "hk"),
    (r"\bjd\.com|京东", "Jdcom", None, "hk"),
    (r"\bpdd|pinduoduo|拼多多|temu", "Pdd", None, "us"),
    (r"\bnintendo|任天堂", "Nintendo", None, "jp"),
    (r"\bsony|ソニー", "Sony", None, "jp"),
    (r"\bline yahoo|\bly corporation|ＬＩＮＥヤフー", "Lineyahoo", None, "jp"),
    (r"\brakuten|楽天", "Rakuten", None, "jp"),
    (r"\bmercari|メルカリ", "Mercari", None, "jp"),
    (r"\bsquare enix|スクウェア", "Squareenix", None, "jp"),
    (r"\bbandai namco|バンダイナムコ", "Bandainamco", None, "jp"),
    (r"\bkonami|コナミ", "Konami", None, "jp"),
    (r"\bcyberagent|サイバーエージェント", "Cyberagent", None, "jp"),
    (r"\bmixi\b", "Mixi", None, "jp"),
    (r"\bkakao|카카오", "Kakao", None, "kr"),
    (r"\bnaver|네이버", "Naver", None, "kr"),
    (r"\bkrafton|크래프톤", "Krafton", None, "kr"),
    (r"\bnexon|넥슨", "Nexon", None, "jp"),
)
_PUB_RX = [(re.compile(rx, re.I), key, cfd, home) for rx, key, cfd, home in PUBLISHERS]


def publisher_company(artist: str) -> tuple[str, str | None, str] | None:
    """(company key, share CFD or None, home region) for a publisher name, else None."""
    for rx, key, cfd, home in _PUB_RX:
        if rx.search(artist or ""):
            return key, cfd, home
    return None


def parse_apple_rss(raw: bytes | None, country: str, chart: str) -> list[dict[str, Any]]:
    doc = _json(raw)
    results = (((doc or {}).get("feed") or {}).get("results")) if isinstance(doc, dict) else None
    out: list[dict[str, Any]] = []
    for i, r in enumerate(results or []):
        if not isinstance(r, dict):
            continue
        out.append({"country": country, "chart": chart, "rank": i + 1,
                    "app_id": str(r.get("id") or ""), "name": str(r.get("name") or "")[:120],
                    "artist": str(r.get("artistName") or "")[:120]})
    return out


def app_rank_scores(rows: Sequence[Mapping[str, Any]], n: int = 100
                    ) -> tuple[dict[str, float], dict[str, float], dict[str, dict[str, Any]]]:
    """(company score, home-index score, column meta). Score = sum over charts and countries of
    (n + 1 - rank) / n for every app the company publishes -- presence weighted by position."""
    comp: dict[str, float] = defaultdict(float)
    idx: dict[str, float] = defaultdict(float)
    meta: dict[str, dict[str, Any]] = {}
    for r in rows:
        hit = publisher_company(str(r.get("artist") or ""))
        if hit is None:
            continue
        key, cfd, home = hit
        w = (n + 1 - int(r.get("rank") or n)) / n
        col = f"co_{key}"
        comp[col] += w
        meta.setdefault(col, {"hypothesis": list(proxies_for_company(cfd, home if not cfd
                                                                          else None)),
                              "event": [cfd] if cfd else [],
                              "why": f"{key}'s consumer apps' chart presence"})
        for proxy in proxies_for_company(cfd, home if not cfd else None)[:1]:
            icol = f"idx_{proxy}"
            idx[icol] += w
            meta.setdefault(icol, {"hypothesis": [proxy], "event": [],
                                   "why": f"chart presence of {proxy}-home publishers"})
    return dict(comp), dict(idx), meta


def fetch_app_rank_apple(fetch: Fetch, row: Mapping[str, Any], cursor: Mapping[str, Any],
                         now: datetime) -> Harvest:
    h = Harvest(str(row["id"]))
    rows: list[dict[str, Any]] = []
    for cc in row.get("countries") or APP_COUNTRIES:
        for chart in row.get("charts") or APP_CHARTS:
            raw = _get(fetch, h, APPLE_RSS.format(cc=cc, chart=chart))
            rows.extend(parse_apple_rss(raw, cc, chart))
    if not rows:
        h.status = "BLOCKED"
        h.detail = "no chart parsed: " + ", ".join(f"{k}x{v}" for k, v in h.failures.items())
        return h
    comp, idx, meta = app_rank_scores(rows)
    day = _day(now)
    h.obs = [{"key": k, "period_end": day, "value": round(v, 5)}
             for k, v in {**comp, **idx}.items()]
    h.columns = meta
    h.raw = [{**r, "snapshot_utc": now.isoformat()} for r in rows]
    h.notes.append(f"{len(rows)} ranked apps from {len({(r['country'], r['chart']) for r in rows})}"
                   " charts")
    return h


# ============================================================= 2. CN forum sentiment
#: keyword -> (column ticker, hypothesis targets, event CFDs)
CN_TOPICS: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("阿里巴巴", "BABA", ("CHINAH", "HK50", "USDCNH"), ("AlibabaGroup",)),
    ("百度", "BIDU", ("CHINAH", "HK50"), ("Baidu",)),
    ("蔚来", "NIO", ("CHINAH", "HK50"), ("NIO",)),
    ("腾讯音乐", "TME", ("CHINAH", "HK50"), ("TMEGroup",)),
    ("恒生指数", "HSI", ("HK50",), ()),
    ("恒生国企", "HSCEI", ("CHINAH",), ()),
    ("人民币汇率", "CNH", ("USDCNH",), ()),
    ("黄金", "GOLD", ("XAUUSD",), ()),
    ("原油", "OIL", ("XTIUSD", "XBRUSD"), ()),
    ("美股", "USEQ", ("US500", "NAS100"), ()),
    ("日经", "N225", ("JPN225",), ()),
    ("比特币", "BTC", ("BTCUSD",), ()),
)


def _topics(row: Mapping[str, Any]) -> list[tuple[str, str, tuple[str, ...], tuple[str, ...]]]:
    out = []
    for t in CN_TOPICS:
        kw, tick, hyp = t[0], t[1], t[2]
        ev = t[3] if len(t) > 3 else ()
        out.append((kw, tick, hyp, ev))
    return out


def parse_weibo(raw: bytes | None) -> list[dict[str, Any]]:
    doc = _json(raw)
    out: list[dict[str, Any]] = []
    cards = (((doc or {}).get("data") or {}).get("cards")) if isinstance(doc, dict) else None
    for c in cards or []:
        groups = [c, *((c or {}).get("card_group") or [])]
        for g in groups:
            mb = (g or {}).get("mblog")
            if not isinstance(mb, dict):
                continue
            user = mb.get("user") or {}
            out.append({"id": f"wb{mb.get('id')}", "text": _text(str(mb.get("text") or "")),
                        "author": author_hash(user.get("id")),
                        "followers": _num(user.get("followers_count")),
                        "statuses": _num(user.get("statuses_count")),
                        "created": _weibo_time(str(mb.get("created_at") or ""))})
    return out


def _num(v: Any) -> float | None:
    try:
        if isinstance(v, str):
            v = v.replace(",", "")
            if v.endswith("万"):
                return float(v[:-1]) * 1e4
        return float(v)
    except (TypeError, ValueError):
        return None


def _weibo_time(s: str) -> str | None:
    for fmt in ("%a %b %d %H:%M:%S %z %Y",):
        try:
            return datetime.strptime(s, fmt).astimezone(UTC).isoformat()
        except ValueError:
            continue
    return None


def parse_xueqiu(raw: bytes | None) -> list[dict[str, Any]]:
    doc = _json(raw)
    out: list[dict[str, Any]] = []
    for st in ((doc or {}).get("list") or []) if isinstance(doc, dict) else []:
        if not isinstance(st, dict):
            continue
        user = st.get("user") or {}
        ts = st.get("created_at")
        created = (datetime.fromtimestamp(float(ts) / 1000.0, tz=UTC).isoformat()
                   if isinstance(ts, (int, float)) else None)
        out.append({"id": f"xq{st.get('id')}",
                    "text": _text(str(st.get("text") or st.get("description") or "")),
                    "author": author_hash(user.get("id")),
                    "followers": _num(user.get("followers_count")),
                    "statuses": _num(user.get("status_count")), "created": created})
    return out


def parse_guba(raw: bytes | None, now: datetime) -> list[dict[str, Any]]:
    """Eastmoney Guba board listing: the page embeds `var article_list={...}` JSON."""
    if not raw:
        return []
    text = raw.decode("utf-8", "replace")
    m = re.search(r"var\s+article_list\s*=\s*(\{.*?\});", text, re.S)
    out: list[dict[str, Any]] = []
    if m:
        try:
            doc = json.loads(m.group(1))
        except ValueError:
            doc = {}
        for r in doc.get("re") or []:
            if not isinstance(r, dict):
                continue
            ts = str(r.get("post_publish_time") or "")
            try:
                created = (datetime.strptime(f"{ts} +0800", "%Y-%m-%d %H:%M:%S %z")
                           .astimezone(UTC).isoformat())
            except ValueError:
                created = None
            out.append({"id": f"gb{r.get('post_id')}", "text": str(r.get("post_title") or ""),
                        "author": author_hash(r.get("user_id")),
                        "followers": None, "statuses": None, "created": created})
    return out


def parse_sogou_zhihu(raw: bytes | None) -> list[dict[str, Any]]:
    """Zhihu answers through Sogou's public Zhihu index -- the lawful public route while Zhihu's
    own API answers 403 to every unauthenticated request."""
    if not raw:
        return []
    page = raw.decode("utf-8", "replace")
    if "antispider" in page or "请输入验证码" in page:
        raise FetchError("anti_bot", "sogou zhihu challenge")
    out: list[dict[str, Any]] = []
    for block in re.split(r'<div class="(?:txt-box|result-about-list|box-result)"', page)[1:]:
        t = re.search(r"<a\b[^>]*>(.*?)</a>", block, re.S)
        p = re.search(r"<p\b[^>]*>(.*?)</p>", block, re.S)
        if not t:
            continue
        title = _text(t.group(1))
        body = _text(p.group(1)) if p else ""
        href = re.search(r'href="([^"]+)"', block)
        out.append({"id": "zh" + hashlib.sha1((href.group(1) if href else title).encode())
                    .hexdigest()[:16], "text": f"{title} {body}".strip(),
                    "author": "", "followers": None, "statuses": None, "created": None})
    return out


CN_ROUTES: dict[str, dict[str, Any]] = {
    "cn_weibo": {"url": ("https://m.weibo.cn/api/container/getIndex?containerid="
                         "{cid}&page_type=searchall"), "parse": "weibo",
                 "referer": "https://m.weibo.cn/"},
    "cn_xueqiu": {"url": ("https://xueqiu.com/query/v1/search/status.json?"
                          "sortId=2&q={kw}&count=20&page=1"), "parse": "xueqiu",
                  "referer": "https://xueqiu.com/", "cookie_from": "https://xueqiu.com/"},
    "cn_zhihu": {"url": "https://zhihu.sogou.com/zhihu?query={kw}", "parse": "zhihu",
                 "referer": "https://zhihu.sogou.com/",
                 "direct_probe": "https://www.zhihu.com/api/v4/search_v3?t=general&q={kw}"},
    "cn_guba": {"url": "https://guba.eastmoney.com/list,{board}.html", "parse": "guba",
                "referer": "https://guba.eastmoney.com/"},
}
#: Guba board per topic column (US-listed ADR boards are "us<ticker>").
GUBA_BOARDS: dict[str, str] = {"BABA": "usBABA", "BIDU": "usBIDU", "NIO": "usNIO",
                               "TME": "usTME", "HSI": "hk", "GOLD": "gjgold",
                               "OIL": "yuanyou", "USEQ": "mgzq", "CNH": "whfx"}


def _post_time(p: Mapping[str, Any], now: datetime) -> datetime:
    try:
        return datetime.fromisoformat(str(p.get("created")))
    except (TypeError, ValueError):
        return now


def fetch_cn_forum(fetch: Fetch, row: Mapping[str, Any], cursor: Mapping[str, Any],
                   now: datetime) -> Harvest:
    """One forum, every topic keyword; posts deduped by id against the cursor, bot-filtered,
    scored and folded into a DAILY per-topic aggregate the hunter turns into the weekly index."""
    sid = str(row["id"])
    h = Harvest(sid)
    route = CN_ROUTES.get(sid)
    if route is None:
        h.status, h.detail = "NO_ROUTE", f"no route declared for {sid}"
        return h
    seen = set(cursor.get("seen_ids") or [])
    headers = {"Referer": route["referer"], "Accept-Language": "zh-CN,zh;q=0.9"}
    if route.get("cookie_from"):
        # THE ONE PUBLIC HANDSHAKE: the landing page sets the visitor cookies the JSON API wants.
        # When a WAF challenge answers instead (acw_sc__v2), the API call below fails and the
        # blocker is RECORDED; nothing here solves a challenge.
        landing = _get(fetch, h, route["cookie_from"], headers)
        if landing and b"acw_sc__v2" in landing:
            h.notes.append("xueqiu landing served the acw_sc__v2 WAF challenge")
    posts_by_topic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for kw, tick, hyp, ev in _topics(row):
        if route["parse"] == "guba":
            board = GUBA_BOARDS.get(tick)
            if not board:
                continue
            url = route["url"].format(board=board)
        elif route["parse"] == "weibo":
            url = route["url"].format(cid=urllib.parse.quote(f"100103type=1&q={kw}", safe=""))
        else:
            url = route["url"].format(kw=urllib.parse.quote(kw))
        raw = _get(fetch, h, url, headers)
        try:
            posts = {"weibo": parse_weibo, "xueqiu": parse_xueqiu,
                     "zhihu": parse_sogou_zhihu}.get(route["parse"], lambda r: [])(raw) \
                if route["parse"] != "guba" else parse_guba(raw, now)
        except FetchError as exc:
            h.failures[exc.reason] += 1
            posts = []
        for p in posts:
            if p["id"] in seen:
                continue
            seen.add(p["id"])
            posts_by_topic[tick].append(p)
        h.columns.setdefault(f"{tick}_sent", {"hypothesis": list(hyp), "event": list(ev),
                                              "why": f"{sid} tone on {kw}"})
        h.columns.setdefault(f"{tick}_bull", {"hypothesis": list(hyp), "event": list(ev),
                                              "why": f"{sid} Antweiler-Frank bullishness, {kw}"})
        h.columns.setdefault(f"{tick}_posts", {"hypothesis": list(hyp), "event": list(ev),
                                               "why": f"{sid} post volume on {kw}"})
    if route.get("direct_probe"):
        probe = _get(fetch, h, route["direct_probe"].format(kw=urllib.parse.quote("量化")),
                     headers)
        h.notes.append("zhihu direct API " + ("answered" if probe else "refused (recorded)"))
    total = sum(len(v) for v in posts_by_topic.values())
    if total == 0:
        h.status = "BLOCKED" if h.failures else "EMPTY"
        h.detail = ", ".join(f"{k}x{v}" for k, v in h.failures.items()) or "no new posts"
        h.cursor = {"seen_ids": sorted(seen)[-20000:]}
        return h
    method = ""
    for tick, posts in posts_by_topic.items():
        kept, stats = bot_filter(posts)
        h.notes.append(f"{tick}: bot filter kept {stats['kept']}/{stats['seen']} "
                       f"{ {k: v for k, v in stats.items() if k not in ('kept', 'seen')} }")
        for p in kept:
            score, method = sentiment_cn(str(p.get("text") or ""))
            day = _day(_post_time(p, now))
            h.raw.append({"id": p["id"], "topic": tick, "day": day, "score": round(score, 4),
                          "method": method, "author": p.get("author")})
    h.cursor = {"seen_ids": sorted(seen)[-20000:]}
    h.notes.append(f"sentiment method: {method or 'none scored'}")
    return h


def weekly_index(raw_rows: Iterable[Mapping[str, Any]], today: date
                 ) -> list[dict[str, Any]]:
    """Per topic, per CLOSED ISO week: mean tone, bullishness and post count. A week still open
    is never published -- its value would move after the fact."""
    agg: dict[tuple[str, date], list[float]] = defaultdict(list)
    for r in raw_rows:
        try:
            d = date.fromisoformat(str(r.get("day")))
        except ValueError:
            continue
        agg[(str(r.get("topic")), _week_end(d))].append(float(r.get("score") or 0.0))
    out: list[dict[str, Any]] = []
    for (topic, wk), scores in sorted(agg.items()):
        if wk >= today:
            continue
        pos = sum(1 for s in scores if s > 0.1)
        neg = sum(1 for s in scores if s < -0.1)
        out += [{"key": f"{topic}_sent", "period_end": wk.isoformat(),
                 "value": round(sum(scores) / len(scores), 5)},
                {"key": f"{topic}_bull", "period_end": wk.isoformat(),
                 "value": round(bullishness(pos, neg), 5)},
                {"key": f"{topic}_posts", "period_end": wk.isoformat(), "value": len(scores)}]
    return out


# ============================================================ 3. JP IR transcripts
TRANSCRIPT_RX = re.compile(r"transcript|q\s*&\s*a|qa|question|script|speech|質疑|説明会|議事録|"
                           r"presentation|briefing", re.I)


def ir_links(page: bytes | None, base: str, rx: re.Pattern[str] = TRANSCRIPT_RX
             ) -> list[str]:
    if not page:
        return []
    text = page.decode("utf-8", "replace")
    out: list[str] = []
    for href, label in re.findall(r'<a\b[^>]*href="([^"#]+)"[^>]*>(.*?)</a>', text, re.S):
        if rx.search(href) or rx.search(_text(label)):
            url = urllib.parse.urljoin(base, html.unescape(href))
            if url.startswith("http") and url not in out:
                out.append(url)
    return out


def document_text(raw: bytes | None, url: str) -> str | None:
    """HTML to text. PDF text only when a PDF reader is importable (none is in the requirements
    files); otherwise the document is recorded as unreadable here, never guessed at."""
    if not raw:
        return None
    if url.lower().endswith(".pdf") or raw[:5] == b"%PDF-":
        for mod in ("pypdf", "PyPDF2"):
            try:
                lib = __import__(mod)
                reader = lib.PdfReader(io.BytesIO(raw))
                return "\n".join((p.extract_text() or "") for p in reader.pages[:60])
            except Exception:
                continue
        return None
    text = raw.decode("utf-8", "replace")
    text = re.sub(r"<(script|style)\b.*?</\1>", " ", text, flags=re.S | re.I)
    return _text(text)


def fetch_jp_ir(fetch: Fetch, row: Mapping[str, Any], cursor: Mapping[str, Any],
                now: datetime) -> Harvest:
    """Every declared IR page: new transcript/Q&A documents -> tone -> delta vs the company's
    previous document. The delta is the column; the level rides in the raw archive."""
    h = Harvest(str(row["id"]))
    seen = set(cursor.get("seen_docs") or [])
    last_tone: dict[str, float] = dict(cursor.get("last_tone") or {})
    unreadable = 0
    for co in row.get("companies") or []:
        name, page_url = str(co.get("name")), str(co.get("ir_url"))
        cfd = co.get("cfd")
        col = f"{name}_tone_delta"
        h.columns.setdefault(col, {"hypothesis": ["JPN225", "USDJPY"],
                                   "event": [cfd] if cfd else [],
                                   "why": f"{name} IR call tone change vs its previous call"})
        page = _get(fetch, h, page_url)
        for url in ir_links(page, page_url)[: int(row.get("docs_per_company") or 4)]:
            if url in seen:
                continue
            raw = _get(fetch, h, url)
            text = document_text(raw, url)
            seen.add(url)
            if not text:
                unreadable += 1
                continue
            ja = len(re.findall(r"[぀-ヿ一-鿿]", text)) > len(text) * 0.2
            t = tone_ja(text) if ja else tone_en(text)
            h.raw.append({"company": name, "url": url, "lang": "ja" if ja else "en",
                          "tone": round(t["tone"], 5), "uncertainty": round(t["uncertainty"], 5),
                          "words": t["words"], "seen_utc": now.isoformat()})
            if name in last_tone:
                h.obs.append({"key": col, "period_end": _day(now),
                              "value": round(t["tone"] - last_tone[name], 5)})
            last_tone[name] = t["tone"]
    if unreadable:
        h.notes.append(f"{unreadable} document(s) unreadable here (PDF with no reader installed)")
    h.cursor = {"seen_docs": sorted(seen)[-5000:], "last_tone": last_tone}
    if not h.raw and not h.obs:
        h.status = "BLOCKED" if h.failures else "EMPTY"
        h.detail = ", ".join(f"{k}x{v}" for k, v in h.failures.items()) or "no new documents"
    return h


# ================================================================== 4. JP patents
#: Applicant name -> (company key, share CFD or None). JP applicants appear in JP and EN forms.
JP_APPLICANTS: tuple[tuple[str, str, str | None], ...] = (
    (r"トヨタ自動車|toyota motor", "Toyota", "Toyota"), (r"ソニー|sony", "Sony", None),
    (r"任天堂|nintendo", "Nintendo", None), (r"本田技研|honda motor", "Honda", None),
    (r"パナソニック|panasonic", "Panasonic", None), (r"キヤノン|canon inc", "Canon", None),
    (r"日立製作所|hitachi", "Hitachi", None), (r"東芝|toshiba", "Toshiba", None),
    (r"デンソー|denso", "Denso", None), (r"東京エレクトロン|tokyo electron", "TokyoElectron", None),
    (r"ソフトバンク|softbank", "SoftBank", None), (r"富士通|fujitsu", "Fujitsu", None),
    (r"日本電気|\bnec\b", "NEC", None), (r"村田製作所|murata", "Murata", None),
    (r"信越化学|shin-etsu", "ShinEtsu", None), (r"ファナック|fanuc", "Fanuc", None),
    (r"キーエンス|keyence", "Keyence", None), (r"三菱電機|mitsubishi electric", "MitsubishiElec",
                                               None),
    (r"富士フイルム|fujifilm", "Fujifilm", None), (r"アドバンテスト|advantest", "Advantest", None),
)
_JP_APP_RX = [(re.compile(rx, re.I), key, cfd) for rx, key, cfd in JP_APPLICANTS]


def jp_applicant(name: str) -> tuple[str, str | None] | None:
    for rx, key, cfd in _JP_APP_RX:
        if rx.search(name or ""):
            return key, cfd
    return None


def parse_patent_table(raw: bytes) -> list[dict[str, str]]:
    """A bulk table (CSV or TSV) with a publication date, an applicant and an IPC column. Header
    names are matched loosely because JPO and IIP files name them differently."""
    text = raw.decode("utf-8-sig", "replace")
    dialect = "\t" if text.count("\t") > text.count(",") else ","
    rows = list(csv.DictReader(io.StringIO(text), delimiter=dialect))
    out: list[dict[str, str]] = []
    for r in rows:
        low = {str(k).strip().lower(): str(v or "") for k, v in r.items() if k}
        pub = next((v for k, v in low.items() if ("pub" in k and "date" in k) or k in
                    ("公開日", "publication_date", "公報発行日")), "")
        app = next((v for k, v in low.items() if "applicant" in k or k in ("出願人",
                                                                            "出願人名")), "")
        ipc = next((v for k, v in low.items() if "ipc" in k or k in ("国際特許分類",)), "")
        if pub and app:
            out.append({"pub": pub.strip()[:10].replace("/", "-"), "applicant": app,
                        "ipc": ipc.strip()[:4].upper()})
    return out


def patent_momentum(rows: Sequence[Mapping[str, str]]) -> tuple[list[dict[str, Any]],
                                                                 dict[str, dict[str, Any]]]:
    """Monthly publication counts per company and per IPC cluster; momentum = ln((1 + last 3m) /
    (1 + the 3m before)), published at each month end. Mapped companies only, plus the JP total."""
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for r in rows:
        month = str(r.get("pub") or "")[:7]
        if not re.fullmatch(r"\d{4}-\d{2}", month):
            continue
        hit = jp_applicant(str(r.get("applicant") or ""))
        counts["jp_all"][month] += 1
        if r.get("ipc"):
            counts[f"ipc_{r['ipc']}"][month] += 1
        if hit:
            counts[hit[0]][month] += 1
    obs: list[dict[str, Any]] = []
    meta: dict[str, dict[str, Any]] = {}
    for key, per in counts.items():
        months = sorted(per)
        for i in range(5, len(months)):
            last3 = sum(per[m] for m in months[i - 2:i + 1])
            prev3 = sum(per[m] for m in months[i - 5:i - 2])
            y, mo = int(months[i][:4]), int(months[i][5:7])
            end = (date(y + (mo == 12), mo % 12 + 1, 1) - timedelta(days=1)).isoformat()
            obs.append({"key": f"{key}_mom", "period_end": end,
                        "value": round(math.log((1 + last3) / (1 + prev3)), 5)})
        cfd = next((c for _rx, k, c in _JP_APP_RX if k == key), None)
        meta[f"{key}_mom"] = {"hypothesis": ["JPN225", "USDJPY"],
                              "event": [cfd] if cfd else [],
                              "why": f"JP patent publication momentum, {key}"}
    return obs, meta


def fetch_jp_patents(fetch: Fetch, row: Mapping[str, Any], cursor: Mapping[str, Any],
                     now: datetime, *, inbox: Any = None) -> Harvest:
    """Keyless JP patent data does not exist as an API: J-PlatPat is a web search with no API and
    the JPO's bulk data needs an application. So the route is a BULK FILE the box holds (JPO
    標準データ / IIP patent database extracts) dropped into the inbox; the doors are probed and
    their answer recorded every pass."""
    h = Harvest(str(row["id"]))
    for url in row.get("probe_urls") or []:
        raw = _get(fetch, h, str(url))
        h.notes.append(f"probe {url}: " + ("answered" if raw else "refused"))
    files = sorted(inbox.glob("*.csv")) + sorted(inbox.glob("*.tsv")) if inbox is not None \
        and inbox.exists() else []
    if not files:
        h.status = "NEEDS_BULK_FILE"
        h.detail = (f"no JP patent bulk file in {inbox}; J-PlatPat has no API and JPO bulk data "
                    "needs an application -- drop a CSV/TSV extract (publication date, applicant, "
                    "IPC) there and the next pass ingests it")
        return h
    done = set(cursor.get("files") or [])
    rows: list[dict[str, str]] = []
    for f in files:
        rows.extend(parse_patent_table(f.read_bytes()))
        done.add(f.name)
    h.obs, h.columns = patent_momentum(rows)
    h.cursor = {"files": sorted(done)}
    h.notes.append(f"{len(rows)} patent rows from {len(files)} file(s)")
    if not h.obs:
        h.status, h.detail = "EMPTY", "bulk files parsed but carry no usable month history"
    return h


# ================================================================ 5a. Google Trends
TRENDS_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("gold price", ("XAUUSD",)), ("recession", ("US500", "USDJPY", "XAUUSD")),
    ("inflation", ("XAUUSD", "UST10Y")), ("bitcoin", ("BTCUSD",)),
    ("oil price", ("XTIUSD", "XBRUSD")), ("unemployment", ("US500", "EURUSD")),
    ("stock market crash", ("US500", "NAS100")), ("yen", ("USDJPY",)),
    ("mortgage rates", ("UST10Y", "US500")), ("layoffs", ("US500", "NAS100")),
)


def trends_col(term: str) -> str:
    return "gt_" + re.sub(r"\W+", "_", term.lower()).strip("_")


def parse_trends_explore(raw: bytes | None) -> dict[str, Any] | None:
    doc = _json(raw)
    for w in (doc or {}).get("widgets", []) if isinstance(doc, dict) else []:
        if w.get("id") == "TIMESERIES":
            return {"token": w.get("token"), "req": w.get("request")}
    return None


def parse_trends_multiline(raw: bytes | None) -> list[tuple[str, float]]:
    doc = _json(raw)
    out: list[tuple[str, float]] = []
    for p in (((doc or {}).get("default") or {}).get("timelineData") or []) \
            if isinstance(doc, dict) else []:
        try:
            ts = datetime.fromtimestamp(int(p["time"]), tz=UTC).date().isoformat()
            if p.get("isPartial"):
                continue
            out.append((ts, float(p["value"][0])))
        except (KeyError, ValueError, TypeError, IndexError):
            continue
    return out


def fetch_gtrends(fetch: Fetch, row: Mapping[str, Any], cursor: Mapping[str, Any],
                  now: datetime) -> Harvest:
    """Interest over time for each term. THE PUBLISHED COLUMN IS THE LOG CHANGE, computed inside
    one response: Trends rescales every response to its own window maximum, so a LEVEL carries the
    future through its normaliser, while a within-response ratio does not."""
    h = Harvest(str(row["id"]))
    base = "https://trends.google.com/trends/api"
    for term, targets in row.get("terms") or TRENDS_TERMS:
        req = {"comparisonItem": [{"keyword": term, "geo": "", "time": "today 3-m"}],
               "category": 0, "property": ""}
        url = (f"{base}/explore?hl=en-US&tz=0&req="
               f"{urllib.parse.quote(json.dumps(req, separators=(',', ':')))}")
        widget = parse_trends_explore(_get(fetch, h, url))
        if not widget or not widget.get("token"):
            continue
        url2 = (f"{base}/widgetdata/multiline?hl=en-US&tz=0&req="
                f"{urllib.parse.quote(json.dumps(widget['req'], separators=(',', ':')))}"
                f"&token={urllib.parse.quote(str(widget['token']))}")
        pts = parse_trends_multiline(_get(fetch, h, url2))
        col = trends_col(term)
        h.columns[col] = {"hypothesis": list(targets), "event": [],
                          "why": f"search attention log-change, '{term}'"}
        for (_d0, v0), (d1, v1) in pairwise(pts):
            h.obs.append({"key": col, "period_end": d1,
                          "value": round(math.log((1.0 + v1) / (1.0 + v0)), 5)})
        h.raw += [{"term": term, "day": d, "value": v} for d, v in pts[-7:]]
    if not h.obs:
        h.status = "BLOCKED" if h.failures else "EMPTY"
        h.detail = ", ".join(f"{k}x{v}" for k, v in h.failures.items()) or "no points"
    return h


# ============================================================ 5b. congressional trades
HOUSE_FD_ZIP = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip"
STOCKWATCHER = ("https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/"
                "all_transactions.json")


def parse_house_fd_index(raw: bytes | None) -> list[dict[str, str]]:
    """The Clerk's yearly index (XML inside the zip): one row per filing. FilingType P is a
    periodic transaction report. Names are dropped; the filing date is what is kept."""
    if not raw:
        return []
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        return []
    name = next((n for n in zf.namelist() if n.lower().endswith(".xml")), None)
    if name is None:
        return []
    xml = zf.read(name).decode("utf-8", "replace")
    out: list[dict[str, str]] = []
    for m in re.finditer(r"<Member>(.*?)</Member>", xml, re.S):
        block = m.group(1)

        def tag(t: str, _b: str = block) -> str:
            g = re.search(rf"<{t}>(.*?)</{t}>", _b, re.S)
            return g.group(1).strip() if g else ""
        out.append({"type": tag("FilingType"), "date": tag("FilingDate"), "doc": tag("DocID")})
    return out


def _us_date(s: str) -> str | None:
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt).replace(tzinfo=UTC).date().isoformat()
        except ValueError:
            continue
    return None


def parse_stockwatcher(raw: bytes | None) -> list[dict[str, Any]]:
    doc = _json(raw)
    out: list[dict[str, Any]] = []
    for r in doc if isinstance(doc, list) else []:
        if not isinstance(r, dict):
            continue
        typ = str(r.get("type") or "").lower()
        side = 1 if "purchase" in typ else -1 if "sale" in typ else 0
        disc = _us_date(str(r.get("disclosure_date") or ""))
        if not side or not disc:
            continue
        out.append({"ticker": str(r.get("ticker") or "").upper().strip(), "side": side,
                    "disclosed": disc})
    return out


def fetch_congress(fetch: Fetch, row: Mapping[str, Any], cursor: Mapping[str, Any],
                   now: datetime) -> Harvest:
    """Disclosure-dated, never trade-dated: a congressional trade becomes public on its
    DISCLOSURE date (up to 45 days late), so that is the only date a series may carry."""
    h = Harvest(str(row["id"]))
    h.columns["ptr_filings"] = {"hypothesis": ["US500", "NAS100"], "event": [],
                                "why": "House periodic transaction reports filed per day"}
    for year in (now.year - 1, now.year):
        for r in parse_house_fd_index(_get(fetch, h, HOUSE_FD_ZIP.format(year=year))):
            if r["type"] != "P":
                continue
            d = _us_date(r["date"])
            if d:
                h.raw.append({"kind": "ptr", "day": d, "doc": r["doc"]})
    per_day = Counter(r["day"] for r in h.raw if r.get("kind") == "ptr")
    h.obs += [{"key": "ptr_filings", "period_end": d, "value": n}
              for d, n in sorted(per_day.items())]
    tx = parse_stockwatcher(_get(fetch, h, str(row.get("mirror_url") or STOCKWATCHER)))
    net: dict[tuple[str, str], int] = defaultdict(int)
    for t in tx:
        net[("net_all", t["disclosed"])] += t["side"]
        cfd = TICKER_CFD.get(t["ticker"])
        if cfd:
            net[(f"net_{t['ticker']}", t["disclosed"])] += t["side"]
            h.columns.setdefault(f"net_{t['ticker']}", {
                "hypothesis": list(proxies_for_company(cfd)), "event": [cfd],
                "why": f"congressional net buys disclosed, {t['ticker']}"})
    if tx:
        h.columns["net_all"] = {"hypothesis": ["US500", "NAS100", "US30"], "event": [],
                                "why": "congressional net buys disclosed, all tickers"}
    h.obs += [{"key": k, "period_end": d, "value": v} for (k, d), v in sorted(net.items())]
    if not h.obs:
        h.status = "BLOCKED" if h.failures else "EMPTY"
        h.detail = ", ".join(f"{k}x{v}" for k, v in h.failures.items()) or "no filings"
    return h


# ===================================================================== 5c. CoinPaprika
#: Fusion crypto CFD base -> CoinPaprika coin id. The BASES come from the broker registry at run
#: time (asset class Crypto); this table only spells each base the way CoinPaprika does.
PAPRIKA_IDS: dict[str, str] = {
    "BTC": "btc-bitcoin", "ETH": "eth-ethereum", "ADA": "ada-cardano", "AVAX": "avax-avalanche",
    "BCH": "bch-bitcoin-cash", "BNB": "bnb-binance-coin", "DOGE": "doge-dogecoin",
    "DOT": "dot-polkadot", "EOS": "eos-eos", "LNK": "link-chainlink", "LINK": "link-chainlink",
    "LTC": "ltc-litecoin", "MATIC": "matic-polygon", "SOL": "sol-solana", "XLM": "xlm-stellar",
}


def parse_paprika_ticker(raw: bytes | None) -> dict[str, float] | None:
    doc = _json(raw)
    q = (((doc or {}).get("quotes") or {}).get("USD")) if isinstance(doc, dict) else None
    if not isinstance(q, dict):
        return None
    out = {}
    for k in ("volume_24h", "market_cap", "percent_change_24h", "percent_change_7d"):
        if isinstance(q.get(k), (int, float)):
            out[k] = float(q[k])
    return out or None


def fetch_coinpaprika(fetch: Fetch, row: Mapping[str, Any], cursor: Mapping[str, Any],
                      now: datetime, *, crypto_cfds: Sequence[str] = ()) -> Harvest:
    """Hourly market state per Fusion crypto CFD. Nothing here is an exchange universe: a coin is
    fetched only because the broker lists a CFD on it."""
    h = Harvest(str(row["id"]))
    hour = now.replace(minute=0, second=0, microsecond=0).isoformat()
    for sym in crypto_cfds:
        base = sym[:-3] if sym.endswith("USD") else sym
        cid = PAPRIKA_IDS.get(base)
        if not cid:
            h.notes.append(f"{sym}: no CoinPaprika id declared")
            continue
        q = parse_paprika_ticker(_get(fetch, h, f"https://api.coinpaprika.com/v1/tickers/{cid}"))
        if not q:
            continue
        for k, v in q.items():
            col = f"{base}_{k}"
            h.columns[col] = {"hypothesis": [sym], "event": [],
                              "why": f"CoinPaprika {k} for the {sym} CFD's underlying"}
            h.obs.append({"key": col, "period_end": hour, "value": v})
    glob = _json(_get(fetch, h, "https://api.coinpaprika.com/v1/global"))
    if isinstance(glob, dict) and isinstance(glob.get("bitcoin_dominance_percentage"),
                                             (int, float)):
        h.columns["btc_dominance"] = {"hypothesis": list(crypto_cfds)[:6], "event": [],
                                      "why": "bitcoin share of total crypto market cap"}
        h.obs.append({"key": "btc_dominance", "period_end": hour,
                      "value": float(glob["bitcoin_dominance_percentage"])})
    if not h.obs:
        h.status = "BLOCKED" if h.failures else "EMPTY"
        h.detail = ", ".join(f"{k}x{v}" for k, v in h.failures.items()) or "no quotes"
    return h


# ================================================================= 5d. Reddit / Telegram
#: instrument words scanned in English posts -> (column, hypothesis targets, event CFDs)
EN_TOPICS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (r"\bgold\b|\bxau|золот", "GOLD", ("XAUUSD",)), (r"\bsilver\b|\bxag", "SILVER", ("XAGUSD",)),
    (r"\boil\b|\bcrude|\bwti\b|\bbrent|нефт", "OIL", ("XTIUSD", "XBRUSD")),
    (r"\bspy\b|s&p ?500|\bspx\b", "SPX", ("US500",)), (r"\bqqq\b|nasdaq", "NDX", ("NAS100",)),
    (r"\beur/?usd|\beuro\b", "EUR", ("EURUSD",)), (r"\busd/?jpy|\byen\b", "JPY", ("USDJPY",)),
    (r"\bgbp|\bcable\b|\bpound\b", "GBP", ("GBPUSD",)),
    (r"\bbitcoin|\bbtc\b|биткоин", "BTC", ("BTCUSD",)), (r"\bethereum|\beth\b", "ETH", ("ETHUSD",)),
    (r"\bdxy\b|dollar index|индекс доллара", "DXY", ("USDX",)), (r"\bnikkei", "N225", ("JPN225",)),
)
_EN_RX = [(re.compile(rx, re.I), col, hyp) for rx, col, hyp in EN_TOPICS]
_CASHTAG = re.compile(r"\$([A-Z]{1,5})\b")


def en_mentions(text: str) -> list[tuple[str, tuple[str, ...], tuple[str, ...]]]:
    out: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
        (col, hyp, ()) for rx, col, hyp in _EN_RX if rx.search(text)]
    for tick in set(_CASHTAG.findall(text)):
        cfd = TICKER_CFD.get(tick)
        if cfd:
            out.append((tick, proxies_for_company(cfd), (cfd,)))
    return out


def parse_reddit(raw: bytes | None) -> list[dict[str, Any]]:
    doc = _json(raw)
    out: list[dict[str, Any]] = []
    for c in (((doc or {}).get("data") or {}).get("children") or []) \
            if isinstance(doc, dict) else []:
        d = (c or {}).get("data") or {}
        author = str(d.get("author") or "")
        if author in ("AutoModerator", "[deleted]", ""):
            continue
        out.append({"id": f"rd{d.get('name')}", "fullname": d.get("name"),
                    "text": f"{d.get('title') or ''} {d.get('selftext') or ''}"[:4000],
                    "author": author_hash(author),
                    "created": datetime.fromtimestamp(float(d.get("created_utc") or 0),
                                                      tz=UTC).isoformat()})
    return out


def parse_telegram(raw: bytes | None, channel: str) -> list[dict[str, Any]]:
    if not raw:
        return []
    page = raw.decode("utf-8", "replace")
    out: list[dict[str, Any]] = []
    for m in re.finditer(r'data-post="([^"]+)"(.*?)(?=data-post="|\Z)', page, re.S):
        post_id, block = m.group(1), m.group(2)
        body = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', block,
                         re.S)
        when = re.search(r'<time[^>]*datetime="([^"]+)"', block)
        if not body:
            continue
        out.append({"id": f"tg{post_id}", "text": _text(body.group(1))[:4000],
                    "author": author_hash(channel),
                    "created": when.group(1) if when else None})
    return out


def _social(h: Harvest, posts: list[dict[str, Any]], now: datetime, sid: str) -> None:
    kept, stats = bot_filter(posts, max_per_author=10_000 if sid == "telegram" else 20)
    h.notes.append(f"bot filter kept {stats['kept']}/{stats['seen']}")
    for p in kept:
        text = str(p.get("text") or "")
        tone, method = tone_social(text)
        day = _day(_post_time(p, now))
        for col, hyp, ev in en_mentions(text):
            h.columns.setdefault(f"{col}_mentions", {"hypothesis": list(hyp), "event": list(ev),
                                                     "why": f"{sid} daily mentions of {col}"})
            h.columns.setdefault(f"{col}_tone", {"hypothesis": list(hyp), "event": list(ev),
                                                 "why": f"{sid} daily tone on {col}"})
            h.raw.append({"id": p["id"], "topic": col, "day": day,
                          "score": round(float(tone), 4), "method": method})


def fetch_reddit(fetch: Fetch, row: Mapping[str, Any], cursor: Mapping[str, Any],
                 now: datetime) -> Harvest:
    h = Harvest(str(row["id"]))
    seen = set(cursor.get("seen_ids") or [])
    posts: list[dict[str, Any]] = []
    for sub in row.get("subreddits") or ():
        raw = _get(fetch, h, f"https://www.reddit.com/r/{sub}/new.json?limit=100&raw_json=1")
        for p in parse_reddit(raw):
            if p["id"] not in seen:
                seen.add(p["id"])
                posts.append(p)
    _social(h, posts, now, "reddit")
    h.cursor = {"seen_ids": sorted(seen)[-50000:]}
    if not h.raw:
        h.status = "BLOCKED" if h.failures else "EMPTY"
        h.detail = ", ".join(f"{k}x{v}" for k, v in h.failures.items()) or "no new posts"
    return h


def fetch_telegram(fetch: Fetch, row: Mapping[str, Any], cursor: Mapping[str, Any],
                   now: datetime) -> Harvest:
    h = Harvest(str(row["id"]))
    seen = set(cursor.get("seen_ids") or [])
    posts: list[dict[str, Any]] = []
    for ch in row.get("channels") or ():
        for p in parse_telegram(_get(fetch, h, f"https://t.me/s/{ch}"), str(ch)):
            if p["id"] not in seen:
                seen.add(p["id"])
                posts.append(p)
    _social(h, posts, now, "telegram")
    h.cursor = {"seen_ids": sorted(seen)[-50000:]}
    if not h.raw:
        h.status = "BLOCKED" if h.failures else "EMPTY"
        h.detail = ", ".join(f"{k}x{v}" for k, v in h.failures.items()) or "no new posts"
    return h


def daily_social(raw_rows: Iterable[Mapping[str, Any]], today: date) -> list[dict[str, Any]]:
    """Per topic per CLOSED UTC day: mention count and mean tone."""
    agg: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in raw_rows:
        agg[(str(r.get("topic")), str(r.get("day")))].append(float(r.get("score") or 0.0))
    out: list[dict[str, Any]] = []
    for (topic, day), sc in sorted(agg.items()):
        if day >= today.isoformat():
            continue
        out.append({"key": f"{topic}_mentions", "period_end": day, "value": len(sc)})
        out.append({"key": f"{topic}_tone", "period_end": day,
                    "value": round(sum(sc) / len(sc), 5)})
    return out


# =========================================================== 5e. AKShare / TuShare / BaoStock
#: series -> (Eastmoney secid | Sina futures symbol, route, hypothesis targets)
CN_MARKET: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("csi300", "1.000300", "eastmoney", ("CHINAH", "HK50", "USDCNH", "AUDUSD")),
    ("sse_comp", "1.000001", "eastmoney", ("CHINAH", "USDCNH")),
    ("hsi", "100.HSI", "eastmoney", ("HK50",)),
    ("shfe_au", "AU0", "sina", ("XAUUSD", "XAUAUD")),
    ("shfe_ag", "AG0", "sina", ("XAGUSD",)),
    ("shfe_cu", "CU0", "sina", ("XCUUSD", "AUDUSD")),
    ("ine_sc", "SC0", "sina", ("XBRUSD", "XTIUSD")),
    ("shfe_al", "AL0", "sina", ("XALUSD",)),
    ("shfe_zn", "ZN0", "sina", ("XZNUSD",)),
    ("shfe_ni", "NI0", "sina", ("XNIUSD",)),
)


def parse_eastmoney_kline(raw: bytes | None) -> list[tuple[str, float]]:
    doc = _json(raw)
    kl = (((doc or {}).get("data") or {}).get("klines")) if isinstance(doc, dict) else None
    out: list[tuple[str, float]] = []
    for line in kl or []:
        parts = str(line).split(",")
        try:
            out.append((parts[0], float(parts[2])))       # date, open, CLOSE, ...
        except (IndexError, ValueError):
            continue
    return out


def parse_sina_futures(raw: bytes | None) -> list[tuple[str, float]]:
    doc = _json(raw)
    out: list[tuple[str, float]] = []
    for r in doc if isinstance(doc, list) else []:
        try:
            out.append((str(r.get("d") or r.get("date"))[:10], float(r.get("c") or r.get("close"))))
        except (TypeError, ValueError):
            continue
    return out


def fetch_akshare_direct(fetch: Fetch, row: Mapping[str, Any], cursor: Mapping[str, Any],
                         now: datetime) -> Harvest:
    """AKShare's own upstreams, fetched directly (AKShare is not in the requirements files).
    Daily closes; the column is the log return, published at the Shanghai close + a day."""
    h = Harvest(str(row["id"]))
    for key, code, route, targets in CN_MARKET:
        if route == "eastmoney":
            url = ("https://push2his.eastmoney.com/api/qt/stock/kline/get?secid="
                   f"{code}&fields1=f1,f2,f3&fields2=f51,f52,f53,f54,f55,f56&klt=101&fqt=0"
                   "&beg=0&end=20500101&lmt=400")
            pts = parse_eastmoney_kline(_get(fetch, h, url, {"Referer":
                                                               "https://quote.eastmoney.com/"}))
        else:
            url = ("https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_x=/"
                   f"InnerFuturesNewService.getDailyKLine?symbol={code}")
            pts = parse_sina_futures(_get(fetch, h, url, {"Referer": "https://finance.sina.com.cn/"}))
        _returns(h, key, pts, targets, f"{key} daily log return ({route})")
    if not h.obs:
        h.status = "BLOCKED" if h.failures else "EMPTY"
        h.detail = ", ".join(f"{k}x{v}" for k, v in h.failures.items()) or "no bars"
    return h


def _returns(h: Harvest, key: str, pts: Sequence[tuple[str, float]], targets: Sequence[str],
             why: str) -> None:
    pts = sorted(p for p in pts if p[1] and p[1] > 0)
    if len(pts) < 2:
        return
    col = f"{key}_ret"
    h.columns[col] = {"hypothesis": list(targets), "event": [], "why": why}
    for (_d0, c0), (d1, c1) in pairwise(pts):
        h.obs.append({"key": col, "period_end": d1, "value": round(math.log(c1 / c0), 6)})


TUSHARE_API = "http://api.tushare.pro"
TUSHARE_CALLS: tuple[tuple[str, str, dict[str, str], str, tuple[str, ...]], ...] = (
    ("csi300", "index_daily", {"ts_code": "000300.SH"}, "close", ("CHINAH", "HK50", "USDCNH")),
    ("shibor_on", "shibor", {}, "on", ("USDCNH",)),
    ("shibor_3m", "shibor", {}, "3m", ("USDCNH", "AUDUSD")),
)


def parse_tushare(raw: bytes | None, value_field: str) -> list[tuple[str, float]]:
    doc = _json(raw)
    if not isinstance(doc, dict) or doc.get("code") not in (0, "0"):
        return []
    data = doc.get("data") or {}
    fields = list(data.get("fields") or [])
    items = data.get("items") or []
    if value_field not in fields:
        return []
    di = next((i for i, f in enumerate(fields) if f in ("trade_date", "date", "cal_date")), None)
    if di is None:
        return []
    vi = fields.index(value_field)
    out: list[tuple[str, float]] = []
    for it in items:
        try:
            d = str(it[di])
            out.append((f"{d[:4]}-{d[4:6]}-{d[6:8]}", float(it[vi])))
        except (TypeError, ValueError, IndexError):
            continue
    return out


def fetch_tushare(fetch: Fetch, row: Mapping[str, Any], cursor: Mapping[str, Any],
                  now: datetime) -> Harvest:
    h = Harvest(str(row["id"]))
    token = read_key(str(row.get("key_env") or "TUSHARE_TOKEN"))
    if not token:
        h.status = "NEEDS_CREDENTIAL"
        h.detail = f"{row.get('key_env') or 'TUSHARE_TOKEN'} is not set on this host"
        return h
    for key, api, params, field_, targets in TUSHARE_CALLS:
        body = json.dumps({"api_name": api, "token": token, "params": params,
                           "fields": ""}).encode()
        pts = parse_tushare(_get(fetch, h, TUSHARE_API, {"Content-Type": "application/json"},
                                 body), field_)
        if key.startswith("shibor"):
            col = f"{key}_level"
            h.columns[col] = {"hypothesis": list(targets), "event": [], "why": f"SHIBOR {field_}"}
            h.obs += [{"key": col, "period_end": d, "value": v} for d, v in pts]
        else:
            _returns(h, key, pts, targets, f"{key} daily log return (tushare)")
    if not h.obs:
        h.status = "BLOCKED" if h.failures else "EMPTY"
        h.detail = ", ".join(f"{k}x{v}" for k, v in h.failures.items()) or "no rows"
    return h


def fetch_package_route(fetch: Fetch, row: Mapping[str, Any], cursor: Mapping[str, Any],
                        now: datetime) -> Harvest:
    """BaoStock and jqdatasdk speak their own client protocols (BaoStock a TCP socket, JoinQuant
    an authenticated session); neither is reachable without its package, and neither package is
    in the requirements files, so no install is attempted. When the package IS importable on a
    host the fetch runs through it."""
    h = Harvest(str(row["id"]))
    mod = str(row.get("package") or "")
    try:
        lib = __import__(mod)
    except Exception:
        h.status = "NOT_INSTALLED"
        h.detail = f"python package {mod!r} is not importable here and is not in requirements"
        return h
    if mod == "baostock":
        try:
            lg = lib.login()
            if str(getattr(lg, "error_code", "1")) != "0":
                h.status, h.detail = "BLOCKED", f"baostock login {getattr(lg, 'error_msg', '')}"
                return h
            start = (now.date() - timedelta(days=400)).isoformat()
            rs = lib.query_history_k_data_plus("sh.000300", "date,close", start_date=start,
                                               frequency="d")
            pts: list[tuple[str, float]] = []
            while rs.error_code == "0" and rs.next():
                d, c = rs.get_row_data()
                pts.append((d, float(c)))
            lib.logout()
            _returns(h, "csi300", pts, ("CHINAH", "HK50", "USDCNH"), "CSI300 (baostock)")
        except Exception as exc:
            h.status, h.detail = "BLOCKED", f"{type(exc).__name__}: {str(exc)[:120]}"
            return h
    elif mod == "jqdatasdk":
        user = read_key("JQ_USER")
        pw = read_key("JQ_PASS")
        if not user or not pw:
            h.status, h.detail = "NEEDS_CREDENTIAL", "JQ_USER / JQ_PASS are not set on this host"
            return h
        try:
            lib.auth(user, pw)
            df = lib.get_price("000300.XSHG", count=400, end_date=now.date().isoformat(),
                               frequency="daily", fields=["close"])
            pts = [(str(i)[:10], float(v)) for i, v in zip(df.index, df["close"], strict=False)]
            _returns(h, "csi300", pts, ("CHINAH", "HK50", "USDCNH"), "CSI300 (jqdatasdk)")
        except Exception as exc:
            h.status, h.detail = "BLOCKED", f"{type(exc).__name__}: {str(exc)[:120]}"
            return h
    if not h.obs:
        h.status = "EMPTY"
    return h


def fetch_akshare_package(fetch: Fetch, row: Mapping[str, Any], cursor: Mapping[str, Any],
                          now: datetime) -> Harvest:
    """AKShare through its own package when importable, else its upstreams directly."""
    try:
        import akshare as ak  # type: ignore[import-not-found]
    except Exception:
        h = fetch_akshare_direct(fetch, row, cursor, now)
        h.notes.append("akshare package not importable: fetched its upstreams directly")
        return h
    h = Harvest(str(row["id"]))
    try:
        df = ak.stock_zh_index_daily(symbol="sh000300")
        pts = [(str(d)[:10], float(c)) for d, c in zip(df["date"], df["close"], strict=False)]
        _returns(h, "csi300", pts, ("CHINAH", "HK50", "USDCNH"), "CSI300 (akshare)")
    except Exception as exc:
        h.failures[type(exc).__name__] += 1
    if not h.obs:
        h.status = "BLOCKED" if h.failures else "EMPTY"
    return h


# ===================================================================== 6. catalogues
#: Hosts that ARE a crypto-exchange universe: a catalogue link to one is refused and counted.
EXCHANGE_HOSTS = ("binance", "bybit", "okx", "okex", "hyperliquid", "deribit", "bitmex",
                  "kucoin", "huobi", "htx", "gate.io", "bitfinex", "kraken", "coinglass",
                  "dydx", "mexc", "bitget")
MT5_RELEVANCE = ("fx", "forex", "currency", "exchange rate", "gold", "silver", "metal", "oil",
                 "energy", "commodit", "index", "indices", "bond", "yield", "rate", "macro",
                 "inflation", "cpi", "gdp", "employment", "central bank", "futures",
                 "positioning", "cot", "sentiment", "news", "satellite", "shipping", "freight",
                 "weather", "patent", "app", "web traffic", "search", "trends", "earnings",
                 "transcript", "supply chain", "trade", "customs", "economic")


def parse_catalogue(raw: bytes | None, catalogue: str, base: str = "") -> list[dict[str, Any]]:
    """Every outbound link with its label and the heading it sits under. Markdown, RST and HTML
    are all read the same way: find a link, remember the nearest heading above it."""
    if not raw:
        return []
    text = raw.decode("utf-8", "replace")
    out: list[dict[str, Any]] = []
    section = ""
    seen: set[str] = set()
    link_rx = re.compile(r"\[([^\]]{2,160})\]\((https?://[^)\s]+)\)"            # markdown
                         r"|`([^`<]{2,160})\s*<(https?://[^>\s]+)>`_"            # rst
                         r'|<a\b[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>',    # html
                         re.S | re.I)
    prev = ""
    for line in text.splitlines():
        hd = re.match(r"^\s*#{1,6}\s+(.+)$", line) or re.match(r"^<h[1-6][^>]*>(.*?)</h", line)
        if hd:
            section = _text(hd.group(1))[:80]
        elif re.fullmatch(r"[=\-~^]{3,}", line.strip()) and prev.strip() and "`" not in prev:
            section = _text(prev.strip())[:80]           # an RST heading is underlined
        prev = line
        for m in link_rx.finditer(line):
            if m.group(2):
                label, url = m.group(1), m.group(2)
            elif m.group(4):
                label, url = m.group(3), m.group(4)
            else:
                url, label = m.group(5), _text(m.group(6) or "")
            url = url.rstrip(").,")
            if (url in seen or ("github.com/" in url and url.count("/") <= 3)
                    or "/apd-core/" in url or "awesome.re" in url or "shields.io" in url):
                continue
            seen.add(url)
            out.append({"name": _text(label)[:160], "url": url, "section": section,
                        "catalogue": catalogue})
    return out


def score_dataset(d: Mapping[str, Any]) -> tuple[float, str | None]:
    """(MT5 relevance score, refusal reason). Refused: a crypto-exchange universe host."""
    blob = f"{d.get('name', '')} {d.get('section', '')} {d.get('url', '')}".lower()
    host = urllib.parse.urlparse(str(d.get("url") or "")).netloc.lower()
    if any(x in host for x in EXCHANGE_HOSTS):
        return 0.0, "crypto-exchange universe host (MT5 mandate 2026-08-18)"
    hits = sum(1 for w in MT5_RELEVANCE if w in blob)
    return float(hits), None


def fetch_catalogue(fetch: Fetch, row: Mapping[str, Any], cursor: Mapping[str, Any],
                    now: datetime) -> Harvest:
    h = Harvest(str(row["id"]))
    known = set(cursor.get("known_urls") or [])
    refused = 0
    for cat in row.get("catalogues") or ():
        raw = _get(fetch, h, str(cat["url"]))
        for d in parse_catalogue(raw, str(cat["name"]), str(cat["url"])):
            score, why = score_dataset(d)
            if why:
                refused += 1
                continue
            if d["url"] in known:
                continue
            known.add(d["url"])
            h.datasets.append({**d, "score": score, "discovered_utc": now.isoformat()})
    h.cursor = {"known_urls": sorted(known)[-100000:]}
    h.notes.append(f"{len(h.datasets)} new dataset link(s); {refused} refused (exchange hosts)")
    if not h.datasets and not known:
        h.status = "BLOCKED" if h.failures else "EMPTY"
        h.detail = ", ".join(f"{k}x{v}" for k, v in h.failures.items()) or "no links"
    elif not h.datasets:
        h.status, h.detail = "OK", "no NEW links (catalogues unchanged)"
    return h


FETCHERS: dict[str, Callable[..., Harvest]] = {
    "app_rank_apple": fetch_app_rank_apple, "cn_forum": fetch_cn_forum, "jp_ir": fetch_jp_ir,
    "jp_patents": fetch_jp_patents, "gtrends": fetch_gtrends, "congress": fetch_congress,
    "coinpaprika": fetch_coinpaprika, "reddit": fetch_reddit, "telegram": fetch_telegram,
    "akshare": fetch_akshare_package, "tushare": fetch_tushare,
    "package": fetch_package_route, "catalogue": fetch_catalogue,
}
