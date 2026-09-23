"""CLOCK IMPLIES CERTIFICATE -- and the law RAISES testing rather than cutting evidence.

The tests that matter here are the ones that stop the obvious wrong implementation. A breach is
easy to "fix" by switching the clock off; doing that would shrink the forward book to the size
of the canon, destroy the evidence that would have settled each cell, and reintroduce exactly
the scarcity the principal abolished. So: a breached clock KEEPS accruing and its cell goes to
the FRONT of the judge's queue; only the judge's own rejection takes a clock away, and only when
that rejection cannot belong to a sibling parameterization; an empty canon declares no breach at
all; and the fence fails on breach AGE, never on breach COUNT.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research"), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_clock_liveness as fence  # noqa: E402
import clock_certificate as cc  # noqa: E402


def _clock(key, **kw):
    return {"lane": "main", "key": key, "symbol": key.split(".")[0], "timeframe": "H1",
            "verdict": "ACCRUING", "status": "ACTIVE", **kw}


def _report(certificate):
    return {"at": datetime.now(UTC).isoformat(), "clocks_total": 10, "frozen_after": 0,
            "frozen_before": 0, "frozen": [], "counts": {}, "repairs": [],
            "certificate": certificate}


@pytest.fixture
def canon(tmp_path):
    p = tmp_path / "canon.json"
    p.write_text(json.dumps({"n": 2, "survivors": {"a": {}, "b": {}}}), encoding="utf-8")
    return p


def _audit(clocks, roster, tmp_path, canon_path, verdicts=None, apply=False):
    v = tmp_path / "verdicts.jsonl"
    v.write_text("\n".join(json.dumps(r) for r in (verdicts or [])), encoding="utf-8")
    return cc.audit(clocks, roster=roster, apply=apply, canon_path=canon_path, verdict_path=v,
                    ledger_path=tmp_path / "breach.json", queue_path=tmp_path / "q.jsonl")


# ------------------------------------------------------------------------------ the tracing
def test_a_clock_on_the_roster_is_backed(tmp_path, canon):
    out = _audit([_clock("EURUSD.carry.continuous")], {"EURUSD.carry.continuous"}, tmp_path,
                 canon)
    assert out["counts"][cc.BACKED] == 1
    assert out["breached"] == 0


def test_a_clock_with_no_certificate_is_a_breach_naming_its_cell(tmp_path, canon):
    out = _audit([_clock("EURUSD.carry.continuous")], set(), tmp_path, canon)
    assert out["breached"] == 1
    assert out["rows"][0]["cell"] == "EURUSD.carry"


def test_an_intraday_clock_names_its_chart_in_the_cell(tmp_path, canon):
    out = _audit([_clock("BTCUSD.macro_conditional.continuous", timeframe="M5")], set(),
                 tmp_path, canon)
    assert out["rows"][0]["cell"] == "BTCUSD@M5.macro_conditional"


def test_an_already_terminal_clock_breaches_nothing(tmp_path, canon):
    out = _audit([_clock("EURUSD.carry.continuous", status="RETIRED_ORPHAN", verdict="RETIRED")],
                 set(), tmp_path, canon)
    assert out["counts"][cc.RETIRED] == 1
    assert out["breached"] == 0


# ------------------------------------------------------------- the remedy is the judge, not the axe
def test_a_breached_clock_is_queued_first_and_keeps_its_clock(tmp_path, canon):
    out = _audit([_clock("EURUSD.carry.continuous")], set(), tmp_path, canon, apply=True)
    assert out["queue"]["submitted"] == 1
    from libs.ops.task_queue import TaskQueue
    tasks = list(TaskQueue(tmp_path / "q.jsonl").tasks().values())
    assert tasks[0].kind == "recertify"
    assert tasks[0].priority == cc.BREACH_PRIORITY
    assert tasks[0].dedupe_key == "clock_breach:EURUSD.carry"
    assert out["rows"][0]["backing"] == cc.AWAITING       # the clock keeps running


def test_a_cell_already_waiting_in_the_queue_is_not_requeued_every_hour(tmp_path, canon):
    clocks = [_clock("EURUSD.carry.continuous")]
    _audit(clocks, set(), tmp_path, canon, apply=True)
    again = _audit(clocks, set(), tmp_path, canon, apply=True)
    assert again["queue"]["submitted"] == 0
    assert again["queue"]["already_queued"] == 1


def test_an_empty_canon_makes_backing_unmeasured_and_declares_no_breach(tmp_path):
    p = tmp_path / "canon.json"
    p.write_text(json.dumps({"n": 0, "survivors": {}}), encoding="utf-8")
    out = _audit([_clock("EURUSD.carry.continuous")], set(), tmp_path, p)
    assert out["counts"][cc.UNMEASURED] == 1
    assert out["breached"] == 0
    assert "mid-repair" in out["canon"]["why"]


def test_an_unreadable_roster_makes_backing_unmeasured(tmp_path, canon):
    out = _audit([_clock("EURUSD.carry.continuous")], None, tmp_path, canon)
    assert out["counts"][cc.UNMEASURED] == 1
    assert out["breached"] == 0


# ------------------------------------------------------------------------------ the verdicts
def _verdict(gate, status="REJECTED", passed=False):
    return [{"at": "2026-09-20T00:00:00+00:00", "cell": "EURUSD.carry.p=abc", "sym": "EURUSD",
             "family": "carry", "passed": passed, "terminal_gate": gate,
             "downstream_status": status}]


def test_a_parameter_independent_reject_takes_the_clock_with_the_verdict_as_its_reason(tmp_path,
                                                                                       canon):
    out = _audit([_clock("EURUSD.carry.continuous")], set(), tmp_path, canon,
                 verdicts=_verdict("economic_prior", "NOT_RUN_TERMINAL_GATE_1_REJECT"))
    assert out["counts"][cc.RETIRED] == 1
    assert out["breached"] == 0
    assert "economic_prior" in out["retire"][0]["why"]


def test_a_parameter_dependent_reject_never_takes_a_sibling_cells_clock(tmp_path, canon):
    """`deflated_sharpe` rules on ONE parameterization, and the ledger cannot be joined to a
    clock below (symbol, family, chart) -- so acting on it would retire an unjudged cell."""
    out = _audit([_clock("EURUSD.carry.continuous")], set(), tmp_path, canon,
                 verdicts=_verdict("deflated_sharpe"))
    assert out["counts"][cc.RETIRED] == 0
    assert out["rows"][0]["backing"] == cc.AWAITING
    assert "not this clock" in out["rows"][0]["why"]


def test_a_cell_the_judge_stamped_but_never_ran_is_awaiting_not_rejected(tmp_path, canon):
    out = _audit([_clock("EURUSD.carry.continuous")], set(), tmp_path, canon,
                 verdicts=_verdict("", "NOT_RUN_BUILD_BUDGET_DEFERRED"))
    assert out["rows"][0]["backing"] == cc.AWAITING
    assert out["counts"][cc.RETIRED] == 0


def test_a_pass_the_canon_has_not_caught_up_with_keeps_the_clock(tmp_path, canon):
    out = _audit([_clock("EURUSD.carry.continuous")], set(), tmp_path, canon,
                 verdicts=_verdict("expected_value", "PASSED", passed=True))
    assert out["rows"][0]["backing"] == cc.AWAITING
    assert "certificate lane" in out["rows"][0]["why"]


# ------------------------------------------------------------------------------- the ageing
def test_breach_age_is_measured_from_the_ledger_not_from_this_pass(tmp_path, canon):
    led = tmp_path / "breach.json"
    old = (datetime.now(UTC) - timedelta(hours=5)).isoformat()
    led.write_text(json.dumps({"first_seen": {"EURUSD.carry": old}}), encoding="utf-8")
    v = tmp_path / "verdicts.jsonl"
    v.write_text("", encoding="utf-8")
    out = cc.audit([_clock("EURUSD.carry.continuous")], roster=set(), apply=False,
                   canon_path=canon, verdict_path=v, ledger_path=led,
                   queue_path=tmp_path / "q.jsonl")
    assert out["rows"][0]["breach_age_s"] > 4 * 3600
    assert out["overdue_beyond_one_judging_cycle"] == 1


def test_the_breach_ratchet_only_falls(tmp_path):
    led = tmp_path / "breach.json"
    assert cc.ratchet(40, led)["lowest_breached"] == 40
    assert cc.ratchet(12, led)["lowest_breached"] == 12
    assert cc.ratchet(30, led)["lowest_breached"] == 12       # it may never rise
    assert cc.read_ratchet(led)["last_breached"] == 30


# --------------------------------------------------------------------------------- the fence
_CERT = {"breached": 400, "awaiting": 400, "backed": 5, "retired": 10,
         "overdue_beyond_one_judging_cycle": 0, "judging_cycle_s": 3600.0,
         "ratchet": {"lowest_breached": 400}, "queue": {"submitted": 400, "already_queued": 0}}


def test_the_fence_fails_on_breach_age_and_never_on_breach_count():
    """A fence that went red on the COUNT would pressure a session into retiring clocks to get
    green -- destroying the evidence the law exists to gather."""
    ok = fence.judge(_report(_CERT), {"lowest_frozen": 0}, require_state=True)
    assert ok["verdict"] == fence.OK, ok["findings"]
    overdue = {**_CERT, "overdue_beyond_one_judging_cycle": 3, "oldest_breach_age_s": 20000.0}
    out = fence.judge(_report(overdue), {"lowest_frozen": 0}, require_state=True)
    assert out["verdict"] == fence.FAIL
    assert any("UNCERTIFIED" in f for f in out["findings"])
    assert any("the remedy is the judge, not the clock" in f for f in out["findings"])


def test_the_fence_fails_when_the_breach_ratchet_rises():
    cert = {**_CERT, "breached": 12, "ratchet": {"lowest_breached": 5},
            "queue": {"submitted": 12, "already_queued": 0}}
    out = fence.judge(_report(cert), {"lowest_frozen": 0}, require_state=True)
    assert out["verdict"] == fence.FAIL
    assert any("breach count ROSE" in f for f in out["findings"])


def test_the_fence_fails_when_breaches_reach_no_queue():
    cert = {**_CERT, "breached": 9, "ratchet": {"lowest_breached": 9},
            "queue": {"submitted": 0, "already_queued": 0, "why": "task_queue unimportable"}}
    out = fence.judge(_report(cert), {"lowest_frozen": 0}, require_state=True)
    assert out["verdict"] == fence.FAIL
    assert any("not a remedy" in f for f in out["findings"])


def test_judging_throughput_honours_the_breach_docket(tmp_path, monkeypatch):
    """The priority is decorative unless the judge is SIZED to reach the front of its queue."""
    from desks.mt5.research import judging_throughput as jt
    d = tmp_path / "CLOCK_CERTIFICATE_BREACH.json"
    d.write_text(json.dumps({"breached": 71, "overdue_beyond_one_judging_cycle": 4}),
                 encoding="utf-8")
    monkeypatch.setattr(jt, "BREACH_DOCKET", d)
    monkeypatch.setattr(jt, "BACKPRESSURE", tmp_path / "absent.json")
    q = jt.measure_queue()
    assert q["clock_breach_cells"] == 71
    assert q["clock_breach_overdue"] == 4
    plan = jt.plan({"cores": 4, "reserved_cores": 1, "free_mb": 8000, "commit_free_mb": 8000,
                    "terminal": {}}, q, jt.declared_costs())
    assert plan["queue_deep"] is True
    assert plan["limiting_resource"] == "clock_certificate_breach"
