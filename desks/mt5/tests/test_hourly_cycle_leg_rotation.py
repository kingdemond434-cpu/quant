"""POSITION MUST NOT DECIDE WHETHER A LEG RUNS.

Measured 2026-09-23 from the compute ledger: 19 of 112 CORE_LEGS had never executed once, because
`main()` runs ~325 legs front to back and the task that owns the core plan allows 40 minutes. The
tail was not late, it was unreachable, and the same legs were skipped every hour.

These tests pin the two halves of the cure inside the cycle itself: `_costed` is the ONE boundary
every leg passes through, so a rotated-out leg must return there in microseconds and leave no
ledger row; and the always-run set must consist of legs that actually exist, because a typo there
is protection that silently is not applied.
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hourly_cycle  # noqa: E402

from libs.ops import leg_rotation as LR  # noqa: E402


def _install(monkeypatch, admitted: set[str], deferred: set[str],
             att: LR.Attendance | None = None) -> LR.Decision:
    dec = LR.Decision(plan="core", budget_s=100.0, admitted=set(admitted),
                      deferred=set(deferred), roster=sorted(admitted | deferred))
    dec.why = dict.fromkeys(deferred, "deferred for this test")
    state = {"built": True, "decision": dec, "lr": LR,
             "attendance": att or LR.Attendance(), "started": datetime.now(tz=UTC), "ran": []}
    monkeypatch.setattr(hourly_cycle, "_ROTATION", state, raising=False)
    return dec


def test_a_rotated_out_leg_does_not_run_and_leaves_no_ledger_row(monkeypatch) -> None:
    """A deferred leg must cost nothing: that is what lets the pass reach its own tail."""
    monkeypatch.setattr(hourly_cycle, "HOURLY_PLAN", "all", raising=False)
    _install(monkeypatch, admitted=set(), deferred={"some_leg"})
    calls: list[str] = []
    rows: list[str] = []
    monkeypatch.setattr(hourly_cycle, "_emit_leg", lambda *a, **k: rows.append("row"),
                        raising=False)

    out = hourly_cycle._costed("some_leg", lambda: calls.append("ran") or {"status": "OK"})

    assert out["status"] == "ROTATED_OUT"
    assert calls == [], "a rotated-out leg must not be executed"
    assert rows == [], "a rotated-out leg must not be recorded as having run"
    assert "deferred for this test" in out["why"]


def test_an_admitted_leg_still_runs_and_is_counted(monkeypatch) -> None:
    monkeypatch.setattr(hourly_cycle, "HOURLY_PLAN", "all", raising=False)
    _install(monkeypatch, admitted={"some_leg"}, deferred=set())
    calls: list[str] = []

    out = hourly_cycle._costed("some_leg", lambda: calls.append("ran") or {"status": "OK"})

    assert calls == ["ran"]
    assert out.get("status") != "ROTATED_OUT"
    assert "some_leg" in hourly_cycle._ROTATION["ran"]


def test_rotation_never_overrides_the_plan(monkeypatch) -> None:
    """SKIPPED_BY_PLAN still wins: rotation decides WITHIN a plan, it does not widen one."""
    monkeypatch.setattr(hourly_cycle, "HOURLY_PLAN", "core", raising=False)
    _install(monkeypatch, admitted={"definitely_not_core"}, deferred=set())
    out = hourly_cycle._costed("definitely_not_core", lambda: {"status": "OK"})
    assert out["status"] == "SKIPPED_BY_PLAN"


def test_a_broken_rotation_never_stops_a_leg(monkeypatch) -> None:
    """A scheduler that can be taken down by the thing measuring it is worse than no measurement."""
    monkeypatch.setattr(hourly_cycle, "HOURLY_PLAN", "all", raising=False)
    monkeypatch.setattr(hourly_cycle, "_ROTATION", {}, raising=False)
    monkeypatch.setattr(hourly_cycle, "_rotation", lambda: None, raising=False)
    calls: list[str] = []
    hourly_cycle._costed("some_leg", lambda: calls.append("ran") or {"status": "OK"})
    assert calls == ["ran"], "with no rotation available every leg must run as before"


def test_every_always_run_leg_is_a_real_leg_of_this_cycle() -> None:
    """A typo in ALWAYS_RUN is protection that silently does not apply to anything."""
    roster = set(LR.legs_in_order(DESK / "research" / "hourly_cycle.py"))
    missing = sorted(LR.ALWAYS_RUN - roster)
    assert not missing, f"ALWAYS_RUN names legs this cycle does not have: {missing}"


def test_every_core_leg_has_a_call_site_the_rotation_can_see() -> None:
    """The roster is derived from the AST; a CORE leg it cannot see is a leg it cannot rotate."""
    roster = set(LR.legs_in_order(DESK / "research" / "hourly_cycle.py"))
    unseen = sorted(set(hourly_cycle.CORE_LEGS) - roster)
    assert not unseen, f"CORE_LEGS with no _costed call site the rotation can find: {unseen}"


def test_the_sixteen_that_were_dark_are_on_the_roster() -> None:
    """The legs this whole exercise was about must be rotatable, by name."""
    roster = set(LR.legs_in_order(DESK / "research" / "hourly_cycle.py"))
    dark = {"source_drain", "source_evig", "timeframe_fanout", "cycle_pricing", "clock_ledger",
            "clock_liveness", "fill_recorder", "evidence_chain", "quantbench", "destroyer_pool",
            "meta_rnd", "shortfall_model", "actor_pressure", "causal_invariance",
            "counterfactual_timeframes", "producer_census"}
    assert dark <= roster, f"not rostered: {sorted(dark - roster)}"
    assert dark <= set(hourly_cycle.CORE_LEGS), "these are core legs and must stay core"
