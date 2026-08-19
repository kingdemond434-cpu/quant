"""Academic and code sources: arXiv, SSRN, OpenReview, Hacker News.

WHY THESE MATTER MORE THAN THE VIDEO SOURCES, and it follows directly from the desk's measured
conversion record rather than from prestige. What converts here is a MEASUREMENT over many trials
or an explicit PROCEDURE; what converts nothing is narrative. A paper abstract is almost purely
the first category -- it exists to state what was measured and how -- while a video title is
mostly the second, which is why the video ranker needed a whole battery of negative weights for
course funnels and profit claims.

AND UNLIKE VIDEO, THESE CAN BE READ. Captions are blocked on both YouTube and Bilibili, so those
miners can only ever produce a queue for a human. arXiv, SSRN and OpenReview return ABSTRACTS in
the API response. That is the difference between a tool that says "go look at this" and a tool
that can surface the claim itself -- the miner stops being a queue and starts being a source of
findings.

MEASURED REACHABLE 2026-08-01 from this box:

    arXiv API          WORKS -- Atom feed, full abstracts, date-sortable, no auth
    SSRN API           WORKS -- JSON, abstracts, 59,011 papers on the q-fin binding alone
    OpenReview API     WORKS -- JSON notes with abstracts
    HN Algolia         WORKS -- JSON, good for surfacing tools and repos being discussed
    GitHub API         403 unauthenticated -- needs a token to enable repo/code search
    Reddit             403 -- blocked

ABSTRACTS ARE INDEXED, NOT ARCHIVED. What is stored is what is needed to rank and to point a
human at the source: title, abstract, authors, link. The desk reads papers; it does not host them.
"""

from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

_UA = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/xml, */*",
}

#: arXiv categories worth sweeping. q-fin.TR is trading/microstructure, ST is statistical finance,
#: CP is computational finance, PM is portfolio management. stat.ML catches methodology papers
#: that never get cross-listed to q-fin but are exactly the "explicit procedure" category.
ARXIV_CATEGORIES = ("q-fin.TR", "q-fin.ST", "q-fin.CP", "q-fin.PM", "stat.ME")


@dataclass(frozen=True)
class Paper:
    source: str
    ident: str
    title: str
    url: str
    abstract: str = ""
    authors: tuple[str, ...] = ()
    published: str = ""

    @property
    def searchable(self) -> str:
        """Title plus abstract. The abstract is where the method words and the sample sizes are;
        a title alone would rank a paper about permutation testing the same as one that merely
        mentions trading."""
        return f"{self.title} {self.abstract}"


def _get(url: str, *, timeout: float = 30.0) -> str:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        body: str = fh.read().decode("utf8", errors="ignore")
    return body


def arxiv(query: str, *, category: str = "q-fin.TR", limit: int = 25
          ) -> tuple[list[Paper], str | None]:
    """arXiv search, newest first. Returns (papers, error).

    SORTED BY SUBMISSION DATE, not relevance, because this runs on a schedule: the job is to catch
    what is NEW, and relevance ordering would re-surface the same well-matched classics every run
    while newly posted work sat below the fold.
    """
    q = f"cat:{category}" + (f"+AND+all:{quote(query)}" if query else "")
    url = (f"http://export.arxiv.org/api/query?search_query={q}"
           f"&max_results={int(limit)}&sortBy=submittedDate&sortOrder=descending")
    try:
        xml = _get(url)
    except Exception as exc:
        return [], f"{type(exc).__name__}: {str(exc)[:140]}"
    out: list[Paper] = []
    for entry in re.split(r"<entry>", xml)[1:]:
        title = _tag(entry, "title")
        summary = _tag(entry, "summary")
        ident = _tag(entry, "id")
        if not title or not ident:
            continue
        out.append(Paper(
            source="arxiv", ident=ident.rsplit("/", 1)[-1], title=title, url=ident,
            abstract=summary[:1200],
            authors=tuple(re.findall(r"<name>([^<]+)</name>", entry))[:6],
            published=_tag(entry, "published")[:10],
        ))
    if not out:
        return [], "arxiv returned no parseable entries"
    return out, None


def ssrn(binding: int = 204, *, count: int = 25) -> tuple[list[Paper], str | None]:
    """SSRN papers for a subject binding. 204 is the financial-economics network.

    SSRN has no keyword endpoint on this path, so the sweep is by BINDING and the filtering is
    left to the ranker. That is the right split: a keyword list would silently exclude the
    unfamiliar work that is the entire reason to read a paper feed.
    """
    url = f"https://api.ssrn.com/content/v1/bindings/{int(binding)}/papers?index=0&count={int(count)}"
    try:
        body = json.loads(_get(url))
    except Exception as exc:
        return [], f"{type(exc).__name__}: {str(exc)[:140]}"
    out: list[Paper] = []
    for p in body.get("papers") or []:
        pid = str(p.get("id") or "")
        title = str(p.get("title") or "").strip()
        if not pid or not title:
            continue
        out.append(Paper(
            source="ssrn", ident=pid, title=title,
            url=f"https://papers.ssrn.com/sol3/papers.cfm?abstract_id={pid}",
            abstract=str(p.get("abstract") or "")[:1200],
            authors=tuple(str(a.get("name") or "") for a in (p.get("authors") or []))[:6],
            published=str(p.get("approved_date") or "")[:10],
        ))
    if not out:
        return [], f"ssrn returned {len(body.get('papers') or [])} rows, none parseable"
    return out, None


def openreview(term: str, *, limit: int = 15) -> tuple[list[Paper], str | None]:
    url = f"https://api.openreview.net/notes/search?term={quote(term)}&limit={int(limit)}"
    try:
        body = json.loads(_get(url))
    except Exception as exc:
        return [], f"{type(exc).__name__}: {str(exc)[:140]}"
    out: list[Paper] = []
    for n in body.get("notes") or []:
        c = n.get("content") or {}
        title = str(_val(c.get("title")) or "").strip()
        nid = str(n.get("id") or "")
        if not title or not nid:
            continue
        out.append(Paper(
            source="openreview", ident=nid, title=title,
            url=f"https://openreview.net/forum?id={nid}",
            abstract=str(_val(c.get("abstract")) or "")[:1200],
        ))
    return out, None if out else "openreview returned no parseable notes"


def hackernews(query: str, *, limit: int = 20) -> tuple[list[Paper], str | None]:
    """HN via Algolia. Surfaces tools, repos and libraries being discussed rather than papers --
    a different discovery axis from a paper feed, and cheap."""
    url = (f"https://hn.algolia.com/api/v1/search?query={quote(query)}"
           f"&tags=story&hitsPerPage={int(limit)}")
    try:
        body = json.loads(_get(url))
    except Exception as exc:
        return [], f"{type(exc).__name__}: {str(exc)[:140]}"
    out: list[Paper] = []
    for h in body.get("hits") or []:
        title = str(h.get("title") or "").strip()
        oid = str(h.get("objectID") or "")
        if not title or not oid:
            continue
        out.append(Paper(
            source="hn", ident=oid, title=title,
            url=str(h.get("url") or f"https://news.ycombinator.com/item?id={oid}"),
            abstract=str(h.get("story_text") or "")[:600],
            published=str(h.get("created_at") or "")[:10],
        ))
    return out, None if out else "hn returned no hits"


def _tag(xml: str, name: str) -> str:
    m = re.search(rf"<{name}[^>]*>(.*?)</{name}>", xml, flags=re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def _val(v: Any) -> Any:
    """OpenReview wraps some fields as {"value": ...} and leaves others bare."""
    return v.get("value") if isinstance(v, dict) else v


def probe_all() -> list[dict[str, Any]]:
    """Reachability for every declared academic source, re-measured every run."""
    rows: list[dict[str, Any]] = []
    checks: tuple[tuple[str, Any], ...] = (
        ("arxiv", lambda: arxiv("backtest", category="q-fin.TR", limit=5)),
        ("ssrn", lambda: ssrn(count=5)),
        ("openreview", lambda: openreview("quantitative trading", limit=5)),
        ("hn", lambda: hackernews("quant backtest", limit=5)),
    )
    for name, fn in checks:
        items, err = fn()
        rows.append({"source": name, "ok": err is None, "n": len(items), "error": err})
    # MT5 universe (2026-08-18): was "quant backtest crypto"; the desk hunts FX/gold/metals/
    # indices now, and MT5 expert advisors are the public-code donor GitHub is richest in.
    gh_items, gh_err = github("MT5 forex expert advisor backtest")
    rows.append({"source": "github", "ok": gh_err is None, "n": len(gh_items),
                 "token_present": github_token() is not None, "error": gh_err})
    rows.append({"source": "reddit", "ok": False, "error": "HTTP 403 -- blocked"})
    return rows


# ---------------------------------------------------------------------------- GitHub (token-gated)

#: Where the token is looked for, in order. NEVER hardcoded and never committed: a token in a repo
#: is a credential leak that outlives whoever pasted it. `GITHUB_TOKEN` in the environment is the
#: right place; the dotfile is the fallback for a box where env config is inconvenient.
GITHUB_TOKEN_ENV = "GITHUB_TOKEN"    # noqa: S105 -- env var NAME, not a credential
GITHUB_TOKEN_FILE = "~/.gh_token"    # noqa: S105 -- dotfile PATH, not a credential


def github_token() -> str | None:
    """The token, or None. Absence is a normal state, not an error."""
    import os
    from pathlib import Path
    tok = os.environ.get(GITHUB_TOKEN_ENV, "").strip()
    if tok:
        return tok
    path = Path(GITHUB_TOKEN_FILE).expanduser()
    if path.exists():
        got = path.read_text("utf-8").strip()
        if got:
            return got
    return None


def github(query: str, *, kind: str = "repositories", limit: int = 20
           ) -> tuple[list[Paper], str | None]:
    """GitHub repo or code search. Requires a token; 403s without one.

    WHY IT IS WORTH A CREDENTIAL. Code is the least ambiguous source there is -- a repository that
    implements a permutation test contains the procedure itself, not a description of it, and the
    desk's conversion record says procedures convert. It is also the only source here that can be
    searched for an IMPLEMENTATION rather than a claim about one.

    `kind="code"` needs the token to carry `public_repo`; repo search works with any valid token.
    """
    tok = github_token()
    if not tok:
        return [], (f"no token: set ${GITHUB_TOKEN_ENV} or write one to {GITHUB_TOKEN_FILE}. "
                    "GitHub search is 403 unauthenticated.")
    if kind not in ("repositories", "code"):
        raise ValueError(f"kind must be 'repositories' or 'code', got {kind!r}")
    url = (f"https://api.github.com/search/{kind}?q={quote(query)}"
           f"&per_page={int(limit)}" + ("&sort=updated" if kind == "repositories" else ""))
    req = urllib.request.Request(url, headers={
        **_UA, "Authorization": f"Bearer {tok}",
        "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.urlopen(req, timeout=30) as fh:
            body = json.loads(fh.read().decode("utf8", errors="ignore"))
    except Exception as exc:
        return [], f"{type(exc).__name__}: {str(exc)[:140]}"
    out: list[Paper] = []
    for item in body.get("items") or []:
        if kind == "repositories":
            name = str(item.get("full_name") or "")
            if not name:
                continue
            out.append(Paper(
                source="github", ident=name, title=name,
                url=str(item.get("html_url") or ""),
                abstract=str(item.get("description") or "")[:600],
                published=str(item.get("pushed_at") or "")[:10]))
        else:
            repo = (item.get("repository") or {}).get("full_name") or ""
            path = str(item.get("path") or "")
            out.append(Paper(
                source="github_code", ident=f"{repo}/{path}", title=f"{repo} :: {path}",
                url=str(item.get("html_url") or ""), abstract=""))
    return out, None if out else "github returned no items"
