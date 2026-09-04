"""The deep-forest story miner: Chinese practitioner ground, reverse-engineered into the gauntlet.

    Discover (search-engine + platform routes) -> Extract (bilingual mechanism claims)
      -> queue (story_mechanism) -> deepening worker Reimplement -> compiler -> gauntlet
      -> world crawler frontier (every URL found here becomes crawlable ground)

WHY A SECOND MINER BESIDE THE WORLD CRAWLER. The crawler follows LINKS; it reaches what its
frontier links to. Most of the Chinese deep forest is not linked from anywhere the crawler has
been: it is indexed by search engines, sits behind JavaScript shells (聚宽/优矿/米筐 communities),
or lives on platforms with their own APIs (Bilibili, Gitee, 掘金, 微信 via 搜狗). This miner
reaches those by ROUTE -- search-engine `site:` queries for grounds that refuse direct fetches
(知乎 403, CSDN timeouts, 雪球 WAF), platform APIs where they exist, a rendered fetch where a
shell hides the listing -- and then hands every URL it finds to the crawler's frontier, so the
forest it opens keeps being walked after this run ends.

WHAT IT KEEPS. Sentences that name a market quantity, a direction and a horizon
(`libs.research.mechanism_claims`), verbatim, with the instrument mapped to its MT5 analogue or
marked as a mechanism-class transfer, the story's own stated numbers attached as evidence ABOUT
THE STORY, and a provenance line. Every claim becomes a deepening task of kind `story_mechanism`;
the worker seat extracts an exact recipe or rejects; nothing bypasses the compiler or the gates.
A dubious trader story is still a testable mechanism -- that is the principal's point -- and the
gauntlet, not the miner, decides what it was worth.

EVERY GROUND RECORDS ITS OWN STATUS, re-measured each run. Off the box the network is usually
absent; then the miner rebuilds the queue from its claims ledger and says so.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html as _html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_DESK / "side_channels"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.research import mechanism_claims as mc  # noqa: E402

SOURCE = "deep_forest"
KIND = "story_mechanism"
SOURCES = _DESK / "data" / "deep_forest_sources.json"
CLAIMS = _DESK / "data" / "deep_forest_claims.jsonl"
SEEN = _DESK / "data" / "deep_forest_seen.json"
REPORT = _DESK / "reports" / "DEEP_FOREST.json"
MAX_TASKS = 400
PAGE_FETCH_PER_QUERY = 3
DEEP_LINKS_PER_GROUND = 6
MIN_PAGE_TEXT = 1500
_UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
       "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
       "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8"}
GRADE = {"competition": "COMPETITION_RECORD", "interview": "INTERVIEW",
         "community": "COMMUNITY_POST", "forum": "COMMUNITY_POST", "qa": "COMMUNITY_POST",
         "social": "COMMUNITY_POST", "blog": "COMMUNITY_POST", "code": "CODE",
         "video": "VIDEO_METADATA", "academic": "PAPER"}


# ------------------------------------------------------------------------------- fetching
def _http(url: str, *, timeout: float = 20.0, referer: str = "") -> str:
    req = urllib.request.Request(url, headers={**_UA, **({"Referer": referer} if referer else {})})
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        body: str = fh.read(2_000_000).decode("utf-8", errors="replace")
    return body


def html_text(page: str) -> str:
    """Visible text of a page: scripts and styles dropped, tags removed, entities decoded."""
    s = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", page or "")
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = _html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def html_links(page: str, base: str) -> list[tuple[str, str]]:
    out = []
    for m in re.finditer(r'(?is)<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page or ""):
        href, anchor = m.group(1), html_text(m.group(2))[:120]
        if href.startswith(("javascript:", "mailto:", "#")):
            continue
        out.append((urljoin(base, href).split("#")[0], anchor))
    return out[:400]


def _title(page: str) -> str:
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", page or "")
    return html_text(m.group(1))[:160] if m else ""


# --------------------------------------------------------------------------- search routes
def parse_bing(page: str) -> list[dict[str, str]]:
    rows = []
    for block in re.split(r'<li class="b_algo"', page or "")[1:]:
        m = re.search(r'(?is)<h2>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block)
        if not m:
            continue
        snip = re.search(r'(?is)<p[^>]*>(.*?)</p>', block)
        rows.append({"url": _html.unescape(m.group(1)), "title": html_text(m.group(2)),
                     "snippet": html_text(snip.group(1)) if snip else ""})
    return rows


def parse_ddg(page: str) -> list[dict[str, str]]:
    rows = []
    for m in re.finditer(r'(?is)<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
                         r'(.*?)(?=<a[^>]*class="result__a"|$)', page or ""):
        href = _html.unescape(m.group(1))
        if "uddg=" in href:
            q = parse_qs(urlparse(href).query).get("uddg") or []
            href = unquote(q[0]) if q else href
        snip = re.search(r'(?is)class="result__snippet"[^>]*>(.*?)</a>', m.group(3))
        rows.append({"url": href, "title": html_text(m.group(2)),
                     "snippet": html_text(snip.group(1)) if snip else ""})
    return rows


def bing_search(query: str, site: str = "") -> tuple[list[dict[str, str]], str | None]:
    q = f"site:{site} {query}" if site else query
    url = f"https://www.bing.com/search?q={quote(q)}&setlang=zh-CN&cc=CN&count=20"
    try:
        page = _http(url, referer="https://www.bing.com/")
    except Exception as exc:
        return [], f"{type(exc).__name__}: {str(exc)[:120]}"
    rows = parse_bing(page)
    if not rows:
        return [], (f"bing returned no parseable results ({len(page)} bytes -- an anti-bot "
                    "shell or a layout change, not an empty forest)")
    return rows, None


def ddg_search(query: str, site: str = "") -> tuple[list[dict[str, str]], str | None]:
    q = f"site:{site} {query}" if site else query
    url = f"https://html.duckduckgo.com/html/?q={quote(q)}&kl=cn-zh"
    try:
        page = _http(url, referer="https://duckduckgo.com/")
    except Exception as exc:
        return [], f"{type(exc).__name__}: {str(exc)[:120]}"
    rows = parse_ddg(page)
    if not rows:
        return [], f"duckduckgo returned no parseable results ({len(page)} bytes)"
    return rows, None


def engine_search(query: str, site: str = "") -> tuple[list[dict[str, str]], str, list[str]]:
    """Bing first, DuckDuckGo second. (rows, engine, errors)."""
    errs = []
    for name, fn in (("bing", bing_search), ("duckduckgo", ddg_search)):
        rows, err = fn(query, site)
        if rows:
            return rows, name, errs
        errs.append(f"{name}: {err}")
        time.sleep(1.0)
    return [], "", errs


# --------------------------------------------------------------------------- platform routes
def gitee_search(query: str) -> tuple[list[dict[str, Any]], str | None]:
    url = (f"https://gitee.com/api/v5/search/repositories?q={quote(query)}"
           "&sort=stars_count&order=desc&per_page=20")
    try:
        rows = json.loads(_http(url))
    except Exception as exc:
        return [], f"{type(exc).__name__}: {str(exc)[:120]}"
    if not isinstance(rows, list):
        return [], "gitee search did not return a list"
    return [{"full": r.get("full_name") or r.get("path_with_namespace") or "",
             "url": r.get("html_url") or "", "description": r.get("description") or "",
             "license": (r.get("license") or "NONE"), "stars": r.get("stargazers_count"),
             "pushed": r.get("pushed_at") or r.get("updated_at")} for r in rows
            if isinstance(r, dict)], None


def gitee_readme(full: str) -> str:
    try:
        doc = json.loads(_http(f"https://gitee.com/api/v5/repos/{full}/readme"))
        return base64.b64decode(doc.get("content", "")).decode("utf-8", errors="replace")
    except Exception:
        return ""


def bilibili_transcript(bvid: str) -> tuple[str, str | None]:
    """Public subtitles via view -> cid -> player/v2. Empty with a reason when there are none."""
    try:
        view = json.loads(_http(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"))
        data = view.get("data") or {}
        cid = data.get("cid")
        pl = json.loads(_http(f"https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}"))
        subs = ((pl.get("data") or {}).get("subtitle") or {}).get("subtitles") or []
        if not subs:
            return "", "no public subtitle track (login-gated on most videos)"
        url = str(subs[0].get("subtitle_url") or "")
        url = "https:" + url if url.startswith("//") else url
        body = json.loads(_http(url))
        return " ".join(str(x.get("content", "")) for x in body.get("body", [])), None
    except Exception as exc:
        return "", f"{type(exc).__name__}: {str(exc)[:120]}"


# ------------------------------------------------------------------------------- ledgers
def _load_sources() -> dict[str, Any]:
    try:
        return json.loads(SOURCES.read_text("utf-8"))
    except (OSError, ValueError):
        return {"grounds": []}


def _load_seen() -> dict[str, Any]:
    try:
        d = json.loads(SEEN.read_text("utf-8"))
        return d if isinstance(d, dict) else {"claims": [], "urls": []}
    except (OSError, ValueError):
        return {"claims": [], "urls": []}


def _save_seen(seen: dict[str, Any]) -> None:
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps({"claims": sorted(set(seen.get("claims") or []))[-50_000:],
                                "urls": sorted(set(seen.get("urls") or []))[-50_000:],
                                "updated_utc": datetime.now(tz=UTC).isoformat()}), "utf-8")


def _claims_rows() -> list[dict[str, Any]]:
    try:
        return [json.loads(ln) for ln in CLAIMS.read_text("utf-8").splitlines() if ln.strip()]
    except (OSError, ValueError):
        return []


def _universe() -> set[str]:
    try:
        meta = json.loads((_DESK / "data" / "universe" / "universe.json").read_text("utf-8"))
        return {str(k).upper() for k in meta}
    except (OSError, ValueError):
        return set()


# ------------------------------------------------------------------------------- the run
class _Run:
    def __init__(self, budget_s: float, fetch: bool, only: set[str] | None) -> None:
        self.budget_s, self.fetch, self.only = budget_s, fetch, only
        self.started = time.monotonic()
        self.seen = _load_seen()
        self.seen_claims = set(self.seen.get("claims") or [])
        self.seen_urls = set(self.seen.get("urls") or [])
        self.universe = _universe()
        self.new: list[dict[str, Any]] = []
        self.status: list[dict[str, Any]] = []
        self.frontier: list[tuple[str, str]] = []
        self.counts = {"queries": 0, "pages": 0, "transcripts": 0, "rendered": 0,
                       "dropped_venue": 0, "claims_seen_before": 0, "net_failures": 0}
        self.network: bool | None = None
        self.render_used = 0

    def over(self) -> bool:
        return time.monotonic() - self.started > self.budget_s

    def _net_ok(self) -> bool:
        """After three straight transport failures the box has no network; stop trying."""
        return self.fetch and self.network is not False

    def _note_net(self, ok: bool) -> None:
        if ok:
            self.network = True
            self.counts["net_failures"] = 0
        else:
            self.counts["net_failures"] += 1
            if self.network is None and self.counts["net_failures"] >= 3:
                self.network = False

    def page(self, url: str, referer: str = "") -> str:
        if not self._net_ok():
            return ""
        try:
            body = _http(url, referer=referer)
            self._note_net(True)
            self.counts["pages"] += 1
            return body
        except urllib.error.HTTPError as exc:
            self._note_net(True)
            self.status.append({"url": url, "http": exc.code})
            return ""
        except Exception as exc:
            self._note_net(False)
            self.status.append({"url": url, "error": f"{type(exc).__name__}: {str(exc)[:80]}"})
            return ""

    def rendered(self, url: str) -> str:
        try:
            from libs.data.render_fetch import render
            page, err = render(url, timeout_s=25.0, lang="zh-CN")
        except Exception as exc:
            page, err = "", f"{type(exc).__name__}: {str(exc)[:80]}"
        if err:
            self.status.append({"url": url, "render": err[:120]})
            return ""
        self.counts["rendered"] += 1
        return page

    def take(self, text: str, *, ground: dict[str, Any], url: str, title: str,
             route: str, grade: str | None = None, extra: dict[str, Any] | None = None) -> int:
        claims, dropped = mc.extract_claims_with_drops(text, universe=self.universe or None)
        self.counts["dropped_venue"] += dropped
        n = 0
        for c in claims:
            if c["claim_hash"] in self.seen_claims:
                self.counts["claims_seen_before"] += 1
                continue
            self.seen_claims.add(c["claim_hash"])
            row = {**c, "ground": ground.get("name"), "ground_kind": ground.get("kind"),
                   "route": route, "url": url, "title": title[:160],
                   "evidence_grade": grade or GRADE.get(str(ground.get("kind")), "COMMUNITY_POST"),
                   "fetched_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                   "score": mc.claim_score(c), **(extra or {})}
            self.new.append(row)
            n += 1
            self._provenance(row)
        return n

    def _provenance(self, row: dict[str, Any]) -> None:
        try:
            from libs.data.datahub import record_mined_source
            record_mined_source(repo=str(row.get("ground")), url=str(row.get("url")),
                                commit=str(row.get("fetched_utc")),
                                license_=str(row.get("license") or "WEB-PUBLIC"),
                                file=str(row.get("route")), mechanism=str(row["claim"])[:200],
                                code_copied=False, commercial_restriction=True)
        except Exception:
            pass

    def follow(self, url: str, anchor: str, via: str) -> None:
        if url in self.seen_urls:
            return
        self.frontier.append((url, via))
        self.seen_urls.add(url)

    # ---------------------------------------------------------------- routes per ground
    def ground_http(self, g: dict[str, Any], *, render_first: bool = False) -> dict[str, Any]:
        urls = [g.get("url"), *list(g.get("alt") or [])]
        got = claims = pages = 0
        for u in [x for x in urls if x]:
            if self.over():
                break
            page = self.page(str(u))
            text = html_text(page)
            if (len(text) < MIN_PAGE_TEXT or render_first) and self._net_ok():
                rp = self.rendered(str(u))
                if rp:
                    page, text = rp, html_text(rp)
            if not text:
                continue
            got += 1
            claims += self.take(text, ground=g, url=str(u), title=_title(page) or str(u),
                                route=g.get("route", "http"))
            host = urlparse(str(u)).netloc
            deep = 0
            for href, anchor in html_links(page, str(u)):
                if urlparse(href).netloc != host:
                    continue
                if self._worth(href, anchor):
                    self.follow(href, anchor, via=f"{SOURCE}:{g.get('name')}")
                    if deep < DEEP_LINKS_PER_GROUND and not self.over() and href not in urls:
                        sub = self.page(href, referer=str(u))
                        st = html_text(sub)
                        if len(st) >= MIN_PAGE_TEXT:
                            pages += 1
                            deep += 1
                            claims += self.take(st, ground=g, url=href,
                                                title=_title(sub) or anchor, route="http:deep")
                        time.sleep(1.0)
        return {"fetched": got, "deep_pages": pages, "claims": claims}

    def ground_search(self, g: dict[str, Any]) -> dict[str, Any]:
        site = str(g.get("site") or "")
        claims = pages = 0
        engines: dict[str, int] = {}
        errors: list[str] = []
        for q in g.get("queries") or []:
            if self.over() or not self._net_ok():
                break
            self.counts["queries"] += 1
            rows, engine, errs = engine_search(str(q), site)
            self._note_net(bool(rows) or any("HTTPError" in e for e in errs))
            errors.extend(errs[:2])
            if not rows:
                continue
            engines[engine] = engines.get(engine, 0) + 1
            fetched = 0
            for r in rows:
                url = r.get("url") or ""
                text = f"{r.get('title', '')}. {r.get('snippet', '')}"
                claims += self.take(text, ground=g, url=url, title=r.get("title", ""),
                                    route=f"search:{engine}")
                self.follow(url, r.get("title", ""), via=f"{SOURCE}:{g.get('name')}")
                if fetched < PAGE_FETCH_PER_QUERY and not self.over():
                    body = html_text(self.page(url))
                    if len(body) >= MIN_PAGE_TEXT:
                        fetched += 1
                        pages += 1
                        claims += self.take(body, ground=g, url=url, title=r.get("title", ""),
                                            route=f"search:{engine}:page")
                    time.sleep(1.0)
            time.sleep(1.5)
        return {"queries": len(g.get("queries") or []), "engines": engines, "pages": pages,
                "claims": claims, "errors": errors[:4]}

    def ground_cn_api(self, g: dict[str, Any]) -> dict[str, Any]:
        from libs.data import cn_sources
        fn = cn_sources.juejin if g.get("route") == "juejin" else cn_sources.sogou_weixin
        claims = 0
        errors: list[str] = []
        for q in g.get("queries") or []:
            if self.over() or not self._net_ok():
                break
            self.counts["queries"] += 1
            arts, err = fn(str(q))
            self._note_net(err is None or "HTTPError" in str(err))
            if err:
                errors.append(str(err)[:100])
            for a in arts:
                claims += self.take(a.searchable, ground=g, url=a.url, title=a.title,
                                    route=str(g.get("route")))
                self.follow(a.url, a.title, via=f"{SOURCE}:{g.get('name')}")
            time.sleep(1.2)
        return {"queries": len(g.get("queries") or []), "claims": claims, "errors": errors[:4]}

    def ground_bilibili(self, g: dict[str, Any]) -> dict[str, Any]:
        from libs.data import bilibili
        try:
            from libs.research.video_triage import score_title
        except Exception:
            def score_title(text: str) -> tuple[float, list[str]]:  # type: ignore[misc]
                return 0.0, []
        claims = 0
        videos: list[Any] = []
        errors: list[str] = []
        for q in g.get("queries") or []:
            if self.over() or not self._net_ok():
                break
            self.counts["queries"] += 1
            vids, err = bilibili.search(str(q))
            self._note_net(err is None or "code=" in str(err) or "SOFT" in str(err))
            if err:
                errors.append(str(err)[:100])
                if "SOFT REFUSAL" in str(err):
                    break
            for v in vids:
                claims += self.take(v.searchable, ground=g, url=v.url, title=v.title,
                                    route="bilibili:metadata")
                self.follow(v.url, v.title, via=f"{SOURCE}:{g.get('name')}")
            videos.extend(vids)
            time.sleep(0.5)
        ranked = sorted({v.bvid: v for v in videos}.values(),
                        key=lambda v: -score_title(v.searchable)[0])
        n_tr = 0
        tr_err: list[str] = []
        for v in ranked[: int(g.get("transcripts") or 0)]:
            if self.over() or not self._net_ok():
                break
            text, err = bilibili_transcript(v.bvid)
            if err:
                tr_err.append(f"{v.bvid}: {err}")
                continue
            n_tr += 1
            self.counts["transcripts"] += 1
            claims += self.take(text, ground=g, url=v.url, title=v.title,
                                route="bilibili:transcript", grade="VIDEO_TRANSCRIPT")
            time.sleep(0.5)
        return {"queries": len(g.get("queries") or []), "videos": len(videos),
                "transcripts": n_tr, "claims": claims, "errors": (errors + tr_err)[:4]}

    def ground_gitee(self, g: dict[str, Any]) -> dict[str, Any]:
        try:
            from libs.data.datahub import copy_allowed
        except Exception:
            def copy_allowed(lic: str) -> bool:                  # type: ignore[misc]
                return False
        claims = repos = 0
        errors: list[str] = []
        seen_repo: set[str] = set()
        for q in g.get("queries") or []:
            if self.over() or not self._net_ok():
                break
            self.counts["queries"] += 1
            rows, err = gitee_search(str(q))
            self._note_net(err is None or "HTTPError" in str(err))
            if err:
                errors.append(err[:100])
                continue
            for r in rows:
                full = str(r.get("full") or "")
                if not full or full in seen_repo or self.over():
                    continue
                seen_repo.add(full)
                repos += 1
                readme = gitee_readme(full)
                text = f"{r.get('description', '')}\n{readme}"
                claims += self.take(text, ground=g, url=str(r.get("url")), title=full,
                                    route="gitee:readme", grade="CODE",
                                    extra={"license": r.get("license"), "stars": r.get("stars"),
                                           "copy_allowed": copy_allowed(str(r.get("license")))})
                self.follow(str(r.get("url")), full, via=f"{SOURCE}:{g.get('name')}")
                time.sleep(0.5)
        return {"queries": len(g.get("queries") or []), "repos": repos, "claims": claims,
                "errors": errors[:4]}

    @staticmethod
    def _worth(url: str, anchor: str) -> bool:
        try:
            import world_frontier as wf
            return bool(wf.worth_following(url, anchor))
        except Exception:
            return bool(mc.is_cjk(anchor) or "trad" in url.lower())

    def work(self, g: dict[str, Any]) -> None:
        name, route = str(g.get("name")), str(g.get("route") or "http")
        row: dict[str, Any] = {"ground": name, "route": route, "kind": g.get("kind")}
        if self.only and name not in self.only and route not in self.only:
            return
        if route == "unreachable":
            self.status.append({**row, "status": "UNREACHABLE", "why": g.get("why")})
            return
        if not self.fetch:
            self.status.append({**row, "status": "SKIPPED", "why": "--no-fetch"})
            return
        if not self._net_ok():
            self.status.append({**row, "status": "NO_NETWORK",
                                "why": "three straight transport failures on this box"})
            return
        try:
            if route == "http":
                out = self.ground_http(g)
            elif route == "render":
                out = self.ground_http(g, render_first=True)
            elif route == "search":
                out = self.ground_search(g)
            elif route in ("juejin", "sogou"):
                out = self.ground_cn_api(g)
            elif route == "bilibili":
                out = self.ground_bilibili(g)
            elif route == "gitee":
                out = self.ground_gitee(g)
            else:
                out = {"error": f"unknown route {route}"}
        except Exception as exc:
            out = {"error": f"{type(exc).__name__}: {str(exc)[:120]}"}
        n_claims = int(out.get("claims") or 0)
        status = ("PRODUCTIVE" if n_claims else
                  ("REACHED_NO_CLAIMS" if (out.get("fetched") or out.get("engines")
                                           or out.get("videos") or out.get("repos"))
                   else "BLOCKED"))
        self.status.append({**row, "status": status, **out})


def _feed_frontier(urls: list[tuple[str, str]]) -> int:
    if not urls:
        return 0
    try:
        import world_frontier as wf
        sources = wf.load()
        added = 0
        # EVERY URL A MECHANISM QUERY SURFACED IS GROUND. The vocabulary filter the crawler
        # applies to anchors would reject a Chinese article URL that carries no Latin trading
        # word; the query that found it is the evidence it is worth a fetch, and the frontier's
        # yield ranking charges it forever if that turns out wrong.
        for url, via in urls:
            if url.startswith(("http://", "https://")):
                added += int(wf.add(sources, url, via=via, lang="zh"))
        wf.save(sources, note=f"{SOURCE} {datetime.now(tz=UTC):%Y-%m-%dT%H:%MZ}")
        return added
    except Exception:
        return 0


def _task(row: dict[str, Any]) -> dict[str, Any]:
    inst = row.get("instruments") or {}
    perf = row.get("claimed_performance") or {}
    desc = (f"CLAIM ({row.get('lang')}, {row.get('evidence_grade')}): \"{row['claim']}\". "
            f"MT5 analogues: {inst.get('analogues') or 'none'}"
            + (f"; transfer-only: {inst.get('transfer_only')}" if inst.get("transfer_only") else "")
            + (" (instrument inherited from the document)" if row.get("instrument_from_context")
               else "")
            + (f". Story's own numbers: {perf}" if perf else "")
            + f". Provenance: {row.get('ground')} via {row.get('route')} at "
              f"{row.get('fetched_utc')}, {row.get('url')}. Extract the exact mechanism as an "
              "MT5 family and parameters if the text states one; otherwise reject with why. "
              "Concept only -- never copy code; stated performance is not evidence.")
    return {"source": SOURCE, "kind": KIND,
            "title": f"{row.get('ground')}: {row['claim'][:90]}",
            "description": desc, "url": row.get("url"),
            "symbols": list(inst.get("analogues") or []),
            "mechanism_tags": list(row.get("quantities") or []), "lang": row.get("lang"),
            "evidence_grade": row.get("evidence_grade"), "claimed_performance": perf,
            "transfer_only": inst.get("transfer_only") or [], "claim_hash": row.get("claim_hash"),
            "score": row.get("score"), "status": None,
            "consumer": "deepening_worker (story_mechanism) -> miner_candidate_compiler "
                        "-> gauntlet"}


def build_tasks(rows: list[dict[str, Any]], *, decided: set[str] | None = None,
                cap: int = MAX_TASKS) -> list[dict[str, Any]]:
    """Every undecided claim, best first. Decided ones (the worker's ledger) are not re-asked."""
    try:
        from research.deepening_worker import task_id
    except Exception:
        def task_id(t: dict[str, Any]) -> str:                   # type: ignore[misc]
            return hashlib.sha256(f"{t.get('source')}|{t.get('url')}|{t.get('title')}"
                                  .encode()).hexdigest()[:16]
    by_hash: dict[str, dict[str, Any]] = {}
    for r in rows:
        if r.get("claim_hash"):
            by_hash[str(r["claim_hash"])] = r
    tasks = [_task(r) for r in by_hash.values()]
    if decided:
        tasks = [t for t in tasks if task_id(t) not in decided]
    tasks.sort(key=lambda t: -float(t.get("score") or 0.0))
    return tasks[:cap]


def run(budget_s: float = 900.0, fetch: bool = True, only: list[str] | None = None,
        write: bool = True) -> dict[str, Any]:
    cfg = _load_sources()
    r = _Run(budget_s, fetch, set(only or []) or None)
    for g in cfg.get("grounds") or []:
        if r.over():
            r.status.append({"ground": g.get("name"), "status": "BUDGET_EXHAUSTED"})
            continue
        r.work(g)
    if write and r.new:
        CLAIMS.parent.mkdir(parents=True, exist_ok=True)
        with CLAIMS.open("a", encoding="utf-8") as fh:
            for row in r.new:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    frontier_added = _feed_frontier(r.frontier) if write else 0
    all_rows = _claims_rows() if write else list(r.new)
    try:
        from research.deepening_worker import worked_ids
        decided = worked_ids()
    except Exception:
        decided = set()
    tasks = build_tasks(all_rows, decided=decided)
    if write:
        r.seen["claims"] = list(r.seen_claims)
        r.seen["urls"] = list(r.seen_urls)
        _save_seen(r.seen)
        if tasks:
            try:
                from research.regime_coverage import _merge_into_queue
                _merge_into_queue(tasks, source=SOURCE)
            except Exception:
                pass
    grounds = [s for s in r.status if "ground" in s]
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
           "budget_s": budget_s, "elapsed_s": round(time.monotonic() - r.started, 1),
           "network": r.network, "fetch": fetch, "grounds": grounds,
           "productive": sum(1 for s in grounds if s.get("status") == "PRODUCTIVE"),
           "blocked": [s.get("ground") for s in grounds
                       if s.get("status") in ("BLOCKED", "NO_NETWORK", "UNREACHABLE")],
           "counts": r.counts, "claims_new": len(r.new), "claims_total": len(all_rows),
           "tasks_queued": len(tasks), "frontier_added": frontier_added,
           "fetch_notes": [s for s in r.status if "url" in s][:40],
           "top_claims": [{k: t.get(k) for k in ("title", "symbols", "evidence_grade",
                                                 "claimed_performance", "score", "url")}
                          for t in tasks[:12]],
           "loop": ("Discover (search/platform routes) -> Extract (bilingual claims) -> queue "
                    "story_mechanism -> worker Reimplement -> compiler -> gauntlet -> allocator; "
                    "URLs found feed the world crawler frontier")}
    if write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str), "utf-8")
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--budget-s", type=float, default=900.0)
    ap.add_argument("--no-fetch", action="store_true", help="rebuild the queue from the ledger")
    ap.add_argument("--only", action="append", default=None,
                    help="ground name or route to work (repeatable)")
    a = ap.parse_args()
    d = run(budget_s=a.budget_s, fetch=not a.no_fetch, only=a.only)
    print(f"DEEP FOREST  network={d['network']} productive={d['productive']} "
          f"claims_new={d['claims_new']} total={d['claims_total']} tasks={d['tasks_queued']} "
          f"frontier+={d['frontier_added']} counts={d['counts']}")
    for g in d["grounds"]:
        print(f"  {g.get('ground')!s:34s} {g.get('route')!s:9s} {g.get('status')} "
              f"claims={g.get('claims', 0)} {g.get('errors') or g.get('why') or ''}")
    print(f"written: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
