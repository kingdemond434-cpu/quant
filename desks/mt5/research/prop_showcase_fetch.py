"""Prop-firm showcase harvest: firm sitemaps -> story pages -> claim rows.

The fetching half of prop_showcase_miner (see its header for the whole pipeline). Public pages
only: robots.txt is consulted per host and an unreadable or walled one means the host is not
fetched; walls (401/402/403/429) are counted and never crossed; no login, no cookies. Raw text
is vaulted under the gitignored INTEL directory and never leaves the box.
"""
from __future__ import annotations

import gzip
import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from prop_showcase_lexicon import extract

DESK = Path(__file__).resolve().parents[1]
SOURCE = "prop_showcase_story"
INTEL = DESK / "data" / "intelligence" / "prop_showcase"
CLAIMS = DESK / "data" / "prop_showcase_claims.jsonl"
SEEN = INTEL / "seen.json"
AGENT = "quant-research-reader/1.0 (+public pages only)"
DELAY_S = 3.0
MAX_NEW_PER_FIRM = 40
MAX_SITEMAPS = 12

#: Public story ground per firm. `paths` keeps the sitemap to its blog/news trees; `slug` picks
#: trader stories and strategy write-ups out of them. Firms are MT5/CFD or futures (Topstep,
#: Apex: their futures stories map to the CFD on the same underlying).
FIRMS: dict[str, dict[str, Any]] = {
    "ftmo": {"home": "https://ftmo.com", "paths": ("/blog/", "/en/blog/")},
    "the5ers": {"home": "https://the5ers.com", "paths": ("/blog", "/trader", "/success")},
    "fundednext": {"home": "https://fundednext.com", "paths": ("/blog", "/success")},
    "topstep": {"home": "https://www.topstep.com", "paths": ("/blog", "/trader")},
    "e8": {"home": "https://e8markets.com", "paths": ("/blog", "/news")},
    "fxify": {"home": "https://fxify.com", "paths": ("/blog", "/news")},
    "fundingpips": {"home": "https://fundingpips.com", "paths": ("/blog",)},
    "alpha_capital": {"home": "https://alphacapitalgroup.uk", "paths": ("/blog", "/news")},
    "apex": {"home": "https://apextraderfunding.com", "paths": ("/blog",)},
    "fintokei": {"home": "https://www.fintokei.com", "paths": ("/blog", "/jp/blog")},
}
#: THE TERMS GATE, FAIL CLOSED (same vocabulary as book_forensics.TERMS / alt_proxies.TERMS).
#: A firm's site is fetched ONLY when its verdict is `confirmed` AND TERMS_EVIDENCE holds the
#: terms URL and a verbatim permitting quote a human recorded. Robots.txt is a second gate, not
#: a substitute. An unlisted firm is `to_confirm`. No verdict here is `confirmed` yet: nobody
#: has read these terms, so nothing is fetched and the report says BLOCKED_ON_TERMS.
_UNREAD = "site terms of use not read; no automated-access ruling recorded (2026-11-14)"
TERMS: dict[str, tuple[str, str]] = dict.fromkeys(FIRMS, ("to_confirm", _UNREAD))
TERMS_EVIDENCE: dict[str, dict[str, str]] = {}
TERMS_VALUES = ("confirmed", "to_confirm", "refused")


def terms_ok(firm: str, terms: dict[str, tuple[str, str]] | None = None,
             evidence: dict[str, dict[str, str]] | None = None) -> bool:
    """True only for a `confirmed` verdict backed by a recorded terms URL and quote."""
    verdict = (TERMS if terms is None else terms).get(firm, ("to_confirm", ""))[0]
    ev = (TERMS_EVIDENCE if evidence is None else evidence).get(firm, {})
    return verdict == "confirmed" and bool(ev.get("url")) and bool(ev.get("quote"))


STORY_SLUG = re.compile(
    r"(trader|scalp|secur|earn|reward|payout|interview|stor(y|ies)|spotlight|strateg|funded|"
    r"success|journey|profit|withdraw|how-[a-z]+-[a-z]+-)", re.I)


# ------------------------------------------------------------------------------- harvest
class _Fetcher:
    """Polite GET. Robots consulted per host; an unreadable or walled robots.txt (0, 401, 402,
    403, 429, 5xx) means the host is not fetched at all. Spacing per host is
    max(robots Crawl-delay, DELAY_S). A redirect to another host is refused; a same-host
    redirect is re-checked against robots. No cookies, no retries on a wall."""

    WALLS = (401, 402, 403, 429)

    def __init__(self, delay_s: float = DELAY_S) -> None:
        self.delay_s = delay_s
        self.robots: dict[str, Any] = {}
        self.last: dict[str, float] = {}
        self.log: dict[str, int] = {}
        #: Outcome of the last get(): "ok", "disallowed", "permanent" (4xx incl. walls) or
        #: "transient" (0 / 5xx), so the caller marks a URL seen only when it should be.
        self.outcome = ""

    def _count(self, k: str) -> None:
        self.log[k] = self.log.get(k, 0) + 1

    def _spacing(self, host: str) -> float:
        rp = self.robots.get(host)
        cd = None
        if rp is not None:
            try:
                cd = rp.crawl_delay(AGENT)
            except Exception:
                cd = None
        return max(self.delay_s, float(cd or 0.0))

    def _raw(self, url: str, limit: int = 3_000_000) -> tuple[int, bytes, str]:
        """(status, body, final_url) through polite_fetch (certifi trust store, charset) with
        retries=0, so a 429 stays a counted wall, never a retry loop."""
        host = urllib.parse.urlsplit(url).netloc.lower()
        wait = self._spacing(host) - (time.monotonic() - self.last.get(host, -1e9))
        if wait > 0:
            time.sleep(wait)
        self.last[host] = time.monotonic()
        try:
            from libs.data import polite_fetch as pf
        except Exception:
            pf = None
        if pf is not None:
            r = pf.get(url, headers={"User-Agent": AGENT}, retries=0, max_bytes=limit,
                       leg=SOURCE)
            return (int(r.status or 0), (r.text or "").encode("utf-8"),
                    str(r.final_url or url))
        req = urllib.request.Request(url, headers={"User-Agent": AGENT})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read(limit)
                if resp.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                return int(resp.status), body, str(resp.geturl() or url)
        except urllib.error.HTTPError as exc:
            return int(exc.code), b"", url
        except Exception:
            return 0, b"", url

    def robot(self, url: str) -> Any:
        parts = urllib.parse.urlsplit(url)
        host = parts.netloc.lower()
        if host not in self.robots:
            from urllib.robotparser import RobotFileParser
            code, body, final = self._raw(f"{parts.scheme}://{host}/robots.txt")
            if (code in self.WALLS or code == 0 or code >= 500
                    or urllib.parse.urlsplit(final).netloc.lower() != host):
                self.robots[host] = None           # unreadable or walled: fetch nothing here
                self._count("robots_refused")
            else:
                rp = RobotFileParser()
                rp.parse(body.decode("utf-8", "replace").splitlines() if code == 200 else [])
                self.robots[host] = rp
        return self.robots[host]

    def get(self, url: str) -> bytes | None:
        host = urllib.parse.urlsplit(url).netloc.lower()
        rp = self.robot(url)
        if rp is None or not rp.can_fetch(AGENT, url):
            self._count("robots_disallowed")
            self.outcome = "disallowed"
            return None
        code, body, final = self._raw(url)
        if code in self.WALLS:
            self._count(f"walled_{code}")          # a wall is a counted absence, never crossed
            self.outcome = "transient" if code == 429 else "permanent"
            return None
        if code != 200:
            self._count(f"http_{code}")
            self.outcome = "transient" if code == 0 or code >= 500 else "permanent"
            return None
        if urllib.parse.urlsplit(final).netloc.lower() != host:
            self._count("cross_host_redirect_refused")
            self.outcome = "permanent"
            return None
        if final != url and not rp.can_fetch(AGENT, final):
            self._count("robots_disallowed_after_redirect")
            self.outcome = "disallowed"
            return None
        self._count("fetched")
        self.outcome = "ok"
        return body


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _sitemap_urls(f: _Fetcher, home: str) -> list[str]:
    rp = f.robot(home)
    if rp is None:
        return []
    maps = list(rp.site_maps() or []) or [home.rstrip("/") + "/sitemap.xml",
                                          home.rstrip("/") + "/sitemap_index.xml"]
    urls: list[str] = []
    seen_maps: set[str] = set()
    while maps and len(seen_maps) < MAX_SITEMAPS:
        m = maps.pop(0)
        if m in seen_maps:
            continue
        seen_maps.add(m)
        body = f.get(m)
        if not body:
            continue
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body.decode("utf-8", "replace"))
        for loc in locs:
            loc = html.unescape(loc)
            if loc.endswith(".xml") or ".xml?" in loc:
                if re.search(r"post|blog|news|stor|article|page", loc, re.I):
                    maps.append(loc)
            else:
                urls.append(loc)
    return urls


def _story_urls(urls: list[str], paths: tuple[str, ...]) -> list[str]:
    out = []
    for u in urls:
        p = urllib.parse.urlsplit(u).path
        if any(p.startswith(x) for x in paths) and STORY_SLUG.search(p.rsplit("/", 2)[-2]
                                                                     if p.endswith("/")
                                                                     else p.rsplit("/", 1)[-1]):
            out.append(u)
    return out


def _text(body: bytes) -> tuple[str, str | None, str]:
    """(visible text, published date if the page states one, title)."""
    s = body.decode("utf-8", "replace")
    pub = None
    m = re.search(r"(?:article:published_time|datePublished)[\"']?[^>]{0,40}?(?:content=|:)"
                  r"\s*[\"']([^\"']+)", s)
    if m:
        pub = m.group(1)[:25]
    tm = re.search(r"<title[^>]*>(.*?)</title>", s, re.S | re.I)
    title = html.unescape(re.sub(r"\s+", " ", tm.group(1))).strip()[:200] if tm else ""
    s = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip(), pub, title


def _load_seen() -> dict[str, str]:
    try:
        return json.loads(SEEN.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def harvest(fetcher: _Fetcher | None = None, firms: dict[str, dict[str, Any]] | None = None,
            budget_s: float = 1500.0, terms: dict[str, tuple[str, str]] | None = None,
            evidence: dict[str, dict[str, str]] | None = None) -> dict[str, Any]:
    """New stories -> claim rows appended to CLAIMS. Raw text vaulted on the box only.
    A firm without a confirmed terms verdict is not contacted at all (not even robots.txt)."""
    f = fetcher or _Fetcher()
    started = time.monotonic()
    seen = _load_seen()
    rep: dict[str, Any] = {"by_firm": {}}
    new_claims: list[dict[str, Any]] = []
    blocked: dict[str, str] = {}
    for firm, cfg in (firms or FIRMS).items():
        if not terms_ok(firm, terms, evidence):
            verdict, why = (TERMS if terms is None else terms).get(firm, ("to_confirm", _UNREAD))
            blocked[firm] = verdict if verdict != "confirmed" else "to_confirm"
            rep["by_firm"][firm] = {"skipped": "terms", "terms": blocked[firm], "why": why}
            continue
        if time.monotonic() - started > budget_s:
            rep["by_firm"][firm] = {"skipped": "budget"}
            continue
        urls = _sitemap_urls(f, cfg["home"])
        stories = [u for u in _story_urls(urls, cfg["paths"]) if u not in seen]
        row = {"sitemap_urls": len(urls), "story_urls_new": len(stories), "read": 0,
               "claims_with_mechanism": 0}
        for u in stories[:MAX_NEW_PER_FIRM]:
            if time.monotonic() - started > budget_s:
                break
            body = f.get(u)
            now = datetime.now(UTC).isoformat(timespec="seconds")
            if f.outcome != "transient":           # a 5xx/429/timeout is retried next pass
                seen[u] = now
            if not body:
                continue
            text, pub, title = _text(body)
            digest = hashlib.sha256(text.encode()).hexdigest()
            INTEL.mkdir(parents=True, exist_ok=True)
            vault = INTEL / f"{digest[:16]}.txt.gz"
            if not vault.exists():
                vault.write_bytes(gzip.compress(text.encode()))
            row["read"] += 1
            claim = {"firm": firm, "url": u, "title": title, "published_time": pub,
                     "available_time": now, "knowable_from": pub or now,
                     "text_sha256": digest, **extract(title + " " + text)}
            if claim["styles"] and claim["instruments"]:
                row["claims_with_mechanism"] += 1
            new_claims.append(claim)
        rep["by_firm"][firm] = row
    if new_claims:
        CLAIMS.parent.mkdir(parents=True, exist_ok=True)
        with CLAIMS.open("a", encoding="utf-8") as fh:
            for c in new_claims:
                fh.write(json.dumps(c, sort_keys=True) + "\n")
    INTEL.mkdir(parents=True, exist_ok=True)
    _write_atomic(SEEN, json.dumps(seen, indent=0))
    rep["fetch_log"] = f.log
    read = sum(int(r.get("read", 0)) for r in rep["by_firm"].values())
    pending = sum(int(r.get("story_urls_new", 0)) for r in rep["by_firm"].values())
    rep["harvest_status"] = ("MEASURED" if read or (f.log.get("fetched") and not pending) else
                             "UNMEASURED: nothing was fetched this pass (walls, robots or "
                             "network); zero new stories is not a finding")
    rep["terms_blocked"] = blocked
    if blocked and len(blocked) == len(rep["by_firm"]):
        rep["harvest_status"] = ("BLOCKED_ON_TERMS: no firm has a confirmed terms verdict in "
                                 "prop_showcase_fetch.TERMS / TERMS_EVIDENCE; nothing fetched")
    rep["new_claims"] = len(new_claims)
    return rep


def load_claims(path: Path | None = None) -> list[dict[str, Any]]:
    """Newest claim per URL."""
    best: dict[str, dict[str, Any]] = {}
    try:
        lines = (path or CLAIMS).read_text("utf-8").splitlines()
    except OSError:
        return []
    for ln in lines:
        try:
            c = json.loads(ln)
        except ValueError:
            continue
        if isinstance(c, dict) and c.get("url"):
            best[c["url"]] = c
    return list(best.values())
