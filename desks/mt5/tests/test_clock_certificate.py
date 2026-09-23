"""CLOCK IF AND ONLY IF CERTIFICATE -- strict, and these tests pin what that does and does not mean.

The rule: a forward clock exists only while a canonical certificate backs it, and an unbacked
clock is retired on the pass it is found. The tests that matter are the ones that stop the two
wrong implementations. It must not keep an unbacked clock alive "until the judge gets to it" --
that was the power-cure lane the principal abolished, and it bought forward evidence the desk can
never cash. And it must not quietly drop the cell: losing a clock is NOT losing priority, so the
cell stays at the FRONT of the judge's queue. An empty canon still declares nothing, because a
canon that cannot be read cannot convict.
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


def test_a_clock_with_no_certificate_is_retired_naming_its_cell(tmp_path, canon):
    out = _audit([_clock("EURUSD.carry.continuous")], set(), tmp_path, canon)
    assert out["breached"] == 1
    assert out["rows"][0]["cell"] == "EURUSD.carry"
    assert out["retire"][0]["retired_reason"] == "NO_CERTIFICATE"
    assert out["awaiting"] == 0


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
def test_a_cell_that_loses_its_clock_keeps_the_front_of_the_judges_queue(tmp_path, canon):
    """Losing a clock is not losing priority: judging the cell is the only thing that can give
    it a clock back, so it is still submitted at the maximum priority in the queue."""
    out = _audit([_clock("EURUSD.carry.continuous")], set(), tmp_path, canon, apply=True)
    assert out["queue"]["submitted"] == 1
    from libs.ops.task_queue import TaskQueue
    tasks = list(TaskQueue(tmp_path / "q.jsonl").tasks().values())
    assert tasks[0].kind == "recertify"
    assert tasks[0].priority == cc.BREACH_PRIORITY
    assert tasks[0].dedupe_key == "clock_breach:EURUSD.carry"


def test_there_is_no_awaiting_judgement_state_left(tmp_path, canon):
    """The power-cure lane is abolished: no clock may wait for the judge while accruing."""
    out = _audit([_clock("EURUSD.carry.continuous"),
                  _clock("GBPUSD.carry.continuous")], set(), tmp_path, canon)
    assert out["awaiting"] == 0
    assert out["counts"][cc.AWAITING] == 0
    assert len(out["retire"]) == 2
    assert "restarts from zero" in out["cost"]


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


def test_a_parameter_independent_reject_is_recorded_as_the_reason(tmp_path, canon):
    """The clock goes either way under the strict rule; what the judge's own verdict buys is a
    truthful REASON on the retired row -- rejected at a named gate, not merely uncertified."""
    out = _audit([_clock("EURUSD.carry.continuous")], set(), tmp_path, canon,
                 verdicts=_verdict("economic_prior", "NOT_RUN_TERMINAL_GATE_1_REJECT"))
    assert out["retire"][0]["retired_reason"] == "JUDGE_REJECTED"
    assert "economic_prior" in out["retire"][0]["why"]


def test_a_parameter_dependent_reject_is_not_used_as_the_reason(tmp_path, canon):
    """The clock goes either way now -- what the sibling verdict must not do is be RECORDED as
    this cell's rejection, because the judge never ruled on this parameterization."""
    out = _audit([_clock("EURUSD.carry.continuous")], set(), tmp_path, canon,
                 verdicts=_verdict("deflated_sharpe"))
    assert out["retire"][0]["retired_reason"] == "NO_CERTIFICATE"
    assert "deflated_sharpe" not in str(out["retire"][0]["why"])


def test_a_cell_the_judge_never_ran_loses_its_clock_for_want_of_a_certificate(tmp_path, canon):
    out = _audit([_clock("EURUSD.carry.continuous")], set(), tmp_path, canon,
                 verdicts=_verdict("", "NOT_RUN_BUILD_BUDGET_DEFERRED"))
    assert out["retire"][0]["retired_reason"] == "NO_CERTIFICATE"
    assert out["queue"]["applied"] is False      # dry run here; the live pass queues it first


def test_only_the_canon_grants_a_clock_never_a_lane_declaring_its_own_pass(tmp_path, canon):
    """A gate ledger row saying `passed` is not a certificate. Only entry into the canonical
    store creates a clock -- that is what `if and only if` forbids."""
    out = _audit([_clock("EURUSD.carry.continuous")], set(), tmp_path, canon,
                 verdicts=_verdict("expected_value", "PASSED", passed=True))
    assert out["backed"] == 0
    assert out["retire"][0]["retired_reason"] == "NO_CERTIFICATE"


# ------------------------------------------------------------------------------- the ageing
def test_breach_age_is_still_published_from_the_ledger_for_the_record(tmp_path, canon):
    """The age no longer gates anything -- nothing survives to age -- but a cell that keeps
    coming back uncertified is worth seeing, so the first-seen ledger is still published."""
    led = tmp_path / "breach.json"
    old = (datetime.now(UTC) - timedelta(hours=5)).isoformat()
    led.write_text(json.dumps({"first_seen": {"EURUSD.carry": old}}), encoding="utf-8")
    v = tmp_path / "verdicts.jsonl"
    v.write_text("", encoding="utf-8")
    out = cc.audit([_clock("EURUSD.carry.continuous")], roster=set(), apply=False,
                   canon_path=canon, verdict_path=v, ledger_path=led,
                   queue_path=tmp_path / "q.jsonl")
    assert out["rows"][0]["breach_age_s"] > 4 * 3600
    assert out["overdue_beyond_one_judging_cycle"] == 0      # no tolerance to outlive


def test_the_breach_ratchet_only_falls(tmp_path):
    led = tmp_path / "breach.json"
    assert cc.ratchet(40, led)["lowest_breached"] == 40
    assert cc.ratchet(12, led)["lowest_breached"] == 12
    assert cc.ratchet(30, led)["lowest_breached"] == 12       # it may never rise
    assert cc.read_ratchet(led)["last_breached"] == 30


# --------------------------------------------------------------------------------- the fence
_CERT = {"breached": 95, "awaiting": 0, "backed": 55, "retired": 434, "unbacked_live": 0,
         "overdue_beyond_one_judging_cycle": 0, "judging_cycle_s": 3600.0,
         "ratchet": {"lowest_breached": 95}, "queue": {"submitted": 71, "already_queued": 0}}


def test_the_fence_fails_on_any_unbacked_clock_at_all():
    """Strict: there is no tolerance and no ageing window, because an unbacked clock is retired
    on the pass it is found. A clean pass leaves zero, so anything else is the law broken."""
    ok = fence.judge(_report(_CERT), {"lowest_frozen": 0}, require_state=True)
    assert ok["verdict"] == fence.OK, ok["findings"]
    live = {**_CERT, "unbacked_live": 1}
    out = fence.judge(_report(live), {"lowest_frozen": 0}, require_state=True)
    assert out["verdict"] == fence.FAIL
    assert any("NO canonical certificate" in f for f in out["findings"])


def test_the_fence_rejects_the_return_of_the_awaiting_lane():
    out = fence.judge(_report({**_CERT, "awaiting": 4}), {"lowest_frozen": 0},
                      require_state=True)
    assert out["verdict"] == fence.FAIL
    assert any("must not come back" in f for f in out["findings"])


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
