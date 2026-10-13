"""CENTRAL-BANK TONE -- a role of the LLM research lab (principal's idea 18, approved 2026-10-13).

WHAT IT DOES. Reads PBoC, BoJ, SARB, RBA and CBRT speeches, decisions and minutes IN THEIR
ORIGINAL LANGUAGE (zh, ja, en, en, tr), scores each for hawkish/dovish stance twice -- once with a
native-language lexicon (deterministic, reads no history) and once with a free-tier model through
`libs.ops.free_chain` -- and writes the readings as POINT-IN-TIME lake series that the registered
`exogenous_conditioner` family reads. It then donates exact conditioner cells on the currencies
each bank sets. The cells are hypotheses: the canonical gauntlet decides, and nothing here has
promotion authority.

WHY A NEW ORGAN AND NOT AN EDIT OF `side_channels/bis_speech_tone.py`. That organ scores the BIS
corpus with an ENGLISH lexicon for nine banks, writes a jsonl nothing executes, and covers none of
PBoC, SARB or CBRT. Its corpus and lexicon are reused here (imported, not copied): for RBA and
SARB the BIS text is the original language, so it is the history; for PBoC, BoJ and CBRT it is a
translation and lands in its own column (`tone_lex_en`) so it never mixes with native readings.

THE LOOK-AHEAD GUARD IS ENFORCED IN THE DATA, not only stamped on the cell. A model that scores a
2019 statement may know what the bank did in 2020; its 2019 reading is contaminated. So the
series carries `tone_llm` (every reading, for research) and `tone_llm_clean` (only documents
published on or after the scoring model's `evidence_from` -- the earlier of its registered
training cutoff and the day this organ first used it). Only `tone_lex` and `tone_llm_clean` are
ever donated as cells, so the sealed gauntlet, which does not read `lookahead_guard`, still cannot
count a contaminated window as evidence.

PIT. `available_time` is the publication stamp when the source gives a time, the next UTC midnight
when it gives only a date, and the speech date + 7 days for BIS rows (the BIS collection delay is
UNMEASURED; seven days is the conservative reading). The conditioner then lags a further 24h.

ACCESS. Official sources only, each with a terms row that FAILS CLOSED; robots.txt disallow is
respected; a challenge page, 403 or 429 is recorded BLOCKED and cooled for a day -- never retried
under another agent. Document TEXT is cached only under the gitignored lake; the tracked ledger
holds URL, title, hashes and scores, never the text.
"""

from __future__ import annotations

import gzip
import hashlib
import html
import io
import json
import math
import os
import re
import sys
import time
import urllib.parse
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(BASE / "side_channels"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

STATE_DIR = BASE / "data" / "llm_lab" / "cb_tone"
DOCS = STATE_DIR / "docs.jsonl"
SOURCES_CONFIG = STATE_DIR / "sources.json"
SOURCE_STATE = STATE_DIR / "source_state.json"
MODEL_FIRST_USED = STATE_DIR / "model_first_used.json"
SERIES_DIR = BASE / "data" / "lake" / "series"
TEXT_CACHE = BASE / "data" / "lake" / "cb_tone_text"
BIS_ZIP = BASE / "data" / "intelligence" / "central_banks" / "bis_speeches" / "speeches.zip"
DONATE_DIR = BASE / "data" / "intelligence" / "llm_lab"
ROLE = "CB_TONE"
UNMEASURED = "UNMEASURED"
UA = "quant-desk-cb-tone/1.0 (research; official sources only)"
BLOCK_COOLDOWN_H = 24
BIS_DELAY_DAYS = 7
MIN_OBSERVATIONS = 30          # family_exogenous_conditioner.MIN_OBSERVATIONS
EXCERPT_CHARS = 6000


@dataclass(frozen=True)
class Source:
    """One official feed. `kind` is rss (RSS/Atom) or html (a listing page of links)."""

    sid: str
    url: str
    kind: str
    lang: str
    include: str
    terms: str = "confirmed"
    terms_basis: str = ""


@dataclass(frozen=True)
class Bank:
    key: str
    name: str
    currency: str
    lang: str
    bis_names: tuple[str, ...]
    #: symbol -> side_when_high: hawkish (high tone) strengthens the bank's currency, so +1 where
    #: it is the base and -1 where it is the quote.
    symbols: dict[str, int]
    sources: tuple[Source, ...] = field(default_factory=tuple)


#: SEED, not a boundary: `data/llm_lab/cb_tone/sources.json` ({"<sid>": {...}}) edits a row (url,
#: include, terms) or adds one, so a moved page is a config change on the box, never a code edit.
#: Terms basis is recorded per row. Public pages are read politely; a row the config marks
#: "to_confirm" is skipped quietly, and nothing ever crosses a login, paywall, CAPTCHA or limit.
BANKS: dict[str, Bank] = {
    "PBOC": Bank("PBOC", "People's Bank of China", "CNH", "zh",
                 ("people's bank of china",), {"USDCNH": -1},
                 (Source("pboc_news", "http://www.pbc.gov.cn/goutongjiaoliu/113456/113469/index.html",
                         "html", "zh", r"货币政策|例会|讲话|致辞|演讲|答记者问|新闻发布会|利率|准备金",
                         "confirmed", "PRC Copyright Law Art.5: official communiques and decisions "
                         "of state organs are outside copyright; read and scored, never republished"),)),
    "BOJ": Bank("BOJ", "Bank of Japan", "JPY", "ja", ("bank of japan",),
                {"USDJPY": -1, "EURJPY": -1},
                (Source("boj_whatsnew_ja", "https://www.boj.or.jp/rss/whatsnew.xml", "rss", "ja",
                        r"講演|挨拶|議事要旨|主な意見|金融政策|記者会見|展望レポート",
                        "confirmed", "BoJ site terms: reproduction permitted with source "
                        "attribution (https://www.boj.or.jp/about/services/kiyaku.htm)"),)),
    "SARB": Bank("SARB", "South African Reserve Bank", "ZAR", "en",
                 ("south african reserve bank",), {"USDZAR": -1, "EURZAR": -1},
                 (Source("sarb_speeches", "https://www.resbank.co.za/en/home/publications/speeches",
                         "html", "en", r"speech|address|statement|monetary policy|MPC",
                         "confirmed", "public official statements fetched politely (principal's "
                         "no-ban ruling relayed 2026-10-13 16:10Z): never past a login, paywall, "
                         "CAPTCHA or rate limit; BIS corpus is the history"),)),
    "RBA": Bank("RBA", "Reserve Bank of Australia", "AUD", "en",
                ("reserve bank of australia",), {"AUDUSD": 1, "AUDJPY": 1},
                (Source("rba_speeches", "https://www.rba.gov.au/rss/rss-cb-speeches.xml", "rss",
                        "en", r".", "confirmed", "RBA content is CC BY 4.0 "
                        "(https://www.rba.gov.au/copyright/)"),
                 Source("rba_media", "https://www.rba.gov.au/rss/rss-cb-media-releases.xml", "rss",
                        "en", r"monetary policy|cash rate|minutes|statement", "confirmed",
                        "RBA content is CC BY 4.0 (https://www.rba.gov.au/copyright/)"))),
    "CBRT": Bank("CBRT", "Central Bank of the Republic of Turkiye", "TRY", "tr",
                 ("central bank of the republic of turkey", "central bank of the republic of "
                  "türkiye", "central bank of turkey"), {"USDTRY": -1, "EURTRY": -1},
                 (Source("cbrt_press_tr", "https://www.tcmb.gov.tr/wps/wcm/connect/tr/tcmb+tr/"
                         "main+menu/duyurular/basin", "html", "tr",
                         r"Para Politikası|PPK|Faiz|Konuşma|Sunum|Toplantı Özeti|Enflasyon Raporu",
                         "confirmed", "FSEK Art.31: officially published decisions are free to "
                         "use; read and scored, never republished"),)),
}

#: Native-language stance lexicons. Phrases where a bare word is ambiguous. English reuses the
#: BIS organ's lists so the two English readings can never drift apart.
LEXICON: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "zh": (("收紧", "加息", "上调", "提高存款准备金率", "稳健偏紧", "抑制通胀", "防止通胀",
            "通胀压力", "防范资产泡沫", "回笼流动性", "去杠杆", "保持流动性合理", "汇率稳定"),
           ("降准", "降息", "下调", "宽松", "适度宽松", "逆周期调节", "稳增长", "降低融资成本",
            "释放流动性", "加大货币政策调控力度", "支持实体经济", "精准滴灌", "降低存款准备金率")),
    "ja": (("利上げ", "引き上げ", "引き締め", "緩和の度合いを調整", "正常化", "上振れ",
            "インフレ圧力", "物価の上昇圧力", "国債買入れの減額"),
           ("利下げ", "緩和的", "金融緩和を継続", "追加緩和", "下振れリスク", "粘り強く",
            "低金利", "緩和的な金融環境", "国債買入れを継続")),
    "tr": (("sıkı para politikası", "sıkılaştırma", "faiz artırımı", "artırılmasına",
            "sıkı duruş", "enflasyonist baskı", "parasal sıkılaştırma", "yükseltilmesine",
            "ilave sıkılaştırma"),
           ("faiz indirimi", "indirilmesine", "gevşeme", "parasal genişleme", "destekleyici",
            "politika faizinin düşürülmesi", "ölçülü indirim")),
}


def _english_lexicon() -> tuple[tuple[str, ...], tuple[str, ...]]:
    try:
        import bis_speech_tone as bst
        return tuple(bst.HAWKISH), tuple(bst.DOVISH)
    except Exception:                                  # pragma: no cover - defensive
        return (("tighten", "raise interest rates", "restrictive"),
                ("accommodative", "easing", "rate cut"))


def lexicon(lang: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return LEXICON.get(lang) or _english_lexicon()


def score_lex(text: str, lang: str) -> tuple[int, int, float | None]:
    """(hawk hits, dove hits, net tone in [-1,1] or None). None, never 0.0, when no hit: 'no
    directional language' and 'balanced language' are different facts (L1.28a)."""
    hawk, dove = lexicon(lang)
    low = text.casefold()
    h = sum(low.count(p.casefold()) for p in hawk)
    d = sum(low.count(p.casefold()) for p in dove)
    return h, d, (round((h - d) / (h + d), 4) if h + d else None)


# ============================================================================ small helpers
def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except OSError:
        pass
    return out


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    os.replace(tmp, path)


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript|head)\b.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()


def pdf_to_text(body: bytes) -> str | None:
    """Text of a PDF, or None when no PDF reader is installed (NEEDS_PDF_TEXT, retried)."""
    try:
        import pypdf
    except Exception:
        return None
    try:
        reader = pypdf.PdfReader(io.BytesIO(body))
        return re.sub(r"\s+", " ", " ".join((p.extract_text() or "") for p in reader.pages[:40]))
    except Exception:
        return ""


def _cache_text(sha: str, text: str) -> None:
    TEXT_CACHE.mkdir(parents=True, exist_ok=True)
    p = TEXT_CACHE / f"{sha[:24]}.txt.gz"
    if not p.exists():
        p.write_bytes(gzip.compress(text.encode("utf-8")))


def _cached_text(sha: str) -> str:
    try:
        return gzip.decompress((TEXT_CACHE / f"{sha[:24]}.txt.gz").read_bytes()).decode("utf-8")
    except Exception:
        return ""


# ============================================================================ sources
def sources() -> list[tuple[Bank, Source]]:
    """Seed rows overlaid by the config. A config row cannot open a bank this module does not
    know, and a NEW row defaults to terms "to_confirm" -- the gate fails closed."""
    cfg = _read_json(SOURCES_CONFIG, {}) or {}
    out: list[tuple[Bank, Source]] = []
    seen: set[str] = set()
    for bank in BANKS.values():
        for s in bank.sources:
            row = cfg.get(s.sid) if isinstance(cfg.get(s.sid), dict) else {}
            out.append((bank, Source(s.sid, str(row.get("url") or s.url),
                                     str(row.get("kind") or s.kind), s.lang,
                                     str(row.get("include") or s.include),
                                     str(row.get("terms") or s.terms),
                                     str(row.get("terms_basis") or s.terms_basis))))
            seen.add(s.sid)
    for sid, row in cfg.items():
        if sid in seen or not isinstance(row, dict) or str(row.get("bank")) not in BANKS:
            continue
        bank = BANKS[str(row["bank"])]
        if str(row.get("kind")) not in ("rss", "html") or not str(row.get("url", "")).startswith(
                ("http://", "https://")):
            continue
        out.append((bank, Source(sid, str(row["url"]), str(row["kind"]),
                                 str(row.get("lang") or bank.lang), str(row.get("include") or "."),
                                 str(row.get("terms") or "to_confirm"),
                                 str(row.get("terms_basis") or ""))))
    return out


_CHALLENGE = re.compile(r"(?i)captcha|challenge-platform|wzws|verify you are human|"
                        r"enable javascript|cf-chl|access denied")


def _get(url: str, timeout: float) -> tuple[int, bytes, str]:
    import requests
    r = requests.get(url, timeout=timeout, headers={"User-Agent": UA})
    return r.status_code, r.content, str(r.headers.get("content-type") or "")


def _robots_ok(url: str, timeout: float) -> bool:
    """robots.txt disallow is respected. An unreadable robots file allows, as RFC 9309 says."""
    from urllib.robotparser import RobotFileParser
    parts = urllib.parse.urlsplit(url)
    try:
        code, body, _ = _get(f"{parts.scheme}://{parts.netloc}/robots.txt", timeout)
    except Exception:
        return True
    if code >= 400:
        return True
    rp = RobotFileParser()
    rp.parse(body.decode("utf-8", errors="replace").splitlines())
    return bool(rp.can_fetch(UA, url))


def _decode(body: bytes) -> str:
    head = body[:2000].decode("ascii", errors="ignore").lower()
    m = re.search(r"charset=[\"']?([a-z0-9_-]+)", head)
    for enc in ([m.group(1)] if m else []) + ["utf-8", "gb18030", "shift_jis"]:
        try:
            return body.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", errors="replace")


def _stamp(raw: str) -> tuple[str, str]:
    """(published_time ISO UTC, available_time ISO UTC) from a feed or page date."""
    raw = (raw or "").strip()
    if not raw:
        return "", ""
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        iso = dt.astimezone(UTC).isoformat(timespec="seconds")
        return iso, iso
    except (TypeError, ValueError, IndexError):
        pass
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if len(raw) > 10 and dt.tzinfo is not None:
            iso = dt.astimezone(UTC).isoformat(timespec="seconds")
            return iso, iso
        day = dt.date()
    except ValueError:
        m = re.search(r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})", raw)
        if not m:
            return "", ""
        try:
            day = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
        except ValueError:
            return "", ""
    pub = datetime(day.year, day.month, day.day, tzinfo=UTC)
    # A date with no time could be any hour of that day in the bank's zone: it is available, for
    # a backtest, from the next UTC midnight -- never earlier.
    return pub.isoformat(timespec="seconds"), (pub + timedelta(days=1)).isoformat(
        timespec="seconds")


def parse_listing(body: bytes, src: Source) -> list[dict[str, str]]:
    """Items {title, url, date} from an RSS/Atom feed or an HTML listing, filtered by `include`."""
    text = _decode(body)
    inc = re.compile(src.include)
    items: list[dict[str, str]] = []
    if src.kind == "rss":
        for block in re.findall(r"(?is)<(?:item|entry)\b.*?</(?:item|entry)>", text):
            title_m = re.search(r"(?is)<title[^>]*>(.*?)</title>", block)
            title = title_m.group(1) if title_m else ""
            title = html_to_text(re.sub(r"<!\[CDATA\[|\]\]>", "", title))
            link_m = (re.search(r"(?is)<link[^>]*>\s*(?:<!\[CDATA\[)?(https?://[^<\]\s]+)", block)
                      or re.search(r"(?is)<link[^>]*href=[\"'](https?://[^\"']+)", block))
            date_m = re.search(r"(?is)<(pubDate|dc:date|published|updated)[^>]*>(.*?)</\1>", block)
            if link_m and inc.search(title):
                items.append({"title": title[:300], "url": link_m.group(1).strip(),
                              "date": date_m.group(2).strip() if date_m else ""})
        return items
    for href, label, tail in re.findall(
            r"(?is)<a\b[^>]*href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>(.{0,200})", text):
        title = html_to_text(label)
        if not title or not inc.search(title):
            continue
        url = urllib.parse.urljoin(src.url, href.strip())
        if not url.startswith(("http://", "https://")):
            continue
        date_m = re.search(r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}", f"{tail} {href}")
        items.append({"title": title[:300], "url": url, "date": date_m.group(0) if date_m else ""})
    uniq: dict[str, dict[str, str]] = {}
    for it in items:
        uniq.setdefault(it["url"], it)
    return list(uniq.values())


def fetch_new(docs: dict[str, dict[str, Any]], state: dict[str, Any], *, deadline: float,
              max_fetch: int, timeout: float = 20.0) -> dict[str, Any]:
    """Pull every open source's listing and up to `max_fetch` new documents. Returns per-source
    outcomes; every skip is named (TERMS_CLOSED, BLOCKED, ROBOTS, COOLING, ERROR)."""
    outcomes: dict[str, Any] = {}
    fetched = 0
    now = datetime.now(UTC)
    for bank, src in sources():
        st = state.setdefault(src.sid, {})
        if src.terms != "confirmed":
            outcomes[src.sid] = {"state": "TERMS_CLOSED", "basis": src.terms_basis}
            continue
        until = str(st.get("cooling_until") or "")
        if until and until > now.isoformat():
            outcomes[src.sid] = {"state": "COOLING", "until": until, "why": st.get("why")}
            continue
        if time.time() > deadline:
            outcomes[src.sid] = {"state": "NOT_THIS_PASS", "why": "pass deadline"}
            continue

        def block(why: str, *, _st: dict[str, Any] = st, _sid: str = src.sid) -> None:
            _st.update({"cooling_until": (now + timedelta(hours=BLOCK_COOLDOWN_H)).isoformat(),
                        "why": why, "last_state": "BLOCKED"})
            outcomes[_sid] = {"state": "BLOCKED", "why": why}

        try:
            if not _robots_ok(src.url, timeout):
                block("robots.txt disallows the listing")
                continue
            code, body, _ = _get(src.url, timeout)
        except Exception as exc:
            st.update({"last_state": "ERROR", "why": f"{type(exc).__name__}"})
            outcomes[src.sid] = {"state": "ERROR", "why": type(exc).__name__}
            continue
        if code in (401, 403, 412, 429) or code >= 500:
            block(f"HTTP {code}: an access control or rate limit, never retried under another "
                  "agent")
            continue
        items = parse_listing(body, src) if code == 200 else []
        if code == 200 and not items and _CHALLENGE.search(body[:20000].decode(
                "utf-8", errors="ignore")):
            block("challenge page served: an automation block is never bypassed")
            continue
        new = [it for it in items if _doc_id(src.sid, it["url"]) not in docs]
        got = 0
        for it in new:
            if fetched >= max_fetch or time.time() > deadline:
                break
            row = _fetch_doc(bank, src, it, timeout)
            docs[row["id"]] = row
            fetched += 1
            got += 1
        st.update({"last_state": "OK" if code == 200 else f"HTTP {code}", "why": "",
                   "last_listing": _now(), "listed": len(items)})
        outcomes[src.sid] = {"state": "OK" if code == 200 else f"HTTP {code}",
                             "listed": len(items), "new": len(new), "fetched": got,
                             "owed": max(0, len(new) - got)}
    return outcomes


def _doc_id(sid: str, url: str) -> str:
    return f"{sid}:{_sha(url)[:16]}"


def _fetch_doc(bank: Bank, src: Source, item: dict[str, str], timeout: float) -> dict[str, Any]:
    pub, avail = _stamp(item.get("date", ""))
    row: dict[str, Any] = {
        "id": _doc_id(src.sid, item["url"]), "bank": bank.key, "source_id": src.sid,
        "url": item["url"], "title": item.get("title", ""), "lang": src.lang, "original": True,
        "published_time": pub, "available_time": avail, "retrieval_time": _now(),
        "text_sha": "", "chars": 0, "hawk": None, "dove": None, "tone_lex": None,
        "llm": None, "blocker": ""}
    if not avail:
        # Retrieval time is a valid, conservative availability stamp when the source gave none.
        row["available_time"] = row["retrieval_time"]
        row["published_time"] = row["retrieval_time"]
        row["stamp_basis"] = "no publication stamp in the listing: retrieval time used"
    try:
        if not _robots_ok(item["url"], timeout):
            row["blocker"] = "ROBOTS"
            return row
        code, body, ctype = _get(item["url"], timeout)
    except Exception as exc:
        row["blocker"] = f"FETCH_ERROR:{type(exc).__name__}"
        return row
    if code != 200:
        row["blocker"] = f"HTTP_{code}"
        return row
    is_pdf = "pdf" in ctype.lower() or item["url"].lower().endswith(".pdf")
    text = pdf_to_text(body) if is_pdf else html_to_text(_decode(body))
    if text is None:
        row["blocker"] = "NEEDS_PDF_TEXT"
        return row
    if len(text) < 200:
        row["blocker"] = "NEEDS_BODY_TEXT"
        return row
    _attach_text(row, text)
    return row


def _attach_text(row: dict[str, Any], text: str) -> None:
    sha = _sha(text)
    _cache_text(sha, text)
    h, d, tone = score_lex(text, str(row["lang"]))
    row.update({"text_sha": sha, "chars": len(text), "hawk": h, "dove": d, "tone_lex": tone,
                "blocker": ""})


# ============================================================================ BIS history
def ingest_bis(docs: dict[str, dict[str, Any]], state: dict[str, Any],
               zip_path: Path | None = None) -> dict[str, Any]:
    """The BIS corpus as history, once per corpus version. Original language for RBA and SARB;
    an English translation for the others, which lands in `tone_lex_en` and is never LLM-scored
    as if it were the original."""
    zp = zip_path or BIS_ZIP
    if not zp.exists():
        return {"state": UNMEASURED, "why": f"corpus absent: {zp.name}"}
    version = f"{zp.stat().st_size}:{int(zp.stat().st_mtime)}"
    if state.get("bis", {}).get("version") == version:
        return {"state": "CURRENT", "version": version}
    try:
        import bis_speech_tone as bst
    except Exception as exc:                           # pragma: no cover - defensive
        return {"state": "ERROR", "why": type(exc).__name__}
    names = [(n, b) for b in BANKS.values() for n in b.bis_names]
    today = datetime.now(UTC).date().isoformat()
    added = 0
    for rec in bst.iter_speeches(zp):
        day = (rec.get("date") or "")[:10]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) or day > today:
            continue
        head = f"{rec.get('title', '')} {rec.get('description', '')}".lower()
        hit = max(((len(n), b) for n, b in names if n in head), default=None,
                  key=lambda t: t[0])
        text = rec.get("text") or ""
        if hit is None or len(text) < 200:
            continue
        bank = hit[1]
        url = str(rec.get("url") or f"bis:{day}:{_sha(text)[:12]}")
        did = _doc_id("bis", url)
        if did in docs:
            continue
        pub = datetime.fromisoformat(day).replace(tzinfo=UTC)
        original = bank.lang == "en"
        row: dict[str, Any] = {
            "id": did, "bank": bank.key, "source_id": "bis", "url": url,
            "title": str(rec.get("title") or "")[:300], "lang": "en", "original": original,
            "published_time": pub.isoformat(timespec="seconds"),
            "available_time": (pub + timedelta(days=BIS_DELAY_DAYS)).isoformat(timespec="seconds"),
            "retrieval_time": _now(), "stamp_basis": f"BIS collection delay UNMEASURED: speech "
            f"date + {BIS_DELAY_DAYS}d", "llm": None, "blocker": ""}
        _attach_text(row, text)
        docs[did] = row
        added += 1
    state["bis"] = {"version": version, "ingested": _now(), "added": added}
    return {"state": "INGESTED", "added": added, "version": version}


# ============================================================================ model scoring
SYSTEM = ("You read one central-bank text in its original language and label its monetary-policy "
          "stance. Judge only what the text itself says; do not use any knowledge of what the bank "
          "or markets did afterwards. Reply with ONE JSON object and nothing else: "
          '{"stance": <number from -1 (very dovish) to 1 (very hawkish), 0 neutral>, '
          '"shift": "more_hawkish" | "more_dovish" | "unchanged" | "unclear" (versus the policy '
          'stance the text says was in place before), "quote": "<a verbatim excerpt of at most '
          '120 characters from the text that most supports the stance>"}')
SHIFT_VALUE = {"more_hawkish": 1.0, "more_dovish": -1.0, "unchanged": 0.0}


def excerpt(text: str, lang: str, limit: int = EXCERPT_CHARS) -> str:
    """The opening of the text plus the sentences that carry stance vocabulary, so a long minute
    reaches the model at its policy paragraphs rather than its table of contents."""
    if len(text) <= limit:
        return text
    hawk, dove = lexicon(lang)
    terms = [t.casefold() for t in hawk + dove]
    sentences = re.split(r"(?<=[.!?。！？])\s*", text)
    picked = [s for s in sentences if any(t in s.casefold() for t in terms)]
    head = text[: limit // 3]
    body = " ".join(picked)[: limit - len(head) - 5]
    return f"{head} ... {body}"


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s).casefold()


def parse_reading(raw: str, text: str) -> tuple[dict[str, Any] | None, str]:
    """A typed reading or a named discard. The quote must appear in the text: a model that
    cannot point at its evidence is not read."""
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        return None, "no JSON object"
    try:
        doc = json.loads(m.group(0))
    except ValueError:
        return None, "unparseable JSON"
    try:
        stance = float(doc.get("stance"))
    except (TypeError, ValueError):
        return None, "stance is not a number"
    if not math.isfinite(stance) or not -1.0 <= stance <= 1.0:
        return None, "stance outside [-1, 1]"
    shift = str(doc.get("shift") or "unclear")
    if shift not in (*SHIFT_VALUE, "unclear"):
        return None, f"shift {shift!r} outside the enumeration"
    quote = str(doc.get("quote") or "")
    if len(_norm(quote)) < 6 or _norm(quote)[:120] not in _norm(text):
        return None, "quote not found verbatim in the text"
    return {"stance": round(stance, 4), "shift": shift, "quote": quote[:160]}, ""


def _guard(model: str, first_used: dict[str, str]) -> dict[str, Any]:
    """The lab's guard, evaluated at the day this organ FIRST used the model: a document published
    after a model was already in service cannot be in its training data."""
    day = first_used.setdefault(model, _now()[:10])
    try:
        import llm_lab
        return llm_lab.lookahead_guard(model, at=day)
    except Exception:                                  # pragma: no cover - defensive
        return {"model": model, "model_training_cutoff": UNMEASURED, "evidence_from": day}


def score_with_model(docs: dict[str, dict[str, Any]], *, max_calls: int, deadline: float,
                     chat: Any = None) -> dict[str, Any]:
    """Score unscored ORIGINAL-language documents, newest first. Free tier only: the chain has no
    paid rung, and the seat's prompt hygiene (`scrub`) still runs on every prompt."""
    if chat is None:
        try:
            from libs.ops import free_chain
        except Exception:                              # pragma: no cover
            return {"state": UNMEASURED, "why": "free_chain unavailable"}
        chat = free_chain.chat
    try:
        from libs.research.proposer_seat import PromptRefused, scrub
    except Exception:                                  # pragma: no cover
        return {"state": UNMEASURED, "why": "prompt hygiene unavailable: nothing is sent"}
    first_used = _read_json(MODEL_FIRST_USED, {}) or {}
    open_ = [d for d in docs.values() if d.get("original") and d.get("text_sha")
             and not d.get("llm") and int(d.get("llm_attempts") or 0) < 3]
    # Newest live documents first (they are the clean, post-cutoff readings), then BIS history.
    todo = sorted(open_, key=lambda d: (d.get("source_id") != "bis",
                                        str(d.get("published_time"))), reverse=True)
    calls = ok = 0
    discards: dict[str, int] = {}
    exhausted = ""
    for d in todo:
        if calls >= max_calls or time.time() > deadline:
            break
        text = _cached_text(str(d["text_sha"]))
        if not text:
            d["blocker"] = "TEXT_CACHE_MISSING"
            continue
        bank = BANKS.get(str(d["bank"]))
        user = (f"Central bank: {bank.name if bank else d['bank']}. Language: {d['lang']}.\n"
                f"TEXT:\n{excerpt(text, str(d['lang']))}")
        try:
            scrub(SYSTEM + "\n" + user)
        except PromptRefused as exc:
            d["llm_attempts"] = 3
            d["blocker"] = f"PROMPT_REFUSED:{str(exc)[:80]}"
            continue
        calls += 1
        d["llm_attempts"] = int(d.get("llm_attempts") or 0) + 1
        try:
            reply = chat(SYSTEM, user, max_tokens=300, temperature=0.0,
                         timeout=max(10.0, min(90.0, deadline - time.time())))
        except Exception as exc:
            exhausted = type(exc).__name__
            break
        reading, why = parse_reading(getattr(reply, "text", ""), text)
        if reading is None:
            discards[why] = discards.get(why, 0) + 1
            continue
        model = f"{getattr(reply, 'provider', '')}:{getattr(reply, 'model', '')}"
        reading.update({"model": model, "scored_at": _now(),
                        "lookahead_guard": _guard(model, first_used)})
        d["llm"] = reading
        ok += 1
    _write_json(MODEL_FIRST_USED, first_used)
    return {"state": "RAN" if calls else ("DARK" if exhausted else "NOTHING_OWED"),
            "calls": calls, "scored": ok, "discards": discards, "chain": exhausted or "ok",
            "owed": max(0, len(todo) - ok)}


# ============================================================================ series + cells
SIGNALS_DONATED = ("tone_lex", "tone_llm_clean")
TRANSFORMS = (("level_z", 1.0), ("delta", 0.5))


def series_rows(docs: Iterable[dict[str, Any]], bank: str) -> list[dict[str, Any]]:
    """One row per available_time (readings sharing a stamp are averaged), PIT envelope first."""
    buckets: dict[str, dict[str, list[float]]] = {}
    meta: dict[str, dict[str, Any]] = {}
    for d in docs:
        if d.get("bank") != bank or not d.get("available_time") or not d.get("text_sha"):
            continue
        at = str(d["available_time"])
        b = buckets.setdefault(at, {k: [] for k in ("tone_lex", "tone_lex_en", "tone_llm",
                                                    "tone_llm_clean", "shift_llm")})
        meta.setdefault(at, {"published_time": d.get("published_time"),
                             "retrieval_time": d.get("retrieval_time"),
                             "source_id": d.get("source_id"), "n_docs": 0})
        meta[at]["n_docs"] += 1
        if d.get("tone_lex") is not None:
            (b["tone_lex"] if d.get("original") else b["tone_lex_en"]).append(float(d["tone_lex"]))
        llm = d.get("llm") or {}
        if llm.get("stance") is not None:
            b["tone_llm"].append(float(llm["stance"]))
            ev = str((llm.get("lookahead_guard") or {}).get("evidence_from") or "9999")
            if str(d.get("published_time") or "")[:10] >= ev[:10]:
                b["tone_llm_clean"].append(float(llm["stance"]))
            if llm.get("shift") in SHIFT_VALUE:
                b["shift_llm"].append(SHIFT_VALUE[llm["shift"]])
    rows = []
    for at in sorted(buckets):
        m = meta[at]
        row: dict[str, Any] = {"available_time": at, "published_time": m["published_time"],
                               "retrieval_time": m["retrieval_time"],
                               "source_id": f"cb_tone_{bank.lower()}",
                               "vintage_id": "v1", "n_docs": m["n_docs"]}
        for k, vals in buckets[at].items():
            row[k] = round(sum(vals) / len(vals), 4) if vals else ""
        rows.append(row)
    return rows


SERIES_COLUMNS = ("available_time", "published_time", "retrieval_time", "source_id",
                  "vintage_id", "n_docs", "tone_lex", "tone_lex_en", "tone_llm",
                  "tone_llm_clean", "shift_llm")


def write_series(docs: Sequence[dict[str, Any]]) -> dict[str, dict[str, int]]:
    import csv
    SERIES_DIR.mkdir(parents=True, exist_ok=True)
    counts: dict[str, dict[str, int]] = {}
    for bank in BANKS:
        rows = series_rows(docs, bank)
        path = SERIES_DIR / f"cb_tone_{bank.lower()}.csv"
        tmp = path.with_suffix(".csv.tmp")
        with tmp.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(SERIES_COLUMNS))
            w.writeheader()
            w.writerows(rows)
        os.replace(tmp, path)
        counts[bank] = {c: sum(1 for r in rows if r.get(c) != "") for c in SERIES_COLUMNS[6:]}
        counts[bank]["rows"] = len(rows)
    return counts


def cells(counts: dict[str, dict[str, int]], uni: dict[str, str] | None = None
          ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(donation rows, owed). A signal with fewer than MIN_OBSERVATIONS readings is OWED as
    NEEDS_DATA, never donated: the family would refuse it and the trial would be wasted."""
    try:
        import llm_lab
        uni = uni if uni is not None else llm_lab.universe()
        lane_ok = llm_lab._lane_ok
        ident = llm_lab.cell_identity
    except Exception:                                  # pragma: no cover
        return [], [{"blocker": "NEEDS_LAB", "why": "llm_lab unavailable"}]
    rows: list[dict[str, Any]] = []
    owed: list[dict[str, Any]] = []
    for bank in BANKS.values():
        source = f"cb_tone_{bank.key.lower()}"
        for sig in SIGNALS_DONATED:
            n = int(counts.get(bank.key, {}).get(sig, 0))
            if n < MIN_OBSERVATIONS:
                owed.append({"bank": bank.key, "signal": sig, "blocker": "NEEDS_DATA",
                             "have": n, "need": MIN_OBSERVATIONS})
                continue
            for sym, side in bank.symbols.items():
                if uni and sym not in uni:
                    owed.append({"bank": bank.key, "symbol": sym, "blocker": "NEEDS_INSTRUMENT"})
                    continue
                if not lane_ok(sym, "exogenous_conditioner"):
                    continue
                for transform, thr in TRANSFORMS:
                    params = {"source": source, "signal": sig, "transform": transform,
                              "threshold": thr, "side_when_high": side}
                    cell = {"family": "exogenous_conditioner", "params": params, "symbol": sym}
                    guard: dict[str, Any] = (
                        {"model": "none", "model_training_cutoff": "n/a",
                         "evidence_from": "1900-01-01",
                         "basis": "deterministic native-language lexicon: no model read history"}
                        if sig == "tone_lex" else
                        {"model": "per-document", "model_training_cutoff": "per-document",
                         "evidence_from": "per-document",
                         "basis": "tone_llm_clean holds only documents published on or after "
                                  "their scoring model's evidence_from; contaminated readings "
                                  "never enter this column"})
                    rows.append({
                        "kind": "hypothesis", "family": "exogenous_conditioner", "params": params,
                        "symbols": [sym], "symbol": sym,
                        "mechanism": (f"{bank.name} {'hawkish' if side > 0 else 'dovish'}-to-"
                                      f"{bank.currency} stance shift, read in "
                                      f"{bank.lang} from its own statements, precedes "
                                      f"{bank.currency} repricing in {sym}"),
                        "falsifier": (f"{sym} returns after an extreme {sig} ({transform}) are "
                                      f"no different from unconditioned returns once the "
                                      f"24h publication lag is applied"),
                        "title": f"llm_lab CB_TONE: {bank.key} {sig} {transform} on {sym}",
                        "lab": ROLE, "lab_name": "central_bank_tone",
                        "novelty_class": "GENUINELY_NOVEL", "cell_id": ident(cell),
                        "mechanism_class": "central_bank_communication",
                        "lineage": {"root": f"cb_tone:{bank.key}", "operator": "llm_lab"},
                        "url": f"llm_lab://{ROLE}/{bank.key}/{sig}",
                        "lookahead_guard": guard,
                        "copy_trade": False, "credibility_inherited": False,
                        "gauntlet_bypass": False})
    return rows, owed


def run(*, budget_s: float = 120.0, max_llm: int = 8, max_fetch: int | None = None,
        dry_run: bool = False, chat: Any = None, bis_zip: Path | None = None) -> dict[str, Any]:
    started = time.time()
    deadline = started + max(10.0, budget_s)
    max_fetch = int(max_fetch if max_fetch is not None else
                    os.environ.get("QUANT_CB_TONE_MAX_FETCH", "15"))
    docs = {str(d["id"]): d for d in _jsonl(DOCS) if d.get("id")}
    state = _read_json(SOURCE_STATE, {}) or {}
    out: dict[str, Any] = {"role": ROLE, "generated_at": _now(), "docs_before": len(docs)}
    if dry_run:
        out["sources"] = [{"sid": s.sid, "bank": b.key, "terms": s.terms} for b, s in sources()]
        return out
    out["bis"] = ingest_bis(docs, state, bis_zip)
    out["fetch"] = fetch_new(docs, state, deadline=deadline - 30, max_fetch=max_fetch)
    out["model"] = score_with_model(docs, max_calls=max_llm, deadline=deadline, chat=chat)
    rows = list(docs.values())
    _write_jsonl(DOCS, rows)
    _write_json(SOURCE_STATE, state)
    counts = write_series(rows)
    donate, owed = cells(counts)
    known = set((_read_json(STATE_DIR / "donated.json", []) or []))
    fresh = [r for r in donate if r["cell_id"] not in known]
    if fresh:
        import llm_lab
        import llm_lab_roles
        screened, out["style_screen"] = llm_lab.style_screened(fresh,
                                                               deadline=time.time() + 30.0)
        llm_lab_roles.record_evidence_start(screened, llm_lab.STATE_DIR / "evidence_start.json")
        target = llm_lab.donation_target(DONATE_DIR)
        target.mkdir(parents=True, exist_ok=True)
        stamp = _now().replace(":", "").replace("-", "")[:15]
        _write_json(target / f"discoveries_cbtone_{stamp}.json",
                    {"source": "llm_lab", "role": ROLE, "generated_at": _now(),
                     "rule": "THE LAB PROPOSES, THE DESK JUDGES", "discoveries": screened})
        _write_json(STATE_DIR / "donated.json", sorted(known | {r["cell_id"] for r in fresh}))
    blockers: dict[str, int] = {}
    for d in rows:
        if d.get("blocker"):
            k = str(d["blocker"]).split(":")[0]
            blockers[k] = blockers.get(k, 0) + 1
    out.update({"docs": len(rows), "series": counts,
                "cells_donated": len(screened) if fresh else 0,
                "cells_total": len(donate), "owed": owed, "doc_blockers": blockers,
                "seconds": round(time.time() - started, 1)})
    return out


def main(argv: Sequence[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--budget-s", type=float, default=120.0)
    ap.add_argument("--max-llm", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    print(json.dumps(run(budget_s=a.budget_s, max_llm=a.max_llm, dry_run=a.dry_run),
                     indent=1, ensure_ascii=False, default=str)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
