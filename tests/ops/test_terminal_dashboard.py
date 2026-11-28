"""The final terminal (C row 14): the thread-status writer and the page's three tabs.

No network: the writer reads local files only, and the page is checked as text.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import publish_thread_status as pts  # noqa: E402

PAGE = ROOT / "web" / "terminal.html"


def test_absent_index_is_unmeasured_not_empty(tmp_path: Path) -> None:
    doc = pts.build(tmp_path / "missing.json")
    assert doc["status"] == "UNMEASURED"
    assert doc["threads"] == []
    assert "no thread index" in doc["why"]


def test_unreadable_and_shapeless_index_are_unmeasured(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", "utf-8")
    assert pts.build(bad)["status"] == "UNMEASURED"
    bad.write_text(json.dumps({"threads": "nope"}), "utf-8")
    assert pts.build(bad)["status"] == "UNMEASURED"


def test_partial_rows_keep_nulls_and_drop_free_text(tmp_path: Path) -> None:
    idx = tmp_path / "INDEX.json"
    idx.write_text(json.dumps({"generated_utc": "2026-11-18T07:54:27+00:00", "threads": [
        {"title": "Done one", "open_rows": 0, "pm_open": 0, "prs": 0, "next_step": "secret prose"},
        {"title": "Busy", "open_rows": 5, "pm_open": 1, "prs": 3},
        {"title": "Stuck", "open_rows": 2, "next_step": "BLOCKED on the console"},
        {"title": "Explicit", "state": "blocked", "last_activity": "2026-11-17T00:00:00+00:00"},
        {"open_rows": 1},
        "not a row",
    ]}), "utf-8")
    doc = pts.build(idx)
    assert doc["status"] == "MEASURED"
    by = {t["title"]: t for t in doc["threads"]}
    assert by["Done one"]["state"] == "done"
    assert by["Busy"]["state"] == "working" and by["Busy"]["open_prs"] == 3
    assert by["Stuck"]["state"] == "blocked" and by["Stuck"]["open_prs"] is None
    assert by["Explicit"]["state"] == "blocked"
    assert by["Explicit"]["last_activity"] == "2026-11-17T00:00:00+00:00"
    assert by["Busy"]["last_activity"] == "2026-11-18T07:54:27+00:00"
    assert doc["counts"] == {"working": 1, "blocked": 2, "done": 1}
    assert "secret prose" not in json.dumps(doc)
    assert set(by["Busy"]) == {"title", "state", "last_activity", "open_prs", "open_rows"}


def test_main_writes_the_file(tmp_path: Path) -> None:
    out = tmp_path / "web" / "threads.json"
    assert pts.main(["--index", str(tmp_path / "none.json"), "--out", str(out)]) == 0
    assert json.loads(out.read_text("utf-8"))["status"] == "UNMEASURED"


def test_page_has_three_tabs_and_reads_its_inputs() -> None:
    html = PAGE.read_text("utf-8")
    tabs = re.findall(r'data-tab="(\w+)"', html)
    assert tabs == ["quant", "memecoin", "agents"]
    for panel in ("tab-quant", "tab-memecoin", "tab-agents"):
        assert f'id="{panel}"' in html
    for name in ("desk_state.json", "memecoin_state.json", "threads.json"):
        assert f'load("{name}")' in html
    assert "UNMEASURED" in html


def test_page_is_self_contained() -> None:
    html = PAGE.read_text("utf-8")
    assert not re.search(r'<script[^>]+src=', html)
    assert not re.search(r'<link[^>]+href=', html)
    assert "http://" not in html and "https://" not in html
    assert "innerHTML" not in html


def test_refresh_tick_publishes_thread_status() -> None:
    sh = (ROOT / "ops" / "refresh_desk_state.sh").read_text("utf-8")
    assert "scripts/publish_thread_status.py --out web/threads.json" in sh
