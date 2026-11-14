"""Two depth miners for seed_miners: published research feeds, and GitHub repos read in depth.

Principal, 2026-11-10: GitHub mining must reach "trading bots, quantitative research
repositories, strategy code, issues, discussions and forks", and institutional mining must reach
"public hedge fund papers, market microstructure studies and published quantitative models" plus
"recently published strategies, code changes, research papers and emerging market anomalies".

MEASURED BEFORE THIS MODULE (live 18c9b2da5):
  * `github_topics` saved name, description and stars only. No README, no commit, no issue, no
    discussion and no fork of any repo was ever read.
  * `arxiv_qfin` read the 25 newest papers from 3 of arXiv's 9 q-fin categories, newest only, so
    a paper outside the newest 25 at the moment of the pass was never seen.
  * NBER, the Fed, the ECB and BIS working papers existed only as HTML grounds in
    deep_forest_sources.json, with no measured yield.

WHAT THIS ADDS, both registered in seed_miners.MINERS so they inherit its hourly clock:
  research_feeds  every feed in research_feeds.json (RSS 1.0/2.0 or Atom, parsed by element
                  local-name so one parser reads all three), plus all nine arXiv q-fin
                  categories: the newest page every pass AND one backfill page that walks the
                  archive deeper each pass, so the back catalogue is reached, not just the head.
  github_depth    for the trading repos github_topics has found: README (only when it changed),
                  new commits (code changes), new issues (pull requests skipped), the most-starred
                  forks, and discussions over GraphQL when a token is configured. Starred forks
                  join the pool, so the frontier grows by the repos the crowd chose to build on.

LEGITIMACY. Feeds are endpoints published for machines. GitHub is read through its documented
API inside its published rate limit: the budget is read from /rate_limit (which costs nothing)
and the pass stops at a floor, never retries a 403, never rotates identity. Without a token,
discussions are recorded UNMEASURED rather than scraped from HTML. No token is ever printed or
written: only whether one was present.

FAILURE IS VISIBLE. A feed that errors writes a fetch_error row and an rf_status entry; a feed
that answered and parsed nothing writes status "empty". Neither looks like a quiet source.
"""
from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as _ET

try:                                                    # hardened parser when installed
    from defusedxml import ElementTree as ET  # type: ignore[import-untyped,unused-ignore]
except ImportError:                                     # pragma: no cover - stdlib fallback
    ET = _ET  # type: ignore[misc,assignment,unused-ignore]

HERE = Path(__file__).resolve().parent
FEEDS_CONFIG = HERE / "research_feeds.json"
SEEN_CAP = 40_000

TRADING_TOPICS = frozenset({
    "mql5", "metatrader5", "forex-trading", "algorithmic-trading", "quantitative-finance",
    "quantitative-trading", "trading-bot",
})
GH_API = "https://api.github.com"
# Requests one repo visit costs on the REST quota: metadata, readme, commits, issues, forks.
GH_COST_PER_REPO = 5
GH_FLOOR_ANON, GH_FLOOR_TOKEN = 10, 500
GH_MAX_REPOS_ANON, GH_MAX_REPOS_TOKEN = 10, 80
FORK_POOL_MIN_STARS = 5
# Bounded state: the fork pool keeps its most-starred entries, the visit memory its most recent.
FORK_POOL_CAP, VISITED_CAP = 2_000, 5_000
# GraphQL has its own points budget; discussions stop below this many points.
GQL_FLOOR = 200
# Wall-clock budgets per pass, so one slow host can never hold the hourly sweep.
FEEDS_DEADLINE_S, GITHUB_DEADLINE_S = 600.0, 900.0
# An honest, generic client name (not a browser string). It names no person, account or
# repository: nothing about the owner is published to third-party hosts.
HONEST_UA = "research-feed-miner/1.0 (automated; RSS/Atom and public API reader)"
# Feeds are fetched only under a recorded terms verdict that permits it. A feed whose terms
# were never recorded is CLOSED and says so in rf_status: unknown is not permission.
OPEN_TERMS = frozenset({"open"})

# THE MT5 MANDATE (CLAUDE.md): crypto-exchange ground is never hunted. `trading-bot` and
# `algorithmic-trading` are dominated by exchange bots, so every repo and fork is screened on
# its name, description and topics before a single depth request is spent on it.
CRYPTO_RE = re.compile(
    r"ccxt|binance|bybit|okx|hyperliquid|freqtrade|hummingbot|crypto|defi\b|bitcoin|btc\b"
    r"|ethereum|\beth\b|solana|coinbase|kucoin|bitmex|deribit|uniswap|web3|altcoin|memecoin",
    re.IGNORECASE)


def is_crypto(*fields: Any) -> bool:
    """True when any field names crypto-exchange ground."""
    return any(CRYPTO_RE.search(str(f or "")) for f in fields)

Row = dict[str, Any]
RowFn = Callable[..., Row]


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _key(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _clean(text: str, limit: int = 1500) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


# ------------------------------------------------------------------------------ feed parsing
def parse_feed(xml_text: str) -> list[dict[str, str]]:
    """Entries of an RSS 1.0 (RDF), RSS 2.0 or Atom document, by element local-name.

    Matching on local-name is the point: BIS speeches were silent for 75 sweeps because a
    regex anchored on a literal `<item>` never met an RDF `<item rdf:about=...>`. Here every
    dialect is the same walk. A document declaring entities is refused outright.
    """
    head = (xml_text if isinstance(xml_text, str) else xml_text.decode("utf-8", "replace")).upper()
    if "<!DOCTYPE" in head or "<!ENTITY" in head:
        raise ValueError("feed carries a DOCTYPE or entity declaration; refused")
    root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    out: list[dict[str, str]] = []
    for el in root.iter():
        if _local(el.tag) not in ("item", "entry"):
            continue
        rec: dict[str, str] = {}
        authors: list[str] = []
        for ch in el:
            name, txt = _local(ch.tag), (ch.text or "").strip()
            if name == "title" and "title" not in rec:
                rec["title"] = _clean(txt, 300)
            elif name == "link":
                href = ch.attrib.get("href", "")
                rel = ch.attrib.get("rel", "alternate")
                if href and rel == "alternate" and "url" not in rec:
                    rec["url"] = href
                elif txt and "url" not in rec:
                    rec["url"] = txt
            elif name == "id" and txt.startswith("http") and "url" not in rec:
                rec["url"] = txt
            elif name in ("description", "summary", "abstract", "encoded", "content") \
                    and txt and len(txt) > len(rec.get("_raw", "")):
                rec["_raw"] = txt
            elif name in ("pubdate", "date", "published", "updated", "issued") \
                    and "published" not in rec and txt:
                rec["published"] = txt[:40]
            elif name in ("creator", "author"):
                who = txt or " ".join((g.text or "").strip() for g in ch if _local(g.tag) == "name")
                if who:
                    authors.append(_clean(who, 120))
            elif name == "primary_category":
                rec["category"] = ch.attrib.get("term", "")
        if not rec.get("title"):
            continue
        rec["text"] = _clean(rec.pop("_raw", ""))
        if authors:
            rec["authors"] = "; ".join(authors[:8])
        out.append(rec)
    return out


def load_feed_config(path: Path = FEEDS_CONFIG) -> dict[str, Any]:
    cfg: dict[str, Any] = json.loads(path.read_text("utf-8"))
    return cfg


def _arxiv_url(categories: list[str], start: int, size: int) -> str:
    query = "+OR+".join(f"cat:{c}" for c in categories)
    return (f"https://export.arxiv.org/api/query?search_query={query}"
            f"&sortBy=submittedDate&sortOrder=descending&start={start}&max_results={size}")


def mine_research_feeds(st: dict[str, Any], get_text: Callable[[str], str], row: RowFn,
                        config: dict[str, Any] | None = None,
                        sleep: Callable[[float], None] = time.sleep,
                        clock: Callable[[], float] = time.monotonic,
                        deadline_s: float = FEEDS_DEADLINE_S) -> list[Row]:
    """Every configured feed plus arXiv q-fin head and backfill. Mutates `st` in place."""
    cfg = config if config is not None else load_feed_config()
    t0 = clock()
    seen_list: list[str] = list(st.get("rf_seen", []))
    seen = set(seen_list)
    status: dict[str, Any] = st.setdefault("rf_status", {})
    out: list[Row] = []

    def take(feed: str, kind: str, institution: str, entries: list[dict[str, str]]) -> int:
        new = 0
        for e in entries:
            k = _key(e.get("url") or e["title"])
            if k in seen:
                continue
            seen.add(k)
            seen_list.append(k)
            new += 1
            extra = {f: e[f] for f in ("published", "authors", "category") if e.get(f)}
            out.append(row("research_feeds", kind, e["title"], e.get("url", ""),
                           e.get("text", ""), feed=feed, institution=institution, **extra))
        return new

    sources: list[tuple[str, str, str, str]] = []
    for f in cfg.get("feeds", []):
        if f.get("terms") not in OPEN_TERMS:
            status[f["name"]] = {"at": _now(), "status": "closed",
                                 "why": f"terms {f.get('terms') or 'unrecorded'}; fetched only "
                                        "once a permitting verdict is recorded",
                                 "url": f["url"]}
            continue
        sources.append((f["name"], f["url"], f.get("kind", "paper"), f.get("institution", "")))
    ax = cfg.get("arxiv") or {}
    if ax.get("categories") and ax.get("terms") not in OPEN_TERMS:
        status["arxiv_qfin"] = {"at": _now(), "status": "closed",
                                "why": f"terms {ax.get('terms') or 'unrecorded'}"}
    elif ax.get("categories"):
        size = int(ax.get("page_size", 100))
        depth = int(ax.get("backfill_depth", 20_000))
        back = int(st.get("rf_arxiv_back", size))
        if back >= depth:
            back = size
        sources.append(("arxiv_qfin_head", _arxiv_url(ax["categories"], 0, size),
                        "paper", "arXiv"))
        sources.append(("arxiv_qfin_backfill", _arxiv_url(ax["categories"], back, size),
                        "paper", "arXiv"))
    for i, (name, url, kind, inst) in enumerate(sources):
        if clock() - t0 > deadline_s:
            status[name] = {"at": _now(), "status": "deferred",
                            "why": f"pass deadline {deadline_s:.0f}s reached", "url": url}
            continue
        if name.startswith("arxiv") and i:
            sleep(3.0)                                  # arXiv API asks for 3 s between calls
        try:
            entries = parse_feed(get_text(url))
        except Exception as exc:
            status[name] = {"at": _now(), "status": "error", "error": str(exc)[:200], "url": url}
            out.append(row("research_feeds", "fetch_error", f"{name}: {str(exc)[:160]}", url,
                           needs_selector_work=True, feed=name))
            continue
        new = take(name, kind, inst, entries)
        status[name] = {"at": _now(), "status": "ok" if entries else "empty",
                        "items": len(entries), "new": new, "url": url}
        if name == "arxiv_qfin_backfill":           # advance from the page actually read
            st["rf_arxiv_back"] = back + size if entries else size
    st["rf_seen"] = seen_list[-SEEN_CAP:]
    return out


# ------------------------------------------------------------------------------ GitHub depth
class RateFloor(Exception):
    """The REST quota reached its floor; the pass stops here and resumes next hour."""


def github_token() -> str | None:
    """GITHUB_TOKEN from the environment only. No dotfile is read; absence is normal."""
    tok = os.environ.get("GITHUB_TOKEN", "").strip()
    return tok or None


def topic_repos(intel_dir: Path, max_files: int = 96) -> dict[str, int]:
    """Trading-topic repos github_topics has archived, with their latest star count."""
    files = sorted((intel_dir / "github_topics").glob("discoveries_*.json"))[-max_files:]
    repos: dict[str, int] = {}
    for f in files:
        try:
            rows = json.loads(f.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(rows, dict):
            rows = rows.get("discoveries", [])
        for r in rows if isinstance(rows, list) else []:
            if (isinstance(r, dict) and r.get("topic") in TRADING_TOPICS
                    and "/" in str(r.get("title"))
                    and not is_crypto(r.get("title"), r.get("text"), r.get("topics"))):
                repos[str(r["title"])] = int(r.get("stars") or 0)
    return repos


def _order(pool: dict[str, int], visited: dict[str, Any]) -> list[str]:
    """Never-read repos first, most-starred first; then the stalest visit first."""
    fresh = sorted((r for r in pool if r not in visited), key=lambda r: -pool[r])
    stale = sorted((r for r in pool if r in visited),
                   key=lambda r: str(visited[r].get("visited", "")))
    return fresh + stale


def _bound(st: dict[str, Any]) -> None:
    pool: dict[str, int] = st.get("gd_fork_pool", {})
    if len(pool) > FORK_POOL_CAP:
        st["gd_fork_pool"] = dict(sorted(pool.items(), key=lambda kv: -kv[1])[:FORK_POOL_CAP])
    seen: dict[str, Any] = st.get("gd_repos", {})
    if len(seen) > VISITED_CAP:
        keep = sorted(seen, key=lambda r: str(seen[r].get("visited", "")))[-VISITED_CAP:]
        st["gd_repos"] = {r: seen[r] for r in keep}


def mine_github_depth(st: dict[str, Any], http_get: Callable[..., Any], row: RowFn,
                      pool: dict[str, int], token: str | None,
                      clock: Callable[[], float] = time.monotonic,
                      deadline_s: float = GITHUB_DEADLINE_S) -> list[Row]:
    """Read README, new commits, new issues, starred forks and (with a token) discussions.

    `http_get(url, headers=..., timeout=...)` returns an object with `status_code`, `headers`,
    `json()`; tests pass a fake. Mutates `st` in place.
    """
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": HONEST_UA}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    floor = GH_FLOOR_TOKEN if token else GH_FLOOR_ANON
    visited: dict[str, Any] = st.setdefault("gd_repos", {})
    extra: dict[str, int] = st.setdefault("gd_fork_pool", {})
    status: dict[str, Any] = {"at": _now(), "token": bool(token), "repos_read": 0,
                              "discussions": "measured" if token else
                              "UNMEASURED: no GITHUB_TOKEN; discussions need GraphQL auth"}
    st["gd_status"] = status
    out: list[Row] = []
    t0 = clock()

    def stop(why: str) -> list[Row]:
        # A pass that read nothing says WHY in a row of its own, so the sweep never mistakes it
        # for a parser whose markup moved.
        status["stopped"] = why
        out.append(row("github_depth", "unmeasured", f"github_depth: {why}",
                       "https://api.github.com/rate_limit", why, needs_selector_work=False))
        return out

    full_pool = {r: n for r, n in {**extra, **pool}.items() if not is_crypto(r)}
    if not full_pool:
        return stop("no trading repos archived by github_topics yet")
    try:
        rl = http_get(f"{GH_API}/rate_limit", headers=headers, timeout=20)
        core = ((rl.json() or {}).get("resources", {}) or {}).get("core", {}) or {}
        remaining = int(core["remaining"]) if rl.status_code == 200 else None
    except Exception:
        remaining = None
    if remaining is None:
        status["remaining_start"] = "UNMEASURED"
        return stop("rate budget UNMEASURED: /rate_limit unreadable, no request spent")
    status["remaining_start"] = remaining
    budget = max(0, (remaining - floor) // GH_COST_PER_REPO)
    n = min(budget, GH_MAX_REPOS_TOKEN if token else GH_MAX_REPOS_ANON)
    status["planned"] = n
    if n == 0:
        return stop(f"rate floor: {remaining} remaining, floor {floor}")

    def get(path: str) -> Any:
        r = http_get(f"{GH_API}{path}", headers=headers, timeout=20)
        left = r.headers.get("X-RateLimit-Remaining")
        if left is not None:
            status["remaining_end"] = int(left)
        if r.status_code == 403 or r.status_code == 429:
            raise RateFloor(f"HTTP {r.status_code} on {path}")
        if left is not None and int(left) < floor:
            raise RateFloor(f"{left} remaining < floor {floor}")
        if r.status_code in (404, 409, 451):            # missing, empty or blocked repo
            return None
        return r.json() if r.status_code == 200 else None

    try:
        for repo in _order(full_pool, visited)[:n]:
            if clock() - t0 > deadline_s:
                status["stopped"] = f"pass deadline {deadline_s:.0f}s reached"
                break
            stars = full_pool.get(repo, 0)
            mem = visited.setdefault(repo, {})
            since = mem.get("visited")
            if mem.get("screened") == "crypto":
                continue
            # One metadata read first: a neutral NAME can still be an exchange bot, and its
            # description and topics say so before any content request is spent on it.
            meta = get(f"/repos/{repo}")
            if not isinstance(meta, dict) or is_crypto(
                    meta.get("full_name"), meta.get("description"), meta.get("topics")):
                mem["screened"] = "crypto" if isinstance(meta, dict) else "missing"
                mem["visited"] = _now()
                status["screened_out"] = int(status.get("screened_out", 0)) + 1
                continue
            readme = get(f"/repos/{repo}/readme")
            if isinstance(readme, dict) and readme.get("sha") != mem.get("readme_sha"):
                try:
                    body = base64.b64decode(readme.get("content", "")).decode("utf-8", "replace")
                except ValueError:
                    body = ""
                mem["readme_sha"] = readme.get("sha")
                out.append(row("github_depth", "repo_readme", f"{repo} README",
                               f"https://github.com/{repo}", _clean(body), repo=repo,
                               stars=stars))
            q = f"&since={since}" if since else ""
            commits = get(f"/repos/{repo}/commits?per_page=10{q}")
            for c in commits if isinstance(commits, list) else []:
                sha = str(c.get("sha", ""))
                if sha and sha == mem.get("last_commit_sha"):
                    break
                msg = str((c.get("commit") or {}).get("message", ""))
                out.append(row("github_depth", "code_change",
                               f"{repo}: {msg.splitlines()[0] if msg else sha[:10]}",
                               str(c.get("html_url", "")), _clean(msg), repo=repo, sha=sha,
                               stars=stars,
                               committed=(c.get("commit") or {}).get("committer", {}).get("date")))
            if isinstance(commits, list) and commits:
                mem["last_commit_sha"] = commits[0].get("sha")
            issues = get(f"/repos/{repo}/issues?state=all&sort=updated&direction=desc"
                         f"&per_page=10{q}")
            for it in issues if isinstance(issues, list) else []:
                if "pull_request" in it:
                    continue
                out.append(row("github_depth", "repo_issue", f"{repo}: {it.get('title', '')}",
                               str(it.get("html_url", "")), _clean(str(it.get("body") or "")),
                               repo=repo, stars=stars, state=it.get("state"),
                               comments=it.get("comments"), updated=it.get("updated_at")))
            forks = get(f"/repos/{repo}/forks?sort=stargazers&per_page=5")
            seen_forks = set(mem.get("forks", []))
            for fk in forks if isinstance(forks, list) else []:
                name, fstars = str(fk.get("full_name", "")), int(fk.get("stargazers_count") or 0)
                if (not name or fstars <= 0 or name in seen_forks
                        or is_crypto(name, fk.get("description"), fk.get("topics"))):
                    continue
                seen_forks.add(name)
                if fstars >= FORK_POOL_MIN_STARS and name not in pool:
                    extra[name] = fstars
                out.append(row("github_depth", "repo_fork", f"{name} (fork of {repo})",
                               str(fk.get("html_url", "")),
                               _clean(str(fk.get("description") or "")),
                               repo=name, parent=repo, stars=fstars, pushed=fk.get("pushed_at")))
            mem["forks"] = sorted(seen_forks)[-50:]
            if token and int(status.get("gql_remaining", GQL_FLOOR)) >= GQL_FLOOR:
                out.extend(_discussions(repo, stars, http_get, headers, row, mem, status))
            elif token:
                status["discussions"] = f"paused: GraphQL points below floor {GQL_FLOOR}"
            mem["visited"] = _now()
            status["repos_read"] += 1
    except RateFloor as exc:
        status["stopped"] = f"rate floor: {exc}"
    _bound(st)
    return out


_DISCUSSIONS_Q = ("query($o:String!,$n:String!){rateLimit{remaining}"
                  "repository(owner:$o,name:$n){discussions("
                  "first:5,orderBy:{field:UPDATED_AT,direction:DESC}){nodes{title url body "
                  "updatedAt category{name}}}}}")


def _discussions(repo: str, stars: int, http_get: Callable[..., Any], headers: dict[str, str],
                 row: RowFn, mem: dict[str, Any], status: dict[str, Any]) -> list[Row]:
    owner, name = repo.split("/", 1)
    try:
        r = http_get(f"{GH_API}/graphql", headers=headers, timeout=20, method="POST",
                     payload={"query": _DISCUSSIONS_Q, "variables": {"o": owner, "n": name}})
        if r.status_code in (403, 429):
            status["gql_remaining"] = 0
            return []
        data = (r.json() or {}).get("data") or {}
        left = (data.get("rateLimit") or {}).get("remaining")
        if left is not None:
            status["gql_remaining"] = int(left)
        nodes = ((data.get("repository") or {}).get("discussions") or {}).get("nodes") or []
    except Exception:
        return []
    last = str(mem.get("discussions_seen", ""))
    out = [row("github_depth", "repo_discussion", f"{repo}: {d.get('title', '')}",
               str(d.get("url", "")), _clean(str(d.get("body") or "")), repo=repo, stars=stars,
               category=(d.get("category") or {}).get("name"), updated=d.get("updatedAt"))
           for d in nodes if isinstance(d, dict) and str(d.get("updatedAt", "")) > last]
    if nodes:
        mem["discussions_seen"] = max(str(d.get("updatedAt", "")) for d in nodes
                                      if isinstance(d, dict))
    return out


def feed_text(url: str, timeout: int = 40) -> str:
    """A feed fetch under the honest client name (never the browser string seed_miners sends)."""
    r = requests_get(url, headers={"Accept": "application/atom+xml, application/rss+xml, "
                                             "application/xml;q=0.9, */*;q=0.5"},
                     timeout=timeout)
    r.raise_for_status()
    return str(r.text)


def requests_get(url: str, headers: dict[str, str] | None = None, timeout: int = 20,
                 method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    """The production transport: one request, 1 s spacing, no retries, an honest client name."""
    import requests
    time.sleep(1.0)
    headers = {**(headers or {}), "User-Agent": HONEST_UA}
    if method == "POST":
        return requests.post(url, headers=headers, json=payload, timeout=timeout)
    return requests.get(url, headers=headers, timeout=timeout)
