"""THE PROPERTY: EVERY LEG RUNS INSIDE A BOUNDED NUMBER OF PASSES, AND THE REST ARE NAMED.

These tests pin the behaviour that 19 of 112 CORE_LEGS having never executed once was allowed to
be. The interesting ones are not the unit checks -- they are `test_every_leg_runs_within_bounded_
passes`, which simulates the rotation until the roster is exhausted and fails if any leg is still
dark, and `test_rotation_never_shrinks_the_roster`, which pins the principal's standing order that
the cure is never "attempt less".
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.ops import leg_rotation as LR

ROOT = Path(__file__).resolve().parents[2]


def _att(runs: dict[str, int], *, ages_h: dict[str, float] | None = None,
         costs: dict[str, float] | None = None,
         now: datetime | None = None) -> LR.Attendance:
    t0 = now or datetime.now(tz=UTC)
    ages = ages_h or {}
    att = LR.Attendance(runs=dict(runs))
    for leg, n in runs.items():
        if n > 0:
            att.last_at[leg] = (t0 - timedelta(hours=ages.get(leg, 1.0))).isoformat()
    for leg, c in (costs or {}).items():
        att.costs[leg] = [c]
    return att


def test_roster_is_read_from_the_real_cycle_by_ast() -> None:
    """The roster is the cycle's own call sites, never a second list that can drift from it."""
    legs = LR.legs_in_order()
    assert len(legs) > 200, f"expected the full cycle roster, got {len(legs)}"
    # The legs this whole exercise was about must be in it, and in file order.
    for leg in ("record_tape", "clock_liveness", "producer_census", "publish_state"):
        assert leg in legs, f"{leg} missing from the derived roster"
    assert legs.index("record_tape") < legs.index("publish_state")
    assert len(legs) == len(set(legs)), "a leg is rostered twice"


def test_never_run_legs_outrank_every_stale_leg() -> None:
    """A dark leg is admitted ahead of a merely-old one; that is what drains the dark set."""
    roster = ["a", "b", "c", "d"]
    att = _att({"a": 5, "b": 0, "c": 5, "d": 0},
               ages_h={"a": 100.0, "c": 99.0}, costs=dict.fromkeys(roster, 10.0))
    dec = LR.plan_pass(roster, att, plan="core", budget_s=20.0)
    assert dec.admitted == {"b", "d"}, "the two never-run legs must take the whole budget"
    assert dec.never_run == ["b", "d"]


def test_always_run_legs_are_never_rotated_out() -> None:
    """Tick capture is irreversible and promotion is a standing order: neither may be deferred."""
    roster = ["record_tape", "promoter", "filler"]
    att = _att({"record_tape": 9, "promoter": 9, "filler": 0},
               costs={"record_tape": 9_000.0, "promoter": 9_000.0, "filler": 1.0})
    dec = LR.plan_pass(roster, att, plan="core", budget_s=1.0)
    assert {"record_tape", "promoter"} <= dec.admitted
    assert not ({"record_tape", "promoter"} & dec.deferred)
    for leg in LR.ALWAYS_RUN:
        ok, _ = dec.should_run(leg, att, elapsed_s=10_000.0)
        assert ok, f"{leg} was yielded on overrun; it is in the always-run set"


def test_overrun_yields_to_legs_that_have_never_run() -> None:
    """Estimates are wrong; when the pass runs long, the legs that pay must not be the dark ones."""
    roster = ["old", "dark"]
    att = _att({"old": 3, "dark": 0}, costs={"old": 1.0, "dark": 1.0})
    dec = LR.plan_pass(roster, att, plan="core", budget_s=100.0)
    assert dec.admitted == {"old", "dark"}
    ran_ok, why = dec.should_run("old", att, elapsed_s=500.0)
    assert not ran_ok and "never run" in why
    dark_ok, _ = dec.should_run("dark", att, elapsed_s=500.0)
    assert dark_ok, "a leg that has never run must still get its chance after an overrun"


def test_every_leg_runs_within_bounded_passes() -> None:
    """THE GUARANTEE. Simulate passes; every leg must run, and the dark set must never grow."""
    roster = [f"leg{i:03d}" for i in range(300)]
    att = _att(dict.fromkeys(roster, 0), costs=dict.fromkeys(roster, 30.0))
    now = datetime.now(tz=UTC)
    seen: set[str] = set()
    dark_history: list[int] = []
    passes = 0
    while len(seen) < len(roster):
        passes += 1
        assert passes <= 40, f"unbounded: {len(roster) - len(seen)} legs still dark after {passes}"
        dec = LR.plan_pass(roster, att, plan="core", budget_s=1920.0, now=now)
        dark_history.append(len(dec.never_run))
        assert dec.admitted, "a pass that admits nothing can never drain the roster"
        for leg in dec.admitted:
            att.runs[leg] = att.runs.get(leg, 0) + 1
            att.last_at[leg] = now.isoformat()
            seen.add(leg)
        now += timedelta(hours=1)
    assert seen == set(roster)
    assert dark_history == sorted(dark_history, reverse=True), "the dark set must only shrink"
    assert dark_history[-1] < dark_history[0]


def test_rotation_never_shrinks_the_roster() -> None:
    """NEVER REDUCE AGGRESSIVENESS: deferral is a turn to wait, never a leg removed."""
    roster = [f"leg{i:02d}" for i in range(50)]
    att = _att(dict.fromkeys(roster, 1), costs=dict.fromkeys(roster, 100.0))
    dec = LR.plan_pass(roster, att, plan="core", budget_s=500.0)
    assert dec.admitted | dec.deferred == set(roster), "every leg is admitted or deferred"
    assert not (dec.admitted & dec.deferred), "a leg cannot be both"
    assert set(dec.roster) == set(roster)


def test_unbounded_plan_defers_nothing() -> None:
    """The department residents carry no time limit; rotating there would be a throttle."""
    roster = ["a", "b", "c"]
    att = _att({"a": 1, "b": 1, "c": 1}, costs=dict.fromkeys(roster, 10_000.0))
    dec = LR.plan_pass(roster, att, plan="dept:intel", budget_s=0.0)
    assert dec.deferred == set()
    assert dec.admitted == set(roster)


def test_budget_for_reads_the_schedulers_limit_not_its_own() -> None:
    assert LR.budget_for("core", env={}) == pytest.approx(2400.0 * LR.BUDGET_FILL)
    assert LR.budget_for("dept:meta", env={}) == 0.0
    assert LR.budget_for("core", env={"HOURLY_BUDGET_S": "600"}) == pytest.approx(600.0)
    assert LR.budget_for("core", env={"HOURLY_BUDGET_S": "nonsense"}) > 0.0


def test_attendance_folds_the_ledger_incrementally(tmp_path: Path) -> None:
    led = tmp_path / "compute_ledger.jsonl"
    rows = [{"at": "2026-09-23T10:00:00+00:00", "run": "alpha", "wall_s": 3.0},
            {"at": "2026-09-23T10:01:00+00:00", "run": "beta", "wall_s": 7.0}]
    led.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    att = LR.read_attendance(led)
    assert att.runs == {"alpha": 1, "beta": 1}
    assert att.cost_s("alpha") == pytest.approx(3.0)
    assert att.cost_s("never_seen") == LR.UNKNOWN_LEG_COST_S
    with led.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": "2026-09-23T11:00:00+00:00", "run": "alpha",
                             "wall_s": 5.0}) + "\n")
    att2 = LR.read_attendance(led, prior=att)
    assert att2.runs["alpha"] == 2, "the second read must add to the first, not replace it"
    assert att2.last_at["alpha"].startswith("2026-09-23T11:00")


def test_truncated_ledger_forces_a_full_reread(tmp_path: Path) -> None:
    """A rotated ledger must never leave attendance claiming every leg is starved."""
    led = tmp_path / "compute_ledger.jsonl"
    led.write_text(json.dumps({"at": "2026-09-23T10:00:00+00:00", "run": "alpha",
                               "wall_s": 1.0}) + "\n", encoding="utf-8")
    att = LR.read_attendance(led)
    att.offset = 10_000_000
    again = LR.read_attendance(led, prior=att)
    assert again.runs.get("alpha") == 1


def test_record_publishes_never_run_by_name(tmp_path: Path) -> None:
    roster = ["ran", "dark"]
    att = _att({"ran": 4, "dark": 0}, costs={"ran": 1.0, "dark": 1.0})
    dec = LR.plan_pass(roster, att, plan="core", budget_s=100.0)
    out = tmp_path / "LEG_ROTATION.json"
    doc = LR.record(dec, att, ["ran"], path=out)
    assert doc["never_run"] == ["dark"]
    on_disk = json.loads(out.read_text(encoding="utf-8"))
    assert on_disk["never_run"] == ["dark"]
    assert on_disk["pass_complete"] is True
    assert LR.load_record(out)["never_run"] == ["dark"]


def test_fence_fails_on_a_never_run_leg_and_on_an_absent_record(tmp_path: Path) -> None:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_check_leg_rotation", ROOT / "scripts" / "check_leg_rotation.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    absent = mod.check(tmp_path / "nope.json")
    assert not absent["ok"], "an absent record is UNMEASURED, which is never a pass"

    rec = tmp_path / "LEG_ROTATION.json"
    rec.write_text(json.dumps({"generated": datetime.now(tz=UTC).isoformat(),
                               "never_run": ["clock_liveness"], "outside_window": [],
                               "window_h": 24.0, "n_roster": 300}), encoding="utf-8")
    bad = mod.check(rec)
    assert not bad["ok"] and bad["n_never_run"] == 1
    assert any("clock_liveness" in f for f in bad["failures"])

    rec.write_text(json.dumps({"generated": datetime.now(tz=UTC).isoformat(),
                               "never_run": [], "outside_window": [],
                               "window_h": 24.0, "n_roster": 300}), encoding="utf-8")
    assert mod.check(rec)["ok"]

    stale = datetime.now(tz=UTC) - timedelta(hours=9)
    rec.write_text(json.dumps({"generated": stale.isoformat(), "never_run": [],
                               "outside_window": [], "window_h": 24.0}), encoding="utf-8")
    assert not mod.check(rec)["ok"], "a stale record means the cycle is not running on its clock"
