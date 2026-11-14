"""A silent judge tops RESEARCH_PRODUCTIVITY's bottleneck; an unreadable ledger is UNMEASURED."""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import research_productivity as rp  # noqa: E402

NOW = datetime(2026, 10, 14, 4, 24, tzinfo=UTC)
_STAGES = {"deepening": {"backlog": 0}, "judged": {"cells": 10, "unmeasured": 0}}


@pytest.fixture(autouse=True)
def _no_box_sweep(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Hermetic: the second witness is absent unless a test writes one."""
    monkeypatch.setattr(rp, "SWEEP_REPORT", tmp_path / "no_sweep_report.json")


def _ledger(tmp_path: Path, *stamps: datetime) -> Path:
    p = tmp_path / "gate_verdict_ledger.jsonl"
    p.write_text("".join(json.dumps({"cell": f"c{i}", "at": s.isoformat(), "passed": False,
                                     "terminal_gate": "dsr"}) + "\n"
                         for i, s in enumerate(stamps)), "utf-8")
    return p


def test_lease_is_the_judge_coverage_fence_constant() -> None:
    import importlib.util
    spec = importlib.util.spec_from_file_location("_t_fence", ROOT / "scripts" /
                                                  "check_judge_coverage.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert rp.judge_stale_hours() == mod.STALE_H


def test_judge_silent_47h_tops_the_bottleneck(tmp_path: Path) -> None:
    last = datetime(2026, 10, 12, 6, 59, tzinfo=UTC)
    led = _ledger(tmp_path, last - timedelta(hours=3), last)
    judge = rp.judge_silence(led, now=NOW)
    assert judge["status"] == "MEASURED" and judge["silent"] is True
    assert judge["age_hours"] == 45.4
    # Even with a deepening backlog that would otherwise win, the silent judge outranks it.
    name, detail = rp.choose_bottleneck({**_STAGES, "deepening": {"backlog": 500}}, judge)
    assert name == rp.JUDGE_SILENT
    assert detail["age_hours"] == 45.4 and detail["evidence"] == str(led)
    assert "gate_verdict_ledger.jsonl" in detail["why"] and "45.4h" in detail["why"]


def test_fresh_judge_falls_through_to_the_old_rules(tmp_path: Path) -> None:
    led = _ledger(tmp_path, NOW - timedelta(minutes=30))
    judge = rp.judge_silence(led, now=NOW)
    assert judge["silent"] is False
    assert rp.choose_bottleneck(_STAGES, judge)[0] == "none obvious"
    assert rp.choose_bottleneck({**_STAGES, "deepening": {"backlog": 500}}, judge)[0] == "deepening"


def test_missing_ledger_is_unmeasured_never_none_obvious(tmp_path: Path) -> None:
    judge = rp.judge_silence(tmp_path / "absent.jsonl", now=NOW)
    assert judge["status"] == "UNMEASURED" and judge["silent"] is None
    name, detail = rp.choose_bottleneck(_STAGES, judge)
    assert name == "UNMEASURED" and name != "none obvious"
    assert "absent.jsonl" in detail["why"]


def test_unstamped_ledger_is_unmeasured(tmp_path: Path) -> None:
    p = tmp_path / "gate_verdict_ledger.jsonl"
    p.write_text('{"cell": "x"}\nnot json\n', "utf-8")
    assert rp.judge_silence(p, now=NOW)["status"] == "UNMEASURED"


def test_unreadable_lease_is_unmeasured(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(rp, "JUDGE_FENCE", tmp_path / "nope.py")
    led = _ledger(tmp_path, NOW)
    judge = rp.judge_silence(led, now=NOW)
    assert judge["status"] == "UNMEASURED" and "lease" in judge["why"]


def _sweep(tmp_path: Path, at: datetime) -> Path:
    p = tmp_path / "universal_gates_external.json"
    p.write_text('{"n_judged": 3, "verdicts": []}', "utf-8")
    os.utime(p, (at.timestamp(), at.timestamp()))
    return p


def test_a_fresh_sweep_with_no_changed_verdict_is_not_silent(tmp_path: Path) -> None:
    """The gauntlet appends a ledger row only when a verdict CHANGES; a sweep that re-judged
    unchanged cells rewrites the sweep report, and that is the judge running."""
    led = _ledger(tmp_path, NOW - timedelta(hours=47))
    sw = _sweep(tmp_path, NOW - timedelta(minutes=40))
    judge = rp.judge_silence(led, now=NOW, sweep=sw)
    assert judge["status"] == "MEASURED" and judge["silent"] is False
    assert judge["evidence"] == str(sw) and judge["age_hours"] == 0.7
    assert judge["newest_ledger_verdict_at"] == (NOW - timedelta(hours=47)).isoformat()
    # and both witnesses old is still silent
    old = _sweep(tmp_path, NOW - timedelta(hours=30))
    assert rp.judge_silence(led, now=NOW, sweep=old)["silent"] is True


def test_sweep_alone_measures_the_judge_when_the_ledger_is_absent(tmp_path: Path) -> None:
    sw = _sweep(tmp_path, NOW - timedelta(hours=20))
    judge = rp.judge_silence(tmp_path / "absent.jsonl", now=NOW, sweep=sw)
    assert judge["status"] == "MEASURED" and judge["silent"] is True
    assert any("absent.jsonl" in g for g in judge["gaps"])


def test_a_future_stamped_row_never_masks_a_silent_judge(tmp_path: Path) -> None:
    led = _ledger(tmp_path, NOW - timedelta(hours=47), NOW + timedelta(days=30))
    judge = rp.judge_silence(led, now=NOW)
    assert judge["status"] == "MEASURED" and judge["silent"] is True
    assert judge["age_hours"] == 47.0 and judge["ledger_rows_stamped_in_future"] == 1
    only_future = _ledger(tmp_path, NOW + timedelta(days=30))
    assert rp.judge_silence(only_future, now=NOW)["status"] == "UNMEASURED"
    fut_sweep = _sweep(tmp_path, NOW + timedelta(days=1))
    j2 = rp.judge_silence(only_future, now=NOW, sweep=fut_sweep)
    assert j2["status"] == "UNMEASURED" and "future" in j2["why"]


def test_an_unmeasured_judge_still_carries_the_measured_stage(tmp_path: Path) -> None:
    judge = rp.judge_silence(tmp_path / "absent.jsonl", now=NOW)
    name, detail = rp.choose_bottleneck({**_STAGES, "deepening": {"backlog": 500}}, judge)
    assert name == "UNMEASURED"
    assert detail["measured_stage"] == {"bottleneck": "deepening", "stage": "deepening",
                                        "backlog": 500}
    _n, quiet = rp.choose_bottleneck(_STAGES, judge)
    assert quiet["measured_stage"]["bottleneck"] == "none obvious"


def test_a_sweep_that_judged_nothing_is_no_witness(tmp_path: Path) -> None:
    """Re-audit of 9dd343f69: an n_judged=0 report from 1h ago masked a 47h-silent ledger."""
    led = _ledger(tmp_path, NOW - timedelta(hours=47))
    empty = tmp_path / "universal_gates_external.json"
    for body in ('{"hunt": "external_discoveries", "verdicts": []}',
                 '{"n_judged": 0, "verdicts": []}'):
        empty.write_text(body, "utf-8")
        stamp = (NOW - timedelta(hours=1)).timestamp()
        os.utime(empty, (stamp, stamp))
        judge = rp.judge_silence(led, now=NOW, sweep=empty)
        assert judge["status"] == "MEASURED" and judge["silent"] is True, body
        assert any("judged no cell" in g for g in judge["gaps"])
    empty.write_text('{"n_judged": 12, "verdicts": []}', "utf-8")
    os.utime(empty, (stamp, stamp))
    assert rp.judge_silence(led, now=NOW, sweep=empty)["silent"] is False
