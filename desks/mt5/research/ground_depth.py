"""THE FRONT DOOR IS NOT THE GROUND -- crawl depth for grounds that hold documents and name nothing.

MEASURED 2026-09-23, and it is one cause with fifteen instances. `pack_cells` resolves 106 of the
121 document-holding grounds to an MT5 instrument through its three-rung ladder. The other fifteen
carry the SAME owned reason, written by `pack_cells.resolve_ground` and never by a guess:

    "CRAWL DEPTH (owner: the crawler that fetched it -- world_crawler / deep_forest_miner): the
     documents held are landing or navigation pages that name no MT5 symbol."

Read the documents and the reason is literal. `literature` holds aqr.com's fraud-warning banner and
its nav rail; `github_topics` holds "Reload to refresh your session."; `asia:sgx_derivatives` holds
an iOS upgrade notice in English and Chinese; `asia:port_congestion` holds unctadstat's menu and its
copyright line. Nothing is broken -- `moat_collectors.collect_html` says so in its own docstring:
"link-following belongs to the crawler and the deep-forest miner -- a collector's job is the
immutable capture of the DECLARED document". So the registry's one declared URL per ground is
fetched forever and the ground's own inside is never walked. The crawler DOES walk links, but its
frontier is the open web by yield; it is not aimed at a registered ground that owes cells.

WHAT THIS ORGAN DOES, and every clause is a number it publishes per ground:

  1. TAKES ITS TARGETS FROM THE LADDER IT DOES NOT OWN. `pack_cells.world_rows()` decides which
     grounds hold documents and still name no instrument; this organ never re-derives that and
     never edits that module. A ground the ladder resolves is never touched here.

  2. WALKS INSIDE THE DOOR. Each ground's own held documents give the landing URLs; the desk's own
     reader (`world_crawler.read_page`) gives that page's links and its DATA ENDPOINTS, and the
     links are RANKED -- release, table, statistics, download, csv, contract specification ahead of
     cookie notices and share buttons. Ranking is an ORDER, never a filter: the per-pass budget
     decides how deep this hour goes, the cursor carries the rest to the next pass, and no link is
     ever removed from the ground's list.

  3. CAPTURES THROUGH THE SAME DOOR AS EVERY OTHER DOCUMENT. `moat_collectors.collect_html` ->
     `normalise` -> `write_document` -> `claims_of` -> `record_claims`, with the GROUND's own
     source_id on every row. No second store, no second crawler, no second claim table. A deep page
     therefore becomes a held document of that ground, which is exactly what `pack_cells`' rung 3
     reads -- so the conversion happens on the next pack_cells pass with no change to it.

  4. MEASURES THE ONLY THING THAT COUNTS. Not documents fetched: documents that NAME AN INSTRUMENT
     (`pack_cells.named_instruments`, the same universe-routed test the ladder uses) or a SERIES the
     desk can map (a data endpoint: csv/json/xlsx/api). Both are published per ground, before and
     after, with the grounds-naming-an-instrument total that is this job's deliverable.

  5. RECORDS WHAT FAILS AS A VERDICT, NOT AS A PENDING JOB. A ground whose deeper pages still name
     nothing gets DEEPER_PAGES_NAME_NOTHING with the URLs tried, the links seen and the hosts; a
     ground whose pages carry a shape the desk has no reader for gets READER_MISSING with the SHAPE
     named (javascript_rendered, pdf_only, api_key_required, access_controlled), which makes the
     next reader a known job. Verdicts accumulate attempts across passes in
     `data/ground_depth_verdicts.json`, so "tried 3 times, 41 pages, nothing named" is a MEASURED
     exhaustion claim with per-attempt evidence and not an adjective.

  6. HANDS THE REST TO THE DESK'S OWN FRONTIER. Promising links this pass did not reach are pushed
     to `world_frontier` with `discovered_via` set to the landing page, so the hourly crawler walks
     them on its own clock. That is the bound on depth: a per-pass wall clock plus the frontier the
     desk already runs, never an unbounded recursive crawl of its own.

LAWFUL IN THE DESK'S CURRENT SENSE. Everything reachable on the open internet is fetched and
labelled. The only refusals are the five acts -- credential theft, logging in as someone else,
bypassing a paywall or access control, material non-public information, stolen or personal data --
and a refused link is COUNTED AND NAMED in the report with the act it would have been, so a refusal
is visible evidence and never a silent absence.

NOTHING HERE IS A CAP. It mints nothing, judges nothing, sizes nothing and vetoes nothing; it
fetches pages the desk already declared it wanted and files them where the desk already files them.

    python desks/mt5/research/ground_depth.py --once --budget-s 600
    python desks/mt5/research/ground_depth.py --once --dry-run
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(DESK / "side_channels"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = DESK / "reports" / "GROUND_DEPTH.json"
VERDICTS = DESK / "data" / "ground_depth_verdicts.json"
CURSOR = DESK / "data" / "ground_depth_cursor.json"

#: Links followed per ground per pass. THE ORDER, NOT A CAP: the cursor advances by exactly this
#: many, so the next pass takes the next ones and a ground with two hundred links is walked in
#: passes rather than refused. A pass cut short leaves its grounds at the head of the next one.
LINKS_PER_GROUND_PER_PASS = 8
#: Landing pages re-read per ground per pass to harvest links. A ground's held documents usually
#: come from one or two URLs; reading them all again every pass would spend the budget on chrome.
LANDINGS_PER_GROUND = 3
#: Below this many characters of extracted text, a page that returned a large body is a shell the
#: desk's reader cannot see into -- the javascript_rendered shape, which is a named reader job.
MIN_TEXT_CHARS = 500
#: A body this large that yields almost no text is the same shape stated the other way round.
SHELL_BODY_BYTES = 20_000

#: THE FIVE ACTS. A link matching one of these is set aside, counted and named -- never fetched,
#: never hidden. Everything else on the open internet is fetched and labelled.
_ACCESS_DOORS: tuple[str, ...] = (
    "/login", "/log-in", "/signin", "/sign-in", "/register", "/signup", "/sign-up",
    "/account", "/accounts/", "/auth/", "/oauth", "/subscribe", "/subscription",
    "/checkout", "/cart", "/paywall", "/members", "/my-account", "/password", "/session/new")

#: What a page that HOLDS SOMETHING looks like in its own URL and anchor text, in the languages the
#: desk mines. Weights are an order of preference, nothing else reads them.
_CONTENT_TOKENS: dict[str, float] = {
    "download": 3.0, "csv": 3.0, "xlsx": 3.0, ".xls": 2.5, "json": 2.0, "/api": 2.0,
    "dataset": 3.0, "data/": 2.5, "statistic": 3.0, "statistics": 3.0, "series": 2.5,
    "release": 2.5, "report": 2.0, "publication": 2.0, "bulletin": 2.0, "table": 2.5,
    "price": 2.0, "quote": 2.0, "settlement": 3.0, "futures": 2.5, "contract": 2.5,
    "specification": 2.5, "product": 1.5, "market": 1.5, "index": 1.5, "history": 2.5,
    "historical": 2.5, "archive": 2.0, "chart": 1.5, "research": 1.5, "paper": 1.5,
    "strategy": 2.0, "signal": 2.0, "backtest": 2.5, "performance": 2.0, "results": 2.0,
    "code": 1.5, "blob/": 2.0, "raw/": 2.5, "readme": 2.0, "wiki": 1.5, "docs": 1.5,
    "数据": 3.0, "统计": 3.0, "报告": 2.0, "行情": 2.5, "指数": 2.0, "期货": 2.5,
    "データ": 3.0, "統計": 3.0, "先物": 2.5, "통계": 3.0, "데이터": 3.0,
    "datos": 2.5, "estadistica": 3.0, "estadística": 3.0, "informe": 2.0, "mercado": 1.5,
}
#: Site furniture. A NEGATIVE WEIGHT IS STILL A RANK -- such a link sorts last and is still
#: followed when a ground has nothing better, because "about us" pages occasionally carry the only
#: statement of what a venue publishes.
_CHROME_TOKENS: dict[str, float] = {
    "privacy": -3.0, "cookie": -3.0, "terms": -3.0, "legal": -2.0, "disclaimer": -2.0,
    "careers": -3.0, "contact": -2.0, "about": -1.0, "sitemap": -1.5, "newsletter": -2.5,
    # `//x.com/` and not `x.com`: the bare token also matched sgx.com, which is a VENUE, and the
    # share button's penalty was being charged to the Singapore Exchange's own pages.
    "facebook": -3.0, "twitter": -3.0, "//x.com/": -2.0, "linkedin": -3.0, "instagram": -3.0,
    "youtube.com": -1.0, "share?": -3.0, "/tags/": -1.0, "/tag/": -1.0, "/feed": -1.0,
    "mailto:": -4.0, "#": -0.5, "javascript:": -4.0, "/search": -1.5, "language": -1.5,
}
#: File extensions that ARE a series even when the page around them names no symbol.
_SERIES_EXT: tuple[str, ...] = (".csv", ".tsv", ".json", ".xlsx", ".xls", ".zip", ".parquet")
#: File extensions the desk's html reader cannot read; naming the shape is the reader job.
_UNREADABLE_EXT: tuple[str, ...] = (".pdf", ".doc", ".docx", ".ppt", ".pptx", ".zip", ".gz")


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")


def _pc() -> Any:
    """The ladder module, or None. It is read for its own constants and never edited."""
    try:
        from research import pack_cells as pc
        return pc
    except Exception:
        return None


def refusal(url: str, anchor: str = "") -> str:
    """The act this link would have been, or "". THE ONLY REFUSALS ON THIS DESK.

    A sign-in, registration, subscription or checkout door is the one shape that cannot be walked
    without logging in as someone else or crossing an access control. Everything else -- every
    robots preference, every rate note, every "please do not scrape" -- is not one of the five
    acts and is therefore not refused here; the desk fetches the open internet and labels it.
    """
    low = f"{url} {anchor}".lower()
    if any(door in low for door in _ACCESS_DOORS):
        return ("access control: the link is a sign-in, registration or subscription door, and "
                "logging in as someone else / bypassing an access control is one of the five acts")
    return ""


def link_score(url: str, anchor: str, base_host: str) -> float:
    """How likely this link leads to the ground's CONTENT rather than its chrome.

    Derived from the URL and its anchor text only -- no network, no state, no model. Same-host
    links are preferred because a registered ground owes cells about ITSELF, and a data endpoint
    outranks everything because a csv IS the series the desk came for.
    """
    low = f"{url} {anchor}".lower()
    score = 0.0
    for token, w in _CONTENT_TOKENS.items():
        if token in low:
            score += w
    for token, w in _CHROME_TOKENS.items():
        if token in low:
            score += w
    host = urlparse(url).netloc.lower()
    if host and base_host and (host == base_host or host.endswith("." + base_host)):
        score += 2.0
    path = urlparse(url).path.lower()
    if path.endswith(_SERIES_EXT):
        score += 4.0
    if path.endswith(_UNREADABLE_EXT):
        score -= 1.0                      # still followed: its shape is the reader job it names
    depth = path.count("/")
    if depth >= 2:
        score += 0.5                      # a deep path is inside the site, not its front door
    try:
        import world_frontier as wf  # type: ignore[import-not-found]
        if wf.worth_following(url, anchor):
            score += 1.0                  # the desk's own recall-biased opinion, as a BONUS
    except Exception:
        pass
    return round(score, 3)


def is_series_endpoint(url: str) -> bool:
    """Does this URL hand over a SERIES -- a file or a data API -- rather than a page about one?"""
    path = urlparse(url).path.lower()
    return path.endswith(_SERIES_EXT) or "/api/" in path or path.endswith("/api")


def landing_urls(source_id: str, registry_url: str) -> list[str]:
    """The URLs this ground already holds documents from, most-recent-distinct first.

    Read from the claims' own provenance through `pack_cells.held_documents`, which is the same
    bounded read the ladder does -- the landing pages ARE the ground's held documents, and that is
    the whole finding this organ exists to act on.
    """
    urls: list[str] = []
    try:
        from research import pack_cells as pc
        for d in pc.held_documents(source_id):
            u = str(d.get("url") or "").strip()
            if u and u not in urls:
                urls.append(u)
    except Exception:
        pass
    reg = str(registry_url or "").strip()
    if reg and reg not in urls:
        urls.append(reg)
    return urls


def harvest(url: str, lang: str = "") -> dict[str, Any]:
    """One landing page's links and data endpoints, through the desk's own reader.

    `moat_collectors.fetch_text` is the desk's one HTTP client (it wraps `deep_forest_miner._http`)
    and `world_crawler.read_page` is the desk's one page reader. Neither is re-implemented here.
    """
    try:
        from research import moat_collectors as mc
        body, status, err = mc.fetch_text(url, lang)
    except Exception as exc:                                     # a bad page never ends the pass
        return {"url": url, "error": f"{type(exc).__name__}: {str(exc)[:80]}", "links": [],
                "endpoints": [], "status": 0, "text_len": 0, "body_bytes": 0}
    if not body:
        return {"url": url, "error": err or "empty body", "links": [], "endpoints": [],
                "status": status, "text_len": 0, "body_bytes": 0}
    try:
        import world_crawler as wc  # type: ignore[import-not-found]
        page = wc.read_page(body.encode("utf-8", errors="replace"), url)
    except Exception as exc:
        return {"url": url, "error": f"read_page: {type(exc).__name__}: {str(exc)[:60]}",
                "links": [], "endpoints": [], "status": status, "text_len": 0,
                "body_bytes": len(body)}
    return {"url": url, "error": "", "status": status,
            "links": [(str(u), str(a or "")) for u, a in (page.get("links") or [])],
            "endpoints": [str(e) for e in (page.get("endpoints") or [])],
            "symbols": [str(s) for s in (page.get("symbols") or [])],
            "text_len": int(page.get("text_len") or 0), "body_bytes": len(body)}


def ranked_links(harvests: list[dict[str, Any]], base_host: str) -> list[dict[str, Any]]:
    """Every link and endpoint the landing pages offered, best first, deduped, with refusals named.

    A refused link keeps its row and carries the act it would have been, so the report can publish
    what was set aside and why instead of showing a shorter list with no explanation.
    """
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for h in harvests:
        pairs = [(u, "") for u in (h.get("endpoints") or [])]
        pairs += list(h.get("links") or [])
        for url, anchor in pairs:
            clean = str(url).split("#")[0].strip()
            if not clean.startswith(("http://", "https://")) or clean in seen:
                continue
            seen.add(clean)
            act = refusal(clean, anchor)
            out.append({"url": clean, "anchor": str(anchor)[:80],
                        "score": link_score(clean, anchor, base_host), "via": h.get("url"),
                        "refused": act, "series": is_series_endpoint(clean)})
    out.sort(key=lambda r: (-float(r["score"]), r["url"]))
    return out


def page_shape(doc: dict[str, Any], cap_text: str, body_bytes: int, status: int,
               url: str) -> str:
    """The SHAPE of a page the desk could not read anything out of, named for the next reader.

    Empty when the page was read fine. This is the difference between "that ground gave nothing"
    and "that ground publishes PDFs and the desk has no PDF reader on this path" -- the second is
    a job with a specification, the first is a shrug.
    """
    path = urlparse(url).path.lower()
    if status in (401, 402, 403):
        return f"access_controlled: HTTP {status}"
    if path.endswith(_UNREADABLE_EXT):
        return f"binary_document: {path.rsplit('.', 1)[-1]} needs the collector for that media type"
    if "/api" in path and status in (0, 400, 404, 422):
        return "api_key_required: the endpoint answers only to a parameterised or keyed request"
    if body_bytes >= SHELL_BODY_BYTES and len(cap_text) < MIN_TEXT_CHARS:
        return ("javascript_rendered: the page returned "
                f"{body_bytes} bytes and {len(cap_text)} characters of text, so its content is "
                "assembled in the browser and needs a headless reader")
    if not cap_text.strip():
        return "empty_after_read: the fetch succeeded and the reader extracted no text"
    _ = doc
    return ""


def fetch_deep(sid: str, url: str, lang: str, budget_s: float) -> dict[str, Any]:
    """One deep page, captured and normalised as a document OF THIS GROUND.

    Everything here belongs to `moat_collectors`: the capture is immutable and sha-addressed, the
    document is normalised by the same function every other document goes through, and the claims
    are that module's sentences. The only thing this organ supplies is the URL.
    """
    try:
        from research import moat_collectors as mc
    except Exception as exc:
        return {"url": url, "error": f"moat_collectors unavailable: {type(exc).__name__}: {exc}",
                "claims": [], "named": [], "shape": ""}
    row = {"source_id": sid, "url": url, "kind": "html", "language": lang}
    try:
        caps = mc.collect_html(row, budget_s)
    except Exception as exc:
        return {"url": url, "error": f"collect_html: {type(exc).__name__}: {str(exc)[:70]}",
                "claims": [], "named": [], "shape": ""}
    if not caps:
        return {"url": url, "error": "no capture", "claims": [], "named": [], "shape": ""}
    cap = caps[0]
    doc = mc.normalise(cap)
    with contextlib.suppress(Exception):
        mc.write_document(doc)
    claims = mc.claims_of(doc)
    try:
        from research import pack_cells as pc
        named = pc.named_instruments([str(doc.get("text") or "")])
    except Exception:
        named = []
    shape = page_shape(doc, str(doc.get("text") or ""), int(cap.content_length or 0),
                       int(cap.http_status or 0), url)
    # The symbol the page NAMES must exist in the ground's claims, or the ladder cannot see it.
    claims = [*symbol_excerpt_claims(doc, named), *claims]
    return {"url": url, "error": str(cap.unmeasured or ""), "claims": claims, "named": named,
            "shape": shape, "http_status": int(cap.http_status or 0),
            "text_chars": len(str(doc.get("text") or "")),
            "title": str(doc.get("title") or "")[:90]}


#: Characters of the document kept either side of a symbol, VERBATIM, when the page names an
#: instrument and no extracted sentence carries it. Wide enough to read, narrow enough to be an
#: excerpt of that page and nothing else.
EXCERPT_RADIUS = 160


def symbol_excerpt_claims(doc: dict[str, Any], named: list[str]) -> list[dict[str, Any]]:
    """The page's own words AROUND the instrument it names, as claims of this ground.

    MEASURED 2026-09-23, and this is the whole reason the first walk moved two grounds and not
    six. A deeper page names XAUUSD in a signal table, a product grid or a title -- and
    `moat_collectors.claims_of` emits SENTENCES, so the symbol never reaches the claims table and
    the ladder, which reads claim TEXT, still sees only navigation prose. The page named the
    instrument; the desk's record of the page did not.

    So one claim per named symbol carries the document's own characters around that symbol,
    VERBATIM and nothing else -- no summary, no template, no asserted relationship. It is the
    same evidence the page shows a reader, cut to a window, stamped with the same provenance as
    every other claim from that capture, and deduped by `lead_id_of` like every other claim.
    """
    text = " ".join(str(doc.get("text") or "").split())
    if not text or not named:
        return []
    try:
        from libs.research import lead_schema as ls
        from research.moat_collectors import _instruments
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    upper = text.upper()
    for sym in named[:8]:
        at = upper.find(sym.upper())
        if at < 0:
            continue
        excerpt = text[max(0, at - EXCERPT_RADIUS): at + len(sym) + EXCERPT_RADIUS].strip()
        if not excerpt:
            continue
        out.append({
            "claim_id": ls.lead_id_of(str(doc.get("source_id") or ""), excerpt),
            "doc_id": str(doc.get("doc_id") or ""),
            "source_id": str(doc.get("source_id") or ""),
            "text": excerpt,
            "language": str(doc.get("language") or "UNMEASURED"),
            "knowable_at": str(doc.get("knowable_at") or "UNMEASURED"),
            "instruments": _instruments(excerpt) or [sym],
            "kind": "claim",
            "media_type": str(doc.get("media_type") or ""),
            "provenance": {**dict(doc.get("provenance") or {}),
                           "excerpt_of": "the page's own characters around the symbol it names; "
                                         "verbatim, cut by ground_depth.symbol_excerpt_claims"},
        })
    return out


def order_claims(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Instrument-naming claims first. NOT A FILTER -- every claim is written, in a chosen ORDER.

    `pack_cells.held_documents` reads a ground's FIRST `RESOLVE_SAMPLE` claims by created_at, and
    every claim this organ writes in one pass carries the same timestamp, so insertion order is
    what that bounded sample sees. Writing the pages that name an instrument first is the
    difference between the ladder resolving the ground next pass and reading twenty-four more
    sentences of navigation chrome. Nothing is dropped and nothing is reordered in the database.
    """
    try:
        from research import pack_cells as pc
    except Exception:
        return rows
    def names(r: dict[str, Any]) -> int:
        return 1 if pc.named_instruments([str(r.get("text") or "")]) else 0
    return sorted(rows, key=lambda r: -names(r))


def write_claims(rows: list[dict[str, Any]]) -> tuple[int, int, str]:
    """(claims, edges, error) through `moat_collectors.record_claims` -- the desk's ONE claim door.

    Instrument-naming rows go in first (see `order_claims`); nothing is dropped, deduped or
    rewritten here, and no second claim table exists.
    """
    try:
        from libs.moat import registry as reg
        from research.moat_collectors import record_claims
    except Exception as exc:
        return 0, 0, f"claim door unavailable: {type(exc).__name__}: {str(exc)[:70]}"
    try:
        conn = reg.connect()
    except Exception as exc:
        return 0, 0, f"registry unavailable: {type(exc).__name__}: {str(exc)[:70]}"
    try:
        written, edges = record_claims(conn, order_claims(rows))
        return int(written), int(edges), ""
    except Exception as exc:
        return 0, 0, f"record_claims: {type(exc).__name__}: {str(exc)[:70]}"
    finally:
        with contextlib.suppress(Exception):
            conn.close()


def seed_frontier(links: list[dict[str, Any]], lang: str = "") -> int:
    """Promising links this pass did not reach, handed to the desk's own frontier.

    THIS IS THE BOUND ON DEPTH. No recursion here: the hourly `world_crawler` already walks the
    frontier by measured yield with its own per-host politeness and its own run clock, so a link
    added here is walked on a clock that exists rather than by this organ going deeper and deeper
    inside one hour.
    """
    if not links:
        return 0
    try:
        import world_frontier as wf
        sources = wf.load()
    except Exception:
        return 0
    added = 0
    for row in links:
        if row.get("refused"):
            continue
        with contextlib.suppress(Exception):
            if wf.add(sources, str(row["url"]), str(row.get("via") or "ground_depth"), lang):
                added += 1
    if added:
        with contextlib.suppress(Exception):
            wf.save(sources, note=f"ground_depth seeded {added} link(s) from registered grounds")
    return added


def verdict_of(pages: list[dict[str, Any]], series: list[str], links_seen: int,
               *, ladder_sees: bool | None = None, claims_held: int = 0) -> tuple[str, str]:
    """(verdict, the reason it is that verdict). Every branch is a measurement of this pass."""
    named = [p for p in pages if p.get("named")]
    if named and ladder_sees is False:
        # THE PAGE NAMED IT AND THE LADDER STILL CANNOT SEE IT, which is a different failure from
        # a ground that names nothing, and it is not this organ's to fix.
        return ("LADDER_WINDOW_SATURATED",
                f"{len(named)} deeper page(s) name an MT5 instrument and this ground now holds "
                f"{claims_held} claims, but `pack_cells.held_documents` resolves a ground from its "
                f"OLDEST {getattr(_pc(), 'RESOLVE_SAMPLE', 24)} claims (ORDER BY created_at "
                "LIMIT), and those are the landing page's chrome. The evidence is in the registry; "
                "the sample the ladder reads is full of older rows")
    if named:
        return ("NAMES_AN_INSTRUMENT",
                f"{len(named)} of {len(pages)} deeper page(s) name an MT5 instrument "
                f"({', '.join(sorted({s for p in named for s in p['named']}))[:120]}); the ladder "
                "resolves this ground on the next pack_cells pass")
    if series:
        return ("NAMES_A_SERIES",
                f"no deeper page names an MT5 symbol, but {len(series)} data endpoint(s) were "
                "found on this ground: it publishes a series and the next job is registering it "
                "as a data pack (desks/mt5/data/asia_sources.json) rather than reading more prose")
    shapes = sorted({str(p.get("shape")) for p in pages if p.get("shape")})
    if shapes and len(shapes) >= 1 and all(p.get("shape") for p in pages) and pages:
        return ("READER_MISSING",
                "every deeper page carries a shape this desk has no reader for on this path: "
                + "; ".join(shapes)[:300])
    if not pages:
        return ("NO_PAGE_FETCHED",
                f"{links_seen} link(s) were offered by the landing pages and none could be "
                "fetched this pass")
    return ("DEEPER_PAGES_NAME_NOTHING",
            f"{len(pages)} deeper page(s) fetched from this ground's own landing page(s), out of "
            f"{links_seen} link(s) offered, and not one names an MT5 instrument or a data "
            "endpoint; the ground is prose about itself")


def next_job_for(verdict: str, shapes: list[str], attempts: int, pages: int) -> str:
    """The owned next job for a ground this pass did not convert. Never "look again"."""
    if verdict == "NAMES_AN_INSTRUMENT":
        return ""
    if verdict == "NAMES_A_SERIES":
        return ("REGISTER THE SERIES: add the endpoint(s) as a row in "
                "desks/mt5/data/asia_sources.json with its targets, and source_drain collects, "
                "asia_parser stamps and pack_cells mints from the stamped frame")
    if verdict == "LADDER_WINDOW_SATURATED":
        return ("WIDEN THE LADDER'S SAMPLE (owner: desks/mt5/research/pack_cells.py, "
                "held_documents): it reads a ground's OLDEST RESOLVE_SAMPLE claims, so a ground "
                "whose landing page was captured first can never be resolved by evidence fetched "
                "later. Sampling the newest rows as well as the oldest resolves this ground with "
                "the claims already in the registry -- no further crawling is required")
    if verdict == "READER_MISSING":
        return ("WRITE THE READER: " + ("; ".join(shapes)[:200] or "shape unrecorded")
                + " -- owner: desks/mt5/research/moat_collectors.py COLLECTORS (the media-type "
                  "dispatch already exists; this ground names which reader is missing)")
    return (f"MEASURED EXHAUSTION SO FAR: {attempts} pass(es), {pages} deeper page(s), nothing "
            "named. The remaining depth is handed to world_frontier (seeded above); if three "
            "passes name nothing this ground's documents are chrome and the honest disposition is "
            "to retire it from the cell backlog, not to crawl it again")


def deepen(row: dict[str, Any], budget_s: float, *, dry_run: bool = False,
           offset: int = 0) -> dict[str, Any]:
    """One ground, walked inside its own front door. Returns everything measured about the walk."""
    t0 = time.monotonic()
    sid = str(row.get("id") or "")
    lang = str(row.get("language") or "")
    landings = landing_urls(sid, str(row.get("url") or ""))[:LANDINGS_PER_GROUND]
    harvests = [harvest(u, lang) for u in landings]
    base_host = (urlparse(landings[0]).netloc.lower() if landings else "")
    links = ranked_links(harvests, base_host)
    allowed = [r for r in links if not r["refused"]]
    refused = [r for r in links if r["refused"]]
    take = allowed[offset:offset + LINKS_PER_GROUND_PER_PASS]
    if not take and allowed:
        take = allowed[:LINKS_PER_GROUND_PER_PASS]          # the ground wraps, it is never spent
    series = [r["url"] for r in allowed if r["series"]][:12]

    pages: list[dict[str, Any]] = []
    claim_rows: list[dict[str, Any]] = []
    if not dry_run:
        for r in take:
            left = budget_s - (time.monotonic() - t0)
            if left <= 2.0:
                break
            page = fetch_deep(sid, str(r["url"]), lang, left)
            claim_rows.extend(page.pop("claims", []))
            pages.append(page)

    written = edges = 0
    if claim_rows and not dry_run:
        written, edges, err = write_claims(claim_rows)
        if err:
            pages.append({"url": "", "error": err, "named": [], "shape": ""})

    seeded = 0 if dry_run else seed_frontier(allowed[offset + LINKS_PER_GROUND_PER_PASS:
                                                     offset + LINKS_PER_GROUND_PER_PASS + 20],
                                             lang)
    # WHAT THE LADDER ITSELF SEES, after the claims are written. This organ's page-level test is
    # not the deliverable; `pack_cells.resolve_ground` is, so it is asked directly and its answer
    # is published whether it agrees or not.
    ladder: dict[str, Any] = {}
    claims_held = 0
    if not dry_run:
        pc = _pc()
        with contextlib.suppress(Exception):
            if pc is not None:
                ladder = pc.resolve_ground({"id": sid, "url": str(row.get("url") or "")})
        with contextlib.suppress(Exception):
            from libs.moat import registry as reg
            conn = reg.connect()
            try:
                claims_held = int(conn.execute(
                    "SELECT COUNT(*) FROM claims WHERE source_id = ?", (sid,)).fetchone()[0])
            finally:
                with contextlib.suppress(Exception):
                    conn.close()
    ladder_sees = bool(ladder.get("targets")) if ladder else None
    verdict, why = verdict_of(pages, series, len(links), ladder_sees=ladder_sees,
                              claims_held=claims_held)
    if dry_run:                    # nothing was fetched, so no verdict about the ground is earned
        verdict, why = "DRY_RUN", (f"{len(links)} link(s) offered, {len(take)} would be followed "
                                   f"this pass, {len(series)} data endpoint(s) visible")
    shapes = sorted({str(p.get("shape")) for p in pages if p.get("shape")})
    named = sorted({s for p in pages for s in (p.get("named") or [])})
    return {
        "id": sid, "verdict": verdict, "why": why,
        "landing_pages": landings,
        "landing_errors": [f"{h['url']}: {h['error']}" for h in harvests if h.get("error")],
        "links_offered": len(links), "links_followed": len(pages),
        "links_refused": len(refused),
        "refusals": [{"url": r["url"][:140], "act": r["refused"]} for r in refused[:5]],
        "series_endpoints": series,
        "pages": [{"url": str(p.get("url"))[:140], "named": p.get("named") or [],
                   "text_chars": p.get("text_chars"), "shape": p.get("shape") or "",
                   "error": p.get("error") or "", "title": p.get("title") or ""}
                  for p in pages],
        "instruments_named": named,
        "ladder_mapped_by": str(ladder.get("mapped_by") or "") if ladder else "",
        "ladder_targets": list(ladder.get("targets") or []) if ladder else [],
        "claims_held": claims_held,
        "claims_written": written, "claim_edges": edges,
        "frontier_seeded": seeded, "shapes": shapes,
        "next_offset": offset + len(take),
        "seconds": round(time.monotonic() - t0, 2),
    }


def targets(limit: int = 60) -> tuple[list[dict[str, Any]], int, int, str]:
    """(grounds holding documents that still name no instrument, naming, holding, why).

    The ladder decides, not this organ: `pack_cells.world_rows()` is called and its verdict is
    read. Ranked by documents already held, highest first -- the same ranking `pack_cells` uses,
    because a ground the crawler has already paid for is the cheapest cell on the desk.
    """
    try:
        from research import pack_cells as pc
        rows, why = pc.world_rows()
    except Exception as exc:
        return [], 0, 0, f"pack_cells.world_rows failed: {type(exc).__name__}: {exc}"
    holding = [w for w in rows if int(w.get("n_documents") or 0) > 0]
    naming = [w for w in holding if w.get("targets")]
    unmapped = sorted((w for w in holding if not w.get("targets")),
                      key=lambda w: (-int(w["n_documents"]), str(w["id"])))
    return unmapped[:limit], len(naming), len(holding), why


def build(budget_s: float = 600.0, *, dry_run: bool = False,
          only: str = "") -> dict[str, Any]:
    t0 = time.monotonic()
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    unmapped, naming_before, holding, why = targets()
    if only:
        wanted = {s.strip() for s in only.split(",") if s.strip()}
        unmapped = [w for w in unmapped if str(w["id"]) in wanted]

    cursor = _read(CURSOR, {}) or {}
    offsets: dict[str, int] = dict(cursor.get("offsets") or {})
    start = int(cursor.get("next_ground") or 0)
    order = (unmapped[start % max(len(unmapped), 1):] + unmapped[:start % max(len(unmapped), 1)]
             if unmapped else [])

    history: dict[str, Any] = _read(VERDICTS, {}) or {}
    results: list[dict[str, Any]] = []
    for w in order:
        left = budget_s - (time.monotonic() - t0)
        if left <= 5.0:
            break
        sid = str(w["id"])
        res = deepen(w, min(left, max(budget_s / 3.0, 60.0)), dry_run=dry_run,
                     offset=offsets.get(sid, 0))
        prior = history.get(sid) or {}
        attempts = int(prior.get("attempts") or 0) + (0 if dry_run else 1)
        pages_total = int(prior.get("pages_total") or 0) + int(res["links_followed"])
        res["attempts"] = attempts
        res["pages_total"] = pages_total
        res["next_job"] = next_job_for(res["verdict"], res["shapes"], attempts, pages_total)
        results.append(res)
        offsets[sid] = int(res["next_offset"])
        if not dry_run:
            history[sid] = {
                "at": now, "verdict": res["verdict"], "why": res["why"],
                "attempts": attempts, "pages_total": pages_total,
                "tried_urls": sorted({*(prior.get("tried_urls") or []),
                                      *[str(p["url"]) for p in res["pages"] if p.get("url")]})[:40],
                "landing_pages": res["landing_pages"], "shapes": res["shapes"],
                "instruments_named": res["instruments_named"],
                "series_endpoints": res["series_endpoints"],
                "next_job": res["next_job"],
                "rule": ("a measured verdict per attempt with the URLs tried, so a ground that "
                         "names nothing is an exhaustion CLAIM with evidence and never an open "
                         "job with no owner"),
            }

    if not dry_run:
        _write(VERDICTS, history)
        _write(CURSOR, {"at": now, "offsets": offsets,
                        "next_ground": (start + len(results)) % max(len(unmapped), 1),
                        "rule": ("a round robin over grounds that hold documents and name no "
                                 "instrument, with a per-ground link offset so the next pass "
                                 "follows the next links rather than the same eight")})

    # AFTER, measured the same way as before -- by the ladder, not by this organ's own bookkeeping.
    _naming_after = naming_before
    holding_after = holding
    if not dry_run:
        _unmapped_after, _naming_after, holding_after, _ = targets()

    converted = [r["id"] for r in results if r["verdict"] == "NAMES_AN_INSTRUMENT"]
    by_verdict: dict[str, int] = {}
    for r in results:
        by_verdict[r["verdict"]] = by_verdict.get(r["verdict"], 0) + 1
    return {
        "at": now,
        "status": "OK" if results or not unmapped else "UNMEASURED",
        "why": why,
        "headline": {
            "grounds_holding_documents": holding_after,
            "naming_an_instrument_before": naming_before,
            "naming_an_instrument_after": _naming_after,
            "delta": _naming_after - naming_before,
            "grounds_walked_this_pass": len(results),
            "deeper_pages_fetched": sum(int(r["links_followed"]) for r in results),
            "deeper_pages_naming_an_instrument": sum(
                sum(1 for p in r["pages"] if p.get("named")) for r in results),
            "claims_written": sum(int(r["claims_written"]) for r in results),
            "frontier_seeded": sum(int(r["frontier_seeded"]) for r in results),
            "grounds_converted_this_pass": converted,
        },
        "by_verdict": dict(sorted(by_verdict.items(), key=lambda kv: -kv[1])),
        "grounds": results,
        "still_unmapped_ranked": [
            {"id": r["id"], "verdict": r["verdict"], "attempts": r["attempts"],
             "pages_total": r["pages_total"], "next_job": r["next_job"]}
            for r in sorted(results, key=lambda r: (-int(r["pages_total"]), r["id"]))
            if r["verdict"] != "NAMES_AN_INSTRUMENT"],
        "refusals": {
            "acts": ["credential theft", "logging in as someone else",
                     "bypassing a paywall or access control",
                     "material non-public information", "stolen or personal data"],
            "links_set_aside": sum(int(r["links_refused"]) for r in results),
            "rule": ("everything reachable on the open internet is fetched and labelled; a "
                     "refusal is counted and named so it is evidence, never a silent absence"),
        },
        "consumers": [
            "libs/moat/registry.py claims -> the deep pages become held documents OF THE GROUND, "
            "which is exactly what pack_cells' rung 3 (instruments_named_in_documents) reads",
            "desks/mt5/research/pack_cells.py -> mints the cells on its own hourly clock from the "
            "grounds this organ resolves; nothing here mints, judges or sizes",
            "desks/mt5/data/ground_depth_verdicts.json -> the measured verdict and the owned next "
            "job per ground, accumulated across passes",
            "desks/mt5/side_channels/world_frontier.py -> the links this pass did not reach",
        ],
        "boundary": ("WALKS AND FILES ONLY. No cell is minted here, no candidate judged, no "
                     "budget sized. The per-pass budget is a wall clock and a ground not reached "
                     "leads the next pass."),
        "dry_run": bool(dry_run),
        "seconds": round(time.monotonic() - t0, 2),
    }


def write(doc: dict[str, Any], *, report: Path | None = None) -> None:
    out = report or OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, default=str) + "\n", encoding="utf-8")
    try:
        from libs.ops.events import emit
        head = doc.get("headline") or {}
        emit("ground_depth", grounds_walked=head.get("grounds_walked_this_pass"),
             pages=head.get("deeper_pages_fetched"),
             pages_naming=head.get("deeper_pages_naming_an_instrument"),
             naming_before=head.get("naming_an_instrument_before"),
             naming_after=head.get("naming_an_instrument_after"))
    except Exception:                                                    # pragma: no cover
        pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--dry-run", action="store_true",
                    help="rank the links this pass would follow and write nothing")
    ap.add_argument("--only", default="", help="comma-separated ground ids, for a targeted walk")
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s, dry_run=a.dry_run, only=a.only)
    try:
        write(doc)
    except OSError as exc:
        print(f"ground depth: could not write {OUT}: {exc}")
        return 1
    h = doc["headline"]
    print(f"ground depth: {h['grounds_walked_this_pass']} ground(s) walked, "
          f"{h['deeper_pages_fetched']} deeper page(s), "
          f"{h['deeper_pages_naming_an_instrument']} naming an instrument, "
          f"{h['claims_written']} claim(s) written, {h['frontier_seeded']} link(s) to the frontier")
    print(f"  grounds holding documents that name an instrument: "
          f"{h['naming_an_instrument_before']} -> {h['naming_an_instrument_after']} of "
          f"{h['grounds_holding_documents']}  (converted: {h['grounds_converted_this_pass']})")
    for r in doc["grounds"]:
        print(f"   {str(r['id'])[:26]:<26} {r['verdict']:<26} "
              f"links {r['links_offered']:<4} walked {r['links_followed']:<3} "
              f"{str(r['why'])[:70]}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
