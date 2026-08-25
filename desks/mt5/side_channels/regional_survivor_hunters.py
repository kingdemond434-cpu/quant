"""Global regional survivor hunters -- the full world map, hourly (principal 2026-08-25/26).

Fourteen public copy/PAMM/leaderboard grounds across CN/JP/CIS/MENA/SEA/LATAM/EU/global,
config-driven and fail-soft: every source is enumerated with a ROTATING PAGE CURSOR persisted
across runs, so hourly sweeps accumulate unbounded breadth AND depth over time while staying
polite (a handful of requests per source per hour -- a banned scraper is a dead channel).
Every parsed account row is kind=track_record, so the forward-cohort time machine enrolls it
at first sight; unparseable pages degrade to raw_capture rows flagged needs_selector_work for
the wirer. FBS's published top-trades tape is captured as kind=trade_tape -- full open/close
timestamps, prices, SL/TP: direct Trade-DNA feedstock.

COVERAGE REGISTRY: every attempt updates data/intelligence/coverage_registry.json
(region x language x platform x evidence grade x last state). Empty regions (KR, TR) stay
OPEN cells, permanently searchable -- coverage is a ratchet, "done" is not a state.

Evidence grades: A = broker-native live account data; B = platform-verified aggregation;
C = self-reported/experimental. Grades flow into ranking, never into exclusion.
"""
from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
INTEL = BASE / "data" / "intelligence"
STATE = INTEL / "regional_hunters_state.json"
COVERAGE = INTEL / "coverage_registry.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
           "Accept-Language": "en-US,en;q=0.8,ru;q=0.6,zh;q=0.5,ja;q=0.5,ar;q=0.4,es;q=0.4"}
NUM = r"[-+]?\d[\d\s,]*\.?\d*"


def _read(p: Path, default):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def fetch(url: str, timeout: int = 25) -> str:
    time.sleep(1.1)
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.text


def row(source: str, kind: str, title: str, url: str = "", text: str = "",
        symbols: list | None = None, **extra) -> dict:
    return {"source": source, "kind": kind, "title": title[:300], "url": url,
            "text": text[:1200], "symbols": symbols or [],
            "found_at": datetime.now(tz=UTC).isoformat(timespec="seconds"), **extra}



#: CARD PARSERS -- source-specific extractors that turn a page into SURVIVOR RECORDS, not
#: corpus. MEASURED 2026-08-26: most "bot-walled" sources were never blocked at all -- they
#: return 200 with the numbers server-rendered, and the generic link-regex simply did not match
#: their markup (LiteFinance ships @handle + Profitability% + labelled stats inside
#: data-type="trader_card"). A raw_capture row is an admission the parser is wrong, not proof
#: the source is closed, and treating the two the same is how real ground gets written off.
def parse_litefinance(html: str, region: str) -> list[dict]:
    out = []
    for m in re.finditer(r'data-type="trader_card"(.{0,4000}?)(?=data-type="trader_card"|$)',
                         html, re.DOTALL):
        block = m.group(1)
        handle = re.search(r'class="title">\s*@?([A-Za-z0-9_.\- ]{2,40})', block)
        if not handle:
            continue
        vals = re.findall(r'class="data_value">\s*([-+]?[\d\s,.]+)\s*%?\s*<', block)
        labels = re.findall(r'class="data_label">\s*([^<]{3,60})<', block)
        stats = {}
        for lab, val in zip(labels, vals):
            key = lab.strip().lower()
            try:
                num = float(val.replace(",", "").replace(" ", "").replace("\u00a0", ""))
            except ValueError:
                continue
            if "profit" in key or "return" in key:
                stats["return_pct"] = num
            elif "drawdown" in key or "risk" in key:
                stats["drawdown_pct"] = num
            elif "day" in key or "age" in key:
                stats["age_days"] = num
            elif "copier" in key or "investor" in key or "follower" in key:
                stats["followers"] = num
            elif "equity" in key or "fund" in key:
                stats["equity"] = num
        name = handle.group(1).strip()
        out.append(row("litefinance", "track_record", f"@{name}",
                       f"https://my.litefinance.org/traders/{name}", region=region,
                       stats=stats, evidence_grade="A", lang="en+ru+vi",
                       mechanism_tags=[]))
    return out


CARD_PARSERS = {"litefinance": parse_litefinance}



BLOCKED = INTEL / "blocked_sources.json"


def _record_blocked(source: str, url: str, region: str, code: str, todo: str,
                    err: str = "") -> None:
    """A source that cannot yield RECORDS is a work queue entry, never a discovery.

    Kept OUT of latest_discoveries on purpose (principal 2026-08-26: "never js corpus brought
    to us, but full survivors mined"). The hypothesis converter exists to carry candidates; a
    saved page entering it is a page pretending to be a survivor. Recorded here instead, with a
    diagnosis the wirer can act on and a first_seen/last_seen so a source that has been blocked
    for weeks is visible as debt rather than as silence.
    """
    reg = _read(BLOCKED, {"note": "sources that returned no survivor records -- a WORK QUEUE, "
                                  "never a discovery. Diagnosis says which of three fixes "
                                  "applies: wrong selector / JS app needing its API / HTTP "
                                  "blocked (try the Contabo Windows IP).", "sources": {}})
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    e = reg["sources"].setdefault(source, {"first_seen": now, "region": region})
    e.update({"last_seen": now, "url": url, "diagnosis": code, "fix_hint": todo,
              "error": err, "attempts": int(e.get("attempts", 0)) + 1})
    BLOCKED.write_text(json.dumps(reg, indent=1), "utf-8")


def try_json_routes(base_url: str, html: str) -> list[dict]:
    """Resolve a client-rendered page to STRUCTURED RECORDS via the routes it actually uses.

    A JS app is not a closed source -- it is a source whose data arrives separately. Before any
    page is written off, try the standard places that data lives: the Next.js data route (build
    id is in the HTML), an embedded __NEXT_DATA__/__NUXT__ payload, and the conventional API
    paths. Anything that yields a list of dicts with numeric fields is real data.
    """
    import urllib.parse
    cands: list[str] = []
    bid = re.search(r'"buildId":"([^"]+)"', html)
    if bid:
        path = urllib.parse.urlparse(base_url).path.strip("/") or "index"
        cands.append(f"{base_url.rstrip('/')}/_next/data/{bid.group(1)}/{path}.json")
    for guess in ("/api/providers", "/api/strategies", "/api/traders", "/api/rating",
                  "/api/v1/strategies", "/api/v1/traders"):
        cands.append(base_url.rstrip("/") + guess)
    for url in cands[:6]:
        try:
            txt = fetch(url, timeout=15)
            data = json.loads(txt)
        except Exception:                                                # noqa: BLE001
            continue
        found = _first_record_list(data)
        if found:
            return found
    return []


def _first_record_list(obj, depth: int = 0):
    """Deepest-first search for a list of dicts carrying numbers -- i.e. actual records."""
    if depth > 6:
        return []
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        if any(isinstance(v, (int, float)) for v in obj[0].values()):
            return obj
    if isinstance(obj, dict):
        for v in obj.values():
            got = _first_record_list(v, depth + 1)
            if got:
                return got
    elif isinstance(obj, list):
        for v in obj[:20]:
            got = _first_record_list(v, depth + 1)
            if got:
                return got
    return []


def records_to_rows(source: str, recs: list[dict], region: str, grade: str,
                    lang: str) -> list[dict]:
    """Map arbitrary API records onto survivor rows, in any language, numbers only."""
    from lang_intel import detect_mechanisms                            # noqa: PLC0415
    out = []
    for r in recs[:60]:
        name = next((str(r[k]) for k in ("name", "title", "nickname", "login", "alias",
                                         "strategyName", "trader") if r.get(k)), None)
        if not name:
            continue
        stats = {}
        for k, v in r.items():
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                continue
            kl = k.lower()
            if "return" in kl or "profit" in kl or "gain" in kl or "yield" in kl:
                stats["return_pct"] = float(v)
            elif "drawdown" in kl or kl.endswith("dd"):
                stats["drawdown_pct"] = float(v)
            elif "age" in kl or "days" in kl or "weeks" in kl:
                stats["age_days"] = float(v)
            elif "copier" in kl or "follower" in kl or "investor" in kl:
                stats["followers"] = float(v)
            elif "trade" in kl or "position" in kl or "deal" in kl:
                stats["trades"] = float(v)
        if not stats:
            continue
        out.append(row(source, "track_record", name, str(r.get("url", "")), region=region,
                       stats=stats, evidence_grade=grade, lang=lang,
                       mechanism_tags=detect_mechanisms(json.dumps(r, default=str))))
    return out

def diagnose_page(html: str, status: int | None = None) -> tuple[str, str]:
    """Classify WHY a page yielded no records. (code, what-to-do)

    "needs_selector_work" on its own is a shrug: it says the parser failed without saying which
    of three completely different fixes applies. MEASURED 2026-08-26 across the regional family:
    LiteFinance was server-rendered and merely mis-parsed (0 -> 15 real records once the card
    selector was written), Duplitrade's only percentage was a CSS gradient in a React bundle,
    and Collective2 answered 403. Three sources, three fixes, one useless label -- so the label
    is replaced by a diagnosis the wirer can act on without re-deriving it.
    """
    if status and status >= 400:
        return ("HTTP_BLOCKED",
                f"HTTP {status} -- try the Contabo Windows IP (this box is a datacenter range "
                f"many venues refuse), a regional mirror, or the archive")
    low = html.lower()
    js_markers = ("__next_data__", "data-reactroot", "ng-version", "data-beasties",
                  "window.__nuxt", "muirtl", "_app-", "runtime.")
    has_numbers = bool(re.search(r">\s*[-+]?\d[\d,.]*\s*%\s*<", html))
    if has_numbers:
        return ("SERVER_RENDERED_WRONG_SELECTOR",
                "the numbers ARE in the HTML -- write a card parser for this markup "
                "(see parse_litefinance: 0 -> 15 records with the right selector)")
    if any(m in low for m in js_markers):
        return ("JS_APP_NEEDS_API",
                "client-rendered app: the page ships no data, so find the JSON endpoint its "
                "own XHR calls and read that instead of the HTML")
    return ("UNKNOWN_SHAPE", "page returned 200 with neither rendered numbers nor JS markers")

def generic_cards(source: str, html: str, base_url: str, link_pat: str,
                  region: str) -> list[dict]:
    """Shared extractor: account/strategy links + nearby stats, LABELS READ IN ANY LANGUAGE
    (lang_intel: 収益率, просадка, 最大回撤, أقصى تراجع and drawdown are one concept)."""
    from lang_intel import STAT_CONCEPTS, detect_mechanisms, stat_near  # noqa: PLC0415
    out = []
    for m in re.finditer(link_pat, html):
        href, label = m.group(1), (m.group(2) if m.lastindex >= 2 else m.group(1)).strip()
        ctx = html[m.start():m.start() + 1200]
        pcts = [p.replace(" ", "").replace(",", "") for p in
                re.findall(r"(" + NUM + r")\s*%", ctx)][:6]
        stats = {c: stat_near(ctx, c) for c in STAT_CONCEPTS}
        url = href if href.startswith("http") else base_url.rstrip("/") + href
        out.append(row(source, "track_record", label or href, url,
                       region=region, nearby_pcts=pcts,
                       stats={k: v for k, v in stats.items() if v is not None},
                       mechanism_tags=detect_mechanisms(ctx)))
    return out


#: name -> (region, lang, evidence_grade, page_urls_fn(page:int), link_regex, base_url, npages)
SOURCES = {
    "equiti_copy": ("MENA/global", "en+ar", "A",
                    lambda p: f"https://copy-ratings.equiti.com/?page={p}",
                    r'href="(/(?:provider|strategy)[^"]*)"[^>]*>([^<]{3,80})<',
                    "https://copy-ratings.equiti.com", 5),
    "trading_latam": ("LATAM", "es", "B",
                      lambda p: "https://trading-latam.com/ranking-toptraders/",
                      r'href="(https://trading-latam\.com/[a-z0-9\-]{4,60}/)"[^>]*>([^<]{3,60})<',
                      "https://trading-latam.com", 1),
    "litefinance": ("CIS/SEA", "en+ru+vi", "A",
                    lambda p: f"https://my.litefinance.org/traders?page={p}",
                    r'href="(/traders/[^"]+)"[^>]*>([^<]{3,60})<',
                    "https://my.litefinance.org", 5),
    "duplitrade": ("EU/global", "en", "A",
                   lambda p: "https://duplitrade.com/strategy-providers",
                   r'href="(/strategy-provider[s]?/[^"]+)"[^>]*>([^<]{3,60})<',
                   "https://duplitrade.com", 1),
    "octa_masters": ("SEA", "en+id+vi", "A",
                     lambda p: f"https://my.octabroker.com/copy-trading/rating/?page={p}",
                     r'href="([^"]*master[^"]*)"[^>]*>([^<]{3,60})<',
                     "https://my.octabroker.com", 3),
    "share4you": ("CIS/Asia", "en+ru", "B",
                  lambda p: f"https://www.share4you.com/en/leaders?page={p}",
                  r'href="(/en/leaders/[^"]+)"[^>]*>([^<]{3,60})<',
                  "https://www.share4you.com", 4),
    "instaforex_copy": ("CIS", "en+ru", "A",
                        lambda p: f"https://www.instaforex.com/forexcopy_monitoring?page={p}",
                        r'href="([^"]*forexcopy[^"]*system[^"]*)"[^>]*>([^<]{3,60})<',
                        "https://www.instaforex.com", 3),
    "roboforex_copyfx": ("CIS/global", "en+ru", "A",
                         lambda p: f"https://copy.roboforex.pro/ratings/traders-all/?page={p}",
                         r'href="(/ratings/trader/[^"]+)"[^>]*>([^<]{3,60})<',
                         "https://copy.roboforex.pro", 4),
    "hfm_pamm": ("MENA/Africa", "en+ar", "A",
                 lambda p: f"https://pamm.hfm.com/int/en/performance?page={p}",
                 r'href="([^"]*/(?:pamm|manager|strategy)/[^"]+)"[^>]*>([^<]{3,60})<',
                 "https://pamm.hfm.com", 3),
    "amarkets": ("CIS", "en+ru", "A",
                 lambda p: f"https://www.amarkets.com/copy-trading-rating/?page={p}",
                 r'href="([^"]*strategy\d+[^"]*)"[^>]*>?([^<]{0,60})',
                 "https://www.amarkets.com", 3),
    "followme_cn": ("China", "zh", "B",
                    lambda p: f"https://cn.followme.com/trade/rank?page={p}",
                    r'href="(/(?:trader|user|account)/[^"]+)"[^>]*>([^<]{2,50})<',
                    "https://cn.followme.com", 3),
    "minfx_jp": ("Japan", "ja", "A",
                 lambda p: "https://min-fx.jp/systre/strategy/",
                 r'href="([^"]*strategy[^"]*)"[^>]*>([^<]{3,60})<',
                 "https://min-fx.jp", 1),
    "mylivefx_br": ("Brazil", "pt", "C",
                    lambda p: "https://mylivefx.com/",
                    r'href="(/[a-z0-9\-]*trader[^"]*)"[^>]*>([^<]{3,60})<',
                    "https://mylivefx.com", 1),
    "readitrades_africa": ("Africa", "en", "C",
                           lambda p: "https://www.ready-trade.com/",
                           r'href="(/[a-z0-9\-]*trader[^"]*)"[^>]*>([^<]{3,60})<',
                           "https://www.ready-trade.com", 1),
}

FBS_TRADE_RE = re.compile(
    r"(XAUUSD|XAGUSD|[A-Z]{6}|US\d{2,3}|USOIL)\D{0,60}(BUY|SELL)\D{0,400}?"
    r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?)", re.IGNORECASE | re.DOTALL)


def mine_fbs_tape() -> list[dict]:
    """FBS publishes top closed trades with full geometry -- direct Trade-DNA feedstock."""
    html = fetch("https://fbs.com/top-trades")
    out = []
    for m in FBS_TRADE_RE.finditer(html):
        ctx = html[m.start():m.start() + 800]
        nums = re.findall(r"\b\d+\.\d{2,5}\b", ctx)[:6]
        out.append(row("fbs_tape", "trade_tape", f"{m.group(1)} {m.group(2)}",
                       "https://fbs.com/top-trades", symbols=[m.group(1).upper()],
                       side=m.group(2).upper(), ts=m.group(3), prices_seen=nums))
    if not out:
        out.append(row("fbs_tape", "raw_capture", "top-trades page shape drifted",
                       "https://fbs.com/top-trades", html[:1200],
                       needs_selector_work=True))
    return out[:80]


def update_coverage(name: str, region: str, lang: str, grade: str, state: str,
                    rows_n: int) -> None:
    cov = _read(COVERAGE, {"note": "region x language x platform coverage RATCHET; empty "
                                   "regions are OPEN cells, never 'done'",
                           "open_cells": {"KR": "no native MT5 survivor pool found yet -- "
                                                "canary searches standing",
                                          "TR": "same; OPEN"},
                           "platforms": {}})
    ent = cov["platforms"].setdefault(name, {"region": region, "lang": lang,
                                             "evidence_grade": grade,
                                             "best_rows": 0, "attempts": 0})
    ent["attempts"] += 1
    ent["last_state"] = state
    ent["last_attempt"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
    ent["best_rows"] = max(ent["best_rows"], rows_n)     # coverage ratchets, never falls
    COVERAGE.write_text(json.dumps(cov, indent=1), "utf-8")


def run_and_save() -> dict:
    now = datetime.now(tz=UTC)
    st = _read(STATE, {})
    results = {}
    total_real = 0
    for name, (region, lang, grade, url_fn, link_pat, base_url, npages) in SOURCES.items():
        page = (int(st.get(name, 0)) % npages) + 1          # rotating cursor: depth over hours
        st[name] = page
        rows_: list[dict] = []
        state = "ok"
        try:
            html = fetch(url_fn(page))
            parser = CARD_PARSERS.get(name)
            rows_ = (parser(html, region) if parser
                     else generic_cards(name, html, base_url, link_pat, region))
            for r_ in rows_:
                r_["evidence_grade"] = grade
                r_["lang"] = lang
            if not rows_:
                # LAST RESORT BEFORE GIVING UP: resolve the client-rendered routes.
                recs = try_json_routes(base_url, html)
                if recs:
                    rows_ = records_to_rows(name, recs, region, grade, lang)
            if not rows_:
                # SURVIVORS ONLY (principal 2026-08-26): a source that cannot yield RECORDS
                # yields NOTHING to the discovery pipeline. Corpus rows were polluting the
                # hypothesis converter with pages instead of survivors -- the pipeline exists
                # to carry candidates, not HTML. The blocker is recorded in its own registry
                # with a diagnosis, which is a work queue, not a discovery.
                code, todo = diagnose_page(html)
                state = code.lower()
                _record_blocked(name, url_fn(page), region, code, todo)
                rows_ = []
        except Exception as exc:                                         # noqa: BLE001
            status = getattr(getattr(exc, "response", None), "status_code", None)
            code, todo = diagnose_page("", status)
            state = f"error:{type(exc).__name__}"
            _record_blocked(name, url_fn(page), region,
                            code if status else "FETCH_ERROR", todo, str(exc)[:160])
            rows_ = []
        real = [r_ for r_ in rows_ if not r_.get("needs_selector_work")]
        total_real += len(real)
        d = INTEL / name
        d.mkdir(parents=True, exist_ok=True)
        (d / f"discoveries_{now:%Y%m%d_%H%M}.json").write_text(
            json.dumps(rows_, indent=1, default=str), "utf-8")
        results[name] = {"discoveries": rows_, "count": len(rows_)}
        update_coverage(name, region, lang, grade, state, len(real))
        print(f"  {name} p{page}: {len(real)} real / {len(rows_)} rows [{state}]")
    # FBS tape rides along
    try:
        tape = mine_fbs_tape()
        d = INTEL / "fbs_tape"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"discoveries_{now:%Y%m%d_%H%M}.json").write_text(
            json.dumps(tape, indent=1, default=str), "utf-8")
        results["fbs_tape"] = {"discoveries": tape, "count": len(tape)}
        print(f"  fbs_tape: {len(tape)} rows")
    except Exception as exc:                                             # noqa: BLE001
        print(f"  fbs_tape: {exc}")
    STATE.write_text(json.dumps(st, indent=0), "utf-8")
    latest_p = INTEL / "latest_discoveries.json"
    latest = _read(latest_p, {})
    latest.update(results)
    latest_p.write_text(json.dumps(latest, indent=1, default=str), "utf-8")
    print(f"regional hunters: {total_real} real account rows across {len(SOURCES)} grounds")
    return results


if __name__ == "__main__":
    run_and_save()
