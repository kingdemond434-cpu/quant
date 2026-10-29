"""THE PROPERTY: EVERY LEG RUNS INSIDE A BOUNDED NUMBER OF PASSES, AND THE REST ARE NAMED.

These tests pin the behaviour that 19 of 112 CORE_LEGS having never executed once was allowed to
be. The interesting ones are not the unit checks -- they are `test_every_leg_runs_within_bounded_
passes`, which simulates the rotation until the roster is exhausted and fails if any leg is still
dark, and `test_rotation_never_shrinks_the_roster`, which pins the principal's standing order that
the cure is never "attempt less".
"""
from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.ops import leg_rotation as LR

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _no_live_resident_queue(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`record` reads the department residents' queue; a test never reads the box's live one."""
    monkeypatch.setattr(LR, "RESIDENT_LOCKS", tmp_path / "_resident_locks")


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
    # Above CHEAP_LEG_S on purpose: a cheap leg is never yielded (see the starvation tests).
    att = _att({"old": 3, "dark": 0}, costs={"old": 30.0, "dark": 30.0})
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

    # No `liveness` block: UNMEASURED, which fails (L1.28a) -- it no longer reads as a pass.
    rec.write_text(json.dumps({"generated": datetime.now(tz=UTC).isoformat(),
                               "never_run": [], "outside_window": [],
                               "window_h": 24.0, "n_roster": 300}), encoding="utf-8")
    unmeasured = mod.check(rec)
    assert not unmeasured["ok"] and unmeasured["liveness"] == "UNMEASURED"
    assert any("UNMEASURED" in f for f in unmeasured["failures"])

    rec.write_text(json.dumps({"generated": datetime.now(tz=UTC).isoformat(),
                               "never_run": [], "outside_window": [],
                               "liveness": {"verdict": "GREEN", "red_legs": []},
                               "window_h": 24.0, "n_roster": 300}), encoding="utf-8")
    assert mod.check(rec)["ok"]

    stale = datetime.now(tz=UTC) - timedelta(hours=9)
    rec.write_text(json.dumps({"generated": stale.isoformat(), "never_run": [],
                               "outside_window": [], "window_h": 24.0}), encoding="utf-8")
    assert not mod.check(rec)["ok"], "a stale record means the cycle is not running on its clock"


# ------------------------------------------------------------------------------------------------
# THE 2026-10-29 STARVATION, REPRODUCED. The always-run set alone was charged 3,749 s against a
# 2,640 s budget (`tier_s` at its 1,500 s LEG_TIMEOUT every pass, `smoke_release` at 120 s), so
# `spent + cost <= budget` was false for EVERY other leg: `clock_ledger` (~1 s) went four days
# unadmitted under a "1s would pass the 2640s budget ... it leads the next pass" line, and
# `prop_challenge_allocator` never ran. These pin the class closed.
# ------------------------------------------------------------------------------------------------

BOX_BUDGET_S = 2640.0
#: The always-run set as the box measured it: 1500 + 120 + 2129 = 3749 s, past the budget alone.
HEAVY_ALWAYS = {"tier_s": 1500.0, "smoke_release": 120.0, "forward_reconcile": 2129.0}


def _load(path: Path, name: str) -> object:
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _prior(started: datetime, starve: dict[str, int], declared: list[str],
           plan: str = "core") -> dict:
    """A previous record in the published shape: per-plan ageing state, declared roster."""
    return {"generated": started.isoformat(), "declared": list(declared),
            "ageing": {plan: {"generated": started.isoformat(),
                              "pass_started": started.isoformat(),
                              "starve_passes": dict(starve), "red": {}}}}


def _box_roster() -> tuple[list[str], LR.Attendance, datetime]:
    """Heavy always-run legs FIRST, then a cheap leg, a never-run money leg, a chronic-timeout
    non-always leg and twenty ordinary ones -- the shape of the box on 2026-10-29."""
    now = datetime(2026, 10, 29, 14, 0, tzinfo=UTC)
    ordinary = [f"organ{i:02d}" for i in range(20)]
    roster = [*HEAVY_ALWAYS, "clock_ledger", "prop_challenge_allocator", "slow_timeout",
              *ordinary]
    costs = {**HEAVY_ALWAYS, "clock_ledger": 1.2, "slow_timeout": 1400.0,
             **dict.fromkeys(ordinary, 300.0)}
    runs = {**dict.fromkeys(roster, 40), "prop_challenge_allocator": 0}
    att = _att(runs, ages_h=dict.fromkeys(roster, 1.0), costs=costs, now=now)
    att.timeouts = {"tier_s": 9, "slow_timeout": 9}
    return roster, att, now


def _simulate(roster: list[str], att: LR.Attendance, now: datetime, tmp_path: Path,
              passes: int, prior: dict | None = None) -> tuple[list[LR.Decision], dict]:
    """Run `passes` hourly passes, each admitted leg actually running, the record chained."""
    out = tmp_path / "LEG_ROTATION.json"
    decisions: list[LR.Decision] = []
    doc = prior
    t = now
    for _ in range(passes):
        dec = LR.plan_pass(roster, att, plan="core", budget_s=BOX_BUDGET_S, now=t, prior=doc)
        ran = [leg for leg in roster if leg in dec.admitted]
        for leg in ran:
            att.runs[leg] = att.runs.get(leg, 0) + 1
            att.last_at[leg] = (t + timedelta(minutes=1)).isoformat(timespec="seconds")
        doc = LR.record(dec, att, ran, path=out, started=t, now=t + timedelta(minutes=50))
        decisions.append(dec)
        t += timedelta(hours=1)
    return decisions, doc or {}


def test_reproduces_and_ends_the_2026_10_29_starvation(tmp_path: Path) -> None:
    roster, att, now = _box_roster()
    first = LR.plan_pass(roster, att, plan="core", budget_s=BOX_BUDGET_S, now=now)
    always_cost = sum(HEAVY_ALWAYS.values())
    assert always_cost > BOX_BUDGET_S, "the reproduction needs the always-run set past budget"
    # THE CHEAP LEG IS ADMITTED EVEN THOUGH THE BUDGET IS ALREADY GONE. Before the fix this was
    # "deferred this pass: 1s would pass the 2640s budget (3749s planned)".
    assert "clock_ledger" in first.admitted and "clock_ledger" in first.protected
    # The box adopts this code mid-flight: its last record predates `starve_passes`.
    adoption = {"generated": (now - timedelta(minutes=30)).isoformat(), "elapsed_s": 0.0}
    decisions, _ = _simulate(roster, att, now, tmp_path, passes=16, prior=adoption)
    # This roster is OVERSUBSCRIBED (6,000 s of organs, no budget left after the always-run set),
    # and the rotation must SAY so rather than promise a bound it cannot keep ...
    cap = decisions[0].capacity
    assert cap["oversubscribed"] is True
    bound = math.ceil(cap["passes_to_cover"]) + LR.MAX_DEFERRALS
    streak: dict[str, int] = dict.fromkeys(roster, 0)
    worst: dict[str, int] = dict.fromkeys(roster, 0)
    for dec in decisions:
        assert "clock_ledger" in dec.admitted, "a cheap leg must be admitted every pass"
        assert dec.aged or not dec.queued, "the ageing queue must drain even with no budget"
        for leg in roster:
            streak[leg] = streak[leg] + 1 if leg in dec.deferred else 0
            worst[leg] = max(worst[leg], streak[leg])
    # ... and still run every leg within the bound its own capacity line states: no livelock.
    over = {leg: n for leg, n in worst.items() if n > bound}
    assert not over, f"legs deferred past the stated {bound}-pass catch-up bound: {over}"
    ran = set().union(*(d.admitted for d in decisions))
    assert ran == set(roster), f"never admitted in 16 passes: {set(roster) - ran}"
    assert "prop_challenge_allocator" in decisions[0].admitted, "never run: aged in at once"
    assert "prop_challenge_allocator" in decisions[0].red, "and named RED until it has run"
    assert decisions[-1].red, "an oversubscribed plan is RED by name, never quietly late"


def test_deferral_ages_into_unconditional_admission(tmp_path: Path) -> None:
    """With no room at all, a leg is deferred at most MAX_DEFERRALS passes, then admitted."""
    roster = ["tier_s", "waiter"]
    now = datetime(2026, 10, 29, tzinfo=UTC)
    att = _att({"tier_s": 5, "waiter": 5}, costs={"tier_s": 5000.0, "waiter": 200.0}, now=now)
    decisions, doc = _simulate(roster, att, now, tmp_path, passes=LR.MAX_DEFERRALS + 1,
                               prior=_prior(now - timedelta(hours=1), {"waiter": 0}, roster))
    states = ["waiter" in d.admitted for d in decisions]
    assert states == [False] * LR.MAX_DEFERRALS + [True], states
    last = decisions[-1]
    assert "waiter" in last.aged and "aged" in last.why["waiter"]
    assert doc["starve_passes"]["waiter"] == LR.MAX_DEFERRALS
    assert "it leads the next pass" not in json.dumps(doc["why"]), "the false promise is gone"


def test_aged_and_cheap_legs_are_not_yielded_on_overrun() -> None:
    """tier_s timing out early puts the clock past budget for the rest of the pass; the aged and
    cheap legs it admitted must still run, or admission is a promise the runtime breaks."""
    roster = ["tier_s", "cheap", "aged", "plain"]
    att = _att({"tier_s": 5, "cheap": 5, "aged": 5, "plain": 5},
               costs={"tier_s": 1500.0, "cheap": 0.5, "aged": 300.0, "plain": 30.0})
    prior = _prior(datetime.now(tz=UTC) - timedelta(hours=1),
                   {"aged": LR.MAX_DEFERRALS, "cheap": 0, "plain": 0}, roster)
    att.last_at = dict.fromkeys(roster, "2020-01-01T00:00:00+00:00")
    dec = LR.plan_pass(roster, att, plan="core", budget_s=2000.0, prior=prior)
    assert {"cheap", "aged"} <= dec.protected
    for leg in ("cheap", "aged", "tier_s"):
        ok, why = dec.should_run(leg, att, elapsed_s=5000.0)
        assert ok, f"{leg} yielded on overrun: {why}"
    ok, why = dec.should_run("plain", att, elapsed_s=5000.0)
    assert not ok and "at most" in why


def test_chronic_timeout_is_ranked_last_not_removed(tmp_path: Path) -> None:
    """A non-always leg timing out every pass cedes its slot to a stale leg, but still ages in."""
    roster = ["slow_timeout", "stale"]
    now = datetime(2026, 10, 29, tzinfo=UTC)
    att = _att({"slow_timeout": 5, "stale": 5}, ages_h={"slow_timeout": 9.0, "stale": 2.0},
               costs={"slow_timeout": 600.0, "stale": 600.0}, now=now)
    att.timeouts = {"slow_timeout": LR.CHRONIC_TIMEOUT_RUNS}
    dec = LR.plan_pass(roster, att, plan="core", budget_s=700.0, now=now)
    assert dec.chronic_timeouts == ["slow_timeout"]
    assert dec.admitted == {"stale"}, "older, but a chronic timeout ranks behind a stale leg"
    assert "CHRONIC TIMEOUT" in dec.why["slow_timeout"]
    decisions, _ = _simulate(roster, att, now, tmp_path, passes=4,
                             prior=_prior(now - timedelta(hours=1), {}, roster))
    assert any("slow_timeout" in d.admitted for d in decisions), "demoted, never removed"


def test_attendance_counts_consecutive_timeouts(tmp_path: Path) -> None:
    led = tmp_path / "compute_ledger.jsonl"
    rows = [{"at": f"2026-10-29T0{i}:00:00+00:00", "run": "tier_s", "wall_s": 1500.0,
             "outcome": "TIMEOUT"} for i in range(LR.CHRONIC_TIMEOUT_RUNS)]
    led.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    att = LR.read_attendance(led)
    assert att.chronic_timeout("tier_s")
    again = LR.Attendance.from_json(json.loads(json.dumps(att.to_json())))
    assert again.chronic_timeout("tier_s"), "the streak must survive the record round trip"
    with led.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": "2026-10-29T09:00:00+00:00", "run": "tier_s",
                             "wall_s": 900.0, "outcome": "ok"}) + "\n")
    assert not LR.read_attendance(led, prior=att).chronic_timeout("tier_s")


def test_adoption_seeds_the_wait_from_attendance_age() -> None:
    """The first pass after this ships reads a record with no `starve_passes`: a leg already dark
    four days, and a never-run one, are admitted on that very pass and named RED."""
    now = datetime(2026, 10, 29, 14, 37, tzinfo=UTC)
    roster = ["tier_s", "clock_ledger_big", "prop_challenge_allocator", "fresh"]
    att = _att({"tier_s": 9, "clock_ledger_big": 9, "prop_challenge_allocator": 0, "fresh": 9},
               ages_h={"tier_s": 0.5, "clock_ledger_big": 104.0, "fresh": 0.5},
               costs={"tier_s": 5000.0, "clock_ledger_big": 120.0, "fresh": 120.0}, now=now)
    old_format = {"generated": (now - timedelta(minutes=20)).isoformat(), "elapsed_s": 0.0,
                  "never_run": ["prop_challenge_allocator"]}
    dec = LR.plan_pass(roster, att, plan="core", budget_s=2640.0, now=now, prior=old_format)
    assert "clock_ledger_big" in dec.aged
    assert "prop_challenge_allocator" in dec.admitted & dec.protected, "money-critical"
    assert "fresh" in dec.deferred
    # The seed is not capped: 104 h dark is RED on the first pass that can see it.
    assert {"clock_ledger_big", "prop_challenge_allocator"} <= set(dec.red)
    assert dec.starve_passes["clock_ledger_big"] == 104


def test_red_names_a_leg_starved_past_the_bound(tmp_path: Path) -> None:
    """Admitted at the bound and STILL not run (pass killed before it): RED, by name, in the
    record, in the fence and in the desk-health checker."""
    now = datetime(2026, 10, 29, 15, 0, tzinfo=UTC)
    roster = ["tier_s", "clock_ledger"]
    att = _att({"tier_s": 9, "clock_ledger": 9}, ages_h={"tier_s": 0.5, "clock_ledger": 100.0},
               costs={"tier_s": 5000.0, "clock_ledger": 1.0}, now=now)
    prior = _prior(now - timedelta(hours=1), {"clock_ledger": LR.MAX_DEFERRALS, "tier_s": 0},
                   roster)
    dec = LR.plan_pass(roster, att, plan="core", budget_s=2640.0, now=now, prior=prior)
    assert dec.starve_passes["clock_ledger"] == LR.RED_AFTER_PASSES
    assert list(dec.red) == ["clock_ledger"], dec.red
    out = tmp_path / "LEG_ROTATION.json"
    doc = LR.record(dec, att, [], path=out, started=now, now=now, complete=False)
    assert doc["liveness"]["verdict"] == "RED"
    assert doc["liveness"]["red_legs"] == ["clock_ledger"]

    fence = _load(ROOT / "scripts" / "check_leg_rotation.py", "_check_leg_rotation_red")
    rep = fence.check(out, now=now)  # type: ignore[attr-defined]
    assert not rep["ok"] and rep["liveness"] == "RED"
    assert any("liveness RED" in f and "clock_ledger" in f for f in rep["failures"])

    health = _load(ROOT / "desks" / "mt5" / "scripts" / "check_desk_health.py", "_cdh_red")
    health._FINDINGS.clear()  # type: ignore[attr-defined]
    health.check_leg_rotation(out)  # type: ignore[attr-defined]
    found = health._FINDINGS  # type: ignore[attr-defined]
    assert [f["level"] for f in found] == ["PROBLEM"]
    assert "clock_ledger" in found[0]["message"]

    # ... and the same leg, run, is GREEN on the next pass.
    att.last_at["clock_ledger"] = (now + timedelta(minutes=2)).isoformat()
    nxt = LR.plan_pass(roster, att, plan="core", budget_s=2640.0,
                       now=now + timedelta(hours=1), prior=doc)
    assert nxt.starve_passes["clock_ledger"] == 0 and not nxt.red
    green = LR.record(nxt, att, ["clock_ledger"], path=out, started=now + timedelta(hours=1),
                      now=now + timedelta(hours=1))
    assert green["liveness"]["verdict"] == "GREEN"
    health._FINDINGS.clear()  # type: ignore[attr-defined]
    health.check_leg_rotation(out)  # type: ignore[attr-defined]
    assert [f["level"] for f in health._FINDINGS] == ["OK"]  # type: ignore[attr-defined]


def test_a_newly_wired_leg_is_not_red_before_it_has_had_a_pass() -> None:
    now = datetime(2026, 10, 29, tzinfo=UTC)
    roster = ["old", "brand_new"]
    att = _att({"old": 3, "brand_new": 0}, costs={"old": 30.0}, now=now)
    prior = _prior(now - timedelta(hours=1), {"old": 0}, ["old"])
    dec = LR.plan_pass(roster, att, plan="core", budget_s=1000.0, now=now, prior=prior)
    assert "brand_new" in dec.never_run and "brand_new" not in dec.red
    prior2 = {**prior, "declared": roster}
    assert "brand_new" in LR.plan_pass(roster, att, plan="core", budget_s=1000.0, now=now,
                                       prior=prior2).red


def test_a_department_pass_cannot_reset_the_core_plans_wait(tmp_path: Path) -> None:
    """Core and the department residents share LEG_ROTATION.json; a dept write in between two
    core passes must neither reset core's counts nor paper over core's RED."""
    now = datetime(2026, 10, 29, 10, tzinfo=UTC)
    out = tmp_path / "LEG_ROTATION.json"
    core = ["tier_s", "waiter"]
    att = _att({"tier_s": 5, "waiter": 5, "dept_leg": 5},
               costs={"tier_s": 5000.0, "waiter": 200.0, "dept_leg": 10.0}, now=now)
    doc = _prior(now - timedelta(hours=1), {"waiter": LR.RED_AFTER_PASSES - 2}, core)
    att.last_at["waiter"] = (now - timedelta(hours=9)).isoformat()
    dec = LR.plan_pass(core, att, plan="core", budget_s=2640.0, now=now, prior=doc)
    assert dec.red == {} and "waiter" in dec.aged
    LR.record(dec, att, [], path=out, started=now, now=now)    # killed: aged waiter never ran
    d2 = LR.plan_pass(["dept_leg"], att, plan="dept:data", budget_s=600.0,
                      now=now + timedelta(minutes=30), prior=LR.load_record(out))
    LR.record(d2, att, ["dept_leg"], path=out, started=now + timedelta(minutes=30))
    rec = LR.load_record(out)
    assert set(rec["ageing"]) == {"core", "dept:data"}
    nxt = LR.plan_pass(core, att, plan="core", budget_s=2640.0, now=now + timedelta(hours=1),
                       prior=rec)
    assert nxt.starve_passes["waiter"] == LR.RED_AFTER_PASSES, "the dept write reset core"
    LR.record(nxt, att, [], path=out, started=now + timedelta(hours=1))
    d3 = LR.plan_pass(["dept_leg"], att, plan="dept:data", budget_s=600.0,
                      now=now + timedelta(hours=1, minutes=30), prior=LR.load_record(out))
    final = LR.record(d3, att, ["dept_leg"], path=out)
    assert final["plan"] == "dept:data" and final["liveness"]["verdict"] == "RED"
    assert final["liveness"]["red_by_plan"] == {"core": ["waiter"]}


def test_money_critical_legs_have_a_hard_staleness_bound() -> None:
    """decay_monitor & co. are admitted every pass, never yielded, RED after one missed pass."""
    now = datetime(2026, 10, 29, tzinfo=UTC)
    money = sorted(LR.MONEY_CRITICAL)
    roster = ["tier_s", *money]
    att = _att(dict.fromkeys(roster, 9), costs={"tier_s": 9000.0, **dict.fromkeys(money, 60.0)},
               now=now)
    dec = LR.plan_pass(roster, att, plan="core", budget_s=100.0, now=now,
                       prior=_prior(now - timedelta(hours=1), dict.fromkeys(money, 0), roster))
    assert set(money) <= dec.admitted
    assert set(money) <= dec.protected | LR.ALWAYS_RUN
    for leg in money:
        assert dec.should_run(leg, att, elapsed_s=99_999.0)[0], leg
    for leg in money:
        att.last_at[leg] = (now - timedelta(hours=5)).isoformat()
    starved = _prior(now - timedelta(hours=1),
                     dict.fromkeys(money, LR.MONEY_MAX_STALE_PASSES), roster)
    red = LR.plan_pass(roster, att, plan="core", budget_s=100.0, now=now, prior=starved).red
    assert set(red) == set(money), red
    assert all("money-critical" in why for why in red.values())


def test_cheap_legs_are_batched_and_still_bounded(tmp_path: Path) -> None:
    """Sixty 10 s legs behind an always-run set already past budget: each pass admits a cheap
    batch inside its allowance, and no cheap leg waits past the ageing bound."""
    now = datetime(2026, 10, 29, tzinfo=UTC)
    cheap = [f"cheap{i:02d}" for i in range(60)]
    roster = ["tier_s", *cheap]
    att = _att(dict.fromkeys(roster, 9), costs={"tier_s": 3749.0, **dict.fromkeys(cheap, 10.0)},
               now=now)
    decisions, _ = _simulate(roster, att, now, tmp_path, passes=6,
                             prior=_prior(now - timedelta(hours=1), dict.fromkeys(roster, 0),
                                          roster))
    allowance = LR.CHEAP_BATCH_FILL * BOX_BUDGET_S
    for dec in decisions:
        assert sum(10.0 for leg in dec.cheap) <= allowance
    streak = dict.fromkeys(cheap, 0)
    for dec in decisions:
        for leg in cheap:
            streak[leg] = streak[leg] + 1 if leg in dec.deferred else 0
            assert streak[leg] <= LR.MAX_DEFERRALS, (leg, streak[leg])


def test_two_hundred_twenty_stale_legs_all_catch_up_under_a_killing_scheduler(
        tmp_path: Path) -> None:
    """THE BOX ON 2026-10-29: 220 roster legs older than 24 h. Adopt the fix, then run passes
    in FILE ORDER under a scheduler that KILLS the pass at its limit. Every leg must run within a
    bounded number of passes, the RED set must drain to empty, and the money legs must hold."""
    now = datetime(2026, 10, 29, 15, 30, tzinfo=UTC)
    money = sorted(LR.MONEY_CRITICAL)
    stale = [f"stale{i:03d}" for i in range(220 - len(money))]
    roster = ["tier_s", "smoke_release", *stale[:100], *money, *stale[100:]]
    costs = {"tier_s": 1500.0, "smoke_release": 120.0, **dict.fromkeys(money, 8.0)}
    for i, leg in enumerate(stale):                  # the box's mix: mostly seconds, some minutes
        costs[leg] = (1.4, 4.8, 9.8, 15.0, 40.0)[i % 5]
    att = _att(dict.fromkeys(roster, 9), costs=costs, now=now,
               ages_h={**dict.fromkeys(roster, 30.0 + 24 * 20), "tier_s": 0.5,
                       "smoke_release": 0.5})
    limit_s = BOX_BUDGET_S / LR.BUDGET_FILL          # what the scheduler actually kills at
    out = tmp_path / "LEG_ROTATION.json"
    doc: dict = {"generated": (now - timedelta(minutes=50)).isoformat(), "elapsed_s": 0.0}
    t = now
    first_ran: dict[str, int] = {}
    reds: list[int] = []
    for n in range(16):
        dec = LR.plan_pass(roster, att, plan="core", budget_s=BOX_BUDGET_S, now=t, prior=doc)
        reds.append(len(dec.red))
        clock, ran = 0.0, []
        for leg in roster:                            # file order, killed at the limit
            if leg not in dec.admitted:
                continue
            if not dec.should_run(leg, att, clock)[0]:
                continue
            if clock + costs[leg] > limit_s:
                break
            clock += costs[leg]
            ran.append(leg)
            att.runs[leg] = att.runs.get(leg, 0) + 1
            att.last_at[leg] = (t + timedelta(seconds=clock)).isoformat(timespec="seconds")
            first_ran.setdefault(leg, n)
        doc = LR.record(dec, att, ran, path=out, started=t, now=t + timedelta(minutes=55),
                        complete=False)
        t += timedelta(hours=1)
    assert reds[0] >= 220 - 2, "every stale roster leg is RED, by name, on adoption"
    assert set(first_ran) == set(roster), f"never ran: {set(roster) - set(first_ran)}"
    cover = doc["capacity"]["passes_to_cover"]
    assert cover is not None and not doc["capacity"]["oversubscribed"]
    # The whole backlog of 220 is aged at once on adoption; the queue serves it in order of wait.
    backlog = sum(costs[leg] for leg in stale) / doc["capacity"]["per_pass_s"]
    assert max(first_ran.values()) + 1 <= math.ceil(backlog) + 1, first_ran
    for leg in money:
        assert first_ran[leg] == 0, f"money-critical {leg} waited behind the backlog"
    assert reds[-1] == 0, f"still RED after catch-up: {sorted(dec.red)}"
    assert doc["liveness"]["n_red"] == 0
    assert doc["capacity"]["passes_to_cover"] is not None


def test_capacity_names_an_oversubscribed_plan() -> None:
    roster = ["tier_s", *[f"big{i}" for i in range(10)]]
    att = _att(dict.fromkeys(roster, 3),
               costs={"tier_s": 2000.0, **{f"big{i}": 1000.0 for i in range(10)}})
    dec = LR.plan_pass(roster, att, plan="core", budget_s=2640.0)
    assert dec.capacity["oversubscribed"] is True
    assert dec.capacity["per_pass_s"] == pytest.approx(max(640.0, LR.AGED_MIN_FILL * 2640.0)
                                                       + LR.CHEAP_BATCH_FILL * 2640.0)


# ------------------------------------------------------------------------------------------------
# THE DEPARTMENT RESIDENTS, SAME CLASS (2026-10-29): ~15 residents finished 1,200-9,231 s passes
# and then sat 3-5 h on "waiting: bounded department slots or older pass(es) ahead", unmeasured.
# ------------------------------------------------------------------------------------------------

def _ticket(locks: Path, dept: str, since: datetime, pid: int | None = None) -> Path:
    import os
    locks.mkdir(parents=True, exist_ok=True)
    ns = int(since.timestamp() * 1e9)
    path = locks / f"dept_wait_{ns}_{pid or os.getpid()}_{dept}.ticket"
    path.touch()
    return path


def _queue(locks: Path, dept: str, pass_s: float, waited_s: float = 0.0) -> None:
    locks.mkdir(parents=True, exist_ok=True)
    (locks / f"dept_queue_{dept}.json").write_text(json.dumps(
        {"dept": dept, "pass_s": pass_s, "waited_s": waited_s, "slots": 3,
         "max_wait_s": 7200.0}), encoding="utf-8")


def test_a_resident_waiting_past_its_bound_is_red_by_name(tmp_path: Path) -> None:
    now = datetime(2026, 10, 29, 16, 0, tzinfo=UTC)
    locks = tmp_path / "locks"
    _ticket(locks, "forest_europe", now - timedelta(hours=4, minutes=10))
    _ticket(locks, "execution", now - timedelta(hours=3))
    _ticket(locks, "intel", now - timedelta(minutes=20))
    for i, dept in enumerate(("execution", "forward", "intel", "validate", "data", "rest",
                              "forest_europe", "forest_japan", "forest_china", "forest_latam",
                              "forest_mena", "forest_korea", "forest_asean", "forest_africa",
                              "forest_oceania")):
        _queue(locks, dept, pass_s=(1200.0, 3000.0, 9231.0)[i % 3])
    res = LR.resident_liveness(locks, now=now)
    assert [w["dept"] for w in res["waiting"]] == ["forest_europe", "execution", "intel"], \
        "the queue is published longest wait first"
    assert set(res["red"]) == {"forest_europe", "execution"}
    assert res["oversubscribed"] is True, "15 passes of up to 9,231 s over 3 slots cannot fit 2 h"
    assert res["expected_wait_s"] > res["max_wait_s"]

    # The SAME liveness block the starved legs use, and the same two readers.
    roster = ["tier_s"]
    att = _att({"tier_s": 3}, costs={"tier_s": 10.0}, now=now)
    dec = LR.plan_pass(roster, att, plan="core", budget_s=100.0, now=now)
    out = tmp_path / "LEG_ROTATION.json"
    doc = LR.record(dec, att, ["tier_s"], path=out, started=now, now=now, residents=res)
    live = doc["liveness"]
    assert live["verdict"] == "RED" and live["red_legs"] == []
    assert live["red_residents"] == ["execution", "forest_europe"] and live["n_red"] == 2
    fence = _load(ROOT / "scripts" / "check_leg_rotation.py", "_check_leg_rotation_res")
    rep = fence.check(out, now=now)  # type: ignore[attr-defined]
    assert not rep["ok"]
    assert any("resident liveness RED" in f and "forest_europe" in f for f in rep["failures"])
    assert not any(f.startswith("leg liveness RED") for f in rep["failures"])
    health = _load(ROOT / "desks" / "mt5" / "scripts" / "check_desk_health.py", "_cdh_res")
    health._FINDINGS.clear()  # type: ignore[attr-defined]
    health.check_leg_rotation(out)  # type: ignore[attr-defined]
    msgs = [f["message"] for f in health._FINDINGS]  # type: ignore[attr-defined]
    assert len(msgs) == 1 and "forest_europe" in msgs[0] and "OVERSUBSCRIBED" in msgs[0]


def test_a_dead_waiters_ticket_is_not_a_red_resident(tmp_path: Path, monkeypatch) -> None:
    now = datetime(2026, 10, 29, tzinfo=UTC)
    locks = tmp_path / "locks"
    _ticket(locks, "ghost", now - timedelta(hours=9), pid=4_000_000)
    monkeypatch.setattr(LR, "_pid_alive", lambda pid: pid != 4_000_000)
    res = LR.resident_liveness(locks, now=now)
    assert res["red"] == {} and res["n_waiting"] == 0


def test_an_absent_queue_is_green_and_never_raises(tmp_path: Path) -> None:
    res = LR.resident_liveness(tmp_path / "nope")
    assert res["red"] == {} and res["expected_wait_s"] is None and not res["oversubscribed"]


def test_money_critical_is_additive_to_always_run(monkeypatch) -> None:
    """A leg in BOTH sets (decay_monitor once it moves to ALWAYS_RUN) is charged once."""
    monkeypatch.setattr(LR, "ALWAYS_RUN", LR.ALWAYS_RUN | {"decay_monitor"})
    roster = ["decay_monitor", "other"]
    att = _att({"decay_monitor": 3, "other": 3}, costs={"decay_monitor": 40.0, "other": 50.0})
    dec = LR.plan_pass(roster, att, plan="core", budget_s=100.0)
    assert dec.planned_s == pytest.approx(90.0), "charged once, not twice"
    assert "always-run" in dec.why["decay_monitor"]
    assert dec.capacity["always_run_s"] == pytest.approx(40.0)
    assert dec.capacity["money_critical_s"] == pytest.approx(0.0)


def test_every_money_critical_leg_is_a_real_leg_of_the_cycle() -> None:
    legs = set(LR.legs_in_order())
    assert legs >= LR.MONEY_CRITICAL, f"not in the cycle: {sorted(LR.MONEY_CRITICAL - legs)}"


def test_stale_report_publishers_are_red_after_one_missed_pass() -> None:
    """2026-10-29: PRODUCER_YIELD, CERTIFICATE_CLOCK_LAW (11:4xZ) and JUDGING_THROUGHPUT (14:18Z)
    went stale. Their publishers carry the hard 1-pass bound: admitted every pass, RED after
    two missed ones -- judging_throughput too, although it is ALWAYS_RUN."""
    now = datetime(2026, 10, 29, 16, tzinfo=UTC)
    pubs = ["productivity_census", "certificate_clock_law", "judging_throughput"]
    assert set(pubs) <= LR.MONEY_CRITICAL and "judging_throughput" in LR.ALWAYS_RUN
    roster = ["tier_s", *pubs]
    att = _att(dict.fromkeys(roster, 9),
               ages_h={"tier_s": 0.5, "productivity_census": 4.2, "certificate_clock_law": 4.2,
                       "judging_throughput": 1.7},
               costs={"tier_s": 9000.0, "productivity_census": 300.0,
                      "certificate_clock_law": 90.0, "judging_throughput": 200.0}, now=now)
    dec = LR.plan_pass(roster, att, plan="core", budget_s=2640.0, now=now,
                       prior=_prior(now - timedelta(hours=1), dict.fromkeys(pubs, 1), roster))
    assert set(pubs) <= dec.admitted, "admitted every pass, whatever the budget"
    assert set(dec.red) == set(pubs), dec.red
    assert dec.planned_s == pytest.approx(9000.0 + 300.0 + 90.0 + 200.0), "each charged once"


def test_a_stuck_leg_timeout_is_red_and_its_cap_grows(tmp_path: Path) -> None:
    """math_lab (720 s) / physics_lab (700 s): LEG_TIMEOUT every pass, 0 artifacts moved."""
    led = tmp_path / "compute_ledger.jsonl"
    rows = [{"at": f"2026-10-29T0{i}:00:00+00:00", "run": leg, "wall_s": cap,
             "outcome": "TIMEOUT", "output_hash": "same"}
            for i in range(4) for leg, cap in (("math_lab", 720.0), ("physics_lab", 700.0))]
    rows.append({"at": "2026-10-29T05:00:00+00:00", "run": "moving", "wall_s": 600.0,
                 "outcome": "TIMEOUT", "output_hash": "a"})
    rows.append({"at": "2026-10-29T06:00:00+00:00", "run": "moving", "wall_s": 600.0,
                 "outcome": "TIMEOUT", "output_hash": "b"})
    led.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    att = LR.read_attendance(led)
    # The first row only sets the artifact baseline; the three after it moved nothing.
    assert att.stuck["math_lab"] == 3 and att.stuck_timeout("physics_lab")
    assert not att.stuck_timeout("moving"), "a timeout that moved its artifact is progress"
    dec = LR.plan_pass(["math_lab", "physics_lab", "moving"], att, plan="dept:mathlab",
                       budget_s=8856.0)
    assert dec.stuck_timeouts == ["math_lab", "physics_lab"]
    assert {"math_lab", "physics_lab"} <= set(dec.red)
    assert "0 artifacts moved" in dec.red["math_lab"]
    cap, why = LR.measured_cap("math_lab", att, 720.0, 8856.0)
    assert cap == pytest.approx(720.0 * LR.TIMEOUT_GROWTH) and "stuck" in why
    # Bounded: never past TIMEOUT_GROWTH_MAX x base, nor half a bounded plan's budget.
    att.stuck["math_lab"] = 40
    assert LR.measured_cap("math_lab", att, 720.0, 8856.0)[0] == pytest.approx(2880.0)
    assert LR.measured_cap("math_lab", att, 720.0, 2000.0)[0] == pytest.approx(1000.0)
    # One-sided, and never for an ALWAYS_RUN leg (tier_s's cap is its owner's).
    att.stuck["tier_s"] = 40
    assert LR.measured_cap("tier_s", att, 1500.0, 0.0) == (1500.0, "")
    assert LR.measured_cap("never_seen", att, 300.0)[0] == pytest.approx(300.0)


def test_a_finish_resets_stuck_and_the_measured_cap_holds(tmp_path: Path) -> None:
    led = tmp_path / "compute_ledger.jsonl"
    rows = [{"at": f"2026-10-29T0{i}:00:00+00:00", "run": "math_lab", "wall_s": 720.0,
             "outcome": "TIMEOUT", "output_hash": "x"} for i in range(3)]
    rows.append({"at": "2026-10-29T04:00:00+00:00", "run": "math_lab", "wall_s": 1228.0,
                 "outcome": "ok", "output_hash": "y"})
    led.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    att = LR.read_attendance(led)
    assert not att.stuck_timeout("math_lab")
    cap, why = LR.measured_cap("math_lab", att, 720.0, 8856.0)
    assert cap == pytest.approx(1228.0 * LR.MEASURED_HEADROOM) and "measured" in why
    again = LR.Attendance.from_json(json.loads(json.dumps(att.to_json())))
    assert again.ok_walls["math_lab"] == [1228.0], "the measurement survives the record"


# --- Auditor HOLD 2026-10-29: MF1 run-first prelude, MF2 charged/bounded raise, MF3 mining ----


def test_liftable_legs_admits_module_level_calls_and_refuses_main_locals(tmp_path: Path) -> None:
    src = tmp_path / "cycle.py"
    src.write_text(
        "def _producer(*a):\n    return {}\n"
        "def allocator_join():\n    return {}\n"
        "def main():\n"
        "    h = 1\n"
        "    _costed('allocator_join', allocator_join)\n"
        "    _costed('desk_health', lambda: _producer('desk_health', 'x.py', '--out'))\n"
        "    _costed('frontier_report', lambda: frontier_report(h))\n", encoding="utf-8")
    lift = LR.liftable_legs(src)
    assert lift["allocator_join"] == "allocator_join"
    assert "desk_health" in lift and "_producer" in lift["desk_health"]
    assert "frontier_report" not in lift, "a call over main() locals cannot run ahead of file order"


def test_every_money_critical_core_leg_is_liftable_from_the_real_cycle() -> None:
    lift = LR.liftable_legs(LR.CYCLE)
    roster = LR.legs_in_order(LR.CYCLE)
    assert {leg for leg in LR.MONEY_CRITICAL if leg in roster} <= set(lift)


def _tail_roster() -> list[str]:
    head = ["smoke_release", "tier_s"]
    return head + [f"leg_{i}" for i in range(20)] + ["kelly_survival", "desk_health"]


def test_mf1_money_legs_past_the_kill_run_first() -> None:
    """Always-run past the kill: money legs in the tail are lifted into the prelude, in file
    order, and the leg whose call cannot be rebuilt is named UNREACHABLE."""
    roster = [*_tail_roster(), "prop_challenge_allocator"]
    costs = {"smoke_release": 120.0, "tier_s": 3600.0, "kelly_survival": 5.0, "desk_health": 5.0,
             "prop_challenge_allocator": 5.0, **{f"leg_{i}": 30.0 for i in range(20)}}
    att = _att(dict.fromkeys(roster, 3), costs=costs)
    dec = LR.plan_pass(roster, att, plan="core", budget_s=2640.0, kill_s=3300.0,
                       liftable={"kelly_survival", "desk_health"})
    assert dec.lifted == ["kelly_survival", "desk_health"]
    assert dec.unreachable == ["prop_challenge_allocator"]
    assert "RUN FIRST" in dec.why["desk_health"]
    assert "UNREACHABLE" in dec.why["prop_challenge_allocator"]
    assert dec.capacity["always_run_past_kill"] is True
    assert dec.capacity["headroom_s"] == dec.capacity["per_pass_s"]
    # Without the liftable set, file order is left exactly as it was.
    assert LR.plan_pass(roster, att, plan="core", budget_s=2640.0).lifted == []


def test_mf1_lifting_never_pushes_a_reachable_always_run_leg_past_the_kill() -> None:
    roster = ["smoke_release", "tier_s", "leg_0", "desk_health"]
    att = _att(dict.fromkeys(roster, 3), costs={"smoke_release": 100.0, "tier_s": 3195.0,
                                                "leg_0": 30.0, "desk_health": 10.0})
    dec = LR.plan_pass(roster, att, plan="core", budget_s=2640.0, kill_s=3300.0,
                       liftable=set(roster))
    assert dec.lifted == [] and dec.unreachable == ["desk_health"]
    assert "tier_s" in dec.why["desk_health"]


def test_mf1_money_legs_that_fit_keep_their_file_order_place() -> None:
    roster = ["smoke_release", "leg_0", "desk_health"]
    att = _att(dict.fromkeys(roster, 3), costs={"smoke_release": 60.0, "leg_0": 30.0,
                                                "desk_health": 10.0})
    dec = LR.plan_pass(roster, att, plan="core", budget_s=2640.0, liftable=set(roster))
    assert dec.lifted == [] and dec.unreachable == []


def test_mf_a_a_money_leg_finishing_between_budget_and_kill_line_is_not_lifted() -> None:
    """Audit MF-A: lifting starts at the kill-side line, never at the budget. A money leg
    projected to finish after the 2,640 s budget but inside the line runs fresh in file order,
    after its producers, instead of reading last pass's inputs from the prelude."""
    roster = ["smoke_release", "tier_s", "desk_health"]
    att = _att(dict.fromkeys(roster, 3), costs={"smoke_release": 2600.0, "tier_s": 60.0,
                                                "desk_health": 10.0})
    dec = LR.plan_pass(roster, att, plan="core", budget_s=2640.0, kill_s=3300.0,
                       liftable=set(roster))
    line = 2640.0 + LR.OUT_OF_BUDGET_SHARE * (3300.0 - 2640.0)
    assert 2640.0 < 2670.0 <= line
    assert "desk_health" in dec.admitted
    assert dec.lifted == [] and dec.unreachable == []


def _stuck_att(legs: list[str], base: float = 300.0, n: int = 4) -> LR.Attendance:
    att = _att(dict.fromkeys(legs, n), costs=dict.fromkeys(legs, base))
    for leg in legs:
        att.costs[leg] = [base] * n
        att.timeouts[leg] = n
        att.stuck[leg] = n
    return att


def test_mf2_raises_are_charged_and_bounded_across_the_pass() -> None:
    """30 stuck legs: each granted raise is CHARGED, and the raised seconds of a pass stay inside
    RAISE_PASS_SHARE of the budget (the first raise is whole: a part-raise kills it short)."""
    legs = [f"stuck_{i}" for i in range(30)]
    att = _stuck_att(legs)
    for leg in legs:
        att.last_at[leg] = (datetime.now(tz=UTC) - timedelta(hours=10)).isoformat()
    prior = {"ageing": {"core": {"pass_started": (datetime.now(tz=UTC) - timedelta(hours=1))
                                 .isoformat(), "starve_passes": dict.fromkeys(legs, 5)}}}
    dec = LR.plan_pass(legs, att, plan="core", budget_s=2640.0, prior=prior)
    assert dec.raise_grants, "a stuck leg must still be granted its raise"
    extra = sum(cap - 300.0 for cap in dec.raise_grants.values())
    assert extra <= max(LR.RAISE_PASS_SHARE * 2640.0, max(
        cap - 300.0 for cap in dec.raise_grants.values()))
    assert dec.capacity["raised_s"] == pytest.approx(extra, abs=0.5)
    for leg, cap in dec.raise_grants.items():
        assert dec.charged[leg] == cap, "the raised cap is what the plan charges"
    assert dec.planned_s <= LR.kill_for(2640.0)
    granted = next(iter(dec.raise_grants))
    ungranted = next(leg for leg in legs if leg not in dec.raise_grants)
    assert dec.cap_for(granted, att, 300.0)[0] == pytest.approx(dec.raise_grants[granted])
    assert dec.cap_for(ungranted, att, 300.0) == (300.0, ""), "no grant, no uncharged raise"


def test_mf2_unbounded_plan_keeps_measured_cap() -> None:
    att = _stuck_att(["math_lab"], base=720.0)
    dec = LR.plan_pass(["math_lab"], att, plan="dept:labs", budget_s=0.0)
    assert dec.cap_for("math_lab", att, 720.0) == LR.measured_cap("math_lab", att, 720.0, 0.0)


def test_mf3_mining_is_admitted_ahead_of_the_bands_that_spend_the_budget() -> None:
    roster = ["smoke_release", "queue_cycle"] + [f"leg_{i}" for i in range(40)]
    costs = {"smoke_release": 1000.0, "queue_cycle": 150.0,
             **{f"leg_{i}": 100.0 for i in range(40)}}
    att = _att(dict.fromkeys(roster, 3), costs=costs)
    for leg in roster:
        att.last_at[leg] = (datetime.now(tz=UTC) - timedelta(hours=10)).isoformat()
    prior = {"ageing": {"core": {"pass_started": (datetime.now(tz=UTC) - timedelta(hours=1))
                                 .isoformat(), "starve_passes": dict.fromkeys(roster, 4)}}}
    dec = LR.plan_pass(roster, att, plan="core", budget_s=1200.0, prior=prior,
                       mining={"queue_cycle"})
    assert dec.mining == ["queue_cycle"]
    assert "queue_cycle" in dec.protected
    assert dec.should_run("queue_cycle", att, 5000.0)[0], "mining is never yielded"
    # The out-of-budget bands stop at the kill-side line.
    line = 1200.0 + LR.OUT_OF_BUDGET_SHARE * (LR.kill_for(1200.0) - 1200.0)
    assert dec.planned_s <= line + 100.0


def test_record_merges_under_the_writer_lock(tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    """The shared record's read-modify-write runs under the repo's OS lock (alert_ledger)."""
    from libs.ops import alert_ledger
    seen: list[str] = []
    real = alert_ledger.os_lock

    def spy(lock: Path, timeout_s: float = 10.0):  # type: ignore[no-untyped-def]
        seen.append(lock.name)
        return real(lock, timeout_s)
    monkeypatch.setattr(alert_ledger, "os_lock", spy)
    att = _att({"a": 1})
    dec = LR.plan_pass(["a"], att, plan="core", budget_s=100.0)
    out = tmp_path / "LEG_ROTATION.json"
    doc = LR.record(dec, att, ["a"], path=out, residents={})
    assert seen == ["LEG_ROTATION.json.flock"]
    assert "write_error" not in doc and LR.load_record(out)["liveness"]["verdict"]
    assert not list(tmp_path.glob("*.tmp"))


def test_record_reports_a_held_lock_instead_of_writing_unlocked(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(LR, "RECORD_LOCK_WAIT_S", 0.05)
    out = tmp_path / "LEG_ROTATION.json"
    from libs.ops.alert_ledger import os_lock
    att = _att({"a": 1})
    dec = LR.plan_pass(["a"], att, plan="core", budget_s=100.0)
    # A second open handle conflicts with the first (flock / msvcrt lock per handle).
    with os_lock(out.with_name(out.name + ".flock")):
        doc = LR.record(dec, att, ["a"], path=out, residents={})
    assert "AlertLedgerBusy" in doc["write_error"]
    assert not out.exists(), "a writer that cannot get the lock never writes unlocked"
    assert doc["liveness"]["verdict"] in {"RED", "GREEN"}
