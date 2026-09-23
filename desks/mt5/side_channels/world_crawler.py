#!/usr/bin/env python3
"""THE WORLD CRAWLER -- hourly, worldwide, multilingual, and it finds its own ground.

    "this scraper world wide should be hourly too ... deep and wide fully covering every bit of
     world wide web fr edges n datas"                        -- the principal, 2026-08/09

WHAT MAKES THIS DIFFERENT FROM THE FORTY MINERS. Each miner is pointed at a source a person
chose, which sets the desk's coverage to the ceiling of human attention: a ground nobody thought
of is one the desk can never reach, and its absence is indistinguishable from emptiness (L1.28a).
This crawler is pointed at a FRONTIER it grows itself -- every page it reads is also read for
links, every link that carries trading vocabulary in any language becomes a candidate source, and
every source carries its own measured yield so the next hour is spent where the last one paid.

MAX ROI IS THE SCHEDULER, and it is the only thing standing between "wide" and "useless". An hour
buys a bounded number of fetches; `world_frontier.due()` spends them highest-posterior-yield
first, shrunk toward the host mean and then the global mean so a lucky first fetch cannot capture
the budget, with an exploration bonus that keeps never-tried ground reachable and a per-host cap
that stops one prolific domain owning the hour. Depth and width are the same knob and this is it.

EVERYTHING IT FETCHES IS VAULTED POINT-IN-TIME. Raw bytes, gzipped, keyed by content hash with
the fetch timestamp -- never overwritten, so a claim can always be re-read against what the page
said WHEN IT SAID IT rather than what it says now. A crawler without that is a rumour mill: the
evidence for a candidate evaporates the moment the source edits the page.

WHAT IT EMITS. Rows in the miner-discovery contract that
`research/miner_candidate_compiler.py` already consumes, so a page stating an exact rule
(registered family + params + a symbol the broker quotes) becomes an executable candidate that
reaches the ten gates this hour, and everything else becomes a LEAD that steers the family-free
search. No row is invented and no family is guessed from a buzzword -- the compiler's own law.
"""
from __future__ import annotations

import argparse
import contextlib
import gzip
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlparse, urlsplit, urlunsplit

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "side_channels"))
sys.path.insert(0, str(BASE))

import world_frontier as wf  # noqa: E402  # type: ignore[import-not-found]

WORLD = BASE / "data" / "intelligence" / "world"
VAULT = WORLD / "vault"
REPORT = BASE / "reports" / "world_crawl.json"

#: Browser UA, because a bot string is refused or served a stub by a large share of the ground
#: this desk needs -- the gotcha recorded in the free-data-plane findings, where a healthy source
#: reads as dead purely from its User-Agent.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

#: Per-request and whole-run budgets. The run budget is what makes this safe to put on an hourly
#: timer beside everything else on a 3.8 GB box: it stops on the clock, not when it runs out of
#: world, and the frontier makes the next hour resume rather than restart.
FETCH_TIMEOUT_S = 12
#: WIDENED 2026-09-03 (principal: "explore every area possible ... every time 24/7"). The run is
#: hourly, so the old 900s/60-fetch pair spent a quarter of each slot and left the rest idle --
#: 1,440 fetches a day against a frontier capped at 40,000. 2400s still lands well inside the
#: hour with room for a slow tail, and 150 fetches raises the day to 3,600.
#:
#: BREADTH SCALES WITH IT AUTOMATICALLY, which is the point: `world_frontier.due()` sets its
#: per-host cap at `budget // 8`, so a bigger budget widens the number of hosts touched rather
#: than letting one prolific domain take the extra fetches. HOST_GAP_S is untouched -- politeness
#: per host is not what was limiting coverage, the run clock was.
RUN_BUDGET_S = 2400
DEFAULT_FETCHES = 150
MAX_BYTES = 1_500_000
#: Politeness gap between two requests to the same host, seconds.
HOST_GAP_S = 2.0
#: The frontier may not grow without bound on a box with no swap. New links past this are
#: DROPPED AND COUNTED, never silently discarded.
MAX_FRONTIER = 40_000
#: Links per page kept for SOURCE EXPANSION. The whole link set is already walked for the
#: frontier; this is only the slice handed to `source_shares.expand()` to classify, and it is
#: bounded so one link-farm page cannot fill a pass's expansion quota on its own.
EXPANSION_LINKS_PER_PAGE = 40


#: Fetches a source must have HAD before it is evictable. Under this it is unmeasured, and
#: evicting the unmeasured is how a frontier becomes a monument to whatever it happened to see
#: first -- the exact failure the two-level shrinkage exists to prevent one layer down.
EVICT_MIN_FETCHES = 3


def _evict_one(sources: dict) -> bool:
    """Make room by dropping the worst MEASURED dud. True when the frontier has space after.

    A FLAT CAP IS FIRST-COME-FIRST-SERVED, AND THAT IS THE WRONG AUCTION. At 40,000 entries every
    new link was DROPPED, so a URL discovered in week one and fetched five times for nothing
    outranked one discovered today and never tried -- purely by arrival order. Nothing about that
    ordering is evidence.

    It matters much more now than it did: `index_discovery` returns ~583 addresses per run
    instead of per hour of crawling, so the cap binds almost immediately and the frontier freezes
    against exactly the ground the indexes were added to reach.

    So the cap becomes a budget on SIZE rather than a lottery on arrival: the lowest-yielding
    source that has actually been MEASURED (>= EVICT_MIN_FETCHES fetches, zero candidates and zero
    leads) is evicted to make room. A source nobody has tried is never evicted -- absence of
    evidence is not evidence of no yield (L1.28a) -- and when nothing qualifies the caller drops
    and counts, exactly as before.
    """
    worst_key = None
    worst = None
    for k, s in sources.items():
        fetches = int(getattr(s, "fetches", 0) or 0)
        if fetches < EVICT_MIN_FETCHES:
            continue
        yielded = float(getattr(s, "candidates", 0) or 0) + float(getattr(s, "leads", 0) or 0)
        if yielded > 0:
            continue
        # Among proven duds, the one that has consumed the most fetches for nothing.
        if worst is None or fetches > worst:
            worst, worst_key = fetches, k
    if worst_key is None:
        return False
    sources.pop(worst_key, None)
    return True


def log(msg: str) -> None:
    print(f"[{datetime.now(tz=UTC):%H:%M:%S}] {msg}", flush=True)


class _Extract(HTMLParser):
    """Links, anchor text and visible text. One pass, no third-party parser on the money box."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.text: list[str] = []
        self._href: str | None = None
        self._skip = 0
        self.lang = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = dict(attrs)
        if tag in ("script", "style", "noscript"):
            self._skip += 1
        elif tag == "a" and d.get("href"):
            self._href = str(d["href"])
        elif tag == "html" and d.get("lang"):
            self.lang = str(d["lang"])[:8]

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1
        elif tag == "a":
            self._href = None

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        chunk = data.strip()
        if not chunk:
            return
        self.text.append(chunk)
        if self._href:
            self.links.append((self._href, chunk[:120]))


def _ascii_url(url: str) -> str:
    """Percent-encode a URL's non-ASCII parts. urllib raises UnicodeEncodeError without this.

    MEASURED on the first live crawl: `note.com/hashtag/システムトレード` -- a Japanese hub, exactly
    the ground this crawler exists to reach -- died with UnicodeEncodeError and was charged to
    that source as a failure. A crawler that cannot fetch a non-ASCII URL is not multilingual,
    and the failure is indistinguishable from a dead host.
    """
    try:
        url.encode("ascii")
    except UnicodeEncodeError:
        parts = urlsplit(url)
        netloc = parts.netloc
        with contextlib.suppress(UnicodeError):
            netloc = parts.netloc.encode("idna").decode("ascii")
        return urlunsplit((parts.scheme, netloc, quote(parts.path, safe="/%"),
                           quote(parts.query, safe="=&%?"), quote(parts.fragment, safe="%")))
    return url


def fetch(url: str) -> tuple[bytes | None, str]:
    """Bytes, or None with the reason. NEVER raises -- one bad page must not end the hour."""
    try:
        req = urllib.request.Request(_ascii_url(url), headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            # No language preference: asking for English is how a crawler that is supposed to
            # cover the world quietly stops covering most of it.
            "Accept-Language": "*",
        })
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S) as resp:
            ctype = str(resp.headers.get("Content-Type", ""))
            if "html" not in ctype and "text" not in ctype and "json" not in ctype:
                return None, f"content-type {ctype.split(';')[0] or 'unknown'}"
            return resp.read(MAX_BYTES), ""
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:60]}"
    except Exception as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:60]}"


def vault(url: str, raw: bytes) -> str:
    """Store the fetch point-in-time and return its content hash.

    NEVER OVERWRITTEN. The same page fetched twice with the same bytes writes once; changed bytes
    write a second file. A candidate's evidence therefore survives the source editing the page,
    which is the difference between a citation and a rumour.
    """
    digest = hashlib.sha256(raw).hexdigest()[:20]
    host = (urlparse(url).netloc or "unknown").replace(":", "_")[:60]
    out = VAULT / host / f"{digest}.gz"
    if out.exists():
        return digest
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({
        "url": url,
        "fetched_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "sha256_20": digest,
        "bytes": len(raw),
    }).encode() + b"\n" + raw
    out.write_bytes(gzip.compress(payload))
    return digest


# ------------------------------------------------------------------------------ what a page says

#: Timeframe tokens, multilingual where the word differs. Used only to ANNOTATE a lead -- the
#: compiler decides what becomes executable, and this module never guesses a family.
_TF = re.compile(r"\b(M1|M5|M15|M30|H1|H4|D1|W1|MN|1m|5m|15m|30m|1h|4h|daily|weekly|"
                 r"分钟|小时|日线|分鐘|日線|週線|時間足|日足|週足|분봉|일봉|주봉|дневн|недельн|"
                 r"intraday|intradía|intradiário|journalier|giornaliero|täglich|günlük|dzienn|"
                 r"nến ngày|รายวัน|harian|दैनिक)\b", re.IGNORECASE)

#: Mechanism vocabulary. A HIT IS A LEAD, NEVER A FAMILY. The compiler admits a family only when
#: the page names a registered one explicitly with params; this list exists so a lead can say
#: what it is ABOUT and steer the family-free search, which is the desk's own rule that a family
#: may not be guessed from a buzzword.
#: WORLD REGISTER (2026-09-05, principal: "deep forests in ALL major languages"). Each pattern
#: now carries the word in every script the desk mines -- traditional Chinese, Vietnamese,
#: Thai, Indonesian, Hindi, the European languages, Arabic, Turkish, Hebrew, Polish, the Nordic
#: languages -- so a Thai or Polish page is annotated with what it is ABOUT rather than read as
#: prose with no mechanism. Written as literals: a lexicon in escapes is unreadable.
_MECH = {
    "breakout": r"breakout|break out|突破|ブレイク|돌파|пробой|пробій|ruptura|phá vỡ|ทะลุ|"
                r"penembusan|"
                r"ब्रेकआउट|ausbruch|cassure|rottura|rompimento|kırılım|פריצה|wybici|uitbraak|"  # noqa: RUF001
                r"utbrott|"
                r"udbrud|utbrudd|läpimur|اختراق",
    "mean_reversion": r"mean revers|reversion|回归|回歸|逆張り|평균회귀|возврат|đảo chiều|hồi quy|"
                      r"กลับตัว|pembalikan|रिवर्सल|umkehr|rückkehr|retournement|inversione|"
                      r"reversión|"
                      r"reversão|dönüş|היפוך|odwrócen|omkeer|vändning|vending|käänne|انعكاس",
    "momentum": r"momentum|trend follow|动量|趋势|動量|趨勢|モメンタム|추세|импульс|tendencia|"
                r"xu hướng|"
                r"động lượng|โมเมนตัม|แนวโน้ม|tren\b|मोमेंटम|ट्रेंड|tendance|tendenza|tendência|"
                r"trendi|mwelekeo|زخم|اتجاه",
    "carry": r"carry trade|swap rate|息差|carry|キャリー|캐리|кэрри|chênh lệch lãi suất|"
             r"ส่วนต่างดอกเบี้ย|zinsdifferenz|différentiel de taux|cupom cambial|taşıma",  # noqa: RUF001
    "session": r"asian session|london open|new york open|亚盘|欧盘|美盘|東京時間|ロンドン|런던장|"
               r"뉴욕장|"
               r"лондон|нью-йорк|phiên|เปิดตลาด|sesi pagi|handelsschluss|séance|seduta|sesión|"
               r"pregão|"
               r"seans|sesj",
    "gap": r"\bgap\b|跳空|缺口|窓開け|갭|гэп|khoảng trống|แก๊ป|kurslücke|hueco|luka",
    "volatility": r"volatility|波动率|波動率|ボラティリティ|변동성|волатильн|biến động|"
                  r"ความผันผวน|"
                  r"volatilitas|वोलैटिलिटी|volatilität|volatilité|volatilità|volatilidad|"
                  r"volatilidade|"
                  r"oynaklık|תנודתיות|zmienność|volatiliteit|volatilitet|volatiliteetti|تذبذب",  # noqa: RUF001
    "seasonality": r"seasonal|day of week|turn of month|季节性|季節性|曜日|계절성|сезонн|mùa vụ|"
                   r"ฤดูกาล|"
                   r"musiman|मौसमी|saisonal|saisonnalité|stagionalità|estacionalidad|sazonalidade|"
                   r"mevsimsel|sezonow|seizoen|säsong|sæson|sesong|kausi|موسمي",
    "correlation": r"correlation|相关性|相關性|相関|상관관계|корреляц|tương quan|ความสัมพันธ์|"
                   r"korelasi|"
                   r"सहसंबंध|korrelation|corrélation|correlazione|correlación|correlação|"
                   r"korelasyon|"
                   r"מתאם|korelacj|correlatie|korrelasjon|korrelaatio|ارتباط",
    "orderflow": r"order flow|liquidity|流动性|流動性|オーダーフロー|유동성|ликвидн|thanh khoản|"
                 r"สภาพคล่อง|likuiditas|लिक्विडिटी|orderfluss|liquidité|liquidità|liquidez|"
                 r"likidite|"
                 r"נזילות|płynność|liquiditeit|likviditet|likviditeetti|سيولة",
    # zh practitioner register (2026-09-04): basis / calendar-spread / roll, the night session,
    # arbitrage, positioning -- the words a 七禾网 interview or a competition write-up uses.
    "basis": r"basis|基差|升水|贴水|跨期|换月|換月|展期|轉倉|term structure|期限结构|ベーシス|限月|"
             r"베이시스|базис|contango|backwardation|cơ sở|เบสิส|vencimiento|vencimento|vade",
    "arbitrage": r"arbitrage|套利|跨市|跨品种|内外盘|沪伦比|金银比|金油比|cointegrat|协整|裁定|"
                 r"차익거래|"
                 r"арбитраж|arbitraje|arbitragem|arbitraggio",
    "night_session": r"夜盘|夜盤|night session|收盘前|尾盘|早盘|开盘后|ナイトセッション|夜間|야간|"
                     r"вечерн|ข้ามคืน|qua đêm|after-hours|overnight",
    "positioning": r"positioning|持仓量|多空比|主力|cot report|净持仓|未平倉|建玉|미결제약정|"
                   r"수급|외국인|"
                   r"открыт интерес|khối ngoại|ต่างชาติ|asing|ओपन इंटरेस्ट|positionierung|"
                   r"positionnement|posizionamento|posicionamiento|posicionamento|法人|籌碼",
    # THE INDIRECT CHANNELS (2026-09-05): policy, flows, inventories, auctions -- the words a
    # central-bank release, a customs table or a harvest report uses, in the languages they
    # are written in, so a Brazilian soy page or a CBRT statement is a lead about a pair.
    "policy": r"rate decision|central bank|intervention|央行|加息|降息|升息|干预|干預|介入|"
              r"政策金利|"
              r"日銀|기준금리|한은|ставк|интервенц|цб рф|lãi suất|ngân hàng nhà nước|ดอกเบี้ย|ธปท|"
              r"suku bunga|bank indonesia|ब्याज दर|आरबीआई|leitzins|ezb|taux directeur|bce|tassi|"
              r"tipos de interés|tasa de interés|banxico|selic|copom|bacen|faiz|tcmb|"
              r"merkez bankası|"  # noqa: RUF001
              r"ריבית|בנק ישראל|stóp procentow|nbp|rpp|riksbank|norges bank|nationalbank|"
              r"korkopäätö|"
              r"sarb|cbrt|rbi|mas\b|hkma|boj|fomc|البنك المركزي|ساما|فائدة",
    "flow": r"fund flows|etf flows|exports|imports|remittances|northbound|southbound|资金流|資金流|"
            r"北向|南下|港股通|出口|進口|实需|輸出|投信|수출|экспорт|експорт|dòng tiền|xuất khẩu|"
            r"ส่งออก|ekspor|"
            r"निर्यात|export|fret|flux|flujo|fluxo|exportações|ihracat|eksport|vracht|frakt|vienti|"
            r"صادرات",
    "inventory": r"inventor(?:y|ies)|stockpile|warehouse stocks|harvest|crop|wasde|库存|庫存|"
                 r"产量|在庫|"
                 r"재고|запас|урожа|tồn kho|สต็อก|stok|persediaan|भंडार|lagerbestand|ernte|récolte|"
                 r"scorte|raccolto|existencias|cosecha|estoque|safra|hasat|zapas|voorraad|lager|"
                 r"skörd|høst|avling|varasto|مخزون",
    "auction": r"auction|tender results|入札|国债拍卖|국채 입찰|аукцион|офз|leilão|subasta|asta|"
               r"adjudication|ihale|przetarg|veiling|auktion|emissione|adjudicación",
}
_MECH_RE = {k: re.compile(v, re.IGNORECASE) for k, v in _MECH.items()}

#: A symbol claim is a 6-letter FX pair or a metal/index the desk might quote. Resolved against
#: the live registry below -- this only proposes.
_SYM = re.compile(r"\b(?:[A-Z]{6}|XAU[A-Z]{3}|XAG[A-Z]{3}|US30|US500|NAS100|GER40|UK100)\b")


def _fusion_symbols() -> set[str]:
    """The symbols Fusion actually quotes AND the desk can replay, UPPERCASED.

    IMPORTED, NEVER RESTATED (protocol rule 5). `merge_hypotheses.tradeable_universe` already
    answers this and already carries the principal's 2026-09-03 order to hunt only Fusion's
    tradeable set; a second list here would be a second answer to one question, and the two
    would disagree the first time the broker's offering changed.

    WHY THIS FILTER EXISTS. `_SYM` matches any six capital letters, so the crawler's own output
    named ONLINE 50 times, POINTS 27 and AVISOS 8 -- more often than every real instrument
    combined. A page mentioning "ONLINE" was being carried forward as a claim about an
    instrument. Resolving here rather than "later, by the compiler" is the point: the compiler
    never saw a symbol column it could trust, and neither could anything reading the artifact.

    DELIBERATELY A BROADER PREDICATE THAN `merge_hypotheses.tradeable_universe`, and the
    difference is the point. That function requires a registry entry AND an H1 parquet, because
    it answers "can a clock replay this?". The question HERE is only "is this token a real
    instrument the broker quotes?" -- and a page naming XAUUSD is making a claim about gold
    whether or not this machine happens to have gold bars cached. Measured while writing this:
    on a checkout with thin parquet coverage the replay predicate returned 24 symbols, so
    filtering on it would have silently discarded most real instrument mentions and looked
    exactly like pages that name nothing.

    Same file, same `tradeable` flag, one less condition -- not a second universe.

    An unreadable registry returns EMPTY and the caller then filters NOTHING: losing the
    universe file must never silently blank the symbol column, which would read as "this page
    mentions no instruments" (L1.28a).
    """
    try:
        meta = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))
    except (OSError, ValueError) as exc:
        log(f"universe unreadable ({type(exc).__name__}: {exc}); symbol column UNFILTERED")
        return set()
    # CLOSE_ONLY symbols are excluded for the same reason the hunt excludes them: no new
    # position can be opened, so a claim about one can never become a trade. Rows predating the
    # flag are ALLOWED rather than dropped (L1.28a) -- they tighten on the next fetch.
    return {str(k).upper() for k, v in meta.items()
            if not (isinstance(v, dict) and v.get("tradeable") is False)}


#: A page that hands over DATA is worth more than a page that describes an idea, and this desk
#: has measured exactly how much more. From `miner_candidates.per_source`, the conversion of
#: evidence rows into executable candidates:
#:
#:     broker_swaps         248 rows -> 248 candidates      structured data
#:     forexfactory          44 rows -> 107 candidates      structured calendar
#:     cot                   11 rows ->   7 candidates      structured positioning
#:     ff_calendar_vintage  113 rows ->   6 candidates      structured, point-in-time
#:     ---------------------------------------------------------------------------
#:     reddit / github / quant_se / bis_speeches / amarkets / world_crawler
#:                          341 rows ->   0 candidates      PROSE
#:
#: Prose converts at ZERO and it is not a tuning failure: the compiler's stated rule is "exact
#: recipe or structured causal data only; no prose-to-family guessing", and a blog post cannot
#: supply a registered family with exact params. So a crawler pointed at articles is spending
#: its hour on the one input class that provably cannot produce a candidate.
#:
#: These patterns steer it at the class that can: endpoints, dataset indexes, statistics
#: portals, official archives. It is a PRIORITY, not a filter -- prose still enters as a
#: deepening task, which is what prose is actually good for.
_DATA_HINT = re.compile(
    r"(?:/api/|/apis/|/data|/download|/export|\.csv|\.json|\.parquet|"
    r"/statistics|/statement|/stats/|/historical|/history/|/archive|/bulk|/quotes?/|"
    r"/opendata|/open-data|/document|developer|documentation|/docs/api|swagger|"
    # zh: 数据(data) 接口(interface/API) 下载(download) 历史(history) 开放数据(open data)
    r"数据|接口|下载|历史数据|开放数据|"
    # ja / ko / ru
    r"データ|ダウンロード|데이터|данные|статистик)",
    re.IGNORECASE)


#: Hosts that ARE data providers whatever their URL says. A path pattern alone misses them --
#: `fred.stlouisfed.org/categories` is one of the largest free macro archives in the world and
#: contains no data token at all, while `blog.example.com/my-data-journey` contains one. The
#: host is the more reliable signal for the institutions, the path for everything else.
#: Matched on the registrable suffix, so subdomains count.
#: File and API shapes that ARE the data rather than a page about it. A dataset page is only
#: worth an hour if something downloadable comes off it: measured 2026-09-03, the crawler had
#: banked 724 leads and produced ZERO executable candidates, because "this page concerns COT
#: data" is not COT data. These extensions turn a lead into an acquirable artifact.
_ENDPOINT_RE = re.compile(
    r"""href=["']([^"']+?\.(?:csv|tsv|json|jsonl|parquet|zip|gz|xlsx?|txt)(?:\?[^"']*)?)["']""",
    re.IGNORECASE)
#: API shapes that serve data without a file extension -- the majority of official statistics.
_API_RE = re.compile(
    r"""href=["']([^"']*(?:/api/|/download|/dataset|/series|/data\?|format=csv|"""
    r"""type=csv|export|bulkdownload|/sdmx|/rest/data)[^"']*)["']""", re.IGNORECASE)


_DATA_HOSTS = (
    "stlouisfed.org", "newyorkfed.org", "federalreserve.gov", "cftc.gov", "sec.gov",
    "bis.org", "ecb.europa.eu", "imf.org", "worldbank.org", "eia.gov", "bls.gov",
    "lbma.org.uk", "cmegroup.com", "datahub.io", "data.gov",
    # zh
    "tushare.pro", "akfamily.xyz", "shfe.com.cn", "sge.com.cn", "pbc.gov.cn",
    "stats.gov.cn", "chinabond.com.cn", "eastmoney.com", "csrc.gov.cn",
    # ja / ko
    "boj.or.jp", "jpx.co.jp", "bok.or.kr", "estat.go.jp",
    # ---- MT5-INSTRUMENT TICK AND BAR ARCHIVES (2026-09-03) -----------------------------------
    # Free historical tick/M1 for exactly the instrument classes Fusion quotes -- FX majors and
    # crosses, metals, indices, energy. This is the raw material the ten gates measure on, and
    # the desk has none of it beyond what its own recorder has collected since it started.
    "dukascopy.com", "histdata.com", "truefx.com", "forextester.com",
    "firstratedata.com", "kibot.com", "tickstory.com", "pepperstone.com",
    # ---- BROKER CONTRACT SPECIFICATIONS -------------------------------------------------------
    # THE HIGHEST-CONVERTING CLASS THE DESK HAS EVER MINED. `broker_swaps` turned 248 evidence
    # rows into 248 executable candidates -- 100%, the only source that ever did -- because a swap
    # and spec table IS structured causal data: a carry number per symbol per side, dated. Every
    # MT5 broker publishes one, and the desk was mining exactly one of them.
    "fusionmarkets.com", "icmarkets.com", "fpmarkets.com", "vantagemarkets.com",
    "eightcap.com", "tickmill.com", "axi.com", "blueberrymarkets.com", "thinkmarkets.com",
    # WIDENED 2026-09-03 (principal: "hunt maximum high value tick type free datasets ...
    # force it to explore every area possible"). Ordered by the desk's OWN measured
    # conversion, not by how interesting each class looks.
    #
    # (a) MORE BROKER SPEC TABLES. `broker_swaps` is the only source that has ever converted
    #     at 100% (248 rows -> 248 candidates), because a swap/spec table IS structured causal
    #     data: a dated carry number per symbol per side. Every one of these publishes one,
    #     and each is an independent cross-section of the same measurable.
    "exness.com", "xm.com", "hfm.com", "octafx.com", "roboforex.com", "instaforex.com",
    "admiralmarkets.com", "oanda.com", "forex.com", "swissquote.com", "cmcmarkets.com",
    "ig.com", "activtrades.com", "fxpro.com", "alpari.com", "global-prime.com",
    "vtmarkets.com", "monetamarkets.com", "errante.com", "tradeviewforex.com",
    # (b) FREE TICK / INTRADAY ARCHIVES beyond the first tranche -- the raw material the ten
    #     gates measure on, for exactly the instrument classes Fusion quotes.
    "stooq.com", "finam.ru", "eoddata.com", "alphavantage.co", "twelvedata.com",
    "tiingo.com", "polygon.io", "marketstack.com", "exchangerate.host", "frankfurter.app",
    "openexchangerates.org", "data-link.nasdaq.com",
    # (c) CENTRAL BANKS -- the carry leg. Policy rates and official fixings are the published
    #     half of every swap number in (a), which makes them its falsifier rather than a
    #     second opinion.
    "bundesbank.de", "banque-france.fr", "snb.ch", "rba.gov.au", "bankofcanada.ca",
    "bankofengland.co.uk", "rbnz.govt.nz", "norges-bank.no", "riksbank.se", "cbr.ru",
    # (d) EXCHANGES for the metals, energy and index underlyings the desk trades as CFDs.
    "lme.com", "theice.com", "eurex.com", "nasdaq.com", "euronext.com", "tocom.or.jp",
)


def is_data_source(url: str, title: str = "") -> bool:
    """Does this look like a place that hands over DATA rather than opinions about it?"""
    host = urlparse(url).netloc.lower()
    if any(host == h or host.endswith("." + h) for h in _DATA_HOSTS):
        return True
    return bool(_DATA_HINT.search(url) or (title and _DATA_HINT.search(title)))


def data_endpoints(text: str, base: str) -> list[str]:
    """Absolute URLs on this page that ARE data: files and data APIs, deduped and capped.

    THE DIFFERENCE BETWEEN A LEAD AND AN ASSET. A page ABOUT the CFTC archive converts at zero,
    exactly like every other prose row -- the desk measured 341 of those. The .csv links ON that
    page are the archive. Extracting them here is what lets a dataset page produce something the
    compiler can admit, instead of one more row asserting that data exists somewhere.
    """
    from urllib.parse import urljoin
    out: list[str] = []
    seen: set[str] = set()
    for rx in (_ENDPOINT_RE, _API_RE):
        for m in rx.findall(text or ""):
            try:
                full = urljoin(base, str(m))
            except ValueError:
                continue
            if full.startswith(("http://", "https://")) and full not in seen:
                seen.add(full)
                out.append(full)
            if len(out) >= 200:
                return out
    return out


def read_page(raw: bytes, url: str) -> dict[str, Any]:
    """Links, language and the trading claims a page makes. Pure; no network, no state."""
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:
        return {"links": [], "symbols": [], "timeframes": [], "patterns": [], "lang": "",
                "title": "", "text_len": 0, "endpoints": []}
    parser = _Extract()
    with contextlib.suppress(Exception):
        parser.feed(text)                       # a malformed page still yields what it parsed
    body = " ".join(parser.text)[:400_000]

    endpoints = data_endpoints(text, url)

    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()[:200]

    # RESOLVED AGAINST FUSION, HERE, not "later by somebody". `_SYM` is six capital letters, so
    # unfiltered it named ONLINE more often than every real instrument combined.
    claimed = set(_SYM.findall(body))
    known = _fusion_symbols()
    symbols = sorted(claimed & known) if known else sorted(claimed)

    # STORY CLAIMS (2026-09-04). A page that says, in Chinese or English, "gold reverses after
    # the night-session open when the day range is wide" names a testable mechanism even when it
    # names no registered family. `mechanism_claims` keeps such sentences verbatim, maps the
    # instrument to its MT5 analogue (沪金 -> XAUUSD) and drops crypto-exchange venues; the
    # deepening worker turns a claim into an exact recipe or rejects it. The crawler still never
    # emits a family or params.
    claims: list[dict[str, Any]] = []
    try:
        from libs.research.mechanism_claims import extract_claims
        claims = extract_claims(body, max_claims=12, universe=known or None)
    except Exception as exc:                                     # the crawler must not die on it
        log(f"claim extraction failed ({type(exc).__name__}: {exc}); page carried as prose")
    for c in claims:
        for a in (c.get("instruments") or {}).get("analogues") or []:
            if a not in symbols:
                symbols.append(a)

    return {
        "links": [(urljoin(url, href), anchor) for href, anchor in parser.links[:400]],
        "symbols": symbols[:24],
        "symbols_rejected": len(claimed) - len(symbols) if known else 0,
        "timeframes": sorted({t.upper() for t in _TF.findall(body)})[:8],
        "patterns": sorted({k for k, rx in _MECH_RE.items() if rx.search(body)}),
        "lang": parser.lang,
        "title": title,
        "text_len": len(body),
        "endpoints": endpoints,
        "claims": claims,
    }


def to_discovery(url: str, page: dict[str, Any], digest: str, terms_note: str = ""
                 ) -> dict[str, Any] | None:
    """A page as a miner-contract row, or None when it claims nothing worth carrying.

    NOTHING IS INVENTED HERE. `symbols` are tokens the page actually contains and the compiler
    resolves them against the live Fusion registry; `patterns` say what the page is ABOUT so the
    family-free search can be steered; no `family` or `params` is emitted, because this crawler
    cannot know that a page's prose is a registered family's exact rule and guessing one is the
    precise failure `miner_candidate_compiler` was written to stop.

    Confidence is the count of independent things the page asserted, not a feeling: a page naming
    a symbol, a timeframe and a mechanism is worth more than one naming a symbol.
    """
    is_data = is_data_source(url, page.get("title") or "")
    claims = list(page.get("claims") or [])
    # A DATASET IS WORTH CARRYING EVEN WHEN IT NAMES NO PATTERN. An API index or a statistics
    # portal is exactly the input class that converts (broker_swaps: 248 rows, 248 candidates),
    # and it typically contains none of the mechanism prose this filter was written around --
    # so the old rule discarded the only pages that could ever pay.
    if not page["symbols"] and not page["patterns"] and not is_data and not claims:
        return None
    signals = (bool(page["symbols"]) + bool(page["timeframes"]) + bool(page["patterns"])
               + bool(claims))
    return {
        "source": "world_crawler",
        # WHICH CLASS OF INPUT THIS IS, on the row. Measured conversion: structured data 100%,
        # 96%, 64%; prose 0% across 341 rows and six sources. A consumer that cannot tell them
        # apart must treat a blog post and a CSV endpoint as the same evidence, which is how a
        # crawler's whole hour goes to the class that provably cannot produce a candidate.
        # A STORY is prose that states a mechanism sentence; it converts through the deepening
        # worker (kind story_mechanism), which plain prose cannot.
        "kind": "dataset" if is_data else ("story" if claims else "prose"),
        "title": page["title"] or url[:120],
        "url": url,
        "published": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "symbols": page["symbols"],
        "timeframes": page["timeframes"],
        "patterns": page["patterns"],
        # A dataset page starts higher than a prose page asserting the same number of things,
        # because the desk has measured that the two convert at 100% and 0%.
        "confidence": round(min(0.95, 0.15 + 0.20 * signals + (0.20 if is_data else 0.0)), 2),
        # PROVENANCE, so a candidate that reaches the gauntlet can be traced to the exact bytes
        # that proposed it -- the vault entry is keyed by this hash.
        "lang": page["lang"],
        # THE ACQUIRABLE ARTIFACTS ON THIS PAGE. A dataset row with an empty list is still only a
        # claim that data exists; a row carrying endpoints is something the desk can go and get.
        # Counted separately in the report so "valuable datasets found" is a measured number
        # rather than a count of pages that mentioned the word.
        "endpoints": page.get("endpoints") or [],
        "n_endpoints": len(page.get("endpoints") or []),
        "vault_sha": digest,
        "host": urlparse(url).netloc,
        # THE CLAIMS THEMSELVES, verbatim with their instrument mapping, so the compiler's
        # deepening path can ask the seat about the sentence rather than the page title.
        "claims": [{k: c.get(k) for k in ("claim", "lang", "quantities", "direction", "horizon",
                                          "instruments", "claimed_performance", "claim_hash")}
                   for c in claims[:8]],
        "n_claims": len(claims),
        # THE ROUTING LABEL, NOT A BRAKE (LAWS 5e, 2026-09-23). A robots Disallow, a terms note
        # or a registry `machine_use_allowed=false` lands HERE, on the crawled row, and the page
        # is crawled exactly as any other. What the label withholds is REDISTRIBUTION; it has
        # never had anything to say about whether the desk may read and test the page.
        "terms_note": str(terms_note or ""),
    }


# ------------------------------------------------------------------------------------ the crawl

#: Ground the desk starts from when the frontier is empty. A SEED, NEVER A LIMIT -- the same law
#: `fetch_universe.SEED_CANDIDATES` follows. Every one of these is a hub whose links lead outward,
#: chosen so the first hour reaches several languages rather than one; after that the frontier is
#: whatever the crawler found, and this list stops mattering.
SEEDS = (
    "https://www.mql5.com/en/code/mt5/experts",
    "https://www.mql5.com/zh/code",
    "https://www.mql5.com/ja/code",
    "https://www.forexfactory.com/forums",
    "https://www.reddit.com/r/algotrading/top/?t=week",
    "https://quantocracy.com/",
    "https://www.quantstart.com/articles/",
    "https://xueqiu.com/",
    "https://www.joinquant.com/help/api/help",
    "https://uqer.datayes.com/",
    "https://zhuanlan.zhihu.com/quant",
    "https://qiita.com/tags/systemtrade",
    "https://note.com/hashtag/システムトレード",
    "https://smart-lab.ru/blog/",
    "https://www.rankia.com/foros/bolsa",
    "https://github.com/topics/algorithmic-trading",
    "https://github.com/topics/mt5",
    "https://arxiv.org/list/q-fin.TR/recent",
    "https://papers.ssrn.com/sol3/JELJOUR_Results.cfm?form_name=journalBrowse&journal_id=203",
    # ---- FREE DATA, which is the only class that has ever converted here ----------------
    #
    # The seeds above are hubs of PROSE and they have produced, across every prose source the
    # desk mines, exactly zero executable candidates from 341 rows. These are hubs of DATA:
    # official statistics, point-in-time archives and open APIs. broker_swaps -- one structured
    # feed -- produced 248 candidates from 248 rows on its own.
    #
    # Every one is free at the point of use and none needs a key to browse. What the desk does
    # with them still goes through the same ten gates; a dataset is not an edge, it is the raw
    # material an edge can be MEASURED on, which is the thing prose can never supply.
    #
    # en / official
    "https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm",
    "https://fred.stlouisfed.org/categories",
    "https://www.newyorkfed.org/markets/data-hub",
    "https://www.bis.org/statistics/index.htm",
    "https://www.ecb.europa.eu/stats/html/index.en.html",
    "https://www.lbma.org.uk/prices-and-data",
    "https://www.cmegroup.com/market-data/delayed-quotes/metals.html",
    "https://data.worldbank.org/indicator",
    "https://www.eia.gov/opendata/",
    "https://datahub.io/collections/finance",
    # zh -- the Chinese open-data and quant-library ground, which is large, free and almost
    # entirely absent from English-language crawling
    "https://tushare.pro/document/2",
    "https://akshare.akfamily.xyz/data/index.html",
    "https://www.shfe.com.cn/statements/dataview.html",
    "https://www.sge.com.cn/sjzx/mrhq",
    "https://www.pbc.gov.cn/diaochatongjisi/116219/index.html",
    "https://www.stats.gov.cn/sj/",
    "https://data.eastmoney.com/cjsj/",
    "https://www.chinabond.com.cn/cb/cn/yjfx/zzsj/index.shtml",
    # ja / ko / other
    "https://www.boj.or.jp/en/statistics/index.htm",
    "https://www.jpx.co.jp/markets/statistics-equities/index.html",
    "https://ecos.bok.or.kr/",
    # ---- TICK AND BAR ARCHIVES FOR THE INSTRUMENTS THIS DESK ACTUALLY TRADES (2026-09-03) -----
    #
    # Principal direction: hunt edge-strategy candidates and free tick-class datasets, and only
    # ones relative to MT5. These are free-at-point-of-use historical tick/M1 archives whose
    # coverage IS the Fusion universe -- FX majors and crosses, XAU/XAG, indices, energy -- not
    # equities-only feeds that would resolve to symbols this desk cannot trade.
    "https://www.dukascopy.com/swiss/english/marketwatch/historical/",
    "https://www.histdata.com/download-free-forex-data/",
    "https://www.truefx.com/truefx-historical-downloads/",
    "https://forextester.com/data/datasources",
    "https://firstratedata.com/free-intraday-data",
    "https://www.kibot.com/free_historical_data.aspx",
    # ---- BROKER CONTRACT SPECS: the one class measured at 100% conversion ---------------------
    #
    # `broker_swaps` produced 248 candidates from 248 rows. Nothing else the desk mines comes
    # close, and the reason is structural: a swap/spec table is a dated carry number per symbol
    # per side, which is exactly what the compiler's "structured causal data" rule admits. The
    # desk was mining ONE broker's table. These are the other MT5 brokers quoting the same
    # instruments, so the same extractor applies to all of them.
    "https://fusionmarkets.com/trading/forex",
    "https://www.icmarkets.com/global/en/trading-conditions/contract-specifications",
    "https://www.fpmarkets.com/forex-trading/trading-conditions/",
    "https://www.vantagemarkets.com/trading-info/contract-specifications/",
    "https://www.eightcap.com/trading/contract-specifications/",
    "https://www.tickmill.com/trading/contract-specifications",
    "https://www.axi.com/int/trading-conditions",
    "https://blueberrymarkets.com/trading-conditions/",
    # ---- EXECUTABLE RECIPES: source code, not articles about source code ----------------------
    #
    # The compiler admits "exact recipe or structured causal data only; no prose-to-family
    # guessing". An article cannot supply a registered family with exact params -- but an EA's
    # SOURCE can: it names its entry condition, its parameters and their defaults. This is the
    # only prose-adjacent ground with a route to a candidate, and it is MT5-native.
    "https://www.mql5.com/en/code/mt5/experts",
    "https://www.mql5.com/en/code/mt5/indicators",
    "https://github.com/topics/mql5",
    "https://github.com/topics/metatrader5",
    # ---- THE CHINESE DEEP FOREST (principal 2026-09-04): STORIES THAT NAME MECHANISMS ---------
    #
    # Competition records, 七禾网/期货日报 trader interviews, the quant-platform communities,
    # Q&A and social, Gitee, Bilibili, the forums. Even a dubious trader story names a testable
    # mechanism, and `read_page` now keeps such sentences as CLAIMS (kind "story") for the
    # deepening worker to reverse-engineer. `research/deep_forest_miner.py` reaches the grounds
    # a link-frontier cannot (search-engine indexes, JS shells, platform APIs) and feeds every
    # URL it finds into this frontier, so the two grow the same ground.
    "https://www.7hcn.com/",
    "https://www.7hcn.com/article/list-1.html",
    "https://www.qhrb.com.cn/",
    "https://www.simuwang.com/",
    "https://www.joinquant.com/view/community/list?listType=1",
    "https://www.ricequant.com/community",
    "https://bbs.myquant.cn/",
    "https://bigquant.com/wiki/",
    "https://www.jisilu.cn/explore/",
    "https://www.taoguba.com.cn/",
    "https://bbs.pinggu.org/forum-2196-1.html",
    "https://gitee.com/explore/quant",
    "https://gitee.com/search?q=%E9%87%8F%E5%8C%96%E4%BA%A4%E6%98%93",
    "https://juejin.cn/search?query=%E9%87%8F%E5%8C%96%E4%BA%A4%E6%98%93",
    "https://www.futuresmag.com.cn/",
    "https://www.cfachina.org/",
    "https://futures.hexun.com/",
    "https://futures.eastmoney.com/",
    # ---- THE WORLD FOREST (principal 2026-09-05: "every place deep forest for all edges") ------
    #
    # One or two HUBS per region whose links lead outward into that region's practitioner
    # ground, in that region's language. `research/deep_forest_miner.py` works the same
    # regions by ROUTE (search index, platform APIs, feeds, archives) and feeds every URL it
    # finds into this frontier; these seeds are where the link-walk starts when the frontier
    # has nothing from that region yet. Seeds, never limits.
    # ja
    "https://fx.minkabu.jp/",
    "https://kabutan.jp/news/marketnews/",
    "https://media.rakuten-sec.net/",
    "https://zenn.dev/topics/systemtrade",
    # ko
    "https://www.paxnet.co.kr/",
    "https://velog.io/tags/퀀트",
    "https://ecos.bok.or.kr/",
    # zh-Hant (TW / HK)
    "https://www.ptt.cc/bbs/Stock/index.html",
    "https://www.ptt.cc/bbs/Option/index.html",
    "https://www.wantgoo.com/",
    "https://www.macromicro.me/blog",
    "https://news.cnyes.com/news/cat/forex",
    "https://www.etnet.com.hk/www/tc/news/categorized_news.php?category=commentary",
    "https://www.hkex.com.hk/News/Research-Reports?sc_lang=en",
    # sea (sg / vn / th / id / my / ph)
    "https://forums.hardwarezone.com.sg/forums/money-mind.31/",
    "https://www.investingnote.com/",
    "https://f319.com/",
    "https://cafef.vn/thi-truong-chung-khoan.chn",
    "https://pantip.com/forum/sinthorn",
    "https://stock2morrow.com/",
    "https://investasi.kontan.co.id/",
    "https://klse.i3investor.com/web/blog/list",
    "https://www.pinoyinvestor.com/",
    # in / south asia
    "https://tradingqna.com/latest",
    "https://forum.valuepickr.com/latest",
    "https://blog.quantinsti.com/",
    "https://zerodha.com/varsity/",
    "https://www.mcxindia.com/market-data",
    # anz
    "https://hotcopper.com.au/",
    "https://www.aussiestockforums.com/forums/",
    "https://www.rba.gov.au/publications/rdp/",
    "https://www.sharetrader.co.nz/",
    # mena (ar / tr / he)
    "https://www.arabictrader.com/",
    "https://www.argaam.com/",
    "https://www.bloomberght.com/",
    "https://evds2.tcmb.gov.tr/",
    "https://www.globes.co.il/",
    "https://www.boi.org.il/en/",
    # africa
    "https://www.moneyweb.co.za/",
    "https://www.resbank.co.za/en/home/what-we-do/statistics",
    "https://nairametrics.com/",
    "https://www.businessdailyafrica.com/",
    "https://www.cbe.org.eg/en/",
    "https://www.bkam.ma/",
    # west (en)
    "https://www.elitetrader.com/et/",
    "https://forum.wilmott.com/",
    "https://quant.stackexchange.com/questions?tab=votes&pagesize=50",
    "https://www.quantconnect.com/forum",
    "https://forums.babypips.com/latest",
    "https://www.forexpeacearmy.com/community/forums/",
    "https://quantpedia.com/blog/",
    "https://alphaarchitect.com/blog/",
    "https://macrosynergy.com/research/",
    "https://www.cmegroup.com/insights/economic-research.html",
    "https://www.cboe.com/insights/",
    "https://www.trade2win.com/",
    "https://www.bankofengland.co.uk/working-paper/working-papers",
    "https://www.bankofcanada.ca/research/staff-working-papers/",
    # institutional
    "https://www.imf.org/en/Publications/WP",
    "https://www.ecb.europa.eu/pub/research/working-papers/html/index.en.html",
    "https://www.federalreserve.gov/econres/feds/index.htm",
    "https://www.newyorkfed.org/research/staff_reports/index.html",
    "https://www.bis.org/cbspeeches/index.htm",
    "https://www.usda.gov/oce/commodity/wasde",
    "https://www.jodidata.org/oil/",
    "https://www.icco.org/statistics/",
    "https://www.ico.org/new_historical.asp",
    "https://www.gold.org/goldhub/data",
    "https://www.balticexchange.com/en/data-services/market-information0/dry-services.html",
    "https://www.treasurydirect.gov/auctions/announcements-data-results/",
    "https://alfred.stlouisfed.org/",
    # eu (de / fr / it / es / nl)
    "https://www.wallstreet-online.de/diskussion/",
    "https://stock3.com/",
    "https://www.bundesbank.de/de/publikationen/forschung/diskussionspapiere",
    "https://www.boursorama.com/bourse/forum/",
    "https://forum.finanzaonline.com/",
    "https://www.x-trader.net/",
    "https://www.iex.nl/forum/",
    "https://data.snb.ch/",
    # nordics
    "https://www.riksbank.se/en-gb/statistics/",
    "https://www.norges-bank.no/en/topics/Statistics/",
    "https://www.nationalbanken.dk/en/what-we-do/statistics",
    "https://www.suomenpankki.fi/fi/tilastot/",
    # east eu (pl / cz / hu / ua)
    "https://www.stockwatch.pl/",
    "https://nbp.pl/statystyka-i-sprawozdawczosc/",
    "https://www.cnb.cz/en/statistics/",
    "https://www.mnb.hu/en/statistics",
    "https://bank.gov.ua/ua/statistic",
    # ru (full depth)
    "https://forum.mfd.ru/forum/",
    "https://t.me/s/markettwits",
    "https://t.me/s/russianmacro",
    "https://www.moex.com/ru/marketdata/",
    "https://www.cbr.ru/statistics/",
    "https://rosstat.gov.ru/",
    "https://habr.com/ru/hubs/finance/",
    # latam (pt / es)
    "https://www.infomoney.com.br/mercados/",
    "https://clubedovalor.com.br/blog/",
    "https://quantbrasil.com.br/",
    "https://www.bcb.gov.br/publicacoes/wps",
    "https://www.conab.gov.br/info-agro/safras",
    "https://www.eleconomista.com.mx/mercados/",
    "https://www.banxico.org.mx/SieInternet/",
    "https://si3.bcentral.cl/Siete/",
    "https://www.cochilco.cl/",
    "https://www.rava.com/",
    "https://www.bcra.gob.ar/PublicacionesEstadisticas/Principales_variables.asp",
)


def frontier_seeds() -> tuple[str, ...]:
    """The watched organisations' own pages, from the frontier registry.

    THE MINER WAS READING ABOUT THESE FIRMS BY ACCIDENT. `frontier_supervisor.scout()` filters the
    intelligence roots for rows that MENTION a tracked organisation, and `registry.FIRMS` lists
    twenty-two of them -- but no firm page was ever seeded anywhere on this desk, so the only rows
    it could match were incidental mentions in material gathered for something else. An hourly
    organ whose whole subject is those organisations had no path to their own words.

    Seeded HERE rather than fetched in `frontier_intel`, because this crawler already owns the
    fetch budget, the rate limiting, the vault, the deduplication and the source policy. A second
    fetch layer in that package would be a second thing to get blocked and a second copy of all
    five -- which is the reason the supervisor's scouting is offline by design.

    Soft-failing on purpose: a crawler that cannot start because an unrelated package moved is a
    worse outcome than a crawl without these seeds, and the rest of the ground is still worth
    covering.
    """
    try:
        sys.path.insert(0, str(BASE))
        from frontier_intel import registry as _registry
        return _registry.crawl_seeds()
    except Exception as exc:
        log(f"frontier seeds unavailable ({type(exc).__name__}: {exc}) -- crawling without them")
        return ()


def seed(sources: dict[str, wf.Source]) -> int:
    added = 0
    for url in (*SEEDS, *frontier_seeds()):
        if wf.add(sources, url, via="seed"):
            added += 1
    return added


def crawl(budget: int = DEFAULT_FETCHES, run_budget_s: int = RUN_BUDGET_S,
          seconds_per_host: float = HOST_GAP_S) -> dict[str, Any]:
    """One hour's crawl. Returns the report it writes."""
    started = time.time()
    sources = wf.load()
    n_seeded = seed(sources)
    if n_seeded:
        log(f"seeded {n_seeded} hub(s); frontier now {len(sources)}")

    picked = wf.due(sources, budget)
    # THE CRAWL BUDGET IS THE SOURCE REGISTRY'S SHARES (Tier-1 W17). This run stops on its clock,
    # so the HEAD of this list is what actually gets fetched -- re-ranking it by the registry's
    # published share IS spending the budget by measured intel ROI. Guarded: an absent, empty or
    # stale SOURCE_REGISTRY.json returns the list untouched and says which, so a report that did
    # not regenerate leaves today's order exactly as it was. NOTHING IS DROPPED FOR LICENCE,
    # TERMS, ROBOTS OR `machine_use_allowed` ANY MORE (LAWS 5e, 2026-09-23): a source carrying
    # any of those notes is CRAWLED, with the note recorded as `terms_note` on every row it
    # produces. The only removal left is one of the five refused acts of the hard boundary.
    share_meta: dict[str, Any] = {"status": "unavailable", "why": "source_shares not importable"}
    share_state: dict[str, Any] | None = None
    terms_labels: dict[str, str] = {}
    try:
        sys.path.insert(0, str(BASE))
        from research import source_shares
        share_state = source_shares.load()
        picked, share_meta = source_shares.order_picked(picked, share_state)
        terms_labels = {str(r.get("url") or ""): str(r.get("terms_note") or "")
                        for r in (share_meta.get("labelled") or []) if r.get("url")}
    except Exception as exc:
        share_meta = {"status": "unavailable", "why": f"{type(exc).__name__}: {exc}"}
    # THE PROPOSER SEAT, OPTIONAL: what is worth LOOKING FOR next, as search strings.
    # The crawler's frontier is a set of URLs it already holds; the seat proposes TERMS, and the
    # seat itself refuses anything shaped like an address, so nothing here can route a fetch. A
    # term reaches the world only through `to_discovery`, which every row already passes, and
    # the hard boundary's five refused acts still apply unchanged. No panel, no call, no change.
    seat_hint: dict[str, Any] = {"verdict": "UNMEASURED"}
    try:
        from libs.research import proposer_seat as _ps
        seat_hint = _ps.ask(
            "world_crawler", "terms",
            task=("Propose search phrases that would surface a market mechanism this desk has "
                  "probably not read: obscure venue microstructure, a scheduled flow nobody "
                  "models, a participant constraint. Phrases only, no sites."),
            context=[f"hosts already on the frontier: "
                     f"{len({s.host for s in sources.values()})}",
                     f"sources already held: {len(sources)}"],
            n=8).to_row()
    except Exception as _exc:                             # pragma: no cover - optional seat
        seat_hint = {"verdict": "UNMEASURED", "why": f"{type(_exc).__name__}: {_exc}"}

    log(f"frontier {len(sources)} source(s) across "
        f"{len({s.host for s in sources.values()})} host(s); crawling {len(picked)} this pass "
        f"| shares {share_meta.get('status')}: {share_meta.get('why')}")

    rows: list[dict[str, Any]] = []
    observed: dict[str, list[tuple[str, str]]] = {}
    discovered = dropped = unchanged = 0
    failures: Counter[str] = Counter()
    langs: Counter[str] = Counter()
    last_host_hit: dict[str, float] = {}

    for src in picked:
        if time.time() - started > run_budget_s:
            log(f"run budget {run_budget_s}s spent; {len(picked)} planned, stopping here. "
                f"The frontier resumes next hour rather than restarting.")
            break

        gap = seconds_per_host - (time.time() - last_host_hit.get(src.host, 0.0))
        if gap > 0:
            time.sleep(min(gap, seconds_per_host))
        last_host_hit[src.host] = time.time()

        raw, why = fetch(src.url)
        src.fetches += 1
        src.last_fetched = datetime.now(tz=UTC).isoformat(timespec="seconds")
        if raw is None:
            src.failures += 1
            src.consecutive_failures += 1
            failures[why.split(":")[0]] += 1
            continue
        src.consecutive_failures = 0

        digest = vault(src.url, raw)
        if digest == src.last_hash:
            # UNCHANGED IS A MEASUREMENT, not a wasted fetch: it decays this source's score so
            # the hour moves to ground that is actually moving.
            src.unchanged_streak += 1
            unchanged += 1
            continue
        src.last_hash, src.unchanged_streak = digest, 0

        page = read_page(raw, src.url)
        if page["lang"]:
            src.lang = page["lang"]
        langs[src.lang or "??"] += 1

        row = to_discovery(src.url, page, digest, terms_note=terms_labels.get(src.url, ""))
        if row:
            rows.append(row)
            src.leads += 1

        # SOURCE EXPANSION: this page's links are also evidence about its source's
        # NEIGHBOURHOOD, kept per source so `source_shares.expand()` can promote the ones served
        # by a source whose ROI share ROSE into candidate grounds in the registered grounds file.
        observed.setdefault(src.url, []).extend(
            (str(h), str(a)) for h, a in page["links"][:EXPANSION_LINKS_PER_PAGE])

        # RECURSION: every page read is also read for where to go next. This is the whole
        # difference between a crawler and a list of miners.
        for href, anchor in page["links"]:
            if len(sources) >= MAX_FRONTIER and not _evict_one(sources):
                dropped += 1
                continue
            if wf.worth_following(href, anchor) and wf.add(sources, href, via=src.url):
                discovered += 1

    wf.save(sources, note=f"crawl {datetime.now(tz=UTC):%Y-%m-%dT%H:%MZ}")

    expansion: dict[str, Any] = {"status": "unavailable", "why": "source_shares not importable"}
    try:
        from research import source_shares as _ss
        expansion = _ss.expand(observed, share_state)
    except Exception as exc:
        expansion = {"status": "unavailable", "why": f"{type(exc).__name__}: {exc}"}

    elapsed = round(time.time() - started, 1)
    report = {
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "elapsed_s": elapsed,
        "planned": len(picked),
        "fetched": sum(1 for s in picked if s.last_fetched),
        "rows_emitted": len(rows),
        "proposer_seat": seat_hint,
        "new_sources_discovered": discovered,
        "frontier_size": len(sources),
        "frontier_hosts": len({s.host for s in sources.values()}),
        "unchanged_pages": unchanged,
        "dropped_at_frontier_cap": dropped,
        "languages": dict(langs.most_common()),
        "failures": dict(failures.most_common()),
        # WHOSE BUDGET THIS WAS. `source_shares` says whether the registry's published shares
        # ranked this pass or whether the old order stood, and why -- an absence is a verdict,
        # never a silent fallback (L1.28a).
        "source_shares": share_meta,
        "source_expansion": expansion,
        # THE CAP IS REPORTED, NOT SILENT. A crawler that quietly stops discovering because it
        # hit a bound looks exactly like a web that ran out of pages (L1.28a).
        "frontier_cap": MAX_FRONTIER,
        "frontier_eviction": ("at the cap the lowest-yielding MEASURED dud is evicted to make "
                              "room; an unfetched source is never evicted, and when nothing "
                              "qualifies the new link is dropped and counted as before"),
        "note": ("Rows are LEADS in the miner-discovery contract. No family or params is emitted: "
                 "miner_candidate_compiler admits an executable candidate only from a page that "
                 "names a registered family explicitly, and guessing one from a buzzword is the "
                 "failure it exists to prevent."),
    }

    if rows:
        stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M")
        out = WORLD / f"discoveries_{stamp}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
        log(f"-> {out.relative_to(BASE)} ({len(rows)} row(s))")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1), encoding="utf-8")
    log(f"crawled {report['fetched']}/{report['planned']} in {elapsed}s | "
        f"{len(rows)} lead(s) | +{discovered} new source(s) | "
        f"frontier {len(sources)} across {report['frontier_hosts']} host(s) | "
        f"langs {dict(langs.most_common(6))}")
    if failures:
        log(f"failures: {dict(failures.most_common(6))}")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fetches", type=int, default=DEFAULT_FETCHES)
    ap.add_argument("--budget-s", type=int, default=RUN_BUDGET_S)
    ap.add_argument("--host-gap", type=float, default=HOST_GAP_S)
    args = ap.parse_args()
    crawl(args.fetches, args.budget_s, args.host_gap)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
