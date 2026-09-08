"""The programme ledger cannot claim what the repository does not hold.

An EXISTS-LIT entry must cite files that exist, lines inside them, a clock the repo knows and an
artifact; otherwise the ledger is the same kind of theatre it exists to end.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts import check_tier1_program as ck  # noqa: E402


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "ops").mkdir()
    (tmp_path / "ops" / "quant-x.timer").write_text("[Timer]\n", "utf-8")
    (tmp_path / "desks" / "mt5" / "ops").mkdir(parents=True)
    (tmp_path / "desks" / "mt5" / "ops" / "box_tasks.manifest").write_text(
        'TASK name="MT5-Hourly" trigger="loop"\n', "utf-8")
    (tmp_path / "desks" / "mt5" / "research").mkdir()
    (tmp_path / "desks" / "mt5" / "research" / "hourly_cycle.py").write_text(
        'def daily():\n    pass\n\n_costed("mine", lambda: 1)\n', "utf-8")
    (tmp_path / "libs").mkdir()
    (tmp_path / "libs" / "thing.py").write_text("a\nb\nc\n", "utf-8")
    return tmp_path


def _ledger(**item) -> dict:
    base = {"id": "X1", "item": "x", "phase": 0, "status": "EXISTS-LIT", "gate": "none",
            "evidence": ["libs/thing.py:2 — it (MEASURED)"], "scheduled_by": "quant-x.timer",
            "artifact": "data/x.json", "consumer": "y"}
    base.update(item)
    return {"updated": "2026-09-08", "phases": {"0": "truth"}, "acceptance_properties": [],
            "items": [base]}


def test_a_true_lit_entry_passes(tmp_path: Path) -> None:
    problems, census = ck.check(_ledger(), _repo(tmp_path))
    assert problems == [] and census["total"] == {"EXISTS-LIT": 1}


def test_a_missing_file_is_a_lie(tmp_path: Path) -> None:
    problems, _ = ck.check(_ledger(evidence=["libs/nope.py:1 — x"]), _repo(tmp_path))
    assert any("does not exist" in p for p in problems)


def test_a_missing_file_on_a_partial_entry_is_a_warning_not_a_lie(tmp_path: Path) -> None:
    """A PARTIAL entry's citation is evidence of absence; a sweep may cite a short name. Only a
    claim that something RUNS or has LANDED must be verifiable to the line."""
    problems, census = ck.check(_ledger(status="PARTIAL", gap="half of it",
                                        evidence=["libs/nope.py:1 — x"]), _repo(tmp_path))
    assert problems == [] and any("does not exist" in w for w in census["warnings"])


def test_a_bare_name_resolves_through_the_tree(tmp_path: Path) -> None:
    """A sweep that cites `thing.py:2` by name alone is citing a real file; a name nothing in
    the tree carries is still a lie; a name several files carry exists but is not line-checked."""
    repo = _repo(tmp_path)
    (repo / "desks" / "mt5" / "research" / "thing.py").write_text("a\n", "utf-8")
    ck._BASENAMES.clear()
    assert ck.check(_ledger(evidence=["quant-x.timer — it (MEASURED)"]), repo)[0] == []
    assert ck.check(_ledger(evidence=["box_tasks.manifest — it (MEASURED)"]), repo)[0] == []
    problems, _ = ck.check(_ledger(evidence=["ghost.py:1 — x"]), repo)
    assert any("does not exist" in p for p in problems)
    problems, census = ck.check(_ledger(evidence=["thing.py:40 — x"]), repo)
    assert problems == [] and any("several" in w for w in census["warnings"])
    ck._BASENAMES.clear()


def test_a_line_beyond_the_file_is_a_lie(tmp_path: Path) -> None:
    problems, _ = ck.check(_ledger(evidence=["libs/thing.py:40 — x"]), _repo(tmp_path))
    assert any("beyond" in p for p in problems)


def test_lit_needs_a_clock_the_repo_knows(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    for sched, ok in (("quant-x.timer", True), ("quant-ghost.timer", False),
                      ("MT5-Hourly", True), ("MT5-Ghost", False),
                      ("hourly_cycle:daily", True), ("hourly_cycle:mine", True),
                      ("hourly_cycle:ghost", False), ("NONE", False), ("", False)):
        problems, _ = ck.check(_ledger(scheduled_by=sched), repo)
        assert (problems == []) is ok, (sched, problems)


def test_dark_and_missing_need_no_clock_but_partial_needs_a_gap(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assert ck.check(_ledger(status="EXISTS-DARK", scheduled_by="NONE"), repo)[0] == []
    assert ck.check(_ledger(status="MISSING", evidence=[], scheduled_by=""), repo)[0] == []
    bad, _ = ck.check(_ledger(status="PARTIAL", gap=""), repo)
    assert any("PARTIAL" in p for p in bad)


def test_the_real_ledger_tells_no_lies() -> None:
    if not ck.LEDGER.exists():
        import pytest
        pytest.skip("ledger not yet written")
    problems, census = ck.check(json.loads(ck.LEDGER.read_text("utf-8")), ROOT)
    assert problems == [], "\n".join(problems)
    assert census["n_items"] >= 100, "the two blueprints hold ~120 items"


def test_render_is_generated_from_the_json(tmp_path: Path) -> None:
    ledger = _ledger()
    _, census = ck.check(ledger, _repo(tmp_path))
    text = ck.render(ledger, census)
    assert "X1 x" in text and "EXISTS-LIT" in text and "do not edit by hand" in text
