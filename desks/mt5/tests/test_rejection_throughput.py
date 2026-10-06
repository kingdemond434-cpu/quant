"""Confident kills per day: a REJECT counts only when a MEASURED gate statistic backs it.

`research/rejection_throughput.py` is the desk's rejection-throughput headline. These pin the
contract: an UNKNOWN / NOT_RUN / fail-closed-without-proof verdict is never a confident kill; a
gate-0 refusal is its own bucket; judged is the sum of the four buckets, one per cell per day;
kill confidence carries a Wilson interval; and a missing or stale ledger is UNMEASURED, never 0.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK / "research"), str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import rejection_throughput as RT  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _row(cell: str, days_ago: float, gate: str | None = "cpcv", passed: bool = False,
         status: str | None = None, **extra: object) -> str:
    at = (NOW - timedelta(days=days_ago)).isoformat(timespec="seconds")
    return json.dumps({"at": at, "cell": cell, "passed": passed, "terminal_gate": gate,
                       "downstream_status": status, **extra}) + "\n"


def test_outcome_buckets() -> None:
    assert RT.outcome({"passed": True, "terminal_gate": "PASSED"})[0] == "survivor"
    assert RT.outcome({"passed": False, "terminal_gate": "deflated_sharpe"}) == (
        "confident_kill", "deflated_sharpe")
    assert RT.outcome({"passed": False, "terminal_gate": "UNKNOWN"}) == (
        "unconfident", "unknown_gate")
    assert RT.outcome({"passed": None, "terminal_gate": "UNKNOWN",
                       "downstream_status": "NOT_RUN_BUILD_BUDGET_DEFERRED"}) == (
        "unconfident", "not_run")
    assert RT.outcome({"passed": False, "terminal_gate": "economic_prior"})[0] == "screen_reject"
    # Fail-closed gates are a kill only with proof they measured.
    assert RT.outcome({"passed": False, "terminal_gate": "swap_cost"})[0] == "unconfident"
    assert RT.outcome({"passed": False, "terminal_gate": "swap_cost",
                       "stages": {"swap_cost": {"measured": True}}})[0] == "confident_kill"
    assert RT.outcome({"passed": False, "terminal_gate": "lockbox",
                       "stages": {"lockbox": {"lockbox_sharpe": None}}})[0] == "unconfident"
    assert RT.outcome({"passed": False, "terminal_gate": "lockbox",
                       "stages": {"lockbox": {"lockbox_sharpe": -0.2}}})[0] == "confident_kill"
    assert RT.outcome({"passed": False, "terminal_gate": "made_up_gate"})[0] == "unconfident"


def test_wilson_interval_known_values() -> None:
    assert RT.wilson(0, 0) is None
    lo, hi = RT.wilson(0, 10)
    assert lo == 0.0 and abs(hi - 0.2775) < 1e-3
    lo, hi = RT.wilson(5, 10)
    assert abs(lo - 0.2366) < 1e-3 and abs(hi - 0.7634) < 1e-3


def test_absent_ledger_is_unmeasured_never_zero(tmp_path: Path) -> None:
    doc = RT.build(NOW, ledger=tmp_path / "absent.jsonl", compute=tmp_path / "none.jsonl")
    assert doc["status"] == "UNMEASURED"
    assert doc["confident_kills_per_day"] == "UNMEASURED"
    assert doc["kill_confidence"] == "UNMEASURED"


def test_stale_ledger_is_unmeasured(tmp_path: Path) -> None:
    led = tmp_path / "gate.jsonl"
    led.write_text(_row("a", 5.0) + _row("b", 4.0), "utf-8")
    doc = RT.build(NOW, ledger=led, compute=tmp_path / "none.jsonl")
    assert doc["status"] == "UNMEASURED"
    assert doc["confident_kills_per_day"] == "UNMEASURED"
    assert "old" in doc["why"]


def test_per_day_counts_one_cell_once_and_sums_to_judged(tmp_path: Path) -> None:
    led = tmp_path / "gate.jsonl"
    rows = [
        # yesterday (1 complete day): 3 confident kills, 1 survivor, 2 unconfident, 1 screen
        _row("k1", 1.0, "cpcv"), _row("k2", 1.0, "deflated_sharpe"),
        _row("k3", 1.0, "walk_forward"),
        _row("s1", 1.0, "PASSED", passed=True),
        _row("u1", 1.0, "UNKNOWN"), _row("u2", 1.0, None, passed=False,
                                         status="NOT_RUN_DATA_MISSING"),
        _row("e1", 1.0, "economic_prior"),
        # the same cell twice in a day counts once, at its LAST verdict
        _row("k4", 1.02, "UNKNOWN"), _row("k4", 1.01, "pbo"),
        # today: fresh, keeps the ledger live
        _row("t1", 0.1, "cpcv"),
    ]
    led.write_text("".join(rows), "utf-8")
    comp = tmp_path / "compute.jsonl"
    day = (NOW - timedelta(days=1)).isoformat()
    comp.write_text(json.dumps({"at": day, "run": "external_gauntlet", "cpu_s": 7200}) + "\n"
                    + json.dumps({"at": day, "run": "search", "cpu_s": 99999}) + "\n", "utf-8")
    doc = RT.build(NOW, ledger=led, compute=comp)
    assert doc["status"] == "MEASURED"
    y = next(d for d in doc["per_day"] if d["day"] == (NOW - timedelta(days=1)).date().isoformat())
    assert y["confident_kills"] == 4
    assert y["survivors"] == 1
    assert y["unconfident"] == 2
    assert y["screen_rejects"] == 1
    assert y["judged"] == y["confident_kills"] + y["survivors"] + y["unconfident"] \
        + y["screen_rejects"] == 8
    assert y["kill_confidence"] == 0.5
    assert y["kill_confidence_wilson95"] == RT.wilson(4, 8)
    assert y["judge_core_hours"] == 2.0          # only the gauntlet's CPU counts
    assert y["confident_kills_per_core_hour"] == 2.0
    # headline over complete days only; today is partial
    assert doc["headline_days"] == [y["day"]]
    assert doc["confident_kills_per_day"] == 4.0
    assert doc["kill_confidence"] == 0.5
    assert doc["confident_kills_per_core_hour"] == 2.0
    # a day before the ledger's first row is UNMEASURED, not zero
    early = doc["per_day"][0]
    assert early["status"] == "UNMEASURED"


def test_core_hours_absent_is_unmeasured(tmp_path: Path) -> None:
    led = tmp_path / "gate.jsonl"
    led.write_text(_row("k1", 1.0, "cpcv") + _row("t", 0.1, "cpcv"), "utf-8")
    doc = RT.build(NOW, ledger=led, compute=tmp_path / "none.jsonl")
    assert doc["confident_kills_per_core_hour"] == "UNMEASURED"


def test_the_classifier_is_imported_from_the_burndown_not_respelled() -> None:
    src = (_DESK / "research" / "rejection_throughput.py").read_text("utf-8")
    assert "from judging_burndown import classify" in src


def test_the_leg_is_on_the_hourly_clock_and_belongs_to_a_layer() -> None:
    """UNWIRED OR IDLE IS A DEFECT (III.16)."""
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["rejection_throughput"] == "meta"
    cycle = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"rejection_throughput", "research/rejection_throughput.py"' in cycle
    assert '"rejection_throughput": rjt' in cycle
    assert '"rejection_throughput": 600' in cycle
    # after the judge and the burn-down whose ledger it reads
    assert cycle.index('"judging_burndown", "research/judging_burndown.py"') < \
        cycle.index('"rejection_throughput", "research/rejection_throughput.py"')
