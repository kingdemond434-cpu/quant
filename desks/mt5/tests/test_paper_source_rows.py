"""Every published-paper feed is its own source-registry row with route, kind and region, so the
yield rule and its region floor see it; nothing paper-shaped runs outside the registry."""
from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import source_registry as sr  # noqa: E402


def test_each_shipped_feed_and_arxiv_gets_a_row_with_a_region():
    doc = json.loads(sr.PAPER_FEEDS.read_text("utf-8"))
    rows: dict = {}
    n = sr._paper_rows(rows)
    names = [f["name"] for f in doc["feeds"]]
    harvesters = [h["name"] for h in doc.get("harvesters") or []]
    assert n == len(names) + len(harvesters) + 1
    for name in [*names, "arxiv_qfin"]:
        row = rows[f"src:paper:{name}"]
        assert row["region"], name
        assert row["route"] == "rss" and row["fetch_clock"] == sr.CLOCK_PAPERS
        assert row["kind"] in ("scholarly", "official")
        assert row["cost"] is not None
    assert "research_feeds:nber_new" in rows["src:paper:nber_new"]["aliases"]


def test_a_closed_feed_is_registered_as_closed(tmp_path):
    p = tmp_path / "feeds.json"
    p.write_text(json.dumps({"feeds": [{"name": "x", "region": "jp", "url": "u",
                                        "kind": "working_paper", "terms": "unrecorded"}]}))
    rows: dict = {}
    assert sr._paper_rows(rows, p) == 1
    assert rows["src:paper:x"]["licence_note"].startswith("CLOSED")
    assert rows["src:paper:x"]["region"] == "jp"


def test_every_shipped_feed_declares_a_region():
    doc = json.loads(sr.PAPER_FEEDS.read_text("utf-8"))
    assert all(f.get("region") for f in doc["feeds"]) and doc["arxiv"].get("region")
    assert sr.SEAT_KIND["research_feeds"] == "scholarly"
