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

import json
import ssl
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

import certifi

_ARCHIVE = Path("data/research_feed.json")
_INBOX = Path("docs/research/feed_inbox.md")
_API = ("http://export.arxiv.org/api/query?search_query="
        "cat:q-fin.TR+OR+cat:q-fin.PM+OR+cat:q-fin.ST"
        "&sortBy=submittedDate&sortOrder=descending&max_results=25")
_NS = {"a": "http://www.w3.org/2005/Atom"}
_KEEP = 500


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
    new = [it for it in _fetch() if it["id"] and it["id"] not in seen]
    today = datetime.now(tz=UTC).date().isoformat()
    for it in new:
        seen[it["id"]] = today
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
    print(f"research feed: {len(new)} new paper(s) -> inbox (archive {len(arch['seen'])})")


if __name__ == "__main__":
    main()
