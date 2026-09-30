"""The six-event trace reads recorded artifacts only: absence is MISSING, never a pass."""

from __future__ import annotations

import json
from pathlib import Path

from libs.ops import six_event_trace


def _run(root: Path, *extra: str) -> dict:
    out = root / "desks" / "mt5" / "reports" / "six_event_trace.json"
    assert six_event_trace.main(["--root", str(root), "--now", "2026-09-30T12:00:00Z", *extra]) == 0
    return json.loads(out.read_text(encoding="utf-8"))


def test_an_empty_tree_is_missing_on_every_event_and_never_raises(tmp_path: Path) -> None:
    doc = _run(tmp_path)
    assert [e["verdict"] for e in doc["events"]] == ["MISSING"] * 6


def test_the_live_tree_reports_six_events_with_a_verdict_each() -> None:
    root = Path(six_event_trace.ROOT)
    doc = _run(root)
    assert len(doc["events"]) == 6
    assert {e["verdict"] for e in doc["events"]} <= {"PROVEN", "STALE", "MISSING"}
    for e in doc["events"]:
        if e["verdict"] != "MISSING":
            assert e["latest_at"], e["event"]


def test_freshness_is_measured_against_now(tmp_path: Path) -> None:
    root = Path(six_event_trace.ROOT)
    stale = _run(root)
    fresh = _run(root, "--fresh-days", "100000")
    for s, f in zip(stale["events"], fresh["events"], strict=True):
        if s["verdict"] == "MISSING":
            assert f["verdict"] == "MISSING"
        else:
            assert f["verdict"] == "PROVEN"
