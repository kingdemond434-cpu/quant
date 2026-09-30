"""Global regional survivor hunters -- the full world map, hourly (principal 2026-08-25/26).

Fourteen public copy/PAMM/leaderboard grounds across CN/JP/CIS/MENA/SEA/LATAM/EU/global,
config-driven and fail-soft: every source is enumerated with a ROTATING PAGE CURSOR persisted
across runs, so hourly sweeps accumulate unbounded breadth AND depth over time while staying
polite (per-HOST spacing through `libs.data.polite_fetch` -- a banned scraper is a dead channel).
Every parsed account row is kind=track_record, so the forward-cohort time machine enrolls it
at first sight. FBS's published top-trades tape is captured as kind=trade_tape -- full
open/close timestamps, prices, SL/TP: direct Trade-DNA feedstock.

COVERAGE REGISTRY: every attempt updates data/intelligence/coverage_registry.json
(region x language x platform x evidence grade x last state, plus attempts / successes / rows /
last error). Empty regions (KR, TR) stay OPEN cells, permanently searchable -- coverage is a
ratchet, "done" is not a state.

THE LOSS REASONS, FIXED AT THE ROOT (2026-09-30). Measured in the registry: 10 of 14 platforms
had never yielded a row after ~221 attempts each, lost to five reasons. Each now has its fix in
the RESOLUTION CHAIN `mine_source` walks before it gives up on a page:

* `js_app_needs_api` (equiti, duplitrade): the old fallback GUESSED six `/api/...` paths. Now
  the page's own data is found where a browser finds it -- embedded state (`__NEXT_DATA__`,
  `__INITIAL_STATE__`, `application/json` script blocks), then the Next.js data route, then the
  API paths the page's OWN script bundles reference (`discover_endpoints`), ranked by how much
  they look like a rating list, then sitemap/RSS. No headless browser needed.
* `unknown_shape` / `server_rendered_wrong_selector` (octa, roboforex, mylivefx): numbers
  in a `<table>` or in repeated cards are read by the generic `parse_tables` /
  `parse_repeated_cards` extractors (labels in any language via lang_intel) before the page is
  written off.
* `error:HTTPError` 404 (share4you, minfx_jp): the listing MOVED. `resolve_listing` walks the
  source's alternates and the site root's own links for a rating/leader/strategy page and
  REMEMBERS the one that yielded, so the next run starts there.
* `error:HTTPError` 403 (hfm_pamm, followme_cn): alternates on sibling hosts, a Referer from the
  site root and a JSON Accept for API routes; a 429/5xx is retried with backoff.
* `error:SSLError` (readitrades_africa): certifi-backed trust (`polite_fetch.ssl_context`), then
  the bare-host variant. Verification is never turned off.

Evidence grades: A = broker-native live account data; B = platform-verified aggregation;
C = self-reported/experimental. Grades flow into ranking, never into exclusion.
"""
from __future__ import annotations

import contextlib
import html as _html
import json
import os
import re
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

BASE = Path(__file__).resolve().parent.parent
_REPO = BASE.parent.parent
for _p in (str(Path(__file__).resolve().parent), str(BASE), str(_REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import polite_fetch as pf  # noqa: E402

INTEL = BASE / "data" / "intelligence"
STATE = INTEL / "regional_hunters_state.json"
COVERAGE = INTEL / "coverage_registry.json"
#: One line per run: the leg's fetches, successes, rows and seconds -- the fetches/second series
#: `research/alt_data_yield.py` publishes. Append-only and tiny. OUTSIDE data/intelligence/ on
#: purpose: the compiler reads everything under that root as donations.
RUNS = BASE / "data" / "alt_fetch_runs.jsonl"
YIELD_OUT = BASE / "reports" / "ALT_DATA_YIELD.json"
LEG = "regional_survivor_hunters"
HEADERS = {"User-Agent": pf.BROWSER_UA,
           "Accept-Language": "en-US,en;q=0.8,ru;q=0.6,zh;q=0.5,ja;q=0.5,ar;q=0.4,es;q=0.4"}
NUM = r"[-+]?\d[\d\s,]*\.?\d*"
#: Sources worked at once. Politeness is per HOST (`polite_fetch.GATE`), so this buys coverage
#: per second without raising the rate any one venue sees.
WORKERS = 8
#: Hard per-request timeout; one venue can never stall the run.
REQUEST_TIMEOUT_S = 25.0
#: Whole-run deadline. No fetch starts after it and no in-flight fetch outlives it.
RUN_BUDGET_S = 900.0
#: Pages per source per run. The cursor still rotates, so depth accumulates across hours; each
#: run now takes up to this many pages instead of exactly one.
PAGES_PER_RUN = 3
#: Script bundles / discovered endpoints tried per page. A budget, reported, never silent.
MAX_BUNDLES = 6
MAX_ENDPOINTS = 10


def _read(p: Path, default):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


class FetchError(Exception):
    """A fetch that returned no page. `status` is the HTTP code when there was one;
    `response.status_code` mirrors it for the `diagnose_page` call sites."""

    def __init__(self, url: str, status: int | None, error: str) -> None:
        super().__init__(f"{error} for url: {url}")
        self.url, self.status, self.error = url, status, error
        self.response = type("R", (), {"status_code": status})()


_DEADLINE: dict[str, float | None] = {"at": None}


def fetch(url: str, timeout: float = REQUEST_TIMEOUT_S, *, referer: str = "",
          accept_json: bool = False) -> str:
    """One polite GET: per-host spacing, bounded retries on 429/5xx/transport, certifi-backed
    TLS, charset-aware decoding. Raises FetchError on failure."""
    hdr = dict(HEADERS)
    if referer:
        hdr["Referer"] = referer
    if accept_json:
        hdr["Accept"] = "application/json, text/plain, */*"
        hdr["X-Requested-With"] = "XMLHttpRequest"
    r = pf.get(url, headers=hdr, timeout=timeout, retries=2, leg=LEG, deadline=_DEADLINE["at"])
    if not r.ok:
        raise FetchError(url, r.status, r.error or f"HTTP {r.status}")
    return r.text


_WRITE_LOCK = threading.Lock()


def _atomic_write(path: Path, text: str) -> None:
    """Write-then-replace, Windows-safe: a reader never sees half a file, and a destination
    another process holds open (or marked read-only -- WinError 5) is retried, not raised."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(text, "utf-8")
    for i in range(6):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            with contextlib.suppress(OSError):
                os.chmod(path, 0o666)
            time.sleep(0.2 * (i + 1))
    try:
        path.write_text(text, "utf-8")
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()


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
        for lab, val in zip(labels, vals, strict=False):
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
    to us, but full survivors mined"). Recorded here instead, with a diagnosis the wirer can act
    on and a first_seen/last_seen so a source blocked for weeks is visible as debt.
    """
    with _WRITE_LOCK:
        reg = _read(BLOCKED, {"note": "sources that returned no survivor records -- a WORK "
                                      "QUEUE, never a discovery. Diagnosis says which fix "
                                      "applies: wrong selector / JS app needing its API / HTTP "
                                      "blocked / TLS.", "sources": {}})
        now = datetime.now(tz=UTC).isoformat(timespec="seconds")
        e = reg.setdefault("sources", {}).setdefault(source, {"first_seen": now,
                                                              "region": region})
        e.update({"last_seen": now, "url": url, "diagnosis": code, "fix_hint": todo,
                  "error": err, "attempts": int(e.get("attempts", 0)) + 1})
        _atomic_write(BLOCKED, json.dumps(reg, indent=1, ensure_ascii=False))


def _clear_blocked(source: str) -> None:
    """A source that yielded is no longer debt: move it to `resolved` with when it cleared."""
    with _WRITE_LOCK:
        reg = _read(BLOCKED, None)
        if not isinstance(reg, dict) or source not in (reg.get("sources") or {}):
            return
        e = reg["sources"].pop(source)
        e["resolved_at"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
        reg.setdefault("resolved", {})[source] = e
        _atomic_write(BLOCKED, json.dumps(reg, indent=1, ensure_ascii=False))


# ----------------------------------------------------------------------- the JS-app route
_EMBED_JSON_RES = (
    re.compile(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S | re.I),
    re.compile(r'<script[^>]+type="application/(?:ld\+)?json"[^>]*>(.*?)</script>', re.S | re.I),
)
_STATE_ASSIGN = re.compile(
    r"window\.(?:__INITIAL_STATE__|__PRELOADED_STATE__|__APOLLO_STATE__|__DATA__|__STATE__|"
    r"initialState)\s*=\s*", re.I)
#: Words that make an endpoint look like a rating/leader list. Rank, never filter.
_LIST_WORDS = ("trader", "leader", "strateg", "provider", "master", "rating", "ranking", "rank",
               "pamm", "copy", "signal", "manager", "account", "top", "systre", "portfolio",
               "list", "search")


def _balanced_json(text: str, start: int) -> Any:
    """Parse the JSON object/array that starts at `text[start]`, or None."""
    if start >= len(text) or text[start] not in "{[":
        return None
    with contextlib.suppress(ValueError):
        obj, _end = json.JSONDecoder().raw_decode(text[start:])
        return obj
    return None


def embedded_records(html: str) -> list[dict]:
    """Records a client-rendered page SHIPS INSIDE ITSELF -- the hydration payload. This is
    where most Next/React/Vue listings keep their first page, so no second request is needed."""
    for rx in _EMBED_JSON_RES:
        for m in rx.finditer(html):
            with contextlib.suppress(ValueError):
                found = _first_record_list(json.loads(_html.unescape(m.group(1).strip())))
                if found:
                    return found
    for m in _STATE_ASSIGN.finditer(html):
        found = _first_record_list(_balanced_json(html, m.end()))
        if found:
            return found
    return []


_BUNDLE_RE = re.compile(r'<script[^>]+src="([^"]+\.js[^"]*)"', re.I)
_ENDPOINT_IN_JS = re.compile(
    r"""["'`]((?:https?://[a-z0-9.\-]+)?/(?:api|v\d|rest|graphql|data|ajax|json)[/?][^"'`\s<>{}$]{0,160})["'`]""",
    re.I)


def _score_endpoint(url: str) -> int:
    low = url.lower()
    return sum(3 for w in _LIST_WORDS if w in low) - low.count("login") * 5 - \
        low.count("auth") * 5 - low.count("logout") * 5


def discover_endpoints(base_url: str, html: str, *, max_bundles: int = MAX_BUNDLES) -> list[str]:
    """The API routes this page's OWN code calls, read from the page and its script bundles.

    A JS app is not a closed source -- its data arrives by XHR from a route its bundle names.
    Reading the bundle for `/api/...`-shaped strings finds that route without a browser.
    Same-site bundles only; ranked by how much the route looks like a rating list.
    """
    host = urlparse(base_url).netloc
    site = ".".join(host.split(".")[-2:])
    texts = [html]
    bundles = []
    for src in _BUNDLE_RE.findall(html):
        u = urljoin(base_url, _html.unescape(src))
        if site and site in urlparse(u).netloc:
            bundles.append(u)
    for u in bundles[:max_bundles]:
        with contextlib.suppress(Exception):
            texts.append(fetch(u, referer=base_url))
    found: dict[str, int] = {}
    for t in texts:
        for m in _ENDPOINT_IN_JS.finditer(t):
            path = m.group(1)
            u = urljoin(base_url, path)
            if site and site not in urlparse(u).netloc:
                continue
            if re.search(r"\.(?:js|css|png|jpg|svg|woff2?)(?:\?|$)", u, re.I):
                continue
            found[u] = max(found.get(u, -99), _score_endpoint(u))
    return [u for u, _s in sorted(found.items(), key=lambda kv: -kv[1])]


def try_json_routes(base_url: str, html: str) -> list[dict]:
    """Resolve a client-rendered page to STRUCTURED RECORDS via the routes it actually uses.

    Order: the hydration payload in the page itself, the Next.js data route (build id in the
    HTML), the endpoints its own bundles name, then the conventional API paths as a last guess.
    Anything that yields a list of dicts with numeric fields is real data.
    """
    got = embedded_records(html)
    if got:
        return got
    cands: list[str] = []
    bid = re.search(r'"buildId":"([^"]+)"', html)
    if bid:
        path = urlparse(base_url).path.strip("/") or "index"
        root = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"
        cands.append(f"{root}/_next/data/{bid.group(1)}/{path}.json")
    cands.extend(discover_endpoints(base_url, html))
    for guess in ("/api/providers", "/api/strategies", "/api/traders", "/api/rating",
                  "/api/v1/strategies", "/api/v1/traders"):
        cands.append(base_url.rstrip("/") + guess)
    seen: set[str] = set()
    tried = 0
    for url in cands:
        if url in seen or tried >= MAX_ENDPOINTS:
            continue
        seen.add(url)
        tried += 1
        try:
            data = json.loads(fetch(url, timeout=15, referer=base_url, accept_json=True))
        except Exception:
            continue
        found = _first_record_list(data)
        if found:
            return found
    return []


def _first_record_list(obj, depth: int = 0):
    """Deepest-first search for a list of dicts carrying numbers -- i.e. actual records."""
    if depth > 8:
        return []
    if isinstance(obj, list) and obj and isinstance(obj[0], dict) and any(
            isinstance(v, (int, float)) and not isinstance(v, bool) for v in obj[0].values()):
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


_NAME_KEYS = ("name", "title", "nickname", "nickName", "nick", "login", "alias", "strategyName",
              "strategy_name", "displayName", "display_name", "userName", "username",
              "accountName", "masterName", "providerName", "trader", "manager")


def _record_name(r: dict) -> str | None:
    for k in _NAME_KEYS:
        v = r.get(k)
        if isinstance(v, (str, int)) and str(v).strip():
            return str(v).strip()
    for k, v in r.items():
        if isinstance(v, str) and v.strip() and ("name" in k.lower() or "nick" in k.lower()):
            return v.strip()
    return None


def records_to_rows(source: str, recs: list[dict], region: str, grade: str,
                    lang: str) -> list[dict]:
    """Map arbitrary API records onto survivor rows, in any language, numbers only."""
    from lang_intel import detect_mechanisms
    out = []
    for r in recs[:200]:
        if not isinstance(r, dict):
            continue
        name = _record_name(r)
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
            elif "copier" in kl or "follower" in kl or "investor" in kl or "subscriber" in kl:
                stats["followers"] = float(v)
            elif "trade" in kl or "position" in kl or "deal" in kl:
                stats["trades"] = float(v)
            elif "equity" in kl or "balance" in kl or "fund" in kl or "aum" in kl:
                stats["equity"] = float(v)
        if not stats:
            continue
        out.append(row(source, "track_record", name, str(r.get("url", "") or ""),
                       region=region, stats=stats, evidence_grade=grade, lang=lang,
                       mechanism_tags=detect_mechanisms(json.dumps(r, default=str,
                                                                   ensure_ascii=False))))
    return out


# ----------------------------------------------------------------------- generic HTML shapes
_TAG = re.compile(r"<[^>]+>")
_HREF = re.compile(r"""href=["']([^"']+)["']""")


def _cell_text(fragment: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(_TAG.sub(" ", fragment))).strip()


_MINUS, _NBSP = "\u2212", "\u00a0"
_NUM_RE = re.compile("[-+" + _MINUS + r"]?\d[\d\s," + _NBSP + r"]*\.?\d*")
_PCT_RE = re.compile("([-+" + _MINUS + r"]?\d[\d.,]*)\s*%")


def _is_num(text: str) -> bool:
    """A cell that IS a number (a stat), as opposed to a name that contains a digit."""
    t = text.strip().replace(_MINUS, "-").replace(_NBSP, " ")
    return bool(re.fullmatch(r"[-+$€£]?\s*[-+]?\d[\d\s,.]*\s*(?:%|pips?|[kKmM])?", t))


def _num(text: str) -> float | None:
    m = _NUM_RE.search(text)
    if not m:
        return None
    try:
        return float(m.group(0).replace(_MINUS, "-").replace(",", "").replace(" ", "")
                     .replace(_NBSP, ""))
    except ValueError:
        return None


def _stat_key(label: str) -> str | None:
    """A column/label in ANY language -> the stat it measures (lang_intel's lexicon)."""
    from lang_intel import STAT_CONCEPTS, label_regex
    names = {"return": "return_pct", "drawdown": "drawdown_pct", "win_rate": "win_rate",
             "trades": "trades", "followers": "followers", "age": "age_days"}
    for c in STAT_CONCEPTS:
        if label_regex(c).search(label):
            return names.get(c, c)
    return None


def parse_tables(source: str, html: str, base_url: str, region: str) -> list[dict]:
    """Rating tables: one row per account, a name cell and numeric cells under labelled
    headers. Header labels are read in any language."""
    out: list[dict] = []
    for tbl in re.findall(r"<table\b.*?</table>", html, re.S | re.I):
        rows_ = re.findall(r"<tr\b.*?</tr>", tbl, re.S | re.I)
        if len(rows_) < 2:
            continue
        head = [_cell_text(c) for c in re.findall(r"<t[hd]\b[^>]*>(.*?)</t[hd]>", rows_[0],
                                                   re.S | re.I)]
        keys = [_stat_key(h) for h in head]
        for tr in rows_[1:]:
            cells = re.findall(r"<td\b[^>]*>(.*?)</td>", tr, re.S | re.I)
            if len(cells) < 2:
                continue
            texts = [_cell_text(c) for c in cells]
            name_i = next((i for i, t in enumerate(texts)
                           if t and not _is_num(t) and 2 <= len(t) <= 80), None)
            if name_i is None:
                continue
            stats: dict[str, float] = {}
            pcts = []
            for i, t in enumerate(texts):
                if i == name_i:
                    continue
                v = _num(t)
                if v is None:
                    continue
                if "%" in t:
                    pcts.append(v)
                k = keys[i] if i < len(keys) else None
                if k and k not in stats:
                    stats[k] = v
            if not stats and not pcts:
                continue
            if not stats and pcts:
                stats["return_pct"] = pcts[0]
            href = _HREF.search(cells[name_i])
            url = urljoin(base_url, _html.unescape(href.group(1))) if href else ""
            out.append(row(source, "track_record", texts[name_i], url, region=region,
                           stats=stats, nearby_pcts=pcts[:6], parser="table"))
    return out


def parse_repeated_cards(source: str, html: str, base_url: str, region: str,
                         min_cards: int = 3) -> list[dict]:
    """Server-rendered CARDS: the class that repeats most often with a percentage inside is the
    card; each card's first non-numeric text is the name, its labelled numbers the stats. This
    is `parse_litefinance` generalised -- the shape that took LiteFinance from 0 to 15 records."""
    from lang_intel import STAT_CONCEPTS, detect_mechanisms, stat_near
    names = {"return": "return_pct", "drawdown": "drawdown_pct", "win_rate": "win_rate",
             "trades": "trades", "followers": "followers", "age": "age_days"}
    classes: dict[str, int] = {}
    for c in re.findall(r'class="([^"]{3,80})"', html):
        classes[c] = classes.get(c, 0) + 1
    best: list[dict] = []
    for cls, n in sorted(classes.items(), key=lambda kv: -kv[1])[:40]:
        if n < min_cards or n > 400:
            continue
        marker = f'class="{cls}"'
        parts = html.split(marker)[1:]
        cards: list[dict] = []
        for part in parts:
            block = part[:4000]
            text = _cell_text("<x " + block)
            if "%" not in text:
                continue
            # the card's own text nodes, in order: the first that is neither a number nor a
            # stat label (in any language) is the account's name
            tokens = [t for t in (_cell_text(x) for x in re.split(r"<[^>]*>", "<x " + block))
                      if t]
            name = next((t for t in tokens if not _is_num(t) and 2 <= len(t) <= 60
                         and _stat_key(t) is None), None)
            if not name:
                continue
            pcts = [p for p in (_num(x) for x in _PCT_RE.findall(text))
                    if p is not None][:6]
            stats = {names.get(c, c): v for c in STAT_CONCEPTS
                     if (v := stat_near(text, c)) is not None}
            if not stats and pcts:
                stats["return_pct"] = pcts[0]
            href = _HREF.search(block)
            url = urljoin(base_url, _html.unescape(href.group(1))) if href else ""
            cards.append(row(source, "track_record", name, url, region=region, stats=stats,
                             nearby_pcts=pcts, parser=f"cards:{cls[:40]}",
                             mechanism_tags=detect_mechanisms(text)))
        if len(cards) >= min_cards and len(cards) > len(best):
            best = cards
    return best


def diagnose_page(html: str, status: int | None = None) -> tuple[str, str]:
    """Classify WHY a page yielded no records. (code, what-to-do)

    MEASURED 2026-08-26 across the regional family: LiteFinance was server-rendered and merely
    mis-parsed (0 -> 15 real records once the card selector was written), Duplitrade's only
    percentage was a CSS gradient in a React bundle, and Collective2 answered 403. Three
    sources, three fixes, one useless label -- so the label is a diagnosis.
    """
    if status and status >= 400:
        return ("HTTP_BLOCKED",
                f"HTTP {status} -- the listing moved (404) or the host refuses this client "
                f"(403); resolve_listing tried the alternates and the site root's own links")
    low = html.lower()
    js_markers = ("__next_data__", "data-reactroot", "ng-version", "data-beasties",
                  "window.__nuxt", "muirtl", "_app-", "runtime.")
    has_numbers = bool(re.search(r">\s*[-+]?\d[\d,.]*\s*%\s*<", html))
    if has_numbers:
        return ("SERVER_RENDERED_WRONG_SELECTOR",
                "the numbers ARE in the HTML and neither the table nor the card extractor "
                "found a repeated record -- write a card parser for this markup")
    if any(m in low for m in js_markers):
        return ("JS_APP_NEEDS_API",
                "client-rendered app: no hydration payload and none of the endpoints its own "
                "bundles name returned a record list")
    return ("UNKNOWN_SHAPE", "page returned 200 with neither rendered numbers nor JS markers")


def generic_cards(source: str, html: str, base_url: str, link_pat: str,
                  region: str) -> list[dict]:
    """Shared extractor: account/strategy links + nearby stats, LABELS READ IN ANY LANGUAGE
    (lang_intel: 収益率, просадка, 最大回撤, أقصى تراجع and drawdown are one concept)."""
    from lang_intel import STAT_CONCEPTS, detect_mechanisms, stat_near
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

#: ALTERNATES a source is resolved through when its primary listing 404s, 403s or fails TLS.
#: Sibling hosts and moved paths of the SAME venue only -- never a new venue (new grounds are
#: registered, not hard-coded here). Tried in order after the primary; the one that yields is
#: remembered in the state file and tried FIRST next run. Unverified from the build sandbox
#: (its egress proxy refuses these hosts), so each is a candidate the run measures, not a claim.
ALTERNATES: dict[str, tuple[str, ...]] = {
    "share4you": ("https://www.share4you.com/en/leaders/", "https://www.share4you.com/leaders",
                  "https://share4you.com/en/leaders"),
    "minfx_jp": ("https://min-fx.jp/systre/", "https://min-fx.jp/systre/ranking/",
                 "https://min-fx.jp/start/systre/"),
    "hfm_pamm": ("https://www.hfm.com/int/en/trading-tools/pamm-performance",
                 "https://pamm.hfm.com/int/en/", "https://pamm.hfm.com/"),
    "followme_cn": ("https://www.followme.com/trade/rank", "https://cn.followme.com/trade",
                    "https://www.followme.com/"),
    "readitrades_africa": ("https://ready-trade.com/",),
    "octa_masters": ("https://my.octabroker.com/copy-trading/",),
    "roboforex_copyfx": ("https://copy.roboforex.pro/ratings/",
                         "https://copyfx.roboforex.com/ratings/"),
    "equiti_copy": ("https://copy-ratings.equiti.com/",),
    "duplitrade": ("https://duplitrade.com/strategy-providers/",),
    "mylivefx_br": ("https://mylivefx.com/ranking/", "https://mylivefx.com/traders/"),
}
_LISTING_LINK = re.compile(
    r'href="([^"#]{2,200})"[^>]*>\s*([^<]{0,80}(?:rank|rating|leader|trader|strateg|master|'
    r'provider|pamm|copy|signal|systre|ランキング|ストラテジー|排行|榜|рейтинг|трейдер)[^<]{0,40})<',
    re.I)


def _listing_links(html: str, base_url: str) -> list[str]:
    """Links on a site root that point at its rating/leader listing, same site only."""
    host = ".".join(urlparse(base_url).netloc.split(".")[-2:])
    out: list[str] = []
    for href, _label in _LISTING_LINK.findall(html):
        u = urljoin(base_url, _html.unescape(href))
        if host in urlparse(u).netloc and u not in out:
            out.append(u)
    return out[:6]


def extract_rows(name: str, html: str, url: str, region: str, lang: str, grade: str,
                 link_pat: str, base_url: str) -> tuple[list[dict], str]:
    """Every extractor, most specific first. Returns (rows, which extractor yielded)."""
    parser = CARD_PARSERS.get(name)
    if parser:
        got = parser(html, region)
        if got:
            return got, "card_parser"
    got = generic_cards(name, html, base_url, link_pat, region)
    # a link list with no numbers anywhere is a navigation menu, not a rating
    if got and any(r_.get("stats") or r_.get("nearby_pcts") for r_ in got):
        return got, "link_cards"
    tab = parse_tables(name, html, url, region)
    if tab:
        return tab, "table"
    cards = parse_repeated_cards(name, html, url, region)
    if cards:
        return cards, "repeated_cards"
    recs = try_json_routes(url, html)
    if recs:
        return records_to_rows(name, recs, region, grade, lang), "json_route"
    if got:
        return got, "link_cards"
    return [], ""


def mine_source(name: str, spec: tuple, page: int, resolved: str = "",
                explore: bool = True) -> dict[str, Any]:
    """Work one source for one page through the whole resolution chain. Never raises.
    `explore=False` (a later page of a listing already found) fetches the page URL only."""
    region, lang, grade, url_fn, link_pat, base_url, _npages = spec
    primary = url_fn(page)
    urls = [u for u in dict.fromkeys(
        [resolved, primary, *(ALTERNATES.get(name, ()) if explore else ())]) if u]
    tried: list[dict[str, Any]] = []
    last_html, last_status, last_err = "", None, ""
    for i, u in enumerate(urls):
        try:
            html = fetch(u, referer=base_url if i else "")
        except FetchError as exc:
            tried.append({"url": u, "status": exc.status, "error": exc.error[:120]})
            last_status, last_err = exc.status, exc.error
            continue
        rows_, how = extract_rows(name, html, u, region, lang, grade, link_pat, base_url)
        tried.append({"url": u, "status": 200, "rows": len(rows_), "via": how})
        if rows_:
            return {"rows": rows_, "url": u, "via": how, "tried": tried, "state": "ok",
                    "error": ""}
        last_html, last_status, last_err = html, 200, ""
    # Nothing on the declared URLs: the listing may have moved. The site root's own links say
    # where it went.
    with contextlib.suppress(FetchError):
        if not explore:
            raise FetchError(primary, None, "no exploration on a later page")
        root = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}/"
        home = fetch(root)
        for u in _listing_links(home, root):
            if u in urls:
                continue
            try:
                html = fetch(u, referer=root)
            except FetchError as exc:
                tried.append({"url": u, "status": exc.status, "error": exc.error[:120]})
                continue
            rows_, how = extract_rows(name, html, u, region, lang, grade, link_pat, base_url)
            tried.append({"url": u, "status": 200, "rows": len(rows_), "via": how,
                          "found_on": "site_root"})
            if rows_:
                return {"rows": rows_, "url": u, "via": how, "tried": tried, "state": "ok",
                        "error": ""}
    if last_status == 200:
        code, todo = diagnose_page(last_html)
        state = code.lower()
    elif last_status:
        code, todo = diagnose_page("", last_status)
        state = "error:HTTPError"
    else:
        code = "FETCH_ERROR"
        todo = "transport failed on every URL (timeout / TLS / DNS) -- see `tried`"
        state = f"error:{(last_err.split(':')[0] or 'FetchError')}"
    return {"rows": [], "url": primary, "via": "", "tried": tried, "state": state,
            "error": last_err or code, "diagnosis": code, "fix_hint": todo}


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
        for r_ in embedded_records(html):
            sym = str(r_.get("symbol") or r_.get("instrument") or "").upper()
            side = str(r_.get("type") or r_.get("side") or r_.get("cmd") or "").upper()
            if sym:
                out.append(row("fbs_tape", "trade_tape", f"{sym} {side}".strip(),
                               "https://fbs.com/top-trades", symbols=[sym], side=side,
                               record=r_))
    if not out:
        out.append(row("fbs_tape", "raw_capture", "top-trades page shape drifted",
                       "https://fbs.com/top-trades", html[:1200],
                       needs_selector_work=True))
    return out[:80]


def update_coverage(name: str, region: str, lang: str, grade: str, state: str,
                    rows_n: int, *, error: str = "", url: str = "", via: str = "",
                    attempts: int = 1) -> None:
    """Ratchet the coverage registry. `attempts` counts page attempts this run; `successes`
    counts attempts that yielded at least one record; `rows_total` is cumulative."""
    with _WRITE_LOCK:
        cov = _read(COVERAGE, {"note": "region x language x platform coverage RATCHET; empty "
                                       "regions are OPEN cells, never 'done'",
                               "open_cells": {"KR": "no native MT5 survivor pool found yet -- "
                                                    "canary searches standing",
                                              "TR": "same; OPEN"},
                               "platforms": {}})
        ent = cov.setdefault("platforms", {}).setdefault(
            name, {"region": region, "lang": lang, "evidence_grade": grade, "best_rows": 0,
                   "attempts": 0})
        now = datetime.now(tz=UTC).isoformat(timespec="seconds")
        ent["attempts"] = int(ent.get("attempts") or 0) + max(1, attempts)
        # successes/rows_total were not counted before 2026-09-30; they start from here and the
        # stamp says so, so an old platform's history reads UNMEASURED, never zero.
        ent.setdefault("counted_since", now)
        ent["successes"] = int(ent.get("successes") or 0) + (1 if rows_n > 0 else 0)
        ent["rows_total"] = int(ent.get("rows_total") or 0) + max(0, rows_n)
        ent["last_rows"] = rows_n
        ent["last_state"] = state
        ent["last_attempt"] = now
        if rows_n > 0:
            ent["last_success"] = now
            ent["last_error"] = ""
        else:
            ent["last_error"] = error[:200]
        if url:
            ent["last_url"] = url
        if via:
            ent["last_via"] = via
        ent["best_rows"] = max(int(ent.get("best_rows") or 0), rows_n)   # ratchets, never falls
        _atomic_write(COVERAGE, json.dumps(cov, indent=1, ensure_ascii=False))


def _append_run(doc: dict[str, Any]) -> None:
    with contextlib.suppress(OSError), _WRITE_LOCK:
        RUNS.parent.mkdir(parents=True, exist_ok=True)
        with RUNS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(doc, ensure_ascii=False, default=str) + "\n")


def _work_source(name: str, spec: tuple, st: dict[str, Any]) -> dict[str, Any]:
    """All of this run's pages for one source (cursor page first), sequential per source so
    the host gate and the source's own pagination stay polite."""
    npages = int(spec[6])
    cur = int(st.get(name, 0) or 0)
    pages = [((cur + k) % npages) + 1 for k in range(min(PAGES_PER_RUN, npages))]
    resolved = str((st.get("_resolved") or {}).get(name) or "")
    results = []
    for page in pages:
        if _DEADLINE["at"] is not None and time.monotonic() >= _DEADLINE["at"]:
            break
        first = page == pages[0]
        res = mine_source(name, spec, page, resolved if first else "", explore=first)
        res["page"] = page
        results.append(res)
        moved = bool(res["rows"] and res.get("url") and res["url"] != spec[3](page))
        if moved:
            resolved = res["url"]
        elif res["rows"] and first:
            resolved = ""          # the primary answers again; forget the stale alternate
        # a single-URL source, a moved listing (its pagination is unknown) or an empty first
        # page has nothing further to walk this run
        if npages == 1 or moved or (not res["rows"] and first):
            break
    return {"name": name, "pages": results, "resolved": resolved,
            "cursor": pages[len(results) - 1] if results else cur}


def run_and_save(*, budget_s: float = RUN_BUDGET_S, workers: int = WORKERS) -> dict:
    now = datetime.now(tz=UTC)
    t0 = time.monotonic()
    _DEADLINE["at"] = t0 + budget_s
    pf.reset_stats(LEG)
    st = _read(STATE, {})
    results: dict[str, Any] = {}
    total_real = 0
    out = pf.run_concurrently(list(SOURCES.items()),
                              lambda kv: _work_source(kv[0], kv[1], st), workers=workers)
    for (name, spec), work, err in out:
        region, lang, grade = spec[0], spec[1], spec[2]
        pages = (work or {}).get("pages") or []
        rows_: list[dict] = []
        for res in pages:
            for r_ in res["rows"]:
                r_.setdefault("evidence_grade", grade)
                r_.setdefault("lang", lang)
                r_.setdefault("region", region)
            rows_.extend(res["rows"])
        if work:
            st[name] = work["cursor"]
            if work.get("resolved"):
                st.setdefault("_resolved", {})[name] = work["resolved"]
            elif any(p["rows"] for p in pages):
                (st.get("_resolved") or {}).pop(name, None)
        last = pages[-1] if pages else {"state": f"error:{err.split(':')[0] or 'NoAttempt'}",
                                        "error": err or "deadline before first fetch",
                                        "url": "", "via": ""}
        ok_page = next((p for p in pages if p["rows"]), None)
        state = "ok" if ok_page else last["state"]
        real = [r_ for r_ in rows_ if not r_.get("needs_selector_work")]
        total_real += len(real)
        if real:
            _clear_blocked(name)
            d = INTEL / name
            d.mkdir(parents=True, exist_ok=True)
            _atomic_write(d / f"discoveries_{now:%Y%m%d_%H%M}.json",
                          json.dumps(rows_, indent=1, default=str, ensure_ascii=False))
        else:
            _record_blocked(name, str(last.get("url") or ""), region,
                            str(last.get("diagnosis") or "FETCH_ERROR"),
                            str(last.get("fix_hint") or ""),
                            json.dumps(last.get("tried") or [], ensure_ascii=False)[:600]
                            if last.get("tried") else str(last.get("error") or "")[:160])
        results[name] = {"discoveries": rows_, "count": len(rows_)}
        update_coverage(name, region, lang, grade, state, len(real),
                        error=str(last.get("error") or ""),
                        url=str((ok_page or last).get("url") or ""),
                        via=str((ok_page or {}).get("via") or ""), attempts=max(1, len(pages)))
        print(f"  {name} p{[p['page'] for p in pages]}: {len(real)} real / {len(rows_)} rows "
              f"[{state}{' via ' + ok_page['via'] if ok_page else ''}]")
    # FBS tape rides along
    try:
        tape = mine_fbs_tape()
        d = INTEL / "fbs_tape"
        d.mkdir(parents=True, exist_ok=True)
        _atomic_write(d / f"discoveries_{now:%Y%m%d_%H%M}.json",
                      json.dumps(tape, indent=1, default=str, ensure_ascii=False))
        results["fbs_tape"] = {"discoveries": tape, "count": len(tape)}
        print(f"  fbs_tape: {len(tape)} rows")
    except Exception as exc:
        print(f"  fbs_tape: {exc}")
    _atomic_write(STATE, json.dumps(st, indent=0, ensure_ascii=False))
    latest_p = INTEL / "latest_discoveries.json"
    latest = _read(latest_p, {})
    latest.update(results)
    _atomic_write(latest_p, json.dumps(latest, indent=1, default=str, ensure_ascii=False))
    secs = time.monotonic() - t0
    s = pf.stats(LEG)
    _append_run({"at": now.isoformat(timespec="seconds"), "leg": LEG, "seconds": round(secs, 2),
                 "workers": workers, "sources": len(SOURCES), "rows": total_real,
                 "sources_yielded": sum(1 for k, v in results.items()
                                        if k != "fbs_tape" and v["count"]),
                 **s, "fetches_per_s": round(s["fetches"] / secs, 3) if secs > 0 else None})
    _DEADLINE["at"] = None
    with contextlib.suppress(Exception):
        from research import alt_data_yield
        alt_data_yield.write(out=YIELD_OUT, coverage=COVERAGE, runs=RUNS)
    print(f"regional hunters: {total_real} real account rows across {len(SOURCES)} grounds "
          f"in {secs:.0f}s ({s['fetches']} fetches)")
    return results


if __name__ == "__main__":
    run_and_save()
