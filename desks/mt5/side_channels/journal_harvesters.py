"""Published research outside the English feeds: OAI-PMH and official-API readers.

THE GAP (coordinator, 2026-11-25). The paper miners read English RSS: NBER, the Fed, BIS, the
ECB, arXiv. Japanese, Korean, Russian, French, Spanish and Portuguese scholarship reached the
desk only as HTML grounds in deep_forest_sources.json, with no measured yield and no row the
yield rule could fund. This module reads the machine interfaces those literatures publish.

THREE READERS, ONE PASS, EVERY SOURCE A ROW IN research_feeds.json ("harvesters"):
  oai_pmh   ListRecords in oai_dc, date-incremental (`from`), per set when the repository's sets
            are journals, resumption tokens persisted so a pass resumes where the last one
            stopped. KCI, the SciELO country nodes, RePEc, HAL, CyberLeninka.
  jstage    J-STAGE WebAPI article search (service=3), keyword by keyword.
  openalex  OpenAlex works, one row per LANGUAGE, restricted to the Economics, Econometrics and
            Finance field. OpenAlex is CC0 and indexes the journals J-STAGE, CyberLeninka and
            HAL host, so it is the lawful route to the literatures whose own hosts refuse us.

WHAT WAS READ BEFORE ANY OF THIS SHIPPED (2026-11-25, from the authoring container; the verdict
and its evidence sit on each config row, and `terms_page_read` is true only where the page was
opened):
  * J-STAGE WebAPI terms (rev. 2024-06-11): for-profit use needs JST's prior approval (art. 2.2),
    API data may not be kept machine-readable beyond 24 hours (art. 3.5). CLOSED.
  * HAL OAI: api.archives-ouvertes.fr/robots.txt disallows /oai/ and /search/, and the OAI
    conditions say no commercial use of extracted data. CLOSED.
  * CyberLeninka user agreement 6.2 forbids automated collection of information and metadata,
    4.2 limits every service to personal non-commercial use. CLOSED.
  * RePEc: "free to do whatever you want with metadata from RePEc archives". OPEN.
  * SciELO: CC-BY is the network standard, commercial reuse included. OPEN per country node;
    each node's own robots.txt still decides on the box (Chile and Peru disallow, Brazil sits
    behind a bot wall -- none is worked around).
  * KCI: an OAI-PMH endpoint published for harvesting, no key. OPEN on that basis.
A CLOSED row is registered, costs nothing and is never fetched; it opens by editing its `terms`
with the evidence, never by code.

LEGITIMACY, PER FETCH. Terms are necessary, not sufficient: every URL goes through the desk's
one robots gate (research/robots_gate.py) under the honest client name, a Disallow or an unread
robots.txt stops the fetch and is billed, a site with no robots.txt is fetched and counted.
One request a second, no retries, no key, no login. An HTML answer where XML or JSON was due is
a bot wall: recorded as `not_data`, never parsed, never retried inside the pass. A 403 or 429
stops every other source on that host for the rest of the pass.

WHAT A DONATED ROW CARRIES. `source` is the HARVESTER'S OWN NAME, not the miner's: the compiler
stamps `miner:<source>` and source_registry resolves that to `src:paper:<name>`, so a
certification is credited to the one source that found the paper and the yield rule moves that
source's budget, not a pooled seat's. `symbols` holds the MT5 instruments the title and keywords
name in any of the languages below (the compiler reads declared instruments before prose, and
its prose reader is English). Title and keywords only: an abstract that mentions coffee is not
a paper about coffee. Exotic pairs are never declared.

THE TOPIC SCREEN IS NOT A VETO ON AN EDGE. KCI and SciELO publish every discipline through one
endpoint; a paper is donated only when it names a market phrase (MARKET_RE). The count screened
out is published per source in jh_status, so a screen that eats a literature is visible.

FAILURE IS VISIBLE. Every source writes a jh_status entry each pass: ok, empty, closed,
set_aside (robots), not_data (bot wall), error, deferred. An error also donates a fetch_error
row, as research_feeds does.
"""
# ruff: noqa: RUF001 -- the lexicons below are Cyrillic, Turkish and CJK on purpose
from __future__ import annotations

import importlib
import json
import re
import time
import urllib.parse
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from side_channels import research_depth_miners as rdm
except ModuleNotFoundError:                             # run from inside side_channels/
    import research_depth_miners as rdm  # type: ignore[no-redef]

ET = rdm.ET
Row = dict[str, Any]
RowFn = Callable[..., Row]
#: (harvester name, url) -> (may fetch, label, why). Production: `robots_gate_for_pass`.
Gate = Callable[[str, str], tuple[bool, str, str]]

FEEDS_CONFIG: Path = rdm.FEEDS_CONFIG
ORGAN = "journal_harvesters"
#: The product token robots.txt groups are matched on (RFC 9309) is the UA's leading token.
AGENT = rdm.HONEST_UA
#: Under the rotating sweep this miner shares a 600 s slice, as research_feeds does.
DEADLINE_S = 600.0
SEEN_CAP = 120_000
#: Requests one source may spend in one pass unless its row says otherwise.
MAX_REQUESTS = 4
#: First pass reads this far back; later passes read from the day the previous walk began.
LOOKBACK_DAYS = 30
#: A finished walk restarts this many days before the day it began: datestamps are per day and
#: repositories stamp late, and the seen-set makes the overlap free.
OVERLAP_DAYS = 2
SETS_TTL_DAYS = 7
OPEN_TERMS = rdm.OPEN_TERMS
#: Without a key OpenAlex pages by number and serves the first 10,000 results of a query; paging
#: by cursor answers 401 and asks for a key bound to an email address. No key is requested or
#: sent: the owner's address is never given to a third party by this desk's code.
OPENALEX_MAX_PAGE = 100
OPENALEX_SELECT = ("id,doi,title,publication_date,language,primary_location,"
                   "abstract_inverted_index,primary_topic,keywords")

# ------------------------------------------------------------------- what a paper is about
#: A paper is donated when its title or keywords name a MARKET (its abstract too, when the source
#: or the record is already economics: `screen_abstract`, ECON_SUBJECT_RE). Phrases, not bare
#: stems, in en / es / pt / fr / it / de / tr / ru / ja / zh / ko: the first live pass, with bare
#: stems, donated 85 of 300 KCI records -- folklore and tourism among them -- because `cambio`,
#: `курс` and `선물` are everyday words. The compiler and the gauntlet do the judging; this only
#: keeps botany and case law out of the docket.
MARKET_RE = re.compile(
    r"exchange rate|foreign exchange|\bforex\b|currenc|monetary polic|interest rate|yield curve"
    r"|(?:government|sovereign|corporate) bonds?|bond (?:market|yield|return|spread)"
    r"|treasury (?:bond|yield|bill|market)|stock (?:market|return|price|index)"
    r"|equity (?:market|return|premi)|asset pric|volatility|futures (?:market|price|contract)"
    r"|index futures|\bhedg|option pric|options? market|financial derivativ|derivatives market"
    r"|commodity (?:price|market|futures)|commodities|gold (?:price|market|return|futures)"
    r"|price of gold|crude oil|oil (?:price|market|shock)|inflation|central bank"
    r"|portfolio (?:select|optimi|choice|return|allocation|management|risk)|risk premi"
    r"|momentum (?:strateg|effect|return|profit|trading)|price momentum|carry trade"
    r"|market microstructure|market liquidity|order flow|\barbitrage"
    r"|trading (?:strateg|rule|volume|system|cost|signal)|(?:algorithmic|insider) trading"
    r"|financial market|capital market|(?:stock|excess|asset|expected|abnormal) returns"
    # es / pt / fr / it
    r"|tipo de cambio|tasa de (?:cambio|inter[eé]s)|taxa de (?:c[aâ]mbio|juros)|cambiari|divisas"
    r"|mercados? (?:de valores|financier|burs[aá]til|cambiario|de capitales|de capitais"
    r"|de divisas|accionario|de futuros|de a[cç][oõ]es|de acciones)|bolsa de valor|burs[aá]til"
    r"|pre[cç]os? d[ae]s? a[cç][oõ]es|precio de las acciones|volatilidad|volatilidade|volatilit[eéà]"
    r"|inflaci[oó]n|infla[cç][aã]o|pol[ií]tica monet|banco central|precio del oro|pre[cç]o do ouro"
    r"|petr[oó]leo|taux de change|taux d.int[eé]r[eê]t|march[eé]s? financ|bours(?:e|ier)"
    r"|politique mon[eé]taire|banque centrale|prix d[eu] l?.?(?:or|p[eé]trole)\b|tasso di cambio"
    r"|mercat[oi] finanziar"
    # de / tr
    r"|wechselkurs|zinss[aä]tz|leitzins|aktienm[aä]rkt|aktienkurs|geldpolitik|finanzm[aä]rkt"
    r"|d[oö]viz kuru|faiz oran|borsa istanbul|hisse sened|enflasyon|alt[ıi]n fiyat"
    # ru
    r"|валютн\w* (?:курс|рын)|обменн\w* курс|курс\w* (?:рубля|валют|доллара)|процентн\w* ставк"
    r"|ключев\w* ставк|рын\w* акций|облигац|волатильн|фьючерс|инфляц|денежно-кредитн"
    r"|центральн\w* банк|цен\w* на (?:золото|нефть)|рын\w* нефти|фондов\w* рын"
    r"|финансов\w* рын|доходност\w* (?:акций|облигаций)|биржев"
    # ja / zh
    r"|為替|金利|株式市場|株価|債券|先物|金融政策|物価|原油|金価格|ボラティリティ|日経平均|円安|円高"
    r"|汇率|利率|股票|股市|债券|期货|货币政策|通胀|通货膨胀|黄金|波动率"
    # ko
    r"|환율|금리|주식시장|주식수익|주가|채권|선물시장|선물가격|선물거래|통화정책|인플레이션|원유"
    r"|변동성|금융시장|증권시장|외환",
    re.IGNORECASE)
#: A record filed under one of these DISCIPLINES (KCI's dc:subject is the discipline) is read as
#: far as its abstract; everything else is judged on title and keywords alone, because any long
#: abstract mentions a price somewhere.
ECON_SUBJECT_RE = re.compile(
    r"econom|financ|경제|경영|무역|회계|금융|経済|金融|经济|эконом|финанс", re.IGNORECASE)

#: Instruments a paper names -> the MT5 symbols it is about. Majors, metals, energy, indices,
#: softs and bonds only: an exotic pair is never declared (exotics are banned, 2026-11-24).
INSTRUMENTS: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = tuple(
    (re.compile(p, re.IGNORECASE), s) for p, s in (
        (r"\bgold\b|\boro\b|\bouro\b|\bl'or\b|prix de l.or|золот|金価格|金相場|黄金|금값|금 가격"
         r"|alt[ıi]n fiyat|goldpreis", ("XAUUSD",)),
        (r"\bsilver\b|\bplata\b|\bprata\b|серебр|銀価格|白银|은 가격", ("XAGUSD",)),
        (r"crude|\bbrent\b|\bwti\b|petr[oó]le|p[eé]trole|нефт|原油|원유|roh[oö]l|ham petrol",
         ("XTIUSD", "XBRUSD")),
        (r"natural gas|gas natural|g[aá]s natural|gaz naturel|природн\w* газ|天然ガス|天然气"
         r"|천연가스", ("XNGUSD",)),
        (r"\bcopper\b|\bcobre\b|cuivre|\bмед[ьи]\b|銅価格|铜价|구리", ("XCUUSD",)),
        (r"\byen\b|\bjpy\b|\biene\b|иен[аыу]|円相場|円安|円高|ドル円|日元|엔화|엔/달러",
         ("USDJPY",)),
        (r"\beuro\b|\beur\b|евро\b|ユーロ|欧元|유로", ("EURUSD",)),
        (r"sterling|\bgbp\b|pound|libra esterlina|livre sterling|фунт\w* стерл|ポンド|英镑|파운드",
         ("GBPUSD",)),
        (r"swiss franc|\bchf\b|franco su[ií][zç]o|franc suisse|швейцарск\w* франк|スイスフラン"
         r"|瑞士法郎", ("USDCHF",)),
        (r"australian dollar|\baud\b|d[oó]lar australiano|австралийск\w* доллар|豪ドル|澳元"
         r"|호주 달러", ("AUDUSD",)),
        (r"canadian dollar|\bcad\b|d[oó]lar canad|dollar canadien|канадск\w* доллар|カナダドル"
         r"|加元", ("USDCAD",)),
        (r"new zealand dollar|\bnzd\b|ニュージーランドドル|新西兰元", ("NZDUSD",)),
        (r"dollar index|\bdxy\b|[ií]ndice d[eo]l? d[oó]lar|индекс доллара|ドル指数|美元指数"
         r"|달러 인덱스|달러지수", ("USDX",)),
        (r"nikkei|日経平均|日経225|닛케이", ("JPN225",)),
        (r"s&p ?500|s&p500|sp500", ("US500",)),
        (r"nasdaq|ナスダック|나스닥|纳斯达克", ("NAS100",)),
        (r"dow jones|ダウ平均|다우존스|道琼斯", ("US30",)),
        (r"\bdax\b", ("GER40",)),
        (r"cac ?40", ("FRA40",)),
        (r"ftse ?100", ("UK100",)),
        (r"euro ?stoxx", ("EUSTX50",)),
        (r"hang seng|恒生|ハンセン|항셍", ("HK50",)),
        (r"asx ?200", ("AUS200",)),
        (r"\bibex\b", ("E35",)),
        (r"treasury (?:yield|bond|note)|us treasur|bonos del tesoro|米国債|美国国债|미국 국채"
         r"|казначейск\w* облигац", ("UST10Y",)),
        (r"\bgilts?\b", ("UKGILT",)),
        (r"\bwheat\b|\btrigo\b|\bbl[eé]\b|пшениц|小麦|밀 가격", ("WHEAT",)),
        (r"\bcorn\b|\bmaize\b|\bma[ií]z\b|\bmilho\b|кукуруз|トウモロコシ|玉米|옥수수", ("CORN",)),
        (r"soybean|\bsoja\b|\bсо[яеи]\b|大豆|대두", ("SOYBEAN",)),
        (r"\bcoffee\b|\bcaf[eé]\b|кофе|コーヒー|咖啡|커피", ("COFARA",)),
        (r"\bsugar\b|az[uú]car|a[cç][uú]car|\bsucre\b|сахар|砂糖|白糖|설탕", ("SUGAR",)),
        (r"\bcotton\b|algod[oó]n|algod[aã]o|хлопок|хлопк|綿花|棉花|면화", ("COTTON",)),
        (r"\bcocoa\b|\bcacao\b|\bcacau\b|какао|カカオ|可可|코코아", ("USCOCOA",)),
    ))


def is_market(*fields: Any) -> bool:
    """True when any field names a market term in any covered language."""
    return any(MARKET_RE.search(str(f or "")) for f in fields)


def symbols_named(*fields: Any) -> list[str]:
    """The MT5 symbols these fields name, in INSTRUMENTS order, each once."""
    text = " ".join(str(f or "") for f in fields)
    out: list[str] = []
    for pat, syms in INSTRUMENTS:
        if pat.search(text):
            out.extend(s for s in syms if s not in out)
    return out


# ------------------------------------------------------------------------------- parsing
class NotData(ValueError):
    """The host answered with something that is not the XML or JSON its interface serves."""


def _root(body: str) -> Any:
    head = body.lstrip()[:400].lower()
    if not head.startswith("<") or head.startswith(("<!doctype html", "<html")):
        raise NotData("the answer is not XML (an HTML page or a challenge)")
    if "<!doctype" in body[:2000].lower() or "<!entity" in body[:2000].lower():
        raise NotData("the answer carries a DOCTYPE or entity declaration; refused")
    try:
        return ET.fromstring(body.encode("utf-8"))
    except Exception as exc:                            # ParseError, or defusedxml's refusals
        raise NotData(f"unparseable XML: {type(exc).__name__}") from exc


def _txt(el: Any) -> str:
    return rdm._clean("".join(el.itertext()), 4000) if el is not None else ""


def parse_oai(body: str) -> dict[str, Any]:
    """One OAI-PMH response -> {"records", "sets", "token", "error"}.

    Elements are matched by local-name: SciELO declares `oai-dc`, KCI and CyberLeninka `oai_dc`.
    A deleted record is skipped. `error` is the protocol's own code (`noRecordsMatch`,
    `badResumptionToken`, ...): an answer, not a failure of the fetch.
    """
    root = _root(body)
    if rdm._local(root.tag) != "oai-pmh":
        raise NotData(f"not an OAI-PMH document (root <{rdm._local(root.tag)}>)")
    out: dict[str, Any] = {"records": [], "sets": [], "token": None, "error": None}
    for el in root.iter():
        name = rdm._local(el.tag)
        if name == "error":
            out["error"] = el.attrib.get("code") or "error"
        elif name == "resumptiontoken":
            out["token"] = (el.text or "").strip() or None
        elif name == "set":
            spec = name_ = ""
            for ch in el:
                if rdm._local(ch.tag) == "setspec":
                    spec = (ch.text or "").strip()
                elif rdm._local(ch.tag) == "setname":
                    name_ = _txt(ch)
            if spec:
                out["sets"].append((spec, name_))
        elif name == "record":
            rec = _oai_record(el)
            if rec:
                out["records"].append(rec)
    return out


def _oai_record(el: Any) -> dict[str, Any] | None:
    rec: dict[str, Any] = {"titles": [], "subjects": [], "descriptions": [], "authors": []}
    for node in el.iter():
        name = rdm._local(node.tag)
        text = (node.text or "").strip()
        if name == "header" and node.attrib.get("status") == "deleted":
            return None
        if name == "identifier" and "oai_id" not in rec and not node.attrib:
            rec["oai_id"] = text
        if name == "datestamp":
            rec["published"] = text[:25]
        elif name == "title" and text:
            lang = str(node.attrib.get("lang") or "").lower()
            rec["titles"].append((lang, rdm._clean(text, 300)))
        elif name == "subject" and text:
            rec["subjects"].append(rdm._clean(text, 120))
        elif name == "description" and text:
            rec["descriptions"].append(rdm._clean(text, 1500))
        elif name == "creator" and text:
            rec["authors"].append(rdm._clean(text, 120))
        elif name == "language" and text:
            rec["language"] = text[:12]
        elif name == "identifier" and text:
            kind = str(node.attrib.get("type") or "").lower()
            if text.startswith("http") and ("url" not in rec or kind == "doi"):
                rec["url"] = text                           # a DOI beats the first plain link
    if not rec["titles"]:
        return None
    if "url" not in rec and str(rec.get("oai_id", "")).startswith("http"):
        rec["url"] = rec["oai_id"]
    return rec


def _english_first(pairs: list[tuple[str, str]]) -> str:
    """The English title when the repository gives one (the compiler reads English), then the
    original appended so nothing the source said is dropped."""
    eng = [t for lang, t in pairs if lang in ("en", "eng", "english")]
    rest = [t for lang, t in pairs if lang not in ("en", "eng", "english")]
    if eng and rest and rest[0] != eng[0]:
        return f"{eng[0]} / {rest[0]}"[:300]
    return (eng or rest)[0]


def parse_jstage(body: str) -> dict[str, Any]:
    """J-STAGE WebAPI service=3 -> {"records", "total", "error"}. `<status>` non-zero is the
    API's own error (ERR_001 = no results), carried as `error`."""
    root = _root(body)
    out: dict[str, Any] = {"records": [], "total": None, "error": None}
    for el in root.iter():
        name = rdm._local(el.tag)
        if name == "status" and (el.text or "0").strip() not in ("0", ""):
            out["error"] = (el.text or "").strip()
        elif name == "totalresults" and (el.text or "").strip().isdigit():
            out["total"] = int((el.text or "0").strip())
        elif name == "entry":
            rec: dict[str, Any] = {"titles": [], "subjects": [], "descriptions": [],
                                   "authors": []}
            for ch in el:
                cn = rdm._local(ch.tag)
                if cn == "article_title":
                    for lang in ch:
                        if _txt(lang):
                            rec["titles"].append((rdm._local(lang.tag), _txt(lang)[:300]))
                elif cn == "article_link":
                    links = {rdm._local(x.tag): (x.text or "").strip() for x in ch}
                    rec["url"] = links.get("en") or links.get("ja") or ""
                elif cn == "material_title":
                    rec["subjects"].extend(_txt(x)[:120] for x in ch if _txt(x))
                elif cn == "author":
                    rec["authors"].extend(_txt(x)[:120] for x in ch.iter()
                                          if rdm._local(x.tag) == "name" and _txt(x))
                elif cn == "pubyear" and (ch.text or "").strip():
                    rec["published"] = (ch.text or "").strip()[:10]
            if rec["titles"]:
                out["records"].append(rec)
    return out


def parse_openalex(body: str) -> dict[str, Any]:
    """OpenAlex /works page -> {"records"}. The abstract arrives as an inverted index
    (word -> positions) and is rebuilt in order."""
    try:
        doc = json.loads(body)
    except ValueError as exc:
        raise NotData("the answer is not JSON (an HTML page or a challenge)") from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("results"), list):
        raise NotData("not an OpenAlex works page")
    out: dict[str, Any] = {"records": []}
    for w in doc["results"]:
        if not isinstance(w, dict) or not w.get("title"):
            continue
        inv = w.get("abstract_inverted_index") or {}
        words = sorted((p, t) for t, ps in inv.items() if isinstance(ps, list) for p in ps)
        topic = w.get("primary_topic") or {}
        loc = w.get("primary_location") or {}
        subjects = [str(k.get("display_name")) for k in w.get("keywords") or []
                    if isinstance(k, dict) and k.get("display_name")]
        if topic.get("display_name"):
            subjects.insert(0, str(topic["display_name"]))
        out["records"].append({
            "titles": [("", rdm._clean(str(w["title"]), 300))],
            "subjects": subjects[:12],
            "descriptions": [rdm._clean(" ".join(t for _, t in words), 1500)] if words else [],
            "authors": [], "published": str(w.get("publication_date") or "")[:10],
            "url": str(w.get("doi") or loc.get("landing_page_url") or w.get("id") or ""),
            "venue": str((loc.get("source") or {}).get("display_name") or "")[:160]})
    return out


# ------------------------------------------------------------------------------ the walk
def load_harvesters(path: Path | None = None) -> list[dict[str, Any]]:
    doc = json.loads((path or FEEDS_CONFIG).read_text("utf-8"))
    return [h for h in doc.get("harvesters") or [] if isinstance(h, dict) and h.get("name")]


def _oai_url(h: dict[str, Any], cur: dict[str, Any], sets: list[str | None]) -> str:
    base = str(h["base"])
    if cur.get("token"):
        q = {"verb": "ListRecords", "resumptionToken": cur["token"]}
    else:
        frm = str(cur["from"])
        if h.get("granularity") == "second":
            frm += "T00:00:00Z"
        q = {"verb": "ListRecords", "metadataPrefix": h.get("metadata_prefix") or "oai_dc",
             "from": frm}
        s = sets[int(cur.get("set_i", 0)) % len(sets)]
        if s:
            q["set"] = s
    return f"{base}?{urllib.parse.urlencode(q)}"


def _jstage_url(h: dict[str, Any], cur: dict[str, Any]) -> str:
    kws = [str(k) for k in h.get("keywords") or ["finance"]]
    q = {"service": "3", "keyword": kws[int(cur.get("set_i", 0)) % len(kws)],
         "pubyearfrom": str(cur["from"])[:4], "start": str(int(cur.get("token") or 1)),
         "count": str(int(h.get("page_size", 100)))}
    return f"{h['base']}?{urllib.parse.urlencode(q)}"


def _openalex_url(h: dict[str, Any], cur: dict[str, Any]) -> str:
    flt = (f"language:{h['language']},primary_topic.field.id:{int(h.get('field', 20))},"
           f"from_publication_date:{cur['from']}")
    q = {"filter": flt, "sort": "publication_date:desc",
         "per-page": str(int(h.get("page_size", 100))), "page": str(int(cur.get("token") or 1)),
         "select": OPENALEX_SELECT}
    return f"{h['base']}?{urllib.parse.urlencode(q, safe=':,')}"


def _advance(cur: dict[str, Any], n_sets: int, today: date) -> bool:
    """Move to the next set; True when that finished the whole walk (the window then restarts
    from the day this walk began, less the overlap)."""
    cur["token"] = None
    cur["set_i"] = int(cur.get("set_i", 0)) + 1
    if cur["set_i"] < n_sets:
        return False
    began = date.fromisoformat(str(cur.get("began") or today.isoformat()))
    cur.update({"set_i": 0, "from": (began - timedelta(days=OVERLAP_DAYS)).isoformat(),
                "began": today.isoformat()})
    return True


def _resolve_sets(h: dict[str, Any], cur: dict[str, Any], fetch: Callable[[str], str],
                  today: date) -> list[str | None]:
    """The sets to walk. `sets` is explicit; `set_name_match` picks journals by name from
    ListSets, cached SETS_TTL_DAYS; neither means the whole repository as one walk."""
    if h.get("sets"):
        return [str(s) for s in h["sets"]]
    pattern = h.get("set_name_match")
    if not pattern:
        return [None]
    at = str(cur.get("sets_at") or "")
    if cur.get("sets") and at and (today - date.fromisoformat(at)).days < SETS_TTL_DAYS:
        return list(cur["sets"])
    rx = re.compile(str(pattern), re.IGNORECASE)
    found: list[str] = []
    token: str | None = None
    for _ in range(int(h.get("max_set_pages", 3))):
        q = {"verb": "ListSets", **({"resumptionToken": token} if token else {})}
        page = parse_oai(fetch(f"{h['base']}?{urllib.parse.urlencode(q)}"))
        found.extend(spec for spec, name in page["sets"] if rx.search(name))
        token = page["token"]
        if not token:
            break
    if not found:
        raise NotData(f"ListSets named no set matching {pattern!r}")
    cur.update({"sets": found, "sets_at": today.isoformat(), "set_i": 0, "token": None})
    return list(found)


def harvest(st: dict[str, Any], get_text: Callable[[str], str], row: RowFn, gate: Gate,
            config: list[dict[str, Any]] | None = None,
            clock: Callable[[], float] = time.monotonic, deadline_s: float = DEADLINE_S,
            today: date | None = None) -> list[Row]:
    """Every configured harvester, once. Mutates `st` (jh_seen, jh_status, jh_cursor)."""
    cfg = config if config is not None else load_harvesters()
    day = today or datetime.now(tz=UTC).date()
    t0 = clock()
    seen_list: list[str] = list(st.get("jh_seen", []))
    seen = set(seen_list)
    status: dict[str, Any] = st.setdefault("jh_status", {})
    cursors: dict[str, Any] = st.setdefault("jh_cursor", {})
    stopped_hosts: dict[str, str] = {}
    out: list[Row] = []
    for h in cfg:
        name, base = str(h["name"]), str(h.get("base") or "")
        host = (urllib.parse.urlsplit(base).hostname or "").lower()
        if h.get("terms") not in OPEN_TERMS:
            status[name] = {"at": rdm._now(), "status": "closed", "url": base,
                            "why": f"terms {h.get('terms') or 'unrecorded'}: "
                                   f"{str(h.get('terms_note') or 'no verdict recorded')[:240]}"}
            continue
        if clock() - t0 > deadline_s:
            status[name] = {"at": rdm._now(), "status": "deferred", "url": base,
                            "why": f"pass deadline {deadline_s:.0f}s reached"}
            continue
        if host in stopped_hosts:
            status[name] = {"at": rdm._now(), "status": "deferred", "url": base,
                            "why": f"host stopped this pass: {stopped_hosts[host]}"}
            continue
        cur = cursors.setdefault(name, {})
        cur.setdefault("from", (day - timedelta(days=int(h.get("lookback_days",
                                                               LOOKBACK_DAYS)))).isoformat())
        cur.setdefault("began", day.isoformat())
        tally = {"requests": 0, "items": 0, "new": 0, "screened_out": 0}

        def fetch(url: str, _name: str = name, _tally: dict[str, int] = tally) -> str:
            ok, label, why = gate(_name, url)
            if not ok:
                raise PermissionError(f"{label}: {why}")
            _tally["requests"] += 1
            return get_text(url)

        url = base
        try:
            out.extend(_walk(h, cur, fetch, row, seen, seen_list, tally, day))
            state = "ok" if tally["items"] else "empty"
            status[name] = {"at": rdm._now(), "status": state, "url": base, **tally,
                            "from": cur["from"], "resuming": bool(cur.get("token"))}
        except PermissionError as exc:
            status[name] = {"at": rdm._now(), "status": "set_aside", "url": url, **tally,
                            "why": str(exc)[:240]}
        except NotData as exc:
            cur["token"] = None
            status[name] = {"at": rdm._now(), "status": "not_data", "url": base, **tally,
                            "why": f"{exc}; not parsed, not retried this pass"}
            out.append(row(name, "fetch_error", f"{name}: {str(exc)[:160]}", base,
                           needs_selector_work=True, feed=name))
        except Exception as exc:
            code = getattr(getattr(exc, "response", None), "status_code", None)
            if code in (401, 403, 429) and host:
                stopped_hosts[host] = f"HTTP {code} on {name}"
            status[name] = {"at": rdm._now(), "status": "error", "url": base, **tally,
                            "error": f"{type(exc).__name__}: {str(exc)[:180]}"}
            out.append(row(name, "fetch_error", f"{name}: {str(exc)[:160]}", base,
                           needs_selector_work=True, feed=name))
    st["jh_seen"] = seen_list[-SEEN_CAP:]
    return out


def _walk(h: dict[str, Any], cur: dict[str, Any], fetch: Callable[[str], str], row: RowFn,
          seen: set[str], seen_list: list[str], tally: dict[str, int], day: date) -> list[Row]:
    proto = str(h.get("protocol") or h.get("route") or "oai_pmh")
    budget = int(h.get("max_requests", MAX_REQUESTS))
    out: list[Row] = []
    sets: list[str | None] = [None]
    if proto == "oai_pmh":
        sets = _resolve_sets(h, cur, fetch, day)
    elif proto == "jstage":
        sets = [str(k) for k in h.get("keywords") or ["finance"]]
    while tally["requests"] < budget:
        if proto == "oai_pmh":
            page = parse_oai(fetch(_oai_url(h, cur, sets)))
            if page["error"] == "badResumptionToken":       # expired: restart this set's page
                cur["token"] = None
                continue
            if page["error"] not in (None, "noRecordsMatch"):
                raise NotData(f"OAI-PMH error {page['error']}")
            token = page["token"]
        elif proto == "jstage":
            page = parse_jstage(fetch(_jstage_url(h, cur)))
            start = int(cur.get("token") or 1) + len(page["records"])
            more = bool(page["records"]) and start <= int(page["total"] or 0)
            token = str(start) if more else None
        elif proto == "openalex":
            page = parse_openalex(fetch(_openalex_url(h, cur)))
            nxt = int(cur.get("token") or 1) + 1            # page numbers: cursors need a key
            full = len(page["records"]) >= int(h.get("page_size", 100))
            token = str(nxt) if full and nxt <= OPENALEX_MAX_PAGE else None
        else:
            raise NotData(f"unknown protocol {proto!r}")
        out.extend(_take(h, page["records"], row, seen, seen_list, tally))
        if token:
            cur["token"] = token
        elif _advance(cur, len(sets), day):
            break
    return out


def _take(h: dict[str, Any], records: list[dict[str, Any]], row: RowFn, seen: set[str],
          seen_list: list[str], tally: dict[str, int]) -> list[Row]:
    name = str(h["name"])
    out: list[Row] = []
    for rec in records:
        tally["items"] += 1
        title = _english_first(rec["titles"])
        all_titles = [t for _, t in rec["titles"]]
        text = max(rec["descriptions"], key=len, default="")
        eng = [d for d in rec["descriptions"] if d.isascii() or _mostly_latin(d)]
        if eng and h.get("language") not in ("en", "es", "pt", "fr", "de", "it"):
            text = max(eng, key=len)                # an English abstract beside a CJK/Cyrillic one
        deep = h.get("screen_abstract") or ECON_SUBJECT_RE.search(" ".join(rec["subjects"]))
        if h.get("topic_screen", True) and not is_market(
                *all_titles, *rec["subjects"], text if deep else ""):
            tally["screened_out"] += 1
            continue
        key = rdm._key(name, rec.get("url") or rec.get("oai_id") or title)
        if key in seen:
            continue
        seen.add(key)
        seen_list.append(key)
        tally["new"] += 1
        extra = {k: v for k, v in (
            ("published", rec.get("published")), ("authors", "; ".join(rec["authors"][:8])),
            ("subjects", rec["subjects"][:12]), ("venue", rec.get("venue")),
            ("language", rec.get("language") or h.get("language")),
            ("region", h.get("region"))) if v}
        out.append(row(name, str(h.get("kind") or "paper"), title, rec.get("url") or "", text,
                       symbols=symbols_named(*all_titles, *rec["subjects"]),
                       feed=name, institution=str(h.get("institution") or ""), **extra))
    return out


def _mostly_latin(text: str) -> bool:
    return sum(ch.isascii() for ch in text) >= 0.9 * max(1, len(text))


# --------------------------------------------------------------------------- production
def robots_gate_for_pass() -> Gate:
    """The desk's one robots gate, with one robots.txt read per host per pass. A stop is billed
    (robots_gate.refuse); a fetch made because the host serves no robots.txt is counted."""
    try:
        robots_gate: Any = importlib.import_module("research.robots_gate")
    except ModuleNotFoundError:                         # only the repo root is on sys.path
        robots_gate = importlib.import_module("desks.mt5.research.robots_gate")
    cache: dict[tuple[str, str], Any] = {}

    def gate(name: str, url: str) -> tuple[bool, str, str]:
        label, why = robots_gate.read(url, AGENT, cache=cache)
        if robots_gate.stops(label):
            robots_gate.refuse(ORGAN, name, url, label, why)
            return False, label, why
        if label == robots_gate.ROBOTS_ABSENT:
            robots_gate.note_absent(ORGAN, name, url, why)
        return True, label, why
    return gate


def data_text(url: str, timeout: int = 60) -> str:
    """One GET under the honest client name; raises on a non-2xx with the response attached."""
    r = rdm.requests_get(url, headers={"Accept": "application/xml, text/xml, application/json;"
                                                 "q=0.9, */*;q=0.5"}, timeout=timeout)
    r.raise_for_status()
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding or "utf-8"     # SciELO nodes mislabel UTF-8 bodies
    return str(r.text)
