"""EVERY OBLIGATION IS INHERITED, NOT REMEMBERED: plant five incomplete arrivals, catch five.

The fence's whole claim is that a thing created NEXT MONTH inherits its obligations without a
session remembering them. The only way to test that claim is to create such a thing -- one per
axis -- after the floor has been recorded, and require the fence to name each of them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import check_birth_obligations as birth  # noqa: E402


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _baseline_tree(root: Path) -> None:
    """A small tree where every axis measures and every object HAS its obligation."""
    _write(root / "scripts" / "old_tool.py", "if __name__ == '__main__':\n    pass\n")
    _write(root / "desks" / "mt5" / "research" / "hourly_cycle.py",
           '_costed("old_tool", lambda: None)\n')
    _write(root / "docs" / "research" / "runtime_state.json",
           json.dumps({"organs": [{"organ": "leg:old_tool", "artifact": "scripts/old_tool.py"}]}))
    _write(root / "desks" / "mt5" / "data" / "deep_forest_sources.json",
           json.dumps({"cn": [{"id": "old_source"}]}))
    _write(root / "desks" / "mt5" / "reports" / "SOURCE_DRAIN.json",
           json.dumps({"rows": [{"source": "old_source", "stage": "cells_judged"}]}))
    _write(root / "desks" / "mt5" / "reports" / "JUDGE_COVERAGE.json",
           json.dumps({"families": {"old_family": {"judged": 12}}}))
    _write(root / "desks" / "mt5" / "reports" / "regional_parity.json",
           json.dumps({"regions": {"old_region": {"depth": 3}}, "flagged": []}))
    _write(root / "libs" / "old_deleter.py",
           "import shutil\n\n\ndef go(p):\n    if p.exists():\n        shutil.rmtree(p)\n")
    # 6. the SIXTH AXIS (attribution, 2026-09-23): a registry whose cells and discoveries born
    # since the obligation date all carry their producer stamp.
    import sqlite3
    db = root / "data" / "alpha_registry.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db))
    con.execute("create table research_candidates (id text, created_at text, producer text)")
    con.execute("create table discoveries (discovery_id text, created_at text, producer text)")
    con.execute("insert into research_candidates values ('c1', '2026-09-24T01:00:00', 'miner')")
    con.execute("insert into discoveries values ('d1', '2026-09-24T01:00:00', 'miner')")
    con.commit()
    con.close()
    # 7. the SEVENTH AXIS (certificate birth, 2026-09-24): every certificate the canon holds has
    # a row in the birth record, naming its producer.
    _write(root / "desks" / "mt5" / "data" / "UNIVERSAL_SURVIVORS.canon.json",
           json.dumps({"survivors": {"external.OLD.cell": {"hunt": "external",
                                                           "cell": "OLD.cell"}}}))
    _write(root / "desks" / "mt5" / "data" / "certificate_provenance.json",
           json.dumps({"records": {"OLD.cell": {"verdict": "ATTRIBUTED",
                                                "producer": "miner"}}}))


def _plant_five(root: Path) -> None:
    """One new object per axis, each arriving WITHOUT the obligation of its class."""
    # 1. a new executable with no clock and no attested row
    _write(root / "scripts" / "new_tool.py", "if __name__ == '__main__':\n    pass\n")
    # 2. a new source with no position in the collection chain
    _write(root / "desks" / "mt5" / "data" / "deep_forest_sources.json",
           json.dumps({"cn": [{"id": "old_source"}, {"id": "new_source"}]}))
    # 3. a new family the judge never reaches
    _write(root / "desks" / "mt5" / "reports" / "JUDGE_COVERAGE.json",
           json.dumps({"families": {"old_family": {"judged": 12},
                                    "new_family": {"judged": 0}}}))
    # 4. a new country arriving below the standing floors
    _write(root / "desks" / "mt5" / "reports" / "regional_parity.json",
           json.dumps({"regions": {"old_region": {"depth": 3}, "new_country": {"depth": 0}},
                       "flagged": ["new_country"]}))
    # 5. a new destructive path that acts without looking
    _write(root / "libs" / "new_deleter.py",
           "import shutil\n\n\ndef go(p):\n    shutil.rmtree(p)\n")


def test_the_baseline_tree_is_complete_on_every_axis(tmp_path: Path) -> None:
    _baseline_tree(tmp_path)
    doc = birth.measure(tmp_path)
    for name, ax in doc["axes"].items():
        assert ax["verdict"] == "measured", f"{name} could not be measured: {ax['why']}"
        assert ax["incomplete"] == 0, f"{name} starts incomplete: {ax['names']}"
    assert doc["failures"] == []


def test_five_arrivals_without_their_obligations_are_all_caught(tmp_path: Path) -> None:
    _baseline_tree(tmp_path)
    assert birth.main(["--root", str(tmp_path), "--update"]) == 0
    _plant_five(tmp_path)

    doc = birth.measure(tmp_path)
    arrived = {k: v["arrived_without_obligation"] for k, v in doc["axes"].items()}
    assert arrived["executable"] == ["scripts/new_tool.py"]
    assert arrived["source"] == ["new_source"]
    assert arrived["family"] == ["new_family"]
    assert arrived["region"] == ["new_country"]
    assert arrived["destructive"] == ["libs/new_deleter.py"]
    assert len(doc["failures"]) == 5
    assert birth.main(["--root", str(tmp_path)]) == 2


def test_an_arrival_that_acquires_its_obligation_leaves_the_floor(tmp_path: Path) -> None:
    """The ratchet falls by itself: no human edits a number to record the repair."""
    _baseline_tree(tmp_path)
    birth.main(["--root", str(tmp_path), "--update"])
    _write(tmp_path / "libs" / "new_deleter.py",
           "import shutil\n\n\ndef go(p):\n    shutil.rmtree(p)\n")
    assert birth.measure(tmp_path)["axes"]["destructive"]["arrived_without_obligation"] == [
        "libs/new_deleter.py"]
    birth.main(["--root", str(tmp_path), "--update"])          # accept the debt
    ax = birth.measure(tmp_path)["axes"]["destructive"]
    assert ax["arrived_without_obligation"] == [] and ax["incomplete"] == 1
    _write(tmp_path / "libs" / "new_deleter.py",
           "import shutil\n\n\ndef go(p):\n    if p.exists():\n        shutil.rmtree(p)\n")
    ax = birth.measure(tmp_path)["axes"]["destructive"]
    assert ax["incomplete"] == 0 and ax["healed"] == 1


def test_an_axis_with_no_declaring_artifact_is_unmeasured_not_zero(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    doc = birth.measure(tmp_path)
    for name, ax in doc["axes"].items():
        assert ax["verdict"] == birth.UNMEASURED, name
        assert ax["why"].startswith(birth.UNMEASURED)
    assert doc["failures"] == [], "an unmeasured axis must never manufacture a failure"


def test_every_axis_names_the_fence_that_already_owns_it() -> None:
    """The point is ONE place that answers 'did anything arrive incomplete', not five more
    checkers: each axis must delegate to the fence the desk already has."""
    for ax in birth.AXES:
        assert ax.fence is not None, ax.name
        assert (ROOT / "scripts" / ax.fence[0]).is_file(), ax.fence[0]
    gate = (ROOT / "scripts" / "run_law_gate.py").read_text(encoding="utf-8")
    assert "check_birth_obligations.py" in gate, "the fence must run on the law gate"


def _copied_box_report(root: Path, at: str) -> None:
    """A JUDGE_COVERAGE.json as a clone holds it: the box's own stamp, a checkout-fresh mtime."""
    _write(root / "desks" / "mt5" / "reports" / "JUDGE_COVERAGE.json",
           json.dumps({"at": at, "families": {"old_family": {"judged": 12},
                                              "new_family": {"judged_total": 0}}}))


def test_a_copied_box_report_is_aged_by_its_own_stamp_not_the_checkout(
        tmp_path: Path, monkeypatch) -> None:
    """2026-10-29: a clone's mtime is checkout time, so a two-day-old box report read as fresh
    and a standalone run named 59 'arrived' families on a host that measures nothing about the
    judge. Off the box the report's own `at` decides, and that verdict is UNMEASURED."""
    _baseline_tree(tmp_path)
    assert birth.main(["--root", str(tmp_path), "--update"]) == 0
    _copied_box_report(tmp_path, "2026-01-01T00:00:00+00:00")       # mtime: now
    monkeypatch.setattr(birth, "_is_trading_host", lambda root: False)
    monkeypatch.delenv("QUANT_LAWGATE_SOURCE_VIEW", raising=False)
    ax = birth.measure(tmp_path)["axes"]["family"]
    assert ax["verdict"] == birth.UNMEASURED and "h old" in ax["why"]
    assert not [f for f in birth.measure(tmp_path)["failures"] if f.startswith("family")]


def test_the_box_still_judges_a_stale_family_report(tmp_path: Path, monkeypatch) -> None:
    """The teeth are untouched where they bite: on the trading host, and under --require-state,
    the same report is judged and the unreached family fails."""
    _baseline_tree(tmp_path)
    birth.main(["--root", str(tmp_path), "--update"])
    _copied_box_report(tmp_path, "2026-01-01T00:00:00+00:00")
    monkeypatch.delenv("QUANT_LAWGATE_SOURCE_VIEW", raising=False)
    monkeypatch.setattr(birth, "_is_trading_host", lambda root: True)
    assert birth.measure(tmp_path)["axes"]["family"]["arrived_without_obligation"] == [
        "new_family"]
    monkeypatch.setattr(birth, "_is_trading_host", lambda root: False)
    doc = birth.measure(tmp_path, require_state=True)
    assert doc["axes"]["family"]["arrived_without_obligation"] == ["new_family"]
    assert any(f.startswith("family") for f in doc["failures"])


def test_a_fresh_stamp_off_the_box_is_still_judged(tmp_path: Path, monkeypatch) -> None:
    """The stamp narrows nothing beyond the mtime it replaces: a report the box wrote inside the
    window is judged off the box exactly as before."""
    from datetime import UTC, datetime
    _baseline_tree(tmp_path)
    birth.main(["--root", str(tmp_path), "--update"])
    _copied_box_report(tmp_path, datetime.now(tz=UTC).isoformat(timespec="seconds"))
    monkeypatch.delenv("QUANT_LAWGATE_SOURCE_VIEW", raising=False)
    monkeypatch.setattr(birth, "_is_trading_host", lambda root: False)
    assert birth.measure(tmp_path)["axes"]["family"]["arrived_without_obligation"] == [
        "new_family"]


def test_a_committed_declaration_is_not_aged_by_its_stamp(tmp_path: Path, monkeypatch) -> None:
    """The runtime attestation is an in-repo declaration ('has a row'), which a clone CAN judge
    whatever its age: an old `generated_at` must not turn the executable axis UNMEASURED."""
    _baseline_tree(tmp_path)
    _write(tmp_path / "docs" / "research" / "runtime_state.json",
           json.dumps({"generated_at": "2026-01-01T00:00:00+00:00",
                       "organs": [{"organ": "leg:old_tool", "artifact": "scripts/old_tool.py"}]}))
    monkeypatch.setattr(birth, "_is_trading_host", lambda root: False)
    assert birth.measure(tmp_path)["axes"]["executable"]["verdict"] == "measured"
    assert {ax.name for ax in birth.AXES if ax.box_report} == {
        "source", "family", "region", "attribution"}
