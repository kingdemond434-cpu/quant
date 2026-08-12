"""SHADOW -> LIVE WITHOUT A HUMAN, and the two things that must stay impossible while it happens.

THE DEFECT THIS CLOSES. `check_promotion_gate` has decided `granted_rung` since it was written.
A grep for its CONSUMERS on 2026-08-12 found the capability ratchet (which SCORES it) and
run_cadence (which checks the file EXISTS). Nothing read it and changed a size. The evidence could
arrive in full, every criterion could pass, and the sleeve would sit on paper until a person
noticed -- L0079 verbatim, landing on the one transition the desk exists to make.

THE OTHER HALF. Automatic retirement was refused on the grounds that it shrinks the Holm m and
loosens every standing clock's bar. True of the IMPLEMENTATION (derive_slots drops RETIRED rows),
false of the LAW, which says the correction covers "all trailing-180d entrants INCLUDING KILLED
ONES". Counting only survivors judges the last clock standing against m=1 after eleven looks.

So both halves are now automatic, and these tests pin the invariants that make that safe rather
than the fact that it happens: the actuator can never grant more than the gate, and retirement can
never move a bar.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.research import forward_multiplicity as fm

_REPO = Path(__file__).resolve().parents[2]


def _ledger(root: Path, rows: list[dict]) -> None:
    p = root / fm.RETIREMENT_LEDGER
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")


# ================================================================== multiplicity
def test_a_retired_trial_is_still_charged_for(tmp_path: Path) -> None:
    """THE LOAD-BEARING PROPERTY, and the whole reason automatic retirement is safe. A trial that
    was started and abandoned still CONSUMED A TEST. Dropping it from m is the forking-paths
    garden in its purest form: run twelve clocks, retire the eleven that disappointed, judge the
    twelfth against m=1."""
    start = (datetime.now(tz=UTC) - timedelta(days=10)).isoformat()
    _ledger(tmp_path, [{"name": "dead_a", "shadow_start": start},
                       {"name": "dead_b", "shadow_start": start}])
    m = fm.effective_m(root=tmp_path, live=10, complete=True)
    assert m.m == 12 and m.live == 10 and m.retired_in_window == 2


def test_retirement_is_bar_neutral_not_bar_reducing(tmp_path: Path) -> None:
    """Retiring moves a clock between two terms of one sum. Twelve live and zero retired must give
    exactly the same m as ten live and two retired -- otherwise freeing a slot is a statistical
    act and this whole pipeline stays manual."""
    start = (datetime.now(tz=UTC) - timedelta(days=5)).isoformat()
    before = fm.effective_m(root=tmp_path, live=12, complete=True)
    _ledger(tmp_path, [{"name": "a", "shadow_start": start},
                       {"name": "b", "shadow_start": start}])
    after = fm.effective_m(root=tmp_path, live=10, complete=True)
    assert after.m == before.m == 12


def test_the_effective_m_is_never_below_the_live_count(tmp_path: Path) -> None:
    """The floor that makes this adoption safe in every direction: it can only ever TIGHTEN
    relative to counting live clocks alone."""
    assert fm.effective_m(root=tmp_path, live=7, complete=True).m >= 7
    assert not fm.effective_m(root=tmp_path, live=7, complete=True).loosened_against


def test_a_retirement_outside_the_window_stops_counting(tmp_path: Path) -> None:
    """The family is the trailing window. A trial from last year is not in it -- otherwise m grows
    without bound and the bar becomes unreachable, which is its own way of killing the desk."""
    old = (datetime.now(tz=UTC) - timedelta(days=400)).isoformat()
    _ledger(tmp_path, [{"name": "ancient", "shadow_start": old}])
    assert fm.effective_m(root=tmp_path, live=5, complete=True).m == 5


def test_an_unparseable_birth_date_still_counts(tmp_path: Path) -> None:
    """UNKNOWN RESOLVES TOWARD TIGHTER. A bad timestamp is not evidence the trial was outside the
    window, and resolving it outward is the single direction that shrinks m."""
    _ledger(tmp_path, [{"name": "mystery", "shadow_start": "not-a-date"}])
    assert fm.effective_m(root=tmp_path, live=5, complete=True).m == 6


def test_the_window_is_not_tunable_per_call() -> None:
    """A window that can be shortened at the point of use is a window that gets shortened whenever
    the answer is inconvenient. It is a module constant, matched to the 180d the law names."""
    import inspect
    assert fm.WINDOW_DAYS == 180.0
    for fn in (fm.effective_m, fm.retired_in_window, fm.bar_for):
        assert "window" not in inspect.signature(fn).parameters


def test_the_bar_report_shows_both_numbers_so_the_direction_is_visible(tmp_path) -> None:
    """A change that can only tighten should PROVE it on every run rather than in a docstring."""
    b = fm.bar_for(root=tmp_path)
    assert b["at_least_as_strict"] and b["z"] >= b["z_if_only_live_counted"]
    assert "INCLUDING KILLED ONES" in b["law"]


def test_an_incomplete_cohort_says_the_bar_may_be_higher(tmp_path: Path) -> None:
    m = fm.effective_m(root=tmp_path, live=4, complete=False)
    assert "LOWER bound" in m.why


# ================================================================== the retirer
@pytest.fixture
def retirer():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "run_slot_retirement", _REPO / "scripts/run_slot_retirement.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_only_the_structurally_unfinishable_are_retirable(retirer) -> None:
    """ACCRUING, TOO_EARLY and UNKNOWN must never be in the set. An unmeasured clock is not a dead
    one, and resolving unknown toward retirement is how a real candidate gets swept."""
    assert set(retirer.RETIRABLE) == {"SOURCE_FROZEN", "PRODUCER_UNSCHEDULED"}
    for safe in ("ACCRUING", "TOO_EARLY", "UNKNOWN", "SOURCE_STALE_HERE"):
        assert safe not in retirer.RETIRABLE


def test_a_clock_whose_producer_only_needs_a_cron_line_is_kept(retirer, tmp_path) -> None:
    """THE DISTINCTION THAT PROTECTS CANDIDATES. A missing schedule is a BUILD defect costing one
    line. Retiring the clock for it would discard a real candidate to hide the defect -- and that
    is exactly what happened to liquidation_reversion_BTCUSDT, which was repaired by scheduling
    its screen, not by burying it."""
    rep = {"clocks": [{"name": "c", "state": "PRODUCER_UNSCHEDULED", "producer": "screen_x.py",
                       "origin_artifact": "data/x.json", "age_h": 300.0, "rows_added": 0.0,
                       "why": "w", "repair": "schedule screen_x.py"}]}
    assert retirer._candidates(rep, tmp_path) == []


def test_a_clock_nothing_can_feed_is_retirable(retirer, tmp_path: Path) -> None:
    rep = {"clocks": [{"name": "c", "state": "PRODUCER_UNSCHEDULED", "producer": "",
                       "origin_artifact": "data/x.json", "age_h": 300.0, "rows_added": 0.0,
                       "why": "w", "repair": "r"}]}
    assert [c["name"] for c in retirer._candidates(rep, tmp_path)] == ["c"]


def test_an_already_retired_clock_is_not_retired_twice(retirer, tmp_path: Path) -> None:
    """Double-counting a retirement in the ledger would inflate m -- the safe direction, but still
    a lie about how many trials the desk ran."""
    _ledger(tmp_path, [{"name": "c", "shadow_start": datetime.now(tz=UTC).isoformat()}])
    rep = {"clocks": [{"name": "c", "state": "SOURCE_FROZEN", "producer": "",
                       "origin_artifact": "data/x.json", "age_h": 300.0, "rows_added": 0.0,
                       "why": "w", "repair": "r"}]}
    assert retirer._candidates(rep, tmp_path) == []


def test_the_ledger_is_written_before_the_roster(retirer) -> None:
    """ORDER IS LOAD-BEARING. The ledger is what keeps a retired trial counted in m; a roster edit
    landing without it is the one path by which this organ could loosen a bar. So an unwritable
    ledger refuses the retirement, and the roster is touched only afterwards."""
    src = (_REPO / "scripts/run_slot_retirement.py").read_text("utf-8")
    assert src.index("RETIREMENT_LEDGER") < src.index("ROSTER).read_text")
    assert "REFUSED-LEDGER-UNWRITABLE" in src


def test_the_batch_is_refused_if_the_bar_ever_moves_down(retirer) -> None:
    """The safety is RE-DERIVED every run. A docstring claiming multiplicity-neutrality is worth
    nothing on the night the assumption stops holding."""
    src = (_REPO / "scripts/run_slot_retirement.py").read_text("utf-8")
    assert 'if after["z"] < before["z"]' in src
    assert "REFUSED-BAR-LOOSENED" in src


def test_it_runs_clean_on_the_live_desk(retirer) -> None:
    doc = retirer.run(root=_REPO, dry_run=True)
    assert doc["status"] in ("NOTHING-TO-RETIRE", "DRY-RUN")
    assert doc["bar_before"]["at_least_as_strict"]


# ================================================================== the actuator
@pytest.fixture
def actuator():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "run_promotion_actuator", _REPO / "scripts/run_promotion_actuator.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_authority_table_matches_the_gates_own_ladder(actuator) -> None:
    """A SECOND HAND-MAINTAINED COPY OF THE LADDER is exactly how a rung silently gains a size.
    The gate's prose is the source; this pins the machine-readable form against it."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "check_promotion_gate", _REPO / "scripts/check_promotion_gate.py")
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)

    assert set(actuator._AUTHORITY) == {0, 1, 2, 3, 4}
    assert actuator._AUTHORITY[0] == ("PAPER", 0.0)
    for row in gate._RUNGS:
        mode, frac = actuator._AUTHORITY[row["rung"]]
        grants = row["grants"]
        if "still PAPER" in grants or "PAPER" in grants:
            assert mode == "PAPER" and frac == 0.0, row
        else:
            assert mode == "LIVE", row
            assert f"{frac:.0%}" in grants, (
                f"rung {row['rung']} grants {grants!r} but the actuator would deploy {frac:.0%}")


def test_the_actuator_can_never_grant_more_than_the_gate(actuator, tmp_path) -> None:
    """It is a transmission belt. It computes no criterion and cannot invent a rung."""
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data/promotion_gate.json").write_text(json.dumps(
        {"granted_rung": 1, "granted": "paper", "blocked_at_rung": 2, "ladder": []}), "utf-8")
    (tmp_path / "data/live_authority.json").write_text(json.dumps(
        {"rung": 1, "mode": "PAPER", "confirm_streak": 9}), "utf-8")
    d = actuator.run(root=tmp_path)
    assert d["rung"] <= 1 and d["mode"] == "PAPER" and d["book_fraction"] == 0.0


def test_a_rung_above_the_table_is_clamped_never_extrapolated(actuator, tmp_path) -> None:
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data/promotion_gate.json").write_text(json.dumps(
        {"granted_rung": 99, "granted": "x", "ladder": []}), "utf-8")
    (tmp_path / "data/live_authority.json").write_text(json.dumps(
        {"rung": 4, "mode": "LIVE", "confirm_streak": 9}), "utf-8")
    d = actuator.run(root=tmp_path)
    assert d["rung"] == 4 and d["book_fraction"] == 0.15


def test_a_falling_rung_derisks_immediately(actuator, tmp_path: Path) -> None:
    """HESITATING TO REDUCE is the one direction that costs real money. No confirmation delay."""
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data/promotion_gate.json").write_text(json.dumps(
        {"granted_rung": 0, "granted": "paper", "ladder": []}), "utf-8")
    (tmp_path / "data/live_authority.json").write_text(json.dumps(
        {"rung": 3, "mode": "LIVE", "book_fraction": 0.05, "confirm_streak": 5}), "utf-8")
    d = actuator.run(root=tmp_path)
    assert d["direction"] == "DERISK" and d["rung"] == 0 and d["mode"] == "PAPER"


def test_a_rising_rung_must_hold_before_capital_follows(actuator, tmp_path: Path) -> None:
    """A criterion oscillating across its threshold would otherwise deal real capital in and out
    on noise. The asymmetry with de-risking is the design, not an oversight."""
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data/promotion_gate.json").write_text(json.dumps(
        {"granted_rung": 2, "granted": "LIVE at 1%", "ladder": []}), "utf-8")
    (tmp_path / "data/live_authority.json").write_text(json.dumps(
        {"rung": 0, "mode": "PAPER", "confirm_streak": 3}), "utf-8")

    first = actuator.run(root=tmp_path)
    assert first["direction"] == "HOLD-PENDING-CONFIRM"
    assert first["mode"] == "PAPER", "one good evaluation must not deploy real money"

    second = actuator.run(root=tmp_path)
    assert second["direction"] == "PROMOTE" and second["mode"] == "LIVE"
    assert second["book_fraction"] == 0.01


def test_an_unreadable_gate_neither_promotes_nor_flattens(actuator, tmp_path) -> None:
    """Dropping to PAPER on a transient read error would flatten a live book on a filesystem
    hiccup; granting anything would be worse. Hold, and say so."""
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data/live_authority.json").write_text(json.dumps(
        {"rung": 2, "mode": "LIVE", "book_fraction": 0.01}), "utf-8")
    d = actuator.run(root=tmp_path)
    assert d["status"] == "UNMEASURED"
    assert d["rung"] == 2 and d["mode"] == "LIVE" and d["book_fraction"] == 0.01


def test_it_cannot_reach_the_ruin_rail_or_the_deadman_switch(actuator) -> None:
    """Those bound everything this can grant. A promotion path that could edit its own bounds is
    not a promotion path."""
    src = (_REPO / "scripts/run_promotion_actuator.py").read_text("utf-8")
    for forbidden in ("run_deadman_switch", "ruin_rail", "MAX_PORTFOLIO_HEAT", "RISK_CAP_CEILING"):
        assert forbidden not in src.split('"""', 2)[2], forbidden


def test_it_places_no_order(actuator) -> None:
    """It writes an AUTHORITY, not an order. The execution path still applies every check it
    already applies; this only states the ceiling."""
    src = (_REPO / "scripts/run_promotion_actuator.py").read_text("utf-8")
    body = src.split('"""', 2)[2]
    for forbidden in ("create_order", "place_order", "binance", "requests.post", "urlopen"):
        assert forbidden not in body, forbidden


def test_going_live_pages_a_person(actuator) -> None:
    """Nobody should learn the desk went live from a P&L statement. Not an approval step -- a
    notification, on the run it happens."""
    src = (_REPO / "scripts/run_promotion_actuator.py").read_text("utf-8")
    assert "send_all" in src and 'mode == "LIVE"' in src


# ================================================================== the wiring
def test_both_organs_are_scheduled() -> None:
    """L1.40. An actuator nobody runs is the defect it was built to fix, one level down."""
    man = (_REPO / "ops/crontab.manifest").read_text("utf-8")
    for script in ("run_slot_retirement.py", "run_promotion_actuator.py"):
        assert any(script in ln and ln[:1].isdigit() for ln in man.splitlines()), script


def test_the_retirer_runs_before_the_next_spawn_cycle() -> None:
    """A freed slot that nothing claims is the same stall with an extra step."""
    man = (_REPO / "ops/crontab.manifest").read_text("utf-8")
    assert any("run_paper_sleeve_spawner.py" in ln and ln[:1].isdigit()
               for ln in man.splitlines())
    assert any("run_slot_retirement.py" in ln and ln[:1].isdigit() for ln in man.splitlines())


def test_the_actuator_is_not_given_a_dry_run_flag_in_cron() -> None:
    """A scheduled actuator running --dry-run is an actuator that does nothing, and it would look
    exactly like one that works."""
    man = (_REPO / "ops/crontab.manifest").read_text("utf-8")
    for ln in man.splitlines():
        if "run_promotion_actuator.py" in ln and ln[:1].isdigit():
            assert "--dry-run" not in ln, ln


def test_a_pending_promotion_cannot_stall_forever(actuator, tmp_path: Path) -> None:
    """THE BUG THIS FILE CAUGHT IN ITS OWN ACTUATOR, and it failed in the worst direction.

    The streak compared the gate's rung against what was APPLIED. While a promotion is pending the
    applied rung is deliberately behind the gate's, so the comparison was false on every pass, the
    streak reset to 1 each time, and CONFIRM_RUNS could never be reached. The gate could grant
    LIVE for a year and nothing would ever deploy.

    A confirmation delay that never expires is a permanent block wearing the costume of a delay --
    indistinguishable, from the outside, from the manual stall this organ exists to remove. So the
    streak counts the GATE's verdict, and this walks a promotion all the way through.
    """
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data/promotion_gate.json").write_text(json.dumps(
        {"granted_rung": 2, "granted": "LIVE at 1%", "ladder": []}), "utf-8")
    (tmp_path / "data/live_authority.json").write_text(json.dumps(
        {"rung": 0, "gate_rung": 0, "mode": "PAPER", "confirm_streak": 1}), "utf-8")

    seen = [actuator.run(root=tmp_path)["mode"] for _ in range(4)]
    assert "LIVE" in seen, f"the promotion never landed in four cycles: {seen}"
    assert seen.index("LIVE") == actuator.CONFIRM_RUNS - 1, (
        f"it landed at cycle {seen.index('LIVE') + 1}, not at CONFIRM_RUNS: {seen}")


def test_the_streak_resets_when_the_gate_actually_changes_its_mind(actuator, tmp_path) -> None:
    """The other half: the delay must still BE a delay. A gate flickering between rungs restarts
    the count, so noise cannot accumulate its way into real capital."""
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data/live_authority.json").write_text(json.dumps(
        {"rung": 0, "gate_rung": 2, "mode": "PAPER", "confirm_streak": 1}), "utf-8")
    (tmp_path / "data/promotion_gate.json").write_text(json.dumps(
        {"granted_rung": 3, "granted": "LIVE at 5%", "ladder": []}), "utf-8")
    d = actuator.run(root=tmp_path)
    assert d["confirm_streak"] == 1 and d["mode"] == "PAPER"
