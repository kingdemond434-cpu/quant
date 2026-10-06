"""breadth_ladder, qd_frontier and research_auction: a leg that returns must have WRITTEN.

The runtime audit read these three legs as NEVER. Each one is run here exactly as the hourly
cycle runs it (its own `main`), with its output redirected, and the test fails if the leg returns
without a fresh artifact carrying `generated_utc` at its fixed path.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

import breadth_ladder as bl  # noqa: E402
import qd_frontier as qd  # noqa: E402
import research_auction as ra  # noqa: E402

FIXED = {"breadth_ladder": "BREADTH_LADDER.json", "qd_frontier": "QD_FRONTIER.json",
         "research_auction": "RESEARCH_AUCTION.json"}


def _fresh(path: Path) -> dict:
    assert path.exists(), f"{path.name}: the leg returned 0 without writing"
    doc = json.loads(path.read_text("utf-8"))
    at = datetime.fromisoformat(str(doc["generated_utc"]))
    assert datetime.now(UTC) - at < timedelta(minutes=5)
    return doc


def test_fixed_paths_are_under_reports() -> None:
    assert DESK / "reports" / FIXED["breadth_ladder"] == bl.OUT
    assert DESK / "reports" / FIXED["qd_frontier"] == qd.OUT_REPORT
    assert DESK / "reports" / FIXED["research_auction"] == ra.OUT


def test_breadth_ladder_writes_a_stamped_artifact(tmp_path: Path, monkeypatch) -> None:
    for name in ("HISTORY", "LATEST", "LEDGER", "AXIS", "SATURATION", "FEEDBACK"):
        monkeypatch.setattr(bl, name, tmp_path / f"in_{name}.json")
    out = tmp_path / FIXED["breadth_ladder"]
    monkeypatch.setattr(bl, "OUT", out)
    assert bl.main([]) == 0
    doc = _fresh(out)
    assert doc["budget_split"]["split"] and doc["status"] == "UNMEASURED"


def test_qd_frontier_writes_a_stamped_artifact(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / FIXED["qd_frontier"]
    monkeypatch.setattr(qd, "OUT_REPORT", out)
    monkeypatch.setattr(qd, "OUT_MAP", tmp_path / "qd_mental_map.json")
    monkeypatch.setattr(qd, "INTAKE", tmp_path / "intake")
    assert qd.main([]) == 0
    _fresh(out)


def test_research_auction_writes_a_stamped_artifact(tmp_path: Path, monkeypatch) -> None:
    from libs.moat import registry
    monkeypatch.setattr(registry, "remember", lambda *a, **k: None)
    out = tmp_path / FIXED["research_auction"]
    assert ra.main(["--once", "--budget-s", "300", "--out", str(out)]) == 0
    doc = _fresh(out)
    assert doc["factors"]
    assert not out.with_suffix(out.suffix + ".tmp").exists()
