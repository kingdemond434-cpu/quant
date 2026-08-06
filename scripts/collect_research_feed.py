"""Nightly research feed -- keyless arXiv q-fin ingestion into the vault (Phase-2 surveillance).

Pulls the newest quantitative-finance papers (q-fin.TR trading/microstructure, q-fin.PM portfolio,
q-fin.ST statistical finance) from the free arXiv Atom API, dedupes against the archive, and
appends NEW items to docs/research/feed_inbox.md -- the inbox the CRO cycle processes (per
SKILL.md): summarize -> economic intuition -> EV-score -> either graveyard-reject or distill into a
topic note + research queue. Mechanical fetch only; ALL judgment stays in the CRO cycle. Keyless,
stdlib, one call/day. SSRN/blogs/changelogs deliberately NOT scraped (fragile, ToS, low
signal-per-maintenance-hour) -- those remain the CRO's WebSearch job.

    python scripts/collect_research_feed.py
"""

from __future__ import annotations

import contextlib
import json
import re
import ssl
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

import certifi

_ARCHIVE = Path("data/research_feed.json")
_INBOX = Path("docs/research/feed_inbox.md")
_AGENDA = Path("research_agenda.json")
_GRAVEYARD = Path("docs/graveyard.md")
_API = ("http://export.arxiv.org/api/query?search_query="
        "cat:q-fin.TR+OR+cat:q-fin.PM+OR+cat:q-fin.ST"
        "&sortBy=submittedDate&sortOrder=descending&max_results=25")
_NS = {"a": "http://www.w3.org/2005/Atom"}
_KEEP = 500

#: arXiv ids carry a version suffix. Keying the seen-archive on the FULL versioned URL made a v2
#: of an already-delivered paper a brand-new item -- measured 2026-08-06: two exact duplicate
#: pairs sitting in the inbox (2607.19005 and 2607.17428, each delivered as v1 then v2). The
#: paper is the thing that was already triaged, not the revision.
_VERSION = re.compile(r"v\d+$")


def canonical_id(raw: str) -> str:
    """Strip the version suffix so a revised paper is the SAME item, not a new one."""
    return _VERSION.sub("", (raw or "").strip().rstrip("/"))


def _arxiv_ids(text: str) -> set[str]:
    """Every arXiv id mentioned anywhere in a text blob, version-stripped."""
    return {canonical_id(m) for m in re.findall(r"\b\d{4}\.\d{4,5}(?:v\d+)?\b", text or "")}


def killed_ids() -> set[str]:
    """arXiv ids the desk has ALREADY judged -- from do_not_repeat and the graveyard.

    THE RE-DELIVERY THIS CLOSES. The collector deduped only against its own seen-archive, so a
    paper EV-rejected months ago and recorded in do_not_repeat came back as a fresh inbox entry
    the moment arXiv bumped its version. Measured instance: 'The Quarter-Hour Effect'
    (2607.09426), rejected 2026-07-17 at ev 0.0006 and re-delivered as v2.

    Unreadable or absent sources return what was found so far rather than raising -- degrading
    toward MORE inbox entries, never fewer. A dedupe that silently swallowed a read error would
    drop real papers, which is the expensive direction.
    """
    ids: set[str] = set()
    with contextlib.suppress(OSError, json.JSONDecodeError):
        agenda = json.loads(_AGENDA.read_text("utf-8"))
        for entry in agenda.get("do_not_repeat") or []:
            ids |= _arxiv_ids(str(entry))
    with contextlib.suppress(OSError):
        ids |= _arxiv_ids(_GRAVEYARD.read_text("utf-8"))
    return ids


def _text(e: ET.Element, tag: str) -> str:
    return (e.findtext(f"a:{tag}", "", _NS) or "").strip()


def _fetch() -> list[dict[str, str]]:
    # certifi context: this machine's system store lacks the arXiv CA chain (urllib default fails)
    ctx = ssl.create_default_context(cafile=certifi.where())
    req = urllib.request.Request(_API, headers={"User-Agent": "quant-research-feed/1.0"})
    with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
        root = ET.fromstring(r.read())
    out = []
    for e in root.findall("a:entry", _NS):
        out.append({"id": _text(e, "id"), "title": " ".join(_text(e, "title").split()),
                    "published": _text(e, "published")[:10],
                    "abstract": " ".join(_text(e, "summary").split())[:600]})
    return out


def main() -> None:
    try:
        arch = json.loads(_ARCHIVE.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        arch = {"seen": {}}
    seen = arch.get("seen", {})
    # Migrate legacy versioned keys so an already-delivered paper is not re-delivered once on the
    # changeover. Without this the fix would itself cause one duplicate wave.
    seen = {canonical_id(k): v for k, v in seen.items()}
    killed = killed_ids()
    fetched = [it for it in _fetch() if it["id"]]
    new, blocked = [], []
    for it in fetched:
        cid = canonical_id(it["id"])
        if cid in seen:
            continue
        if _arxiv_ids(cid) & killed:
            blocked.append(cid)          # judged already: record it as seen, do NOT re-inbox it
            continue
        it["cid"] = cid
        new.append(it)
    today = datetime.now(tz=UTC).date().isoformat()
    for it in new:
        seen[it["cid"]] = today
    for cid in blocked:
        seen[cid] = today
    arch["seen"] = dict(list(seen.items())[-_KEEP:])
    _ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    _ARCHIVE.write_text(json.dumps(arch), "utf-8")

    if new:
        _INBOX.parent.mkdir(parents=True, exist_ok=True)
        head = ("# Research feed inbox (auto-fetched; CRO processes then DELETES entries)\n\n"
                "For each item: economic intuition -> orthogonality vs the alpha map -> EV-score "
                "(alpha_economics) -> graveyard-reject OR distill into docs/research/<topic>.md "
                "with [[wikilinks]] + research queue.\n")
        body = _INBOX.read_text("utf-8") if _INBOX.exists() else head
        if not body.startswith("# Research feed inbox"):
            body = head + body
        for it in new:
            body += (f"\n## {it['title']}\n- {it['published']} · {it['id']}\n"
                     f"- {it['abstract']}\n")
        _INBOX.write_text(body, "utf-8")
    print(f"research feed: {len(new)} new paper(s) -> inbox, {len(blocked)} already-judged "
          f"suppressed (archive {len(arch['seen'])})")


if __name__ == "__main__":
    main()
